"""CONCEPT-SITE QUALITY for the call sheet (day-a11y 2026-11-22; Monday's dialing: agency/calls/2026-11-23.csv, 150 businesses).

    python -X utf8 -m tests.test_site_quality            (--static: no browser)
a. the generator (tools/site_factory.py): the business's name wins over a wrong map category (a daycare filed as optometry), never for adult
   day care; every tap target the page draws is >= 44 px (the header call button, the phone link); the price-book package line; the premium
   parts are honest (a sample photo says so, the reviews block says "your reviews here" and that we never write reviews)
b. the 150 pages on the call sheet (static): each exists, names the business and the town, its call link dials the sheet's number, no placeholder
   or lorem text; the top 20 (premium) have a hero photo that exists here (CC0, never hotlinked), the reviews block and the package
c. browser 390 x 844 + 1280 on a sample (the top 20 + every 10th): every image loads, every tap target >= 44 px, no sideways scroll, no page error
"""
from __future__ import annotations

import csv
import html
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
W = os.path.join(ROOT, "tools", "web_public")
SHEET = os.path.join(ROOT, "agency", "calls", "2026-11-23.csv")
FAILS: list = []
N = [0]


def check(name, ok, info=""):
    N[0] += 1
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  [{str(info)[:400]}]"))
    if not ok:
        FAILS.append(name)


def rows():
    with open(SHEET, encoding="utf-8") as f:
        return sorted([r for r in csv.DictReader(l for l in f if not l.startswith("#"))], key=lambda r: int(r["rank"]))


def html_of(r):
    with open(os.path.join(W, "agency", r["concept_site"], "index.html"), encoding="utf-8") as f:
        return f.read()


def generator():
    from tools import site_factory as F
    nk = {n: F.name_kind({"name": n, "category": c}) for n, c in (("Abc home DAYCARE", "optometry"), ("Evergreen Adult Medical Daycare Center", "health care"),
                                                                  ("Family Dentistry", "dentist"), ("Cool Breeze Plumbing, Heating & A/C", "hvac service"),
                                                                  ("Paradise Indian Grill", "software development"), ("Norby's Cafe", "coffee shop"))}
    check("a. the name wins over a wrong category (a daycare filed as optometry -> Child care; a grill filed as software -> Restaurant); never for adult "
          "day care, never when the category already agrees",
          nk["Abc home DAYCARE"][1] == "Child care" and nk["Paradise Indian Grill"][1] == "Restaurant" and nk["Evergreen Adult Medical Daycare Center"] is None
          and nk["Family Dentistry"] is None and nk["Cool Breeze Plumbing, Heating & A/C"] is None and nk["Norby's Cafe"] is None, nk)
    src = open(os.path.join(ROOT, "tools", "site_factory.py"), encoding="utf-8").read()
    check("a. the header call button and the phone link are >= 44 px (were 38 px and a 20 px text link)",
          "min-height:38px" not in src and 'style="min-height:44px;padding:0 14px;font-size:.9rem"' in src and '<a class="tap" href="tel:' in src
          and ".tap{display:inline-flex;align-items:center;min-height:44px" in src)
    pb = json.load(open(os.path.join(ROOT, "agency", "pricebook.json"), encoding="utf-8"))
    st = next(x for x in pb["packages"] if x["id"] == "starter")
    line = F.pricebook_offer()
    check("a. the package line comes from the price book (Starter setup + monthly, pages, days; the no-upfront plan)",
          f"${st['setup']:,} setup + ${st['monthly']}/month" in line and f"${pb['no_upfront']['monthly']}/month for {pb['no_upfront']['months']} months" in line, line)
    photo, rev, pkg = F.premium_parts({"name": "Ace Roofing", "category": "roofing"}, "Roofing", "Ace Roofing")
    check("a. premium parts are honest: 'Sample photo: your own photos go here', 'Your reviews here', 'We never write reviews'; the photo is local",
          'src="../img/roofing.webp"' in photo and "Sample photo: your own photos go here." in photo and "Your reviews here." in rev
          and "We never write reviews" in rev and "This site, yours this week" in pkg and "http" not in photo, (photo[:120], rev[:80]))
    check("a. no stock photo of children (child care keeps its drawn art); every photo key has its file and a CC0 credit",
          F.photo_key({"name": "Abc home DAYCARE"}, "Child care") == "" and all(os.path.isfile(os.path.join(W, "agency", "f", "img", k + ".webp")) for _, k in F.PHOTOS)
          and set(json.load(open(os.path.join(W, "agency", "f", "img", "CREDITS.json")))["photos"]) >= {k for _, k in F.PHOTOS})


