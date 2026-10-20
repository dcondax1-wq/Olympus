"""New LIT entry types and confluence tags (research/writeups/lit-new-entries.md). Pure functions on 5m arrays, no look-ahead;
engine/lit.py is not changed and nothing here is used by the live loop (every option is research-only and off).

Three building blocks:

1. MSNR (Malaysian SnR) levels from the LINE chart (closes only) of a timeframe tf (15m / 1h / 4h, resampled from 5m):
     A-level  a peak of the close line: close[j] > the k closes before it and >= the k after it -> resistance (side "high")
     V-level  a valley of the close line -> support (side "low")
     QM       quasimodo: V1, then a peak A1, then a lower valley V2 < V1 (a lower low), then the close line breaks above A1
              (the MSB) -> the bullish QM level = V1 (support, the "left shoulder"); bearish mirror (A1, V1, A2 > A1, a close
              below V1 -> QM level = A1). Known at the close of the candle that breaks.
     flip     an A-level that a close broke (resistance turned support, side "low") / a broken V-level (side "high"); MSNR's
              "unfresh after the break" SnR flip. Known at the close of the breaking candle.
   prominence: the pivot close must stand >= min_move x ATR(14) of tf away from the extreme close of the k candles on each side
   (no micro wiggles). A level is KNOWN at the close of the last 5m bar of the tf candle that confirms it (ki, a 5m index).
   Fresh = no 5m wick has reached the level since ki (first_touch).
   storyline(): the tf line-chart trend at every 5m bar: +1 after a close above the last confirmed A-level, -1 after a close
   below the last confirmed V-level (MSNR's "storyline" = the higher-timeframe direction), 0 before any break.

2. LevelMarket: an engine.lit.Market whose levels(k) returns other liquidity (MSNR levels, inducement swings) instead of / next
   to the LIT levels, so engine.lit.candidates() finds "sweep of that level + displacement + 5m CISD" exactly like LIT, and
   engine.lit.run_x trades it with the live executor (30-min limit at the CISD level, 1m CISD entry, stop 1 tick beyond the
   sweep extreme, VIX-band target, BE at 1R, weekly stop, Monday rule). A level is offered on a day only while it is still
   fresh at the start of that day's search window (no touch in (ki, s - 600]); candidates() then takes its first breach.

3. idm_ob_levels(): SMC inducement into an order block. For every fresh bullish 15m/1h block (engine/lit_ob.py), the 5m
   fractal lows that form ABOVE it (within near x ATR of its top) while it is still untouched are inducement (IDM): early
   buyers' stops resting in front of the block. A sweep of an IDM low that runs INTO the block (extreme <= the block's top +
   tol) and turns with a 5m CISD is the setup. Mirror for shorts. The block must still be untouched when the IDM forms.
"""
from __future__ import annotations

import bisect

import numpy as np

from engine import lit
from engine import lit_ob as O


# ------------------------------------------------------------------------------------------------ line chart pivots
def _atr(h, l, c, n=14):
    return O.atr(np.asarray(h, float), np.asarray(l, float), np.asarray(c, float), n)


def line_pivots(c, at, k=2, min_move=0.5):
    """(peaks, valleys): candle indices j of close-line pivots with prominence >= min_move x at[j]; confirmed at j + k."""
    c = np.asarray(c, float)
    n = len(c)
    pk, vl = [], []
    for j in range(k, n - k):
        w0, w1 = c[j - k:j], c[j + 1:j + k + 1]
        if c[j] > w0.max() and c[j] >= w1.max():
            if c[j] - min(w0.min(), w1.min()) >= min_move * at[j]:
                pk.append(j)
        if c[j] < w0.min() and c[j] <= w1.min():
            if max(w0.max(), w1.max()) - c[j] >= min_move * at[j]:
                vl.append(j)
    return np.array(pk, dtype=np.int64), np.array(vl, dtype=np.int64)


def _first_cross(c, start, px, above, limit=None):
    """First index >= start where c > px (above) / c < px (below), searched in growing chunks; None if none (before limit)."""
    n = len(c) if limit is None else min(len(c), limit)
    i, step = start, 64
    while i < n:
        seg = c[i:min(n, i + step)]
        m = seg > px if above else seg < px
        if m.any():
            return i + int(np.argmax(m))
        i += step
        step = min(step * 2, 1 << 16)
    return None


def htf(M, tf):
    return O.resample(M.t, M.o, M.h, M.l, M.c, tf, M.mod, M.day_of)


