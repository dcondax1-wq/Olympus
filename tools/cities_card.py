"""OLYMPUS CITIES: the Jarvis card of the Cities hub (tools/web_public/cities/jarvis.json), with the "City of the day".

    python tools/cities_card.py              # writes tools/web_public/cities/jarvis.json for today (New York date)
    python tools/cities_card.py 2026-11-05   # for a given day (deterministic: the same date always picks the same city)

The city of the day is a pure function of the date and the list of city ids in cities.json: FNV-1a (32 bit) of "cities:<date>"
modulo the number of cities. util.js `cityOfDay()` does the same in the page, so the card and the page's Today chip agree.
`publish(out)` writes the card into a built site folder (<out>/cities/jarvis.json); read-only, nothing else is touched.
The Jarvis card contract is docs/JARVIS_APPS.md (<= 8 KB, plain text, kpis <= 3, lines <= 3).
"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(ROOT, "tools", "web_public", "cities")
STALE_AFTER = 129600           # 36 h: the card is rewritten with every site publish


def hash32(s: str) -> int:
    """FNV-1a 32 bit over the UTF-8 bytes (identical to util.js hash32 for ASCII)."""
    h = 0x811C9DC5
    for b in s.encode("utf-8"):
        h ^= b
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h


def city_of_day(date: str, ids: list[str]) -> str | None:
    return ids[hash32("cities:" + date) % len(ids)] if ids else None


def load_specs(path: str | None = None) -> list[dict]:
    with open(path or os.path.join(PAGE, "cities.json"), encoding="utf-8") as fh:
        return json.load(fh)["cities"]


def today_ny() -> str:
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    except Exception:                                    # no tz database: UTC is close enough
        return datetime.utcnow().strftime("%Y-%m-%d")


def build(date: str | None = None, now: int | None = None, specs: list[dict] | None = None) -> dict:
    specs = specs if specs is not None else load_specs()
    date = date or today_ny()
    by = {s["id"]: s for s in specs}
    cid = city_of_day(date, [s["id"] for s in specs])
    c = by[cid]
    sources = len({s["dataset"] for s in specs})
    return {
        "v": 1,
        "name": "Cities",
        "status": {"level": "ok", "label": f"Today: {c['name']}"[:48]},
        "kpis": [
            {"label": "Cities", "value": str(len(specs))},
            {"label": "City of the day", "value": c["name"][:24]},
            {"label": "Datasets", "value": str(sources)},
        ],
        "lines": [c["motto"][:120], f"Landmark: {c['landmark']['label']}. Tap to fly in."[:120]],
        "t": int(time.time() if now is None else now),
        "open": "#" + cid,
        "theme": "#07050f",
        "stale_after": STALE_AFTER,
    }


def dumps(card: dict) -> str:
    return json.dumps(card, separators=(",", ":"), ensure_ascii=True) + "\n"


def write(path: str, card: dict) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(dumps(card))


def publish(out: str) -> str:
    """Write <out>/cities/jarvis.json (the card for today) when the site build has the Cities page; returns a one-line status."""
    d = os.path.join(out, "cities")
    if not os.path.isdir(d):
        return "no cities folder in the build: skipped"
    card = build()
    write(os.path.join(d, "jarvis.json"), card)
    return f"city of the day {card['open'][1:]}"


def main(argv: list[str]) -> int:
    card = build(argv[0] if argv else None)
    write(os.path.join(PAGE, "jarvis.json"), card)
    print(f"cities card: {card['status']['label']} ({card['open']})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
