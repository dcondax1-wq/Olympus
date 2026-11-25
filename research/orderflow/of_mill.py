"""Order-flow idea mill (day-ofmax 2026-11-25): research/orderflow/DESIGN2.md (frozen, commit 88bab8cea), 49 features x
{LIT, ATLAS, LVL} x {hi, lo} = 294 variants through 4 gates (Discovery + BH-FDR, Holdout, Deflated Sharpe, 20 forward days).
Paper research only: nothing here trades, arms or edits a live setting.

    python -X utf8 research/orderflow/of_mill.py [--src DIR] [--out-dir DIR]     (normally run by of_battery.py at each look)
    python -X utf8 research/orderflow/of_mill.py --selftest                       (synthetic days: a planted signal must pass,
                                                                                   random features must not)
Hook for research/ideamill: candidates(D, days, H, lit, atlas) -> rows {"id", "family", "entry", "feature", "side", "trades"}.
"""
from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import math
import os
import statistics
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
TICK = 0.25
FLOOR, N_PLACEBO, FDR_Q, DSR_MIN, FWD_DAYS = 8, 1000, 0.10, 0.95, 20
DEPTH_MIN_DAYS = 40
FEATURES = (["A%d" % i for i in range(1, 7)] + ["B%d" % i for i in range(1, 12)] + ["C%d" % i for i in range(1, 7)]
            + ["D1", "D2"] + ["E%d" % i for i in range(1, 5)] + ["F%d" % i for i in range(1, 5)]
            + ["G%d" % i for i in range(1, 9)] + ["H%d" % i for i in range(1, 9)])
assert len(FEATURES) == 49          # DESIGN2.md table (erratum: 49, not 48)


def _mod(path, name):
    sp = importlib.util.spec_from_file_location(name, os.path.join(HERE, path))
    m = importlib.util.module_from_spec(sp); sp.loader.exec_module(m)
    return m


B = _mod("of_battery.py", "of_battery_m")       # Day, levels, lit_trades, atlas_md, halves, S (of_study: _sim_df)
NORM = statistics.NormalDist()


# ------------------------------------------------------------------------------------------------ per-bar footprint stats
def bar_stats(day):
    """One row per bar of day.bars: POC place, stacked imbalances, diagonal ratio, top/bottom delta, extreme volumes /
    two-sidedness, thin prices, OF1 zones at both extremes (all from the footprint)."""
    b = day.bars
    n = len(b)
    out = {k: np.zeros(n) for k in ("poc", "stk_b", "stk_s", "diag", "top2", "bot2", "vlo", "vhi", "unf_lo", "unf_hi",
                                    "thin", "nprice", "vz_lo", "dz_lo", "vz_hi", "dz_hi", "poc_px")}
    for i, g in day.fp_by_bar.items():
        if i >= n:
            continue
        g = g.sort_values("k")
        k = g.k.to_numpy(); a = g.a.to_numpy(float); bb = g.b.to_numpy(float); u = g.u.to_numpy(float)
        v = a + bb + u
        kmax = int(round((b.at[i, "high"] - b.at[i, "low"]) / TICK))
        full_a = np.zeros(kmax + 1); full_b = np.zeros(kmax + 1)
        ok = (k >= 0) & (k <= kmax)
        full_a[k[ok]] += a[ok]; full_b[k[ok]] += bb[ok]
        pk = int(k[np.argmax(v)])
        out["poc"][i] = (pk / kmax) * 2 - 1 if kmax > 0 else 0.0
        out["poc_px"][i] = b.at[i, "low"] + pk * TICK
        buy = (full_a[1:] >= 3 * np.maximum(full_b[:-1], 1)) & (full_a[1:] > 0)        # ask(p) vs bid(p - 1)
        sell = (full_b[:-1] >= 3 * np.maximum(full_a[1:], 1)) & (full_b[:-1] > 0)       # bid(p) vs ask(p + 1)
        out["stk_b"][i] = _runs(buy); out["stk_s"][i] = _runs(sell)
        out["diag"][i] = float(np.mean(np.log((full_a[1:] + 1) / (full_b[:-1] + 1)))) if kmax > 0 else 0.0
        out["top2"][i] = float((full_a[-2:] - full_b[-2:]).sum()); out["bot2"][i] = float((full_a[:2] - full_b[:2]).sum())
        out["vlo"][i] = full_a[0] + full_b[0]; out["vhi"][i] = full_a[-1] + full_b[-1]
        out["unf_lo"][i] = float(full_a[0] > 0 and full_b[0] > 0); out["unf_hi"][i] = float(full_a[-1] > 0 and full_b[-1] > 0)
        tot = v.sum()
        out["thin"][i] = float((v <= 0.01 * tot).sum()); out["nprice"][i] = float(len(v))
        lo = g[g.k <= 8]; hi = g[g.k >= kmax - 8]
        out["vz_lo"][i] = float((lo.a + lo.b + lo.u).sum()); out["dz_lo"][i] = float((lo.a - lo.b).sum())
        out["vz_hi"][i] = float((hi.a + hi.b + hi.u).sum()); out["dz_hi"][i] = float((hi.a - hi.b).sum())
    return pd.DataFrame(out)


