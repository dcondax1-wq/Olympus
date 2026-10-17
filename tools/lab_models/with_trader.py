"""Any Strategy Lab model traded by the shared trader layer (tools/trader_layer.py; rules in
research/lab/TRADER_LAYER_RULES.md). Plug-in interface (research/lab/PROTOCOL.md), so live_model.json can deploy it:

    {"model": "lab:with_trader", "params": {"base": "silver_bullet", "base_params": {"sym": "NQ"},
                                            "layer": {"bias_align": "grade"}}}

run() asks the base model for its trades, keeps only their entries, directions and invalidation stops (and its own
target, which the layer uses only with plan off), then the layer judges, sizes, targets and manages each one like a
person. An unfinished last trade has exit_kind 'open'; its "stop" / "target" / "qty" are the CURRENT stop (after
break-even / trailing), the next target and the contracts still open, so the live loop can mirror the bracket.

Base "engine" (bonus): the Liquidity Engine itself proposes the entries (engine.model.Engine on the same bars).

Notes for live use:
- The base model's own day rules (stop after a win, max trades) still gate what it proposes; set base_params so they
  are no stricter than the layer's (2 a day, 2 losers, -$600, +1R winner).
- 1m-trigger models (ATM with tf=1) need 1m bars; pass params["bars1_path"] (a CSV with time/high/low/... ) or they
  run on the 5m bars they are given.
- The simulated eval account lives inside one run() call (it restarts from $50,000 at the start of the frame), as in
  the backtest; the live risk manager should use the real account state.
"""
from __future__ import annotations

import importlib
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tools import trader_layer as tl  # noqa: E402

NAME = "with_trader"
PARAMS = {"base": "silver_bullet", "base_params": {"sym": "NQ"}, "layer": {}, "kind": None, "bars1_path": None}
# how each base module stamps its trades (see tools/trader_layer.setups_from_trades)
KINDS = {"silver_bullet": "limit", "ict2022": "limit", "mech_ifvg": "signal_open", "session_po3": "signal_open",
         "continuation": "cont", "atm": "atm", "engine": "engine"}
_LAST = {}


def _bars1(path, bars5):
    if not path:
        return None
    try:
        import pandas as pd
        p = path if os.path.isabs(path) else os.path.join(ROOT, path)
        m1 = pd.read_csv(p, usecols=["time", "high", "low"])
        a, z = int(bars5["time"].iloc[0]), int(bars5["time"].iloc[-1]) + 300
        return m1[(m1["time"] >= a) & (m1["time"] <= z)].reset_index(drop=True)
    except Exception:
        return None


def _engine_trades(bars5, base_params, es5=None):
    """Bonus: the Liquidity Engine's own trades on the same 5m frame (entries become setups). Light, single run."""
    from engine.data import from_frame
    from engine.model import Engine
    cols = ["time", "open", "high", "low", "close", "volume"]
    b = from_frame("NQ", "5m", bars5[cols])
    partner = from_frame("ES", "5m", es5[cols]) if es5 is not None and len(es5) else None
    eng = Engine(b, partner=partner, params=base_params or {}).run()
    return eng.result()["trades"]


def run(bars5, params=None, es5=None):
    p = {**PARAMS, **(params or {})}
    base = p["base"]
    kind = p.get("kind") or KINDS.get(base, "close")
    if base == "engine":
        raw = _engine_trades(bars5, p.get("base_params") or {}, es5)
    else:
        mod = importlib.import_module(base if "." in base else f"tools.lab_models.{base}")
        bp = {**getattr(mod, "PARAMS", {}), **(p.get("base_params") or {})}
        raw = mod.run(bars5, bp, es5)
    setups = tl.setups_from_trades(raw, kind, bars5, model=base)
    log = []
    trades = tl.apply(setups, bars5, es5, p.get("layer") or {}, log=log, bars1=_bars1(p.get("bars1_path"), bars5))
    for t in trades:
        if t.get("exit_kind") == "open":
            t["stop0"] = t["stop"]
            t["stop"] = t.get("live_stop", t["stop"])
            t["target"] = t.get("live_target", (t.get("plan") or {}).get("T"))
            t["qty_total"] = t["qty"]
            t["qty"] = t.get("live_qty", t["qty"])
        else:
            t.setdefault("target", (t.get("plan") or {}).get("T"))
    _LAST.clear()
    _LAST.update({"base": base, "setups": len(setups), "taken": len(trades), "log": log[-20:], "raw": len(raw)})
    return trades


def state(bars5, params=None, es5=None):
    p = {**PARAMS, **(params or {})}
    st = {}
    base = p["base"]
    if base != "engine":
        try:
            mod = importlib.import_module(base if "." in base else f"tools.lab_models.{base}")
            if hasattr(mod, "state"):
                bp = {**getattr(mod, "PARAMS", {}), **(p.get("base_params") or {})}
                st = dict(mod.state(bars5, bp, es5) or {})
        except Exception as ex:
            st = {"state_error": f"{type(ex).__name__}: {ex}"}
    last = (_LAST.get("log") or [None])[-1]
    st["trader_layer"] = {"base": base, "setups_seen": _LAST.get("setups"), "trades_taken": _LAST.get("taken"),
                          "last_decision": last, "imports": dict(tl._IMPORT_ERR)}
    if last is not None:
        st.setdefault("status", f"{base} + trader layer: last setup {last.get('decision')} ({last.get('reason') or last.get('grade')})")
    return st
