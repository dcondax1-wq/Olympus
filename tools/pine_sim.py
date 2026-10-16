"""Bar-by-bar Python replica of tradingview/liquidity_engine.pine, including TradingView's broker emulator.

    python -X utf8 tools/pine_sim.py data/tv_mnq_5m_2026-10-16.csv --parity     # current script vs engine.backtest
    python -X utf8 tools/pine_sim.py data/tv_mnq_5m_2026-10-16.csv --legacy     # the script TradingView ran before 2026-10-16
    python -X utf8 tools/pine_sim.py [bars.csv] [--from D --to D] [--no-news] [--no-roll] [--debug]

Why: TradingView only loads ~8 weeks of history and its Strategy Tester is slow to iterate on, so every Pine change is
first checked here against the TradingView trade list (Strategy Tester) and against engine/model.py (tools/pine_parity.py).
The code mirrors the Pine script statement by statement; keep the two in sync. Results: research/PINE_PARITY.md.

Bars: a TradingView chart export (time, open, high, low, close, Volume - unadjusted MNQ1!, exactly what the Pine script
sees; roll gaps then come from data/NQ_rolls.json, as the script reads them from the back-adjusted symbol) or, with no
csv, data/NQ_5m.csv (back-adjusted NQ, what the Python engine sees; no roll shift needed).

Broker emulation (TradingView settings used by the script): market entries fill at the next bar open +/- slippage
(1 tick); strategy.exit stop/limit are checked intrabar along open->high->low->close when the open is nearer the high,
else open->low->high->close; a stop fills at its price (or the open on a gap) +/- slippage; a limit needs a 1-tick
trade-through (backtest_fill_limits_assumption=1) and fills at its price (or the open on a gap); commission $0.75 per
contract per fill; rule exits use strategy.close_all(immediately=true) and fill at the bar close -/+ 1 tick.

--legacy reproduces the pre-parity script (commit fdaea88) as TradingView actually ran it - its 1H/15m structure never
updated there - including next-open rule exits: 8 trades, +$547.50 on the 2026-10-16 export, exactly TradingView's list.
"""
from __future__ import annotations

import argparse
import datetime as dt
import math
import os
import sys
from zoneinfo import ZoneInfo

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

ET = ZoneInfo("America/New_York")
DAY = 86400000

DEFAULT_INPUTS = {
    "riskUsd": 350.0, "gradeSizing": True, "convStep": 0.33, "maxQty": 40, "maxTrades": 2, "stopAfterWin": True,
    "dayStop": 600.0, "ddAware": True, "cushionFrac": 0.25, "mllAmt": 2000.0, "mllLock": 50100.0, "regimeEr": 0.45,
    "regimeMode": "half", "dayRangeMax": 1.6, "gEarly": 2, "gQ3": 1, "gPd": 2,
    "minFvg": 3.0, "minStop": 10.0, "maxStop": 60.0, "stopBuf": 2.0, "eqTol": 6.0, "minRR": 1.5, "maxRR": 5.0,
    "fallbackRR": 2.0, "beAtR": 1.0, "timeStopM": 30, "givebackR": 0.5, "minScore": 1, "expiryMin": 60, "legLook": 24,
    "flatMod": 955, "newsOn": True, "newsBefore": 15, "newsAfter": 30, "newsFlatM": 5, "fomcPmOff": True,
    # parity fixes (all off with legacy=True, which reproduces the script TradingView ran before 2026-10-16)
    "fixStruct": True,           # 1H/15m structure actually updates (the UDT/method version never did on TradingView)
    "fixRetire": True,           # retire stale pools before adding the prior-day / prior-week pools (engine order)
    "fixSwingBorn": True,        # swing pools are born at the 1H/15m candle close (engine t0), not the 5m bar open
    "rollAdjust": True,          # shift stored price levels by the roll gap when the continuous contract rolls
    "fillOnClose": True,         # rule exits fill at this close (close_all immediately=true), are managed before entries
                                 #   (same-bar re-entry), flatten on the session's last bar, realized day P&L
}
TICK = 0.25
PV = 2.0           # MNQ $/pt (syminfo.pointvalue)
COMM = 0.75        # per contract per fill
SLIP = 1           # ticks
CAPITAL = 50000.0


# ------------------------------------------------------------------------------------------------ bars
class Series:
    def __init__(self, t, o, h, l, c, v):
        self.t = np.asarray(t, dtype=np.int64) * 1000          # ms, like Pine `time`
        self.o, self.h, self.l, self.c = (np.asarray(x, dtype=float) for x in (o, h, l, c))
        self.v = np.asarray(v, dtype=float)
        n = len(self.t)
        self.mod = np.zeros(n, dtype=np.int64)
        self.date = np.zeros(n, dtype=np.int64)
        self.week = np.zeros(n, dtype=np.int64)
        self.tdate = [""] * n
        for i in range(n):
            e = dt.datetime.fromtimestamp(self.t[i] / 1000, ET)
            self.mod[i] = e.hour * 60 + e.minute
            self.date[i] = e.year * 10000 + e.month * 100 + e.day
            w = e + dt.timedelta(hours=6)
            iso = w.isocalendar()
            self.week[i] = iso[0] * 100 + iso[1]
            self.tdate[i] = w.strftime("%Y-%m-%d")

    def __len__(self):
        return len(self.t)


