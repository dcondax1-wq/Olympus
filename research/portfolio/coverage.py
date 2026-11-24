"""24-hour coverage map of the NQ week (research/portfolio/DESIGN.md part 1). PAPER RESEARCH ONLY.
    python -X utf8 research/portfolio/coverage.py  -> research/portfolio/coverage.json + a text grid
"""
from __future__ import annotations

import collections
import datetime as dt
import gzip
import json
import os
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(HERE, "coverage.json")
ET = ZoneInfo("America/New_York")
DAYS = ("Sun", "Mon", "Tue", "Wed", "Thu", "Fri")
PILLARS = ("lit", "atlas", "blitz")


def slot_of(ts):
    t = dt.datetime.fromtimestamp(int(ts), ET)
    return t.strftime("%a"), f"{t.hour:02d}:{30 * (t.minute // 30):02d}"


def mffu(day, s):
    """The account limits on that slot (docs/ACCOUNT_RULES.md)."""
    h, m = map(int, s.split(":"))
    mins = h * 60 + m
    if day == "Sun" and mins < 1080:
        return "closed"
    if day == "Fri" and mins >= 1020:
        return "closed"
    if 1020 <= mins < 1080:
        return "closed (17:00-18:00 CME halt)"
    if 960 <= mins < 1020:
        return "no new trades (bot flat 15:55, MFFU auto-close 16:10)"
    if mins == 930:
        return "bot flat 15:55; LIT entries end 15:30"
    if mins in (510, 840):
        return "open; 08:30 / 14:00 = main US news times (Rapid FUNDED: flat +-2 min)"
    return "open"


def run(say=print):
    rows = [json.loads(x) for x in gzip.open(os.path.join(ROOT, "research", "learn", "lessons.jsonl.gz"), "rt", encoding="utf-8")]
    rows = [r for r in rows if r.get("span") in ("2021-25", "H1", "H2") and r.get("pillar") in PILLARS and r.get("entry_t")]
    cell = collections.defaultdict(lambda: {"n": 0, "usd": 0.0, "n26": 0, "usd26": 0.0})
    members = collections.defaultdict(set)
    for r in rows:
        d, s = slot_of(r["entry_t"])
        k = (d, s, r["pillar"])
        c = cell[k]
        c["n"] += 1
        c["usd"] += float(r.get("usd") or 0)
        if r["span"] in ("H1", "H2"):
            c["n26"] += 1
            c["usd26"] += float(r.get("usd") or 0)
        if r.get("member"):
            members[(r["pillar"], r["member"])].add(s)
    grid = []
    for d in DAYS:
        for h in range(24):
            for m in (0, 30):
                s = f"{h:02d}:{m:02d}"
                lim = mffu(d, s)
                row = {"day": d, "slot": s, "mffu": lim, "pillars": {}}
                for p in PILLARS:
                    c = cell.get((d, s, p))
                    if c and c["n"]:
                        row["pillars"][p] = {k: round(v) if isinstance(v, float) else v for k, v in c.items()}
                can = []
                mins = h * 60 + m
                if lim.startswith("open") or lim.startswith("bot flat"):
                    if 120 <= mins <= 930 and d != "Sun":
                        can.append("LIT")
                    for p in ("atlas", "blitz"):
                        if any((dd, s, p) in cell for dd in DAYS):
                            can.append(p.upper())
                row["can_trade"] = can
                row["status"] = ("closed" if lim.startswith("closed") or lim.startswith("no new") else
                                 "covered" if row["pillars"] else "EMPTY (open, no live strategy has traded it)")
                grid.append(row)
    open_slots = [g for g in grid if g["status"] != "closed"]
    empty = [g for g in open_slots if g["status"].startswith("EMPTY")]
    by_hour = collections.defaultdict(lambda: {"open_slots": 0, "covered": 0, "usd": 0, "n": 0})
    for g in open_slots:
        b = by_hour[g["slot"]]
        b["open_slots"] += 1
        b["covered"] += g["status"] == "covered"
        for p, c in g["pillars"].items():
            b["usd"] += c["usd"]; b["n"] += c["n"]
    J = {"made": "2026-11-24", "source": "research/learn/lessons.jsonl.gz (LIT / ATLAS / BLITZ backtests, 2021-25 + 2026, costs in)",
         "open_slots": len(open_slots), "covered_slots": len(open_slots) - len(empty), "empty_slots": len(empty),
         "covered_pct": round(100 * (len(open_slots) - len(empty)) / len(open_slots), 1),
         "atlas_members_slots": {f"{p}/{m}": sorted(v) for (p, m), v in members.items()},
         "by_time_of_day": dict(sorted(by_hour.items())), "grid": grid}
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(J, fh, indent=1)
    say(f"open 30-min slots a week {J['open_slots']}, covered {J['covered_slots']} ({J['covered_pct']}%), empty {J['empty_slots']}")
    for s, b in sorted(by_hour.items()):
        say(f"  {s}  covered {b['covered']}/{b['open_slots']} days  trades {b['n']:5d}  ${b['usd']:>9,}")
    return J


if __name__ == "__main__":
    run()
