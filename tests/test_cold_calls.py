"""Cold-call copilot (team B2, 2026-11-14): docs/COLD_CALLING_RULES.md, the phone page tools/web_public/agency/call.html (+ callcore.js, callrules.json,
callscript.json, call_fixture.json) and the PC twin agency/calls/ (core.py, build.py).

  a. static: the files, the OLYMPUS / AGORA kit lines, no markup from data, NO NETWORK SENDS (the page only reads its three JSON files; calls / emails /
     texts are tel: / mailto: / sms: links a human taps), the rules file (every state, windows inside 8 am-9 pm, the strict states), the script slots, the
     fixture is fictional, the rules doc, the out/ folder is git-ignored
  b. the PC twin (python): call windows by state / time zone / city / DST / holidays, the DNC flag and opt-outs lock a lead, the DNC download, the script
     fills from a lead, the call-list builder (B1's lead files -> call_list.json / csv, opt-outs that never shrink)
  c. node: callcore.js gives the SAME answers as core.py (windows, locks, leads, phones, trades, scripts, holidays), then the phone-only logic (one call a day,
     the 24-hour cap, callbacks, the 7-day plan, the funnel, CAN-SPAM email gate, text consent gate, import / export / merge, junk safety)
  d. Chromium 390 x 844 (and 375 x 667 LITE): the page renders (DEMO), the call screen (big text, 3 questions, objections, voicemail, one-tap outcomes),
     do-not-call locks for good, the import -> localStorage -> reload loop, text and email gates, every tap target >= 44 px, nothing sent off the page
    python -X utf8 -m tests.test_cold_calls --static                               (a, b, c: no browser)
    flock -w 2400 /tmp/olympus_browser.lock python -X utf8 -m tests.test_cold_calls  (everything)
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import agora_kit as AK  # noqa: E402
from agency.calls import core as PC  # noqa: E402
from agency.calls import build as PB  # noqa: E402

check = AK.check
D = os.path.join(AK.WEB, "agency")
R = PC.load_rules()
SC = PC.load_script()


def ms(s: str) -> int:
    return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp() * 1000)


def iso(m) -> str | None:
    return datetime.fromtimestamp(m / 1000, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if m else None


# ------------------------------------------------------------------------------------------------ a. static
def test_static():
    files = ["call.html", "call.css", "call.js", "callcore.js", "callrules.json", "callscript.json", "call_fixture.json", "call-icon.svg", "call.webmanifest"]
    check("a. the page files: " + ", ".join(files), all(os.path.isfile(os.path.join(D, n)) for n in files), [n for n in files if not os.path.isfile(os.path.join(D, n))])
    pc = [os.path.join(AK.ROOT, "agency", "calls", n) for n in ("__init__.py", "core.py", "build.py", ".gitignore")]
    check("a. the PC twin: agency/calls/__init__.py, core.py, build.py, .gitignore", all(os.path.isfile(p) for p in pc))
    html, js, core, css = (AK.read(os.path.join(D, n)) for n in ("call.html", "call.js", "callcore.js", "call.css"))
    lines = html.splitlines()
    i = next((n for n, ln in enumerate(lines) if "../olympus/olympus.js?v=o20" in ln), -1)
    check('a. the kit: olympus.css?v=o7, agora.css after it, call.css last; themes.js; olympus.js?v=o20 data-app="agency" with the intro tag on the next line; a11y, agora-ui, gate-nav, sfx',
          html.index("../olympus/olympus.css?v=o7") < html.index("../olympus/agora.css") < html.index("call.css") and "../olympus/themes.js?v=o9" in html
          and i >= 0 and 'data-app="agency"' in lines[i] and lines[i + 1].strip() == AK.INCLUDE and html.count("intro-app.js") == 1
          and all(x in html for x in ("../olympus/a11y.js", "../olympus/agora-ui.js", "../olympus/gate-nav.js", "../olympus/sfx.js?v=s4")))
    check("a. AGORA: <html data-theme=agora>, viewport-fit=cover, theme-color, the manifest, the icon, ONE h1 'Call copilot', a polite status line, the page is an ES module",
          '<html lang="en" data-theme="agora">' in html and all(x in html for x in ("viewport-fit=cover", 'name="theme-color"', 'rel="manifest" href="call.webmanifest"', 'rel="icon" href="call-icon.svg"', "apple-touch-icon"))
          and html.count("<h1") == 1 and ">Call copilot</h1>" in html and 'role="status"' in html and 'aria-live="polite"' in html and '<script type="module" src="call.js' in html)
    check("a. the call screen is a real dialog: role=dialog aria-modal, a Close button, four tabs (Script / Objections / Voicemail / Follow up), the outcome grid",
          'role="dialog" aria-modal="true"' in html and 'id="cClose"' in html and html.count('role="tab"') == 4 and 'id="outs"' in html)
    bad = [p for p in (r"\.innerHTML", r"outerHTML", r"insertAdjacentHTML", r"document\.write", r"\beval\s*\(", r"new Function", r"\bimport\s*\(") if re.search(p, js) or re.search(p, core)]
    check("a. no markup is ever built from data: no innerHTML / outerHTML / insertAdjacentHTML / document.write / eval / dynamic import", not bad, bad)
    fetches = set(re.findall(r"getJSON\('([^']+)'", js))
    check("a. NO NETWORK SENDS: the page reads only ./callrules.json, ./callscript.json, ./call_fixture.json and team B1's ./leads.json; no XHR / WebSocket / sendBeacon / POST / cookies / web address; fetch only inside getJSON",
          fetches == {"./callrules.json", "./callscript.json", "./call_fixture.json", "./leads.json"} and js.count("fetch(") == 1 and "fetch(" not in core
          and not re.search(r"XMLHttpRequest|WebSocket|sendBeacon|method:\s*['\"]POST|document\.cookie|https?://(?!www\.w3\.org)|navigator\.share|postMessage", js + core), sorted(fetches))
    check("a. calls / emails / texts only as links a human taps (tel: / mailto: / sms: built in callcore.js), never opened by code (no location.href = / window.open)",
          "'tel:'" in core and "'mailto:'" in core and "'sms:'" in core and not re.search(r"location\.(href|assign|replace)\s*[=(]|window\.open\(", js))
    check("a. callcore.js is pure (no document / window / fetch / localStorage) and Safari 16 safe (no lookbehind, no .at())",
          not re.search(r"\bdocument\.|\bwindow\.|\bfetch\(|\blocalStorage\b|\(\?<[=!]|\.at\(", re.sub(r"//[^\n]*", "", core)))
    check("a. the owner's data lives in ONE localStorage key (agency.calls.v1) and the page reads (never writes) team B1's shared keys",
          "export const KEY = 'agency.calls.v1';" in core and js.count("localStorage.setItem(") == 1 and "localStorage.setItem(C.KEY" in js)
    check("a. text only through textContent / createElement(NS); svg built with createElementNS", "textContent" in js and "createElementNS" in js)
    check("a. CSS: taps >= 44 px (outcomes 56), safe areas, 176 px clear of Jarvis's corner, reduced motion, LITE, big call text (opener 22 px, script 20 px)",
          css.count("min-height: 44px") >= 3 and "min-height: 56px" in css and "safe-area-inset" in css and "176px" in css and "prefers-reduced-motion" in css
          and 'data-oly-lite="1"' in css and re.search(r"\.say\.opener \{[^}]*22px", css) and re.search(r"\.say \{[^}]*20px", css))
    zi = re.search(r"\.sheet \{[^}]*z-index: (\d+)", css)
    check("a. the call screen sits above AGORA's compact app bar (z-index 70) and its sheets (81), so the bar never covers Close (found by the browser run)", zi and int(zi.group(1)) > 81, zi and zi.group(1))
    check("a. the AGORA look: no neon / glow / techno font / cyber words in the page's own files", not AK.BANNED_LOOK.search(css + js + core + html.split("</head>")[0].split("-->")[-1]), AK.BANNED_LOOK.findall(css + js)[:3])
    man = json.loads(AK.read(os.path.join(D, "call.webmanifest")))
    check("a. the manifest opens Call mode itself: start_url ./call.html, scope ./, standalone, portrait, the svg icon",
          man["start_url"] == "./call.html" and man["scope"] == "./" and man["display"] == "standalone" and man["orientation"] == "portrait" and man["icons"][0]["src"] == "call-icon.svg")
    svg = AK.read(os.path.join(D, "call-icon.svg"))
    check("a. call-icon.svg: an AGORA mark (no neon colours)", svg.lstrip().startswith("<svg") and "viewBox" in svg and not re.search(r"#(?:0ff|00f|f0f|0f0)\b|#00ffff|#ff00ff", svg, re.I))
    fx = json.loads(AK.read(os.path.join(D, "call_fixture.json")))
    fic = [L["phone"] for L in fx["leads"]] + fx.get("optouts", []) + [fx["settings"]["phone"]]
    check("a. the DEMO fixture says so (demo: true, 'not real') and EVERY number in it is a fictional 555-01xx number (never dialed); web addresses are example.com",
          fx.get("demo") is True and "not real" in fx["note"].lower() and all(PC.is_fictional(PC.norm_phone(p)) for p in fic)
          and all("example.com" in L.get("demo", "example.com") for L in fx["leads"]), [p for p in fic if not PC.is_fictional(PC.norm_phone(p))])
    # the rules file
    us = set("AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY".split())
    st = R["states"]
    zones_ok = all(PC.valid_tz(z) for s in st.values() for z in s["tz"]) and all(PC.valid_tz(z) for c in R["cities"].values() for z in c.values())
    inside = all(480 <= (s.get("win") or [480, 1260])[0] < (s.get("win") or [480, 1260])[1] <= 1260 for s in st.values())
    check("a. callrules.json: all 50 states + DC, every time zone real, every state window inside the federal 8 am-9 pm", us <= set(st) and zones_ok and inside, sorted(us - set(st)))
    check("a. the strict states as researched: FL / OK / MD 8-8 and 3 calls in 24 h; PA 9 am-7 pm, no Sundays or holidays (Act 47 of 2026); TX 9-9 and Sunday noon; RI weekdays 9-6, Saturday 10-5; KY 10 am; CT / NV 9 am; AL / LA no Sundays or holidays",
          all(st[k]["win"] == [480, 1200] and st[k]["max24"] == 3 for k in ("FL", "OK", "MD")) and st["PA"]["win"] == [540, 1140] and st["PA"]["sun"] is None and st["PA"]["hol"]
          and st["TX"]["win"] == [540, 1260] and st["TX"]["sun"] == [720, 1260] and st["RI"]["win"] == [540, 1080] and st["RI"]["sat"] == [600, 1020] and st["KY"]["win"][0] == 600
          and st["CT"]["win"][0] == 540 and st["NV"]["win"][0] == 540 and all(st[k]["sun"] is None and st[k]["hol"] for k in ("AL", "LA")))
    check("a. the one-line rule holds: weekdays 10 am-6 pm their time is inside every state's window (docs part '5 lines', rules5 line 1)",
          all((s.get("win") or [480, 1260])[0] <= 600 and (s.get("win") or [480, 1260])[1] >= 1080 for s in st.values()) and "10 am-6 pm" in R["rules5"][0],
          [k for k, s in st.items() if not ((s.get("win") or [480, 1260])[0] <= 600 and (s.get("win") or [480, 1260])[1] >= 1080)])
    P = R["policy"]
    check("a. the copilot's own policy: no Sundays, no federal holidays (+ the day after Thanksgiving), one call a day, at most 3 in 24 h, 180 days rest after 'not interested', DNC checks expire after 31 days",
          P["noSunday"] and P["federalHolidays"] and P["dayAfterThanksgiving"] and P["maxPerDay"] == 1 and P["cap24h"] == 3 and P["restDays"] == 180 and P["dncMaxAgeDays"] == 31)
    tr = R["trades"]
    check("a. trades: restaurants 2-4 pm (and 9:30-11), contractors 8-9 am and 4-6 pm, every window inside 8 am-9 pm on weekdays, an 'other' fallback",
          [840, 960] in tr["restaurant"]["win"] and tr["contractor"]["win"] == [[480, 540], [960, 1080]] and "other" in tr
          and all(480 <= w[0] < w[1] <= 1260 for T in tr.values() for w in T["win"]) and all(set(T["days"]) <= {1, 2, 3, 4, 5} for T in tr.values())
          and all(T.get("one") and T.get("plural") for T in tr.values()))
    cad = R["cadence"]
    check("a. the 7-day plan: day 1 call + voicemail 1 + email 1 ... day 7 last call + goodbye email; texts only on the consent step", [c["day"] for c in cad] == [1, 2, 3, 4, 5, 7]
          and cad[0]["vm"] == "vm1" and cad[0]["email"] == "e1" and cad[-1]["email"] == "e4" and [c.get("text") for c in cad if c.get("text")] == ["t2"])
    check("a. the rules in 5 lines are on the page (rules5)", len(R["rules5"]) == 5 and "$500" in " ".join(R["rules5"]) and "never the caller" in R["rules5"][4])
    # the script slots
    v = PC.vars_for(PC.norm_lead({"name": "X", "phone": "813-555-0142", "state": "FL"}, R), {}, R, SC, ms("2026-11-17T19:30:00Z"))
    txt = json.dumps(SC)
    slots = set(re.findall(r"\{(\w+)\}", txt))
    check("a. callscript.json: every {slot} is filled by the lead / settings / trade or has a fallback", slots <= set(v) | set(SC["fallback"]), sorted(slots - set(v) - set(SC["fallback"])))
    check("a. the script is honest: the opener says who you are and that it is a sales call; 'take me off' has its own answer; the voicemail rule bans recorded / AI drops",
          "{me} with {myBiz}" in SC["opener"] and "sales call" in SC["opener"] and any(o["key"] == "remove" for o in SC["objections"]) and "recorded, AI" in SC["voicemail"]["rule"])
    keys = {o["key"] for o in SC["objections"]}
    check("a. objection answers: I already have a site, too expensive, not interested, send me an email, who are you with, gatekeeper (+ how did you get my number, take me off)",
          {"have_site", "expensive", "not_interested", "email", "who", "gatekeeper", "how_number", "remove"} <= keys and all(len(o["lines"]) >= 2 for o in SC["objections"]))
    check("a. CAN-SPAM in every email (your name, postal address, an opt-out line) and 'Reply STOP to opt out' on every text",
          "{myAddress}" in SC["emailFooter"] and "{me}" in SC["emailFooter"] and "will not email you again" in SC["emailFooter"] and SC["textFooter"].strip() == "Reply STOP to opt out." and len(SC["emails"]) == 4)
    doc = AK.read(os.path.join(AK.ROOT, "docs", "COLD_CALLING_RULES.md"))
    need = ("not legal advice", "FCC 24-17", "prior express written consent", "Do Not Call", "Chennette", "Pennsylvania", "Act 47", "Florida", "Oklahoma", "CAN-SPAM", "$53,088",
            "10 business days", "all-party", "ringless voicemail", "10DLC", "$500", "$1,500", "receptionist", "Sources:")
    check("a. docs/COLD_CALLING_RULES.md covers the rules with sources and dates (TCPA, the FCC AI ruling, DNC + sole proprietors, mini-TCPAs, hours, recording, CAN-SPAM, texting, AI voice costs + consent, the AI receptionist)",
          all(n in doc for n in need) and len(re.findall(r"20\d\d-\d\d-\d\d", doc)) >= 30, [n for n in need if n not in doc])
    r = subprocess.run(["git", "check-ignore", "-q", "agency/calls/out/call_list.json"], cwd=AK.ROOT)
    check("a. agency/calls/out/ (the owner's call lists and opt-outs) is git-ignored", r.returncode == 0)
    secrets = re.search(r"sk-[A-Za-z0-9]{20}|AKIA[0-9A-Z]{16}|api[_-]?key\s*[:=]\s*['\"][^'\"]{12}", html + js + core + txt + AK.read(os.path.join(AK.ROOT, "agency", "calls", "core.py")), re.I)
    check("a. no secrets or account numbers anywhere in the copilot", not secrets)


# ------------------------------------------------------------------------------------------------ b. the PC twin
WINDOW_CASES = [  # (name, lead, now, settings, expected code, expected next start or None)
    ("FL restaurant, Tampa (two zones, city unknown), Tue 2:30 pm ET", {"name": "Taco Town", "phone": "813-555-0142", "city": "Tampa", "state": "FL", "category": "restaurant"}, "2026-11-17T19:30:00Z", {}, "best", "2026-11-17T19:30:00Z"),
    ("FL restaurant at 8:30 pm ET: closed (Florida ends at 8), next 9:30 am", {"name": "Taco Town", "phone": "813-555-0142", "city": "Tampa", "state": "FL", "category": "restaurant"}, "2026-11-18T01:30:00Z", {}, "closed", "2026-11-18T14:30:00Z"),
    ("FL Pensacola (Central) restaurant, 2:30 pm CT", {"name": "Gulf Grill", "phone": "850-555-0101", "city": "Pensacola", "state": "FL", "category": "restaurant"}, "2026-11-17T20:30:00Z", {}, "best", "2026-11-17T20:30:00Z"),
    ("TX El Paso (Mountain) roofer at 7:30 am MT: Texas starts at 9, next 4 pm MT", {"name": "El Paso Roofing", "phone": "915-555-0101", "city": "El Paso", "state": "TX", "category": "roofing contractor"}, "2026-11-17T14:30:00Z", {}, "closed", "2026-11-17T23:00:00Z"),
    ("TX Houston plumber at 8:30 am CT: closed until 9, next 4 pm CT", {"name": "Bayou Plumbing", "phone": "713-555-0101", "city": "Houston", "state": "TX", "category": "plumber"}, "2026-11-17T14:30:00Z", {}, "closed", "2026-11-17T22:00:00Z"),
    ("PA auto shop on Saturday 10 am ET: legal (Mon-Sat 9-7) but not a shop day", {"name": "Main Street Auto", "phone": "412-555-0166", "city": "Pittsburgh", "state": "PA", "category": "auto repair"}, "2026-11-21T15:00:00Z", {}, "ok", "2026-11-23T14:30:00Z"),
    ("PA auto shop on Sunday: closed", {"name": "Main Street Auto", "phone": "412-555-0166", "city": "Pittsburgh", "state": "PA", "category": "auto repair"}, "2026-11-22T15:00:00Z", {}, "closed", "2026-11-23T14:30:00Z"),
    ("CA nail salon on Thanksgiving: closed; the day after is off too, next Tuesday 9 am PT", {"name": "Glow Nails", "phone": "213-555-0181", "city": "Los Angeles", "state": "CA", "category": "nail salon"}, "2026-11-26T18:00:00Z", {}, "closed", "2026-12-01T17:00:00Z"),
    ("AZ diner (no daylight saving), 2:30 pm MST", {"name": "Sunset Diner", "phone": "602-555-0144", "city": "Phoenix", "state": "AZ", "category": "diner"}, "2026-11-17T21:30:00Z", {}, "best", "2026-11-17T21:30:00Z"),
    ("HI restaurant, 9:30 am HST", {"name": "Aloha Cafe", "phone": "808-555-0101", "city": "Honolulu", "state": "HI", "category": "cafe"}, "2026-11-17T19:30:00Z", {}, "best", "2026-11-17T19:30:00Z"),
    ("RI bookstore, Saturday 9:30 am: Rhode Island Saturdays start at 10", {"name": "Corner Books", "phone": "401-555-0158", "city": "Providence", "state": "RI", "category": "bookstore"}, "2026-11-21T14:30:00Z", {}, "closed", "2026-11-23T15:00:00Z"),
    ("KY Louisville salon at 9:15 am ET: Kentucky starts at 10, so the 9-10:30 slot opens at 10", {"name": "Derby Hair", "phone": "502-555-0101", "city": "Louisville", "state": "KY", "category": "hair salon"}, "2026-11-17T14:15:00Z", {}, "closed", "2026-11-17T15:00:00Z"),
    ("no state, no default: the hours cannot be checked", {"name": "Mystery Shop", "phone": "212-555-0101", "category": "boutique"}, "2026-11-17T16:00:00Z", {}, "nozone", None),
    ("no state, the owner's default NY: 11:00 am ET boutique (best 10-11:30)", {"name": "Mystery Shop", "phone": "212-555-0101", "category": "boutique"}, "2026-11-17T16:00:00Z", {"defaultState": "NY"}, "best", "2026-11-17T16:00:00Z"),
    ("an explicit time zone wins (Denver), 2:30 pm MT restaurant", {"name": "Mile High Tacos", "phone": "303-555-0101", "tz": "America/Denver", "category": "restaurant"}, "2026-11-17T21:30:00Z", {}, "best", "2026-11-17T21:30:00Z"),
    ("daylight saving (EDT after 2027-03-14): NY restaurant 2:30 pm EDT", {"name": "Joe's Pizza", "phone": "212-555-0102", "city": "New York", "state": "NY", "category": "pizza"}, "2027-03-15T18:30:00Z", {}, "best", "2027-03-15T18:30:00Z"),
    ("TN, city unknown (Central + Eastern): 8 am CT office is legal in both zones but too early, next 9 am CT", {"name": "Music Row Law", "phone": "615-555-0103", "state": "TN", "category": "law firm"}, "2026-11-17T14:00:00Z", {}, "ok", "2026-11-17T15:00:00Z"),
    ("MT contractor at 7:30 pm MT Monday: legal until 9 pm, next Tue 8 am MT", {"name": "Big Sky Fence", "phone": "406-555-0101", "city": "Billings", "state": "MT", "category": "fence contractor"}, "2026-11-17T02:30:00Z", {}, "ok", "2026-11-17T15:00:00Z"),
]


def test_python():
    for name, lead, now, sets, code, nxt in WINDOW_CASES:
        L = PC.norm_lead(lead, R)
        w = PC.window_status(L, ms(now), R, sets)
        got = (w["code"], iso(w["next"]["start"]) if w.get("next") else None)
        check(f"b. window: {name}", got == (code, nxt), (got, w.get("text")))
    t = ms("2026-11-17T19:30:00Z")
    base = {"name": "Taco Town", "phone": "813-555-0142", "city": "Tampa", "state": "FL", "category": "restaurant"}
    st = {"leads": [], "log": [], "optouts": [], "settings": {}}
    check("b. a clean lead is not locked", PC.block_of(PC.norm_lead(base, R), st, t, R) is None)
    for name, patch, want in (("dnc: 'listed' (on the National Do Not Call list)", {"dnc": "listed"}, "dnc"), ("dnc: true", {"dnc": True}, "dnc"), ("scrub: 'yes'", {"scrub": "yes"}, "dnc"),
                              ("optout: true", {"optout": True}, "optout"), ("do_not_call: 'yes'", {"do_not_call": "yes"}, "optout"), ("no phone number", {"phone": "555-0142"}, "nophone")):
        L = PC.norm_lead({**base, **patch}, R)
        b = PC.block_of(L, st, t, R)
        check(f"b. the DNC / opt-out flag locks the lead: {name} -> {want}", b is not None and b["code"] == want and (want == "nophone" or b.get("lock")), b)
    L = PC.norm_lead(base, R)
    st2 = {"leads": [L], "log": [], "optouts": ["+1 (813) 555-0142".replace(" ", "")], "settings": {}}
    st2["optouts"] = [PC.norm_phone("1-813-555-0142")]
    check("b. an opt-out list entry matches the lead whatever the formatting ((813) 555-0142 vs 1-813-555-0142)", (PC.block_of(L, st2, t, R) or {}).get("code") == "optout")
    st3 = {"leads": [L], "log": [{"t": t - 60_000, "id": L["id"], "k": "dial"}], "optouts": [], "settings": {}}
    check("b. one call a day: a dial earlier today locks the lead until tomorrow", (PC.block_of(L, st3, t, R) or {}).get("code") == "today" and PC.block_of(L, st3, t + PC.DAY, R) is None)
    L2 = dict(L, stage="notinterested")
    st4 = {"leads": [L2], "log": [{"t": t, "id": L["id"], "k": "notinterested"}], "optouts": [], "settings": {}}
    check("b. 'not interested' rests the lead 180 days, then it may be called again", (PC.block_of(L2, st4, t + 179 * PC.DAY, R) or {}).get("code") == "rest" and PC.block_of(L2, st4, t + 181 * PC.DAY, R) is None)
    clear = dict(L, dnc="clear", dncChecked="2026-11-10")
    check("b. a clear DNC check is good for 31 days, then it needs checking again (or the business-line confirmation)",
          PC.dnc_state(clear, ms("2026-11-17T12:00:00Z"), R) == "clear" and PC.dnc_state(clear, ms("2026-12-20T12:00:00Z"), R) == "expired"
          and not PC.needs_confirm(clear, ms("2026-11-17T12:00:00Z"), R) and PC.needs_confirm(clear, ms("2026-12-20T12:00:00Z"), R) and not PC.needs_confirm(dict(clear, lineConfirmed="2026-12-19"), ms("2026-12-20T12:00:00Z"), R))
    nums, codes = PC.parse_dnc_file("813,5550142\n8135550177\n(727) 555-0101\njunk line\n")
    leads = [PC.norm_lead({"name": n, "phone": p, "state": "FL"}, R) for n, p in (("A", "813-555-0142"), ("B", "813-555-0150"), ("C", "305-555-0101"))]
    n = PC.apply_dnc(leads, nums, codes, "2026-11-14")
    check("b. the National DNC download: on it = listed (locked), in a covered area code but not on it = clear (checked today), other area codes untouched",
          sorted(nums) == ["+17275550101", "+18135550142", "+18135550177"] and codes == {"727", "813"} and n == {"listed": 1, "clear": 1, "not_covered": 1}
          and [x["dnc"] for x in leads] == ["listed", "clear", "unchecked"] and leads[1]["dncChecked"] == "2026-11-14" and PC.block_of(leads[0], st, t, R)["code"] == "dnc", (n, [x["dnc"] for x in leads]))
    # the script
    lead = PC.norm_lead({**base, "contact": "Maria Lopez", "demo": "https://example.com/demo/taco-town", "issue": "your menu is a PDF that is hard to read on a phone"}, R)
    me = {"me": "Sam Rivera", "biz": "Bright Sites", "city": "Tampa", "phone": "(813) 555-0100", "price": "$499"}
    s = PC.script_for(lead, me, R, SC, t)
    allt = json.dumps({k: v for k, v in s.items() if k != "vars"})
    check("b. the script fills from the lead: 'is this Maria?', Sam Rivera with Bright Sites, restaurants, the PDF menu issue, 3 questions with Taco Town, no {slot} left",
          s["opener"].startswith("Hi, is this Maria? This is Sam Rivera with Bright Sites, a small web studio in Tampa. It is a sales call") and "restaurants" in s["opener"] and "Taco Town" in s["opener"]
          and "your menu is a PDF" in s["why"] and len(s["questions"]) == 3 and "Taco Town" in s["questions"][0] and not re.search(r"\{\w+\}", allt), s["opener"])
    exp = next(o for o in s["objections"] if o["key"] == "expensive")
    check("b. 'Too expensive' quotes your own starting price ($499) and the voicemail gives your number twice", any("$499" in x for x in exp["lines"]) and s["vm1"].count("(813) 555-0100") == 2, exp["lines"])
    bare = PC.script_for(PC.norm_lead({"name": "Dr Smile", "phone": "512-555-0117", "state": "TX", "category": "dentist", "contact": "Dr. Anita Patel"}, R), {}, R, SC, t)
    bare2 = PC.script_for(PC.norm_lead({"name": "Acme Plumbing", "phone": "614-555-0123", "state": "OH", "category": "plumber"}, R), {}, R, SC, t)
    check("b. missing data never leaves a blank or a brace: 'Dr. Patel' for a titled contact, 'the owner' when none, '[your name]' until Settings has it",
          bare["opener"].startswith("Hi, is this Dr. Patel?") and bare2["opener"].startswith("Hi, could I speak with the owner, please? This is [your name] with [your business]")
          and not re.search(r"\{\w+\}", json.dumps(bare2)) and "the owner" in next(o for o in bare2["objections"] if o["key"] == "gatekeeper")["lines"][1], (bare["opener"][:60], bare2["opener"][:90]))
    # leads from team B1's shapes
    shapes = [{"name": "A", "phone": "+1 813 555 0142", "address": {"city": "Tampa", "state": "Florida", "postcode": "33602"}, "types": ["restaurant", "food"]},
              {"tags": {"name": "B", "phone": "727-555-0101", "addr:city": "Clearwater", "addr:state": "FL", "craft": "plumber"}},
              {"business_name": "C", "phone_number": "(305) 555-0101 ext. 4", "formatted_address": "1 Main St, Miami, FL 33101, USA", "category": "hair salon"},
              {"name": "A again", "phone": "813.555.0142", "email": "a@example.com"}]
    got, dupes, skipped = PC.norm_leads(shapes, R)
    check("b. B1's lead shapes: flat, an address object, OSM tags, a formatted address, an extension; the same phone only once (later copies fill empty fields)",
          [(x["name"], x["phone"], x["city"], x["state"], x["trade"]) for x in got] == [("A", "+18135550142", "Tampa", "FL", "restaurant"), ("B", "+17275550101", "Clearwater", "FL", "contractor"), ("C", "+13055550101", "Miami", "FL", "salon")]
          and dupes == 1 and got[0]["email"] == "a@example.com", [(x["name"], x["phone"], x["city"], x["state"], x["trade"]) for x in got])
    # the builder
    tmp = tempfile.mkdtemp(prefix="cc-build-")
    try:
        A = os.path.join(tmp, "agency")
        for sub in ("out/tampa-fl", "out/providence-ri", "content/fixtures", "calls/out"):
            os.makedirs(os.path.join(A, *sub.split("/")))
        b1 = [  # team B1's lead finder records (agency/leads.py): phone_e164, an address object, a category key, site_status, why
            {"id": "osm-n1", "name": "A", "category": "restaurant", "category_label": "Restaurant", "phone": "(813) 555-0142", "phone_e164": "+18135550142",
             "address": {"street": "Main St", "city": "Tampa", "state": "FL", "postcode": "33602", "line": "1 Main St, Tampa, FL 33602", "has_street": True},
             "website": "", "site_status": "none", "why": "No website found: people who search 'restaurant Tampa' on their phone find a competitor first.", "tier": "A", "score": 90},
            {"id": "osm-n2", "name": "B", "category": "plumber", "phone_e164": "+17275550101", "address": {"city": "Clearwater", "state": "FL"}, "site_status": "bad", "why": "Not mobile friendly."},
            {"id": "osm-n3", "name": "C", "category": "barber", "phone_e164": "+13055550101", "address": {"city": "Miami", "state": "FL"}, "email": "c@example.com"},
            {"id": "osm-n4", "name": "A again", "phone": "813.555.0142", "email": "a@example.com"},
            {"id": "osm-n5", "name": "Hill Roofing", "category": "roofer", "phone_e164": "+18135550177", "address": {"city": "Tampa", "state": "FL"}}]
        with open(os.path.join(A, "out", "tampa-fl", "leads.json"), "w", encoding="utf-8") as fh:
            json.dump({"v": 1, "kind": "agency-leads", "meta": {}, "leads": b1}, fh)
        for junk in (("out", "tampa-fl", "leads.csv"), ("out", "tampa-fl", "all_leads.csv"), ("content", "fixtures", "leads.csv"), ("calls", "out", "leads.json")):
            with open(os.path.join(A, *junk), "w", encoding="utf-8") as fh:
                fh.write("name,phone,state\nShould Not Be Read,212-555-0199,NY\n" if junk[-1].endswith(".csv") else '[{"name": "Should Not Be Read", "phone": "212-555-0199"}]')
        with open(os.path.join(A, "out", "providence-ri", "leads.csv"), "w", encoding="utf-8") as fh:
            fh.write("rank,tier,score,name,category_label,address,phone,website,site_status,why,reasons,distance_km,hours,email,osm_url,id\n"
                     "1,A,88,Corner Florist,Florist,\"12 Hope St, Providence, RI 02906\",(401) 555-0158,,none,No website found,,1.2,,,,osm-n9\n"
                     "2,B,70,No Phone Shop,Florist,\"3 Elm St, Providence, RI 02906\",,,none,No website found,,2.0,,,,osm-n10\n")
        found = PB.find_lead_files(__import__("pathlib").Path(A))
        check("b. the builder finds B1's day lists (agency/out/<city>/leads.json, a leads.csv only where there is no json); never all_leads.csv, other teams' fixtures or agency/calls/",
              sorted(os.path.relpath(str(p), A) for p in found) == [os.path.join("out", "providence-ri", "leads.csv"), os.path.join("out", "tampa-fl", "leads.json")], [str(p) for p in found])
        bl = {L["name"]: L for L in PC.norm_leads(b1, R)[0]}
        check("b. B1's records: phone_e164, the address object's city and state, trades from B1's category keys, B1's site grade becomes the pitch line and its 'why' stays visible",
              bl["A"]["phone"] == "+18135550142" and bl["A"]["city"] == "Tampa" and bl["A"]["state"] == "FL" and [bl[k]["trade"] for k in ("A", "B", "C", "Hill Roofing")] == ["restaurant", "contractor", "salon", "contractor"]
              and bl["A"]["issue"].startswith("you do not have a website yet") and bl["B"]["issue"].startswith("your current site has a few problems") and bl["A"]["finder"].startswith("No website found")
              and bl["A"]["id"] == "osm-n1", {k: (v["phone"], v["trade"], v["issue"][:20]) for k, v in bl.items()})
        roy = PC.norm_lead({"id": "w1", "name": "Roy's Quick Lube", "category": "auto_repair", "phone_e164": "+19705550123", "address_line": "825 North College Avenue, Fort Collins, CO 80524",
                            "city": "Fort Collins", "demo_url": "https://roys-quick-lube-demo.netlify.app", "setup": 999.0, "monthly": 79.0}, R)
        rs = PC.script_for(roy, {"me": "Sam", "price": "$499"}, R, SC, ms("2026-11-17T19:30:00Z"))
        check("b. B1's published CRM record: the state comes from address_line (CO), its demo_url and its own package price ('$999 to set up, then $79 a month') win over yours",
              roy["state"] == "CO" and roy["city"] == "Fort Collins" and roy["demo"].endswith("netlify.app") and roy["price"] == "$999 to set up, then $79 a month"
              and any("For Roy's Quick Lube it is $999 to set up, then $79 a month." in x for o in rs["objections"] for x in o["lines"]), (roy["state"], roy["price"]))
        sample = os.path.join(tmp, "sample.json")
        with open(sample, "w", encoding="utf-8") as fh:
            json.dump({"v": 1, "kind": "agency-crm-data", "demo": False, "sample": True, "leads": b1}, fh)
        check("b. B1's sample / demo files are never read as your leads (the page skips them too)", PB.read_leads(__import__("pathlib").Path(sample)) == [])
        b1keys = ["restaurant", "cafe", "bakery", "barber", "salon", "beauty", "plumber", "hvac", "electrician", "roofer", "painter", "builder", "locksmith", "landscaper", "cleaner",
                  "florist", "pet_grooming", "auto_repair", "car_wash", "dentist", "chiropractor", "physio", "vet", "massage", "gym", "tattoo"]
        got_t = [PC.trade_of({"category": k}, R) for k in b1keys]
        check("b. every one of B1's 26 category keys lands on a real trade (none falls to 'other')", "other" not in got_t, dict(zip(b1keys, got_t)))
        dnc = os.path.join(tmp, "813.txt")
        with open(dnc, "w", encoding="utf-8") as fh:
            fh.write("813,5550177\n")
        export = os.path.join(tmp, "export.json")
        with open(export, "w", encoding="utf-8") as fh:
            json.dump({"v": 1, "app": "agency-calls", "leads": [{"id": "x", "name": "C", "phone": "+13055550101", "stage": "dnc", "email": "c@example.com", "optout": True}], "optouts": ["727-555-0101"], "log": []}, fh)
        out_dir = __import__("pathlib").Path(A, "calls", "out")
        res = PB.build(found, [dnc], [export], "FL", ms("2026-11-17T19:30:00Z"), out_dir)
        cl = json.load(open(os.path.join(out_dir, "call_list.json"), encoding="utf-8"))
        byname = {x["name"]: x for x in cl["leads"]}
        check("b. call_list.json: kind call_list, 6 leads (1 duplicate merged), the phone's opt-outs locked (B, C), the DNC download locked Hill Roofing, no-phone kept but flagged",
              cl["kind"] == "call_list" and cl["app"] == "agency-calls" and len(cl["leads"]) == 6 and cl["summary"]["duplicates"] == 1 and byname["B"]["optout"] and byname["C"]["optout"]
              and byname["Hill Roofing"]["dnc"] == "listed" and byname["No Phone Shop"]["phone"] == "" and cl["summary"]["dnc"]["listed"] == 1 and sorted(cl["optouts"]) == ["+13055550101", "+17275550101"], cl["summary"])
        opt = json.load(open(os.path.join(out_dir, "optouts.json"), encoding="utf-8"))
        res2 = PB.build(found, [], [], "FL", ms("2026-11-18T19:30:00Z"), out_dir)
        opt2 = json.load(open(os.path.join(out_dir, "optouts.json"), encoding="utf-8"))
        check("b. optouts.json never shrinks: a later build without the export keeps both numbers (and the email opt-out)", opt["phones"] == opt2["phones"] == ["+13055550101", "+17275550101"] and opt2["emails"] == ["c@example.com"] and res2["summary"]["optouts"] == 2)
        hill = next(x for x in res2["leads"] if x["name"] == "Hill Roofing")
        corner = next(x for x in res2["leads"] if x["name"] == "Corner Florist")
        check("b. Do Not Call results are kept on the PC (dnc_checked.json): the next build without the download still locks Hill Roofing; numbers never checked stay unchecked",
              hill["dnc"] == "listed" and PC.block_of(hill, {"optouts": []}, ms("2026-11-18T19:30:00Z"), R)["code"] == "dnc" and corner["dnc"] == "unchecked", (hill["dnc"], corner["dnc"]))
        with open(os.path.join(out_dir, "call_list.csv"), encoding="utf-8") as fh:
            csvt = fh.read()
        check("b. call_list.csv: a printable sheet with their time now, the status and the next good time", csvt.startswith("name,phone,trade,city,state,their_time_now,status,next_good_time,dnc,demo") and "Corner Florist" in csvt and "On the National Do Not Call list" in csvt)
        rc = PB.main(["--leads", os.path.join(A, "out"), "--out", str(out_dir), "--now", "2026-11-17T19:30:00Z", "--state", "FL"])
        check("b. the command line: python -m agency.calls.build --leads <folder> --out <dir> works (exit 0) and prints the table", rc == 0)
        check("b. the builder's table lists the businesses with their status", "| Business | Trade | Their time | Status | Next good time |" in PB.table(res))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------------------------------------ c. node: the same answers + the phone-only logic
HARNESS = r"""
import fs from 'fs';
const C = await import(process.argv[2]);
const P = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
const R = P.rules, S = P.script, out = {};
out.windows = P.windows.map((c) => { const L = C.normLead(c.lead, R, 0); const w = C.windowStatus(L, c.now, R, c.settings || {}); return [w.code, w.next ? w.next.start : null, !!w.legal, w.zones, L.trade]; });
out.blocks = P.blocks.map((c) => { const L = C.normLead(c.lead, R, 0); const b = C.blockOf(L, { leads: [L], log: c.log, optouts: c.optouts, settings: {} }, c.now, R); return b ? b.code : null; });
out.leads = P.leads.map((raw) => C.normLead(raw, R, 0));
out.phones = P.phones.map(C.normPhone);
out.trades = P.trades.map((n) => C.tradeOf({ name: n }, R));
out.scripts = P.scripts.map((c) => { const sc = C.scriptFor(C.normLead(c.lead, R, 0), c.settings, R, S, c.now); delete sc.vars; return sc; });
out.holidays = [2026, 2027, 2028].map((y) => C.holidays(y, R.policy));
out.plan = P.windows.map((c) => C.nextDayName(C.normLead(c.lead, R, 0), c.now, R, c.settings || {}));

