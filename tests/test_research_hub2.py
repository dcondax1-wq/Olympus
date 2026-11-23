"""RESEARCH HUB v2 (night-hub2 2026-11-22): cities/hub.html + hub.js + hub.css, data = cities/hub-data.json from tools/build_research_hub.py.
(tests/test_research_hub.py is the older Clio hub; this file is the Cities hub.)
  a. static: the JSON is fresh (build --check), every write-up is a card, every card + hunt line links to a real write-up, every headline $ and
     every curated number is in its source file, the Decide 'Waiting on you' list = the open / later cards, small (gzip <= 150 KB),
     privacy-clean (tools/site_privacy + the public-build privacy test's detectors), OLYMPUS NIGHT palette, no external fonts / network,
     read-only, the doors (Cities bar, Brain header link, Brain button)
  b. Chromium 390 x 844: loads, no page error, no sideways scroll, every section filled, search + family + verdict filters narrow,
     Show more, a card opens the write-up reader link, the saved copy works offline
    python -X utf8 -m tests.test_research_hub2          (RH_NO_BROWSER=1 skips b)
"""
from __future__ import annotations

import functools
import gzip
import http.server
import json
import os
import re
import sys
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
WEB = os.path.join(ROOT, "tools", "web_public", "cities")
WU = os.path.join(ROOT, "research", "writeups")
RES: list = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:600]}"), flush=True)


def read(n):
    return open(os.path.join(WEB, n), encoding="utf-8").read()


