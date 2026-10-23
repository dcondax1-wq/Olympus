"""Second strategies (paper) next to LIT: the research winners of 2026-10-22, run live on the bars LIT uses.

    EMA   London EMA trend pullback (research/writeups/second-ema.md, tools/second_ema.py, run ema2_lon_vix)
    MACD  MACD divergence at a liquidity sweep (research/writeups/second-md.md, tools/second_md.py, run md2_best)

This module computes signals and keeps no orders: it has no broker / adapter / NinjaTrader import and never writes an
order file (tests/test_second.py asserts it). Config: second_model.json ({"paper": true, "strategies": {...}});
live_model.json / live_model_lit.json are never read or changed here. A strategy with "route": true (default false; the
owner's switch `python -m engine.second --route <key> on|off`, below) is ROUTED by the PC bot on LIT's account: that
lives in engine/live.py (LiveBot._second_route_tick: LIT first, one position, max 2 trades a day, eval-safe size);
everything else stays paper. Each strategy also returns its "brain" (rule checks in the engine's order, closed bars only).

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

import bisect
import collections
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
    c["paper"] = True                 # this module never routes, whatever the file says (engine/live.py routes "route" ones)
    c.setdefault("strategies", {})
    for sc in c["strategies"].values():
        if isinstance(sc, dict):      # "route": false = paper (default); never for a cloud-only strategy
            sc["route"] = bool(sc.get("route", False)) and bool(sc.get("on", True)) and not sc.get("cloud_only") \
                and not sc.get("candidate")   # a candidate ATLAS member (stop hunts) is paper only
    return c


def routed(cfg: dict | None = None) -> list:
    """Keys of the strategies the PC bot routes to its account (second_model.json "on" and "route" true, not cloud_only).
    Routing itself lives in engine/live.py (LiveBot._second_route_tick); this module only computes signals."""
    cfg = cfg or load_cfg()
    return [k for k, s in (cfg.get("strategies") or {}).items() if isinstance(s, dict) and s.get("route")]


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
            brain = _safe_brain(lambda: _ema_brain(SE, d, E, X, U, st, SE.candidates(), last_t), st)
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

                    st.update(stage="armed", text=f"Signal ({'long' if sig[0]['dir'] > 0 else 'short'}): 5m CISD after a pullback to "
                                                  f"the EMA 50 on the {_hm(last_t)} ET bar; entry at the {_hm(last_t + 300)} ET open, "
                                                  f"stop {sig[0]['stop']:,.2f}")

                    def _sb(d2=d2, n2=n2, dr=int(sig[0]["dir"])):
                        c2 = SE.candidates()
                        row = next(r for r in (x for _, x in c2.iterrows()) if int(r["ei"]) == n2 and int(r["dir"]) == dr)
                        return _ema_brain(SE, d2, E, X, U, st, c2, last_t, row, d2)
                    brain = _safe_brain(_sb, st)
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
    return {"trades": trades, "state": st, "brain": brain}


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


# ============================================================================================ LIT variant (paper shadow)
@plugin("lit_variant")
def _litv_run(df5, one_min, cfg, now, lit):
    """LIT itself with extra settings (e.g. the Asia slot of research/writeups/lit-more-entries.md: all hours, 2 a day,
    1 per session, Asia banked at 3R) through engine/lit_live.run = the same executor as the backtest, on the same bars.
    Cloud only ("cloud_only": the PC bot never runs it: its guards block evening entries and it must not trade). LIT's
    size rule from the model's own micros; the "with LIT" view does not apply (it is LIT plus)."""
    from engine import lit as L
    from engine import lit_live
    with open(os.path.join(ROOT, "live_model.json"), encoding="utf-8") as fh:
        base = json.load(fh).get("lit") or {}
    P = {**L.DEFAULTS, **base, **(cfg.get("overrides") or {})}
    res = lit_live.run(df5, P, one_min=one_min, now=now)
    asia = cfg.get("tag_window") or [1080, 120]
    trades = []
    for t in res.get("trades") or []:
        m = _mod(t["entry_t"])
        tag = "Asia" if (m >= asia[0] or m < asia[1]) else "day"
        trades.append({"day": trading_day(t["entry_t"]), "entry_t": int(t["entry_t"]), "exit_t": int(t["exit_t"]) if t.get("exit_t") else None,
                       "dir": int(t["dir"]), "entry": _r2(t.get("entry")), "stop": _r2(t.get("stop")), "target": _r2(t.get("target")),
                       "exit": _r2(t.get("exit_price")), "exit_kind": str(t.get("exit_reason") or "").upper(), "r": round(float(t.get("pnl_r") or 0), 3),
                       "qty": int(t.get("qty") or 0), "usd": round(float(t.get("pnl") or 0), 2), "risk_pts": _r2(t.get("risk_pts")),
                       "risk_usd": None, "setup": f"LIT ({tag} slot)", "last": None, "stop_now": None, "lit": None, "note": f"{tag} slot"})
    pos = (res.get("state") or {}).get("position")
    if pos and pos.get("entry_t") is not None and not any(x["entry_t"] == int(pos["entry_t"]) for x in trades):
        m = _mod(pos["entry_t"])
        tag = "Asia" if (m >= asia[0] or m < asia[1]) else "day"
        trades.append({"day": trading_day(pos["entry_t"]), "entry_t": int(pos["entry_t"]), "exit_t": None, "dir": int(pos["dir"]),
                       "entry": _r2(pos.get("entry")), "stop": _r2(pos.get("stop0") or pos.get("stop")), "target": _r2(pos.get("target")),
                       "exit": None, "exit_kind": "OPEN", "r": 0.0, "qty": int(pos.get("qty") or 0), "usd": 0.0,
                       "risk_pts": _r2(pos.get("risk_pts")), "risk_usd": None, "setup": f"LIT ({tag} slot)", "last": None,
                       "stop_now": _r2(pos.get("stop")), "lit": None, "note": f"{tag} slot"})
    trades.sort(key=lambda x: x["entry_t"])
    st = {"day": trading_day(now), "stage": "in_trade" if pos else "waiting", "text": res["state"].get("model_state") or "-",
          "window": "18:00-15:30 ET (Asia 18:00-02:00 banked at 3R, then the normal LIT day trade)"}
    if not pos and any(t["day"] == st["day"] for t in trades) and "done for today" in str(st["text"]).lower():
        st["stage"] = "done"
    return {"trades": trades, "state": st, "brain": basic_brain(st, "LIT + Asia slot (cloud paper shadow): its state line")}


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
            brain = _safe_brain(lambda: _sr_brain(SR, d, key, st, TT, now, last_t), st)
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
        if str(u["exit_kind"]) == "OPEN_CUT":          # the 15-minute check failed on the last close: exits at the next open
            t.update(cut_now="T15", note="15-minute check failed: exits at the next open")
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
    return {"trades": trades, "state": st, "brain": brain}


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
    brain = _safe_brain(lambda: _md_brain(SM, X, C, outs, flt, sim, st, now, last_t, trades, gen), st)
    return {"trades": trades, "state": st, "brain": brain}


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
        t["cut_now"] = "CUT"
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


# ============================================================================================ the second-strategy brain
# One compact dict per strategy (owner 2026-10-22: "one brain is LIT, one brain shows whatever strategy you came with"):
#   stage / text      the strategy's own state line (waiting / armed / in_trade / done / off)
#   focus             which bar the checks are about: the live bar (last close), a signal, or today's trade's signal bar
#   checks            the strategy's rules in the engine's order, each {"k", "name", "ok" (True / False / None = not yet),
#                     "val", "need"}; the first False is why there is no trade
#   plan              entry / stop / target / risk / micros ($500) when armed or in a trade
#   log               today's evaluated setups (one line each: TRADE or the first failed rule)
# Built from the strategy's own arrays on closed bars only (inside its run, same data as the decision).
def _safe_brain(fn, st):
    """A brain bug never touches the strategy's trades: the error is shown in the brain instead."""
    try:
        return fn()
    except Exception as e:
        return {**basic_brain(st), "error": f"{e.__class__.__name__}: {e}"}


def _ck(k, name, ok, val=None, need=None):
    return {"k": k, "name": name, "ok": None if ok is None else bool(ok), **({"val": val} if val is not None else {}),
            **({"need": need} if need is not None else {})}


def _hhmm(m):
    m = int(m) % 1440
    return f"{m // 60:02d}:{m % 60:02d}"


def first_fail(checks):
    """The engine's reason: the first rule that failed (None = nothing failed)."""
    return next((c["k"] for c in checks or [] if c.get("ok") is False), None)


def _brain(st, focus, checks, plan=None, log=None, extra=None):
    b = {"stage": (st or {}).get("stage"), "text": (st or {}).get("text"), "focus": focus, "checks": checks,
         "first_fail": first_fail(checks), "plan": plan, "log": _trim_log(log, 12), "closed_bars_only": True}
    if extra:
        b.update(extra)
    return b


def _trim_log(log, n):
    """At most n lines: today's trade / signal lines always stay; setups outside the strategy's hours are summarised
    first, then the oldest of the rest go."""
    log = list(log or [])
    if len(log) <= n:
        return log
    keep = [x for x in log if x.get("trade") or x.get("signal")]
    rest = [x for x in log if not (x.get("trade") or x.get("signal"))]
    inw = [x for x in rest if x.get("ff") != "window" and x.get("t") is not None]
    nw = len(rest) - len(inw)
    room = max(0, n - len(keep) - (1 if nw else 0))
    out = sorted(keep + inw[-room:] if room else keep, key=lambda x: x.get("t") or 0)
    return ([{"t": None, "ok": False, "ff": "window", "text": f"{nw + max(0, len(inw) - room)} more setups (outside its hours / earlier)"}]
            if nw or len(inw) > room else []) + out


def brain_compact(b, max_log=6):
    """The heartbeat / live.json cut (about 2 KB per strategy): checks, plan, the last log lines, the S/R levels."""
    if not isinstance(b, dict):
        return None
    out = {k: b.get(k) for k in ("stage", "text", "focus", "first_fail", "plan", "error") if b.get(k) is not None}
    out["checks"] = [{k: v for k, v in c.items() if k in ("k", "name", "ok", "val", "need")} for c in b.get("checks") or []]
    out["log"] = [{k: v for k, v in x.items() if k in ("t", "ok", "text", "trade", "signal")} for x in _trim_log(b.get("log"), max_log)]
    if isinstance(b.get("levels"), list):
        out["levels"] = [{k: x.get(k) for k in ("name", "px", "known", "stage")} for x in b["levels"][:14]]
    return out


