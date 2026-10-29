"""Market structure engine (owner 2026-10-28: "it should learn market structure for each strategy, and trade like a person").

Deterministic and READ-ONLY: closed bars in, a description of the structure out. Nothing here sizes, routes or changes an
order; the bots only quote it (engine/advisor.py, the Live View "structure" block, the narrator). No look-ahead: every value
is known at the close of the bar it is attached to.

Rules (one timeframe; 1m / 5m / 15m / 1h, the higher ones built from 1m or 5m bars by resample()):
  swing high      bar j whose high is ABOVE the k highs before it and AT LEAST the k highs after it (k = 2, the same
                  fractal as engine/lit.fractals); it exists only from the close of bar j + k (confirmed). Mirror for lows.
  labels          each swing high vs the previous swing high: HH (higher) / LH (lower or equal); each swing low vs the
                  previous swing low: HL (higher) / LL (lower or equal); the first of each side "H" / "L".
  break (close)   a bar CLOSING above the latest unbroken swing high is a break up; closing below the latest unbroken swing
                  low is a break down. A break with the trend (or from "range") is a BOS, against the trend a CHoCH. The
                  trend becomes the break's direction.
  protected swing after a break up the protected low = the lowest low from the broken swing high's bar to the break bar (the
                  origin of the leg that broke); it must hold. A close below the protected low while up = CHoCH down (even
                  when no newer swing low exists). Mirror for down. Each new BOS moves the protected swing to its own leg.
  trend           "up" / "down" after the last break, "range" before the first one in the window.
  dealing range   up: protected low -> the highest high since it; down: protected high -> the lowest low since it; range:
                  the latest swing low -> the latest swing high, stretched by price since. eq = the middle; above eq =
                  premium, below = discount. Taken from the 15m frame (5m when 15m has no swings yet).
  displacement    a run of same-direction candles holding a body >= 1.0 ATR(14) (ATR as engine/lit.atr) is a displacement
                  leg (start, end, direction, points, biggest body in ATR).
  liquidity pools buy-side (above highs) / sell-side (below lows): today's session boxes Asia 20:00-24:00, London 02:00-05:00,
                  NY open 09:30-10:30 (engine/lit.SESSIONS asia20 / lon25 / ny9301030; a box is a level only after its last
                  bar closed), the prior trading day's high / low, equal highs / lows (engine/lit.buildups on 5m: two swings
                  within max(1.5, 0.15 ATR), untouched between), and the unbroken 1h swing highs / lows. swept = price traded
                  through the pool after it was known.

API
  Tracker(secs)               one timeframe, one closed bar at a time (push); snapshot() = trend, last event, swings,
                              protected swing, dealing range, legs. Incremental: O(1) a bar (the protected swing is a
                              slice min / max only at a break).
  resample(rows, secs, now)   1m / 5m rows -> closed bars of a higher timeframe (a bucket counts only once it has ended).
  analyze(b1, b5, now)        bounded windows (WINDOW bars per timeframe) -> every frame + pools + zone (full detail).
  block(...)                  the dashboards' "structure" block (engine/liveview_api.view, phone_view), exactly the shape
                              the Live View renders; cached on the last closed bar (a new 1m close = one recompute).
  frame_events(...)           research: one Tracker over a whole history, every break with the bar it is known at.

    python -X utf8 -m tests.test_structure
"""
from __future__ import annotations

import datetime as dt
import math
import time
from collections import deque
from zoneinfo import ZoneInfo

import numpy as np

ET = ZoneInfo("America/New_York")
TICK = 0.25
TF_SECS = {"1m": 60, "5m": 300, "15m": 900, "1h": 3600}
WINDOW = {"1m": 720, "5m": 864, "15m": 672, "1h": 360}      # bars kept per frame on the live poll (12 h / 3 / 7 / 15 days)
K = 2                                                         # fractal half-width (= engine/lit.fractals)
DISP_ATR = 1.0                                                # displacement candle: body >= 1.0 ATR(14)
SESSION_POOLS = (("asia20", "Asia"), ("lon25", "London"), ("ny9301030", "NY open"))
N_SWINGS = 20
N_POOLS = 16


