"""CONT: the ICT / smart-money continuation model as publicly taught (rules + sources: research/lab/CONT_RULES.md).

HTF trend  1H market structure from CLOSED 1H bars built out of the 5m bars (clock hours, anchored at the 18:00 ET open).
           Swing = ICT 3-candle swing, confirmed when the next 1H bar closes. Trend = side of the last 1H close through the
           latest confirmed, unbroken swing (break of structure, BOS).
Leg        impulse leg of the last BOS: origin = extreme between the broken swing and the BOS candle, end = extreme since
           (extends with new highs/lows). EQ = 50 %; longs only from discount, shorts only from premium.
PD array   5m FVGs inside the leg (internal range liquidity); "discount FVG" = consequent encroachment (CE) <= EQ.
Entry      fvg  : resting limit at the CE of the highest untouched discount FVG; fills only on a 1-tick trade-through;
                  stop 2 ticks beyond the FVG's far edge.
           ifvg : pullback low <= EQ and it tapped a discount FVG; the first 5m close through the top of a bearish FVG the
                  pullback left (inversion / change in state of delivery) -> market at that close; stop 2 ticks beyond the
                  pullback swing low.
Target     the leg's old high / low (external range liquidity), limit, 1-tick trade-through; signal skipped if < 2R.
Risk       $350 fixed risk, <= 2 trades/day, stop for the day after a winner or 2 losers, -$700 daily stop, flat 15:55 ET.
Causal     decisions on closed 5m bars only; a 1H bar is used only after its last 5m bar closed; same-bar stop/target ->
           stop first; on a limit-fill bar only the stop can fill; shorts run in mirrored price space (x -> -x).
"""
from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from tools.strategy_lab import make_trade  # noqa: E402

NAME = "continuation"
TICK = 0.25
INF = float("inf")

# Defaults = variant IFVG_AMPM, the best of the 3 tested (research/lab/CONT_REPORT.md). It does NOT clear the lab gate
# (0.3-0.5 trades/wk, avg R ~0, no edge over the zero-edge eval baseline): paper only, not for live.
PARAMS = {
    "sym": "NQ",                       # NQ (MNQ $2/pt) | ES (MES $5/pt)
    "entry": "ifvg",                   # ifvg (5m inversion close, market) | fvg (resting limit at the FVG CE)
    "windows": [[570, 660], [810, 900]],  # entry killzones, ET minutes [start, end) of the 5m bar: 09:30-11:00 + 13:30-15:00
    "htf_min": 60,                     # HTF bar (minutes from the 18:00 ET open): 60 = 1H
    "min_fvg": {"NQ": 3.0, "ES": 0.75},  # points; same noise floor for every variant (NQ ~3.8x ES in points)
    "stop_ticks": 2,                   # stop buffer beyond the swing / FVG edge
    "min_rr": 2.0,                     # target (old high/low) must pay at least this
    "fill_ticks": 1,                   # resting entry limit needs a trade-through of N ticks
    "target_ticks": 1,                 # target limit needs a trade-through of N ticks
    "flat_mod": 955,                   # flat at 15:55 ET (close of the 15:50 bar)
    "max_trades_day": 2,
    "max_losers_day": 2,
    "stop_after_win": True,
    "daily_stop": -700.0,              # realized day P&L at/below this -> no new trades
    "risk_usd": 350.0,
}

VARIANTS = {   # fixed in research/lab/CONT_RULES.md before any test
    "FVG": {"entry": "fvg", "windows": [[570, 660]]},
    "IFVG": {"entry": "ifvg", "windows": [[570, 660]]},
    "IFVG_AMPM": {"entry": "ifvg", "windows": [[570, 660], [810, 900]]},
}


def _params(params):
    p = {**PARAMS}
    params = dict(params or {})
    v = params.pop("variant", None)
    if v:
        p.update(VARIANTS[v])
    p.update(params)
    return p


class _Leg:
    __slots__ = ("d", "lo", "lo_idx", "hi", "hi_idx", "valid", "eq", "fvgs", "disc_top", "pb_lo", "pb_idx", "bears",
                 "bos_t")

    def __init__(self, d):
        self.d = d
        self.valid = True
        self.fvgs = []        # leg FVGs (direction space, bullish): [k, top, bot, ce, touched]
        self.bears = []       # pullback FVGs (direction space, bearish): [k, top, inverted]
        self.pb_lo, self.pb_idx = INF, -1


