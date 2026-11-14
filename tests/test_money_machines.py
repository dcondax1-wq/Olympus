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
        n0 = len(NET_TRIES)
        p = GP.run_report("https://example.com", "Rivera Plumbing", tmp, use_audit=False)
        page = open(p, encoding="utf-8").read()
        check("b. the website report without the agency kit: written, says the automatic check did not run, no network", "not available here" in page
              and len(NET_TRIES) == n0 and "PageSpeed" in page)
        fake = {"issues": [{"code": "no_tel", "weight": 10, "text": "The phone number is not tap-to-call"},
                           {"code": "no_https", "weight": 20, "text": "No padlock"}], "facts": {"https": False}}
        h = GP.report_html("Rivera Plumbing", "http://x.test", fake, "2026-11-14")
        check("b. the report lists what the check found, biggest first", h.index("No padlock") < h.index("tap-to-call") and "2026-11-14" in h)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    st = GP.tool_status()
    check("b. --check knows the tool of every gig (ours ready: brand kit + GBP checklist)", len(st) == 8
          and {g for g, m, ok, s in st if ok} >= {"logo-brand-kit", "gbp-setup"}, st)


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


PARTS = {"a": part_a, "b": part_b, "c": part_c, "d": part_d}


def main(argv=None):
    want = (argv or sys.argv[1:]) or list(PARTS)
    for k in want:
        PARTS[k]()
    check("no network was touched by any part", not NET_TRIES, NET_TRIES[:3])
    print(f"\n{sum(RES)}/{len(RES)} passed")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
