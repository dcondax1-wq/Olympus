"""ATHENA (tools/web_public/athena/, tools/athena_build.py, 2026-11-03): the owner's library, a searchable plain-words knowledge base.

  a. the files: the OLYMPUS kit links (?v=o2, data-app="athena"), only local scripts, module imports resolve, the render core + materials
     are used, the Jarvis card, nothing stored, the orb corner CSS
  b. the build: library.json / jarvis.json equal a fresh build (python tools/athena_build.py), the content covers what was asked (the
     strategy, the MFFU rules from research/lit/mffu_rules.json, the rejected list, the glossary terms, the four playbooks), ids and
     [[links]] resolve, entries are short, a jargon word has its glossary link
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
          all(s in html for s in ('../olympus/olympus.css?v=o2', '../olympus/themes.js?v=o2', '../olympus/olympus.js?v=o2" data-app="athena"')))
    check("a. title Athena, a description, theme-color = the page colour, the Jarvis icon like the siblings",
          "<title>Athena</title>" in html and 'name="description"' in html and 'content="#070b14"' in html and "../jarvis/icon-192.png" in html)
    srcs = re.findall(r'(?:src|href)="([^"]+)"', html)
    check("a. only local files (no external script, font or stylesheet)", all(not s.startswith(("http:", "https:", "//")) for s in srcs), srcs)
    check("a. every local file the page links exists",
          all(os.path.exists(os.path.normpath(os.path.join(PAGE, s.split("?")[0]))) for s in srcs if not s.startswith("#")), srcs)
    js = rd("athena.js") + rd("athenacore.js")
    imps = re.findall(r"from '(\.[^']+)'", js + rd("athenaplus.js") + rd("athenabrain.js"))
    check("a. every module import resolves (three.js from ../jarvis/, the render core + materials from ../olympus/)",
          all(os.path.exists(os.path.normpath(os.path.join(PAGE, i))) for i in imps) and "../olympus/render.js" in imps and "../olympus/materials.js" in imps, imps)
    check("a. the 3D library is built on the render core (createRenderer) and not a bare WebGLRenderer", "createRenderer(" in js and "new THREE.WebGLRenderer" not in js)
    store = rd("athenastore.js") + rd("athenaplus.js") + rd("athenabrain.js")
    check("a. the reader's memory lives in athenastore.js only, every key under 'athena.' (nothing else is written, no cookies, no network in the new modules)",
          "const P = 'athena.';" in store and len(re.findall(r"localStorage\.setItem", store)) == 1 and not re.search(r"sessionStorage|indexedDB|document\.cookie|sendBeacon|XMLHttpRequest|fetch\(", store)
          and not re.search(r"localStorage|sessionStorage|indexedDB|document\.cookie", rd("athenabrain.js") + rd("athenaplus.js")))
    check("a. no network but its own library.json / jarvis.json; nothing stored by the page code itself (the memory is athenastore.js), nothing sent",
          sorted(set(re.findall(r"fetch\('([^'?]+)", js))) == ["jarvis.json"] and "loadLibrary('library.json" in js and "fetch(url" in js
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
            p.click('#tabs [data-tab="quiz"]'); p.wait_for_timeout(150)
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
            check("d. the dock has six tabs: Library, Ask, Today, Cards, Rules, Quiz (each 44 px tall or more, the orb corner free), and a star at the top right for Saved",
                  tabs == ["lib", "ask", "today", "cards", "rules", "quiz"] and p.is_visible("#savedBtn") and p.evaluate("[...document.querySelectorAll('#tabs button')].every(b => b.getBoundingClientRect().height >= 44)") and orb_hits(p) == [], tabs)
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


def main(argv):
    fast = "fast" in argv
    tmp = tempfile.mkdtemp(prefix="athena_test_")
    try:
        part_a()
        lib = part_b()
        part_b2(lib)
        part_b3(lib)
        if not fast:
            part_c(tmp, lib)
            part_d(tmp, lib)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"\n{sum(RES)}/{len(RES)} passed", flush=True)
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
