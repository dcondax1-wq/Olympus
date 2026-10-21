"""Parameter robustness of the locked strategy (study "sens", 2026-10-17): does the lock sit on a plateau or on a peak?

  python tools/research_sens.py            # everything: neighbour runs (sens_*), rolling windows, years, joint grid
  python tools/research_sens.py quick      # tables only, saves nothing

The lock (live_model.json, STRATEGY.md): cold-streak filter lookback 15 / threshold 0R / quarter size, half size on late
entries, $800 up to a 20-pt stop (risk_ref_stop 20), breakeven at +3R on trending days. Every neighbour is computed on the
cached exact live-loop replay (tools/runlib.replay) and is exact:
  * cold_size, lookback, threshold, late_mult: runlib.size with a modified filter / sizing dict (P&L is linear in micros)
  * be_at_r_trending: exits re-simulated bar by bar with tools/research_trade.sim_exit (reproduces the replay 768/768);
    3.5 is also confirmed by a full engine replay (run sens_betrend350_replay)
  * risk_ref_stop 15/25/30/40/off: the cached engine replays of those settings, exits re-simulated with the lock's
    breakeven rule, then the lock's sizing
  * risk_usd 700/900: tools/research_risk post-hoc re-sizing from the engine's own rule (a setup under 1 micro is skipped)
Rolling 6-month windows, the longest flat stretch and the year table compare the lock (run baseline) with the morning
rules (run live_2026-10-17am). Output: runs research/runs/sens_*.json, research/archive/engine-2026-10-17/sensitivity.json, and the tables for
research/writeups/parameter-robustness.md (printed and written to the scratch folder).
No look-ahead anywhere: every rule uses the setup fields and trades finished before entry only.
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tools import runlib as rl  # noqa: E402

SCRATCH = os.environ.get("SENS_SCRATCH") or os.path.join(
    "/tmp/claude-0/-home-user-nq-liquidity-engine/1c5df1a3-c52b-5e3b-a05e-7ae8d672b70d/scratchpad/sprint/sens")
LAB_JSON = os.path.join(ROOT, "research", "archive", "engine-2026-10-17", "sensitivity.json")   # old engine (LIT: research/lab/sensitivity.json, tools/lit_sensitivity.py)
WRITEUP = "research/writeups/parameter-robustness.md"
LOCK_EQF = dict(rl.LIVE_EQF)                         # lookback 15, min_sum_r 0, half mode, cold_size 0.25
LOCK_SZ = {**(rl.LIVE_SIZING or {}), "press": None}  # late_mult 0.5
MORNING_EQF = {**LOCK_EQF, "cold_size": 0.5}
MORNING_SZ = {"late_mult": None, "press": None}
NOISE = {"2026": 250, "2021-25": 500}                # $ differences smaller than this are "the same"


def eqf(lookback=15, cold_size=0.25, thr=0.0):
    return {"lookback": int(lookback), "min_sum_r": float(thr), "cold_mode": "half", "cold_size": float(cold_size)}


def sz(late=0.5):
    return {"late_mult": late, "press": None}


# ------------------------------------------------------------------------------------------------ fast stats
def quick(T, sessions):
    """n, net, pf, dd for the three spans without the eval columns (for the big joint grid)."""
    days = rl.days_of(T, sessions)
    out = {}
    for name, a, z in rl.SPANS:
        X = [t for t in T if a <= t["day"] <= z]
        p = np.array([t["pnl"] for t in X]) if X else np.array([0.0])
        gl = -p[p < 0].sum()
        cum = peak = dd = 0.0
        for d in days:
            if a <= d["date"] <= z:
                cum += d["pnl"]; peak = max(peak, cum); dd = min(dd, cum - peak)
        out[name] = {"n": len(X), "net": round(float(p.sum())), "pf": round(float(p[p > 0].sum() / gl), 2) if gl else None,
                     "dd": round(dd)}
    return out


def head(S):
    o = {}
    for k in ("2026", "2021-25", "all"):
        s = S["spans"][k]
        o[k] = {c: s.get(c) for c in ("n", "tpw", "wk2", "pf", "net", "per_month", "dd", "p10", "f10", "p20", "f20", "b2b")}
    return o


def rel(S, B):
    """Plain-words verdict of a neighbour against the lock."""
    a, A = S["spans"]["2026"], B["spans"]["2026"]
    b, Bb = S["spans"]["2021-25"], B["spans"]["2021-25"]
    d26, d5 = a["net"] - A["net"], b["net"] - Bb["net"]
    w26 = "better" if d26 > NOISE["2026"] else "worse" if d26 < -NOISE["2026"] else "the same"
    w5 = "better" if d5 > NOISE["2021-25"] else "worse" if d5 < -NOISE["2021-25"] else "the same"
    both_up = d26 > 0 and d5 > 0 and (a["pf"] or 0) >= (A["pf"] or 0) and (b["pf"] or 0) >= (Bb["pf"] or 0)
    ok_freq = 2.0 <= (a["tpw"] or 0) <= 4.0 and 2.0 <= (b["tpw"] or 0) <= 4.0
    if both_up and ok_freq and d5 >= 1000 and d26 >= 0:
        st = "adopt-candidate"
    elif both_up and ok_freq:
        st = "promising"
    elif w26 == "worse" or w5 == "worse":
        st = "rejected"
    else:
        st = "info"
    txt = (f"vs the lock: 2026 {w26} ({d26:+,.0f}$, PF {a['pf']} vs {A['pf']}), 2021-25 {w5} ({d5:+,.0f}$, PF {b['pf']} vs {Bb['pf']}); "
           f"max DD {a['dd']:,}$ / {b['dd']:,}$ (lock {A['dd']:,}$ / {Bb['dd']:,}$); evals passed/failed within 1 month "
           f"{a['p20']}%/{a['f20']}% and {b['p20']}%/{b['f20']}% (lock {A['p20']}%/{A['f20']}%, {Bb['p20']}%/{Bb['f20']}%); "
           f"{a['tpw']} / {b['tpw']} trades a week.")
    return st, txt


def _save(id, title, family, question, T, S, B, params=None, sizing=None, note="", status=None, verdict=None):
    st, txt = rel(S, B)
    rl.save(id, title, family, question, params=params or {}, sizing=sizing or {}, trades=T, scored=S, status=status or st,
            verdict=verdict or txt, notes=note, writeup=WRITEUP, tags=["sens", "robustness"])
    print(f"  saved {id:24s} {status or st:16s} 2026 {S['spans']['2026']['net']:+7,} PF {S['spans']['2026']['pf']}  | "
          f"2021-25 {S['spans']['2021-25']['net']:+7,} PF {S['spans']['2021-25']['pf']}", flush=True)
    return st, txt


# ------------------------------------------------------------------------------------------------ neighbours
def cold_grid(raw, lookbacks=(10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20), sizes=(0.15, 0.2, 0.25, 0.3, 0.35, 0.5)):
    cells = {}
    for lb in lookbacks:
        for cs in sizes:
            T = rl.size(raw, eqf=eqf(lb, cs), sizing=LOCK_SZ)
            S = rl.score(T, raw)
            cells[(lb, cs)] = (T, S)
    return cells


def thr_row(raw, thrs=(-3.0, -2.0, -1.0, 0.0, 1.0, 2.0, 3.0)):
    return {th: (lambda T: (T, rl.score(T, raw)))(rl.size(raw, eqf=eqf(15, 0.25, th), sizing=LOCK_SZ)) for th in thrs}


def late_row(raw, mults=(0.25, 0.35, 0.5, 0.65, 0.75, 1.0)):
    return {m: (lambda T: (T, rl.score(T, raw)))(rl.size(raw, eqf=LOCK_EQF, sizing=sz(m))) for m in mults}


def betrend_row(raw, values=(0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 99)):
    """be_at_r_trending neighbours: exits re-simulated on the lock's entries (0 = breakeven at +1R on every day, the morning
    rule; 99 = never move to breakeven on trending days)."""
    from tools import research_trade as rt
    out = {}
    for v in values:
        sim = {"be_at_r_trending": v}
        R = {**raw, "trades": [rt.sim_exit(t, sim) for t in raw["trades"]]}
        T = rl.size(R, eqf=LOCK_EQF, sizing=LOCK_SZ)
        out[v] = (T, rl.score(T, R), R)
    return out


def cached_replay(extra):
    """A cached engine replay of the morning params + extra (None when it was never run)."""
    import hashlib
    morning = {k: v for k, v in rl.LIVE_PARAMS.items() if k not in ("be_at_r_trending", "memory_seed")}
    for params in ({**morning, **extra}, {**rl.LIVE_PARAMS, **extra}):
        key = hashlib.sha1((json.dumps(params, sort_keys=True) + rl._data_key()).encode()).hexdigest()[:16]
        p = os.path.join(rl.CACHE, key + ".json")
        if os.path.exists(p):
            return json.load(open(p, encoding="utf-8"))
    return None


def refstop_row(values=(15.0, 20.0, 25.0, 30.0, 40.0, 0.0)):
    """risk_ref_stop neighbours: the cached engine replays of each setting, exits re-simulated with the lock's breakeven rule
    (be_at_r_trending 3), then the lock's cold / late sizing."""
    from tools import research_trade as rt
    out = {}
    for v in values:
        raw_v = rl.replay(quiet=True) if v == 20.0 else cached_replay({"risk_ref_stop": v})
        if raw_v is None:
            continue
        if v != 20.0 and raw_v["params"].get("be_at_r_trending") != 3.0:
            raw_v = {**raw_v, "trades": [rt.sim_exit(t, {"be_at_r_trending": 3.0}) for t in raw_v["trades"]]}
        T = rl.size(raw_v, eqf=LOCK_EQF, sizing=LOCK_SZ)
        out[v] = (T, rl.score(T, raw_v), raw_v)
    return out


