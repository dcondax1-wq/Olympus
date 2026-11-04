"""Safari / WebKit compatibility (docs/OLYMPUS_SAFARI.md): the owner is on an iPhone, every other test runs Chromium.

  lint   a static scan of the whole web tree (tools/web_public) for constructs that break in iOS Safari 16 / 17 (or have no value there)
         and are easy to add by accident in a Chromium-only run: a regex lookbehind or a newer Array / Object method in a script,
         an unprefixed backdrop-filter without its -webkit- twin, a bare `new AudioContext` without the webkit fallback, a float
         render target (iOS has EXT_color_buffer_half_float, not _float, for rendering), navigator.vibrate / getBattery unguarded,
         the Jarvis worker's SHELL list naming a file that does not exist (one 404 fails cache.addAll and the whole install)
  smoke  every page (about 30 apps, Jarvis, the dashboard) loaded in WebKit with the iPhone 13 profile from a local static server of
         tools/web_public, 15 s each: console errors, page errors, failed requests, WebGL2, a non blank screenshot. Skipped when WebKit
         is not installed (PLAYWRIGHT_BROWSERS_PATH=<dir> python -m playwright install webkit).
    python -X utf8 -m tests.test_safari_smoke            (lint + smoke when WebKit is there)
    python -X utf8 -m tests.test_safari_smoke --lint     (lint only)
    python -X utf8 -m tests.test_safari_smoke arena jarvis   (smoke only these pages)   --wait 8   (seconds per page)   --deep (only the two intro films)
"""
from __future__ import annotations

import http.server
import io
import json
import os
import re
import sys
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "tools", "web_public")
RES: list = []
BUILT = ("kit.json",)   # written by the site build (tools/build_web_dashboard.py), not in the source tree


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:700]}"), flush=True)


# ------------------------------------------------------------------ the lint
SKIP_DIRS = ("three-addons", "node_modules", "icon_options", "/fx/src", "/fx/build")
SKIP_FILES = ("three.module.min.js", "build.mjs", "fx.js")   # fx.js: bundles of three.js (minified), not ours


def sources(exts):
    for root, _dirs, files in os.walk(WEB):
        rel = os.path.relpath(root, WEB).replace(os.sep, "/")
        if any(s.strip("/") in rel.split("/") or ("/" + rel + "/").find(s) >= 0 for s in SKIP_DIRS):
            continue
        for f in files:
            if f.endswith(exts) and f not in SKIP_FILES:
                p = os.path.join(root, f)
                with open(p, encoding="utf-8", errors="ignore") as fh:
                    yield os.path.relpath(p, WEB).replace(os.sep, "/"), fh.read()


def strip_comments(t):
    t = re.sub(r"/\*.*?\*/", "", t, flags=re.S)
    return re.sub(r"(?m)(^|[^:\"'\\])//.*$", r"\1", t)


# construct -> (regex, why). Only scripts (js / html inline) are scanned for the script ones; comments are ignored.
SCRIPT_BANNED = {
    "regex lookbehind (a SyntaxError that kills the whole script before iOS 16.4)": r"\(\?<[=!]",
    "Object.groupBy / Map.groupBy (iOS 17.4+)": r"\b(Object|Map)\.groupBy\(",
    "Array.prototype.toSorted / toReversed / toSpliced (iOS 16+, wrapped by nobody)": r"\.to(Sorted|Reversed|Spliced)\(",
    "Array.fromAsync / Promise.withResolvers / Array.prototype.with (iOS 17.4 / 18+)": r"\bArray\.fromAsync\(|\bPromise\.withResolvers\(",
    "AbortSignal.any (iOS 17.4+)": r"\bAbortSignal\.any\(",
    "Set methods union / intersection (iOS 17+)": r"\.(union|intersection|symmetricDifference|isSubsetOf)\(",
    "iterator helpers (iOS 18.4+)": r"\.values\(\)\.(map|filter|take|drop|toArray)\(",
    "navigator.gpu / SharedArrayBuffer (no value on iOS without COOP / COEP)": r"\bSharedArrayBuffer\b",
    "FloatType render target (iOS renders to half float only)": r"(WebGLRenderTarget|RenderTarget)\([^)]*(?<!Half)FloatType(?!\w)",
}
CSS_BANNED = {
    "CSS nesting with & (iOS 16.5+)": r"(?m)^\s*&\s*[.:#\[]",
    "@starting-style / field-sizing / animation-timeline (iOS 17.4+ / none)": r"@starting-style|field-sizing|animation-timeline",
    "@container size queries (iOS 16+) used without @supports": r"@container\s*\(",
}
# known, reviewed uses that are guarded or harmless (file -> reason); new ones fail the lint
ALLOW = {
    ("SCRIPT", "regex lookbehind"): [],
}


