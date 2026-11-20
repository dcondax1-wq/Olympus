"""Website Business HQ (tools/web_public/agency/index.html top + hq.js + hq.css + sections.json; 2026-11-20 day-web-hub).
  a. static: the HQ sits above the untouched CRM (every CRM id still there, in its order); 7 tiles (Expert, Leads, Audit, Demos, Showcase,
     Offers, Calls) with their folder links; this week = 6 rows; hq.js text only, writes one key, sends nothing; hq.css tokens only;
     sections.json valid; wired: Money door (<= 8 shortcuts, Websites), search ('website' ... -> the HQ), Help, What's new
  b. node: compute() = next step, pipeline, MRR (no data, a due call-back, open proposals, a section summary, junk)
  c. Chromium 390 x 844, the default look + Ivory: no console error, layout shift < 0.01, no sideways scroll, HQ taps >= 44 px; a seeded
     call-back becomes the next step, a seeded section summary shows on its tile, a week tick survives a reload
    python -X utf8 -m tests.test_web_hub          (WEBHUB_NO_BROWSER=1 skips c; run c under flock -w 2400 /tmp/olympus_browser.lock)
    python -X utf8 -m tests.test_web_hub --shots  (+ research/handoff/2026-11-20/web/hub/*.png, deviceScaleFactor 2)
"""
from __future__ import annotations

import functools
import http.server
import json
import os
import re
import subprocess
import sys
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "tools", "web_public")
AG = os.path.join(WEB, "agency")
SHOTS = os.path.join(ROOT, "research", "handoff", "2026-11-20", "web", "hub")
RES: list = []
CLS_JS = """window.__cls = 0; new PerformanceObserver(l => { for (const e of l.getEntries()) if (!e.hadRecentInput) window.__cls += e.value; })
  .observe({type: 'layout-shift', buffered: true});"""


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:500]}"))


def rd(*p):
    with open(os.path.join(*p), encoding="utf-8") as f:
        return f.read()


def part_a():
    html, js, css = rd(AG, "index.html"), rd(AG, "hq.js"), rd(AG, "hq.css")
    crm = ['id="heroNum"', 'id="today"', 'id="stages"', 'id="list"', 'id="detail"', 'id="planTable"', 'id="exportBtn"']
    check("a. the HQ comes first, then the whole CRM in its order (agency.js untouched)", html.index('id="hq"') < html.index(crm[0])
          and all(html.index(crm[i]) < html.index(crm[i + 1]) for i in range(len(crm) - 1)) and '<script type="module" src="agency.js' in html)
    tiles = re.findall(r'<a class="hq-tile" data-slice="([a-z]+)" href="([^"]+)"', html)
    check("a. 7 tiles: Expert, Leads, Audit, Demos, Showcase, Offers -> their folders, Calls -> #today", tiles == [
        ("expert", "expert/"), ("leads", "leads/"), ("audit", "audit/"), ("demos", "demos/"), ("showcase", "showcase/"), ("offers", "offers/"), ("calls", "#today")], tiles)
    check("a. this week: 6 rows (Mon-Sat), each with a checkbox and a link", len(re.findall(r'<li data-day="[1-6]"><label><input type="checkbox">', html)) == 6)
    check("a. hq.js: text only, writes only agency.hq.week.v1, no POST / beacon, reads agency.crm.v1 + agency.<slice>.summary",
          not re.search(r"innerHTML|outerHTML|insertAdjacentHTML|document\.write|sendBeacon|method:\s*['\"]POST", js)
          and js.count("localStorage.setItem") == 1 and "'agency.hq.week.v1'" in js and "lsGet('agency.crm.v1')" in js and "'agency.' + k + '.summary'" in js)
    check("a. hq.css: no raw colour (every colour an --ag-* / --oly-* token)", not re.findall(r"#[0-9a-fA-F]{3,8}\b|rgba?\(", css))
    sec = json.loads(rd(AG, "sections.json"))
    check("a. sections.json: the 6 sections, each live + summary_file booleans", sorted(sec["sections"]) == sorted(["expert", "leads", "audit", "demos", "showcase", "offers"])
          and all(isinstance(v["live"], bool) and isinstance(v["summary_file"], bool) for v in sec["sections"].values()))
    doors = rd(WEB, "olympus", "doors.js")
    money = re.search(r"\{ id: 'money'.*?items: \[(.*?)\],\s*ids:", doors, re.S).group(1)
    n = len(re.findall(r"\{ label:", money))
    check(f"a. Money door: Websites -> agency/, {n} shortcuts (max 8)", "href: 'agency/'" in money and n <= 8, n)
    check("a. web_next's doors.js = the site's (byte-identical)", rd(ROOT, "web_next", "js", "next", "doors.js") == doors)
    h = json.loads(rd(WEB, "hub", "help.json"))
    w = json.loads(rd(WEB, "hub", "whatsnew.json"))
    check("a. Help + What's new carry the HQ (agency/index.html#hq)", any(i["id"] == "websites" and i["link"]["href"] == "../agency/index.html#hq" for i in h["items"])
          and any(i["href"] == "../agency/index.html#hq" for i in w["items"]))


