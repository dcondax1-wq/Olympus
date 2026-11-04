"""BLITZ funded-only fix test (job 30, 2026-11-04): why a funded Builder 25K at BLITZ's $150 size pays $108 a month in Jan-Jun and $0 in Jul-Oct
(research/scalp/blitz_funded_study.json), and one concrete fix to test. RESEARCH ONLY.

The funded account (tools/scalp_na_lib.Funded, the MFFU Builder 25K funded rules: $1,000 EOD trailing floor locked at +$100, $600 soft daily loss,
$1,100 buffer, request $250-$1,000, best day <= 50% of the cycle, 80% to you, 5 payouts) is played on 1,000 Monte Carlo paths of 126 sessions (5-session
blocks of the span; the old study used 22 / 6 three-month starts, too few for Jul-Oct). The bot stops trading a funded account when its room falls
under about 2 x the median risk of a micro ("stuck"): at $150 a trade BLITZ's small edge cannot rebuild the room, so most accounts end stuck before the
$1,350 balance a first payout needs.

Variants: the funded size (share of the room, $ cap, a day take-profit), BLITZ's later-break size in the funded phase (first band break of the day
x0.5, a later one x1.75; owner-adopted for the eval 2026-10-31), only later breaks, and a "build then hold" size (bigger until the first payout, $150 after).

    python -X utf8 tools/blitz_funded_fix.py        # -> research/scalp/blitz_funded_fix.json
Pick on Jan-Jun, check on Jul-Oct. Nothing live.
"""
from __future__ import annotations

import json
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import ab_edge as AB  # noqa: E402

OUT = os.path.join(ROOT, "research", "scalp", "blitz_funded_fix.json")


def funded_mc(N, BS, T, S, fz, n=1000, length=126, seed=23, stuck_mult=1.0):
    by = BS._by(T)
    stuck = BS._stuck(T) * stuck_mult
    paid, first, outc, trades = [], [], {"lost": 0, "stuck": 0, "max": 0, "open": 0}, []
    for seq in N.mc_paths(S, n, length, seed=seed):
        acc = N.Funded("25k", fz, stuck)
        tot, fp, nt = 0.0, None, 0
        for k, d in enumerate(seq):
            nt += len(by.get(d, ()))
            p = acc.step(by.get(d, ()))
            tot += p
            if p and fp is None:
                fp = k + 1
            if acc.done:
                break
        paid.append(tot)
        trades.append(nt / max(1, k + 1) * 5)
        outc[acc.done or "open"] += 1
        if fp:
            first.append(fp)
    a = np.array(paid)
    return {"per_month": round(float(a.mean()) / 6.0), "p10_per_month": round(float(np.percentile(a, 10)) / 6.0),
            "any_pay_pct": round(100.0 * len(first) / n, 1), "first_med": float(np.median(first)) if first else None,
            "lost_pct": round(100.0 * outc["lost"] / n, 1), "stuck_pct": round(100.0 * outc["stuck"] / n, 1), "maxed_pct": round(100.0 * outc["max"] / n, 1),
            "trades_per_week": round(float(np.mean(trades)), 2)}


def main():
    N, K, BS = AB.blitz_libs()
    TT = AB.blitz_trades()
    SP = AB.spans_of(TT)
    FZ = dict(AB.PICK_FZ)
    V = {}
    V["today_f0.10_cap150_tp400"] = ({}, None)
    for f, cap in ((0.05, 100.0), (0.15, 150.0), (0.10, 200.0), (0.15, 250.0), (0.20, 300.0)):
        V[f"size_f{f}_cap{int(cap)}"] = ({"f": f, "cap": cap}, None)
    for tp in (200.0, 300.0, 600.0, None):
        V[f"day_tp_{int(tp) if tp else 'none'}"] = ({"day_tp": tp}, None)
    V["later_break_size_x0.5_x1.75"] = ({}, "mult")
    V["later_break_only"] = ({}, "only_later")
    V["later_break_size_cap200"] = ({"cap": 200.0, "f": 0.12}, "mult")
    V["keep_trading_stuck_x0.75"] = ({"_stuck": 0.75}, None)       # stop only when room < 0.75 x today's stuck line (today 2 x the median micro risk)
    V["keep_trading_stuck_x0.5"] = ({"_stuck": 0.5}, None)         # = one median micro's risk
    V["later_break_cap200_stuck_x0.75"] = ({"cap": 200.0, "f": 0.12, "_stuck": 0.75}, "mult")
    V["later_break_cap200_stuck_x0.5"] = ({"cap": 200.0, "f": 0.12, "_stuck": 0.5}, "mult")
    V["later_break_size_stuck_x0.5"] = ({"_stuck": 0.5}, "mult")
    V["stuck_x0.5_day_tp_600"] = ({"_stuck": 0.5, "day_tp": 600.0}, None)
    V["later_break_size_stuck_x0.5_day_tp_600"] = ({"_stuck": 0.5, "day_tp": 600.0}, "mult")
    res = {"what": "BLITZ funded 25K, funded stage only, 1,000 paths x 126 sessions", "spans": {}}
    for nm, (chg, mode) in V.items():
        res.setdefault("rows", {})[nm] = {"fz": {**FZ, **chg}, "mode": mode}
    for sp, (T, S) in SP.items():
        if sp == "R":
            continue
        nth = AB.nth_of_entry
        for nm, (chg, mode) in V.items():
            fz = {**FZ, **chg}
            sm = fz.pop("_stuck", 1.0)
            if fz.get("day_tp", 0) is None:
                fz.pop("day_tp", None)
            Tm = T
            if mode == "mult":
                m = [AB.nth_mult(t["f"].get("nth", np.nan), 1.75, 0.5) for t in T]
                Tm = AB.with_mult(T, m)
            elif mode == "only_later":
                Tm = [t for t in T if t["f"].get("nth", 1) >= 2]
            t1 = time.time()
            r = funded_mc(N, BS, Tm, S, fz, stuck_mult=sm)
            res["rows"][nm][sp] = r
            print(f"{nm:34s} {sp} ${r['per_month']:>4}/mo (p10 {r['p10_per_month']}) any payout {r['any_pay_pct']}% first {r['first_med']} lost {r['lost_pct']} stuck {r['stuck_pct']} max {r['maxed_pct']} tpw {r['trades_per_week']} ({time.time() - t1:.0f}s)", flush=True)
            json.dump(res, open(OUT, "w"), indent=1)
    json.dump(res, open(OUT, "w"), indent=1)


if __name__ == "__main__":
    main()
