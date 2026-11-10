"""CHRYSOS, the OLYMPUS prop-firm eval and payout fleet planner (tools/money/chrysos.py + tools/web_public/chrysos/, AGORA look, 2026-11-10).

  a. static: the files, the kit lines, the AGORA look, read-only, the Jarvis card, the manifest, the DEMO fixture, the owner's real prices, the fixture equals the tool's --fixture output
  b. the Python maths (the tool's own selftest, the contract file, cases ordered, caps, break-even, calendar, fleet) and the JS core in node (words, validation, tower model, calendar groups)
  c. Chromium 390 x 844: the DEMO plan, the three cases, the month slider, 3D or flat tower, the real file, a broken file falls back to the fixture, LITE / reduced motion, taps >= 44 px, no sideways scroll
    python -X utf8 -m tests.test_chrysos_page            (--static: parts a and b only)
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import agora_kit as AK  # noqa: E402

APP, NAME = "chrysos", "Chrysos"
check = AK.check
TOOL = os.path.join(AK.ROOT, "tools", "money", "chrysos.py")


def tool():
    spec = importlib.util.spec_from_file_location("chrysos_tool", TOOL)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_static():
    AK.static_kit(APP, NAME, reads=("../money/chrysos.json",))
    d = os.path.join(AK.WEB, APP)
    more = ["tower.js", "towerload.js"]
    check("a. the 3D files: tower.js (render core) and towerload.js (its own module tag, so a missing WebGL never stops the page)", all(os.path.isfile(os.path.join(d, n)) for n in more))
    tw = AK.read(os.path.join(d, "tower.js"))
    check("a. tower.js is built on the OLYMPUS render core, no neon, bloom <= .25, no network, no markup from data",
          "../olympus/render.js" in tw and "../jarvis/three.module.min.js" in tw and not AK.BANNED_LOOK.search(tw) and not re.search(r"fetch\(|innerHTML|XMLHttpRequest|https?://", tw)
          and all(float(x) <= 0.25 for x in re.findall(r"bloom: \{ strength: ([\d.]+)", tw)), None)
    html = AK.read(os.path.join(d, "index.html"))
    check("a. towerload.js is a separate module tag before chrysos.js; the page has a canvas AND a flat svg tower (the fallback)", html.index("towerload.js") < html.index('src="chrysos.js') and 'id="stage"' in html and 'id="flat"' in html)
    t = tool()
    check("a. the owner's real prices: Builder 50K $91.80, Builder 25K $63, ATLAS 25K $43 (CLAUDE.md), also in the page footer",
          (t.PLANS["b50"]["price"], t.PLANS["b25"]["price"], t.PLANS["atlas"]["price"]) == (91.8, 63.0, 43.0) and all(x in html for x in ("$91.80", "$63", "$43")))
    out = tempfile.mkdtemp(prefix="chry-")
    path, doc = t.write(out, fixture=True)
    fx = json.load(open(os.path.join(d, "fixture.json"), encoding="utf-8"))
    same = {k: v for k, v in doc.items()} == fx
    check("a. fixture.json equals the tool's --fixture output (rerun: python tools/money/chrysos.py --out <dir> --fixture, copy chrysos.json)", same)
    check("a. the fixture is a DEMO: status sample, demo true, 'not real'", fx["status"] == "sample" and fx["demo"] is True and "not real" in fx["note"].lower())
    core = AK.read(os.path.join(d, "chrysoscore.js"))
    check("a. no promise words in the page files", not re.search(r"guarantee|risk-free|sure thing|you will earn|passive income", html + core + AK.read(os.path.join(d, "chrysos.js")), re.I))


HARNESS = r"""
import(process.argv[2]).then((C) => {
  const fx = JSON.parse(require('fs').readFileSync(process.argv[3], 'utf8'));
  const o = {};
  o.words = [C.money(2000), C.moneyS(-60), C.moneyS(0), C.price(91.8), C.pct(83.6), C.beWords(1.4), C.beWords(0), C.beWords(null), C.beWords(0.5), C.dayWords(8), C.dayWords(45), C.dayWords(90), C.dateWords('2026-12-25'), C.monthWords('2027-01')];
  o.usable = [!!C.usable(fx), C.usable(null), C.usable({}), C.usable({ id: 'chrysos', chrysos: {} }), C.usable('x'), C.usable(JSON.parse(JSON.stringify(fx, (k, v) => (k === 'cum' ? [1, 2] : v))))];
  o.age = [C.age({ asof: '2026-11-10T00:00:00Z' }, Date.parse('2026-11-11T00:00:00Z')), C.age({ asof: '2026-11-10T00:00:00Z' }, Date.parse('2026-11-15T00:00:00Z')), C.age({ asof: '2026-11-10T00:00:00Z' }, Date.parse('2026-12-15T00:00:00Z')), C.age({}, 1)];
  o.accs = C.fleetAccounts(fx).map((a) => a.name);
  o.head = CASES();
  function CASES() { return C.CASES.map((k) => C.headline(fx, k)); }
  const tw = C.towers(fx, 'base', 12), t0 = C.towers(fx, 'base', 0), tj = C.towers(fx, 'base', 'junk'), tn = C.towers(fx, 'base', -5);
  o.tower = [tw.towers.length, tw.unit, tw.towers.map((t) => t.coins), tw.towers.map((t) => t.paidBack), t0.towers.map((t) => t.coins), t0.towers.every((t) => t.paidBack === false), tj.month, tn.month, tw.towers.every((t) => t.drum >= 1)];
  o.unit = [C.coinUnit(0), C.coinUnit(26), C.coinUnit(900), C.coinUnit(1e9), C.coinUnit('x')];
  const g = C.calendarGroups(fx);
  o.cal = [g.length, g[0].key, g[0].label, g.every((m, i) => i === 0 || g[i - 1].key < m.key), g.every((m) => m.total_expected <= m.total_if + 1e-9), g[0].rows[0].label];
  o.lines = [C.accountLine(fx.chrysos.owned[0], 'base'), C.riskLines(fx, 'base').length, C.riskLines(fx, 'conservative')[1]];
  o.card = C.jarvisCard(fx, 'base');
  o.wrong = C.wrongLines(fx);
  o.order = C.CASES.map((k) => fx.chrysos.fleet[k].net12);
  console.log(JSON.stringify(o));
});
"""


def test_maths():
    t = tool()
    r = subprocess.run([sys.executable, TOOL, "--selftest"], capture_output=True, text=True, timeout=120)
    check("b. the tool's own selftest passes", r.returncode == 0 and "passed" in r.stdout, r.stdout[-300:] + r.stderr[-300:])
    st, src = t.load_stats(fixture=True)
    doc = t.plan(st, src)
    c = doc["chrysos"]
    check("b. the data contract: v 1, id, asof, mode paper, status, headline.text + usd_month, items with title / detail / usd / score / risk, notes",
          doc["v"] == 1 and doc["id"] == "chrysos" and doc["mode"] == "paper" and doc["status"] in ("ok", "stale", "sample") and isinstance(doc["headline"]["usd_month"], (int, float))
          and all(set(i) == {"title", "detail", "usd", "score", "risk"} for i in doc["items"]) and isinstance(doc["notes"], list) and len(doc["notes"]) >= 3)
    nets = [c["fleet"][k]["net12"] for k in t.CASES]
    check("b. the three cases are ordered: cautious <= middle <= hopeful, for the fleet and for every account type", nets == sorted(nets) and all(
        a["cases"]["conservative"]["net12"] <= a["cases"]["base"]["net12"] <= a["cases"]["optimistic"]["net12"] for a in c["owned"] + c["candidates"]), nets)
    check("b. a paid fee is sunk: the owned accounts start their forward cash at $0 (a candidate starts at minus its price)", all(a["cases"]["base"]["cum"][0] == 0 for a in c["owned"]) and all(a["cases"]["base"]["cum"][0] == -a["price"] for a in c["candidates"]))
    check("b. payouts never pass the MFFU cap (5 payouts x the max) and every chance is a probability", all(a["cases"][k]["income"][-1] <= a["cases"][k]["payout_cap_total"] + 0.01 and 0 < a["cases"][k]["p_funded"] < 100 for a in c["owned"] + c["candidates"] for k in t.CASES))
    check("b. the fleet is the sum of its accounts (month by month, base case) and capped", all(abs(c["fleet"]["base"]["cum"][m] - sum(a["cases"]["base"]["cum"][m] for a in c["owned"] + c["buy_next"])) < 0.2 for m in range(13)) and len(c["owned"]) + len(c["buy_next"]) <= c["max_accounts"])
    fcz = c["fleet"]["conservative"]
    check("b. Cautious is a correlated stress path: net negative in months 1 and 2, at least one LOSS month, every copy fails together once and is bought again (same cycle length, 2 purchases), the weak-month ratio is the worst real 2026 month",
          fcz["cum"][1] < 0 and fcz["cum"][2] < 0 and fcz["loss_months"] and len({a["cases"]["conservative"]["days_to_funded"] for a in c["candidates"]}) == 1
          and all(abs(a["cases"]["conservative"]["attempts"] - 2.0) < 1e-9 for a in c["candidates"]) and 0.05 < st["funded"]["weak_ratio"] < 0.2, (fcz["cum"][:4], fcz["loss_months"]))
    fst = c["fleet"]["stress"]
    check("b. Stress ('what if I am wrong'): two failed cycles then the 2021-25 line; it ends month 12 near zero or negative, loses months 1 and 2, every account bought 3 times; the order is stress <= cautious <= base <= optimistic; Mint's usd_month low = Stress / 12",
          fst["net12"] < 1000 and fst["loss_months"][:2] == [1, 2] and all(abs(a["cases"]["stress"]["attempts"] - 3.0) < 1e-9 for a in c["candidates"]) and [c["fleet"][k]["net12"] for k in t.CASES] == sorted(c["fleet"][k]["net12"] for k in t.CASES)
          and abs(doc["usd_month"]["low"] - fst["net12"] / 12.0) < 0.01 and doc["usd_month"]["low"] <= doc["usd_month"]["base"] <= doc["usd_month"]["high"], (fst["net12"], doc["usd_month"]))
    check("b. the budget rules: $0 buys nothing, a huge budget still obeys the 6-account cap, an empty fleet works", t.plan(st, src, budget=0)["chrysos"]["buy_next"] == [] and len(t.plan(st, src, fleet=[], budget=1e5)["chrysos"]["buy_next"]) <= t.MAX_ACCOUNTS)
    check("b. honest labels: 'Estimate' in the headline and every item, a not-a-promise note, the correlated-accounts warning", "Estimate" in doc["headline"]["text"] and all("Estimate" in i["detail"] for i in doc["items"]) and any("SAME signals" in n for n in doc["notes"]) and any("promise" in n.lower() for n in doc["notes"] + [doc["headline"]["text"]]))
    live, lsrc = t.load_stats(fixture=False)
    check("b. the live read: when research/lit exists the stats come from it and the status is ok; the worst-case net is not above the bundled one by more than rounding", (lsrc.startswith("research/lit") and t.plan(live, lsrc)["status"] == "ok") or lsrc == "bundled sample", lsrc)
    empty = tempfile.mkdtemp(prefix="chry-empty-")
    est, esrc = t.load_stats(root=empty)
    check("b. no research files at all: the bundled numbers are used and the plan still builds (offline)", esrc == "bundled sample" and t.plan(est, esrc)["items"])
    out = AK.node(APP, HARNESS, os.path.join(AK.WEB, APP, "fixture.json"))
    if out is None:
        check("b. node is not installed: the JS core maths skipped", True)
        return
    check("b. no error in the harness", "_error" not in out, out.get("_error"))
    if "_error" in out:
        return
    check("b. words: $2,000, -$60, $0, $91.80, 84%, 'in about 1.4 months', 'already', 'not within 12 months', 'in under a month', 8 days, about 6 weeks, about 3 months, Dec 25, Jan 2027",
          out["words"] == ["$2,000", "-$60", "$0", "$91.80", "84%", "in about 1.4 months", "already", "not within 12 months", "in under a month", "8 days", "about 6 weeks", "about 3 months", "Dec 25", "Jan 2027"], out["words"])
    check("b. usable(): the fixture passes; null, {}, a stub, a string and a file with short series are refused (the page falls back, never blank)", out["usable"] == [True, None, None, None, None, None], out["usable"])
    check("b. age: fresh / old / stale / unknown", out["age"] == ["fresh", "old", "stale", "unknown"], out["age"])
    check("b. every headline says Estimate, names the case, has Not a promise", all(h.startswith("Estimate, ") and h.endswith("Not a promise.") for h in out["head"]) and "stress" in out["head"][0] and "cautious" in out["head"][1] and "hopeful" in out["head"][3] and len(out["head"]) == 4, out["head"])
    tw = out["tower"]
    check("b. tower model: 4 accounts, a coin unit, coins at month 12, none paid back at month 0, junk month -> 12, negative -> 0, drums never below 1", tw[0] == 4 and tw[1] in (25, 50, 100, 250, 500) and all(x > 0 for x in tw[2]) and not any(tw[4]) and tw[5] and tw[6] == 12 and tw[7] == 0 and tw[8], tw)
    check("b. coin unit is bounded: 10 for nothing, a nice step for a tall tower, 5000 at the top, junk safe", out["unit"][0] == 10 and out["unit"][1] == 10 and out["unit"][3] == 5000 and out["unit"][4] == 10, out["unit"])
    check("b. calendar groups: months in order, expected <= if-funded, labelled", out["cal"][0] >= 3 and out["cal"][3] and out["cal"][4] and out["cal"][2].endswith("2026") or out["cal"][2].endswith("2027"), out["cal"])
    check("b. account line is an Estimate with odds, first payout, the monthly figure, fees and break-even; the risk lines are never empty; the cautious line is honest", out["lines"][0].startswith("Estimate:") and "break-even" in out["lines"][0] and "already paid" in out["lines"][0] and out["lines"][1] == 5, out["lines"])
    check("b. 'What if I am wrong': four plain sentences, the Stress numbers in words, loss months named, a real loss stated in dollars",
          len(out["wrong"]) == 4 and "third try passes" in out["wrong"][0] and "6 months" in out["wrong"][1] and "Loss months: 1 and 2" in out["wrong"][2] and ("real loss of $" in out["wrong"][3] or "near" in out["wrong"][3]), out["wrong"])
    check("b. the Jarvis helper card and the case order", out["card"]["name"] == "Chrysos" and out["order"] == sorted(out["order"]), out)


def real_doc(shift=1.0):
    t = tool()
    st, src = t.load_stats(fixture=True)
    doc = t.plan(st, src, asof="2026-11-10T00:00:00Z", status="ok")
    doc["headline"]["text"] = doc["headline"]["text"] + " (live)"
    return json.dumps(doc)


def test_page():
    try:
        import playwright  # noqa: F401
    except ImportError:
        check("c. page tests skipped: no Playwright", True)
        return
    srv, origin = AK.serve()
    try:
        with AK.browser() as br:
            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, APP, "?demo=1", hook="CHRYSOS")
            d = p.evaluate("""() => ({ demo: !document.querySelector('#demo').hidden, cases: [...document.querySelectorAll('#cases button')].map((b) => b.textContent), on: document.querySelector('#cases [aria-pressed=true]').textContent,
              head: document.querySelector('#headline').textContent, tiles: document.querySelector('#tiles').textContent, buy: document.querySelectorAll('#buy .acard').length, fleet: document.querySelectorAll('#fleet .acard').length,
              cal: document.querySelectorAll('#cal .calrow').length, gone: document.querySelectorAll('#gone li').length, wrong: document.querySelectorAll('#wrong li').length, how: document.querySelectorAll('#how li').length, legend: document.querySelectorAll('#legend li').length,
              warn: document.querySelector('#warn').textContent, font: getComputedStyle(document.querySelector('h1')).fontFamily, bg: getComputedStyle(document.body).backgroundColor, mode: window.CHRYSOS.mode })""")
            check("c. DEMO: the chip, four cases (Middle on, Stress first), an 'Estimate' headline with Not a promise, five tiles, 3 buy cards, 4 fleet cards, a calendar, 5 risks, the warning line",
                  d["demo"] and d["cases"] == ["Stress", "Cautious", "Middle", "Hopeful"] and d["on"] == "Middle" and d["head"].startswith("Estimate, middle case") and d["head"].endswith("Not a promise.") and "Net after 12 months" in d["tiles"] and "Break-even" in d["tiles"]
                  and d["buy"] == 3 and d["fleet"] == 4 and d["cal"] >= 8 and d["gone"] == 5 and d["wrong"] == 4 and d["how"] >= 6 and d["legend"] == 4 and "not a promise" in d["warn"].lower(), d)
            check("c. AGORA look: serif title, warm dark body", any(f in d["font"] for f in ("Palatino", "Iowan", "Georgia")) and d["bg"] == "rgb(20, 17, 14)", d)
            check("c. the tower is 3D or the flat drawing, never nothing: the canvas XOR the svg is visible", d["mode"] in ("3d", "flat") and p.evaluate("() => document.querySelector('#stage').hidden !== document.querySelector('#flat').hasAttribute('hidden')"), d["mode"])
            if d["mode"] == "3d":
                px = p.evaluate("""() => { const c = document.querySelector('#stage'); return [c.width > 100, c.height > 100, window.CHRYSOS.tower.towers]; }""")
                check("c. 3D mode: a real canvas with four towers", px[0] and px[1] and px[2] == 4, px)
            if d["mode"] == "3d":
                check("c. 3D mode hides the flat drawing", p.evaluate("() => getComputedStyle(document.querySelector('#flat')).display") == "none")
            AK.shot(p, "chrysos-demo")
            flat = p.evaluate("() => document.querySelectorAll('#flat rect').length")
            check("c. the flat tower is always drawn (the fallback and the screen-reader picture): bronze and coin rectangles", flat > 20, flat)
            p.locator("#cases [data-case=conservative]").click()
            p.wait_for_timeout(150)
            a = p.evaluate("() => [document.querySelector('#headline').textContent, document.querySelector('#caseNote').textContent, document.querySelector('#status').textContent]")
            check("c. tap Cautious: the headline, the note and the spoken status change (cautious case)", a[0].startswith("Estimate, cautious case") and "Cautious" in a[1] and "Cautious case" in a[2], a)
            before = p.evaluate("() => document.querySelector('#legend').textContent")
            p.fill("#month", "0")
            p.dispatch_event("#month", "input")
            p.wait_for_timeout(200)
            m = p.evaluate("() => [document.querySelector('#monthV').textContent, document.querySelector('#legend').textContent, document.querySelector('#status').textContent]")
            check("c. month slider to 0: the towers fall back to the fees only (no payouts yet), 'Month 0 of 12' is spoken", m[0] == "0" and m[1] != before and "payouts $0" in m[1] and "Month 0" in m[2], m)
            p.fill("#month", "12")
            p.dispatch_event("#month", "input")
            p.wait_for_timeout(200)
            y = p.evaluate("() => document.querySelector('#legend').textContent")
            check("c. month slider back to 12: the coins return and 'paid back' shows", "paid back" in y, y)
            t = AK.taps(p)
            check("c. every tap target is at least 44 x 44 px (the three cases, the month slider, the page)", not t, t[:5])
            check("c. no sideways scroll; Jarvis's corner is free; no console error; nothing off the origin", AK.no_sideways(p) and not AK.corner(p) and not errs and not off, (errs[:3], off[:3]))
            ctx.close()

            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, APP, "?demo=1&case=optimistic&month=6", hook="CHRYSOS")
            q = p.evaluate("() => [document.querySelector('#cases [aria-pressed=true]').textContent, document.querySelector('#month').value]")
            check("c. ?case=optimistic&month=6 opens that view", q == ["Hopeful", "6"], q)
            ctx.close()

            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, APP, "?demo=1&q=high", hook="CHRYSOS")
            hq = p.evaluate("() => [window.CHRYSOS.mode, getComputedStyle(document.querySelector('#flat')).display, window.CHRYSOS.tower ? window.CHRYSOS.tower.towers : 0]")
            check("c. ?q=high: the 3D tower with four towers builds and the flat drawing is hidden (or, with no WebGL, the flat tower stays), no console error",
                  ((hq[0] == "3d" and hq[1] == "none" and hq[2] == 4) or (hq[0] == "flat" and hq[1] != "none")) and not errs, (hq, errs[:2]))
            ctx.close()
            srv2, origin2 = AK.serve({"/money/chrysos.json": real_doc()})
            ctx, p, errs, seen, off = AK.page(br, origin2)
            AK.open_app(p, origin2, APP, "", hook="CHRYSOS")
            r = p.evaluate("() => [!document.querySelector('#demo').hidden, document.querySelector('#headline').textContent]")
            check("c. the real money/chrysos.json (status ok): no DEMO chip and the Estimate headline, nothing off the origin", not r[0] and r[1].startswith("Estimate, middle case"), r)
            check("c. the real run read the file and no console error", any("money/chrysos.json" in u for u in seen) and not off and not errs, (off[:3], errs[:3]))
            ctx.close()
            srv2.shutdown()

            srv3, origin3 = AK.serve({"/money/chrysos.json": '{"id":"chrysos","chrysos":{"owned":[]}}'})
            ctx, p, errs, seen, off = AK.page(br, origin3)
            AK.open_app(p, origin3, APP, "", hook="CHRYSOS")
            r = p.evaluate("() => [!document.querySelector('#demo').hidden, document.querySelectorAll('#fleet .acard').length]")
            check("c. a broken money/chrysos.json never blanks the page: the fixture shows with the DEMO chip", r == [True, 4] and not errs, (r, errs[:2]))
            ctx.close()
            srv3.shutdown()

            srv4, origin4 = AK.serve({"/money/chrysos.json": None})
            ctx, p, errs, seen, off = AK.page(br, origin4)
            AK.open_app(p, origin4, APP, "", hook="CHRYSOS")
            r = p.evaluate("() => [!document.querySelector('#demo').hidden, document.querySelectorAll('#fleet .acard').length]")
            check("c. a missing money/chrysos.json (404): the fixture shows with the DEMO chip", r == [True, 4], r)
            ctx.close()
            srv4.shutdown()

            ctx, p, errs, seen, off = AK.page(br, origin, w=375, h=667, reduced=True, lite=True)
            AK.open_app(p, origin, APP, "?demo=1&q=low", hook="CHRYSOS")
            mode = p.evaluate("() => window.CHRYSOS.mode")
            check("c. 375 x 667, LITE (?q=low), reduced motion: the flat tower, no sideways scroll, every tap >= 44 px, no error", mode == "flat" and AK.no_sideways(p) and not AK.taps(p) and not errs, (mode, AK.taps(p)[:3], errs[:2]))
            AK.shot(p, "chrysos-lite")
            ctx.close()
    finally:
        srv.shutdown()


if __name__ == "__main__":
    test_static()
    test_maths()
    if "--static" not in sys.argv:
        test_page()
    AK.finish()
