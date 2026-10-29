"""CME equity index futures (NQ / MNQ / ES) holiday calendar: one place for every strategy (Zlarior / LIT, ATLAS, BLITZ,
account B and any extra account) and every "is the market open" check. No heavy imports (the cloud monitor, the ops task
and the Start page use it too). All times are ET wall clock (America/New_York): DST never changes them.

  early_close(day)  ET minute at which the trading date `day` halts early (US holidays 13:00 ET = 12:00 CT; the day after
                    Thanksgiving and Christmas Eve 13:15 ET = 12:15 CT; July 3 13:15 when July 4 is a Tuesday-Friday; Good
                    Friday 09:15 ET when it trades at all), else None. Moved here from engine/lit_live.py (which re-exports
                    it, same values); 2026-10-29: Christmas Eve on the Friday when Christmas is a Saturday (2021, 2027) is a
                    full closure, not a 13:15 close.
  full_closure(day) no Globex session for that trading date: New Year's Day and Christmas Day, observed on the Monday when
                    they fall on a Sunday; Christmas observed on Friday Dec 24 when it is a Saturday (New Year's Day on a
                    Saturday is not moved: CME trades Friday Dec 31 in full, e.g. 2021-12-31).
  halted(ts)        CME is shut at `ts` for a holiday: anywhere in a full-closure trading date (18:00 ET the evening before
                    -> 17:00 ET), or between an early close's halt and 18:00 ET. The weekend / the daily 17:00-18:00 break
                    are not "halted" here (engine/live.market_open has those).
  entry_cut(day, flat_mod) / flat_cut(day, flat_mod)  the last entry minute (15 min before a halt) and the flat minute
                    (5 min before a halt) of a day, as the NinjaTrader adapter applies them (engine/ninjatrader._flat_today).

Source, checked 2026-10-29 (cmegroup.com is not reachable from the cloud session, so the dates are proven on the bars):
data/NQ_5m.csv (TradingView CME NQ1!) 2021-11 -> 2026-10: every Thanksgiving ends with the 12:55 bar (halt 13:00), every
day after Thanksgiving and every weekday Christmas Eve with the 13:10 bar (halt 13:15), MLK / Presidents / Memorial /
Juneteenth / July 4 / Labor Day with the 12:55 bar, New Year's Eve runs the full session (2021, 2024, 2025), and the
missing weekdays are exactly Christmas / New Year (observed Monday when on a Sunday), 2021-12-24 (Christmas on a Saturday)
and the Good Fridays without a jobs report (2022, 2024, 2025). CME lists its 2026 holiday schedules for 26-28 Nov and
24-26 Dec (search snippet of cmegroup.com/trading-hours.html); the exact hours are published about two weeks before each
holiday: re-check them then (tests/test_holidays.py prints the calendar this file gives).

The 2026-11 -> 2027-01 dates the bot meets: Thu 2026-11-26 halt 13:00, Fri 11-27 13:15, Thu 12-24 13:15, Fri 12-25 closed,
Thu 12-31 full day, Fri 2027-01-01 closed, Mon 2027-01-18 (MLK) 13:00, Mon 02-15 (Presidents) 13:00.
"""
from __future__ import annotations

import datetime as dt
from functools import lru_cache
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
ENTRY_BEFORE_HALT = 15          # minutes: no new entry within 15 min of an early close (LIT report ch.28)
FLAT_BEFORE_HALT = 5            # minutes: flat 5 min before the halt, so nothing is held into it


def _nth_weekday(y, m, wd, n):
    if n > 0:
        d = dt.date(y, m, 1)
        d += dt.timedelta(days=(wd - d.weekday()) % 7)
        return d + dt.timedelta(weeks=n - 1)
    d = dt.date(y, m + 1, 1) - dt.timedelta(days=1) if m < 12 else dt.date(y, 12, 31)
    return d - dt.timedelta(days=(d.weekday() - wd) % 7)


def _easter(y):
    a, b, c = y % 19, y // 100, y % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l_ = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l_) // 451
    month = (h + l_ - 7 * m + 114) // 31
    return dt.date(y, month, (h + l_ - 7 * m + 114) % 31 + 1)


def _date(day) -> dt.date:
    return day if isinstance(day, dt.date) else dt.date.fromisoformat(str(day)[:10])


@lru_cache(maxsize=4096)
def _full(d: dt.date) -> bool:
    for m, dd in ((1, 1), (12, 25)):
        h = dt.date(d.year, m, dd)
        if h.weekday() == 6:
            h += dt.timedelta(days=1)                  # Sunday -> observed Monday
        elif h.weekday() == 5 and m == 12:
            h -= dt.timedelta(days=1)                  # Christmas on a Saturday -> observed Friday Dec 24 (2021-12-24 closed)
        if d == h:
            return True
    return False


def full_closure(day) -> bool:
    """No CME Globex session for the trading date `day` (see the module doc)."""
    return _full(_date(day))