def _plan(dr, entry, stop, target, usd=500.0, when=None, est=False):
    if entry is None or stop is None:
        return None
    rp = abs(float(entry) - float(stop))
    q = max(1, min(40, int(float(usd) / (rp * PV)))) if rp > 0 else 0
    return {"dir": int(dr), "side": "long" if dr > 0 else "short", "entry": _r2(entry), "stop": _r2(stop), "target": _r2(target),
            "risk_pts": _r2(rp), "qty_500": q, "risk_usd": _r2(q * rp * PV), "when": when, "estimate": bool(est),
            "rr": _r2(abs(float(target) - float(entry)) / rp) if target is not None and rp > 0 else None}


# ---- EMA
def _ema_row_checks(SE, d, E, X, row, taken_before):
    a, z = SE.WINS[E["win"]]
    dr = int(row["dir"])
    lo = "low" if dr > 0 else "high"
    m = int(row['mod']) + 5
    C = [_ck("window", f"Entry {_hhmm(a)}-{_hhmm(z)} ET", a <= m < z, f"{_hhmm(m)} ET")]
    tr = E["trend"]
    if tr in ("t15", "t15_60", "all3"):
        C.append(_ck("t15", "15m EMA 21 vs EMA 50 points the trade's way", row["t15"] > 0, "with" if row["t15"] > 0 else "against"))
    if tr in ("t60", "t15_60", "t60_240", "all3"):
        C.append(_ck("t60", "1h EMA 21 vs EMA 50 points the trade's way", row["t60"] > 0, "with" if row["t60"] > 0 else "against"))
    if E["pull"] in ("e50", "e21"):
        k = "touch50" if E["pull"] == "e50" else "touch21"
        C.append(_ck("pull", f"Pullback reached the 5m EMA {E['pull'][1:]} (within 0.1 ATR)", row[k] > 0,
                     f"{float(row['depth']):.2f} ATR run"))
    if E.get("sweep"):
        C.append(_ck("sweep", f"Pullback {lo} swept a confirmed 5m swing {lo} (< 1.5 ATR)", row["swept"] > 0,
                     f"{float(row['sdepth']):.2f} ATR past it" if row["swept"] > 0 else "no swing taken"))
    if E.get("disp", 0) > 0:
        C.append(_ck("disp", f"CISD candle body >= {E['disp']} ATR", row["disp"] >= E["disp"], f"{float(row['disp']):.2f} ATR"))
    if E.get("reg") == "nomon":
        C.append(_ck("monday", "Not a Monday", int(row["dow"]) != 0, DOW[int(row["dow"])]))
    C.append(_ck("cisd", f"5m CISD close back {'up' if dr > 0 else 'down'} through the run's open", True, f"{dr * float(row['lvl']):,.2f}"))
    C.append(_ck("stop", "Stop 6-80 pts, 1 tick beyond the sweep wick", True, f"{float(row['risk']):.2f} pts"))
    C.append(_ck("one", "First trade of the day (max 1)", not taken_before))
    sim = SE.simulate(row, X, d) if first_fail(C) is None else None
    if first_fail(C) is None:
        C.append(_ck("target", "VIX-band target >= 1.5R away", sim is not None,
                     (f"{dr * float(sim[5]):,.2f}" if sim is not None and sim[5] is not None else "under 1.5R / no VIX")))
    else:
        C.append(_ck("target", "VIX-band target >= 1.5R away", None))
    return C, sim


def _ema_live_pull(SE, d, dr, i_last):
    """The counter-trend run in progress at the last closed bar (direction dr), tracked exactly as candidates() does."""
    n = d["n"]
    sid = d["sid"]
    s0 = sid[i_last]
    fh, fl = SE.fractal_masks(d["h"], d["l"])
    if dr > 0:
        O, H, L, C = d["o"], d["h"], d["l"], d["c"]
        FL = fl
    else:
        O, H, L, C = -d["o"], -d["l"], -d["h"], -d["c"]
        FL = fh
    bear = C < O
    start, lvl, low, active, last_s, prev_bear = -1, 0.0, 0.0, False, -1, -9
    swl = collections.deque(maxlen=20)
    for i in range(max(0, i_last - 300), min(n, i_last + 1)):
        s = sid[i]
        if s != last_s:
            active = False; last_s = s
        q = i - 2
        if q >= 0 and FL[q]:
            swl.append((q, L[q]))
        if bear[i]:
            if not active:
                start, lvl, low, active = i, O[i], L[i], True
            elif i != prev_bear + 1 and L[i] < low:
                lvl = O[i]
            prev_bear = i
            low = min(low, L[i])
            continue
        if not active:
            continue
        low = min(low, L[i])
        if i - start > 24:
            active = False
            continue
        if C[i] > lvl:
            active = False
    if not active or sid[start] != s0:
        return None
    a = d["atr"][i_last]
    sw = [p for (qq, p) in swl if qq + 2 < start and qq >= i_last - 48 and p > low and p - low < 1.5 * a]
    lowbar = start + int(np.argmin(L[start:i_last + 1]))
    e50 = dr * d["e50"][lowbar]
    return {"start_t": int(d["t"][start]), "lvl": float(dr * lvl), "low": float(dr * low), "touch50": bool(low <= e50 + 0.1 * a),
            "swept": bool(sw), "sdepth": float((max(sw) - low) / a) if sw else 0.0, "e50": float(d["e50"][i_last]),
            "close": float(d["c"][i_last])}


def _ema_brain(SE, d, E, X, U, st, cand, last_t, sig_row=None, d_sig=None):
    day = st.get("day")
    a, z = SE.WINS[E["win"]]
    today = cand[cand["day"] == day] if len(cand) else cand
    taken = {int(u["sig_i"]) for u in U if u["day"] == day}
    log, seen_trade = [], False
    for row in (x for _, x in today.iterrows()):
        C, _sim = _ema_row_checks(SE, d, E, X, row, seen_trade)
        ff = first_fail(C)
        is_t = int(row["sig"]) in taken
        pend = sig_row is not None and int(row["sig"]) == int(sig_row["sig"]) and int(row["dir"]) == int(sig_row["dir"])
        side = "long" if row["dir"] > 0 else "short"
        log.append({"t": int(d["t"][int(row["sig"])]) + 300, "ok": is_t or pend, "ff": ff, "dir": int(row["dir"]), "entry_t": int(d["t"][int(row["sig"])]) + 300, "trade": bool(is_t), "signal": bool(pend),
                    "text": f"{_hm(int(d['t'][int(row['sig'])]) + 300)} CISD {side}: " + ("TRADE" if is_t else "signal, enters at the next open"
                                                                                          if pend else f"no - {ff or 'no valid exit'}")})
        if is_t:
            seen_trade = True
    tr_today = [u for u in U if u["day"] == day]
    if tr_today:
        u = tr_today[0]
        row = next((r for r in (x for _, x in cand.iterrows()) if int(r["sig"]) == int(u["sig_i"]) and int(r["dir"]) == int(u["dir"])), None)
        C = _ema_row_checks(SE, d, E, X, row, False)[0] if row is not None else []
        return _brain(st, {"kind": "trade", "t": int(u["entry_t"]), "label": f"today's trade: signal {_hm(int(u['entry_t']))} ET"}, C,
                      _plan(u["dir"], u["entry"], u["stop"], u["target"], when=_hm(u["entry_t"])), log)
    if sig_row is not None and d_sig is not None:
        C, sim = _ema_row_checks(SE, d_sig, E, X, sig_row, False)
        dr = int(sig_row["dir"])
        tgt = dr * float(sim[5]) if sim is not None and sim[5] is not None else None
        return _brain(st, {"kind": "signal", "t": int(last_t) + 300, "label": f"signal on the {_hm(int(last_t) + 300)} ET close"}, C,
                      _plan(dr, dr * float(sig_row["e"]), dr * float(sig_row["stop"]), tgt, when=_hm(int(last_t) + 300), est=True), log)
    # live: the bar that just closed
    i = d["n"] - 1
    m_next = _mod(last_t + 300)
    t15, t60 = float(d["t15"][i]), float(d["t60"][i])
    dr = 1 if (t15 > 0 if t15 != 0 else t60 >= 0) else -1
    dow = dt.date.fromisoformat(trading_day(last_t + 300)).weekday()
    lo = "low" if dr > 0 else "high"
    run_ = _ema_live_pull(SE, d, dr, i)
    C = [_ck("window", f"Entry {_hhmm(a)}-{_hhmm(z)} ET", a <= m_next < z, f"next bar {_hhmm(m_next)} ET")]
    C.append(_ck("t15", "15m EMA 21 vs EMA 50 points the trade's way", t15 * dr > 0, {1: "up", -1: "down", 0: "flat"}[int(np.sign(t15))]))
    C.append(_ck("t60", "1h EMA 21 vs EMA 50 points the trade's way", t60 * dr > 0, {1: "up", -1: "down", 0: "flat"}[int(np.sign(t60))]))
    e50 = float(d["e50"][i])
    if run_ is None:
        C.append(_ck("pull", "Pullback reached the 5m EMA 50 (within 0.1 ATR)", None,
                     f"EMA 50 {e50:,.2f}, price {float(d['c'][i]):,.2f} ({abs(float(d['c'][i]) - e50):,.0f} pts away)",
                     need=f"a run of {'red' if dr > 0 else 'green'} 5m candles down to it"))
        C.append(_ck("sweep", f"Pullback {lo} swept a confirmed 5m swing {lo} (< 1.5 ATR)", None))
        C.append(_ck("cisd", "5m CISD close back through the run's open", None))
    else:
        C.append(_ck("pull", "Pullback reached the 5m EMA 50 (within 0.1 ATR)", True if run_["touch50"] else None,
                     f"EMA 50 {e50:,.2f}, run {lo} {run_['low']:,.2f} ({abs(run_['low'] - e50):,.0f} pts away)"))
        C.append(_ck("sweep", f"Pullback {lo} swept a confirmed 5m swing {lo} (< 1.5 ATR)", True if run_["swept"] else None,
                     f"{run_['sdepth']:.2f} ATR past it" if run_["swept"] else "not yet"))
        C.append(_ck("cisd", "5m CISD close back through the run's open", None, need=f"a 5m close {'above' if dr > 0 else 'below'} "
                                                                                  f"{run_['lvl']:,.2f}"))
    if E.get("reg") == "nomon":
        C.insert(3, _ck("monday", "Not a Monday", dow != 0, DOW[dow]))
    C += [_ck("stop", "Stop 6-80 pts, 1 tick beyond the sweep wick", None), _ck("one", "First trade of the day (max 1)", True),
          _ck("target", "VIX-band target >= 1.5R away", None)]
    return _brain(st, {"kind": "live", "t": int(last_t) + 300, "label": f"live: the {_hm(int(last_t) + 300)} ET close"}, C, None, log,
                  {"side": "long" if dr > 0 else "short"})


