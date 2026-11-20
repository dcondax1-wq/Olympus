"""AI caller red-team checks (security review 2026-11-20, research/handoff/2026-11-20/caller/SECURITY_REVIEW.md). Offline, no keys.
  a. forged consent: a stranger's number (not one of our leads), another lead's id, a valid form never confirmed -> no call;
     confirmed by the business calling in (inbound) or by the owner -> the gate passes
  b. the consent endpoint: per-sender limit (the LAST X-Forwarded-For entry, a forged first entry cannot dodge it), daily cap,
     an Origin outside consent_origins refused, a broken Content-Length refused
  c. email: a comma list / newline / name from the form or the model never reaches the outbox
  d. webhooks: a replayed signed /voice/inbound (same CallSid) never mints a second relay token; over the inbound caps = the cheap
     message; a relay token expires; a WebSocket message built from fragments past the limit is refused
  e. kill switch: OFF during an outbound call ends it at the next turn
    python -X utf8 -m tests.test_caller_security
"""
from __future__ import annotations

import base64
import datetime as dt
import hashlib
import hmac
import http.client
import json
import os
import socket
import struct
import sys
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tests.test_caller import FAKE_KEYS, LEAD, NUM, TUE_10ET, new_home  # noqa: E402
from tools.caller import actions as A  # noqa: E402
from tools.caller import brain as B  # noqa: E402
from tools.caller import compliance as G  # noqa: E402
from tools.caller import config as C  # noqa: E402
from tools.caller import consent as K  # noqa: E402
from tools.caller import run as R  # noqa: E402
from tools.caller import server as SV  # noqa: E402
from tools.caller import telephony as T  # noqa: E402

RES = []
UTC = dt.timezone.utc
LEADS = {NUM: dict(LEAD)}


def ok(cond, name, info=""):
    RES.append(bool(cond))
    print(("  PASS " if cond else "  FAIL ") + name + ("" if cond or not info else f"  -> {str(info)[:400]}"))


def form(phone="(301) 555-0142", lead_id="t1", **kw):
    return {"phone": phone, "business": LEAD["name"], "signed_name": "Tom Harbor", "agree": True, "version": K.CONSENT_VERSION,
            "lead_id": lead_id, **kw}


def part_a():
    print("a. forged consent")
    h = new_home()
    s = C.settings(h)
    t0 = dt.datetime(2026, 11, 20, 16, 0, tzinfo=UTC)
    r1 = K.record(form(phone="(240) 555-0177"), s, h, now=t0, leads=LEADS)
    ok(not r1[0], "a stranger's number (not one of our leads) is refused", r1[1])
    r2 = K.record(form(lead_id="t9"), s, h, now=t0, leads=LEADS)
    ok(not r2[0], "our lead's number with another lead's id is refused", r2[1])
    r3 = K.record(form(), s, h, now=t0, leads=LEADS)
    v = K.valid_for(NUM, TUE_10ET, s, h)
    ok(r3[0] and not v[0] and "not confirmed" in v[1] and "call us once" in r3[1], "a valid form is only PENDING (the reply says: call us once)", (r3[1], v))
    dec = G.check_outbound(dict(LEAD), TUE_10ET, "landline", v, h, s)
    ok(not dec.ok and dec.blocked_by == "consent", "the gate refuses a pending consent", dec.blocked_by)
    ok(not K.confirm(NUM, "website", h), "only inbound_call / owner can confirm")
    ok(not K.confirm("+13015559999", "owner", h), "nothing to confirm for a number with no consent")
    ok(K.pending(NUM, h), "pending() sees it")
    K.confirm(NUM, "inbound_call", h, now=t0 + dt.timedelta(minutes=5), detail="TN-Validation-Passed-A")
    v2 = K.valid_for(NUM, TUE_10ET, s, h)
    ok(v2[0] and G.check_outbound(dict(LEAD), TUE_10ET, "landline", v2, h, s).ok, "confirmed by the business calling in: the gate passes", v2)
    K.record(form(), s, h, now=t0 + dt.timedelta(days=1), leads=LEADS)
    ok(not K.valid_for(NUM, TUE_10ET, s, h)[0], "a NEW form after the confirm needs its own confirm")


