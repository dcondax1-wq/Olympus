"""The Business -> Taxes page (tools/web_public/business/taxes.html + taxes.js, 2026-11-17): the eight sections in order,
'Education, not tax advice' with IRS.gov sources, textContent only (no innerHTML / eval), phone-first layout, the next 4
quarterly due dates computed from today (weekend + MLK Day shifts), the set-aside calculator (30% default, junk safe), and
the same 30% default in Oikos, the Ledger and the Oikos scanner. Offline. --browser adds a 390 px phone check (run it under
flock -w 2400 /tmp/olympus_browser.lock).

  python -X utf8 -m tests.test_business_taxes [--browser]
"""
from __future__ import annotations

import functools
import glob
import http.server
import json
import os
import re
import subprocess
import sys
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
WEB = os.path.join(ROOT, "tools", "web_public")
BIZ = os.path.join(WEB, "business")
RES = []


def check(name, cond, detail=""):
    RES.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({str(detail)[:300]})" if detail and not cond else ""))


def read(*p):
    with open(os.path.join(*p), encoding="utf-8") as fh:
        return fh.read()


def part_a():
    html, js = read(BIZ, "taxes.html"), read(BIZ, "taxes.js")
    heads = ["In one minute", "How your payouts are taxed", "What you can deduct", "Quarterly dates", "Set aside per payout",
             "Kalshi", "Records to keep", "Get help free"]
    pos = [html.find(">" + h + "<") for h in heads]
    check("a. the eight sections are there, in order", all(p > 0 for p in pos) and pos == sorted(pos), dict(zip(heads, pos)))
    foot = html[html.find("<footer"):]
    check("a. the footer says 'Education, not tax advice' and links IRS.gov, MFFU's and Kalshi's help centers",
          "Education, not tax advice" in foot and foot.count('href="https://www.irs.gov/') >= 6
          and "help.myfundedfutures.com" in foot and "help.kalshi.com" in foot)
    check("a. no innerHTML / outerHTML / insertAdjacentHTML / document.write / eval in the page script",
          not re.search(r"innerHTML|outerHTML|insertAdjacentHTML|document\.write|\beval\(|new Function", js))
    check("a. phone first: a viewport meta, the AGORA theme, business.css, a 16px side gutter, a back link to Business",
          'name="viewport"' in html and 'data-theme="agora"' in html and "business.css" in html and "padding: 12px 16px" in html and 'href="./"' in html)
    check("a. only same-site scripts and styles (no CDN, no tracker); outside links open with rel=noopener",
          not re.search(r'<(script|link)[^>]+(src|href)="https?://', html) and all("noopener" in m for m in re.findall(r'<a [^>]*href="https?://[^>]*>', html)))
    check("a. the rule and the key facts: 30% pot, 15.3% on 92.35%, $2,000 1099 threshold, 90% / 100% / 110% safe harbor, $5 / 300 sq ft",
          all(x in html for x in ("30% of every payout", "15.3%", "92.35%", "$2,000", "90%", "100% of last year", "110%", "$5 a square foot", "300 sq ft")))
    check("a. the owner's real prices, never list prices", "$91.80" in html and "$63 / $43" in html and "$153" not in html and "$105" not in html)
    low = (html + js).lower()
    check("a. no private details (account ids, emails, the owner's name) on the page",
          not re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", html + js) and "dcondax" not in low and "zlarior" not in low)
    check("a. Kalshi's treatment is marked as unclear; the state card is Maryland",
          "Unclear" in html and "Your state: Maryland" in html)
    # the 30% default is the same everywhere a tax set-aside is suggested
    oc, lc, py = read(WEB, "oikos", "oikoscore.js"), read(WEB, "ledger", "ledgercore.js"), read(ROOT, "tools", "money", "oikos.py")
    check("a. Oikos, the Ledger and the Oikos scanner all default to the same 30% as this page",
          "tax: 0.30" in oc and "taxPct: 30 }" in oc and "{ taxPct: 30 }" in lc and '"tax": 0.30' in py and "DEFAULT_PCT = 30" in js
          and 'value="30"' in read(WEB, "oikos", "index.html"), None)


NODE = r"""
const T = require(process.argv[1]);
const d = (t) => T.dueDates(t, 4).map((r) => T.iso(r.due) + '|' + r.period);
const out = {
  nov: d('2026-11-17'), onDay: T.iso(T.dueDates('2027-01-15', 1)[0].due), after: T.iso(T.dueDates('2027-01-16', 1)[0].due),
  y28: d('2027-09-16'), y22: T.dueDates('2022-04-01', 1).map((r) => T.iso(r.due)), dflt: T.dueDates(undefined, 4).length,
  s1: T.split(1000, 30), s2: T.split(2800), s3: T.split('$1,234.50', 25), junk: [T.split('x', 30), T.split(-50, 30), T.split(100, 999), T.split(100, -5)],
  usd: [T.usd(300), T.usd(1960), T.usd(308.63)], fmt: T.fmtDate(T.dueDates('2026-11-17', 1)[0].due), pct: T.DEFAULT_PCT,
};
console.log(JSON.stringify(out));
"""


def part_b():
    try:
        r = subprocess.run(["node", "-e", NODE, os.path.join(BIZ, "taxes.js")], capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as e:
        check("b. node runs taxes.js", False, e)
        return
    if r.returncode != 0:
        check("b. node runs taxes.js", False, r.stderr[-400:])
        return
    o = json.loads(r.stdout)
    check("b. from 2026-11-17 the next 4 due dates are Jan 15, Apr 15, Jun 15, Sep 15 2027, each with its months",
          o["nov"] == ["2027-01-15|Sep - Dec 2026", "2027-04-15|Jan - Mar 2027", "2027-06-15|Apr - May 2027", "2027-09-15|Jun - Aug 2027"], o["nov"])
    check("b. a due date counts on its own day; the day after moves to the next one", o["onDay"] == "2027-01-15" and o["after"] == "2027-04-15", o)
    check("b. Jan 15, 2028 (a Saturday, then MLK Day) moves to Jan 18, 2028", o["y28"][0] == "2028-01-18|Sep - Dec 2027", o["y28"])
    check("b. Apr 15, 2022 (Friday, Emancipation Day observed) moves to Apr 18 like the IRS did", o["y22"] == ["2022-04-18"], o["y22"])
    check("b. with no date it uses today and still gives 4 dates", o["dflt"] == 4, o["dflt"])
    s1, s2, s3 = o["s1"], o["s2"], o["s3"]
    check("b. $1,000 at 30% -> $300 to the pot, $700 yours; $2,800 at the default -> $840 / $1,960; '$1,234.50' at 25% -> 308.63 / 925.87",
          (s1["pot"], s1["yours"]) == (300, 700) and (s2["pct"], s2["pot"], s2["yours"]) == (30, 840, 1960) and (s3["pot"], s3["yours"]) == (308.63, 925.87), (s1, s2, s3))
    j = o["junk"]
    check("b. junk or a negative payout gives 0 / 0; the percent is kept to 0..60",
          j[0]["pot"] == 0 and j[0]["yours"] == 0 and j[1]["pot"] == 0 and j[2]["pct"] == 60 and j[2]["pot"] == 60 and j[3]["pct"] == 0 and j[3]["yours"] == 100, j)
    check("b. money and dates read plainly: $300, $1,960, $308.63, 'Jan 15, 2027'; default 30",
          o["usd"] == ["$300", "$1,960", "$308.63"] and o["fmt"] == "Jan 15, 2027" and o["pct"] == 30, o)


NODE_D = r"""
const T = require(process.argv[1]);
console.log(JSON.stringify({
  w1: T.waterfall(800, 30, 0, 0), w5: T.waterfall(4000, 30, 0, 0), full: T.waterfall(800, 30, 5000, 320), near: T.waterfall(800, 30, 4900, 300),
  junk: T.waterfall('x', 30, 'y', -5),
  p: [T.potPct(5000, false), T.potPct(15000, false), T.potPct(30000, true), T.potPct(60000, false), T.potPct(100000, true), T.potPct('x')],
}));
"""


def part_d():
    """2026-11-20 keep-the-most: the payout waterfall and the set-aside % table (tools/money/keep_most.py)."""
    r = subprocess.run(["node", "-e", NODE_D, os.path.join(BIZ, "taxes.js")], capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        check("d. node runs the waterfall", False, r.stderr[-400:])
        return
    o = json.loads(r.stdout)
    w1, w5, full, near = o["w1"], o["w5"], o["full"], o["near"]
    check("d. $800 landed -> $240 tax / $80 reserve / $80 retirement / $160 live / $240 yours",
          (w1["pot"], w1["reserve"], w1["retire"], w1["live"], w1["yours"]) == (240, 80, 80, 160, 240), w1)
    check("d. $4,000 landed -> $1,200 / $320 (reserve capped) / $400 / $800 / $1,280",
          (w5["pot"], w5["reserve"], w5["retire"], w5["live"], w5["yours"]) == (1200, 320, 400, 800, 1280), w5)
    check("d. full buckets give their share back: $800 -> $480 yours; near-full buckets take only what is missing",
          full["yours"] == 480 and full["live"] == 0 and full["reserve"] == 0 and near["live"] == 100 and near["reserve"] == 20, (full, near))
    check("d. junk gives 0 everywhere", all(o["junk"][k] == 0 for k in ("pot", "reserve", "retire", "live", "yours")), o["junk"])
    check("d. Maryland set-aside %: $5k only trading 15, $15k 20, $30k + day job 40, $60k 30, $100k + day job 45, unknown 25",
          o["p"] == [15, 20, 40, 30, 45, 25], o["p"])
    html = read(BIZ, "taxes.html")
    check("d. the page has the waterfall, the %-table, the no-penalty card, the ladder, the live trigger and the Maryland card",
          all(x in html for x in ('id="wfYours"', 'id="s-pct"', 'id="s-pen"', 'id="s-ladder"', 'id="s-live"', "Tell Claude your county", "$5,000 in the live fund")))


def part_e():
    """tools/money/keep_most.py: the tax math behind the page (2026 + 2027 IRS tables)."""
    from tools.money import keep_most as K
    t = K.tax(30000, 0, 0, 2026, qbi=False)
    check("e. $30,000 profit, no job, 2026: SE tax $4,239 + income tax $1,178 = $5,417 (18.1%)",
          abs(t["se"] - 4238.9) < 1 and abs(t["total"] - 5416.92) < 1, t)
    check("e. SE tax stops at the Social Security base ($184,500 2026, $192,300 2027); 2027 std deduction $16,600",
          K.YEARS[2026]["ss_base"] == 184500 and K.YEARS[2027]["ss_base"] == 192300 and K.YEARS[2027]["std"] == 16600)
    f = K.s1256(30000, 0, 2026)
    check("e. $30,000 of 60/40 futures gains with no other income: $0 federal (all in the 0% band)", f["total"] == 0, f)
    check("e. the Maryland set-aside % the page uses = keep_most.pot_pct (highest county)",
          [K.pot_pct(5000), K.pot_pct(15000), K.pot_pct(30000, True), K.pot_pct(60000), K.pot_pct(100000, True)] == [15, 20, 40, 30, 45])
    m = K.md_tax(30000 - 2119.5, 0.032)
    check("e. Maryland on $27,880 AGI, county 3.20%: state $961 + county $683 (std $3,350, exemption $3,200)", abs(m - 1643.3) < 1, m)
    f2 = K.s1256(30000, 0, 2026, K.MD_HIGH)
    check("e. Maryland taxes 60/40 futures gains as ordinary income: $30,000 -> ~$1,835 (state + county 3.30%), $0 federal", 1700 < f2["total"] < 1900, f2)
    w = K.waterfall(800)
    check("e. waterfall($800) = 240 / 80 / 80 / 160 / 240", (w["tax_pot"], w["eval_reserve"], w["retirement"], w["live_fund"], w["yours"]) == (240, 80, 80, 160, 240), w)
    check("e. S-corp break-even near $49,000 profit (Maryland)", 40000 <= K.scorp_break_even() <= 60000, K.scorp_break_even())


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def part_c():
    from playwright.sync_api import sync_playwright
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=WEB))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    port = srv.server_address[1]
    outside, errs = [], []
    try:
        with sync_playwright() as pw:
            exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
            br = pw.chromium.launch(**({"executable_path": exe} if exe else {}))
            ctx = br.new_context(viewport={"width": 390, "height": 844}, has_touch=True)

            def guard(route):
                u = route.request.url
                if u.startswith(f"http://127.0.0.1:{port}") or u.startswith(("data:", "blob:")):
                    return route.continue_()
                outside.append(u)
                return route.abort()
            ctx.route("**/*", guard)
            ctx.add_init_script("(() => { const D = Date; const fixed = new D('2026-11-17T12:00:00').getTime(); globalThis.Date = class extends D { constructor(...a) { super(...(a.length ? a : [fixed])); } static now() { return fixed; } }; })()")
            p = ctx.new_page()
            p.on("pageerror", lambda e: errs.append(str(e)))
            p.goto(f"http://127.0.0.1:{port}/business/taxes.html")
            p.wait_for_function("document.querySelectorAll('#dates li b[data-iso]').length === 4")
            dates = p.evaluate("() => [...document.querySelectorAll('#dates li b')].map((b) => b.dataset.iso)")
            check("c. phone: the four dates are drawn and the minute card names the next one",
                  dates == ["2027-01-15", "2027-04-15", "2027-06-15", "2027-09-15"] and p.inner_text("#nextDue") == "Jan 15, 2027", dates)
            p.fill("#pay", "2500")
            p.fill("#pct", "25")
            got = p.evaluate("() => [document.querySelector('#pot').textContent, document.querySelector('#mine').textContent, document.querySelector('#month').textContent]")
            check("c. phone: typing $2,500 at 25% shows $625 to the pot and $1,875 yours; the month line follows the %",
                  got[0] == "$625" and got[1] == "$1,875" and "$700 to the pot" in got[2], got)
            wide = p.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
            p.set_viewport_size({"width": 320, "height": 700})
            wide2 = p.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
            check("c. no sideways scroll at 390 px or 320 px", wide <= 0 and wide2 <= 0, (wide, wide2))
            check("c. no script errors and nothing fetched from outside", not errs and not outside, (errs, outside))
            br.close()
    finally:
        srv.shutdown()


def main():
    part_a()
    part_b()
    part_d()
    part_e()
    if "--browser" in sys.argv:
        part_c()
    ok = all(RES)
    print(f"\n{sum(RES)}/{len(RES)} passed" + ("" if ok else "  FAILURES"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