# ---- MACD
def _md_brain(SM, X, C, outs, flt, sim, st, now, last_t, trades, gen):
    n = X.n
    day_i = int(X.day[n - 1])
    kz = SM.KZ[flt["kz"]]
    win = ", ".join(f"{_hhmm(a)}-{_hhmm(b)}" for a, b in kz) + " ET"
    fil = SM.md_filter(flt)
    busy, cnt, info = -1, collections.Counter(), {}
    for idx, (z, r) in enumerate(zip(C, outs)):
        why = None
        if r is None:
            why = "pending" if z["j"] == n - 1 else "fill"
        elif r["x0"] <= busy:
            why = "busy"
        elif not fil(z["f"]):
            why = "depth"
        elif not SM.in_kz(int(X.Xm[r["x0"]]), flt["kz"]):
            why = "window"
        elif cnt[int(X.Xday[r["x0"]])] >= flt["maxpd"]:
            why = "one"
        else:
            cnt[int(X.Xday[r["x0"]])] += 1
            busy = r["x1"]
        info[idx] = why

    def checks(z, r, why):
        dr = z["dir"]
        lo = "low" if dr > 0 else "high"
        dv = z.get("div") or {}
        m = int(X.Xm[r["x0"]]) if r is not None else _mod(int(X.t[z["j"]]) + 300)
        out = [_ck("swept", f"A LIT level ({lo}) taken", True, f"{float(z.get('level', z['ext'])):,.2f} at {_hm(int(X.t[z.get('sweep_i', z['j'])]))} ET"),
               _ck("cisd", "5m CISD close back", True, f"{float(z['cisd']):,.2f}"),
               _ck("div", f"MACD line divergence at the {lo} (weaker than at the prior swing)", True,
                   f"MACD {dv.get('osc_ext', float('nan')):.2f} vs {dv.get('osc_prior', float('nan')):.2f} at {dv.get('px_prior', float('nan')):,.2f}"),
               _ck("fill", "Fill at the next open, stop 6-80 pts, VIX target >= 1.5R", None if why == "pending" else why != "fill",
                   f"{r['risk']:.2f} pts" if r is not None else None),
               _ck("busy", "Not inside an earlier trade", None if why in ("pending", "fill") else why != "busy"),
               _ck("depth", f"Sweep depth >= {flt['depth']} ATR", z["f"]["depth"] >= flt["depth"], f"{z['f']['depth']:.2f} ATR"),
               _ck("window", f"Entry {win}", SM.in_kz(m, flt["kz"]), f"{_hhmm(m)} ET"),
               _ck("one", f"Max {flt['maxpd']} a day", None if why in ("pending", "fill", "busy", "depth", "window") else why != "one")]
        return out
    log = []
    today = [(i, z) for i, z in enumerate(C) if int(X.day[z["j"]]) == day_i]
    for i, z in today:
        why = info[i]
        side = "long" if z["dir"] > 0 else "short"
        log.append({"t": int(X.t[z["j"]]) + 300, "ok": why is None, "ff": None if why == "pending" else why, "dir": int(z["dir"]), "entry_t": int(X.t[z["j"]]) + 300, "trade": why is None, "signal": why == "pending",
                    "text": f"{_hm(int(X.t[z['j']]) + 300)} MACD-div {side}: " + ("TRADE" if why is None else
                                                                                 "signal, enters at the next open" if why == "pending" else f"no - {why}")})
    td = [t for t in trades if t["day"] == X.dates[day_i]]
    if td:
        t = td[-1]
        k = next((i for i, z in today if info[i] is None and outs[i] is not None and int(X.Xt[outs[i]["x0"]]) == int(t["entry_t"])), None)
        Cc = checks(C[k], outs[k], None) if k is not None else []
        return _brain(st, {"kind": "trade", "t": int(t["entry_t"]), "label": f"today's trade: {_hm(int(t['entry_t']))} ET"}, Cc,
                      _plan(t["dir"], t["entry"], t["stop"], t["target"], when=_hm(t["entry_t"])), log)
    last = [(i, z) for i, z in today if z["j"] == n - 1]
    if last:
        i, z = last[0]
        Cc = checks(z, outs[i], info[i])
        e = float(X.c[n - 1])
        cx = X.M.ctx[day_i] if day_i < len(X.M.ctx) else {}
        tp = None
        if cx.get("vix_move") and sim.get("tgt") == "vix":            # the VIX band from the next open (estimate: the last close)
            dist = (cx["open18"] + z["dir"] * cx["vix_move"] - e) * z["dir"]
            rk = abs(e - z["stops"]["ext"])
            tp = e + z["dir"] * min(dist, 8.0 * rk) if rk > 0 and dist >= 1.5 * rk else None
        return _brain(st, {"kind": "signal", "t": int(last_t) + 300, "label": f"signal on the {_hm(int(last_t) + 300)} ET close"}, Cc,
                      _plan(z["dir"], e, z["stops"]["ext"], tp, when=_hm(int(last_t) + 300), est=True), log)
    if today:                                           # the latest setup of today (rejected): its checks
        i, z = today[-1]
        Cc = checks(z, outs[i], info[i])
        return _brain(st, {"kind": "setup", "t": int(X.t[z["j"]]) + 300, "label": f"last setup: {_hm(int(X.t[z['j']]) + 300)} ET"}, Cc,
                      None, log)
    # live: an armed sweep (a level taken >= depth in the last 2 hours) waiting for the CISD + divergence
    m_next = _mod(last_t + 300)
    s0 = X.M.days[day_i][1]
    best = None
    for i, dr, px in SM.sweep_events(X, SM.LV[gen["lv"]]):
        if s0 <= i < n and i >= n - 24:
            ext = float(X.l[i:n].min()) if dr > 0 else float(X.h[i:n].max())
            dep = (px - ext) * dr / X.atr[i] if X.atr[i] > 0 else 0.0
            best = (i, dr, px, ext, dep)
    Cc = [_ck("window", f"Entry {win}", SM.in_kz(m_next, flt["kz"]), f"next bar {_hhmm(m_next)} ET")]
    if best:
        i, dr, px, ext, dep = best
        lo = "low" if dr > 0 else "high"
        Cc += [_ck("swept", f"A LIT level ({lo}) taken", True, f"{px:,.2f} at {_hm(int(X.t[i]))} ET, extreme {ext:,.2f}"),
               _ck("depth", f"Sweep depth >= {flt['depth']} ATR", True if dep >= flt["depth"] else None, f"{dep:.2f} ATR"),
               _ck("cisd", "5m CISD close back", None, need=f"until {_hm(int(X.t[i]) + 24 * 300)} ET"),
               _ck("div", "MACD line divergence at the extreme", None)]
    else:
        Cc += [_ck("swept", "A LIT level taken", None, need="session high/low, PDH/PDL, PWH/PWL, equal highs/lows..."),
               _ck("depth", f"Sweep depth >= {flt['depth']} ATR", None), _ck("cisd", "5m CISD close back", None),
               _ck("div", "MACD line divergence at the extreme", None)]
    Cc.append(_ck("one", f"Max {flt['maxpd']} a day", True))
    return _brain(st, {"kind": "live", "t": int(last_t) + 300, "label": f"live: the {_hm(int(last_t) + 300)} ET close"}, Cc, None, log)


# ---- S/R
SR_NAMES = {"pdh": "yesterday's RTH high", "pdl": "yesterday's RTH low", "onh": "overnight high", "onl": "overnight low",
            "ash": "Asia high", "asl": "Asia low", "loh": "London high", "lol": "London low", "orh": "opening-range high",
            "orl": "opening-range low", "pwh": "last week's high", "pwl": "last week's low"}


