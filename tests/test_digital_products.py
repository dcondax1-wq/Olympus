"""DIGITAL PRODUCTS 2-5 (team D2, 2026-11-14): the website templates, the social media kit, the agency starter kit and the trader planner.
No network at all (every socket connect and urlopen raises). No browser: the pictures and PDFs are checked as files. Checks:
  a. every product: the buyer files are all present, the upload zip builds with plain Python (one top folder, exactly the buyer files,
     deterministic bytes, under 10 MB), 6 covers at 1280 x 720 / 2000 x 2000 (JPEG, each under 900 KB)
  b. honesty: no outside link in any buyer file (only the shop's host may appear; vocabulary names such as XML namespaces excepted),
     no third-party brand name or trademark from kit.TRADEMARKS in any buyer file or the buyer-facing listing text, no income /
     result / ranking promise (kit.PROMISES), office files carry neutral metadata
  c. listing: title <= 140, 13 unique tags <= 20 chars, 6 FAQ, a refund line, the price = the catalogue's, comparables with a link and
     a date, the fee table = kit.fees (and the numbers by hand for one price)
  d. website templates: the 5 pages are the editor's own renderer output (Node, when installed), phone viewport, a tap-to-call link,
     structured data that parses, no script or style loaded from anywhere, colour pairs >= 4.5:1, the editor has a no-network CSP
  e. social kit: 30 days x 12 designs, 150 unique captions with <= 5 hashtags, a review rule on review posts, alt text for every day,
     colour pairs pass, the Post Maker has a no-network CSP and no network calls, the CSV has 30 rows
  f. agency kit: 7 .docx + 2 .xlsx, the agreement says NOT LEGAL ADVICE, the first email has the opt-out and postal-address lines,
     the spreadsheets keep formulas and their cached results add up (invoice total, pricing)
  g. trader planner: Letter and A4 PDFs with 16 pages at the right size, the journal keeps formulas and computed the examples, the
     risk line is in the readme, licence and listing, the example rows show no profit or loss
  h. catalogue, docs and the money test area: 5 built products, folded ideas named, docs/MONEY_MACHINES.md lists each build command,
     tests/run_area.py runs this suite in the money area, the product folders stay under 15 MB
    python -X utf8 -m tests.test_digital_products            (parts: a b c d e f g h, e.g. python -m tests.test_digital_products d e)
"""
from __future__ import annotations

import hashlib
import importlib
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

RES, NET_TRIES = [], []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:700]}"), flush=True)


def _no_net(*a, **k):
    NET_TRIES.append(a[:1])
    raise OSError("network disabled in tests.test_digital_products")


socket.socket.connect = _no_net
socket.create_connection = _no_net
urllib.request.urlopen = _no_net

from money_machines.products import kit as K  # noqa: E402

PRODUCTS = {
    "site_templates": "money_machines.products.build_site_templates",
    "social_kit": "money_machines.products.build_social_kit",
    "agency_kit": "money_machines.products.build_agency_kit",
    "trader_planner": "money_machines.products.build_trader_planner",
}
REQUIRED = {
    "site_templates": ["Site_Editor.html", "Guide.pdf", "LICENSE.txt", "README.txt"] + [f"templates/{d}/index.html" for d in
                                                                                      ("1-trades", "2-home-garden", "3-cafe", "4-salon", "5-barber")],
    "social_kit": ["Post_Maker.html", "30_Day_Plan.pdf", "30_Day_Plan.csv", "Caption_Bank.pdf", "Caption_Bank.txt", "All_30_Designs.jpg", "How_to_use.pdf",
                   "LICENSE.txt", "README.txt"],
    "agency_kit": ["00_Start_Here.pdf", "01_Outreach_Scripts.docx", "02_Discovery_Call.docx", "03_Proposal_Template.docx", "04_Service_Agreement.docx",
                   "05_Client_Onboarding.docx", "06_Reviews_and_Referrals.docx", "07_Service_Checklists.docx", "Agency_Tracker.xlsx", "Invoice_Template.xlsx",
                   "LICENSE.txt", "README.txt"],
    "trader_planner": ["Trader_Planner_Letter.pdf", "Trader_Planner_A4.pdf", "Trader_Journal.xlsx", "LICENSE.txt", "README.txt"],
}
CATALOG_ID = {"site_templates": "local-site-templates", "social_kit": "social-post-pack", "agency_kit": "agency-starter-kit", "trader_planner": "trader-routine-planner"}


