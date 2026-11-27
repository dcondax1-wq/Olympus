"""25K / Rapid EOD 25K / 50K evals at account C's eval size ($400 a trade = 40% of the $1,000 room), 40 sessions, rolling starts. -> results.json evals_at_400"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import blitzmore as M
from tools import scalp_na_lib as N
M.USD = 400.0
A = {"Builder 25K": {**M.MT.ACCTS["25K"], "x": 1.0}, "Rapid EOD 25K": {**M.MT.ACCTS["Rapid25K"], "x": 1.0}, "Builder 50K": {**M.MT.ACCTS["50K"], "x": 1.0}}
B1, B5 = N.bars(1), N.bars(5)
res = json.load(open(os.path.join(HERE, "results.json")))
for nm, o in res["variants"].items():
    cfg = M.V.get(nm) if nm in M.V else None
    if cfg is None:                                   # M13 (= today when nothing survived)
        cfg = {}
    T1, T5 = M.usd(M.sim(B1, cfg)), M.usd(M.sim(B5, cfg))
    out = {}
    for sp, (tf, k) in M.SPANS.items():
        S = N.sessions(B1 if tf == 1 else B5, k)
        dl, _ = M.MT.daily([t for t in (T1 if tf == 1 else T5) if S[0] <= t["day"] <= S[-1]])
        p = [dl[s][0] if s in dl else 0.0 for s in S]; lo = [min(dl[s][1], 0) if s in dl else 0.0 for s in S]
        out[sp] = {a: M.MT.evals(p, lo, x) for a, x in A.items()}
    o["evals_at_400"] = out
    print(nm[:30].ljust(30), " | ".join(f"{sp}: B25 {v['Builder 25K']['pass']}/{v['Builder 25K']['fail']} med {v['Builder 25K']['med']} R25 {v['Rapid EOD 25K']['pass']}/{v['Rapid EOD 25K']['fail']} 50K {v['Builder 50K']['pass']}/{v['Builder 50K']['fail']}" for sp, v in out.items()))
json.dump(res, open(os.path.join(HERE, "results.json"), "w"), indent=1, default=float)
