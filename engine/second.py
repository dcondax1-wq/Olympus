"""Second strategies (paper) next to LIT: the research winners of 2026-10-22, run live on the bars LIT uses.

    EMA   London EMA trend pullback (research/writeups/second-ema.md, tools/second_ema.py, run ema2_lon_vix)
    MACD  MACD divergence at a liquidity sweep (research/writeups/second-md.md, tools/second_md.py, run md2_best)

PAPER ONLY. This module computes signals and keeps no orders: it has no broker / adapter / NinjaTrader import and never
writes an order file (tests/test_second.py asserts it). Config: second_model.json ({"paper": true, "strategies": {...}});
live_model.json / live_model_lit.json are never read or changed here, so LIT and the eval account are untouched.

Same code as the research: every signal and every exit comes from the research modules themselves
(tools/second_ema.py candidates / simulate / trades_of on tools/retail_standalone.load_frame, tools/second_md.py Ctx /
md_cands / sim_one / greedy), on the window LIT's live loop keeps (engine/lit_live.window_start: from the first trading
day of the previous month minus a week). Only closed bars count:
  - a higher-timeframe bar whose clock period has not ended is still forming (retail_standalone live_cut),
  - a trade the bars end inside is "OPEN" (the research simulators' live mode), a signal on the last closed 5m bar is
    "signal" (it enters at the next 5m open, as the backtest does) and shows in the state, never in the trades.
tests/test_second.py replays every 2026 session through run() and gets the research trades.

Each strategy also gets the "on LIT's account" view (the research's own combine rule): LIT goes first; no second entry
while a LIT trade is open; at most 2 trades a day (LIT's 1 + the second's 1); the MACD trade is closed at market the
moment LIT enters (tools/second_md.combine). `lit` = LIT's trades of the window as [{"entry_t", "exit_t" (None = open)}].

Plugin slot for a third strategy (e.g. the S/R levels study, research/second/sr_best.json): a second_model.json entry
{"kind": "<name>", "module": "tools.second_sr", ...} whose module has
    live_run(df5, one_min, cfg, now, lit) -> {"trades": [common trade dicts], "state": {...}}
(see _ema_run for the trade dict), or a function registered here with @plugin("<kind>").
"""
from __future__ import annotations

import datetime as dt
import importlib
import json
import math
import os
import threading
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG_PATH = os.path.join(ROOT, "second_model.json")
ET = ZoneInfo("America/New_York")
PV, COMM, TICK = 2.0, 1.90, 0.25
_LOCK = threading.Lock()              # tools/retail_standalone keeps its bars in a module dict: one run at a time
PLUGINS: dict = {}
DOW = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def plugin(kind):
    def deco(fn):
        PLUGINS[kind] = fn
        return fn
    return deco


def load_cfg(path: str | None = None) -> dict:
    """second_model.json; a missing / broken file = nothing on (never raises)."""
    try:
        with open(path or CFG_PATH, encoding="utf-8") as fh:
            c = json.load(fh)
        if not isinstance(c, dict):
            raise ValueError("not an object")
    except Exception as e:
        return {"paper": True, "strategies": {}, "error": f"{e.__class__.__name__}: {e}"}
    c["paper"] = True                 # paper only, whatever the file says
    c.setdefault("strategies", {})
    return c


def _et(t):
    return dt.datetime.fromtimestamp(int(t), ET)


def _hm(t):
    return _et(t).strftime("%H:%M") if t is not None else None


def _mod(t):
    e = _et(t)
    return e.hour * 60 + e.minute


def trading_day(t) -> str:
    return str((_et(t) + dt.timedelta(hours=6)).date())


def _r2(x):
    return None if x is None or (isinstance(x, float) and not math.isfinite(x)) else round(float(x), 2)


def _window(df5: pd.DataFrame) -> pd.DataFrame:
    from engine import lit_live
    df5 = df5[["time", "open", "high", "low", "close", "volume"]]
    last_t = int(df5["time"].max())
    return df5[df5["time"] >= lit_live.window_start(last_t)].reset_index(drop=True)


def _session_open(day: str, now: int, last_close: int) -> bool:
    """`day`'s 15:55 flat is still ahead: before 15:55 ET of that date and the session not ended early (CME holiday halt)."""
    from engine import lit_live
    flat = int(dt.datetime.combine(dt.date.fromisoformat(day), dt.time(15, 55), ET).timestamp())
    return now < flat and not lit_live._session_over(day, now, last_close)


def lit_windows(res: dict | None) -> list:
    """LIT's trades of a lit_live.run result as [{"entry_t", "exit_t"}] (the open position: exit_t None)."""
    out = []
    if not res:
        return out
    for t in res.get("trades") or []:
        if t.get("entry_t") is not None:
            out.append({"entry_t": int(t["entry_t"]), "exit_t": int(t["exit_t"]) if t.get("exit_t") else None})
    pos = (res.get("state") or {}).get("position")
    if pos and pos.get("entry_t") is not None and not any(x["entry_t"] == int(pos["entry_t"]) for x in out):
        out.append({"entry_t": int(pos["entry_t"]), "exit_t": None})
    return sorted(out, key=lambda x: x["entry_t"])


def _in_lit(lit, t):
    return any(x["entry_t"] <= t < (x["exit_t"] if x["exit_t"] is not None else 1 << 62) for x in lit)


