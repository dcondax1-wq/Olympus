"""Rapid EOD 25K launch check (2026-11-20, day-rapid): what the owner's new Rapid EOD 25K (DLL version, $97.20) should trade
at ATLAS's real fills. PAPER RESEARCH ONLY: reads stored trades, writes research/lab/rapid25_launch.json, changes nothing live.
Design (committed before any run): research/second/rapid25_launch_design.md. Write-up: research/writeups/rapid-launch-2026-11-20.md.

Rows: R1 LIT only, R2 ATLAS only ($250), R3 LIT + ATLAS $250 (as built), R4 R3 + the LIT bank lane (rapid25-lit-bank).
Engine = tools/money/money_plan.RSeat on tools/money/rapid25.acct("25k", keep $500); ATLAS re-priced at N ticks a side with
tools/atlas_risk.T_at (= tools/atlas_fills.priced); LIT unchanged. Same paths / seeds as tools/atlas_risk.py.

    python -X utf8 tools/money/rapid25_launch.py run [--n 1000]
    python -X utf8 tools/money/rapid25_launch.py show
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
for p in (ROOT, os.path.join(ROOT, "tools"), HERE):
    if p not in sys.path:
        sys.path.insert(0, p)
import logging  # noqa: E402
logging.getLogger("engine.sizing").setLevel(logging.ERROR)

DATE = "2026-11-20"
DESIGN = "research/second/rapid25_launch_design.md"
OUT = os.path.join(ROOT, "research", "lab", "rapid25_launch.json")
COSTS = (1, 10)
SPANS = ("H1", "H2", "REF")
ROWS = {"R1_lit_only": "lit", "R2_atlas_only": "atlas", "R3_both": "both", "R4_both_bank": "bank"}
LABEL = {"R1_lit_only": "LIT only", "R2_atlas_only": "ATLAS only ($250)", "R3_both": "LIT + ATLAS $250 (as built)",
         "R4_both_bank": "LIT + ATLAS + LIT bank lane"}
DLL = 500.0


def _AR():
    import atlas_risk as AR
    return AR


def spec(kind):
    import rapid25 as R25
    import rapid_levers as RL
    import uprisk as U
    if kind == "bank":
        import rapid25_lit_lane as RLL
        return RLL.spec("bank1")
    sp = dict(R25.acct("25k", ("cushion", 500.0)))
    if kind == "both":
        return sp
    mix = ("LIT",) if kind == "lit" else ("ATLAS",)
    E, F = R25.rules("25k")
    ec, z, pol = sp["ecfg"], ({} if kind == "lit" else sp["z"]), ("cushion", 500.0)
    sp.update(z=z, BYe=RL.mix_by(mix), BYf=RL.mix_by(mix, news=True), mix_f=mix,
              fund=lambda: RL.Rapid(U.UP25, F, z, pol), ev=lambda: RL.Ev(ec, E, z, "guard"))
    return sp


def eval_paths(n):
    import account4_sim as A4
    import rapid_levers as RL
    import stack_one_account as SOA
    import uprisk as U
    S = SOA.data()["S"]
    return {sp: U.mc_paths(S, sp, 2 * n, length=RL.H_EVAL, seed=A4.SEED_EVAL) for sp in SPANS}


def pct_date(firsts, q):
    cal = _AR().calendar()
    arr = sorted(f if f else 10 ** 6 for f in firsts)
    v = arr[min(len(arr) - 1, int(q / 100.0 * len(arr)))]
    return None if v >= 10 ** 6 else cal[int(v) - 1]


def life_row(sp, n):
    import money_plan as MP
    import rapid_levers as RL
    AR = _AR()
    PF = AR.rapid_paths(n)
    out = {}
    for s in SPANS:
        net, firsts, lost, fail_first, owner6, dll_days, traded = [], [], [], [], [], 0, 0
        for seq in PF[s]:
            st = MP.RSeat(sp, join=0)
            own = cost = 0.0
            first = None
            evals_at_first = None
            for k, si in enumerate(seq[:RL.LEN]):
                o, c = st.step(k, si)
                own += o
                cost += c
                if o > 0 and first is None:
                    first, evals_at_first = k + 1, st.s.evals
            net.append(own - cost)
            owner6.append(own)
            firsts.append(first)
            lost.append(st.lost > 0)
            fail_first.append((evals_at_first or st.s.evals) > 1)
            d = [x for x in st.s.days if abs(x) > 1e-9]
            traded += len(d)
            dll_days += sum(1 for x in d if x < -DLL)
        k, dt, nop = AR.first_stats(firsts)
        out[s] = {"usd_m": round(float(np.mean(net)) / MP.MO), "owner_6m": round(float(np.mean(owner6))),
                  "first_date": dt, "first_p25": pct_date(firsts, 25), "first_p75": pct_date(firsts, 75),
                  "no_pay_6m": nop, "lost_6m": round(100.0 * float(np.mean(lost)), 1),
                  "fail_before_pay": round(100.0 * float(np.mean(fail_first)), 1),
                  "dll_per_100": round(100.0 * dll_days / max(1, traded), 2)}
    return out


def eval_row(sp, PE):
    import rapid_levers as RL
    return {s: RL.eval_stats(sp, PE[s]) for s in SPANS}


def judge(res):
    c = "10t"
    R = {k: res["rows"][k][c] for k in ROWS}
    H = ("H1", "H2")
    both, lit, atl, bank = R["R3_both"], R["R1_lit_only"], R["R2_atlas_only"], R["R4_both_bank"]
    a_yes = all(both["life"][s]["usd_m"] > lit["life"][s]["usd_m"] and both["life"][s]["no_pay_6m"] < lit["life"][s]["no_pay_6m"]
                for s in H)
    why_b = []
    for s in H:
        if bank["life"][s]["usd_m"] < both["life"][s]["usd_m"]:
            why_b.append(f"{s} ${both['life'][s]['usd_m']} -> ${bank['life'][s]['usd_m']}/mo")
        if bank["life"][s]["lost_6m"] > both["life"][s]["lost_6m"] + 5:
            why_b.append(f"{s} lost {both['life'][s]['lost_6m']} -> {bank['life'][s]['lost_6m']}%")
        if bank["eval"][s]["f60"] > both["eval"][s]["f60"] + 1:
            why_b.append(f"{s} eval fail {both['eval'][s]['f60']} -> {bank['eval'][s]['f60']}%")
    if bank["life"]["REF"]["usd_m"] < both["life"]["REF"]["usd_m"] - 10:
        why_b.append(f"REF ${both['life']['REF']['usd_m']} -> ${bank['life']['REF']['usd_m']}/mo")
    atlas_card = all(atl["life"][s]["usd_m"] > both["life"][s]["usd_m"] for s in SPANS)
    dll = max(both["life"][s]["dll_per_100"] for s in SPANS)
    return {"atlas-on-rapid": "yes" if a_yes else "no", "rapid25-lit-bank": "no" if why_b else "yes", "bank_why_not": why_b,
            "atlas_only_card": atlas_card, "dll_days_per_100_max": dll, "sizing_patch": dll > 1.0}


def cmd_run(n=1000, log=print):
    AR = _AR()
    t0 = time.time()
    AR.rapid_patch(AR.T_at(COSTS[0]))     # sets ATLAS's trades (and no BLITZ) before the paths read the days, as atlas_risk
    PE = eval_paths(n)
    res = {"date": DATE, "design": DESIGN, "n_paths": n, "costs": list(COSTS), "rows": {k: {} for k in ROWS}}
    for c in COSTS:
        AR.rapid_patch(AR.T_at(c))
        for nm, kind in ROWS.items():
            if kind == "lit" and c != COSTS[0]:
                res["rows"][nm][f"{c}t"] = res["rows"][nm][f"{COSTS[0]}t"]   # no ATLAS trade to re-price
                continue
            sp = spec(kind)
            r = {"eval": eval_row(sp, PE), "life": life_row(sp, n)}
            res["rows"][nm][f"{c}t"] = r
            log(f"{nm:14s} {c:2d}t " + " | ".join(
                f"{s} ${r['life'][s]['usd_m']}/mo pass {r['eval'][s]['p60']}% in~{r['eval'][s]['pass_med']} fail {r['eval'][s]['f60']}% "
                f"1st {r['life'][s]['first_date']} lost {r['life'][s]['lost_6m']}% dll {r['life'][s]['dll_per_100']}"
                for s in SPANS) + f"  [{time.time() - t0:.0f}s]")
    res["judge"] = judge(res)
    res["took_s"] = round(time.time() - t0)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1, default=float)
    log(json.dumps(res["judge"]))
    log(f"wrote {os.path.relpath(OUT, ROOT)}")
    return res


def cmd_sizing(n=1000, log=print):
    """The design's conditional step (taken because R3 had > 1 day under -$500 per 100 at 10 ticks): R3 with ATLAS sized on a
    10-tick stop-out (engine/rapid.stack_qty SLIP 0.25 -> 2.5 pts), 10 ticks a side. Written to the same file, key "sizing"."""
    import stack_one_account as SOA
    AR = _AR()
    with open(OUT, encoding="utf-8") as fh:
        res = json.load(fh)
    AR.rapid_patch(AR.T_at(COSTS[0]))
    PE = eval_paths(n)
    AR.rapid_patch(AR.T_at(10))
    orig = SOA.stack_q

    def q10(t, z, room, cum, maxq, dll=SOA.SOFT_DLL):
        s = z.get(t["strat"])
        if not s:
            return 0
        slip = 2.5 if t["strat"] == "ATLAS" else SOA.SLIP
        loss1 = (t["risk"] + slip) * SOA.PV + SOA.COMM
        usd = min(float(s["usd"]), float(s["f"]) * max(0.0, room), dll + min(0.0, cum))
        return max(0, min(int(maxq), int(usd // loss1)))
    SOA.stack_q = q10
    try:
        sp = spec("both")
        r = {"eval": eval_row(sp, PE), "life": life_row(sp, n)}
    finally:
        SOA.stack_q = orig
    res["sizing"] = {"R5_both_atlas_slip10_10t": r}
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1, default=float)
    log(" | ".join(f"{s} ${r['life'][s]['usd_m']}/mo pass {r['eval'][s]['p60']}% fail {r['eval'][s]['f60']}% "
                   f"1st {r['life'][s]['first_date']} lost {r['life'][s]['lost_6m']}% dll {r['life'][s]['dll_per_100']}" for s in SPANS))
    return r


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("run", "sizing", "show"))
    ap.add_argument("--n", type=int, default=1000)
    a = ap.parse_args(argv)
    if a.cmd == "run":
        cmd_run(a.n)
    elif a.cmd == "sizing":
        cmd_sizing(a.n)
    else:
        with open(OUT, encoding="utf-8") as fh:
            print(json.dumps(json.load(fh)["judge"], indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
