"""Past-only features of every 5m bar and the event table (every trigger with its mini-backtest).

Time: every bar's ET clock, its CME day (18:00 ET -> 17:00 ET, named by the date it ends on) and `mod` = minutes since
18:00 ET (18:00 = 0, 02:00 = 480, 09:30 = 930, 16:00 = 1320).

No look-ahead: a feature of bar i uses bars <= i only (the bar's own close included: the decision is taken at that close
and the trade enters at the NEXT bar's open). Day-level facts (levels, ATR regime, VIX, previous day type) use earlier days
only; the news calendar is a schedule known in advance. tests/test_datacity.py checks this by cutting the data.

Mini-backtest (one trade per event): entry = next bar open; stop = structure (sweeps: 1 tick beyond the sweep extreme,
others: 1 tick beyond the extreme of the last 6 bars), at least MIN_STOP points, at most MAX_STOP; target 2R; exit at the
close of bar H (2 hours) or the CME day's last bar, whichever first. A bar that touches both the stop and a target counts
as a stop (conservative). Money per MNQ micro ($2 a point) after COST = $1.90 commission + 2 ticks slippage.
"""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

ET = "America/New_York"
TICK, PT_USD, COMM, SLIP_TICKS = 0.25, 2.0, 1.90, 2
COST = round(COMM + SLIP_TICKS * TICK * PT_USD, 2)     # $2.90 per micro round trip
H = 24                                                  # 2 hours of 5m bars
MIN_STOP, MAX_STOP = 4.0, 120.0
TGT_R = 2.0

WINDOWS = (("asia", 0, 480), ("london", 480, 780), ("pre", 780, 930), ("nyam", 930, 1050), ("lunch", 1050, 1170), ("pm", 1170, 1320))
WIN_NAMES = [w[0] for w in WINDOWS]

# trigger id -> (label, direction). Directional by construction.
LEVELS = (("asia_h", "Asia high"), ("asia_l", "Asia low"), ("lon_h", "London high"), ("lon_l", "London low"),
          ("pdh", "prior-day high"), ("pdl", "prior-day low"), ("pwh", "prior-week high"), ("pwl", "prior-week low"),
          ("orh", "opening-range high"), ("orl", "opening-range low"))


def _trig_table():
    T = []
    for k, lab in LEVELS:
        hi = k.endswith("_h") or k in ("pdh", "pwh", "orh")
        T.append((f"sweep_{k}", f"{lab} sweep", -1 if hi else 1))
        T.append((f"break_{k}", f"{lab} break", 1 if hi else -1))
    T += [("fvg_bull", "bullish FVG", 1), ("fvg_bear", "bearish FVG", -1), ("ifvg_bull", "bullish IFVG", 1),
          ("ifvg_bear", "bearish IFVG", -1), ("cisd_bull", "bullish CISD", 1), ("cisd_bear", "bearish CISD", -1),
          ("disp_bull", "bullish displacement", 1), ("disp_bear", "bearish displacement", -1),
          ("vwap_up", "VWAP reclaim", 1), ("vwap_dn", "VWAP loss", -1),
          ("gapfill_up", "gap-down fill", -1), ("gapfill_dn", "gap-up fill", 1),
          ("news_long", "news bar up (follow)", 1), ("news_short", "news bar down (follow)", -1),
          ("slot_long", "plain long at the slot", 1), ("slot_short", "plain short at the slot", -1)]
    return T


TRIGS = _trig_table()
TRIG_ID = {t[0]: i for i, t in enumerate(TRIGS)}

# state family -> value labels (index = code; -1 = not available)
STATES = {
    "vwap": ("with VWAP", "against VWAP"),
    "ema": ("with the EMA200 trend", "against the EMA200 trend"),
    "atr": ("quiet ATR", "normal ATR", "wild ATR"),
    "vix": ("VIX < 15", "VIX 15-20", "VIX 20-25", "VIX 25+"),
    "vxn": ("VXN < 20", "VXN 20-28", "VXN 28+"),
    "lsa": ("London swept no Asia side", "London swept the Asia high", "London swept the Asia low", "London swept both Asia sides"),
    "today": ("trending so far today", "balanced so far today"),
    "prev": ("after a trend day", "after a range day"),
    "wd": ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday"),
    "dst": ("winter time", "summer time", "DST gap weeks"),
    "news": ("no big news today", "big-news day"),
    "gap": ("flat open", "gap up", "gap down"),
    "smt": ("no ES-NQ SMT", "ES-NQ SMT with the trade", "ES-NQ SMT against the trade"),
    # added 2026-11-03 (the bigger city): opening-range types, gap types, the VIX curve and trend, ES-NQ strength, calendar
    "orw": ("a narrow opening range", "a normal opening range", "a wide opening range"),
    "orp": ("beyond the opening range with the trade", "inside the opening range", "beyond the opening range against the trade"),
    "gapt": ("no RTH gap", "a gap up already filled", "a gap up still open", "a gap down already filled", "a gap down still open"),
    "vts": ("the VIX curve in contango", "a flat VIX curve", "the VIX curve inverted"),
    "vtr": ("VIX falling", "VIX steady", "VIX rising"),
    "esr": ("NQ outpacing ES the trade's way", "NQ and ES in step", "NQ lagging ES the trade's way"),
    "cal": ("the turn of the month", "OpEx week", "a plain week"),
}
FAMILIES = list(STATES)