def sr_scan(SR, d, key, s=None):
    """Every level of a session (default the last) through gen_reclaim's steps in its order, recorded instead of skipped:
    known yet -> swept (first trade-through from the other side) -> reclaim close within W bars -> depth -> body >= disp
    ATR -> inducement swing taken first. Same arithmetic as tools/second_sr.gen_reclaim (tests/test_second.py checks it)."""
    o, h, l, c, atr, rel = d["o"], d["h"], d["l"], d["c"], d["atr"], d["rel"]
    n = d["n"]
    sess = [x for x in d["sess"] if s is None or x[0] == s]
    if not sess:
        return []
    s, a, b = sess[-1]
    L = SR.levels(d, SR.LV_SETS[key["lv"]]).get(s) or []
    fl, fh = d["fl"], d["fh"]
    b2 = min(b, n)
    out = []
    for p, nm, fr in L:
        rec = {"name": nm, "label": SR_NAMES.get(nm, nm), "px": _r2(p), "known": bool(rel[b2 - 1] >= fr), "steps": []}
        out.append(rec)
        if not rec["known"]:
            continue
        j0 = a + int(np.searchsorted(rel[a:b2], fr + 5)) if fr > 0 else a + 1
        j0 = max(j0, a + 1)
        jj = None
        for j in range(j0, b2):
            if rel[j] >= 1315:
                break
            if c[j - 1] > p and l[j] < p:
                jj, dr = j, 1; break
            if c[j - 1] < p and h[j] > p:
                jj, dr = j, -1; break
        if jj is None:
            rec["stage"] = "not swept"
            continue
        j = jj
        A = atr[j - 1]
        if dr > 0:
            cd, od, ld, pp = c, o, l, p
        else:
            cd, od, ld, pp = -c, -o, -h, -p
        rec.update(dir=dr, swept_t=int(d["t"][j]))
        ext = ld[j]; r = None
        for q in range(j, min(j + key["W"], b2)):
            if rel[q] >= 1315:
                break
            ext = min(ext, ld[q])
            if cd[q] > pp:
                r = q; break
        if r is None:
            rec["stage"] = "swept, no reclaim close" + (" yet" if j + key["W"] > b2 - 1 else f" within {key['W']} bars")
            rec["wait"] = j + key["W"] > b2 - 1
            continue
        rec["reclaim_t"] = int(d["t"][r])
        rec["sig"] = int(r)
        rec["depth_ok"] = bool(pp - ext >= key["depth"] * A)
        rec["body"] = round(float((cd[r] - od[r]) / A), 2) if A > 0 else 0.0
        rec["body_ok"] = not (key["disp"] > 0 and (cd[r] - od[r]) < key["disp"] * A)
        ok = False
        if key["idm"]:
            F = fl if dr > 0 else fh
            lo_i = bisect.bisect_left(F, j - 36); hi_i = bisect.bisect_left(F, j - 2)
            for f in F[lo_i:hi_i]:
                fp = l[f] if dr > 0 else -h[f]
                if pp < fp <= pp + A and f >= a:
                    ok = True; break
        rec["idm_ok"] = ok if key["idm"] else True
        rec["stop"] = _r2(dr * (ext - TICK))
        rec["gen_ok"] = rec["depth_ok"] and rec["body_ok"] and rec["idm_ok"]
        rec["stage"] = "reclaimed" if rec["gen_ok"] else ("reclaimed, rejected: " + ("depth" if not rec["depth_ok"] else
                                                                                   "body" if not rec["body_ok"] else "inducement"))
    return out


def _sr_brain(SR, d, key, st, TT, now, last_t):
    n = d["n"]
    a, z = SR.WINDOWS[key["win"]]
    win = f"{_hhmm(a)}-{_hhmm(z)} ET"
    scan = sr_scan(SR, d, key)
    oc = SR.oc_of(key)
    cb = (key["tg"], key["bk"], key["be"], key["tc"])
    busy, cnt, why = -1, collections.Counter(), {}
    for x in oc:                                                  # tools/second_sr.select's order, the reason recorded
        k = (int(x["sig"]), int(x["dir"]), x["nm"])
        if x["k0"] <= busy:
            why[k] = "busy"; continue
        if x["risk"] > key.get("max_stop", 80.0):
            why[k] = "stop"; continue
        if not (a <= x["mod"] < z):
            why[k] = "window"; continue
        r = x["tab"].get(cb)
        if r is None:
            why[k] = "target"; continue
        if cnt[x["s"]] >= key["maxpd"]:
            why[k] = "one"; continue
        why[k] = None
        busy = x["k0"] + r[1]
        cnt[x["s"]] += 1
    in_oc = {(int(x["sig"]), int(x["dir"]), x["nm"]): x for x in oc}

    def checks(rec):
        dr = rec.get("dir") or 1
        lo = "low" if dr > 0 else "high"
        k = (rec.get("sig", -1), dr, rec["name"])
        x = in_oc.get(k)
        w = why.get(k, "fill" if rec.get("gen_ok") and rec.get("sig", -1) < n - 1 else None)
        pend = rec.get("gen_ok") and rec.get("sig") == n - 1
        m = int(x["mod"]) if x else (_mod(int(d["t"][rec["sig"]]) + 300) if rec.get("sig") is not None else _mod(last_t + 300))
        C = [_ck("known", "Level known (from closed bars)", rec["known"], f"{rec['label']} {rec['px']:,.2f}"),
             _ck("swept", f"Swept from the other side ({lo} taken)", True if rec.get("swept_t") else None,
                 _hm(rec["swept_t"]) + " ET" if rec.get("swept_t") else None),
             _ck("reclaim", f"5m close back {'above' if dr > 0 else 'below'} it within {key['W']} bars", True if rec.get("reclaim_t") else
                 (False if rec.get("swept_t") and not rec.get("wait") else None), _hm(rec["reclaim_t"]) + " ET" if rec.get("reclaim_t") else None),
             _ck("body", f"Reclaim candle body >= {key['disp']} ATR", rec.get("body_ok") if rec.get("reclaim_t") else None,
                 f"{rec['body']:.2f} ATR" if rec.get("reclaim_t") else None),
             _ck("idm", "Inducement swing (within 1 ATR beyond) taken first", rec.get("idm_ok") if rec.get("reclaim_t") else None),
             _ck("fill", "Fill at the next open, stop 6-120 pts", None if not rec.get("gen_ok") or pend else (x is not None),
                 f"{x['risk']:.2f} pts" if x else None),
             _ck("busy", "Not inside an earlier trade (one position at a time)", None if x is None else w != "busy"),
             _ck("stop", f"Stop <= {key.get('max_stop', 80.0):.0f} pts", None if x is None or w == "busy" else w != "stop"),
             _ck("window", f"Entry {win}", (a <= m < z) if rec.get("reclaim_t") else None, f"{_hhmm(m)} ET" if rec.get("reclaim_t") else None),
             _ck("one", f"Max {key['maxpd']} a day", None if x is None or w in ("busy", "stop", "window", "target") else w != "one")]
        if key["depth"] > 0:
            C.insert(3, _ck("depth", f"Sweep depth >= {key['depth']} ATR", rec.get("depth_ok") if rec.get("reclaim_t") else None))
        return C, w, pend
    log, best = [], None
    for rec in sorted([r for r in scan if r.get("swept_t")], key=lambda r: r.get("reclaim_t") or r["swept_t"]):
        C, w, pend = checks(rec)
        ff = first_fail(C)
        taken = rec.get("gen_ok") and w is None and not pend and (rec.get("sig", -1), rec.get("dir"), rec["name"]) in in_oc
        side = "long" if (rec.get("dir") or 1) > 0 else "short"
        log.append({"t": int(rec.get("reclaim_t") or rec["swept_t"]) + 300, "ok": bool(taken), "ff": ff, "dir": int(rec.get("dir") or 1), "entry_t": (int(rec["reclaim_t"]) + 300) if rec.get("reclaim_t") else None, "trade": bool(taken), "signal": bool(pend), "level": rec["name"],
                    "text": f"{_hm(int(rec.get('reclaim_t') or rec['swept_t']) + 300)} {rec['label']} swept ({side}): "
                            + ("TRADE" if taken else "signal, enters at the next open" if pend else f"no - {ff}" if ff else rec.get("stage", ""))})
        best = (rec, C, pend) if best is None or taken or pend or not best[2] else best
    levels = [{"name": r["name"], "label": r["label"], "px": r["px"], "known": r["known"], "stage": r.get("stage") or ("waiting" if r["known"] else "not known yet")}
              for r in scan]
    td = [t for t in TT if t["day"] == str(d["days"][int(d["sid"][n - 1])])]
    plan = None
    if td:
        t = td[-1]
        plan = _plan(t["dir"], t["entry"], t["stop"], t["target"], when=_hm(t["entry_t"]))
        rec = next((r for r in scan if r.get("sig") is not None and int(d["t"][r["sig"]]) + 300 == int(t["entry_t"])), None)
        Cc = checks(rec)[0] if rec else []
        focus = {"kind": "trade", "t": int(t["entry_t"]), "label": f"today's trade: {_hm(int(t['entry_t']))} ET"}
    elif best is not None:
        rec, Cc, pend = best
        focus = {"kind": "signal" if pend else "setup", "t": int(rec.get("reclaim_t") or rec["swept_t"]) + 300,
                 "label": (f"signal on the {_hm(int(rec['reclaim_t']) + 300)} ET close" if pend else f"last setup: {rec['label']}")}
        if pend:
            e = float(d["c"][n - 1])
            sp = float(rec["stop"])
            plan = _plan(rec["dir"], e, sp, e + rec["dir"] * key["tg"] * abs(e - sp), when=_hm(int(last_t) + 300), est=True)
    else:
        m_next = _mod(last_t + 300)
        Cc = [_ck("window", f"Entry {win}", a <= m_next < z, f"next bar {_hhmm(m_next)} ET"),
              _ck("known", "Levels of the day known", any(r["known"] for r in scan), f"{sum(1 for r in scan if r['known'])} of {len(scan)}"),
              _ck("swept", "A level swept from the other side", None), _ck("reclaim", "5m close back over it", None),
              _ck("body", f"Reclaim candle body >= {key['disp']} ATR", None), _ck("idm", "Inducement swing taken first", None)]
        focus = {"kind": "live", "t": int(last_t) + 300, "label": f"live: the {_hm(int(last_t) + 300)} ET close"}
    return _brain(st, focus, Cc, plan, log, {"levels": levels})


# ============================================================================================ STOP-HUNT candidates (paper)
# research/writeups/stophunt.md (2026-10-23): the Asia resweep hunt (sh_asia_resweep) and the trend inducement hunt
# (sh_trend_idm5), candidate ATLAS members, PAPER ONLY (never routed, not on account B). Same code as the research:
# tools/stophunt.live = one() / FINAL's pipeline (engine/stophunt pools / hunts / _signals / _fill / _walk, select_stats)
# on LIT's window, data cut at the poll (closed bars only), a trade the bars end inside = OPEN.
SH_TYPE = {"f1": "1m swing", "f5": "5m swing", "f15": "15m swing", "f60": "1h swing", "eq5": "5m equal", "eq15": "15m equal",
           "range": "range edge", "tl": "trendline", "asia": "Asia", "lon": "London", "ny": "prior NY", "on": "overnight",
           "pd": "prior day", "pw": "prior week", "r100": "round x00", "r50": "round x50"}
SH_MODE = {"rs": ("rs", "Resweep: the pool re-run after a close back inside, or the hunt's new extreme taken after a 0.5 ATR bounce"),
           "pre": ("pre", "Inducement first: a 5m swing within 1 ATR of the pool was taken on the way in"),
           "idm": ("idm", "Inducement after the hunt: the early reversal traders' swing taken"),
           "rs_or_idm": ("rs", "A resweep or an inducement after the hunt")}


