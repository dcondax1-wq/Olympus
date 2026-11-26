"""RISK-DISTANCE ALARMS (day-guard2 2026-11-26): how many $ each account has left before an MFFU limit, from the bot's own numbers.

Read-only: never sizes, routes, arms or closes anything (the bot keeps its own stops and its own room sizing). It reads the live
view the phone already gets (engine/live_publish.build: the board cards lit / atlas and the extra accounts' sections) and says:

  distance    per account, the nearer of the two MFFU limits, live (the open trade's unrealized loss counted):
                floor   room to the trailing max-loss floor  = room + min(0, unrealized)
                day     the daily loss limit left            = dll - max(dll used, -(today + min(0, unrealized)))
              at $500 / $300 / $150 left: ONE push per level per account per CME day (only the highest new level: 600 -> 120 is
              one push). $150 is LOUD (urgent, rings in quiet hours); $300 high; $500 normal.
  payout      on a FUNDED account the push adds its payout-buffer state (engine/payout_autopilot views: "payout requestable now:
              $1,000 ($800 to you)" or why not yet). The after-close "REQUEST PAYOUT TODAY" stays engine/payout_autopilot's job.
Hidden bots (BLITZ) are never named. Finished accounts (passed / failed / lost) are skipped.
Called by tools/pc_guard.guard (the PC's report, every 15 min; Telegram / Discord first through engine/alert_bus when set up).
  python -X utf8 -m engine.risk_alarm          the distances now (from the running bot's live view, read-only)
Tests: tests/test_guard2.py.
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
LEVELS = (500.0, 300.0, 150.0)
PREFIX = "guard:risk:"
DONE = ("passed", "failed", "lost", "graduated", "stuck", "not set up", "off")


def _d(x) -> dict:
    return x if isinstance(x, dict) else {}


def _f(x):
    try:
        return None if x is None or isinstance(x, bool) else float(x)
    except (TypeError, ValueError):
        return None


def money(x) -> str:
    v = _f(x) or 0.0
    return ("-" if v < 0 else "") + f"${abs(v):,.0f}"


def trading_day(now) -> str:
    return (dt.datetime.fromtimestamp(int(now), ET) + dt.timedelta(hours=6)).date().isoformat()


def _hidden() -> tuple:
    try:
        from . import hidden_bots
        return tuple(hidden_bots.hidden() or ())
    except Exception:  # noqa: BLE001
        return ("blitz",)


def distance(room, dll, dll_used, today, unreal) -> dict:
    """{"left", "limit" (floor | day), "floor_left", "day_left"} or {} when nothing is known. Pure."""
    room, dll = _f(room), _f(dll)
    u = min(0.0, _f(unreal) or 0.0)
    fl = None if room is None else room + u
    dl = None
    if dll:
        used = max(_f(dll_used) or 0.0, -((_f(today) or 0.0) + u), 0.0)
        dl = dll - used
    if fl is None and dl is None:
        return {}
    if dl is None or (fl is not None and fl <= dl):
        return {"left": round(fl, 2), "limit": "floor", "floor_left": fl, "day_left": dl}
    return {"left": round(dl, 2), "limit": "day", "floor_left": fl, "day_left": dl}


def rows(live: dict) -> list:
    """[{id, name, funded, real, left, limit, floor_left, day_left, unreal}] for every running eval / funded account in the view."""
    live = _d(live)
    hide = set(_hidden())
    out = []
    bd = _d(live.get("board"))
    names = {"lit": "Zlarior 50K", "atlas": "ATLAS 25K"}
    for k in ("lit", "atlas", "blitz"):
        c = _d(bd.get(k))
        if not c or k in hide or c.get("error") or c.get("off") or str(c.get("status") or "").lower() in DONE:
            continue
        if k != "lit" and c.get("configured") is False:
            continue
        pos = _d(c.get("position"))
        dist = distance(c.get("room"), c.get("dll"), c.get("dll_used"), c.get("today_pnl"), pos.get("unrealized_usd"))
        if not dist:
            continue
        funded = str(c.get("status") or "").lower() == "funded" or c.get("stage") == "funded"
        real = bool(c.get("real")) or "LIVE" in str(c.get("badge") or "").upper() or (k == "lit" and live.get("mode") == "LIVE")
        out.append({"id": k, "name": names.get(k, str(c.get("name") or k.upper())[:30]), "funded": funded, "real": real,
                    "unreal": _f(pos.get("unrealized_usd")), **dist})
    for a in live.get("accounts") or []:
        a = _d(a)
        aid = str(a.get("id") or "")
        if not a.get("extra") or not aid or a.get("error") or aid in hide or aid == "acct_c" or a.get("kind") not in ("eval", "funded"):
            continue
        ev = _d(a.get("eval"))
        if str(ev.get("status") or "").lower() in DONE:
            continue
        pos = _d(a.get("position"))
        dist = distance(ev.get("room"), ev.get("dll"), ev.get("dll_used"), ev.get("today"), pos.get("unrealized_usd"))
        if not dist:
            continue
        try:
            from . import mffu_view, notify
            name = notify.mask_ids(mffu_view.owner_name(aid, a.get("name"), a.get("plan"), a.get("kind")))[:40]
        except Exception:  # noqa: BLE001
            name = "Extra account"
        out.append({"id": aid, "name": name, "funded": a.get("kind") == "funded", "real": str(a.get("badge") or "") == "LIVE",
                    "unreal": _f(pos.get("unrealized_usd")), **dist})
    return out


def payout_line(acct_id: str, views=None) -> str:
    """The payout-buffer state of a funded account ("payout requestable now: $1,000 ($800 to you)" / why not yet), '' if unknown."""
    try:
        if views is None:
            from . import payout_autopilot as PA
            views = PA.gather()
        key = {"atlas": "atlas"}.get(acct_id, acct_id)
        for v in views or []:
            v = _d(v)
            if v.get("key") in (key, f"x:{acct_id}") or (acct_id.startswith("rapid") and v.get("key") == acct_id):
                if v.get("ready") and _f(v.get("amount")):
                    return f"payout requestable now: {money(v['amount'])} ({money(v.get('to_you'))} to you)"
                if _f(v.get("mffu_would_pay")):
                    return f"MFFU would pay {money(v['mffu_would_pay'])} now (your plan waits for the max)"
                why = (v.get("why") or [""])[0]
                return f"no payout yet: {why}"[:140] if why else "no payout yet"
    except Exception:  # noqa: BLE001
        pass
    return ""


def pushes(live: dict, sent: dict, now, views=None) -> list:
    """The new risk pushes (pc_guard shape: key, title, body, priority, tags, night). Marks lower levels said in `sent` (one push
    for a jump). Never raises."""
    out = []
    try:
        day = trading_day(now)
        for r in rows(live):
            left = r["left"]
            hit = [lvl for lvl in LEVELS if left <= lvl]
            if not hit:
                continue
            lvl = min(hit)                                    # the tightest level reached
            keys = {x: f"{PREFIX}{r['id']}:{day}:{int(x)}" for x in LEVELS}
            if keys[lvl] in sent:
                continue
            for x in LEVELS:
                if x > lvl:
                    sent.setdefault(keys[x], int(now))
            lim = ("the trailing max-loss floor" if r["limit"] == "floor" else "today's daily loss limit")
            other = r["day_left"] if r["limit"] == "floor" else r["floor_left"]
            body = (f"{r['name']} ({'real account' if r['real'] else 'Sim / paper'}): {money(left)} left before {lim}"
                    + (f" ({money(-r['unreal'])} of the loss is in the open trade)" if (r.get("unreal") or 0) < 0 else "")
                    + (f"; {'daily limit' if r['limit'] == 'floor' else 'floor'} {money(other)} away" if other is not None else "")
                    + ".")
            if r["funded"]:
                pl = payout_line(r["id"], views)
                if pl:
                    body += f" Funded: {pl}."
            body += " The bot keeps its own stops and sizes from the room; this alert changes nothing."
            loud = lvl <= 150
            out.append({"key": keys[lvl], "covers": [keys[x] for x in LEVELS if x > lvl], "title": f"{r['name']}: {money(left)} left ({'daily limit' if r['limit'] == 'day' else 'floor'})",
                        "body": body, "priority": "urgent" if loud else "high" if lvl <= 300 else "default",
                        "tags": "rotating_light" if loud else "warning", "night": loud})
    except Exception:  # noqa: BLE001
        return out
    return out


def main(argv=None) -> int:
    import urllib.request
    try:
        from .ops_checks import _port
        with urllib.request.urlopen(f"http://127.0.0.1:{_port()}/api/site/live.json", timeout=10) as r:
            live = json.loads(r.read().decode("utf-8"))
    except Exception as e:  # noqa: BLE001
        print(f"  [..]   the bot server's live view is not reachable ({e.__class__.__name__})")
        return 1
    for r in rows(live):
        print(f"  {r['name']:<24} {money(r['left']):>8} left ({r['limit']})" + (f"  {payout_line(r['id'])}" if r["funded"] else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