# ================================================================================================ one timeframe
class Tracker:
    """Market structure of one timeframe from closed bars, one at a time (see the module rules)."""

    def __init__(self, secs: int, k: int = K, keep: int = 4000, disp: float = DISP_ATR, max_events: int | None = 200,
                 max_swings: int | None = 200):
        self.secs, self.k, self.keep, self.disp = int(secs), int(k), int(keep), float(disp)
        self.t, self.o, self.h, self.l, self.c = [], [], [], [], []
        self.base = 0                 # absolute index of the buffers' first bar
        self.n = 0                    # bars pushed so far
        self.atr = None               # ATR(14) of the last bar (engine/lit.atr recursion)
        self._atr_prev = None         # ATR of the bar before (displacement compares the body with it)
        self.trend = 0
        self.sh = None                # latest confirmed swing high [level, abs j, t, broken]
        self.sl = None
        self.prev_hi = self.prev_lo = None
        self.prot_hi = None           # (level, abs j, t)
        self.prot_lo = None
        self.swings = deque(maxlen=max_swings)
        self.events = deque(maxlen=max_events)
        self.legs = deque(maxlen=50)
        self._run = None              # [dir, abs start, open, max body ATR, t0]

    # ---- buffers
    def _b(self, arr, j):
        return arr[j - self.base]

    def _trim(self):
        if len(self.t) > 2 * self.keep:
            cut = len(self.t) - self.keep
            for a in (self.t, self.o, self.h, self.l, self.c):
                del a[:cut]
            self.base += cut

    def _min_low(self, a, z):
        """(lowest low, its abs index) over abs bars a..z (inclusive), the latest on ties."""
        a = max(a, self.base)
        seg = self.l[a - self.base:z - self.base + 1]
        m = min(seg)
        j = a + len(seg) - 1 - seg[::-1].index(m)
        return m, j

    def _max_high(self, a, z):
        a = max(a, self.base)
        seg = self.h[a - self.base:z - self.base + 1]
        m = max(seg)
        j = a + len(seg) - 1 - seg[::-1].index(m)
        return m, j

    # ---- one closed bar
    def push(self, t, o, h, l, c) -> list:
        """Add one CLOSED bar; returns the events it produced (breaks), each known at this bar's close."""
        t, o, h, l, c = int(t), float(o), float(h), float(l), float(c)
        if self.t and t <= self.t[-1]:
            return []                 # same / older bar: ignored (the caller feeds closed bars in order)
        prev_c = self.c[-1] if self.c else c
        self.t.append(t); self.o.append(o); self.h.append(h); self.l.append(l); self.c.append(c)
        i = self.n
        self.n += 1
        tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
        self._atr_prev = self.atr
        self.atr = tr if self.atr is None else self.atr + (tr - self.atr) / 14.0
        out = []
        # 1) the swing confirmed by this close (bar j = i - k)
        k = self.k
        j = i - k
        if j - k >= self.base:
            hj, lj = self._b(self.h, j), self._b(self.l, j)
            left_h = self.h[j - k - self.base:j - self.base]
            right_h = self.h[j + 1 - self.base:i + 1 - self.base]
            if hj > max(left_h) and hj >= max(right_h):
                kind = "H" if self.prev_hi is None else ("HH" if hj > self.prev_hi else "LH")
                self.prev_hi = hj
                self.sh = [hj, j, self._b(self.t, j), False]
                self.swings.append({"t": self._b(self.t, j), "price": hj, "kind": kind, "side": 1, "j": j, "known": i})
            left_l = self.l[j - k - self.base:j - self.base]
            right_l = self.l[j + 1 - self.base:i + 1 - self.base]
            if lj < min(left_l) and lj <= min(right_l):
                kind = "L" if self.prev_lo is None else ("HL" if lj > self.prev_lo else "LL")
                self.prev_lo = lj
                self.sl = [lj, j, self._b(self.t, j), False]
                self.swings.append({"t": self._b(self.t, j), "price": lj, "kind": kind, "side": -1, "j": j, "known": i})
        # 2) a break at this close
        ev = None
        if self.sh is not None and not self.sh[3] and c > self.sh[0]:
            kind = "CHoCH" if self.trend == -1 else "BOS"
            m, jm = self._min_low(self.sh[1], i)
            self.sh[3] = True
            self.trend, self.prot_lo, self.prot_hi = 1, (m, jm, self._b(self.t, jm)), None
            ev = {"kind": kind, "dir": 1, "t": t, "price": self.sh[0], "i": i, "via": "swing", "prot": m}
        elif self.sl is not None and not self.sl[3] and c < self.sl[0]:
            kind = "CHoCH" if self.trend == 1 else "BOS"
            m, jm = self._max_high(self.sl[1], i)
            self.sl[3] = True
            self.trend, self.prot_hi, self.prot_lo = -1, (m, jm, self._b(self.t, jm)), None
            ev = {"kind": kind, "dir": -1, "t": t, "price": self.sl[0], "i": i, "via": "swing", "prot": m}
        elif self.trend == 1 and self.prot_lo is not None and c < self.prot_lo[0]:
            m, jm = self._max_high(self.prot_lo[1], i)
            lvl = self.prot_lo[0]
            self.trend, self.prot_hi, self.prot_lo = -1, (m, jm, self._b(self.t, jm)), None
            ev = {"kind": "CHoCH", "dir": -1, "t": t, "price": lvl, "i": i, "via": "protected", "prot": m}
        elif self.trend == -1 and self.prot_hi is not None and c > self.prot_hi[0]:
            m, jm = self._min_low(self.prot_hi[1], i)
            lvl = self.prot_hi[0]
            self.trend, self.prot_lo, self.prot_hi = 1, (m, jm, self._b(self.t, jm)), None
            ev = {"kind": "CHoCH", "dir": 1, "t": t, "price": lvl, "i": i, "via": "protected", "prot": m}
        if ev is not None:
            ev["known_t"] = t + self.secs
            self.events.append(ev)
            out.append(ev)
        # 3) displacement legs (runs of same-direction candles holding a body >= disp x ATR of the bar before)
        d = 1 if c > o else (-1 if c < o else 0)
        a0 = self._atr_prev if self._atr_prev else self.atr
        body = abs(c - o) / a0 if a0 else 0.0
        r = self._run
        if r is not None and d == r[0] and d != 0:
            r[3] = max(r[3], body)
        else:
            if r is not None and r[3] >= self.disp:
                self._close_leg(r, i - 1)
            self._run = [d, i, o, body, t] if d != 0 else None
        self._trim()
        return out

    def _close_leg(self, r, z):
        self.legs.append({"dir": r[0], "t0": r[4], "t1": self._b(self.t, z), "from": r[2], "to": self._b(self.c, z),
                          "pts": round(abs(self._b(self.c, z) - r[2]), 2), "body_atr": round(r[3], 2)})

    # ---- views
    def trend_word(self) -> str:
        return {1: "up", -1: "down"}.get(self.trend, "range")

    def protected(self) -> dict:
        return {"high": _r(self.prot_hi[0]) if self.prot_hi else None, "low": _r(self.prot_lo[0]) if self.prot_lo else None}

    def last_event(self) -> dict | None:
        if not self.events:
            return None
        e = self.events[-1]
        return {"kind": e["kind"], "dir": int(e["dir"]), "t": int(e["t"]), "price": _r(e["price"])}

    def dealing_range(self) -> dict | None:
        if not self.t:
            return None
        z = self.n - 1
        if self.trend == 1 and self.prot_lo is not None:
            lo = self.prot_lo[0]
            hi = self._max_high(self.prot_lo[1], z)[0]
        elif self.trend == -1 and self.prot_hi is not None:
            hi = self.prot_hi[0]
            lo = self._min_low(self.prot_hi[1], z)[0]
        elif self.sh is not None and self.sl is not None:
            hi = max(self.sh[0], self._max_high(self.sh[1], z)[0])
            lo = min(self.sl[0], self._min_low(self.sl[1], z)[0])
        else:
            return None
        if hi - lo < TICK:
            return None
        return {"lo": _r(lo), "hi": _r(hi), "eq": _r((lo + hi) / 2.0)}

    def open_leg(self) -> dict | None:
        r = self._run
        if r is None or r[3] < self.disp or not self.t:
            return None
        return {"dir": r[0], "t0": r[4], "t1": self.t[-1], "from": r[2], "to": self.c[-1], "pts": round(abs(self.c[-1] - r[2]), 2),
                "body_atr": round(r[3], 2), "open": True}

    def snapshot(self, n_swings: int = N_SWINGS) -> dict:
        sw = [{"t": int(s["t"]), "price": _r(s["price"]), "kind": s["kind"]} for s in list(self.swings)[-n_swings:]]
        legs = list(self.legs)[-5:]
        ol = self.open_leg()
        if ol:
            legs.append(ol)
        return {"trend": self.trend_word(), "last_event": self.last_event(), "swings": sw, "protected": self.protected(),
                "range": self.dealing_range(), "legs": legs, "bars": self.n, "last_t": self.t[-1] if self.t else None,
                "atr": _r(self.atr) if self.atr is not None else None}