# ============================================================================================ EMA: London trend pullback
@plugin("ema_pullback")
def _ema_run(df5, one_min, cfg, now, lit):
    from tools import retail_standalone as RS
    from tools import second_ema as SE
    E, X = dict(cfg["entry"]), dict(cfg["exit"])
    rule = f"usd{int(cfg.get('usd', 500))}"
    w = _window(df5)
    last_t = int(w["time"].iloc[-1])
    with _LOCK:
        saved = dict(RS.D)
        try:
            d = _ema_load(RS, SE, w, now, last_t)
            U = SE.trades_of(E, X, span=(str(d["days"][0]), "9999"))
            st = _ema_state(SE, d, E, X, now, last_t, U)
            # a CISD on the last closed bar enters at the next 5m open: seen by adding that bar flat at the last close
            # (an estimate for the state line only; the trade itself comes from the real bar on the next poll)
            wx = pd.concat([w, pd.DataFrame([{"time": last_t + 300, **{k: float(w["close"].iloc[-1]) for k in ("open", "high", "low", "close")},
                                              "volume": 0.0}])], ignore_index=True)
            if _mod(last_t + 300) < 960 and trading_day(last_t + 300) == trading_day(last_t):
                d2 = _ema_load(RS, SE, wx, now, last_t + 300)
                n2 = d2["n"] - 1
                sig = [u for u in SE.trades_of(E, X, span=(trading_day(last_t), trading_day(last_t))) if u["ei"] == n2]
                if sig and not any(u["day"] == sig[0]["day"] and u["ei"] < n2 for u in U):
                    st["signal"] = {"dir": sig[0]["dir"], "enter_at": _hm(last_t + 300), "stop": sig[0]["stop"],
                                    "entry_est": sig[0]["entry"], "target_est": sig[0]["target"]}
        finally:
            RS.D.clear()
            RS.D.update(saved)
    trades = []
    for u in U:
        q = SE.qty(rule, u["risk_pts"])
        if q <= 0:
            continue
        open_ = str(u["exit_kind"]).startswith("OPEN")
        r_ = float(u["r"])
        pnl = q * PV * r_ * u["risk_pts"]
        t = {"day": u["day"], "entry_t": int(u["entry_t"]), "exit_t": None if open_ else int(u["exit_t"]), "dir": int(u["dir"]),
             "entry": u["entry"], "stop": u["stop"], "target": u["target"], "exit": None if open_ else u["exit"],
             "exit_kind": "OPEN" if open_ else str(u["exit_kind"]).upper(), "r": round(r_, 4), "qty": int(q),
             "usd": round(pnl, 2), "risk_pts": round(float(u["risk_pts"]), 2), "risk_usd": round(q * u["risk_pts"] * PV, 2),
             "setup": u["setup"], "last": u["exit"] if open_ else None,
             "stop_now": (round(u["entry"] + u["dir"] * float(X.get("beo", 0.0)), 2) if u["exit_kind"] == "OPEN_BE" else u["stop"])
             if open_ else None}
        # LIT first on one account (tools/second_ema.combine maxday 2): no EMA entry while a LIT trade is open
        t["lit"] = {"taken": not _in_lit(lit, t["entry_t"]), "usd": t["usd"], "exit_kind": t["exit_kind"]}
        if not t["lit"]["taken"]:
            t["lit"].update(usd=0.0, why="LIT was in a trade")
        trades.append(t)
    _session_end(trades, now, last_t)
    return {"trades": trades, "state": st}


def _ema_load(RS, SE, w, now, last_t):
    RS.load_frame(w, live_cut=True)
    d = SE.load()
    s_last = int(d["sid"][-1])
    day = str(d["days"][s_last])
    # the last session's 15:55 flat not reached yet (no bar at 15:50+ of it, the day not over): trades in it stay open
    m = d["mod"][d["sid"] == s_last]
    has_flat = bool(((m >= 950) & (m < 1080)).any())
    d["open_sid"] = s_last if (not has_flat and _session_open(day, now, last_t + 300)) else None
    return d


