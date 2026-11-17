#!/usr/bin/env python3
"""K5: honest ranges for the 'answer already public, buy the late favourite' cells. Zero-loss samples make a bootstrap
range far too narrow, so next to it: exact (Clopper-Pearson, one-sided 95%) upper bound on the loss rate and the edge at
that loss rate. Pooled family = the five pre-registered 'fav' cells of study.PREREG (no new search)."""
import json, os, sys, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import study  # noqa: E402
from lib import summary, fee_per_contract  # noqa: E402
from statistics import NormalDist
HERE = os.path.dirname(os.path.abspath(__file__))

def cp_upper(k, n, a=0.05):
    """one-sided upper bound on a binomial rate (bisection on the exact tail)."""
    from math import comb
    if n == 0: return 1.0
    lo, hi = k / n, 1.0
    for _ in range(60):
        m = (lo + hi) / 2
        tail = sum(comb(n, i) * m ** i * (1 - m) ** (n - i) for i in range(k + 1))
        lo, hi = (m, hi) if tail > a else (lo, m)
    return hi

def edge_at(loss, ps):
    return sum(((1 - loss) - p - fee_per_contract(p)) / (p + fee_per_contract(p)) for p in ps) / len(ps)

gas = study.gas_values(); allu = []
for s in study.CFG:
    rows = study.load(s)
    allu += study.units(s, rows)
FAM = [c for c in study.PREREG if c[2] == "fav"]
out = {}
for half in (False, True):
    v = [u for u in allu for (s, h, role, (lo, hi)) in FAM if u["s"] == s and u["h"] == h and u["role"] == role and lo <= u["p"] < hi and u["test"] == half]
    days = study.days_of(v); sm = summary(v, days)
    k = sum(not u["won"] for u in v); n = len(v); up = cp_upper(k, n)
    sm.update({"losses": k, "loss_rate_upper95": up, "edge_at_loss_upper": edge_at(up, [u["p"] for u in v]),
               "breakeven_loss": 1 - sum(u["p"] + fee_per_contract(u["p"]) for u in v) / n,
               "series": sorted({u["s"] for u in v}), "events": len({u["cl"] for u in v})})
    out["test" if half else "train"] = sm
    print("test" if half else "train", {k2: (round(x, 4) if isinstance(x, float) else x) for k2, x in sm.items()})
# each carried 95-98.5 cell: exact bound
res = json.load(open(os.path.join(HERE, "results.json")))
out["carried_exact"] = []
for c in res["carried"]:
    t = c["test"]
    if not t: continue
    k = round((1 - t["win"]) * t["n"]); up = cp_upper(k, t["n"])
    out["carried_exact"].append({"cell": c["cell"], "n": t["n"], "losses": k, "loss_upper95": up})
    print(c["cell"], "test n", t["n"], "losses", k, "loss-rate upper 95%% %.1f%%" % (100 * up), "(break-even ~3%)")
json.dump(out, open(os.path.join(HERE, "results_pooled.json"), "w"), indent=1)