def _r(x, d=2):
    try:
        v = float(x)
        return None if v != v else round(v, d)
    except (TypeError, ValueError):
        return None


# ================================================================================================ bars
def as_rows(x) -> list:
    """[[t, o, h, l, c], ...] from rows, a list of dicts (time/open/high/low/close) or a DataFrame."""
    if x is None:
        return []
    if hasattr(x, "columns"):
        if not len(x):
            return []
        return [[int(a), float(b), float(c), float(d), float(e)] for a, b, c, d, e in
                zip(x["time"], x["open"], x["high"], x["low"], x["close"])]
    out = []
    for r in x:
        if isinstance(r, dict):
            out.append([int(r.get("time", r.get("t"))), float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"])])
        else:
            out.append([int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4])])
    return out


def resample(rows, secs: int, src_secs: int | None = None, now: int | None = None) -> list:
    """Closed bars of `secs` (5m / 15m / 1h on the clock grid; whole-hour ET offsets, so UTC hours = ET hours) from closed
    rows of a smaller timeframe. A bucket is closed once a later bucket has a bar, its last source bar ends at the bucket's
    end, or `now` passed the end. src_secs = the source timeframe (guessed from the rows' spacing when None)."""
    rows = rows or []
    if not rows:
        return []
    if src_secs is None:
        src_secs = _guess_secs(rows)
    if src_secs >= secs:
        return [list(r) for r in rows]
    out = []
    cur = None
    for t, o, h, l, c in rows:
        g = int(t) // secs * secs
        if cur is None or g != cur[0]:
            if cur is not None:
                out.append(cur[:5])
            cur = [g, o, h, l, c, int(t)]
        else:
            cur[2] = max(cur[2], h); cur[3] = min(cur[3], l); cur[4] = c; cur[5] = int(t)
    if cur is not None:
        ended = cur[5] + src_secs >= cur[0] + secs or (now is not None and int(now) >= cur[0] + secs)
        if ended:
            out.append(cur[:5])
    return out


