"""Discretion score for ATLAS and BLITZ (owner 2026-10-30: "good discretion like a skilled human trader": judge each trade's
quality from what is known at entry, trade the good ones bigger, the bad ones smaller or not at all).
Write-up: research/writeups/discretion-score-2026-10-30.md. Research only: nothing here touches engine/, live_model*.json,
second_model.json or data/.

PRE-REGISTERED (written before any fit; not changed after looking at H2 / 2021-25):
  features (6 per bot, all known at the signal / entry bar's close, never the trade's own outcome / mfe / mae):
    BLITZ  exc        how hard the band broke: the close's move from the 09:30 open in noise-band sigmas
           rng_sofar  the day's range 09:30 -> signal / its 14-day mean RTH range (trend-day activity)
           vix        VIX prior close (CBOE's own file)
           nth        the day's signal count so far (the "later break" idea), capped at 4
           liq_room   distance from the signal close to the nearest untaken liquidity ahead (the session's extreme so far
                      incl. the prior evening, the prior RTH high / low, the prior week high / low; only pools beyond the
                      session extreme count), in 5m ATR, capped at 6
           st15_with  15m market structure (engine/structure.frame_events on 15m bars built from the 5m CME bars, closed
                      bars only): +1 the last break was with the trade, -1 against, 0 none yet
    ATLAS  stop_atr   the stop distance / 5m ATR(14) at the last closed 5m bar before the entry
           vix        VIX prior close
           atrp       percentile of the prior session's daily ATR(14) in the trailing year (tools/atlas_v2.atr_pct)
           liq_room   as BLITZ (from the entry price)
           st15_with  as BLITZ (at the entry time)
           day_prev   the day's earlier ATLAS candidate that had closed before this entry: +1 won, -1 lost, 0 none
  models (fit on 2026 H1 trades only, then frozen):
    ridge  ridge regression of the trade's R (costs in, clipped to [-1.5, +3]) on the 6 standardised features (H1 mean / sd,
           a missing value = the H1 mean), penalty alpha = 1 x n (strong shrinkage)
    check  a points checklist: +1 per feature on its H1-better side of its H1 median (the side = the sign of the feature's
           H1 correlation with R), score 0-6
  size rules (score terciles cut on the H1 scores, frozen):
    t3     bottom third x0.5, middle x1, top third x1.5
    skip   bottom third not traded, the rest x1
  controls: the same fit on H1 with the trades' R shuffled (200 seeds BLITZ, 40 ATLAS), applied the same way; the real
           score's rank among them on H2 and on 2021-25 (p = share of shuffles at least as good).
  money: BLITZ - "$500 view" ($500 x mult risk a trade, fractional micros, $1.90 a micro + 1 tick), the MFFU 25K eval
           ({"mode":"frac","f":0.4,"cap":600,"push":(5,1.0)}, x mult) and the whole 25K slot $ a month
           (tools/blitz25k_size.life); ATLAS - "$500 view" and tools/atlas_v2.score (the account-B 25K need size x mult,
           back-to-back eval paths, verdict = the v2 test).
  a score counts only if it is better in H1, H2 AND 2021-25 and beats its shuffled controls.

    python -X utf8 tools/dsx_discretion.py blitz     # -> research/scalp/dsx_blitz.json
    python -X utf8 tools/dsx_discretion.py atlas     # -> research/second/dsx_atlas.json
    python -X utf8 tools/dsx_discretion.py extra_blitz   # disclosed robustness: other model forms + fit on 2021-25 -> 2026
    python -X utf8 tools/dsx_discretion.py extra_atlas   # fit on 2021-24 -> 2025 / 2026 (add "100 ridge 11" for 100 shuffles)
    python -X utf8 tools/dsx_discretion.py prior         # a trader's checklist, no fit (written after the first fact table)
    python -X utf8 tools/dsx_discretion.py prior_check   # its multiplier-shuffle p, per year, eval / slot at 1,000 lives
    python -X utf8 tools/dsx_discretion.py save      # runs dsx_* in the run library
"""
from __future__ import annotations

import collections
import json
import os
import sys
import time
import warnings

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
warnings.filterwarnings("ignore")
from tools import ab_edge as E  # noqa: E402

FB = ("exc", "rng_sofar", "vix", "nth", "liq_room", "st15_with")
FA = ("stop_atr", "vix", "atrp", "liq_room", "st15_with", "day_prev")
RULES = {"t3": (0.5, 1.0, 1.5), "skip": (0.0, 1.0, 1.0)}
CLIP = (-1.5, 3.0)
ALPHA = 1.0
CAP_ROOM = 6.0
OUT_B = os.path.join(ROOT, "research", "scalp", "dsx_blitz.json")
OUT_A = os.path.join(ROOT, "research", "second", "dsx_atlas.json")
A_SPANS = ("H1", "H2", "2025", "2021-24")
MONTHS_A = E.MONTHS_A
COMM, PV, TICK = 1.90, 2.0, 0.25


# ================================================================================================ shared facts
_C = {}


def bars5():
    N, K, BS = E.blitz_libs()
    return N.bars(5)


