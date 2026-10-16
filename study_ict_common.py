"""Shared harness for the ICT / SMC concept studies (study_ict_*.py). REAL CME futures only.

* Bars source: any CSV of 5m bars (time, open, high, low, close, volume). Default order:
    1. data/clean/NQ_5m.csv (the data agent's merged TradingView history), if it exists;
    2. otherwise a temporary merge of data/tv_exports/NQ1_5m_chunk_*.csv + data/NQ_5m.csv, written OUTSIDE data/
       (env ICT_TMP or the system temp dir). Chunk bars (TradingView CME exchange bars) win where both have a bar.
  data/_cfd_archive is never read. `--src default` reproduces engine.backtest.run exactly (data/NQ_5m.csv, NQ_1h warm-up).
* ES partner: data/ES_5m.csv (only Aug-Oct 2026 exists), used for SMT where the timestamps match.
* ICTEngine: the real Engine, unchanged, plus (1) the sweep geometry of every candidate stored in its feature dict and
  (2) the ICT features computed at plan time from closed bars only, and (3) an optional gate / score change that
  emulates exactly what an engine weight would do (score < min_score -> pass, shadow still logged, setup not consumed).
"""
from __future__ import annotations

import datetime as dt
import glob
import os
import tempfile
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from engine import ict_features as ICT
from engine.data import DATA_DIR, from_frame, load
from engine.instruments import INSTRUMENTS
from engine.model import Engine

ET = ZoneInfo("America/New_York")
FLAT = {"dd_aware": False, "daily_max_loss": 1e9}
WIDE = {**FLAT, "max_trades_day": 9, "stop_after_win": False}
RISK = 350.0
SPEC = INSTRUMENTS["NQ"]
CLEAN = os.path.join(DATA_DIR, "clean", "NQ_5m.csv")


# ----------------------------------------------------------------------------------------------- data
def _read(path):
    df = pd.read_csv(path)
    df.columns = [c.strip().lower() for c in df.columns]
    if "volume" not in df.columns:
        df["volume"] = 0.0
    df = df[["time", "open", "high", "low", "close", "volume"]].dropna(subset=["open", "high", "low", "close"])
    df["volume"] = df["volume"].fillna(0)
    return df


def merged_source():
    """Path of the best available NQ 5m history (see module doc)."""
    if os.path.exists(CLEAN):
        return CLEAN
    out = os.path.join(os.environ.get("ICT_TMP", tempfile.gettempdir()), "ict_NQ_5m_merged.csv")
    chunks = sorted(glob.glob(os.path.join(DATA_DIR, "tv_exports", "NQ1_5m_chunk_*.csv")))
    parts = [_read(f) for f in chunks]
    tv = pd.concat(parts).drop_duplicates("time", keep="last") if parts else pd.DataFrame()
    base = _read(os.path.join(DATA_DIR, "NQ_5m.csv"))
    if len(tv):
        base = base[~base["time"].isin(set(tv["time"]))]
    df = pd.concat([tv, base]).sort_values("time").drop_duplicates("time")
    df.to_csv(out, index=False)
    return out


_BARS = {}


def bars_from(path, sym="NQ"):
    key = (path, os.path.getmtime(path))
    if key not in _BARS:
        df = _read(path)
        df = df[~((df["high"] == df["low"]) & (df["volume"] <= 0))]
        _BARS[key] = from_frame(sym, "5m", df)
    return _BARS[key]


def slice_days(b, a, z):
    idx = [k for k, d in enumerate(b.date_str) if (not a or d >= a) and (not z or d <= z)]
    if not idx:
        raise ValueError("no bars in range")
    return b.slice(idx[0], idx[-1] + 1)


def warm_from(day, n_days=21):
    return (dt.date.fromisoformat(day) - dt.timedelta(days=n_days)).isoformat() if day else None


