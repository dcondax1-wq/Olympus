"""Weekly hands-off score (competitor-features.md #10, Edgewonk Tiltmeter idea): for a bot trader, discipline = let it run.

Every week (Monday-Sunday, New York time) starts at 100. Points come off for each time a person stepped in:

  manual_trade   25  reconcile saw a position on the account the bot did not open (engine/guards.reconcile_tick)
  manual_close   20  the bot's position was closed on the account, not by the bot (reconcile: ledger open, broker flat)
  manual_size    15  the account holds a different size than the bot routed (reconcile: qty mismatch)
  kill           15  HOLD TO KILL (dashboard or phone); 5 outside trading hours
  flatten        15  flatten now (phone remote)
  stop           10  the bot stopped by hand (dashboard Stop, Bot Control STOP, phone stop); 2 outside trading hours
  pause           5  new entries paused (phone / PC 'pause until')
  settings       15  live_model.json / live_model_lit.json changed by hand (hash differs and the file is not the committed
                     one; a change that came with an update from GitHub is listed for 0 points)
  restart        10  a server start that no auto-update or remote restart asked for, in trading hours (01:50-16:00 ET on a
                     weekday); 0 outside (Windows updates, the evening restart)
  no_checkin      5  a bot trade while nobody was checked in (only once the presence check-in is in use: engine/presence.py)
Trading hours = weekdays 01:50-16:00 ET (the auto-update blackout; LIT trades 02:00-15:55).

What it cost: where the execution audit (engine/fill_audit.py, logs/exec_audit/report.json) has a row for that day, the
note says it in $: a closed-early trade = real P&L - the backtest at the same size; a stop / pause / kill / restart before a
backtest trade the bot did not take = that trade's $ (missed); a manual trade = not the strategy's P&L.

Events: data/handsoff.jsonl (gitignored), written by record() from the server's kill / stop routes, the remote control,
the reconcile guard, the settings check (tick, once per poll from engine/guards.tick, real clock only) and the server start
(note_server_start). Read-only for trading: nothing here blocks, sizes or routes anything.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import subprocess
import time
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, "data", "handsoff.jsonl")
AUDIT_REPORT = os.path.join(ROOT, "logs", "exec_audit", "report.json")
SETTINGS_FILES = ("live_model.json", "live_model_lit.json")
POINTS = {"manual_trade": 25, "manual_close": 20, "manual_size": 15, "kill": 15, "flatten": 15, "stop": 10, "pause": 5,
          "settings": 15, "settings_update": 0, "restart": 10, "no_checkin": 5}
OUT_OF_HOURS = {"kill": 5, "stop": 2, "restart": 0}
LABEL = {"manual_trade": "Manual trade on the account", "manual_close": "Position closed by hand",
         "manual_size": "Size changed by hand", "kill": "Kill switch", "flatten": "Flatten now", "stop": "Bot stopped by hand",
         "pause": "Entries paused", "settings": "Settings changed by hand", "settings_update": "Settings updated from GitHub",
         "restart": "Server restarted by hand (or crashed)", "no_checkin": "Trade without a check-in"}
SESSION = (1 * 60 + 50, 16 * 60)


def _et(t) -> dt.datetime:
    return dt.datetime.fromtimestamp(int(t), ET)


def trading_day(t) -> str:
    return (_et(t) + dt.timedelta(hours=6)).strftime("%Y-%m-%d")


def in_hours(t) -> bool:
    e = _et(t)
    return e.weekday() < 5 and SESSION[0] <= e.hour * 60 + e.minute < SESSION[1]


def path_for(bot=None) -> str:
    """data/handsoff.jsonl beside data/live_state.json; another state file (harnesses) gets <name>_handsoff.jsonl."""
    sp = getattr(bot, "state_path", None) if bot is not None else None
    if not sp:
        return PATH
    d, n = os.path.split(sp)
    return os.path.join(d, "handsoff.jsonl" if n == "live_state.json" else os.path.splitext(n)[0] + "_handsoff.jsonl")


def points(kind: str, t) -> int:
    if kind in OUT_OF_HOURS and not in_hours(t):
        return OUT_OF_HOURS[kind]
    return int(POINTS.get(kind, 0))


# ---------------------------------------------------------------------------------------------- recording
def record(kind: str, src: str = "pc", detail: str = "", now=None, path: str = PATH, **extra) -> dict | None:
    """Append one event. Never raises (returns None on failure)."""
    try:
        t = int(time.time() if now is None else now)
        row = {"t": t, "kind": str(kind), "src": str(src)[:16], "detail": str(detail)[:200], "in_hours": in_hours(t), **extra}
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")
        return row
    except Exception:
        return None


def events(path: str = PATH) -> list:
    out = []
    try:
        with open(path, encoding="utf-8") as fh:
            for ln in fh:
                try:
                    r = json.loads(ln)
                except Exception:
                    continue
                if isinstance(r, dict) and isinstance(r.get("t"), (int, float)) and r.get("kind") in POINTS:
                    out.append(r)
    except FileNotFoundError:
        pass
    return sorted(out, key=lambda r: r["t"])


# ---------------------------------------------------------------------------------------------- settings hash (tick)
def _state_path(path: str) -> str:
    return os.path.splitext(path)[0] + "_state.json"


def _load(p) -> dict:
    try:
        with open(p, encoding="utf-8") as fh:
            d = json.load(fh)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _save(p, d):
    try:
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(d, fh, indent=1)
        from .fsutil import replace as _fs_replace   # retried: Windows / OneDrive lock the target a moment
        _fs_replace(tmp, p)
    except Exception:
        pass


def _sha(b: bytes) -> str:
    return hashlib.sha1(b).hexdigest()[:16]


def _committed(root: str, name: str) -> bytes | None:
    try:
        r = subprocess.run(["git", "show", f"HEAD:{name}"], cwd=root, capture_output=True, timeout=20)
        return r.stdout if r.returncode == 0 else None
    except Exception:
        return None


def settings_check(path: str = PATH, root: str = ROOT, files=SETTINGS_FILES, now=None) -> list:
    """Compare each settings file's hash with the last one seen. First sight = the baseline (no event). A change whose
    content equals the committed file (git HEAD) = 'settings_update' (0 points); otherwise 'settings'. Returns new events."""
    sp = _state_path(path)
    st = _load(sp)
    seen = st.setdefault("hash", {})
    out = []
    for name in files:
        try:
            with open(os.path.join(root, name), "rb") as fh:
                b = fh.read()
        except OSError:
            continue
        h = _sha(b)
        old = seen.get(name)
        if old == h:
            continue
        seen[name] = h
        if old is None:
            continue
        com = _committed(root, name)
        kind = "settings_update" if com is not None and _sha(com) == h else "settings"
        ev = record(kind, "file", f"{name} changed ({old[:7]} -> {h[:7]})", now=now, path=path)
        if ev:
            out.append(ev)
    _save(sp, st)
    return out


def tick(bot, now=None) -> list:
    """engine/guards.tick, once per poll: the settings check, at most once a minute, on the real clock only."""
    if getattr(bot, "clock", None) is not time.time:
        return []
    t = time.time()
    if t - float(getattr(bot, "_handsoff_at", 0) or 0) < 60:
        return []
    bot._handsoff_at = t
    try:
        return settings_check(path_for(bot))
    except Exception:
        return []


def note_server_start(marker=None, path: str = PATH, done_path: str | None = None, now=None) -> dict | None:
    """server.py at start: a restart nobody asked for (no auto-update marker, no remote restart / update in the last
    10 min) is a 'restart' event (10 points in trading hours, 0 outside). Also takes the settings baseline."""
    now = int(time.time() if now is None else now)
    try:
        settings_check(path, now=now)
    except Exception:
        pass
    if marker:
        return None
    try:
        from . import remote_ctl
        last = (remote_ctl.load_done(done_path or remote_ctl.DONE_PATH).get("last") or {})
        if last.get("cmd") in ("restart", "update") and now - int(last.get("t") or 0) < 600:
            return None
    except Exception:
        pass
    return record("restart", "server", "server started without an update or remote restart asking for it", now=now, path=path)


# ---------------------------------------------------------------------------------------------- the score card
def _usd(v) -> str:
    v = float(v)
    return f"{'-' if v < 0 else '+'}${abs(v):,.0f}"


def _audit_rows(report_path: str = AUDIT_REPORT) -> list:
    d = _load(report_path)
    return [r for r in (d.get("rows") or []) if isinstance(r, dict)]


def cost_note(ev: dict, rows: list) -> tuple:
    """(note, usd or None) from the execution audit rows of the event's trading day."""
    k, t = ev["kind"], int(ev["t"])
    day = trading_day(t)
    same = [r for r in rows if r.get("day") == day]
    if k == "manual_trade":
        ex = [r for r in same if r.get("status") == "extra" and r.get("live_pnl") is not None]
        if ex:
            v = sum(float(r["live_pnl"]) for r in ex)
            return f"a trade the backtest did not take: {_usd(v)} (not the strategy's P&L)", round(v, 2)
        return "not the strategy's trade: its P&L is yours (see NinjaTrader Account Performance)", None
    if k in ("settings", "settings_update"):
        return ("rules changed by hand: the backtest numbers no longer describe the live bot (rerun tools/lit_losses.py live)"
                if k == "settings" else "came with an update from GitHub: no cost"), None
    if k == "no_checkin":
        return "MFFU wants you watching while the bot trades: tap I'm here before the session", None
    if k in ("manual_close", "flatten", "kill", "manual_size"):
        m = [r for r in same if r.get("status") == "matched" and r.get("exec_usd") is not None
             and int(r.get("entry_t") or 0) <= t]
        if m:
            v = sum(float(r["exec_usd"]) for r in m)
            return f"vs the backtest at the same size: {_usd(v)}", round(v, 2)
    if k in ("stop", "pause", "kill", "restart", "flatten"):
        ms = [r for r in same if r.get("status") == "missed" and int(r.get("entry_t") or 0) >= t]
        if ms:
            v = sum(float(r.get("missed_usd") or 0) for r in ms)
            when = ", ".join(_et(r["entry_t"]).strftime("%H:%M") for r in ms)
            return f"the backtest traded at {when} ET and the bot did not: {_usd(v)} not taken", round(-v, 2)
        if same or rows:
            return "no backtest trade was missed that day", 0.0
    return "cost unknown (no execution audit for that day yet)", None


