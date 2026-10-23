"""Meta-labeling (Lopez de Prado), owner 2026-10-23: "What about quant, could you learn that?"

Keep each strategy's own signals. From facts known when the order goes in, learn the probability that the trade wins (R >= +0.5,
the trade_intel rule) and its expected R, and use that ONLY to size the trade (x0.5 to x1.5; never to create a trade, never to
skip one, so the trades per week stay exactly as they are). Research only: no engine / model file is touched.

Signals
  lit     run lit_live (the live LIT replay, 630 trades: 2026 on 1m bars, 2021-25 on 5m bars only = a different fill regime;
          a feature `fill_1m` says which). $ views: the LIT size rule (as lit_live is scored) and, for 2026, the eval path
          (two_week sizing, tools/lit_big_ideas.run_eval_x, the per-trade multiplier capped by 60% room + soft daily loss).
  atlas   the three ATLAS members (research/second/ema_best, md_best, sr_best; pooled, member as a feature) on the Builder 25K
          path (tools/second_account_b.py: need sizing, no-hedge; a multiplier capped by 50% room + the $600 soft loss, 20 max).
  sh_asia / sh_trend  the stop-hunt candidates (research/stophunt/sh_asia_resweep.json, sh_trend_idm5.json). The audit calls
          them weak / not real: a negative control. $ at their $500 risk.

Features (all known at the fill, from closed bars only; checked on data cut at the signal by `check_cut`)
  market   5m ATR and its 20-day percentile, realized vol (1h / 4h / 1 day) and its ratio, return over 1h / 4h / 1 day and vs
           EMA 50 / 200 / 600 (signed by the trade's side, in ATR), distance to the 18:00 open, the day's range so far vs the
           daily ATR, where price sits in it, distance to the prior day's high / low (target side / stop side), daily ATR and
           its 1-year percentile, prior day / 5 days with the trade, VIX / VXN prior close, 1- and 5-day change, 1-year
           percentile, VXN - VIX, VIX9D / VIX3M term structure, ES prior day with the trade and ES - NQ, ES 1h with the trade
           (ES intraday only from 2025-04), minute of day (sin / cos), weekday
  trade    stop (pts, ATR, daily ATR), R:R to the target
  recent   the strategy's own last 5 / 10 / 20 finished trades (mean R, win share, sum R), streak, days since the last exit
  own      LIT: the ~60 entry facts of research/lab/trade_intel.json; ATLAS: member; stop-hunt: pool score, flags, session
Method: purged + embargoed expanding walk-forward by calendar month (train on trades whose exit is >= 2 days before the month
starts; first test month once 120 trades are in the training set), plus one model frozen on everything before 2026-07-01 for
2026 H2. Models: L2 logistic (strong penalty), gradient boosting (depth 3, 80 trees), random forest (depth 3, 150 trees),
Platt-calibrated; each on all features and on a 12-feature core set picked before looking (no selection on outcomes). Expected R:
ridge + gradient boosting. Baseline: the training set's win rate (Brier skill vs that). Permutation test: the outcome (R) is
shuffled over the trades (recent-performance features recomputed from the shuffled R), the whole walk-forward re-run; the
statistic is the BEST model's AUC (max over the family = the multiple-testing price). Sizing: m = 0.5 + the trade's percentile
among the training predictions (rank map, mean ~1) or p / base rate (edge map), clipped 0.5-1.5; against flat (x1) and random
sizing (the same multipliers shuffled over the span's trades, 200-1000 draws).

    python -X utf8 tools/meta_label.py build      # features -> research/runs/_cache/meta_*.pkl + the cut-data check
    python -X utf8 tools/meta_label.py run        # walk-forward + permutations + sizing -> research/quant/meta/*.json
    python -X utf8 tools/meta_label.py save       # rl.save the runs ml_*
    python -X utf8 tools/meta_label.py all
Paper only. Edits no engine file.
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import logging
import math
import os
import pickle
import sys
import time
import warnings
from zoneinfo import ZoneInfo

os.environ.setdefault("OMP_NUM_THREADS", "1")
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "research", "quant", "meta")
CACHE = os.path.join(ROOT, "research", "runs", "_cache")
ET = ZoneInfo("America/New_York")
WIN_R = 0.5
EMBARGO_S = 2 * 86400
MIN_TRAIN = 120
H2_CUT = "2026-07-01"
N_PERM = int(os.environ.get("ML_PERM", "200"))
N_RAND = int(os.environ.get("ML_RAND", "200"))
SEED = 7
warnings.filterwarnings("ignore")
logging.getLogger("engine.sizing").setLevel(logging.ERROR)
CORE = ["stop_atr", "rr", "atr_pct", "vix", "vix_chg5", "rv_ratio", "d18", "ret4h", "ema200", "min_sin", "min_cos", "rec10_r"]


def ts_day(ts):
    return dt.datetime.fromtimestamp(int(ts), ET)


# ================================================================================================ market context (closed bars)
class Mkt:
    """Every array is causal: the value at bar i uses bars <= i only. feats(ts) reads the last bar CLOSED by ts."""

    def __init__(self, nq5, es5, vix, vxn, cboe, es1d, upto=None):
        if upto is not None:                                    # the cut-data copy: nothing at or after the signal exists
            nq5 = nq5[nq5.time + 300 <= upto]
            es5 = es5[es5.time + 300 <= upto]
        self.t = nq5.time.values.astype(np.int64)
        o, h, l, c = (nq5[k].values.astype(float) for k in ("open", "high", "low", "close"))
        self.o, self.h, self.l, self.c = o, h, l, c
        pc = np.r_[c[0], c[:-1]]
        tr = np.maximum(h - l, np.maximum(abs(h - pc), abs(l - pc)))
        s = pd.Series(c)
        self.atr = pd.Series(tr).rolling(14, min_periods=5).mean().values
        self.atr_pct = pd.Series(self.atr).rolling(5520, min_periods=500).rank(pct=True).values
        lr = np.r_[0.0, np.diff(np.log(c))]
        L = pd.Series(lr)
        self.rv12, self.rv48, self.rv276 = (L.rolling(n, min_periods=n // 2).std().values for n in (12, 48, 276))
        self.e50, self.e200, self.e600 = (s.ewm(span=n, adjust=False).mean().values for n in (50, 200, 600))
        # CME trading day (18:00 ET -> 17:00 ET, labelled by its end date)
        et = pd.to_datetime(self.t, unit="s", utc=True).tz_convert(ET)
        td = (et + pd.Timedelta(hours=6)).date
        self.td = np.array([d.isoformat() for d in td])
        b = np.r_[0, np.nonzero(self.td[1:] != self.td[:-1])[0] + 1]
        self.day_start = b
        self.days = list(self.td[b])
        e = np.r_[b[1:], len(c)]
        self.dO = o[b]; self.dC = c[e - 1]
        self.dH = np.array([h[i:j].max() for i, j in zip(b, e)]); self.dL = np.array([l[i:j].min() for i, j in zip(b, e)])
        dpc = np.r_[self.dC[0], self.dC[:-1]]
        dtr = np.maximum(self.dH - self.dL, np.maximum(abs(self.dH - dpc), abs(self.dL - dpc)))
        self.datr = pd.Series(dtr).rolling(14, min_periods=5).mean().values      # index j = days <= j
        self.datr_pct = pd.Series(self.datr).rolling(250, min_periods=60).rank(pct=True).values
        # ES intraday (2025-04 on)
        self.et_ = es5.time.values.astype(np.int64); self.ec = es5.close.values.astype(float)
        # daily vol / ES files: rows strictly before the trading day
        self.vix, self.vxn, self.cboe, self.es1d = vix, vxn, cboe, es1d

    @staticmethod
    def _daily(df, day, col, n=0):
        d = df[df.date < day]
        return d[col].values

    def feats(self, ts, side, risk_pts, tgt_pts, day):
        k = int(np.searchsorted(self.t, ts - 300, side="right")) - 1     # last bar closed by ts
        if k < 300:
            return None
        c, a = self.c[k], self.atr[k]
        f = {"atr5": a, "atr_pct": self.atr_pct[k], "rv12": self.rv12[k] * 1e4, "rv48": self.rv48[k] * 1e4,
             "rv276": self.rv276[k] * 1e4}
        f["rv_ratio"] = self.rv12[k] / self.rv276[k] if self.rv276[k] else np.nan
        for nm, n in (("ret1h", 12), ("ret4h", 48), ("ret1d", 276)):
            f[nm] = side * (c - self.c[k - n]) / a
        for nm, e in (("ema50", self.e50), ("ema200", self.e200), ("ema600", self.e600)):
            f[nm] = side * (c - e[k]) / a
        f["ema50_slope"] = side * (self.e50[k] - self.e50[k - 12]) / a
        j = int(np.searchsorted(self.day_start, k, side="right")) - 1     # the trading day bar k belongs to
        i0 = self.day_start[j]
        hi, lo = self.h[i0:k + 1].max(), self.l[i0:k + 1].min()
        datr = self.datr[j - 1] if j >= 1 else np.nan                       # prior days only
        f["d18"] = side * (c - self.o[i0]) / a
        f["day_rng"] = (hi - lo) / datr if datr else np.nan
        f["day_pos"] = ((c - lo) / (hi - lo) if hi > lo else 0.5) if side > 0 else ((hi - c) / (hi - lo) if hi > lo else 0.5)
        if j >= 6:
            pH, pL = self.dH[j - 1], self.dL[j - 1]
            f["pd_tgt"] = ((pH - c) if side > 0 else (c - pL)) / datr
            f["pd_stop"] = ((c - pL) if side > 0 else (pH - c)) / datr
            f["prev_day"] = side * (self.dC[j - 1] - self.dO[j - 1]) / datr
            f["prev_5d"] = side * (self.dC[j - 1] - self.dO[j - 5]) / datr
            f["datr"] = datr; f["datr_pct"] = self.datr_pct[j - 1]
        v = self._daily(self.vix, day, "close")
        if len(v) > 6:
            f["vix"] = v[-1]; f["vix_chg1"] = v[-1] - v[-2]; f["vix_chg5"] = v[-1] - v[-6]
            w = v[-250:]; f["vix_pct"] = float((w <= v[-1]).mean())
        x = self._daily(self.vxn, day, "close")
        x = x[x > 0]
        if len(x) and "vix" in f:
            f["vxn"] = x[-1]; f["vxn_vix"] = x[-1] - f["vix"]
        cb = self.cboe[self.cboe.date < day]
        if len(cb) and cb.vix3m.values[-1] > 0:
            f["vix_ts"] = cb.vix9d.values[-1] / cb.vix3m.values[-1]
        es = self.es1d[self.es1d.date < day]
        if len(es) > 2 and j >= 2:
            er = (es.close.values[-1] - es.close.values[-2]) / es.close.values[-2]
            nr = (self.dC[j - 1] - self.dC[j - 2]) / self.dC[j - 2]
            f["es_prev"] = side * er * 100; f["es_nq_prev"] = side * (er - nr) * 100
        ke = int(np.searchsorted(self.et_, ts - 300, side="right")) - 1
        if ke >= 12 and ts - self.et_[ke] < 900:
            er = (self.ec[ke] - self.ec[ke - 12]) / self.ec[ke - 12]
            nr = (c - self.c[k - 12]) / self.c[k - 12]
            f["es_1h"] = side * er * 100; f["es_nq_1h"] = side * (er - nr) * 100
        x = ts_day(ts)
        m = x.hour * 60 + x.minute
        f["min"] = m; f["min_sin"] = math.sin(2 * math.pi * m / 1440); f["min_cos"] = math.cos(2 * math.pi * m / 1440)
        f["wday"] = dt.date.fromisoformat(day).weekday()
        f["stop_pts"] = risk_pts; f["stop_atr"] = risk_pts / a
        f["stop_datr"] = risk_pts / datr if datr else np.nan
        f["rr"] = tgt_pts / risk_pts if (tgt_pts and risk_pts) else np.nan
        return {k_: (float(v_) if v_ is not None else np.nan) for k_, v_ in f.items()}


def load_raw():
    nq5 = pd.read_csv(os.path.join(ROOT, "data", "NQ_5m.csv"))
    es5 = pd.read_csv(os.path.join(ROOT, "data", "ES_5m.csv"))
    vix = pd.read_csv(os.path.join(ROOT, "data", "VIX_1d.csv"))
    vxn = pd.read_csv(os.path.join(ROOT, "data", "VXN_1d.csv"))
    cboe = pd.read_csv(os.path.join(ROOT, "data", "CBOE_vol_1d.csv"))
    es1d = pd.read_csv(os.path.join(ROOT, "data", "ES_1d.csv"))
    es1d["date"] = pd.to_datetime(es1d.time, unit="s", utc=True).dt.strftime("%Y-%m-%d")
    for d in (vix, vxn, cboe):
        d["date"] = d["date"].astype(str)
    return nq5, es5, vix, vxn, cboe, es1d


# ================================================================================================ recent strategy performance
def recent(rs, entry, exit_, idx):
    """Last 5 / 10 / 20 trades of the same strategy that EXITED before this one entered (R known then)."""
    i = idx
    fin = [j for j in range(len(rs)) if exit_[j] < entry[i]]
    fin.sort(key=lambda j: exit_[j])
    r = [rs[j] for j in fin]
    f = {}
    for n in (5, 10, 20):
        w = r[-n:]
        f[f"rec{n}_r"] = float(np.mean(w)) if len(w) >= min(n, 3) else np.nan
    w = r[-10:]
    f["rec10_win"] = float(np.mean([x >= WIN_R for x in w])) if len(w) >= 3 else np.nan
    f["rec20_sum"] = float(np.sum(r[-20:])) if r else np.nan
    st = 0
    for x in reversed(r):
        s = 1 if x > 0 else -1
        if st == 0 or (s > 0) == (st > 0):
            st += s
        else:
            break
    f["streak"] = float(st)
    f["since_exit_d"] = (entry[i] - exit_[fin[-1]]) / 86400 if fin else np.nan
    return f


def recent_matrix(rs, entry, exit_, groups):
    """recent() for every trade, within its own group (strategy member)."""
    rows = [None] * len(rs)
    for g in set(groups):
        ix = [i for i in range(len(rs)) if groups[i] == g]
        sr = [rs[i] for i in ix]; se = [entry[i] for i in ix]; sx = [exit_[i] for i in ix]
        order = np.argsort(sx)
        sx_sorted = np.array(sx)[order]; sr_sorted = np.array(sr)[order]
        for jj, i in enumerate(ix):
            n = int(np.searchsorted(sx_sorted, se[jj], side="left"))
            r = list(sr_sorted[:n])
            f = {}
            for m in (5, 10, 20):
                w = r[-m:]
                f[f"rec{m}_r"] = float(np.mean(w)) if len(w) >= min(m, 3) else np.nan
            w = r[-10:]
            f["rec10_win"] = float(np.mean([x >= WIN_R for x in w])) if len(w) >= 3 else np.nan
            f["rec20_sum"] = float(np.sum(r[-20:])) if r else np.nan
            st = 0
            for x in reversed(r):
                s = 1 if x > 0 else -1
                if st == 0 or (s > 0) == (st > 0):
                    st += s
                else:
                    break
            f["streak"] = float(st)
            f["since_exit_d"] = (se[jj] - sx_sorted[n - 1]) / 86400 if n else np.nan
            rows[i] = f
    return pd.DataFrame(rows)


REC_COLS = ["rec5_r", "rec10_r", "rec20_r", "rec10_win", "rec20_sum", "streak", "since_exit_d"]


# ================================================================================================ the four signal sets
def lit_trades():
    from tools import runlib as rl
    r = rl.load("lit_live")
    T = [dict(zip(r["trade_cols"], a)) for a in r["trades"]]
    ti = json.load(open(os.path.join(ROOT, "research", "lab", "trade_intel.json"), encoding="utf-8"))
    cols = ti["cols"]; keys = [c["key"] for c in cols]
    rows = {(x[keys.index("day")], int(x[keys.index("entry_t")])): dict(zip(keys, x)) for x in ti["rows"]}
    drop = {"micros", "risk_usd", "wk_half", "stop_pts", "side"}
    own_num = [c["key"] for c in cols if c["when"] == "entry" and c["kind"] in ("num", "bool") and c["key"] not in drop]
    own_cat = [c["key"] for c in cols if c["when"] == "entry" and c["kind"] == "cat" and c["key"] not in ("weekday", "side")]
    out = []
    for t in T:
        x = rows[(t["day"], int(t["entry_t"]))]
        own = {k: (float(x[k]) if x[k] is not None else np.nan) for k in own_num}
        for k in own_cat:
            own[f"{k}={x[k]}"] = 1.0
        own["fill_1m"] = float(t["trigger"] == "LIT-1m")
        tgt = (x.get("rr") or np.nan) * float(t["risk_pts"])
        out.append({"day": t["day"], "entry_t": int(t["entry_t"]), "exit_t": int(t["exit_t"]), "dir": int(t["dir"]),
                    "r": float(t["r"]), "risk_pts": float(t["risk_pts"]), "tgt_pts": tgt, "grp": "LIT", "qty": int(t["qty"]),
                    "pnl": float(t["pnl"]), "mae": t["mae"], "own": own, "exit": t["exit"]})
    return out


SECOND_FILES = {"EMA": "ema_best.json", "MD": "md_best.json", "SR": "sr_best.json"}


def second_trades(files, base, kind):
    out = []
    for g, fn in files.items():
        d = json.load(open(os.path.join(ROOT, *base, fn), encoding="utf-8"))
        for t in d["trades"]:
            e, s = float(t["entry"]), float(t["stop"])
            risk = abs(e - s)
            if risk <= 0:
                continue
            tgt = abs(float(t["target"]) - e) if t.get("target") is not None else np.nan
            own = {}
            if kind == "atlas":
                for m in files:
                    own[f"member={m}"] = float(g == m)
            else:
                own["pool_score"] = float(t.get("pool_score") or np.nan)
                own["flags"] = float(t.get("flags") or 0)
                own["hunt_lag_m"] = (int(t["entry_t"]) - int(t.get("hunt_t") or t["entry_t"])) / 60
                own["pool_dist"] = abs(float(t.get("pool_px") or e) - e) / risk
                own[f"session={t.get('session')}"] = 1.0
            out.append({"day": t["day"], "entry_t": int(t["entry_t"]), "exit_t": int(t["exit_t"]), "dir": int(t["dir"]),
                        "r": float(t["r"]), "risk_pts": risk, "tgt_pts": tgt, "grp": g, "qty": int(t["qty"]),
                        "pnl": float(t["pnl_usd"]), "mae": None, "own": own, "exit": t["exit_kind"]})
    out.sort(key=lambda t: t["entry_t"])
    return out


def signal_sets():
    return {"lit": lit_trades(),
            "atlas": second_trades(SECOND_FILES, ("research", "second"), "atlas"),
            "sh_asia": second_trades({"SHA": "sh_asia_resweep.json"}, ("research", "stophunt"), "sh"),
            "sh_trend": second_trades({"SHT": "sh_trend_idm5.json"}, ("research", "stophunt"), "sh")}


def build_set(T, mk):
    mrows, keep = [], []
    for i, t in enumerate(T):
        f = mk.feats(t["entry_t"], t["dir"], t["risk_pts"], t["tgt_pts"], t["day"])
        if f is None:
            continue
        mrows.append({**f, **t["own"]}); keep.append(i)
    T = [T[i] for i in keep]
    X = pd.DataFrame(mrows)
    own_cols = sorted({k for t in T for k in t["own"]})
    for k in own_cols:
        if "=" in k:
            X[k] = X[k].fillna(0.0)
    return T, X


def build():
    t0 = time.time()
    raw = load_raw()
    mk = Mkt(*raw)
    S = signal_sets()
    D = {}
    for nm, T in S.items():
        T, X = build_set(T, mk)
        D[nm] = {"T": T, "X": X}
        print(f"{nm}: {len(T)} trades, {X.shape[1]} features ({time.time() - t0:.0f}s)", flush=True)
    os.makedirs(CACHE, exist_ok=True)
    pickle.dump(D, open(os.path.join(CACHE, "meta_sets.pkl"), "wb"))
    chk = check_cut(raw, S)
    return D, chk


def check_cut(raw, S, n=25):
    """The market features of n random trades per set, recomputed from data cut at the signal (every 5m bar that closes after
    the fill removed, the arrays rebuilt from scratch): they must be identical to the full-data values."""
    rng = np.random.default_rng(SEED)
    full = Mkt(*raw)
    res = {}
    for nm, T in S.items():
        bad, done = [], 0
        for i in rng.choice(len(T), size=min(n, len(T)), replace=False):
            t = T[int(i)]
            a = full.feats(t["entry_t"], t["dir"], t["risk_pts"], t["tgt_pts"], t["day"])
            if a is None:
                continue
            cut = Mkt(*raw, upto=t["entry_t"])
            b = cut.feats(t["entry_t"], t["dir"], t["risk_pts"], t["tgt_pts"], t["day"])
            done += 1
            diff = [k for k in a if not (np.isclose(a[k], b.get(k, np.nan), rtol=1e-9, atol=1e-9, equal_nan=True))]
            # the 20-day ATR percentile and the EMAs start from the file's first bar in both copies, so they must match too
            if diff:
                bad.append({"day": t["day"], "entry_t": t["entry_t"], "diff": diff[:6]})
        res[nm] = {"checked": done, "differ": len(bad), "examples": bad[:3]}
        print(f"cut-data check {nm}: {done - len(bad)}/{done} identical", flush=True)
    return res


def load_sets():
    p = os.path.join(CACHE, "meta_sets.pkl")
    if not os.path.exists(p):
        return build()[0]
    return pickle.load(open(p, "rb"))


# ================================================================================================ models
def models():
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor, RandomForestClassifier
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression, Ridge
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    imp = lambda: SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True)  # noqa: E731
    cal = lambda m: CalibratedClassifierCV(m, method="sigmoid", cv=3)  # noqa: E731
    return {
        "lr": lambda: make_pipeline(imp(), StandardScaler(), LogisticRegression(C=0.05, max_iter=2000)),
        "gb": lambda: cal(HistGradientBoostingClassifier(max_depth=3, max_iter=80, learning_rate=0.05, min_samples_leaf=20,
                                                         l2_regularization=1.0, random_state=SEED)),
        "rf": lambda: cal(make_pipeline(imp(), RandomForestClassifier(n_estimators=150, max_depth=3, min_samples_leaf=10,
                                                                      max_features=0.3, random_state=SEED, n_jobs=1))),
    }, {
        "ridge": lambda: make_pipeline(imp(), StandardScaler(), Ridge(alpha=300.0)),
        "gbr": lambda: HistGradientBoostingRegressor(max_depth=3, max_iter=80, learning_rate=0.05, min_samples_leaf=20,
                                                     l2_regularization=1.0, random_state=SEED),
    }


def month_start_ts(m):
    return int(dt.datetime.fromisoformat(m + "-01").replace(tzinfo=ET).timestamp())


def folds(T):
    """Expanding monthly walk-forward: (train idx, test idx) with train = exits >= EMBARGO_S before the month opens."""
    months = sorted({t["day"][:7] for t in T})
    ex = np.array([t["exit_t"] for t in T]); dd = np.array([t["day"][:7] for t in T])
    out = []
    for m in months:
        cut = month_start_ts(m) - EMBARGO_S
        tr = np.nonzero(ex < cut)[0]; te = np.nonzero(dd == m)[0]
        if len(tr) >= MIN_TRAIN and len(te):
            out.append((m, tr, te))
    cut = month_start_ts(H2_CUT[:7]) - EMBARGO_S
    h2 = (np.nonzero(ex < cut)[0], np.nonzero(np.array([t["day"] >= H2_CUT for t in T]))[0])
    return out, h2


def fit_predict(X, y, tr, te, mk, cls=True):
    m = mk()
    # drop a column that is empty / constant in any third of the training set (the calibration's inner folds must see values)
    ok = np.array([all(len(np.unique(p[~np.isnan(p)])) >= 2 for p in np.array_split(c, 3)) for c in X[tr].T])
    X = X[:, ok]
    if X.shape[1] == 0:                     # nothing usable (e.g. a fixed 2R target: R:R is constant) -> the base rate
        b = float(y[tr].mean())
        return np.full(len(te), b), np.full(len(tr), b)
    if cls:
        if len(set(y[tr])) < 2:
            p = np.full(len(te), float(y[tr].mean())); return p, np.full(len(tr), float(y[tr].mean()))
        m.fit(X[tr], y[tr])
        return m.predict_proba(X[te])[:, 1], m.predict_proba(X[tr])[:, 1]
    m.fit(X[tr], y[tr])
    return m.predict(X[te]), m.predict(X[tr])


def walk(X_all, X_core, r, F, H2, fast=False):
    """One walk-forward pass over every model x feature set. Returns per-model OOS arrays (nan where no prediction)."""
    CLS, REG = models()
    y = (r >= WIN_R).astype(int)
    yr = np.clip(r, -1.2, 8.0)
    n = len(r)
    out = {}
    for fs, X in (("all", X_all), ("core", X_core)):
        for nm, mk in list(CLS.items()) + list(REG.items()):
            cls = nm in CLS
            key = f"{nm}_{fs}"
            P = np.full(n, np.nan); PCT = np.full(n, np.nan); BASE = np.full(n, np.nan)
            for _, tr, te in F:
                p, ptr = fit_predict(X, y if cls else yr, tr, te, mk, cls)
                P[te] = p
                PCT[te] = [(ptr < v).mean() + 0.5 * (ptr == v).mean() for v in p]
                BASE[te] = y[tr].mean() if cls else yr[tr].mean()
            tr, te = H2
            p, ptr = fit_predict(X, y if cls else yr, tr, te, mk, cls)
            P2 = np.full(n, np.nan); PCT2 = np.full(n, np.nan); B2 = np.full(n, np.nan)
            P2[te] = p; PCT2[te] = [(ptr < v).mean() + 0.5 * (ptr == v).mean() for v in p]
            B2[te] = y[tr].mean() if cls else yr[tr].mean()
            out[key] = {"cls": cls, "p": P, "pct": PCT, "base": BASE, "p_h2": P2, "pct_h2": PCT2, "base_h2": B2}
    return out


def auc(y, p):
    from sklearn.metrics import roc_auc_score
    ok = ~np.isnan(p)
    if ok.sum() < 10 or len(set(y[ok])) < 2:
        return np.nan
    return float(roc_auc_score(y[ok], p[ok]))


def spear(a, b):
    ok = ~np.isnan(b)
    if ok.sum() < 10:
        return np.nan
    return float(pd.Series(a[ok]).corr(pd.Series(b[ok]), method="spearman"))


def metrics(W, r, masks):
    y = (r >= WIN_R).astype(int); yr = np.clip(r, -1.2, 8.0)
    out = {}
    for key, w in W.items():
        o = {}
        for sp, mm in masks.items():
            src = "h2" if sp == "2026 H2 frozen" else ""
            p = w["p_h2"] if src else w["p"]; b = w["base_h2"] if src else w["base"]
            ok = mm & ~np.isnan(p)
            if ok.sum() < 10:
                o[sp] = {"n": int(ok.sum())}; continue
            if w["cls"]:
                br = float(np.mean((p[ok] - y[ok]) ** 2)); b0 = float(np.mean((b[ok] - y[ok]) ** 2))
                o[sp] = {"n": int(ok.sum()), "auc": round(auc(y[ok], p[ok]), 3), "brier": round(br, 4), "brier_base": round(b0, 4),
                         "bss": round(1 - br / b0, 3) if b0 else None, "win": round(float(y[ok].mean()), 3),
                         "p_mean": round(float(p[ok].mean()), 3)}
            else:
                mse = float(np.mean((p[ok] - yr[ok]) ** 2)); m0 = float(np.mean((b[ok] - yr[ok]) ** 2))
                o[sp] = {"n": int(ok.sum()), "spearman": round(spear(yr[ok], p[ok]), 3), "r2_vs_base": round(1 - mse / m0, 3),
                         "auc_win": round(auc(y[ok], p[ok]), 3)}
        out[key] = o
    return out


def stat_of(W, r, mask_wf, mask_h2):
    """The permutation statistics: OOS AUC on every walk-forward prediction, and the frozen model's AUC on 2026 H2 (regressors:
    the AUC of their predicted R for a win, so every model sits on one scale)."""
    y = (r >= WIN_R).astype(int)
    s = {}
    for k, w in W.items():
        s[k] = (auc(y[mask_wf], w["p"][mask_wf]), auc(y[mask_h2], w["p_h2"][mask_h2]))
    return s


def _perm_job(args):
    seed, X_all, X_core, r, T, F, H2, mwf, mh2, rec_ix, core_rec = args
    rng = np.random.default_rng(seed)
    rp = r[rng.permutation(len(r))]
    Xa, Xc = X_all.copy(), X_core.copy()
    rec = recent_matrix(list(rp), [t["entry_t"] for t in T], [t["exit_t"] for t in T], [t["grp"] for t in T])
    Xa[:, rec_ix] = rec[REC_COLS].values
    for j, c in core_rec:
        Xc[:, j] = rec[c].values
    W = walk(Xa, Xc, rp, F, H2)
    return stat_of(W, rp, mwf, mh2)


# ================================================================================================ sizing maps + $ / eval effects
def mult_of(w, mp, h2=False):
    p = w["p_h2"] if h2 else w["p"]; pct = w["pct_h2"] if h2 else w["pct"]; b = w["base_h2"] if h2 else w["base"]
    if mp == "rank":
        m = 0.5 + pct
    else:                                   # edge: p / base rate (classifiers) or 1 + (E[R] - mean R) (regressors)
        m = p / b if w["cls"] else 1.0 + (p - b)
    m = np.clip(m, 0.5, 1.5)
    return np.where(np.isnan(m), 1.0, m)


def qty_scale(q0, m, cap=40):
    if abs(m - 1.0) < 1e-9:
        return q0
    return max(1, min(cap, int(q0 * m + 1e-9))) if m < 1 else min(cap, int(q0 * m + 1e-9))


def dollar_view(T, m, sess, span, low_mode="mae"):
    """$ at the strategy's own size rule x m (P&L linear in micros), with the run library's scoring for the span."""
    from tools import runlib as rl
    a, z = span
    TT = []
    for t, mm in zip(T, m):
        if not (a <= t["day"] <= z):
            continue
        q = qty_scale(t["qty"], mm)
        per = t["pnl"] / t["qty"]
        if low_mode == "mae" and t.get("mae") is not None:
            low = -min(float(t["mae"]), max(1.0, -t["r"])) * t["risk_pts"] * 2.0 * q
        else:
            low = min(0.0, per * q)
        TT.append({**{k: t[k] for k in ("day", "entry_t", "exit_t", "dir", "r", "risk_pts", "exit")}, "qty": q,
                   "pnl": round(per * q, 2), "risk_usd": round(t["risk_pts"] * 2 * q, 2), "low": low, "mult": round(q / t["qty"], 3)})
    D = rl.days_of(TT, [d for d in sess if a <= d <= z])
    p = np.array([t["pnl"] for t in TT]) if TT else np.zeros(1)
    gl = -p[p < 0].sum()
    eq = np.cumsum(p)
    e = rl.eval_speed(D, horizon=20)
    return {"n": len(TT), "net": round(float(p.sum())), "pf": round(float(p[p > 0].sum() / gl), 2) if gl else None,
            "dd": round(float((eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min())) if len(TT) else 0,
            "per_month": round(float(p.sum()) / max(len(D) / 21, 1e-9)), "p10": e["p10"], "f10": e["f10"],
            "p20": e["p20"], "f20": e["f20"], "avg_mult": round(float(np.mean([t["mult"] for t in TT])), 3) if TT else None}, TT


class LitEval:
    """2026 eval path with the live two_week sizing (tools/lit_big_ideas.run_eval_x: multiplier on the two_week micros, a size-up
    capped by 60% of the room and the soft daily loss)."""

    def __init__(self):
        from tools import lit_adopt_combo as AC
        from tools import lit_big_ideas as BI  # noqa: F401  (patches lit_adv_manage.run_eval)
        from tools import lit_adv_manage as A
        from tools import lit_final as F
        self.A = A
        T = F.run(AC.LIVE | {"t_check": AC.T15, "be_off": AC.BE_OFF})
        self.U = AC.units(T)

    def score(self, mult, spans=("H1", "H2")):
        A = self.A
        U = [dict(u, m=float(mult.get(u["entry_t"], 1.0))) for u in self.U]
        o = {}
        for s in spans:
            Tp, n = A.b2b(U, s)
            st = A.stats(Tp, s); ev = A.evals(U, s)
            o[s] = {"net": st["net"], "pf": st["pf"], "dd": st["dd"], "per_month": st["per_month"], "p10": ev["p10"], "f10": ev["f10"],
                    "p20": ev["p20"], "f20": ev["f20"], "b2b": f"{n['PASS']}/{n['FAIL']}/{n['OPEN']}"}
        return o


class AtlasEval:
    """Builder 25K path (tools/second_account_b.py, need sizing, no-hedge): multiplier on the need micros, a size-up capped by
    50% of the room (the 25K preset), the $600 soft daily loss and 20 micros."""

    def __init__(self):
        from tools import second_account_b as SB
        from tools import second_mix as M
        self.SB, self.M = SB, M
        M.units()
        self.U = M.acct_units(SB.NAMES, nohedge=True)
        self.S = M.units()["sessions"]

    def score(self, mult, spans=("H1", "H2", "2025", "2021-24")):
        SB, M = self.SB, self.M
        U = [dict(u, m=float(mult.get((u["src"], u["entry_t"]), 1.0))) for u in self.U]
        o = {}
        with SB.Plan("builder25k") as pl:
            base_q = M.second_q

            def q2(t, st, rule):
                q = base_q(t, st, rule); m = t.get("m", 1.0)
                if q <= 0 or abs(m - 1.0) < 1e-9:
                    return q
                if m < 1:
                    return max(1, int(q * m + 1e-9))
                cap = min(pl.maxq, int(0.5 * max(0.0, st["room"]) / (t["risk"] * M.PV)), M.dll_cap(t, st))
                return max(q, min(int(q * m + 1e-9), cap))
            M.second_q = q2
            by = M.by_day(U)
            for sp in spans:
                a, z = M.SPANS[sp]
                S = [d for d in self.S if a <= d <= z]
                res = [(SB.run_eval(S[i:i + 20], by, "acctb_need"), len(S) - i) for i in range(len(S))]
                R = [x for x, av in res if av >= 10]; N = len(R) or 1
                p10 = round(100.0 * sum(1 for x in R if x[0] == "PASS" and x[1] <= 10) / N, 1)
                d10 = round(100.0 * sum(1 for x in R if x[0] in ("FAIL", "STUCK") and x[1] <= 10) / N, 1)
                k, TT, n = 0, [], collections.Counter()
                while k < len(S):
                    x, used, _ = SB.run_eval(S[k:], by, "acctb_need", len(S) - k, keep=TT)
                    n[x] += 1
                    if x == "OPEN":
                        break
                    k += used
                p = np.array([t["pnl"] for t in TT]) if TT else np.zeros(1)
                gl = -p[p < 0].sum()
                o[sp] = {"net": round(float(p.sum())), "pf": round(float(p[p > 0].sum() / gl), 2) if gl else None, "p10": p10,
                         "dead10": d10, "b2b": f"{n['PASS']}/{n['FAIL']}/{n['STUCK']}/{n['OPEN']}"}
        return o


# ================================================================================================ main experiment
SPANS = {"2021-25": ("2021-01-01", "2025-12-31"), "2026 H1": ("2026-01-01", "2026-06-30"), "2026 H2": ("2026-07-01", "2026-12-31")}


def run_set(nm, D, evalr=None, n_perm=N_PERM, procs=4):
    from multiprocessing import Pool
    t0 = time.time()
    T, Xdf = D["T"], D["X"].copy()
    r = np.array([t["r"] for t in T])
    rec = recent_matrix(list(r), [t["entry_t"] for t in T], [t["exit_t"] for t in T], [t["grp"] for t in T])
    for c in REC_COLS:
        Xdf[c] = rec[c].values
    cols = list(Xdf.columns)
    X_all = Xdf.values.astype(float)
    core = [c for c in CORE if c in cols]
    X_core = Xdf[core].values.astype(float)
    rec_ix = [cols.index(c) for c in REC_COLS]
    core_rec = [(core.index(c), c) for c in core if c in REC_COLS]
    F, H2 = folds(T)
    days = np.array([t["day"] for t in T])
    masks = {sp: (days >= a) & (days <= z) for sp, (a, z) in SPANS.items()}
    masks["2026 H2 frozen"] = masks["2026 H2"]
    W = walk(X_all, X_core, r, F, H2)
    has = ~np.isnan(W["lr_all"]["p"])
    masks_wf = {**{sp: m & has for sp, m in masks.items() if sp != "2026 H2 frozen"}, "all OOS": has,
                "2026 H2 frozen": masks["2026 H2"]}
    M = metrics(W, r, masks_wf)
    print(f"[{nm}] walk-forward done ({time.time() - t0:.0f}s): {len(F)} monthly folds, first test month {F[0][0]}, "
          f"{int(has.sum())} OOS trades", flush=True)
    for k in W:
        a, b = M[k].get("all OOS", {}), M[k].get("2026 H2 frozen", {})
        print(f"   {k:10s} OOS {a}  | H2 frozen {b}", flush=True)
    # trivial reference: a logistic on the R:R to the target (+ the member) only - the mechanical part of "win probability"
    tc = [c for c in cols if c == "rr" or c.startswith("member=")]
    Xt = Xdf[tc].values.astype(float)
    CLS, _ = models()
    y = (r >= WIN_R).astype(int)
    pt = np.full(len(r), np.nan); pt2 = np.full(len(r), np.nan)
    for _, tr, te in F:
        pt[te] = fit_predict(Xt, y, tr, te, CLS["lr"])[0]
    pt2[H2[1]] = fit_predict(Xt, y, H2[0], H2[1], CLS["lr"])[0]
    trivial = {"features": tc, "auc_oos": round(auc(y[has], pt[has]), 3), "auc_h2_frozen": round(auc(y[masks["2026 H2"]], pt2[masks["2026 H2"]]), 3)}
    print(f"   trivial (R:R + member only) {trivial}", flush=True)
    # permutation test (max over the model family)
    real = stat_of(W, r, has, masks["2026 H2"])
    pc = os.path.join(CACHE, f"meta_perm_{nm}.pkl")           # resumable: {seed: stats}
    done = pickle.load(open(pc, "rb")) if os.path.exists(pc) else {}
    todo = [SEED + 1000 + i for i in range(n_perm) if SEED + 1000 + i not in done]
    if todo:
        args = [(sd, X_all, X_core, r, T, F, H2, has, masks["2026 H2"], rec_ix, core_rec) for sd in todo]
        with Pool(procs) as pool:
            for i, s in enumerate(pool.imap(_perm_job, args, chunksize=1)):
                done[todo[i]] = s
                if (i + 1) % 10 == 0 or i + 1 == len(todo):
                    pickle.dump(done, open(pc, "wb"))
                    print(f"   permutations {len(done)}/{n_perm} ({time.time() - t0:.0f}s)", flush=True)
    perms = [done[SEED + 1000 + i] for i in range(n_perm)]
    P = perm_summary(real, perms)
    print(f"   permutation: best OOS AUC {P['best_wf']} p(max)={P.get('p_max_wf')}; best H2 AUC {P['best_h2']} p(max)={P.get('p_max_h2')}",
          flush=True)
    # importance stability (logistic coefficients per fold sign agreement; tree permutation importance on the H2-frozen fit)
    IMP = importance(Xdf, cols, core, r, F, H2)
    # sizing
    SZ_ = sizing(nm, T, W, masks, evalr)
    keep = {k: {"p": _r(W[k]["p"]), "p_h2": _r(W[k]["p_h2"])} for k in ("lr_all", "lr_core", "gb_all", "ridge_all")}
    res = {"set": nm, "n": len(T), "n_features": len(cols), "features": cols, "core": core, "folds": len(F),
           "first_test_month": F[0][0], "oos_trades": int(has.sum()), "h2_train_n": int(len(H2[0])), "h2_test_n": int(len(H2[1])),
           "win_rate": {sp: round(float((r[m] >= WIN_R).mean()), 3) for sp, m in masks.items() if m.any()},
           "metrics": M, "trivial": trivial, "permutation": P, "importance": IMP, "sizing": SZ_, "seconds": round(time.time() - t0),
           "trades": [{"day": t["day"], "entry_t": t["entry_t"], "grp": t["grp"], "r": round(t["r"], 3)} for t in T],
           "pred": keep}
    os.makedirs(OUT, exist_ok=True)
    json.dump(res, open(os.path.join(OUT, f"{nm}.json"), "w"), default=_js, separators=(",", ":"))
    return res, W


def _r(a):
    return [None if np.isnan(x) else round(float(x), 4) for x in a]


def _js(o):
    if isinstance(o, (np.floating,)):
        return None if np.isnan(o) else float(o)
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    return str(o)


def perm_summary(real, perms):
    keys = list(real)
    o = {"n_perm": len(perms), "real": {k: [round(v, 3) if not np.isnan(v) else None for v in real[k]] for k in keys}}
    bw = max(keys, key=lambda k: np.nan_to_num(real[k][0], nan=0)); bh = max(keys, key=lambda k: np.nan_to_num(real[k][1], nan=0))
    o["best_wf_model"], o["best_wf"] = bw, round(real[bw][0], 3)
    o["best_h2_model"], o["best_h2"] = bh, round(real[bh][1], 3)
    if not perms:
        return o
    mx_wf = np.array([max(np.nan_to_num(s[k][0], nan=0) for k in keys) for s in perms])
    mx_h2 = np.array([max(np.nan_to_num(s[k][1], nan=0) for k in keys) for s in perms])
    o["p_max_wf"] = round(float((1 + (mx_wf >= real[bw][0]).sum()) / (len(perms) + 1)), 4)
    o["p_max_h2"] = round(float((1 + (mx_h2 >= real[bh][1]).sum()) / (len(perms) + 1)), 4)
    o["null_max_wf_q95"] = round(float(np.quantile(mx_wf, 0.95)), 3)
    o["null_max_h2_q95"] = round(float(np.quantile(mx_h2, 0.95)), 3)
    o["per_model"] = {}
    for k in keys:
        a = np.array([np.nan_to_num(s[k][0], nan=0) for s in perms]); b = np.array([np.nan_to_num(s[k][1], nan=0) for s in perms])
        o["per_model"][k] = {"p_wf": round(float((1 + (a >= np.nan_to_num(real[k][0], nan=9)).sum()) / (len(perms) + 1)), 4),
                             "p_h2": round(float((1 + (b >= np.nan_to_num(real[k][1], nan=9)).sum()) / (len(perms) + 1)), 4),
                             "beats_shuffled_wf_pct": round(100 * float((a < np.nan_to_num(real[k][0], nan=-9)).mean()), 1),
                             "beats_shuffled_h2_pct": round(100 * float((b < np.nan_to_num(real[k][1], nan=-9)).mean()), 1)}
    return o


def importance(Xdf, cols, core, r, F, H2):
    """Is the same feature important in every fold? Logistic (all features, standardized): top-10 |coef| per yearly refit and
    the sign agreement across refits; the frozen pre-July model's top-10."""
    from sklearn.impute import SimpleImputer
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    y = (r >= WIN_R).astype(int)
    X = Xdf.values.astype(float)
    tops, coefs = [], []
    sel = [f for f in F if f[0].endswith("-01") or f[0].endswith("-07")]
    for m, tr, _ in sel + [("H2-frozen", H2[0], None)]:
        imp = SimpleImputer(strategy="median", keep_empty_features=True).fit(X[tr])
        sc = StandardScaler().fit(imp.transform(X[tr]))
        lr = LogisticRegression(C=0.05, max_iter=2000).fit(sc.transform(imp.transform(X[tr])), y[tr])
        c = lr.coef_[0]
        coefs.append(c)
        tops.append({"fit": m, "n": int(len(tr)), "top": [[cols[i], round(float(c[i]), 3)] for i in np.argsort(-abs(c))[:10]]})
    C = np.array(coefs)
    sgn = np.sign(C)
    agree = np.abs(sgn.sum(0)) / len(C)
    top_sets = [set(x[0] for x in t["top"]) for t in tops]
    jac = [len(a & b) / len(a | b) for a, b in zip(top_sets[:-1], top_sets[1:])] if len(top_sets) > 1 else []
    stable = sorted(((cols[i], round(float(agree[i]), 2), round(float(C[:, i].mean()), 3)) for i in range(len(cols))),
                    key=lambda x: (-x[1], -abs(x[2])))[:12]
    return {"fits": tops, "top10_jaccard_next_fit": [round(j, 2) for j in jac],
            "mean_jaccard": round(float(np.mean(jac)), 2) if jac else None, "most_sign_stable": stable}


