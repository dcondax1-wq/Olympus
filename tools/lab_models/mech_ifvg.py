"""MECH track: the public "Mechanical Model" / IFVG model (PB Blake and other ICT-derived educators), 5m version.

Rules (sourced and numbered in research/lab/MECH_RULES.md):
  1. Liquidity map, built causally: prior-day high/low (full CME session), Asia 20:00-00:00 H/L, London 02:00-05:00 H/L,
     and untaken 1H swing highs/lows of today + yesterday (3-candle fractal, usable once the next 1H candle has closed).
     Equal highs/lows are covered: sweeping an EQH means trading through the higher of two 1H swing highs.
  2. Only inside the NY AM "golden hour" (09:30-11:00 ET): a 5m bar trades >= 1 tick through a fresh (untaken) level =
     sweep. Sweep of a low -> look for longs; sweep of a high -> look for shorts.
  3. Manipulation leg = swing high -> swing low that hit the level: from the highest high of the hour (12 bars) before
     the sweep extreme down to the extreme (mirror for shorts). Fair value gaps formed inside that leg are the candidates.
  4. Trigger (IFVG): the first 5m candle whose BODY CLOSES beyond the far edge of one of those gaps (inverts it), after the
     sweep and inside the window. 5m is the highest of PB's 1-5m confirmation timeframes and the only one we have.
  5. Entry at that candle's close (market). Stop 1 tick beyond the sweep extreme ("safest" swing stop).
  6. Target = the nearest untaken opposing liquidity at least 1R away (same map + the leg's own swing high/low), capped at
     3R (PB: "~1:1 to 1:3"); none -> no trade. Stop to break-even once price trades +1R. Variant: fixed 1R.
  7. Variant SMT: the partner index (ES for NQ, NQ for ES) must NOT have taken its own matching level.
  Risk: $350 fixed risk, max 2 trades/day, done after a winner or 2 losers, daily stop -$700, flat 15:55 ET.

Causal: decisions on closed 5m bars only; the open position is checked from the bar after entry; same-bar stop/target
ambiguity -> the stop fills first; the break-even move only applies from the bar after it is earned.
"""
from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from tools.strategy_lab import make_trade, size  # noqa: E402

NAME = "mech_ifvg"
TICK = 0.25

PARAMS = {
    "sym": "NQ",                  # NQ (MNQ $2/pt) | ES (MES $5/pt)
    "windows": [[570, 660]],      # ET minutes [start, end): sweep, trigger and entry all inside (09:30-11:00)
    "levels": ["PD", "AS", "LO", "H1"],   # PD prior day H/L, AS Asia, LO London, H1 1H swing highs/lows
    "asia": [1200, 1440],         # 20:00-00:00 ET (prior calendar evening)
    "london": [120, 300],         # 02:00-05:00 ET
    "h1_days": 2,                 # 1H swings formed during the current and previous trading day count
    "sweep_ticks": 1,             # sweep = trade >= this many ticks through the level
    "leg_bars": 12,               # manipulation leg origin = extreme of the 12 bars (1 hour) before the sweep extreme
    "min_fvg_ticks": 1,           # any real 3-candle gap counts
    "stop_ticks": 1,              # stop this many ticks beyond the sweep extreme
    "target": "dol",              # dol (nearest opposing liquidity >= min_rr, capped at max_rr) | rr (fixed R)
    "min_rr": 1.0,
    "max_rr": 3.0,
    "leg_target": True,           # the manipulation leg's own swing high/low counts as opposing liquidity
    "rr": 1.0,                    # fixed-R variant
    "be_r": 1.0,                  # move the stop to entry once a bar trades +be_r R (0 = off)
    "smt": False,                 # require SMT divergence with the partner index
    "risk_usd": 350.0,
    "max_trades_day": 2,
    "stop_after_win": True,
    "max_losses_day": 2,
    "daily_stop_usd": -700.0,
    "flat_mod": 955,              # flat at 15:55 ET (close of the bar that ends 15:55)
    "long": True, "short": True,
}


