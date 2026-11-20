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


STATUS_FEED = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "tools", "web_public", "status_feed.json")


def fetch_pc_status(feed_path: str = STATUS_FEED, timeout: float = 15.0) -> dict | None:
    """day-archive 2026-11-20: the PC's newest status post (the public ntfy topic in status_feed.json, the same feed the site's pages
    read; the last 12 hours, all ntfy keeps). LIVE_URL is the retired old repo and only ever gave the fallback numbers."""
    try:
        feed = json.load(open(feed_path, encoding="utf-8"))
        url = f"{str(feed.get('ntfy') or 'https://ntfy.sh').rstrip('/')}/{feed['topic']}/json?poll=1&since=12h"
        with urllib.request.urlopen(url, timeout=timeout) as r:
            lines = r.read().decode("utf-8").splitlines()
        best = None
        for ln in lines:
            try:
                m = json.loads(ln)
                j = json.loads(m.get("message") or "") if m.get("event") == "message" else None
            except Exception:
                continue
            if isinstance(j, dict) and j.get("kind") != "le-live-ext" and isinstance(j.get("board"), dict) and (best is None or (_num(j.get("t")) or 0) > (_num(best.get("t")) or 0)):
                best = j
        return best
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
    if str(c.get("status") or "").lower() == "funded":      # day-archive 2026-11-20: a funded account passed its eval (its to_target is the payout's)
        to_t = 0.0
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
    src = "live.json"
    if path and os.path.exists(path):
        j = json.load(open(path, encoding="utf-8"))
    elif url:
        j = fetch_pc_status() if url == LIVE_URL else None
        src = "pc status post" if j else src
        j = j or fetch(url)
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
    return {"source": src if j else "fallback", "t": int(t) if t else None, "feed_day": feed_day.isoformat(),
            "first_session": first_session(t).isoformat(), "bots": bots, "trades": trades}
