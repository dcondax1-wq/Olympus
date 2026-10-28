"""Mean-reversion scalp signals (research). Every signal is decided at a bar's CLOSE from data known then; the simulator
(tools/scalp_mr_lib.simulate) enters at the next bar's open. Each returns (dir, stop, target, limit) arrays:
dir +1 long / -1 short / 0, stop = 1 tick beyond the sweep extreme, target NaN = R multiple, limit NaN = market entry."""
from __future__ import annotations

import numba as nb
import numpy as np

from tools.scalp_mr_lib import TICK, arr

NAN = np.nan


def _empty(n):
    return np.zeros(n, np.int64), np.full(n, NAN), np.full(n, NAN), np.full(n, NAN)


def _trend(F, mode):
    """+1 allow longs only / -1 shorts only / 0 both, per bar. mode: none | with | against | flat."""
    n = len(F)
    if mode == "none":
        return np.zeros(n)
    c = arr(F, "close"); e = arr(F, "ema_4h"); e1 = arr(F, "ema_1h")
    up = (c > e) & (e1 > e); dn = (c < e) & (e1 < e)
    t = np.where(up, 1, np.where(dn, -1, 0))
    if mode == "with":
        return t.astype(float)
    if mode == "against":
        return -t.astype(float)
    if mode.startswith("vwflat"):  # VWAP slope over 30 bars < x ATR (range day): both sides, else none
        x = float(mode[6:] or 1.0)
        vw = arr(F, "vwap")
        sl = np.abs(vw - np.roll(vw, 30)) / np.maximum(arr(F, "atr"), 1e-9)
        return np.where(sl < x, 0, 9).astype(float)
    if mode == "flat":            # only when the 1h/4h EMAs disagree (no trend): both sides
        return np.where(t == 0, 0, 9).astype(float)
    raise ValueError(mode)


def _apply_trend(sd, tr):
    ok = (tr == 0) | (tr == sd)
    return np.where(ok & (tr != 9), sd, 0)


def _lowest(x, m):
    out = x.copy()
    for k in range(1, m):
        out[k:] = np.minimum(out[k:], x[:-k])
    return out


def _highest(x, m):
    out = x.copy()
    for k in range(1, m):
        out[k:] = np.maximum(out[k:], x[:-k])
    return out


# ------------------------------------------------------------------------------------------------ 1. VWAP band fade
def sig_vwap(F, k=2.0, m=3, anchor="session", confirm="inside", tgt="vwap", trend="none"):
    """Price pokes outside VWAP +/- k sd within the last m bars and the bar closes back inside the band (confirm
    'inside') or closes in the fade direction (confirm 'turn'). Stop beyond the lowest low / highest high of those m bars.
    Target: VWAP ('vwap'), the 1-sd band ('sd1'), or an R multiple ('r')."""
    o, h, l, c = arr(F, "open"), arr(F, "high"), arr(F, "low"), arr(F, "close")
    vw = arr(F, "vwap" if anchor == "session" else "rvwap"); sd = arr(F, "vsd" if anchor == "session" else "rvsd")
    lo_b, hi_b = vw - k * sd, vw + k * sd
    ll, hh = _lowest(l, m), _highest(h, m)
    poke_lo = _lowest(l - lo_b, m) < 0
    poke_hi = _highest(h - hi_b, m) > 0
    if confirm == "inside":
        L = poke_lo & (c > lo_b) & (c > o)
        S = poke_hi & (c < hi_b) & (c < o)
    else:
        L = poke_lo & (c > o) & (c > np.roll(h, 1))
        S = poke_hi & (c < o) & (c < np.roll(l, 1))
    sd_ = np.where(L, 1, np.where(S, -1, 0))
    sd_ = np.where(sd > 0, sd_, 0)
    sd_ = _apply_trend(sd_, _trend(F, trend))
    stop = np.where(sd_ == 1, ll - TICK, np.where(sd_ == -1, hh + TICK, NAN))
    if tgt == "vwap":
        tg = np.where(sd_ != 0, vw, NAN)
    elif tgt == "sd1":
        tg = np.where(sd_ == 1, vw - sd, np.where(sd_ == -1, vw + sd, NAN))
    else:
        tg = np.full(len(c), NAN)
    return sd_.astype(np.int64), stop, tg, np.full(len(c), NAN)


