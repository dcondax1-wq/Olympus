#!/usr/bin/env python3
"""K4 idea 1 (crypto): Kalshi 15-minute up/down vs the SAME window on Polymarket.

Signal: Polymarket's Up price pu (last print at or before the decision minute). Kalshi side bought at its ask
(YES = yes ask, NO = 1 - yes bid), fee 0.07 p(1-p) rounded up on a $10 order.
  follow : buy Kalshi YES when pu - yes_ask > thr; buy NO when (1 - pu) - (1 - yes_bid) > thr
  average: fair = (pu + kalshi mid) / 2, same test against the ask
Execution: 'now' = the Kalshi quote of the same minute; 'lag' = the Kalshi quote one minute LATER (realistic delay).
One trade per market: the earliest minute (most minutes to expiry) in the bucket where the signal fires.
Cells: coin x minutes-to-expiry bucket x thr x rule x exec. Train = closes before SPLIT, test after (read once).
Cluster = settle time (all coins settle together). Bonferroni bar over the eligible cells (n_train >= 60).
Also: locked arbitrage = Kalshi side ask + Polymarket other side (pu or 1-pu, + 0.5c half spread) + both fees < $1,
and how often the two venues settle differently (basis risk: BRTI vs Chainlink).
    python research/kalshi_edge_K4/crypto_xvenue.py           -> results_crypto_xvenue.json
    python research/kalshi_edge_K4/crypto_xvenue.py --align   -> results_crypto_xvenue_aligned.json
--align: diag_lag.py shows a Polymarket print stamped t matches the Kalshi quote of t - 60 s (gap 2.6c vs 7.5c at the
same stamp), i.e. the history is stamped about a minute late. With --align the print stamped t is treated as known at
t - 60 s: 'now' trades the Kalshi quote of t - 60 s, 'lag' the quote of t.
"""
import gzip
import json
import math
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone

from lib import fee_per_contract, pnl_per_dollar, summary

HERE = os.path.dirname(os.path.abspath(__file__))
SPLIT = datetime(2026, 10, 29, tzinfo=timezone.utc).timestamp()
BUCKETS = {"m1-3": range(1, 4), "m4-7": range(4, 8), "m8-13": range(8, 14)}
THRS = (0.03, 0.05, 0.08, 0.12)


def load(coin):
    p = os.path.join(HERE, "data", "crypto_%s.json.gz" % coin)
    return json.load(gzip.open(p)) if os.path.exists(p) else []


def quotes(r):
    q = {}
    for c in r.get("c") or []:
        if c[1] is not None and c[2] is not None and c[2] > c[1]:
            q[int(round((r["close"] - c[0]) / 60))] = (c[1], c[2])
    return q


def pm_at(pm, t):
    best = None
    for a, p in pm:
        if a <= t and t - a <= 90:
            best = p
    return best


def zbar(k, alpha=0.05):
    a = alpha / max(k, 1)
    lo, hi = 0.0, 10.0
    for _ in range(60):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if 0.5 * math.erfc(mid / 2 ** 0.5) > a else (lo, mid)
    return hi


ALIGN = "--align" in sys.argv


