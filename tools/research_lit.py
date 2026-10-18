"""LIT (Liquidity Inducement Theorem) research runner: builds every LIT component from CME NQ1! 5m (engine/lit.py),
backtests rule variants and scores each exactly like tools/runlib.py (rl.score on the same 1,278 sessions as run
`baseline`), so the numbers sit next to the locked Liquidity Engine.

  python tools/research_lit.py grid       # one-factor tests + combinations -> research/lab/lit_results.json
  python tools/research_lit.py critic     # year by year, odd/even months, neighbours of the best variant
  python tools/research_lit.py save       # store the headline LIT runs with rl.save (family other, tag lit)
  python tools/research_lit.py charts     # 8 example trade charts -> research/study/lit/
"""
from __future__ import annotations

import json
import os
import pickle
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import lit  # noqa: E402
from engine.analytics import PLANS, monte_carlo  # noqa: E402
from tools import runlib as rl  # noqa: E402

CACHE = os.path.join(ROOT, "research", "runs", "_cache")
OUT = os.path.join(ROOT, "research", "lab", "lit_results.json")
BASE = rl.load("baseline")
SESS = [d[0] for d in BASE["days"]]
ALL_CLS = ("buildup", "asia", "london", "ny", "pre", "pd", "pw", "pm", "gap")


def market(tol_atr=0.15, **kw):
    key = f"lit_{tol_atr}_{json.dumps(kw, sort_keys=True)}_{rl._data_key()}".replace(" ", "")
    p = os.path.join(CACHE, key.replace(":", "_").replace("{", "").replace("}", "").replace('"', "") + ".pkl")
    M = lit.Market(tol_atr=tol_atr)
    if os.path.exists(p):
        C = pickle.load(open(p, "rb"))
    else:
        C = lit.candidates(M, **kw)
        os.makedirs(CACHE, exist_ok=True)
        pickle.dump(C, open(p, "wb"))
    return M, C


def mc_rate(days, a, z):
    pn = [d["pnl"] for d in days if a <= d["date"] <= z]
    m = monte_carlo(pn, PLANS["builder_50k"], runs=2000, horizon=60)
    tot = m["pass_prob"] + m["fail_prob"]
    return round(100 * m["pass_prob"] / tot, 1) if tot else None


def score(T, mc=False):
    S = rl.score(T, SESS)
    if mc:
        for nm, a, z in rl.SPANS:
            S["spans"][nm]["mc_pass_rate"] = mc_rate(S["days"], a, z)
    return S


def row(S):
    o = {}
    for nm in ("2026", "2021-25", "all"):
        s = S["spans"][nm]
        o[nm] = {k: s.get(k) for k in ("n", "tpw", "wk2", "win", "pf", "net", "per_month", "dd", "avg_r", "stop", "p10", "f10", "p20",
                                        "f20", "b2b", "mc_pass_rate")}
    o["years"] = S["years"]
    return o


# ------------------------------------------------------------------------------------------------ variant definitions
WIN = {
    "ny_am": [(570, 690)],                     # 09:30-11:30 (the engine's AM killzone)
    "ny_am830": [(510, 690)],                  # 08:30-11:30
    "ny_am_lc": [(570, 660)],                  # 09:30-11:00 (stop at London close)
    "ny_both": [(570, 690), (810, 930)],       # AM + PM killzones (09:30-11:30, 13:30-15:30), as the engine
    "london": [(120, 300)],                    # 02:00-05:00
    "lon_ny": [(120, 300), (570, 690)],
    "all3": [(120, 300), (570, 690), (810, 930)],
    "day": [(120, 930)],                       # 02:00-15:30
}

LIQ = {
    "all": set(ALL_CLS),
    "sessions": {"asia", "london", "ny", "pre"},
    "asia_london": {"asia", "london"},
    "ny_trap": {"ny"},
    "daily": {"pd", "pw", "pm"},
    "buildup": {"buildup"},
    "no_buildup": set(ALL_CLS) - {"buildup"},
}

# specific session definitions (swept names)
SESS_DEF = {
    "asia20": {"asia20_h", "asia20_l"}, "asia18": {"asia18_h", "asia18_l"}, "asia19": {"asia19_h", "asia19_l"},
    "lon25": {"lon25_h", "lon25_l"}, "lon34": {"lon34_h", "lon34_l"}, "lon23": {"lon23_h", "lon23_l"},
    "ny89": {"ny89_h", "ny89_l"}, "ny830": {"ny830_h", "ny830_l"}, "ny930": {"ny930_h", "ny930_l"},
    "ny9301030": {"ny9301030_h", "ny9301030_l"}, "pre": {"pre_h", "pre_l"},
}


