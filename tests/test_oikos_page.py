"""OIKOS, the OLYMPUS household page (tools/web_public/oikos/, AGORA look, 2026-11-10) and its offline scanner tools/money/oikos.py: where the money leaks, a generic tax set-aside, the buckets, reinvest or withdraw.

  a. static: the files, the kit lines, the AGORA look, read-only, the Jarvis card, the manifest, the DEMO fixture is the scanner's bundled sample, the 3D scene file, the scanner contract and its selftest
  b. the maths: the Python selftest (hand-checked numbers) and the page's oikoscore.js in node on the same ledgers (the bundled sample, a hand ledger with weekly / yearly / ended items, junk) must agree to the cent
  c. Chromium 390 x 844 (and 375 x 667): the DEMO, the amphora (WebGL coins, flat fallback), sliders, paste / file import / export, the Ledger on the phone, the scanner feed, LITE / reduced motion, taps >= 44 px, no sideways scroll, no console error
    python -X utf8 -m tests.test_oikos_page            (--static: parts a and b only)
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools", "money"))
from tests import agora_kit as AK  # noqa: E402
import oikos  # noqa: E402

APP, NAME, TODAY = "oikos", "Oikos", "2026-11-10"
check = AK.check
SAMPLE = os.path.join(ROOT, "tools", "money", "oikos_sample.json")


def test_static():
    AK.static_kit(APP, NAME, reads=("../money/oikos.json", "../ledger/rules.json"), storage=True)
    d = os.path.join(AK.WEB, APP)
    js, core, scene, html = (AK.read(os.path.join(d, n)) for n in ("oikos.js", "oikoscore.js", "oikosscene.js", "index.html"))
    check("a. the page keeps only its own 'oikos.v1' on the phone and reads the Ledger's 'ledger.v1' (never writes it); no session storage / indexedDB",
          "'oikos.v1'" in js and "setItem('ledger" not in js and not re.search(r"sessionStorage|indexedDB|setItem\(\s*'ledger", js + core), None)
    check("a. the 3D scene: a marble amphora from three (local copy), WebGL optional (returns null -> a flat vase), no neon, bloom or composer",
          "../jarvis/three.module.min.js" in scene and "LatheGeometry" in scene and "InstancedMesh" in scene and "return null" in scene and not re.search(r"Bloom|EffectComposer|neon|emissive: '#(?:0ff|f0f)", scene)
          and "createAmphora" in js and "drawFallback" in js, None)
    check("a. no markup is built from data in the scene file either", not re.search(r"innerHTML|outerHTML|insertAdjacentHTML|eval\(", scene), None)
    fx = AK.read(os.path.join(d, "fixture.json"))
    check("a. fixture.json is exactly the scanner's bundled sample (tools/money/oikos_sample.json)", fx == AK.read(SAMPLE), None)
    order = [html.index(x) for x in ('id="amph"', 'id="srcBtns"', 'id="leaks"', 'id="acctRows"', 'id="tax"', 'id="buckets"', 'id="chart"')]
    check("a. the page order: amphora, where the numbers come from, leaks, accounts, tax, buckets, projector", order == sorted(order), order)
    check("a. 'not tax advice', 'estimate' and 'not a promise' are on the page", all(x in html + js + core for x in ("Not tax advice", "estimate", "not a promise")), None)
    check("a. import and export exist: a file picker, a paste box, an Export button", all(x in html for x in ('id="file"', 'id="paste"', 'id="exportBtn"', 'id="useLedger"', 'id="useDemo"')), None)
    # the scanner
    src = AK.read(os.path.join(ROOT, "tools", "money", "oikos.py"))
    check("a. the scanner is stdlib only and offline (no network module, no trading code)", not re.search(r"^\s*(?:import|from)\s+(?:urllib|requests|http|socket|ccxt|ninja|engine)", src, re.M) and "engine" not in src.split('"""')[1].split("Stdlib")[0], None)
    with tempfile.TemporaryDirectory() as tmp:
        r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "money", "oikos.py"), "--out", tmp, "--fixture", "--today", TODAY], capture_output=True, text=True)
        doc = json.load(open(os.path.join(tmp, "oikos.json"), encoding="utf-8")) if r.returncode == 0 else {}
    ok = (doc.get("v") == 1 and doc.get("id") == "oikos" and doc.get("mode") == "paper" and doc.get("status") == "sample" and re.match(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$", doc.get("asof", ""))
          and isinstance(doc.get("headline", {}).get("text"), str) and isinstance(doc["headline"].get("usd_month"), (int, float)) and doc.get("notes")
          and all(set(i) == {"title", "detail", "usd", "score", "risk"} and 0 <= i["score"] <= 100 and i["risk"] in ("low", "med", "high") for i in doc.get("items", [])) and doc.get("items"))
    check("a. tools/money/oikos.py --fixture --out writes oikos.json in the money data contract (v 1, id, asof, paper, status sample, headline, items, notes)", ok, (r.stderr[-300:], list(doc)[:12]))
    check("a. the scanner's bundled-sample JSON says 'not real' and the contract's notes say estimate / not tax advice", "not real" in doc.get("ledger", {}).get("note", "").lower() and any("estimate" in n.lower() for n in doc.get("notes", [])) and any("tax advice" in n.lower() for n in doc.get("notes", [])), doc.get("notes"))


def hand_ledgers():
    return {
        "sample": json.load(open(SAMPLE, encoding="utf-8")),
        "hand": {"settings": {"taxPct": 30}, "accounts": [{"id": "A", "name": "Alpha 50K"}], "entries": [
            {"id": "a", "kind": "fee", "amount": 100, "date": "2026-08-15", "acct": "A"}, {"id": "b", "kind": "reset", "amount": 50, "date": "2026-09-01", "acct": "A"},
            {"id": "c", "kind": "payout_in", "amount": 300, "date": "2026-09-20", "acct": "A"}, {"id": "d", "kind": "fee", "amount": 40, "date": "2026-09-05", "acct": "B"},
            {"id": "e", "kind": "expense", "amount": 30, "date": "2026-08-10", "acct": "general", "note": "Feed", "rec": {"every": "month"}},
            {"id": "w", "kind": "expense", "amount": 5, "date": "2026-10-01", "acct": "general", "note": "Weekly tool", "rec": {"every": "week"}},
            {"id": "y", "kind": "expense", "amount": 120, "date": "2026-03-31", "acct": "general", "note": "Yearly plan", "rec": {"every": "year"}},
            {"id": "u", "kind": "expense", "amount": 20, "date": "2026-01-31", "acct": "general", "note": "Ended", "rec": {"every": "month", "until": "2026-06-30"}},
            {"id": "f", "kind": "payout_in", "amount": 600, "date": "2026-10-20", "acct": "A"}, {"id": "g", "kind": "tax", "amount": 50, "date": "2026-10-25"},
            {"id": "h", "kind": "income", "amount": "$1,250.50", "date": "2026-11-02", "acct": "general"}, {"id": "i", "kind": "payout_req", "amount": 900, "date": "2026-11-05", "acct": "A"},
            {"kind": "deposit", "amount": 200, "date": "2026-10-02", "acct": "kalshi"}]},
        "loss": {"entries": [{"kind": "fee", "amount": 90, "date": "2026-10-01", "acct": "Z"}, {"kind": "reset", "amount": 55, "date": "2026-10-09", "acct": "Z"}]},
        "bare": [{"kind": "fee", "amount": 43, "date": "2026-07-01", "acct": "Q"}, {"kind": "payout_in", "amount": 20, "date": "2026-07-30", "acct": "Q"}, {"kind": "payout_in", "amount": 500, "date": "2026-11-01", "acct": "R"}],
        "junk": {"entries": [{"kind": "fee", "amount": -5, "date": "2026-10-01"}, {"kind": "zzz"}, 7, None, {"kind": "fee", "amount": 12, "date": "2026-02-30"}, {"kind": "fee", "amount": 12, "off": -3}]},
        "empty": {"entries": []}, "notjson": "oops",
    }


HARNESS = r"""
const fs = require('fs');
import(process.argv[2]).then((C) => {
  const cases = JSON.parse(fs.readFileSync(process.argv[3], 'utf8')), today = process.argv[4], out = {};
  for (const k of Object.keys(cases)) {
    const raw = cases[k], led = C.normalize(typeof raw === 'string' ? raw : raw, today);
    out[k] = C.analyze(led, today, k === 'hand' ? { emergency: 0.3, reinvest: 0.1, cap: 4, proj_re: 0.8, account_cost: 70, living: 3000, em_saved: 5000 } : undefined);
  }
  const a = out.sample;
  out._words = [C.money(2000), C.money(-60.5), C.moneyS(150), C.pct(0.255), C.headline(a).usd_month, C.jarvisCard(a, 5).kpis.length, C.jarvisCard(out.empty, 5).status.level];
  out._unwrap = [C.unwrap('{"entries":[]}') !== null, C.unwrap('nope'), C.unwrap({ ledger: { entries: [1] }, opts: { tax: 0.3 } }).opts.tax, C.unwrap([1, 2]).entries.length, C.unwrap({ a: 1 })];
  out._opts = [C.mergeOpts({ tax: 0.5, emergency: 0.4, reinvest: 0.4 }), C.mergeOpts({ cap: 99, months: 0, living: 'x' })];
  console.log(JSON.stringify(out));
});
"""


def py_analysis(raw, key):
    opts = {"emergency": 0.3, "reinvest": 0.1, "cap": 4, "proj_re": 0.8, "account_cost": 70, "living": 3000, "em_saved": 5000} if key == "hand" else None
    return json.loads(json.dumps(oikos.analyze(oikos.normalize(raw, TODAY), TODAY, opts)))


def walk(x, y, path="", bad=None):
    bad = [] if bad is None else bad
    if isinstance(x, dict):
        for k in set(x) | set(y):
            if k not in x or k not in y:
                bad.append(f"key {path}/{k}")
            else:
                walk(x[k], y[k], f"{path}/{k}", bad)
    elif isinstance(x, list):
        if len(x) != len(y):
            bad.append(f"len {path}")
        else:
            for i, (a, b) in enumerate(zip(x, y)):
                walk(a, b, f"{path}/{i}", bad)
    elif isinstance(x, (int, float)) and isinstance(y, (int, float)) and not isinstance(x, bool):
        if abs(x - y) > 1e-9:
            bad.append(f"{path}: py {x} js {y}")
    elif x != y:
        bad.append(f"{path}: py {x!r} js {y!r}")
    return bad


def test_maths():
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = oikos.selftest()
    check("b. the scanner's own selftest (hand-checked totals, leaks, tax, buckets, projector) passes", rc == 0, buf.getvalue()[-600:])
    cases = hand_ledgers()
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as fh:
        json.dump(cases, fh)
        path = fh.name
    try:
        o = AK.node(APP, HARNESS, path, TODAY)
    finally:
        os.unlink(path)
    if o is None:
        check("b. node is not installed: the page maths cross-check was skipped", True)
        return
    check("b. no error in the node harness", "_error" not in o, o.get("_error"))
    if "_error" in o:
        return
    for k, raw in cases.items():
        bad = walk(py_analysis(raw, k), o[k])
        check(f"b. page maths = scanner maths on the '{k}' ledger (every number, to the cent)", not bad, bad[:5])
    a = o["hand"]
    t = a["totals"]
    # hand check: feed 30 x4 (08-10..11-10) = 120; weekly 5 from 10-01: 10-01,08,15,22,29,11-05 = 6 x 5 = 30; yearly 120 on 03-31 = 120; ended 20 monthly 01-31..06-30 = 6 x 20 = 120
    check("b. hand check: expenses 120 (monthly feed) + 30 (six weeks) + 120 (yearly) + 120 (ended in June) = 390; payouts 900; income 2150.50; fees 140; resets 50", (t["expenses"], t["payouts"], t["income"], t["fees"], t["resets"]) == (390.0, 900.0, 2150.5, 140.0, 50.0), t)
    check("b. the ended subscription is not listed as a running one; the running ones are the feed, the weekly tool and the yearly plan", sorted(s["name"] for s in a["subs"]) == ["Feed", "Weekly tool", "Yearly plan"], [s["name"] for s in a["subs"]])
    check("b. money words: $2,000, -$60.50, +$150, 26%, a leak figure, a Jarvis card with 3 kpis, an empty ledger is 'ok'", o["_words"][:4] == ["$2,000", "-$60.50", "+$150", "26%"] and o["_words"][5] == 3 and o["_words"][6] == "ok", o["_words"])
    check("b. unwrap takes a Ledger export, an Oikos export, a feed, a bare list; junk gives null", o["_unwrap"] == [True, None, 0.3, 2, None], o["_unwrap"])
    m1, m2 = o["_opts"]
    check("b. the sliders never add up past 100%: tax 50 + emergency 40 + reinvest 40 trims reinvest to 10; caps and months are clamped", abs(m1["reinvest"] - 0.1) < 1e-9 and m2["cap"] == 20 and m2["months"] == 1 and m2["living"] == 2500, o["_opts"])
    s = o["sample"]
    check("b. the demo shows real leaks: a reset gap and a never-covered account, in worst-first order", {"reset:demoB", "never:demoC"} <= {x["id"] for x in s["leaks"]} and all(s["leaks"][i]["score"] >= s["leaks"][i + 1]["score"] for i in range(len(s["leaks"]) - 1)), [x["id"] for x in s["leaks"]])
    check("b. a loss-only household projects nothing and sets nothing aside; never a negative tax", o["loss"]["tax"]["set_aside"] == 0 and o["loss"]["projector"]["scenarios"][1]["end_withdraw"] == 0, o["loss"]["projector"]["scenarios"][1])
    check("b. conservative <= base <= optimistic on cash kept, and reinvesting never ends with fewer accounts", all(sc["end_withdraw"] <= nx["end_withdraw"] and sc["end_accounts"] >= p["n0"] for p in [s["projector"]] for sc, nx in zip(p["scenarios"], p["scenarios"][1:] + [p["scenarios"][-1]])), None)
    check("b. the account price you type is used for the projector and the 'next account' bucket", a["projector"]["account_cost"] == 70 and a["buckets"][3]["target"] == 70, a["projector"]["account_cost"])


SIDE = "()=>[document.querySelector('#demo').hidden, document.querySelector('#srcNote').textContent, document.querySelector('#headline').textContent, document.querySelector('#fillPill').textContent, [...document.querySelectorAll('#leaks li b')].map(x=>x.textContent), document.querySelectorAll('#acctRows tr').length, document.querySelector('#taxLabel').textContent, document.querySelectorAll('#buckets li').length, [...document.querySelectorAll('#scen button')].map(x=>x.textContent), document.querySelectorAll('#chart polyline').length]"


def test_page():
    try:
        import playwright  # noqa: F401
    except ImportError:
        check("c. page tests skipped: no Playwright", True)
        return
    pa = oikos.analyze(oikos.normalize(cases_sample(), TODAY), TODAY)
    srv, origin = AK.serve()
    try:
        with AK.browser() as br:
            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, APP, f"?demo=1&today={TODAY}")
            d = p.evaluate(SIDE)
            check("c. DEMO: the chip, the example note, the scanner's headline, the same worst leak first, 4 accounts, 30% tax, 4 buckets, 3 scenarios and a chart with 2 lines",
                  d[0] is False and "EXAMPLE numbers" in d[1] and d[2] == oikos.headline(pa)["text"] and d[4][0] == "Resets that did not pay back: Example eval 50K (second try)" and d[5] == 4 and d[6] == "Set aside 30% of net profit" and d[7] == 4
                  and d[8] == ["Conservative", "Base", "Optimistic"] and d[9] == 2, d)
            check("c. the amphora pill says how full the buckets are, as the scanner computes it", d[3] == f"{int(pa['fill'] * 100 + 0.5)}% full", (d[3], pa["fill"]))
            sc = p.evaluate("() => { const s = window.OIKOS.scene(); return s ? [s.coins(), s.capacity(), s.fill(), window.OIKOS.S.sceneMode, !document.querySelector('#amph').hidden, document.querySelector('#amphFallback').hasAttribute('hidden')] : [0, 0, 0, window.OIKOS.S.sceneMode, !document.querySelector('#amph').hidden, document.querySelector('#amphFallback').hasAttribute('hidden')]; }")
            if sc[3] == "webgl":
                p.wait_for_timeout(1500)
                n = p.evaluate("() => window.OIKOS.scene().coins()")
                check("c. 3D: the marble amphora is drawn (WebGL canvas) and holds gold coins in proportion to the fill (fill x capacity, within a coin)", abs(n - round(pa["fill"] * sc[1])) <= 2 and sc[1] > 300 and sc[4] and sc[5], (n, sc, pa["fill"]))
            else:
                fb = p.evaluate("() => [document.querySelectorAll('#amphFallback path').length, document.querySelectorAll('#amphFallback rect').length]")
                check("c. WebGL is not available here: the flat vase is drawn instead (never blank)", fb[0] >= 1 and fb[1] == 1, fb)
            AK.shot(p, "oikos-demo")
            font = p.evaluate("() => [getComputedStyle(document.querySelector('h1')).fontFamily, getComputedStyle(document.body).backgroundColor]")
            check("c. AGORA look: serif title, warm dark body", any(f in font[0] for f in ("Palatino", "Iowan", "Georgia")) and font[1] == "rgb(20, 17, 14)", font)
            # the tax slider
            before = p.evaluate("() => document.querySelector('#taxKv').textContent")
            p.evaluate("() => { const e = document.querySelector('#tax'); e.value = '40'; e.dispatchEvent(new Event('input', { bubbles: true })); }")
            p.wait_for_timeout(150)
            tx = p.evaluate("() => [document.querySelector('#taxLabel').textContent, document.querySelector('#taxKv').textContent, document.querySelector('#taxNote').textContent]")
            want = oikos.analyze(oikos.normalize(cases_sample(), TODAY), TODAY, {"tax": 0.4})["tax"]
            check("c. the tax slider to 40%: the label, the set-aside and the 'not tax advice' note follow", tx[0] == "Set aside 40% of net profit" and oikos.money(want["set_aside"]) in tx[1] and tx[1] != before and "Not tax advice" in tx[2], (tx, want["set_aside"]))
            # the sliders never exceed 100%
            p.evaluate("() => { for (const [id, v] of [['em', '60'], ['re', '60']]) { const e = document.querySelector('#' + id); e.value = v; e.dispatchEvent(new Event('input', { bubbles: true })); } }")
            p.wait_for_timeout(150)
            sl = p.evaluate("() => [document.querySelector('#bktNote').textContent, document.querySelector('#tax').value, document.querySelector('#em').value, document.querySelector('#re').value]")
            check("c. tax 40 + emergency 60 + next account 60 is trimmed to 100% in total and the note says 'you 0%'", float(sl[1]) + float(sl[2]) + float(sl[3]) <= 100.01 and "you 0%" in sl[0], sl)
            # scenarios and the projector
            p.locator("#scen [data-scen=conservative]").click()
            p.wait_for_timeout(150)
            pj = p.evaluate("() => [document.querySelector('#prjKv').textContent, document.querySelector('#scen [aria-pressed=true]').textContent, document.querySelector('#prjWarn').textContent, document.querySelector('#chart').getAttribute('aria-label')]")
            cons = oikos.analyze(oikos.normalize(cases_sample(), TODAY), TODAY, {"tax": 0.4, "emergency": 0.4, "reinvest": 0.2})["projector"]["scenarios"][0]
            check("c. tap Conservative: the kept-cash lines follow the scanner's numbers, and the page says estimate, not a promise, 'win and lose together'",
                  pj[1] == "Conservative" and oikos.money(cons["end_withdraw"]) in pj[0] and "not a promise" in pj[2] and "win and lose together" in pj[2] and "reinvest" in pj[3], (pj[0][:160], pj[1], cons["end_withdraw"]))
            p.evaluate("() => { document.querySelector('#prMore').open = true; }")
            p.locator("#priceChips button").first.click()
            p.wait_for_timeout(150)
            pc = p.evaluate("() => [document.querySelector('#acctCost').value, document.querySelector('#priceChips [aria-pressed=true]').textContent, document.querySelector('#prjNote').textContent]")
            check("c. the owner's real price chip (Builder 50K $91.80) sets the price of one more account", pc[0] == "91.8" and "$91.80" in pc[1] and "$91.80" in pc[2], pc)
            t = AK.taps(p)
            check("c. every tap target is at least 44 x 44 px (buttons, sliders, inputs, the page)", not t, t[:5])
            check("c. no sideways scroll; Jarvis's corner is free; no console error; nothing off the origin", AK.no_sideways(p) and not AK.corner(p) and not errs and not off, (errs[:3], off[:3]))
            # paste
            ledger = {"app": "ledger", "entries": [{"id": "p1", "kind": "fee", "amount": 91.8, "date": "2026-10-01", "acct": "mine", "note": "Mine"}, {"id": "p2", "kind": "payout_in", "amount": 400, "date": "2026-10-20", "acct": "mine"},
                      {"id": "p3", "kind": "expense", "amount": 20, "date": "2026-09-01", "acct": "general", "note": "My feed", "rec": {"every": "month"}}]}
            p.evaluate("() => { document.querySelector('#pasteBox').open = true; }")
            p.fill("#paste", "this is not json")
            p.locator("#pasteGo").click()
            p.wait_for_timeout(150)
            bad = p.evaluate("() => [document.querySelector('#status').textContent, !document.querySelector('#demo').hidden]")
            check("c. a bad paste changes nothing and says so in plain words (still DEMO)", "not a Ledger export" in bad[0] and bad[1] is True, bad)
            p.fill("#paste", json.dumps(ledger))
            p.locator("#pasteGo").click()
            p.wait_for_timeout(250)
            imp = p.evaluate(SIDE)
            mine = oikos.analyze(oikos.normalize(ledger, TODAY), TODAY)
            check("c. paste a real export: DEMO off, 'a file you imported', the headline and the leaks are the scanner's numbers for it", imp[0] is True and "imported" in imp[1] and imp[2] == oikos.headline(mine)["text"] and imp[4][0] == mine["leaks"][0]["title"], (imp[:3], mine["leaks"][0]["title"]))
            kept = p.evaluate("() => window.OIKOS.raw('oikos.v1')")
            check("c. the imported ledger is kept on this phone only (oikos.v1) and survives a reload", kept and "p1" in kept, (kept or "")[:80])
            AK.open_app(p, origin, APP, f"?today={TODAY}")      # ?demo=1 would force the demo, so the reload drops it
            rl = p.evaluate("() => [document.querySelector('#srcNote').textContent, document.querySelector('#demo').hidden]")
            check("c. after a reload it still shows your imported ledger (never blank, never silently back to the demo)", "imported" in rl[0] and rl[1] is True, rl)
            with p.expect_download(timeout=20000) as dl:
                p.locator("#exportBtn").click()
            ex = json.load(open(dl.value.path(), encoding="utf-8"))
            check("c. Export JSON: an Oikos file with the ledger entries, the settings used, the headline and the leaks, and the tax note", ex.get("app") == "oikos" and len(ex["ledger"]["entries"]) == 3 and "tax" in ex["opts"] and ex["headline"]["text"] and ex["leaks"] and "Not tax advice" in ex["tax_note"], list(ex))
            p.locator("#useDemo").click()
            p.wait_for_timeout(200)
            check("c. 'Show the demo' brings the example back", p.evaluate("() => !document.querySelector('#demo').hidden"), None)
            # the file picker, with the same export fed back in
            p.set_input_files("#file", {"name": "oikos.json", "mimeType": "application/json", "buffer": json.dumps(ex).encode()})
            p.wait_for_timeout(400)
            fi = p.evaluate("() => [document.querySelector('#srcNote').textContent, document.querySelector('#demo').hidden]")
            check("c. the file picker takes the Oikos export back (a round trip)", "imported" in fi[0] and fi[1] is True, fi)
            check("c. the import and export runs sent nothing off the site and raised no error", not off and not errs, (off[:3], errs[:3]))
            ctx.close()
            # the Ledger on this phone
            ph = {"v": 1, "entries": [{"id": "x1", "kind": "fee", "amount": 91.8, "date": "2026-10-18", "acct": "lit50k", "cat": "Eval fees", "note": "", "rec": None},
                                      {"id": "x2", "kind": "payout_in", "amount": 500, "date": "2026-11-01", "acct": "lit50k", "cat": "Payouts", "note": ""}], "settings": {"taxPct": 30}, "hidden": []}
            ctx, p, errs, seen, off = AK.page(br, origin, storage={"ledger.v1": json.dumps(ph)})
            AK.open_app(p, origin, APP, f"?today={TODAY}")
            r = p.evaluate(SIDE)
            check("c. with a Ledger on the phone it reads it (read only): 'Your Ledger on this phone', no DEMO chip, the Ledger's own 30% tax setting", r[0] is True and "Your Ledger on this phone: 2 entries" in r[1] and r[6] == "Set aside 30% of net profit", r)
            check("c. it never wrote to the Ledger's storage", p.evaluate("() => localStorage.getItem('ledger.v1')") == json.dumps(ph) and not errs, errs[:2])
            ctx.close()
            # the scanner's feed
            feed = oikos.build(oikos.normalize(cases_sample(), TODAY), TODAY, "ok")
            srv2, origin2 = AK.serve({"/money/oikos.json": json.dumps(feed)})
            ctx, p, errs, seen, off = AK.page(br, origin2)
            AK.open_app(p, origin2, APP, f"?today={TODAY}")
            fd = p.evaluate(SIDE)
            check("c. with no Ledger on the phone but a scanner feed (status ok) it reads the feed's ledger", fd[0] is True and "scanner's copy" in fd[1] and any("money/oikos.json" in u for u in seen) and not errs, (fd[1], errs[:2]))
            ctx.close()
            srv2.shutdown()
            # the feed says 'sample' -> demo; the feed is missing -> demo
            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, APP, f"?today={TODAY}")
            check("c. no Ledger, no feed (404) -> the DEMO, never blank, no console error", p.evaluate("() => !document.querySelector('#demo').hidden && document.querySelectorAll('#leaks li').length > 0") and not errs, errs[:2])
            ctx.close()
            ctx, p, errs, seen, off = AK.page(br, origin, w=375, h=667, reduced=True, lite=True)
            AK.open_app(p, origin, APP, f"?demo=1&today={TODAY}&q=low")
            check("c. 375 x 667, LITE, reduced motion: no sideways scroll, every tap >= 44 px, no error", AK.no_sideways(p) and not AK.taps(p) and not errs, (AK.taps(p)[:3], errs[:2]))
            ctx.close()
    finally:
        srv.shutdown()


def cases_sample():
    return json.load(open(SAMPLE, encoding="utf-8"))


if __name__ == "__main__":
    test_static()
    test_maths()
    if "--static" not in sys.argv:
        test_page()
    AK.finish()