def _sh_1m(one_min, t0, now):
    """The 1m bars as a frame (time, open, high, low, close) from t0, closed by `now` (a feed frame or research Bars)."""
    if one_min is None:
        return None
    if hasattr(one_min, "t") and hasattr(one_min, "o"):
        d = pd.DataFrame({"time": np.asarray(one_min.t, np.int64), "open": one_min.o, "high": one_min.h, "low": one_min.l, "close": one_min.c})
    else:
        d = one_min[["time", "open", "high", "low", "close"]].copy()
        d["time"] = d["time"].astype(np.int64)
    d = d[(d["time"] >= t0) & (d["time"] + 60 <= now) & (d["time"] % 60 == 0)]
    return d.reset_index(drop=True) if len(d) else None


def _sh_side(dr):
    return "long" if dr > 0 else "short"


@plugin("stop_hunt")
def _sh_run(df5, one_min, cfg, now, lit):
    from tools import stophunt as SH
    spec = {**SH.FINAL.get(cfg.get("pick"), {}), **(cfg.get("params") or {})}
    spec.setdefault("name", cfg.get("pick") or "stophunt")
    w = _window(df5)
    w = w[w["time"] + 300 <= now].reset_index(drop=True)          # closed 5m bars only
    last_t = int(w["time"].iloc[-1])
    d1 = _sh_1m(one_min, int(w["time"].min()), now)
    L = SH.live(spec, w, d1, now=now, is_open=lambda d: _session_open(d, now, last_t + 300))
    trades = []
    for r in L["rows"]:
        open_ = r["open"]
        t = {"day": r["day"], "entry_t": int(r["entry_t"]), "exit_t": None if open_ else int(r["exit_t"]), "dir": int(r["dir"]),
             "entry": r["entry"], "stop": r["stop"], "target": r["target"], "exit": None if open_ else r["exit"],
             "exit_kind": "OPEN" if open_ else str(r["exit_kind"]).upper(), "r": r["r"], "qty": int(r["qty"]), "usd": r["pnl_usd"],
             "risk_pts": r["risk_pts"], "risk_usd": round(r["qty"] * r["risk_pts"] * PV, 2), "setup": cfg.get("label") or spec["name"],
             "last": r.get("last") if open_ else None, "stop_now": r.get("stop_now") if open_ else None,
             "signal_t": int(r["signal_t"]), "hunt_t": int(r["hunt_t"]), "pool_px": r["pool_px"], "path": r["path"]}
        # LIT first on one account (the EMA rule): no entry while a LIT trade is open (research: own account / ATLAS member)
        t["lit"] = {"taken": not _in_lit(lit, t["entry_t"]), "usd": t["usd"], "exit_kind": t["exit_kind"]}
        if not t["lit"]["taken"]:
            t["lit"].update(usd=0.0, why="LIT was in a trade")
        trades.append(t)
    _session_end(trades, now, last_t)
    info = _sh_info(SH, L, spec, cfg, trades, now, last_t)
    st = info["state"]
    brain = _safe_brain(lambda: _sh_brain(SH, L, spec, cfg, trades, info, now, last_t), st)
    return {"trades": trades, "state": st, "brain": brain}


def _sh_win(SH, spec):
    m = SH.WINDOWS[spec["win"]]
    edges = [(0, 240), (240, 480), (480, 840), (840, 1080), (1080, 1290)]      # rel (minutes since 18:00 ET) per bucket bit
    ok = lambda rel: any((m >> b) & 1 and a <= rel < z for b, (a, z) in enumerate(edges))
    return ok, SH.WIN_TXT[spec["win"]]


def _sh_info(SH, L, spec, cfg, trades, now, last_t):
    """Today's stage (waiting / armed / in_trade / done / off) and the pending signal / limit of a stop-hunt pick."""
    g = L["g"]; B = g["B"]; sg = L["sg"]
    n = B["n"]
    s_last = int(B["sid"][n - 1])
    nxt = last_t + 300
    rel_next = (_mod(nxt) - 1080) % 1440
    new_sess = rel_next == 0                                   # 18:00: the next bar opens a new session
    day = trading_day(nxt)
    win_ok, win_txt = _sh_win(SH, spec)
    st = {"day": day, "window": win_txt, "price": _r2(B["c"][n - 1]), "atr": _r2(B["atr"][n - 1]), "candidate": True}
    today = [t for t in trades if t["day"] == day]
    ctx = SH.context(g) if spec["ctx"] != "none" else None
    trend = int(np.sign(ctx["trend"][n - 1])) if ctx is not None else 0
    if ctx is not None:
        st["trend_1h"] = {1: "up", -1: "down", 0: "flat"}[trend]
    # a signal on the last closed bar (market: the next open; limit: the trigger candle's middle for 30 minutes)
    pend = []
    for i in range(len(sg["sig"])):
        k = int(sg["sig"][i])
        if k < n - (6 if spec["entry"] in ("mid", "fvg") else 1) or new_sess and k == n - 1:
            continue
        dr = int(sg["dr"][i])
        if not win_ok(int(B["rel"][k])) or (ctx is not None and not SH.ctx_ok(g, {"sig": np.array([k]), "dr": np.array([dr])}, spec["ctx"])[0]):
            continue
        tsig = int(B["t"][k]) + 300
        if spec["entry"] in ("mid", "fvg") and nxt >= tsig + 1800:
            continue
        if any(t["signal_t"] == tsig for t in trades):
            continue
        lim = float(sg["mid"][i] if spec["entry"] == "mid" else sg["fvg"][i]) * dr if spec["entry"] in ("mid", "fvg") else None
        stop = round(dr * (float(sg["ext"][i]) - 0.25), 2)
        pend.append({"dir": dr, "signal_t": tsig, "stop": stop, "limit": _r2(lim), "pool": _r2(dr * float(sg["p"][i])),
                     "enter_at": _hm(tsig) if lim is None else f"{_hm(tsig)}-{_hm(tsig + 1800)}", "kind": "market" if lim is None else "limit"})
    busy = any(t["exit_kind"] == "OPEN" for t in trades)
    n_sess = sum(1 for t in today)
    if pend and not busy and n_sess < spec["mp"]:
        st["signal"] = pend[-1]
    if busy:
        t = next(t for t in trades if t["exit_kind"] == "OPEN")
        st.update(stage="in_trade", text=f"In a paper {_sh_side(t['dir'])} from {_hm(t['entry_t'])} ET at {t['entry']:,.2f}, stop "
                                          f"{t['stop_now']:,.2f}, target {t['target']:,.2f} (2R)")
    elif n_sess >= spec["mp"]:
        t = today[-1]
        st.update(stage="done", text=f"Done for this session (max {spec['mp']}): {_sh_side(t['dir'])} {_hm(t['entry_t'])} ET -> "
                                     f"{str(t['exit_kind']).lower()} {float(t['r']):+.2f}R")
    elif st.get("signal"):
        s = st["signal"]
        st.update(stage="armed", text=(f"Signal ({_sh_side(s['dir'])}): the stop hunt of {s['pool']:,.2f} reversed with a strong candle "
                                       f"on the {_hm(s['signal_t'] - 300)} ET bar; " +
                                       (f"paper entry at the {s['enter_at']} ET open" if s["kind"] == "market" else
                                        f"paper limit at {s['limit']:,.2f} ({s['enter_at']} ET)") + f", stop {s['stop']:,.2f}"))
    elif not win_ok(rel_next if not new_sess else 0) or rel_next > 1290:
        st.update(stage="off", text=f"Outside its hours: entries {win_txt}" + (" (next: 18:00 ET)" if spec["win"].startswith("asia") else ""))
    else:
        st.update(stage="waiting", text="Waiting for a stop hunt: " + ("a 15m / 1h / session / day / week high or low run by 0.5 ATR, a resweep, "
                                                                       "then a 5m candle >= 1.2 ATR back through it and the last swing"
                                                                       if spec["mode"] == "rs" else
                                                                       f"a pullback against the 1h trend ({st.get('trend_1h', '-')}) that takes an "
                                                                       "inducement swing and runs a 5m swing, then a 5m candle >= 1.2 ATR back with the trend"))
    return {"state": st, "pend": pend, "win_ok": win_ok, "ctx": ctx, "s_last": s_last, "day": day}


def _sh_checks(SH, spec, g, x, ctx, win_ok, row=None, upto_last=True):
    """Rule checks of one hunt (tools/stophunt.explain) in the engine's order."""
    B = g["B"]
    dr = x["dr"]
    lo = "low" if dr > 0 else "high"
    q = x["trigger"] or x["last"] or {}
    trig = x["trigger"] is not None
    A = x["atr"] or 1.0
    kb = SH.BODY_SPEC[spec["body"]][0]
    names = ", ".join(SH_TYPE.get(tp, tp) for tp in x["types"])
    dep_ok = (x["last"] or {}).get("depth", 0.0) >= spec["depth"] if not trig else True
    mk, mtxt = SH_MODE.get(spec["mode"], (None, None))
    rel_f = int(B["rel"][q["q"] if q else int(np.searchsorted(B["t"], x["t"]))])
    C = [_ck("window", "Hours: " + SH.WIN_TXT[spec["win"]], win_ok(rel_f) and rel_f <= 1290,
             f"{'signal' if trig else 'bar'} {_hhmm(rel_f + 1085)} ET"),
         _ck("pool", f"Pool hunted: {SH.POOL_SETS[spec['pool']][4]}", True, f"{names} {lo} {x['pool']:,.2f} run at {_hm(x['t'])} ET"),
         _ck("depth", f"Hunt depth >= {spec['depth']} ATR beyond the pool", dep_ok if (trig or x["expired"] or dep_ok) else None,
             f"{(q.get('depth') or 0):.2f} ATR ({lo} {x['ext']:,.2f})")]
    if mk == "pre":
        C.append(_ck("pre", mtxt, x["pre"]))
    elif mk:
        seen = q.get("rs") if mk == "rs" else q.get("idm")
        C.append(_ck(mk, mtxt, True if seen else (False if x["expired"] else None)))
    if spec["ctx"] == "with" and ctx is not None:
        k = (q.get("q") if q else int(np.searchsorted(B["t"], x["t"])))
        tr = int(np.sign(ctx["trend"][k])) if k is not None else 0
        C.append(_ck("trend", "With the 1h trend (last closed 1h close vs its EMA 50): the hunt is a pullback against it",
                     tr * dr > 0, {1: "1h trend up", -1: "1h trend down", 0: "1h trend flat"}[tr]))
    body = q.get("body")
    big = body is not None and body >= q.get("thr", 1e9) and body > 0
    C += [_ck("disp", f"Strong candle back: body >= {kb} x ATR", True if trig else (None if not x["expired"] else bool(big) and False),
              f"last {body:,.2f} pts = {body / A:.2f} ATR (needs {q.get('thr', 0):,.2f})" if body is not None else None),
          _ck("pool_close", f"Close back {'above' if dr > 0 else 'below'} the pool", True if trig else (None if not x["expired"] else False)),
          _ck("mss", f"Close beyond the last 5m swing {'high' if dr > 0 else 'low'} (structure shift)", True if trig else
              (None if not x["expired"] else False), f"swing {q['lvl']:,.2f}" if q.get("lvl") is not None else "no swing in the last 4 h"),
          _ck("within", f"Within {spec['W']} 5m bars of the hunt", True if trig else (None if not x["expired"] else False), f"until {_hm(x['until_t'])} ET")]
    if trig:
        C.append(_ck("taken", f"Filled with a 6-{spec['max_stop']:.0f} pt stop, one position, max {spec['mp']} a session", True if row else
                     (None if upto_last and q["q"] >= B["n"] - 6 else False), f"{row['risk_pts']:.2f} pts stop" if row else None))
    # the first failure of an expired hunt: report it at the first unmet trigger rule
    if x["expired"] and not trig:
        for c in C:
            if c["ok"] is None:
                c["ok"] = False
                break
    return C