def _guess_secs(rows) -> int:
    if len(rows) < 2:
        return 60
    d = [rows[i + 1][0] - rows[i][0] for i in range(min(len(rows) - 1, 50))]
    d = [x for x in d if x > 0]
    return int(min(d)) if d else 60


def closed_only(rows, secs: int, now: int | None) -> list:
    """Drop a bar still forming at `now` (t + secs > now)."""
    if now is None:
        return rows
    return [r for r in rows if int(r[0]) + secs <= int(now)]


# ================================================================================================ ET helpers
_OFF: dict = {}


def et_offset(t: int) -> int:
    """ET offset in seconds of a unix time (cached per hour)."""
    hk = int(t) // 3600
    v = _OFF.get(hk)
    if v is None:
        v = int(dt.datetime.fromtimestamp(hk * 3600, ET).utcoffset().total_seconds())
        if len(_OFF) > 20000:
            _OFF.clear()
        _OFF[hk] = v
    return v


def et_mod(t: int) -> int:
    return ((int(t) + et_offset(t)) % 86400) // 60


def trading_day(t: int) -> str:
    """CME trading day of a unix time (18:00 ET -> 17:00 ET belongs to the next date)."""
    x = int(t) + et_offset(t) + 6 * 3600
    return dt.datetime.fromtimestamp(x, dt.timezone.utc).strftime("%Y-%m-%d")