def msnr_levels(M, tf="1h", k=2, min_move=0.5, kinds=("A", "V", "QM", "F")):
    """MSNR levels of timeframe tf as dicts {side, px, ki (5m index known), kind, tf, j (tf candle)}, sorted by ki."""
    B = htf(M, tf)
    c, last = B["c"], B["last"]
    if len(c) < 2 * k + 3:
        return []
    at = _atr(B["h"], B["l"], c)
    pk, vl = line_pivots(c, at, k, min_move)
    out = []
    n = len(c)
    if "A" in kinds:
        out += [{"side": "high", "px": float(c[j]), "ki": int(last[j + k]), "kind": "A", "tf": tf, "j": int(j)} for j in pk]
    if "V" in kinds:
        out += [{"side": "low", "px": float(c[j]), "ki": int(last[j + k]), "kind": "V", "tf": tf, "j": int(j)} for j in vl]
    if "F" in kinds:
        # flips: first close beyond a confirmed pivot (from its confirmation candle on)
        for arr, side, sgn in ((pk, "low", 1), (vl, "high", -1)):
            for j in arr:
                m = _first_cross(c, j + k + 1, c[j], sgn == 1)
                if m is not None:
                    out.append({"side": side, "px": float(c[j]), "ki": int(last[m]), "kind": "F", "tf": tf, "j": int(j)})
    if "QM" in kinds:
        # pivots in time order with their confirm candle; QM confirmed at the first close beyond the middle pivot
        piv = sorted([(int(j), 1) for j in pk] + [(int(j), -1) for j in vl])
        for q in range(len(piv) - 2):
            (j1, s1), (j2, s2), (j3, s3) = piv[q], piv[q + 1], piv[q + 2]
            if not (s1 == s3 and s2 == -s1):
                continue
            if s1 == -1:     # V1, A1, V2 < V1 -> bullish QM when a close goes above A1 (after V2 is confirmed)
                if not c[j3] < c[j1]:
                    continue
                st = j3 + k + 1
                m = _first_cross(c, st, c[j2], True, st + max(1, 4 * (j3 - j1)))   # the break within a few legs
                if m is not None:
                    # no close back below V2 before the break (the lower low held)
                    if c[j3 + 1:m + 1].min() >= c[j3]:
                        out.append({"side": "low", "px": float(c[j1]), "ki": int(last[m]), "kind": "QM", "tf": tf, "j": int(j1)})
            else:            # A1, V1, A2 > A1 -> bearish QM when a close goes below V1
                if not c[j3] > c[j1]:
                    continue
                st = j3 + k + 1
                m = _first_cross(c, st, c[j2], False, st + max(1, 4 * (j3 - j1)))
                if m is not None:
                    if c[j3 + 1:m + 1].max() <= c[j3]:
                        out.append({"side": "high", "px": float(c[j1]), "ki": int(last[m]), "kind": "QM", "tf": tf, "j": int(j1)})
    out.sort(key=lambda x: x["ki"])
    return out


def first_touch(h, l, lv, start=None):
    """First 5m index after lv["ki"] (or start) where a wick reaches the level; len(h) if never."""
    n = len(h)
    i = (lv["ki"] if start is None else start) + 1
    arr, px, hi = (h, lv["px"], True) if lv["side"] == "high" else (l, lv["px"], False)
    step = 256
    while i < n:
        seg = arr[i:i + step]
        m = seg >= px if hi else seg <= px
        if m.any():
            return i + int(np.argmax(m))
        i += step
        step = min(step * 2, 1 << 16)
    return n


def add_touch(M, levels):
    for lv in levels:
        lv["touch"] = first_touch(M.h, M.l, lv)
    return levels


def storyline(M, tf="4h", k=2, min_move=0.5):
    """+1 / -1 / 0 per 5m bar: the tf close line's last break (close above the last confirmed A-level = +1, below the last
    confirmed V-level = -1), known at the close of the breaking tf candle (from the next 5m bar on)."""
    B = htf(M, tf)
    c, last = B["c"], B["last"]
    at = _atr(B["h"], B["l"], c)
    pk, vl = line_pivots(c, at, k, min_move)
    conf_a = {int(j + k): int(j) for j in pk}
    conf_v = {int(j + k): int(j) for j in vl}
    st = np.zeros(len(c), np.int8)
    la = lv = None
    cur = 0
    for m in range(len(c)):
        if la is not None and c[m] > c[la]:
            cur = 1; la = None
        elif lv is not None and c[m] < c[lv]:
            cur = -1; lv = None
        if m in conf_a:
            la = conf_a[m]
        if m in conf_v:
            lv = conf_v[m]
        st[m] = cur
    out = np.zeros(M.n, np.int8)
    # value of candle m applies from the 5m bar after last[m]
    for m in range(len(c)):
        a = int(last[m]) + 1
        b = int(last[m + 1]) + 1 if m + 1 < len(c) else M.n
        out[a:b] = st[m]
    return out


