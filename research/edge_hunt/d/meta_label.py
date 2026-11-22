"""Lane D part 1: SIMPLE meta-labeling for SIZE only (0.5x / 1x / 1.5x), strict walk-forward.

PRE-REGISTERED before any result (this file's grid is the whole list; 16 versions + controls):
  features  F6  = sweep depth / 5m ATR, minute of day, NY flag (>= 08:00), log R:R to the target, prior day's range / 10-day mean
                  range, VIX, streak (mean clipped R of the last 3 finished LIT trades, exit before this entry)
            F12 = F6 + stop / ATR, displacement, ATR regime, day range so far, prior day open->close with the trade, inducement count
  label     win = final R >= +0.5 (the 2026-10-23 meta-labeling rule, comparable)
  models    L2 logistic (lambda 10 on standardised features, Newton), depth-2 tree (min leaf 25, Laplace-smoothed leaves)
  sizing    p ranked against the TRAINING predictions: bottom third / top third ->
              A 0.5 / 1.5 (the brief's map)  B 0.75 / 1.25  C down-only 0.5 / 1.0  D up-only 1.0 / 1.5
  walk-fwd  refit on the 1st trading day of each month on trades whose EXIT is >= 2 days before that day (purge + 1-2 day
            embargo); first test month once 100 finished trades exist (m = 1 before); expanding window; never refit inside a month.
  scoring   tools/lit_edge.evaluate (LIT size, live eval path with the MFFU caps, + funded MC for the best 3) vs the plain 1x run;
            controls: shuffled multipliers (200) and a shuffled-LABEL walk-forward (100); in-sample bound = a model fit on all
            631 trades applied to the same trades (the optimism = the IS - OOS gap).

    python -X utf8 research/edge_hunt/d/meta_label.py
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import E, HERE, SP, log_variant, row, span_sum, verdict  # noqa: E402

LAMBDA, MIN_TRAIN, EMBARGO_S = 10.0, 100, 2 * 86400
WIN_R = 0.5
MAPS = {"A_05_15": (0.5, 1.5), "B_075_125": (0.75, 1.25), "C_down05": (0.5, 1.0), "D_up15": (1.0, 1.5)}
F6 = ["depth_atr", "tod_h", "is_ny", "log_rr", "prev_rng", "vix", "streak3"]
F12 = F6 + ["stop_atr", "disp", "atr_regime", "day_rng", "prev_day", "idm_n"]
FEATS = {"F6": F6, "F12": F12}


# ------------------------------------------------------------------------------------------------ features (all known at the fill)
def build():
    """Per trade (in entry order): feature dict + R + exit_t. U = today's trades (E.trades())."""
    c = E.ctx()
    U = sorted(E.trades(), key=lambda u: u["entry_t"])
    rng, adr10, dix = c["rng"], c["adr10"], c["dix"]
    rows = []
    for u in U:
        r = c["intel"][int(u["entry_t"])]
        k = dix.get(str(u["day"]))
        pr = float(rng[k - 1] / adr10[k]) if k and k >= 1 and not np.isnan(adr10[k]) else 1.0
        R = u["pts"] / u["risk"]
        f = {"depth_atr": E._num(r["depth_atr"], 1.0), "tod_h": E._num(r["entry_min"], 0.0) / 60.0,
             "is_ny": 1.0 if E._num(r["entry_min"], 0.0) >= 480 else 0.0, "log_rr": math.log(max(E._num(r["rr"], 2.0), 1.0)),
             "prev_rng": pr, "vix": E._num(r["vix"], 18.0), "stop_atr": E._num(r["stop_atr"], 3.0), "disp": E._num(r["disp"], 1.0),
             "atr_regime": E._num(r["atr_regime"], 0.03), "day_rng": E._num(r["day_rng"], 0.3), "prev_day": E._num(r["prev_day"], 0.0),
             "idm_n": min(E._num(r["idm_n"], 0), 4)}
        rows.append({"u": u, "f": f, "R": R, "exit_t": int(u["exit_t"]), "entry_t": int(u["entry_t"]), "day": u["day"]})
    # streak: mean clipped R of the last 3 trades that FINISHED before this entry (nothing later leaks in)
    for i, a in enumerate(rows):
        prev = sorted((b for b in rows[:i] if b["exit_t"] <= a["entry_t"]), key=lambda b: b["exit_t"])[-3:]
        a["f"]["streak3"] = float(np.mean([max(-1.0, min(3.0, b["R"])) for b in prev])) if prev else 0.0
    return rows


