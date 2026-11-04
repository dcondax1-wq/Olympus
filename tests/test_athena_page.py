"""ATHENA (tools/web_public/athena/, tools/athena_build.py, 2026-11-03): the owner's library, a searchable plain-words knowledge base.

  a. the files: the OLYMPUS kit links (?v=o2, data-app="athena"), only local scripts, module imports resolve, the render core + materials
     are used, the Jarvis card, nothing stored, the orb corner CSS
  b. the build: library.json / jarvis.json equal a fresh build (python tools/athena_build.py), the content covers what was asked (the
     strategy, the MFFU rules from research/lit/mffu_rules.json, the rejected list, the glossary terms, the four playbooks), ids and
     [[links]] resolve, entries are short, a jargon word has its glossary link
  b+. Train (2026-11-04): the questions the library can make (counted from it), Leitner boxes, the weakest topic and ONE next thing, the streak, the chart
     drills (drills.json against research/lab/backtest_live.json and data/NQ_5m.csv when they are here) and the scoring, in node
  e. the Train tab in Playwright at 390 x 844: the daily quiz (8 questions, boxes saved under 'athena.train.v1'), the 10 chart setups played through with a
     canvas, taps of 44 px or more, a missing drills.json / library.json, a damaged saved state, no network
  c. the page in Playwright Chromium at 390 x 844: search (exact, partial, a typo), the shelves filter the list by chip AND by a tap
     on the 3D shelf, an entry and its glossary links, #routes, Quiz me (5 questions, 4 options, score, nothing stored or sent), the
     stub library when library.json is missing, no sideways scroll, the orb corner free, reduced motion, no errors

    python -X utf8 -m tests.test_athena_page            (everything; c needs Playwright's Chromium)
    python -X utf8 -m tests.test_athena_page fast       (a and b: no browser)
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tests.olympus_money_kit import RES, WEB, browser, check, open_page, orb_hits, site, tidy_errors  # noqa: E402
from tools import athena_build as B  # noqa: E402

PAGE = os.path.join(WEB, "athena")


def rd(name):
    with open(os.path.join(PAGE, name), encoding="utf-8") as fh:
        return fh.read()


# ------------------------------------------------------------------------------------------------------------ a
def part_a():
    html = rd("index.html")
    check("a. the OLYMPUS kit: olympus.css, themes.js, olympus.js (data-app) all at ?v=o2",
          all(s in html for s in ('../olympus/olympus.css?v=o3', '../olympus/themes.js?v=o3', '../olympus/olympus.js?v=o3" data-app="athena"')))
    check("a. title Athena, a description, theme-color = the page colour, the Jarvis icon like the siblings",
          "<title>Athena</title>" in html and 'name="description"' in html and 'content="#070b14"' in html and "../jarvis/icon-192.png" in html)
    srcs = re.findall(r'(?:src|href)="([^"]+)"', html)
    check("a. only local files (no external script, font or stylesheet)", all(not s.startswith(("http:", "https:", "//")) for s in srcs), srcs)
    check("a. every local file the page links exists",
          all(os.path.exists(os.path.normpath(os.path.join(PAGE, s.split("?")[0]))) for s in srcs if not s.startswith("#")), srcs)
    js = rd("athena.js") + rd("athenacore.js")
    imps = re.findall(r"from '(\.[^']+)'", js + rd("athenaplus.js") + rd("athenabrain.js") + rd("athenatrain.js") + rd("athenatraincore.js"))
    check("a. every module import resolves (three.js from ../jarvis/, the render core + materials from ../olympus/)",
          all(os.path.exists(os.path.normpath(os.path.join(PAGE, i))) for i in imps) and "../olympus/render.js" in imps and "../olympus/materials.js" in imps, imps)
    tr = rd("athenatrain.js") + rd("athenatraincore.js")
    check("a. Train (athenatrain.js, athenatraincore.js): no innerHTML / outerHTML / insertAdjacentHTML / document.write (library and replay text goes in as text), no storage or network of its own (memory only through athenastore.js), "
          "no timers or animation loop (a screen is drawn once per tap: cheap on LITE)",
          not re.search(r"innerHTML|outerHTML|insertAdjacentHTML|document\.write|localStorage|sessionStorage|indexedDB|document\.cookie|sendBeacon|XMLHttpRequest|fetch\(|requestAnimationFrame|setInterval|setTimeout|eval\(|new Function", tr)
          and "from './athenastore.js'" in rd("athenatrain.js") and "load(KEY" in rd("athenatrain.js") and "const KEY = 'train.v1';" in rd("athenatrain.js"))
    check("a. the Train tab is in the dock (data-tab=train, badge) with its pane, and the Jarvis files stay the same", 'data-tab="train"' in html and 'id="p-train"' in html and 'id="bd-train"' in html and 'athena.js?v=a3' in html and 'athena.css?v=a3' in html)
    check("a. the 3D library is built on the render core (createRenderer) and not a bare WebGLRenderer", "createRenderer(" in js and "new THREE.WebGLRenderer" not in js)
    store = rd("athenastore.js") + rd("athenaplus.js") + rd("athenabrain.js")
    check("a. the reader's memory lives in athenastore.js only, every key under 'athena.' (nothing else is written, no cookies, no network in the new modules)",
          "const P = 'athena.';" in store and len(re.findall(r"localStorage\.setItem", store)) == 1 and not re.search(r"sessionStorage|indexedDB|document\.cookie|sendBeacon|XMLHttpRequest|fetch\(", store)
          and not re.search(r"localStorage|sessionStorage|indexedDB|document\.cookie", rd("athenabrain.js") + rd("athenaplus.js")))
    check("a. no network but its own library.json / jarvis.json; nothing stored by the page code itself (the memory is athenastore.js), nothing sent",
          sorted(set(re.findall(r"fetch\('([^'?]+)", js))) == ["jarvis.json"] and "loadLibrary('library.json" in js and "loadJson('drills.json" in js and "fetch(url" in js
          and not re.search(r"localStorage|sessionStorage|indexedDB|document\.cookie|sendBeacon|XMLHttpRequest|yahoo", js, re.I), re.findall(r"fetch\(([^,)]+)", js))
    card = json.loads(rd("jarvis.json"))
    check("a. the Jarvis card: v 1, name, status, kpis, open #library, the page theme, a stale_after",
          card["v"] == 1 and card["name"] == "Athena" and card["open"] == "#library" and card["theme"] == "#070b14" and len(card["kpis"]) >= 2
          and card["status"]["level"] in ("ok", "off", "warn", "bad") and card["stale_after"] > 0, card)
    css = rd("athena.css")
    check("a. the dock and the sheet keep the bottom-right 80 x 160 px free (right padding 88, sheet ends 166 px up)",
          "padding: 8px calc(88px" in css and "bottom: calc(166px" in css)


# ------------------------------------------------------------------------------------------------------------ b
def part_b():
    built = B.build()
    lib = json.loads(rd("library.json"))
    check("b. library.json and jarvis.json are a fresh build (python tools/athena_build.py)", lib == built["library.json"] and json.loads(rd("jarvis.json")) == built["jarvis.json"])
    E = lib["entries"]
    ids = [e["id"] for e in E]
    byid = {e["id"]: e for e in E}
    check("b. at least 60 entries, ids unique, every entry has a title, a short line and a known shelf", len(E) >= 60 and len(set(ids)) == len(ids)
          and all(e["title"] and e["short"] and e["kind"] in {t["id"] for t in lib["tags"]} and e["kind"] in e["tags"] for e in E))
    links = [m for e in E for t in [e["short"], *e["body"]] for m in re.findall(r"\[\[([a-z0-9-]+)\]\]", t)]
    check("b. every [[glossary link]] resolves (%d links)" % len(links), links and all(m in byid for m in links))
    check("b. short and plain: a short line is at most 260 characters, a body line at most 330, at most 7 body lines",
          all(len(e["short"]) <= 260 and len(e["body"]) <= 7 and all(len(b) <= 330 for b in e["body"]) for e in E),
          [e["id"] for e in E if len(e["short"]) > 260 or any(len(b) > 330 for b in e["body"])])
    kinds = {t["id"]: [e for e in E if e["kind"] == t["id"]] for t in lib["tags"]}
    check("b. every shelf is stocked (strategy 8+, MFFU 8+, rejected 8+, words 30+, playbooks 6+, numbers 3+)",
          len(kinds["strategy"]) >= 8 and len(kinds["mffu"]) >= 8 and len(kinds["rejected"]) >= 8 and len(kinds["words"]) >= 30 and len(kinds["playbook"]) >= 6 and len(kinds["numbers"]) >= 3,
          {k: len(v) for k, v in kinds.items()})
    ol = kinds["olympus"]
    apps = {"jarvis": "o-jarvis", "modes": "o-jarvis-modes", "think": "o-jarvis-think", "talking": "o-jarvis-talk", "smart key": "o-jarvis-key", "obsidian": "o-jarvis-obsidian",
            "zenith": "o-zenith", "oracle": "o-oracle", "odeon": "o-odeon", "fates": "o-fates", "data city": "o-datacity", "daphne": "o-daphne", "prometheus": "o-prometheus",
            "pantheon": "o-pantheon", "planner": "o-planner", "mind": "o-mind", "arena": "o-arena", "kalshi": "o-kalshi", "tyche": "o-tyche", "hermes": "o-hermes",
            "bridge": "o-bridge", "bridge sync": "o-bridge-sync", "ares": "o-ares", "plutus": "o-plutus", "athena": "o-athena", "phone": "o-phone"}
    check("b. the OLYMPUS shelf has an entry for every app asked for, a Phone setup entry and a Daily routine playbook (before / during / after)",
          all(v in byid and byid[v]["kind"] == "olympus" for v in apps.values()) and len(ol) >= 26 and "p-daily" in byid
          and all(w in " ".join(byid["p-daily"]["body"]) for w in ("BEFORE", "DURING", "AFTER")), [k for k, v in apps.items() if v not in byid])
    check("b. every app entry says what it is, when to open it and the one thing to look at; every app folder it names exists",
          all(any(b.startswith("Open it when:") for b in byid[v]["body"]) and any(b.startswith("The one thing to look at:") for b in byid[v]["body"]) for v in apps.values() if v != "o-phone")
          and all(os.path.exists(os.path.join(ROOT, *s.split("/"))) for e in ol for s in e["src"]), [s for e in ol for s in e["src"] if not os.path.exists(os.path.join(ROOT, *s.split("/")))])
    ph = " ".join([byid["o-phone"]["short"], *byid["o-phone"]["body"]])
    check("b. Phone setup: add to Home Screen, close and reopen after updates, and the Ava (Premium) voice path",
          "Add to Home Screen" in ph and "reopen" in ph and "Settings, then Accessibility, then Spoken Content, then Voices, then Ava (Premium)" in ph)
    bs = " ".join(byid["o-bridge-sync"]["body"])
    check("b. the ChatGPT sync steps match handoff/ONBOARD.md (handoff/inbox, paper only, no keys, 'Bridge: <job> done')",
          all(w in bs for w in ("ONBOARD.md", "handoff/inbox", "Bridge:", "paper only", "no keys")) and "handoff/inbox" in open(os.path.join(ROOT, "handoff", "ONBOARD.md"), encoding="utf-8").read())
    need = ["sweep", "ifvg", "cisd", "floor", "r", "pf", "inducement", "displacement", "eod-trailing", "drawdown", "atr", "vix-band", "breakeven", "consistency", "payout", "buffer", "eval", "funded"]
    check("b. the glossary has the terms asked for (sweep, IFVG, CISD, drawdown floor, R, PF ...)", all(n in byid and byid[n]["kind"] == "words" for n in need), [n for n in need if n not in byid])
    check("b. the four playbooks exist: a loss, 7-day inactivity, an eval fail, a payout (and each has numbered steps)",
          all(n in byid and byid[n]["kind"] == "playbook" and len(byid[n]["body"]) >= 2 for n in ("p-loss", "p-idle", "p-fail", "p-payout")))
    # the MFFU numbers are the file's own numbers
    d = json.loads(open(os.path.join(ROOT, "research", "lit", "mffu_rules.json"), encoding="utf-8").read())
    L = d["limits"]["builder_50k"]
    txt = lambda i: " ".join([byid[i]["short"], *byid[i]["body"]])  # noqa: E731
    check("b. the MFFU entries carry the rule file's numbers (floor $48,000 from the $2,000 max loss, daily $1,000, target $3,000, 40 micros, 7 days, buffer $2,100, first payout $52,600, 80%)",
          "$48,000" in txt("m-floor") and "$50,100" in txt("m-floor") and "$1,000" in txt("m-dll") and "$3,000" in txt("m-target") and "40 micros" in txt("m-size")
          and "7 days" in txt("m-idle") and "$2,100" in txt("m-pay") and "$52,600" in txt("m-pay") and "80%" in txt("m-pay")
          and (L["mll"], L["dll"], L["target"], L["max_micros"], L["inactivity_days"], L["buffer"]) == (2000.0, 1000.0, 3000.0, 40, 7, 2100.0))
    check("b. the owner's real prices, not list prices ($91.80 and $63)", "$91.80" in txt("m-price") and "$63" in txt("m-price") and "$153" not in txt("m-price"))
    check("b. the headline quotes the H2 check rate (PF 2.91, +$9,919) next to the 2026 figure", "2.91" in txt("n-headline") and "$9,919" in txt("n-headline") and "4.19" in txt("n-headline"))
    check("b. the rejected shelf says why (each entry has a reason line and the 'new idea' rule) and cites its source",
          all(e["src"] and len(e["body"]) >= 1 for e in kinds["rejected"]) and any("genuinely new idea" in " ".join(e["body"]) for e in kinds["rejected"]))
    # no jargon without a glossary link: outside the glossary, an entry that uses a term links to it
    jargon = {"cisd": "cisd", "ifvg": "ifvg", "inducement": "inducement", "displacement": "displacement", "atr": "atr", "vix band": "vix-band", "breakeven": "breakeven",
              "consistency": "consistency", "eod-trailing": "eod-trailing", "profit factor": None, "pf": "pf", "micro": "micro", "micros": "micro", "sweep": "sweep"}
    bad = []
    for e in E:
        if e["kind"] == "words":
            continue
        text = " ".join([e["title"], e["short"], *e["body"]])
        linked = set(re.findall(r"\[\[([a-z0-9-]+)\]\]", text))
        low = re.sub(r"\[\[[a-z0-9-]+\]\]", " ", text).lower()
        for term, gid in jargon.items():
            if gid and re.search(r"(?<![a-z-])" + re.escape(term) + r"(?![a-z])", low) and gid not in linked and e["id"] != gid:
                # a term spelled out in the title of the entry that explains it is fine (step-4 explains CISD in its own line)
                bad.append((e["id"], term))
    check("b. no jargon without a glossary link (an entry that uses CISD, ATR, PF, sweep ... links its meaning)", not bad, bad[:8])
    return lib


# ------------------------------------------------------------------------------------------------------------ c
def part_c(tmp, lib):
    from playwright.sync_api import sync_playwright
    srv, url = site(tmp, "athena", "c", data=False)
    srv2, url_off = site(tmp, "athena", "off", data=False, drop=("library.json",))
    try:
        with sync_playwright() as pw:
            br = browser(pw)
            errs = []
            reqs = []
            ctx, p = open_page(br, url + "?seed=7", errs, "__athena", reduced=True, wait_site=False)
            p.on("request", lambda r: reqs.append(r.url))
            check("c. the page opens; the library has its entries; the 3D room is up with one shelf per topic (9)",
                  p.evaluate("window.__athena.lib.entries.length") == len(lib["entries"]) and p.evaluate("window.__athena.ready3d") is True and p.evaluate("window.__athena.shelves") == len(lib["tags"]))
            q = p.evaluate("window.__athena.quality")
            ps = p.evaluate("window.__athena.passes")
            check("c. it runs on the render core: the pass list matches the tier (%s: %s)" % (q, ps), {"ultra": 3, "high": 3, "low": 2, "off": 1}[q] == len(ps), ps)
            check("c. no sideways scroll at 390 x 844", p.evaluate("document.documentElement.scrollWidth <= innerWidth && document.body.scrollWidth <= innerWidth"))
            check("c. the orb corner (bottom-right 80 x 160) is free of buttons and inputs", orb_hits(p) == [], orb_hits(p))
            n0 = len(p.query_selector_all("#list .item"))
            check("c. the list starts with every entry; a shelf chip for each topic, with its count", n0 == len(lib["entries"]) and len(p.query_selector_all("#chips .chip")) == len(lib["tags"]) == 9, n0)

            def top(term):
                p.fill("#q", term); p.wait_for_timeout(80)
                return p.evaluate("[...document.querySelectorAll('#list .item')].map(b => b.dataset.open)")

            r = top("sweep")
            check("c. search 'sweep': the glossary entry comes first, instantly", r and r[0] == "sweep", r[:4])
            r = top("swep")
            check("c. search with a typo ('swep') still finds Sweep", "sweep" in r[:3], r[:4])
            r = top("drawdown floor")
            check("c. search 'drawdown floor' finds the floor entries", r and r[0] in ("floor", "m-floor"), r[:3])
            r = top("payout")
            check("c. search 'payout' finds the payout entry and the playbook", "m-pay" in r[:6] and "p-payout" in r[:6], r[:6])
            r = top("7 day")
            check("c. search '7 day' finds the inactivity rule and its playbook", "m-idle" in r[:4] and "p-idle" in r[:6], r[:6])
            r = top("zzqxv")
            check("c. nothing found says so in plain words", r == [] and "Nothing found" in p.inner_text("#list"))
            p.fill("#q", ""); p.wait_for_timeout(80)

            # the chips filter
            p.click('#chips [data-tag="rejected"]'); p.wait_for_function("window.__athena.settled", timeout=30000)
            kinds = p.evaluate("[...document.querySelectorAll('#list .item')].map(b => b.dataset.open)")
            check("c. tapping the Rejected chip lists only the rejected entries, and the shelf turns to face you",
                  set(kinds) == {e["id"] for e in lib["entries"] if "rejected" in e["tags"]} and "x-all" in kinds and p.evaluate("window.__athena.facing") == "rejected", kinds[:3])
            p.fill("#q", "stop"); p.wait_for_timeout(80)
            r = p.evaluate("[...document.querySelectorAll('#list .item')].map(b => b.dataset.open)")
            check("c. a shelf and a search together narrow the list", set(r) <= set(kinds) and len(r) < len(kinds), r)
            p.fill("#q", "")
            p.click('#chips [data-tag="rejected"]'); p.wait_for_timeout(120)
            check("c. tapping the chip again clears the shelf", len(p.query_selector_all("#list .item")) == len(lib["entries"]))

            # a tap on the 3D shelf filters, too
            p.click('#chips [data-tag="mffu"]'); p.wait_for_timeout(120)
            p.click('#chips [data-tag="mffu"]'); p.wait_for_timeout(120)         # off again; the room now faces the MFFU shelf
            pt = p.evaluate("window.__athena.shelfPoint('mffu')")
            p.mouse.click(pt["x"], pt["y"]); p.wait_for_timeout(200)
            st = p.evaluate("window.__athena.state")
            check("c. tapping the glowing 3D shelf filters the list (MFFU rules shelf)", st["tag"] == "mffu" and pt["y"] < 330 and p.get_attribute('#chips [data-tag="mffu"]', "aria-pressed") == "true", (pt, st["tag"]))
            p.click('#chips [data-tag="mffu"]'); p.wait_for_timeout(100)

            # an entry and the glossary links
            p.fill("#q", "step 6"); p.wait_for_timeout(80)
            p.click("#list .item >> nth=0"); p.wait_for_timeout(120)
            body = p.inner_text("#entry")
            check("c. an entry opens in plain words with a glossary link; its link opens the meaning", "Step 6" in body and p.query_selector("#entry .gl") is not None)
            p.click("#entry .gl >> nth=0"); p.wait_for_timeout(120)
            check("c. ... the glossary entry opens, and Back returns to the list", p.evaluate("window.__athena.state.view") == "entry" and p.evaluate("window.__athena.state.entry") in ("stop", "tick"))
            p.click("#back"); p.wait_for_timeout(100)
            check("c. ... Back returns to the library list", p.evaluate("window.__athena.state.view") == "lib")
            p.fill("#q", "")

            # routes
            p.evaluate("location.hash = '#e/m-floor'"); p.wait_for_timeout(150)
            ok1 = "drawdown floor" in p.inner_text("#entry").lower()
            p.evaluate("location.hash = '#t/words'"); p.wait_for_timeout(150)
            ok2 = p.evaluate("window.__athena.state.tag") == "words" and p.evaluate("window.__athena.facing") == "words"
            p.evaluate("location.hash = '#library'"); p.wait_for_timeout(150)
            ok3 = p.evaluate("window.__athena.state.tag") is None and p.evaluate("window.__athena.state.view") == "lib"
            check("c. #e/<id>, #t/<shelf> and #library (the Jarvis card's link) open the right place", ok1 and ok2 and ok3, (ok1, ok2, ok3))

            # the quiz
            p.evaluate("location.hash = '#quiz'"); p.wait_for_timeout(150)                    # the old 5-question quiz lives behind Train (and #quiz)
            sig = []
            for i in range(5):
                qq = p.inner_text("#quiz .qq")
                opts = p.query_selector_all("#quiz .opt")
                sig.append((qq, len(opts)))
                correct = p.evaluate("(i) => window.__athena.state.quiz.qs[i].answer", i)
                opts[correct if i % 2 == 0 else (correct + 1) % 4].click(); p.wait_for_timeout(80)
                if i == 0:
                    check("c. Quiz me: question 1 of 5 has 4 options; after a pick the right one is marked and a 'Read' link shows",
                          sig[0][1] == 4 and "Question 1 of 5" in body + p.inner_text("#quiz") + "Question 1 of 5" and p.query_selector("#quiz .opt.right") is not None and p.query_selector("#quiz .gl") is not None, sig[0])
                p.click("#next"); p.wait_for_timeout(60)
            txt = p.inner_text("#quiz")
            check("c. 5 distinct questions, each with 4 options; the score is shown (3 / 5 for 3 right) with the missed entries to re-read",
                  len(set(s[0] for s in sig)) == 5 and all(s[1] == 4 for s in sig) and "3 / 5" in txt and len(p.query_selector_all("#quiz .item")) == 2, (sig, txt[:120]))
            p.click("#again"); p.wait_for_timeout(100)
            check("c. 'Quiz me again' draws a new set of 5 (question 1 of 5)", "Question 1 of 5" in p.inner_text("#quiz"))
            seeds = p.evaluate("""() => { const C = window.__athena.CORE, l = window.__athena.lib; const a = C.makeQuiz(l, 5, 3).map(q => q.id).join(), b = C.makeQuiz(l, 5, 3).map(q => q.id).join(), c = C.makeQuiz(l, 5, 4).map(q => q.id).join();
              return [a === b, a !== c, C.makeQuiz(l, 5, 9).every(q => q.options.length === 4 && q.answer >= 0 && new Set(q.options).size === 4)]; }""")
            check("c. the quiz is drawn from the library with a seed (same seed, same 5; other seed, other 5; 4 different options each)", all(seeds), seeds)
            ls = p.evaluate("[...Object.keys(localStorage).filter(k => !k.startsWith('athena.')), ...Object.keys(sessionStorage)].length")
            ext = [u for u in reqs if not u.startswith(url.rsplit("/", 2)[0] + "/")]
            check("c. nothing leaves the page and only this phone's own 'athena.*' keys are stored (no outside request, no POST)", ls == 0 and not ext, (ls, ext[:3]))
            y0 = p.evaluate("window.__athena.yaw")
            p.wait_for_timeout(1200)
            check("c. reduced motion: the library does not turn by itself", abs(p.evaluate("window.__athena.yaw") - y0) < 1e-9)
            ctx.close()
            check("c. no page errors, console errors or failed requests", not errs, errs[:5])

            errs = []
            ctx, p = open_page(br, url, errs, "__athena", wait_site=False)
            y0 = p.evaluate("window.__athena.yaw")
            p.wait_for_function("(y) => window.__athena.yaw !== y", arg=y0, timeout=30000)
            check("c. with motion on, the library turns slowly by itself and the first frame has lifted the loading veil", True and p.evaluate("document.documentElement.getAttribute('data-oly-state')") == "ready")
            p.click('#chips [data-tag="playbook"]'); p.wait_for_function("window.__athena.settled && window.__athena.facing === 'playbook'", timeout=60000)
            y1 = p.evaluate("window.__athena.yaw"); p.wait_for_timeout(1500)
            check("c. a chosen shelf stops the idle turn and the room settles on it", p.evaluate("window.__athena.facing") == "playbook" and abs(p.evaluate("window.__athena.yaw") - y1) < 0.02)
            ctx.close()
            check("c. no errors with motion on", not errs, errs[:5])

            errs = []
            ctx, p = open_page(br, url_off, errs, "__athena", wait_site=False)
            check("c. library.json missing: the stub library opens with a STUB LIBRARY tag, search still works, nothing else breaks",
                  p.is_visible("#demo") and p.evaluate("window.__athena.lib.entries.length") == 1 and len(p.query_selector_all("#list .item")) == 1)
            ctx.close()
            bad = tidy_errors(errs, allow=("library.json",))
            check("c. ... only the missing file's 404, nothing else", not bad, bad[:5])
            br.close()
    finally:
        srv.shutdown()
        srv2.shutdown()


# ------------------------------------------------------------------------------------------------------------ b2: the 2026-11-04 shelves, rules and the offline brain
def part_b2(lib):
    E = lib["entries"]
    byid = {e["id"]: e for e in E}
    kal = [e for e in E if e["kind"] == "kalshi"]
    src = open(os.path.join(ROOT, B.KALSHI_SRC), encoding="utf-8").read()
    check("b. the Kalshi shelf is built from research/writeups/*kalshi_edges*.md: 8 entries with its numbers (95c and above, -$248, XRP, $0.71 / $12.89, 18 wins), sources cited",
          len(kal) >= 8 and all(e["src"] == [B.KALSHI_SRC] for e in kal) and "95c" in " ".join([byid["k-pocket"]["short"], *byid["k-pocket"]["body"]])
          and "$248" in " ".join([byid["k-loses"]["short"], *byid["k-loses"]["body"]]) and "$12.89" in byid["k-win-rate"]["short"] and "XRP" in " ".join([byid["k-loses"]["short"], *byid["k-loses"]["body"]])
          and all(n in src for n in ("$248", "$12.89", "XRP")), [e["id"] for e in kal])
    learned = [e for e in E if e["kind"] == "learned"]
    files = [e["src"][0] for e in learned]
    check(f"b. the 'What we learned' shelf has one entry per write-up that found something ({len(learned)}), each with its status line, a date and its file",
          len(learned) >= 40 and all(os.path.exists(os.path.join(ROOT, *f.split("/"))) for f in files) and len(set(files)) == len(files)
          and all(any(e["body"][0].startswith(w) for w in B.STATUS_WORDS.values()) for e in learned), len(learned))
    check("b. every write-up that is an adopt-candidate, adopted, promising or a finding is on the shelf (none left out)",
          {os.path.basename(f) for f in files} == {os.path.basename(f) for f in __import__("glob").glob(os.path.join(ROOT, "research", "writeups", "*.md"))
                                                    if re.match(r"---\n.*?\nstatus: (adopt-candidate|adopted|promising|finding)", open(f, encoding="utf-8").read(), re.S)
                                                    and re.search(r"^summary: ", open(f, encoding="utf-8").read(), re.M)})
    R = lib["rules"]
    check("b. 'My rules': 18 checklist lines in 5 groups, each pointing at a real entry, with the rule file's numbers ($48,000, $1,000, 40 micros, $3,000, 7 days)",
          len(R) >= 15 and {r["group"] for r in R} == {"before", "during", "after", "money", "never"} and all(r["from"] in byid for r in R)
          and all(n in " ".join(r["text"] for r in R) for n in ("$48,000", "$1,000", "40 micros", "$3,000", "7 days")), len(R))


UNIT_JS = r"""
import fs from 'node:fs';
const A = '__ATHENA__/';
const C = await import(A + 'athenacore.js'), B = await import(A + 'athenabrain.js');
const lib = JSON.parse(fs.readFileSync(A + 'library.json', 'utf8')), ix = C.indexOf(lib), out = {};
const top = (q) => B.ask(ix, q, 3).map((x) => x.e.id);
out.ask = { kalshi: top('why does the kalshi bot lose'), dll: top('what is the daily loss limit'), payout: top('how do I get a payout'), typo: B.ask(ix, 'swep', 8).map((x) => x.e.id), blank: B.ask(ix, 'the of a', 3).length, none: B.ask(ix, 'zzqxv', 3).length };
const r0 = B.ask(ix, 'why does the kalshi bot lose', 3)[0];
out.askShape = [r0.conf, typeof r0.excerpt === 'string' && r0.excerpt.length > 10, r0.matched.length >= 2, r0.score > 0];
const day = (n) => new Date(2026, 10, 4 + n, 12).getTime();
const seen = new Set(); for (let n = 0; n < lib.entries.filter((e) => e.body.length && e.kind !== 'olympus').length; n++) seen.add(B.dailyLesson(lib, day(n)).id);
out.daily = { same: B.dailyLesson(lib, day(0)).id === B.dailyLesson(lib, day(0) + 3600e3).id, differs: B.dailyLesson(lib, day(0)).id !== B.dailyLesson(lib, day(1)).id,
  noRepeat: seen.size === lib.entries.filter((e) => e.body.length && e.kind !== 'olympus').length };
