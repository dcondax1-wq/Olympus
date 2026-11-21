"""EMAIL AUTOPILOT core (day-a11y 2026-11-20, the Website Factory). Pure logic: no network, no files (tests/test_agency_autopilot.py).

The owner wants zero hands-on outreach. AI phone calls are out (FCC: an AI voice is a robocall under the TCPA; Maryland's law bans cold
automated calls without signed consent), so the PC sends EMAIL only, to businesses with a PUBLIC business email, within hard limits:
  * OFF until the owner types SEND EMAILS in EMAIL_SETUP.bat ("live"); "dry" sends every message to the owner's own test address only.
  * at most CAP_NEW (20) new businesses a day (warm-up), follow-ups on day 3 and day 7 only, nothing after a reply, Mon-Fri 9:00-16:00 ET.
  * a suppression list: an opt-out reply, a bounce or "stop" = never again (address and, for a bounce, the address only).
  * every message: the sender's real name and business, the postal address and a one-line way to say no (CAN-SPAM); refused otherwise.
Reply handling: classify (interested / question / not_now / optout / bounce), trim to the business's own words (no quoted thread, no
signature, phone numbers and emails masked) for the private branch; drafts that Claude writes go out by themselves only for the
price / demo / payment / booking kinds and only with links from the allow-list; everything else waits for the owner.
"""
from __future__ import annotations

import datetime as dt
import re

CAP_NEW = 20                     # new businesses a day (warm-up); follow-ups are on top but bounded by MAX_DAY
MAX_DAY = 60                     # every message of any kind in one ET day: a hard ceiling
MAX_RUN = 5                      # messages one run may send (the task runs every 30 minutes: spread over the day)
WINDOW = (9, 16)                 # ET hours [start, end): Mon-Fri only
FOLLOW = {"bump": 3, "last": 7}  # days after the first email
PHRASE = "SEND EMAILS"
MODES = ("off", "dry", "live")
AUTO_KINDS = ("price", "demo", "payment", "booking")
CLASSES = ("interested", "question", "not_now", "optout", "bounce")
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+'-]{1,64}@[A-Za-z0-9.-]{1,190}\.[A-Za-z]{2,24}$")
OPTOUT_LINE = 'Reply "no thanks"'

try:
    from zoneinfo import ZoneInfo
    ET = ZoneInfo("America/New_York")
except Exception:  # noqa: BLE001  (Windows without the tzdata package: a fixed -5 h is good enough for a 9-16 window)
    ET = dt.timezone(dt.timedelta(hours=-5))


def et_now(now: dt.datetime | None = None) -> dt.datetime:
    n = now or dt.datetime.now(dt.timezone.utc)
    if n.tzinfo is None:
        n = n.replace(tzinfo=dt.timezone.utc)
    return n.astimezone(ET)


def in_window(now: dt.datetime | None = None) -> bool:
    e = et_now(now)
    return e.weekday() < 5 and WINDOW[0] <= e.hour < WINDOW[1]


def day_of(now: dt.datetime | None = None) -> str:
    return et_now(now).strftime("%Y-%m-%d")


def add_days(iso: str, n: int) -> str:
    return (dt.date.fromisoformat(iso) + dt.timedelta(days=n)).isoformat()


def valid_email(a) -> bool:
    return isinstance(a, str) and bool(EMAIL_RE.match(a.strip()))


def norm_email(a) -> str:
    return str(a or "").strip().lower()


# ------------------------------------------------------------------------------------------------ config + state
CFG_KEYS = ("from_address", "app_password", "from_name", "business_name", "phone", "postal_address", "test_address", "booking_link",
            "payment_link", "site_base", "smtp_host", "smtp_port", "imap_host", "mode", "t_set")


def norm_cfg(raw) -> dict:
    c = {k: raw.get(k) for k in CFG_KEYS} if isinstance(raw, dict) else {}
    out = {k: (str(v).strip() if isinstance(v, str) else v) for k, v in c.items() if v not in (None, "")}
    out["mode"] = out.get("mode") if out.get("mode") in MODES else "off"
    out.setdefault("smtp_host", "smtp.gmail.com")
    out["smtp_port"] = int(out.get("smtp_port") or 465)
    out.setdefault("imap_host", "imap.gmail.com")
    return out


def cfg_problems(c: dict) -> list:
    """what is missing before ANY message may go out (dry or live)"""
    p = []
    if not valid_email(c.get("from_address")):
        p.append("the sending Gmail address")
    if not c.get("app_password"):
        p.append("the Gmail app password")
    if not c.get("from_name"):
        p.append("your name (the sender)")
    if not c.get("business_name"):
        p.append("your business name")
    if len(str(c.get("postal_address") or "")) < 8:
        p.append("your postal address (CAN-SPAM: required in every email)")
    if not valid_email(c.get("test_address")):
        p.append("a test address (dry run)")
    return p


