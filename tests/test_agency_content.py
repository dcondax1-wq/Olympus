"""Agency content machine (agency/content/): the social post machine and the monthly client report.

  a. packs: the 8 trade packs (barber, salon, restaurant, plumber/HVAC, landscaper, auto, gym, dentist) are complete, every alias maps,
     3 palettes each with readable text, the fonts are on disk with their OFL licences, every icon and layout exists
  b. plans: every trade x 12 months x 12 / 16 / 20 posts: the post count, dates inside the month (sorted, one a day), times on the
     trade's posting hours, no duplicate captions or headlines, 6+ designs a month, holidays on or before their day, December has
     Christmas, respect days never sell, 6 hashtags or fewer, captions under Instagram's 2,200 characters, no {placeholder} left,
     the same input gives the same month, offers carry a question for the client
  c. honesty: no review quote unless real reviews are given (then the quote is the real text); the client message lists every check
  d. the CSV: the documented columns in order, one row per post, UTF-8 with BOM (Excel), captions survive a round trip
  e. the report without a browser: leads from the fixture CSV (14 in Nov, 9 in Oct, 13 people, 2 spam, 1 bad date, by week), the site
     check against a local server (up, ms) and a closed port (down), the suggestion rules, the email's numbers, no external URL
  f. Chromium (one browser on the machine: run under the lock): a full month for one client (every PNG 1080 x 1080 / 1080 x 1920 and
     not blank, contact sheet + preview), posts for the 7 other trades, the no-Playwright path (the browser's own --screenshot, as
     on a Windows PC with Edge), the report renders with every network request blocked (none tried), one Letter page as a PDF,
     no sideways scroll at 390 px
    flock -w 2400 /tmp/olympus_browser.lock python -X utf8 -m tests.test_agency_content        (--no-browser: parts a-e only)
"""
from __future__ import annotations

import csv
import datetime as dt
import http.server
import io
import json
import os
import re
import shutil
import socket
import sys
import tempfile
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from agency.content import client_report as C  # noqa: E402
from agency.content import designs as D  # noqa: E402
from agency.content import make_posts as M  # noqa: E402
from agency.content import packs as P  # noqa: E402
from agency.content import render as R  # noqa: E402
from agency.content import seasons as S  # noqa: E402
from agency.content import sheet as SH  # noqa: E402

FIX = os.path.join(ROOT, "agency", "content", "fixtures")
CLIENTS = M.load_clients(os.path.join(FIX, "clients_demo.json"))
BY_TRADE = {}
for _c in CLIENTS:
    if _c["status"] == "active":
        BY_TRADE.setdefault(P.trade_of(_c["trade"]), _c)
RES: list[bool] = []
PLACEHOLDER = re.compile(r"\{[a-z_]+\}")


def check(name, cond, detail=""):
    RES.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({str(detail)[:600]})" if detail and not cond else ""), flush=True)
    return bool(cond)


