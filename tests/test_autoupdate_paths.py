"""Update gate (updategate 2026-11-20, TOP25 idea #4; engine/autoupdate.py): a bad update can never take the bot down for long.
  a. needs_restart(): site / docs / research / tests / handoff / vault / root *.md only = the bot keeps running; engine/, server.py,
     the models, scripts/, tools/*.py, web/, requirements.txt, a path nobody listed, an empty list = restart (fail-safe)
  b. a real temp repo: a site-only update is pulled + tested, restart=False, no restart marker, no crash guard; a bot update
     restarts and arms the crash guard; site + bot together restart
  c. the import check: a new server.py that cannot import is never started (rolled back, bad_sha, HEAD back); one that imports passes
  d. crash_check(): the restart + 2 short runs only counted; the 4th start within 10 min = back to the commit before, bad_sha, ONE
     push; a run past 10 min clears it; not on the updated commit = cleared, git never touched; count=False only looks
  e. DailyUpdater.start(): a rolled-back crash loop restarts the server (exit 75) on the old code; LE_CRASH_CHECK=supervisor only looks
    python -X utf8 -m tests.test_autoupdate_paths
"""
from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import autoupdate as au  # noqa: E402

RES = []
OK_T = [["-c", "import sys; sys.exit(0)"]]


def ok(cond, name, info=""):
    RES.append(bool(cond))
    print(("  PASS " if cond else "  FAIL ") + name + ("" if cond or not info else f"  -> {str(info)[:400]}"))


def git(cwd, *a):
    return subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()


