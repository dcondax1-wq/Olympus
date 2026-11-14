"""Call copilot core, PC twin of tools/web_public/agency/callcore.js (team B2, 2026-11-14).

Same rules file (tools/web_public/agency/callrules.json), same script (callscript.json), same answers: the phone page and this module must agree
on every call window, lock and filled script (tests/test_cold_calls.py runs both on the same leads). Pure: no network, no dialing, no files
written here (build.py writes the call list). Times are UTC milliseconds like the page; the law behind every limit is docs/COLD_CALLING_RULES.md.
"""
from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "tools" / "web_public" / "agency"
DAY = 86_400_000
HOUR = 3_600_000
DOW = ["", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
DOW3 = ["", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
MON3 = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
CALL_KINDS = ("noanswer", "voicemail", "callback", "interested", "notinterested", "dnc")


def load_rules(path: Path | None = None) -> dict:
    return json.loads((path or WEB / "callrules.json").read_text(encoding="utf-8"))


def load_script(path: Path | None = None) -> dict:
    return json.loads((path or WEB / "callscript.json").read_text(encoding="utf-8"))


# ------------------------------------------------------------------------------------------------ small helpers
def s_(v) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v).strip()


def ymd(y: int, m: int, d: int) -> str:
    return f"{y:04d}-{m:02d}-{d:02d}"


def add_days(ds: str, n: int) -> str:
    return (datetime.strptime(ds, "%Y-%m-%d") + timedelta(days=n)).strftime("%Y-%m-%d")


def iso_wd(ds: str) -> int:
    return datetime.strptime(ds, "%Y-%m-%d").isoweekday()


def clock(minute: int) -> str:
    h, m = (minute // 60) % 24, minute % 60
    return f"{12 if h % 12 == 0 else h % 12}:{m:02d} {'am' if h < 12 else 'pm'}"


def span(a: int, b: int) -> str:
    return f"{clock(a)}-{clock(b)}"


EMAIL = re.compile(r"""^[^\s@?&#<>"',;:()]+@[^\s@?&#<>"',;:()]+\.[A-Za-z]{2,}$""")


def valid_email(e) -> bool:
    return bool(EMAIL.match(s_(e)))


def fold(v) -> str:
    t = unicodedata.normalize("NFD", s_(v).lower())
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    return " " + re.sub(r"[^a-z0-9']+", " ", t).strip() + " "


def truthy(v) -> bool:
    if v is True or v == 1:
        return True
    return s_(v).lower() in ("1", "true", "yes", "y", "on", "x")


def utc_date(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y-%m-%d")


# ------------------------------------------------------------------------------------------------ phones (US / NANP only)
EXT = re.compile(r"\s*(?:ext\.?|extension|x|#)\s*\d{1,6}\s*$", re.I)


def norm_phone(raw) -> str:
    s = s_(raw)
    if not s:
        return ""
    s = EXT.sub("", s)
    plus = s.startswith("+")
    d = re.sub(r"\D", "", s)
    if len(d) == 11 and d[0] == "1":
        d = d[1:]
    elif plus:
        return ""
    if not re.fullmatch(r"[2-9]\d{2}[2-9]\d{6}", d):
        return ""
    return "+1" + d


def pretty_phone(e164: str) -> str:
    d = s_(e164).removeprefix("+1")
    return f"({d[:3]}) {d[3:6]}-{d[6:]}" if re.fullmatch(r"\d{10}", d) else s_(e164)


def area_code(e164: str) -> str:
    d = s_(e164).removeprefix("+1")
    return d[:3] if len(d) == 10 else ""


def is_fictional(e164: str) -> bool:
    return bool(re.fullmatch(r"\+1\d{3}55501\d\d", s_(e164)))


# ------------------------------------------------------------------------------------------------ states, zones, the clock
def state_code(v, rules: dict) -> str:
    s = s_(v)
    if not s:
        return ""
    up = s.upper().replace(".", "")
    if len(up) == 2 and up in rules["states"]:
        return up
    low = re.sub(r"\s+", " ", s.lower().replace(".", "")).strip()
    for k, st in rules["states"].items():
        if st["name"].lower() == low:
            return k
    return "DC" if low in ("washington dc", "d c") else ""


_ZI: dict = {}


def zi(tz: str) -> ZoneInfo:
    if tz not in _ZI:
        _ZI[tz] = ZoneInfo(tz)
    return _ZI[tz]


def valid_tz(tz) -> bool:
    if not tz or not isinstance(tz, str) or "/" not in tz:
        return False
    try:
        zi(tz)
        return True
    except Exception:
        return False


def parts_in(ms: int, tz: str) -> dict:
    t = datetime.fromtimestamp(int(ms // 1000), zi(tz))
    return {"y": t.year, "m": t.month, "d": t.day, "wd": t.isoweekday(), "min": t.hour * 60 + t.minute, "date": t.strftime("%Y-%m-%d")}


def zoned_to_utc(ds: str, minute: int, tz: str) -> int:
    y, m, d = (int(x) for x in ds.split("-"))
    t = datetime(y, m, d, tzinfo=zi(tz)) + timedelta(minutes=minute)
    return int(round(t.timestamp() * 1000))


def zones_of(lead: dict, rules: dict, settings: dict | None = None) -> dict:
    if valid_tz(lead.get("tz")):
        return {"zones": [lead["tz"]], "how": "lead", "state": state_code(lead.get("state"), rules)}
    code, how = state_code(lead.get("state"), rules), "state"
    if not code and settings and state_code(settings.get("defaultState"), rules):
        code, how = state_code(settings.get("defaultState"), rules), "default"
    st = rules["states"].get(code)
    if not st:
        return {"zones": [], "how": "none", "state": ""}
    city = s_(lead.get("city")).lower()
    cm = (rules.get("cities") or {}).get(code) or {}
    if city and city in cm:
        return {"zones": [cm[city]], "how": "city", "state": code}
    return {"zones": list(st["tz"]), "how": "split" if len(st["tz"]) > 1 else how, "state": code}


# ------------------------------------------------------------------------------------------------ holidays
def _nth_wd(y: int, m: int, wd: int, n: int) -> str:
    if n > 0:
        f = iso_wd(ymd(y, m, 1))
        return ymd(y, m, 1 + ((wd - f + 7) % 7) + (n - 1) * 7)
    last = ((datetime(y + (m == 12), m % 12 + 1, 1)) - timedelta(days=1)).day
    lw = iso_wd(ymd(y, m, last))
    return ymd(y, m, last - ((lw - wd + 7) % 7))


_HOL: dict = {}


def holidays(y: int, policy: dict | None = None) -> dict:
    key = (y, not (policy and policy.get("dayAfterThanksgiving") is False))
    if key in _HOL:
        return _HOL[key]
    out: dict = {}
    for m, d, n in ((1, 1, "New Year's Day"), (6, 19, "Juneteenth"), (7, 4, "Independence Day"), (11, 11, "Veterans Day"), (12, 25, "Christmas Day")):
        ds = ymd(y, m, d)
        out[ds] = n
        w = iso_wd(ds)
        if w == 6:
            out[add_days(ds, -1)] = n + " (observed)"
        if w == 7:
            out[add_days(ds, 1)] = n + " (observed)"
    out[_nth_wd(y, 1, 1, 3)] = "Martin Luther King Jr. Day"
    out[_nth_wd(y, 2, 1, 3)] = "Washington's Birthday"
    out[_nth_wd(y, 5, 1, -1)] = "Memorial Day"
    out[_nth_wd(y, 9, 1, 1)] = "Labor Day"
    out[_nth_wd(y, 10, 1, 2)] = "Columbus Day"
    tg = _nth_wd(y, 11, 4, 4)
    out[tg] = "Thanksgiving"
    if key[1]:
        out[add_days(tg, 1)] = "Day after Thanksgiving"
    _HOL[key] = out
    return out


def holiday_name(ds: str, policy: dict | None = None) -> str:
    y = int(ds[:4])
    return holidays(y, policy).get(ds) or holidays(y + 1, policy).get(ds) or ""


# ------------------------------------------------------------------------------------------------ legal window of a local day
def day_window(st: dict | None, wd: int, ds: str, rules: dict) -> tuple[list | None, str]:
    P = rules["policy"]
    fed = P.get("fed") or [480, 1260]
    if P.get("noSunday") and wd == 7:
        return None, "Sunday: no calls"
    if P.get("federalHolidays"):
        h = holiday_name(ds, P)
        if h:
            return None, h + ": no calls"
    w = st["win"] if st and st.get("win") else fed
    if st and wd == 6 and "sat" in st:
        w = st["sat"]
    if st and wd == 7 and "sun" in st:
        w = st["sun"]
    if not w:
        return None, ("Sunday" if wd == 7 else "Saturday") + ": no sales calls in " + (st["name"] if st else "this state")
    s, e = max(w[0], fed[0]), min(w[1], fed[1])
    return ([s, e], "") if s < e else (None, "no legal hours that day")


def legal_in(ms: int, zones: list, st: dict | None, rules: dict) -> tuple[bool, str]:
    for z in zones:
        q = parts_in(ms, z)
        win, why = day_window(st, q["wd"], q["date"], rules)
        if not win:
            return False, why
        if q["min"] < win[0] or q["min"] >= win[1]:
            extra = f" ({st['name']} has two time zones and the city is not known: only hours legal in both count)" if len(zones) > 1 else ""
            return False, "their legal hours are " + span(win[0], win[1]) + extra
    return True, ""


# ------------------------------------------------------------------------------------------------ trades
_KEYS: dict = {}


def _trade_keys(rules: dict) -> list:
    k = id(rules)
    if k not in _KEYS:
        _KEYS[k] = [(tid, fold(raw).strip()) for tid, T in rules["trades"].items() for raw in T.get("keys", []) if fold(raw).strip()]
    return _KEYS[k]


def trade_of(lead: dict, rules: dict) -> str:
    t = s_(lead.get("trade")).lower()
    if t in rules["trades"]:
        return t
    for txt in (lead.get("trade"), lead.get("category"), lead.get("name")):
        if not txt:
            continue
        f = fold(" ".join(map(s_, txt)) if isinstance(txt, list) else txt)
        best, bl = None, 0
        for tid, k in _trade_keys(rules):
            hit = (" " + k + " ") in f if len(k) <= 3 else (" " + k) in f
            if hit and len(k) > bl:
                best, bl = tid, len(k)
        if best:
            return best
    return "other"


def trade_info(lead: dict, rules: dict) -> dict:
    return rules["trades"].get(lead.get("trade")) or rules["trades"]["other"]


# ------------------------------------------------------------------------------------------------ call windows
def next_window(lead: dict, now_ms: int, rules: dict, settings: dict | None = None, Z: dict | None = None) -> dict | None:
    Z = Z or zones_of(lead, rules, settings)
    if not Z["zones"]:
        return None
    st, T, z0 = rules["states"].get(Z["state"]), trade_info(lead, rules), Z["zones"][0]
    today = parts_in(now_ms, z0)["date"]
    for i in range(rules["policy"].get("searchDays") or 14):
        ds = add_days(today, i)
        wd = iso_wd(ds)
        if wd not in T["days"]:
            continue
        win, _ = day_window(st, wd, ds, rules)
        if not win:
            continue
        lo = max(zoned_to_utc(ds, win[0], z) for z in Z["zones"])
        hi = min(zoned_to_utc(ds, win[1], z) for z in Z["zones"])
        if not lo < hi:
            continue
        for w in T["win"]:
            s = max(lo, zoned_to_utc(ds, w[0], z0))
            e = min(hi, zoned_to_utc(ds, w[1], z0))
            if e <= now_ms:
                continue
            s = max(s, now_ms)
            if e - s >= 10 * 60_000:
                return {"start": s, "end": e, "date": ds, "wd": wd}
    return None


def when_words(ms: int, tz: str, now_ms: int | None = None) -> str:
    q, n = parts_in(ms, tz), parts_in(ms if now_ms is None else now_ms, tz)
    if q["date"] == n["date"]:
        return "today " + clock(q["min"])
    if q["date"] == add_days(n["date"], 1):
        return "tomorrow " + clock(q["min"])
    return f"{DOW3[q['wd']]} {MON3[q['m']]} {q['d']}, {clock(q['min'])}"


def date_words(ms: int, tz: str) -> str:
    q = parts_in(ms, tz)
    return f"{DOW3[q['wd']]} {MON3[q['m']]} {q['d']}"


def window_status(lead: dict, now_ms: int, rules: dict, settings: dict | None = None) -> dict:
    Z, T = zones_of(lead, rules, settings), trade_info(lead, rules)
    if not Z["zones"]:
        return {"code": "nozone", "text": "Add the state: their time zone is unknown, so the copilot cannot check the hours.", "legal": False, "zones": [], "next": None, "local": ""}
    st, z0 = rules["states"].get(Z["state"]), Z["zones"][0]
    q = parts_in(now_ms, z0)
    ok, why = legal_in(now_ms, Z["zones"], st, rules)
    in_trade = q["wd"] in T["days"] and any(w[0] <= q["min"] < w[1] for w in T["win"])
    nxt = next_window(lead, now_ms, rules, settings, Z)
    local = f"{DOW3[q['wd']]} {clock(q['min'])}"
    base = {"zones": Z["zones"], "how": Z["how"], "state": Z["state"], "local": local, "legal": ok, "next": nxt, "allParty": bool(st and st.get("allParty"))}
    if ok and in_trade:
        return {**base, "code": "best", "text": f"Good time to call: {local} their time."}
    if ok:
        best = f" Best: {when_words(nxt['start'], z0, now_ms)} their time." if nxt else ""
        return {**base, "code": "ok", "text": f"Legal now ({local} their time), not the best time for {T['plural']} (avoid {T['avoid']}).{best}"}
    nx = f" Next good time: {when_words(nxt['start'], z0, now_ms)} their time." if nxt else ""
    return {**base, "code": "closed", "text": f"Not now: {why}.{nx}"}


# ------------------------------------------------------------------------------------------------ leads in
def _pick(o: dict, names) -> str:
    for n in names:
        v = o.get(n)
        if isinstance(v, list):
            if v:
                return " ".join(map(s_, v))
            continue
        if v is not None and s_(v) != "":
            return v
    return ""


def _dnc_word(v) -> str:
    if v is True:
        return "listed"
    s = s_(v).lower()
    if s in ("listed", "dnc", "yes", "y", "true", "1", "on", "blocked", "registered"):
        return "listed"
    if s in ("clear", "clean", "no", "n", "false", "0", "ok", "checked", "not listed", "scrubbed"):
        return "clear"
    return "unchecked"


def _line_word(v) -> str:
    s = s_(v).lower()
    if re.search(r"mobile|cell|wireless", s):
        return "mobile"
    if re.search(r"business|landline|fixed|office", s):
        return "business"
    return "voip" if "voip" in s else "unknown"


def _site_issue(v) -> str:
    """Team B1's lead finder grades the current site (site_status): none / bad / fair -> the reason the script gives on the call (same as callcore.js)."""
    s = s_(v).lower()
    if s == "none":
        return "you do not have a website yet, so people who search on their phone find a competitor first"
    if s in ("bad", "fair"):
        return "your current site has a few problems that cost you customers on a phone"
    return ""


def _date_only(v) -> str:
    s = s_(v)
    return s[:10] if re.match(r"\d{4}-\d{2}-\d{2}", s) else ""


def _slug(v) -> str:
    return fold(v).strip().replace(" ", "-")[:40]


ADDR1 = re.compile(r",\s*([^,]+?),\s*([A-Za-z]{2})\s+\d{5}(?:-\d{4})?\b")
ADDR2 = re.compile(r",\s*([^,]+?),\s*([A-Za-z]{2})\s*(?:,|$)")


def norm_lead(raw, rules: dict, i: int = 0) -> dict | None:
    """One lead from any shape team B1 (or a CSV) gives; the same keys as callcore.js normLead (the phone imports this JSON as is)."""
    if not isinstance(raw, dict):
        return None
    src = {**(raw.get("tags") if isinstance(raw.get("tags"), dict) else {}), **(raw.get("address") if isinstance(raw.get("address"), dict) else {}), **raw}
    name = s_(_pick(src, ["name", "business", "business_name", "businessName", "company", "title"]))
    phone_raw = s_(_pick(src, ["phone_e164", "phone", "phone_number", "phoneNumber", "tel", "telephone", "formatted_phone_number", "international_phone_number", "contact:phone", "mobile"]))
    phone = norm_phone(phone_raw)
    if not name and not phone:
        return None
    state = state_code(_pick(src, ["state", "state_code", "region", "province", "addr:state", "administrative_area_level_1"]), rules)
    city = s_(_pick(src, ["city", "town", "locality", "addr:city", "municipality"]))
    full = s_(raw["address"] if isinstance(raw.get("address"), str) else _pick(src, ["formatted_address", "full_address", "vicinity"]))
    if (not state or not city) and full:
        m = ADDR1.search(full) or ADDR2.search(full)
        if m:
            state = state or state_code(m.group(2), rules)
            city = city or s_(m.group(1))
    tz = s_(_pick(src, ["tz", "timezone", "time_zone"]))
    ctr = raw.get("consentText")
    if isinstance(ctr, dict) and ctr.get("on"):
        ct = {"on": _date_only(ctr["on"]) or s_(ctr["on"])[:10], "how": s_(ctr.get("how"))[:120] or "imported"}
    elif truthy(_pick(src, ["text_consent", "textConsent", "sms_consent", "consent_text"])):
        ct = {"on": _date_only(_pick(src, ["text_consent_on", "consent_on"])), "how": s_(_pick(src, ["text_consent_how", "consent_how"]))[:120] or "imported"}
    else:
        ct = None
    email = s_(_pick(src, ["email", "e-mail", "contact:email", "mail"]))
    try:
        cb = int(float(raw.get("callbackAt") or 0))
        da = int(float(raw.get("demoAt") or 0))
    except (TypeError, ValueError):
        cb = da = 0
    lead = {
        "id": s_(_pick(src, ["id", "lead_id", "leadId", "place_id", "osm_id"])) or ("p" + phone[2:] if phone else f"n-{_slug(name + ' ' + city)}-{i}"),
        "name": name or pretty_phone(phone), "phone": phone, "phoneRaw": phone_raw, "contact": s_(_pick(src, ["contact", "contact_name", "contactName", "owner", "owner_name", "manager"]))[:80],
        "email": email if valid_email(email) else "", "website": s_(_pick(src, ["website", "url", "site", "web", "contact:website"]))[:300],
        "demo": s_(_pick(src, ["demo", "demo_url", "demoUrl", "demo_site", "preview", "preview_url", "previewUrl", "mockup"]))[:300],
        "city": city[:80], "state": state, "zip": s_(_pick(src, ["zip", "postcode", "postal_code", "zipcode", "addr:postcode"]))[:10], "tz": tz if valid_tz(tz) else "",
        "category": s_(_pick(src, ["category", "category_label", "categories", "type", "types", "industry", "kind", "amenity", "shop", "craft", "office", "healthcare", "leisure"]))[:120],
        "trade": "", "dnc": _dnc_word(_pick(src, ["dnc", "scrub", "dnc_status", "dncStatus"])), "dncChecked": _date_only(_pick(src, ["dncChecked", "dnc_checked", "scrubbed_on", "scrubbedOn"])),
        "lineType": _line_word(_pick(src, ["lineType", "line_type", "phone_type", "phoneType"])), "lineConfirmed": _date_only(_pick(src, ["lineConfirmed", "line_confirmed"])),
        "consentText": ct, "optout": truthy(_pick(src, ["optout", "opt_out", "do_not_call", "doNotCall"])), "emailOptOut": truthy(_pick(src, ["emailOptOut", "email_optout", "unsubscribed"])),
        "issue": s_(_pick(src, ["issue", "site_issue", "siteIssue", "pitch_issue", "problem"]))[:200] or _site_issue(_pick(src, ["site_status", "siteStatus"])),
        "source": s_(_pick(src, ["source", "found_on", "via"]))[:60], "finder": s_(_pick(src, ["finder", "why"]))[:220],
        "notes": s_(_pick(src, ["notes", "note"]))[:500], "stage": s_(raw.get("stage")) or "new", "callbackAt": cb, "demoAt": da,
    }
    lead["trade"] = trade_of({"trade": _pick(src, ["trade"]), "category": lead["category"], "name": lead["name"]}, rules)
    return lead


def _fill_empty(a: dict, b: dict) -> dict:
    for k, v in b.items():
        if a.get(k) in ("", None) and v not in ("", None):
            a[k] = v
    if b.get("dnc") == "listed":
        a["dnc"] = "listed"
    if b.get("optout"):
        a["optout"] = True
    return a


def norm_leads(items, rules: dict) -> tuple[list, int, int]:
    out, by_phone, dupes, skipped = [], {}, 0, 0
    for i, raw in enumerate(items if isinstance(items, list) else []):
        L = norm_lead(raw, rules, i)
        if not L:
            skipped += 1
            continue
        if L["phone"] and L["phone"] in by_phone:
            _fill_empty(by_phone[L["phone"]], L)
            dupes += 1
            continue
        if L["phone"]:
            by_phone[L["phone"]] = L
        out.append(L)
    return out, dupes, skipped


# ------------------------------------------------------------------------------------------------ Do Not Call, opt-outs, limits
def dnc_state(lead: dict, now_ms: int, rules: dict) -> str:
    if lead.get("dnc") == "listed":
        return "listed"
    if lead.get("dnc") != "clear":
        return "unchecked"
    try:
        t = datetime.strptime(s_(lead.get("dncChecked")), "%Y-%m-%d").replace(hour=12, tzinfo=timezone.utc).timestamp() * 1000
    except ValueError:
        return "expired"
    return "clear" if now_ms - t <= (rules["policy"].get("dncMaxAgeDays") or 31) * DAY else "expired"


def needs_confirm(lead: dict, now_ms: int, rules: dict) -> bool:
    return dnc_state(lead, now_ms, rules) != "clear" and not lead.get("lineConfirmed")


def attempt_times(log: list, lead_id: str) -> list:
    return sorted(e["t"] for e in (log or []) if e.get("id") == lead_id and (e.get("k") == "dial" or (e.get("k") in CALL_KINDS and not e.get("dial"))))


def callback_due(lead: dict, now_ms: int) -> bool:
    cb = lead.get("callbackAt") or 0
    return lead.get("stage") == "callback" and cb > 0 and cb - 15 * 60_000 <= now_ms <= cb + 2 * DAY


def block_of(lead: dict, st: dict, now_ms: int, rules: dict) -> dict | None:
    """Why this lead must not be called now (same codes and order as callcore.js blockOf), or None."""
    if not lead.get("phone"):
        return {"code": "nophone", "text": "No valid US phone number."}
    opt = (st or {}).get("optouts") or []
    if lead.get("optout") or lead.get("stage") == "dnc" or lead["phone"] in opt:
        return {"code": "optout", "text": "Asked not to be called: never call, text or email again.", "lock": True}
    if lead.get("dnc") == "listed":
        return {"code": "dnc", "text": "On the National Do Not Call list: do not call (the number may be personal).", "lock": True}
    if lead.get("stage") == "won":
        return {"code": "client", "text": "Already a client: no cold calls."}
    log = (st or {}).get("log") or []
    Z = zones_of(lead, rules, (st or {}).get("settings"))
    tz = Z["zones"][0] if Z["zones"] else "America/New_York"
    sr = rules["states"].get(Z["state"]) or {}
    if lead.get("stage") == "notinterested":
        ni = max((e["t"] for e in log if e.get("id") == lead["id"] and e.get("k") == "notinterested"), default=0)
        until = ni + (rules["policy"].get("restDays") or 180) * DAY
        if now_ms < until:
            return {"code": "rest", "text": f"Said not interested: rest until {date_words(until, tz)}.", "until": until}
    tries = attempt_times(log, lead["id"])
    cap = min(rules["policy"].get("cap24h") or 3, sr.get("max24") or 99)
    if sum(1 for t in tries if 0 <= now_ms - t < DAY) >= cap:
        return {"code": "cap", "text": f"{cap} calls in 24 hours: the legal limit. Wait a day."}
    today = parts_in(now_ms, tz)["date"]
    if sum(1 for t in tries if parts_in(t, tz)["date"] == today) >= (rules["policy"].get("maxPerDay") or 1) and not callback_due(lead, now_ms):
        return {"code": "today", "text": "Called today already: one call a day. Try tomorrow."}
    return None


# ------------------------------------------------------------------------------------------------ the script
def fill(tpl: str, v: dict, script: dict) -> str:
    F = script.get("fallback") or {}

    def one(m):
        x = s_(v.get(m.group(1))) if v else ""
        return x or s_(F.get(m.group(1)))
    out = re.sub(r"\{(\w+)\}", one, s_(tpl) if tpl is not None else "")
    out = re.sub(r"[ \t]{2,}", " ", out)
    return re.sub(r" ([,.?!:])", r"\1", out)


TITLES = ("dr", "mr", "mrs", "ms", "miss", "mx", "prof")


def _first(v) -> str:
    """How to greet a contact: the first name, or the title and last name ("Dr. Anita Patel" -> "Dr. Patel"), same as callcore.js first()."""
    p = s_(v).split()
    if not p:
        return ""
    return f"{p[0]} {p[-1]}" if len(p) > 1 and p[0].lower().rstrip(".") in TITLES else p[0]


def next_day_name(lead: dict, now_ms: int, rules: dict, settings: dict | None = None) -> str:
    Z = zones_of(lead, rules, settings)
    if not Z["zones"]:
        return "tomorrow"
    z0 = Z["zones"][0]
    today = parts_in(now_ms, z0)["date"]
    nx = next_window(lead, zoned_to_utc(add_days(today, 1), 0, z0), rules, settings, Z)
    if not nx:
        return "next week"
    return "tomorrow" if nx["date"] == add_days(today, 1) else DOW[nx["wd"]]


def vars_for(lead: dict, settings: dict | None, rules: dict, script: dict, now_ms: int) -> dict:
    S, T = settings or {}, trade_info(lead, rules)
    my_phone = norm_phone(S.get("phone"))
    price = s_(S.get("price"))
    return {
        "me": s_(S.get("me")) if _first(S.get("me")) else "", "myBiz": S.get("biz"), "myCity": S.get("city") or lead.get("city"),
        "myPhone": pretty_phone(my_phone) if my_phone else s_(S.get("phone")), "myEmail": S.get("email"), "myAddress": S.get("address"), "mySite": S.get("site"),
        "biz": lead.get("name"), "contact": lead.get("contact"), "contactName": _first(lead.get("contact")), "contactOrOwner": lead.get("contact"),
        "contactAsk": f"is this {_first(lead.get('contact'))}?" if s_(lead.get("contact")) else "could I speak with the owner, please?",
        "city": lead.get("city"), "plural": T["plural"], "word": T["word"], "ask": T["ask"], "goal": T["goal"], "hook": T["hook"],
        "issue": lead.get("issue") or T["issue"], "source": lead.get("source"), "day": next_day_name(lead, now_ms, rules, S),
        "demoOrOffer": lead.get("demo"), "price": price,
        "priceLine": f"My sites for {T['plural']} start at {price}, and one new customer a month usually covers it." if price else "",
    }


def script_for(lead: dict, settings: dict | None, rules: dict, script: dict, now_ms: int) -> dict:
    v = vars_for(lead, settings, rules, script, now_ms)

    def f(t):
        return fill(t, v, script)
    return {
        "opener": f(script["opener"]), "why": f(script["why"]), "questions": [f(q) for q in script["questions"]], "close": f(script["close"]),
        "consent": f(script["consent"]), "book": f(script["book"]),
        "objections": [{"key": o["key"], "title": o["title"], "lines": [x for x in (f(t) for t in o["lines"]) if x]} for o in script["objections"]],
        "vm1": f(script["voicemail"]["vm1"]), "vm2": f(script["voicemail"]["vm2"]), "vmRule": script["voicemail"]["rule"], "vars": v,
    }


# ------------------------------------------------------------------------------------------------ the National Do Not Call download (PC only)
def parse_dnc_file(text: str) -> tuple[set, set]:
    """The FTC registry download (one number per line, '813,5550142' or '8135550142' or formatted): -> (numbers E.164, area codes seen)."""
    nums, codes = set(), set()
    for line in (text or "").splitlines():
        d = re.sub(r"\D", "", line)
        p = norm_phone(d) if len(d) in (10, 11) else ""
        if p:
            nums.add(p)
            codes.add(area_code(p))
    return nums, codes


def apply_dnc(leads: list, nums: set, codes: set, today: str) -> dict:
    """Mark leads whose area code the download covers: on it = 'listed' (locked), not on it = 'clear' (checked today, good for 31 days)."""
    n = {"listed": 0, "clear": 0, "not_covered": 0}
    for L in leads:
        if not L.get("phone"):
            continue
        if area_code(L["phone"]) not in codes:
            n["not_covered"] += 1
            continue
        if L["phone"] in nums:
            L["dnc"], L["dncChecked"] = "listed", today
            n["listed"] += 1
        else:
            if L.get("dnc") != "listed":
                L["dnc"], L["dncChecked"] = "clear", today
            n["clear"] += 1
    return n