def in_win(z, w):
    return any(a <= z["mod"] < b for a, b in WIN[w])


def make(win="ny_both", liq="all", names=None, ind=0, vec=None, disp=0.0, po3=None, po3_disc=None, vix=None, how=None,
         wk_ext=None, depth=None, dows=None, maxbars=None, **exec_kw):
    """A variant = an entry-time filter on the candidates + executor settings."""
    L = LIQ[liq]

    def f(z):
        if not in_win(z, win):
            return False
        if names is not None:
            if not (set(z["swept"]) & names):
                return False
        elif not (set(z["swept_cls"]) & L):
            return False
        if z["ind_n"] < ind:
            return False
        if vec == "climax" and not z["vec"]:
            return False
        if vec == "any" and not z["vec_any"]:
            return False
        if vec == "none" and z["vec_any"]:
            return False
        if z["disp"] < disp:
            return False
        if po3:
            p = z["po3"].get(po3)
            if p is None or not p[0]:
                return False
        if po3_disc:
            p = z["po3"].get(po3_disc)
            if p is None or not p[1]:
                return False
        if vix is not None:
            ve = z["vix_ext"]
            if ve is None or not (vix[0] <= ve < vix[1]):
                return False
        if how is not None and z["how"] != how:
            return False
        if wk_ext is not None and z["wk_ext"] != wk_ext:
            return False
        if depth is not None and not (depth[0] <= z["depth_atr"] < depth[1]):
            return False
        if dows is not None and z["dow"] not in dows:
            return False
        if maxbars is not None and z["bars"] > maxbars:
            return False
        return True

    cfg = {"filt": f, "classes": ALL_CLS, "min_rr": 1.5, "max_rr": 5.0, "stop_buf": 2.0, "min_stop": 8.0, "max_stop": 60.0,
           "be_r": 1.0, "time_bars": None, "max_per_day": 1}
    cfg.update(exec_kw)
    return cfg


def go(M, C, cfg, cold=False, mc=False):
    T = lit.run(M, C, cfg, SESS)
    if cold:
        T = lit.cold_size(T)
    return T, score(T, mc=mc)


def short(S):
    o = []
    for nm in ("2026", "2021-25"):
        s = S["spans"][nm]
        o.append(f"{nm}: n={s.get('n')} tpw={s.get('tpw')} PF={s.get('pf')} net={s.get('net')} dd={s.get('dd')}")
        o[-1] += f" 2w={s.get('p10')}/{s.get('f10')}" if s.get('n') else ""
    return " | ".join(o)


def brief(S):
    a, b = S["spans"]["2026"], S["spans"]["2021-25"]
    f = lambda s: (f"n={s.get('n')} tpw={s.get('tpw')} win={s.get('win')} PF={s.get('pf')} net={s.get('net')} $/mo={s.get('per_month')} "
                   f"DD={s.get('dd')} 2w={s.get('p10')}/{s.get('f10')} 1m={s.get('p20')}/{s.get('f20')}")
    return f"26[{f(a)}] | 21-25[{f(b)}]"


# ------------------------------------------------------------------------------------------------ grid
BASES = {"day": dict(win="day", liq="all", entry="ref", max_stop=80),
         "ny": dict(win="ny_both", liq="all", entry="ref", max_stop=80),
         "lon_ny": dict(win="lon_ny", liq="all", entry="ref", max_stop=80)}
BASE_V = BASES["day"]


