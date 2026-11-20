"""THE COMPLIANCE GATE. Every outbound dial and every spoken line passes through here; nothing else may dial.

Outbound (consent_only mode, the only mode there is):
  1. the caller is ON (CALLER_ON.bat, typed phrase) and today's cap is not used up
  2. a valid SIGNED consent record for exactly this number (consent.py: not revoked, current wording, under 365 days old)
  3. the number is not on our own do-not-call list (forever) and not on the federal registry copy (area code downloaded, <= 31 days old)
  4. the line type is a business LANDLINE (Twilio Lookup); mobile, VoIP, toll-free, unknown = never
  5. Mon-Fri 9:00-17:00 in the business's own time zone (both zones for split states), never a federal holiday or the day after Thanksgiving
  6. at most 1 call + 1 follow-up per business; the follow-up only after no answer / busy / voicemail / "call me back", 2+ business days later
Spoken lines:
  - the opening line is built HERE, never by the model, and must say "AI assistant", the agency, and "recorded" in its first sentence
  - any reply that claims to be human is replaced before it is spoken
  - an opt-out phrase from the business ends the call and goes on the do-not-call list at once
Not legal advice: research/writeups/ai-caller-2026-11-20.md has the law and its sources.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
from dataclasses import dataclass, field
from zoneinfo import ZoneInfo

try:
    from . import config as C
except ImportError:  # pragma: no cover
    import config as C  # type: ignore

# ---------------------------------------------------------------- phone numbers

def e164(phone: str) -> str:
    """'(301) 663-5550' -> '+13016635550'; '' when it is not a 10-digit US/Canada number."""
    d = re.sub(r"\D", "", str(phone or ""))
    if len(d) == 11 and d.startswith("1"):
        d = d[1:]
    if len(d) != 10 or d[0] in "01" or d[3] in "01":
        return ""
    return "+1" + d


def area_code(phone: str) -> str:
    n = e164(phone)
    return n[2:5] if n else ""


# ---------------------------------------------------------------- time zones and holidays

_E, _C, _M, _P = "America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles"
STATE_TZ = {
    "MD": [_E], "DC": [_E], "VA": [_E], "DE": [_E], "PA": [_E], "WV": [_E], "NJ": [_E], "NY": [_E], "CT": [_E], "RI": [_E],
    "MA": [_E], "VT": [_E], "NH": [_E], "ME": [_E], "NC": [_E], "SC": [_E], "GA": [_E], "OH": [_E], "MI": [_E, _C],
    "FL": [_E, _C], "IN": [_E, _C], "KY": [_E, _C], "TN": [_E, _C], "AL": [_C], "MS": [_C], "LA": [_C], "AR": [_C],
    "MO": [_C], "IA": [_C], "MN": [_C], "WI": [_C], "IL": [_C], "OK": [_C], "KS": [_C, _M], "NE": [_C, _M],
    "SD": [_C, _M], "ND": [_C, _M], "TX": [_C, _M], "NM": [_M], "CO": [_M], "WY": [_M], "MT": [_M], "UT": [_M],
    "ID": [_M, _P], "AZ": ["America/Phoenix"], "NV": [_P], "CA": [_P], "OR": [_P, _M], "WA": [_P],
    "AK": ["America/Anchorage"], "HI": ["Pacific/Honolulu"],
}


def _nth_weekday(y, m, wd, n):
    d = dt.date(y, m, 1)
    d += dt.timedelta(days=(wd - d.weekday()) % 7)
    return d + dt.timedelta(weeks=n - 1)


def _last_weekday(y, m, wd):
    d = dt.date(y, m + 1, 1) - dt.timedelta(days=1) if m < 12 else dt.date(y, 12, 31)
    return d - dt.timedelta(days=(d.weekday() - wd) % 7)


def _observed(d: dt.date) -> dt.date:
    return d - dt.timedelta(days=1) if d.weekday() == 5 else (d + dt.timedelta(days=1) if d.weekday() == 6 else d)


def federal_holidays(y: int) -> set:
    fixed = [dt.date(y, 1, 1), dt.date(y, 6, 19), dt.date(y, 7, 4), dt.date(y, 11, 11), dt.date(y, 12, 25)]
    out = {_observed(d) for d in fixed}
    out |= {_nth_weekday(y, 1, 0, 3), _nth_weekday(y, 2, 0, 3), _last_weekday(y, 5, 0), _nth_weekday(y, 9, 0, 1), _nth_weekday(y, 10, 0, 2)}
    tg = _nth_weekday(y, 11, 3, 4)
    out |= {tg, tg + dt.timedelta(days=1)}          # Thanksgiving + the day after (our own rule)
    nxt = _observed(dt.date(y + 1, 1, 1))
    if nxt.year == y:
        out.add(nxt)
    return out


def _hm(s: str) -> int:
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def in_calling_hours(state: str, now_utc: dt.datetime, hours: dict) -> tuple:
    """(ok, why). Every time zone of the state must be inside the window (split states get the overlap)."""
    tzs = STATE_TZ.get(str(state or "").upper())
    if not tzs:
        return False, f"unknown state {state!r}: no time zone, no call"
    start, end = _hm(hours.get("start", "09:00")), _hm(hours.get("end", "17:00"))
    for tz in tzs:
        loc = now_utc.astimezone(ZoneInfo(tz))
        if hours.get("weekdays_only", True) and loc.weekday() >= 5:
            return False, f"weekend in {tz}"
        if hours.get("no_federal_holidays", True) and loc.date() in federal_holidays(loc.year):
            return False, f"federal holiday {loc.date()} in {tz}"
        mins = loc.hour * 60 + loc.minute
        if not (start <= mins < end - 5):           # leave 5 minutes so no call runs past the end
            return False, f"outside {hours.get('start')}-{hours.get('end')} local ({loc:%H:%M} {tz})"
    return True, "inside calling hours"


def business_days_between(a: dt.date, b: dt.date) -> int:
    n, d = 0, a
    while d < b:
        d += dt.timedelta(days=1)
        if d.weekday() < 5 and d not in federal_holidays(d.year):
            n += 1
    return n


# ---------------------------------------------------------------- spoken-line rules

AI_WORD = re.compile(r"\b(AI|A\.I\.|artificial intelligence|automated assistant)\b", re.I)
RECORDED = re.compile(r"\b(recorded|recording)\b", re.I)
HUMAN_CLAIM = re.compile(
    r"\b(i\s*am|i'?m|im)\s+(a\s+|an\s+)?(real\s+|actual\s+|live\s+)?(human|person|human being|woman|man|guy|lady)\b"
    r"|\bnot\s+(a\s+|an\s+)?(robot|bot|machine|ai|computer|recording)\b"
    r"|\b(real|live)\s+person\s+(here|speaking|calling)\b", re.I)
OPT_OUT = re.compile(
    r"\b(do\s*n[o']?t|don'?t|never|stop)\s+(call|calling|ring)(ing)?\b|\btake\s+(me|us|my\s+number|this\s+number)\s+off\b"
    r"|\bremove\s+(me|us|my|this|our)\b|\bput\s+(me|us)\s+on\s+(your|the)\s+do\s*not\s*call\b|\bdo\s*not\s*call\s+list\b"
    r"|\blose\s+(my|this|our)\s+number\b|\bunsubscribe\b|\bstop\s+contacting\b|\bnever\s+again\b|^\s*stop\s*[.!]*\s*$", re.I)


def first_sentence(text: str) -> str:
    m = re.match(r"\s*(.+?[.!?])(\s|$)", str(text or ""), re.S)
    return (m.group(1) if m else str(text or "")).strip()


def opening_line(s: dict, business: str = "", inbound: bool = False) -> str:
    """The disclosure-first opener, built in code (never by the model)."""
    agency, name = s.get("agency_name", "our agency"), s.get("assistant_name", "Ava")
    if inbound:
        return (f"Thanks for calling {agency}, I'm {name}, an AI assistant, and this call is recorded and transcribed. "
                f"How can I help you today?")
    who = f" Is this {business}?" if business else ""
    return (f"Hi, this is {name}, an AI assistant calling for {agency}, and this call is recorded and transcribed.{who} "
            f"You asked us to call about the free website preview we made for you, is now an OK time for two minutes?")


def check_disclosure(text: str, s: dict) -> tuple:
    """(ok, why): the FIRST sentence says AI, the agency name and that the call is recorded."""
    fs = first_sentence(text)
    miss = []
    if not AI_WORD.search(fs):
        miss.append("does not say it is an AI")
    if not RECORDED.search(fs):
        miss.append("does not say the call is recorded")
    agency = str(s.get("agency_name", "")).strip()
    if not agency or agency.upper().startswith("YOUR "):
        miss.append("no agency name set (settings: agency_name)")
    elif agency.lower() not in fs.lower():
        miss.append("does not name the agency")
    if HUMAN_CLAIM.search(text):
        miss.append("claims to be human")
    return (not miss), ("; ".join(miss) or "disclosure first: AI + agency + recorded")


HONEST_ROBOT = "I'm an AI assistant, not a person. {owner} is a real person, and I can book you a short call with them if you'd like."


def speech_filter(text: str, s: dict) -> tuple:
    """(safe_text, changed): a reply that claims to be human is replaced by the honest line before it is spoken."""
    if HUMAN_CLAIM.search(text or ""):
        return HONEST_ROBOT.format(owner=s.get("owner_first_name", "the owner")), True
    return text, False


def is_opt_out(said: str) -> bool:
    return bool(OPT_OUT.search(said or ""))


# ---------------------------------------------------------------- lists (our do-not-call list, the registry copy, the call log)

def _p(h, *parts):
    return os.path.join(C.state_dir(h), *parts)


def dnc_numbers(h=None) -> set:
    try:
        with open(_p(h, "dnc.txt"), encoding="utf-8") as f:
            return {e164(x.split("\t")[0]) for x in f if e164(x.split("\t")[0])}
    except OSError:
        return set()


def add_dnc(phone: str, why: str, h=None, now: dt.datetime | None = None) -> None:
    n = e164(phone)
    if not n:
        return
    with open(_p(h, "dnc.txt"), "a", encoding="utf-8") as f:
        f.write(f"{n}\t{(now or dt.datetime.now(dt.timezone.utc)).isoformat()}\t{why[:80]}\n")


def registry_status(phone: str, today: dt.date, h=None) -> tuple:
    """(ok, why) against <home>/caller/registry/: meta.json {"downloaded": "YYYY-MM-DD", "area_codes": [...]} + <area>.txt."""
    meta = C.read_json(_p(h, "registry", "meta.json"), {}) if os.path.isdir(_p(h, "registry")) else {}
    ac = area_code(phone)
    try:
        got = dt.date.fromisoformat(str(meta.get("downloaded")))
    except ValueError:
        return False, "the federal Do-Not-Call list has not been downloaded (CALLER_SETUP.bat step 4)"
    if (today - got).days > 31:
        return False, f"the Do-Not-Call download is {(today - got).days} days old (re-download every 31 days)"
    if ac not in [str(a) for a in meta.get("area_codes", [])]:
        return False, f"area code {ac} is not in our Do-Not-Call download"
    try:
        with open(_p(h, "registry", f"{ac}.txt"), encoding="utf-8") as f:
            listed = {re.sub(r"\D", "", x)[-10:] for x in f}
    except OSError:
        return False, f"registry file for {ac} missing"
    if e164(phone)[2:] in listed:
        return False, "on the federal Do-Not-Call list"
    return True, "not on the federal Do-Not-Call list"


def read_calls(h=None) -> list:
    out = []
    try:
        with open(_p(h, "calls.jsonl"), encoding="utf-8") as f:
            for line in f:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    pass
    except OSError:
        pass
    return out


def log_call(rec: dict, h=None) -> None:
    with open(_p(h, "calls.jsonl"), "a", encoding="utf-8") as f:
        f.write(C.redact(json.dumps(rec, sort_keys=True), h) + "\n")


def caller_state(h=None) -> dict:
    return C.read_json(_p(h, "state.json"), {}) or {}


# ---------------------------------------------------------------- the gate

FOLLOW_UP_OK = {"no_answer", "busy", "voicemail", "callback_requested", "failed"}


@dataclass
class Decision:
    ok: bool
    number: str = ""
    reasons: list = field(default_factory=list)   # every check, passed or not, in plain words
    blocked_by: str = ""

    def as_dict(self):
        return {"ok": self.ok, "number": self.number, "blocked_by": self.blocked_by, "reasons": self.reasons}


def check_outbound(lead: dict, now_utc: dt.datetime, line_type: str, consent_ok: tuple, h=None, s: dict | None = None,
                   calls: list | None = None) -> Decision:
    """The one question before any dial. consent_ok = consent.valid_for(...) -> (ok, why). line_type from the adapter's lookup."""
    s = s or C.settings(h)
    num = e164(lead.get("phone", ""))
    d = Decision(ok=False, number=num)

    def step(name, ok, why):
        d.reasons.append(("OK  " if ok else "NO  ") + f"{name}: {why}")
        if not ok and not d.blocked_by:
            d.blocked_by = name
        return ok

    st = caller_state(h)
    raw = read_calls(h) if calls is None else calls
    results = {c.get("call_id"): c.get("outcome") for c in raw if c.get("kind") == "result" and c.get("call_id")}
    calls = [{**c, "outcome": results.get(c.get("call_id"), c.get("outcome"))} for c in raw if c.get("kind", "attempt") == "attempt"]
    today_utc = now_utc.date()
    cap = min(int(st.get("daily_cap") or s["limits"]["daily_cap"]), int(s["limits"]["daily_cap_max"]))
    made_today = sum(1 for c in calls if c.get("dir") == "out" and str(c.get("ts", ""))[:10] == today_utc.isoformat())
    oks = [
        step("number", bool(num), "a US number" if num else "not a valid US number"),
        step("switch", bool(st.get("on")) and s.get("outbound_mode") == "consent_only",
             "caller is ON (consent-only)" if st.get("on") else "caller is OFF (CALLER_ON.bat + START CALLING)"),
        step("daily cap", made_today < cap, f"{made_today} of {cap} today"),
        step("consent", bool(consent_ok[0]), consent_ok[1]),
        step("our do-not-call list", num not in dnc_numbers(h), "not on it" if num not in dnc_numbers(h) else "ON our do-not-call list: never"),
    ]
    reg = registry_status(num, now_utc.astimezone(ZoneInfo(_E)).date(), h) if num else (False, "no number")
    oks.append(step("federal Do-Not-Call", reg[0], reg[1]))
    lt = str(line_type or "unknown").lower()
    oks.append(step("line type", lt in [x.lower() for x in s.get("line_types_allowed", ["landline"])] and lt == "landline",
                    f"{lt} ({'business landline OK' if lt == 'landline' else 'only landlines, never mobile / VoIP / unknown'})"))
    hrs = in_calling_hours(lead.get("state", ""), now_utc, s["hours"])
    oks.append(step("hours", hrs[0], hrs[1]))
    mine = sorted([c for c in calls if c.get("dir") == "out" and c.get("number") == num], key=lambda c: c.get("ts", ""))
    if not mine:
        oks.append(step("attempts", True, "first call"))
    elif len(mine) >= int(s["limits"]["max_attempts"]):
        oks.append(step("attempts", False, f"already {len(mine)} calls (1 call + 1 follow-up max)"))
    else:
        last = mine[-1]
        gap = business_days_between(dt.date.fromisoformat(str(last.get("ts"))[:10]), today_utc)
        need = int(s["limits"]["follow_up_min_business_days"])
        okf = last.get("outcome") in FOLLOW_UP_OK and gap >= need
        oks.append(step("attempts", okf, f"follow-up after '{last.get('outcome')}' {gap} business days ago (needs one of "
                                         f"{sorted(FOLLOW_UP_OK)} and {need}+ days)"))
    d.ok = all(oks)
    return d
