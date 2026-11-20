"""The phone line behind one small interface, so the brain and the gate never know which carrier is underneath.

  Adapter.lookup(number)      -> "landline" | "mobile" | "voip" | "unknown"        (Twilio Lookup v2 Line Type Intelligence, $0.008)
  Adapter.dial(number, twiml) -> call id                                            (Twilio Calls API; machine detection on)
  Adapter.hangup(call id)

FakeAdapter is what the tests and the simulator use: no network, no money, every dial recorded in .dialed.
TwilioAdapter needs CALLER_SETUP.bat's keys and is only ever built by run.py / server.py after the gate said yes.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import urllib.parse
import urllib.request
from xml.sax.saxutils import quoteattr

LINE_TYPES = {"landline": "landline", "mobile": "mobile", "fixedVoip": "voip", "nonFixedVoip": "voip"}


class Adapter:
    name = "base"

    def lookup(self, number: str) -> str:
        raise NotImplementedError

    def dial(self, number: str, twiml: str, status_url: str = "") -> str:
        raise NotImplementedError

    def hangup(self, call_id: str) -> None:
        raise NotImplementedError


class FakeAdapter(Adapter):
    """Offline line. line_types = {"+1301...": "landline"}; anything not listed is 'unknown' (= never dialed)."""
    name = "fake"

    def __init__(self, line_types: dict | None = None):
        self.line_types = dict(line_types or {})
        self.dialed, self.lookups, self.hung = [], [], []

    def lookup(self, number):
        self.lookups.append(number)
        return self.line_types.get(number, "unknown")

    def dial(self, number, twiml, status_url=""):
        self.dialed.append({"number": number, "twiml": twiml, "status_url": status_url})
        return f"FAKE{len(self.dialed):04d}"

    def hangup(self, call_id):
        self.hung.append(call_id)


class TwilioAdapter(Adapter):
    name = "twilio"
    API = "https://api.twilio.com/2010-04-01"
    LOOKUP = "https://lookups.twilio.com/v2/PhoneNumbers/"

    def __init__(self, keys: dict, max_seconds: int = 300, opener=None):
        self._sid, self._tok, self._from = keys["twilio_sid"], keys["twilio_token"], keys["twilio_from"]
        self.max_seconds = int(max_seconds)
        self._open = opener or urllib.request.urlopen

    def _req(self, url, data=None, method="GET"):
        auth = base64.b64encode(f"{self._sid}:{self._tok}".encode()).decode()
        body = urllib.parse.urlencode(data).encode() if data is not None else None
        r = urllib.request.Request(url, data=body, method=method, headers={"Authorization": "Basic " + auth})
        with self._open(r, timeout=20) as resp:
            return json.loads(resp.read().decode() or "{}")

    def lookup(self, number):
        try:
            j = self._req(self.LOOKUP + urllib.parse.quote(number) + "?Fields=line_type_intelligence")
        except Exception:
            return "unknown"
        t = ((j or {}).get("line_type_intelligence") or {}).get("type") or ""
        return LINE_TYPES.get(t, "unknown")

    def dial(self, number, twiml, status_url=""):
        data = {"To": number, "From": self._from, "Twiml": twiml, "MachineDetection": "Enable", "Timeout": "25",
                "TimeLimit": str(self.max_seconds)}
        if status_url:
            data.update({"StatusCallback": status_url, "StatusCallbackEvent": "completed"})
        j = self._req(f"{self.API}/Accounts/{self._sid}/Calls.json", data, "POST")
        return str(j.get("sid", ""))

    def hangup(self, call_id):
        self._req(f"{self.API}/Accounts/{self._sid}/Calls/{call_id}.json", {"Status": "completed"}, "POST")

    def set_voice_url(self, url: str) -> bool:
        """Point the agency number's incoming calls at our /voice/inbound (so the owner never edits the Twilio console)."""
        q = urllib.parse.urlencode({"PhoneNumber": self._from})
        j = self._req(f"{self.API}/Accounts/{self._sid}/IncomingPhoneNumbers.json?{q}")
        nums = (j or {}).get("incoming_phone_numbers") or []
        if not nums:
            return False
        self._req(f"{self.API}/Accounts/{self._sid}/IncomingPhoneNumbers/{nums[0]['sid']}.json", {"VoiceUrl": url, "VoiceMethod": "POST"}, "POST")
        return True


def relay_twiml(ws_url: str, greeting: str, voice: dict) -> str:
    """<Connect><ConversationRelay>: Twilio turns speech into text for us and our text into speech. The greeting is the disclosure line."""
    attrs = {"url": ws_url, "welcomeGreeting": greeting, "welcomeGreetingInterruptible": "none", "interruptible": "speech",
             "language": voice.get("language", "en-US"), "ttsProvider": voice.get("tts_provider", "ElevenLabs"),
             "transcriptionProvider": voice.get("transcription_provider", "Deepgram"), "dtmfDetection": "true"}
    a = " ".join(f"{k}={quoteattr(str(v))}" for k, v in attrs.items())
    return f'<?xml version="1.0" encoding="UTF-8"?><Response><Connect><ConversationRelay {a} /></Connect></Response>'


def twilio_signature_ok(token: str, url: str, params: dict, signature: str) -> bool:
    """X-Twilio-Signature: base64(HMAC-SHA1(token, url + every POST key+value sorted by key)). Webhooks without it are refused."""
    if not token or not signature:
        return False
    base = url + "".join(k + str(params[k]) for k in sorted(params))
    want = base64.b64encode(hmac.new(token.encode(), base.encode(), hashlib.sha1).digest()).decode()
    return hmac.compare_digest(want, signature)