# ============================================================================================================== a. packs
def part_a():
    check("a. 8 trade packs: barber, salon, restaurant, plumber (HVAC), landscaper, auto, gym, dentist", sorted(P.TRADES) ==
          sorted(["barber", "salon", "restaurant", "plumber", "landscaper", "auto", "gym", "dentist"]), P.TRADES)
    need = {"services": 6, "checklists": 1, "offers": 4, "bts": 3, "faq": 3, "engage": 1, "booking": 2, "palettes": 3, "tags": 6, "cta": 2, "icons": 3}
    short = {f"{t}.{k}": len(P.PACKS[t][k]) for t in P.TRADES for k, n in need.items() if len(P.PACKS[t][k]) < n}
    check("a. every pack has enough of each kind (6 services, 4 offers, 3 behind-the-scenes, 3 FAQs, 3 palettes ...)", not short, short)
    tips = {t: len(P.PACKS[t]["tips"]["any"]) + sum(len(P.PACKS[t]["tips"].get(s, [])) for s in ("winter", "spring", "summer", "fall")) for t in P.TRADES}
    check("a. 8 evergreen tips per trade plus tips for every season", all(len(P.PACKS[t]["tips"]["any"]) >= 8 and all(P.PACKS[t]["tips"].get(s)
          for s in ("winter", "spring", "summer", "fall")) for t in P.TRADES), tips)
    check("a. season hooks for all four seasons in every pack", all(all(P.PACKS[t]["season"].get(s) for s in ("winter", "spring", "summer", "fall")) for t in P.TRADES))
    aliases = {"Barber": "barber", "barbershop": "barber", "Hair salon": "salon", "Pizzeria": "restaurant", "Plumbing & HVAC": "plumber",
               "Heating & Cooling": "plumber", "Lawn care": "landscaper", "Auto repair": "auto", "Mechanic": "auto", "CrossFit": "gym",
               "Family Dentistry": "dentist", "Dental practice": "dentist"}
    got = {k: P.trade_of(k) for k in aliases}
    check("a. trade names as typed in the CRM map to a pack (Plumbing & HVAC -> plumber, Pizzeria -> restaurant ...)", got == aliases, got)
    try:
        P.trade_of("Accountant")
        bad = False
    except ValueError:
        bad = True
    check("a. a trade with no pack is refused with the list of packs (never a wrong pack)", bad)
    low = []
    for t in P.TRADES:
        for pal in P.PACKS[t]["palettes"]:
            v = D.palette_vars(pal)
            for a, b, need_r in ((pal["ink"], pal["bg"], 7), (pal["paper_ink"], pal["paper"], 7), (v["acc_d"], pal["bg"], 3), (v["acc_p"], pal["paper"], 3),
                                 (v["on_acc"], pal["accent"], 3.5)):
                if D.contrast(a, b) < need_r:
                    low.append((t, pal["name"], a, b, round(D.contrast(a, b), 2)))
    check("a. every palette reads: body text 7:1, accent text 3:1 on both backgrounds, text on accent 3.5:1", not low, low[:4])
    fonts = sorted({f for k in D.FONTS for f, _, _ in D.FONTS[k][1]})
    missing = [f for f in fonts if not os.path.isfile(os.path.join(D.FONT_DIR, f))]
    lic = os.listdir(os.path.join(D.FONT_DIR, "licenses"))
    check("a. every font file is on disk (no web fonts) and each family has its SIL Open Font License next to it", not missing and len(lic) >= 9
          and all("Open Font License" in open(os.path.join(D.FONT_DIR, "licenses", x), encoding="utf-8").read() for x in lic), (missing, lic))
    icons = {i for t in P.TRADES for i in P.PACKS[t]["icons"]} | {h["icon"] for y in (2026, 2027) for m in range(1, 13) for h in S.holidays(y, m)}
    check("a. every trade and holiday icon is drawn", icons <= set(D.ICONS), sorted(icons - set(D.ICONS)))
    check("a. 11 layouts (bold, split, tip, quote, offer, holiday, date, checklist, qa, frame, minimal)", set(D.LAYOUTS) == set(D.LAYOUT_FN) and len(D.LAYOUTS) == 11)
    check("a. Hanukkah only from the checked table (2026-12-04, 2027-12-24, 2028-12-12), Easter by the computus (2026-04-05, 2027-03-28)",
          [h["date"] for h in S.holidays(2026, 12) if h["key"] == "hanukkah"] == [dt.date(2026, 12, 4)] and
          [h["date"] for h in S.holidays(2027, 12) if h["key"] == "hanukkah"] == [dt.date(2027, 12, 24)] and
          S.easter(2026) == dt.date(2026, 4, 5) and S.easter(2027) == dt.date(2027, 3, 28) and
          not [h for h in S.holidays(2031, 12) if h["key"] == "hanukkah"])
    check("a. US floating days: Thanksgiving 2026-11-26, Memorial Day 2027-05-31, Labor Day 2027-09-06, MLK 2027-01-18",
          S.nth_weekday(2026, 11, 3, 4) == dt.date(2026, 11, 26) and S.nth_weekday(2027, 5, 0, -1) == dt.date(2027, 5, 31)
          and S.nth_weekday(2027, 9, 0, 1) == dt.date(2027, 9, 6) and S.nth_weekday(2027, 1, 0, 3) == dt.date(2027, 1, 18))
    zones = {c: S.zone_of(c) for c in ("Denver, CO", "Tampa, FL", "Austin, TX", "Portland, Oregon", "Springfield")}
    check("a. climate zone from the state (no snow talk in Florida): cold / warm / mild / rainy, unknown -> mild", zones ==
          {"Denver, CO": "cold", "Tampa, FL": "warm", "Austin, TX": "mild", "Portland, Oregon": "rainy", "Springfield": "mild"}, zones)


