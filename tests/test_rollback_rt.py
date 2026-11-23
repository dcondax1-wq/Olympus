"""Red team on night-rollback (2026-11-23): the chained crash window must never roll back a GOOD update because the owner
restarted it, never ping-pong between the good and the bad SHA, and never act mid-trade. Same temp git world as
tests/test_rollback_world (the REAL autoupdate.crash_check / check_once / pull), no network, never arms anything.

    python -X utf8 -m tests.test_rollback_rt        (~15 s)

E1. a good update, then 4 START BOT / re-arm restarts 3 min apart (each a new supervisor: run_bot.ps1 --on-start marks it
    deliberate first): never rolled back; the guard clears once 10 min pass since the last counted start.
E2. a good update, then 3 Bot Control / phone restarts 1 min apart: never rolled back.
E3. a good update that runs all day, then the restart after 16:00 ET (a PC restart or one owner restart): cleared.
E4. a good update with ONE real crash and two owner restarts in the chain: counted, never rolled back.
E5. no loop: after a crash-loop rollback the old code's starts arm nothing; the hourly check and START BOT never re-take the bad
    SHA or a newer main that only adds site files on top of it; a newer main with a bot-code fix IS taken (one new guard).
E6. a position open: the hourly check skips (nothing fetched, moved or restarted), and the crash net's own rollback leaves the
    autostart record (what resumes the position) untouched.
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import autoupdate as au  # noqa: E402
from tests import test_rollback_world as W  # noqa: E402

RES = W.RES


def _good_update(tmp):
    w = W.World(tmp)
    undo = W.capture(w)
    new = w.r.push({"engine/bot.py": "X = 7  # good\n"}, "good")
    res = w.check(W.Bot(), W.GOOD_T)
    assert res["status"] == "updated", res
    t = float(au.load_state(w.sp)["crash_guard"]["t"]) + 3
    return w, undo, new, t


def _owner_start(w, t, why):
    """A deliberate restart: the mark (run_bot.ps1 --on-start / Bot Control / the phone), then the server's crash_check."""
    au.mark_deliberate_restart(why, path=w.sp, now=t)
    return au.crash_check(w.r.sh, now=t + 20, path=w.sp)


def case_e1(tmp):
    w, undo, new, t = _good_update(tmp)
    try:
        sts = [au.crash_check(w.r.sh, now=t, path=w.sp)["status"]]
        for i in range(1, 5):
            sts.append(_owner_start(w, t + 180 * i, "a new supervisor (START BOT / reboot)")["status"])
        later = au.crash_check(w.r.sh, now=t + 180 * 4 + 20 + 11 * 60, path=w.sp)["status"]
        W.check("E1. good update + 4 START BOT / re-arm restarts 3 min apart: never rolled back, cleared after a 10+ min run",
                "rolled_back" not in sts and "cleared" in sts + [later] and w.r.head() == new and not w.pushes, (sts, later))
    finally:
        undo()


def case_e2(tmp):
    w, undo, new, t = _good_update(tmp)
    try:
        sts = [au.crash_check(w.r.sh, now=t, path=w.sp)["status"]]
        for i, why in enumerate(("Bot Control restart", "the phone's restart", "Bot Control restart"), 1):
            sts.append(_owner_start(w, t + 60 * i, why)["status"])
        W.check("E2. good update + 3 Bot Control / phone restarts 1 min apart: never rolled back",
                "rolled_back" not in sts and w.r.head() == new and not w.pushes, sts)
    finally:
        undo()


def case_e3(tmp):
    w, undo, new, t = _good_update(tmp)
    try:
        a = au.crash_check(w.r.sh, now=t, path=w.sp)
        b = au.crash_check(w.r.sh, now=t + 20 * 3600, path=w.sp)          # ran all day; the 16:00 ET restart (unmarked even)
        W.check("E3. good update that ran all day, then the restart after 16:00 ET: cleared, no push",
                a["status"] == "counted" and b["status"] == "cleared" and w.r.head() == new and not w.pushes, (a, b))
    finally:
        undo()


