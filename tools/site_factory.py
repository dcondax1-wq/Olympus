"""Website Factory: one finished, phone-first concept site for every lead with no website.

    python tools/site_factory.py            build / refresh every site + the owner gallery
    python tools/site_factory.py --check    build into a temp folder, print the summary, change nothing

In:  tools/web_public/agency/leads/leads.json (the leads team's list: name, niche, category, town, phone, address, hours, osm link)
Out: tools/web_public/agency/f/<8-char id>/index.html   one self-contained site (inline CSS + SVG art, no photos, no fonts, < 100 KB)
     tools/web_public/agency/factory/index.html + sites.json   the owner-only gallery (noindex)
     tools/site_factory_ids.json   lead id -> its random 8-char folder (kept, so a link never changes once sent)

Honesty (owner 2026-11-20): only facts from the lead (name, town, phone, address, hours) + generic, true-for-the-niche sections.
No reviews, testimonials, awards, prices, licences, years or photos. Every page says "Concept made for <business> - not live,
not affiliated", is noindex/nofollow, sends no referrer, and lives on an unguessable path linked from nowhere but the gallery.
"""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
import secrets
import shutil
import sys
import tempfile
from urllib.parse import quote

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "tools", "web_public", "agency")
LEADS = os.path.join(WEB, "leads", "leads.json")
IDS = os.path.join(ROOT, "tools", "site_factory_ids.json")
# the agency band at the bottom of every concept page (lead 2026-11-20). Maryland bans cold AI calls: the assistant (day-caller) may
# only call a business that ASKS, so the page carries a consent form whose markup / text / endpoint day-caller supplies. Until then
# AGENCY["caller_html"] is empty and the page holds a clearly marked slot. No third-party form service, no secret in the page.
AGENCY = {"phone": "", "phone_label": "", "caller_html": "", "pay_url": "", "public_base": "", "agency_name": "", "agency_email": ""}
# the offer on every concept page (research/writeups/client-plan-2026-11-20.md); pay_url = the owner's payment link (owner step)
OFFER = "Starter $1,500 + $79/mo, or $149/mo with nothing upfront."
CODES = os.path.join(ROOT, "tools", "site_factory_codes.json")   # lead id -> short code (FR-27): printed on the postcards too, never changes
AGENCY_FILE = os.environ.get("SITE_FACTORY_AGENCY") or os.path.join(ROOT, "tools", "site_factory_agency.json")     # optional: {"phone": "+1...", "caller_html": "<form ...>"}
BUDGET = 100 * 1024
VERSION = "f1"

# ---------------------------------------------------------------- niches: the client's look + true, generic sections
# palette: bg, ink, soft, brand, brand2 (accent), on (text on brand)
NICHES = {
    "health": {"label": "Health", "pal": [("#f5fbfb", "#12302f", "#4a6665", "#0f7c79", "#7fd1c7", "#ffffff"),
                                          ("#f7f9fc", "#16243a", "#4d5b70", "#2a6fb0", "#9cc8f0", "#ffffff")],
               "cta": "Call to book", "icon": "tooth"},
    "food": {"label": "Restaurant / food", "pal": [("#fff8f1", "#2b1a12", "#6b5144", "#c2410c", "#fbbf6b", "#ffffff"),
                                                   ("#fbf7ef", "#23200f", "#5f5a3d", "#8a3b12", "#e9b949", "#ffffff"),
                                                   ("#fff6f6", "#2a1416", "#6a4a4d", "#b4232f", "#f4a259", "#ffffff")],
             "cta": "Call to order", "icon": "plate"},
    "auto": {"label": "Auto", "pal": [("#f4f6fa", "#111a2b", "#4a5468", "#1d3a6e", "#f59e0b", "#ffffff")],
             "cta": "Call the shop", "icon": "car"},
    "gym": {"label": "Gym / fitness", "pal": [("#f6f7f2", "#121411", "#4d5249", "#1f2a1c", "#a3e635", "#ffffff"),
                                              ("#f5f5f7", "#14141a", "#50505c", "#3f2b96", "#f97316", "#ffffff")],
            "cta": "Call to join", "icon": "dumbbell"},
    "beauty": {"label": "Salon / beauty", "pal": [("#fff7f8", "#2d1a22", "#6e5560", "#9d3b62", "#f3b6c5", "#ffffff")],
               "cta": "Call to book", "icon": "scissors"},
    "trades": {"label": "Trades / contractor", "pal": [("#f6f6f4", "#1c1f24", "#555b63", "#334155", "#f59e0b", "#ffffff")],
               "cta": "Call for a quote", "icon": "wrench"},
    "cleaning": {"label": "Cleaning", "pal": [("#f3fafd", "#10283a", "#4b6274", "#0e7490", "#86efac", "#ffffff")],
                 "cta": "Call to book", "icon": "sparkle"},
    "retail": {"label": "Retail", "pal": [("#f8f7fc", "#1b1730", "#55506e", "#4338ca", "#fb7185", "#ffffff")],
               "cta": "Call the store", "icon": "bag"},
    "pro": {"label": "Professional services", "pal": [("#f7f7f5", "#17202b", "#4f5966", "#1e3a5f", "#c8a45a", "#ffffff")],
            "cta": "Call the office", "icon": "brief"},
    "services": {"label": "Local services", "pal": [("#f5f9f7", "#13261f", "#4a5f57", "#17624a", "#9fd8b8", "#ffffff")],
                 "cta": "Call us", "icon": "sparkle"},
}