def grid(base="day"):
    global BASE_V
    BASE_V = BASES[base]
    res = {}
    M, C = market()
    print(len(C), "candidates", flush=True)

    def t(name, **kw):
        v = {**BASE_V, **kw}
        T, S = go(M, C, make(**v))
        res[name] = {"variant": {k: (sorted(x) if isinstance(x, set) else x) for k, x in v.items()}, **row(S)}
        print(f"{name:24s} {short(S)}", flush=True)
        return S

    t("base")
    for em in ("market", "ref", "fib50", "fib62", "fib70"):
        t(f"entry_{em}", entry=em)
    t("wait6", wait=6); t("wait24", wait=24)
    # entry windows (incl. London) and session markers
    for w in WIN:
        t(f"win_{w}", win=w)
    # which liquidity counts
    for q in LIQ:
        t(f"liq_{q}", liq=q)
    # session box definitions (sweep of that box only)
    for nm, ss in SESS_DEF.items():
        t(f"box_{nm}", names=ss, win="day")
        t(f"box_{nm}_nyb", names=ss)
    # inducement
    for k in (1, 2, 3):
        t(f"ind_{k}", ind=k)
    # vector candles / displacement
    for v in ("climax", "any", "none"):
        t(f"vec_{v}", vec=v)
    for x in (0.5, 0.8, 1.0, 1.5):
        t(f"disp_{x}", disp=x)
    # PO3 (manipulation beyond the HTF open / entry still in discount)
    for p in ("1h", "4h", "d", "00", "830", "930", "wk", "22"):
        t(f"po3man_{p}", po3=p)
        t(f"po3disc_{p}", po3_disc=p)
    # VIX implied one-day move: how far the sweep extreme sits from the 18:00 open, in "VIX moves"
    for lo, hi in ((-9, 0.5), (0.5, 9), (0.25, 9), (-9, 0.25), (0.75, 9), (0.5, 1.25)):
        t(f"vix_{lo}_{hi}", vix=(lo, hi))
    # high/low-of-week window
    t("how_in", how=True); t("how_out", how=False); t("wkext_yes", wk_ext=True); t("wkext_no", wk_ext=False)
    # sweep depth
    for lo, hi in ((0, 0.5), (0.5, 9), (0, 1.0), (1.0, 99)):
        t(f"depth_{lo}_{hi}", depth=(lo, hi))
    # weekday (daily separators) - reported, calendar rules are not adopted
    for dd in range(5):
        t(f"dow_skip{dd}", dows=set(range(5)) - {dd})
    t("maxbars6", maxbars=6); t("maxbars12", maxbars=12)
    # targets
    t("tgt_buildup", classes=("buildup",), fallback_rr=None)
    t("tgt_sessions", classes=("asia", "london", "ny", "pre"))
    t("tgt_daily", classes=("pd", "pw", "pm"))
    t("tgt_bu_daily", classes=("buildup", "pd", "pw", "pm"))
    t("tgt_noban", max_rr=None)
    t("tgt_bank3", max_rr=3.0)
    t("tgt_minrr1", min_rr=1.0); t("tgt_minrr2", min_rr=2.0)
    t("tgt_fb2", fallback_rr=2.0)
    for r in (2.0, 3.0, 4.0):
        t(f"fixed_{r}R", fixed_rr=r)
    # management
    t("be_none", be_r=None); t("be_2", be_r=2.0); t("be_15", be_r=1.5)
    t("time6", time_bars=6, time_min_r=0.0); t("time12", time_bars=12, time_min_r=0.0)
    t("stopbuf1", stop_buf=1.0); t("stopbuf4", stop_buf=4.0)
    t("stop_10_40", min_stop=10, max_stop=40); t("stop_5_80", min_stop=5, max_stop=80)
    t("perday2", max_per_day=2)
    # alternative detector settings (swing look-backs, tolerance)
    for kw in ({"leg": 12}, {"leg": 36}, {"sweep_win": 12}, {"sweep_win": 48}):
        M2, C2 = market(**kw)
        nm = "det_" + "_".join(f"{k}{v}" for k, v in kw.items())
        T, S = go(M2, C2, make(**BASE_V))
        res[nm] = {"variant": {**BASE_V, "detector": kw}, **row(S)}
        print(f"{nm:24s} {short(S)}", flush=True)
    for tol in (0.08, 0.3):
        M2, C2 = market(tol_atr=tol)
        T, S = go(M2, C2, make(**BASE_V))
        res[f"det_tol{tol}"] = {"variant": {**BASE_V, "tol_atr": tol}, **row(S)}
        print(f"{'det_tol' + str(tol):24s} {short(S)}", flush=True)
    json.dump(res, open(OUT.replace(".json", f"_{base}.json"), "w"), indent=1)
    print("wrote", OUT)


def edge_table(res):
    """Each confluence's own edge: with vs without, in both periods."""
    b = res["base"]
    rows = []
    for k, v in res.items():
        if k == "base":
            continue
        a, c = v["2026"], v["2021-25"]
        rows.append((k, a["n"], a["pf"], a["net"], c["n"], c["pf"], c["net"],
                     (a["pf"] or 0) > (b["2026"]["pf"] or 0) and (c["pf"] or 0) > (b["2021-25"]["pf"] or 0)))
    return rows


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "grid"
    if cmd == "grid":
        grid(sys.argv[2] if len(sys.argv) > 2 else "day")
    elif cmd == "edges":
        res = json.load(open(OUT.replace(".json", f"_{sys.argv[2] if len(sys.argv) > 2 else 'day'}.json")))
        for r in edge_table(res):
            print("%-26s 26: n=%4s PF=%5s net=%7s | 21-25: n=%4s PF=%5s net=%7s %s" % (*r[:7], "BOTH" if r[7] else ""))