def _ema_state(SE, d, E, X, now, last_t, U):
    """Today's stage for the dashboards: waiting for / armed / in trade / done, in plain words."""
    i = d["n"] - 1
    day = str(d["days"][int(d["sid"][i])])
    a, z = SE.WINS[E["win"]]
    m_next = _mod(last_t + 300)
    t15, t60 = float(d["t15"][i]), float(d["t60"][i])
    trend = 1 if t15 > 0 and t60 > 0 else (-1 if t15 < 0 and t60 < 0 else 0)
    e50, atr = float(d["e50"][i]), float(d["atr"][i])
    px = float(d["c"][i])
    today = [u for u in U if u["day"] == day]
    st = {"day": day, "trend": {1: "up", -1: "down", 0: "mixed"}[trend], "t15": int(np.sign(t15)), "t60": int(np.sign(t60)),
          "ema50_5m": _r2(e50), "price": _r2(px), "atr": _r2(atr), "window": f"{a // 60:02d}:{a % 60:02d}-{z // 60:02d}:{z % 60:02d} ET"}
    dow = dt.date.fromisoformat(trading_day(last_t + 300)).weekday()
    if any(str(u["exit_kind"]).startswith("OPEN") for u in today):
        u = next(u for u in today if str(u["exit_kind"]).startswith("OPEN"))
        st.update(stage="in_trade", text=f"In a paper {'long' if u['dir'] > 0 else 'short'} from {_hm(u['entry_t'])} ET at "
                                          f"{u['entry']:,.2f}, stop {u['stop']:,.2f}, target {u['target']:,.2f}")
    elif today:
        u = today[0]
        st.update(stage="done", text=f"Done for today (1 trade a day): {'long' if u['dir'] > 0 else 'short'} {_hm(u['entry_t'])} ET -> "
                                     f"{str(u['exit_kind']).lower()} {u['r']:+.2f}R")
    elif E.get("reg") == "nomon" and dow == 0:
        st.update(stage="off", text="No trades on Mondays (rule): back on Tuesday from 03:00 ET")
    elif not (a <= m_next < z):
        st.update(stage="off", text=f"Outside its hours: entries {st['window']}" + (" (next: tomorrow 03:00 ET)" if m_next >= z and m_next < 1080 else ""))
    elif trend == 0:
        st.update(stage="waiting", text="Waiting for the 15m and 1h trend to agree (EMA 21 vs EMA 50 on both)")
    else:
        side = "long" if trend > 0 else "short"
        far = (px - e50) * trend
        touch = ((float(d["l"][i]) <= e50 + 0.1 * atr) if trend > 0 else (float(d["h"][i]) >= e50 - 0.1 * atr))
        if touch:
            st.update(stage="armed", text=f"Armed ({side}): price is at the 5m EMA 50 ({e50:,.2f}); waiting for a swing "
                                          f"{'low' if trend > 0 else 'high'} to be swept and a 5m CISD close back {'up' if trend > 0 else 'down'}")
        else:
            st.update(stage="waiting", text=f"Trend {st['trend']} ({side}s only): waiting for a pullback to the 5m EMA 50 "
                                            f"({e50:,.2f}, {abs(far):,.0f} pts away) that sweeps a swing {'low' if trend > 0 else 'high'}, then a 5m CISD")
    return st


# ============================================================================================ S/R: NY sweep-and-reclaim
@plugin("sr_reclaim")
def _sr_run(df5, one_min, cfg, now, lit):
    """tools/second_sr.py (setup nyreclaim): candidates (gen_reclaim), outcomes (_walk) and the sequential pick (select) on
    retail_standalone.load_frame of LIT's window; targets as set_targets."""
    from tools import retail_standalone as RS
    from tools import second_sr as SR
    key = dict(cfg["key"])
    rule = f"usd{int(cfg.get('usd', 500))}"
    w = _window(df5)
    last_t = int(w["time"].iloc[-1])
    with _LOCK:
        saved, saved_sr, saved_oc = dict(RS.D), dict(SR.D), dict(SR._OC)
        try:
            RS.load_frame(w, live_cut=True)
            SR.D.clear()
            SR._OC.clear()
            SR.data()
            d = SR.D                     # data() returns a copy on its first call; run_key / trades_of read SR.D
            s_last = int(d["sid"][-1])
            m = d["mod"][d["sid"] == s_last]
            has_flat = bool(((m >= 950) & (m < 1080)).any())
            d["open_sid"] = s_last if (not has_flat and _session_open(str(d["days"][s_last]), now, last_t + 300)) else None
            T = SR.run_key(key)
            TT = SR.set_targets(SR.trades_of(T, rule, "nyreclaim"), key)
            # LIT first on one account (tools/second_sr.lit_skip max2): a candidate is skipped while a LIT trade is open,
            # so a later one that day may be taken instead
            TL = SR.set_targets(SR.trades_of(SR.run_key(key, skip=lambda x: _in_lit(lit, int(d["t"][x["k0"]]))), rule, "nyreclaim"), key)
            # a reclaim close on the last bar: enters at the next 5m open
            g = {k: key[k] for k in SR.GEN_KEYS[key["setup"]]}
            n = d["n"]
            a, z = SR.WINDOWS[key["win"]]
            sig = [c for c in SR.gen(d, key["setup"], g) if c[0] == n - 1 and a <= _mod(last_t + 300) < z]
            st = _sr_state(d, key, TT, sig, now, last_t)
        finally:
            RS.D.clear(); RS.D.update(saved)
            SR.D.clear(); SR.D.update(saved_sr)
            SR._OC.clear(); SR._OC.update(saved_oc)
    fl = lambda v: None if v is None else float(v)
    for u in TT + TL:                  # numpy scalars -> plain numbers (state.json / data.json)
        for k in ("entry", "stop", "target", "exit", "r", "pnl_usd", "risk_pts", "risk_usd"):
            u[k] = fl(u.get(k))
    lmap = {int(t["entry_t"]): t for t in TL}
    trades = []
    for u in TT:
        open_ = str(u["exit_kind"]).startswith("OPEN")
        t = {"day": u["day"], "entry_t": int(u["entry_t"]), "exit_t": None if open_ else int(u["exit_t"]), "dir": int(u["dir"]),
             "entry": u["entry"], "stop": u["stop"], "target": u["target"], "exit": None if open_ else u["exit"],
             "exit_kind": "OPEN" if open_ else str(u["exit_kind"]).upper(), "r": u["r"], "qty": int(u["qty"]), "usd": u["pnl_usd"],
             "risk_pts": u["risk_pts"], "risk_usd": u["risk_usd"], "setup": "S/R sweep-and-reclaim (NY)",
             "last": u["exit"] if open_ else None, "stop_now": u["stop"] if open_ else None}
        lt = lmap.pop(t["entry_t"], None)
        t["lit"] = {"taken": lt is not None, "usd": round(float(lt["pnl_usd"]), 2) if lt else 0.0, "exit_kind": t["exit_kind"] if lt else None,
                    "note": "own account recommended"}
        if lt is None:
            t["lit"]["why"] = "LIT was in a trade"
        trades.append(t)
    if lmap:                           # on LIT's account another reclaim later that day would have been taken instead
        st["lit_alt"] = [{"day": u["day"], "entry_t": int(u["entry_t"]), "dir": int(u["dir"]), "r": u["r"], "usd": u["pnl_usd"],
                          "exit_kind": str(u["exit_kind"]).upper()} for u in lmap.values()][-5:]
    _session_end(trades, now, last_t)
    return {"trades": trades, "state": st}


