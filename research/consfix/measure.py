"""big-consfix: rank.py eval pass % + 6-month slot $ per plan x market (1,000 paths, rank seeds). python -X utf8 research/consfix/measure.py <out.json>"""
import sys,json
sys.path.insert(0,"research/plans"); import rank as R
R.AR.rapid_patch(R.AR.T_at(10)); S=R.SOA.data()["S"]
out={}
for p in ("mffu_builder_50k","mffu_builder_25k","mffu_rapid_eod_25k"):
    sp=R.spec(p)
    for s in R.SPANS:
        PE=R.U.mc_paths(S,s,1000,length=R.H_EVAL,seed=7); PF=R.U.mc_paths(S,s,1000,length=R.LEN,seed=23)
        e=R.eval_run(sp,PE); sl=R.slot_run(sp,PF)
        out[f"{p}|{s}"]={"pass":e["pass"],"fail":e["fail"],"med":e["med_days"],"net6":sl["net_6m"],"pays":sl["pays"],"first":sl["first_pay_med"]}
        print(p,s,out[f"{p}|{s}"],flush=True)
json.dump(out,open(sys.argv[1],"w"),indent=1)
