"""Mind: the bots' thinking layer (owner 2026-10-29: "Give it a brain that's very smart. Can think for itself.").

READ-ONLY. Mind thinks, predicts, explains, researches and PROPOSES; it never changes a live rule, a size or an order
(CLAUDE.md hard rules). No paid service, no external model: plain statistics on the bots' own history, deterministic and
testable. Built on the pieces that already exist: the Bot Brain (engine/brain.py), market structure (engine/structure.py),
the playbook / discretion advisor (engine/playbook.py, engine/advisor.py), the narrator (engine/narrator.py).

What it does
  1 memory     every historical setup of each bot (Zlarior/LIT: run lit_live, 2026 1m + 2021-25 5m; ATLAS: run
               atlas_funded_live, EMA / MACD / S/R members; BLITZ: research/scalp/na_best_trades.json, 2026 1m) with the same
               features the live bot can compute (sweep depth / displacement in ATR, inducements, stop in ATR, R to the VIX
               band, time of day, killzone, VIX, 15m / 1h structure trend vs the trade, prior-day range ratio, first-hour
               range ratio, member) plus the live / paper trades as they close (logs/mind/<bot>_live.jsonl). For a forming /
               armed / open setup: the k nearest past setups -> win %, average R, $ at today's size, confidence, 3 examples.
               Validated out of sample (tools/mind_build.py: fit on 2026 H1, checked on 2026 H2 and 2021-25): when similarity
               does not predict the outcome there, the block says so ("valid": false, conf "low") and it is context only.
  2 regime     per closed 5m bar: trend (15m + 1h structure), volatility (5m ATR vs its 7-day median, VIX), and from 10:30 ET
               a trend-day probability (first hour vs its average, how directional the first hour was, where price sits vs
               the overnight range, the gap, VIX) from a small logistic model fit on 2026 H1, with its measured accuracy on
               2026 H2 and 2021-25 next to it.
  3 game plan  before each window (01:45 ET Zlarior + ATLAS, 10:45 ET BLITZ) an if-then plan per bot from today's levels,
               structure and regime, the $ at today's size and "what would change my mind".
  4 review     after each closed trade (any bot, real or paper): grade A-F, what went right / wrong, the lesson, luck or skill
               (outcome vs the R similar setups made). Journal: logs/mind/reviews.jsonl (gitignored).
  5 research   nightly (PC after 16:05 ET, a low-priority child process capped at 10 minutes): hypotheses from its own
               observations, each tested on the stored trades with the research scoring (2026 H1 pick / H2 check, 2021-25),
               filed as proposals {testing | candidate | rejected}. Never adopts anything: a candidate carries the exact change
               for the owner to approve.

Contract (rendered by the dashboards): block() -> {"t", "regime", "plans", "similar", "reviews", "proposals", "alerts", "iq"}
(tests/fixtures/mind_sample.json). liveview view()["mind"], phone_view (small cut), heartbeat "mind" (compact < 12 KB),
holo_api "mind", GET /api/next/mind (block + history). Nothing heavy runs on the trading poll: pc_tick (from
engine/narrator.tick) only checks whether a new 5m bar closed and, if so, starts one background thread.

    python -X utf8 tools/mind_build.py            # rebuild the memory + the calibration (research/mind/)
    python -X utf8 -m engine.mind research        # the nightly self-research job, by hand
    python -X utf8 -m tests.test_mind
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os
import threading
import time
from zoneinfo import ZoneInfo

import numpy as np

ET = ZoneInfo("America/New_York")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES_DIR = os.path.join(ROOT, "research", "mind")             # committed: the memory + calibration (tools/mind_build.py)
STORE_PATH = os.path.join(RES_DIR, "store.json")
CALIB_PATH = os.path.join(RES_DIR, "calibration.json")
SEED_PROPOSALS = os.path.join(RES_DIR, "proposals_seed.json")  # the first research run, so the dashboard is not empty
LOG_DIR = os.path.join(ROOT, "logs", "mind")                  # gitignored: reviews, live trades, proposals, plans
VERSION = 1
KIND = "le-mind"
BOTS = {"lit": "Zlarior", "atlas": "ATLAS", "blitz": "BLITZ"}
PV = 2.0
H1 = ("2026-01-01", "2026-06-30")
H2 = ("2026-07-01", "2026-12-31")
R2125 = ("2021-01-01", "2025-12-31")

# features per bot: numeric (z-scored on the fit set) / categorical (mismatch penalty), with weights
SPEC = {
    "lit": {"k": 15,
            "num": ["depth", "disp", "idm_n", "stop_atr", "rr", "mod", "vix", "tr15", "tr1h", "prev_rng", "day_pos", "atr_r"],
            "cat": ["dir", "kz", "lvl"],
            "w": {"depth": 1.0, "disp": 1.0, "idm_n": 0.6, "stop_atr": 1.0, "rr": 0.8, "mod": 0.6, "vix": 0.8, "tr15": 0.7,
                  "tr1h": 0.7, "prev_rng": 0.6, "day_pos": 0.6, "atr_r": 0.6, "dir": 0.5, "kz": 0.8, "lvl": 0.5}},
    "atlas": {"k": 20,
              "num": ["stop_atr", "mod", "vix", "tr15", "tr1h", "prev_rng", "day_pos", "atr_r"],
              "cat": ["member", "dir", "kz"],
              "w": {"stop_atr": 1.0, "mod": 0.7, "vix": 0.8, "tr15": 0.8, "tr1h": 0.8, "prev_rng": 0.6, "day_pos": 0.7,
                    "atr_r": 0.6, "member": 3.0, "dir": 0.5, "kz": 0.6}},
    "blitz": {"k": 20,
              "num": ["mod", "vix", "tr15", "tr1h", "prev_rng", "fh_ratio", "day_pos", "atr_r"],
              "cat": ["dir"],
              "w": {"mod": 0.7, "vix": 0.8, "tr15": 0.8, "tr1h": 0.8, "prev_rng": 1.0, "fh_ratio": 1.0, "day_pos": 0.8,
                    "atr_r": 0.6, "dir": 0.5}},
}
ROW0 = ["day", "t", "dir", "r", "usd", "exit", "src"]        # every store row starts with these, then the bot's features


# ================================================================================================ small helpers
def _et(t) -> dt.datetime:
    return dt.datetime.fromtimestamp(int(t), ET)


def et_mod(t) -> int:
    e = _et(t)
    return e.hour * 60 + e.minute


def trading_day(t) -> str:
    return (_et(t) + dt.timedelta(hours=6)).strftime("%Y-%m-%d")


def _f(v, nd=None):
    try:
        x = float(v)
        if not math.isfinite(x):
            return None
        return round(x, nd) if nd is not None else x
    except (TypeError, ValueError):
        return None


def _i(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def px(x) -> str:
    try:
        s = f"{float(x):,.2f}"
    except (TypeError, ValueError):
        return "?"
    return s.rstrip("0").rstrip(".") if "." in s else s


def usd(x, sign=True) -> str:
    v = _f(x)
    if v is None:
        return "$?"
    s = f"${abs(v):,.0f}"
    return (("+" if v > 0 else "-" if v < 0 else "") + s) if sign else s


def killzone(mod) -> str:
    """ET minute of the day -> session name (the windows the bots and the playbook talk about)."""
    m = int(mod) % 1440
    if m >= 1080 or m < 120:
        return "asia"
    if m < 300:
        return "london"
    if m < 510:
        return "pre"
    if m < 660:
        return "ny_am"
    if m < 810:
        return "lunch"
    if m < 960:
        return "ny_pm"
    return "close"


KZ_WORD = {"asia": "Asia", "london": "London", "pre": "pre-market", "ny_am": "New York morning", "lunch": "New York lunch",
           "ny_pm": "New York afternoon", "close": "after the close"}


def lvl_class(names) -> str:
    """The swept level's family from raw engine names (lon34_h, pdh, bu_l) or the Brain's labels (London high, PDH)."""
    for n in names or []:
        s = str(n).lower()
        if s.startswith("asia") or "asia" in s:
            return "asia"
        if s.startswith("lon") or "london" in s:
            return "london"
        if s.startswith("pre") or "premarket" in s or "pre-market" in s:
            return "pre"
        if s.startswith("ny") or "new york" in s or s.startswith("x_ny"):
            return "ny"
        if s[:3] in ("pdh", "pdl", "pwh", "pwl", "pmh", "pml") or "previous" in s or "prev " in s:
            return "htf"
        if s.startswith("bu_") or "equal" in s:
            return "buildup"
        if s.startswith(("nwog", "ndog")) or "gap" in s:
            return "gap"
    return "other"


def _span(day: str, sp) -> bool:
    return sp[0] <= str(day) <= sp[1]


def _read_json(path, default=None):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def _write_json(path, obj):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(obj, fh, separators=(",", ":"), default=_jd)
        os.replace(tmp, path)
        return True
    except Exception:
        return False


def _jd(o):
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, np.bool_):
        return bool(o)
    return str(o)


def _jl_read(path, n: int | None = None) -> list:
    try:
        with open(path, encoding="utf-8") as fh:
            rows = [json.loads(x) for x in fh if x.strip()]
    except (OSError, ValueError):
        return []
    return rows[-n:] if n else rows


def _jl_append(path, rows) -> bool:
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, separators=(",", ":"), default=_jd) + "\n")
        return True
    except Exception:
        return False


# ================================================================================================ bar history -> features
class Hist:
    """5m bars (unix open time, o, h, l, c) with everything the features need, computed once: ATR (engine/lit.atr), ET
    minute, trading day, per-day ranges (whole day, 09:30-16:00, first hour 09:30-10:30, overnight 18:00-09:30), running
    day high / low, 15m and 1h structure trends (engine/structure.frame_events, closed bars only) and the daily VIX close.
    The research store (whole data/NQ_5m.csv) and the live bot (CSV tail + the bot's own bars) use this same class, so a
    live setup is described exactly like the historical ones."""

    def __init__(self, t, o, h, l, c, vix: dict | None = None):
        import pandas as pd
        from engine import lit
        from engine import structure as ST
        order = np.argsort(np.asarray(t, np.int64), kind="stable")
        self.t = np.asarray(t, np.int64)[order]
        self.o, self.h, self.l, self.c = (np.asarray(x, float)[order] for x in (o, h, l, c))
        self.n = len(self.t)
        self.atr = lit.atr(self.h, self.l, self.c, 14) if self.n else np.zeros(0)
        s = pd.to_datetime(self.t, unit="s", utc=True).tz_convert(ET)
        self.mod = (s.hour * 60 + s.minute).to_numpy()
        dd = (s + pd.Timedelta(hours=6)).tz_localize(None).normalize()
        self.dayn = dd.to_numpy().astype("datetime64[D]").astype(np.int64)        # trading day as days since 1970
        u, first = np.unique(self.dayn, return_index=True)
        self.days = u
        self.first = first
        self.last = np.r_[first[1:], self.n] - 1
        self.k_of = np.searchsorted(u, self.dayn)
        df = pd.DataFrame({"k": self.k_of, "h": self.h, "l": self.l, "o": self.o, "c": self.c, "m": self.mod})
        g = df.groupby("k")
        self.cumhi = g["h"].cummax().to_numpy()
        self.cumlo = g["l"].cummin().to_numpy()
        nd = len(u)
        self.rng = (g["h"].max() - g["l"].min()).reindex(range(nd)).to_numpy()
        self.open18 = g["o"].first().reindex(range(nd)).to_numpy()

        def part(mask):
            q = df[mask].groupby("k")
            return (q["h"].max().reindex(range(nd)).to_numpy(), q["l"].min().reindex(range(nd)).to_numpy(),
                    q["o"].first().reindex(range(nd)).to_numpy(), q["c"].last().reindex(range(nd)).to_numpy())
        rth = (df["m"] >= 570) & (df["m"] < 960)
        self.rth_h, self.rth_l, self.rth_o, self.rth_c = part(rth)
        self.fh_h, self.fh_l, _o, self.fh_c = part((df["m"] >= 570) & (df["m"] < 630))
        self.on_h, self.on_l, _o2, _c2 = part((df["m"] >= 1080) | (df["m"] < 570))
        self.rth_rng = self.rth_h - self.rth_l
        self.fh_rng = self.fh_h - self.fh_l
        self.ev = {}
        for tf, secs in (("15m", 900), ("1h", 3600)):
            b = self.resample(secs)
            self.ev[tf] = ST.frame_events(*b, secs) if len(b[0]) > 10 else None
        self.vix = vix if vix is not None else load_vix()
        self._vd = np.array(sorted(self.vix), dtype="datetime64[D]").astype(np.int64) if self.vix else np.zeros(0, np.int64)
        self._vv = np.array([self.vix[k] for k in sorted(self.vix)], float) if self.vix else np.zeros(0)

    def resample(self, secs: int):
        b = (self.t // secs) * secs
        if not self.n:
            return (np.zeros(0, np.int64),) + tuple(np.zeros(0) for _ in range(4))
        cut = np.r_[0, np.flatnonzero(np.diff(b)) + 1]
        o = self.o[cut]
        h = np.maximum.reduceat(self.h, cut)
        l_ = np.minimum.reduceat(self.l, cut)
        c = self.c[np.r_[cut[1:], self.n] - 1]
        return b[cut], o, h, l_, c

    # ---- lookups
    def idx(self, T: int) -> int:
        """The last 5m bar closed by T (-1 if none)."""
        return int(np.searchsorted(self.t + 300, int(T), side="right")) - 1

    def day_k(self, day: str) -> int | None:
        dn = np.datetime64(day, "D").astype(np.int64)
        k = int(np.searchsorted(self.days, dn))
        return k if k < len(self.days) and self.days[k] == dn else None

    def vix_before(self, day: str):
        if not len(self._vd):
            return None
        dn = np.datetime64(day, "D").astype(np.int64)
        j = int(np.searchsorted(self._vd, dn)) - 1
        return float(self._vv[j]) if j >= 0 else None

    def trend(self, tf: str, T: int) -> int:
        ev = self.ev.get(tf)
        if ev is None or not len(ev["known_t"]):
            return 0
        from engine import structure as ST
        return ST.trend_at(ev, int(T))

    def ctx(self, T: int, d: int) -> dict:
        """The context features at decision time T (unix: the close of the deciding bar) for a trade in direction d."""
        i = self.idx(T)
        if i < 20:
            return {}
        k = int(self.k_of[i])
        day = str(np.datetime64(int(self.days[k]), "D"))
        mod = et_mod(T)
        f = {"mod": mod if mod >= 1080 - 1440 else mod, "kz": killzone(mod), "dir": int(d)}
        f["mod"] = (mod - 1080) % 1440                           # minutes since the 18:00 open (Asia first, no wrap)
        f["vix"] = self.vix_before(day)
        f["tr15"] = self.trend("15m", T) * int(d)
        f["tr1h"] = self.trend("1h", T) * int(d)
        a = float(self.atr[i])
        f["atr"] = round(a, 2)
        lo = max(0, i - 2016)
        med = float(np.median(self.atr[lo:i])) if i - lo > 50 else None
        f["atr_r"] = round(a / med, 3) if med else None
        if k >= 14:
            m = float(np.nanmean(self.rth_rng[k - 14:k]))
            f["prev_rng"] = round(float(self.rth_rng[k - 1]) / m, 3) if m and np.isfinite(self.rth_rng[k - 1]) else None
            if mod >= 630 and mod < 1080 and np.isfinite(self.fh_rng[k]):
                mf = float(np.nanmean(self.fh_rng[k - 14:k]))
                f["fh_ratio"] = round(float(self.fh_rng[k]) / mf, 3) if mf else None
        hi, lo_ = float(self.cumhi[i]), float(self.cumlo[i])
        pos = (float(self.c[i]) - lo_) / (hi - lo_) if hi > lo_ else 0.5
        f["day_pos"] = round(pos if d == 1 else 1.0 - pos, 3)
        f["day"] = day
        return f

    def price(self, T: int):
        i = self.idx(T)
        return float(self.c[i]) if i >= 0 else None


def load_vix(path: str | None = None) -> dict:
    """{date: close} of data/VIX_1d.csv (CBOE's own file)."""
    import csv
    out = {}
    try:
        with open(path or os.path.join(ROOT, "data", "VIX_1d.csv"), encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                v = _f(r.get("close"))
                if v is not None and r.get("date"):
                    out[r["date"][:10]] = v
    except OSError:
        pass
    return out


def hist_from_frame(df, since: int | None = None, vix: dict | None = None) -> Hist:
    if since is not None:
        df = df[df["time"] >= since]
    df = df.drop_duplicates("time", keep="last")
    return Hist(df["time"].to_numpy(), df["open"].to_numpy(), df["high"].to_numpy(), df["low"].to_numpy(), df["close"].to_numpy(), vix)


def hist_from_rows(rows, vix: dict | None = None) -> Hist:
    a = np.asarray([r[:5] for r in rows], float) if rows else np.zeros((0, 5))
    return Hist(a[:, 0].astype(np.int64), a[:, 1], a[:, 2], a[:, 3], a[:, 4], vix)


# ================================================================================================ the setup features
def lit_feats(depth=None, disp=None, idm_n=None, stop_pts=None, atr=None, rr=None, swept=None) -> dict:
    """Zlarior's own setup numbers (the engine's candidate fields; live: the Brain's setup checks / watch)."""
    a = _f(atr)
    return {"depth": _f(depth, 3), "disp": _f(disp, 3), "idm_n": _i(idm_n), "rr": _f(rr, 2),
            "stop_atr": round(float(stop_pts) / a, 3) if a and _f(stop_pts) is not None else None, "lvl": lvl_class(swept)}


# ================================================================================================ the memory (k nearest)
class Memory:
    """One bot's store as matrices; query(f) -> the k nearest past setups. Numeric features are z-scored on `fit` rows (all
    rows when None; missing -> 0 = the average), categorical ones add their weight on a mismatch."""

    def __init__(self, bot: str, cols: list, rows: list, fit=None):
        sp = SPEC[bot]
        self.bot, self.cols, self.rows = bot, list(cols), list(rows)
        self.num, self.cat, self.w, self.k = sp["num"], sp["cat"], sp["w"], sp["k"]
        ci = {c: j for j, c in enumerate(self.cols)}
        self.ci = ci
        n = len(self.rows)
        X = np.full((n, len(self.num)), np.nan)
        for j, c in enumerate(self.num):
            if c in ci:
                for r_i, r in enumerate(self.rows):
                    v = _f(r[ci[c]])
                    if v is not None:
                        X[r_i, j] = v
        F = np.ones(n, bool) if fit is None else np.asarray(fit, bool)
        with np.errstate(all="ignore"):
            mu = np.nanmean(X[F], axis=0) if F.any() else np.zeros(len(self.num))
            sd = np.nanstd(X[F], axis=0) if F.any() else np.ones(len(self.num))
        self.mu = np.where(np.isfinite(mu), mu, 0.0)
        self.sd = np.where(np.isfinite(sd) & (sd > 1e-9), sd, 1.0)
        Z = (X - self.mu) / self.sd
        self.Z = np.where(np.isfinite(Z), Z, 0.0)
        self.wn = np.array([self.w.get(c, 1.0) for c in self.num])
        self.C = [[str(r[ci[c]]) if c in ci else "" for c in self.cat] for r in self.rows]
        self.wc = np.array([self.w.get(c, 1.0) for c in self.cat])
        self.r = np.array([_f(r[ci["r"]]) or 0.0 for r in self.rows])
        self.days = [str(r[ci["day"]]) for r in self.rows]
        self.usd = [_f(r[ci["usd"]]) for r in self.rows]

    def zq(self, f: dict) -> np.ndarray:
        q = np.array([_f(f.get(c)) if _f(f.get(c)) is not None else np.nan for c in self.num])
        z = (q - self.mu) / self.sd
        return np.where(np.isfinite(z), z, 0.0)

    def dists(self, f: dict, pool=None) -> np.ndarray:
        z = self.zq(f)
        d2 = ((self.Z - z) ** 2 * self.wn).sum(axis=1)
        qc = [str(f.get(c)) if f.get(c) is not None else None for c in self.cat]
        for j, c in enumerate(qc):
            if c is None:
                continue
            mis = np.array([row[j] != c for row in self.C], float)
            d2 = d2 + mis * self.wc[j]
        d = np.sqrt(d2)
        if pool is not None:
            d = np.where(np.asarray(pool, bool), d, np.inf)
        return d

    def query(self, f: dict, k: int | None = None, pool=None, exclude_day: str | None = None) -> dict:
        k = int(k or self.k)
        if exclude_day is not None:
            ex = np.array([dd != exclude_day for dd in self.days])
            pool = ex if pool is None else (np.asarray(pool, bool) & ex)
        d = self.dists(f, pool)
        ok = np.isfinite(d)
        if not ok.any():
            return {"n": 0, "idx": []}
        order = np.argsort(d, kind="stable")[:min(k, int(ok.sum()))]
        rr = self.r[order]
        return {"n": int(len(order)), "idx": [int(i) for i in order], "avg_r": float(rr.mean()), "win": float((rr > 0).mean()),
                "sd": float(rr.std()), "d": [float(d[i]) for i in order]}


def conf_of(n: int, avg_r: float, sd: float, valid: bool) -> str:
    """"low" | "medium" | "high". Never above "low" when the out-of-sample check said similarity does not predict."""
    if not valid or n < 8:
        return "low"
    se = sd / math.sqrt(max(1, n))
    if abs(avg_r) >= 2.5 * se and n >= 15:
        return "high"
    if abs(avg_r) >= 1.5 * se:
        return "medium"
    return "low"


# ================================================================================================ honest validation
def _rank(x):
    x = np.asarray(x, float)
    o = np.argsort(x, kind="stable")
    r = np.empty(len(x))
    r[o] = np.arange(len(x))
    # ties: average ranks
    xs = x[o]
    i = 0
    while i < len(xs):
        j = i
        while j + 1 < len(xs) and xs[j + 1] == xs[i]:
            j += 1
        if j > i:
            r[o[i:j + 1]] = (i + j) / 2.0
        i = j + 1
    return r


def spearman(a, b) -> float | None:
    if len(a) < 5:
        return None
    ra, rb = _rank(a), _rank(b)
    if ra.std() == 0 or rb.std() == 0:
        return None
    return float(np.corrcoef(ra, rb)[0, 1])


def auc(score, y) -> float | None:
    score, y = np.asarray(score, float), np.asarray(y, bool)
    npos, nneg = int(y.sum()), int((~y).sum())
    if npos == 0 or nneg == 0:
        return None
    r = _rank(score) + 1
    return float((r[y].sum() - npos * (npos + 1) / 2) / (npos * nneg))


def tercile_spread(pred, actual) -> tuple:
    pred, actual = np.asarray(pred, float), np.asarray(actual, float)
    if len(pred) < 9:
        return None, None, None
    o = np.argsort(pred, kind="stable")
    n3 = len(o) // 3
    lo, hi = actual[o[:n3]].mean(), actual[o[-n3:]].mean()
    return float(hi - lo), float(hi), float(lo)


def perm_p(pred, actual, n_perm: int = 500, seed: int = 7) -> float | None:
    """One-sided permutation p-value of the top-minus-bottom tercile spread (is it bigger than shuffled predictions give)."""
    s, _, _ = tercile_spread(pred, actual)
    if s is None:
        return None
    rng = np.random.default_rng(seed)
    pred = np.asarray(pred, float)
    hits = 0
    for _ in range(n_perm):
        s2, _, _ = tercile_spread(rng.permutation(pred), actual)
        hits += s2 >= s
    return float((hits + 1) / (n_perm + 1))


def evaluate(mem: Memory, fit_mask, test_mask, k: int | None = None) -> dict:
    """Predict every test row from its k nearest FIT rows (never its own day) and score: rank correlation of the predicted
    average R with the real R, the top-vs-bottom tercile spread in R (+ permutation p), win-rate calibration (Brier vs
    the fit set's base rate) and AUC of the predicted win rate."""
    fit_mask, test_mask = np.asarray(fit_mask, bool), np.asarray(test_mask, bool)
    base = float((mem.r[fit_mask] > 0).mean()) if fit_mask.any() else 0.5
    pr, pw, ar = [], [], []
    for i in np.flatnonzero(test_mask):
        f = {c: mem.rows[i][mem.ci[c]] for c in mem.num + mem.cat if c in mem.ci}
        q = mem.query(f, k, pool=fit_mask, exclude_day=mem.days[i])
        if not q.get("n"):
            continue
        pr.append(q["avg_r"]); pw.append(q["win"]); ar.append(mem.r[i])
    if len(ar) < 9:
        return {"n": len(ar)}
    ar = np.array(ar); pw = np.array(pw)
    spread, top, bot = tercile_spread(pr, ar)
    y = ar > 0
    return {"n": len(ar), "spearman": _f(spearman(pr, ar), 3), "spread_r": _f(spread, 3), "top_r": _f(top, 3), "bot_r": _f(bot, 3),
            "p_perm": _f(perm_p(pr, ar), 3), "auc_win": _f(auc(pw, y), 3),
            "brier": _f(float(((pw - y) ** 2).mean()), 4), "brier_base": _f(float(((base - y) ** 2).mean()), 4),
            "win_real": _f(float(y.mean()), 3), "win_pred": _f(float(pw.mean()), 3), "avg_r_real": _f(float(ar.mean()), 3)}


def judge(spans: dict) -> tuple:
    """(valid, note): similarity counts as predictive only when EVERY checked span shows a positive rank correlation, a
    positive top-minus-bottom spread and a permutation p < 0.10."""
    used = {k: v for k, v in spans.items() if (v or {}).get("n", 0) >= 9}
    if not used:
        return False, "not enough out-of-sample trades to check"
    bad = [k for k, v in used.items() if not ((v.get("spearman") or 0) > 0 and (v.get("spread_r") or 0) > 0
                                             and (v.get("p_perm") if v.get("p_perm") is not None else 1) < 0.10)]
    return (not bad), ("predicts out of sample on " + " and ".join(used) if not bad else
                       "does NOT predict out of sample on " + " and ".join(bad) + ": shown as context only")


# ================================================================================================ day type (trend day at 10:30)
DT_FEATS = ["fh_ratio", "fh_eff", "on_ext", "gap", "prev_rng", "vix"]


def daytype_label(H: Hist, k: int) -> int | None:
    """1 = a trend day: the 09:30-16:00 session opened in one quarter of its range and closed in the opposite quarter."""
    hi, lo, o, c = H.rth_h[k], H.rth_l[k], H.rth_o[k], H.rth_c[k]
    if not all(np.isfinite([hi, lo, o, c])) or hi - lo <= 0:
        return None
    po, pc = (o - lo) / (hi - lo), (c - lo) / (hi - lo)
    return int((po <= 0.25 and pc >= 0.75) or (po >= 0.75 and pc <= 0.25))


def daytype_x(H: Hist, k: int) -> dict | None:
    """The 10:30 ET features of trading day k (known at the 10:25 bar's close)."""
    if k < 15:
        return None
    o, fh_h, fh_l, fh_c = H.rth_o[k], H.fh_h[k], H.fh_l[k], H.fh_c[k]
    if not all(np.isfinite([o, fh_h, fh_l, fh_c])) or fh_h - fh_l <= 0:
        return None
    m = float(np.nanmean(H.fh_rng[k - 14:k]))
    mr = float(np.nanmean(H.rth_rng[k - 14:k]))
    onh, onl = H.on_h[k], H.on_l[k]
    pos = (fh_c - onl) / (onh - onl) if np.isfinite(onh) and np.isfinite(onl) and onh > onl else 0.5
    prc, prr = H.rth_c[k - 1], H.rth_rng[k - 1]
    day = str(np.datetime64(int(H.days[k]), "D"))
    vx = H.vix_before(day)
    return {"fh_ratio": min(4.0, (fh_h - fh_l) / m) if m else None,
            "fh_eff": abs(fh_c - o) / (fh_h - fh_l),
            "on_ext": min(3.0, abs(pos - 0.5) * 2.0),
            "gap": min(2.0, abs(o - prc) / prr) if np.isfinite(prc) and np.isfinite(prr) and prr > 0 else None,
            "prev_rng": min(3.0, prr / mr) if mr and np.isfinite(prr) else None,
            "vix": (vx / 20.0) if vx else None, "day": day}


def logit_fit(X, y, lam: float = 1.0, iters: int = 50):
    """L2 logistic regression by Newton steps (numpy only). X already standardized; returns (b0, w)."""
    X, y = np.asarray(X, float), np.asarray(y, float)
    n, p = X.shape
    A = np.c_[np.ones(n), X]
    w = np.zeros(p + 1)
    R = np.eye(p + 1) * lam
    R[0, 0] = 0.0
    for _ in range(iters):
        z = A @ w
        pr = 1 / (1 + np.exp(-np.clip(z, -30, 30)))
        g = A.T @ (pr - y) + R @ w
        Hs = A.T @ (A * (pr * (1 - pr))[:, None]) + R
        step = np.linalg.solve(Hs, g)
        w -= step
        if np.abs(step).max() < 1e-8:
            break
    return float(w[0]), [float(x) for x in w[1:]]


def daytype_prob(model: dict, x: dict) -> float | None:
    if not model or not x:
        return None
    z = model["b0"]
    for j, c in enumerate(model["feats"]):
        v = _f(x.get(c))
        v = model["mu"][j] if v is None else v
        z += model["w"][j] * (v - model["mu"][j]) / model["sd"][j]
    return float(1 / (1 + math.exp(-max(-30.0, min(30.0, z)))))
