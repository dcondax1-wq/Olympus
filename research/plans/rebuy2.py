"""The top plans with a RE-BUY LIMIT (lead 2026-11-22, for the Decide cards): at most 2 re-buys = 3 evals in all per slot;
after that the slot stops (no more fees). Same engine, paths and prices as rank.py."""
import json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rank as R


def slot_capped(sp, paths, max_evals=3):
    rows = []
    for seq in paths:
        cost, owner, evals, lost, pays, first_pay = sp["price"], 0.0, 1, 0, 0, None
        e, f, wait, done = sp["ev"](), None, 0, False
        for k, si in enumerate(seq[:R.LEN]):
            if done:
                break
            if e is not None:
                r, _ = e.step(sp["BYe"][si])
                if r == "pass":
                    e, wait = None, R.GAP
                elif r in ("fail", "stuck"):
                    if evals >= max_evals:
                        done = True
                    else:
                        e = sp["ev"](); cost += sp["price"]; evals += 1
                continue
            if f is None:
                wait -= 1
                if wait <= 0:
                    f = sp["fund"]()
                continue
            ev, x, _ = f.step(sp["BYf"][si])
            if ev in ("paid", "grad"):
                owner += x; pays += 1; first_pay = first_pay or k + 1
            if ev in ("lost", "grad"):
                lost += ev == "lost"; f = None
                if evals >= max_evals:
                    done = True
                else:
                    e = sp["ev"](); cost += sp["price"]; evals += 1
        rows.append((owner, cost, evals, lost, pays, first_pay))
    net = np.array([r[0] - r[1] for r in rows])
    fp = [r[5] for r in rows if r[5]]
    return {"net_6m": round(float(net.mean())), "net_p10": round(float(np.percentile(net, 10))),
            "owner_6m": round(float(np.mean([r[0] for r in rows]))), "fees_6m": round(float(np.mean([r[1] for r in rows])), 1),
            "worst": round(float(net.min())), "p_neg": round(100.0 * float((net < 0).mean()), 1),
            "evals": round(float(np.mean([r[2] for r in rows])), 2), "first_pay_med": float(np.median(fp)) if fp else None,
            "no_pay": round(100.0 * sum(1 for r in rows if not r[4]) / len(rows), 1)}


R.AR.rapid_patch(R.AR.T_at(10))
S = R.SOA.data()["S"]
PF = {sp: R.U.mc_paths(S, sp, 1000, length=R.LEN, seed=23) for sp in R.SPANS}
out = {}
for plan in ("mffu_rapid_eod_50k", "fn_rapid_daily_50k", "lucid_pro_50k"):
    sp = R.spec(plan)
    out[plan] = {s: slot_capped(sp, PF[s]) for s in R.SPANS}
    print(plan, " | ".join(f"{s} net ${out[plan][s]['net_6m']} p10 ${out[plan][s]['net_p10']} worst ${out[plan][s]['worst']} lose-money {out[plan][s]['p_neg']}% fees ${out[plan][s]['fees_6m']} 1st pay {out[plan][s]['first_pay_med']}" for s in R.SPANS))
R0 = json.load(open(R.OUT)); R0["rebuy2"] = out; json.dump(R0, open(R.OUT, "w"), indent=1, default=float)
