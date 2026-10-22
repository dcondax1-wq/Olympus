"""Read-only API of the Bot Brain (engine/brain.py) for the PC dashboard's "Bot Brain" area (web_next/js/next/brain.js).
Mounted by engine/next_api.py. Every route only READS: the PC bot's last Brain (engine/live.BOT.brain, built after each
LIT poll), the day's thought log (data/brain/YYYY-MM-DD.jsonl) and, for a replay, data/NQ_5m.csv + the 1m research bars.

  GET /api/next/brain                    the live Brain (full; ?compact=1 = the phone cut). No poll yet: {"empty": true,
                                         "reason", "latest_day"} (the page then offers the replay)
  GET /api/next/brain/log?day=YYYY-MM-DD the persisted thought log of a day (newest first, last 200)
  GET /api/next/brain/days               the 2026 sessions in the data (newest first) with the live run's trade of each
  GET /api/next/brain/day/{date}         that day replayed: ?t=<unix> or ?hm=HH:MM (ET; 18:00-23:59 = the evening before),
                                         default 16:00; &frames=1 adds the scrubber's stops (every 5m close)
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import re
import threading

from fastapi import APIRouter
from fastapi.responses import Response

from . import brain

router = APIRouter()
_cache: "collections.OrderedDict" = collections.OrderedDict()
_lock = threading.Lock()
CACHE_N = 400


def _J(obj, status=200):
    return Response(json.dumps(obj, separators=(",", ":"), default=str), media_type="application/json", status_code=status)


def _bot():
    """The PC bot (tests replace this function)."""
    from .live import BOT
    return BOT


@router.get("/api/next/brain")
def brain_now(compact: int = 0):
    bot = _bot()
    b = getattr(bot, "brain", None)
    if not b:
        try:
            latest = brain.sessions_2026()[0]["day"]
        except Exception:
            latest = None
        return _J({"empty": True, "running": bool(getattr(bot, "running", False)), "latest_day": latest,
                   "reason": ("The bot is running but has not finished a LIT poll yet." if getattr(bot, "running", False) else
                              "The bot is not running, so there is no live Brain. Start it on Bot Control, or replay a day.")})
    out = brain.compact(b) if compact else b
    return _J({**out, "running": bool(getattr(bot, "running", False))})


@router.get("/api/next/brain/second")
def brain_second():
    """The second-strategy brain (engine/second.py brain, closed bars only): per strategy ROUTED on <account> / paper, its
    stage, the waiting sentence, every rule check, the plan and today's log, from the PC bot's last run (LiveBot.second, the
    paper thread after LIT's routing). Read-only."""
    try:
        from . import second as S
        bot = _bot()
        run = getattr(bot, "second", None)
        ri = bot.second_route_info() if callable(getattr(bot, "second_route_info", None)) else None
        if not run:
            return _J({"empty": True, "strategies": {}, "route": ri,
                       "reason": "The PC bot has not run the second strategies yet (they run after each LIT poll while the bot runs)."})
        return _J({**S.compact(run, max_trades=3, route=ri), "running": bool(getattr(bot, "running", False))})
    except Exception as e:
        return _J({"error": f"{e.__class__.__name__}: {e}", "strategies": {}}, 500)


@router.get("/api/next/brain/log")
def brain_log(day: str = ""):
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day or ""):
        b = getattr(_bot(), "brain", None) or {}
        day = b.get("day") or str(dt.date.today())
    return _J({"day": day, "log": brain.read_day_log(day)})


@router.get("/api/next/brain/days")
def brain_days():
    try:
        return _J({"days": brain.sessions_2026()})
    except Exception as e:
        return _J({"error": f"{e.__class__.__name__}: {e}"}, 500)


@router.get("/api/next/brain/day/{day}")
def brain_day(day: str, t: int = 0, hm: str = "", frames: int = 0):
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
        return _J({"error": "day must be YYYY-MM-DD"}, 400)
    try:
        dt.date.fromisoformat(day)
    except ValueError:
        return _J({"error": "not a date"}, 400)
    try:
        if hm and re.fullmatch(r"\d{1,2}:\d{2}", hm):
            h, m = (int(x) for x in hm.split(":"))
            d0 = dt.date.fromisoformat(day) - dt.timedelta(days=1 if h >= 18 else 0)
            t = int(dt.datetime.combine(d0, dt.time(h, m), brain.ET).timestamp())
        t = int(t) if t else 0
        key = (day, t)
        with _lock:
            hit = _cache.get(key)
            if hit is not None:
                _cache.move_to_end(key)
        if hit is None:
            hit = brain.replay(day, t or None)
            with _lock:
                _cache[key] = hit
                while len(_cache) > CACHE_N:
                    _cache.popitem(last=False)
        out = dict(hit)
        if frames:
            out["frames"] = brain.replay_frames(day)
        return _J(out)
    except Exception as e:
        return _J({"error": f"{e.__class__.__name__}: {e}"}, 500)
