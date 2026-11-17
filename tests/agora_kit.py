"""Shared helper of the AGORA app suites (test_hestia_page, test_demeter_page, test_apollo_page, test_hera_page, test_dionysus_page, test_clio_page), 2026-11-09.

    from tests import agora_kit as AK
    AK.static_kit("hestia", "Hestia")            # the files, the kit lines, the AGORA lines, no markup from data, no network, the card, the manifest
    out = AK.node("hestia", HARNESS, extra_args)   # run an ES-module harness in node against <app>core.js; returns its JSON
    srv, origin = AK.serve(overrides={"/home.json": b"..."})     # the site folder (tools/web_public) with a few files replaced / added
    with AK.browser() as br: ctx, p, errs, seen, off = AK.page(br, origin); AK.open_app(p, origin, "hestia", "?demo=1")
    AK.taps(p) / AK.corner(p) / AK.no_sideways(p) / AK.finish()
Every suite is read only: it serves the site folder from a local port, aborts every request off that origin and never writes anything outside a temp folder.
"""
from __future__ import annotations

import contextlib
import functools
import glob
import http.server
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "tools", "web_public")
INCLUDE = '<script src="../olympus/intro-app.js?v=i5" defer></script>'
RES: list = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:700]}"), flush=True)


def finish():
    bad = RES.count(False)
    print(f"\n{len(RES) - bad}/{len(RES)} passed", flush=True)
    sys.exit(1 if bad else 0)


def read(p):
    with open(p, encoding="utf-8") as fh:
        return fh.read()


def jarvis_problems(card):
    p = []
    raw = json.dumps(card)
    if len(raw.encode()) > 8192:
        p.append("over 8 KB")
    if card.get("v") != 1 or not isinstance(card.get("name"), str) or len(card["name"]) > 40:
        p.append("v / name")
    st = card.get("status") or {}
    if st.get("level") not in ("ok", "warn", "bad", "off") or len(st.get("label", "")) > 48:
        p.append("status")
    for k in card.get("kpis", []):
        if len(str(k["label"])) > 20 or len(str(k["value"])) > 24 or len(str(k.get("delta", ""))) > 16:
            p.append(f"kpi {k}")
    if len(card.get("kpis", [])) > 3 or len(card.get("lines", [])) > 3 or any(len(x) > 120 for x in card.get("lines", [])):
        p.append("kpis / lines")
    if any(ch in raw for ch in "<>") or "&amp;" in raw or "\\n" in raw:
        p.append("markup")
    if not isinstance(card.get("t"), int) or not str(card.get("theme", "")).startswith("#") or len(card.get("theme", "")) != 7:
        p.append("t / theme")
    return p


BANNED_LOOK = re.compile(r"Orbitron|Rajdhani|text-shadow\s*:\s*0\s+0|#00ffff|#0ff\b|neon|scanline|cyber|hologra|quantum", re.I)


