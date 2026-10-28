"""The momentum-scalp picks (tools/scalp_mo.py grids, picked on 2026 H1): full numbers, MFFU eval sizing, placebo,
look-ahead check, run library + research/scalp/mo_best_trades.json.

    python -X utf8 tools/scalp_mo_pick.py            # table + research/scalp/mo_picks.json
    python -X utf8 tools/scalp_mo_pick.py save       # + rl.save runs scalp_mo_* + mo_best_trades.json
    python -X utf8 tools/scalp_mo_pick.py lookahead  # signals on cut data == full data (a few cut days per pick)
Paper research only.
"""
from __future__ import annotations

import json
import os
import sys
import warnings

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import scalp_mo as S  # noqa: E402
from tools import scalp_mo_lib as L  # noqa: E402

warnings.filterwarnings("ignore")
OUT = os.path.join(ROOT, "research", "scalp")

# tf = the timeframe the rule was picked on (1 = 1m, 2026 only; its 2021-25 line is the same rule on 5m bars)
PICKS = {
    "na_scalp": {"fam": "na", "tf": 1, "maxday": 6, "day_stop": 3.0,
                 "p": {"vm": 1.0, "every": 30, "stop": "a5x1.5", "trail": 1.5, "trail_start": 1.0, "win": [630, 930], "hold_min": 30},
                 "title": "Noise-area momentum scalp (1m, checked every 30 min, 10:30-15:30, 30-min max hold)"},
}
SIZES = {"25k": [(f, c) for f in (0.2, 0.3, 0.4, 0.5) for c in (200.0, 300.0, 400.0, 600.0)],
         "50k": [(f, c) for f in (0.2, 0.3, 0.4) for c in (400.0, 600.0, 800.0, 1200.0)]}
FIXED = {"25k": 150.0, "50k": 300.0}


def trades(name, tf=None):
    P = PICKS[name]
    tf = tf or P["tf"]
    B = L.bars(tf)
    T = S.run(B, P["fam"], S._resolve(B, P["fam"], P["p"]), maxday=P["maxday"], day_stop=P["day_stop"])
    return B, T


def placebo(name, seeds=60):
    P = PICKS[name]
    out = {}
    for tf, spans in ((P["tf"], ("H1", "H2")), (5, ("R",))):
        B = L.bars(tf)
        pp = S._resolve(B, P["fam"], P["p"])
        T = S.run(B, P["fam"], pp, maxday=P["maxday"], day_stop=P["day_stop"])

        def ar(T, sp):
            Ss = L.sessions(B, sp)
            r = [t["pnl_pm"] / t["risk_pm"] for t in T if Ss[0] <= t["day"] <= Ss[-1]]
            return float(np.mean(r)) if r else 0.0
        pl = {sp: [] for sp in spans}
        for sd in range(seeds):
            Tp = S.run(B, P["fam"], pp, maxday=P["maxday"], day_stop=P["day_stop"], placebo=sd)
            for sp in spans:
                pl[sp].append(ar(Tp, sp))
        for sp in spans:
            a = np.array(pl[sp])
            out[sp] = {"real_r": round(ar(T, sp), 3), "placebo_r": round(float(a.mean()), 3), "p": round(float((a >= ar(T, sp)).mean()), 3)}
    return out


def evals(T, B, span, plan):
    Ss = L.sessions(B, span)
    Ts = [t for t in T if Ss[0] <= t["day"] <= Ss[-1]]
    return {f"{f}_{int(c)}": L.eval_score(Ts, Ss, plan, f, c) for f, c in SIZES[plan]}


