"""Order-flow feature set v3 (research/orderflow/DESIGN3.md, frozen 327619a1). Paper research only: nothing here trades.

13 features in 4 groups, from the same per-5m summaries as v2 (engine/ofsum.py) plus three additive columns (bars `sac`,
depth `imb1` / `ofi` / `dep1`):
  I impact (Kyle's lambda, impact residual at the sweep, impact asymmetry), J toxicity / persistence (VPIN proxy, its change,
  trade-sign autocorrelation, persistent flow with the trade), K stop-run at the swept extreme (burst, one-sidedness,
  post-sweep flip, cascade-vs-absorb), L queue (best-queue imbalance, Cont-Kukanov-Stoikov OFI; depth days only).
features(cx, i, d, ext_i, level) -> {name: value}; cx = of_mill.Ctx (bars < i only). NaN = not computable.
    python -X utf8 research/orderflow/of_v3.py --selftest
"""
from __future__ import annotations

import math
import sys

import numpy as np
import pandas as pd

FEATURES_V3 = ["I1", "I2", "I3", "J1", "J2", "J3", "J4", "K1", "K2", "K3", "K4", "L1", "L2"]
GROUPS_V3 = {"I": ["I1", "I2", "I3"], "J": ["J1", "J2", "J3", "J4"], "K": ["K1", "K2", "K3", "K4"], "L": ["L1", "L2"]}
LAM_WIN, LAM_MIN, SIDE_MIN = 24, 12, 5


def _ols(x, y):
    """Slope of y on x (with intercept); NaN when x has no spread."""
    x = np.asarray(x, float); y = np.asarray(y, float)
    if len(x) < 2:
        return np.nan
    vx = float(((x - x.mean()) ** 2).sum())
    if vx <= 0:
        return np.nan
    return float(((x - x.mean()) * (y - y.mean())).sum() / vx)


def _prep(cx):
    """Per-day arrays v3 needs, cached on the Ctx: returns r, lam (per bar, from bars before it), lam's running median."""
    if getattr(cx, "_v3", None) is not None:
        return cx._v3
    c, dl = cx.c, cx.dl
    n = len(c)
    r = np.r_[np.nan, np.diff(c)]
    x = dl / 1000.0
    lam = np.full(n, np.nan)
    for i in range(n):
        a = max(1, i - LAM_WIN)
        if i - a >= LAM_MIN:
            lam[i] = _ols(x[a:i], r[a:i])
    med = np.full(n, np.nan)
    seen = []
    for i in range(n):
        if len(seen) >= 5:
            med[i] = float(np.median(seen))
        if np.isfinite(lam[i]):
            seen.append(lam[i])
    b = cx.b
    sac = pd.to_numeric(b["sac"], errors="coerce").to_numpy(float) if "sac" in b else np.full(n, np.nan)
    cx._v3 = {"r": r, "x": x, "lam": lam, "lam_med": med, "sac": sac}
    return cx._v3