def _week_start(t) -> dt.datetime:
    e = _et(t)
    d = (e - dt.timedelta(days=e.weekday())).date()
    return dt.datetime(d.year, d.month, d.day, tzinfo=ET)


def _no_checkin_events(since, until, presence_path: str | None, bot=None, ledger_path=None) -> list:
    try:
        from . import presence
        p = presence_path or presence.path_for(bot)
        if not presence.events(p):                   # the check-in is not in use yet: no points
            return []
        lv = presence.log_view(now=until, days=max(1, int((until - since) // 86400) + 1), path=p, bot=bot,
                               ledger_path=ledger_path)
        return [{"t": tr["entry_t"], "kind": "no_checkin", "src": "presence", "in_hours": True,
                 "detail": f"{tr['side']} {tr.get('qty') or ''} at {tr['time']} with nobody checked in"}
                for tr in lv["trades"] if not tr["present"] and since <= tr["entry_t"] < until]
    except Exception:
        return []


def week_card(week_start: dt.datetime, evs: list, rows: list, now: int, extra: list | None = None) -> dict:
    a = int(week_start.timestamp())
    b = int((week_start + dt.timedelta(days=7)).timestamp())
    items = []
    for ev in sorted([e for e in evs if a <= e["t"] < b] + list(extra or []), key=lambda e: e["t"]):
        pts = points(ev["kind"], ev["t"])
        note, usd = cost_note(ev, rows)
        items.append({"t": int(ev["t"]), "kind": ev["kind"], "label": LABEL.get(ev["kind"], ev["kind"]), "src": ev.get("src"),
                      "detail": ev.get("detail") or "", "points": pts, "note": note, "usd": usd,
                      "when": f"{_et(ev['t']):%a %H:%M} ET"})
    lost = sum(i["points"] for i in items)
    score = max(0, 100 - lost)
    usd = [i["usd"] for i in items if i["usd"] is not None]
    verdict = ("hands off: the bot ran on its own" if score == 100 else "mostly hands off" if score >= 80
               else "you stepped in a few times" if score >= 50 else "a lot of stepping in this week")
    return {"week": week_start.strftime("%Y-%m-%d"), "label": f"week of {week_start:%a %d %b}", "score": score, "lost": lost,
            "events": items, "n": len(items), "usd": round(sum(usd), 2) if usd else None, "verdict": verdict,
            "current": a <= now < b}


def view(now=None, weeks: int = 4, path: str = PATH, report_path: str = AUDIT_REPORT, presence_path: str | None = None,
         bot=None, ledger_path: str | None = None) -> dict:
    now = int(time.time() if now is None else now)
    evs = events(path)
    rows = _audit_rows(report_path)
    ws = _week_start(now)
    cards = []
    for i in range(max(1, int(weeks))):
        w = ws - dt.timedelta(days=7 * i)
        w = dt.datetime(w.year, w.month, w.day, tzinfo=ET)
        a, b = int(w.timestamp()), int((w + dt.timedelta(days=7)).timestamp())
        cards.append(week_card(w, evs, rows, now, _no_checkin_events(a, min(b, now), presence_path, bot, ledger_path)))
    return {"t": now, "weeks": cards, "points": POINTS, "out_of_hours": OUT_OF_HOURS,
            "how": "100 a week, points off each time a person stepped in; $ from the execution audit where it has the day"}


def compact(now=None, path: str = PATH, report_path: str = AUDIT_REPORT, presence_path: str | None = None) -> dict:
    """The heartbeat / live.json block (via engine/remote_ctl.hb_field): this week's score + up to 5 events."""
    c = view(now, 1, path, report_path, presence_path)["weeks"][0]
    return {"week": c["week"], "score": c["score"], "lost": c["lost"], "n": c["n"], "usd": c["usd"], "verdict": c["verdict"],
            "events": [{k: i[k] for k in ("when", "label", "points", "note")} for i in c["events"][-5:]]}