// ---------------------------------------------------------------- the phone-only logic: one day in the life of a list
const F = {};
const t0 = Date.parse('2026-11-17T19:30:00Z'), D = C.DAY;
const st = C.emptyState();
st.settings = Object.assign(C.defaultSettings(), { me: 'Sam Rivera', biz: 'Bright Sites', city: 'Tampa', phone: '(813) 555-0100' });
const csv = 'Business Name,Phone,City,State,Category,Email\n"Taco Town, Inc",(813) 555-0142,Tampa,FL,restaurant,maria@example.com\nGlow Nails,213-555-0181,Los Angeles,CA,nail salon,\nTaco again,813.555.0142,,,,\n=cmd|evil,415-555-0101,San Francisco,CA,boutique,\n';
const imp = C.parseImport(csv, R), m1 = C.mergeImport(st, imp);
F.csv = [imp.kind, imp.leads.length, imp.dupes, m1.added, st.leads[0].name, st.leads[0].email, st.leads[1].trade];
const L = st.leads[0], id = L.id;
F.needs = C.needsConfirm(L, t0, R);
C.applyOutcome(st, id, 'confirm', t0);
F.confirmed = [C.needsConfirm(L, t0, R), L.lineType];
const d1 = C.logDial(st, id, t0); const o1 = C.applyOutcome(st, id, 'noanswer', t0 + 60000);
F.attach = [d1.o, o1.dial === t0, C.attemptTimes(st.log, id).length, C.funnel(st.log, 0, Infinity).dials, (C.blockOf(L, st, t0 + 120000, R) || {}).code];
C.applyOutcome(st, id, 'voicemail', t0 + 90000);
F.vmSame = [C.attemptTimes(st.log, id).length, C.funnel(st.log, 0, Infinity).dials, d1.o];
// dialed from the phone's recents (no Call tap): two outcome taps within 10 minutes are still one call; a tap 20 minutes later is a new call
const sr = C.emptyState(); sr.leads.push(C.normLead({ name: 'Recents', phone: '813-555-0123', city: 'Tampa', state: 'FL' }, R, 0));
const rid = sr.leads[0].id;
C.applyOutcome(sr, rid, 'noanswer', t0); C.applyOutcome(sr, rid, 'callback', t0 + 120000, { at: t0 + 7200000 }); C.applyOutcome(sr, rid, 'interested', t0 + 240000);
const one = [C.attemptTimes(sr.log, rid).length, C.funnel(sr.log, 0, Infinity).dials, C.funnel(sr.log, 0, Infinity).conversations];
C.applyOutcome(sr, rid, 'voicemail', t0 + 1440000);
F.recents = one.concat([C.attemptTimes(sr.log, rid).length]);
F.cad1 = C.cadence(L, st, t0 + 100000, R).next;
const e1 = C.emailFor(L, 'e1', st.settings, R, S, t0);
st.settings.address = 'PO Box 100, Tampa, FL 33601';
const e1b = C.emailFor(L, 'e1', st.settings, R, S, t0);
F.email = [e1.ok, e1.why, e1b.ok, e1b.href.startsWith('mailto:maria@example.com?subject='), e1b.body.includes('PO Box 100, Tampa, FL 33601'), e1b.body.includes('will not email you again'), e1b.subject];
C.applyOutcome(st, id, 'email', t0 + 120000, { key: 'e1' });
const tx1 = C.textFor(L, 't1', st.settings, R, S, t0);
C.applyOutcome(st, id, 'consent', t0 + 130000);
const tx2 = C.textFor(L, 't1', st.settings, R, S, t0);
F.text = [tx1.ok, tx1.why, tx2.ok, tx2.href.startsWith('sms:+18135550142?&body='), tx2.body.endsWith('Reply STOP to opt out.'), L.consentText.how];
C.applyOutcome(st, id, 'noconsent', t0 + 140000);
F.textOff = C.textFor(L, 't1', st.settings, R, S, t0).ok;
// day 2: the second call of the plan
const t1 = t0 + D;
F.day2 = [(C.blockOf(L, st, t1, R) || { code: null }).code, C.cadence(L, st, t1, R).next.day];
C.logDial(st, id, t1); C.applyOutcome(st, id, 'callback', t1 + 30000, { at: t1 + 2 * 3600000 });
F.cb = [L.stage, (C.blockOf(L, st, t1 + 60000, R) || {}).code, C.blockOf(L, st, t1 + 2 * 3600000, R), C.callbackDue(L, t1 + 2 * 3600000)];
C.logDial(st, id, t1 + 2 * 3600000);
C.logDial(st, id, t1 + 2 * 3600000 + 600000);
F.cap = (C.blockOf(L, st, t1 + 2.5 * 3600000, R) || {}).code;
C.applyOutcome(st, id, 'interested', t1 + 2 * 3600000 + 900000, { email: 'maria@tacotown.example', text: true });
F.int = [L.stage, L.email, !!(L.consentText && L.consentText.on), C.cadence(L, st, t1 + 3 * 3600000, R).next.kind];
C.applyOutcome(st, id, 'demo', t1 + 4 * 3600000, { at: t1 + 2 * D });
C.applyOutcome(st, id, 'won', t1 + 2 * D + 3600000);
const fw = C.funnel(st.log, 0, Infinity);
F.funnel = [fw.dials, fw.conversations, fw.interested, fw.demos, fw.closes, fw.voicemails, fw.noanswer, fw.callbacks, fw.emails, fw.rates.talk];
F.client = (C.blockOf(L, st, t1 + 3 * D, R) || {}).code;
// do not call: locked for good, no emails / texts, a re-import cannot unlock it
const G = st.leads[1];
C.applyOutcome(st, G.id, 'dnc', t0);
const again = C.parseImport('name,phone,state\nGlow Nails,(213) 555-0181,CA\n', R); C.mergeImport(st, again);
F.dnc = [st.optouts.indexOf('+12135550181') >= 0, (C.blockOf(G, st, t0 + 400 * D, R) || {}).code, C.emailFor(Object.assign({}, G, { email: 'g@example.com' }), 'e1', st.settings, R, S, t0).ok, C.textFor(G, 't1', st.settings, R, S, t0).ok, G.optout, st.leads.length];
// not interested: 180 days of rest
const N = st.leads[2];
C.applyOutcome(st, N.id, 'notinterested', t0);
F.rest = [(C.blockOf(N, st, t0 + 100 * D, R) || {}).code, C.blockOf(N, st, t0 + 181 * D, R), C.cadence(N, st, t0, R).stop];
// the CSV export: a cell that starts with = is defused
const out2 = C.toCSV(st, t0, R);
F.csvOut = [out2.split('\n')[0], out2.includes("\"'=cmd|evil\""), out2.split('\n').length];
// export -> load -> merge into an empty phone: everything comes back
const ex = C.exportJSON(st, t0), back = C.loadState(ex), pi = C.parseImport(ex, R), fresh = C.emptyState(), mm = C.mergeImport(fresh, pi);
F.backup = [back.leads.length, back.log.length === st.log.length, back.optouts.length, pi.kind, mm.added, mm.events === st.log.length, fresh.optouts.length, (C.blockOf(fresh.leads[1], fresh, t0, R) || {}).code];
// junk never throws
F.junk = [C.loadState('not json').leads.length, C.loadState('{"leads":"x","log":[1,{"t":"a"}],"optouts":["abc", "2135550181"],"settings":{"me":123}}').optouts, C.parseImport('{oops', R).kind, C.parseImport('', R).kind, C.normLead(null, R, 0), C.normLead({ city: 'x' }, R, 0)];
// team B1's agency app on the same phone (localStorage shared keys)
F.shared = C.sharedLeads(JSON.stringify({ leads: [{ business_name: 'From B1', phone: '813-555-0190', state: 'FL', category: 'bakery' }] }), R).map((x) => [x.name, x.trade]);
// fictional numbers are never dialed
F.tel = [C.telHref('+18135550142'), C.telHref('+18135551234'), C.isFictional('+18135550199')];
// team B1's CRM on the same phone: 'Do not contact' locks for good, 'won' = a client; other stages and junk change nothing
const cs = C.emptyState(); for (const [i, n] of [['b-1', 'One'], ['b-2', 'Two'], ['b-3', 'Three']]) { const x = C.normLead({ id: i, name: n, phone: '813-555-02' + i.slice(2).padStart(2, '0'), state: 'FL' }, R, 0); cs.leads.push(x); }
const stg = C.crmStages(JSON.stringify({ v: 1, leads: { 'b-1': { stage: 'dnc' }, 'b-2': { stage: 'won' }, 'b-3': { stage: 'callback' } }, log: [] }));
const nCrm = C.applyCrm(cs, stg), again2 = C.applyCrm(cs, stg);
F.crm = [stg, nCrm, again2, (C.blockOf(cs.leads[0], cs, t0, R) || {}).code, (C.blockOf(cs.leads[1], cs, t0, R) || {}).code, C.blockOf(cs.leads[2], cs, t0, R), cs.optouts.length, Object.keys(C.crmStages('nope')).length, Object.keys(C.crmStages('{"leads": [1, 2]}')).length];
F.url = [C.safeUrl('https://example.com/demo/taco-town'), C.safeUrl('javascript:alert(1)'), C.safeUrl('data:text/html,x'), C.safeUrl('https://x.example/a"onmouseover'), C.safeUrl(' http://ok.example/p ')];
// the queue: a callback due first, good now, legal now, later, locked last
const q = C.emptyState();
const mk = (o) => { const x = C.normLead(o, R, 0); x.lineConfirmed = '2026-11-17'; q.leads.push(x); return x; };
mk({ name: 'Locked', phone: '813-555-0111', state: 'FL', category: 'restaurant', dnc: 'listed' });
mk({ name: 'Later', phone: '671-555-0112', state: 'GU', category: 'plumber' });
mk({ name: 'Good', phone: '813-555-0113', city: 'Tampa', state: 'FL', category: 'restaurant' });
mk({ name: 'Legal', phone: '312-555-0114', city: 'Chicago', state: 'IL', category: 'law firm' });
const cbL = mk({ name: 'Callback', phone: '813-555-0115', state: 'FL', category: 'plumber' }); cbL.stage = 'callback'; cbL.callbackAt = t0;
F.queue = C.queue(q, t0, R).map((x) => x.lead.name + ':' + x.rank);
F.plan = C.callPlan(q, t0, R, 'America/New_York').map((p) => p.label + ' ' + p.mine);
console.log(JSON.stringify({ out, F }));
"""


def py_side(payload: dict) -> dict:
    out = {}
    out["windows"] = []
    for c in payload["windows"]:
        L = PC.norm_lead(c["lead"], R)
        w = PC.window_status(L, c["now"], R, c.get("settings") or {})
        out["windows"].append([w["code"], w["next"]["start"] if w.get("next") else None, bool(w["legal"]), w["zones"], L["trade"]])
    out["blocks"] = []
    for c in payload["blocks"]:
        L = PC.norm_lead(c["lead"], R)
        b = PC.block_of(L, {"leads": [L], "log": c["log"], "optouts": c["optouts"], "settings": {}}, c["now"], R)
        out["blocks"].append(b["code"] if b else None)
    out["leads"] = [PC.norm_lead(x, R) for x in payload["leads"]]
    out["phones"] = [PC.norm_phone(x) for x in payload["phones"]]
    out["trades"] = [PC.trade_of({"name": n}, R) for n in payload["trades"]]
    out["scripts"] = []
    for c in payload["scripts"]:
        s = PC.script_for(PC.norm_lead(c["lead"], R), c["settings"], R, SC, c["now"])
        s.pop("vars")
        out["scripts"].append(s)
    out["holidays"] = [PC.holidays(y, R["policy"]) for y in (2026, 2027, 2028)]
    out["plan"] = [PC.next_day_name(PC.norm_lead(c["lead"], R), c["now"], R, c.get("settings") or {}) for c in payload["windows"]]
    return out


def test_node():
    exe = shutil.which("node")
    if not exe:
        check("c. node is not installed: parity skipped", True)
        return
    t = ms("2026-11-17T19:30:00Z")
    base = {"name": "Taco Town", "phone": "813-555-0142", "city": "Tampa", "state": "FL", "category": "restaurant"}
    payload = {
        "rules": R, "script": SC,
        "windows": [{"lead": lead, "now": ms(now), "settings": sets} for _, lead, now, sets, _, _ in WINDOW_CASES],
        "blocks": [
            {"lead": base, "now": t, "log": [], "optouts": []},
            {"lead": {**base, "dnc": "listed"}, "now": t, "log": [], "optouts": []},
            {"lead": {**base, "phone": "(813)555-0142"}, "now": t, "log": [], "optouts": ["+18135550142"]},
            {"lead": {**base, "phone": ""}, "now": t, "log": [], "optouts": []},
            {"lead": base, "now": t, "log": [{"t": t - 60_000, "id": "p8135550142", "k": "dial"}], "optouts": []},
            {"lead": base, "now": t + PC.DAY, "log": [{"t": t - 60_000, "id": "p8135550142", "k": "dial"}], "optouts": []},
            {"lead": {**base, "stage": "callback", "callbackAt": t}, "now": t, "log": [{"t": t - 3 * 3_600_000, "id": "p8135550142", "k": "dial"}], "optouts": []},
            {"lead": {**base, "stage": "callback", "callbackAt": t}, "now": t, "log": [{"t": t - k * 3_600_000, "id": "p8135550142", "k": "dial"} for k in (1, 2, 3)], "optouts": []},
            {"lead": {**base, "stage": "notinterested"}, "now": t + 10 * PC.DAY, "log": [{"t": t, "id": "p8135550142", "k": "notinterested"}], "optouts": []},
            {"lead": {**base, "stage": "won"}, "now": t, "log": [], "optouts": []},
        ],
        "leads": [
            {"name": "A", "phone": "+1 813 555 0142", "address": {"city": "Tampa", "state": "Florida", "postcode": 33602}, "types": ["restaurant", "food"], "website": "https://a.example.com"},
            {"tags": {"name": "B", "phone": "727-555-0101", "addr:city": "Clearwater", "addr:state": "FL", "craft": "plumber"}, "dnc": "yes", "osm_id": 12345},
            {"business_name": "C", "phone_number": "(305) 555-0101 ext. 4", "formatted_address": "1 Main St, Miami, FL 33101, USA", "category": "hair salon", "text_consent": "yes", "text_consent_on": "2026-11-01"},
            {"name": "D", "phone": 8135550142.0, "email": "not an email", "line_type": "Mobile", "contact": "  Dr. Ann  Lee ", "tz": "Not/AZone", "callbackAt": "123"},
            {"company": "E", "tel": "+44 20 7946 0958", "state": "tx", "consentText": {"on": "2026-11-02T10:00:00Z", "how": "web form"}, "optout": 1},
            {"city": "Nowhere"},
            {"id": "osm-n1", "name": "B1 Diner", "category": "restaurant", "category_label": "Restaurant", "phone": "(813) 555-0142", "phone_e164": "+18135550142",
             "address": {"street": "Main St", "city": "Tampa", "state": "FL", "postcode": "33602", "line": "1 Main St, Tampa, FL 33602", "has_street": True}, "site_status": "none", "why": "No website found."},
            {"rank": "1", "name": "B1 Florist", "category_label": "Florist", "address": "12 Hope St, Providence, RI 02906", "phone": "(401) 555-0158", "site_status": "fair", "why": "Slow site."},
            {"id": "w248410324", "name": "Roy's Quick Lube", "category": "auto_repair", "trade_label": "Auto repair", "phone": "(970) 555-0123", "phone_e164": "+19705550123",
             "address_line": "825 North College Avenue, Fort Collins, CO 80524", "city": "Fort Collins", "demo_url": "https://roys-quick-lube-demo.netlify.app", "setup": 999.0, "monthly": 79.0,
             "site_status": "none", "why": "No website found.", "opener": "B1's own opener", "package": "growth"},
        ],
        "phones": ["(813) 555-0142", "+1-813-555-0142", "1 813 555 0142", "813.555.0142 x12", "555-0142", "+44 20 7946 0958", "113-555-0142", "813-155-0142", "", "8135550142"],
        "trades": ["Joe's Bar & Grill", "Smile Dental", "Kitchen Remodeling Pros", "Main St Auto", "Bella Nails", "Dance Studio 9", "Barber Shop", "Coffee Shop", "Body Shop", "Bookkeeping LLC", "Café Rio", "Lawn Bros", "Spanish Moss Bakery", "Zen Spa", "Unknown Thing"],
        "scripts": [
            {"lead": {**base, "contact": "Maria Lopez", "demo": "https://example.com/demo/taco-town", "issue": "your menu is a PDF"}, "settings": {"me": "Sam Rivera", "biz": "Bright Sites", "city": "Tampa", "phone": "(813) 555-0100", "price": "$499"}, "now": t},
            {"lead": {"name": "Acme Plumbing", "phone": "614-555-0123", "state": "OH", "category": "plumber"}, "settings": {}, "now": t},
            {"lead": {"name": "Dr Smile", "phone": "512-555-0117", "state": "TX", "category": "dentist", "contact": "Dr. Anita Patel", "source": "Yelp"}, "settings": {"me": "Sam", "phone": "not a number"}, "now": ms("2026-11-20T19:30:00Z")},
            {"lead": {"name": "Roy's Quick Lube", "category": "auto_repair", "phone_e164": "+19705550123", "address_line": "825 North College Avenue, Fort Collins, CO 80524", "setup": 1500, "monthly": 79},
             "settings": {"me": "Sam", "price": "$499"}, "now": t},
        ],
    }
    tmp = tempfile.mkdtemp(prefix="cc-node-")
    try:
        core = os.path.join(tmp, "callcore.mjs")
        shutil.copy(os.path.join(D, "callcore.js"), core)
        h = os.path.join(tmp, "harness.mjs")
        with open(h, "w", encoding="utf-8") as fh:
            fh.write(HARNESS)
        pj = os.path.join(tmp, "payload.json")
        with open(pj, "w", encoding="utf-8") as fh:
            json.dump(payload, fh)
        r = subprocess.run([exe, h, core, pj], capture_output=True, text=True, timeout=180)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    check("c. the node harness runs", r.returncode == 0, r.stderr[-800:])
    if r.returncode:
        return
    res = json.loads(r.stdout)
    js, F = res["out"], res["F"]
    py = py_side(payload)
    for k in ("windows", "blocks", "leads", "phones", "trades", "scripts", "holidays", "plan"):
        same = js[k] == py[k]
        diff = [(i, a, b) for i, (a, b) in enumerate(zip(js[k], py[k])) if a != b][:2] if isinstance(js[k], list) else ""
        check(f"c. the phone (callcore.js) and the PC (core.py) agree on {k}", same, diff)
    check("c. the window cases end as the PC expects (codes)", [w[0] for w in js["windows"]] == [c[4] for c in WINDOW_CASES], [w[0] for w in js["windows"]])
    check("c. locks in node: clean / DNC listed / opted out (any format) / no phone / called today / tomorrow / callback due / 3 in 24 h / resting / client",
          js["blocks"] == [None, "dnc", "optout", "nophone", "today", None, None, "cap", "rest", "client"], js["blocks"])
    check("c. phones: (813) 555-0142, +1-813-..., 1 813 ..., an extension -> +18135550142; 7 digits, UK, area codes or exchanges starting with 0/1, blank -> nothing",
          js["phones"] == ["+18135550142"] * 4 + ["", "", "", "", "", "+18135550142"], js["phones"])
    check("c. holidays 2027: July 4 (Sunday) observed Monday July 5; Christmas (Saturday) observed Friday Dec 24; New Year 2028 (Saturday) observed Friday Dec 31, 2027",
          js["holidays"][1].get("2027-07-05", "").endswith("(observed)") and js["holidays"][1].get("2027-12-24", "").endswith("(observed)") and js["holidays"][2].get("2027-12-31", "").endswith("(observed)"))
    check("c. CSV import: quoted commas, a header with spaces, the duplicate phone merged; restaurant + salon trades", F["csv"] == ["csv", 3, 1, 3, "Taco Town, Inc", "maria@example.com", "salon"], F["csv"])
    check("c. an unchecked number needs the one-time 'business line' confirmation; after it, no more questions", F["needs"] is True and F["confirmed"] == [False, "business"], (F["needs"], F["confirmed"]))
    check("c. Call + No answer = ONE attempt (the outcome joins the dial): 1 dial in the funnel, then 'called today'", F["attach"] == ["noanswer", True, 1, 1, "today"], F["attach"])
    check("c. a second tap for the same call (No answer, then Voicemail) is still one attempt", F["vmSame"] == [1, 1, "voicemail"], F["vmSame"])
    check("c. dialed from the phone's recents (no Call tap): outcome taps within 10 minutes are one call (1 dial, 1 conversation); 20 minutes later is a second call",
          F["recents"] == [1, 1, 1, 2], F["recents"])
    check("c. after call 1 the plan says day 2: call again", F["cad1"]["day"] == 2 and F["cad1"]["kind"] == "call", F["cad1"])
    check("c. CAN-SPAM gate: no email until your postal address is set; then a mailto: link with the subject, your address and the opt-out line",
          F["email"][0] is False and "postal address" in F["email"][1] and F["email"][2:6] == [True, True, True, True] and F["email"][6] == "Preview of a new website for Taco Town, Inc", F["email"])
    check("c. text gate: no text until 'They said I can text' is logged; then an sms: link ending 'Reply STOP to opt out.'; 'stop' removes it again",
          F["text"][0] is False and "said yes" in F["text"][1] and F["text"][2:5] == [True, True, True] and F["textOff"] is False, F["text"])
    check("c. day 2: the lead is callable again and the plan asks for call 2", F["day2"] == [None, 2], F["day2"])
    check("c. a callback: 'called today' until the time they asked for, then callable again (the one exception to one call a day)", F["cb"][0] == "callback" and F["cb"][1] == "today" and F["cb"][2] is None and F["cb"][3] is True, F["cb"])
    check("c. the hard cap: 3 attempts in 24 hours (Florida's limit too) locks even a callback", F["cap"] == "cap", F["cap"])
    check("c. interested: stage, the new email, text consent from the call, the plan moves to 'book the demo'", F["int"] == ["interested", "maria@tacotown.example", True, "demo"], F["int"])
    check("c. the funnel: 4 dials, 2 conversations (callback + interested), 1 interested, 1 demo, 1 close, 1 voicemail, 1 no answer, 1 email, 50% talk rate",
          F["funnel"] == [4, 2, 1, 1, 1, 1, 1, 1, 1, 50], F["funnel"])
    check("c. a client is never cold-called again", F["client"] == "client", F["client"])
    check("c. do not call: on the opt-out list, locked forever (400 days later too), no email, no text, and a re-import of the same business does not unlock it",
          F["dnc"] == [True, "optout", False, False, True, 3], F["dnc"])
    check("c. not interested: rests 180 days (locked at day 100, free at day 181), the follow-up plan stops", F["rest"] == ["rest", None, "notinterested"], F["rest"])
    check("c. CSV export: the header row, a formula-looking name is defused with an apostrophe", F["csvOut"][0].startswith("name,phone,contact,email,city,state,trade,stage,dnc") and F["csvOut"][1] is True, F["csvOut"][:2])
    check("c. backup: export -> load keeps every lead, tap and opt-out; importing it on an empty phone restores the list and its locks",
          F["backup"][0] == 3 and F["backup"][1] is True and F["backup"][2] == 1 and F["backup"][3] == "backup" and F["backup"][4] == 3 and F["backup"][5] is True and F["backup"][6] == 1 and F["backup"][7] == "optout", F["backup"])
    check("c. junk never throws: bad JSON, wrong types, a bad opt-out, an empty paste, a lead without a name or phone",
          F["junk"] == [0, ["+12135550181"], "bad", "empty", None, None], F["junk"])
    check("c. team B1's agency app on the same phone: its shared leads load (a bakery is a restaurant-type trade)", F["shared"] == [["From B1", "restaurant"]], F["shared"])
    check("c. fictional 555-01xx numbers never get a tel: link; real ones do", F["tel"] == ["", "tel:+18135551234", True], F["tel"])
    check("c. team B1's CRM stages on this phone: 'Do not contact' locks the lead for good (opt-out list too), 'won' = a client, other stages and junk change nothing, applying twice changes nothing more",
          F["crm"] == [{"b-1": "dnc", "b-2": "won"}, 2, 0, "optout", "client", None, 1, 0, 0], F["crm"])
    check("c. a demo-site link from the data is used only when it is plain http(s): javascript:, data: and quote tricks are dropped", F["url"] == ["https://example.com/demo/taco-town", "", "", "", "http://ok.example/p"], F["url"])
    check("c. the queue: the callback due first, good now, legal now, opens later, the DNC-listed one last", F["queue"] == ["Callback:0", "Good:1", "Legal:2", "Later:3", "Locked:9"], F["queue"])
    check("c. today's call plan in YOUR time zone (New York): restaurants now to 4, Chicago's offices 3-5:30 pm, Florida's contractors 4-6 pm, Guam's at 8 am their time = 5 pm yours",
          F["plan"] == ["restaurant 2:30 pm-4:00 pm", "local office 3:00 pm-5:30 pm", "contractor 4:00 pm-6:00 pm", "contractor 5:00 pm-6:00 pm"], F["plan"])


# ------------------------------------------------------------------------------------------------ d. Chromium
NOW = "2026-11-17T19:30:00Z"  # a Tuesday, 2:30 pm in New York


def test_page():
    try:
        import playwright  # noqa: F401
    except ImportError:
        check("d. page tests skipped: no Playwright", True)
        return
    srv, origin = AK.serve()
    try:
        with AK.browser() as br:
            ctx, p, errs, seen, off = AK.page(br, origin)
            methods = []
            p.on("request", lambda rq: methods.append(rq.method))
            AK.open_app(p, origin, "agency", f"call.html?demo=1&now={NOW}", hook="CALLS")
            d = p.evaluate("""() => ({ demo: !document.querySelector('#demo').hidden, line: document.querySelector('#nowLine').textContent, goals: document.querySelectorAll('#goals .tile').length,
              bars: document.querySelectorAll('#funnel rect.bar').length, leads: [...document.querySelectorAll('#leads .lead')].map((b) => b.querySelector('b').textContent + '|' + b.querySelector('.pill').textContent),
              rules: document.querySelectorAll('#rules5 li').length, plan: document.querySelectorAll('#plan li').length, follow: document.querySelectorAll('#follow .lead').length,
              font: getComputedStyle(document.querySelector('h1')).fontFamily, bg: getComputedStyle(document.body).backgroundColor, h1: document.querySelector('h1').textContent })""")
            check("d. the page renders (DEMO): the chip, 'OK to call right now', 4 goal tiles, a 5-bar funnel, the queue, today's plan, follow-ups, the rules in 5 lines",
                  d["demo"] and "OK to call right now" in d["line"] and d["goals"] == 4 and d["bars"] == 5 and len(d["leads"]) >= 3 and d["rules"] == 5 and d["plan"] >= 1 and d["follow"] >= 1 and d["h1"] == "Call copilot", d)
            check("d. Taco Town (Tampa, 2:30 pm their time) is 'Good now'; Sunset Diner (called 45 min ago) is not in 'Call now'",
                  any(x == "Taco Town|Good now" for x in d["leads"]) and not any(x.startswith("Sunset Diner") for x in d["leads"]), d["leads"])
            check("d. AGORA look: serif title, warm dark body", any(f in d["font"] for f in ("Palatino", "Iowan", "Georgia")) and d["bg"] == "rgb(20, 17, 14)", (d["font"], d["bg"]))
            AK.shot(p, "calls-demo")
            p.locator("#filters [data-f=locked]").click()
            p.wait_for_timeout(150)
            lk = p.evaluate("() => [...document.querySelectorAll('#leads .lead b')].map((b) => b.textContent)")
            check("d. the Locked filter: Hilltop Roofing (on the DNC list) and Bayou Bistro (asked not to be called)", "Hilltop Roofing" in lk and "Bayou Bistro" in lk, lk)
            p.locator("#leads [data-lead=d-hill]").click()
            p.wait_for_timeout(200)
            hl = p.evaluate("""() => ({ open: !document.querySelector('#call').hidden, locked: !document.querySelector('#cLocked').hidden && document.querySelector('#cLocked').textContent, dial: document.querySelector('#cDial').hidden,
              outs: [...document.querySelectorAll('#outs button')].every((b) => b.disabled), win: document.querySelector('#cWin').textContent })""")
            check("d. a DNC-listed business: the Call button is locked ('Locked: do not call'), every outcome is disabled, the reason is in words",
                  hl["open"] and hl["locked"] == "Locked: do not call" and hl["dial"] and hl["outs"] and "Do Not Call list" in hl["win"], hl)
            p.locator("#cClose").click()
            p.locator("#filters [data-f=now]").click()
            p.wait_for_timeout(150)
            p.locator("#leads [data-lead=d-taco]").click()
            p.wait_for_timeout(250)
            c = p.evaluate("""() => ({ name: document.querySelector('#cName').textContent, opener: document.querySelector('#sOpener').textContent, size: parseFloat(getComputedStyle(document.querySelector('#sOpener')).fontSize),
              qs: [...document.querySelectorAll('#sQs li')].map((l) => l.textContent), dial: document.querySelector('#cDial').textContent, href: document.querySelector('#cDial').getAttribute('href'),
              demo: document.querySelector('#cDemo').hidden ? null : document.querySelector('#cDemo').getAttribute('href'),
              win: document.querySelector('#cWin').textContent, law: document.querySelector('#cLaw').textContent, outs: [...document.querySelectorAll('#outs button')].map((b) => [b.textContent, Math.round(b.getBoundingClientRect().height)]) })""")
            check("d. the call screen: Taco Town, the opener in big type (>= 22 px) asking for Maria, 3 questions, the Call button with the number (an example number: no tel: link), their preview site one tap away",
                  c["name"] == "Taco Town" and c["opener"].startswith("Hi, is this Maria? This is Sam Rivera with Bright Sites") and c["size"] >= 22 and len(c["qs"]) == 3
                  and c["dial"] == "Call (813) 555-0142 (example: no real call)" and c["href"] is None and "Good time to call" in c["win"] and "Florida" in c["law"]
                  and c["demo"] == "https://example.com/demo/taco-town", c)
            check("d. six one-tap outcomes (no answer, voicemail, callback time, interested, not interested, do not call), each at least 56 px tall",
                  [o[0] for o in c["outs"]] == ["No answer", "Voicemail", "Callback time", "Interested", "Not interested", "Do not call"] and all(o[1] >= 56 for o in c["outs"]), c["outs"])
            p.locator("#tabObj").click()
            p.locator("#objChips [data-obj=expensive]").click()
            p.wait_for_timeout(100)
            ob = p.evaluate("() => [document.querySelectorAll('#objChips button').length, document.querySelector('#objAnswer').textContent]")
            check("d. objections: 8 answers; 'Too expensive' shows your own price ($499) in big words", ob[0] == 8 and "Too expensive" in ob[1] and "$499" in ob[1], ob)
            p.locator("#objChips [data-obj=gatekeeper]").click()
            gk = p.evaluate("() => document.querySelector('#objAnswer').textContent")
            check("d. the gatekeeper lines ask who looks after the website and the best time to reach Maria", "Who looks after your website?" in gk and "Maria Lopez" in gk, gk)
            p.locator("#tabVm").click()
            vm = p.evaluate("() => [document.querySelector('#vm1').textContent, document.querySelector('#vmRule').textContent]")
            check("d. the voicemail script (your name, your number twice) and the rule: live, never a recorded or AI drop", "Sam Rivera" in vm[0] and vm[0].count("(813) 555-0100") == 2 and "Never a recorded, AI" in vm[1], vm)
            p.locator("#tabNext").click()
            nx = p.evaluate("""() => ({ emails: [...document.querySelectorAll('#nEmails a')].map((a) => a.getAttribute('href').slice(0, 40)), texts: document.querySelectorAll('#nTexts a').length,
              tdis: [...document.querySelectorAll('#nTexts button')].every((b) => b.disabled), twhy: document.querySelector('#nTextWhy').textContent, steps: document.querySelectorAll('#nSteps li').length })""")
            check("d. follow up: the 7-day plan (6 steps), 4 email links (mailto:, your postal address is set in the demo), texts locked until they said yes",
                  nx["steps"] == 6 and len(nx["emails"]) == 4 and all(e.startswith("mailto:maria@example.com?subject=") for e in nx["emails"]) and nx["texts"] == 0 and nx["tdis"] and "said yes" in nx["twhy"], nx)
            p.locator("#consentBtn").click()
            p.wait_for_timeout(100)
            sms = p.evaluate("() => [...document.querySelectorAll('#nTexts a')].map((a) => a.getAttribute('href'))")
            check("d. 'They said I can text' unlocks the texts: sms: links that end 'Reply STOP to opt out.'", len(sms) == 2 and all(s.startswith("sms:+18135550142?&body=") and s.endswith("Reply%20STOP%20to%20opt%20out.") for s in sms), sms[:1])
            t = AK.taps(p)
            check("d. the call screen: every tap target is at least 44 x 44 px", not t, t[:5])
            p.locator("#tabScript").click()
            p.locator("#cDial").click()
            p.wait_for_timeout(500)
            p.locator("#outs [data-out=noanswer]").click()
            p.wait_for_timeout(250)
            na = p.evaluate("() => ({ status: document.querySelector('#status').textContent, locked: document.querySelector('#cLocked').textContent, dial: document.querySelector('#cDial').hidden, log: window.CALLS.state.log.filter((e) => e.id === 'd-taco' && (e.k === 'dial' || e.k === 'noanswer')).map((e) => e.k + (e.o ? ':' + e.o : '')) })")
            check("d. Call then No answer: saved as one attempt, the status says what is next, the Call button locks for today",
                  na["status"].startswith("Saved: No answer for Taco Town.") and "Next: day 2" in na["status"] and na["dial"] and na["locked"] == "Not now: called today" and na["log"] == ["dial:noanswer", "noanswer"], na)
            p.locator("#cNextLead").click()
            p.wait_for_timeout(250)
            nm = p.evaluate("() => document.querySelector('#cName').textContent")
            check("d. 'Next business' moves on to the next one to call", nm and nm != "Taco Town", nm)
            p.locator("#cClose").click()
            p.locator("#filters [data-f=all]").click()
            p.locator("#leads [data-lead=d-glow]").click()
            p.wait_for_timeout(200)
            p.locator("#outs [data-out=dnc]").click()
            armed = p.evaluate("() => document.querySelector('#outs [data-out=dnc]').textContent")
            p.locator("#outs [data-out=dnc]").click()
            p.wait_for_timeout(250)
            g = p.evaluate("() => ({ opt: window.CALLS.state.optouts, locked: document.querySelector('#cLocked').textContent, saved: (() => { try { return localStorage.getItem('agency.calls.v1'); } catch (e) { return 'x'; } })() })")
            check("d. Do not call asks twice ('Tap again: never call ...'), then locks the business for good; the DEMO list is never saved",
                  armed.startswith("Tap again: never call Glow Nail Studio") and "+12135550181" in g["opt"] and g["locked"] == "Locked: do not call" and g["saved"] is None, (armed, g))
            p.locator("#cClose").click()
            check("d. no sideways scroll; Jarvis's corner is free; no console error", AK.no_sideways(p) and not AK.corner(p) and not errs, errs[:3])
            t = AK.taps(p)
            check("d. the main page: every tap target is at least 44 x 44 px", not t, t[:5])
            agency = [u.split("?")[0] for u in seen if "/agency/" in u and u.split("?")[0].endswith(".json")]
            check("d. NOTHING SENT: only GET requests, nothing off this origin, and the page read only its own JSON files (+ B1's leads.json)",
                  set(methods) <= {"GET"} and not off and set(x.rsplit("/", 1)[-1] for x in agency) <= {"callrules.json", "callscript.json", "call_fixture.json", "leads.json"}, (set(methods), off[:3], agency))
            ctx.close()

            # the real loop: import -> saved on the phone -> reload -> export
            ctx, p, errs, seen, off = AK.page(br, origin)
            methods = []
            p.on("request", lambda rq: methods.append(rq.method))
            AK.open_app(p, origin, "agency", f"call.html?now={NOW}", hook="CALLS")
            first = p.evaluate("() => [!document.querySelector('#demo').hidden, window.CALLS.S.demo]")
            p.fill("#box", "Business,Phone,City,State,Category,Email\nMain Pizza,(813) 555-1001,Tampa,FL,pizza,owner@mainpizza.example\nDesert Plumbing,602-555-1002,Phoenix,AZ,plumber,\nMain Pizza again,813.555.1001,,,,\n")
            p.locator("#importBox").click()
            p.wait_for_timeout(300)
            im = p.evaluate("() => ({ demo: !document.querySelector('#demo').hidden, status: document.querySelector('#status').textContent, saved: JSON.parse(localStorage.getItem('agency.calls.v1') || 'null') })")
            check("d. with nothing saved the page shows the example list; importing a pasted CSV switches to YOUR list (2 businesses, the duplicate merged) saved on this phone",
                  first == [True, True] and not im["demo"] and "2 new businesses" in im["status"] and "1 duplicates merged" in im["status"] and im["saved"] and len(im["saved"]["leads"]) == 2, (first, im["status"]))
            lid = im["saved"]["leads"][0]["id"]
            p.evaluate(f"() => window.CALLS.open({json.dumps(lid)}, 'script')")
            p.wait_for_timeout(200)
            cf = p.evaluate("() => [!document.querySelector('#cConfirm').hidden, document.querySelector('#cLocked').textContent, document.querySelector('#cDial').hidden]")
            check("d. a number not checked against the DNC list: the Call button waits for the 'their business line' answer", cf == [True, "Answer the Do Not Call question first", True], cf)
            p.locator("#cConfYes").click()
            p.wait_for_timeout(150)
            href = p.evaluate("() => document.querySelector('#cDial').getAttribute('href')")
            check("d. after 'Yes, it is their business line' the Call button is a tel: link the owner taps (the phone's own dialer)", href == "tel:+18135551001", href)
            p.locator("#tabNext").click()
            ew = p.evaluate("() => [document.querySelectorAll('#nEmails a').length, document.querySelector('#nEmailWhy').textContent]")
            check("d. CAN-SPAM: with no postal address in Settings the email buttons stay locked and say why", ew[0] == 0 and "postal address" in ew[1], ew)
            p.locator("#cClose").click()
            for sel, val in (("#setMe", "Sam Rivera"), ("#setBiz", "Bright Sites"), ("#setAddress", "PO Box 100, Tampa, FL 33601"), ("#setPhone", "813-555-0100"), ("#tDials", "25")):
                p.fill(sel, val)
            p.locator("#saveSet").click()
            p.wait_for_timeout(150)
            p.evaluate(f"() => window.CALLS.open({json.dumps(lid)}, 'next')")
            p.wait_for_timeout(200)
            em = p.evaluate("() => [...document.querySelectorAll('#nEmails a')].map((a) => decodeURIComponent(a.getAttribute('href')))")
            check("d. with your name and postal address saved: 4 email links whose body ends with your address and the opt-out line", len(em) == 4 and all("PO Box 100, Tampa, FL 33601" in e and "will not email you again" in e for e in em), em[:1])
            p.locator("#tabScript").click()
            p.locator("#outs [data-out=dnc]").click()
            p.locator("#outs [data-out=dnc]").click()
            p.wait_for_timeout(200)
            p.locator("#cClose").click()
            p.reload()
            p.wait_for_function("window.CALLS && window.CALLS.ready()", timeout=120000, polling=300)
            p.wait_for_timeout(300)
            rl = p.evaluate(f"""() => {{ const st = window.CALLS.state, L = st.leads.find((x) => x.id === {json.dumps(lid)}), b = window.CALLS.C.blockOf(L, st, window.CALLS.S.now(), window.CALLS.S.rules);
              return {{ demo: window.CALLS.S.demo, n: st.leads.length, opt: st.optouts, code: b && b.code, target: document.querySelector('#goals .tile b').textContent, me: document.querySelector('#setMe').value }}; }}""")
            check("d. after a reload: your list, your settings and targets, and the do-not-call lock are still there (localStorage on this phone)",
                  rl["demo"] is False and rl["n"] == 2 and "+18135551001" in rl["opt"] and rl["code"] == "optout" and rl["target"].endswith("/ 25") and rl["me"] == "Sam Rivera", rl)
            p.locator("#exportJson").click()
            p.wait_for_timeout(300)
            ex = json.loads(p.evaluate("() => document.querySelector('#box').value"))
            check("d. Export JSON: the list, every tap and the opt-out in one file (also shown in the box to copy)", ex["app"] == "agency-calls" and len(ex["leads"]) == 2 and "+18135551001" in ex["optouts"] and any(e["k"] == "dnc" for e in ex["log"]), list(ex)[:6])
            p.locator("#exportCsv").click()
            p.wait_for_timeout(200)
            cv = p.evaluate("() => document.querySelector('#box').value")
            check("d. Export CSV: a header row and both businesses", cv.startswith("name,phone,contact,email") and "Main Pizza" in cv and "Desert Plumbing" in cv, cv[:80])
            far = [u for u in off if not u.startswith(("blob:", "data:"))]  # the Export download is a blob: of this page (never leaves the phone)
            check("d. the real run: only GET requests, nothing off this origin (the export is a local blob:), no console error", set(methods) <= {"GET"} and not far and not errs, (set(methods), far[:3], errs[:3]))
            ctx.close()

            ctx, p, errs, seen, off = AK.page(br, origin, w=375, h=667, reduced=True, lite=True)
            AK.open_app(p, origin, "agency", f"call.html?demo=1&q=low&now={NOW}&lead=d-acme", hook="CALLS")
            sm = p.evaluate("() => ({ open: !document.querySelector('#call').hidden, name: document.querySelector('#cName').textContent, conf: !document.querySelector('#cConfirm').hidden })")
            check("d. 375 x 667, LITE, reduced motion, ?lead=d-acme opens its call screen (an unchecked mobile number asks the DNC question first)", sm == {"open": True, "name": "Acme Plumbing & Heating", "conf": True}, sm)
            t = AK.taps(p)
            check("d. small phone: no sideways scroll, every tap >= 44 px, no console error", AK.no_sideways(p) and not t and not errs, (t[:3], errs[:2]))
            AK.shot(p, "calls-lite")
            ctx.close()
    finally:
        srv.shutdown()


if __name__ == "__main__":
    test_static()
    test_python()
    test_node()
    if "--static" not in sys.argv:
        test_page()
    AK.finish()