def riskusd_row(raw, values=(600.0, 700.0, 800.0, 900.0, 1000.0)):
    """risk_usd neighbours: tools/research_risk post-hoc re-sizing from the engine's own rule under the lock's cold / late
    sizing (no soft daily-limit cut, as runlib.size)."""
    from tools import research_risk as rr
    T0 = rr.prep(raw)
    out = {}
    for v in values:
        pol = {"risk_usd": v, "ref": 20.0, "cold": {"lookback": 15, "thr": 0.0, "size": 0.25}, "late_mult": 0.5}
        T = rr.run_account(T0, pol, dll=False)
        out[v] = (T, rl.score(T, raw))
    return out


def regime_row(raw, thrs=(0.35, 0.40, 0.45, 0.50, 0.55)):
    """Trending-market threshold (regime_er10_max, lock 0.45: 10-day efficiency above it = trending day = half size and
    breakeven at +3R). Exact post-hoc: every trade stores the day's efficiency (f.rg_er10, reproduces the engine's label
    768/768), so the day is relabelled, the exit re-simulated with the lock's breakeven rule, and the micros re-done from
    the engine's own rule (trending half) with the lock's cold / late sizing. Entries do not depend on the regime
    (regime_mode half)."""
    from tools import research_risk as rr
    from tools import research_trade as rt
    out = {}
    for thr in thrs:
        sim = []
        for t in raw["trades"]:
            lab = "trending" if float((t.get("f") or {}).get("rg_er10") or 0.0) > thr else "rotational"
            s = rt.sim_exit({**t, "regime": lab}, {"be_at_r_trending": 3.0})
            s["regime"], s["_new_regime"] = t["regime"], lab           # prep must see the label the engine sized with
            sim.append(s)
        T0 = rr.prep({**raw, "trades": sim})
        for t in T0:
            t["regime"] = t["_new_regime"]
        pol = {"risk_usd": 800.0, "ref": 20.0, "cold": {"lookback": 15, "thr": 0.0, "size": 0.25}, "late_mult": 0.5, "pre_key": f"regime{thr}"}
        T = rr.run_account(T0, pol, dll=False)
        for t in T:
            t.pop("_new_regime", None)
        n_tr = sum(1 for t in T0 if t["regime"] == "trending")
        out[thr] = (T, rl.score(T, raw), n_tr)
    return out


