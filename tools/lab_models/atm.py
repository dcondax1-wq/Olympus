"""ATM track: the owner's own ATM model (NQ, ES for SMT). Timeframe-parametric; the main test is 5m.

Rules (exact mechanical definitions in research/lab/ATM_RULES.md):
  1. ATM range = highest high / lowest low of the bars opening 07:00 .. 09:25 ET (the 09:25 bar is the last one, so the
     range is final at 09:30).
  2. From the 09:30 bar on, a sweep = a bar trading >= 1 tick beyond the ATM low (-> long setup) or high (-> short).
     Once one side is swept the other side is the draw; a setup dies when its target side has been traded through.
  3. Strong V + IFVG (long; shorts mirror):
     - extreme e = lowest low since the sweep (every lower low moves it and restarts the clock)
     - sweep leg = last confirmed swing high (fractal, k=2) before e, down to e
     - V: within N bars of e (5m N=6) a close back inside the range (> ATM low) that has retraced >= X (50%) of the leg,
       with a bullish displacement candle (body >= 1 x ATR14 or body >= 60% of its range) between e and that close
     - IFVG: a bearish FVG created by the leg (c1 at/after the leg origin, c3 at/before e, not closed through before e)
       that a bar from e on closes above
     - entry = close of the first bar <= e+N where the V and the IFVG are both done and the close is inside the range
  4. Confluences (logged; they only feed the sizing score): 1H trend, SMT, NQ>ES relative strength, open location,
     IFVG size, V speed, LRLR path, target = EQH/EQL or session level.
  5. Stop = e -/+ max(2 ticks, 0.1 x ATR14). Target = the opposite ATM side (limit 1 tick inside it, filled only when
     price reaches the level). Skip if the opposite side is < 1.5R away. Variants: first clear pool / half there + runner.
  6. Flat 15:55 ET, 1 trade a day, entries 09:30-11:30 ET (signal bar closes by 11:30).
  Sizing: confidence score = number of the 8 confluences present; A >= 5 (1 NQ = 10 MNQ if the stop costs <= $700,
  else $700 in micros), B 3-4 ($350 in micros), C <= 2 ($175 in micros, min 1). Never risk past the $1,000 soft DLL.

Causal: decisions on closed bars only; HTF (15m/1H) bars count once their clock period has closed; the position is
managed from the bar after entry; same-bar stop/target -> stop first; break-even (partial variant) applies from the bar
after TP1 fills. Entries never depend on the size, so every sizing scheme trades exactly the same entries.
"""
from __future__ import annotations

import collections
import math
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
from tools.strategy_lab import COMMISSION_RT, PV, SLIP_PTS, make_trade, size  # noqa: E402

NAME = "atm"
TICK = 0.25
CONF_KEYS = ["trend_1h_with", "smt", "nq_rs_with", "open_loc_with", "ifvg_big", "v_fast", "lrlr", "tgt_pool"]

PARAMS = {
    "sym": "NQ",
    "tf": 5,                      # minutes per bar of the frame passed in (5 = main test; 1m/3m need a TradingView 1m export)
    "range": [420, 570],          # ATM range = bars opening 07:00 .. 09:25 ET ([start, end) in bar-open ET minutes)
    "open_mod": 570,              # sweeps count from the bar opening 09:30
    "entry_end": 690,             # entry bars must open before 11:30 (signal close <= 11:30)
    "sweep_ticks": 1,
    "v_bars": 6,                  # N: the V must complete within N bars of the extreme (5m: 6 = 30 min)
    "v_retrace": 0.5,             # X: close retraces >= X of the sweep leg
    "disp_atr": 1.0,              # displacement: body >= 1.0 x ATR14 ...
    "disp_body_frac": 0.6,        # ... or body >= 60% of the candle range (owner's OR)
    "swing_k": 2,                 # fractal strength for the leg origin, pools and path resistance
    "leg_lookback": 48,           # bars searched back for the leg origin (5m: 4 h)
    "min_fvg_ticks": 1,
    "stop_buf_ticks": 2,
    "stop_buf_atr": 0.1,
    "target": "opp",              # opp (a) | first_clear (b) | partial (c)
    "tp_min_r": 1.0,              # (b)/(c): the first clear pool must be >= this many R from entry
    "min_rr": 1.5,                # skip if the opposite ATM side is closer than this many R
    "be_after_partial": True,     # (c): stop to entry after the partial fills
    "max_trades_day": 1,
    "flat_mod": 955,              # flat at 15:55 ET
    "sizing": "flat",             # flat ($350; the default since the tiers failed the rank test on 5m and 1m) | tier (owner)
    "risk_usd": 350.0,
    "tier_risk": {"A": 700.0, "B": 350.0, "C": 175.0},
    "tier_a_qty": 10,             # 1 NQ = 10 MNQ-equivalent
    "tier_cut": [5, 3],           # score >= 5 -> A, >= 3 -> B, else C (fixed before any result was seen)
    "ifvg_big_atr": 0.25,         # confluence: inverted FVG >= 0.25 x ATR14
    "v_fast_bars": 2,             # confluence: close back inside the range within 2 bars of the extreme
    "dll_usd": 1000.0,            # MFFU soft daily loss limit: never let day loss + new risk exceed it
    "skip_news": False,           # optional: no entries on CPI / NFP / FOMC days
    "long": True, "short": True,
}


# ------------------------------------------------------------------------------------------------ helpers
def _arrays(df):
    return (df["open"].to_numpy(float), df["high"].to_numpy(float), df["low"].to_numpy(float),
            df["close"].to_numpy(float), df["time"].to_numpy(np.int64), df["mod"].to_numpy(int), df["day"].to_numpy())


def _day_bounds(day):
    cut = np.flatnonzero(day[1:] != day[:-1]) + 1
    starts = np.r_[0, cut]
    ends = np.r_[cut, len(day)]
    return list(zip(day[starts], starts, ends))


def _atr(h, l, c, n=14):
    pc = np.r_[c[0], c[:-1]]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    return pd.Series(tr).ewm(alpha=1.0 / n, adjust=False).mean().to_numpy()


def _pivots(h, l, k):
    """Fractal swings: high[p] > the k highs before and >= the k highs after (lows mirror). Usable at the close of p+k."""
    sh = np.ones(len(h), bool)
    sl = np.ones(len(h), bool)
    for j in range(1, k + 1):
        sh &= (h > np.r_[np.full(j, np.inf), h[:-j]]) & (h >= np.r_[h[j:], np.full(j, np.inf)])
        sl &= (l < np.r_[np.full(j, -np.inf), l[:-j]]) & (l <= np.r_[l[j:], np.full(j, -np.inf)])
    return sh, sl


