"""MONEY MACHINES (money_machines/, team F1 2026-11-14). No network at all: every socket connect and urlopen in this process raises. Checks:
  a. brand kit: every SVG parses, has a viewBox, no script / foreignObject / outside links / live <text> (letters are paths), the name is
     escaped, colours are hex; the palettes and a client-colour palette pass contrast; same input = same bytes; brand.json + guide complete
  b. gig pack: 8 gigs inside Fiverr's limits (title <= 80, 5 tags <= 20 chars, description <= 1,200, FAQ sizes), 3 rising prices, the two
     smaller packages under an hour, a tool + Upwork template per gig, AI line, never-build list; docs/GIG_PACK.md is not stale; the order
     file has B1's agency-leads shape; the GBP checklist and the website report are written without the network
  c. content plan: 30 consecutive dates per account, unique captions <= 2,200 chars, <= 5 hashtags, alt text, the trading account carries
     the risk line and no performance claim, the specials land on their days, the committed plans equal a fresh build; one image render
     (skipped without Chromium)
  d. poster: dry run (with or without a token) never touches the network; --live without a token refuses; a token file inside the repo is
     refused; the 24 h cap and the ledger stop double posts; live calls go through one function (faked here) in the documented order
  e. product: the eval tracker files are present (xlsx with formulas, offline web app, how-to PDF, licence, listing, covers, price),
     the web app has no network call, the listing makes no performance promise, the math matches by hand; the catalogue lists 4 more
    python -X utf8 -m tests.test_money_machines
"""
from __future__ import annotations

import json
import os
import re
import shutil
import socket
import sys
import tempfile
import urllib.request
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

RES = []
NET_TRIES = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:600]}"), flush=True)


def _no_net(*a, **k):
    NET_TRIES.append(a[:1])
    raise OSError("network disabled in tests.test_money_machines")


socket.socket.connect = _no_net               # every TCP connect in this process fails loudly and is counted
socket.create_connection = _no_net
urllib.request.urlopen = _no_net

from money_machines import brand_kit as BK  # noqa: E402
from money_machines import gig_pack as GP  # noqa: E402

SVG = "{http://www.w3.org/2000/svg}"


# ------------------------------------------------------------------------------------------------ a. brand kit
def svg_problems(path):
    raw = open(path, encoding="utf-8").read()
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as e:
        return [f"parse: {e}"]
    p = []
    if root.tag != SVG + "svg":
        p.append("root is not svg")
    vb = (root.get("viewBox") or "").split()
    if len(vb) != 4 or not all(re.fullmatch(r"-?\d+(\.\d+)?", v) for v in vb):
        p.append(f"viewBox {vb}")
    elif root.get("width") != vb[2] or root.get("height") != vb[3]:
        p.append("width/height differ from the viewBox")
    tags = {el.tag.replace(SVG, "") for el in root.iter()}
    for bad in ("script", "foreignObject", "image", "text", "use", "a"):
        if bad in tags:
            p.append(f"has <{bad}>")
    if re.search(r"(?:href|src)\s*=|https?:|url\(", raw.replace('xmlns="http://www.w3.org/2000/svg"', "")):
        p.append("outside reference")
    for el in root.iter():
        for attr in ("fill", "stroke"):
            v = el.get(attr)
            if v and v != "none" and not re.fullmatch(r"#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?", v):
                p.append(f"{attr}={v}")
    if root.find(SVG + "title") is None:
        p.append("no <title>")
    return p