def static_kit(app, name, reads=(), storage=None, allow_urls=()):
    """The checks every AGORA app shares. reads = the published files its JS may fetch (besides ./fixture.json)."""
    d = os.path.join(WEB, app)
    names = ["index.html", f"{app}.css", f"{app}.js", f"{app}core.js", "fixture.json", "icon.svg", "manifest.webmanifest", "jarvis.json"]
    check(f"a. the files: {', '.join(names)}", all(os.path.isfile(os.path.join(d, n)) for n in names), [n for n in names if not os.path.isfile(os.path.join(d, n))])
    html, js, core, css = (read(os.path.join(d, n)) for n in ("index.html", f"{app}.js", f"{app}core.js", f"{app}.css"))
    lines = html.splitlines()
    i = next((n for n, ln in enumerate(lines) if "../olympus/olympus.js?v=o7" in ln), -1)
    check(f'a. the kit: olympus.css?v=o7, agora.css after it, themes.js, olympus.js?v=o7 data-app="{app}", the intro tag on the very next line',
          html.index("../olympus/olympus.css?v=o7") < html.index("../olympus/agora.css") < html.index(f"{app}.css") and "../olympus/themes.js?v=o6" in html
          and f'data-app="{app}"' in lines[i] and lines[i + 1].strip() == INCLUDE and html.count("intro-app.js") == 1, lines[i:i + 2])
    check("a. AGORA: <html data-theme=\"agora\">, the a11y layer and the sound kit, the page is an ES module",
          re.search(r'<html lang="en" data-theme="agora"( data-oly-light)?>', html) and "../olympus/a11y.js" in html and "../olympus/sfx.js?v=s4" in html and f'<script type="module" src="{app}.js' in html)
    check(f"a. viewport-fit=cover, theme-color, manifest, icon, apple-touch-icon, lang, ONE h1 named {name}, a polite live status line",
          all(x in html for x in ("viewport-fit=cover", 'name="theme-color"', 'rel="manifest"', 'rel="icon"', "apple-touch-icon", '<html lang="en"')) and html.count("<h1") == 1
          and f">{name}</h1>" in html and 'role="status"' in html and 'aria-live="polite"' in html)
    bad = [p for p in (r"\.innerHTML", r"outerHTML", r"insertAdjacentHTML", r"document\.write", r"\beval\s*\(", r"new Function", r"\bimport\s*\(") if re.search(p, js) or re.search(p, core)]
    check("a. no markup is ever built from data: no innerHTML / outerHTML / insertAdjacentHTML / document.write / eval / dynamic import", not bad, bad)
    fetches = set(re.findall(r"getJSON\('([^']+)'", js))
    want = {"./fixture.json", *reads, *allow_urls}
    web_js = js + core
    for u in allow_urls:
        web_js = web_js.replace(u, "")
    check("a. it reads only published JSON of this site and its fixture, and sends nothing: no XHR / WebSocket / sendBeacon / POST / cookies / web address",
          fetches == want and not re.search(r"XMLHttpRequest|WebSocket|sendBeacon|method:\s*['\"]POST|document\.cookie|https?://(?!www\.w3\.org)", web_js), (sorted(fetches), sorted(want)))
    check(f"a. {app}core.js is pure (no document / window / fetch / localStorage), Safari 16 safe (no lookbehind, no .at())",
          not re.search(r"\bdocument\.|\bwindow\.|\bfetch\(|\blocalStorage\b|\(\?<[=!]|\.at\(", re.sub(r"//[^\n]*", "", core)))
    check("a. text only through textContent / createElementNS / a value", "textContent" in js and (("createElementNS" in js) or "<svg" not in read(os.path.join(d, "index.html")) and "sv(" not in js))
    check("a. every tap target is at least 44 px in the CSS, safe areas, 176 px clear of Jarvis's corner, reduced motion, LITE",
          css.count("min-height: 44px") >= 3 and "safe-area-inset" in css and "176px" in css and "prefers-reduced-motion" in css and 'data-oly-lite="1"' in css)
    check("a. the AGORA look: no neon / glow / techno font / cyber words in the app's own files", not BANNED_LOOK.search(css + html.split("</head>")[0].split("-->")[-1]) and not BANNED_LOOK.search(js), BANNED_LOOK.findall(css + js)[:3])
    card = json.loads(read(os.path.join(d, "jarvis.json")))
    check("a. jarvis.json follows the card contract (<= 8 KB, v 1, name, status, <= 3 kpis, <= 3 lines of 120, no markup, t, theme)", not jarvis_problems(card), jarvis_problems(card))
    man = json.loads(read(os.path.join(d, "manifest.webmanifest")))
    check(f"a. the manifest: name {name}, standalone, portrait, ./ scope, an svg icon", man["name"] == name and man["display"] == "standalone" and man["orientation"] == "portrait" and man["scope"] == "./" and man["icons"][0]["src"] == "icon.svg")
    svg = read(os.path.join(d, "icon.svg"))
    check("a. icon.svg is a Greek-flavoured mark on the AGORA palette (no neon colours)", svg.lstrip().startswith("<svg") and "viewBox" in svg and not re.search(r"#(?:0ff|00f|f0f|0f0)\b|#00ffff|#ff00ff", svg, re.I))
    fx = json.loads(read(os.path.join(d, "fixture.json")))
    check("a. the fixture is labelled demo (demo: true, 'not real' in its note) so it can never pass for the owner's numbers", fx.get("demo") is True and "not real" in str(fx.get("note", "")).lower(), fx.get("note"))
    if storage is None:
        check("a. no browser storage of its own", not re.search(r"localStorage\.setItem|sessionStorage|indexedDB", js + core))


# ------------------------------------------------------------------------------------------------ node
def node(app, harness, *args):
    """Run `harness` (ES module source; reads process.argv[2] = a temp copy of <app>core.mjs, then the extra args) and return its stdout parsed as JSON."""
    exe = shutil.which("node")
    if not exe:
        return None
    tmp = tempfile.mkdtemp(prefix=f"ag-{app}-")
    try:
        core = os.path.join(tmp, f"{app}core.mjs")
        shutil.copy(os.path.join(WEB, app, f"{app}core.js"), core)
        h = os.path.join(tmp, "harness.cjs")
        with open(h, "w", encoding="utf-8") as fh:
            fh.write(harness)
        r = subprocess.run([exe, h, core, *map(str, args)], capture_output=True, text=True, timeout=120)
        if r.returncode:
            print(r.stderr[-1500:])
            return {"_error": r.stderr[-600:]}
        return json.loads(r.stdout)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ------------------------------------------------------------------------------------------------ the local site
class Handler(http.server.SimpleHTTPRequestHandler):
    overrides: dict = {}

    def log_message(self, *a):
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in self.overrides:
            body = self.overrides[path]
            if body is None:
                self.send_error(404)
                return
            body = body if isinstance(body, bytes) else body.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json" if path.endswith(".json") else "text/plain; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()


def serve(overrides=None):
    """The site folder on a local port. overrides = {"/home.json": bytes | str | None (404)} replace or add files."""
    handler = type("H", (Handler,), {"overrides": dict(overrides or {})})
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(handler, directory=WEB))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


