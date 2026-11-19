#!/usr/bin/env python3
"""Red team: the raw public data behind the rewards PAPER test (research/kalshi_edge_K5/paper/rewards_paper_snapshot.json):
for its 9 markets, the trade tape and 1-minute candles from an hour before the paper start to now, the market state, the
liquidity programs of the 3 series, and 2 rounds of live order books (all active program markets of the 3 series, up to 30 per
series) for the reward-formula check. GET only, <= 1 request a second. Writes /home/user/kalshi_cache/kred/paper_raw.json.
    python research/kalshi_red_team/paper_fetch.py"""
from __future__ import annotations

import json
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import fetch  # noqa: E402
from harvest_bt import T, candles, trades  # noqa: E402

LEDGER = os.path.join(ROOT, "research", "kalshi_edge_K5", "paper", "rewards_paper_snapshot.json")
OUT = os.path.join(fetch.CACHE, "paper_raw.json")
SERIES = ["KXRT", "KXPANAMAWEEKLY", "KXBABELMANDEBWEEKLY"]


def main():
    led = json.load(open(LEDGER))
    t0 = T(led["started"]) - 3600
    now = float(int(time.time() // 60 * 60))
    out = {"fetched": now, "paper_started": led["started"], "paper_updated": led["updated"], "markets": {}, "programs": {}, "books": []}
    for s in SERIES:
        rows = fetch.paged("/incentive_programs", {"series_ticker": s, "type": "liquidity", "limit": 1000}, "incentive_programs",
                           cursor_key="next_cursor", cache=False, max_pages=40)
        out["programs"][s] = [x for x in rows if x.get("incentive_type") == "liquidity" and T(x["end_date"]) > t0]
        print(s, "programs since paper start", len(out["programs"][s]), "requests", fetch.COUNT[0], flush=True)
    for t, m in led["markets"].items():
        mk = (fetch.get("/markets/" + t, cache=False) or {}).get("market") or {}
        out["markets"][t] = {"s": m["s"], "info": {k: mk.get(k) for k in ("result", "status", "close_time", "yes_bid_dollars", "yes_ask_dollars",
                                                                            "last_price_dollars", "settlement_ts")},
                             "candles": candles(m["s"], t, t0, now, cache=False), "trades": trades(t, t0, now, cache=False)}
        print(t, "trades", len(out["markets"][t]["trades"]), "candles", len(out["markets"][t]["candles"]), "requests", fetch.COUNT[0], flush=True)
    act = []
    for s in SERIES:
        ps = [x for x in out["programs"][s] if T(x["start_date"]) <= now < T(x["end_date"])]
        random.Random(3).shuffle(ps)
        act += ps[:30] if s == "KXRT" else ps
    for k in range(2):
        for x in act:
            ob = fetch.get("/markets/%s/orderbook" % x["market_ticker"], cache=False) or {}
            out["books"].append({"k": k, "t": time.time(), "s": x["series_ticker"], "m": x["market_ticker"], "target": float(x["target_size_fp"]),
                                 "df": x["discount_factor_bps"] / 1e4, "usd_day": x["period_reward"] / 1e4 / max((T(x["end_date"]) - T(x["start_date"])) / 86400, 1e-9),
                                 "ob": ob.get("orderbook_fp") or {}})
        print("books round", k, len(act), "requests", fetch.COUNT[0], flush=True)
    json.dump(out, open(OUT, "w"))
    print("wrote", OUT, os.path.getsize(OUT) // 1024, "KB; requests", fetch.COUNT[0])


if __name__ == "__main__":
    main()
