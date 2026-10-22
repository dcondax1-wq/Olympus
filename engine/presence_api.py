"""PC dashboard API for the "I'm here" check-in, the entry pause and the weekly hands-off score (server.py includes it).

  GET  /api/next/presence            status + the presence log (windows, bot trades, present at entry?, overlap)  ?days=14
  POST /api/next/presence/checkin    {"hours": 4} optional: one "in" line in data/presence.jsonl (src pc)
  POST /api/next/presence/checkout   "I'm leaving": closes the window
  GET  /api/next/pause               the running pause (or null)
  POST /api/next/pause               {"until": "HH:MM" | "tomorrow" | "YYYY-MM-DD"}: no new entries until then (+ hands-off event)
  POST /api/next/pause/clear         resume entries (lift the pause)
  GET  /api/next/handsoff            the weekly hands-off score cards ?weeks=4
Files only (engine/presence.py, engine/entry_pause.py, engine/handsoff.py): nothing here starts, arms, routes or sizes
anything; a pause only ever blocks new entries. The presence_required guard stays whatever live_model.json says (OFF).
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Request
from fastapi.responses import Response

from . import entry_pause, handsoff, presence

router = APIRouter()
_BOT = {"bot": None}


def bind(bot):
    _BOT["bot"] = bot


def _bot():
    if _BOT["bot"] is None:
        from .live import BOT
        _BOT["bot"] = BOT
    return _BOT["bot"]


def _J(obj, status=200):
    return Response(json.dumps(obj, separators=(",", ":"), default=str), media_type="application/json", status_code=status)


async def _body(req: Request) -> dict:
    try:
        d = await req.json()
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _cfg(bot) -> dict:
    try:
        from . import guards
        return guards.config(bot)
    except Exception:
        return {}


def _clock(bot):
    try:
        return int(bot.clock())
    except Exception:
        import time
        return int(time.time())


@router.get("/api/next/presence")
def get_presence(days: int = 14):
    bot = _bot()
    v = presence.log_view(now=_clock(bot), days=max(1, min(60, int(days))), path=presence.path_for(bot), bot=bot, cfg=_cfg(bot))
    v["pause"] = entry_pause.active(_clock(bot), entry_pause.path_for(bot))
    return _J(v)


@router.post("/api/next/presence/checkin")
async def post_checkin(req: Request):
    bot = _bot()
    b = await _body(req)
    row = presence.check_in("pc", b.get("hours") or _cfg(bot).get("presence_hours"), _clock(bot), presence.path_for(bot))
    return _J({"ok": True, "row": row, "status": presence.status(_clock(bot), presence.path_for(bot), _cfg(bot))})


@router.post("/api/next/presence/checkout")
def post_checkout():
    bot = _bot()
    row = presence.check_out("pc", _clock(bot), presence.path_for(bot))
    return _J({"ok": True, "row": row, "status": presence.status(_clock(bot), presence.path_for(bot), _cfg(bot))})


@router.get("/api/next/pause")
def get_pause():
    bot = _bot()
    return _J({"pause": entry_pause.active(_clock(bot), entry_pause.path_for(bot))})


@router.post("/api/next/pause")
async def post_pause(req: Request):
    bot = _bot()
    b = await _body(req)
    r = entry_pause.set_pause(b.get("until"), _clock(bot), entry_pause.path_for(bot), src="pc")
    if not r.get("ok"):
        return _J(r, 400)
    handsoff.record("pause", "dashboard", f"no new entries until {r['label']}", now=_clock(bot), path=handsoff.path_for(bot))
    try:
        bot._log("risk", f"PAUSE: new entries paused until {r['label']} (PC dashboard); open trades keep their stop / target")
    except Exception:
        pass
    return _J(r)


@router.post("/api/next/pause/clear")
def post_pause_clear():
    bot = _bot()
    was = entry_pause.clear(entry_pause.path_for(bot), _clock(bot))
    try:
        if was:
            bot._log("system", "PAUSE lifted: new entries allowed again (PC dashboard)")
    except Exception:
        pass
    return _J({"ok": True, "was_paused": was})


@router.get("/api/next/handsoff")
def get_handsoff(weeks: int = 4):
    bot = _bot()
    return _J(handsoff.view(now=_clock(bot), weeks=max(1, min(26, int(weeks))), path=handsoff.path_for(bot),
                            presence_path=presence.path_for(bot), bot=bot))
