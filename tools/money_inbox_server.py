#!/usr/bin/env python3
"""MONEY INBOX (2026-11-14): a tiny, SEPARATE server so an iPhone Shortcut can log a cash expense (or a balance) from the phone. It does one
thing: append one checked line to  <home>/money_inbox/cash.jsonl  (home = OLYMPUS_HOME or %USERPROFILE%\\.olympus). tools/money_import.py
reads that file with the bank exports. It never trades, never reads a file back, never runs a command and has nothing to do with the bot
server (server.py / engine/live_site.py are not touched; this is its own process on its own port).

  python tools/money_inbox_server.py                 listen on 127.0.0.1:8767 (this PC only)
  python tools/money_inbox_server.py --port 8767 --home DIR

Reaching it from the iPhone: MONEY_INBOX.bat runs  tailscale serve --bg --yes --https=8443 http://127.0.0.1:8767  so the phone (signed in to
the SAME Tailscale account) posts to  https://<your-pc>.<tailnet>.ts.net:8443/inbox . Never Funnel: a Funnel (internet) request is refused.

Routes (everything else is 404 / 405):
  POST /inbox     JSON {"kind": "expense" | "income" | "balance", "amount": 12.5, "what": "Tacos", "cat": "food", "date": "2026-11-14",
                  "name": "Checking" (balance only)}  or plain text "12.50 tacos food"  ->  {"ok": true, "saved": "Saved: $12.50 Tacos (food)"}
  GET  /health    {"ok": true, "kind": "olympus-money-inbox"}  (says nothing about your money)
Checks: a body of at most 2 KB, an amount above 0 and at most $1,000,000, short plain text (4+ digit runs masked: no card numbers), at most
30 posts a minute and 500 a day. Through Tailscale the request must carry Tailscale's signed-in user (Tailscale-User-Login); an optional
allow-list <home>/money/inbox.json {"allow": ["you@example.com"]} limits it to your own login. Nothing here is a secret or needs a key.
Team Q2 (2026-11-14): the Host must be this PC (127.0.0.1 / localhost) or your <pc>.<tailnet>.ts.net name, so a web page that renames
itself to 127.0.0.1 (DNS rebinding) cannot post; a client that stalls is dropped after 15 s.
Test: python -X utf8 -m tests.test_money_inbox
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import money_import as MI  # noqa: E402

PORT = 8767
MAX_BODY = 2048
MAX_USD = 1_000_000.0
PER_MIN, PER_DAY = 30, 500
KINDS = ("expense", "income", "balance")
PROXY = ("x-forwarded-for", "x-forwarded-host", "x-forwarded-proto", "forwarded", "tailscale-user-login", "tailscale-funnel-request")
CAT_WORDS = {c: c for c in MI.CATS} | {"groceries": "food", "eating": "food", "lunch": "food", "dinner": "food", "coffee": "food", "fuel": "gas",
                                         "uber": "transport", "car": "transport", "gym": "health", "bills": "utilities", "atm": "cash"}


def text(v, n=80) -> str:
    return MI.scrub(" ".join(str(v if v is not None else "").split()), n)


def parse_body(raw: bytes, ctype: str) -> dict | None:
    """JSON or plain text '12.50 tacos food' -> the fields, else None"""
    try:
        s = raw.decode("utf-8")
    except UnicodeDecodeError:
        return None
    s = s.strip()
    if "json" in (ctype or "") or s.startswith("{"):
        try:
            d = json.loads(s)
        except ValueError:
            return None
        return d if isinstance(d, dict) else None
    m = re.match(r"^\$?\s*(\d+(?:[.,]\d{1,2})?)\s+(.+)$", s)
    if not m:
        return None
    words = m.group(2).split()
    cat = CAT_WORDS.get(words[-1].lower()) if len(words) > 1 else None
    return {"kind": "expense", "amount": m.group(1).replace(",", "."), "what": " ".join(words[:-1] if cat else words), "cat": cat or ""}


def clean(d: dict, today: str) -> tuple[dict | None, str]:
    """-> (the line to append, '') or (None, why)"""
    kind = str(d.get("kind") or "expense").lower()
    if kind not in KINDS:
        return None, "kind must be expense, income or balance"
    amt = MI.parse_amount(d.get("amount"))
    if amt is None:
        return None, "amount is not a number"
    if kind != "balance" and not (0 < amt <= MAX_USD):
        return None, "amount must be above $0 and at most $1,000,000"
    if kind == "balance" and abs(amt) > 100 * MAX_USD:
        return None, "balance is too large"
    date = MI.parse_date(d.get("date")) if d.get("date") else today
    if not date or date > MI.add_days(today, 1) or date < MI.add_days(today, -400):
        return None, "date must be YYYY-MM-DD within the last year"
    line = {"id": uuid.uuid4().hex[:12], "t": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "kind": kind, "amount": MI.r2(amt), "date": date}
    if kind == "balance":
        name = text(d.get("name") or d.get("what"), 40)
        if not name:
            return None, "a balance needs the account's name (no number)"
        line["name"] = name
        ak = str(d.get("account_kind") or "").lower()
        if ak in MI.BAL_KINDS:
            line["account_kind"] = ak
    else:
        line["what"] = text(d.get("what") or ("Cash" if kind == "expense" else "Cash in"), 80)
        cat = CAT_WORDS.get(str(d.get("cat") or "").lower().strip())
        if cat:
            line["cat"] = cat
    return line, ""


def say(line: dict) -> str:
    if line["kind"] == "balance":
        return f"Saved: {line['name']} balance {MI.money(line['amount'])}"
    return f"Saved: {MI.money(line['amount'])} {line['what']}" + (f" ({line['cat']})" if line.get("cat") else "") + (" in" if line["kind"] == "income" else "")


class Inbox:
    def __init__(self, home: str, now=time.time):
        self.home, self.now = home, now
        self.path = os.path.join(home, "money_inbox", "cash.jsonl")
        self.lock = threading.Lock()
        self.hits: list = []
        self.day: dict = {}

    def allow_list(self) -> list:
        j = MI.read_json(os.path.join(self.home, "money", "inbox.json"))
        a = j.get("allow") if isinstance(j, dict) else None
        return [str(x).strip().lower() for x in a if str(x).strip()] if isinstance(a, list) else []

    def guard(self, headers) -> tuple | None:
        """None = ok, else (status, why). Pure on the headers + the allow-list file."""
        h = {k.lower(): v for k, v in headers.items()}
        if h.get("tailscale-funnel-request"):
            return 403, "this inbox is private: only your own devices on Tailscale, never the internet"
        proxied = any(h.get(k) for k in PROXY)
        host = str(h.get("host") or "").strip().lower()
        host = host[1:].split("]", 1)[0] if host.startswith("[") else (host.rsplit(":", 1)[0] if host.count(":") == 1 else host)
        if host not in ("127.0.0.1", "localhost", "::1") and not (proxied and host.endswith(".ts.net")):
            return 403, "this inbox answers only on this PC (127.0.0.1) or at your Tailscale address"
        login = (h.get("tailscale-user-login") or "").strip().lower()
        if proxied and not login:
            return 403, "only a signed-in Tailscale device can post here"
        allow = self.allow_list()
        if allow and proxied and login not in allow:
            return 403, "this Tailscale user is not on the inbox allow-list"
        return None

    def rate(self) -> bool:
        t = self.now()
        self.hits = [x for x in self.hits if t - x < 60]
        d = dt.datetime.fromtimestamp(t, dt.timezone.utc).strftime("%Y-%m-%d")
        if len(self.hits) >= PER_MIN or self.day.get(d, 0) >= PER_DAY:
            return False
        self.hits.append(t)
        self.day = {d: self.day.get(d, 0) + 1}
        return True

    def append(self, line: dict) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        data = (json.dumps(line, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
        with self.lock:
            fd = os.open(self.path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
            try:
                os.write(fd, data)
            finally:
                os.close(fd)


def make_handler(inbox: Inbox):
    class H(BaseHTTPRequestHandler):
        server_version = "OlympusMoneyInbox/1"
        sys_version = ""
        timeout = 15                       # a client that stalls (sends less than its Content-Length) is dropped

        def log_message(self, *a):  # quiet: never log bodies
            pass

        def _send(self, status: int, obj: dict):
            body = json.dumps(obj).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path.split("?")[0] in ("/health", "/inbox/health"):
                g = inbox.guard(self.headers)
                return self._send(g[0], {"ok": False, "error": g[1]}) if g else self._send(200, {"ok": True, "kind": "olympus-money-inbox", "writes": "append only"})
            self._send(404, {"ok": False, "error": "not here"})

        def do_POST(self):
            if self.path.split("?")[0] != "/inbox":
                return self._send(404, {"ok": False, "error": "not here"})
            g = inbox.guard(self.headers)
            if g:
                return self._send(g[0], {"ok": False, "error": g[1]})
            try:
                n = int(self.headers.get("Content-Length") or "-1")
            except ValueError:
                n = -1
            if n < 0:
                return self._send(411, {"ok": False, "error": "send a Content-Length"})
            if n > MAX_BODY:
                return self._send(413, {"ok": False, "error": "too big (2 KB at most)"})
            if not inbox.rate():
                return self._send(429, {"ok": False, "error": "too many entries: wait a minute"})
            d = parse_body(self.rfile.read(n), self.headers.get("Content-Type", ""))
            if d is None:
                return self._send(400, {"ok": False, "error": 'send JSON {"amount": 12.5, "what": "Tacos"} or text "12.50 tacos"'})
            line, why = clean(d, MI.today_et())
            if not line:
                return self._send(400, {"ok": False, "error": why})
            inbox.append(line)
            self._send(200, {"ok": True, "saved": say(line), "id": line["id"]})

        def _no(self):
            self._send(405, {"ok": False, "error": "only POST /inbox"})

        do_PUT = do_DELETE = do_PATCH = _no

    return H


def serve(home: str, port: int = PORT, host: str = "127.0.0.1"):
    if host not in ("127.0.0.1", "localhost", "::1"):
        raise SystemExit("the inbox only listens on this PC (127.0.0.1); Tailscale serve brings the phone to it")
    srv = ThreadingHTTPServer((host, port), make_handler(Inbox(home)))
    srv.daemon_threads = True
    return srv


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="The append-only money inbox for the iPhone Shortcut (paper only, never trades).")
    ap.add_argument("--port", type=int, default=PORT)
    ap.add_argument("--home", help="the private folder (default OLYMPUS_HOME or %%USERPROFILE%%\\.olympus)")
    a = ap.parse_args(argv)
    srv = serve(a.home or MI.olympus_dir(), a.port)
    print(f"money inbox: listening on http://127.0.0.1:{a.port}/inbox (append only) -> {os.path.join(a.home or MI.olympus_dir(), 'money_inbox', 'cash.jsonl')}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