def load_csv(path, day_from=None, day_to=None):
    import csv
    rows = list(csv.DictReader(open(path, encoding="utf-8-sig")))
    vk = next((k for k in rows[0] if k.lower() == "volume"), None)
    t, o, h, l, c, v = [], [], [], [], [], []
    for r in rows:
        t.append(int(float(r["time"]))); o.append(float(r["open"])); h.append(float(r["high"])); l.append(float(r["low"]))
        c.append(float(r["close"])); v.append(float(r[vk] or 0) if vk else 0.0)
    s = Series(t, o, h, l, c, v)
    return _cut(s, day_from, day_to)


def load_engine(sym="NQ", day_from=None, day_to=None):
    from engine.data import load
    b = load(sym, "5m")
    s = Series(b.t, b.o, b.h, b.l, b.c, b.v)
    return _cut(s, day_from, day_to)


def _cut(s, day_from, day_to):
    idx = [i for i, d in enumerate(s.tdate) if (not day_from or d >= day_from) and (not day_to or d <= day_to)]
    if not idx:
        raise ValueError("no bars in range")
    a, b = idx[0], idx[-1] + 1
    out = Series.__new__(Series)
    for k in ("t", "o", "h", "l", "c", "v", "mod", "date", "week"):
        setattr(out, k, getattr(s, k)[a:b])
    out.tdate = s.tdate[a:b]
    return out


# ------------------------------------------------------------------------------------------------ HTF structure
class Struct:
    def __init__(self):
        self.h, self.l = [], []
        self.sh = self.shMin = self.sl = self.slMax = None
        self.trend = 0
        self.protL = self.protH = self.lsh = self.lsl = None
        self.newH = self.newL = None

    def step(self, bh, bl, bc):
        self.h.append(bh); self.l.append(bl)
        if len(self.h) > 13:
            self.h.pop(0); self.l.pop(0)
        n = len(self.h)
        if self.shMin is not None:
            self.shMin = min(self.shMin, bl)
        if self.slMax is not None:
            self.slMax = max(self.slMax, bh)
        if n >= 5:
            hk, lk = self.h[n - 3], self.l[n - 3]
            if hk > max(self.h[n - 5], self.h[n - 4]) and hk >= max(self.h[n - 2], self.h[n - 1]):
                self.sh = hk; self.lsh = hk; self.newH = hk
                self.shMin = min(lk, min(self.l[n - 2], self.l[n - 1]))
            if lk < min(self.l[n - 5], self.l[n - 4]) and lk <= min(self.l[n - 2], self.l[n - 1]):
                self.sl = lk; self.lsl = lk; self.newL = lk
                self.slMax = max(hk, max(self.h[n - 2], self.h[n - 1]))
        if self.sh is not None and bc > self.sh:
            self.protL = self.shMin; self.trend = 1; self.sh = None; self.shMin = None
        elif self.sl is not None and bc < self.sl:
            self.protH = self.slMax; self.trend = -1; self.sl = None; self.slMax = None
        if self.trend == 1 and self.protL is not None and bc < self.protL:
            self.trend = -1; self.protH = max(self.h)
        elif self.trend == -1 and self.protH is not None and bc > self.protH:
            self.trend = 1; self.protL = min(self.l)

    def shift(self, g):
        """Roll adjustment: move every stored price by the roll gap."""
        self.h = [x + g for x in self.h]; self.l = [x + g for x in self.l]
        for k in ("sh", "shMin", "sl", "slMax", "protL", "protH", "lsh", "lsl"):
            v = getattr(self, k)
            if v is not None:
                setattr(self, k, v + g)


class Agg:
    def __init__(self):
        self.b = None; self.h = self.l = self.c = None; self.done = True

    def feed(self, s, ms, t, h, l, c):
        s.newH = None; s.newL = None
        bk = t // ms
        if self.b is None or bk != self.b:
            if self.b is not None and not self.done:
                s.step(self.h, self.l, self.c)
            self.b = bk; self.h, self.l, self.c = h, l, c; self.done = False
        else:
            self.h = max(self.h, h); self.l = min(self.l, l); self.c = c
        if (t + 300000) % ms == 0:
            s.step(self.h, self.l, self.c)
            self.done = True


