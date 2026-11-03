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
    imps = re.findall(r"from '(\.[^']+)'", js)
    check("a. every module import resolves (three.js from ../jarvis/, the render core + materials from ../olympus/)",
          all(os.path.exists(os.path.normpath(os.path.join(PAGE, i))) for i in imps) and "../olympus/render.js" in imps and "../olympus/materials.js" in imps, imps)
    check("a. the 3D library is built on the render core (createRenderer) and not a bare WebGLRenderer", "createRenderer(" in js and "new THREE.WebGLRenderer" not in js)
    check("a. no network but its own library.json / jarvis.json; nothing stored (no localStorage / cookies), nothing sent",
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
            check("c. the page opens; the library has its entries; the 3D room is up with 6 shelves",
                  p.evaluate("window.__athena.lib.entries.length") == len(lib["entries"]) and p.evaluate("window.__athena.ready3d") is True and p.evaluate("window.__athena.shelves") == 6)
            q = p.evaluate("window.__athena.quality")
            ps = p.evaluate("window.__athena.passes")
            check("c. it runs on the render core: the pass list matches the tier (%s: %s)" % (q, ps), {"ultra": 3, "high": 3, "low": 2, "off": 1}[q] == len(ps), ps)
            check("c. no sideways scroll at 390 x 844", p.evaluate("document.documentElement.scrollWidth <= innerWidth && document.body.scrollWidth <= innerWidth"))
            check("c. the orb corner (bottom-right 80 x 160) is free of buttons and inputs", orb_hits(p) == [], orb_hits(p))
            n0 = len(p.query_selector_all("#list .item"))
            check("c. the list starts with every entry; six shelf chips with their counts", n0 == len(lib["entries"]) and len(p.query_selector_all("#chips .chip")) == 6, n0)

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
            ls = p.evaluate("localStorage.length + sessionStorage.length")
            ext = [u for u in reqs if not u.startswith(url.rsplit("/", 2)[0] + "/")]
            check("c. nothing leaves the page and nothing is stored (no storage, no outside request, no POST)", ls == 0 and not ext, (ls, ext[:3]))
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


def main(argv):
    fast = "fast" in argv
    tmp = tempfile.mkdtemp(prefix="athena_test_")
    try:
        part_a()
        lib = part_b()
        if not fast:
            part_c(tmp, lib)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"\n{sum(RES)}/{len(RES)} passed", flush=True)
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
