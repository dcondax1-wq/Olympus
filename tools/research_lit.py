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


# ------------------------------------------------------------------------------------------------ combinations + critic
CONF = {
    "disp1": dict(disp=1.0),
    "vix05": dict(vix=(-9, 0.5)),
    "how": dict(how=True),
    "depth05": dict(depth=(0.5, 99)),
    "tgt_daily": dict(classes=("pd", "pw", "pm")),
    "fixed4": dict(fixed_rr=4.0),
    "po3_00": dict(po3="00"),
    "vec": dict(vec="climax"),
    "ind2": dict(ind=2),
}


def quick(T, sess=SESS):
    """Fast stats for a search: per period n, trades/week, PF, net; plus odd / even calendar months (all years)."""
    import collections as co
    nd = co.Counter(d[:4] >= "2026" for d in sess)
    out = {}
    for nm, sel, days in (("2026", lambda d: d >= "2026", nd[True]), ("2021-25", lambda d: d < "2026", nd[False]),
                          ("odd", lambda d: int(d[5:7]) % 2 == 1, sum(1 for d in sess if int(d[5:7]) % 2)),
                          ("even", lambda d: int(d[5:7]) % 2 == 0, sum(1 for d in sess if not int(d[5:7]) % 2))):
        p = np.array([t["pnl"] for t in T if sel(t["day"])] or [0.0])
        gl = -p[p < 0].sum()
        out[nm] = {"n": int((p != 0).sum()), "tpw": round(len([t for t in T if sel(t["day"])]) / max(days / 5, 1e-9), 2),
                   "pf": round(float(p[p > 0].sum() / gl), 2) if gl else None, "net": round(float(p.sum()))}
    return out


def combos(base="day"):
    import itertools
    M, C = market()
    keys = list(CONF)
    rows = []
    for r in range(0, 4):
        for ks in itertools.combinations(keys, r):
            if "tgt_daily" in ks and "fixed4" in ks:
                continue
            v = {**BASES[base]}
            for k in ks:
                v.update(CONF[k])
            T = lit.run(M, C, make(**v), SESS)
            q = quick(T)
            rows.append({"base": base, "conf": list(ks), **q})
    rows.sort(key=lambda x: -(x["odd"]["pf"] or 0))
    json.dump(rows, open(os.path.join(ROOT, "research", "lab", f"lit_combos_{base}.json"), "w"), indent=0)
    print(f"{len(rows)} combos; top 15 by ODD-month PF (selection), with EVEN months as the check, tpw >= 2 in both periods:")
    k = 0
    for x in rows:
        if x["2026"]["tpw"] < 2 or x["2021-25"]["tpw"] < 2:
            continue
        print(f"{'+'.join(x['conf']) or 'base':32s} odd PF {x['odd']['pf']} ${x['odd']['net']} | even PF {x['even']['pf']} ${x['even']['net']}"
              f" | 2026 n={x['2026']['n']} tpw={x['2026']['tpw']} PF={x['2026']['pf']} ${x['2026']['net']}"
              f" | 21-25 n={x['2021-25']['n']} tpw={x['2021-25']['tpw']} PF={x['2021-25']['pf']} ${x['2021-25']['net']}")
        k += 1
        if k >= 15:
            break


CAND = {
    "A": {**BASES["day"], "disp": 1.0, "depth": (0.5, 99), "classes": ("pd", "pw", "pm")},
    "B": {**BASES["day"], "vix": (-9, 0.5), "depth": (0.5, 99), "classes": ("pd", "pw", "pm")},
    "AB": {**BASES["day"], "disp": 1.0, "vix": (-9, 0.5), "depth": (0.5, 99), "classes": ("pd", "pw", "pm")},
}


def full_line(S, nm):
    s = S["spans"][nm]
    return (f"{nm}: n={s['n']} tpw={s['tpw']} wk2={s['wk2']}% win={s['win']}% PF={s['pf']} net={s['net']:+,} (${s['per_month']:,}/mo) "
            f"DD={s['dd']:,} 2w {s['p10']}/{s['f10']} 1m {s['p20']}/{s['f20']} MCpass {s.get('mc_pass_rate')}% b2b {s['b2b']} medstop {s['stop']}")


