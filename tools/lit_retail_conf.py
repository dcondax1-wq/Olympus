"""LIT + retail tools as CONFLUENCE / SIZE on the live LIT trades (owner 2026-10-21: "See if it would be good to implement
very big retail strategies like EMAs / supply and demand / support and resistance ... Even MACD. Implementing into LIT. We
still should definitely find 3 entries a week whatever we do.").

This file tests the retail tools only as a filter or a size tilt on the trades LIT already takes (run lit_live = engine/lit.py
run_x on live_model.json "lit"). New entries from retail tools are a separate study.

Features (63, each read as WITH the trade / AGAINST it / neutral), all from bars CLOSED before the entry (a 5m bar counts when
its close <= entry time, a 15m / 1h bar when its last minute closed <= entry time; checked by `lookahead`, which recomputes
every feature on data cut at the entry bar):
  EMA      9 / 21 / 50 / 200 on 5m, 15m, 1h: price side, slope (vs 3 bars ago), 9>21>50 stack, 2+ ATR on the wrong side of
           the EMA 21 ("stretched"), the 1h EMA 20 falling knife (3 ATR, research/writeups/moving-averages.md)
  MACD     12/26/9 on 5m, 15m, 1h: histogram sign, histogram turning, signal cross within 6 bars, regular divergence (MACD line
           and histogram) between the sweep extreme and the prior swing on 5m and 15m
  S/R      clusters of 2+ swing highs/lows (15m swings of 5 days, 1h swings of 10 days; prior day / week highs and lows, which LIT
           already trades, removed): sweep at S/R, S/R between entry and target (anywhere / inside 2R), S/R between stop and
           entry; round numbers (every 100 / 50 pts): sweep at a round number, a 100 inside 2R, a round number behind the stop
  S/D      supply / demand zones on 15m and 1h (1-3 small base candles, then an impulse candle >= 1.5 ATR): the sweep into a fresh
           zone, into any (fresh or tested) zone, a fresh opposing zone between entry and target
Rules per feature: skip AGAINST | half size AGAINST | x1.25 WITH | x1.5 WITH (neutral = unchanged). Two views, costs in:
  LIT size rule  the engine's trades re-sized (P&L is linear in micros; cut = int(q x m) min 1, up = int(q x m) max 40)
  eval path      live two_week sizing via tools/lit_big_ideas.run_eval_x (t["m"]: cut int(q x m) min 1, up capped by the live
                 60% room / soft daily loss / 40 micros), the same executor behind run lit_adopt_t15_be_off_eval
Judged the LIT way: pick on 2026 H1 (Jan-Jun), check on H2 (Jul-Oct); 2021-25 = reference (LIT size rule, 5m entries).
Works = LIT-rule net up in H1 AND H2, eval-path net up in H1 AND H2, eval 2-week pass minus fail not lower in either half,
2026 trades/week >= 2.9. Chance = the same count with each feature shuffled across the 2026 trades.

  python -X utf8 tools/lit_retail_conf.py feats       # features for every lit_live trade -> research/runs/_cache/litretail_*.pkl
  python -X utf8 tools/lit_retail_conf.py lookahead   # features on data cut at the entry == full-data features (30 trades)
  python -X utf8 tools/lit_retail_conf.py grid        # every test -> research/lit/retail_conf.json
  python -X utf8 tools/lit_retail_conf.py chance      # shuffled features, 20 rounds -> research/lit/retail_conf_chance.json
  python -X utf8 tools/lit_retail_conf.py save        # rl.save every variant as lit_retail_c_* (+ _eval for the top ones)
Paper only. Changes no engine file and no live setting.
"""
from __future__ import annotations

import json
import os
import pickle
import random
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import lit  # noqa: E402
from tools import lit_final as F  # noqa: E402
from tools import runlib as rl  # noqa: E402

CACHE = os.path.join(ROOT, "research", "runs", "_cache")
OUT = os.path.join(ROOT, "research", "lit", "retail_conf.json")
OUT_CH = os.path.join(ROOT, "research", "lit", "retail_conf_chance.json")
VER = "v1"
P_LIVE = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))["lit"]
TFS = {"5m": 300, "15m": 900, "1h": 3600}
EMAS = (9, 20, 21, 50, 200)
RULES = {"skip": ("skip AGAINST", 0.0, None), "half": ("half size AGAINST", 0.5, None),
         "x125": ("x1.25 WITH", None, 1.25), "x150": ("x1.5 WITH", None, 1.5)}


# ================================================================================================ indicators (causal)
def ema(x, p):
    return pd.Series(x).ewm(span=p, adjust=False).mean().values


