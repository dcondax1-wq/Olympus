"""DAY INBOX (team X2 "connect the day", 2026-11-14): the ONE small write the phone link allows. docs/CONNECT_DAY.md.

The iPhone Shortcut "Add to my day" sends a task or a note to the PC over the private Tailscale link:

    POST https://<your-pc>.<tailnet>.ts.net/inbox/day        header  X-Olympus-Inbox: 1
         body  {"text": "Call the bank", "type": "task" | "note", "due": "today" | "tomorrow" | "YYYY-MM-DD"}   (or plain text = a task)

and this ONLY appends one line to data/inbox/<kind>.jsonl (gitignored; LE_INBOX_DIR overrides) and rewrites the small snapshot
data/day/inbox.json that the Planner reads at /site/day/inbox.json (it adds each item to your plan once). Nothing else: it never
starts, stops, arms, sizes or routes a bot, never touches a setting, never reads or sends a secret, never calls out. Shared shape
with the money inbox (team X1): POST /inbox/{kind}; a kind is one entry of KINDS (register() adds one, e.g. "money"), every kind
writes only its own file.

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


KINDS = {"day": validate_day}


def register(kind: str, validate) -> None:
    """another inbox (team X1's "money"): validate(body, now_s) -> (record, why). It gets its own file data/inbox/<kind>.jsonl."""
    if not PATH_RX.match("/inbox/" + str(kind)):
        raise ValueError("a kind is 2-16 lowercase letters / digits")
    KINDS[kind] = validate


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
    os.replace(p + ".tmp", p)
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
    return 200, {"ok": True, "id": rid, "kind": kind, "said": (f"Added to your day: {what}" if kind == "day" else f"Saved in your {kind} inbox.")[:240]}


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