def _sh_brain(SH, L, spec, cfg, trades, info, now, last_t):
    g = L["g"]; B = g["B"]
    n = B["n"]
    st, ctx, win_ok = info["state"], info["ctx"], info["win_ok"]
    s_last = info["s_last"]
    ev = SH.ev_of(g, spec["pool"])
    a0 = int(B["sess_start"][s_last])
    js = sorted({int(j) for j in ev["j"] if j >= a0 and B["rel"][j] <= SH.E.ENTRY_CUT})     # hunts after 15:30 are no setups
    if info["day"] != str(B["days"][s_last]):
        js = []                                                   # 17:55 close: the next session has no bar yet
    by_sig = {t["signal_t"]: t for t in trades}
    log, items = [], []
    for j in js[-200:]:
        for x in SH.explain(g, spec, j):
            q = x["trigger"]
            row = by_sig.get(int(q["t"]) + 300) if q else None
            C = _sh_checks(SH, spec, g, x, ctx, win_ok, row)
            ff = first_fail(C)
            sig_now = q is not None and q["q"] == n - 1 and row is None and ff is None
            lo = "low" if x["dr"] > 0 else "high"
            txt = (f"{_hm(x['t'] + 300)} {', '.join(SH_TYPE.get(tp, tp) for tp in x['types'])} {lo} {x['pool']:,.2f} hunted ({_sh_side(x['dr'])}): "
                   + ("TRADE " + _hm(row["entry_t"]) + " ET" if row else "signal, " + ("enters at the next open" if spec["entry"] == "mkt" else "limit at mid-candle") if sig_now
                      else f"no - {ff}" if ff else "watching"))
            log.append({"t": int(x["t"]) + 300, "ok": bool(row), "ff": ff, "dir": x["dr"], "trade": bool(row), "signal": bool(sig_now), "text": txt})
            items.append((x, C, row, sig_now))
    today = [t for t in trades if t["day"] == info["day"]]
    plan, focus, Cc = None, None, None
    sig_items = [i for i in items if i[3]] if st.get("signal") else []
    if today and (not sig_items or any(t["exit_kind"] == "OPEN" for t in today)):
        t = today[-1]
        plan = _plan(t["dir"], t["entry"], t.get("stop_now") or t["stop"], t["target"], when=_hm(t["entry_t"]))
        it = next((i for i in items if i[2] is t), None)
        Cc = it[1] if it else []
        focus = {"kind": "trade", "t": int(t["entry_t"]), "label": f"today's trade: {_hm(int(t['entry_t']))} ET"}
    else:
        live_items = sig_items or [i for i in items if not i[0]["expired"] and i[0]["trigger"] is None]
        if live_items:
            x, Cc, row, sig_now = live_items[-1]
            focus = {"kind": "signal" if sig_now else "setup", "t": int(x["t"]) + 300,
                     "label": (f"signal on the {_hm(int(B['t'][n - 1]) + 300)} ET close" if sig_now else f"hunt at {_hm(x['t'] + 300)} ET, watching")}
            s = st.get("signal")
            if s:
                e = float(s["limit"]) if s.get("limit") is not None else float(B["c"][n - 1])
                plan = _plan(s["dir"], e, s["stop"], e + s["dir"] * 2.0 * abs(e - s["stop"]), when=s["enter_at"], est=True)
        elif items:
            x, Cc, row, sig_now = items[-1]
            focus = {"kind": "setup", "t": int(x["t"]) + 300, "label": f"last hunt: {_hm(x['t'] + 300)} ET"}
        else:
            rel_next = (_mod(last_t + 300) - 1080) % 1440
            Cc = [_ck("window", "Hours: " + SH.WIN_TXT[spec["win"]], win_ok(rel_next) and rel_next <= 1290, f"next bar {_hm(last_t + 300)} ET"),
                  _ck("pool", f"Pool hunted: {SH.POOL_SETS[spec['pool']][4]}", None), _ck("depth", f"Hunt depth >= {spec['depth']} ATR", None)]
            mk, mtxt = SH_MODE.get(spec["mode"], (None, None))
            if mk:
                Cc.append(_ck(mk, mtxt, None))
            if spec["ctx"] == "with":
                Cc.append(_ck("trend", "With the 1h trend (EMA 50)", None, f"1h trend {st.get('trend_1h', '-')}"))
            Cc += [_ck("disp", f"Strong candle back: body >= {SH.BODY_SPEC[spec['body']][0]} x ATR", None,
                       f"{SH.BODY_SPEC[spec['body']][0] * float(B['atr'][n - 1]):,.2f} pts now"),
                   _ck("mss", "Close beyond the pool and the last 5m swing (structure shift)", None)]
            focus = {"kind": "live", "t": int(last_t) + 300, "label": f"live: the {_hm(int(last_t) + 300)} ET close"}
    return _brain(st, focus, Cc, plan, log, {"candidate": True})


def basic_brain(st, label=None):
    """A strategy without its own brain (e.g. the LIT + Asia shadow): its stage and plain state line only."""
    return _brain(st, {"kind": "live", "label": label or "state"}, [], None, [])


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
        base = {"label": sc.get("label") or key, "short": sc.get("short") or key, "on": bool(sc.get("on", True)),
                "route": bool(sc.get("route")), **({"candidate": True} if sc.get("candidate") else {})}
        if not base["on"]:
            out["strategies"][key] = {**base, "trades": [], "state": {"stage": "off", "text": "Switched off in second_model.json"}}
            continue
        try:
            if sc.get("module"):
                fn = getattr(importlib.import_module(sc["module"]), "live_run")
            else:
                fn = PLUGINS[sc["kind"]]
            r = fn(df5, one_min, sc, now, lit)
            out["strategies"][key] = {**base, "trades": r["trades"], "state": r["state"], **({"brain": r["brain"]} if r.get("brain") else {})}
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
        elif sc.get("kind") == "lit_variant":        # a stored run (research/runs/<id>.json) vs lit_live, per period
            from tools import runlib as rl
            sess = [d[0] for d in rl.load("lit_live")["days"]]
            for side, rid in (("own", sc.get("run")), ("lit_only", "lit_live")):
                r = rl.load(rid)
                T = [dict(zip(r["trade_cols"], a)) for a in r["trades"]]
                for p, a, b in (("H1", "2026-01-01", "2026-06-30"), ("H2", "2026-07-01", "2026-10-16"), ("2026", "2026-01-01", "2026-10-16"),
                                ("2025", "2025-01-01", "2025-12-31"), ("2021-24", "2021-11-01", "2024-12-31")):
                    TT = [t for t in T if a <= t["day"] <= b]
                    S_ = [s for s in sess if a <= s <= b]
                    out[side][p] = _row(rl._compact(TT, rl.days_of(TT, S_))) if TT else None
            out["with_lit"] = out["own"]
        elif sc.get("kind") == "stop_hunt":          # research/stophunt/<pick>.json spans ($500 a trade) + the ATLAS 25K eval paths
            rep = json.load(open(os.path.join(ROOT, rs.get("best") or f"research/stophunt/{sc.get('pick')}.json"), encoding="utf-8"))
            for p, _ in PERIODS:
                if p == "2026":
                    T = [t for t in rep.get("trades") or [] if "2026-01-01" <= t["day"] <= "2026-10-16"]
                    out["own"][p] = _row(_span_row(T, 199)) if T else None
                else:
                    out["own"][p] = _row((rep.get("spans") or {}).get(p))
            try:
                ev = json.load(open(os.path.join(ROOT, rs.get("evals") or "research/stophunt/evals.json"), encoding="utf-8"))
                ek = ("n", "tpw", "net", "per_month", "dd", "pf", "p10", "f10", "p20", "f20", "pass_med")
                cut = lambda o: {k: {kk: v.get(kk) for kk in ek if v.get(kk) is not None} for k, v in (o or {}).items() if isinstance(v, dict)}
                out["atlas_eval"] = {"label": "MFFU Builder 25K, ATLAS need sizing, never opposite to LIT (tools/stophunt.py evals)",
                                     "atlas": cut(ev.get("ATLAS_25k")), "atlas_plus": cut((ev.get(sc.get("pick")) or {}).get("ATLAS_plus_25k")),
                                     "atlas_plus_both": cut((ev.get("sh_book") or {}).get("ATLAS_plus_25k")),
                                     "own_25k": cut((ev.get(sc.get("pick")) or {}).get("own_builder25k"))}
            except Exception as e:
                out["atlas_eval"] = {"error": f"{e.__class__.__name__}: {e}"}
            out["placebo"] = {k: {kk: v.get(kk) for kk in ("n", "p_rtime", "p_flip")} for k, v in (rep.get("placebo") or {}).items()}
            out["candidate"] = True
        elif rs.get("summary"):                      # a plugin strategy: its research JSON gives the same tables
            rep = json.load(open(os.path.join(ROOT, rs["summary"]), encoding="utf-8"))
            for k in ("own", "with_lit", "lit_only"):
                out[k] = rep.get(k) or {}
    except Exception as e:
        out["error"] = f"{e.__class__.__name__}: {e}"
    out["periods"] = [list(p) for p in PERIODS]
    return out


