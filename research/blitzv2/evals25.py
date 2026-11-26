"""BLITZ v2: standalone 25K / Rapid EOD 25K evals at account C's eval size ($400 a trade = 40% of the $1,000 room), x1."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, "research", "moretrades")); os.chdir(ROOT)
import blitzv2 as BZ, moretrades as MT
from tools import scalp_na_lib as N
BZ.USD = 400.0
A = {"Builder 25K": {**MT.ACCTS["25K"], "x": 1.0}, "Rapid EOD 25K": {**MT.ACCTS["Rapid25K"], "x": 1.0}}
B1, B5 = N.bars(1), N.bars(5)
res = json.load(open(os.path.join(HERE, "results.json")))
for nm, v in BZ.V.items():
    T1, T5 = BZ.usd(BZ.sim(B1, v)), BZ.usd(BZ.sim(B5, v))
    out = {}
    for sp, (tf, k) in BZ.SPANS.items():
        S = N.sessions(B1 if tf == 1 else B5, k)
        dl, _ = MT.daily([t for t in (T1 if tf == 1 else T5) if S[0] <= t["day"] <= S[-1]])
        p = [dl[s][0] if s in dl else 0.0 for s in S]; lo = [min(dl[s][1], 0) if s in dl else 0.0 for s in S]
        out[sp] = {a: MT.evals(p, lo, x) for a, x in A.items()}
    res["variants"][nm]["evals_at_400"] = out
    print(nm[:40].ljust(40), " | ".join(f"{sp}: B25 {o['Builder 25K']['pass']}/{o['Builder 25K']['fail']} med {o['Builder 25K']['med']} Rapid {o['Rapid EOD 25K']['pass']}/{o['Rapid EOD 25K']['fail']}" for sp, o in out.items()))
json.dump(res, open(os.path.join(HERE, "results.json"), "w"), indent=1, default=float)
