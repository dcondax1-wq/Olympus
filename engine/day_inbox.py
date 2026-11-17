"""DAY INBOX (team X2 "connect the day", 2026-11-14): the ONE small write the phone link allows. docs/CONNECT_DAY.md.

The iPhone Shortcut "Add to my day" sends a task or a note to the PC over the private Tailscale link:

    POST https://<your-pc>.<tailnet>.ts.net/inbox/day        header  X-Olympus-Inbox: 1
         body  {"text": "Call the bank", "type": "task" | "note", "due": "today" | "tomorrow" | "YYYY-MM-DD"}   (or plain text = a task)

and this ONLY appends one line to data/inbox/<kind>.jsonl (gitignored; LE_INBOX_DIR overrides) and rewrites the small snapshot
data/day/inbox.json that the Planner reads at /site/day/inbox.json (it adds each item to your plan once). Nothing else: it never
starts, stops, arms, sizes or routes a bot, never touches a setting, never reads or sends a secret, never calls out. Shared shape
with the money inbox (team X1): POST /inbox/{kind}; a kind is one entry of KINDS (register() adds one, e.g. "money"), every kind
writes only its own file. Built in: "day" (above) and "health" (team ME1, docs/ME_HUB.md: the iPhone Shortcut "Health to PC" posts
one evening summary of Apple Health; validate_health is strict: known fields, numbers in human ranges, a date in the last 10 days)
and "board" (2026-11-17, docs/BOARD.md: an owner note on the Board both the bot and Claude read; data/inbox/board.jsonl).

Safety: the read-only guard of engine/live_site.py lets a proxied POST through ONLY for /inbox/<a registered kind>, and only once
install() ran; a Tailscale Funnel (internet) request is still refused; the route takes a post only from the PC itself or through the
Tailscale link (live_site.private_why: never another device on the home WiFi, team Q2 2026-11-14); a body over 2 KB is refused from
its Content-Length before it is read, and never read past 2 KB; the custom header makes a browser on another site send a
CORS pre-flight first, which is never answered, so a web page cannot post here behind your back; 2 KB a request, 200 characters of
text, 30 requests per 10 minutes, 5,000 lines per file. Wiring (the lead): server.py calls day_inbox.install(app) right after
live_site.install(app, ...). Test: python -X utf8 -m tests.test_calendar_sync --only=j
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import threading
import time

from fastapi import Request
from fastapi.responses import JSONResponse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INBOX_DIR = os.path.join(ROOT, "data", "inbox")
DAY_DIR = os.path.join(ROOT, "data", "day")
HEADER = "x-olympus-inbox"
MAX_BODY = 2048
MAX_TEXT = 200
MAX_LINES = 5000
RATE_N, RATE_S = 30, 600
SNAPSHOT_N, SNAPSHOT_DAYS = 50, 30
PATH_RX = re.compile(r"^/inbox/([a-z][a-z0-9_]{1,15})$")
DAY_RX = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_LOCK = threading.Lock()
_HITS: list = []
_S = {"installed": False}


def _dirs(env=None):
    env = os.environ if env is None else env
    return env.get("LE_INBOX_DIR") or INBOX_DIR, env.get("LE_DAY_DIR") or DAY_DIR


def _clean(s, n=MAX_TEXT) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[\x00-\x1f\x7f<>]", " ", str(s or ""))).strip()[:n]


def _ny_day(t: float, plus: int = 0) -> str:
    try:
        from zoneinfo import ZoneInfo
        d = dt.datetime.fromtimestamp(t, tz=ZoneInfo("America/New_York")).date()
    except Exception:  # noqa: BLE001
        d = dt.datetime.utcfromtimestamp(t - 5 * 3600).date()
    return (d + dt.timedelta(days=plus)).isoformat()


def validate_day(body, now_s: float) -> tuple[dict | None, str]:
    """the "day" kind: a task or a note for the Planner. -> (record, '') or (None, why)"""
    if isinstance(body, str):
        body = {"text": body}
    if not isinstance(body, dict):
        return None, "send {\"text\": \"...\"} or plain text"
    text = _clean(body.get("text") or body.get("task") or body.get("note"))
    if not text:
        return None, "nothing to add: the text is empty"
    typ = str(body.get("type") or ("note" if body.get("note") and not body.get("text") else "task")).lower()
    if typ not in ("task", "note"):
        typ = "task"
    due_raw = str(body.get("due") or "").strip().lower()
    due = _ny_day(now_s) if due_raw in ("", "today") else _ny_day(now_s, 1) if due_raw == "tomorrow" else due_raw if DAY_RX.match(due_raw) else ""
    return {"type": typ, "text": text, "due": due}, ""


# ------------------------------------------------------------------------------------------------ the "health" kind (team ME1, 2026-11-14)
# The iPhone Shortcut "Health to PC" (docs/ME_HUB.md, no app to install) posts one evening summary of Apple Health:
#   POST /inbox/health   header X-Olympus-Inbox: 1
#   {"date": "2026-11-14", "steps": 8432, "active_kcal": 512, "exercise_min": 34, "stand_h": 11, "rhr": 58, "hrv_ms": 46,
#    "sleep_h": 7.2, "weight_lb": 182.4, "workouts": "Running 32 min; Walking 45 min"}
# STRICT: a JSON object only; known fields only (any letter case, a few plain aliases); every value a number in a human range, or empty
# (= not sent); the date within the last 10 days (empty = today, New York); at least one number. tools/me_health.py turns the lines of
# data/inbox/health.jsonl into the Me hub's me/health.json. Nothing here reads, sends or changes anything else.
HEALTH_FIELDS = {   # field: (lowest, highest, decimals kept)
    "steps": (0, 150000, 0), "active_kcal": (0, 15000, 0), "exercise_min": (0, 1440, 0), "stand_h": (0, 24, 0),
    "rhr": (25, 220, 1), "hrv_ms": (1, 400, 1), "sleep_h": (0, 24, 2), "sleep_deep_h": (0, 24, 2), "sleep_rem_h": (0, 24, 2),
    "weight_lb": (40, 1000, 1),
}
HEALTH_ALIASES = {"active_energy": "active_kcal", "move": "active_kcal", "move_kcal": "active_kcal", "exercise": "exercise_min",
                  "stand": "stand_h", "stand_hours": "stand_h", "resting_hr": "rhr", "resting_heart_rate": "rhr", "hrv": "hrv_ms",
                  "sleep": "sleep_h", "weight": "weight_lb"}
HEALTH_CONVERT = {"sleep_min": ("sleep_h", 1 / 60.0), "sleep_s": ("sleep_h", 1 / 3600.0), "weight_kg": ("weight_lb", 2.20462), "active_kj": ("active_kcal", 0.239006)}
# a unit mix-up is refused, not stored: a night in seconds or minutes is either 0 (no sleep sent) or at least 10 minutes long
HEALTH_UNIT_FLOOR = {"sleep_s": 600, "sleep_min": 10}
WORKOUT_KEYS = {"type": None, "min": (0, 1440), "kcal": (0, 5000), "km": (0, 500), "mi": (0, 320)}
NUM_RX = re.compile(r"^-?(\d{1,3}(,\d{3})+|\d+)(\.\d+)?$")
DECIMAL_COMMA_RX = re.compile(r"^\d+,\d{1,2}$")
CLOCK_RX = re.compile(r"^(\d{1,2}):([0-5]\d)(:([0-5]\d))?$")


def _hnum(key: str, v):
    """-> (number or None when empty, why). A number, or a string the Shortcuts app made of one: "8432", "8,432", "7.25", "7,25",
    and for the sleep fields a clock-style duration "7:12" / "7:12:30" (hours). Anything else is refused, never guessed."""
    if v is None:
        return None, ""
    if isinstance(v, bool):
        return None, f"{key}: true / false is not a number"
    if isinstance(v, (int, float)):
        x = float(v)
    elif isinstance(v, str):
        s = v.strip()
        if s == "":
            return None, ""
        m = CLOCK_RX.match(s)
        if m and key.startswith("sleep"):
            x = int(m.group(1)) + int(m.group(2)) / 60.0 + int(m.group(4) or 0) / 3600.0
        elif DECIMAL_COMMA_RX.match(s):
            x = float(s.replace(",", "."))
        elif NUM_RX.match(s):
            x = float(s.replace(",", ""))
        else:
            return None, f"{key}: '{_clean(s, 24)}' is not a number"
    else:
        return None, f"{key}: send a number"
    if x != x or x in (float("inf"), float("-inf")):
        return None, f"{key}: not a number"
    return x, ""


def _ranged(key: str, x: float, lo: float, hi: float, dec: int):
    if x < lo or x > hi:
        return None, f"{key}: {x:g} is outside {lo:g}-{hi:g}"
    return (int(round(x)) if dec == 0 else round(x, dec)), ""


def _workouts(v):
    """the workouts: a short text ("Running 32 min; Walking 45 min") or a list of at most 12 {type, min, kcal, km | mi}"""
    if isinstance(v, str):
        t = _clean(v, 300)
        return ({"workouts_text": t} if t else {}), ""
    if not isinstance(v, list):
        return None, "workouts: a text or a list"
    if len(v) > 12:
        return None, "workouts: 12 at most"
    out = []
    for w in v:
        if not isinstance(w, dict):
            return None, "workouts: each one is {\"type\", \"min\", \"kcal\", \"km\"}"
        row = {}
        for k0, val in w.items():
            k = str(k0).strip().lower()
            if k not in WORKOUT_KEYS:
                return None, f"workouts: unknown field '{_clean(k, 16)}'"
            if k == "type":
                row["type"] = re.sub(r"[^A-Za-z /&+-]", "", _clean(val, 40)).strip() or "Workout"
                continue
            x, why = _hnum("workouts " + k, val)
            if why:
                return None, why
            if x is None:
                continue
            lo, hi = WORKOUT_KEYS[k]
            x, why = _ranged("workouts " + k, x, lo, hi, 1)
            if why:
                return None, why
            if k == "mi":
                row["km"] = round(x * 1.609344, 1)
            else:
                row[k] = x
        out.append({"type": row.pop("type", "Workout"), **row})
    return ({"workouts": out} if out else {}), ""


def validate_health(body, now_s: float) -> tuple[dict | None, str]:
    """the "health" kind: one day of Apple Health numbers from the Shortcut. -> (record, '') or (None, why)"""
    if not isinstance(body, dict):
        return None, "send a JSON object: {\"date\": \"2026-11-14\", \"steps\": 8432, ...} (docs/ME_HUB.md)"
    rec, nums = {}, 0
    for k0, v in body.items():
        k = str(k0).strip().lower().replace(" ", "_").replace("-", "_")
        k = HEALTH_ALIASES.get(k, k)
        if k == "date":
            s = str(v or "").strip()[:10]
            if s == "":
                continue
            if not DAY_RX.match(s):
                return None, "date: use yyyy-MM-dd (Format Date, Custom) or leave it out for today"
            if not (_ny_day(now_s, -10) <= s <= _ny_day(now_s, 1)):
                return None, f"date: {s} is not in the last 10 days"
            rec["date"] = s
            continue
        if k == "workouts":
            w, why = _workouts(v)
            if w is None:
                return None, why
            rec.update(w)
            continue
        if k in HEALTH_CONVERT:
            to, f = HEALTH_CONVERT[k]
            x, why = _hnum(k, v)
            if why:
                return None, why
            if x is None:
                continue
            if 0 < x < HEALTH_UNIT_FLOOR.get(k, 0):
                return None, f"{k}: {x:g} is too short for a night (send {'seconds' if k == 'sleep_s' else 'minutes'}, or sleep_h in hours)"
            k, v = to, x * f
        if k not in HEALTH_FIELDS:
            return None, f"unknown field '{_clean(k, 24)}': the fields are date, " + ", ".join(sorted(HEALTH_FIELDS)) + ", workouts"
        x, why = _hnum(k, v)
        if why:
            return None, why
        if x is None:
            continue
        lo, hi, dec = HEALTH_FIELDS[k]
        x, why = _ranged(k, x, lo, hi, dec)
        if why:
            return None, why
        if k in rec:
            return None, f"{k} sent twice (under two names): send it once"
        rec[k] = x
        nums += 1
    if not nums and not rec.get("workouts") and not rec.get("workouts_text"):
        return None, "nothing to save: send at least one number (steps, active_kcal, exercise_min, sleep_h, rhr, hrv_ms ...)"
    rec.setdefault("date", _ny_day(now_s))
    return rec, ""


def say_health(rec: dict) -> str:
    """the Shortcut's notification: what the PC kept"""
    bits = []
    if rec.get("steps") is not None:
        bits.append(f"{rec['steps']:,} steps")
    if rec.get("sleep_h") is not None:
        bits.append(f"slept {rec['sleep_h']:.1f} h")
    if rec.get("exercise_min") is not None:
        bits.append(f"{rec['exercise_min']} min exercise")
    if rec.get("rhr") is not None:
        bits.append(f"resting HR {rec['rhr']:g}")
    n = len([k for k in rec if k in HEALTH_FIELDS])
    head = ", ".join(bits[:3]) if bits else f"{n} numbers"
    return f"Saved your health for {rec.get('date')}: {head}. The Me hub updates within 15 minutes."