def mod(name):
    return importlib.import_module(PRODUCTS[name])


def prod_dir(name):
    return os.path.join(ROOT, "money_machines", "products", name)


def buyer(name):
    return os.path.join(prod_dir(name), "buyer")


def listing(name):
    return json.load(open(os.path.join(prod_dir(name), "shop", "listing.json"), encoding="utf-8"))


# ------------------------------------------------------------------------------------------------ a. files, zips, covers
def part_a():
    for name in PRODUCTS:
        M = mod(name)
        files = K.buyer_files(buyer(name))
        missing = [f for f in REQUIRED[name] if f not in files]
        empty = [f for f in files if os.path.getsize(os.path.join(buyer(name), f)) < 200]
        check(f"a. {name}: every buyer file is present and not empty ({len(files)} files)", not missing and not empty, (missing, empty))
        L = listing(name)
        check(f"a. {name}: listing.json names exactly the buyer files", sorted(L["files"]) == files, set(L["files"]) ^ set(files))
        tmp = tempfile.mkdtemp(prefix="dp_zip_")
        try:
            z1 = M.make_zip(tmp)
            h1 = hashlib.sha256(open(z1, "rb").read()).hexdigest()
            names = zipfile.ZipFile(z1).namelist()
            bad = zipfile.ZipFile(z1).testzip()
            z2 = M.make_zip(tmp)
            h2 = hashlib.sha256(open(z2, "rb").read()).hexdigest()
            size = os.path.getsize(z1)
            check(f"a. {name}: the upload zip builds with plain Python: one top folder '{M.TOP}/', exactly the buyer files, no damage, same bytes twice, {size // 1024} KB (< 10 MB)",
                  sorted(names) == sorted(f"{M.TOP}/{f}" for f in files) and bad is None and h1 == h2 and size < 10 * 1024 * 1024 and os.path.basename(z1) == M.ZIP,
                  (names[:5], bad, size))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        shop = os.path.join(prod_dir(name), "shop")
        probs = []
        for fn, w, h in K.COVERS:
            p = os.path.join(shop, fn)
            if not os.path.exists(p):
                probs.append(f"{fn} missing")
                continue
            try:
                got = K.jpeg_size(p)
            except ValueError as e:
                probs.append(str(e))
                continue
            if got != (w, h):
                probs.append(f"{fn} is {got}, want {(w, h)}")
            if os.path.getsize(p) > 900 * 1024:
                probs.append(f"{fn} is {os.path.getsize(p) // 1024} KB")
        check(f"a. {name}: 3 covers at 1280 x 720 + 3 at 2000 x 2000, JPEG, each under 900 KB", not probs, probs)


