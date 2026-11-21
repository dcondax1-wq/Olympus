"""Update gate (updategate 2026-11-20, TOP25 idea #4; engine/autoupdate.py): a bad update can never take the bot down for long.
  a. needs_restart(): site / docs / research / tests / handoff / vault / root *.md only = the bot keeps running; engine/, server.py,
     the models, scripts/, tools/*.py, web/, requirements.txt, a path nobody listed, an empty list = restart (fail-safe)
  b. a real temp repo: a site-only update is pulled + tested, restart=False, no restart marker, no crash guard; a bot update
     restarts and arms the crash guard; site + bot together restart
  c. the import check: a new server.py that cannot import is never started (rolled back, bad_sha, HEAD back); one that imports passes
  d. crash_check(): the restart + 2 short runs only counted; the 4th start within 10 min = back to the commit before, bad_sha, ONE
     push; a run past 10 min clears it; not on the updated commit = cleared, git never touched; count=False only looks
  e. DailyUpdater.start(): a rolled-back crash loop restarts the server (exit 75) on the old code; LE_CRASH_CHECK=supervisor only looks
  f. (redteam 2026-11-21) a renamed bot file (engine/x.py -> research/x.py) restarts (git's rename detection hid engine/x.py);
     the MFFU rules data the running bot caches restarts too
  g. the crash window starts at the restart, not when the update began testing (a slow update is still rolled back)
  h. the owner's own restarts (Bot Control / the phone / a new supervisor) are not counted: a good update is never rolled back
     by them, and the net stays armed after them
  i. the rollback puts back a bot-made tracked file the bad code rewrote (else git reset --keep refuses and the loop goes on)
  j. after a crash rollback: START BOT (pull) never re-takes the bad commit; a newer main with only site commits on top is not
     taken either; one that changes the bot code is
  k. server.py runs the crash check FIRST in its startup (before the bot resumes / any watcher starts); once per process; the CLI
     and the server's rollback push wait for their sends; botctl / remote_ctl mark their restarts
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
        os.makedirs(tmp, exist_ok=True)
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
    y = au.crash_check(r.sh, now=t1 + 10 + au.CRASH_WINDOW_S + 5, path=sp)     # the window starts at the first start (t1 + 10)
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


def crash_loop(r, sp, t, n, told=None, gap=40):
    told = [] if told is None else told
    return [au.crash_check(r.sh, now=t + gap * i, path=sp, notify_fn=lambda *a, **k: told.append(a)) for i in range(n)]


def part_f(tmp):
    print("f. renames and cached rule data")
    r = Repo(os.path.join(tmp, "f"))
    r.push({"engine/helper.py": "H = 1\n" * 40}, "helper")
    git(r.pc, "pull", "-q", "--ff-only")
    old = r.head()
    os.makedirs(os.path.join(r.dev, "research"), exist_ok=True)
    git(r.dev, "mv", "engine/helper.py", "research/helper.py")
    git(r.dev, "commit", "-qm", "archive the helper")
    git(r.dev, "push", "-q", "origin", "HEAD:main")
    new = git(r.dev, "rev-parse", "HEAD")
    git(r.pc, "fetch", "-q", "origin")
    paths = au.changed_paths(r.sh, old, new)
    ok(sorted(paths) == ["engine/helper.py", "research/helper.py"] and au.needs_restart(paths) == (True, ["engine/helper.py"]),
       "a bot file moved to research/: both paths listed, the bot restarts", paths)
    sp = os.path.join(tmp, "f.json")
    res, s = update(r, sp)
    ok(res["status"] == "updated" and res["restart"] is True and "crash_guard" in s, "the update restarts + arms the crash guard", res)
    ok(au.needs_restart(["research/lit/mffu_rules.json"])[0] and au.needs_restart(["research/props/firm_rules.json"])[0]
       and not au.needs_restart(["research/lab/costs.json", "research/writeups/x.md"])[0],
       "the MFFU / firm rules data the running bot caches restarts; other research data does not")


def part_g(tmp):
    print("g. the crash window starts at the restart")
    r = Repo(os.path.join(tmp, "g"))
    sp = os.path.join(tmp, "g.json")
    old = r.head()
    good = r.push({"engine/bot.py": "X = 2\n"}, "bot")
    res, s = update(r, sp)
    t0 = s["crash_guard"]["t"]
    seq = crash_loop(r, sp, t0 + 420, 4, gap=70)              # pip + tests + the PC self-test took 7 min before the restart
    ok([x["status"] for x in seq] == ["counted"] * 3 + ["rolled_back"] and r.head() == old,
       "a slow update (restart 7 min after the check began) that keeps crashing is still rolled back", [x["status"] for x in seq])
    ok(au.load_state(sp).get("bad_sha") == good, "and marked bad")


def part_h(tmp):
    print("h. owner restarts are not crashes")
    r = Repo(os.path.join(tmp, "h"))
    sp = os.path.join(tmp, "h.json")
    good = r.push({"engine/bot.py": "X = 2\n"}, "bot with a safety fix")
    res, s = update(r, sp)
    t0 = s["crash_guard"]["t"]
    out = [au.crash_check(r.sh, now=t0 + 30, path=sp)]        # the update's own restart
    for i, why in enumerate(("Bot Control restart", "the phone's restart", "a new supervisor (START BOT / reboot)")):
        ok(au.mark_deliberate_restart(why, path=sp, now=t0 + 60 + 60 * i), f"{why}: marked")
        out.append(au.crash_check(r.sh, now=t0 + 65 + 60 * i, path=sp))
    ok([x["status"] for x in out] == ["counted"] * 4 and r.head() == good and "deliberate" in out[1]["reason"]
       and out[-1]["starts"] == 1, "3 owner restarts within 10 min: none counted, the good update stays", [(x["status"], x["starts"]) for x in out])
    more = crash_loop(r, sp, t0 + 300, 3)
    ok([x["status"] for x in more] == ["counted", "counted", "rolled_back"],
       "the net stays armed: real crashes after them are still caught", [x["status"] for x in more])
    ok(not au.mark_deliberate_restart("x", path=os.path.join(tmp, "none.json")), "no crash guard armed: nothing to mark")
    r2 = Repo(os.path.join(tmp, "h2"))
    sp2 = os.path.join(tmp, "h2.json")
    r2.push({"engine/bot.py": "X = 5\n"}, "bot")
    _res, s2 = update(r2, sp2)
    t2 = s2["crash_guard"]["t"]
    au.mark_deliberate_restart("old mark", path=sp2, now=t2 - au.DELIBERATE_S - 50)
    z = crash_loop(r2, sp2, t2 + 10, 4)
    ok(z[-1]["status"] == "rolled_back", "a stale mark (older than DELIBERATE_S) never hides a crash loop", [x["status"] for x in z])


def part_i(tmp):
    print("i. a bot-made file the bad code rewrote")
    r = Repo(os.path.join(tmp, "i"))
    r.push({"data/GEX_1d.csv": "t,v\n1,2\n"}, "gex")
    git(r.pc, "pull", "-q", "--ff-only")
    old = r.head()
    bad = r.push({"engine/bot.py": "X = 7\n", "data/GEX_1d.csv": "t,v\n1,3\n"}, "bad bot + fresh gex")
    sp = os.path.join(tmp, "i.json")
    res, s = update(r, sp)
    write(r.pc, "data/GEX_1d.csv", "t,v\n1,4\n")             # the bad server refreshed it, then crashed
    told = []
    seq = crash_loop(r, sp, s["crash_guard"]["t"] + 5, 4, told)
    ok(seq[-1]["status"] == "rolled_back" and r.head() == old and au.load_state(sp).get("bad_sha") == bad and len(told) == 1
       and "Back on" in told[0][1], "rolled back (was 'ROLLBACK FAILED': git refused the rewritten file)", (seq[-1], told))
    return r, sp, old, bad


def part_j(tmp, r, sp, old, bad):
    print("j. after a crash rollback the bad code stays out")
    s = au.load_state(sp)
    ok(s.get("crash_sha") == bad, "the crash-looped commit is kept as crash_sha", s.get("crash_sha"))
    p = au.pull(r.sh, branch="main", pip=False, state_path=sp)
    ok(p["status"] == "skipped" and p.get("kept") and r.head() == old and p["say"].startswith("Kept the version that works"),
       "START BOT / UPDATE.bat (pull): the bad commit is not pulled again", p)
    site = r.push({"tools/web_public/index.html": "<p>v9</p>\n", "docs/N.md": "n\n"}, "site publish on top")
    res, s = update(r, sp)
    ok(res["status"] == "skipped" and "crash-looped" in res["reason"] and r.head() == old,
       "a newer main with only site commits on top of it: not taken (it would bring the crash back)", res)
    p = au.pull(r.sh, branch="main", pip=False, state_path=sp)
    ok(p["status"] == "skipped" and p.get("kept") and r.head() == old, "nor by START BOT", p)
    fix = r.push({"engine/bot.py": "X = 8\n"}, "the fix")
    res, s = update(r, sp)
    ok(res["status"] == "updated" and res["restart"] and r.head() == fix and "crash_sha" not in s and "bad_sha" not in s,
       "a main that changes the bot code after it: taken (guard armed again), crash_sha cleared", (res, s.get("crash_sha")))
    ok(site != fix, "(the site commit came along)")


def part_k(tmp):
    print("k. wiring")
    src = open(os.path.join(ROOT, "server.py"), encoding="utf-8").read()
    body = src[src.index("def _autostart_startup"):src.index("app.router.add_event_handler(\"startup\", _autostart_startup)")]
    ok(0 <= body.find("AUTOUPDATE.crash_start()") < body.find("_autostart_resume") and body.find("crash_start") < body.find("WATCHDOG.start()"),
       "server.py: the crash check runs before the bot resumes and before any watcher starts")
    sp = os.path.join(tmp, "k.json")
    au.save_state({"enabled": False}, sp)
    real, calls = au.crash_check, []
    try:
        au.crash_check = lambda **kw: (calls.append(kw), {"status": "counted"})[1]
        d = au.DailyUpdater(bot=None, exit_fn=lambda c: None, state_path=sp, every_s=3600)
        d.crash_start()
        d.start()
        d._stop.set()
        ok(len(calls) == 1 and calls[0].get("notify_fn") is au.notify_sync, "once per process (server startup + start()); its push waits (sync)", calls)
    finally:
        au.crash_check = real
    seen = []
    real_n = au.notify
    try:
        au.notify = lambda t, b, key, sync=False: seen.append(sync)
        au.notify_sync("t", "b", key="k")
    finally:
        au.notify = real_n
    ok(seen == [True], "notify_sync sends synchronously (a daemon thread dies with the exiting process)")
    cli = open(os.path.join(ROOT, "engine", "autoupdate.py"), encoding="utf-8").read()
    ok("crash_check(notify_fn=notify_sync)" in cli and 'mark_deliberate_restart("a new supervisor' in cli,
       "the --crash-check CLI waits for its push; --on-start (a new supervisor) marks its start")
    from engine import botctl
    old_h = dict(botctl.HOOKS)
    marks, exits = [], []
    os.environ["LE_SUPERVISED"] = "1"
    real_flat = botctl._flat_reason
    try:
        botctl._flat_reason = lambda bot: None
        botctl.HOOKS.update(deliberate=marks.append, exit=exits.append)
        r = botctl.do_restart(None)
        time.sleep(1.3)
    finally:
        botctl._flat_reason = real_flat
        botctl.HOOKS.clear()
        botctl.HOOKS.update(old_h)
        os.environ.pop("LE_SUPERVISED", None)
    ok(r.get("ok") and marks == ["Bot Control restart"] and exits == [au.RESTART_CODE], "Bot Control's Restart marks itself deliberate", (r, marks, exits))
    rc = open(os.path.join(ROOT, "engine", "remote_ctl.py"), encoding="utf-8").read()
    ok('if cmd == "restart":' in rc and "mark_deliberate_restart)(\"the phone's restart\")" in rc,
       "the phone's 'restart' marks itself deliberate (an 'update' restart does not: its own restart is counted)")


def main():
    tmp = tempfile.mkdtemp(prefix="le_augate_")
    au.LOG_DIR = os.path.join(tmp, "logs")
    try:
        part_a()
        parts_bcd(tmp)
        part_e(tmp)
        part_f(tmp)
        part_g(tmp)
        part_h(tmp)
        part_j(tmp, *part_i(tmp))
        part_k(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    n = sum(RES)
    print(f"\nautoupdate_paths: {n}/{len(RES)} " + ("ALL PASS" if n == len(RES) else "FAILED"))
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
