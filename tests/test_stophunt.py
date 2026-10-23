"""STOP-HUNT research checks (research/writeups/stophunt.md).

    python -X utf8 -m tests.test_stophunt            # ~2 min: the stored picks reproduce, look-ahead on cut data, no order code
    python -X utf8 -m tests.test_stophunt --quick    # one pick, 3 look-ahead trades

1. engine/stophunt.py + tools/stophunt.py rebuild every stored pick (research/stophunt/sh_*.json) trade for trade.
2. Sampled trades re-derive identically from data cut at their signal close (no look-ahead).
3. engine/stophunt.py is research only: no adapter / NinjaTrader / order import.
"""
from __future__ import annotations

import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def main(quick=False):
    from tools import stophunt as SH
    ok = True
    src = open(os.path.join(ROOT, "engine", "stophunt.py"), encoding="utf-8").read()
    bad = re.findall(r"^\s*(?:from|import)\s+(engine\.(?:ninjatrader|adapter\w*|live|guards)|ninjatrader)", src, re.M)
    print("no order code imported:", "OK" if not bad else f"FAIL {bad}")
    ok &= not bad
    g = SH.base()
    names = list(SH.FINAL)[:1] if quick else list(SH.FINAL)
    for nm in names:
        spec = SH.FINAL[nm]
        st, rows = SH.one(g, spec)
        rows = [r for r in rows if r["day"] >= "2021-11-01"]
        stored = json.load(open(os.path.join(SH.OUT, nm + ".json"), encoding="utf-8"))["trades"]
        same = [(r["entry_t"], r["exit_t"], r["dir"], r["pnl_usd"]) for r in rows] == \
               [(r["entry_t"], r["exit_t"], r["dir"], r["pnl_usd"]) for r in stored]
        print(f"{nm}: {len(rows)} trades, reproduce stored:", "OK" if same else "FAIL")
        ok &= same
        n, k, diffs = SH.lookahead(spec, rows, n=3 if quick else 10, seed=5)
        print(f"{nm}: look-ahead on cut data {k}/{n}", "OK" if k == n else f"FAIL {diffs[:2]}")
        ok &= k == n
    print("ALL OK" if ok else "FAILED")
    return ok


if __name__ == "__main__":
    sys.exit(0 if main(quick="--quick" in sys.argv) else 1)
