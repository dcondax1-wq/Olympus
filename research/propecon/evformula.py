"""EV per eval dollar = P(pass in 60 sessions) x E(owner $ from that funded account before it blows / closes, 6 months) - fee."""
import json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import logging; logging.disable(logging.ERROR)
import unit as X
R, B = X.R, X.B
PR = {"mffu_builder_50k": "B50", "mffu_builder_25k": "B25", "mffu_rapid_eod_25k": "R25", "mffu_rapid_eod_50k": "R50",
      "fn_rapid_daily_50k": "FN", "lucid_pro_50k": "LU"}
POL = {"today": None, "AGG2 eval": ("LAB", 2.0, 2.0, "LA", 1.0, 1.0, "plan"), "LIT-only": ("L", 1.0, 1.0, "L", 1.0, 1.0, "min")}
TODAYB = {"R50": ("LA", 0.5, 1.0, "LA", 1.0, 1.0, "plan")}
out = {}
for plan in PR:
    for pn, pol in POL.items():
        pol = pol or TODAYB.get(PR[plan], ("LA", 1.0, 1.0, "LA", 1.0, 1.0, "plan"))
        pmax = 4 if plan.startswith("mffu_builder") else None
        sp = X.build(plan, *pol, pmax=pmax)
        B.CFG.clear(); B.CFG.update(sp["knobs"])
        for span in ("H1", "H2", "REF"):
            ev = R.eval_run(sp, X.paths(span, 1000, 60, 7))
            own, lost, fp = [], 0, []
            for seq in X.paths(span, 1000, 126, 23):
                f, o = sp["fund"](), 0.0
                for k, si in enumerate(seq):
                    e, x, _ = f.step(sp["BYf"][si])
                    if e in ("paid", "grad"): o += x; fp.append(k + 1) if o == x else None
                    if e in ("lost", "grad"): lost += e == "lost"; break
                own.append(o)
            Eo, pp = float(np.mean(own)), ev["pass"] / 100
            price = R.PLANS[plan]
            out[f"{plan}|{pn}|{span}"] = {"p_pass": ev["pass"], "pass_med": ev["med_days"], "E_funded_owner": round(Eo),
                "p_funded_lost": round(lost / 10, 1), "first_pay_med": float(np.median(fp)) if fp else None, "fee": price,
                "EV_per_eval": round(pp * Eo - price), "EV_per_eval_dollar": round((pp * Eo - price) / price, 2)}
            print(plan, pn, span, out[f"{plan}|{pn}|{span}"], flush=True)
        B.CFG.clear()
json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "evformula.json"), "w"), indent=0)
