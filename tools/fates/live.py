"""FATES: today's real eval state, read from the PC's published live feed (live.json on the nq-dashboard `live` branch,
the file Jarvis reads), with the owner's numbers as fallbacks.

    state = read_live()          # {"source", "t", "first_session", "bots": {"zlarior": {...}, "atlas": {...}}, "trades": [...]}

Per bot: profit (balance - start), floor and peak (relative to the start), session (sessions already traded in this eval),
quiet_days (calendar days without a trade), last_trade (date), eval_start, the plan. Read only; nothing is written to the feed.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import urllib.request
from zoneinfo import ZoneInfo

from tools.fates.rules import load_rules, trading_days
from tools.fates.sources import today_state_defaults

LIVE_URL = "https://raw.githubusercontent.com/demetrades2000-coder/nq-dashboard/live/live.json"
NY = ZoneInfo("America/New_York")
BOARD_KEYS = {"zlarior": "lit", "atlas": "atlas"}
# CME equity futures full closures in the simulated year ahead (the inactivity clock still runs on them)
CLOSED = {"2026-11-26", "2026-12-25", "2027-01-01", "2027-03-26", "2027-11-25"}


def fetch(url: str = LIVE_URL, timeout: float = 8.0) -> dict | None:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def _num(x):
    try:
        v = float(x)
        return v if v == v else None
    except (TypeError, ValueError):
        return None


def bot_state(bot: str, card: dict | None, fallback: dict, today: dt.date) -> dict:
    """One bot's eval in $ relative to its start balance (profit, floor, peak), from its live.json board card."""
    R = load_rules(fallback["plan"])
    c = card if isinstance(card, dict) else {}
    room, to_t = _num(c.get("room")), _num(c.get("to_target"))
    src = "live" if room is not None and to_t is not None else "fallback"
    if src == "fallback":
        room, to_t = fallback["room"], fallback["to_target"]
    profit = R.target - to_t
    floor = profit - room
    # the floor trails the best end-of-day balance by the max loss until it locks at start + $100
    peak = floor + R.mll if floor < R.lock - 1e-9 else max(profit, R.lock + R.mll)
    session = int(_num(c.get("session")) or fallback["session"])
    quiet = _num(c.get("quiet_days"))
    quiet = int(quiet) if quiet is not None else int(fallback["quiet_days"])
    return {"bot": bot, "source": src, "plan": R.key, "plan_name": R.name, "profit": round(profit, 2), "floor": round(floor, 2),
            "peak": round(max(peak, profit), 2), "room": round(room, 2), "to_target": round(to_t, 2), "session": session,
            "quiet_days": quiet, "last_trade": (today - dt.timedelta(days=quiet)).isoformat(),
            "eval_start": c.get("eval_start"), "status": c.get("status") or "open"}


def first_session(t: float | None) -> dt.date:
    """The next session to be simulated: the feed's ET day if it is a weekday before 16:00 ET, else the next weekday."""
    now = dt.datetime.fromtimestamp(t, NY) if t else dt.datetime.now(NY)
    d = now.date() if now.hour < 16 else now.date() + dt.timedelta(days=1)
    while d.weekday() >= 5 or d.isoformat() in CLOSED:
        d += dt.timedelta(days=1)
    return d


def calendar(start: dt.date, n: int) -> list[dt.date]:
    """The n sessions from start: weekdays without the CME full closures."""
    return [d for d in trading_days(start, n + 10) if d.isoformat() not in CLOSED][:n]


def read_live(path: str | None = None, url: str | None = LIVE_URL) -> dict:
    """path = a saved live.json (tests, offline builds); else the published feed; else the fallbacks."""
    j = None
    if path and os.path.exists(path):
        j = json.load(open(path, encoding="utf-8"))
    elif url:
        j = fetch(url)
    t = _num((j or {}).get("t"))
    feed_day = dt.datetime.fromtimestamp(t, NY).date() if t else dt.datetime.now(NY).date()
    board = (j or {}).get("board") or {}
    fb = today_state_defaults()
    bots = {b: bot_state(b, board.get(k), fb[b], feed_day) for b, k in BOARD_KEYS.items()}
    trades = []
    for x in board.get("trades") or []:
        if isinstance(x, dict) and x.get("src") == "live" and x.get("acct") in ("lit", "atlas") and _num(x.get("usd")) is not None:
            trades.append({"bot": "zlarior" if x["acct"] == "lit" else "atlas", "day": str(x.get("day"))[:10], "side": x.get("side"),
                           "usd": round(float(x["usd"]), 2), "exit": x.get("exit"), "qty": x.get("qty")})
    return {"source": "live.json" if j else "fallback", "t": int(t) if t else None, "feed_day": feed_day.isoformat(),
            "first_session": first_session(t).isoformat(), "bots": bots, "trades": trades}
