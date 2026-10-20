"""PC heartbeat: the always-on PC (a Surface in a drawer, say) tells the cloud it is alive, so the cloud monitor can
alert the phone when it is not.

Every `every_s` seconds the PC server pushes one tiny commit (just heartbeat.json) to the `heartbeat` branch of the
repo, replacing the previous one (orphan commit, force push: no history grows). The cloud monitor (GitHub Actions) reads
that branch on every run and alerts when the bot said it was running but has been silent for 20 minutes in a session.

heartbeat.json: {"t": unix seconds, "running": bot running, "adapter": paper|ninjatrader|tradovate, "position": bool,
                 "model_state": str, "host": computer name, "every_s": N,
                 "acct": the Accounts page's view of the routed activity (engine/accounts.pc_activity: account name + SIM/LIVE,
                         open position, today's orders, last 60 closed routed trades, the eval's P&L per day; secret-free,
                         under 48 KB; older cloud monitors ignore it),
                 "health": is the bot really trading the eval (engine/accounts.pc_health: account name + LIVE/SIM, adapter
                           enabled or the DISABLED reason, armed, NINJATRADER_LIVE set (a bool), NinjaTrader connection,
                           feed source + age of the last 1m / 5m bar, last poll + errors, the LIT stage, setups seen today,
                           orders today, kill flag, uptime; secret-free, ~2 KB; the cloud's verdict: accounts.verdict),
                 "ops": the owner's PC helpers (engine/ops_checks.hb_fields: last check red / yellow count + first fix,
                        last backup, free disk; ~200 bytes)}
Every beat also writes the payload to logs/heartbeat_last.json (local, gitignored) for HEALTH_CHECK and the ops task.

No Yahoo (engine/pcbars.py, owner 2026-10-19): next to heartbeat.json the commit carries the PC's NinjaTrader bars,
bars_1m.csv.gz (last 3 days of 1m, every push) and bars_5m.csv.gz (last 40 days of 5m, rebuilt hourly; unchanged = the
same blob, nothing new to push), plus heartbeat.json "bars" (newest bar times, the forming 1m bar's open). The cloud monitor
and the fast-entry watcher trade the paper ledger on them instead of Yahoo. While a LIT setup is armed or a trade is open
in a session the PC pushes every FAST_EVERY_S seconds instead of every_s, so the cloud's watcher sees the entry soon.

On by default only when LE_HEARTBEAT=1 (scripts/run_bot.ps1 sets it; a dev shell does not push anything). Needs git
with push rights in the project folder (the owner's PC has them). Never raises into the server; failures are logged
at most once an hour.
"""
from __future__ import annotations

import json
import os
import platform
import subprocess
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRANCH = "heartbeat"
SILENT_AFTER_S = 20 * 60
LAST_PATH = os.path.join(ROOT, "logs", "heartbeat_last.json")   # the last payload, for engine/ops_checks (logs/ is gitignored)
FAST_EVERY_S = 60
FAST_STAGES = ("limit", "cisd1m", "trade")       # engine/accounts._lit_stage: a setup armed, or in a trade


def enabled() -> bool:
    return os.environ.get("LE_HEARTBEAT", "0") == "1"


def _git(args, cwd, inp=None, timeout=60):
    return subprocess.run(["git", *args], cwd=cwd, input=inp, capture_output=True, text=True, timeout=timeout)


def _blob(data: bytes, cwd) -> str | None:
    """git hash-object -w of raw bytes (binary stdin: no newline translation on Windows). The id, or None."""
    r = subprocess.run(["git", "hash-object", "-w", "--stdin"], cwd=cwd, input=data, capture_output=True, timeout=60)
    out = r.stdout.decode(errors="replace").strip()
    return out if not r.returncode and len(out) >= 40 else None


def push(payload: dict, cwd: str = ROOT, remote: str = "origin", branch: str = BRANCH, files: dict | None = None) -> dict:
    """Write payload as heartbeat.json (+ `files`: {name: bytes}, e.g. the PC's NinjaTrader bars) in an orphan commit and
    force-push it to remote/branch. Touches neither the working tree nor the index (git plumbing only). Returns {"ok", "error"}."""
    try:
        body = json.dumps(payload, separators=(",", ":"))
        blob = _blob(body.encode("utf-8"), cwd)
        if not blob:
            return {"ok": False, "error": "hash-object failed"}
        entries = [f"100644 blob {blob}\theartbeat.json\n"]
        for name, data in sorted((files or {}).items()):
            if not data or "/" in name or "\t" in name or "\n" in name:
                continue
            b = _blob(bytes(data), cwd)
            if not b:
                return {"ok": False, "error": f"hash-object failed ({name})"}
            entries.append(f"100644 blob {b}\t{name}\n")
        # bytes, not text: on Windows text-mode stdin turns "\n" into "\r\n" and the file was named "heartbeat.json\r"
        r = subprocess.run(["git", "mktree"], cwd=cwd, input="".join(entries).encode(),
                           capture_output=True, timeout=60)
        r.stdout, r.stderr = r.stdout.decode(errors="replace"), r.stderr.decode(errors="replace")
        if r.returncode:
            return {"ok": False, "error": r.stderr.strip()[:200] or "mktree failed"}
        tree = r.stdout.strip()
        env = {**os.environ, "GIT_AUTHOR_NAME": "liquidity-engine-pc", "GIT_AUTHOR_EMAIL": "pc@liquidity-engine.local",
               "GIT_COMMITTER_NAME": "liquidity-engine-pc", "GIT_COMMITTER_EMAIL": "pc@liquidity-engine.local"}
        r = subprocess.run(["git", "commit-tree", tree, "-m", f"heartbeat {payload.get('t')}"], cwd=cwd, capture_output=True, text=True,
                           timeout=60, env=env)
        if r.returncode:
            return {"ok": False, "error": r.stderr.strip()[:200] or "commit-tree failed"}
        commit = r.stdout.strip()
        r = _git(["push", "-q", "--force", remote, f"{commit}:refs/heads/{branch}"], cwd, timeout=90)
        if r.returncode:
            return {"ok": False, "error": r.stderr.strip()[-200:] or "push failed"}
        return {"ok": True, "commit": commit[:10]}
    except Exception as e:
        return {"ok": False, "error": f"{e.__class__.__name__}: {e}"}


