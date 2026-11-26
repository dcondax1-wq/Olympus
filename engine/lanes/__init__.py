"""Switchable strategy lanes (day-zerotouch2, docs/NEW_STRATEGY.md). Each lane is engine/lanes/<id>.py made by
tools/new_strategy.py: OFF by default, its own switch file data/lanes/<id>.json, and three functions:
  is_on() -> bool        set_on(phrase) -> {"ok", "say" | "error"}        set_off() -> {"ok", "say"}
LABEL = one plain line. set_on refuses anything but the typed live phrase. engine/pending_switch lists every lane here as
"lane:<id>", so the phone can queue it and the next START turns it on with the ONE phrase."""
from __future__ import annotations

import importlib
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ID_OK = re.compile(r"^[a-z][a-z0-9_]{1,30}$")


def ids() -> list:
    return sorted(f[:-3] for f in os.listdir(HERE) if f.endswith(".py") and f != "__init__.py" and ID_OK.match(f[:-3]))


def load(lane_id: str):
    if not ID_OK.match(str(lane_id or "")) or lane_id not in ids():
        return None
    try:
        m = importlib.import_module(f"engine.lanes.{lane_id}")
    except Exception:  # noqa: BLE001
        return None
    return m if all(callable(getattr(m, f, None)) for f in ("is_on", "set_on", "set_off")) else None