# ------------------------------------------------------------------------------------------------ b. honesty
def part_b():
    for name in PRODUCTS:
        links, marks, promises, meta = {}, {}, {}, []
        for rel in K.buyer_files(buyer(name)):
            p = os.path.join(buyer(name), rel)
            text, lk = K.file_text(p)
            if lk:
                links[rel] = lk[:3]
            tm = K.trademark_hits(text)
            if tm:
                marks[rel] = tm
            pr = K.promise_hits(text)
            if pr:
                promises[rel] = pr[:2]
            if rel.endswith((".docx", ".xlsx")):
                with zipfile.ZipFile(p) as z:
                    app = z.read("docProps/app.xml").decode("utf-8", "replace") if "docProps/app.xml" in z.namelist() else ""
                    core = z.read("docProps/core.xml").decode("utf-8", "replace") if "docProps/core.xml" in z.namelist() else ""
                if re.search(r"Microsoft|openpyxl|python-docx|LibreOffice", app + core):
                    meta.append(rel)
            if rel.endswith(".pdf"):
                raw = open(p, "rb").read()
                if re.search(rb"/(?:Producer|Creator)\s*\((?:Skia|Chromium|Google)", raw):
                    meta.append(rel)
        check(f"b. {name}: no outside link in any buyer file (the shop's host only: {list(K.SHOP_HOSTS) or 'none set'})", not links, links)
        L = listing(name)
        lt = K.listing_text(L)
        check(f"b. {name}: no third-party brand name or trademark in the buyer files or the listing copy ({len(K.TRADEMARKS)} names checked)",
              not marks and not K.trademark_hits(lt), (marks, K.trademark_hits(lt)))
        check(f"b. {name}: no income, result, ranking or pass promise in the buyer files or the listing copy",
              not promises and not K.promise_hits(lt), (promises, K.promise_hits(lt)))
        check(f"b. {name}: office files and PDFs carry neutral metadata (no app or tool names)", not meta, meta)
    # the scanners themselves catch what they should
    check("b. the scanners: an outside link, a brand name and an income promise are caught; a disclaimer and a namespace are not",
          K.outside_links("see https://example.com/x") == ["https://example.com/x"] and not K.outside_links('xmlns="http://www.w3.org/2000/svg"')
          and K.trademark_hits("Made for Instagram") == ["Instagram"] and not K.trademark_hits("instagrammable square posts")
          and K.promise_hits("Earn $500 a day") and not K.promise_hits("It promises nothing and does not guarantee results."))


# ------------------------------------------------------------------------------------------------ c. listings and fees
def part_c():
    cat = {p["id"]: p for p in json.load(open(os.path.join(ROOT, "money_machines", "products", "catalog.json"), encoding="utf-8"))["products"]}
    for name in PRODUCTS:
        L = listing(name)
        tags = L["tags_etsy"]
        check(f"c. {name}: title <= 140 chars ({len(L['title'])}), 13 unique tags <= 20 chars, 6 FAQ, a refund line, a short line",
              len(L["title"]) <= 140 and len(tags) == 13 and len(set(tags)) == 13 and all(len(t) <= 20 for t in tags) and len(L["faq"]) >= 6
              and "14 days" in L["refund"] and 20 < len(L["short"]) <= 160, (len(L["title"]), [t for t in tags if len(t) > 20]))
        c = cat.get(CATALOG_ID[name], {})
        check(f"c. {name}: price ${L['price_usd']} = the catalogue's, with the reasoning and >= 4 comparables (link + date)",
              L["price_usd"] == c.get("price_usd") and len(L["price_reasoning"]) > 120 and len(L["comparables"]) >= 4
              and all(x["url"].startswith("https://") and x["seen"] == "2026-11-14" and x["price"] for x in L["comparables"]), (L["price_usd"], c.get("price_usd")))
        net = K.fees(L["price_usd"])
        ft = {r["platform"]: r["net_usd"] for r in L["fee_table"]}
        md = open(os.path.join(prod_dir(name), "shop", "listing.md"), encoding="utf-8").read()
        check(f"c. {name}: the fee table equals kit.fees and listing.md shows it ({', '.join(f'{k.split()[0]} ${v:.2f}' for k, v in net.items())})",
              ft == net and L["net_per_sale_usd"] == net and all(f"${v:.2f}" in md for v in net.values()), (ft, net))
        desc = "\n".join(L["description"])
        check(f"c. {name}: the description discloses AI help (Etsy's rule) and has no outside link", "AI tools" in desc and not K.outside_links(desc))
    f = K.fees(24)
    check("c. the fee math by hand for $24: Payhip 24 - 1.20 - (0.70 + 0.30) = 21.80; Gumroad 24 - 2.40 - 0.50 - 1.00 = 20.10; Etsy 24 - 0.20 - 1.56 - 0.97 = 21.27",
          f == {"Payhip (free plan)": 21.80, "Gumroad": 20.10, "Etsy": 21.27}, f)


