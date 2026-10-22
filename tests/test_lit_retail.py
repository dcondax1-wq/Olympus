"""Retail-tool entries (engine/lit_retail.py, research/writeups/lit-retail-entries.md): the switch is off by default.

    python -X utf8 -m tests.test_lit_retail          # option off = today's LIT (120/120 2026 trades of run lit_live), HTF candles
                                                      # known only at their close, a cut-at-entry rebuild finds the same setup
Option on through the live loop (the PC bot / cloud path, engine/lit_live.py):
    python -X utf8 -m tests.test_lit_live --days --nobot --retail='{"retail": {"kind": "macd", "macd_tf": "15m", "macd_sub": ["idm"]}, "max_per_day": 2, "src_cap": 1}'
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from engine import lit, lit_retail as R  # noqa: E402


def main():
    from tools import lit_retail as X
    from tools import runlib as rl
    ok = True
    M, C, B1, B5, Tb = X.base()
    # 1. off = unchanged candidates and trades
    C0 = R.apply(M, C, {**X.LIVE, "retail": None})
    same_c = C0 is C
    T0 = lit.run_x(M, C0, {**X.LIVE, "retail": None, "src_cap": None}, X.SESS, B1=B1, B5=B5)
    r = rl.load("lit_live")
    ref = sorted((dict(zip(r["trade_cols"], a))["day"], int(dict(zip(r["trade_cols"], a))["entry_t"]))
                 for a in r["trades"] if a[0] >= "2026")
    got = sorted((t["day"], int(t["entry_t"])) for t in T0 if t["day"] >= "2026")
    print(f"off: candidates unchanged {same_c}; 2026 trades {len(got)} vs lit_live {len(ref)}, identical {got == ref}")
    ok &= same_c and got == ref
    # 2. a 15m candle is known only once its last 5m bar closed
    H = R.HTF(M, 900)
    bad = sum(1 for j in range(1, min(H.n, 50000)) if H.known[j] < 10 ** 12 and H.known[j] < H.last[j])
    print(f"15m candles known before their last 5m bar: {bad}")
    ok &= bad == 0
    # 3. cut at the entry bar: the same setups (a sample per family)
    for cfg in ({"kind": "sd", "sd_tf": ["15m"], "stop": "ext"}, {"kind": "macd", "macd_tf": "15m", "macd_sub": ["idm"]},
                {"kind": "ema", "ema_pb": "15m21"}):
        ok &= X.lookahead(cfg, n=8) == 0
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