def st15():
    """15m structure events from the 5m CME bars (closed 15m buckets only; known at the bucket's end)."""
    if "st15" in _C:
        return _C["st15"]
    from engine import structure as ST
    B = bars5()
    t = np.asarray(B["t"], np.int64)
    g = (t // 900) * 900
    first = np.r_[True, g[1:] != g[:-1]]
    last = np.r_[g[1:] != g[:-1], True]
    gid = np.cumsum(first) - 1
    ng = int(gid[-1]) + 1
    H = np.full(ng, -np.inf); L = np.full(ng, np.inf)
    np.maximum.at(H, gid, B["h"]); np.minimum.at(L, gid, B["l"])
    ev = ST.frame_events(g[first], B["o"][first], H, L, B["c"][last], 900)
    _C["st15"] = ev
    return ev


def trend15(ts):
    ev = st15()
    i = int(np.searchsorted(ev["known_t"], int(ts), side="right")) - 1
    return float(ev["dir"][i]) if i >= 0 else 0.0


def liq_room(B, i, dr, px):
    """nearest untaken liquidity ahead of px (trade direction dr) in ATR of bars B, from closed bars up to index i."""
    N, K, BS = E.blitz_libs()
    D = K.levels_ctx(B)
    if i < 0 or i >= len(B["t"]):
        return np.nan
    di = int(B["day"][i])
    s0 = int(D["s0"][di])
    if s0 < 0 or s0 > i:
        return np.nan
    a = B["atr5"][i] if "atr5" in B else B["atr"][i]
    if not (a == a and a > 0):
        return np.nan
    if dr > 0:
        ext = float(np.max(B["h"][s0:i + 1]))
        if D["eveh"][di] == D["eveh"][di]:
            ext = max(ext, float(D["eveh"][di]))
        pools = [ext] + [x for x in (D["pdh"][di], D["pwh"][di]) if x == x and x > ext]
        ahead = [x - px for x in pools if x > px]
    else:
        ext = float(np.min(B["l"][s0:i + 1]))
        if D["evel"][di] == D["evel"][di]:
            ext = min(ext, float(D["evel"][di]))
        pools = [ext] + [x for x in (D["pdl"][di], D["pwl"][di]) if x == x and x < ext]
        ahead = [px - x for x in pools if x < px]
    return float(min(CAP_ROOM, min(ahead) / a)) if ahead else CAP_ROOM


# ================================================================================================ models
def _std(X, mu=None, sd=None):
    if mu is None:
        mu = np.nanmean(X, 0)
        sd = np.nanstd(X, 0)
        sd = np.where(sd > 0, sd, 1.0)
    Z = (X - mu) / sd
    return np.where(Z == Z, Z, 0.0), mu, sd


ALPHAS = {"ridge": ALPHA, "ridge01": 0.1, "ridge10": 10.0}      # robustness forms (extra), the pre-registered one is "ridge"
LOGIT_LAM = 0.05


def fit(model, X, R):
    """-> a frozen model dict (fit on the H1 rows X, outcomes R)."""
    if model in ALPHAS:
        Z, mu, sd = _std(X)
        y = np.clip(R, *CLIP)
        y = y - y.mean()
        n = len(y)
        w = np.linalg.solve(Z.T @ Z + ALPHAS[model] * n * np.eye(Z.shape[1]), Z.T @ y)
        return {"model": "ridge", "mu": mu, "sd": sd, "w": w}
    if model == "logit":                       # L2 logistic regression of "a winner" (R > 0), Newton steps
        Z, mu, sd = _std(X)
        y = (R > 0).astype(float)
        n, k = Z.shape
        Z1 = np.c_[np.ones(n), Z]
        w = np.zeros(k + 1)
        P = np.diag(np.r_[0.0, np.full(k, LOGIT_LAM * n)])
        for _ in range(30):
            p = 1 / (1 + np.exp(-Z1 @ w))
            g = Z1.T @ (p - y) + P @ w
            Hs = (Z1 * (p * (1 - p))[:, None]).T @ Z1 + P
            w = w - np.linalg.solve(Hs, g)
        return {"model": "ridge", "mu": mu, "sd": sd, "w": w[1:]}
    if model == "check":
        med = np.nanmedian(X, 0)
        sg = np.zeros(X.shape[1])
        for j in range(X.shape[1]):
            ok = X[:, j] == X[:, j]
            if ok.sum() > 5 and np.std(X[ok, j]) > 0:
                sg[j] = np.sign(np.corrcoef(X[ok, j], R[ok])[0, 1])
        return {"model": "check", "med": med, "sg": sg}
    raise ValueError(model)


def score_of(M, X):
    if M["model"] == "ridge":
        Z, _, _ = _std(X, M["mu"], M["sd"])
        return Z @ M["w"]
    d = (X - M["med"]) * M["sg"]
    return np.where(d == d, (d > 0).astype(float), 0.0).sum(1)


def cuts(s):
    return float(np.quantile(s, 1 / 3)), float(np.quantile(s, 2 / 3))


def mult_of(s, c, rule):
    lo, mid, hi = RULES[rule]
    return np.where(s < c[0], lo, np.where(s >= c[1], hi, mid))


def model_json(M, feats):
    if M["model"] == "ridge":
        return {"model": "ridge", "alpha_per_trade": ALPHA, "clip": CLIP,
                "weights_per_sd": {f: round(float(w), 4) for f, w in zip(feats, M["w"])},
                "h1_mean": {f: round(float(m), 4) for f, m in zip(feats, M["mu"])}, "h1_sd": {f: round(float(s), 4) for f, s in zip(feats, M["sd"])}}
    return {"model": "check", "h1_median": {f: round(float(m), 4) for f, m in zip(feats, M["med"])},
            "point_side": {f: ("high" if g > 0 else "low" if g < 0 else "none") for f, g in zip(feats, M["sg"])}}


# ================================================================================================ BLITZ
def blitz_prep():
    N, K, BS = E.blitz_libs()
    from tools import blitz25k_grid as G
    G.prep()
    TT, SP = E._prep_blitz()
    for tf in (1, 5):
        B = N.bars(tf)
        for t in TT[tf]:
            i = int(np.searchsorted(B["t"], t["sig_t"]))
            px = float(B["c"][i])
            t["f"]["liq_room"] = liq_room(B, i, t["dir"], px)
            t["f"]["st15_with"] = trend15(int(t["sig_t"]) + 60 * B["tf"]) * t["dir"]
            nth = t["f"].get("nth", np.nan)
            t["f"]["nth_c"] = min(4.0, nth) if nth == nth else np.nan
    return TT, E.spans_of(TT)


def bX(T):
    return np.array([[t["f"].get("nth_c" if f == "nth" else f, np.nan) for f in FB] for t in T], float)


def bR(T):
    return np.array([t["pnl_pm"] / t["risk_pm"] for t in T])


def b_eval(SP, m, slot=True, n=300):
    out = {}
    for sp in ("H1", "H2", "R"):
        T, S = SP[sp]
        out[sp] = {"usd500": E.rview(T, S, m[sp]), "ev": E.ev25(T, S, m[sp])}
        tk = [t for t, x in zip(T, m[sp]) if x > 0]                 # the trades actually taken (skip rule)
        out[sp]["usd500"]["tpw_taken"] = round(len(tk) / (len(S) / 5), 2)
        out[sp]["usd500"]["wk2_taken"] = E.blitz_libs()[1].wk2(tk, S)
        if slot:
            out[sp]["slot"] = E.slot25(T, S, m[sp], n=n)
    return out


# ================================================================================================ extra (disclosed robustness)
def _pl_rank(real, L):
    a = np.array(L, float)
    return {"p": round(float((a >= real - 1e-9).mean()), 3), "pl_mean": round(float(a.mean()), 3), "pl_q95": round(float(np.quantile(a, 0.95)), 3)}


def cmd_extra_blitz(n_pl=100):
    """robustness forms of the score (NOT the pre-registered one, reported as a family): ridge alpha 0.1 / 10 and a logistic
    regression of "a winner" fit on H1; and the reverse test - the pre-registered ridge / checklist fit on the 5-year 2021-25
    trades (1,841, 5m) and applied to 2026 H1 and H2 (both untouched). Each with its own shuffled-label controls."""
    t0 = time.time()
    TT, SP = blitz_prep()
    XS = {sp: bX(SP[sp][0]) for sp in SP}
    RS = {sp: bR(SP[sp][0]) for sp in SP}
    today = b_eval(SP, {sp: np.ones(len(RS[sp])) for sp in RS})
    out = {"built": time.strftime("%Y-%m-%d %H:%M"), "rows": {}}
    rng = np.random.default_rng(7)
    for model, src in (("ridge01", "H1"), ("ridge10", "H1"), ("logit", "H1"), ("ridge", "R"), ("check", "R")):
        name = f"{model} fit on {src}"
        Mo = fit(model, XS[src], RS[src])
        sc = {sp: score_of(Mo, XS[sp]) for sp in XS}
        c = cuts(sc[src])
        m = {sp: mult_of(sc[sp], c, "t3") for sp in sc}
        x = b_eval(SP, m)
        row = {"fit": {"model": model, "fit_on": src, **({"weights_per_sd": {f: round(float(w), 4) for f, w in zip(FB, Mo["w"])}} if "w" in Mo else
                                                         {"point_side": {f: int(g) for f, g in zip(FB, Mo["sg"])}})}, "t3": x, "placebo": {}}
        L = collections.defaultdict(list)
        for s in range(n_pl):
            Rs = rng.permutation(RS[src])
            Mp = fit(model, XS[src], Rs)
            scp = {sp: score_of(Mp, XS[sp]) for sp in XS}
            cp = cuts(scp[src])
            for sp in ("H1", "H2", "R"):
                mp = mult_of(scp[sp], cp, "t3")
                L[sp].append(E.rview(SP[sp][0], SP[sp][1], mp)["r_per_risk"])
        for sp in ("H1", "H2", "R"):
            row["placebo"][sp] = _pl_rank(x[sp]["usd500"]["r_per_risk"], L[sp])
        out["rows"][name] = row
        print(f"{name}: " + " | ".join(f"{sp} r/risk {x[sp]['usd500']['r_per_risk']:+.3f} (today {today[sp]['usd500']['avg_r']:+.3f}, p {row['placebo'][sp]['p']}) "
                                      f"2w {x[sp]['ev']['p10']}/{x[sp]['ev']['f10']} slot ${x[sp]['slot']['life_pm']} (today ${today[sp]['slot']['life_pm']})"
                                      for sp in ("H1", "H2", "R")), json.dumps(row["fit"]), flush=True)
    E.dump(out, OUT_B.replace(".json", "_extra.json"))
    print(f"done {time.time() - t0:.0f}s", flush=True)
    return out


def cmd_blitz(n_pl=200):
    t0 = time.time()
    TT, SP = blitz_prep()
    XS = {sp: bX(SP[sp][0]) for sp in SP}
    RS = {sp: bR(SP[sp][0]) for sp in SP}
    print("BLITZ trades", {sp: len(RS[sp]) for sp in RS}, f"{time.time() - t0:.0f}s", flush=True)
    out = {"built": time.strftime("%Y-%m-%d %H:%M"), "feats": FB, "n": {sp: len(RS[sp]) for sp in RS}, "coverage": {}, "facts": {}}
    for j, f in enumerate(FB):
        out["coverage"][f] = {sp: round(float((XS[sp][:, j] == XS[sp][:, j]).mean()), 3) for sp in XS}
        med = float(np.nanmedian(XS["H1"][:, j]))
        row = {"h1_median": med}
        for sp in XS:
            x, r = XS[sp][:, j], RS[sp]
            hi, lo = (x >= med) & (x == x), (x < med) & (x == x)
            row[sp] = {"hi": [int(hi.sum()), round(float(r[hi].mean()), 3) if hi.any() else None],
                       "lo": [int(lo.sum()), round(float(r[lo].mean()), 3) if lo.any() else None],
                       "corr": round(float(np.corrcoef(x[x == x], r[x == x])[0, 1]), 3) if (x == x).sum() > 5 else None}
        out["facts"][f] = row
        print(f, json.dumps(row), flush=True)
    one = {sp: np.ones(len(RS[sp])) for sp in RS}
    out["today"] = b_eval(SP, one)
    rows = {}
    for model in ("ridge", "check"):
        M = fit(model, XS["H1"], RS["H1"])
        sc = {sp: score_of(M, XS[sp]) for sp in XS}
        c = cuts(sc["H1"])
        rows[model] = {"fit": model_json(M, FB), "cuts": c,
                       "score_corr_R": {sp: round(float(np.corrcoef(sc[sp], RS[sp])[0, 1]), 3) for sp in sc},
                       "tercile_avg_R": {sp: [round(float(RS[sp][k].mean()), 3) if k.any() else None for k in
                                              (sc[sp] < c[0], (sc[sp] >= c[0]) & (sc[sp] < c[1]), sc[sp] >= c[1])] for sp in sc},
                       "tercile_n": {sp: [int(k.sum()) for k in (sc[sp] < c[0], (sc[sp] >= c[0]) & (sc[sp] < c[1]), sc[sp] >= c[1])] for sp in sc}}
        for rule in RULES:
            m = {sp: mult_of(sc[sp], c, rule) for sp in sc}
            rows[model][rule] = b_eval(SP, m)
            x = rows[model][rule]
            print(f"{model} {rule}: " + " | ".join(
                f"{sp} r/risk {x[sp]['usd500']['r_per_risk']:+.3f} (today {out['today'][sp]['usd500']['avg_r']:+.3f}) "
                f"${x[sp]['usd500']['per_month']}/mo PF {x[sp]['usd500']['pf']} 2w {x[sp]['ev']['p10']}/{x[sp]['ev']['f10']} slot ${x[sp]['slot']['life_pm']}"
                for sp in ("H1", "H2", "R")), flush=True)
        print(model, json.dumps(rows[model]["fit"]), rows[model]["tercile_avg_R"], flush=True)
    out["rows"] = rows
    # shuffled-label controls
    rng = np.random.default_rng(2026)
    pl = {(model, rule): [] for model in ("ridge", "check") for rule in RULES}
    for s in range(n_pl):
        Rs = rng.permutation(RS["H1"])
        for model in ("ridge", "check"):
            M = fit(model, XS["H1"], Rs)
            sc = {sp: score_of(M, XS[sp]) for sp in XS}
            c = cuts(sc["H1"])
            for rule in RULES:
                m = {sp: mult_of(sc[sp], c, rule) for sp in sc}
                rec = {}
                for sp in ("H1", "H2", "R"):
                    T, S = SP[sp]
                    v = E.rview(T, S, m[sp])
                    rec[sp] = (v["r_per_risk"], v["per_month"], E.slot25(T, S, m[sp], n=100)["life_pm"])
                pl[(model, rule)].append(rec)
        if s % 20 == 19:
            print(f"placebo {s + 1}/{n_pl} {time.time() - t0:.0f}s", flush=True)
    out["placebo"] = {}
    for (model, rule), L in pl.items():
        real = rows[model][rule]
        o = {}
        for sp in ("H1", "H2", "R"):
            # the real score's slot at n=100 too, so it is compared like for like
            a = np.array([r[sp] for r in L], float)
            rr = (real[sp]["usd500"]["r_per_risk"], real[sp]["usd500"]["per_month"])
            o[sp] = {"p_r_per_risk": round(float((a[:, 0] >= rr[0] - 1e-9).mean()), 3), "p_usd500": round(float((a[:, 1] >= rr[1] - 1e-9).mean()), 3),
                     "pl_mean_r_per_risk": round(float(a[:, 0].mean()), 3), "pl_mean_usd500": round(float(a[:, 1].mean())),
                     "pl_slot_mean": round(float(a[:, 2].mean())), "pl_slot_q95": round(float(np.quantile(a[:, 2], 0.95)))}
        o["_slot_raw"] = {sp: [r[sp][2] for r in L] for sp in ("H1", "H2", "R")}
        out["placebo"][f"{model} {rule}"] = o
    # the real score's slot at the placebo's n=100 for the slot rank
    for model in ("ridge", "check"):
        M = fit(model, XS["H1"], RS["H1"])
        sc = {sp: score_of(M, XS[sp]) for sp in XS}
        c = cuts(sc["H1"])
        for rule in RULES:
            m = {sp: mult_of(sc[sp], c, rule) for sp in sc}
            o = out["placebo"][f"{model} {rule}"]
            for sp in ("H1", "H2", "R"):
                T, S = SP[sp]
                v = E.slot25(T, S, m[sp], n=100)["life_pm"]
                raw = np.array(o["_slot_raw"][sp], float)
                o[sp]["real_slot_n100"] = v
                o[sp]["p_slot"] = round(float((raw >= v - 1e-9).mean()), 3)
            o.pop("_slot_raw")
            print("placebo", model, rule, json.dumps(o), flush=True)
    E.dump(out, OUT_B)
    print(f"wrote {OUT_B} {time.time() - t0:.0f}s", flush=True)
    return out


# ================================================================================================ ATLAS
def a_units():
    V2, A, M, EAB = E.atlas_libs()
    V = V2.V_()
    U = A.account_units(V)
    B = bars5()
    t = np.asarray(B["t"], np.int64)
    a14 = V2.atr_pct()
    vx = A.vix_prev()
    by = collections.defaultdict(list)
    for u in U:
        by[u["day"]].append(u)
    for u in U:
        i = int(np.searchsorted(t, int(u["entry_t"]) - 300, side="right")) - 1
        f = {}
        a = B["atr5"][i] if "atr5" in B else B["atr"][i]
        f["stop_atr"] = float(u["risk"]) / float(a) if a == a and a > 0 else np.nan
        f["vix"] = float(vx.get(u["day"], np.nan))
        f["atrp"] = float(a14.get(u["day"], np.nan))
        px = float(u.get("entry", B["c"][i]))
        f["liq_room"] = liq_room(B, i, u["dir"], px)
        f["st15_with"] = trend15(int(u["entry_t"])) * u["dir"]
        prev = [x for x in by[u["day"]] if x["exit_t"] <= u["entry_t"] and x is not u]
        f["day_prev"] = float(np.sign(E._R(sorted(prev, key=lambda x: x["exit_t"])[-1]))) if prev else 0.0
        u["_f"] = f
    return V, U


def a_span(d):
    return "H1" if "2026-01-01" <= d < "2026-07-01" else "H2" if d >= "2026-07-01" else "2025" if d >= "2025-01-01" else "2021-24"


def aR(u):
    return (float(u["pts"]) * PV - COMM) / ((float(u["risk"]) + TICK) * PV + COMM)


def a_view(U, m, sp, usd=500.0):
    R = np.array([aR(u) for u in U])
    pnl = usd * m * R
    gl = -pnl[pnl < 0].sum()
    eq = np.cumsum(pnl)
    return {"n": len(U), "avg_r": round(float(R.mean()), 3), "r_per_risk": round(float((m * R).sum() / max(1e-9, m.sum())), 3),
            "mean_mult": round(float(m.mean()), 3), "pf": round(float(pnl[pnl > 0].sum() / gl), 2) if gl else 99.0,
            "net": round(float(pnl.sum())), "per_month": round(float(pnl.sum() / MONTHS_A[sp])),
            "dd": round(float((eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min())) if len(eq) else 0}


def a_run(V, U, base, m_all, key):
    V2, A, M, EAB = E.atlas_libs()
    E._UM[key] = {(u["src"], u["entry_t"]): float(x) for u, x in zip(U, m_all) if x != 1.0}
    o = E.a_score({**V, "um": key})
    v = V2.verdict(o, base)
    sp_of = np.array([a_span(u["day"]) for u in U])
    view = {sp: a_view([u for u, s in zip(U, sp_of) if s == sp], m_all[sp_of == sp], sp) for sp in A_SPANS}
    return o, v, view


def cmd_atlas(n_pl=40):
    t0 = time.time()
    V2, A, M, EAB = E.atlas_libs()
    V, U = a_units()
    sp_of = np.array([a_span(u["day"]) for u in U])
    X = np.array([[u["_f"][f] for f in FA] for u in U], float)
    R = np.array([aR(u) for u in U])
    h1 = sp_of == "H1"
    print("ATLAS units", collections.Counter(sp_of), f"{time.time() - t0:.0f}s", flush=True)
    base = E.a_score(V)
    out = {"built": time.strftime("%Y-%m-%d %H:%M"), "feats": FA, "n": dict(collections.Counter(sp_of)), "facts": {},
           "today": {"o": E.a_compact(base), "view": {sp: a_view([u for u, s in zip(U, sp_of) if s == sp], np.ones((sp_of == sp).sum()), sp) for sp in A_SPANS}}}
    for j, f in enumerate(FA):
        med = float(np.nanmedian(X[h1, j]))
        row = {"h1_median": med, "coverage": round(float((X[:, j] == X[:, j]).mean()), 3)}
        for sp in A_SPANS:
            k = sp_of == sp
            x, r = X[k, j], R[k]
            hi, lo = (x >= med) & (x == x), (x < med) & (x == x)
            row[sp] = {"hi": [int(hi.sum()), round(float(r[hi].mean()), 3) if hi.any() else None],
                       "lo": [int(lo.sum()), round(float(r[lo].mean()), 3) if lo.any() else None],
                       "corr": round(float(np.corrcoef(x[x == x], r[x == x])[0, 1]), 3) if (x == x).sum() > 5 and np.std(x[x == x]) > 0 else None}
        out["facts"][f] = row
        print(f, json.dumps(row), flush=True)
    for s in A_SPANS:
        print("  today", E.a_line(base, s), flush=True)
    rows = {}
    for model in ("ridge", "check"):
        Mo = fit(model, X[h1], R[h1])
        sc = score_of(Mo, X)
        c = cuts(sc[h1])
        rows[model] = {"fit": model_json(Mo, FA), "cuts": c,
                       "score_corr_R": {sp: round(float(np.corrcoef(sc[sp_of == sp], R[sp_of == sp])[0, 1]), 3) for sp in A_SPANS},
                       "tercile_avg_R": {sp: [round(float(R[(sp_of == sp) & k].mean()), 3) if ((sp_of == sp) & k).any() else None for k in
                                              (sc < c[0], (sc >= c[0]) & (sc < c[1]), sc >= c[1])] for sp in A_SPANS},
                       "tercile_n": {sp: [int(((sp_of == sp) & k).sum()) for k in (sc < c[0], (sc >= c[0]) & (sc < c[1]), sc >= c[1])] for sp in A_SPANS}}
        for rule in RULES:
            m = mult_of(sc, c, rule)
            o, v, view = a_run(V, U, base, m, f"dsx_{model}_{rule}")
            rows[model][rule] = {"o": E.a_compact(o), "verdict": v, "view": view}
            print(f"{model} {rule} {'PASS' if v['pass'] else ('both' if v['both'] else '    ')} ref {v['ref']} | " +
                  " | ".join(f"{E.a_line(o, s)} r/risk {view[s]['r_per_risk']:+.3f} (today {view[s]['avg_r']:+.3f}) ${view[s]['per_month']}/mo" for s in A_SPANS), flush=True)
        print(model, json.dumps(rows[model]["fit"]), rows[model]["tercile_avg_R"], flush=True)
    out["rows"] = rows
    rng = np.random.default_rng(2026)
    pl = collections.defaultdict(list)
    for s in range(n_pl):
        Rs = R.copy()
        Rs[h1] = rng.permutation(R[h1])
        for model in ("ridge", "check"):
            Mo = fit(model, X[h1], Rs[h1])
            sc = score_of(Mo, X)
            c = cuts(sc[h1])
            for rule in RULES:
                m = mult_of(sc, c, rule)
                o, v, view = a_run(V, U, base, m, "_dsx_pl")
                pl[f"{model} {rule}"].append({sp: (view[sp]["r_per_risk"], view[sp]["per_month"], o[sp]["mp_net_less_fees"], o[sp]["p10"], o[sp]["dead10"])
                                              for sp in A_SPANS} | {"pass": v["pass"], "both": v["both"]})
        print(f"placebo {s + 1}/{n_pl} {time.time() - t0:.0f}s", flush=True)
    out["placebo"] = {}
    for k, L in pl.items():
        model, rule = k.split()
        real = rows[model][rule]
        o = {"pass_share": round(float(np.mean([r["pass"] for r in L])), 3), "both_share": round(float(np.mean([r["both"] for r in L])), 3)}
        for sp in A_SPANS:
            a = np.array([r[sp] for r in L], float)
            rr = (real["view"][sp]["r_per_risk"], real["view"][sp]["per_month"], real["o"][sp]["mp_net_less_fees"])
            o[sp] = {"p_r_per_risk": round(float((a[:, 0] >= rr[0] - 1e-9).mean()), 3), "p_usd500": round(float((a[:, 1] >= rr[1] - 1e-9).mean()), 3),
                     "p_eval_path": round(float((a[:, 2] >= rr[2] - 1e-9).mean()), 3), "pl_mean_eval_path": round(float(a[:, 2].mean())),
                     "pl_mean_r_per_risk": round(float(a[:, 0].mean()), 3)}
        out["placebo"][k] = o
        print("placebo", k, json.dumps(o), flush=True)
    E.dump(out, OUT_A)
    print(f"wrote {OUT_A} {time.time() - t0:.0f}s", flush=True)
    return out


def cmd_extra_atlas(n_pl=20, models=("ridge", "check"), seed=7, tag=""):
    """the reverse test for ATLAS: the pre-registered ridge / checklist fit on the 2021-24 candidates (875) and applied to
    2025, 2026 H1 and H2 (all untouched), t3 size, with shuffled-label controls."""
    t0 = time.time()
    V2, A, M, EAB = E.atlas_libs()
    V, U = a_units()
    sp_of = np.array([a_span(u["day"]) for u in U])
    X = np.array([[u["_f"][f] for f in FA] for u in U], float)
    R = np.array([aR(u) for u in U])
    k0 = sp_of == "2021-24"
    base = E.a_score(V)
    out = {"built": time.strftime("%Y-%m-%d %H:%M"), "rows": {}}
    rng = np.random.default_rng(seed)
    for model in models:
        Mo = fit(model, X[k0], R[k0])
        sc = score_of(Mo, X)
        c = cuts(sc[k0])
        o, v, view = a_run(V, U, base, mult_of(sc, c, "t3"), f"dsx_rev_{model}")
        row = {"fit": model_json(Mo, FA), "o": E.a_compact(o), "verdict": v, "view": view, "placebo": {}}
        L = collections.defaultdict(list)
        for s in range(n_pl):
            Rs = R.copy()
            Rs[k0] = rng.permutation(R[k0])
            Mp = fit(model, X[k0], Rs[k0])
            scp = score_of(Mp, X)
            op, vp, viewp = a_run(V, U, base, mult_of(scp, cuts(scp[k0]), "t3"), "_dsx_pl")
            for sp in A_SPANS:
                L[sp].append((viewp[sp]["r_per_risk"], op[sp]["mp_net_less_fees"]))
        for sp in A_SPANS:
            a = np.array(L[sp], float)
            row["placebo"][sp] = {"p_r_per_risk": round(float((a[:, 0] >= view[sp]["r_per_risk"] - 1e-9).mean()), 3),
                                  "p_eval_path": round(float((a[:, 1] >= o[sp]["mp_net_less_fees"] - 1e-9).mean()), 3),
                                  "pl_mean_eval_path": round(float(a[:, 1].mean()))}
        out["rows"][f"{model} fit on 2021-24"] = row
        print(f"{model} fit on 2021-24 {'PASS' if v['pass'] else ('both' if v['both'] else '    ')} ref {v['ref']} | " +
              " | ".join(f"{E.a_line(o, s)} r/risk {view[s]['r_per_risk']:+.3f} (today {view[s]['avg_r']:+.3f}) p {row['placebo'][s]}" for s in A_SPANS),
              json.dumps(row["fit"]), flush=True)
    E.dump(out, OUT_A.replace(".json", f"_extra{tag}.json"))
    print(f"done {time.time() - t0:.0f}s", flush=True)
    return out


# ================================================================================================ a trader's prior (no fit at all)
# The checklist a discretionary trader would write down BEFORE looking at any result (signs from trading logic, not data):
# a point per box ticked; 0-1 points x0.5, 2-3 x1, 4-5 x1.5. "med" = the H1 median of the fact (a level, not an outcome).
PRIOR_B = (("exc", ">", "med"),          # a strong break, not a drift over the band
           ("rng_sofar", ">", "med"),    # the day is already moving (trend day)
           ("nth", ">=", 2.0),           # not the day's first signal: the move has been confirmed
           ("liq_room", ">", "med"),     # room to run before the next pool where it can stall
           ("st15_with", ">=", 1.0))     # with the 15m structure
PRIOR_A = (("stop_atr", "<", "med"),     # a tight, clean sweep (small stop in ATR)
           ("atrp", ">", "med"),         # a market that moves (daily ATR high in its year)
           ("liq_room", ">", "med"),     # room to the next pool
           ("st15_with", ">=", 1.0),     # with the 15m structure
           ("day_prev", ">=", 0.0))      # not right after a losing trade today
PRIOR_BANDS = ((0, 1, 0.5), (2, 3, 1.0), (4, 5, 1.5))


def prior_points(X, feats, prior, flips, xh1):
    pts = np.zeros(len(X))
    for k, (f, op, thr) in enumerate(prior):
        j = feats.index(f)
        x = X[:, j]
        th = float(np.nanmedian(xh1[:, j])) if thr == "med" else float(thr)
        hit = {">": x > th, ">=": x >= th, "<": x < th}[op]
        if flips[k]:
            hit = ~hit
        pts += np.where(x == x, hit, False)
    return pts


def prior_mult(pts):
    m = np.ones(len(pts))
    for lo, hi, mm in PRIOR_BANDS:
        m[(pts >= lo) & (pts <= hi)] = mm
    return m


def cmd_prior():
    """the trader's prior checklist (no fit; every span is out of sample) vs all 31 other sign choices of the same 5 boxes."""
    import itertools
    t0 = time.time()
    out = {"built": time.strftime("%Y-%m-%d %H:%M"), "blitz": {}, "atlas": {}}
    TT, SP = blitz_prep()
    feats = list(FB)
    XS = {sp: bX(SP[sp][0]) for sp in SP}
    rows = []
    for flips in itertools.product((0, 1), repeat=len(PRIOR_B)):
        m = {sp: prior_mult(prior_points(XS[sp], feats, PRIOR_B, flips, XS["H1"])) for sp in XS}
        x = {sp: E.rview(SP[sp][0], SP[sp][1], m[sp]) for sp in XS}
        rows.append({"flips": flips, **{sp: x[sp]["r_per_risk"] for sp in XS}})
        if not any(flips):
            real = b_eval(SP, m)
            out["blitz"]["prior"] = real
            out["blitz"]["share_by_band"] = {sp: [round(float((m[sp] == mm).mean()), 3) for _, _, mm in PRIOR_BANDS] for sp in m}
    for sp in ("H1", "H2", "R"):
        a = np.array([r[sp] for r in rows])
        out["blitz"][f"rank_{sp}"] = int((a > rows[0][sp] + 1e-12).sum()) + 1        # 1 = best of the 32
    out["blitz"]["all"] = rows
    print("BLITZ prior:", {sp: (out["blitz"]["prior"][sp]["usd500"]["r_per_risk"], out["blitz"][f"rank_{sp}"]) for sp in ("H1", "H2", "R")},
          out["blitz"]["share_by_band"], f"{time.time() - t0:.0f}s", flush=True)
    V2, A, M, EAB = E.atlas_libs()
    V, U = a_units()
    sp_of = np.array([a_span(u["day"]) for u in U])
    X = np.array([[u["_f"][f] for f in FA] for u in U], float)
    base = E.a_score(V)
    rows = []
    for flips in itertools.product((0, 1), repeat=len(PRIOR_A)):
        m = prior_mult(prior_points(X, list(FA), PRIOR_A, flips, X[sp_of == "H1"]))
        o, v, view = a_run(V, U, base, m, "_dsx_prior")
        rows.append({"flips": flips, **{s: [view[s]["r_per_risk"], o[s]["mp_net_less_fees"]] for s in A_SPANS}, "pass": v["pass"]})
        if not any(flips):
            out["atlas"]["prior"] = {"o": E.a_compact(o), "verdict": v, "view": view,
                                     "share_by_band": {s: [round(float((m[sp_of == s] == mm).mean()), 3) for _, _, mm in PRIOR_BANDS] for s in A_SPANS}}
            print("ATLAS prior:", " | ".join(f"{E.a_line(o, s)} r/risk {view[s]['r_per_risk']:+.3f} (today {view[s]['avg_r']:+.3f})" for s in A_SPANS), flush=True)
    for s in A_SPANS:
        a = np.array([r[s][0] for r in rows]); b = np.array([r[s][1] for r in rows])
        out["atlas"][f"rank_{s}"] = [int((a > rows[0][s][0] + 1e-12).sum()) + 1, int((b > rows[0][s][1]).sum()) + 1]
    out["atlas"]["n_pass"] = sum(r["pass"] for r in rows)
    out["atlas"]["all"] = rows
    print("ATLAS prior ranks (R/risk, eval path) of 32:", {s: out["atlas"][f"rank_{s}"] for s in A_SPANS}, "v2 passes", out["atlas"]["n_pass"], flush=True)
    E.dump(out, os.path.join(ROOT, "research", "scalp", "dsx_prior.json"))
    print(f"done {time.time() - t0:.0f}s", flush=True)
    return out


def cmd_prior_check():
    """BLITZ trader's checklist: multiplier-shuffle p per span (2,000 draws), per-year table, 25K eval and slot at 1,000 lives,
    avg R per box and per point count -> research/scalp/dsx_prior_blitz_check.json"""
    TT, SP = blitz_prep()
    XS = {sp: bX(SP[sp][0]) for sp in SP}
    m = {sp: prior_mult(prior_points(XS[sp], list(FB), PRIOR_B, (0,) * 5, XS["H1"])) for sp in XS}
    out = {}
    for sp in ("H1", "H2", "R"):
        T, S = SP[sp]
        out[sp] = {"perm_p": E.placebo_p(T, S, m[sp], None, n=2000, seed=5), "ev_today": E.ev25(T, S), "ev": E.ev25(T, S, m[sp]),
                   "slot_today_1000": E.slot25(T, S, None, n=1000), "slot_1000": E.slot25(T, S, m[sp], n=1000)}
        print(sp, json.dumps(out[sp]), flush=True)
    allT = SP["R"][0] + SP["H1"][0] + SP["H2"][0]
    out["per_year"] = E.per_year(allT, np.r_[m["R"], m["H1"], m["H2"]])
    box = {}
    for f, op, thr in PRIOR_B:
        j = list(FB).index(f)
        th = float(np.nanmedian(XS["H1"][:, j])) if thr == "med" else float(thr)
        row = {}
        for sp in ("H1", "H2", "R"):
            x = XS[sp][:, j]
            hit = {">": x > th, ">=": x >= th, "<": x < th}[op]
            R = bR(SP[sp][0])
            row[sp] = [int(hit.sum()), round(float(R[hit].mean()), 3), int((~hit).sum()), round(float(R[~hit].mean()), 3)]
        box[f] = row
    out["boxes"] = box
    pts = {sp: prior_points(XS[sp], list(FB), PRIOR_B, (0,) * 5, XS["H1"]) for sp in XS}
    out["by_points"] = {sp: {int(p): [int((pts[sp] == p).sum()), round(float(bR(SP[sp][0])[pts[sp] == p].mean()), 3)] for p in range(6)
                             if (pts[sp] == p).any()} for sp in XS}
    print(json.dumps(out["per_year"]), json.dumps(out["by_points"]), flush=True)
    E.dump(out, os.path.join(ROOT, "research", "scalp", "dsx_prior_blitz_check.json"))
    return out


# ================================================================================================ run library
def _frozen_blitz():
    TT, SP = blitz_prep()
    XH, RH = bX(SP["H1"][0]), bR(SP["H1"][0])
    out = {}
    for model in ("ridge", "check"):
        Mo = fit(model, XH, RH)
        out[model] = (Mo, cuts(score_of(Mo, XH)))
    return TT, SP, out


def cmd_save():
    from tools import runlib as rl
    V2, A, M, EAB = E.atlas_libs()
    TT, SP, FZ = _frozen_blitz()
    sess = sorted(set(M.units()["sessions"]) | {d for sp in SP for d in SP[sp][1]})
    J = json.load(open(OUT_B, encoding="utf-8"))
    JA = json.load(open(OUT_A, encoding="utf-8"))
    names = {"ridge": "ridge score (6 facts, strong shrinkage)", "check": "points checklist (6 facts, H1 medians)"}
    rules = {"t3": "bottom third x0.5 / middle x1 / top third x1.5", "skip": "bottom third skipped"}
    allT = [t for t in TT[5] if t["day"] < "2026-01-01"] + [t for t in TT[1] if t["day"] >= "2026-01-01"]
    for model in ("ridge", "check"):
        Mo, c = FZ[model]
        for rule in RULES:
            sc = score_of(Mo, bX(allT))
            mm = mult_of(sc, c, rule)
            key = {(t["day"], t["entry_t"]): float(x) for t, x in zip(allT, mm)}
            fn = lambda t, key=key: key[(t["day"], t["entry_t"])]
            r, td, pl = J["rows"][model][rule], J["today"], J["placebo"][f"{model} {rule}"]
            f = lambda sp: (f"{sp if sp != 'R' else '2021-25'} R/risk {r[sp]['usd500']['r_per_risk']:+.3f} (today {td[sp]['usd500']['avg_r']:+.3f}, "
                            f"shuffled p {pl[sp]['p_r_per_risk']}), 25K 2-week pass/fail {r[sp]['ev']['p10']}/{r[sp]['ev']['f10']} "
                            f"(today {td[sp]['ev']['p10']}/{td[sp]['ev']['f10']}), slot ${r[sp]['slot']['life_pm']}/mo (today ${td[sp]['slot']['life_pm']})")
            vt = (f"BLITZ discretion score, {names[model]}, fit on 2026 H1 only, {rules[rule]}: " + "; ".join(f(sp) for sp in ("H1", "H2", "R")) +
                  ". Not better in all three spans and inside its shuffled-label controls: at chance, rejected.")
            T = E._blitz_store(TT, fn)
            rl.save(f"dsx_blitz_{model}_{rule}", f"BLITZ discretion score ({model}, {rule}) - rejected (at chance)", "risk",
                    "Owner 2026-10-30: give BLITZ good discretion - judge each trade from what is known at entry, size the good ones up and the bad ones down?",
                    params={"features": list(FB), "fit": J["rows"][model]["fit"], "cuts": c, "rule": RULES[rule]},
                    sizing={"usd_per_trade": 500.0, "x": "score tercile mult", "eval_25k": E.PICK_EZ},
                    trades=T, scored=rl.score(T, sess), status="rejected", verdict=vt,
                    notes="tools/dsx_discretion.py blitz (stored at $500 x mult a trade; 2026 1m, 2021-25 5m)",
                    writeup="discretion-score-2026-10-30", tags=["blitz", "scalp", "sizing", "discretion"])
            print("saved", f"dsx_blitz_{model}_{rule}", flush=True)
    # ATLAS
    V, U = a_units()
    sp_of = np.array([a_span(u["day"]) for u in U])
    X = np.array([[u["_f"][f] for f in FA] for u in U], float)
    R = np.array([aR(u) for u in U])
    h1 = sp_of == "H1"
    base = E.a_score(V)
    for model in ("ridge", "check"):
        Mo = fit(model, X[h1], R[h1])
        sc = score_of(Mo, X)
        c = cuts(sc[h1])
        for rule in RULES:
            rid = f"dsx_atlas_{model}_{rule}"
            m = mult_of(sc, c, rule)
            E._UM[rid] = {(u["src"], u["entry_t"]): float(x) for u, x in zip(U, m) if x != 1.0}
            o, T = E._atlas_store({**V, "um": rid})
            r, td, pl = JA["rows"][model][rule], JA["today"], JA["placebo"][f"{model} {rule}"]
            f = lambda s: (f"{s} 2-week pass/dead {r['o'][s]['p10']}/{r['o'][s]['dead10']} (today {td['o'][s]['p10']}/{td['o'][s]['dead10']}), eval paths "
                           f"${r['o'][s]['mp_net_less_fees']:,} (today ${td['o'][s]['mp_net_less_fees']:,}, shuffled p {pl[s]['p_eval_path']}), R/risk "
                           f"{r['view'][s]['r_per_risk']:+.3f} (today {r['view'][s]['avg_r']:+.3f})")
            vt = (f"ATLAS discretion score, {names[model]}, fit on 2026 H1 only, {rules[rule]}: " + "; ".join(f(s) for s in A_SPANS) +
                  f". v2 test: {'passes' if r['verdict']['pass'] else 'fails'}. At chance, rejected.")
            rl.save(rid, f"ATLAS discretion score ({model}, {rule}) - rejected (at chance)", "risk",
                    "Owner 2026-10-30: give ATLAS good discretion - judge each trade from what is known at entry, size the good ones up and the bad ones down?",
                    params={"features": list(FA), "fit": JA["rows"][model]["fit"], "cuts": c, "rule": RULES[rule]},
                    sizing={"account_b": "need size (engine/account_b.qty) x score tercile mult"}, trades=T, scored=rl.score(T, sess),
                    status="rejected", verdict=vt, notes="tools/dsx_discretion.py atlas (eval-path trades, 4 spans)",
                    writeup="discretion-score-2026-10-30", tags=["atlas", "account_b", "25k", "sizing", "discretion"])
            print("saved", rid, flush=True)
    # the trader's prior checklist (no fit; written after the first run's fact table was seen: not blind)
    P = json.load(open(os.path.join(ROOT, "research", "scalp", "dsx_prior.json"), encoding="utf-8"))
    PC = json.load(open(os.path.join(ROOT, "research", "scalp", "dsx_prior_blitz_check.json"), encoding="utf-8"))
    xh1 = bX(SP["H1"][0])
    mm = prior_mult(prior_points(bX(allT), list(FB), PRIOR_B, (0,) * 5, xh1))
    key = {(t["day"], t["entry_t"]): float(x) for t, x in zip(allT, mm)}
    pb = P["blitz"]["prior"]
    f = lambda sp: (f"{sp if sp != 'R' else '2021-25'} R/risk {pb[sp]['usd500']['r_per_risk']:+.3f} (today {pb[sp]['usd500']['avg_r']:+.3f}, multiplier-shuffle p "
                    f"{PC[sp]['perm_p']}), 25K 2-week pass/fail {PC[sp]['ev']['p10']}/{PC[sp]['ev']['f10']} (today {PC[sp]['ev_today']['p10']}/{PC[sp]['ev_today']['f10']}), "
                    f"slot ${PC[sp]['slot_1000']['life_pm']}/mo (today ${PC[sp]['slot_today_1000']['life_pm']})")
    vt = ("BLITZ trader's checklist (no fit: strong break, day already moving, not the first signal, room to the next pool, with the 15m "
          "structure; 0-1 boxes x0.5, 2-3 x1, 4-5 x1.5): " + "; ".join(f(sp) for sp in ("H1", "H2", "R")) +
          ". Better per unit of risk in every span and 6 of 7 years, but the out-of-sample shuffles reach it 10-12% of the time, the H2 2-week "
          "pass drops, and it was written after the fact table was seen (two boxes are the known later-break / trend-day facts). Thin lead, not adopted.")
    T = E._blitz_store(TT, lambda t: key[(t["day"], t["entry_t"])])
    rl.save("dsx_blitz_prior", "BLITZ trader's checklist size (no fit) - thin lead, not adopted", "risk",
            "Does a trader's written-down checklist (no fitting at all) size BLITZ better than a fitted score?",
            params={"prior": [list(x) for x in PRIOR_B], "bands": [list(x) for x in PRIOR_BANDS]}, sizing={"usd_per_trade": 500.0, "eval_25k": E.PICK_EZ},
            trades=T, scored=rl.score(T, sess), status="info", verdict=vt, notes="tools/dsx_discretion.py prior (+ research/scalp/dsx_prior_blitz_check.json)",
            writeup="discretion-score-2026-10-30", tags=["blitz", "scalp", "sizing", "discretion"])
    print("saved dsx_blitz_prior", flush=True)
    m = prior_mult(prior_points(X, list(FA), PRIOR_A, (0,) * 5, X[h1]))
    E._UM["dsx_atlas_prior"] = {(u["src"], u["entry_t"]): float(x) for u, x in zip(U, m) if x != 1.0}
    o, T = E._atlas_store({**V, "um": "dsx_atlas_prior"})
    pa = P["atlas"]
    vt = ("ATLAS trader's checklist (no fit: tight stop in ATR, a moving market, room to the next pool, with the 15m structure, not after a "
          "loss today): " + "; ".join(f"{s} 2-week pass/dead {o[s]['p10']}/{o[s]['dead10']} (today {base[s]['p10']}/{base[s]['dead10']}), eval paths "
                                      f"${o[s]['mp_net_less_fees']:,} (today ${base[s]['mp_net_less_fees']:,})" for s in A_SPANS) +
          f". Rank among the 32 sign choices of the same boxes (R per risk): {[pa['rank_' + s][0] for s in A_SPANS]}; v2 test fails. At chance, rejected.")
    rl.save("dsx_atlas_prior", "ATLAS trader's checklist size (no fit) - rejected (at chance)", "risk",
            "Does a trader's written-down checklist (no fitting at all) size ATLAS better?",
            params={"prior": [list(x) for x in PRIOR_A], "bands": [list(x) for x in PRIOR_BANDS]}, sizing={"account_b": "need size x checklist mult"},
            trades=T, scored=rl.score(T, sess), status="rejected", verdict=vt, notes="tools/dsx_discretion.py prior",
            writeup="discretion-score-2026-10-30", tags=["atlas", "account_b", "25k", "sizing", "discretion"])
    print("saved dsx_atlas_prior", flush=True)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "blitz"
    if cmd == "extra_atlas" and len(sys.argv) > 2:          # e.g. extra_atlas 60 ridge 11 -> research/second/dsx_atlas_extra_ridge60.json
        cmd_extra_atlas(int(sys.argv[2]), (sys.argv[3],), int(sys.argv[4]), f"_{sys.argv[3]}{sys.argv[2]}")
    else:
        {"blitz": cmd_blitz, "atlas": cmd_atlas, "extra_blitz": cmd_extra_blitz, "extra_atlas": cmd_extra_atlas, "prior": cmd_prior, "prior_check": cmd_prior_check, "save": cmd_save}[cmd]()