def report(name):
    P = PICKS[name]
    res = {"name": name, **P}
    B1, T1 = trades(name, P["tf"])
    B5, T5 = trades(name, 5)
    lines = {}
    for sp, (B, T) in (("H1", (B1, T1)), ("H2", (B1, T1)), ("R", (B5, T5)), ("2025", (B5, T5)), ("2021-24", (B5, T5))):
        Ss = L.sessions(B, sp)
        row = {"fixed25": L.stats(T, Ss, FIXED["25k"], 20), "fixed50": L.stats(T, Ss, FIXED["50k"], 40)}
        for plan in ("25k", "50k"):
            row["eval_" + plan] = evals(T, B, sp, plan)
        lines[sp] = row
    # the eval size: picked on H1 by 2-week pass minus 2-week fail, then the H1 path $ as a tie-break
    for plan in ("25k", "50k"):
        E = lines["H1"]["eval_" + plan]
        best = max(E, key=lambda k: (E[k]["p10"] - E[k]["f10"], E[k]["path_net"]))
        res["size_" + plan] = best
    res["lines"] = lines
    return res, (B1, T1, B5, T5)


def fmt_row(sp, r, plan, size):
    s = r["fixed25" if plan == "25k" else "fixed50"]
    e = r["eval_" + plan][size]
    if not s.get("n"):
        return f"  {sp:7} no trades"
    return (f"  {sp:7} {s['tpw']:5}/wk win {s['win']:4}% avgR {s['avg_r']:6} PF {s['pf']:4} net ${s['net']:>7} ${s['per_month']:>5}/mo "
            f"DD ${s['dd']:>6} cost {s['cost_share']:5}% | eval {plan} {size}: p10 {e['p10']:4} f10 {e['f10']:4} dec10 {e['dec10']:4} "
            f"p15 {e['p15']:4} f15 {e['f15']:4} med {e['pass_med']} slow {e['slow_pass']} path ${e['path_net']:>6} (${e['path_pm']}/mo, "
            f"{e['b2b']} P/F, fees ${e['fees']:.0f}, net-fees ${e['path_net_less_fees']}) qty {e['med_qty']}")


def main(save=False, names=None):
    allres = {}
    for name in names or PICKS:
        res, (B1, T1, B5, T5) = report(name)
        res["placebo"] = placebo(name, 40)
        allres[name] = res
        print(f"== {name}: {PICKS[name]['title']}\n   {json.dumps(PICKS[name]['p'])} maxday {PICKS[name]['maxday']} day_stop {PICKS[name]['day_stop']}R")
        for plan in ("25k", "50k"):
            for sp in ("H1", "H2", "R", "2025", "2021-24"):
                print(fmt_row(sp, res["lines"][sp], plan, res["size_" + plan]))
        print("   placebo (random direction, same bars):", res["placebo"])
        if save:
            store(name, res, T1, T5)
    json.dump(allres, open(os.path.join(OUT, "mo_picks.json"), "w"), indent=1, default=float)
    return allres


def store(name, res, T1, T5):
    from tools import runlib as rl
    P = PICKS[name]
    # 2026 from the pick's own timeframe, 2021-25 from 5m (same rule)
    T = [t for t in T5 if t["day"] < "2026-01-01"] + [t for t in T1 if t["day"] >= "2026-01-01"]
    tr = L.runlib_trades(T, FIXED["25k"], 20)
    for t, x in zip(tr, T):
        t["trigger"] = name
    B1, B5 = L.bars(P["tf"]), L.bars(5)
    sess = sorted(set(L.sessions(B5, "R")) | set(L.sessions(B1, "H1")) | set(L.sessions(B1, "H2")))
    S_ = rl.score(tr, sess)
    h1, h2, r = res["lines"]["H1"], res["lines"]["H2"], res["lines"]["R"]
    sz = res["size_25k"]
    verdict = (f"H1 PF {h1['fixed25']['pf']} / H2 PF {h2['fixed25']['pf']} / 2021-25 PF {r['fixed25']['pf']} at ${FIXED['25k']:.0f} a trade; "
               f"25K eval ({sz}) 2-week pass/fail H1 {h1['eval_25k'][sz]['p10']}/{h1['eval_25k'][sz]['f10']}, "
               f"H2 {h2['eval_25k'][sz]['p10']}/{h2['eval_25k'][sz]['f10']}")
    rl.save("scalp_mo_" + name, P["title"], "other", "Owner 2026-10-28: a momentum scalp (several trades a day) for its own MFFU account?",
            params={"fam": P["fam"], "tf": P["tf"], **P["p"], "maxday": P["maxday"], "day_stop_r": P["day_stop"]},
            sizing={"fixed_usd": FIXED["25k"], "eval_25k": sz, "eval_50k": res["size_50k"]}, trades=tr, scored=S_,
            status="info", verdict=verdict, notes="tools/scalp_mo_pick.py; 2026 on the pick's timeframe, 2021-25 = the same rule on 5m bars",
            writeup="scalp-momentum", tags=["scalp", "momentum", "third-strategy"])


