"""BLITZ more tests (research/blitzmore/DESIGN.md, pre-registered before this ran). PAPER RESEARCH ONLY.
    python -X utf8 research/blitzmore/blitzmore.py   -> research/blitzmore/results.json
"""
from __future__ import annotations

import collections
import copy
import datetime as dt
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "research", "blitzv2"))
sys.path.insert(0, os.path.join(ROOT, "research", "moretrades"))
os.chdir(ROOT)
import blitzv2 as BZ  # noqa: E402
import moretrades as MT  # noqa: E402
from tools import blitz25k_lib as L, scalp_na_lib as N  # noqa: E402

TICK, PV, COMM, USD = 0.25, 2.0, 1.90, 150.0
BASE = {"hold": 30, "trail": 1.5, "tstart": 1.0, "maxday": 6, "day_stop": 3.0, "stop_x": 1.5, "tgt": None, "streak": None,
        "cm_min": 0, "cm_max": 931, "trend": False, "vix_min": None, "stopcap": None}
V = collections.OrderedDict([
    ("V0 today", {}),
    ("M1 max 3 a day", {"maxday": 3}),
    ("M2 pause after 2 losses in a row", {"streak": 2}),
    ("M3 no entry after 14:30", {"cm_max": 870}),
    ("M4 morning only (to 12:30)", {"cm_max": 750}),
    ("M5 afternoon only (from 13:00)", {"cm_min": 780}),
    ("M6 daily-trend aligned", {"trend": True}),
    ("M7 prior VIX >= 18", {"vix_min": 18.0}),
    ("M8 skip stop > 0.40% of price", {"stopcap": 0.40}),
    ("M9 tighter stop 1.0 ATR", {"stop_x": 1.0}),
    ("M10 wider stop 2.0 ATR", {"stop_x": 2.0}),
    ("M11 fixed target 2R", {"tgt": 2.0}),
    ("M12 time exit 60 min", {"hold": 60}),
])
SPANS = {"2026 H1": (1, "H1"), "2026 Jul-Nov20": (1, "H2"), "2021-25": (5, "R")}


# ------------------------------------------------------------------------------------------------ context arrays
_CTX = {}


def ctx(B):
    k = id(B)
    if k in _CTX:
        return _CTX[k]
    tf, mod, day, c = B["tf"], B["mod"], B["day"], B["c"]
    nd = int(day.max()) + 1
    rth = (mod >= 570) & (mod + tf <= 960)
    last = np.full(nd, np.nan)
    idx = np.where(rth)[0]
    last[day[idx]] = c[idx]                      # ascending: the last RTH bar of each day wins
    trend = np.zeros(nd, int)                    # +1 prior close above the mean of the last 20 prior closes, -1 below
    for d in range(nd):
        w = last[max(0, d - 20):d]
        w = w[~np.isnan(w)]
        if len(w) >= 10:
            trend[d] = 1 if w[-1] > w.mean() else -1
    vd = []
    with open(os.path.join(ROOT, "data", "VIX_1d.csv"), encoding="utf-8") as fh:
        next(fh)
        for ln in fh:
            a = ln.strip().split(",")
            vd.append((a[0], float(a[4])))
    vdates = [x[0] for x in vd]
    vix = np.full(nd, np.nan)
    ds = B["dates"]
    for d in range(nd):
        i = int(np.searchsorted(vdates, str(ds[d]), side="left")) - 1   # the last VIX close BEFORE this date
        if i >= 0:
            vix[d] = vd[i][1]
    _CTX[k] = {"trend": trend, "vix": vix}
    return _CTX[k]