def resample(t, o, h, l, c, sec):
    if sec == 300:
        return {"t": t, "end": t + 300, "o": o, "h": h, "l": l, "c": c, "k5_last": np.arange(len(t))}
    key = t // sec
    st = np.r_[0, np.flatnonzero(np.diff(key) != 0) + 1]
    en = np.r_[st[1:], len(t)]
    return {"t": key[st] * sec, "end": (key[st] + 1) * sec, "o": o[st], "h": np.maximum.reduceat(h, st),
            "l": np.minimum.reduceat(l, st), "c": c[en - 1], "k5_last": en - 1}


def indicators(t, o, h, l, c):
    """Every series per time frame from the 5m arrays; each value at bar j uses bars <= j only (EMA / Wilder ATR / MACD are
    recursive; swing points are kept with the bar that confirms them)."""
    t = np.asarray(t, np.int64)
    o, h, l, c = (np.asarray(a, float) for a in (o, h, l, c))
    I = {}
    for nm, sec in TFS.items():
        B = resample(t, o, h, l, c, sec)
        for p in EMAS:
            B[f"e{p}"] = ema(B["c"], p)
        B["atr"] = lit.atr(B["h"], B["l"], B["c"])
        m = ema(B["c"], 12) - ema(B["c"], 26)
        B["macd"], B["sig"] = m, ema(m, 9)
        B["hist"] = m - B["sig"]
        B["fh"], B["fl"] = lit.fractals(B["h"], B["l"], 2)
        I[nm] = B
    I["k5"] = {"t": t, "h": h, "l": l, "c": c, "o": o}
    return I


def last_closed(B, entry_t):
    return int(np.searchsorted(B["end"], entry_t, side="right")) - 1


# ================================================================================================ features
def _sgn(x):
    return 0 if not np.isfinite(x) or x == 0 else (1 if x > 0 else -1)


def _swings(B, j, lookback):
    """Prices of swing highs and lows confirmed by bar j (fractal at q confirmed at q+2), within lookback bars."""
    a = j - lookback
    hi = [float(B["h"][q]) for q in B["fh"] if a <= q and q + 2 <= j]
    lo = [float(B["l"][q]) for q in B["fl"] if a <= q and q + 2 <= j]
    return hi + lo


def _clusters(px, tol, excl):
    out = []
    px = sorted(px)
    g = []
    for p in px:
        if g and p - g[0] > tol:
            if len(g) >= 2:
                out.append(float(np.mean(g)))
            g = []
        g.append(p)
    if len(g) >= 2:
        out.append(float(np.mean(g)))
    return [L for L in out if all(abs(L - e) > tol for e in excl)]


def _zones(B, j, lookback):
    """Supply / demand zones created by bar j: 1-3 base bars (body <= 0.5 ATR) then an impulse bar (body >= 1.5 ATR) that
    closes beyond the base. Returns (side +1 demand / -1 supply, lo, hi, k5 index of the impulse bar's last 5m bar)."""
    o, h, l, c, at = B["o"], B["h"], B["l"], B["c"], B["atr"]
    out = []
    for m in range(max(4, j - lookback), j + 1):
        a = at[m - 1]
        body = c[m] - o[m]
        if abs(body) < 1.5 * a:
            continue
        base = []
        q = m - 1
        while q >= m - 3 and abs(c[q] - o[q]) <= 0.5 * a:
            base.append(q); q -= 1
        if not base:
            continue
        bl, bh = float(min(l[b] for b in base)), float(max(h[b] for b in base))
        bt, bb = float(max(max(o[b], c[b]) for b in base)), float(min(min(o[b], c[b]) for b in base))
        if body > 0 and c[m] > bh:
            out.append((1, bl, bt, int(B["k5_last"][m])))
        elif body < 0 and c[m] < bl:
            out.append((-1, bb, bh, int(B["k5_last"][m])))
    return out


def _approaches(K, side, lo, hi, a, z):
    """Touches of a zone by the 5m bars a..z (inclusive) and whether it was broken (a 5m close through the far edge).
    Returns (number of separate approaches, broken before the last approach, the last bar is inside an approach)."""
    if z < a:
        return 0, False, False
    if side == 1:
        ins = K["l"][a:z + 1] <= hi
        brk = K["c"][a:z + 1] < lo
    else:
        ins = K["h"][a:z + 1] >= lo
        brk = K["c"][a:z + 1] > hi
    starts = np.flatnonzero(ins & ~np.r_[False, ins[:-1]])
    n = len(starts)
    last_start = starts[-1] if n else len(ins)
    broken = bool(brk[:last_start].any()) if n else bool(brk.any())
    return n, broken, bool(ins[-1])


