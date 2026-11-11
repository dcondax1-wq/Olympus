"""Team C shared code: loading snapshots, trade units, fee, cluster-robust stats, market-calibrated null (max-t), bootstrap.

Protocol (same spirit as teams A and B, fixed before any held-out block is read):
  * a taker BUYS at the quoted ask (yes: yes ask; no: 1 - yes bid); fee 0.07*p*(1-p) per contract; edge per $1 = sum(pnl) / sum(cost).
  * clusters = settlement DAY (all cities / strikes that settle on one day are one cluster).
  * TRAIN = first 75% of quoted days, TEST = last 25% (read once). Cells are picked on TRAIN only.
  * multiple testing: a cell is carried only if its cluster t beats the 95th percentile of the MAX t over ALL cells of the family in a
    null where outcomes are drawn from the market's own mid prices (one bucket per event, days correlated). Every cell looked at is counted.
  * a carried cell must then be positive in TEST with a Bonferroni cluster-bootstrap lower bound > 0, and replicate frozen on unseen series.
"""
import glob, gzip, json, math, os
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
MAX_SPREAD = 0.04
BANDS = [(0.01, 0.10), (0.10, 0.30), (0.30, 0.50), (0.50, 0.70), (0.70, 0.90), (0.90, 0.95), (0.95, 0.99)]


def fee(p):
    return 0.07 * p * (1 - p)


def ncdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def load(series):
    fn = os.path.join(DATA, f"snap_{series}.jsonl.gz")
    if not os.path.exists(fn):
        return []
    return [json.loads(l) for l in gzip.open(fn, "rt")]


def band_of(p):
    for i, (a, b) in enumerate(BANDS):
        if a <= p < b or (i == len(BANDS) - 1 and p <= b + 1e-9 and p >= a):
            return i
    return -1


def quote(r, off):
    """-> (bid, ask) in dollars at `off` hours before close, or None. Empty sides are bid 0 / ask 1."""
    q = r["q"].get(str(off))
    if not q:
        return None
    return q[0] / 100.0, q[1] / 100.0


def sides(bid, ask, max_spread=MAX_SPREAD):
    """tradable taker buys at this quote: list of (side, price). Needs a two-sided book and a spread <= max_spread."""
    out = []
    if ask < bid or ask - bid > max_spread:
        return out
    if 0.01 <= ask <= 0.99:
        out.append(("yes", ask))
    if 0.01 <= 1 - bid <= 0.99:
        out.append(("no", 1 - bid))
    return out


def cell_stats(pnl, cost, cl):
    """cluster-robust ratio estimator: (n, clusters, edge per $1, t)."""
    n = len(pnl)
    if n == 0:
        return 0, 0, float("nan"), 0.0
    S, C = float(pnl.sum()), float(cost.sum())
    edge = S / C
    u, inv = np.unique(cl, return_inverse=True)
    resid = np.bincount(inv, weights=pnl - edge * cost, minlength=len(u))
    se = math.sqrt(float((resid ** 2).sum())) / C
    # floor: the binomial SE at the prices paid (as if every bet were independent). Without it a cell of 99c favourites that
    # happened to win every time has zero sample variance and an absurd t.
    p = np.clip(cost, 0.01, 0.99)
    se = max(se, math.sqrt(float((p * (1 - p)).sum())) / C)
    return n, len(u), edge, (edge / se if se > 0 else 0.0)


def boot(pnl, cost, cl, alpha=0.05, B=4000, seed=5):
    """cluster bootstrap of the edge: (one-sided lower bound at alpha, [2.5%, 97.5%])."""
    u, inv = np.unique(cl, return_inverse=True)
    sp = np.bincount(inv, weights=pnl, minlength=len(u)); sc = np.bincount(inv, weights=cost, minlength=len(u))
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(u), (B, len(u)))
    e = sp[idx].sum(1) / np.maximum(sc[idx].sum(1), 1e-12)
    return float(np.percentile(e, alpha * 100)), [float(np.percentile(e, 2.5)), float(np.percentile(e, 97.5))]


class Units:
    """flat table of candidate trades. Each unit: one market x decision time x side."""

    def __init__(self):
        self.rows = []      # dicts
        self.groups = {}    # (event, time) -> list of (market key, mid, kind, lo, hi) for the null draw

    def add(self, **k):
        self.rows.append(k)

    def finish(self):
        self.n = len(self.rows)
        self.col = {}
        if not self.rows:
            return self
        for key in self.rows[0]:
            v = [r[key] for r in self.rows]
            self.col[key] = np.array(v, dtype=object) if isinstance(v[0], str) else np.array(v, dtype=float)
        c = self.col
        c["pnl"] = c["win"] - c["p"] - 0.07 * c["p"] * (1 - c["p"])
        return self


