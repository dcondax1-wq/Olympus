"""PC bot automation: auto-update (engine/autoupdate.py) and the owner-enabled real-account auto-resume
(engine/autoresume.py). Offline; temporary git repos and files only; fake / Sim accounts only (the live phrase is taken
from the code constant at run time and must never land in a file).

  python -X utf8 -m tests.test_autorun
"""
from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from engine import accounts, autoresume as ar, autoupdate as au, watchdog
from engine.tradovate import LIVE_PHRASE

ET = ZoneInfo("America/New_York")
ACCT = "FAKEEVAL1"


def ts(y, mo, d, h, mi):
    return dt.datetime(y, mo, d, h, mi, tzinfo=ET).timestamp()


HALT = ts(2026, 10, 20, 17, 10)          # Tuesday 17:10 ET (CME halt)
TRADING = ts(2026, 10, 20, 10, 0)        # Tuesday 10:00 ET
EVENING = ts(2026, 10, 20, 20, 0)        # Tuesday 20:00 ET


class FakeShell(au.Shell):
    """Scripted git / python: answers by the first matching prefix; records every call."""

    def __init__(self, answers=None, tests_fail=(), pip_fail=False, changed="engine/x.py"):
        super().__init__(cwd="/nonexistent")
        self.calls = []
        self.head = "a" * 40
        self.remote = "b" * 40
        self.branch = "main"
        self.dirty = ""
        self.ff = True
        self.tests_fail = set(tests_fail)
        self.pip_fail = pip_fail
        self.changed = changed
        self.answers = answers or {}

    def git(self, *args, timeout=120):
        self.calls.append(("git",) + args)
        a = list(args)
        if a[:2] == ["rev-parse", "--abbrev-ref"]:
            return 0, self.branch + "\n"
        if a == ["rev-parse", "HEAD"]:
            return 0, self.head + "\n"
        if a[:1] == ["rev-parse"]:
            return 0, self.remote + "\n"
        if a[:1] == ["status"]:
            return 0, self.dirty
        if a[:1] == ["fetch"]:
            return 0, ""
        if a[:1] == ["merge-base"]:
            return (0 if self.ff else 1), ""
        if a[:1] == ["diff"]:
            return 0, self.changed
        if a[:1] == ["merge"]:
            self.head = a[-1]
            return 0, ""
        if a[:2] == ["reset", "--keep"]:
            self.head = a[2]
            return 0, ""
        return 1, "unexpected"

    def py(self, args, timeout=600):
        self.calls.append(("py",) + tuple(args))
        if "pip" in args:
            return (1, "pip broke") if self.pip_fail else (0, "")
        return (1, "FAIL") if any(t in args for t in self.tests_fail) else (0, "PASS")


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="le_autorun_")
    au.LOG_DIR = os.path.join(tmp, "logs")           # keep the test's update log out of logs/
    results = []

    def check(name, cond, info=""):
        results.append(bool(cond))
        print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({info})" if info and not cond else ""))

    ON = {"enabled": True}
    env_on = {"NINJATRADER_LIVE": "1"}
    try:
        # ------------------------------------------------------------------ auto-update decisions
        sh = FakeShell()
        r = au.run_update(sh, "start", EVENING, None, state={}, env={})
        check("update: off until the owner enables it (nothing touched)", r["status"] == "off" and not sh.calls, r)
        r = au.run_update(FakeShell(), "start", EVENING, None, state=ON, env={"LE_AUTOUPDATE": "0"})
        check("update: LE_AUTOUPDATE=0 overrides the opt-in", r["status"] == "off")
        for when, mode, why in ((TRADING, "start", "trading hours"), (TRADING, "daily", "trading hours"),
                                (ts(2026, 10, 20, 1, 55), "manual", "trading hours"), (EVENING, "daily", "outside the daily")):
            sh = FakeShell()
            r = au.run_update(sh, mode, when, None, state=ON, env={})
            check(f"update: window {dt.datetime.fromtimestamp(when, ET):%H:%M} {mode} -> skipped ({why})",
                  r["status"] == "skipped" and r["reason"].startswith(why) and not sh.calls, r)
        r = au.run_update(FakeShell(), "daily", HALT, None, state={**ON, "last_check_day": "2026-10-20"}, env={})
        check("update: the daily check runs once per ET date", r["status"] == "skipped" and "already checked" in r["reason"])
        r = au.run_update(FakeShell(), "start", ts(2026, 10, 24, 11, 0), None, state=ON, env={})
        check("update: a Saturday morning is allowed (no trading)", r["status"] == "updated", r)
        sh = FakeShell()
        r = au.run_update(sh, "daily", HALT, "a position is open", state=ON, env={})
        check("update: not flat -> skipped, no git call", r["status"] == "skipped" and "not flat" in r["reason"] and not sh.calls)
        sh = FakeShell(); sh.branch = "claude/test"
        r = au.run_update(sh, "start", EVENING, None, state=ON, env={})
        check("update: not on main -> skipped with an alert", r["status"] == "skipped" and r["alert"] and "not on branch main" in r["reason"])
        sh = FakeShell(); sh.dirty = " M engine/live.py\n"
        r = au.run_update(sh, "start", EVENING, None, state=ON, env={})
        check("update: dirty tree -> skipped + alert, no fetch / merge / reset",
              r["status"] == "skipped" and r["alert"] and "engine/live.py" in r["reason"]
              and not any(c[1] in ("fetch", "merge", "reset") for c in sh.calls if c[0] == "git"), sh.calls)
        sh = FakeShell(); sh.remote = sh.head
        r = au.run_update(sh, "start", EVENING, None, state=ON, env={})
        check("update: main unchanged -> up_to_date", r["status"] == "up_to_date" and not r["alert"])
        sh = FakeShell(); sh.ff = False
        r = au.run_update(sh, "start", EVENING, None, state=ON, env={})
        check("update: not a fast-forward -> skipped + alert, never merged",
              r["status"] == "skipped" and r["alert"] and not any(c[1] == "merge" for c in sh.calls if c[0] == "git"))
        sh = FakeShell(tests_fail={"tests.test_no_yahoo"})
        r = au.run_update(sh, "start", EVENING, None, state=ON, env={})
        check("update: a failing self-test rolls back (git reset --keep <old>) and marks the sha bad",
              r["status"] == "rolled_back" and r["alert"] and sh.head == "a" * 40 and r.get("bad_sha") == "b" * 40
              and ("git", "reset", "--keep", "a" * 40) in sh.calls and not r["restart"], r)
        sh = FakeShell(pip_fail=True, changed="requirements.txt\nengine/x.py")
        r = au.run_update(sh, "start", EVENING, None, state=ON, env={})
        check("update: requirements changed + pip fails -> rolled back, tests not run",
              r["status"] == "rolled_back" and sh.head == "a" * 40
              and not any("--selftest" in c for c in sh.calls if c[0] == "py"), r)
        sh = FakeShell(changed="requirements.txt")
        r = au.run_update(sh, "start", EVENING, None, state=ON, env={})
        pips = [c for c in sh.calls if c[0] == "py" and "pip" in c]
        check("update: requirements changed -> pip install, then the 3 self-tests, then restart",
              r["status"] == "updated" and r["restart"] and len(pips) == 1
              and sum(1 for c in sh.calls if c[0] == "py" and "pip" not in c) == 3)
        sh = FakeShell()
        r = au.run_update(sh, "start", EVENING, None, state=ON, env={})
        check("update: no requirements change -> no pip", r["status"] == "updated" and not any("pip" in c for c in sh.calls if c[0] == "py"))
        r = au.run_update(FakeShell(), "start", EVENING, None, state={**ON, "bad_sha": "b" * 40}, env={})
        check("update: a sha that failed before is not retried", r["status"] == "skipped" and "failed its tests before" in r["reason"])
        sp = os.path.join(tmp, "autoupdate.json")
        au.save_state(dict(ON), sp)
        r = au.run_update(FakeShell(), "daily", HALT, None, state=au.load_state(sp), env={})
        s = au.record(r, path=sp)
        check("update: record() keeps the result, the check day and the restart marker",
              s["last"]["status"] == "updated" and s["last_check_day"] == "2026-10-20" and s["restart_pending"]["sha"] == "b" * 40)
        st = au.status(sp)
        check("update: status() for the health block", st["on"] and st["result"] == "updated" and "sha" in st)
        # restart marker is read once
        s["restart_pending"]["t"] = int(__import__("time").time())
        au.save_state(s, sp)
        m1, m2 = au.take_restart_marker(sp), au.take_restart_marker(sp)
        check("update: the restart marker is read once", m1 and m1["sha"] == "b" * 40 and m2 is None)
        # flatness
        check("flat: position / routed / open bracket / pending LIT entry are not flat",
              au.flat_reason({"position": {"x": 1}}) and au.flat_reason({}, open_routed=123)
              and au.flat_reason({}, legs=[{"status": "protected"}]) and au.flat_reason({"setups": {"a": {}}}, running=True)
              and au.flat_reason({}, legs=[{"status": "closed"}]) is None and au.flat_reason({}) is None)
        bot = SimpleNamespace(state={"setups": {"k": {"tapped_t": 1}}}, running=True, _open_routed=None, adapter=None)
        check("flat: bot_flat_reason sees a 1m-CISD wait", bool(au.bot_flat_reason(bot)))
        os.makedirs(os.path.join(tmp, "root", "data"))
        with open(os.path.join(tmp, "root", "data", "ninjatrader_state.json"), "w") as f:
            json.dump({"legs": [{"status": "pending"}]}, f)
        check("flat: the on-start check reads NinjaTrader's saved legs", "bracket" in (au.files_flat_reason(os.path.join(tmp, "root")) or ""))
        # in-server daily updater: exit 75 only after a successful update, never when not flat
        exits = []
        sp2 = os.path.join(tmp, "au2.json")
        au.save_state(dict(ON), sp2)
        flat_bot = SimpleNamespace(state={}, running=True, _open_routed=None, adapter=SimpleNamespace(legs=[]), _save_state=lambda: None)
        u = au.DailyUpdater(flat_bot, exit_fn=exits.append, clock=lambda: HALT, state_path=sp2)
        busy_bot = SimpleNamespace(state={"position": {"q": 1}}, running=True, _open_routed=None, adapter=None)
        ub = au.DailyUpdater(busy_bot, exit_fn=exits.append, clock=lambda: HALT, state_path=sp2)
        rb = ub.check_once(sh=FakeShell())
        check("daily updater: not flat -> no update, no exit", rb["status"] == "skipped" and not exits)
        orig_sleep = au.time.sleep
        au.time.sleep = lambda s: None
        try:
            r = u.check_once(sh=FakeShell())
            r2 = u.check_once(sh=FakeShell())
        finally:
            au.time.sleep = orig_sleep
        check("daily updater: success -> server exits with code 75 (run_bot.ps1 restarts it), then not again today",
              r["status"] == "updated" and exits == [au.RESTART_CODE] and r2 is None, (r, exits))

        # ------------------------------------------------------------------ hourly checks outside trading time ("pull all the time")
        W = {"Tue 20:00": EVENING, "Tue 23:40": ts(2026, 10, 20, 23, 40), "Wed 01:10": ts(2026, 10, 21, 1, 10),
             "Sat 11:00": ts(2026, 10, 24, 11, 0), "Sun 19:30": ts(2026, 10, 25, 19, 30), "Tue 16:20": ts(2026, 10, 20, 16, 20)}
        check("hourly: allowed weekdays 16:00-01:20 ET and all weekend",
              all(au.window_reason(t, "hourly") is None for t in W.values()), {k: au.window_reason(t, "hourly") for k, t in W.items()})
        NO = {"Wed 01:25 (30 min margin)": ts(2026, 10, 21, 1, 25), "Wed 01:55": ts(2026, 10, 21, 1, 55),
              "Tue 10:00": TRADING, "Tue 15:59": ts(2026, 10, 20, 15, 59), "Mon 01:30 (Sunday night)": ts(2026, 10, 26, 1, 30)}
        check("hourly: never 01:20-16:00 ET on a weekday",
              all(au.window_reason(t, "hourly") for t in NO.values()), {k: au.window_reason(t, "hourly") for k, t in NO.items()})
        check("hourly: the halt keeps the daily check (no hourly inside 17:02-17:50)",
              "daily check runs in the halt" in (au.window_reason(HALT, "hourly") or ""))
        check("hourly: once per clock hour", "already checked this hour" in (au.window_reason(EVENING, "hourly", None, au.hour_key(EVENING)) or "")
              and au.window_reason(EVENING + 3600, "hourly", None, au.hour_key(EVENING)) is None)
        # LIT all_hours (the Asia slot trades from 18:00 ET): the hourly checks leave the evening / overnight session alone
        AH_OK = {"Tue 16:20": ts(2026, 10, 20, 16, 20), "Tue 16:50": ts(2026, 10, 20, 16, 50), "Fri 20:00": ts(2026, 10, 23, 20, 0),
                 "Sat 11:00": ts(2026, 10, 24, 11, 0), "Sun 17:00": ts(2026, 10, 25, 17, 0)}
        AH_NO = {"Tue 17:55": ts(2026, 10, 20, 17, 55), "Tue 20:00": EVENING, "Tue 23:40": ts(2026, 10, 20, 23, 40),
                 "Wed 01:10": ts(2026, 10, 21, 1, 10), "Sun 19:30": ts(2026, 10, 25, 19, 30), "Thu 18:30": ts(2026, 10, 22, 18, 30)}
        check("hourly, LIT all_hours: only 16:00-17:30 ET on weekdays and the weekend (Fri 16:00 -> Sun 17:30); never 18:00-16:00",
              all(au.window_reason(t, "hourly", all_hours=True) is None for t in AH_OK.values())
              and all(au.window_reason(t, "hourly", all_hours=True) for t in AH_NO.values())
              and all(au.window_reason(t, "hourly") is None for k, t in AH_NO.items() if k != "Tue 17:55" and k != "Thu 18:30"),
              {k: au.window_reason(t, "hourly", all_hours=True) for k, t in {**AH_OK, **AH_NO}.items()})
        ah_bot = SimpleNamespace(state={"strategy": {"model": "lit", "params": {"all_hours": True}}}, running=True, _open_routed=None,
                                 adapter=None, _lit_all_hours=lambda: True)
        sp4 = os.path.join(tmp, "au4.json")
        au.save_state(dict(ON), sp4)
        hu4 = au.DailyUpdater(ah_bot, exit_fn=lambda c: None, clock=lambda: EVENING, state_path=sp4)
        check("hourly, LIT all_hours: a flat bot at 20:00 ET gets no hourly update (due none), the halt check still runs",
              hu4.due_mode(EVENING) is None and hu4.due_mode(HALT) == "daily" and au.bot_all_hours(ah_bot)
              and not au.bot_all_hours(flat_bot))
        sp3 =os.path.join(tmp, "au3.json")
        au.save_state(dict(ON), sp3)
        ex3 = []
        orig_sleep = au.time.sleep
        au.time.sleep = lambda s: None
        try:
            hu = au.DailyUpdater(flat_bot, exit_fn=ex3.append, clock=lambda: EVENING, state_path=sp3)
            check("hourly: due_mode at 20:00 ET = hourly, at 17:10 = daily, at 10:00 = none",
                  hu.due_mode(EVENING) == "hourly" and hu.due_mode(HALT) == "daily" and hu.due_mode(TRADING) is None)
            sh_up = FakeShell(); sh_up.remote = sh_up.head
            r = hu.check_once(sh=sh_up, optin={})
            r_again = hu.check_once(sh=FakeShell(), optin={})
            check("hourly: up to date -> no restart, recorded for the hour, not again this hour",
                  r["status"] == "up_to_date" and r["mode"] == "hourly" and not ex3 and r_again is None
                  and au.load_state(sp3).get("last_hourly") == au.hour_key(EVENING) and not au.load_state(sp3).get("last_check_day"), r)
            hu2 = au.DailyUpdater(flat_bot, exit_fn=ex3.append, clock=lambda: EVENING + 3600, state_path=sp3)
            r = hu2.check_once(sh=FakeShell(), optin={})
            check("hourly: the next hour a new main fast-forwards, self-tests, then exit 75",
                  r["status"] == "updated" and ex3 == [au.RESTART_CODE], (r, ex3))
            armed = SimpleNamespace(state={"setups": {"k": {"limit": 1}}}, running=True, _open_routed=None, adapter=SimpleNamespace(legs=[]))
            sp4 = os.path.join(tmp, "au4.json")
            au.save_state(dict(ON), sp4)
            sh4 = FakeShell()
            r = au.DailyUpdater(armed, exit_fn=ex3.append, clock=lambda: EVENING, state_path=sp4).check_once(sh=sh4, optin={})
            check("hourly: a setup armed -> skipped, no git call, retried next minute",
                  r["status"] == "skipped" and "pending" in r["reason"] and not sh4.calls and not au.load_state(sp4).get("last_hourly"), r)
            live_bot = SimpleNamespace(state={}, running=True, _open_routed=None, adapter=SimpleNamespace(legs=[]),
                                       cfg={"adapter": "ninjatrader", "nt_account": ACCT})
            sh5 = FakeShell()
            r = au.DailyUpdater(live_bot, exit_fn=ex3.append, clock=lambda: EVENING, state_path=sp4).check_once(sh=sh5, optin={})
            check("hourly: a real-account bot without auto-resume waits for the halt check (no git call, no restart)",
                  r["status"] == "skipped" and "17:02" in r["reason"] and not sh5.calls and ex3 == [au.RESTART_CODE], r)
            check("hourly: paper / Sim bots and a stopped bot restart safely",
                  au.restart_safe_reason(flat_bot) is None
                  and au.restart_safe_reason(SimpleNamespace(running=True, cfg={"adapter": "ninjatrader", "nt_account": "Sim101"}), {}) is None
                  and au.restart_safe_reason(SimpleNamespace(running=False, cfg={"adapter": "ninjatrader", "nt_account": ACCT}), {}) is None)
            sh6 = FakeShell(); sh6.dirty = " M engine/live.py\n"
            sp6 = os.path.join(tmp, "au6.json")
            au.save_state(dict(ON), sp6)
            r = au.DailyUpdater(flat_bot, exit_fn=ex3.append, clock=lambda: EVENING, state_path=sp6).check_once(sh=sh6, optin={})
            check("hourly: a dirty tree is skipped without the hourly alert (the halt check still alerts)",
                  r["status"] == "skipped" and not r["alert"] and not (au.load_state(sp6).get("history") or []), r)
        finally:
            au.time.sleep = orig_sleep

        # ------------------------------------------------------------------ real git: fast-forward, rollback, untouched
        def git(cwd, *a):
            return subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True, check=True).stdout.strip()

        bare, work, dev = (os.path.join(tmp, n) for n in ("o.git", "w", "dev"))
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", bare], check=True)
        subprocess.run(["git", "clone", "-q", bare, dev], check=True, capture_output=True)
        for d in (dev,):
            git(d, "config", "user.email", "t@t"); git(d, "config", "user.name", "t")
        git(dev, "checkout", "-q", "-b", "main")
        open(os.path.join(dev, "a.txt"), "w").write("1\n")
        git(dev, "add", "."); git(dev, "commit", "-qm", "c1"); git(dev, "push", "-q", "origin", "main")
        subprocess.run(["git", "clone", "-q", "-b", "main", bare, work], check=True, capture_output=True)
        git(work, "config", "user.email", "t@t"); git(work, "config", "user.name", "t")
        old = git(work, "rev-parse", "HEAD")
        open(os.path.join(dev, "a.txt"), "w").write("2\n")
        git(dev, "commit", "-qam", "c2"); git(dev, "push", "-q", "origin", "main")
        new = git(dev, "rev-parse", "HEAD")
        ok_t = [["-c", "import sys; sys.exit(0)"]]
        bad_t = [["-c", "import sys; sys.exit(3)"]]
        r = au.run_update(au.Shell(work), "start", EVENING, None, state=ON, tests=bad_t, env={})
        check("git: failing test -> rolled back to the old sha, clean tree",
              r["status"] == "rolled_back" and git(work, "rev-parse", "HEAD") == old and not git(work, "status", "--porcelain")
              and open(os.path.join(work, "a.txt")).read() == "1\n", r)
        r = au.run_update(au.Shell(work), "start", EVENING, None, state=ON, tests=ok_t, env={})
        check("git: passing tests -> fast-forwarded to origin/main", r["status"] == "updated" and git(work, "rev-parse", "HEAD") == new, r)
        open(os.path.join(dev, "a.txt"), "w").write("3\n")
        git(dev, "commit", "-qam", "c3"); git(dev, "push", "-q", "origin", "main")
        open(os.path.join(work, "a.txt"), "w").write("local edit\n")
        r = au.run_update(au.Shell(work), "start", EVENING, None, state=ON, tests=ok_t, env={})
        check("git: a local edit is never touched (skipped, edit kept)",
              r["status"] == "skipped" and open(os.path.join(work, "a.txt")).read() == "local edit\n"
              and git(work, "rev-parse", "HEAD") == new)
        git(work, "checkout", "-q", "--", "a.txt")
        open(os.path.join(work, "b.txt"), "w").write("mine\n")
        git(work, "add", "b.txt"); git(work, "commit", "-qm", "local commit")
        mine = git(work, "rev-parse", "HEAD")
        r = au.run_update(au.Shell(work), "start", EVENING, None, state=ON, tests=ok_t, env={})
        check("git: a local commit (not a fast-forward) is never merged or reset",
              r["status"] == "skipped" and "fast-forward" in r["reason"] and git(work, "rev-parse", "HEAD") == mine)

        # ------------------------------------------------------------------ bot-made tracked files (engine/generated_files.py)
        # the Surface 2026-10-20: "skipped: local changes in tracked files: cache/dash/5y_NQ.json, ..., data/GEX_1d.csv"
        sh = FakeShell(); sh.dirty = " M cache/dash/5y_NQ.json\n M data/GEX_1d.csv\n M research/lit/live_check.json\n"
        r = au.run_update(sh, "start", EVENING, None, state=ON, env={})
        check("update: only bot-made files changed -> not dirty, updated", r["status"] == "updated", r)
        sh = FakeShell(changed="data/GEX_1d.csv\nengine/x.py"); sh.dirty = " M data/GEX_1d.csv\n M cache/dash/coverage.json\n"
        r = au.run_update(sh, "start", EVENING, None, state=ON, env={})
        co = [c for c in sh.calls if c[:2] == ("git", "checkout")]
        check("update: only the bot-made files the update changes are reset, before the merge",
              r["status"] == "updated" and co == [("git", "checkout", "HEAD", "--", "data/GEX_1d.csv")]
              and sh.calls.index(co[0]) < next(i for i, c in enumerate(sh.calls) if c[:2] == ("git", "merge")), sh.calls)
        sh = FakeShell(); sh.dirty = " M cache/dash/5y_NQ.json\n M engine/live.py\n"
        r = au.run_update(sh, "start", EVENING, None, state=ON, env={})
        check("update: a hand edit next to bot-made files still blocks (reason names only the hand edit)",
              r["status"] == "skipped" and "engine/live.py" in r["reason"] and "cache/dash" not in r["reason"]
              and not any(c[1] in ("fetch", "merge", "checkout") for c in sh.calls if c[0] == "git"), r)
        from engine import generated_files as gf
        check("generated: list covers the Surface's files, never code or the model",
              all(gf.is_generated(p) for p in ("cache/dash/5y_NQ.json", "cache/dash/bt_NQ_default.json", "cache/dash/coverage.json",
                                               "data/GEX_1d.csv", "data/VIX_1d.csv", "data/VXN_1d.csv", "research/lit/live_check.json",
                                               "research/lit/live_timing.json", "research/lit/live_exit_route.json",
                                               "research/lit/rehearsal.json", "tools/web_hub_snapshot.json", "cache\\dash\\es_fresh.json"))
              and not any(gf.is_generated(p) for p in ("engine/live.py", "live_model.json", "live_model_lit.json", "data/NQ_5m.csv",
                                                       "UPDATE.bat", "research/lit/lit_final.json", "cache/other.json")))

        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        upd = open(os.path.join(here, "UPDATE.bat"), encoding="utf-8").read()
        ots = open(os.path.join(here, "scripts", "one_time_setup.ps1"), encoding="utf-8").read()
        check("scripts: UPDATE.bat and one_time_setup.ps1 reset bot-made files (--prepare-pull) right before git pull",
              0 < upd.find("engine.generated_files --prepare-pull") < upd.find("git pull --ff-only origin main")
              and 0 < ots.find("--prepare-pull") < ots.find("& git pull --ff-only origin main")
              and ots.find("--discard-all") < ots.find("& git checkout main"))

        bare2, w2, d2 =(os.path.join(tmp, n) for n in ("g.git", "gw", "gdev"))
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", bare2], check=True)
        subprocess.run(["git", "clone", "-q", bare2, d2], check=True, capture_output=True)
        git(d2, "config", "user.email", "t@t"); git(d2, "config", "user.name", "t")
        git(d2, "checkout", "-q", "-b", "main")

        def put(root, rel, text):
            p = os.path.join(root, *rel.split("/"))
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w") as fh:
                fh.write(text)

        def get(root, rel):
            with open(os.path.join(root, *rel.split("/"))) as fh:
                return fh.read()

        for rel in ("cache/dash/5y_NQ.json", "cache/dash/coverage.json", "data/GEX_1d.csv", "engine/x.py"):
            put(d2, rel, "v1\n")
        git(d2, "add", "."); git(d2, "commit", "-qm", "g1"); git(d2, "push", "-q", "origin", "main")
        subprocess.run(["git", "clone", "-q", "-b", "main", bare2, w2], check=True, capture_output=True)
        git(w2, "config", "user.email", "t@t"); git(w2, "config", "user.name", "t")
        g_old = git(w2, "rev-parse", "HEAD")
        put(d2, "engine/x.py", "v2\n"); put(d2, "data/GEX_1d.csv", "upstream\n")
        git(d2, "commit", "-qam", "g2"); git(d2, "push", "-q", "origin", "main")
        g_new = git(d2, "rev-parse", "HEAD")
        # the bot rewrote its files on the PC (one of them main changes too)
        put(w2, "cache/dash/5y_NQ.json", "bot\n"); put(w2, "cache/dash/coverage.json", "bot\n"); put(w2, "data/GEX_1d.csv", "bot\n")
        rewrite_fail = [["-c", "open('data/GEX_1d.csv','w').write('test\\n'); import sys; sys.exit(3)"]]
        r = au.run_update(au.Shell(w2), "start", EVENING, None, state=ON, tests=rewrite_fail, env={})
        check("git: bot-made files + a failing test that rewrites one -> still rolled back cleanly to the old sha",
              r["status"] == "rolled_back" and git(w2, "rev-parse", "HEAD") == g_old and get(w2, "engine/x.py") == "v1\n"
              and get(w2, "cache/dash/5y_NQ.json") == "bot\n", r)
        put(w2, "data/GEX_1d.csv", "bot\n")
        r = au.run_update(au.Shell(w2), "start", EVENING, None, state=ON, tests=ok_t, env={})
        check("git: modified cache/dash + GEX no longer block: fast-forwarded (GEX = main's, untouched caches kept)",
              r["status"] == "updated" and git(w2, "rev-parse", "HEAD") == g_new and get(w2, "engine/x.py") == "v2\n"
              and get(w2, "data/GEX_1d.csv") == "upstream\n" and get(w2, "cache/dash/5y_NQ.json") == "bot\n", r)
        put(d2, "engine/x.py", "v3\n"); git(d2, "commit", "-qam", "g3"); git(d2, "push", "-q", "origin", "main")
        put(w2, "engine/x.py", "hand edit\n")
        r = au.run_update(au.Shell(w2), "start", EVENING, None, state=ON, tests=ok_t, env={})
        check("git: a modified engine/*.py still blocks (edit kept, HEAD kept)",
              r["status"] == "skipped" and "engine/x.py" in r["reason"] and get(w2, "engine/x.py") == "hand edit\n"
              and git(w2, "rev-parse", "HEAD") == g_new, r)
        git(w2, "checkout", "-q", "--", "engine/x.py")
        # UPDATE.bat on a PC without the fix: plain `git pull --ff-only` with bot-made files dirty that main does not change
        pr = subprocess.run(["git", "pull", "-q", "--ff-only", "origin", "main"], cwd=w2, capture_output=True, text=True)
        check("git: plain pull --ff-only succeeds with dirty bot-made files main does not change (first LE UPDATE gets the fix)",
              pr.returncode == 0 and get(w2, "engine/x.py") == "v3\n" and get(w2, "cache/dash/5y_NQ.json") == "bot\n", pr.stderr)
        put(d2, "cache/dash/coverage.json", "upstream2\n"); git(d2, "commit", "-qam", "g4"); git(d2, "push", "-q", "origin", "main")
        put(w2, "cache/dash/coverage.json", "bot2\n")
        hit = gf.prepare_pull(lambda *a: au.Shell(w2).git(*a))
        pr = subprocess.run(["git", "pull", "-q", "--ff-only", "origin", "main"], cwd=w2, capture_output=True, text=True)
        check("git: UPDATE.bat's --prepare-pull resets only what main changes, then the pull succeeds",
              hit == ["cache/dash/coverage.json"] and pr.returncode == 0 and get(w2, "cache/dash/coverage.json") == "upstream2\n"
              and get(w2, "cache/dash/5y_NQ.json") == "bot\n", (hit, pr.stderr))

        # ------------------------------------------------------------------ auto-resume: opt-in record
        op = os.path.join(tmp, "auto_resume.json")
        for acct, phrase, why in (("Sim101", LIVE_PHRASE, "Sim"), (ACCT, "", "phrase"), (ACCT, LIVE_PHRASE.lower(), "phrase"),
                                  ("", LIVE_PHRASE, "account")):
            try:
                ar.enable(acct, phrase, {}, path=op)
                bad = True
            except ValueError:
                bad = False
            check(f"opt-in: refused ({why})", not bad and not os.path.exists(op))
        start_cfg = {"sym": "NQ", "tf": "5m", "adapter": "ninjatrader", "armed": True, "nt_account": ACCT, "confirm": LIVE_PHRASE}
        rec = ar.enable(ACCT, LIVE_PHRASE, start_cfg, now=EVENING, path=op)
        raw = open(op, encoding="utf-8").read()
        check("opt-in: stored for that exact account, the phrase is NOT in the file",
              rec["enabled"] and rec["account"] == ACCT and LIVE_PHRASE not in raw and LIVE_PHRASE.lower() not in raw.lower()
              and "confirm" not in json.loads(raw)["cfg"] and ar.valid(rec))
        check("opt-in: data/auto_resume.json is gitignored",
              subprocess.run(["git", "check-ignore", "-q", "data/auto_resume.json"], cwd=au.ROOT).returncode == 0
              and subprocess.run(["git", "check-ignore", "-q", "data/autoupdate.json"], cwd=au.ROOT).returncode == 0)
        tampered = {**rec, "account": "OTHER1"}
        check("opt-in: an edited record (other account) fails its proof", not ar.valid(tampered))

        # ------------------------------------------------------------------ auto-resume gate
        auto_cfg = watchdog.sanitize(start_cfg, phrases=(LIVE_PHRASE,))
        from engine.live import trading_day
        now = EVENING
        today = trading_day(now)                      # 20:00 ET belongs to the next trading day
        connected = True
        d = ar.decide(rec, auto_cfg, None, env=env_on, now=now, connected=connected)
        check("gate: opt-in + matching account + NINJATRADER_LIVE=1 + connected -> resume (phrase only in memory)",
              d["resume"] and d["cfg"]["confirm"] == LIVE_PHRASE and d["cfg"]["nt_account"] == ACCT and d["cfg"]["armed"], d["reason"])
        cases = [
            ("no opt-in", dict(optin=None)),
            ("opt-in off", dict(optin={**rec, "enabled": False})),
            ("tampered", dict(optin=tampered)),
            ("intentional stop (no autostart record)", dict(cfg=None)),
            ("account mismatch", dict(cfg={**auto_cfg, "nt_account": "FAKEEVAL2"})),
            ("account mismatch (case)", dict(cfg={**auto_cfg, "nt_account": ACCT.lower()})),
            ("Sim start record", dict(cfg={**auto_cfg, "nt_account": "Sim101"})),
            ("NINJATRADER_LIVE missing", dict(env={})),
            ("kill flag today", dict(ls={"day": today, "kill": True})),
            ("daily loss today", dict(ls={"day": today, "kill": False, "day_pnl_routed": -1004.0})),
            ("failed start 3 min ago", dict(optin={**rec, "last_fail_at": now - 180})),
            ("NinjaTrader not connected", dict(conn=False)),
            ("NinjaTrader no connection files", dict(conn=None)),
        ]
        for name, kw in cases:
            d = ar.decide(kw.get("optin", rec), kw.get("cfg", auto_cfg), kw.get("ls"), env=kw.get("env", env_on), now=now,
                          connected=kw.get("conn", True))
            check(f"gate: {name} -> no resume", not d["resume"] and d["cfg"] is None, d["reason"])
        d = ar.decide(rec, auto_cfg, {"day": "2026-10-18", "kill": True}, env=env_on, now=now, connected=True)
        check("gate: an earlier day's kill flag does not block today", d["resume"], d["reason"])
        d = ar.decide({**rec, "last_fail_at": now - 700}, auto_cfg, None, env=env_on, now=now, connected=True)
        check("gate: 10+ min after a failed start it may try again", d["resume"])
        check("gate: the existing autostart never resumes a real account by itself",
              not watchdog.decide_resume({"cfg": auto_cfg, "saved_at": now, "mode": "live"}, now)["resume"])

        # ------------------------------------------------------------------ resume_live (fake bot, fake clock)
        class FakeBot:
            def __init__(self, ok=True, disabled=None):
                self.running, self.calls, self.ok, self.dis, self.adapter = False, [], ok, disabled, None

            def start(self, cfg):
                self.calls.append(dict(cfg))
                self.adapter = SimpleNamespace(disabled=self.dis)
                if self.ok:
                    self.running = True
                    return {"ok": True, "restored": None}
                return {"ok": False, "error": "boom"}

            def stop(self):
                self.running = False

        pushes = []
        clock = [now]
        fb = FakeBot()
        r = ar.resume_live(fb, auto_cfg, {"sha": "abc1234ffff"}, notify=lambda *a: pushes.append(a), log=lambda t: None,
                           sleep=lambda s: clock.__setitem__(0, clock[0] + s), clock=lambda: clock[0], path=op,
                           state_path=os.path.join(tmp, "nols.json"), connected_fn=lambda c: True, env=env_on)
        check("resume_live: resumes and pushes 'Bot resumed on <account> after the update to <sha>'",
              fb.running and len(fb.calls) == 1 and pushes and pushes[-1][0] == f"Bot resumed on {ACCT}"
              and "abc1234" in pushes[-1][1], pushes)
        check("resume_live: the opt-in file still has no phrase after a resume", LIVE_PHRASE not in open(op, encoding="utf-8").read())
        pushes.clear()
        fb = FakeBot()
        r = ar.resume_live(fb, auto_cfg, None, notify=lambda *a: pushes.append(a), log=lambda t: None,
                           sleep=lambda s: clock.__setitem__(0, clock[0] + s), clock=lambda: clock[0], path=op,
                           state_path=os.path.join(tmp, "nols.json"), connected_fn=lambda c: True, env={})
        check("resume_live: NINJATRADER_LIVE missing -> refused, bot never started, phone told",
              not fb.calls and pushes and "NOT resumed" in pushes[-1][0] and ar.status(op)["last_result"] == "refused")
        pushes.clear()
        conn = {"n": 0}

        def later(c):
            conn["n"] += 1
            return conn["n"] > 3                     # NinjaTrader connects after ~1.5 min (3 waits of 30 s)
        fb = FakeBot()
        r = ar.resume_live(fb, auto_cfg, None, notify=lambda *a: pushes.append(a), log=lambda t: None,
                           sleep=lambda s: clock.__setitem__(0, clock[0] + s), clock=lambda: clock[0], path=op,
                           state_path=os.path.join(tmp, "nols.json"), connected_fn=later, env=env_on)
        check("resume_live: waits for NinjaTrader to connect after a reboot, then resumes", fb.running and len(fb.calls) == 1)
        pushes.clear()
        t_start = clock[0]
        fb = FakeBot(ok=True, disabled="LIVE account refused: start the server with NINJATRADER_LIVE=1")
        r = ar.resume_live(fb, auto_cfg, None, notify=lambda *a: pushes.append(a), log=lambda t: None,
                           sleep=lambda s: clock.__setitem__(0, clock[0] + s), clock=lambda: clock[0], path=op,
                           state_path=os.path.join(tmp, "nols.json"), connected_fn=lambda c: True, env=env_on)
        gaps = len(fb.calls)
        check("resume_live: an adapter that comes up DISABLED is stopped, retried after 10 min, 3 tries, then the phone is told",
              gaps == 3 and not fb.running and clock[0] - t_start >= 2 * ar.FAIL_COOLDOWN_S and pushes and "NOT resumed" in pushes[-1][0],
              (gaps, clock[0] - t_start, pushes))
        ls_kill = os.path.join(tmp, "ls_kill.json")
        json.dump({"day": trading_day(clock[0]), "kill": True}, open(ls_kill, "w"))
        rec = ar.enable(ACCT, LIVE_PHRASE, start_cfg, now=clock[0], path=op)
        fb = FakeBot()
        ar.resume_live(fb, auto_cfg, None, notify=lambda *a: None, log=lambda t: None, sleep=lambda s: None, clock=lambda: clock[0],
                       path=op, state_path=ls_kill, connected_fn=lambda c: True, env=env_on)
        check("resume_live: kill flag today -> never started", not fb.calls)
        # disable / kill switch
        was = ar.disable("kill switch", path=op)
        fb = FakeBot()
        r = ar.resume_live(fb, auto_cfg, None, notify=lambda *a: pushes.append(a), log=lambda t: None, sleep=lambda s: None,
                           clock=lambda: clock[0], path=op, state_path=os.path.join(tmp, "nols.json"), connected_fn=lambda c: True, env=env_on)
        st = ar.status(op)
        check("disable: the kill switch / --disable-auto-resume turn it off; then nothing auto-arms",
              was and not fb.calls and not st["on"] and st["off_reason"] == "kill switch" and "proof" not in json.load(open(op)))
        check("disable: turning it on again needs the owner's command (no proof left)", not ar.valid(ar.load(op)))

        # ------------------------------------------------------------------ health block + cloud text
        hl = {"auto": {"version": "abc1234", "branch": "main",
                       "update": {"on": True, "result": "rolled_back", "reason": "self-test failed", "last_check_t": int(HALT),
                                  "updated_at": int(HALT) - 86400},
                       "resume": {"on": True, "account": ACCT, "last_result": "refused", "last_t": int(EVENING), "last_reason": "not connected"}}}
        txt = accounts.auto_text(hl)
        check("health: one line 'running version abc1234, updated ...; auto-update on (...); auto-resume on (ACCT)'",
              txt.startswith("running version abc1234, updated") and "auto-update on" in txt and f"auto-resume on ({ACCT})" in txt, txt)
        ns = accounts.auto_notices(hl, EVENING + 60)
        check("health: the cloud pushes a failed update and a refused resume (PC keys, so not twice)",
              len(ns) == 2 and all(n["kind"] == "pc" for n in ns) and ns[0]["key"].startswith("auto:update:")
              and ns[1]["key"] == f"auto:refused:{int(EVENING) // 60}", ns)
        blk = accounts._auto_status()
        check("health: pc_health's auto block has version / update / resume, no secrets",
              set(blk) >= {"version", "update", "resume"} and LIVE_PHRASE not in json.dumps(blk))
        bot = SimpleNamespace(cfg={"adapter": "paper"}, adapter=None, health={}, state={}, ledger=[], running=False, started_at=None)
        check("health: pc_health carries it", "auto" in accounts.pc_health(bot))
        # nothing in the repo holds the phrase outside its two definitions
        hits = []
        for rel in ("engine/autoresume.py", "engine/autoupdate.py", "tests/test_autorun.py", "server.py", "scripts/run_bot.ps1",
                    "scripts/install_autostart.ps1", "scripts/setup_dedicated_pc.ps1"):
            with open(os.path.join(au.ROOT, rel), encoding="utf-8") as f:
                if LIVE_PHRASE in f.read():
                    hits.append(rel)
        check("repo: the phrase is not written into the new code, the scripts or this test", not hits, hits)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    n = len(results)
    print(f"autorun: {sum(results)}/{n} {'ALL PASS' if all(results) else 'FAILED'}")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
