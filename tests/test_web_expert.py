"""Agency > Expert (team web-expert 2026-11-20, owner: "an expert expert on marketing 3D websites"): tools/web_public/agency/expert/.
  a. playbook.json: the offers (Starter / Growth / 3D / care ...) with sane $ ranges, every trade with a 3D verdict, an offer that exists and
     the words to say, the playbooks (say / do / $), the 5 diagnosis questions; nothing private, no promises ("#1 on Google", "guaranteed")
  b. expertcore.js in node: the diagnosis (an emergency trade never gets 3D; a premium visual business does; a restaurant starts with the
     Google listing; few reviews adds the profile fix; every site gets the care plan) and the free-question finder
  c. the page at 390 x 844, dark and Ivory: 5 taps -> the offer, the price, the words to say; search; no sideways scroll; every control
     44 px+; sentences 15 px+; no page errors; text drawn with textContent only (no innerHTML in expert.js)
  d. Jarvis answers from the same file (node tests/test_jarvis_biz.mjs runs the 'web' checks)
    python -X utf8 -m tests.test_web_expert      (a local server, ~30 s)
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
EX = os.path.join(WEB, "agency", "expert")
RESULTS = []


def check(name, ok, info=None):
    RESULTS.append((name, bool(ok)))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:400]}"))


def part_a():
    P = json.load(open(os.path.join(EX, "playbook.json"), encoding="utf-8"))
    offers = {o["id"]: o for o in P["offers"]}
    check("a. the offers: Starter, Growth, 3D / immersive, care plan, local plan, Google profile fix, ads",
          {"starter", "growth", "immersive", "care", "local", "gbp", "ads"} <= set(offers), sorted(offers))
    check("a. every offer has a $ range low < high, whole dollars, a plain description",
          all(isinstance(o["usd_low"], int) and isinstance(o["usd_high"], int) and 0 < o["usd_low"] < o["usd_high"] and len(o["what"]) > 30 for o in P["offers"]), None)
    check("a. the ladder makes sense: Starter < Growth < 3D (low and high ends)",
          offers["starter"]["usd_high"] <= offers["growth"]["usd_high"] <= offers["immersive"]["usd_high"] and offers["starter"]["usd_low"] < offers["growth"]["usd_low"] < offers["immersive"]["usd_low"], None)
    ok = all(n["three_d"] in ("sells", "maybe", "gimmick") and n["offer"] in offers and len(n["say"]) > 60 and n["hook"] and n["pain"] for n in P["niches"])
    check(f"a. {len(P['niches'])} trades, each with a 3D verdict, an offer that exists, the pain, the hook and the words to say", ok and len(P["niches"]) >= 10, None)
    v = {k: [n["id"] for n in P["niches"] if n["three_d"] == k] for k in ("sells", "maybe", "gimmick")}
    check("a. 3D sells for venues / builders / real estate / landscapers / furniture; a gimmick for plumbers, lawyers, restaurants",
          {"venue", "builder", "realestate", "landscaper", "furniture"} <= set(v["sells"]) and {"plumber", "lawyer", "restaurant"} <= set(v["gimmick"]), v)
    topics = {c["id"] for c in P["cards"]}
    need = {"positioning", "pricing", "price3d", "when3d", "outreach", "objections", "localseo", "gbp", "reviews", "conversion", "ads", "retainers", "upsells", "process"}
    check("a. the playbooks: positioning, pricing, 3D pricing, when 3D sells, cold outreach, objections, local SEO, Google profile, reviews, conversion, ads, retainers, upsells, process",
          need <= topics, sorted(need - topics))
    check("a. every playbook has the words to say and what to do", all(c["say"] and c["do"] and c["title"] for c in P["cards"]), None)
    qs = P["diagnose"]["questions"]
    check("a. the diagnosis: 5 questions (trade, site, reviews, visual, budget), each 2+ options",
          [q["id"] for q in qs] == ["trade", "site", "reviews", "visual", "budget"] and all(len(q["options"]) >= 2 for q in qs), [q["id"] for q in qs])
    raw = open(os.path.join(EX, "playbook.json"), encoding="utf-8").read().lower()
    check("a. honest: no promise of '#1 on Google' or 'guaranteed' results (only as what to avoid), no private details",
          "demetrades" not in raw and "@gmail" not in raw and "guaranteed results" not in raw and raw.count("#1 on google") == raw.count("promising '#1 on google'"), None)


NODE = r"""
const E = await import(process.argv[1] + '/expertcore.js');
const P = JSON.parse(require('fs').readFileSync(process.argv[1] + '/playbook.json', 'utf8'));
const d = (a) => { const x = E.diagnose(a, P); return { offer: x.offer && x.offer.id, total: x.total, addons: x.addons.map((y) => y.id), niche: x.niche && x.niche.id, script: !!x.script, why: x.why.length }; };
const out = {
  plumber: d({ trade: 'trades_fast', site: 'none', reviews: 'few', visual: 'no', budget: 'premium' }),
  builder: d({ trade: 'trades_big', site: 'old', reviews: 'many', visual: 'yes', budget: 'premium' }),
  venue_tight: d({ trade: 'places', site: 'old', reviews: 'some', visual: 'yes', budget: 'tight' }),
  venue_normal: d({ trade: 'places', site: 'ok', reviews: 'some', visual: 'yes', budget: 'normal' }),
  food: d({ trade: 'food', site: 'ok', reviews: 'some', visual: 'no', budget: 'normal' }),
  lawyer_ok: d({ trade: 'pro', site: 'ok', reviews: 'many', visual: 'no', budget: 'normal' }),
  none_tight: d({ trade: 'health', site: 'none', reviews: 'few', visual: 'no', budget: 'tight' }),
  find: ['how do I price a 3D site', 'what do I say to a roofer', 'best niche for 3D', 'they say too expensive', 'google business profile', 'nothing here at all'].map((q) => { const f = E.find(q, P); return f ? f.kind + ':' + f.item.id : null; }),
  money: E.money(1500), sells: E.sells3d(P).map((n) => n.id),
};
console.log(JSON.stringify(out));
"""


def part_b():
    out = subprocess.run(["node", "--input-type=commonjs", "-e", "(async () => {" + NODE.replace("const E = await import(process.argv[1] + '/expertcore.js');", "const E = await import('file://' + process.argv[1] + '/expertcore.js');") + "})()", EX],
                         capture_output=True, text=True, timeout=60)
    try:
        r = json.loads(out.stdout.strip().splitlines()[-1])
    except Exception:                                       # noqa: BLE001 - reported
        check("b. expertcore.js runs in node", False, out.stderr[-400:]); return
    check("b. an emergency trade never gets 3D, even premium (Growth at most); its words are the plumber's", r["plumber"]["offer"] in ("starter", "growth") and r["plumber"]["niche"] == "plumber", r["plumber"])
    check("b. a premium builder whose customers must see the work: the 3D / immersive site + care plan", r["builder"]["offer"] == "immersive" and "care" in r["builder"]["addons"] and r["builder"]["niche"] == "builder", r["builder"])
    check("b. a visual business on a tight budget: Growth now, the 3D piece later", r["venue_tight"]["offer"] == "growth" and "3d-later" in r["venue_tight"]["addons"], r["venue_tight"])
    check("b. a restaurant: the Google listing first, then a Starter site", r["food"]["offer"] == "gbp" and "starter" in r["food"]["addons"], r["food"])
    check("b. a decent site with many reviews: sell results (the local plan), not a new site", r["lawyer_ok"]["offer"] == "local", r["lawyer_ok"])
    check("b. no site, few reviews, tight budget: Starter + the Google profile fix + care plan, with a price total", r["none_tight"]["offer"] == "starter" and {"gbp", "care"} <= set(r["none_tight"]["addons"]) and "$1,500" in r["none_tight"]["total"], r["none_tight"])
    check("b. every result has words to say and a reason", all(v["script"] and v["why"] >= 1 for k, v in r.items() if isinstance(v, dict)), None)
    check("b. free questions find the right card or trade (3D price, roofer, best 3D niche, objections, Google profile; nothing for nonsense)",
          r["find"] == ["card:price3d", "niche:roofer", "card:when3d", "card:objections", "card:gbp", None], r["find"])
    check("b. money() and the 3D trades list", r["money"] == "$1,500" and "venue" in r["sells"] and "plumber" not in r["sells"], (r["money"], r["sells"]))


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a, **k):
        pass


def part_c():
    from playwright.sync_api import sync_playwright
    js = open(os.path.join(EX, "expert.js"), encoding="utf-8").read()
    check("c. expert.js draws with textContent only (no innerHTML / insertAdjacentHTML), an ES module", "innerHTML" not in js and "insertAdjacentHTML" not in js and "import {" in js, None)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=WEB))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}/agency/expert/"
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch()
            for look in ("dark", "ivory"):
                ctx = b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True, service_workers="block")
                ctx.route(re.compile(r"^https?://(?!127\.0\.0\.1)"), lambda r: r.abort())
                if look == "ivory":
                    ctx.add_init_script("try { localStorage.setItem('olympus.theme', 'ivory'); localStorage.setItem('olympus.theme.v', '2'); } catch (e) {}")
                p = ctx.new_page()
                errs = []
                p.on("pageerror", lambda e: errs.append(str(e)))
                p.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
                p.goto(url, wait_until="load")
                p.wait_for_function("window.EXPERT && window.EXPERT.ready", timeout=15000)
                p.wait_for_timeout(400)
                for label in ("Big projects", "Old or slow", "Under 10", "Yes: the place", "Premium"):
                    p.locator(".ex-opt", has_text=label).first.tap()
                res = p.locator("#dx").inner_text()
                check(f"c[{look}]. 5 taps -> the 3D / immersive site, its $ range, the care plan, the Google profile fix, the builder's words",
                      "3D / immersive site" in res and "$6,000-$15,000" in res and "care plan" in res.lower() and "Google Business Profile fix" in res and "What to say (Home builder" in res, res[:300])
                p.fill("#find", "roofer")
                p.wait_for_timeout(400)
                first = p.locator("#cards details").first
                check(f"c[{look}]. search 'roofer': the roofer's card first, open, with the words to say", first.get_attribute("id") == "ni-roofer" and first.get_attribute("open") is not None and "Most homeowners" in first.inner_text(), first.get_attribute("id"))
                m = p.evaluate("""() => ({ sw: document.documentElement.scrollWidth, w: innerWidth, bg: getComputedStyle(document.body).backgroundColor,
                  small: [...document.querySelectorAll('button, a, summary, input')].filter((e) => { const r = e.getBoundingClientRect(); return r.width && r.height < 44; }).map((e) => e.tagName + ':' + e.textContent.slice(0, 20)),
                  tiny: [...document.querySelectorAll('p, li, span, td, summary, button')].filter((e) => e.getClientRects().length && e.textContent.trim().length > 12 && parseFloat(getComputedStyle(e).fontSize) < 15).map((e) => e.tagName + ':' + e.textContent.slice(0, 24)).slice(0, 5) })""")
                check(f"c[{look}]. no sideways scroll at 390 px, every control 44 px+, sentences 15 px+", m["sw"] <= m["w"] and not m["small"] and not m["tiny"], m)
                if look == "ivory":
                    rgb = [int(x) for x in re.findall(r"\d+", m["bg"])[:3]]
                    check("c[ivory]. the Ivory look paints the page light", sum(rgb) / 3 > 180, m["bg"])
                check(f"c[{look}]. no page errors", not errs, errs[:3])
                ctx.close()
            b.close()
    finally:
        srv.shutdown()


def main():
    part_a()
    part_b()
    part_c()
    bad = [n for n, ok in RESULTS if not ok]
    print(f"\nweb expert: {len(RESULTS) - len(bad)}/{len(RESULTS)} {'ALL PASS' if not bad else 'FAILED'}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