def case_e4(tmp):
    w, undo, new, t = _good_update(tmp)
    try:
        sts = [au.crash_check(w.r.sh, now=t, path=w.sp)["status"],
               au.crash_check(w.r.sh, now=t + 240, path=w.sp)["status"],             # one real crash (a blip)
               _owner_start(w, t + 420, "Bot Control restart")["status"],
               _owner_start(w, t + 600, "a new supervisor (START BOT / reboot)")["status"]]
        W.check("E4. good update, ONE real crash + two owner restarts in the chain: never rolled back",
                "rolled_back" not in sts and w.r.head() == new and not w.pushes, sts)
    finally:
        undo()


def case_e5(tmp):
    w = W.World(tmp)
    undo = W.capture(w)
    try:
        bad = w.r.push({"engine/bot.py": "X = 8  # crash loop\n"}, "bad")
        w.check(W.Bot(), W.GOOD_T)
        told = []
        seq, t_end = W.crash_starts(w, [115] * 4, lambda *a, **k: told.append(a))
        rolled = seq[-1]["status"] == "rolled_back" and w.r.head() == w.good
        nxt = [au.crash_check(w.r.sh, now=t_end + 30 + 20 * i, path=w.sp)["status"] for i in range(5)]
        w.r.push({"tools/web_public/x.txt": "site only\n"}, "site on top of bad")
        h1 = w.check(W.Bot(), W.GOOD_T, now=W.SAT_19 + 3600)
        pl = au.pull(w.r.sh, branch="main", pip=False, state_path=w.sp)
        W.check("E5a. after the rollback: the old code's starts arm nothing; hourly + START BOT never re-take the bad SHA or "
                "site-only commits on top of it; one push only", rolled and set(nxt) == {"none"} and h1["status"] == "skipped"
                and pl["status"] == "skipped" and w.r.head() == w.good and len(told) == 1, (seq[-1], nxt, h1, pl))
        fix = w.r.push({"engine/bot.py": "X = 9  # the fix\n"}, "fix")
        h2 = w.check(W.Bot(), W.GOOD_T, now=W.SAT_19 + 7200)
        s = au.load_state(w.sp)
        W.check("E5b. a newer main with a bot-code fix is taken (one new guard on it, crash_sha dropped): no ping-pong",
                h2["status"] == "updated" and w.r.head() == fix and s["crash_guard"]["new"] == fix
                and not s.get("crash_sha") and bad != fix, (h2, s.get("crash_sha")))
    finally:
        undo()


def case_e6(tmp):
    w = W.World(tmp)
    undo = W.capture(w)
    try:
        w.r.push({"engine/bot.py": "X = 10\n"}, "new")
        res = w.check(W.Bot(position={"dir": 1, "qty": 2}), W.GOOD_T)
        W.check("E6a. position open: the hourly check skips, nothing fetched, moved or restarted",
                res["status"] == "skipped" and "flat" in res["reason"] and w.r.head() == w.good and not w.exits, res)
    finally:
        undo()
    w = W.World(tmp + "b")
    undo = W.capture(w)
    try:
        w.r.push({"engine/bot.py": "X = 11  # crash loop\n"}, "bad")
        w.check(W.Bot(), W.GOOD_T)
        seq, _ = W.crash_starts(w, [115] * 4, lambda *a, **k: None)
        W.check("E6b. the crash net's rollback leaves the autostart record (what resumes a position) as it was",
                seq[-1]["status"] == "rolled_back" and w.autostart_same(), seq[-1])
    finally:
        undo()


def main():
    base = tempfile.mkdtemp(prefix="le_rollback_rt_")
    try:
        for i, fn in enumerate((case_e1, case_e2, case_e3, case_e4, case_e5, case_e6)):
            try:
                fn(os.path.join(base, f"w{i}"))
            except Exception as e:  # noqa: BLE001
                import traceback
                traceback.print_exc()
                W.check(f"case {i} crashed: {e.__class__.__name__}: {e}", False)
    finally:
        shutil.rmtree(base, ignore_errors=True)
    ok = sum(RES)
    print(f"\nrollback red team: {'PASS' if ok == len(RES) else 'FAIL'} ({ok}/{len(RES)})")
    return ok == len(RES)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