def lint():
    banned = []
    for rel, txt in sources((".js", ".html", ".mjs")):
        code = txt if rel.endswith(".html") else strip_comments(txt)
        if rel.endswith(".html"):
            code = "\n".join(re.findall(r"<script[^>]*>(.*?)</script>", txt, re.S))
            code = strip_comments(code)
        for name, rx in SCRIPT_BANNED.items():
            for m in re.finditer(rx, code):
                banned.append((name, rel, code[max(0, m.start() - 40):m.end() + 40].replace("\n", " ")))
    check("lint: no lookbehind, groupBy, toSorted, fromAsync, withResolvers, AbortSignal.any, Set algebra, iterator helpers, float render targets in any script", not banned, banned[:6])

    nobp = []
    for rel, txt in sources((".css", ".html", ".js")):
        for m in re.finditer(r"(?<![\w-])backdrop-filter\s*:([^;}\"']*)", txt):
            # the -webkit- twin must sit in the same declaration block (a few hundred chars around)
            ctx = txt[max(0, m.start() - 400):m.end() + 400]
            if "-webkit-backdrop-filter" not in ctx:
                nobp.append((rel, txt[m.start():m.end() + 30].replace("\n", " ")))
    check("lint: every backdrop-filter has its -webkit- twin beside it (iOS 16 / 17 only know the prefixed one)", not nobp, nobp[:6])

    nous = []
    for rel, txt in sources((".css", ".html", ".js")):
        for m in re.finditer(r"(?<![\w-])user-select\s*:\s*(none|all|text)", txt):
            if "-webkit-user-select" not in txt[max(0, m.start() - 120):m.end() + 120]:
                nous.append((rel, txt[m.start():m.end() + 10].replace("\n", " ")))
    check("lint: every user-select has its -webkit- twin beside it (iOS Safari still only knows the prefixed one)", not nous, nous[:6])

    bare = []
    for rel, txt in sources((".js", ".html")):
        code = strip_comments(txt)
        for m in re.finditer(r"new\s+AudioContext\(", code):
            before = code[max(0, m.start() - 160):m.start()]
            if "webkitAudioContext" not in before and "webkitAudioContext" not in code[m.start():m.end() + 80]:
                bare.append((rel, code[max(0, m.start() - 60):m.end() + 30].replace("\n", " ")))
    check("lint: every `new AudioContext(` has the webkitAudioContext fallback beside it", not bare, bare[:6])

    unguarded = []
    for rel, txt in sources((".js", ".html")):
        code = strip_comments(txt)
        for m in re.finditer(r"navigator\.(vibrate|getBattery)\(", code):
            before = code[max(0, m.start() - 120):m.start()]
            if not re.search(r"(typeof\s+navigator\.(vibrate|getBattery)|navigator\.(vibrate|getBattery)\s*(&&|\?|!==|===|\)|;)|'(vibrate|getBattery)'\s+in|try\s*\{)", before + code[max(0, m.start() - 40):m.start() + 1]) \
                    and "navigator.vibrate)" not in before and "navigator.getBattery)" not in before and "&&" not in before[-30:]:
                unguarded.append((rel, code[max(0, m.start() - 70):m.end() + 20].replace("\n", " ")))
    check("lint: navigator.vibrate / getBattery (absent on iOS) are only ever called behind a guard or a try", not unguarded, unguarded[:6])

    missing = []
    for app, names in (("jarvis", ("SHELL", "CORE")), ("kalshi", ("SHELL",))):
        sw = open(os.path.join(WEB, app, "sw.js"), encoding="utf-8").read()
        for nm in names:
            m = re.search(r"const %s = \[(.*?)\];" % nm, sw, re.S)
            if not m:
                missing.append(f"{app}: no {nm} list found")
                continue
            for f in re.findall(r"'([^']+)'", m.group(1)):
                p = os.path.normpath(os.path.join(WEB, app, f.split("?")[0]))
                if f not in ("./", "../") and not os.path.exists(p) and os.path.basename(p) not in BUILT:
                    missing.append(f"{app} {nm}: {f}")
    check("lint: every file in the Jarvis and Kalshi workers' SHELL / CORE lists exists (one 404 fails cache.addAll and the whole offline install)", not missing, missing)

    rr = open(os.path.join(WEB, "olympus", "render.js"), encoding="utf-8").read()
    check("lint: the render core targets half float (EXT_color_buffer_half_float) for bloom / PMREM and never requires EXT_color_buffer_float", "HalfFloatType" in rr
          and not re.search(r"getExtension\('EXT_color_buffer_float'\)\s*\)?\s*(throw|return false)", rr), "render.js")

    ls_bad = []
    for rel, txt in sources((".js", ".html")):
        code = strip_comments(txt)
        for m in re.finditer(r"(?<![\w.])(localStorage|sessionStorage)\.(getItem|setItem|removeItem)\(", code):
            line_start = code.rfind("\n", 0, m.start()) + 1
            ctx = code[max(0, line_start - 300):m.end() + 200]
            if not re.search(r"try\s*\{|catch\s*\(|catch\s*\{|=>\s*\{?\s*try|function\s+\w+\([^)]*\)\s*\{\s*try", ctx) and "try" not in code[max(0, m.start() - 120):m.start()]:
                ls_bad.append((rel, code[line_start:line_start + 110].strip()))
    check("lint: every localStorage / sessionStorage call sits in a try (it throws in a private window and with site data blocked)", not ls_bad, ls_bad[:8])


