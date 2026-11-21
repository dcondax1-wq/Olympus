"""Skeptic round 4: card rapid-atlas-size-10t on week blocks / day blocks / another seed + flat-$ controls. Run from the repo root on a tree with day-rapid merged: python -X utf8 research/skeptic/rapid10t.py week|day|seed"""
import sys, json, time
sys.path.insert(0, "/home/user/olympus/tools/money")  # needs day-rapid's tools/money/rapid25_launch.py
sys.path.insert(0, "/home/user/olympus/tools/money"); sys.path.insert(0, "/home/user/olympus/tools"); sys.path.insert(0, "/home/user/olympus")
import rapid25_launch as RLx
from tools import uprisk as U
import account4_sim as A4
mode = sys.argv[1]           # week | day | seed
n = 1000
if mode == "day": U.BLOCK = 1
if mode == "seed": A4.SEED_LIFE = 101; A4.SEED_EVAL = 11
AR = RLx._AR()
import stack_one_account as SOA
t0 = time.time()
AR.rapid_patch(AR.T_at(1)); PE = RLx.eval_paths(n)
AR.rapid_patch(AR.T_at(10))
out = {}
sp = RLx.spec("both"); out["R3 as built"] = {"eval": RLx.eval_row(sp, PE), "life": RLx.life_row(sp, n)}
orig = SOA.stack_q
def q10(t, z, room, cum, maxq, dll=SOA.SOFT_DLL):
    s = z.get(t["strat"])
    if not s: return 0
    slip = 2.5 if t["strat"] == "ATLAS" else SOA.SLIP
    loss1 = (t["risk"] + slip) * SOA.PV + SOA.COMM
    usd = min(float(s["usd"]), float(s["f"]) * max(0.0, room), dll + min(0.0, cum))
    return max(0, min(int(maxq), int(usd // loss1)))
SOA.stack_q = q10
sp = RLx.spec("both"); out["R5 10-tick sizing"] = {"eval": RLx.eval_row(sp, PE), "life": RLx.life_row(sp, n)}
SOA.stack_q = orig
# flat-smaller control: ATLAS $ cap lowered so the average risk drops like the 10-tick sizing (same slip as built)
import rapid25 as R25
for usd in (200.0, 175.0):
    def qs(t, z, room, cum, maxq, dll=SOA.SOFT_DLL, usd=usd):
        s = z.get(t["strat"])
        if not s: return 0
        loss1 = (t["risk"] + SOA.SLIP) * SOA.PV + SOA.COMM
        cap = usd if t["strat"] == "ATLAS" else float(s["usd"])
        u = min(cap, float(s["f"]) * max(0.0, room), dll + min(0.0, cum))
        return max(0, min(int(maxq), int(u // loss1)))
    SOA.stack_q = qs
    sp = RLx.spec("both"); out[f"ATLAS ${int(usd)} flat"] = {"eval": RLx.eval_row(sp, PE), "life": RLx.life_row(sp, n)}
    SOA.stack_q = orig
for k, r in out.items():
    print(mode, k, " | ".join(f"{s} ${r['life'][s]['usd_m']} lost {r['life'][s]['lost_6m']}% 1st {r['life'][s]['first_date']} pass {r['eval'][s]['p60']} fail {r['eval'][s]['f60']} dll {r['life'][s]['dll_per_100']}" for s in ("H1","H2","REF")), flush=True)
json.dump(out, open(f"research/skeptic/rapid10t_{mode}.json","w"), default=float)
print("took", round(time.time()-t0))