def _arrays(df):
    return (df["open"].to_numpy(float), df["high"].to_numpy(float), df["low"].to_numpy(float),
            df["close"].to_numpy(float), df["time"].to_numpy(np.int64), df["mod"].to_numpy(int), df["day"].to_numpy())


def _day_bounds(day):
    cut = np.flatnonzero(day[1:] != day[:-1]) + 1
    starts = np.r_[0, cut]
    ends = np.r_[cut, len(day)]
    return list(zip(day[starts], starts, ends))


def _h1_swings(h, l, t):
    """1H candles from 5m bars (clock-hour aligned). Returns lists of swing highs / lows:
    (price, t0, t1, avail_t) where [t0, t1) is the 1H candle and avail_t the close of the next 1H candle (confirmation)."""
    hr = t // 3600
    cut = np.flatnonzero(hr[1:] != hr[:-1]) + 1
    st = np.r_[0, cut]
    en = np.r_[cut, len(t)]
    H = np.maximum.reduceat(h, st)
    L = np.minimum.reduceat(l, st)
    T0 = hr[st] * 3600
    highs, lows = [], []
    for j in range(1, len(st) - 1):
        # neighbours must be the adjacent clock hours (no gaps across the daily break / weekends)
        if T0[j] - T0[j - 1] != 3600 or T0[j + 1] - T0[j] != 3600:
            continue
        if H[j] > H[j - 1] and H[j] > H[j + 1]:
            highs.append((float(H[j]), int(T0[j]), int(T0[j] + 3600), int(T0[j + 1] + 3600)))
        if L[j] < L[j - 1] and L[j] < L[j + 1]:
            lows.append((float(L[j]), int(T0[j]), int(T0[j] + 3600), int(T0[j + 1] + 3600)))
    return highs, lows


class _Partner:
    """The other index for SMT: its own extreme over the window that formed our level, and whether it has been
    taken since (by a given time)."""

    def __init__(self, df):
        self.ok = df is not None and len(df) > 0
        if self.ok:
            self.t = df["time"].to_numpy(np.int64)
            self.h = df["high"].to_numpy(float)
            self.l = df["low"].to_numpy(float)

    def held(self, side, t0, t1, avail_t, t_now):
        """side +1: our level is a LOW. True if the partner did NOT trade below its own low of [t0, t1) between avail_t
        and t_now (inclusive of the bar opening at t_now). None if partner data is missing."""
        if not self.ok:
            return None
        a, b = np.searchsorted(self.t, [t0, t1])
        c, d = np.searchsorted(self.t, [avail_t, t_now + 1])
        if b <= a or d <= c:
            return None
        if side == 1:
            return bool(self.l[c:d].min() > self.l[a:b].min() - TICK / 2)
        return bool(self.h[c:d].max() < self.h[a:b].max() + TICK / 2)


def _levels_for_day(p, h, l, t, mod, bounds, nday, sw_hi, sw_lo):
    """Liquidity levels relevant to trading day nday. Each: dict(side, name, px, t0, t1, avail)."""
    dlabel, a, b = bounds[nday]
    a0, b0 = bounds[nday - 1][1], bounds[nday - 1][2]
    use = set(p["levels"])
    out = []
    t_day0 = int(t[a])
    if "PD" in use:
        out.append({"side": -1, "name": "PDH", "px": float(h[a0:b0].max()), "t0": int(t[a0]), "t1": int(t[b0 - 1]) + 300, "avail": t_day0})
        out.append({"side": 1, "name": "PDL", "px": float(l[a0:b0].min()), "t0": int(t[a0]), "t1": int(t[b0 - 1]) + 300, "avail": t_day0})
    seg_mod = mod[a:b]
    for fam, (s, e) in (("AS", p["asia"]), ("LO", p["london"])):
        if fam not in use:
            continue
        m = (seg_mod >= s) & (seg_mod < e)        # Asia 20:00-24:00 is the evening that opens this trading day
        if not m.any():
            continue
        idx = np.flatnonzero(m) + a
        t0, t1 = int(t[idx[0]]), int(t[idx[-1]]) + 300
        out.append({"side": -1, "name": fam + "H", "px": float(h[idx].max()), "t0": t0, "t1": t1, "avail": t1})
        out.append({"side": 1, "name": fam + "L", "px": float(l[idx].min()), "t0": t0, "t1": t1, "avail": t1})
    if "H1" in use:
        k0 = max(0, nday - int(p["h1_days"]) + 1)
        t_from = int(t[bounds[k0][1]])
        t_to = int(t[b - 1]) + 300
        for side, lst in ((-1, sw_hi), (1, sw_lo)):
            for px, t0, t1, av in lst:
                if t_from <= t0 and av <= t_to:
                    out.append({"side": side, "name": "H1" + ("H" if side == -1 else "L"), "px": px, "t0": t0, "t1": t1, "avail": av})
    return out


