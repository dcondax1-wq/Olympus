"""MFFU 7-DAY CLOCK per account (day-nqops 2026-11-21, lead: "the 7-day MFFU clocks: Zlarior 50K hard day Mon 11-23").

MFFU closes an Evaluation / Sim Funded account with no EXECUTED trade in 7 consecutive calendar days (Terms section 7; the full
rule and how days are counted: engine/keepalive.py). One small, read-only block a row per account, the same numbers everywhere:

  {"t": now, "a": [{"id", "nm", "lf" (last fill day), "base" ("fill" | "start": the day the count runs from), "dl" (the cautious
   deadline, base + 6), "hard" (MFFU's literal last day, base + 7), "left" (calendar days from today to hard), "act" (the session
   the keep-alive would use: engine/keepalive.plan act_day), "on" (keep-alive switch: True / False / None unknown),
   "lvl" ("ok" | "warn" | "bad")}]}

Sources (no new work for the bot): the PC post's "mf" block (engine/mffu_view.compact: per account its start day "sd" and last
traded day "lt") and the heartbeat's "keepalive" block (engine/keepalive.hb_block: a keep-alive / hand-trade / kept fill day per
keep-alive key, the "on" switches, the lane map). The newest of the two wins. In doubt it counts FEWER days (an account with no
fill counts from the day before its start, as engine/keepalive does).

Used by engine/preflight.py (the Sunday 17:30 / daily 01:30 ET self-check), tools/pc_report.py (ext block "k7" for the NQ page's
clock card and Jarvis) and tools/web_public/nq/clock7.js (the same rules in the browser when an older post has no "k7").
Never places, changes or arms anything. Never raises.
"""
from __future__ import annotations

import datetime as _dt
import time

LIMIT_DAYS = 7
WARN_LEFT = 3                 # <= 3 calendar days to MFFU's last day: amber
BAD_LEFT = 1                  # <= 1 day (or past): red
LANE_ID = {"lit": "mffu50k_eval", "atlas": "atlas", "rapid": "rapid"}   # keep-alive key -> the PC account id (mf / accounts)


def _d(x) -> dict:
    return x if isinstance(x, dict) else {}


def _l(x) -> list:
    return x if isinstance(x, list) else []


def _day(x) -> str | None:
    try:
        s = str(x or "")[:10]
        _dt.date.fromisoformat(s)
        return s
    except Exception:
        return None


def trading_day(t) -> str:
    """CME trading day: 18:00 ET starts the next day's session (engine/keepalive.trading_day)."""
    try:
        from .keepalive import trading_day as td
        return td(t)
    except Exception:
        return (_dt.datetime.utcfromtimestamp(int(t)) + _dt.timedelta(hours=1)).date().isoformat()


def ka_id(key: str) -> str:
    """keep-alive key ("lit", "atlas", "rapid", "x:<id>") -> the PC account id."""
    k = str(key or "")
    return LANE_ID.get(k) or (k[2:] if k.startswith("x:") else k)


def sessions_left(today: _dt.date, hard: _dt.date) -> int:
    """Weekdays (CME sessions, by their trading day) from today to MFFU's last day, both counted. A weekend = no session."""
    n, d = 0, today
    while d <= hard and n < 30:
        n += d.weekday() < 5
        d += _dt.timedelta(days=1)
    return n


def row(aid: str, name: str, last_fill, start, now, on=None) -> dict | None:
    """One account's clock. last_fill / start = ISO days (either may be None). None when neither is known."""
    lf, sd = _day(last_fill), _day(start)
    if lf:
        base, kind = _dt.date.fromisoformat(lf), "fill"
    elif sd:
        base, kind = _dt.date.fromisoformat(sd) - _dt.timedelta(days=1), "start"   # the start day is day 1
    else:
        return None
    today = _dt.date.fromisoformat(trading_day(now))
    hard = base + _dt.timedelta(days=LIMIT_DAYS)
    dl = base + _dt.timedelta(days=LIMIT_DAYS - 1)
    left = (hard - today).days
    ses = sessions_left(today, hard)
    act = None
    try:
        from .keepalive import plan
        act = plan(base.isoformat(), now).get("act_day")
    except Exception:
        act = None
    return {"id": str(aid), "nm": str(name or aid)[:40], "lf": lf, "base": kind, "dl": dl.isoformat(), "hard": hard.isoformat(),
            "left": left, "ses": ses, "act": act, "on": on,
            "lvl": "bad" if left <= BAD_LEFT or ses <= 1 else "warn" if left <= WARN_LEFT or ses <= 2 else "ok"}


def build(mf: dict | None, ka: dict | None = None, now=None, skip=("blitz",)) -> dict | None:
    """The "k7" block from the post's mf block + the heartbeat's keepalive block. None when no account is known."""
    try:
        now = int(now or time.time())
        k = _d(ka)
        ka_last = {ka_id(key): _day(v) for key, v in _d(k.get("last")).items() if _day(v)}
        on_map = {ka_id(key): bool(v) for key, v in _d(k.get("on")).items()}
        rows, seen = [], set()
        for a in _l(_d(mf).get("a")):
            if not isinstance(a, dict) or not a.get("id") or str(a["id"]) in skip:
                continue
            aid = str(a["id"])
            fills = [d for d in (_day(a.get("lt")), ka_last.get(aid)) if d]
            on = on_map.get(aid, False) if k else None        # the block lists only the switches that are ON
            r = row(aid, a.get("nm") or aid, max(fills) if fills else None, a.get("sd"), now, on)
            if r:
                rows.append(r)
                seen.add(aid)
        for aid, d in ka_last.items():                    # a keep-alive account the mf block does not list (yet)
            if aid not in seen and aid not in skip:
                r = row(aid, aid, d, None, now, on_map.get(aid, False if k else None))
                if r:
                    rows.append(r)
        if not rows:
            return None
        rows.sort(key=lambda r: (r["left"], r["id"]))
        return {"t": now, "a": rows}
    except Exception:  # noqa: BLE001
        return None


def from_post(post: dict | None, now=None) -> dict | None:
    """The block from a whole PC post / live.json (its "k7" when the PC sent one, else built from "mf" + pc.keepalive)."""
    p = _d(post)
    if isinstance(p.get("k7"), dict) and _l(p["k7"].get("a")):
        return p["k7"]
    return build(p.get("mf"), _d(p.get("pc")).get("keepalive") or p.get("keepalive"), now)


def line(r: dict, today: str | None = None) -> str:
    """'Zlarior 50K: last fill Mon 11-16, MFFU last day Mon 11-23 (2 days), keep-alive OFF'."""
    def wd(s):
        try:
            d = _dt.date.fromisoformat(s)
            return f"{d:%a} {d.month}-{d.day:02d}"
        except Exception:
            return str(s)
    last = f"last fill {wd(r['lf'])}" if r.get("lf") else "no fill yet"
    left = r.get("left")
    when = "TODAY" if left == 0 else ("PASSED" if left is not None and left < 0 else f"{left} day{'s' if left != 1 else ''}")
    ka = {True: "keep-alive ON", False: "keep-alive OFF"}.get(r.get("on"), "keep-alive unknown")
    return f"{r.get('nm')}: {last}, MFFU last day {wd(r['hard'])} ({when}), {ka}"