HIGH_LEVELS = ("asia_h", "lon_h", "pdh", "pwh", "orh")
LEVEL_VALID_FROM = {"asia_h": 480, "asia_l": 480, "lon_h": 780, "lon_l": 780, "pdh": 0, "pdl": 0, "pwh": 0, "pwl": 0,
                    "orh": 945, "orl": 945}
STATE_EDGES = {"vix": (15, 20, 25), "vxn": (20, 28), "atr": (1 / 3, 2 / 3), "orw": (1 / 3, 2 / 3), "vts": (0.9, 1.0),
               "vtr": (0.95, 1.05)}
DAY_FAMILIES = ("wd", "dst", "news", "vix", "vxn", "atr", "prev", "vts", "vtr", "cal", "mon")   # known before the day trades
ESR_PCT = 0.15                    # NQ vs ES % change since the day's open: beyond +/- this = one leads the other
GAP_X = 0.15                      # an RTH gap: |09:30 open - prior RTH close| > this x the daily ATR


# ------------------------------------------------------------------------------------------------ helpers
def _first_per_group(mask, grp):
    """Index of the first True of mask in each group (grp sorted ascending)."""
    idx = np.flatnonzero(mask)
    if not len(idx):
        return idx
    _, first = np.unique(grp[idx], return_index=True)
    return idx[first]


def _bucket(x, edges):
    """Bucket index of x by the edges; -1 where x is not finite."""
    out = np.full(len(x), -1, dtype=np.int8)
    ok = np.isfinite(x)
    out[ok] = np.searchsorted(np.asarray(edges, dtype=float), x[ok], side="right")
    return out


def _shift(a, k, fill=np.nan):
    """a moved k places later (a[i - k] at i)."""
    return np.r_[np.full(k, fill, dtype=float), a[:-k]]


def _dst_state(days):
    """0 winter, 1 summer (US DST), 2 the gap weeks (US and Europe disagree)."""
    from zoneinfo import ZoneInfo
    ny, ldn = ZoneInfo("America/New_York"), ZoneInfo("Europe/London")
    out = np.zeros(len(days), dtype=np.int8)
    for i, d in enumerate(days.astype(object)):
        noon = dt.datetime(d.year, d.month, d.day, 12)
        us, eu = bool(noon.replace(tzinfo=ny).dst()), bool(noon.replace(tzinfo=ldn).dst())
        out[i] = 2 if us != eu else (1 if us else 0)
    return out


def _cboe_before(d, days):
    """The CBOE close of the last date strictly before each day (VIX / VXN), NaN when there is none."""
    out = np.full(len(days), np.nan)
    if d is None or not len(d):
        return out
    k = np.searchsorted(np.array(d["date"].to_numpy(), dtype="datetime64[D]"), days, side="left") - 1
    ok = k >= 0
    out[ok] = d["close"].to_numpy(dtype=float)[k[ok]]
    return out


def _past_pct(x, k=250, min_n=40):
    """Share of the previous k finite values below today's (NaN when today's is NaN or too little history)."""
    out = np.full(len(x), np.nan)
    for i in range(len(x)):
        if not np.isfinite(x[i]):
            continue
        w = x[max(0, i - k):i]
        w = w[np.isfinite(w)]
        if len(w) >= min_n:
            out[i] = float(np.mean(w < x[i]))
    return out


def _vix_trend(vix):
    """VIX close / the mean of the 5 closes before it, as a CBOE-style frame (date, close)."""
    if vix is None or not len(vix):
        return None
    c = vix["close"].astype(float)
    return pd.DataFrame({"date": vix["date"], "close": (c / c.shift(1).rolling(5, min_periods=5).mean()).to_numpy()}).dropna()


