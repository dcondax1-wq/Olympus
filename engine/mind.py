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
              "num": ["mod", "vix", "tr15", "tr1h", "prev_rng", "fh_ratio", "p_trend", "day_pos", "atr_r"],
              "cat": ["dir"],
              "w": {"mod": 0.7, "vix": 0.8, "tr15": 0.8, "tr1h": 0.8, "prev_rng": 1.0, "fh_ratio": 1.0, "p_trend": 1.0, "day_pos": 0.8,
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
        f = {"mod": (mod - 1080) % 1440, "kz": killzone(mod), "dir": int(d)}     # mod: minutes since the 18:00 open (no wrap)
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


# ================================================================================================ the memory on disk
_MEM: dict = {}


def load_store(path: str | None = None) -> dict:
    """research/mind/store.json (tools/mind_build.py), cached by mtime. {} when missing."""
    p = path or STORE_PATH
    try:
        mt = os.path.getmtime(p)
    except OSError:
        return {}
    hit = _MEM.get(("store", p))
    if hit and hit[0] == mt:
        return hit[1]
    S = _read_json(p, {}) or {}
    _MEM[("store", p)] = (mt, S)
    return S


def load_calib(path: str | None = None) -> dict:
    p = path or CALIB_PATH
    try:
        mt = os.path.getmtime(p)
    except OSError:
        return {}
    hit = _MEM.get(("calib", p))
    if hit and hit[0] == mt:
        return hit[1]
    C = _read_json(p, {}) or {}
    _MEM[("calib", p)] = (mt, C)
    return C


def live_rows(bot: str, log_dir: str | None = None) -> list:
    """The bot's live / paper trades Mind has added to its memory (logs/mind/<bot>_live.jsonl) as store rows."""
    return [r["row"] for r in _jl_read(os.path.join(log_dir or LOG_DIR, f"{bot}_live.jsonl")) if isinstance(r, dict) and r.get("row")]


def memory(bot: str, store: dict | None = None, log_dir: str | None = None) -> Memory | None:
    """The bot's whole memory (history + live rows), z-scored on all of it (what live queries use)."""
    S = store if store is not None else load_store()
    blk = (S.get("bots") or {}).get(bot)
    if not blk:
        return None
    lr = live_rows(bot, log_dir)
    key = ("mem", bot, id(S), len(lr), log_dir)
    hit = _MEM.get(key)
    if hit is not None:
        return hit
    rows = list(blk["rows"]) + [r for r in lr if isinstance(r, list) and len(r) == len(blk["cols"])]
    m = Memory(bot, blk["cols"], rows)
    for k in [k for k in _MEM if isinstance(k, tuple) and k[:2] == ("mem", bot)]:
        _MEM.pop(k, None)
    _MEM[key] = m
    return m


def calib_valid(bot: str, C: dict | None = None) -> tuple:
    c = ((C if C is not None else load_calib()).get("similar") or {}).get(bot) or {}
    return bool(c.get("valid")), c


def calibration_line(C: dict | None = None) -> str:
    """One honest sentence per bot: does similarity predict outcomes out of sample?"""
    C = C if C is not None else load_calib()
    out = []
    for bot, nm in BOTS.items():
        c = (C.get("similar") or {}).get(bot)
        if not c:
            continue
        sp = c.get("spans") or {}
        bits = [f"{k} rank corr {float((v or {}).get('spearman') or 0):+.2f}, top-third minus bottom-third {float((v or {}).get('spread_r') or 0):+.2f}R"
                for k, v in sp.items() if v and v.get("n")]
        rev = ((c.get("reverse") or {}).get("spans") or {})
        rv = [f"{k} {float((v or {}).get('spread_r') or 0):+.2f}R (p {float((v or {}).get('p_perm') or 1):.2f})" for k, v in rev.items() if v and v.get("n")]
        out.append(f"{nm}: " + ("PREDICTS" if c.get("valid") else "does NOT predict") + " (fit 2026 H1; " + "; ".join(bits) + ")"
                   + (f"; with 2021-25 as memory: {', '.join(rv)}" if rv else ""))
    if not out:
        return "No calibration yet (python -X utf8 tools/mind_build.py)."
    return "Similar-setup memory, out of sample: " + " | ".join(out) + ". Not predictive = shown as context only, no confidence claims."


def daytype_note(C: dict | None = None) -> str:
    m = (C if C is not None else load_calib()).get("daytype") or {}
    rep = m.get("report") or {}
    h2, r = rep.get("H2") or {}, rep.get("2021-25") or {}
    if not h2 and not r:
        return "Trend-day model not built yet."
    s = (f"Trend-day model (fit 2026 H1, {m.get('n_fit')} days): 2026 H2 AUC {h2.get('auc')}, 2021-25 AUC {r.get('auc')} "
         f"(0.5 = coin flip); base rate {round(100 * (r.get('base_rate') or 0))}% of days")
    if r.get("n_p60"):
        s += f"; when it said >= 60%, {round(100 * (r.get('hit_p60') or 0))}% were trend days in 2021-25 (n {r['n_p60']})"
    s += ". Weak but real: odds, not a call (as a yes/no call it is no better than 'not a trend day')."
    return s


# ================================================================================================ the live bars
_HC: dict = {"key": None, "H": None}
CSV_HIST = True                                              # tests can switch the data/NQ_5m.csv tail off
HIST_DAYS = 45


def _rows_of_frame(df) -> list:
    return [[int(t), float(o), float(h), float(l_), float(c)] for t, o, h, l_, c in
            zip(df["time"].to_numpy(), df["open"].to_numpy(), df["high"].to_numpy(), df["low"].to_numpy(), df["close"].to_numpy())]


def live_hist(bot, now: int) -> Hist | None:
    """Hist for the live bot: the TradingView 5m export's tail, the bot's archive of NinjaTrader 5m bars, the bot's 1m
    store aggregated to 5m and bars_tail (later sources win on the same bar); closed bars only. Cached per closed 5m bar."""
    from . import pcdash_api
    now = int(now)
    try:
        b5, b1 = pcdash_api.bot_bars(bot, now - 14 * 86400)
    except Exception:
        b5, b1 = [], []
    key = (id(bot), now // 300, len(b5), b5[-1][0] if b5 else None, len(b1), b1[-1][0] if b1 else None)
    if _HC.get("key") == key and _HC.get("H") is not None:
        return _HC["H"]
    rows = {}
    t_from = now - HIST_DAYS * 86400
    if CSV_HIST:
        try:
            df = pcdash_api._csv("NQ", "5m")
            if df is not None and len(df):
                for r in _rows_of_frame(df[(df["time"] >= t_from) & (df["time"] + 300 <= now)]):
                    rows[r[0]] = r
        except Exception:
            pass
        try:
            from . import pcbars
            sym = str((getattr(bot, "cfg", None) or {}).get("sym") or "NQ")
            for s_ in dict.fromkeys((sym, "MNQ", "NQ")):
                a = pcbars.archive_read(s_, "5m")
                if a is not None and len(a):
                    for r in _rows_of_frame(a[(a["time"] >= t_from) & (a["time"] + 300 <= now)]):
                        rows[r[0]] = r
                    break
        except Exception:
            pass
    if b1:
        agg = {}
        for r in b1:
            b = int(r[0]) // 300 * 300
            if b + 300 > now:
                continue
            a = agg.get(b)
            agg[b] = [b, float(r[1]), float(r[2]), float(r[3]), float(r[4])] if a is None else \
                [b, a[1], max(a[2], float(r[2])), min(a[3], float(r[3])), float(r[4])]
        rows.update(agg)
    for r in b5:
        if int(r[0]) + 300 <= now:
            rows[int(r[0])] = [int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4])]
    if len(rows) < 300:
        return None
    H = hist_from_rows([rows[k] for k in sorted(rows)], vix=_vix_cached())
    _HC.update(key=key, H=H)
    return H


def _vix_cached() -> dict:
    p = os.path.join(ROOT, "data", "VIX_1d.csv")
    try:
        mt = os.path.getmtime(p)
    except OSError:
        return {}
    hit = _MEM.get(("vix", p))
    if hit and hit[0] == mt:
        return hit[1]
    v = load_vix(p)
    _MEM[("vix", p)] = (mt, v)
    return v


# ================================================================================================ regime + day type
def regime(H: Hist | None, now: int, C: dict | None = None) -> dict:
    """{"label", "trend", "vol", "day_type", "why"} at the last closed 5m bar."""
    if H is None or H.idx(now) < 50:
        return {"label": "No bars yet", "trend": "range", "vol": "normal", "day_type": None,
                "why": "Mind needs the bot's bars (NinjaTrader) or the TradingView export to read the market."}
    i = H.idx(now)
    t15, t1h = H.trend("15m", now), H.trend("1h", now)
    trend = ("up" if t1h > 0 else "down") if (t15 == t1h and t1h != 0) or (t1h != 0 and t15 == 0) else "range"
    a = float(H.atr[i])
    lo = max(0, i - 10 * 288)                              # the same time of day (+/- 30 min) over the last 10 sessions
    m_now = int(H.mod[i])
    near = np.abs(((H.mod[lo:i] - m_now) + 720) % 1440 - 720) <= 30
    pool = H.atr[lo:i][near]
    med = float(np.median(pool)) if len(pool) > 20 else (float(np.median(H.atr[max(0, i - 2016):i])) if i > 50 else a)
    ar = a / med if med else 1.0
    k = int(H.k_of[i])
    day = str(np.datetime64(int(H.days[k]), "D"))
    vx = H.vix_before(day)
    vol = "high" if (ar >= 1.35 or (vx or 0) >= 25) else "quiet" if (ar <= 0.75 and (vx if vx is not None else 99) < 16) else "normal"
    word = {-1: "down", 0: "range", 1: "up"}
    why = [f"15m structure {word[t15]}, 1h {word[t1h]}"]
    ev = H.ev.get("1h")
    if ev is not None and len(ev["known_t"]):
        j = int(np.searchsorted(ev["known_t"], int(now), side="right")) - 1
        if j >= 0:
            why.append(f"last 1h {'CHoCH' if int(ev['kind'][j]) == 2 else 'BOS'} {'up' if int(ev['dir'][j]) > 0 else 'down'} "
                       f"through {px(ev['level'][j])} at {_et(int(ev['known_t'][j])):%a %H:%M} ET")
    why.append(f"5m ATR {a:.1f} pts = {ar:.2f}x its usual at this time of day (10 sessions)")
    if vx is not None:
        why.append(f"VIX {vx:.1f}")
    lab = {"up": "Trending up", "down": "Trending down", "range": "Range"}[trend] + " · " + \
        {"high": "high volatility", "normal": "normal volatility", "quiet": "quiet"}[vol]
    return {"label": lab, "trend": trend, "vol": vol, "day_type": day_type(H, now, C), "why": "; ".join(why),
            "atr": round(a, 2), "atr_r": round(ar, 3), "vix": vx}