# ============================================================================================================== b. plans
def part_b():
    dupes, outside, layouts, times, holi, sells, tags, length, ph, counts = [], [], [], [], [], [], [], [], [], []
    for trade, client in BY_TRADE.items():
        pack = P.PACKS[trade]
        for y, m in [(2026, 12)] + [(2027, k) for k in range(1, 12)]:
            for n in (12, 16, 20):
                plan = M.plan_month(client, y, m, n)
                ps = plan["posts"]
                if len(ps) != n:
                    counts.append((trade, y, m, n, len(ps)))
                ds = [dt.date.fromisoformat(p["date"]) for p in ps]
                if any(d.year != y or d.month != m for d in ds) or ds != sorted(ds) or len(set(ds)) != len(ds):
                    outside.append((trade, y, m, n))
                caps = [re.sub(r"\W+", " ", p["caption"].lower()) for p in ps]
                heads = [M.strip_stars(p["headline"]).lower() for p in ps]
                if len(set(caps)) != len(caps) or len(set(heads)) != len(heads):
                    dupes.append((trade, y, m, n, [h for h in heads if heads.count(h) > 1][:2]))
                if len({p["layout"] for p in ps}) < 6:
                    layouts.append((trade, y, m, n, sorted({p["layout"] for p in ps})))
                for p in ps:
                    d = dt.date.fromisoformat(p["date"])
                    ok_t = p["time"] == pack["times"].get(d.weekday()) or (p["kind"] == "holiday" and p["time"] in ("09:00", "12:00")) or p["time"] == "10:00"
                    if not ok_t:
                        times.append((trade, p["date"], p["time"], p["kind"]))
                    if not 1 <= len(p["hashtags"]) <= 6 or any(not re.fullmatch(r"#[A-Za-z0-9]+", t) for t in p["hashtags"]):
                        tags.append((trade, p["n"], p["hashtags"]))
                    if len(M.caption_full(p)) > 2200:
                        length.append((trade, p["n"], len(M.caption_full(p))))
                    txt = " ".join(str(p.get(k) or "") for k in ("caption", "headline", "sub", "label", "alt", "sub_long", "go")) + " ".join(p.get("items") or [])
                    if PLACEHOLDER.search(txt) or "None" in txt.split():
                        ph.append((trade, p["n"], PLACEHOLDER.findall(txt)[:2]))
                hs = {h["key"]: h for h in S.holidays(y, m)}
                for p in ps:
                    if p["kind"] == "holiday":
                        h = hs.get(p["holiday_key"])
                        if not h or not (h["date"] - dt.timedelta(days=6) <= dt.date.fromisoformat(p["date"]) <= h["date"]):
                            holi.append((trade, p["date"], p.get("holiday_key")))
                        if h and h["respect"] and re.search(r"book|call|visit|\$|%|deal|offer|gift card", p["caption"], re.I):
                            sells.append((trade, p["date"], p["holiday"]))
    check("b. the post count is what was asked (12, 16 or 20) for every trade and every month", not counts, counts[:3])
    check("b. every date is inside the month, sorted, one post a day (8 trades x 12 months x 3 sizes)", not outside, outside[:3])
    check("b. no duplicate captions and no duplicate headlines inside a month", not dupes, dupes[:3])
    check("b. 6 or more of the 11 designs every month", not layouts, layouts[:3])
    check("b. posting times are the trade's best times (holiday greetings 9 am, New Year's Eve noon)", not times, times[:4])
    check("b. holiday posts land on the day or up to a few days before it (booking pushes)", not holi, holi[:3])
    check("b. respect days (MLK, Memorial Day, Juneteenth, Veterans Day) never sell", not sells, sells[:3])
    check("b. 6 hashtags or fewer per post, each one word", not tags, tags[:3])
    check("b. every caption + hashtags is under Instagram's 2,200 characters", not length, length[:3])
    check("b. no {placeholder} or 'None' left in any caption, headline, label or alt text", not ph, ph[:3])
    dec = M.plan_month(BY_TRADE["barber"], 2026, 12, 16)
    keys = [p.get("holiday_key") for p in dec["posts"]]
    check("b. December: Christmas and New Year's Eve are in, Christmas on the 25th", "christmas" in keys and "nye" in keys and
          any(p["date"] == "2026-12-25" and p.get("holiday_key") == "christmas" for p in dec["posts"]), keys)
    a1, a2 = M.plan_month(BY_TRADE["salon"], 2027, 3, 16), M.plan_month(BY_TRADE["salon"], 2027, 3, 16)
    strip = lambda pl: [(p["date"], p["caption"], p["layout"], p["hashtags"]) for p in pl["posts"]]  # noqa: E731
    check("b. the same client and month always give the same posts (deterministic)", strip(a1) == strip(a2))
    other = dict(BY_TRADE["barber"], id="another-barber", name="Sharp Lines Barbers")
    b1, b2 = M.plan_month(BY_TRADE["barber"], 2027, 3, 16), M.plan_month(other, 2027, 3, 16)
    check("b. two barbers in one city do not get the same month (order, colours or words differ)", strip(b1) != strip(b2))
    caps_rep, head_rep = [], []
    for trade, client in BY_TRADE.items():
        for n in (12, 20):
            prev = None
            for y, m in [(2026, 12)] + [(2027, k) for k in range(1, 13)]:
                pl = M.plan_month(client, y, m, n)
                heads = {M.strip_stars(p["headline"]).lower(): p for p in pl["posts"] if p["kind"] != "holiday"}
                caps = {p["caption"] for p in pl["posts"]}
                if prev:
                    caps_rep += [(trade, n, f"{y}-{m:02d}", c[:40]) for c in caps & prev[1]]
                    head_rep += [(trade, n, f"{y}-{m:02d}", h) for h, p in heads.items() if h in prev[0]
                                 and not (p["kind"] == "offer" and "gift" in h and m == 12)]
                prev = (heads, caps)
    check("b. next month is new content: no caption repeats from the month before (8 trades x 12 months x 12 and 20 posts)", not caps_rep, caps_rep[:3])
    check("b. ...and no headline repeats either (only the holiday gift-card offer runs in both November and December)", not head_rep, head_rep[:3])
    offers = [p for t, c in BY_TRADE.items() for p in M.plan_month(c, 2026, 12, 20)["posts"] if p["kind"] == "offer"]
    unq = [p["headline"] for p in offers if not p["check"] and re.search(r"gift card|discount|free|deal", p["caption"], re.I)]
    check("b. an offer that assumes a service (gift cards, discounts, free tests) always carries a yes/no question for the client", offers and not unq, unq)
    ph_plan = M.plan_month(BY_TRADE["plumber"], 2027, 1, 16)
    winter = " ".join(p["caption"] for p in M.plan_month(dict(BY_TRADE["plumber"], city="Tampa, FL"), 2027, 1, 16)["posts"]).lower()
    check("b. the climate shows: a Denver plumber in January talks freezes, a Tampa one is never told about snow and ice",
          any(re.search(r"freez|frozen|snow", p["caption"], re.I) for p in ph_plan["posts"]) and "snow and ice" not in winter)
    try:
        M.plan_month(BY_TRADE["barber"], 2027, 1, 25)
        ok = False
    except ValueError:
        ok = True
    check("b. 12-20 posts only (the sellable range)", ok)
    check("b. the package sets the count: Social Basic 12, Social Pro 20, otherwise 16", M.default_posts({"package": "Website + Social Basic"}) == 12
          and M.default_posts({"package": "Social Pro"}) == 20 and M.default_posts({"package": "Website + Social"}) == 16)


