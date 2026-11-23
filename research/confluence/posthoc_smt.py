"""POST-HOC (not pre-registered): LIT skipping setups WITH the SMT tag, the only tag whose split survived Holm. Money check + luck test."""
import collections, json, os, sys
import numpy as np
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "research", "confluence"))
import confluences as CF
from tools import setup_grade as SG
SG.setup()
LT = CF.lit_tags()
o0, U0, L0, T0 = SG.lit_score(); s0 = SG.lit_short(o0)
skip = {k for k, v in LT.items() if v["smt"]}
o, U, L, T = SG.lit_score(skip=skip); s = SG.lit_short(o, o0); ok, why = SG.lit_gate(s, s0)
kt = lambda t: (str(t["day"]), int(t["i"]), int(t["dir"]))
keys = collections.defaultdict(list); nsk = collections.Counter()
for t in T0:
    sp = CF.span3(t["day"])
    if sp and t["day"] >= "2025-04-14":
        keys[sp].append(kt(t)); nsk[sp] += kt(t) in skip
rng = np.random.default_rng(5); beat = collections.Counter(); N = 100
for _ in range(N):
    sk = set()
    for sp, ks in keys.items():
        sk |= {ks[i] for i in rng.permutation(len(ks))[:nsk[sp]]}
    oo, *_ = SG.lit_score(skip=sk, ref_eval=False)
    for sp in ("H1", "H2", "2021-25"):
        beat["lit:" + sp] += oo["lit"][sp]["net"] >= o["lit"][sp]["net"]
    for sp in ("H1", "H2"):
        beat["eval:" + sp] += oo["eval"][sp]["net"] >= o["eval"][sp]["net"]
res = {"note": "post-hoc, not pre-registered", "s": s, "ok": ok, "why": why, "skipped_traded": dict(nsk),
       "luck_p": {k: round((beat[k] + 1) / (N + 1), 3) for k in ("lit:H1", "lit:H2", "lit:2021-25", "eval:H1", "eval:H2")}}
print(json.dumps({k: res[k] for k in ("ok", "why", "skipped_traded", "luck_p")}, indent=1))
print({h: (s["lit"][h]["per_month"], s0["lit"][h]["per_month"], s["lit"][h]["dd"] if "dd" in s["lit"][h] else None) for h in s["lit"]})
json.dump(res, open(os.path.join(ROOT, "research", "confluence", "posthoc_smt.json"), "w"), indent=1, default=SG._j)
