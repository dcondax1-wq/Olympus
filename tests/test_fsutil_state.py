"""State writes survive a brief Windows/OneDrive lock (PermissionError twice, then success): keepalive's state + hand_hedge's window.

    python -X utf8 -m tests.test_fsutil_state
"""
from __future__ import annotations

import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
from engine import fsutil, hand_hedge, keepalive, msg_throttle  # noqa: E402

R = []


def check(name, ok, extra=""):
    R.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {extra}"), flush=True)


class Locked:
    """os.replace that raises PermissionError the first n calls, then really replaces."""
    def __init__(self, n):
        self.n, self.calls, self.real = n, 0, os.replace

    def __call__(self, a, b):
        self.calls += 1
        if self.calls <= self.n:
            raise PermissionError(13, "locked by OneDrive")
        return self.real(a, b)


def run(label, fn, path, expect):
    lk = Locked(2)
    orig_rep, orig_sleep = os.replace, fsutil.time.sleep
    os.replace, fsutil.time.sleep = lk, lambda s: None
    try:
        fn()
    finally:
        os.replace, fsutil.time.sleep = orig_rep, orig_sleep
    try:
        d = json.load(open(path, encoding="utf-8"))
    except Exception as e:
        d = repr(e)
    check(f"{label}: PermissionError x2 then success -> file complete, {lk.calls} tries, no .tmp left",
          lk.calls == 3 and expect(d) and not os.path.exists(path + ".tmp"), (lk.calls, d))


def main():
    with tempfile.TemporaryDirectory() as t:
        p = os.path.join(t, "ka_state.json")
        run("keepalive.save_state", lambda: keepalive.save_state({"acc": {"A": 1}, "sent": ["x"]}, p), p,
            lambda d: isinstance(d, dict) and d.get("acc") == {"A": 1} and d.get("sent") == ["x"])
        w = os.path.join(t, "hh_window.json")
        run("hand_hedge.set_window", lambda: hand_hedge.set_window(5, path=w, now=1_795_000_000), w,
            lambda d: isinstance(d, dict) and d.get("minutes") == 5.0)
        m = os.path.join(t, "mt.json")
        run("msg_throttle._write (no sleeps)", lambda: msg_throttle._write(m, {"k": 1}), m, lambda d: d == {"k": 1})
    print(f"fsutil state: {sum(R)}/{len(R)} {'ALL PASS' if all(R) else 'FAILED'}")
    return 0 if all(R) else 1


if __name__ == "__main__":
    sys.exit(main())