# ============================================================================================================= c. honesty
def part_c():
    plan = M.plan_month(BY_TRADE["barber"], 2027, 2, 20)
    rv = [p for p in plan["posts"] if p["kind"] == "review"]
    check("c. no reviews given -> review posts ask for reviews, never quote one (no invented customers)", rv and all(p["quote"] is None for p in rv)
          and not any(re.search(r'"[^"]{12,}"\s*-', p["caption"]) for p in rv), [p["caption"][:80] for p in rv])
    real = [{"text": "Best fade I have had in years. Marco took his time and the shop is spotless.", "who": "Jordan P."}]
    plan2 = M.plan_month(BY_TRADE["barber"], 2027, 2, 20, reviews=real)
    rv2 = [p for p in plan2["posts"] if p["kind"] == "review" and p["quote"]]
    check("c. real reviews given -> the quote is the real text with a first name + initial", rv2 and rv2[0]["quote"]["text"] == real[0]["text"]
          and real[0]["text"] in rv2[0]["caption"] and rv2[0]["quote"]["who"].startswith("Jordan P."), rv2[:1])
    check("c. a full name is cut to first name + initial (privacy)", M.short_name("Maria Lopez") == "Maria L." and M.short_name("Sam") == "Sam")
    with tempfile.TemporaryDirectory() as td:
        f = os.path.join(td, "r.txt")
        with open(f, "w", encoding="utf-8") as fh:
            fh.write("# comment\n\"Great service, fast and friendly.\" | Alex Kim\nLoved it|\n")
        got = M.read_reviews(f, {})
    check("c. the --reviews file: one review a line, text | name, comments skipped", got == [{"text": "Great service, fast and friendly.", "who": "Alex K."},
                                                                                           {"text": "Loved it", "who": "a happy customer"}], got)
    dec = M.plan_month(BY_TRADE["restaurant"], 2026, 12, 16)
    msg = M.client_message(dec)
    check("c. the client message asks every yes/no question of the month, lists the photo ideas and asks for a YES", all(q in msg for q in dec["checks"])
          and "YES" in msg and (not any(p["photo_idea"] for p in dec["posts"]) or "real photo" in msg), msg[:300])
    bts = [p for p in dec["posts"] if p["kind"] in ("bts", "team")]
    check("c. behind-the-scenes posts carry a photo idea (a real photo beats a graphic) and are not mistaken for questions",
          all(p["photo_idea"].startswith("Better with a real photo") and not p["check"] for p in bts))