def _runs(mask) -> int:
    n, run = 0, 0
    for x in mask:
        run = run + 1 if x else 0
        if run == 3:
            n += 1
    return n


class Ctx:
    """Everything the 48 features read for one day (built once)."""
    def __init__(self, day, prev_day=None):
        self.d = day
        b = day.bars
        self.b = b
        self.fs = bar_stats(day)
        self.vol = b.volume.to_numpy(float)
        self.dl = b.delta.to_numpy(float)
        self.c = b.close.to_numpy(float); self.o = b.open.to_numpy(float)
        self.h = b.high.to_numpy(float); self.l = b.low.to_numpy(float)
        self.mod = b["mod"].to_numpy()
        self.rng = self.h - self.l
        self.atr5 = pd.Series(self.rng).rolling(20, min_periods=5).mean().shift(1).to_numpy()
        self.medv = pd.Series(self.vol).rolling(20, min_periods=5).median().shift(1).to_numpy()
        eff = np.where(self.rng > 0, self.vol / np.maximum(self.rng, TICK), np.nan)
        self.meff = pd.Series(eff).rolling(20, min_periods=5).median().shift(1).to_numpy()
        self.eff = eff
        rth = (self.mod >= 570) & (self.mod < 960)
        self.rth = rth
        self.cvd_rth = np.where(rth, np.cumsum(np.where(rth, self.dl, 0.0)), np.nan)
        self.cvd = np.cumsum(self.dl)
        g = lambda c: pd.to_numeric(b[c], errors="coerce").fillna(0).to_numpy(float) if c in b else np.zeros(len(b))
        self.b10, self.b20, self.b50, self.bth = g("b10"), g("b20"), g("b50"), g("bth")
        self.dep = None
        if getattr(day, "depth", None) is not None and len(day.depth):
            self.dep = day.depth.set_index("t")
        bv = b.buy.to_numpy(float); sv = b.sell.to_numpy(float)
        mid = (self.h + self.l) / 2
        cb, cs = np.cumsum(np.where(rth, bv * mid, 0)), np.cumsum(np.where(rth, sv * mid, 0))
        nb, ns = np.cumsum(np.where(rth, bv, 0)), np.cumsum(np.where(rth, sv, 0))
        self.vwap_gap = np.where((nb > 0) & (ns > 0), (cb / np.maximum(nb, 1) - cs / np.maximum(ns, 1)) / TICK, 0.0)
        on = (self.mod < 570) | (self.mod >= 1080)
        self.on_cvd = float(self.dl[on & (self.mod < 570)].sum()) / max(1.0, float(self.vol[on & (self.mod < 570)].sum()))
        self.mean_dl = np.cumsum(self.dl) / np.arange(1, len(self.dl) + 1)
        self.day_vol_mean = float(self.vol.mean()) if len(self.vol) else 1.0


def _s(x, n):
    return float(np.nansum(x)) if n > 0 else 0.0