def validate_board(body, now_s: float) -> tuple[dict | None, str]:
    """the "board" kind (engine/board_events.py, 2026-11-17): an owner note for the bot AND Claude ("ATLAS passed", "Zlarior
    49,192.78", "new funded name ends 1234"). A typed balance updates the account's row on the board, marked owner, typed, date."""
    from engine import board_events
    return board_events.validate_owner(body, now_s)


def say_board(rec: dict) -> str:
    from engine import board_events
    return board_events.say_owner(rec)


KINDS = {"day": validate_day, "health": validate_health, "board": validate_board}
SAYS = {"health": say_health, "board": say_board}


def register(kind: str, validate, say=None) -> None:
    """another inbox (team X1's "money"): validate(body, now_s) -> (record, why). It gets its own file data/inbox/<kind>.jsonl.
    say(record) -> the reply line (optional)."""
    if not PATH_RX.match("/inbox/" + str(kind)):
        raise ValueError("a kind is 2-16 lowercase letters / digits")
    KINDS[kind] = validate
    if say is not None:
        SAYS[kind] = say


def allowed(method: str, path: str) -> bool:
    """engine/live_site.guard asks this: the only POST the phone link may make (once install() ran)"""
    m = PATH_RX.match(path or "")
    return bool(_S["installed"] and (method or "").upper() == "POST" and m and m.group(1) in KINDS)


