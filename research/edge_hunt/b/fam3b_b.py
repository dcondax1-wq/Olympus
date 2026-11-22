"""Family 3b: ES/NQ relative strength at a ROLLING sweep (bar pokes beyond the last-12-bar swing extreme and closes back inside),
10:00-14:00, 1 trade a day. ES from 2025-04-14 only. Control = no RS condition. 8 variants + control."""
import json, numpy as np
from feat import *
import e2_new_strats as E2
B = DS.D(); S = E2.ES(); TICK = DS.TICK; col = DS.col_of
KS = [k for k, x in enumerate(B.days) if x <= LAST and np.isfinite(S.O0[k])]
def run(sign, z, tg, lb=12):
    out = []
    for k in KS:
        H, L, C, O = B.H[k], B.L[k], B.C[k], B.O[k]
        for j in range(max(lb, 6), col((14, 0)) + 1):
            hi, lo = H[j - lb:j].max(), L[j - lb:j].min()
            d = -1 if (H[j] > hi and C[j] < hi) else 1 if (L[j] < lo and C[j] > lo) else 0
            if not d: continue
            sN, sE = B.sig[14][k, j], S.sig[k, j]
            if not (np.isfinite(sN) and np.isfinite(sE) and sN > 0 and sE > 0 and np.isfinite(S.C[k, j])): continue
            sp = (C[j] - O[0]) / sN - (S.C[k, j] - S.O0[k]) / sE
            ok = True
            if sign == "lag": ok = (sp <= -z) if d == 1 else (sp >= z)
            elif sign == "lead": ok = (sp >= z) if d == 1 else (sp <= -z)
            if not ok: continue
            ext = H[j] if d == -1 else L[j]
            w = E2.walk(k, j, d, ext + (TICK if d == -1 else -TICK), tgt=B.VW[k, j] if tg == "vwap" else None, rr=2.0 if tg == "r2" else None)
            if w: out.append(w)
            break
    return out
res = {}; SP = ("H1", "H2", "2025")
for sign, z in (("none", 0), ("lag", 0.5), ("lag", 1.0), ("lead", 0.5), ("lead", 1.0)):
    for tg in ("r2", "vwap"):
        if sign == "none" and False: continue
        T = DS.booked(run(sign, z, tg)); cid = f"{sign}_z{z}_{tg}"
        res[cid] = {s: DS.stats(T, s) for s in SP + ("all",)}
        print(cid, {s: (res[cid][s].get('n'), res[cid][s].get('tpw'), res[cid][s].get('pf'), res[cid][s].get('net')) for s in SP})
json.dump(res, open("fam3b_b.json", "w"))
