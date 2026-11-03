"""Auto-update of the PC bot (owner opt-in): fast-forward to origin/main once a day in the CME halt, test, roll back.

  python -m engine.autoupdate --enable       turn it on (once; stored in data/autoupdate.json, gitignored)
  python -m engine.autoupdate --disable      turn it off
  python -m engine.autoupdate --status       what it did last
  python -m engine.autoupdate --on-start     scripts/run_bot.ps1 runs this before it starts server.py
  python -m engine.autoupdate --check        one check now (same rules; the server's daily check does this in-process)
  python -m engine.autoupdate --pull         the update now, bot stopped (UPDATE.bat, START BOT, the Start page)

"Pull all the time" (owner 2026-10-21): besides the main daily check in the halt, the server checks for a new main once an
hour outside trading time (weekdays 16:00-01:20 ET, i.e. never within 30 min of the 01:50 blackout, and all weekend), with
the same rules plus two more: no setup armed (bot_flat_reason), and a restart must be safe: a bot on a real account without
the owner's auto-resume opt-in waits for the 17:02 halt check (an hourly update at night would leave it stopped until he
types the start command). Hourly checks never push "update skipped" alerts (only failures / rollbacks).

Rules (never broken):
  * only when the bot is FLAT: no model position, no routed position, no open NinjaTrader bracket, no LIT limit / 1m-CISD
    entry pending; never between 01:50 and 16:00 ET on a weekday (LIT trades 02:00-15:55). The daily check runs in the
    CME halt (17:02-17:50 ET) once per ET date; --on-start runs at any other allowed time.
  * only on branch main, only a FAST-FORWARD (git merge --ff-only): never a merge, rebase or reset of local work. A dirty
    tree (tracked files changed by hand) or a main that is not a fast-forward of HEAD is skipped with an alert.
  * bot-made tracked files (engine/generated_files.py: cache/dash/*, data/GEX_1d.csv, VIX/VXN, check reports) never
    count as dirty; the ones the update changes are put back to HEAD right before the fast-forward (and before a rollback).
  * (2026-10-26, fast_forward) ATLAS's account block in second_model.json moves to data/account_b.json first
    (engine/account_b.migrate_local); a file checked out from main by hand is no local work either (from_main: back to
    HEAD before the move, put back after a rollback); a shallow history is deepened before "not a fast-forward" is
    decided; a refused `git merge --ff-only` to a proven descendant is done with `git reset --keep`. UPDATE.bat and
    START BOT use the same code (--pull).
  * after the fast-forward: pip install -r requirements.txt when it changed, then the quick self-tests
    (engine.ninjatrader --selftest, engine.sizing, tests.test_no_yahoo). Any failure rolls back with
    `git reset --keep <old sha>` (the tree was clean, so nothing local can be lost; --keep refuses otherwise), remembers
    the bad sha (not retried until main moves again) and alerts the phone. Then, only with "selftest_hold": true in
    data/autoupdate.json (OFF by default until the PC has a green self-test baseline), the PC self-test
    (engine/pc_selftest.py, 2026-10-30: 24 curated suites + 2 checks in sealed temp folders): a regression (a check that
    passed on this PC before) rolls back the same way and pushes "Update held back: <first failing check>".
  * success: the server restarts (exit code RESTART_CODE; run_bot.ps1 starts it again at once). Paper / Sim bots resume
    by themselves; a real-account bot only with the owner's auto-resume opt-in (engine/autoresume.py), otherwise the
    phone gets "Updated to <sha>: bot is stopped on your eval, type the start command to resume".
Every step is logged to logs/update-YYYYMMDD.log; the last result is in the heartbeat health block (version + update).
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import threading
import time
from zoneinfo import ZoneInfo

from . import generated_files

ET = ZoneInfo("America/New_York")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_PATH = os.path.join(ROOT, "data", "autoupdate.json")          # gitignored
LOG_DIR = os.path.join(ROOT, "logs")
BRANCH = os.environ.get("LE_AUTOUPDATE_BRANCH", "main")
RESTART_CODE = 75                                                    # server exit code: "restart me now, I updated"
HALT_FROM, HALT_TO = 17 * 60 + 2, 17 * 60 + 50                      # daily check window (ET minutes)
BLACKOUT_FROM, BLACKOUT_TO = 1 * 60 + 50, 16 * 60                    # never on a weekday 01:50-16:00 ET
HOURLY_MARGIN = 30                                                   # hourly checks stop 30 min before the blackout (01:20 ET)
ASIA_FROM = 18 * 60                                                  # LIT all_hours: the CME trading day starts 18:00 ET
PENDING_STAGES = ("limit", "cisd1m", "trade")                        # engine/accounts._lit_stage
OPEN_LEG = ("entry_sent", "pending", "cancel_pending", "protected", "unprotected", "closing")   # ninjatrader.OPEN_STATUSES
TESTS = (["-m", "engine.ninjatrader", "--selftest", "--quiet"], ["-X", "utf8", "-m", "engine.sizing"],
         ["-X", "utf8", "-m", "tests.test_no_yahoo"])
# 2026-10-30: then the PC self-test (engine/pc_selftest.py, mode update: the curated suites + checks, below-normal priority,
# sealed temp folders). It exits 1 only on a REGRESSION (a check that passed on this PC before the update, or has no earlier
# result): the update is held back like a failed test (rollback + bad_sha) and the push says "Update held back: <check>".
# "{old}" = the commit before the update (its result is the baseline). Skipped when the new checkout has no pc_selftest.
SELFTEST = ["-X", "utf8", "-m", "engine.pc_selftest", "--mode", "update", "--base", "{old}", "--quiet"]
SELFTEST_TIMEOUT_S = 600
HOLD_MARK = "SELFTEST-HOLD:"


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
    from .fsutil import replace as _fs_replace   # retried: Windows / OneDrive lock the target a moment
    _fs_replace(tmp, path)


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


def hour_key(now) -> str:
    return _et(now).strftime("%Y-%m-%dT%H")


def window_reason(now, mode: str, last_check_day: str | None = None, last_hour: str | None = None, all_hours: bool = False):
    """None when an update may run now, else why not. mode 'daily' (the server's halt check) | 'hourly' (the extra checks
    outside trading time) | 'start' | 'manual'.
    all_hours (LIT all_hours on: the Asia slot trades from 18:00 ET): hourly checks only 16:00-17:30 ET on a weekday, Friday
    after 16:00, Saturday and Sunday before 17:30 (never in the evening / overnight session). Off: unchanged."""
    if in_blackout(now):
        return "trading hours (no update 01:50-16:00 ET on a weekday)"
    if mode == "hourly":
        e = _et(now)
        m = e.hour * 60 + e.minute
        if all_hours:
            wd = e.weekday()
            free = wd == 5 or (wd == 4 and m >= BLACKOUT_TO) or (wd == 6 and m < ASIA_FROM - HOURLY_MARGIN) \
                or (wd < 5 and BLACKOUT_TO <= m < ASIA_FROM - HOURLY_MARGIN)
            if not free:
                return ("LIT all_hours: the Asia slot trades from 18:00 ET (hourly checks only 16:00-17:30 ET on weekdays "
                        "and at the weekend)")
        if e.weekday() < 5 and BLACKOUT_FROM - HOURLY_MARGIN <= m < BLACKOUT_TO:
            return "too close to the 01:50 ET trading start (hourly checks stop at 01:20 ET)"
        if in_halt(now):
            return "the daily check runs in the halt"
        if last_hour == hour_key(now):
            return "already checked this hour"
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


def bot_all_hours(bot) -> bool:
    """LIT all_hours on for the running bot (its poll's params), else in live_model.json "lit". Never raises."""
    try:
        f = getattr(bot, "_lit_all_hours", None)
        if callable(f) and (getattr(bot, "state", None) or {}).get("strategy"):
            return bool(f())
        from .lab_adapter import live_model
        lm = live_model()
        return lm.get("model") == "lit" and bool((lm.get("lit") or {}).get("all_hours"))
    except Exception:
        return False


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
        """(returncode, output). Through heartbeat.run_cmd (2026-11-03): on Windows subprocess.run(timeout=) waits without
        a limit for its pipes while git-remote-https / the credential manager hang (the heartbeat's 2026 fix); run_cmd
        uses temp files and kills the whole process tree at the timeout. Git never prompts (GIT_TERMINAL_PROMPT=0)."""
        try:
            from .heartbeat import run_cmd
            r = run_cmd(args, cwd=self.cwd, timeout=timeout,
                        env={**os.environ, "PYTHONIOENCODING": "utf-8", "LE_HEARTBEAT": "0", "LE_NO_AUTOSTART": "1",
                             "GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "never"})
            if r.timed_out:
                return 124, f"timed out after {timeout} s"
            if r.returncode == -1:                       # could not start
                return 127, r.err
            out, err = (r.stdout or b"").decode("utf-8", "replace"), (r.stderr or b"").decode("utf-8", "replace")
            return r.returncode, out + err
        except Exception as e:
            return 127, f"{e.__class__.__name__}: {e}"

    def git(self, *args, timeout=120):
        return self.run([generated_files.git_exe(), *args], timeout=timeout)

    def py(self, args, timeout=600):
        return self.run([self.python, *args], timeout=timeout)


def git_head(sh: Shell) -> str | None:
    c, out = sh.git("rev-parse", "HEAD")
    return out.strip() if c == 0 and out.strip() else None


# ---------------------------------------------------------------------- the fast-forward every update path uses
_SHA = __import__("re").compile(r"\b[0-9a-f]{40}\b")
TRACKED_LOCAL = "second_model.json"          # engine/account_b.migrate_local moves its local block to data/account_b.json


def _sha(out: str) -> str | None:
    m = _SHA.search(out or "")
    return m.group(0) if m else None


def _dirty(sh) -> tuple:
    c, out = sh.git("status", "--porcelain", "--untracked-files=no")
    return c, out, generated_files.porcelain_paths(out) if c == 0 else []


def is_ancestor(sh, old, new, log=None, branch: str = BRANCH) -> bool:
    """old is in new's history. A SHALLOW checkout may not show it (the owner's Surface, 2026-10-25 22:33: "refusing to
    merge unrelated histories" for 94e232d..e20e268 although 94e232d is e20e268's grandparent): deepen, then unshallow."""
    log = log or (lambda t: None)
    if sh.git("merge-base", "--is-ancestor", old, new)[0] == 0:
        return True
    c, out = sh.git("rev-parse", "--is-shallow-repository")
    if c != 0 or out.strip() != "true":
        return False
    for args in (("fetch", "-q", "--deepen=300", "origin", branch), ("fetch", "-q", "--unshallow", "origin", branch)):
        c, out = sh.git(*args, timeout=900)
        log(f"shallow history: git {' '.join(args[1:3])} -> {c}" + (f" ({out.strip()[-120:]})" if c else ""))
        if sh.git("merge-base", "--is-ancestor", old, new)[0] == 0:
            return True
    return False


def from_main(sh, path: str, old: str, new: str) -> str | None:
    """The commit whose version of `path` the local copy is (worktree and index), when that version came in with
    old..new: a file checked out from main by hand (`git checkout origin/main -- engine/live.py`, the clock fix on the
    owner's PC 2026-10-25), never the owner's own edit. None = an unknown local change (it blocks the update)."""
    c, raw = sh.git("log", "--no-abbrev", "--raw", "-m", "--format=commit %H", f"{old}..{new}", "--", path)
    if c != 0:
        return None
    blobs, cur = {}, None
    for ln in raw.splitlines():
        if ln.startswith("commit "):
            cur = ln.split()[1]
        elif ln.startswith(":") and cur:
            parts = ln.split("\t", 1)[0].split()
            if len(parts) >= 4 and set(parts[3]) != {"0"}:
                blobs.setdefault(parts[3], cur)
    if not blobs:
        return None
    c, head = sh.git("rev-parse", "--verify", "-q", f"HEAD:{path}")
    head = _sha(head) if c == 0 else None
    c, work = sh.git("hash-object", "--", path)
    c2, idx = sh.git("ls-files", "-s", "--", path)
    work, idx = (_sha(work) if c == 0 else None), (_sha(idx) if c2 == 0 else None)
    if not work or not idx or not ({work, idx} - {head}):
        return None
    if work not in blobs and work != head or idx not in blobs and idx != head:
        return None
    return blobs.get(work) or blobs.get(idx)


def fast_forward(sh, branch: str = BRANCH, log=None, skip_sha: str | None = None) -> dict:
    """Move the checkout to origin/<branch> (fast-forward only), the one way every update runs: the auto-update, the
    phone's "update", UPDATE.bat and START BOT (`python -m engine.autoupdate --pull`), the dashboard's Start page.
    Before the dirty check: ATLAS's account block an older version wrote into second_model.json goes to
    data/account_b.json (engine/account_b.migrate_local); bot-made files the update replaces go back to HEAD; a file
    checked out from main by hand (from_main) goes back to HEAD too (the fast-forward then brings main's version). Any
    other local change still blocks. A shallow history is deepened (is_ancestor). When `git merge --ff-only` still
    refuses, `git reset --keep` to the proven descendant does the same move (it refuses on a conflicting local change).
    Returns {"status": up_to_date | updated | skipped | failed, "reason", "old", "new", "changed", "restore"
    ({path: commit} of the hand-checked-out files, put back on a rollback), "alert"}."""
    log = log or sh.log
    res = {"status": "skipped", "reason": "", "old": None, "new": None, "changed": [], "restore": {}, "alert": False}

    def done(status, reason, alert=False, **kw):
        res.update(status=status, reason=reason, alert=alert, **kw)
        return res

    c, cur = sh.git("rev-parse", "--abbrev-ref", "HEAD")
    if c != 0 or cur.strip() != branch:
        return done("skipped", f"not on branch {branch} (on {cur.strip()[:60] or '?'})", alert=True)
    old = git_head(sh)
    res["old"] = old
    c, st, paths = _dirty(sh)
    if c != 0:
        return done("failed", f"git status failed: {st.strip()[:200]}", alert=True)
    if TRACKED_LOCAL in paths:
        from . import account_b
        m = account_b.migrate_local(root=sh.cwd, git=sh.git)
        log(f"second_model.json: {m.get('say')}")
        c, st, paths = _dirty(sh)
    gen_dirty, other = generated_files.split_dirty(st)
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
    if skip_sha and skip_sha == new:
        return done("skipped", f"{new[:7]} failed its tests before; waiting for a newer main")
    if not is_ancestor(sh, old, new, log, branch):
        return done("skipped", f"origin/{branch} {new[:7]} is not a fast-forward of {old[:7]} (local commits?): not touched", alert=True)
    known = {}
    for p in other:
        if p == TRACKED_LOCAL:
            continue                                  # its block could not be moved: it blocks (below)
        k = from_main(sh, p, old, new)
        if k:
            known[p] = k
    blocking = [p for p in other if p not in known]
    if blocking:
        return done("skipped", "local changes in tracked files (not touched): " + ", ".join(blocking[:4]), alert=True)
    c, changed = sh.git("diff", "--name-only", old, new)
    changed = changed.split() if c == 0 else []
    res["changed"] = changed
    hit = [p for p in gen_dirty if p in changed]        # bot-made files the update replaces: back to HEAD, else the ff fails
    if hit:
        c, out = generated_files.discard(sh.git, hit)
        log(f"reset {len(hit)} bot-made file(s) the update replaces: {', '.join(hit[:6])}"
            + (f" (git: {out.strip()[-120:]})" if c else ""))
    if known:
        c, out = sh.git("checkout", "HEAD", "--", *known)
        log(f"{len(known)} file(s) checked out from main by hand go back to HEAD first (the update brings main's version): "
            f"{', '.join(list(known)[:6])}" + (f" (git: {out.strip()[-120:]})" if c else ""))
        res["restore"] = dict(known)

    c, out = sh.git("merge", "--ff-only", "-q", new)
    if c != 0:
        log(f"git merge --ff-only refused ({out.strip()[-160:]}): git reset --keep {new[:7]}")
        c, out2 = sh.git("reset", "--keep", new)
        if c != 0 or git_head(sh) != new:
            sh.git("reset", "--keep", old)
            put_back(sh, known)
            return done("failed", f"fast-forward refused: {(out.strip() or out2.strip())[-200:]}", alert=True)
    log(f"fast-forwarded {old[:7]} -> {new[:7]} ({len(changed)} files)")
    return done("updated", f"{old[:7]} -> {new[:7]}")


def put_back(sh, restore: dict):
    """After a rollback (or a refused move): the files that were checked out from main by hand get that version again,
    so the PC is exactly as before the update."""
    for p, k in (restore or {}).items():
        sh.git("checkout", k, "--", p)


# ---------------------------------------------------------------------- the update itself
def selftest_step(sh, old: str | None, args=None, timeout: float = SELFTEST_TIMEOUT_S) -> dict | None:
    """The PC self-test on the new checkout (engine/pc_selftest.py, mode update). None when the checkout has no
    engine/pc_selftest.py (an older main: nothing to run). {"code", "held": the first failing check's label or None,
    "out"}; code != 0 = hold the update back."""
    if not os.path.exists(os.path.join(sh.cwd, "engine", "pc_selftest.py")):
        return None
    argv = [str(a).replace("{old}", old or "") for a in (args or SELFTEST)]
    c, out = sh.py(argv, timeout=timeout)
    held = None
    for ln in (out or "").splitlines():
        if ln.startswith(HOLD_MARK):
            held = ln[len(HOLD_MARK):].strip().split(":", 1)[0].strip() or None
    if c != 0 and not held:
        held = "the PC self-test" + (" (timed out)" if c == 124 else "")
    return {"code": c, "held": held if c != 0 else None, "out": out}


def run_update(sh: Shell, mode: str = "manual", now=None, flat: str | None = None, state: dict | None = None,
               tests=TESTS, branch: str = BRANCH, env=None, all_hours: bool = False, selftest: bool | None = None) -> dict:
    """One check. Returns {"status", "reason", "old", "new", "restart", "alert"}; status: off | skipped | up_to_date |
    updated | rolled_back | failed. `flat` = flat_reason (None = flat). Pure apart from `sh`. selftest: run the PC
    self-test after `tests` (selftest_step; a regression holds the update back: rolled back, "held" = the check).
    None (default) = only when data/autoupdate.json has "selftest_hold": true (2026-10-30: OFF until the PC has a green
    baseline from the Sunday / on-demand self-test; until then the self-test only reports, it never holds an update)."""
    now = time.time() if now is None else now
    state = load_state() if state is None else state
    res = {"t": int(now), "mode": mode, "status": "skipped", "reason": "", "old": None, "new": None, "restart": False, "alert": False}

    def done(status, reason, alert=False, **kw):
        res.update(status=status, reason=reason, alert=alert, **kw)
        sh.log(f"{status}: {reason}")
        return res

    if not is_enabled(state, env):
        return done("off", "auto-update is off (python -m engine.autoupdate --enable)")
    w = window_reason(now, mode, state.get("last_check_day"), state.get("last_hourly"), all_hours=all_hours)
    if w:
        return done("skipped", w)
    if flat:
        return done("skipped", f"not flat: {flat}")
    res["checked"] = True
    ff = fast_forward(sh, branch, skip_sha=state.get("bad_sha"))
    old, new, changed = ff.get("old"), ff.get("new"), ff.get("changed") or []
    res.update(old=old, new=new)
    if ff["status"] != "updated":
        return done(ff["status"], ff["reason"], alert=ff.get("alert", False))

    def rollback(why, held=None):
        # the self-tests may rewrite bot-made files; --keep refuses on a locally changed file the ff changed
        c2, st2 = sh.git("status", "--porcelain", "--untracked-files=no")
        if c2 == 0:
            generated_files.discard(sh.git, [p for p in generated_files.split_dirty(st2)[0] if p in changed])
        rc, rout = sh.git("reset", "--keep", old)
        back = git_head(sh) == old
        if back:
            put_back(sh, ff.get("restore"))             # files checked out from main by hand: as they were before
        if "requirements.txt" in changed:
            sh.py(["-m", "pip", "install", "-q", "-r", "requirements.txt"], timeout=900)
        return done("rolled_back" if back else "failed",
                    f"{why}; " + (f"rolled back to {old[:7]}" if back else f"ROLLBACK FAILED ({rout.strip()[-120:]}): fix by hand"),
                    alert=True, bad_sha=new, **({"held": held} if held else {}))

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
    if selftest is None:
        selftest = bool((state or {}).get("selftest_hold") is True)
    st = selftest_step(sh, old) if selftest else None
    if st is not None:
        sh.log(f"PC self-test -> {st['code']}" + (f" (held back: {st['held']})" if st.get("held") else ""))
        if st["code"] != 0:
            hold_line = next((ln for ln in (st.get("out") or "").splitlines() if ln.startswith(HOLD_MARK)), "")
            return rollback(f"PC self-test failed: {(hold_line[len(HOLD_MARK):].strip() or (st.get('out') or '').strip())[-200:]}",
                            held=st["held"])
    return done("updated", f"{old[:7]} -> {new[:7]}, self-tests passed", restart=True)


def pull(sh: Shell | None = None, branch: str = BRANCH, pip: bool = True) -> dict:
    """A manual update with the bot stopped (UPDATE.bat, START BOT, the dashboard's Start page): fast_forward, then
    pip install when requirements.txt changed. No time window, no self-tests here (UPDATE.bat runs them after the start).
    Returns fast_forward's result + "say" (one plain line)."""
    sh = sh or Shell(log=file_log)
    r = fast_forward(sh, branch)
    if r["status"] == "updated" and pip and "requirements.txt" in (r.get("changed") or []):
        c, out = sh.py(["-m", "pip", "install", "-q", "-r", "requirements.txt", "--disable-pip-version-check"], timeout=900)
        r["pip"] = c
        sh.log(f"pip install -> {c}")
    r["say"] = {"updated": f"Updated to the newest version ({r['reason']})", "up_to_date": "Already the newest version",
                }.get(r["status"]) or f"Not updated: {r['reason']}"
    return r


def record(res: dict, state: dict | None = None, path: str = STATE_PATH) -> dict:
    """Store the result in data/autoupdate.json (last result, history, bad sha, restart marker)."""
    s = load_state(path) if state is None else state
    s["last"] = {k: res.get(k) for k in ("t", "mode", "status", "reason", "old", "new")}
    if res.get("held"):
        s["last"]["held"] = res["held"]
    if res.get("mode") == "daily" and res.get("checked"):
        s["last_check_day"] = _et(res["t"]).date().isoformat()
    if res.get("mode") == "hourly" and res.get("checked"):
        s["last_hourly"] = hour_key(res["t"])
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
    body = str(res.get("reason") or "")[:300]
    if res.get("held") and st == "rolled_back":      # the PC self-test found a regression (engine/pc_selftest.py)
        title = f"Update held back: {res['held']}"[:120]
        body = (f"Still on {str(res.get('old') or '')[:7]}; {str(res.get('new') or '')[:7]} is not used until a newer main "
                f"comes. {body}")[:300]
    notify(title, body, key=f"auto:update:{st}:{res['t']}", sync=sync)


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
            "bad_sha": (s.get("bad_sha") or "")[:7] or None, "last_hourly": s.get("last_hourly"),
            **({"held": str(last["held"])[:80]} if last.get("held") else {})}


# ---------------------------------------------------------------------- in-server daily check
def restart_safe_reason(bot, optin=None, tradovate_env=None) -> str | None:
    """None when restarting the server now brings the bot back by itself: not running, paper / Sim, or a real account with
    the owner's auto-resume opt-in (engine/autoresume.py). Else why the hourly check waits for the halt check."""
    try:
        if not getattr(bot, "running", False):
            return None
        from .watchdog import AUTO_MODES, mode_of
        tenv = tradovate_env
        if tenv is None:
            try:
                from .tradovate import env_status
                tenv = env_status().get("env", "demo")
            except Exception:
                tenv = "demo"
        if mode_of(getattr(bot, "cfg", None) or {}, tenv) in AUTO_MODES:
            return None
        from . import autoresume
        rec = autoresume.load() if optin is None else optin
        if autoresume.valid(rec):
            return None
        return "a real-account bot without auto-resume: waits for the 17:02 ET halt check"
    except Exception as e:
        return f"cannot tell if a restart is safe ({e.__class__.__name__})"


class DailyUpdater:
    """Daemon thread in server.py: once per ET date in 17:02-17:50 ET, when flat, run_update; plus once an hour outside
    trading time (weekdays 16:00-01:20 ET, all weekend) when flat, nothing armed and a restart is safe. On success exit the
    server with RESTART_CODE (scripts/run_bot.ps1 starts the new code at once)."""

    def __init__(self, bot, every_s: float = 60.0, exit_fn=None, clock=time.time, state_path: str = STATE_PATH):
        self.bot, self.every_s, self.clock, self.state_path = bot, every_s, clock, state_path
        self.exit_fn = exit_fn or (lambda code: os._exit(code))
        self._stop = threading.Event()
        self._thread = None
        self.busy = False

    def due_mode(self, now=None) -> str | None:
        """'daily' (the halt check), 'hourly' (an extra check outside trading time) or None."""
        now = self.clock() if now is None else now
        s = load_state(self.state_path)
        if not is_enabled(s):
            return None
        if window_reason(now, "daily", s.get("last_check_day")) is None:
            return "daily"
        if window_reason(now, "hourly", s.get("last_check_day"), s.get("last_hourly"), all_hours=bot_all_hours(self.bot)) is None:
            return "hourly"
        return None

    def due(self, now=None) -> bool:
        return self.due_mode(now) is not None

    def check_once(self, now=None, sh: Shell | None = None, tests=TESTS, optin=None) -> dict | None:
        now = self.clock() if now is None else now
        mode = self.due_mode(now)
        if mode is None or self.busy:
            return None
        flat = bot_flat_reason(self.bot)
        if flat:                                       # try again next minute while the window is open
            return {"status": "skipped", "mode": mode, "reason": f"not flat: {flat}"}
        if mode == "hourly":
            why = restart_safe_reason(self.bot, optin)
            if why:
                return {"status": "skipped", "mode": mode, "reason": why}
        self.busy = True
        try:
            file_log(f"{mode} check (server)")
            res = run_update(sh or Shell(log=file_log), mode, now, None, state=load_state(self.state_path), tests=tests,
                             all_hours=bot_all_hours(self.bot))
            if mode == "hourly" and res.get("status") == "skipped":
                res["alert"] = False                   # the halt check alerts about a dirty tree etc.; not every hour
            record(res, path=self.state_path)
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
    g.add_argument("--pull", action="store_true", help="UPDATE.bat / START BOT: the update now (bot stopped), the same "
                                                      "fast-forward as the auto-update; exit 1 when not updated")
    a = ap.parse_args(argv)
    if a.pull:
        r = pull()
        print(f"  [{'OK' if r['status'] in ('updated', 'up_to_date') else 'FIX'}]  {r['say']}")
        return 0 if r["status"] in ("updated", "up_to_date") else 1
    s = load_state()
    if a.enable or a.disable:
        s["enabled"] = bool(a.enable)
        s["changed_at"] = int(time.time())
        save_state(s)
        file_log(f"auto-update turned {'ON' if a.enable else 'OFF'} by the owner")
        print(f"Auto-update is {'ON' if a.enable else 'OFF'}." + (
            " Daily in 17:02-17:50 ET, hourly outside trading time (weekdays 16:00-01:20 ET, all weekend) and when"
            " run_bot.ps1 starts; only when flat; only fast-forwards of main." if a.enable else ""))
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