# ------------------------------------------------------------------------------------------------ windows, years
def _run_trades(id):
    r = rl.load(id)
    T = [dict(zip(r["trade_cols"], a)) for a in r["trades"]]
    D = [dict(zip(r["day_cols"], a)) for a in r["days"]]
    return r, T, D


def _add_months(ym, k):
    y, m = int(ym[:4]), int(ym[5:7]) - 1 + k
    return f"{y + m // 12:04d}-{m % 12 + 1:02d}"


def rolling(T, D, months=6, step=1):
    """Calendar windows of `months` months, stepping `step` month(s): n, net, pf, max dd, win %."""
    first, last = D[0]["date"][:7], D[-1]["date"][:7]
    rows = []
    start = first
    while _add_months(start, months - 1) <= last:
        end = _add_months(start, months)                       # exclusive
        X = [t for t in T if start <= t["day"][:7] < end]
        p = np.array([t["pnl"] for t in X]) if X else np.array([0.0])
        gl = -p[p < 0].sum()
        cum = peak = dd = 0.0
        for d in D:
            if start <= d["date"][:7] < end:
                cum += d["pnl"]; peak = max(peak, cum); dd = min(dd, cum - peak)
        rows.append({"start": start, "end": _add_months(start, months - 1), "n": len(X), "net": round(float(p.sum())),
                     "pf": round(float(p[p > 0].sum() / gl), 2) if gl else None, "dd": round(dd),
                     "win": round(100 * float((p > 0).mean()), 1) if X else None})
        start = _add_months(start, step)
    return rows


def flat_stretches(D, top=3):
    """Stretches without a new closed-equity high (calendar days, sessions, depth), longest first."""
    cum = peak = 0.0
    peak_i = 0
    out = []
    for i, d in enumerate(D):
        cum += d["pnl"]
        if cum > peak + 1e-9:
            if i - peak_i > 1:
                out.append((peak_i, i))
            peak, peak_i = cum, i
    out.append((peak_i, len(D) - 1))                             # the open stretch at the end (if any)
    res = []
    for a, z in out:
        if z <= a:
            continue
        da, dz = dt.date.fromisoformat(D[a]["date"]), dt.date.fromisoformat(D[z]["date"])
        seg = D[a + 1:z + 1]
        c = low = 0.0
        for d in seg:
            c += d["pnl"]; low = min(low, c)
        res.append({"from": D[a]["date"], "to": D[z]["date"], "days": (dz - da).days, "sessions": z - a, "weeks": round((dz - da).days / 7, 1),
                    "depth": round(low), "open": z == len(D) - 1})
    res.sort(key=lambda x: -x["days"])
    return res[:top]


def neg_month_streak(T):
    by = collections.defaultdict(float)
    for t in T:
        by[t["day"][:7]] += t["pnl"]
    months = sorted(by)
    best, cur, cur_from, best_rng = 0, 0, None, None
    for m in months:
        if by[m] < 0:
            cur += 1; cur_from = cur_from or m
            if cur > best:
                best, best_rng = cur, (cur_from, m)
        else:
            cur, cur_from = 0, None
    return best, best_rng


def years_table(T, D):
    out = {}
    for y in sorted({d["date"][:4] for d in D}):
        X = [t for t in T if t["day"][:4] == y]
        p = np.array([t["pnl"] for t in X]) if X else np.array([0.0])
        gl = -p[p < 0].sum()
        cum = peak = dd = 0.0
        for d in D:
            if d["date"][:4] == y:
                cum += d["pnl"]; peak = max(peak, cum); dd = min(dd, cum - peak)
        wk = len({dt.date.fromisoformat(d["date"]).isocalendar()[:2] for d in D if d["date"][:4] == y})
        out[y] = {"n": len(X), "tpw": round(len(X) / max(wk, 1), 2), "net": round(float(p.sum())),
                  "pf": round(float(p[p > 0].sum() / gl), 2) if gl else None, "win": round(100 * float((p > 0).mean()), 1) if X else None,
                  "dd": round(dd)}
    return out


# ------------------------------------------------------------------------------------------------ joint grid
def joint_grid(raw, lookbacks=(12, 13, 14, 15, 16, 17, 18), sizes=(0.15, 0.2, 0.25, 0.3, 0.35), lates=(0.35, 0.5, 0.65)):
    rows = []
    for lb in lookbacks:
        for cs in sizes:
            for lm in lates:
                T = rl.size(raw, eqf=eqf(lb, cs), sizing=sz(lm))
                q = quick(T, raw["sessions"])
                rows.append({"lookback": lb, "cold_size": cs, "late_mult": lm, "net26": q["2026"]["net"], "pf26": q["2026"]["pf"],
                             "net5": q["2021-25"]["net"], "pf5": q["2021-25"]["pf"], "dd5": q["2021-25"]["dd"], "dd26": q["2026"]["dd"]})
    return rows