def fresh_near(levels_sorted_ki, touch, ki_arr, i, side, px_lo, px_hi):
    """Levels of `side` known by bar i (ki < i), untouched before bar i (touch >= i), with price in [px_lo, px_hi]."""
    b = bisect.bisect_left(ki_arr, i)
    return [lv for lv in levels_sorted_ki[:b] if lv["side"] == side and lv["touch"] >= i and px_lo <= lv["px"] <= px_hi]


# ------------------------------------------------------------------------------------------------ a Market with other levels
class LevelMarket(lit.Market):
    """A copy of a built Market whose levels(k) returns custom levels (and the LIT levels too when keep_lit)."""

    def __init__(self, base, levels, keep_lit=False, cls="msnr", max_age=8640, lead=600):   # noqa: D401 (no super().__init__)
        self.__dict__.update(base.__dict__)
        self._base_levels = base.levels
        self._lv = sorted(levels, key=lambda x: x["ki"])
        self._ki = [x["ki"] for x in self._lv]
        self._keep = keep_lit
        self._cls = cls
        self._age = max_age
        self._lead = lead

    def levels(self, k):
        x = self.ctx[k]
        s, e = x["s"], x["e"]
        L = list(self._base_levels(k)) if self._keep else []
        a = bisect.bisect_left(self._ki, s - self._age)
        b = bisect.bisect_left(self._ki, e)
        w0 = s - self._lead
        for lv in self._lv[a:b]:
            if lv["touch"] <= max(lv["ki"], w0):      # used up before today's search window
                continue
            nm = lv.get("name") or f"{self._cls}_{lv['tf']}_{lv['kind']}"
            L.append((lv["side"], lv["px"], lv["ki"], nm, lv.get("cls", self._cls)))
        return L


# ------------------------------------------------------------------------------------------------ SMC inducement into an OB
def idm_ob_levels(M, obs, near=2.0, max_wait=576, kind="body"):
    """IDM levels in front of fresh blocks. obs = blocks with k5 (5m known index), mit5 (first 5m touch), top / bot (zone).
    For a bullish block: every 5m fractal low that confirms (j + 2) after the block is known and before its first touch, with
    its low in (top, top + near x ATR(5m)] -> {"side": "low", "px", "ki": j + 2, "ob": block}. Mirror for bearish blocks."""
    out = []
    fl, fh = M.fl, M.fh
    for ob in obs:
        k5 = ob["k5"]
        end = min(ob["mit5"] if ob["mit5"] is not None else M.n, k5 + max_wait)
        if ob["dir"] == 1:
            a = bisect.bisect_left(fl, k5 - 1); b = bisect.bisect_left(fl, end - 2)
            for j in fl[a:b]:
                j = int(j)
                if j + 2 <= k5 or j + 2 >= end:
                    continue
                if ob["top"] < M.l[j] <= ob["top"] + near * M.atr[j]:
                    out.append({"side": "low", "px": float(M.l[j]), "ki": j + 2, "kind": "IDM", "tf": ob["tf"], "ob": ob})
        else:
            a = bisect.bisect_left(fh, k5 - 1); b = bisect.bisect_left(fh, end - 2)
            for j in fh[a:b]:
                j = int(j)
                if j + 2 <= k5 or j + 2 >= end:
                    continue
                if ob["bot"] - near * M.atr[j] <= M.h[j] < ob["bot"]:
                    out.append({"side": "high", "px": float(M.h[j]), "ki": j + 2, "kind": "IDM", "tf": ob["tf"], "ob": ob})
    out.sort(key=lambda x: x["ki"])
    return out


def selftest():
    """Line pivots, QM and storyline on a toy close line (no data needed)."""
    c = np.array([10, 11, 12, 11, 10, 9, 10, 11, 13, 12, 11, 8, 9, 10, 12, 14, 15, 14, 13], float)
    at = np.ones_like(c)
    pk, vl = line_pivots(c, at, k=2, min_move=0.5)
    assert list(pk) == [2, 8, 16], pk
    assert list(vl) == [5, 11], vl
    print("lit_entries selftest ok: peaks", list(pk), "valleys", list(vl))


if __name__ == "__main__":
    selftest()
