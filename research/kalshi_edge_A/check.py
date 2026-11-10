#!/usr/bin/env python3
"""python research/kalshi_edge_A/check.py : sanity tests (no network). Fee formula, Wilson, and that the verdict files agree."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import analyze as A
# fee: the bot's feed was checked as 0.07*contracts*p*(1-p) to the cent (research/writeups/2026-11-04_kalshi_edges.md)
assert abs(0.07 * 17 * 0.96 * 0.04 - 0.0457) < 1e-3
lo, hi = A.wilson(98, 100)
assert 0.92 < lo < 0.95 and hi > 0.99
assert A.klass("KXBTC15M") == "15min crypto" and A.klass("KXBTCD") == "hourly crypto above/below" and A.klass("KXINXU") == "index"
r = json.load(open(os.path.join(HERE, "results.json")))
rules = json.load(open(os.path.join(HERE, "edge_rules_A.json")))
n_surv = r["cells_survive"] + sum(1 for c in r["prereg"] if c["survives"])
assert (n_surv == 0) == (rules["status"] == "no_edge_found" and rules["rules"] == []), "verdict file disagrees with results.json"
assert r["train_end"] < r["data_to"]
print("ok: survivors =", n_surv, "| markets", r["markets"], "| trade-units", r["units"])