# category -> (niche, what we call it, sections). Sections are things that are true of ANY business of that kind, worded so
# nothing is promised that the business might not do (no menus, prices, insurers, brands, years).
CATS = {
    "dentist": ("health", "Dental office", [("Check-ups and cleanings", "Routine visits to keep teeth and gums healthy."),
                                            ("Everyday dental care", "Call to ask which treatments the office offers."),
                                            ("New patients", "Call the office to ask about booking a first visit.")]),
    "clinic": ("health", "Clinic", [("Appointments", "Call the clinic to book or to ask about a visit."),
                                    ("Questions before you come", "The front desk can tell you what to bring."),
                                    ("Find us", "Directions and the address are below.")]),
    "doctors": ("health", "Doctor's office", None), "pharmacy": ("health", "Pharmacy", None),
    "veterinary": ("health", "Veterinary clinic", [("Pet check-ups", "Routine visits for your animals."),
                                                   ("Appointments", "Call to book a visit or ask a question."),
                                                   ("Find us", "Directions and the address are below.")]),
    "restaurant": ("food", "Restaurant", [("Eat in", "Come by for a meal: hours are below."),
                                          ("Call ahead", "Call to ask about takeout or a table."),
                                          ("Find us", "The address and a map link are below.")]),
    "cafe": ("food", "Café", [("Coffee and more", "Stop in for a drink and a bite."),
                              ("Call ahead", "Call to ask what is on today."),
                              ("Find us", "The address and a map link are below.")]),
    "bar": ("food", "Bar", [("Drinks", "Come by: hours are below."),
                            ("Call ahead", "Call to ask about tonight."),
                            ("Find us", "The address and a map link are below.")]),
    "fast food": ("food", "Quick food", [("Quick meals", "Fast food, ready to go."),
                                         ("Call ahead", "Call to ask about an order."),
                                         ("Find us", "The address and a map link are below.")]),
    "ice cream": ("food", "Ice cream", [("Sweet treats", "Stop in for ice cream."),
                                        ("Call ahead", "Call to ask about today's flavors."),
                                        ("Find us", "The address and a map link are below.")]),
    "car wash": ("auto", "Car wash", [("Car wash", "Bring the car by for a wash."),
                                      ("Questions", "Call to ask about options and wait times."),
                                      ("Find us", "The address and a map link are below.")]),
    "auto_repair": ("auto", "Auto repair", [("Repairs and service", "Call to describe the problem and book a time."),
                                            ("Questions", "The shop can tell you what to expect."),
                                            ("Find us", "The address and a map link are below.")]),
    "fitness centre": ("gym", "Fitness center", [("Train", "Equipment and space to work out."),
                                                 ("Membership questions", "Call to ask about joining."),
                                                 ("Find us", "The address and a map link are below.")]),
    "sports centre": ("gym", "Sports center", [("Get active", "A place to play and train."),
                                               ("Questions", "Call to ask about times and joining."),
                                               ("Find us", "The address and a map link are below.")]),
    "dojo": ("gym", "Martial arts", [("Classes", "Martial arts training."),
                                     ("Try it", "Call to ask about class times and a first visit."),
                                     ("Find us", "The address and a map link are below.")]),
    "hairdresser": ("beauty", "Hair salon", [("Hair", "Cuts and styling."),
                                             ("Book", "Call to book a time."),
                                             ("Find us", "The address and a map link are below.")]),
    "beauty": ("beauty", "Beauty salon", None),
}
GENERIC = {
    "health": [("Appointments", "Call to book or ask a question."), ("Find us", "The address and a map link are below.")],
    "food": [("Come by", "Hours are below."), ("Call ahead", "Call to ask about an order."), ("Find us", "The address and a map link are below.")],
    "auto": [("Service", "Call to describe what the car needs."), ("Find us", "The address and a map link are below.")],
    "gym": [("Train", "Call to ask about joining."), ("Find us", "The address and a map link are below.")],
    "beauty": [("Book", "Call to book a time."), ("Find us", "The address and a map link are below.")],
    "trades": [("Get a quote", "Call to describe the job."), ("Service area", "Call to ask if they cover your street."),
               ("Find us", "The address and a map link are below.")],
    "cleaning": [("Cleaning", "Call to describe what needs cleaning."), ("Find us", "The address and a map link are below.")],
    "pro": [("Appointments", "Call the office to set up a time."), ("Questions", "Call to ask whether they can help with yours."),
            ("Find us", "The address and a map link are below.")],
    "services": [("How it works", "Call to describe what you need."), ("Find us", "The address and a map link are below.")],
    "retail": [("Shop", "Stop in: hours are below."), ("Questions", "Call to ask if something is in stock."),
               ("Find us", "The address and a map link are below.")],
}
CAT_ICON = {"clinic": "cross", "doctors": "cross", "pharmacy": "cross", "veterinary": "paw", "cafe": "cup", "bar": "glass",
            "ice cream": "cone", "dojo": "dumbbell"}
NICHE_ALIAS = {"fitness": "gym", "health": "health", "food": "food", "auto": "auto", "beauty": "beauty", "salon": "beauty",
               "trades": "trades", "contractor": "trades", "cleaning": "cleaning", "retail": "retail", "shop": "retail",
               "pro": "pro", "professional": "pro", "services": "services", "local": "services"}

# simple line icons (24x24, stroke = currentColor): the only "art" (no photos)
ICONS = {
    "tooth": '<path d="M7 3c-2.5 0-4 2-4 4.5 0 3 1.5 4.5 2 7 .5 3 1 6.5 2.5 6.5S9 18 10 16c.6-1.2 1.4-1.2 2 0 1 2 1.5 5 3 5s2-3.5 2.5-6.5c.5-2.5 2-4 2-7C19.5 5 18 3 15.5 3c-1.7 0-2.4 1-3.5 1S8.7 3 7 3z"/>',
    "plate": '<circle cx="12" cy="12" r="7"/><circle cx="12" cy="12" r="3.5"/><path d="M2 4v6M4 4v6M3 10v10M22 4c-1.5 1-2 3-2 6h2v10"/>',
    "car": '<path d="M3 16v-3l2-5h14l2 5v3H3z"/><circle cx="7" cy="17" r="1.8"/><circle cx="17" cy="17" r="1.8"/><path d="M5 12h14"/>',
    "dumbbell": '<path d="M2 12h20M5 8v8M8 6v12M16 6v12M19 8v8"/>',
    "scissors": '<circle cx="6" cy="6" r="3"/><circle cx="6" cy="18" r="3"/><path d="M8.5 7.5 20 19M8.5 16.5 20 5"/>',
    "wrench": '<path d="M14.7 6.3a4 4 0 0 0 5 5L22 14l-8 8-2.3-2.3a4 4 0 0 0-5-5L2 10l8-8 2.3 2.3a4 4 0 0 0 2.4 2z"/>',
    "sparkle": '<path d="M12 2l2 6 6 2-6 2-2 6-2-6-6-2 6-2 2-6zM19 15l1 3 3 1-3 1-1 3-1-3-3-1 3-1 1-3z"/>',
    "bag": '<path d="M5 8h14l-1 13H6L5 8z"/><path d="M9 8V6a3 3 0 0 1 6 0v2"/>',
    "brief": '<rect x="3" y="7" width="18" height="13" rx="2"/><path d="M9 7V5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2M3 13h18"/>',
    "cross": '<path d="M9 3h6v6h6v6h-6v6H9v-6H3V9h6V3z"/>',
    "paw": '<circle cx="5.5" cy="10" r="2"/><circle cx="9.5" cy="5.5" r="2"/><circle cx="14.5" cy="5.5" r="2"/><circle cx="18.5" cy="10" r="2"/><path d="M12 12c-3 0-6 4-6 6.5 0 2 2 2.5 3 2.5s1.8-.6 3-.6 2 .6 3 .6 3-.5 3-2.5C18 16 15 12 12 12z"/>',
    "cup": '<path d="M4 8h13v5a6 6 0 0 1-6 6h-1a6 6 0 0 1-6-6V8zM17 10h1.5a2.5 2.5 0 0 1 0 5H17M8 2v3M12 2v3"/>',
    "glass": '<path d="M5 3h14l-7 9-7-9zM12 12v8M8 21h8"/>',
    "cone": '<path d="M7 10l5 12 5-12"/><path d="M6.5 10a5.5 5.5 0 0 1 11 0z"/>',
    "phone": '<path d="M5 3h4l2 5-2.5 1.5a11 11 0 0 0 6 6L16 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 5a2 2 0 0 1 2-2z"/>',
    "pin": '<path d="M12 22s7-7 7-12a7 7 0 0 0-14 0c0 5 7 12 7 12z"/><circle cx="12" cy="10" r="2.5"/>',
    "clock": '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
}

DAYS = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]
DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

# words a concept site must never contain (no invented social proof): the test greps for the same list
BANNED = ["review", "testimonial", "rated", "stars", "award", "best in", "#1", "number one", "licensed", "certified", "insured",
          "years of experience", "since 19", "since 20", "trusted by", "voted", "guarantee"]


# national / regional chains: they almost always have a website even when the map does not list one -> the gallery says "check first"
CHAINS = ["bonefish", "glory days", "crunch fitness", "bruster", "exxon", "ymca", "america's best wings", "medstar", "med star",
          "anchor bar", "planet fitness", "anytime fitness", "orangetheory", "subway", "mcdonald",
          "burger king", "wendy", "taco bell", "domino", "papa john", "pizza hut", "starbucks", "dunkin", "chick-fil-a", "chipotle",
          "panera", "applebee", "olive garden", "red robin", "buffalo wild", "jiffy lube", "valvoline", "midas", "meineke", "firestone",
          "great clips", "supercuts", "sport clips", "aspen dental", "children's national", "advanced radiology", "kaiser permanente",
          "patient first", "minuteclinic", "cvs", "walgreens", "rite aid", "quest diagnostics", "labcorp", "concentra", "massage envy",
          "european wax", "h&r block", "jackson hewitt", "state farm", "allstate", "geico", "7-eleven", "wawa", "sheetz", "royal farms"]


