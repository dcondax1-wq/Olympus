"""LIT adopt-candidates combined (2026-10-19): the 15-minute check (t_check), scale-in after breakeven (scale_in) and
breakeven at entry + 1.25 pts (be_off), alone and all three together, on the ENGINE itself (engine/lit.py run_x = the code
the live loop runs), against run lit_live. Judged the LIT way: 2026 only, H1 (Jan-Jun, pick) and H2 (Jul-Oct, check);
2021-25 is a reference line (no 1m bars there: t_check and scale_in never act; be_off does).

Two views, both costs in:
  LIT size rule  the engine's own trades ($800 up to a 20-pt stop, weekly stop) = how run lit_live is scored
  eval path      the live two_week sizing (engine/sizing.lit_qty: two_week for 10 sessions then safe_eval, no reset, $1.90 a
                 micro, scale-in adds sized by engine/sizing.scale_in_qty inside 60% of the room and the soft daily loss),
                 scored by tools/lit_adv_manage.py / tools/lit_big_ideas.py (fresh evals on every session + back-to-back path)
                 from the engine's trades turned into units (per-micro points, worst open points, adds)

    python -X utf8 tools/lit_adopt_combo.py           # score -> research/lit/adopt_combo.json
    python -X utf8 tools/lit_adopt_combo.py save      # + rl.save runs lit_adopt_* (LIT size rule) and lit_adopt_*_eval
Paper only. Edits no engine file.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import lit  # noqa: E402
from tools import lit_final as F  # noqa: E402

OUT = os.path.join(ROOT, "research", "lit", "adopt_combo.json")
T15 = {"at": 15, "x": 0.3, "mfe": 0.5}
SCALE = {"pb": 0.25, "f": 1.0, "rat_k": 1.0, "min_rk": 2.0, "n": 1}
BE_OFF = 1.25
# "base" = the live settings without the three options (they are ON in live_model.json since 2026-10-20)
LIVE = {k: v for k, v in json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))["lit"].items()
        if k not in ("t_check", "scale_in", "be_off")}
V = {"base": {}, "t15": {"t_check": T15}, "scale": {"scale_in": SCALE}, "be_off": {"be_off": BE_OFF},
     "t15_be_off": {"t_check": T15, "be_off": BE_OFF}, "all3": {"t_check": T15, "scale_in": SCALE, "be_off": BE_OFF}}


def units(T):
    """Engine trades (2026) -> eval-path units: risk, tgt (pts), pts (per micro, exit slippage in), w1 (worst open pts),
    legs, and the adds (rk, prev_rk, w_ph, dist, pts) for scale-in trades. The weekly-stop multiplier is undone (the
    two_week sizing has no weekly stop)."""
    M, _ = F.market(LIVE["ref"], LIVE.get("extra_boxes") or [])
    B1, B5 = F.bars(M, "1m"), F.bars(M, "5m")
    out = []
    for t in T:
        if t["day"] < "2026-01-01":
            continue
        d = int(t["dir"])
        B = B1 if t.get("tf") == 1 else B5
        e = float(t["entry_px"]) * d
        if t.get("adds"):
            pts, w1 = float(t["pts"]), float(t["w1"])
        else:
            pts = (t["pnl"] + lit.COMM * t["qty"]) / (lit.PV * t["qty"])
            k0 = int(np.searchsorted(B.t, int(t["entry_t"])))
            kx = int(np.searchsorted(B.t, int(t["exit_t"]) - B.secs))
            if t["exit"] == "CUT_T15":
                kx -= 1                                   # the cut fills at the exit bar's open: that bar never counts
            lo = B.l if d == 1 else -B.h
            w1 = min(0.0, float(lo[k0:kx + 1].min()) - e) if kx >= k0 else 0.0
        u = {"day": t["day"], "entry_t": int(t["entry_t"]), "exit_t": int(t["exit_t"]), "dir": d, "exit": t["exit"],
             "risk": float(t["risk_pts"]), "tgt": round(d * (float(t["target_px"]) - float(t["entry_px"])), 4), "pts": round(pts, 4),
             "w1": round(w1, 4), "legs": [(1.0, round(pts, 4))], "on1": t.get("tf") == 1}
        if t.get("adds"):
            u.update(w_pre=float(t["w_pre"]), add_f=SCALE["f"],
                     adds=[{k: a[k] for k in ("rk", "prev_rk", "w_ph", "dist", "pts")} for a in t["adds"]])
        out.append(u)
    return out


def check_units(U):
    """Options off: the engine units == tools/lit_adv_manage.py unit() (the executor behind every published eval number)."""
    from tools import lit_adv_manage as A
    R = A.unit()
    ka = [(u["day"], u["entry_t"], u["exit"], round(u["pts"], 2), round(u["w1"], 2), round(u["tgt"], 2)) for u in U]
    kb = [(u["day"], u["entry_t"], u["exit"], round(u["pts"], 2), round(u["w1"], 2), round(u["tgt"], 2)) for u in R]
    bad = [(a, b) for a, b in zip(ka, kb) if a != b]
    print(f"engine units == lit_adv_manage.unit(): {len(ka) - len(bad)}/{len(kb)}", flush=True)
    for x in bad[:5]:
        print("  diff", x)
    return not bad and len(ka) == len(kb)


def main(save=False):
    from tools import lit_big_ideas as BI           # patches lit_adv_manage.run_eval with the add-aware eval
    res, TT = {}, {}
    for nm, x in V.items():
        P = {**LIVE, **x}
        T = F.run(P)
        TT[nm] = T
        U = units(T)
        if nm == "base" and not check_units(U):
            raise SystemExit("engine units differ from the research executor: eval numbers would not be comparable")
        res[nm] = {"params": x, "lit_rule": F.score(T), "eval": BI.short(BI.score(U)),
                   "exits_2026": dict(__import__("collections").Counter(t["exit"] for t in T if t["day"] >= "2026")),
                   "adds_2026": sum(1 for t in T if t.get("adds") and t["day"] >= "2026")}
        o, e = res[nm]["lit_rule"], res[nm]["eval"]
        print(f"{nm:11s} LIT rule {F.fmt({k: o[k] for k in ('H1', 'H2')})}", flush=True)
        print(f"{'':11s} eval     " + " | ".join(f"{s}[n={e[s]['n']} PF={e[s]['pf']} net={e[s]['net']:+,} ${e[s]['per_month']:,}/mo "
                                                 f"DD={e[s]['dd']:,} 2w={e[s]['p10']}/{e[s]['f10']} mc={e[s].get('mc_p10')}/{e[s].get('mc_f10')}]"
                                                 for s in ("H1", "H2")), flush=True)
    json.dump(res, open(OUT, "w"), indent=1, default=float)
    if save:
        store(res, TT)
    return res


def store(res, TT):
    from tools import runlib as rl
    from tools import lit_adv_manage as A
    from tools import lit_big_ideas as BI
    names = {"t15": "15-minute check (t_check)", "scale": "scale-in after breakeven (scale_in)",
             "be_off": "breakeven at entry + 1.25 pts (be_off)", "t15_be_off": "t_check + be_off",
             "all3": "t_check + scale_in + be_off (all three adopt-candidates)"}
    Q = "Owner 2026-10-19: make the adopt-candidates switch-on ready on the PC route; what do they make together vs lit_live?"
    for nm in ("all3", "t15_be_off"):
        o, e = res[nm]["lit_rule"], res[nm]["eval"]
        h = lambda s: (f"n={s['n']} {s['tpw']}/wk win {s['win']}% PF {s['pf']} net {s['net']:+,} (${s['per_month']:,}/mo) DD {s['dd']:,} "  # noqa
                       f"eval 2wk {s['p10']}/{s['f10']} 1mo {s['p20']}/{s['f20']}")
        he = lambda s: (f"n={e[s]['n']} PF {e[s]['pf']} net {e[s]['net']:+,} (${e[s]['per_month']:,}/mo) DD {e[s]['dd']:,}; 2-week "  # noqa
                        f"pass/fail {e[s]['p10']}/{e[s]['f10']} (Monte Carlo {e[s].get('mc_p10')}/{e[s].get('mc_f10')}), 1 month "
                        f"{e[s]['p20']}/{e[s]['f20']}")
        T = [{k: v for k, v in t.items() if not k.startswith("_") and k not in ("size_why", "size_mult")} for t in TT[nm]]
        P = {**lit.DEFAULTS, **LIVE, **V[nm]}
        rl.save("lit_adopt_" + nm, "LIT live + " + names[nm], "management", Q, params=P, trades=T, scored=rl.score(T, F.SESS),
                status="adopt-candidate",
                verdict=f"LIT size rule (engine run_x, as lit_live). 2026 H1 (pick) {h(o['H1'])}; 2026 H2 (check) {h(o['H2'])}; "
                        f"2021-25 reference {h(o['2021-25'])}. Eval path (two_week sizing): H1 {he('H1')}; H2 {he('H2')}.",
                notes="tools/lit_adopt_combo.py: engine/lit.py run_x on live_model.json lit + the options (default off). The PC route "
                      "does the same: tests/test_lit_exit_route.py (t_check, be_off), tests/test_lit_scale_in.py part 5 (scale_in).",
                writeup="lit-big-ideas", tags=["lit", "lit_adopt"])
        U = units(TT[nm])
        Tp = []
        for sp in ("H1", "H2"):
            Tp += A.b2b(U, sp)[0]
        for t in Tp:
            t["risk_pts"] = t["risk"]; t["r"] = round(t["pnl"] / t["risk_usd"], 3) if t["risk_usd"] else 0.0
            t.update(half=False, trigger="LIT-1m", mfe=None, mae=None, bars_held=None, regime="", mult=None, tgt_pts=t["tgt"])
        rl.save("lit_adopt_" + nm + "_eval", "LIT live + " + names[nm] + " (eval path, two_week sizing)", "management", Q,
                params=P, sizing={"mode": "two_week", **A.CFG}, trades=Tp, scored=rl.score(Tp, A.S26), status="adopt-candidate",
                verdict=f"Eval path, live two_week sizing. 2026 H1 (pick) {he('H1')}. 2026 H2 (check) {he('H2')}. 2021-25: no 1m bars.",
                notes="tools/lit_adopt_combo.py: the engine's trades as units, sized and scored by tools/lit_adv_manage.py + "
                      "tools/lit_big_ideas.py run_eval_x (stored trades = the back-to-back eval path per half).",
                writeup="lit-big-ideas", tags=["lit", "lit_adopt"])
        print("saved lit_adopt_" + nm, "and lit_adopt_" + nm + "_eval", flush=True)
    _ = BI


if __name__ == "__main__":
    main(save=len(sys.argv) > 1 and sys.argv[1] == "save")
