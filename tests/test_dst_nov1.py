"""Sunday 2026-11-01 (the first day of EST: clocks went back at 02:00) and Monday 2026-11-02, focused and fast. Every
trading-day helper the bots and the cloud use is FOUND by a scan of the code (tests/test_dst.py checks a fixed list of 25;
the scan finds the ones added since, e.g. account_c, mind, structure, trade_chart, the cloud monitor's own tday), then
walked minute by minute on epoch seconds from Sun 00:00 EDT (the doubled 01:00 ET hour walked twice) to Mon 19:30 EST,
with Monday's windows on their exact UTC instants. tests/test_dst.py (three switches) and tests/test_dst_sunday.py (the
days themselves with the real server, ~10 min) stay the full checks.

    python -X utf8 -m tests.test_dst_nov1          # seconds

 1. Discovery: every top-level trading_day / _trading_day / tday / trading_date / session_day of engine/*.py and of the
    cloud workflow's tools (cloud_monitor, lit_watch, recap, build_web_dashboard, news_hub) that takes a time; the
    minute-of-day helpers (lit_live.tday, ninjatrader._tday: argument `mod`) are left out.
 2. Each helper == cme_calendar.trading_date on every minute (the weekday helpers insight_api.trading_day and
    go.session_day roll a weekend date to Monday): Sunday up to 17:59 EST keeps Sunday's date, 18:00 EST = 23:00 UTC opens
    2026-11-02, Monday 18:00 EST = 23:00 UTC opens 2026-11-03.
 3. market_open (live, go, dash_market): shut until Sun 18:00 EST = 23:00 UTC, open all Monday's session, the 17:00-18:00
    EST halt = 22:00-23:00 UTC, open again from Mon 18:00 EST.
 4. Monday 2026-11-02 on the right UTC instants: no CME holiday or early close; the route guard (guards.calendar with
    live_model.json's LIT window start and flat) refuses Sunday 18:00-23:55 EST (before the 02:00 start), allows 02:00 EST =
    07:00 UTC .. 15:54, refuses 15:55 EST = 20:55 UTC (cme_calendar.flat_ts); lit_live's session is over at 17:00 EST =
    22:00 UTC, not a minute before; LIT's entry window 02:00-15:30 ET = 07:00-20:30 UTC.
 5. The PC's Sunday schedules (engine/pc_health): the self-test window opens 15:30 EST = 20:30 UTC, the readiness push
    17:30 EST = 22:30 UTC, on Sunday only (not on Monday at the same ET minutes).
Pure functions: nothing is written.
"""
from __future__ import annotations

import datetime as dt
import importlib
import json
import os
import re
import sys
import warnings
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

ET = ZoneInfo("America/New_York")
UTC = dt.timezone.utc
RESULTS = []
SUN, MON = dt.date(2026, 11, 1), dt.date(2026, 11, 2)
CLOUD_TOOLS = ("cloud_monitor", "lit_watch", "recap", "build_web_dashboard", "news_hub")
WEEKDAY = {"engine.insight_api.trading_day", "engine.go.session_day"}      # a weekend date rolls to Monday
NAMES = re.compile(r"^def (trading_day|_trading_day|tday|trading_date|session_day)\((\w*)", re.M)


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok)))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + ("" if ok else f"  -> {str(detail)[:700]}"), flush=True)


def ts(d: dt.date, hh: int, mm: int = 0) -> int:
    return int(dt.datetime(d.year, d.month, d.day, hh, mm, tzinfo=ET).timestamp())


def utc_hm(t: int) -> str:
    return dt.datetime.fromtimestamp(t, UTC).strftime("%a %H:%M UTC")


def et_hm(t: int) -> str:
    return dt.datetime.fromtimestamp(t, ET).strftime("%a %H:%M %Z")


# ------------------------------------------------------------------------------------------------ 1. discovery
def discover() -> dict:
    srcs = [("engine." + f[:-3], os.path.join(ROOT, "engine", f)) for f in sorted(os.listdir(os.path.join(ROOT, "engine")))
            if f.endswith(".py")]
    srcs += [("tools." + n, os.path.join(ROOT, "tools", n + ".py")) for n in CLOUD_TOOLS
             if os.path.exists(os.path.join(ROOT, "tools", n + ".py"))]
    found, failed = {}, []
    for mod, path in srcs:
        text = open(path, encoding="utf-8", errors="replace").read()
        hits = [(fn, arg) for fn, arg in NAMES.findall(text) if arg != "mod"]
        if not hits:
            continue
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                m = importlib.import_module(mod)
        except Exception as e:
            failed.append(f"{mod}: {e.__class__.__name__}: {e}")
            continue
        for fn, _ in hits:
            f = getattr(m, fn, None)
            if callable(f):
                found[f"{mod}.{fn}"] = f
    return found, failed


