"""Deep dive on the single cell that was positive in all 3 spans (Monday long, 09:30 -> 15:55, no target) + a joint null."""
import json, os, random, sys, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
from edge_c import Sim, windows, pick, lit_days, in_span, SPANS, daily, corr
rng = random.Random(11)
sim = Sim(); LD = lit_days(); W = windows(sim)
w = W["dow_mon"]
T = pick(sim, w, 570, 955, None)
by = collections.defaultdict(lambda: [0, 0.0])
for t in T:
    by[t["s1"][:4]][0] += 1; by[t["s1"][:4]][1] += t["usd"]
print("by year n/net:", {k: (v[0], round(v[1])) for k, v in sorted(by.items())})
for sp in SPANS:
    u = sorted([t["usd"] for t in T if in_span(t["s1"], sp)], reverse=True)
    tot = sum(u)
    print(sp, "n", len(u), "net", round(tot), "top1 share", round(u[0]/tot, 2) if tot > 0 else None,
          "top3 share", round(sum(u[:3])/tot, 2) if tot > 0 else None, "net without top3", round(tot - sum(u[:3])),
          "max qty", max(t["q"] for t in T if in_span(t["s1"], sp)))
D = daily(T)
print("corr LIT / mondays-LIT-off $/mo:", {sp: corr(D, LD, sim.st, sp) for sp in SPANS})
# joint null: random day sets of the same size per span (long, no target, 09:30->15:55); P(all three spans net>0)
pool = sim.pool(570, 955, 1, None)
n = {sp: sum(1 for s in w if in_span(s, sp)) for sp in SPANS}
days = {sp: [s for s in sim.S if in_span(s, sp)] for sp in SPANS}
hit = 0; N = 4000
for _ in range(N):
    ok = True
    for sp in SPANS:
        ss = rng.sample(days[sp], n[sp])
        if sum((pool[s] or {"usd": 0})["usd"] for s in ss) <= 0:
            ok = False; break
    hit += ok
print("P(random long-only same-size day sets positive in all 3 spans) =", round(hit/N, 3), "(the Monday cell is 1 of 1 such; 28 long/short window cells tried)")