def _span_row(T, nsess):
    """n / tpw / win / pf / net / per_month / dd of research trades (pnl_usd) over nsess sessions."""
    p = [float(t["pnl_usd"]) for t in T]
    eq = np.cumsum(p)
    dd = float((eq - np.maximum.accumulate(np.r_[0.0, eq])[1:]).min()) if p else 0.0
    gl = -sum(x for x in p if x < 0)
    return {"n": len(p), "tpw": round(len(p) / (nsess / 5), 2), "win": round(100.0 * sum(1 for x in p if x > 0) / len(p), 1),
            "pf": round(sum(x for x in p if x > 0) / gl, 2) if gl else None, "net": round(sum(p)),
            "per_month": round(sum(p) / (nsess / 21)), "dd": round(dd)}


def dashboard_block(state: dict | None = None, cfg: dict | None = None, pc: dict | None = None, route: dict | None = None) -> dict:
    """data.json "second" / /api/next/second: per strategy its rules, backtest tables, today's state and the paper
    trades (cloud ledger; the PC's live view when given). route = LiveBot.second_route_info() or the heartbeat's
    second.route: which strategies the PC routes to its account ("ROUTED on <account>"), else "paper"."""
    cfg = cfg or load_cfg()
    st = state or {}
    route = route or (pc or {}).get("route") or None
    rk = set((route or {}).get("keys") or [])
    ab = (route or {}).get("account_b") or None
    bk = set((ab or {}).get("keys") or []) if (ab or {}).get("enabled") else set()
    note = ("Paper only: nothing is traded. LIT and the eval account are unchanged." if not rk else
            f"{', '.join(sorted(rk))} ROUTED on {(route or {}).get('account') or 'the bot account'} next to LIT "
            "(LIT first, one position at a time, max 2 trades a day); the others are paper.")
    if bk:
        note = (f"{', '.join(sorted(bk))} ROUTED on {ab['label']} ({ab.get('plan_label')}, its own eval; never opposite to LIT). "
                + (note if rk else "LIT's account is unchanged."))
    out = {"paper": not (rk or bk), "note": note, "account_b": ab,
           "route": route, "t": st.get("t"), "first_run": st.get("first_run"), "strategies": [], "pc_t": (pc or {}).get("t")}
    for key, sc in (cfg.get("strategies") or {}).items():
        s = (st.get("strategies") or {}).get(key) or {}
        led = s.get("ledger") or {}
        rows = sorted(led.values(), key=lambda v: v.get("entry_t") or 0)
        fin = [v for v in rows if v.get("exit_kind") not in (None, "OPEN")]
        lit_fin = [v for v in fin if (v.get("lit") or {}).get("taken")]
        pcs = ((pc or {}).get("strategies") or {}).get(key) or {}
        out["strategies"].append({
            "key": key, "label": sc.get("label") or key, "short": sc.get("short") or key, "on": bool(sc.get("on", True)),
            "candidate": bool(sc.get("candidate")),
            "summary": sc.get("summary"), "with_lit_label": sc.get("with_lit_label"), "with_lit_note": sc.get("with_lit_note"),
            "backtest": (bt := backtest(key, sc)), "rules": sc.get("rules") or bt.get("rules") or [],
            "state": pcs.get("state") if pcs.get("state") and (pc or {}).get("t", 0) >= (st.get("t") or 0) else s.get("state"),
            "state_src": "PC" if pcs.get("state") and (pc or {}).get("t", 0) >= (st.get("t") or 0) else "cloud",
            "trades": rows[-60:], "paper": {"n": len(fin), "usd": round(sum(v.get("usd") or 0 for v in fin), 2),
                                            "wins": sum(1 for v in fin if (v.get("usd") or 0) > 0),
                                            "with_lit_n": len(lit_fin), "with_lit_usd": round(sum((v.get("lit") or {}).get("usd") or 0 for v in lit_fin), 2)},
            "pc_today": [t for t in (pcs.get("trades") or []) if t.get("day") == (pcs.get("state") or {}).get("day")][-5:],
            "route": key in rk or key in bk, "route_label": route_label(key in rk or key in bk, ab["label"] if key in bk else (route or {}).get("account")),
            "brain": pcs.get("brain") or s.get("brain"),
        })
    try:                                   # go / no-go scorecard (engine/second_scorecard.py): paper result vs the expected range
        from . import second_scorecard as SC
        rows = {}
        for key in SC.all_keys():
            s = (st.get("strategies") or {}).get(key) or {}
            pcs = ((pc or {}).get("strategies") or {}).get(key) or {}
            rows[key] = SC.merge_rows(list((s.get("ledger") or {}).values()), pcs.get("trades"))
        src = (f"cloud paper ledger since {_et(st['first_run']):%b %d}" if st.get("first_run") else
               "the PC bot's live window (its trades of the last weeks, replayed)" if st else "no paper trades yet")
        sc = SC.card(rows, keys_b=(ab or {}).get("keys") or None, source=src)
        for x in out["strategies"]:
            x["scorecard"] = sc["strategies"].get(x["key"])
        out["scorecard"] = {k: sc[k] for k in ("account_b", "rule", "source", "built")}
    except Exception as e:
        out["scorecard"] = {"error": f"{e.__class__.__name__}: {e}"}
    out["atlas"] = atlas_info()            # ATLAS = the members on the 25K (display name; internal key stays "second")
    return out


ATLAS_KEYS = ["ema_lon_vix", "macd_sweep", "sr_nyreclaim"]


def atlas_info() -> dict:
    """ATLAS (owner 2026-10-22: the second strategy, EMA + MACD + S/R pooled on the 25K; internal key "second"): its name,
    members, rules and research numbers for the dashboards (data.json second.atlas, /api/next/second). From
    research/second/atlas.json (the tuning job: keys name, members, rules, numbers, eval25k) when it exists, else the
    account-B research (research/second/account_b.json, plan builder25k, sizing need: second-account-b.md). Display only."""
    p = os.path.join(ROOT, "research", "second", "atlas.json")
    try:
        if os.path.exists(p):
            d = json.load(open(p, encoding="utf-8"))
            if isinstance(d, dict):
                d.setdefault("name", "ATLAS")
                d.setdefault("members", ATLAS_KEYS)
                d.setdefault("source", "research/second/atlas.json")
                return d
    except Exception as e:
        return {"name": "ATLAS", "members": ATLAS_KEYS, "error": f"atlas.json: {e.__class__.__name__}: {e}"}
    out = {"name": "ATLAS", "members": ATLAS_KEYS, "source": "research/second/account_b.json (Builder 25K, need sizing)",
           "writeup": "second-account-b", "numbers_label": "Builder 25K, need sizing, costs in"}
    try:
        ab = json.load(open(os.path.join(ROOT, "research", "second", "account_b.json"), encoding="utf-8"))
        x = (ab.get("plans") or {}).get("builder25k|need") or {}
        out["numbers"] = {k: {kk: v.get(kk) for kk in ("n", "tpw", "win", "pf", "net", "per_month", "dd") if v.get(kk) is not None}
                          for k, v in x.items() if isinstance(v, dict)}
        out["eval25k"] = {k: {kk: v.get(kk) for kk in ("p10", "f10", "p20", "f20", "dead10", "pass_med", "ev_eval_3m") if v.get(kk) is not None}
                          for k, v in x.items() if isinstance(v, dict)}
    except Exception as e:
        out["error"] = f"account_b.json: {e.__class__.__name__}: {e}"
    return out


def route_label(route: bool, account: str | None) -> str:
    """"ROUTED on Sim101" / "paper": what the dashboards and the heartbeat show per strategy."""
    return f"ROUTED on {account or 'the bot account'}" if route else "paper"


def compact(res: dict | None, max_trades: int = 6, route: dict | None = None) -> dict | None:
    """The heartbeat / live.json cut of one run(): today's state + the last trades per strategy (small) + its second brain.
    route = LiveBot.second_route_info() ({"keys": [...], "account": "Sim101", "open": {...}, "routed": [...]}): which
    strategies the PC bot routes to its account ("ROUTED on <account>") and which stay paper."""
    if not res:
        return None
    rk = set((route or {}).get("keys") or [])
    acct = (route or {}).get("account")
    ab = (route or {}).get("account_b") or None
    bk = set((ab or {}).get("keys") or []) if (ab or {}).get("enabled") else set()
    out = {"t": res.get("t"), "day": res.get("day"), "paper": not (rk or bk), "strategies": {},
           **({"route": {k: v for k, v in route.items() if k in ("keys", "account", "open", "routed", "note", "account_b")}} if route else {})}
    for k, s in (res.get("strategies") or {}).items():
        tr = [{kk: t.get(kk) for kk in ("day", "entry_t", "exit_t", "dir", "entry", "stop", "stop_now", "target", "exit", "exit_kind",
                                        "r", "qty", "usd", "last", "lit")} for t in (s.get("trades") or [])[-(3 if s.get("candidate") else max_trades):]]
        on_route = k in rk or k in bk
        out["strategies"][k] = {"label": s.get("label"), "short": s.get("short"), "on": s.get("on"), "state": s.get("state"),
                                **({"candidate": True} if s.get("candidate") else {}),
                                "route": on_route, "route_label": route_label(on_route, ab["label"] if k in bk else acct), "trades": tr,
                                **({"brain": brain_compact(s.get("brain"), max_log=3 if s.get("candidate") else 6)} if s.get("brain") else {}),
                                **({"error": s["error"]} if s.get("error") else {})}
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
        out["strategies"][key] = {kk: s.get(kk) for kk in ("label", "short", "on", "state", "error", "route", "candidate") if kk != "candidate" or s.get(kk)}
        if s.get("brain"):
            out["strategies"][key]["brain"] = brain_compact(s["brain"])
        out["strategies"][key]["ledger"] = dict(sorted(led.items())[-200:])
    for key, s in old.items():                        # a strategy switched off / removed keeps its ledger
        if key not in out["strategies"]:
            out["strategies"][key] = {**s, "on": False}
    return out