def day_type(H: Hist, now: int, C: dict | None = None) -> dict | None:
    """From 10:30 ET on a weekday: the trend-day probability of today (the model fit on 2026 H1) with its measured accuracy."""
    e = _et(now)
    if e.weekday() >= 5:
        return None
    C = C if C is not None else load_calib()
    model = C.get("daytype") or {}
    note = daytype_note(C)
    mod = e.hour * 60 + e.minute
    if not (630 <= mod < 1080):
        return {"p_trend": None, "label": "Trend-day odds come at 10:30 ET (after the first hour)", "acc_note": note}
    i = H.idx(now)
    k = int(H.k_of[i])
    if str(np.datetime64(int(H.days[k]), "D")) != trading_day(now):
        return {"p_trend": None, "label": "No bars of today's first hour yet", "acc_note": note}
    x = daytype_x(H, k)
    p = daytype_prob(model, x) if x else None
    if p is None:
        return {"p_trend": None, "label": "Trend-day odds unavailable (first hour missing)", "acc_note": note}
    lab = (f"Trend day likely ({p:.0%} odds)" if p >= 0.5 else f"Range / rotation day likely (trend-day odds {p:.0%})" if p <= 0.2
           else f"Unclear day ({p:.0%} trend-day odds)")
    return {"p_trend": round(p, 3), "label": lab, "acc_note": note,
            "x": {k_: (round(v, 3) if isinstance(v, float) else v) for k_, v in (x or {}).items() if k_ != "day"}}


# ================================================================================================ live setups -> similar
def _check(s: dict, key: str):
    for c in s.get("checks") or []:
        if isinstance(c, dict) and c.get("key") == key:
            return c.get("value")
        if isinstance(c, (list, tuple)) and c and c[0] == key:
            return None
    return None


def lit_now(bot, H: Hist, now: int) -> dict | None:
    """Zlarior's setup that matters now: the open trade's setup, an armed / tapped setup, else the forming side (swept)."""
    b = getattr(bot, "brain", None) or {}
    if not isinstance(b, dict) or not b:
        return None
    S = [s for s in b.get("setups") or [] if isinstance(s, dict)]
    key = (b.get("stage") or {}).get("key")
    pick = None
    if key == "trade":
        pick = next((s for s in reversed(S) if s.get("trade") or s.get("status") == "filled"), None)
    if pick is None:
        pick = next((s for s in reversed(S) if s.get("status") in ("armed", "tapped", "entering")), None)
    if pick is not None and pick.get("t"):
        d = int(pick.get("dir") or 1)
        f = H.ctx(int(pick["t"]), d)
        if not f:
            return None
        stop = _check(pick, "stop") or (pick.get("plan") or {}).get("stop_pts")
        f.update(lit_feats(_check(pick, "depth"), _check(pick, "disp"), _check(pick, "idm"), stop, pick.get("atr"),
                           _check(pick, "target") or (pick.get("plan") or {}).get("rr"), pick.get("swept")))
        what = f"{pick.get('side') or ('LONG' if d == 1 else 'SHORT')} setup {pick.get('hm') or ''} ({pick.get('status') or 'live'})"
        return {"f": f, "what": what.strip(), "dir": d, "stage": key}
    from .liveview_api import lead_watch
    w = lead_watch(b)
    if not w or key in ("done",):
        return None
    d = int(w.get("dir") or 1)
    f = H.ctx(now, d)
    if not f:
        return None
    f.update(lit_feats(w.get("depth_atr"), w.get("disp"), w.get("idm_n"), w.get("stop_preview"), w.get("atr") or f.get("atr"),
                       None, w.get("swept")))
    return {"f": f, "what": f"forming {w.get('side') or ''} ({w.get('stage') or 'sweep'})".replace("  ", " "), "dir": d, "stage": key}


MEMBER = {"ema": "EMA", "macd": "MD", "sr": "SR"}


def member_of(key: str) -> str | None:
    k = str(key or "").lower()
    for p, m in MEMBER.items():
        if k.startswith(p):
            return m
    return None


def _dir_from_text(txt) -> int | None:
    s = str(txt or "").lower()
    if "(long" in s or " long" in s[:40]:
        return 1
    if "(short" in s or " short" in s[:40]:
        return -1
    return None


def atlas_now(bot, H: Hist, now: int) -> dict | None:
    sec = getattr(bot, "second", None) or {}
    best = None
    for k, s in ((sec.get("strategies") or {}) if isinstance(sec, dict) else {}).items():
        m = member_of(k)
        if not m or not isinstance(s, dict) or s.get("on") is False:
            continue
        st = s.get("state") or {}
        stage = st.get("stage")
        op = next((t for t in reversed(s.get("trades") or []) if isinstance(t, dict) and t.get("exit_kind") == "OPEN"), None)
        if op:
            d, T, stop_pts = int(op.get("dir") or 1), int(op.get("entry_t") or now), abs(float(op.get("entry") or 0) - float(op.get("stop") or 0))
            rank = 2
        elif stage == "armed":
            pl = ((s.get("brain") or {}).get("plan") or {})
            d = _dir_from_text(st.get("text")) or (1 if str(pl.get("side") or "").lower().startswith("l") else -1 if pl.get("side") else None)
            if d is None:
                continue
            T = now
            stop_pts = abs(float(pl.get("entry") or 0) - float(pl.get("stop") or 0)) if pl.get("entry") is not None and pl.get("stop") is not None else None
            rank = 1
        else:
            continue
        if best is None or rank > best[0]:
            best = (rank, k, m, d, T, stop_pts, s.get("short") or k, stage if not op else "in_trade")
    if best is None:
        return None
    _r_, k, m, d, T, stop_pts, short, stage = best
    f = H.ctx(T, d)
    if not f:
        return None
    f["member"] = m
    f["stop_atr"] = round(stop_pts / f["atr"], 3) if stop_pts and f.get("atr") else None
    return {"f": f, "what": f"{short} {'LONG' if d == 1 else 'SHORT'} ({stage})", "dir": d, "key": k}


def blitz_now(bot, H: Hist, now: int) -> dict | None:
    S = getattr(bot, "blitz", None)
    if not isinstance(S, dict):
        return None
    day = trading_day(now)
    op = next((r for r in reversed(S.get("ledger") or []) if isinstance(r, dict) and r.get("exit_kind") == "OPEN"), None)
    if op and op.get("entry_t"):
        d, T, what = int(op.get("dir") or 1), int(op["entry_t"]), "open PAPER trade"
    else:
        sg = next((x for x in reversed(S.get("signals") or []) if isinstance(x, dict) and x.get("t") and trading_day(int(x["t"])) == day
                   and now - int(x.get("close_t") or int(x["t"]) + 60) <= 1800), None)
        if not sg:
            return None
        d, T, what = int(sg.get("dir") or 1), int(sg.get("close_t") or int(sg["t"]) + 60), "signal " + ("taken" if sg.get("taken") else "skipped")
    f = H.ctx(T, d)
    if not f:
        return None
    f["p_trend"] = p_trend_at(H, T)
    return {"f": f, "what": f"{'LONG' if d == 1 else 'SHORT'} {what}", "dir": d}


def p_trend_at(H: Hist, T: int, C: dict | None = None):
    """The trend-day odds known at T (None before 10:30 ET): the same number the store's p_trend column holds."""
    if not (630 <= et_mod(T) < 1080):
        return None
    i = H.idx(T)
    if i < 0:
        return None
    x = daytype_x(H, int(H.k_of[i]))
    p = daytype_prob(((C if C is not None else load_calib()).get("daytype") or {}), x) if x else None
    return _f(p, 3)


def similar(bot_key: str, live: dict | None, risk_usd=None, store=None, C=None, log_dir=None) -> dict | None:
    """The contract's similar[bot]: the k nearest past setups of a live setup."""
    if not live or not live.get("f"):
        return None
    mem = memory(bot_key, store, log_dir)
    if mem is None or not mem.rows:
        return None
    valid, cal = calib_valid(bot_key, C)
    q = mem.query(live["f"])
    if not q.get("n"):
        return None
    n, win, avg_r, sd = q["n"], q["win"], q["avg_r"], q["sd"]
    ru = _f(risk_usd)
    u = round(avg_r * ru, 0) if ru else None
    ex = []
    for j in q["idx"][:3]:
        ex.append({"day": mem.days[j], "r": round(float(mem.r[j]), 2), "usd": _f(mem.usd[j], 0)})
    conf = conf_of(n, avg_r, sd, valid)
    txt = (f"Resembles {n} past {BOTS[bot_key]} setups ({live.get('what')}): {win:.0%} won, average {avg_r:+.2f}R"
           + (f", {usd(u)} a trade at today's size" if u is not None else "") + f" (spread {sd:.2f}R). "
           + ("Similarity predicted outcomes out of sample: confidence " + conf + "." if valid else
              "Context only: out of sample, similar setups did not predict the outcome (" + str(cal.get("note") or "no calibration") + ")."))
    return {"n": int(n), "win": round(float(win), 3), "avg_r": round(float(avg_r), 3), "usd": u, "conf": conf, "valid": bool(valid),
            "examples": ex, "text": txt}


# ================================================================================================ game plans
PLAN_AT = {"lit": 105, "atlas": 105, "blitz": 645}           # ET minute: 01:45 (Zlarior + ATLAS), 10:45 (BLITZ)
LVL_KINDS = ("asia", "london", "ny", "x_ny", "pre", "pd", "pw", "pm", "buildup", "gap")


def _hist_stats(bot_key: str, pred, store=None, log_dir=None, min_n: int = 8) -> dict | None:
    """Win rate / average R / average $ of the stored setups matching pred(row dict) (plain history, not a model)."""
    mem = memory(bot_key, store, log_dir)
    if mem is None:
        return None
    rr, uu = [], []
    for j, r in enumerate(mem.rows):
        row = dict(zip(mem.cols, r))
        try:
            if pred(row):
                rr.append(float(mem.r[j])); uu.append(mem.usd[j])
        except Exception:
            continue
    if len(rr) < min_n:
        return None
    a = np.array(rr)
    u = [x for x in uu if x is not None]
    return {"n": len(rr), "win": float((a > 0).mean()), "avg_r": float(a.mean()), "avg_usd": float(np.mean(u)) if u else None}


def _sizing_for(bot, stop_pts: float, tgt_pts: float, now: int) -> dict | None:
    """Zlarior's micros / $ for a planned stop + target with the bot's own sizing math (engine/brain._sizing, read-only)."""
    try:
        from . import brain as BR
        b = getattr(bot, "brain", None) or {}
        ctx = BR.bot_ctx(bot, now)
        s = BR._sizing({"risk": float(stop_pts), "tgt": float(tgt_pts), "what": "game plan"}, ctx, b.get("rules") or {},
                       {"vix_move": ((b.get("guards") or {}).get("vix") or {}).get("move")}, b.get("price"))
        return {"qty": int(s["qty"]), "risk_usd": float(s["risk_usd"]), "win_usd": float(s["win_usd"])}
    except Exception:
        return None


def _struct(bot, now):
    try:
        from .liveview_api import structure_block
        return structure_block(bot, now, compute=False) or {}
    except Exception:
        return {}


