"""Agency · Offers (tools/web_public/agency/offers/, day-web-offers 2026-11-20): the money side of the website business.

    python -X utf8 -m tests.test_web_offers            (--static: no browser)
a. static: files, no network but its own JSON, no paid service, no owner details, 'not legal advice', print rules, 44 px / 15 px in the CSS
b. core (node): margins vs the hourly target, quote (extras, rush, discount, 50 % deposit), proposal text, month-end due dates, MRR / late,
   goals for $1,000 / $3,000 / $5,000, junk state never throws
c. browser (390 x 844 and 320 x 568): renders with no error, no sideways scroll, proposal total, deposit invoice, a monthly client survives a reload,
   the tabs work by keyboard, every button >= 44 px and named, the print view holds only the proposal
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
D = os.path.join(ROOT, "tools", "web_public", "agency", "offers")
FAILS: list = []
N = [0]


def check(name, ok, info=""):
    N[0] += 1
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  [{str(info)[:300]}]"))
    if not ok:
        FAILS.append(name)


def read(name):
    with open(os.path.join(D, name), encoding="utf-8") as fh:
        return fh.read()


def static():
    for f in ("index.html", "offers.js", "offerscore.js", "offers.css", "offers.json"):
        check(f"a. {f} exists", os.path.isfile(os.path.join(D, f)))
    html, js, core, css = read("index.html"), read("offers.js"), read("offerscore.js"), read("offers.css")
    data = json.loads(read("offers.json"))
    check("a. three packages: Starter site, 3D Showcase, Growth retainer, each with price, days, monthly and what is included",
          [p["name"] for p in data["packages"]] == ["Starter site", "3D Showcase", "Growth retainer"]
          and all(p["price"] > 0 and p["days"] > 0 and p["monthly"] > 0 and len(p["includes"]) >= 4 for p in data["packages"]))
    check("a. prices say where they come from (placeholder until the research numbers)", data.get("source") and "placeholder" in json.dumps(data).lower() or data.get("placeholder") is False)
    check("a. the terms cover deposit, revisions, hosting, who owns what", {"deposit", "revisions", "hosting", "ownership"} <= {t["id"] for t in data["terms"]})
    check("a. 'Not legal advice' is on the terms", "Not legal advice" in html and "not legal advice" in html.lower())
    urls = re.findall(r"""(?:fetch|getJSON)\(\s*['"`]([^'"`]+)""", js) + re.findall(r"'(\.\./[^']+\.json)'", js)
    check("a. reads only its own price list and the Agency's lead names (no other network)", set(urls) <= {"offers.json", "../leads.json", "../fixture.json", "u"} and "http" not in js.replace("https://", "") , urls)
    check("a. no paid service, key or tracker", not re.search(r"stripe|paypal|api[_-]?key|analytics|gtag|sendgrid|mailchimp", (html + js + core).lower()))
    check("a. no owner details in the files", not re.search(r"demetrades|@gmail|zlarior", (html + js + core + json.dumps(data)).lower()))
    check("a. text only by textContent (no innerHTML)", "innerHTML" not in js and "innerHTML" not in core)
    check("a. one localStorage key of its own ('agency.offers.v1'), plus download / load a copy", "agency.offers.v1" in js and "download" in js and "importFile" in js)
    check("a. print: only #print shows on paper, black on white", "@media print" in css and "body > *:not(#print)" in css and "#fff" in css)
    check("a. taps 44 px, 16 px inputs (no iOS zoom), safe areas, reduced motion", css.count("min-height: 44px") >= 4 and "font-size: 1rem" in css and "safe-area-inset-bottom" in css and "prefers-reduced-motion" in css)
    check("a. no px font sizes under 15 px for sentences (rem / tokens)", not re.search(r"font-size:\s*1[0-4]px", css) and not re.search(r"font:\s*\d+\s+1[0-4]px", css))


HARNESS = r"""
const C = await import(process.argv[2]);
const fs = await import('fs');
const D = C.normData(JSON.parse(fs.readFileSync(process.argv[3], 'utf8')));
const out = {};
out.counts = [D.packages.length, D.extras.length, D.terms.length];
out.m = C.margin({ price: 1000, hours: 10, hard: 100 }, 60);
out.mlow = C.margin({ price: 300, hours: 10, hard: 0 }, 60);
out.q = C.quote(D, { package: 'showcase3d', extras: ['gbp', 'model3d', 'nope'], rush: true, discount: 100 }, 60);
out.q0 = C.quote(D, { package: 'starter' }, 60);
out.text = C.proposalText(out.q0, 'Peak Web', "Roy's Quick Lube", 'Nov 20, 2026');
out.textG = C.proposalText(C.quote(D, { package: 'growth' }, 60), '', '', '');
out.due = [C.nextDue({ start: '2026-01-31', paid: '' }), C.nextDue({ start: '2026-01-31', paid: '2026-01-31' }), C.nextDue({ start: '2026-01-31', paid: '2026-02-28' }), C.nextDue({ start: '2026-12-15', paid: '2026-12-15' })];
out.L = C.ledger({ clients: [{ id: 'a', name: 'Roy', monthly: 49, start: '2026-10-05', paid: '2026-10-05' }, { id: 'b', name: 'Bo', monthly: 499, start: '2026-11-25' },
  { id: 'c', name: 'Old', monthly: 99, start: '2026-01-01', active: false }], invoices: [{ id: 'i', client: 'Roy', amount: 250, due: '2026-11-01' }, { id: 'j', client: 'Bo', amount: 500, due: '2026-11-01', paid: '2026-11-03' }] }, '2026-11-20');
out.G = C.goals(D, 60, 548);
out.Gdone = C.goals(D, 60, 6000);
out.junk = [C.normState(null), C.normState({ hourly: 'x', clients: [1, null, { name: '<b>', start: 'no' }], invoices: 'z' }), C.normData(42), C.quote(C.normData({}), {}, 60)];
out.money = [C.money(1234.4), C.money(-80), C.money(null)];
console.log(JSON.stringify(out));
"""


def core():
    exe = shutil.which("node")
    if not exe:
        print("SKIP core: no node")
        return
    tmp = tempfile.mkdtemp(prefix="offers-")
    try:
        shutil.copy(os.path.join(D, "offerscore.js"), os.path.join(tmp, "offerscore.mjs"))
        h = os.path.join(tmp, "h.mjs")
        with open(h, "w", encoding="utf-8") as fh:
            fh.write(HARNESS)
        r = subprocess.run([exe, h, os.path.join(tmp, "offerscore.mjs"), os.path.join(D, "offers.json")], capture_output=True, text=True, timeout=60)
        if r.returncode:
            check("b. the core runs in node", False, r.stderr[-400:])
            return
        o = json.loads(r.stdout)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    check("b. offers.json loads: 3 packages, extras, terms", o["counts"][0] == 3 and o["counts"][1] >= 4 and o["counts"][2] >= 6, o["counts"])
    m = o["m"]
    check("b. margin: $1,000 job, 10 h, $100 hard costs -> keep $900 = $90/h, $300 over a $60/h target, ok",
          m["profit"] == 900 and m["per_hour"] == 90 and m["time_cost"] == 600 and m["over_target"] == 300 and m["ok"], m)
    check("b. margin: $300 for 10 h is below a $60/h target (flagged)", o["mlow"]["ok"] is False and o["mlow"]["per_hour"] == 30)
    q = o["q"]
    base = 2499 + 149 + 299
    check("b. quote: package + 2 extras (unknown id dropped) + 25 % rush - $100 discount", q["setup"] == base + round(base * 0.25) - 100 and len(q["lines"]) == 5, (q["setup"], [l["name"] for l in q["lines"]]))
    check("b. quote: 50 % deposit, the balance at launch, rush halves the days", q["deposit"] + q["balance"] == q["setup"] and abs(q["deposit"] - q["setup"] / 2) <= 1 and q["days"] == -(-(14 + 1 + 2) // 2), (q["deposit"], q["days"]))
    check("b. quote: first year = build + 12 months", o["q0"]["first_year"] == o["q0"]["setup"] + 12 * o["q0"]["monthly"])
    t = o["text"]
    check("b. proposal text: names both businesses, the total, the deposit, the days, what is included, valid 14 days, no NaN / undefined",
          "Roy's Quick Lube" in t and "Peak Web" in t and "$499" in t and "deposit" in t and "working days" in t and "- " in t and "14 days" in t and not re.search(r"NaN|undefined|null", t), t[:300])
    check("b. proposal text: the Growth retainer says its 3-month minimum; a blank name never prints 'undefined'", "3 months minimum" in o["textG"] and "Your business" in o["textG"] and "undefined" not in o["textG"])
    check("b. next due: same day each month, clamped to the month's end (Jan 31 -> Feb 28 -> Mar 31), across the year end",
          o["due"] == ["2026-01-31", "2026-02-28", "2026-03-31", "2027-01-15"], o["due"])
    L = o["L"]
    check("b. ledger: MRR counts active clients only ($548), the late one is 15 days late, the open invoice is $250 and 19 days late",
          L["mrr"] == 548 and L["active"] == 2 and L["overdue"][0]["late"] == 15 and L["open_total"] == 250 and L["open_invoices"][0]["late"] == 19, L)
    check("b. ledger: paid this month counts the paid invoice", L["paid_month"] == 500, L["paid_month"])
    G = o["G"]
    st = [p for p in G[0]["per"] if p["id"] == "starter"][0]
    check("b. goals: $1,000 / $3,000 / $5,000, the gap from $548, clients needed at each plan's monthly price",
          [g["goal"] for g in G] == [1000, 3000, 5000] and G[0]["gap"] == 452 and st["clients"] == -(-452 // st["monthly"]), G[0])
    check("b. goals: past $5,000 every goal says reached", all(g["reached"] for g in o["Gdone"]))
    j = o["junk"]
    check("b. junk state / data never throws: defaults, bad rows dropped, no quote without packages",
          j[0]["hourly"] == 60 and j[1]["clients"] == [] and j[1]["invoices"] == [] and j[1]["hourly"] == 60 and j[2]["packages"] == [] and j[3] is None, j)
    check("b. money: $1,234 / a real minus sign / $0", o["money"] == ["$1,234", "−$80", "$0"], o["money"])


def browser():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("SKIP browser: no Python playwright")
        return
    sys.path.insert(0, os.path.join(ROOT, "tests"))
    import browser_kit as BK
    from tests import agora_kit as AK
    srv, origin = AK.serve()
    try:
        with sync_playwright() as pw:
            br = BK.launch(pw)
            for w, hgt in ((390, 844), (320, 568)):
                ctx = br.new_context(viewport={"width": w, "height": hgt}, is_mobile=True, has_touch=True, reduced_motion="reduce", service_workers="block")
                ctx.route(re.compile(r"^(?!https?://127\.0\.0\.1)"), lambda r: r.abort())
                p = ctx.new_page()
                errs = []
                p.on("pageerror", lambda e: errs.append(str(e)))
                p.goto(f"{origin}/agency/offers/", wait_until="load")
                p.wait_for_function("document.querySelectorAll('#pkgs .pkg').length === 3", timeout=15000)
                check(f"c. {w}px: three package cards, no page error", not errs, errs)
                p.wait_for_timeout(600)
                check(f"c. {w}px: the page tells the kit it is ready (the loading veil lifts at once, not after 12 s)", p.evaluate("!document.documentElement.hasAttribute('data-oly-veil')"))
                wide = p.evaluate("() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - innerWidth")
                check(f"c. {w}px: no sideways scroll", wide <= 1 and p.evaluate("innerWidth") == w, wide)
                small = p.evaluate("""() => [...document.querySelectorAll('button, a[href], input:not([type=checkbox]):not([type=radio]):not([type=file]), select, summary, .opt, .chk')]
                  .filter(e => e.getClientRects().length && !e.closest('[hidden]')).map(e => { const r = e.getBoundingClientRect(); return [e.id || e.className || e.tagName, Math.round(r.width), Math.round(r.height)]; })
                  .filter(x => x[2] < 43.5)""")
                check(f"c. {w}px: every visible control is at least 44 px tall", not small, small[:5])
                if w != 390:
                    ctx.close()
                    continue
                check("c. each package shows what you keep per hour against the target", p.locator("#pkgs .pkg dl.kv").count() == 3 and "/h" in p.text_content("#pkgs"))
                p.keyboard.press("Tab")
                p.focus("#tab-pk")
                p.keyboard.press("ArrowRight")
                check("c. the tabs move by arrow key (Prices -> Proposal)", p.evaluate("document.activeElement.id") == "tab-pr" and not p.is_hidden("#p-pr"))
                p.fill("#prBiz", "Roy's Quick Lube")
                p.check("#prExtras input[value=gbp]")
                p.fill("#prFrom", "Peak Web")
                p.dispatch_event("#prFrom", "change")
                check("c. proposal: Starter $499 + Google profile $149 = $648, for Roy's Quick Lube, from Peak Web",
                      p.text_content("#shTotal") == "$648" and "Roy's Quick Lube" in p.text_content("#shTitle") and "Peak Web" in p.text_content("#shFrom"))
                check("c. proposal: the margin line is for the owner only (outside the printed sheet)", "/h" in p.text_content("#prMargin") and p.locator("#sheet #prMargin").count() == 0)
                p.evaluate("() => { window.print = () => { window.__printed = document.getElementById('print').textContent; }; }")
                p.click("#prPrint")
                printed = p.evaluate("window.__printed || ''")
                check("c. Save as PDF prints the proposal sheet (total and name) and not the page", "$648" in printed and "Roy's Quick Lube" in printed and "For you only" not in printed, printed[:120])
                p.click("#prInvoice")
                check("c. the deposit invoice ($324, due in 7 days) lands in Money", "$324" in p.text_content("#invoices") and not p.is_hidden("#p-mo"))
                p.click("#addClientBox summary")
                p.fill("#clName", "Bo Bakery")
                p.select_option("#clPkg", "growth")
                p.fill("#clMonthly", "499")
                p.click("#clForm button[type=submit]")
                check("c. a monthly client: MRR $499 on top", p.text_content("#mrrNum") == "$499" and "Bo Bakery" in p.text_content("#clients"))
                names = p.evaluate("() => [...document.querySelectorAll('#clients button, #invoices button')].map(b => b.getAttribute('aria-label') || '')")
                check("c. row buttons say whose they are for VoiceOver ('Paid: Bo Bakery')", all(":" in n for n in names) and any("Bo Bakery" in n for n in names), names)
                p.reload()
                p.wait_for_function("document.querySelectorAll('#pkgs .pkg').length === 3", timeout=15000)
                check("c. saved on the phone: after a reload the client, invoice and agency name are still there",
                      p.text_content("#mrrNum") == "$499" and "$324" in p.text_content("#invoices") and p.input_value("#prFrom") == "Peak Web")
                p.click("#tab-tm")
                p.locator("#terms input").first.check()
                check("c. terms: ticking one counts it, 'Not legal advice' shown", p.text_content("#termsCount").startswith("1 of") and "Not legal advice" in p.text_content("#p-tm"))
                p.click("#tab-gl")
                check("c. goal: three goals with a gap from $499", p.locator("#goals .goal").count() == 3 and "$501 to go" in p.text_content("#goals"))
                ctx.close()
    finally:
        srv.shutdown()


if __name__ == "__main__":
    static()
    core()
    if "--static" not in sys.argv:
        browser()
    print(f"\n{N[0] - len(FAILS)}/{N[0]} passed" + ("" if not FAILS else f"; FAILED: {FAILS}"))
    sys.exit(1 if FAILS else 0)
