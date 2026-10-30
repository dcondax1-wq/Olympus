"""Read-only API of the fleet (engine/fleet.py) on the PC dashboard. Mounted by engine/next_api.py.

  GET /api/next/fleet   every follower account: firm, plan, stage, balance, room to the floor (the firm's way), today's /
                        this week's P&L, open position, slippage vs the lead's fill, the last skipped copy and why, rule
                        warnings (unverified / unknown values); the leads' own accounts; the fleet kill flag; the firm
                        catalog (plans, verified / unknown counts, the owner's prices only) for the "Add an account" guide.

Nothing here starts, arms, routes, sizes or writes. With the fleet off (no data/fleet.json) it answers {"on": false} with
the catalog, never a 500.
"""
from __future__ import annotations

import json
import time

from fastapi import APIRouter
from fastapi.responses import Response

router = APIRouter()
_CAT: dict = {"t": 0.0, "v": None}


def _J(obj, status=200):
    return Response(json.dumps(obj, separators=(",", ":"), default=str), media_type="application/json", status_code=status)


def _bot():
    """The PC bot (tests replace this function)."""
    from .live import BOT
    return BOT


def catalog() -> list:
    """The firms and their plans, compact (cached 10 min)."""
    if _CAT["v"] is not None and time.time() - _CAT["t"] < 600:
        return _CAT["v"]
    from . import firms as FM
    D = FM.load()
    out = []
    for fid, f in (D.get("firms") or {}).items():
        plans = []
        for pid in f.get("plans") or []:
            P = FM.profile(pid)
            if P is None:
                continue
            ver = sum(1 for v in P["verified"].values() if v)
            plans.append({"id": pid, "name": P.get("plan"), "size": P.get("size"), "target": P.get("target"),
                          "dd": P.get("dd_amount"), "dd_type": P.get("dd_type"), "lock": P.get("lock"), "dll": P.get("dll"),
                          "dll_type": P.get("dll_type"), "micros": FM.max_micros(P), "cons": P.get("consistency"),
                          "min_days": P.get("min_days"), "price": P.get("price"), "verified": ver, "unknown": len(P["unknown"])})
        val = lambda k: (f.get(k) or {}).get("v") if isinstance(f.get(k), dict) else f.get(k)
        out.append({"id": fid, "name": f.get("name"), "bots": val("bots"), "hedging": val("hedging"), "copy": val("copy_trading"),
                    "ninjatrader": val("ninjatrader"), "flat_by": val("flat_by"), "plans": plans})
    _CAT.update(t=time.time(), v=out)
    return out


def _from_file() -> dict:
    """The bot is not running (or the fleet not built yet): the configured followers from data/fleet.json, read-only."""
    from . import fleet as FL
    d = FL.load_file()
    rows = []
    ids, names = set(), set()
    for r in d.get("accounts") or []:
        n = FL.normalize(r, ids, names)
        ids.add(n["id"])
        P = FL.profile_of(n) or {}
        rows.append({"id": n["id"], "name": n["name"], "lead": n["lead"], "lead_name": FL.LEAD_NAMES.get(n["lead"]),
                     "firm": P.get("firm"), "plan": P.get("plan"), "plan_id": n["plan"], "stage": n["stage"], "label": n["label"],
                     "status": "killed" if n["killed"] or d.get("kill") else ("off" if n["problem"] else "not running"),
                     "nt_account": n["nt_account"] or None, "warn": ([n["problem"]] if n["problem"] else []) + list(P.get("warn") or [])[:3]})
    return {"v": FL.VERSION, "on": bool(rows), "running": False, "kill": d.get("kill") is True, "accounts": rows, "leads": [], "totals": {}}


@router.get("/api/next/fleet")
def fleet_get():
    try:
        b = _bot()
        fl = getattr(b, "fleet", None) if b is not None else None
        if fl is not None:
            out = fl.api()
            out["running"] = bool(getattr(b, "running", False))
        else:
            try:
                out = _from_file()
            except Exception:
                out = {"on": False, "accounts": []}
            if not out.get("accounts"):
                out = {"v": 1, "on": False, "accounts": [], "running": bool(getattr(b, "running", False)) if b is not None else False,
                       "note": "Fleet off: no follower accounts. docs/ADD_ACCOUNT.md: python -X utf8 -m engine.fleet --add ..."}
        try:
            out["firms"] = catalog()
        except Exception as e:
            out["firms"] = []
            out["firms_error"] = f"{e.__class__.__name__}"
        return _J(out)
    except Exception as e:
        return _J({"on": False, "accounts": [], "error": f"{e.__class__.__name__}: {e}"[:200]})
