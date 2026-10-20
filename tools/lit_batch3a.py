"""LIT batch 3a (2026-10-20): 13 setup-quality ideas the earlier studies did not test, on today's LIT trades.

  1  ICT macro windows (02:33-03:00, 04:03-04:30, 08:50-09:10, 09:50-10:10, 10:50-11:10, 11:50-12:10, 13:10-13:40, 15:15-15:45)
  2  relative volume of the sweep bar (vs the same 5m slot's average over the prior 20 sessions)
  3  relative volume of the displacement bar / the displacement leg
  4  bar-delta proxy (close location x volume, from true 1m bars, summed per 5m bar) at the sweep and over the CISD leg
  5  sweep rejection: wick-to-body ratio of the extreme bar, close location, close back inside the swept level
  6  displacement speed: bars from the extreme (and from the first breach) to the 5m CISD close
  7  level age: hours since the swept level was printed
  8  level touches: how often price came within 0.1 / 0.2 ATR of the level before the sweep
  9  equal highs / lows (build-ups): as a size tilt, and as extra LIT levels (looser / longer build-up detector, engine re-run)
  10 round numbers: distance of the swept level to the nearest 00 / 50 handle (on the real contract price: the back-adjusted
     5m file is un-adjusted with data/NQ_rolls.json)
  11 level type: which class of swept level pays (session box / PDH-PDL / PWH-PWL / PMH-PML / gap / build-up), size weights
  12 consecutive-day sweeps: yesterday swept the same-name level too / had a same-side LIT setup / tested the same price
  13 level type x session matrix as size weights (fit on H1, checked on H2, coarse 0.5 / 1 / 1.5)

Every feature is known by the close of the 5m CISD bar (the setup's trigger), before the limit is placed: no look-ahead.

Judged the LIT way (CLAUDE.md): 2026 only, pick on H1 (Jan-Jun), check on H2 (Jul-Oct 16); 2021-25 is a reference line.
Two references: base = live LIT (run lit_live), all3 = the adopt-candidate combo t_check + scale_in + be_off. Two views,
costs in: eval = the real MFFU 50K eval path (engine/sizing.lit_qty two_week 10 sessions then safe_eval, no reset, $1.90,
true 1m; tools/lit_adv_manage.py + tools/lit_big_ideas.run_eval_x), lit = the LIT size rule (engine/lit.scale_trade).

Uses:
  size  a multiplier on the trade (the trade list stays identical; a cut is int(q x m) min 1, an up-size is capped by the
        live caps: 60% of the room, the $1,000 soft daily loss, 40 micros) - the scoring of tools/lit_context.py
  filt  drop the candidates that fail the condition and re-run the engine (engine/lit.run_x on the kept candidates: a skipped
        setup frees the day for a later one, exactly as a setup_ok filter would); only kept if 2026 stays >= 2.5 trades/week
  lvl   extra LIT levels (item 9): the candidates re-built with a different build-up detector, engine re-run

Adopt test (tools/lit_context.strict + neighbours + beats flat leverage): eval net up in H1 AND H2, 2-week pass not down,
2-week fail (exact and Monte Carlo) not up, LIT-rule net not down, >= 10 / 5 trades touched per half, the neighbouring
thresholds hold, and a size tilt must beat a flat multiplier equal to its mean size.

    python -X utf8 tools/lit_batch3a.py          # screen everything -> research/lit/batch3a.json
    python -X utf8 tools/lit_batch3a.py store    # rl.save runs lit_b3a_* from research/lit/batch3a.json
Paper only. Changes nothing in live_model.json.
"""
from __future__ import annotations

import bisect
import collections
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import lit  # noqa: E402
from tools import lit_adopt_combo as AC  # noqa: E402
from tools import lit_adv_manage as A  # noqa: E402
from tools import lit_big_ideas as BI  # noqa: E402  (installs run_eval_x: size multiplier + adds)
from tools import lit_context as LC  # noqa: E402
from tools import lit_final as F  # noqa: E402

OUT = os.path.join(ROOT, "research", "lit", "batch3a.json")
REFS = LC.REFS
QS = LC.QS
SHAPES = LC.SHAPES
FSHAPES = LC.FSHAPES
MACROS = [(153, 180), (243, 270), (530, 550), (590, 610), (650, 670), (710, 730), (790, 820), (915, 945)]
CLS_RANK = ["pm", "pw", "pd", "gap", "london", "asia", "ny", "pre", "x_ny", "buildup"]     # tie-break: the more major class
GROUP = {"pm": "htf", "pw": "htf", "pd": "pd", "gap": "gap", "london": "box", "asia": "box", "ny": "box", "pre": "box",
         "x_ny": "box", "buildup": "eq"}


