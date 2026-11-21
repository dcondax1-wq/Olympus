"""K8 day (2026-11-20): refresh the public trade history of the K8 legs (Kalshi PUBLIC GET only, no key, at most 1 request a second).

Every leg market of Aug 3 - today that has settled: Kalshi's result + the first 45 s of public trades (engine.kalshi_adapt.fetch_tape,
the same code the PC's weekly re-test uses). Appends to research/kalshi_k8_day/data/tape.jsonl (one row per market, resumable).

    python research/kalshi_k8_day/fetch.py [--start 2026-08-03] [--end 2026-11-20]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
from engine import kalshi_adapt as KA, kalshi_clock as KC  # noqa: E402

TAPE = os.path.join(HERE, "data", "tape.jsonl")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2026-08-03")
    ap.add_argument("--end", default=dt.date.today().isoformat())
    a = ap.parse_args(argv)
    cfg = KC.load_config()[0]
    pub = KA.Public(gap=1.05)
    s, e = dt.date.fromisoformat(a.start), dt.date.fromisoformat(a.end)
    r = KA.fetch_tape(pub, TAPE, s, e, cfg)
    print(json.dumps({**r, "errors": pub.errors, "rows": len(KA.read_tape(TAPE))}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