def sim(B, v, placebo=None):
    v = {**BASE, **v}
    G = L.base(B, "prng>=0.8", ("rth",))
    I, D = G["sig"].copy(), G["dir"].copy()
    atr, c0, tf = B["atr5"], B["c"], B["tf"]
    stp0 = c0[I] - D * v["stop_x"] * atr[I]
    keep = np.ones(len(I), bool)
    cm = B["mod"][I] + tf
    keep &= (cm >= v["cm_min"]) & (cm <= v["cm_max"])
    X = ctx(B)
    dI = B["day"][I]
    if v["trend"]:
        keep &= (X["trend"][dI] == D.astype(int))
    if v["vix_min"] is not None:
        keep &= X["vix"][dI] >= v["vix_min"]
    if v["stopcap"]:
        keep &= v["stop_x"] * atr[I] / c0[I] * 100 <= v["stopcap"]
    I, D, ST = I[keep], D[keep], stp0[keep]
    o, h, l, c, mod, day, flat, t = B["o"], B["h"], B["l"], B["c"], B["mod"], B["day"], B["flat"], B["t"]
    hold = int(round(v["hold"] / tf))
    out, busy, cur, dn, dR, loss_run = [], -1, -1, 0, 0.0, 0
    for q in range(len(I)):
        s = int(I[q]); Dq = float(D[q])
        if day[s] != cur:
            cur, dn, dR, loss_run = day[s], 0, 0.0, 0
        if s < busy or dn >= v["maxday"] or dR <= -v["day_stop"] or (v["streak"] and loss_run >= v["streak"]):
            continue
        fe = int(flat[s])
        if s + 1 > fe or mod[s] > 930:
            continue
        j = s + 1
        st = float(ST[q])
        fill = float(o[j]) + Dq * TICK
        risk = Dq * (fill - st)
        if risk < TICK:
            busy = j
            continue
        tg = fill + Dq * v["tgt"] * risk if v["tgt"] else None
        stp, ext, mae, xp, xk, kind = st, fill, 0.0, None, j, None
        for i in range(j, fe + 1):
            first = i == j
            if not first and ((Dq > 0 and o[i] <= stp) or (Dq < 0 and o[i] >= stp)):
                xp, xk, kind = o[i] - Dq * TICK, i, "stop"; mae = max(mae, Dq * (fill - xp)); break
            if tg is not None and not first and ((Dq > 0 and o[i] >= tg + TICK) or (Dq < 0 and o[i] <= tg - TICK)):
                xp, xk, kind = o[i], i, "target"; break
            if (l[i] <= stp) if Dq > 0 else (h[i] >= stp):
                xp, xk, kind = stp - Dq * TICK, i, "stop"; mae = max(mae, Dq * (fill - xp)); break
            mae = max(mae, (fill - l[i]) if Dq > 0 else (h[i] - fill))
            if tg is not None and ((Dq > 0 and h[i] >= tg + TICK) or (Dq < 0 and l[i] <= tg - TICK)):
                xp, xk, kind = tg, i, "target"; break
            if i >= fe:
                xp, xk, kind = c[i] - Dq * TICK, i, "flat"; break
            if hold > 0 and i >= j + hold:
                xp, xk, kind = c[i] - Dq * TICK, i, "time"; break
            ext = max(ext, h[i]) if Dq > 0 else min(ext, l[i])
            if v["trail"] and Dq * (ext - fill) >= v["tstart"] * risk:
                nt = ext - Dq * v["trail"] * risk
                if Dq * (nt - stp) > 0:
                    stp = nt
        pts = Dq * (xp - fill)
        pm = pts * PV - COMM
        out.append({"day": str(B["dates"][day[j]]), "sig_t": int(t[s]), "entry_t": int(t[j]), "exit_t": int(t[xk]) + 60 * tf, "dir": int(Dq),
                    "pts": pts, "risk_pts": risk, "exit_kind": kind, "pnl_pm": pm, "risk_pm": (risk + TICK) * PV + COMM,
                    "mae_pm": -mae * PV - COMM, "mod": int(mod[s]) + tf})
        busy = xk
        dn += 1
        dR += pm / ((risk + TICK) * PV + COMM)
        loss_run = loss_run + 1 if pm < 0 else 0
    return out


def usd(T, extra=0.0):
    out = []
    for t in T:
        q = max(1, min(20, int(USD / t["risk_pm"])))
        out.append({**t, "pnl": q * (t["pnl_pm"] - extra * 2 * TICK * PV), "low": min(0.0, q * t["mae_pm"]), "q": q})
    return out


