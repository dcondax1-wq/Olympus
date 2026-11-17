#!/usr/bin/env python3
"""Kalshi rewards backtest, step 2: Kalshi publishes no order-book HISTORY, so the queue ahead of a new order and the
others' reward score are estimated from TODAY's public order books (GET only). For up to N active program markets per series,
ROUNDS snapshots GAP seconds apart; per side: best bid, reference price (where depth reaches Target/5), ticks from best to
reference, depth at prices >= reference (= the queue ahead of a new order there) and everyone's qualifying score, as
multiples of Target, by side price bucket (cheap < 15c, mid, rich > 85c). Writes depth_profiles.json (small, committed).

    python research/kalshi_rewards_bt/depth_snap.py [SERIES,..] [--n 25] [--rounds 3] [--gap 180]"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import os
import random
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harvest as H  # noqa: E402

H.GAP = 0.25
OUT = os.path.join(H.HERE, "depth_profiles.json")


def bucket(p):
    return "cheap" if p < 0.15 else "rich" if p > 0.85 else "mid"


def side(levels, target, df):
    if not levels:
        return None
    cum, ref = 0.0, None
    for pr, s in levels:
        cum += s
        if cum >= target / 5 - 1e-9:
            ref = pr
            break
    depth = sum(s for _, s in levels)
    if ref is None:
        return {"best": levels[0][0], "ref": None, "depth_t": depth / target}
    ahead = sum(s for pr, s in levels if pr >= ref - 1e-9)
    sc = sum(s * (1.0 if pr >= ref - 1e-9 else df ** round((ref - pr) * 100)) for pr, s in levels)
    return {"best": levels[0][0], "ref": ref, "ticks": round((levels[0][0] - ref) * 100), "ahead_t": ahead / target,
            "score_t": sc / target, "depth_t": depth / target}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("series", nargs="?", default=",".join(H.SERIES))
    ap.add_argument("--n", type=int, default=25)
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--gap", type=float, default=180)
    a = ap.parse_args()
    now = time.time()
    pick = []
    for s in a.series.split(","):
        ps = [p for p in H.programs(s, now, now + 1) if p["start"] <= now < p["end"]]
        random.Random(5).shuffle(ps)
        pick += [(s, p) for p in ps[:a.n]]
    obs = []
    for k in range(a.rounds):
        for s, p in pick:
            ob = H.get("/markets/%s/orderbook" % p["m"], cache=False) or {}
            o = ob.get("orderbook_fp") or {}
            yes = sorted([(float(x), float(y)) for x, y in (o.get("yes_dollars") or [])], reverse=True)
            no = sorted([(float(x), float(y)) for x, y in (o.get("no_dollars") or [])], reverse=True)
            ys, ns = side(yes, p["target"], p["df"]), side(no, p["target"], p["df"])
            valid = bool(ys and ns and ys["depth_t"] + 0.2 >= 1 and ns["depth_t"] + 0.2 >= 1)
            obs.append({"k": k, "s": s, "m": p["m"], "target": p["target"], "usd_day": p["usd"] / max((p["end"] - p["start"]) / 86400, 1e-6),
                        "yes": ys, "no": ns, "valid": valid})
        if k < a.rounds - 1:
            time.sleep(a.gap)
    prof = {}
    for s in a.series.split(","):
        rows = [o for o in obs if o["s"] == s]
        b = collections.defaultdict(list)
        for o in rows:
            for sd in ("yes", "no"):
                x = o[sd]
                if x and x.get("ref") is not None:
                    b[bucket(x["ref"])].append(x)
        prof[s] = {"snapshots": len(rows), "markets": len({o["m"] for o in rows}),
                   "valid_pct": round(100 * sum(o["valid"] for o in rows) / max(len(rows), 1), 1), "buckets": {}}
        for bk, xs in b.items():
            q = sorted(x["ahead_t"] for x in xs)
            prof[s]["buckets"][bk] = {"n": len(xs), "ticks_med": statistics.median(x["ticks"] for x in xs),
                                      "ahead_t_med": statistics.median(q), "ahead_t_q25": q[len(q) // 4], "ahead_t_q75": q[3 * len(q) // 4],
                                      "score_t_med": statistics.median(x["score_t"] for x in xs),
                                      "score_t_mean": statistics.fmean(x["score_t"] for x in xs)}
    json.dump({"when": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "profiles": prof, "obs": obs},
              open(OUT, "w"), indent=0)
    for s, v in prof.items():
        print(s, v["markets"], "mkts", v["valid_pct"], "% valid", {k: (x["n"], round(x["ahead_t_med"], 2), round(x["score_t_med"], 2), x["ticks_med"])
                                                                  for k, x in v["buckets"].items()})


if __name__ == "__main__":
    main()
