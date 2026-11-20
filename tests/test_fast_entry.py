"""engine/fast_entry.py: the minute's first poll on NinjaTrader's first tick (BUILT, OFF by default).

Pins: OFF everywhere = engine/live.LiveBot._sleep_s gives exactly today's wait (+2 s / +32 s); ON (cfg, env or
data/fast_entry.json; NinjaTrader feed only) the poll after the +32 s one waits for the files: it returns the moment the new
minute's open is in <ROOT>_1m_open.csv AND the 1m bar file changed after the boundary (here 0.6 s after it, not 2.0 s), at the
latest at the usual +2 s when no tick comes; a stop request ends the wait at once; the same minute never gets a second
"first" poll; a wrong-minute open file (last minute's) does not count; the CLI switch writes the local file only.

    python -X utf8 -m tests.test_fast_entry
"""
from __future__ import annotations

import io
import contextlib
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import fast_entry as FE  # noqa: E402
from engine import live as L  # noqa: E402
from engine.ninjatrader import FEED_DIR, NinjaTraderBars  # noqa: E402

RES = []


def check(name, cond, detail=""):
    RES.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({str(detail)[:300]})" if detail and not cond else ""), flush=True)


class Clock:
    """A fake clock; sleep() advances it and runs the scheduled file writes (the first tick) when their time comes."""
    def __init__(self, t, events=()):
        self.t, self.events, self.slept, self.stop_at = float(t), sorted(events), 0.0, None

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.t += float(s)
        self.slept += float(s)
        while self.events and self.events[0][0] <= self.t:
            self.events.pop(0)[1]()
        return self.stop_at is not None and self.t >= self.stop_at


REAL = os.path.join(ROOT, "data", "fast_entry.json")


