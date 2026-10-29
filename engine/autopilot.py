"""Autopilot score (2026-10-29, owner: "automatic in a few weeks"; docs/AUTOPILOT.md): how many times the owner had to do
something by hand this week (Monday-Sunday, New York time). Goal: 0.

Counted, per week:
  taps      every write on the PC's Start page (engine/start_api._do: Start trading, the live phrase, names, open NinjaTrader,
            setup, Sim test, clock sync, account add / remove / balance / funded / new Name), recorded by note_tap() in
            data/autopilot.jsonl (gitignored). The job's own call to /resume is the bot, not the owner: not counted.
  hands-on  engine/handsoff.py's events (manual trade / close / size, kill, flatten, stop, pause, settings, restart).
Score = 100 - 10 per manual step (floor 0), verdict "hands-free" at 0. compact() rides in the heartbeat's "remote" block
(engine/remote_ctl._extras, next to the hands-off score), so the cloud, live.json and the phone see it.
STEPS = the catalogue of a normal week's manual steps and their state (docs/AUTOPILOT.md is the plain-language version).
Read-only for trading; never raises.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import time
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "data", "autopilot.jsonl")
KEEP = 600                                  # lines kept in the tap log
PER_STEP = 10
DEDUP_S = 30 * 60                           # one Start page write repeated within 30 min = one step
TAPS = {"/api/next/start/go": "Start trading tapped", "/api/next/start/arm": "Live phrase typed (arm)",
        "/api/next/start/names": "Account Names set", "/api/next/start/nt": "Open NinjaTrader tapped",
        "/api/next/start/setup": "Setup run by hand", "/api/next/start/sims": "Sim test run by hand",
        "/api/next/start/clock": "PC clock synced by hand", "/api/next/start/accounts/add": "Account added",
        "/api/next/start/accounts/remove": "Account removed", "/api/next/start/accounts/anchor": "Balance typed in (MFFU numbers)",
        "/api/next/start/accounts/funded": "Eval switched to funded", "/api/next/start/newacct": "New account Name assigned"}
NOT_OWNER = ("/api/next/start/resume",)     # the Start trading job asks the server itself

# (id, the step, "auto" | "manual" | "planned", how / what is left)
STEPS = [
    ("pc_boot", "Start the bot after a reboot / Windows update", "auto",
     "Startup shortcuts open NinjaTrader and the bot server; auto-resume restarts the bot with the Run switch on"),
    ("nt_login", "Log in to NinjaTrader / connect", "auto", "NinjaTrader 'Connect on startup'; the bot waits and retries"),
    ("weekend", "Weekend disconnect, Sunday 18:00 reconnect", "auto", "entries wait while every connection is DISCONNECTED, "
                                                                     "resume by themselves once NinjaTrader reconnects"),
    ("update", "Install updates", "auto", "hourly / daily auto-update outside trading hours when flat"),
    ("dst", "Clock change (Sun 2026-11-01)", "auto", "every time is New York time; tests/test_dst.py"),
    ("holidays", "Holiday hours (Thanksgiving, Christmas, New Year)", "auto",
     "engine/cme_calendar.py: no entry 15 min before an early close, flat 5 min before, no entry on a closed day"),
    ("phantom", "Remove a fake P&L after refused orders", "auto", "startup void of refused days (50K + ATLAS)"),
    ("clock", "Sync the PC clock", "manual", "only when the clock guard turns red (one tap: Sync the clock)"),
    ("chart", "Reload the NinjaTrader chart when the bars stop", "manual", "push + Start page line with the exact click"),
    ("roll", "December roll: chart to MNQ 03-27", "manual", "once a quarter; reminders 7 days / 1 day before (ROLL_DEC_2026.md)"),
    ("anchor", "Type the MFFU balance in", "planned", "automatic from NinjaTrader's accounts.csv once LE_BarFeed's account "
                                                       "writer is compiled on the PC (engine/broker_balance.py)"),
    ("new_account", "New MFFU account after a pass / fail", "manual", "detected + pushed; one tap 'Use for ...' + the live phrase"),
    ("phrase", "Type I ACCEPT LIVE RISK", "manual", "only for a new account Name (MFFU rule: the owner arms live trading)"),
]


def _week_start(t) -> dt.datetime:
    e = dt.datetime.fromtimestamp(int(t), ET)
    d = e.date() - dt.timedelta(days=e.weekday())
    return dt.datetime(d.year, d.month, d.day, tzinfo=ET)


def note_tap(path_url: str, now=None, path: str = PATH) -> dict | None:
    """A Start page write by the owner. Never raises."""
    try:
        label = TAPS.get(str(path_url or "").rstrip("/"))
        if not label:
            return None
        ev = {"t": int(time.time() if now is None else now), "kind": "tap", "what": label, "url": str(path_url)[:80]}
        os.makedirs(os.path.dirname(path), exist_ok=True)
        lines = []
        if os.path.exists(path):
            with open(path, encoding="utf-8") as fh:
                lines = fh.read().splitlines()[-(KEEP - 1):]
        lines.append(json.dumps(ev))
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
        from .fsutil import replace as _fs_replace
        _fs_replace(tmp, path)
        return ev
    except Exception:
        return None


def _taps(path: str) -> list:
    try:
        with open(path, encoding="utf-8") as fh:
            return [json.loads(x) for x in fh if x.strip()]
    except Exception:
        return []


def week(now=None, path: str = PATH, handsoff_path: str | None = None) -> dict:
    """This week's manual steps: {"week", "manual", "score", "verdict", "items": [{"when", "what", "src"}]}."""
    now = int(time.time() if now is None else now)
    w0 = _week_start(now)
    a, z = int(w0.timestamp()), int((w0 + dt.timedelta(days=7)).timestamp())
    items = []
    for ev in _taps(path):
        if a <= int(ev.get("t") or 0) < z:
            items.append({"t": int(ev["t"]), "what": ev.get("what"), "src": "Start page"})
    try:
        from . import handsoff
        for ev in handsoff.events(handsoff_path or handsoff.PATH):
            t = int(ev.get("t") or 0)
            if a <= t < z and handsoff.points(ev.get("kind"), t) > 0:
                items.append({"t": t, "what": handsoff.LABEL.get(ev.get("kind"), ev.get("kind")), "src": "hands-on"})
    except Exception:
        pass
    items.sort(key=lambda x: x["t"])
    # the same Start page write again within 30 min is one step (the page's / the Run switch's own retries of a stop,
    # two open tabs): the owner pressed it once
    out, last = [], {}
    for x in items:
        if x["src"] == "Start page" and x["t"] - last.get(x["what"], -10 ** 9) < DEDUP_S:
            last[x["what"]] = x["t"]
            continue
        last[x["what"]] = x["t"]
        out.append(x)
    items = out
    n = len(items)
    for x in items:
        x["when"] = dt.datetime.fromtimestamp(x["t"], ET).strftime("%a %H:%M")
    return {"week": w0.date().isoformat(), "manual": n, "score": max(0, 100 - PER_STEP * n),
            "verdict": "hands-free" if n == 0 else f"{n} manual step{'s' if n != 1 else ''}",
            "auto": sum(1 for s in STEPS if s[2] == "auto"), "catalogue": len(STEPS), "items": items}


def compact(folder: str | None = None, now=None) -> dict:
    """The heartbeat block: score, manual steps, the last 5. Never raises."""
    try:
        p = os.path.join(folder, "autopilot.jsonl") if folder else PATH
        hp = os.path.join(folder, "handsoff.jsonl") if folder else None
        w = week(now, p, hp)
        return {"week": w["week"], "score": w["score"], "manual": w["manual"], "verdict": w["verdict"],
                "auto_steps": w["auto"], "steps": w["catalogue"],
                "last": [{k: x[k] for k in ("when", "what", "src")} for x in w["items"][-5:]]}
    except Exception as e:
        return {"error": e.__class__.__name__}
