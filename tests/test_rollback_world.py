"""If Monday's landing breaks something, the PC saves itself (night-rollback 2026-11-23). A temp git world (origin + the PC's
clone), the REAL engine/autoupdate code path the server runs (DailyUpdater.check_once / crash_check), fakes only for the bot and
the phone. Never arms anything; no network.

    python -X utf8 -m tests.test_rollback_world        (~20 s)

A. a new head whose health check (self-tests) fails  -> rolled back to the last good SHA before any restart; the bot keeps
   running exactly as it was (no exit, the autostart record untouched); ONE phone alert naming both SHAs; the next hourly
   check does not take it again and sends nothing more.
B. a new head whose server does not import           -> the same (held "Bot server starts (imports)").
C. a new head that crashes the bot within 2 minutes  -> the update restarts (exit 75, crash guard armed); the supervisor's
   restarts (its real 5 / 15 / 60 s waits) are counted; the 4th start rolls back to the last good SHA, ONE push "Update
   rolled back", the server exits 75 so the old code starts; the autostart record (paper / armed state) is untouched, so the
   old code resumes exactly as before; START BOT / the next check never re-take the bad SHA.
C2. the same with a crash about 3.5 min after each start (the 4th start lands after 10 min): rolled back too (before
   night-rollback the guard cleared itself here and the bad code looped for good, with no push).
C3. a good update that runs 12 min, then one owner restart: never rolled back.
D. never mid-trade: with a position open (LIT, ATLAS or an extra account) the check does not fetch, move or restart anything.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import autoupdate as au  # noqa: E402
from tests.test_autoupdate_paths import Repo, git  # noqa: E402

RES = []
GOOD_T = [["-c", "import sys; sys.exit(0)"]]
BAD_T = [["-c", "import sys; print('FAIL health: 3 checks red'); sys.exit(1)"]]
SAT_19 = dt.datetime(2026, 11, 21, 19, 5, tzinfo=au.ET).timestamp()     # Saturday 19:05 ET: an hourly check is allowed


def check(name, ok, info=""):
    print(f"{'ok  ' if ok else 'FAIL'} {name}{(': ' + str(info)[:400]) if info and not ok else ''}")
    RES.append(bool(ok))


class Bot:
    """A paper bot, running (hourly updates restart only a bot that comes back by itself: paper / Sim / opt-in)."""
    def __init__(self, position=None):
        self.running = True
        self.cfg = {"adapter": "paper", "sym": "NQ"}
        self.state = {"position": position} if position else {}
        self._open_routed = None
        self.saved = 0

    def _save_state(self):
        self.saved += 1


class World:
    def __init__(self, tmp):
        self.r = Repo(tmp)
        git(self.r.pc, "config", "user.email", "t@example.com")
        git(self.r.pc, "config", "user.name", "t")
        self.sp = os.path.join(tmp, "autoupdate.json")
        au.save_state({"enabled": True}, self.sp)
        # the autostart record (data/autostart.json: what resumes after a restart: paper / armed). Untracked + ignored, as on the PC
        with open(os.path.join(self.r.pc, ".git", "info", "exclude"), "a", encoding="utf-8") as fh:
            fh.write("data/\n")
        os.makedirs(os.path.join(self.r.pc, "data"), exist_ok=True)
        self.autostart = os.path.join(self.r.pc, "data", "autostart.json")
        with open(self.autostart, "w", encoding="utf-8") as fh:
            json.dump({"cfg": {"adapter": "ninjatrader", "armed": True, "account": "Sim101"}, "saved_at": 1}, fh)
        self.autostart_bytes = open(self.autostart, "rb").read()
        self.good = self.r.head()
        self.exits, self.pushes = [], []

    def updater(self, bot):
        return au.DailyUpdater(bot, exit_fn=self.exits.append, clock=lambda: SAT_19, state_path=self.sp)

    def check(self, bot, tests, now=SAT_19):
        u = self.updater(bot)
        return u.check_once(now=now, sh=self.r.sh, tests=tests, optin=None)

    def autostart_same(self):
        return open(self.autostart, "rb").read() == self.autostart_bytes


def capture(w):
    real_notify, real_digest = au.notify, None
    def fake(title, body, key, sync=False):
        w.pushes.append((title, body, key))
    au.notify = fake
    try:
        from engine import alert_bus as AB
        real_digest = AB.digest_add
        AB.digest_add = lambda *a, **k: None
    except Exception:  # noqa: BLE001
        AB = None
    return lambda: (setattr(au, "notify", real_notify), AB and real_digest and setattr(AB, "digest_add", real_digest))


def case_a(tmp):
    w = World(tmp)
    undo = capture(w)
    try:
        bad = w.r.push({"engine/bot.py": "X = 2  # breaks the health check\n"}, "bad: health")
        bot = Bot()
        res = w.check(bot, BAD_T)
        s = au.load_state(w.sp)
        check("A1. health check fails -> rolled back to the last good SHA, bad_sha = the new head",
              res["status"] == "rolled_back" and w.r.head() == w.good and s.get("bad_sha") == bad, (res, w.r.head()[:7]))
        check("A2. the bot is not restarted (no exit), keeps running as it was; the autostart record untouched",
              not w.exits and bot.running and w.autostart_same(), w.exits)
        check("A3. ONE phone alert, saying what happened (rolled back, both SHAs)", len(w.pushes) == 1
              and "rolled back" in w.pushes[0][0] and bad[:7] in w.pushes[0][1] and w.good[:7] in w.pushes[0][1], w.pushes)
        res2 = w.check(bot, GOOD_T, now=SAT_19 + 3600)
        check("A4. the next hourly check does not take the bad head again and sends nothing more",
              res2["status"] == "skipped" and w.r.head() == w.good and len(w.pushes) == 1, (res2, w.pushes))
        pl = au.pull(w.r.sh, branch="main", pip=False, state_path=w.sp)
        check("A5. START BOT / UPDATE.bat (pull) keep the version that works", pl["status"] == "skipped" and w.r.head() == w.good, pl)
    finally:
        undo()


def case_b(tmp):
    w = World(tmp)
    undo = capture(w)
    try:
        bad = w.r.push({"server.py": "import no_such_module_on_this_pc\napp = None\n"}, "bad: import")
        bot = Bot()
        res = w.check(bot, GOOD_T)
        s = au.load_state(w.sp)
        check("B1. new server does not import -> rolled back before any restart, held 'Bot server starts (imports)'",
              res["status"] == "rolled_back" and w.r.head() == w.good and s.get("bad_sha") == bad
              and "imports" in str(res.get("held")), (res, w.r.head()[:7]))
        check("B2. no exit, bot state and the autostart record as before", not w.exits and w.autostart_same())
        check("B3. ONE alert, naming the import failure", len(w.pushes) == 1 and "imports" in w.pushes[0][0] + w.pushes[0][1], w.pushes)
    finally:
        undo()


def crash_starts(w, gaps, notify):
    """The supervisor's starts after the update's own restart: run each, crash after `run_s`, wait 5 / 15 / 60 s."""
    t = float(au.load_state(w.sp)["crash_guard"]["t"]) + 3
    waits = [5, 15, 60, 60, 60]
    out = [au.crash_check(w.r.sh, now=t, path=w.sp, notify_fn=notify)]          # the update's restart (start 1)
    for i, run_s in enumerate(gaps):
        t += run_s + waits[min(i, len(waits) - 1)]
        out.append(au.crash_check(w.r.sh, now=t, path=w.sp, notify_fn=notify))
        if out[-1]["status"] in ("rolled_back", "failed", "cleared"):
            break
    return out, t


def case_c(tmp, run_s, label):
    w = World(tmp)
    undo = capture(w)
    try:
        bad = w.r.push({"engine/bot.py": "X = 3  # crashes the bot after it starts\n"}, "bad: crash")
        bot = Bot()
        res = w.check(bot, GOOD_T)
        check(f"{label}1. the update passes its tests + import, restarts the server (exit 75), arms the crash guard",
              res["status"] == "updated" and w.exits == [au.RESTART_CODE] and w.r.head() == bad
              and "crash_guard" in au.load_state(w.sp) and bot.saved == 1, (res, w.exits))
        told = []
        seq, t_end = crash_starts(w, [run_s] * 4, lambda *a, **k: told.append(a))
        sts = [x["status"] for x in seq]
        s = au.load_state(w.sp)
        check(f"{label}2. crash ~{run_s // 60} min {run_s % 60} s after each start: counted, then the 4th start rolls back to the "
              f"last good SHA (bad_sha + crash_sha kept)", sts[-1] == "rolled_back" and len(sts) == 4 and w.r.head() == w.good
              and s.get("bad_sha") == bad and s.get("crash_sha") == bad, (sts, w.r.head()[:7]))
        check(f"{label}3. ONE push 'Update rolled back' saying the new code kept stopping and the version it is back on",
              len(told) == 1 and told[0][0] == "Update rolled back" and bad[:7] in told[0][1] and w.good[:7] in told[0][1], told)
        check(f"{label}4. the autostart record (paper / armed state) untouched: the old code resumes exactly as before",
              w.autostart_same())
        nxt = au.crash_check(w.r.sh, now=t_end + 30, path=w.sp, notify_fn=lambda *a, **k: told.append(a))
        pl = au.pull(w.r.sh, branch="main", pip=False, state_path=w.sp)
        check(f"{label}5. the old code's start: nothing armed any more; START BOT never re-takes the bad SHA; no 2nd push",
              nxt["status"] == "none" and pl["status"] == "skipped" and w.r.head() == w.good and len(told) == 1, (nxt, pl))
    finally:
        undo()


def case_c_server(tmp):
    """The server's own net (DailyUpdater.crash_start, the first thing server.py runs) on the 4th start: push + exit 75."""
    w = World(tmp)
    undo = capture(w)
    try:
        w.r.push({"engine/bot.py": "X = 4\n"}, "bad: crash 2")
        w.check(Bot(), GOOD_T)
        g = au.load_state(w.sp)["crash_guard"]
        now = __import__("time").time()
        g["t"], g["starts"] = now - 400, [now - 400, now - 250, now - 120]
        s = au.load_state(w.sp)
        s["crash_guard"] = g
        au.save_state(s, w.sp)
        w.exits.clear()
        real_root = os.getcwd()
        real_shell = au.Shell
        au.Shell = lambda *a, **k: real_shell(cwd=w.r.pc, **{x: y for x, y in k.items() if x != "cwd"})
        old_ns = au.notify_sync
        au.notify_sync = lambda title, body, key: w.pushes.append((title, body, key))
        try:
            st = w.updater(Bot()).crash_start()
        finally:
            au.Shell = real_shell
            au.notify_sync = old_ns
            os.chdir(real_root)
        check("C4s. server start #4 (crash_start, before the bot resumes): rolled back, ONE push, exit 75 -> the old code starts",
              st == "rolled_back" and w.exits == [au.RESTART_CODE] and w.r.head() == w.good
              and sum(1 for p in w.pushes if p[0] == "Update rolled back") == 1, (st, w.exits, w.pushes))
    finally:
        undo()