def feats(I, t, ctx_day):
    """WITH (+1) / AGAINST (-1) / neutral (0) for every feature of one trade, from the indicators I (bars closed by entry)."""
    d = int(t["dir"])
    et = int(t["entry_t"])
    K = I["k5"]
    k5 = int(np.searchsorted(K["t"] + 300, et, side="right")) - 1
    e = int(t["ext_i"])
    assert e <= k5, (t["day"], e, k5)
    ext = float(K["l"][e]) if d == 1 else float(K["h"][e])
    entry, stop, tgt, R = float(t["entry_px"]), float(t["stop_px"]), float(t["target_px"]), float(t["risk_pts"])
    f = {}
    J = {nm: last_closed(I[nm], et) for nm in TFS}
    # ---- EMA
    for nm in TFS:
        B, j = I[nm], J[nm]
        cl = B["c"][j]
        for p in (9, 21, 50, 200):
            ok = j >= (p if p < 200 else 200)
            f[f"ema_{nm}_{p}_side"] = _sgn(d * (cl - B[f"e{p}"][j])) if ok else 0
            f[f"ema_{nm}_{p}_slope"] = _sgn(d * (B[f"e{p}"][j] - B[f"e{p}"][j - 3])) if ok else 0
        s1, s2 = d * (B["e9"][j] - B["e21"][j]), d * (B["e21"][j] - B["e50"][j])
        f[f"ema_{nm}_stack"] = 1 if (s1 > 0 and s2 > 0) else (-1 if (s1 < 0 and s2 < 0) else 0)
        f[f"ema_{nm}_21_stretch2"] = -1 if d * (cl - B["e21"][j]) <= -2.0 * B["atr"][j] else 1
    B, j = I["1h"], J["1h"]
    f["ema_1h_20_knife3"] = -1 if d * (B["c"][j] - B["e20"][j]) <= -3.0 * B["atr"][j] else 1
    # ---- MACD
    for nm in TFS:
        B, j = I[nm], J[nm]
        f[f"macd_{nm}_hist"] = _sgn(d * B["hist"][j])
        f[f"macd_{nm}_turn"] = _sgn(d * (B["hist"][j] - B["hist"][j - 1]))
        s = np.sign(B["macd"][j - 6:j + 1] - B["sig"][j - 6:j + 1])
        f[f"macd_{nm}_cross6"] = 1 if (s[-1] == d and (s[:-1] == -d).any()) else (-1 if s[-1] == -d else 0)
    # regular divergence at the sweep extreme vs the prior swing (5m: 72 bars back, 15m: 32 bars back)
    for nm, lb in (("5m", 72), ("15m", 32)):
        B, j = I[nm], J[nm]
        je = int(np.searchsorted(B["t"], int(K["t"][e]), side="right")) - 1     # the bar holding the sweep extreme
        je = min(je, j)
        idx = B["fl"] if d == 1 else B["fh"]
        prev = [q for q in idx if je - lb <= q < je - 1 and q + 2 <= j]
        for lab, ser in (("line", "macd"), ("hist", "hist")):
            if not prev:
                f[f"macd_{nm}_div_{lab}"] = 0
                continue
            q = prev[-1]
            pq = float(B["l"][q]) if d == 1 else float(B["h"][q])
            new_ext = d * (pq - ext) > 0                       # lower low (long) / higher high (short)
            div = d * (B[ser][je] - B[ser][q]) > 0             # the indicator did not confirm it
            f[f"macd_{nm}_div_{lab}"] = 1 if (new_ext and div) else -1
    # ---- support / resistance (prior day / week highs and lows removed: LIT trades those already)
    tol = 0.15 * float(I["1h"]["atr"][J["1h"]])
    excl = [ctx_day.get(k) for k in ("pdh", "pdl", "pwh", "pwl") if ctx_day.get(k) is not None]
    for nm, lb in (("15m", 5 * 92), ("1h", 10 * 23)):
        lev = _clusters(_swings(I[nm], J[nm], lb), tol, excl)
        f[f"sr_{nm}_sweep"] = 1 if any(-tol <= d * (L - ext) <= 2 * tol for L in lev) else -1
        far = [L for L in lev if d * (L - entry) > 0.5 * R and d * (tgt - L) > 0]
        f[f"sr_{nm}_path"] = -1 if far else 1
        f[f"sr_{nm}_path2r"] = -1 if any(d * (L - entry) <= 2 * R for L in far) else 1
        f[f"sr_{nm}_stop"] = 1 if any(d * (entry - L) > 0 and d * (L - stop) > 0 for L in lev) else -1
    for step, rt in ((100, 10.0), (50, 5.0)):
        nr = round(ext / step) * step
        f[f"rn_{step}_sweep"] = 1 if abs(nr - ext) <= rt else -1
        lo_, hi_ = sorted((entry, stop))
        f[f"rn_{step}_stop"] = 1 if np.floor(hi_ / step) * step > lo_ else -1
    a0, a1 = sorted((entry + d * 0.5 * R, min(tgt, entry + 2 * R) if d == 1 else max(tgt, entry - 2 * R)))
    f["rn_100_path2r"] = -1 if np.floor(a1 / 100) * 100 >= a0 else 1
    # ---- supply / demand zones
    for nm, lb in (("15m", 5 * 92), ("1h", 20 * 23)):
        Z = _zones(I[nm], J[nm], lb)
        fresh = anyz = False
        block = False
        for side, lo, hi, kz in Z:
            if kz >= e:
                pass
            elif side == d:                                     # demand under a long / supply over a short
                at_zone = (ext <= hi + tol and ext >= lo - tol) if d == 1 else (ext >= lo - tol and ext <= hi + tol)
                if at_zone:
                    n, broken, inside = _approaches(K, side, lo - (tol if d == 1 else 0), hi + (tol if d == -1 else 0), kz + 1, e)
                    if not broken:
                        anyz = True
                        fresh = fresh or n <= 1
            if side == -d and kz < k5:                         # opposing fresh zone between entry and target
                near = lo if d == 1 else hi
                if d * (near - entry) > 0 and d * (tgt - near) > 0:
                    n, broken, _ = _approaches(K, side, lo, hi, kz + 1, k5)
                    if n == 0 and not broken:
                        block = True
        f[f"sd_{nm}_fresh_sweep"] = 1 if fresh else -1
        f[f"sd_{nm}_any_sweep"] = 1 if anyz else -1
        f[f"sd_{nm}_path"] = -1 if block else 1
    return f


