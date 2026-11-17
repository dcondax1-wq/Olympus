#!/usr/bin/env python3
"""K5 rewards: list ACTIVE Kalshi liquidity-incentive programs (public endpoint, no key), snapshot each sampled market's
public order book, and work out what a new resting order would earn per $ per day:
  my payout per day ~= daily_reward x (my score / (others' score + my score)) x valid-snapshot share
(help.kalshi.com 'Liquidity Incentive Program': score = size x DF^(ticks below the reference price), reference = price where
cumulative depth reaches Target/5; a side under Target depth -> snapshot excluded). period_reward is in centi-cents.
GET only. Writes data/rewards_snapshot.json."""
import datetime as dt, json, os, random, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from net import KAL, get  # noqa: E402
HERE = os.path.dirname(os.path.abspath(__file__))
now = dt.datetime.now(dt.timezone.utc)
def T(s): return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))

progs, cur = [], None
for _ in range(200):
    p = {"status": "active", "type": "liquidity", "limit": 1000}
    if cur: p["cursor"] = cur
    d = get(KAL + "/incentive_programs", p, cache=False)
    if not d: break
    progs += d.get("incentive_programs", [])
    cur = d.get("next_cursor")
    if not cur or not d.get("incentive_programs"): break
progs = [x for x in progs if x["incentive_type"] == "liquidity" and T(x["start_date"]) <= now < T(x["end_date"])]
for x in progs:
    x["days"] = (T(x["end_date"]) - T(x["start_date"])).total_seconds() / 86400
    x["usd_day"] = x["period_reward"] / 1e4 / max(x["days"], 1e-6)
print("active liquidity programs", len(progs), "total $/day %.0f" % sum(x["usd_day"] for x in progs))

def side_score(levels, target, df):
    """levels: [(price, size)] for one side (bids), best first. Returns (total depth, qualifying score, ref price)."""
    depth = sum(s for _, s in levels)
    cum, ref = 0.0, None
    for pr, s in levels:
        cum += s
        if cum >= target / 5: ref = pr; break
    if ref is None: return depth, 0.0, None
    sc = sum(s * (1.0 if pr >= ref - 1e-9 else df ** round((ref - pr) * 100)) for pr, s in levels)
    return depth, sc, ref

NICHE = ["KXAAAGASD", "KXAAAGASW", "KXAAAGASM", "KXYTVIEWSW", "KXTSAW", "KXTRUTHSOCIAL", "KXTRUTHSOCIALD", "KXRT",
         "KXNETFLIXRANKSHOW", "KXSPOTIFYD", "KXDIESELD"]
rnd = random.Random(5)
by = collections.defaultdict(list)
for x in progs: by[x["series_ticker"]].append(x)
top = sorted(by, key=lambda s: -sum(x["usd_day"] for x in by[s]))[:25]
pick = []
for s in set(top) | {s for s in NICHE if s in by}:
    pick += rnd.sample(by[s], min(8, len(by[s])))
out = []
for x in pick:
    ob = get(KAL + "/markets/%s/orderbook" % x["market_ticker"], cache=False)
    o = (ob or {}).get("orderbook_fp") or {}
    yes = sorted([(float(a), float(b)) for a, b in (o.get("yes_dollars") or [])], reverse=True)
    no = sorted([(float(a), float(b)) for a, b in (o.get("no_dollars") or [])], reverse=True)
    tgt, df = float(x["target_size_fp"]), x["discount_factor_bps"] / 1e4
    dy, sy, ry = side_score(yes, tgt, df); dn, sn, rn = side_score(no, tgt, df)
    valid = dy >= tgt and dn >= tgt
    mid = ((yes[0][0] if yes else 0) + (1 - no[0][0] if no else 1)) / 2
    # a new order of Q contracts each side at the reference price: score Q per side, capital ~ Q x (p_yes + p_no) ~ Q dollars
    Q = tgt / 5
    share = ((Q / (sy + Q)) + (Q / (sn + Q))) / 2 if (sy and sn) else None
    usd_day_mine = x["usd_day"] * share if (share and valid) else 0.0
    out.append({"s": x["series_ticker"], "t": x["market_ticker"], "usd_day_pool": x["usd_day"], "target": tgt, "df": df,
                "desc": x["incentive_description"], "depth_yes": dy, "depth_no": dn, "score_yes": sy, "score_no": sn,
                "ref_yes": ry, "ref_no": rn, "valid_now": valid, "mid": mid, "Q": Q, "share": share,
                "usd_day_mine": usd_day_mine, "usd_per_dollar_day": usd_day_mine / Q if Q else 0})
json.dump({"when": now.isoformat(), "n_active": len(progs), "usd_day_all": sum(x["usd_day"] for x in progs),
           "by_series_usd_day": {s: sum(x["usd_day"] for x in by[s]) for s in by}, "sample": out},
          open(os.path.join(HERE, "data", "rewards_snapshot.json"), "w"), indent=1)
agg = collections.defaultdict(list)
for r in out: agg[r["s"]].append(r)
print("%-22s %4s %9s %7s %6s %10s %10s" % ("series", "n", "pool$/day", "valid%", "Q", "mine$/day", "per$1/day"))
for s, rs in sorted(agg.items(), key=lambda kv: -sum(r["usd_day_pool"] for r in kv[1])):
    n = len(rs)
    print("%-22s %4d %9.1f %7.0f %6.0f %10.2f %9.3f%%" % (s, n, sum(r["usd_day_pool"] for r in rs) / n, 100 * sum(r["valid_now"] for r in rs) / n,
          sum(r["Q"] for r in rs) / n, sum(r["usd_day_mine"] for r in rs) / n, 100 * sum(r["usd_per_dollar_day"] for r in rs) / n))
