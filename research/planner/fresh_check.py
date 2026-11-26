"""Post-hoc check on FRESH paths (seeds 101-104, never used before): today vs today+W3 vs 2nd Rapid 25K + W5 / W3.
    python -X utf8 research/planner/fresh_check.py -> research/planner/fresh_check.json"""
import json, os, sys, multiprocessing as mp
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import planner as P  # noqa: E402
P.AR.rapid_patch(P.AR.T_at(10)); S = P.SOA.data()["S"]
for pl in P.PRICE: P.spec(pl)
for mx in (P.LIT, P.LA, P.AT): P.by(mx); P.by(mx, True)
lit = [t["pts"] / t["risk"] for ts in P.by(P.LIT) for t in ts]
P.G["lit0"] = lit[-40:]
P.G["P"] = {m: P.paths(S, m, 1000, 101 + i) for i, m in enumerate(P.MKTS)}
jobs = [(p, t, m) for p, t in (("K0 today", "W0"), ("K0 today", "W3"), ("K0 today", "W5"), ("K2 + 2nd Rapid 25K", "W5"),
                               ("K2 + 2nd Rapid 25K", "W3"), ("K2 + 2nd Rapid 25K", "W0")) for m in P.MKTS]
out = {}
with mp.get_context("fork").Pool(4) as pool:
    for key, st in pool.imap_unordered(P.job, jobs):
        out["|".join(key)] = st
for p, t in (("K0 today", "W0"), ("K0 today", "W3"), ("K0 today", "W5"), ("K2 + 2nd Rapid 25K", "W5"), ("K2 + 2nd Rapid 25K", "W3"), ("K2 + 2nd Rapid 25K", "W0")):
    print(f"{p:20s} {t} " + " | ".join(f"{m} {out[f'{p}|{t}|{m}']['net12_mean']} cash {out[f'{p}|{t}|{m}']['cash_needed_p90']}" for m in P.MKTS))
json.dump(out, open(os.path.join(HERE, "fresh_check.json"), "w"), indent=1)