def empty_state() -> dict:
    return {"v": 1, "sent": {}, "suppress": [], "replied": {}, "days": {}, "last_uid": 0, "inbox": [], "outbox_done": {}, "pending": [], "flagged": [], "notes": {}, "caller_pushed": {}, "pc_from": {}}


def norm_state(raw) -> dict:
    s = empty_state()
    if isinstance(raw, dict):
        for k in s:
            if k in raw and isinstance(raw[k], type(s[k])):
                s[k] = raw[k]
    s["suppress"] = sorted({norm_email(a) for a in s["suppress"] if valid_email(a)})
    return s


def suppressed(state: dict, addr: str) -> bool:
    return norm_email(addr) in set(state.get("suppress") or [])


def suppress(state: dict, addr: str) -> bool:
    a = norm_email(addr)
    if not valid_email(a) or a in state["suppress"]:
        return False
    state["suppress"] = sorted(set(state["suppress"]) | {a})
    return True


def day_counts(state: dict, day: str) -> dict:
    return state["days"].setdefault(day, {"new": 0, "followup": 0, "reply": 0, "replies_in": 0})


# ------------------------------------------------------------------------------------------------ who gets what today
HEAT = {"hot": 0, "warm": 1, "cold": 2}


def lead_email(L: dict) -> str:
    for k in ("email", "contact_email", "public_email"):
        a = norm_email(L.get(k))
        if valid_email(a):
            return a
    return ""


def plan(leads: list, state: dict, now: dt.datetime | None = None, cap_new: int = CAP_NEW) -> list:
    """[{lead, to, step}] for this run: due follow-ups first, then new businesses (hot first, best score), within every limit.
    Empty outside Mon-Fri 9-16 ET. Never a suppressed address, never a business that replied, never twice the same step."""
    if not in_window(now):
        return []
    day = day_of(now)
    cnt = day_counts(state, day)
    room_day = MAX_DAY - (cnt["new"] + cnt["followup"] + cnt["reply"])
    room = max(0, min(MAX_RUN, room_day))
    out, seen = [], set()
    byid = {L.get("id"): L for L in leads if isinstance(L, dict) and L.get("id")}
    for lid, log in sorted(state["sent"].items()):
        L = byid.get(lid)
        if not L or lid in state["replied"] or not log:
            continue
        to = norm_email(log[0].get("to"))
        if suppressed(state, to):
            continue
        d0, done = log[0].get("d"), {x.get("step") for x in log}
        for step, n in FOLLOW.items():
            if step not in done and d0 and add_days(d0, n) <= day:
                if step == "last" and "bump" not in done:
                    break
                out.append({"lead": L, "to": to, "step": step})
                seen.add(lid)
                break
    out = out[:room]
    new_room = max(0, min(cap_new - cnt["new"], room - len(out)))
    fresh = [L for L in leads if isinstance(L, dict) and L.get("id") and L["id"] not in state["sent"] and L["id"] not in seen
             and lead_email(L) and not suppressed(state, lead_email(L)) and L.get("name")]
    fresh.sort(key=lambda L: (HEAT.get(L.get("heat"), 3), -(float(L.get("score") or 0)), str(L.get("name"))))
    taken = {norm_email(x.get("to")) for log_ in state["sent"].values() for x in log_}   # an address already written to (any lead) never again as "new"
    for L in fresh:
        if len(out) >= room or new_room <= 0:
            break
        a = lead_email(L)
        if a in taken:                    # two leads, one address: write once
            continue
        taken.add(a)
        out.append({"lead": L, "to": a, "step": "first"})
        new_room -= 1
    return out


def record_sent(state: dict, lead_id: str, to: str, step: str, now: dt.datetime | None = None, msg_id: str = "") -> None:
    day = day_of(now)
    state["sent"].setdefault(lead_id, []).append({"step": step, "d": day, "to": norm_email(to), "t": int(et_now(now).timestamp()), "id": msg_id})
    c = day_counts(state, day)
    c["new" if step == "first" else "reply" if step == "reply" else "followup"] += 1


# ------------------------------------------------------------------------------------------------ the words
NICHE_DEMO = {"food": "restaurant", "auto": "detailer", "roofing": "roofer", "trades": "roofer", "home": "roofer", "realestate": "estate", "outdoor": "shed"}


def fill(text: str, v: dict) -> str:
    def rep(m):
        k = m.group(1)
        if k in v and v[k] is not None:
            return str(v[k])
        return "[" + k.replace("_", " ") + "]"
    return re.sub(r"\{([a-z_]+)\}", rep, str(text or ""))