def _sr_state(d, key, TT, sig, now, last_t):
    from tools import second_sr as SR
    n = d["n"]
    day = str(d["days"][int(d["sid"][n - 1])])
    a, z = SR.WINDOWS[key["win"]]
    win = f"{a // 60:02d}:{a % 60:02d}-{z // 60:02d}:{z % 60:02d} ET"
    st = {"day": day, "window": win, "price": _r2(d["c"][n - 1]), "lit_note": "own account recommended (with LIT it slightly worsens "
                                                                              "LIT's eval path in 2026 H2)"}
    today = [u for u in TT if u["day"] == day]
    m_next = _mod(last_t + 300)
    if sig and not today:
        c = sig[0]
        st["signal"] = {"dir": int(c[2]), "enter_at": _hm(last_t + 300), "stop": _r2(c[5]), "level": c[8]}
    if any(str(u["exit_kind"]).startswith("OPEN") for u in today):
        u = next(u for u in today if str(u["exit_kind"]).startswith("OPEN"))
        st.update(stage="in_trade", text=f"In a paper {'long' if u['dir'] > 0 else 'short'} from {_hm(u['entry_t'])} ET at "
                                          f"{u['entry']:,.2f}, stop {u['stop']:,.2f}, target {u['target']:,.2f} (2R)")
    elif today:
        u = today[-1]
        st.update(stage="done", text=f"Done for today (1 trade a day): {'long' if u['dir'] > 0 else 'short'} {_hm(u['entry_t'])} ET -> "
                                     f"{str(u['exit_kind']).lower()} {u['r']:+.2f}R")
    elif st.get("signal"):
        s = st["signal"]
        st.update(stage="armed", text=f"Signal ({'long' if s['dir'] > 0 else 'short'}): {s['level']} swept and reclaimed on the "
                                      f"{_hm(last_t)} ET close; paper entry at the {s['enter_at']} ET open, stop {s['stop']:,.2f}")
    elif not (a <= m_next < z):
        st.update(stage="off", text=f"Outside its hours: entries {win}")
    else:
        st.update(stage="waiting", text="Waiting for a level of the day (yesterday's RTH high/low, overnight, Asia / London box, "
                                        "last week, opening range) to be swept after an inducement, then a strong 5m close back over it")
    return st


# ============================================================================================ MACD divergence at a sweep
@plugin("macd_sweep")
def _md_run(df5, one_min, cfg, now, lit):
    from engine import lit as L
    from engine import lit_live
    from engine.data import Bars, from_frame
    from tools import second_md as SM
    gen, sim, flt = dict(cfg["gen"]), dict(cfg["sim"]), dict(cfg["flt"])
    usd = float(cfg.get("usd", 500))
    w = lit_live._clean5(_window(df5))
    last_t = int(w["time"].iloc[-1])
    M = L.Market(bars=from_frame("NQ", "5m", w))
    t0 = int(w["time"].min())
    B1 = "none"                                           # no 1m bars: 5m execution (the backtest rule before 2026)
    if one_min is not None:
        if isinstance(one_min, Bars):
            src = lit_live._slice_bars(one_min, t0)
            B1 = L.bars_1m(M, src=src) if len(src) else "none"                 # research-clean bars: the backtest rule
        else:
            src = lit_live.feed_1m(one_min, t0)
            B1 = L.bars_1m(M, src=src, tol=lit_live.LIVE_TOL_1M) if src is not None and len(src) else "none"
    X = SM.Ctx(M, B1)
    C = SM.md_cands(X, **gen)
    outs = [SM.sim_x(X, z, sim, live=True) for z in C]
    T = SM.greedy(X, C, outs, flt["kz"], flt["maxpd"], SM.md_filter(flt))
    trades = []
    for z, r in T:
        q = SM.q_usd(usd, r["risk"])
        if q <= 0:
            continue
        t = _md_trade(SM, X, z, r, q)
        trades.append(t)
        t["lit"] = _md_lit(SM, X, z, r, sim, usd, lit, trades)
    st = _md_state(SM, X, C, T, flt, gen, now, last_t, trades)
    _session_end(trades, now, last_t)
    return {"trades": trades, "state": st}