def _calendar(days):
    """0 the turn of the month (last 2 / first 3 weekdays), 1 OpEx week (the Mon-Fri week of the 3rd Friday), 2 plain."""
    out = np.full(len(days), 2, dtype=np.int8)
    for i, d in enumerate(days.astype(object)):
        if d.weekday() > 4:
            out[i] = -1
            continue
        first = dt.date(d.year, d.month, 1)
        nxt = dt.date(d.year + (d.month == 12), d.month % 12 + 1, 1)
        wd_before = int(np.busday_count(first, d))                # weekdays of the month before d
        wd_after = int(np.busday_count(d, nxt)) - 1                # weekdays of the month after d
        fri = first + dt.timedelta(days=(4 - first.weekday()) % 7 + 14)
        if wd_before < 3 or wd_after < 2:
            out[i] = 0
        elif 0 <= (fri - d).days <= 4:
            out[i] = 1
    return out


class Bars:
    """The 5m bars as arrays, with their ET clock and CME day."""

    def __init__(self, df: pd.DataFrame):
        df = df.reset_index(drop=True)
        self.t = df["time"].to_numpy(dtype=np.int64)
        self.o, self.h, self.l, self.c = (df[k].to_numpy(dtype=float) for k in ("open", "high", "low", "close"))
        self.v = np.maximum(df["volume"].to_numpy(dtype=float), 1.0)
        self.n = len(df)
        self.et = pd.to_datetime(self.t, unit="s", utc=True).tz_convert(ET)
        self.mins = (self.et.hour * 60 + self.et.minute).to_numpy()
        self.mod = (self.mins - 1080) % 1440
        dday = (self.et + pd.Timedelta(hours=6)).normalize().tz_localize(None).to_numpy().astype("datetime64[D]")
        self.days, self.did = np.unique(dday, return_inverse=True)
        self.nd = len(self.days)
        self.first = np.r_[True, self.did[1:] != self.did[:-1]] if self.n else np.zeros(0, bool)

    def per_day(self, mask, arr, how):
        """One value a day from the day's own bars under mask (max / min / first / last), NaN for a day without one."""
        out = np.full(self.nd, np.nan)
        if mask.any():
            g = pd.Series(arr[mask]).groupby(self.did[mask])
            r = getattr(g, how)()
            out[r.index.to_numpy()] = r.to_numpy()
        return out

    def in_day(self, arr, how):
        """Running max / min of arr within each day (bars so far)."""
        g = pd.Series(arr).groupby(self.did)
        return (g.cummax() if how == "max" else g.cummin()).to_numpy()

    def rolling(self, arr, k, how):
        r = pd.Series(arr).rolling(k, min_periods=1)
        return (r.max() if how == "max" else r.min()).to_numpy()

    def same_day(self, a, b):
        """b is a bar of the same day as a."""
        return (b < self.n) & (self.did[np.minimum(b, self.n - 1)] == self.did[a])


# ------------------------------------------------------------------------------------------------ facts
def day_facts(b: Bars, vix=None, vxn=None, news=None, vix3m=None) -> dict:
    """Day-level facts. Levels of the day itself (Asia, London, opening range) are only used after they are complete;
    everything else comes from earlier days or from a schedule known in advance."""
    every = np.ones(b.n, bool)
    hi, lo = b.per_day(every, b.h, "max"), b.per_day(every, b.l, "min")
    op, cl = b.per_day(every, b.o, "first"), b.per_day(every, b.c, "last")
    asia, lon, orng = b.mod < 480, (b.mod >= 480) & (b.mod < 780), (b.mod >= 930) & (b.mod < 945)
    rth_open = b.per_day(b.mod == 930, b.o, "first")
    rth_close = b.per_day((b.mod >= 930) & (b.mod < 1320), b.c, "last")
    week = np.array([d.isocalendar()[0] * 100 + d.isocalendar()[1] for d in b.days.astype(object)])
    _, wid = np.unique(week, return_inverse=True)
    w_hi = np.r_[np.nan, pd.Series(hi).groupby(wid).max().to_numpy()]
    w_lo = np.r_[np.nan, pd.Series(lo).groupby(wid).min().to_numpy()]
    datr = pd.Series(hi - lo).shift(1).rolling(14, min_periods=5).mean().to_numpy()      # earlier 14 days
    pct = pd.Series(datr).rolling(250, min_periods=40).apply(
        lambda w: np.mean(w[:-1] < w[-1]) if np.isfinite(w[-1]) else np.nan, raw=True).to_numpy()
    prev_type = (np.abs(cl - op) / np.maximum(hi - lo, 1e-9) < 0.6).astype(np.int8)       # 0 trend, 1 range
    pc = _shift(rth_close, 1)
    wd = np.array([d.weekday() for d in b.days.astype(object)], dtype=np.int8)
    news_dates = set(news["date"].astype(str)) if news is not None and len(news) else set()
    orh, orl = b.per_day(orng, b.h, "max"), b.per_day(orng, b.l, "min")
    v_prev, v3_prev = _cboe_before(vix, b.days), _cboe_before(vix3m, b.days)
    return {
        "levels": {"asia_h": b.per_day(asia, b.h, "max"), "asia_l": b.per_day(asia, b.l, "min"),
                   "lon_h": b.per_day(lon, b.h, "max"), "lon_l": b.per_day(lon, b.l, "min"),
                   "pdh": _shift(hi, 1), "pdl": _shift(lo, 1), "pwh": w_hi[wid], "pwl": w_lo[wid],
                   "orh": orh, "orl": orl},
        "open": op, "datr": datr, "pc": pc, "gapx": (rth_open - pc) / datr,
        "atr": _bucket(pct, STATE_EDGES["atr"]), "prev": np.r_[-1, prev_type[:-1]].astype(np.int8),
        "vix": _bucket(_cboe_before(vix, b.days), STATE_EDGES["vix"]),
        "vxn": _bucket(_cboe_before(vxn, b.days), STATE_EDGES["vxn"]),
        "dst": _dst_state(b.days), "wd": np.where(wd > 4, -1, wd).astype(np.int8),
        "news": np.array([1 if str(d) in news_dates else 0 for d in b.days.astype(object)], dtype=np.int8),
        "orw": _bucket(_past_pct((orh - orl) / datr), STATE_EDGES["orw"]),           # today's OR vs the last 250 days
        "vts": _bucket(v_prev / v3_prev, STATE_EDGES["vts"]),                           # VIX / VIX3M, closes before the day
        "vtr": _bucket(_cboe_before(_vix_trend(vix), b.days), STATE_EDGES["vtr"]),
        "cal": _calendar(b.days),
    }