def call(name, f, t):
    if name == "engine.go.session_day":
        return str(f(dt.datetime.fromtimestamp(t, ET)))
    return str(f(t))


# ------------------------------------------------------------------------------------------------ 2. trading days
def t_trading_days(found):
    print("2. every trading-day helper, minute by minute Sun 00:00 EDT -> Mon 19:30 EST", flush=True)
    from engine import cme_calendar
    t0, t1 = ts(SUN, 0, 0), ts(MON, 19, 30)
    bad, n = {}, 0
    for t in range(t0, t1 + 1, 60):
        n += 1
        d = cme_calendar.trading_date(t)
        wd = d
        while wd.weekday() >= 5:
            wd += dt.timedelta(days=1)
        for name, f in found.items():
            want = (wd if name in WEEKDAY else d).isoformat()
            try:
                got = call(name, f, t)
            except Exception as e:
                got = f"{e.__class__.__name__}: {e}"
            if got != want:
                bad.setdefault(name, []).append((et_hm(t), got, want))
    check(f"{len(found)} helpers x {n:,} minutes (the doubled 01:00 ET hour twice): each == cme_calendar.trading_date "
          "(weekday helpers: Monday for the weekend)", not bad, {k: v[:2] for k, v in list(bad.items())[:4]})
    flips = [t for t in range(t0 + 60, t1 + 1, 60)
             if cme_calendar.trading_date(t) != cme_calendar.trading_date(t - 60)]
    check(f"the trading date changes exactly twice: {', '.join(f'{et_hm(t)} = {utc_hm(t)}' for t in flips)}",
          flips == [ts(SUN, 18, 0), ts(MON, 18, 0)] and all(dt.datetime.fromtimestamp(t, UTC).hour == 23 for t in flips),
          [et_hm(t) for t in flips])
    doubled = [t for t in range(t0, ts(SUN, 3, 0), 60) if dt.datetime.fromtimestamp(t, ET).hour == 1]
    check(f"the 01:00 ET hour on Sunday is {len(doubled)} minutes long (EDT then EST)", len(doubled) == 120, len(doubled))


# ------------------------------------------------------------------------------------------------ 3. market open
def t_market_open():
    print("3. market_open: Sunday open, Monday halt", flush=True)
    from engine import dash_market, go, live
    t0, t1 = ts(SUN, 0, 0), ts(MON, 19, 30)
    rows, bad = [], []
    for t in range(t0, t1 + 1, 60):
        a, b, c = live.market_open(t), go.market_open(dt.datetime.fromtimestamp(t, ET)), dash_market.market_open(t)
        if not a == b == c:
            bad.append((et_hm(t), a, b, c))
        rows.append((t, a))
    check("live / go / dash_market agree on every minute", not bad, bad[:4])
    changes = [(t, o) for (t, o), (_, p) in zip(rows[1:], rows[:-1]) if o != p]
    want = [(ts(SUN, 18, 0), True), (ts(MON, 17, 0), False), (ts(MON, 18, 0), True)]
    check("open at Sun 18:00 EST = Sun 23:00 UTC, halt Mon 17:00-18:00 EST = 22:00-23:00 UTC, open again Mon 18:00 EST: "
          + "; ".join(f"{'open' if o else 'shut'} {et_hm(t)} = {utc_hm(t)}" for t, o in changes),
          changes == want and not rows[0][1], [(et_hm(t), o) for t, o in changes])