def main():
    trades = defaultdict(list)  # cell -> list of units
    arb = []
    agree = [0, 0]
    ndays = {}
    for coin in ("BTC", "ETH", "SOL", "XRP"):
        rows = load(coin)
        for r in rows:
            if not r.get("pm") or r.get("pm_res") is None:
                continue
            agree[0] += r["pm_res"] == r["res"]
            agree[1] += 1
            q = quotes(r)
            pm = sorted(r["pm"])
            yes_won = r["res"] == "yes"
            sig = {}
            for m in range(1, 14):
                t = r["close"] - m * 60
                pu = pm_at(pm, t)
                km = m + 1 if ALIGN else m  # the Kalshi minute that is contemporaneous with this print
                if pu is None or km not in q:
                    continue
                bid, ask = q[km]
                if ask - bid > 0.05:
                    continue
                sig[m] = (pu, bid, ask)
                # locked arbitrage (both venues, both fees): YES on Kalshi + Down on Polymarket, or NO on Kalshi + Up
                for kp, pp in ((ask, 1 - pu + 0.005), (1 - bid, pu + 0.005)):
                    if 0.01 < kp < 0.99 and 0.01 < pp < 0.99:
                        cost = kp + fee_per_contract(kp) + pp + fee_per_contract(pp)
                        if cost < 1:
                            arb.append({"coin": coin, "m": m, "cost": cost, "ts": r["close"]})
            for bname, ms in BUCKETS.items():
                for rule in ("follow", "average"):
                    for ex in ("now", "lag"):
                        for thr in THRS:
                            for m in sorted(ms, reverse=True):
                                if m not in sig:
                                    continue
                                pu, bid, ask = sig[m]
                                fair = pu if rule == "follow" else (pu + (bid + ask) / 2) / 2
                                if ex == "lag":
                                    km = m if ALIGN else m - 1
                                    if km not in q or km < 1:
                                        continue
                                    bid, ask = q[km]
                                side = None
                                if fair - ask > thr:
                                    side, p, won = "yes", ask, yes_won
                                elif (1 - fair) - (1 - bid) > thr:
                                    side, p, won = "no", 1 - bid, not yes_won
                                if side and 0.02 <= p <= 0.98:
                                    trades[(coin, bname, rule, ex, thr)].append(
                                        {"r": pnl_per_dollar(p, won), "won": won, "cl": int(r["close"]), "ts": r["close"],
                                         "p": p, "side": side, "m": m})
                                    break
        if rows:
            ndays[coin] = ((min(r["close"] for r in rows), max(r["close"] for r in rows)))
    lo = min(a for a, b in ndays.values())
    hi = max(b for a, b in ndays.values())
    dtr = (SPLIT - lo) / 86400
    dte = (hi - SPLIT) / 86400
    out = {"settle_agreement": agree, "train_days": dtr, "test_days": dte, "split": "2026-10-29",
           "from": datetime.fromtimestamp(lo, timezone.utc).isoformat(), "to": datetime.fromtimestamp(hi, timezone.utc).isoformat()}
    # arbitrage
    out["arb"] = {"hits": len(arb), "by_coin": {c: sum(1 for a in arb if a["coin"] == c) for c in ndays},
                  "mean_profit_per_set": (sum(1 - a["cost"] for a in arb) / len(arb)) if arb else 0,
                  "markets_with_hit": len({(a["coin"], a["ts"]) for a in arb})}
    # cells
    elig = {}
    for k, v in trades.items():
        a = [u for u in v if u["ts"] < SPLIT]
        if len(a) >= 60:
            elig[k] = summary(a, dtr)
    z = zbar(len(elig))
    ranked = sorted(elig.items(), key=lambda kv: -kv[1]["t"])
    out["eligible"] = len(elig)
    out["z_bar"] = z
    out["top"] = [{"cell": "|".join(map(str, k)), "train": s} for k, s in ranked[:12]]
    out["carried"] = []
    for k, s in ranked:
        if s["t"] >= z:
            b = [u for u in trades[k] if u["ts"] >= SPLIT]
            out["carried"].append({"cell": "|".join(map(str, k)), "train": s, "test": summary(b, dte)})
    # pooled pre-registered: follow, lag, thr 0.05, all coins, each bucket
    pooled = {}
    for bname in BUCKETS:
        for ex in ("now", "lag"):
            v = [u for c in ndays for u in trades[(c, bname, "follow", ex, 0.05)]]
            pooled["follow|%s|%s|0.05|all coins" % (bname, ex)] = {
                "train": summary([u for u in v if u["ts"] < SPLIT], dtr), "test": summary([u for u in v if u["ts"] >= SPLIT], dte)}
    out["pooled"] = pooled
    with open(os.path.join(HERE, "results_crypto_xvenue%s.json" % ("_aligned" if ALIGN else "")), "w") as f:
        json.dump(out, f, indent=1)
    fmt = lambda s: "n %5d edge %+6.2f%% [%+6.2f, %+6.2f] t %+5.2f win %.3f" % (
        s["n"], 100 * s["edge"], 100 * s["lo"], 100 * s["hi"], s["t"], s["win"]) if s["n"] else "n 0"
    print("settle agreement", agree, "train days %.1f test days %.1f" % (dtr, dte))
    print("arb", out["arb"])
    for k, v in pooled.items():
        print("%-34s TR %s | TE %s" % (k, fmt(v["train"]), fmt(v["test"])))
    print("eligible", len(elig), "z bar %.2f" % z)
    for c in out["top"]:
        print("  top", c["cell"], fmt(c["train"]))
    for c in out["carried"]:
        print("  CARRIED", c["cell"], fmt(c["train"]), "| TE", fmt(c["test"]))


if __name__ == "__main__":
    main()
