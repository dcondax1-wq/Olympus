"""Thanksgiving week 2026 (night-tgweek 2026-11-23): Wed 11-25 a full day, Thu 11-26 a CME half day (halt 13:00 ET: NQ trades
02:00-12:55 on Thanksgiving, as data/NQ_5m.csv shows for 2023-2025; NOT closed), Fri 11-27 a half day (halt 13:15 ET).
The adapter-level replay of every routed lane (9: LIT, ATLAS, both Rapids' LIT + ATLAS lanes, an extra account, a fleet follower,
BLITZ) is tests/test_holiday_replay.py; this file: the calendar per day, the update / restart windows, and the owner's words.

    python -X utf8 -m tests.test_tgweek        (~3 s)
"""
from __future__ import annotations

import csv
import datetime as dt
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import autoupdate as au, cme_calendar as CC  # noqa: E402

ET = CC.ET
RES = []


def check(name, ok, info=""):
    print(f"{'ok  ' if ok else 'FAIL'} {name}{(': ' + str(info)[:400]) if info and not ok else ''}")
    RES.append(bool(ok))


def ts(y, m, d, hh, mm=0):
    return int(dt.datetime(y, m, d, hh, mm, tzinfo=ET).timestamp())


def main():
    W, T, F = "2026-11-25", "2026-11-26", "2026-11-27"
    L = {d: CC.route_limits(d) for d in (W, T, F)}
    check("calendar: Wed 11-25 full day (entries to 15:55 flat), Thu 11-26 halt 13:00 (no entry from 12:45, flat 12:55), "
          "Fri 11-27 halt 13:15 (no entry from 13:00, flat 13:10); none closed",
          L[W] == {"closed": False, "halt": None, "entry_cut": 955, "flat": 955}
          and L[T] == {"closed": False, "halt": 780, "entry_cut": 765, "flat": 775}
          and L[F] == {"closed": False, "halt": 795, "entry_cut": 780, "flat": 790}, L)
    seen = {}
    try:
        for r in csv.DictReader(open(os.path.join(ROOT, "data", "NQ_5m.csv"), encoding="utf-8")):
            x = dt.datetime.fromtimestamp(int(float(r["time"])), ET)
            k = x.date().isoformat()
            if k in ("2023-11-23", "2024-11-28", "2025-11-27") and 2 <= x.hour < 17:
                seen.setdefault(k, []).append(x.strftime("%H:%M"))
    except FileNotFoundError:
        seen = None
    check("the bars agree: Thanksgiving 2023 / 2024 / 2025 traded 02:00-12:55 ET (a half day, not a closure)",
          seen is None or all(v[0] == "02:00" and v[-1] == "12:55" for v in seen.values()) and len(seen) == 3,
          {k: (v[0], v[-1]) for k, v in (seen or {}).items()})

    def wr(day, hh, mm, mode, last_day=None):
        y, m, d = map(int, day.split("-"))
        return au.window_reason(ts(y, m, d, hh, mm), mode, last_day)
    check("auto-update: Thu / Fri no update or restart 01:50-16:00 ET (even after the 13:00 / 13:15 halt: the bot is flat, "
          "the window stays the safe default)", wr(T, 13, 30, "hourly") and wr(F, 14, 0, "hourly") and wr(F, 10, 0, "daily"))
    check("auto-update: Thu 16:30 hourly allowed (Friday's session opens 18:00, LIT trades from 02:00); Thu + Fri 17:02-17:50 daily "
          "allowed; Thu 18:30 hourly allowed; Fri 01:25 not (too close to 02:00)",
          wr(T, 16, 30, "hourly") is None and wr(T, 17, 10, "daily") is None and wr(F, 17, 10, "daily") is None
          and wr(T, 18, 30, "hourly") is None and wr(F, 1, 25, "hourly") is not None,
          [wr(T, 16, 30, "hourly"), wr(T, 17, 10, "daily"), wr(F, 17, 10, "daily"), wr(T, 18, 30, "hourly"), wr(F, 1, 25, "hourly")])
    check("the halt state: Thu 13:05 and Fri 13:20 are halted (no bars until 18:00), Thu 12:50 is not", CC.halted(ts(2026, 11, 26, 13, 5))
          and CC.halted(ts(2026, 11, 27, 13, 20)) and not CC.halted(ts(2026, 11, 26, 12, 50)))

    from tools import morning_brief as MB
    from engine import readiness as R
    fri = ts(2026, 11, 27, 8, 0)
    note, win = MB.early_note(fri), MB.windows_line(fri)
    check("brief Fri 11-27: 'half day, closes 13:15 ET (no new entry from 13:00)'; 'Zlarior till 13:00, ATLAS till 12:00'",
          note == "half day, closes 13:15 ET (no new entry from 13:00)" and "Zlarior till 13:00" in win, (note, win))
    check("brief Thu 11-26: 'half day, closes 13:00 ET (no new entry from 12:45)'; Wed 11-25: no note",
          MB.early_note(ts(2026, 11, 26, 8)) == "half day, closes 13:00 ET (no new entry from 12:45)" and MB.early_note(ts(2026, 11, 25, 8)) == "")
    lines = R.calendar_lines([dt.date(2026, 11, d) for d in (23, 24, 25, 26, 27)])
    check("the week's calendar line: 'Thu Nov 26 half day, closes 13:00 ET (no new entry from 12:45)', 'Fri Nov 27 half day, "
          "closes 13:15 ET (no new entry from 13:00)'", lines == ["Thu Nov 26 half day, closes 13:00 ET (no new entry from 12:45)",
                                                            "Fri Nov 27 half day, closes 13:15 ET (no new entry from 13:00)"], lines)
    js = open(os.path.join(ROOT, "tools", "web_public", "nq", "braincore.js"), encoding="utf-8").read()
    check("the phone's NQ Brain plan: 'Half day: closes 13:15 ET' (braincore.js, cache v7 through brain.js / brain.html)",
          "`Half day: closes ${str(brief.early_close, 80)} ET`" in js
          and "braincore.js?v=7" in open(os.path.join(ROOT, "tools", "web_public", "nq", "brain.js"), encoding="utf-8").read()
          and 'src="brain.js?v=7"' in open(os.path.join(ROOT, "tools", "web_public", "nq", "brain.html"), encoding="utf-8").read())
    from engine import live_board as LB
    nw = LB.next_windows(ts(2026, 11, 27, 8), [(120, 930)], n=1)
    check("the phone's next window Fri: 'Fri 02:00-13:00 ET', early_close 13:15", nw and nw[0]["label"] == "Fri 02:00-13:00 ET"
          and nw[0].get("early_close") == "13:15", nw)
    ok = sum(RES)
    print(f"\nthanksgiving week: {'PASS' if ok == len(RES) else 'FAIL'} ({ok}/{len(RES)})")
    return ok == len(RES)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
