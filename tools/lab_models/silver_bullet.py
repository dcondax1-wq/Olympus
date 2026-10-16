"""ICT Silver Bullet, as publicly taught, on 5m NQ / ES futures. Plain-English rules + sources: research/lab/SB_RULES.md.

Window     NY local 10:00-11:00 (AM) and 14:00-15:00 (PM). The 03:00-04:00 London window is part of the teaching but
           is skipped for the bot. The setup FVG must FORM inside the window (displacement candle 2 opens at or after
           the window start, candle 3 closes inside it) and the limit entry must FILL inside the window; once filled
           the trade may run past the window (to target, stop or 15:55 ET).
Liquidity  pools = prior week H/L, prior day H/L, Asia (20:00-00:00) H/L, London (02:00-05:00) H/L, the 09:00-10:00
           hour H/L, the NY AM session (09:30-12:00) H/L (PM window only), and intraday 5m short-term highs/lows
           (3-candle swings, usable once the right-hand candle has closed). A pool is "taken" once price trades 1 tick
           beyond it after it formed.
Setup      a raid of sell-side (buy-side) liquidity -> displacement up (down) that leaves a bullish (bearish) FVG
           (candle 1 high < candle 3 low) -> the draw on liquidity = the nearest untaken opposite-side pool at least
           10 handles (40 ticks) from the entry, and it must pay >= 2R. One attempt per window: the FIRST qualifying
           FVG is the setup; if its order does not fill inside the window there is no trade in that window.
Entry      resting limit at the FVG near edge ("edge") or 50% consequent encroachment ("ce"); fills only when a later
           bar trades 1 tick through it inside the window. Cancelled if price reaches the target first or the window
           ends.
Stop       1 tick beyond FVG candle 1 ("c1", default) or beyond the displacement leg extreme ("swing").
Target     the draw on liquidity ("dol": the pool price, filled only on a 1-tick trade-through) or fixed R ("rr").
Risk       $350 fixed per trade, max 2 trades/day (one per window), stop for the day after a winner or 2 losers,
           daily stop -$700, flat 15:55 ET.

Causal: decisions on closed 5m bars only; the stop is checked first from the fill bar on; no target credit on the fill
bar; same-bar stop/target ambiguity -> stop. Unfinished last trade -> exit_kind 'open'.
"""
from __future__ import annotations

import datetime as dt
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from tools.strategy_lab import make_trade, size  # noqa: E402

NAME = "silver_bullet"
TICK = 0.25

PARAMS = {
    "sym": "NQ",
    "windows": [[600, 660], [840, 900]],   # ET minutes [start, end): 10:00-11:00, 14:00-15:00
    "require_sweep": True,       # the FVG's displacement must follow a raid on opposite-side liquidity
    "sweep_lookback": 12,        # bars: the raid must be at most this many bars (60 min) before FVG candle 1
    "swing_pools": True,         # intraday short-term highs/lows count as liquidity pools
    "swing_n": 1,                # 1 = 3-candle swing (ICT short-term high/low)
    "entry": "edge",             # edge | ce
    "stop": "c1",                # c1 (beyond FVG candle 1) | swing (beyond the displacement leg extreme)
    "stop_ticks": 1,             # stop buffer beyond the reference price
    "target": "dol",             # dol | rr
    "rr": 2.0,                   # R multiple for target "rr"
    "min_tgt_pts": 10.0,         # ICT minimum trade framework: >= 10 handles (40 ticks) of room to the draw
    "min_rr": 2.0,               # the draw must pay at least this many R (community minimum 1:2)
    "min_fvg_ticks": 1,          # minimum gap size
    "target_ticks": 1,           # limit target needs a trade-through of N ticks
    "risk_usd": 350.0,
    "max_trades_day": 2,
    "max_losses_day": 2,
    "stop_after_win": True,
    "daily_stop": -700.0,
    "flat_mod": 955,             # flat at 15:55 ET (close of the 15:50 bar)
}

