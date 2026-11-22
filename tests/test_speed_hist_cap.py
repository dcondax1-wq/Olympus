"""engine/live.py history cap (day-speed 2026-11-20, HIST_KEEP_DAYS = 150): what _read_hist hands the poll.
    python -X utf8 -m tests.test_speed_hist_cap
a. NQ 5m / 1m: only the last 150 days of the bot's clock; b. the newest rows are exactly today's (uncapped) rows;
c. cfg hist_keep_days 0 = all rows (today's behaviour); d. ES 5m and NQ 1h are never cut;
e. the LIT window (engine/lit_live.window_start) is always inside the kept 150 days, every day of 2026;
f. a bad hist_keep_days ("0", 30, junk, NaN, inf) never empties or shortens LIT's history and never raises.
"""
from __future__ import annotations

import datetime as dt
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pandas as pd  # noqa: E402

from engine import live, lit_live  # noqa: E402

FAIL = []


def check(name, ok, info=""):
    print(f"  [{'OK' if ok else 'FAIL'}] {name}" + (f"  ({info})" if info and not ok else ""))
    if not ok:
        FAIL.append(name)


def main():
    tmp = tempfile.mkdtemp(prefix="hist_cap_")
    old = live.DATA_DIR
    try:
        t_end = 1_794_900_000 - 1_794_900_000 % 300
        n = 400 * 288                                      # 400 days of 5m bars
        times = [t_end - 300 * i for i in range(n)][::-1]
        df = pd.DataFrame({"time": times, "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5, "volume": 10.0})
        for name in ("NQ_5m", "NQ_1m", "ES_5m", "NQ_1h"):
            df.to_csv(os.path.join(tmp, f"{name}.csv"), index=False)
        live.DATA_DIR = tmp
        now = t_end + 600

        def bot(**cfg):
            b = live.LiveBot()
            b.clock = lambda: now
            b.cfg = {"sym": "NQ", **cfg}
            b.no_yahoo = True
            b.state_path = os.path.join(tmp, "st.json")
            return b
        b = bot()
        cut = now - live.HIST_KEEP_DAYS * 86400
        for tf in ("5m", "1m"):
            h = b._read_hist("NQ", tf)
            check(f"a. NQ {tf}: kept from {live.HIST_KEEP_DAYS} days back", int(h["time"].min()) >= cut and int(h["time"].min()) < cut + 300,
                  f"{h['time'].min()} vs {cut}")
        full = bot(hist_keep_days=0)._read_hist("NQ", "5m")
        capped = b._read_hist("NQ", "5m")
        tail = full[full["time"] >= cut].reset_index(drop=True)
        check("b. the kept rows are exactly today's newest rows", tail.equals(capped.reset_index(drop=True)))
        check("c. hist_keep_days 0 = every row (today)", len(full) == n, f"{len(full)}")
        check("d. ES 5m and NQ 1h are never cut", len(b._read_hist("ES", "5m")) == n and len(b._read_hist("NQ", "1h")) == n)
        # redteam 2026-11-21: a bad start cfg never empties / shortens LIT's history and never makes a poll raise
        check("f. hist_keep_days \"0\" (a string) = every row, never an empty history", len(bot(hist_keep_days="0")._read_hist("NQ", "5m")) == n)
        h30 = bot(hist_keep_days=30)._read_hist("NQ", "5m")
        floor = now - live.HIST_MIN_DAYS * 86400
        check(f"f. hist_keep_days 30 is floored at {live.HIST_MIN_DAYS} days (LIT's window)",
              int(h30["time"].min()) >= floor and int(h30["time"].min()) < floor + 300, f"{h30['time'].min()} vs {floor}")
        hj = bot(hist_keep_days="junk")._read_hist("NQ", "5m")
        check("f. a junk value falls back to the default cap", int(hj["time"].min()) >= cut and int(hj["time"].min()) < cut + 300)
        check("f. NaN / inf: no cut, no exception", len(bot(hist_keep_days=float("nan"))._read_hist("NQ", "5m")) == n
              and len(bot(hist_keep_days=float("inf"))._read_hist("NQ", "5m")) == n)
        worst = 0
        d = dt.date(2026, 1, 2)
        while d <= dt.date(2026, 12, 31):
            t = int(dt.datetime(d.year, d.month, d.day, 12, tzinfo=dt.timezone.utc).timestamp())
            worst = max(worst, t - lit_live.window_start(t))
            d += dt.timedelta(days=1)
        check(f"e. LIT's window reaches back at most {worst / 86400:.0f} days (< {live.HIST_KEEP_DAYS})",
              worst < live.HIST_KEEP_DAYS * 86400 - 7 * 86400)
    finally:
        live.DATA_DIR = old
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"\n{'ALL OK' if not FAIL else 'FAILED: ' + ', '.join(FAIL)}")
    return 1 if FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
