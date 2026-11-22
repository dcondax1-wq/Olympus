"""Daily screen: do the prior-close cross-asset features predict the next RTH day's direction / range? (no trading)."""
import numpy as np, json
from feat import *
f = F(); B = f.B
out = {}
spans = {"H1": ("2026-01-01", "2026-06-30"), "H2": ("2026-07-01", LAST), "2021-25": ("2021-11-01", "2025-12-31")}
for nm in f.pr:
    p = f.pr[nm]
    for sp, (a, z) in spans.items():
        ks = [k for k, x in enumerate(B.days) if a <= x <= z and np.isfinite(p[k])]
        if len(ks) < 20: continue
        ks = np.array(ks)
        r = f.ret[ks] / B.O[ks, 0] * 1e4; rg = f.rng[ks] / B.O[ks, 0] * 1e4; pp = p[ks]
        row = {}
        for lab, m in (("lo<33", pp < 33), ("mid", (pp >= 33) & (pp < 67)), ("hi>=67", pp >= 67)):
            row[lab] = (int(m.sum()), round(float(r[m].mean()), 1) if m.sum() else None, round(float(rg[m].mean()), 0) if m.sum() else None)
        out[f"{nm}|{sp}"] = row
        print(nm, sp, row)
json.dump(out, open("screen.json", "w"), indent=1)
