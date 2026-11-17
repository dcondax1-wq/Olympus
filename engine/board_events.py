"""Comms board events (minimal stub: the night-board helper's engine/board_events.py replaces this file at the merge).
emit(kind, account_key, text, data=None) records one event in memory and never raises."""
from __future__ import annotations

import threading
import time

_lock = threading.Lock()
_recent: list = []


def emit(kind, account_key, text, data=None):
    ev = {"t": int(time.time()), "kind": str(kind), "account": str(account_key), "text": str(text)[:600], "data": data}
    try:
        with _lock:
            _recent.append(ev)
            del _recent[:-100]
    except Exception:
        pass
    return ev