SESS = {  # name: (start dm, end dm) in minutes after 18:00 ET (dm), [start, end); usable from the end of the range
    "AS": (120, 360),     # Asia 20:00-00:00
    "LO": (480, 660),     # London 02:00-05:00
    "H9": (900, 960),     # 09:00-10:00 hour
    "AM": (930, 1080),    # NY AM 09:30-12:00 (only reachable by the PM window)
}


def _dm(mod):
    return np.where(mod >= 1080, mod - 1080, mod + 360)


def _day_bounds(day):
    cut = np.flatnonzero(day[1:] != day[:-1]) + 1
    starts = np.r_[0, cut]
    ends = np.r_[cut, len(day)]
    return list(zip(day[starts], starts, ends))


def _p(params):
    p = {**PARAMS, **(params or {})}
    m = p["min_tgt_pts"]
    p["_min_tgt"] = float(m.get(p["sym"], 10.0) if isinstance(m, dict) else m)
    return p


def _prior_week(bounds, h, l):
    """{day: (PWH, PWL)} from the previous ISO week's trading days."""
    wk = {}
    for d, a, b in bounds:
        y, w, _ = dt.date.fromisoformat(d).isocalendar()
        hi, lo = float(h[a:b].max()), float(l[a:b].min())
        x = wk.get((y, w))
        wk[(y, w)] = (hi, lo) if x is None else (max(x[0], hi), min(x[1], lo))
    keys = sorted(wk)
    prev = {keys[k]: wk[keys[k - 1]] for k in range(1, len(keys))}
    out = {}
    for d, a, b in bounds:
        y, w, _ = dt.date.fromisoformat(d).isocalendar()
        if (y, w) in prev:
            out[d] = prev[(y, w)]
    return out


class _Pools:
    """Liquidity pools of one trading day. side +1 = buy-side (highs), -1 = sell-side (lows)."""

    def __init__(self):
        self.px, self.side, self.avail, self.name, self.taken = [], [], [], [], []
        self.live = []

    def add(self, name, px, side, avail_i):
        self.live.append(len(self.px))
        self.name.append(name)
        self.px.append(float(px))
        self.side.append(side)
        self.avail.append(avail_i)      # first bar index on which the pool can be traded through
        self.taken.append(False)

    def update(self, i, hi, lo):
        """Mark pools taken by bar i. Returns [(name, px, side)] swept on this bar."""
        out, keep = [], []
        for k in self.live:
            if i >= self.avail[k] and ((self.side[k] == 1 and hi >= self.px[k] + TICK) or
                                       (self.side[k] == -1 and lo <= self.px[k] - TICK)):
                self.taken[k] = True
                out.append((self.name[k], self.px[k], self.side[k]))
            else:
                keep.append(k)
        self.live = keep
        return out

    def draw(self, i, d, entry, min_dist):
        """Nearest untaken pool on side d (+1: highs above for longs) at least min_dist beyond the entry."""
        best = None
        for k in self.live:
            if self.side[k] != d or i < self.avail[k]:
                continue
            dist = (self.px[k] - entry) * d
            if dist >= min_dist and (best is None or dist < best[0]):
                best = (dist, self.px[k], self.name[k])
        return best


def _short(nm):
    return nm[:2] if nm[:2] in ("SH", "SL") else nm


