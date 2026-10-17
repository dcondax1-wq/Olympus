"""Bar-by-bar Python replica of tradingview/liquidity_engine.pine, including TradingView's broker emulator.

    python -X utf8 tools/pine_sim.py data/tv_mnq_5m_2026-10-16.csv --parity      # locked strategy vs engine (live_model.json)
    python -X utf8 tools/pine_sim.py --parity                                    # same on the engine's own 5-year NQ bars
    python -X utf8 tools/pine_sim.py data/tv_mnq_5m_2026-10-16.csv --alerts      # every alert message (bridge JSON)
    python -X utf8 tools/pine_sim.py data/tv_mnq_5m_2026-10-16.csv --alerts --set alertFmt="Phone text"
    python -X utf8 tools/pine_sim.py data/tv_mnq_5m_2026-10-16.csv --preset oct16   # the 2026-10-16 script (25 trades)
    python -X utf8 tools/pine_sim.py data/tv_mnq_5m_2026-10-16.csv --legacy      # the script TradingView ran before 2026-10-16
    python -X utf8 tools/pine_sim.py [bars.csv] [--from D --to D] [--no-news] [--no-roll] [--debug] [--json out.json]

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

Presets (--preset): locked (default: the script as of 2026-10-17 = live_model.json), prev (the repo script of 2026-10-16
evening: $350, cushion cap, 1 trade/day, fallback targets), oct16 (the script TradingView matched on 2026-10-16: $350 x
grade, 2 trades/day; 25 trades, +$8,784.50 on the export), legacy (commit fdaea88 as TradingView actually ran it - its
1H/15m structure never updated there - with next-open rule exits: 8 trades, +$547.50).
"""
from __future__ import annotations