def case_c3(tmp):
    w = World(tmp)
    undo = capture(w)
    try:
        new = w.r.push({"engine/bot.py": "X = 5  # good\n"}, "good")
        w.check(Bot(), GOOD_T)
        t = float(au.load_state(w.sp)["crash_guard"]["t"]) + 3
        a = au.crash_check(w.r.sh, now=t, path=w.sp)
        b = au.crash_check(w.r.sh, now=t + 12 * 60, path=w.sp)        # ran 12 min, then one owner restart (or a reboot)
        check("C3. a good update that ran 12 min, then a restart: cleared, never rolled back, no push",
              a["status"] == "counted" and b["status"] == "cleared" and w.r.head() == new and not w.pushes, (a, b))
    finally:
        undo()


def case_d(tmp):
    w = World(tmp)
    undo = capture(w)
    try:
        w.r.push({"engine/bot.py": "X = 6\n"}, "new")
        for label, bot in (("LIT position", Bot(position={"dir": 1, "qty": 3})),
                           ("ATLAS position", _with_atlas())):
            res = w.check(bot, GOOD_T)
            check(f"D. never mid-trade ({label}): skipped, nothing fetched, moved or restarted",
                  res and res["status"] == "skipped" and "flat" in res["reason"] and w.r.head() == w.good and not w.exits
                  and not w.pushes, res)
    finally:
        undo()


def _with_atlas():
    b = Bot()
    class A:
        def position(self):
            return {"dir": -1, "qty": 2}
    b.acct_b = A()
    return b


def main():
    base = tempfile.mkdtemp(prefix="le_rollback_")
    try:
        for i, fn in enumerate((case_a, case_b, lambda t: case_c(t, 115, "C"), lambda t: case_c(t, 210, "C2-"),
                                case_c_server, case_c3, case_d)):
            try:
                fn(os.path.join(base, f"w{i}"))
            except Exception as e:  # noqa: BLE001
                import traceback
                traceback.print_exc()
                check(f"case {i} crashed: {e.__class__.__name__}: {e}", False)
    finally:
        shutil.rmtree(base, ignore_errors=True)
    ok = sum(RES)
    print(f"\nrollback world: {'PASS' if ok == len(RES) else 'FAIL'} ({ok}/{len(RES)})")
    return ok == len(RES)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