def read_file(name: str, cwd: str = ROOT, ref: str = "FETCH_HEAD") -> bytes | None:
    """The raw bytes of one file of the fetched heartbeat commit (None when it is not there)."""
    try:
        r = subprocess.run(["git", "show", f"{ref}:{name}"], cwd=cwd, capture_output=True, timeout=60)
        return r.stdout if not r.returncode and r.stdout else None
    except Exception:
        return None


def read(cwd: str = ROOT, remote: str = "origin", branch: str = BRANCH, now: float | None = None, files=()) -> dict:
    """Cloud side: fetch the branch and parse heartbeat.json. {"present": bool, "age_s", "silent": bool, ...payload}.
    files = names to read from the same commit too (raw bytes in hb["files"]; never stored in state.json)."""
    now = time.time() if now is None else now
    try:
        r = _git(["fetch", "-q", "--depth", "1", remote, branch], cwd, timeout=90)
        if r.returncode:
            return {"present": False, "reason": "no heartbeat branch"}
        r = _git(["show", f"FETCH_HEAD:heartbeat.json"], cwd)
        if r.returncode:
            # older Windows PCs wrote the name as "heartbeat.json\r" (text-mode stdin): read that blob by its id
            t = _git(["ls-tree", "FETCH_HEAD"], cwd)
            ids = [ln.split()[2] for ln in (t.stdout or "").splitlines()
                   if len(ln.split()) >= 4 and "heartbeat.json" in ln.split("\t", 1)[-1]]
            r = _git(["cat-file", "-p", ids[0]], cwd) if ids else r
        if r.returncode:
            return {"present": False, "reason": "no heartbeat.json"}
        hb = json.loads(r.stdout)
    except Exception as e:
        return {"present": False, "reason": f"{e.__class__.__name__}: {e}"}
    if files:
        hb["files"] = {n: read_file(n, cwd) for n in files}
    age = max(0.0, now - float(hb.get("t") or 0))
    every = float(hb.get("every_s") or 300)
    hb.update(present=True, age_s=int(age), silent=bool(hb.get("running")) and age > max(SILENT_AFTER_S, 3 * every))
    return hb


def _push_pk():
    try:
        from engine import push
        return push.pc_public_key()
    except Exception:
        return None


def _health(bot):
    """The "health" block (engine/accounts.pc_health). Never raises; None when unavailable."""
    try:
        from engine import accounts
        return accounts.pc_health(bot)
    except Exception:
        return None


def _ops():
    """The owner's PC helpers' last result (engine/ops_checks.hb_fields: checks red / yellow, last backup, free disk)."""
    try:
        from . import ops_checks
        return ops_checks.hb_fields()
    except Exception:
        return None


def save_last(payload: dict, res: dict, path: str = LAST_PATH):
    """The last payload + push result, for HEALTH_CHECK / the ops task (engine/ops_checks reads it). Never raises."""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump({"saved_t": int(time.time()), "push": {"at": int(time.time()), **(res or {})}, "payload": payload}, fh,
                      separators=(",", ":"), default=str)
        os.replace(tmp, path)
    except Exception:
        pass


def _acct(bot):
    """The Accounts page block (engine/accounts.pc_activity). Never raises; None when unavailable."""
    try:
        from engine import accounts
        return accounts.pc_activity(bot)
    except Exception:
        return None


