"""AGENCY BILLING (agency/billing/, team B6 "get paid", 2026-11-14): close and collect for the website agency. Checks:
  a. invoice numbers never repeat: one sequence over voids, a hand-edited or deleted invoices.json (the backup and the invoice files on
     disk still count), a new year, a raised start number, 4 processes issuing at once; a damaged file is refused, untouched; the lock
  b. the money: line amounts, tax half-up on taxable lines only, discounts, paid / balance, a total below $0 refused, the item syntax,
     and the invoice page shows the same totals
  c. the documents render offline: no script / style / font / image from the network, everything escaped, only http(s) / mailto / tel
     links; the agreement says template + not legal advice; in Chromium (network blocked) nothing is fetched, the proposal and the
     invoice print on ONE Letter page, nothing is wider than a 390 px phone, and to_pdf() writes a PDF with a headless Chromium
  d. MRR and churn on the fixture ledger by hand (new, churn on the last day, expansion, contraction across a month end,
     reactivation, a plan inside one month, a future plan), the identity start + moves = end every month, churn %, goal, cash by
     month, the daily rows, junk and future rows skipped; no client name, id, email or phone in the summary
  e. the money scoreboard hook (tools/money_scoreboard.py): agency cash counted with --private / publish, private otherwise, a sample
     never, the owner's own "agency" ledger entries win (no double count), ROI on eval fees untouched, "off" when there is no file
  f. the command line end to end in a temp folder: setup, kit, paid (+ the plan starts), plan change / cancel, a Stripe-style CSV
     import (twice: no duplicates), void, summary, demo; bad input stops with exit 2 and changes nothing; the repo's data/agency untouched
  g. hygiene: data/agency/ gitignored (+ its own .gitignore), no network module, no secret, subprocess only for the PDF
    python -X utf8 -m tests.test_agency_billing          (AB_NO_BROWSER=1 skips the Chromium part of c; run that part under the shared
    lock on a busy machine: flock -w 2400 /tmp/olympus_browser.lock python -X utf8 -m tests.test_agency_billing)
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from agency.billing import core as C  # noqa: E402
from agency.billing import render as R  # noqa: E402
from agency.billing import store as S  # noqa: E402
from tools import money_scoreboard as MS  # noqa: E402

FIX = os.path.join(ROOT, "agency", "billing", "fixtures")
RES = []
NOW = 1794762000          # 2026-11-15 17:00 UTC = Sunday 12:00 ET (the money scoreboard tests' clock)
TMP = tempfile.mkdtemp(prefix="agency_billing_")
REPO_DATA = os.path.join(ROOT, "data", "agency")
REPO_DATA_BEFORE = sorted(os.listdir(REPO_DATA)) if os.path.isdir(REPO_DATA) else None


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:700]}"), flush=True)


def near(a, b, tol=0.005):
    return a is not None and b is not None and abs(float(a) - float(b)) <= tol


def load(name):
    with open(os.path.join(FIX, name), encoding="utf-8") as fh:
        return json.load(fh)


def fresh(name) -> S.Store:
    d = os.path.join(TMP, name)
    shutil.rmtree(d, ignore_errors=True)
    return S.Store(d)


def draft(total=99.0):
    return {"client_id": "c1", "lines": [C.make_line("Plan", 1, total)], **C.totals([C.make_line("Plan", 1, total)])}


def raises(fn, exc=Exception, text=""):
    try:
        fn()
    except exc as e:
        return text.lower() in str(e).lower()
    return False


# ------------------------------------------------------------------------------------------------ a. numbering
def part_a():
    st = fresh("num")
    nos = [st.issue(draft(), "2026-11-14")["no"] for _ in range(5)]
    check("a. five invoices: INV-2026-0001 .. 0005, in order, no repeat", nos == [f"INV-2026-{i:04d}" for i in range(1, 6)], nos)
    st.void("INV-2026-0003", "typo")
    n6 = st.issue(draft(), "2026-11-14")
    check("a. a voided number is never reused: the next is 0006, the void keeps its number and says void",
          n6["seq"] == 6 and st.find_invoice("INV-2026-0003")["status"] == "void", (n6["no"], st.find_invoice("INV-2026-0003")))
    check("a. invoices.json.bak is a copy of the last good state (same content after every change)",
          open(st.inv_path, "rb").read() == open(st.inv_path + ".bak", "rb").read())
    doc = json.load(open(st.inv_path, encoding="utf-8"))
    doc["invoices"], doc["last"] = doc["invoices"][:2], 0                         # a hand edit that "resets" the counter
    json.dump(doc, open(st.inv_path, "w", encoding="utf-8"))
    os.remove(st.inv_path + ".bak")
    n7 = st.issue(draft(), "2026-11-14")
    check("a. a hand-edited invoices.json (last = 0, invoices removed) and no backup: the high-water mark invoices.last still counts, the next is 0007",
          n7["seq"] == 7 and open(st.counter_path).read().strip() == "7", n7["no"])
    os.makedirs(st.inv_dir, exist_ok=True)
    for f in ("INV-2026-0007.html", "INV-2026-0007.pdf", "notes.html"):
        open(os.path.join(st.inv_dir, f), "w").write("x")
    for f in (st.inv_path, st.inv_path + ".bak", st.counter_path):
        os.remove(f)
    n8 = st.issue(draft(), "2026-11-14")
    check("a. invoices.json, its backup AND invoices.last deleted: the invoice files on disk still count, the next is 0008", n8["seq"] == 8, n8["no"])
    shutil.rmtree(st.inv_dir)
    os.remove(st.counter_path)
    json.dump({"v": 1, "kind": "agency-invoices", "last": 0, "invoices": []}, open(st.inv_path, "w", encoding="utf-8"))
    n8b = st.issue(draft(), "2026-11-14")
    check("a. only the backup copy left (counter and invoice files gone, invoices.json emptied by hand): it still counts, the next is 0009", n8b["seq"] == 9, n8b["no"])
    open(st.counter_path, "w").write("seven")
    check("a. a damaged invoices.last is refused with a plain message (never guessed)", raises(lambda: st.issue(draft(), "2026-11-14"), S.StoreError, "invoices.last"))
    open(st.counter_path, "w").write("9\n")
    n9 = st.issue(draft(), "2027-01-02")
    check("a. a new year: the year in the number changes, the sequence does not reset (INV-2027-0010)", n9["no"] == "INV-2027-0010", n9["no"])
    n10 = st.issue(draft(), "2027-01-02", start_at=1001)
    n11 = st.issue(draft(), "2027-01-02", start_at=1)
    check("a. a start number only moves numbers up (1001), lowering it again never goes back (1002)", (n10["seq"], n11["seq"]) == (1001, 1002), (n10["no"], n11["no"]))
    allno = [i["no"] for i in json.load(open(st.inv_path, encoding="utf-8"))["invoices"]]
    check("a. every number handed out in this file is different", len(allno) == len(set(allno)), allno)
    check("a. a bad prefix is refused", raises(lambda: st.issue(draft(), "2027-01-02", prefix="inv1"), S.StoreError, "prefix"))
    raw = open(st.inv_path, "rb").read()
    open(st.inv_path, "w").write("{broken")
    bad = open(st.inv_path, "rb").read()
    check("a. a damaged invoices.json is refused (no guessing) with a plain message, and left exactly as it was",
          raises(lambda: st.issue(draft(), "2027-01-02"), S.StoreError, "damaged") and open(st.inv_path, "rb").read() == bad)
    open(st.inv_path, "wb").write(raw)
    # the lock
    st.LOCK_TIMEOUT = 0.3
    lk = os.path.join(st.root, ".lock")
    open(lk, "w").write("123")
    check("a. while another command holds the lock, a second one waits and then stops with a plain message", raises(lambda: st.issue(draft(), "2027-01-02"), S.StoreError, "running"))
    old = time.time() - 600
    os.utime(lk, (old, old))
    n12 = st.issue(draft(), "2027-01-02")
    check("a. a lock left by a crashed command (10 minutes old) is cleared and the number continues (1003)", n12["seq"] == 1003 and not os.path.exists(lk), n12["no"])
    # 4 processes at once
    st2 = fresh("race")
    st2.ensure()
    code = ("import sys; sys.path.insert(0, {root!r}); from agency.billing import store as S, core as C\n"
            "st = S.Store({d!r})\n"
            "for _ in range(10): st.issue({{'client_id': 'x', 'lines': [], 'total_usd': 1.0}}, '2026-11-14')\n").format(root=ROOT, d=st2.root)
    procs = [subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, stderr=subprocess.PIPE) for _ in range(4)]
    errs = [p.communicate(timeout=120)[1].decode()[-300:] for p in procs]
    d2 = json.load(open(st2.inv_path, encoding="utf-8"))
    seqs = [i["seq"] for i in d2["invoices"]]
    check("a. 4 processes x 10 invoices at once: 40 invoices, 40 different numbers 1..40, last = 40, the file is valid JSON",
          all(p.returncode == 0 for p in procs) and sorted(seqs) == list(range(1, 41)) and len(set(i["no"] for i in d2["invoices"])) == 40 and d2["last"] == 40,
          (sorted(seqs)[:5], len(seqs), errs))


# ------------------------------------------------------------------------------------------------ b. the money
def part_b():
    lines = [C.make_line("Website plan", 3, "99.99"), C.make_line("Discount", 1, -10, taxable=False)]
    t = C.totals(lines, 7.25, paid=100)
    check("b. 3 x $99.99 + a $10 untaxed discount at 7.25% tax: subtotal $289.97, tax $21.75 (on $299.97, half-up), total $311.72, balance $211.72",
          (t["subtotal_usd"], t["taxable_usd"], t["tax_usd"], t["total_usd"], t["paid_usd"], t["balance_usd"]) == (289.97, 299.97, 21.75, 311.72, 100.0, 211.72), t)
    check("b. half-up to the cent (5% of $0.10 = $0.01, not $0.00) and no float drift (3 x $0.10 = $0.30)",
          C.totals([C.make_line("x", 1, "0.10")], 5)["tax_usd"] == 0.01 and C.totals([C.make_line("x", 1, 0.1)] * 3)["subtotal_usd"] == 0.3)
    check("b. a $0 setup line + $149 a month: total $149.00, nothing taxed when the rate is 0",
          C.totals([C.make_line("Website setup: included", 1, 0), C.make_line("Growth plan", 1, 149)], 0)["total_usd"] == 149.0)
    check("b. refused: a total below $0, a quantity of 0, a tax rate above 25%, an empty description, a price that is not a number",
          raises(lambda: C.totals([C.make_line("Discount", 1, -50)]), ValueError, "below") and raises(lambda: C.make_line("x", 0, 5), ValueError)
          and raises(lambda: C.totals(lines, 30), ValueError) and raises(lambda: C.make_line("", 1, 5), ValueError) and raises(lambda: C.make_line("x", 1, "abc"), ValueError))
    items = [C.parse_item(s) for s in ("Extra page=50x2", "Discount=-25", "Domain renewal=15 notax", "Logo=$1,250.50")]
    check("b. --item syntax: 'Extra page=50x2' = 2 x $50, 'Discount=-25', 'Domain=15 notax' untaxed, '$1,250.50' read as money",
          [(i["desc"], i["qty"], i["amount_usd"], i["taxable"]) for i in items] == [("Extra page", 2.0, 100.0, True), ("Discount", 1.0, -25.0, True),
                                                                                     ("Domain renewal", 1.0, 15.0, False), ("Logo", 1.0, 1250.5, True)], items)
    check("b. money words: $1,234.50 / -$5.00 / +$5.00 / $0.00 / '-' / $1,235 (whole)",
          [C.usd(1234.5), C.usd(-5, True), C.usd(5, True), C.usd(0), C.usd(None), C.usd(1234.5, whole=True)] == ["$1,234.50", "-$5.00", "+$5.00", "$0.00", "-", "$1,235"])
    check("b. numbers from text: '$1,234.50' -> 1234.50, '(12.50)' -> -12.50, junk / bool / nan -> None",
          C.dec("$1,234.50") == C.dec("1234.50") and C.dec("(12.50)") == C.dec("-12.50") and C.dec("abc") is None and C.dec(True) is None and C.dec(float("nan")) is None)
    inv = {"no": "INV-2026-0042", "issued": "2026-11-14", "due": "2026-11-21", "period": "2026-11", "lines": lines, **t, "status": "open",
           "pay_link": "https://buy.stripe.com/test_abc"}
    h = R.invoice_html(inv, {"name": "Rivera Plumbing", "email": "o@rivera.example"}, S.fixture_business())
    check("b. the invoice page shows the same totals (subtotal, 7.25% tax, total, paid, balance) and the pay button with the link",
          all(x in h for x in ("$289.97", "Sales tax (7.25%)", "$21.75", "$311.72", "-$100.00", "$211.72", "INV-2026-0042"))
          and 'class="btn" href="https://buy.stripe.com/test_abc"' in h and "Pay $211.72 now" in h, re.findall(r"\$[\d,.]+", h)[:12])


# ------------------------------------------------------------------------------------------------ c. the documents, offline
EXTERNAL = re.compile(r"<(?:script|img|iframe|link|source|video|audio|embed|object)\b[^>]*\b(?:src|href|data)\s*=\s*[\"']?(?:https?:)?//", re.I)


def docs_for(client_id, accent=None):
    clients, pk, biz = S.fixture_clients(), S.Store.packages(), S.fixture_business()
    if accent:
        biz["accent"] = accent
    c = C.find_client(clients, client_id)
    pkg = C.plan_for(c, pk)
    lines = [C.make_line(f"Website setup ({pkg['name']} plan): included", 1, pkg["setup_usd"]), C.make_line(f"{pkg['name']} website plan, November 2026", 1, pkg["monthly_usd"])]
    inv = {"no": "INV-2026-0007", "issued": "2026-11-14", "due": "2026-11-21", "period": "2026-11", "lines": lines, **C.totals(lines), "status": "open",
           "pay_link": R.pay_link_for(biz, pkg["id"])}
    return c, pkg, {"proposal": R.proposal_html(c, pkg, biz, "2026-11-14"), "agreement": R.agreement_html(c, pkg, biz, "2026-11-14"),
                    "invoice": R.invoice_html(inv, c, biz)}


def part_c():
    c, pkg, d = docs_for("c_demo_northside")
    allh = "".join(d.values())
    check("c. offline: no script / image / font / stylesheet from the network, no @import, no url(), no web font, all CSS inline",
          not EXTERNAL.search(allh) and "@import" not in allh and "url(" not in allh and "@font-face" not in allh and "<link" not in allh
          and allh.count("<style>") >= 3, EXTERNAL.findall(allh)[:3])
    check("c. the proposal: client name (escaped &amp;), the plan, $0 setup + $249 a month, every item, the demo link, 3 steps, valid 14 days, sign line",
          "More calls for Northside Heating &amp; Air (sample)" in d["proposal"] and "Pro plan" in d["proposal"] and ">$0<" in d["proposal"] and ">$249<" in d["proposal"]
          and all(R.esc(x) in d["proposal"] for x in pkg["includes"]) and 'href="https://demo.example.com/northside-hvac"' in d["proposal"]
          and d["proposal"].count("<li><b>") == 3 and "Valid until November 28, 2026" in d["proposal"] and "Accepted for" in d["proposal"])
    ag = d["agreement"]
    check("c. the agreement is marked template + not legal advice on screen, in the footer and on every printed page (in the page's bottom margin)",
          "Template, not legal advice." in ag and ag.count(R.TEMPLATE_NOTE) >= 2 and '@bottom-center{content:"' + R.TEMPLATE_NOTE + '"' in ag
          and "@bottom-center" not in d["proposal"] + d["invoice"])
    check("c. plain words: '2 small content edits', '1 business day' (no 'edit(s)'), and a blank date line that keeps its period",
          "2 small content edits a month" in docs_for("c_demo_rivera")[2]["agreement"] and "1 business day." in ag and "(s)" not in ag.split("<body>")[1]
          and '<span class="nw"><span class="blank">' in ag)
    check("c. the agreement covers scope, the monthly plan, payment, cancellation, ownership of the site AND the domain, liability limits, governing law",
          all(x in ag for x in ("What we will do", "Price and payment", "Term and cancellation", "Who owns what", "Your domain name", "Limits of liability",
                                "$249 a month", "30 days notice", "3 months before the claim", "Buyout", "The laws of the State of")))
    check("c. the invoice: number, $0 setup line, the plan line, total $249.00, and the payment link in the 'Pay online' box",
          "INV-2026-0007" in d["invoice"] and "Website setup (Pro plan): included" in d["invoice"] and "$249.00" in d["invoice"]
          and 'href="https://pay.example.com/pro-249"' in d["invoice"] and "Pay online in a minute" in d["invoice"])
    evil = {"id": "x", "name": "<script>alert(1)</script> Lawn & Co", "trade": "<b>roofer</b>", "city": "\"Springfield\"", "email": "a@b.example",
            "demo_url": "javascript:alert(1)", "package": "starter", "phone": "555", "site_url": "", "status": "", "notes": "", "setup_usd": 0, "monthly_usd": 99}
    pkg2 = C.plan_for(evil, S.Store.packages())
    ph = R.proposal_html(evil, pkg2, {**S.fixture_business(), "website": "javascript:alert(2)", "pay_links": {"starter": "javascript:x"}}, "2026-11-14")
    ih = R.invoice_html({"no": "INV-2026-0001", "issued": "2026-11-14", "lines": [C.make_line("<img src=x onerror=alert(1)>", 1, 5)], **C.totals([C.make_line("y", 1, 5)]),
                         "pay_link": "javascript:alert(3)"}, evil, S.fixture_business())
    hrefs = re.findall(r'href="([^"]*)"', ph + ih)
    check("c. a hostile client record is escaped (<script>, <b>, quotes) and a javascript: link is never a link (demo, website, payment)",
          "<script>alert" not in ph + ih and "&lt;script&gt;" in ph and "&lt;b&gt;roofer" in ph and "&lt;img src=x" in ih and "&quot;Springfield&quot;" in ph
          and hrefs and not any(h.lower().startswith(("javascript", "data")) for h in hrefs), hrefs)
    check("c. safe_url: http(s), mailto and tel pass; javascript:, data:, a relative path, spaces and quotes do not",
          [bool(R.safe_url(u)) for u in ("https://a.example/x", "http://a.example", "mailto:a@b.example", "tel:+15550100", "javascript:alert(1)", "data:text/html,x", "/etc/passwd", "https://a b.example", "https://a.example/\"x")]
          == [True, True, True, True, False, False, False, False, False])
    light = R.colours("#ffe066")
    check("c. a pale brand colour gets dark text on its band (readable), a dark one white", light["on"] != "#ffffff" and R.colours("#1f5f55")["on"] == "#ffffff", light)
    if os.environ.get("AB_NO_BROWSER") == "1":
        print("SKIP: c. browser part (AB_NO_BROWSER=1)")
        return
    try:
        from playwright.sync_api import sync_playwright
        from tests import browser_kit as BK
    except Exception as e:  # noqa: BLE001
        print(f"SKIP: c. browser part (no Playwright: {e.__class__.__name__})")
        return
    out = os.path.join(TMP, "pages")
    os.makedirs(out, exist_ok=True)
    files = {}
    for cid in ("c_demo_northside", "c_demo_rivera", "c_demo_greenway"):
        _, _, dd = docs_for(cid)
        for k, v in dd.items():
            files[f"{cid}-{k}"] = R.write(os.path.join(out, f"{cid}-{k}.html"), v)
    pages, blocked, wide = {}, [], {}
    with sync_playwright() as pw:
        br = BK.launch(pw)
        ctx = br.new_context(viewport={"width": 1100, "height": 1400})
        ctx.route("**/*", lambda route: route.continue_() if route.request.url.startswith("file:") else (blocked.append(route.request.url), route.abort()))
        pg = ctx.new_page()
        for k, f in files.items():
            pg.goto("file://" + f)
            pdf = pg.pdf(format="Letter", print_background=True, prefer_css_page_size=True)
            pages[k] = len(re.findall(rb"/Type\s*/Page[^s]", pdf))
        ctx.close()
        ph_ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1)
        ph_ctx.route("**/*", lambda route: route.continue_() if route.request.url.startswith("file:") else (blocked.append(route.request.url), route.abort()))
        pp = ph_ctx.new_page()
        for k, f in files.items():
            pp.goto("file://" + f)
            wide[k] = pp.evaluate("document.documentElement.scrollWidth")
        ph_ctx.close()
    check("c. Chromium with the network blocked: the 9 pages load and ask for nothing outside the file", not blocked and len(pages) == 9, blocked[:5])
    check("c. every proposal (Starter, Growth, Pro; the longest name) and every invoice prints on ONE Letter page",
          all(v == 1 for k, v in pages.items() if k.endswith(("-proposal", "-invoice"))), pages)
    check("c. the agreement prints on more than one page (it is the long one) and at most 4", all(2 <= v <= 4 for k, v in pages.items() if k.endswith("-agreement")), pages)
    check("c. at phone width (390 px) no page is wider than the screen", all(v <= 390 for v in wide.values()), wide)
    exe = BK.chrome_exe() if hasattr(BK, "chrome_exe") else None
    if exe:
        pdf, msg = R.to_pdf(files["c_demo_rivera-invoice"], os.path.join(out, "inv.pdf"), browser=exe)
        ok = bool(pdf) and open(pdf, "rb").read(5) == b"%PDF-"
        check("c. to_pdf(): a headless Chromium (the same flags Edge / Chrome take) writes a real PDF next to the page", ok, msg)
    nob, msg = R.to_pdf(files["c_demo_rivera-invoice"], os.path.join(out, "none.pdf"), browser=os.path.join(TMP, "no-such-browser"))
    check("c. to_pdf() without a browser: no crash, the plain 'Print > Save as PDF' advice", nob is None and "Save as PDF" in msg, msg)


# ------------------------------------------------------------------------------------------------ d. MRR and churn
def part_d():
    led = load("ledger.json")
    s = C.summary(led, None, "2026-12-14", NOW + 29 * 86400)
    m = {x["month"]: x for x in s["months"]}
    want = {"2026-09": (0, 248, 248, 0, 0, 0, 0), "2026-10": (248, 248, 149, 0, 0, 0, 149), "2026-11": (248, 597, 249, 0, 100, 0, 0),
            "2026-12": (597, 596, 0, 99, 0, 100, 0)}
    got = {k: (v["mrr_start"], v["mrr_end"], v["new"], v["reactivation"], v["expansion"], v["contraction"], v["churned"]) for k, v in m.items()}
    check("d. by hand: Sep new $248; Oct churn $149 (plan ended on Oct 31) + new $149; Nov expansion $100 + new $249; Dec reactivation $99, contraction $100",
          got == {k: tuple(float(x) for x in v) for k, v in want.items()}, got)
    check("d. the identity holds every month: start + new + reactivation + expansion - contraction - churn = end, and each start = the month before's end",
          all(near(x["mrr_start"] + x["new"] + x["reactivation"] + x["expansion"] - x["contraction"] - x["churned"], x["mrr_end"]) for x in s["months"])
          and all(near(a["mrr_end"], b["mrr_start"]) for a, b in zip(s["months"], s["months"][1:])))
    check("d. churn %: Oct logo 50% (1 of 2) and MRR 60.08% ($149 / $248); Nov 0% and net -40.32% (expansion); Dec MRR 16.75% (contraction $100 / $597); Sep none (no clients yet)",
          (m["2026-10"]["logo_churn_pct"], m["2026-10"]["mrr_churn_pct"], m["2026-11"]["logo_churn_pct"], m["2026-11"]["net_mrr_churn_pct"], m["2026-12"]["mrr_churn_pct"], m["2026-09"]["logo_churn_pct"])
          == (50.0, 60.08, 0.0, -40.32, 16.75, None), [(k, v["logo_churn_pct"], v["mrr_churn_pct"], v["net_mrr_churn_pct"]) for k, v in m.items()])
    check("d. a plan that starts and ends inside October ($99, Oct 15-25) moves nothing; a plan change on Dec 1 is a contraction, not churn + new",
          m["2026-10"]["new_clients"] == 1 and m["2026-12"]["churned_clients"] == 0 and m["2026-12"]["reactivated_clients"] == 1 and m["2026-12"]["partial"] is True)
    mr, g = s["mrr"], s["goal"]
    check("d. now (Dec 14): MRR $596 from 4 clients ($149 average), ARR $7,152; $99 signed to start Dec 20 (not counted yet), $99 cancelling Dec 31",
          (mr["now"], mr["clients"], mr["arpa"], mr["arr"], mr["scheduled_usd"], mr["scheduled_clients"], mr["ending_usd"]) == (596.0, 4, 149.0, 7152.0, 99.0, 1, 99.0), mr)
    check("d. goal $1,000 MRR: $404 to go = about 3 more clients at $149, 59.6% of the way", (g["left"], g["clients_needed"], g["pct"], g["reached"]) == (404.0, 3, 59.6, False), g)
    cash = [(x["month"], x["cash_in"], x["refunds"], x["fees"], x["cash_net"]) for x in s["months"]]
    check("d. cash by month: Sep $248 in / $9.52 fees; Oct $496 in, a $50 refund, $19.04 fees = $426.96; Nov $597 / $22.68; Dec $596 / $22.64",
          cash == [("2026-09", 248.0, 0.0, 9.52, 238.48), ("2026-10", 496.0, 50.0, 19.04, 426.96), ("2026-11", 597.0, 0.0, 22.68, 574.32), ("2026-12", 596.0, 0.0, 22.64, 573.36)], cash)
    a = s["cash"]["all"]
    check("d. all time: $1,937 in, $123.88 out (refund + fees), net $1,813.12; this week (Mon Dec 14) nothing yet; this month $573.36",
          (a["in"], a["out"], a["net"], s["cash"]["week"]["in"], s["cash"]["week"]["from"], s["cash"]["month"]["net"]) == (1937.0, 123.88, 1813.12, 0.0, "2026-12-14", 573.36), s["cash"])
    check("d. the daily rows add up to the same cash (the scoreboard hook reads these)",
          near(sum(d[1] for d in s["days"]), a["in"]) and near(sum(d[2] for d in s["days"]), a["out"]) and s["days"][0] == ["2026-09-05", 99.0, 3.86])
    led2 = json.loads(json.dumps(led))
    led2["plans"] += [{"client_id": "z", "monthly_usd": -5, "start": "2026-10-01"}, {"client_id": "z", "monthly_usd": 50, "start": "2026-10-05", "end": "2026-10-01"}, "junk"]
    led2["payments"] += [{"date": "2026-12-30", "client_id": "z", "amount_usd": 500, "kind": "monthly"}, {"date": "nope", "amount_usd": 5}, {"date": "2026-11-01", "amount_usd": 5, "kind": "gift"}]
    s2 = C.summary(led2, None, "2026-12-14", NOW)
    check("d. junk is skipped and counted (a negative plan, an end before the start, a bad date, an unknown kind); a future-dated payment is ignored",
          s2["counts"]["plans_skipped"] == 3 and s2["counts"]["payments_skipped"] == 2 and s2["counts"]["future_payments_ignored"] == 1 and s2["mrr"] == s["mrr"]
          and s2["cash"]["all"] == s["cash"]["all"], s2["counts"])
    blob = json.dumps(s)
    pii = [x for c in S.fixture_clients() for x in (c["name"], c["id"], c["email"], c["phone"]) if x and x in blob]
    check("d. the summary has NO client name, id, email or phone (aggregates only) and says so", not pii and "Aggregates only" in blob, pii)
    check("d. the summary's shape: kind olympus-agency-income, v 1, built / t, private, publish false, a headline with $ a month",
          s["kind"] == "olympus-agency-income" and s["v"] == 1 and s["private"] is True and s["publish"] is False and s["headline"]["usd_month"] == 596.0
          and s["built"].endswith("Z") and "MRR $596" in s["text"])
    e = C.summary({}, None, "2026-11-14", NOW)
    check("d. an empty ledger: MRR $0, goal 7 clients at the default $149, no months, no crash", e["mrr"]["now"] == 0 and e["goal"]["clients_needed"] == 7 and e["months"] == [], e["goal"])


# ------------------------------------------------------------------------------------------------ e. the money scoreboard hook
def part_e():
    led = load("ledger.json")
    ag = C.summary(led, None, "2026-11-15", NOW)
    rules = json.load(open(os.path.join(ROOT, "tools", "web_public", "ledger", "rules.json"), encoding="utf-8"))
    base = {"home": None, "kalshi": None, "machines": None, "rules": rules, "plans": None, "ledger": None}
    priv = MS.build({**base, "agency": ag}, NOW, include_ledger=True)
    pub = MS.build({**base, "agency": ag}, NOW, include_ledger=False)
    off = MS.build(base, NOW, include_ledger=True)
    src = lambda sb: next((x for x in sb["sources"] if x["id"] == "agency"), {})  # noqa: E731
    row = lambda sb: next((r for r in sb["by_source"] if r["id"] == "agency"), None)  # noqa: E731
    T = priv["totals"]
    check("e. --private: the agency's cash is real cash in the totals: all time $1,239.76 - $134.80 eval fees = $1,104.96; week (Nov 9-15) +$96.10; month +$574.32",
          near(T["all"]["net"], 1104.96) and near(T["week"]["net"], 96.10) and near(T["month"]["net"], 574.32) and near(off["totals"]["all"]["net"], -134.8), (T, off["totals"]["all"]))
    r = row(priv)
    check("e. its own row: Website agency, group cash, net $1,239.76, this week $96.10, MRR $597 from 3 clients; the source is ok",
          r and r["group"] == "cash" and near(r["net"], 1239.76) and near(r["week"], 96.10) and r["mrr"] == 597.0 and r["clients"] == 3 and src(priv)["status"] == "ok", (r, src(priv)))
    check("e. ROI on eval fees is untouched by agency income (fees $134.80, back $0, -100%)", priv["roi"] == off["roi"] and priv["roi"]["fees"] == 134.8 and priv["roi"]["back"] == 0, priv["roi"])
    check("e. the public copy (no --private): no agency money, the source says private, no agency figure in the file",
          pub["totals"] == off["totals"] and row(pub) is None and src(pub)["status"] == "private" and "1,239" not in json.dumps(pub) and "1239" not in json.dumps(pub), src(pub))
    pubok = MS.build({**base, "agency": {**ag, "publish": True}}, NOW, include_ledger=False)
    check("e. ... unless the owner chose to publish it (python -m agency.billing setup --publish yes): then it counts", near(pubok["totals"]["all"]["net"], 1104.96))
    samp = MS.build({**base, "agency": {**ag, "status": "sample"}}, NOW, include_ledger=True)
    check("e. a sample file is never counted as cash", samp["totals"] == off["totals"] and src(samp)["status"] == "sample")
    own = {"state": "ok", "entries": [MS.clean_entry({"kind": "income", "amount": 500, "date": "2026-11-12", "acct": "agency"})], "hidden": [], "publish": False, "t": NOW - 60}
    both = MS.build({**base, "agency": ag, "ledger": own}, NOW, include_ledger=True)
    check("e. the owner's own ledger entries for acct 'agency' win: $500 counted, the kit's rows not (no double count), one agency row",
          near(both["totals"]["all"]["net"], 500 - 134.8) and [x["id"] for x in both["by_source"]].count("agency") == 1 and near(row(both)["net"], 500)
          and "no double count" in src(both)["note"], (both["totals"]["all"], src(both)))
    check("e. no agency file: the source is 'off' (not started), never listed missing; junk or another kind of file is the same",
          src(off)["status"] == "off" and "agency" not in [x["id"] for x in off["missing"]]
          and src(MS.build({**base, "agency": {"kind": "other", "days": [["2026-11-01", 999, 0]]}}, NOW, True))["status"] == "off")
    stale = MS.build({**base, "agency": {**ag, "built": "2026-09-01T00:00:00Z"}}, NOW, include_ledger=True)
    check("e. a summary older than 35 days is shown as stale (still counted: the money did move)", src(stale)["status"] == "stale" and near(stale["totals"]["all"]["net"], 1104.96), src(stale))
    check("e. the printed table has the agency row", "Website agency (client payments)" in MS.table(priv))
    p = os.path.join(TMP, "agency.json")
    json.dump(ag, open(p, "w", encoding="utf-8"))
    g = MS.gather(site=os.path.join(TMP, "nosite"), ledger_path=os.path.join(TMP, "noledger.json"), agency_path=p)
    open(os.path.join(TMP, "other.json"), "w").write('{"kind": "nope"}')
    g2 = MS.gather(site=os.path.join(TMP, "nosite"), ledger_path=os.path.join(TMP, "noledger.json"), agency_path=os.path.join(TMP, "other.json"))
    check("e. gather() reads the summary from --agency FILE (default money_out/agency.json) and ignores a file of another kind",
          g["agency"] and g["agency"]["mrr"]["now"] == 597.0 and g2["agency"] is None and MS.AGENCY.endswith(os.path.join("money_out", "agency.json")))
    blob = json.dumps(priv)
    check("e. no client name or email reaches the scoreboard", not any(c["name"] in blob or c["email"] in blob for c in S.fixture_clients()))


# ------------------------------------------------------------------------------------------------ f. the command line
def run(args, env, ok=0):
    p = subprocess.run([sys.executable, "-X", "utf8", "-m", "agency.billing"] + args, cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
    return p.returncode, p.stdout + p.stderr


def part_f():
    d = os.path.join(TMP, "cli")
    shutil.rmtree(d, ignore_errors=True)
    data, summ = os.path.join(d, "data"), os.path.join(d, "agency.json")
    env = {**os.environ, "AGENCY_DATA_DIR": data, "AGENCY_SUMMARY_OUT": summ}
    env.pop("AGENCY_TODAY", None)
    cl = ["--clients", os.path.join(FIX, "clients.json")]
    rc0, out0 = run([], env)
    check("f. no command: the short help with the commands the owner uses", rc0 == 0 and "kit" in out0 and "paid" in out0 and "summary" in out0, out0[-300:])
    rc, out = run(["setup", "--name", "Test Web Co", "--owner", "Sam Owner", "--email", "sam@testweb.example", "--phone", "(555) 010-0100", "--state", "NY",
                   "--pay-link", "growth=https://buy.stripe.com/test_growth", "--today", "2026-11-14"], env)
    biz = json.load(open(os.path.join(data, "business.json"), encoding="utf-8"))
    check("f. setup saves the agency's profile and payment link; the data folder gets its own .gitignore ('*')",
          rc == 0 and biz["business_name"] == "Test Web Co" and biz["pay_links"]["growth"].endswith("test_growth")
          and "*" in open(os.path.join(data, ".gitignore"), encoding="utf-8").read().split(), out[-300:])
    rc, out = run(["setup", "--pay-link", "growth=javascript:alert(1)"], env)
    check("f. setup refuses a payment link that is not https:// (exit 2)", rc == 2 and "pay-link" in out, out[-200:])
    rc, out = run(["kit", "Rivera", "--today", "2026-11-14"] + cl, env)
    inv = json.load(open(os.path.join(data, "invoices.json"), encoding="utf-8"))["invoices"]
    prop = os.path.join(data, "docs", "c_demo_rivera", "proposal-2026-11-14.html")
    ih = open(os.path.join(data, "invoices", "INV-2026-0001.html"), encoding="utf-8").read()
    check("f. kit 'Rivera': proposal + agreement + invoice INV-2026-0001 ($0 setup + $149 for November) with the growth payment link in its pay box",
          rc == 0 and os.path.isfile(prop) and os.path.isfile(prop.replace("proposal", "agreement")) and len(inv) == 1 and inv[0]["no"] == "INV-2026-0001"
          and inv[0]["total_usd"] == 149.0 and inv[0]["first"] is True and 'href="https://buy.stripe.com/test_growth"' in ih and "Test Web Co" in ih, out[-500:])
    rc, out = run(["paid", "INV-2026-0001", "--today", "2026-11-14"], env)
    led = json.load(open(os.path.join(data, "ledger.json"), encoding="utf-8"))
    ih = open(os.path.join(data, "invoices", "INV-2026-0001.html"), encoding="utf-8").read()
    check("f. paid: the invoice is PAID (page re-made with the stamp), the ledger has $149 with an estimated $5.66 fee, the $149 plan starts that day",
          rc == 0 and led["payments"][0]["amount_usd"] == 149.0 and led["payments"][0]["fee_usd"] == 5.66 and led["payments"][0]["fee_estimated"]
          and led["plans"] == [{"client_id": "c_demo_rivera", "monthly_usd": 149.0, "start": "2026-11-14", "end": None, "package": "growth"}]
          and 'class="stamp paid"' in ih, out[-400:])
    rc, out = run(["paid", "INV-2026-0001", "--today", "2026-11-14"], env)
    check("f. paying the same invoice twice stops (exit 2) and records nothing", rc == 2 and "already paid" in out
          and len(json.load(open(os.path.join(data, "ledger.json"), encoding="utf-8"))["payments"]) == 1, out[-200:])
    rc, out = run(["plan", "change", "c_demo_rivera", "--monthly", "249", "--date", "2026-12-01", "--today", "2026-12-01", "--package", "pro"] + cl, env)
    plans = json.load(open(os.path.join(data, "ledger.json"), encoding="utf-8"))["plans"]
    check("f. plan change to $249 from Dec 1: the $149 plan's last day is Nov 30, the new one starts Dec 1",
          rc == 0 and plans[0]["end"] == "2026-11-30" and plans[1]["monthly_usd"] == 249.0 and plans[1]["start"] == "2026-12-01", (out[-300:], plans))
    csvp = os.path.join(d, "payments.csv")
    with open(csvp, "w", encoding="utf-8", newline="") as fh:
        fh.write("id,Created date (UTC),Amount,Amount Refunded,Currency,Fee,Status,Customer Email,Description\n"
                 "ch_1,2026-12-01 14:02:11,249.00,0.00,usd,7.52,Paid,owner@riveraplumbing.example,Subscription update\n"
                 "ch_2,2026-12-02 09:00:00,99.00,0.00,usd,3.17,Failed,office@summitroofing.example,Subscription\n"
                 "ch_3,2026-12-03 10:00:00,40.00,40.00,usd,1.46,Paid,stranger@nowhere.example,One-off\n"
                 "ch_4,2026-12-04 10:00:00,25.00,0.00,eur,1.00,Paid,owner@riveraplumbing.example,Euro\n")
    rc, out = run(["import", csvp, "--today", "2026-12-05"] + cl, env)
    rc2, out2 = run(["import", csvp, "--today", "2026-12-05"] + cl, env)
    pays = json.load(open(os.path.join(data, "ledger.json"), encoding="utf-8"))["payments"]
    imp = [p for p in pays if p.get("ext_id")]
    check("f. a Stripe-style CSV import: the paid row by email -> Rivera $249 (fee $7.52 from the file), the failed and euro rows skipped, the unknown email kept as 'unmatched' with its $40 refund; twice = no duplicates",
          rc == 0 and rc2 == 0 and [(p["client_id"], p["amount_usd"], p["fee_usd"], p["kind"]) for p in imp] == [("c_demo_rivera", 249.0, 7.52, "monthly"), ("unmatched", 40.0, 1.46, "monthly"), ("unmatched", 40.0, 0.0, "refund")]
          and "Already had 2" in out2 and "Imported 0" in out2, (out[-400:], out2[-300:], imp))
    rc, out = run(["plan", "cancel", "Rivera", "--last-day", "2027-01-31", "--today", "2026-12-15"] + cl, env)
    rc, out = run(["summary", "--today", "2026-12-15"], env)
    s = json.load(open(summ, encoding="utf-8"))
    check("f. plan cancel (last day Jan 31) + summary: MRR $249 still (paid up to Jan 31), $249 cancelling, Nov cash $149, Dec $249 + $40 - fees - refund",
          rc == 0 and s["mrr"]["now"] == 249.0 and s["mrr"]["ending_usd"] == 249.0 and s["months"][0]["cash_in"] == 149.0
          and near(s["months"][1]["cash_net"], 249 + 40 - 7.52 - 1.46 - 40) and "| MRR" in out, (out[-500:], s["mrr"]))
    blob = json.dumps(s)
    check("f. the written summary has no client name, id or email", not any(x in blob for x in ("Rivera", "c_demo_rivera", "riveraplumbing", "stranger@")))
    rc, out = run(["void", "INV-2026-0001", "--today", "2026-12-15"], env)
    check("f. a paid invoice cannot be voided (exit 2, record a refund instead)", rc == 2 and "refund" in out, out[-200:])
    rc, _ = run(["invoice", "c_demo_summit", "--setup", "--item", "Extra page=50x2", "--item", "Discount=-25", "--today", "2026-12-15"] + cl, env)
    rcv, _ = run(["void", "INV-2026-0002", "--today", "2026-12-15"], env)
    rc3, out3 = run(["invoice", "Summit Roofing (sample)", "--today", "2026-12-15", "--month", "2027-01", "--autopay"] + cl, env)
    inv = json.load(open(os.path.join(data, "invoices.json"), encoding="utf-8"))["invoices"]
    i3 = open(os.path.join(data, "invoices", "INV-2026-0003.html"), encoding="utf-8").read()
    check("f. invoice with --setup and items ($0 + $99 + 2 x $50 - $25 = $174), void it, the next is INV-2026-0003 (an autopay one: no pay button, 'charged automatically')",
          (rc, rcv, rc3) == (0, 0, 0) and [(i["no"], i["total_usd"], i["status"]) for i in inv[1:]] == [("INV-2026-0002", 174.0, "void"), ("INV-2026-0003", 99.0, "open")]
          and "charged automatically" in i3 and "January 2027" in i3 and 'class="btn"' not in i3, (out3[-300:], [(i["no"], i["total_usd"], i["status"]) for i in inv]))
    rc, out = run(["invoice", "Nobody Here", "--today", "2026-12-15"] + cl, env)
    check("f. an unknown client stops with exit 2 and names some clients; no number is used", rc == 2 and "no client" in out
          and len(json.load(open(os.path.join(data, "invoices.json"), encoding="utf-8"))["invoices"]) == 3, out[-300:])
    rc, out = run(["invoice", "c_demo_summit", "--dry-run", "--today", "2026-12-15"] + cl, env)
    check("f. --dry-run shows the total and uses no number", rc == 0 and "Dry run" in out and len(json.load(open(os.path.join(data, "invoices.json"), encoding="utf-8"))["invoices"]) == 3)
    before = open(os.path.join(data, "invoices.json"), "rb").read()
    rc, out = run(["demo", "--out", os.path.join(d, "demo"), "--today", "2026-11-14"], env)
    check("f. demo: three sample pages from the fixtures, and the real invoices file is not touched (no number used)",
          rc == 0 and len([f for f in os.listdir(os.path.join(d, "demo")) if f.endswith(".html")]) == 3 and open(os.path.join(data, "invoices.json"), "rb").read() == before, out[-300:])
    open(os.path.join(data, "invoices.json"), "w").write("{oops")
    rc, out = run(["invoice", "c_demo_summit", "--today", "2026-12-15"] + cl, env)
    check("f. a damaged invoices.json: the invoice command stops (exit 2) with the restore advice and leaves the file as it was",
          rc == 2 and "damaged" in out and open(os.path.join(data, "invoices.json")).read() == "{oops", out[-300:])
    after = sorted(os.listdir(REPO_DATA)) if os.path.isdir(REPO_DATA) else None
    check("f. the repo's own data/agency folder was not touched by any of this", after == REPO_DATA_BEFORE, (REPO_DATA_BEFORE, after))


# ------------------------------------------------------------------------------------------------ g. hygiene
def part_g():
    gi = open(os.path.join(ROOT, ".gitignore"), encoding="utf-8").read()
    p = subprocess.run(["git", "check-ignore", "-q", "data/agency/invoices.json"], cwd=ROOT)
    check("g. data/agency/ (the real clients, invoices and payments) is gitignored", "data/agency/" in gi and p.returncode == 0)
    code = {f: open(os.path.join(ROOT, "agency", "billing", f), encoding="utf-8").read() for f in ("core.py", "store.py", "render.py", "__main__.py", "__init__.py")}
    check("g. no network module anywhere in the kit (it sends nothing: the owner sends the files himself)",
          not any(re.search(r"^\s*(import|from)\s+(urllib\.request|http\.client|socket|requests|smtplib|ftplib)\b", c, re.M) for c in code.values()))
    check("g. subprocess only in render.py (the PDF through a local browser)", [f for f, c in code.items() if re.search(r"^import subprocess|^\s+import subprocess", c, re.M)] == ["render.py"])
    check("g. no key, token, password or secret in the kit", not any(re.search(r"api[_-]?key|password|access[_-]?token|bearer|\bsk_(live|test)_[A-Za-z0-9]{6}", c, re.I) for c in code.values()))
    pm = open(os.path.join(ROOT, "agency", "billing", "PAYMENTS.md"), encoding="utf-8").read()
    _, _, d = docs_for("c_demo_rivera")
    check("g. PAYMENTS.md: dated research on Stripe, Square and PayPal (fees, monthly billing, payout time), the 3 steps, where the link goes "
          "(the same 'Pay online in a minute' box the invoice shows), sources",
          "2026-11-14" in pm and all(x in pm for x in ("Stripe", "Square", "PayPal", "ACH", "payout", "## Your 3 steps", "## Where the link goes on the invoice",
                                                         "Pay online in a minute", "## Sources")) and "Pay online in a minute" in d["invoice"]
          and len(re.findall(r"^\d\. ", pm.split("## Your 3 steps")[1].split("##")[0], re.M)) == 3)
    bp = os.path.join(ROOT, "docs", "AGENCY_BUSINESS_SETUP.md")
    bs = open(bp, encoding="utf-8").read() if os.path.isfile(bp) else ""
    plan = bs.split("## 8.")[1] if "## 8." in bs else ""
    check("g. docs/AGENCY_BUSINESS_SETUP.md: not legal / tax advice, dated, sole proprietor vs LLC (varies by state), free EIN, separate bank, sales tax "
          "(how to check), self-employment tax (15.3%, the 2026 wage base, quarterly dates), 25-30% aside, bookkeeping, sources",
          "**Not legal or tax advice.**" in bs and "2026-11-14" in bs and all(x in bs for x in (
              "Sole proprietor or LLC", "varies a lot by state", "IRS.gov/EIN", "separate bank account", "How to check yours", "15.3%", "$184,500",
              "April 15, June 15, September 15, 2026 and January 15, 2027", "25-30%", "bookkeeping", "agency/billing/PAYMENTS.md", "## Sources")))
    check("g. ... and a 30-day plan with daily numbers (leads, dials, talks, demos, closes) adding up to the first $1,000 MRR, its assumptions said out loud",
          all(x in plan for x in ("Leads added", "Dials", "Owner talks", "Demo links sent", "New clients", "**Total**", "7 x $149", "$1,043", "assumptions, not facts"))
          and 7 * 149 >= 1000)
    fx = json.dumps([load("clients.json"), load("business.json"), load("ledger.json")])
    check("g. the fixtures are made up: example.com / .example addresses and 555 phone numbers only",
          all(e.endswith(".example") or e.endswith("example.com") for e in re.findall(r"[\w.+-]+@([\w.-]+)", fx)) and all("555" in ph for ph in re.findall(r"\(\d{3}\) \d{3}-\d{4}", fx)))


def main():
    try:
        for part in (part_a, part_b, part_c, part_d, part_e, part_f, part_g):
            try:
                part()
            except Exception as e:  # noqa: BLE001 (a crash in one part is a failure, the others still run)
                check(f"{part.__name__} ran without crashing", False, f"{e.__class__.__name__}: {e}")
    finally:
        shutil.rmtree(TMP, ignore_errors=True)
    print(f"\n{sum(RES)}/{len(RES)} passed")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
