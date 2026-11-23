"""THE MONEY PIPELINE (lead 2026-11-22: "the owner sees calls turn into dollars"; the Corvette fund).

    python -X utf8 -m tests.test_money_pipeline        (--static: no browser)
a. agency/pipeline.py: dials / talks / proposals from the callers' logs; deposits, live sites, setup $, monthly recurring, cleared $ from the
   CLEARED payments only (a caller's 'won' is no money); a refund takes its money back out; no deposit = the no-upfront plan; the card is counts + $ only
b. pipelinecore.js in node: the funnel, the phone-log fallback (no $), trading payouts from home.json, the goal ($70,000 default, editable, manual adds)
c. browser 390 x 844: no PC card -> the phone's log counts; with a PC card -> its $; the goal edit + a manual add persist after a reload; 44 px, no
   sideways scroll, no page error
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
W = os.path.join(ROOT, "tools", "web_public")
FAILS: list = []
N = [0]


def check(name, ok, info=""):
    N[0] += 1
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  [{str(info)[:400]}]"))
    if not ok:
        FAILS.append(name)


LOG = [{"id": "a1", "k": "called", "t": 1}, {"id": "a1", "k": "interested", "t": 2}, {"id": "b2", "k": "voicemail", "t": 3},
       {"id": "c3", "k": "won", "t": 4}, {"id": "a1", "k": "proposal", "t": 5}, {"id": "a1", "k": "proposal", "t": 6}, {"id": "x", "k": "emailed", "t": 7}]


def py_rules():
    from agency import pipeline as AP
    A = AP.amounts()
    check("a. the price book's amounts: deposit $750, launch $750, care $79, no-upfront $149", A == {"deposit": 750, "launch": 750, "care": 79, "no_upfront": 149}, A)
    c = AP.summary(LOG, [], today="2026-11-22")
    check("a. the calls: 4 dials, 3 talks, proposals counted once per business; a 'won' with no money = 0 sold, $0",
          (c["dials"], c["talks"], c["proposals"], c["sold"], c["cleared"], c["deposits"]) == (4, 3, 1, 0, 0, 0), c)
    pays = [{"id": "p1", "kind": "deposit", "t": "2026-11-02"}, {"id": "p1", "kind": "launch", "t": "2026-11-12"},
            {"id": "p2", "kind": "deposit", "t": "2026-11-05"},
            {"id": "p3", "kind": "monthly", "t": "2026-09-20"}, {"id": "p3", "kind": "monthly", "t": "2026-10-20"}, {"id": "p3", "kind": "monthly", "t": "2026-11-20"},
            {"id": "p4", "kind": "deposit", "t": "2026-10-01"}, {"id": "p4", "kind": "refund", "t": "2026-10-03"}]
    c = AP.summary(LOG, pays, today="2026-11-22")
    check("a. cleared only: p1 (deposit + launch) and p3 (3rd monthly) sold; p2 (deposit only) is not; p4 refunded is not",
          c["sold"] == 2 and c["deposits"] == 3 and c["live"] == 2, c)
    check("a. the $: setup = 3 deposits + 1 launch - the refund ($2,250), MRR = care $79 + no-upfront $149, cleared $2,697",
          c["setup"] == 2250 and c["mrr"] == 228 and c["cleared"] == 1500 + 750 + 447 + 0, c)
    check("a. this month's money in: Nov payments only", c["month_in"] == 750 + 750 + 750 + 149, c)
    keys = set(c)
    check("a. the card is counts + $ only (no names, no phone numbers, no ids)",
          keys == {"v", "kind", "t", "day", "dials", "talks", "proposals", "deposits", "live", "sold", "setup", "mrr", "cleared", "month_in"}
          and all(isinstance(c[k], int) for k in keys - {"kind", "day"}), keys)
    d = tempfile.mkdtemp()
    try:
        p = os.path.join(d, "s.json")
        AP.write_card(c, p)
        check("a. write_card / read_card round trip; a wrong file reads as None", AP.read_card(p) == c and AP.read_card(os.path.join(d, "none.json")) is None)
        with open(os.path.join(d, "portal_log.json"), "w") as f:
            json.dump({"log": LOG}, f)
        with open(os.path.join(d, "agency_paid.json"), "w") as f:
            json.dump({"payments": pays}, f)
        b = AP.build_card(d, today="2026-11-22")
        check("a. build_card reads the PC's portal_log.json + agency_paid.json", b["sold"] == 2 and b["dials"] == 4, b)
    finally:
        shutil.rmtree(d, ignore_errors=True)
    gi = open(os.path.join(ROOT, ".gitignore"), encoding="utf-8").read()
    check("a. the card's folder is gitignored (data/agency_pipeline/)", "data/agency_pipeline/" in gi)


NODE = r"""
import * as C from '%s';
const out = {};
out.log = C.fromLog(%s);
out.card = C.fromCard({kind:'agency-pipeline', dials:10, talks:6, proposals:3, deposits:2, live:1, sold:1, setup:2250, mrr:79, cleared:2329, t:5});
out.bad = C.fromCard({kind:'other'});
out.fun = C.funnel(out.card);
out.trade = C.tradingPayouts({goals:{money:{payouts:[{to_you:400},{to_you:1000.5},{gross:9}]}}});
out.def = C.loadGoal(null); out.junk = C.loadGoal('{bad'); out.lowT = C.loadGoal('{"target":5}');
const g = C.loadGoal(null); out.e1 = C.addManual(g, '0', 'website', 1); out.e2 = C.addManual(g, '500', 'cash', 1); out.ok = C.addManual(g, '500', 'trading', 1);
out.goal = C.goal(g, 2329, 1400.5); out.over = C.goal({target:1000, manual:[]}, 5000, 0);
out.usd = C.usd(70000);
console.log(JSON.stringify(out));
"""


def node_core():
    node = shutil.which("node")
    if not node:
        check("b. node is installed", False)
        return
    js = NODE % (os.path.join(W, "business", "pipelinecore.js").replace("\\", "/"), json.dumps(LOG))
    d = tempfile.mkdtemp()
    try:
        p = os.path.join(d, "t.mjs")
        with open(p, "w", encoding="utf-8") as f:
            f.write(js)
        r = subprocess.run([node, p], capture_output=True, text=True, timeout=60)
    finally:
        shutil.rmtree(d, ignore_errors=True)
    if r.returncode:
        check("b. the core runs in node", False, r.stderr)
        return
    o = json.loads(r.stdout)
    check("b. the phone's log: the same counts as the PC (4 / 3 / 1), never $ (null = 'on the PC card')",
          (o["log"]["dials"], o["log"]["talks"], o["log"]["proposals"]) == (4, 3, 1) and o["log"]["cleared"] is None and o["log"]["setup"] is None, o["log"])
    check("b. the PC card is read; a wrong kind is ignored", o["card"]["cleared"] == 2329 and o["bad"] is None)
    check("b. the funnel: 5 steps in order, each with its share of the step before",
          [s["label"] for s in o["fun"]] == ["Dials", "Talks", "Proposals sent", "Deposits", "Live sites"] and [s["rate"] for s in o["fun"]] == [None, 60, 50, 67, 50], o["fun"])
    check("b. trading payouts = what reached you (to_you), from home.json", abs(o["trade"] - 1400.5) < 1e-9, o["trade"])
    check("b. the goal: 'Corvette fund' $70,000 by default; junk or a too-small target falls back",
          o["def"]["target"] == 70000 and o["def"]["name"] == "Corvette fund" and o["junk"]["target"] == 70000 and o["lowT"]["target"] == 70000)
    check("b. manual adds: $0 and an unknown source are refused; a good one counts", "error" in o["e1"] and "error" in o["e2"] and o["ok"] == {"ok": True})
    check("b. the bar = cleared website $ + trading payouts + your adds; capped at 100%",
          abs(o["goal"]["have"] - (2329 + 1400.5 + 500)) < 1e-6 and o["goal"]["pct"] == 6.0 and o["over"]["pct"] == 100 and o["over"]["left"] == 0, o["goal"])
    check("b. dollars print as $70,000", o["usd"] == "$70,000")


def browser():
    from tests import pw_skip
    if pw_skip.missing("c. (the browser part)"):            # night-reds2: the module missing = a printed SKIP, not a FAIL
        return
    from playwright.sync_api import sync_playwright
    import http.server
    import threading
    import functools

    class Q(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            if self.path.startswith("/home.json"):
                b = json.dumps({"goals": {"money": {"payouts": [{"day": "2026-11-10", "gross": 500, "to_you": 400, "type": "sim", "name": "x"}]}}}).encode()
                self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(b)
                return
            return super().do_GET()

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Q, directory=W))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}/business/pipeline.html"
    card = {"kind": "agency-pipeline", "dials": 40, "talks": 22, "proposals": 6, "deposits": 3, "live": 2, "sold": 2, "setup": 3750, "mrr": 158, "cleared": 3908, "t": 1764000000}
    errs = []
    try:
        with sync_playwright() as p:
            b = p.chromium.launch()
            for mode in ("log", "pc"):
                ctx = b.new_context(viewport={"width": 390, "height": 844})
                pg = ctx.new_page()
                pg.on("pageerror", lambda e: errs.append(str(e)))
                ctx.route("**/ntfy.sh/**", lambda r: r.fulfill(status=200, body=""))
                lite = json.dumps({"ap": card}) if mode == "pc" else "null"
                pg.add_init_script("localStorage.setItem('agency.portal.v1', %s);"
                                   "window.__lite = %s;"
                                   "Object.defineProperty(window, 'PC_FEED', {configurable: true, set(v) { this._pf = v; }, get() {"
                                   " const f = this._pf; return f && Object.assign({}, f, {fetchLatest: async () => window.__lite}); }});"
                                   % (json.dumps(json.dumps({"caller": "T", "log": LOG})), lite))
                pg.goto(url)
                pg.wait_for_function("document.getElementById('src').textContent !== 'Loading...'")
                fun = pg.eval_on_selector_all("#funnel li b", "els => els.map(e => e.textContent)")
                if mode == "log":
                    check("c. no PC card: the funnel counts this phone's log; deposits / live / $ wait for the PC",
                          fun == ["4", "3", "1", "-", "-"] and pg.text_content("#tSetup") == "-" and "has not sent" in pg.text_content("#src"), fun)
                    check("c. the goal starts at 'Corvette fund' $70,000; trading payouts from Home count ($400)",
                          pg.text_content("#gTarget") == "$70,000" and pg.text_content("#gHave") == "$400" and "Corvette" in pg.text_content("#gName"))
                    pg.click("#gEdit")
                    pg.fill("#gTargetIn", "80000"); pg.fill("#gAmt", "1,250"); pg.select_option("#gSrc", "website"); pg.click("#gForm button[type=submit]")
                    pg.reload(); pg.wait_for_function("document.getElementById('src').textContent !== 'Loading...'")
                    check("c. the goal edit + a manual add are saved on the phone (after a reload: $80,000, $1,650)",
                          pg.text_content("#gTarget") == "$80,000" and pg.text_content("#gHave") == "$1,650", (pg.text_content("#gTarget"), pg.text_content("#gHave")))
                    pg.click("#gEdit")
                else:
                    check("c. with the PC card: its funnel + setup / monthly / cleared $; the bar adds cleared website $ to payouts",
                          fun == ["40", "22", "6", "3", "2"] and pg.text_content("#tSetup") == "$3,750" and pg.text_content("#tMrr") == "$158/mo"
                          and pg.text_content("#tCleared") == "$3,908" and pg.text_content("#gHave") == "$4,308" and "From the PC" in pg.text_content("#src"),
                          (fun, pg.text_content("#gHave")))
                small = pg.evaluate("""() => [...document.querySelectorAll('a, button, input, select')].filter(e => e.offsetParent)
                    .map(e => e.getBoundingClientRect()).filter(r => r.height < 44).length""")
                sw = pg.evaluate("document.documentElement.scrollWidth")
                check(f"c. {mode}: every tap target 44 px, no sideways scroll at 390", small == 0 and sw <= 390, (small, sw))
                ctx.close()
            b.close()
    finally:
        srv.shutdown()
    check("c. no page error", not errs, errs)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    py_rules()
    node_core()
    if "--static" not in argv:
        browser()
    print(f"\n{N[0] - len(FAILS)}/{N[0]} passed")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
