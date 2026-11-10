"""Shared helpers: loading, fees, Wilson / cluster-bootstrap CIs, normal cdf."""
import gzip, json, math, os, random
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")


def load(name):
    with gzip.open(os.path.join(DATA, name), "rt") as fh:
        return json.load(fh)


def load_spot(sym="BTC"):
    rows = load("spot_%s.json.gz" % sym)  # [start, low, high, open, close]
    t = np.array([r[0] for r in rows], dtype=np.int64)
    c = np.array([r[4] for r in rows], dtype=float)
    return t, c


class Spot:
    """Coinbase 1-minute closes. at(ts) = price at the END of the minute that ends at ts (ts multiple of 60)."""
    def __init__(self, sym="BTC"):
        self.t, self.c = load_spot(sym)
        self.idx = {int(x): i for i, x in enumerate(self.t)}

    def at(self, ts):
        i = self.idx.get(int(ts) - 60)
        return None if i is None else self.c[i]

    def vol(self, ts, win=90):
        """per-minute std of log returns over the `win` minutes before ts (None if gaps)."""
        i = self.idx.get(int(ts) - 60)
        if i is None or i < win:
            return None
        seg = self.c[i - win:i + 1]
        if self.t[i] - self.t[i - win] != win * 60:
            return None
        r = np.diff(np.log(seg))
        return float(np.std(r))


def ncdf(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def fee(p, rate=0.07):
    """Kalshi taker fee per contract (unrounded): 0.07*p*(1-p). Maker (resting) fee is 0.0175*p*(1-p) where charged."""
    return rate * p * (1 - p)


def wilson(w, n, z=1.96):
    if n == 0:
        return (0.0, 1.0)
    p = w / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def cluster_ci(vals, groups, B=2000, seed=1):
    """mean of vals with a 95% CI from a cluster bootstrap over `groups` (e.g. one cluster per day/event)."""
    vals = np.asarray(vals, float)
    if len(vals) == 0:
        return (float("nan"),) * 3
    gs = {}
    for v, g in zip(vals, groups):
        gs.setdefault(g, []).append(v)
    keys = list(gs)
    sums = np.array([sum(gs[k]) for k in keys])
    cnt = np.array([len(gs[k]) for k in keys])
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(B):
        s = rng.integers(0, len(keys), len(keys))
        out.append(sums[s].sum() / cnt[s].sum())
    return (float(vals.mean()), float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5)))