def slip_extra(T, ticks=2):
    out = []
    for t in T:
        x = dict(t); x["pnl"] = round(t["pnl"] - ticks * lit.TICK * lit.PV * t["qty"], 2); out.append(x)
    return out


def critic(names=("A", "B", "AB")):
    M, C = market()
    rep = {}
    for nm in names:
        v = CAND[nm]
        T = lit.run(M, C, make(**v), SESS)
        S = score(T, mc=True)
        print(f"=== {nm} {v}")
        for sp in ("2026", "2021-25", "all"):
            print("  " + full_line(S, sp))
        print("  years:", {y: (x["n"], x["pf"], x["net"]) for y, x in S["years"].items()})
        q = quick(T)
        print("  odd/even months:", q["odd"], q["even"])
        Q = quick(slip_extra(T))
        print("  +2 ticks slippage: 2026", Q["2026"], "21-25", Q["2021-25"])
        longs = [t for t in T if t["dir"] == 1]; shorts = [t for t in T if t["dir"] == -1]
        print("  longs", quick(longs)["2021-25"], quick(longs)["2026"], "| shorts", quick(shorts)["2021-25"], quick(shorts)["2026"])
        nb = {}
        tweaks = {"disp0.8": {"disp": 0.8}, "disp1.2": {"disp": 1.2}, "depth0.3": {"depth": (0.3, 99)}, "depth0.75": {"depth": (0.75, 99)},
                  "vix0.4": {"vix": (-9, 0.4)}, "vix0.6": {"vix": (-9, 0.6)}, "maxstop60": {"max_stop": 60}, "maxstop100": {"max_stop": 100},
                  "market": {"entry": "market"}, "lon_ny": {"win": "lon_ny"}, "all3": {"win": "all3"}, "be_none": {"be_r": None},
                  "be1.5": {"be_r": 1.5}, "minrr1": {"min_rr": 1.0}, "minrr2": {"min_rr": 2.0}, "bank3": {"max_rr": 3.0}, "nobank": {"max_rr": None},
                  "buf1": {"stop_buf": 1.0}, "buf4": {"stop_buf": 4.0}, "wait6": {"wait": 6}, "wait24": {"wait": 24},
                  "tgt+bu": {"classes": ("pd", "pw", "pm", "buildup")}, "tgt+sess": {"classes": ("pd", "pw", "pm", "asia", "london", "ny")}}
        for k, tw in tweaks.items():
            if k.startswith("vix") and "vix" not in v or k.startswith("disp") and "disp" not in v:
                continue
            q2 = quick(lit.run(M, C, make(**{**v, **tw}), SESS))
            nb[k] = q2
            print(f"  nb {k:10s} 2026 n={q2['2026']['n']} PF={q2['2026']['pf']} ${q2['2026']['net']} | 21-25 n={q2['2021-25']['n']} "
                  f"PF={q2['2021-25']['pf']} ${q2['2021-25']['net']}")
        for kw in ({"leg": 18}, {"leg": 36}, {"sweep_win": 12}, {"sweep_win": 36}):
            M2, C2 = market(**kw)
            q2 = quick(lit.run(M2, C2, make(**v), SESS)); nb[str(kw)] = q2
            print(f"  nb {str(kw):10s} 2026 n={q2['2026']['n']} PF={q2['2026']['pf']} ${q2['2026']['net']} | 21-25 n={q2['2021-25']['n']} "
                  f"PF={q2['2021-25']['pf']} ${q2['2021-25']['net']}")
        rep[nm] = {"variant": {k: (list(x) if isinstance(x, (tuple, set)) else x) for k, x in v.items()}, **row(S), "odd_even": q,
                   "slip2": Q, "neighbours": nb}
    json.dump(rep, open(os.path.join(ROOT, "research", "lab", "lit_critic.json"), "w"), indent=1)


