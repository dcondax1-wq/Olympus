"""Track B: session liquidity / Power of 3 (accumulation -> manipulation -> distribution), straight rules.

Accumulation  Asia 20:00-00:00, London 02:00-05:00, overnight 18:00-09:30 ranges (+ prior day H/L), midnight / 09:30 opens.
Manipulation  inside the killzone a 5m bar trades >= 1 tick beyond a FRESH (not yet taken today) session level.
Confirmation  5m CISD (body close through the open of the candle run that printed the sweep extreme) and/or an IFVG
              (body close through an FVG formed inside the sweep leg).
Distribution  stop beyond the sweep extreme + buffer, target = fixed R / opposite side of the swept range / nearest
              untaken level; optional BE; flat 15:55 ET.

Causal: every decision uses closed 5m bars only; entry = signal-bar close; from the next bar the stop is checked before
the target (same-bar ambiguity -> stop first). Shorts are simulated in mirrored price space (x -> -x) like engine/model.py.
"""
from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from tools.strategy_lab import make_trade  # noqa: E402

NAME = "session_po3"
TICK = 0.25

PARAMS = {
    "windows": [[570, 660]],      # ET minutes: the sweep AND the entry must happen inside [start, end) (09:30-11:00)
    "levels": ["AS", "LO", "ON", "PD"],   # AS Asia, LO London, ON overnight, PD prior day (full session), AM, LU (PM only)
    "on_end": 570,                # overnight range ends 09:30 (or the first window start if earlier)
    "fresh": True,                # a level only counts if no bar traded through it between its formation and the sweep
    "sweep_ticks": 1,             # sweep = trade >= this many ticks beyond the level
    "trigger": "cisd",            # cisd | ifvg | either | engine (IFVG if the leg holds an FVG, else CISD)
    "min_fvg": 3.0,               # points (engine NQ spec)
    "leg_lookback": 24,           # bars searched back from the extreme for the leg origin (IFVG / CISD run cap)
    "expiry_min": 60,             # setup dies if no trigger within N minutes of the latest extreme
    "stop_buffer": 2.0,           # points beyond the sweep extreme
    "min_stop": 8.0,              # widen tighter stops to this (points)
    "max_stop": 60.0,             # skip setups whose stop is wider (points)
    "target": "rr",               # rr | opp (opposite side of the swept range) | pool (nearest untaken level)
    "rr": 2.0,                    # fixed R for target "rr" and the fallback
    "min_rr": 1.5,                # opp/pool targets must pay at least this
    "max_rr": 4.0,                # opp/pool targets capped here
    "fallback": True,             # opp/pool: when no level pays >= min_rr, use the fixed rr target (else skip)
    "target_ticks": 1,            # limit target needs a trade-through of N ticks
    "be_r": 0.0,                  # move the stop to entry once a bar trades +be_r R (0 = off)
    "flat_mod": 955,              # flat at 15:55 ET (exit at the close of the bar ending 15:55)
    "max_trades_day": 1,
    "stop_after_win": True,
    "long": True, "short": True,
    # ---- optional filters (all off by default; each one is tested, not assumed)
    "bias": "none",               # none | pdc (prior RTH close in upper half -> longs only, lower -> shorts) | pdc_fade
                                  #   | pdo (prior RTH close vs open) | pdo_fade | ema (5m close vs EMA(bias_ema) at signal)
    "bias_ema": 240,
    "pd_filter": "none",          # none | on (long only in the discount half of the overnight range, short in premium)
    "mo_filter": "none",          # none | with (long only below the midnight open, short above) | against
    "rth_open_filter": "none",    # none | with (long only below the 09:30 open, short above) | against
    "vwap_filter": "none",        # none | below (long only under the RTH VWAP, short above) | above
    "open_value": "none",         # none | with (09:30 open above prior RTH VWAP -> longs only) | against
    "smt": "none",                # none | require (ES did NOT sweep its matching level) | veto (skip when ES held)
    "smt_missing_ok": False,      # if ES bars are missing: True = let the trade through
    "first_sweep_only": False,    # only the first armed setup of the day (per direction) may trade
}

