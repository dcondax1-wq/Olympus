"""SIGNED CONSENT: the only way an outbound AI call is ever allowed.

Maryland (Com. Law 14-4501(d)) and the FCC (47 CFR 64.1200(f)(9)) want a written agreement that bears the called party's signature, names
the number, clearly authorises an artificial voice / automated dialing, and says agreeing is not a condition of buying. E-SIGN lets a web
form with a typed name + a tap be that signature (FCC 2012 TCPA order, 77 FR 34233). The form lives on each demo site (consent_form_html),
posts to the caller server's POST /consent, and is stored here append-only (<home>/caller/consent.jsonl); a revoke is a new line.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import html
import json
import os
import re
import uuid

try:
    from . import compliance as G
    from . import config as C
except ImportError:  # pragma: no cover
    import compliance as G  # type: ignore
    import config as C  # type: ignore

CONSENT_VERSION = "v2-2026-11-20"
BUTTON = "Have our assistant call me"
WINDOWS = {"morning": (9, 12), "afternoon": (12, 17), "any": (9, 17)}
CONSENT_TEXT = (
    "By typing my name and tapping \"Have our assistant call me\", I agree that {agency} may call me at {phone} using an AI assistant "
    "(an artificial voice) and an automated dialing system, to talk about the website preview it made for {business}. "
    "The call is recorded and transcribed. I do not have to agree to this to buy anything. "
    "I can say \"stop\" on the call, or email or call {callback} at any time, and you will never call again."
)


def text_for(s: dict, phone: str, business: str) -> str:
    return CONSENT_TEXT.format(agency=s.get("agency_name", ""), phone=phone, business=business or "my business",
                               callback=s.get("callback_number", ""))


def _path(h=None):
    return os.path.join(C.state_dir(h), "consent.jsonl")


def _all(h=None) -> list:
    out = []
    try:
        with open(_path(h), encoding="utf-8") as f:
            for line in f:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    pass
    except OSError:
        pass
    return out


def record(form: dict, s: dict, h=None, now: dt.datetime | None = None, ip: str = "", ua: str = "") -> tuple:
    """(ok, message, rec). form = {phone, business, signed_name, email?, lead_id?, agree: true, version}. Refuses anything incomplete."""
    now = now or dt.datetime.now(dt.timezone.utc)
    num = G.e164(form.get("phone", ""))
    name = re.sub(r"\s+", " ", str(form.get("signed_name", ""))).strip()[:80]
    biz = re.sub(r"\s+", " ", str(form.get("business", ""))).strip()[:120]
    if not num:
        return False, "That does not look like a US phone number.", None
    if form.get("agree") is not True:
        return False, "Please tick the box to agree.", None
    if len(name) < 3 or not re.search(r"[A-Za-z]{2,}", name):
        return False, "Please type your full name as your signature.", None
    if form.get("version") != CONSENT_VERSION:
        return False, "This form is out of date; please reload the page.", None
    window = str(form.get("window") or "any")
    if window not in WINDOWS:
        return False, "Please pick a time that suits you.", None
    text = text_for(s, "the number I type below", "my business") + f" (Number typed: {num}. Business: {biz or 'not given'}.)"   # what they saw + what they typed
    rec = {"id": uuid.uuid4().hex[:12], "kind": "consent", "phone": num, "business": biz, "signed_name": name,
           "email": str(form.get("email", ""))[:120], "lead_id": str(form.get("lead_id", ""))[:40], "version": CONSENT_VERSION,
           "window": window, "asked_t": now.isoformat(), "phone_source": "their form",
           "text_sha256": hashlib.sha256(text.encode()).hexdigest(), "text": text, "ts": now.isoformat(), "ip": ip[:64], "ua": ua[:200]}
    with open(_path(h), "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, sort_keys=True) + "\n")
    share(rec, h)
    return True, "Thank you. Our AI assistant will call you on a weekday between 9 and 5.", rec


def share(rec: dict, h=None) -> str:
    """The copy the PC pushes to the private 'agency-inbox' branch as caller/consent/<id>.json, so the email autopilot stops the email
    sequence for this lead. No phone, no name, no email in it: only what the autopilot needs."""
    d = os.path.join(C.state_dir(h), "share", "consent")
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, f"{rec['id']}.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump({k: rec.get(k, "") for k in ("id", "lead_id", "business", "asked_t", "window", "phone_source", "version")}, f, sort_keys=True)
    return p


def revoke(phone: str, why: str, h=None, now: dt.datetime | None = None) -> None:
    num = G.e164(phone)
    if not num:
        return
    with open(_path(h), "a", encoding="utf-8") as f:
        f.write(json.dumps({"kind": "revoke", "phone": num, "why": why[:80], "ts": (now or dt.datetime.now(dt.timezone.utc)).isoformat()}) + "\n")


def valid_for(phone: str, now: dt.datetime, s: dict, h=None) -> tuple:
    """(ok, why): the newest consent for exactly this number, not revoked after it, current wording, not older than consent_max_age_days."""
    num = G.e164(phone)
    rows = [r for r in _all(h) if r.get("phone") == num]
    if not rows:
        return False, "no signed consent for this number (cold calls are not allowed: Md. Com. Law 14-4502(a)(3))"
    last_consent = max((r for r in rows if r.get("kind") == "consent"), key=lambda r: r["ts"], default=None)
    last_revoke = max((r for r in rows if r.get("kind") == "revoke"), key=lambda r: r["ts"], default=None)
    if not last_consent:
        return False, "consent was revoked"
    if last_revoke and last_revoke["ts"] >= last_consent["ts"]:
        return False, "consent was revoked"
    if last_consent.get("version") != CONSENT_VERSION:
        return False, "consent was given on an old form wording"
    if last_consent.get("text_sha256") != hashlib.sha256(str(last_consent.get("text", "")).encode()).hexdigest():
        return False, "consent record does not match its text"
    age = (now - dt.datetime.fromisoformat(last_consent["ts"])).days
    if age > int(s["limits"]["consent_max_age_days"]):
        return False, f"consent is {age} days old"
    return True, f"signed by {last_consent['signed_name']} on {last_consent['ts'][:10]}"


def consented_numbers(h=None) -> list:
    """The newest consent record per number (for the dialer's queue)."""
    best = {}
    for r in _all(h):
        if r.get("kind") == "consent":
            if r["phone"] not in best or r["ts"] > best[r["phone"]]["ts"]:
                best[r["phone"]] = r
    return list(best.values())


def consent_form_html(s: dict, lead: dict | None, post_url: str) -> str:
    """The block for the concept page's caller slot (day-cities3: tools/site_factory_agency.json "caller_html"). Inline HTML + JS only,
    no third party, no secret. The site factory fills the hidden inputs lead_id and business per site (empty here when lead is None).
    It posts JSON to <post_url> (the caller's public Funnel address + /consent)."""
    e = html.escape
    lead = lead or {}
    sample = text_for(s, "the number I type below", "my business")
    return f"""<form id="callme" class="callme" data-version="{CONSENT_VERSION}" data-post="{e(post_url)}">
<p class="callme-lede">Our AI assistant can call your business line on a weekday between 9 and 5 to answer questions and book a short call with {e(s.get('owner_first_name', 'us'))}. Or call us yourself: {e(s.get('callback_number', ''))}.</p>
<label>Business phone <input name="phone" type="tel" required autocomplete="tel" inputmode="tel"></label>
<label>Your full name (your signature) <input name="signed_name" required autocomplete="name"></label>
<label>Best time <select name="window"><option value="any">Any time 9-5</option><option value="morning">Morning (9-12)</option><option value="afternoon">Afternoon (12-5)</option></select></label>
<label>Email (optional) <input name="email" type="email" autocomplete="email"></label>
<input type="hidden" name="lead_id" value="{e(lead.get('id', ''))}"><input type="hidden" name="business" value="{e(lead.get('name', ''))}">
<label class="callme-agree"><input type="checkbox" name="agree" required> <span>{e(sample)}</span></label>
<button type="submit">{BUTTON}</button>
<p class="callme-out" role="status" aria-live="polite"></p>
</form>
<script>(function(){{var f=document.getElementById("callme");if(!f)return;f.addEventListener("submit",function(ev){{ev.preventDefault();var o=f.querySelector(".callme-out");
var b={{phone:f.phone.value,signed_name:f.signed_name.value,window:f.window.value,email:f.email.value,lead_id:f.lead_id.value,business:f.business.value,agree:f.agree.checked,version:f.dataset.version}};
o.textContent="Sending...";fetch(f.dataset.post,{{method:"POST",headers:{{"Content-Type":"application/json"}},body:JSON.stringify(b),referrerPolicy:"no-referrer"}})
.then(function(r){{return r.json()}}).then(function(j){{o.textContent=j.message;if(j.ok)f.querySelector("button").disabled=true}})
.catch(function(){{o.textContent="Could not send. Please call us instead."}});}});}})();</script>"""
