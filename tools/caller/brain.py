"""THE CALL BRAIN: one CallSession per call. Warm and natural, honest always.

Order of every turn (the order is the safety):
  1. the opener is compliance.opening_line (code, not the model): AI assistant + agency + recorded, in the first sentence
  2. what the business said is checked for an opt-out FIRST: "don't call me" ends the call, do-not-call list + consent revoked, forever
  3. the brain (ScriptedBrain offline, ClaudeBrain live) picks the reply and at most one action: book / payment link / email / callback / end
  4. the reply passes compliance.speech_filter: a line that claims to be human is replaced by the honest one before it is spoken
  5. hard stops: 16 turns or max_call_seconds, two clear no's = a polite goodbye (never a third push)
"""
from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import dataclass

try:
    from . import actions as A
    from . import compliance as G
except ImportError:  # pragma: no cover
    import actions as A  # type: ignore
    import compliance as G  # type: ignore

MAX_TURNS = 16


@dataclass
class Reply:
    text: str
    action: str = ""          # "", "book:0", "book:1", "pay", "demo", "callback", "end"
    end: bool = False


def spoken_email(said: str) -> str:
    """'bob dot smith at gmail dot com' / 'bob@gmail.com' -> 'bob.smith@gmail.com'; '' if none heard."""
    t = " " + said.lower() + " "
    t = re.sub(r"\s+at\s+", "@", t)
    t = re.sub(r"\s+dot\s+", ".", t)
    t = re.sub(r"\s+(underscore)\s+", "_", t)
    t = re.sub(r"\s+(dash|hyphen)\s+", "-", t)
    m = re.search(r"([a-z0-9._%+\-]+)\s*@\s*([a-z0-9\-]+(?:\.[a-z0-9\-]+)*\.[a-z]{2,})", t)
    return f"{m.group(1)}@{m.group(2)}" if m else ""


class CallSession:
    def __init__(self, lead: dict, s: dict, brain, actions: "A.Actions", now_utc: dt.datetime, inbound: bool = False,
                 email: str = "", call_id: str = ""):
        self.lead, self.s, self.brain, self.act, self.now = lead, s, brain, actions, now_utc
        self.inbound, self.email, self.call_id = inbound, email, call_id
        self.transcript = []            # [{"who": "ai"|"biz", "text"}]
        self.state = "opened"
        self.slots = A.offer_slots(lead, now_utc, s)
        self.nos = 0
        self.outcome = "connected"
        self.ended = False
        self.filtered = 0

    # -- speaking
    def _say(self, text: str) -> str:
        safe, changed = G.speech_filter(text, self.s)
        self.filtered += int(changed)
        self.transcript.append({"who": "ai", "text": safe})
        return safe

    def start(self) -> str:
        line = G.opening_line(self.s, "" if self.inbound else self.lead.get("name", ""), inbound=self.inbound)
        ok, why = G.check_disclosure(line, self.s)
        if not ok:                                   # a broken setting (no agency name) must never reach a phone
            raise RuntimeError("disclosure check failed: " + why)
        self.transcript.append({"who": "ai", "text": line})
        return line

    def hear(self, said: str) -> Reply:
        if self.ended:
            return Reply("", end=True)
        self.transcript.append({"who": "biz", "text": said})
        if G.is_opt_out(said):
            self.act.opt_out(self.lead, said)
            self.outcome, self.ended = "opt_out", True
            return Reply(self._say("Understood, I've taken this number off our list and we won't call again. Sorry to bother you, "
                                   "have a good day."), "end", True)
        em = spoken_email(said)
        if em:
            self.email = em
        if sum(1 for t in self.transcript if t["who"] == "biz") >= MAX_TURNS:
            self.ended = True
            return Reply(self._say(f"I don't want to keep you. I'll email what we talked about, and you can reach us at "
                                   f"{self.s.get('callback_number')}. Thanks so much."), "end", True)
        r = self.brain.respond(self, said)
        r.text = self._say(r.text)
        self._do(r.action)
        if r.end:
            self.ended = True
        return r

    def _do(self, action: str):
        if action.startswith("book:"):
            i = int(action.split(":")[1])
            if 0 <= i < len(self.slots):
                self.act.book(self.lead, self.slots[i], self.email)
                self.outcome, self.state = "booked", "booked"
        elif action == "pay":
            self.act.send_payment_link(self.lead, self.email)
            self.outcome = "payment_link"
        elif action == "demo":
            self.act.send_demo(self.lead, self.email)
            if self.outcome == "connected":
                self.outcome = "demo_sent"
        elif action == "callback":
            self.outcome = "callback_requested"
        elif action == "declined" and self.outcome == "connected":
            self.outcome = "declined"

    def record(self) -> dict:
        return {"kind": "result", "ts": self.now.isoformat(), "call_id": self.call_id, "lead_id": self.lead.get("id", ""), "business": self.lead.get("name", ""),
                "number": G.e164(self.lead.get("phone", "")), "dir": "in" if self.inbound else "out", "outcome": self.outcome,
                "turns": len(self.transcript), "actions": self.act.done, "replaced_lines": self.filtered}