JS = r"""
const G = require(process.argv[1]), H = require(process.argv[2]);
const first = (q) => { const r = G.findAll(q, 8); return r.actions[0] ? r.actions[0].path : r.apps[0] ? r.apps[0].path : '-'; };
const words = Object.fromEntries(['website', '3d site', 'marketing', 'leads', 'audit', 'proposal', 'clients'].map((q) => [q, first(q)]));
const none = H.compute({});
const due = H.compute({ today: '2026-11-20', leads: [{ id: 'a', name: 'Joe Plumbing' }, { id: 'b' }], crm: { leads: { a: { stage: 'callback', callback: '2026-11-19', calls: 1 }, b: { stage: 'won', monthly: 79 } } } });
const prop = H.compute({ today: '2026-11-20', leads: [{ id: 'a' }, { id: 'b' }], crm: { leads: { a: { stage: 'contacted', calls: 1, price: 999 } } } });
const sum = H.compute({ leads: [{ id: 'a' }], sums: { offers: { mrr: 300, pipe: { proposal: 4, paid: 3 }, next: 'Send the proposal to Ace Roofing' }, leads: { n: 42, label: '42 leads found' } } });
const junk = H.compute({ crm: 'x', leads: 'y', sums: { offers: 'z', audit: { n: 'NaN', pipe: { called: -5 } } } });
console.log(JSON.stringify({ words, none, due, prop, sum, junk, wk: H.isoWeek(new Date(2026, 10, 20)) }));
"""


