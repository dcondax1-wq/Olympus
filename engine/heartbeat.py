"""PC heartbeat: the always-on PC (a Surface in a drawer, say) tells the cloud it is alive, so the cloud monitor can
alert the phone when it is not.

Every `every_s` seconds the PC server pushes one tiny commit (just heartbeat.json) to the `heartbeat` branch of the
repo, replacing the previous one (orphan commit, force push: no history grows). The cloud monitor (GitHub Actions) reads
that branch on every run and alerts when the bot said it was running but has been silent for 20 minutes in a session.

heartbeat.json: {"t": unix seconds, "running": bot running, "adapter": paper|ninjatrader|tradovate, "position": bool,
                 "model_state": str, "host": computer name, "every_s": N}

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


def enabled() -> bool:
    return os.environ.get("LE_HEARTBEAT", "0") == "1"


def _git(args, cwd, inp=None, timeout=60):
    return subprocess.run(["git", *args], cwd=cwd, input=inp, capture_output=True, text=True, timeout=timeout)


def push(payload: dict, cwd: str = ROOT, remote: str = "origin", branch: str = BRANCH) -> dict:
    """Write payload as heartbeat.json in an orphan commit and force-push it to remote/branch. Touches neither the
    working tree nor the index (git plumbing only). Returns {"ok", "error"}."""
    try:
        body = json.dumps(payload, separators=(",", ":"))
        r = _git(["hash-object", "-w", "--stdin"], cwd, inp=body)
        if r.returncode:
            return {"ok": False, "error": r.stderr.strip()[:200] or "hash-object failed"}
        blob = r.stdout.strip()
        r = _git(["mktree"], cwd, inp=f"100644 blob {blob}\theartbeat.json\n")
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


def read(cwd: str = ROOT, remote: str = "origin", branch: str = BRANCH, now: float | None = None) -> dict:
    """Cloud side: fetch the branch and parse heartbeat.json. {"present": bool, "age_s", "silent": bool, ...payload}."""
    now = time.time() if now is None else now
    try:
        r = _git(["fetch", "-q", "--depth", "1", remote, branch], cwd, timeout=90)
        if r.returncode:
            return {"present": False, "reason": "no heartbeat branch"}
        r = _git(["show", f"FETCH_HEAD:heartbeat.json"], cwd)
        if r.returncode:
            return {"present": False, "reason": "no heartbeat.json"}
        hb = json.loads(r.stdout)
    except Exception as e:
        return {"present": False, "reason": f"{e.__class__.__name__}: {e}"}
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


class Heartbeat:
    """Daemon thread on the PC server: pushes a heartbeat every `every_s` seconds while the server runs."""

    def __init__(self, bot, every_s: float = 300.0, log=print):
        self.bot, self.every_s, self.log = bot, every_s, log
        self.last: dict = {}
        self._stop = threading.Event()
        self._thread = None
        self._err_at = 0.0

    def payload(self) -> dict:
        st = getattr(self.bot, "state", None) or {}
        cfg = getattr(self.bot, "cfg", None) or {}
        return {"t": int(time.time()), "running": bool(getattr(self.bot, "running", False)), "adapter": cfg.get("adapter", "paper"),
                "position": bool(st.get("position")), "model_state": st.get("model_state"), "host": platform.node(),
                "model": (st.get("strategy") or {}).get("model") or cfg.get("model"),
                "push_pk": _push_pk(),          # phone notifications: the cloud seals the notification key to this (engine/push.py)
                "every_s": int(self.every_s)}

    def beat(self) -> dict:
        res = push(self.payload())
        self.last = {"at": int(time.time()), **res}
        if not res["ok"] and time.time() - self._err_at > 3600:
            self._err_at = time.time()
            self.log(f"[heartbeat] push failed: {res['error']}")
        return res

    def _run(self):
        while not self._stop.is_set():
            self.beat()
            self._stop.wait(self.every_s)

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
        print("heartbeat selftest OK: push, read, silent after 20 min, stopped bot never silent, no history growth")
        return True
    finally:
        shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    import sys
    sys.exit(0 if selftest() else 1)