class _Sim:
    def __init__(self, bars5, p):
        self.p = p
        df = bars5
        o = df["open"].to_numpy(float)
        h = df["high"].to_numpy(float)
        l = df["low"].to_numpy(float)
        c = df["close"].to_numpy(float)
        self.t = df["time"].to_numpy(np.int64)
        self.mod = df["mod"].to_numpy(int)
        self.day = df["day"].to_numpy()
        self.dm = np.where(self.mod >= 1080, self.mod - 1080, self.mod + 360)
        self.n = n = len(c)
        mf = p["min_fvg"][p["sym"]] if isinstance(p["min_fvg"], dict) else float(p["min_fvg"])
        contig = np.zeros(n, bool)
        if n > 2:
            contig[2:] = (self.t[2:] - self.t[:-2]) == 600
        self.D = {}
        for d in (1, -1):
            O, H, L, C = (o, h, l, c) if d == 1 else (-o, -l, -h, -c)
            bull = np.zeros(n, bool)
            bear = np.zeros(n, bool)
            if n > 2:
                bull[2:] = contig[2:] & (L[2:] - H[:-2] >= mf - 1e-9)     # gap: H[k-2] .. L[k]
                bear[2:] = contig[2:] & (L[:-2] - H[2:] >= mf - 1e-9)     # gap: H[k] .. L[k-2]
            self.D[d] = {"O": O, "H": H, "L": L, "C": C, "bull": bull, "bear": bear}
        self.last_of_day = np.r_[self.day[1:] != self.day[:-1], True] if n else np.zeros(0, bool)
        self.flat_dm = int(p["flat_mod"] - 5 - 1080 if p["flat_mod"] - 5 >= 1080 else p["flat_mod"] - 5 + 360)
        self.wins = [tuple(w) for w in p["windows"]]
        # HTF state
        self.hH, self.hL, self.hC, self.hA = [], [], [], []
        self.cur = None           # [key, a, hi, lo, close]
        self.sh = self.sl = None  # [price, htf idx, broken]
        self.trend = 0
        self.leg = None
        # trading state
        self.trades = []
        self.pos = None
        self.order = None         # resting limit for the next bar (fvg entry)
        self.dstate = {"day": None, "n": 0, "losers": 0, "won": False, "pnl": 0.0}
        self.last_signal = None
        self.dbg = {} if p.get("_debug") else None     # condition funnel per killzone day (diagnostics only)
        self.dbg_rr = []

    # ------------------------------------------------------------------------------------------------ HTF structure
    def _htf_key(self, i):
        return (self.day[i], int(self.dm[i]) // int(self.p["htf_min"]))

    def _htf_close(self, now):
        key, a, hi, lo, cl = self.cur
        self.cur = None
        self.hH.append(hi)
        self.hL.append(lo)
        self.hC.append(cl)
        self.hA.append(a)
        k = len(self.hH) - 1
        if k >= 2:
            if self.hH[k - 1] > self.hH[k - 2] and self.hH[k - 1] > self.hH[k]:
                self.sh = [self.hH[k - 1], k - 1, False]
            if self.hL[k - 1] < self.hL[k - 2] and self.hL[k - 1] < self.hL[k]:
                self.sl = [self.hL[k - 1], k - 1, False]
        ck = self.hC[k]
        if self.sh is not None and not self.sh[2] and ck > self.sh[0]:
            self.sh[2] = True
            self.trend = 1
            self.leg = self._new_leg(1, self.hA[self.sh[1] + 1], now)
        elif self.sl is not None and not self.sl[2] and ck < self.sl[0]:
            self.sl[2] = True
            self.trend = -1
            self.leg = self._new_leg(-1, self.hA[self.sl[1] + 1], now)

    def _new_leg(self, d, a5, now):
        D = self.D[d]
        H, L, C = D["H"], D["L"], D["C"]
        g = _Leg(d)
        g.bos_t = int(self.t[now]) + 300
        seg = L[a5:now + 1]
        g.lo_idx = a5 + int(np.argmin(seg))
        g.lo = float(L[g.lo_idx])
        segh = H[g.lo_idx:now + 1]
        g.hi_idx = g.lo_idx + len(segh) - 1 - int(np.argmax(segh[::-1]))   # last bar printing the extreme
        g.hi = float(H[g.hi_idx])
        for k in range(g.lo_idx + 2, g.hi_idx + 1):
            if D["bull"][k]:
                top, bot = float(L[k]), float(H[k - 2])
                ce = (top + bot) / 2
                touched = bool(k < now and L[k + 1:now + 1].min() <= ce)
                g.fvgs.append([k, top, bot, ce, touched])
        if g.hi_idx < now:
            s = L[g.hi_idx + 1:now + 1]
            g.pb_idx = g.hi_idx + 1 + int(np.argmin(s))
            g.pb_lo = float(L[g.pb_idx])
            for k in range(g.hi_idx + 2, now + 1):
                if D["bear"][k]:
                    top = float(L[k - 2])
                    inv = bool(k < now and C[k + 1:now + 1].max() > top)
                    g.bears.append([k, top, inv])
        self._refresh(g)
        return g

    @staticmethod
    def _refresh(g):
        g.eq = (g.hi + g.lo) / 2
        tops = [f[1] for f in g.fvgs if f[3] <= g.eq]
        g.disc_top = max(tops) if tops else -INF

    # ------------------------------------------------------------------------------------------------ 5m leg update
    def _leg_bar(self, i):
        """Update the active leg with bar i. Returns True when a pullback FVG was inverted by bar i's close."""
        g = self.leg
        if g is None or not g.valid:
            return False
        D = self.D[g.d]
        H, L, C = D["H"], D["L"], D["C"]
        if L[i] < g.lo:
            g.valid = False
            return False
        for f in g.fvgs:
            if not f[4] and L[i] <= f[3]:
                f[4] = True
        if H[i] > g.hi:
            old = g.hi_idx
            g.hi, g.hi_idx = float(H[i]), i
            for k in range(max(old + 1, g.lo_idx + 2), i + 1):
                if D["bull"][k]:
                    top, bot = float(L[k]), float(H[k - 2])
                    ce = (top + bot) / 2
                    touched = bool(k < i and L[k + 1:i + 1].min() <= ce)
                    g.fvgs.append([k, top, bot, ce, touched])
            self._refresh(g)
            g.pb_lo, g.pb_idx, g.bears = INF, -1, []
            return False
        if L[i] < g.pb_lo:
            g.pb_lo, g.pb_idx = float(L[i]), i
        inv = False
        for b in g.bears:
            if not b[2] and C[i] > b[1]:
                b[2] = True
                inv = True
        if i - 2 >= g.hi_idx and D["bear"][i]:
            g.bears.append([i, float(L[i - 2]), False])
        return inv

    # ------------------------------------------------------------------------------------------------ helpers
    def _in_win(self, i):
        m = self.mod[i]
        return any(a <= m < b for a, b in self.wins)

    def _day_ok(self):
        s, p = self.dstate, self.p
        return (s["n"] < p["max_trades_day"] and s["losers"] < p["max_losers_day"]
                and not (s["won"] and p["stop_after_win"]) and s["pnl"] > p["daily_stop"])

    def _open(self, i, d, entry_d, stop_d, tgt_d, kind, setup, fill_bar, extra):
        self.pos = {"d": d, "i": i, "entry_d": entry_d, "stop_d": stop_d, "tgt_d": tgt_d, "kind": kind, "setup": setup,
                    "mae": 0.0, "entry_t": int(self.t[i]) + (300 if kind == "market" else 0), "fill_bar": fill_bar,
                    "extra": extra}
        self.dstate["n"] += 1

    def _close(self, i, px_d, how):
        ps = self.pos
        d = ps["d"]
        kind = "market" if how == "open" else how
        tr = make_trade(ps["entry_t"], int(self.t[i]) + 300, d, ps["entry_d"] * d, ps["stop_d"] * d, px_d * d, kind,
                        setup=ps["setup"], mae_pts=ps["mae"], sym=self.p["sym"], risk_usd=self.p["risk_usd"],
                        entry_kind=ps["kind"], target=round(ps["tgt_d"] * d, 2), **ps["extra"])
        if how == "open":
            tr["exit_kind"] = "open"
        self.trades.append(tr)
        s = self.dstate
        s["pnl"] += tr["pnl"]
        if tr["pnl"] > 0:
            s["won"] = True
        else:
            s["losers"] += 1
        self.pos = None

    def _manage(self, i):
        """Stop / target / time exit for an open position on bar i (bars after the entry bar)."""
        ps = self.pos
        D = self.D[ps["d"]]
        O, H, L, C = D["O"], D["H"], D["L"], D["C"]
        if L[i] <= ps["stop_d"]:
            ps["mae"] = max(ps["mae"], ps["entry_d"] - min(O[i], ps["stop_d"]))
            self._close(i, min(O[i], ps["stop_d"]), "stop")
            return True
        ps["mae"] = max(ps["mae"], ps["entry_d"] - L[i])
        if H[i] >= ps["tgt_d"] + self.p["target_ticks"] * TICK:
            self._close(i, ps["tgt_d"], "target")
            return True
        if self.dm[i] >= self.flat_dm or self.last_of_day[i]:
            if i == self.n - 1 and self.dm[i] < self.flat_dm:
                self._close(i, C[i], "open")
            else:
                self._close(i, C[i], "time")
            return True
        return False

    # ------------------------------------------------------------------------------------------------ main loop
    def run(self):
        p = self.p
        st = p["stop_ticks"] * TICK
        for i in range(self.n):
            if self.dstate["day"] != self.day[i]:
                self.dstate = {"day": self.day[i], "n": 0, "losers": 0, "won": False, "pnl": 0.0}
            key = self._htf_key(i)
            if self.cur is not None and self.cur[0] != key:
                self._htf_close(i - 1)
            if self.cur is None:
                self.cur = [key, i, float(self.D[1]["H"][i]), float(self.D[1]["L"][i]), 0.0]
            else:
                self.cur[2] = max(self.cur[2], float(self.D[1]["H"][i]))
                self.cur[3] = min(self.cur[3], float(self.D[1]["L"][i]))
            self.cur[4] = float(self.D[1]["C"][i])
            exited = False
            # ---- resting limit placed at the previous close (fvg entry)
            od = self.order
            self.order = None
            if od is not None and self.pos is None and self._in_win(i) and self.day[i] == od["day"]:
                D = self.D[od["d"]]
                if D["L"][i] <= od["px"] - p["fill_ticks"] * TICK:
                    self._open(i, od["d"], od["px"], od["stop"], od["tgt"], "limit", od["setup"], True, od["extra"])
                    if D["L"][i] <= od["stop"]:                # same bar: stop first, no target on the fill bar
                        self.pos["mae"] = od["px"] - od["stop"]
                        self._close(i, od["stop"], "stop")
                        exited = True
                    else:
                        self.pos["mae"] = max(0.0, od["px"] - D["L"][i])
                        if self.dm[i] >= self.flat_dm or self.last_of_day[i]:
                            self._close(i, D["C"][i], "time")
                            exited = True
            elif self.pos is not None and self.pos["i"] < i:
                exited = self._manage(i)
            # ---- structure / leg updates with bar i (closed)
            g0 = self.leg
            inv = self._leg_bar(i)
            if self.cur is not None and (int(self.dm[i]) + 5) % int(p["htf_min"]) == 0:
                self._htf_close(i)
            if self.leg is not g0:             # a new 1H BOS replaced the leg at this close: no signal from the old one
                inv = False
            # ---- new signals at bar i's close
            g = self.leg
            dbg = self.dbg if self.dbg is not None and self._in_win(i) else None
            if dbg is not None:
                dbg.setdefault(self.day[i], set()).add("kz")
                if g is not None and g.valid:
                    dbg[self.day[i]].add("leg")
                    if g.pb_idx >= 0 and g.pb_lo <= g.eq:
                        dbg[self.day[i]].add("disc")
                        if g.pb_lo <= g.disc_top:
                            dbg[self.day[i]].add("tap")
                            if inv:
                                dbg[self.day[i]].add("inv")
            if exited or self.pos is not None or g is None or not g.valid or not self._day_ok():
                continue
            D = self.D[g.d]
            if p["entry"] == "ifvg":
                if not inv or not self._in_win(i):
                    continue
                if not (g.pb_idx >= 0 and g.pb_lo <= g.eq and g.pb_lo <= g.disc_top):
                    continue
                entry = float(D["C"][i])
                stop = g.pb_lo - st
                risk = entry - stop
                if risk <= 0 or (g.hi - entry) < p["min_rr"] * risk:
                    if dbg is not None:
                        dbg[self.day[i]].add("rr_fail")
                        self.dbg_rr.append({"t": int(self.t[i]), "d": g.d, "lo": g.lo * g.d, "hi": g.hi * g.d,
                                            "pb": g.pb_lo * g.d, "entry": entry * g.d, "risk": risk,
                                            "reward": g.hi - entry, "inv_tops": [b[1] * g.d for b in g.bears if b[2]]})
                    continue
                extra = {"leg_lo": round(g.lo * g.d, 2), "leg_hi": round(g.hi * g.d, 2), "eq": round(g.eq * g.d, 2),
                         "rr_plan": round((g.hi - entry) / risk, 2)}
                self._open(i, g.d, entry, stop, g.hi, "market", f"IFVG {'L' if g.d == 1 else 'S'}", False, extra)
                self.last_signal = {"i": i, "d": g.d}
            else:   # fvg: (re)place the resting limit for bar i+1
                if i + 1 >= self.n or self.day[i + 1] != self.day[i] or not self._in_win(i + 1):
                    continue
                cands = [f for f in g.fvgs if f[3] <= g.eq and not f[4]]
                if not cands:
                    continue
                f = max(cands, key=lambda z: z[3])
                px = round(f[3] / TICK) * TICK if g.d == 1 else -round(-f[3] / TICK) * TICK
                stop = f[2] - st
                risk = px - stop
                if risk <= 0 or (g.hi - px) < p["min_rr"] * risk:
                    continue
                extra = {"leg_lo": round(g.lo * g.d, 2), "leg_hi": round(g.hi * g.d, 2), "eq": round(g.eq * g.d, 2),
                         "rr_plan": round((g.hi - px) / risk, 2), "fvg": [round(f[2] * g.d, 2), round(f[1] * g.d, 2)]}
                self.order = {"d": g.d, "px": px, "stop": stop, "tgt": g.hi, "day": self.day[i],
                              "setup": f"FVG {'L' if g.d == 1 else 'S'}", "extra": extra}
        if self.pos is not None:        # data ended inside the trade
            i = self.n - 1
            self._close(i, float(self.D[self.pos["d"]]["C"][i]), "open")
        return self.trades


def run(bars5, params=None, es5=None):
    """Causal simulation over bars5 (strategy_lab.bars(sym, '5m', ..., warmup_days=...)). es5 is unused (no SMT)."""
    p = _params(params)
    return _Sim(bars5.reset_index(drop=True), p).run()


def state(bars5, params=None, es5=None):
    """Dashboard snapshot at the last bar: HTF trend, leg / EQ, pullback progress, armed order, today's trades."""
    p = _params(params)
    df = bars5.reset_index(drop=True)
    days = df["day"].to_numpy()
    uniq = list(dict.fromkeys(days))
    if len(uniq) > 15:                 # 15 sessions are plenty to rebuild the 1H structure
        df = df[df["day"] >= uniq[-15]].reset_index(drop=True)
    sim = _Sim(df, p)
    trades = sim.run()
    if sim.n == 0:
        return {"model": NAME, "status": "no bars"}
    last = sim.n - 1
    dlabel = sim.day[last]
    g = sim.leg
    side = {1: "long", -1: "short", 0: "none"}
    leg = None
    status = "NO TREND YET"
    if g is not None:
        d = g.d
        leg = {"dir": side[d], "valid": g.valid, "origin": round(g.lo * d, 2), "extreme": round(g.hi * d, 2),
               "eq": round(g.eq * d, 2), "pullback_extreme": None if g.pb_idx < 0 else round(g.pb_lo * d, 2),
               "in_discount": bool(g.pb_idx >= 0 and g.pb_lo <= g.eq),
               "tapped_discount_fvg": bool(g.pb_idx >= 0 and g.pb_lo <= g.disc_top),
               "discount_fvgs": [{"lo": round(min(f[1] * d, f[2] * d), 2), "hi": round(max(f[1] * d, f[2] * d), 2),
                                  "ce": round(f[3] * d, 2), "touched": f[4]} for f in g.fvgs if f[3] <= g.eq],
               "open_pullback_fvgs": [round(b[1] * d, 2) for b in g.bears if not b[2]]}
        if not g.valid:
            status = "LEG VOID - waiting for the next 1H break of structure"
        elif p["entry"] == "ifvg":
            if leg["in_discount"] and leg["tapped_discount_fvg"]:
                status = f"ARMED {side[d]} - waiting for a 5m close through a pullback FVG (IFVG) in the killzone"
            else:
                zone = "discount" if d == 1 else "premium"
                status = f"TREND {side[d]} - waiting for the pullback to reach EQ {leg['eq']} and a {zone} FVG"
        else:
            zone = "discount" if d == 1 else "premium"
            status = f"TREND {side[d]} - limit at the CE of the nearest untouched {zone} FVG during the killzone"
    today = [t for t in trades if t["day"] == dlabel]
    if today and today[-1]["exit_kind"] == "open":
        status = "IN TRADE"
    elif sim.dstate["day"] == dlabel and not sim._day_ok():
        status = "DONE FOR TODAY"
    elif not sim._in_win(last):
        status += " (outside killzone " + ", ".join(f"{a // 60:02d}:{a % 60:02d}-{b // 60:02d}:{b % 60:02d}" for a, b in sim.wins) + " ET)"
    order = None
    if sim.order is not None:
        od = sim.order
        order = {"dir": side[od["d"]], "limit": round(od["px"] * od["d"], 2), "stop": round(od["stop"] * od["d"], 2),
                 "target": round(od["tgt"] * od["d"], 2)}
    return {"model": NAME, "day": dlabel, "status": status, "htf_trend": side[sim.trend], "leg": leg, "order": order,
            "trades_today": today, "last_close": float(sim.D[1]["C"][last]), "params": p}
