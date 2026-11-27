"""The PC's thought logs for nq/story.html (day-thoughtlog web side, 2026-11-27).

The PC packs every bot's thoughts of a CME day into its day zip (engine/thoughtlog.py -> days/<day>/thoughts.jsonl.gz; the cloud
pulls it with tools/data_pull.py into data/pc_days/<day>/). This publishes the last KEEP days for the site:

  tools/web_public/nq/thoughts/index.json      {"v", "days": [{"day", "n", "bots": {lit: n, atlas: n, of: n}}]} newest first
  tools/web_public/nq/thoughts/<day>.json      {"v", "day", "rows": [[t, bot, kind, text], ...]} oldest first

Published again only from what the PC already masked (ids "...1234"); this run masks once more, drops BLITZ / hidden lanes and caps
each day (ROWS) and each line (220 characters). No network.

    python tools/nq_thoughts.py          (site build, after tools/data_pull.py)
"""
from __future__ import annotations

import gzip
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "data", "pc_days")
OUT = os.path.join(ROOT, "tools", "web_public", "nq", "thoughts")
KEEP, ROWS, LINE = 10, 1200, 220
BOTS = ("lit", "atlas", "of")
_ID = re.compile(r"\b[A-Za-z]{2,}\d{5,}\b|\b\d{7,}\b")


def clean(s) -> str:
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    return _ID.sub(lambda m: "..." + m.group(0)[-4:], s)[:LINE]


def read_day(day: str, src: str = SRC) -> list:
    p = os.path.join(src, day, "thoughts.jsonl.gz")
    rows = []
    try:
        for ln in gzip.decompress(open(p, "rb").read()).decode("utf-8").splitlines():
            try:
                r = json.loads(ln)
            except ValueError:
                continue
            if not isinstance(r, dict) or r.get("bot") not in BOTS or not isinstance(r.get("t"), (int, float)) or not r.get("text"):
                continue
            if re.search(r"blitz|acct_c", str(r.get("text")), re.I):
                continue
            rows.append([int(r["t"]), r["bot"], str(r.get("kind") or "")[:16], clean(r["text"])])
    except (OSError, ValueError, EOFError):
        return []
    rows.sort(key=lambda x: x[0])
    return rows[-ROWS:]


def build(src: str = SRC, out: str = OUT) -> dict:
    days = sorted((d for d in os.listdir(src) if re.match(r"^\d{4}-\d\d-\d\d$", d) and os.path.exists(os.path.join(src, d, "thoughts.jsonl.gz"))),
                  reverse=True)[:KEEP] if os.path.isdir(src) else []
    os.makedirs(out, exist_ok=True)
    idx = []
    for d in days:
        rows = read_day(d, src)
        if not rows:
            continue
        with open(os.path.join(out, f"{d}.json"), "w", encoding="utf-8") as fh:
            json.dump({"v": 1, "day": d, "rows": rows}, fh, separators=(",", ":"), ensure_ascii=False)
        idx.append({"day": d, "n": len(rows), "bots": {b: sum(1 for r in rows if r[1] == b) for b in BOTS}})
    keep = {f"{x['day']}.json" for x in idx} | {"index.json"}
    for f in os.listdir(out):                                    # older published days leave the site (the PC keeps its own copy)
        if f.endswith(".json") and f not in keep:
            os.remove(os.path.join(out, f))
    doc = {"v": 1, "days": idx, "note": "the PC's own thought log of each day (engine/thoughtlog.py): LIT's day log + ATLAS / OF lines"}
    with open(os.path.join(out, "index.json"), "w", encoding="utf-8") as fh:
        json.dump(doc, fh, separators=(",", ":"))
    return doc


def main():
    doc = build()
    print(f"nq_thoughts: {len(doc['days'])} day(s) published to tools/web_public/nq/thoughts/" + (f" (newest {doc['days'][0]['day']})" if doc["days"] else " (no PC thought logs pulled yet)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