# ================================================================================================================ d. CSV
def part_d():
    plan = M.plan_month(BY_TRADE["dentist"], 2027, 4, 16)
    with tempfile.TemporaryDirectory() as td:
        f = os.path.join(td, "posts.csv")
        M.write_csv(plan, f)
        raw = open(f, "rb").read()
        rows = list(csv.reader(io.StringIO(raw.decode("utf-8-sig"))))
        M.write_captions(plan, os.path.join(td, "captions.txt"))
        cap = open(os.path.join(td, "captions.txt"), encoding="utf-8").read()
    check("d. the CSV columns, in order: " + ", ".join(M.CSV_COLUMNS), rows[0] == M.CSV_COLUMNS, rows[0])
    check("d. one row per post, UTF-8 with a BOM so Excel shows emoji and accents", len(rows) == 17 and raw[:3] == b"\xef\xbb\xbf")
    body = rows[1:]
    check("d. dates, times and images match the plan; captions survive the round trip (line breaks, quotes, emoji)",
          [r[1] for r in body] == [p["date"] for p in plan["posts"]] and [r[2] for r in body] == [p["time"] for p in plan["posts"]]
          and [r[7] for r in body] == [p["caption"] for p in plan["posts"]] and all(r[10].endswith("_square.png") and r[11].endswith("_story.png") for r in body))
    check("d. captions.txt: every caption with its date, time and image file, ready to copy from a phone", all(p["caption"] in cap and p["square"] in cap for p in plan["posts"]))
    with tempfile.TemporaryDirectory() as td:
        rc = M.main([os.path.join(FIX, "clients_demo.json"), "--id", "nonna-rosa", "--month", "2027-02", "--no-images", "--out", td, "--quiet"])
        files = sorted(os.listdir(td))
        sheet = open(os.path.join(td, "contact_sheet.html"), encoding="utf-8").read()
        plan = json.load(open(os.path.join(td, "posts.json"), encoding="utf-8"))
    check("d. the command line, no images: exit 0, the month folder (posts.csv, captions.txt, contact_sheet.html, client_message.txt, posts.json, "
          "HOW_TO_POST.txt) and a sheet that shows each headline instead of broken images", rc == 0 and
          {"posts.csv", "captions.txt", "contact_sheet.html", "client_message.txt", "posts.json", "HOW_TO_POST.txt"} <= set(files)
          and "<img" not in sheet and sheet.count('class="ph"') == len(plan["posts"]) and plan["month"] == "2027-02", files)
    try:
        M.main([os.path.join(FIX, "clients_demo.json"), "--month", "2027-02", "--no-images", "--quiet"])
        refused = False
    except SystemExit as e:
        refused = "--id" in str(e)
    check("d. a file with several clients and no --id / --all is refused with the list of ids (never a guess)", refused)
    paying = M.choose_clients(CLIENTS, None, True)
    check("d. --all takes the paying clients only (the lead in the demo file is skipped)", len(paying) == 8 and all(c["status"] == "active" for c in paying))
    # the two double-click helpers for the owner's PC (the same static rules as the repo's Windows scripts; cmd.exe is not run here)
    bad = {}
    for name in ("MAKE_POSTS.bat", "CLIENT_REPORT.bat"):
        raw = open(os.path.join(ROOT, "agency", "content", name), "rb").read()
        probs = []
        if b"\n" in raw.replace(b"\r\n", b"") or not raw.endswith(b"\r\n"):
            probs.append("not CRLF")
        try:
            txt = raw.decode("ascii")
        except UnicodeDecodeError:
            probs.append("non-ASCII")
            txt = raw.decode("utf-8", "replace")
        lines = txt.split("\r\n")
        labels = {ln.strip()[1:].split()[0].lower() for ln in lines if ln.strip().startswith(":") and not ln.strip().startswith("::")} | {"eof"}
        for ln in lines:
            s = ln.strip()
            if s.lower().startswith("rem"):
                continue
            probs += [f"no :{m}" for m in re.findall(r"(?i)\bgoto\s+:([A-Za-z0-9_]+)", s) if m.lower() not in labels]
            if s.count("(") != s.count(")") and not s.lower().startswith("echo"):
                probs.append(f"parentheses: {s[:40]}")
            for m in re.findall(r"agency\\content\\([A-Za-z_]+\.py)", s):
                if not os.path.isfile(os.path.join(ROOT, "agency", "content", m)):
                    probs.append(f"missing {m}")
        if "cd /d \"%~dp0..\\..\"" not in txt or "where python" not in txt:
            probs.append("does not start from the repo root / check python")
        if probs:
            bad[name] = probs
    check("d. MAKE_POSTS.bat / CLIENT_REPORT.bat: CRLF, ASCII, every goto has its label, balanced, run from the repo root, the scripts they call exist", not bad, bad)