# ------------------------------------------------------------------------------------------------ d. website templates
def _contrast(a, b):
    def lum(h):
        h = h.lstrip("#")
        vals = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        vals = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in vals]
        return 0.2126 * vals[0] + 0.7152 * vals[1] + 0.0722 * vals[2]
    x, y = lum(a), lum(b)
    return (max(x, y) + 0.05) / (min(x, y) + 0.05)


def part_d():
    from money_machines.products import site_templates_data as SD
    B = mod("site_templates")
    ed = open(B.EDITOR, encoding="utf-8").read()
    check("d. the editor is current: Site_Editor.html = editor.html + the data (a fresh build gives the same file)", ed == B.editor_html())
    csp = re.search(r'http-equiv="Content-Security-Policy" content="([^"]+)"', ed)
    check("d. the editor allows no network: CSP default-src 'none', no connect/script/style source outside the page; no fetch, XHR, beacon or socket",
          csp and "default-src 'none'" in csp.group(1) and "http" not in csp.group(1)
          and not re.search(r"\bfetch\(|XMLHttpRequest|sendBeacon|WebSocket|EventSource|import\(", ed), csp and csp.group(1))
    bad_pairs = []
    for tid, t in SD.THEMES.items():
        for a, b in SD.CONTRAST_PAIRS:
            r = _contrast(t["palette"][a], t["palette"][b])
            if r < 4.5:
                bad_pairs.append((tid, a, b, round(r, 2)))
    check("d. all 5 looks: every text colour pair >= 4.5:1 (WCAG AA), 9 pairs each", not bad_pairs, bad_pairs)
    node = B.node_exe()
    pages = {}
    for tid in SD.ORDER:
        pages[tid] = open(B.template_path(tid), encoding="utf-8").read()
    if node:
        fresh = B.render_all(ed)
        check("d. the 5 template files are exactly the editor's own renderer output (Node)", all(fresh[t] == pages[t] for t in SD.ORDER),
              [t for t in SD.ORDER if fresh[t] != pages[t]])
    else:
        print("[SKIP] d. renderer output check: Node is not installed")
    probs = []
    for tid, html in pages.items():
        if 'name="viewport"' not in html or '<html lang="en">' not in html or "<h1>" not in html:
            probs.append(f"{tid}: viewport / lang / h1")
        if not re.search(r'href="tel:\+?\d{7,}"', html):
            probs.append(f"{tid}: no tap-to-call link")
        if re.search(r"<script[^>]+src=|<link[^>]+rel=\"stylesheet\"|@import|url\(\s*['\"]?https?:", html):
            probs.append(f"{tid}: loads something from outside")
        m = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
        try:
            ld = json.loads(m.group(1))
            if ld.get("@context") != "https://schema.org" or not ld.get("name") or not ld.get("telephone"):
                probs.append(f"{tid}: structured data fields")
        except Exception as e:  # noqa: BLE001
            probs.append(f"{tid}: structured data {e}")
        if "555-01" not in html.replace("(555) 01", "555-01") or "example.com" not in html:
            probs.append(f"{tid}: sample contact is not the fictional 555-01xx / example.com")
        for sec in ("services", "about", "faq", "visit", "contact", "reviews"):
            if f'id="{sec}"' not in html:
                probs.append(f"{tid}: no #{sec}")
        if "Paste a real review" not in html:
            probs.append(f"{tid}: review placeholders must ask for real reviews")
        if len(html) > 80_000:
            probs.append(f"{tid}: {len(html)} bytes")
    check("d. every template: phone viewport, a tap-to-call link, structured data, all sections, real-review placeholders, nothing loaded from outside, < 80 KB",
          not probs, probs)
    specials = {tid: SD.THEMES[tid]["special"] for tid in SD.ORDER}
    marks = {"steps": 'class="steps"', "seasons": 'class="seasons"', "menu": 'class="boards"', "prices": 'class="items pricelist"'}
    check("d. each template has its own section (steps, seasons, menu board, price list x2)", all(marks[s] in pages[t] for t, s in specials.items()), specials)


