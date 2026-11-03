"""A deterministic demo for ARENA: HERMES's demo site data (tools/hermes/fixture.py: Zlarior on the MFFU 50K, ATLAS on its
25K, the cloud's paper twin) plus what ARENA reads besides: the Surface heartbeat's uptime per day, an older eval that was
passed and is now funded with one payout, one ATLAS trade closed by hand, and four weeks of phone-side events (Planner tasks,
habits and daily goals, Obsidian daily notes, the Kalshi bot's days, daily quests). Made-up (the page shows DEMO).

NOW is Friday 2026-10-30 17:00 ET, as in HERMES's fixture.
"""
from __future__ import annotations

import copy
import datetime as dt

from tools.hermes import fixture as HF

NOW = HF.NOW
TODAY = "2026-10-30"
DOWN_DAY, DEGRADED_DAY = "2026-10-13", "2026-10-21"


def _weekdays(a: str, b: str) -> list:
    d0, d1, out = dt.date.fromisoformat(a), dt.date.fromisoformat(b), []
    while d0 <= d1:
        if d0.weekday() < 5:
            out.append(d0.isoformat())
        d0 += dt.timedelta(days=1)
    return out


def _days(a: str, b: str) -> list:
    d0, d1, out = dt.date.fromisoformat(a), dt.date.fromisoformat(b), []
    while d0 <= d1:
        out.append(d0.isoformat())
        d0 += dt.timedelta(days=1)
    return out


def data() -> dict:
    d = copy.deepcopy(HF.data())
    days = [[x, 40.0 if x == DOWN_DAY else 75.0 if x == DEGRADED_DAY else 100.0] for x in _weekdays("2026-10-05", TODAY)]
    d["perf"] = {"status": {"parts": [{"id": "cloud", "days": [[x, 100.0] for x, _ in days]}, {"id": "surface", "days": days}]}}
    atlas = next(a for a in d["accounts"] if a["id"] == "atlas25k")
    e0 = HF.ts("2026-10-15", "10:40")
    atlas["trades"].insert(0, {"day": "2026-10-15", "entry_t": e0, "exit_t": e0 + 9 * 60, "side": "LONG", "qty": 5, "entry": 25010.0,
                               "stop": 24996.0, "target": 25038.0, "exit_px": 25004.0, "exit": "Manual close", "r": -0.4, "pnl": -60.0,
                               "risk_pts": 14.0, "sweep_ext": 24996.25})
    d["accounts"].insert(2, {"id": "mffu25k_funded", "name": "MFFU 25K Funded", "firm": "MFFU", "plan": "Builder 25K", "kind": "funded",
                             "source": "pc", "badge": "SIM", "trades": [], "orders": [],
                             "funded": {"start": "2026-10-07", "payouts": {"2026-10-28": 500.0}}})
    return d


def home() -> dict:
    return HF.home()


def phone_events() -> list:
    """Four weeks of the phone's own events (the page's demo shows them; the real ones come from the phone)."""
    out = []
    for i, day in enumerate(_days("2026-10-05", TODAY)):
        n = 2 + (i * 7) % 4                                   # 2-5 tasks done a day
        for k in range(n):
            out.append({"id": f"task:demo-{day}-{k}", "day": day, "kind": "task_done", "src": "planner", "note": "Demo task"})
        out.append({"id": f"habit:demo-gym:{day}", "day": day, "kind": "habit", "src": "planner", "note": "Gym"})
        if day >= "2026-10-21":                               # a 10-day daily-goal streak up to today
            out.append({"id": f"goal:{day}", "day": day, "kind": "goal_day", "src": "planner", "note": "Every habit checked in"})
        if i % 5 != 3:
            out.append({"id": f"journal:{day}", "day": day, "kind": "journal", "src": "obsidian", "note": f"Daily note {day}"})
        if dt.date.fromisoformat(day).weekday() < 5:
            out.append({"id": f"kalshi:{day}", "day": day, "kind": "kalshi_day", "src": "kalshi", "note": "Kalshi bot listed the day"})
    for day in _days("2026-10-24", "2026-10-29"):            # six quest sweeps in a row (the 7th is today's)
        for q in ("a", "b", "c"):
            out.append({"id": f"quest:{day}:{q}", "day": day, "kind": "quest", "src": "quest", "note": "Demo quest"})
        out.append({"id": f"quest:{day}:sweep", "day": day, "kind": "quest_sweep", "src": "quest", "note": "All 3 quests"})
    return out