def features(cx: Ctx, i: int, d: int, ext_i: int | None = None, level: float | None = None) -> dict:
    """The 48 signed features for an entry at bar i (decision uses bars < i). NaN = not computable."""
    f = {k: np.nan for k in FEATURES}
    if i < 7:
        return f
    k1 = i - 1
    V = cx.vol; D = cx.dl; fs = cx.fs
    w3, w6, w12 = slice(i - 3, i), slice(i - 6, i), slice(max(0, i - 12), i)
    sv3, sv6 = max(1.0, V[w3].sum()), max(1.0, V[w6].sum())
    f["A1"] = d * D[k1] / max(1.0, V[k1])
    f["A2"] = d * D[w3].sum() / sv3
    f["A3"] = d * D[w6].sum() / sv6
    f["A4"] = d * float(np.nansum(D[w12] * cx.rth[w12])) / max(1.0, V[w12].sum()) if cx.mod[k1] >= 630 else 0.0
    pm = cx.c[k1] - cx.c[i - 6]
    f["A5"] = 1.0 if (d * D[w6].sum() > 0 and d * pm < 0) else (-1.0 if (d * D[w6].sum() < 0 and d * pm > 0) else 0.0)
    H, L = cx.h[:i], cx.l[:i]
    a6 = 0.0
    if len(H) > 7:
        j = int(np.argmax(H[:-1])); jl = int(np.argmin(L[:-1]))
        if H[-1] > H[:-1].max() and k1 - j >= 6 and cx.cvd[k1] < cx.cvd[j]:
            a6 = -1.0                                           # bearish divergence
        elif L[-1] < L[:-1].min() and k1 - jl >= 6 and cx.cvd[k1] > cx.cvd[jl]:
            a6 = 1.0
    f["A6"] = d * a6
    f["B1"] = d * (fs.stk_b[k1] - fs.stk_s[k1])
    f["B2"] = d * (fs.stk_b[w3].sum() - fs.stk_s[w3].sum())
    f["B3"] = d * fs.diag[k1]
    f["B4"] = d * fs.poc[k1]
    f["B5"] = d * (fs.poc_px[k1] - fs.poc_px[i - 6]) / cx.atr5[i] if cx.atr5[i] and np.isfinite(cx.atr5[i]) else np.nan
    unf_against = fs.unf_lo[k1] if d == -1 else fs.unf_hi[k1]          # the extreme against a long is the low? no: a long fears the low
    unf_against = fs.unf_lo[k1] if d == 1 else fs.unf_hi[k1]
    f["B6"] = -1.0 if unf_against else 1.0
    v_ext = fs.vlo[k1] if d == 1 else fs.vhi[k1]
    f["B7"] = 1.0 if V[k1] > 0 and v_ext <= 0.02 * V[k1] else 0.0
    f["B8"] = fs.thin[w3].sum() / max(1.0, fs.nprice[w3].sum())
    f["B9"] = d * (fs.top2[k1] - fs.bot2[k1]) / max(1.0, V[k1])
    vz, dz = (fs.vz_lo[k1], fs.dz_lo[k1]) if d == 1 else (fs.vz_hi[k1], fs.dz_hi[k1])
    absorbed = vz > 0 and dz * d < 0 and abs(dz) >= 0.20 * vz
    f["B10"] = 0.0 if vz <= 0 else (1.0 if absorbed else -1.0)
    f["B11"] = (abs(dz) / vz) * (1 if absorbed else -1) if vz > 0 else 0.0
    f["C1"] = d * cx.b10[w3].sum() / sv3
    f["C2"] = d * cx.b20[w3].sum() / sv3
    f["C3"] = d * cx.b50[w3].sum() / sv3
    f["C4"] = d * cx.bth[w6].sum() / sv6
    cl = (np.abs(cx.b20[w6]) >= 0.3 * np.maximum(V[w6], 1))
    f["C5"] = d * float(np.sign(cx.b20[w6].sum())) * float(cl.sum())
    f["C6"] = float(np.abs(cx.b20[w3]).sum()) / sv3
    k2 = i - 2
    hi6, lo6 = cx.h[k2 - 6:k2].max(), cx.l[k2 - 6:k2].min()
    d1 = 0.0
    if cx.h[k2] > hi6 and D[k2] > 0 and cx.c[k1] < hi6:
        d1 = -1.0                                               # trapped buyers: favours a short
    elif cx.l[k2] < lo6 and D[k2] < 0 and cx.c[k1] > lo6:
        d1 = 1.0
    f["D1"] = d * d1
    f["D2"] = (d * -D[k2] / max(1.0, V[k2])) if d1 != 0 else 0.0
    agree = 1.0 if d * D[k1] > 0 else -1.0
    f["E1"] = (cx.eff[k1] / cx.meff[i]) * agree if np.isfinite(cx.eff[k1]) and cx.meff[i] and np.isfinite(cx.meff[i]) else np.nan
    f["E2"] = V[k1] / cx.medv[i] if cx.medv[i] and np.isfinite(cx.medv[i]) else np.nan
    f["E3"] = 1.0 if V[w3].sum() < 0.7 * V[i - 6:i - 3].sum() and d * (cx.c[k1] - cx.c[i - 4]) < 0 else 0.0
    moved = abs(cx.c[k1] - cx.o[i - 3]) / TICK
    f["E4"] = d * D[w3].sum() / max(1.0, moved)
    ref = level if level is not None else (cx.l[ext_i] if (ext_i is not None and d == 1) else (cx.h[ext_i] if ext_i is not None else None))
    if ref is not None:
        g = cx.d.fp
        lows = cx.b.low.to_numpy()
        px = lows[g.bar.to_numpy()] + g.k.to_numpy() * TICK
        m = (np.abs(px - ref) <= 2 * TICK) & (g.bar.to_numpy() < i)
        f["F1"] = float((g.a + g.b + g.u).to_numpy()[m].sum()) / max(1.0, cx.day_vol_mean)
    if ext_i is not None and 0 <= ext_i < i:
        vz2, dz2 = (fs.vz_lo[ext_i], fs.dz_lo[ext_i]) if d == 1 else (fs.vz_hi[ext_i], fs.dz_hi[ext_i])
        f["F2"] = -d * dz2 / vz2 if vz2 > 0 else 0.0           # sellers hitting into a long's low = + (absorbed)
    seg = cx.l[w12] if d == 1 else cx.h[w12]
    f["F3"] = float(len(seg) - 1 - (np.argmin(seg) if d == 1 else np.argmax(seg)))
    f["F4"] = d * cx.vwap_gap[k1]
    if cx.dep is not None:
        t = cx.b.t.to_numpy()
        rows = [cx.dep.loc[t[j]] if t[j] in cx.dep.index else None for j in range(i - 4, i)]
        if rows[-1] is not None:
            r1 = rows[-1]
            f["G1"] = d * float(r1["imb"])
            ok3 = [r for r in rows[-3:] if r is not None]
            f["G2"] = d * float(np.mean([r["imb"] for r in ok3]))
            if rows[0] is not None:
                a0, a1 = rows[0]["bid5"] - rows[0]["ask5"], r1["bid5"] - r1["ask5"]
                f["G3"] = d * float(a1 - a0) / max(1.0, float(r1["bid5"] + r1["ask5"]) / 2)
            pb, pa = sum(r["pull_b"] for r in ok3), sum(r["pull_a"] for r in ok3)
            sb, sa = sum(r["stack_b"] for r in ok3), sum(r["stack_a"] for r in ok3)
            f["G4"] = float(pa - pb) if d == 1 else float(pb - pa)
            f["G5"] = float(sb - sa) if d == 1 else float(sa - sb)
            f["G6"] = d * math.log((float(r1["bmax"]) + 1) / (float(r1["amax"]) + 1))
            shown = float(r1["bmax"] if d == 1 else r1["amax"])
            f["G7"] = 1.0 if shown > 0 and v_ext / shown > 2 else 0.0
            f["G8"] = float(r1["spread"]) if np.isfinite(r1["spread"]) else np.nan
    hist = cx.cvd[max(0, k1 - 19):k1 + 1]
    f["H1"] = d * (cx.cvd[k1] - hist.mean()) / hist.std() if len(hist) > 5 and hist.std() > 0 else 0.0
    f["H2"] = d * float(np.sign(cx.cvd_rth[k1])) if np.isfinite(cx.cvd_rth[k1]) else 0.0
    f["H3"] = d * cx.on_cvd
    op = (cx.mod >= 570) & (cx.mod < 600)
    f["H4"] = d * D[:i][op[:i]].sum() / max(1.0, V[:i][op[:i]].sum()) if cx.mod[k1] >= 600 else 0.0
    h5 = 0.0
    if len(H) > 2:
        if cx.cvd[k1] >= cx.cvd[:k1].max() and cx.h[k1] < H[:-1].max():
            h5 = 1.0                                            # CVD new high, price not: buyers absorbed -> bearish
        elif cx.cvd[k1] <= cx.cvd[:k1].min() and cx.l[k1] > L[:-1].min():
            h5 = -1.0
    f["H5"] = -d * h5
    f["H6"] = d * cx.b20[:i].sum() / max(1.0, V[:i].sum())
    ab = (np.abs(D[:i]) > 0.3 * V[:i]) & (np.abs(cx.c[:i] - cx.o[:i]) < 0.25 * np.maximum(cx.rng[:i], TICK))
    f["H7"] = d * float(np.sign(D[:i][ab].sum())) * float(ab.sum()) if ab.any() else 0.0
    f["H8"] = d * (D[k1] - cx.mean_dl[k1]) / max(1.0, V[k1])
    return f


