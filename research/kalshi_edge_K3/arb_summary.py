#!/usr/bin/env python3
"""K3 angle 1 summary: edge per $1 of capital, frequency and size of the settled-history range-bucket arbs (data/arb_hist.json).
k = number of buckets (length of the per-market volume list). Cost per set: YES set = 100 - gross; NO set = 100 (k-1) - gross.
Train = events before 2026-08-01, test = after. Size proxy: the smallest per-leg volume traded in that hour (a fill needs every leg).
    python research/kalshi_edge_K3/arb_summary.py   -> data/arb_summary.json"""
import json, os, random, time, calendar
H = os.path.dirname(os.path.abspath(__file__))
MON = "JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split()
d = json.load(open(os.path.join(H, "data", "arb_hist.json")))
rows = []
for h in d["hits"]:
    k = len(h["vol"]); tag = h["e"].split("-")[1]
    day = calendar.timegm((2000 + int(tag[:2]), MON.index(tag[2:5]) + 1, int(tag[5:7]) if tag[5:7].isdigit() else 1, 0, 0, 0))
    cost = (100 - h["gross_c"]) if h["k"] == "yes" else (100 * (k - 1) - h["gross_c"])
    rows.append({"e": h["e"], "day": day, "net_c": h["net_c"], "cost_c": cost, "minvol": min(h["vol"]), "k": h["k"]})
SPLIT = calendar.timegm((2026, 8, 1, 0, 0, 0))

def stats(rs, nb=2000):
    if not rs:
        return None
    ev = {}
    for r in rs:
        ev.setdefault(r["e"], []).append(r)
    ks = list(ev); rnd = random.Random(3)
    f = lambda xs: sum(x["net_c"] for x in xs) / sum(x["cost_c"] for x in xs)
    bs = sorted(f([x for k in (rnd.choice(ks) for _ in ks) for x in ev[k]]) for _ in range(nb))
    days = (max(r["day"] for r in rs) - min(r["day"] for r in rs)) / 86400 + 1
    # $ per day if every hit filled 100 sets but no more than the thinnest leg traded that hour
    usd = sum(min(100, r["minvol"]) * r["net_c"] / 100 for r in rs)
    return {"n_obs": len(rs), "events": len(ks), "edge_per_$": round(f(rs), 4), "lo": round(bs[int(.025 * nb)], 4), "hi": round(bs[int(.975 * nb)], 4),
            "median_net_c_per_set": sorted(r["net_c"] for r in rs)[len(rs) // 2], "span_days": round(days),
            "usd_total_capped_by_thinnest_leg": round(usd, 2), "usd_per_day": round(usd / days, 2),
            "share_thinnest_leg_zero_vol": round(sum(r["minvol"] == 0 for r in rs) / len(rs), 3)}
out = {"source": "arb_hist.json hits (hourly closes, net of 0.07 p(1-p) fees on 100-lot legs)", "totals": d["total"],
       "all": stats(rows), "train": stats([r for r in rows if r["day"] < SPLIT]), "test": stats([r for r in rows if r["day"] >= SPLIT])}
json.dump(out, open(os.path.join(H, "data", "arb_summary.json"), "w"), indent=1)
print(json.dumps(out, indent=1))
