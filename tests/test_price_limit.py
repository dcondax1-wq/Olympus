"""MFFU's 2% price-limit rule (engine/price_limit.py; help center 9698984, research/lit/mffu_rules.json price_limit_rule).

    python -X utf8 -m tests.test_price_limit          # ~20 s

  a. MFFU's own worked example: reference 18,556 -> stop above 19,483 / below 17,628
  b. the reference = the prior session's last regular-hours close before 16:00 ET (Monday -> Friday, never the evening session)
  c. real crash days on data/NQ_5m.csv (2026-11-05 -7.0%, 2025-04-04 -6.4%, 2024-08-05 -5.8%): blocked once NQ is 4.75% from
     the settlement, and for the rest of that session (sticky to 18:00 ET); normal days (2026-10-13, 2026-11-18, 2025-06-02)
     never; over every session 2021-2026 only the days that really moved >= 4.75% are ever blocked
  d. accounts: FUNDED only. A funded LIT lane (engine/multi_account) refuses entries; an eval lane does not. ATLAS's funded
     account (engine/account_b) and the Rapid's funded ATLAS refuse entries and flatten an open position ("PRICE LIMIT");
     their eval stage does not. Zlarior's own account: blocked only once funded. Unknown / stale reading = not blocked
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import pandas as pd  # noqa: E402

from engine import price_limit as PL  # noqa: E402

RESULTS = []


def check(name, cond, info=""):
    RESULTS.append((name, bool(cond)))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + ("" if cond else f"  -> {str(info)[:400]}"))


_D = {}


def bars():
    if "d" not in _D:
        _D["d"] = pd.read_csv(os.path.join(ROOT, "data", "NQ_5m.csv"))
    return _D["d"]


def window(day: str, back_days: int = 6):
    """5m bars from a few days before `day`'s session to its 17:00 ET end."""
    d = bars()
    end = PL._ts(pd.Timestamp(day).date(), 17)
    return d[(d.time >= end - back_days * 86400) & (d.time < end)]


def walk(day: str):
    """Poll every 5 min through `day`'s session like LiveBot: (first blocked time ET, blocked at the end, readings)."""
    PL.reset()
    w = window(day)
    so = PL.session_open(PL._ts(pd.Timestamp(day).date(), 12))
    first, last = None, None
    for t in range(so + 300, so + 23 * 3600 + 1, 300):
        sub = w[w.time + 300 <= t]
        if not len(sub):
            continue
        PL.update(sub, None, t)
        b = PL.blocked(t)
        if b and first is None:
            first = t
        last = b
    return first, last


def part_a():
    ref = 18556.0
    st = PL.status([0], [ref], 10 ** 6, 300, price=ref)       # reference() needs bars: check the levels directly
    up, dn = ref * (1 + PL.CME_LIMIT - PL.MFFU_BUFFER), ref * (1 - PL.CME_LIMIT + PL.MFFU_BUFFER)
    check("a. MFFU's example: 18,556 -> 19,483 / 17,628 (their figures, cut to whole points)", int(up) == 19483 and int(dn) == 17628, (up, dn))
    check("a. the bot stops at 4.75% (0.25% before MFFU's 5%)", abs(PL.TRIGGER - 0.0475) < 1e-12)
    check("a. no reference bar = unknown (not blocked)", st == {} or not st.get("hit"), st)


def part_b():
    d = bars()
    mon = PL._ts(pd.Timestamp("2026-11-16").date(), 10)         # a Monday 10:00 ET
    w = d[(d.time > mon - 6 * 86400) & (d.time < mon)]
    ref, ref_t = PL.reference(w.time.tolist(), w.close.tolist(), mon)
    e = PL._et(ref_t)
    fri = w[(w.time + 300 == ref_t)]
    check("b. Monday's reference = Friday's 15:55 bar close (ends 16:00 ET), not Sunday evening",
          e.strftime("%a %H:%M") == "Fri 16:00" and len(fri) == 1 and float(fri.close.iloc[0]) == ref, (e, ref))
    ev = PL._ts(pd.Timestamp("2026-11-17").date(), 20)          # Tue 20:00 ET = Wednesday's session
    w2 = d[(d.time > ev - 6 * 86400) & (d.time < ev)]
    _r, t2 = PL.reference(w2.time.tolist(), w2.close.tolist(), ev)
    check("b. the evening session's reference = that same day's 16:00 close", PL._et(t2).strftime("%Y-%m-%d %H:%M") == "2026-11-17 16:00",
          PL._et(t2))