def _md_trade(SM, X, z, r, q):
    rec = SM.tr_rec(X, z, r, q, "MACD-div")
    open_ = r["kind"] == "OPEN"
    t = {"day": rec["day"], "entry_t": rec["entry_t"], "exit_t": None if open_ else rec["exit_t"], "dir": rec["dir"],
         "entry": rec["entry"], "stop": rec["stop"], "target": rec["target"], "exit": None if open_ else rec["exit"],
         "exit_kind": "OPEN" if open_ else str(r["kind"]).upper(), "r": rec["r"], "qty": int(q), "usd": rec["pnl_usd"],
         "risk_pts": rec["risk_pts"], "risk_usd": rec["risk_usd"], "setup": "MACD divergence at a sweep + 5m CISD",
         "last": round(r["ex"], 2) if open_ else None, "stop_now": round(r["stop_now"], 2) if open_ else None}
    if open_ and r.get("cut"):
        t["note"] = "15-minute check failed: exits at the next open"
    return t


def _md_lit(SM, X, z, r, sim, usd, lit, prev):
    """tools/second_md.combine mode 'two' for one trade: skipped while LIT is in a trade or once the day has 2 trades;
    closed at market the moment LIT enters."""
    ft = int(X.Xt[r["x0"]])
    day = X.dates[X.Xday[r["x0"]]]
    L_day = [x for x in lit if trading_day(x["entry_t"]) == day]
    if _in_lit(L_day, ft):
        return {"taken": False, "usd": 0.0, "why": "LIT was in a trade", "exit_kind": None}
    taken = len(L_day) + sum(1 for p in prev[:-1] if p["day"] == day and (p.get("lit") or {}).get("taken"))
    if taken >= 2:
        return {"taken": False, "usd": 0.0, "why": "2 trades already today", "exit_kind": None}
    nxt = [x["entry_t"] for x in L_day if x["entry_t"] > ft]
    et_ = int(X.Xt[r["x1"]])
    if nxt and nxt[0] <= et_:
        r2 = SM.sim_x(X, z, sim, force_t=nxt[0], live=True)
        if r2 is None:
            return {"taken": False, "usd": 0.0, "why": "no fill", "exit_kind": None}
        q = SM.q_usd(usd, r2["risk"])
        t2 = _md_trade(SM, X, z, r2, q)
        return {"taken": True, "usd": t2["usd"], "exit_kind": "LIT" if r2["kind"] == "lit" else t2["exit_kind"],
                "why": f"closed at market when LIT entered {_hm(nxt[0])} ET" if r2["kind"] == "lit" else None}
    q = SM.q_usd(usd, r["risk"])
    t2 = _md_trade(SM, X, z, r, q)
    return {"taken": True, "usd": t2["usd"], "exit_kind": t2["exit_kind"]}


def _md_state(SM, X, C, T, flt, gen, now, last_t, trades):
    n = X.n
    day_i = int(X.day[n - 1])
    day = X.dates[day_i]
    kz = SM.KZ[flt["kz"]]
    win = ", ".join(f"{a // 60:02d}:{a % 60:02d}-{b // 60:02d}:{b % 60:02d}" for a, b in kz) + " ET"
    m_next = _mod(last_t + 300)
    today = [t for t in trades if t["day"] == day]
    st = {"day": day, "window": win, "price": _r2(X.c[n - 1])}
    # a signal on the last closed bar: enters at the next 5m open (the backtest's fill)
    fil = SM.md_filter(flt)
    sig = [z for z in C if z["j"] == n - 1 and fil(z["f"]) and SM.in_kz(m_next, flt["kz"])]
    if sig and len(today) < flt["maxpd"]:
        z = sig[0]
        st["signal"] = {"dir": z["dir"], "enter_at": _hm(last_t + 300), "stop": _r2(z["stops"]["ext"]), "cisd": _r2(z["cisd"])}
    if any(t["exit_kind"] == "OPEN" for t in today):
        t = next(t for t in today if t["exit_kind"] == "OPEN")
        st.update(stage="in_trade", text=f"In a paper {'long' if t['dir'] > 0 else 'short'} from {_hm(t['entry_t'])} ET at "
                                          f"{t['entry']:,.2f}, stop {t['stop_now']:,.2f}, target {t['target']:,.2f}")
        return st
    if len(today) >= flt["maxpd"]:
        t = today[-1]
        st.update(stage="done", text=f"Done for today (1 trade a day): {'long' if t['dir'] > 0 else 'short'} {_hm(t['entry_t'])} ET -> "
                                     f"{t['exit_kind'].lower()} {t['r']:+.2f}R")
        return st
    if st.get("signal"):
        s = st["signal"]
        st.update(stage="armed", text=f"Signal ({'long' if s['dir'] > 0 else 'short'}): MACD divergence + CISD on the {_hm(last_t)} ET "
                                      f"close; paper entry at the {s['enter_at']} ET open, stop {s['stop']:,.2f}")
        return st
    # armed: a LIT level swept >= depth ATR in the last 2 hours, waiting for the CISD close with MACD divergence
    s0 = X.M.days[day_i][1]
    ev = [(i, dr, px) for (i, dr, px) in SM.sweep_events(X, SM.LV[gen["lv"]]) if s0 <= i < n and i >= n - 24]
    best = None
    for i, dr, px in ev:
        ext = float(X.l[i:n].min()) if dr > 0 else float(X.h[i:n].max())
        dep = (px - ext) * dr / X.atr[i] if X.atr[i] > 0 else 0.0
        if dep >= flt["depth"]:
            best = (i, dr, px, ext)
    if not any(a <= m_next < b for a, b in kz):
        st.update(stage="off", text=f"Outside its hours: entries {win}")
    elif best:
        i, dr, px, ext = best
        st.update(stage="armed", text=f"Armed ({'long' if dr > 0 else 'short'}): a level at {px:,.2f} was swept at {_hm(int(X.t[i]))} ET "
                                      f"(extreme {ext:,.2f}); waiting until {_hm(int(X.t[i]) + 24 * 300)} ET for a 5m CISD close "
                                      "with MACD divergence")
    else:
        st.update(stage="waiting", text="Waiting for a LIT level (session high/low, PDH/PDL, equal highs/lows...) to be swept "
                                        f"by {flt['depth']} ATR, then a 5m CISD close with MACD divergence")
    return st


