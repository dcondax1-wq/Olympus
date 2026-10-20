"""Inducement-count sizing (engine/lit.py option idm_size) ON THE EVAL PATH (2026-10-19): the live sizing
engine/sizing.lit_qty (two_week for 10 sessions, then safe_eval, no reset, $1.90 a micro), which since 2026-10-19 applies the
trade's idm_m / idm_cap itself (before the 60% room, soft daily loss and max-micros caps). Alone and with the three
adopt-candidates (t_check, scale_in, be_off; tools/lit_adopt_combo.py), against run lit_live. Judged the LIT way: 2026 only,
H1 (Jan-Jun, pick) and H2 (Jul-Oct, check).

Executor: the engine's trades (tools/lit_final.run = engine/lit.py run_x on live_model.json lit + options) turned into units by
tools/lit_adopt_combo.units (+ the trade's idm_m / idm_cap), sized trade by trade by engine/sizing.lit_qty with the exact MFFU
50K rules (tools/lit_adv_manage.evals / mc / b2b; adds by engine/sizing.scale_in_qty via tools/lit_big_ideas.trade_pnl).
The model's micros handed to lit_qty carry the idm multiplier the way engine/lit.py books it (sizing.idm_apply on the LIT
size), so the safe_eval sessions after session 10 route what the live loop would.

    python -X utf8 tools/lit_idm_eval.py          # score -> research/lit/idm_eval.json
    python -X utf8 tools/lit_idm_eval.py save     # + rl.save runs lit_idm_eval_*
Paper only. Changes nothing in live_model.json.
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import lit  # noqa: E402
from engine import sizing as SZ  # noqa: E402
from tools import lit_adopt_combo as AC  # noqa: E402
from tools import lit_adv_manage as A  # noqa: E402
from tools import lit_big_ideas as BI  # noqa: E402  (patches A.run_eval; replaced below)
from tools import lit_final as F  # noqa: E402

OUT = os.path.join(ROOT, "research", "lit", "idm_eval.json")
IDM = {"atr": 2.0, "bars": 48, "n": 2, "up": 1.5, "down": 0.75, "cap_usd": 990}
T15, SCALE, BE_OFF = AC.T15, AC.SCALE, AC.BE_OFF
# name -> (engine options, lit_sizing "idm" mode)
V = {"base": ({}, "both"),
     "idm": ({"idm_size": IDM}, "both"),
     "idm_cut": ({"idm_size": IDM}, "cut"),
     "all3": ({"t_check": T15, "scale_in": SCALE, "be_off": BE_OFF}, "both"),
     "idm_all3": ({"idm_size": IDM, "t_check": T15, "scale_in": SCALE, "be_off": BE_OFF}, "both"),
     "t15_be_off": ({"t_check": T15, "be_off": BE_OFF}, "both"),
     "idm_t15_be_off": ({"idm_size": IDM, "t_check": T15, "be_off": BE_OFF}, "both"),
     "idm_cut_all3": ({"idm_size": IDM, "t_check": T15, "scale_in": SCALE, "be_off": BE_OFF}, "cut")}
PAIR = {"idm": "base", "idm_cut": "base", "idm_all3": "all3", "idm_cut_all3": "all3", "idm_t15_be_off": "t15_be_off"}
CUR = {"idm": "both"}
PV, SLIP, ECOMM, DLL = A.PV, A.SLIP, A.ECOMM, A.A50["dll"]


def units(T):
    """lit_adopt_combo.units + the inducement fields of each engine trade (same order, 2026 only)."""
    U = AC.units(T)
    T6 = [t for t in T if t["day"] >= "2026-01-01"]
    assert len(U) == len(T6) and all(u["entry_t"] == int(t["entry_t"]) for u, t in zip(U, T6))
    for u, t in zip(U, T6):
        if t.get("idm_m") is not None:
            u.update(idm_m=float(t["idm_m"]), idm_cap=t.get("idm_cap"), idm_n=t.get("idm_n"))
    return U


def run_eval_idm(seq, by, horizon=20, keep=None, cfg=None):
    """lit_adv_manage.run_eval with the trade's idm_m / idm_cap handed to engine/sizing.lit_qty (as engine/live.py does with
    the lit_live position) and scale-in adds sized at the routed micros (engine/live.py _add_qty: scale_in_qty(q, q, ...))."""
    cfg = {**(cfg or A.CFG), "idm": CUR["idm"]}
    tgt, mll, lockv = A.A50["target"], A.A50["mll"], A.A50["lock"]
    bal = peak = 0.0
    floor = -mll
    for kk, si in enumerate(seq[:horizon]):
        cum = 0.0
        for t in by[si]:
            if cum <= -DLL:
                break
            st = {"profit": bal, "cum": cum, "room": bal + cum - floor, "session": kk + 1, "n_today": 0}
            tr = {"risk_pts": t["risk"], "tgt_pts": t["tgt"], "size_mult": 1.0}
            m0 = lit.qty_for(t["risk"])
            if t.get("idm_m") is not None:
                tr.update(idm_m=t["idm_m"], idm_cap=t.get("idm_cap"), wk_m=1.0, size_mult=t["idm_m"])
                m0 = SZ.idm_apply(m0, tr, t["risk"], 40, "both")        # the model's micros (engine/lit.py books them so)
            q = SZ.lit_qty(m0, tr, cfg, room=st["room"], state=st, learning=None)["qty"] if m0 else 0
            if q <= 0:
                continue
            pnl, low, tot = BI.trade_pnl(t, q, q, st)
            if cum + low <= -DLL:
                pnl = -DLL - cum - SLIP * PV * tot
                low = pnl
            rec = {**{k: t[k] for k in ("day", "entry_t", "exit_t", "dir", "exit", "risk", "tgt")}, "qty": tot, "pnl": round(pnl, 2),
                   "low": round(low, 2), "risk_usd": round(t["risk"] * PV * q, 2),
                   "risk_full": round(((t["risk"] + SLIP) * PV + ECOMM) * q, 2), "idm_m": t.get("idm_m")}
            if bal + cum + low <= floor:
                if keep is not None:
                    keep.append(rec)
                return "FAIL", kk + 1
            cum += pnl
            if keep is not None:
                keep.append(rec)
        bal += cum
        if bal <= floor:
            return "FAIL", kk + 1
        peak = max(peak, bal)
        floor = min(max(floor, peak - mll), lockv)
        if bal >= tgt:
            return "PASS", kk + 1
    return "OPEN", min(len(seq), horizon)


A.run_eval = run_eval_idm


def risk_stats(U):
    """$ at risk per trade on the back-to-back eval path (full stop + 1 tick + $1.90 a micro): max and median, per half."""
    import numpy as np
    o = {}
    for sp in ("H1", "H2"):
        T, _ = A.b2b(U, sp)
        r = [t["risk_full"] for t in T]
        o[sp] = {"max": round(max(r)) if r else None, "med": round(float(np.median(r))) if r else None,
                 "max_q": max(t["qty"] for t in T) if T else None}
    return o


def score_units(U, idm_mode):
    CUR["idm"] = idm_mode
    A._MC.clear()
    e = BI.short(BI.score(U))
    rk = risk_stats(U)
    for s in ("H1", "H2"):
        e[s]["risk_max"], e[s]["risk_med"], e[s]["max_q"] = rk[s]["max"], rk[s]["med"], rk[s]["max_q"]
    return e


def main(save=False):
    res, TT, UU = {}, {}, {}
    cache = {}
    for nm, (x, im) in V.items():
        key = json.dumps(x, sort_keys=True)
        if key not in cache:
            cache[key] = F.run({**AC.LIVE, **x})
        T = cache[key]
        TT[nm] = T
        U = units(T)
        UU[nm] = U
        if nm == "base" and not AC.check_units(U):
            raise SystemExit("engine units differ from the research executor")
        e = score_units(U, im)
        res[nm] = {"params": x, "idm_mode": im, "lit_rule": F.score(T), "eval": e,
                   "adds_2026": sum(1 for t in T if t.get("adds") and t["day"] >= "2026")}
        print(f"{nm:15s} " + " | ".join(f"{s}[PF={e[s]['pf']} net={e[s]['net']:+,} ${e[s]['per_month']:,}/mo DD={e[s]['dd']:,} "
                                         f"2w={e[s]['p10']}/{e[s]['f10']} mc={e[s]['mc_p10']}/{e[s]['mc_f10']} "
                                         f"risk max ${e[s]['risk_max']} med ${e[s]['risk_med']}]" for s in ("H1", "H2")), flush=True)
    b = res["base"]["eval"]
    ref = json.load(open(AC.OUT, encoding="utf-8"))["base"]["eval"]
    same = all(b[s][k] == ref[s][k] for s in ("H1", "H2") for k in ("net", "pf", "dd", "p10", "f10", "mc_p10", "mc_f10"))
    print("base == research/lit/adopt_combo.json base eval (lit_live on the eval path):", same, flush=True)
    res["_check_base_equals_adopt_combo"] = same
    json.dump(res, open(OUT, "w"), indent=1, default=float)
    if save:
        store(res, TT, UU)
    return res


NAMES = {"base": "LIT live (lit_live) on the eval path - executor check",
         "idm": "inducement-count size (idm_size) on the eval path",
         "idm_cut": "idm_size, eval sizing takes only the 0.75x cut",
         "all3": "t_check + scale_in + be_off on the eval path",
         "idm_all3": "idm_size + t_check + scale_in + be_off on the eval path",
         "t15_be_off": "t_check + be_off on the eval path",
         "idm_t15_be_off": "idm_size + t_check + be_off on the eval path",
         "idm_cut_all3": "idm_size (cut only on the eval) + t_check + scale_in + be_off on the eval path"}


def store(res, TT, UU):
    from tools import runlib as rl
    Q = ("Owner 2026-10-19: the inducement-count size only acted in normal sizing; make engine/sizing.py honour it on the eval "
         "path and score it alone and with the adopt-candidates vs lit_live.")
    b = res["base"]["eval"]

    def he(e, s):
        x = e[s]
        return (f"n={x['n']} PF {x['pf']} net {x['net']:+,} (${x['per_month']:,}/mo) DD {x['dd']:,}; 2-week pass/fail "
                f"{x['p10']}/{x['f10']} (Monte Carlo {x['mc_p10']}/{x['mc_f10']}), 1 month {x['p20']}/{x['f20']}; max risk "
                f"${x['risk_max']:,} (median ${x['risk_med']:,})")
    for nm in V:
        e = res[nm]["eval"]
        CUR["idm"] = res[nm]["idm_mode"]
        A._MC.clear()
        Tp = []
        for sp in ("H1", "H2"):
            Tp += A.b2b(UU[nm], sp)[0]
        for t in Tp:
            t["risk_pts"] = t["risk"]; t["r"] = round(t["pnl"] / t["risk_usd"], 3) if t["risk_usd"] else 0.0
            t.update(half=False, trigger="LIT-1m", mfe=None, mae=None, bars_held=None, regime="", mult=t.get("idm_m"), tgt_pts=t["tgt"])
        # judged against the same variant without idm_size (idm alone: against lit_live): net up AND 2-week pass not down AND
        # 2-week fail not up, in BOTH halves
        c = res[PAIR.get(nm, "base")]["eval"]
        better = all(e[s]["net"] > c[s]["net"] and e[s]["p10"] >= c[s]["p10"] and e[s]["f10"] <= c[s]["f10"] for s in ("H1", "H2"))
        st = "info" if nm == "base" else ("adopt-candidate" if better else ("rejected" if nm in PAIR else "promising"))
        P = {**lit.DEFAULTS, **AC.LIVE, **res[nm]["params"]}
        rl.save("lit_idm_eval_" + nm, NAMES[nm], "risk", Q, params=P,
                sizing={"mode": "two_week", **A.CFG, "idm": res[nm]["idm_mode"]}, trades=Tp, scored=rl.score(Tp, A.S26),
                status=st,
                verdict=f"Eval path (live two_week 10 sessions then safe_eval, no reset, $1.90, true 1m). 2026 H1 (pick) {he(e, 'H1')}. "
                        f"2026 H2 (check) {he(e, 'H2')}. lit_live on the same path: H1 net {b['H1']['net']:+,} 2-week "
                        f"{b['H1']['p10']}/{b['H1']['f10']}, H2 net {b['H2']['net']:+,} 2-week {b['H2']['p10']}/{b['H2']['f10']}.",
                notes="tools/lit_idm_eval.py: engine/lit.py run_x trades as units, sized by engine/sizing.lit_qty (idm_m / idm_cap "
                      "honoured since 2026-10-19), scored by tools/lit_adv_manage.py evals / mc / b2b (stored trades = the "
                      "back-to-back eval path per half).",
                writeup="lit-new-entries", tags=["lit", "lit_idm_eval"])
        print("saved lit_idm_eval_" + nm, flush=True)


if __name__ == "__main__":
    main(save=len(sys.argv) > 1 and sys.argv[1] == "save")