def run(bars5, params=None, es5=None, _debug=None):
    p = {**PARAMS, **(params or {})}
    sym = p["sym"]
    o, h, l, c, t, mod, day = _arrays(bars5)
    n = len(c)
    bounds = _day_bounds(day)
    sw_hi, sw_lo = _h1_swings(h, l, t) if "H1" in p["levels"] else ([], [])
    partner = _Partner(es5) if p["smt"] else None
    wins = [tuple(w) for w in p["windows"]]
    sweep = p["sweep_ticks"] * TICK
    min_fvg = p["min_fvg_ticks"] * TICK
    lb = int(p["leg_bars"])
    dirs = [d for d, ok in ((1, p["long"]), (-1, p["short"])) if ok]
    flat_last = p["flat_mod"] - 5          # bar opening 15:50 closes 15:55
    trades = []

    for nday in range(1, len(bounds)):
        dlabel, a, b = bounds[nday]
        levels = _levels_for_day(p, h, l, t, mod, bounds, nday, sw_hi, sw_lo)
        # freshness: a level is already taken if price traded through it after it became available (before today)
        for lv in levels:
            lv["taken"] = False
            if lv["avail"] < t[a]:
                j0 = int(np.searchsorted(t, lv["avail"]))
                if j0 < a:
                    lv["taken"] = bool(l[j0:a].min() <= lv["px"] - sweep) if lv["side"] == 1 else \
                        bool(h[j0:a].max() >= lv["px"] + sweep)
        pos = None
        setups = {1: None, -1: None}
        ntr = nloss = 0
        won = False
        day_pnl = 0.0
        for i in range(a, b):
            mi = mod[i]
            ti = int(t[i])
            # ------------------------------------------------------------ manage the open position (from the bar after entry)
            if pos is not None:
                d = pos["d"]
                hi_d, lo_d, op_d = (h[i], l[i], o[i]) if d == 1 else (-l[i], -h[i], -o[i])
                ex = None
                if lo_d <= pos["stop_d"]:
                    ex = (min(op_d, pos["stop_d"]), "be" if pos["be"] else "stop")
                elif hi_d >= pos["tgt_d"]:
                    ex = (pos["tgt_d"], "target")          # resting limit: filled at its price (never better)
                elif (mi >= flat_last and mi < 1080) or i == b - 1:
                    ex = (c[i] * d, "time")
                pos["mae"] = max(pos["mae"], min(pos["entry_d"] - lo_d, pos["entry_d"] - pos["stop_d"]))
                if ex is None and p["be_r"] > 0 and not pos["be"] and hi_d >= pos["entry_d"] + p["be_r"] * pos["risk"]:
                    pos["be"], pos["stop_d"] = True, pos["entry_d"]
                if ex is not None:
                    kind = ex[1]
                    is_open = kind == "time" and i == n - 1 and not (mi >= flat_last and mi < 1080)
                    tr = make_trade(t[pos["i"]], ti + 300, d, pos["entry"], pos["stop0"], ex[0] * d,
                                    "market" if is_open else kind, setup=pos["setup"], mae_pts=pos["mae"], sym=sym,
                                    risk_usd=p["risk_usd"], target=pos["tgt"], levels=pos["levels"], smt=pos["smt"])
                    if is_open:
                        tr["exit_kind"] = "open"
                    trades.append(tr)
                    ntr += 1
                    day_pnl += tr["pnl"]
                    if tr["pnl"] > 0:
                        won = True
                    else:
                        nloss += 1
                    pos = None
                    setups = {1: None, -1: None}
                    # the exit bar is still scanned for sweeps below, but cannot open a new trade
                    exited = True
                else:
                    exited = False
            else:
                exited = False
            # ------------------------------------------------------------ sweeps of fresh levels
            in_win = any(w0 <= mi < w1 for w0, w1 in wins)
            done = (ntr >= p["max_trades_day"] or (won and p["stop_after_win"]) or nloss >= p["max_losses_day"]
                    or day_pnl <= p["daily_stop_usd"])
            can_trade = pos is None and not exited and in_win and not done
            for lv in levels:
                if lv["taken"] or ti < lv["avail"]:
                    continue
                side = lv["side"]
                hit = l[i] <= lv["px"] - sweep if side == 1 else h[i] >= lv["px"] + sweep
                if not hit:
                    continue
                lv["taken"] = True
                if not can_trade or side not in dirs:
                    continue
                s = setups[side]
                if s is None:
                    setups[side] = {"arm": i, "ext": i, "levels": [lv]}
                    if _debug is not None:
                        _debug.append({"day": dlabel, "arm": side, "lv": lv["name"]})
                else:
                    s["levels"].append(lv)
            if not in_win:
                setups = {1: None, -1: None}
                continue
            if not can_trade:
                continue
            # ------------------------------------------------------------ armed setups -> IFVG trigger on this bar's close
            for d in dirs:
                s = setups[d]
                if s is None:
                    continue
                if (l[i] < l[s["ext"]]) if d == 1 else (h[i] > h[s["ext"]]):
                    s["ext"] = i
                ext = s["ext"]
                lo = max(a - 300, ext - lb, 0)
                # direction space: long as-is, short mirrored (x -> -x, high <-> low)
                if d == 1:
                    O_, H_, L_, C_ = o, h, l, c
                else:
                    O_, H_, L_, C_ = -o, -l, -h, -c
                leg0 = lo + int(np.argmax(H_[lo:ext + 1]))
                trig = None
                gaps = []
                for k in range(leg0 + 2, min(ext + 1, i - 1) + 1):
                    top, bot = L_[k - 2], H_[k]            # gap against the new direction (bearish FVG for a long)
                    if top - bot >= min_fvg - 1e-9:
                        gaps.append((top, bot, k))
                for top, bot, k in sorted(gaps):
                    if C_[i] > top and (k + 1 > i - 1 or C_[k + 1:i].max() <= top):
                        trig = (top, bot, k)
                        break
                if trig is None:
                    continue
                setups[d] = None
                entry = float(c[i])
                ext_px = float(l[ext]) if d == 1 else float(h[ext])
                stop = ext_px - d * p["stop_ticks"] * TICK
                risk = (entry - stop) * d
                if risk <= 0 or size(risk + TICK, p["risk_usd"], sym) < 1:
                    if _debug is not None:
                        _debug.append({"day": dlabel, "skip": "size", "risk": risk})
                    continue
                # ---- SMT (variant)
                smt = None
                if partner is not None:
                    held = [partner.held(d, lv["t0"], lv["t1"], lv["avail"], ti) for lv in s["levels"]]
                    known = [x for x in held if x is not None]
                    smt = bool(any(known)) if known else None
                    if not smt:
                        if _debug is not None:
                            _debug.append({"day": dlabel, "skip": "smt" if smt is False else "smt_nodata"})
                        continue
                # ---- target
                if p["target"] == "dol":
                    cands = [lv["px"] for lv in levels if lv["side"] == -d and not lv["taken"] and lv["avail"] <= ti + 300]
                    if p["leg_target"]:
                        org = float(h[leg0]) if d == 1 else float(l[leg0])
                        after = h[leg0 + 1:i + 1].max() if d == 1 else l[leg0 + 1:i + 1].min()
                        if (after - org) * d < 0:        # the leg's swing high/low is still untaken
                            cands.append(org)
                    opts = sorted(x for x in cands if (x - entry) * d >= p["min_rr"] * risk)
                    if not opts:
                        if _debug is not None:
                            _debug.append({"day": dlabel, "skip": "no_dol", "risk": risk})
                        continue
                    tgt = opts[0] if d == 1 else opts[-1]
                    if (tgt - entry) * d > p["max_rr"] * risk:
                        tgt = entry + d * p["max_rr"] * risk
                else:
                    tgt = entry + d * p["rr"] * risk
                pos = {"d": d, "i": i, "entry": entry, "stop0": stop, "tgt": float(tgt), "entry_d": entry * d,
                       "stop_d": stop * d, "tgt_d": tgt * d, "risk": risk, "be": False, "mae": 0.0, "smt": smt,
                       "setup": "IFVG:" + "+".join(lv["name"] for lv in s["levels"]),
                       "levels": [lv["name"] for lv in s["levels"]]}
                setups = {1: None, -1: None}
                if _debug is not None:
                    _debug.append({"day": dlabel, "i": i, "d": d, "gap": trig, "ext": ext_px, "entry": entry, "tgt": tgt,
                                   "levels": pos["levels"]})
                break
    return trades


