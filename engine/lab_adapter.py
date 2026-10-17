"""Run a Strategy Lab rule module (tools/lab_models/<name>.py) inside the live loop.

The live bot and the cloud monitor normally re-run engine.model.Engine on a rolling window every poll. When
live_model.json (repo root) says {"model": "lab:<name>", "params": {...}}, they call run() here instead. It returns the
same shape the live loop already consumes: state (with "position"), completed trades, events and days.

A lab module exposes run(bars5, params, es5) -> trades (strategy_lab.make_trade format; an unfinished trade has
exit_kind 'open') and optionally state(bars5, params, es5) -> dict.
"""
from __future__ import annotations

import datetime as dt
import importlib
import json
import os
from zoneinfo import ZoneInfo

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.path.join(ROOT, "live_model.json")
ET = ZoneInfo("America/New_York")
EXIT_NAMES = {"stop": "STOP", "target": "TARGET", "market": "EXIT", "time": "TIME", "be": "BE", "open": "OPEN"}


def live_model() -> dict:
    """{"model": "engine" | "lab:<name>", "params": {...}}; engine with its defaults when the file is missing.
    The LE_LIVE_MODEL environment variable (same JSON) overrides the file (tests / one-off runs)."""
    try:
        if os.environ.get("LE_LIVE_MODEL"):
            cfg = json.loads(os.environ["LE_LIVE_MODEL"])
        else:
            with open(CONFIG, encoding="utf-8") as fh:
                cfg = json.load(fh)
        return {"model": cfg.get("model") or "engine", "params": cfg.get("params") or {}, "label": cfg.get("label", ""),
                "sym": (cfg.get("sym") or "NQ").upper(), "equity_filter": cfg.get("equity_filter"),
                "chosen": cfg.get("chosen", "")}
    except Exception:
        return {"model": "engine", "params": {}, "label": "", "sym": "NQ", "equity_filter": None}


def lab_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Live bars (time/open/high/low/close/volume) -> the Strategy Lab frame (adds et, day, mod)."""
    b = df[["time", "open", "high", "low", "close", "volume"]].sort_values("time").reset_index(drop=True).copy()
    et = pd.to_datetime(b["time"], unit="s", utc=True).dt.tz_convert(ET)
    b["et"] = et
    b["day"] = (et + pd.Timedelta(hours=6)).dt.strftime("%Y-%m-%d")
    b["mod"] = et.dt.hour * 60 + et.dt.minute
    return b


def _module(name: str):
    return importlib.import_module(name if "." in name else f"tools.lab_models.{name}")


def _hhmm(t):
    return dt.datetime.fromtimestamp(int(t), ET).strftime("%H:%M")


def run(name: str, df: pd.DataFrame, params: dict | None = None, es_df: pd.DataFrame | None = None) -> dict:
    mod = _module(name)
    p = {**getattr(mod, "PARAMS", {}), **(params or {})}
    b = lab_frame(df)
    es = lab_frame(es_df) if es_df is not None and len(es_df) else None
    raw = mod.run(b, p, es)
    st = {}
    if hasattr(mod, "state"):
        try:
            st = mod.state(b, p, es) or {}
        except Exception as e:             # a dashboard helper must never stop trading decisions
            st = {"state_error": f"{e.__class__.__name__}: {e}"}
    trades, events, position = [], [], None
    for t in sorted(raw, key=lambda t: t["entry_t"]):
        side = "LONG" if t["dir"] == 1 else "SHORT"
        events.append({"t": int(t["entry_t"]), "type": "entry", "dir": t["dir"],
                       "text": f"{side} {t.get('setup', '')} @ {t['entry']:.2f} stop {t['stop']:.2f}"
                               f"{' target ' + format(t['target'], '.2f') if t.get('target') is not None else ''} qty {t.get('qty')}"})
        if t.get("exit_kind") == "open":
            position = {"entry_t": int(t["entry_t"]), "dir": int(t["dir"]), "qty": int(t.get("qty") or 0), "stop": float(t["stop"]),
                        "target": t.get("target"), "entry": float(t["entry"]), "setup": t.get("setup")}
            continue
        reason = EXIT_NAMES.get(t.get("exit_kind"), str(t.get("exit_kind", "")).upper())
        trades.append({"entry_t": int(t["entry_t"]), "exit_t": int(t["exit_t"]), "dir": int(t["dir"]), "entry": float(t["entry"]),
                       "exit_price": float(t["exit"]), "stop": float(t["stop"]), "target": t.get("target"), "qty": int(t.get("qty") or 0),
                       "pnl": float(t["pnl"]), "pnl_r": float(t["r"]), "exit_reason": reason, "trigger": t.get("setup", ""),
                       "grade": None, "day": t["day"], "risk_pts": t.get("risk_pts")})
        events.append({"t": int(t["exit_t"]), "type": "exit",
                       "text": f"EXIT {reason} {side} {t.get('setup', '')} | {t['r']:+.2f}R | ${t['pnl']:+,.0f}"})
    for ev in st.get("events", []) or []:
        if isinstance(ev, dict) and "t" in ev and "text" in ev:
            events.append({"t": int(ev["t"]), "type": ev.get("type", "sweep"), "text": str(ev["text"])})
    events.sort(key=lambda e: e["t"])
    days = {}
    for t in trades:
        d = days.setdefault(t["day"], {"date": t["day"], "pnl": 0.0, "trades": 0})
        d["pnl"] += t["pnl"]
        d["trades"] += 1
    last = b.iloc[-1] if len(b) else None
    today = b["day"].iloc[-1] if len(b) else None
    state = {"model": f"lab:{name}", "model_state": st.get("status") or ("IN TRADE" if position else "WATCHING"),
             "position": position, "setups": st.get("setups") or {}, "active_pools": st.get("levels") or [],
             "session": st.get("session") or {}, "price": float(last["close"]) if last is not None else None,
             "t": int(last["time"]) if last is not None else None, "day_trades": sum(1 for t in trades if t["day"] == today),
             "day_pnl": round(sum(t["pnl"] for t in trades if t["day"] == today), 2), "lab_state": st}
    return {"state": state, "trades": trades, "events": events, "signals": [], "days": sorted(days.values(), key=lambda d: d["date"]),
            "shadows": [], "pools": [], "model": f"lab:{name}", "params": p}
