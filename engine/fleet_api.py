"""API of the fleet (engine/fleet.py) on the PC dashboard. Mounted by engine/next_api.py.

  GET  /api/next/fleet       every follower account: firm, plan, stage, balance, room to the floor (the firm's way),
                             today's / this week's P&L, open position, slippage vs the lead's fill, the last skipped copy and
                             why, rule warnings (unverified / unknown values); the leads' own accounts; the fleet kill flag;
                             the firm catalog (plans, verified / unknown counts, the owner's prices only). Read-only; with the
                             fleet off (no data/fleet.json) {"on": false} + the catalog, never a 500.
  POST /api/next/fleet/set   the Fleet page's buttons = the CLI (engine/fleet.run): add / remove / on / off / kill / unkill /
                             to_funded / payout on data/fleet.json. PC only (cloud_guard.local_only: never the phone, the
                             cloud or a proxy). It NEVER arms: arming a real account stays a console line (--arm) and real
                             trading still needs the typed phrase at the bot's start + NINJATRADER_LIVE=1.
"""
from __future__ import annotations

import json
import re
import time

from fastapi import APIRouter, Request
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


ACTIONS = ("add", "remove", "on", "off", "kill", "unkill", "to_funded", "payout")
_DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ID = re.compile(r"^[A-Za-z0-9_\-]{1,40}$")


def _argv(b: dict) -> list:
    """The page's request -> the CLI's arguments, every field checked (ValueError = refused)."""
    from . import firms as FM
    from . import fleet as FL
    act = str(b.get("action") or "")
    if act in ("arm", "disarm"):
        raise ValueError("arming is never done from a page: python -X utf8 -m engine.fleet --arm <id> on the PC (and the live phrase at the bot's start)")
    if act not in ACTIONS:
        raise ValueError(f"unknown action {act!r}")
    fid = str(b.get("id") or "")
    if not (_ID.match(fid) or (act in ("kill", "unkill") and fid == "all")):
        raise ValueError("id: letters, digits, - and _ only")

    def day(k, need=False):
        v = str(b.get(k) or "")
        if not v and not need:
            return None
        if not _DAY.match(v):
            raise ValueError(f"{k}: a day as yyyy-mm-dd")
        return v

    def num(k):
        v = b.get(k)
        if v in (None, ""):
            return None
        try:
            x = float(v)
        except (TypeError, ValueError):
            raise ValueError(f"{k}: a number")
        if x != x or x < 0 or x > 1e7:
            raise ValueError(f"{k}: out of range")
        return x

    def name(k):
        v = str(b.get(k) or "").strip()
        if any(c in v for c in ";|\r\n\"") or len(v) > 60:
            raise ValueError(f"{k}: no ; | quotes or line breaks, <= 60 characters")
        return v or None
    if act == "add":
        plan = str(b.get("plan") or "")
        if plan != "live" and plan not in FM.plans():
            raise ValueError(f"unknown plan {plan!r}")
        lead = str(b.get("lead") or "zlarior")
        if lead not in FL.LEADS:
            raise ValueError("lead: zlarior | atlas | blitz")
        out = ["--add", "--id", fid, "--plan", plan, "--lead", lead, "--start", day("start", need=True)]
        for k, flag in (("name", "--name"), ("account", "--account")):
            v = name(k)
            if v:
                out += [flag, v]
        for k, flag in (("balance", "--balance"), ("risk_usd", "--risk-usd"), ("max_risk", "--max-risk"), ("daily_stop", "--daily-stop"),
                        ("weekly_stop", "--weekly-stop")):
            v = num(k)
            if v is not None:
                out += [flag, f"{v:g}"]
        for k, flag in (("max_micros", "--max-micros"), ("stagger_ms", "--stagger-ms")):
            v = num(k)
            if v is not None:
                out += [flag, str(int(v))]
        return out
    if act == "to_funded":
        out = ["--to-funded", fid, "--start", day("start", need=True)]
        v = name("account")
        return out + (["--account", v] if v else [])
    if act == "payout":
        v = num("usd")
        if not v:
            raise ValueError("usd: the payout amount")
        return ["--payout", fid, f"{day('day', need=True)}={v:g}"]
    return [f"--{act}", fid]


async def _body(request: Request) -> dict:
    if "application/json" not in (request.headers.get("content-type") or ""):
        return {}
    try:
        b = await request.json()
        return b if isinstance(b, dict) else {}
    except Exception:
        return {}


@router.post("/api/next/fleet/set")
async def fleet_set(request: Request):
    from . import cloud_guard
    why = cloud_guard.local_only(request)
    if why is not None:
        return _J({"ok": False, "error": why, "local": False}, 403)
    try:
        argv = _argv(await _body(request))
    except ValueError as e:
        return _J({"ok": False, "error": str(e)}, 400)
    try:
        from . import fleet as FL
        rc, lines = FL.run(argv + ["--file", FL.FLEET_PATH])
        return _J({"ok": rc == 0, "out": "\n".join(lines)[-2000:]})
    except SystemExit:
        return _J({"ok": False, "error": "bad request"}, 400)
    except Exception as e:
        return _J({"ok": False, "error": f"{e.__class__.__name__}: {e}"[:200]}, 500)
