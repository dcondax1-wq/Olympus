"""Rapid EOD 50K in a 2025-like market (the one plan research/badcase did not run). Same engine and paths as research/badcase
(rank.spec, badcase.slot_full, 1,000 paths, seeds 23 / 7).    python -X utf8 research/evalroi/rapid50_y25.py -> rapid50_y25.json"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "research", "plans")); sys.path.insert(0, os.path.join(ROOT, "research", "badcase")); sys.path.insert(0, ROOT)
import rank as R  # noqa: E402
import badcase as BC  # noqa: E402
R.AR.rapid_patch(R.AR.T_at(10))
S = R.SOA.data()["S"]
sp = R.spec("mffu_rapid_eod_50k")
PE, PF = R.U.mc_paths(S, "Y25", 1000, length=R.H_EVAL, seed=7), R.U.mc_paths(S, "Y25", 1000, length=R.LEN, seed=23)
out = {"plan": "mffu_rapid_eod_50k", "price": 165.0, "Y25": {"eval": R.eval_run(sp, PE), "slot": BC.slot_full(sp, PF)}}
json.dump(out, open(os.path.join(HERE, "rapid50_y25.json"), "w"), indent=1)
print(json.dumps(out["Y25"]))