# ------------------------------------------------------------------------------------------------ e. social kit
def part_e():
    from money_machines.products import social_kit_data as SK
    B = mod("social_kit")
    app = open(B.APP, encoding="utf-8").read()
    check("e. the Post Maker is current (a fresh build gives the same file)", app == B.app_html())
    csp = re.search(r'http-equiv="Content-Security-Policy" content="([^"]+)"', app)
    check("e. the Post Maker allows no network: CSP default-src 'none'; no fetch, XHR, beacon, socket or remote font",
          csp and "default-src 'none'" in csp.group(1) and not re.search(r"\bfetch\(|XMLHttpRequest|sendBeacon|WebSocket|EventSource|@font-face|import\(", app))
    days = SK.DAYS
    layouts_used = {d["layout"] for d in days}
    check(f"e. 30 days, every design exists, all 12 designs used ({len(layouts_used)})", len(days) == 30 and layouts_used <= set(SK.LAYOUTS) and len(SK.LAYOUTS) == 12
          and layouts_used == set(SK.LAYOUTS), sorted(set(SK.LAYOUTS) - layouts_used))
    bank = SK.bank()
    texts = [b["text"] for b in bank]
    tags_ok = all(len(re.findall(r"(?<![\w&])#\[?\w", t)) <= 5 for t in texts)
    check(f"e. caption bank: 150 unique captions in 13 groups, each <= 2,200 chars and <= 5 hashtags",
          len(bank) == 150 and len(set(texts)) == 150 and len({b["cat"] for b in bank}) == 13 and all(len(t) <= 2200 for t in texts) and tags_ok)
    rv = [d for d in days if "review" in (d["theme"] + d["caption"]).lower()]
    check("e. every review post carries the real-reviews rule; no review is ever traded for a reward",
          rv and all("real reviews" in d["rule"] for d in rv) and not re.search(r"review[^.]{0,60}(?:discount|free|reward|prize|chance to win)",
                                                                                  " ".join(texts).lower().replace("never offer anything", "")))
    check("e. every day has alt text, a tip and a caption that ends with the hashtag line", all(d["alt"] and d["tip"] and d["caption"].endswith(SK.TAGS) for d in days))
    bad = []
    for p in SK.PALETTES:
        for a, b, need in SK.CONTRAST:
            r = _contrast(p[a], p[b])
            if r < need:
                bad.append((p["id"], a, b, round(r, 2)))
    check("e. the 8 colour looks: text >= 4.5:1, large accent shapes >= 3:1", not bad, bad)
    rows = open(os.path.join(buyer("social_kit"), "30_Day_Plan.csv"), encoding="utf-8-sig").read().splitlines()
    import csv as _csv
    parsed = list(_csv.reader(rows))
    check("e. 30_Day_Plan.csv: a header + 30 days in order, placeholders shown as [brackets]",
          len(parsed) == 31 and [r[0] for r in parsed[1:]] == [str(i) for i in range(1, 31)] and "{name}" not in "\n".join(rows))
    sheet = os.path.join(buyer("social_kit"), "All_30_Designs.jpg")
    check("e. the contact sheet of all 30 designs is a JPEG under 900 KB", os.path.exists(sheet) and K.jpeg_size(sheet)[0] > 1000 and os.path.getsize(sheet) < 900 * 1024)