@contextlib.contextmanager
def browser():
    from playwright.sync_api import sync_playwright
    try:
        sys.path.insert(0, os.path.join(ROOT, "tests"))
        import browser_kit as BK
    except Exception:
        BK = None
    with sync_playwright() as pw:
        if BK:
            br = BK.launch(pw)
        else:
            exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
            br = pw.chromium.launch(args=["--no-sandbox", "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"], **({"executable_path": exe} if exe else {}))
        yield br


def status_feed_prefix():
    """The one sanctioned outside address: the public PC status topic of status_feed.json (pc_feed.js polls it; docs/PRIVACY.md:
    'The status topic is public on purpose'). Returns '<ntfy>/<topic>/' or '' when the file is missing or odd."""
    try:
        with open(os.path.join(WEB, "status_feed.json"), encoding="utf-8") as f:
            feed = json.load(f)
        base, topic = str(feed.get("ntfy") or "").rstrip("/"), str(feed.get("topic") or "")
    except (OSError, ValueError, AttributeError):
        return ""
    return f"{base}/{topic}/" if base.startswith("https://") and re.fullmatch(r"[A-Za-z0-9_-]{16,}", topic) else ""


def is_status_feed(u):
    pre = status_feed_prefix()
    return bool(pre) and u.startswith(pre)


def page(br, origin, w=390, h=844, reduced=False, lite=False, storage=None, mock=None):
    ctx = br.new_context(viewport={"width": w, "height": h}, device_scale_factor=2, is_mobile=True, has_touch=True, reduced_motion="reduce" if reduced else "no-preference", accept_downloads=True)
    init = "try { localStorage.setItem('jfx', '%s'); } catch (e) {}" % ("low" if lite else "high")
    for k, v in (storage or {}).items():
        init += " try { localStorage.setItem(%s, %s); } catch (e) {}" % (json.dumps(k), json.dumps(v))
    ctx.add_init_script(init)
    seen, off, mocked, feed = [], [], [], []

    def route(r):
        u = r.request.url
        for frag, body in (mock or {}).items():
            if frag in u:
                mocked.append(u)
                r.fulfill(status=200, content_type="application/json", headers={"Access-Control-Allow-Origin": "*"}, body=body)
                return
        if not u.startswith(origin):
            if is_status_feed(u):
                feed.append(u)          # the sanctioned public PC status feed (docs/PRIVACY.md), still aborted: never reached
            else:
                off.append(u)
            r.abort()
        else:
            seen.append(u)
            r.continue_()
    ctx.route("**/*", route)
    p = ctx.new_page()
    errs = []
    p.on("pageerror", lambda e: errs.append(str(e)))
    p.on("console", lambda m: errs.append(m.text) if m.type == "error" and "Failed to load resource" not in m.text and "net::ERR" not in m.text else None)
    p.mocked = mocked
    p.feed = feed
    return ctx, p, errs, seen, off


def open_app(p, origin, app, q="", hook=None):
    p.goto(f"{origin}/{app}/{q}")
    hook = hook or app.upper()
    p.wait_for_function(f"window.{hook} && window.{hook}.ready()", timeout=120000, polling=300)
    p.wait_for_timeout(700)
    p.evaluate("document.getAnimations().forEach((a) => { try { a.finish(); } catch (e) {} })")


TAPS = """() => { const bad = [];
  for (const e of document.querySelectorAll('button, input:not([type=file]), select, textarea, summary, a[href], [role=tab], [role=button]')) {
    const cs = getComputedStyle(e); if (cs.display === 'none' || cs.visibility === 'hidden') continue; const r = e.getBoundingClientRect();
    if (r.width && r.height && (r.height < 43.5 || r.width < 43.5)) bad.push((e.id || e.className || e.tagName) + ' ' + Math.round(r.width) + 'x' + Math.round(r.height)); }
  return bad; }"""
SIDEWAYS = "() => document.documentElement.scrollWidth <= innerWidth + 1"
CORNER = """() => { const W = innerWidth, H = innerHeight, bad = []; window.scrollTo(0, document.documentElement.scrollHeight);
  for (const e of document.querySelectorAll('button, input, select, textarea, summary, a[href]')) { if (/oly-/.test(e.className + ' ' + e.id)) continue; const r = e.getBoundingClientRect(); if (!r.width) continue;
    if (r.right > W - 80 && r.bottom > H - 160 && r.left < W && r.top < H) bad.push(e.id || e.className || e.tagName); }
  return bad; }"""


def taps(p):
    return p.evaluate(TAPS)


def corner(p):
    return p.evaluate(CORNER)


def no_sideways(p):
    return p.evaluate(SIDEWAYS)


def shot(p, name):
    """A screenshot for the owner's eyes, only when AGORA_SHOTS=<dir> is set."""
    d = os.environ.get("AGORA_SHOTS")
    if d:
        os.makedirs(d, exist_ok=True)
        p.screenshot(path=os.path.join(d, name + ".png"), full_page=True)
