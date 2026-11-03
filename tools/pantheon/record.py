"""Record the test fixtures (tests/fixtures/pantheon/) from the last good downloads in data/pantheon_cache/, trimmed small.

    python -X utf8 -m tools.pantheon            # fetch once (fills the cache)
    python -X utf8 -m tools.pantheon.record     # then trim the cache into the fixtures (from SINCE on)

The tests read only these files (sources.Store(fixtures=...)): never the network.
"""
from __future__ import annotations

import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import pandas as pd  # noqa: E402

from tools.pantheon import sources as SRC  # noqa: E402

FIXTURES = os.path.join(SRC.ROOT, "tests", "fixtures", "pantheon")
SINCE = "2024-06-01"           # ~2.4 years: enough for a 250-observation z-score and a 2026 relation row
COT_SINCE = "2020-06-01"       # the weekly COT needs ~5 years for 250 reports


def _trim_csv(text: str, date_col: int, fmt: str | None) -> str:
    lines = text.strip().splitlines()
    head, rows = lines[0], lines[1:]
    since = pd.Timestamp(SINCE)
    keep = [r for r in rows if pd.to_datetime(r.split(",")[date_col], format=fmt, errors="coerce") >= since]
    return "\n".join([head] + keep) + "\n"


def trim(src: SRC.Source, text: str) -> str:
    if src.id.startswith("fred:"):
        return _trim_csv(text, 0, "%Y-%m-%d")
    if src.id.startswith("cboe:"):
        return _trim_csv(text, 0, "%m/%d/%Y")
    if src.id == "squeeze:dix":
        return _trim_csv(text, 0, "%Y-%m-%d")
    if src.id == "cftc:tff_nq":
        rows = [r for r in json.loads(text) if r.get("report_date_as_yyyy_mm_dd", "") >= COT_SINCE]   # weekly: more years
        keep = ["report_date_as_yyyy_mm_dd", *SRC.TFF_COLS]
        return json.dumps([{k: r[k] for k in keep if k in r} for r in rows], separators=(",", ":"))
    if src.id == "treasury:curve":
        df = pd.read_csv(io.StringIO(text))
        return df.head(40).to_csv(index=False)
    return text


def main() -> int:
    os.makedirs(FIXTURES, exist_ok=True)
    for src in SRC.SOURCES:
        path = os.path.join(SRC.CACHE, src.fixture)
        if src.id == "local:events":
            path = os.path.join(SRC.DATA, "news", "events.csv")
        elif src.id == "ff:week" and not os.path.exists(path):
            path = os.path.join(SRC.DATA, "news", "ff_thisweek.json")
        if not os.path.exists(path):
            print(f"  {src.id:<22} no cached download: skipped")
            continue
        with open(path, encoding="utf-8") as fh:
            text = trim(src, fh.read())
        src.parser(text)                                   # the fixture must parse
        with open(os.path.join(FIXTURES, src.fixture), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        print(f"  {src.id:<22} {len(text):>8,} bytes -> tests/fixtures/pantheon/{src.fixture}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
