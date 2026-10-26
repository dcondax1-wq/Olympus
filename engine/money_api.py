"""The PC dashboard's "Road to $10K / Stingray 3LT" card (engine/money_goal.py) and its small local form.

Mounted by engine/next_api.py. Read-only to trading: the only write is the owner's money figures in the gitignored
data/goals_money.json (savings balance, the month's job income and Kalshi P&L, the car / plan settings). Nothing here arms,
routes, sizes or changes a config.

  GET  /api/next/money     the card (the running bot's accounts + the local figures) + "local": may this browser save
  POST /api/next/money     {"savings", "savings_day", "savings_delete", "month", "jobs", "kalshi", "settings"} -> saved + the
                           new card. Refused unless the request comes from a browser on this PC (engine/cloud_guard.local_only:
                           not the phone, not the cloud, not a proxy or tunnel, Host / Origin localhost); listed in
                           cloud_guard.CLOUD_BLOCKED (MONEY_WRITES).
"""
from __future__ import annotations

import json

from fastapi import APIRouter, Request
from fastapi.responses import Response

from . import cloud_guard, money_goal

router = APIRouter()
PATH = None                 # tests: a temp file instead of data/goals_money.json


def _J(obj, status=200):
    return Response(json.dumps(obj, separators=(",", ":"), default=str), media_type="application/json", status_code=status)


def _bot():
    """The PC bot or None (tests replace this function)."""
    try:
        from .live import BOT
        return BOT
    except Exception:
        return None


def card() -> dict:
    """The card from the running bot's blocks (the same ones /api/next/goals reads) + the local figures."""
    from .next_api import goals_data
    data = goals_data(_bot())
    return money_goal.build(data, money_goal.local_block(PATH))


@router.get("/api/next/money")
def r_money(request: Request):
    try:
        out = card()
        out["local"] = cloud_guard.local_only(request) is None
        out["local_why"] = None if out["local"] else cloud_guard.local_only(request)
        return _J(out)
    except Exception as e:                                   # never 500 the dashboard over a page
        return _J({"error": f"{e.__class__.__name__}: {e}"[:200]}, 500)


@router.post("/api/next/money")
async def r_money_save(request: Request):
    why = cloud_guard.local_only(request)
    if why is not None:
        return _J({"ok": False, "error": why, "local": False}, 403)
    if "application/json" not in (request.headers.get("content-type") or ""):
        return _J({"ok": False, "error": "send JSON"}, 400)
    try:
        d = await request.json()
    except Exception:
        d = None
    if not isinstance(d, dict):
        return _J({"ok": False, "error": "send a JSON object"}, 400)
    try:
        r = money_goal.save(d, PATH)
    except Exception as e:
        r = {"ok": False, "error": f"{e.__class__.__name__}: {e}"[:200]}
    if r.get("ok"):
        r.pop("inputs", None)
        try:
            r["card"] = card()
        except Exception as e:
            r["card"] = {"error": f"{e.__class__.__name__}: {e}"[:200]}
    return _J(r, 200 if r.get("ok") else 400)
