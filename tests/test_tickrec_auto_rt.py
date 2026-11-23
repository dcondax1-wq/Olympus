"""Red team on day-ofprogram d4d0c35 (2026-11-23): the tick autopilot never works into the bot's trading hours and never
counts a study that did not finish. Fakes only (no study run, no NinjaTrader).

    python -X utf8 -m tests.test_tickrec_auto_rt        (< 2 s)

1. start_window: no NEW job 01:40-16:05 ET on a weekday (a job started at 01:59 ran into 02:00); any time Sat / Sun.
2. seconds_left: until the next weekday 01:55 ET, capped at 6 h (the study's timeout = this - 5 min).
3. _run_study: a timeout / a non-zero exit / an OLD results.json = {} (FOUND: a killed study returned the previous results
   and used up one of the 2 looks); the autopilot then records nothing.
5. a live CSV more than 7 days old and already in data/ticks is deleted (today's kept); the live instrument list follows the
   front contract after the Dec roll (FOUND: written once at enable); nothing written while OFF.
4. the lock outlives the study (7 h; FOUND 3 h vs a 6 h study = two at once); pc_report's kick uses the same 01:40 / 7 h.
"""
from __future__ import annotations

import datetime as dt
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import tickrec as T  # noqa: E402

RES = []


def check(name, ok, info=""):
    print(f"{'ok  ' if ok else 'FAIL'} {name}{(': ' + str(info)[:300]) if info != '' and not ok else ''}")
    RES.append(bool(ok))


def et(*a):
    return dt.datetime(*a, tzinfo=T.ET)