def plan_lit(bot, H: Hist, now: int, reg: dict, store=None, log_dir=None) -> dict | None:
    b = getattr(bot, "brain", None) or {}
    if not isinstance(b, dict) or not b.get("levels"):
        return None
    i = H.idx(now) if H is not None else -1
    price = _f(b.get("price")) or (H.price(now) if H is not None else None)
    atr = _f(b.get("atr")) or (float(H.atr[i]) if i >= 0 else None)
    if price is None or not atr:
        return None
    rules = b.get("rules") or {}
    dmin = float(rules.get("depth", 0.5))
    vx = (b.get("guards") or {}).get("vix") or {}
    o18, move = _f(vx.get("open18")), _f(vx.get("move"))
    lv = [x for x in b.get("levels") or [] if isinstance(x, dict) and not x.get("taken") and _f(x.get("price")) is not None
          and (x.get("kind") in LVL_KINDS or x.get("kind") is None)]
    above = sorted([x for x in lv if float(x["price"]) > price], key=lambda x: float(x["price"]))
    below = sorted([x for x in lv if float(x["price"]) < price], key=lambda x: -float(x["price"]))
    mem = memory("lit", store, log_dir)
    scen = []
    for d, L in ((-1, above[:1]), (1, below[:1])):
        if not L:
            continue
        x = L[0]
        lvl = float(x["price"])
        side = "SHORT" if d == -1 else "LONG"
        med = None
        if mem is not None:
            sa = [float(r[mem.ci["stop_atr"]]) for r in mem.rows if r[mem.ci["dir"]] == d and _f(r[mem.ci["stop_atr"]]) is not None]
            med = float(np.median(sa)) if sa else None
        stop_pts = round(max(8.0, min(80.0, (med or 2.5) * atr)), 1)
        sweep_to = round((lvl - d * dmin * atr) * 4) / 4
        cisd = round((lvl + d * 0.5 * atr) * 4) / 4
        entry = cisd
        tgt = (o18 + d * move) if (o18 is not None and move) else None
        tgt_pts = (tgt - entry) * d if tgt is not None else None
        word = "below" if d == -1 else "above"
        then = f"Zlarior looks for a {side} 5m CISD then the 1m CISD; stop ~{stop_pts:.0f} pts (1 tick beyond the sweep extreme)"
        exp = odds = None
        sz = None
        if tgt_pts is not None and tgt_pts > 0:
            rr = tgt_pts / stop_pts
            tp = min(tgt_pts, 8.0 * stop_pts)
            sz = _sizing_for(bot, stop_pts, tp, now)
            then += f"; target band {px(tgt)} ({rr:.1f}R" + (", banked at 8R" if rr > 8 else "") + ")"
            if rr < float(rules.get("min_rr", 1.5)):
                then += f" - under {rules.get('min_rr', 1.5)}R: no trade unless the sweep goes deeper"
        if sz:
            then += f" -> {sz['qty']} micro{'s' if sz['qty'] != 1 else ''} at today's room = about {usd(sz['win_usd'])} / {usd(-sz['risk_usd'])}"
        cls = lvl_class([x.get("label"), x.get("kind")])
        hs = _hist_stats("lit", lambda r, d=d, cls=cls: r["dir"] == d and r.get("lvl") == cls, store, log_dir) or \
            _hist_stats("lit", lambda r, d=d: r["dir"] == d, store, log_dir)
        if hs:
            odds = round(hs["win"], 3)
            if sz:
                exp = round(hs["avg_r"] * sz["risk_usd"], 0)
            then += f". History: {hs['n']} Zlarior {side.lower()}s like it won {hs['win']:.0%}, average {hs['avg_r']:+.2f}R"
        scen.append({"if": f"Price sweeps the {x.get('label')} {px(lvl)} by >= {dmin:g} ATR (to ~{px(sweep_to)}) and a 5m "
                           f"candle closes back {word} ~{px(cisd)} (the CISD)",
                     "then": then, "levels": [round(lvl, 2), round(cisd, 2)] + ([round(tgt, 2)] if tgt is not None else []),
                     "exp_usd": exp, "odds": odds})
    S = _struct(bot, now)
    fr = (S.get("frames") or {}).get("1h") or {}
    prot = dict(fr.get("protected") or {})
    t1h = fr.get("trend")
    if not fr and H is not None and H.ev.get("1h") is not None and len(H.ev["1h"]["known_t"]):
        ev = H.ev["1h"]                                    # no Live View structure cached: Mind's own 1h frame (same rules)
        j = int(np.searchsorted(ev["known_t"], int(now), side="right")) - 1
        if j >= 0:
            t1h = "up" if int(ev["dir"][j]) > 0 else "down"
            prot = {"low" if t1h == "up" else "high": _f(ev["prot"][j], 2)}
    t1h = t1h or reg.get("trend")
    cm = []
    if t1h == "down" and _f(prot.get("high")):
        cm.append(f"A 1h close above {px(prot['high'])} (the 1h protected high) turns the 1h structure up: shorts would then be against it")
    elif t1h == "up" and _f(prot.get("low")):
        cm.append(f"A 1h close below {px(prot['low'])} (the 1h protected low) turns the 1h structure down: longs would then be against it")
    else:
        cm.append("A 1h break (BOS) either way would give the day a side; until then both sweeps count the same")
    w = _hist_stats("lit", lambda r: r.get("tr1h") == 1, store, log_dir)
    a = _hist_stats("lit", lambda r: r.get("tr1h") == -1, store, log_dir)
    if w and a:
        cm.append(f"(history: with the 1h trend {w['avg_r']:+.2f}R a trade, n {w['n']}; against {a['avg_r']:+.2f}R, n {a['n']}: both pay)")
    vxx = reg.get("vix")
    cm.append(f"VIX {'above 25' if not vxx or vxx < 25 else 'falling back under 25'} or a high-impact release would change the size of the move")
    tr = {"up": "longs", "down": "shorts"}.get(reg.get("trend"))
    head = (f"Zlarior game plan for {trading_day(now)}: " + (f"structure favours {tr} ({reg.get('label')})" if tr else f"no structure side ({reg.get('label')})")
            + (f"; VIX band {px(o18 - move)} / {px(o18 + move)}" if o18 is not None and move else ""))
    return {"t": int(now), "headline": head, "scenarios": scen, "change_mind": "; ".join(cm) + "."}


def plan_atlas(bot, H: Hist, now: int, reg: dict, store=None, log_dir=None) -> dict | None:
    sec = getattr(bot, "second", None) or {}
    mem_ok = memory("atlas", store, log_dir) is not None
    scen, idle = [], []
    for k, s in ((sec.get("strategies") or {}) if isinstance(sec, dict) else {}).items():
        m = member_of(k)
        if not m or not isinstance(s, dict) or s.get("on") is False:
            continue
        st = s.get("state") or {}
        br = s.get("brain") or {}
        if st.get("stage") in ("off", "done", "error"):
            idle.append(f"{s.get('short') or k} {'done for today' if st.get('stage') == 'done' else 'off now'}")
            continue
        lv = [round(float(x["px"]), 2) for x in br.get("levels") or [] if isinstance(x, dict) and _f(x.get("px")) is not None][:3]
        pl = br.get("plan") if isinstance(br.get("plan"), dict) else {}
        d = _dir_from_text(st.get("text"))
        hs = _hist_stats("atlas", (lambda r, m=m, d=d: r.get("member") == m and (d is None or r["dir"] == d)), store, log_dir) if mem_ok else None
        ff = br.get("first_fail")
        then = f"ATLAS {s.get('short') or k} " + (f"takes the {'long' if d == 1 else 'short'}" if d else "looks for its entry") + \
            " (account B sizes it; paper here)"
        if hs:
            then += f". History: {hs['n']} {m} trades like it won {hs['win']:.0%}, average {hs['avg_r']:+.2f}R"
        scen.append({"if": f"{s.get('short') or k}: " + str(st.get("text") or ff or "waits for its signal")[:200], "then": then,
                     "levels": lv + ([round(float(pl["entry"]), 2)] if _f(pl.get("entry")) is not None else []),
                     "exp_usd": round(hs["avg_usd"], 0) if hs and hs.get("avg_usd") is not None else None,
                     "odds": round(hs["win"], 3) if hs else None})
    if not scen and not idle:
        return None
    S = _struct(bot, now)
    note = ((S.get("per_strategy") or {}).get("atlas") or {}).get("note")
    note = (note or "A 15m / 1h break against the members' side would put them on the other side").rstrip(".") + "."
    return {"t": int(now), "headline": f"ATLAS game plan: {len(scen)} member{'s' if len(scen) != 1 else ''} on watch"
                                       + (f" ({', '.join(idle)})" if idle else "") + f"; {reg.get('label')}",
            "scenarios": scen[:4], "change_mind": note + " A 1h trend flip changes which members can fire."}


def plan_blitz(bot, H: Hist, now: int, reg: dict, store=None, log_dir=None) -> dict | None:
    S = getattr(bot, "blitz", None)
    if not isinstance(S, dict) or not S.get("eng"):
        return None
    from . import blitz as BZ
    E = S.get("eng") or {}
    day = BZ.et_date(now)
    b = BZ.Engine(E).band_now() if E.get("date") == day else None
    if not b or not b.get("ready"):
        return {"t": int(now), "headline": "BLITZ game plan: the noise band is not ready yet (needs today's 09:30 open)", "scenarios": [],
                "change_mind": "The plan comes once the band is known."}
    dt_ = (reg.get("day_type") or {})
    p = dt_.get("p_trend")
    if b.get("day_ok") is False:
        return {"t": int(now), "headline": f"BLITZ game plan: NO trades today: the day filter is off (yesterday's range {float(b.get('prng') or 0):.2f}x "
                                           "its 14-day average, needs 0.8x)", "scenarios": [],
                "change_mind": "Nothing changes it today: the filter is decided before the open."}
    rows = [r for r in b.get("checks") or [] if r.get("up") is not None]
    nxt = next((r for r in rows if int(r["t"]) > now), None)
    i = H.idx(now) if H is not None else -1
    atr = float(H.atr[i]) if i >= 0 else None
    ev = BZ.eval_view(S) or {}
    room = _f(ev.get("room"))
    scen = []
    pb = (lambda r: (r.get("p_trend") is not None and r["p_trend"] >= 0.4)) if (p is not None and p >= 0.4) else \
        (lambda r: (r.get("p_trend") is not None and r["p_trend"] < 0.2)) if (p is not None and p < 0.2) else \
        (lambda r: (r.get("p_trend") is not None and 0.2 <= r["p_trend"] < 0.4)) if p is not None else (lambda r: True)
    if nxt:
        for d, lvl in ((1, nxt["up"]), (-1, nxt["lo"])):
            side = "LONG" if d == 1 else "SHORT"
            stop = round(1.5 * atr, 1) if atr else None
            q = rpm = None
            if stop and room is not None:
                rpm = stop * PV + 1.90 + 0.5
                q = BZ.qty(rpm, room, float(ev.get("today") or 0))
            hs = _hist_stats("blitz", lambda r, d=d, pb=pb: r["dir"] == d and pb(r), store, log_dir, min_n=6)
            then = f"BLITZ PAPER {side} at the next open, stop 1.5 x 5m ATR (~{stop:.0f} pts)" if stop else f"BLITZ PAPER {side} at the next open"
            if q:
                then += f" -> {q} micros on the paper 25K = {usd(-q * rpm)} if stopped; trail 1.5R after +1R, out after 30 bars"
            if hs:
                then += f". History on days like today: {hs['n']} {side.lower()}s won {hs['win']:.0%}, average {hs['avg_r']:+.2f}R"
            scen.append({"if": f"A 1m close at the {nxt.get('hm')} check (or a later one) goes {'above' if d == 1 else 'below'} "
                               f"{px(lvl)} (the {'upper' if d == 1 else 'lower'} noise band)",
                         "then": then, "levels": [round(float(lvl), 2)],
                         "exp_usd": round(hs["avg_r"] * q * rpm, 0) if (hs and q) else None, "odds": round(hs["win"], 3) if hs else None})
    hi = _hist_stats("blitz", lambda r: r.get("p_trend") is not None and r["p_trend"] >= 0.4, store, log_dir, min_n=5)
    lo = _hist_stats("blitz", lambda r: r.get("p_trend") is not None and r["p_trend"] < 0.2, store, log_dir, min_n=5)
    cm = "A first hour inside its average range with no close outside the band by 12:00 points to a range day"
    if hi and lo:
        cm += f" (history: trend-day odds >= 40% {hi['avg_r']:+.2f}R a trade, n {hi['n']}; under 20% {lo['avg_r']:+.2f}R, n {lo['n']})"
    head = f"BLITZ game plan: day filter ON (yesterday's range {float(b.get('prng') or 0):.2f}x its average)" + \
        (f", trend-day odds {p:.0%}" if p is not None else "")
    return {"t": int(now), "headline": head, "scenarios": scen, "change_mind": cm + "."}


