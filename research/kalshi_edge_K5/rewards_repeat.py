#!/usr/bin/env python3
"""K5: repeat the order-book snapshot of active reward markets ROUNDS times, GAP seconds apart, to measure how often a
snapshot is valid (both sides at Target depth) and how stable a new order's share is. GET only.
    python research/kalshi_edge_K5/rewards_repeat.py SERIES[,..] ROUNDS GAP
Writes data/rewards_repeat.json."""
import datetime as dt, json, os, sys, time, random, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from net import KAL, get  # noqa: E402
HERE = os.path.dirname(os.path.abspath(__file__))
def T(s): return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
def side_score(levels, target, df):
    depth = sum(s for _, s in levels); cum, ref = 0.0, None
    for pr, s in levels:
        cum += s
        if cum >= target / 5: ref = pr; break
    if ref is None: return depth, 0.0, None
    return depth, sum(s * (1.0 if pr >= ref - 1e-9 else df ** round((ref - pr) * 100)) for pr, s in levels), ref
series = sys.argv[1].split(","); rounds = int(sys.argv[2]); gap = float(sys.argv[3])
now = dt.datetime.now(dt.timezone.utc); pick = []
for s in series:
    d = get(KAL + "/incentive_programs", {"status": "active", "type": "liquidity", "limit": 1000, "series_ticker": s}, cache=False)
    ps = [x for x in (d or {}).get("incentive_programs", []) if x["series_ticker"] == s and T(x["start_date"]) <= now < T(x["end_date"])]
    pick += random.Random(9).sample(ps, min(8, len(ps)))
obs = collections.defaultdict(list)
for k in range(rounds):
    for x in pick:
        ob = get(KAL + "/markets/%s/orderbook" % x["market_ticker"], cache=False) or {}
        o = ob.get("orderbook_fp") or {}
        yes = sorted([(float(a), float(b)) for a, b in (o.get("yes_dollars") or [])], reverse=True)
        no = sorted([(float(a), float(b)) for a, b in (o.get("no_dollars") or [])], reverse=True)
        tgt, df = float(x["target_size_fp"]), x["discount_factor_bps"] / 1e4
        dy, sy, ry = side_score(yes, tgt, df); dn, sn, rn = side_score(no, tgt, df)
        Q = tgt / 5
        # my order of Q at the reference price on each side counts toward depth too
        valid = (dy + Q) >= tgt and (dn + Q) >= tgt
        share = ((Q / (sy + Q)) + (Q / (sn + Q))) / 2
        usd_day = (x["period_reward"] / 1e4) / ((T(x["end_date"]) - T(x["start_date"])).total_seconds() / 86400)
        bb = yes[0][0] if yes else None; ba = (1 - no[0][0]) if no else None
        obs[x["market_ticker"]].append({"k": k, "s": x["series_ticker"], "valid": valid, "share": share, "pool_day": usd_day,
            "Q": Q, "ref_yes": ry, "ref_no": rn, "bid": bb, "ask": ba, "cap": Q * ((ry or 0) + (rn or 0))})
    if k < rounds - 1: time.sleep(gap)
json.dump(obs, open(os.path.join(HERE, "data", "rewards_repeat.json"), "w"))
agg = collections.defaultdict(list)
for t, v in obs.items():
    for o in v: agg[o["s"]].append(o)
print("%-20s %5s %7s %7s %9s %9s %10s" % ("series", "obs", "valid%", "share", "mine$/d", "capital$", "per$1/day"))
for s, v in agg.items():
    md = sum(o["pool_day"] * o["share"] * o["valid"] for o in v) / len(v); cap = sum(o["cap"] for o in v) / len(v)
    print("%-20s %5d %6.0f%% %6.1f%% %9.2f %9.0f %9.2f%%" % (s, len(v), 100 * sum(o["valid"] for o in v) / len(v),
          100 * sum(o["share"] for o in v) / len(v), md, cap, 100 * md / max(cap, 1)))