def news_bars(b: Bars, news) -> np.ndarray:
    """The bar that opens at each scheduled high-impact release minute (ET)."""
    if news is None or not len(news):
        return np.zeros(b.n, bool)
    day = np.array(pd.to_datetime(news["date"]).to_numpy(), dtype="datetime64[D]").astype(np.int64)
    hhmm = news["time_et"].astype(str)
    keys = day * 1440 + hhmm.str[:2].astype(int).to_numpy() * 60 + hhmm.str[3:5].astype(int).to_numpy()
    local_day = b.et.tz_localize(None).to_numpy().astype("datetime64[D]").astype(np.int64)
    return np.isin(local_day * 1440 + b.mins, keys)


def bar_facts(b: Bars, D: dict, es=None) -> dict:
    """Bar-level facts at each bar's close (bars <= i only)."""
    h, lo, c, did = b.h, b.l, b.c, b.did
    pcl = np.r_[c[:1], c[:-1]]
    tr = np.maximum(h - lo, np.maximum(np.abs(h - pcl), np.abs(lo - pcl)))
    vw = pd.Series((h + lo + c) / 3 * b.v).groupby(did).cumsum().to_numpy() / pd.Series(b.v).groupby(did).cumsum().to_numpy()
    hi_sofar, lo_sofar = b.in_day(h, "max"), b.in_day(lo, "min")
    datr = D["datr"][did]
    rng = hi_sofar - lo_sofar
    today = np.where(~np.isfinite(datr), -1, np.where((np.abs(c - D["open"][did]) >= 0.6 * rng) & (rng >= 0.5 * datr), 0, 1))
    lon = (b.mod >= 480) & (b.mod < 780)
    swept_h = b.in_day(np.where(lon, h, -np.inf), "max") > D["levels"]["asia_h"][did]
    swept_l = b.in_day(np.where(lon, lo, np.inf), "min") < D["levels"]["asia_l"][did]
    drift = np.where(b.mod >= 930, D["gapx"][did], (c - D["pc"][did]) / datr)
    rth = b.mod >= 930
    pc, gx = D["pc"][did], D["gapx"][did]
    lo_rth, hi_rth = b.in_day(np.where(rth, lo, np.inf), "min"), b.in_day(np.where(rth, h, -np.inf), "max")
    gapt = np.where(gx > GAP_X, np.where(lo_rth <= pc, 1, 2), np.where(gx < -GAP_X, np.where(hi_rth >= pc, 3, 4), 0))
    gapt = np.where(rth & (b.mod < 1320) & np.isfinite(gx), gapt, -1)
    orh, orl = D["levels"]["orh"][did], D["levels"]["orl"][did]
    or_side = np.where((b.mod >= 945) & np.isfinite(orh), np.where(c > orh, 1.0, np.where(c < orl, -1.0, 0.0)), np.nan)
    return {"gapt": gapt.astype(np.int8), "or_side": or_side, "esrel": es_rel(b, es),"pcl": pcl, "atr": pd.Series(tr).rolling(14, min_periods=5).mean().to_numpy(),
            "ema": pd.Series(c).ewm(span=200, adjust=False).mean().to_numpy(), "vwap": vw,
            "today": today.astype(np.int8),
            "lsa": np.where(b.mod < 480, -1, swept_h.astype(int) + 2 * swept_l.astype(int)).astype(np.int8),
            "gap": np.where(~np.isfinite(drift), -1, np.where(drift > 0.15, 1, np.where(drift < -0.15, 2, 0))).astype(np.int8),
            "smt": smt(b, hi_sofar, lo_sofar, es),
            "lo6": b.rolling(lo, 6, "min"), "hi6": b.rolling(h, 6, "max")}