def best_trades(name):
    P = PICKS[name]
    B, T = trades(name, P["tf"])
    import datetime as dt
    from zoneinfo import ZoneInfo
    et = ZoneInfo("America/New_York")
    f = lambda x: dt.datetime.fromtimestamp(x, et).strftime("%Y-%m-%d %H:%M")
    rows = [{"entry_t": f(t["entry_t"]), "exit_t": f(t["exit_t"]), "dir": "long" if t["dir"] > 0 else "short", "entry": t["entry"],
             "stop": t["stop"], "target": round(t["target"], 2), "exit": t["exit"], "exit_kind": t["exit_kind"], "pts": t["pts"],
             "risk_pts": t["risk_pts"], "r": round(t["pnl_pm"] / t["risk_pm"], 3)} for t in T]
    json.dump({"name": name, "title": P["title"], "rule": P["p"], "maxday": P["maxday"], "day_stop_r": P["day_stop"], "tf": f"{P['tf']}m",
               "note": "entry/exit_t ET = bar open time of the fill bar / end of the exit bar; prices include 1 tick slippage on market and "
                       "stop fills; target = limit (traded through by 1 tick). $ = pts x $2 x micros - $1.90 a micro.",
               "trades": rows}, open(os.path.join(OUT, "mo_best_trades.json"), "w"), indent=0)
    return len(rows)


def lookahead(name, cuts=6):
    """Signals and fills on data cut at a few times inside the 2026 sessions == the full-data run for trades that ended before the cut."""
    P = PICKS[name]
    B = L.bars(P["tf"])
    full = trades(name)[1]
    rng = np.random.default_rng(1)
    days = [d for d in L.sessions(B, "H1") + L.sessions(B, "H2")]
    bad = 0
    for d in rng.choice(days, cuts, replace=False):
        i = int(np.where(B["dates"] == d)[0][0])
        idx = np.where(B["day"] == i)[0]
        cut_t = int(B["t"][idx[(B["mod"][idx] >= 780)][0]])     # 13:00 ET
        Bc = L._bars(P["tf"], "2021-11-01", cut_t=cut_t)
        Tc = S.run(Bc, P["fam"], S._resolve(Bc, P["fam"], P["p"]), maxday=P["maxday"], day_stop=P["day_stop"])
        a = [(t["entry_t"], t["dir"], t["entry"], t["exit"]) for t in full if t["exit_t"] < cut_t and t["day"] >= "2026-01-01"]
        b = [(t["entry_t"], t["dir"], t["entry"], t["exit"]) for t in Tc if t["exit_t"] < cut_t and t["day"] >= "2026-01-01"]
        diff = len(set(a) ^ set(b))
        bad += diff
        print(f"  cut {d} 13:00: {len(a)} closed trades, {diff} differ")
    return bad


if __name__ == "__main__":
    a = sys.argv[1:]
    if a and a[0] == "lookahead":
        for n in a[1:] or PICKS:
            print(n, "differences:", lookahead(n))
    else:
        main(save=bool(a and a[0] == "save"), names=[x for x in a if x in PICKS] or None)
