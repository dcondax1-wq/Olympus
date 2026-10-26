"""The PC dashboard's Start & Accounts page (web_next/js/next/start.js): START BOT (engine/go.py) as one checklist with one
button per red line, and the account panel. Every write goes through engine/go.py's step / account functions, the same ones
START_BOT.bat runs, so the console and the page cannot drift apart.

Mounted by engine/next_api.py. GET is read-only and open to the phone (status only). Every POST is refused unless the
request comes from a browser on this PC (engine/cloud_guard.local_only: not the phone, not the cloud, not a proxy or
tunnel, Host / Origin localhost) and is listed in cloud_guard.CLOUD_BLOCKED. Nothing here arms by itself: arming needs the
owner's typed I ACCEPT LIVE RISK, checked here and again by engine/go.step_arm and engine/ninjatrader.

  GET  /api/next/start/status            checklist (6 lines), plain status line, accounts, NinjaTrader pick list, the job
  POST /api/next/start/names             {"lit": 50K Name, "atlas": 25K Name}
  POST /api/next/start/nt                open NinjaTrader (no wait)
  POST /api/next/start/setup             launch prep for the saved names (engine/launch_prep)
  POST /api/next/start/sims              the two Sim101 roundtrips (a job: the server is stopped and started again)
  POST /api/next/start/arm               {"confirm": "I ACCEPT LIVE RISK"} arm the 25K, live switch, start, verify (a job)
  POST /api/next/start/accounts/add      {"name", "plan": builder50k|builder25k, "strategy": zlarior|atlas, "start"}
  POST /api/next/start/accounts/remove   {"name"}
  POST /api/next/start/accounts/anchor   {"name", "balance", "floor", "as_of"}
  POST /api/next/start/accounts/funded   {"name", "funded_name", "start"}
"""
from __future__ import annotations

import json
import time

from fastapi import APIRouter, Request
from fastapi.responses import Response

from . import cloud_guard, go

router = APIRouter()
_NT = {"t": 0.0, "v": None}


def _J(obj, status=200):
    return Response(json.dumps(obj, separators=(",", ":"), default=str), media_type="application/json", status_code=status)


def _bot():
    """The PC bot (tests replace this function)."""
    from .live import BOT
    return BOT


def _running() -> bool:
    return bool(getattr(_bot(), "running", False))


go.bot_running = _running            # in the server: read the bot itself, not through the server's own HTTP port


def _state() -> dict:
    b = _bot()
    return {"running": bool(getattr(b, "running", False)), "cfg": dict(getattr(b, "cfg", None) or {})}


def _connected():
    """NinjaTrader CONNECTED (cached 10 s: the page polls)."""
    if time.time() - _NT["t"] > 10:
        from . import autoresume
        _NT.update(t=time.time(), v=autoresume.nt_connected({"adapter": "ninjatrader"}))
    return _NT["v"]


def _cards() -> dict:
    try:
        from . import pc_cc_api as C
        b = _bot()
        if not getattr(b, "running", False):
            return {}
        now = C._now(b)
        return {"lit": C._lit_card(b, now, C._lm()), "atlas": C._atlas_card(b, now)}
    except Exception:
        return {}


def _local(request: Request):
    why = cloud_guard.local_only(request)
    return None if why is None else _J({"ok": False, "error": why, "local": False}, 403)


async def _body(request: Request) -> dict:
    if "application/json" not in (request.headers.get("content-type") or ""):
        return {}
    try:
        d = await request.json()
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


@router.get("/api/next/start/status")
def r_status(request: Request):
    try:
        st = go.status(state=_state(), connected=_connected)
        st["accounts"] = go.accounts(_cards())
        st["local"] = cloud_guard.local_only(request) is None
        return _J(st)
    except Exception as e:
        return _J({"error": f"{e.__class__.__name__}: {e}"[:200]}, 500)


def _do(request: Request, fn):
    bad = _local(request)
    if bad is not None:
        return bad
    try:
        r = fn()
    except Exception as e:
        r = {"ok": False, "error": f"{e.__class__.__name__}: {e}"[:200]}
    return _J(r, 200 if r.get("ok") else 400)


@router.post("/api/next/start/names")
async def r_names(request: Request):
    d = await _body(request)
    return _do(request, lambda: go.set_names(d.get("lit"), d.get("atlas")))


@router.post("/api/next/start/nt")
def r_nt(request: Request):
    _NT["t"] = 0.0
    return _do(request, go.open_nt)


@router.post("/api/next/start/setup")
def r_setup(request: Request):
    return _do(request, go.run_setup)


@router.post("/api/next/start/sims")
def r_sims(request: Request):
    return _do(request, lambda: go.job_start("sims"))


@router.post("/api/next/start/arm")
async def r_arm(request: Request):
    d = await _body(request)
    phrase = str(d.get("confirm") or "")
    if phrase != go.LIVE_PHRASE:            # checked before anything else; step_arm and engine/ninjatrader check it again
        bad = _local(request)
        return bad if bad is not None else _J({"ok": False, "error": "Type I ACCEPT LIVE RISK exactly. Nothing is armed."}, 400)
    return _do(request, lambda: go.job_start("arm", phrase))


@router.post("/api/next/start/accounts/add")
async def r_add(request: Request):
    d = await _body(request)
    return _do(request, lambda: go.add_account(d.get("name"), d.get("plan"), d.get("strategy"), d.get("start")))


@router.post("/api/next/start/accounts/remove")
async def r_remove(request: Request):
    d = await _body(request)
    return _do(request, lambda: go.remove_account(d.get("name")))


@router.post("/api/next/start/accounts/anchor")
async def r_anchor(request: Request):
    d = await _body(request)
    return _do(request, lambda: go.set_anchor(d.get("name"), d.get("balance"), d.get("floor"), d.get("as_of")))


@router.post("/api/next/start/accounts/funded")
async def r_funded(request: Request):
    d = await _body(request)
    return _do(request, lambda: go.to_funded(d.get("name"), d.get("funded_name"), d.get("start"), d.get("plan")))
