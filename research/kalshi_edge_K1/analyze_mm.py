#!/usr/bin/env python3
"""K1 study 3: resting a limit order 1-2c INSIDE the spread (market making) on Kalshi's hourly Nasdaq-100 / S&P 500 markets.

From the 1-minute candles (yes bid / ask high-low-close and trade-price high-low per minute, public API):
  post at m minutes before close (m = 50 / 30 / 20 / 10) when the spread is >= 2c (>= 3c for 2c inside) and 3 <= mid <= 97:
    YES bid at bid+k, or a NO bid at 100-(ask-k) (= offering YES at ask-k); it rests until close or for W minutes.
  FILLED only if the market later trades THROUGH it: the yes ask drops to our bid, or a trade prints below our bid (for the
  NO side: the yes bid rises to our offer, or a trade prints above it). A print exactly at our price is NOT counted as a
  fill (queue position unknown) - this favours the strategy slightly on fill rate but not on adverse selection.
  P&L per fill = settlement - price - maker fee (0.0175 p(1-p), rounded up per contract; charged as if every series had it).
Adverse selection = mid at posting minus what the filled contracts were worth at settlement.
Split by time (train settle < 2026-07-01). Cluster bootstrap by settle time.

    python research/kalshi_edge_K1/analyze_mm.py [--series KXNASDAQ100U]
"""
import argparse, datetime as dt, gzip, json, os, sys
from zoneinfo import ZoneInfo
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kk, stats

HERE = os.path.dirname(os.path.abspath(__file__))
SPLIT = int(dt.datetime(2026, 7, 1, tzinfo=ZoneInfo("America/New_York")).timestamp())


def quote(c, m):
    for k in range(m, 67):
        q = c.get(str(k))
        if q and q[0] is not None and q[1] is not None:
            return q
    return None


def sim(rows, m, k, side, W):
    fills, posted, upper, adv = [], 0, [], []
    for r in rows:
        c = r["c"]
        q = quote(c, m)
        if not q:
            continue
        b, a = q[0], q[1]
        if a - b < k + 1 or not (3 <= (a + b) / 2 <= 97) or a > 100 or b < 0:
            continue
        y = r["res"] == "yes"
        mid = (a + b) / 2
        posted += 1
        if side == "yes":
            p = b + k
            filled = False
            for j in range(m - 1, max(-1, m - 1 - W), -1):
                x = c.get(str(j))
                if not x:
                    continue
                if (x[2] is not None and x[2] <= p) or (x[4] is not None and x[6] > 0 and x[4] < p):
                    filled = True
                    break
            val = 100 if y else 0
            cost = p
        else:
            s = a - k                    # we offer YES at s = we bid NO at 100 - s
            filled = False
            for j in range(m - 1, max(-1, m - 1 - W), -1):
                x = c.get(str(j))
                if not x:
                    continue
                if (x[3] is not None and x[3] >= s) or (x[5] is not None and x[6] > 0 and x[5] > s):
                    filled = True
                    break
            val = 0 if y else 100
            cost = 100 - s
        pnl = val - cost - kk.fee_c(cost, maker=True)
        upper.append((r["ct"], pnl, cost))
        if filled:
            fills.append((r["ct"], pnl, cost))
            adv.append(((mid if side == "yes" else 100 - mid) - val))
    return posted, fills, upper, adv


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--series", default="KXNASDAQ100U")
    a = ap.parse_args()
    rows = [json.loads(l) for l in gzip.open(os.path.join(kk.DATA, f"idx_{a.series}.jsonl.gz"), "rt")]
    rows = [r for r in rows if r["st"] == "greater_or_equal"]
    out = {"series": a.series, "split": "2026-07-01", "cells": []}
    for m in (50, 30, 20, 10):
        for k in (1, 2):
            for side in ("yes", "no"):
                for W in (5, 60):
                    cell = {"m": m, "k": k, "side": side, "W": W}
                    for nm, rs in (("train", [r for r in rows if r["ct"] < SPLIT]), ("test", [r for r in rows if r["ct"] >= SPLIT])):
                        posted, fills, upper, adv = sim(rs, m, k, side, W)
                        cell[nm] = {"posted": posted, "fill_rate": round(len(fills) / posted, 3) if posted else None,
                                    "filled": stats.block(fills), "if_always_filled": stats.block(upper),
                                    "adverse_c": round(sum(adv) / len(adv), 2) if adv else None}
                    out["cells"].append(cell)
                    tr, te = cell["train"], cell["test"]
                    print(m, k, side, W, "train fill", tr["fill_rate"], "edge", tr["filled"].get("edge_per_usd"), "n", tr["filled"].get("n"),
                          "adv", tr["adverse_c"], "| test fill", te["fill_rate"], "edge", te["filled"].get("edge_per_usd"),
                          te["filled"].get("lo95"), te["filled"].get("hi95"), "n", te["filled"].get("n"), "adv", te["adverse_c"],
                          "| upper", te["if_always_filled"].get("edge_per_usd"))
    best = max((c for c in out["cells"] if c["train"]["filled"].get("n", 0) >= 100), key=lambda c: c["train"]["filled"]["edge_per_usd"], default=None)
    out["best_on_train"] = best
    json.dump(out, open(os.path.join(HERE, f"results_mm_{a.series}.json"), "w"), indent=1)
    if best:
        print("BEST on train:", {k: best[k] for k in ("m", "k", "side", "W")}, "train", best["train"]["filled"], "test", best["test"]["filled"])


if __name__ == "__main__":
    main()
