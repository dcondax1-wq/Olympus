"""Night R&D 2026-11-03: where the owner's money per month comes from, on today's live settings, and what moves it.
research/writeups/2026-11-03-money-plan.md and 2026-11-03-slippage.md. Paper research only (nothing live changes).

  slots   The three MFFU slots the owner may hold (1 funded Builder 50K + 2 funded Builder 25K per person): which bot
          should sit on each? Zlarior (LIT) 50K / 25K slots on the uprisk engine (live two_week eval room_f 0.8, live
          funded preset 60% / <= $1,500 / winner <= $2,000 on the 50K, the same at half scale on the 25K, $1.90 a micro,
          eval -> 2 sessions paperwork -> funded -> payouts -> next eval, 6 months, 1,000 MC paths, 5-session blocks,
          seed 23); ATLAS 25K and BLITZ 25K from their stored slot engines (research/second/atx_funded_day.json "today",
          atlas-blitz-edge-2026-10-30.md BLITZ later-break pick). Books of LIT slots on the SAME paths (correlated).
  fleet   N Zlarior 50K-type accounts started a week apart on the same paths (MFFU 50K rules as the proxy for LucidPro /
          FundedNext 50Ks, priced at $130 a 50K eval): $ a month, the 1-in-10 bad case, P(the book loses), per account.
  slip    Extra slippage per round trip (0 / 1 / 2 / 4 / 8 ticks) on Zlarior's units: eval 2-week pass / fail + slot $
          (uprisk engine), and the trade lists of runs lit_live (LIT size), atxd_today (ATLAS 25K path) and
          ab_blitz_later_break (BLITZ 25K path) re-priced at $0.50 a micro a tick: PF / net / $ a month both periods.

    python -X utf8 tools/rd_money.py [slots|fleet|slip|all] [--n 1000]  -> research/lab/rd_money.json
"""
from __future__ import annotations

import copy
import datetime as dt
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import uprisk as U  # noqa: E402

OUT = os.path.join(ROOT, "research", "lab", "rd_money.json")
SP = ("H1", "H2", "REF")
ATLAS = json.load(open(os.path.join(ROOT, "research", "second", "atx_funded_day.json"), encoding="utf-8"))["res"]["today"]["slot"]
ATLAS_PM = {"H1": ATLAS["H1"]["pm"], "H2": ATLAS["H2"]["pm"], "REF": ATLAS["2021-25"]["pm"]}
BLITZ_PM = {"H1": 286, "H2": 52, "REF": -39}           # atlas-blitz-edge-2026-10-30.md, the adopted later-break pick, $63 evals
BLITZ_ADDON_PM = {"H1": 301, "H2": 290, "REF": 16}      # BLITZ as an add-on on LIT's funded 50K (scalp-na-mffu.md), paper only


def e50():
    return U.ecfg_of({})


def e25():
    return U.ecfg_of({}, plan="builder25k")


def e25p():
    """The fleet's 25K preset (engine/multi_account.PRESETS mffu_builder_25k, lit-builder-25k.md): 50% of the room, safe_eval
    at 30% after session 10."""
    return U.ecfg_of({"room_f": 0.5, "safe_cap": 0.3}, plan="builder25k")


