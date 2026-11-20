"""Red team 2 (2026-11-20, day-redteam2): what could cost money in the next 10 trading days (Thanksgiving week, Christmas,
New Year; restarts mid-trade; a 4th account added live; MFFU rules). Temp dirs only, a fake clock, never the owner's phone.

    python -X utf8 -m tests.test_redteam2_live

h. half-day halt with a broker position open (engine/fast_alarm.halt_open): MFFU does not auto-close at a CME half-day
   halt; a stopped / crashed bot leaves the trade open into it = the account fails. The phone must ring before the halt.
"""
from __future__ import annotations

import datetime as dt
import os
import shutil
import sys
import tempfile
import types
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

ET = ZoneInfo("America/New_York")
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok)))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + ("" if ok else f"  -> {str(detail)[:700]}"), flush=True)


def ts(y, m, d, hh, mm=0, ss=0) -> int:
    return int(dt.datetime(y, m, d, hh, mm, ss, tzinfo=ET).timestamp())


def _pos(folder, inst, acct, text):
    og = os.path.join(folder, "outgoing")
    os.makedirs(og, exist_ok=True)
    with open(os.path.join(og, f"{inst}_{acct}_Position.txt"), "w", encoding="utf-8") as fh:
        fh.write(text)


def t_halt(tmp):
    print("h. a broker position open into a CME half-day halt", flush=True)
    from engine import fast_alarm as FA
    folder = os.path.join(tmp, "NT")
    stopped = types.SimpleNamespace(running=False, cfg={"adapter": "ninjatrader", "nt_folder": folder})
    running = types.SimpleNamespace(running=True, cfg={"adapter": "ninjatrader", "nt_folder": folder}, started_at=0,
                                    health={"last_ok_poll": 0}, thread=None)
    _pos(folder, "MNQ 12-26 Globex", "MFFUEVLB25K9991234", "SHORT;2;20950.25")
    _pos(folder, "MNQ 12-26 Globex", "Sim101", "LONG;1;20950.25")
    halt = getattr(FA, "halt_open", None)
    ev = lambda b, t: FA.evaluate(b, t, server_started_at=t - 3600, autostart=None)
    thx_1252 = ev(stopped, ts(2026, 11, 26, 12, 52))
    check("Thanksgiving 12:52 ET, bot STOPPED, ATLAS short open on the real account -> 'halt_open' alarm (MFFU does not "
          "close it at the 13:00 half-day halt)", "halt_open" in thx_1252, thx_1252)
    check("the alarm text names the halt, the position (account id cut to 4) and says close it by hand",
          "13:00" in str(thx_1252.get("halt_open")) and "..1234" in str(thx_1252.get("halt_open"))
          and "9991234" not in str(thx_1252.get("halt_open")).replace("..1234", ""), thx_1252)
    check("Thanksgiving 12:52, bot RUNNING (it flattens at 12:55 itself) -> no alarm yet",
          "halt_open" not in ev(running, ts(2026, 11, 26, 12, 52)))
    check("Thanksgiving 12:56, bot running, still open after its own 12:55 flat -> alarm",
          "halt_open" in ev(running, ts(2026, 11, 26, 12, 56)))
    check("Fri 11-27 13:06 and Christmas Eve 12-24 13:06 (halt 13:15), bot stopped -> alarm",
          "halt_open" in ev(stopped, ts(2026, 11, 27, 13, 6)) and "halt_open" in ev(stopped, ts(2026, 12, 24, 13, 6)))
    check("a normal Friday 12:52 / Thanksgiving 12:30 (too early) / 13:01 (halt passed) -> no alarm",
          not any("halt_open" in ev(stopped, t) for t in (ts(2026, 11, 20, 12, 52), ts(2026, 11, 26, 12, 30),
                                                          ts(2026, 11, 26, 13, 1))))
    _pos(folder, "MNQ 12-26 Globex", "MFFUEVLB25K9991234", "FLAT;0;0")
    check("flat on the real account (only the Sim101 position open) -> no alarm",
          "halt_open" not in ev(stopped, ts(2026, 11, 26, 12, 52)))
    # the push goes out even when the day's 6-alarm cap is used up, and no 'back to normal' after the halt itself
    _pos(folder, "MNQ 12-26 Globex", "MFFUEVLB25K9991234", "SHORT;2;20950.25")
    sent = []
    fa = FA.FastAlarm(send=lambda p: (sent.append(p), "sent")[1], clock=lambda: 0)
    day = dt.date(2026, 11, 26).isoformat()
    fa.day_n = {day: FA.DAY_MAX}
    fa.step(stopped, now=ts(2026, 11, 26, 12, 51))
    fa.step(stopped, now=ts(2026, 11, 26, 13, 0, 30))
    check("FastAlarm pushes 'CLOSE THE TRADE NOW' although 6 alarms went out today; no 'Back to normal' when the halt passes",
          [p.get("code") for p in sent] == ["halt_open"] and sent[0].get("title") == "CLOSE THE TRADE NOW", sent)
    sent.clear()
    fa2 = FA.FastAlarm(send=lambda p: (sent.append(p), "sent")[1], clock=lambda: 0)
    fa2.step(stopped, now=ts(2026, 11, 26, 12, 51))
    _pos(folder, "MNQ 12-26 Globex", "MFFUEVLB25K9991234", "FLAT;0;0")
    fa2.step(stopped, now=ts(2026, 11, 26, 12, 53))
    check("closed by hand at 12:53 -> one 'Back to normal: flat before the halt'",
          len(sent) == 2 and sent[1].get("back") and "flat" in sent[1].get("body", ""), sent)
    _pos(folder, "MNQ 12-26 Globex", "MFFUEVLB25K9991234", "SHORT;2;20950.25")
    import time as _t
    t0 = _t.perf_counter()
    for _ in range(200):
        ev(running, ts(2026, 11, 20, 10, 0))
    check("outside the 10 halt minutes the check reads no file (200 evaluations of a normal 10:00 < 50 ms)",
          _t.perf_counter() - t0 < 0.05, _t.perf_counter() - t0)


def main():
    tmp = tempfile.mkdtemp(prefix="rt2_")
    try:
        for t in (t_halt,):
            try:
                t(tmp)
            except Exception as e:  # noqa: BLE001
                import traceback
                traceback.print_exc()
                check(f"{t.__name__} ran", False, e)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    n = sum(ok for _, ok in RESULTS)
    print(f"\nredteam2 live: {n}/{len(RESULTS)} checks passed")
    return 0 if n == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