# ============================================================================================================ e. report
class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):  # noqa: N802
        body = b"<!doctype html><title>Demo Barber</title><h1>ok</h1>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _serve():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Quiet)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}/"


def _closed_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def report_fixture(site: dict):
    client = BY_TRADE["barber"]
    leads = C.read_leads(os.path.join(FIX, "leads_demo.csv"), 2026, 11)
    this_plan = M.plan_month(client, 2026, 11, 16)
    next_plan = M.plan_month(client, 2026, 12, 16)
    return C.build_report(client, 2026, 11, leads, site, 47, 41, 4.9, ["Added the holiday hours banner to the site"], ["New gallery photos"],
                          this_plan, next_plan, {"name": "Main Street Web Co.", "email": "hello@mainstreet.example", "phone": "(512) 555-0100", "site": ""})


def part_e():
    lead = C.read_leads(os.path.join(FIX, "leads_demo.csv"), 2026, 11)
    check("e. leads from the form export: 14 in November (a double-click counted once), 9 in October, 13 different people",
          lead["ok"] and lead["month"] == 14 and lead["prev"] == 9 and lead["people"] == 13, lead)
    check("e. spam rows (2) and a row with no readable date (1) are left out; the date column is found by its name",
          lead["spam"] == 2 and lead["skipped"] == 1 and lead["column"] == "created_at", lead)
    check("e. leads by week: 3, 4, 2, 4, 1", lead["weeks"] == [3, 4, 2, 4, 1], lead["weeks"])
    with tempfile.TemporaryDirectory() as td:
        g = os.path.join(td, "google_forms.csv")
        with open(g, "w", encoding="utf-8") as fh:
            fh.write("Timestamp,Your name,Phone number\n11/3/2026 14:22:05,Ann,512-555-0130\n11/28/2026 9:01:00,Bo,512-555-0131\n10/30/2026 8:00:00,Cy,512-555-0132\n")
        gl = C.read_leads(g, 2026, 11)
        s2 = os.path.join(td, "semi.csv")
        with open(s2, "w", encoding="utf-8") as fh:
            fh.write("Submitted at;Email;Status\n2026-11-05 10:00;a@x.example;new\n2026-11-06 10:00;b@x.example;spam\n")
        sl = C.read_leads(s2, 2026, 11)
    check("e. other form tools: Google Forms (Timestamp, US dates) and a semicolon export with a status=spam column",
          gl["month"] == 2 and gl["prev"] == 1 and sl["month"] == 1 and sl["spam"] == 1, (gl, sl))
    srv, url = _serve()
    try:
        up = C.check_site(url)
    finally:
        srv.shutdown()
    down = C.check_site(f"http://127.0.0.1:{_closed_port()}/", timeout=3)
    check("e. site check: a live site is up with a status, a speed and its title", up["checked"] and up["up"] and up["status"] == 200
          and isinstance(up["ms"], int) and up["title"] == "Demo Barber", up)
    check("e. site check: a dead site is down with a plain reason", down["checked"] and down["up"] is False and down["reason"], down)
    check("e. no website on file -> 'not checked', not a fake 'up'", C.check_site("")["checked"] is False)
    rep = report_fixture(up)
    h = rep["html"]
    for want in ("Fade &amp; Co. Barbershop", "November 2026", ">14<", "47", "+6 this month", "4.9", "Website leads by week", "Next month: December",
                 "Added the holiday hours banner", "New gallery photos", "Main Street Web Co."):
        if want not in h:
            check(f"e. the report shows {want!r}", False)
            break
    else:
        check("e. the report shows the client, month, 14 leads, 47 reviews (+6, 4.9), the week chart, next month and the owner's own lines", True)
    urls = [u for u in re.findall(r"(?:src|href)\s*=\s*[\"']?(https?://[^\"' >]+)", h)] + re.findall(r"url\((?:\"|')?https?://", h)
    check("e. the report HTML loads nothing from the internet (fonts inside, chart is inline SVG)", not urls and "@import" not in h, urls[:3])
    em = rep["email"]
    check("e. the email: subject line, the leads (+5 vs October), reviews, posts, next month and the one suggestion", em.startswith("Subject: Your November 2026 report")
          and "Website leads: 14 (+5 vs October)" in em and "Google reviews: 47 (+6 this month), rating 4.9" in em and "16 posts + 16 stories" in em
          and "Coming up in December" in em and "One idea for December" in em, em)
    nos = C.suggest({"package": "Website only"}, {"ok": True, "month": 3}, 1)
    rb = C.suggest({"package": "Website + Social"}, {"ok": True, "month": 3}, 1)
    ch = C.suggest({"package": "Website + Social"}, {"ok": True, "month": 12}, 7)
    pro = C.suggest({"package": "Website + Social Basic + Review + Chat"}, {"ok": True, "month": 2}, 9)
    none = C.suggest({"package": "Website + Social Pro + Review + Chat"}, {"ok": True, "month": 2}, 9)
    check("e. one suggestion from the numbers: no social -> social posts; few new reviews -> review booster; many leads -> chat; basic -> pro; nothing left -> none",
          nos["id"] == "social_basic" and rb["id"] == "review_booster" and ch["id"] == "chat_widget" and pro["id"] == "social_pro" and none is None,
          [x and x["id"] for x in (nos, rb, ch, pro, none)])
    off = report_fixture({"checked": False, "up": None, "reason": "check skipped (offline)", "at": ""})
    check("e. offline: the website box says 'check skipped', never a made-up result", "check skipped (offline)" in off["html"] and "Website: up" not in off["email"])