def es_rel(b: Bars, es=None) -> np.ndarray:
    """NQ's % change since the CME day's first bar minus ES's, at each bar's close (NaN without ES bars or in the first hour)."""
    if es is None or not len(es):
        return np.full(b.n, np.nan)
    e = es.set_index("time").reindex(b.t)
    ec, eo = e["close"].to_numpy(dtype=float), e["open"].to_numpy(dtype=float)
    first = lambda a: pd.Series(a).groupby(b.did).transform("first").to_numpy()   # noqa: E731 (first non-NaN of the day)
    nq0, es0 = first(b.o), first(eo)
    have = np.isfinite(ec) & np.isfinite(es0) & (b.mod >= 60)
    return np.where(have, 100 * ((b.c / nq0 - 1) - (ec / np.where(have, es0, 1.0) - 1)), np.nan)


def smt(b: Bars, hi_sofar, lo_sofar, es=None) -> np.ndarray:
    """ES-NQ SMT at each bar: 1 bearish (NQ made a new day high in the last 3 bars, ES did not), 2 bullish (lows),
    0 none, -1 no ES bars (ES_5m.csv starts 2025-04) or the first hour of the day."""
    if es is None or not len(es):
        return np.full(b.n, -1, np.int8)
    e = es.set_index("time").reindex(b.t)
    eh, el = e["high"].to_numpy(dtype=float), e["low"].to_numpy(dtype=float)
    have = np.isfinite(eh)
    e_hi, e_lo = b.in_day(np.where(have, eh, -np.inf), "max"), b.in_day(np.where(have, el, np.inf), "min")
    before = lambda a, fill: np.where(b.first, fill, np.r_[fill, a[:-1]])                        # noqa: E731
    last3 = lambda a: pd.Series(a.astype(float)).groupby(b.did).rolling(3, min_periods=1).max().to_numpy() > 0  # noqa: E731
    bear = last3(b.h > before(hi_sofar, np.inf)) & ~last3(have & (eh > before(e_hi, np.inf)))
    bull = last3(b.l < before(lo_sofar, -np.inf)) & ~last3(have & (el < before(e_lo, -np.inf)))
    es_ok = pd.Series(have.astype(float)).rolling(6, min_periods=6).min().to_numpy() > 0
    return np.where(~es_ok | (b.mod < 60), -1, np.where(bear & ~bull, 1, np.where(bull & ~bear, 2, 0))).astype(np.int8)


# ------------------------------------------------------------------------------------------------ triggers
class Events:
    """Collects (decision bar, trigger, stop price) rows."""

    def __init__(self):
        self.idx, self.trig, self.stop = [], [], []

    def add(self, idx, trig, stop):
        idx = np.asarray(idx, dtype=np.int64)
        if len(idx):
            self.idx.append(idx)
            self.trig.append(np.full(len(idx), TRIG_ID[trig], np.int16))
            self.stop.append(np.asarray(stop, float))

    def arrays(self):
        if not self.idx:
            return np.array([], np.int64), np.array([], np.int16), np.array([])
        return np.concatenate(self.idx), np.concatenate(self.trig), np.concatenate(self.stop)


