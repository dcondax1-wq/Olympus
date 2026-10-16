"""No-lookahead check for engine/ict_features.py: for every shadow candidate, the ICT features computed on bars TRUNCATED
at the signal bar (NQ and ES) must equal the features computed on the full series.

    python study_ict_lookahead.py [--from 2026-08-06] [--to 2026-10-16] [--n 80]
"""
import argparse

import study_ict_common as C
from engine import ict_features as I
from engine.data import load

ap = argparse.ArgumentParser()
ap.add_argument("--from", dest="a", default="2026-08-06")
ap.add_argument("--to", dest="z", default="2026-10-16")
ap.add_argument("--n", type=int, default=80)
args = ap.parse_args()

b = C.slice_days(load("NQ", "5m"), C.warm_from(args.a), args.z)          # exactly the bars C.run uses
es = C.slice_days(load("ES", "5m"), b.date_str[0], b.date_str[-1])
r = C.run(C.WIDE, "default", args.a, args.z)
full = I.Context(b, es)
bad = 0
rows = r["shadows"][: args.n]
for s in rows:
    f = s["f"]; i = f["_sig_i"]
    ctx = I.Context(b.slice(0, i + 1), es.slice(0, int((es.t <= b.t[i]).sum())))
    x1 = I.features(full, s["dir"], i, f["_arm_i"], f["_ext_i"], f["_pool"])
    x2 = I.features(ctx, s["dir"], i, f["_arm_i"], f["_ext_i"], f["_pool"])
    if x1 != x2:
        bad += 1
        print(s["day"], {k: (x1[k], x2[k]) for k in x1 if x1[k] != x2[k]})
print(f"checked {len(rows)} candidates, mismatches {bad}")
