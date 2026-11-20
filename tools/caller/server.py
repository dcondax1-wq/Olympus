"""THE CALLER SERVER: its own process on 127.0.0.1:8790 (never the bot server's port), stdlib only.

  GET  /health            {"ok", "kind": "olympus-caller", "on"}                       (says nothing about calls)
  POST /consent           the demo page's "Call me" form (JSON) -> consent.record          (30 a minute, 4 KB max)
  POST /voice/inbound     Twilio: a business calls the agency number -> ConversationRelay with the inbound disclosure opener
  POST /voice/status      Twilio: how an outbound call ended (no answer / busy / voicemail / completed)
  GET  /relay?t=TOKEN     the ConversationRelay WebSocket: Twilio sends what the person said, we answer with text
Every /voice/* request must carry a valid X-Twilio-Signature; every /relay needs the one-time token made when the call was set up.
The public address is Tailscale Funnel on :10000 (CALLER_ON.bat), which forwards to this port. The dialer thread runs run.tick()
once a minute while the caller is ON. Run: python -m tools.caller.server [--port 8790] [--public https://pc.tailnet.ts.net:10000]
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import json
import os
import secrets
import struct
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    __package__ = "tools.caller"

from . import actions as A  # noqa: E402
from . import brain as B  # noqa: E402
from . import compliance as G  # noqa: E402
from . import config as C  # noqa: E402
from . import consent as K  # noqa: E402
from . import run as R  # noqa: E402
from . import telephony as T  # noqa: E402

WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
MAX_BODY = 4096


# ---------------------------------------------------------------- a minimal RFC 6455 WebSocket (text frames, ping, close)

def ws_accept(key: str) -> str:
    return base64.b64encode(hashlib.sha1((key + WS_GUID).encode()).digest()).decode()


def ws_send(sock, text: str, opcode: int = 1):
    data = text.encode()
    n = len(data)
    head = bytes([0x80 | opcode]) + (bytes([n]) if n < 126 else (bytes([126]) + struct.pack(">H", n) if n < 65536 else bytes([127]) + struct.pack(">Q", n)))
    sock.sendall(head + data)


def _recv(sock, n):
    buf = b""
    while len(buf) < n:
        part = sock.recv(n - len(buf))
        if not part:
            raise ConnectionError("closed")
        buf += part
    return buf


def ws_recv(sock, limit: int = 65536):
    """(opcode, text). Client frames must be masked (RFC 6455 5.1); fragments are joined."""
    out, op0 = b"", None
    while True:
        b1, b2 = _recv(sock, 2)
        fin, op, masked, n = b1 & 0x80, b1 & 0x0F, b2 & 0x80, b2 & 0x7F
        if n == 126:
            n = struct.unpack(">H", _recv(sock, 2))[0]
        elif n == 127:
            n = struct.unpack(">Q", _recv(sock, 8))[0]
        if n > limit or not masked:
            raise ConnectionError("bad frame")
        mask = _recv(sock, 4)
        payload = bytes(c ^ mask[i % 4] for i, c in enumerate(_recv(sock, n)))
        if op == 9:
            ws_send(sock, payload.decode("latin-1"), 10)
            continue
        if op == 8:
            return 8, ""
        if op in (1, 2):
            op0 = op
        out += payload
        if fin:
            return op0 or op, out.decode("utf-8", "replace")


# ---------------------------------------------------------------- the app

class Caller:
    def __init__(self, h=None, adapter=None, brain_factory=None, public_base="", clock=None):
        self.h = h
        self.adapter = adapter
        self.public = public_base.rstrip("/")
        self.clock = clock or (lambda: dt.datetime.now(dt.timezone.utc))
        self.brain_factory = brain_factory or (lambda: B.ScriptedBrain())
        self.pending = {}            # token -> {"lead", "call_id", "email", "inbound"}
        self.lock = threading.Lock()
        self.hits = []               # consent rate limit
        self.token = C.load_keys(h).get("twilio_token", "")

    def s(self):
        return C.settings(self.h)

    def is_on(self):
        return bool(G.caller_state(self.h).get("on"))

    def register(self, token, info):
        with self.lock:
            self.pending[token] = info

    def take(self, token):
        with self.lock:
            return self.pending.pop(token, None)

    # -- Twilio webhooks
    def inbound_twiml(self, params: dict) -> str:
        s = self.s()
        if not self.is_on():
            msg = (f"Thanks for calling {s.get('agency_name')}. This is an automated message, and our AI assistant is off right now. "
                   f"Please email us, or call back on a weekday between 9 and 5. Goodbye.")
            return f'<?xml version="1.0" encoding="UTF-8"?><Response><Say>{T.quoteattr(msg)[1:-1]}</Say><Hangup/></Response>'
        frm = G.e164(params.get("From", ""))
        lead = dict(R.leads_by_phone().get(frm) or {"phone": frm, "name": "", "state": R.AREA_STATE.get(G.area_code(frm), "MD")})
        tok = secrets.token_urlsafe(18)
        self.register(tok, {"lead": lead, "call_id": params.get("CallSid", ""), "email": "", "inbound": True})
        return T.relay_twiml(self.public.replace("https://", "wss://") + f"/relay?t={tok}", G.opening_line(s, inbound=True), s.get("voice", {}))

    def status(self, params: dict):
        st, ans = params.get("CallStatus", ""), params.get("AnsweredBy", "")
        outcome = {"no-answer": "no_answer", "busy": "busy", "failed": "failed", "canceled": "failed"}.get(st, "")
        if ans.startswith("machine") or ans == "fax":
            outcome = "voicemail"            # no AI voicemail is ever left: machine = hang up, try once more another day
            if self.adapter and params.get("CallSid"):
                try:
                    self.adapter.hangup(params["CallSid"])
                except Exception:
                    pass
        if outcome:
            G.log_call({"kind": "result", "ts": self.clock().isoformat(), "call_id": params.get("CallSid", ""), "dir": "out",
                        "number": G.e164(params.get("To", "")), "outcome": outcome}, self.h)

    # -- the conversation
    def converse(self, sock, info: dict):
        s = self.s()
        act = A.Actions(self.h, s, dry=False)
        cs = B.CallSession(info["lead"], s, self.brain_factory(), act, self.clock(), inbound=info["inbound"], email=info.get("email", ""),
                           call_id=info.get("call_id", ""))
        cs.start()                                    # the greeting itself was spoken by Twilio (welcomeGreeting = this same line)
        started = time.time()
        try:
            while not cs.ended:
                op, txt = ws_recv(sock)
                if op == 8:
                    break
                try:
                    m = json.loads(txt)
                except ValueError:
                    continue
                if m.get("type") == "prompt" and m.get("last", True):
                    r = cs.hear(str(m.get("voicePrompt", ""))[:1000])
                    if r.text:
                        ws_send(sock, json.dumps({"type": "text", "token": r.text, "last": True}))
                    if time.time() - started > int(s["limits"]["max_call_seconds"]) and not cs.ended:
                        ws_send(sock, json.dumps({"type": "text", "token": "I'll let you go. I'll email the details. Thanks!", "last": True}))
                        cs.ended = True
                    if cs.ended:
                        ws_send(sock, json.dumps({"type": "end", "handoffData": json.dumps({"outcome": cs.outcome})}))
                elif m.get("type") == "error":
                    break
        except (ConnectionError, OSError):
            pass
        rec = cs.record()
        G.log_call(rec, self.h)
        tdir = os.path.join(C.state_dir(self.h), "transcripts")
        os.makedirs(tdir, exist_ok=True)
        tpath = os.path.join(tdir, f"{rec['ts'][:10]}-{(rec['call_id'] or 'call')[-10:]}.json")
        with open(tpath, "w", encoding="utf-8") as f:
            f.write(C.redact(json.dumps({**rec, "transcript": cs.transcript}, indent=1), self.h))
        act.inbox({**rec, "summary": " / ".join(t["text"][:80] for t in cs.transcript if t["who"] == "biz")[:400],
                   "transcript_file": os.path.basename(tpath)})

    def consent_post(self, body: dict, ip: str, ua: str) -> tuple:
        now = time.time()
        self.hits = [t for t in self.hits if now - t < 60]
        if len(self.hits) >= 30:
            return 429, {"ok": False, "message": "Too many requests, please try again in a minute."}
        self.hits.append(now)
        ok, msg, _ = K.record(body, self.s(), self.h, ip=ip, ua=ua)
        return (200 if ok else 400), {"ok": ok, "message": msg}


def make_handler(app: Caller):
    class H(BaseHTTPRequestHandler):
        server_version = "OlympusCaller/1"

        def log_message(self, fmt, *args):      # no request lines (numbers) in the console
            return

        def _send(self, code, body, ctype="application/json"):
            data = body.encode() if isinstance(body, str) else json.dumps(body).encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(data)

        def _body(self):
            n = int(self.headers.get("Content-Length") or 0)
            if n <= 0 or n > MAX_BODY:
                return None
            return self.rfile.read(n)

        def do_OPTIONS(self):
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "POST")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()

        def do_GET(self):
            u = urllib.parse.urlparse(self.path)
            if u.path == "/health":
                return self._send(200, {"ok": True, "kind": "olympus-caller", "on": app.is_on()})
            if u.path == "/relay" and self.headers.get("Upgrade", "").lower() == "websocket":
                tok = (urllib.parse.parse_qs(u.query).get("t") or [""])[0]
                info = app.take(tok) if tok else None
                if not info:
                    return self._send(403, {"ok": False})
                self.send_response(101, "Switching Protocols")
                self.send_header("Upgrade", "websocket")
                self.send_header("Connection", "Upgrade")
                self.send_header("Sec-WebSocket-Accept", ws_accept(self.headers.get("Sec-WebSocket-Key", "")))
                self.end_headers()
                self.wfile.flush()
                self.close_connection = True
                return app.converse(self.connection, info)
            return self._send(404, {"ok": False})

        def do_POST(self):
            u = urllib.parse.urlparse(self.path)
            raw = self._body()
            if raw is None:
                return self._send(413, {"ok": False, "message": "empty or too big"})
            if u.path == "/consent":
                try:
                    body = json.loads(raw.decode())
                except ValueError:
                    return self._send(400, {"ok": False, "message": "bad form"})
                code, out = app.consent_post(body if isinstance(body, dict) else {}, self.headers.get("X-Forwarded-For", self.client_address[0]),
                                             self.headers.get("User-Agent", ""))
                return self._send(code, out)
            if u.path in ("/voice/inbound", "/voice/status"):
                params = {k: v[0] for k, v in urllib.parse.parse_qs(raw.decode(), keep_blank_values=True).items()}
                if not T.twilio_signature_ok(app.token, app.public + u.path, params, self.headers.get("X-Twilio-Signature", "")):
                    return self._send(403, {"ok": False})
                if u.path == "/voice/inbound":
                    return self._send(200, app.inbound_twiml(params), "text/xml")
                app.status(params)
                return self._send(204, "")
            return self._send(404, {"ok": False})

    return H


def serve(port: int, app: Caller, host: str = "127.0.0.1", dial_every: int = 60):
    if host not in ("127.0.0.1", "localhost"):
        raise SystemExit("the caller listens on this PC only (127.0.0.1); Tailscale Funnel forwards the public address")
    httpd = ThreadingHTTPServer((host, port), make_handler(app))

    def dialer():
        while True:
            time.sleep(dial_every)
            try:
                if app.is_on() and app.adapter is not None:
                    R.tick(app.clock(), app.adapter, app.public, app.h, register=app.register)
            except Exception as e:  # never crash the server; the reason goes to the log without secrets
                with open(os.path.join(C.state_dir(app.h), "errors.log"), "a", encoding="utf-8") as f:
                    f.write(C.redact(f"{dt.datetime.now(dt.timezone.utc).isoformat()} dialer: {e!r}", app.h) + "\n")

    threading.Thread(target=dialer, daemon=True).start()
    return httpd


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=0)
    ap.add_argument("--public", default="", help="the Funnel address, e.g. https://my-pc.tailnet.ts.net:10000")
    a = ap.parse_args(argv)
    s = C.settings()
    keys = C.load_keys()
    if not C.keys_ready():
        print("Keys missing: run CALLER_SETUP.bat first. (The simulator needs no keys: python -m tools.caller.simulate)")
        return 2
    public = a.public or str(G.caller_state().get("public") or "")
    if not public.startswith("https://"):
        print("No public https address yet: CALLER_ON.bat sets it from Tailscale Funnel.")
        return 2
    model = s.get("model", "claude-opus-5-5")
    app = Caller(adapter=T.TwilioAdapter(keys, s["limits"]["max_call_seconds"]), public_base=public,
                 brain_factory=lambda: B.ClaudeBrain(keys["anthropic_key"], model, s.get("effort", "low")))
    httpd = serve(a.port or int(s.get("port", 8790)), app)
    print(f"Caller server on 127.0.0.1:{httpd.server_address[1]}  (public {public}; {'ON' if app.is_on() else 'OFF'}). Ctrl+C or CALLER_STOP.bat stops it.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
