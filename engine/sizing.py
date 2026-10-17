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
    print("sizing selftest OK")
    return True


if __name__ == "__main__":
    import sys
    sys.exit(0 if selftest() else 1)
