"""Edge hunt lane B: day features known BEFORE the 09:30 open (prior-close values only). Paper research only."""
import bisect, os, sys
import numpy as np, pandas as pd
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "tools"))
import div_search as DS
LAST = "2026-10-16"      # last day of GEX / VIX / VXN / ES data


def _prior(dates, vals, x, lag=1):
    i = bisect.bisect_left(dates, x) - lag        # strictly before x (a daily value is known only after its close)
    return vals[i] if i >= 0 else np.nan


def pct_rank(series, k, win=252, minp=60):
    h = series[max(0, k - win):k]
    h = h[np.isfinite(h)]
    if len(h) < minp or not np.isfinite(series[k]): return np.nan
    return float((h <= series[k]).mean() * 100)


class F:
    def __init__(self):
        B = DS.D()
        self.B = B
        n = len(B.days)
        self.k_ok = [k for k, x in enumerate(B.days) if x <= LAST]
        g = pd.read_csv(os.path.join(ROOT, "data", "GEX_1d.csv"))
        gd, gv = g.date.astype(str).tolist(), (g.gex / 1e9).tolist()
        self.gex = np.array([_prior(gd, gv, x) for x in B.days])
        v = pd.read_csv(os.path.join(ROOT, "data", "VIX_1d.csv")); v = v[v.close > 0]
        x_ = pd.read_csv(os.path.join(ROOT, "data", "VXN_1d.csv")); x_ = x_[x_.close > 0]
        vd, vv = v.date.astype(str).tolist(), v.close.tolist()
        xd, xv = x_.date.astype(str).tolist(), x_.close.tolist()
        self.vix = np.array([_prior(vd, vv, x) for x in B.days])
        self.vix2 = np.array([_prior(vd, vv, x, 2) for x in B.days])
        self.vxn = np.array([_prior(xd, xv, x) for x in B.days])
        self.vchg = self.vix / self.vix2 - 1
        self.spread = self.vxn - self.vix
        c = pd.read_csv(os.path.join(ROOT, "data", "CBOE_vol_1d.csv"))
        cd = c.date.astype(str).tolist()
        self.v3m = np.array([_prior(cd, c.vix3m.tolist(), x) for x in B.days])
        self.v9d = np.array([_prior(cd, c.vix9d.tolist(), x) for x in B.days])
        # CBOE series ends 2026-09-17: blank after that (no forward fill)
        late = np.array([x > "2026-09-18" for x in B.days]); self.v3m[late] = np.nan; self.v9d[late] = np.nan
        self.ts = self.vix / self.v3m            # >1 = backwardation
        self.ts9 = self.v9d / self.vix
        self.pr = {}
        for nm in ("gex", "spread", "vchg", "ts", "ts9", "vix"):
            a = getattr(self, nm)
            self.pr[nm] = np.array([pct_rank(a, k) for k in range(n)])
        self.ret = (B.C[:, -1] - B.O[:, 0])
        self.rng = B.H.max(axis=1) - B.L.min(axis=1)
        self.rel = self.rng / np.nanmean(np.where(True, self.rng, np.nan))