def _rate_ok(now_s: float) -> bool:
    with _LOCK:
        while _HITS and now_s - _HITS[0] > RATE_S:
            _HITS.pop(0)
        if len(_HITS) >= RATE_N:
            return False
        _HITS.append(now_s)
        return True


def _count_lines(p: str) -> int:
    try:
        with open(p, "rb") as fh:
            return sum(1 for _ in fh)
    except OSError:
        return 0


def snapshot(env=None, now_s: float | None = None) -> dict:
    """data/day/inbox.json: the last 50 "day" items of the last 30 days (what the Planner adds, once each)"""
    now_s = time.time() if now_s is None else now_s
    ib, dd = _dirs(env)
    items = []
    try:
        with open(os.path.join(ib, "day.jsonl"), encoding="utf-8") as fh:
            for line in fh:
                try:
                    j = json.loads(line)
                except ValueError:
                    continue
                if isinstance(j, dict) and j.get("id") and now_s - float(j.get("t") or 0) <= SNAPSHOT_DAYS * 86400:
                    items.append({k: j.get(k) for k in ("id", "type", "text", "due", "t")})
    except OSError:
        pass
    snap = {"v": 1, "kind": "olympus-inbox", "t": int(now_s), "items": items[-SNAPSHOT_N:],
            "about": "What you sent from the iPhone (Add to my day). Private: only the PC's own link serves it."}
    os.makedirs(dd, exist_ok=True)
    p = os.path.join(dd, "inbox.json")
    with open(p + ".tmp", "w", encoding="utf-8") as fh:
        json.dump(snap, fh, ensure_ascii=False)
    from .fsutil import replace as _rep         # retried: a Windows / OneDrive lock (tests.test_selfheal)
    _rep(p + ".tmp", p)
    try:
        os.chmod(p, 0o600)
    except OSError:
        pass
    return snap