def _sim_day(p, o, h, l, c, t, mod, dm, a, b, prev, pw, n, dlabel, sym, debug=None, live=None):
    wins = [tuple(w) for w in p["windows"]]
    flat_dm = int(_dm(np.array([p["flat_mod"] - 5]))[0])
    pools = _Pools()
    if pw is not None:
        pools.add("PWH", pw[0], 1, a)
        pools.add("PWL", pw[1], -1, a)
    if prev is not None:
        a0, b0 = prev
        pools.add("PDH", h[a0:b0].max(), 1, a)
        pools.add("PDL", l[a0:b0].min(), -1, a)
    seg_dm = dm[a:b]
    for nm, (s, e) in SESS.items():
        m = (seg_dm >= s) & (seg_dm < e)
        after = np.flatnonzero(seg_dm >= e)
        if not m.any() or not len(after):
            continue
        idx = np.flatnonzero(m) + a
        av = a + int(after[0])
        pools.add(nm + "H", h[idx].max(), 1, av)
        pools.add(nm + "L", l[idx].min(), -1, av)
    sweeps = []                 # (bar i, side swept, pool name, pool px)
    trades = []
    pend = None                 # resting limit order
    pos = None
    ntr = nloss = 0
    won = False
    day_pnl = 0.0
    used_win = set()            # windows whose one attempt has been used (armed)
    mn = p["min_fvg_ticks"] * TICK
    sn = int(p["swing_n"])

    def book(tr):
        nonlocal ntr, nloss, won, day_pnl
        trades.append(tr)
        ntr += 1
        day_pnl += tr["pnl"]
        if tr["pnl"] > 0:
            won = True
        else:
            nloss += 1

    for i in range(a, b):
        mi, di = mod[i], dm[i]
        # ---- short-term highs/lows whose right-hand candle closed at bar i-1 become pools from bar i
        if p["swing_pools"] and i - 1 - 2 * sn >= a:
            m_ = i - 1 - sn
            if h[m_] > h[m_ - sn:m_].max() and h[m_] > h[m_ + 1:m_ + 1 + sn].max():
                pools.add(f"SH{m_ - a}", h[m_], 1, i)
            if l[m_] < l[m_ - sn:m_].min() and l[m_] < l[m_ + 1:m_ + 1 + sn].min():
                pools.add(f"SL{m_ - a}", l[m_], -1, i)
        win = next((w for w in wins if w[0] <= mi < w[1]), None)
        # ---- 1) open position: stop first, then target, then time
        if pos is not None and i > pos["fill_i"]:
            d = pos["d"]
            hi_d, lo_d = (h[i], l[i]) if d == 1 else (-l[i], -h[i])
            ex = None
            if lo_d <= pos["stop_d"]:
                ex = (min(o[i] * d, pos["stop_d"]), "stop")
            elif hi_d >= pos["tgt_d"] + p["target_ticks"] * TICK:
                ex = (pos["tgt_d"], "target")
            elif di >= flat_dm or i == b - 1:
                ex = (c[i] * d, "time")
            pos["mae"] = max(pos["mae"], min(pos["entry_d"] - lo_d, pos["entry_d"] - pos["stop_d"]))
            if ex is not None:
                kind = ex[1]
                is_open = kind == "time" and i == n - 1 and di < flat_dm
                tr = make_trade(t[pos["fill_i"]], t[i] + 300, d, pos["entry"], pos["stop"], ex[0] * d,
                                "market" if is_open else kind, setup=pos["setup"], mae_pts=max(pos["mae"], 0.0),
                                sym=sym, risk_usd=p["risk_usd"], entry_kind="limit", target=pos["tgt"],
                                fvg=pos["fvg"], window=pos["window"])
                if is_open:
                    tr["exit_kind"] = "open"
                book(tr)
                pos = None
        # ---- liquidity raids on this bar
        for nm, px, side in pools.update(i, h[i], l[i]):
            sweeps.append((i, side, nm, px))
        allowed = (ntr < p["max_trades_day"] and nloss < p["max_losses_day"] and not (won and p["stop_after_win"])
                   and day_pnl > p["daily_stop"])
        # ---- 2) resting limit order
        if pend is not None:
            d = pend["d"]
            if win is None or tuple(win) != pend["window"] or not allowed or pos is not None:
                pend = None                                    # window over -> cancel
            else:
                hi_d, lo_d = (h[i], l[i]) if d == 1 else (-l[i], -h[i])
                if lo_d <= pend["entry_d"] - TICK:             # traded through -> filled at the limit
                    pos = {"d": d, "fill_i": i, "entry": pend["entry"], "stop": pend["stop"], "tgt": pend["tgt"],
                           "entry_d": pend["entry_d"], "stop_d": pend["stop"] * d, "tgt_d": pend["tgt"] * d,
                           "mae": 0.0, "setup": pend["setup"], "fvg": pend["fvg"], "window": f"{win[0]}"}
                    pend = None
                    if lo_d <= pos["stop_d"]:                  # stopped on the fill bar (stop first, no target credit)
                        book(make_trade(t[i], t[i] + 300, d, pos["entry"], pos["stop"], pos["stop"], "stop",
                                        setup=pos["setup"], mae_pts=abs(pos["entry"] - pos["stop"]), sym=sym,
                                        risk_usd=p["risk_usd"], entry_kind="limit", target=pos["tgt"],
                                        fvg=pos["fvg"], window=pos["window"]))
                        pos = None
                    else:
                        pos["mae"] = max(0.0, pos["entry_d"] - lo_d)
                elif hi_d >= pend["tgt_d"]:                    # ran to the draw without us -> cancel
                    pend = None
        # ---- 3) new setup: FVG completed by bar i (candles i-2, i-1, i) inside the window
        allowed = (ntr < p["max_trades_day"] and nloss < p["max_losses_day"] and not (won and p["stop_after_win"])
                   and day_pnl > p["daily_stop"])
        if (win is None or pend is not None or pos is not None or not allowed or tuple(win) in used_win
                or i - 2 < a or mod[i - 1] < win[0]):
            continue
        for d in (1, -1):
            if d == 1:
                bot, top = h[i - 2], l[i]
                edge = top
            else:
                bot, top = h[i], l[i - 2]
                edge = bot
            if top - bot < mn:
                continue
            sw_name = "nosweep"
            if p["require_sweep"]:
                cand = [s for s in sweeps if s[1] == -d and i - 2 - p["sweep_lookback"] <= s[0] <= i - 2]
                if not cand:
                    continue
                s0 = cand[0][0]
                sw_name = "+".join(sorted({_short(s[2]) for s in cand}))
                rng = np.arange(s0, i + 1)
            else:
                rng = np.arange(max(a, i - 2 - p["sweep_lookback"]), i + 1)
            leg_ext_i = int(rng[np.argmin(l[rng])]) if d == 1 else int(rng[np.argmax(h[rng])])
            leg_ext = float(l[leg_ext_i] if d == 1 else h[leg_ext_i])
            if p["require_sweep"] and leg_ext_i > i - 2:
                continue                                       # the leg extreme came after candle 1: not a displacement off the raid
            entry = float(edge if p["entry"] == "edge" else round((top + bot) / 2 / TICK) * TICK)
            ref = (l[i - 2] if d == 1 else h[i - 2]) if p["stop"] == "c1" else leg_ext
            stop = float(ref - d * p["stop_ticks"] * TICK)
            risk = (entry - stop) * d
            if risk <= 0 or size(risk, p["risk_usd"], sym) < 1:
                continue                                       # stop too wide for 1 micro at the fixed risk
            dol = pools.draw(i + 1, d, entry, p["_min_tgt"])
            if dol is None or dol[0] < p["min_rr"] * risk:
                continue                                       # no draw on liquidity with enough room
            tgt = float(dol[1]) if p["target"] == "dol" else entry + d * p["rr"] * risk
            pend = {"d": d, "entry": entry, "entry_d": entry * d, "stop": stop, "tgt": tgt, "tgt_d": tgt * d,
                    "window": tuple(win), "fvg": [float(bot), float(top)],
                    "setup": f"{'L' if d == 1 else 'S'}:{sw_name}>{_short(dol[2])}"}
            used_win.add(tuple(win))
            if debug is not None:
                debug.append({"day": dlabel, "i": i, "d": d, "fvg": [bot, top], "entry": entry, "stop": stop,
                              "tgt": tgt, "dol": dol, "sweep": sw_name})
            break
    if live is not None:
        live.update({"pend": pend, "pos": pos, "ntr": ntr, "won": won, "nloss": nloss, "day_pnl": day_pnl,
                     "used_win": sorted(used_win),
                     "pools": [(pools.name[k], pools.px[k], pools.side[k]) for k in pools.live
                               if not pools.name[k].startswith(("SH", "SL"))]})
    return trades