def part_b():
    print("b. the consent endpoint")
    h = new_home()
    app = SV.Caller(h, None, public_base="https://pc.example.ts.net:10000")
    real = SV.R.leads_by_phone
    SV.R.leads_by_phone = lambda *a, **k: dict(LEADS)
    try:
        codes = [app.consent_post(form(), "203.0.113.9", "ua")[0] for _ in range(6)]
        ok(codes[:5] == [200] * 5 and codes[5] == 429, "5 an hour per sender, the 6th refused", codes)
        fake = {"X-Forwarded-For": "1.2.3.%d, 203.0.113.9" % 7}
        ok(SV.client_ip(fake, "127.0.0.1") == "203.0.113.9", "the LAST X-Forwarded-For entry is used (Funnel appends the real client)")
        ok(app.consent_post(form(), SV.client_ip(fake, "127.0.0.1"), "ua")[0] == 429, "a forged first entry does not reset the limit")
        f = {"ok": 0}
        app.day_hits = {"day": time.strftime("%Y-%m-%d", time.gmtime()), "n": int(C.settings(h)["limits"]["consent_per_day"])}
        ok(app.consent_post(form(), "198.51.100.1", "ua")[0] == 429, "the daily cap holds for every sender")
        s = C.settings(h)
        with open(os.path.join(h, "caller", "settings.json"), encoding="utf-8") as fh:
            mine = json.load(fh)
        mine["consent_origins"] = ["https://demo.example.com"]
        with open(os.path.join(h, "caller", "settings.json"), "w", encoding="utf-8") as fh:
            json.dump(mine, fh)
        app.day_hits = {"day": "", "n": 0}
        ok(app.consent_post(form(), "198.51.100.2", "ua", "https://evil.example")[0] == 403, "an Origin outside consent_origins is refused")
        ok(app.consent_post(form(), "198.51.100.3", "ua", "https://demo.example.com")[0] == 200, "the demo site's own Origin passes")
        del f, s
    finally:
        SV.R.leads_by_phone = real


def part_c():
    print("c. email addresses")
    for bad in ("a@b.com, c@d.com", "a@b.com\nBcc: x@y.com", "Tom <a@b.com>", "a@b", "", "x" * 200 + "@b.com"):
        if A.valid_email(bad):
            ok(False, "a bad address is refused: " + repr(bad))
            break
    else:
        ok(True, "a list, a newline, a display name, no domain, too long: all refused")
    ok(A.valid_email(" tom@example.com ") == "tom@example.com", "one plain address passes")
    h = new_home()
    act = A.Actions(h, C.settings(h))
    act.queue_email("demo_link", "a@b.com,\nvictim@x.com", "s", "b", LEAD)
    p = os.path.join(h, "caller", "outbox.jsonl")
    ok(not os.path.exists(p) or "victim" not in open(p, encoding="utf-8").read(), "the outbox never gets the injected list")

    class Fake:
        class beta:
            class messages:
                @staticmethod
                def create(**kw):
                    tu = type("B", (), {"type": "tool_use", "name": "send_email", "input": {"kind": "demo", "email": "a@b.com, spam@x.com"}})()
                    tx = type("B", (), {"type": "text", "text": "Sure."})()
                    return type("R", (), {"content": [tx, tu], "stop_reason": "tool_use"})()
    cs = B.CallSession(dict(LEAD), C.settings(h), B.ClaudeBrain("x", client=Fake()), act, TUE_10ET)
    cs.start()
    cs.hear("send it to a@b.com comma spam@x.com")
    ok("spam@x.com" not in (cs.email or "") and "spam" not in (open(p, encoding="utf-8").read() if os.path.exists(p) else ""),
       "an injected list from the model (prompt injection) never becomes the email", cs.email)


def sig(token, url, params):
    return base64.b64encode(hmac.new(token.encode(), (url + "".join(k + params[k] for k in sorted(params))).encode(), hashlib.sha1).digest()).decode()


def ws_client(port, path):
    s = socket.create_connection(("127.0.0.1", port), timeout=5)
    key = base64.b64encode(os.urandom(16)).decode()
    s.sendall((f"GET {path} HTTP/1.1\r\nHost: x\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\n"
               "Sec-WebSocket-Version: 13\r\n\r\n").encode())
    head = b""
    while b"\r\n\r\n" not in head:
        head += s.recv(1)
    return s, head.decode()


def frame(text, fin=True, op=1):
    data = text.encode()
    mask = os.urandom(4)
    n = len(data)
    hdr = bytes([(0x80 if fin else 0) | op]) + (bytes([0x80 | n]) if n < 126 else bytes([0x80 | 126]) + struct.pack(">H", n))
    return hdr + mask + bytes(c ^ mask[i % 4] for i, c in enumerate(data))


