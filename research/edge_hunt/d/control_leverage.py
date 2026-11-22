"""Control for the one meta-label version that clears the money gate (tree F12 up-only 1.5x): the SAME average leverage with no
model (every trade x1.167, and x1.25), scored identically. If a flat multiplier makes the same $, the model added nothing."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import E, HERE, SP, log_variant, row, span_sum, verdict
import meta_label as ML

rows = ML.build()
U0 = [r["u"] for r in rows]
base_o, _, base_L = E.evaluate(U=[{**u, "m": 1.0} for u in U0], fund=True)
res = {}
mm = ML.walk_forward(rows, ML.F12, "tree", "D_up15")
ups = sum(1 for v in mm.values() if v > 1)
print("up-only trades:", ups, "of", len(mm), "mean multiplier", sum(mm.values()) / len(mm))
for nm, m in (("ctrl_flat_1.167x", 1.167), ("ctrl_flat_1.25x", 1.25)):
    U = [{**u, "m": m} for u in U0]
    o, _, L = E.evaluate(U=U, fund=True)
    s = E.short(o, base_o)
    s["pass"] = verdict(s)
    res[nm] = s
    log_variant("D-meta", nm, "flat multiplier control", {"d_lit": s["d_lit"], "d_eval": s["d_eval"], "pass": s["pass"]})
    print(row(nm, s), "pass", s["pass"], "fund", {k: (v["per_month"], v["loss_6m"], v["any_pay"]) for k, v in o["fund"].items()}, flush=True)
json.dump(res, open(os.path.join(HERE, "control_leverage_results.json"), "w"), indent=1, default=float)