def sizing(nm, T, W, masks, evalr):
    """$ / eval effect per model x map vs flat and random. Spans: 2021-25 (walk-forward predictions), 2026 H1 (walk-forward),
    2026 H2 (the frozen pre-July model)."""
    from tools import runlib as rl
    sess = [d[0] for d in rl.load("baseline")["days"]]
    rng = np.random.default_rng(SEED)
    out = {}
    combos = [(k, "rank") for k in W] + [(k, "edge") for k in ("lr_all", "lr_core", "ridge_all")]
    flat = {sp: dollar_view(T, np.ones(len(T)), sess, SPANS[sp])[0] for sp in SPANS}
    out["flat"] = {"dollar": flat}
    if evalr is not None:
        out["flat"]["eval"] = evalr.score({})
        print(f"   flat eval path {json.dumps(out['flat']['eval'])}", flush=True)
    for k, mp in combos:
        m_wf = mult_of(W[k], mp); m_h2 = mult_of(W[k], mp, h2=True)
        m = np.where(masks["2026 H2"], m_h2, m_wf)
        has = ~np.isnan(np.where(masks["2026 H2"], W[k]["p_h2"], W[k]["p"]))
        o = {"dollar": {}, "random": {}}
        for sp in SPANS:
            o["dollar"][sp] = dollar_view(T, m, sess, SPANS[sp])[0]
            ix = np.nonzero(masks[sp] & has)[0]
            nets, p10s = [], []
            for _ in range(N_RAND if sp != "2021-25" else N_RAND // 2):
                mr = m.copy(); mr[ix] = m[ix][rng.permutation(len(ix))]
                d = dollar_view(T, mr, sess, SPANS[sp])[0]
                nets.append(d["net"]); p10s.append(d["p10"])
            o["random"][sp] = {"net_mean": round(float(np.mean(nets))), "net_q95": round(float(np.quantile(nets, 0.95))),
                               "net_beats_random_pct": round(100 * float((np.array(nets) < o["dollar"][sp]["net"]).mean()), 1),
                               "p10_mean": round(float(np.mean(p10s)), 1),
                               "p10_beats_random_pct": round(100 * float((np.array(p10s) < o["dollar"][sp]["p10"]).mean()), 1)}
        if evalr is not None and mp == "rank" and k in ("lr_all", "lr_core", "gb_all", "rf_all", "ridge_all"):
            o["eval"], o["eval_random"] = eval_effect(nm, T, m, has, masks, evalr, rng)
        out[f"{k}|{mp}"] = o
        d = o["dollar"]
        print(f"   size {k:10s} {mp:4s} " + " | ".join(f"{sp} {d[sp]['net']:+,} (flat {flat[sp]['net']:+,}) 2w {d[sp]['p10']}/{d[sp]['f10']} "
                                                       f"rnd {o['random'][sp]['net_beats_random_pct']}%" for sp in SPANS)
              + (f" | eval {json.dumps(o.get('eval'))}" if o.get("eval") else ""), flush=True)
    return out


def eval_effect(nm, T, m, has, masks, evalr, rng, n=int(os.environ.get("ML_ERAND", "40"))):
    if nm == "lit":
        key = lambda t: t["entry_t"]  # noqa: E731
        spans = ("H1", "H2")
        smask = {"H1": masks["2026 H1"], "H2": masks["2026 H2"]}
    else:
        key = lambda t: (t["grp"], t["entry_t"])  # noqa: E731
        spans = ("H1", "H2", "2025", "2021-24")
        days = np.array([t["day"] for t in T])
        smask = {"H1": masks["2026 H1"], "H2": masks["2026 H2"], "2025": (days >= "2025-01-01") & (days <= "2025-12-31"),
                 "2021-24": days <= "2024-12-31"}
    mult = {key(t): float(x) for t, x in zip(T, m)}
    real = evalr.score(mult, spans)
    rnd = collections.defaultdict(list)
    for _ in range(n):
        mr = m.copy()
        for sp in spans:
            ix = np.nonzero(smask[sp] & has)[0]
            mr[ix] = m[ix][rng.permutation(len(ix))]
        o = evalr.score({key(t): float(x) for t, x in zip(T, mr)}, spans)
        for sp in spans:
            rnd[sp].append(o[sp])
    R = {}
    for sp in spans:
        nets = np.array([x["net"] for x in rnd[sp]]); p10 = np.array([x["p10"] for x in rnd[sp]])
        R[sp] = {"n": n, "net_mean": round(float(nets.mean())), "p10_mean": round(float(p10.mean()), 1),
                 "net_beats_random_pct": round(100 * float((nets < real[sp]["net"]).mean()), 1),
                 "p10_beats_random_pct": round(100 * float((p10 < real[sp]["p10"]).mean()), 1)}
    return real, R


def strict(res):
    """The owner's bar: OOS skill above the shuffled models in 95%+ of permutations (family max) AND better $ and eval odds than
    flat in 2026 H2 AND the 2021-25 walk-forward, for one sizing."""
    P = res["permutation"]
    skill = P.get("p_max_wf", 1) <= 0.05 and P.get("p_max_h2", 1) <= 0.05
    flat = res["sizing"]["flat"]["dollar"]
    hits = []
    for k, o in res["sizing"].items():
        if k == "flat":
            continue
        d = o["dollar"]
        ok = all(d[sp]["net"] > flat[sp]["net"] and d[sp]["p10"] >= flat[sp]["p10"] and d[sp]["f10"] <= flat[sp]["f10"]
                 for sp in ("2021-25", "2026 H2"))
        fe = res["sizing"]["flat"].get("eval")
        if ok and fe:                       # the eval path too (LIT: 2026 H2; ATLAS 25K: H2, 2025, 2021-24)
            if "eval" not in o:
                ok = False
            else:
                sps = [s for s in ("H2", "2025", "2021-24") if s in fe]
                dead = lambda x: x.get("f10", x.get("dead10"))  # noqa: E731
                ok = all(o["eval"][s]["net"] > fe[s]["net"] and o["eval"][s]["p10"] >= fe[s]["p10"]
                         and dead(o["eval"][s]) <= dead(fe[s]) for s in sps)
        if ok:
            hits.append(k)
    return {"skill_beats_shuffled_95": bool(skill), "sizings_better_both": hits, "passes": bool(skill and hits)}


def run(sets=("lit", "atlas", "sh_asia", "sh_trend")):
    D = load_sets()
    summ = {}
    for nm in sets:
        ev = LitEval() if nm == "lit" else (AtlasEval() if nm == "atlas" else None)
        res, _ = run_set(nm, D[nm], ev)
        res["strict"] = strict(res)
        json.dump(res, open(os.path.join(OUT, f"{nm}.json"), "w"), default=_js, separators=(",", ":"))
        summ[nm] = {"n": res["n"], "oos": res["oos_trades"], "perm": {k: v for k, v in res["permutation"].items() if k != "per_model"},
                    "strict": res["strict"]}
        print(f"[{nm}] strict: {res['strict']}", flush=True)
    summary()
    return summ


def summary():
    """research/quant/meta/summary.json from every stored set file: skill, permutation p, the trivial reference, the strict
    verdict and flat vs the best-$ sizing per span."""
    out = {}
    for nm in ("lit", "atlas", "sh_asia", "sh_trend"):
        p = os.path.join(OUT, f"{nm}.json")
        if not os.path.exists(p):
            continue
        r = json.load(open(p))
        P = r["permutation"]
        sz = {k: v for k, v in r["sizing"].items() if k != "flat"}
        best = max(sz, key=lambda k: sz[k]["dollar"]["2026 H2"]["net"])
        out[nm] = {"n": r["n"], "oos_trades": r["oos_trades"], "first_test_month": r["first_test_month"], "n_features": r["n_features"],
                   "win_rate": r["win_rate"], "trivial_rr_member": r.get("trivial"),
                   "best_oos": [P["best_wf_model"], P["best_wf"]], "p_family_oos": P.get("p_max_wf"),
                   "best_h2_frozen": [P["best_h2_model"], P["best_h2"]], "p_family_h2": P.get("p_max_h2"), "n_perm": P.get("n_perm"),
                   "importance_mean_jaccard": r["importance"]["mean_jaccard"],
                   "flat": r["sizing"]["flat"], "best_h2_sizing": best,
                   "best_h2_sizing_numbers": {"dollar": sz[best]["dollar"], "random": sz[best]["random"], "eval": sz[best].get("eval")},
                   "strict": r.get("strict")}
    json.dump(out, open(os.path.join(OUT, "summary.json"), "w"), indent=1, default=_js)
    return out


# ================================================================================================ store runs
def save():
    from tools import runlib as rl
    sess = [d[0] for d in rl.load("baseline")["days"]]
    D = load_sets()
    Q = "Owner 2026-10-23: can quant / ML meta-labeling (learn when a signal is likely to win, size it up or down) improve the strategies?"
    for nm, ttl in (("lit", "LIT"), ("atlas", "ATLAS members (EMA + MACD + S/R)"), ("sh_asia", "Stop-hunt Asia resweep"),
                    ("sh_trend", "Stop-hunt trend inducement")):
        res = json.load(open(os.path.join(OUT, f"{nm}.json")))
        k = "lr_all"
        W = {k: {"cls": True, "p": np.array([np.nan if x is None else x for x in res["pred"][k]["p"]]),
                 "p_h2": np.array([np.nan if x is None else x for x in res["pred"][k]["p_h2"]])}}
        T = D[nm]["T"]
        assert [t["entry_t"] for t in T] == [t["entry_t"] for t in res["trades"]]
        # percentiles were not stored: rebuild the rank map from the stored probabilities' rank inside each span's past
        o = res["sizing"][f"{k}|rank"]
        m = recompute_rank(res, k)
        TT = []
        for sp in SPANS:
            TT += dollar_view(T, m, sess, SPANS[sp])[1]
        TT.sort(key=lambda t: t["entry_t"])
        for t in TT:
            t.update(half=False, trigger=nm, mfe=None, mae=None, bars_held=None, regime="")
        f = lambda sp: (f"{sp} n={o['dollar'][sp]['n']} net {o['dollar'][sp]['net']:+,} vs flat {res['sizing']['flat']['dollar'][sp]['net']:+,}, "  # noqa: E731
                        f"2-wk {o['dollar'][sp]['p10']}/{o['dollar'][sp]['f10']} vs {res['sizing']['flat']['dollar'][sp]['p10']}/"
                        f"{res['sizing']['flat']['dollar'][sp]['f10']}, beats random sizing in {o['random'][sp]['net_beats_random_pct']}%")
        P = res["permutation"]
        mt = res["metrics"][k]
        rl.save(f"ml_{nm}_lr_rank", f"Meta-labeling size tilt on {ttl} (L2 logistic, rank map x0.5-x1.5)", "risk", Q,
                params={"model": "logistic L2 C=0.05, all features", "map": "m = 0.5 + percentile of p among the training predictions",
                        "walk_forward": "monthly expanding, 2-day embargo, min 120 trades", "h2": "frozen on data before 2026-07-01"},
                sizing={"mult": "0.5-1.5", "skip": False}, trades=TT, scored=rl.score(TT, [d for d in sess if d >= TT[0]["day"]]),
                status="rejected" if not res["strict"]["passes"] else "promising",
                verdict=(f"OOS AUC {mt['all OOS'].get('auc')} (2026 H2 frozen {mt['2026 H2 frozen'].get('auc')}); best model of the family "
                         f"{P['best_wf_model']} AUC {P['best_wf']} permutation p {P.get('p_max_wf')} (H2 {P.get('p_max_h2')}). "
                         f"{f('2021-25')}; {f('2026 H2')}. Strict pass: {res['strict']['passes']}."),
                notes="tools/meta_label.py; research/quant/meta/" + nm + ".json; sized at the strategy's own size rule x the multiplier "
                      "(P&L linear in micros); trades = walk-forward OOS span trades (untested months at x1).",
                writeup="meta-labeling", tags=["ml", "meta_label", nm])
        print("saved", f"ml_{nm}_lr_rank", flush=True)


def recompute_rank(res, k):
    """Rebuild the rank-map multipliers for model k (the stored run kept p, not the percentile): refit is avoided by redoing the
    walk-forward for that one model."""
    D = load_sets()[res["set"]]
    T, Xdf = D["T"], D["X"].copy()
    r = np.array([t["r"] for t in T])
    rec = recent_matrix(list(r), [t["entry_t"] for t in T], [t["exit_t"] for t in T], [t["grp"] for t in T])
    for c in REC_COLS:
        Xdf[c] = rec[c].values
    X = Xdf.values.astype(float)
    F, H2 = folds(T)
    CLS, _ = models()
    y = (r >= WIN_R).astype(int)
    n = len(r)
    PCT = np.full(n, np.nan); PCT2 = np.full(n, np.nan)
    for _, tr, te in F:
        p, ptr = fit_predict(X, y, tr, te, CLS[k.split("_")[0]])
        PCT[te] = [(ptr < v).mean() + 0.5 * (ptr == v).mean() for v in p]
    p, ptr = fit_predict(X, y, H2[0], H2[1], CLS[k.split("_")[0]])
    PCT2[H2[1]] = [(ptr < v).mean() + 0.5 * (ptr == v).mean() for v in p]
    days = np.array([t["day"] for t in T])
    pct = np.where(days >= H2_CUT, PCT2, PCT)
    return np.where(np.isnan(pct), 1.0, np.clip(0.5 + pct, 0.5, 1.5))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    if cmd == "build":
        D, chk = build()
        os.makedirs(OUT, exist_ok=True)
        json.dump(chk, open(os.path.join(OUT, "cut_check.json"), "w"), indent=1, default=_js)
    elif cmd == "run":
        run(tuple(sys.argv[2:]) or ("lit", "atlas", "sh_asia", "sh_trend"))
    elif cmd == "save":
        save()
    elif cmd == "summary":
        summary()
    else:
        D, chk = build()
        os.makedirs(OUT, exist_ok=True)
        json.dump(chk, open(os.path.join(OUT, "cut_check.json"), "w"), indent=1, default=_js)
        run(); save()
