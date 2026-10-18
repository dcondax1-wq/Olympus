"""Live-loop sizing: one multiplier on top of the engine's micros, applied in exactly the same way by the PC bot
(engine/live.py), the cloud monitor (tools/cloud_monitor.py), the dashboard's replay (tools/export_backtest.py) and the
research library (tools/runlib.py). Research 2026-10-17: research/writeups/risk-summary.md.

Config, live_model.json:
  "equity_filter": {"lookback": 15, "min_sum_r": 0.0, "cold_mode": "half", "cold_size": 0.25}   cold streak -> x cold_size
  "sizing": {"late_mult": 0.5,                 late entry (15m trend already points the trade's way) -> x late_mult
             "press": {"floor": -1000, "ref": 60} | null}
                                               fast-eval mode: while the eval's profit is >= floor ($), size as if the
                                               wide-stop reference were `ref` pts ($800 on any stop up to 60) instead of
                                               params.risk_ref_stop; off when null (default)
The engine's micros already carry the $ risk and the wide-stop scaling. The multipliers are combined, rounded down
ONCE, floor 1 micro, cap max_micros. cold 0 (skip mode) means no trade.

LIT (live_model.json "lit_sizing": {"mode": "normal" | "fast_eval" | "safe_eval"}, default normal): lit_qty() below, used by
the PC bot and the cloud monitor's paper ledger; mffu_eval() is the eval room for safe_eval.
"""
from __future__ import annotations

import math

DEFAULT = {"late_mult": None, "press": None}


def is_late(trade: dict) -> bool:
    """15m structure already turned the trade's way at entry (the -1 item of the confluence score)."""
    try:
        return (float(trade.get("m15_trend") or 0) * float(trade.get("dir") or 0)) > 0
    except (TypeError, ValueError):
        return False


