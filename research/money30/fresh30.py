"""30-day money: fresh account today, LIT+ATLAS, rank.py real-fills engine, horizon 21 sessions (+ eval) -> first $ and $ in 30 days."""
import sys, os, json, time
import numpy as np
ROOT = "/home/user/olympus"; sys.path.insert(0, ROOT + "/research/plans")
import rank as RK
from rank import U, SOA, AR
PRICES = {"mffu_builder_25k": 63.0, "mffu_builder_50k": 91.80, "mffu_rapid_eod_25k": 97.20, "mffu_rapid_eod_50k": 165.0,
          "lucid_pro_25k": 90.0, "lucid_pro_50k": 126.0, "lucid_flex_25k": 90.0, "lucid_flex_50k": 134.40,
          "fn_rapid_daily_25k": 100.0, "fn_rapid_daily_50k": 149.99, "fn_rapid_pro_50k": 149.99, "topstep_50k": 49.0,
          "apex_eod_50k": 35.0, "tpt_50k": 150.0, "alpha_zero_50k": 99.0}
plans = sys.argv[2].split(",")
RK.PLANS.update(PRICES)
for p in plans: RK.LABEL.setdefault(p, p)
AR.rapid_patch(AR.T_at(10))
S = SOA.data()["S"]
H = 63   # run 3 months; $ counted at session 21 (30 days)
N = int(sys.argv[1])
out = {}
for span in ("H1", "H2", "REF"):
    P = U.mc_paths(S, span, N, length=H, seed=31)
    for plan in plans:
        try:
            sp = RK.spec(plan)
        except Exception as ex:
            out.setdefault(plan, {})["err"] = repr(ex); continue
        rows = []
        for seq in P:
            e, f, wait, owner, first, passed, cost, o21 = sp["ev"](), None, 0, 0.0, None, None, sp["price"], None
            for k, si in enumerate(seq[:H]):
                if k == 21: o21 = owner
                if e is not None:
                    r, _ = e.step(sp["BYe"][si])
                    if r == "pass":
                        passed = k + 1; e, wait = None, RK.GAP
                    elif r in ("fail", "stuck"):
                        e = None; break          # 30-day view: no re-buy, the fee is lost
                    continue
                if f is None:
                    wait -= 1
                    if wait <= 0: f = sp["fund"]()
                    continue
                ev, x, _ = f.step(sp["BYf"][si])
                if ev in ("paid", "grad"):
                    owner += x; first = first or k + 1
                if ev in ("lost", "grad"):
                    break
            rows.append(((owner if o21 is None else o21) - cost, first, passed))
        net = np.array([r[0] for r in rows])
        fp = [r[1] for r in rows if r[1]]
        ps = [r[2] for r in rows if r[2]]
        out.setdefault(plan, {})[span] = {"net30_p50": round(float(np.median(net))), "net30_p10": round(float(np.percentile(net, 10))),
            "net30_mean": round(float(net.mean())), "p_paid30": round(100 * len(fp) / N, 1), "first_pay_med_sessions": float(np.median(fp)) if fp else None,
            "pass_in30": round(100 * len(ps) / N, 1), "pass_med": float(np.median(ps)) if ps else None, "gap": RK.GAP, "p_paid_by21": round(100*sum(1 for r in rows if r[1] and r[1]<=21)/N,1), "net30_p90": round(float(np.percentile(net,90)))}
        print(plan, span, out[plan][span], flush=True)
json.dump(out, open(sys.argv[3], "w"), indent=1)
