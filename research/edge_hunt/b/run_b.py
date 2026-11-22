"""Lane B grid: gamma/vol day-type switch (trend vs fade) + ES/NQ relative strength at a sweep. Paper only.
Pick on 2026 H1 only; H2 (Jul-Oct16), 2025, 2021-24 untouched. Every cell logged -> grid_b.json (count printed)."""
import json, collections, itertools
import numpy as np
from feat import *
import e2_new_strats as E2
B = DS.D(); f = F(); TICK = DS.TICK
col = DS.col_of
KS = f.k_ok

def orb_trend(stopk, ex, last=(13, 0)):
    out = []; lc = col(last); rr = 2.0 if ex == "r2" else None
    for k in KS:
        H, L, C = B.H[k], B.L[k], B.C[k]
        oh, ol = H[:6].max(), L[:6].min()
        for j in range(6, lc + 1):
            d = 1 if C[j] > oh else -1 if C[j] < ol else 0
            if not d: continue
            ref = (ol if d == 1 else oh) if stopk == "far" else (oh + ol) / 2
            w = E2.walk(k, j, d, ref - d * TICK, rr=rr)
            if w: out.append(w)
            break
    return out

def orb_fade(tg, last=(12, 0)):
    """failed OR break: a bar pokes beyond the OR extreme and closes back inside -> fade; stop 1 tick beyond the poke."""
    out = []; lc = col(last)
    for k in KS:
        H, L, C = B.H[k], B.L[k], B.C[k]
        oh, ol = H[:6].max(), L[:6].min()
        for j in range(6, lc + 1):
            d = -1 if (H[j] > oh and C[j] < oh and C[j] > ol) else 1 if (L[j] < ol and C[j] > ol and C[j] < oh) else 0
            if not d: continue
            ext = H[j] if d == -1 else L[j]
            w = E2.walk(k, j, d, ext + (TICK if d == -1 else -TICK), tgt=((oh + ol) / 2 if tg == "mid" else None), rr=2.0 if tg == "r2" else None)
            if w: out.append(w)
            break
    return out

def pdx(tg):
    c = {"last": (12, 0), "rv": 0, "tg": tg}
    return [w for w in E2.run_pdx(c, KS)]

ENT = {}
for s, e in itertools.product(("far", "mid"), ("eod", "r2")): ENT[f"T_orb_{s}_{e}"] = ("T", lambda s=s, e=e: orb_trend(s, e))
for t in ("mid", "r2"): ENT[f"F_orf_{t}"] = ("F", lambda t=t: orb_fade(t))
for t in ("vwap", "r2"): ENT[f"F_pdx_{t}"] = ("F", lambda t=t: pdx(t))
W = {n: fn() for n, (_, fn) in ENT.items()}
T = {n: DS.booked(w) for n, w in W.items()}

def kday(t): return B.pos[t["day"]]
SPN = ("H1", "H2", "2025", "2021-24")
def S(t): return {s: DS.stats(t, s) for s in SPN}
cells = {}
def add(cid, tr):
    cells[cid] = {"S": S(tr), "T": tr}
for n in ENT: add(f"{n}|all", T[n])
# day-type filters: feature low/high; "trend side" = expected-big-range side (gex LOW, spread HIGH, ts HIGH)
CUTS = {"p50": (50, 50), "p33": (33, 67)}
sides = {}
for feat_ in ("gex", "spread", "ts"):
    p = f.pr[feat_]
    for cn, (lo, hi) in CUTS.items():
        low = lambda k, p=p, lo=lo: np.isfinite(p[k]) and p[k] < lo
        high = lambda k, p=p, hi=hi: np.isfinite(p[k]) and p[k] >= hi
        sides[f"{feat_}_{cn}_low"] = low; sides[f"{feat_}_{cn}_high"] = high
for sid, fn in sides.items():
    for n in ENT:
        add(f"{n}|{sid}", [t for t in T[n] if fn(kday(t))])
print("cells (entry x day-type incl. unconditional):", len(cells))
json.dump({k: v["S"] for k, v in cells.items()}, open("grid_b.json", "w"))

def line(cid):
    s = cells[cid]["S"]; r = []
    for sp in SPN:
        x = s[sp]
        r.append("n0" if not x.get("n") else f"{x['n']}/{x['tpw']}/{x['pf']}/{x['net']}")
    return cid + "  " + "  ".join(r)
print("== unconditional"); [print(line(f"{n}|all")) for n in ENT]
good = [c for c, v in cells.items() if v["S"]["H1"].get("n", 0) >= 12 and (v["S"]["H1"]["pf"] or 0) >= 1.2]
print("== H1 n>=12 PF>=1.2:", len(good))
for c in sorted(good, key=lambda c: -cells[c]["S"]["H1"]["net"])[:25]: print(line(c))
hold = [c for c in good if all(cells[c]["S"][s].get("n", 0) >= 5 and cells[c]["S"][s]["net"] > 0 for s in ("H2", "2025", "2021-24"))]
print("== holds H2+2025+2021-24 net>0:", hold)

# ---- switches: best-H1 trend entry on trend side + best-H1 fade entry on fade side, same feature/cut
def best(side_id, kind):
    c = [(f"{n}|{side_id}") for n in ENT if ENT[n][0] == kind and cells[f"{n}|{side_id}"]["S"]["H1"].get("n", 0) >= 8]
    return max(c, key=lambda c: cells[c]["S"]["H1"]["net"], default=None)
SW = {}
for feat_ in ("gex", "spread", "ts"):
    for cn in CUTS:
        ts_, fs_ = f"{feat_}_{cn}_low", f"{feat_}_{cn}_high"      # gex: low=trend/high=fade ; spread,ts: high=trend/low=fade
        if feat_ != "gex": ts_, fs_ = fs_, ts_
        a, b = best(ts_, "T"), best(fs_, "F")
        if a and b:
            tr = sorted(cells[a]["T"] + cells[b]["T"], key=lambda t: (t["day"], t["entry_t"]))
            SW[f"SW_{feat_}_{cn}"] = {"parts": [a, b], "S": S(tr), "T": tr}
for k, v in SW.items():
    print(k, v["parts"], {s: (v["S"][s].get("n"), v["S"][s].get("pf"), v["S"][s].get("net")) for s in SPN})
json.dump({"cells": len(cells), "sw": {k: {"parts": v["parts"], "S": v["S"]} for k, v in SW.items()}}, open("switch_b.json", "w"))
import pickle; pickle.dump({"cells": {k: v["T"] for k, v in cells.items()}, "SW": {k: v["T"] for k, v in SW.items()}}, open("/tmp/claude-0/-home-user/985fb1ba-d48a-5b61-8251-6d2f2f33af8c/scratchpad/trades_b.pkl", "wb"))
