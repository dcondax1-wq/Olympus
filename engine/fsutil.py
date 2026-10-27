"""Windows-safe file replace for the bot's state files (2026-10-27: the PC's heartbeat showed "state save failed:
[WinError 5] Access is denied" on live_state.json: on Windows os.replace fails while another process (the dashboard /
heartbeat reading it, antivirus, OneDrive, the search indexer) has the target open for a moment. A failed save loses
restart safety (a restart restores an older state).

replace(tmp, dst): os.replace, retried on PermissionError for up to ~2 s (12 tries, growing waits). Raises the last error
when every try failed (the caller's error handling stays as it was)."""
from __future__ import annotations

import os
import time

WAITS = (0.02, 0.03, 0.05, 0.05, 0.1, 0.1, 0.15, 0.2, 0.25, 0.3, 0.4)


def replace(src: str, dst: str, sleep=time.sleep, _replace=None) -> int:
    """os.replace(src, dst) with retries on PermissionError; returns the number of retries it needed."""
    rep = _replace or os.replace
    for i, w in enumerate(WAITS + (None,)):
        try:
            rep(src, dst)
            return i
        except PermissionError:
            if w is None:
                raise
            sleep(w)
    return len(WAITS)