def daily(T):
    d = collections.defaultdict(float)
    for t in T:
        d[t["day"]] += t["pnl"]
    return d


def holm(ps):
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    adj, run = [None] * len(ps), 0.0
    for k, i in enumerate(order):
        run = max(run, min(1.0, (len(ps) - k) * ps[i]))
        adj[i] = run
    return adj


def perm_p(diff, n=20000, seed=7):
    d = np.asarray(diff, float)
    if not len(d) or not np.any(d):
        return 1.0
    rng = np.random.default_rng(seed)
    obs = d.mean()
    s = rng.choice([-1.0, 1.0], size=(n, len(d)))
    return float((1 + np.sum((s * d).mean(axis=1) >= obs - 1e-12)) / (1 + n))


def score(nm, v, B1, B5, S, TV, base):
    T1, T5 = TV
    o = {"cfg": v, "spans": {}, "years": {}, "tick1": {}}
    for sp, (tf, k) in SPANS.items():
        Ss = S[sp]
        T = T1 if tf == 1 else T5
        st = N.stats(T, Ss, USD, 20)
        ev = MT.span_stats(T, Ss, Ss[0], Ss[-1])
        st["b25k"], st["rapid25k"], st["k50"] = ev["evals"]["25K"], ev["evals"]["Rapid25K"], ev["evals"]["50K"]
        o["spans"][sp] = st
        Tx = usd(BZ_raw[nm][0 if tf == 1 else 1], 1.0)
        sx = N.stats(Tx, Ss, USD, 20)
        o["tick1"][sp] = {"pf": sx["pf"], "per_month": sx["per_month"], "net": sx["net"]}
    for y in BZ.YEARS:
        o["years"][y] = N.stats(T5, [d for d in S["2021-25"] if d.startswith(y)], USD, 20)["per_month"]
    o["walk_forward"] = BZ.walk(T5, B5, base[1]) if nm != "V0 today" else "-"
    return o


BZ_raw = {}


def diff_series(TV, T0, S):
    """Daily $ difference variant - today over every session 2021-11..2026-11 (2021-25 from 5m, 2026 from 1m)."""
    out = {}
    for lab, (a, b, Ss) in (("2021-25", (TV[1], T0[1], S["2021-25"])), ("2026 H1", (TV[0], T0[0], S["2026 H1"])),
                            ("2026 Jul-Nov20", (TV[0], T0[0], S["2026 Jul-Nov20"]))):
        da, db = daily(a), daily(b)
        out[lab] = np.array([da.get(s, 0.0) - db.get(s, 0.0) for s in Ss])
    return out


