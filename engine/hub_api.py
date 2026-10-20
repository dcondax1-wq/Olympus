"""Read-only API for the PC dashboard's hub pages (web_next/js/next/hubpages.js): Prop Firms, Business, Market, Learn,
System. Mounted by engine/next_api.py. Every route is a GET over repo files (tools/hub_data.py) plus the PC bot's own
account, LIT plan and log when the bot is there. Nothing here starts, arms, routes, sizes or stops anything.

  GET /api/next/hub/firms              research/props/firms.json + LIT fit per plan + flat comparison table + combos
  GET /api/next/hub/business           payout calendar, live-move guide, fees + net P&L, tax set-aside, goal, eval odds,
                                       floor gauge, MFFU compliance, scaling + withdrawal planner inputs
  GET /api/next/hub/market             week calendar, mega-cap earnings, CME holidays, roll, VIX / VXN + target band,
                                       overnight recap, weekly / monthly levels
  GET /api/next/hub/learn              strategy versions, research library, LIT glossary, trade gallery, upgrades tracker
  GET /api/next/hub/system             discipline log, PC uptime, data quality
  GET /api/next/hub/odds?profit=&session=&room=   Monte Carlo eval odds from a given state
  GET /api/next/hub/gallery/<file.png> an annotated chart from research/lab/gallery (png only)
"""
from __future__ import annotations

import json
import os
import time

from fastapi import APIRouter
from fastapi.responses import FileResponse, Response

from tools import hub_data as H

router = APIRouter()
GALLERY = os.path.join(H.LAB, "gallery")


def _J(obj, status=200):
    return Response(json.dumps(obj, separators=(",", ":"), default=str), media_type="application/json", status_code=status)


def _bot():
    """The PC bot (engine/pcdash_api._bot, which the tests replace). None when it cannot be loaded."""
    try:
        from . import pcdash_api
        return pcdash_api._bot()
    except Exception:
        return None


def _account(bot):
    if bot is None:
        return None
    try:
        from . import pcdash_api
        ac = pcdash_api.account_view(bot, bars=False)
        return None if ac.get("error") else ac
    except Exception:
        return None


def _brief(bot):
    if bot is None:
        return None
    try:
        from . import botctl
        p = botctl.plan_view(bot)
        return p.get("_brief") if not p.get("error") else None
    except Exception:
        return None


def _wrap(fn, *a):
    try:
        d = fn(*a)
        return _J(d, 500 if isinstance(d, dict) and d.get("error") and len(d) == 1 else 200)
    except Exception as e:                                   # never 500 the dashboard over a panel without a reason
        return _J({"error": f"{e.__class__.__name__}: {str(e)[:160]}"}, 500)


@router.get("/api/next/hub/firms")
def hub_firms():
    return _wrap(H.firms_view)


@router.get("/api/next/hub/business")
def hub_business():
    bot = _bot()
    return _wrap(lambda: H.business_view(_account(bot), now=time.time()))


@router.get("/api/next/hub/market")
def hub_market():
    bot = _bot()
    return _wrap(lambda: H.market_view(_brief(bot), now=time.time()))


@router.get("/api/next/hub/learn")
def hub_learn():
    return _wrap(H.learn_view)


@router.get("/api/next/hub/system")
def hub_system():
    bot = _bot()
    return _wrap(lambda: H.system_view(bot, now=time.time()))


@router.get("/api/next/hub/odds")
def hub_odds(profit: float = 0.0, session: int = 1, room: float | None = None):
    return _wrap(lambda: H.eval_odds(float(profit), max(1, int(session)), room))


@router.get("/api/next/hub/gallery/{name:path}")
def hub_gallery(name: str):
    p = os.path.realpath(os.path.join(GALLERY, name))
    if not p.startswith(os.path.realpath(GALLERY) + os.sep) or not p.lower().endswith(".png") or not os.path.isfile(p):
        return _J({"error": "not found"}, 404)
    return FileResponse(p, media_type="image/png")