@lru_cache(maxsize=4096)
def _early(d: dt.date):
    if _full(d):
        return None
    y = d.year
    jul4 = dt.date(y, 7, 4)
    jul4 = jul4 + dt.timedelta(days=1) if jul4.weekday() == 6 else jul4 - dt.timedelta(days=1) if jul4.weekday() == 5 else jul4
    jun19 = dt.date(y, 6, 19)
    jun19 = jun19 + dt.timedelta(days=1) if jun19.weekday() == 6 else jun19 - dt.timedelta(days=1) if jun19.weekday() == 5 else jun19
    thanks = _nth_weekday(y, 11, 3, 4)
    hol = {_nth_weekday(y, 1, 0, 3), _nth_weekday(y, 2, 0, 3), _nth_weekday(y, 5, 0, -1), jun19, jul4, _nth_weekday(y, 9, 0, 1),
           thanks, thanks + dt.timedelta(days=1), dt.date(y, 12, 24)}
    if d == thanks + dt.timedelta(days=1) or d == dt.date(y, 12, 24):
        return 13 * 60 + 15
    # July 3 closes 12:15 CT = 13:15 ET when July 4 itself is a Tuesday-Friday (data/NQ_5m.csv: 2023-07-03, 2024-07-03,
    # 2025-07-03 end with the 13:10 bar); July 4 on a Saturday: July 3 is the observed holiday (13:00 below).
    if d == dt.date(y, 7, 3) and 1 <= dt.date(y, 7, 4).weekday() <= 4:
        return 13 * 60 + 15
    if d in hol:
        return 13 * 60
    if d == _easter(y) - dt.timedelta(days=2):
        return 9 * 60 + 15
    return None


def early_close(day) -> int | None:
    """ET minute at which CME equity futures halt early on this trading date, else None (see the module doc)."""
    return _early(_date(day))


def trading_date(ts) -> dt.date:
    """The CME trading date of unix time ts: 18:00 ET opens the next date."""
    return (dt.datetime.fromtimestamp(int(ts), ET) + dt.timedelta(hours=6)).date()


_HC: dict = {}                                         # UTC hour -> (full closure, halt time or None)


def halted(ts) -> bool:
    """CME is shut for a holiday at ts: a full-closure trading date, or past an early close's halt (until 18:00 ET).
    Cached per UTC hour (ET offsets are whole hours, so the ET hour and the trading date are fixed inside one): the bars'
    gap checks call this for every minute slot of a poll."""
    ts = int(ts)
    k = ts // 3600
    v = _HC.get(k)
    if v is None:
        e = dt.datetime.fromtimestamp(k * 3600, ET)
        td = (e + dt.timedelta(hours=6)).date()
        if _full(td):
            v = (True, None)
        elif e.hour >= 18:
            v = (False, None)                          # 18:00-24:00 belongs to the next date, which is not a full closure
        else:
            ec = _early(td)
            v = (False, int(dt.datetime.combine(td, dt.time(ec // 60, ec % 60), ET).timestamp()) if ec is not None else None)
        if len(_HC) > 100_000:
            _HC.clear()
        _HC[k] = v
    return v[0] or (v[1] is not None and ts >= v[1])


def entry_cut(day, flat_mod: int = 955) -> int:
    """Last minute (exclusive) a new entry may start on `day`: flat_mod, or 15 min before an early close."""
    ec = early_close(day)
    return flat_mod if ec is None else min(int(flat_mod), ec - ENTRY_BEFORE_HALT)


def flat_cut(day, flat_mod: int = 955) -> int:
    """Flat minute on `day`: flat_mod, or 5 min before an early close."""
    ec = early_close(day)
    return flat_mod if ec is None else min(int(flat_mod), ec - FLAT_BEFORE_HALT)


def flat_ts(day, flat_mod: int = 955) -> int:
    """Unix time of flat_cut(day) on that date."""
    d, m = _date(day), flat_cut(day, flat_mod)
    return int(dt.datetime.combine(d, dt.time(m // 60, m % 60), ET).timestamp())


def calendar(start, days: int = 60) -> list:
    """[{"day", "weekday", "kind": "closed" | "early", "halt": "HH:MM" | None}] for the weekdays from `start`."""
    d, out = _date(start), []
    for _ in range(int(days)):
        if d.weekday() < 5:
            if full_closure(d):
                out.append({"day": d.isoformat(), "weekday": d.strftime("%a"), "kind": "closed", "halt": None})
            else:
                ec = early_close(d)
                if ec is not None:
                    out.append({"day": d.isoformat(), "weekday": d.strftime("%a"), "kind": "early",
                                "halt": f"{ec // 60:02d}:{ec % 60:02d}"})
        d += dt.timedelta(days=1)
    return out


if __name__ == "__main__":
    import sys
    for r in calendar(sys.argv[1] if len(sys.argv) > 1 else dt.date.today().isoformat(), 120):
        print(f"{r['day']} {r['weekday']}  {'CLOSED' if r['kind'] == 'closed' else 'halt ' + r['halt'] + ' ET'}")