RUNS = {
    "lit_textbook_ny": ("LIT as taught, NY killzones, market entry", {**BASES["ny"], "entry": "market", "max_stop": 60}, "rejected",
                        "Pure LIT (sweep -> structure shift, market entry next bar, stop beyond the protected low) in the NY killzones: "
                        "too few trades (0.5/wk in 2026) and it loses money in 2021-25."),
    "lit_raw_day": ("LIT, 02:00-15:30, retest entry, no confluence filters", BASES["day"], "rejected",
                    "Every LIT setup of the day with a limit entry on the retest of the broken structure: about break-even (PF 0.97 / 1.01)."),
    "lit_A": ("LIT best: displacement >= 1 ATR, sweep >= 0.5 ATR deep, targets PDH/PWH/PMH", CAND["A"], "info",
              "Best LIT variant (picked on odd months only). Profitable in 2026 and 2021-25 and in every neighbour, but thin "
              "(PF 1.26 / 1.15), drawdown -$21k and MFFU evals fail more often than they pass; well below the locked bot in 2026."),
    "lit_B": ("LIT: VIX-move filter, sweep >= 0.5 ATR deep, targets PDH/PWH/PMH", CAND["B"], "info",
              "Runner-up: best 2021-25 money (+$43.6k) but 2026 PF only 1.15 and all of the 2021-25 edge comes from longs."),
}


def save_runs():
    M, C = market()
    for rid, (title, v, status, verdict) in RUNS.items():
        T = lit.run(M, C, make(**v), SESS)
        S = score(T, mc=True)
        vv = {k: (list(x) if isinstance(x, (tuple, set)) else x) for k, x in v.items()}
        rl.save(rid, title, "other", "Does the owner's LIT method (Liquidity Inducement Theorem) beat the Liquidity Engine?",
                params=vv, trades=T, scored=S, status=status, verdict=verdict, writeup="lit-strategy", tags=["lit"],
                notes="engine/lit.py + tools/research_lit.py; separate strategy, not the live engine; no cold-streak filter; "
                      "size $800 up to a 20-pt stop then 800x20/stop, MNQ, max 40 micros, $1.40/micro + 1 tick slippage")
        print(rid, full_line(S, "2026")); print("   ", full_line(S, "2021-25"))