def part_b():
    try:
        out = subprocess.run(["node", "-e", JS, os.path.join(WEB, "olympus", "gate-catalog.js"), os.path.join(AG, "hq.js")], capture_output=True, text=True, timeout=60)
        r = json.loads(out.stdout)
    except Exception as e:  # noqa: BLE001
        check("b. node runs", False, e)
        return
    check("b. search: website, 3d site, marketing, leads, audit, proposal, clients -> the HQ first", all(v == "agency/index.html#hq" for v in r["words"].values()), r["words"])
    n = r["none"]
    check("b. no data: 0 / 0 / 0 / 0, $0, next = find your first 20 leads -> leads/", n["pipe"] == {"leads": 0, "called": 0, "proposal": 0, "paid": 0} and n["mrr"] == 0
          and n["next"]["to"] == "leads/" and "20 leads" in n["next"]["text"], n)
    d = r["due"]
    check("b. a due call-back is the next step (by name); won = paid 1, its $79 = MRR (3% of the $3,000 goal: research 2026-11-20)", d["next"]["text"].startswith("Call back Joe Plumbing") and d["next"]["to"] == "#today"
          and d["pipe"] == {"leads": 2, "called": 2, "proposal": 0, "paid": 1} and d["mrr"] == 79 and d["pct"] == 3 and d["goal"] == 3000, d)
    p = r["prop"]
    check("b. a priced open lead = 1 proposal -> follow it up", p["pipe"]["proposal"] == 1 and "Follow up your 1 open proposal" == p["next"]["text"], p)
    s = r["sum"]
    check("b. section summaries: Offers' next step + MRR, the most of each stage (no double count), the Leads tile count",
          s["next"]["text"] == "Send the proposal to Ace Roofing" and s["mrr"] == 300 and s["pipe"] == {"leads": 42, "called": 0, "proposal": 4, "paid": 3} and s["pct"] == 10, s)
    j = r["junk"]
    check("b. junk in, sane out (no NaN, no negatives)", j["pipe"] == {"leads": 0, "called": 0, "proposal": 0, "paid": 0} and j["mrr"] == 0, j)
    check("b. ISO week of Fri Nov 20 2026 = 2026-W47", r["wk"] == "2026-W47", r["wk"])


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def part_c(shots):
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:  # noqa: BLE001
        print(f"[SKIP] c. browser (playwright missing: {e})")
        return
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=WEB))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}/"
    if shots:
        os.makedirs(SHOTS, exist_ok=True)
    try:
        with sync_playwright() as pw:
            br = pw.chromium.launch()
            for look in ("agora", "ivory"):
                ctx = br.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, color_scheme="dark", device_scale_factor=2 if shots else 1)
                ctx.route(re.compile(r"^https?://(?!127\.0\.0\.1)"), lambda r: r.fulfill(status=204, body=""))
                ctx.route(re.compile(r"/agency/my_leads\.json"), lambda r: r.fulfill(status=200, body="{}", content_type="application/json"))   # only on the owner's PC
                ctx.add_init_script(CLS_JS)
                if look != "agora":
                    pre = ctx.new_page()
                    pre.goto(base + "hub/doors.html")
                    pre.wait_for_function("window.OLYMPUS_THEMES && window.OLYMPUS_THEMES.set")
                    pre.evaluate(f"window.OLYMPUS_THEMES.set('{look}')")
                    pre.close()
                errs: list = []
                pg = ctx.new_page()
                pg.on("pageerror", lambda e: errs.append(str(e)))
                pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
                pg.goto(base + "agency/index.html")
                pg.wait_for_function("window.AGENCY_HQ && window.AGENCY_HQ.ready", timeout=20000)
                pg.wait_for_timeout(600)
                nxt = pg.text_content("#hqNextText")
                wide = pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
                small = pg.evaluate("[...document.querySelectorAll('#hq a, #hq button, #hq label')].filter(e => { const r = e.getBoundingClientRect(); return r.width > 0 && (r.height < 44 || r.width < 44); }).length")
                cls = pg.evaluate("window.__cls")
                if shots:
                    pg.screenshot(path=os.path.join(SHOTS, f"hq-top-{'dark' if look == 'agora' else 'light'}.png"))
                    pg.evaluate("document.querySelector('.hq-tiles').scrollIntoView({block: 'start'})")
                    pg.wait_for_timeout(200)
                    pg.screenshot(path=os.path.join(SHOTS, f"hq-tiles-{'dark' if look == 'agora' else 'light'}.png"))
                check(f"c. {look}: the next step is filled ({nxt!r}), no sideways scroll, HQ taps >= 44 px, CLS {cls:.3f} < 0.01, no console error",
                      nxt and "Working out" not in nxt and wide and small == 0 and cls < 0.01 and not errs, (nxt, wide, small, cls, errs[:3]))
                if look == "agora":
                    pg.evaluate("""(() => { const s = JSON.parse(localStorage.getItem('agency.crm.v1') || '{"v":1,"leads":{},"log":[]}');
                        s.leads['seed-x'] = { stage: 'callback', callback: '2000-01-01', calls: 1 }; localStorage.setItem('agency.crm.v1', JSON.stringify(s));
                        localStorage.setItem('agency.audit.summary', JSON.stringify({ n: 3, label: '3 sites audited', t: 1 })); })()""")
                    pg.reload()
                    pg.wait_for_function("window.AGENCY_HQ && window.AGENCY_HQ.ready", timeout=20000)
                    nxt2, aud = pg.text_content("#hqNextText"), pg.text_content('.hq-tile[data-slice="audit"] .hq-live')
                    check(f"c. a seeded due call-back is the next step ({nxt2!r}); a seeded Audit summary shows on its tile ({aud!r})",
                          nxt2.startswith("Call back") and aud == "3 sites audited", (nxt2, aud))
                    pg.check('#hqWeek li[data-day="3"] input')
                    pg.reload()
                    pg.wait_for_function("window.AGENCY_HQ && window.AGENCY_HQ.ready", timeout=20000)
                    check("c. a week tick survives a reload (this phone)", pg.is_checked('#hqWeek li[data-day="3"] input')
                          and "1 of 6" in pg.text_content("#hqWeekCount"), pg.text_content("#hqWeekCount"))
                    check("c. the CRM below still works (its list and Call today are drawn)", pg.evaluate("window.AGENCY && window.AGENCY.ready()")
                          and pg.eval_on_selector_all("#list > *", "e => e.length") > 0)
                ctx.close()
            br.close()
    finally:
        srv.shutdown()


def main():
    part_a()
    part_b()
    if not os.environ.get("WEBHUB_NO_BROWSER"):
        part_c("--shots" in sys.argv)
    n = sum(RES)
    print(f"\nweb_hub: {n}/{len(RES)} " + ("ALL PASS" if n == len(RES) else "FAILED"))
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    raise SystemExit(main())