def level_triggers(b: Bars, D: dict, X: dict, E: Events):
    """First trade through each level of the day: a break (the touch bar closes beyond, continuation) and a sweep (the
    touch bar or one of the next 2 bars closes back inside, reversal; stop 1 tick beyond the sweep extreme)."""
    o, h, lo, c = b.o, b.h, b.l, b.c
    for k, lev in D["levels"].items():
        L = lev[b.did]
        up = k in HIGH_LEVELS
        touch = (b.mod >= LEVEL_VALID_FROM[k]) & np.isfinite(L) & ((h > L) if up else (lo < L))
        t0 = _first_per_group(touch, b.did)
        t0 = t0[(o[t0] <= L[t0]) if up else (o[t0] >= L[t0])]            # it must trade through the level, not open past it
        br = t0[(c[t0] > L[t0]) if up else (c[t0] < L[t0])]
        E.add(br, f"break_{k}", X["lo6"][br] - TICK if up else X["hi6"][br] + TICK)
        back = np.full((3, len(t0)), -1)
        for j in range(3):
            tj = t0 + j
            ok = b.same_day(t0, tj)
            tj = np.where(ok, tj, t0)
            back[j] = np.where(ok & ((c[tj] < L[t0]) if up else (c[tj] > L[t0])), tj, -1)
        has = (back >= 0).any(axis=0)
        ti = back[np.argmax(back >= 0, axis=0), np.arange(len(t0))][has]
        if up:
            E.add(ti, f"sweep_{k}", np.array([h[a:z + 1].max() for a, z in zip(t0[has], ti, strict=True)]) + TICK)
        else:
            E.add(ti, f"sweep_{k}", np.array([lo[a:z + 1].min() for a, z in zip(t0[has], ti, strict=True)]) - TICK)


def gap_triggers(b: Bars, X: dict, E: Events):
    """FVG (3-bar gap >= 0.1 ATR, same day) and IFVG (the first close through an opposite FVG of the last 24 bars)."""
    h, lo, c, n = b.h, b.l, b.c, b.n
    h2, l2 = _shift(h, 2), _shift(lo, 2)
    same2 = np.r_[False, False, b.did[2:] == b.did[:-2]]
    bull = same2 & (lo - h2 >= 0.1 * X["atr"])
    bear = same2 & (l2 - h >= 0.1 * X["atr"])
    E.add(np.flatnonzero(bull), "fvg_bull", l2[bull] - TICK)
    E.add(np.flatnonzero(bear), "fvg_bear", h2[bear] + TICK)
    top = np.where(bear, l2, np.nan)                  # a bearish FVG's top
    bot = np.where(bull, h2, np.nan)                  # a bullish FVG's bottom
    ib, isb = np.zeros(n, bool), np.zeros(n, bool)
    ib_stop, is_stop = np.full(n, np.nan), np.full(n, np.nan)
    cs = pd.Series(c).shift(1)
    for k in range(1, 25):
        s_top, s_bot = _shift(top, k), _shift(bot, k)
        same = np.r_[np.zeros(k, bool), b.did[k:] == b.did[:-k]]
        if k == 1:                                    # closes strictly between the FVG bar and bar i: none for k = 1
            mx, mn = np.full(n, -np.inf), np.full(n, np.inf)
        else:
            mx = cs.rolling(k - 1, min_periods=1).max().to_numpy()
            mn = cs.rolling(k - 1, min_periods=1).min().to_numpy()
        nb = same & np.isfinite(s_top) & (c > s_top) & (mx <= s_top) & ~ib
        ns = same & np.isfinite(s_bot) & (c < s_bot) & (mn >= s_bot) & ~isb
        ib_stop[nb] = b.rolling(lo, k + 3, "min")[nb] - TICK
        is_stop[ns] = b.rolling(h, k + 3, "max")[ns] + TICK
        ib |= nb
        isb |= ns
    E.add(np.flatnonzero(ib), "ifvg_bull", ib_stop[ib])
    E.add(np.flatnonzero(isb), "ifvg_bear", is_stop[isb])


def _cisd_side(b: Bars, sign):
    """Bullish (sign 1) CISD: the first close above the open of the last run of >= 2 bearish candles, the run ended within
    4 bars of the same day; stop 1 tick beyond the run's extreme (and the signal bar's). sign -1 mirrors it."""
    o, c = b.o * sign, b.c * sign
    low = b.l if sign > 0 else -b.h                    # the extreme on the stop side, in the mirrored space
    against = c < o
    hit, stop = np.zeros(b.n, bool), np.full(b.n, np.nan)
    lvl, end, ext = np.nan, -99, np.nan
    run, run_open, run_ext = 0, np.nan, np.nan
    for i in range(b.n):
        if b.first[i]:
            lvl, end, run = np.nan, -99, 0
        if np.isfinite(lvl) and i - end <= 4 and c[i] > lvl and c[i - 1] <= lvl:
            hit[i], stop[i], lvl = True, min(ext, low[i]), np.nan
        if against[i]:
            if run == 0:
                run_open, run_ext = o[i], low[i]
            run += 1
            run_ext = min(run_ext, low[i])
            if run >= 2:
                lvl, end, ext = run_open, i, run_ext
        else:
            run = 0
    return hit, stop * sign - sign * TICK


