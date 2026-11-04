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

    lint_more()


# ------------------------------------------------------------------ the iPhone sweep rules (job 2026-11-04: layout, input zoom, missing APIs, syntax)
def css_rules(txt):
    """[(selector, body, offset)] for every flat rule of a stylesheet / <style> (good enough for these lints; @media bodies are walked too)"""
    for m in re.finditer(r"([^{}@][^{}]*)\{([^{}]*)\}", txt):
        yield m.group(1).strip(), m.group(2), m.start()


def lint_more():
    # 1. 100vh is the tallest the screen can be (toolbars hidden): a height / min-height / top-bottom made of it hides the bottom of the
    #    page behind iOS's toolbar unless a dvh / svh / fill-available twin follows in the same rule (or the JS-set --oly-vh var)
    vh = []
    for rel, txt in sources((".css", ".html")):
        for sel, body, off in css_rules(txt):
            for m in re.finditer(r"(?<![\w-])(min-height|max-height|height|top|bottom)\s*:\s*([^;}]*\b100vh[^;}]*)", body):
                if re.search(r"\b100(d|s|l)vh\b|-webkit-fill-available|--oly-vh|-vh\b", body) or "env(safe-area" in m.group(2):
                    continue
                vh.append((rel, sel[-50:], m.group(0)[:70]))
    check("lint: every height made of 100vh has a 100dvh / 100svh twin in the same rule (iOS toolbars make 100vh taller than the screen)", not vh, vh[:8])

    # 2. a focused form control under 16px makes iOS zoom the page in and leave it zoomed
    small = []
    for rel, txt in sources((".css", ".html")):
        for sel, body, off in css_rules(txt):
            if not re.search(r"(^|[\s,>+~])(input|select|textarea)\b", sel) or re.search(r"checkbox|radio|range|button|submit|color|file|::placeholder|\[type=.?(hidden|image)", sel):
                continue
            fs = [(m2.group(1) or m2.group(3), m2.group(2) or "px") for m2 in re.finditer(r"(?<![\w-])font-size\s*:\s*([\d.]+)(px|rem|em)|(?<![\w-])font\s*:[^;]*?\b([\d.]+)px\b", body)]
            last = fs[-1] if fs else None                 # the last declaration wins
            if last and float(last[0]) * (16 if last[1] in ("rem", "em") else 1) < 16:
                small.append((rel, sel[-60:], last[0] + last[1]))
    check("lint: no input / select / textarea is styled under 16px (iOS zooms the page on focus)", not small, small[:8])

    # 3. Notification does not exist in an iPhone browser tab (only in the Home Screen app): a bare use is a ReferenceError
    nb = []
    for rel, txt in sources((".js", ".html")):
        code = strip_comments(txt)
        for m in re.finditer(r"(?<![\w.'\"])Notification\.(permission|requestPermission)", code):
            before = code[:m.start()]                     # a guard earlier in the same file (the calls sit in functions that run after it)
            if not re.search(r"'Notification'\s+in\s+(window|self|globalThis)|typeof\s+Notification|pushSupport\s*=|notifySupport|window\.Notification", before):
                nb.append((rel, code[max(0, m.start() - 60):m.end() + 20].replace("\n", " ")))
    check("lint: Notification.* is only used after a 'Notification' in window / typeof / pushSupport() guard (absent in an iPhone browser tab)", not nb, nb[:6])

    # 4. requestIdleCallback does not exist in Safari (before 18-ish, behind a flag): call it only with a fallback
    ric = []
    for rel, txt in sources((".js", ".html")):
        code = strip_comments(txt)
        for m in re.finditer(r"(?<![\w.])requestIdleCallback\s*\(", code):
            before = code[max(0, m.start() - 120):m.start()]
            if not re.search(r"(window\.)?requestIdleCallback\s*(\?|&&|\|\||\)\s*\?|\))|typeof\s+requestIdleCallback|'requestIdleCallback'\s+in", before + "requestIdleCallback"):
                ric.append((rel, code[max(0, m.start() - 70):m.end() + 20].replace("\n", " ")))
    check("lint: requestIdleCallback is only called behind a feature test (Safari has none) with a setTimeout fallback", not ric, ric[:6])

    # 5. APIs with no (or a late, partial) iOS implementation that nothing here should need
    oc = []
    for rel, txt in sources((".js", ".html")):
        code = strip_comments(txt)
        for m in re.finditer(r"\b(OffscreenCanvas|transferControlToOffscreen|audioWorklet|AudioWorkletNode|navigator\.gpu|requestPictureInPicture|webkitEnterFullscreen|showOpenFilePicker|showSaveFilePicker|BarcodeDetector|FileSystemHandle|navigator\.usb|navigator\.bluetooth|screen\.orientation\.lock)\b", code):
            before = code[max(0, m.start() - 100):m.start()]
            if not re.search(r"typeof\s+$|'\w+'\s+in\s+\w+\s*&&\s*$|\?\s*$|&&\s*$|if\s*\(\s*$", before):
                oc.append((rel, code[max(0, m.start() - 40):m.end() + 30].replace("\n", " ")))
    check("lint: no OffscreenCanvas / AudioWorklet / WebGPU / file-system / USB / Bluetooth / orientation lock without a feature test", not oc, oc[:6])

    # 6. a touch listener that calls preventDefault must say passive: false (iOS treats window / document / body touch listeners as passive)
    tp = []
    for rel, txt in sources((".js", ".html")):
        code = strip_comments(txt)
        for m in re.finditer(r"addEventListener\(\s*['\"](touchstart|touchmove|wheel)['\"]", code):
            seg = code[m.start():m.start() + 900]
            end = re.search(r"\},\s*\{[^}]*\}\s*\)|\}\s*\)\s*;", seg)
            body = seg[:end.end()] if end else seg[:400]
            if "preventDefault" in body and not re.search(r"passive\s*:\s*false", body):
                tp.append((rel, code[m.start():m.start() + 90].replace("\n", " ")))
    check("lint: a touchstart / touchmove / wheel listener that calls preventDefault says { passive: false } (else Safari ignores it)", not tp, tp[:6])

    # 7. WebGL2 context used straight off getContext (null on a phone without it)
    gl = []
    for rel, txt in sources((".js", ".html")):
        code = strip_comments(txt)
        for m in re.finditer(r"getContext\(\s*['\"]webgl2['\"][^)]*\)\s*\.\s*\w", code):
            gl.append((rel, code[max(0, m.start() - 30):m.end() + 20].replace("\n", " ")))
    check("lint: getContext('webgl2') is never dereferenced straight away (it is null without WebGL2: test it, fall back)", not gl, gl[:6])

    # 8. audio / video: autoplay needs muted + playsinline (iOS), and every .play() handles the rejection a missing gesture gives
    ap = []
    for rel, txt in sources((".html", ".js")):
        for m in re.finditer(r"<(video|audio)\b[^>]*\bautoplay\b[^>]*>", txt):
            tag = m.group(0)
            if "muted" not in tag or (m.group(1) == "video" and "playsinline" not in tag):
                ap.append((rel, tag[:90]))
        code = strip_comments(txt)
        for m in re.finditer(r"(?<![\w$])(\w+(?:\.\w+)*)\.play\(\)", code):
            if re.search(r"(speechSynthesis|player|game|anim|timeline|tl|gsap|clip|action|mixer|scrub|loop|ticker|sim|demo|film)", m.group(1), re.I) and not re.search(r"audio|video|\bel\b|\ba\b|snd|sound|media|voice|tone", m.group(1), re.I):
                continue
            after = code[m.end():m.end() + 160]
            before = code[max(0, m.start() - 60):m.start()]
            if not re.search(r"^\s*\.catch|^\s*\.then|;\s*if\s*\(\w+[^)]*\)\s*\w+\.catch|\w+\.catch", after) and not re.search(r"(const|let|var)\s+\w+\s*=\s*$|try\s*\{[^}]*$|await\s+$|return\s+$", before) \
                    and not re.search(r"try\s*\{", code[max(0, m.start() - 200):m.start()]):
                ap.append((rel, code[max(0, m.start() - 40):m.end() + 30].replace("\n", " ")))
    check("lint: autoplay media is muted + playsinline, and every media .play() handles its rejection (no user gesture = NotAllowedError)", not ap, ap[:6])

    # 9. every page: a viewport meta with device-width, viewport-fit=cover wherever the page (or its stylesheets) uses env(safe-area-inset-*)
    vp = []
    for root, _d, files in os.walk(WEB):
        rel_root = os.path.relpath(root, WEB).replace(os.sep, "/")
        if any(x in rel_root for x in ("icon_options", "three-addons", "node_modules", "/fx", "fx/")) or rel_root == "fx":
            continue
        for f in files:
            if not f.endswith(".html"):
                continue
            p = os.path.join(root, f)
            t = open(p, encoding="utf-8", errors="ignore").read()
            if "<html" not in t.lower():
                continue
            m = re.search(r"<meta[^>]*name=[\"']viewport[\"'][^>]*>", t)
            rel = os.path.relpath(p, WEB).replace(os.sep, "/")
            if not m:
                vp.append((rel, "no viewport meta"))
                continue
            css = t
            for l in re.findall(r"<link[^>]*href=[\"']([^\"'?#]+\.css)", t):
                q = os.path.normpath(os.path.join(root, l))
                if os.path.exists(q):
                    css += open(q, encoding="utf-8", errors="ignore").read()
            if "device-width" not in m.group(0):
                vp.append((rel, "no width=device-width"))
            if "safe-area-inset" in css and "viewport-fit=cover" not in m.group(0):
                vp.append((rel, "uses safe-area-inset without viewport-fit=cover (the insets would be 0)"))
    check("lint: every page has width=device-width and viewport-fit=cover where it uses the safe-area insets", not vp, vp[:6])

    # 10. syntax: every script parses as ES2021 (iOS 15+: optional chaining, ??, ||=, private fields; a module may use top-level await,
    #     a classic script may not). Needs node + acorn (the repo's node-tools); skipped, said so, when they are not there.
    syntax_gate()