def main() -> bool:
    real_before = os.path.exists(REAL)
    tmp = tempfile.mkdtemp(prefix="fastentry_")
    try:
        d = os.path.join(tmp, FEED_DIR)
        os.makedirs(d)
        feed = NinjaTraderBars(folder=tmp, roots={"NQ": ["MNQ"]})
        p1, po = os.path.join(d, "MNQ_1m.csv"), os.path.join(d, "MNQ_1m_open.csv")
        b = 1795014000                                     # a minute boundary (2026-11-18 10:00 ET)
        assert b % 60 == 0

        def files(bar_mtime, open_minute):
            with open(p1, "w") as fh:
                fh.write("time,open,high,low,close,volume\n")
            os.utime(p1, (bar_mtime, bar_mtime))
            with open(po, "w") as fh:
                fh.write(f"{open_minute},27000.25\n")

        def tick():                                        # LE_BarFeed on the first trade of minute b
            files(b + 0.6, b)
        # ---- the switch
        cfg_nt = {"data_source": "ninjatrader"}
        sw = os.path.join(tmp, "fast_entry.json")
        check("OFF by default (no cfg key, no env, no file)", not FE.enabled(cfg_nt, env={}, path=sw))
        check("never for another feed (paper / Yahoo)", not FE.enabled({"data_source": "yahoo", "poll_on_tick": True}, env={}, path=sw))
        check("cfg poll_on_tick true -> on", FE.enabled({**cfg_nt, "poll_on_tick": True}, env={}, path=sw))
        check("cfg poll_on_tick false wins over the env", not FE.enabled({**cfg_nt, "poll_on_tick": False}, env={"LE_POLL_ON_TICK": "1"}, path=sw))
        check("env LE_POLL_ON_TICK=1 -> on", FE.enabled(cfg_nt, env={"LE_POLL_ON_TICK": "1"}, path=sw))
        FE.set_on(True, sw)
        check("data/fast_entry.json on -> on", FE.enabled(cfg_nt, env={}, path=sw))
        FE.set_on(False, sw)
        check("... off again", not FE.enabled(cfg_nt, env={}, path=sw))
        # ---- the wait
        files(b - 60 + 0.4, b - 60)                        # last minute's files
        c = Clock(b - 28.0, [(b + 0.6, tick)])             # just after the +32 s poll of the minute before
        w = FE.first_tick_wait(feed, "NQ", c(), clock=c, sleep=c.sleep)
        check("ON: returns (poll now, boundary)", w == (0.0, b), w)
        check("... at the first tick (+0.6 s), not +2.0 s", b + 0.6 <= c.t < b + 0.7, c.t - b)
        files(b - 60 + 0.4, b - 60)
        c = Clock(b - 28.0)                                # no trade in the new minute
        w = FE.first_tick_wait(feed, "NQ", c(), clock=c, sleep=c.sleep)
        check("no tick: polls at the usual +2 s", w == (0.0, b) and abs(c.t - (b + 2.0)) < 0.06, c.t - b)
        files(b + 0.3, b - 60)                             # bar file touched but the open file still names the old minute
        c = Clock(b - 1.0, [(b + 1.1, tick)])
        FE.first_tick_wait(feed, "NQ", c(), clock=c, sleep=c.sleep)
        check("the old minute's open file does not count (waits for the new minute's)", b + 1.1 <= c.t < b + 1.2, c.t - b)
        files(b - 60 + 0.4, b - 60)
        c = Clock(b - 28.0)
        c.stop_at = b - 10.0
        w = FE.first_tick_wait(feed, "NQ", c(), clock=c, sleep=c.sleep)
        check("a stop request ends the wait at once (no tick watch after the stop)", w == (0.0, b) and abs(c.t - (b + 0.15)) < 1e-6,
              c.t - b)
        c = Clock(b + 0.8)
        w = FE.first_tick_wait(feed, "NQ", c(), clock=c, sleep=c.sleep, done=b)
        check("this minute's first poll already ran on its tick: next wait is the +32 s poll (no 2nd first poll)",
              w is not None and abs(w[0] - 31.2) < 1e-6 and c.slept == 0, w)
        c = Clock(b + 10.0)
        check("after the first poll of the minute (the +32 s one is next): None = the usual wait",
              FE.first_tick_wait(feed, "NQ", c(), clock=c, sleep=c.sleep) is None)
        check("no NinjaTrader 1m file: None", FE.first_tick_wait(NinjaTraderBars(folder=os.path.join(tmp, "x"), roots={"NQ": ["MNQ"]}),
                                                                  "NQ", b - 28.0, clock=c, sleep=c.sleep) is None)
        # ---- LiveBot._sleep_s: OFF = exactly today's wait; ON = the tick
        bot = L.LiveBot()
        bot.cfg = {**L.LIVE_DEFAULTS, "data_source": "ninjatrader", "poll_sec": 60}
        bot._nt_feed = feed
        bot.health["bar_1m_behind"] = False
        files(b - 60 + 0.4, b - 60)
        c = Clock(b - 28.0, [(b + 0.6, tick)])
        bot.clock = c
        old = os.environ.pop("LE_POLL_ON_TICK", None)
        saved = FE.PATH
        FE.PATH = os.path.join(tmp, "absent.json")
        FE._CACHE.update(t=0.0, path=None)
        try:
            check("LiveBot OFF: _sleep_s = today's 30 s to +2 s", abs(bot._sleep_s() - 30.0) < 1e-6 and c.slept == 0, c.slept)
            bot.cfg["poll_on_tick"] = True
            bot.stop_flag.wait = c.sleep                    # the fake clock advances while the bot waits
            w = bot._sleep_s()
            check("LiveBot ON: _sleep_s waits for the tick and says poll now", w == 0.0 and b + 0.6 <= c.t < b + 0.7, (w, c.t - b))
            c.t = b + 0.9
            w2 = bot._sleep_s()
            check("LiveBot ON: right after that poll, the next wait is the +32 s poll", abs(w2 - 31.1) < 1e-6, w2)
        finally:
            FE.PATH = saved
            FE._CACHE.update(t=0.0, path=None)
            if old is not None:
                os.environ["LE_POLL_ON_TICK"] = old
        buf = io.StringIO()
        saved = FE.PATH
        FE.PATH = os.path.join(tmp, "cli.json")
        try:
            with contextlib.redirect_stdout(buf):
                FE.main(["--on"])
            check("CLI --on writes the local switch file only", os.path.exists(FE.PATH) and FE.file_on(FE.PATH, now=10**10), buf.getvalue())
        finally:
            FE.PATH = saved
            FE._CACHE.update(t=0.0, path=None)
        check("the real data/fast_entry.json is untouched by the test", os.path.exists(REAL) == real_before)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    ok = all(RES)
    print(f"{sum(RES)}/{len(RES)} passed")
    return ok


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
