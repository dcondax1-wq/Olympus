"""night-of-monfix 2026-11-27: lane A's 'previous day' is the last file WITH a regular session (RTH 09:30-16:00 ET), and a
Globex-only file in between (the Sunday evening before a Monday, thin or not) joins the overnight range. Before: a Monday's
previous day was the Sunday file (no pdh / pdl on 7 of 9 Mondays), or, with a thin Sunday, Friday without Sunday 18:00-24:00.
Synthetic day files only (research/orderflow/of_battery.levels, engine/of_paper._prev_summary + step). Paper only.

    python -X utf8 -m tests.test_of_monfix
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import tempfile
from zoneinfo import ZoneInfo

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import of_paper as P  # noqa: E402

ET = ZoneInfo("America/New_York")
FRI, SUN, MON, TUE = "2030-03-01", "2030-03-03", "2030-03-04", "2030-03-05"
FAILS = []


def check(name, ok):
    print(("ok   " if ok else "FAIL ") + name)
    if not ok:
        FAILS.append(name)


def summary(day, spans, base=100.0, peaks=()):
    """5m bars over the ET (hh:mm, hh:mm) spans at a flat price `base`; peaks = [(hh:mm, high, low)] override one bar."""
    pk = {p[0]: p for p in peaks}
    rows = []
    d0 = dt.date.fromisoformat(day)
    for a, b in spans:
        t = dt.datetime.combine(d0, dt.time(*map(int, a.split(":"))), ET)
        end = dt.datetime.combine(d0, dt.time(*map(int, b.split(":"))), ET)
        while t < end:
            hm = t.strftime("%H:%M")
            h, l = (pk[hm][1], pk[hm][2]) if hm in pk else (base + 1, base - 1)
            rows.append({"t": int(t.timestamp()), "o": base, "h": h, "l": l, "c": base, "vol": 100, "buy": 50, "sell": 50,
                         "unk": 0, "n": 50, "b10": 0, "b20": 0, "b50": 0, "bth": 0, "sac": 0.3, "sruns": 0.3})
            t += dt.timedelta(minutes=5)
    bars = pd.DataFrame(rows)
    fp = pd.DataFrame({"bar": list(range(len(bars))), "k": [0] * len(bars), "b": [1] * len(bars), "a": [1] * len(bars), "u": [0] * len(bars)})
    return {"bars": bars, "fp": fp, "meta": {"v": 1, "day": day, "rows": 60000 if len(bars) > 60 else 9000}, "depth": None}


def files():
    fri = summary(FRI, [("00:00", "17:00")], peaks=[("11:00", 120.0, 99.0), ("13:00", 101.0, 80.0), ("16:30", 130.0, 99.0)])
    sun = summary(SUN, [("18:00", "23:55")], peaks=[("20:00", 125.0, 99.0)])
    mon = summary(MON, [("00:00", "17:00"), ("18:00", "23:55")],
                  peaks=[("03:00", 101.0, 90.0), ("11:00", 111.0, 99.0), ("12:00", 101.0, 88.0), ("16:30", 140.0, 99.0), ("19:00", 112.0, 99.0)])
    tue = summary(TUE, [("00:00", "17:00")], peaks=[("04:00", 101.0, 94.0)])
    return {FRI: fri, SUN: sun, MON: mon, TUE: tue}


def lv(L):
    return {n: p for n, p, _ in L}


def main() -> int:
    B, _, _ = P._mods()
    F = files()
    D = {d: B.Day(d, R) for d, R in F.items()}
    check("has_rth: Friday yes, Sunday evening no", B.has_rth(D[FRI]) and not B.has_rth(D[SUN]))

    # (a) Monday after a kept Sunday file (in the day list)
    L = lv(B.levels(D, [FRI, SUN, MON], 2))
    check("Monday after Sunday: pdh / pdl are Friday's RTH (120 / 80)", L.get("pdh") == 120.0 and L.get("pdl") == 80.0)
    check("Monday after Sunday: Friday 16:30 (after the close, before 18:00) is not overnight", L.get("onh") != 130.0)
    check("Monday after Sunday: onh = Sunday evening's 125, onl = Monday 03:00's 90", L.get("onh") == 125.0 and L.get("onl") == 90.0)

    # (b) Monday after a THIN Sunday (dropped from the day list but in D)
    L = lv(B.levels(D, [FRI, MON], 1))
    check("thin Sunday: still Friday's pdh / pdl", L.get("pdh") == 120.0 and L.get("pdl") == 80.0)
    check("thin Sunday: its 18:00-24:00 still sets onh (125)", L.get("onh") == 125.0)
    D2 = {k: v for k, v in D.items() if k != SUN}
    L = lv(B.levels(D2, [FRI, MON], 1))
    check("no Sunday file at all: Friday pdh, onh from Monday morning only (101)", L.get("pdh") == 120.0 and L.get("onh") == 101.0)

    # (c) normal Tuesday
    L = lv(B.levels(D, [FRI, SUN, MON, TUE], 3))
    check("Tuesday: pdh / pdl = Monday RTH (111 / 88)", L.get("pdh") == 111.0 and L.get("pdl") == 88.0)
    check("Tuesday: onh = Monday 19:00's 112 (Monday 16:30's 140 is not overnight), onl = Tuesday 04:00's 94",
          L.get("onh") == 112.0 and L.get("onl") == 94.0)
    check("Tuesday: a thin Sunday two days back changes nothing", lv(B.levels(D, [FRI, MON, TUE], 2)) == L)
    check("look-ahead: today's RTH bars never set onh / onl", lv(B.levels(D, [FRI, SUN, MON], 2)).get("onh") != 111.0)

    # (rt) red team #35: a thin RTH day the battery dropped (the 11-26 half day) is still the prior day (= the live bot), not a hole
    WED, THU, FRI2 = "2030-03-06", "2030-03-07", "2030-03-08"
    G = {WED: summary(WED, [("00:00", "17:00"), ("18:00", "23:55")], peaks=[("11:00", 120.0, 99.0), ("20:00", 105.0, 99.0)]),
         THU: summary(THU, [("00:00", "13:00"), ("18:00", "23:55")], peaks=[("10:00", 130.0, 99.0), ("21:00", 126.0, 99.0)]),
         FRI2: summary(FRI2, [("00:00", "13:15")])}
    DG = {d: B.Day(d, R) for d, R in G.items()}
    kept, dropped = lv(B.levels(DG, [WED, THU, FRI2], 2)), lv(B.levels(DG, [WED, FRI2], 1))
    check("rt thin half-day Thursday dropped: Friday still gets Thursday's pdh 130 + its evening onh 126 (same as kept)",
          dropped == kept and kept.get("pdh") == 130.0 and kept.get("onh") == 126.0)
    check("rt a later file in D never feeds an earlier day's levels", lv(B.levels(DG, [WED, THU], 1)) == lv(B.levels(
        {k: v for k, v in DG.items() if k != FRI2}, [WED, THU], 1)))
    with tempfile.TemporaryDirectory() as root:
        cd = os.path.join(root, "data", P.CACHE_NAME)
        os.makedirs(cd)
        for d, R in G.items():
            json.dump({"bars": R["bars"].to_dict("list"), "fp": R["fp"].to_dict("list"), "meta": R["meta"]}, open(os.path.join(cd, f"{d}.json"), "w"))
        pg, Rg = P._prev_summary(FRI2, None, root)
        Sg = P.replay_summary(G[FRI2], FRI2, Rg, pg, lit=[])
        Lg = {x["name"]: x["px"] for x in Sg["levels"]}
        check("rt live path agrees on the half-day Friday (pdh 130, onh 126)", pg == THU and Lg.get("pdh") == 130.0 and Lg.get("onh") == 126.0)

    # (d) the live path: engine/of_paper._prev_summary reads the day cache under data/of_paper_cache/
    with tempfile.TemporaryDirectory() as root:
        cd = os.path.join(root, "data", P.CACHE_NAME)
        os.makedirs(cd)
        for d, R in F.items():
            json.dump({"bars": R["bars"].to_dict("list"), "fp": R["fp"].to_dict("list"), "meta": R["meta"]}, open(os.path.join(cd, f"{d}.json"), "w"))
        pday, Rp = P._prev_summary(MON, None, root)
        check("_prev_summary(Monday) = Friday, Sunday rides along", pday == FRI and [x[0] for x in Rp.get("extra") or []] == [SUN])
        pt, Rt = P._prev_summary(TUE, None, root)
        check("_prev_summary(Tuesday) = Monday, nothing extra", pt == MON and not Rt.get("extra"))
        S = P.replay_summary(F[MON], MON, Rp, pday, lit=[])
        Ls = {x["name"]: x["px"] for x in S["levels"]}
        check("step(Monday) levels: pdh 120 / pdl 80 / onh 125 / onl 90", (Ls.get("pdh"), Ls.get("pdl"), Ls.get("onh"), Ls.get("onl")) == (120.0, 80.0, 125.0, 90.0))
        os.remove(os.path.join(cd, f"{FRI}.json"))
        pday2, Rp2 = P._prev_summary(MON, None, root)
        check("no RTH day in reach: the Sunday file still feeds the overnight", pday2 == SUN and not Rp2.get("extra"))
        S2 = P.replay_summary(F[MON], MON, Rp2, pday2, lit=[])
        L2 = {x["name"]: x["px"] for x in S2["levels"]}
        check("  ... and gives no pdh / pdl, onh 125", "pdh" not in L2 and L2.get("onh") == 125.0)
        check("kept cache files: Friday + Sunday + Monday fit (keep 6)", len(os.listdir(cd)) >= 3)
    print(f"\n{'ALL OK' if not FAILS else str(len(FAILS)) + ' FAILED'}")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