def readme_lines(block: dict | None, money=None) -> list:
    """README section "ATLAS (paper)" (cloud monitor, dashboard branch; ATLAS = the second strategy, internal key "second")."""
    money = money or (lambda x: f"{'+' if x >= 0 else '-'}${abs(x):,.0f}")
    L = ["", "## ATLAS (paper)",
         "ATLAS = the second strategy for the 25K (EMA London pullback + MACD sweep divergence + S/R NY reclaim), run next to "
         "LIT on the same bars, **paper only** (engine/second.py, second_model.json): nothing is traded, LIT and the eval "
         "account are unchanged. Never opposite to LIT, LIT first; \"With LIT\" = LIT first on one account, no ATLAS entry "
         "while LIT is in a trade, max 2 trades a day."]
    if not block or not block.get("strategies"):
        return L + ["", "Not running yet (second_model.json missing or every strategy off)."]
    for key, s in block["strategies"].items():
        led = sorted((s.get("ledger") or {}).values(), key=lambda v: v.get("entry_t") or 0, reverse=True)
        fin = [v for v in led if v.get("exit_kind") not in (None, "OPEN")]
        lt = [v for v in fin if (v.get("lit") or {}).get("taken")]
        st = s.get("state") or {}
        L += ["", f"### {s.get('label') or key} ({s.get('short') or key})" + ("" if s.get("on", True) else " - OFF") + (" - candidate ATLAS member" if s.get("candidate") else "") + (" - ROUTED on the PC account (LIVE pushes come from the PC)" if s.get("route") else " - paper"),
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
    try:                                   # go / no-go scorecard on the paper ledger (engine/second_scorecard.py)
        from . import second_scorecard as SC
        led = {k: list(((block["strategies"].get(k) or {}).get("ledger") or {}).values()) for k in SC.all_keys()}
        L += SC.readme_lines(SC.card(led, source="cloud paper ledger"),
                             labels={k: (block["strategies"].get(k) or {}).get("short") or k for k in SC.all_keys()})
    except Exception as e:
        L += ["", f"Scorecard unavailable: {e.__class__.__name__}: {e}"]
    return L


# ============================================================================================ the owner's switch
def _selftest_ok(timeout=600) -> tuple:
    """engine.ninjatrader --selftest in its own process (this module imports no adapter): (passed, last line)."""
    import subprocess
    import sys
    try:
        p = subprocess.run([sys.executable, "-X", "utf8", "-m", "engine.ninjatrader", "--selftest"], cwd=ROOT, capture_output=True,
                           text=True, timeout=timeout)
        lines = [x for x in (p.stdout or "").splitlines() if x.strip()]
        return p.returncode == 0, (lines[-1] if lines else (p.stderr or "").strip()[-200:])
    except Exception as e:
        return False, f"{e.__class__.__name__}: {e}"


def set_route(key: str, on: bool, path: str | None = None, selftest=_selftest_ok) -> dict:
    """second_model.json strategies.<key>.route = on (the one line of the file, the rest untouched). Refused: an unknown /
    cloud-only / switched-off strategy, or (switching on) a failing engine.ninjatrader --selftest."""
    import re
    path = path or CFG_PATH
    with open(path, encoding="utf-8") as fh:
        raw = fh.read()
    c = json.loads(raw)
    sc = (c.get("strategies") or {}).get(key)
    if not isinstance(sc, dict):
        return {"ok": False, "error": f"unknown strategy {key!r} (known: {', '.join(c.get('strategies') or {})})"}
    if sc.get("cloud_only"):
        return {"ok": False, "error": f"{key} is cloud only (a paper shadow): it is never routed"}
    if on and sc.get("candidate"):
        return {"ok": False, "error": f"{key} is a candidate ATLAS member (paper only until its paper scorecard and the audit say go): "
                                      "it is never routed"}
    if on and not sc.get("on", True):
        return {"ok": False, "error": f"{key} is switched off (\"on\": false): switch it on first"}
    old = bool(sc.get("route", False))
    ab = c.get("account_b")
    if on and isinstance(ab, dict) and key in (ab.get("strategies") or ["ema_lon_vix", "macd_sweep", "sr_nyreclaim"]):
        return {"ok": False, "error": f"{key} trades on account B ({ab.get('account')}): it is never also routed on LIT's account "
                                      "(python -m engine.second --account-b off first)"}
    if on:
        ok, line = selftest()
        if not ok:
            return {"ok": False, "error": f"engine.ninjatrader --selftest failed ({line}): route NOT switched on"}
    m = re.search(r'"%s"\s*:\s*\{' % re.escape(key), raw)
    nxt = re.search(r'\n  "[^"]+"\s*:\s*\{', raw[m.end():])
    a, b = m.end(), m.end() + (nxt.start() if nxt else len(raw) - m.end())
    blk = raw[a:b]
    val = "true" if on else "false"
    if re.search(r'"route"\s*:\s*(true|false)', blk):
        blk = re.sub(r'"route"\s*:\s*(true|false)', f'"route": {val}', blk, count=1)
    else:
        blk = re.sub(r'("on"\s*:\s*(true|false),)', r'\1 "route": ' + val + ',', blk, count=1)
    new = raw[:a] + blk + raw[b:]
    chk = json.loads(new)
    if bool(chk["strategies"][key].get("route")) != bool(on) or any(
            json.dumps(v, sort_keys=True) != json.dumps(c["strategies"][k], sort_keys=True)
            for k, v in chk["strategies"].items() if k != key):
        return {"ok": False, "error": "second_model.json edit check failed: nothing written"}
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(new)
    os.replace(tmp, path)
    return {"ok": True, "key": key, "from": old, "to": bool(on), "label": sc.get("label") or key}


def _account_b_cli(a) -> int:
    """python -m engine.second --account-b "<Name>" --plan builder25k --start <day> | --account-b off (engine/account_b.py)."""
    from engine import account_b as AB
    r = AB.set_account_b(a.account_b, plan=a.plan, start=a.start, sizing=a.sizing,
                         strategies=[x.strip() for x in a.strategies.split(",") if x.strip()] if a.strategies else None)
    if not r["ok"]:
        print("REFUSED: " + r["error"])
        return 1

    def desc(v):
        if not v:
            return "off"
        return (f"{v['account']} {AB.PLANS[v['plan']]['label']}, eval from {v['eval_start']}, size {v['sizing']}, "
                f"strategies {', '.join(v['strategies'])}")
    print(f"Account B: {desc(r['from'])} -> {desc(r['to'])}")
    if r["to"]:
        P = AB.PLANS[r["to"]["plan"]]
        print(f"The PC bot picks it up on its next poll: its own NinjaTrader account, eval tracker and size, never opposite to "
              f"LIT. Plan {P['label']} (${P['price']:.2f})."
              + (f" Switched off on LIT's account: {', '.join(r['routed_off'])}." if r.get("routed_off") else ""))
        if not r.get("sim"):
            print("Not a Sim account: its orders are refused until you arm it yourself (the same steps as LIT's live account).")
    else:
        print("The PC bot takes no new account B entry from its next poll; an open account B trade is still managed to its exit.")
    return 0


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(prog="python -m engine.second", description="Second strategies next to LIT (paper / routed).")
    ap.add_argument("--route", nargs=2, metavar=("KEY", "on|off"), help="route a second strategy to the PC bot's account (on) or "
                                                                          "back to paper (off)")
    ap.add_argument("--status", action="store_true", help="show every strategy: on / routed / paper")
    ap.add_argument("--account-b", metavar="NAME", help="trade the second strategies on their own account (the NinjaTrader account "
                                                       "Name), or 'off' (engine/account_b.py)")
    ap.add_argument("--plan", default="builder25k", choices=["builder25k", "builder50k"], help="account B's MFFU plan")
    ap.add_argument("--start", help="account B's first eval session (yyyy-mm-dd; default today)")
    ap.add_argument("--sizing", default="need", choices=["need", "safe"], help="account B's size: need (one winner passes) or safe")
    ap.add_argument("--strategies", help="comma list (default ema_lon_vix,macd_sweep,sr_nyreclaim)")
    a = ap.parse_args(argv)
    if a.account_b:
        return _account_b_cli(a)
    if a.route:
        key, st = a.route[0], a.route[1].lower()
        if st not in ("on", "off"):
            print("use: python -m engine.second --route <key> on|off")
            return 2
        r = set_route(key, st == "on")
        if not r["ok"]:
            print("REFUSED: " + r["error"])
            return 1
        word = lambda v: "ROUTED (the PC bot trades it on its account next to LIT)" if v else "paper"
        print(f"{r['key']} ({r['label']}): route {'on' if r['from'] else 'off'} -> {'on' if r['to'] else 'off'}: "
              f"{word(r['from'])} -> {word(r['to'])}")
        print("The PC bot reads second_model.json every poll: the change applies on its next poll (no restart needed)."
              + (" LIT stays first; one position at a time; max 2 trades a day." if r["to"] else ""))
        return 0
    cfg = load_cfg()
    ab = cfg.get("account_b")
    print("Account B: " + (f"{ab.get('account')} {ab.get('plan')} from {ab.get('eval_start')} size {ab.get('sizing', 'need')}: "
                           f"{', '.join(ab.get('strategies') or [])}" if isinstance(ab, dict) and ab else "off"))
    onb = set((ab or {}).get("strategies") or []) if isinstance(ab, dict) else set()
    for k, sc in cfg["strategies"].items():
        if k in onb:
            print(f"{k:14s} {'on ' if sc.get('on', True) else 'OFF'} ACCOUNT B  {sc.get('label') or ''}")
            continue
        print(f"{k:14s} {'on ' if sc.get('on', True) else 'OFF'} {'ROUTED' if sc.get('route') else 'cloud only' if sc.get('cloud_only') else 'paper'}"
              f"  {sc.get('label') or ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