# ------------------------------------------------------------------------------------------------ entries
def entry_rows(D, days, lit, atlas):
    """[(family, day, i, d, pnl, alt_or_flip, ext_i, level)] for the 3 entry families."""
    rows = []
    for t in lit or []:
        ed = B.et_day(t["te"])
        if ed in D and int(t["tn"]) in D[ed].row_of_t and int(t["te"]) in D[ed].row_of_t:
            rows.append(("LIT", ed, D[ed].row_of_t[int(t["tn"])], t["dir"], t["pnl"], None, D[ed].row_of_t[int(t["te"])], None))
    for u in atlas or []:
        ed = B.et_day(u["entry_t"])
        if ed in D and int(u["entry_t"]) in D[ed].row_of_t:
            i = D[ed].row_of_t[int(u["entry_t"])]
            if i >= 6:
                b = D[ed].bars
                w = b.iloc[i - 6:i]
                j = int(w.low.idxmin() if u["dir"] == 1 else w.high.idxmax())
                rows.append(("ATLAS", ed, i, u["dir"], u["pnl"], None, j, None))
    for k, d in enumerate(days):
        rth = D[d].rth()
        if len(rth) < 60:
            continue
        L = B.levels(D, days, k)
        orb = rth[(rth["mod"] >= 570) & (rth["mod"] < 600)]
        if len(orb):
            L = L + [("orh", float(orb.high.max()), 1), ("orl", float(orb.low.min()), -1)]
        used = set()
        for j in range(len(rth) - 1):
            if not (585 <= rth.at[j, "mod"] <= 900):
                continue
            for nm, lv, side in L:
                if nm in used or (nm.startswith("or") and rth.at[j, "mod"] < 600):
                    continue
                h, l, c = rth.at[j, "high"], rth.at[j, "low"], rth.at[j, "close"]
                if side == 1 and h >= lv + TICK and c < lv:
                    dd = -1
                elif side == -1 and l <= lv - TICK and c > lv:
                    dd = 1
                else:
                    continue
                used.add(nm)
                pnl, flip = B.S._sim_df(rth, j, dd), B.S._sim_df(rth, j, -dd)
                if pnl is None:
                    continue
                i = D[d].row_of_t.get(int(rth.at[j + 1, "t"]))
                if i is not None:
                    rows.append(("LVL", d, i, dd, pnl, flip if flip is not None else 0.0, D[d].row_of_t.get(int(rth.at[j, "t"])), lv))
    return rows