# ------------------------------------------------------------------------------------------------ 4. Monday's windows
def t_monday():
    print("4. Monday 2026-11-02 on the right UTC instants", flush=True)
    from engine import cme_calendar, guards, lit_live
    lm = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))
    P = lm.get("lit") or {}
    win = P.get("window") or [[120, 930]]
    start, end, flat = int(win[0][0]), int(win[-1][1]), int(P.get("flat_mod") or 955)
    check("Mon 2026-11-02: no CME full closure, no early close; flat 15:55 EST = 20:55 UTC",
          not cme_calendar._full(MON) and cme_calendar.early_close(MON.isoformat()) is None
          and cme_calendar.flat_ts(MON.isoformat(), flat) == ts(MON, flat // 60, flat % 60)
          and dt.datetime.fromtimestamp(cme_calendar.flat_ts(MON.isoformat(), flat), UTC).strftime("%H:%M") == "20:55",
          (cme_calendar.early_close(MON.isoformat()), utc_hm(cme_calendar.flat_ts(MON.isoformat(), flat))))
    g = lambda t: guards.calendar(t, t, session_from=start, flat_mod=flat)       # noqa: E731
    sun_eve = [t for t in range(ts(SUN, 18, 0), ts(MON, 0, 0), 300) if not g(t)]
    sun_aft = [t for t in range(ts(SUN, 16, 0), ts(SUN, 18, 0), 300) if not g(t)]
    check("route guard: Sun 16:00-17:55 EST refused (market shut), Sun 18:00-23:55 EST refused (before the 02:00 start)",
          not sun_eve and not sun_aft, [et_hm(t) for t in sun_aft + sun_eve][:4])
    mon = {hm: g(ts(MON, *hm)) for hm in ((1, 59), (2, 0), (9, 30), (15, 54), (15, 55), (17, 0))}
    check(f"route guard Monday: 01:59 EST refused, 02:00 EST ({utc_hm(ts(MON, 2, 0))}) .. 15:54 allowed, 15:55 EST "
          f"({utc_hm(ts(MON, 15, 55))}) refused, 17:00 shut",
          bool(mon[(1, 59)]) and not mon[(2, 0)] and not mon[(9, 30)] and not mon[(15, 54)] and bool(mon[(15, 55)])
          and bool(mon[(17, 0)]) and dt.datetime.fromtimestamp(ts(MON, 2, 0), UTC).hour == 7, mon)
    check(f"LIT's entry window {start // 60:02d}:{start % 60:02d}-{end // 60:02d}:{end % 60:02d} ET = "
          f"{utc_hm(ts(MON, start // 60, start % 60))} - {utc_hm(ts(MON, end // 60, end % 60))} on Monday",
          (start, end) == (120, 930) and dt.datetime.fromtimestamp(ts(MON, 2, 0), UTC).strftime("%H:%M") == "07:00"
          and dt.datetime.fromtimestamp(ts(MON, 15, 30), UTC).strftime("%H:%M") == "20:30", win)
    over = [lit_live._session_over(MON.isoformat(), t) for t in (ts(MON, 16, 59), ts(MON, 17, 0))]
    check(f"lit_live: Monday's session not over at 16:59 EST, over at 17:00 EST ({utc_hm(ts(MON, 17, 0))})",
          over == [False, True], over)
    ws = lit_live.window_start(ts(MON, 2, 0))
    check(f"lit_live.window_start for Monday = {et_hm(ws)} (18:00 ET, the first trading day of the previous month - a week)",
          dt.datetime.fromtimestamp(ws, ET).strftime("%H:%M") == "18:00", et_hm(ws))


# ------------------------------------------------------------------------------------------------ 5. Sunday schedules
def t_schedules():
    print("5. the PC's Sunday self-test and readiness push", flush=True)
    from engine import pc_health as H
    st = [H.in_window(ts(SUN, hh, mm), 6, H.SUNDAY_TEST) for hh, mm in ((14, 30), (15, 29), (15, 30), (17, 44), (17, 45))]
    check(f"self-test window: opens Sun 15:30 EST = {utc_hm(ts(SUN, 15, 30))}, not at 14:30 EST (= 15:30 EDT), until 17:45",
          st == [False, False, True, True, False], st)
    rd = [H.in_window(ts(SUN, hh, mm), 6, H.SUNDAY_READY) for hh, mm in ((16, 30), (17, 29), (17, 30), (18, 29), (18, 30))]
    check(f"readiness push window: opens Sun 17:30 EST = {utc_hm(ts(SUN, 17, 30))}, not at 16:30 EST (= 17:30 EDT)",
          rd == [False, False, True, True, False], rd)
    mon = [H.in_window(ts(MON, 15, 30), 6, H.SUNDAY_TEST), H.in_window(ts(MON, 17, 30), 6, H.SUNDAY_READY)]
    check("neither fires on Monday at the same ET minutes", mon == [False, False], mon)


def main():
    print("1. discovery", flush=True)
    found, failed = discover()
    names = sorted(found)
    check(f"{len(names)} trading-day helpers found (engine + cloud tools), every module imported", len(names) >= 30 and not failed,
          failed or names)
    must = {"engine.live.trading_day", "engine.lit_live.trading_date", "engine.cme_calendar.trading_date",
            "engine.guards.trading_day", "engine.ninjatrader._trading_day", "engine.account_c.trading_day",
            "tools.cloud_monitor.tday", "engine.go.session_day"}
    check("the live loop's own helpers are among them (PC bot, LIT, guards, NinjaTrader, BLITZ, cloud monitor, go)",
          must <= set(names), sorted(must - set(names)))
    t_trading_days(found)
    t_market_open()
    t_monday()
    t_schedules()
    n_ok = sum(ok for _, ok in RESULTS)
    print(f"\nDST Nov 1: {n_ok}/{len(RESULTS)} checks passed")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