# ------------------------------------------------------------------------------------------------ simulation
def simulate(S: Series, inputs: dict | None = None, legacy=False, news=None, debug=False, roll_gaps=None, snap_times=()):
    """Run the Pine logic over Series S. news: list of (epoch_s, label) or None (= the Pine default: empty list).
    roll_gaps: {bar_time_s: gap_pts} roll adjustments (new contract - old contract at the switch bar)."""
    P = dict(DEFAULT_INPUTS)
    if legacy:
        P.update(fixStruct=False, fixRetire=False, fixSwingBorn=False, rollAdjust=False, fillOnClose=False)
    P.update(inputs or {})
    n = len(S)
    T, O, H, L, C, V, MOD = S.t, S.o, S.h, S.l, S.c, S.v, S.mod
    tick = TICK
    pools = []           # dicts: px side major swing str eqOk born life

    def add_pool(px, side, major, swing, strength, eqOk, life, checkEq, t):
        # t = birth time; swing pools are born at the 1H / 15m candle close (engine Structure pools: t0 = HTF close)
        idx = None
        for q in pools:
            if q["side"] == side and abs(q["px"] - px) < tick / 2:
                idx = q
                if major:
                    q["major"] = True
                if strength > q["str"]:
                    q["str"] = strength; q["swing"] = swing; q["eqOk"] = eqOk; q["life"] = life
                break
        if idx is None:
            idx = {"px": px, "side": side, "major": major, "swing": swing, "str": strength, "eqOk": eqOk, "born": t, "life": life}
            pools.append(idx)
        if checkEq:
            for q in pools:
                if q is not idx and q["side"] == side and q["eqOk"]:
                    dd = abs(q["px"] - idx["px"])
                    if tick / 2 <= dd <= P["eqTol"]:
                        q["major"] = True; idx["major"] = True
        return idx

    s1h, s15 = Struct(), Struct()
    g1h, g15 = Agg(), Agg()
    st = dict(dHi=None, dLo=None, wHi=None, wLo=None, asH=None, asL=None, asPub=False, loH=None, loL=None, loPub=False,
              onH=None, onL=None, onPub=False, curWeek=None, tradesToday=0, dayStartEq=0.0, dayStartNet=0.0, wonToday=False, vwPV=0.0, vwV=0.0,
              adr20=None, trending=False, peakEod=CAPITAL, mllLvl=CAPITAL - P["mllAmt"])
    dRanges, dCloses = [], []
    qOpen = [None] * 7
    # setups
    A = {1: dict(armed=False, ext=None, extTime=0, extBar=0, armMod=0, vavg=None, vrun=0.0, vmax=0.0),
         -1: dict(armed=False, ext=None, extTime=0, extBar=0, armMod=0, vavg=None, vrun=0.0, vmax=0.0)}
    # broker
    pos = 0              # signed qty
    avg = 0.0
    netprofit = 0.0
    trades = []          # closed trades
    cur = None           # open trade record
    pend_entry = None    # (dir, qty, stop, target, comment)
    pend_close = None    # reason
    bracket = None       # dict(stop, limit) for the open position (active orders)
    tr = dict(stop=None, tgt=None, entry=None, risk=None, bar=0, mfe=0.0)
    lastTrades = 0
    events = [] if debug else None
    news = sorted(news or [])
    ev_t = [int(t) * 1000 for t, _ in news]
    ev_date = [int(dt.datetime.fromtimestamp(t, ET).strftime("%Y%m%d")) for t, _ in news]
    ev_fomc = ["FOMC" in lab.upper() for _, lab in news]
    roll_gaps = roll_gaps or {}
    snap_times = set(snap_times or ())
    vol_sma = np.full(n, np.nan)
    if n > 20:
        cs = np.concatenate([[0.0], np.cumsum(V)])
        for i in range(19, n):
            vol_sma[i] = (cs[i + 1] - cs[i - 19]) / 20.0

    def close_pos(i, px, reason, t):
        nonlocal pos, avg, netprofit, cur, bracket
        d = 1 if pos > 0 else -1
        q = abs(pos)
        pnl = (px - avg) * d * q * PV - COMM * q * 2
        netprofit += pnl
        cur.update({"exit_t": t // 1000, "exit": px, "exit_signal": reason, "profit": round(pnl, 2), "exit_bar": i})
        trades.append(cur)
        cur = None; pos = 0; avg = 0.0; bracket = None

    for i in range(n):
        t, o, h, l, c, v, mod = int(T[i]), O[i], H[i], L[i], C[i], V[i], int(MOD[i])
        # ============================ broker: orders placed on the previous bar fill on this bar
        if pend_close is not None and pos != 0:
            d = 1 if pos > 0 else -1
            close_pos(i, o - d * SLIP * tick, pend_close, t)
        pend_close = None
        if pend_entry is not None and pos == 0:
            d, q, stp, tgt, cmt = pend_entry
            fill = o + d * SLIP * tick
            pos = d * q; avg = fill
            cur = {"dir": d, "qty": q, "entry_t": t // 1000, "entry": fill, "entry_signal": cmt, "entry_bar": i}
            bracket = {"stop": stp, "limit": tgt}
        pend_entry = None
        if pos != 0 and bracket is not None:
            d = 1 if pos > 0 else -1
            stp, lim = bracket["stop"], bracket["limit"]
            high_first = (h - o) <= (o - l)
            hit = None
            # gap at the open
            if (o - stp) * d <= 0:
                hit = ("STOP", o - d * SLIP * tick)
            elif (o - lim) * d >= tick:
                hit = ("TARGET", o)
            else:
                legs = ["h", "l"] if high_first else ["l", "h"]
                for leg in legs:
                    px = h if leg == "h" else l
                    fav = (leg == "h") == (d == 1)
                    if fav and (px - lim) * d >= tick:
                        hit = ("TARGET", lim); break
                    if not fav and (px - stp) * d <= 0:
                        hit = ("STOP", stp - d * SLIP * tick); break
            if hit:
                close_pos(i, hit[1], hit[0], t)

        # ============================ script (runs at the bar close)
        mod1 = int(MOD[i - 1]) if i > 0 else 0
        gapMs = t - (int(T[i - 1]) if i > 0 else t)
        newDay = (mod >= 1080 and (mod1 < 1080 or gapMs > 6 * 3600000)) or (mod < 1080 and gapMs > 4 * 3600000)
        inKZ = (570 <= mod < 690) or (810 <= mod < 930)
        canArm = 480 <= mod < P["flatMod"]
        curDate = int(S.date[i])
        equity = CAPITAL + netprofit + ((c - avg) * pos * PV if pos != 0 else 0.0)

        # roll: shift stored levels into the new contract's prices
        rollD = 0.0
        if P["rollAdjust"] and (t // 1000) in roll_gaps:
            g = roll_gaps[t // 1000]
            rollD = g
            for q in pools:
                q["px"] += g
            for k in ("dHi", "dLo", "wHi", "wLo", "asH", "asL", "loH", "loL", "onH", "onL"):
                if st[k] is not None:
                    st[k] += g
            for k in range(len(dCloses)):
                dCloses[k] += g
            s1h.shift(g); s15.shift(g)
            for ag in (g1h, g15):
                if ag.h is not None:
                    ag.h += g; ag.l += g; ag.c += g
            for d_ in (1, -1):
                if A[d_]["ext"] is not None:
                    A[d_]["ext"] += g

        if newDay and P["fixRetire"]:
            # retire stale pools BEFORE the new prior-day / prior-week pools are added (engine order)
            for q in list(pools)[::-1]:
                if t - q["born"] > q["life"]:
                    pools.remove(q)
        if newDay:
            if st["dHi"] is not None:
                dRanges.append(st["dHi"] - st["dLo"])
                dCloses.append(C[i - 1] + rollD)
                balEod = CAPITAL + netprofit
                st["peakEod"] = max(st["peakEod"], balEod)
                st["mllLvl"] = min(max(st["mllLvl"], st["peakEod"] - P["mllAmt"]), P["mllLock"])
                if h <= st["dHi"]:
                    add_pool(st["dHi"], 1, True, False, 2, True, int(2.2 * DAY), False, t)
                if l >= st["dLo"]:
                    add_pool(st["dLo"], -1, True, False, 2, True, int(2.2 * DAY), False, t)
            nR = len(dRanges)
            if nR > 0:
                cnt = min(20, nR)
                st["adr20"] = sum(dRanges[nR - cnt:]) / cnt
            st["trending"] = False
            nC = len(dCloses)
            if P["regimeEr"] > 0 and nC >= 11:
                path = sum(abs(dCloses[k] - dCloses[k - 1]) for k in range(nC - 10, nC))
                if path > 0:
                    st["trending"] = abs(dCloses[nC - 1] - dCloses[nC - 11]) / path > P["regimeEr"]
            wk = int(S.week[i])
            if st["curWeek"] is not None and wk != st["curWeek"] and st["wHi"] is not None:
                add_pool(st["wHi"], 1, True, False, 3, False, 5 * DAY, False, t)
                add_pool(st["wLo"], -1, True, False, 3, False, 5 * DAY, False, t)
                st["wHi"] = None; st["wLo"] = None
            st["curWeek"] = wk
            st["dHi"], st["dLo"] = h, l
            for k in ("asH", "asL", "loH", "loL", "onH", "onL"):
                st[k] = None
            st["asPub"] = st["loPub"] = st["onPub"] = False
            st["tradesToday"] = 0
            st["dayStartEq"] = equity
            st["dayStartNet"] = netprofit
            st["wonToday"] = False
            qOpen = [None] * 7
            if not P["fixRetire"]:
                for q in list(pools)[::-1]:
                    if t - q["born"] > q["life"]:
                        pools.remove(q)
        else:
            st["dHi"] = max(h if st["dHi"] is None else st["dHi"], h)
            st["dLo"] = min(l if st["dLo"] is None else st["dLo"], l)
        st["wHi"] = max(h if st["wHi"] is None else st["wHi"], h)
        st["wLo"] = min(l if st["wLo"] is None else st["wLo"], l)

        if not P["fixStruct"]:
            # what TradingView actually ran: the UDT-method structure never took effect (trend 0, no swings)
            s1h.newH = s1h.newL = s15.newH = s15.newL = None
        else:
            g1h.feed(s1h, 3600000, t, h, l, c)
            g15.feed(s15, 900000, t, h, l, c)
        tb = t + 300000 if P["fixSwingBorn"] else t
        if s1h.newH is not None:
            add_pool(s1h.newH, 1, True, True, 2, True, 5 * DAY, True, tb)
        if s1h.newL is not None:
            add_pool(s1h.newL, -1, True, True, 2, True, 5 * DAY, True, tb)
        if s15.newH is not None:
            add_pool(s15.newH, 1, False, True, 1, True, int(1.2 * DAY), True, tb)
        if s15.newL is not None:
            add_pool(s15.newL, -1, False, True, 1, True, int(1.2 * DAY), True, tb)

        if 380 <= mod <= 920 and (mod - 380) % 90 == 0:
            qOpen[(mod - 380) // 90] = o

        if mod == 570 or (mod >= 570 and mod1 < 570):
            st["vwPV"] = 0.0; st["vwV"] = 0.0
        if 570 <= mod < 960:
            vv = v if v > 0 else 1.0
            st["vwPV"] += (h + l + c) / 3 * vv; st["vwV"] += vv
        vwap = st["vwPV"] / st["vwV"] if st["vwV"] > 0 else None

        if mod >= 1200:
            st["asH"] = max(h if st["asH"] is None else st["asH"], h); st["asL"] = min(l if st["asL"] is None else st["asL"], l)
        elif st["asH"] is not None and not st["asPub"] and mod < 1080:
            st["asPub"] = True
            add_pool(st["asH"], 1, True, False, 1, True, int(2.2 * DAY), True, t)
            add_pool(st["asL"], -1, True, False, 1, True, int(2.2 * DAY), True, t)
        if 120 <= mod < 300:
            st["loH"] = max(h if st["loH"] is None else st["loH"], h); st["loL"] = min(l if st["loL"] is None else st["loL"], l)
        elif st["loH"] is not None and not st["loPub"] and 300 <= mod < 1080:
            st["loPub"] = True
            add_pool(st["loH"], 1, True, False, 2, True, int(2.2 * DAY), True, t)
            add_pool(st["loL"], -1, True, False, 2, True, int(2.2 * DAY), True, t)
        if mod >= 1080 or mod < 570:
            st["onH"] = max(h if st["onH"] is None else st["onH"], h); st["onL"] = min(l if st["onL"] is None else st["onL"], l)
        elif st["onH"] is not None and not st["onPub"] and 570 <= mod < 1080:
            st["onPub"] = True
            add_pool(st["onH"], 1, True, False, 2, True, int(2.2 * DAY), False, t)
            add_pool(st["onL"], -1, True, False, 2, True, int(2.2 * DAY), False, t)

        def news_block():
            blk = False
            if P["newsOn"]:
                for k in range(len(ev_t)):
                    if t - P["newsAfter"] * 60000 <= ev_t[k] <= t + P["newsBefore"] * 60000:
                        blk = True
                    if P["fomcPmOff"] and ev_fomc[k] and ev_date[k] == curDate and mod >= 780:
                        blk = True
            return blk

        def news_soon():
            if not (P["newsOn"] and P["newsFlatM"] > 0):
                return False
            tc = t + 300000
            return any(tc < e <= tc + P["newsFlatM"] * 60000 for e in ev_t)

        # ---- sweeps
        vAvg20 = vol_sma[i - 1] if i >= 1 else np.nan
        if newDay:
            A[1]["armed"] = False; A[-1]["armed"] = False
        for d_ in (1, -1):
            if A[d_]["armed"]:
                A[d_]["vrun"] = max(A[d_]["vrun"], v)
        for q in list(pools)[::-1]:
            px, sd = q["px"], q["side"]
            hitp = (sd == -1 and l <= px - tick) or (sd == 1 and h >= px + tick)
            if hitp:
                d_ = 1 if sd == -1 else -1
                a = A[d_]
                if canArm and not a["armed"]:
                    a.update(armed=True, ext=(l if d_ == 1 else h), extTime=t, extBar=i, armMod=mod, vavg=vAvg20, vrun=v, vmax=v)
                    if debug:
                        events.append((t // 1000, "arm", d_, px, q["str"], q["major"]))
                pools.remove(q)
        for d_ in (1, -1):
            a = A[d_]
            if a["armed"] and ((l < a["ext"]) if d_ == 1 else (h > a["ext"])):
                a.update(ext=(l if d_ == 1 else h), extTime=t, extBar=i, vmax=a["vrun"])
        for d_ in (1, -1):
            if A[d_]["armed"] and t - A[d_]["extTime"] > P["expiryMin"] * 60000:
                A[d_]["armed"] = False

        # ---- manage the open position: exits at this close (fixed script: before entries, like the engine)
        def manage():
            nonlocal pend_close
            closed = False
            if pos != 0 and cur is not None and cur["entry_bar"] == i:
                tr["entry"] = avg; tr["risk"] = abs(avg - tr["stop"]); tr["bar"] = i; tr["mfe"] = 0.0
            if pos != 0:
                d = 1 if pos > 0 else -1
                fav = (h - tr["entry"]) if d == 1 else (tr["entry"] - l)
                tr["mfe"] = max(tr["mfe"], fav / tr["risk"] if tr["risk"] > 0 else 0)
                reason = ""
                lastbar = P["fillOnClose"] and i + 1 < n and S.tdate[i + 1] != S.tdate[i]     # session.islastbar
                if mod >= P["flatMod"] or lastbar:
                    reason = "FLAT"
                elif news_soon():
                    reason = "NEWS FLAT"
                elif P["timeStopM"] > 0 and (i - tr["bar"] + 1) * 300 >= P["timeStopM"] * 60 and tr["mfe"] < 0.5:
                    reason = "TIME STOP"
                elif P["givebackR"] > 0 and tr["mfe"] >= P["givebackR"] and (c - tr["entry"]) * d < 0:
                    reason = "GIVEBACK"
                if reason:
                    if P["fillOnClose"]:
                        close_pos(i, c - d * SLIP * tick, reason, t)      # strategy.close_all(immediately=true)
                        closed = True
                    else:
                        pend_close = reason
                elif P["beAtR"] > 0 and tr["mfe"] >= P["beAtR"]:
                    newStop = max(tr["stop"], tr["entry"] + tick) if d == 1 else min(tr["stop"], tr["entry"] - tick)
                    if newStop != tr["stop"]:
                        tr["stop"] = newStop
            if pos != 0 and bracket is not None:
                bracket["stop"] = tr["stop"]; bracket["limit"] = tr["tgt"]
            return closed

        if P["fillOnClose"]:
            manage()
        if len(trades) > lastTrades:
            if trades[-1]["profit"] > 0:
                st["wonToday"] = True
            lastTrades = len(trades)
        # realized P&L today (fixed script) / equity-based (legacy)
        dayPnl = (netprofit - st["dayStartNet"]) if P["fillOnClose"] else (equity - st["dayStartEq"])
        bal = CAPITAL + netprofit
        blocked = st["tradesToday"] >= P["maxTrades"] or dayPnl <= -P["dayStop"] or (P["stopAfterWin"] and st["wonToday"])
        flat = pos == 0
        rangeBlock = P["dayRangeMax"] > 0 and len(dRanges) >= 5 and st["adr20"] and (st["dHi"] - st["dLo"]) / st["adr20"] >= P["dayRangeMax"]
        entryBlock = news_block() or rangeBlock or (st["trending"] and P["regimeMode"] == "skip")

        def trig(d_, extOff):
            # direction-space: d=1 uses (H, L, O, C) as is; d=-1 mirrors
            hh = (lambda j: H[i - j]) if d_ == 1 else (lambda j: -L[i - j])
            ll = (lambda j: L[i - j]) if d_ == 1 else (lambda j: -H[i - j])
            oo = (lambda j: O[i - j] * d_)
            cc = (lambda j: C[i - j] * d_)
            legOff = extOff
            best = hh(extOff)
            for j in range(extOff, extOff + P["legLook"] + 1):
                if i - j < 0:
                    break
                if hh(j) >= best:
                    best = hh(j); legOff = j
            bestTop, inv, hasGap = None, None, False
            if legOff >= 3:
                for j in range(legOff - 2, 0, -1):
                    gTop, gBot = ll(j + 2), hh(j)
                    if gTop - gBot >= P["minFvg"]:
                        hasGap = True
                        if cc(0) > gTop and oo(0) < cc(0):
                            first = all(not (cc(q_) > gTop) for q_ in range(j - 1, 0, -1))
                            if first and (bestTop is None or gTop < bestTop):
                                bestTop = gTop
                                inv = min(ll(j), ll(j + 1), ll(j + 2))
            if bestTop is not None:
                return True, inv * d_, "IFVG"
            if not hasGap:
                f = extOff
                if cc(extOff) < oo(extOff):
                    while f + 1 < legOff and cc(f + 1) < oo(f + 1):
                        f += 1
                lvl = oo(f)
                if cc(0) > lvl and oo(0) < cc(0):
                    first = all(not (cc(q_) > lvl) for q_ in range(extOff - 1, 0, -1))
                    if first:
                        return True, ll(extOff) * d_, "CISD"
            return False, None, None

        def q90(m):
            if 360 <= m < 720:
                q = (m - 360) // 90 + 1
                return q, 360 + (q - 1) * 90
            if 720 <= m < 1080:
                q = (m - 720) // 90 + 1
                return q, 720 + (q - 1) * 90
            return 0, None

        def plan(d_, ext, invX, armMod, climax):
            entry = c
            stop = ext - d_ * P["stopBuf"]
            risk = (entry - stop) * d_
            if risk < P["minStop"]:
                stop = entry - d_ * P["minStop"]; risk = P["minStop"]
            if risk > P["maxStop"]:
                alt = invX - d_ * P["stopBuf"] if invX is not None else None
                altRisk = (entry - alt) * d_ if alt is not None else None
                if alt is not None and P["minStop"] <= altRisk <= P["maxStop"]:
                    stop, risk = alt, altRisk
                else:
                    risk = -1.0
            if risk <= 0:
                return None
            best = None
            for q in pools:
                if q["side"] == d_ and q["major"] and (q["px"] - entry) * d_ >= P["minRR"] * risk:
                    if best is None or (q["px"] - entry) * d_ < (best - entry) * d_:
                        best = q["px"]
            if best is None:
                target = entry + d_ * P["fallbackRR"] * risk
            else:
                target = entry + d_ * P["maxRR"] * risk if (best - entry) * d_ > P["maxRR"] * risk else best - d_ * tick
            htf = s1h.trend
            score = (1 if htf == d_ else -1 if htf == -d_ else 0)
            pdv = 0
            if s1h.lsh is not None and s1h.lsl is not None and s1h.lsh > s1h.lsl:
                ppos = (ext - s1h.lsl) / (s1h.lsh - s1h.lsl)
                pdv = 1 if ((d_ == 1 and ppos <= 0.5) or (d_ == -1 and ppos >= 0.5)) else -1
            score += 1 if pdv > 0 else 0
            obst = sum(1 for q in pools if q["side"] == d_ and q["swing"] and (q["px"] - entry) * d_ > 0 and (q["px"] - target) * d_ < 0)
            lrl, hrl = obst <= 1, obst >= 3
            score += 1 if lrl else -1 if hrl else 0
            m15al = s15.trend == d_
            score += -1 if m15al else 0
            vw = 0 if vwap is None else (1 if (vwap - entry) * d_ > 0 else -1)
            firstHour = 570 <= mod < 630
            comp = {"htf": (2 if htf == d_ else -1 if htf == -d_ else 0), "pd": P["gPd"] * pdv, "vwap": 2 * vw,
                    "climax": -2 if climax else 0, "lrl": 1 if lrl else -2 if hrl else 0, "first_hour": -1 if firstHour else 0,
                    "m15": -1 if m15al else 0}
            sQ, _ = q90(armMod)
            eQ, eQs = q90(mod)
            comp["q2"] = 1 if sQ == 2 else 0
            comp["q90open"] = 0
            if eQs is not None:
                qi = (eQs - 360) // 90
                if 0 <= qi <= 6 and qOpen[qi] is not None:
                    comp["q90open"] = 1 if (qOpen[qi] - ext) * d_ > 0 else -1
            comp["stretched"] = -1 if (st["adr20"] and (st["dHi"] - st["dLo"]) / st["adr20"] >= 1.2) else 0
            sessStart = 570 if mod < 720 else 810
            comp["early"] = -P["gEarly"] if mod - sessStart < 45 else 0
            comp["q3"] = -P["gQ3"] if eQ == 3 else 0
            pts = sum(comp.values())
            mult = 1.5 if pts >= 7 else 1.25 if pts >= 5 else 1.0 if pts >= 3 else 0.75 if pts >= 1 else 0.5
            grade = "A+" if pts >= 7 else "A" if pts >= 5 else "B" if pts >= 3 else "C" if pts >= 1 else "D"
            riskEff = P["riskUsd"]
            if P["ddAware"]:
                riskEff = min(riskEff, max(0.0, (bal - st["mllLvl"]) * P["cushionFrac"]))
            if P["gradeSizing"]:
                riskEff *= mult
            if st["trending"] and P["regimeMode"] == "half":
                riskEff *= 0.5
            qty = min(P["maxQty"], int(math.floor(riskEff / (risk * PV))))
            return dict(stop=stop, target=target, score=score, qty=qty, grade=grade, pts=pts, risk=risk, comp=comp,
                        trending=st["trending"], obst=obst, htf=htf, m15=s15.trend)

        if debug and (t // 1000) in snap_times:
            events.append((t // 1000, "snap", {"flat": flat, "blocked": bool(blocked), "tradesToday": st["tradesToday"],
                                               "won": st["wonToday"], "inKZ": inKZ, "entryBlock": bool(entryBlock),
                                               "armed": {1: A[1]["armed"], -1: A[-1]["armed"]}, "pools": len(pools),
                                               "trend1h": s1h.trend, "trend15": s15.trend}))
        if flat and inKZ and mod < P["flatMod"] - 10 and not blocked:
            for d_ in (1, -1):
                a = A[d_]
                if not a["armed"]:
                    continue
                ok, inv, ttype = trig(d_, i - a["extBar"])
                if not ok:
                    continue
                climax = (a["vavg"] is not None and not np.isnan(a["vavg"]) and a["vavg"] > 0 and a["vmax"] >= 1.5 * a["vavg"])
                pl = plan(d_, a["ext"], inv, a["armMod"], climax)
                if debug:
                    events.append((t // 1000, "cand", d_, ttype, None if pl is None else {k: pl[k] for k in ("score", "qty", "grade", "pts", "risk", "comp", "trending", "obst")},
                                   bool(entryBlock)))
                if pl is None:
                    a["armed"] = False
                elif not entryBlock and pl["score"] >= P["minScore"]:
                    if pl["qty"] < 1:
                        a["armed"] = False
                    else:
                        pend_entry = (d_, pl["qty"], pl["stop"], pl["target"], (f"{'L' if d_ == 1 else 'S'} r={pl['risk']:.2f} g={pl['grade']}" if legacy else
                                     f"{'L' if d_ == 1 else 'S'} r={pl['risk']:.2f} sl={pl['stop']:.2f} g={pl['grade']}"))
                        tr["stop"], tr["tgt"] = pl["stop"], pl["target"]
                        st["tradesToday"] += 1
                        A[1]["armed"] = False; A[-1]["armed"] = False
                        break

        if not P["fillOnClose"]:
            manage()

    return {"trades": trades, "events": events, "netprofit": round(netprofit, 2)}


# ------------------------------------------------------------------------------------------------ CLI
def fmt(ts):
    return dt.datetime.fromtimestamp(ts, ET).strftime("%Y-%m-%d %H:%M")


def roll_gaps_from_engine(sym="NQ"):
    """{switch bar time (s): gap pts} from data/<sym>_rolls.json - the same rolls the engine's back-adjusted bars use."""
    import json
    path = os.path.join(ROOT, "data", f"{sym}_rolls.json")
    if not os.path.exists(path):
        return {}
    return {int(r["switch_t"]): float(r["gap"]) for r in json.load(open(path, encoding="utf-8"))["rolls"] if r.get("gap") is not None}


def engine_news():
    from engine import news as _n
    return [(int(e["t"]), e["event"]) for e in _n.historical_events(("high",))]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv", nargs="?")
    ap.add_argument("--from", dest="day_from")
    ap.add_argument("--to", dest="day_to")
    ap.add_argument("--legacy", action="store_true", help="the script as TradingView ran it before the parity fix")
    ap.add_argument("--no-news", action="store_true", help="empty news list (default: the engine's high-impact calendar)")
    ap.add_argument("--no-roll", action="store_true", help="no roll adjustment")
    ap.add_argument("--parity", action="store_true", help="diff against engine.backtest (tools/pine_parity.py)")
    ap.add_argument("--debug", action="store_true")
    a = ap.parse_args()
    S = load_csv(a.csv, a.day_from, a.day_to) if a.csv else load_engine("NQ", a.day_from, a.day_to)
    news = None if (a.legacy or a.no_news) else engine_news()
    gaps = {} if (a.no_roll or not a.csv) else roll_gaps_from_engine("NQ")
    r = simulate(S, legacy=a.legacy, news=news, debug=a.debug, roll_gaps=gaps)
    for x in r["trades"]:
        print(f"{fmt(x['entry_t'])} {'L' if x['dir'] == 1 else 'S'} {x['entry_signal']:18} q={x['qty']:<3} {x['entry']:.2f} -> "
              f"{fmt(x['exit_t'])} {x['exit_signal']:10} {x['exit']:.2f}  {x['profit']:+.2f}")
    print(f"{len(r['trades'])} trades, net {r['netprofit']:+.2f}")
    if a.debug:
        for e in r["events"]:
            if e[1] == "cand":
                print(fmt(e[0]), e[1:])
    if a.parity:
        import re
        import pine_parity as pp
        tv = []
        for x in r["trades"]:
            m = re.search(r"sl=([0-9.]+)", x["entry_signal"])
            m2 = re.search(r"r=([0-9.]+)", x["entry_signal"])
            tv.append({**x, "risk_pts": abs(x["entry"] - float(m.group(1))) if m else (float(m2.group(1)) if m2 else None)})
        pp.compare(pp.py_trades(), tv, day_from=a.day_from or S.tdate[0], day_to=a.day_to or S.tdate[-1])


if __name__ == "__main__":
    main()