# ------------------------------------------------------------------------------------------------ 2. level sweep + reclaim
@nb.njit(cache=True)
def _sweep(h, l, c, dayi, lv, side, m, maxpen, once):
    """side +1: low breaks lv, close back above within m bars (penetration <= maxpen pts) -> long, stop below the extreme.
    side -1 mirror. once: one signal per level per day."""
    n = len(c)
    sd = np.zeros(n, np.int64); st = np.full(n, np.nan)
    armed = -1; ext = 0.0; La = 0.0; used = False; cur = -1
    for i in range(1, n):
        if dayi[i] != cur:
            cur = dayi[i]; armed = -1; used = False
        L = lv[i]
        if np.isnan(L) or (once and used):
            armed = -1
            continue
        if side == 1:
            if armed < 0:
                if l[i] < L - TICK_ and c[i - 1] > L:
                    armed = i; ext = l[i]; La = L
            else:
                ext = min(ext, l[i])
            if armed >= 0:
                if La - ext > maxpen or i - armed >= m:
                    armed = -1
                    continue
                if c[i] > La:
                    sd[i] = 1; st[i] = ext - TICK_; used = True; armed = -1
        else:
            if armed < 0:
                if h[i] > L + TICK_ and c[i - 1] < L:
                    armed = i; ext = h[i]; La = L
            else:
                ext = max(ext, h[i])
            if armed >= 0:
                if ext - La > maxpen or i - armed >= m:
                    armed = -1
                    continue
                if c[i] < La:
                    sd[i] = -1; st[i] = ext + TICK_; used = True; armed = -1
    return sd, st


TICK_ = TICK
LEVELS = {"pd": ("pdh", "pdl"), "on": ("on_h", "on_l"), "asia": ("asia_h", "asia_l"), "lon": ("lon_h", "lon_l"),
          "or": ("or_h", "or_l"), "ib": ("ib_h", "ib_l")}


def sig_levels(F, levels=("pd", "on", "asia", "lon"), m=3, maxpen=15.0, once=True, tgt="r", trend="none", rnd=0, swing=0):
    """Sweep-and-reclaim of session levels (and round numbers every `rnd` pts if rnd > 0)."""
    import pandas as pd
    h, l, c = arr(F, "high"), arr(F, "low"), arr(F, "close")
    dayi = pd.factorize(F["day"])[0].astype(np.int64)
    n = len(c)
    sd = np.zeros(n, np.int64); st = np.full(n, NAN)
    for name in levels:
        hk, lk = LEVELS[name]
        for key, side in ((lk, 1), (hk, -1)):
            a, b = _sweep(h, l, c, dayi, arr(F, key), side, m, maxpen, once)
            new = (a != 0) & (sd == 0)
            sd[new] = a[new]; st[new] = b[new]
    if swing:      # N-bar swing high/low (excluding this bar): turtle-soup sweep + reclaim, repeats allowed
        hiN = np.roll(_highest(h, swing), 1); loN = np.roll(_lowest(l, swing), 1)
        for lvv, side in ((loN, 1), (hiN, -1)):
            a, b = _sweep(h, l, c, dayi, lvv, side, m, maxpen, False)
            new = (a != 0) & (sd == 0)
            sd[new] = a[new]; st[new] = b[new]
    if rnd:
        pc = np.roll(c, 1)
        lvl_dn = np.floor(pc / rnd) * rnd          # round number below the last close
        lvl_up = np.ceil(pc / rnd) * rnd
        L = (l < lvl_dn - TICK) & (c > lvl_dn) & (lvl_dn - l <= maxpen)
        S = (h > lvl_up + TICK) & (c < lvl_up) & (h - lvl_up <= maxpen)
        nl = L & (sd == 0); ns = S & (sd == 0) & ~L
        sd[nl] = 1; st[nl] = l[nl] - TICK
        sd[ns] = -1; st[ns] = h[ns] + TICK
    tr = _trend(F, trend)
    sd = _apply_trend(sd, tr).astype(np.int64)
    st = np.where(sd != 0, st, NAN)
    if tgt == "vwap":
        tg = np.where(sd != 0, arr(F, "vwap"), NAN)
    else:
        tg = np.full(n, NAN)
    return sd, st, tg, np.full(n, NAN)