SESS = {  # name: (start dm, end dm) in minutes after 18:00 ET (dm), [start, end)
    "AS": (120, 360),     # 20:00-00:00
    "LO": (480, 660),     # 02:00-05:00
    "AM": (930, 1080),    # 09:30-12:00 (PM windows only)
    "LU": (1080, 1170),   # 12:00-13:30 (PM windows only)
}


def _dm(mod):
    return np.where(mod >= 1080, mod - 1080, mod + 360)


def _arrays(df):
    o = df["open"].to_numpy(float)
    h = df["high"].to_numpy(float)
    l = df["low"].to_numpy(float)
    c = df["close"].to_numpy(float)
    v = df["volume"].to_numpy(float)
    t = df["time"].to_numpy(np.int64)
    mod = df["mod"].to_numpy(int)
    day = df["day"].to_numpy()
    return o, h, l, c, v, t, mod, _dm(mod), day


def _day_bounds(day):
    cut = np.flatnonzero(day[1:] != day[:-1]) + 1
    starts = np.r_[0, cut]
    ends = np.r_[cut, len(day)]
    return list(zip(day[starts], starts, ends))


def _levels(h, l, o, c, v, mod, dm, a, b, prev, p, on_end_dm):
    """Session levels of the day [a, b) and of the prior day prev=(a0, b0). Each level: (price, formed_dm)."""
    L = {}
    seg_dm = dm[a:b]
    for name, (s, e) in SESS.items():
        m = (seg_dm >= s) & (seg_dm < e)
        if m.any():
            L[name + "H"] = (float(h[a:b][m].max()), e)
            L[name + "L"] = (float(l[a:b][m].min()), e)
    m = seg_dm < on_end_dm
    if m.any():
        L["ONH"] = (float(h[a:b][m].max()), on_end_dm)
        L["ONL"] = (float(l[a:b][m].min()), on_end_dm)
    info = {}
    if prev is not None:
        a0, b0 = prev
        L["PDH"] = (float(h[a0:b0].max()), 0)
        L["PDL"] = (float(l[a0:b0].min()), 0)
        rth = (mod[a0:b0] >= 570) & (mod[a0:b0] < 960)
        if rth.any():
            idx = np.flatnonzero(rth) + a0
            hi, lo = float(h[idx].max()), float(l[idx].min())
            info["pd_rth_open"], info["pd_rth_close"] = float(o[idx[0]]), float(c[idx[-1]])
            info["pd_rth_hi"], info["pd_rth_lo"] = hi, lo
            tp = (h[idx] + l[idx] + c[idx]) / 3
            vv = v[idx]
            info["pd_vwap"] = float((tp * vv).sum() / vv.sum()) if vv.sum() > 0 else float(tp.mean())
    k = np.flatnonzero(mod[a:b] == 0)
    info["midnight_open"] = float(o[a + k[0]]) if len(k) else None
    k = np.flatnonzero(mod[a:b] == 570)
    info["rth_open"] = float(o[a + k[0]]) if len(k) else None
    return L, info


def _cisd_level(O, H, L, C, ext, lo_i, lb):
    """Direction space (long): open of the first candle of the down-close run that printed the extreme bar `ext`.
    If the extreme bar itself closed up, the run is the one ending on the bar before it."""
    r = ext if C[ext] < O[ext] else ext - 1
    if r < lo_i or not (C[r] < O[r]):
        return float(H[ext])          # no down run into the low: demand a close above the sweep bar's high
    j = r
    while j - 1 >= max(lo_i, ext - lb) and C[j - 1] < O[j - 1]:
        j -= 1
    return float(O[j])