def X_of(rows, cols):
    return np.array([[r["f"][c] for c in cols] for r in rows], float)


# ------------------------------------------------------------------------------------------------ models (numpy only)
class Logit:
    def fit(self, X, y):
        self.mu, self.sd = X.mean(0), X.std(0) + 1e-9
        Z = np.c_[np.ones(len(X)), (X - self.mu) / self.sd]
        w = np.zeros(Z.shape[1])
        P = np.eye(Z.shape[1]) * LAMBDA
        P[0, 0] = 0
        for _ in range(30):
            p = 1 / (1 + np.exp(-np.clip(Z @ w, -30, 30)))
            g = Z.T @ (p - y) + P @ w
            H = (Z * (p * (1 - p))[:, None]).T @ Z + P + 1e-6 * np.eye(len(w))
            step = np.linalg.solve(H, g)
            w -= step
            if np.abs(step).max() < 1e-7:
                break
        self.w = w
        return self

    def predict(self, X):
        Z = np.c_[np.ones(len(X)), (X - self.mu) / self.sd]
        return 1 / (1 + np.exp(-np.clip(Z @ self.w, -30, 30)))


class Tree:
    """Depth-2 gini tree, thresholds on 9 quantiles per feature, min leaf 25, Laplace leaves."""

    def __init__(self, depth=2, leaf=25):
        self.depth, self.leaf = depth, leaf

    def _split(self, X, y):
        best = (None, None, 0.0)
        n = len(y)
        g0 = 2 * y.mean() * (1 - y.mean())
        for j in range(X.shape[1]):
            for t in np.unique(np.quantile(X[:, j], np.linspace(0.1, 0.9, 9))):
                m = X[:, j] <= t
                nl = m.sum()
                if nl < self.leaf or n - nl < self.leaf:
                    continue
                pl, pr = y[m].mean(), y[~m].mean()
                gain = g0 - (nl / n) * 2 * pl * (1 - pl) - ((n - nl) / n) * 2 * pr * (1 - pr)
                if gain > best[2]:
                    best = (j, t, gain)
        return best

    def _grow(self, X, y, d):
        if d == 0 or len(y) < 2 * self.leaf:
            return (y.sum() + 1) / (len(y) + 2)
        j, t, gain = self._split(X, y)
        if j is None:
            return (y.sum() + 1) / (len(y) + 2)
        m = X[:, j] <= t
        return (j, t, self._grow(X[m], y[m], d - 1), self._grow(X[~m], y[~m], d - 1))

    def fit(self, X, y):
        self.t = self._grow(X, y, self.depth)
        return self

    def _one(self, x, node):
        while isinstance(node, tuple):
            node = node[2] if x[node[0]] <= node[1] else node[3]
        return node

    def predict(self, X):
        return np.array([self._one(x, self.t) for x in X])


MODELS = {"logit": Logit, "tree": Tree}


# ------------------------------------------------------------------------------------------------ walk-forward multipliers
def month_start_ts(day):
    d = dt.datetime.strptime(day[:7] + "-01", "%Y-%m-%d").replace(tzinfo=dt.timezone.utc)
    return int(d.timestamp())


def walk_forward(rows, cols, model, mapname, y=None):
    """m per entry_t. y = labels (default the real ones; the shuffled-label control passes its own)."""
    X = X_of(rows, cols)
    y = np.array([1.0 if r["R"] >= WIN_R else 0.0 for r in rows]) if y is None else y
    lo, hi = MAPS[mapname]
    exit_t = np.array([r["exit_t"] for r in rows])
    months = sorted({r["day"][:7] for r in rows})
    out = {}
    for mo in months:
        cut = month_start_ts(mo + "-01") - EMBARGO_S
        tr = exit_t <= cut
        idx = [i for i, r in enumerate(rows) if r["day"][:7] == mo]
        if tr.sum() < MIN_TRAIN or len(set(y[tr])) < 2:
            for i in idx:
                out[rows[i]["entry_t"]] = 1.0
            continue
        mdl = MODELS[model]().fit(X[tr], y[tr])
        ptr = mdl.predict(X[tr])
        q1, q2 = np.quantile(ptr, [1 / 3, 2 / 3])
        for i, p in zip(idx, mdl.predict(X[idx])):
            out[rows[i]["entry_t"]] = lo if p <= q1 else hi if p >= q2 else 1.0
    return out