# ------------------------------------------------------------------------------------------------ f. agency kit
def part_f():
    from openpyxl import load_workbook

    from money_machines.products import agency_kit_data as AK
    d = buyer("agency_kit")
    agr, _ = K.ooxml_text(os.path.join(d, "04_Service_Agreement.docx"))
    check("f. the service agreement says NOT LEGAL ADVICE and to have a lawyer review it, in the document itself", "NOT LEGAL ADVICE" in agr and "lawyer" in agr)
    lic = open(os.path.join(d, "LICENSE.txt"), encoding="utf-8").read()
    lst = "\n".join(listing("agency_kit")["description"]) + json.dumps(listing("agency_kit")["faq"])
    check("f. the licence and the listing also say the legal templates are not legal advice", "NOT LEGAL ADVICE" in lic and "not legal advice" in lst.lower())
    out, _ = K.ooxml_text(os.path.join(d, "01_Outreach_Scripts.docx"))
    check("f. outreach follows the email rules: an opt-out line and a postal address in every email footer; no autodialers; no cold texts",
          out.count("your postal address") >= 3 and "won't email you again" in out and "No autodialers" in out and "CAN-SPAM" in out)
    rv, _ = K.ooxml_text(os.path.join(d, "06_Reviews_and_Referrals.docx"))
    check("f. the reviews document bans rewards, gating, fake and suppressed reviews", all(w in rv for w in ("Never offer", "not only the happy ones", "Never write reviews", "suppress")))
    no_title = []
    for fname, doc in AK.DOCS:
        t, _ = K.ooxml_text(os.path.join(d, fname))
        if doc["title"].split("[")[0].strip()[:20] not in t:
            no_title.append(fname)
    check("f. 7 documents open as .docx and hold their titles", len(AK.DOCS) == 7 and not no_title, no_title)
    wf, wv = load_workbook(os.path.join(d, "Invoice_Template.xlsx")), load_workbook(os.path.join(d, "Invoice_Template.xlsx"), data_only=True)
    inv, invv = wf["Invoice"], wv["Invoice"]
    labels = {inv.cell(row=r, column=3).value: r for r in range(20, 40)}
    tr, br = labels.get("TOTAL"), labels.get("BALANCE DUE")
    check("f. the invoice keeps formulas (amount = qty x rate, total, balance) and its cached example adds up: 1 x 600 + 1 x 120 = 720",
          tr and str(inv.cell(row=tr, column=4).value).startswith("=") and str(inv["D15"].value).startswith("=")
          and invv.cell(row=tr, column=4).value == 720 and invv.cell(row=br, column=4).value == 720, (tr, br))
    tf, tv = load_workbook(os.path.join(d, "Agency_Tracker.xlsx")), load_workbook(os.path.join(d, "Agency_Tracker.xlsx"), data_only=True)
    pv = tv["Pricing"]
    prices = {pv.cell(row=r, column=1).value: [pv.cell(row=r, column=j).value for j in (2, 3, 4)] for r in range(8, 30)}
    sp = prices.get("SUGGESTED PRICE ($)")
    check("f. the tracker: tabs, status list, DUE formula, dashboard; pricing by hand: Starter 8.5 h x $50 x 1.15 = $488.75 -> $490",
          tf.sheetnames == ["Start here", "Dashboard", "Prospects", "Pricing", "Invoices", "Lists"] and sp and sp[0] == 490
          and str(tf["Prospects"]["N5"].value).startswith("=IF(AND(L5") and tv["Dashboard"]["B3"].value == 3, (tf.sheetnames, sp))