def _arrays(df):
    return (df["open"].to_numpy(float), df["high"].to_numpy(float), df["low"].to_numpy(float),
            df["close"].to_numpy(float), df["time"].to_numpy(np.int64), df["mod"].to_numpy(int), df["day"].to_numpy())


def run(bars5, params=None, es5=None, _debug=None):
    p = _p(params)
    o, h, l, c, t, mod, day = _arrays(bars5)
    dm = _dm(mod)
    n = len(c)
    bounds = _day_bounds(day)
    pw = _prior_week(bounds, h, l)
    trades = []
    for k, (dlabel, a, b) in enumerate(bounds):
        if k == 0:
            continue
        prev = (bounds[k - 1][1], bounds[k - 1][2])
        trades += _sim_day(p, o, h, l, c, t, mod, dm, a, b, prev, pw.get(dlabel), n, dlabel, p["sym"], _debug)
    return trades


def state(bars5, params=None, es5=None):
    """Dashboard snapshot for the latest trading day: untaken pools, armed order, open trade, what it waits for."""
    p = _p(params)
    o, h, l, c, t, mod, day = _arrays(bars5)
    dm = _dm(mod)
    bounds = _day_bounds(day)
    if len(bounds) < 2:
        return {"model": NAME, "status": "not enough bars"}
    dlabel, a, b = bounds[-1]
    prev = (bounds[-2][1], bounds[-2][2])
    pw = _prior_week(bounds, h, l).get(dlabel)
    live = {}
    today = _sim_day(p, o, h, l, c, t, mod, dm, a, b, prev, pw, len(c), dlabel, p["sym"], None, live)
    mi = int(mod[b - 1])
    wins = [tuple(w) for w in p["windows"]]
    in_win = next((w for w in wins if w[0] <= mi < w[1]), None)
    if live.get("pos") is not None or (today and today[-1]["exit_kind"] == "open"):
        status = "IN TRADE"
    elif live.get("pend") is not None:
        status = "LIMIT ARMED at the FVG"
    elif (live["ntr"] >= p["max_trades_day"] or live["nloss"] >= p["max_losses_day"] or
          (live["won"] and p["stop_after_win"]) or live["day_pnl"] <= p["daily_stop"]):
        status = "DONE FOR TODAY"
    elif in_win and tuple(in_win) in [tuple(w) for w in live["used_win"]]:
        status = "WINDOW ATTEMPT USED - waiting for the next window"
    elif in_win:
        status = "SILVER BULLET WINDOW - waiting for a liquidity raid + displacement FVG toward an untaken pool"
    else:
        status = "OUTSIDE WINDOW (" + ", ".join(f"{w[0] // 60:02d}:{w[0] % 60:02d}-{w[1] // 60:02d}:{w[1] % 60:02d}" for w in wins) + " ET)"
    pend = live.get("pend")
    return {"model": NAME, "sym": p["sym"], "day": dlabel, "status": status,
            "armed": None if pend is None else {k: pend[k] for k in ("d", "entry", "stop", "tgt", "fvg", "setup")},
            "untaken_pools": [{"name": nm, "price": px, "side": "buy-side" if sd == 1 else "sell-side"}
                              for nm, px, sd in live["pools"]],
            "trades_today": today, "day_pnl": round(live["day_pnl"], 2), "last_close": float(c[b - 1]),
            "params": {k: v for k, v in p.items() if not k.startswith("_")}}