# ------------------------------------------------------------------------------------------------ gates
def bh(pvals, q=FDR_Q):
    """Benjamini-Hochberg: which p-values are discoveries at FDR q."""
    p = np.array(pvals, float)
    n = len(p)
    if n == 0:
        return np.zeros(0, bool)
    order = np.argsort(p)
    thr = q * (np.arange(1, n + 1) / n)
    ok = p[order] <= thr
    k = np.max(np.where(ok)[0]) + 1 if ok.any() else 0
    out = np.zeros(n, bool)
    out[order[:k]] = True
    return out


def dsr(daily, n_trials, sr_var):
    """Deflated Sharpe ratio (Bailey & Lopez de Prado 2014) of a daily P&L series."""
    x = np.asarray(daily, float)
    T = len(x)
    if T < 10 or x.std(ddof=1) == 0 or n_trials < 1:
        return 0.0
    sr = x.mean() / x.std(ddof=1)
    sk = float(pd.Series(x).skew()); ku = float(pd.Series(x).kurt()) + 3.0
    g = 0.5772156649
    n = max(2, n_trials)
    sr0 = math.sqrt(max(sr_var, 1e-12)) * ((1 - g) * NORM.inv_cdf(1 - 1.0 / n) + g * NORM.inv_cdf(1 - 1.0 / (n * math.e)))
    den = 1 - sk * sr + (ku - 1) / 4.0 * sr * sr
    if den <= 0:
        return 0.0
    return float(NORM.cdf((sr - sr0) * math.sqrt(T - 1) / math.sqrt(den)))