def demo_for(L: dict, sites: dict, base: str) -> tuple:
    b = str(base or "").rstrip("/")
    own = (sites or {}).get(L.get("id")) or L.get("demo_url")
    if isinstance(own, str) and re.match(r"^(https://|\.\./|/|sites/|f/[a-z2-9]{8}/)", own):
        return (own if own.startswith("https://") else b + "/agency/" + re.sub(r"^(\.\./)+|^/?agency/", "", own.lstrip("/"))), True
    d = NICHE_DEMO.get(L.get("niche") or "", "")
    return b + "/agency/demos/" + (d + "/" if d else ""), False


def niche_words(L: dict) -> str:
    c = str(L.get("category") or L.get("trade") or "").replace("_", " ").strip()
    if c and c != "yes":
        return "food" if c == "fast food" else c
    return str(L.get("niche_name") or "a local business").lower()


def price_line(offers: dict) -> str:
    P = (offers or {}).get("packages") or []
    s = next((p for p in P if isinstance(p, dict) and p.get("id") == "starter"), {"price": 1500, "monthly": 79})
    return (f"Starter site ${int(s['price']):,} + ${int(s['monthly'])} a month for hosting and small edits, "
            "or no upfront: $149 a month for 12 months.")


CALL_LINE = "Prefer a quick call? On your draft site, tap \"Have our assistant call me\" and pick a time that suits you."


def message(words: dict, L: dict, step: str, cfg: dict, offers: dict, sites: dict) -> dict:
    """{subject, body, html?}: the step's email from scripts.json, personalised, the CAN-SPAM footer guaranteed"""
    tpl = next((e for e in words.get("email", []) if e.get("id") == step), None)
    if not tpl:
        raise ValueError(f"no email for step {step}")
    demo, own = demo_for(L, sites, cfg.get("site_base") or "")
    v = {"business": L.get("name") or "your business", "town": L.get("town") or L.get("city") or "your town", "niche": niche_words(L),
         "demo": demo, "demo_short": re.sub(r"^https?://", "", demo), "offer_line": price_line(offers),
         "your_name": cfg.get("from_name"), "your_business": cfg.get("business_name"), "your_phone": cfg.get("phone") or "",
         "your_email": cfg.get("from_address"), "postal_address": cfg.get("postal_address"),
         "call_line": CALL_LINE if (own and step == "first") else ""}
    body = fill(tpl["body"], v)
    if step == "first" and own and CALL_LINE not in body:
        body = body.replace("\n\nWould a 10-minute call", "\n\n" + CALL_LINE + "\n\nWould a 10-minute call", 1)
    body = ensure_footer(body, cfg)
    return {"subject": fill(tpl["subject"], v), "body": body, "demo": demo}


def ensure_footer(body: str, cfg: dict) -> str:
    """the postal address and the way to say no are in every message (added when a draft forgot them)"""
    addr = str(cfg.get("postal_address") or "").strip()
    add = []
    if addr and addr not in body:
        add.append(f"{cfg.get('business_name') or ''} · {addr}".strip(" ·"))
    if "no thanks" not in body.lower() and "won't keep emailing" not in body.lower():
        add.append(f'{OPTOUT_LINE} and I won\'t write again.')
    return body.rstrip() + ("\n\n" + "\n".join(add) if add else "")


def compliant(body: str, cfg: dict, subject: str = "") -> list:
    """problems that block a send: no postal address, no way to say no, no sender name, a deceptive subject"""
    p = []
    b = body or ""
    if len(str(cfg.get("postal_address") or "")) < 8 or str(cfg.get("postal_address")) not in b:
        p.append("no postal address")
    if "no thanks" not in b.lower() and "won't keep emailing" not in b.lower() and "unsubscribe" not in b.lower():
        p.append("no way to say no")
    if not cfg.get("from_name") or str(cfg.get("from_name")) not in b:
        p.append("no sender name")
    if re.match(r"^\s*(re|fwd?):", subject or "", re.I) and "free website draft" not in (subject or "").lower():
        p.append("a 'Re:' subject on a first message")
    if re.search(r"\[(your name|business name|postal address|your phone)", b, re.I):
        p.append("an unfilled [placeholder]")
    return p


# ------------------------------------------------------------------------------------------------ replies
BOUNCE_FROM = re.compile(r"mailer-daemon|postmaster|mail delivery subsystem", re.I)
BOUNCE_SUBJ = re.compile(r"delivery status notification|undeliverable|undelivered|mail delivery failed|returned mail|delivery failure|address not found", re.I)
OPTOUT = re.compile(r"\b(unsubscribe|remove me|take me off|stop (emailing|contacting|messaging)|do not (email|contact|write)|don'?t (email|contact|write)|"
                    r"no thanks|no,? thank you|not interested|leave (me|us) alone|spam|^stop\b)", re.I | re.M)