# ================================================================================================ pools
def pools(b5: list, now: int | None = None, h1_swings: list | None = None, price: float | None = None, n: int = N_POOLS) -> list:
    """Liquidity pools from closed 5m rows (today's session boxes, the prior day's high / low, equal highs / lows) plus the
    unbroken 1h swings (h1_swings = Tracker.swings of the 1h frame). Each: price, side buy (above highs) / sell (below lows),
    label, t0 (known from), swept (traded through after t0). Nearest to the price first, at most n."""
    from engine import lit
    if not b5:
        return []
    T = np.array([r[0] for r in b5], dtype=np.int64)
    H = np.array([r[2] for r in b5], dtype=float)
    L = np.array([r[3] for r in b5], dtype=float)
    C = np.array([r[4] for r in b5], dtype=float)
    days = [trading_day(int(t)) for t in T]
    mods = np.array([et_mod(int(t)) for t in T])
    today = days[-1]
    ix_today = [i for i, d in enumerate(days) if d == today]
    s0 = ix_today[0]
    prev_days = sorted({d for d in days if d < today})
    out = []

    def swept_after(i_known, side, px):
        a = i_known + 1
        if a >= len(T):
            return False
        return bool(H[a:].max() > px) if side == "buy" else bool(L[a:].min() < px)

    # today's session boxes (engine/lit.SESSIONS), a level once the box's last bar closed
    for nm, label in SESSION_POOLS:
        a, z = lit.SESSIONS[nm]
        md = mods[s0:]
        if a < z:
            ii = np.flatnonzero((md >= a) & (md < z))
        else:
            ii = np.flatnonzero(md >= a)
        if a >= 1080:
            ii = ii[md[ii] >= 1080]
        else:
            ii = ii[md[ii] < 1080]
        if len(ii) < 2:
            continue
        last = s0 + int(ii[-1])
        if last == len(T) - 1 and int(mods[last]) + 5 < z:
            continue                                   # the box is still forming (its last bar has not come yet)
        hi, lo = float(H[s0 + ii].max()), float(L[s0 + ii].min())
        t_known = int(T[last]) + 300
        out.append({"price": _r(hi), "side": "buy", "label": f"{label} high", "t0": t_known, "swept": swept_after(last, "buy", hi)})
        out.append({"price": _r(lo), "side": "sell", "label": f"{label} low", "t0": t_known, "swept": swept_after(last, "sell", lo)})
    # prior trading day high / low (known at today's 18:00 open)
    if prev_days:
        pd_ = prev_days[-1]
        ii = [i for i, d in enumerate(days) if d == pd_]
        if ii:
            hi, lo = float(H[ii].max()), float(L[ii].min())
            t_known = int(T[s0])
            out.append({"price": _r(hi), "side": "buy", "label": "Prior day high", "t0": t_known, "swept": swept_after(s0 - 1, "buy", hi)})
            out.append({"price": _r(lo), "side": "sell", "label": "Prior day low", "t0": t_known, "swept": swept_after(s0 - 1, "sell", lo)})
    # equal highs / lows (engine/lit.buildups on these 5m bars), known in the last day
    if len(T) >= 20:
        at = lit.atr(H, L, C, 14)
        fh, fl = pivots(H, L, K)
        for side, px, ki in lit.buildups(H, L, fh, fl, at, tol_atr=0.15, lookback=288):
            if ki >= len(T) or ki < len(T) - 288:
                continue
            sd = "buy" if side == "high" else "sell"
            out.append({"price": _r(px), "side": sd, "label": "Equal highs" if sd == "buy" else "Equal lows",
                        "t0": int(T[ki]) + 300, "swept": swept_after(ki, sd, px)})
    # unbroken 1h swings (buy-side above swing highs, sell-side below swing lows)
    for s in (h1_swings or [])[-12:]:
        if int(s["t"]) < int(T[0]):
            continue                                   # older than these 5m bars: "unbroken" cannot be checked
        sd = "buy" if s.get("side", 1) == 1 else "sell"
        px = float(s["price"])
        i0 = int(np.searchsorted(T, int(s["t"]) + 3600))
        sw = bool(i0 < len(T) and ((H[i0:].max() > px) if sd == "buy" else (L[i0:].min() < px)))
        if sw:
            continue
        out.append({"price": _r(px), "side": sd, "label": "1h swing high" if sd == "buy" else "1h swing low",
                    "t0": int(s["t"]) + 3600 * (K + 1), "swept": False})
    # de-duplicate (same side within 1 tick: keep the first, session / day levels beat equal highs / swings)
    ded = []
    for p in out:
        if p["price"] is None:
            continue
        if any(q["side"] == p["side"] and abs(q["price"] - p["price"]) <= TICK for q in ded):
            continue
        ded.append(p)
    ref = float(price) if price is not None else float(C[-1])
    ded.sort(key=lambda p: (p["swept"], abs(p["price"] - ref)))
    return ded[:n]


