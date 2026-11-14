"""Agency monthly add-ons (agency/upsells, team B4): the Front-desk chat widget and the Review booster (fake clients only).

  a. build: the 3 demo widgets build under the 25,000-byte budget (gzip printed), the runtime .min matches chat/widget.js,
     the committed demo equals a fresh build, every built file passes node --check, the client folder stays out of the repo
  b. matching: 48 sample questions over the 3 presets give the right answer in the SHIPPED file (node); out-of-scope questions
     get the fallback; make_chat's Python norm/stem/SYN read keys exactly like the widget (the keyword dedupe relies on it)
  c. answers: hours in the business's own time zone at fixed moments (open, closed, next opening, holiday closure, past
     midnight, a visitor in Tokyo), a named service's price, area by town and ZIP; a missing fact is never claimed (that FAQ is
     off and listed); the budget guard only ever drops optional FAQs, never a quick button
  d. no network: one fetch() in the file (the form post), no XHR / beacon / socket / image / stylesheet / import / cookie /
     storage, no URL but the client's own links
  e. QR: qr-<id>.svg decodes (own reader: format bits, mask, Reed-Solomon) to the review page URL at level Q with a 4-module
     quiet zone; the encoder equals python-qrcode on golden vectors; the card's inline QR is the same code
  f. review page (static): the Google link sits outside every hidden pane, the private form is a Netlify form with a honeypot,
     nothing loads from another site; templates: the text is <= 160 characters with "Reply STOP", the email has an opt-out,
     nothing a customer sees offers a reward or asks for a good rating
  g. Chromium 390 x 844 (one browser on the machine: flock -w 2400 /tmp/olympus_browser.lock): the widget greets, the chips
     and typed questions answer, after-hours shows the next opening, the lead form validates and its POST is the only request
     the widget makes; Escape closes; 44 px targets; reduced motion; hostile text stays text; the review page shows Google in
     every state, 4-5 stars open Google, 1-3 show the form AND Google, the private message posts, no-JS still offers both;
     the cards print at A6, 3.5 x 2 in and Letter
    python -X utf8 -m tests.test_agency_upsells                  (all)
    python -X utf8 -m tests.test_agency_upsells --no-browser     (a-f)      --browser-only (g)
    flock -w 2400 /tmp/olympus_browser.lock python -X utf8 -m tests.test_agency_upsells --shots    (+ docs/shots/agency_upsells/)
"""
from __future__ import annotations

import datetime
import gzip
import hashlib
import http.server
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from functools import partial
from urllib.parse import parse_qs, urlparse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from agency.upsells import build_demos as BD  # noqa: E402
from agency.upsells import build_widget as BW  # noqa: E402
from agency.upsells import common as K  # noqa: E402
from agency.upsells import make_chat as MC  # noqa: E402
from agency.upsells import make_review as MR  # noqa: E402
from agency.upsells import qr as Q  # noqa: E402

UP = os.path.join(ROOT, "agency", "upsells")
DEMO = os.path.join(UP, "demo")
FIX = os.path.join(UP, "fixtures")
SHOTS = os.path.join(ROOT, "docs", "shots", "agency_upsells")
RES: list = []
TMP = tempfile.mkdtemp(prefix="agency_upsells_")
ET = datetime.timezone(datetime.timedelta(hours=-5))          # US Eastern in November (EST)


def check(name, cond, detail=""):
    RES.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({str(detail)[:700]})" if detail and not cond else ""), flush=True)
    return bool(cond)