import argparse
import bisect
import datetime as dt
import json
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
    # Risk and size (the locked strategy: live_model.json)
    "riskUsd": 800.0, "refStop": 20.0, "maxQty": 40, "maxTrades": 1, "stopAfterWin": True, "dayStop": 600.0,
    "regimeEr": 0.45, "regimeMode": "half", "dayRangeMax": 1.6,
    # cold-streak filter (engine/equity_filter.py with live_model.json equity_filter)
    "coldOn": True, "coldLook": 15, "coldMinR": 0.0, "coldMult": 0.5, "coldForce": "Auto",
    # old rules (off in the locked strategy)
    "gradeSizing": False, "convStep": 0.0, "ddAware": False, "cushionFrac": 0.25, "mllAmt": 2000.0, "mllLock": 50100.0,
    "useFallback": False, "fallbackRR": 2.0, "gEarly": 2, "gQ3": 1, "gPd": 2,
    # model
    "minFvg": 3.0, "minStop": 10.0, "maxStop": 60.0, "stopBuf": 2.0, "eqTol": 6.0, "minRR": 1.5, "maxRR": 5.0,
    "beAtR": 1.0, "timeStopM": 30, "givebackR": 0.5, "minScore": 1, "expiryMin": 60, "legLook": 24,
    "flatMod": 955, "newsOn": True, "newsBefore": 15, "newsAfter": 30, "newsFlatM": 5, "fomcPmOff": True,
    # alerts
    "alertFmt": "Bridge JSON", "bridge": "TradersPost", "bTicker": "MNQ", "syncExits": True, "beModify": True,
    "pmtToken": "", "pmtAccount": "",
    # parity fixes (all off with legacy=True, which reproduces the script TradingView ran before 2026-10-16)
    "fixStruct": True,           # 1H/15m structure actually updates (the UDT/method version never did on TradingView)
    "fixRetire": True,           # retire stale pools before adding the prior-day / prior-week pools (engine order)
    "fixSwingBorn": True,        # swing pools are born at the 1H/15m candle close (engine t0), not the 5m bar open
    "rollAdjust": True,          # shift stored price levels by the roll gap when the continuous contract rolls
    "fillOnClose": True,         # rule exits fill at this close (close_all immediately=true), are managed before entries
                                 #   (same-bar re-entry), flatten on the session's last bar, realized day P&L
    # replica-only research switch (not a Pine input): commission inside the cold-streak R. "tv" = the trade's own net
    # result on TradingView ($0.75 per contract per fill, what the script does); "py" = the engine's mini/micro split
    "coldRComm": "tv",
}
_OLD = {"riskUsd": 350.0, "refStop": 0.0, "coldOn": False, "ddAware": True, "useFallback": True}
PRESETS = {
    "locked": {},
    "prev": dict(_OLD),                                                          # repo script 2026-10-16 23:21 (d007e59)
    "oct16": {**_OLD, "gradeSizing": True, "convStep": 0.33, "maxTrades": 2},    # TradingView parity run (ab027f1)
    "legacy": {**_OLD, "gradeSizing": True, "convStep": 0.33, "maxTrades": 2,    # fdaea88 as TradingView ran it
               "fixStruct": False, "fixRetire": False, "fixSwingBorn": False, "rollAdjust": False, "fillOnClose": False},
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


def unadjust(S, roll_gaps):
    """The unadjusted continuous contract (what a TradingView MNQ1!/NQ1! chart shows) from back-adjusted bars: every bar
    before a roll's switch bar loses that roll's gap (data/NQ_rolls.json: back-adjusted = unadjusted + later gaps)."""
    out = Series.__new__(Series)
    for k in ("t", "v", "mod", "date", "week"):
        setattr(out, k, getattr(S, k))
    out.tdate = S.tdate
    ts = S.t // 1000
    adj = np.zeros(len(ts))
    for sw, g in roll_gaps.items():
        adj[ts < sw] += g
    for k in ("o", "h", "l", "c"):
        setattr(out, k, getattr(S, k) - adj)
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


# ------------------------------------------------------------------------------------------------ alert messages
# Same strings as the Pine functions f_num / f_px / f_usd / f_entryMsg / f_exitMsg / f_bracketMsg / f_beMsg.
def _mintick(x):
    return round(x / TICK) * TICK


def f_num(x):            # str.tostring(math.round_to_mintick(x), "#.##")
    return f"{_mintick(x):.2f}".rstrip("0").rstrip(".")


def f_px(x):             # str.tostring(math.round_to_mintick(x), "#,##0.00")
    return f"{_mintick(x):,.2f}"


def f_usd(x):            # "$" + str.tostring(math.round(x), "#,##0")
    return "$" + f"{int(math.floor(x + 0.5)):,}"


def _g(x):               # str.tostring(<number>) with the default format
    return f"{x:.10f}".rstrip("0").rstrip(".") if isinstance(x, float) else str(x)


class Msg:
    def __init__(self, P):
        self.P = P

    def pos(self, d, q):
        return f"{'LONG' if d == 1 else 'SHORT'} {q} {self.P['bTicker']}"

    def pmt(self, data, q, px, sl, tp, upd_sl, t_close_ms):
        P = self.P
        date = dt.datetime.fromtimestamp(t_close_ms / 1000, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        return ('{"symbol":"' + P["bTicker"] + '","date":"' + date + '","data":"' + data + '","quantity":' + str(q)
                + ',"risk_percentage":0,"price":' + f_num(px) + ',"tp":' + f_num(tp)
                + ',"percentage_tp":0,"dollar_tp":0,"sl":' + f_num(sl) + ',"dollar_sl":0,"percentage_sl":0,"trail":0,"trail_stop":0,"trail_trigger":0,"trail_freq":0'
                + ',"update_tp":false,"update_sl":' + ("true" if upd_sl else "false") + ',"token":"' + P["pmtToken"] + '","pyramid":false,"same_direction_ignore":true'
                + ',"reverse_order_close":false' + (',"full_closed":true' if data == "close" else "") + ',"account_id":"' + P["pmtAccount"] + '"}')

    def entry(self, d, q, st, tp, close, risk_d, note, t_close_ms):
        P = self.P
        if P["alertFmt"] == "Phone text":
            return f"{self.pos(d, q)} at market · stop {f_px(st)} · target {f_px(tp)} · risk {f_usd(risk_d)}{note}"
        if P["bridge"] == "TradersPost":
            return ('{"ticker":"' + P["bTicker"] + '","action":"' + ("buy" if d == 1 else "sell") + '","quantity":' + str(q)
                    + ',"orderType":"market","signalPrice":' + f_num(close) + ',"stopLoss":{"type":"stop","stopPrice":' + f_num(st)
                    + '},"takeProfit":{"limitPrice":' + f_num(tp) + '}}')
        return self.pmt("buy" if d == 1 else "sell", q, close, st, tp, False, t_close_ms)

    def why(self, reason):
        P = self.P
        return {"TIME STOP": f"time stop: not +0.5R after {P['timeStopM']} min",
                "GIVEBACK": f"giveback: was +{_g(float(P['givebackR']))}R, closed back through the entry",
                "FLAT": "end of day: be flat by 15:55",
                "NEWS FLAT": f"high-impact news in {P['newsFlatM']} min"}.get(reason, reason)

    def exit(self, reason, d, q, close, t_close_ms):
        P = self.P
        if P["alertFmt"] == "Phone text":
            return f"CLOSE {self.pos(d, q)} at market · {self.why(reason)}"
        if P["bridge"] == "TradersPost":
            return ('{"ticker":"' + P["bTicker"] + '","action":"exit","orderType":"market","cancel":true,"extras":{"reason":"'
                    + reason + '"}}')
        return self.pmt("close", q, close, 0.0, 0.0, False, t_close_ms)

    def bracket(self, is_target, d, q, st, tp, entry_px, close, t_close_ms):
        if self.P["alertFmt"] == "Phone text":
            be_stop = entry_px is not None and (st - entry_px) * d > 0
            head = "TARGET HIT" if is_target else ("BREAKEVEN STOP HIT" if be_stop else "STOP HIT")
            return f"{head} · {self.pos(d, q)} closed at {f_px(tp if is_target else st)} · check your broker: flat, no orders left"
        return self.exit("bracket", d, q, close, t_close_ms)

    def be(self, d, q, new_stop, tgt, close, t_close_ms):
        P = self.P
        if P["alertFmt"] == "Phone text":
            return f"MOVE STOP to {f_px(new_stop)} (breakeven) · {self.pos(d, q)} · target {f_px(tgt)} stays"
        if P["bridge"] == "TradersPost":
            return '{"ticker":"' + P["bTicker"] + '","action":"breakeven","orderType":"stop"}'
        return self.pmt("buy" if d == 1 else "sell", q, close, new_stop, tgt, True, t_close_ms)

    @staticmethod
    def size_note(cold, trend_half):
        return (" · half size (cold streak)" if cold else "") + (" · half size (trending market)" if trend_half else "")


# ------------------------------------------------------------------------------------------------ simulation
def simulate(S: Series, inputs: dict | None = None, legacy=False, news=None, debug=False, roll_gaps=None, snap_times=(),
             preset="locked"):
    """Run the Pine logic over Series S. news: list of (epoch_s, label) or None (= the Pine default: empty list).
    roll_gaps: {bar_time_s: gap_pts} roll adjustments (new contract - old contract at the switch bar).
    Returns trades (closed, TradingView's view: entry/exit/qty/profit + the plan), alerts (time_s, kind, message) and net."""
    P = dict(DEFAULT_INPUTS)
    P.update(PRESETS["legacy" if legacy else preset])
    P.update(inputs or {})
    n = len(S)
    T, O, H, L, C, V, MOD = S.t, S.o, S.h, S.l, S.c, S.v, S.mod
    tick = TICK
    pools = []           # dicts: px side major swing str eqOk born life
    M = Msg(P)

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
    pend_entry = None    # (dir, qty, stop, target, comment, info, entry message)
    pend_close = None    # reason
    bracket = None       # dict(stop, limit, msg_target, msg_stop) for the open position (active orders)
    tr = dict(stop=None, stop0=None, tgt=None, entry=None, risk=None, bar=0, mfe=0.0, beSent=False)
    lastTrades = 0
    coldR = []           # R of every closed trade, oldest first (Pine: coldR)
    alerts = []          # (time_s the alert fires, kind, message)
    events = [] if debug else None
    news = sorted(news or [])
    ev_t = [int(t) * 1000 for t, _ in news]
    ev_date = [int(dt.datetime.fromtimestamp(t, ET).strftime("%Y%m%d")) for t, _ in news]
    ev_fomc = ["FOMC" in lab.upper() for _, lab in news]
    fomc_dates = {ev_date[k] for k in range(len(ev_t)) if ev_fomc[k]}
    roll_gaps = roll_gaps or {}
    snap_times = set(snap_times or ())
    vol_sma = np.full(n, np.nan)
    if n > 20:
        cs = np.concatenate([[0.0], np.cumsum(V)])
        for i in range(19, n):
            vol_sma[i] = (cs[i + 1] - cs[i - 19]) / 20.0

    def trade_r(rec, px, pnl):
        """The cold-streak R of a closed trade (Pine f_tradeR): net result / (fill to the stop at entry x qty x $/pt)."""
        risk = abs(rec["entry"] - rec["stop0"])
        q = rec["qty"]
        if risk <= 0 or q <= 0:
            return 0.0
        if P["coldRComm"] == "py":
            qf = rec["qty_full"]
            gross = (px - rec["entry"]) * rec["dir"] * qf * PV
            comm = (qf // 10) * 4.5 + (qf % 10) * 1.5
            return round((gross - comm) / (risk * qf * PV), 3)
        return round(pnl / (risk * q * PV), 3)

    def close_pos(i, px, reason, t, msg=None, alert_t=None):
        nonlocal pos, avg, netprofit, cur, bracket
        d = 1 if pos > 0 else -1
        q = abs(pos)
        pnl = (px - avg) * d * q * PV - COMM * q * 2
        netprofit += pnl
        cur.update({"exit_t": t // 1000, "exit": px, "exit_signal": reason, "profit": round(pnl, 2), "exit_bar": i})
        cur["r"] = trade_r(cur, px, pnl)
        coldR.append(cur["r"])
        trades.append(cur)
        if msg is not None:
            alerts.append(((alert_t or t) // 1000, reason, msg))
        cur = None; pos = 0; avg = 0.0; bracket = None

    for i in range(n):
        t, o, h, l, c, v, mod = int(T[i]), O[i], H[i], L[i], C[i], V[i], int(MOD[i])
        t_close = t + 300000
        # ============================ broker: orders placed on the previous bar fill on this bar
        if pend_close is not None and pos != 0:
            d = 1 if pos > 0 else -1
            close_pos(i, o - d * SLIP * tick, pend_close, t)
        pend_close = None
        if pend_entry is not None and pos == 0:
            d, q, stp, tgt, cmt, info, emsg = pend_entry
            fill = o + d * SLIP * tick
            pos = d * q; avg = fill
            cur = {"dir": d, "qty": q, "entry_t": t // 1000, "entry": fill, "entry_signal": cmt, "entry_bar": i, **info}
            bracket = {"stop": stp, "limit": tgt, "msgs": info.pop("_bracket_msgs")}
            cur.pop("_bracket_msgs", None)
            alerts.append((t // 1000, "ENTRY", emsg))
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
                mt, ms = bracket["msgs"]
                close_pos(i, hit[1], hit[0], t, (mt if hit[0] == "TARGET" else ms) if P["syncExits"] else None)

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
            st["vwPV"] += st["vwV"] * g

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
            # Pine f_newsBlock loops over every release; same result with a binary search over the sorted times
            if not P["newsOn"]:
                return False
            k = bisect.bisect_left(ev_t, t - P["newsAfter"] * 60000)
            if k < len(ev_t) and ev_t[k] <= t + P["newsBefore"] * 60000:
                return True
            return bool(P["fomcPmOff"] and mod >= 780 and curDate in fomc_dates)

        def news_soon():
            if not (P["newsOn"] and P["newsFlatM"] > 0):
                return False
            tc = t + 300000
            k = bisect.bisect_right(ev_t, tc)
            return k < len(ev_t) and ev_t[k] <= tc + P["newsFlatM"] * 60000

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
                tr["entry"] = avg; tr["risk"] = abs(avg - tr["stop0"]); tr["bar"] = i; tr["mfe"] = 0.0
            if pos != 0:
                d = 1 if pos > 0 else -1
                qx = abs(pos)
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
                        # strategy.close_all(immediately=true): fills at this close
                        close_pos(i, c - d * SLIP * tick, reason, t, M.exit(reason, d, qx, c, t_close), alert_t=t_close)
                        closed = True
                    else:
                        pend_close = reason
                else:
                    if P["beAtR"] > 0 and tr["mfe"] >= P["beAtR"]:
                        newStop = max(tr["stop"], tr["entry"] + tick) if d == 1 else min(tr["stop"], tr["entry"] - tick)
                        if newStop != tr["stop"]:
                            tr["stop"] = newStop
                            if P["beModify"] and not tr["beSent"]:
                                tr["beSent"] = True
                                alerts.append((t_close // 1000, "BREAKEVEN", M.be(d, qx, newStop, tr["tgt"], c, t_close)))
                    if bracket is not None:
                        bracket["msgs"] = (M.bracket(True, d, qx, tr["stop"], tr["tgt"], tr["entry"], c, t_close),
                                           M.bracket(False, d, qx, tr["stop"], tr["tgt"], tr["entry"], c, t_close))
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
        trendHalf = st["trending"] and P["regimeMode"] == "half"
        # ---- cold-streak filter: sum of the last coldLook closed-trade R values (Pine f_coldState)
        lastR = coldR[-P["coldLook"]:] if P["coldLook"] > 0 else []
        coldSum = round(sum(lastR), 2)
        coldN = len(lastR)
        coldNow = P["coldOn"] and (P["coldForce"] == "Always cold" or
                                   (P["coldForce"] == "Auto" and coldN >= P["coldLook"] and coldSum <= P["coldMinR"]))

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

        def size(riskPts, gradeMult, conv, cold):
            """Pine f_size: Engine._size in the engine's order, then the cold-streak cut. Returns (qty, qtyFull)."""
            riskEff = P["riskUsd"]
            if P["ddAware"]:                                   # old: cap at a fraction of the MLL cushion
                riskEff = min(riskEff, max(0.0, (bal - st["mllLvl"]) * P["cushionFrac"]))
            if P["gradeSizing"]:                               # old: A+..D grade multiplier
                riskEff = riskEff * gradeMult
            elif P["convStep"] > 0:                            # old: conviction multiplier
                riskEff = riskEff * max(0.5, min(1.5, 1 + P["convStep"] * conv))
            if P["refStop"] > 0 and riskPts > P["refStop"]:    # wide stop: risk x refStop / stop
                riskEff = riskEff * (P["refStop"] / riskPts)
            if st["trending"] and P["regimeMode"] == "half":   # trending regime: half size
                riskEff = riskEff * 0.5
            qtyFull = min(P["maxQty"], int(math.floor(riskEff / (riskPts * PV))))
            qty = qtyFull
            if cold and qtyFull >= 1:                          # cold streak: micros x coldMult, at least 1
                qty = max(1, int(qtyFull * P["coldMult"]))
            return qty, qtyFull

        def plan(d_, ext, invX, armMod, climax, cold):
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
                return None                                    # stop too wide: setup consumed
            best = None
            for q in pools:
                if q["side"] == d_ and q["major"] and (q["px"] - entry) * d_ >= P["minRR"] * risk:
                    if best is None or (q["px"] - entry) * d_ < (best - entry) * d_:
                        best = q["px"]
            if best is None:
                if not P["useFallback"]:
                    return None                                # no major pool in range: no trade, setup consumed
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
            conv = (1 if vw > 0 else 0) - (1 if climax else 0) - (1 if firstHour else 0)
            qty, qtyFull = size(risk, mult, conv, cold)
            return dict(stop=stop, target=target, score=score, qty=qty, qtyFull=qtyFull, grade=grade, pts=pts, risk=risk,
                        comp=comp, trending=st["trending"], obst=obst, htf=htf, m15=s15.trend)

        if debug and (t // 1000) in snap_times:
            events.append((t // 1000, "snap", {"flat": flat, "blocked": bool(blocked), "tradesToday": st["tradesToday"],
                                               "won": st["wonToday"], "inKZ": inKZ, "entryBlock": bool(entryBlock),
                                               "armed": {1: A[1]["armed"], -1: A[-1]["armed"]}, "pools": len(pools),
                                               "trend1h": s1h.trend, "trend15": s15.trend, "coldSum": coldSum, "coldN": coldN}))
        if flat and inKZ and mod < P["flatMod"] - 10 and not blocked:
            for d_ in (1, -1):
                a = A[d_]
                if not a["armed"]:
                    continue
                ok, inv, ttype = trig(d_, i - a["extBar"])
                if not ok:
                    continue
                climax = (a["vavg"] is not None and not np.isnan(a["vavg"]) and a["vavg"] > 0 and a["vmax"] >= 1.5 * a["vavg"])
                pl = plan(d_, a["ext"], inv, a["armMod"], climax, coldNow)
                if debug:
                    events.append((t // 1000, "cand", d_, ttype, None if pl is None else {k: pl[k] for k in ("score", "qty", "qtyFull", "grade", "pts", "risk", "comp", "trending", "obst")},
                                   bool(entryBlock)))
                if pl is None:
                    a["armed"] = False
                elif not entryBlock and pl["score"] >= P["minScore"]:
                    if pl["qty"] < 1:
                        a["armed"] = False
                    else:
                        q = pl["qty"]
                        cmt = (f"{'L' if d_ == 1 else 'S'} r={pl['risk']:.2f} g={pl['grade']}" if legacy else
                               f"{'L' if d_ == 1 else 'S'} r={f_num(pl['risk'])} sl={f_num(pl['stop'])} g={pl['grade']}" + (" cold" if coldNow else ""))
                        info = {"stop0": pl["stop"], "target": pl["target"], "qty_full": pl["qtyFull"], "cold": coldNow,
                                "cold_sum": coldSum, "cold_n": coldN, "risk_plan": pl["risk"], "grade": pl["grade"],
                                "score": pl["score"], "trending": st["trending"], "signal_t": t // 1000,
                                "_bracket_msgs": (M.bracket(True, d_, q, pl["stop"], pl["target"], None, c, t_close),
                                                  M.bracket(False, d_, q, pl["stop"], pl["target"], None, c, t_close))}
                        emsg = M.entry(d_, q, pl["stop"], pl["target"], c, q * pl["risk"] * PV, M.size_note(coldNow, trendHalf), t_close)
                        pend_entry = (d_, q, pl["stop"], pl["target"], cmt, info, emsg)
                        tr["stop"], tr["stop0"], tr["tgt"] = pl["stop"], pl["stop"], pl["target"]
                        tr["beSent"] = False
                        st["tradesToday"] += 1
                        A[1]["armed"] = False; A[-1]["armed"] = False
                        break

        if not P["fillOnClose"]:
            manage()

    return {"trades": trades, "events": events, "alerts": alerts, "netprofit": round(netprofit, 2), "inputs": P,
            "open": None if cur is None else dict(cur), "cold_now": {"sum": round(sum(coldR[-P["coldLook"]:]), 2),
                                                                      "n": len(coldR[-P["coldLook"]:])}}


# ------------------------------------------------------------------------------------------------ summary
def stats(trades):
    """Strategy Tester summary numbers: trades, net, gross profit / loss, PF, win %, max drawdown (closed-trade equity)."""
    p = [x["profit"] for x in trades]
    gp = sum(x for x in p if x > 0)
    gl = -sum(x for x in p if x < 0)
    eq, peak, mdd = 0.0, 0.0, 0.0
    for x in p:
        eq += x; peak = max(peak, eq); mdd = min(mdd, eq - peak)
    return {"trades": len(p), "net": round(sum(p), 2), "gross_profit": round(gp, 2), "gross_loss": round(-gl, 2),
            "pf": round(gp / gl, 2) if gl else None, "win_pct": round(100 * sum(1 for x in p if x > 0) / len(p), 1) if p else None,
            "max_dd_closed": round(mdd, 2), "cold_trades": sum(1 for x in trades if x.get("cold")),
            "commission": round(sum(COMM * 2 * x["qty"] for x in trades), 2)}


# ------------------------------------------------------------------------------------------------ CLI
def fmt(ts):
    return dt.datetime.fromtimestamp(ts, ET).strftime("%Y-%m-%d %H:%M")


def roll_gaps_from_engine(sym="NQ"):
    """{switch bar time (s): gap pts} from data/<sym>_rolls.json - the same rolls the engine's back-adjusted bars use."""
    path = os.path.join(ROOT, "data", f"{sym}_rolls.json")
    if not os.path.exists(path):
        return {}
    return {int(r["switch_t"]): float(r["gap"]) for r in json.load(open(path, encoding="utf-8"))["rolls"] if r.get("gap") is not None}


def engine_news():
    from engine import news as _n
    return [(int(e["t"]), e["event"]) for e in _n.historical_events(("high",))]


def _parse_set(items):
    out = {}
    for it in items or []:
        k, _, v = it.partition("=")
        base = DEFAULT_INPUTS.get(k)
        if base is None:
            raise SystemExit(f"--set: unknown input {k!r}")
        if isinstance(base, bool):
            out[k] = v.strip().lower() in ("1", "true", "yes", "on")
        elif isinstance(base, int):
            out[k] = int(v)
        elif isinstance(base, float):
            out[k] = float(v)
        else:
            out[k] = v
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv", nargs="?")
    ap.add_argument("--from", dest="day_from")
    ap.add_argument("--to", dest="day_to")
    ap.add_argument("--preset", default="locked", choices=sorted(PRESETS))
    ap.add_argument("--legacy", action="store_true", help="the script as TradingView ran it before the parity fix")
    ap.add_argument("--set", action="append", metavar="INPUT=VALUE", help="override a script input, e.g. --set riskUsd=600")
    ap.add_argument("--no-news", action="store_true", help="empty news list (default: the engine's high-impact calendar)")
    ap.add_argument("--no-roll", action="store_true", help="no roll adjustment")
    ap.add_argument("--unadjust", action="store_true", help="engine bars only: replay the unadjusted continuous contract "
                                                            "(TradingView's view) with the roll shift, instead of back-adjusted bars")
    ap.add_argument("--parity", action="store_true", help="diff against engine.backtest with live_model.json (tools/pine_parity.py)")
    ap.add_argument("--py-bars", action="store_true", help="with --parity and a csv: run the Python engine on the csv's bars too")
    ap.add_argument("--py-cache", help="with --parity: reuse / store the Python trades in this JSON file")
    ap.add_argument("--alerts", action="store_true", help="print every alert message in firing order")
    ap.add_argument("--json", help="write trades, summary (and the parity rows) to this JSON file")
    ap.add_argument("--debug", action="store_true")
    a = ap.parse_args()
    S = load_csv(a.csv, a.day_from, a.day_to) if a.csv else load_engine("NQ", a.day_from, a.day_to)
    news = None if (a.legacy or a.no_news) else engine_news()
    gaps = {} if (a.no_roll or (not a.csv and not a.unadjust)) else roll_gaps_from_engine("NQ")
    if a.unadjust and not a.csv:
        S = unadjust(S, gaps)
    preset = "legacy" if a.legacy else a.preset
    r = simulate(S, inputs=_parse_set(a.set), news=news, debug=a.debug, roll_gaps=gaps, preset=preset,
                 legacy=preset == "legacy")
    for x in r["trades"]:
        print(f"{fmt(x['entry_t'])} {'L' if x['dir'] == 1 else 'S'} {x['entry_signal']:30} q={x['qty']:<3} {x['entry']:.2f} -> "
              f"{fmt(x['exit_t'])} {x['exit_signal']:10} {x['exit']:.2f}  {x['profit']:+9.2f}  R {x.get('r', 0):+.3f}")
    sm = stats(r["trades"])
    print(f"{sm['trades']} trades, net {sm['net']:+.2f}, PF {sm['pf']}, win {sm['win_pct']}%, max DD (closed) {sm['max_dd_closed']:.2f}, "
          f"cold-streak trades {sm['cold_trades']}, commission {sm['commission']:.2f} | bars {fmt(S.t[0] // 1000)} .. {fmt(S.t[-1] // 1000)}"
          f" | cold record now: last {r['cold_now']['n']} trades {r['cold_now']['sum']:+.2f}R")
    if a.alerts:
        for ts, kind, m in r["alerts"]:
            print(f"{fmt(ts)} {kind:10} {m}")
    if a.debug:
        for e in r["events"]:
            if e[1] == "cand":
                print(fmt(e[0]), e[1:])
    out = {"bars": [fmt(S.t[0] // 1000), fmt(S.t[-1] // 1000)], "preset": preset, "summary": sm,
           "inputs": {k: v for k, v in r["inputs"].items() if k not in ("pmtToken", "pmtAccount")},
           "trades": [{k: v for k, v in x.items()} for x in r["trades"]]}
    if a.parity:
        import pine_parity as pp
        tv = [{**x, "risk_pts": abs(x["entry"] - x["stop0"])} if x.get("stop0") is not None else dict(x) for x in r["trades"]]
        d0, d1 = a.day_from or S.tdate[0], a.day_to or S.tdate[-1]
        py = pp.py_trades(day_from=d0, day_to=d1, bars_csv=a.csv if a.py_bars else None, cache=a.py_cache)
        py = pp.apply_cold(py)
        res = pp.compare(py, tv, day_from=d0, day_to=d1, t_to=int(S.t[-1] // 1000))
        out["parity"] = {k: v for k, v in res.items()}
    if a.json:
        with open(a.json, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=1, default=str)


if __name__ == "__main__":
    main()