def accept(kind: str, raw: bytes, content_type: str = "", headers=None, now_s: float | None = None, env=None,
           client: str | None = None) -> tuple[int, dict]:
    """The whole endpoint, pure enough to test: -> (HTTP status, JSON reply). Appends one line, nothing else. client: the
    request's address (the route always passes it): only the PC itself or the Tailscale link may post (live_site.private_why)."""
    now_s = time.time() if now_s is None else now_s
    h = {str(k).lower(): v for k, v in (headers or {}).items()}
    if kind not in KINDS:
        return 404, {"ok": False, "error": "no such inbox"}
    if client is not None:
        try:
            from engine import live_site
            why = live_site.private_why(client, h)
        except Exception:  # noqa: BLE001
            why = "private: the check could not run"
        if why:
            return 403, {"ok": False, "error": why}
    if str(h.get(HEADER, "")).strip() != "1":
        return 403, {"ok": False, "error": "missing the X-Olympus-Inbox: 1 header (docs/CONNECT_DAY.md has the Shortcut)"}
    if h.get("tailscale-funnel-request"):
        return 403, {"ok": False, "error": "private: not from the internet"}
    if raw is None or len(raw) > MAX_BODY:
        return 413, {"ok": False, "error": "too long: 2 KB at most"}
    text = raw.decode("utf-8", "replace").strip()
    body = text
    if "json" in (content_type or "").lower() or text.startswith("{"):
        try:
            body = json.loads(text) if text else {}
        except (ValueError, RecursionError):
            return 400, {"ok": False, "error": "that is not JSON"}
    rec, why = KINDS[kind](body, now_s)
    if rec is None:
        return 400, {"ok": False, "error": why}
    if not _rate_ok(now_s):
        return 429, {"ok": False, "error": "too many in a row: wait a few minutes"}
    ib, _dd = _dirs(env)
    os.makedirs(ib, exist_ok=True)
    p = os.path.join(ib, f"{kind}.jsonl")
    if _count_lines(p) >= MAX_LINES:
        return 507, {"ok": False, "error": "the inbox file is full (5,000 lines): clear it on the PC"}
    rid = hashlib.sha1(f"{kind}|{now_s}|{rec}".encode("utf-8")).hexdigest()[:12]
    line = {"id": rid, "kind": kind, "t": int(now_s), **rec}
    with _LOCK:
        with open(p, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(line, ensure_ascii=False) + "\n")
    try:
        os.chmod(p, 0o600)
    except OSError:
        pass
    if kind == "day":
        try:
            snapshot(env, now_s)
        except OSError:
            pass
    what = rec.get("text") or ""
    try:
        said = SAYS[kind](rec) if kind in SAYS else (f"Added to your day: {what}" if kind == "day" else f"Saved in your {kind} inbox.")
    except Exception:  # noqa: BLE001
        said = f"Saved in your {kind} inbox."
    return 200, {"ok": True, "id": rid, "kind": kind, "said": said[:240]}


def install(app) -> dict:
    """Add POST /inbox/{kind} and tell live_site's read-only guard this one path may be posted to. Call it after live_site.install."""

    @app.post("/inbox/{kind}")
    async def r_inbox(kind: str, request: Request):
        client = getattr(getattr(request, "client", None), "host", None) or ""
        try:
            n = int(request.headers.get("content-length") or 0)
        except ValueError:
            n = 0
        if n > MAX_BODY:                                     # refused before a byte is read (a 1 GB post costs nothing)
            raw = b"x" * (MAX_BODY + 1)
        else:
            raw = b""
            async for chunk in request.stream():             # never more than 2 KB in memory, whatever the client says
                raw += chunk
                if len(raw) > MAX_BODY:
                    break
        status, out = accept(kind, raw[: MAX_BODY + 1], request.headers.get("content-type", ""), dict(request.headers), client=client)
        return JSONResponse(out, status_code=status, headers={"Cache-Control": "no-store"})

    _S["installed"] = True
    try:
        from engine import live_site
        live_site.allow_post(allowed)
    except Exception:  # noqa: BLE001
        pass
    return {"kinds": sorted(KINDS)}
