"""After you download the federal Do-Not-Call files into <home>/caller/registry/<area>.txt: records today's date and the area codes.
python -m tools.caller.registry   (re-run after every download; the gate refuses a copy older than 31 days)
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import sys

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    __package__ = "tools.caller"

from . import config as C  # noqa: E402


def stamp(h=None, today: dt.date | None = None) -> dict:
    d = os.path.join(C.state_dir(h), "registry")
    os.makedirs(d, exist_ok=True)
    codes = sorted(m.group(1) for n in os.listdir(d) if (m := re.fullmatch(r"(\d{3})\.txt", n)))
    meta = {"downloaded": (today or dt.date.today()).isoformat(), "area_codes": codes}
    with open(os.path.join(d, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f)
    return meta


if __name__ == "__main__":
    m = stamp()
    print(f"[OK] Do-Not-Call copy dated {m['downloaded']} for area codes {', '.join(m['area_codes']) or '(none found)'}")
    sys.exit(0 if m["area_codes"] else 1)