def write(base, rel, text):
    p = os.path.join(base, rel)
    os.makedirs(os.path.dirname(p) or base, exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


SAT_NOON = dt.datetime(2026, 11, 21, 12, 0, tzinfo=au.ET).timestamp()     # a Saturday: no trading window


def part_a():
    print("a. which changes restart the bot")
    no = [["tools/web_public/nq/nqchart.js", "docs/AUTO_UPDATE.md", "research/writeups/x.md", "tests/test_x.py",
           "handoff/inbox/a.md", "vault/Days/d.md", "STATE.md", ".github/workflows/x.yml", "tools/web_public/olympus/kit.js",
           "tools/web_public/jarvis/push-ui.js"]]
    ok(au.needs_restart(no[0]) == (False, []), "site / docs / research / tests / handoff / vault / root *.md: the bot keeps running")
    for p in ("engine/lit.py", "server.py", "live_model.json", "live_model_lit.json", "second_model.json", "accounts/a.json",
              "scripts/run_bot.ps1", "tools/pc_report.py", "tools/status_sign.py", "web/index.html", "requirements.txt",
              "ninjatrader/LE_Feed.cs", "update_source.json", "engine/README.md", "START_BOT.bat", "something_new.py"):
        r, bot = au.needs_restart(no[0] + [p])
        if not (r and bot == [p]):
            ok(False, f"{p} restarts the bot", (r, bot))
            break
    else:
        ok(True, "engine/, server.py, the models, scripts/, tools/*.py, web/, requirements, *.bat, a new path: restart")
    ok(au.needs_restart([]) == (True, []), "nothing known (empty list): restart, never skipped by not knowing")
    ok(au.needs_restart(["./docs/a.md", "docs\\b.md"]) == (False, []) and au.needs_restart(["github/x.yml"])[0],
       "./ and Windows slashes are read right; a look-alike folder is not the site")


class Repo:
    """origin (bare, branch main) + the PC's clone on main; commits land on origin through a second clone."""

    def __init__(self, tmp):
        self.origin = os.path.join(tmp, "origin.git")
        self.pc = os.path.join(tmp, "pc")
        self.dev = os.path.join(tmp, "dev")
        git(tmp, "init", "-q", "--bare", "-b", "main", self.origin)
        git(tmp, "clone", "-q", self.origin, self.dev)
        for d in (self.dev,):
            git(d, "config", "user.email", "t@example.com")
            git(d, "config", "user.name", "t")
        write(self.dev, "engine/__init__.py", "")
        write(self.dev, "engine/bot.py", "X = 1\n")
        write(self.dev, "server.py", "class _A:\n    routes = [1, 2]\napp = _A()\n")
        write(self.dev, "tools/web_public/index.html", "<p>v1</p>\n")
        git(self.dev, "add", "-A")
        git(self.dev, "commit", "-qm", "v1")
        git(self.dev, "push", "-q", "origin", "HEAD:main")
        git(tmp, "clone", "-q", "-b", "main", self.origin, self.pc)
        self.sh = au.Shell(cwd=self.pc)

    def push(self, files: dict, msg: str):
        for rel, text in files.items():
            write(self.dev, rel, text)
        git(self.dev, "add", "-A")
        git(self.dev, "commit", "-qm", msg)
        git(self.dev, "push", "-q", "origin", "HEAD:main")
        return git(self.dev, "rev-parse", "HEAD")

    def head(self):
        return git(self.pc, "rev-parse", "HEAD")


def update(r, state_path):
    st = {**au.load_state(state_path), "enabled": True}       # as DailyUpdater does: the saved state (bad_sha ...) + on
    res = au.run_update(r.sh, "manual", now=SAT_NOON, state=st, tests=OK_T, branch="main", env={})
    au.record(res, path=state_path)
    return res, au.load_state(state_path)


def parts_bcd(tmp):
    r = Repo(tmp)
    sp = os.path.join(tmp, "autoupdate.json")
    print("b. a real repo")
    old = r.head()
    new = r.push({"tools/web_public/index.html": "<p>v2</p>\n", "docs/NOTE.md": "x\n"}, "site only")
    res, s = update(r, sp)
    ok(res["status"] == "updated" and res["restart"] is False and res.get("site_only") and r.head() == new,
       "a site-only update is pulled and tested, and the bot keeps running (restart False)", res)
    ok("restart_pending" not in s and "crash_guard" not in s, "no restart marker, no crash guard", s)
    old = r.head()
    new = r.push({"engine/bot.py": "X = 2\n"}, "bot")
    res, s = update(r, sp)
    ok(res["status"] == "updated" and res["restart"] is True, "a bot-code update restarts", res)
    ok(s.get("restart_pending", {}).get("sha") == new and s.get("crash_guard", {}).get("old") == old,
       "the restart marker + the crash guard (old = the commit before) are set", s)
    new = r.push({"engine/bot.py": "X = 3\n", "tools/web_public/index.html": "<p>v3</p>\n"}, "both")
    res, _ = update(r, sp)
    ok(res["restart"] is True, "site + bot code together: restart")

    print("c. the import check")
    old = r.head()
    bad = r.push({"server.py": "raise SystemExit('boom: a bad import')\n"}, "bad server")
    res, s = update(r, sp)
    ok(res["status"] == "rolled_back" and r.head() == old and s.get("bad_sha") == bad and res.get("held") == "Bot server starts (imports)",
       "a server.py that cannot import is never started: rolled back, marked bad", res)
    ok("restart_pending" not in s or s["restart_pending"].get("sha") != bad, "no restart marker for the bad commit")
    good = r.push({"server.py": "class _A:\n    routes = [1]\napp = _A()\n"}, "server fixed")
    res, s = update(r, sp)
    ok(res["status"] == "updated" and res["restart"] and r.head() == good, "the fixed server imports: updated, restart", res)

    print("d. the crash-loop net")
    prev = s["crash_guard"]["old"]
    told = []
    t0 = s["crash_guard"]["t"]
    seq = [au.crash_check(r.sh, now=t0 + 30 * i, path=sp, notify_fn=lambda *a, **k: told.append(a)) for i in range(1, 4)]
    ok([x["status"] for x in seq] == ["counted"] * 3 and r.head() == good and not told,
       "the restart + 2 short runs: only counted, git untouched", seq)
    look = au.crash_check(r.sh, now=t0 + 100, path=sp, count=False)
    ok(look["status"] == "counted" and look["starts"] == 3, "count=False only looks", look)
    x = au.crash_check(r.sh, now=t0 + 120, path=sp, notify_fn=lambda *a, **k: told.append(a))
    s = au.load_state(sp)
    ok(x["status"] == "rolled_back" and r.head() == prev and s.get("bad_sha") == good and "crash_guard" not in s,
       "the 4th start within 10 min: back to the commit before, that commit marked bad", (x, s.get("last")))
    ok(len(told) == 1 and "Back on" in told[0][1], "ONE phone push says so", told)
    ok(au.crash_check(r.sh, now=t0 + 150, path=sp)["status"] == "none", "after that: nothing armed")
    ok(s["last"]["status"] == "rolled_back" and s["last"]["mode"] == "crash", "the history says crash / rolled_back")
    res, s2 = update(r, sp)
    ok(res["status"] == "skipped" and "failed its tests before" in res["reason"], "the next check skips the bad commit", res)

    new2 = r.push({"engine/bot.py": "X = 9\n"}, "next")
    res, s = update(r, sp)
    t1 = s["crash_guard"]["t"]
    au.crash_check(r.sh, now=t1 + 10, path=sp)
    y = au.crash_check(r.sh, now=t1 + au.CRASH_WINDOW_S + 5, path=sp)
    ok(y["status"] == "cleared" and r.head() == new2 and "crash_guard" not in au.load_state(sp), "a run past 10 min: cleared, the new code stays", y)
    r.push({"engine/bot.py": "X = 10\n"}, "again")
    res, s = update(r, sp)
    git(r.pc, "reset", "-q", "--keep", "HEAD~1")              # the owner moved it by hand
    t2 = s["crash_guard"]["t"]
    z = [au.crash_check(r.sh, now=t2 + i, path=sp) for i in range(1, 6)]
    ok(z[-1]["status"] in ("cleared", "none") and r.head() == new2, "not on the updated commit any more: cleared, git never touched", z[-2:])


def part_e(tmp):
    print("e. DailyUpdater.start")
    sp = os.path.join(tmp, "e.json")
    au.save_state({"enabled": False}, sp)
    codes = []
    real = au.crash_check
    seen = {}
    try:
        au.crash_check = lambda **kw: (seen.update(kw), {"status": "rolled_back"})[1]
        d = au.DailyUpdater(bot=None, exit_fn=codes.append, state_path=sp, every_s=3600)
        d.start()
        time.sleep(2.6)
        d._stop.set()
        ok(codes == [au.RESTART_CODE] and seen.get("count") is True, "a rolled-back crash loop restarts the server on the old code (75)", codes)
        os.environ["LE_CRASH_CHECK"] = "supervisor"
        codes.clear()
        au.crash_check = lambda **kw: (seen.update(kw), {"status": "counted"})[1]
        d2 = au.DailyUpdater(bot=None, exit_fn=codes.append, state_path=sp, every_s=3600)
        d2.start()
        d2._stop.set()
        ok(seen.get("count") is False and not codes, "LE_CRASH_CHECK=supervisor: the server only looks (the supervisor counts)")
    finally:
        au.crash_check = real
        os.environ.pop("LE_CRASH_CHECK", None)


def main():
    tmp = tempfile.mkdtemp(prefix="le_augate_")
    au.LOG_DIR = os.path.join(tmp, "logs")
    try:
        part_a()
        parts_bcd(tmp)
        part_e(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    n = sum(RES)
    print(f"\nautoupdate_paths: {n}/{len(RES)} " + ("ALL PASS" if n == len(RES) else "FAILED"))
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