# ----------------------------------------------------------------------------------------------- engine
class ICTEngine(Engine):
    def __init__(self, *a, ict=None, es1h=None, **k):
        super().__init__(*a, **k)
        self.ict_cfg = ict or {}
        self._t2i = {int(t): j for j, t in enumerate(self.b.t)}
        self._arms = {1: [], -1: []}
        self._ictx = ICT.Context(self.b, self.partner, partner_1h=es1h)

    def _ev(self, t, kind, text, **data):
        if kind == "sweep" and "armed" in text:
            j = self._t2i.get(int(t))
            if j is not None and data.get("dir") in (1, -1):
                self._arms[data["dir"]].append(j)
        return super()._ev(t, kind, text, **data)

    def _plan(self, d, s, trig, i, *rest):
        order = super()._plan(d, s, trig, i, *rest)
        if order.get("skip") or "arm_i" not in s or not s.get("pools"):
            return order
        pool = float(s["pools"][0]["price"])
        x = ICT.features(self._ictx, d, i, s["arm_i"], s["ext_i"], pool, self._arms[d])
        f = order["features"]
        f.update({"_sig_i": i, "_arm_i": s["arm_i"], "_ext_i": s["ext_i"], "_pool": pool})
        f.update(x)
        cfg = self.ict_cfg
        if cfg:
            v = bool(f.get(cfg["feat"]) or 0)          # an ict_* feature, or any engine feature (e.g. "smt")
            mode, w = cfg.get("mode", "require"), cfg.get("w", 1)
            if mode == "require" and not v:
                order["score"] -= 100
            elif mode == "veto" and v:
                order["score"] -= 100
            elif mode == "plus" and v:
                order["score"] += w
            elif mode == "minus" and not v:
                order["score"] -= w
            order["conf_tags"] = order["conf_tags"] + [f"{cfg['feat']}={int(v)}"]
        return order


def run(params=None, src=None, date_from=None, date_to=None, ict=None, window_weeks=0):
    """Engine run(s). Trades / days / shadows are returned only for [date_from, date_to]; 21 calendar days before
    date_from are kept as warm-up. src: None = merged_source(), 'default' = exactly what engine.backtest.run uses.
    window_weeks > 0: independent runs over consecutive windows of that many weeks (each with its own 21-day warm-up),
    concatenated - guards against engine state carrying across a multi-year run."""
    if window_weeks:
        if src == "default":
            b = load("NQ", "5m")
        else:
            b = bars_from(src or merged_source())
        a0 = date_from or b.date_str[0]
        z0 = date_to or b.date_str[-1]
        out = {"trades": [], "days": [], "shadows": []}
        cur = dt.date.fromisoformat(a0)
        end = dt.date.fromisoformat(z0)
        while cur <= end:
            nxt = min(cur + dt.timedelta(weeks=window_weeks) - dt.timedelta(days=1), end)
            try:
                r = run(params, src, cur.isoformat(), nxt.isoformat(), ict, 0)
            except ValueError:
                r = {"trades": [], "days": [], "shadows": []}
            for k in out:
                out[k] += r[k]
            cur = nxt + dt.timedelta(days=1)
        return out
    p = {**FLAT, **(params or {})}
    if src == "default":
        b = load("NQ", "5m")
        htf = load("NQ", "1h")
    else:
        b = bars_from(src or merged_source())
        htf = None                     # resampled from the base bars: one self-consistent source
    b = slice_days(b, warm_from(date_from), date_to)
    partner = None
    if os.path.exists(os.path.join(DATA_DIR, "ES_5m.csv")):
        es = load("ES", "5m")
        try:
            partner = slice_days(es, b.date_str[0], b.date_str[-1])
        except ValueError:
            partner = None
    es1h = None
    for pth in (os.path.join(DATA_DIR, "clean", "ES_1h.csv"), os.path.join(DATA_DIR, "ES_1h.csv")):
        if os.path.exists(pth):
            es1h = bars_from(pth, "ES")
            break
    eng = ICTEngine(b, htf=htf, partner=partner, params=p, ict=ict, es1h=es1h).run()
    res = eng.result()
    keep = lambda day: (not date_from or day >= date_from) and (not date_to or day <= date_to)
    for t in res["trades"]:
        t["day"] = (dt.datetime.fromtimestamp(t["entry_t"], ET) + dt.timedelta(hours=6)).strftime("%Y-%m-%d")
    trades = [t for t in res["trades"] if keep(t["day"])]
    days = [d for d in res["days"] if keep(d["date"])]
    shadows = [s for s in res["shadows"] if keep(s["day"])]
    slim = lambda t: {k: t[k] for k in ("day", "dir", "pnl", "pnl_r", "gross", "qty", "grade", "grade_mult", "grade_points", "risk_pts_plan",
                                        "features", "entry_t", "exit_reason", "trigger", "regime") if k in t}
    return {"trades": [slim(t) for t in trades], "days": [d["date"] for d in days],
            "shadows": [{k: s[k] for k in ("day", "dir", "r", "f", "taken", "grade", "t")} for s in shadows]}