def pivots(h, l, k: int = K):
    """Vectorised engine/lit.fractals: (swing-high indices, swing-low indices) of numpy arrays (same rule, same result)."""
    h = np.asarray(h, float); l = np.asarray(l, float)
    n = len(h)
    if n < 2 * k + 1:
        return np.zeros(0, np.int64), np.zeros(0, np.int64)
    from numpy.lib.stride_tricks import sliding_window_view as sw
    Wh, Wl = sw(h, k), sw(l, k)                     # Wh[s] = h[s:s+k]
    j = np.arange(k, n - k)
    left_h, right_h = Wh[j - k].max(axis=1), Wh[j + 1].max(axis=1)
    left_l, right_l = Wl[j - k].min(axis=1), Wl[j + 1].min(axis=1)
    fh = j[(h[j] > left_h) & (h[j] >= right_h)]
    fl = j[(l[j] < left_l) & (l[j] <= right_l)]
    return fh, fl


# ================================================================================================ all frames
def frames_from(b1: list | None, b5: list | None, now: int | None = None, tfs=("1m", "5m", "15m", "1h"),
                window: dict | None = None) -> dict:
    """{tf: closed rows} for each timeframe: 1m from b1; 5m from b5 (else built from b1); 15m / 1h from whichever source
    reaches further back (both bounded to the frame's window)."""
    W = {**WINDOW, **(window or {})}
    b1 = closed_only(as_rows(b1), 60, now)
    b5 = closed_only(as_rows(b5), 300, now)
    out = {}
    for tf in tfs:
        secs = TF_SECS[tf]
        t_from = (int(now) if now else (b1[-1][0] if b1 else (b5[-1][0] if b5 else 0))) - W[tf] * secs
        if tf == "1m":
            rows = [r for r in b1 if r[0] >= t_from]
        else:
            s1 = [r for r in b1 if r[0] >= t_from]
            s5 = [r for r in b5 if r[0] >= t_from]
            a1 = s1[0][0] if s1 else None
            a5 = s5[0][0] if s5 else None
            if a5 is not None and (a1 is None or a5 <= a1):
                # the 5m source reaches further back; 1m bars newer than its last bucket extend it (the 5m tail lags)
                rows = resample(s5, secs, 300, now)
                if s1:
                    last = rows[-1][0] if rows else -1
                    rows += [r for r in resample([x for x in s1 if x[0] >= last + secs], secs, 60, now) if r[0] > last]
            else:
                rows = resample(s1, secs, 60, now)
        out[tf] = rows[-W[tf]:]
    return out


def analyze(b1=None, b5=None, now: int | None = None, price: float | None = None, tfs=("1m", "5m", "15m", "1h"),
            window: dict | None = None) -> dict:
    """Full detail on bounded windows: {"t", "price", "frames": {tf: Tracker.snapshot()}, "pools", "zone", "ms"}."""
    t_start = time.perf_counter()
    F = frames_from(b1, b5, now, tfs, window)
    snaps, trackers = {}, {}
    for tf in tfs:
        tr = Tracker(TF_SECS[tf])
        for r in F[tf]:
            tr.push(*r)
        trackers[tf] = tr
        snaps[tf] = tr.snapshot()
    last = None
    for tf in tfs:
        if F[tf]:
            last = F[tf][-1][4] if last is None else last
    px = float(price) if price is not None else last
    h1sw = list(trackers["1h"].swings) if "1h" in trackers else []
    P = pools(F.get("5m") or [], now, h1sw, px)
    zone = None
    for tf in ("15m", "5m"):
        rg = snaps.get(tf, {}).get("range")
        if rg:
            zone = {**rg, "premium": bool(px is not None and px > rg["eq"]), "tf": tf}
            break
    return {"t": int(now) if now else (int(F["1m"][-1][0]) + 60 if F.get("1m") else None), "price": _r(px), "frames": snaps,
            "pools": P, "zone": zone, "ms": round((time.perf_counter() - t_start) * 1000.0, 1),
            "n": {tf: len(F[tf]) for tf in tfs}}


# ================================================================================================ the dashboards' block
BLOCK_FRAMES = ("5m", "15m", "1h")


