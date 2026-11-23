"""The PC guard's state for the Start page, readiness and TRADE_HOME (night-pcguard 2026-11-23): data/pc_guard.json, written
by scripts/pc_guard.ps1 (run in FIX_CLOCK.bat's administrator window; undone by FIX_CLOCK_OFF.bat). Read-only, never raises.

  status(path)  {"on": True | False | None (never run), "t", "items": {update, power, nic, bot_startup, nt_startup}}
  line(path)    "Windows guard: on" | "Windows guard: OFF (...)" | "Windows guard: not set up (...)"
"""
from __future__ import annotations

import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "data", "pc_guard.json")
FIX = "right-click FIX_CLOCK.bat > Run as administrator once"
MISSING = {"bot_startup": "the bot does not start at sign-in", "nt_startup": "NinjaTrader does not start at sign-in"}


def status(path: str | None = None) -> dict:
    try:
        with open(path or PATH, encoding="utf-8-sig") as fh:
            d = json.load(fh)
        if not isinstance(d, dict):
            raise ValueError
        items = d.get("items") if isinstance(d.get("items"), dict) else {}
        return {"on": bool(d.get("on")), "t": d.get("t"), "items": items}
    except Exception:
        return {"on": None, "t": None, "items": {}}


def line(path: str | None = None) -> str:
    s = status(path)
    if s["on"] is None:
        return f"Windows guard: not set up ({FIX})"
    miss = [MISSING[k] for k in MISSING if s["items"].get(k) == "missing"]
    if s["on"]:
        return "Windows guard: on" + (f" ({'; '.join(miss)}: START_BOT.bat once adds it)" if miss else "")
    bad = [k for k in ("update", "power", "nic") if s["items"].get(k) == "fix"]
    return "Windows guard: OFF" + (f" ({', '.join(bad)} could not be set: send Claude a photo of FIX_CLOCK's window)" if bad
                                    else f" ({FIX})")