def slots(n, out):
    S, BY = U.load()
    P = {sp: U.mc_paths(S, sp, n) for sp in SP}
    P60 = {sp: U.mc_paths(S, sp, n, length=60) for sp in SP}
    res = {}
    for key, plan, ec, fc, price in (("lit50", "builder50k", e50(), U.UP50, 91.80), ("lit25_63", "builder25k", e25(), U.UP25, 63.0),
                                     ("lit25_43", "builder25k", e25(), U.UP25, 43.0),
                                     ("lit25p_63", "builder25k", e25p(), U.UP25, 63.0)):
        U.PRICE[plan] = price
        row = {}
        for sp in SP:
            L = U.life(BY, P[sp], ec, fc, plan=plan)
            m = U.eval_mc(BY, P60[sp], ec, plan=plan, horizon=60)
            row[sp] = {"pm": L["net_m"], "p10_6m": L["net_p10"], "p_neg": L["p_neg"], "evals": L["evals"], "funded": L["funded"],
                       "first_pay_med": L["first_pay_med"], "p10": m["p10"], "f10": m["f10"], "dec10": m["dec10"],
                       "pass_med": m["pass_med"], "slow_pass": m["slow_pass"]}
        res[key] = row
        print(key, " | ".join(f"{sp} ${row[sp]['pm']}/mo p10/f10 {row[sp]['p10']}/{row[sp]['f10']}" for sp in SP), flush=True)
    U.PRICE.update({"builder50k": 91.80, "builder25k": 63.0})
    # LIT books on the same paths (25Ks a week = 5 sessions after the 50K, as lit-builder-25k.md recommends)
    books = {"lit50": [("builder50k", e50(), U.UP50)],
             "lit50_lit25": [("builder50k", e50(), U.UP50), ("builder25k", e25(), U.UP25)],
             "lit50_lit25_lit25": [("builder50k", e50(), U.UP50), ("builder25k", e25(), U.UP25), ("builder25k", e25(), U.UP25)],
             "lit50_lit25p": [("builder50k", e50(), U.UP50), ("builder25k", e25p(), U.UP25)]}
    B = {}
    for bk, sl in books.items():
        B[bk] = {sp: U.book(BY, S, sp, sl, n) for sp in SP}
        print("book", bk, " | ".join(f"{sp} ${B[bk][sp]['net_m']}/mo p10 ${B[bk][sp]['net_p10_m']} p_neg {B[bk][sp]['p_neg']}%" for sp in SP), flush=True)
    # the MFFU three-slot plans (ATLAS / BLITZ means added: their engines are separate; expectations add)
    plans = {
        "today: LIT 50K + ATLAS 25K + BLITZ 25K": {sp: B["lit50"][sp]["net_m"] + ATLAS_PM[sp] + BLITZ_PM[sp] for sp in SP},
        "LIT 50K + ATLAS 25K + LIT 25K": {sp: B["lit50_lit25"][sp]["net_m"] + ATLAS_PM[sp] for sp in SP},
        "LIT 50K + LIT 25K + LIT 25K": {sp: B["lit50_lit25_lit25"][sp]["net_m"] for sp in SP},
        "LIT 50K + ATLAS 25K + LIT 25K (fleet preset 50% room)": {sp: B["lit50_lit25p"][sp]["net_m"] + ATLAS_PM[sp] for sp in SP},
        "today + BLITZ add-on on LIT's funded 50K": {sp: B["lit50"][sp]["net_m"] + ATLAS_PM[sp] + BLITZ_PM[sp] + BLITZ_ADDON_PM[sp] for sp in SP},
    }
    for k, v in plans.items():
        print(f"plan {k:45s} " + " | ".join(f"{sp} ${v[sp]}/mo" for sp in SP))
    out["slots"] = {"single": res, "books": B, "plans": plans, "atlas_pm": ATLAS_PM, "blitz_pm": BLITZ_PM, "blitz_addon_pm": BLITZ_ADDON_PM}


def fleet(n, out):
    S, BY = U.load()
    res = {}
    U.PRICE["builder50k"] = 130.0
    try:
        for N in (1, 2, 3, 4, 6, 8):
            sl = [("builder50k", e50(), U.UP50)] * N
            res[N] = {sp: U.book(BY, S, sp, sl, n) for sp in SP}
            r = res[N]
            print(f"fleet {N}: " + " | ".join(f"{sp} ${r[sp]['net_m']}/mo (${r[sp]['net_m'] / N:.0f}/acct) p10 ${r[sp]['net_p10_m']} "
                                              f"p_neg {r[sp]['p_neg']}% all0 {r[sp]['p_all_zero']}% corr {r[sp]['corr_12']}" for sp in SP), flush=True)
    finally:
        U.PRICE["builder50k"] = 91.80
    out["fleet"] = {str(k): v for k, v in res.items()}


def _slip_units(BY, ticks):
    d = ticks * 0.25
    return [[{**t, "pts": t["pts"] - d, "w1": t["w1"] - d / 2} for t in ts] for ts in BY]


def _reprice(run_id, ticks):
    from tools import runlib as rl
    from tools.export_backtest import _stats
    r = rl.load(run_id)
    cols = r["trade_cols"]
    T = [dict(zip(cols, x)) for x in r["trades"]]
    for t in T:
        t["pnl"] = (t["pnl"] or 0.0) - ticks * 0.5 * (t["qty"] or 0)
    sess = [d[0] for d in r["days"]]
    o = {}
    for name, a, z in (("2026", "2026-01-01", "2026-12-31"), ("2021-25", "2021-01-01", "2025-12-31")):
        TT = [t for t in T if a <= t["day"] <= z]
        D = rl.days_of(TT, [s for s in sess if a <= s <= z])
        s = _stats(TT, D) if TT else None
        if not s:
            continue
        o[name] = {"n": s["trades"], "tpw": s["per_week"], "wk2": s["weeks_2plus_pct"], "pf": s["pf"], "net": round(s["net"]),
                   "pm": round(s["net"] / max(len(D) / 21, 1e-9)), "dd": round(s["max_dd"])}
        if run_id == "lit_live":
            o[name].update(rl.eval_speed(D))
    return o