def in_sample(rows, cols, model, mapname):
    """Optimism bound: one model fitted on ALL trades, applied to the same trades (look-ahead on purpose)."""
    X = X_of(rows, cols)
    y = np.array([1.0 if r["R"] >= WIN_R else 0.0 for r in rows])
    lo, hi = MAPS[mapname]
    mdl = MODELS[model]().fit(X, y)
    p = mdl.predict(X)
    q1, q2 = np.quantile(p, [1 / 3, 2 / 3])
    return {r["entry_t"]: (lo if pi <= q1 else hi if pi >= q2 else 1.0) for r, pi in zip(rows, p)}


def with_m(U, mm):
    return [{**u, "m": float(mm.get(u["entry_t"], 1.0))} for u in U]


def auc(p, y):
    o = np.argsort(p)
    r = np.empty(len(p)); r[o] = np.arange(1, len(p) + 1)
    n1, n0 = y.sum(), (1 - y).sum()
    return float((r[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0)) if n1 and n0 else float("nan")


def main():
    rows = build()
    U0 = [r["u"] for r in rows]
    base_o, _, base_L = E.evaluate(U=[{**u, "m": 1.0} for u in U0], fund=True)
    base = E.short(base_o)
    print(row("plain 1x (today's LIT)", base))
    res, picks = {}, []
    for fs in FEATS:
        for md in MODELS:
            for mp in MAPS:
                nm = f"{md}_{fs}_{mp}"
                mm = walk_forward(rows, FEATS[fs], md, mp)
                U = with_m(U0, mm)
                o, _, L = E.evaluate(U=U)
                s = E.short(o, base_o)
                ism = in_sample(rows, FEATS[fs], md, mp)
                _, _, Lis = E.evaluate(U=with_m(U0, ism))
                s["is_gap"] = {sp: round(span_sum(Lis, sp) - span_sum(base_L, sp)) for sp in SP}      # in-sample uplift
                s["oos_gain"] = {sp: round(span_sum(L, sp) - span_sum(base_L, sp)) for sp in SP}      # walk-forward uplift
                s["n_up"] = sum(1 for u in U if u["m"] > 1.0 + 1e-9 and u["day"] >= "2026")
                s["n_dn"] = sum(1 for u in U if u["m"] < 1.0 - 1e-9 and u["day"] >= "2026")
                s["pass"] = verdict(s)
                res[nm] = s
                log_variant("D-meta", nm, f"{md} on {fs}, map {mp}, walk-forward monthly", {k: s[k] for k in ("d_lit", "d_eval", "pass")})
                print(row(nm, s), "| dLIT", s["d_lit"], "IS", s["is_gap"], "pass", s["pass"], flush=True)
    # AUC of the walk-forward p on the OOS months (does it rank at all?)
    # controls for the 3 best by (H1+H2 LIT delta)
    best = sorted(res, key=lambda k: -(res[k]["d_lit"]["H1"] + res[k]["d_lit"]["H2"]))[:3]
    for nm in best:
        md, fs, mp = nm.split("_", 2)[0], nm.split("_")[1], "_".join(nm.split("_")[2:])
        U = with_m(U0, walk_forward(rows, FEATS[fs], md, mp))
        res[nm]["placebo_shuffled_m"] = E.placebo(U, base_L, n=200)
        rng = np.random.default_rng(5)
        real = {sp: span_sum(E.lit_size(U), sp) for sp in SP}
        beat = collections.Counter()
        y0 = np.array([1.0 if r["R"] >= WIN_R else 0.0 for r in rows])
        for _ in range(100):
            ys = rng.permutation(y0)
            LL = E.lit_size(with_m(U0, walk_forward(rows, FEATS[fs], md, mp, y=ys)))
            for sp in SP:
                beat[sp] += span_sum(LL, sp) >= real[sp]
        res[nm]["placebo_shuffled_label"] = {sp: beat[sp] / 100 for sp in SP}
        res[nm]["fund"] = E.funded(U)
        print("CONTROLS", nm, res[nm]["placebo_shuffled_m"], res[nm]["placebo_shuffled_label"], "fund", {k: v["per_month"] for k, v in res[nm]["fund"].items()}, flush=True)
    res["_base"] = base
    json.dump(res, open(os.path.join(HERE, "meta_label_results.json"), "w"), indent=1, default=float)


if __name__ == "__main__":
    main()
