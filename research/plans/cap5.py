"""SENSITIVITY (labelled; not the pre-registered ranking): CLAUDE.md says MFFU sim-funded accounts get only 5 sim payouts
(then the live move); firm_rules.json lists no cap for the Rapid. Re-run the MFFU Rapid plans with max_payouts = 5 (the 5th
payout ends the slot's funded account like Lucid's / FundedNext's caps; the slot buys a new eval, as for every capped plan)."""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rank as R
R.AR.rapid_patch(R.AR.T_at(10))
S = R.SOA.data()["S"]
PF = {sp: R.U.mc_paths(S, sp, 1000, length=R.LEN, seed=23) for sp in R.SPANS}
out = {}
for plan in ("mffu_rapid_eod_25k", "mffu_rapid_eod_50k"):
    sp = R.spec(plan)
    F5 = {**sp["F"], "max_payouts": 5}
    ask = sp["F"]["pay_min"]
    sp["fund"] = lambda F5=F5, ask=ask, sp=sp: R.Funded(R.U.UP50 if "50k" in plan else R.U.UP25, F5, sp["z"], ask)
    out[plan] = {s: R.slot_run(sp, PF[s]) for s in R.SPANS}
    print(plan, " | ".join(f"{s} net ${out[plan][s]['net_6m']} owner ${out[plan][s]['owner_6m']} pays {out[plan][s]['pays']} lost {out[plan][s]['p_lost']}%" for s in R.SPANS))
R0 = json.load(open(R.OUT)); R0["cap5_sensitivity"] = out; json.dump(R0, open(R.OUT, "w"), indent=1, default=float)