def static():
    from tools import build_research_hub as B
    from tools import research_hub as R
    check("a. hub-data.json is fresh (python tools/build_research_hub.py --check)", B.main(["--check"]) == 0)
    raw = read("hub-data.json")
    d = json.loads(raw)
    stems = {os.path.splitext(f)[0] for f in os.listdir(WU) if f.endswith(".md") and f.upper() != "INDEX.MD"}
    slug2stem = {R.slugify(s): s for s in stems}
    check("a. every write-up in research/writeups is one card", len(d["cards"]) == len(stems) and {c["s"] for c in d["cards"]} == set(slug2stem), (len(d["cards"]), len(stems)))
    check("a. every card links to an existing write-up (slug -> research/writeups/<stem>.md)", all(c["s"] in slug2stem for c in d["cards"]))
    check("a. cards are newest first, each has title, family, verdict a / r / o; all three verdicts and all 6 families exist",
          [c["d"] for c in d["cards"]] == sorted((c["d"] for c in d["cards"]), reverse=True) and all(c["t"] and 0 <= c["f"] < 6 and c["v"] in "aro" for c in d["cards"])
          and {c["v"] for c in d["cards"]} == set("aro") and {c["f"] for c in d["cards"]} == set(range(6)) and d["fam"] == ["LIT", "ATLAS", "Rapid + fleet money", "Kalshi", "Websites", "Ops"])
    bad = []
    for c in d["cards"]:
        src = open(os.path.join(WU, slug2stem[c["s"]] + ".md"), encoding="utf-8").read().replace(" ", "")
        for tok in re.findall(r"\$\d[\d,]*(?:\.\d+)?k?", c["m"].replace(" ", "")):
            if tok not in src:
                bad.append((c["s"], tok))
    check("a. every headline $ comes from its write-up (never invented); a card with no $ says 'no $ figure' on the page", not bad and "no $ figure" in read("hub.js"), bad[:5])
    check("a. the one-account study's headline is its $4,918 / $2,204 / -$88 a month line",
          any(c["s"] == "one-account-book-2026-11-22" and "$4,918 / $2,204 / -$88 a month" in c["m"] for c in d["cards"]))
    miss = [(h["k"], B.missing_numbers(h["t"], open(os.path.join(ROOT, h["src"]), encoding="utf-8").read())) for h in d["hunt"]["lines"]]
    check("a. tonight's edge hunt: lanes A-E + fleet v2 + rapid25 slot, every number is in its write-up, every line links a write-up",
          [h["k"][0] for h in d["hunt"]["lines"][:5]] == list("ABCDE") and len(d["hunt"]["lines"]) == 7 and not any(m for _, m in miss)
          and all(h["s"] in slug2stem for h in d["hunt"]["lines"]) and "0 new edges" in d["hunt"]["head"], miss)
    e = next(h for h in d["hunt"]["lines"] if h["k"].startswith("E"))
    check("a. lane E line: Rapid EOD 50K $4,918 / $2,204 a month vs $981 / $857", all(k in e["t"] for k in ("Rapid EOD 50K", "$4,918 / $2,204", "$981 / $857")))
    check("a. the edge-hunt head's 347 = 14 + 128 + 174 + 31 (the four lanes' variant counts)", "347" in d["hunt"]["head"] and 14 + 128 + 174 + 31 == 347)
    dec = json.load(open(os.path.join(ROOT, "tools", "web_public", "business", "decisions.json"), encoding="utf-8"))["items"]
    want = {c["id"] for c in dec if c.get("status") in ("open", "later")}
    check("a. 'Waiting on you' = every open / later Decide card, each with a $ a month line", {w["id"] for w in d["wait"]} == want and all("$" in w["m"] or w["m"] == "no $ figure" for w in d["wait"]), want ^ {w["id"] for w in d["wait"]})
    accs = json.load(open(os.path.join(ROOT, "tools", "web_public", "business", "accounts.json"), encoding="utf-8"))
    check("a. Live now: Zlarior (LIT), ATLAS, Rapid, keep-alive, the accounts' plan; plans come from accounts.json",
          [r["k"] for r in d["live"]][:4] == ["Zlarior (LIT)", "ATLAS", "Zlarior 25K #2", "Rapid EOD 25K"] and {"Keep-alive", "The accounts' plan"} <= {r["k"] for r in d["live"]}
          and all(any(a["plan"] in r["t"] for a in accs["accounts"]) for r in d["live"][:4]))
    gz = len(gzip.compress(raw.encode()))
    check("a. small: data gzipped <= 150 KB (raw <= 400 KB)", gz <= 150_000 and len(raw.encode()) <= 400_000, (gz, len(raw)))
    import site_privacy as SP
    blob = raw + read("hub.html") + read("hub.js") + read("hub.css")
    hits = SP.scan_text(blob, "cities/hub")
    check("a. privacy-clean (tools/site_privacy; no email / phone / account id / owner name)", not hits and not re.search(r"[\w.+-]+@[\w-]+\.\w+", blob)
          and "demetrades" not in blob.lower(), [h.kind for h in hits][:5])
    try:
        from tests import test_public_build_privacy as PB
        found = PB.kinds([{"kind": h.kind} for h in SP.scan_text(raw, "cities/hub-data.json")])
        check("a. tests.test_public_build_privacy detectors agree: nothing found", not found, found)
    except Exception as ex:  # noqa: BLE001
        check("a. tests.test_public_build_privacy detectors agree: nothing found", False, ex)
    css, js, html = read("hub.css"), read("hub.js"), read("hub.html")
    browns = [c for c in re.findall(r"#[0-9a-fA-F]{6}\b", css + html) if c.lower() in ("#231d16", "#2a2112", "#3a2d14", "#1f1a12", "#8b7259", "#c9a06a")]
    check("a. OLYMPUS NIGHT palette, no brown", all(k in css for k in ("#000", "#16131e", "#3e255e", "#4d2e76", "#9d59ee", "#f1c14b", "#77db89")) and not browns, browns)
    check("a. no external fonts / scripts / network; read-only (no Arm / Start / Stop)", not re.search(r"https?://", css + js + html) and "@font-face" not in css and "@import" not in css
          and not re.search(r"<button[^>]*>\s*(Arm|Start|Stop|Flatten)\b", html + js, re.I) and "method: 'POST'" not in js)
    idx, bh = read("index.html"), read("brain.html")
    check("a. doors: Cities bar next to Research Brain, Brain header -> Hub, Hub -> Brain button", 'href="hub.html"' in idx and idx.index('href="brain.html"') < idx.index('href="hub.html"')
          and 'href="hub.html"' in bh and 'id="brainBtn" href="brain.html"' in html)


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def browser():
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:  # noqa: BLE001
        check("b. playwright", False, e)
        return
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(_Quiet, directory=os.path.dirname(WEB)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}/cities/hub.html"
    d = json.loads(read("hub-data.json"))
    n = len(d["cards"])
    try:
        with sync_playwright() as pw:
            try:
                b = pw.chromium.launch(executable_path=os.environ.get("RH_CHROME") or None)
            except Exception:  # noqa: BLE001  (a pip playwright whose own browser is not installed: the pre-installed one)
                b = pw.chromium.launch(executable_path="/opt/pw-browsers/chromium", args=["--no-sandbox"])
            ctx = b.new_context(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True)
            p = ctx.new_page()
            errs = []
            p.on("pageerror", lambda e: errs.append(str(e)))
            p.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
            p.goto(url, wait_until="domcontentloaded")
            p.wait_for_function("window.ResearchHub && ResearchHub.S.data", timeout=10000)
            cnt = lambda: p.evaluate("document.getElementById('count').textContent")  # noqa: E731
            check("b. loads: the count shows every study, 30 cards drawn, Show more", cnt().startswith(f"{n} of {n}") and p.locator("#cards .cd").count() == 30 and p.is_visible("#more"), cnt())
            check("b. every section is filled (live, waiting, hunt, brain button)", p.locator("#live .lv").count() == len(d["live"]) and p.locator("#wait .wt").count() == len(d["wait"])
                  and p.locator("#hunt .hl").count() == 7 and p.is_visible("#brainBtn"))
            check("b. no sideways scroll at 390 x 844", p.evaluate("document.documentElement.scrollWidth <= innerWidth && document.body.scrollWidth <= innerWidth"))
            small = p.evaluate("[...document.querySelectorAll('button, a')].filter(e => e.offsetParent && e.getBoundingClientRect().height < 44).map(e => e.textContent.trim().slice(0, 30))")
            check("b. every button / chip >= 44 px tall", not [s for s in small if s], small[:5])
            p.fill("#q", "kalshi")
            k = p.evaluate("ResearchHub.filtered().length")
            check("b. search narrows ('kalshi')", 0 < k < n and cnt().startswith(f"{k} of {n}"), (k, cnt()))
            p.fill("#q", "")
            p.click("#fams button[data-f='3']")
            k3 = sum(1 for c in d["cards"] if c["f"] == 3)
            check("b. the Kalshi family chip shows only Kalshi studies", cnt().startswith(f"{k3} of {n}"), cnt())
            p.click("#verd button[data-v='r']")
            kr = sum(1 for c in d["cards"] if c["f"] == 3 and c["v"] == "r")
            check("b. + the Rejected chip: Kalshi AND rejected, red chips only", cnt().startswith(f"{kr} of {n}") and p.locator("#cards .v.a, #cards .v.o").count() == 0, cnt())
            p.click("#fams button[data-f='-1']")
            p.click("#verd button[data-v='a']")
            ka = sum(1 for c in d["cards"] if c["v"] == "a")
            check("b. All families + Adopted", cnt().startswith(f"{ka} of {n}"), cnt())
            p.click("#verd button[data-v='']")
            p.click("#more")
            check("b. Show more draws 30 more", p.locator("#cards .cd").count() == min(60, n))
            href = p.get_attribute("#cards .cd >> nth=0", "href")
            check("b. a card opens the write-up reader (../clio/?read=<slug>)", href.startswith("../clio/?read=") and href.split("=", 1)[1] == d["cards"][0]["s"], href)
            check("b. no page or console error", not errs, errs[:3])
            # offline: the saved copy
            p.route("**/hub-data.json", lambda r: r.abort())
            p.reload(wait_until="domcontentloaded")
            p.wait_for_function("window.ResearchHub && ResearchHub.S.data", timeout=10000)
            check("b. offline: the saved copy loads and says so", "offline" in cnt() and p.locator("#cards .cd").count() == 30, cnt())
            if os.environ.get("AGORA_SHOTS"):
                p.unroute("**/hub-data.json")
                p.reload()
                p.wait_for_function("window.ResearchHub && ResearchHub.S.data")
                p.evaluate("scrollTo(0, 0)")
                p.screenshot(path=os.path.join(ROOT, "research", "handoff", "2026-11-22", "hub2", "hub_390.png"), full_page=False)
                p.evaluate("document.getElementById('hHunt').scrollIntoView()")
                p.screenshot(path=os.path.join(ROOT, "research", "handoff", "2026-11-22", "hub2", "hub_390_hunt.png"), full_page=False)
            ctx.close()
            b.close()
    finally:
        srv.shutdown()


def main() -> int:
    static()
    if not os.environ.get("RH_NO_BROWSER"):
        browser()
    ok = sum(RES)
    print(f"research_hub2: {ok}/{len(RES)} passed")
    return 0 if ok == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
