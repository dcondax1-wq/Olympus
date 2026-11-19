#!/usr/bin/env python3
"""Red team on K8, part 2 (offline; K8 raw cache read only): liquidity for $10 / $15 / $20 at +20 s per leg, the correlation
between the day's bets (how many independent bets a paper test really has), the forward thresholds (how many paper bets and
which win rate before any money), and the trend of the edge over the 78 days. Adds to results_k8.json.
    python research/kalshi_red_team/k8_more.py"""
from __future__ import annotations

import collections
import json
import math
import os
import random
import statistics
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import k8_check as K  # noqa: E402

OUT = K.OUT


def main():
    res = json.load(open(OUT))
    tape = {name: K.open_tape(s) for name, s in K.SER.items()}
    bets = [r for r in K.csv.DictReader(open(K.BETS)) if r["leg"] in K.LEGS]
    # ---------------------------------------------------------- liquidity at +20 s, per leg and stake
    liq = collections.defaultdict(lambda: collections.defaultdict(list))
    comp = collections.defaultdict(list)
    for b in bets:
        name, hh, side = K.LEGS[b["leg"]]
        rec = tape[name].get(b["ticker"])
        if not rec:
            continue
        tr = rec["tr"]
        first = next((p for t, p, c in sorted(K.our(tr, side)) if t >= 20.0), None)
        for stake in (10.0, 15.0, 20.0):
            n = int(stake // float(b["entry_15_30s"]))
            px, t_done = K.walk(tr, side, 20.0, n)
            liq[b["leg"]][stake].append((px, t_done, first, n))
        o = K.our(tr, side)
        comp[b["leg"]].append(sum(c for t, p, c in o if 20.0 <= t <= 25.0))
    L = {}
    for leg, by in liq.items():
        L[leg] = {}
        for stake, xs in by.items():
            done30 = sum(1 for px, t, f, n in xs if t is not None and t <= 30.0)
            done45 = sum(1 for px, t, f, n in xs if t is not None)
            slip = sorted((px - f) for px, t, f, n in xs if px is not None and f is not None)
            L[leg]["$%d" % stake] = {"contracts": int(statistics.median(n for _, _, _, n in xs)), "filled_by_30s_pct": round(100 * done30 / len(xs)),
                                     "filled_by_45s_pct": round(100 * done45 / len(xs)),
                                     "walk_minus_first_trade_c_median": round(100 * slip[len(slip) // 2], 2) if slip else None,
                                     "walk_minus_first_trade_c_p90": round(100 * slip[int(0.9 * len(slip))], 2) if slip else None}
        cs = sorted(comp[leg])
        L[leg]["our_side_contracts_20_25s_median"] = round(cs[len(cs) // 2], 1)
    res["liquidity_at_20s"] = L
    # ---------------------------------------------------------- correlation inside a day (design effect)
    byday = collections.defaultdict(dict)
    for b in bets:
        byday[b["date"]][b["leg"]] = 1.0 if b["won"] == "1" else 0.0
    legs = list(K.LEGS)
    pairs = []
    for i in range(len(legs)):
        for j in range(i + 1, len(legs)):
            xs = [(d[legs[i]], d[legs[j]]) for d in byday.values() if legs[i] in d and legs[j] in d]
            if len(xs) < 20:
                continue
            a = [x for x, _ in xs]
            b2 = [y for _, y in xs]
            ma, mb = statistics.fmean(a), statistics.fmean(b2)
            sa, sb = statistics.pstdev(a), statistics.pstdev(b2)
            if sa > 0 and sb > 0:
                rho = statistics.fmean((x - ma) * (y - mb) for x, y in xs) / (sa * sb)
                pairs.append((legs[i], legs[j], round(rho, 3)))
    rho_bar = statistics.fmean(p[2] for p in pairs)
    deff = 1 + (6 - 1) * rho_bar
    res["correlation"] = {"pairs": pairs, "mean_rho": round(rho_bar, 3), "design_effect_6_bets_a_day": round(deff, 2),
                          "same_window_gold_silver": [p for p in pairs if p[0][:1] == p[1][:1]]}
    # ---------------------------------------------------------- forward thresholds
    # break-even at the recent price: 28 contracts at 0.54 + the fee
    p_be = (28 * 0.54 + float(K.V.fee("0.54", 28))) / 28
    thr = []
    rnd = random.Random(5)
    days_all = sorted(byday)
    for n_bets in (60, 90, 120, 150, 180):
        se0 = math.sqrt(p_be * (1 - p_be) * deff / n_bets)
        x = p_be + 1.645 * se0                       # a 5% chance to pass if the edge is gone (true rate = break-even)
        se1 = math.sqrt(0.68 * 0.32 * deff / n_bets)
        power = 0.5 * (1 + math.erf((0.68 - x) / se1 / math.sqrt(2)))
        # check by resampling whole days of the in-sample record: how often does a paper run of this length clear x?
        k = n_bets // 6
        hits = 0
        for _ in range(4000):
            ds = [rnd.choice(days_all) for _ in range(k)]
            w = [v for d in ds for v in byday[d].values()]
            hits += (sum(w) / len(w)) >= x
        thr.append({"paper_bets": n_bets, "weeks": round(n_bets / 30, 1), "win_rate_needed": round(x, 3),
                    "chance_to_pass_if_the_edge_is_gone": 0.05, "chance_to_pass_if_it_is_like_aug_nov_normal": round(power, 2),
                    "chance_to_pass_resampling_aug_nov_days": round(hits / 4000, 2)})
    res["forward"] = {"break_even_win_rate_at_54c": round(p_be, 4), "design_effect": round(deff, 2), "thresholds": thr}
    # ---------------------------------------------------------- trend over the 78 days (daily net per $1 at $15, study entry)
    dly = collections.defaultdict(lambda: [0.0, 0.0])
    for b in bets:
        p = float(b["entry_15_30s"])
        net, cost, n, fee = K.pnl(p, b["won"] == "1")
        dly[b["date"]][0] += net
        dly[b["date"]][1] += cost
    ds = sorted(dly)
    xs = list(range(len(ds)))
    ys = [dly[d][0] / dly[d][1] for d in ds]

    def slope(ix):
        mx = statistics.fmean(xs[i] for i in ix)
        my = statistics.fmean(ys[i] for i in ix)
        num = sum((xs[i] - mx) * (ys[i] - my) for i in ix)
        den = sum((xs[i] - mx) ** 2 for i in ix)
        return num / den if den else 0.0
    s0 = slope(range(len(ds)))
    bs = sorted(slope([rnd.randrange(len(ds)) for _ in ds]) for _ in range(3000))
    res["trend"] = {"days": len(ds), "slope_net_per_1_per_month": round(30 * s0, 4),
                    "ci95_per_month": [round(30 * bs[75], 4), round(30 * bs[2924], 4)],
                    "first_half_avg_daily_net_per_1": round(statistics.fmean(ys[:len(ys) // 2]), 4),
                    "second_half_avg_daily_net_per_1": round(statistics.fmean(ys[len(ys) // 2:]), 4)}
    # the price paid month by month (is the market catching up?)
    pm = collections.defaultdict(list)
    for b in bets:
        pm[b["date"][:7]].append(float(b["entry_15_30s"]))
    res["price_paid_by_month"] = {m: round(statistics.fmean(v), 3) for m, v in sorted(pm.items())}
    json.dump(res, open(OUT, "w"), indent=1, default=str)
    print("LIQUIDITY", json.dumps(L))
    print("CORRELATION", json.dumps(res["correlation"]))
    print("FORWARD", json.dumps(res["forward"]))
    print("TREND", json.dumps(res["trend"]), res["price_paid_by_month"])


if __name__ == "__main__":
    main()