class Heartbeat:
    """Daemon thread on the PC server: pushes a heartbeat every `every_s` seconds while the server runs."""

    def __init__(self, bot, every_s: float = 300.0, log=print, last_path: str = LAST_PATH):
        self.bot, self.every_s, self.log, self.last_path = bot, every_s, log, last_path
        self.last: dict = {}
        self._stop = threading.Event()
        self._thread = None
        self._err_at = 0.0
        self._bars = None                    # engine.pcbars.PCBars, when no_yahoo is on

    def bar_files(self) -> dict:
        """The PC's NinjaTrader bars for the cloud (no_yahoo, engine/pcbars.py); {} when off or unavailable. Never raises."""
        try:
            from . import pcbars
            if not pcbars.no_yahoo(getattr(self.bot, "cfg", None) or None):
                return {}
            cfg = getattr(self.bot, "cfg", None) or {}
            if self._bars is None:
                self._bars = pcbars.PCBars(sym=cfg.get("sym") or "NQ", root=cfg.get("nt_archive") or pcbars.ARCHIVE_DIR)
            return self._bars.files(self.bot)
        except Exception as e:
            if time.time() - self._err_at > 3600:
                self._err_at = time.time()
                self.log(f"[heartbeat] bars not attached: {e.__class__.__name__}: {e}")
            return {}

    def payload(self) -> dict:
        st = getattr(self.bot, "state", None) or {}
        cfg = getattr(self.bot, "cfg", None) or {}
        return {"t": int(time.time()), "running": bool(getattr(self.bot, "running", False)), "adapter": cfg.get("adapter", "paper"),
                "position": bool(st.get("position")), "model_state": st.get("model_state"), "host": platform.node(),
                "model": (st.get("strategy") or {}).get("model") or cfg.get("model"),
                "push_pk": _push_pk(),          # phone notifications: the cloud seals the notification key to this (engine/push.py)
                "every_s": int(self.every_s), "acct": _acct(self.bot), "health": _health(self.bot), "ops": _ops()}

    def beat(self) -> dict:
        files = self.bar_files()
        pl = self.payload()
        if files:
            from . import pcbars
            pl["bars"] = pcbars.PCBars.meta(files, self.bot)
        res = push(pl, files=files)
        self.last = {"at": int(time.time()), **res}
        save_last(pl, res, self.last_path)
        if not res["ok"] and time.time() - self._err_at > 3600:
            self._err_at = time.time()
            self.log(f"[heartbeat] push failed: {res['error']}")
        return res

    def wait_s(self) -> float:
        """every_s, or FAST_EVERY_S while a LIT setup is armed / a trade is open in a session (the cloud watcher's bars)."""
        try:
            from . import accounts
            from .live import market_open
            if getattr(self.bot, "running", False) and market_open(time.time()) and \
                    accounts._lit_stage(getattr(self.bot, "state", None) or {}).get("stage") in FAST_STAGES:
                return float(min(self.every_s, FAST_EVERY_S))
        except Exception:
            pass
        return float(self.every_s)

    def _run(self):
        while not self._stop.is_set():
            self.beat()
            self._stop.wait(self.wait_s())

    def start(self):
        if not enabled():
            self.log("[heartbeat] off (set LE_HEARTBEAT=1 on the always-on PC)")
            return False
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._run, name="heartbeat", daemon=True)
            self._thread.start()
        return True

    def status(self) -> dict:
        return {"enabled": enabled(), "every_s": self.every_s, "last": self.last,
                "thread_alive": bool(self._thread and self._thread.is_alive())}


def selftest() -> bool:
    """Push to a temporary bare repo and read it back (no network)."""
    import shutil
    import tempfile
    d = tempfile.mkdtemp(prefix="le_hb_")
    try:
        bare, work = os.path.join(d, "bare.git"), os.path.join(d, "work")
        subprocess.run(["git", "init", "-q", "--bare", bare], check=True)
        subprocess.run(["git", "init", "-q", work], check=True)
        subprocess.run(["git", "-C", work, "remote", "add", "origin", bare], check=True)
        now = time.time()
        p = push({"t": int(now), "running": True, "adapter": "ninjatrader", "position": False, "every_s": 300}, cwd=work)
        assert p["ok"], p
        hb = read(cwd=work, now=now + 60)
        assert hb["present"] and not hb["silent"] and hb["adapter"] == "ninjatrader", hb
        hb2 = read(cwd=work, now=now + 30 * 60)
        assert hb2["silent"], hb2
        p2 = push({"t": int(now), "running": False, "every_s": 300}, cwd=work)
        assert p2["ok"] and not read(cwd=work, now=now + 30 * 60)["silent"]
        n = subprocess.run(["git", "-C", bare, "rev-list", "--count", BRANCH], capture_output=True, text=True).stdout.strip()
        assert n == "1", f"history grew: {n}"
        raw = bytes(range(256)) + b"\r\n\n"
        p3 = push({"t": int(now), "running": True, "every_s": 300}, cwd=work, files={"bars_1m.csv.gz": raw})
        hb3 = read(cwd=work, now=now + 60, files=("bars_1m.csv.gz", "missing.bin"))
        assert p3["ok"] and hb3["files"]["bars_1m.csv.gz"] == raw and hb3["files"]["missing.bin"] is None, hb3.get("files")
        print("heartbeat selftest OK: push, read, silent after 20 min, stopped bot never silent, no history growth, "
              "binary bar files round-trip byte for byte")
        return True
    finally:
        shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    import sys
    sys.exit(0 if selftest() else 1)
