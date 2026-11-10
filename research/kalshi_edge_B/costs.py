#!/usr/bin/env python3
"""Trading-cost map: how much true edge (vs the mid price) a taker needs, by price band, from real quotes (5 min before close).
need = half spread + taker fee 0.07*p*(1-p).  A resting (maker) order saves the half spread and pays 0.0175*p*(1-p) but is only
filled when the market moves toward you (adverse selection, measured in study.py 'maker').   -> costs.json"""
import json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import *
from study import prep, quote

HERE = os.path.dirname(os.path.abspath(__file__))
out = {}
for nm in ("KXBTC15M", "KXETH15M", "KXBTCD"):
    if not os.path.exists(os.path.join(DATA, nm + ".json.gz")):
        continue
    rows = prep(nm + ".json.gz")
    bands = [(0.05, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 0.9), (0.9, 0.95), (0.95, 0.99)]
    tab = []
    for lo, hi in bands:
        sp, need, n = [], [], 0
        for r in rows:
            q = quote(r, 5)
            if not q:
                continue
            b, a = q
            mid = (a + b) / 2
            if lo <= mid < hi and a - b <= 0.2:
                sp.append(a - b)
                need.append((a - b) / 2 + fee(a))
        if sp:
            tab.append({"mid_band": "%.2f-%.2f" % (lo, hi), "n": len(sp), "median_spread_c": round(100 * float(np.median(sp)), 2),
                        "taker_needs_edge_c": round(100 * float(np.mean(need)), 2),
                        "maker_fee_c_at_mid": round(100 * fee((lo + hi) / 2, 0.0175), 2)})
    out[nm] = tab
json.dump(out, open(os.path.join(HERE, "costs.json"), "w"), indent=1)
for k, v in out.items():
    print(k)
    for t in v:
        print("  ", t)