def sheet():
    R = rows()
    check("b. the call sheet has 150 businesses, each with a concept site", len(R) == 150 and all(re.fullmatch(r"f/[a-z2-9]{8}/", r["concept_site"]) for r in R), len(R))
    bad = {}
    for r in R:
        h = html_of(r)
        text = html.unescape(re.sub(r"<[^>]+>", " ", re.sub(r"<(script|style)\b.*?</\1>", " ", h, flags=re.S)))
        name = re.sub(r"\s+", " ", r["name"]).strip()
        ph = re.sub(r"\D", "", r["phone"] or "")[-10:]
        why = []
        if name.lower() not in re.sub(r"\s+", " ", text).lower():
            why.append("name")
        if r["town"] and r["town"].lower() not in text.lower():
            why.append("town")
        if ph and f'href="tel:+1{ph}"' not in h:
            why.append("call")
        if re.search(r"lorem|ipsum|\bTODO\b|undefined|\bNaN\b|\{\{|\[(your|business|name|town)", text, re.I):
            why.append("placeholder")
        if why:
            bad[r["rank"]] = why
    check("b. all 150 pages: the business name + town, a call link that dials the sheet's number, no placeholder text", not bad, bad)
    top = R[:20]
    miss = {}
    for r in top:
        h = html_of(r)
        m = re.search(r'src="\.\./img/([a-z]+)\.webp"', h)
        if "Child care" not in h and not (m and os.path.isfile(os.path.join(W, "agency", "f", "img", m.group(1) + ".webp"))):
            miss[r["rank"]] = "photo"
        if 'id="h-rev"' not in h or 'class="pkg"' not in h:
            miss[r["rank"]] = "reviews / package"
    check("b. the top 20: a hero photo that exists here (child care keeps its art), the honest reviews block and the price-book package", not miss, miss)
    rest = [r for r in R[20:] if 'class="pkg"' in html_of(r)]
    check("b. ranks 21-150 keep the light page (no premium parts)", not rest, [r["rank"] for r in rest][:5])
    kinds = {r["rank"]: re.search(r'<span class="kind rise">.*?</svg>([^<]*)', html_of(r)).group(1) for r in R[:20]}
    check("b. the trade on the page is right for the top 20 (rank 11, a home daycare, reads Child care, not Optometry)",
          kinds["11"].startswith("Child care") and kinds["1"].startswith("Dental office") and kinds["20"].startswith("Air duct"), kinds)


def browser():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("SKIP browser: no Python playwright")
        return
    sys.path.insert(0, os.path.join(ROOT, "tests"))
    import browser_kit as BK
    from tests import agora_kit as AK
    R = rows()
    sample = R[:20] + R[20::10]
    js = """() => ({ imgs: [...document.images].filter((i) => !i.complete || i.naturalWidth === 0).length, n: document.images.length,
      small: [...document.querySelectorAll('a, button')].filter((e) => { const r = e.getBoundingClientRect(); return r.width && r.height && r.height < 43.5
        && !(e.closest('footer') && !e.className); }).map((e) => e.textContent.trim().slice(0, 16) + ':' + Math.round(e.getBoundingClientRect().height)),
      wide: document.documentElement.scrollWidth - innerWidth })"""
    srv, origin = AK.serve()
    try:
        with sync_playwright() as pw:
            br = BK.launch(pw)
            for vw, vh in ((390, 844), (1280, 800)):
                ctx = br.new_context(viewport={"width": vw, "height": vh}, service_workers="block")
                ctx.route(re.compile(r"^(?!https?://127\.0\.0\.1)"), lambda r: r.abort())
                p = ctx.new_page()
                errs, bad = [], {}
                p.on("pageerror", lambda e: errs.append(str(e)[:100]))
                for r in sample:
                    p.goto(f"{origin}/agency/{r['concept_site']}", wait_until="load")
                    o = p.evaluate(js)
                    if o["imgs"] or o["small"] or o["wide"] > 1:
                        bad[r["rank"]] = o
                photos = sum(1 for r in R[:20] if "img/" in html_of(r))
                check(f"c. {vw}px: {len(sample)} pages (the top 20 + every 10th): every image loads ({photos} hero photos), every tap target >= 44 px, "
                      "no sideways scroll, no page error", not bad and not errs, (list(bad.items())[:3], errs[:2]))
                ctx.close()
            br.close()
    finally:
        srv.shutdown()


if __name__ == "__main__":
    generator()
    sheet()
    if "--static" not in sys.argv:
        browser()
    print(f"\n{N[0] - len(FAILS)}/{N[0]} passed" + ("" if not FAILS else f"; FAILED: {FAILS}"))
    sys.exit(1 if FAILS else 0)
