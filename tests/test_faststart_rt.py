"""Red team on night-faststart (2026-11-23): faster looks must never shorten a limit or race START. Fake clock, nothing runs.

    python -X utf8 -m tests.test_faststart_rt        (< 1 s)

1. stop_server on a server that still holds the port but answers slowly (each look = its 3 s timeout): it still waits at
   least the old limit (30 s of waiting + the looks' own time, ~2 min), not 30 s of wall clock (FOUND: the wall-clock
   loop gave such a server 30 s; before it got ~120 s; fixed in engine/go.stop_server).
2. stop_server on a quick "still up" server: gives up after 30 s, as before.
3. start_server never reads the launch checklist; START's checklist look comes after the bot start (order in _step_arm).
"""
from __future__ import annotations

import os
import sys
import time
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tests.test_faststart import Clock  # noqa: E402

RES = []


def check(name, ok, info=""):
    print(f"{'ok  ' if ok else 'FAIL'} {name}{(': ' + str(info)[:300]) if info and not ok else ''}")
    RES.append(bool(ok))


def main():
    from engine import go as G
    keep = {k: getattr(G, k) for k in ("subprocess", "server_up")}
    real_time, real_sleep = time.time, time.sleep
    C = Clock()
    time.time, time.sleep = C.time, C.sleep
    try:
        G.subprocess = types.SimpleNamespace(run=lambda *a, **k: types.SimpleNamespace(returncode=0))
        down_at = [C.t + 80]

        def slow_up():                       # a look takes its 3 s timeout; the server lets go of the port at 80 s
            C.t += 3
            return C.t < down_at[0]
        G.server_up = slow_up
        t0 = C.t
        ok = G.stop_server()
        check("1. slow-answering server going down at 80 s: stop_server still sees it stop (old limit kept)", ok, C.t - t0)
        down_at[0] = 10 ** 12
        t0 = C.t
        ok = G.stop_server()
        check("1. a slow server that never stops: gives up after ~30 s of waiting + its looks (>= 100 s, as before)",
              not ok and C.t - t0 >= 100, C.t - t0)
        G.server_up = lambda: True
        t0 = C.t
        check("2. quick 'still up' server: gives up after 30 s (unchanged)", not G.stop_server() and 30 <= C.t - t0 <= 31, C.t - t0)
    finally:
        time.time, time.sleep = real_time, real_sleep
        for k, v in keep.items():
            setattr(G, k, v)
    src = open(os.path.join(ROOT, "engine", "go.py"), encoding="utf-8").read()
    ss = src[src.index("def start_server("):src.index("def stop_server(")]
    arm = src[src.index("def _step_arm("):src.index("def armed_accounts(")]
    check("3. start_server never reads the checklist; _step_arm reads it only after the bot start",
          "checklist" not in ss and arm.index("ninjatrader.main(start)") < arm.index("checklist_launch()"))
    ok = sum(RES)
    print(f"\nfaststart red team: {'PASS' if ok == len(RES) else 'FAIL'} ({ok}/{len(RES)})")
    return ok == len(RES)


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