def null_wins(U, n_sims, rho=0.3, seed=11):
    """Market-calibrated null: for each (event, time) group one outcome bucket is drawn from the normalised mid prices
    (exclusive buckets) or, for threshold ladders, yes iff u < mid (comonotone). The same uniform u is used for both decision
    times of an event and u is correlated across events of one day (rho). Yields win arrays (n_units,) per simulation."""
    c = U.col
    ev = c["event"]; day = c["day"]
    ue, einv = np.unique(ev, return_inverse=True)
    ud, dinv_units = np.unique(day, return_inverse=True)
    ev_day = np.zeros(len(ue), dtype=int)
    ev_day[einv] = dinv_units
    rng = np.random.default_rng(seed)
    lo, hi, yes = c["nlo"], c["nhi"], (c["side"] == "yes")
    from math import sqrt
    for _ in range(n_sims):
        z = sqrt(rho) * rng.standard_normal(len(ud))[ev_day] + sqrt(1 - rho) * rng.standard_normal(len(ue))
        u = np.array([ncdf(x) for x in z])[einv]
        y = (u >= lo) & (u < hi)          # yes-outcome of the unit's market under the null
        yield np.where(yes, y, ~y).astype(float)


def run_family(U, cells, train_mask, n_sims=300, min_n=100, min_cl=25, label=""):
    """cells: {name: boolean mask over units}. Returns dict with per-cell train/test stats, the null threshold, carried cells."""
    c = U.col
    pnl, cost, cl = c["pnl"], c["p"], c["day"]
    tr, te = train_mask, ~train_mask
    elig = {}
    for name, m in cells.items():
        j = np.where(m & tr)[0]
        if len(j) < min_n:
            continue
        n, ncl, e, t = cell_stats(pnl[j], cost[j], cl[j])
        if ncl < min_cl:
            continue
        elig[name] = (j, n, ncl, e, t)
    maxt = []
    for w in null_wins(U, n_sims):
        pn = w - c["p"] - 0.07 * c["p"] * (1 - c["p"])
        best = -9.0
        for name, (j, *_r) in elig.items():
            best = max(best, cell_stats(pn[j], cost[j], cl[j])[3])
        maxt.append(best)
    thr = float(np.percentile(maxt, 95)) if maxt and elig else float("nan")
    out = []
    carried = [nm for nm, (j, n, ncl, e, t) in elig.items() if e > 0 and t > thr]
    for name, m in cells.items():
        rec = {"cell": name, "n_train_all": int((m & tr).sum())}
        if name in elig:
            j, n, ncl, e, t = elig[name]
            rec.update(train_n=n, train_days=ncl, train_edge=round(e, 4), train_t=round(t, 2), train_win=round(float(c["win"][j].mean()), 4),
                       train_price=round(float(c["p"][j].mean()), 4), carried=name in carried)
        j = np.where(m & te)[0]
        if len(j) >= 20:
            n, ncl, e, t = cell_stats(pnl[j], cost[j], cl[j])
            rec.update(test_n=n, test_days=ncl, test_edge=round(e, 4), test_t=round(t, 2))
            rec["test_ci95"] = [round(x, 4) for x in boot(pnl[j], cost[j], cl[j], B=1000)[1]]
            if name in carried:
                lo_b, ci = boot(pnl[j], cost[j], cl[j], alpha=0.05 / max(1, len(carried)))
                rec.update(test_ci95=[round(x, 4) for x in ci], test_lo_bonf=round(lo_b, 4), survives=bool(e > 0 and lo_b > 0))
        elif name in carried:
            rec.update(test_n=int(len(j)), survives=False)
        out.append(rec)
    return {"family": label, "cells_defined": len(cells), "cells_eligible": len(elig), "null_max_t_p95": round(thr, 3) if elig else None,
            "null_max_t_median": round(float(np.median(maxt)), 3) if maxt and elig else None, "carried": carried,
            "survive": [r["cell"] for r in out if r.get("survives")], "cells": out}


def frozen(U, mask, alpha=0.05):
    """stats of one frozen rule on a set of units (replication)."""
    c = U.col
    j = np.where(mask)[0]
    if len(j) < 20:
        return {"n": int(len(j))}
    n, ncl, e, t = cell_stats(c["pnl"][j], c["p"][j], c["day"][j])
    lo_b, ci = boot(c["pnl"][j], c["p"][j], c["day"][j], alpha=alpha)
    return {"n": n, "days": ncl, "edge": round(e, 4), "t": round(t, 2), "ci95": [round(x, 4) for x in ci], "lo": round(lo_b, 4),
            "win": round(float(c["win"][j].mean()), 4), "price": round(float(c["p"][j].mean()), 4)}