# ------------------------------------------------------------------------------------------------ tables
def money(v):
    return f"{'+' if v >= 0 else '-'}${abs(v):,.0f}"


def md(rows, head):
    return "\n".join(["| " + " | ".join(head) + " |", "|" + "|".join("---:" if i else "---" for i in range(len(head))) + "|"] +
                     ["| " + " | ".join(str(c) for c in r) + " |" for r in rows])


def cell(S, k):
    s = S["spans"][k]
    return f"{money(s['net'])} ({s['pf']})"


def main(save=True):
    t0 = time.time()
    os.makedirs(SCRATCH, exist_ok=True)
    raw = rl.replay(quiet=True)
    B = rl.load("baseline")
    M = rl.load("live_2026-10-17am")
    T_lock = rl.size(raw, eqf=LOCK_EQF, sizing=LOCK_SZ)
    S_lock = rl.score(T_lock, raw)
    assert S_lock["spans"]["2026"]["net"] == B["spans"]["2026"]["net"] and S_lock["spans"]["2021-25"]["net"] == B["spans"]["2021-25"]["net"], "lock mismatch"
    lab = {"built": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "study": "sens", "writeup": WRITEUP,
           "lock": {"equity_filter": LOCK_EQF, "sizing": LOCK_SZ, "params": rl.LIVE_PARAMS, "spans": head(S_lock)},
           "morning": {"spans": head(rl.score([dict(zip(M["trade_cols"], a)) for a in M["trades"]], [d[0] for d in M["days"]]))}}
    out_md = []

    # ---- A. cold-streak grid
    print("A. cold-streak grid", flush=True)
    cells = cold_grid(raw)
    lbs = sorted({k[0] for k in cells}); css = sorted({k[1] for k in cells})
    lab["cold_grid"] = {"lookbacks": lbs, "cold_sizes": css,
                        "cells": [{"lookback": lb, "cold_size": cs, **{f"{p}_{c}": cells[(lb, cs)][1]["spans"][k][c] for k, p in (("2026", "y26"), ("2021-25", "y5"))
                                                                        for c in ("net", "pf", "dd", "p20", "f20")}} for lb in lbs for cs in css]}
    T_off = rl.size(raw, eqf=None, sizing=LOCK_SZ)
    S_off = rl.score(T_off, raw)
    lab["cold_off"] = head(S_off)
    cold_days = {}
    for lb in lbs:
        T = cells[(lb, 0.25)][0]
        cold_days[lb] = {k: sum(1 for t in T if t["half"] and a <= t["day"] <= z) for k, a, z in rl.SPANS if k != "all"}
    lab["cold_trades_by_lookback"] = cold_days
    rows = [[lb] + [cell(cells[(lb, cs)][1], "2021-25") for cs in css] + [cold_days[lb]["2021-25"]] for lb in lbs]
    rows.append(["filter off"] + [cell(S_off, "2021-25")] * len(css) + [0])
    out_md.append("### Cold-streak filter: 2021-25 net (PF) by lookback (rows) and cold size (columns)\n\n" + md(rows, ["lookback"] + [f"x{c:g}" for c in css] + ["cold trades (x0.25)"]))
    rows = [[lb] + [cell(cells[(lb, cs)][1], "2026") for cs in css] + [cold_days[lb]["2026"]] for lb in lbs]
    rows.append(["filter off"] + [cell(S_off, "2026")] * len(css) + [0])
    out_md.append("### Cold-streak filter: 2026 net (PF)\n\n" + md(rows, ["lookback"] + [f"x{c:g}" for c in css] + ["cold trades (x0.25)"]))
    if save:
        for cs in (0.15, 0.2, 0.3, 0.35):
            T, S = cells[(15, cs)]
            _save(f"sens_cold{int(round(cs * 100)):03d}", f"Neighbour: cold-streak size x{cs:g} (lock x0.25)", "risk",
                  f"If the cold-streak size were x{cs:g} instead of x0.25, with everything else as locked, what changes?", T, S, B,
                  sizing={"equity_filter": eqf(15, cs), "late_mult": 0.5},
                  note="Robustness neighbour of the lock (study sens). Exact: runlib.size with a modified filter dict on the cached live-loop replay.")
        for lb in (12, 13, 17, 18):
            T, S = cells[(lb, 0.25)]
            _save(f"sens_lb{lb:02d}", f"Neighbour: cold-streak lookback {lb} signals (lock 15)", "risk",
                  f"If the cold-streak filter looked at the last {lb} signals instead of 15, with everything else as locked, what changes?", T, S, B,
                  sizing={"equity_filter": eqf(lb, 0.25), "late_mult": 0.5},
                  note="Robustness neighbour of the lock (study sens). Exact: runlib.size with a modified filter dict on the cached live-loop replay.")

    # ---- A2. threshold
    thr = thr_row(raw)
    lab["threshold"] = [{"thr": th, "y26": head(S)["2026"], "y5": head(S)["2021-25"]} for th, (T, S) in thr.items()]
    out_md.append("### Cold-streak threshold (lock 0R; lookback 15, x0.25)\n\n" + md(
        [[f"{th:+g}R", cell(S, "2026"), cell(S, "2021-25"), f"{S['spans']['2021-25']['dd']:,}", f"{S['spans']['2021-25']['p20']}% / {S['spans']['2021-25']['f20']}%"]
         for th, (T, S) in thr.items()], ["threshold", "2026 net (PF)", "2021-25 net (PF)", "2021-25 max DD", "2021-25 evals 1 month pass / fail"]))

    # ---- B. late
    print("B. late-entry size", flush=True)
    late = late_row(raw)
    lab["late"] = [{"late_mult": m, "y26": head(S)["2026"], "y5": head(S)["2021-25"]} for m, (T, S) in late.items()]
    out_md.append("### Late-entry size (lock x0.5)\n\n" + md(
        [[f"x{m:g}", cell(S, "2026"), cell(S, "2021-25"), f"{S['spans']['2026']['dd']:,} / {S['spans']['2021-25']['dd']:,}",
          f"{S['spans']['2021-25']['p20']}% / {S['spans']['2021-25']['f20']}%"] for m, (T, S) in late.items()],
        ["late size", "2026 net (PF)", "2021-25 net (PF)", "max DD 2026 / 2021-25", "2021-25 evals 1 month pass / fail"]))
    if save:
        for m in (0.35, 0.65):
            T, S = late[m]
            _save(f"sens_late{int(round(m * 100)):03d}", f"Neighbour: late-entry size x{m:g} (lock x0.5)", "risk",
                  f"If late entries (15m already turned) were sized x{m:g} instead of x0.5, what changes?", T, S, B,
                  sizing={"equity_filter": LOCK_EQF, "late_mult": m},
                  note="Robustness neighbour of the lock (study sens). Exact: runlib.size with a modified sizing dict on the cached live-loop replay.")

    # ---- C. breakeven on trending days
    print("C. breakeven on trending days", flush=True)
    from tools import research_trade as rt
    n = len(raw["trades"])
    ok = sum(1 for t in raw["trades"] if (lambda s: s["exit"] == t["exit"] and s["exit_t"] == t["exit_t"] and abs(s["pnl"] - t["pnl"]) < 0.02)(
        rt.sim_exit(t, {"be_at_r_trending": 3.0})))
    print(f"  exit simulator reproduces the lock's replay {ok}/{n}", flush=True)
    bt = betrend_row(raw)
    lab["betrend"] = [{"be_at_r_trending": v, "y26": head(S)["2026"], "y5": head(S)["2021-25"]} for v, (T, S, R) in bt.items()]
    rows = []
    for v, (T, S, R) in bt.items():
        lab_v = "+1R (morning rule)" if v == 0 else "never" if v == 99 else f"+{v:g}R"
        rows.append([lab_v + (" (lock)" if v == 3.0 else ""), cell(S, "2026"), cell(S, "2021-25"), f"{S['spans']['2021-25']['dd']:,}",
                     f"{S['spans']['2026']['p20']}% / {S['spans']['2026']['f20']}%", f"{S['spans']['2021-25']['p20']}% / {S['spans']['2021-25']['f20']}%"])
    out_md.append("### Breakeven on trending days (lock +3R), lock sizing\n\n" + md(
        rows, ["breakeven at", "2026 net (PF)", "2021-25 net (PF)", "2021-25 max DD", "2026 evals 1 month", "2021-25 evals 1 month"]))
    if save:
        for v in (2.5, 3.5):
            T, S, R = bt[v]
            _save(f"sens_betrend{int(v * 100):03d}", f"Neighbour: breakeven at +{v:g}R on trending days (lock +3R), lock sizing", "management",
                  f"If the trending-day breakeven were +{v:g}R instead of +3R, with the lock's sizing, what changes?", T, S, B,
                  params={"be_at_r_trending": v}, sizing={"equity_filter": LOCK_EQF, "late_mult": 0.5},
                  note="Robustness neighbour of the lock (study sens). Exits re-simulated with tools/research_trade.sim_exit (reproduces "
                       f"the lock's replay {ok}/{n}) on the lock's entries, then the lock's sizing. The saved runs mgt_betrend250/300 are the "
                       "same change on the MORNING sizing (half size when cold, no late-entry rule).")
    # the exact replay of 3.5, if it has been run (started separately: rl.replay({'be_at_r_trending': 3.5}))
    R35 = cached_replay({"be_at_r_trending": 3.5}) if False else None
    import hashlib
    key = hashlib.sha1((json.dumps({**rl.LIVE_PARAMS, "be_at_r_trending": 3.5}, sort_keys=True) + rl._data_key()).encode()).hexdigest()[:16]
    p35 = os.path.join(rl.CACHE, key + ".json")
    if os.path.exists(p35):
        R35 = json.load(open(p35, encoding="utf-8"))
        T35 = rl.size(R35, eqf=LOCK_EQF, sizing=LOCK_SZ)
        S35 = rl.score(T35, R35)
        sim = {t["entry_t"]: t for t in bt[3.5][2]["trades"]}
        same = sum(1 for t in R35["trades"] if t["entry_t"] in sim and sim[t["entry_t"]]["exit_t"] == t["exit_t"] and abs(sim[t["entry_t"]]["pnl"] - t["pnl"]) < 0.02)
        print(f"  replay 3.5: {len(R35['trades'])} trades, simulator matched {same}", flush=True)
        lab["betrend_replay_350"] = {"trades": len(R35["trades"]), "sim_matched": same, "y26": head(S35)["2026"], "y5": head(S35)["2021-25"]}
        if save:
            _save("sens_betrend350_replay", "Neighbour: breakeven at +3.5R on trending days (exact replay), lock sizing", "management",
                  "Does a full engine replay confirm the simulated +3.5R neighbour?", T35, S35, B, params={"be_at_r_trending": 3.5},
                  sizing={"equity_filter": LOCK_EQF, "late_mult": 0.5},
                  note=f"Exact live-loop engine replay with be_at_r_trending 3.5; the exit simulator matched {same} of {len(R35['trades'])} trades.")
    else:
        print("  replay 3.5 not in the cache yet", flush=True)

    # ---- D. risk_ref_stop
    print("D. wide-stop reference", flush=True)
    rs = refstop_row()
    lab["ref_stop"] = [{"risk_ref_stop": v, "n_raw": len(R["trades"]), "y26": head(S)["2026"], "y5": head(S)["2021-25"]} for v, (T, S, R) in rs.items()]
    rows = []
    for v, (T, S, R) in rs.items():
        rows.append([("off ($800 on any stop)" if v == 0 else f"{v:g} pts") + (" (lock)" if v == 20 else ""), S["spans"]["2026"]["tpw"], S["spans"]["2021-25"]["tpw"],
                     cell(S, "2026"), cell(S, "2021-25"), f"{S['spans']['2026']['dd']:,} / {S['spans']['2021-25']['dd']:,}",
                     f"{S['spans']['2021-25']['p20']}% / {S['spans']['2021-25']['f20']}%"])
    out_md.append("### Full risk up to a stop of ... (risk_ref_stop, lock 20 pts), lock sizing and breakeven rule\n\n" + md(
        rows, ["full risk up to", "2026 trades/wk", "2021-25 trades/wk", "2026 net (PF)", "2021-25 net (PF)", "max DD 2026 / 2021-25", "2021-25 evals 1 month pass / fail"]))
    if save:
        for v in (15.0, 25.0):
            if v in rs:
                T, S, R = rs[v]
                st, txt = rel(S, B)
                _save(f"sens_ref{int(v):02d}", f"Neighbour: full risk up to a {v:g}-pt stop (lock 20), lock sizing", "risk",
                      f"If $800 applied up to a {v:g}-pt stop instead of 20 (then scaled down), with the lock's sizing and breakeven rule, what changes?",
                      T, S, B, params={"risk_ref_stop": v}, sizing={"equity_filter": LOCK_EQF, "late_mult": 0.5},
                      status="info" if st in ("adopt-candidate", "promising") else st,
                      verdict=txt + (" More risk on wide stops is a scale change (more net, lower PF, bigger drawdown, more eval fails), not a new edge."
                                     if v > 20 else ""),
                      note="Robustness neighbour of the lock (study sens): the cached exact engine replay of this setting, exits re-simulated with "
                           "the lock's trending-day breakeven (+3R), then the lock's cold / late sizing. The saved runs risk_ref15/25 are the same "
                           "setting on the MORNING rules.")

    # ---- E. risk_usd
    print("E. risk per trade", flush=True)
    ru = riskusd_row(raw)
    chk = ru[800.0][1]["spans"]
    print(f"  post-hoc re-sizing reproduces the lock: 2026 {chk['2026']['net']:+,} 2021-25 {chk['2021-25']['net']:+,}", flush=True)
    lab["risk_usd"] = [{"risk_usd": v, "y26": head(S)["2026"], "y5": head(S)["2021-25"]} for v, (T, S) in ru.items()]
    rows = []
    for v, (T, S) in ru.items():
        rows.append([f"${v:,.0f}" + (" (lock)" if v == 800 else ""), S["spans"]["2026"]["tpw"], S["spans"]["2021-25"]["tpw"], cell(S, "2026"), cell(S, "2021-25"),
                     f"{S['spans']['2026']['dd']:,} / {S['spans']['2021-25']['dd']:,}", f"{S['spans']['2021-25']['p20']}% / {S['spans']['2021-25']['f20']}%"])
    out_md.append("### Risk per trade (risk_usd, lock $800), lock sizing\n\n" + md(
        rows, ["risk", "2026 trades/wk", "2021-25 trades/wk", "2026 net (PF)", "2021-25 net (PF)", "max DD 2026 / 2021-25", "2021-25 evals 1 month pass / fail"]))
    if save:
        for v in (700.0, 900.0):
            T, S = ru[v]
            st, txt = rel(S, B)
            _save(f"sens_usd{int(v)}", f"Neighbour: ${v:,.0f} risk up to a 20-pt stop (lock $800), lock sizing", "risk",
                  f"If the risk were ${v:,.0f} instead of $800 (wide stops scaled in proportion), with the lock's sizing, what changes?", T, S, B,
                  params={"risk_usd": v}, sizing={"equity_filter": LOCK_EQF, "late_mult": 0.5}, status="info",
                  verdict=txt + " A size change, not a new edge: the same trades at a different scale, so PF only moves through micro rounding "
                                "while net, drawdown and eval fails all scale together (see research/writeups/risk-summary.md on more risk).",
                  note="Robustness neighbour of the lock (study sens): tools/research_risk post-hoc re-sizing from the engine's own rule (exact; a setup "
                       "under 1 micro is skipped), lock's cold / late sizing. The saved runs risk_usd700/900 are the same change on the MORNING rules.")

    # ---- E2. trending-market threshold
    print("E2. trending-market threshold", flush=True)
    rg = regime_row(raw)
    chk = rg[0.45][1]["spans"]
    print(f"  relabel at 0.45 reproduces the lock: 2026 {chk['2026']['net']:+,} 2021-25 {chk['2021-25']['net']:+,}", flush=True)
    lab["regime"] = [{"regime_er10_max": th, "trending_trades": n_tr, "y26": head(S)["2026"], "y5": head(S)["2021-25"]} for th, (T, S, n_tr) in rg.items()]
    rows = []
    for th, (T, S, n_tr) in rg.items():
        rows.append([f"{th:g}" + (" (lock)" if th == 0.45 else ""), n_tr, cell(S, "2026"), cell(S, "2021-25"),
                     f"{S['spans']['2026']['dd']:,} / {S['spans']['2021-25']['dd']:,}", f"{S['spans']['2021-25']['p20']}% / {S['spans']['2021-25']['f20']}%"])
    out_md.append("### Trending-market threshold (10-day efficiency, lock 0.45): half size + breakeven at +3R on those days\n\n" + md(
        rows, ["threshold", "trending trades (of 768)", "2026 net (PF)", "2021-25 net (PF)", "max DD 2026 / 2021-25", "2021-25 evals 1 month pass / fail"]))
    if save:
        REGIME_050 = (" Better in both periods on net and PF, but not a robust improvement: fewer 'trending' days means more full-size "
                      "trades, so the drawdown and the 1-month eval fails rise with the net, and the next step (0.55) gives back all of "
                      "the 2021-25 gain and more (+$14.4k). A noisy parameter, not a new edge.")
        for th in (0.40, 0.50):
            T, S, n_tr = rg[th]
            st, txt = rel(S, B)
            _save(f"sens_regime{int(round(th * 100)):03d}", f"Neighbour: trending day = 10-day efficiency above {th:g} (lock 0.45)", "filters",
                  f"If 'trending day' (half size, breakeven at +3R) started at a 10-day efficiency of {th:g} instead of 0.45, what changes?", T, S, B,
                  params={"regime_er10_max": th}, sizing={"equity_filter": LOCK_EQF, "late_mult": 0.5},
                  status="promising" if st == "adopt-candidate" else st, verdict=txt + (REGIME_050 if th == 0.5 else ""),
                  note=f"Robustness neighbour of the lock (study sens). Exact post-hoc: days relabelled from the stored 10-day efficiency ({n_tr} "
                       "trending trades), exits re-simulated with the lock's breakeven rule, micros re-done from the engine's rule, lock's cold / late sizing.")
    key = hashlib.sha1((json.dumps({**rl.LIVE_PARAMS, "regime_er10_max": 0.5}, sort_keys=True) + rl._data_key()).encode()).hexdigest()[:16]
    p50 = os.path.join(rl.CACHE, key + ".json")
    if os.path.exists(p50):
        R50 = json.load(open(p50, encoding="utf-8"))
        T50 = rl.size(R50, eqf=LOCK_EQF, sizing=LOCK_SZ)
        S50 = rl.score(T50, R50)
        ph = {t["entry_t"]: t for t in rg[0.5][0]}
        same = sum(1 for t in T50 if t["entry_t"] in ph and ph[t["entry_t"]]["exit_t"] == t["exit_t"] and abs(ph[t["entry_t"]]["pnl"] - t["pnl"]) < 0.02)
        print(f"  replay regime 0.5: {len(R50['trades'])} trades, post-hoc matched {same} of {len(T50)}", flush=True)
        lab["regime_replay_050"] = {"trades": len(R50["trades"]), "posthoc_matched": same, "y26": head(S50)["2026"], "y5": head(S50)["2021-25"]}
        if save:
            st, txt = rel(S50, B)
            _save("sens_regime050_replay", "Neighbour: trending day = 10-day efficiency above 0.5 (exact replay)", "filters",
                  "Does a full engine replay confirm the post-hoc 0.50 neighbour?", T50, S50, B, params={"regime_er10_max": 0.5},
                  sizing={"equity_filter": LOCK_EQF, "late_mult": 0.5}, status="promising" if st == "adopt-candidate" else st,
                  verdict=txt + REGIME_050,
                  note=f"Exact live-loop engine replay with regime_er10_max 0.5; the post-hoc relabel matched {same} of {len(T50)} sized trades.")
    else:
        print("  replay regime 0.5 not in the cache yet", flush=True)

    # ---- F. rolling windows, flat stretches, years
    print("F. rolling windows and years", flush=True)
    _, TB, DB = _run_trades("baseline")
    _, TM, DM = _run_trades("live_2026-10-17am")
    win = {"lock": rolling(TB, DB), "morning": rolling(TM, DM)}
    lab["rolling_6m"] = win
    stat = {}
    for k, W in win.items():
        nets = [w["net"] for w in W]
        stat[k] = {"windows": len(W), "negative": sum(1 for v in nets if v < 0), "below_minus_2k": sum(1 for v in nets if v < -2000),
                   "worst": min(nets), "best": max(nets), "median": round(float(np.median(nets))),
                   "pf_below_1": sum(1 for w in W if (w["pf"] or 0) < 1), "worst_window": min(W, key=lambda w: w["net"]),
                   "best_window": max(W, key=lambda w: w["net"]), "flat": flat_stretches([d for d in DB] if k == "lock" else DM),
                   "neg_months": neg_month_streak(TB if k == "lock" else TM)}
    lab["rolling_stats"] = stat
    rows = []
    for a, b in zip(win["lock"], win["morning"]):
        rows.append([f"{a['start']} to {a['end']}", a["n"], money(a["net"]), a["pf"], money(b["net"]), b["pf"]])
    out_md.append("### Rolling 6-month windows (every month start): lock vs morning rules\n\n" + md(rows, ["window", "trades", "lock net", "lock PF", "morning net", "morning PF"]))
    rows = []
    for k in ("lock", "morning"):
        s = stat[k]
        rows.append([k, s["windows"], s["negative"], s["below_minus_2k"], s["pf_below_1"], money(s["worst"]) + f" ({s['worst_window']['start']})",
                     money(s["median"]), money(s["best"]) + f" ({s['best_window']['start']})",
                     f"{s['flat'][0]['weeks']} weeks ({s['flat'][0]['from']} to {s['flat'][0]['to']}, {money(s['flat'][0]['depth'])})",
                     f"{s['neg_months'][0]} ({s['neg_months'][1][0]} to {s['neg_months'][1][1]})" if s["neg_months"][1] else "0"])
    out_md.append("### Window summary\n\n" + md(rows, ["rules", "windows", "negative", "below -$2k", "PF < 1", "worst (start)", "median", "best (start)", "longest flat stretch", "longest run of losing months"]))
    yrs = {"lock": years_table(TB, DB), "morning": years_table(TM, DM)}
    lab["years"] = yrs
    rows = []
    for y in yrs["lock"]:
        a, b = yrs["lock"][y], yrs["morning"][y]
        rows.append([y, a["n"], a["tpw"], f"{a['win']}%", money(a["net"]), a["pf"], f"{a['dd']:,}", money(b["net"]), b["pf"], f"{b['dd']:,}"])
    out_md.append("### Year by year: lock vs morning rules\n\n" + md(rows, ["year", "trades", "trades/wk", "win %", "lock net", "lock PF", "lock max DD", "morning net", "morning PF", "morning max DD"]))

    # ---- G. joint grid
    print("G. joint grid", flush=True)
    J = joint_grid(raw)
    lab["joint"] = J
    n5 = np.array([r["net5"] for r in J]); n26 = np.array([r["net26"] for r in J])
    lock_j = next(r for r in J if r["lookback"] == 15 and r["cold_size"] == 0.25 and r["late_mult"] == 0.5)
    morning5, morning26 = M["spans"]["2021-25"]["net"], M["spans"]["2026"]["net"]
    js = {"combos": len(J), "y5": {"min": int(n5.min()), "p25": int(np.percentile(n5, 25)), "median": int(np.median(n5)), "p75": int(np.percentile(n5, 75)), "max": int(n5.max()),
                                  "share_above_morning": round(100 * float((n5 > morning5).mean()), 1), "share_above_10k": round(100 * float((n5 > 10000).mean()), 1),
                                  "share_negative": round(100 * float((n5 < 0).mean()), 1)},
          "y26": {"min": int(n26.min()), "median": int(np.median(n26)), "max": int(n26.max()), "share_above_morning": round(100 * float((n26 > morning26).mean()), 1)},
          "share_better_both": round(100 * float(((n5 > lock_j["net5"]) & (n26 > lock_j["net26"])).mean()), 1),
          "share_worse_both": round(100 * float(((n5 < lock_j["net5"]) & (n26 < lock_j["net26"])).mean()), 1),
          "lock_rank_y5": int((n5 > lock_j["net5"]).sum()) + 1, "lock_rank_y26": int((n26 > lock_j["net26"]).sum()) + 1}
    # by lookback: median 2021-25 net over the 15 cold/late combos
    js["by_lookback"] = {lb: {"y5_median": int(np.median([r["net5"] for r in J if r["lookback"] == lb])), "y5_min": int(min(r["net5"] for r in J if r["lookback"] == lb)),
                              "y5_max": int(max(r["net5"] for r in J if r["lookback"] == lb)), "y26_median": int(np.median([r["net26"] for r in J if r["lookback"] == lb]))}
                        for lb in sorted({r["lookback"] for r in J})}
    js["by_cold_size"] = {cs: {"y5_median": int(np.median([r["net5"] for r in J if r["cold_size"] == cs])), "y26_median": int(np.median([r["net26"] for r in J if r["cold_size"] == cs]))}
                          for cs in sorted({r["cold_size"] for r in J})}
    js["by_late"] = {lm: {"y5_median": int(np.median([r["net5"] for r in J if r["late_mult"] == lm])), "y26_median": int(np.median([r["net26"] for r in J if r["late_mult"] == lm]))}
                     for lm in sorted({r["late_mult"] for r in J})}
    lab["joint_stats"] = js
    out_md.append("### Joint grid: 105 combinations of lookback 12-18 x cold size 0.15-0.35 x late size 0.35-0.65\n\n" + md(
        [[lb, money(v["y5_min"]), money(v["y5_median"]), money(v["y5_max"]), money(v["y26_median"])] for lb, v in js["by_lookback"].items()],
        ["lookback", "2021-25 worst combo", "2021-25 median", "2021-25 best combo", "2026 median"]))
    out_md.append(md([[f"x{cs:g}", money(v["y5_median"]), money(v["y26_median"])] for cs, v in js["by_cold_size"].items()], ["cold size", "2021-25 median", "2026 median"]))
    out_md.append(md([[f"x{lm:g}", money(v["y5_median"]), money(v["y26_median"])] for lm, v in js["by_late"].items()], ["late size", "2021-25 median", "2026 median"]))

    rl._dump(lab, LAB_JSON, separators=(",", ":"))
    text = "\n\n".join(out_md)
    with open(os.path.join(SCRATCH, "tables.md"), "w", encoding="utf-8") as fh:
        fh.write(text)
    with open(os.path.join(SCRATCH, "stats.json"), "w", encoding="utf-8") as fh:
        json.dump({"rolling_stats": stat, "joint_stats": js, "years": yrs}, fh, indent=1, default=str)
    print(text)
    print(f"\ndone in {time.time() - t0:.0f}s; lab json {LAB_JSON}; tables {os.path.join(SCRATCH, 'tables.md')}")


if __name__ == "__main__":
    main(save=(sys.argv[1:2] != ["quick"]))
