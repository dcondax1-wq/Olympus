"""(d) current MFFU accounts from today's balances + (b) a $300 / $500 live 1-MNQ account. rank.py engine, 21 sessions = 30 days."""
import sys, json
import numpy as np
ROOT = "/home/user/olympus"; sys.path.insert(0, ROOT + "/research/plans")
import rank as RK
from rank import U, SOA, AR, RL
AR.rapid_patch(AR.T_at(10))
S = SOA.data()["S"]; N = int(sys.argv[1]); H = 21; out = {}
LA = RL.mix_by(RL.LA); ATL = RL.mix_by(("ATLAS",))

def funded(plan, ask, bal, peak, floor, BY=None, gap=0):
    sp = RK.spec(plan)
    def mk():
        f = RK.Funded(U.UP50 if "50k" in plan else U.UP25, sp["F"], sp["z"], ask)
        f.bal, f.peak, f.floor, f.cyc_start = bal, peak, floor, 0.0
        return f
    return sp, mk, BY or sp["BYf"]

def run_funded(name, plan, ask, bal, peak, floor, BY=None, P=None):
    sp, mk, BYf = funded(plan, ask, bal, peak, floor, BY)
    rows = []
    for seq in P:
        f, got, first, lost = mk(), 0.0, None, False
        for k, si in enumerate(seq[:H]):
            ev, x, _ = f.step(BYf[si])
            if ev in ("paid", "grad"): got += x; first = first or k + 1
            if ev in ("lost", "grad"): lost = ev == "lost"; break
        rows.append((got, first, lost))
    return rows

def run_eval(name, plan, ask, bal, floor, P, BYe=None):
    sp = RK.spec(plan); rows = []
    for seq in P:
        e = sp["ev"](); e.bal, e.floor = bal, floor
        f, wait, got, first, lost, passed = None, 0, 0.0, None, False, None
        for k, si in enumerate(seq[:H]):
            if e is not None:
                r, _ = e.step((BYe or sp["BYe"])[si])
                if r == "pass": passed = k + 1; e, wait = None, RK.GAP
                elif r in ("fail", "stuck"): lost = True; break
                continue
            if f is None:
                wait -= 1
                if wait <= 0: f = RK.Funded(U.UP50 if "50k" in plan else U.UP25, sp["F"], sp["z"], ask)
                continue
            ev, x, _ = f.step(sp["BYf"][si])
            if ev in ("paid", "grad"): got += x; first = first or k + 1
            if ev in ("lost", "grad"): break
        rows.append((got, first, lost, passed))
    return rows

def summ(rows):
    g = np.array([r[0] for r in rows]); fp = [r[1] for r in rows if r[1]]
    d = {"cash30_p50": round(float(np.median(g))), "cash30_p10": round(float(np.percentile(g, 10))), "cash30_mean": round(float(g.mean())),
         "p_paid30": round(100 * len(fp) / len(rows), 1), "first_med": float(np.median(fp)) if fp else None,
         "p_lost": round(100 * sum(1 for r in rows if r[2]) / len(rows), 1)}
    if len(rows[0]) > 3: d["p_pass"] = round(100 * sum(1 for r in rows if r[3]) / len(rows), 1)
    return d

def live(P, start, comm, margin, mix, monthly_fee):
    rows = []
    for seq in P:
        b, ruin, first = start, False, None
        for k, si in enumerate(seq[:H]):
            for t in mix[si]:
                if b < margin + t["risk"] * 2: continue      # 1 micro no longer fits margin + its stop: skip
                b += t["pts"] * 2.0 - comm
            if b < margin + 40: ruin = True; break
            if first is None and b - start >= 100: first = k + 1    # first $100 you could withdraw
        rows.append((b - start - monthly_fee, first, ruin))
    return rows

for span in ("H1", "H2", "REF"):
    P = U.mc_paths(S, span, N, length=H, seed=41); o = {}
    import os
    if os.environ.get("ONLY_LIVE"):
        for st in (300, 500):
            o[f"live_1mnq_{st}_rt2.00_data12"] = summ(live(P, st, 2.00, 100.0, LA, 12.0))
        out[span] = o
        for k, v in o.items(): print(span, k, v, flush=True)
        continue
    # ATLAS 25K Builder funded: MFFU profit $401, peak $401, floor -$599 (board 2026-11-23 10:12 ET)
    o["atlas25_ask_cap1000"] = summ(run_funded("a", "mffu_builder_25k", "cap", 401.0, 401.0, -599.0, ATL, P))
    o["atlas25_ask_min250"] = summ(run_funded("a", "mffu_builder_25k", 250.0, 401.0, 401.0, -599.0, ATL, P))
    o["atlas25_LIT+ATLAS_min250"] = summ(run_funded("a", "mffu_builder_25k", 250.0, 401.0, 401.0, -599.0, LA, P))
    # Zlarior 50K eval: -$786, room $1,046 -> floor -$1,832; funded ask cap ($2,000) vs min ($500)
    o["zlarior50_eval_then_cap"] = summ(run_eval("z", "mffu_builder_50k", "cap", -786.0, -1832.0, P))
    o["zlarior50_eval_then_min500"] = summ(run_eval("z", "mffu_builder_50k", 500.0, -786.0, -1832.0, P))
    o["b25_2_eval_then_min250"] = summ(run_eval("b", "mffu_builder_25k", 250.0, 24.0, -976.0, P))
    o["rapid25_eval_fresh_daily"] = summ(run_eval("r", "mffu_rapid_eod_25k", 500.0, 0.0, -1000.0, P))
    for st in (300, 500):
        o[f"live_1mnq_{st}"] = summ(live(P, st, 1.60, 100.0, LA, 0.0))
    out[span] = o
    for k, v in o.items(): print(span, k, v, flush=True)
json.dump(out, open(sys.argv[2], "w"), indent=1)