# ------------------------------------------------------------------------------------------------ 3. RSI / stretch extremes
def sig_rsi(F, n=2, lo=10, m=3, trend="none", tgt="r", turn=True):
    o, h, l, c = arr(F, "open"), arr(F, "high"), arr(F, "low"), arr(F, "close")
    r = arr(F, f"rsi{n}"); rp = np.roll(r, 1)
    if turn:      # the extreme was the previous bar, this bar turns
        L = (rp < lo) & (c > o) & (c > np.roll(c, 1)); S = (rp > 100 - lo) & (c < o) & (c < np.roll(c, 1))
    else:
        L = r < lo; S = r > 100 - lo
    sd = np.where(L, 1, np.where(S, -1, 0))
    sd = _apply_trend(sd, _trend(F, trend)).astype(np.int64)
    st = np.where(sd == 1, _lowest(l, m) - TICK, np.where(sd == -1, _highest(h, m) + TICK, NAN))
    tg = np.where(sd != 0, arr(F, "ema20"), NAN) if tgt == "ema" else (np.where(sd != 0, arr(F, "vwap"), NAN) if tgt == "vwap" else np.full(len(c), NAN))
    return sd, st, tg, np.full(len(c), NAN)


def sig_stretch(F, k=3.0, ema="ema20", m=3, trend="none", tgt="r"):
    """Close stretched > k ATR from the EMA, then a reversal bar closes back toward it."""
    o, h, l, c = arr(F, "open"), arr(F, "high"), arr(F, "low"), arr(F, "close")
    e, a = arr(F, ema), arr(F, "atr")
    z = (np.roll(c, 1) - np.roll(e, 1)) / np.maximum(np.roll(a, 1), 1e-9)
    L = (z < -k) & (c > o); S = (z > k) & (c < o)
    sd = np.where(L, 1, np.where(S, -1, 0))
    sd = _apply_trend(sd, _trend(F, trend)).astype(np.int64)
    st = np.where(sd == 1, _lowest(l, m) - TICK, np.where(sd == -1, _highest(h, m) + TICK, NAN))
    tg = np.where(sd != 0, e, NAN) if tgt == "ema" else np.full(len(c), NAN)
    return sd, st, tg, np.full(len(c), NAN)


# ------------------------------------------------------------------------------------------------ 4. limit fade at the band
def sig_band_limit(F, k=2.5, anchor="session", stop_sd=1.0, trend="none"):
    """Resting LIMIT at VWAP +/- k sd (placed at the bar close when price is within 1 sd of the band); stop at
    band +/- stop_sd sd; target VWAP. Fills only when price trades through the limit by a tick."""
    c = arr(F, "close")
    vw = arr(F, "vwap" if anchor == "session" else "rvwap"); sd = arr(F, "vsd" if anchor == "session" else "rvsd")
    lo_b, hi_b = vw - k * sd, vw + k * sd
    L = (c < lo_b + sd) & (c > lo_b) & (sd > 0)
    S = (c > hi_b - sd) & (c < hi_b) & (sd > 0) & ~L
    d = np.where(L, 1, np.where(S, -1, 0))
    d = _apply_trend(d, _trend(F, trend)).astype(np.int64)
    lim = np.where(d == 1, np.round(lo_b / TICK) * TICK, np.where(d == -1, np.round(hi_b / TICK) * TICK, NAN))
    st = np.where(d == 1, lim - stop_sd * sd, np.where(d == -1, lim + stop_sd * sd, NAN))
    st = np.round(st / TICK) * TICK
    tg = np.where(d != 0, vw, NAN)
    return d, st, tg, lim


# ------------------------------------------------------------------------------------------------ 5. ES-NQ divergence (SMT)
def sig_smt(F5, N=12, m=3, trend="none", need_close=True):
    """5m: NQ sweeps its N-bar low while ES holds above its own N-bar low (and the NQ bar closes up) -> long; mirror short.
    ES 5m exists from 2025-04 only. Execute on 1m with tools.scalp_mr_lib.map_5m_to_1m."""
    import os
    import pandas as pd
    es = pd.read_csv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "ES_5m.csv"))
    es = es.set_index("time").reindex(F5["time"].values)
    eh, el = es["high"].values, es["low"].values
    o, h, l, c = arr(F5, "open"), arr(F5, "high"), arr(F5, "low"), arr(F5, "close")
    nqlo = np.roll(_lowest(l, N), 1); nqhi = np.roll(_highest(h, N), 1)
    eslo = np.roll(_lowest(el, N), 1); eshi = np.roll(_highest(eh, N), 1)
    L = (l < nqlo) & (el > eslo)
    S = (h > nqhi) & (eh < eshi)
    if need_close:
        L &= c > o; S &= c < o
    sd = np.where(L, 1, np.where(S & ~L, -1, 0))
    sd = np.where(np.isnan(el) | np.isnan(eslo), 0, sd)
    sd = _apply_trend(sd, _trend(F5, trend)).astype(np.int64)
    st = np.where(sd == 1, _lowest(l, m) - TICK, np.where(sd == -1, _highest(h, m) + TICK, NAN))
    return sd, st, np.full(len(c), NAN), np.full(len(c), NAN)