def features(cx, i: int, d: int, ext_i: int | None = None, level: float | None = None) -> dict:
    f = {k: np.nan for k in FEATURES_V3}
    if i < 7:
        return f
    P = _prep(cx)
    V, Dl, r, x = cx.vol, cx.dl, P["r"], P["x"]
    lam = P["lam"][i]
    # I: impact
    if np.isfinite(lam) and np.isfinite(P["lam_med"][i]) and P["lam_med"][i] != 0:
        f["I1"] = lam / abs(P["lam_med"][i])
    if ext_i is not None and 0 <= ext_i < i and np.isfinite(lam):
        a = max(1, ext_i - 2)
        res = float(np.nansum(r[a:ext_i + 1]) - lam * x[a:ext_i + 1].sum())
        atr = cx.atr5[i]
        if atr and np.isfinite(atr):
            f["I2"] = -d * res / atr
    a = max(1, i - LAM_WIN)
    if i - a >= LAM_MIN and np.isfinite(lam) and lam != 0:
        xs, ys = x[a:i], r[a:i]
        up, dn = xs > 0, xs < 0
        if up.sum() >= SIDE_MIN and dn.sum() >= SIDE_MIN:
            lu, ld = _ols(xs[up], ys[up]), _ols(xs[dn], ys[dn])
            if np.isfinite(lu) and np.isfinite(ld):
                f["I3"] = d * (lu - ld) / abs(lam)
    # J: toxicity / persistence
    w12, w6, w6b = slice(i - 12, i), slice(i - 6, i), slice(i - 12, i - 6)
    tox = lambda w: float(np.abs(Dl[w]).sum()) / max(1.0, float(V[w].sum()))
    if i >= 12:
        f["J1"] = tox(w12)
        f["J2"] = tox(w6) - tox(w6b)
    s3 = P["sac"][i - 3:i]
    s3 = s3[np.isfinite(s3)]
    if len(s3):
        f["J3"] = float(s3.mean())
        f["J4"] = f["J3"] * float(np.sign(d * Dl[i - 3:i].sum()))
    # K: stop-run at the swept extreme
    if ext_i is not None and 0 <= ext_i < i:
        med = cx.medv[i]
        if med and np.isfinite(med):
            f["K1"] = V[ext_i] / med
        f["K2"] = -d * Dl[ext_i] / max(1.0, V[ext_i])
        if ext_i + 1 <= i - 1:
            w = slice(ext_i + 1, i)
            f["K3"] = d * float(Dl[w].sum()) / max(1.0, float(V[w].sum()))
        else:
            f["K3"] = 0.0
        if np.isfinite(f["K1"]):
            f["K4"] = float(np.clip(f["K2"] * f["K3"] * f["K1"], -10, 10))
    # L: queue (depth days)
    if cx.dep is not None and "imb1" in cx.dep.columns:
        t = cx.b.t.to_numpy()
        rows = [cx.dep.loc[t[j]] if t[j] in cx.dep.index else None for j in range(i - 3, i)]
        if rows[-1] is not None and np.isfinite(float(rows[-1]["imb1"])):
            f["L1"] = d * float(rows[-1]["imb1"])
        ok = [q for q in rows if q is not None]
        if ok:
            dep = float(np.mean([float(q["dep1"]) for q in ok]))
            f["L2"] = d * float(sum(float(q["ofi"]) for q in ok)) / max(1.0, 3 * dep)
    return f


def selftest() -> bool:
    import importlib.util
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    sys.path.insert(0, os.path.dirname(os.path.dirname(here)))
    sp = importlib.util.spec_from_file_location("of_mill_v3t", os.path.join(here, "of_mill.py"))
    M = importlib.util.module_from_spec(sp); sp.loader.exec_module(M)
    from engine import ofsum
    x = ofsum.synth_day("2026-11-02", n=80_000, seed=3)
    R = M.B._from_bytes(ofsum.summarize(x, "2026-11-02"))
    D = M.B.Day("2026-11-02", R)
    cx = M.Ctx(D)
    f = features(cx, 150, 1, 147)
    g = features(cx, 150, -1, 147)
    ok = all(np.isfinite(f[k]) for k in ("I1", "J1", "J2", "J3", "K1", "K2", "K3", "K4"))
    ok = ok and math.isclose(f["K2"], -g["K2"]) and math.isclose(f["J1"], g["J1"]) and np.isnan(f["L1"])
    # look-ahead: changing bar i and later must not change anything
    D.bars.loc[150:, "buy"] += 999
    D.bars["delta"] = D.bars.buy - D.bars.sell
    cx2 = M.Ctx(D)
    f2 = features(cx2, 150, 1, 147)
    ok = ok and all((np.isnan(f[k]) and np.isnan(f2[k])) or math.isclose(f[k], f2[k], rel_tol=1e-9, abs_tol=1e-12) for k in FEATURES_V3)
    print("of_v3 selftest:", "OK" if ok else "FAIL", {k: (round(v, 3) if np.isfinite(v) else None) for k, v in f.items()})
    return bool(ok)


if __name__ == "__main__":
    sys.exit(0 if selftest() else 1)
