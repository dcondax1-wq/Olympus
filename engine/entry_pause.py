"""'Pause until' for new entries (competitor-features.md #8; freqtrade /stopentry, Tradesyncer session lockout).

The owner pauses NEW entries until a time; an open trade keeps its stop / target / breakeven / exits untouched. Set from the
phone (engine/remote_ctl.py commands "pause" {"until": "HH:MM" | "tomorrow" | "YYYY-MM-DD"} and "resume_entries") or the
PC dashboard (POST /api/next/pause, engine/presence_api.py). The check sits in engine/guards.entry_problems, so a paused
entry is "NOT routed: GUARD paused by you until ..." with the usual phone push. Only ever blocks; nothing here starts,
arms or sizes anything.

  until "HH:MM"       the next time it is HH:MM in New York (today if still ahead, else tomorrow)
  until "tomorrow"    until 00:00 ET tonight: no new entry for the rest of today, trading resumes tomorrow
  until "YYYY-MM-DD"  until 00:00 ET on that day (at most 14 days ahead)
The file: data/entry_pause.json (gitignored) beside data/live_state.json ({"until", "label", "set_t", "src", "id"}); a
pause that ran out is ignored (and removed on the next check).
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import time
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NAME = "entry_pause.json"
PATH = os.path.join(ROOT, "data", NAME)
MAX_DAYS = 14


def path_for(bot=None) -> str:
    """data/entry_pause.json beside data/live_state.json; another state file (harnesses, extra accounts) gets
    <name>_pause.json beside it. PATH without a bot."""
    sp = getattr(bot, "state_path", None) if bot is not None else None
    if not sp:
        return PATH
    d, n = os.path.split(sp)
    return os.path.join(d, NAME if n == "live_state.json" else os.path.splitext(n)[0] + "_pause.json")


def _fmt(t) -> str:
    return dt.datetime.fromtimestamp(int(t), ET).strftime("%a %d %b %H:%M")


def parse_until(v, now=None) -> tuple:
    """(until_ts, label) or (None, why)."""
    now = float(time.time() if now is None else now)
    e = dt.datetime.fromtimestamp(now, ET)
    s = str(v or "").strip().lower()
    if not s:
        return None, "no 'until' (HH:MM, tomorrow or YYYY-MM-DD)"
    if s == "tomorrow":
        d = (e + dt.timedelta(days=1)).date()
        u = dt.datetime(d.year, d.month, d.day, tzinfo=ET)
        return int(u.timestamp()), f"tomorrow ({_fmt(u.timestamp())} ET)"
    m = re.fullmatch(r"(\d{1,2}):(\d{2})", s)
    if m:
        h, mi = int(m.group(1)), int(m.group(2))
        if h > 23 or mi > 59:
            return None, f"bad time {s!r}"
        u = e.replace(hour=h, minute=mi, second=0, microsecond=0)
        if u.timestamp() <= now:
            u = (e + dt.timedelta(days=1)).replace(hour=h, minute=mi, second=0, microsecond=0)
        u = dt.datetime(u.year, u.month, u.day, h, mi, tzinfo=ET)          # re-anchor (DST-safe)
        return int(u.timestamp()), f"{_fmt(u.timestamp())} ET"
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        try:
            u = dt.datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), tzinfo=ET)
        except ValueError:
            return None, f"bad date {s!r}"
        if u.timestamp() <= now:
            return None, f"{s} is not in the future"
        if u.timestamp() - now > MAX_DAYS * 86400:
            return None, f"at most {MAX_DAYS} days ahead"
        return int(u.timestamp()), f"{_fmt(u.timestamp())} ET"
    return None, f"bad 'until' {s[:20]!r} (HH:MM, tomorrow or YYYY-MM-DD)"


def load(path: str = PATH) -> dict | None:
    try:
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)
        return d if isinstance(d, dict) and isinstance(d.get("until"), (int, float)) else None
    except Exception:
        return None


def active(now=None, path: str = PATH) -> dict | None:
    now = time.time() if now is None else now
    d = load(path)
    return d if d and now < float(d["until"]) else None


def set_pause(until, now=None, path: str = PATH, src: str = "pc", cid: str | None = None) -> dict:
    """{"ok", "until", "label"} or {"ok": False, "error"}."""
    now = time.time() if now is None else now
    u, label = parse_until(until, now)
    if u is None:
        return {"ok": False, "error": label}
    rec = {"until": int(u), "label": label, "set_t": int(now), "src": str(src)[:12], "id": cid}
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(rec, fh, indent=1)
    os.replace(tmp, path)
    return {"ok": True, **rec}


def clear(path: str = PATH, now=None) -> bool:
    """True when a pause that was still running was lifted."""
    was = active(now, path=path) is not None
    try:
        os.remove(path)
    except FileNotFoundError:
        pass
    return was


def problem(bot, now) -> str | None:
    """guards.entry_problems: the reason while a pause runs, else None (an expired file is removed)."""
    p = path_for(bot)
    d = load(p)
    if not d:
        return None
    if now >= float(d["until"]):
        try:
            os.remove(p)
        except OSError:
            pass
        return None
    return f"new entries paused by you until {d.get('label') or _fmt(d['until']) + ' ET'} (resume_entries lifts it)"


def line(now=None, path: str = PATH) -> str | None:
    d = active(now, path)
    return f"entries paused until {d.get('label')}" if d else None