def slip(n, out):
    S, BY = U.load()
    P = {sp: U.mc_paths(S, sp, n) for sp in SP}
    P60 = {sp: U.mc_paths(S, sp, n, length=60) for sp in SP}
    res = {"lit_slot": {}, "trades": {}}
    for k in (0, 1, 2, 4, 8):
        B2 = _slip_units(BY, k)
        row = {}
        for sp in SP:
            L = U.life(B2, P[sp], e50(), U.UP50)
            m = U.eval_mc(B2, P60[sp], e50(), horizon=60)
            row[sp] = {"pm": L["net_m"], "p10": m["p10"], "f10": m["f10"], "pass_med": m["pass_med"]}
        res["lit_slot"][k] = row
        print(f"slip +{k} ticks LIT 50K slot: " + " | ".join(f"{sp} ${row[sp]['pm']}/mo p10/f10 {row[sp]['p10']}/{row[sp]['f10']}" for sp in SP), flush=True)
        for rid in ("lit_live", "atxd_today", "ab_blitz_later_break"):
            o = _reprice(rid, k)
            res["trades"].setdefault(rid, {})[k] = o
            print(f"   {rid:22s} " + " | ".join(f"{nm} PF {v['pf']} net ${v['net']} (${v['pm']}/mo)" for nm, v in o.items()), flush=True)
    out["slip"] = res


def corr(n, out):
    """Daily / weekly P&L correlation of the three bots' stored paths (LIT size run lit_live, ATLAS 25K path atxd_today,
    BLITZ 25K path ab_blitz_later_break) and how often all three lose the same week."""
    import collections
    from tools import runlib as rl
    ids = ("lit_live", "atxd_today", "ab_blitz_later_break")
    D = {rid: {d[0]: d[1] for d in rl.load(rid)["days"]} for rid in ids}
    res = {}
    for nm, a, z in (("H1", "2026-01-01", "2026-06-30"), ("H2", "2026-07-01", "2026-10-16"), ("2021-25", "2021-01-01", "2025-12-31")):
        days = sorted(d for d in set().union(*[set(v) for v in D.values()]) if a <= d <= z)
        M = np.array([[D[r].get(d, 0.0) for d in days] for r in ids])
        c = np.corrcoef(M)
        wk = collections.defaultdict(lambda: np.zeros(3))
        for j, d in enumerate(days):
            y, w, _ = dt.date.fromisoformat(d).isocalendar()
            wk[(y, w)] += M[:, j]
        W = np.array(list(wk.values())).T
        cw = np.corrcoef(W)
        res[nm] = {"days": len(days), "daily": {"lit_atlas": round(c[0, 1], 2), "lit_blitz": round(c[0, 2], 2), "atlas_blitz": round(c[1, 2], 2)},
                   "weekly": {"lit_atlas": round(cw[0, 1], 2), "lit_blitz": round(cw[0, 2], 2), "atlas_blitz": round(cw[1, 2], 2)},
                   "weeks_all3_lose_pct": round(100 * float(np.mean((W < 0).all(0))), 1),
                   "weeks_lit_loses_pct": round(100 * float(np.mean(W[0] < 0)), 1),
                   "weeks_lit_loses_and_another_wins_pct": round(100 * float(np.mean((W[0] < 0) & ((W[1] > 0) | (W[2] > 0)))), 1)}
        print("corr", nm, res[nm], flush=True)
    out["corr"] = res


