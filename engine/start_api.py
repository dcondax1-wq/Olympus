"""The PC dashboard's Start & Accounts page (web_next/js/next/start.js): START BOT (engine/go.py) as one checklist with one
button per red line, and the account panel. Every write goes through engine/go.py's step / account functions, the same ones
START_BOT.bat runs, so the console and the page cannot drift apart.

Mounted by engine/next_api.py. GET is read-only and open to the phone (status only). Every POST is refused unless the
request comes from a browser on this PC (engine/cloud_guard.local_only: not the phone, not the cloud, not a proxy or
tunnel, Host / Origin localhost) and is listed in cloud_guard.CLOUD_BLOCKED. Nothing here arms by itself: arming needs the
owner's typed I ACCEPT LIVE RISK, checked here and again by engine/go.step_arm and engine/ninjatrader.

  GET  /api/next/start/status            checklist (6 lines), plain status line, accounts, NinjaTrader pick list, the job,
                                         need_phrase / resume_why (the one button), the PC clock
  GET  /api/next/start/boot              the commit this server booted on (engine/go.server_stale)
  POST /api/next/start/go                {"confirm"?: phrase} the one button "Start trading" (a job: engine/go.step_auto)
  POST /api/next/start/resume            start without the phrase through the auto-resume gate (engine/go.resume_now)
  POST /api/next/start/clock             "Sync the clock" (w32tm /resync, else the Windows Settings steps)
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
_FEED = {"t": 0.0, "v": None}


def _boot_sha():
    try:
        return go.head_sha()
    except Exception:
        return None


BOOT_SHA = _boot_sha()          # the commit this server booted on (engine/go.server_stale: restart it after an update)


@router.get("/api/next/start/boot")
def r_boot():
    return _J({"sha": BOOT_SHA})


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


def _feed():
    """LE_BarFeed's MNQ 5m bars: None = fresh, else why (go.feed_problem, cached 10 s)."""
    if time.time() - _FEED["t"] > 10:
        _FEED.update(t=time.time(), v=go.feed_problem())
    return _FEED["v"]


_CLK = {"t": 0.0, "v": None, "busy": False}
CLOCK_EVERY_S = 600


def _clock_probe():
    from . import guards
    return guards.clock_probe()


def _clock_run():
    try:
        d = _clock_probe()
        _CLK.update(v=None if d is None else {"drift_s": round(float(d), 2), "t": int(time.time())})
    except Exception:
        _CLK["v"] = None
    finally:
        _CLK["t"], _CLK["busy"] = time.time(), False


def _clock(fresh=False) -> dict:
    """The PC clock against internet time (engine/guards.clock_probe: only the drift the probe can prove), probed in a
    thread at most every 10 min (the page never waits for it). The bot's guard blocks new entries above 5 s."""
    if (fresh or time.time() - _CLK["t"] > CLOCK_EVERY_S) and not _CLK["busy"]:
        _CLK["busy"] = True
        import threading
        threading.Thread(target=_clock_run, name="start-clock", daemon=True).start()
    v = _CLK["v"]
    if v is None:
        return {"known": False, "ok": True, "say": "checking the PC clock against internet time" if _CLK["busy"] else
                "PC clock not checked (no internet answer)"}
    d = float(v["drift_s"])
    ok = abs(d) <= go.CLOCK_MAX_S
    side = "behind" if d > 0 else "ahead of"
    return {"known": True, "ok": ok, "drift_s": d, "t": v["t"],
            "say": "PC clock matches internet time" if abs(d) < 0.5 else
            f"PC clock {abs(d):.1f} s {side} internet time" + ("" if ok else f": new entries are blocked above {go.CLOCK_MAX_S:.0f} s")}


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
def r_status(request: Request, fresh: int = 0):
    if fresh:                                   # the page's "Check again"
        _NT["t"] = _FEED["t"] = 0.0
    try:
        st = go.status(state=_state(), connected=_connected, feed=_feed)
        st["accounts"] = go.accounts(_cards())
        st["local"] = cloud_guard.local_only(request) is None
        st["clock"] = _clock(fresh=bool(fresh))
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


@router.post("/api/next/start/go")
async def r_go(request: Request):
    """The one button "Start trading": every step in one job (engine/go.step_auto). The phrase is optional: needed only
    when the status says need_phrase (no valid auto-resume for the 50K); checked here, in the job and by ninjatrader."""
    d = await _body(request)
    phrase = go.typed_phrase(str(d.get("confirm") or "")) if d.get("confirm") else None
    if phrase is not None and phrase != go.LIVE_PHRASE:
        bad = _local(request)
        return bad if bad is not None else _J({"ok": False, "error": "Type I ACCEPT LIVE RISK exactly (or leave it empty). Nothing is armed."}, 400)
    return _do(request, lambda: go.job_start("auto", phrase))


def _start_fn():
    from . import botctl
    return botctl.HOOKS.get("start") or (lambda body: _bot().start(body))


def _stop_fn():
    from . import botctl
    return botctl.HOOKS.get("stop") or (lambda: _bot().stop())


@router.post("/api/next/start/resume")
def r_resume(request: Request):
    """Start without the phrase, through the auto-resume gate (engine/go.resume_now); the "Start trading" job calls it."""
    _NT["t"] = 0.0
    return _do(request, lambda: go.resume_now(_start_fn(), connected=_connected(), state_fn=_state, stop_fn=_stop_fn()))


@router.post("/api/next/start/clock")
def r_clock(request: Request):
    """"Sync the clock": w32tm /resync (engine/go.sync_clock), then a new probe here and in the bot's clock guard."""
    def run():
        r = go.sync_clock()
        try:
            from . import guards
            guards._CLOCK["t"] = 0.0                 # the bot's guard probes again at its next poll
        except Exception:
            pass
        _clock(fresh=True)
        return r
    return _do(request, run)


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
