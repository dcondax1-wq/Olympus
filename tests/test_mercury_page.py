"""MERCURY, money machine #2 DEALS (tools/money/mercury.py + tools/web_public/mercury/, AGORA look, 2026-11-10): sales, codes, free resets and rule changes on public pages.

  a. static: the files, the kit lines, the AGORA look, read-only (no markup from data, no network except ../money/mercury.json + the fixture), the Jarvis card, the manifest, the DEMO fixture,
     the 3D scene file (warm light, no bloom, no neon), the scanner never buys / logs in / posts
  b. the scanner (python selftest with canned HTML, offline) and the contract of its fixture-mode output; the page model in node (mercurycore.js): days left, grouping, bad data
  c. Chromium 390 x 844 (and 375 x 667): the DEMO page, a real mercury.json from the scanner, no file at all, LITE / reduced motion, taps >= 44 px, no sideways scroll, no console error
    python -X utf8 -m tests.test_mercury_page            (--static: parts a and b only)
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import agora_kit as AK  # noqa: E402

APP, NAME = "mercury", "Mercury"
check = AK.check
PY = os.path.join(AK.ROOT, "tools", "money", "mercury.py")


def test_static():
    AK.static_kit(APP, NAME, reads=("../money/mercury.json",))
    d = os.path.join(AK.WEB, APP)
    html, js, s3d, py = AK.read(os.path.join(d, "index.html")), AK.read(os.path.join(d, "mercury.js")), AK.read(os.path.join(d, "mercury3d.js")), AK.read(PY)
    check("a. the page answers first: hero, 'what I would buy', deals now, ends soon, rule changes that affect you, pages watched",
          html.index('id="pickCard"') < html.index('id="dealsCard"') < html.index('id="soonCard"') < html.index('id="rulesCard"') < html.index('id="watch"') and "never buys" in html.lower())
    check("a. the 3D stage is a canvas with a label, loaded by its own optional module (the page works without it)", '<canvas id="stage"' in html and 'aria-label="A marble pedestal' in html and 'src="mercury3d.js' in html)
    check("a. the scene: marble + bronze, a warm key light, warm fog, no bloom / emissive / neon, WebGL failure hides the canvas, reduced motion / LITE draw one still frame",
          "MeshStandardMaterial" in s3d and "0xffd7a0" in s3d and "Fog(" in s3d and not re.search(r"Bloom|emissive|UnrealBloom", s3d) and "classList.add('off')" in s3d and "state.still" in s3d and not AK.BANNED_LOOK.search(s3d))
    check("a. the scene reads nothing from the network and never builds markup", not re.search(r"fetch\(|XMLHttpRequest|innerHTML|WebSocket|https?://", s3d))
    check("a. the scanner is stdlib only, one GET with a generic agent and a 10 s timeout, and has no buy / login / post code",
          not re.search(r"^\s*(?:import|from)\s+(?!argparse|datetime|hashlib|html|json|os|re|sys|tempfile|urllib|__future__)", py, re.M) and "TIMEOUT = 10" in py and "price-watch/1.0" in py
          and not re.search(r"method=['\"]POST|\.post\(|password|login\(|checkout\(|add_to_cart|card_number|api[_-]?key", py, re.I))
    check("a. the owner's real prices are in the scanner: Builder 25K $63, ATLAS 25K $43, Builder 50K $91.80", '"mffu": {25: 63.0, 50: 91.80}' in py and '"atlas": {25: 43.0}' in py)
    check("a. the page shows the price list in plain words and says a sale is not income", "$63" in html and "$43" in html and "$91.80" in html and "not income" in html)
    fx = json.load(open(os.path.join(d, "fixture.json"), encoding="utf-8"))
    check("a. the fixture follows the scanner contract (v 1, id mercury, items with title / detail / usd / score / risk, a pick, notes)",
          fx["v"] == 1 and fx["id"] == "mercury" and fx["mode"] == "paper" and fx["items"] and all({"title", "detail", "usd", "score", "risk"} <= set(i) for i in fx["items"]) and fx["pick"]["title"] and fx["notes"])


HARNESS = r"""
import(process.argv[2]).then((C) => {
  const now = new Date('2026-11-10T12:00:00Z'), o = {};
  o.money = [C.money(27.54), C.money(73), C.money(1234.5), C.money(null), C.money('x'), C.money(-5)];
  o.days = [C.daysLeft('2026-11-13', now), C.daysLeft('2026-11-10', now), C.daysLeft('2026-11-09', now), C.daysLeft('nope', now), C.daysLeft(null, now), C.daysLeft('2027-01-01', new Date('2026-11-10T23:59:00Z'))];
  o.when = [C.whenText(null), C.whenText(-1), C.whenText(0), C.whenText(1), C.whenText(3)];
  o.age = [C.ageText(0.2), C.ageText(5), C.ageText(1), C.ageText(60), C.ageText(null), C.ageHours('2026-11-10T09:00:00Z', now)];
  const doc = { v: 1, status: 'ok', asof: '2026-11-10T11:00:00Z', headline: { text: 'Best: 30% off' }, notes: ['a', '', 5],
    pick: { buy: true, title: 'Buy it', why: 'because', usd: 27.5, buy_by: '2026-11-13' },
    pages: [{ firm: 'MFFU', ok: true, owner: true }, null, { firm: 'Apex', ok: false }],
    items: [
      { id: 'a', kind: 'deal', title: '30% off', detail: 'd', usd: 27.54, score: 54, risk: 'low', expires: '2026-11-13', code: 'BLACK30', pct: 30, new: true, url: 'https://example.org/x' },
      { id: 'b', kind: 'deal', title: '80% off', detail: 'd', usd: 73.44, score: 100, risk: 'med', expires: '2026-11-10', pct: 80, url: 'javascript:alert(1)' },
      { id: 'c', kind: 'deal', title: 'Old', detail: 'd', usd: 9, score: 80, risk: 'low', expires: '2026-11-01' },
      { id: 'd', kind: 'reset', title: 'Free reset', detail: 'd', usd: 22.95, score: 60, risk: 'low', expires: '2026-12-01' },
      { id: 'e', kind: 'rule', title: 'Rule', detail: 'd', usd: null, score: 70, risk: 'med', affects_me: true },
      { id: 'f', kind: 'rule', title: 'Other rule', detail: 'd', usd: null, score: 25, risk: 'low', affects_me: false },
      { id: 'g', kind: 'weird', title: 'Odd', detail: 5, usd: 'abc', score: 999, risk: 'zzz', code: '<b>x</b>' }, { title: '' }, null, 7 ] };
  const m = C.buildModel(doc, now);
  o.model = { ok: m.ok, status: m.status, deals: m.deals.map((i) => i.id), soon: m.soon.map((i) => i.id), mine: m.rulesMine.map((i) => i.id), other: m.rulesOther.map((i) => i.id),
    pages: m.pages.length, notes: m.notes, pick: m.pick, tags: m.tags.map((t) => t.label), best: m.best && m.best.id, ageH: m.ageH, status_line: C.statusLine(m) };
  const odd = m.deals.find((i) => i.id === 'g');
  o.odd = odd && { kind: odd.kind, usd: odd.usd, score: odd.score, risk: odd.risk, code: odd.code, detail: odd.detail };
  o.url = [m.deals.find((i) => i.id === 'a').url, m.deals.find((i) => i.id === 'b').url];
  o.bad = [C.buildModel(null, now).ok, C.buildModel('x', now).ok, C.buildModel({}, now).ok, C.buildModel({ items: 'x' }, now).ok];
  const e = C.buildModel({ items: [], status: 'weird' }, now);
  o.empty = { ok: e.ok, status: e.status, pick: e.pick.title, line: C.statusLine(e), deals: e.deals.length, headline: e.headline };
  console.log(JSON.stringify(o));
});
"""


def test_scanner_and_core():
    r = subprocess.run([sys.executable, "-X", "utf8", PY, "--selftest"], capture_output=True, text=True, timeout=120)
    check("b. the scanner's own selftest on canned HTML passes (extraction, expiry, scoring, diff, polite fetch, outage)", r.returncode == 0 and "ALL PASS" in r.stdout and "[FAIL]" not in r.stdout, r.stdout[-900:] + r.stderr[-300:])
    with tempfile.TemporaryDirectory(prefix="mercury-test-") as tmp:
        r = subprocess.run([sys.executable, "-X", "utf8", PY, "--fixture", "--out", tmp], capture_output=True, text=True, timeout=60)
        doc = json.load(open(os.path.join(tmp, "mercury.json"), encoding="utf-8")) if r.returncode == 0 else {}
        sys.path.insert(0, os.path.join(AK.ROOT, "tools", "money"))
        import mercury as M  # noqa: E402
        check("b. --fixture writes mercury.json that meets the money-machine contract, status sample, mode paper, no monthly income promise",
              r.returncode == 0 and not M.contract_problems(doc) and doc["status"] == "sample" and doc["mode"] == "paper" and doc["headline"]["usd_month"] is None, (r.stderr[-300:], M.contract_problems(doc)))
        saved = json.load(open(os.path.join(AK.WEB, APP, "fixture.json"), encoding="utf-8"))
        same = [(i["title"], i["usd"], i["score"]) for i in doc["items"]] == [(i["title"], i["usd"], i["score"]) for i in saved["items"]]
        check("b. the page's fixture.json is the scanner's own fixture output (rerun it when the scanner or the sample pages change)", same, "regenerate: python tools/money/mercury.py --fixture --out X, then add demo + note")
    out = AK.node(APP, HARNESS)
    if out is None:
        print("[SKIP] node is not installed: the page model checks were skipped")
        return
    check("b. node: money words", out["money"] == ["$27.54", "$73", "$1,234.50", "n/a", "n/a", "-$5"], out["money"])
    check("b. node: days left (end date minus today, bad dates are null), plain 'ends in' words", out["days"] == [3, 0, -1, None, None, 52] and out["when"] == ["No end date on the page", "Over", "Ends today", "Ends tomorrow", "Ends in 3 days"], (out["days"], out["when"]))
    check("b. node: age words", out["age"][:5] == ["Checked a few minutes ago", "Checked 5 hours ago", "Checked 1 hour ago", "Checked 3 days ago", "Check time unknown"] and out["age"][5] == 3, out["age"])
    m = out["model"]
    check("b. node: deals sorted by score, an ended offer dropped, rules split into 'affects you' and 'other'", m["deals"] == ["b", "g", "d", "a"] and "c" not in m["deals"] and m["mine"] == ["e"] and m["other"] == ["f"], m)
    check("b. node: 'ends soon' = within 7 days, soonest first", m["soon"] == ["b", "a"], m["soon"])
    check("b. node: pick, headline, pages, notes, tags for the 3D scene, status line", m["pick"]["buy"] and m["pick"]["buyBy"] == "2026-11-13" and m["pages"] == 2 and m["notes"] == ["a", "5"] and m["tags"][0] == "80% OFF" and m["tags"][-1] == "RULE"
          and m["best"] == "b" and "deals found" in m["status_line"] and "1 rule change to read" in m["status_line"], m)
    check("b. node: junk rows are made safe (kind / risk / score clamped, a code with markup dropped), only https links survive", out["odd"] == {"kind": "deal", "usd": None, "score": 100, "risk": "med", "code": None, "detail": "5"} and out["url"] == ["https://example.org/x", None], (out["odd"], out["url"]))
    check("b. node: nothing / junk in -> not ok, never throws; an empty list says 'No deals found'", out["bad"] == [False] * 4 and out["empty"]["ok"] and out["empty"]["status"] == "stale" and out["empty"]["deals"] == 0 and out["empty"]["line"].startswith("No deals found") and out["empty"]["pick"] == "Nothing worth buying now", out["empty"])


def test_page():
    try:
        import playwright  # noqa: F401
    except Exception:
        print("[SKIP] playwright is not installed: part c skipped")
        return
    with tempfile.TemporaryDirectory(prefix="mercury-page-") as tmp:
        subprocess.run([sys.executable, "-X", "utf8", PY, "--fixture", "--out", tmp], check=True, capture_output=True, timeout=60)
        real = json.load(open(os.path.join(tmp, "mercury.json"), encoding="utf-8"))
    real["status"] = "ok"
    real["asof"] = "2026-11-10T11:00:00Z"
    real["headline"]["text"] = "Best deal now: 30% off at MyFundedFutures, about $27.54 saved (estimate)."
    srv, origin = AK.serve({"/money/mercury.json": json.dumps(real)})
    try:
        with AK.browser() as br:
            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, APP, "?demo=1")
            r = p.evaluate("""() => ({ demo: !document.querySelector('#demo').hidden, h: document.querySelector('#headline').textContent, deals: document.querySelectorAll('#deals li.it').length,
              soon: document.querySelectorAll('#soon li.it').length, rules: document.querySelectorAll('#rules li.it').length, pick: document.querySelector('#pickTitle').textContent,
              h1: document.querySelectorAll('h1').length, copy: [...document.querySelectorAll('#deals button')].some((b) => /Copy code/.test(b.textContent)) })""")
            check("c. ?demo=1: the DEMO chip, a headline, deals with copy-code buttons, an 'ends soon' list, rules that affect me, and a pick", r["demo"] and "Best deal" in r["h"] and r["deals"] >= 3 and r["soon"] >= 1 and r["rules"] >= 1 and r["pick"] and r["copy"] and r["h1"] == 1, r)
            check("c. 390 x 844: no sideways scroll, every tap >= 44 px, nothing under Jarvis's corner, no console error, nothing off the page's origin", AK.no_sideways(p) and not AK.taps(p) and not AK.corner(p) and not errs and not off, (AK.taps(p)[:3], AK.corner(p), errs[:3], off[:3]))
            p.wait_for_timeout(2500)
            st = p.evaluate("() => ({ on: document.documentElement.getAttribute('data-stage'), n: window.MERCURY3D ? window.MERCURY3D.tags() : -1, off: document.querySelector('.stage').classList.contains('off') })")
            check("c. the marble scene drew (or, with no WebGL here, the canvas is hidden and the page still works) with one tag per deal", (st["on"] == "on" and st["n"] >= 3) or st["off"] or st["n"] == -1, st)
            AK.shot(p, "mercury")
            ctx.close()
            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, APP)
            r = p.evaluate("() => ({ demo: !document.querySelector('#demo').hidden, h: document.querySelector('#headline').textContent, asof: document.querySelector('#asof').textContent })")
            check("c. the scanner's real file (status ok): no DEMO chip, its headline and 'Checked 1 hour ago' are shown, the file was read", not r["demo"] and "$27.54" in r["h"] and "Checked" in r["asof"] and any("money/mercury.json" in u for u in seen), r)
            ctx.close()
        srv.shutdown()
        srv, origin = AK.serve({"/money/mercury.json": None})
        with AK.browser() as br:
            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, APP)
            r = p.evaluate("() => ({ demo: !document.querySelector('#demo').hidden, deals: document.querySelectorAll('#deals li.it').length })")
            check("c. no scanner file at all: the DEMO fixture shows, never a blank page", r["demo"] and r["deals"] >= 3 and not errs, (r, errs[:2]))
            ctx.close()
            ctx, p, errs, seen, off = AK.page(br, origin, w=375, h=667, reduced=True, lite=True)
            AK.open_app(p, origin, APP, "?demo=1&q=low")
            check("c. 375 x 667, LITE, reduced motion: no sideways scroll, every tap >= 44 px, no error", AK.no_sideways(p) and not AK.taps(p) and not errs, (AK.taps(p)[:3], errs[:2]))
            ctx.close()
    finally:
        srv.shutdown()


if __name__ == "__main__":
    test_static()
    test_scanner_and_core()
    if "--static" not in sys.argv:
        test_page()
    AK.finish()
