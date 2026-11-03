"""The page's demo fixture: DAPHNE's JSON from SYNTHETIC trades (random $ and random conditions, no market data).

The page shows it, marked DEMO, when tree.json is missing.

  python -X utf8 -m tools.strategytree.demo        # -> tools/web_public/tree/demo.json
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

from tools.strategytree import features as fx, report, roots as rx, search as sx
from tools.strategytree.sessions import period_of

DEMO_JSON = os.path.join(os.path.dirname(report.PAGE_JSON), "demo.json")
DEMO_ROOTS = (rx.Root("ORH", "fade", 1.0, 60), rx.Root("PDL", "fade", 2.0, 120), rx.Root("ORL", "break", 1.0, 120),
              rx.Root("ONH", "fade", 1.0, 60), rx.Root("LL", "break", 2.0, 60), rx.Root("AH", "fade", 2.0, 120))
DEMO_CFG = sx.SearchConfig(min_n=40, max_expand=250)


def demo_doc(seed: int = 42) -> dict:
    """A small DAPHNE document with the real schema, built from random trades."""
    rng = np.random.default_rng(seed)
    days = pd.bdate_range("2021-12-01", "2026-10-16").strftime("%Y-%m-%d").to_numpy()
    raw = []
    for r in DEMO_ROOTS:
        n = int(rng.integers(350, 600))
        dates = np.sort(rng.choice(days, n, replace=False))
        trades = pd.DataFrame({"date": dates, "pnl": rng.normal(-2, 55, n).round(2),
                               "risk_pts": rng.uniform(8, 45, n).round(2)})
        codes = np.column_stack([rng.integers(0, len(f.labels), n) for f in fx.FEATURES]).astype(np.int8)
        raw.append((r, trades, codes))
    sessions = {k: int(v.sum()) for k, v in period_of(days).items()}
    prep = report.Prepared(raw, fx.conditions(), [], {"vol30d": [], "or_width": []})
    doc = report.assemble(prep, sessions, DEMO_CFG, placebos=1, quota=450,
                          extra_meta={"demo": True, "first_day": str(days[0]), "last_day": str(days[-1]),
                                      "data": "DEMO: synthetic trades, not market data"})
    doc.pop("_results")
    doc["meta"]["built"] = "demo"
    doc["meta"]["seconds"] = 0
    return doc


def main() -> int:
    body = json.dumps(demo_doc(), separators=(",", ":"), allow_nan=False)
    with open(DEMO_JSON, "w", encoding="utf-8") as fh:
        fh.write(body)
    print(f"{DEMO_JSON} ({len(body) / 1e3:.0f} kB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
