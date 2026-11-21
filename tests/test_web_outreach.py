"""Agency · Outreach (tools/web_public/agency/outreach/, day-a11y 2026-11-20, the Website Factory's outreach + close kit).

    python -X utf8 -m tests.test_web_outreach            (--static: no browser)
a. static + the words: noindex, no owner details, no texting, the CAN-SPAM parts in every email (true subject, who it is from, postal address,
   opt-out), 3 emails on day 0 / 3 / 7, opener + voicemail, 8 objections, the agreement says 'not legal advice', the invoice's payment line
   is an owner step, the delivery checklist names who does each step, prices = agency/offers
b. core (node): fill never prints 'undefined', the demo link (own site > niche demo), the follow-up rhythm, today's 20 order, state junk
c. browser 390 x 844 + 320: renders, 20 cards, no sideways scroll, 44 px controls, a status tap writes the SHARED Leads key, the touch moves
   the lead to its day-3 follow-up, copy gives the personalised email, the owner's details fill the messages and survive a reload, the close kit
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
D = os.path.join(ROOT, "tools", "web_public", "agency", "outreach")
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
    html, js, core = read("index.html"), read("outreach.js"), read("outreachcore.js")
    W = json.loads(read("scripts.json"))
    check("a. owner-only: noindex, nofollow", '<meta name="robots" content="noindex, nofollow">' in html)
    allt = html + js + core + json.dumps(W)
    check("a. no owner details in the files ([Your name] / [Business name] placeholders only)", not re.search(r"demetrades|@gmail|zlarior", allt.lower()) and "[Your name]" in core and "[Business name]" in core)
    check("a. never a text message: no sms: link, the rules say no cold texts (TCPA)", "sms:" not in allt and any("No cold texts" in r for r in W["rules"]))
    check("a. calls dialled by hand, no auto-dialer or voicemail drops", any("auto-dialer" in r for r in W["rules"]))
    em = W["email"]
    check("a. three emails: day 0, 3 and 7", [e["day"] for e in em] == [0, 3, 7])
    check("a. every email: from your name, your postal address, a way to say no (except the last, which says it stops)",
          all("{your_name}" in e["body"] and "{postal_address}" in e["body"] for e in em) and all("no thanks" in e["body"] for e in em[:2]) and "won't keep emailing" in em[2]["body"])
    check("a. honest subjects: no 'Re:' trick on the first email, the business name in each", not em[0]["subject"].lower().startswith("re:") and all("{business}" in e["subject"] for e in em))
    check("a. the first email says it is a one-time business offer", "one-time business offer" in em[0]["body"])
    check("a. personalised: business name + demo link in the opener, voicemail and every email", all("{business}" in x and ("{demo}" in x or "{demo_short}" in x) for x in [e["body"] for e in em] + [W["phone"]["voicemail"]]) and "{business}" in W["phone"]["opener"])
    check("a. 8 objections, each with an answer", len(W["objections"]) == 8 and all(o["q"] and len(o["a"]) > 40 for o in W["objections"]))
    check("a. the agreement: deposit, ownership, domain in their name, ending, 'not legal advice'", all(any(k in x[0] for x in W["agreement"]["items"]) for k in ("Price", "Who owns", "domain", "Ending")) and "not legal advice" in W["agreement"]["foot"])
    check("a. the invoice's payment line is an OWNER STEP with no paid service", "OWNER STEP" in W["invoice"]["pay_line"] and "No paid service" in W["invoice"]["pay_line"])
    check("a. delivery checklist: the client buys the domain, free hosting, Google Business Profile, who does each step", any(d["who"] == "client" and "domain" in d["step"] for d in W["delivery"])
          and any("free" in d["step"] and "hosting" in d["step"] for d in W["delivery"]) and any("Google Business Profile" in d["step"] for d in W["delivery"]) and {d["who"] for d in W["delivery"]} == {"owner", "client", "claude"})
    check("a. status marks go to the Leads page's key, the owner's details to its own key", "'agency.leads.status.v1'" in js and "'agency.outreach.v1'" in js)
    check("a. reads only its own files (scripts, leads, offers, the factory's sites index); the autopilot counts come through pc_feed.js (the PC report)",
          set(re.findall(r"getJSON\('([^']+)'\)", js)) == {"scripts.json", "../leads/leads.json", "../offers/offers.json", "../sites/index.json"}
          and js.count("fetch(") == 1 and "PC_FEED" in js and "../../pc_feed.js" in html)
    check("a. the autopilot card's numbers keep their place from the first paint (tiles with '-')", "autoTiles(null)" in js and 'id="autoNums" hidden' not in html)
    check("a. no innerHTML, no paid service", "innerHTML" not in js + core and not re.search(r"stripe|paypal|twilio|sendgrid|mailchimp", allt.lower()))
    off = json.loads(open(os.path.join(ROOT, "tools", "web_public", "agency", "offers", "offers.json"), encoding="utf-8").read())
    st = [p for p in off["packages"] if p["id"] == "starter"][0]
    check("a. prices = agency/offers (Starter $1,500 + $79) and the no-upfront $149 x 12", (st["price"], st["monthly"]) == (1500, 79) and "monthly: 149, months: 12" in core)


HARNESS = r"""
const C = await import(process.argv[2]);
const fs = await import('fs');
const L = JSON.parse(fs.readFileSync(process.argv[3], 'utf8')).leads;
const offers = JSON.parse(fs.readFileSync(process.argv[4], 'utf8'));
const W = JSON.parse(fs.readFileSync(process.argv[5], 'utf8'));
const o = {};
const lead = { id: 'x1', name: "Joe's Diner", niche: 'food', category: 'restaurant', town: 'Frederick', heat: 'hot', phone: '(301) 555-0100', score: 9 };
const v0 = C.varsFor(lead, {}, { base: 'https://example.org/site/', offers });
o.blank = C.fill(W.email[0].subject + '\n' + W.email[0].body, v0);
o.me = C.fill(W.email[0].body, C.varsFor(lead, { your_name: 'Sam', your_business: 'Peak Web', your_phone: '555-1', postal_address: '1 Main St' }, { base: 'https://example.org/site/', offers }));
o.empty = C.fill('notice{min_term}.', { min_term: '' });
o.demo = [C.demoFor(lead, {}, 'https://e.org/s').url, C.demoFor(lead, { x1: '../sites/joes/' }, 'https://e.org/s'), C.demoFor({ id: 'z', niche: 'health' }, {}, 'https://e.org/s').url,
  C.demoFor(lead, { x1: 'javascript:alert(1)' }, 'https://e.org/s').url];