def other_triggers(b: Bars, D: dict, X: dict, news_bar, E: Events):
    """CISD, displacement, VWAP cross, gap fill, the news bar and the plain 15-minute slots."""
    o, h, lo, c, did, mod = b.o, b.h, b.l, b.c, b.did, b.mod
    for sign, name in ((1, "cisd_bull"), (-1, "cisd_bear")):
        hit, stop = _cisd_side(b, sign)
        E.add(np.flatnonzero(hit), name, stop[hit])
    rng = np.maximum(h - lo, 1e-9)
    up = (c - o >= 1.5 * X["atr"]) & ((h - c) / rng <= 0.25)                # body >= 1.5 ATR, close in the outer quarter
    dn = (o - c >= 1.5 * X["atr"]) & ((c - lo) / rng <= 0.25)
    E.add(np.flatnonzero(up), "disp_bull", lo[up] - TICK)
    E.add(np.flatnonzero(dn), "disp_bear", h[dn] + TICK)
    pvw = _shift(X["vwap"], 1)
    third = np.r_[False, False, did[2:] == did[:-2]]
    up = third & (c > X["vwap"]) & (X["pcl"] <= pvw)
    dn = third & (c < X["vwap"]) & (X["pcl"] >= pvw)
    E.add(np.flatnonzero(up), "vwap_up", X["lo6"][up] - TICK)
    E.add(np.flatnonzero(dn), "vwap_dn", X["hi6"][dn] + TICK)
    pc, gx = D["pc"][did], D["gapx"][did]                                  # gap >= 0.15 daily ATR, fade the first touch
    iu = _first_per_group((mod >= 930) & (gx > 0.15) & (lo <= pc), did)
    idn = _first_per_group((mod >= 930) & (gx < -0.15) & (h >= pc), did)
    E.add(iu, "gapfill_dn", X["lo6"][iu] - TICK)
    E.add(idn, "gapfill_up", X["hi6"][idn] + TICK)
    up, dn = news_bar & (c > o), news_bar & (c < o)
    E.add(np.flatnonzero(up), "news_long", lo[up] - TICK)
    E.add(np.flatnonzero(dn), "news_short", h[dn] + TICK)
    nxt = np.r_[mod[1:], -1]                                                # decide at the bar before the slot opens
    si = np.flatnonzero((nxt >= 0) & (nxt % 15 == 0) & (np.r_[did[1:], -1] == did))
    E.add(si, "slot_long", X["lo6"][si] - TICK)
    E.add(si, "slot_short", X["hi6"][si] + TICK)


# ------------------------------------------------------------------------------------------------ outcomes
def outcomes(b: Bars, ti, tk, stop) -> dict:
    """The mini-backtest of every event. Drops events without a next bar the same day, entries from 16:00 ET, stops on the
    wrong side of the entry and stops over MAX_STOP. Returns the kept rows sorted by (trigger, bar)."""
    n, did = b.n, b.did
    dirs = np.array([x[2] for x in TRIGS], dtype=np.int8)[tk]
    e = ti + 1
    ok = (e < n) & np.isfinite(stop)
    ok[ok] &= did[e[ok]] == did[ti[ok]]
    ok[ok] &= b.mod[e[ok]] < 1320
    ok[ok] &= (b.o[e[ok]] - stop[ok]) * dirs[ok] > 0
    risk = np.full(len(ti), np.inf)
    risk[ok] = np.maximum((b.o[e[ok]] - stop[ok]) * dirs[ok], MIN_STOP)
    ok &= risk <= MAX_STOP
    keep = np.flatnonzero(ok)
    keep = keep[np.lexsort((ti[keep], tk[keep]))]
    ti, tk, dirs, e, risk = ti[keep], tk[keep], dirs[keep], e[keep], risk[keep]
    entry = b.o[e]
    m = len(ti)
    J = e[:, None] + np.arange(H)[None, :]
    valid = J < n
    J = np.minimum(J, n - 1)
    valid &= did[J] == did[ti][:, None]
    d = dirs[:, None]
    fav = np.where(valid, np.where(d > 0, b.h[J] - entry[:, None], entry[:, None] - b.l[J]) / risk[:, None], -np.inf)
    adv = np.where(valid, np.where(d > 0, entry[:, None] - b.l[J], b.h[J] - entry[:, None]) / risk[:, None], -np.inf)

    def first_hit(mask):
        return np.where(mask.any(axis=1), np.argmax(mask, axis=1), H)

    stop_at = first_hit(adv >= 1.0)
    hits = {k: first_hit(fav >= k) < stop_at for k in (1, 2, 3)}
    last_c = b.c[J[np.arange(m), np.maximum(valid.sum(axis=1) - 1, 0)]] if m else np.array([])
    R = np.where(first_hit(fav >= TGT_R) < stop_at, TGT_R, np.where(stop_at < H, -1.0, (last_c - entry) * dirs / risk))
    fwd = {}
    for minutes, k in ((15, 2), (30, 5), (60, 11)):
        j = e + k
        okj = j < n
        okj[okj] &= did[j[okj]] == did[ti[okj]]
        x = np.full(m, np.nan)
        x[okj] = (b.c[j[okj]] - entry[okj]) * dirs[okj]
        fwd[minutes] = x.astype(np.float32)
    emod = b.mod[e]
    return {"ti": ti, "trig": tk, "dir": dirs, "emod": emod, "risk": risk.astype(np.float32), "R": R.astype(np.float32),
            "pnl": (R * risk * PT_USD - COST).astype(np.float32), "h1": hits[1], "h2": hits[2], "h3": hits[3],
            "f15": fwd[15], "f30": fwd[30], "f60": fwd[60]}


