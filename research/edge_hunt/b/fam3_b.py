"""Family 3: ES/NQ relative strength AT a PDH/PDL sweep-reclaim (ES from 2025-04-14 only). 8 variants + coin-flip twins."""
import json, numpy as np
from feat import *
import e2_new_strats as E2
B = DS.D(); S = E2.ES(); X = E2.E(); TICK = DS.TICK; col = DS.col_of
KS = [k for k in f_ok] if False else [k for k, x in enumerate(B.days) if x <= LAST and np.isfinite(S.O0[k])]
def run(sign, z, tg, last=(12, 0)):
    lc = col(last); out = []
    for k in KS:
        ph, pl = X.PH[k], X.PL[k]
        if not (np.isfinite(ph) and np.isfinite(pl)): continue
        H, L, C, O = B.H[k], B.L[k], B.C[k], B.O[k]
        if not (pl < O[0] < ph): continue
        done = False
        for j in range(1, lc + 1):
            for d, lvl in ((-1, ph), (1, pl)):
                px = H[:j].max() if d == -1 else L[:j].min()
                sw = (H[j] > lvl and px <= lvl) if d == -1 else (L[j] < lvl and px >= lvl)
                if not sw: continue
                jr = j if ((C[j] < lvl) if d == -1 else (C[j] > lvl)) else (j + 1 if j + 1 <= lc and ((C[j + 1] < lvl) if d == -1 else (C[j + 1] > lvl)) else None)
                if jr is None: continue
                sN, sE = B.sig[14][k, jr], S.sig[k, jr]
                if not (np.isfinite(sN) and np.isfinite(sE) and sN > 0 and sE > 0 and np.isfinite(S.C[k, jr])): continue
                sp = (B.C[k, jr] - O[0]) / sN - (S.C[k, jr] - S.O0[k]) / sE      # NQ minus ES, noise-sigma units since the open
                # d=+1 (long after a low sweep): "lag" = NQ weaker than ES (sp <= -z); d=-1 mirrored
                lag = (sp <= -z) if d == 1 else (sp >= z)
                lead = (sp >= z) if d == 1 else (sp <= -z)
                if (sign == "lag" and lag) or (sign == "lead" and lead):
                    ext = H[j:jr + 1].max() if d == -1 else L[j:jr + 1].min()
                    w = E2.walk(k, jr, d, ext + (TICK if d == -1 else -TICK), tgt=B.VW[k, jr] if tg == "vwap" else None, rr=2.0 if tg == "r2" else None)
                    if w: out.append(w)
                done = True; break
            if done: break
    return out
SP = ("H1", "H2", "2025")
res = {}
for sign in ("lag", "lead"):
    for z in (0.5, 1.0):
        for tg in ("r2", "vwap"):
            T = DS.booked(run(sign, z, tg))
            res[f"{sign}_z{z}_{tg}"] = {s: DS.stats(T, s) for s in SP + ("all",)}
            print(f"{sign}_z{z}_{tg}", {s: (res[f'{sign}_z{z}_{tg}'][s].get('n'), res[f'{sign}_z{z}_{tg}'][s].get('pf'), res[f'{sign}_z{z}_{tg}'][s].get('net')) for s in SP})
json.dump(res, open("fam3_b.json", "w"))