def _session_end(trades, now, last_t):
    """A trade still open when its session is over (holiday early close before 15:55): flat at the last close - 1 tick,
    as the backtest does once the next session's bars arrive."""
    for t in trades:
        if t["exit_kind"] == "OPEN" and not _session_open(t["day"], now, last_t + 300) and t.get("last") is not None:
            ex = float(t["last"]) - t["dir"] * TICK
            pts = (ex - float(t["entry"])) * t["dir"]
            per = pts * PV - COMM
            t.update(exit_kind="FLAT", exit=round(ex, 2), exit_t=int(last_t) + 300, r=round(per / (t["risk_pts"] * PV), 4),
                     usd=round(t["qty"] * per, 2), stop_now=None, note="session ended early (holiday)")


# ============================================================================================ one poll, all strategies
def run(df5: pd.DataFrame, one_min=None, now: int | None = None, cfg: dict | None = None, lit: list | None = None) -> dict:
    """One poll: every strategy of second_model.json that is on. df5 = the merged 5m history LIT's loop uses, one_min =
    its 1m bars (a feed DataFrame or research Bars; None = 5m execution), lit = LIT's trades of the window. A failing
    strategy reports its error and never stops the others. Paper only, nothing is routed."""
    cfg = cfg or load_cfg()
    if df5 is None or not len(df5):
        return {"paper": True, "t": now, "strategies": {}, "error": "no 5m bars"}
    now = int(now if now is not None else int(df5["time"].max()) + 300)
    lit = lit or []
    out = {"paper": True, "t": now, "day": trading_day(now), "strategies": {}}
    for key, sc in (cfg.get("strategies") or {}).items():
        base = {"label": sc.get("label") or key, "short": sc.get("short") or key, "on": bool(sc.get("on", True))}
        if not base["on"]:
            out["strategies"][key] = {**base, "trades": [], "state": {"stage": "off", "text": "Switched off in second_model.json"}}
            continue
        try:
            if sc.get("module"):
                fn = getattr(importlib.import_module(sc["module"]), "live_run")
            else:
                fn = PLUGINS[sc["kind"]]
            r = fn(df5, one_min, sc, now, lit)
            out["strategies"][key] = {**base, "trades": r["trades"], "state": r["state"]}
        except Exception as e:                       # never stops LIT or the other strategies
            out["strategies"][key] = {**base, "trades": [], "state": {"stage": "error", "text": f"error: {e.__class__.__name__}: {e}"},
                                      "error": f"{e.__class__.__name__}: {e}"}
    return out


# ============================================================================================ backtest numbers (dashboards)
PERIODS = (("H1", "2026 H1 (picked)"), ("H2", "2026 H2 (check)"), ("2026", "2026 Jan 2 - Oct 16"), ("2025", "2025"),
           ("2021-24", "2021-24"))
_KEEP = ("n", "tpw", "win", "pf", "net", "per_month", "dd", "avg_r", "p10", "f10", "p20", "f20")


def _row(x):
    return {k: x.get(k) for k in _KEEP if x.get(k) is not None} if isinstance(x, dict) else None