o.price = C.priceLine(offers);
o.p = [C.plan(lead, null, [], '2026-11-20'), C.plan(lead, { s: 'called' }, [{ d: '2026-11-20', k: 'first' }], '2026-11-21'), C.plan(lead, { s: 'called' }, [{ d: '2026-11-20', k: 'first' }], '2026-11-23'),
  C.plan(lead, null, [{ d: '2026-11-20', k: 'first' }, { d: '2026-11-23', k: 'bump' }], '2026-11-27'), C.plan(lead, null, [{ d: '2026-11-20', k: 'first' }, { d: '2026-11-23', k: 'bump' }, { d: '2026-11-27', k: 'last' }], '2026-12-01'),
  C.plan(lead, { s: 'no' }, [], '2026-11-20'), C.plan(lead, { s: 'interested' }, [{ d: '2026-11-20', k: 'first' }], '2026-11-20')];
const marks = { [L[5].id]: { s: 'no' }, [L[6].id]: { s: 'interested' } }, touches = { [L[7].id]: [{ d: '2026-11-15', k: 'first' }], [L[8].id]: [{ d: '2026-11-19', k: 'first' }] };
const T = C.todays(L, marks, touches, '2026-11-20', 20);
o.t = { n: T.length, first: T.slice(0, 2).map((r) => [r.L.id, r.p.step]), ids: T.map((r) => r.L.id), heat: T.map((r) => r.L.heat) };
o.ids = { no: L[5].id, yes: L[6].id, due: L[7].id, wait: L[8].id };
o.junk = [C.normState(null), C.normState({ me: { your_name: '<b>x</b>', evil: 1 }, touches: { a: [{ d: 'x', k: 'first' }, { d: '2026-01-01', k: 'hack' }, { d: '2026-01-02', k: 'bump' }] }, checks: { d1: true, d2: 'yes' } })];
o.step = [C.emailStep({ step: 'first' }), C.emailStep({ step: 'bump' }), C.emailStep({ step: 'wait', day: 7 })];
o.mail = C.parseCard({ t: 100, m: 'live', n: 7, c: 20, q: 3, name: 'Joe' });
o.mail0 = [C.parseCard(null), C.parseCard({ m: 'live' })];
console.log(JSON.stringify(o));
"""


def core():
    exe = shutil.which("node")
    if not exe:
        print("SKIP core: no node")
        return
    tmp = tempfile.mkdtemp(prefix="outreach-")
    try:
        shutil.copy(os.path.join(D, "outreachcore.js"), os.path.join(tmp, "c.mjs"))
        h = os.path.join(tmp, "h.mjs")
        with open(h, "w", encoding="utf-8") as fh:
            fh.write(HARNESS)
        A = os.path.join(ROOT, "tools", "web_public", "agency")
        r = subprocess.run([exe, h, os.path.join(tmp, "c.mjs"), os.path.join(A, "leads", "leads.json"), os.path.join(A, "offers", "offers.json"), os.path.join(D, "scripts.json")],
                           capture_output=True, text=True, timeout=60)
        if r.returncode:
            check("b. the core runs in node", False, r.stderr[-400:])
            return
        o = json.loads(r.stdout)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    b = o["blank"]
    check("b. without the owner's details the email shows [placeholders], never 'undefined' / 'null' / a raw {key}",
          "[Your name]" in b and "[postal address" in b and not re.search(r"undefined|null|\{[a-z_]+\}", b), b[:200])
    check("b. personalised: the business, the town, the niche, the demo link, the price line", all(x in b for x in ("Joe's Diner", "Frederick", "restaurant", "https://example.org/site/agency/demos/restaurant/", "$1,500")))
    check("b. the owner's details fill the email", all(x in o["me"] for x in ("Sam", "Peak Web", "555-1", "1 Main St")))
    check("b. a deliberately empty part prints nothing", o["empty"] == "notice.", o["empty"])
    d = o["demo"]
    check("b. demo link: the niche demo, the factory's own site first (own: true), a generic demo for an unknown niche, never a javascript: link",
          d[0].endswith("/agency/demos/restaurant/") and d[1]["own"] and d[1]["url"] == "https://e.org/s/agency/sites/joes/" and d[2].endswith("/agency/demos/") and "javascript" not in d[3], d)
    check("b. price line: Starter $1,500 + $79 a month, or $149 a month for 12 months", "Starter site $1,500 + $79 a month" in o["price"] and "$149 a month for 12 months" in o["price"], o["price"])
    P = o["p"]
    check("b. rhythm: day 0 first -> waiting -> day 3 follow-up due -> day 7 last note due -> done; 'no' = done; interested = close",
          [x["step"] for x in P] == ["first", "wait", "bump", "last", "done", "done", "close"] and P[1]["due"] == "2026-11-23" and P[3]["due"] == "2026-11-27", [x["step"] for x in P])
    t, ids = o["t"], o["ids"]
    check("b. today's 20: 20 rows, the interested lead first, then the due follow-up; 'no' and the one still waiting are left out",
          t["n"] == 20 and t["first"] == [[ids["yes"], "close"], [ids["due"], "bump"]] and ids["no"] not in t["ids"] and ids["wait"] not in t["ids"], t)
    fresh = t["heat"][2:]
    check("b. today's 20: the untouched ones hot first, then warm, then cold", fresh == sorted(fresh, key=lambda x: {"hot": 0, "warm": 1, "cold": 2}.get(x, 3)), fresh)
    j = o["junk"]
    check("b. junk state never throws: unknown fields, bad dates and kinds dropped, markup stripped", j[0] == {"v": 1, "me": {}, "touches": {}, "checks": {}}
          and j[1]["touches"] == {"a": [{"d": "2026-01-02", "k": "bump"}]} and j[1]["checks"] == {"d1": True} and "<" not in j[1]["me"].get("your_name", "") and "evil" not in j[1]["me"], j[1])
    check("b. a tap records the step the plan is on (first / bump / last)", o["step"] == ["first", "bump", "last"], o["step"])
    m = o["mail"] or {}
    check("b. the autopilot card (the PC report's 'am'): numbers only, an extra field like a name dropped, nothing without a time", m.get("t") == 100 and m.get("new") == 7 and m.get("mode") == "live" and "name" not in m and o["mail0"] == [None, None], (m, o["mail0"]))


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
                ctx.grant_permissions(["clipboard-read", "clipboard-write"], origin=origin)
                p = ctx.new_page()
                errs = []
                p.on("pageerror", lambda e: errs.append(str(e)))
                p.goto(f"{origin}/agency/outreach/", wait_until="load")
                p.wait_for_function("document.querySelectorAll('#today li.lead').length === 20", timeout=15000)
                check(f"c. {w}px: 20 businesses, no page error, the veil lifted", not errs and p.evaluate("!document.documentElement.hasAttribute('data-oly-veil')"), errs)
                wide = p.evaluate("() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth) - innerWidth")
                check(f"c. {w}px: no sideways scroll", wide <= 1, wide)
                small = p.evaluate("""() => [...document.querySelectorAll('#p-today button, #p-today a, .ag-tab')].filter(e => e.getClientRects().length)
                  .map(e => [e.textContent.trim().slice(0, 20), Math.round(e.getBoundingClientRect().height)]).filter(x => x[1] < 43.5)""")
                check(f"c. {w}px: every button and link on Today is at least 44 px tall", not small, small[:5])
                if w != 390:
                    ctx.close()
                    continue
                first = p.locator("#today li.lead").first
                name = first.locator("h3").text_content()
                check("c. no texting anywhere on the page (no sms: link)", p.locator("a[href^='sms:']").count() == 0)
                check("c. the first card: a Call link (tel:) and the demo link", first.locator("a[href^='tel:']").count() == 1 and first.locator("a.demo").count() == 1)
                first.get_by_role("button", name=re.compile("Copy the day 0")).click()
                clip = p.evaluate("navigator.clipboard.readText()")
                check("c. Copy email: the personalised day-0 email with its subject, placeholders until the owner fills Me", clip.startswith("Subject: A free website draft for " + name) and "[Your name]" in clip and "[postal address" in clip, clip[:160])
                first.get_by_role("button", name="Called").click()
                marks = p.evaluate("JSON.parse(localStorage.getItem('agency.leads.status.v1'))")
                st = p.evaluate("JSON.parse(localStorage.getItem('agency.outreach.v1'))")
                check("c. 'Called' writes the Leads page's shared key and a day-0 touch", any(v.get("s") == "called" for v in marks.values()) and any(t[0]["k"] == "first" for t in st["touches"].values()), (marks, st))
                check("c. the called lead leaves today's list (its day-3 follow-up is later)", name not in [x.text_content() for x in p.locator("#today li.lead h3").all()])
                p.click("#tab-me")
                for k, v in (("your_name", "Sam Test"), ("your_business", "Peak Web"), ("your_phone", "555-0199"), ("postal_address", "1 Main St, Town")):
                    p.fill("#" + k, v)
                p.click("#meForm button[type=submit]")
                p.reload()
                p.wait_for_function("document.querySelectorAll('#today li.lead').length === 20", timeout=15000)
                p.locator("#today li.lead").first.get_by_role("button", name=re.compile("Copy the phone opener")).click()
                op = p.evaluate("navigator.clipboard.readText()")
                check("c. the owner's details survive a reload and fill the opener; the 'fill in your details' card is gone", "Sam Test" in op and "Peak Web" in op and p.is_hidden("#meWarn"), op[:120])
                p.click("#tab-words")
                check("c. Words: the rules, 3 emails, 8 objections", p.locator("#rules li").count() == 5 and p.locator("#emailWords .say").count() == 3 and p.locator("#objections details").count() == 8)
                p.click("#tab-close")
                p.fill("#cBiz", "Joe's Diner")
                p.dispatch_event("#cBiz", "input")
                ag, inv = p.text_content("#agreement"), p.text_content("#invoice")
                check("c. Close: the agreement names both businesses, $1,500 / $750 deposit, says not legal advice; no stray [placeholder] once filled",
                      "Joe's Diner" in ag and "Peak Web" in ag and "$1,500" in ag and "$750" in ag and "not legal advice" in ag and "[min term]" not in ag, ag[:200])
                check("c. Close: the deposit invoice is $750 with the owner-step payment line", "$750" in inv and "OWNER STEP" in inv)
                p.locator("#cPlan input[value=noupfront]").check()
                check("c. Close: the no-upfront plan invoices $149 for the first month", "$149" in p.text_content("#invoice"))
                p.locator("#delivery input").first.check()
                check("c. the delivery checklist ticks are saved", p.evaluate("JSON.parse(localStorage.getItem('agency.outreach.v1')).checks.d0") is True)
                p.evaluate("() => { window.print = () => { window.__printed = document.getElementById('print').textContent; }; }")
                p.click("#printAg")
                check("c. Agreement as PDF prints only the agreement", "Website agreement" in p.evaluate("window.__printed || ''"))
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