def states(b: Bars, D: dict, X: dict, ti, dirs) -> dict:
    """The "while" states at each decision bar (direction-relative where it matters: with / against)."""
    day = b.did[ti]
    side = lambda x: np.where(~np.isfinite(x), -1, np.where(np.sign(x) == dirs, 0, 1)).astype(np.int8)  # noqa: E731
    rel3 = lambda x: np.where(~np.isfinite(x), -1, np.where(x > 0, 0, np.where(x == 0, 1, 2))).astype(np.int8)  # noqa: E731
    er = X["esrel"][ti]
    s = X["smt"][ti]
    with_trade = ((s == 1) & (dirs < 0)) | ((s == 2) & (dirs > 0))
    return {"vwap": side(b.c[ti] - X["vwap"][ti]), "ema": side(b.c[ti] - X["ema"][ti]), "atr": D["atr"][day],
            "vix": D["vix"][day], "vxn": D["vxn"][day], "lsa": X["lsa"][ti], "today": X["today"][ti], "prev": D["prev"][day],
            "wd": D["wd"][day], "dst": D["dst"][day], "news": D["news"][day], "gap": X["gap"][ti],
            "smt": np.where(s < 0, -1, np.where(s == 0, 0, np.where(with_trade, 1, 2))).astype(np.int8),
            "orw": np.where(b.mod[ti] >= 945, D["orw"][day], -1).astype(np.int8),
            "orp": rel3(X["or_side"][ti] * dirs), "gapt": X["gapt"][ti], "vts": D["vts"][day], "vtr": D["vtr"][day],
            "esr": rel3(np.where(np.isfinite(er), np.where(np.abs(er) > ESR_PCT, np.sign(er), 0.0), np.nan) * dirs),
            "cal": D["cal"][day]}


# ------------------------------------------------------------------------------------------------ build
def build(df: pd.DataFrame, es=None, vix=None, vxn=None, news=None, vix3m=None) -> dict:
    """The event table of a tidy 5m frame: {"ev": {column: array}, "days", "last_t", "last_mod", "bars": bar facts}."""
    b = Bars(df)
    D = day_facts(b, vix, vxn, news, vix3m)
    X = bar_facts(b, D, es)
    E = Events()
    level_triggers(b, D, X, E)
    gap_triggers(b, X, E)
    other_triggers(b, D, X, news_bars(b, news), E)
    res = outcomes(b, *E.arrays())
    ti = res.pop("ti")
    emod = res.pop("emod")
    emins = (emod + 1080) % 1440
    ev = {"t": b.t[ti], "bar": ti, "day": b.did[ti].astype(np.int32),
          "win": np.searchsorted([w[1] for w in WINDOWS[1:]], emod, side="right").astype(np.int8),
          "slot": (emins // 15).astype(np.int16), **res,
          **{f"s_{k}": np.asarray(v, dtype=np.int8) for k, v in states(b, D, X, ti, res["dir"]).items()}}
    return {"ev": ev, "days": b.days, "last_t": int(b.t[-1]) if b.n else 0, "last_mod": int(b.mod[-1]) if b.n else 0,
            "bars": {k: X[k] for k in ("vwap", "ema", "atr", "today", "lsa", "gap", "smt")}}


def complete_days(feat) -> int:
    """How many leading days are over in the data: every day but the last, and the last too once its 15:55 ET bar is in."""
    nd = len(feat["days"])
    if not nd:
        return 0
    return nd if feat.get("last_mod", 0) >= 1315 else nd - 1