def part_a():
    tmp = tempfile.mkdtemp(prefix="mm_bk_")
    try:
        name = "Bloom & Stem <Co>"
        r = BK.kit(name, os.path.join(tmp, "k1"), tagline="Flowers for \"every\" day", industry="florist")
        svgs = [p for p in r["files"] if p.endswith(".svg")]
        need = {"logo_primary", "logo_stacked", "logo_mark", "logo_wordmark", "logo_mono_dark", "logo_mono_light", "favicon", "social_avatar",
                "social_banner", "business_card_front", "business_card_back", "palette", "concepts", "concept_1", "concept_2", "concept_3"}
        have = {os.path.basename(p)[:-4] for p in svgs}
        check("a. the kit writes the 16 SVG pieces + brand.json + brand_guide.html", need <= have and os.path.exists(os.path.join(tmp, "k1", "brand.json"))
              and os.path.exists(os.path.join(tmp, "k1", "brand_guide.html")), sorted(need - have))
        probs = {os.path.basename(p): svg_problems(p) for p in svgs}
        probs = {k: v for k, v in probs.items() if v}
        check("a. every SVG is valid: svg root, numeric viewBox = width/height, <title>, hex colours only", not probs, probs)
        check("a. no script, foreignObject, image, live <text> or outside link in any SVG (letters are vector paths)", not probs, probs)
        title = ET.parse(os.path.join(tmp, "k1", "logo_primary.svg")).getroot().find(SVG + "title").text
        check("a. a name with & and < is escaped and reads back exactly", title == f"{name} logo", title)
        r2 = BK.kit(name, os.path.join(tmp, "k2"), tagline="Flowers for \"every\" day", industry="florist")
        same = all(open(a, "rb").read() == open(a.replace(os.sep + "k1" + os.sep, os.sep + "k2" + os.sep), "rb").read() for a in r["files"])
        check("a. deterministic: the same input writes the same bytes", same and len(r2["files"]) == len(r["files"]))
        bad = {k: (BK.contrast(v[3], v[4]), BK.contrast(v[4], v[0])) for k, v in BK.PALETTES.items()
               if BK.contrast(v[3], v[4]) < 7 or BK.contrast(v[4], v[0]) < 4.5}
        check("a. every palette: text on paper >= 7:1 and paper on the brand colour >= 4.5:1", not bad, bad)
        cp = [BK.custom_palette(c) for c in ("#ffcc00", "#3fa9f5", "#e91e63", "#222222", "#7fff00")]
        check("a. a palette built from a client's colour is readable (paper on primary >= 4.5:1, ink on paper >= 7:1)",
              all(BK.contrast(p[4], p[0]) >= 4.5 and BK.contrast(p[3], p[4]) >= 7 for p in cp), cp)
        check("a. every industry maps to a real mark and palette", all((m == "monogram" or m in BK.MARKS) and p in BK.PALETTES and f in BK.FONT_INFO
                                                                      for m, p, f in BK.INDUSTRIES.values()))
        bj = json.load(open(os.path.join(tmp, "k1", "brand.json"), encoding="utf-8"))
        check("a. brand.json has the colours, fonts, contrast and rules", {"colors", "fonts", "contrast", "rules", "logo"} <= set(bj)
              and set(bj["colors"]) == {"primary", "secondary", "accent", "ink", "paper"} and bj["logo"]["letters"].startswith("vector"), bj.keys())
        guide = open(os.path.join(tmp, "k1", "brand_guide.html"), encoding="utf-8").read()
        check("a. the brand guide shows every logo inline and has no script or outside link", guide.count("<svg") >= 11
              and "<script" not in guide and "http" not in guide.replace("http://www.w3.org/2000/svg", ""))
        w1 = BK.measure("AV", "sans", 100)
        w0 = (BK.font("sans")["glyphs"]["A"][0] + BK.font("sans")["glyphs"]["V"][0]) * 100 / BK.font("sans")["upm"]
        check("a. kerning is applied (AV narrower than A + V)", w1 < w0, (w1, w0))
        lic = open(os.path.join(ROOT, "money_machines", "fonts", "FONTS_LICENSE.txt"), encoding="utf-8").read()
        check("a. the glyph outlines carry the SIL Open Font License and both copyrights", "SIL OPEN FONT LICENSE" in lic and "Inter Project Authors" in lic
              and "Caladea Project Authors" in lic)
        rc = BK.main(["--name", "X", "--out", os.path.join(tmp, "k3"), "--palette", "nope"])
        check("a. a wrong palette name is a clear error (exit 2), not a crash", rc == 2)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------------------------------------ b. gig pack