# ----------------------------------------------------------------------------------------------- stats
def week(day):
    y, w, _ = dt.date.fromisoformat(day).isocalendar()
    return f"{y}-W{w:02d}"


def resize(t, m):
    """$ pnl of a taken trade re-sized by multiplier m exactly like engine._size (micros floor, cap 40, commission)."""
    if abs(m - 1) < 1e-9:
        return t["pnl"]
    if t.get("regime") == "trending":
        m = m * 0.5                    # the engine already halved it; keep that
        base = 0.5
    else:
        base = 1.0
    micros = min(int(RISK * t["grade_mult"] * m // (t["risk_pts_plan"] * SPEC["micro_pv"])), 40)
    if micros < 1:
        return 0.0                     # skipped ("risk too small")
    gross = t["gross"] / t["qty"] * micros
    minis, rem = micros // 10, micros % 10
    return round(gross - (minis * SPEC["mini_comm_rt"] + rem * SPEC["micro_comm_rt"]), 2)


def boot(items, stat, weeks=None, n=2000, seed=7):
    """Week-block bootstrap of stat(list_of_items). items carry 'wk'. Returns (point, lo5, hi95, P(stat > 0))."""
    rng = np.random.default_rng(seed)
    by = {}
    for x in items:
        by.setdefault(x["wk"], []).append(x)
    wks = weeks or sorted(by)
    pt = stat(items)
    vals = []
    for _ in range(n):
        pick = rng.integers(0, len(wks), len(wks))
        sample = [x for k in pick for x in by.get(wks[k], [])]
        v = stat(sample)
        if v is not None and not np.isnan(v):
            vals.append(v)
    if not vals:
        return pt, None, None, None
    vals = np.array(vals)
    return pt, float(np.percentile(vals, 5)), float(np.percentile(vals, 95)), float((vals > 0).mean())


def diff_mean(key, val="r"):
    def f(items):
        a = [x[val] for x in items if x.get(key) == 1]
        b = [x[val] for x in items if x.get(key) == 0]
        if len(a) < 2 or len(b) < 2:
            return np.nan
        return float(np.mean(a) - np.mean(b))
    return f


def folds(weeks, train0, block):
    """Expanding-window week-block folds: [(train_weeks, test_weeks)]."""
    out = []
    k = train0
    while k < len(weeks):
        out.append((weeks[:k], weeks[k:k + block]))
        k += block
    return out


def fmt_ci(t, nd=2, pre="+"):
    pt, lo, hi, pp = t
    if pt is None or (isinstance(pt, float) and np.isnan(pt)):
        return "n/a"
    if lo is None:
        return f"{pt:{pre}.{nd}f}"
    return f"{pt:{pre}.{nd}f} ({lo:{pre}.{nd}f}..{hi:{pre}.{nd}f}, p+ {pp:.2f})"
