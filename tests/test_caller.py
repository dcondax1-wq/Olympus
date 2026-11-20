"""AI CALLER (tools/caller/, day-caller 2026-11-20): the consent-first AI phone assistant. Offline, no network, no money. Checks:
  a. disclosure first: the opener says AI + agency + recorded in its FIRST sentence (outbound and inbound); a broken opener or a missing
     agency name stops the call before it starts; a reply claiming to be human is replaced before it is spoken
  b. never a wireless number: mobile / VoIP / unknown are blocked; only a landline passes; the dialer never dials a blocked number
  c. consent: no signed consent = no call (Md. Com. Law 14-4502(a)(3)); revoked, old wording or incomplete forms are refused
  d. hours: Mon-Fri 9:00-17:00 their time, never weekends / federal holidays / the day after Thanksgiving, unknown state = no call
  e. caps: the daily cap, 1 call + 1 follow-up, the follow-up only after no answer and 2 business days; OFF blocks everything
  f. opt-out: "don't call me" ends the call at once, our do-not-call list + consent revoked, the gate refuses that number forever;
     the federal registry copy must exist, be <= 31 days old and cover the area code
  g. the switch: START CALLING typed exactly, keys present, agency named, cap 1-100; OFF always works
  h. no secret in files or logs: keys live outside the repo, every written line is redacted, no key-shaped string in tools/caller or the bats
  i. the simulator runs offline (network cut) and every persona scores 100%
  j. the server: 127.0.0.1 only, its own port, Twilio signatures required, consent form, inbound TwiML, a real WebSocket conversation
  k. separation: tools/caller never imports engine/, server.py, ninjatrader; the bats are ASCII + CRLF and never touch port 8766
    python -X utf8 -m tests.test_caller
"""
from __future__ import annotations

import base64
import datetime as dt
import glob
import hashlib
import hmac
import http.client
import json
import os
import re
import shutil
import socket
import struct
import sys
import tempfile
import threading
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools.caller import actions as A  # noqa: E402
from tools.caller import brain as B  # noqa: E402
from tools.caller import compliance as G  # noqa: E402
from tools.caller import config as C  # noqa: E402
from tools.caller import consent as K  # noqa: E402
from tools.caller import cost as CO  # noqa: E402
from tools.caller import onoff as O  # noqa: E402
from tools.caller import registry as RG  # noqa: E402
from tools.caller import run as R  # noqa: E402
from tools.caller import server as SV  # noqa: E402
from tools.caller import setup_keys as SK  # noqa: E402
from tools.caller import simulate as SIM  # noqa: E402
from tools.caller import siteform as SF  # noqa: E402
from tools.caller import telephony as T  # noqa: E402

RES = []
UTC = dt.timezone.utc
TUE_10ET = dt.datetime(2026, 11, 24, 15, 0, tzinfo=UTC)     # Tue Nov 24 2026 10:00 ET
NUM = "+13015550142"
LEAD = {"id": "t1", "name": "Harbor Street Plumbing", "state": "MD", "phone": "(301) 555-0142", "town": "Frederick"}
FAKE_KEYS = {"twilio_sid": "AC" + "a1" * 16, "twilio_token": "f0" * 16, "twilio_from": "+13015550100", "anthropic_key": "sk-ant-test-" + "x" * 30}


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:600]}"), flush=True)


def new_home(keys=True, on=True, registry=True, cap=20, outbound=True):
    h = tempfile.mkdtemp(prefix="caller-test-")
    os.makedirs(os.path.join(h, "caller"), exist_ok=True)
    with open(os.path.join(h, "caller", "settings.json"), "w") as f:
        json.dump({"agency_name": "Brightline Web Studio", "owner_first_name": "Dee", "callback_number": "(301) 555-0100",
                   "postal_address": "1 Example St, Frederick, MD 21701", "payment_link": "https://example.com/pay",
                   "outbound_enabled": outbound}, f)
    if keys:
        with open(os.path.join(h, "caller.json"), "w") as f:
            json.dump(FAKE_KEYS, f)
    if on:
        with open(os.path.join(h, "caller", "state.json"), "w") as f:
            json.dump({"on": True, "daily_cap": cap}, f)
    if registry:
        os.makedirs(os.path.join(h, "caller", "registry"), exist_ok=True)
        for ac in ("301", "240", "410", "443", "667"):
            with open(os.path.join(h, "caller", "registry", f"{ac}.txt"), "w") as f:
                f.write("3015550999\n")
        RG.stamp(h, dt.date(2026, 11, 20))
    return h


def sign(h, phone=NUM, now=None, confirm=True):
    """A signed consent; confirm=True also confirms it (security review 2026-11-20: a consent counts only once confirmed)."""
    s = C.settings(h)
    t = now or dt.datetime(2026, 11, 20, 16, 0, tzinfo=UTC)
    r = K.record({"phone": phone, "business": LEAD["name"], "signed_name": "Tom Harbor", "agree": True, "version": K.CONSENT_VERSION,
                  "email": "tom@example.com"}, s, h, now=t)
    if confirm and r[0]:
        K.confirm(phone, "owner", h, now=t + dt.timedelta(seconds=1))
    return r


def gate(h, now=TUE_10ET, line="landline", lead=None, calls=None):
    lead = lead or LEAD
    s = C.settings(h)
    return G.check_outbound(lead, now, line, K.valid_for(lead["phone"], now, s, h), h, s, calls)


