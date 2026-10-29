"""CME holiday / early-close calendar for every strategy (2026-10-29, engine/cme_calendar.py).

    python -X utf8 -m tests.test_holidays

 1. The calendar the bot meets next: Thu 2026-11-26 halt 13:00 ET, Fri 11-27 13:15, Thu 12-24 13:15, Fri 12-25 closed,
    Thu 12-31 full day, Fri 2027-01-01 closed, Mon 2027-01-18 (MLK) 13:00; and it equals the bars: every short session in
    data/NQ_5m.csv (2021-11 -> 2026-10) ends at the calendar's halt, every missing weekday is a calendar closure (Good
    Fridays without a jobs report are the known exception: the calendar keeps them as a 09:15 close, so a Good Friday that
    does trade is not blocked), New Year's Eve runs in full.
 2. lit_live.early_close / guards.full_closure are the same calendar (one source).
 3. Every strategy stops entering 15 min before an early close and is flat 5 min before it; no entry on a closed date:
    guards.calendar (LIT's and ATLAS / account B's route guard), the NinjaTrader adapter's entry gate (every account it
    routes: Zlarior, ATLAS, extra accounts, a BLITZ router) + its flat watch, account B's / the second strategies' own
    flat, the extra accounts' entry_block, the ATLAS paper session end, BLITZ route_limits, the board's next windows.
 4. Market-open checks know the holidays: no FEED STALE / gap alarms on Thanksgiving afternoon or Christmas Day
    (live / ops_checks / go market_open, pcbars.hist_gap over the Thanksgiving halt).
Temp dirs only.
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


def ts(y, m, d, hh, mm=0) -> int:
    return int(dt.datetime(y, m, d, hh, mm, tzinfo=ET).timestamp())


def t_calendar():
    print("1. the calendar", flush=True)
    from engine import cme_calendar as C
    cal = C.calendar("2026-10-29", 120)
    want = [("2026-11-26", "early", "13:00"), ("2026-11-27", "early", "13:15"), ("2026-12-24", "early", "13:15"),
            ("2026-12-25", "closed", None), ("2027-01-01", "closed", None), ("2027-01-18", "early", "13:00"),
            ("2027-02-15", "early", "13:00")]
    got = [(r["day"], r["kind"], r["halt"]) for r in cal]
    check("2026-10-29 + 120 days: Thanksgiving 13:00, Fri 11-27 13:15, Christmas Eve 13:15, Christmas closed, New Year's Day "
          "closed, MLK 13:00, Presidents 13:00 (New Year's Eve 12-31 not listed = full session)", got == want, got)
    check("Christmas on a Saturday (2027): Fri 2027-12-24 closed (as 2021-12-24), not a 13:15 close; New Year's Day 2028 on a "
          "Saturday: Fri 2027-12-31 trades in full (as 2021-12-31)",
          C.full_closure("2027-12-24") and C.early_close("2027-12-24") is None and not C.full_closure("2027-12-31")
          and C.early_close("2027-12-31") is None and C.full_closure("2021-12-24"))
    # against the bars
    import pandas as pd
    df = pd.read_csv(os.path.join(ROOT, "data", "NQ_5m.csv"), usecols=["time"])
    e = pd.to_datetime(df["time"], unit="s", utc=True).dt.tz_convert(ET)
    td = (e + pd.Timedelta(hours=6)).dt.date
    last = pd.Series(e.values, index=td.values).groupby(level=0).max()
    days = set(last.index)
    short, bad = [], []
    for d, x in last.items():
        x = pd.Timestamp(x).tz_localize("UTC").tz_convert(ET) if pd.Timestamp(x).tzinfo is None else pd.Timestamp(x).tz_convert(ET)
        end = x.hour * 60 + x.minute + 5                          # the last bar's close
        ec = C.early_close(d)
        if d == dt.date(2025, 1, 9):                              # National Day of Mourning (one-off 09:30 close, not a rule)
            continue
        if end < 17 * 60:
            short.append(d)
            if ec != end:
                bad.append((d.isoformat(), "short session", end, ec))
        elif ec is not None:
            bad.append((d.isoformat(), "full session but calendar early", ec))
    first, lastd = min(days), max(days)
    gf = set()
    d = first
    while d <= lastd:
        if d.weekday() < 5 and d not in days:
            if C.full_closure(d):
                pass
            elif d == C._easter(d.year) - dt.timedelta(days=2):
                gf.add(d.isoformat())                             # Good Friday without a jobs report: CME closed
            else:
                bad.append((d.isoformat(), "weekday without bars, not a calendar closure"))
        elif d in days and C.full_closure(d):
            bad.append((d.isoformat(), "calendar closure but the bars trade"))
        d += dt.timedelta(days=1)
    check(f"data/NQ_5m.csv {first} -> {lastd}: {len(short)} short sessions all end at the calendar's halt, every missing weekday "
          f"is a calendar closure (Good Fridays closed: {sorted(gf)}), no closure day has bars", not bad and len(short) >= 30, bad[:6])
    nye = [d for d in days if d.month == 12 and d.day == 31]
    check(f"New Year's Eve trades the full session in the data ({', '.join(sorted(x.isoformat() for x in nye))}) and in the calendar",
          len(nye) >= 3 and all(C.early_close(d) is None and not C.full_closure(d) for d in nye))


def t_one_source():
    print("2. one calendar", flush=True)
    from engine import cme_calendar as C, guards, lit_live
    d, bad = dt.date(2021, 1, 1), []
    while d < dt.date(2031, 1, 1):
        s = d.isoformat()
        if lit_live.early_close(s) != C.early_close(s) or guards.full_closure(s) != C.full_closure(s):
            bad.append(s)
        d += dt.timedelta(days=1)
    check("lit_live.early_close and guards.full_closure == engine/cme_calendar on every date 2021-2030", not bad, bad[:5])

    def ref(t):                                   # halted() without its per-hour cache
        e = dt.datetime.fromtimestamp(t, ET)
        td = (e + dt.timedelta(hours=6)).date()
        if C._full(td):
            return True
        m = e.hour * 60 + e.minute
        ec = C._early(td)
        return m < 1080 and ec is not None and m >= ec
    a, z = ts(2025, 1, 1, 0, 0), ts(2028, 1, 1, 0, 0)
    bad = [t for t in range(a, z, 300) if ref(t) != C.halted(t)]
    check("cme_calendar.halted (cached per UTC hour) == the plain rule on every 5 minutes 2025-2027 (both DST switches a year)",
          not bad, bad[:3])


def t_strategies(tmp):
    print("3. every strategy: entries stop 15 min before a halt, flat 5 min before; no entry on a closed date", flush=True)
    from engine import account_b, blitz, guards, live, live_board, multi_account, second
    from engine.ninjatrader import NinjaTraderAdapter
    # guards.calendar = LIT's route guard and account B's (ATLAS) guard (account_b.AccountB.guard)
    g = lambda *a: guards.calendar(ts(*a), ts(*a), session_from=120, flat_mod=955)   # noqa: E731
    ok = (not g(2026, 11, 26, 12, 44) and "early close" in " ".join(g(2026, 11, 26, 12, 45))
          and not g(2026, 11, 27, 12, 59) and g(2026, 11, 27, 13, 0) and not g(2026, 12, 24, 12, 59) and g(2026, 12, 24, 13, 0)
          and "holiday" in " ".join(g(2026, 12, 25, 10, 0)) and "holiday" in " ".join(g(2027, 1, 1, 10, 0))
          and not g(2026, 12, 31, 15, 54) and g(2027, 1, 18, 12, 45) and not g(2027, 1, 18, 12, 44) and not g(2026, 11, 25, 15, 54))
    check("calendar guard (LIT + ATLAS route): 11-26 12:44 ok / 12:45 refused, 11-27 + 12-24 12:59 ok / 13:00 refused, 12-25 and "
          "2027-01-01 refused (holiday), 12-31 15:54 ok, MLK 2027-01-18 12:44 ok / 12:45 refused", ok)
    # the NinjaTrader adapter: entry gate + flat watch (every account it routes)
    now = [0.0]
    folder = os.path.join(tmp, "NT")
    for s in ("incoming", "outgoing"):
        os.makedirs(os.path.join(folder, s), exist_ok=True)
    ad = NinjaTraderAdapter({"adapter": "ninjatrader", "sym": "NQ", "armed": True, "nt_folder": folder,
                             "params": {"max_micros": 40, "flat_mod": 955}, "model": "lit", "model_params": {"window": [[120, 930]]},
                             "nt_state_path": os.path.join(tmp, "nt.json"), "nt_audit_log": os.path.join(tmp, "oif.log")},
                            clock=lambda: now[0])

    def gate(*a):
        now[0] = ts(*a)
        return ad._gate("entry")
    ok = (gate(2026, 11, 26, 12, 44) is None and gate(2026, 11, 26, 12, 45) and gate(2026, 11, 27, 12, 59) is None
          and gate(2026, 11, 27, 13, 0) and "holiday" in gate(2026, 12, 25, 10, 0)["error"] and "holiday" in gate(2027, 1, 1, 10, 0)["error"]
          and gate(2026, 12, 31, 15, 54) is None and gate(2026, 12, 24, 12, 59) is None)
    check("NinjaTrader adapter entry gate (Zlarior, ATLAS, extra accounts, a BLITZ router): the same cut-offs, and a CME "
          "full-closure date (12-25, 2027-01-01) is refused by the adapter itself", ok)
    closed = []
    ad._close = lambda legs, why="": closed.append(why)
    ad._our_instruments = lambda: []
    seq = []
    for a in ((2026, 11, 26, 12, 54), (2026, 11, 26, 12, 55), (2026, 11, 27, 13, 9), (2026, 11, 27, 13, 10), (2026, 12, 24, 13, 10)):
        closed.clear()
        ad.legs = [{"status": "protected", "instrument": "MNQ 12-26", "entry_id": "x"}]
        ad._tick_flat_time(ts(*a))
        seq.append(bool(closed))
    ad.legs = []
    check("adapter flat watch: an open trade is flattened at 12:55 on 11-26 (not 12:54), 13:10 on 11-27 (not 13:09) and 12-24",
          seq == [False, True, False, True, True], seq)
    pv = lambda d: {"day": d}   # noqa: E731
    ok = (not account_b.AccountB._past_flat(None, pv("2026-11-26"), ts(2026, 11, 26, 12, 54))
          and account_b.AccountB._past_flat(None, pv("2026-11-26"), ts(2026, 11, 26, 12, 55))
          and account_b.AccountB._past_flat(None, pv("2026-11-27"), ts(2026, 11, 27, 13, 10))
          and not account_b.AccountB._past_flat(None, pv("2026-11-25"), ts(2026, 11, 25, 15, 54))
          and live.LiveBot._second_past_flat(None, pv("2026-12-24"), ts(2026, 12, 24, 13, 10))
          and not live.LiveBot._second_past_flat(None, pv("2026-12-24"), ts(2026, 12, 24, 13, 9)))
    check("account B (ATLAS) / second strategies route their own TIME exit with the adapter: 12:55 on 11-26, 13:10 on 11-27 / "
          "12-24, 15:55 on a normal day (was 15:55 always: B's ledger only learned of the adapter's flatten later)", ok)
    # extra accounts (multi_account): entry_block
    fake = types.SimpleNamespace(router=types.SimpleNamespace(killed=lambda: False), disabled_reason=lambda: None, lock=None,
                                 in_news=lambda now: None, mode="sim", entries_today=lambda d: 0)
    eb = lambda *a: multi_account.Account.entry_block(fake, ts(*a))   # noqa: E731
    ok = (eb(2026, 11, 26, 12, 44) is None and "early close" in (eb(2026, 11, 26, 12, 45) or "")
          and "holiday" in (eb(2026, 12, 25, 10, 0) or "") and eb(2026, 12, 31, 15, 0) is None and eb(2026, 11, 27, 12, 59) is None)
    check("extra accounts (multi_account entry_block): 11-26 12:45 refused (early close), 12-25 refused (holiday), 12-31 open", ok)
    # ATLAS paper (second.py): its session ends at the halt once the feed stopped there
    ok = (second._session_open("2026-11-26", ts(2026, 11, 26, 12, 50), ts(2026, 11, 26, 12, 50))
          and not second._session_open("2026-11-26", ts(2026, 11, 26, 13, 6), ts(2026, 11, 26, 13, 0)))
    check("ATLAS paper members: 11-26 open at 12:50, session over at 13:06 with the feed stopped at the 13:00 halt", ok)
    # BLITZ (paper Engine unchanged; route_limits for the router)
    r = {d: blitz.route_limits(d) for d in ("2026-11-26", "2026-11-27", "2026-12-24", "2026-12-25", "2026-12-31")}
    ok = (r["2026-11-26"] == {"closed": False, "halt": 780, "entry_cut": 765, "flat": 775}
          and r["2026-11-27"]["entry_cut"] == 780 and r["2026-11-27"]["flat"] == 790 and r["2026-12-24"]["flat"] == 790
          and r["2026-12-25"]["closed"] and r["2026-12-31"] == {"closed": False, "halt": None, "entry_cut": 955, "flat": 955})
    check("BLITZ route_limits: 11-26 entries to 12:45 / flat 12:55, 11-27 + 12-24 to 13:00 / 13:10, 12-25 closed, 12-31 normal "
          "(15:55); BLITZ's 12:30 check still trades on 11-26, its 13:00 / 13:30 checks on 11-27 do not", ok, r)
    w = live_board.next_windows(ts(2026, 11, 26, 0, 30), [[120, 930]], n=3)
    lab = [x["label"] for x in w]
    w2 = live_board.next_windows(ts(2026, 12, 24, 16, 0), [[120, 930]], n=1)
    check("board next windows: Thu 02:00-12:45, Fri 02:00-13:00, Mon 11-30; after Christmas Eve the next is Mon 12-28",
          lab[:2] == ["Thu 02:00-12:45 ET", "Fri 02:00-13:00 ET"] and w[2]["day"] == "2026-11-30" and w2 and w2[0]["day"] == "2026-12-28",
          (lab, w2))
    from engine import ops_checks as OC
    dd = [OC.due(ts(2026, 12, 25, 1, 45))["presession"], OC.due(ts(2026, 12, 25, 16, 10))["eod"], OC.due(ts(2027, 1, 1, 1, 45))["presession"],
          OC.due(ts(2026, 12, 24, 1, 45))["presession"], OC.due(ts(2026, 11, 26, 1, 45))["presession"], OC.due(ts(2026, 12, 27, 18, 0))["weekly"]]
    check("ops pushes: no pre-session check / day summary on Christmas and New Year's Day (no session); Christmas Eve and "
          "Thanksgiving keep theirs; the Sunday week report stays", dd == [False, False, False, True, True, True], dd)
    from engine import insight_api
    n1 = insight_api.next_window([[120, 930]], ts(2026, 11, 26, 12, 0))
    n2 = insight_api.next_window([[120, 930]], ts(2026, 12, 24, 14, 0))
    check("AI Insights next window: Thanksgiving 12:00 -> open, closes 12:45 (45 min); Christmas Eve 14:00 -> next opens Mon 12-28 "
          "02:00 (Christmas skipped)", n1["open"] and n1["end_hm"] == "12:45" and n1["closes_in_s"] == 2700
          and not n2["open"] and n2["start_day"] == "Mon Dec 28" and n2["start_hm"] == "02:00", (n1, n2))


def t_market_open():
    print("4. market-open checks know the holidays (no false FEED STALE / gap alarms)", flush=True)
    import pandas as pd
    from engine import go, live, ops_checks, pcbars
    cases = [((2026, 11, 26, 12, 59), True), ((2026, 11, 26, 13, 0), False), ((2026, 11, 26, 17, 59), False), ((2026, 11, 26, 18, 0), True),
             ((2026, 11, 27, 13, 14), True), ((2026, 11, 27, 13, 15), False), ((2026, 12, 24, 13, 15), False),
             ((2026, 12, 24, 18, 0), False), ((2026, 12, 25, 10, 0), False), ((2026, 12, 27, 18, 0), True),
             ((2026, 12, 31, 16, 0), True), ((2026, 12, 31, 18, 0), False), ((2027, 1, 1, 12, 0), False), ((2027, 1, 3, 18, 0), True),
             ((2026, 11, 25, 15, 0), True)]
    fns = {"live": live.market_open, "ops_checks": ops_checks.market_open,
           "go": lambda t: go.market_open(dt.datetime.fromtimestamp(t, ET))}
    bad = [(n, a, w) for n, f in fns.items() for a, w in cases if bool(f(ts(*a))) != w]
    check("market_open (live / ops_checks / go): shut from the 13:00 Thanksgiving halt to 18:00, from the Christmas Eve 13:15 "
          "halt to Sun 12-27 18:00, from Thu 12-31 17:00 to Sun 2027-01-03 18:00; open otherwise", not bad, bad)
    # a 1m archive ending at the 12:59 Thanksgiving bar and a fresh feed from 18:00: no hole
    hist = pd.DataFrame({"time": [ts(2026, 11, 26, 12, 58), ts(2026, 11, 26, 12, 59)]})
    fresh = pd.DataFrame({"time": [ts(2026, 11, 26, 18, 0), ts(2026, 11, 26, 18, 1)]})
    hole = pcbars.hist_gap(hist, fresh, 60)
    hist2 = pd.DataFrame({"time": [ts(2026, 11, 25, 12, 58), ts(2026, 11, 25, 12, 59)]})
    fresh2 = pd.DataFrame({"time": [ts(2026, 11, 25, 18, 0)]})
    hole2 = pcbars.hist_gap(hist2, fresh2, 60)
    check("pcbars.hist_gap: the Thanksgiving halt 13:00 -> 18:00 is not a hole in the bars (a normal Wednesday's 13:00 -> 17:00 is: "
          f"{hole2[2] if hole2 else None} missing minutes)", hole is None and hole2 is not None and hole2[2] == 240, (hole, hole2))


def main():
    tmp = tempfile.mkdtemp(prefix="le_hol_")
    try:
        t_calendar()
        t_one_source()
        t_strategies(tmp)
        t_market_open()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    n_ok = sum(ok for _, ok in RESULTS)
    print(f"\nholidays: {n_ok}/{len(RESULTS)} checks passed")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
