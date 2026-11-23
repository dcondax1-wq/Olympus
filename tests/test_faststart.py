"""START BOT's waits (night-faststart 2026-11-23, owner: "running the bot takes too long"), on a fake clock.

    python -X utf8 -m tests.test_faststart          # < 1 s, nothing real runs (subprocess and the bot server are faked)

The owner's seconds per wait, same scenario as research/handoff/2026-11-23/faststart/TIMING.md (before = night-integrate):
  server answers 3.2 s after the start      before 4.0 s   now <= 3.5 s
  server down 1.3 s after STOP              before 2.0 s   now <= 1.5 s
  NinjaTrader connected 7 s after the prompt before 10 s   now <= 8 s
  live bars back 20 s after the chart hint  before 30 s    now <= 21 s
  launch checklist green 12 s after start   before 20 s    now <= 12 s (already green: 10 s -> 0 s)
and every LIMIT is unchanged (server 120 s, stop 30 s, checklist 90 s, NinjaTrader / chart 15 min): only how often it looks.
"""
from __future__ import annotations

import os
import sys
import time
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
RES = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {info!r}"[:400]), flush=True)


class Clock:
    def __init__(self):
        self.t = 1000.0

    def time(self):
        return self.t

    def sleep(self, s):
        self.t += s


def main() -> int:
    from engine import go as G
    keep = {k: getattr(G, k) for k in ("subprocess", "server_up", "_http", "nt_running")}
    real_time, real_sleep = time.time, time.sleep
    C = Clock()
    time.time, time.sleep = C.time, C.sleep            # go._sleep / go._clock read these at call time
    try:
        started = {}
        G.subprocess = types.SimpleNamespace(Popen=lambda *a, **k: started.__setitem__("t", C.t),
                                             run=lambda *a, **k: (started.__setitem__("stop", C.t), types.SimpleNamespace(returncode=0))[1])
        G.server_up = lambda: C.t - started["t"] >= 3.2
        t0 = C.t
        ok = G.start_server()
        check("server start: ready 3.2 s after the start -> START goes on by 3.5 s (was 4.0 s)", ok and C.t - t0 <= 3.5, C.t - t0)
        G.server_up = lambda: False
        t0 = C.t
        check("server start: still gives up at 120 s (limit unchanged)", not G.start_server() and 120 <= C.t - t0 <= 121, C.t - t0)
        G.server_up = lambda: C.t - started["stop"] < 1.3
        t0 = C.t
        check("server stop: down at 1.3 s -> seen by 1.5 s (was 2.0 s)", G.stop_server() and C.t - t0 <= 1.5, C.t - t0)
        G.server_up = lambda: True
        t0 = C.t
        check("server stop: still gives up after 30 s (limit unchanged)", not G.stop_server() and 30 <= C.t - t0 <= 31, C.t - t0)
        mark = {}

        def conn():
            mark.setdefault("nt", C.t)
            return C.t - mark["nt"] >= 7.0
        from engine import autoresume
        keep_conn = autoresume.nt_connected
        autoresume.nt_connected = lambda cfg: conn()
        G.nt_running = lambda: True
        try:
            t0 = C.t
            check("NinjaTrader log-in: connected at 7 s -> seen by 8 s (was 10 s)", G.ensure_ninjatrader() and C.t - t0 <= 8, C.t - t0)
            t0 = C.t
            check("NinjaTrader log-in: still waits the full 15 minutes (limit unchanged)",
                  not G.ensure_ninjatrader(connected=lambda: False) and 900 <= C.t - t0 <= 903, C.t - t0)
        finally:
            autoresume.nt_connected = keep_conn

        def prob():
            mark.setdefault("fd", C.t)
            return None if C.t - mark["fd"] >= 20.0 else "stale"
        t0 = C.t
        check("chart fix: live bars back at 20 s -> seen by 21 s (was 30 s)", G.ensure_feed(problem=prob) and C.t - t0 <= 21, C.t - t0)
        # night-startcheck 2026-11-23: the launch checklist (always empty: it read "items" / "good" from an endpoint that sends
        # "checks" with pass / warn / fail) is gone; START prints the readiness verdict ONCE after arming, never a wait loop
        import threading as _th
        from engine import readiness as RD
        keep_rv = RD.ready_verdict
        try:
            RD.ready_verdict = lambda *a, **k: {"ready": True, "level": "READY", "window": "02:00", "blockers": []}
            t0 = C.t
            lines, ok = G.ready_lines()
            check("ready check: READY -> 'READY for the next window' at once (no 90 s checklist wait)", ok is True and C.t - t0 == 0
                  and lines == ["  READY for the next window"], (lines, C.t - t0))
            RD.ready_verdict = lambda *a, **k: {"ready": False, "level": "NOT_READY", "window": "02:00", "blockers": [
                {"what": "PC clock 25 s behind", "exact_fix": "SYNC_CLOCK.bat", "level": "NOT_READY"}]}
            lines, ok = G.ready_lines()
            check("ready check: NOT READY -> the phone's headline + the first blocker's fix, ok False",
                  ok is False and lines[0] == f"  {RD.headline(RD.ready_verdict())}" and "PC clock 25 s behind -> fix: SYNC_CLOCK.bat" in lines[1], lines)

            def slow(*a, **k):
                _th.Event().wait(2.0)
                return {"ready": True, "level": "READY", "blockers": []}
            RD.ready_verdict = slow
            w0 = keep_time = real_time()
            lines, ok = G.ready_lines(max_s=0.2)
            check("ready check: a slow verdict never holds START: 'still checking' after its limit (here 0.2 s), ok unknown",
                  ok is None and "still checking" in lines[0] and real_time() - w0 < 1.5, (lines, real_time() - keep_time))

            def bad(*a, **k):
                raise RuntimeError("x")
            RD.ready_verdict = bad
            lines, ok = G.ready_lines()
            check("ready check: a broken verdict says 'not readable', never raises", ok is None and "not readable: RuntimeError" in lines[0], lines)
        finally:
            RD.ready_verdict = keep_rv
        src = open(os.path.join(ROOT, "engine", "go.py"), encoding="utf-8").read()
        arm = src[src.index("def _step_arm("):src.index("def armed_accounts(")]
        check("_step_arm prints ready_lines() once; the dead launch checklist and its 90 s wait are gone from go.py",
              "ready_lines()" in arm and "time.sleep(10)" not in arm and "checklist_launch" not in src and "checklist_lines" not in src
              and "/api/dash/launch" not in src and "CHECK_MAX_S" not in src)
    finally:
        time.time, time.sleep = real_time, real_sleep
        for k, v in keep.items():
            setattr(G, k, v)
    print(f"\nfaststart: {sum(RES)}/{len(RES)} " + ("ALL PASS" if all(RES) else "FAILED"))
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
