#!/usr/bin/env python3
"""Cross-series scan (GET only, <= 1 request a second, never an order): from a saved list of today's ACTIVE liquidity programs
(kalshi_cache/krew/active_programs_*.json, the public /incentive_programs), take up to --per markets of each of the --top series
by pool, read each market's public order book once, and append it to the books file (same format as books.py, "mk" empty).
    python research/kalshi_best_shot/scan.py [--top 120] [--per 3] [--skip KXPANAMAWEEKLY,...]"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import glob
import gzip
import json
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import kget  # noqa: E402
from books import OUT, T, levels  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=120)
    ap.add_argument("--per", type=int, default=3)
    ap.add_argument("--skip", default="")
    ap.add_argument("--programs", default="")
    a = ap.parse_args()
    fn = a.programs or sorted(glob.glob("/home/user/kalshi_cache/krew/active_programs_*.json"))[-1]
    ps = json.load(open(fn))
    now = time.time()
    by = collections.defaultdict(list)
    for p in ps:
        if p.get("incentive_type") == "liquidity" and T(p["start_date"]) <= now < T(p["end_date"]):
            by[p["series_ticker"]].append(p)
    skip = set(x for x in a.skip.split(",") if x)
    rank = sorted(by, key=lambda s: -sum(p["period_reward"] / 1e4 / max((T(p["end_date"]) - T(p["start_date"])) / 86400, 1e-9) for p in by[s]))
    rank = [s for s in rank if s not in skip][:a.top]
    os.makedirs(OUT, exist_ok=True)
    out = os.path.join(OUT, dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d") + "_scan.jsonl.gz")
    n = 0
    with gzip.open(out, "at") as f:
        for s in rank:
            L = sorted(by[s], key=lambda p: p["market_ticker"])
            random.Random(5).shuffle(L)
            for p in L[:a.per]:
                ob = kget.get("/markets/%s/orderbook" % p["market_ticker"], cache=False)
                if ob is None:
                    continue
                a0, b0 = T(p["start_date"]), T(p["end_date"])
                f.write(json.dumps({"t": round(time.time(), 1), "m": p["market_ticker"], "s": s, "yes": levels(ob, "yes_dollars"),
                                    "no": levels(ob, "no_dollars"),
                                    "prog": {"usd_day": p["period_reward"] / 1e4 / max((b0 - a0) / 86400, 1e-9), "usd": p["period_reward"] / 1e4,
                                             "target": float(p.get("target_size_fp") or 1000), "df": (p.get("discount_factor_bps") or 5000) / 1e4,
                                             "start": a0, "end": b0}, "mk": {}}) + "\n")
                n += 1
            f.flush()
    print("scan books", n, "->", out, kget.STATS)


if __name__ == "__main__":
    main()