def part_d_e():
    print("d. webhooks, tokens, frames")
    h = new_home()
    pub = "https://pc.example.ts.net:10000"
    app = SV.Caller(h, None, public_base=pub, clock=lambda: TUE_10ET)
    httpd = SV.serve(0, app, dial_every=3600)
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    def post(path, params):
        body = __import__("urllib.parse").parse.urlencode(params).encode()
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        c.request("POST", path, body=body, headers={"Content-Type": "application/x-www-form-urlencoded", "Content-Length": str(len(body)),
                                                    "X-Twilio-Signature": sig(FAKE_KEYS["twilio_token"], pub + path, params)})
        r = c.getresponse()
        return r.status, r.read().decode()
    p1 = {"CallSid": "CA" + "7" * 32, "From": "+13015550142", "To": "+13015550100"}
    st1, x1 = post("/voice/inbound", p1)
    st2, x2 = post("/voice/inbound", p1)
    ok(st1 == 200 and "/relay?t=" in x1 and st2 == 200 and "/relay?t=" not in x2 and "<Hangup/>" in x2,
       "a replayed signed webhook (same CallSid) gets no second relay token", (x1[:80], x2[:80]))
    outs = [post("/voice/inbound", {**p1, "CallSid": "CA" + str(i) * 32})[1] for i in range(1, 4)]
    ok("/relay?t=" in outs[0] and "/relay?t=" in outs[1] and "/relay?t=" not in outs[2],
       "one number: 3 conversations a day (the replay was not counted), then the cheap message", [("/relay" in o) for o in outs])
    tok = "tok-expired"
    app.register(tok, {"lead": dict(LEAD), "call_id": "CAX", "email": "", "inbound": False})
    app.pending[tok]["_t"] -= 10_000
    s, head = ws_client(port, f"/relay?t={tok}")
    ok(" 403 " in head.split("\r\n")[0], "an expired relay token is refused", head.split("\r\n")[0])
    s.close()
    tok2 = "tok-frag"
    app.register(tok2, {"lead": dict(LEAD), "call_id": "CAY", "email": "", "inbound": True})
    s, head = ws_client(port, f"/relay?t={tok2}")
    try:
        for _ in range(3):
            s.sendall(frame("x" * 30000, fin=False))
        time.sleep(0.5)
        s.settimeout(3)
        closed = s.recv(10) == b""
    except (ConnectionError, OSError):
        closed = True
    ok(" 101 " in head and closed, "fragments past the 64 KB limit: the server drops the socket", head.split("\r\n")[0])
    s.close()

    held = []
    for _ in range(SV.MAX_CONNECTIONS + 4):                 # idle connections: each holds a slot until its read times out
        c = socket.create_connection(("127.0.0.1", port), timeout=3)
        held.append(c)
    time.sleep(0.5)
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
    try:
        c.request("GET", "/health")
        refused = False
        c.getresponse().read()
    except (ConnectionError, OSError, http.client.HTTPException):
        refused = True
    ok(refused, "past %d open connections a new one is closed (a flood never takes the trading PC's CPU)" % SV.MAX_CONNECTIONS)
    for c2 in held:
        c2.close()
    time.sleep(0.5)

    print("e. the kill switch mid-call")
    tok3 = "tok-kill"
    app.register(tok3, {"lead": dict(LEAD), "call_id": "CAZ", "email": "", "inbound": False})
    s, head = ws_client(port, f"/relay?t={tok3}")
    with open(os.path.join(h, "caller", "state.json"), "w", encoding="utf-8") as fh:
        json.dump({"on": False}, fh)
    s.sendall(frame(json.dumps({"type": "prompt", "voicePrompt": "hello who is this", "last": True})))
    s.settimeout(5)
    got = b""
    try:
        while b'"end"' not in got:
            part = s.recv(4096)
            if not part:
                break
            got += part
    except OSError:
        pass
    ok(b"goodbye" in got and b'"end"' in got, "OFF during an outbound call: a goodbye and the end, at the next turn", got[:120])
    s.close()
    httpd.shutdown()


def main():
    part_a()
    part_b()
    part_c()
    part_d_e()
    n = sum(RES)
    print(f"\ncaller_security: {n}/{len(RES)} " + ("ALL PASS" if n == len(RES) else "FAILED"))
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