def chain_of(name: str) -> bool:
    n = str(name or "").lower()
    return any(c in n for c in CHAINS)


def esc(s) -> str:
    return html.escape(str(s or ""), quote=True)


def niche_of(lead: dict) -> str:
    cat = str(lead.get("category") or "").lower()
    if cat in CATS:
        return CATS[cat][0]
    n = str(lead.get("niche") or "").lower()
    return NICHE_ALIAS.get(n, "retail")


def sections_of(lead: dict, niche: str):
    cat = str(lead.get("category") or "").lower()
    c = CATS.get(cat)
    raw = re.sub(r"[_]+", " ", str(lead.get("category") or "")).strip()
    kind = (c[1] if c else (raw[:1].upper() + raw[1:] if raw else NICHES[niche]["label"]))
    return kind, (c[2] if c and c[2] else GENERIC[niche])


def parse_hours(s: str):
    """OSM opening_hours (the simple forms) -> 7 rows [(day, 'text')], or None when anything is unclear (then: 'call for hours')."""
    s = str(s or "").strip()
    if not s:
        return None
    if s in ("24/7", "Mo-Su 00:00+", "Mo-Su 00:00-24:00"):
        return [(d, "Open 24 hours") for d in DAY_NAMES]
    out = {}
    tre = r"\d{1,2}:\d\d-\d{1,2}:\d\d"
    for part in re.split(r"\s*(?:;|\|\|)\s*", s):
        if not part:
            continue
        if re.fullmatch(tre + r"(?:,\s*" + tre + r")*", part):          # '11:00-22:00' = every day
            days, times = "Mo-Su", part
        else:
            m = re.fullmatch(r"((?:Mo|Tu|We|Th|Fr|Sa|Su)(?:[-,](?:Mo|Tu|We|Th|Fr|Sa|Su))*)\s+(off|closed|" + tre + r"(?:,\s*" + tre + r")*)", part)
            if not m:
                # 'Mo-Sa 11:00-24:00, Su 11:00-23:00' (comma between rules)
                sub = re.split(r",\s*(?=(?:Mo|Tu|We|Th|Fr|Sa|Su)\b)", part)
                if len(sub) > 1:
                    r = parse_hours("; ".join(sub))
                    if r is None:
                        return None
                    for d, t in r:
                        if t != "Closed" or d not in out:
                            out[d] = t
                    continue
                return None
            days, times = m.group(1), m.group(2)
        idx = set()
        for chunk in days.split(","):
            if "-" in chunk:
                a, b = chunk.split("-")
                i, j = DAYS.index(a), DAYS.index(b)
                k = i
                while True:
                    idx.add(k)
                    if k == j:
                        break
                    k = (k + 1) % 7
            else:
                idx.add(DAYS.index(chunk))
        if times in ("off", "closed"):
            txt = "Closed"
        else:
            spans = []
            for t in re.split(r",\s*", times):
                a, b = t.split("-")
                for x in (a, b):
                    h, mi = map(int, x.split(":"))
                    if h > 24 or mi > 59:
                        return None
                spans.append(fmt_t(a) + " - " + fmt_t(b))
            txt = ", ".join(spans)
        for i in idx:
            out[DAY_NAMES[i]] = txt
    if not out:
        return None
    return [(d, out.get(d, "Call to ask")) for d in DAY_NAMES]


def fmt_t(t: str) -> str:
    h, m = map(int, t.split(":"))
    if h in (0, 24):
        return "midnight" if m == 0 else "12:%02d am" % m
    ap = "am" if h < 12 else "pm"
    h12 = h % 12 or 12
    return ("%d" % h12 if m == 0 else "%d:%02d" % (h12, m)) + " " + ap


def tel(phone: str) -> str:
    d = re.sub(r"\D", "", str(phone or ""))
    if len(d) == 10:
        d = "1" + d
    return "+" + d if len(d) == 11 else ""


def street(addr: str, town: str) -> str:
    """'196, Suite 200 Thomas Johnson Drive, Frederick' -> a cleaner one-line address (the OSM order, de-duplicated town)."""
    a = re.sub(r"\s+", " ", str(addr or "")).strip(" ,")
    m = re.match(r"^(\d+[A-Za-z]?),\s*(Suite \S+)\s+(.*)$", a)      # 'number, Suite N Street' -> 'number Street, Suite N'
    if m:
        rest = m.group(3)
        st, _, tail = rest.partition(",")
        a = f"{m.group(1)} {st.strip()}, {m.group(2)}" + ("," + tail if tail else "")
    return a


def ensure_ids(leads, ids: dict) -> dict:
    used = set(ids.values())
    for L in leads:
        if L["id"] not in ids:
            while True:
                h = "".join(secrets.choice("abcdefghjkmnpqrstuvwxyz23456789") for _ in range(8))
                if h not in used:
                    break
            ids[L["id"]] = h
            used.add(h)
    return ids


def pick_pal(niche: str, lead_id: str):
    pals = NICHES[niche]["pal"]
    return pals[int(hashlib.sha256(lead_id.encode()).hexdigest(), 16) % len(pals)]


def icon(name: str, size=24, extra="") -> str:
    return (f'<svg viewBox="0 0 24 24" width="{size}" height="{size}" fill="none" stroke="currentColor" stroke-width="1.7" '
            f'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"{extra}>{ICONS[name]}</svg>')


CSS_V = "s1"     # the concept sites share one stylesheet (agency/f/site.css): 4,500 sites x 7 KB of the same CSS was 30 MB
CSS = """*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}body{margin:0;background:var(--bg);color:var(--ink);
font:16px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
a{color:var(--brand)}.wrap{max-width:640px;margin:0 auto;padding:0 18px}
.bar{position:sticky;top:0;z-index:5;background:color-mix(in srgb,var(--bg) 88%,transparent);backdrop-filter:blur(10px);
-webkit-backdrop-filter:blur(10px);border-bottom:1px solid var(--line)}
.bar .wrap{display:flex;align-items:center;gap:10px;min-height:56px;padding-top:env(safe-area-inset-top)}
.logo{width:34px;height:34px;border-radius:10px;background:var(--brand);color:var(--on);display:grid;place-items:center;flex:none}
.bar b{font-size:1rem;line-height:1.2;flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.call{display:inline-flex;align-items:center;justify-content:center;gap:8px;min-height:44px;padding:0 16px;border-radius:999px;
background:var(--brand);color:var(--on);text-decoration:none;font-weight:700;white-space:nowrap}
.call.ghost{background:transparent;color:var(--brand);border:2px solid var(--brand)}
.hero{position:relative;overflow:hidden;padding:44px 0 36px;isolation:isolate}
.hero:before,.hero:after{content:"";position:absolute;z-index:-1;border-radius:50%;filter:blur(40px);opacity:.55}
.hero:before{width:320px;height:320px;background:var(--brand2);top:-120px;right:-90px;animation:f1 14s ease-in-out infinite alternate}
.hero:after{width:260px;height:260px;background:var(--brand);opacity:.18;bottom:-140px;left:-80px;animation:f2 18s ease-in-out infinite alternate}
@keyframes f1{to{transform:translate(-40px,30px) scale(1.12)}}@keyframes f2{to{transform:translate(50px,-20px) scale(1.15)}}
.kind{display:inline-flex;align-items:center;gap:8px;font-size:.8rem;font-weight:700;letter-spacing:.06em;text-transform:uppercase;color:var(--brand)}
h1{font-size:clamp(2rem,9vw,3rem);line-height:1.05;margin:10px 0 10px;letter-spacing:-.02em}
.lead{color:var(--soft);font-size:1.08rem;margin:0 0 22px}
.ctas{display:flex;flex-wrap:wrap;gap:10px}.art{position:absolute;right:6px;bottom:6px;color:var(--brand);opacity:.13;z-index:-1}
.rise{animation:rise .7s cubic-bezier(.2,.7,.2,1) both}.rise.d1{animation-delay:.08s}.rise.d2{animation-delay:.16s}
@keyframes rise{from{opacity:0;transform:translateY(14px)}}
section{padding:26px 0;border-top:1px solid var(--line)}h2{font-size:1.3rem;margin:0 0 14px;letter-spacing:-.01em}
.grid{display:grid;gap:12px}.tile{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:16px}
.tile h3{margin:0 0 4px;font-size:1.02rem}.tile p{margin:0;color:var(--soft)}
.hours{width:100%;border-collapse:collapse}.hours td{padding:9px 0;border-bottom:1px solid var(--line)}.hours td+td{text-align:right;color:var(--soft)}
.hours tr.today td{font-weight:700;color:var(--ink)}
.row{display:flex;gap:12px;align-items:flex-start}.row svg{flex:none;color:var(--brand);margin-top:2px}
.muted{color:var(--soft)}.foot{padding:26px 0 calc(90px + env(safe-area-inset-bottom));font-size:.85rem;color:var(--soft)}
.dock{position:fixed;left:0;right:0;bottom:0;z-index:6;padding:10px 14px calc(10px + env(safe-area-inset-bottom));
background:color-mix(in srgb,var(--bg) 92%,transparent);backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);border-top:1px solid var(--line)}
.dock .call{width:100%;min-height:50px;font-size:1.05rem}
.call:focus-visible,a:focus-visible{outline:3px solid var(--brand2);outline-offset:2px}
@media (min-width:700px){.grid{grid-template-columns:repeat(3,1fr)}.dock{display:none}.foot{padding-bottom:30px}}
@media (prefers-reduced-motion:reduce){*,:before,:after{animation:none!important}}"""


