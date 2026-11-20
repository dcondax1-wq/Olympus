"""What a call can DO: offer 2 time slots, book one, queue the demo / confirmation / payment-link email, write the inbox, ping the phone.

Email: never sent from here. Each email is <home>/caller/share/outbox/<id>.json in the email autopilot's outbox format (day-a11y
docs/EMAIL_AUTOPILOT.md): {"id", "inbox_id", "lead_id", "kind": demo|booking|payment, "subject", "body", "approved": false} + "to"
(the address said on the call); the PC sends demo / booking / payment drafts by itself when every link is the owner's own.
Inbox: every finished call is one line in <home>/caller/inbox/<YYYY-MM-DD>.jsonl, the 'agency-inbox' branch record format.
Phone ping: one ntfy push per booking to the owner's PRIVATE topic (<home>/ntfy.json, the file the PC report uses). Read-only use of it.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import urllib.request
import uuid
from zoneinfo import ZoneInfo

try:
    from . import compliance as G
    from . import config as C
except ImportError:  # pragma: no cover
    import compliance as G  # type: ignore
    import config as C  # type: ignore


OUTBOX_KIND = {"demo_link": "demo", "booking_confirmation": "booking", "payment_link": "payment"}
STATUS_S = {"booked": "interested", "payment_link": "interested", "demo_sent": "called", "callback_requested": "called",
            "connected": "called", "declined": "no", "opt_out": "no"}


EMAIL_RX = __import__("re").compile(r"[A-Za-z0-9._%+\-]{1,64}@[A-Za-z0-9\-]{1,63}(?:\.[A-Za-z0-9\-]{1,63})*\.[A-Za-z]{2,24}")


def valid_email(x) -> str:
    """ONE plain address or '' (security review 2026-11-20: a name, a comma list or a newline from the form or the model never
    reaches the email autopilot's To: line)."""
    t = str(x or "").strip()
    return t if len(t) <= 120 and EMAIL_RX.fullmatch(t) else ""


def lead_tz(lead: dict) -> ZoneInfo:
    return ZoneInfo((G.STATE_TZ.get(str(lead.get("state", "")).upper()) or ["America/New_York"])[0])


def offer_slots(lead: dict, now_utc: dt.datetime, s: dict) -> list:
    """Two slots: the first business day >= days_ahead_min at times_local[0], the next business day at times_local[1]."""
    tz = lead_tz(lead)
    loc = now_utc.astimezone(tz)
    times = list(s["slots"]["times_local"]) or ["10:00", "14:00"]
    out, d, ahead = [], loc.date(), 0
    while len(out) < 2 and ahead <= int(s["slots"]["days_ahead_max"]) + 7:
        d += dt.timedelta(days=1)
        ahead += 1
        if ahead < int(s["slots"]["days_ahead_min"]) or d.weekday() >= 5 or d in G.federal_holidays(d.year):
            continue
        hh, mm = times[min(len(out), len(times) - 1)].split(":")
        start = dt.datetime(d.year, d.month, d.day, int(hh), int(mm), tzinfo=tz)
        h12 = str(int(start.strftime("%I"))) + (start.strftime(":%M") if start.minute else "")     # no %-I: Windows has none
        out.append({"start": start.isoformat(), "say": f"{start:%A} at {h12} {'in the morning' if start.hour < 12 else 'in the afternoon'}",
                    "minutes": int(s["slots"]["length_min"])})
    return out


class Actions:
    """Side effects of a call. dry=True (simulator, tests) writes into the given home only and never touches the network."""

    def __init__(self, h: str | None, s: dict, dry: bool = True, http=None):
        self.h, self.s, self.dry = h, s, dry
        self._http = http or urllib.request.urlopen
        self.done = []     # [(kind, detail)] for the transcript / score

    def _append(self, rel: str, rec: dict):
        p = os.path.join(C.state_dir(self.h), rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "a", encoding="utf-8") as f:
            f.write(C.redact(json.dumps(rec, sort_keys=True), self.h) + "\n")

    def queue_email(self, kind: str, to: str, subject: str, body: str, lead: dict) -> dict:
        footer = (f"\n\n--\n{self.s.get('agency_name')} | {self.s.get('postal_address')} | {self.s.get('callback_number')}\n"
                  "Reply STOP or 'unsubscribe' and we will never email or call again.")
        to = valid_email(to)
        rec = {"id": "call-" + uuid.uuid4().hex[:12], "inbox_id": "", "lead_id": lead.get("id", ""), "kind": OUTBOX_KIND.get(kind, "other"),
               "subject": subject, "body": body + footer, "approved": False, "to": to, "from_app": "caller", "caller_kind": kind,
               "t": dt.datetime.now(dt.timezone.utc).isoformat()}
        if to:      # the email autopilot's outbox/<id>.json (day-a11y docs/EMAIL_AUTOPILOT.md); "to" is the address said on the call
            p = os.path.join(C.state_dir(self.h), "share", "outbox", rec["id"] + ".json")
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                f.write(C.redact(json.dumps(rec, sort_keys=True), self.h))
        self.done.append(("email:" + kind, to or "(no valid email yet)"))
        return rec

    def demo_url(self, lead: dict) -> str:
        return str(self.s.get("demo_url_pattern", "")).replace("{hash}", str(lead.get("site_hash") or lead.get("id", "")))

    def book(self, lead: dict, slot: dict, email: str) -> dict:
        rec = {"lead_id": lead.get("id", ""), "business": lead.get("name", ""), "phone": G.e164(lead.get("phone", "")), "slot": slot,
               "email": email, "ts": dt.datetime.now(dt.timezone.utc).isoformat()}
        self._append("bookings.jsonl", rec)
        self.queue_email("booking_confirmation", email, f"Your call with {self.s.get('agency_name')}: {slot['say']}",
                         f"Hi,\n\nThanks for talking with our AI assistant. You are booked for a {slot['minutes']}-minute call with "
                         f"{self.s.get('owner_first_name')} on {slot['say']} ({slot['start'][:16].replace('T', ' ')} your time).\n\n"
                         f"Your free website preview: {self.demo_url(lead)}\n\nNeed another time? Just reply to this email.", lead)
        self.done.append(("booked", slot["say"]))
        self.ping(f"Booked: {lead.get('name', 'a business')} {slot['say']} ({lead.get('town') or lead.get('city', '')})")
        return rec

    def send_payment_link(self, lead: dict, email: str) -> bool:
        link = str(self.s.get("payment_link") or "")
        if not link:
            self.done.append(("payment_link", "none set: the owner sends it"))
            return False
        self.queue_email("payment_link", email, f"Your website from {self.s.get('agency_name')}: the link to start",
                         f"Hi,\n\nHere is the secure link to start your site: {link}\n\nYour preview: {self.demo_url(lead)}\n\n"
                         "Nothing is charged until you finish the checkout page.", lead)
        self.ping(f"Payment link sent: {lead.get('name', 'a business')}")
        return True

    def send_demo(self, lead: dict, email: str):
        self.queue_email("demo_link", email, f"Your free website preview from {self.s.get('agency_name')}",
                         f"Hi,\n\nAs promised on the call, here is the preview we made for {lead.get('name', 'you')}: "
                         f"{self.demo_url(lead)}\n\nIf you like it, reply and we will make it yours.", lead)

    def opt_out(self, lead: dict, said: str):
        try:
            from . import consent as K
        except ImportError:  # pragma: no cover
            import consent as K  # type: ignore
        G.add_dnc(lead.get("phone", ""), "said: " + said[:60], self.h)
        K.revoke(lead.get("phone", ""), "opt-out on the call", self.h)
        self.done.append(("opt_out", "on our do-not-call list forever"))

    def inbox(self, rec: dict):
        day = str(rec.get("ts", dt.datetime.now(dt.timezone.utc).isoformat()))[:10]
        st = STATUS_S.get(rec.get("outcome", ""), "called")
        self._append(os.path.join("inbox", f"{day}.jsonl"), {"v": 1, "app": "caller", "s": st, **rec})
        if rec.get("lead_id"):     # the shared lead status (phone key agency.leads.status.v1): {lead_id: {s, t}}
            p = os.path.join(C.state_dir(self.h), "share", "status", f"{rec['lead_id']}.json")
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                json.dump({"lead_id": rec["lead_id"], "s": st, "t": rec.get("ts", ""), "outcome": rec.get("outcome", "")}, f)

    def ping(self, text: str):
        self.done.append(("ping", text))
        if self.dry:
            return
        c = C.read_json(os.path.join(self.h or C.home(), "ntfy.json"), {}) or {}
        topic = str(c.get("topic") or "").strip()
        if not topic or c.get("on", True) is False:
            return
        try:
            r = urllib.request.Request(str(c.get("ntfy") or "https://ntfy.sh").rstrip("/") + "/" + topic, data=text.encode()[:500],
                                       method="POST", headers={"Title": "Caller", "Tags": "telephone_receiver"})
            self._http(r, timeout=10).close()
        except Exception:
            pass