def run(D, days, H, lit, atlas, rng=None, look_day=None, prior=None):
    """All variants through the 4 gates. Returns {"variants": [...], "counts": {...}, "candidates": [...]}."""
    rng = rng or np.random.default_rng(20261125)
    ctx, prev = {}, None
    for d in days:
        ctx[d] = Ctx(D[d], prev)
        prev = D[d]
    rows = entry_rows(D, days, lit, atlas)
    F = [features(ctx[r[1]], r[2], r[3], r[6], r[7]) for r in rows]
    depth_days = sum(1 for d in days if getattr(D[d], "depth", None) is not None and len(D[d].depth))
    disc, hold = set(H["Discovery"]), set(H["Confirm"])
    variants = []
    for fam in ("LIT", "ATLAS", "LVL"):
        idx = [k for k, r in enumerate(rows) if r[0] == fam]
        if not idx:
            continue
        for feat in FEATURES:
            if feat.startswith("G") and depth_days < DEPTH_MIN_DAYS:
                variants.append({"id": f"{fam}.{feat}", "family": fam, "feature": feat, "state": "waiting for depth"})
                continue
            vals = np.array([F[k][feat] for k in idx], float)
            dmask = np.array([rows[k][1] in disc for k in idx])
            fin = np.isfinite(vals)
            if (fin & dmask).sum() < FLOOR:
                continue
            med = float(np.median(vals[fin & dmask]))
            for side in ("hi", "lo"):
                keep = np.where(fin, vals >= med if side == "hi" else vals <= med, fam != "LVL")
                variants.append(_score(fam, feat, side, med, idx, rows, keep, disc, hold, days, rng))
    scored = [v for v in variants if "p_disc" in v]
    disc_ok = bh([v["p_disc"] if v["gain_disc"] > 0 and v["n_disc"] >= FLOOR else 1.0 for v in scored])
    srs = [v["sr"] for v in scored if v.get("sr") is not None]
    sr_var = float(np.var(srs)) if len(srs) > 1 else 0.0
    for v, ok in zip(scored, disc_ok):
        v["g1"] = bool(ok)
        v["g2"] = bool(v["gain_hold"] > 0 and v["n_hold"] >= FLOOR and v["p_hold"] < 0.10 and
                       (v["family"] != "LVL" or ((v["pf_hold"] or 0) >= 1.15 and v["wk_hold"] >= 0.5)))
        v["dsr"] = round(dsr(v.pop("_daily"), len(scored), sr_var), 3)
        v["g3"] = v["dsr"] >= DSR_MIN
        v["state"] = "candidate: pending 20 forward days" if (v["g1"] and v["g2"] and v["g3"]) else "rejected"
    for v in scored:
        v.pop("_daily", None)
    # gate 4: a variant that was a candidate at an earlier look is checked on the days after that look
    for v in scored:
        p = (prior or {}).get(v["id"])
        if p and p.get("since"):
            fwd = [d for d in days if d > p["since"]]
            v["fwd_days"] = len(fwd)
            v["fwd_gain"] = v.get("_fwd", {}).get(p["since"]) if False else _fwd_gain(v, rows, idx_of(rows, v["family"]), fwd)
            if len(fwd) >= FWD_DAYS:
                v["g4"] = v["fwd_gain"] > 0
                v["state"] = "PASS all 4 gates: owner yes/no card" if (v["g4"] and v["g1"] and v["g2"] and v["g3"]) else "rejected (forward)"
    cands = [v for v in scored if v["state"].startswith(("candidate", "PASS"))]
    near = sorted(scored, key=lambda v: v["p_disc"])[:5]
    return {"variants": variants, "candidates": cands, "near_misses": [{k: v.get(k) for k in ("id", "gain_disc", "p_disc", "gain_hold", "p_hold", "dsr", "state")} for v in near],
            "counts": {"variants": len(variants), "scored": len(scored), "g1": int(sum(v["g1"] for v in scored)),
                       "g1g2": int(sum(v["g1"] and v["g2"] for v in scored)), "g1g2g3": len(cands),
                       "entries": {f: sum(1 for r in rows if r[0] == f) for f in ("LIT", "ATLAS", "LVL")}, "depth_days": depth_days},
            "look_day": look_day}