def part_b():
    pack = GP.load()
    probs = GP.validate(pack)
    check("b. the gig pack passes its own validator (Fiverr limits + our rules)", not probs, probs)
    gigs = pack["gigs"]
    check("b. 8 gigs, the 8 asked for", [g["id"] for g in gigs] == ["local-website", "logo-brand-kit", "gbp-setup", "review-booster", "speed-seo-report",
                                                                     "landing-page", "social-month", "chat-widget"], [g["id"] for g in gigs])
    check("b. titles start 'I will' and fit 80 chars; 5 tags of <= 20 chars; descriptions <= 1,200",
          all(g["title"].startswith("I will ") and len(g["title"]) <= 80 and len(g["tags"]) == 5 and max(map(len, g["tags"])) <= 20
              and len(g["description"]) <= 1200 for g in gigs))
    check("b. 3 packages each with rising prices; the two smaller ones take under an hour of the owner's time",
          all(len(g["packages"]) == 3 and g["packages"][0]["price"] < g["packages"][1]["price"] < g["packages"][2]["price"]
              and max(k["minutes"] for k in g["packages"][:2]) <= 60 for g in gigs))
    check("b. every gig: FAQ (>= 4), requirements, delivery checklist, a tool with steps, an Upwork template",
          all(len(g["faq"]) >= 4 and g["requirements"] and g["delivery_checklist"] and g["tool"]["steps"] and g["id"] in pack["upwork"]["templates"] for g in gigs))
    allt = json.dumps(pack).lower()
    check("b. the never-build list names auto-bidding, scraping, mass messages, fake reviews and second accounts",
          all(w in " ".join(pack["never_build"]).lower() for w in ("auto-bidding", "scraper", "mass-message", "fake reviews", "second account")))
    check("b. nothing promises rankings or results (only 'no one can promise')",
          not re.search(r"guaranteed (ranking|results|sales)|we guarantee|#1 on google|first page guaranteed", allt))
    check("b. every proposal template carries the AI disclosure and is sent by hand (no auto-send words)",
          all("ai" in t.lower() for t in pack["upwork"]["templates"].values()) and "send by hand" in pack["upwork"]["rules"].lower())
    doc = open(os.path.join(ROOT, "docs", "GIG_PACK.md"), encoding="utf-8").read()
    check("b. docs/GIG_PACK.md is up to date with gig_pack.json (python -m money_machines.gig_pack --md)", doc == GP.render_md(pack))
    lead = GP.make_lead("Rivera Plumbing", "plumber", "Fort Collins, CO", "(970) 555-0142", "a@b.co")
    L = lead["leads"][0]
    b1_keys = {"id", "name", "slug", "category", "category_label", "template", "address", "phone", "phone_e164", "email", "website",
               "opening_hours", "hours", "issues", "reasons", "why", "score", "tier", "site_status"}
    check("b. the order file has B1's agency-leads v1 shape (kind, leads[0] keys, address block, e164 phone)",
          lead["kind"] == "agency-leads" and lead["v"] == 1 and b1_keys <= set(L) and L["phone_e164"] == "+19705550142"
          and L["address"]["city"] == "Fort Collins" and L["address"]["state"] == "CO" and L["slug"] == "rivera-plumbing", L)
    tmp = tempfile.mkdtemp(prefix="mm_gp_")
    try:
        files = GP.checklist_files(pack, "gbp-setup", "Rivera Plumbing", tmp)
        md = open(files[0], encoding="utf-8").read()
        check("b. the GBP checklist deliverable is written (md + html) with all 18 lines and the honest-rules line",
              len(files) == 2 and md.count("\n| ") >= 18 and "No one can promise a ranking" in md)
        rc = GP.main(["order", "--gig", "review-booster", "--name", "Rivera Plumbing", "--category", "plumber", "--city", "Fort Collins, CO",
                      "--phone", "(970) 555-0142", "--review-url", "https://g.page/r/example/review", "--colors", "#14213D,#D4A24C,nothex", "--price", "60",
                      "--out", os.path.join(tmp, "ord")])
        cl = json.load(open(os.path.join(tmp, "ord", "client.json"), encoding="utf-8"))
        shared = {"id", "name", "trade", "city", "phone", "email", "site_url", "demo_url", "status", "package", "setup_usd", "monthly_usd", "notes"}
        check("b. order writes lead.json (B1) and client.json in the shared client record B4/B5 read (+ review_url, valid brand colours only)",
              rc == 0 and os.path.exists(os.path.join(tmp, "ord", "lead.json")) and shared <= set(cl) and cl["id"] == "rivera-plumbing"
              and cl["review_url"].endswith("/review") and cl["brand_colors"] == ["#14213D", "#D4A24C"] and cl["setup_usd"] == 60.0, cl)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    st = GP.tool_status()
    by = {g: (m, ok) for g, m, ok, s in st}
    check("b. --check knows the tool of every gig: ours are ready (brand kit, GBP checklist); the agency tools are named by their real paths",
          len(st) == 8 and by["logo-brand-kit"][1] and by["gbp-setup"][1] and by["speed-seo-report"][0] == "agency/storefront/grade.py"
          and by["social-month"][0] == "agency/content/make_posts.py" and by["review-booster"][0] == "agency/upsells/make_review.py"
          and by["chat-widget"][0] == "agency/upsells/make_chat.py" and by["local-website"][0] == "agency.build_site", st)
    check("b. no website-report code of our own (team B3's grader does that job)", not hasattr(GP, "run_report"))