def _trigger(mode, O, H, L, C, i, ext, arm_lo, p):
    """Direction-space trigger on bar i (long). Returns (kind, level) or None."""
    lb = int(p["leg_lookback"])
    up = C[i] > O[i]
    if not up:
        return None
    gaps = []
    if mode in ("ifvg", "either", "engine"):
        a = max(arm_lo, ext - lb)
        leg0 = a + int(np.argmax(H[a:ext + 1]))
        for k in range(leg0 + 2, i):
            top, bot = L[k - 2], H[k]
            if top - bot >= p["min_fvg"]:
                gaps.append((k, top))
        for k, top in sorted(gaps, key=lambda z: z[1]):
            if C[i] > top and (i - k <= 1 or C[k + 1:i].max() <= top):
                return ("IFVG", float(top))
    if mode == "cisd" or mode == "either" or (mode == "engine" and not gaps):
        lvl = _cisd_level(O, H, L, C, ext, max(0, ext - lb), lb)
        prev = C[ext + 1:i]
        if C[i] > lvl and (len(prev) == 0 or prev.max() <= lvl):
            return ("CISD", lvl)
    return None


def _ema(x, n):
    a = 2.0 / (n + 1)
    out = np.empty_like(x)
    m = x[0]
    for k, xv in enumerate(x):
        m = a * xv + (1 - a) * m
        out[k] = m
    return out


class _ES:
    """ES partner levels for SMT: same session definitions, looked up by NQ bar time."""

    def __init__(self, es5, p, on_end_dm):
        self.ok = es5 is not None and len(es5) > 0
        if not self.ok:
            return
        o, h, l, c, v, t, mod, dm, day = _arrays(es5)
        self.h, self.l, self.t, self.dm = h, l, t, dm
        self.days = {}
        bounds = _day_bounds(day)
        for n, (d, a, b) in enumerate(bounds):
            prev = (bounds[n - 1][1], bounds[n - 1][2]) if n else None
            L, _ = _levels(h, l, o, c, v, mod, dm, a, b, prev, p, on_end_dm)
            self.days[d] = (a, b, L)

    def held(self, d, name, side, t_sig):
        """True if ES did NOT trade through its own `name` level between formation and t_sig (side +1 = low level).
        None when ES data is missing."""
        if not self.ok or d not in self.days:
            return None
        a, b, L = self.days[d]
        if name not in L:
            return None
        px, formed = L[name]
        j1 = int(np.searchsorted(self.t, t_sig, side="right"))
        j1 = min(j1, b)
        if j1 <= a:
            return None
        seg = slice(a, j1)
        m = self.dm[seg] >= formed
        if not m.any():
            return None
        if side == 1:
            return bool(self.l[seg][m].min() > px - TICK)
        return bool(self.h[seg][m].max() < px + TICK)