def idx_of(rows, fam):
    return [k for k, r in enumerate(rows) if r[0] == fam]


def _fwd_gain(v, rows, idx, fwd):
    fw = set(fwd)
    keep = v.get("_keep_all")
    if keep is None:
        return 0.0
    return float(sum((rows[k][4] if kk else 0.0) - (0.0 if rows[k][0] == "LVL" else rows[k][4]) for k, kk in zip(idx, keep) if rows[k][1] in fw))


def _score(fam, feat, side, med, idx, rows, keep, disc, hold, days, rng):
    pnl = np.array([rows[k][4] for k in idx], float)
    flip = np.array([rows[k][5] if rows[k][5] is not None else 0.0 for k in idx], float)
    day = np.array([rows[k][1] for k in idx])
    v = {"id": f"{fam}.{feat}.{side}", "family": fam, "feature": feat, "side": side, "median": round(med, 4),
         "_keep_all": [bool(x) for x in keep]}
    for nm, S_ in (("disc", disc), ("hold", hold)):
        m = np.array([x in S_ for x in day])
        p, k = pnl[m], keep[m]
        if fam == "LVL":
            gain = float(p[k].sum())
            act, alt = p[k], flip[m][k]
            if len(act):
                dr = np.array([np.where(rng.random(len(act)) < 0.5, act, alt).sum() for _ in range(N_PLACEBO)])
                pv = float((dr >= act.sum()).mean())
            else:
                pv = 1.0
            w, l = act[act > 0].sum(), -act[act <= 0].sum()
            v["pf_" + nm] = round(float(w / l), 2) if l > 0 else None
            v["wk_" + nm] = round(len(act) / max(1, len(S_)) * 5, 2)
        else:
            gain = float(-(p[~k]).sum())                       # kept - all = minus the skipped trades
            ns = int((~k).sum())
            if len(p) and 0 < ns < len(p):
                dr = np.array([-p[rng.choice(len(p), ns, replace=False)].sum() for _ in range(N_PLACEBO)])
                pv = float((dr >= gain).mean())
            else:
                pv = 1.0
        v["gain_" + nm] = round(gain)
        v["n_" + nm] = int(k.sum())
        v["p_" + nm] = round(pv, 4)
    dd = {d: 0.0 for d in days}
    for x, kk, dy in zip(pnl, keep, day):
        if kk:
            dd[dy] += x
    daily = np.array([dd[d] for d in days])
    v["_daily"] = daily
    v["sr"] = float(daily.mean() / daily.std(ddof=1)) if daily.std(ddof=1) > 0 else None
    return v