# ================================================================================================ market data
class Mk:
    """The live LIT market (ref cisd, no extra boxes) + the arrays the features need."""

    def __init__(self):
        self.M, self.C = F.market(AC.LIVE["ref"], AC.LIVE.get("extra_boxes") or [])
        M = self.M
        self.B1, self.B5 = F.bars(M, "1m"), F.bars(M, "5m")
        self.tod = self._tod_avg(M)
        self.delta, self.dsrc = self._delta(M)
        self.adj_t, self.adj_cum = self._rolls()
        self.ncls = self._name_cls()

    @staticmethod
    def _tod_avg(M, n=20):
        """Average volume of the same 5m slot (ET minute) over the prior n sessions (min 8), per bar; nan when unknown."""
        df = pd.DataFrame({"d": M.day_of, "m": M.mod, "v": M.v})
        pv = df.pivot_table(index="d", columns="m", values="v", aggfunc="first")
        av = pv.rolling(n, min_periods=8).mean().shift(1)
        cols = {m: j for j, m in enumerate(av.columns)}
        arr = av.values
        ci = np.array([cols[m] for m in M.mod])
        ri = np.searchsorted(av.index.values, M.day_of)
        return arr[ri, ci]

    @staticmethod
    def _delta(M):
        """Bar-delta proxy per 5m bar: sum over its 1m bars of volume x ((close-low) - (high-close)) / (high-low). Bars without
        five 1m bars fall back to the 5m bar's own close location x volume. Returns (delta, source 1 = 1m / 0 = 5m)."""
        raw = pd.read_csv(os.path.join(ROOT, "data", "NQ_1m.csv"))
        raw.columns = [c.strip().lower() for c in raw.columns]
        h, l, c, v = (raw[k].values.astype(float) for k in ("high", "low", "close", "volume"))
        rng = h - l
        with np.errstate(invalid="ignore", divide="ignore"):
            clv = np.where(rng > 0, ((c - l) - (h - c)) / rng, 0.0)
        g = pd.DataFrame({"t5": raw["time"].values // 300 * 300, "d": clv * v, "v": v, "n": 1}).groupby("t5").sum()
        rng5 = M.h - M.l
        with np.errstate(invalid="ignore", divide="ignore"):
            d5 = np.where(rng5 > 0, ((M.c - M.l) - (M.h - M.c)) / rng5, 0.0) * M.v
        j = np.searchsorted(g.index.values, M.t)
        jc = np.minimum(j, len(g) - 1)
        ok = (j < len(g)) & (g.index.values[jc] == M.t) & (g["n"].values[jc] == 5)
        out = np.where(ok, g["d"].values[jc], d5)
        return out, ok.astype(int)

    @staticmethod
    def _rolls():
        """Back-adjustment offset per time: unadjusted = adjusted - sum(gaps of rolls with switch_t > t)."""
        R = json.load(open(os.path.join(ROOT, "data", "NQ_rolls.json"), encoding="utf-8"))["rolls"]
        ts = [int(r["switch_t"]) for r in R]
        gs = [float(r["gap"]) for r in R]
        cum_after = [sum(gs[i:]) for i in range(len(gs))] + [0.0]     # offset for a bar before switch i (and after i-1)
        return ts, cum_after

    def unadj(self, px, t):
        i = bisect.bisect_right(self.adj_t, int(t))
        return px - self.adj_cum[i]

    def _name_cls(self):
        out = {}
        for nm, cls in lit.SESSION_CLASS.items():
            out[nm + "_h"] = out[nm + "_l"] = cls
        for p in lit.DAILY:
            out[p + "h"] = out[p + "l"] = p
        out.update(nwog="gap", ndog="gap", bu_h="buildup", bu_l="buildup", ny8_830_h="x_ny", ny8_830_l="x_ny")
        return out


# ================================================================================================ features
def macro_in(m0, m1):
    """True when [m0, m1) ET minutes overlaps a macro window."""
    return any(m0 < b and m1 > a for a, b in MACROS)


def macro_in_w(m0, m1, pad):
    return any(m0 < b + pad and m1 > a - pad for a, b in MACROS)


def features(K: Mk, z):
    """Every batch-3a feature of one candidate (known by the close of its trigger bar z['i'])."""
    M = K.M
    d = z["dir"]
    if d == 1:
        hi_d, lo_d, c_d, o_d = M.h, M.l, M.c, M.o
    else:
        hi_d, lo_d, c_d, o_d = -M.l, -M.h, -M.c, -M.o
    ee, i, sb, k = z["ext_i"], z["i"], z["sweep_i"], z["k"]
    s = M.days[k][1]
    at = max(float(z["atr_ext"]), 1e-9)
    f = {}
    # 1 macros: the sweep extreme's 5m bar, the trigger close, (the fill is added per trade)
    f["mac_ext"] = macro_in(int(M.mod[ee]), int(M.mod[ee]) + 5)
    f["mac_trig"] = macro_in(int(M.mod[i]) + 4, int(M.mod[i]) + 6)          # the minute the 5m CISD bar closes
    f["mac_ext_w10"] = macro_in_w(int(M.mod[ee]), int(M.mod[ee]) + 5, 10)
    f["mac_trig_w10"] = macro_in_w(int(M.mod[i]) + 4, int(M.mod[i]) + 6, 10)
    f["mac_sweep"] = macro_in(int(M.mod[sb]), int(M.mod[sb]) + 5)
    # 2 / 3 relative volume
    tod = K.tod

    def rv(j):
        a = tod[j]
        return float(M.v[j] / a) if a and a == a and a > 0 else None
    f["rv_ext"] = rv(ee)
    f["rv_sweep"] = rv(sb)
    f["rv_ext3"] = (lambda a: float(M.v[ee - 1:ee + 2].sum() / a) if a == a and a > 0 else None)(float(np.nansum(tod[ee - 1:ee + 2])))
    if i > ee:
        body = (c_d[ee + 1:i + 1] - o_d[ee + 1:i + 1])
        jd = ee + 1 + int(np.argmax(body))
        f["rv_disp"] = rv(jd)
        f["rv_trig"] = rv(i)
        a = float(np.nansum(tod[ee + 1:i + 1]))
        f["rv_leg"] = float(M.v[ee + 1:i + 1].sum() / a) if a > 0 else None
        vleg = float(M.v[ee + 1:i + 1].sum())
        f["dl_cisd"] = float(d * K.delta[ee + 1:i + 1].sum() / vleg) if vleg > 0 else None
    else:
        f["rv_disp"] = f["rv_trig"] = f["rv_leg"] = f["dl_cisd"] = None
    # 4 delta proxy (direction space: + = buying for a long / selling for a short)
    f["dl_ext"] = float(d * K.delta[ee] / M.v[ee]) if M.v[ee] > 0 else None
    v3 = float(M.v[ee - 1:ee + 2].sum())
    f["dl_ext3"] = float(d * K.delta[ee - 1:ee + 2].sum() / v3) if v3 > 0 else None
    f["dl_src1m"] = int(K.dsrc[ee])
    # primary (nearest) swept level and its class
    lev = max(z["sw"].values())
    names = [nm for nm, p in z["sw"].items() if abs(p - lev) < 1e-9]
    cls_all = {K.ncls.get(nm, "other") for nm in z["sw"]}
    cls_p = [K.ncls.get(nm, "other") for nm in names]
    prim = min(cls_p, key=lambda c: CLS_RANK.index(c) if c in CLS_RANK else 99)
    f["prim_cls"] = prim
    f["prim_grp"] = GROUP.get(prim, "box")
    for c in ("pd", "pw", "pm", "gap", "asia", "london", "ny", "pre", "buildup"):
        f["sw_" + c] = c in cls_all
        f["pr_" + c] = prim == c
    f["sw_htf"] = bool(cls_all & {"pw", "pm"})
    f["sw_daily"] = bool(cls_all & {"pd", "pw", "pm"})
    f["only_box"] = cls_all <= {"asia", "london", "ny", "pre", "x_ny"}
    f["n_cls"] = len(cls_all)
    f["n_lvls"] = len(z["sw"])
    # 5 rejection of the extreme bar
    rng = float(hi_d[ee] - lo_d[ee])
    bd = abs(float(c_d[ee] - o_d[ee]))
    wick = float(min(o_d[ee], c_d[ee]) - lo_d[ee])
    f["rj_wick_body"] = wick / max(bd, lit.TICK)
    f["rj_wick_rng"] = wick / rng if rng > 0 else None
    f["rj_cloc"] = float(c_d[ee] - lo_d[ee]) / rng if rng > 0 else None
    f["rj_back"] = bool(c_d[ee] > lev)
    f["rj_back_sb"] = bool(c_d[sb] > lev)
    f["rj_bull"] = bool(c_d[ee] > o_d[ee])
    # 6 speed
    f["sp_ext"] = int(i - ee)
    f["sp_sweep"] = int(i - sb)
    # 7 / 8 age and touches of the primary level
    lvls = [x for x in M.levels(k) if (x[0] == "low") == (d == 1) and x[3] in names]
    ki = min(x[2] for x in lvls) if lvls else s - 1
    a0 = max(0, ki - 31 * 288)
    seg = np.abs(lo_d[a0:ki + 1] - lev) < 1e-6
    idx = np.flatnonzero(seg)
    jf = a0 + int(idx[-1]) if len(idx) else int(ki)
    f["age_h"] = (int(M.t[ee]) - int(M.t[jf])) / 3600.0
    f["age_found"] = bool(len(idx))
    st = jf + 3
    pre = lo_d[st:sb] - lev
    for nm_, tf in (("tc1", 0.1), ("tc2", 0.2)):
        tol = max(2.0, tf * at)
        if len(pre):
            tch = (pre <= tol) & (pre > 0)
            prev = np.r_[False, tch[:-1]]
            f[nm_] = int((tch & ~prev).sum())
        else:
            f[nm_] = 0
    # 10 round numbers (real contract price at the time of the extreme)
    px = K.unadj(lev * d, M.t[ee])
    f["rn50"] = abs(px - round(px / 50.0) * 50.0)
    f["rn100"] = abs(px - round(px / 100.0) * 100.0)
    f["rn_near50_5"] = f["rn50"] <= 5.0
    f["rn_near100_10"] = f["rn100"] <= 10.0
    # 12 consecutive-day sweeps
    if k >= 1:
        ps, pe = M.days[k - 1][1], M.days[k - 1][2]
        lp = M.levels(k - 1)
        same = [x for x in lp if x[3] in names and (x[0] == "low") == (d == 1)]
        took = False
        for side, p_, ki_, nm_, cls_ in same:
            pd_ = p_ * d
            a_ = max(ki_ + 1, ps)
            if a_ < pe and float(lo_d[a_:pe].min()) < pd_:
                took = True
        f["cn_kind"] = took
        f["cn_px"] = bool(float(lo_d[ps:pe].min()) <= lev + 0.25 * at)       # yesterday traded at / through today's level
        f["cn_px_hold"] = bool(f["cn_px"] and float(c_d[pe - 1]) > lev)
    else:
        f["cn_kind"] = f["cn_px"] = f["cn_px_hold"] = None
    # 13 session bucket of the trigger
    m = int(M.mod[i]) + 5
    f["sess"] = "lon" if m < 300 else "early" if m < 480 else "ny"
    f["cell"] = f["prim_grp"] + "|" + f["sess"]
    return f


def add_setup_flags(K: Mk, FT):
    """cn_setup: yesterday had a LIT candidate in the same direction (a same-side sweep setup)."""
    days = collections.defaultdict(set)
    for z in K.C:
        days[z["k"]].add(z["dir"])
    for z in K.C:
        FT[ckey(z)]["cn_setup"] = z["dir"] in days.get(z["k"] - 1, set())


def ckey(z):
    return (z["day"], int(z["dir"]), int(z["i"]))


def tkey(t):
    return (t["day"], int(t["dir"]), int(t["i"]))


# ================================================================================================ references
class Ref:
    def __init__(self, nm, K: Mk, FT):
        self.nm = nm
        self.K = K
        self.P = {**lit.DEFAULTS, **AC.LIVE, **REFS[nm]}
        self.T = run_c(K, K.C, self.P)
        self.U = AC.units(self.T)
        self.key = LC.trades_key(self.T)
        self.ev = LC.score_eval(self.U)
        self.lr = LC.score_lit(self.T)
        self.T26 = [t for t in self.T if t["day"] >= "2026-01-01"]
        assert len(self.T26) == len(self.U)
        self.fx = [trade_feats(K, FT, t) for t in self.T]
        self.fu = [trade_feats(K, FT, t) for t in self.T26]


def run_c(K: Mk, cands, P):
    return lit.run_x(K.M, cands, P, F.SESS, B1=K.B1 if P["tf"] == "1m" else None, B5=K.B5)


def trade_feats(K, FT, t):
    f = dict(FT[tkey(t)])
    et = pd.Timestamp(int(t["entry_t"]), unit="s", tz="UTC").tz_convert("America/New_York")
    m = et.hour * 60 + et.minute
    f["mac_fill"] = macro_in(m, m + 1)
    f["mac_fill_w10"] = macro_in_w(m, m + 1, 10)
    f["risk"] = float(t["risk_pts"])
    return f


# ================================================================================================ size tilts
CONT = ["rv_ext", "rv_sweep", "rv_ext3", "rv_disp", "rv_trig", "rv_leg", "dl_ext", "dl_ext3", "dl_cisd", "rj_wick_body",
        "rj_wick_rng", "rj_cloc", "sp_ext", "sp_sweep", "age_h", "tc1", "tc2", "rn50", "rn100", "n_cls", "n_lvls"]
FLAGS = ["mac_ext", "mac_trig", "mac_fill", "mac_sweep", "mac_ext_w10", "mac_trig_w10", "mac_fill_w10", "rj_back", "rj_back_sb",
         "rj_bull", "sw_pd", "sw_pw", "sw_pm", "sw_gap", "sw_asia", "sw_london", "sw_ny", "sw_pre", "sw_buildup", "pr_pd",
         "pr_pw", "pr_gap", "pr_asia", "pr_london", "pr_ny", "pr_pre", "pr_buildup", "sw_htf", "sw_daily", "only_box",
         "rn_near50_5", "rn_near100_10", "cn_kind", "cn_px", "cn_px_hold", "cn_setup", "eq_tc1"]
ITEM = {"mac": 1, "rv_ext": 2, "rv_sweep": 2, "rv_ext3": 2, "rv_disp": 3, "rv_trig": 3, "rv_leg": 3, "dl": 4, "rj": 5, "sp": 6,
        "age": 7, "tc": 8, "eq": 9, "sw_buildup": 9, "pr_buildup": 9, "rn": 10, "sw": 11, "pr": 11, "only": 11, "n_cls": 11,
        "n_lvls": 11, "cn": 12, "cell": 13, "cls": 11}


def item_of(feat):
    for k in sorted(ITEM, key=len, reverse=True):
        if feat.startswith(k):
            return ITEM[k]
    return 0


def fval(f, feat):
    if feat == "eq_tc1":                    # equal-ish level: a build-up, or a level tested before the sweep
        return bool(f.get("sw_buildup") or (f.get("tc1") or 0) >= 1)
    return f.get(feat)


def tilt(R: Ref, mf):
    TT = [lit.scale_trade(t, m) if (m := mf(f)) != 1.0 else t for t, f in zip(R.T, R.fx)]
    UU = [{**u, "m": mf(f)} for u, f in zip(R.U, R.fu)]
    return TT, UU


def eval_tilt(R: Ref, mf, info):
    TT, UU = tilt(R, mf)
    ms = [mf(f) for f in R.fu]
    h1 = [m for u, m in zip(R.U, ms) if u["day"] <= "2026-06-30"]
    h2 = [m for u, m in zip(R.U, ms) if u["day"] >= "2026-07-01"]
    info = {**info, "flag_h1": sum(1 for m in h1 if m != 1.0), "flag_h2": sum(1 for m in h2 if m != 1.0),
            "mean_m": round(float(np.mean(ms)), 4) if ms else 1.0, "item": item_of(info["feat"])}
    return {"info": info, "eval": LC.score_eval(UU), "lit": LC.score_lit(TT)}


def h1_vals(R, feat):
    return [float(v) for f, u in zip(R.fu, R.U) if u["day"] <= "2026-06-30" and (v := fval(f, feat)) is not None]


def size_grid(R: Ref):
    res = {}
    for feat in CONT:
        vals = h1_vals(R, feat)
        if len(vals) < 30:
            continue
        for q in QS:
            th = float(np.quantile(vals, q))
            for sn, hm, lm in SHAPES:
                mf = (lambda f, feat=feat, th=th, hm=hm, lm=lm: 1.0 if (v := fval(f, feat)) is None else (hm if v >= th else lm))
                res[f"{feat} >= q{q} ({th:.4g}) {sn}"] = eval_tilt(R, mf, {"feat": feat, "q": q, "th": th, "shape": sn})
    for fl in FLAGS:
        for sn, mm in FSHAPES:
            mf = (lambda f, fl=fl, mm=mm: mm if fval(f, fl) else 1.0)
            res[f"{fl} {sn}"] = eval_tilt(R, mf, {"feat": fl, "q": None, "th": None, "shape": sn})
    return res


# ---- items 11 / 13: fitted class weights (on H1 trades only), coarse 0.5 / 1 / 1.5
def fit_weights(R: Ref, key, min_n, delta, up=1.5, down=0.5):
    """Per-cell weight from the H1 trades' average R (LIT size rule R): >= overall + delta -> up, <= overall - delta -> down,
    cells with < min_n H1 trades stay 1.0."""
    by = collections.defaultdict(list)
    allr = []
    for t, f in zip(R.T26, R.fu):
        if t["day"] <= "2026-06-30":
            r = t["pnl"] / max(t["risk_usd"], 1e-9)
            by[f[key]].append(r)
            allr.append(r)
    mu = float(np.mean(allr))
    W = {}
    for c, rs in by.items():
        if len(rs) < min_n:
            continue
        a = float(np.mean(rs))
        W[c] = up if a >= mu + delta else down if a <= mu - delta else 1.0
    return W, {c: (len(v), round(float(np.mean(v)), 2)) for c, v in by.items()}, mu


def weight_grid(R: Ref):
    res = {}
    for key in ("prim_cls", "prim_grp", "cell"):
        for min_n in (5, 8):
            for delta in (0.25, 0.5, 0.75):
                for up, down in ((1.5, 0.5), (1.25, 0.75), (1.0, 0.5), (1.5, 1.0)):
                    W, cells, mu = fit_weights(R, key, min_n, delta, up, down)
                    if not any(w != 1.0 for w in W.values()):
                        continue
                    mf = (lambda f, W=W, key=key: W.get(f[key], 1.0))
                    lab = f"{key} weights n>={min_n} d={delta} {up}/{down}"
                    o = eval_tilt(R, mf, {"feat": "cls_" + key, "q": None, "th": None, "shape": f"{up}/{down}",
                                          "min_n": min_n, "delta": delta, "W": W, "cells": {str(c): v for c, v in cells.items()},
                                          "mu_h1": round(mu, 3)})
                    o["info"]["item"] = 13 if key == "cell" else 11
                    res[lab] = o
    return res


def weight_neighbours(res, lab, o):
    """Fitted weights: the same key and shape at the other min_n / delta settings must keep eval net up in both halves."""
    i = o["info"]
    out = []
    for lab2, o2 in res.items():
        i2 = o2["info"]
        if lab2 == lab or i2.get("feat") != i["feat"] or i2.get("shape") != i["shape"] or "delta" not in i2:
            continue
        out.append(o2["_g"]["d_net_h1"] > 0 and o2["_g"]["d_net_h2"] > 0)
    return all(out) if out else None


# ================================================================================================ filters
FILT_CONT = ["rv_ext", "rv_disp", "rv_leg", "dl_ext", "dl_cisd", "rj_wick_body", "rj_cloc", "sp_ext", "sp_sweep", "age_h",
             "tc1", "rn50"]
FILT_FLAGS = ["mac_ext", "mac_trig", "rj_back", "sw_buildup", "sw_daily", "only_box", "cn_kind", "cn_px", "cn_setup",
              "rn_near50_5"]


def eval_filter(R: Ref, keep, info):
    Cf = [z for z in R.K.C if keep(R.K.FT[ckey(z)])]
    T = run_c(R.K, Cf, R.P)
    U = AC.units(T)
    o = {"info": {**info, "item": item_of(info["feat"])}, "eval": LC.score_eval(U), "lit": LC.score_lit(T)}
    k0 = set(R.key)
    k1 = set(LC.trades_key(T))
    for sp, a, b in (("h1", "2026-01-01", "2026-06-30"), ("h2", "2026-07-01", "2026-12-31")):
        o["info"]["drop_" + sp] = sum(1 for x in k0 - k1 if a <= x[0] <= b)
        o["info"]["new_" + sp] = sum(1 for x in k1 - k0 if a <= x[0] <= b)
    o["info"]["flag_h1"] = o["info"]["drop_h1"] + o["info"]["new_h1"]
    o["info"]["flag_h2"] = o["info"]["drop_h2"] + o["info"]["new_h2"]
    n26 = o["eval"]["H1"]["n"] + o["eval"]["H2"]["n"]
    o["info"]["tpw26"] = round(n26 / (len([d for d in F.SESS if d >= "2026-01-01"]) / 5.0), 2)
    return o


def filter_grid(R: Ref):
    res = {}
    for feat in FILT_CONT:
        vals = h1_vals(R, feat)
        for q in (0.1, 0.2, 0.33):
            for side in ("drop_lo", "drop_hi"):
                th = float(np.quantile(vals, q if side == "drop_lo" else 1 - q))
                if side == "drop_lo":
                    keep = (lambda f, feat=feat, th=th: (v := fval(f, feat)) is None or v >= th)
                else:
                    keep = (lambda f, feat=feat, th=th: (v := fval(f, feat)) is None or v <= th)
                res[f"filter {feat} {side} q{q} ({th:.4g})"] = eval_filter(R, keep, {"feat": feat, "q": q, "th": th, "side": side,
                                                                                    "shape": "filter"})
    for fl in FILT_FLAGS:
        for want in (True, False):
            keep = (lambda f, fl=fl, want=want: fval(f, fl) is None or bool(fval(f, fl)) == want)
            res[f"filter {fl} == {want}"] = eval_filter(R, keep, {"feat": fl, "q": None, "th": None, "side": str(want),
                                                                  "shape": "filter"})
    return res


def filter_neighbours(res, lab, o):
    i = o["info"]
    if i.get("q") is None:
        return None
    qs = (0.1, 0.2, 0.33)
    kq = qs.index(i["q"])
    nb = [qs[j] for j in (kq - 1, kq + 1) if 0 <= j < len(qs)]
    out = [o2["_g"]["d_net_h1"] > 0 and o2["_g"]["d_net_h2"] > 0 for lab2, o2 in res.items()
           if o2["info"].get("feat") == i["feat"] and o2["info"].get("side") == i["side"] and o2["info"].get("q") in nb]
    return all(out) if out else None


# ================================================================================================ item 9b: extra levels
LVL_VARIANTS = {
    "bu tol 0.10 ATR": {"tol_atr": 0.10},
    "bu tol 0.25 ATR": {"tol_atr": 0.25},
    "bu tol 0.35 ATR": {"tol_atr": 0.35},
    "bu lookback 2 days": {"lookback": 576},
    "bu lookback 2 days, tol 0.25": {"lookback": 576, "tol_atr": 0.25},
    "bu lookback 12 h": {"lookback": 144},
    "bu min gap 6 bars": {"min_gap": 6},
    "no build-up levels": {"off": True},
}


def buildups_x(h, l, fh, fl, at, tol_atr=0.15, tol_min=1.5, lookback=288, k=2, min_gap=3):
    """lit.buildups with a configurable minimum gap between the two swings (min_gap 3 = lit.buildups)."""
    out = []
    for side, idx, arr in (("low", fl, l), ("high", fh, h)):
        recent = collections.deque()
        for j in idx:
            while recent and j - recent[0] > lookback:
                recent.popleft()
            tol = max(tol_min, tol_atr * at[j])
            for kk in reversed(recent):
                if j - kk < min_gap or abs(arr[j] - arr[kk]) > tol:
                    continue
                if side == "low":
                    lev = min(arr[j], arr[kk])
                    if l[kk + 1:j].min() > lev:
                        out.append(("low", float(lev), int(j + k))); break
                else:
                    lev = max(arr[j], arr[kk])
                    if h[kk + 1:j].max() < lev:
                        out.append(("high", float(lev), int(j + k))); break
            recent.append(j)
    out.sort(key=lambda x: x[2])
    return out


def level_grid(R: Ref, K: Mk):
    import copy
    res = {}
    M0 = K.M
    for lab, spec in LVL_VARIANTS.items():
        M = copy.copy(M0)
        if spec.get("off"):
            M.bu = []
        else:
            M.bu = buildups_x(M0.h, M0.l, M0.fh, M0.fl, M0.atr, tol_atr=spec.get("tol_atr", 0.15),
                              lookback=spec.get("lookback", 288), min_gap=spec.get("min_gap", 3))
        M._bu_known = [x[2] for x in M.bu]
        C = lit.candidates(M, ref=AC.LIVE["ref"])
        T = lit.run_x(M, C, R.P, F.SESS, B1=K.B1 if R.P["tf"] == "1m" else None, B5=K.B5)
        U = AC.units(T)
        o = {"info": {"feat": "eq_levels", "q": None, "th": None, "shape": "levels", "spec": spec, "item": 9,
                      "n_bu": len(M.bu), "n_bu0": len(M0.bu)}, "eval": LC.score_eval(U), "lit": LC.score_lit(T)}
        k0, k1 = set(R.key), set(LC.trades_key(T))
        for sp, a, b in (("h1", "2026-01-01", "2026-06-30"), ("h2", "2026-07-01", "2026-12-31")):
            o["info"]["drop_" + sp] = sum(1 for x in k0 - k1 if a <= x[0] <= b)
            o["info"]["new_" + sp] = sum(1 for x in k1 - k0 if a <= x[0] <= b)
        o["info"]["flag_h1"] = o["info"]["drop_h1"] + o["info"]["new_h1"]
        o["info"]["flag_h2"] = o["info"]["drop_h2"] + o["info"]["new_h2"]
        n26 = o["eval"]["H1"]["n"] + o["eval"]["H2"]["n"]
        o["info"]["tpw26"] = round(n26 / (len([d for d in F.SESS if d >= "2026-01-01"]) / 5.0), 2)
        res["levels: " + lab] = o
        print(f"     levels {lab:32s} bu {len(M.bu)} (live {len(M0.bu)}) new/drop {o['info']['new_h1']}/{o['info']['drop_h1']} "
              f"{o['info']['new_h2']}/{o['info']['drop_h2']} " + " | ".join(
                  f"{s} net {o['eval'][s]['net']:+,} 2w {o['eval'][s]['p10']}/{o['eval'][s]['f10']}" for s in ("H1", "H2")),
              flush=True)
    return res


# ================================================================================================ descriptive table
def describe(R: Ref):
    """Per feature: H1 / H2 average R with vs without (flags) or top vs bottom half (continuous, H1 median), LIT size rule."""
    out = {}
    rr = [t["pnl"] / max(t["risk_usd"], 1e-9) for t in R.T26]
    h = ["H1" if t["day"] <= "2026-06-30" else "H2" for t in R.T26]
    ref = [(t["pnl"] / max(t["risk_usd"], 1e-9), f) for t, f in zip(R.T, R.fx) if t["day"] < "2026-01-01"]
    for feat in CONT + FLAGS:
        if feat in CONT:
            vals = h1_vals(R, feat)
            if len(vals) < 20:
                continue
            th = float(np.median(vals))
            g = (lambda f, feat=feat, th=th: None if (v := fval(f, feat)) is None else v >= th)
        else:
            g = (lambda f, feat=feat: None if fval(f, feat) is None else bool(fval(f, feat)))
        o = {}
        for sp in ("H1", "H2"):
            a = [r for r, f, x in zip(rr, R.fu, h) if x == sp and g(f) is True]
            b = [r for r, f, x in zip(rr, R.fu, h) if x == sp and g(f) is False]
            o[sp] = (len(a), round(float(np.mean(a)), 2) if a else None, len(b), round(float(np.mean(b)), 2) if b else None)
        a = [r for r, f in ref if g(f) is True]
        b = [r for r, f in ref if g(f) is False]
        o["2021-25"] = (len(a), round(float(np.mean(a)), 2) if a else None, len(b), round(float(np.mean(b)), 2) if b else None)
        out[feat] = o
    return out


# ================================================================================================ main
def finish(R, res, grp):
    for lab, o in res.items():
        o["_g"] = LC.gains(R, o)
    for lab, o in res.items():
        if grp == "size":
            o["nb_ok"] = LC.neighbours(res, lab, o)
        elif grp == "weights":
            o["nb_ok"] = weight_neighbours(res, lab, o)
        elif grp == "filter":
            o["nb_ok"] = filter_neighbours(res, lab, o)
        else:
            o["nb_ok"] = None
        o["strict"] = LC.strict(o["_g"], o["info"])
        if grp in ("filter", "levels"):
            o["strict"] = bool(o["strict"] and o["info"]["tpw26"] >= 2.5)
        o["adopt"] = bool(o["strict"] and o["nb_ok"] is not False)
        if o["adopt"] and grp in ("size", "weights"):
            lc = LC.leverage_control(R, o["info"]["mean_m"])
            if lc is not None:
                o["lev_ctrl"] = {s: lc["eval"][s]["net"] for s in ("H1", "H2")}
                o["adopt"] = all(o["eval"][s]["net"] > lc["eval"][s]["net"] for s in ("H1", "H2"))
    n_loose = sum(1 for o in res.values() if LC.loose(o["_g"]))
    n_strict = sum(1 for o in res.values() if o["strict"])
    n_ad = sum(1 for o in res.values() if o["adopt"])
    print(f"   {grp}: {len(res)} variants, net up in both halves {n_loose}, strict {n_strict}, adopt {n_ad}", flush=True)
    top = sorted(res.items(), key=lambda kv: min(kv[1]["_g"]["d_net_h1"], kv[1]["_g"]["d_net_h2"]), reverse=True)[:12]
    for lab, o in top:
        g = o["_g"]
        print(f"     {lab[:56]:56s} dnet {g['d_net_h1']:+6,}/{g['d_net_h2']:+6,} pass {g['d_p10_h1']:+5}/{g['d_p10_h2']:+5} "
              f"fail {g['d_f10_h1']:+5}/{g['d_f10_h2']:+5} mcf {g['d_mcf_h1']:+5}/{g['d_mcf_h2']:+5} LIT {g['d_lit_h1']:+6,}/"
              f"{g['d_lit_h2']:+6,} ref {g['d_lit_ref']:+7,} n {o['info']['flag_h1']}/{o['info']['flag_h2']} "
              f"tpw {o['info'].get('tpw26', '')} strict={o['strict']} nb={o['nb_ok']} adopt={o['adopt']}", flush=True)
    for lab, o in res.items():
        if o["adopt"]:
            print(f"     ADOPT {lab}", flush=True)
    return res


def main(only=None):
    K = Mk()
    FT = {ckey(z): features(K, z) for z in K.C}
    add_setup_flags(K, FT)
    K.FT = FT
    print(f"features for {len(FT)} candidates; 1m delta on {int(K.dsrc.sum())} 5m bars", flush=True)
    out = {"_note": "eval = live two_week eval path; lit = LIT size rule; d_* = vs the reference", "refs": {}, "describe": {}}
    if only and os.path.exists(OUT):           # one reference at a time, merged into the stored screen
        out = json.load(open(OUT, encoding="utf-8"))
    for nm in REFS:
        if only and nm != only:
            continue
        R = Ref(nm, K, FT)
        out["refs"][nm] = {"eval": R.ev, "lit": R.lr}
        print(f"== reference {nm}: " + " | ".join(f"{s} net {R.ev[s]['net']:+,} PF {R.ev[s]['pf']} DD {R.ev[s]['dd']:,} "
                                                f"2w {R.ev[s]['p10']}/{R.ev[s]['f10']} mc {R.ev[s]['mc_p10']}/{R.ev[s]['mc_f10']}"
                                                for s in ("H1", "H2")), flush=True)
        out["describe"][nm] = describe(R)
        for grp, fn in (("size", size_grid), ("weights", weight_grid), ("filter", filter_grid),
                        ("levels", lambda r: level_grid(r, K))):
            res = finish(R, fn(R), grp)
            out.setdefault(nm, {})[grp] = res
        json.dump(out, open(OUT, "w"), indent=1, default=float)
    json.dump(out, open(OUT, "w"), indent=1, default=float)
    return out


# ================================================================================================ summary / chance / store
ITEM_NAME = {1: "ICT macro windows", 2: "relative volume at the sweep", 3: "displacement volume", 4: "bar-delta proxy",
             5: "sweep rejection quality", 6: "displacement speed", 7: "level age", 8: "level touches",
             9: "equal highs / lows (build-ups)", 10: "round numbers", 11: "level type", 12: "consecutive-day sweeps",
             13: "level type x session matrix"}


def best_per_item(out, nm):
    """Per item: the variant with the largest min(d_net H1, d_net H2) on the eval path (any group)."""
    best = {}
    for grp in ("size", "weights", "filter", "levels"):
        for lab, o in out[nm][grp].items():
            it = o["info"].get("item") or item_of(o["info"]["feat"])
            if not it:
                continue
            g = o["_g"]
            if o["info"].get("flag_h1", 0) == 0 and o["info"].get("flag_h2", 0) == 0:
                continue
            sc = min(g["d_net_h1"], g["d_net_h2"])
            if it not in best or sc > best[it][2]:
                best[it] = (grp, lab, sc)
    return best


def rebuild(K: Mk, R: Ref, grp, o):
    """(engine trades T, eval units U) of a stored variant."""
    i = o["info"]
    if grp == "size":
        if i["q"] is None:
            mm = float(i["shape"][1:])
            mf = (lambda f, fl=i["feat"], mm=mm: mm if fval(f, fl) else 1.0)
        else:
            sh = next(s for s in SHAPES if s[0] == i["shape"])
            mf = (lambda f, feat=i["feat"], th=i["th"], hm=sh[1], lm=sh[2]: 1.0 if (v := fval(f, feat)) is None else (hm if v >= th else lm))
        return tilt(R, mf)
    if grp == "weights":
        key = i["feat"][4:]
        W = i["W"]
        return tilt(R, lambda f, W=W, key=key: W.get(str(f[key]), W.get(f[key], 1.0)))
    if grp == "filter":
        feat = i["feat"]
        if i["q"] is None:
            want = i["side"] == "True"
            keep = (lambda f: fval(f, feat) is None or bool(fval(f, feat)) == want)
        elif i["side"] == "drop_lo":
            keep = (lambda f: (v := fval(f, feat)) is None or v >= i["th"])
        else:
            keep = (lambda f: (v := fval(f, feat)) is None or v <= i["th"])
        T = run_c(K, [z for z in K.C if keep(K.FT[ckey(z)])], R.P)
        return T, AC.units(T)
    import copy
    spec = i["spec"]
    M = copy.copy(K.M)
    M.bu = [] if spec.get("off") else buildups_x(K.M.h, K.M.l, K.M.fh, K.M.fl, K.M.atr, tol_atr=spec.get("tol_atr", 0.15),
                                                lookback=spec.get("lookback", 288), min_gap=spec.get("min_gap", 3))
    M._bu_known = [x[2] for x in M.bu]
    T = lit.run_x(M, lit.candidates(M, ref=AC.LIVE["ref"]), R.P, F.SESS, B1=K.B1, B5=K.B5)
    return T, AC.units(T)


def chance(R: Ref, o, n=100, seed=7):
    """Shuffle test for a size tilt: the trades' feature rows are permuted within each half (n times); share of shuffles whose
    eval net gain is at least the real one in BOTH halves (p), and the shuffles' median gains."""
    rng = np.random.default_rng(seed)
    g0 = o["_g"]
    i = o["info"]
    sh = None if i["q"] is None else next(s for s in SHAPES if s[0] == i["shape"])
    if i["q"] is None:
        mm = float(i["shape"][1:])
        mf = (lambda f: mm if fval(f, i["feat"]) else 1.0)
    else:
        mf = (lambda f: 1.0 if (v := fval(f, i["feat"])) is None else (sh[1] if v >= i["th"] else sh[2]))
    h1 = [j for j, u in enumerate(R.U) if u["day"] <= "2026-06-30"]
    h2 = [j for j, u in enumerate(R.U) if u["day"] >= "2026-07-01"]
    hits, d1s, d2s = 0, [], []
    for _ in range(n):
        perm = np.empty(len(R.U), int)
        perm[h1] = rng.permutation(h1)
        perm[h2] = rng.permutation(h2)
        UU = [{**u, "m": mf(R.fu[perm[j]])} for j, u in enumerate(R.U)]
        e = LC.score_eval(UU)
        d1, d2 = e["H1"]["net"] - R.ev["H1"]["net"], e["H2"]["net"] - R.ev["H2"]["net"]
        d1s.append(d1); d2s.append(d2)
        hits += d1 >= g0["d_net_h1"] and d2 >= g0["d_net_h2"]
    return {"p": round(hits / n, 3), "med_d1": float(np.median(d1s)), "med_d2": float(np.median(d2s)), "n": n}


def _he(e, s):
    x = e[s]
    return (f"n={x['n']} {x['tpw']}/wk PF {x['pf']} net {x['net']:+,} (${x['per_month']:,}/mo) DD {x['dd']:,}; 2-week pass/fail "
            f"{x['p10']}/{x['f10']} (Monte Carlo {x['mc_p10']}/{x['mc_f10']}), 1 month {x['p20']}/{x['f20']}")


def _slug(s):
    import re
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")[:56]


def store(out):
    """rl.save the best variant of every item on both references (runs lit_b3a_*), with the shuffle test on size tilts."""
    from tools import runlib as rl
    Q = ("Owner 2026-10-20 batch 3a: do ICT macros, relative volume, a delta proxy, sweep rejection, displacement speed, level "
         "age / touches, equal highs/lows, round numbers, level type, consecutive-day sweeps or a level x session matrix help LIT "
         "(size tilt, management or a filter that keeps >= 2.5 trades/week)?")
    K = Mk()
    FT = {ckey(z): features(K, z) for z in K.C}
    add_setup_flags(K, FT)
    K.FT = FT
    saved = []
    for nm in REFS:
        R = Ref(nm, K, FT)
        b = out["refs"][nm]["eval"]
        for it, (grp, lab, sc) in sorted(best_per_item(out, nm).items()):
            o = out[nm][grp][lab]
            T, U = rebuild(K, R, grp, o)
            e = LC.score_eval(U)
            assert e["H1"]["net"] == o["eval"]["H1"]["net"] and e["H2"]["net"] == o["eval"]["H2"]["net"], (nm, lab)
            if grp == "size" and it == 1 and "chance" not in o:      # per-variant shuffle (slow): the top idea only
                o["chance"] = chance(R, o)
            A._MC.clear()
            Tp = []
            for sp in ("H1", "H2"):
                Tp += A.b2b(U, sp)[0]
            for t in Tp:
                t["risk_pts"] = t["risk"]; t["r"] = round(t["pnl"] / t["risk_usd"], 3) if t["risk_usd"] else 0.0
                t.update(half=False, trigger="LIT-1m", mfe=None, mae=None, bars_held=None, regime="", mult=None, tgt_pts=t["tgt"])
            g = o["_g"]
            st = "adopt-candidate" if o["adopt"] else ("promising" if g["d_net_h1"] > 0 and g["d_net_h2"] > 0 else "rejected")
            if st == "promising" and not o["strict"]:
                st = "rejected"            # net up in both halves alone is not enough (strict test failed)
            rid = f"lit_b3a_{'' if nm == 'base' else 'all3_'}{it:02d}_{_slug(lab)}"
            P = {**lit.DEFAULTS, **AC.LIVE, **REFS[nm], "b3a": {"item": it, "group": grp, "variant": lab}}
            ch = o.get("chance")
            rl.save(rid, f"LIT {'live' if nm == 'base' else '+ all3'} + batch 3a #{it} {ITEM_NAME[it]}: {lab}",
                    "filters" if grp in ("filter", "levels") else "risk", Q, params=P, sizing={"mode": "two_week", **A.CFG},
                    trades=Tp, scored=rl.score(Tp, A.S26), status=st,
                    verdict=f"Eval path (two_week 10 sessions then safe_eval, no reset, $1.90, true 1m). H1 (pick) {_he(o['eval'], 'H1')}. "
                            f"H2 (check) {_he(o['eval'], 'H2')}. Reference {nm}: H1 net {b['H1']['net']:+,} 2-week "
                            f"{b['H1']['p10']}/{b['H1']['f10']}, H2 net {b['H2']['net']:+,} 2-week {b['H2']['p10']}/{b['H2']['f10']}. "
                            f"Change: net {g['d_net_h1']:+,} / {g['d_net_h2']:+,}, 2-week fail {g['d_f10_h1']:+} / {g['d_f10_h2']:+}, "
                            f"LIT size rule {g['d_lit_h1']:+,} / {g['d_lit_h2']:+,}, 2021-25 reference {g['d_lit_ref']:+,}. Trades "
                            f"touched {o['info']['flag_h1']}/{o['info']['flag_h2']}; strict test {o['strict']}; neighbours {o['nb_ok']}"
                            + (f"; shuffle p = {ch['p']}" if ch else "") + ".",
                    notes="tools/lit_batch3a.py (stored trades = the back-to-back eval path per half; the best variant of this item "
                          "by the smaller of the two half gains).", writeup="lit-batch3a", tags=["lit", "lit_b3a"])
            saved.append((rid, st, it, nm, lab, g, o.get("chance")))
            print("saved", rid, st, ch, flush=True)
    json.dump(out, open(OUT, "w"), indent=1, default=float)
    return saved


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "store":
        store(json.load(open(OUT, encoding="utf-8")))
    else:
        main(only=sys.argv[1] if len(sys.argv) > 1 else None)       # optional: base | all3