def main():
    check("1. Mon 01:39 ET may start, 01:40 / 01:59 / 10:00 / 16:04 may not, 16:05 may",
          T.start_window(et(2026, 11, 23, 1, 39)) and not T.start_window(et(2026, 11, 23, 1, 40))
          and not T.start_window(et(2026, 11, 23, 1, 59)) and not T.start_window(et(2026, 11, 23, 10, 0))
          and not T.start_window(et(2026, 11, 23, 16, 4)) and T.start_window(et(2026, 11, 23, 16, 5)))
    check("1. Saturday 01:50 ET may start", T.start_window(et(2026, 11, 28, 1, 50)))
    check("2. Mon 23:55 ET -> 2 h left (Tue 01:55)", abs(T.seconds_left(et(2026, 11, 23, 23, 55)) - 7200) < 1, T.seconds_left(et(2026, 11, 23, 23, 55)))
    check("2. Fri 20:00 ET -> capped at 6 h (next 01:55 is Monday)", T.seconds_left(et(2026, 11, 27, 20, 0)) == 6 * 3600)
    check("2. Tue 01:00 ET -> 55 min", abs(T.seconds_left(et(2026, 11, 24, 1, 0)) - 3300) < 1)

    real_run = subprocess.run
    try:
        def boom(*a, **k):
            raise subprocess.TimeoutExpired(a[0], k.get("timeout"))
        subprocess.run = boom
        check("3. a study stopped by its timeout = {} (never the old results)", T._run_study(timeout=1) == {})
        subprocess.run = lambda *a, **k: subprocess.CompletedProcess(a[0], 1)
        check("3. a study that failed = {}", T._run_study(timeout=1) == {})
        subprocess.run = lambda *a, **k: subprocess.CompletedProcess(a[0], 0)
        rp = os.path.join(ROOT, "research", "orderflow", "results.json")
        old = (not os.path.exists(rp)) or os.path.getmtime(rp) < __import__("time").time()
        check("3. a clean exit that wrote no NEW results.json = {}", T._run_study(timeout=1) == {} if old else True)
    finally:
        subprocess.run = real_run

    keep = (T.TICK_DIR, T.CFG_PATH, T.AUTO_PATH, T.NOTE_PATH, os.environ.get("OLYMPUS_NT_DIR"))
    with tempfile.TemporaryDirectory() as tmp:
        T.TICK_DIR = os.path.join(tmp, "ticks")
        T.CFG_PATH = os.path.join(tmp, "data", "tickrec.json")
        T.AUTO_PATH = os.path.join(tmp, "data", "orderflow_auto.json")
        T.NOTE_PATH = os.path.join(tmp, "data", "orderflow_note.json")
        os.makedirs(os.path.join(tmp, "data"))
        nd = os.path.join(tmp, "NinjaTrader 8")
        os.makedirs(os.path.join(nd, "le_ticks"))
        os.environ["OLYMPUS_NT_DIR"] = nd
        T.set_enabled(True, ["NQ"])
        real_days = T.nq_days
        T.nq_days = lambda: ["2026-%02d-%02d" % (1 + i // 28, 1 + i % 28) for i in range(61)]
        try:
            r = T.autopilot(now=et(2026, 11, 24, 21, 0), study=lambda: {})
            check("3. the autopilot records NO look when the study returns nothing",
                  not r.get("ran") and not os.path.exists(T.AUTO_PATH) and not os.path.exists(T.NOTE_PATH), r)
            r2 = T.autopilot(now=et(2026, 11, 24, 1, 50), study=lambda: {"x": 1})
            check("1. the autopilot does not start at 01:50 ET on a weekday", not r2.get("ran") and "trading hours" in r2.get("why", ""), r2)
        finally:
            T.nq_days = real_days
            T.set_enabled(False)
    T.TICK_DIR, T.CFG_PATH, T.AUTO_PATH, T.NOTE_PATH = keep[:4]
    if keep[4] is None:
        os.environ.pop("OLYMPUS_NT_DIR", None)
    else:
        os.environ["OLYMPUS_NT_DIR"] = keep[4]
    with tempfile.TemporaryDirectory() as tmp:
        T.TICK_DIR = os.path.join(tmp, "ticks")
        T.CFG_PATH = os.path.join(tmp, "data", "tickrec.json")
        nd = os.path.join(tmp, "NinjaTrader 8")
        rd = os.path.join(nd, "le_ticks")
        os.makedirs(rd)
        os.environ["OLYMPUS_NT_DIR"] = nd
        old_f, new_f = os.path.join(rd, "NQ_2026-11-05.csv"), os.path.join(rd, "NQ_%s.csv" % T._et_today())
        for f, t in ((old_f, 1793871000000), (new_f, int(__import__("time").time() * 1000))):
            with open(f, "w") as fh:
                fh.write("t_ms,price,size,bid,ask\n%d,21000.25,1,21000,21000.25\n" % t)
        r = T.ingest(nd)
        check("5. a 18-day-old live CSV already ingested is deleted, today's is kept",
              "NQ_2026-11-05.csv" in r.get("removed_raw", []) and not os.path.exists(old_f) and os.path.exists(new_f), r)
        check("5. OFF: the instrument list is never written",
              not T.refresh_instruments(nd, dt.date(2026, 12, 15)) and not os.path.exists(os.path.join(rd, "instruments.txt")))
        T.set_enabled(True, ["NQ", "ES"])
        open(os.path.join(rd, "instruments.txt"), "w").write("NQ 12-26\nES 12-26\n")
        ok_roll = T.refresh_instruments(nd, dt.date(2026, 12, 15))
        lst = open(os.path.join(rd, "instruments.txt")).read().split("\n")
        check("5. recording after the Dec roll: the live list moves to 03-27", ok_roll and lst[:2] == ["NQ 03-27", "ES 03-27"], lst)
        T.set_enabled(False)
    T.TICK_DIR, T.CFG_PATH = keep[0], keep[1]
    if keep[4] is None:
        os.environ.pop("OLYMPUS_NT_DIR", None)
    else:
        os.environ["OLYMPUS_NT_DIR"] = keep[4]
    pr = open(os.path.join(ROOT, "tools", "pc_report.py"), encoding="utf-8").read()
    check("4. lock 7 h in tickrec and pc_report; pc_report's kick stops at 01:40 ET",
          T.LOCK_STALE_S == 7 * 3600 and "< 7 * 3600" in pr and "100 <= m < 16 * 60 + 5" in pr)
    ok = sum(RES)
    print(f"\ntick autopilot red team: {'PASS' if ok == len(RES) else 'FAIL'} ({ok}/{len(RES)})")
    return ok == len(RES)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