def agency_cfg() -> dict:
    c = dict(AGENCY)
    try:
        c.update({k: v for k, v in json.load(open(AGENCY_FILE)).items() if k in AGENCY and isinstance(v, str)})
    except (OSError, ValueError):
        pass
    return c


CALLER_CSS = ("form.callme{display:grid;gap:10px;width:100%;margin-top:6px}form.callme label{display:grid;gap:4px;font-size:.92rem}"
              "form.callme input:not([type=checkbox]),form.callme select{font:inherit;min-height:44px;border:1px solid var(--line);border-radius:12px;"
              "padding:0 12px;background:#fff;color:var(--ink);width:100%}.callme-lede{color:var(--soft);margin:0}"
              ".callme-agree{display:flex!important;grid-template-columns:none!important;gap:10px;align-items:flex-start;font-size:.82rem;color:var(--soft)}"
              ".callme-agree input{width:22px;height:22px;flex:none;margin-top:2px}form.callme button{font:inherit;font-weight:700;min-height:48px;"
              "border:0;border-radius:999px;background:var(--brand);color:var(--on)}.callme-out{font-size:.9rem;color:var(--soft)}")


def caller_form(html_in: str, lead_id: str, name: str) -> str:
    """day-caller's consent form (tools/caller/siteform.py) with THIS site's lead id + business name in its two hidden fields."""
    out = html_in
    for field, val in (("lead_id", lead_id), ("business", name)):
        out, n = re.subn(r'(<input type="hidden" name="%s" value=")(")' % field, lambda m: m.group(1) + esc(val) + m.group(2), out, count=1)
        if not n:
            raise ValueError(f"caller_html has no hidden {field} field")
    return out


def ensure_codes(leads, codes: dict) -> dict:
    """a short, stable code per lead: 2 letters of the town + the next number for that town (FR-1, FR-2 ...); kept forever."""
    top = {}
    for v in codes.values():
        m = re.fullmatch(r"([A-Z]{2})-(\d+)", v)
        if m:
            top[m.group(1)] = max(top.get(m.group(1), 0), int(m.group(2)))
    for L in sorted(leads, key=lambda x: x["id"]):
        if L["id"] in codes:
            continue
        t = re.sub(r"[^A-Za-z]", "", str(L.get("town") or L.get("city") or "")).upper()
        pre = (t[:2] if len(t) >= 2 else "XX")
        top[pre] = top.get(pre, 0) + 1
        codes[L["id"]] = f"{pre}-{top[pre]}"
    return codes


def agency_band(name: str, lead_id: str = "", code: str = "") -> str:
    """'Like this site?' band: 'Call us' (the agency number, a placeholder until set) + 'Have our assistant call me' (day-caller's
    consent form, a marked slot until it arrives). Kept apart from the business's own buttons."""
    c = agency_cfg()
    t = tel(c["phone"])
    # lead 2026-11-20: the trading PC's address (Funnel) never goes on public pages, so the consent form stays OFF here; the band is the
    # agency number, answered by the inbound AI receptionist (only Twilio knows the PC endpoint). caller_form() is kept for later use.
    shown = esc(c["phone_label"] or c["phone"])
    # voice only (day-caller 2026-11-20: no SMS handling, texting needs 10DLC); 'AI' said up front, as on the call; no 'any time' promise
    call = (f'<a class="call" href="tel:{t}">{icon("phone", 18)}Call {shown}</a>' if t else
            '<span class="call ghost" aria-disabled="true" data-slot="agency-phone" style="opacity:.6">Call us (number coming)</span>')
    line = (f'<p data-line="1" style="margin:0 0 10px">Call {shown}: our AI assistant answers.</p>' if t else
            '<p data-line="0" style="margin:0 0 10px">Call us: our AI assistant answers (number coming).</p>')
    form = ""
    pay = c["pay_url"] if re.match(r"https://[\w.-]+/", c["pay_url"] or "") else ""
    claim = (f'<a class="call" data-claim="1" href="{esc(pay)}" rel="noopener noreferrer" target="_blank">Claim this site</a>' if pay else
             '<p data-claim="0" style="margin:0 0 10px;font-weight:700">Claim this site: call us</p>')
    return (f'<section class="agency" aria-labelledby="h-ag" data-agency="1"><h2 id="h-ag">Like this site for {esc(name)}?</h2>'
            f'<p class="muted" style="margin:0 0 10px">This is a free concept made by an independent web studio, not by the business. '
            f'If you own {esc(name)}, it can be yours.</p>'
            f'<p class="offer" style="margin:0 0 12px"><b>{esc(OFFER)}</b></p>{claim}{line}<div class="ctas">{call}{form}</div>'
            + (f'<p class="muted" data-code="{esc(code)}" style="margin:14px 0 0;font-size:.8rem">Your code: {esc(code)}</p>' if code else "")
            + '</section>')


