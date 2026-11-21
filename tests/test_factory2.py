"""Website Factory 2 (lead 2026-11-21): the agency launch site (tools/agency_site.py), 'yes -> live in 24 h' delivery
(tools/client_deliver.py) and the first 100 calls (tools/first_calls.py).

    python tests/test_factory2.py            static (fast)
    python tests/test_factory2.py --browser  + the exported launch site and a client bundle in a phone browser (under the browser lock)
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import agency_site as AS  # noqa: E402
from tools import client_deliver as CD  # noqa: E402
from tools import first_calls as FC  # noqa: E402
from tools import site_factory as F  # noqa: E402

RES = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("  [OK]  " if ok else "  [FAIL] ") + name + ("" if ok else f"  -> {str(info)[:400]}"))


def main() -> int:
    sites = json.load(open(os.path.join(F.WEB, "factory", "sites.json")))["sites"]
    paths = {s["path"] for s in sites}
    # ---------------------------------------------------------------- a. the agency launch site
    fs = AS.build_files({"phone": "", "agency_name": "", "agency_email": ""}, prefix="", base="https://neutral.example/")
    areas = [k for k in fs if re.fullmatch(r"areas/[a-z0-9-]+-md\.html", k)]
    check("a. home, work, pricing, FAQ, contact, style, sitemap + 16 local pages + area index",
          {"index.html", "work.html", "pricing.html", "faq.html", "contact.html", "style.css", "sitemap.xml", "areas/index.html"} <= set(fs) and len(areas) == 16, sorted(fs))
    trades = {re.sub(r"-[a-z-]+?-md\.html$", "", a.split("/")[1]) for a in areas}
    check("a. local pages cover several trades (not 16 copies of one)", len({a.split("/")[1].split("-")[0] for a in areas}) >= 4, sorted(areas))
    bad = []
    for a in areas:
        h = fs[a]
        m = re.search(r"<h1>Website design for (.+?) in (.+?), MD</h1>", h)
        num = re.search(r'<div class="stat">(\d+)</div>', h)
        if not m or not num or "What a" not in h or "OpenStreetMap" not in h:
            bad.append(a)
    check("a. each local page: 'Website design for <trade> in <town>, MD', a real count from the leads, trade-specific advice", not bad, bad)
    allh = "".join(v for k, v in fs.items() if k.endswith(".html"))
    check("a. no testimonials, awards, ratings, client counts or guarantees", not re.search(r"testimonial|award|\brated\b|\b\d+ stars\b|guarantee|happy clients|trusted by", allh, re.I),
          re.findall(r"testimonial|award|\brated\b|guarantee|trusted by", allh, re.I)[:5])
    of = json.load(open(AS.OFFERS))
    st = {p["id"]: p for p in of["packages"]}["starter"]
    check("a. prices from offers.json (Starter $1,500 + $79/mo, $149/mo nothing upfront, Call engine)",
          f"${st['price']:,}" in fs["pricing.html"] and f"${st['monthly']}/month" in fs["pricing.html"] and "$149/month" in fs["pricing.html"] and "Call engine" in fs["pricing.html"])
    ld = re.search(r'<script type="application/ld\+json">(.*?)</script>', fs["index.html"], re.S)
    try:
        j = json.loads(ld.group(1)) if ld else {}
    except ValueError:
        j = {}
    check("a. schema.org LocalBusiness with placeholders (name, phone, email) and the 16 towns as areaServed",
          j.get("@type") == "LocalBusiness" and j.get("name") == "AGENCY_NAME" and j.get("telephone") == "AGENCY_PHONE" and len(j.get("areaServed", [])) == 16, j)
    check("a. contact needs no paid service: mailto + phone only, no form, no third-party script",
          "mailto:AGENCY_EMAIL" in fs["contact.html"] and "<form" not in allh and not re.search(r"<script[^>]+src=", allh))
    sm = fs["sitemap.xml"]
    check("a. sitemap lists every page (22) on the public base", sm.count("<loc>") == 6 + 16 and "https://neutral.example/areas/" in sm)
    check("a. noindex until the agency is named; indexable once named",
          'content="noindex, nofollow"' in fs["index.html"] and 'content="index, follow"' in AS.build_files({"agency_name": "Main St Web"}, prefix="", base="https://x.example/")["index.html"])
    links = set()
    for k, v in fs.items():
        if not k.endswith(".html"):
            continue
        d = os.path.dirname(k)
        for h in re.findall(r'href="([^"#?:]+)"', v):
            if h.startswith(("http", "mailto", "tel", "data")):
                continue
            links.add(os.path.normpath(os.path.join(d, h)).replace(os.sep, "/"))
    broken = [x for x in links if x not in fs and not (x.startswith("f/") and x.rstrip("/") + "/" in paths)]
    check("a. every internal link resolves (pages + concept sites f/<id>/)", not broken, broken[:8])
    leak = [m.group(0) for v in fs.values() for m in [re.search("|".join(F.FORBIDDEN), v, re.I)] if m]
    check("a. nothing points at Olympus, the owner or a PC", not leak, leak[:5])
    # export carries it
    with tempfile.TemporaryDirectory() as t:
        ag, out = os.path.join(t, "ag.json"), os.path.join(t, "out")
        json.dump({"public_base": "https://neutral.example/"}, open(ag, "w"))
        r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "site_factory.py"), "--export", out], capture_output=True, text=True, timeout=300,
                           env={**os.environ, "SITE_FACTORY_AGENCY": ag})
        okx = r.returncode == 0 and os.path.isfile(os.path.join(out, "pricing.html")) and len(os.listdir(os.path.join(out, "areas"))) == 17 \
            and "already built" in open(os.path.join(out, "index.html")).read()
    check("a. the neutral-host export carries the launch site at its root", okx, r.stderr[-300:])
    # ---------------------------------------------------------------- b. client delivery
    lead = next(s for s in sites if s["phone"])
    with tempfile.TemporaryDirectory() as t:
        from PIL import Image
        Image.new("RGB", (400, 300), (200, 80, 40)).save(os.path.join(t, "a.jpg"))
        Image.new("RGB", (64, 64), (20, 20, 20)).save(os.path.join(t, "logo.png"))
        open(os.path.join(t, "fake.jpg"), "w").write("not an image")
        with open(os.path.join(t, "big.jpg"), "wb") as f:
            f.write(b"\xff\xd8" + os.urandom(CD.MAX_IMG + 10))
        ok_ed = {"domain": "https://www.example-diner.com/", "tagline": "Breakfast on Main Street.", "about": "A small family place.",
                 "services": [["Breakfast", "Eggs and pancakes."], ["Lunch", "Sandwiches."]], "logo": os.path.join(t, "logo.png"),
                 "photos": [os.path.join(t, "a.jpg")], "hours": "Mo-Fr 07:00-15:00; Sa 08:00-14:00; Su off"}
        refusals = {}
        for nm, ed in {"no domain": {}, "github.io": {"domain": "me.github.io"}, "missing photo": {"domain": "x.com", "photos": [os.path.join(t, "nope.jpg")]},
                       "not an image": {"domain": "x.com", "photos": [os.path.join(t, "fake.jpg")]}, "over 2 MB": {"domain": "x.com", "photos": [os.path.join(t, "big.jpg")]},
                       "fake review words": {"domain": "x.com", "tagline": "Rated #1 by 500 happy reviews"}}.items():
            try:
                CD.deliver(lead["id"], ed, os.path.join(t, "o"))
                refusals[nm] = False
            except CD.Refused:
                refusals[nm] = True
        check("b. delivery refuses: no domain, a github.io domain, a missing / fake / 2 MB+ image, fake-review words", all(refusals.values()), refusals)
        r = CD.deliver(lead["code"], ok_ed, os.path.join(t, "o"))
        site = os.path.join(r["dir"], "site")
        h = open(os.path.join(site, "index.html")).read()
        need = ["index.html", "404.html", "robots.txt", "sitemap.xml", "CNAME", "_headers", ".nojekyll", "img/logo.png", "img/photo-1.jpg"]
        check("b. bundle by code: site/ with index, 404, robots, sitemap, CNAME, _headers, images + PUBLISH.md + CARE_PLAN.md",
              all(os.path.exists(os.path.join(site, n)) for n in need) and all(os.path.exists(os.path.join(r["dir"], n)) for n in ("PUBLISH.md", "CARE_PLAN.md", "bundle.json"))
              and open(os.path.join(site, "CNAME")).read().strip() == "example-diner.com", r)
        check("b. production page: indexable, canonical = the client's domain, their words / services / logo / photos, no concept text or agency band",
              'content="index, follow"' in h and 'href="https://example-diner.com/"' in h and "Breakfast on Main Street." in h and "Sandwiches." in h
              and 'src="img/logo.png"' in h and 'src="img/photo-1.jpg"' in h and "Concept made for" not in h and 'data-agency' not in h and "noindex" not in h)
        pub = open(os.path.join(r["dir"], "PUBLISH.md")).read()
        check("b. PUBLISH.md: GitHub Pages + Cloudflare Pages steps with the domain + the 4 GitHub A records; CARE_PLAN.md: the monthly checklist",
              "example-diner.com" in pub and pub.count("185.199.") == 4 and "Cloudflare" in pub and "Monthly" in open(os.path.join(r["dir"], "CARE_PLAN.md")).read())
        check("b. the bundle is small (< 100 KB of HTML)", len(h.encode()) < 100 * 1024)
        if "--browser" in sys.argv:
            shots = os.path.join(ROOT, "scratch", "factory2_shots")
            os.makedirs(shots, exist_ok=True)
            res = subprocess.run(["node", os.path.join(ROOT, "tests", "site_factory_shots.cjs"), site, shots, ""], capture_output=True, text=True, timeout=120)
            try:
                x = json.loads(res.stdout.strip().splitlines()[-1])[0]
            except (ValueError, IndexError):
                x = {"errs": [res.stderr[-200:]], "sw": 999}
            check("b. the client page opens at 390 px: no error, no sideways scroll", not x["errs"] and x["sw"] <= 390, x)
    # ---------------------------------------------------------------- c. first 100 calls
    d = json.load(open(FC.OUT))
    rows = d["leads"]
    check("c. first100.json: the caller-portal list format, 100 rows (or every lead with a phone)",
          d.get("kind") == "caller-portal-list" and d["count"] == len(rows) and 0 < len(rows) <= 100
          and all({"id", "name", "phone", "town", "state", "niche", "kind", "code", "site", "heat"} <= set(r) for r in rows), d.get("count"))
    check("c. every row has a 10-digit phone, a concept site that exists and a code; no chain", all(re.fullmatch(r"\d{10}", r["phone"]) and r["site"] in paths and r["code"]
                                                                                                     and not F.chain_of(r["name"]) for r in rows))
    check("c. ranked: score never goes up down the list; rank 1..n", all(rows[i]["score"] >= rows[i + 1]["score"] for i in range(len(rows) - 1))
          and [r["rank"] for r in rows] == list(range(1, len(rows) + 1)))
    check("c. the calling-hours reader: open 5 weekdays for 'Mo-Fr 09:00-17:00', 0 for 'Mo-Fr 18:00-23:00', 0 unknown",
          FC.weekday_open_days("Mo-Fr 09:00-17:00") == 5 and FC.weekday_open_days("Mo-Fr 18:00-23:00") == 0 and FC.weekday_open_days("") == 0)
    fresh = FC.build(len(rows))
    check("c. the committed list = a fresh build (run python tools/first_calls.py after the leads change)",
          [r["id"] for r in fresh["leads"]] == [r["id"] for r in rows])
    print(f"{sum(RES)} passed, {len(RES) - sum(RES)} failed")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
