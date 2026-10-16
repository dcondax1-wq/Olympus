"""Print the engine's high-impact USD releases in the Pine strategy's news-list format (one per line).

    python -X utf8 tools/pine_news.py [--from 2026-10-18] [--days 120]

Paste the output into the strategy's "Release times (ET)" input (Settings > Inputs > News blackout) so TradingView blocks
the same entries (15 min before / 30 min after, no FOMC afternoons) and flattens 5 min before a release, like
engine.model. The same calendar (data/news/events.csv + ff_archive.csv) feeds the Python engine.
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

ET = ZoneInfo("America/New_York")


def lines(day_from: str | None = None, days: int | None = None) -> list[str]:
    from engine import news
    a = dt.datetime.fromisoformat(day_from).replace(tzinfo=ET) if day_from else None
    b = a + dt.timedelta(days=days) if (a and days) else None
    out, seen = [], set()
    for e in news.historical_events(("high",)):
        t = dt.datetime.fromtimestamp(e["t"], ET)
        if (a and t < a) or (b and t >= b):
            continue
        label = e["event"].encode("ascii", "ignore").decode().replace('"', "").replace("\\", "").replace(";", ",").strip()
        slot = t.strftime("%Y-%m-%d %H:%M")
        if slot in seen:                      # one line per release time (the blackout only needs the time;
            continue                          # an FOMC slot keeps an FOMC label)
        seen.add(slot)
        out.append(f"{slot} {label}")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from", dest="day_from", default=dt.date.today().isoformat())
    ap.add_argument("--days", type=int, default=None)
    a = ap.parse_args()
    print("\n".join(lines(a.day_from, a.days)))


if __name__ == "__main__":
    main()