# ------------------------------------------------------------------ the WebKit smoke
class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def pages():
    out = ["index"]
    for d in sorted(os.listdir(WEB)):
        if os.path.isfile(os.path.join(WEB, d, "index.html")):
            out.append(d)
    return out


def nonblank(png):
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(png)).convert("L").resize((64, 128))
        px = list(im.tobytes())
        mean = sum(px) / len(px)
        var = sum((v - mean) ** 2 for v in px) / len(px)
        return var > 20 or mean > 40
    except Exception:
        return len(png) > 6000


def smoke(only, wait):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[SKIP] smoke: no Playwright")
        return
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), lambda *a: Handler(*a, directory=WEB))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    origin = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        with sync_playwright() as pw:
            try:
                br = pw.webkit.launch()
            except Exception as e:
                print(f"[SKIP] smoke: WebKit is not installed here ({str(e)[:90]}). PLAYWRIGHT_BROWSERS_PATH=<dir> python -m playwright install webkit")
                return
            dev = pw.devices["iPhone 13"]
            report = []
            for name in (only if "--deep" in sys.argv else (only or pages())):
                ctx = br.new_context(**dev)
                ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith(origin) else r.abort())
                p = ctx.new_page()
                errs, fails, bad = [], [], []
                p.on("pageerror", lambda e, errs=errs: errs.append(str(e)[:240]))
                p.on("console", lambda m, errs=errs: errs.append("console: " + m.text[:240]) if m.type == "error" and "Failed to load resource" not in m.text else None)
                p.on("requestfailed", lambda r, fails=fails: fails.append(r.url.replace(origin, "")[:100]) if r.url.startswith(origin) else None)
                p.on("response", lambda r, bad=bad: bad.append(f"{r.status} {r.url.replace(origin, '')[:100]}") if r.url.startswith(origin) and r.status >= 400 else None)
                url = origin + ("/" if name == "index" else f"/{name}/")
                try:
                    p.goto(url, wait_until="commit", timeout=60000)
                    p.wait_for_timeout(int(wait * 1000))
                    gl = p.evaluate("(() => { try { const c = document.createElement('canvas'); const g = c.getContext('webgl2'); return g ? 2 : (c.getContext('webgl') ? 1 : 0); } catch (e) { return -1; } })()")
                    shot = p.screenshot(timeout=60000)
                    over = p.evaluate("document.documentElement.scrollWidth - innerWidth")
                    row = dict(page=name, errors=errs[:5], failed=fails[:5], http=bad[:5], webgl=gl, nonblank=nonblank(shot), overflow=over)
                except Exception as e:
                    row = dict(page=name, errors=[f"harness: {str(e)[:200]}"], failed=[], http=[], webgl=-1, nonblank=False, overflow=0)
                report.append(row)
                ctx.close()
                hard = [x for x in row["http"] if not re.search(r"\.json|/icons/", x)]   # the data files and icons are published by the site build: a bare static tree has none of them
                row["data_404"] = len(row["http"]) - len(hard)
                ok = not row["errors"] and not hard and row["nonblank"]
                check(f"smoke (WebKit, iPhone 13): {name}: no console / page error, no failed request, a non blank screen, WebGL2 {'yes' if row['webgl'] == 2 else 'no (' + str(row['webgl']) + ')'}", ok, row)
            # the two film shaders in WebKit (GLSL differs from SwiftShader / ANGLE): the Jarvis intro at its forge moment and an app intro
            if not only or "--deep" in sys.argv:
                for label, path, init, probe in (
                        ("jarvis intro film (WebGL1 shaders, held at 6.9 s)", "/jarvis/", "try { localStorage.setItem('jarvis.intro.force', 'full'); localStorage.setItem('jarvis.intro.hold', '6.9'); localStorage.setItem('jarvis.intro.scale', '0.6'); } catch (e) {}",
                         "(() => { const s = window.__olyIntro || {}; return s.state === 'playing' && s.frames > 2 && !s.err; })()"),
                        ("app intro (oracle ?intro=1)", "/oracle/?intro=1&demo=1", "", "(() => { const s = window.__olyAppIntro || {}; return ['playing', 'done'].includes(s.state) && s.frames > 1 && !s.err; })()")):
                    ctx = br.new_context(**dev)
                    ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith(origin) else r.abort())
                    if init:
                        ctx.add_init_script(init)
                    p = ctx.new_page()
                    errs: list = []
                    p.on("pageerror", lambda e, errs=errs: errs.append(str(e)[:200]))
                    try:
                        p.goto(origin + path, wait_until="commit", timeout=60000)
                        ok = False
                        for _ in range(40):
                            p.wait_for_timeout(1000)
                            if p.evaluate(probe):
                                ok = True
                                break
                        check(f"smoke (WebKit, iPhone 13): {label}", ok and not errs, (errs[:3], p.evaluate("JSON.stringify(window.__olyIntro || window.__olyAppIntro || null)")))
                    except Exception as e:
                        check(f"smoke (WebKit, iPhone 13): {label}", False, e)
                    ctx.close()
            br.close()
            if os.environ.get("SAFARI_REPORT"):
                with open(os.environ["SAFARI_REPORT"], "w", encoding="utf-8") as fh:
                    json.dump(report, fh, indent=1)
    finally:
        srv.shutdown()


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--") and not a.isdigit()]
    wait = float(sys.argv[sys.argv.index("--wait") + 1]) if "--wait" in sys.argv else 15
    if "--smoke" not in sys.argv:
        lint()
    if "--lint" not in sys.argv:
        smoke(args, wait)


if __name__ == "__main__":
    t0 = time.time()
    main()
    n = sum(RES)
    print(f"\n{n}/{len(RES)} passed in {time.time() - t0:.0f}s")
    sys.exit(0 if n == len(RES) else 1)