def engine_micros(risk_usd: float, risk_pts: float, ref_stop: float, max_micros: int = 40, pv: float = 2.0) -> int:
    """The engine's own rule (model.py): risk_usd up to ref_stop pts, then risk_usd x ref / stop; micros rounded down."""
    if risk_pts <= 0:
        return 0
    usd = risk_usd * (min(1.0, ref_stop / risk_pts) if ref_stop else 1.0)
    return int(min(max_micros, usd // (risk_pts * pv)))


def route_qty(qty: int, trade: dict, cold_mult: float, sizing: dict | None = None, params: dict | None = None,
              eval_profit: float | None = None) -> dict:
    """{"qty", "mult", "reasons": [...]} for one entry.
    qty: the engine's micros. trade: dict with dir, m15_trend, risk_pts (or entry+stop). cold_mult: equity_filter mult.
    eval_profit: the eval account's profit vs its start ($) at entry, None = unknown (press off)."""
    sz = {**DEFAULT, **(sizing or {})}
    p = params or {}
    reasons = []
    if qty <= 0 or cold_mult <= 0:
        return {"qty": 0, "mult": 0.0, "reasons": ["cold streak: paper only"] if cold_mult <= 0 else ["no size"]}
    base = int(qty)
    press = sz.get("press")
    if press and eval_profit is not None and eval_profit >= float(press.get("floor", -1000)):
        risk = trade.get("risk_pts")
        if risk is None and trade.get("entry") is not None and trade.get("stop") is not None:
            risk = abs(float(trade["entry"]) - float(trade["stop"]))
        if risk:
            pressed = engine_micros(float(p.get("risk_usd", 800)), float(risk), float(press.get("ref", 60)),
                                    int(p.get("max_micros", 40)))
            if pressed > base:
                reasons.append(f"fast eval: {pressed} instead of {base} micros (eval {eval_profit:+,.0f} vs floor {float(press.get('floor', -1000)):+,.0f})")
                base = pressed
    mult = float(cold_mult)
    if mult < 1:
        reasons.append(f"cold streak x{mult:g}")
    if sz.get("late_mult") is not None and is_late(trade):
        mult *= float(sz["late_mult"])
        reasons.append(f"late entry (15m already turned) x{float(sz['late_mult']):g}")
    q = base if mult >= 1 else max(1, int(math.floor(base * mult)))
    q = min(q, int(p.get("max_micros", 40)))
    return {"qty": q, "mult": round(q / qty, 4) if qty else 0.0, "reasons": reasons}


# ------------------------------------------------------------------------------------------------ LIT (live_model.json "lit_sizing")
MFFU_50K = {"start": 50000.0, "target": 3000.0, "mll": 2000.0, "lock": 50100.0}


def mffu_eval(day_pnl: dict, plan: dict | None = None) -> dict:
    """MFFU Builder 50K eval from P&L per trading day: balance, trailing max-loss floor (end-of-day high - $2,000, locked at
    $50,100) and the room (cushion) between them. Same rule as tools/cloud_monitor.eval_track."""
    p = {**MFFU_50K, **(plan or {})}
    bal = peak = p["start"]
    mll = p["start"] - p["mll"]
    for d in sorted(day_pnl):
        bal += float(day_pnl[d])
        peak = max(peak, bal)
        mll = min(max(mll, peak - p["mll"]), p["lock"])
    return {"balance": round(bal, 2), "profit": round(bal - p["start"], 2), "to_target": round(p["start"] + p["target"] - bal, 2),
            "trailing_mll": round(mll, 2), "cushion": round(bal - mll, 2)}


def lit_qty(qty: int, trade: dict, cfg: dict | None = None, room: float | None = None, max_micros: int = 40) -> dict:
    """Micros to route for one LIT entry. qty = the model's micros (engine/lit.py: $800 up to a 20-pt stop, then 800x20/stop,
    times the weekly stop, rounded once). cfg = live_model.json "lit_sizing" {"mode": "normal" | "fast_eval" | "safe_eval"}:
      normal     the model's micros (default)
      fast_eval  $800 up to a fast_ref_stop (40) pt stop, then 800x40/stop, times the model's size multiplier (weekly stop),
                 rounded down once, floor 1 (run lit_x_fast_eval)
      safe_eval  the model's micros capped at safe_cap (60%) of room / (stop x $2), min 1; room = eval balance - trailing
                 max-loss floor (run lit_x_room_cap60). room None = unknown: no cap (reason logged)
    Returns {"qty", "mult" (vs the model's micros), "reasons"}."""
    c = cfg or {}
    mode = c.get("mode") or "normal"
    if qty <= 0:
        return {"qty": 0, "mult": 0.0, "reasons": ["no size"]}
    reasons = list(trade.get("size_why") or [])
    risk = trade.get("risk_pts")
    if risk is None and trade.get("entry") is not None and trade.get("stop0", trade.get("stop")) is not None:
        risk = abs(float(trade["entry"]) - float(trade.get("stop0", trade.get("stop"))))
    q = int(qty)
    if mode == "fast_eval" and risk:
        from .lit import qty_for
        base = qty_for(float(risk), 800.0, float(c.get("fast_ref_stop", 40.0)), max_micros)
        m = float(trade.get("size_mult") or 1.0)
        q = base if m >= 1 else max(1, int(base * m + 1e-9))
        q = max(q, 1)
        reasons.append(f"fast eval: $800 up to a {float(c.get('fast_ref_stop', 40.0)):g}-pt stop -> {q} micros")
    elif mode == "safe_eval" and risk:
        if room is None:
            reasons.append("safe eval: eval room unknown, no cap")
        else:
            cap = int(float(c.get("safe_cap", 0.6)) * max(0.0, float(room)) / (float(risk) * 2.0))
            if cap < q:
                q = max(1, cap)
                reasons.append(f"safe eval: {q} micro{'s' if q != 1 else ''} = {float(c.get('safe_cap', 0.6)) * 100:.0f}% of ${float(room):,.0f} room to the max-loss floor")
    q = min(q, max_micros)
    return {"qty": q, "mult": round(q / qty, 4), "reasons": reasons}


def selftest() -> bool:
    t_late = {"dir": 1, "m15_trend": 1, "risk_pts": 44.0}
    t_ok = {"dir": -1, "m15_trend": 1, "risk_pts": 44.0}
    sz = {"late_mult": 0.5, "press": None}
    assert route_qty(4, t_ok, 1.0, sz)["qty"] == 4
    assert route_qty(4, t_ok, 0.25, sz)["qty"] == 1
    assert route_qty(4, t_late, 1.0, sz)["qty"] == 2
    assert route_qty(4, t_late, 0.25, sz)["qty"] == 1            # 4 x 0.125 = 0.5 -> floor 1
    assert route_qty(9, t_late, 0.5, sz)["qty"] == 2             # one rounding: floor(9 x 0.25) = 2
    assert route_qty(4, t_ok, 0.0, sz)["qty"] == 0
    assert engine_micros(800, 44.0, 20) == 4 and engine_micros(800, 44.0, 60) == 9 and engine_micros(800, 10.0, 20) == 40
    fast = {"late_mult": 0.5, "press": {"floor": -1000, "ref": 60}}
    r = route_qty(4, t_ok, 1.0, fast, {"risk_usd": 800, "max_micros": 40}, eval_profit=0.0)
    assert r["qty"] == 9 and "fast eval" in r["reasons"][0], r
    assert route_qty(4, t_ok, 1.0, fast, {"risk_usd": 800}, eval_profit=-1500.0)["qty"] == 4
    assert route_qty(4, t_late, 0.25, fast, {"risk_usd": 800}, eval_profit=500.0)["qty"] == 1   # 9 x 0.125 = 1.1 -> 1
    lt = {"risk_pts": 47.0}
    assert lit_qty(3, lt)["qty"] == 3 and lit_qty(3, lt, {"mode": "normal"})["qty"] == 3
    assert lit_qty(3, lt, {"mode": "fast_eval"})["qty"] == 7                       # 800*40/47 = 680.9 / 94 = 7.2 -> 7
    assert lit_qty(1, {**lt, "size_mult": 0.5}, {"mode": "fast_eval"})["qty"] == 3  # 7 x 0.5 = 3.5 -> 3 (one rounding)
    assert lit_qty(3, lt, {"mode": "safe_eval"}, room=2000.0)["qty"] == 3           # 0.6*2000/94 = 12.8 -> no cap
    assert lit_qty(3, lt, {"mode": "safe_eval"}, room=300.0)["qty"] == 1            # 0.6*300/94 = 1.9 -> 1
    assert lit_qty(3, lt, {"mode": "safe_eval"}, room=50.0)["qty"] == 1             # min 1
    assert mffu_eval({"a": 1000, "b": -500})["trailing_mll"] == 49000.0 and mffu_eval({})["cushion"] == 2000.0
    print("sizing selftest OK")
    return True


if __name__ == "__main__":
    import sys
    sys.exit(0 if selftest() else 1)