def main():
    t0 = time.time()
    say = lambda s: print(f"[{time.time() - t0:5.0f}s] {s}", flush=True)  # noqa: E731
    B1, B5 = N.bars(1), N.bars(5)
    S = {sp: N.sessions(B1 if tf == 1 else B5, k) for sp, (tf, k) in SPANS.items()}
    ref = L.trades()
    mine = {1: sim(B1, {}), 5: sim(B5, {})}
    par = {tf: {"n_lib": len(ref[tf]), "n_mine": len(mine[tf]), "same_entries": len({t["entry_t"] for t in ref[tf]} & {t["entry_t"] for t in mine[tf]}),
                "net_pm_lib": round(sum(t["pnl_pm"] for t in ref[tf]), 1), "net_pm_mine": round(sum(t["pnl_pm"] for t in mine[tf]), 1)} for tf in (1, 5)}
    say(f"parity {par}")
    res = {"made": "2026-11-27", "design": "research/blitzmore/DESIGN.md", "parity": par, "variants": {}}
    TV, base = {}, None
    names = list(V)
    for nm in names:
        v = V[nm]
        if nm.startswith("M13"):
            continue
        r1, r5 = sim(B1, v), sim(B5, v)
        BZ_raw[nm] = (r1, r5)
        TV[nm] = (usd(r1), usd(r5))
    T0 = TV["V0 today"]
    base = T0
    pvals = {}
    for nm in names:
        o = score(nm, V[nm], B1, B5, S, TV[nm], base)
        dd = diff_series(TV[nm], T0, S)
        allv = np.concatenate([dd["2021-25"], dd["2026 H1"], dd["2026 Jul-Nov20"]])
        o["p_raw"] = perm_p(allv) if nm != "V0 today" else None
        o["p_2125"] = perm_p(dd["2021-25"]) if nm != "V0 today" else None
        res["variants"][nm] = o
        s = o["spans"]
        say(f"{nm:36s} " + " | ".join(f"{k}: {s[k]['tpw']}/wk PF {s[k]['pf']} ${s[k]['per_month']:,}/mo DD {s[k]['dd']}" for k in SPANS) + f" | yrs {o['years']} | p {o['p_raw']}")
    # ---- picks / checks (rules fixed in DESIGN.md)
    b = res["variants"]["V0 today"]["spans"]
    surv = []
    for nm in names[1:]:
        s = res["variants"][nm]["spans"]
        pick = s["2026 H1"]["per_month"] > b["2026 H1"]["per_month"] and (s["2026 H1"]["pf"] or 0) >= (b["2026 H1"]["pf"] or 0) - 0.05
        chk = s["2026 Jul-Nov20"]["per_month"] >= b["2026 Jul-Nov20"]["per_month"] and s["2021-25"]["per_month"] >= b["2021-25"]["per_month"]
        res["variants"][nm]["pick"], res["variants"][nm]["check"] = bool(pick), bool(chk)
        if pick and chk:
            surv.append(nm)
    say(f"survivors of PICK + CHECK: {surv}")
    # ---- M13: the combination of the survivors (counted as a test either way)
    if surv:
        cfg = {}
        for nm in surv:
            cfg.update(V[nm])
    else:
        cfg = {}
    nm13 = "M13 combination of the survivors" + ("" if surv else " (none survived: = today)")
    r1, r5 = sim(B1, cfg), sim(B5, cfg)
    BZ_raw[nm13] = (r1, r5)
    TV[nm13] = (usd(r1), usd(r5))
    V[nm13] = cfg
    o = score(nm13, cfg, B1, B5, S, TV[nm13], base)
    dd = diff_series(TV[nm13], T0, S)
    o["p_raw"] = perm_p(np.concatenate(list(dd.values()))) if surv else 1.0
    o["p_2125"] = perm_p(dd["2021-25"]) if surv else 1.0
    s = o["spans"]
    o["pick"] = bool(surv) and s["2026 H1"]["per_month"] > b["2026 H1"]["per_month"]
    o["check"] = bool(surv) and s["2026 Jul-Nov20"]["per_month"] >= b["2026 Jul-Nov20"]["per_month"] and s["2021-25"]["per_month"] >= b["2021-25"]["per_month"]
    res["variants"][nm13] = o
    say(f"{nm13}: " + " | ".join(f"{k}: PF {s[k]['pf']} ${s[k]['per_month']:,}/mo" for k in SPANS) + f" p {o['p_raw']}")
    tests = [n for n in res["variants"] if n != "V0 today"]
    adj = holm([res["variants"][n]["p_raw"] for n in tests])
    for n, a in zip(tests, adj):
        r = res["variants"][n]
        r["p_holm"] = round(a, 4)
        s = r["spans"]
        r["holds_up"] = bool(r["pick"] and r["check"] and (s["2021-25"]["pf"] or 0) >= 1.15 and (r["tick1"]["2021-25"]["pf"] or 0) > 1.05
                             and all(r["years"][y] >= 0 for y in BZ.YEARS) and a <= 0.05)
        r["tradeoff"] = bool((s["2021-25"]["per_month"] > b["2021-25"]["per_month"]) and
                             (s["2026 H1"]["per_month"] + s["2026 Jul-Nov20"]["per_month"] < 0.75 * (b["2026 H1"]["per_month"] + b["2026 Jul-Nov20"]["per_month"])))
    res["holm_tests"] = len(tests)
    json.dump(res, open(os.path.join(HERE, "results.json"), "w"), indent=1, default=float)
    say("done")


if __name__ == "__main__":
    main()