class _HTF:
    """Clock-aligned bars (15m / 1H) from the base frame; 3-candle swings and a BOS trend known at each bar's close."""

    def __init__(self, t, h, l, c, span):
        self.span = span
        key = t // span
        cut = np.flatnonzero(key[1:] != key[:-1]) + 1
        s, e = np.r_[0, cut], np.r_[cut, len(t)]
        self.t0 = key[s] * span
        self.close_t = self.t0 + span
        H, L, C = np.maximum.reduceat(h, s), np.minimum.reduceat(l, s), c[e - 1]
        self.h, self.l, self.c = H, L, C
        n = len(s)
        self.trend = np.zeros(n, np.int8)
        sh = sl = None
        shb = slb = True
        tr = 0
        for m in range(n):
            if m >= 2:
                if H[m - 1] > H[m - 2] and H[m - 1] > H[m]:
                    sh, shb = H[m - 1], False
                if L[m - 1] < L[m - 2] and L[m - 1] < L[m]:
                    sl, slb = L[m - 1], False
            if sh is not None and not shb and C[m] > sh:
                tr, shb = 1, True
            if sl is not None and not slb and C[m] < sl:
                tr, slb = -1, True
            self.trend[m] = tr

    def last(self, t_dec):
        """Index of the last HTF bar whose clock period has closed by t_dec (-1 if none)."""
        return int(np.searchsorted(self.close_t, t_dec, side="right")) - 1

    def fvgs(self):
        """Opposing gaps as near edges in direction space: {1: bottoms of bearish FVGs (resistance for longs),
        -1: -(tops of bullish FVGs) (resistance for shorts)}, each with the time the gap is known (close of c3)."""
        H, L, t0, sp = self.h, self.l, self.t0, self.span
        ok = np.r_[False, False, (t0[2:] - t0[1:-1] == sp) & (t0[1:-1] - t0[:-2] == sp)]
        bear = np.r_[False, False, H[2:] < L[:-2]] & ok
        bull = np.r_[False, False, L[2:] > H[:-2]] & ok
        return {1: (H[bear], self.close_t[bear]), -1: (-L[bull], self.close_t[bull])}


class _Es:
    """Partner index (ES) per trading day: its own ATM range and RTH open, for SMT and relative strength."""

    def __init__(self, es, p):
        o, h, l, c, t, mod, day = _arrays(es)
        self.t, self.h, self.l, self.c = t, h, l, c
        r0, r1 = p["range"]
        self.days = {}
        for dl, a, b in _day_bounds(day):
            seg = mod[a:b]
            rm = np.flatnonzero((seg >= r0) & (seg < r1)) + a
            io = np.flatnonzero((seg >= p["open_mod"]) & (seg < 1080)) + a
            if len(rm) and len(io):
                self.days[dl] = (float(h[rm].max()), float(l[rm].min()), int(io[0]), float(o[io[0]]), int(b))

    def at(self, dl, d, t_bar):
        """(smt, es_return_since_open) using ES bars opening at or before t_bar (the NQ signal bar)."""
        x = self.days.get(dl)
        if x is None:
            return None, None
        eh, el, i0, op, b = x
        j = int(np.searchsorted(self.t, t_bar, side="right")) - 1
        if j < i0 or j >= b:
            return None, None
        if d == 1:
            smt = bool(self.l[i0:j + 1].min() > el - TICK)      # ES did not take its own ATM low
        else:
            smt = bool(self.h[i0:j + 1].max() < eh + TICK)      # ES did not take its own ATM high
        return smt, float(self.c[j] / op - 1.0)


_NEWS = None


def _news_days():
    """Trading dates with a high-impact CPI, NFP or FOMC release (data/news/events.csv)."""
    global _NEWS
    if _NEWS is None:
        _NEWS = {}
        try:
            df = pd.read_csv(os.path.join(ROOT, "data", "news", "events.csv"))
            for r in df.itertuples():
                ev = str(r.event).upper()
                if str(r.impact).lower() == "high" and ("CPI" in ev or "NON-FARM" in ev or "FOMC" in ev):
                    _NEWS.setdefault(str(r.date), []).append(str(r.event))
        except Exception:
            pass
    return _NEWS


