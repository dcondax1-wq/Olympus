"""Keep the PC from sleeping while the bot runs (Windows only, process-scoped).

Uses SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED). That request belongs to the calling THREAD and
lasts until the same thread clears it or exits, so a single long-lived worker thread owns it. Nothing else is
touched: no power plan, no registry, no system setting. When the process dies Windows drops the request by itself.
The display may still turn off (ES_DISPLAY_REQUIRED is deliberately not set). No-op on non-Windows.
"""
from __future__ import annotations

import sys
import threading
import time

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001


class KeepAwake:
    def __init__(self, refresh_s: float = 60.0):
        self._want = False
        self.held = False
        self.since = None
        self.last_error = None
        self.refresh_s = refresh_s
        self._wake = threading.Event()
        self._thread = None
        self._lock = threading.Lock()
        self.supported = sys.platform == "win32"

    def _call(self, flags: int) -> bool:
        if not self.supported:
            return False
        try:
            import ctypes
            prev = ctypes.windll.kernel32.SetThreadExecutionState(ctypes.c_uint(flags))
            if prev == 0:
                self.last_error = "SetThreadExecutionState returned 0"
                return False
            return True
        except Exception as e:                       # never let this break the server
            self.last_error = f"{e.__class__.__name__}: {e}"
            return False

    def _run(self):
        while True:
            want = self._want
            if want:
                ok = self._call(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)    # re-asserting is harmless
                if ok and not self.held:
                    self.held, self.since = True, int(time.time())
            elif self.held:
                self._call(ES_CONTINUOUS)                               # release: back to normal sleep rules
                self.held, self.since = False, None
            self._wake.wait(self.refresh_s)
            self._wake.clear()

    def set(self, want: bool):
        """Ask for (True) or release (False) the keep-awake request. Cheap; call as often as you like."""
        want = bool(want)
        with self._lock:
            if self._thread is None and self.supported:
                self._thread = threading.Thread(target=self._run, name="keepawake", daemon=True)
                self._thread.start()
        if want != self._want:
            self._want = want
            self._wake.set()

    def status(self) -> dict:
        return {"supported": self.supported, "want": self._want, "held": self.held, "since": self.since,
                "last_error": self.last_error}


KEEPAWAKE = KeepAwake()
