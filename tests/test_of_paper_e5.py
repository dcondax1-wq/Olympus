"""DESIGN_paper_v2 (night-of-paperv2 2026-11-27): the E5 second fill of engine/of_paper lane A rows. Paper only.

    python -X utf8 -m tests.test_of_paper_e5
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from engine import of_paper as P  # noqa: E402

T = 0.25
FAILS = []


def check(name, ok):
    print(("ok   " if ok else "FAIL ") + name)
    if not ok:
        FAILS.append(name)


def row(d=-1, lv=100.0, stop=105.0, td=1_800_000_000):
    return {"d": d, "level_px": lv, "stop": stop, "t_dec": td, "taken": True}


def ticks(td, secs, prices):
    return np.array([(td + s) * 1000 for s in secs], np.int64), np.array(prices, float)


def main() -> int:
    td = 1_800_000_000 // 300 * 300
    r = row(td=td)
    # short at a high, level 100: trades 99, 99.5, 100.25 (1 tick through) -> filled at the level
    tt, pp = ticks(td, [1, 20, 60], [99.0, 99.5, 100.25])
    f = P._fill_e5(r, None, tt, pp, False)
    check("level fill needs 1 tick through", f is not None and f[0] == 100.0 and f[2] == "level" and f[1] == tt[2])
    # touch only (100.0) then nothing until +300 -> market + 18 ticks
    tt, pp = ticks(td, [1, 20, 301], [99.0, 100.0, 98.0])
    f = P._fill_e5(r, None, tt, pp, False)
    check("touch only -> market +18 after 300 s", f is not None and f[2] == "market+18" and abs(f[0] - (98.0 - 18 * T)) < 1e-9)
    # undecided while the window is open
    tt, pp = ticks(td, [1, 20], [99.0, 99.25])
    check("undecided inside the window", P._fill_e5(r, None, tt, pp, False) is None)
    # a jump to the stop passes the level first: filled at the level (the shadow _resolve then books the stop)
    tt, pp = ticks(td, [1, 5, 10], [99.0, 105.0, 100.5])
    f = P._fill_e5(r, None, tt, pp, False)
    check("jump through the level to the stop -> level fill", f is not None and f[0] == 100.0 and f[2] == "level")
    # marketable when placed
    tt, pp = ticks(td, [1], [100.5])
    f = P._fill_e5(r, None, tt, pp, False)
    check("marketable at the first trade", f is not None and f[0] == 100.5 and f[2] == "marketable")
    # long mirror
    rl = row(d=1, lv=100.0, stop=95.0, td=td)
    tt, pp = ticks(td, [2, 30], [101.0, 99.75])
    f = P._fill_e5(rl, None, tt, pp, False)
    check("long: level fill", f is not None and f[0] == 100.0 and f[2] == "level")
    # coarse (5m bars): entry bar through the level / not
    bars = pd.DataFrame({"t": [td, td + 300], "open": [99.0, 98.0], "high": [100.25, 98.5], "low": [98.0, 97.0], "close": [99, 98]})
    f = P._fill_e5(r, bars, np.array([], np.int64), np.array([]), True)
    check("coarse: entry bar through the level", f is not None and f[0] == 100.0 and f[2] == "level")
    bars2 = bars.assign(high=[100.0, 98.5])
    f = P._fill_e5(r, bars2, np.array([], np.int64), np.array([]), True)
    check("coarse: else next open +18", f is not None and f[2] == "market+18" and abs(f[0] - (98.0 - 18 * T)) < 1e-9)
    # the E5 book pays $1.90 (engine/costs.COMM_RT); the v1 book keeps its frozen $1.40
    sh = {"comm": P.COMM_E5, "d": -1, "stop": 105.0, "fill": 100.0}
    P._close(sh, td, 90.0, "target")
    v1 = {"d": -1, "stop": 105.0, "fill": 100.0}
    P._close(v1, td, 90.0, "target")
    check("E5 book at $1.90, v1 at $1.40", abs(sh["usd_1"] - (20.0 - 1.90)) < 1e-9 and abs(v1["usd_1"] - (20.0 - 1.40)) < 1e-9)
    # the original fields are untouched by the E5 shadow: the frozen selftest (research LVL = paper) still holds
    check("of_paper selftest (original fills unchanged)", P.selftest())
    print(f"test_of_paper_e5: {'ALL OK' if not FAILS else str(len(FAILS)) + ' FAILED'}")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
