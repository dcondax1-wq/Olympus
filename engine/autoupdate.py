"""Auto-update of the PC bot (owner opt-in): fast-forward to origin/main once a day in the CME halt, test, roll back.

  python -m engine.autoupdate --enable       turn it on (once; stored in data/autoupdate.json, gitignored)
  python -m engine.autoupdate --disable      turn it off
  python -m engine.autoupdate --status       what it did last
  python -m engine.autoupdate --on-start     scripts/run_bot.ps1 runs this before it starts server.py
  python -m engine.autoupdate --check        one check now (same rules; the server's daily check does this in-process)

Rules (never broken):
  * only when the bot is FLAT: no model position, no routed position, no open NinjaTrader bracket, no LIT limit / 1m-CISD
    entry pending; never between 01:50 and 16:00 ET on a weekday (LIT trades 02:00-15:55). The daily check runs in the
    CME halt (17:02-17:50 ET) once per ET date; --on-start runs at any other allowed time.
  * only on branch main, only a FAST-FORWARD (git merge --ff-only): never a merge, rebase or reset of local work. A dirty
    tree (tracked files changed) or a main that is not a fast-forward of HEAD is skipped with an alert.
  * after the fast-forward: pip install -r requirements.txt when it changed, then the quick self-tests
    (engine.ninjatrader --selftest, engine.sizing, tests.test_no_yahoo). Any failure rolls back with
    `git reset --keep <old sha>` (the tree was clean, so nothing local can be lost; --keep refuses otherwise), remembers
    the bad sha (not retried until main moves again) and alerts the phone.
  * success: the server restarts (exit code RESTART_CODE; run_bot.ps1 starts it again at once). Paper / Sim bots resume
    by themselves; a real-account bot only with the owner's auto-resume opt-in (engine/autoresume.py), otherwise the
    phone gets "Updated to <sha>: bot is stopped on your eval, type the start command to resume".
Every step is logged to logs/update-YYYYMMDD.log; the last result is in the heartbeat health block (version + update).
"""
from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import sys
import threading
import time
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_PATH = os.path.join(ROOT, "data", "autoupdate.json")          # gitignored
LOG_DIR = os.path.join(ROOT, "logs")
BRANCH = os.environ.get("LE_AUTOUPDATE_BRANCH", "main")
RESTART_CODE = 75                                                    # server exit code: "restart me now, I updated"
HALT_FROM, HALT_TO = 17 * 60 + 2, 17 * 60 + 50                      # daily check window (ET minutes)
BLACKOUT_FROM, BLACKOUT_TO = 1 * 60 + 50, 16 * 60                    # never on a weekday 01:50-16:00 ET
PENDING_STAGES = ("limit", "cisd1m", "trade")                        # engine/accounts._lit_stage
OPEN_LEG = ("entry_sent", "pending", "cancel_pending", "protected", "unprotected", "closing")   # ninjatrader.OPEN_STATUSES
TESTS = (["-m", "engine.ninjatrader", "--selftest", "--quiet"], ["-X", "utf8", "-m", "engine.sizing"],
         ["-X", "utf8", "-m", "tests.test_no_yahoo"])


# ---------------------------------------------------------------------- state file
def load_state(path: str = STATE_PATH) -> dict:
    try:
        with open(path, encoding="utf-8") as f:
            s = json.load(f)
        return s if isinstance(s, dict) else {}
    except Exception:
        return {}