def candidates(D, days, H, lit, atlas):
    """The ideamill hook (DESIGN2.md): one row per variant with every trade's P&L, its no-rule twin and its coin-flip twin."""
    ctx = {d: Ctx(D[d]) for d in days}
    rows = entry_rows(D, days, lit, atlas)
    F = [features(ctx[r[1]], r[2], r[3], r[6], r[7]) for r in rows]
    out = []
    disc = set(H["Discovery"])
    for fam in ("LIT", "ATLAS", "LVL"):
        idx = idx_of(rows, fam)
        if not idx:
            continue
        for feat in FEATURES:
            vals = np.array([F[k][feat] for k in idx], float)
            fin = np.isfinite(vals) & np.array([rows[k][1] in disc for k in idx], bool)
            if fin.sum() < FLOOR:
                continue
            med = float(np.median(vals[fin]))
            for side in ("hi", "lo"):
                tr = []
                for k, x in zip(idx, vals):
                    kept = (x >= med if side == "hi" else x <= med) if np.isfinite(x) else fam != "LVL"
                    r = rows[k]
                    tr.append({"day": r[1], "pnl": float(r[4]) if kept else 0.0, "alt": 0.0 if fam == "LVL" else float(r[4]),
                               "flip": float(r[5]) if (fam == "LVL" and kept and r[5] is not None) else None})
                out.append({"id": f"{fam}.{feat}.{side}", "family": "orderflow", "entry": fam, "feature": feat, "side": side, "trades": tr})
    return out


def run_look(D, days, H, lit, atlas, out_dir, look_no, look_day):
    """Called by of_battery at each look: writes mill_results.json (+ mill_prior.json for gate 4) in out_dir."""
    prior_p = os.path.join(out_dir, "mill_prior.json")
    try:
        prior = json.load(open(prior_p, encoding="utf-8"))
    except Exception:
        prior = {}
    res = run(D, days, H, lit, atlas, look_day=look_day, prior=prior)
    for v in res["candidates"]:
        prior.setdefault(v["id"], {"since": look_day, "look": look_no})
    for v in res["variants"]:
        v.pop("_keep_all", None)
    os.makedirs(out_dir, exist_ok=True)
    json.dump(prior, open(prior_p, "w"), indent=1)
    json.dump({"look": look_no, "look_day": look_day, **res}, open(os.path.join(out_dir, "mill_results.json"), "w"), indent=1, default=str)
    return res


# ------------------------------------------------------------------------------------------------ selftest
def selftest():
    from engine import ofsum
    days = [d.strftime("%Y-%m-%d") for d in pd.bdate_range("2026-09-14", periods=44)]
    raw, metas = {}, {}
    for k, d in enumerate(days):
        x = ofsum.synth_day(d, n=100_000, seed=k)
        raw[d] = B._from_bytes(ofsum.summarize(x, d, ofsum.block_threshold(d, metas=metas)))
        metas[d] = raw[d]["meta"]
    D = {d: B.Day(d, raw[d]) for d in days}
    for d in days:
        D[d].depth = None
    H = B.halves(days)
    rng = np.random.default_rng(5)
    # planted signal: LIT-like trades that win when the last closed bar's delta agrees with them (A1), lose otherwise
    lit = []
    for d in days:
        b = D[d].bars
        for _ in range(4):
            j = int(rng.integers(10 * 12 + 10, 15 * 12)) if len(b) > 200 else 20
            j = min(j, len(b) - 1)
            dd = int(rng.choice([-1, 1]))
            a1 = dd * b.delta.iloc[j - 1] / max(1, b.volume.iloc[j - 1])
            pnl = (400 if a1 > 0 else -400) + rng.normal(0, 120)
            lit.append({"day": d, "dir": dd, "pnl": float(pnl), "te": int(b.t.iloc[j - 2]), "tn": int(b.t.iloc[j])})
    res = run(D, days, H, lit, [])
    ids = {v["id"] for v in res["candidates"]}
    planted = "LIT.A1.hi" in ids
    noise = [i for i in ids if not i.startswith("LIT.A1") and not i.startswith("LIT.A2") and not i.startswith("LIT.A3")
             and not i.startswith("LIT.H8") and not i.startswith("LIT.E4") and not i.startswith("LIT.B9")]
    ok = planted and len(noise) <= 3 and res["counts"]["scored"] > 100
    rows = candidates(D, days, H, lit, [])
    ok = ok and rows and all({"id", "entry", "feature", "side", "trades"} <= set(r) for r in rows)
    print("of_mill selftest:", "OK" if ok else "FAIL", "| planted A1 found:", planted, "| other candidates:", noise[:6],
          "| counts:", res["counts"], "| ideamill rows:", len(rows))
    return bool(ok)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    sys.exit(0 if (selftest() if a.selftest else True) else 1)