# ------------------------------------------------------------------------------------------------ g. trader planner
def part_g():
    from openpyxl import load_workbook
    B = mod("trader_planner")
    d = buyer("trader_planner")
    try:
        from pypdf import PdfReader
    except Exception:
        PdfReader = None
    if PdfReader:
        sizes = {}
        for size, (wmm, hmm) in B.SIZES.items():
            r = PdfReader(os.path.join(d, f"Trader_Planner_{size}.pdf"))
            box = r.pages[0].mediabox
            sizes[size] = (len(r.pages), round(float(box.width) / 72 * 25.4), round(float(box.height) / 72 * 25.4))
        check(f"g. the planner PDFs: 16 pages each, US Letter 216 x 279 mm and A4 210 x 297 mm ({sizes})",
              sizes.get("Letter") == (16, 216, 279) and sizes.get("A4") == (16, 210, 297), sizes)
    else:
        print("[SKIP] g. PDF page count and size: pypdf is not installed")
    check("g. 16 page designs in the source, each with a name", len(B.pages()) == 16 and all(n and html for n, html in B.pages()))
    wf, wv = load_workbook(B.JOURNAL), load_workbook(B.JOURNAL, data_only=True)
    db = {wv["Dashboard"].cell(row=r, column=1).value: wv["Dashboard"].cell(row=r, column=2).value for r in range(3, 25)}
    check("g. the journal keeps formulas and computed the 3 example days: 3 days, routine 2 of 3, average grade B, streak 0, rule 1 broken once",
          wf.sheetnames == ["Start here", "Dashboard", "Daily", "Rules", "Rule breaks", "Routine", "Weekly"]
          and str(wf["Daily"]["M5"].value).startswith("=") and db.get("Days journaled") == 3 and abs((db.get("Routine done (share of days)") or 0) - 2 / 3) < 1e-6
          and db.get("Average process grade") == "B" and db.get("Current routine streak (days in a row)") == 0 and wv["Rules"]["D5"].value == 1, db)
    check("g. the example rows show no profit or loss (the optional result column is empty)", all(wv["Daily"].cell(row=r, column=11).value in (None, "") for r in range(5, 8)))
    risk = "substantial risk of loss"
    texts = [open(os.path.join(d, f), encoding="utf-8").read() for f in ("README.txt", "LICENSE.txt")] + ["\n".join(listing("trader_planner")["description"])]
    check("g. the risk line is in the readme, the licence and the listing; 'not financial advice' in the listing FAQ",
          all(risk in t for t in texts) and "No." in json.dumps(listing("trader_planner")["faq"]))
    words = re.compile(r"\b(buy|sell) signals?\b|\bwin rate\b|\bprofit target\b|\bentry signal from us\b", re.I)
    allt = "\n".join(K.file_text(os.path.join(d, f))[0] for f in K.buyer_files(d))
    check("g. no signal, win-rate or profit-target wording anywhere in the planner files", not words.search(allt), words.findall(allt)[:3])


# ------------------------------------------------------------------------------------------------ h. catalogue, docs, area, size
def part_h():
    cat = json.load(open(os.path.join(ROOT, "money_machines", "products", "catalog.json"), encoding="utf-8"))
    pr = cat["products"]
    check("h. the catalogue: 5 built products (the tracker + these 4), each with price, files, the zip command and platforms",
          len(pr) == 5 and all(p["status"] == "built" for p in pr) and all(p.get("build", "").endswith("--zip") and p.get("files") and p["price_usd"] > 0 and p["platforms"] for p in pr)
          and {p["id"] for p in pr} >= set(CATALOG_ID.values()))
    folded = {f["id"] for f in cat.get("folded", [])}
    check("h. the two weaker ideas are folded in with a reason (Google-profile checklist, review request kit -> the agency kit)",
          folded == {"gbp-checklist-kit", "review-request-kit"} and all(f.get("into") and f.get("why") for f in cat["folded"]))
    doc = open(os.path.join(ROOT, "docs", "MONEY_MACHINES.md"), encoding="utf-8").read()
    check("h. docs/MONEY_MACHINES.md lists every product's zip command and price", all(f"python -m {m} --zip" in doc for m in PRODUCTS.values())
          and all(f"${listing(n)['price_usd']}" in doc for n in PRODUCTS))
    ra = open(os.path.join(ROOT, "tests", "run_area.py"), encoding="utf-8").read()
    m = re.search(r'"money":\s*\[([^\]]*)\]', ra)
    check("h. tests/run_area.py runs this suite in the money area", m and '"digital_products"' in m.group(1) and '"money_machines"' in m.group(1))
    total = 0
    for name in PRODUCTS:
        for base, _, files in os.walk(prod_dir(name)):
            total += sum(os.path.getsize(os.path.join(base, f)) for f in files)
    check(f"h. the 4 product folders stay small: {total / 1e6:.1f} MB (< 15 MB)", total < 15e6, total)
    tracked = subprocess.run(["git", "ls-files", "money_machines/out"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    check("h. no zip or output is committed (money_machines/out is ignored)", tracked == "", tracked[:200])


PARTS = {"a": part_a, "b": part_b, "c": part_c, "d": part_d, "e": part_e, "f": part_f, "g": part_g, "h": part_h}


def main(argv=None):
    want = (argv or sys.argv[1:]) or list(PARTS)
    for k in want:
        PARTS[k]()
    check("no network was touched by any part", not NET_TRIES, NET_TRIES[:3])
    print(f"\n{sum(RES)}/{len(RES)} passed")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