def backtest(key: str, sc: dict) -> dict:
    """The research numbers of one strategy at $500 risk a trade: alone, and LIT + it on one account vs LIT alone, per
    period (H1 / H2 / 2026 / 2025 / 2021-24). From the research JSON named in second_model.json "research"."""
    rs = sc.get("research") or {}
    out = {"run": sc.get("run"), "writeup": sc.get("writeup"), "own": {}, "with_lit": {}, "lit_only": {}, "rules": sc.get("rules") or []}
    try:
        if not out["rules"] and rs.get("best"):
            out["rules"] = json.load(open(os.path.join(ROOT, rs["best"]), encoding="utf-8")).get("rules") or []
        if sc.get("kind") == "ema_pullback":
            rep = json.load(open(os.path.join(ROOT, rs.get("report", "research/second/ema_report.json")), encoding="utf-8"))
            v = rep["versions"][sc.get("run", "ema2_lon_vix")]
            own = v["money"][f"usd{int(sc.get('usd', 500))}"]
            for p, _ in PERIODS:
                out["own"][p] = _row(own.get(p))
                out["with_lit"][p] = _row(v["with_lit_max2"].get(p))
                out["lit_only"][p] = _row((rep.get("lit") or {}).get(p))
            out["eval_with_lit"] = v.get("eval_with_lit")
            out["eval_lit_only"] = (rep.get("lit") or {}).get("eval_path")
        elif sc.get("kind") == "macd_sweep":
            rep = json.load(open(os.path.join(ROOT, rs.get("best", "research/second/md_best.json")), encoding="utf-8"))["report"]
            own = rep["own"][f"usd{int(sc.get('usd', 500))}"]
            pm = {"H1": "H1", "H2": "H2", "2026": "2026", "2025": "2025", "2021-24": "2124"}
            for p, _ in PERIODS:
                out["own"][p] = _row(own.get(pm[p]))
                out["with_lit"][p] = _row(rep["combo"]["two"]["merged"].get(pm[p]))
                out["lit_only"][p] = _row(rep["combo"]["lit_only"].get(pm[p]))
            ev = rep["combo"]["two"].get(f"eval_usd{int(sc.get('usd', 500))}") or {}
            out["eval_with_lit"] = {"H1": ev.get("H1"), "H2": ev.get("H2")}
        elif sc.get("kind") == "sr_reclaim":
            rep = json.load(open(os.path.join(ROOT, rs.get("report", "research/second/sr_final.json")), encoding="utf-8"))[sc.get("name", "nyreclaim")]
            for p, _ in PERIODS:
                out["own"][p] = _row((rep["periods"].get(p) or {}).get(f"usd{int(sc.get('usd', 500))}"))
                cb = (rep.get("combo") or {}).get("max2", {}).get(p)
                if cb:
                    out["with_lit"][p] = _row({**cb, "n": None})
                    out["lit_only"][p] = {"net": cb.get("lit_net_alone"), "dd": cb.get("lit_dd_alone")}
            ev = rep.get("eval") or {}
            out["eval_with_lit"] = {k: (ev.get("with_lit_max2") or {}).get(k) for k in ("H1", "H2")}
            out["eval_lit_only"] = {k: (ev.get("lit_alone") or {}).get(k) for k in ("H1", "H2")}
        elif rs.get("summary"):                      # a plugin strategy: its research JSON gives the same tables
            rep = json.load(open(os.path.join(ROOT, rs["summary"]), encoding="utf-8"))
            for k in ("own", "with_lit", "lit_only"):
                out[k] = rep.get(k) or {}
    except Exception as e:
        out["error"] = f"{e.__class__.__name__}: {e}"
    out["periods"] = [list(p) for p in PERIODS]
    return out


def dashboard_block(state: dict | None = None, cfg: dict | None = None, pc: dict | None = None) -> dict:
    """data.json "second" / /api/next/second: per strategy its rules, backtest tables, today's state and the paper
    trades (cloud ledger; the PC's live view when given)."""
    cfg = cfg or load_cfg()
    st = state or {}
    out = {"paper": True, "note": "Paper only: nothing is traded. LIT and the eval account are unchanged.",
           "t": st.get("t"), "first_run": st.get("first_run"), "strategies": [], "pc_t": (pc or {}).get("t")}
    for key, sc in (cfg.get("strategies") or {}).items():
        s = (st.get("strategies") or {}).get(key) or {}
        led = s.get("ledger") or {}
        rows = sorted(led.values(), key=lambda v: v.get("entry_t") or 0)
        fin = [v for v in rows if v.get("exit_kind") not in (None, "OPEN")]
        lit_fin = [v for v in fin if (v.get("lit") or {}).get("taken")]
        pcs = ((pc or {}).get("strategies") or {}).get(key) or {}
        out["strategies"].append({
            "key": key, "label": sc.get("label") or key, "short": sc.get("short") or key, "on": bool(sc.get("on", True)),
            "summary": sc.get("summary"), "with_lit_label": sc.get("with_lit_label"), "with_lit_note": sc.get("with_lit_note"),
            "backtest": (bt := backtest(key, sc)), "rules": sc.get("rules") or bt.get("rules") or [],
            "state": pcs.get("state") if pcs.get("state") and (pc or {}).get("t", 0) >= (st.get("t") or 0) else s.get("state"),
            "state_src": "PC" if pcs.get("state") and (pc or {}).get("t", 0) >= (st.get("t") or 0) else "cloud",
            "trades": rows[-60:], "paper": {"n": len(fin), "usd": round(sum(v.get("usd") or 0 for v in fin), 2),
                                            "wins": sum(1 for v in fin if (v.get("usd") or 0) > 0),
                                            "with_lit_n": len(lit_fin), "with_lit_usd": round(sum((v.get("lit") or {}).get("usd") or 0 for v in lit_fin), 2)},
            "pc_today": [t for t in (pcs.get("trades") or []) if t.get("day") == (pcs.get("state") or {}).get("day")][-5:],
        })
    return out