def charts(n=8):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import datetime as dt
    from zoneinfo import ZoneInfo
    ET = ZoneInfo("America/New_York")
    M, C = market()
    T = lit.run(M, C, make(**CAND["A"]), SESS)
    out = os.path.join(ROOT, "research", "study", "lit")
    os.makedirs(out, exist_ok=True)
    pick = []
    for want, k in (("TARGET", 4), ("STOP", 2), ("BE", 1), ("EOD", 1)):
        for yr in ("2026", "2025", "2024", "2023"):
            xs = [t for t in T if t["exit"] == want and t["day"][:4] == yr and t not in pick]
            if xs and sum(1 for p in pick if p["exit"] == want) < k:
                pick.append(xs[len(xs) // 2])
    names = []
    for t in pick[:n]:
        k = M.day_of[t["entry_i"]]
        a = max(t["sweep_i"] - 30, M.days[k][1]); z = min(t["exit_i"] + 12, M.n - 1)
        idx = np.arange(a, z + 1)
        fig, ax = plt.subplots(figsize=(12, 6.2), dpi=110)
        fig.patch.set_facecolor("#ffffff"); ax.set_facecolor("#ffffff")
        for x, i in enumerate(idx):
            o, h, l, c = M.o[i], M.h[i], M.l[i], M.c[i]
            up = c >= o
            col = "#2a9d8f" if up else "#d1495b"
            if M.climax[i]:
                col = "#0b6e4f" if up else "#8f1d2c"
            ax.vlines(x, l, h, color="#6b6b6b", lw=0.8)
            ax.add_patch(plt.Rectangle((x - 0.32, min(o, c)), 0.64, max(abs(c - o), 0.25), color=col, ec=col))
        X = lambda i: int(i - a)
        ext_px = M.l[t["ext_i"]] if t["dir"] == 1 else M.h[t["ext_i"]]
        want = "low" if t["dir"] == 1 else "high"
        drawn = {}
        for side, px, ki, nm, cls in M.levels(k):
            if nm not in t["swept"] or side != want or ki >= t["ext_i"]:
                continue
            if (px > ext_px) if t["dir"] == 1 else (px < ext_px):     # the extreme traded through it
                if nm not in drawn or abs(px - ext_px) < abs(drawn[nm] - ext_px):
                    drawn[nm] = px
        by_px = {}
        for nm, px in drawn.items():
            by_px.setdefault(round(px, 2), []).append(nm)
        for px, nms in by_px.items():
            ax.axhline(px, color="#7a5195", lw=1, ls=":")
            ax.text(0.5, px, " swept " + " / ".join(sorted(nms)), color="#4a2f5f", fontsize=8, va="bottom")
        e0 = X(t["entry_i"]); e1 = X(t["exit_i"])
        for px, lab, col in ((t["entry_px"], "entry", "#1f3b73"), (t["stop_px"], "stop (beyond protected low/high)", "#b23a48"),
                             (t["target_px"], "target (PDH/PDL/PWH/PWL/PMH/PML)", "#2d6a4f")):
            ax.hlines(px, e0, e1, color=col, lw=2)
            ax.text(e1 + 0.3, px, f" {lab} {px:,.2f}", color=col, fontsize=8, va="center")
        ax.axvline(X(t["sweep_i"]), color="#999999", lw=0.8, ls="--")
        ax.text(X(t["sweep_i"]), ax.get_ylim()[1], "sweep", fontsize=8, color="#555555", ha="center", va="bottom")
        ax.scatter([X(t["ext_i"])], [M.l[t["ext_i"]] if t["dir"] == 1 else M.h[t["ext_i"]]], s=60, marker="o", facecolor="none",
                   edgecolor="#b23a48", lw=1.6, zorder=5)
        ax.scatter([X(t["ref_i"])], [M.h[t["ref_i"]] if t["dir"] == 1 else M.l[t["ref_i"]]], s=60, marker="s", facecolor="none",
                   edgecolor="#1f3b73", lw=1.6, zorder=5)
        ax.hlines(M.h[t["ref_i"]] if t["dir"] == 1 else M.l[t["ref_i"]], X(t["ref_i"]), X(t["i"]), color="#1f3b73", lw=1, ls="--")
        ax.text(X(t["i"]), M.h[t["ref_i"]] if t["dir"] == 1 else M.l[t["ref_i"]], " structure shift", fontsize=8, color="#1f3b73")
        ticks = list(range(0, len(idx), 12))
        ax.set_xticks(ticks)
        ax.set_xticklabels([dt.datetime.fromtimestamp(int(M.t[idx[q]]), ET).strftime("%H:%M") for q in ticks], fontsize=8)
        ax.grid(axis="y", color="#eeeeee", lw=0.6); ax.set_axisbelow(True)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        side = "LONG" if t["dir"] == 1 else "SHORT"
        ax.set_title(f"LIT {side} {t['day']} - {t['exit']}  {t['r']:+.2f}R  ${t['pnl']:+,.0f}  ({t['qty']} MNQ, stop {t['risk_pts']:.1f} pts, "
                     f"inducements taken {t['ind_n']})", fontsize=10, loc="left")
        ax.text(0.0, -0.09, "circle = protected low/high (stop goes beyond it) · square = the swing that broke · darker candles = PVSRA "
                "climax vector · times ET · 5m CME NQ1!", transform=ax.transAxes, fontsize=7.5, color="#555555")
        fn = f"{t['day']}_{side.lower()}_{t['exit'].lower()}.png"
        fig.tight_layout(); fig.savefig(os.path.join(out, fn)); plt.close(fig)
        names.append(fn)
    print("charts:", names)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "grid"
    if cmd == "grid":
        grid(sys.argv[2] if len(sys.argv) > 2 else "day")
    elif cmd == "save":
        save_runs()
    elif cmd == "charts":
        charts()
    elif cmd == "critic":
        critic()
    elif cmd == "combos":
        combos(sys.argv[2] if len(sys.argv) > 2 else "day")
    elif cmd == "edges":
        res = json.load(open(OUT.replace(".json", f"_{sys.argv[2] if len(sys.argv) > 2 else 'day'}.json")))
        for r in edge_table(res):
            print("%-26s 26: n=%4s PF=%5s net=%7s | 21-25: n=%4s PF=%5s net=%7s %s" % (*r[:7], "BOTH" if r[7] else ""))