# ---------------------------------------------------------------- the offline brain (tests, simulator, fallback)

def _has(said, *words):
    s = said.lower()
    return any(re.search(r"\b" + re.escape(w) + r"\b", s) for w in words)


class ScriptedBrain:
    """Rules, no model, no network: the same honest script every time. Used by the simulator and if the model is down."""
    name = "scripted"

    def respond(self, cs: CallSession, said: str) -> Reply:
        s, lead = cs.s, cs.lead
        owner, biz = s.get("owner_first_name", "the owner"), lead.get("name", "your business")
        sl = cs.slots
        offer = (f"Would {sl[0]['say']} or {sl[1]['say']} work for a {sl[0]['minutes']}-minute call with {owner}?" if len(sl) >= 2
                 else f"I can have {owner} email you a time.")
        if _has(said, "robot", "bot", "machine", "real person", "human", "recording", "ai", "computer", "person"):
            if getattr(cs, "said_ai", False):
                return Reply(f"No, I'm not human: I'm an AI assistant. If you'd rather talk to a person, {owner} can call you. " + offer)
            cs.said_ai = True
            return Reply(f"I'll be straight with you: I'm an AI assistant, not a person. {owner} is the real person behind "
                         f"{s.get('agency_name')}, and I can book you a short call with them. " + offer)
        if cs.state == "offered" or _has(said, "monday", "tuesday", "wednesday", "thursday", "friday", "first one", "second one",
                                         "the first", "the second", "morning", "afternoon"):
            pick = None
            if _has(said, "first", "morning") or (sl and _has(said, sl[0]["say"].split()[0].lower())):
                pick = 0
            elif _has(said, "second", "afternoon", "later one") or (len(sl) > 1 and _has(said, sl[1]["say"].split()[0].lower())):
                pick = 1
            if pick is not None and len(sl) > pick:
                if not cs.email:
                    cs.state, cs.pending = "need_email", pick
                    return Reply(f"Great, {sl[pick]['say']}. What's the best email for the confirmation and the preview link?")
                cs.state = "booked"
                return Reply(f"You're booked for {sl[pick]['say']}. I'll email the confirmation and the preview link to {cs.email}. "
                             f"Anything else I can answer?", f"book:{pick}")
        if cs.state == "need_email":
            if cs.email:
                pick = getattr(cs, "pending", 0)
                cs.state = "booked"
                return Reply(f"Thanks, got it: {cs.email}. You're booked for {sl[pick]['say']}, the confirmation is on its way. "
                             f"Anything else?", f"book:{pick}")
            return Reply("Sorry, I didn't catch that. Could you spell the email for me, like 'bob at gmail dot com'?")
        if cs.state == "booked" and _has(said, "no", "nope", "that's it", "thats it", "all good", "bye", "thanks", "thank you"):
            return Reply(f"Perfect. Talk soon, and have a great day.", "end", True)
        if _has(said, "busy", "bad time", "call back", "later", "in the middle", "with a customer", "can't talk", "cant talk"):
            if cs.state == "busy":
                return Reply("Of course. Thanks for picking up, have a good day.", "callback", True)
            cs.state = "busy"
            return Reply("No problem at all, I'll keep it short. Can I just email you the preview so you can look when it suits you, "
                         "and we try once more another day?", "callback")
        if _has(said, "how much", "price", "cost", "expensive", "charge", "pricing") and not _has(said, "too expensive", "too much"):
            cs.state = "offered"
            return Reply(f"{s.get('price_line')} {owner} can walk you through it. " + offer)
        if _has(said, "nephew", "niece", "cousin", "my son", "my daughter", "friend does", "guy who does", "someone who does", "we have someone"):
            return Reply("That's great, family help is worth a lot. The preview is already built, so there's no cost to compare: I can email it, "
                         "and your nephew could even use it. Would that be helpful?")
        if _has(said, "already have", "have a website", "got a website", "have a site"):
            return Reply("Nice. The preview is just a second option side by side; if yours is better you've lost one minute. "
                         "Want me to email the link?")
        if _has(said, "who is this", "what is this", "what's this", "what preview", "what site", "how did you get"):
            return Reply(f"Sure: {s.get('agency_name')} builds websites for local businesses. Someone asked on the preview page for us to call "
                         f"{biz}, so I'm following up. The preview is a finished one-page site. " + offer)
        if _has(said, "pay", "sign up", "ready to start", "let's do it", "lets do it", "buy"):
            if s.get("payment_link") and cs.email:
                return Reply(f"Wonderful. I'm emailing the secure checkout link to {cs.email} now; nothing is charged until you finish it. "
                             f"Would you also like a quick call with {owner} to go over photos and wording? " + offer, "pay")
            cs.state = "offered"
            return Reply(f"Wonderful. {owner} will set it up with you. " + offer)
        if _has(said, "email", "send it", "send me"):
            if cs.email:
                return Reply(f"Done, I'll send it to {cs.email} right after this call. " + offer, "demo")
            cs.state = "ask_email_demo"
            return Reply("Happy to. What's the best email?")
        if cs.state == "ask_email_demo" and cs.email:
            cs.state = "pitched"
            return Reply(f"Got it, {cs.email}. The link is on its way. " + offer, "demo")
        if _has(said, "no", "not interested", "no thanks", "nah", "don't need", "dont need", "too much", "more than i want",
                "can't afford", "cant afford", "too expensive"):
            cs.nos += 1
            if cs.nos >= 2 or cs.state == "asked_why":
                return Reply("Totally fair, thanks for your time. If you ever want the preview, just call us. Have a good day.", "declined", True)
            cs.state = "asked_why"
            return Reply("No worries. Is it the timing, or are you happy with how customers find you now? Either way I can just email "
                         "the preview, no strings.")
        if _has(said, "yes", "yeah", "sure", "okay", "ok", "go ahead", "sounds good", "interested", "tell me", "alright", "fine"):
            cs.state = "offered"
            return Reply(f"Great. We built a free one-page site for {biz}: services, hours, tap-to-call and a map, ready to go live. "
                         f"The easiest next step is a short call with {owner} to make it yours. " + offer)
        return Reply("Sorry, I didn't quite get that. In short: the preview is free, and I can email it or book a short call with "
                     f"{owner}. Which would you prefer?")