def compact(res: dict | None, max_trades: int = 6) -> dict | None:
    """The heartbeat / live.json cut of one run(): today's state + the last trades per strategy (small)."""
    if not res:
        return None
    out = {"t": res.get("t"), "day": res.get("day"), "paper": True, "strategies": {}}
    for k, s in (res.get("strategies") or {}).items():
        tr = [{kk: t.get(kk) for kk in ("day", "entry_t", "exit_t", "dir", "entry", "stop", "stop_now", "target", "exit", "exit_kind",
                                        "r", "qty", "usd", "last", "lit")} for t in (s.get("trades") or [])[-max_trades:]]
        out["strategies"][k] = {"label": s.get("label"), "short": s.get("short"), "on": s.get("on"), "state": s.get("state"),
                                "trades": tr, **({"error": s["error"]} if s.get("error") else {})}
    return out


# ============================================================================================ paper ledger (cloud monitor)
ROW_KEYS = ("day", "entry_t", "exit_t", "dir", "entry", "stop", "stop_now", "target", "exit", "exit_kind", "r", "qty", "usd",
            "risk_pts", "risk_usd", "last", "lit", "note")


def ledger_update(prev: dict | None, res: dict, now: int, pauses=None, in_pause=None) -> dict:
    """The cloud's paper ledger per strategy from one run(): the trades that entered after the ledger started watching
    (first_run). A finished paper trade is frozen (the decision made on the bars available then, as the LIT ledger,
    tests/test_ledger_freeze.py): a later re-run that disagrees is only noted ("revised_replay"). pauses (no PC bars):
    a trade that would enter inside a stretch without the PC's bars is not added (nothing could have entered)."""
    prev = prev or {}
    first = int(prev.get("first_run") or now)
    out = {"first_run": first, "t": int(now), "day": res.get("day"), "paper": True, "strategies": {}}
    old = prev.get("strategies") or {}
    for key, s in (res.get("strategies") or {}).items():
        led = {str(k): dict(v) for k, v in ((old.get(key) or {}).get("ledger") or {}).items()}
        for t in s.get("trades") or []:
            k = str(int(t["entry_t"]))
            p = led.get(k)
            if p is None and (int(t["entry_t"]) < first - 300 or (pauses and in_pause and in_pause(int(t["entry_t"]), pauses))):
                continue
            row = {kk: t.get(kk) for kk in ROW_KEYS}
            row["side"] = "LONG" if t["dir"] > 0 else "SHORT"
            if p and p.get("exit_kind") not in (None, "OPEN"):
                new = {kk: row[kk] for kk in ("exit_kind", "r", "exit_t")}
                if any(new[kk] != p.get(kk) for kk in new):
                    p["revised_replay"] = new
                else:
                    p.pop("revised_replay", None)
                continue
            led[k] = row
        out["strategies"][key] = {kk: s.get(kk) for kk in ("label", "short", "on", "state", "error")}
        out["strategies"][key]["ledger"] = dict(sorted(led.items())[-200:])
    for key, s in old.items():                        # a strategy switched off / removed keeps its ledger
        if key not in out["strategies"]:
            out["strategies"][key] = {**s, "on": False}
    return out


def readme_lines(block: dict | None, money=None) -> list:
    """README section "Second strategies (paper)" (cloud monitor, dashboard branch)."""
    money = money or (lambda x: f"{'+' if x >= 0 else '-'}${abs(x):,.0f}")
    L = ["", "## Second strategies (paper)",
         "Two research winners run next to LIT on the same bars, **paper only** (engine/second.py, second_model.json): nothing is "
         "traded, LIT and the eval account are unchanged. \"With LIT\" = LIT first on one account, no second entry while LIT "
         "is in a trade, max 2 trades a day."]
    if not block or not block.get("strategies"):
        return L + ["", "Not running yet (second_model.json missing or every strategy off)."]
    for key, s in block["strategies"].items():
        led = sorted((s.get("ledger") or {}).values(), key=lambda v: v.get("entry_t") or 0, reverse=True)
        fin = [v for v in led if v.get("exit_kind") not in (None, "OPEN")]
        lt = [v for v in fin if (v.get("lit") or {}).get("taken")]
        st = s.get("state") or {}
        L += ["", f"### {s.get('label') or key} ({s.get('short') or key})" + ("" if s.get("on", True) else " - OFF"),
              "| | |", "|---|---|", f"| Now | {st.get('text') or '-'} |",
              f"| Paper ledger | {len(fin)} finished trades, {money(sum(v.get('usd') or 0 for v in fin))} since "
              f"{_et(block.get('first_run') or block.get('t') or 0):%b %d} |",
              f"| With LIT (one account) | {len(lt)} taken, {money(sum((v.get('lit') or {}).get('usd') or 0 for v in lt))} |"]
        if s.get("error"):
            L.append(f"| Error | {s['error']} |")
        L += ["", "| Day | Entry | Side | Exit | R | $ | With LIT |", "|---|---|---|---|---:|---:|---|"]
        rows = []
        for v in led[:8]:
            lit = v.get("lit") or {}
            rows.append(f"| {v.get('day')} | {_hm(v.get('entry_t'))} | {v.get('side')} | {v.get('exit_kind')} | "
                        f"{(v.get('r') or 0):+.2f} | {money(v.get('usd') or 0)} | "
                        f"{'yes' if lit.get('taken') else 'no (' + str(lit.get('why') or '-') + ')'} |")
        L += rows or ["| - | - | - | - | - | - | - |"]
    return L
