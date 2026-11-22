"""Placebo + eval MC + LIT correlation for the one survivor G1 = ORB far-stop trend held to EOD on prior-day-GEX >= 1y-median days."""
import pickle, json, random, collections
import numpy as np
from feat import *
B = DS.D(); f = F()
P = pickle.load(open("/tmp/claude-0/-home-user/985fb1ba-d48a-5b61-8251-6d2f2f33af8c/scratchpad/trades_b.pkl", "rb"))["cells"]
ALL = P["T_orb_far_eod|all"]; G1 = P["T_orb_far_eod|gex_p50_high"]
SPN = ("H1", "H2", "2025", "2021-24")
def holds(T): return all((lambda s: s.get("n", 0) >= 5 and s["net"] > 0 and (s["pf"] or 0) >= 1.1)(DS.stats(T, sp)) for sp in SPN)
# placebo: random half of the ORB days (same entry rule), judged the same way (all four spans net>0, PF>=1.1)
rng = random.Random(7); days = sorted({t["day"] for t in ALL}); N = 2000; hit = 0
for _ in range(N):
    keep = {d for d in days if rng.random() < 0.5}
    hit += holds([t for t in ALL if t["day"] in keep])
print("placebo random-half-of-days holds in all 4 spans:", hit / N)
# same for the stronger H1-picked rule: of random halves that pass H1 PF>=1.2, how many hold the rest
c1 = c2 = 0
for _ in range(N):
    keep = {d for d in days if rng.random() < 0.5}
    T = [t for t in ALL if t["day"] in keep]; s = DS.stats(T, "H1")
    if s.get("n", 0) >= 12 and (s["pf"] or 0) >= 1.2:
        c1 += 1; c2 += all(DS.stats(T, sp).get("net", -1) > 0 for sp in ("H2", "2025", "2021-24"))
print("random halves passing the H1 gate:", c1, "of which positive in H2+2025+2021-24:", c2)
# eval MC (MFFU Builder 50K: +3000, 2000 EOD trailing floor locking at +100, 1000 soft daily loss); owner eval sizing = room_f 0.4
def eval_mc(T, span, rf=0.4, n=1000, block=5, horizon=60, seed=3):
    a, z = DS.SPANS[span]; ds = [d for d in B.days if a <= d <= z]
    by = collections.defaultdict(list)
    for t in T: by[t["day"]].append(t["r"])
    R = [by.get(d, []) for d in ds]; r = random.Random(seed); out = []
    for _ in range(n):
        bal = 0.0; floor = -2000.0; hi = 0.0; res = None; i = 0
        seq = []
        while len(seq) < horizon:
            s = r.randrange(0, max(1, len(R) - block)); seq += R[s:s + block]
        for i, rs in enumerate(seq[:horizon]):
            room = bal - floor; day = 0.0
            for x in rs:
                risk = min(rf * room, 1000.0 + day) if False else rf * room
                pnl = x * risk; bal += pnl; day += pnl
                if bal <= floor: res = ("F", i + 1); break
                if bal >= 3000: res = ("P", i + 1); break
                if day <= -1000: break
            if res: break
            hi = max(hi, bal); floor = min(max(-2000.0, hi - 2000.0), 100.0)
        out.append(res or ("N", horizon))
    p = [x[1] for x in out if x[0] == "P"]
    return {"pass_%": round(100 * len(p) / n, 1), "fail_%": round(100 * sum(1 for x in out if x[0] == "F") / n, 1),
            "pass_in_10_%": round(100 * sum(1 for x in p if x <= 10) / n, 1), "median_pass_days": int(np.median(p)) if p else None}
rows = {}
for nm, T in (("G1", G1), ("ORBfar_all", ALL)):
    rows[nm] = {"spans": {sp: DS.stats(T, sp) for sp in SPN + ("2021-25",)}, "corr26": DS.corr(T, "2026"), "corr2125": DS.corr(T, "2021-25"),
                "eval": {sp: eval_mc(T, sp) for sp in ("H1", "H2", "2025", "2021-24")}}
    print(nm); [print("  ", k, v) for k, v in rows[nm]["eval"].items()]
json.dump({"placebo_halves": [hit / N, c1, c2], "rows": rows}, open("final_b.json", "w"), indent=1)