# ---------------------------------------------------------------- the live brain (Claude)

SYSTEM = """You are {assistant}, an AI phone assistant for {agency}, a small web studio. You are on a live phone call with {business} in {town}.
Facts you may use: we already built a free one-page website preview for them ({demo}). {price_line} The owner, {owner}, is a real person.
They SIGNED a form asking us to call (or they called us). Two call slots you may offer: {slots}.
Rules (never break them):
- You are an AI. If asked anything about being a robot, a person, or a recording, say plainly you are an AI assistant. Never claim or hint you are human.
- Never invent clients, reviews, results, discounts or guarantees. If you do not know, say {owner} will answer by email.
- If they say anything like "don't call", "remove me", "stop": apologise, confirm they are off the list, end the call (tool end_call reason opt_out).
- Two clear no's: thank them and end politely. Never pressure.
- Speak like a warm, relaxed local person on the phone: one or two short sentences per turn, no lists, no markdown, no emojis.
- To book, use book_slot (0 or 1) only after they picked one AND you have an email (ask for it). To send the preview or the payment link, use the tools.
"""

TOOLS = [
    {"name": "book_slot", "description": "Book one of the two offered slots after the person chose it and gave an email.", "strict": True,
     "input_schema": {"type": "object", "properties": {"slot": {"type": "integer", "enum": [0, 1]}, "email": {"type": "string"}},
                      "required": ["slot", "email"], "additionalProperties": False}},
    {"name": "send_email", "description": "Email the preview link (kind=demo) or the payment link (kind=pay).", "strict": True,
     "input_schema": {"type": "object", "properties": {"kind": {"type": "string", "enum": ["demo", "pay"]}, "email": {"type": "string"}},
                      "required": ["kind", "email"], "additionalProperties": False}},
    {"name": "end_call", "description": "End the call after saying goodbye.", "strict": True,
     "input_schema": {"type": "object", "properties": {"reason": {"type": "string", "enum": ["done", "declined", "busy", "opt_out"]}},
                      "required": ["reason"], "additionalProperties": False}},
]


