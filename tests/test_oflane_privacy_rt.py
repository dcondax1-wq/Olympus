"""red team #38 (day-ofready2 2026-11-27): an unmatched lane refusal never carries an account name / id into the ntfy status ext
("ofl") or the public NQ_lane.json (engine/oflive._short_why's fallback masks quoted names and id-like runs).
    python -X utf8 -m tests.test_oflane_privacy_rt
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RES: list = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {info!r}"), flush=True)


def main():
    from engine.oflive import _short_why as f
    for w in ("account 'MFFUEVBLDR1234567' is not a NinjaTrader simulation account", 'firm "Zlarior 50K" FFN12345678 rule',
              "acct 98765432 refused", "hedging: MFFUEV123456 holds a SHORT"):
        out = f(w)
        check(f"no name / id: {w[:30]}...", out and not any(x in out for x in ("MFFU", "12345", "98765", "Zlarior")), out)
    check("a known reason keeps its words", f("skipped: day cap (1 of 1 entry today)") == "skipped: day cap (1 a day)")
    n = sum(RES)
    print(f"\n{n}/{len(RES)} passed")
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