def _frame_block(s: dict) -> dict:
    return {"trend": s.get("trend") or "range", "last_event": s.get("last_event"), "swings": list(s.get("swings") or [])[-N_SWINGS:],
            "protected": {"high": (s.get("protected") or {}).get("high"), "low": (s.get("protected") or {}).get("low")}}


def bias_for(A: dict) -> dict:
    """Per strategy: what structure says about the side (advice only; the strategies' own rules decide)."""
    fr = A.get("frames") or {}
    tw = {tf: (fr.get(tf) or {}).get("trend", "range") for tf in ("5m", "15m", "1h")}
    z = A.get("zone")
    prem = None if not z else bool(z.get("premium"))
    side = {"up": "long", "down": "short"}
    out = {}
    # LIT (Zlarior): reversal after a sweep. Structure helps when the 1h agrees and price sits on the cheap / dear side.
    h1 = tw["1h"]
    if h1 == "up" and prem is False:
        out["lit"] = {"bias": "long", "note": "1h up and price in the discount half: a long after a sell-side sweep fits the structure."}
    elif h1 == "down" and prem is True:
        out["lit"] = {"bias": "short", "note": "1h down and price in the premium half: a short after a buy-side sweep fits the structure."}
    elif h1 in ("up", "down") and prem is None:
        out["lit"] = {"bias": side[h1], "note": f"1h {h1}; no dealing range yet for premium / discount. LIT's own rules decide."}
    elif h1 in ("up", "down"):
        out["lit"] = {"bias": side[h1], "note": f"1h {h1}, but price is in the {'premium' if prem else 'discount'} half: "
                      f"a {side[h1]} here would {'buy high' if h1 == 'up' else 'sell low'}; LIT's own rules decide."}
    else:
        out["lit"] = {"bias": "none", "note": "1h has no trend yet (range): no structure side for LIT; LIT's own rules decide."}
    # ATLAS: trend pullbacks / sweeps on 5m with the 15m + 1h trend.
    if tw["15m"] == tw["1h"] and tw["1h"] in ("up", "down"):
        out["atlas"] = {"bias": side[tw["1h"]], "note": f"15m and 1h both {tw['1h']}: ATLAS's trend pullbacks fit {side[tw['1h']]}s."}
    else:
        out["atlas"] = {"bias": "none", "note": f"15m {tw['15m']}, 1h {tw['1h']}: the trends disagree, no clean side for ATLAS."}
    # BLITZ: intraday momentum out of the noise band; the 5m structure is the tell.
    ev = (fr.get("5m") or {}).get("last_event")
    if tw["5m"] in ("up", "down"):
        e = f" (last {ev['kind']} {'up' if ev['dir'] > 0 else 'down'} at {ev['price']:,.2f})" if ev else ""
        out["scalp"] = {"bias": side[tw["5m"]], "note": f"5m {tw['5m']}{e}: momentum {side[tw['5m']]}s go with it."}
    else:
        out["scalp"] = {"bias": "none", "note": "5m is ranging: no momentum side yet."}
    return out


def summary_line(A: dict) -> str:
    fr = A.get("frames") or {}
    parts = []
    for tf in BLOCK_FRAMES:
        s = fr.get(tf) or {}
        ev = s.get("last_event")
        parts.append(f"{tf} {s.get('trend', 'range')}" + (f" ({ev['kind']} {'up' if ev['dir'] > 0 else 'down'})" if ev else ""))
    txt = "Structure: " + ", ".join(parts)
    z = A.get("zone")
    px = A.get("price")
    if z and px is not None:
        txt += f"; price {px:,.2f} in the {'premium' if z['premium'] else 'discount'} of {z['lo']:,.2f}-{z['hi']:,.2f}"
    P = [p for p in A.get("pools") or [] if not p.get("swept") and px is not None]
    up = min((p for p in P if p["side"] == "buy" and p["price"] > px), key=lambda p: p["price"] - px, default=None)
    dn = min((p for p in P if p["side"] == "sell" and p["price"] < px), key=lambda p: px - p["price"], default=None)
    if up or dn:
        bits = []
        if up:
            bits.append(f"buy-side {up['price']:,.2f} ({up['label']}) above")
        if dn:
            bits.append(f"sell-side {dn['price']:,.2f} ({dn['label']}) below")
        txt += "; nearest pools: " + ", ".join(bits)
    return txt + "."