# ------------------------------------------------------------------------------------------------ the model
def run_raw(bars, params=None, es=None, _funnel=None):
    """Causal simulation. Returns raw setups (entries, both exit paths, confluences, tier) before sizing."""
    p = {**PARAMS, **(params or {})}
    sym = p["sym"]
    o, h, l, c, t, mod, day = _arrays(bars)
    n = len(c)
    tf = int(p["tf"])
    tfs = 60 * tf
    atr = _atr(h, l, c)
    k = int(p["swing_k"])
    psh, psl = _pivots(h, l, k)
    h1 = _HTF(t, h, l, c, 3600)
    f15 = _HTF(t, h, l, c, 900).fvgs()
    bounds = _day_bounds(day)
    esx = _Es(es, p) if (es is not None and len(es)) else None
    news = _news_days()
    r0, r1 = p["range"]
    sweep = p["sweep_ticks"] * TICK
    N = int(p["v_bars"])
    X = float(p["v_retrace"])
    min_fvg = p["min_fvg_ticks"] * TICK
    flat_bar = p["flat_mod"] - tf
    dirs = [d for d, ok in ((1, p["long"]), (-1, p["short"])) if ok]
    # direction space: longs as-is, shorts mirrored (x -> -x, high <-> low); piv = swing highs in that space
    MIR = {1: (o, h, l, c, psh), -1: (-o, -l, -h, -c, psl)}
    drange = np.array([h[a_:b_].max() - l[a_:b_].min() for _, a_, b_ in bounds])
    fun = _funnel if _funnel is not None else collections.Counter()
    raws = []

    why = {}

    def signal(d, e, i, lvl_m):
        """V + IFVG check at the close of bar i for the extreme at bar e (direction space). None if not (yet) there;
        the failed check is left in why['r'] (funnel diagnostics only)."""
        O, H, L, C, piv = MIR[d]
        why["r"] = "leg"
        ext = L[e]
        lo = max(0, e - int(p["leg_lookback"]))
        cand = np.flatnonzero(piv[lo:e]) + lo
        cand = cand[cand + k <= i]                         # the swing must be confirmed by now
        if len(cand):
            org = int(cand[-1])
        elif e > lo:
            org = lo + int(np.argmax(H[lo:e]))
        else:
            return None
        leg = H[org] - ext
        if leg <= 0:
            return None
        thr = ext + X * leg
        disp = False
        v_bar = rec_bar = None
        for jj in range(e, i + 1):
            body = C[jj] - O[jj]
            if body > 0:
                rng = H[jj] - L[jj]
                if body >= p["disp_atr"] * atr[jj] or (rng > 0 and body >= p["disp_body_frac"] * rng):
                    disp = True
            if C[jj] > lvl_m:
                if rec_bar is None:
                    rec_bar = jj
                if v_bar is None and disp and C[jj] >= thr:
                    v_bar = jj
        if v_bar is None or C[i] <= lvl_m:
            why["r"] = "no_reclaim" if rec_bar is None else ("no_disp" if not disp else
                                                             ("no_retrace" if v_bar is None else "fell_back"))
            return None
        why["r"] = "no_ifvg"
        inv_bar, best = None, None
        for k3 in range(org + 2, e + 1):                   # c1 = k3-2 >= org, c3 = k3 <= e
            top, bot = L[k3 - 2], H[k3]                    # gap against the reversal (bearish FVG for a long)
            if top - bot < min_fvg - 1e-9:
                continue
            if k3 + 1 < e and C[k3 + 1:e].max() > top:     # already closed through inside the leg -> not this leg's
                continue
            j0 = max(e, k3 + 1)
            if j0 > i:
                continue
            hit = np.flatnonzero(C[j0:i + 1] > top)
            if not len(hit):
                continue
            jb = j0 + int(hit[0])
            if inv_bar is None or jb < inv_bar:
                inv_bar = jb
            if best is None or top - bot > best[0]:
                best = (top - bot, top, bot, k3, jb)
        if inv_bar is None:
            return None
        return {"e": e, "org": org, "leg": float(leg), "v_bar": v_bar, "rec_bar": rec_bar, "inv_bar": inv_bar,
                "ifvg_size": float(best[0]), "ifvg_c3": int(best[3])}

    def untaken(d, pm, j0, i0):
        H = MIR[d][1]
        return j0 > i0 or H[j0:i0 + 1].max() < pm + TICK

    def eq_pools(d, i0, a_day):
        """Relative equal highs (direction space) from swings confirmed by i0: [(level, pb)]."""
        O, H, L, C, piv = MIR[d]
        ps = np.flatnonzero(piv[a_day:max(a_day, i0 - k + 1)]) + a_day
        out = []
        for x in range(len(ps)):
            for y in range(x + 1, len(ps)):
                pa, pb = ps[x], ps[y]
                if pb - pa < 3:
                    continue
                tol = max(2 * TICK, 0.1 * atr[pb])
                if abs(H[pa] - H[pb]) > tol or L[pa:pb + 1].min() > min(H[pa], H[pb]) - atr[pb]:
                    continue
                out.append((float(max(H[pa], H[pb])), int(pb)))
        return out

    def n_res(d, i0, em, pm, a_day, prev_t, t_dec, tol):
        """Path resistance between entry em and level pm (direction space): fresh swing highs of today plus live
        opposing 15m FVGs (last 2 days) in the corridor, each price zone counted once."""
        O, H, L, C, piv = MIR[d]
        zones = []
        ps = np.flatnonzero(piv[a_day:max(a_day, i0 - k + 1)]) + a_day
        for q in ps:
            v = H[q]
            if em < v < pm - tol and (q + 1 > i0 or H[q + 1:i0 + 1].max() < v + TICK):
                zones.append(float(v))
        vals, kt = f15[d]
        sel = (kt >= prev_t) & (kt <= t_dec)
        for v, ktt in zip(vals[sel], kt[sel]):
            if not (em < v < pm - tol):
                continue
            j0 = int(np.searchsorted(t, ktt))
            if j0 <= i0 and H[j0:i0 + 1].max() >= v:      # tapped -> no longer live
                continue
            zones.append(float(v))
        zones.sort()
        cnt, last = 0, None
        for v in zones:
            if last is None or v - last > tol:
                cnt += 1
            last = v
        return cnt

    def sim(i0, d, b_, entry, stop, tl, tpx, t1l=None, t1px=None, be=False):
        """Bar-by-bar exit path from the bar after entry: stop first, then TP1, then the target, then 15:55."""
        ed, sd, tld = entry * d, stop * d, tl * d
        t1ld = None if t1l is None else t1l * d
        tp1, mae, moved = None, 0.0, False
        for i in range(i0 + 1, b_):
            if d == 1:
                hi, lo, op = h[i], l[i], o[i]
            else:
                hi, lo, op = -l[i], -h[i], -o[i]
            mi = mod[i]
            if lo <= sd:
                px = min(op, sd)
                mae = max(mae, ed - px)
                return {"exit_i": i, "exit_t": int(t[i]) + tfs, "exit_px": float(px * d),
                        "kind": "be" if moved else "stop", "tp1": tp1, "mae": float(mae)}
            mae = max(mae, ed - lo)
            if t1ld is not None and tp1 is None and hi >= t1ld:
                tp1 = (int(t[i]) + tfs, float(t1px))
            if hi >= tld:
                return {"exit_i": i, "exit_t": int(t[i]) + tfs, "exit_px": float(tpx), "kind": "target", "tp1": tp1,
                        "mae": float(mae)}
            is_flat = flat_bar <= mi < 1080
            if is_flat or i == b_ - 1:
                kind = "open" if (i == n - 1 and not is_flat) else "time"
                return {"exit_i": i, "exit_t": int(t[i]) + tfs, "exit_px": float(c[i]), "kind": kind, "tp1": tp1,
                        "mae": float(mae)}
            if be and tp1 is not None and not moved:
                sd, moved = max(sd, ed), True
        return {"exit_i": i0, "exit_t": int(t[i0]) + tfs, "exit_px": float(c[i0]), "kind": "open" if i0 == n - 1 else "time",
                "tp1": None, "mae": 0.0}

    for nday in range(1, len(bounds)):
        dlabel, a, b = bounds[nday]
        _, a0, b0 = bounds[nday - 1]
        fun["days"] += 1
        seg = mod[a:b]
        ridx = np.flatnonzero((seg >= r0) & (seg < r1)) + a
        oidx = np.flatnonzero((seg >= p["open_mod"]) & (seg < 1080)) + a
        if len(ridx) < max(2, (r1 - r0) // tf // 2) or not len(oidx):
            continue
        iopen = int(oidx[0])
        if mod[iopen] >= p["entry_end"]:
            continue
        RH, RL = float(h[ridx].max()), float(l[ridx].min())
        if RH <= RL:
            continue
        fun["days_ok"] += 1
        news_ev = news.get(dlabel, [])
        if p["skip_news"] and news_ev:
            continue
        # session levels (all final before 09:30)
        pseg = mod[a0:b0]
        prth = np.flatnonzero((pseg >= 570) & (pseg < 960)) + a0
        statics = [("PDH", 1, float(h[a0:b0].max()), int(t[a])), ("PDL", -1, float(l[a0:b0].min()), int(t[a]))]
        if len(prth):
            statics += [("PRH", 1, float(h[prth].max()), int(t[a])), ("PRL", -1, float(l[prth].min()), int(t[a]))]
        for nm, (s0, s1) in (("AS", (1200, 1440)), ("LO", (120, 300))):
            ix = np.flatnonzero((seg >= s0) & (seg < s1)) + a
            if len(ix):
                av = int(t[ix[-1]]) + tfs
                statics += [(nm + "H", 1, float(h[ix].max()), av), (nm + "L", -1, float(l[ix].min()), av)]
        on = [("ONH", 1, float(h[a:iopen].max()), int(t[iopen])), ("ONL", -1, float(l[a:iopen].min()), int(t[iopen]))] \
            if iopen > a else []
        prc = float(c[prth[-1]]) if len(prth) else None
        adr = float(drange[max(0, nday - 10):nday].mean())
        gap_big = None if prc is None else bool(abs(o[iopen] - prc) >= 0.25 * adr)
        prev_t = int(t[a0])

        setups = {1: None, -1: None}
        killed = {1: False, -1: False}
        swept_any = False
        ntr = 0
        i = iopen
        while i < b:
            mi = mod[i]
            if mi >= p["entry_end"] or mi >= 1080 or ntr >= p["max_trades_day"]:
                break
            low_hit, high_hit = l[i] <= RL - sweep, h[i] >= RH + sweep
            if high_hit:
                killed[1] = True                           # the long's draw (ATM high) is gone
            if low_hit:
                killed[-1] = True
            if (low_hit or high_hit) and not swept_any:
                swept_any = True
                fun["days_swept"] += 1
            entered = None
            for d in dirs:
                if killed[d]:
                    setups[d] = None
                    continue
                L = MIR[d][2]
                lvl_m = RL if d == 1 else -RH
                s = setups[d]
                if s is None:
                    if not (low_hit if d == 1 else high_hit):
                        continue
                    s = setups[d] = {"sweep_i": i, "e": i, "dead": False}
                    fun["armed"] += 1
                elif L[i] < L[s["e"]]:
                    s["e"], s["dead"] = i, False
                if s["dead"]:
                    continue
                e = s["e"]
                if i - e > N:
                    s["dead"] = True
                    fun["v_expired"] += 1
                    continue
                sig = signal(d, e, i, lvl_m)
                if sig is not None:
                    entered = (d, sig)
                    break
                if i - e == N:
                    fun["fail_" + why.get("r", "?")] += 1
            if entered is None:
                i += 1
                continue
            d, sig = entered
            fun["signals"] += 1
            setups[d]["dead"] = True                       # consumed; only a new extreme re-arms it
            e = sig["e"]
            entry = float(c[i])
            buf = max(p["stop_buf_ticks"] * TICK, p["stop_buf_atr"] * float(atr[i]))
            stop = (float(l[e]) - buf) if d == 1 else (float(h[e]) + buf)
            R = (entry - stop) * d
            tgt_lvl = RH if d == 1 else RL
            dist = (tgt_lvl - entry) * d
            if R <= 0 or dist < p["min_rr"] * R:
                fun["skip_rr"] += 1
                i += 1
                continue
            if size(R + SLIP_PTS, p["risk_usd"], sym) < 1:
                fun["skip_size"] += 1
                i += 1
                continue
            t_dec = int(t[i]) + tfs
            em, tm = entry * d, tgt_lvl * d
            tol = max(2 * TICK, 0.1 * float(atr[i]))
            # ---- confluences (all known at the signal close)
            q = h1.last(t_dec)
            smt, es_ret = esx.at(dlabel, d, int(t[i])) if esx is not None else (None, None)
            nq_ret = float(c[i] / o[iopen] - 1.0)
            nres = n_res(d, i, em, tm, a, prev_t, t_dec, tol)
            tgt_pool = None
            for nm, side, px, av in statics + on:
                if side == d and av <= t_dec and abs(px * d - tm) <= tol:
                    tgt_pool = nm
                    break
            if tgt_pool is None:
                Hd = MIR[d][1]
                piv = MIR[d][4]
                ps = [int(x) + a for x in np.flatnonzero(piv[a:max(a, i - k + 1)]) if abs(Hd[int(x) + a] - tm) <= tol]
                Ld = MIR[d][2]
                for x in range(len(ps)):
                    for y in range(x + 1, len(ps)):
                        if ps[y] - ps[x] >= 3 and Ld[ps[x]:ps[y] + 1].min() <= min(Hd[ps[x]], Hd[ps[y]]) - atr[ps[y]]:
                            tgt_pool = "EQ"
                            break
                    if tgt_pool:
                        break
            conf = {
                "trend_1h_with": bool(q >= 0 and h1.trend[q] == d),
                "smt": smt,
                "nq_rs_with": None if es_ret is None else bool((nq_ret - es_ret) * d > 0),
                "open_loc_with": bool((o[iopen] - (RH + RL) / 2) * d < 0),
                "ifvg_big": bool(sig["ifvg_size"] >= p["ifvg_big_atr"] * atr[i]),
                "v_fast": bool(sig["rec_bar"] - e <= p["v_fast_bars"]),
                "lrlr": bool(nres <= 1),
                "tgt_pool": tgt_pool is not None,
            }
            score = int(sum(1 for kk in CONF_KEYS if conf.get(kk)))
            cut = p["tier_cut"]
            tier = "A" if score >= cut[0] else ("B" if score >= cut[1] else "C")
            # ---- first clear pool before the opposite side (variants b / c)
            first = None
            if p["target"] in ("first_clear", "partial"):
                cands = []
                for nm, side, px, av in statics:
                    pm = px * d
                    if side == d and av <= t_dec and em + p["tp_min_r"] * R <= pm < tm - tol and \
                            untaken(d, pm, int(np.searchsorted(t, av)), i):
                        cands.append((pm, nm))
                for pm, pb in eq_pools(d, i, a):
                    if em + p["tp_min_r"] * R <= pm < tm - tol and untaken(d, pm, pb + 1, i):
                        cands.append((pm, "EQ"))
                for pm, nm in sorted(cands):
                    if n_res(d, i, em, pm, a, prev_t, t_dec, tol) <= 1:
                        first = (float(pm * d), nm)
                        break
            # ---- exit paths
            full = sim(i, d, b, entry, stop, tgt_lvl, tgt_lvl - d * TICK)
            pp = None
            if p["target"] == "first_clear" and first is not None:
                full = sim(i, d, b, entry, stop, first[0], first[0] - d * TICK)
            elif p["target"] == "partial" and first is not None:
                pp = sim(i, d, b, entry, stop, tgt_lvl, tgt_lvl - d * TICK, first[0], first[0] - d * TICK,
                         p["be_after_partial"])
            fun["trades"] += 1
            raws.append({
                "day": dlabel, "entry_t": t_dec, "d": d, "entry": entry, "stop": float(stop), "risk_pts": float(R),
                "tgt_lvl": float(tgt_lvl), "rr_opp": float(dist / R), "first": first, "full": full, "pp": pp,
                "partial": p["target"] == "partial", "conf": conf, "score": score, "tier": tier,
                "setup": "ATM:" + ("low-sweep long" if d == 1 else "high-sweep short"),
                "info": {"atm_h": RH, "atm_l": RL, "leg_pts": round(sig["leg"], 2), "ifvg_pts": round(sig["ifvg_size"], 2),
                         "bars_to_reclaim": int(sig["rec_bar"] - e), "bars_to_v": int(sig["v_bar"] - e),
                         "bars_to_entry": int(i - e), "n_res": int(nres), "tgt_pool": tgt_pool,
                         "atr": round(float(atr[i]), 2), "news": news_ev, "gap_big": gap_big, "tf": tf,
                         "nq_ret": round(nq_ret * 100, 3), "es_ret": None if es_ret is None else round(es_ret * 100, 3)},
            })
            ntr += 1
            ex = (pp or full)["exit_i"]
            if ex > i:
                if h[i + 1:ex + 1].max() >= RH + sweep:
                    killed[1] = True
                if l[i + 1:ex + 1].min() <= RL - sweep:
                    killed[-1] = True
            setups = {1: None, -1: None}
            i = max(ex, i) + 1
    return raws


# ------------------------------------------------------------------------------------------------ 1m / multi-frame version
MTF_PARAMS = {
    "ladder": [5, 3, 1],          # frames checked at every 1m close, highest first ("highest timeframe IFVG we find")
    "v_minutes": 30,              # V must complete within 30 min of the extreme on the trigger frame (N = 30 / tf bars)
    "v_bars_fixed": None,         # variant: N = this many bars of the trigger frame, whatever the frame
    "leg_minutes": 240,           # leg-origin search window
    "v_fast_minutes": 10,         # confluence: first 1m close back inside the range within 10 min of the extreme
}


def _resample(t, o, h, l, c, day, tf_min):
    """Clock-aligned tf-minute bars from 1m bars: (t0, o, h, l, c, day, bucket index of every 1m bar)."""
    span = 60 * tf_min
    key = t // span
    cut = np.flatnonzero(key[1:] != key[:-1]) + 1
    s, e = np.r_[0, cut], np.r_[cut, len(t)]
    bmap = np.repeat(np.arange(len(s)), e - s)
    return key[s] * span, o[s], np.maximum.reduceat(h, s), np.minimum.reduceat(l, s), c[e - 1], day[s], bmap


class _Frame:
    """One timeframe built from 1m bars: OHLC, ATR14, k-fractal swings, direction-space views, first bar of each day."""

    def __init__(self, t0, o, h, l, c, day, tf_min, k, bmap):
        self.tf, self.k, self.bmap = tf_min, k, bmap
        self.t0, self.o, self.h, self.l, self.c, self.day = t0, o, h, l, c, day
        self.close_t = t0 + 60 * tf_min
        self.atr = _atr(h, l, c)
        self.psh, self.psl = _pivots(h, l, k)
        self.MIR = {1: (o, h, l, c, self.psh), -1: (-o, -l, -h, -c, self.psl)}
        u, first = np.unique(day, return_index=True)
        self.day_start = {str(x): int(y) for x, y in zip(u, first)}

    def last_closed(self, j1, T):
        """Latest bar of this frame closed by time T (= the close of 1m bar j1). Forming bars are never returned."""
        m = int(self.bmap[j1])
        return m if self.close_t[m] <= T else m - 1


def _frame_signal(F, d, e, i, lvl_m, p, lookback):
    """R3-R5 on frame F (direction space): V + IFVG at the close of bar i for the extreme in bar e, or None."""
    O, H, L, C, piv = F.MIR[d]
    atr, k = F.atr, F.k
    lo = max(0, e - lookback)
    cand = np.flatnonzero(piv[lo:e]) + lo
    cand = cand[cand + k <= i]
    if len(cand):
        org = int(cand[-1])
    elif e > lo:
        org = lo + int(np.argmax(H[lo:e]))
    else:
        return None
    ext = L[e]
    leg = H[org] - ext
    if leg <= 0:
        return None
    thr = ext + p["v_retrace"] * leg
    disp = False
    v_bar = rec_bar = None
    for jj in range(e, i + 1):
        body = C[jj] - O[jj]
        if body > 0:
            rng = H[jj] - L[jj]
            if body >= p["disp_atr"] * atr[jj] or (rng > 0 and body >= p["disp_body_frac"] * rng):
                disp = True
        if C[jj] > lvl_m:
            if rec_bar is None:
                rec_bar = jj
            if v_bar is None and disp and C[jj] >= thr:
                v_bar = jj
    if v_bar is None or C[i] <= lvl_m:
        return None
    ks = np.arange(org + 2, e + 1)
    if not len(ks):
        return None
    top, bot = L[ks - 2], H[ks]
    ok = np.flatnonzero((top - bot) >= p["min_fvg_ticks"] * TICK - 1e-9)
    if not len(ok):
        return None
    seg = C[org:e]
    sm = np.r_[np.maximum.accumulate(seg[::-1])[::-1], -np.inf] if len(seg) else np.array([-np.inf])   # max(C[x:e])
    inv_bar, best = None, None
    for ix in ok:
        k3, tp, bt = int(ks[ix]), float(top[ix]), float(bot[ix])
        q = k3 + 1 - org
        if q < len(sm) and sm[q] > tp:                     # closed through inside the leg already
            continue
        j0 = max(e, k3 + 1)
        if j0 > i:
            continue
        hit = np.flatnonzero(C[j0:i + 1] > tp)
        if not len(hit):
            continue
        jb = j0 + int(hit[0])
        if inv_bar is None or jb < inv_bar:
            inv_bar = jb
        if best is None or tp - bt > best[0]:
            best = (tp - bt, tp, bt, k3, jb)
    if inv_bar is None:
        return None
    return {"e": e, "org": org, "leg": float(leg), "v_bar": v_bar, "rec_bar": rec_bar, "inv_bar": inv_bar,
            "ifvg_size": float(best[0]), "ifvg_top_m": best[1], "ifvg_bot_m": best[2], "ifvg_c3": int(best[3])}


def _frame_eq_pools(F, d, i0, a_day):
    O, H, L, C, piv = F.MIR[d]
    ps = np.flatnonzero(piv[a_day:max(a_day, i0 - F.k + 1)]) + a_day
    out = []
    for x in range(len(ps)):
        for y in range(x + 1, len(ps)):
            pa, pb = ps[x], ps[y]
            if pb - pa < 3:
                continue
            tol = max(2 * TICK, 0.1 * F.atr[pb])
            if abs(H[pa] - H[pb]) > tol or L[pa:pb + 1].min() > min(H[pa], H[pb]) - F.atr[pb]:
                continue
            out.append((float(max(H[pa], H[pb])), int(pb)))
    return out


def _frame_n_res(F, d, i0, em, pm, a_day, prev_t, t_dec, tol, f15):
    """DOL-6 path resistance on frame F (5m in practice) + live opposing 15m gaps, as in the 5m version."""
    O, H, L, C, piv = F.MIR[d]
    zones = []
    for q in np.flatnonzero(piv[a_day:max(a_day, i0 - F.k + 1)]) + a_day:
        v = H[q]
        if em < v < pm - tol and (q + 1 > i0 or H[q + 1:i0 + 1].max() < v + TICK):
            zones.append(float(v))
    vals, kt = f15[d]
    sel = (kt >= prev_t) & (kt <= t_dec)
    for v, ktt in zip(vals[sel], kt[sel]):
        if not (em < v < pm - tol):
            continue
        j0 = int(np.searchsorted(F.t0, ktt))
        if j0 <= i0 and H[j0:i0 + 1].max() >= v:
            continue
        zones.append(float(v))
    zones.sort()
    cnt, last = 0, None
    for v in zones:
        if last is None or v - last > tol:
            cnt += 1
        last = v
    return cnt


def run_raw_mtf(bars1, params=None, es5=None, _funnel=None):
    """1m engine with the owner's timeframe ladder (section G of ATM_RULES.md). bars1 = 1m bars (strategy_lab format),
    es5 = ES 5m bars. Returns raw setups in the same format as run_raw (so build_all sizes them the same way)."""
    p = {**PARAMS, **MTF_PARAMS, **(params or {})}
    p["tf"] = 1
    sym = p["sym"]
    o, h, l, c, t, mod, day = _arrays(bars1)
    n = len(c)
    k = int(p["swing_k"])
    ladder = sorted({int(x) for x in p["ladder"]}, reverse=True)
    frames = {}
    for tf in set(ladder) | {5}:
        if tf == 1:
            frames[1] = _Frame(t, o, h, l, c, day, 1, k, np.arange(n))
        else:
            t0_, o_, h_, l_, c_, d_, bm = _resample(t, o, h, l, c, day, tf)
            frames[tf] = _Frame(t0_, o_, h_, l_, c_, d_, tf, k, bm)
    F5 = frames[5]
    h1 = _HTF(t, h, l, c, 3600)
    f15 = _HTF(t, h, l, c, 900).fvgs()
    bounds = _day_bounds(day)
    esx = _Es(es5, p) if (es5 is not None and len(es5)) else None
    news = _news_days()
    r0, r1 = p["range"]
    sweep = p["sweep_ticks"] * TICK
    flat_bar = p["flat_mod"] - 1
    dirs = [d for d, ok in ((1, p["long"]), (-1, p["short"])) if ok]
    MIR1 = {1: (o, h, l, c), -1: (-o, -l, -h, -c)}
    drange = np.array([h[a_:b_].max() - l[a_:b_].min() for _, a_, b_ in bounds])
    fun = _funnel if _funnel is not None else collections.Counter()
    raws = []

    def nwin(tf):
        return int(p["v_bars_fixed"]) if p.get("v_bars_fixed") else max(1, int(p["v_minutes"]) // tf)

    def sim(i0, d, b_, entry, stop, tl, tpx, t1l=None, t1px=None, be=False):
        ed, sd, tld = entry * d, stop * d, tl * d
        t1ld = None if t1l is None else t1l * d
        tp1, mae, moved = None, 0.0, False
        for i in range(i0 + 1, b_):
            if d == 1:
                hi, lo, op = h[i], l[i], o[i]
            else:
                hi, lo, op = -l[i], -h[i], -o[i]
            mi = mod[i]
            if lo <= sd:
                px = min(op, sd)
                mae = max(mae, ed - px)
                return {"exit_i": i, "exit_t": int(t[i]) + 60, "exit_px": float(px * d), "kind": "be" if moved else "stop",
                        "tp1": tp1, "mae": float(mae)}
            mae = max(mae, ed - lo)
            if t1ld is not None and tp1 is None and hi >= t1ld:
                tp1 = (int(t[i]) + 60, float(t1px))
            if hi >= tld:
                return {"exit_i": i, "exit_t": int(t[i]) + 60, "exit_px": float(tpx), "kind": "target", "tp1": tp1,
                        "mae": float(mae)}
            is_flat = flat_bar <= mi < 1080
            if is_flat or i == b_ - 1:
                kind = "open" if (i == n - 1 and not is_flat) else "time"
                return {"exit_i": i, "exit_t": int(t[i]) + 60, "exit_px": float(c[i]), "kind": kind, "tp1": tp1,
                        "mae": float(mae)}
            if be and tp1 is not None and not moved:
                sd, moved = max(sd, ed), True
        return {"exit_i": i0, "exit_t": int(t[i0]) + 60, "exit_px": float(c[i0]), "kind": "open" if i0 == n - 1 else "time",
                "tp1": None, "mae": 0.0}

    for nday in range(1, len(bounds)):
        dlabel, a, b = bounds[nday]
        plabel, a0, b0 = bounds[nday - 1]
        fun["days"] += 1
        if (pd.Timestamp(dlabel) - pd.Timestamp(plabel)).days > 4:   # coverage hole: no honest prior-day levels
            fun["days_gap"] += 1
            continue
        seg = mod[a:b]
        ridx = np.flatnonzero((seg >= r0) & (seg < r1)) + a
        oidx = np.flatnonzero((seg >= p["open_mod"]) & (seg < 1080)) + a
        if len(ridx) < max(2, (r1 - r0) // 2) or not len(oidx):
            continue
        iopen = int(oidx[0])
        if mod[iopen] >= p["entry_end"]:
            continue
        RH, RL = float(h[ridx].max()), float(l[ridx].min())
        a5 = F5.day_start.get(str(dlabel))
        if RH <= RL or a5 is None:
            continue
        fun["days_ok"] += 1
        news_ev = news.get(dlabel, [])
        if p["skip_news"] and news_ev:
            continue
        pseg = mod[a0:b0]
        prth = np.flatnonzero((pseg >= 570) & (pseg < 960)) + a0
        statics = [("PDH", 1, float(h[a0:b0].max()), int(t[a])), ("PDL", -1, float(l[a0:b0].min()), int(t[a]))]
        if len(prth):
            statics += [("PRH", 1, float(h[prth].max()), int(t[a])), ("PRL", -1, float(l[prth].min()), int(t[a]))]
        for nm, (s0, s1) in (("AS", (1200, 1440)), ("LO", (120, 300))):
            ix = np.flatnonzero((seg >= s0) & (seg < s1)) + a
            if len(ix):
                av = int(t[ix[-1]]) + 60
                statics += [(nm + "H", 1, float(h[ix].max()), av), (nm + "L", -1, float(l[ix].min()), av)]
        on = [("ONH", 1, float(h[a:iopen].max()), int(t[iopen])), ("ONL", -1, float(l[a:iopen].min()), int(t[iopen]))] \
            if iopen > a else []
        prc = float(c[prth[-1]]) if len(prth) else None
        adr = float(drange[max(0, nday - 10):nday].mean())
        gap_big = None if prc is None else bool(abs(o[iopen] - prc) >= 0.25 * adr)
        prev_t = int(t[a0])

        setups = {1: None, -1: None}
        killed = {1: False, -1: False}
        swept_any = False
        ntr = 0
        j = iopen
        while j < b:
            mi = mod[j]
            if mi >= p["entry_end"] or mi >= 1080 or ntr >= p["max_trades_day"]:
                break
            T = int(t[j]) + 60
            low_hit, high_hit = l[j] <= RL - sweep, h[j] >= RH + sweep
            if high_hit:
                killed[1] = True
            if low_hit:
                killed[-1] = True
            if (low_hit or high_hit) and not swept_any:
                swept_any = True
                fun["days_swept"] += 1
            entered = None
            for d in dirs:
                if killed[d]:
                    setups[d] = None
                    continue
                L1 = MIR1[d][2]
                lvl_m = RL if d == 1 else -RH
                s = setups[d]
                if s is None:
                    if not (low_hit if d == 1 else high_hit):
                        continue
                    s = setups[d] = {"sweep_j": j, "e1": j, "last": {tf: -1 for tf in ladder}, "dead": False}
                    fun["armed"] += 1
                elif L1[j] < L1[s["e1"]]:
                    s["e1"], s["dead"] = j, False
                if s["dead"]:
                    continue
                e1 = s["e1"]
                alive = False
                for tf in ladder:
                    F = frames[tf]
                    e_tf = int(F.bmap[e1])
                    m = F.last_closed(j, T)
                    N = nwin(tf)
                    if m - e_tf <= N:
                        alive = True
                    if m < e_tf or m - e_tf > N or m <= s["last"][tf]:
                        continue
                    s["last"][tf] = m
                    sig = _frame_signal(F, d, e_tf, m, lvl_m, p, max(2, int(p["leg_minutes"]) // tf))
                    if sig is not None:
                        entered = (d, tf, m, sig)
                        break
                if entered is not None:
                    break
                if not alive:
                    s["dead"] = True
                    fun["v_expired"] += 1
            if entered is None:
                j += 1
                continue
            d, tf, m, sig = entered
            F = frames[tf]
            s = setups[d]
            s["dead"] = True                                   # consumed; only a new extreme re-arms it
            fun["signals"] += 1
            fun[f"signals_{tf}m"] += 1
            e1, sweep_j = s["e1"], s["sweep_j"]
            entry = float(c[j])
            atr_tf = float(F.atr[m])
            buf = max(p["stop_buf_ticks"] * TICK, p["stop_buf_atr"] * atr_tf)
            ext_px = float(l[e1]) if d == 1 else float(h[e1])
            stop = ext_px - d * buf
            R = (entry - stop) * d
            tgt_lvl = RH if d == 1 else RL
            dist = (tgt_lvl - entry) * d
            if R <= 0 or dist < p["min_rr"] * R:
                fun["skip_rr"] += 1
                j += 1
                continue
            if size(R + SLIP_PTS, p["risk_usd"], sym) < 1:
                fun["skip_size"] += 1
                j += 1
                continue
            em, tm = entry * d, tgt_lvl * d
            i5 = F5.last_closed(j, T)
            tol = max(2 * TICK, 0.1 * float(F5.atr[i5]))
            H1d = MIR1[d][1]
            q = h1.last(T)
            smt, es_ret = esx.at(dlabel, d, T - 300) if esx is not None else (None, None)
            nq_ret = float(c[j] / o[iopen] - 1.0)
            nres = _frame_n_res(F5, d, i5, em, tm, a5, prev_t, T, tol, f15)
            tgt_pool = None
            for nm, side, px, av in statics + on:
                if side == d and av <= T and abs(px * d - tm) <= tol:
                    tgt_pool = nm
                    break
            if tgt_pool is None:
                Hd, Ld, piv5 = F5.MIR[d][1], F5.MIR[d][2], F5.MIR[d][4]
                ps = [int(x) + a5 for x in np.flatnonzero(piv5[a5:max(a5, i5 - k + 1)]) if abs(Hd[int(x) + a5] - tm) <= tol]
                for x in range(len(ps)):
                    for y in range(x + 1, len(ps)):
                        if ps[y] - ps[x] >= 3 and Ld[ps[x]:ps[y] + 1].min() <= min(Hd[ps[x]], Hd[ps[y]]) - F5.atr[ps[y]]:
                            tgt_pool = "EQ"
                            break
                    if tgt_pool:
                        break
            rec = np.flatnonzero(MIR1[d][3][e1:j + 1] > lvl_m)
            rec_min = (int(t[e1 + int(rec[0])]) - int(t[e1])) / 60.0 if len(rec) else None
            conf = {
                "trend_1h_with": bool(q >= 0 and h1.trend[q] == d),
                "smt": smt,
                "nq_rs_with": None if es_ret is None else bool((nq_ret - es_ret) * d > 0),
                "open_loc_with": bool((o[iopen] - (RH + RL) / 2) * d < 0),
                "ifvg_big": bool(sig["ifvg_size"] >= p["ifvg_big_atr"] * atr_tf),
                "v_fast": bool(rec_min is not None and rec_min <= p["v_fast_minutes"]),
                "lrlr": bool(nres <= 1),
                "tgt_pool": tgt_pool is not None,
            }
            score = int(sum(1 for kk in CONF_KEYS if conf.get(kk)))
            cut = p["tier_cut"]
            tier = "A" if score >= cut[0] else ("B" if score >= cut[1] else "C")
            first = None
            if p["target"] in ("first_clear", "partial"):
                cands = []
                for nm, side, px, av in statics:
                    pm = px * d
                    j0 = int(np.searchsorted(t, av))
                    if side == d and av <= T and em + p["tp_min_r"] * R <= pm < tm - tol and \
                            (j0 > j or H1d[j0:j + 1].max() < pm + TICK):
                        cands.append((pm, nm))
                for pm, pb in _frame_eq_pools(F5, d, i5, a5):
                    j0 = int(np.searchsorted(t, F5.close_t[min(pb + k, len(F5.close_t) - 1)]))
                    if em + p["tp_min_r"] * R <= pm < tm - tol and (j0 > j or H1d[j0:j + 1].max() < pm + TICK):
                        cands.append((pm, "EQ"))
                for pm, nm in sorted(cands):
                    if _frame_n_res(F5, d, i5, em, pm, a5, prev_t, T, tol, f15) <= 1:
                        first = (float(pm * d), nm)
                        break
            full = sim(j, d, b, entry, stop, tgt_lvl, tgt_lvl - d * TICK)
            pp = None
            if p["target"] == "first_clear" and first is not None:
                full = sim(j, d, b, entry, stop, first[0], first[0] - d * TICK)
            elif p["target"] == "partial" and first is not None:
                pp = sim(j, d, b, entry, stop, tgt_lvl, tgt_lvl - d * TICK, first[0], first[0] - d * TICK,
                         p["be_after_partial"])
            fun["trades"] += 1
            fun[f"trades_{tf}m"] += 1
            org = sig["org"]
            zlo, zhi = (sig["ifvg_bot_m"], sig["ifvg_top_m"]) if d == 1 else (-sig["ifvg_top_m"], -sig["ifvg_bot_m"])
            raws.append({
                "day": dlabel, "entry_t": T, "d": d, "entry": entry, "stop": float(stop), "risk_pts": float(R),
                "tgt_lvl": float(tgt_lvl), "rr_opp": float(dist / R), "first": first, "full": full, "pp": pp,
                "partial": p["target"] == "partial", "conf": conf, "score": score, "tier": tier,
                "setup": f"ATM {tf}m:" + ("low-sweep long" if d == 1 else "high-sweep short"),
                "info": {"atm_h": RH, "atm_l": RL, "trigger_tf": tf, "tf": 1, "sweep_t": int(t[sweep_j]),
                         "ext_t": int(t[e1]), "ext_px": ext_px, "leg_origin_t": int(F.t0[org]),
                         "leg_origin_px": float(F.h[org] if d == 1 else F.l[org]), "leg_pts": round(sig["leg"], 2),
                         "ifvg_lo": float(zlo), "ifvg_hi": float(zhi), "ifvg_c1_t": int(F.t0[sig["ifvg_c3"] - 2]),
                         "ifvg_c3_t": int(F.t0[sig["ifvg_c3"]]), "ifvg_inv_t": int(F.t0[sig["inv_bar"]]),
                         "ifvg_pts": round(sig["ifvg_size"], 2), "minutes_to_entry": round((T - int(t[e1]) - 60) / 60.0, 1),
                         "minutes_to_reclaim": rec_min, "n_res": int(nres), "tgt_pool": tgt_pool, "atr_tf": round(atr_tf, 2),
                         "news": news_ev, "gap_big": gap_big, "nq_ret": round(nq_ret * 100, 3),
                         "es_ret": None if es_ret is None else round(es_ret * 100, 3)},
            })
            ntr += 1
            ex = (pp or full)["exit_i"]
            if ex > j:
                if h[j + 1:ex + 1].max() >= RH + sweep:
                    killed[1] = True
                if l[j + 1:ex + 1].min() <= RL - sweep:
                    killed[-1] = True
            setups = {1: None, -1: None}
            j = max(ex, j) + 1
    return raws


# ------------------------------------------------------------------------------------------------ sizing
def qty_for(r, scheme, p, day_pnl=0.0):
    sym = p["sym"]
    pv = PV.get(sym, 2.0)
    rs = r["risk_pts"] + SLIP_PTS                          # stop distance incl. the market-entry tick (as size())
    if scheme == "flat":
        q = size(rs, p["risk_usd"], sym)
    else:
        tr = r["tier"]
        if tr == "A":
            q = min(int(p["tier_a_qty"]), int(p["tier_risk"]["A"] // (rs * pv)))
        elif tr == "B":
            q = size(rs, p["tier_risk"]["B"], sym)
        else:
            q = max(1, size(rs, p["tier_risk"]["C"], sym))
    room = p["dll_usd"] + min(0.0, day_pnl)
    return min(q, int(room // (rs * pv + COMMISSION_RT)))


def _make(r, q, sym):
    pv = PV.get(sym, 2.0)
    extra = {"tier": r["tier"], "score": r["score"], "conf": r["conf"], "rr_opp": round(r["rr_opp"], 2),
             "target": r["tgt_lvl"], "first": r["first"], "info": r["info"]}
    d, e, s = r["d"], r["entry"], r["stop"]
    pp = r["pp"]
    if r["partial"] and pp is not None and q >= 2 and pp["tp1"] is not None:
        q1 = min(q - 1, int(math.ceil(q / 2)))
        q2 = q - q1
        k2 = pp["kind"]
        t1 = make_trade(r["entry_t"], pp["tp1"][0], d, e, s, pp["tp1"][1], "target", qty=q1, sym=sym)
        t2 = make_trade(r["entry_t"], pp["exit_t"], d, e, s, pp["exit_px"], "market" if k2 == "open" else k2, qty=q2,
                        sym=sym, setup=r["setup"], **extra)
        tr = dict(t2)
        tr["qty"] = q
        tr["pnl"] = round(t1["pnl"] + t2["pnl"], 2)
        tr["r"] = round(tr["pnl"] / (r["risk_pts"] * pv * q), 3) if r["risk_pts"] else 0.0
        tr["exit"] = round((t1["exit"] * q1 + t2["exit"] * q2) / q, 2)
        tr["exit_kind"] = "open" if k2 == "open" else k2
        tr["partial_filled"] = True
        tr["mae_usd"] = round(pp["mae"] * pv * q, 2)
        return tr
    f = r["full"]
    tr = make_trade(r["entry_t"], f["exit_t"], d, e, s, f["exit_px"], "market" if f["kind"] == "open" else f["kind"], qty=q,
                    mae_pts=f["mae"], sym=sym, setup=r["setup"], **extra)
    if f["kind"] == "open":
        tr["exit_kind"] = "open"
    return tr


def build_all(raws, scheme="tier", params=None):
    """Size the raw setups: 'flat' = $350 fixed risk; 'tier' = owner's A/B/C confidence sizing. Same entries either way
    (a trade is only dropped if the $1,000 soft daily loss limit leaves no room for even 1 micro)."""
    p = {**PARAMS, **(params or {})}
    out, day_pnl = [], collections.defaultdict(float)
    for r in raws:
        q = qty_for(r, scheme, p, day_pnl[r["day"]])
        if q < 1:
            continue
        tr = _make(r, q, p["sym"])
        day_pnl[r["day"]] += tr["pnl"]
        out.append(tr)
    return out


def run(bars5, params=None, es5=None):
    """Plug-in entry point: trades sized by params['sizing'] (default flat $350; 'tier' = the owner's A/B/C). With params
    tf=1, bars5 must be 1m bars and the 1m timeframe-ladder engine (run_raw_mtf) is used; es5 stays ES 5m."""
    p = {**PARAMS, **(params or {})}
    raws = run_raw_mtf(bars5, p, es5) if int(p.get("tf", 5)) == 1 else run_raw(bars5, p, es5)
    return build_all(raws, p["sizing"], p)


def state(bars5, params=None, es5=None):
    """Dashboard snapshot for the latest trading day: ATM range, swept sides, today's trades, what it is waiting for."""
    p = {**PARAMS, **(params or {})}
    o, h, l, c, t, mod, day = _arrays(bars5)
    bounds = _day_bounds(day)
    if len(bounds) < 2:
        return {"model": NAME, "status": "not enough bars"}
    dl, a, b = bounds[-1]
    seg = mod[a:b]
    r0, r1 = p["range"]
    ridx = np.flatnonzero((seg >= r0) & (seg < r1)) + a
    mi = int(mod[b - 1])
    if not len(ridx):
        return {"model": NAME, "day": dl, "status": "waiting for the 07:00-09:25 ET ATM range"}
    RH, RL = float(h[ridx].max()), float(l[ridx].min())
    after = np.flatnonzero((seg >= p["open_mod"]) & (seg < 1080)) + a
    sw_hi = bool(len(after) and h[after].max() >= RH + TICK)
    sw_lo = bool(len(after) and l[after].min() <= RL - TICK)
    recent = bars5.iloc[bounds[max(0, len(bounds) - 4)][1]:].reset_index(drop=True)
    trades = [x for x in run(recent, p, es5) if x["day"] == dl]
    if trades and trades[-1]["exit_kind"] == "open":
        status = "IN TRADE"
    elif len(trades) >= p["max_trades_day"]:
        status = "DONE FOR TODAY"
    elif mi < r1 and mi < 1080 and mi >= r0:
        status = "BUILDING the ATM range (07:00-09:25 ET)"
    elif p["open_mod"] <= mi < p["entry_end"]:
        if sw_hi and sw_lo:
            status = "both ATM sides taken - no setup today"
        elif sw_lo:
            status = ("ATM LOW swept - waiting for a strong V (close back inside, 50% of the leg, displacement) + IFVG "
                      + ("(5m -> 3m -> 1m ladder)" if int(p.get("tf", 5)) == 1 else "(5m)") + " -> long")
        elif sw_hi:
            status = "ATM HIGH swept - waiting for a strong V + IFVG " + \
                ("(5m -> 3m -> 1m ladder)" if int(p.get("tf", 5)) == 1 else "(5m)") + " -> short"
        else:
            status = "NY AM - waiting for a sweep of the ATM high or low"
    else:
        status = "OUTSIDE the 09:30-11:30 ET entry window"
    return {"model": NAME, "sym": p["sym"], "day": dl, "status": status, "atm_high": RH, "atm_low": RL,
            "atm_mid": (RH + RL) / 2, "swept_high": sw_hi, "swept_low": sw_lo, "trades_today": trades,
            "last_close": float(c[b - 1]), "params": p}