FAMILY = {"ema": "EMA", "macd": "MACD", "sr": "support / resistance", "rn": "round numbers", "sd": "supply / demand"}


# ================================================================================================ data
def live_trades():
    return F.run(P_LIVE)


def feats_all(T=None, force=False):
    p = os.path.join(CACHE, f"litretail_{VER}_{rl._data_key().replace(':', '_')}.pkl")
    if os.path.exists(p) and not force:
        return pickle.load(open(p, "rb"))
    T = T or live_trades()
    M, _ = F.market(P_LIVE["ref"], P_LIVE.get("extra_boxes") or [])
    I = indicators(M.t, M.o, M.h, M.l, M.c)
    out = {}
    for t in T:
        out[int(t["entry_t"])] = feats(I, t, M.ctx[int(M.day_of[int(t["ext_i"])])])
    os.makedirs(CACHE, exist_ok=True)
    pickle.dump(out, open(p, "wb"))
    return out


def lookahead(n=30, seed=3):
    """Features recomputed on the 5m data cut at the entry (only bars whose close <= entry time) == full-data features."""
    T = live_trades()
    M, _ = F.market(P_LIVE["ref"], P_LIVE.get("extra_boxes") or [])
    full = feats_all(T)
    rng = random.Random(seed)
    pick = rng.sample([t for t in T if t["day"] >= "2026"], n // 2) + rng.sample([t for t in T if t["day"] < "2026"], n - n // 2)
    bad = 0
    for t in pick:
        k5 = int(np.searchsorted(M.t + 300, int(t["entry_t"]), side="right"))
        a = max(0, k5 - 60000)                                  # ~ 9 months of 5m bars: EMA 200 1h warm-up is long done
        I = indicators(M.t[a:k5], M.o[a:k5], M.h[a:k5], M.l[a:k5], M.c[a:k5])
        tt = {**t, "ext_i": int(t["ext_i"]) - a}
        g = feats(I, tt, M.ctx[int(M.day_of[int(t["ext_i"])])])
        diff = {k: (v, g[k]) for k, v in full[int(t["entry_t"])].items() if g[k] != v}
        if diff:
            bad += 1
            print("  DIFF", t["day"], diff, flush=True)
    print(f"look-ahead: {n - bad}/{n} trades identical on data cut at the entry", flush=True)
    return bad == 0


# ================================================================================================ scoring
def lit_rule(T, FT, fn, rule):
    _, cut, up = RULES[rule]
    out = []
    for t in T:
        v = FT[int(t["entry_t"])][fn]
        q = int(t["qty"])
        m = 1.0
        if v < 0 and cut is not None:
            m = cut
        elif v > 0 and up is not None:
            m = up
        if m <= 0:
            continue
        if m == 1.0:
            out.append(t); continue
        q2 = max(1, int(q * m + 1e-9)) if m < 1 else min(40, max(q, int(q * m + 1e-9)))
        per = float(t["pnl"]) / q
        out.append({**t, "qty": q2, "pnl": round(per * q2, 2), "risk_usd": round(float(t["risk_pts"]) * lit.PV * q2, 2),
                    "low": float(t.get("low", 0.0)) / q * q2, "mult": round(q2 / q, 3)})
    return out


def eval_units(U, FT, fn, rule):
    _, cut, up = RULES[rule]
    out = []
    for u in U:
        v = FT[u["entry_t"]][fn]
        m = cut if (v < 0 and cut is not None) else (up if (v > 0 and up is not None) else 1.0)
        if m <= 0:
            continue
        out.append({**u, "m": m} if m != 1.0 else u)
    return out


def eval_fast(U):
    """Eval path without the Monte Carlo (for the shuffles): b2b net + fresh-start 2-week pass / fail per half."""
    from tools import lit_adv_manage as A
    o = {}
    for s in ("H1", "H2"):
        Tp, _ = A.b2b(U, s)
        st = A.stats(Tp, s)
        ev = A.evals(U, s)
        o[s] = {"net": st.get("net", 0), "p10": ev["p10"], "f10": ev["f10"]}
    return o


def works(lr, ev, base_lr, base_ev):
    tpw = lr["2026"]["tpw"]
    return (tpw >= 2.9 and all(lr[s]["net"] > base_lr[s]["net"] for s in ("H1", "H2"))
            and all(ev[s]["net"] > base_ev[s]["net"] for s in ("H1", "H2"))
            and all(ev[s]["p10"] - ev[s]["f10"] >= base_ev[s]["p10"] - base_ev[s]["f10"] for s in ("H1", "H2")))


def lr_fast(T):
    o = F.score(T, spans=("H1", "H2", "2026", "2021-25"), fast=True)
    return o


def setup():
    from tools import lit_adopt_combo as AC
    from tools import lit_big_ideas as BI   # noqa: F401  (patches lit_adv_manage.run_eval with run_eval_x)
    T = live_trades()
    FT = feats_all(T)
    U = AC.units(T)
    return T, FT, U


def describe(T, FT, fn):
    """Trades / avg R / $ of WITH vs AGAINST per half (LIT size rule)."""
    o = {}
    for s, (a, z) in (("H1", F.SPAN["H1"]), ("H2", F.SPAN["H2"]), ("2021-25", F.SPAN["2021-25"])):
        for side, lab in ((1, "with"), (-1, "against")):
            X = [t for t in T if a <= t["day"] <= z and FT[int(t["entry_t"])][fn] == side]
            o[f"{s}_{lab}"] = {"n": len(X), "avg_r": round(float(np.mean([t["r"] for t in X])), 3) if X else None,
                               "net": round(sum(t["pnl"] for t in X)), "win": round(100 * np.mean([t["pnl"] > 0 for t in X]), 1) if X else None}
    return o


def grid():
    from tools import lit_big_ideas as BI
    T, FT, U = setup()
    fnames = list(next(iter(FT.values())).keys())
    base_lr = F.score(T)
    base_ev = BI.short(BI.score(U))
    res = {"base": {"lit": base_lr, "eval": base_ev}, "features": {}, "tests": {}}
    for fn in fnames:
        res["features"][fn] = describe(T, FT, fn)
        for rule in RULES:
            T2 = lit_rule(T, FT, fn, rule)
            lr = F.score(T2)
            ev = BI.short(BI.score(eval_units(U, FT, fn, rule)))
            w = works(lr, ev, base_lr, base_ev)
            res["tests"][f"{fn}|{rule}"] = {"feat": fn, "rule": rule, "lit": lr, "eval": ev, "works": w,
                                           "both_net": all(lr[s]["net"] > base_lr[s]["net"] for s in ("H1", "H2"))}
            print(f"{fn:26s} {rule:5s} LIT H1 {lr['H1']['net']:+7,} H2 {lr['H2']['net']:+7,} tpw {lr['2026']['tpw']} | eval H1 "
                  f"{ev['H1']['net']:+7,} {ev['H1']['p10']}/{ev['H1']['f10']} H2 {ev['H2']['net']:+7,} {ev['H2']['p10']}/{ev['H2']['f10']}"
                  f"{'  WORKS' if w else ''}", flush=True)
    json.dump(res, open(OUT, "w"), indent=1, default=float)
    n = len(res["tests"])
    print(f"{sum(r['works'] for r in res['tests'].values())} of {n} tests work; "
          f"{sum(r['both_net'] for r in res['tests'].values())} raise LIT net in both halves", flush=True)
    return res


def _chance_round(seed):
    T, FT, U = setup()
    fnames = list(next(iter(FT.values())).keys())
    base_lr = lr_fast(T)
    base_ev = eval_fast(U)
    rng = np.random.default_rng(seed)
    keys = [int(t["entry_t"]) for t in T if t["day"] >= "2026"]
    cnt = {"works": 0, "both_net": 0, "sign_both": 0, "n": 0, "n_feat": 0}
    for fn in fnames:
        vals = [FT[k][fn] for k in keys]
        perm = rng.permutation(vals)
        FS = {k: dict(FT[k]) for k in FT}
        for k, v in zip(keys, perm):
            FS[k][fn] = int(v)
        cnt["sign_both"] += _sign_both(T, FS, fn)
        cnt["n_feat"] += 1
        for rule in RULES:
            lr = lr_fast(lit_rule(T, FS, fn, rule))
            ev = eval_fast(eval_units(U, FS, fn, rule))
            cnt["works"] += works(lr, ev, base_lr, base_ev)
            cnt["both_net"] += all(lr[s]["net"] > base_lr[s]["net"] for s in ("H1", "H2"))
            cnt["n"] += 1
    return cnt


def _sign_both(T, FT, fn):
    """WITH trades have a higher average R than AGAINST trades in H1 and in H2 (>= 5 trades on each side in each half)."""
    ok = True
    for s in ("H1", "H2"):
        a, z = F.SPAN[s]
        w = [t["r"] for t in T if a <= t["day"] <= z and FT[int(t["entry_t"])][fn] == 1]
        g = [t["r"] for t in T if a <= t["day"] <= z and FT[int(t["entry_t"])][fn] == -1]
        if len(w) < 5 or len(g) < 5 or np.mean(w) <= np.mean(g):
            ok = False
    return int(ok)


def chance(rounds=20, procs=4):
    from multiprocessing import Pool
    with Pool(procs) as pool:
        outs = pool.map(_chance_round, list(range(100, 100 + rounds)))
    T, FT, U = setup()
    fnames = list(next(iter(FT.values())).keys())
    real = json.load(open(OUT))
    o = {"rounds": rounds, "per_round": outs,
         "mean_works": round(float(np.mean([x["works"] for x in outs])), 2),
         "mean_both_net": round(float(np.mean([x["both_net"] for x in outs])), 2),
         "mean_sign_both": round(float(np.mean([x["sign_both"] for x in outs])), 2),
         "p_works_ge_real": None,
         "real_works": sum(r["works"] for r in real["tests"].values()),
         "real_both_net": sum(r["both_net"] for r in real["tests"].values()),
         "real_sign_both": sum(_sign_both(T, FT, fn) for fn in fnames), "n_tests": len(real["tests"]), "n_features": len(fnames)}
    o["p_works_ge_real"] = round(float(np.mean([x["works"] >= o["real_works"] for x in outs])), 3)
    o["p_both_net_ge_real"] = round(float(np.mean([x["both_net"] >= o["real_both_net"] for x in outs])), 3)
    o["p_sign_ge_real"] = round(float(np.mean([x["sign_both"] >= o["real_sign_both"] for x in outs])), 3)
    json.dump(o, open(OUT_CH, "w"), indent=1, default=float)
    print(json.dumps({k: v for k, v in o.items() if k != "per_round"}), flush=True)
    return o


# ================================================================================================ follow-up (post-hoc)
def _mult_all(T, U, m_of):
    """LIT-rule trades and eval units with a per-trade multiplier m_of(entry_t) (1 = unchanged)."""
    T2 = []
    for t in T:
        m = m_of(int(t["entry_t"]))
        q = int(t["qty"])
        if m == 1.0:
            T2.append(t); continue
        q2 = max(1, int(q * m + 1e-9)) if m < 1 else min(40, max(q, int(q * m + 1e-9)))
        T2.append({**t, "qty": q2, "pnl": round(float(t["pnl"]) / q * q2, 2), "low": float(t.get("low", 0.0)) / q * q2,
                   "risk_usd": round(float(t["risk_pts"]) * lit.PV * q2, 2)})
    U2 = [{**u, "m": m_of(u["entry_t"])} for u in U]
    return T2, U2


def followup():
    """Controls (every trade x1.25 / x1.5: what up-sizing alone does) and the size-neutral tilt (x1.25 WITH, x0.75 AGAINST)
    for the features whose WITH trades beat their AGAINST trades in both halves (picked after seeing both halves = post-hoc)."""
    from tools import lit_big_ideas as BI
    T, FT, U = setup()
    res = json.load(open(OUT))
    out = {"controls": {}, "tilts": {}}
    for m in (1.25, 1.5):
        T2, U2 = _mult_all(T, U, lambda k, m=m: m)
        out["controls"][f"all_x{m}"] = {"lit": F.score(T2), "eval": BI.short(BI.score(U2))}
    cons = [fn for fn in res["features"] if _sign_both(T, FT, fn)]
    out["consistent"] = cons
    for fn in cons:
        T2, U2 = _mult_all(T, U, lambda k, fn=fn: {1: 1.25, -1: 0.75}.get(FT[k][fn], 1.0))
        lr, ev = F.score(T2), BI.short(BI.score(U2))
        out["tilts"][fn] = {"lit": lr, "eval": ev, "works": works(lr, ev, res["base"]["lit"], res["base"]["eval"])}
    for k, o in list(out["controls"].items()) + list(out["tilts"].items()):
        lr, ev = o["lit"], o["eval"]
        print(f"{k:24s} LIT H1 {lr['H1']['net']:+7,} H2 {lr['H2']['net']:+7,} 21-25 {lr['2021-25']['net']:+7,} | eval H1 {ev['H1']['net']:+7,} "
              f"{ev['H1']['p10']}/{ev['H1']['f10']} H2 {ev['H2']['net']:+7,} {ev['H2']['p10']}/{ev['H2']['f10']}"
              f"{'  WORKS' if o.get('works') else ''}", flush=True)
    res["followup"] = out
    json.dump(res, open(OUT, "w"), indent=1, default=float)
    return out


WATCH = ("ema_1h_21_side", "x150")      # the only finalist whose WITH trades are better in H1, H2 and 2021-25: watch, not adopt
FINALISTS = [("ema_1h_21_side", "x150"), ("ema_1h_21_side", "x125"), ("ema_5m_50_slope", "x150"), ("ema_15m_200_side", "x150"),
             ("ema_1h_50_slope", "x150"), ("ema_5m_200_slope", "x150")]


def perm(n=200):
    """Per finalist: the same rule on the same number of randomly chosen 2026 trades (the feature shuffled), n times. p = share
    of random picks that gain at least as much; random_works = % of random picks that pass the 'works' test too."""
    T, FT, U = setup()
    res = json.load(open(OUT))
    keys = [int(t["entry_t"]) for t in T if t["day"] >= "2026"]
    bl, be = lr_fast(T), eval_fast(U)
    out = {}
    for fn, rule in FINALISTS:
        r = res["tests"][f"{fn}|{rule}"]
        real = (r["lit"]["H1"]["net"] - bl["H1"]["net"], r["lit"]["H2"]["net"] - bl["H2"]["net"],
                r["eval"]["H1"]["net"] - be["H1"]["net"], r["eval"]["H2"]["net"] - be["H2"]["net"])
        rng = np.random.default_rng(5)
        G = []
        for _ in range(n):
            pm = rng.permutation([FT[k][fn] for k in keys])
            FS = {k: dict(FT[k]) for k in FT}
            for k, v in zip(keys, pm):
                FS[k][fn] = int(v)
            lr, ev = lr_fast(lit_rule(T, FS, fn, rule)), eval_fast(eval_units(U, FS, fn, rule))
            G.append((lr["H1"]["net"] - bl["H1"]["net"], lr["H2"]["net"] - bl["H2"]["net"], ev["H1"]["net"] - be["H1"]["net"],
                      ev["H2"]["net"] - be["H2"]["net"], works(lr, ev, bl, be)))
        G = np.array(G, float)
        p = [round(float((G[:, i] >= real[i]).mean()), 3) for i in range(4)]
        out[f"{fn}|{rule}"] = {"real_gain": [round(x) for x in real], "p_lit_h1": p[0], "p_lit_h2": p[1], "p_eval_h1": p[2],
                               "p_eval_h2": p[3], "random_works_pct": round(100 * float(G[:, 4].mean()), 1),
                               "lit_2021_25": r["lit"]["2021-25"]["net"]}
        print(fn, rule, out[f"{fn}|{rule}"], flush=True)
    res["perm"] = out
    json.dump(res, open(OUT, "w"), indent=1, default=float)
    return out


def table():
    """Markdown rows of every test (for the write-up)."""
    res = json.load(open(OUT))
    b = res["base"]
    print("| Test | Rule | 2026 trades/wk | LIT H1 net | LIT H2 net | 2021-25 net | Eval H1 net | Eval H1 2-wk pass/fail | Eval H2 net "
          "| Eval H2 2-wk pass/fail | Works |")
    print("|---|---|---:|---:|---:|---:|---:|---:|---:|---:|:-:|")
    lr, ev = b["lit"], b["eval"]
    print(f"| **live LIT (lit_live)** | - | {lr['2026']['tpw']} | {lr['H1']['net']:+,} | {lr['H2']['net']:+,} | {lr['2021-25']['net']:+,} | "
          f"{ev['H1']['net']:+,} | {ev['H1']['p10']} / {ev['H1']['f10']} | {ev['H2']['net']:+,} | {ev['H2']['p10']} / {ev['H2']['f10']} | |")
    for k, r in res["tests"].items():
        lr, ev = r["lit"], r["eval"]
        print(f"| {r['feat']} | {RULES[r['rule']][0]} | {lr['2026']['tpw']} | {lr['H1']['net']:+,} | {lr['H2']['net']:+,} | "
              f"{lr['2021-25']['net']:+,} | {ev['H1']['net']:+,} | {ev['H1']['p10']} / {ev['H1']['f10']} | {ev['H2']['net']:+,} | "
              f"{ev['H2']['p10']} / {ev['H2']['f10']} | {'yes*' if r['works'] else ''} |")


# ================================================================================================ store
def _h(s):
    return (f"n={s['n']} {s['tpw']}/wk ({s['wk2']}% wks 2+) win {s['win']}% PF {s['pf']} net {s['net']:+,} (${s['per_month']:,}/mo) "
            f"DD {s['dd']:,} eval 2wk {s['p10']}/{s['f10']} 1mo {s['p20']}/{s['f20']}")


def _he(s):
    return (f"n={s['n']} PF {s['pf']} net {s['net']:+,} (${s['per_month']:,}/mo) DD {s['dd']:,}; 2-week pass/fail {s['p10']}/{s['f10']} "
            f"(Monte Carlo {s['mc_p10']}/{s['mc_f10']}), 1 month {s['p20']}/{s['f20']}")


def save(top=6):
    from tools import lit_adv_manage as A
    from tools import lit_big_ideas as BI
    T, FT, U = setup()
    res = json.load(open(OUT))
    Q = ("Owner 2026-10-21: retail tools (EMA, MACD, support/resistance, supply/demand) as confluence / size on the LIT trades - "
         "do they make LIT better while keeping ~3 trades a week?")
    b = res["base"]

    def score_key(r):
        return min(r["eval"]["H1"]["net"] - b["eval"]["H1"]["net"], r["eval"]["H2"]["net"] - b["eval"]["H2"]["net"])
    ranked = sorted(res["tests"].values(), key=score_key, reverse=True)
    real_index, rl.index = rl.index, (lambda: None)       # rebuild the index once at the end, not after every run
    top_ids = {f"{r['feat']}|{r['rule']}" for r in ranked[:top]} | {k for k, r in res["tests"].items() if r["works"]}
    for k, r in res["tests"].items():
        fn, rule = r["feat"], r["rule"]
        nm = "lit_retail_c_" + fn + "_" + rule
        T2 = [{kk: v for kk, v in t.items() if not kk.startswith("_")} for t in lit_rule(T, FT, fn, rule)]
        o, e = r["lit"], r["eval"]
        st = "promising" if (fn, rule) == WATCH else "rejected"
        title = f"LIT + {FAMILY[fn.split('_')[0]]}: {fn} - {RULES[rule][0]}"
        verdict = (f"LIT size rule. 2026 H1 (pick) {_h(o['H1'])}; H2 (check) {_h(o['H2'])}; 2021-25 reference net {o['2021-25']['net']:+,} "
                   f"PF {o['2021-25']['pf']}. Eval path (two_week): H1 {_he(e['H1'])}; H2 {_he(e['H2'])}. "
                   + ("Passes the letter of the test (both halves up), but the same up-size on randomly chosen trades passes it 11-28% "
                      "of the time and does about as well in Jul-Oct (research/lit/retail_conf.json perm): more risk, not a better pick."
                      if r["works"] else "Does not improve both halves on LIT net, eval net and the 2-week eval."))
        rl_rec = rl.save(nm, title, "filters", Q, params={**lit.DEFAULTS, **P_LIVE, "retail_conf": {"feat": fn, "rule": rule}},
                         trades=T2, scored=rl.score(T2, F.SESS), status=st, verdict=verdict,
                         notes="tools/lit_retail_conf.py (features from bars closed before the entry; look-ahead check 30/30).",
                         writeup="lit-retail-confluence", tags=["lit", "lit_retail_c"])
        _ = rl_rec
        if k in top_ids:
            Ux = eval_units(U, FT, fn, rule)
            Tp = []
            for sp in ("H1", "H2"):
                Tp += A.b2b(Ux, sp)[0]
            for t in Tp:
                t["risk_pts"] = t["risk"]; t["r"] = round(t["pnl"] / t["risk_usd"], 3) if t["risk_usd"] else 0.0
                t.update(half=False, trigger="LIT-1m", mfe=None, mae=None, bars_held=None, regime="", mult=None, tgt_pts=t["tgt"])
            rl.save(nm + "_eval", title + " (eval path, two_week sizing)", "filters", Q,
                    params={**lit.DEFAULTS, **P_LIVE, "retail_conf": {"feat": fn, "rule": rule}}, sizing={"mode": "two_week", **A.CFG},
                    trades=Tp, scored=rl.score(Tp, A.S26), status=st,
                    verdict=f"Eval path, live two_week sizing. 2026 H1 (pick) {_he(e['H1'])}. H2 (check) {_he(e['H2'])}.",
                    notes="tools/lit_retail_conf.py: lit_live units sized by tools/lit_big_ideas.run_eval_x with the multiplier.",
                    writeup="lit-retail-confluence", tags=["lit", "lit_retail_c"])
    rl.index = real_index
    rl.index()
    print(f"saved {len(res['tests'])} runs + {len(top_ids)} eval runs", flush=True)
    _ = BI


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "grid"
    if cmd == "feats":
        FT = feats_all(force=True)
        print(len(FT), "trades,", len(next(iter(FT.values()))), "features")
    elif cmd == "lookahead":
        sys.exit(0 if lookahead() else 1)
    elif cmd == "grid":
        grid()
    elif cmd == "chance":
        chance(int(sys.argv[2]) if len(sys.argv) > 2 else 20)
    elif cmd == "followup":
        followup()
    elif cmd == "table":
        table()
    elif cmd == "perm":
        perm()
    elif cmd == "save":
        save()