def run(bars5, params=None, es5=None, _debug=None):
    p = {**PARAMS, **(params or {})}
    o, h, l, c, v, t, mod, dm, day = _arrays(bars5)
    n = len(c)
    wins = [tuple(w) for w in p["windows"]]
    on_end_dm = int(_dm(np.array([min(p["on_end"], min(w[0] for w in wins))]))[0])
    es = _ES(es5, p, on_end_dm) if p["smt"] != "none" else None
    ema = _ema(c, int(p["bias_ema"])) if p["bias"] == "ema" else None
    sweep = p["sweep_ticks"] * TICK
    use_lv = set(p["levels"])
    bounds = _day_bounds(day)
    trades = []
    dirs = [d for d, ok in ((1, p["long"]), (-1, p["short"])) if ok]
    for nday, (dlabel, a, b) in enumerate(bounds):
        prev = (bounds[nday - 1][1], bounds[nday - 1][2]) if nday else None
        if prev is None:
            continue
        LV, info = _levels(h, l, o, c, v, mod, dm, a, b, prev, p, on_end_dm)
        # candidate levels by side: side +1 = lows (long setups), -1 = highs (short setups)
        cand = {1: {}, -1: {}}
        for name, (px, formed) in LV.items():
            fam = name[:2]
            if fam not in use_lv:
                continue
            if fam in ("AM", "LU") and not any(w[0] >= 780 for w in wins):
                continue
            side = 1 if name.endswith("L") else -1
            cand[side][name] = {"px": px, "formed": formed, "taken": False}
        # static directional bias
        allow = {1: True, -1: True}
        bias = 0
        if p["bias"] in ("pdc", "pdc_fade") and "pd_rth_close" in info:
            mid = (info["pd_rth_hi"] + info["pd_rth_lo"]) / 2
            bias = 1 if info["pd_rth_close"] > mid else -1
        elif p["bias"] in ("pdo", "pdo_fade") and "pd_rth_close" in info:
            bias = 1 if info["pd_rth_close"] > info["pd_rth_open"] else -1
        if p["bias"].endswith("_fade"):
            bias = -bias
        if bias:
            allow = {1: bias == 1, -1: bias == -1}
        ov = 0
        if p["open_value"] != "none" and info.get("rth_open") is not None and "pd_vwap" in info:
            ov = 1 if info["rth_open"] > info["pd_vwap"] else -1
            if p["open_value"] == "against":
                ov = -ov
        on_mid = (LV["ONH"][0] + LV["ONL"][0]) / 2 if "ONH" in LV else None
        setups = {1: None, -1: None}
        armed_once = {1: False, -1: False}
        pos = None
        ntr, won = 0, False
        vw_pv = vw_v = 0.0
        flat_dm = int(_dm(np.array([p["flat_mod"] - 5]))[0])
        win_seen = False
        for i in range(a, b):
            mi, di = mod[i], dm[i]
            if mi >= 570 and mi < 960:
                tp = (h[i] + l[i] + c[i]) / 3
                vw_pv += tp * v[i]
                vw_v += v[i]
            exited = False
            # ---------------------------------------------------------------- manage an open position
            if pos is not None:
                d = pos["d"]
                hi_d, lo_d = (h[i], l[i]) if d == 1 else (-l[i], -h[i])
                op_d = o[i] * d
                ex = None
                if lo_d <= pos["stop_d"]:
                    px_d = min(op_d, pos["stop_d"])
                    ex = (px_d, "be" if pos["be"] else "stop")
                elif hi_d >= pos["tgt_d"] + p["target_ticks"] * TICK:
                    ex = (pos["tgt_d"], "target")
                elif di >= flat_dm or i == b - 1:
                    ex = (c[i] * d, "time")
                if ex is None and p["be_r"] > 0 and not pos["be"] and hi_d >= pos["entry_d"] + p["be_r"] * pos["risk"]:
                    pos["be"] = True
                    pos["stop_d"] = pos["entry_d"]
                pos["mae"] = max(pos["mae"], pos["entry_d"] - lo_d)
                if ex is not None:
                    px = ex[0] * d
                    kind = ex[1]
                    if kind == "time" and i == b - 1 and i == n - 1 and di < flat_dm:
                        kind = "open"
                    tr = make_trade(t[pos["i"]], t[i] + 300, d, pos["entry"], pos["stop0"], px, kind if kind != "open" else "market",
                                    setup=pos["setup"], mae_pts=pos["mae"], target=pos["tgt"], levels=pos["levels"])
                    if kind == "open":
                        tr["exit_kind"] = "open"
                    trades.append(tr)
                    ntr += 1
                    won = won or tr["pnl"] > 0
                    pos = None
                    exited = True
                    setups = {1: None, -1: None}
                # level freshness still updates below
            # ---------------------------------------------------------------- level freshness + sweeps
            in_win = any(w[0] <= mi < w[1] for w in wins)
            if in_win and not win_seen:
                win_seen = True
                if not p["fresh"]:        # stale levels are allowed: forget pre-window takes once
                    for side in (1, -1):
                        for lv in cand[side].values():
                            lv["taken"] = False
            can_trade = (pos is None and not exited and in_win and ntr < p["max_trades_day"]
                         and not (won and p["stop_after_win"]))
            for side in (1, -1):
                for name, lv in cand[side].items():
                    if lv["taken"] or di < lv["formed"]:
                        continue
                    hit = l[i] <= lv["px"] - sweep if side == 1 else h[i] >= lv["px"] + sweep
                    if not hit:
                        continue
                    lv["taken"] = True
                    d = side
                    if not can_trade or d not in dirs or not allow[d] or (ov and ov != d):
                        continue
                    if p["first_sweep_only"] and armed_once[d] and setups[d] is None:
                        continue
                    if setups[d] is None:
                        setups[d] = {"arm": i, "ext": i, "levels": [name], "last_ext_dm": di}
                        armed_once[d] = True
                    elif name not in setups[d]["levels"]:
                        setups[d]["levels"].append(name)
            if not can_trade:
                if pos is None and not in_win:
                    setups = {1: None, -1: None}
                continue
            # ---------------------------------------------------------------- armed setups -> trigger
            for d in dirs:
                s = setups[d]
                if s is None:
                    continue
                X_lo = l if d == 1 else h
                if (l[i] < l[s["ext"]]) if d == 1 else (h[i] > h[s["ext"]]):
                    s["ext"] = i
                    s["last_ext_dm"] = di
                if di - s["last_ext_dm"] > p["expiry_min"]:
                    setups[d] = None
                    continue
                lo = max(a, s["ext"] - int(p["leg_lookback"]) - 2)
                if d == 1:
                    O_, H_, L_, C_ = o[lo:i + 1], h[lo:i + 1], l[lo:i + 1], c[lo:i + 1]
                else:
                    O_, H_, L_, C_ = -o[lo:i + 1], -l[lo:i + 1], -h[lo:i + 1], -c[lo:i + 1]
                trig = _trigger(p["trigger"], O_, H_, L_, C_, i - lo, s["ext"] - lo, 0, p)
                if trig is None:
                    continue
                setups[d] = None          # one shot per setup
                entry = float(c[i])
                ext_px = float(X_lo[s["ext"]])
                stop = ext_px - d * p["stop_buffer"]
                risk = (entry - stop) * d
                if risk > p["max_stop"] or risk <= 0:
                    continue
                if risk < p["min_stop"]:
                    stop = entry - d * p["min_stop"]
                    risk = p["min_stop"]
                # ---- entry-time filters
                if p["pd_filter"] == "on" and on_mid is not None and (entry - on_mid) * d > 0:
                    continue
                mo = info.get("midnight_open")
                if p["mo_filter"] != "none" and mo is not None:
                    below = (entry - mo) * d < 0
                    if (p["mo_filter"] == "with") != below:
                        continue
                ro = info.get("rth_open")
                if p["rth_open_filter"] != "none" and ro is not None:
                    below = (entry - ro) * d < 0
                    if (p["rth_open_filter"] == "with") != below:
                        continue
                if p["vwap_filter"] != "none" and vw_v > 0:
                    under = (entry - vw_pv / vw_v) * d < 0
                    if (p["vwap_filter"] == "below") != under:
                        continue
                if p["bias"] == "ema" and (c[i] - ema[i]) * d < 0:
                    continue
                if p["smt"] != "none":
                    held = [es.held(dlabel, nm, d, int(t[i])) for nm in s["levels"]]
                    known = [x for x in held if x is not None]
                    if not known:
                        if not p["smt_missing_ok"]:
                            continue
                    else:
                        smt = any(known)
                        if (p["smt"] == "require") != smt:
                            continue
                # ---- target
                tgt = None
                if p["target"] in ("opp", "pool"):
                    opts = []
                    if p["target"] == "opp":
                        for nm in s["levels"]:
                            on = nm[:-1] + ("H" if d == 1 else "L")
                            if on in LV:
                                opts.append(LV[on][0])
                    else:                 # nearest untaken, already-formed level on the far side
                        for nm, lv in cand[-d].items():
                            if not lv["taken"] and di >= lv["formed"]:
                                opts.append(lv["px"])
                    pays = sorted(x for x in opts if (x - entry) * d >= p["min_rr"] * risk)
                    pays = pays if d == 1 else pays[::-1]
                    if pays:
                        tgt = pays[0]
                        if (tgt - entry) * d > p["max_rr"] * risk:
                            tgt = entry + d * p["max_rr"] * risk
                    elif not p["fallback"]:
                        continue
                if tgt is None:
                    tgt = entry + d * p["rr"] * risk
                pos = {"d": d, "i": i, "entry": entry, "stop0": stop, "tgt": float(tgt), "entry_d": entry * d,
                       "stop_d": stop * d, "tgt_d": tgt * d, "risk": risk, "be": False, "mae": 0.0,
                       "setup": f"{trig[0]}:{'+'.join(s['levels'])}", "levels": list(s["levels"])}
                setups = {1: None, -1: None}
                if _debug is not None:
                    _debug.append({"day": dlabel, "i": i, "d": d, "trig": trig, "levels": s["levels"], "ext": ext_px})
                break
    return trades