# ------------------------------------------------------------------------------------------------ c. content plan
def jpeg_size(path):
    """(width, height) from the JPEG's SOF marker (no Pillow needed)."""
    with open(path, "rb") as fh:
        b = fh.read()
    i = 2
    while i < len(b) - 9:
        if b[i] != 0xFF:
            i += 1
            continue
        m = b[i + 1]
        if m in (0xC0, 0xC1, 0xC2):
            return int.from_bytes(b[i + 7:i + 9], "big"), int.from_bytes(b[i + 5:i + 7], "big")
        i += 2 + int.from_bytes(b[i + 2:i + 4], "big")
    return None


def part_c():
    import datetime as dt
    from money_machines import content_plan as CP
    from money_machines import content_topics as T
    start = dt.date.fromisoformat(CP.FIXED_START)
    plans = {acc: CP.build_plan(acc, start) for acc in ("local_growth", "eval_journal")}
    for acc, plan in plans.items():
        probs = CP.validate(plan)
        check(f"c. {acc}: the 30-day plan is valid (dates, captions, hashtags, claims)", not probs, probs)
        posts = plan["posts"]
        dates = [p["date"] for p in posts]
        check(f"c. {acc}: 30 consecutive dates from {CP.FIXED_START}, days 1-30",
              len(posts) == 30 and dates == [(start + dt.timedelta(days=i)).isoformat() for i in range(30)] and [p["day"] for p in posts] == list(range(1, 31)))
        check(f"c. {acc}: captions unique, <= 2,200 chars, <= 5 hashtags each, alt text on every post",
              len({p["caption"] for p in posts}) == 30 and max(len(p["caption"]) for p in posts) <= 2200
              and all(len(p["hashtags"]) <= 5 and p["caption"].count("#") <= 5 and p["alt_text"] for p in posts))
        jp, mp = CP.plan_paths(acc)
        committed = json.load(open(jp, encoding="utf-8"))
        check(f"c. {acc}: the committed plan equals a fresh build (python -m money_machines.content_plan --all)",
              committed == json.loads(json.dumps(plan)) and open(mp, encoding="utf-8").read() == CP.plan_md(plan))
    ev = plans["eval_journal"]["posts"]
    risk = T.ACCOUNTS["eval_journal"]["risk_line"]
    check("c. eval journal: every caption ends with the risk line; dollar amounts only in 'Example only' posts",
          all(p["caption"].endswith(risk) for p in ev) and all("example only" in p["caption"].lower() for p in ev if "$" in p["caption"]))
    lg = {p["date"]: p for p in plans["local_growth"]["posts"]}
    check("c. specials land on their days: Thanksgiving 11-26, Black Friday 11-27, Small Business Saturday 11-28, holiday hours 12-01",
          lg["2026-11-26"]["special"] == "thanksgiving" and lg["2026-11-27"]["special"] == "black_friday"
          and lg["2026-11-28"]["special"] == "small_business_saturday" and lg["2026-12-01"]["special"] == "holiday_hours")
    check("c. the eval journal's holiday-week post lands on the Monday of Thanksgiving week (11-23)",
          {p["date"]: p for p in ev}["2026-11-23"]["special"] == "thanksgiving_week")
    spring = CP.build_plan("local_growth", dt.date(2027, 3, 1))
    check("c. a month with no specials still fills 30 valid posts from the regular topics", not CP.validate(spring) and len(spring["posts"]) == 30)
    bad = json.loads(json.dumps(plans["eval_journal"]))
    bad["posts"][0]["caption"] = bad["posts"][0]["caption"].replace("Most failed", "I made $500 a day. Most failed")
    bad["posts"][1]["caption"] = bad["posts"][1]["caption"].replace(risk, "")
    bad["posts"][2]["hashtags"] = ["#a", "#b", "#c", "#d", "#e", "#f"]
    bad["posts"][3]["caption"] = "Use my affiliate link for 20% off. " + bad["posts"][3]["caption"][30:]
    msg = " | ".join(CP.validate(bad))
    check("c. the validator catches a profit claim, a missing risk line, 6 hashtags and an undisclosed affiliate link",
          "day 1: claim" in msg and "day 2: the risk line" in msg and "day 3: hashtags" in msg and "day 4: a paid link" in msg, msg)
    try:
        import playwright  # noqa: F401
        have = bool(CP.chromium_path()) or os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    except Exception:
        have = False
    if not have:
        print("[SKIP] c. image render: no playwright / Chromium here")
        return
    tmp = tempfile.mkdtemp(prefix="mm_cp_")
    try:
        imgs = CP.render(plans["eval_journal"], tmp, only={4})
        dims = jpeg_size(imgs[0]) if imgs else None
        sheet = os.path.join(tmp, "eval_journal", "index.html")
        check("c. one card renders to a 1080 x 1350 JPEG (Instagram's 4:5) + the posting sheet and schedule.csv",
              dims == (1080, 1350) and os.path.exists(sheet) and os.path.exists(os.path.join(tmp, "eval_journal", "schedule.csv")), dims)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------------------------------------ d. poster
