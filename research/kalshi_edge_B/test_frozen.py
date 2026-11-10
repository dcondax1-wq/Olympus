#!/usr/bin/env python3
"""FROZEN-RULE TEST (declared before the data was fetched):

    'In a 15-minute crypto up/down market, 8 minutes before it closes, buy the favourite if its ask is 95-97c.'

That cell looked good on BTC and ETH 15m in study.py (Oct 10 - Nov 10).  Here it is run on data NEVER used to find it:
  * the OLDER block (two months before Oct 10) for BTC and ETH  = out-of-time
  * SOL and XRP 15-minute markets                                = out-of-asset
Neighbouring horizons (6,7,9,10 min) and a 1-minute execution delay are shown so a lone lucky cell can be told from a real pocket.
    python research/kalshi_edge_B/test_frozen.py   -> results_frozen.json
"""
import json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import *
from study import prep, quote, summarise, buy, day

HERE = os.path.dirname(os.path.abspath(__file__))
LO, HI = 0.95, 0.97


def fav_trades(rows, tau, lo=LO, hi=HI, delay=0):
    prof, cost, wins, grp = [], [], [], []
    for r in rows:
        q = quote(r, tau)
        qx = quote(r, tau - delay) if delay else q
        if not q or not qx:
            continue
        b, a = q
        side = "yes" if b >= 0.5 else "no"
        p_sig = a if side == "yes" else 1 - b
        if not (lo <= p_sig < hi):
            continue
        px = qx[1] if side == "yes" else 1 - qx[0]
        pr, w = buy(r, side, px)
        prof.append(pr); cost.append(px); wins.append(w); grp.append(day(r))
    return prof, cost, wins, grp


def main():
    sets = {}
    for nm, label in (("KXBTC15M_older", "BTC older block (out-of-time)"), ("KXETH15M_older", "ETH older block (out-of-time)"),
                      ("KXSOL15M", "SOL (out-of-asset)"), ("KXXRP15M", "XRP (out-of-asset)"),
                      ("KXBTC15M", "BTC discovery block"), ("KXETH15M", "ETH discovery block")):
        if os.path.exists(os.path.join(DATA, nm + ".json.gz")):
            sets[label] = prep(nm + ".json.gz")
    out = {"rule": "favourite ask in [0.95,0.97) at 8 min before close, taker, fee 0.07p(1-p) per contract", "sets": {}}
    pooled_new = ([], [], [], [])
    for label, rows in sets.items():
        o = {"markets": len(rows), "days": len({day(r) for r in rows})}
        for tau in (6, 7, 8, 9, 10):
            o["tau%d" % tau] = summarise(*fav_trades(rows, tau))
        o["tau8_delay1"] = summarise(*fav_trades(rows, 8, delay=1))
        o["tau8_band_94_98"] = summarise(*fav_trades(rows, 8, 0.94, 0.98))
        out["sets"][label] = o
        if "discovery" not in label:
            for acc, v in zip(pooled_new, fav_trades(rows, 8)):
                acc.extend(v)
    out["pooled_new_data_tau8"] = summarise(*pooled_new)
    nloss = len(pooled_new[2]) - sum(pooled_new[2])
    out["pooled_new_data_tau8"]["losses"] = nloss
    # Bonferroni-flavoured bound: 99.9% Wilson lower bound on the win rate vs the break-even win rate
    n, w = len(pooled_new[2]), sum(pooled_new[2])
    if n:
        lo999 = wilson(w, n, z=3.29)[0]
        be = float(np.mean([c + fee(c) for c in pooled_new[1]]))
        out["pooled_new_data_tau8"]["win_wilson_99_9_lo"] = round(lo999, 4)
        out["pooled_new_data_tau8"]["breakeven_win"] = round(be, 4)
    json.dump(out, open(os.path.join(HERE, "results_frozen.json"), "w"), indent=1)
    for label, o in out["sets"].items():
        print(label, o["markets"], "markets", o["days"], "days")
        for k in ("tau6", "tau7", "tau8", "tau9", "tau10", "tau8_delay1", "tau8_band_94_98"):
            a = o[k]
            if a.get("n"):
                print("   %-16s n=%-4d win=%.4f edge=%+.4f ci=%s" % (k, a["n"], a["win"], a["edge"], a["ci"]))
            else:
                print("   %-16s n=0" % k)
    print("POOLED NEW DATA tau8:", out["pooled_new_data_tau8"])


if __name__ == "__main__":
    main()
