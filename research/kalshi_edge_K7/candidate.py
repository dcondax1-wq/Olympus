#!/usr/bin/env python3
"""K7 step 6: write research/lab/kalshi_candidates/K7.json ONLY if a carried cell (or a pre-registered pooled rule) passes the
held-out half: test net per $1 > 0 with its 95% cluster range above 0, at least 100 test trades from 20+ events, and train net > 0.
Otherwise it writes nothing and says so."""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "lab", "kalshi_candidates", "K7.json")
R = json.load(open(os.path.join(HERE, "results.json")))


def passes(tr, te):
    return (te.get("n", 0) >= 100 and te.get("events", 0) >= 20 and te["net_per_1"] > 0 and te["ci95"][0] is not None
            and te["ci95"][0] > 0 and tr.get("n", 0) and tr["net_per_1"] > 0)


cands = []
for c in R["carried"]:
    if passes(c["train"], c["test"]):
        cands.append(("carried", "%s / %s / %s" % (c["fam"], c["band"], c["h"]), c["train"], c["test"]))
for k, v in R["prereg_pooled"].items():
    if passes(v["train"], v["test"]):
        cands.append(("prereg", k, v["train"], v["test"]))
for kind, name, tr, te in cands:
    print("PASS", kind, name, "test n", te["n"], "net", te["net_per_1"], te["ci95"])
if not cands:
    print("no rule passes the held-out half: K7.json NOT written")
    if os.path.exists(OUT):
        os.remove(OUT)