class ClaudeBrain:
    """The live brain: Claude via the official SDK. Any error falls back to ScriptedBrain for that turn (the call never goes silent)."""
    name = "claude"

    def __init__(self, api_key: str, model: str = "claude-opus-5-5", effort: str = "low", client=None):
        if client is None:
            import anthropic  # only on the PC with the key; the tests never get here
            client = anthropic.Anthropic(api_key=api_key, max_retries=1, timeout=8.0)
        self.client, self.model, self.effort = client, model, effort
        self.fallback = ScriptedBrain()

    def _system(self, cs: CallSession) -> str:
        s, lead = cs.s, cs.lead
        return SYSTEM.format(assistant=s.get("assistant_name"), agency=s.get("agency_name"), business=lead.get("name", "the business"),
                             town=lead.get("town") or lead.get("city", ""), demo=cs.act.demo_url(lead), price_line=s.get("price_line"),
                             owner=s.get("owner_first_name"), slots="; ".join(f"{i}: {x['say']}" for i, x in enumerate(cs.slots)))

    def respond(self, cs: CallSession, said: str) -> Reply:
        msgs = [{"role": "assistant" if t["who"] == "ai" else "user", "content": t["text"]} for t in cs.transcript]
        if msgs and msgs[0]["role"] == "assistant":
            msgs.insert(0, {"role": "user", "content": "(the call connects)"})
        try:
            r = self.client.beta.messages.create(
                model=self.model, max_tokens=400, system=[{"type": "text", "text": self._system(cs), "cache_control": {"type": "ephemeral"}}],
                messages=msgs, tools=TOOLS, tool_choice={"type": "auto"}, output_config={"effort": self.effort},
                betas=["server-side-fallback-2026-07-01"], fallbacks="default")
        except Exception:
            return self.fallback.respond(cs, said)
        if getattr(r, "stop_reason", "") == "refusal":
            return self.fallback.respond(cs, said)
        text, action, end = "", "", False
        for b in r.content:
            if b.type == "text":
                text += b.text
            elif b.type == "tool_use":
                inp = b.input if isinstance(b.input, dict) else json.loads(b.input or "{}")
                if A.valid_email(inp.get("email")):        # one plain address only (a list / newline never reaches the outbox)
                    cs.email = A.valid_email(inp["email"])
                if b.name == "book_slot" and cs.email:
                    action = f"book:{int(inp.get('slot', 0))}"
                elif b.name == "send_email":
                    action = "pay" if inp.get("kind") == "pay" else "demo"
                elif b.name == "end_call":
                    end = True
                    action = action or {"declined": "declined", "busy": "callback"}.get(inp.get("reason", ""), "end")
        text = re.sub(r"[*_#`>\[\]]", "", text).strip() or "Sorry, could you say that again?"
        return Reply(text, action, end)