def part_c():
    for day, mv in (("2026-11-05", -6.98), ("2025-04-04", -6.43), ("2024-08-05", -5.82)):
        first, last = walk(day)
        check(f"c. crash day {day} ({mv}% low): blocked, and still blocked at the session's end (sticky)",
              first is not None and bool(last), (first and PL._et(first), last))
        if first is not None:
            w = window(day)
            ref = PL._LAST.get("ref") or PL._STICKY[day]["ref"]
            before = w[(w.time + 300 <= first - 300) & (w.time >= PL.session_open(first))]
            far = ((before.close / ref - 1).abs() >= PL.TRIGGER).any() if len(before) else False
            check(f"c. {day}: not blocked before NQ reached 4.75% ({PL._et(first):%H:%M} ET)", not far)
    for day in ("2026-10-13", "2026-11-18", "2025-06-02"):
        first, _ = walk(day)
        check(f"c. normal day {day}: never blocked", first is None, first and PL._et(first))
    # every session: a block only on a day whose closes really moved >= 4.75% from the reference
    d = bars()
    d = d[d.time >= PL._ts(pd.Timestamp("2021-11-01").date(), 0)]
    et = pd.to_datetime(d.time, unit="s", utc=True).dt.tz_convert("America/New_York")
    td = (et + pd.Timedelta(hours=6)).dt.strftime("%Y-%m-%d")
    hits, wrong = [], []
    rth = d[(et.dt.hour >= 9) & (et.dt.hour < 16)]
    settle = rth.groupby(et[rth.index].dt.strftime("%Y-%m-%d")).close.last()
    cal = list(settle.index)
    import bisect
    for day, g in d.groupby(td):
        i = bisect.bisect_left(cal, day) - 1
        if i < 0:
            continue
        ref = float(settle.iloc[i])
        mv = float((g.close / ref - 1).abs().max())
        if mv >= PL.TRIGGER:
            hits.append(day)
    check(f"c. 2021-11 to 2026-11: {len(hits)} sessions reach 4.75% on a 5m close (rare: crash / squeeze days only)",
          3 <= len(hits) <= 20, hits)
    print("    sessions:", ", ".join(hits))
    for day in hits[-4:]:
        first, _ = walk(day)
        if first is None:
            wrong.append(day)
    check("c. the live reading blocks each of the 4 newest such sessions", not wrong, wrong)
    _D["hits"] = hits


def part_d():
    import json
    import tempfile
    import shutil
    from engine import multi_account as MA
    from tests.test_multi_rapid import make_bot, lanes
    from tests.test_rapid import Clock, DAY, T0
    tmp = tempfile.mkdtemp(prefix="price_limit_")
    try:
        PL.reset()
        b1 = {"account": "Sim205", "eval_start": DAY, "armed": False, "plan": "mffu_rapid_eod_25k", "stage": "funded",
              "funded_start": DAY, "payouts": {}}
        b2 = {"account": "Sim206", "eval_start": DAY, "armed": False, "plan": "mffu_rapid_eod_50k"}
        bot = make_bot(os.path.join(tmp, "bot"), Clock(T0), b1, b2)
        l1, l2 = lanes(bot)
        a1, a2 = bot.acct_r, bot.acct_r2
        check("d. set-up: the 25K is FUNDED, the 50K in its eval", l1.mode == "funded" and l2.mode != "funded" and a1.funded()
              and not a2.funded(), (l1.mode, l2.mode))
        check("d. no reading = nothing blocked", l1.price_limit_block(T0) is None and a1._price_limit(T0) is None)
        PL._STICKY[PL.trading_day(T0)] = {"pct": -0.051, "ref": 28566.25, "t": T0 - 600}
        check("d. funded LIT lane: entry refused (PRICE LIMIT)", "PRICE LIMIT" in str(l1.entry_block(T0)), l1.entry_block(T0))
        check("d. eval LIT lane: not affected (MFFU names funded accounts only)", "PRICE LIMIT" not in str(l2.entry_block(T0)),
              l2.entry_block(T0))
        check("d. funded ATLAS lane: blocked; eval ATLAS lane: not", bool(a1._price_limit(T0)) and a2._price_limit(T0) is None)
        g = a1.guard({"qty": 1, "side": "buy", "entry": 25000.0, "stop": 24990.0, "target": 25020.0, "entry_t": T0}, T0, T0)
        check("d. funded ATLAS guard names the rule", "PRICE LIMIT" in str(g), g)
        calls = []
        a1.open_t = T0 - 300
        a1.prov[T0 - 300] = {"dir": 1, "qty": 2, "key": "x"}
        a1.flatten = lambda et_, reason, sym, now, px=None: calls.append((et_, reason)) or True
        a1.tick(None, None, "NQ", T0)
        check("d. funded ATLAS holding a position: flattened with reason PRICE LIMIT", calls[:1] == [(T0 - 300, "PRICE LIMIT")], calls)
        calls2 = []
        a2.open_t = T0 - 300
        a2.prov[T0 - 300] = {"dir": 1, "qty": 2, "key": "x"}
        a2.flatten = lambda et_, reason, sym, now, px=None: calls2.append((et_, reason)) or True
        a2.tick(None, None, "NQ", T0)
        check("d. eval ATLAS holding a position: left alone", not any(r == "PRICE LIMIT" for _e, r in calls2), calls2)
        PL.reset()
        PL._LAST.update({"t": T0 - 1000, "hit": True, "pct": -0.05, "ref": 1.0})
        check("d. a stale reading (> 3 min) does not block", PL.blocked(T0) is None)
        PL.reset()
        PL._STICKY[PL.trading_day(T0)] = {"pct": -0.051, "ref": 28566.25, "t": T0 - 600}
        ent = {"dir": 1, "entry_t": T0, "entry": 25000.0, "stop": 24990.0, "target": 25020.0, "qty": 1}
        keep = bot._lit_sizing
        g0 = bot._guard_entry(ent, 1, "NQ", T0)
        bot._lit_sizing = {**keep, "mode": "funded"}
        g1 = bot._guard_entry(ent, 1, "NQ", T0)
        bot._lit_sizing = keep
        check("d. Zlarior's own account: eval not blocked, funded blocked", "PRICE LIMIT" not in str(g0) and "PRICE LIMIT" in str(g1),
              (g0, g1))
        check("d. the next trading day is free again", PL.blocked(T0 + 86400) is None)
        bot.stop()
    finally:
        PL.reset()
        MA.ADAPTER_FACTORY = None
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    part_a()
    part_b()
    part_c()
    part_d()
    n = sum(1 for _, ok in RESULTS if ok)
    print(f"\n{n}/{len(RESULTS)} passed")
    return 0 if n == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