PLANNERS = {"lit": plan_lit, "atlas": plan_atlas, "blitz": plan_blitz}


# ================================================================================================ reviews (after each close)
RULE_EXITS = {"TARGET", "STOP", "BE", "TIME", "TCHECK", "T15", "EOD", "FLAT", "BANK", "CUT", "HEDGE", "LIT FIRST", "TRAIL"}
REVIEW_BACK_S = 2 * 86400                                    # trades that closed longer ago are not reviewed (first start)


def closed_trades(bot) -> list:
    """Every finished trade the bot knows (Zlarior's routed ledger, ATLAS members' paper trades, BLITZ paper) in one shape."""
    from . import advisor as AD
    out = []
    for nm, fn in (("lit", AD._ledger_trades), ("atlas", AD._second_trades), ("blitz", AD._blitz_trades)):
        try:
            for t in fn(bot):
                if nm == "atlas" and not member_of(t.get("key")):
                    continue
                if t.get("entry_t") is None or t.get("exit_t") is None or t.get("exit_kind") in (None, "", "OPEN"):
                    continue
                out.append({**t, "bot": nm})
        except Exception:
            continue
    return out


def _risk_pts(t: dict):
    """The trade's planned risk in points: its own risk_pts (ATLAS / BLITZ rows; the stop may since have moved to BE), else
    |entry - first stop|."""
    rp = _f(t.get("risk_pts"))
    if rp and rp > 0:
        return rp
    e, s = _f(t.get("entry")), _f(t.get("stop0")) or _f(t.get("stop"))
    return abs(e - s) if e is not None and s is not None and e != s else None


def _r_of(t: dict):
    r = _f(t.get("r"))
    if r is not None:
        return r
    rp, q, u = _risk_pts(t), _f(t.get("qty")), _f(t.get("usd"))
    if not rp or not q or u is None:
        return None
    return u / (rp * PV * q)