def page(lead: dict, ids: dict, client: dict | None = None) -> str:
    """the concept page; client = the production version for a paying client (tools/client_deliver.py): their own words / services /
    logo / photos, indexable, canonical to their domain, no concept footer, no agency band"""
    niche = niche_of(lead)
    kind, secs = sections_of(lead, niche)
    cl = client or {}
    if cl.get("services"):
        secs = [(str(a)[:60], str(b)[:240]) for a, b in cl["services"]][:9]
    bg, ink, soft, brand, brand2, on = pick_pal(niche, lead["id"])
    N = dict(NICHES[niche], icon=CAT_ICON.get(str(lead.get("category") or "").lower(), NICHES[niche]["icon"]))
    name, town, state = lead.get("name", "").strip(), (lead.get("town") or lead.get("city") or "").strip(), (lead.get("state") or "").strip()
    place = town + (", " + state if state else "")
    phone, t = str(lead.get("phone") or "").strip(), tel(lead.get("phone"))
    addr = street(lead.get("address"), town)
    hours = parse_hours(lead.get("hours"))
    maps = lead.get("osm") if str(lead.get("osm", "")).startswith("https://www.openstreetmap.org/") else ""
    search_maps = "https://www.openstreetmap.org/search?query=" + quote(addr + (", " + state if state and state not in addr else ""))
    email = str(lead.get("email") or "").strip()
    email = email if re.fullmatch(r"[\w.+-]+@[\w-]+\.[\w.-]+", email) else ""
    call = (f'<a class="call" href="tel:{t}">{icon("phone", 18)}{esc(N["cta"])}</a>' if t else "")
    hero_line = (f"{esc(kind)} in {esc(town)}." + (" Call us or stop by." if t and addr else " Call us." if t else " Find us on the map."))
    if cl.get("tagline"):
        hero_line = esc(cl["tagline"])
    # no phone / no street address on the listing: never point at something the page does not have
    fixed = []
    for h, p in secs:
        if not t and (p.startswith("Call") or "front desk" in p):
            h, p = ("Stop by", "Use the map below to find us.") if addr else ("On the map", "Tap Open the map to see where we are.")
        if h == "Find us" and not addr:
            p = "Tap Open the map to see where we are."
        if all(p != q for _, q in fixed):
            fixed.append((h, p))
    secs = fixed
    tiles = "".join(f'<div class="tile"><h3>{esc(h)}</h3><p>{esc(p)}</p></div>' for h, p in secs)
    if hours:
        rows = "".join(f'<tr data-d="{i}"><td>{d}</td><td>{esc(x)}</td></tr>' for i, (d, x) in enumerate(hours))
        hours_html = (f'<table class="hours" aria-label="Opening hours">{rows}</table><p class="muted" style="margin:10px 0 0;font-size:.85rem">'
                      + ("Hours can change on holidays: call to check." if t else "Hours can change on holidays.") + "</p>")
    else:
        hours_html = '<p class="muted">Call to ask about today\'s hours.</p>' if t else '<p class="muted">Hours coming soon.</p>'
    visit = []
    if addr:
        visit.append(f'<div class="row">{icon("pin", 20)}<div><b>{esc(addr)}</b>' + (f'<br><span class="muted">{esc(place)}</span>' if town and town not in addr else "") + "</div></div>")
    if phone:
        visit.append(f'<div class="row">{icon("phone", 20)}<div><a href="tel:{t}"><b>{esc(phone)}</b></a></div></div>' if t else
                     f'<div class="row">{icon("phone", 20)}<div><b>{esc(phone)}</b></div></div>')
    btns = []
    if addr or maps:
        btns.append(f'<a class="call ghost" href="{esc(maps or search_maps)}" rel="noopener noreferrer" target="_blank">{icon("pin", 18)}Open the map</a>')
    if email:
        btns.append(f'<a class="call ghost" href="mailto:{esc(email)}?subject={quote("Question for " + name)}">Send an email</a>')
    desc = f"{kind} in {place}." + (f" Call {phone}." if phone else "")
    today_js = ('<script>(function(){var d=(new Date().getDay()+6)%7,r=document.querySelector(\'.hours tr[data-d="\'+d+\'"]\');'
                'if(r)r.className="today";var y=document.getElementById("y");if(y)y.textContent=new Date().getFullYear();})();</script>')
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
{('<meta name="robots" content="index, follow">' + chr(10) + '<link rel="canonical" href="' + esc(cl["canonical"]) + '">') if cl.get("canonical") else '<meta name="robots" content="noindex, nofollow, noarchive">' + chr(10) + '<meta name="referrer" content="no-referrer">'}
<meta name="color-scheme" content="light">
<meta name="theme-color" content="{bg}">
<title>{esc(name)} · {esc(town)}</title>
<meta name="description" content="{esc(desc)}">
<meta name="generator" content="site-factory {VERSION}">
<link rel="icon" href="data:image/svg+xml,{quote(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><rect width="24" height="24" rx="6" fill="{brand}"/><g fill="none" stroke="{on}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" transform="translate(3 3) scale(.75)">{ICONS[N["icon"]]}</g></svg>')}">
<style>:root{{--bg:{bg};--ink:{ink};--soft:{soft};--brand:{brand};--brand2:{brand2};--on:{on};--card:#ffffff;--line:color-mix(in srgb,{ink} 11%,transparent)}}{(chr(10) + CSS) if client else ""}</style>{"" if client else '<link rel="stylesheet" href="../site.css?v=' + CSS_V + '">'}
</head>
<body data-niche="{niche}">
<header class="bar"><div class="wrap">{('<img class="logo" src="' + esc(cl["logo"]) + '" alt="" width="34" height="34" style="object-fit:cover;background:none">') if cl.get("logo") else '<span class="logo">' + icon(N["icon"], 20) + '</span>'}<b>{esc(name)}</b>{call.replace('class="call"', 'class="call" style="min-height:38px;padding:0 13px;font-size:.9rem"', 1) if t else ""}</div></header>
<main>
<div class="hero"><div class="wrap">
<span class="kind rise">{icon(N["icon"], 16)}{esc(kind)} · {esc(town)}</span>
<h1 class="rise d1">{esc(name)}</h1>
<p class="lead rise d1">{hero_line}</p>
<div class="ctas rise d2">{call}{btns[0] if btns else ""}</div>
</div><span class="art">{icon(N["icon"], 150)}</span></div>
<div class="wrap">
<section aria-labelledby="h-what"><h2 id="h-what">What we do</h2><div class="grid">{tiles}</div></section>{('<section aria-labelledby="h-about"><h2 id="h-about">About us</h2><p>' + esc(cl["about"]) + '</p></section>') if cl.get("about") else ""}{('<section aria-labelledby="h-photos"><h2 id="h-photos">Photos</h2><div class="grid">' + "".join('<img src="' + esc(ph) + '" alt="' + esc(name) + '" loading="lazy" style="width:100%;border-radius:16px;aspect-ratio:4/3;object-fit:cover">' for ph in cl.get("photos", [])) + '</div></section>') if cl.get("photos") else ""}
<section aria-labelledby="h-hours"><h2 id="h-hours" class="row" style="align-items:center">{icon("clock", 22)}Hours</h2>{hours_html}</section>
<section aria-labelledby="h-visit"><h2 id="h-visit">{"Visit or call" if t and addr else "Call" if t else "Visit"}</h2><div class="grid" style="grid-template-columns:1fr">{"".join(visit)}</div>
<div class="ctas" style="margin-top:16px">{"".join(btns)}</div></section>
{"" if client else agency_band(name, lead["id"], lead.get("_code", ""))}
</div>
</main>
<footer class="foot"><div class="wrap">
<p style="margin:0 0 6px"><b>{esc(name)}</b> · {esc(place)}</p>
{('<p style="margin:0">© <span id="y"></span> ' + esc(name) + '</p>') if client else '<p style="margin:0 0 6px">Concept made for ' + esc(name) + ' - not live, not affiliated. A sample of what a site could look like; nothing here is an offer from the business.</p>' + chr(10) + '<p style="margin:0">Address, phone and hours: <a href="https://www.openstreetmap.org/copyright" rel="noopener noreferrer" target="_blank">© OpenStreetMap contributors</a>. <span id="y"></span></p>'}
</div></footer>
{f'<div class="dock">{call}</div>' if t else ""}
{today_js}
</body>
</html>
"""


# ---------------------------------------------------------------- the owner-only gallery
GALLERY_CSS = """*{box-sizing:border-box}body{margin:0;background:#f4f4f2;color:#1d1d1b;font:15px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
main{max-width:1100px;margin:0 auto;padding:calc(env(safe-area-inset-top) + 16px) 16px 40px}h1{margin:0 0 4px;font-size:1.6rem}
.sub{color:#666;margin:0 0 14px}.bar{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 14px}
.bar button,.bar input{font:inherit;min-height:40px;border-radius:999px;border:1px solid #ccc;background:#fff;padding:0 14px}
.bar button[aria-pressed=true]{background:#1d1d1b;color:#fff;border-color:#1d1d1b}.bar input{flex:1;min-width:160px}
.list{display:grid;gap:14px;grid-template-columns:repeat(auto-fill,minmax(250px,1fr))}
.c{background:#fff;border:1px solid #e3e3df;border-radius:16px;padding:12px;display:flex;flex-direction:column;gap:8px;min-width:0}
.c h2{font-size:1rem;margin:0;overflow-wrap:anywhere}.m{color:#666;font-size:.85rem}
.pv{position:relative;width:100%;aspect-ratio:390/700;overflow:hidden;border-radius:12px;border:1px solid #e3e3df;background:#fafafa}
.pv iframe{position:absolute;left:0;top:0;width:390px;height:700px;border:0;transform-origin:0 0;pointer-events:none}
.ok{font-size:.78rem;font-weight:700;color:#14612f}.w{font-size:.82rem;color:#8a4b00;background:#fff4e0;border-radius:8px;padding:6px 8px}.r{display:flex;gap:6px;flex-wrap:wrap}.r a,.r button{font:inherit;font-size:.85rem;min-height:36px;display:inline-flex;align-items:center;
padding:0 12px;border-radius:999px;border:1px solid #1d1d1b;background:#fff;color:#1d1d1b;text-decoration:none;cursor:pointer}
.r .p{background:#1d1d1b;color:#fff}.u{font:12px/1.3 ui-monospace,Menlo,monospace;color:#555;overflow-wrap:anywhere}
.toast{position:fixed;left:50%;bottom:calc(env(safe-area-inset-bottom) + 18px);transform:translateX(-50%);background:#1d1d1b;color:#fff;
padding:10px 16px;border-radius:999px;opacity:0;transition:opacity .2s}.toast.on{opacity:1}"""

GALLERY_JS = r"""(function(){'use strict';
var list=document.getElementById('list'),q=document.getElementById('q'),toast=document.getElementById('toast'),n=document.getElementById('n'),cur='all',D=[];
var BASE=location.href.replace(/factory\/(index\.html)?(\?.*)?(#.*)?$/,'');
function say(s){toast.textContent=s;toast.classList.add('on');setTimeout(function(){toast.classList.remove('on')},1800)}
function el(t,c,x){var e=document.createElement(t);if(c)e.className=c;if(x!=null)e.textContent=x;return e}
function fit(){Array.prototype.forEach.call(document.querySelectorAll('.pv'),function(p){var f=p.firstChild;if(f)f.style.transform='scale('+(p.clientWidth/390)+')'})}
var io='IntersectionObserver' in window?new IntersectionObserver(function(es){es.forEach(function(e){if(e.isIntersecting){var p=e.target;io.unobserve(p);
var f=document.createElement('iframe');f.src=p.getAttribute('data-src');f.title='Preview of '+p.getAttribute('data-name');f.setAttribute('tabindex','-1');
f.setAttribute('loading','lazy');f.setAttribute('sandbox','allow-scripts');p.appendChild(f);fit()}})},{rootMargin:'400px'}):null;
function copy(s){if(navigator.clipboard&&navigator.clipboard.writeText)return navigator.clipboard.writeText(s).then(function(){return true},function(){return false});return Promise.resolve(false)}
function draw(){list.textContent='';var s=(q.value||'').toLowerCase(),k=0;
D.forEach(function(x){if(cur==='ready'?!(x.ready&&!x.chain):(cur!=='all'&&x.niche!==cur))return;if(s&&(x.name+' '+x.town+' '+x.kind).toLowerCase().indexOf(s)<0)return;k++;
var url=BASE+x.path,c=el('article','c');c.appendChild(el('h2',null,x.name+(x.code?'  ·  '+x.code:'')));if(x.ready&&!x.chain)c.appendChild(el('div','ok','Ready to send: phone or street address'));c.appendChild(el('div','m',x.kind+' · '+x.town+(x.hours?' · hours':'')+(x.phone?' · phone':' · no phone on file')));
if(x.chain)c.appendChild(el('div','w','Probably a chain: it likely has a website. Check before you send.'));
var p=el('div','pv');p.setAttribute('data-src','../'+x.path);p.setAttribute('data-name',x.name);c.appendChild(p);if(io)io.observe(p);
c.appendChild(el('div','u',url));var r=el('div','r'),o=el('a','p','Open');o.href='../'+x.path;o.target='_blank';o.rel='noopener noreferrer';r.appendChild(o);
var b=el('button',null,'Copy link');b.type='button';b.onclick=function(){copy(url).then(function(ok){say(ok?'Link copied':'Long-press Open to copy')})};r.appendChild(b);
if(navigator.share){var sh=el('button',null,'Share');sh.type='button';sh.onclick=function(){navigator.share({title:x.name,url:url}).catch(function(){})};r.appendChild(sh)}
c.appendChild(r);list.appendChild(c)});n.textContent=k+' of '+D.length+' sites';fit()}
Array.prototype.forEach.call(document.querySelectorAll('.bar button'),function(b){b.onclick=function(){cur=b.getAttribute('data-n');
Array.prototype.forEach.call(document.querySelectorAll('.bar button'),function(x){x.setAttribute('aria-pressed',String(x===b))});draw()}});
q.oninput=draw;addEventListener('resize',fit);
fetch('sites.json',{cache:'no-store'}).then(function(r){return r.json()}).then(function(j){D=j.sites||[];draw()},function(){n.textContent='Could not load the list'});
})();"""


def gallery(sites) -> str:
    niches = sorted({s["niche"] for s in sites})
    chips = '<button type="button" data-n="all" aria-pressed="true">All</button><button type="button" data-n="ready" aria-pressed="false">Ready to send</button>' + "".join(
        f'<button type="button" data-n="{n}" aria-pressed="false">{esc(NICHES[n]["label"])}</button>' for n in niches)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="robots" content="noindex, nofollow, noarchive">
<meta name="referrer" content="no-referrer">
<meta name="color-scheme" content="light">
<title>Site Factory</title>
<style>{GALLERY_CSS}</style>
</head>
<body>
<main>
<h1>Site factory</h1>
<p class="sub">A finished concept site for every lead with no website. Send the business its link. Owner only: these pages are hidden from search and linked from nowhere else. <span id="n"></span></p>
<p class="sub">Before you send: search the name once (a chain or a Facebook page may already be its site). Most leads have no phone on the map, so walk in or use their social page.</p>
<div class="bar" role="group" aria-label="Filter by niche">{chips}<input id="q" type="search" placeholder="Search name or town" aria-label="Search"></div>
<div class="list" id="list"></div>
<div class="toast" id="toast" role="status" aria-live="polite"></div>
</main>
<script>{GALLERY_JS}</script>
</body>
</html>
"""


def ready(L: dict) -> bool:
    """worth a site now (lead 2026-11-21): a phone, or a full street address (house number + street) to mail a postcard to"""
    return bool(tel(L.get("phone"))) or bool(L.get("mailable")) or bool(re.match(r"\d+\w?,?\s+[A-Za-z]", str(L.get("street") or L.get("address") or "")))


def load_leads(only_ready: bool = False):
    """leads.json + the per-town files the leads team writes (agency/leads/towns/*.json), one row per id; only_ready = a phone or a
    full address (the rest get a site once the leads team finds one)."""
    rows = []
    for p in [LEADS] + sorted(__import__("glob").glob(os.path.join(os.path.dirname(LEADS), "towns", "*.json"))):
        try:
            d = json.load(open(p, encoding="utf-8"))
        except (OSError, ValueError):
            continue
        rows += d.get("leads", []) if isinstance(d, dict) else []
    # the county search (tools/web_leads_counties.py): only the leads marked build_site (the top N by $ score; repo size)
    for p in sorted(__import__("glob").glob(os.path.join(os.path.dirname(LEADS), "counties", "*.json"))):
        try:
            d = json.load(open(p, encoding="utf-8"))
        except (OSError, ValueError):
            continue
        rows += [L for L in (d.get("leads", []) if isinstance(d, dict) else []) if isinstance(L, dict) and L.get("build_site")]
    out, seen = [], set()
    for L in rows:
        if not isinstance(L, dict) or L.get("id") in seen:
            continue
        if isinstance(L.get("id"), str):
            seen.add(L["id"])
        if only_ready and not ready(L):
            continue
        if not isinstance(L, dict) or not L.get("id") or not str(L.get("name", "")).strip():
            continue
        if L.get("website"):                     # the factory is only for businesses with no website
            continue
        if not L.get("id") or not str(L.get("name", "")).strip():
            continue
        if chain_of(L.get("name")):              # chains have their own sites: no concept site (lead 2026-11-21)
            continue
        out.append(L)
    added = os.environ.get("SITE_FACTORY_ADDED") or os.path.join(ROOT, "tools", "agency_added_leads.json")    # day-a11y caller portal: businesses a caller found by hand (public facts)
    if os.path.exists(added):
        try:
            extra = json.load(open(added, encoding="utf-8")).get("leads", [])
        except (OSError, ValueError, AttributeError):
            extra = []
        have = {L["id"] for L in out}
        out += [L for L in extra if isinstance(L, dict) and isinstance(L.get("id"), str) and L["id"] not in have
                and str(L.get("name", "")).strip() and not L.get("website") and (not only_ready or ready(L))]
    return out


def _usd(L):
    try:
        from tools import lead_value as V
    except ImportError:
        sys.path.insert(0, ROOT)
        from tools import lead_value as V
    return V.score(L)


def build(web=WEB, ids_path=IDS, write_ids=True):
    leads = load_leads()
    ids = json.load(open(ids_path)) if os.path.exists(ids_path) else {}
    ids = ensure_ids(leads, ids)
    codes_path = os.path.join(os.path.dirname(ids_path), "site_factory_codes.json")
    src = codes_path if os.path.exists(codes_path) else CODES
    codes = ensure_codes(leads, json.load(open(src)) if os.path.exists(src) else {})
    fdir = os.path.join(web, "f")
    os.makedirs(fdir, exist_ok=True)
    keep, sites = set(), []
    for L in leads:
        h = ids[L["id"]]
        keep.add(h)
        d = os.path.join(fdir, h)
        os.makedirs(d, exist_ok=True)
        txt = page(dict(L, _code=codes[L["id"]]), ids)
        with open(os.path.join(d, "index.html"), "w", encoding="utf-8", newline="\n") as f:
            f.write(txt)
        n = niche_of(L)
        sites.append({"id": L["id"], "path": f"f/{h}/", "name": L["name"].strip(), "niche": n, "kind": sections_of(L, n)[0],
                      "town": (L.get("town") or L.get("city") or "").strip(), "phone": bool(tel(L.get("phone"))),
                      "hours": parse_hours(L.get("hours")) is not None, "bytes": len(txt.encode("utf-8")), "heat": L.get("heat", ""),
                      "chain": chain_of(L["name"]), "code": codes[L["id"]], "ready": ready(L),
                      "usd": _usd(L), "county": str(L.get("county") or "")})
    for x in os.listdir(fdir):                   # a lead that left the list: its site goes too
        p = os.path.join(fdir, x)
        if x not in keep and os.path.isdir(p) and re.fullmatch(r"[a-z2-9]{8}", x):
            shutil.rmtree(p)
    with open(os.path.join(fdir, "site.css"), "w", encoding="utf-8", newline="\n") as f:
        f.write(CSS + "\n")
    with open(os.path.join(fdir, "index.html"), "w", encoding="utf-8") as f:   # no folder listing at agency/f/
        f.write('<!doctype html><meta charset="utf-8"><meta name="robots" content="noindex, nofollow"><title>Not found</title><p>Not found.</p>\n')
    sites.sort(key=lambda s: (not s["ready"], s["chain"], -s["usd"], s["town"], s["name"].lower()))   # sendable, then the biggest $ first
    gdir = os.path.join(web, "factory")
    os.makedirs(gdir, exist_ok=True)
    # lead id -> its concept site, relative to agency/ (the outreach page + email autopilot link each lead to its own site)
    sdir = os.path.join(web, "sites")
    os.makedirs(sdir, exist_ok=True)
    with open(os.path.join(sdir, "index.json"), "w", encoding="utf-8") as f:
        json.dump({"v": 1, "kind": "site-factory-index", "note": "owner-facing only: not for search or app lists",
                   "sites": {s["id"]: s["path"] for s in sorted(sites, key=lambda x: x["id"])},
                   "codes": {s["id"]: s["code"] for s in sorted(sites, key=lambda x: x["id"])}}, f, indent=1)
        f.write("\n")
    with open(os.path.join(gdir, "sites.json"), "w", encoding="utf-8") as f:
        json.dump({"v": 1, "kind": "site-factory", "version": VERSION, "count": len(sites), "sites": sites}, f, indent=1)
        f.write("\n")
    with open(os.path.join(gdir, "index.html"), "w", encoding="utf-8") as f:
        f.write(gallery(sites))
    if write_ids:
        with open(codes_path, "w") as f:
            json.dump(dict(sorted(codes.items())), f, indent=1)
            f.write("\n")
        with open(ids_path, "w") as f:
            json.dump(dict(sorted(ids.items())), f, indent=1)
            f.write("\n")
    return sites


# ---------------------------------------------------------------- the neutral-host export (lead 2026-11-21)
# Before any postcard is mailed the concept sites move OFF the owner's GitHub Pages to a neutral host (a free Cloudflare Pages project or a
# separate GitHub org). --export <dir> writes the f/ tree as a standalone static site: its own landing page, robots, 404 and headers;
# nothing that points back at Olympus, the owner's handle or any PC address (checked before it writes, so a leak is never published).
FORBIDDEN = [r"github\.io/jarvis", r"\bolympus\b", r"jarvis", r"dcondax", r"demetrades", r"\.ts\.net\b", r"\b100\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",
             r"tailscale", r"ntfy", r"/agency/", r"\.\./\.\./"]   # ../../ = reaching outside the exported site


def landing(c: dict) -> str:
    named = bool(c["agency_name"].strip())
    name = esc(c["agency_name"].strip() or "Local web studio")
    t = tel(c["phone"])
    call = (f'<a class="call" href="tel:{t}">Call {esc(c["phone_label"] or c["phone"])}</a>' if t else "")
    robots = "index, follow" if named else "noindex, nofollow"
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="robots" content="{robots}">
<meta name="referrer" content="no-referrer">
<meta name="color-scheme" content="light">
<title>{name}</title>
<meta name="description" content="Simple, fast websites for local businesses.">
<style>*{{box-sizing:border-box}}body{{margin:0;background:#f6f5f1;color:#1d1d1b;font:17px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}}
main{{max-width:620px;margin:0 auto;padding:calc(env(safe-area-inset-top) + 48px) 20px 48px}}h1{{font-size:clamp(2rem,8vw,2.8rem);line-height:1.08;margin:0 0 12px;letter-spacing:-.02em}}
p{{color:#55534d;margin:0 0 14px}}.call{{display:inline-flex;align-items:center;min-height:48px;padding:0 20px;border-radius:999px;background:#1d1d1b;color:#fff;text-decoration:none;font-weight:700}}
ul{{padding-left:20px;color:#55534d}}footer{{margin-top:40px;font-size:.85rem;color:#8a877f}}</style>
</head>
<body>
<main>
<h1>{name}</h1>
<p>We build simple, fast, phone-first websites for local businesses: your hours, your phone, your address and a map, done for you.</p>
<ul><li>Made to read well on a phone</li><li>Click-to-call and directions</li><li>You see it finished before you decide</li></ul>
{call}
<footer>Got a link to a sample site made for your business? It was made by us as a free concept. Nothing goes live without you.</footer>
</main>
</body>
</html>
"""


def export(out_dir: str, web: str = WEB) -> int:
    """--export <dir>: the standalone site for the neutral host. Refuses (exit 2, writes nothing) without an https public_base."""
    c = agency_cfg()
    base = (c.get("public_base") or "").strip()
    # a neutral GitHub org's own <org>.github.io is fine; the owner's handle, Olympus or a PC address is not
    bad_base = r"dcondax|demetrades|olympus|jarvis|\.ts\.net|tailscale|\b100\.\d+\.\d+\.\d+"
    if not re.fullmatch(r"https://[a-z0-9.-]+\.[a-z]{2,}(/[\w.-]*)*/?", base, re.I) or re.search(bad_base, base, re.I):
        print("refused: set public_base (the neutral host, e.g. https://example-sites.pages.dev/) in tools/site_factory_agency.json first; "
              "it must be https and must not be a github.io / Olympus / PC address", file=sys.stderr)
        return 2
    base = base.rstrip("/") + "/"
    src = os.path.join(web, "f")
    files = {}
    for d in sorted(os.listdir(src)):
        p = os.path.join(src, d, "index.html")
        if re.fullmatch(r"[a-z2-9]{8}", d) and os.path.isfile(p):
            files[f"f/{d}/index.html"] = read_text(p)
    files["index.html"] = landing(c)
    try:                                         # the agency's own launch site (tools/agency_site.py) replaces the minimal landing
        sys.path.insert(0, ROOT)
        from tools import agency_site as AS
        files.update(AS.build_files(c, prefix="", base=base))
    except (ImportError, OSError, ValueError, KeyError) as e:
        print(f"note: agency site not added ({e}); the minimal landing is used", file=sys.stderr)
    files["404.html"] = '<!doctype html><meta charset="utf-8"><meta name="robots" content="noindex"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Not found</title><p style="font:17px system-ui;padding:40px 20px">Not found.</p>\n'
    files["f/index.html"] = files["404.html"]
    files["f/site.css"] = read_text(os.path.join(src, "site.css"))
    named = bool(c["agency_name"].strip())
    files["robots.txt"] = ("User-agent: *\nDisallow: /f/\nDisallow: /portal/\nSitemap: " + base + "sitemap.xml\n" if named else "User-agent: *\nDisallow: /\n")
    # Cloudflare Pages reads _headers (GitHub Pages ignores it; the pages' own noindex meta covers that host)
    files["_headers"] = ("/f/*\n  X-Robots-Tag: noindex, nofollow, noarchive\n  Referrer-Policy: no-referrer\n"
                         "/portal/*\n  X-Robots-Tag: noindex, nofollow, noarchive\n  Referrer-Policy: no-referrer\n") + \
        ("" if named else "/*\n  X-Robots-Tag: noindex, nofollow\n")
    files[".nojekyll"] = ""
    pf, perr = portal_files(c, base)
    if perr:
        print("refused: " + perr, file=sys.stderr)
        return 3
    files.update(pf)
    leaks = [(k, m.group(0)) for k, v in files.items() for m in [re.search("|".join(FORBIDDEN), v, re.I)] if m]
    if leaks:
        print("refused: these files point back at Olympus / the owner / a PC: " + ", ".join(f"{k} ({w})" for k, w in leaks[:8]), file=sys.stderr)
        return 3
    if os.path.isdir(out_dir):
        for x in os.listdir(out_dir):                 # a clean tree each time (keep a .git folder if the owner exports into a repo)
            if x == ".git":
                continue
            p = os.path.join(out_dir, x)
            shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
    for k, v in files.items():
        p = os.path.join(out_dir, *k.split("/"))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8", newline="\n") as f:
            f.write(v)
    n = sum(1 for k in files if k.startswith("f/") and k != "f/index.html")
    print(f"exported {n} sites to {out_dir} for {base} (landing {'indexed' if named else 'noindex until the agency is named'})")
    return 0


PORTAL = os.path.join(WEB, "portal")
PORTAL_FILES = ["index.html", "portal.css", "portal.js", "portalcore.js", "portal.json", "calllist.json"]


def _strip_comments(name: str, t: str) -> str:
    """the portal's notes name Olympus / the plan files: published copies keep the code only"""
    t = re.sub(r"<!--.*?-->", "", t, flags=re.S) if name.endswith(".html") else t
    if name.endswith((".css", ".js")):
        t = re.sub(r"/\*.*?\*/", "", t, flags=re.S)
    if name.endswith(".js"):
        t = "\n".join(ln for ln in t.split("\n") if not ln.lstrip().startswith("//"))
        t = re.sub(r"(?<=[;{}),\]])\s*//[^'\"`\n]*$", "", t, flags=re.M)      # trailing // notes after code (not inside strings with quotes)
    return t


def portal_files(c: dict, base: str):
    """day-a11y's caller portal (agency/portal/) for the neutral host at portal/: comments out, public_base + agency_number filled in
    portal.json, the site links pointed at <base>/f/<id>/ (on the neutral host the sites sit at the root, not under /agency/), and the
    runtime 'banned' list emptied (it spells out the owner's handle; the base was already checked here)."""
    if not os.path.isdir(PORTAL):
        return {}, ""
    out = {}
    for fn in PORTAL_FILES:
        p = os.path.join(PORTAL, fn)
        if not os.path.isfile(p):
            return {}, f"portal file missing: {fn}"
        t = read_text(p)
        if fn == "portal.json":
            j = json.loads(t)
            j["public_base"] = base.rstrip("/")
            j["agency_number"] = c.get("phone_label") or c.get("phone") or ""
            if c.get("agency_name"):
                j["agency"] = j.get("agency") or c["agency_name"]
            t = json.dumps(j, indent=1) + "\n"
        elif fn == "portalcore.js" and ("'/agency/' + p" in t or "BANNED" in t):
            return {}, "portalcore.js has the old site links or a name list: day-a11y fixed both at the source (<base>/f/<id>/, no names)"
        out["portal/" + fn] = _strip_comments(fn, t)
    return out, ""


def read_text(p: str) -> str:
    with open(p, encoding="utf-8") as f:
        return f.read()


def main(argv) -> int:
    if "--export" in argv:
        i = argv.index("--export")
        if i + 1 >= len(argv):
            print("usage: python tools/site_factory.py --export <dir>", file=sys.stderr)
            return 2
        return export(argv[i + 1])
    if "--check" in argv:
        with tempfile.TemporaryDirectory() as t:
            ip = os.path.join(t, "ids.json")
            if os.path.exists(IDS):
                shutil.copy(IDS, ip)
            sites = build(os.path.join(t, "agency"), ip)
    else:
        sites = build()
    from collections import Counter
    big = max((s["bytes"] for s in sites), default=0)
    print(f"{len(sites)} sites · niches {dict(Counter(s['niche'] for s in sites))} · with hours {sum(s['hours'] for s in sites)} · "
          f"largest {big / 1024:.1f} KB (budget {BUDGET // 1024} KB)")
    return 0 if big <= BUDGET else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
