#!/usr/bin/env python3
"""Replication of the ONE hourly candidate that looked alive on BTC ('late favourite': buy the 97-99c side 10 min before the
hour closes) on an independent asset (ETH hourly ladders) and at neighbouring horizons.  The rule was frozen from BTC before looking
at ETH.  -> results_replication.json"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lib import *
from study import prep, favourites, model_scan, basis_sigma

HERE = os.path.dirname(os.path.abspath(__file__))
out = {}
for nm, sym in (("KXBTCD", "BTC"), ("KXETHD", "ETH")):
    if not os.path.exists(os.path.join(DATA, nm + ".json.gz")):
        continue
    rows = prep(nm + ".json.gz")
    out[nm] = {"markets": len(rows), "events": len({r["e"] for r in rows}),
               "favourites": favourites(rows, nm, [5, 8, 10, 12, 15, 20], [(0.95, 0.97), (0.97, 0.99)])}
for nm in ("KXBTC15M", "KXETH15M"):
    rows = prep(nm + ".json.gz")
    out[nm + "_favourites"] = {"markets": len(rows), "favourites": favourites(rows, nm, [3, 5, 8, 10], [(0.90, 0.95), (0.95, 0.97), (0.97, 0.99)])}
json.dump(out, open(os.path.join(HERE, "results_replication.json"), "w"), indent=1)
for nm, v in out.items():
    print(nm, v["markets"], v.get("events"))
    for f in v["favourites"]:
        a = f["all"]
        if a.get("n", 0) < 20:
            continue
        print("  tau", f["tau_min"], f["band"], "n", a["n"], "ev", a["clusters"], "edge", a["edge"], a["ci"], "win", a["win"], "| tr", f["train"].get("edge"), "va", f["val"].get("edge"), "te", f["test"].get("n"), f["test"].get("edge"))