def main() -> int:
    # ---------------------------------------------------------------- a. disclosure first
    h = new_home()
    s = C.settings(h)
    for inbound in (False, True):
        line = G.opening_line(s, LEAD["name"], inbound=inbound)
        ok, why = G.check_disclosure(line, s)
        fs = G.first_sentence(line)
        check(f"a. {'inbound' if inbound else 'outbound'} opener: the FIRST sentence says AI assistant + {s['agency_name']} + recorded",
              ok and "AI assistant" in fs and "recorded" in fs and s["agency_name"] in fs, (why, fs))
    check("a. an opener without 'AI' / without 'recorded' / claiming to be human fails the check",
          not G.check_disclosure("Hi, this is Ava from Brightline Web Studio. This call is recorded.", s)[0]
          and not G.check_disclosure("Hi, this is Ava, an AI assistant for Brightline Web Studio.", s)[0]
          and not G.check_disclosure("Hi, this is Ava, an AI assistant calling for Brightline Web Studio, this call is recorded, and I'm a real person.", s)[0])
    try:
        B.CallSession(LEAD, {**s, "agency_name": "YOUR AGENCY"}, B.ScriptedBrain(), A.Actions(h, s), TUE_10ET).start()
        check("a. a missing agency name stops the call before a word is spoken", False)
    except RuntimeError:
        check("a. a missing agency name stops the call before a word is spoken", True)
    lies = ["Yes, I'm a real person.", "I am human, don't worry.", "I'm not a robot.", "Real person here!", "I'm a woman named Ava."]
    check("a. every reply that claims to be human is replaced by the honest AI line before it is spoken",
          all(G.speech_filter(x, s)[1] and "AI assistant" in G.speech_filter(x, s)[0] for x in lies)
          and not G.speech_filter("Sure, Wednesday at 10 works.", s)[1])

    class LyingBrain:
        def respond(self, cs, said):
            return B.Reply("Of course, I'm a real person!")
    cs = B.CallSession(LEAD, s, LyingBrain(), A.Actions(h, s), TUE_10ET)
    cs.start()
    out = cs.hear("Are you a real person?").text
    check("a. even a model that lies is overruled: the spoken text says AI, and the replacement is counted", "AI assistant" in out and cs.filtered == 1, out)

    # ---------------------------------------------------------------- launch = inbound only (lead 2026-11-20)
    hi = new_home(outbound=False)
    sign(hi)
    fa0 = T.FakeAdapter({NUM: "landline"})
    check("launch: the repo default is inbound only (outbound_enabled false); even ON + consent + landline, the gate and the dialer make no outbound call",
          C.read_json(os.path.join(ROOT, "tools", "caller", "settings.json"))["outbound_enabled"] is False
          and gate(hi).blocked_by == "switch" and "inbound only" in " ".join(gate(hi).reasons)
          and R.tick(TUE_10ET, fa0, "https://x.example", hi, leads_path=os.path.join(hi, "none.json")) is None and fa0.dialed == [])
    os.environ["OLYMPUS_HOME"] = hi
    try:
        check("launch: CALLER_ON says the receptionist answers and makes no outbound calls", "no outbound calls" in O.turn_on("START CALLING", 20, h=hi)[1])
    finally:
        os.environ.pop("OLYMPUS_HOME", None)

    # ---------------------------------------------------------------- b. never a wireless number
    h = new_home()
    sign(h)
    res = {lt: gate(h, line=lt) for lt in ("landline", "mobile", "voip", "unknown", "tollFree", "")}
    check("b. only a landline passes; mobile, VoIP, toll-free, unknown and blank are blocked by the line-type check",
          res["landline"].ok and all(not d.ok and d.blocked_by == "line type" for k, d in res.items() if k != "landline"),
          {k: (d.ok, d.blocked_by) for k, d in res.items()})
    fa = T.FakeAdapter({NUM: "mobile"})
    att = R.tick(TUE_10ET, fa, "https://pc.example.ts.net:10000", h, leads_path=os.path.join(h, "none.json"))
    check("b. the dialer looks the number up and never dials a mobile number", att is None and fa.dialed == [] and fa.lookups == [NUM], fa.__dict__)
    check("b. Twilio line types map: landline -> landline, mobile -> mobile, fixed/non-fixed VoIP -> voip, anything else -> unknown",
          T.LINE_TYPES == {"landline": "landline", "mobile": "mobile", "fixedVoip": "voip", "nonFixedVoip": "voip"})

    # ---------------------------------------------------------------- c. consent
    h = new_home()
    d = gate(h)
    check("c. no signed consent = no call, and the reason names the Maryland statute", not d.ok and d.blocked_by == "consent"
          and "14-4502" in " ".join(d.reasons), d.reasons)
    bad = [{"phone": NUM, "signed_name": "Tom Harbor", "agree": False, "version": K.CONSENT_VERSION},
           {"phone": NUM, "signed_name": "T", "agree": True, "version": K.CONSENT_VERSION},
           {"phone": "555", "signed_name": "Tom Harbor", "agree": True, "version": K.CONSENT_VERSION},
           {"phone": NUM, "signed_name": "Tom Harbor", "agree": True, "version": "v0"},
           {"phone": NUM, "signed_name": "Tom Harbor", "agree": "yes", "version": K.CONSENT_VERSION}]
    check("c. unticked box, no full-name signature, bad number, old form, or a non-boolean 'agree' are all refused",
          all(not K.record(b, C.settings(h), h)[0] for b in bad) and K.consented_numbers(h) == [])
    ok, _, rec = sign(h)
    check("c. a signed form is stored with the exact wording (AI voice, automated dialing, recorded, not a condition of purchase, the number)",
          ok and all(w in rec["text"] for w in ("AI assistant", "artificial voice", "automated dialing", "recorded", "do not have to agree", NUM))
          and rec["text_sha256"] == hashlib.sha256(rec["text"].encode()).hexdigest(), rec)
    check("c. with consent the gate allows the call (everything else in order)", gate(h).ok, gate(h).reasons)
    check("c. consent for one number does not cover another number", not gate(h, lead={**LEAD, "phone": "(301) 555-0143"}).ok)
    K.revoke(NUM, "test", h, now=dt.datetime(2026, 11, 21, tzinfo=UTC))
    check("c. a revoked consent blocks the call", gate(h).blocked_by == "consent")
    h2 = new_home()
    sign(h2, now=dt.datetime(2025, 10, 1, tzinfo=UTC))
    check("c. consent older than 365 days blocks the call", gate(h2).blocked_by == "consent", gate(h2).reasons)
    html = K.consent_form_html(C.settings(h), LEAD, "https://pc.example.ts.net:10000/consent")
    check("c. the demo-page form shows the full consent wording, a required box and a typed-name signature, and posts to /consent",
          "artificial voice" in html and 'name="agree" required' in html and 'name="signed_name" required' in html and "/consent" in html)
    check("c. the button is exactly 'Have our assistant call me' (the Day-0 email names it) and the consent text quotes it",
          ">Have our assistant call me</button>" in html and K.BUTTON in K.CONSENT_TEXT)
    sh = glob.glob(os.path.join(h, "caller", "share", "consent", "*.json"))
    shared = json.load(open(sh[0])) if sh else {}
    check("c. each consent leaves a share/consent/<id>.json for the email autopilot: lead_id, asked_t, window, phone_source, and NO phone / name / email",
          len(sh) == 1 and shared.get("phone_source") == "their form" and shared.get("window") == "any" and "asked_t" in shared
          and not ({"phone", "signed_name", "email", "text"} & set(shared)), shared)
    real = {**C.settings(h), "callback_number": "(301) 662-0100", "owner_first_name": "Dee"}
    sf = SF.build(s=real)
    ch = sf["caller_html"]
    check("c. siteform: inline markup for the site factory slot, posts to the site's own /api/consent (no PC address), hidden lead_id + business, no third party, no key",
          'data-post="/api/consent"' in ch and 'name="lead_id"' in ch and 'name="business"' in ch and ".ts.net" not in ch
          and not re.search(r"<script[^>]+src=|formspree|googleapis|AC[0-9a-f]{32}|sk-ant-", ch) and sf["caller_button"] == K.BUTTON)
    for bad_ep, why in (("https://olympus-caller.tail1234.ts.net:10000", "a Tailscale address (the privacy pass masks it)"),
                        ("http://evil.example/x?y", "a non-https endpoint")):
        try:
            SF.build(bad_ep, real)
            check(f"c. siteform refuses {why}", False)
        except SystemExit:
            check(f"c. siteform refuses {why}", True)
    try:
        SF.build(s={**real, "callback_number": "(555) 555-0100"})
        check("c. siteform refuses placeholder agency details ((555) 555-0100 / YOUR AGENCY) in the consent text", False)
    except SystemExit:
        check("c. siteform refuses placeholder agency details ((555) 555-0100 / YOUR AGENCY) in the consent text", True)
    from tools.caller import pull as PL
    hp = new_home()
    with open(os.path.join(hp, "caller.json"), "w") as f:
        json.dump({**FAKE_KEYS, "cf_account": "acct1", "cf_kv_namespace": "ns1", "cf_kv_token": "cftok" + "z" * 30}, f)
    store = {"c:2026-11-20T16:00:00Z:ab": json.dumps({"form": {"phone": "(301) 555-0142", "signed_name": "Tom Harbor", "agree": True,
                                                             "version": K.CONSENT_VERSION, "window": "morning", "lead_id": "osm-n1"},
                                                    "received": "2026-11-20T16:00:00Z", "ip": "1.2.3.4", "ua": "x"}),
             "c:2026-11-20T16:01:00Z:cd": json.dumps({"form": {"phone": "12", "agree": True}, "received": "2026-11-20T16:01:00Z"})}
    seen = []

    class Resp:
        def __init__(self, b): self.b = b.encode()
        def read(self): return self.b
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def opener(req, timeout=0):
        seen.append((req.get_method(), req.full_url, req.headers.get("Authorization")))
        u = urllib.parse.unquote(req.full_url)
        if "/keys?" in req.full_url:
            return Resp(json.dumps({"result": [{"name": k} for k in store]}))
        name = u.split("/values/")[1]
        if req.get_method() == "DELETE":
            store.pop(name, None)
            return Resp("{}")
        return Resp(store[name])
    r = PL.pull(hp, opener=opener, leads={NUM: {"id": "osm-n1"}})
    K.confirm(NUM, "owner", hp, now=dt.datetime(2026, 11, 20, 16, 5, tzinfo=UTC))
    check("c. pull: the site's signed forms come from Cloudflare KV into the PC store (lead-matched, pending until confirmed; bad ones refused), each entry deleted after, Bearer token used",
          r == {"ok": True, "added": 1, "refused": 1} and not store and K.valid_for(NUM, TUE_10ET, C.settings(hp), hp)[0]
          and all(a == "Bearer cftok" + "z" * 30 for _, _, a in seen) and any(m == "DELETE" for m, _, _ in seen), (r, seen))
    js = open(os.path.join(ROOT, "tools", "caller", "cloudflare", "consent.js"), encoding="utf-8").read()
    check("c. the Cloudflare function checks the same rules (agree true, full name, 10-digit phone, version), caps 5 a day per IP, CORS pinned to ALLOWED_ORIGIN only (never *), holds no secret",
          "b.agree !== true" in js and K.CONSENT_VERSION in js and "n >= 5" in js and "env.CONSENT" in js and 'request.headers.get("Origin") !== env.ALLOWED_ORIGIN' in js and js.count("ALLOWED_ORIGIN") >= 4
          and '"*"' not in js and not re.search(r"token|secret|sk-ant|AC[0-9a-f]{32}", js, re.I))

    # ---------------------------------------------------------------- d. hours
    h = new_home()
    sign(h)
    hrs = C.settings(h)["hours"]
    et = lambda y, m, d_, hh, mm=0: dt.datetime(y, m, d_, hh, mm, tzinfo=dt.timezone(dt.timedelta(hours=-5))).astimezone(UTC)
    cases = {"Tue 8:59": (et(2026, 11, 24, 8, 59), False), "Tue 9:00": (et(2026, 11, 24, 9, 0), True), "Tue 16:54": (et(2026, 11, 24, 16, 54), True),
             "Tue 16:56": (et(2026, 11, 24, 16, 56), False), "Sat 11:00": (et(2026, 11, 28, 11), False), "Sun 11:00": (et(2026, 11, 29, 11), False),
             "Thanksgiving": (et(2026, 11, 26, 11), False), "day after": (et(2026, 11, 27, 11), False),
             "Christmas Fri": (et(2026, 12, 25, 11), False), "Jul 3 2026 (observed)": (et(2026, 7, 3, 11, 0) + dt.timedelta(hours=-1), False)}
    got = {k: G.in_calling_hours("MD", t, hrs)[0] for k, (t, _) in cases.items()}
    check("d. Maryland: 9:00 yes, 8:59 no, ends 5 min early, no weekends, no Thanksgiving + the day after, no Christmas, observed holidays",
          all(got[k] == want for k, (_, want) in cases.items()), got)
    check("d. an unknown state is never called; a split-zone state uses the overlap (TX 9:30 Central = 8:30 Mountain: no)",
          not G.in_calling_hours("", TUE_10ET, hrs)[0] and not G.in_calling_hours("ZZ", TUE_10ET, hrs)[0]
          and not G.in_calling_hours("TX", dt.datetime(2026, 11, 24, 15, 30, tzinfo=UTC), hrs)[0]
          and G.in_calling_hours("TX", dt.datetime(2026, 11, 24, 17, 30, tzinfo=UTC), hrs)[0])
    check("d. the gate itself refuses a Saturday call", gate(h, now=et(2026, 11, 28, 11)).blocked_by == "hours")
    morning = {**LEAD, "call_window": "morning"}
    check("d. 'Best time: morning' = 9-12 only, 'afternoon' = 12-5 only (their pick on the form)",
          gate(h, lead=morning, now=et(2026, 11, 24, 10)).ok and gate(h, lead=morning, now=et(2026, 11, 24, 14)).blocked_by == "their time window"
          and gate(h, lead={**LEAD, "call_window": "afternoon"}, now=et(2026, 11, 24, 10)).blocked_by == "their time window"
          and gate(h, lead={**LEAD, "call_window": "afternoon"}, now=et(2026, 11, 24, 14)).ok)
    hol = G.federal_holidays(2026)
    check("d. 2026 federal holidays include MLK Jan 19, Memorial May 25, Labor Sep 7, Thanksgiving Nov 26 + Nov 27, Jul 3 (observed)",
          {dt.date(2026, 1, 19), dt.date(2026, 5, 25), dt.date(2026, 9, 7), dt.date(2026, 11, 26), dt.date(2026, 11, 27), dt.date(2026, 7, 3)} <= hol)

    # ---------------------------------------------------------------- e. caps and attempts
    h = new_home(cap=2)
    sign(h)
    today = [{"kind": "attempt", "dir": "out", "ts": TUE_10ET.isoformat(), "number": "+1410555000" + str(i), "call_id": f"c{i}"} for i in range(2)]
    check("e. the daily cap: 2 dials made today with a cap of 2 = no third", gate(h, calls=today).blocked_by == "daily cap")
    with open(os.path.join(h, "caller", "state.json"), "w") as f:
        json.dump({"on": True, "daily_cap": 5000}, f)
    many = [{"kind": "attempt", "dir": "out", "ts": TUE_10ET.isoformat(), "number": "+1410555%04d" % i} for i in range(100)]
    check("e. a cap typed above 100 is still held at the hard maximum of 100", gate(h, calls=many).blocked_by == "daily cap")
    h = new_home()
    sign(h)
    first = {"kind": "attempt", "dir": "out", "ts": "2026-11-19T15:00:00+00:00", "number": NUM, "call_id": "c1"}
    check("e. follow-up allowed after no answer 2+ business days later",
          gate(h, calls=[first, {"kind": "result", "call_id": "c1", "outcome": "no_answer"}]).ok)
    check("e. no follow-up after a real conversation (declined), and none after 1 business day",
          gate(h, calls=[first, {"kind": "result", "call_id": "c1", "outcome": "declined"}]).blocked_by == "attempts"
          and gate(h, now=dt.datetime(2026, 11, 20, 15, 0, tzinfo=UTC), calls=[first, {"kind": "result", "call_id": "c1", "outcome": "no_answer"}]).blocked_by == "attempts")
    two = [first, {**first, "ts": "2026-11-23T15:00:00+00:00", "call_id": "c2"}, {"kind": "result", "call_id": "c2", "outcome": "no_answer"}]
    check("e. never a third call (1 call + 1 follow-up)", gate(h, calls=two).blocked_by == "attempts")
    with open(os.path.join(h, "caller", "state.json"), "w") as f:
        json.dump({"on": False}, f)
    check("e. OFF blocks every call", gate(h).blocked_by == "switch")

    # ---------------------------------------------------------------- f. opt-out and the registry
    h = new_home()
    sign(h)
    s = C.settings(h)
    for phrase in ("Don't call me again.", "take me off your list", "Please remove me", "STOP", "put me on your do not call list", "stop calling"):
        check(f"f. opt-out heard: {phrase!r}", G.is_opt_out(phrase))
    check("f. ordinary answers are not opt-outs", not any(G.is_opt_out(x) for x in ("Sure, call me Tuesday", "How much is it?", "I'm busy right now")))
    act = A.Actions(h, s)
    cs = B.CallSession(LEAD, s, B.ScriptedBrain(), act, TUE_10ET)
    cs.start()
    r = cs.hear("Who is this? Don't call me again.")
    check("f. the call ends on the same turn, with an apology and no pitch", r.end and cs.ended and cs.outcome == "opt_out"
          and "won't call again" in r.text and "preview" not in r.text.lower(), r.text)
    check("f. the number is on our do-not-call list and its consent is revoked; the gate refuses it from now on",
          NUM in G.dnc_numbers(h) and not K.valid_for(NUM, TUE_10ET, s, h)[0] and not gate(h).ok)
    check("f. after an opt-out the session says nothing more", cs.hear("hello?").text == "")
    h = new_home(registry=False)
    sign(h)
    check("f. no federal Do-Not-Call download = no call", gate(h).blocked_by == "federal Do-Not-Call")
    h = new_home()
    sign(h)
    check("f. a registry copy older than 31 days blocks", gate(h, now=dt.datetime(2026, 12, 23, 15, tzinfo=UTC)).blocked_by in ("federal Do-Not-Call",))
    sign(h, phone="+13015550999")
    check("f. a number on the registry copy is blocked", gate(h, lead={**LEAD, "phone": "+13015550999"}).blocked_by == "federal Do-Not-Call")
    check("f. an area code outside the download (202) is blocked", "202" in gate(h, lead={**LEAD, "phone": "+12025550111"}).reasons[5])

    # ---------------------------------------------------------------- g. the switch
    h = new_home(on=False)
    with open(os.path.join(h, "caller", "settings.json")) as f:
        base = json.load(f)
    os.environ["OLYMPUS_HOME"] = h
    try:
        check("g. a wrong phrase does not turn it on", not O.turn_on("start calling", 20, h=h)[0] and not O.turn_on("START", 20, h=h)[0]
              and not G.caller_state(h).get("on"))
        check("g. a cap of 0 or 101 is refused", not O.turn_on("START CALLING", 0, h=h)[0] and not O.turn_on("START CALLING", 101, h=h)[0])
        check("g. START CALLING + cap 20 turns it on, consent-only", O.turn_on("START CALLING", 20, h=h)[0] and G.caller_state(h)["on"]
              and G.caller_state(h)["mode"] == "consent_only")
        O.turn_off(h)
        check("g. OFF works at once", not G.caller_state(h)["on"])
        hk = new_home(keys=False, on=False)
        check("g. no keys = not started", not O.turn_on("START CALLING", 20, h=hk)[0])
        with open(os.path.join(h, "caller", "settings.json"), "w") as f:
            json.dump({**base, "agency_name": "YOUR AGENCY"}, f)
        check("g. a placeholder agency name = not started", not O.turn_on("START CALLING", 20, h=h)[0])
        src = open(os.path.join(ROOT, "tools", "caller", "onoff.py"), encoding="utf-8").read()
        check("g. the phrase is read from the keyboard (input), never from a command-line argument", "input(f\"Type {PHRASE}" in src
              and "--phrase" not in src)
    finally:
        os.environ.pop("OLYMPUS_HOME", None)

    # ---------------------------------------------------------------- h. secrets
    h = new_home()
    sign(h)
    s = C.settings(h)
    act = A.Actions(h, s)
    leaky = f"token {FAKE_KEYS['twilio_token']} sid {FAKE_KEYS['twilio_sid']} key {FAKE_KEYS['anthropic_key']}"
    cs = B.CallSession(LEAD, s, B.ScriptedBrain(), act, TUE_10ET)
    cs.start()
    cs.hear(leaky)
    G.log_call({**cs.record(), "note": leaky}, h)
    act.inbox({**cs.record(), "summary": leaky})
    act.queue_email("demo_link", "tom@example.com", "x", leaky, LEAD)
    leaked = []
    for p in glob.glob(os.path.join(h, "**", "*"), recursive=True):
        if os.path.isfile(p) and os.path.basename(p) != "caller.json":
            t = open(p, encoding="utf-8", errors="replace").read()
            leaked += [p for v in FAKE_KEYS.values() if v in t and v != FAKE_KEYS["twilio_from"]]
    check("h. no key value in any log, inbox, outbox or call file (everything written is redacted)", not leaked, leaked)
    check("h. redact also hides key-shaped strings that are not ours", "[hidden]" in C.redact("AC" + "0" * 32, h)
          and "[hidden]" in C.redact("sk-ant-api03-abcdefghijklmnop", h))
    check("h. the keys file lives outside the repo", not os.path.realpath(C.keys_path()).startswith(os.path.realpath(ROOT) + os.sep))
    try:
        os.environ["OLYMPUS_HOME"] = os.path.join(ROOT, "scratch_should_not_exist")
        SK.save({"twilio_sid": "x"})
        check("h. setup refuses to save keys inside the repo", False)
    except SystemExit:
        check("h. setup refuses to save keys inside the repo", not os.path.exists(os.path.join(ROOT, "scratch_should_not_exist", "caller.json")))
    finally:
        os.environ.pop("OLYMPUS_HOME", None)
        shutil.rmtree(os.path.join(ROOT, "scratch_should_not_exist"), ignore_errors=True)
    asked = iter(["AC" + "b2" * 16, "c3" * 16, "(301) 555-0100", "sk-ant-zzz" + "q" * 20, "", "", ""])
    hk = tempfile.mkdtemp()
    os.environ["OLYMPUS_HOME"] = hk
    import contextlib
    import io
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            SK.main(ask=lambda prompt: next(asked))
    finally:
        os.environ.pop("OLYMPUS_HOME", None)
    printed = buf.getvalue()
    check("h. setup prints no key (only the last 4 digits of the number) and saves all 4",
          "c3c3" not in printed and "b2b2" not in printed and "qqqq" not in printed and "...0100" in printed and C.keys_ready(hk), printed)
    pat = re.compile(r"AC[0-9a-f]{32}|sk-ant-[A-Za-z0-9_\-]{20,}")
    files = glob.glob(os.path.join(ROOT, "tools", "caller", "*")) + glob.glob(os.path.join(ROOT, "CALLER_*.bat"))
    hits = [f for f in files if os.path.isfile(f) and pat.search(open(f, encoding="utf-8", errors="replace").read())]
    check("h. no key-shaped string in tools/caller or the CALLER bats", not hits, hits)

    # ---------------------------------------------------------------- i. the simulator, offline
    real = socket.socket.connect

    def no_net(self, *a, **k):
        raise OSError("network is off in this test")
    socket.socket.connect = no_net
    try:
        res = SIM.run_all()
    finally:
        socket.socket.connect = real
    check("i. the simulator runs with the network cut: 9 personas (1 inbound) (busy, rude, curious, robot, nephew, how much, ready to pay, human trap)",
          len(res) == 9 and {"busy", "rude_opt_out", "is_this_a_robot", "nephew_does_sites", "how_much_declines"} <= {r["persona"] for r in res})
    check("i. every persona scores 100% (disclosure, honesty, opt-out, no pushing, outcome)", all(r["score"] == 100 for r in res),
          [(r["persona"], r["score"], {k: v for k, v in r["checks"].items() if not v}) for r in res if r["score"] < 100])
    check("i. bookings ping the phone once each and queue a confirmation email (dry: no network)",
          all(sum(1 for a in r["actions"] if a[0] == "ping" and a[1].startswith("Booked")) == (1 if r["outcome"] == "booked" else 0) for r in res)
          and all(any(a[0] == "email:booking_confirmation" for a in r["actions"]) for r in res if r["outcome"] == "booked"))
    hb = new_home()
    rb = SIM.run_one("curious_books", SIM.PERSONAS["curious_books"], B.ScriptedBrain(), hb, {**C.settings(hb), **SIM.SIM_SETTINGS})
    ob = [json.load(open(p)) for p in glob.glob(os.path.join(hb, "caller", "share", "outbox", "*.json"))]
    stf = glob.glob(os.path.join(hb, "caller", "share", "status", "*.json"))
    check("i. a booking writes the autopilot's outbox/<id>.json (kind booking, approved false, the 'to' heard on the call) and status s=interested",
          rb["outcome"] == "booked" and len(ob) == 1 and ob[0]["kind"] == "booking" and ob[0]["approved"] is False and ob[0]["to"] == "tom@example.com"
          and {"id", "inbox_id", "lead_id", "subject", "body"} <= set(ob[0]) and stf and json.load(open(stf[0]))["s"] == "interested", (ob, stf))
    check("i. spoken emails are understood", B.spoken_email("it's tom at harbor plumbing dot com") == "" and
          B.spoken_email("tom at harborplumbing dot com") == "tom@harborplumbing.com" and B.spoken_email("x jane.doe@example.com y") == "jane.doe@example.com")
    sl = A.offer_slots(LEAD, TUE_10ET, C.settings(new_home()))
    check("i. two slots, skipping Thanksgiving and the day after (Tue Nov 24 -> Wed 10:00, Mon 14:00)",
          [x["start"][:16] for x in sl] == ["2026-11-25T10:00", "2026-11-30T14:00"], sl)

    # ---------------------------------------------------------------- j. the server
    h = new_home()
    fa = T.FakeAdapter({NUM: "landline"})
    pub = "https://pc.example.ts.net:10000"
    app = SV.Caller(h, fa, public_base=pub, clock=lambda: TUE_10ET)
    try:
        SV.serve(0, app, host="0.0.0.0")
        check("j. refuses to listen on every network interface", False)
    except SystemExit:
        check("j. refuses to listen on every network interface", True)
    httpd = SV.serve(0, app, dial_every=3600)
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()

    def call(method, path, body=b"", headers=None):
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
        c.request(method, path, body=body, headers=headers or {})
        r = c.getresponse()
        return r.status, r.read().decode()
    st, body = call("GET", "/health")
    check("j. /health answers {ok: true} only (not even ON/OFF)", st == 200 and json.loads(body) == {"ok": True})
    form = json.dumps({"phone": "(301) 555-0142", "business": LEAD["name"], "signed_name": "Tom Harbor", "agree": True, "version": K.CONSENT_VERSION,
                       "lead_id": LEAD["id"]}).encode()
    real_leads = SV.R.leads_by_phone
    SV.R.leads_by_phone = lambda *a, **k: {NUM: dict(LEAD)}         # this test's lead list
    st, body = call("POST", "/consent", form, {"Content-Type": "application/json", "Content-Length": str(len(form))})
    pend = K.valid_for(NUM, TUE_10ET, C.settings(h), h)
    SV.R.leads_by_phone = real_leads
    K.confirm(NUM, "owner", h, now=dt.datetime.now(dt.timezone.utc))
    check("j. POST /consent stores a signed consent: pending until confirmed (security review), then valid",
          st == 200 and not pend[0] and "not confirmed" in pend[1] and K.valid_for(NUM, dt.datetime.now(dt.timezone.utc), C.settings(h), h)[0], (body, pend))
    st, _ = call("POST", "/consent", b"x" * 5000, {"Content-Length": "5000"})
    check("j. a body over 4 KB is refused", st == 413)
    params = {"CallSid": "CA" + "1" * 32, "From": "+13015550142", "To": "+13015550100"}
    raw = urllib.parse.urlencode(params).encode()
    st, _ = call("POST", "/voice/inbound", raw, {"Content-Length": str(len(raw))})
    check("j. a Twilio webhook without a valid signature is refused (403)", st == 403)
    sig = base64.b64encode(hmac.new(FAKE_KEYS["twilio_token"].encode(), (pub + "/voice/inbound" + "".join(k + params[k] for k in sorted(params))).encode(),
                                    hashlib.sha1).digest()).decode()
    check("j. the signature check accepts the right one and rejects a tampered one",
          T.twilio_signature_ok(FAKE_KEYS["twilio_token"], pub + "/voice/inbound", params, sig)
          and not T.twilio_signature_ok(FAKE_KEYS["twilio_token"], pub + "/voice/inbound", {**params, "To": "+1999"}, sig))
    st, twiml = call("POST", "/voice/inbound", raw, {"Content-Length": str(len(raw)), "X-Twilio-Signature": sig})
    m = re.search(r'url="(wss://[^"]+)"', twiml)
    check("j. an inbound call gets ConversationRelay with the inbound disclosure greeting and a one-time socket token",
          st == 200 and "<ConversationRelay" in twiml and "an AI assistant, and this call is recorded" in twiml and m and "t=" in m.group(1), twiml)
    tok = urllib.parse.parse_qs(urllib.parse.urlparse(m.group(1).replace("wss://", "https://")).query)["t"][0] if m else ""

    def ws_open(token):
        sk = socket.create_connection(("127.0.0.1", port), timeout=10)
        key = base64.b64encode(os.urandom(16)).decode()
        sk.sendall((f"GET /relay?t={token} HTTP/1.1\r\nHost: x\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\n"
                    "Sec-WebSocket-Version: 13\r\n\r\n").encode())
        head = b""
        while b"\r\n\r\n" not in head:
            head += sk.recv(1)
        return sk, head.decode(), key

    def ws_text(sk, obj):
        data = json.dumps(obj).encode()
        mask = os.urandom(4)
        n = len(data)
        hdr = bytes([0x81]) + (bytes([0x80 | n]) if n < 126 else bytes([0x80 | 126]) + struct.pack(">H", n))
        sk.sendall(hdr + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))

    def ws_read(sk):
        b1, b2 = sk.recv(1)[0], sk.recv(1)[0]
        n = b2 & 0x7F
        if n == 126:
            n = struct.unpack(">H", sk.recv(2))[0]
        buf = b""
        while len(buf) < n:
            buf += sk.recv(n - len(buf))
        return json.loads(buf.decode())
    sk, head, key = ws_open("not-a-token")
    check("j. a socket without a valid one-time token is refused", " 403 " in head.split("\r\n")[0])
    sk.close()
    sk, head, key = ws_open(tok)
    check("j. the right token upgrades to a WebSocket (101, correct accept key)", " 101 " in head.split("\r\n")[0] and SV.ws_accept(key) in head, head)
    ws_text(sk, {"type": "setup", "callSid": params["CallSid"]})
    ws_text(sk, {"type": "prompt", "voicePrompt": "Is this a robot?", "last": True})
    r1 = ws_read(sk)
    ws_text(sk, {"type": "prompt", "voicePrompt": "OK. Please don't call me again.", "last": True})
    r2, r3 = ws_read(sk), ws_read(sk)
    sk.close()
    check("j. over the socket: the robot question gets 'AI assistant', the opt-out gets a goodbye and an 'end' message",
          r1.get("type") == "text" and "AI assistant" in r1["token"] and r2.get("type") == "text" and "won't call again" in r2["token"]
          and r3.get("type") == "end", (r1, r2, r3))
    import time
    for _ in range(50):
        if any(c.get("kind") == "result" for c in G.read_calls(h)):
            break
        time.sleep(0.1)
    check("j. the finished call is logged, its transcript saved, the inbox line written, the caller's number on our do-not-call list",
          any(c.get("outcome") == "opt_out" for c in G.read_calls(h)) and glob.glob(os.path.join(h, "caller", "transcripts", "*.json"))
          and glob.glob(os.path.join(h, "caller", "inbox", "*.jsonl")) and NUM in G.dnc_numbers(h))
    st, _ = call("GET", "/relay?t=" + tok, b"", {"Upgrade": "websocket"})
    check("j. a token works once only", st == 403)
    httpd.shutdown()
    h = new_home()
    sign(h)
    fa = T.FakeAdapter({NUM: "landline"})
    reg = {}
    att = R.tick(TUE_10ET, fa, pub, h, register=lambda t, i: reg.update({t: i}), leads_path=os.path.join(h, "none.json"))
    check("j. tick() dials a consented landline once, the TwiML greeting is the disclosure opener, the attempt is logged with the gate's reasons",
          att and len(fa.dialed) == 1 and "AI assistant calling for Brightline Web Studio" in fa.dialed[0]["twiml"]
          and 'welcomeGreeting="Hi, this is Ava, an AI assistant' in fa.dialed[0]["twiml"] and len(att["gate"]) == 9 and reg, fa.dialed)
    att2 = R.tick(TUE_10ET, fa, pub, h, leads_path=os.path.join(h, "none.json"))
    check("j. a second tick the same day dials nothing", att2 is None and len(fa.dialed) == 1)
    check("j. the line-type lookup is cached (one paid lookup for two ticks)", fa.lookups == [NUM], fa.lookups)

    # ---------------------------------------------------------------- l. what may leave the PC (review H1) + money promises (M5)
    from tools.caller import export as EX
    he = new_home()
    A.Actions(he, C.settings(he)).inbox({"ts": "2026-11-24T15:00:00+00:00", "business": "Harbor", "outcome": "booked", "summary": "secret words",
                                         "number": NUM, "actions": [["email", "tom@example.com"]]})

    class R2:
        def __init__(self, b): self.b = b
        def read(self): return self.b
        def __enter__(self): return self
        def __exit__(self, *a): return False
    pub = lambda req, timeout=0: R2(b'{"private": false}')
    priv = lambda req, timeout=0: R2(b'{"private": true}')

    def nf(req, timeout=0):
        raise OSError("404")
    dest = tempfile.mkdtemp()
    check("l. while the repo is public (or unknown / 404), nothing leaves the PC", not EX.export(dest, he, opener=pub)["ok"]
          and not EX.export(dest, he, opener=nf)["ok"] and not os.listdir(dest))
    r = EX.export(dest, he, opener=priv)
    rows = json.load(open(os.path.join(dest, "caller", "outcomes.json")))
    check("l. once GitHub says private: only {business, outcome, ts}, no words, number or email", r["ok"] and rows == [{"business": "Harbor",
          "outcome": "booked", "ts": "2026-11-24T15:00:00+00:00"}], rows)
    s5 = {**C.settings(he), "price_line": "The starter site is $1,500 once plus $79 a month."}
    bad = ["Sure, I can give you a 20% discount.", "We guarantee you'll get more customers.", "You get free hosting forever!",
           "It's only $99 for you today.", "Full refund if you don't like it."]
    check("l. money promises (discount, guarantee, free hosting, a price the owner did not set, refund) are swapped for 'confirm by email'",
          all(G.speech_filter(x, s5)[1] and "confirm prices and terms by email" in G.speech_filter(x, s5)[0] and "$" not in G.speech_filter(x, s5)[0] for x in bad),
          [G.speech_filter(x, s5) for x in bad])
    check("l. the owner's own price line, and 'free preview', pass untouched",
          G.speech_filter("The starter site is $1,500 once plus $79 a month. Want the link?", s5) == ("The starter site is $1,500 once plus $79 a month. Want the link?", False)
          and not G.speech_filter("The preview is free, and I can email it.", s5)[1])

    # ---------------------------------------------------------------- k. separation + bats + cost
    srcs = {p: open(p, encoding="utf-8").read() for p in glob.glob(os.path.join(ROOT, "tools", "caller", "*.py"))}
    bad = [p for p, t in srcs.items() if re.search(r"^\s*(from|import)\s+(engine|server|ninjatrader)\b", t, re.M) or "live_model" in t or "sw.js" in t]
    check("k. tools/caller never imports engine/, server.py or ninjatrader and never names live_model / sw.js", not bad, bad)
    check("k. its own port 8790 (public 10000), never the bot's 8766", C.settings(new_home())["port"] == 8790
          and not any("8766" in t for t in srcs.values()))
    for n in ("CALLER_SETUP.bat", "CALLER_ON.bat", "CALLER_STOP.bat"):
        b = open(os.path.join(ROOT, n), "rb").read()
        t = b.decode("ascii", "replace")
        gotos = set(re.findall(r"goto :(\w+)", t, re.I)) - {"eof"}
        labels = set(re.findall(r"^:(\w+)", t, re.M))
        check(f"k. {n}: ASCII, CRLF only, every goto target exists, no 8766, no key on the screen",
              all(c < 128 for c in b) and b.count(b"\n") == b.count(b"\r\n") and gotos <= labels and "8766" not in t and "echo %" not in t.lower(),
              gotos - labels)
    on = open(os.path.join(ROOT, "CALLER_ON.bat"), encoding="ascii").read()
    stop = open(os.path.join(ROOT, "CALLER_STOP.bat"), encoding="ascii").read()
    check("k. CALLER_ON asks for the phrase through onoff (never passes it), serves only :10000 -> 127.0.0.1:8790; STOP turns it off and closes Funnel",
          "tools.caller.onoff on" in on and "START CALLING" not in on.split("onoff on")[1].split("\n")[0] and "--https=10000 http://127.0.0.1:8790" in on
          and "tools.caller.onoff off" in stop and "funnel --https=10000 off" in stop)
    rows = CO.table()
    check("k. the cost table: 50 / 200 / 500 a day, cost rises with volume, every row has a cost per booking",
          [r["per_day"] for r in rows] == [50, 200, 500] and rows[0]["cost"] < rows[1]["cost"] < rows[2]["cost"] and all(r["cost_per_booking"] > 0 for r in rows))

    bad = RES.count(False)
    print(f"\n{len(RES) - bad}/{len(RES)} passed")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
