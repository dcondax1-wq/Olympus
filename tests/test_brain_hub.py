"""Research Brain hub (day-brain4 2026-11-22): the giant 3D brain of every finding (cities/brain.html + brain.js + brain-scene.js + brain.css,
data = cities/brain-data.json from tools/build_brain_hub.py).
  a. static: data is fresh vs LEDGER.md + TESTED_AND_REJECTED.md, every ledger row + every rejected bullet is a neuron, small + privacy-clean,
     three.js local only, OLYMPUS NIGHT colours (no brown), reduced motion / hidden tab / low-FPS rules in the source, read-only (no arm/start/stop)
  n. node: brain.js and the scene parse (node --check); the build script's parsers give the same count as the source files
  b. Chromium 390 x 844: loads, no page error, no sideways scroll, the 3D mounts within the neuron budget, a tap on a neuron opens its card,
     search narrows, the Adopted / Rejected / Open chips + family chips filter, the list opens, reduced motion = still, perf budget
    python -X utf8 -m tests.test_brain_hub          (BH_NO_BROWSER=1 skips b)
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
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
WEB = os.path.join(ROOT, "tools", "web_public", "cities")
RES: list = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:600]}"), flush=True)


def read(n):
    return open(os.path.join(WEB, n), encoding="utf-8").read()


def static():
    import build_brain_hub as B
    cur = json.loads(read("brain-data.json"))
    fresh = B.build()
    check("a. brain-data.json is fresh (python tools/build_brain_hub.py)", cur == fresh)
    n_led = sum(1 for ln in open(B.LEDGER, encoding="utf-8") if re.match(r"\|\s*\d{4}-\d\d-\d\d", ln))
    n_rej = sum(1 for ln in open(B.REJECTED, encoding="utf-8") if re.match(r"^\s*- ", ln))
    check("a. every ledger row + every rejected bullet is a neuron", len(cur["n"]) == n_led + n_rej, (len(cur["n"]), n_led, n_rej))
    kinds = {n["s"] for n in cur["n"]}
    check("a. all three kinds exist (mint adopted, red-violet rejected, gold open)", kinds == {"a", "r", "o"}, kinds)
    check("a. neurons carry the plain-words fields; synapses point at real neurons",
          all(n.get("t") and n.get("r") and n.get("v") and 0 <= n["f"] < len(cur["fam"]) for n in cur["n"])
          and all(0 <= a < len(cur["n"]) and 0 <= b < len(cur["n"]) and a != b for a, b in cur["e"]) and len(cur["e"]) > 20)
    raw = read("brain-data.json")
    check("a. the JSON is small (<= 60 KB, gzip <= 25 KB)", len(raw.encode()) <= 60000 and len(__import__("gzip").compress(raw.encode())) <= 25000, len(raw))
    import site_privacy as SP
    hits = SP.scan_text(raw, "brain-data.json")
    check("a. privacy-clean (tools/site_privacy detectors; no email / phone / account id)", not hits and not re.search(r"[\w.+-]+@[\w-]+\.\w+", raw), [h.kind for h in hits][:5])
    wu = [n["w"] for n in cur["n"] if n.get("w")]
    check("a. write-up links point at real research/writeups files", wu and all(os.path.exists(os.path.join(ROOT, "research", "writeups", w + ".md")) for w in wu), len(wu))
    js, sc, css, html = read("brain.js"), read("brain-scene.js"), read("brain.css"), read("brain.html")
    imps = re.findall(r"^import .* from '([^']+)';", sc, re.M)
    check("a. the scene imports only the local three.js; brain.js loads the scene by dynamic import after load", imps == ["../jarvis/three.module.min.js"]
          and "import('./brain-scene.js" in js and "three.module" not in js and "http" not in "".join(imps), imps)
    check("a. perf rules in the source: pause on a hidden tab + off screen, reduced motion = still, low-FPS drops effects, pixel ratio <= 2, context loss -> list",
          all(k in sc for k in ("visibilitychange", "IntersectionObserver", "ST.level++", "Math.min(window.devicePixelRatio || 1, ST.level >= 1 ? 1.25 : 2", "webglcontextlost"))
          and "prefers-reduced-motion" in js + css and "reduce" in sc)
    bad = [c for c in re.findall(r"#[0-9a-fA-F]{6}\b", css + sc + html) if c.lower() in ("#231d16", "#2a2112", "#3a2d14", "#1f1a12", "#8b7259", "#c9a06a")]
    check("a. OLYMPUS NIGHT palette (black, #16131e cards, violet, gold, mint), no brown", all(k in css + sc for k in ("#000", "#16131e", "#3e255e", "#4d2e76", "#9d59ee", "#f1c14b", "#77db89")) and not bad, bad)
    check("a. read-only: no Arm / Start / Stop / Flatten control", not re.search(r"<button[^>]*>\s*(Arm|Start|Stop|Flatten)\b", html + js, re.I))
    check("a. no network but the same-site public json; no secrets", not re.search(r"https?://", js + sc + html) and "ntfy" not in js)


def node():
    for f in ("brain.js", "brain-scene.js"):
        try:
            r = subprocess.run(["node", "--input-type=module", "--check"] if f.endswith("scene.js") else ["node", "--check", os.path.join(WEB, f)],
                               input=read(f) if f.endswith("scene.js") else None, capture_output=True, text=True, timeout=30)
            check(f"n. node parses {f}", r.returncode == 0, r.stderr)
        except Exception as e:  # noqa: BLE001
            check(f"n. node parses {f}", False, e)
    js = read("brain.js")
    # findLive: run the real function on fake status objects (no browser)
    m = re.search(r"function findLive\(o, depth\) \{.*?\n  \}\n", js, re.S)
    code = "const f=(function(){" + m.group(0) + "return findLive;})();" \
        "const t=[[{board:{open_position:{qty:1}}},true],[{board:{positions:[]}},false],[{live:{in_trade:true}},true],[{trades:[1,2]},false],[{}, false]];" \
        "for(const [o,w] of t) if(f(o.board||o.live||o,0)!==w){console.log('bad',JSON.stringify(o));process.exit(1)}"
    r = subprocess.run(["node", "-e", code], capture_output=True, text=True, timeout=30)
    check("n. the live-trade reader: an open position pulses, history / empty does not", r.returncode == 0, r.stdout + r.stderr)


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def browser():
    from tests import pw_skip
    if pw_skip.missing("b. (the browser part)"):            # night-reds2: the module missing = a printed SKIP, not a FAIL
        return
    from playwright.sync_api import sync_playwright
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(_Quiet, directory=os.path.dirname(WEB)))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}/cities/brain.html"
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(executable_path=os.environ.get("BH_CHROME") or None, args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])

            def page(**kw):
                ctx = b.new_context(viewport={"width": 390, "height": 844}, has_touch=True, **kw)
                p = ctx.new_page()
                errs = []
                p.on("pageerror", lambda e: errs.append(str(e)))
                p.on("console", lambda m: errs.append(m.text) if m.type == "error" and not re.search(r"GL Driver|GPU stall|WebGL|404", m.text) else None)
                return ctx, p, errs

            ctx, p, errs = page()
            p.goto(url, wait_until="domcontentloaded")
            p.wait_for_function("window.BrainHub && BrainHub.data", timeout=10000)
            n = p.evaluate("BrainHub.data.n.length")
            check("b. loads: the count line shows every finding", p.evaluate("document.getElementById('count').textContent").startswith(f"{n} of {n}"), p.evaluate("document.getElementById('count').textContent"))
            try:
                p.wait_for_function("BrainHub.stats() && BrainHub.stats().frames > 5", timeout=15000)
                st = p.evaluate("BrainHub.stats()")
            except Exception:  # noqa: BLE001
                st = None
            check("b. the 3D mounts and runs within the budget (<= 1,500 drawn things, <= 12 draw calls, pixel ratio <= 2)",
                  st and st["neurons"] == n and st["drawn"] <= 1500 and st["calls"] <= 12 and st["dpr"] <= 2, st)
            check("b. no sideways scroll at 390 x 844", p.evaluate("document.documentElement.scrollWidth <= innerWidth && document.body.scrollWidth <= innerWidth"))
            # tap a neuron in the canvas
            opened = None
            for i in range(0, n, 7):
                pt = p.evaluate(f"BrainHub.project({i})")
                if pt and 340 < pt["y"] < 700 and 10 < pt["x"] < 380:
                    p.touchscreen.tap(pt["x"], pt["y"])
                    p.wait_for_timeout(250)
                    if p.evaluate("document.getElementById('card').classList.contains('open')"):
                        opened = i
                        break
            card = p.evaluate("document.getElementById('card').innerText") if opened is not None else ""
            check("b. tap a neuron: its plain-words card opens (what we tested, the $ result, verdict)", opened is not None and all(k in card for k in ("WHAT WE TESTED", "THE $ RESULT", "VERDICT")), card[:200])
            p.click("#cx")
            check("b. the card closes", not p.evaluate("document.getElementById('card').classList.contains('open')"))
            p.fill("#q", "atlas")
            p.wait_for_timeout(300)
            c1 = p.evaluate("document.getElementById('count').textContent")
            k1 = int(re.match(r"(\d+) of", c1).group(1))
            check("b. search narrows (atlas)", 0 < k1 < n, c1)
            p.fill("#q", "zzzqqq")
            p.wait_for_timeout(300)
            check("b. a search with no match shows 0", p.evaluate("document.getElementById('count').textContent").startswith("0 of"))
            p.fill("#q", "")
            p.wait_for_timeout(300)
            for m in ("a", "r", "o"):
                p.click(f'[data-m="{m}"]')
                c = p.evaluate("document.getElementById('count').textContent")
                want = p.evaluate(f"BrainHub.data.n.filter(x => x.s === '{m}').length")
                check(f"b. chip filter '{m}' shows only those ({want})", c.startswith(f"{want} of"), c)
            p.click('[data-m="all"]')
            p.click("#famBtn")
            p.click('#fams [data-f="1"]')
            want = p.evaluate("BrainHub.data.n.filter(x => x.f === 1).length")
            check("b. By family: ATLAS only", p.evaluate("document.getElementById('count').textContent").startswith(f"{want} of"))
            p.click("#famBtn")
            p.click("#listBtn")
            check("b. the list opens with every finding as a row", p.locator("#lst li button").count() == n, p.locator("#lst li button").count())
            p.locator("#lst li button").nth(3).click()
            check("b. a list row opens the same card", p.evaluate("document.getElementById('card').classList.contains('open') && BrainHub.state.sel === 3"))
            p.evaluate("BrainHub.sweep()")
            p.wait_for_timeout(500)
            check("b. the pulse sweep runs without a page error", st is not None and p.evaluate("BrainHub.stats().running"))
            # hidden tab pauses
            p.evaluate("Object.defineProperty(document, 'hidden', {configurable: true, get: () => true}); document.dispatchEvent(new Event('visibilitychange'))")
            p.wait_for_timeout(200)
            check("b. a hidden tab pauses the loop", not p.evaluate("BrainHub.stats().running"))
            check("b. no page errors", not errs, errs[:3])
            ctx.close()
            # reduced motion: still frames
            ctx, p, errs = page(reduced_motion="reduce")
            p.goto(url, wait_until="domcontentloaded")
            try:
                p.wait_for_function("BrainHub.stats() && BrainHub.stats().frames >= 1", timeout=15000)
                p.wait_for_timeout(700)
                s = p.evaluate("BrainHub.stats()")
            except Exception:  # noqa: BLE001
                s = None
            check("b. reduced motion = a still frame (no running loop)", s and s["reduce"] and not s["running"] and s["frames"] < 6, s)
            ctx.close()
            # no WebGL -> the list still works
            ctx, p, errs = page()
            p.add_init_script("const g = HTMLCanvasElement.prototype.getContext; HTMLCanvasElement.prototype.getContext = function (t, o) { return /webgl/i.test(String(t)) ? null : g.call(this, t, o); };")
            p.goto(url, wait_until="domcontentloaded")
            p.wait_for_function("document.body.classList.contains('nogl')", timeout=15000)
            p.click("#listBtn")
            check("b. no WebGL: the list view still shows every finding", p.locator("#lst li button").count() > 50 and not errs, errs[:2])
            ctx.close()
            b.close()
    finally:
        srv.shutdown()


def main():
    static()
    node()
    if os.environ.get("BH_NO_BROWSER") != "1":
        browser()
    print(f"\n{sum(RES)}/{len(RES)} passed")
    sys.exit(0 if all(RES) else 1)


if __name__ == "__main__":
    main()
