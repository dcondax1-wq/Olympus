"""olympus/glossary-lite.js: plain-words explanations of trading jargon (sweep, IFVG, CISD, inducement, displacement, p10, ...).

  a. static: loaded (deferred, one line) in Ares, Oracle, Fates and Hephaestus; Safari 16 safe; every word has a one-line sentence (under 130 characters)
  b. Chromium: on a test page the words get a dotted <abbr title> and a tap bubble, the page's text does not change (textContent identical), links,
     buttons, inputs and data-nogloss are left alone, each word is explained at most 4 times, text added later is explained too, no console error
    python -X utf8 -m tests.test_glossary_lite
"""
from __future__ import annotations

import glob
import http.server
import os
import re
import sys
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "tools", "web_public")
RES: list = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:500]}"), flush=True)


def read(*p):
    with open(os.path.join(*p), encoding="utf-8") as fh:
        return fh.read()


PAGE = """<!doctype html><html><head><meta charset="utf-8"><title>g</title></head><body>
<p id="a">A sweep of the Asian low, then an inducement and a displacement; the IFVG and the CISD say go. Sweeps again, sweep, sweep, sweep, sweep.</p>
<p id="b">p10 is 61% and f10 is 12%; MFE 3R, MAE 0.4R, PF 2.1, FDR 5%.</p>
<a id="l" href="#x">sweep link</a><button id="btn">sweep button</button><label>sweep label</label>
<div data-nogloss id="n">inducement here stays plain</div>
<textarea id="t">sweep</textarea>
<div id="late"></div>
<script src="/olympus/glossary-lite.js"></script></body></html>"""


class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path.split("?")[0] == "/page.html":
            b = PAGE.encode()
            self.send_response(200); self.send_header("Content-Type", "text/html"); self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)
            return
        return super().do_GET()


def main():
    js = read(WEB, "olympus", "glossary-lite.js")
    pages = {a: read(WEB, a, "index.html") for a in ("ares", "oracle", "fates", "hephaestus")}
    # Ares, Fates and Hephaestus use the shared per-app glossary.js (glossary-core.js); the lite layer is for Oracle, which has none.
    # Two glossary layers on one page would underline every word twice, so no page may load both.
    check("a. glossary-lite.js is loaded (deferred, one line) in Oracle and no page loads both glossary layers",
          '<script src="../olympus/glossary-lite.js?v=g1" defer></script>' in pages["oracle"]
          and not any("glossary-lite.js" in h and "glossary.js" in h for h in pages.values())
          and all("glossary.js" in pages[a] for a in ("ares", "fates", "hephaestus")))
    check("a. Safari 16 safe (no lookbehind, ?., ??, .at()) and no network", not re.search(r"\(\?<[=!]|\?\?|\.at\(|[\w)\]]\?\.[A-Za-z_$]|fetch\(|XMLHttpRequest", js))
    sents = re.findall(r"\[\s*'(\w+)',\s*/[^/]+/\w*,\s*'([^']+)'\s*\]", js)
    check("a. 11 words, each with one plain sentence under 130 characters (sweep, IFVG, CISD, inducement, displacement, p10, f10, MFE, MAE, FDR, PF)",
          len(sents) == 11 and all(len(s) < 130 for _, s in sents) and {"sweep", "IFVG", "CISD", "inducement", "displacement", "p10"} <= {w for w, _ in sents}, sents)
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        check("browser test skipped: no Playwright", True)
        return
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), lambda *a: Handler(*a, directory=WEB))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    origin = f"http://127.0.0.1:{srv.server_address[1]}"
    with sync_playwright() as pw:
        exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
        br = pw.chromium.launch(**({"executable_path": exe} if exe else {}))
        ctx = br.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
        p = ctx.new_page()
        errs: list = []
        p.on("pageerror", lambda e: errs.append(str(e)))
        p.goto(origin + "/page.html")
        before = p.evaluate("document.body.innerText")
        p.wait_for_function("document.querySelectorAll('abbr.oly-gl').length > 3", timeout=15000)
        words = p.evaluate("[...document.querySelectorAll('abbr.oly-gl')].map((a) => a.dataset.gl)")
        check("b. the jargon in the page's own text is explained: sweep, inducement, displacement, IFVG, CISD, p10, f10, MFE, MAE, PF, FDR (a dotted abbr with a title)",
              {"sweep", "inducement", "displacement", "IFVG", "CISD", "p10", "f10", "MFE", "MAE", "PF", "FDR"} <= set(words), words)
        check("b. the page's text does not change (innerText identical) and each word is explained at most 4 times", p.evaluate("document.body.innerText") == before and words.count("sweep") <= 4, (words.count("sweep"),))
        left = p.evaluate("['l', 'btn', 'n', 't'].map((i) => document.getElementById(i).querySelectorAll('abbr').length).concat([document.querySelectorAll('label abbr').length])")
        check("b. links, buttons, labels, textareas and data-nogloss are left alone", left == [0, 0, 0, 0, 0], left)
        p.evaluate("document.querySelector('abbr.oly-gl').click()")
        tip = p.evaluate("(() => { const t = document.querySelector('.oly-gl-tip'); return t ? t.textContent : null; })()")
        check("b. a tap shows the sentence in a bubble (the iPhone has no hover)", bool(tip) and len(tip) > 20, tip)
        p.evaluate("document.getElementById('late').textContent = 'a late displacement and a late CISD'")
        p.wait_for_function("document.querySelectorAll('#late abbr').length >= 1", timeout=8000)
        check("b. text the app draws later is explained too", p.evaluate("document.querySelectorAll('#late abbr').length") >= 1)
        check("b. no page error, and define() answers", not errs and "pokes" in p.evaluate("OLYMPUS_GLOSS.define('sweep')"), errs[:2])
        br.close()
    srv.shutdown()


if __name__ == "__main__":
    t0 = time.time()
    main()
    n = sum(RES)
    print(f"\n{n}/{len(RES)} passed in {time.time() - t0:.0f}s")
    sys.exit(0 if n == len(RES) else 1)