def save_state(s: dict, path: str = STATE_PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(s, f, indent=1)
    os.replace(tmp, path)


def is_enabled(state: dict | None = None, env=None) -> bool:
    env = os.environ if env is None else env
    if env.get("LE_AUTOUPDATE") == "0":
        return False
    return bool((state if state is not None else load_state()).get("enabled"))


# ---------------------------------------------------------------------- pure decisions
def _et(now):
    return dt.datetime.fromtimestamp(float(now), ET)


def in_blackout(now) -> bool:
    e = _et(now)
    m = e.hour * 60 + e.minute
    return e.weekday() < 5 and BLACKOUT_FROM <= m < BLACKOUT_TO


def in_halt(now) -> bool:
    e = _et(now)
    return HALT_FROM <= e.hour * 60 + e.minute <= HALT_TO


def window_reason(now, mode: str, last_check_day: str | None = None):
    """None when an update may run now, else why not. mode 'daily' (the server's halt check) | 'start' | 'manual'."""
    if in_blackout(now):
        return "trading hours (no update 01:50-16:00 ET on a weekday)"
    if mode == "daily":
        if not in_halt(now):
            return "outside the daily window 17:02-17:50 ET"
        if last_check_day == _et(now).date().isoformat():
            return "already checked today"
    return None


def flat_reason(state: dict | None, open_routed=None, legs=None, running=False):
    """None when the bot is flat with nothing pending, else why not."""
    st = state or {}
    if st.get("position"):
        return "a position is open"
    if open_routed:
        return "a routed position is open"
    for lg in legs or []:
        if isinstance(lg, dict) and lg.get("status") in OPEN_LEG:
            return f"a NinjaTrader bracket is {lg.get('status')}"
    if st.get("enter_now"):
        return "an entry is being sent"
    if st.get("setups") and running:
        return "a LIT entry is pending (limit / 1m CISD)"
    return None


def bot_flat_reason(bot) -> str | None:
    """flat_reason for the running server's LiveBot."""
    try:
        legs = list(getattr(getattr(bot, "adapter", None), "legs", None) or [])
        r = flat_reason(getattr(bot, "state", None), getattr(bot, "_open_routed", None), legs, bool(getattr(bot, "running", False)))
        if r:
            return r
        from .accounts import _lit_stage
        if getattr(bot, "running", False) and _lit_stage(getattr(bot, "state", None) or {}).get("stage") in PENDING_STAGES:
            return "a LIT setup is armed"
        return None
    except Exception as e:
        return f"cannot tell if flat ({e.__class__.__name__})"


def files_flat_reason(root: str = ROOT, now=None) -> str | None:
    """flat_reason from the files when no server runs (the --on-start check): today's live_state.json + NinjaTrader legs."""
    now = time.time() if now is None else now
    try:
        with open(os.path.join(root, "data", "live_state.json"), encoding="utf-8") as f:
            ls = json.load(f)
    except FileNotFoundError:
        ls = {}
    except Exception:
        return "data/live_state.json unreadable"
    try:
        with open(os.path.join(root, "data", "ninjatrader_state.json"), encoding="utf-8") as f:
            nt = json.load(f)
    except FileNotFoundError:
        nt = {}
    except Exception:
        return "data/ninjatrader_state.json unreadable"
    recent = now - float(ls.get("saved_at") or 0) < 24 * 3600        # an older file is a past day: the bot was flat at 15:55
    return flat_reason({}, ls.get("open_routed") if recent else None, nt.get("legs") if isinstance(nt, dict) else None)


# ---------------------------------------------------------------------- git / subprocess layer (swappable in tests)
class Shell:
    def __init__(self, cwd: str = ROOT, python: str = sys.executable, log=None):
        self.cwd, self.python, self.log = cwd, python, log or (lambda t: None)

    def run(self, args, timeout=120):
        try:
            r = subprocess.run(args, cwd=self.cwd, capture_output=True, text=True, timeout=timeout,
                               env={**os.environ, "PYTHONIOENCODING": "utf-8", "LE_HEARTBEAT": "0", "LE_NO_AUTOSTART": "1"})
            return r.returncode, (r.stdout or "") + (r.stderr or "")
        except subprocess.TimeoutExpired:
            return 124, f"timed out after {timeout} s"
        except Exception as e:
            return 127, f"{e.__class__.__name__}: {e}"

    def git(self, *args, timeout=120):
        return self.run(["git", *args], timeout=timeout)

    def py(self, args, timeout=600):
        return self.run([self.python, *args], timeout=timeout)


def git_head(sh: Shell) -> str | None:
    c, out = sh.git("rev-parse", "HEAD")
    return out.strip() if c == 0 and out.strip() else None


# ---------------------------------------------------------------------- the update itself
def run_update(sh: Shell, mode: str = "manual", now=None, flat: str | None = None, state: dict | None = None,
               tests=TESTS, branch: str = BRANCH, env=None) -> dict:
    """One check. Returns {"status", "reason", "old", "new", "restart", "alert"}; status: off | skipped | up_to_date |
    updated | rolled_back | failed. `flat` = flat_reason (None = flat). Pure apart from `sh`."""
    now = time.time() if now is None else now
    state = load_state() if state is None else state
    res = {"t": int(now), "mode": mode, "status": "skipped", "reason": "", "old": None, "new": None, "restart": False, "alert": False}

    def done(status, reason, alert=False, **kw):
        res.update(status=status, reason=reason, alert=alert, **kw)
        sh.log(f"{status}: {reason}")
        return res

    if not is_enabled(state, env):
        return done("off", "auto-update is off (python -m engine.autoupdate --enable)")
    w = window_reason(now, mode, state.get("last_check_day"))
    if w:
        return done("skipped", w)
    if flat:
        return done("skipped", f"not flat: {flat}")
    res["checked"] = True
    c, cur = sh.git("rev-parse", "--abbrev-ref", "HEAD")
    if c != 0 or cur.strip() != branch:
        return done("skipped", f"not on branch {branch} (on {cur.strip()[:60] or '?'})", alert=True)
    old = git_head(sh)
    res["old"] = old
    c, dirty = sh.git("status", "--porcelain", "--untracked-files=no")
    if c != 0:
        return done("failed", f"git status failed: {dirty.strip()[:200]}", alert=True)
    if dirty.strip():
        return done("skipped", "local changes in tracked files (not touched): " + ", ".join(
            ln[3:] for ln in dirty.strip().splitlines()[:4]), alert=True)
    c, out = sh.git("fetch", "-q", "origin", branch, timeout=180)
    if c != 0:
        return done("skipped", f"git fetch failed: {out.strip()[-200:]}")
    c, new = sh.git("rev-parse", f"origin/{branch}")
    new = new.strip() if c == 0 else None
    res["new"] = new
    if not new:
        return done("failed", f"origin/{branch} unknown", alert=True)
    if new == old:
        return done("up_to_date", f"at {old[:7]}")
    if state.get("bad_sha") == new:
        return done("skipped", f"{new[:7]} failed its tests before; waiting for a newer main")
    c, _ = sh.git("merge-base", "--is-ancestor", old, new)
    if c != 0:
        return done("skipped", f"origin/{branch} {new[:7]} is not a fast-forward of {old[:7]} (local commits?): not touched", alert=True)
    c, changed = sh.git("diff", "--name-only", old, new)
    changed = changed.split() if c == 0 else []
    c, out = sh.git("merge", "--ff-only", "-q", new)
    if c != 0:
        sh.git("reset", "--keep", old)                  # a refused ff leaves HEAD alone; this is a no-op then
        return done("failed", f"fast-forward refused: {out.strip()[-200:]}", alert=True)
    sh.log(f"fast-forwarded {old[:7]} -> {new[:7]} ({len(changed)} files)")

    def rollback(why):
        rc, rout = sh.git("reset", "--keep", old)
        back = git_head(sh) == old
        if "requirements.txt" in changed:
            sh.py(["-m", "pip", "install", "-q", "-r", "requirements.txt"], timeout=900)
        return done("rolled_back" if back else "failed",
                    f"{why}; " + (f"rolled back to {old[:7]}" if back else f"ROLLBACK FAILED ({rout.strip()[-120:]}): fix by hand"),
                    alert=True, bad_sha=new)

    if "requirements.txt" in changed:
        c, out = sh.py(["-m", "pip", "install", "-q", "-r", "requirements.txt"], timeout=900)
        sh.log(f"pip install -> {c}")
        if c != 0:
            return rollback(f"pip install failed: {out.strip()[-160:]}")
    for t in tests:
        c, out = sh.py(list(t), timeout=900)
        sh.log(f"test {' '.join(t)} -> {c}")
        if c != 0:
            return rollback(f"self-test {' '.join(t[-2:])} failed: {out.strip()[-160:]}")
    return done("updated", f"{old[:7]} -> {new[:7]}, self-tests passed", restart=True)


def record(res: dict, state: dict | None = None, path: str = STATE_PATH) -> dict:
    """Store the result in data/autoupdate.json (last result, history, bad sha, restart marker)."""
    s = load_state(path) if state is None else state
    s["last"] = {k: res.get(k) for k in ("t", "mode", "status", "reason", "old", "new")}
    if res.get("mode") == "daily" and res.get("checked"):
        s["last_check_day"] = _et(res["t"]).date().isoformat()
    if res.get("status") not in ("skipped", "off") or res.get("alert"):
        s["history"] = (list(s.get("history") or []) + [s["last"]])[-20:]
    if res.get("bad_sha"):
        s["bad_sha"] = res["bad_sha"]
    if res.get("status") == "updated":
        s["updated_at"] = res["t"]
        s["restart_pending"] = {"sha": res["new"], "from": res["old"], "t": res["t"]}
        s.pop("bad_sha", None)
    save_state(s, path)
    return s


def take_restart_marker(path: str = STATE_PATH, max_age_s: int = 3600) -> dict | None:
    """The 'I just updated' marker for the restarted server (read once, then cleared)."""
    s = load_state(path)
    m = s.pop("restart_pending", None)
    if m is None:
        return None
    try:
        save_state(s, path)
    except Exception:
        pass
    return m if time.time() - float(m.get("t") or 0) <= max_age_s else None


# ---------------------------------------------------------------------- logging, alerts, status
def file_log(text: str):
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {text}"
    print("[autoupdate] " + line, flush=True)
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        with open(os.path.join(LOG_DIR, f"update-{time.strftime('%Y%m%d')}.log"), "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def notify(title: str, body: str, key: str, sync: bool = False):
    """Phone push (kind 'pc', always pushed) + the bot's chat alert. sync=True when no server keeps the process alive."""
    try:
        from . import push
        p = push.text_payload("PC", "pc", title, body, key=key, url="#/accounts")
        if sync:
            if not push.pc_notifier().seen(p):
                push._pc_send(p, True)
        else:
            push.pc_notify(p)
    except Exception:
        pass
    try:
        from . import alerts
        alerts.send(f"{title}: {body}", "system", force=True)
    except Exception:
        pass


def alert_for(res: dict, sync=False):
    if not res.get("alert"):
        return
    st = res.get("status")
    title = {"rolled_back": "Bot update failed, rolled back", "failed": "Bot update FAILED"}.get(st, "Bot update skipped")
    notify(title, str(res.get("reason") or "")[:300], key=f"auto:update:{st}:{(res.get('new') or '')[:10]}:{res['t'] // 3600}", sync=sync)


_VER = {"t": 0, "sha": None, "branch": None}


def version(cwd: str = ROOT) -> dict:
    """{"sha": short head, "branch"} (cached 10 min). Never raises."""
    if time.time() - _VER["t"] > 600 or not _VER["sha"]:
        try:
            sh = Shell(cwd)
            h = git_head(sh)
            c, b = sh.git("rev-parse", "--abbrev-ref", "HEAD", timeout=20)
            _VER.update(t=time.time(), sha=h[:7] if h else None, branch=b.strip() if c == 0 else None)
        except Exception:
            _VER.update(t=time.time())
    return {"sha": _VER["sha"], "branch": _VER["branch"]}


def status(path: str = STATE_PATH) -> dict:
    """The health block's auto_update entry (secret-free)."""
    s = load_state(path)
    last = s.get("last") or {}
    return {"on": is_enabled(s), **version(), "updated_at": s.get("updated_at"),
            "last_check_t": last.get("t"), "result": last.get("status"), "reason": str(last.get("reason") or "")[:160],
            "bad_sha": (s.get("bad_sha") or "")[:7] or None}


# ---------------------------------------------------------------------- in-server daily check
class DailyUpdater:
    """Daemon thread in server.py: once per ET date in 17:02-17:50 ET, when flat, run_update; on success exit the server
    with RESTART_CODE (scripts/run_bot.ps1 starts the new code at once)."""

    def __init__(self, bot, every_s: float = 60.0, exit_fn=None, clock=time.time):
        self.bot, self.every_s, self.clock = bot, every_s, clock
        self.exit_fn = exit_fn or (lambda code: os._exit(code))
        self._stop = threading.Event()
        self._thread = None
        self.busy = False

    def due(self, now=None) -> bool:
        now = self.clock() if now is None else now
        s = load_state()
        return is_enabled(s) and window_reason(now, "daily", s.get("last_check_day")) is None

    def check_once(self, now=None, sh: Shell | None = None, tests=TESTS) -> dict | None:
        now = self.clock() if now is None else now
        if not self.due(now) or self.busy:
            return None
        flat = bot_flat_reason(self.bot)
        if flat:                                       # try again next minute while the window is open
            return {"status": "skipped", "reason": f"not flat: {flat}"}
        self.busy = True
        try:
            file_log("daily check (server)")
            res = run_update(sh or Shell(log=file_log), "daily", now, None, tests=tests)
            record(res)
            alert_for(res)
            if res.get("restart"):
                file_log(f"restarting the server on {res['new'][:7]}")
                try:
                    self.bot._save_state()
                except Exception:
                    pass
                time.sleep(2)                          # let the alert threads go out
                self.exit_fn(RESTART_CODE)
            return res
        finally:
            self.busy = False

    def _run(self):
        while not self._stop.is_set():
            try:
                self.check_once()
            except Exception as e:
                file_log(f"daily check error: {e.__class__.__name__}: {e}")
            self._stop.wait(self.every_s)

    def start(self):
        if self._thread is None or not self._thread.is_alive():
            self._thread = threading.Thread(target=self._run, name="autoupdate", daemon=True)
            self._thread.start()


# ---------------------------------------------------------------------- CLI
def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="python -m engine.autoupdate", description="PC bot auto-update (owner opt-in)")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--enable", action="store_true")
    g.add_argument("--disable", action="store_true")
    g.add_argument("--status", action="store_true")
    g.add_argument("--on-start", action="store_true", help="scripts/run_bot.ps1, before server.py starts")
    g.add_argument("--check", action="store_true", help="one check now (outside trading hours, when flat)")
    a = ap.parse_args(argv)
    s = load_state()
    if a.enable or a.disable:
        s["enabled"] = bool(a.enable)
        s["changed_at"] = int(time.time())
        save_state(s)
        file_log(f"auto-update turned {'ON' if a.enable else 'OFF'} by the owner")
        print(f"Auto-update is {'ON' if a.enable else 'OFF'}." + (
            " Daily in 17:02-17:50 ET and when run_bot.ps1 starts; only when flat; only fast-forwards of main." if a.enable else ""))
        return 0
    if a.on_start or a.check:
        res = run_update(Shell(log=file_log), "start" if a.on_start else "manual", flat=files_flat_reason())
        record(res)
        alert_for(res, sync=True)
        print(f"auto-update: {res['status']}: {res['reason']}")
        return 0
    st = status()
    print(json.dumps(st, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