ACORN_JS = r"""
const acorn = require(process.argv[2]); const fs = require('fs'), path = require('path');
const files = JSON.parse(fs.readFileSync(process.argv[3], 'utf8')); const out = [];
for (const f of files) {
  try { acorn.parse(f.code, { ecmaVersion: 2021, sourceType: f.module ? 'module' : 'script', allowAwaitOutsideFunction: !!f.module }); }
  catch (e) { out.push([f.name, e.message]); }
}
console.log(JSON.stringify(out));
"""


def syntax_gate():
    import shutil
    import subprocess
    import tempfile
    node = shutil.which("node")
    acorn = next((c for c in (os.environ.get("ACORN_PATH", ""), "/opt/node-tools/node_modules/acorn", os.path.join(ROOT, "node_modules", "acorn")) if c and os.path.isdir(c)), "")
    if not node or not acorn:
        check("lint: script syntax gate (ES2021, top-level await only in modules) skipped: node or acorn not found (set ACORN_PATH)", True)
        return
    classic = set()                                  # files a classic <script src> loads: no top-level await there
    inline = []
    for rel, txt in sources((".html",)):
        for m in re.finditer(r"<script([^>]*)>(.*?)</script>", txt, re.S):
            attrs, body = m.group(1), m.group(2)
            mod = bool(re.search(r"type=[\"']?module", attrs))
            sm = re.search(r"src=[\"']([^\"'?#]+)", attrs)
            if sm and not mod and not sm.group(1).startswith(("http", "//")):
                classic.add(os.path.normpath(os.path.join(os.path.dirname(rel), sm.group(1))).replace(os.sep, "/"))
            elif not sm and body.strip() and not re.search(r"type=[\"']?(application|text/(plain|template))", attrs):
                inline.append({"name": rel + "#inline" + (" (module)" if mod else " (classic)"), "code": body, "module": mod})
    files = list(inline)
    for rel, txt in sources((".js", ".mjs")):
        if rel.startswith("fx/") or rel.endswith("build.mjs"):
            continue
        files.append({"name": rel, "code": txt, "module": rel not in classic})
    d = tempfile.mkdtemp(prefix="saf_")
    try:
        with open(os.path.join(d, "r.js"), "w", encoding="utf-8") as fh:
            fh.write(ACORN_JS)
        with open(os.path.join(d, "f.json"), "w", encoding="utf-8") as fh:
            json.dump(files, fh)
        r = subprocess.run([node, os.path.join(d, "r.js"), acorn, os.path.join(d, "f.json")], capture_output=True, text=True, timeout=240)
        bad = json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 and r.stdout.strip() else [("acorn", r.stderr[-300:])]
    finally:
        import shutil as _sh
        _sh.rmtree(d, ignore_errors=True)
    check(f"lint: all {len(files)} scripts parse as ES2021 (iOS 15+ syntax; no top-level await in a classic script)", not bad, bad[:6])


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