# ============================================================================================================ f. browser
def _not_blank(path: str) -> bool:
    try:
        from PIL import Image
        im = Image.open(path).convert("RGB").resize((64, 64))
        return len(set(im.getdata())) > 24
    except ImportError:
        return os.path.getsize(path) > 15000


def _pdf_pages(path: str) -> int:
    data = open(path, "rb").read()
    return len(re.findall(rb"/Type\s*/Page(?![s])", data))


def part_f():
    tmp = tempfile.mkdtemp(prefix="agency_test_")
    try:
        client = BY_TRADE["barber"]
        plan = M.plan_month(client, 2026, 12, 12)
        out = os.path.join(tmp, "fade-co", "2026-12")
        with R.Renderer() as r:
            check("f. a browser was found (Playwright + Chromium here)", r.ok, r.kind)
            if not r.ok:
                return
            made = M.write_outputs(plan, out, render=True, renderer=r, quiet=True)
            sizes, blank = [], []
            for p in plan["posts"]:
                for key, want in (("square", (1080, 1080)), ("story", (1080, 1920))):
                    f = os.path.join(out, p[key])
                    if not os.path.isfile(f) or R.png_size(f) != want:
                        sizes.append((p[key], os.path.isfile(f) and R.png_size(f)))
                    elif not _not_blank(f):
                        blank.append(p[key])
            check("f. a full month: 12 posts -> 24 images, squares 1080 x 1080 and stories 1080 x 1920", made["images"] == 24 and not sizes, sizes[:3])
            check("f. no blank image (each one has real type and colour on it)", not blank, blank[:3])
            files = sorted(os.listdir(out))
            check("f. the month folder: posts/, posts.csv, captions.txt, contact_sheet.html + .png, client_message.txt, posts.json, HOW_TO_POST.txt",
                  {"posts", "posts.csv", "captions.txt", "contact_sheet.html", "contact_sheet.png", "client_message.txt", "posts.json", "HOW_TO_POST.txt"} <= set(files), files)
            sheet = open(os.path.join(out, "contact_sheet.html"), encoding="utf-8").read()
            refs = set(re.findall(r'src="(posts/[^"]+)"', sheet))
            want = {p["square"] for p in plan["posts"]} | {p["story"] for p in plan["posts"]}
            check("f. the contact sheet shows every square and story image, and every file it points to exists", refs == want
                  and all(os.path.isfile(os.path.join(out, x)) for x in refs), sorted(want - refs)[:3])
            check("f. the contact sheet loads nothing from the internet", not re.findall(r"(?:src|href)=\"https?://", sheet))
            pw, ph = R.png_size(os.path.join(out, "contact_sheet.png"))
            check("f. contact_sheet.png (the client's preview) is 1600 px wide and holds every post", pw == 1600 and ph >= SH.preview_height(plan) - 200, (pw, ph))

            other, bad = [], []
            for t, c in BY_TRADE.items():
                if t == "barber":
                    continue
                pl = M.plan_month(c, 2027, 3, 16)
                br = M.brand_for(c, t)
                lays = []
                for p in pl["posts"]:
                    if p["layout"] not in lays and len(lays) < 2:
                        lays.append(p["layout"])
                        f = os.path.join(tmp, f"{t}_{p['layout']}_square.png")
                        r.png(D.page(p, br, "square"), f, 1080, 1080)
                        other.append(f)
                        if R.png_size(f) != (1080, 1080) or not _not_blank(f):
                            bad.append(f)
                f = os.path.join(tmp, f"{t}_story.png")
                r.png(D.page(pl["posts"][0], br, "story"), f, 1080, 1920)
                if R.png_size(f) != (1080, 1920) or not _not_blank(f):
                    bad.append(f)
            check("f. the 7 other trades draw too (their own fonts, colours and icons): 2 squares + 1 story each", len(other) == 14 and not bad, bad)

            # the report: offline, one page, phone width
            rep = report_fixture({"checked": True, "up": True, "status": 200, "ms": 412, "https": True, "url": "https://fadeandco.example", "at": "2026-12-01T09:00"})
            rp = os.path.join(tmp, "report.html")
            with open(rp, "w", encoding="utf-8") as fh:
                fh.write(rep["html"])
            ctx = r._br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1)
            seen = []
            ctx.route("**/*", lambda route: (seen.append(route.request.url), route.abort() if route.request.url.startswith(("http:", "https:")) else route.continue_()))
            pg = ctx.new_page()
            errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.goto("file://" + rp, wait_until="load")
            pg.wait_for_function("document.documentElement.getAttribute('data-ready') === '1'", timeout=20000)
            web = [u for u in seen if u.startswith(("http:", "https:"))]
            fonts_ok = pg.evaluate("document.fonts.check('32px \"DM Serif Display\"') && document.fonts.check('13px Manrope')")
            wide = pg.evaluate("document.documentElement.scrollWidth")
            check("f. the report renders offline: no request leaves the machine, its own fonts load, no script error", not web and fonts_ok and not errs, (web[:3], fonts_ok, errs[:2]))
            check("f. the report at 390 px: no sideways scroll", wide <= 390, wide)
            pg.goto("file://" + os.path.join(out, "contact_sheet.html"), wait_until="load")
            pg.wait_for_function("document.documentElement.getAttribute('data-ready') === '1'", timeout=20000)
            sw = pg.evaluate("document.documentElement.scrollWidth")
            loaded = pg.evaluate("Array.from(document.images).filter(i => i.complete && i.naturalWidth > 0).length")
            tap = pg.evaluate("Array.from(document.querySelectorAll('button.copy')).every(b => b.getBoundingClientRect().height >= 44)")
            check("f. the contact sheet at 390 px: no sideways scroll, all 24 images load, Copy buttons are 44 px tall", sw <= 390 and loaded == 24 and tap, (sw, loaded, tap))
            ctx.close()
            pdf = os.path.join(tmp, "report.pdf")
            r.pdf(rep["html"], pdf)
            check("f. the report prints on ONE Letter page (PDF)", os.path.isfile(pdf) and _pdf_pages(pdf) == 1, _pdf_pages(pdf) if os.path.isfile(pdf) else "no pdf")

        # the PC path: no Playwright, the browser's own headless screenshot (what Edge does on Windows)
        with R.Renderer(prefer="cli") as rc:
            if rc.kind != "cli":
                check("f. the no-Playwright path finds a browser binary", False, rc.kind)
            else:
                p = plan["posts"][0]
                br = M.brand_for(client, "barber")
                f1, f2 = os.path.join(tmp, "cli_square.png"), os.path.join(tmp, "cli_story.png")
                rc.png(D.page(p, br, "square"), f1, 1080, 1080)
                rc.png(D.page(p, br, "story"), f2, 1080, 1920)
                check("f. without Playwright (the browser's own --screenshot, as Edge on a Windows PC): same sizes, not blank",
                      R.png_size(f1) == (1080, 1080) and R.png_size(f2) == (1080, 1920) and _not_blank(f1) and _not_blank(f2))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    part_a()
    part_b()
    part_c()
    part_d()
    part_e()
    if "--no-browser" not in sys.argv:
        part_f()
    ok = sum(RES)
    print(f"\n{ok}/{len(RES)} passed", flush=True)
    return 0 if ok == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