def state(bars5, params=None, es5=None):
    """Dashboard snapshot for the latest trading day: liquidity map (taken / fresh), today's trades, status."""
    p = {**PARAMS, **(params or {})}
    o, h, l, c, t, mod, day = _arrays(bars5)
    bounds = _day_bounds(day)
    if len(bounds) < 2:
        return {"model": NAME, "status": "not enough bars"}
    nday = len(bounds) - 1
    dlabel, a, b = bounds[nday]
    sw_hi, sw_lo = _h1_swings(h, l, t)
    levels = _levels_for_day(p, h, l, t, mod, bounds, nday, sw_hi, sw_lo)
    t_last = int(t[b - 1])
    lv_out = []
    for lv in levels:
        avail = lv["avail"] <= t_last + 300
        seg = (t[a:b] >= lv["avail"])
        if lv["side"] == 1:
            taken = bool(avail and seg.any() and l[a:b][seg].min() <= lv["px"] - p["sweep_ticks"] * TICK)
        else:
            taken = bool(avail and seg.any() and h[a:b][seg].max() >= lv["px"] + p["sweep_ticks"] * TICK)
        lv_out.append({"name": lv["name"], "price": round(lv["px"], 2), "formed": avail, "taken": taken})
    recent = bars5.iloc[bounds[max(0, nday - 3)][1]:].reset_index(drop=True)
    trades = [tr for tr in run(recent, p, es5) if tr["day"] == dlabel]
    mi = int(mod[b - 1])
    in_win = any(w0 <= mi < w1 for w0, w1 in p["windows"])
    wins = [tr for tr in trades if tr["pnl"] > 0]
    losses = [tr for tr in trades if tr["pnl"] <= 0 and tr["exit_kind"] != "open"]
    if trades and trades[-1]["exit_kind"] == "open":
        status = "IN TRADE"
    elif len(trades) >= p["max_trades_day"] or (wins and p["stop_after_win"]) or len(losses) >= p["max_losses_day"]:
        status = "DONE FOR TODAY"
    elif in_win:
        status = "NY AM WINDOW - waiting for a sweep of a fresh level, then a 5m IFVG close"
    else:
        status = "OUTSIDE WINDOW (" + ", ".join(f"{w0 // 60:02d}:{w0 % 60:02d}-{w1 // 60:02d}:{w1 % 60:02d}" for w0, w1 in p["windows"]) + " ET)"
    return {"model": NAME, "sym": p["sym"], "day": dlabel, "status": status, "levels": lv_out,
            "fresh_levels": [x["name"] + f"@{x['price']}" for x in lv_out if x["formed"] and not x["taken"]],
            "trades_today": trades, "last_close": float(c[b - 1]), "params": p}
