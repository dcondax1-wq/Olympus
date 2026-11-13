"""Guard pushes for the GitHub-free PC report (tools/pc_report.py, every 15 min on the main PC -> your private ntfy topic).
Read-only: it looks at what the bot already reports (its heartbeat, through engine/live_publish.build) and at NinjaTrader's
LE_BarFeed contract file. It never blocks, places, changes or cancels an order, never arms anything, never edits a setting.

  contract roll   engine/roll_watch.countdown: one push a day from 3 days before the roll to the eve (Mon Dec 7 .. Wed Dec 9
                  2026: "double-click ROLL.bat on Wed after 16:00 ET"), "roll ready" when the chart is already switched, the
                  late alarm while the chart sits on another month (no new entries), "roll done" once.

guard(state, snap, roll_state=None) -> (new state, [push]); state = {"sent": {key: t}}. Each key is sent once; pc_report
forgets a key whose push failed, so the next run tries it again. Quiet hours 23:00-07:00 ET (the roll's late alarm only
from 01:40 ET, before LIT's 02:00 window). Tests: tests/test_pc_guard.py.
"""
from __future__ import annotations

import datetime as dt
import time
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
PREFIX = "guard:"
KEEP_S = 40 * 86400                     # sent keys are kept 40 days (day keys never come back after that)
QUIET_FROM, QUIET_TO = 23 * 60, 7 * 60  # no ordinary guard push between 23:00 and 07:00 ET
LATE_FROM = 100                         # the roll's late alarm: from 01:40 ET


def _d(x) -> dict:
    return x if isinstance(x, dict) else {}


def _mod(now: int) -> int:
    e = dt.datetime.fromtimestamp(int(now), ET)
    return e.hour * 60 + e.minute


def quiet(now: int) -> bool:
    m = _mod(now)
    return m >= QUIET_FROM or m < QUIET_TO


# ------------------------------------------------------------------------------------------------ contract roll
def roll_pushes(now: int, roll_state=None) -> list:
    from engine import roll_watch
    st = roll_state if roll_state is not None else roll_watch.fact(None, {}, now)
    out = []
    for m in roll_watch.countdown(st, now):
        late = m["key"].startswith("roll:late:")
        if late and _mod(now) < LATE_FROM:
            continue
        if not late and quiet(now):
            continue
        out.append({"key": PREFIX + m["key"], "title": m["title"], "body": m["body"], "priority": m.get("priority") or "default",
                    "tags": "warning" if late else "calendar"})
    return out


# ------------------------------------------------------------------------------------------------ one run
def guard(state: dict | None, snap: dict, roll_state=None) -> tuple:
    """(new guard state, [push messages]) for one PC report run. Never raises (a failure sends nothing)."""
    st = {"sent": dict(_d(_d(state).get("sent")))}
    now = int(snap.get("t") or time.time())
    cands = []
    try:
        cands += roll_pushes(now, roll_state if roll_state is not None else snap.get("roll"))
    except Exception:
        pass
    msgs = []
    for m in cands:
        if m["key"] in st["sent"]:
            continue
        st["sent"][m["key"]] = now
        msgs.append(m)
    for k in [k for k, t in st["sent"].items() if now - int(t or 0) > KEEP_S]:
        st["sent"].pop(k, None)
    return st, msgs


def forget(state: dict | None, key: str) -> None:
    """A push that did not go out: drop its key so the next run sends it again."""
    _d(_d(state).get("sent")).pop(key, None)
