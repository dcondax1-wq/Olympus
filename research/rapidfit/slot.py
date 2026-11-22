"""Rapid 25K slot (2026-11-22): (a) ATLAS only, (c) LIT + ATLAS (today), (d) Rapid EOD 50K, on research/plans/rank.py's engine.
Design: research/rapidfit/DESIGN.md.   python -X utf8 research/rapidfit/slot.py -> research/rapidfit/results.json"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "research", "plans"))
import rank as R

R.AR.rapid_patch(R.AR.T_at(10))
S = R.SOA.data()["S"]
PF = {sp: R.U.mc_paths(S, sp, 1000, length=R.LEN, seed=23) for sp in R.SPANS}
PE = {sp: R.U.mc_paths(S, sp, 1000, length=R.H_EVAL, seed=7) for sp in R.SPANS}
cands = {}
c = R.spec("mffu_rapid_eod_25k"); cands["c LIT + ATLAS on the 25K (today)"] = (c, ("LIT", "ATLAS"), {"LIT": 250.0, "ATLAS": 250.0})
a = R.spec("mffu_rapid_eod_25k"); a["BYe"] = R.RL.mix_by(("ATLAS",)); a["BYf"] = R.RL.mix_by(("ATLAS",), news=True)
cands["a ATLAS only on the 25K"] = (a, ("ATLAS",), {"LIT": 0.0, "ATLAS": 250.0})
d = R.spec("mffu_rapid_eod_50k"); cands["d Rapid EOD 50K in the slot (LIT + ATLAS)"] = (d, ("LIT", "ATLAS"), {"LIT": 500.0, "ATLAS": 500.0})
out = {}
for name, (sp, mix, usd) in cands.items():
    row = {}
    for s in R.SPANS:
        fx = R.SOA.plain_stats(R.RL.mix_by(mix), S, s, {**{k: 0.0 for k in R.RL.PRI}, **usd})
        row[s] = {"eval": R.eval_run(sp, PE[s]), "slot": R.slot_run(sp, PF[s]), "fixed": fx}
    out[name] = row
    print(name, " | ".join(f"{s} net ${row[s]['slot']['net_6m']} (${row[s]['slot']['net_6m']//6}/mo) pass {row[s]['eval']['pass']}%/{row[s]['eval']['fail']}% ~{row[s]['eval']['med_days']} 1st pay {row[s]['slot']['first_pay_med']} lost {row[s]['slot']['p_lost']}% nopay {row[s]['slot']['no_pay']}% | fixed {row[s]['fixed']['tpw']}/wk PF {row[s]['fixed']['pf']} ${row[s]['fixed']['net']} dd {row[s]['fixed']['max_dd']}" for s in R.SPANS))
json.dump(out, open(os.path.join(HERE, "results.json"), "w"), indent=1, default=float)