NOT_NOW = re.compile(r"\b(not (right )?now|maybe later|busy (right now|season)|next (month|year|week|spring|summer)|after the holidays|"
                     r"check back|reach out (again )?(in|later)|bad time)\b", re.I)
INTERESTED = re.compile(r"\b(yes|interested|sounds good|love it|looks (great|good)|let'?s (talk|do it|chat)|call me|give me a call|set (it )?up|"
                        r"sign (me|us) up|go ahead|when can (we|you)|i'?m in)\b", re.I)
PRICEQ = re.compile(r"\b(how much|price|cost|pricing|monthly|fee|charge)\b", re.I)


def classify(subject: str, sender: str, text: str) -> str:
    if BOUNCE_FROM.search(sender or "") or BOUNCE_SUBJ.search(subject or ""):
        return "bounce"
    t = trim(text, mask=False)
    if OPTOUT.search(t) and not re.search(r"\bnot interested in (paying|the price)", t, re.I):
        return "optout"
    if NOT_NOW.search(t):
        return "not_now"
    if INTERESTED.search(t) and "?" not in t:
        return "interested"
    if "?" in t or PRICEQ.search(t):
        return "question"
    return "interested" if INTERESTED.search(t) else "question"


QUOTE_START = re.compile(r"^(on .{3,200} wrote:|-{2,} ?original message ?-{2,}|from: .+|sent from my \w+.*|get outlook for .*|_{5,})$", re.I)
SIGN_START = re.compile(r"^(--\s*|thanks,?|thank you,?|best,?|regards,?|best regards,?|cheers,?|sincerely,?)$", re.I)
PHONE_RE = re.compile(r"(\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}")
ADDR_RE = re.compile(r"[A-Za-z0-9._%+'-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def trim(text: str, mask: bool = True, limit: int = 600) -> str:
    """the business's own new words: no quoted thread, no signature; phone numbers and email addresses masked"""
    lines = []
    for ln in str(text or "").replace("\r\n", "\n").split("\n"):
        s = ln.strip()
        if s.startswith(">") or QUOTE_START.match(s):
            break
        if SIGN_START.match(s) and lines:
            break
        lines.append(s)
    out = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
    if mask:
        out = ADDR_RE.sub("[email]", PHONE_RE.sub("[phone]", out))
    return out[:limit]


def bounced_address(text: str, sent_to: set) -> str:
    """which of our recipients a bounce is about (the first address in its text that we sent to)"""
    for a in ADDR_RE.findall(text or ""):
        if norm_email(a) in sent_to:
            return norm_email(a)
    return ""


# ------------------------------------------------------------------------------------------------ Claude's drafts (the outbox)
URL_RE = re.compile(r"https?://[^\s)>\]\"']+", re.I)


def draft_ok(d: dict, cfg: dict, allowed_urls: set) -> tuple:
    """(send_now, why): an auto kind with only allow-listed links goes out; anything else needs approved: true from the owner"""
    if not isinstance(d, dict) or not d.get("id") or not d.get("lead_id") or not d.get("body"):
        return False, "not a draft"
    kind = d.get("kind")
    links = {u.rstrip(".,") for u in URL_RE.findall(d.get("body") or "")}
    if d.get("approved") is True:
        return True, "approved by the owner"
    if kind not in AUTO_KINDS:
        return False, f"'{kind}' needs the owner's OK"
    bad = [u for u in links if not any(u.startswith(a) for a in allowed_urls if a)]
    if bad:
        return False, "a link that is not ours: " + bad[0][:60]
    if re.search(r"\b(guarantee|lawsuit|legal|refund|discount)\b", d.get("body") or "", re.I):
        return False, "words that need the owner (guarantee / legal / refund / discount)"
    return True, f"auto ({kind})"


def public_counts(state: dict, cfg: dict, queue: int, now: dt.datetime | None = None) -> dict:
    """the outreach page's numbers (public ntfy status topic): counts only, never a name, an address or a word of a reply"""
    day = day_of(now)
    c = state["days"].get(day, {})
    inbox = state.get("inbox") or []
    return {"kind": "le-mail", "v": 1, "t": int(et_now(now).timestamp()), "mode": cfg.get("mode", "off"), "day": day,
            "new": c.get("new", 0), "cap": CAP_NEW, "followup": c.get("followup", 0), "replies_today": c.get("replies_in", 0),
            "interested": sum(1 for x in inbox if x.get("class") == "interested"), "questions": sum(1 for x in inbox if x.get("class") == "question"),
            "optouts": sum(1 for x in inbox if x.get("class") == "optout"), "bounces": sum(1 for x in inbox if x.get("class") == "bounce"),
            "suppressed": len(state.get("suppress") or []), "contacted": len(state.get("sent") or {}), "queue": queue}
