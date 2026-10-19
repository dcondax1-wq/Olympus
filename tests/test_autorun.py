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