def part_d():
    from money_machines import ig_post as IG
    plan = json.load(open(os.path.join(ROOT, "money_machines", "plans", "local_growth_30d.json"), encoding="utf-8"))
    tmp = tempfile.mkdtemp(prefix="mm_ig_")
    calls, logs = [], []
    real_call, real_load = IG._call, IG.load_token
    try:
        led = os.path.join(tmp, "ledger.json")
        n0 = len(NET_TRIES)
        r = IG.run(plan, "2026-11-18", live=False, ledger_path=led, log=logs.append)
        check("d. dry run without a token: plans day 3, sends nothing, writes no ledger, no network",
              r["mode"] == "dry-run" and [x["day"] for x in r["planned"]] == [3] and not r["posted"] and not os.path.exists(led) and len(NET_TRIES) == n0)

        def boom(*a, **k):
            raise AssertionError("the token was read in a dry run")
        IG.load_token = boom
        IG._call = lambda *a, **k: calls.append(a) or {}
        r = IG.run(plan, "2026-11-18", live=False, ledger_path=led, env={"IG_ACCESS_TOKEN": "EAAfake", "IG_USER_ID": "1"}, log=logs.append)
        check("d. dry run WITH a token in the environment: the token is not even read and no API call is made", not calls and r["mode"] == "dry-run")
        IG.load_token = real_load
        IG._call = real_call
        rc = IG.main(["--plan", os.path.join(ROOT, "money_machines", "plans", "local_growth_30d.json"), "--date", "2026-11-18", "--live",
                      "--image-base-url", "https://example.test/ig/", "--token-file", os.path.join(tmp, "missing.json"), "--ledger", led])
        check("d. --live without a token refuses with exit 2 and touches no network", rc == 2 and len(NET_TRIES) == n0)
        inrepo = os.path.join(ROOT, "money_machines", "out", "instagram_token.json")
        try:
            IG.load_token(inrepo, env={})
            ok = False
        except IG.Refused as e:
            ok = "inside the repository" in str(e)
        check("d. a token file inside the repository is refused", ok)
        tf = os.path.join(tmp, "tok.json")
        json.dump({"access_token": "EAAsecretTOKEN123456", "ig_user_id": "1784"}, open(tf, "w"))
        seq = []

        def fake(method, url, params):
            seq.append((method, url.split("/v23.0/")[-1]))
            if "content_publishing_limit" in url:
                return {"data": [{"quota_usage": 3, "config": {"quota_total": 100, "quota_duration": 86400}}]}
            if url.endswith("/media"):
                return {"id": "c-17"}
            if url.endswith("/c-17"):
                return {"status_code": "FINISHED"}
            if url.endswith("/media_publish"):
                return {"id": "m-99"}
            return {}
        IG._call = fake
        out = []
        r = IG.run(plan, "2026-11-18", live=True, base_url="https://example.test/ig/", token_file=tf, ledger_path=led, sleep=lambda s: None, log=out.append)
        check("d. live run (faked API): limit check, create container, wait for FINISHED, publish, in that order",
              [s[1] for s in seq] == ["1784/content_publishing_limit", "1784/media", "c-17", "1784/media_publish"]
              and r["posted"] == [{"day": 3, "media_id": "m-99"}], seq)
        check("d. the token never appears in what the tool prints", not any("EAAsecretTOKEN123456" in x for x in out), out)
        seq.clear()
        r2 = IG.run(plan, "2026-11-18", live=True, base_url="https://example.test/ig/", token_file=tf, ledger_path=led, sleep=lambda s: None, log=out.append)
        check("d. the ledger stops the same day being posted twice (no API call the second time)", not seq and not r2["posted"])
        two = json.loads(json.dumps(plan))
        two["posts"][4]["date"] = two["posts"][3]["date"]          # two posts due the same day
        r3 = IG.run(two, two["posts"][3]["date"], live=True, base_url="https://example.test/ig/", token_file=tf, ledger_path=os.path.join(tmp, "l2.json"),
                    max_per_day=1, sleep=lambda s: None, log=out.append)
        check("d. our cap: with 2 posts due and --max-per-day 1, one is posted and the run stops with the reason",
              len(r3["posted"]) == 1 and "cap" in r3["stopped"], r3)
        IG._call = lambda m, u, p: {"error": {"message": "Application request limit reached", "code": 4}}
        try:
            IG.run(plan, "2026-11-19", live=True, base_url="https://example.test/ig/", token_file=tf, ledger_path=os.path.join(tmp, "l3.json"),
                   sleep=lambda s: None, log=out.append)
            ok = False
        except IG.Refused as e:
            ok = "rate limit" in str(e)
        check("d. a Graph API rate-limit error (code 4) stops the run for the day", ok)
        try:
            IG.run(plan, "2026-11-19", live=True, base_url="http://insecure.test/", token_file=tf, ledger_path=os.path.join(tmp, "l4.json"), log=out.append)
            ok = False
        except IG.Refused as e:
            ok = "https" in str(e)
        check("d. live posting needs a public https image address", ok)
        check("d. the caps: our hard ceiling is 25 a day, the assumed API cap the smaller published number (50)", IG.HARD_CAP_24H == 25 and IG.API_CAP_ASSUMED == 50)
        gi = open(os.path.join(ROOT, "money_machines", ".gitignore"), encoding="utf-8").read()
        check("d. the ledger folder and token files are gitignored", "out/" in gi and "*token*.json" in gi)
    finally:
        IG._call, IG.load_token = real_call, real_load
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------------------------------------ e. digital product
def part_e():
    from money_machines.products import build_eval_tracker as B
    from money_machines.products import eval_math as M
    prod = os.path.join(ROOT, "money_machines", "products", "eval_tracker")
    need = ["Prop_Eval_Tracker.xlsx", "prop_eval_tracker.html", "How_to_use.pdf", "LICENSE.txt", "README.txt", "listing.md", "listing.json",
            "cover.jpg", "cover_square.jpg", "app_screenshot.jpg"]
    missing = [f for f in need if not os.path.exists(os.path.join(prod, f)) or os.path.getsize(os.path.join(prod, f)) < 300]
    check("e. the eval tracker product files are all present (xlsx, web app, PDF, licence, readme, listing, covers, screenshot)", not missing, missing)
    check("e. covers have the platform sizes (1280 x 720 Gumroad/Payhip, 2000 x 2000 Etsy)",
          jpeg_size(os.path.join(prod, "cover.jpg")) == (1280, 720) and jpeg_size(os.path.join(prod, "cover_square.jpg")) == (2000, 2000))
    pdf = open(os.path.join(prod, "How_to_use.pdf"), "rb").read()
    check("e. the how-to is a real PDF", pdf[:5] == b"%PDF-" and b"%%EOF" in pdf[-1024:])
    lst = json.load(open(os.path.join(prod, "listing.json"), encoding="utf-8"))
    text = (lst["title"] + " " + lst["short"] + " " + " ".join(lst["description"]) + " " + json.dumps(lst["faq"])).lower()
    bad = [p for p in (r"guarantee", r"pass your (?:eval|challenge)", r"get funded", r"\bprofitable\b", r"make money", r"win rate", r"passive income")
           if re.search(p, text)]
    check("e. the listing: price $17, title <= 140 chars, 13 Etsy tags <= 20 chars, no performance promise, 'not affiliated' + risk line",
          lst["price_usd"] == 17 and len(lst["title"]) <= 140 and len(lst["tags_etsy"]) == 13 and max(map(len, lst["tags_etsy"])) <= 20 and not bad
          and "not affiliated" in text and "substantial risk of loss" in text, bad)
    net = B.fees(17)
    hand = {"Payhip (free plan)": 17 - 0.85 - (0.493 + 0.30), "Gumroad": 17 - 1.70 - 0.50 - (0.493 + 0.30), "Etsy": 17 - 0.20 - 1.105 - (0.51 + 0.25)}
    check("e. net per $17 sale by hand: Payhip about $15.36, Gumroad $14.01, Etsy $14.94 (card fees 2.9% + $0.30)",
          set(net) == set(hand) and all(abs(net[k] - hand[k]) < 0.006 for k in hand), net)
    app = open(os.path.join(prod, "prop_eval_tracker.html"), encoding="utf-8").read()
    netw = [w for w in ("http://", "https://", "fetch(", "XMLHttpRequest", "WebSocket", "sendBeacon", "<script src", "<link", "import(", "@import")
            if w in app]
    check("e. the web app is offline: a CSP of default-src 'none' and no fetch, script src, link or URL anywhere", not netw
          and "default-src 'none'" in app, netw)
    r = M.compute({"start": 50000, "target": 3000, "max_loss": 2000, "type": "EOD trailing", "lock": 100},
                  [{"pnl": 600}, {"pnl": 1600}, {"pnl": -300, "low": 51000}])
    check("e. the math by hand: EOD level 48,600 after +600, stops at 50,100 (start + 100), drawdown left 51,900 - 50,100 = 1,800",
          [x["floor_after"] for x in r["rows"]] == [48600, 50100, 50100] and r["dd_left"] == 1800 and r["status"] == "OK", r["rows"])
    st = M.compute({"start": 25000, "target": 1500, "max_loss": 1000, "type": "Static", "daily_limit": 500}, [{"pnl": -520, "low": 24400}, {"pnl": -500}])
    check("e. static: a daily-limit day, then a close at the level is a breach (at or below counts)",
          [x["status"] for x in st["rows"]] == ["DAILY LIMIT", "BREACHED"] and st["status"] == "BREACHED", st["rows"])
    z = M.size(2000, 20, 2.0, 0.10, 0.0)
    check("e. size follows the stop: $2,000 left, 10%, 20 points on MNQ = 5 contracts, 10 losses in a row", z["contracts"] == 5 and z["losses_in_a_row"] == 10
          and M.size(2000, 40, 2.0, 0.10)["contracts"] == 2, z)
    from openpyxl import load_workbook
    xl = os.path.join(prod, "Prop_Eval_Tracker.xlsx")
    wf, wv = load_workbook(xl), load_workbook(xl, data_only=True)
    check("e. the spreadsheet keeps formulas (Log, Dashboard, Size) and the drop-down for the drawdown type",
          str(wf["Log"]["J7"].value).startswith("=") and str(wf["Dashboard"]["B15"].value).startswith("=") and str(wf["Size"]["B13"].value).startswith("=")
          and any("B6" in str(dv.sqref) for dv in wf["Rules"].data_validations.dataValidation)
          and wf.sheetnames == ["Start here", "Dashboard", "Rules", "Log", "Size", "Lists"], wf.sheetnames)
    ex = M.compute(B.EXAMPLE_RULES | {"consistency": ""}, [B.EXAMPLE_DAY])
    lv, dv = wv["Log"], wv["Dashboard"]
    check("e. the shipped example row was computed (cached values) and equals the math: balance, level, drawdown left, status",
          lv["G7"].value == ex["rows"][0]["end"] and lv["J7"].value == ex["rows"][0]["floor_after"] and lv["K7"].value == ex["dd_left"]
          and lv["M7"].value == "OK" and dv["B15"].value == ex["status"] and wv["Size"]["B13"].value == 4,
          (lv["G7"].value, lv["J7"].value, lv["K7"].value, dv["B15"].value))
    if os.environ.get("MM_VERIFY_XLSX"):
        probs = B.verify(log=lambda *a: None)
        check("e. (MM_VERIFY_XLSX) LibreOffice recomputes 3 scenarios = eval_math", not probs, probs)
    try:
        from playwright.sync_api import sync_playwright
        exe = __import__("glob").glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome")
    except Exception:
        exe = None
    if exe is not None:
        with sync_playwright() as pw:
            br = pw.chromium.launch(args=["--no-sandbox"], **({"executable_path": sorted(exe)[0]} if exe else {}))
            pg = br.new_page()
            pg.set_content(app)
            diffs = []
            for name, rules, days in B.SCENARIOS:
                js = pg.evaluate("([r, d]) => EvalTracker.compute(r, d)", [rules, days])
                py = M.compute(dict(rules, consistency=(rules["consistency"] / 100 if rules["consistency"] != "" else "")), days)
                for k in ("balance", "floor", "dd_left", "profit", "status", "best_share", "consistency_ok", "more_profit_needed"):
                    if js[k] != py[k] and not (isinstance(py[k], float) and abs((js[k] or 0) - py[k]) < 0.005):
                        diffs.append((name, k, js[k], py[k]))
                if [x["status"] for x in js["rows"]] != [x["status"] for x in py["rows"]]:
                    diffs.append((name, "row statuses"))
            zs = pg.evaluate("() => EvalTracker.size(2000, 20, 2, 0.1, 1, null)")
            br.close()
        check("e. the web app's JavaScript gives the same numbers as eval_math in all 3 scenarios (and the size helper)",
              not diffs and zs["contracts"] == M.size(2000, 20, 2.0, 0.10, 1.0)["contracts"] == 4, diffs)
    else:
        print("[SKIP] e. web app math in Chromium: no playwright here")
    cat = json.load(open(os.path.join(ROOT, "money_machines", "products", "catalog.json"), encoding="utf-8"))
    pr = cat["products"]
    check("e. the catalogue: the built tracker + 7 more products (team D2: tests.test_digital_products; night B: tests.test_money_door), each with price, effort, platforms and a source",
          len(pr) == 8 and pr[0]["id"] == "prop-eval-tracker" and all(p["status"] in ("built", "planned") for p in pr)
          and all(p["price_usd"] > 0 and p["platforms"] and "effort_h" in p and (p.get("source") or p.get("files")) for p in pr))
    tmp = tempfile.mkdtemp(prefix="mm_zip_")
    try:
        old = B.OUT
        B.OUT = tmp
        zp = B.make_zip()
        import zipfile
        names = zipfile.ZipFile(zp).namelist()
        check("e. the upload zip holds the 5 buyer files and nothing else", sorted(names) == sorted(B.LISTING["files"]), names)
    finally:
        B.OUT = old
        shutil.rmtree(tmp, ignore_errors=True)


PARTS = {"a": part_a, "b": part_b, "c": part_c, "d": part_d, "e": part_e}


def main(argv=None):
    want = (argv or sys.argv[1:]) or list(PARTS)
    for k in want:
        PARTS[k]()
    check("no network was touched by any part", not NET_TRIES, NET_TRIES[:3])
    print(f"\n{sum(RES)}/{len(RES)} passed")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