def to_block(A: dict) -> dict:
    """The exact Live View "structure" shape from analyze()."""
    fr = A.get("frames") or {}
    z = A.get("zone")
    return {"t": int(A.get("t") or 0), "summary": summary_line(A),
            "frames": {tf: _frame_block(fr.get(tf) or {}) for tf in BLOCK_FRAMES},
            "pools": [{"price": float(p["price"]), "side": p["side"], "label": str(p["label"]), "t0": int(p["t0"]), "swept": bool(p["swept"])}
                      for p in A.get("pools") or []],
            "zone": ({"lo": float(z["lo"]), "hi": float(z["hi"]), "eq": float(z["eq"]), "premium": bool(z["premium"])} if z else None),
            "per_strategy": bias_for(A)}


_CACHE: dict = {}


def block(b1=None, b5=None, now: int | None = None, price: float | None = None, key: str = "default") -> dict:
    """to_block(analyze(...)), cached on (key, the last closed 1m / 5m bar): the page polls every ~3 s, the structure changes
    once a bar closes. The price only moves the summary / premium flag, so those are refreshed on every call."""
    r1 = closed_only(as_rows(b1), 60, now)
    r5 = closed_only(as_rows(b5), 300, now)
    sig = (key, r1[-1][0] if r1 else None, r5[-1][0] if r5 else None, len(r1), len(r5))
    hit = _CACHE.get(key)
    if hit and hit[0] == sig:
        A = hit[1]
    else:
        A = analyze(r1, r5, now, None)
        _CACHE[key] = (sig, A)
        if len(_CACHE) > 8:
            _CACHE.pop(next(iter(_CACHE)))
    return block_from(A, now, price)


def block_from(A: dict, now: int | None = None, price: float | None = None) -> dict:
    """to_block of an analyze() result with the current price (summary + premium flag) and time."""
    if price is not None:
        A = {**A, "price": _r(price)}
        if A.get("zone"):
            A["zone"] = {**A["zone"], "premium": bool(float(price) > A["zone"]["eq"])}
    out = to_block(A)
    if now is not None:
        out["t"] = int(now)
    return out


# ================================================================================================ research helper
def frame_events(t, o, h, l, c, secs: int, k: int = K) -> dict:
    """One Tracker over a whole history (numpy arrays): every break as arrays known_t / kind (1 BOS, 2 CHoCH) / dir / level /
    prot (the new protected swing), plus the swings (t, price, side, known_t). For research replays (no look-ahead: an event
    is usable from known_t = its bar's close)."""
    tr = Tracker(secs, k=k, keep=500, max_events=None, max_swings=None)
    for a, b_, c_, d_, e_ in zip(t, o, h, l, c):
        tr.push(a, b_, c_, d_, e_)
    E = list(tr.events)
    S = list(tr.swings)
    return {"known_t": np.array([e["known_t"] for e in E], np.int64), "kind": np.array([2 if e["kind"] == "CHoCH" else 1 for e in E]),
            "dir": np.array([e["dir"] for e in E]), "level": np.array([e["price"] for e in E], float),
            "prot": np.array([e["prot"] for e in E], float),
            "sw_t": np.array([s["t"] for s in S], np.int64), "sw_px": np.array([s["price"] for s in S], float),
            "sw_side": np.array([s["side"] for s in S]), "sw_known": np.array([t[min(len(t) - 1, s["known"])] + secs for s in S], np.int64)}


def trend_at(ev: dict, ts: int) -> int:
    """Trend (1 / -1 / 0) of a frame at unix time ts from frame_events(): the direction of the last break known by ts."""
    i = int(np.searchsorted(ev["known_t"], int(ts), side="right")) - 1
    return int(ev["dir"][i]) if i >= 0 else 0


if __name__ == "__main__":
    import sys
    import pandas as pd
    p = sys.argv[1] if len(sys.argv) > 1 else "data/NQ_1m.csv"
    df = pd.read_csv(p).tail(20000)
    rows = as_rows(df)
    t0 = time.perf_counter()
    A = analyze(rows, None, int(rows[-1][0]) + 60)
    print(f"analyze {A['ms']} ms on {A['n']}")
    B = to_block(A)
    print(B["summary"])
    print({tf: (v["trend"], v["last_event"], v["protected"]) for tf, v in B["frames"].items()})
    print(math.floor((time.perf_counter() - t0) * 1000), "ms total")