def state(bars5, params=None, es5=None):
    """Dashboard snapshot for the latest trading day in bars5: levels, bias, open/last trade, what the model waits for."""
    p = {**PARAMS, **(params or {})}
    o, h, l, c, v, t, mod, dm, day = _arrays(bars5)
    bounds = _day_bounds(day)
    if len(bounds) < 2:
        return {"model": NAME, "status": "not enough bars"}
    dlabel, a, b = bounds[-1]
    prev = (bounds[-2][1], bounds[-2][2])
    wins = [tuple(w) for w in p["windows"]]
    on_end_dm = int(_dm(np.array([min(p["on_end"], min(w[0] for w in wins))]))[0])
    LV, info = _levels(h, l, o, c, v, mod, dm, a, b, prev, p, on_end_dm)
    last_dm = int(dm[b - 1])
    levels = {}
    for name, (px, formed) in LV.items():
        if name[:2] not in set(p["levels"]):
            continue
        formed_ok = last_dm >= formed
        m = dm[a:b] >= formed
        if name.endswith("L"):
            taken = bool(formed_ok and m.any() and l[a:b][m].min() <= px - p["sweep_ticks"] * TICK)
        else:
            taken = bool(formed_ok and m.any() and h[a:b][m].max() >= px + p["sweep_ticks"] * TICK)
        levels[name] = {"price": round(px, 2), "formed": formed_ok, "taken": taken}
    recent = bars5.iloc[bounds[max(0, len(bounds) - 3)][1]:]
    trades = run(recent.reset_index(drop=True), p, es5)
    today = [tr for tr in trades if tr["day"] == dlabel]
    mi = int(mod[b - 1])
    in_win = any(w[0] <= mi < w[1] for w in wins)
    fresh = [k for k, x in levels.items() if x["formed"] and not x["taken"]]
    if today and today[-1]["exit_kind"] == "open":
        status = "IN TRADE"
    elif len(today) >= p["max_trades_day"] or (today and today[-1]["pnl"] > 0 and p["stop_after_win"]):
        status = "DONE FOR TODAY"
    elif in_win:
        status = "KILLZONE - waiting for a sweep of a fresh level + 5m " + p["trigger"].upper()
    else:
        status = "OUTSIDE KILLZONE (" + ", ".join(f"{w[0] // 60:02d}:{w[0] % 60:02d}-{w[1] // 60:02d}:{w[1] % 60:02d}" for w in wins) + " ET)"
    bias = "none"
    if p["bias"] in ("pdc", "pdo") and "pd_rth_close" in info:
        ref = (info["pd_rth_hi"] + info["pd_rth_lo"]) / 2 if p["bias"] == "pdc" else info["pd_rth_open"]
        bias = "long" if info["pd_rth_close"] > ref else "short"
    return {"model": NAME, "day": dlabel, "status": status, "bias": bias, "levels": levels, "fresh_levels": fresh,
            "midnight_open": info.get("midnight_open"), "rth_open": info.get("rth_open"), "pd_vwap": info.get("pd_vwap"),
            "trades_today": today, "last_close": float(c[b - 1]), "params": p}
