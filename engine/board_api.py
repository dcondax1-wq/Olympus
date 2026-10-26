"""Read-only API of the live board (engine/live_board.py) on the PC dashboard. Mounted by engine/next_api.py.

  GET /api/next/board    "Right now" per account (Zlarior 50K, ATLAS 25K), today's map (LIT levels, VIX objective, 18:00
                         open, price, points and $ per micro), the health strip (poll time, feed ages, NinjaTrader, clock,
                         last error, heartbeat, phone feed), week and eval progress (trades vs 2-4, session X of 10,
                         2-week odds, $ a month expected vs actual) and the trade log of both accounts

The inputs are the blocks the heartbeat already builds from the running bot (engine/heartbeat.py helpers: health, acct,
brain, second, live_pub, crit), the Goals data (engine/next_api.goals_data), the research odds files and the guards'
clock probe. Every read is wrapped: the page never 500s and nothing here starts, arms, routes, sizes, stops or writes.
Cached for CACHE_S seconds so the Home page and the board page polling together cost one build.
"""
from __future__ import annotations

import json
import os
import platform
import threading
import time

from fastapi import APIRouter
from fastapi.responses import Response

from . import live_board as LB

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_S = 4.0
router = APIRouter()
_lock = threading.Lock()
_cache: dict = {"t": 0.0, "v": None}


def _J(obj, status=200):
    return Response(json.dumps(obj, separators=(",", ":"), default=str), media_type="application/json", status_code=status)


def _bot():
    """The PC bot (tests replace this function)."""
    from .live import BOT
    return BOT


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def _lm() -> dict:
    try:
        with open(os.path.join(ROOT, "live_model.json"), encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def _hb_status() -> dict:
    """The heartbeat thread's last push ({"t", "ok", "enabled"}) through botctl.HOOKS (server.py fills it)."""
    from . import botctl
    fn = (getattr(botctl, "HOOKS", None) or {}).get("heartbeat")
    st = fn() if callable(fn) else {}
    last = (st or {}).get("last") or {}
    return {"t": last.get("at"), "ok": last.get("ok", True) if last else None, "enabled": (st or {}).get("enabled")}


def _clock(bot) -> dict:
    from . import guards
    c = dict(getattr(guards, "_CLOCK", {}) or {})          # the probe engine/guards.py runs every 15 min (read, never run here)
    return {"drift": c.get("drift"), "max": float(c.get("max") or 5.0)}


def pc_payload(bot, now: int) -> dict:
    """The heartbeat-shaped view of the running bot (same helpers as engine/heartbeat.Heartbeat.payload, no push)."""
    from . import heartbeat as HB
    st = getattr(bot, "state", None) or {}
    cfg = getattr(bot, "cfg", None) or {}
    pc = {"t": int(now), "present": True, "running": bool(getattr(bot, "running", False)), "kill": bool(getattr(bot, "kill", False)),
          "adapter": cfg.get("adapter", "paper"), "position": bool(st.get("position")), "model_state": st.get("model_state"),
          "host": platform.node(), "model": (st.get("strategy") or {}).get("model") or cfg.get("model"),
          "health": HB._health(bot), "acct": HB._acct(bot), "brain": HB._brain(bot), "second": HB._second(bot),
          "live_pub": HB._live_pub()}
    pc["crit"] = (_safe(lambda: HB._alerts_plus(bot), {}) or {}).get("crit") or []
    return pc


def board_view(bot, now: int | None = None) -> dict:
    from . import accounts as A
    now = int(now or _safe(lambda: int(bot.clock()), None) or time.time())
    lm = _lm()
    pc = pc_payload(bot, now)
    accounts = _safe(lambda: [a for a in A.build_accounts({"pc": {**pc, "age_s": 0, "silent": False}, "last_run": now}, lm, now)
                              if a.get("source") == "pc"], [])
    goals = None
    try:
        from . import goals as G
        from .next_api import goals_data
        goals = G.site_block(goals_data(bot, now), now=now)
    except Exception:
        goals = None
    odds, src = LB.odds_lit_live(lm)
    ab = getattr(bot, "acct_b", None)
    ledger = _safe(lambda: [dict(r) for r in list(getattr(ab, "ledger", None) or [])[-300:] if isinstance(r, dict)], []) if ab is not None else []
    inp = {"pc": pc, "accounts": accounts, "goals": goals, "odds_lit": odds, "odds_src": src, "atlas_info": LB.atlas_info_safe(),
           "heartbeat": _safe(_hb_status, {}), "clock": _safe(lambda: _clock(bot), {}), "atlas_ledger": ledger, "where": "pc",
           "n_trades": 80}
    return LB._json_safe(LB.build(inp, now))


@router.get("/api/next/board")
def r_board():
    try:
        with _lock:
            if _cache["v"] is not None and time.time() - _cache["t"] < CACHE_S:
                return _J(_cache["v"])
        v = board_view(_bot())
        with _lock:
            _cache.update(t=time.time(), v=v)
        return _J(v)
    except Exception as e:                       # never 500 the dashboard over a page
        return _J({"error": f"{e.__class__.__name__}: {str(e)[:160]}"}, 500)
