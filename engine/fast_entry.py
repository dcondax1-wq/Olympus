"""Poll on the first tick (night-nqlive 2026-11-20, owner: "read data faster, better fills, better timing"). BUILT, OFF BY DEFAULT.

Today the PC bot polls 2 s after each minute boundary (engine/live.next_wake offsets 2 s / 32 s): NinjaTrader's LE_BarFeed
writes the closed 1m bar AND the new minute's open (<ROOT>_1m_open.csv, which LIT sizes an entry from: the backtest fills at
that open) on the first trade of the new minute, so +2 s is a safe guess that both are there. Measured on the PC's real
entries (data/pc_days ledger rows, 2026-11-06..18): the market order left 3-5 s after the fill bar opened, and filled 3 ticks
(Zlarior) and 9-15 ticks (ATLAS) worse than that open, against 1 tick in the backtest's costs.

ON: the minute's first poll waits for the files instead of the clock: it wakes at the boundary + 0.15 s and polls the moment
NinjaTrader's <ROOT>_1m_open.csv names the new minute AND the 1m bar file changed after the boundary (checked every 50 ms),
at the latest at the usual +2 s. Same bars, same forming open, same decisions (a poll is a pure function of the bars): only
earlier, by up to ~1.8 s on an active minute. The +32 s poll, the 1m-bar re-poll (engine/live._await_nt_bar), paper / Yahoo
/ Tradovate feeds are unchanged. Only with data_source "ninjatrader".

Switch (any one turns it on; absent everywhere = OFF = exactly today's timing):
  the start cfg {"poll_on_tick": true} | env LE_POLL_ON_TICK=1 | data/fast_entry.json {"poll_on_tick": true}
  python -X utf8 -m engine.fast_entry --on | --off | --status      (writes / reads data/fast_entry.json, PC-local, gitignored)
Takes effect at the next poll (read at most every 30 s). Never routes, arms or sizes anything.
Tests: python -X utf8 -m tests.test_fast_entry
"""
from __future__ import annotations

import json
import math
import os
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "data", "fast_entry.json")
MARGIN_S, LIMIT_S, STEP_S = 0.15, 2.0, 0.05
_CACHE = {"t": 0.0, "path": None, "on": False}


def file_on(path: str | None = None, now=None) -> bool:
    """data/fast_entry.json {"poll_on_tick": true} (re-read at most every 30 s). Never raises."""
    p = path or PATH
    t = time.time() if now is None else float(now)
    if _CACHE["path"] == p and t - _CACHE["t"] < 30.0:
        return _CACHE["on"]
    try:
        with open(p, encoding="utf-8") as fh:
            on = (json.load(fh) or {}).get("poll_on_tick") is True
    except Exception:
        on = False
    _CACHE.update(t=t, path=p, on=on)
    return on


def enabled(cfg: dict | None, env=None, path: str | None = None) -> bool:
    c = cfg or {}
    if c.get("data_source") != "ninjatrader":
        return False
    if c.get("poll_on_tick") is not None:
        return c.get("poll_on_tick") is True
    e = os.environ if env is None else env
    if str(e.get("LE_POLL_ON_TICK", "")).strip() == "1":
        return True
    return file_on(path)


def set_on(on: bool, path: str | None = None) -> str:
    p = path or PATH
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump({"poll_on_tick": bool(on), "saved_at": int(time.time()),
                   "note": "engine/fast_entry.py: the minute's first poll on NinjaTrader's first tick instead of +2 s"}, fh, indent=1)
    os.replace(tmp, p)
    _CACHE.update(t=0.0, path=None)
    return p


def first_tick_wait(feed, sym: str, now: float, offsets=(2.0, 32.0), clock=time.time, sleep=None, done=None,
                    margin: float = MARGIN_S, limit: float = LIMIT_S, step: float = STEP_S):
    """None when the next poll is not the minute's first one (the caller keeps its usual wait). Else (wait, boundary):
    block until the first trade of the new minute is in NinjaTrader's files (the new minute's open in <ROOT>_1m_open.csv
    and the 1m bar file modified after the boundary), at most `limit` s after the boundary, and return (0.0, boundary) =
    poll now; done == that boundary (this minute's first poll already ran on its tick) -> the wait to the poll after the
    usual +2 s one (no second "first" poll). sleep(seconds) -> True when the bot is stopping (LiveBot.stop_flag.wait).
    Never raises."""
    try:
        from .live import next_wake
        offs = sorted(float(x) for x in offsets)
        nw = next_wake(now, offs)
        b = math.floor(nw / 60.0) * 60.0
        if abs((nw - b) - offs[0]) > 1e-6 or offs[0] <= margin:
            return None
        if done is not None and int(done) == int(b):
            return max(0.0, next_wake(b + offs[0] + 0.05, offs) - now), b
        p1 = feed.file_for(sym, 1) if feed is not None else None
        if not p1:
            return None
        sleep = sleep or time.sleep
        t = float(clock())
        if b + margin > t and sleep(b + margin - t):
            return 0.0, b
        end = b + min(limit, offs[0])
        while True:
            t = float(clock())
            if t >= end:
                return 0.0, b
            fo = feed.forming_open(sym, now=int(t))
            try:
                m1 = os.stat(p1).st_mtime
            except OSError:
                m1 = 0.0
            if fo and int(fo[0]) == int(b) and m1 >= b:
                return 0.0, b
            if sleep(step):
                return 0.0, b
    except Exception:
        return None


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="python -m engine.fast_entry", description=__doc__.split("\n\n")[0])
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--on", action="store_true")
    g.add_argument("--off", action="store_true")
    g.add_argument("--status", action="store_true")
    a = ap.parse_args(argv)
    if a.on or a.off:
        p = set_on(bool(a.on))
        print(f"  [OK]  poll on the first tick: {'ON' if a.on else 'OFF'} ({p}); the bot picks it up within 30 s")
        return 0
    print(f"  poll on the first tick: {'ON' if file_on(now=time.time() + 60) else 'OFF'} (data/fast_entry.json; "
          "env LE_POLL_ON_TICK=1 or the start cfg poll_on_tick also turn it on)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