def _path(H: Hist | None, t: dict):
    """(MFE R, MAE R) from the 5m bars between entry and exit (approximate: 5m highs / lows)."""
    if H is None:
        return None, None
    e, risk = _f(t.get("entry")), _risk_pts(t)
    if e is None or not risk:
        return None, None
    d = int(t.get("dir") or 1)
    a = int(np.searchsorted(H.t, int(t["entry_t"]) // 300 * 300))
    z = int(np.searchsorted(H.t, int(t["exit_t"]), side="right"))
    if z <= a:
        return None, None
    fav = ((H.h[a:z] - e) if d == 1 else (e - H.l[a:z])).max() / risk
    adv = ((e - H.l[a:z]) if d == 1 else (H.h[a:z] - e)).max() / risk
    return round(float(fav), 2), round(float(max(0.0, adv)), 2)


def _advice_of(t: dict, adv_dir: str | None = None):
    from . import advisor as AD
    strat = {"lit": "lit", "atlas": "atlas", "blitz": "scalp"}[t["bot"]]
    key = f"{strat}|{t.get('day') or trading_day(int(t['entry_t']))}|{int(t['entry_t'])}|{int(t['dir'])}"
    for r in reversed(AD._jl_read(AD._p(adv_dir, f"{strat}.jsonl"))):
        if r.get("key") == key:
            return r
    return None


def review(t: dict, H: Hist | None, store=None, C=None, log_dir=None, adv_dir=None, now: int | None = None) -> dict:
    """The contract's review of one closed trade: grade, right / wrong, lesson, luck or skill."""
    bot = t["bot"]
    d = int(t.get("dir") or 1)
    r = _r_of(t)
    ek = str(t.get("exit_kind") or "").upper()
    valid, _cal = calib_valid(bot, C)
    exp = None
    if H is not None:
        f = H.ctx(int(t["entry_t"]), d)
        if f:
            if bot == "atlas":
                f["member"] = member_of(t.get("key"))
            if t.get("entry") is not None and t.get("stop") is not None and f.get("atr"):
                f["stop_atr"] = round(_risk_pts(t) / f["atr"], 3) if _risk_pts(t) else None
            mem = memory(bot, store, log_dir)
            if mem is not None:
                q = mem.query(f, exclude_day=t.get("day") or trading_day(int(t["entry_t"])))
                if q.get("n"):
                    exp = q
    mfe, mae = _path(H, t)
    right, wrong = [], []
    score = 1.0
    if ek in RULE_EXITS or ek.startswith(("TARGET", "STOP", "BE", "TIME", "FLAT")):
        score += 1.0
        right.append(f"Plan followed: the written rules closed it ({ek.lower()})")
    elif ek in ("KILL", "KILL SWITCH", "REMOTE FLATTEN", "TIME SAFETY", "MANUAL"):
        score -= 0.5
        wrong.append(f"Closed outside the plan ({ek.lower()})")
    if exp:
        w = 1.0 if valid else 0.5
        if exp["avg_r"] >= 0.5:
            score += w
            right.append(f"Good setup: {exp['n']} similar setups averaged {exp['avg_r']:+.2f}R" + ("" if valid else " (context only)"))
        elif exp["avg_r"] <= 0:
            score -= w
            wrong.append(f"Weak setup: {exp['n']} similar setups averaged {exp['avg_r']:+.2f}R" + ("" if valid else " (context only)"))
    if r is not None:
        if r >= 0.1:
            score += 1.0
            right.append(f"Result {r:+.2f}R ({usd(t.get('usd')) if t.get('usd') is not None else 'paper'})")
        elif r > -0.1:
            score += 0.5
            right.append(f"Scratch {r:+.2f}R ({usd(t.get('usd')) if t.get('usd') is not None else 'paper'}): the risk came off")
        elif r < -0.5:
            score -= 0.5
            wrong.append(f"Result {r:+.2f}R ({usd(t.get('usd')) if t.get('usd') is not None else 'paper'})")
    rec = None
    try:
        rec = _advice_of(t, adv_dir)
    except Exception:
        rec = None
    best = None
    if rec:
        fired = [a for a in rec.get("advice") or [] if a.get("fired")]
        best = max(fired, key=lambda a: a.get("delta_usd") or 0, default=None)
        risk_usd = (_risk_pts(t) or 0.0) * PV * float(t.get("qty") or 1)
        if best and (best.get("delta_usd") or 0) > 0.25 * max(risk_usd, 1):
            score -= 0.5
            wrong.append(f"Management: the advisor's {best['rule']} would have made {usd(best['delta_usd'])} more")
        elif fired and all((a.get("delta_usd") or 0) <= 0 for a in fired):
            score += 0.5
            right.append("Management beat every structure rule the advisor tried")
    if mfe is not None and r is not None and r < 0.1 and mfe >= 1.0:
        wrong.append(f"It was +{mfe:.1f}R first and still closed at {r:+.2f}R")
        if mfe >= 2.0:
            score -= 0.5
    grade = "A" if score >= 3.5 else "B" if score >= 2.5 else "C" if score >= 1.5 else "D" if score >= 0.5 else "F"
    # luck or skill: outcome vs what similar setups made (only when similarity predicts), else the trade's own path
    if valid and exp and r is not None:
        e = exp["avg_r"]
        luck = "skill" if ((r > 0 and e >= 0.3) or (r <= 0 and e < 0)) else "luck" if ((r > 0 and e < 0) or (r <= 0 and e >= 0.3)) else "mixed"
        why = f"similar setups averaged {e:+.2f}R, this one made {r:+.2f}R"
    elif r is not None and mae is not None:
        if r > 0:
            luck = "luck" if mae >= 0.8 else "skill" if mae < 0.5 else "mixed"
            why = f"it went {mae:.1f}R against first" + (" - nearly stopped" if mae >= 0.8 else "")
        else:
            luck = "skill" if (mfe is not None and mfe < 0.3) else "luck" if (mfe is not None and mfe >= 1.0) else "mixed"
            why = ("the setup failed at once (never +0.3R): a read error, not bad luck" if luck == "skill" else
                   f"it was +{mfe:.1f}R first: the market took it back" if luck == "luck" else f"best +{mfe or 0:.1f}R before the loss")
    else:
        luck, why = "mixed", "not enough data to tell luck from skill"
    scratch = r is not None and abs(r) < 0.1
    if scratch:                                   # breakeven / a scratch: neither a win nor a loss
        luck = "mixed"
        why = "a scratch (about 0R): no money either way" + (f"; it was +{mfe:.1f}R first" if mfe else "")
    if scratch:
        lesson = (f"Scratch, but it was +{mfe:.1f}R first and gave it all back: a structure trail (the advisor's trail_15m / trail_5m) "
                  "would have kept part of it - advice only, the rules decide." if (mfe or 0) >= 2.0 else
                  f"Scratch: it was +{mfe:.1f}R first and the breakeven stop took the risk off - the rule did its job." if (mfe or 0) >= 1.0
                  else "Scratch trade: nothing to learn from the result itself.")
    elif r is not None and r > 0:
        lesson = ("Clean setup, clean result: the trade to repeat." if luck == "skill" else
                  "Won, but it nearly stopped first: don't read too much into it." if luck == "luck" else "A fair trade that paid.")
    elif r is not None:
        lesson = ("The setup was wrong from the start: note what it shared with other quick losses (the nightly research looks)." if luck == "skill"
                  else "Good trade, bad outcome: the market took back a move in our favour; the rules stay." if luck == "luck"
                  else "A normal loss inside the plan: size kept it small.")
    else:
        lesson = "Not enough data on this trade for a lesson."
    if best and (best.get("delta_usd") or 0) > 0:
        lesson += f" Advisor note: {best['rule']} ({usd(best['delta_usd'])}) - advice only, the rules decide."
    when = _et(int(t["entry_t"]))
    label = (f"{t.get('day') or trading_day(int(t['entry_t']))} {BOTS[bot]}{(' ' + str(t.get('key'))) if bot == 'atlas' else ''} "
             f"{'LONG' if d == 1 else 'SHORT'} {when:%H:%M} -> {ek} " + (f"{r:+.2f}R" if r is not None else ""))
    return {"t": int(now or t.get("exit_t") or time.time()), "bot": bot, "trade": label.strip(), "grade": grade, "right": right[:4],
            "wrong": wrong[:4], "lesson": lesson, "luck": luck, "why": why, "entry_t": int(t["entry_t"]), "r": _f(r, 3),
            "usd": _f(t.get("usd"), 2), "exp_r": _f((exp or {}).get("avg_r"), 3), "exp_n": (exp or {}).get("n"), "mfe": mfe, "mae": mae}


def _trade_key(t: dict) -> str:
    return f"{t['bot']}|{t.get('key') or ''}|{int(t['entry_t'])}|{int(t.get('dir') or 0)}"


# ================================================================================================ self-research (nightly)
COMM = 1.90
BLITZ_RISK = 150.0                                            # BLITZ store rows carry R only: $ at $150 risk a trade
HALVES = {"london": 210, "asia": 240, "pre": 405, "ny_am": 585, "lunch": 735, "ny_pm": 885}   # ET minute splitting each killzone


def _et_min(row) -> int | None:
    m = _i(row.get("mod"))
    return None if m is None else (m + 1080) % 1440


def _hm_of(m) -> str:
    return f"{int(m) // 60:02d}:{int(m) % 60:02d}"


def _buckets(bot: str, rows: list, cols: list) -> list:
    """(id, words, predicate) buckets the research looks at (time, side, structure, VIX, ranges, member, day-type odds)."""
    R = [dict(zip(cols, r)) for r in rows]
    B = []
    for kz, split in HALVES.items():
        B.append((f"kz-{kz}", f"in {KZ_WORD[kz]}", lambda r, kz=kz: r.get("kz") == kz if r.get("kz") is not None else killzone(_et_min(r) or 0) == kz))
        B.append((f"kz-{kz}-late", f"in {KZ_WORD[kz]} after {_hm_of(split)} ET",
                  lambda r, kz=kz, s=split: killzone(_et_min(r) or 0) == kz and ((_et_min(r) or 0) - s) % 1440 < 720))
    B += [("dir-long", "on longs", lambda r: r.get("dir") == 1), ("dir-short", "on shorts", lambda r: r.get("dir") == -1),
          ("tr1h-against", "against the 1h structure trend", lambda r: r.get("tr1h") == -1),
          ("tr1h-with", "with the 1h structure trend", lambda r: r.get("tr1h") == 1),
          ("tr15-against", "against the 15m structure trend", lambda r: r.get("tr15") == -1),
          ("prev-small", "after a small prior day (< 0.8x its average range)", lambda r: _f(r.get("prev_rng")) is not None and r["prev_rng"] < 0.8),
          ("prev-big", "after a big prior day (> 1.3x its average range)", lambda r: _f(r.get("prev_rng")) is not None and r["prev_rng"] > 1.3),
          ]
    ar = sorted(float(r["atr_r"]) for r in R if _f(r.get("atr_r")) is not None)
    if len(ar) > 30:
        hi = ar[2 * len(ar) // 3]
        B.append(("atr-hot", f"when the 5m ATR is above {hi:.2f}x its 7-day median (its top third)",
                  lambda r, hi=hi: _f(r.get("atr_r")) is not None and r["atr_r"] > hi))
    vx = sorted(float(r["vix"]) for r in R if _f(r.get("vix")) is not None)
    if len(vx) > 30:
        lo, hi = vx[len(vx) // 3], vx[2 * len(vx) // 3]
        B += [(f"vix-low", f"with VIX under {lo:.1f}", lambda r, lo=lo: _f(r.get("vix")) is not None and r["vix"] < lo),
              (f"vix-high", f"with VIX above {hi:.1f}", lambda r, hi=hi: _f(r.get("vix")) is not None and r["vix"] > hi)]
    sa = sorted(float(r["stop_atr"]) for r in R if _f(r.get("stop_atr")) is not None)
    if len(sa) > 30:
        hi = sa[2 * len(sa) // 3]
        B.append(("stop-wide", f"with a wide stop (> {hi:.1f} ATR)", lambda r, hi=hi: _f(r.get("stop_atr")) is not None and r["stop_atr"] > hi))
    for dw, nm in enumerate(("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")):
        B.append((f"dow-{dw}", f"on {nm}s", lambda r, dw=dw: r.get("dow") == dw))
    if bot == "lit":
        for c in ("asia", "london", "ny", "htf", "buildup"):
            B.append((f"lvl-{c}", f"after a {c} level sweep", lambda r, c=c: r.get("lvl") == c))
        B.append(("idm-0", "with no inducement", lambda r: _i(r.get("idm_n")) == 0))
    if bot == "atlas":
        for m in ("EMA", "MD", "SR"):
            B.append((f"member-{m.lower()}", f"for the {m} member", lambda r, m=m: r.get("member") == m))
    if bot in ("blitz", "atlas"):
        B += [("ptrend-hi", "on days with trend-day odds >= 40% at 10:30", lambda r: _f(r.get("p_trend")) is not None and r["p_trend"] >= 0.4),
              ("ptrend-lo", "on days with trend-day odds under 20% at 10:30", lambda r: _f(r.get("p_trend")) is not None and r["p_trend"] < 0.2)]
    return B


def _usd_rows(bot, R: list, mult) -> np.ndarray:
    """$ of each row at a size multiplier (exact linear re-size on the stored micros, floor 1 micro, 0 = skipped)."""
    out = np.zeros(len(R))
    for j, r in enumerate(R):
        m = float(mult[j])
        if bot == "blitz" or _f(r.get("usd")) is None or not _i(r.get("qty")):
            out[j] = (_f(r.get("r")) or 0.0) * BLITZ_RISK * m
            continue
        q0 = int(r["qty"])
        if m <= 0:
            continue
        q = max(1, int(q0 * m + 1e-9)) if m < 1 else int(q0 * m + 1e-9)
        per = (float(r["usd"]) + COMM * q0) / q0
        out[j] = per * q - COMM * q
    return out


def _span_stats(R: list, U: np.ndarray, kept: np.ndarray, sp) -> dict:
    ix = [j for j, r in enumerate(R) if _span(r["day"], sp)]
    if not ix:
        return {"n": 0}
    days = [R[j]["day"] for j in ix]
    d0, d1 = dt.date.fromisoformat(min(days)), dt.date.fromisoformat(max(days))
    weeks = max(1.0, ((d1 - d0).days + 1) / 7.0)
    months = max(1.0, ((d1 - d0).days + 1) / 30.44)
    u = np.array([U[j] for j in ix if kept[j]])
    n = len(u)
    wk = {}
    for j in ix:
        if kept[j]:
            y, w, _ = dt.date.fromisoformat(R[j]["day"]).isocalendar()
            wk[(y, w)] = wk.get((y, w), 0) + 1
    gl = -u[u < 0].sum() if n else 0.0
    eq = np.cumsum(u) if n else np.zeros(1)
    dd = float((eq - np.maximum.accumulate(np.r_[0.0, eq])[1:]).min()) if n else 0.0
    return {"n": n, "tpw": round(n / weeks, 2), "net": round(float(u.sum()) if n else 0.0), "pf": round(float(u[u > 0].sum() / gl), 2) if gl else None,
            "per_month": round(float(u.sum()) / months if n else 0.0), "dd": round(dd),
            "wk2": round(100.0 * sum(1 for v in wk.values() if v >= 2) / max(1, int(round(weeks))), 1)}


def test_rule(bot: str, R: list, pred, mult: float) -> dict:
    """The rule (size x mult when pred) vs the stored live rule on 2026 H1 / H2 / 2021-25."""
    m_rule = np.array([mult if pred(r) else 1.0 for r in R])
    base, alt = _usd_rows(bot, R, np.ones(len(R))), _usd_rows(bot, R, m_rule)
    kept_b, kept_a = np.ones(len(R), bool), m_rule > 0
    out = {}
    for nm, sp in (("H1", H1), ("H2", H2), ("2021-25", R2125)):
        b, a = _span_stats(R, base, kept_b, sp), _span_stats(R, alt, kept_a, sp)
        if b.get("n"):
            out[nm] = {"base": b, "rule": a, "d_net": a["net"] - b["net"], "d_month": a["per_month"] - b["per_month"],
                       "n_hit": int(sum(1 for r in R if _span(r["day"], sp) and pred(r)))}
            if bot == "lit":                                  # the owner's eval-speed numbers on the MFFU 50K (runlib.eval_speed)
                try:
                    out[nm]["eval"] = {"base": eval_speed(R, base, kept_b, sp), "rule": eval_speed(R, alt, kept_a, sp)}
                except Exception:
                    pass
    return out


_SESS: dict = {}


def sessions() -> list:
    """Every trading session of the research history (run lit_live's day list), for the eval-speed simulation."""
    if "v" not in _SESS:
        d = _read_json(os.path.join(ROOT, "research", "runs", "lit_live.json"), {}) or {}
        _SESS["v"] = [r[0] for r in d.get("days") or []]
    return _SESS["v"]


def eval_speed(R: list, U: np.ndarray, kept: np.ndarray, sp, horizon: int = 60) -> dict | None:
    """tools/runlib.eval_speed on the rule's day P&L (a fresh MFFU Builder 50K eval started on every session of the span):
    p10 / f10, p15 / f15 (% passed / failed within 10 / 15 sessions), dec10, slow_pass, pass_med."""
    from .analytics import PLANS, simulate_eval
    ss = [d for d in sessions() if _span(d, sp)]
    if not ss:
        return None
    by: dict = {}
    for j, r in enumerate(R):
        if kept[j] and _span(r["day"], sp):
            by.setdefault(r["day"], []).append(float(U[j]))
    pn, lo = [], []
    for d in ss:
        cum = low = 0.0
        for p in by.get(d, []):
            low = min(low, cum + min(0.0, p)); cum += p; low = min(low, cum)
        pn.append(cum); lo.append(low)
    plan = PLANS["builder_50k"]
    res = [simulate_eval(pn[i:i + horizon], plan, lo[i:i + horizon]) for i in range(len(ss))]
    n = len(res) or 1
    passes = [x["days"] for x in res if x["result"] == "PASS"]
    out = {}
    for Hh in (10, 15):
        out[f"p{Hh}"] = round(100 * sum(1 for x in res if x["result"] == "PASS" and x["days"] <= Hh) / n, 1)
        out[f"f{Hh}"] = round(100 * sum(1 for x in res if x["result"] == "FAIL" and x["days"] <= Hh) / n, 1)
    out["dec10"] = round(out["p10"] + out["f10"], 1)
    out["slow_pass"] = round(100 * sum(1 for d in passes if d > 15) / len(passes), 1) if passes else None
    out["pass_med"] = float(np.median(passes)) if passes else None
    return out


def _ev_txt(nm, x, unit="$") -> str:
    if not x:
        return f"{nm}: no trades"
    b, a = x["base"], x["rule"]
    s = (f"{nm}: {x['d_net']:+,.0f} {unit} vs live ({x['n_hit']} of {b['n']} trades hit; PF {b['pf']} -> {a['pf']}, "
         f"{a['tpw']}/wk, {a['per_month']:+,.0f} {unit}/mo, max DD {a['dd']:,})")
    e = x.get("eval") or {}
    if e.get("base") and e.get("rule"):
        eb, ea = e["base"], e["rule"]
        s += (f"; 50K eval in 2 weeks pass/fail {eb['p10']:.0f}/{eb['f10']:.0f}% -> {ea['p10']:.0f}/{ea['f10']:.0f}%, "
              f"median pass {eb['pass_med']} -> {ea['pass_med']} sessions")
    return s


def judge_rule(bot: str, ev: dict, mult: float) -> tuple:
    """(status, why). Zlarior: picked on 2026 H1, checked on 2026 H2 (2021-25 reference only, CLAUDE.md LIT exception).
    ATLAS / BLITZ: better on H1, H2 and 2021-25 (where there are trades). Always 2+ trades a week."""
    h1, h2, r5 = ev.get("H1"), ev.get("H2"), ev.get("2021-25")
    if not h1 or not h2:
        return "rejected", "not enough trades in 2026 H1 / H2 to judge"
    if h1["n_hit"] < 5 or h2["n_hit"] < 3:
        return "rejected", f"too few trades hit ({h1['n_hit']} in H1, {h2['n_hit']} in H2) to trust"
    if h1["d_net"] <= 0:
        return "rejected", "does not help 2026 H1 (the pick half)"
    if h2["d_net"] <= 0:
        return "rejected", "helped H1 but not the H2 check: a fit to H1"
    if bot != "lit" and r5 and r5["d_net"] <= 0:
        return "rejected", "helped 2026 but not 2021-25"
    if (h2["rule"].get("tpw") or 0) < 2.0 and mult == 0:
        return "rejected", "leaves fewer than 2 trades a week"
    return "candidate", "better on the pick half and the check half" + ("" if bot == "lit" else " and 2021-25")


def observations(bot: str, R: list, buckets: list, last_n: int = 40) -> list:
    """What Mind noticed in its own recent trades: where the recent losses bunch up, where the money came from."""
    out = []
    rec = sorted(R, key=lambda r: r.get("t") or 0)[-last_n:]
    loss = [r for r in rec if (_f(r.get("r")) or 0) < -0.2]
    for bid, words, pred in buckets:
        try:
            hl = sum(1 for r in loss if pred(r))
            ht = sum(1 for r in rec if pred(r))
        except Exception:
            continue
        if len(loss) >= 4 and hl >= 3 and hl / len(loss) >= 0.5 and (ht / max(1, len(rec))) < hl / len(loss):
            out.append({"kind": "losses", "bucket": bid, "text": f"{hl} of the last {len(loss)} {BOTS[bot]} losses came {words} "
                                                                f"({ht} of its last {len(rec)} trades, history + live, were there)",
                        "score": hl / len(loss)})
    R26 = [r for r in R if r["day"] >= "2026"]
    tot = sum(float(r.get("r") or 0) for r in R26)
    if tot > 0 and len(R26) >= 30:
        for bid, words, pred in buckets:
            try:
                s = [r for r in R26 if pred(r)]
            except Exception:
                continue
            got = sum(float(r.get("r") or 0) for r in s)
            if len(s) >= 10 and got / tot >= 0.6 and len(s) / len(R26) <= 0.45:
                out.append({"kind": "money", "bucket": bid, "text": f"{BOTS[bot]} trades {words} made {got / tot:.0%} of its 2026 R "
                                                                    f"with {len(s) / len(R26):.0%} of the trades", "score": got / tot})
    out.sort(key=lambda o: -o["score"])
    return out[:6]


def change_text(bot: str, words: str, mult: float, focus: bool) -> str:
    what = (f"x{mult:g} size {words}" if not focus else f"x{mult:g} size on every trade NOT {words}") if mult > 0 else f"skip trades {words}"
    where = {"lit": 'live_model.json + live_model_lit.json "lit" (a lit_sizing size rule; then python tools/lit_losses.py live)',
             "atlas": 'second_model.json (the ATLAS member / account B sizing)',
             "blitz": 'second_model.json "blitz" (the paper shadow sizing)'}[bot]
    return f"{BOTS[bot]}: {what}. Where: {where}. Not built yet: the owner approves first, then it is built and re-tested in the run library."


def research(budget_s: float = 600.0, store: dict | None = None, log_dir: str | None = None, now: int | None = None,
             write: bool = True) -> dict:
    """The nightly self-research: observations -> hypotheses -> tests -> proposals. Never adopts anything."""
    t_start = time.monotonic()
    now = int(now or time.time())
    S = store if store is not None else load_store()
    ld = log_dir or LOG_DIR
    prev = {p["id"]: p for p in ((_read_json(os.path.join(ld, "proposals.json"), {}) or {}).get("proposals") or []) if isinstance(p, dict)}
    props, obs_all, tested = [], [], 0
    for bot in BOTS:
        blk = (S.get("bots") or {}).get(bot)
        if not blk:
            continue
        cols = blk["cols"]
        R = [dict(zip(cols, r)) for r in list(blk["rows"]) + [x for x in live_rows(bot, ld) if isinstance(x, list) and len(x) == len(cols)]]
        B = _buckets(bot, blk["rows"], cols)
        bmap = {b[0]: b for b in B}
        obs = observations(bot, R, B)
        obs_all += [{**o, "bot": bot} for o in obs]
        hyps = []
        for o in obs:
            bid, words, pred = bmap[o["bucket"]]
            if o["kind"] == "losses":
                hyps.append((f"{bot}-{bid}-half", f"Half size for {BOTS[bot]} trades {words}", pred, 0.5, False, o["text"], words))
                hyps.append((f"{bot}-{bid}-skip", f"Skip {BOTS[bot]} trades {words}", pred, 0.0, False, o["text"], words))
            else:
                hyps.append((f"{bot}-{bid}-focus", f"Half size for {BOTS[bot]} trades NOT {words}", (lambda r, p=pred: not p(r)), 0.5, True,
                             o["text"], words))
        for hid, idea, pred, mult, focus, why, words in hyps:
            if time.monotonic() - t_start > budget_s:
                props.append({"id": hid, "bot": bot, "idea": idea, "evidence": {"h1": "", "h2": "", "r2125": "", "usd_month": None},
                              "status": "testing", "t": now, "change": None, "why": why})
                continue
            ev = test_rule(bot, R, pred, mult)
            tested += 1
            st, verdict = judge_rule(bot, ev, mult)
            unit = "$"
            props.append({"id": hid, "bot": bot, "idea": idea,
                          "evidence": {"h1": _ev_txt("2026 H1 (pick)", ev.get("H1"), unit), "h2": _ev_txt("2026 H2 (check)", ev.get("H2"), unit),
                                       "r2125": _ev_txt("2021-25" + (" (reference)" if bot == "lit" else ""), ev.get("2021-25"), unit),
                                       "usd_month": _f((ev.get("H2") or {}).get("d_month"), 0),
                                       **({"note": "BLITZ $ at $150 risk a trade (the store has R only)"} if bot == "blitz" else {})},
                          "status": st, "t": now, "change": change_text(bot, words, mult, focus) if st == "candidate" else None,
                          "why": f"{why}. Verdict: {verdict}.", "first_t": (prev.get(hid) or {}).get("first_t") or now})
    took = round(time.monotonic() - t_start, 2)
    order = {"candidate": 0, "testing": 1, "rejected": 2}
    keep = {p["id"]: p for p in prev.values()}
    for p in props:
        keep[p["id"]] = p
    allp = sorted(keep.values(), key=lambda p: (order.get(p.get("status"), 3), -(p.get("t") or 0)))[:60]
    out = {"v": VERSION, "t": now, "took_s": took, "tested": tested, "observations": obs_all, "proposals": allp,
           "note": "Mind's own research: it never adopts anything. A candidate holds on the pick half and the check half; the "
                   "owner decides, then it is built and re-tested in the run library (tools/runlib.py)."}
    if write:
        _write_json(os.path.join(ld, "proposals.json"), out)
    return out


def proposals(log_dir: str | None = None) -> list:
    d = _read_json(os.path.join(log_dir or LOG_DIR, "proposals.json")) or _read_json(SEED_PROPOSALS) or {}
    return [p for p in d.get("proposals") or [] if isinstance(p, dict)]


def spawn_research(budget_s: int = 600, log_dir: str | None = None) -> int | None:
    """Start the nightly research as a low-priority child process (nice 15 / BELOW_NORMAL on Windows), capped at budget_s
    inside the job. Returns its pid or None. Never raises."""
    try:
        import subprocess
        import sys
        ld = log_dir or LOG_DIR
        os.makedirs(ld, exist_ok=True)
        log = open(os.path.join(ld, "research.log"), "a", encoding="utf-8")
        cmd = [sys.executable, "-X", "utf8", "-m", "engine.mind", "research", "--budget", str(int(budget_s))]
        if log_dir:
            cmd += ["--log-dir", ld]
        kw = {"cwd": ROOT, "stdout": log, "stderr": log, "stdin": subprocess.DEVNULL}
        if os.name == "nt":
            kw["creationflags"] = 0x00004000 | 0x08000000            # BELOW_NORMAL_PRIORITY_CLASS | CREATE_NO_WINDOW
        else:
            kw["preexec_fn"] = lambda: os.nice(15)
        p = subprocess.Popen(cmd, **kw)
        return p.pid
    except Exception:
        return None


# ================================================================================================ the Mind (state + block)
class Mind:
    def __init__(self, log_dir: str | None = None):
        from collections import deque
        self.mx = threading.Lock()
        self.log_dir = log_dir
        self.block: dict | None = None
        self.key = None
        self.thread: threading.Thread | None = None
        self.plans: dict = {}
        self.frozen: dict = {}
        self.reviews = deque(maxlen=50)
        self.reviewed: set | None = None
        self.alerts = deque(maxlen=30)
        self.events = deque(maxlen=80)
        self.history = deque(maxlen=300)
        self.last_regime = None
        self.ms = None
        self.research_day = None
        self.err = None

    @property
    def ld(self):
        return self.log_dir or LOG_DIR

    def _event(self, key, t, bot, kind, title, text, level="info"):
        self.events.append({"key": key, "t": int(t), "bot": bot, "kind": kind, "title": str(title)[:120], "text": str(text)[:400], "level": level})

    def _alert(self, t, bot, text, level="info"):
        self.alerts.append({"t": int(t), "bot": bot, "text": str(text)[:240], "level": level})

    def _restore(self):
        if self.reviewed is not None:
            return
        rows = _jl_read(os.path.join(self.ld, "reviews.jsonl"), 400)
        self.reviewed = {r.get("key") for r in rows if isinstance(r, dict)}
        for r in rows[-50:]:
            if isinstance(r, dict):
                self.reviews.append({k: v for k, v in r.items() if k != "key"})
        for r in _jl_read(os.path.join(self.ld, "plans.jsonl"), 20):
            if isinstance(r, dict) and r.get("bot") and r.get("day"):
                self.frozen[r["bot"]] = r["day"]

    def compute(self, bot, now: int) -> dict | None:
        t0 = time.perf_counter()
        try:
            now = int(now)
            self._restore()
            store, C = load_store(), load_calib()
            H = live_hist(bot, now)
            reg = regime(H, now, C)
            sim = {"lit": None, "atlas": None, "blitz": None}
            if H is not None:
                b = getattr(bot, "brain", None) or {}
                sim["lit"] = similar("lit", lit_now(bot, H, now), ((b.get("sizing") or {}) if isinstance(b, dict) else {}).get("risk_usd"),
                                     store, C, self.ld)
                sim["atlas"] = similar("atlas", atlas_now(bot, H, now), None, store, C, self.ld)
                bz = blitz_now(bot, H, now)
                rk = None
                try:
                    S_ = getattr(bot, "blitz", None) or {}
                    op = next((r for r in reversed(S_.get("ledger") or []) if r.get("exit_kind") == "OPEN"), None)
                    if op and op.get("qty"):
                        rk = abs(float(op["entry"]) - float(op["stop"])) * PV * int(op["qty"])
                except Exception:
                    rk = None
                sim["blitz"] = similar("blitz", bz, rk, store, C, self.ld)
            e = _et(now)
            mod, day = e.hour * 60 + e.minute, trading_day(now)
            for bk, fn in PLANNERS.items():
                try:
                    p = fn(bot, H, now, reg, store, self.ld)
                except Exception as ex:
                    p = None
                    self.err = f"plan {bk}: {ex.__class__.__name__}: {ex}"[:200]
                if not p:
                    continue
                self.plans[bk] = p
                if e.weekday() < 5 and PLAN_AT[bk] <= mod < 1080 and self.frozen.get(bk) != day:
                    self.frozen[bk] = day
                    _jl_append(os.path.join(self.ld, "plans.jsonl"), [{"bot": bk, "day": day, **p}])
                    sc = p.get("scenarios") or []
                    txt = p["headline"] + (". " + " | ".join(f"IF {s['if']} THEN {s['then']}" for s in sc[:2]) if sc else "") + \
                        (f". What would change my mind: {p.get('change_mind')}" if p.get("change_mind") else "")
                    self._event(f"mind:plan:{bk}:{day}", now, bk, "plan", f"{BOTS[bk]} game plan", txt)
                    self._alert(now, bk, f"Game plan ready: {p['headline']}", "info")
            self._reviews(bot, H, store, C, now)
            if reg.get("label") != self.last_regime:
                if self.last_regime is not None:
                    self._alert(now, "all", f"Regime now: {reg['label']} ({reg.get('why', '')[:120]})", "info")
                self.last_regime = reg.get("label")
            self.history.append({"t": now, "label": reg.get("label"), "trend": reg.get("trend"), "vol": reg.get("vol"),
                                 "p_trend": (reg.get("day_type") or {}).get("p_trend")})
            props = proposals(self.ld)
            seen = {e_["key"] for e_ in self.events}
            for p in props:
                if p.get("status") == "candidate" and f"mind:prop:{p['id']}" not in seen and now - int(p.get("t") or 0) < 3 * 86400:
                    self._event(f"mind:prop:{p['id']}", int(p.get("t") or now), p.get("bot") or "lit", "proposal",
                                f"Mind proposal: {p.get('idea')}", f"{p.get('idea')}. {p['evidence'].get('h1')} | {p['evidence'].get('h2')}. "
                                "Nothing changes unless you approve it.", "good")
                    self._alert(int(p.get("t") or now), p.get("bot") or "lit", f"New idea to approve: {p.get('idea')}", "good")
            n = {bk: len(((store.get("bots") or {}).get(bk) or {}).get("rows") or []) + len(live_rows(bk, self.ld)) for bk in BOTS}
            self.ms = int((time.perf_counter() - t0) * 1000)
            blk = {"t": now, "v": VERSION, "kind": KIND, "regime": reg, "plans": dict(self.plans), "similar": sim,
                   "reviews": list(self.reviews)[-10:][::-1], "proposals": props[:12], "alerts": list(self.alerts)[-10:][::-1],
                   "iq": {"store_n": n, "calibration": calibration_line(C), "daytype": daytype_note(C), "ms": self.ms,
                          "error": self.err}}
            with self.mx:
                self.block = blk
            return blk
        except Exception as ex:
            self.err = f"{ex.__class__.__name__}: {ex}"[:200]
            return None

    def _reviews(self, bot, H, store, C, now):
        try:
            todo = sorted([t for t in closed_trades(bot) if _trade_key(t) not in self.reviewed], key=lambda t: int(t.get("exit_t") or 0))
        except Exception:
            todo = []
        old = [t for t in todo if int(t.get("exit_t") or 0) < now - REVIEW_BACK_S]
        for t in old:                              # older than 2 days (a first start, a long paper ledger): not reviewed now
            self.reviewed.add(_trade_key(t))
        for t in [t for t in todo if int(t.get("exit_t") or 0) >= now - REVIEW_BACK_S][-20:]:
            k = _trade_key(t)
            self.reviewed.add(k)
            try:
                rv = review(t, H, store, C, self.ld, None, now)
            except Exception:
                continue
            self.reviews.append(rv)
            _jl_append(os.path.join(self.ld, "reviews.jsonl"), [{**rv, "key": k}])
            self._add_live_row(t, H, rv)
            if now - int(t.get("exit_t") or now) < 86400:
                self._event(f"mind:review:{k}", now, t["bot"], "review", f"{BOTS[t['bot']]} trade review: {rv['grade']}",
                            f"{rv['trade']}: grade {rv['grade']} ({rv['luck']}: {rv.get('why')}). " + rv["lesson"],
                            "good" if rv["grade"] in ("A", "B") else "warn" if rv["grade"] in ("D", "F") else "info")
                self._alert(now, t["bot"], f"Reviewed {rv['trade']}: {rv['grade']}", "info")

    def _add_live_row(self, t, H, rv):
        """The closed trade joins the bot's memory (logs/mind/<bot>_live.jsonl) with the same columns as the store."""
        try:
            bk = t["bot"]
            blk = (load_store().get("bots") or {}).get(bk)
            if not blk or H is None or rv.get("r") is None:
                return
            d = int(t.get("dir") or 1)
            f = H.ctx(int(t["entry_t"]), d)
            if not f:
                return
            if bk == "atlas":
                f["member"] = member_of(t.get("key"))
            if t.get("entry") is not None and t.get("stop") is not None and f.get("atr"):
                f["stop_atr"] = round(_risk_pts(t) / f["atr"], 3) if _risk_pts(t) else None
            e = _et(int(t["entry_t"]))
            base = {"day": t.get("day") or trading_day(int(t["entry_t"])), "t": int(t["entry_t"]), "dir": d, "r": rv["r"], "usd": _f(t.get("usd"), 2),
                    "exit": str(t.get("exit_kind") or "").upper(), "src": "live", "qty": _i(t.get("qty")),
                    "risk_pts": _f(_risk_pts(t), 2), "hm": e.strftime("%H:%M"), "dow": e.weekday()}
            row = [base[c] if c in base else f.get(c) for c in blk["cols"]]
            _jl_append(os.path.join(self.ld, f"{bk}_live.jsonl"), [{"key": _trade_key(t), "row": row}])
        except Exception:
            pass

    def cached(self) -> dict | None:
        with self.mx:
            return self.block

    def busy(self) -> bool:
        th = self.thread
        return th is not None and th.is_alive()

    def nightly(self, now: int) -> int | None:
        """After 16:05 ET on a weekday, once a day: the self-research as a low-priority child process (Mind's thread)."""
        if os.environ.get("LE_MIND_RESEARCH", "1") == "0":
            return None
        e = _et(now)
        day = e.strftime("%Y-%m-%d")
        if e.weekday() >= 5 or not (965 <= e.hour * 60 + e.minute < 1430) or self.research_day == day:
            return None
        self.research_day = day
        last = _read_json(os.path.join(self.ld, "research_last.json"), {}) or {}
        if last.get("day") == day:
            return None
        pid = spawn_research(600, self.log_dir)
        _write_json(os.path.join(self.ld, "research_last.json"), {"day": day, "t": int(now), "pid": pid})
        return pid

    def _job(self, bot, now: int, nightly: bool):
        self.compute(bot, now)
        if nightly:
            try:
                self.nightly(now)
            except Exception:
                pass

    def kick(self, bot, now: int, background: bool = True, nightly: bool = False) -> bool:
        """Compute once per 5m bar (wall clock): in a background thread unless background=False (+ the nightly research
        check, also in that thread). True when started."""
        key = int(now) // 300
        with self.mx:
            if self.key == key or self.busy():
                return False
            self.key = key
        if not background:
            self._job(bot, int(now), nightly)
            return True
        th = threading.Thread(target=self._job, args=(bot, int(now), nightly), name="mind", daemon=True)
        self.thread = th
        th.start()
        return True


MIND = Mind()


def skeleton(now: int, why: str = "Mind starts after the bot's next 5m bar.") -> dict:
    return {"t": int(now), "v": VERSION, "kind": KIND,
            "regime": {"label": "Mind is starting", "trend": "range", "vol": "normal", "day_type": None, "why": why},
            "plans": {}, "similar": {"lit": None, "atlas": None, "blitz": None}, "reviews": [], "proposals": proposals()[:12],
            "alerts": [], "iq": {"store_n": {bk: len(((load_store().get("bots") or {}).get(bk) or {}).get("rows") or []) for bk in BOTS},
                                 "calibration": calibration_line()}}


def view_block(bot=None, now: int | None = None, mind: Mind | None = None) -> dict:
    """The liveview / holo "mind" block: the last computed block (never computes here: pc_tick or the API does)."""
    try:
        M = mind or MIND
        b = M.cached()
        return b if b is not None else skeleton(int(now or time.time()))
    except Exception:
        return skeleton(int(now or time.time()), "Mind unavailable")


def contract_errors(b) -> list:
    """What is wrong with a block against the contract the dashboards render (tests/fixtures/mind_sample.json); [] = fine."""
    E = []
    num = (int, float)

    def need(c, msg):
        if not c:
            E.append(msg)
    if not isinstance(b, dict):
        return ["not a dict"]
    need(isinstance(b.get("t"), int), "t int")
    r = b.get("regime")
    need(isinstance(r, dict), "regime dict")
    if isinstance(r, dict):
        need(isinstance(r.get("label"), str) and isinstance(r.get("why"), str), "regime label / why str")
        need(r.get("trend") in ("up", "down", "range"), f"regime trend {r.get('trend')}")
        need(r.get("vol") in ("high", "normal", "quiet"), f"regime vol {r.get('vol')}")
        dt_ = r.get("day_type")
        need(dt_ is None or (isinstance(dt_, dict) and (dt_.get("p_trend") is None or isinstance(dt_.get("p_trend"), num))
                             and isinstance(dt_.get("label"), str) and isinstance(dt_.get("acc_note"), str)), "regime day_type")
    pl = b.get("plans")
    need(isinstance(pl, dict) and set(pl) <= set(BOTS), "plans dict of lit / atlas / blitz")
    for k, p in (pl or {}).items() if isinstance(pl, dict) else []:
        need(isinstance(p, dict) and isinstance(p.get("t"), int) and isinstance(p.get("headline"), str) and isinstance(p.get("change_mind"), str)
             and isinstance(p.get("scenarios"), list), f"plan {k}")
        for s in (p or {}).get("scenarios") or []:
            need(isinstance(s.get("if"), str) and isinstance(s.get("then"), str) and isinstance(s.get("levels"), list)
                 and all(isinstance(x, num) for x in s.get("levels") or []) and (s.get("exp_usd") is None or isinstance(s.get("exp_usd"), num))
                 and (s.get("odds") is None or isinstance(s.get("odds"), num)), f"plan {k} scenario")
    sm = b.get("similar")
    need(isinstance(sm, dict) and set(sm) == set(BOTS), "similar has lit / atlas / blitz")
    for k, s in (sm or {}).items() if isinstance(sm, dict) else []:
        if s is None:
            continue
        need(isinstance(s.get("n"), int) and isinstance(s.get("win"), num) and isinstance(s.get("avg_r"), num)
             and (s.get("usd") is None or isinstance(s.get("usd"), num)) and s.get("conf") in ("low", "medium", "high")
             and isinstance(s.get("valid"), bool) and isinstance(s.get("examples"), list), f"similar {k}")
        need(s.get("valid") or s.get("conf") == "low", f"similar {k}: no confidence claim when not valid")
        for x in s.get("examples") or []:
            need(isinstance(x.get("day"), str) and isinstance(x.get("r"), num) and (x.get("usd") is None or isinstance(x.get("usd"), num)),
                 f"similar {k} example")
    for v in b.get("reviews") if isinstance(b.get("reviews"), list) else [None]:
        need(isinstance(v, dict) and isinstance(v.get("t"), int) and isinstance(v.get("bot"), str) and isinstance(v.get("trade"), str)
             and v.get("grade") in ("A", "B", "C", "D", "F") and isinstance(v.get("right"), list) and isinstance(v.get("wrong"), list)
             and isinstance(v.get("lesson"), str) and v.get("luck") in ("luck", "skill", "mixed"), "review")
    for p in b.get("proposals") if isinstance(b.get("proposals"), list) else [None]:
        ev = (p or {}).get("evidence") if isinstance(p, dict) else None
        need(isinstance(p, dict) and isinstance(p.get("id"), str) and isinstance(p.get("bot"), str) and isinstance(p.get("idea"), str)
             and isinstance(ev, dict) and all(isinstance(ev.get(x), str) for x in ("h1", "h2", "r2125"))
             and (ev.get("usd_month") is None or isinstance(ev.get("usd_month"), num))
             and p.get("status") in ("testing", "candidate", "rejected") and isinstance(p.get("t"), int)
             and (p.get("change") is None or isinstance(p.get("change"), str)), f"proposal {(p or {}).get('id') if isinstance(p, dict) else p}")
    for a in b.get("alerts") if isinstance(b.get("alerts"), list) else [None]:
        need(isinstance(a, dict) and isinstance(a.get("t"), int) and isinstance(a.get("bot"), str) and isinstance(a.get("text"), str)
             and a.get("level") in ("info", "good", "warn"), "alert")
    iq = b.get("iq")
    need(isinstance(iq, dict) and isinstance(iq.get("store_n"), dict) and all(isinstance((iq.get("store_n") or {}).get(k), int) for k in BOTS)
         and isinstance(iq.get("calibration"), str), "iq")
    return E


def _cut(s, n):
    s = str(s or "")
    return s if len(s) <= n else s[:n - 1] + "…"


def compact(b: dict | None, max_bytes: int = 12_000) -> dict | None:
    """The phone / heartbeat cut of the block (< max_bytes)."""
    if not isinstance(b, dict):
        return None
    reg = dict(b.get("regime") or {})
    if isinstance(reg.get("day_type"), dict):
        reg["day_type"] = {k: reg["day_type"].get(k) for k in ("p_trend", "label", "acc_note")}
        reg["day_type"]["acc_note"] = _cut(reg["day_type"].get("acc_note"), 260)
    reg = {k: reg.get(k) for k in ("label", "trend", "vol", "day_type", "why")}
    reg["why"] = _cut(reg.get("why"), 240)
    plans = {}
    for k, p in (b.get("plans") or {}).items():
        if isinstance(p, dict):
            plans[k] = {"t": p.get("t"), "headline": _cut(p.get("headline"), 200), "change_mind": _cut(p.get("change_mind"), 300),
                        "scenarios": [{"if": _cut(s.get("if"), 200), "then": _cut(s.get("then"), 300), "levels": (s.get("levels") or [])[:4],
                                       "exp_usd": s.get("exp_usd"), "odds": s.get("odds")} for s in (p.get("scenarios") or [])[:3]]}
    sim = {}
    for k in BOTS:
        s = (b.get("similar") or {}).get(k)
        sim[k] = None if not isinstance(s, dict) else {**{x: s.get(x) for x in ("n", "win", "avg_r", "usd", "conf", "valid")},
                                                       "examples": (s.get("examples") or [])[:3], "text": _cut(s.get("text"), 260)}
    out = {"t": b.get("t"), "v": b.get("v", VERSION), "kind": KIND, "compact": True, "regime": reg, "plans": plans, "similar": sim,
           "reviews": [{**{x: r.get(x) for x in ("t", "bot", "trade", "grade", "luck")}, "right": [_cut(x, 120) for x in (r.get("right") or [])[:2]],
                        "wrong": [_cut(x, 120) for x in (r.get("wrong") or [])[:2]], "lesson": _cut(r.get("lesson"), 200)}
                       for r in (b.get("reviews") or [])[:3]],
           "proposals": [{"id": p.get("id"), "bot": p.get("bot"), "idea": _cut(p.get("idea"), 140), "status": p.get("status"), "t": p.get("t"),
                          "change": _cut(p.get("change"), 220) if p.get("change") else None,
                          "evidence": {"h1": _cut((p.get("evidence") or {}).get("h1"), 140), "h2": _cut((p.get("evidence") or {}).get("h2"), 140),
                                       "r2125": _cut((p.get("evidence") or {}).get("r2125"), 140),
                                       "usd_month": (p.get("evidence") or {}).get("usd_month")}}
                         for p in (b.get("proposals") or [])[:5]],
           "alerts": [{k: a.get(k) for k in ("t", "bot", "text", "level")} for a in (b.get("alerts") or [])[:5]],
           "iq": {"store_n": (b.get("iq") or {}).get("store_n"), "calibration": _cut((b.get("iq") or {}).get("calibration"), 420)}}

    def size():
        return len(json.dumps(out, separators=(",", ":"), default=str))
    for key in ("proposals", "reviews", "alerts"):
        while size() > max_bytes and out[key]:
            out[key] = out[key][:-1]
    if size() > max_bytes:
        for p in out["plans"].values():
            p["scenarios"] = p["scenarios"][:1]
    return out


# ================================================================================================ hooks
def pc_tick(bot, now=None, background: bool = True, spawn: bool = True, mind: Mind | None = None) -> bool | None:
    """engine/narrator.tick hook (PC, after routing): once per 5m bar start Mind's compute in a background thread; after
    16:05 ET on a weekday start the nightly research once (a low-priority child process). The poll thread only checks a
    key. Never raises."""
    if os.environ.get("LE_MIND", "1") == "0":
        return None
    try:
        M = mind or MIND
        now = int(now if now is not None else (bot.clock() if callable(getattr(bot, "clock", None)) else time.time()))
        return M.kick(bot, now, background=background, nightly=spawn)
    except Exception:
        return None


def narrator_msgs(day: str, mind: Mind | None = None) -> list:
    """Today's Mind events for engine/narrator (kind "brain": plan / review / proposal; no phone push by default)."""
    M = mind or MIND
    try:
        with M.mx:
            ev = list(M.events)
    except Exception:
        return []
    return [e for e in ev if trading_day(e["t"]) == day]


def api_view(bot, now: int | None = None, mind: Mind | None = None) -> dict:
    """GET /api/next/mind: the full block + history (regime per 5m bar today, the last plans, reviews, proposals, the
    calibration report). A stale block starts a background compute (the answer is the last block)."""
    M = mind or MIND
    now = int(now or (bot.clock() if callable(getattr(bot, "clock", None)) else time.time()))
    try:
        M.kick(bot, now, background=True)
    except Exception:
        pass
    C = load_calib()
    prop = _read_json(os.path.join(M.ld, "proposals.json")) or _read_json(SEED_PROPOSALS) or {}
    return {"t": now, "block": view_block(bot, now, M), "busy": M.busy(),
            "history": {"regime": [h for h in list(M.history) if trading_day(h["t"]) == trading_day(now)],
                        "plans": _jl_read(os.path.join(M.ld, "plans.jsonl"), 30)[::-1],
                        "reviews": [{k: v for k, v in r.items() if k != "key"} for r in _jl_read(os.path.join(M.ld, "reviews.jsonl"), 100)][::-1],
                        "proposals": prop.get("proposals") or [], "observations": prop.get("observations") or [],
                        "research": {"t": prop.get("t"), "took_s": prop.get("took_s"), "tested": prop.get("tested"), "note": prop.get("note")}},
            "calibration": {"similar": C.get("similar"), "daytype": {k: v for k, v in (C.get("daytype") or {}).items() if k in ("report", "fit", "label", "n_fit")}},
            "read_only": "Mind thinks, predicts, explains and proposes. It never changes a rule, a size or an order: the owner approves changes."}


try:
    from fastapi import APIRouter
    from fastapi.responses import Response
    router = APIRouter()

    def _bot():
        from .live import BOT
        return BOT

    @router.get("/api/next/mind")
    def r_mind():
        try:
            return Response(json.dumps(api_view(_bot()), separators=(",", ":"), default=_jd), media_type="application/json")
        except Exception as e:
            return Response(json.dumps({"error": f"{e.__class__.__name__}: {e}"[:200]}), media_type="application/json", status_code=500)
except Exception:                                             # fastapi missing (cloud tools): the module still works
    router = None


def _main(argv):
    import argparse
    ap = argparse.ArgumentParser(prog="engine.mind")
    ap.add_argument("cmd", choices=["research", "show", "calib"])
    ap.add_argument("--budget", type=float, default=600.0)
    ap.add_argument("--log-dir", default=None)
    a = ap.parse_args(argv)
    if a.cmd == "research":
        t0 = time.time()
        out = research(a.budget, log_dir=a.log_dir)
        print(f"{_et(int(t0)):%Y-%m-%d %H:%M} research: {out['tested']} tests, {out['took_s']} s, "
              f"{sum(1 for p in out['proposals'] if p['status'] == 'candidate')} candidates", flush=True)
        for o in out["observations"]:
            print("  noticed:", o["text"])
        for p in out["proposals"][:20]:
            print(f"  [{p['status']}] {p['idea']}: {p['evidence'].get('h1')} | {p['evidence'].get('h2')}")
    elif a.cmd == "calib":
        print(calibration_line())
        print(daytype_note())
    else:
        print(json.dumps(view_block(), indent=1, default=_jd)[:4000])


if __name__ == "__main__":
    import sys as _sys
    _main(_sys.argv[1:])