def rd(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def built(slug):
    return os.path.join(DEMO, slug, f"chat-demo-{slug}.js")


# node: load a built widget in a bare vm (no DOM) and run questions / answers / states at fixed moments
NODE = r"""
const fs = require("fs"), vm = require("vm");
const req = JSON.parse(fs.readFileSync(0, "utf8")), out = {};
for (const job of req) {
  const sb = {}; sb.globalThis = sb; vm.createContext(sb); vm.runInContext(fs.readFileSync(job.file, "utf8"), sb);
  const api = sb.FrontDeskChat, r = {understand: [], answer: [], state: [], greeting: [], words: []};
  for (const q of job.questions || []) { const m = api.understand(q); r.understand.push({ids: m.ids, sv: m.sv && m.sv.n, town: m.town && m.town.n, zip: m.zip}); }
  for (const [q, t] of job.answers || []) r.answer.push(api.answer(q, new Date(t)).map(a => ({id: a.id, t: a.t, a: a.a || [], lead: !!a.lead})));
  for (const t of job.states || []) { const s = api.state(new Date(t)); r.state.push({open: s.open, until: s.until, next: s.next || null}); }
  for (const t of job.greetings || []) { const g = api.greeting(new Date(t)); r.greeting.push({t: g.t, a: g.a || []}); }
  for (const w of job.words || []) r.words.push(api.words(w).map(x => x.s));
  out[job.name] = r;
}
process.stdout.write(JSON.stringify(out));
"""


def node(jobs, tz=None):
    env = dict(os.environ, TZ=tz) if tz else None
    res = subprocess.run(["node", "-e", NODE], input=json.dumps(jobs), capture_output=True, text=True, env=env, timeout=120)
    if res.returncode:
        raise RuntimeError(res.stderr[-1500:])
    return json.loads(res.stdout)


def iso(y, mo, d, h, mi=0):
    return datetime.datetime(y, mo, d, h, mi, tzinfo=ET).isoformat()


# ---------------------------------------------------------------------------------------------------------------- a. build
def part_build():
    sizes = {}
    for slug, fx, _, _ in BD.FIXTURES:
        res = MC.build(os.path.join(FIX, fx), out=os.path.join(TMP, slug), quiet=True)
        sizes[slug] = (res["bytes"], res["gzip"], res["intents"], res["warnings"])
    print("   built sizes (bytes, gzipped, answers):", {k: v[:3] for k, v in sizes.items()})
    check("a. every demo widget is under the 25,000-byte budget with ALL its answers (none left out by the guard)",
          all(b < MC.BUDGET and not any("left out" in w for w in ws) for b, _, _, ws in sizes.values()), sizes)
    check("a. over the wire it is about 11 KB (gzip, what Netlify sends), far under budget", all(g < 12_500 for _, g, _, _ in sizes.values()), sizes)
    check("a. the runtime chat/widget.min.js was built from the current chat/widget.js (python agency/upsells/build_widget.py)", BW.built_hash() == BW.src_hash(),
          (BW.built_hash(), BW.src_hash()))
    check("a. the runtime alone is under 20 KB (room for the client's facts)", os.path.getsize(BW.OUT) < 20_000, os.path.getsize(BW.OUT))
    fresh = os.path.join(TMP, "demo_fresh")
    BD.build(fresh)
    diff = BD.same_tree(DEMO, fresh)
    check("a. the committed demo (agency/upsells/demo/) equals a fresh build: python agency/upsells/build_demos.py", not diff, diff[:5])
    bad = []
    for slug, _, _, _ in BD.FIXTURES:
        r = subprocess.run(["node", "--check", built(slug)], capture_output=True, text=True)
        if r.returncode:
            bad.append((slug, r.stderr[-300:]))
    check("a. every built file is valid JavaScript (node --check)", not bad, bad)
    src = re.sub(r"^\s*//.*$", "", re.sub(r"/\*.*?\*/", "", rd(os.path.join(UP, "chat", "widget.js")), flags=re.S), flags=re.M)
    hits = re.findall(r".{0,30}(?:\?\.|\?\?|`|\(\?<[=!]).{0,10}", src)
    check("a. the widget source keeps to what iPhone Safari 12+ runs: no ?. / ?? / template strings / lookbehind", not hits, hits)
    probe = os.path.join(ROOT, "data", "agency", "clients", "x.json")
    ignored = subprocess.run(["git", "check-ignore", "-q", probe], cwd=ROOT).returncode == 0
    print(f"   note: data/agency/ is {'ignored by git' if ignored else 'NOT yet in .gitignore (wiring for the lead)'}; make_chat/make_review write real clients there by default")
    check("a. real client output defaults to data/agency/upsells/<id>/ (never inside agency/)", K.default_out({"id": "x"}).endswith(os.path.join("data", "agency", "upsells", "x")))


# ---------------------------------------------------------------------------------------------------------------- b. matching
SAMPLES = {
    "harborline": [
        ("what time do you close today?", "hours"), ("r u open sunday", "hours"), ("are you open on thanksgiving", "hours"),
        ("how much is a skin fade", "prices"), ("how much 4 a beard trim??", "prices"), ("do you take walk-ins", "walkins"),
        ("do i need an apointment", "walkins"), ("can I book online for saturday", "book"), ("where are you located", "dir"),
        ("is there parking", "dir"), ("do you take apple pay", "pay"), ("can you cut my 4 year old son's hair", "kids"),
        ("how long does a cut take", "duration"), ("do you guys do straight razor shaves", "services"), ("I'm running late for my appointment", "cancel"),
        ("do you sell gift cards", "gift"), ("any student discount", "discount"), ("do you cut curly hair", "hairtypes"),
        ("hello", "greet"), ("thanks!", "thanks"), ("can someone call me back", "lead")],
    "blueline": [
        ("my water heater is leaking everywhere", "emergency"), ("pipe burst in the kitchen help!!", "emergency"), ("no hot water since this morning", "emergency"),
        ("I smell gas in my house", "gas"), ("how much do you charge for a service call", "prices"), ("can I get a free estimate on a new ac unit", "estimate"),
        ("are u licensed and insured", "licensed"), ("do you service brandon", "area"), ("do you come out to 33511", "area"),
        ("whats your warranty on repairs", "warranty"), ("do you offer financing", "financing"), ("how soon can someone come out", "response"),
        ("do you work on trane units", "brands"), ("i need a tune up for my ac", "maintenance"), ("do you install tankless water heaters", "services")],
    "casamarina": [
        ("can i make a reservation for 6 people tonight", "book"), ("table for two friday at 7?", "book"), ("do you have vegan options", "dietary"),
        ("is the menu gluten free friendly", "dietary"), ("do you deliver", "delivery"), ("can I order takeout", "takeout"),
        ("do you do catering for a birthday party", "events"), ("what's on the menu", "menu"), ("is there a kids menu", "kids"),
        ("when is happy hour", "happyhour"), ("can we sit outside on the patio with our dog", "outdoor"), ("where do i park", "dir")],
}
OUT_OF_SCOPE = [("harborline", "what's the wifi password"), ("blueline", "who won the game last night"), ("casamarina", "what's the meaning of life")]


def part_matching():
    jobs = [{"name": slug, "file": built(slug), "questions": [q for q, _ in SAMPLES[slug]] + [q for s, q in OUT_OF_SCOPE if s == slug]} for slug in SAMPLES]
    got = node(jobs)
    total = sum(len(v) for v in SAMPLES.values())
    wrong = []
    for slug, cases in SAMPLES.items():
        for (q, want), r in zip(cases, got[slug]["understand"]):
            if not r["ids"] or r["ids"][0] != want:
                wrong.append((slug, q, want, r["ids"]))
    check(f"b. intent matching: {total - len(wrong)}/{total} sample questions (typos, slang, plurals) get the right answer in the shipped files", total >= 40 and not wrong, wrong)
    miss = []
    for slug in SAMPLES:
        extra = [q for s, q in OUT_OF_SCOPE if s == slug]
        for q, r in zip(extra, got[slug]["understand"][len(SAMPLES[slug]):]):
            if r["ids"]:
                miss.append((slug, q, r["ids"]))
    check("b. questions it can't answer get the fallback (suggestions + call / text / leave your number), not a wrong answer", not miss, miss)
    sv = {q: r["sv"] for (q, _), r in zip(SAMPLES["harborline"], got["harborline"]["understand"])}
    check("b. a named service is recognised (skin fade, beard trim, straight razor)", sv["how much is a skin fade"] == "Skin fade" and sv["how much 4 a beard trim??"] == "Beard trim"
          and sv["do you guys do straight razor shaves"] == "Hot towel shave", sv)
    # the Python port used for keyword dedupe reads every key the same way as the widget
    keys = sorted({k.split(":")[0] for p in MC.preset_names() + ["_base"] for it in K.load_json(os.path.join(MC.PRESETS, p + ".json"))["intents"] for k in it["keys"]}
                  | {"walk-ins", "Tommorow's hours?", "Café crème", "it's 24/7", "kids'", "shopping", "cutting", "dresses", "allergies", "closed", "hrs"})
    js = node([{"name": "w", "file": built("harborline"), "words": keys}])["w"]["words"]
    diff = [(k, list(MC.signature(k)), j) for k, j in zip(keys, js) if list(MC.signature(k)) != j]
    check(f"b. make_chat's Python norm/stem/SYN read all {len(keys)} preset keys exactly like the widget", not diff, diff[:6])


# ---------------------------------------------------------------------------------------------------------------- c. answers
def part_answers():
    hb = built("harborline")
    job = {"name": "hb", "file": hb,
           "states": [iso(2026, 11, 14, 11, 5), iso(2026, 11, 15, 16), iso(2026, 11, 25, 20), iso(2026, 11, 16, 10)],
           "greetings": [iso(2026, 11, 14, 11, 5), iso(2026, 11, 15, 16), iso(2026, 11, 16, 10)],
           "answers": [("how much is a skin fade", iso(2026, 11, 14, 11)), ("are you open sunday?", iso(2026, 11, 12, 11)),
                       ("what are your hours", iso(2026, 11, 14, 11)), ("are you open on thanksgiving", iso(2026, 11, 14, 11)),
                       ("are you open this weekend", iso(2026, 11, 12, 11)), ("open tomorrow?", iso(2026, 11, 15, 9))]}
    r = node([job])["hb"]
    s = r["state"]
    check("c. Saturday 11:05 am Tampa time: open until 5 pm", s[0]["open"] == 1 and s[0]["until"] == 17 * 60, s[0])
    check("c. Sunday 4 pm: closed; Monday is a closed day, so the next opening is Tuesday 9 am", not s[1]["open"] and s[1]["next"] == {"k": 2, "d": 2, "m": 540}, s[1])
    check("c. the night before Thanksgiving (a closed date): the next opening skips to Friday 9 am", not s[2]["open"] and s[2]["next"]["d"] == 5 and s[2]["next"]["k"] == 2, s[2])
    g = r["greeting"]
    check("c. greeting: open = the welcome; closed = the after-hours message with the next opening + 'leave my number'",
          "virtual front desk" in g[0]["t"] and "closed right now" in g[1]["t"] and "on Tuesday at 9 am" in g[1]["t"] and "lead" in g[1]["a"]
          and "open tomorrow at 9 am" in g[2]["t"], g)
    a = [x[0]["t"] for x in r["answer"]]
    check("c. 'how much is a skin fade' -> 'Skin fade: $35 (about 45 min).'", a[0] == "Skin fade: $35 (about 45 min).", a[0])
    check("c. 'are you open sunday?' asked on a Thursday -> Sunday's hours", a[1] == "On Sunday we're open 10 am–3 pm.", a[1])
    check("c. 'what are your hours' -> status + the week, Monday first", a[2].startswith("We're open now until 5 pm.") and "• Mon closed" in a[2] and "• Tue–Thu 9 am–7 pm" in a[2], a[2])
    check("c. holidays: the closed dates coming up are listed", "Thanksgiving (11/26)" in a[3] and "Christmas Day (12/25)" in a[3], a[3])
    check("c. 'this weekend' -> Saturday and Sunday", a[4] == "This weekend: Saturday 8 am–5 pm, Sunday 10 am–3 pm.", a[4])
    check("c. 'open tomorrow?' asked on a Sunday -> Monday is closed", a[5] == "Tomorrow we're closed.", a[5])
    tokyo = node([dict(job, answers=[], greetings=[])], tz="Asia/Tokyo")["hb"]["state"]
    check("c. a visitor in another time zone (Tokyo) sees the shop's own hours (same results)", tokyo == s, (tokyo, s))
    # past midnight + area + facts that are missing
    c = K.load_json(os.path.join(FIX, "demo_restaurant.json"))
    c["id"], c["chat"]["hours"]["fri"] = "test-late", "17:00-02:00"
    c["chat"]["facts"].pop("delivery")
    p = os.path.join(TMP, "late.json")
    K.write(p, json.dumps(c))
    res = MC.build(p, out=os.path.join(TMP, "late"), quiet=True)
    late = node([{"name": "l", "file": res["file"], "states": [iso(2026, 11, 14, 1, 30), iso(2026, 11, 14, 2, 30)], "questions": ["do you deliver"]}])["l"]
    check("c. a Friday 5 pm-2 am night: Saturday 1:30 am is still open (until 2 am), 2:30 am is closed", late["state"][0]["open"] == 1 and late["state"][0]["until"] % 1440 == 120
          and not late["state"][1]["open"], late["state"])
    check("c. a missing fact is never made up: no delivery fact -> no delivery answer (fallback) + 'check with the client' warning",
          not late["understand"][0]["ids"] and any("delivery" in w for w in res["warnings"]), (late["understand"], res["warnings"]))
    bl = node([{"name": "b", "file": built("blueline"), "answers": [("do you service brandon", iso(2026, 11, 14, 10)), ("do you come to 33511", iso(2026, 11, 14, 10)),
                                                                     ("do you come to 34470?", iso(2026, 11, 14, 10)), ("pipe burst help", iso(2026, 11, 14, 10))]}])["b"]["answer"]
    check("c. area: a listed town -> yes; a listed ZIP -> yes; another ZIP -> may be outside + leave your address",
          bl[0][0]["t"] == "Yes, we serve Brandon!" and bl[1][0]["t"] == "Yes, 33511 is in our area!" and bl[2][0]["t"].startswith("34470 may be outside our area."), [x[0]["t"] for x in bl[:3]])
    check("c. plumber emergency: shut-off advice + the emergency line button", "main water valve" in bl[3][0]["t"] and "emergency" in bl[3][0]["a"], bl[3])
    p2 = K.load_json(os.path.join(FIX, "demo_plumber.json"))
    p2["id"] = "test-nolicense"
    p2["chat"]["facts"].pop("license")
    pp = os.path.join(TMP, "nolic.json")
    K.write(pp, json.dumps(p2))
    cfg, warns, _ = MC.build_config(K.load_client(pp))
    check("c. no license number in the file -> the 'Licensed & insured?' answer AND its quick button are off, with a warning",
          "licensed" not in [x[0] for x in cfg["it"]] and "licensed" not in cfg["ch"] and any("license" in w for w in warns), (cfg["ch"], warns))
    # the budget guard: a client with far too much text loses optional FAQs only, keeps every quick button
    big = K.load_json(os.path.join(FIX, "demo_barber.json"))
    big["id"] = "test-big"
    big["chat"]["faqs"] = [{"id": f"extra{i}", "a": "A long custom answer about our policy number %d. " % i * 6, "keys": [f"policy{i}", f"rule {i}"]} for i in range(14)]
    bp = os.path.join(TMP, "big.json")
    K.write(bp, json.dumps(big))
    rb = MC.build(bp, out=os.path.join(TMP, "big"), quiet=True)
    kept = json.loads(re.search(r'"ch":(\[[^\]]*\])', rd(rb["file"])).group(1))
    check("c. budget guard: a client with too much text still builds under 25,000 bytes, drops only optional FAQs (listed), keeps every quick button",
          rb["bytes"] < MC.BUDGET and any("left out" in w for w in rb["warnings"]) and kept == ["hours", "prices", "walkins", "book", "dir", "pay"], (rb["bytes"], rb["warnings"], kept))
    try:
        K.parse_hours({"mon": "9-5", "tue": "9am-7pm", "wed": "11-14, 17-22", "thu": "closed", "fri": "18:00-02:00", "sat": "24h", "sun": "10-3"})
        okh = K.parse_day("9-5") == [[540, 1020]] and K.parse_day("9-7pm") == [[540, 1140]] and K.parse_day("18:00-02:00") == [[1080, 1560]] and K.parse_day("12-8") == [[720, 1200]]
    except K.ClientError as e:
        okh = str(e)
    check("c. hours as owners write them: 9-5 (= 9 am-5 pm), 9-7pm, split shifts, past midnight, 24h, closed", okh is True, okh)
    bad = 0
    for spec in ({"mon": "nine to five"}, {"funday": "9-5"}):
        try:
            K.parse_hours(dict({d: "closed" for d in K.DAYS}, **spec))
        except K.ClientError:
            bad += 1
    check("c. unreadable hours are refused with a plain message (not guessed)", bad == 2)
    sp = os.path.join(TMP, "starter.json")
    MC.new_client("barber", "test-starter", "Test Cuts", path=sp)
    try:
        MC.build(sp, out=os.path.join(TMP, "starter"), quiet=True)
        starter = "built"
    except K.ClientError as e:
        starter = str(e)
    todo = K.unfilled(K.load_json(sp))
    check("c. a starter file (the preset's sample hours and prices) is refused until every FILL is replaced: no sample fact goes live",
          "still say FILL" in starter and "chat.hours.mon" in starter and {"chat.services[0].price", "chat.payments[0]", "review.google_review_url"} <= set(todo), (starter, todo))


# ---------------------------------------------------------------------------------------------------------------- d. no network
def part_network():
    for slug, fx, _, _ in BD.FIXTURES:
        js = rd(built(slug))
        cfg = MC.build_config(K.load_client(os.path.join(FIX, fx)))[0]
        banned = [w for w in ("XMLHttpRequest", "sendBeacon", "WebSocket", "EventSource", "importScripts", "new Image", "<img", "<link", "<script", "@import", "url(",
                              "document.cookie", "localStorage", "sessionStorage", "indexedDB", "navigator.geolocation", "postMessage", "<iframe", "eval(", "Function(")
                  if w in js]
        urls = set(re.findall(r"https?://[^\"'\s)<>]+", js))
        own = {u for u in (cfg["bk"], cfg["mp"], cfg["mu"]) if u}
        check(f"d. {slug}: one fetch() (the form post) and nothing else that can reach the network or store anything", js.count("fetch(") == 1 and not banned, banned)
        check(f"d. {slug}: the only web addresses in the file are the client's own links (booking / map / menu)", urls <= own, urls - own)


# ---------------------------------------------------------------------------------------------------------------- e. QR
QR_BLOCKS = {  # ISO/IEC 18004 table 9, versions 1-10: level -> (EC codewords per block, [(blocks, data codewords each)])
    1: {"L": (7, [(1, 19)]), "M": (10, [(1, 16)]), "Q": (13, [(1, 13)]), "H": (17, [(1, 9)])},
    2: {"L": (10, [(1, 34)]), "M": (16, [(1, 28)]), "Q": (22, [(1, 22)]), "H": (28, [(1, 16)])},
    3: {"L": (15, [(1, 55)]), "M": (26, [(1, 44)]), "Q": (18, [(2, 17)]), "H": (22, [(2, 13)])},
    4: {"L": (20, [(1, 80)]), "M": (18, [(2, 32)]), "Q": (26, [(2, 24)]), "H": (16, [(4, 9)])},
    5: {"L": (26, [(1, 108)]), "M": (24, [(2, 43)]), "Q": (18, [(2, 15), (2, 16)]), "H": (22, [(2, 11), (2, 12)])},
    6: {"L": (18, [(2, 68)]), "M": (16, [(4, 27)]), "Q": (24, [(4, 19)]), "H": (28, [(4, 15)])},
    7: {"L": (20, [(2, 78)]), "M": (18, [(4, 31)]), "Q": (18, [(2, 14), (4, 15)]), "H": (26, [(4, 13), (1, 14)])},
    8: {"L": (24, [(2, 97)]), "M": (22, [(2, 38), (2, 39)]), "Q": (22, [(4, 18), (2, 19)]), "H": (26, [(4, 14), (2, 15)])},
    9: {"L": (30, [(2, 116)]), "M": (22, [(3, 36), (2, 37)]), "Q": (20, [(4, 16), (4, 17)]), "H": (24, [(4, 12), (4, 13)])},
    10: {"L": (18, [(2, 68), (2, 69)]), "M": (26, [(4, 43), (1, 44)]), "Q": (24, [(6, 19), (2, 20)]), "H": (28, [(6, 15), (2, 16)])},
}
QR_ALIGN = {1: [], 2: [6, 18], 3: [6, 22], 4: [6, 26], 5: [6, 30], 6: [6, 34], 7: [6, 22, 38], 8: [6, 24, 42], 9: [6, 26, 46], 10: [6, 28, 50]}
QR_MASK = {0: lambda r, c: (r + c) % 2 == 0, 1: lambda r, c: r % 2 == 0, 2: lambda r, c: c % 3 == 0, 3: lambda r, c: (r + c) % 3 == 0,
           4: lambda r, c: (r // 2 + c // 3) % 2 == 0, 5: lambda r, c: (r * c) % 2 + (r * c) % 3 == 0, 6: lambda r, c: ((r * c) % 2 + (r * c) % 3) % 2 == 0,
           7: lambda r, c: ((r + c) % 2 + (r * c) % 3) % 2 == 0}
# golden vectors from the python-qrcode library (forced version + mask): sha256 of the module rows, first 24 hex
QR_GOLDEN = [("https://example.com/review/", "Q", 3, 5, "b7fc629fd7425ae081827568"), ("https://harborfade.example/review/", "Q", 4, 2, "f9774dd5071ef97a30f04059"),
             ("https://g.page/r/CQ0aBcDeFgHiEBM/review", "M", 4, 6, "7c8484cebe0a0d9e6e1daa15"), ("HELLO WORLD", "H", 2, 0, "a59fe6bb9127f552dcd2b5bb"),
             ("https://www.a-much-longer-business-name-for-testing.example/review/?source=card", "Q", 7, 3, "a6de7add484e7b324d9b6c4c")]


def qr_read(rows):
    """an independent reader for a module matrix (versions 1-10, byte mode) -> dict(text, level, mask, rs_ok, format_ok)"""
    m = [[c == "1" for c in row] for row in rows]
    n = len(m)
    ver = (n - 17) // 4
    fn = [[False] * n for _ in range(n)]

    def mark(r0, c0, h, w):
        for r in range(max(0, r0), min(n, r0 + h)):
            for c in range(max(0, c0), min(n, c0 + w)):
                fn[r][c] = True
    mark(0, 0, 9, 9), mark(0, n - 8, 9, 8), mark(n - 8, 0, 8, 9), mark(6, 0, 1, n), mark(0, 6, n, 1)
    for a in QR_ALIGN[ver]:
        for b in QR_ALIGN[ver]:
            if (a, b) not in ((6, 6), (6, n - 7), (n - 7, 6)):
                mark(a - 2, b - 2, 5, 5)
    if ver >= 7:
        mark(0, n - 11, 6, 3), mark(n - 11, 0, 3, 6)
    val = 0
    for r, c in [(8, c) for c in (0, 1, 2, 3, 4, 5, 7, 8)] + [(r, 8) for r in (7, 5, 4, 3, 2, 1, 0)]:
        val = (val << 1) | int(m[r][c])
    fmt = val ^ 0x5412
    level, mask = {1: "L", 0: "M", 3: "Q", 2: "H"}[fmt >> 13], (fmt >> 10) & 7
    rem = (fmt >> 10) << 10
    for i in range(14, 9, -1):
        if rem & (1 << i):
            rem ^= 0x537 << (i - 10)
    bits, col, up = [], n - 1, True
    while col > 0:
        if col == 6:
            col -= 1
        for r in (range(n - 1, -1, -1) if up else range(n)):
            for c in (col, col - 1):
                if not fn[r][c]:
                    bits.append(int(m[r][c] ^ QR_MASK[mask](r, c)))
        up, col = not up, col - 2
    words = [int("".join(map(str, bits[i:i + 8])), 2) for i in range(0, len(bits) - 7, 8)]
    ecc, groups = QR_BLOCKS[ver][level]
    sizes = [d for cnt, d in groups for _ in range(cnt)]
    data, eccb, k = [[] for _ in sizes], [[] for _ in sizes], 0
    for i in range(max(sizes)):
        for j, sz in enumerate(sizes):
            if i < sz:
                data[j].append(words[k])
                k += 1
    for i in range(ecc):
        for j in range(len(sizes)):
            eccb[j].append(words[k])
            k += 1
    exp, log, x = [0] * 512, [0] * 256, 1
    for i in range(255):
        exp[i], log[x] = x, i
        x <<= 1
        if x & 0x100:
            x ^= 0x11D
    for i in range(255, 512):
        exp[i] = exp[i - 255]

    def syndromes(block):
        out = []
        for i in range(ecc):
            s = 0
            for b in block:
                s = (exp[(log[s] + i) % 255] if s else 0) ^ b
            out.append(s)
        return out
    rs_ok = all(not any(syndromes(d + e)) for d, e in zip(data, eccb))
    stream = "".join(f"{w:08b}" for blk in data for w in blk)
    cbits = 8 if ver < 10 else 16
    count = int(stream[4:4 + cbits], 2)
    body = stream[4 + cbits:4 + cbits + 8 * count]
    return {"mode": stream[:4], "text": bytes(int(body[i:i + 8], 2) for i in range(0, len(body), 8)).decode("ascii", "replace"), "level": level, "mask": mask,
            "rs_ok": rs_ok, "format_ok": (fmt & 0x3FF) == rem}


def svg_rows(svg):
    dim = int(re.search(r'viewBox="0 0 (\d+) (\d+)"', svg).group(1))
    runs = [tuple(map(int, t)) for t in re.findall(r"M(\d+) (\d+)h(\d+)v1h-\d+z", svg)]
    xs = [x for x, _, _ in runs] + [x + w for x, _, w in runs]
    ys = [y for _, y, _ in runs]
    quiet = min(min(xs), min(ys), dim - max(xs), dim - 1 - max(ys))
    n = dim - 8
    grid = [["0"] * n for _ in range(n)]
    for x, y, w in runs:
        for i in range(w):
            grid[y - 4][x - 4 + i] = "1"
    return ["".join(r) for r in grid], quiet


def part_qr():
    bad = []
    for text, ecl, ver, mask, want in QR_GOLDEN:
        rows = Q.make(text, ecl=ecl, version=ver, mask=mask).rows()
        if hashlib.sha256("\n".join(rows).encode()).hexdigest()[:24] != want:
            bad.append(text)
    check("e. the QR maker equals the python-qrcode library on 5 golden vectors (versions 2-7, levels M/Q/H, fixed masks)", not bad, bad)
    rr = [qr_read(Q.make(t, ecl=e).rows()) for t, e, _, _, _ in QR_GOLDEN]
    check("e. the independent reader decodes the maker's own choices (auto version + mask) with valid format bits and Reed-Solomon",
          all(r["text"] == g[0] and r["rs_ok"] and r["format_ok"] for r, g in zip(rr, QR_GOLDEN)), rr)
    for slug, fx, _, _ in BD.FIXTURES:
        client = K.load_client(os.path.join(FIX, fx))
        want = MR.page_url(client, client.get("review") or {})
        svg = rd(os.path.join(DEMO, slug, "kit", "print", f"qr-{client['id']}.svg"))
        rows, quiet = svg_rows(svg)
        r = qr_read(rows)
        check(f"e. {slug}: the printed QR decodes to the review page {want} (level Q, byte mode, RS ok), quiet zone >= 4 modules",
              r["text"] == want and r["level"] == "Q" and r["mode"] == "0100" and r["rs_ok"] and r["format_ok"] and quiet >= 4, (r, quiet))
        card = rd(os.path.join(DEMO, slug, "kit", "print", "card-a6.html"))
        d_card = re.search(r'<path fill="#111111" d="([^"]+)"', card).group(1)
        d_svg = re.search(r'<path fill="#111111" d="([^"]+)"', svg).group(1)
        check(f"e. {slug}: the cards print that same code (inline SVG, vector)", d_card == d_svg and rd(os.path.join(DEMO, slug, "kit", "print", "cards-letter-10.html")).count(d_svg) == 10)


# ---------------------------------------------------------------------------------------------------------------- f. review page + templates (static)
def part_review_static():
    for slug, fx, _, _ in BD.FIXTURES:
        client = K.load_client(os.path.join(FIX, fx))
        g = MR.google_link(client["review"])
        page = rd(os.path.join(DEMO, slug, "review", "index.html"))
        tail = page[page.index("</section>"):]                      # after the panes: the always-visible footer
        check(f"f. {slug}: the Google review link is on the page {page.count(K.esc(g))} times, one of them outside every pane (visible whatever the rating)",
              page.count(f'href="{K.esc(g)}"') >= 4 and f'href="{K.esc(g)}"' in tail and "hidden" not in tail.split("<script>")[0], page.count(g))
        form = re.search(r"<form[^>]+>", page).group(0)
        check(f"f. {slug}: the private message is a Netlify form with a honeypot, and the JS posts it to the site itself",
              'data-netlify="true"' in form and 'netlify-honeypot="bot-field"' in form and 'name="form-name"' in page and 'fetch("/"' in page)
        ext = [u for u in re.findall(r'(?:src|href)="(https?://[^"]+)"', page) if u != K.esc(g)]
        check(f"f. {slug}: nothing loads from another site (no fonts, scripts, images, trackers); the only outside link is Google", not ext and "<img" not in page, ext)
        check(f"f. {slug}: the page says what 4-5 stars do before anyone taps (WCAG 3.2.2) and offers Google AND a private message after 1-3",
              "4 or 5 stars opens our Google review page" in page and "Post a Google review" in page and "Send privately" in page)
        txt = rd(os.path.join(DEMO, slug, "kit", "print", "requests.txt"))
        sms = [ln.strip() for ln in txt.splitlines() if "Reply STOP to opt out" in ln][0]
        check(f"f. {slug}: the text message is one SMS (<= 160 characters with a long first name), names the business and ends with 'Reply STOP to opt out'",
              len(sms.replace("[first name]", "Christopher")) <= 160 and client["name"] in sms and re.fullmatch(r"[\x20-\x7e]+", sms), (len(sms), sms))
        check(f"f. {slug}: texts only with consent; the email has an opt-out and (when known) the mailing address; ask every customer",
              "ONLY to customers who said yes" in txt and 'Reply "unsubscribe"' in txt and "EVERY customer" in txt
              and ((client["chat"].get("address") or "") in txt))
        said = txt.split("1) IN PERSON")[1]
        customer_facing = "\n".join(ln for ln in said.splitlines() if not ln.strip().startswith(("Rules:", "Not legal advice", "First ask")))
        for name, html in (("review page", page), ("A6 card", rd(os.path.join(DEMO, slug, "kit", "print", "card-a6.html"))),
                           ("business card", rd(os.path.join(DEMO, slug, "kit", "print", "card-business.html"))), ("request messages", customer_facing)):
            hit = MR.INCENTIVE.search(MR.visible_text(html))
            if hit:
                break
        check(f"f. {slug}: nothing a customer sees offers a reward or asks for a good / 5-star review (page, cards, messages)", not hit, hit and hit.group(0))
    try:
        MR.google_link({"google_review_url": "https://evil.example/review"})
        refused = False
    except K.ClientError:
        refused = True
    check("f. a review link that is not Google's is refused (the page could otherwise send customers anywhere)", refused)
    check("f. a Place ID alone builds the documented review URL", MR.google_link({"place_id": "ChIJabc"}) == "https://search.google.com/local/writereview?placeid=ChIJabc")
    strict = K.load_json(os.path.join(FIX, "demo_barber.json"))
    strict["id"], strict["review"]["same_for_all"] = "test-strict", True
    sp = os.path.join(TMP, "strict.json")
    K.write(sp, json.dumps(strict))
    MR.build(sp, out=os.path.join(TMP, "strict"), quiet=True)
    sp_page = rd(os.path.join(TMP, "strict", "review", "index.html"))
    check("f. strict mode (review.same_for_all): every rating gets the same two choices, no automatic redirect, and the page says so",
          "SAME = true" in sp_page and "Then pick: a Google review or a private message." in sp_page and "4 or 5 stars opens" not in sp_page)


# ---------------------------------------------------------------------------------------------------------------- g. Chromium
POSTS: list = []
REQS: list = []


class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        REQS.append(("GET", self.path))
        super().do_GET()

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(n).decode()
        REQS.append(("POST", self.path))
        POSTS.append((self.path, self.headers.get("Content-Type"), {k: v[0] for k, v in parse_qs(body, keep_blank_values=True).items()}))
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(b"<p>Thank you!</p>")


def serve(root):
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), partial(Handler, directory=root))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def part_browser(shots: bool):
    from tests import browser_kit as BK
    from playwright.sync_api import sync_playwright
    if shots:
        os.makedirs(SHOTS, exist_ok=True)
    site = os.path.join(TMP, "site")
    shutil.copytree(DEMO, site)
    hostile = K.load_json(os.path.join(FIX, "demo_barber.json"))
    hostile.update(id="test-hostile", name="Joe's <img src=x onerror=alert(1)> Cuts")
    hostile["chat"]["facts"]["walkins"] = "<script>window.__pwned=1</script><b>bold?</b> & more"
    hp = os.path.join(TMP, "hostile.json")
    K.write(hp, json.dumps(hostile))
    os.makedirs(os.path.join(site, "hostile"))
    K.write(os.path.join(site, "hostile", "index.html"), "<!doctype html><html><head><meta name=viewport content='width=device-width'></head><body><h1>x</h1></body></html>")
    MC.build(hp, out=os.path.join(TMP, "hostile_kit"), site=os.path.join(site, "hostile"), quiet=True)
    MR.build(hp, out=os.path.join(TMP, "hostile_kit"), site=os.path.join(site, "hostile"), quiet=True)
    strict = K.load_json(os.path.join(FIX, "demo_barber.json"))
    strict["id"], strict["review"]["same_for_all"] = "test-strict", True
    stp = os.path.join(TMP, "strict_site.json")
    K.write(stp, json.dumps(strict))
    os.makedirs(os.path.join(site, "strict"))
    MR.build(stp, out=os.path.join(TMP, "strict_kit"), site=os.path.join(site, "strict"), quiet=True)
    srv, base = serve(site)
    outside = []

    def snap(p, name, full=False):
        if shots:
            p.wait_for_timeout(500)                                    # let the 0.18-0.25 s fade-ins finish
            p.screenshot(path=os.path.join(SHOTS, name), full_page=full)

    with sync_playwright() as pw:
        br = BK.launch(pw)

        def phone(js=True, reduced=False, when=iso(2026, 11, 14, 11, 5)):
            ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True, java_script_enabled=js,
                                 reduced_motion="reduce" if reduced else "no-preference")
            ctx.route("**/*", lambda r: (outside.append(r.request.url), r.fulfill(status=200, body="<p>outside page (test stub)</p>", content_type="text/html"))
                      if not r.request.url.startswith(base) else r.continue_())
            p = ctx.new_page()
            errs = []
            p.on("pageerror", lambda e: errs.append(str(e)))
            if js and when:
                p.clock.set_fixed_time(datetime.datetime.fromisoformat(when))
            return ctx, p, errs

        W = "[data-frontdesk-chat]"
        try:
            # ---- the chat on the barber demo, Saturday 11:05 am (open)
            ctx, p, errs = phone()
            REQS.clear(), POSTS.clear()
            p.goto(base + "/harborline/")
            p.wait_for_selector(W + " >> .l")
            snap(p, "chat-01-site-bubble.png")
            lb = p.locator(W + " >> .l").bounding_box()
            check("g. the chat bubble sits bottom-right, 62 px, inside the screen", lb and lb["width"] >= 60 and lb["x"] + lb["width"] <= 390 and lb["y"] + lb["height"] <= 844, lb)
            p.locator(W + " >> .l").click()
            p.wait_for_selector(W + " >> .ch")
            bar = p.locator(W + " >> .bar .bt").all_inner_texts()
            check("g. the bottom bar fits a phone on one line: Call / Text / Book (short labels)", [t.strip() for t in bar] == ["Call", "Text", "Book"]
                  and all(p.locator(W + " >> .bar .bt").nth(i).bounding_box()["height"] < 60 for i in range(3)), bar)
            check("g. open: aria-expanded, full screen on a phone, greeting + 6 suggested questions + Call / Text / Book bar",
                  p.locator(W + " >> .l").get_attribute("aria-expanded") == "true" and p.locator(W + " >> .cp").count() == 6
                  and "virtual front desk" in p.locator(W + " >> .m").first.inner_text() and p.locator(W + " >> .bar .bt").count() == 3
                  and abs(p.locator(W + " >> .p").bounding_box()["width"] - 390) < 1)
            check("g. the header shows the live status in the shop's time zone", "Open now · until 5 pm" in p.locator(W + " >> .hs").inner_text(), p.locator(W + " >> .hs").inner_text())
            snap(p, "chat-02-open-greeting.png")
            small = p.evaluate("""() => { const r = document.querySelector('[data-frontdesk-chat]').shadowRoot; return [...r.querySelectorAll('.p button, .p a, .p input')]
                     .filter(e => e.offsetParent).map(e => [e.className || e.tagName, Math.round(e.getBoundingClientRect().height), Math.round(e.getBoundingClientRect().width)])
                     .filter(([c, h, w]) => h < 44 || w < 44); }""")
            check("g. every button, link and the input in the chat is at least 44 x 44 px", not small, small)
            inp = p.locator(W + " >> .in input")
            inp.fill("how much is a skin fade?")
            inp.press("Enter")
            inp.fill("do you take walk-ins")
            inp.press("Enter")
            msgs = p.locator(W + " >> .m:not(.u)")
            check("g. typed questions get their answers (price of the named service; walk-ins with Book / Call buttons)",
                  "Skin fade: $35" in msgs.nth(1).inner_text() and "Walk-ins are welcome" in msgs.nth(2).inner_text() and msgs.nth(2).locator(".bt").count() == 2)
            snap(p, "chat-03-answers.png")
            p.locator(W + " >> .cp", has_text="Hours").first.click()
            check("g. a suggested-question chip answers too (the week's hours)", "Tue–Thu 9 am–7 pm" in msgs.last.inner_text(), msgs.last.inner_text())
            snap(p, "chat-04-hours.png")
            inp.fill("can someone call me back about a beard trim on friday")
            inp.press("Enter")
            p.wait_for_selector(W + " >> .fm")
            f = p.locator(W + " >> .fm")
            check("g. 'call me back' opens the lead form, prefilled with what they asked", "beard trim on friday" in f.locator("textarea").input_value())
            f.locator("button").click()
            check("g. the form checks the name first, then a 10-digit phone (plain words, role=alert)", "Please add your name." in f.locator(".er").inner_text())
            f.locator("input[name=name]").fill("Sam Rivera")
            f.locator("input[name=phone]").fill("555-01")
            f.locator("button").click()
            check("g. ... and refuses a short phone number", "10-digit" in f.locator(".er").inner_text() and f.locator("input[name=phone]").get_attribute("aria-invalid") == "true")
            f.locator("input[name=phone]").fill("(813) 555-0199")
            snap(p, "chat-06-lead-form.png")
            f.locator("button").click()
            p.wait_for_function("document.querySelector('[data-frontdesk-chat]').shadowRoot.querySelector('.lg').innerText.includes('Thanks, Sam!')", timeout=8000)
            snap(p, "chat-07-lead-sent.png")
            post = POSTS[-1] if POSTS else None
            check("g. the lead goes to the site's own Netlify form: POST / urlencoded with form-name, name, phone, need, page, chat and the empty honeypot",
                  post and post[0] == "/" and (post[1] or "").startswith("application/x-www-form-urlencoded") and post[2].get("form-name") == "frontdesk-chat"
                  and post[2].get("name") == "Sam Rivera" and post[2].get("phone") == "(813) 555-0199" and "beard trim" in post[2].get("need", "")
                  and post[2].get("page", "").endswith("/harborline/") and post[2].get("bot-field") == "", post)
            widget_reqs = [r for r in REQS if r not in (("GET", "/harborline/"), ("GET", "/harborline/chat-demo-harborline.js"), ("GET", "/favicon.ico"))]
            check("g. no network calls except the form post: the widget made exactly one request (POST /) and nothing left the site",
                  widget_reqs == [("POST", "/")] and not outside, (widget_reqs, outside))
            cookies = ctx.cookies()
            store = p.evaluate("[localStorage.length, sessionStorage.length]")
            check("g. it set no cookies and stored nothing", not cookies and store == [0, 0], (cookies, store))
            p.keyboard.press("Escape")
            check("g. Escape closes the chat and gives focus back to the bubble", p.locator(W + " >> .l").get_attribute("aria-expanded") == "false"
                  and p.evaluate("document.querySelector('[data-frontdesk-chat]').shadowRoot.activeElement.className").startswith("l"))
            check("g. no sideways scroll at 390 px, no page errors", p.evaluate("document.scrollingElement.scrollWidth <= innerWidth") and not errs, errs)
            ctx.close()
            # ---- after hours (Sunday 4 pm; Monday is a closed day)
            ctx, p, errs = phone(when=iso(2026, 11, 15, 16))
            p.goto(base + "/harborline/")
            p.locator(W + " >> .l").click()
            p.wait_for_selector(W + " >> .ch")
            first = p.locator(W + " >> .m").first
            check("g. after hours: 'Closed · opens Tue 9 am' + the after-hours message with 'Leave my number'",
                  "Closed · opens Tue 9 am" in p.locator(W + " >> .hs").inner_text() and "open on Tuesday at 9 am" in first.inner_text()
                  and first.locator("[data-a=lead]").count() == 1, first.inner_text())
            snap(p, "chat-05-after-hours.png")
            ctx.close()
            # ---- plumber (emergency) and restaurant presets
            ctx, p, errs = phone(when=iso(2026, 11, 14, 22, 30))
            p.goto(base + "/blueline/")
            p.locator(W + " >> .l").click()
            p.locator(W + " >> .in input").fill("pipe burst in the kitchen, water everywhere!!")
            p.locator(W + " >> .in input").press("Enter")
            last = p.locator(W + " >> .m:not(.u)").last
            check("g. plumber at 10:30 pm: shut-off advice and an 'Emergency line' button to the 24/7 number",
                  "main water valve" in last.inner_text() and last.locator("a[href='tel:+18135550178']").count() == 1, last.inner_text())
            snap(p, "chat-08-plumber-emergency.png")
            ctx.close()
            ctx, p, errs = phone(when=iso(2026, 11, 14, 18, 15))
            p.goto(base + "/casamarina/")
            p.locator(W + " >> .l").click()
            for q in ("table for two tonight?", "do you have vegan options"):
                p.locator(W + " >> .in input").fill(q)
                p.locator(W + " >> .in input").press("Enter")
            texts = p.locator(W + " >> .m:not(.u)").all_inner_texts()
            check("g. restaurant: reservations (Reserve a table button) and dietary questions", "online in about a minute" in texts[-2] and "allergy or diet" in texts[-1]
                  and p.locator(W + " >> .m a[href='https://casamarina.example/reserve']").count() >= 1, texts[-2:])
            snap(p, "chat-09-restaurant.png")
            ctx.close()
            # ---- reduced motion + hostile text
            ctx, p, errs = phone(reduced=True)
            p.goto(base + "/hostile/")
            p.locator(W + " >> .l").click()
            p.locator(W + " >> .in input").fill("do you take walk ins")
            p.locator(W + " >> .in input").press("Enter")
            anim = p.evaluate("getComputedStyle(document.querySelector('[data-frontdesk-chat]').shadowRoot.querySelector('.m')).animationName")
            inj = p.evaluate("""() => { const r = document.querySelector('[data-frontdesk-chat]').shadowRoot; return [r.querySelectorAll('img,script,b').length,
                     !!window.__pwned, r.querySelector('.hn').textContent, r.querySelector('.lg').innerText.includes('<script>window.__pwned=1</script>')]; }""")
            check("g. reduced motion: no animation", anim == "none", anim)
            check("g. hostile text in a client file stays text (no element injected, nothing runs)", inj[0] == 0 and not inj[1] and "<img src=x" in inj[2] and inj[3], inj)
            p.goto(base + "/hostile/review/")
            check("g. ... on the review page too", p.evaluate("document.querySelectorAll('img').length") == 0 and "<img src=x" in p.locator(".top b").inner_text())
            ctx.close()
            # ---- review page: Google is reachable in every state
            g = "https://g.page/r/DEMO-harborline/review"

            def google_visible(p):
                return p.locator(f"a[href='{g}']:visible").count()
            ctx, p, errs = phone()
            p.goto(base + "/harborline/review/")
            check("g. review page, before any star: the Google link is visible, 5 star buttons of 56 px, no sideways scroll",
                  google_visible(p) >= 1 and p.locator(".star").count() == 5 and p.locator(".star").first.bounding_box()["height"] >= 44
                  and p.evaluate("document.scrollingElement.scrollWidth <= innerWidth"))
            snap(p, "review-01-ask.png")
            states = {}
            for r in (1, 2, 3):
                p.goto(base + "/harborline/review/")
                p.click(f".star[data-r='{r}']")
                states[r] = (p.locator("#sorry").is_visible(), p.locator("#sorry a[data-google]").is_visible(), p.locator("#private textarea").is_visible(), google_visible(p),
                             p.locator("input[name=rating]").input_value())
                if r == 2:
                    snap(p, "review-03-two-stars.png", full=True)
            check("g. 1-3 stars: the 'Post a Google review' button AND the private form, both visible (the form is an extra, not a filter)",
                  all(s[:3] == (True, True, True) and s[3] >= 2 and s[4] == str(r) for r, s in states.items()), states)
            p.locator("#private textarea").fill("The wait was long today.")
            p.locator("#private input[name=name]").fill("Pat")
            p.locator("#private button").click()
            p.wait_for_selector("#sent:not([hidden])")
            post = POSTS[-1]
            check("g. the private message posts to the site's Netlify form (form-name, rating, message, empty honeypot) and Google is still offered after",
                  post[0] == "/" and post[2].get("form-name") == "review-feedback" and post[2].get("rating") == "3" and post[2].get("message") == "The wait was long today."
                  and post[2].get("bot-field") == "" and google_visible(p) >= 2, post)
            snap(p, "review-04-sent.png")
            ctx.close()
            for r in (4, 5):
                ctx, p, errs = phone(when=None)                 # clock.install below: fake timers, so the redirect waits for run_for
                p.clock.install(time=datetime.datetime.fromisoformat(iso(2026, 11, 14, 11, 5)))
                p.goto(base + "/harborline/review/")
                p.click(f".star[data-r='{r}']")
                thanks = p.locator("#happy").is_visible() and p.locator("#happy a[data-google]").is_visible()
                if r == 5:
                    snap(p, "review-02-five-stars.png")
                p.clock.run_for(1000)
                p.wait_for_url(g, timeout=8000)
                check(f"g. {r} stars: 'Thank you!' with the Google button, then straight on to the Google review link", thanks and p.url == g, p.url)
                ctx.close()
            ctx, p, errs = phone()
            p.goto(base + "/strict/review/")
            p.click(".star[data-r='5']")
            p.wait_for_timeout(900)
            check("g. strict mode: 5 stars shows the same two choices as 1 star (Google + private form) and stays on the page",
                  p.locator("#sorry").is_visible() and p.locator("#sorry a[data-google]").is_visible() and p.url.startswith(base) and not p.locator("#happy").is_visible(), p.url)
            ctx.close()
            ctx, p, errs = phone()
            p.goto(base + "/harborline/review/")
            p.click("a[data-private]")
            check("g. 'Message the owner privately' opens the form without rating first (anyone, any time)", p.locator("#private textarea").is_visible()
                  and p.locator("input[name=rating]").input_value() == "")
            ctx.close()
            ctx, p, errs = phone(js=False, when=None)
            p.goto(base + "/harborline/review/")
            check("g. with JavaScript off the page still offers both: the Google link and the private form (posts natively to Netlify)",
                  google_visible(p) >= 2 and p.locator("#private textarea").is_visible())
            ctx.close()
            # ---- print: real PDFs at the right sizes
            ctx = br.new_context()
            p = ctx.new_page()
            sizes = {}
            for name in ("card-a6.html", "card-business.html", "cards-letter-10.html"):
                p.goto(base + f"/harborline/kit/print/{name}")
                pdf = p.pdf(prefer_css_page_size=True, print_background=True)
                boxes = re.findall(rb"/MediaBox\s*\[\s*0 0 ([\d.]+) ([\d.]+)\s*\]", pdf)
                sizes[name] = [(round(float(w)), round(float(h))) for w, h in boxes]
            check("g. the cards print at their sizes: A6 1 page (298 x 420 pt), business card front + back (252 x 144 pt), 10-up on US Letter (612 x 792 pt)",
                  sizes["card-a6.html"] == [(298, 420)] and sizes["card-business.html"] == [(252, 144), (252, 144)] and sizes["cards-letter-10.html"] == [(612, 792)], sizes)
            ctx.close()
            if shots:
                ctx, p, errs = phone()
                for url, name in (("/harborline/kit/print/card-a6.html", "card-a6.png"), ("/harborline/kit/print/card-business.html", "card-business.png"),
                                  ("/harborline/kit/print/cards-letter-10.html", "cards-letter-10.png"), ("/harborline/kit/chat-demo-harborline-preview.html", "chat-answers-preview.png")):
                    p.goto(base + url)
                    p.wait_for_timeout(200)
                    snap(p, name)
                ctx.close()
        finally:
            br.close()
            srv.shutdown()


def main():
    try:
        if "--browser-only" not in sys.argv:                       # the static parts need no browser: run them outside the lock
            part_build()
            part_matching()
            part_answers()
            part_network()
            part_qr()
            part_review_static()
        if "--no-browser" not in sys.argv:
            part_browser("--shots" in sys.argv)
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
    n = sum(RES)
    print(f"\nagency upsells: {n}/{len(RES)} " + ("ALL PASS" if n == len(RES) else "FAILED"))
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