def save(n, out):
    """Runs: the LIT 25K eval path on the real order (fleet preset and room 0.8), and the LIT size trades at +2 / +4 ticks."""
    from tools import runlib as rl
    import rd_eval_dp as DP
    S, BY = U.load()
    sl = out["slots"]["single"]
    for rid, ec, key, title in (("rd_lit25k_preset_eval", e25p, "lit25p_63", "Zlarior on an MFFU Builder 25K: fleet preset (50% room, safe 30% after s10)"),
                                ("rd_lit25k_rf80_eval", e25, "lit25_63", "Zlarior on an MFFU Builder 25K: the 50K's two_week at half scale (80% room)")):
        T = DP.eval_path(S, BY, lambda ec=ec: U.Eval(ec(), "builder25k"))
        r = sl[key]
        v = (f"6-month MFFU 25K slot at $63: ${r['H1']['pm']} / ${r['H2']['pm']} / ${r['REF']['pm']} a month (H1 / H2 / 2021-25) vs BLITZ's "
             f"25K slot ${BLITZ_PM['H1']} / ${BLITZ_PM['H2']} / ${BLITZ_PM['REF']} and ATLAS's ${ATLAS_PM['H1']} / ${ATLAS_PM['H2']} / ${ATLAS_PM['REF']}; "
             f"MC 2-week pass/fail {r['H1']['p10']}/{r['H1']['f10']}, {r['H2']['p10']}/{r['H2']['f10']}, {r['REF']['p10']}/{r['REF']['f10']}. "
             "The eval columns of this run use the 50K scorer on 25K $ (read the verdict).")
        rl.save(rid, title, "risk", "Night R&D 2026-11-03: which bot should sit on the free MFFU 25K slot?",
                params={"strategy": "lit", "plan": "builder25k"}, sizing={"mode": "two_week", "plan": "builder25k"}, trades=T,
                scored=rl.score(T, S), status="adopt-candidate" if key == "lit25p_63" else "promising", verdict=v,
                notes="tools/rd_money.py slots/save; back-to-back 25K evals on the real order; $1.90 a micro.",
                writeup="2026-11-03-money-plan", tags=["slots", "25k", "money"])
        print("saved", rid, flush=True)
    r = rl.load("lit_live")
    cols = r["trade_cols"]
    for k in (2, 4):
        T = [dict(zip(cols, x)) for x in r["trades"]]
        for t in T:
            t["pnl"] = round((t["pnl"] or 0.0) - k * 0.5 * (t["qty"] or 0), 2)
        sess = [d[0] for d in r["days"]]
        rl.save(f"rd_slip_lit_{k}t", f"Zlarior live trades at +{k} ticks of slippage a round trip", "other",
                "Night R&D 2026-11-03: how much slippage does each bot survive?", params={"strategy": "lit", "slip_ticks_rt": k},
                sizing={"mode": "lit size"}, trades=T, scored=rl.score(T, sess), status="info",
                verdict=f"Run lit_live re-priced at $0.50 a micro a tick x {k}.", notes="tools/rd_money.py slip/save",
                writeup="2026-11-03-slippage", tags=["slippage", "stress"])
        print("saved slip", k, flush=True)


def idle(n, out):
    """MFFU 7-day inactivity: on the real order (back-to-back evals), how many evals sit 5+ sessions (= 7+ calendar days)
    without a single trade while still open (the zombie-eval risk of a small room share)?"""
    S, BY = U.load()
    res = {}
    for key, mk, plan in (("lit50_live", e50, "builder50k"), ("lit25_preset", e25p, "builder25k"), ("lit25_rf80", e25, "builder25k")):
        row = {}
        for nm, a, z in (("2026", "2026-01-01", "2026-10-16"), ("2021-25", "2021-01-01", "2025-12-31")):
            ix = [i for i, d in enumerate(S) if a <= d <= z]
            e, gap, evals, idle_evals, hit = U.Eval(mk(), plan), 0, 1, 0, False
            for i in ix:
                d0 = e.dtr
                r = e.step(BY[i])
                gap = 0 if e.dtr > d0 else gap + 1
                if gap >= 5 and not hit:
                    hit = True
                    idle_evals += 1
                if r:
                    e, gap, hit = U.Eval(mk(), plan), 0, False
                    evals += 1
            row[nm] = {"evals": evals, "evals_idle_7d": idle_evals, "pct": round(100.0 * idle_evals / evals, 1)}
        res[key] = row
        print("idle", key, row, flush=True)
    out["idle"] = res


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    what = args[0] if args else "all"
    n = int(sys.argv[sys.argv.index("--n") + 1]) if "--n" in sys.argv else 1000
    out = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
    for name, fn in (("slots", slots), ("fleet", fleet), ("slip", slip), ("corr", corr), ("idle", idle), ("save", save)):
        if what == name or (what == "all" and name != "save"):
            fn(n, out)
    out["built"] = dt.date.today().isoformat()
    out["n"] = n
    json.dump(out, open(OUT, "w", encoding="utf-8"), indent=1, default=float)
    print("->", OUT)


if __name__ == "__main__":
    main()