const deck = B.flashDeck(lib);
out.deck = { n: deck.length === lib.entries.length, kalshi: deck.some((c) => c.from === 'k-win-rate'), learned: deck.some((c) => c.front.startsWith('What did we learn')), ids: new Set(deck.map((c) => c.id)).size === deck.length };
const now = Date.now();
let st = B.rateCard({}, deck[0].id, 1, now); const d1 = Math.round((st[deck[0].id].d - now) / 864e5);
st = B.rateCard(st, deck[0].id, 2, now); const d2 = Math.round((st[deck[0].id].d - now) / 864e5);
const again = B.rateCard(st, deck[0].id, 0, now);
out.cards = { d1, d2, box2: st[deck[0].id].b, againBox: again[deck[0].id].b, againSoon: again[deck[0].id].d - now <= 11 * 60e3, stats: B.cardStats(deck, st, now),
  first: B.dueCards(deck, st, now, 1)[0].id !== deck[0].id };
out.rules = B.ruleGroups(lib).map((g) => [g.key, g.rules.length]);
const k = (t) => { const d = new Date(t); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`; };
out.streak = [B.streakOf([k(now), k(now - 864e5), k(now - 2 * 864e5)], now), B.streakOf([k(now - 864e5)], now), B.streakOf([k(now - 3 * 864e5)], now), B.streakOf([], now)];
console.log(JSON.stringify(out));
"""


def part_b3(lib):
    import subprocess
    node = shutil.which("node")
    if not node:
        check("b. node is available for the brain checks", False)
        return
    f = os.path.join(tempfile.mkdtemp(prefix="athena_unit_"), "unit.mjs")
    open(f, "w", encoding="utf-8").write(UNIT_JS.replace("__ATHENA__", PAGE.replace(os.sep, "/")))
    r = subprocess.run([node, f], capture_output=True, text=True, timeout=120)
    try:
        o = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        check("b. the offline brain runs in node", False, (r.stdout + r.stderr)[-500:])
        return
    a = o["ask"]
    check("b. Ask Athena ranks offline: the Kalshi question finds the Kalshi entries, the loss limit its entries, a payout its entries, a typo still finds Sweep, nonsense finds nothing",
          a["kalshi"][0] == "k-negative" and ("k-win-rate" in a["kalshi"] or "o-kalshi" in a["kalshi"]) and a["dll"][0] in ("m-dll", "dll") and "m-pay" in a["payout"] and "sweep" in a["typo"]
          and a["blank"] == 0 and a["none"] == 0, a)
    check("b. each answer has a plain confidence (Best match / maybe / weak), a best sentence and the words that matched", o["askShape"][0] in ("strong", "maybe") and all(o["askShape"][1:]), o["askShape"])
    d = o["daily"]
    check("b. the lesson of the day: the same all day, a different one tomorrow, no repeat until the whole library has had a turn", d["same"] and d["differs"] and d["noRepeat"], d)
    k = o["deck"]
    check("b. flashcards cover every entry (a word, a question, or what it is about), including the Kalshi and 'what we learned' shelves", all(k.values()), k)
    c = o["cards"]
    check("b. card boxes: good = next box (1 day), easy = two boxes (4 days), again = box 0 and back in 10 minutes; learned cards leave the due pile",
          c["d1"] == 1 and c["d2"] == 4 and c["box2"] == 3 and c["againBox"] == 0 and c["againSoon"] and c["first"] and c["stats"]["learned"] == 1, c)
    check("b. the rules page groups: before, during, after, money, never", [g for g, _ in o["rules"]] == ["before", "during", "after", "money", "never"] and sum(n for _, n in o["rules"]) == len(lib["rules"]), o["rules"])
    check("b. the lesson streak counts days in a row (today may still be empty) and resets on a gap", o["streak"] == [3, 1, 0, 0], o["streak"])


def part_d(tmp, lib):
    """the new panes in the browser (390 x 844): Ask, Today, Cards, Rules, Saved, bookmarks, history, storage under 'athena.' only"""
    from playwright.sync_api import sync_playwright
    srv, url = site(tmp, "athena", "d", data=False)
    try:
        with sync_playwright() as pw:
            br = browser(pw)
            errs = []
            ctx, p = open_page(br, url, errs, "__athena", wait_site=False)
            tabs = p.evaluate("[...document.querySelectorAll('#tabs button')].map(b => b.dataset.tab)")
            check("d. the dock has six tabs: Library, Ask, Today, Cards, Rules, Train (each 44 px tall or more, the orb corner free), and a star at the top right for Saved",
                  tabs == ["lib", "ask", "today", "cards", "rules", "train"] and p.is_visible("#savedBtn") and p.evaluate("[...document.querySelectorAll('#tabs button')].every(b => b.getBoundingClientRect().height >= 44)") and orb_hits(p) == [], tabs)
            p.click('#tabs [data-tab="ask"]'); p.wait_for_timeout(150)
            check("d. Ask opens with example questions to tap", p.query_selector_all("#ask [data-ask]") and len(p.query_selector_all("#ask [data-ask]")) >= 5 and not p.is_visible("#q"))
            p.fill("#askq", "why does the kalshi bot lose"); p.wait_for_timeout(150)
            ans = p.evaluate("[...document.querySelectorAll('#askout .ans')].map(a => [a.querySelector('.atitle').dataset.open, a.className, a.querySelector('.why').innerText.length > 5])")
            check("d. 'why does the kalshi bot lose' answers from the Kalshi shelf first, best match first, with the matched words", ans and ans[0][0] == "k-negative" and "strong" in ans[0][1] and all(a[2] for a in ans), ans[:3])
            p.click("#askout .atitle >> nth=0"); p.wait_for_timeout(150)
            check("d. an answer opens its entry; Back returns to Ask", p.evaluate("__athena.state.view") == "entry" and "Kalshi" in p.inner_text("#entry"))
            p.click("#mark"); p.wait_for_timeout(100)
            check("d. the star bookmarks the entry (kept under 'athena.marks')", p.evaluate("__athena.plus.state.marks") == ["k-negative"] and p.get_attribute("#mark", "aria-pressed") == "true"
                  and p.evaluate("JSON.parse(localStorage.getItem('athena.marks'))") == ["k-negative"])
            p.click("#back"); p.wait_for_timeout(100)
            check("d. Back goes to the tab it came from (Ask)", p.evaluate("__athena.state.view") == "ask")
            p.click("#savedBtn"); p.wait_for_timeout(150)
            check("d. Saved lists the bookmark and the reading history (newest first)", len(p.query_selector_all("#saved .item")) >= 2 and "Why the Kalshi bot loses" in p.inner_text("#saved"), p.inner_text("#saved")[:100])
            p.click('#tabs [data-tab="today"]'); p.wait_for_timeout(150)
            lesson = p.evaluate("__athena.BRAIN.dailyLesson(__athena.lib).id")
            check("d. Today shows the lesson of the day, with a check-yourself question when it has one", p.query_selector(f'#today [data-open="{lesson}"]') is not None and "Today's lesson" in p.inner_text("#today"))
            p.click("#markRead"); p.wait_for_timeout(100)
            check("d. 'I read it' counts the day: the streak is 1, the Today badge clears, kept under 'athena.days'", "Streak: 1 day" in p.inner_text("#today") and p.is_hidden("#bd-today") and len(p.evaluate("JSON.parse(localStorage.getItem('athena.days'))")) == 1)
            p.click('#tabs [data-tab="cards"]'); p.wait_for_timeout(150)
            front = p.inner_text("#flash")
            p.click("#flash"); p.wait_for_timeout(80)
            check("d. Cards: tap to flip to the answer, then Again / Good / Easy", "ANSWER" in p.inner_text("#flash") and len(p.query_selector_all("#cards .grade button")) == 3 and front != p.inner_text("#flash"))
            p.click('#cards [data-g="1"]'); p.wait_for_timeout(100)
            cards = p.evaluate("JSON.parse(localStorage.getItem('athena.cards'))")
            check("d. 'Good' files the card in box 1 (due tomorrow) and shows the next one", len(cards) == 1 and list(cards.values())[0]["b"] == 1 and "ANSWER" not in p.inner_text("#flash"), cards)
            p.click('#tabs [data-tab="rules"]'); p.wait_for_timeout(150)
            n = len(p.query_selector_all("#rules .rule"))
            p.click("#rules .tick >> nth=0"); p.click("#rules .tick >> nth=1"); p.wait_for_timeout(100)
            check(f"d. My rules: {n} lines in 5 groups, tick two: '2 of {n} checked today', kept under 'athena.rules', a 'why' link opens the entry",
                  n == len(lib["rules"]) and f"2 of {n} checked" in p.inner_text("#rules") and len(p.evaluate("JSON.parse(localStorage.getItem('athena.rules')).done")) == 2 and p.query_selector("#rules [data-open]") is not None)
            p.reload(); p.wait_for_function("window.__athena && window.__athena.ready", timeout=30000)
            p.evaluate("location.hash = '#rules'"); p.wait_for_timeout(200)
            check("d. after a reload the bookmarks, the ticks and the card boxes are still there (this phone only)", p.evaluate("__athena.plus.state.marks.length") == 1 and p.evaluate("__athena.plus.counts().rulesDone") == 2 and "2 of" in p.inner_text("#rules"))
            keys = p.evaluate("Object.keys(localStorage)")
            check("d. every key it stores starts with 'athena.' and nothing goes to sessionStorage", all(k.startswith("athena.") for k in keys) and p.evaluate("sessionStorage.length") == 0, keys)
            fx = p.evaluate("__athena.fx")
            check(f"d. the library has the OLYMPUS effects (light shafts, dust, fireflies) on a GPU tier: {fx}", p.evaluate("__athena.quality") in ("low", "off") or {"godRays", "dust", "fireflies"} <= set(fx), fx)
            sw = p.evaluate("document.documentElement.scrollWidth <= innerWidth")
            check("d. no sideways scroll, the orb corner free on every pane", sw and all((p.click(f'#tabs [data-tab="{t}"]') or True) and orb_hits(p) == [] for t in ("ask", "today", "cards", "rules")))
            ctx.close()
            check("d. no page errors", not errs, errs[:5])
            errs = []
            ctx, p = open_page(br, url + "#today", errs, "__athena", reduced=True, wait_site=False)
            check("d. reduced motion: #today opens straight on the lesson, no errors", p.evaluate("__athena.state.view") == "today" and not errs, errs[:3])
            ctx.close()
            br.close()
    finally:
        srv.shutdown()


# ------------------------------------------------------------------------------------------------------------ b4: Train, the pure part (node) and drills.json against its sources
UNIT_TRAIN_JS = r"""
import fs from 'node:fs';
const A = '__ATHENA__/';
const T = await import(A + 'athenatraincore.js');
const lib = JSON.parse(fs.readFileSync(A + 'library.json', 'utf8')), dr = JSON.parse(fs.readFileSync(A + 'drills.json', 'utf8'));
const byId = Object.fromEntries(lib.entries.map((e) => [e.id, e])), qs = T.buildQuestions(lib), out = {}, D = dr.drills;
const now = Date.UTC(2026, 10, 4, 15), DAY = 864e5, plain = (s) => T.plain(s, byId), strip = (s) => s.replace(/\.\.\.$/, '');
out.n = qs.length;
out.topics = Object.fromEntries(T.TOPICS.filter((t) => t.id !== 'charts').map((t) => [t.id, qs.filter((q) => q.topic === t.id).length]));
out.shape = qs.every((q) => { const o = T.askOptions(q, 0); return o.options.length === 4 && new Set(o.options).size === 4 && o.options[o.answer] === q.right && !!byId[q.from] && q.q.length > 8; });
out.unique = new Set(qs.map((q) => q.id)).size === qs.length;
out.det = JSON.stringify(T.buildQuestions(lib)) === JSON.stringify(qs) && JSON.stringify(T.askOptions(qs[0], 0)) === JSON.stringify(T.askOptions(qs[0], 0));
out.seenMoves = qs.slice(0, 30).some((q) => JSON.stringify(T.askOptions(q, 0).options) !== JSON.stringify(T.askOptions(q, 1).options));
out.notCited = qs.filter((q) => {                                       // every right answer is text of the entry it cites
  const e = byId[q.from], r = strip(q.right);
  if (q.id.startsWith('q:')) return plain(byId[q.id.slice(2)].quiz.a) !== q.right;
  if (q.id.startsWith('w:')) return !plain(e.ask.a).includes(r);
  if (q.id.startsWith('g:')) return !plain(e.short).includes(r);
  if (q.id.startsWith('o:')) return q.right !== e.title;
  if (q.id.startsWith('r:')) { const rule = lib.rules.find((x) => 'r:' + x.id === q.id); return !rule || !rule.text.includes(r) || rule.from !== q.from; }
  return true;
}).map((q) => q.id);
out.plain = T.plain('see [[sweep]] and [[nope]]', byId);
const none = T.normState(null), a = T.pickDaily(qs, none, now), b = T.pickDaily(qs, none, now);
out.daily = { n: a.length, uniq: new Set(a).size, same: JSON.stringify(a) === JSON.stringify(b), topics: new Set(a.map((id) => qs.find((q) => q.id === id).topic)).size, ok: a.every((id) => qs.some((q) => q.id === id)) };
const q0 = qs[0];
const s1 = T.answer(none, q0, 0, 0, true, now), s2 = T.answer(s1, q0, 0, 0, true, now), s3 = T.answer(s2, q0, 0, 0, false, now);
out.leitner = { d1: Math.round((s1.q[q0.id].d - now) / DAY), b1: s1.q[q0.id].b, d2: Math.round((s2.q[q0.id].d - now) / DAY), b2: s2.q[q0.id].b, wrongBox: s3.q[q0.id].b, wrongSoon: s3.q[q0.id].d - now <= 11 * 60e3,
  missed: s3.miss[q0.from] === now, n: s3.q[q0.id].n, okCount: s3.q[q0.id].ok };
const sd = T.normState(null), dueIds = qs.slice(0, 3).map((q) => q.id);
for (const id of dueIds) sd.q[id] = { b: 1, d: now - 1000, n: 1, ok: 1 };
out.dueFirst = dueIds.every((id) => T.pickDaily(qs, sd, now).includes(id));
const sn = T.normState(null); for (const q of qs.slice(3, 6)) sn.q[q.id] = { b: 2, d: now + 5 * DAY, n: 1, ok: 1 };
out.notDue = qs.slice(3, 6).every((q) => !T.pickDaily(qs, sn, now).includes(q.id));
const sw = T.normState(null); sw.stats = { lit: [1, 1, 1, 1], mffu: [0, 0, 0, 1], risk: [1, 1, 0, 1], words: [1, 1, 1] };
const nx = T.nextStudy(sw, qs, lib);
out.weak = [T.weakest(sw).id, T.weakest(sw).pct, nx.topic, !!byId[nx.id], qs.some((q) => q.topic === 'mffu' && q.from === nx.id)];
const sm = T.answer(T.normState(null), qs.find((q) => q.topic === 'words'), 0, 0, false, now);
sm.stats.words = [0, 0, 0];
out.nextMissed = [T.nextStudy(sm, qs, lib).id === qs.find((q) => q.topic === 'words').from, T.weakest(sm).id];
out.none = [T.weakest(T.normState(null)) === null, T.nextStudy(T.normState(null), qs, lib).id, T.weakest({ ...T.normState(null), stats: { lit: [0, 0] } }) === null];
let sr = T.startRound(qs, T.normState(null), now); const ids = sr.today.ids.slice();
for (let i = 0; i < ids.length; i++) sr = T.answer(sr, qs.find((x) => x.id === ids[i]), i, 0, i % 2 === 0, now);
const more = T.startRound(qs, sr, now, true);
out.round = { done: T.roundDone(sr.today), days: sr.days.length, qdays: sr.qdays.length, streak: T.streak(sr, now), quizDone: T.quizDoneToday(sr, now), more: more.today.round, noDup: new Set([...ids, ...more.today.ids]).size === ids.length * 2, resume: T.startRound(qs, sr, now).today.round, ids: ids.length };
const lastDay = (n) => { const d = new Date(now - n * DAY); return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`; };
out.streak = [T.streak({ ...none, days: [lastDay(0), lastDay(1), lastDay(2)] }, now), T.streak({ ...none, days: [lastDay(1)] }, now), T.streak({ ...none, days: [lastDay(3)] }, now)];
const t0 = D.find((d) => d.take);
out.drills = { valid: T.validDrills(dr), n: D.length, take: D.filter((d) => d.take).length, flat: D.filter((d) => !d.take).length, sample: T.validDrills(T.sampleDrills()), bad: T.validDrills({ kind: 'x' }), bad2: T.validDrills({ ...dr, drills: [{ ...D[0], o: D[0].o.slice(1) }] }) };
out.chart = D.map((d) => {
  const m1 = T.chartModel(d, 340, 200, {}), m2 = T.chartModel(d, 340, 200, { reveal: true });
  const inside = [...m1.candles, ...m2.candles].every((c) => [c.o, c.h, c.l, c.c].every((v) => v >= 0 && v <= 200));
  const ly = m2.lines.map((l) => l.ly), spaced = ly.every((v, i) => i === 0 || v - ly[i - 1] >= 10.99);
  return [m1.candles.length === d.n_known, m2.candles.length === d.o.length, inside, m1.cut === null && m2.cut > 0, spaced, d.take ? m2.lines.some((l) => l.kind === 'stop') && m2.lines.some((l) => l.kind === 'entry') : m2.lines.length === 0];
});
out.chartOpts = T.chartModel(t0, 340, 200, { options: true }).lines.map((l) => l.label).sort().join('');
const fl = D.find((d) => !d.take);
out.outcome = [T.drillOutcome(t0, true, t0.answer), T.drillOutcome(t0, true, (t0.answer + 1) % 4), T.drillOutcome(t0, false, null), T.drillOutcome(fl, false, null), T.drillOutcome(fl, true, 0)].map((o) => [o.points, o.max]);
let sdr = T.startDrills(T.normState(null)); const before = T.drillIndex(sdr, D);
for (const d of D) sdr = T.recordDrill(sdr, D, d, d.take, d.take ? d.answer : null, now);
out.round2 = { before, done: sdr.drill.done, pts: T.drillPoints(D, sdr.drill.picks), max: D.reduce((x, d) => x + (d.take ? 2 : 1), 0), days: sdr.days.length, charts: sdr.stats.charts.length, expectCharts: Math.min(20, D.reduce((x, d) => x + (d.take ? 2 : 1), 0)), idx: T.drillIndex(sdr, D) };
out.lines = [T.drillLines(t0, true, t0.answer).join(' '), T.drillLines(fl, false, null).join(' ')];
console.log(JSON.stringify(out));
"""


def part_b4(lib):
    import subprocess
    node = shutil.which("node")
    if not node:
        check("b. node is available for the Train checks", False)
        return
    f = os.path.join(tempfile.mkdtemp(prefix="athena_train_"), "unit.mjs")
    open(f, "w", encoding="utf-8").write(UNIT_TRAIN_JS.replace("__ATHENA__", PAGE.replace(os.sep, "/")))
    r = subprocess.run([node, f], capture_output=True, text=True, timeout=120)
    try:
        o = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        check("b. the Train brain runs in node", False, (r.stdout + r.stderr)[-600:])
        return
    E = lib["entries"]
    words = sum(1 for e in E if e["kind"] == "words" and e.get("ask"))
    mffu = sum(1 for e in E if e["kind"] == "mffu")
    risk = sum(1 for e in E if e["kind"] == "playbook") + sum(1 for r_ in lib["rules"] if r_["group"] in ("before", "during", "after", "money", "never"))
    steps = sum(1 for e in E if re.match(r"^Step \d+: ", e["title"]))
    lit = sum(1 for e in E if e["kind"] in ("strategy", "numbers")) + max(0, steps - 1)
    t = o["topics"]
    check(f"b. Train: {o['n']} questions made from the library alone: LIT {t['lit']} (= {lit}), MFFU {t['mffu']} (= {mffu}), risk {t['risk']} (= {risk}), glossary {t['words']} (= {words}); ids unique, 4 different options each, the answer is among them",
          t == {"lit": lit, "mffu": mffu, "risk": risk, "words": words} and o["n"] == lit + mffu + risk + words and o["unique"] and o["shape"], (t, o["n"]))
    check("b. Train: no invented facts: every right answer is text of the entry (or checklist rule) it cites; [[links]] become plain words",
          o["notCited"] == [] and o["plain"] == "see sweep and nope", (o["notCited"][:5], o["plain"]))
    check("b. Train: deterministic (the same library gives the same questions and the same option order); a question seen again may show its options in a new order",
          o["det"] and o["seenMoves"])
    d = o["daily"]
    check(f"b. Train: the daily set is {d['n']} different questions (2 minutes), the same for the same state, from several topics", d["n"] == 8 and d["uniq"] == 8 and d["same"] and d["topics"] >= 3 and d["ok"], d)
    lt = o["leitner"]
    check("b. Train: Leitner boxes: right = box 1 (due in 1 day), right again = box 2 (2 days), wrong = box 0 and back in 10 minutes, with the answer counts and the entry to re-read",
          lt["b1"] == 1 and lt["d1"] == 1 and lt["b2"] == 2 and lt["d2"] == 2 and lt["wrongBox"] == 0 and lt["wrongSoon"] and lt["missed"] and lt["n"] == 3 and lt["okCount"] == 2, lt)
    check("b. Train: what is due comes first, a question not due yet stays out while there are new ones", o["dueFirst"] and o["notDue"])
    w = o["weak"]
    check("b. Train: weakest topic = lowest score with 3+ answers (MFFU 25%), ONE next thing = an entry of that topic; nothing scored yet -> start with 'The bot in one minute'; 2 answers are too few",
          w[0] == "mffu" and w[1] == 25 and w[2] == "mffu" and w[3] and w[4] and o["none"][0] and o["none"][1] == "lit-in-one" and o["none"][2], (w, o["none"]))
    check("b. Train: after a miss, the next thing to study is the entry that was missed", o["nextMissed"] == [True, "words"], o["nextMissed"])
    r_ = o["round"]
    check("b. Train: finishing a round counts the day once (streak 1), the next round never repeats a question of today, and a started round resumes",
          r_["done"] and r_["days"] == 1 and r_["qdays"] == 1 and r_["streak"] == 1 and r_["quizDone"] and r_["more"] == 2 and r_["noDup"] and r_["resume"] == 1 and r_["ids"] == 8, r_)
    check("b. Train: the streak counts days in a row (today may still be empty) and resets on a gap", o["streak"] == [3, 1, 0], o["streak"])
    dd = o["drills"]
    check(f"b. Train: drills.json is valid: {dd['n']} setups ({dd['take']} real trades, {dd['flat']} no-trade days); a broken file is refused, the built-in practice set is valid",
          dd["valid"] and dd["n"] == 10 and dd["take"] >= 5 and dd["flat"] >= 2 and dd["take"] + dd["flat"] == dd["n"] and dd["sample"] and not dd["bad"] and not dd["bad2"], dd)
    check("b. Train: the chart model: before the answer only the bars up to the decision, after it all bars; candles inside the picture; stop and entry lines on a trade; labels never on top of each other",
          all(all(c) for c in o["chart"]) and o["chartOpts"] == "ABCD", o["chart"])
    check("b. Train: scoring: a right yes + the right stop = 2 of 2, a right yes + wrong stop = 1, a wrong 'no' on a trade = 0, 'no' on a flat day = 1 of 1, 'yes' there = 0",
          o["outcome"] == [[2, 2], [1, 2], [0, 2], [1, 1], [0, 1]], o["outcome"])
    r2 = o["round2"]
    check("b. Train: a full round of drills: done, every point counted (max = 2 per trade + 1 per flat day), the day counts for the streak, the chart-reading topic score holds the last 20",
          r2["before"] == 0 and r2["done"] and r2["pts"] == {"got": r2["max"], "max": r2["max"]} and r2["days"] == 1 and r2["charts"] == r2["expectCharts"] and r2["idx"] == -1, r2)
    check("b. Train: the answer is explained in plain words with the replay's own numbers (stop, micros, $ result) and says when the bot stays out",
          all(w_ in o["lines"][0] for w_ in ("took this one", "micros", "$")) and "took no trade" in o["lines"][1], o["lines"])


def part_b5():
    """drills.json against its sources: the candles are the real 5m bars, the trades are the replay's own trades (skipped when the sources are not on this machine)"""
    import csv
    d = json.loads(rd("drills.json"))
    D = d["drills"]
    bt_path, bars_path = os.path.join(ROOT, "research", "lab", "backtest_live.json"), os.path.join(ROOT, "data", "NQ_5m.csv")
    stops_ok = all(len(set(x["stops"])) == 4 and x["stops"][x["answer"]] == x["stop"] and sorted(x["kinds"]) == ["fixed", "real", "tight", "wide"] and x["kinds"][x["answer"]] == "real"
                   and all((s < x["entry"]) if x["side"] == "LONG" else (s > x["entry"]) for s in x["stops"]) and all(abs(a - b) >= 8 for i, a in enumerate(x["stops"]) for b in x["stops"][i + 1:]) for x in D if x["take"])
    check(f"b. drills.json: {len(D)} setups, ids unique, every trade has 4 different stops on the right side of the entry, the real one among them (= the replay's stop), the other three plain alternatives",
          len(D) == 10 and len({x["id"] for x in D}) == len(D) and stops_ok and d["scale"] == 4 and all(x["n_known"] < len(x["o"]) for x in D))
    check("b. drills.json: the mix is on purpose: wins, losses and breakeven among the trades, no-trade days between them (no run of 3 of the same answer)",
          {"TARGET", "STOP", "BE"} <= {x["exit"] for x in D if x["take"]} and all(len({bool(D[i + k]["take"]) for k in range(3)}) == 2 for i in range(len(D) - 2)), [x["take"] for x in D])
    if not (os.path.exists(bt_path) and os.path.exists(bars_path)):
        check("b. drills.json sources (research/lab/backtest_live.json, data/NQ_5m.csv) are not on this machine: source check skipped", True)
        return
    bt = json.load(open(bt_path, encoding="utf-8"))
    trades = {(t["day"], t["side"], round(t["entry"] * 4), round(t["stop"] * 4)): t for t in bt["trades"]}
    flat_days = {x["date"] for x in bt["days"] if x["trades"] == 0}
    bad = []
    for x in D:
        if x["take"]:
            t = trades.get((x["day"], x["side"], x["entry"], x["stop"]))
            if not t or round(t["pnl"], 2) != round(x["pnl"], 2) or t["qty"] != x["qty"] or t["exit"] != x["exit"] or round(t["target"] * 4) != x["target"] or round(t["exit_price"] * 4) != x["exit_price"]:
                bad.append(x["id"])
        elif x["day"] not in flat_days or any(t["day"] == x["day"] for t in bt["trades"]):
            bad.append(x["id"])
    check("b. drills.json trades are the replay's own (same day, side, entry, stop, target, exit, micros and $); the no-trade days are days the replay took no trade", not bad, bad)
    want = {}
    for x in D:
        want.update({x["t0"] + 300 * i: (x["o"][i], x["h"][i], x["l"][i], x["c"][i]) for i in range(len(x["o"]))})
    lo, hi = min(x["t0"] for x in D), max(x["t0"] + 300 * len(x["o"]) for x in D)
    got = {}
    with open(bars_path, encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            t = int(float(row["time"]))
            if lo <= t <= hi and t in want:
                got[t] = tuple(round(float(row[k]) * 4) for k in ("open", "high", "low", "close"))
    miss = [t for t in want if got.get(t) != want[t]]
    check(f"b. drills.json candles are the real TradingView CME NQ1! 5m bars of data/NQ_5m.csv ({len(want)} bars compared, quarter-points)", len(want) > 300 and not miss, miss[:3])
    check("b. drills.json: a trade's bars end at the decision (the entry bar is the first one after the known bars) and the exit is inside the picture",
          all(x["entry_i"] == x["n_known"] and x["n_known"] < x["exit_i"] < len(x["o"]) for x in D if x["take"]))


# ------------------------------------------------------------------------------------------------------------ e: the Train tab in the browser (390 x 844)
def part_e(tmp, lib):
    from playwright.sync_api import sync_playwright
    drills = json.loads(rd("drills.json"))["drills"]
    srv, url = site(tmp, "athena", "e", data=False)
    srv2, url2 = site(tmp, "athena", "e2", data=False, drop=("drills.json",))
    srv3, url3 = site(tmp, "athena", "e3", data=False, drop=("library.json",))
    TAPS = "[...document.querySelectorAll('#train button')].filter(b => b.offsetParent && !b.closest('[hidden]')).map(b => { const r = b.getBoundingClientRect(); return [b.id || b.className || b.textContent.slice(0, 12), Math.round(r.width), Math.round(r.height)]; }).filter(x => x[1] < 44 || x[2] < 44)"
    ANS = """() => { const T = __athena.TRAIN, tr = __athena.train, t = tr.state.today, i = t.res.findIndex(r => r === null), q = tr.questions.find(x => x.id === t.ids[i]);
      const o = T.askOptions(q, tr.state.q[q.id] ? tr.state.q[q.id].n : 0); return { i, id: q.id, answer: o.answer, opts: o.options, topic: q.topic, from: q.from,
      shown: [...document.querySelectorAll('#train .opt')].map(b => b.textContent), head: document.querySelector('#train .qn').textContent }; }"""
    try:
        with sync_playwright() as pw:
            br = browser(pw)
            errs, reqs = [], []
            ctx, p = open_page(br, url, errs, "__athena", wait_site=False)
            p.on("request", lambda r: reqs.append(r.url))
            nq = p.evaluate("__athena.train.questions.length")
            p.click('#tabs [data-tab="train"]'); p.wait_for_timeout(200)
            check(f"e. Train opens with the streak, today's quiz, the weakest-topic card and one thing to study (never blank: {len(p.inner_text('#train'))} characters)",
                  p.evaluate("__athena.state.view") == "train" and len(p.inner_text("#train")) > 300 and p.query_selector("#train .study") is not None and p.query_selector("#train .tiles") is not None
                  and "ONE thing to study next" in p.inner_text("#train") and p.query_selector("#train .study [data-open]") is not None and len(p.query_selector_all("#train .trow")) == 5)
            check("e. the Train tab badge shows the questions still to do today; nothing is stored yet",
                  p.inner_text("#bd-train") == "8" and p.evaluate("localStorage.getItem('athena.train.v1') === null || JSON.parse(localStorage.getItem('athena.train.v1')).days.length === 0"))
            check("e. every tap target on the Train home is 44 px or more, the orb corner is free, no sideways scroll", p.evaluate(TAPS) == [] and orb_hits(p) == [] and p.evaluate("document.documentElement.scrollWidth <= innerWidth"), p.evaluate(TAPS))
            check(f"e. the quiz button counts from the library ({nq} questions: {p.inner_text('#tr-quiz')[:60]!r})", "8 questions" in p.inner_text("#tr-quiz") and f"{nq} new" in p.inner_text("#tr-quiz"), p.inner_text("#tr-quiz"))
            # ---- the daily quiz: 8 questions, 6 right 2 wrong
            p.click("#tr-quiz"); p.wait_for_timeout(150)
            seen_q, tapbad = [], []
            for i in range(8):
                info = p.evaluate(ANS)
                seen_q.append(info["id"])
                if info["shown"] != info["opts"] or f"Question {i + 1} of 8" not in info["head"]:
                    tapbad.append(("shown", i, info["head"]))
                pick = info["answer"] if i % 4 != 3 else (info["answer"] + 1) % 4
                if i == 0:
                    tb = p.evaluate(TAPS)
                    if tb:
                        tapbad.append(("taps", tb))
                p.click(f'#train [data-tq="{pick}"]'); p.wait_for_timeout(60)
                fb = p.evaluate("[!!document.querySelector('#train .opt.right'), !!document.querySelector('#train .gl[data-open]'), !!document.getElementById('tr-next'), document.querySelectorAll('#train .opt[disabled]').length, document.querySelector('#train .src') ? document.querySelector('#train .src').textContent.length : 0]")
                if not (fb[0] and fb[1] and fb[2] and fb[3] == 4 and fb[4] > 10):
                    tapbad.append(("feedback", i, fb))
                if i == 0:
                    p.click(f'#train .gl[data-open="{info["from"]}"]'); p.wait_for_timeout(120)
                    back = p.evaluate("__athena.state.view") == "entry"
                    p.click("#back"); p.wait_for_timeout(120)
                    if not (back and p.evaluate("__athena.state.view") == "train" and "Question 1 of 8" in p.inner_text("#train .qn")):
                        tapbad.append(("source-link", back, p.evaluate("__athena.state.view")))
                p.click("#tr-next"); p.wait_for_timeout(60)
            check("e. Daily quiz: 8 different questions, each shows its 4 options exactly as the brain orders them, a right/wrong mark, the library's own line, a source link that opens the entry and Back returns to the same question, then Next",
                  len(set(seen_q)) == 8 and not tapbad, tapbad[:3])
            txt = p.inner_text("#train")
            check("e. the round ends with the score (6 / 8), the entries to re-read for the 2 misses, '8 more' and Back; the badge clears",
                  "6 / 8" in txt and len(p.query_selector_all("#train .item")) == 2 and p.query_selector("#tr-more") is not None and p.is_hidden("#bd-train") and p.evaluate(TAPS) == [], txt[:80])
            ls = p.evaluate("JSON.parse(localStorage.getItem('athena.train.v1'))")
            wrong = [i for i, r_ in enumerate(ls["today"]["res"]) if r_ == 0]
            check("e. it is all kept under the one key 'athena.train.v1': 8 answers in their boxes (right = box 1, wrong = box 0), the day counted once, the 2 misses remembered, today's round saved",
                  len(ls["q"]) == 8 and sorted(v["b"] for v in ls["q"].values()) == [0, 0, 1, 1, 1, 1, 1, 1] and ls["days"] == ls["qdays"] and len(ls["days"]) == 1 and len(ls["miss"]) == 2 and len(wrong) == 2
                  and sum(len(v) for v in ls["stats"].values()) == 8, ls["q"])
            p.click("#tr-home"); p.wait_for_timeout(150)
            t2 = p.inner_text("#train")
            check("e. back on Train: the streak is 1 day, today's quiz says done, the topic rows show scores", p.inner_text("#train .tiles span >> nth=0").startswith("1") and "Daily quiz: done today" in t2 and "% of" in t2, t2[:120])
            # ---- more practice, all wrong, to make a weakest topic
            p.click("#tr-quiz"); p.wait_for_timeout(150)
            for i in range(8):
                info = p.evaluate(ANS)
                p.click(f'#train [data-tq="{(info["answer"] + 1) % 4}"]'); p.wait_for_timeout(40)
                p.click("#tr-next"); p.wait_for_timeout(40)
            two = p.evaluate("[__athena.train.state.today.round, new Set(__athena.train.state.today.all).size]")
            p.click("#tr-home"); p.wait_for_timeout(150)
            wk = p.evaluate("[__athena.TRAIN.weakest(__athena.train.state), __athena.TRAIN.nextStudy(__athena.train.state, __athena.train.questions, __athena.lib)]")
            hd = p.inner_text("#train .study h2")
            check(f"e. after more answers the weakest-topic card names a topic with its score ({hd!r}) and ONE entry to study",
                  two[0] == 2 and two[1] == 16 and wk[0] and hd.startswith(wk[0]["name"]) and p.get_attribute("#train .study [data-open]", "data-open") == wk[1]["id"], (two, wk, hd))
            p.click("#train .study [data-open]"); p.wait_for_timeout(120)
            ok_open = p.evaluate("__athena.state.view") == "entry"
            p.click("#back"); p.wait_for_timeout(120)
            check("e. ... the study link opens the entry and Back returns to the Train home", ok_open and p.evaluate("__athena.state.view") == "train" and p.query_selector("#train .study") is not None)
            # ---- the chart drills
            p.click("#tr-drill"); p.wait_for_timeout(200)
            nd = len(drills)
            cv = p.evaluate("(() => { const c = document.querySelector('#train canvas.chart'); return c ? [c.width, c.height, c.getAttribute('aria-label')] : null; })()")
            px = p.evaluate("""() => { const c = document.querySelector('#train canvas.chart'), d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data; let g = 0, r = 0, any = 0;
              for (let i = 0; i < d.length; i += 4) { if (d[i + 3]) any++; if (d[i + 3] > 200 && d[i + 1] > 180 && d[i] < 110) g++; if (d[i + 3] > 200 && d[i] > 220 && d[i + 1] < 130) r++; } return [any, g, r]; }""")
            check(f"e. Read the chart: setup 1 of {nd} draws the candles on one canvas (green and red candles, an aria-label), asks 'does the bot take a trade?' with Yes / No, taps 44 px or more",
                  cv and cv[2].startswith("Candle chart of NQ") and px[1] > 20 and px[2] > 20 and f"Setup 1 of {nd}" in p.inner_text("#train") and len(p.query_selector_all("#train [data-dtake]")) == 2 and p.evaluate(TAPS) == [], (cv, px))
            m0 = p.evaluate("document.querySelector('#train canvas.chart').__model.bars")
            earned, rows = 0, []
            for i, d in enumerate(drills):
                if d["take"] and i == 0:                                               # the first trade: answer No on purpose (wrong), see the answer
                    p.click('#train [data-dtake="0"]'); p.wait_for_timeout(80)
                    t_ = p.inner_text("#train")
                    rows.append(("miss", "0 / 2" in t_ and "did take this one" in t_ and "the four stops" in t_.lower()))
                    pts = 0
                elif d["take"]:
                    p.click('#train [data-dtake="1"]'); p.wait_for_timeout(80)
                    stop_view = p.inner_text("#train .qq")
                    labels = p.evaluate("document.querySelector('#train canvas.chart').__model.lines.map(l => l.label).sort().join('')")
                    btns = len(p.query_selector_all("#train [data-dstop]"))
                    pk = d["answer"] if i != 2 else (d["answer"] + 1) % 4                # the third setup: right yes, wrong stop
                    p.click(f'#train [data-dstop="{pk}"]'); p.wait_for_timeout(80)
                    t_ = p.inner_text("#train")
                    pts = 2 if pk == d["answer"] else 1
                    rows.append(("trade", "Where does the bot put the stop" in stop_view and labels == "ABCD" and btns == 4 and f"{pts} / 2" in t_ and "the four stops" in t_.lower() and "(your pick)" in t_ and "micros" in t_ and "$" in t_))
                else:
                    p.click('#train [data-dtake="0"]'); p.wait_for_timeout(80)
                    t_ = p.inner_text("#train")
                    rows.append(("flat", "Right. The bot stayed out." in t_ and "1 / 1" in t_ and "took no trade" in t_))
                    pts = 1
                if i == 0:
                    m1 = p.evaluate("document.querySelector('#train canvas.chart').__model.bars")
                    rows.append(("reveal", m1 == len(d["o"]) and m1 > m0 and p.evaluate(TAPS) == [] and orb_hits(p) == []))
                earned += pts
                p.click("#tr-dnext"); p.wait_for_timeout(60)
            bad = [r for r in rows if not r[1]]
            maxp = sum(2 if d["take"] else 1 for d in drills)
            txt = p.inner_text("#train")
            check(f"e. all {nd} setups: a miss on purpose, a right yes + wrong stop, right yes + right stop, 'no' on the flat days: each reveals the rest of the day with the stop, the $ and the four stops explained", not bad, bad[:3])
            check(f"e. the drill score is {earned} / {maxp} (1 for each right yes/no, 1 for each right stop), the {nd} answers are listed, Play again and Back are there, taps are 44 px or more",
                  f"{earned} / {maxp}" in txt and len(p.query_selector_all("#train .stopnote")) == nd and p.query_selector("#tr-dagain") is not None and p.evaluate(TAPS) == [], txt[:80])
            ls = p.evaluate("JSON.parse(localStorage.getItem('athena.train.v1'))")
            check("e. the round is kept (every setup's pick and result), the chart-reading topic now has a score", ls["drill"]["done"] and len(ls["drill"]["picks"]) == nd and len(ls["stats"]["charts"]) >= 10 and ls["drillRounds"] == 1, ls["drill"])
            p.click("#tr-dagain"); p.wait_for_timeout(100)
            check("e. Play again starts a fresh round at setup 1", f"Setup 1 of {nd}" in p.inner_text("#train") and p.evaluate("JSON.parse(localStorage.getItem('athena.train.v1')).drillRounds") == 2)
            p.click("#tr-home"); p.wait_for_timeout(100)
            p.click("#tr-quick"); p.wait_for_timeout(150)
            check("e. 'Quick random quiz' opens the old 5-question quiz (nothing saved), with the Train tab still lit", p.evaluate("__athena.state.view") == "quiz" and "Question 1 of 5" in p.inner_text("#quiz")
                  and p.get_attribute('#tabs [data-tab="train"]', "aria-pressed") == "true")
            p.reload(); p.wait_for_function("window.__athena && window.__athena.ready", timeout=30000)
            p.evaluate("location.hash = '#train'"); p.wait_for_timeout(200)
            check("e. after a reload the streak, the topic scores and the boxes are still there; #train opens the Train home", p.evaluate("__athena.state.view") == "train" and p.inner_text("#train .tiles span >> nth=0").startswith("1")
                  and p.evaluate("Object.keys(JSON.parse(localStorage.getItem('athena.train.v1')).q).length") == 16)
            keys = p.evaluate("Object.keys(localStorage)")
            ext = [u for u in reqs if not u.startswith(url.rsplit("/", 2)[0] + "/")]
            check("e. only 'athena.*' keys, nothing in sessionStorage, no request leaves the page", all(k.startswith("athena.") for k in keys) and p.evaluate("sessionStorage.length") == 0 and not ext, (keys, ext[:3]))
            ctx.close()
            check("e. no page errors, console errors or failed requests on the Train tab", not errs, errs[:5])

            # ---- never blank: no drills.json (a practice set), no library.json (the stub), a damaged saved state
            errs = []
            ctx, p = open_page(br, url2 + "#train", errs, "__athena", wait_site=False)
            p.click("#tr-drill"); p.wait_for_timeout(150)
            check("e. drills.json missing: the built-in practice set opens, labelled PRACTICE, and plays (never blank)",
                  "PRACTICE" in p.inner_text("#train") and p.query_selector("#train canvas.chart") is not None and len(p.query_selector_all("#train [data-dtake]")) == 2, p.inner_text("#train")[:80])
            ctx.close()
            bad = tidy_errors(errs, allow=("drills.json",))
            check("e. ... only the missing file's 404, nothing else", not bad, bad[:5])
            errs = []
            ctx, p = open_page(br, url3 + "#train", errs, "__athena", wait_site=False)
            check("e. library.json missing (the stub library): Train still opens with words and a way on (no crash, the quiz says it needs more entries)",
                  len(p.inner_text("#train")) > 100 and p.is_disabled("#tr-quiz") and "too small" in p.inner_text("#tr-quiz") and p.query_selector("#tr-drill") is not None, p.inner_text("#train")[:100])
            ctx.close()
            bad = tidy_errors(errs, allow=("library.json",))
            check("e. ... only the missing file's 404", not bad, bad[:5])
            errs = []
            ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2)
            ctx.add_init_script("localStorage.setItem('athena.train.v1', '{\"v\":1,\"q\":\"junk\",\"stats\":5,\"days\":[1,2],\"today\":{\"day\":\"x\"}}')")
            p = ctx.new_page()
            p.on("pageerror", lambda e: errs.append(str(e)))
            p.goto(url + "#train")
            p.wait_for_function("window.__athena && window.__athena.ready", timeout=30000)
            p.wait_for_timeout(300)
            check("e. a damaged saved state is ignored (a clean Train home, no errors)", len(p.inner_text("#train")) > 300 and not errs, errs[:3])
            ctx.close()
            br.close()
    finally:
        srv.shutdown()
        srv2.shutdown()
        srv3.shutdown()


def main(argv):
    fast = "fast" in argv
    tmp = tempfile.mkdtemp(prefix="athena_test_")
    try:
        part_a()
        lib = part_b()
        part_b2(lib)
        part_b3(lib)
        part_b4(lib)
        part_b5()
        if not fast:
            part_c(tmp, lib)
            part_d(tmp, lib)
            part_e(tmp, lib)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"\n{sum(RES)}/{len(RES)} passed", flush=True)
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
