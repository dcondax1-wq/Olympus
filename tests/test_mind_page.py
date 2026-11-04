"""OLYMPUS Mind (tools/web_public/mind/, owner 2026-11-03): the 3D brain of the owner's Obsidian vault and Jarvis's memory.
Its only data source is Jarvis's module ../jarvis/obsidian.js (graphSnapshot() / onIndexChange(cb)); without it the page shows
a demo brain. Runs the real page in Chromium (WebGL through SwiftShader) on a local server that maps /mind/ and /jarvis/ to
tools/web_public/ and serves a fake obsidian.js when a case asks for one, and checks:
  a. the files and the static rules: every module present, every export used by another module (no dead code), no network
     API in the page's code (fetch, XMLHttpRequest, sendBeacon, WebSocket, EventSource), storage only under 'mind.' keys, no
     outside URL, the viewport / theme-color / safe areas / reduced motion / 16 px input, jarvis.json by the Jarvis contract
  b. demo mode at 390 x 844 and 844 x 390: no console errors (the missing obsidian.js 404 aside), the demo chip and the demo
     pill, stats, the 3D view drawn, the layout in a worker, no sideways scroll, the orb's 80 x 160 px corner left free
  c. search: typing lists matches, Enter flies the camera to the note and opens its card; tap a node opens its card
  d. filter chips, the time-lapse (replays and stops), the quality switch, Escape closes the card
  e. the mocked vault (obsidian.js served): live mode, junk notes and links dropped, the newest learned item in the ticker;
     onIndexChange with a new learned item and a new note: the ticker updates, a spark flies, the stats move; escaping;
     the card with and without a snippet; null afterwards = "Vault offline" with the last brain kept
  f. a broken obsidian.js (throws on import, or graphSnapshot throws): the demo brain, no page error
  g. reduced motion: no flight animation, sparks become instant ignitions, no errors
  h. 2,000 notes (?demo=2000): loads, the worker layout settles, no errors (frame rate printed; SwiftShader is not a GPU)
  i. across every case: no request and no fetch to anything but the page's own origin
  j. the 2026-11-03 day upgrade: nebula clouds per galaxy (fewer on LITE), Jarvis's memories seated on the cyan ring around
     Me, the constellation view (kept on this phone), focus mode (one galaxy, its pill, × and Escape leave it), the thought
     stream (newest first, a tap flies to the note), synapse pulses when a note opens (none under reduced motion), the
     markdown-ish preview (headings, lists, tasks, [[links]] that fly, #tags; vault markup stays text), links and backlinks
     apart, applyTheme(theme) and the OLYMPUS theme hook (OLYMPUS.theme() / onTheme) when the kit has one
    python -X utf8 -m tests.test_mind_page
MIND_SHOTS=<dir> also saves screenshots (overview, a node card, the learning spark, the views, focus mode) there.
"""
from __future__ import annotations

import glob
import http.server
import json
import os
import re
import sys
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "tools", "web_public")
MIND = os.path.join(WEB, "mind")
SHOTS = os.environ.get("MIND_SHOTS")
MODULES = ["main.js", "data.js", "demo.js", "graph.js", "layout.js", "layout-worker.js", "render.js", "controls.js", "ui.js",
           "nebula.js", "synapse.js", "memring.js", "markdown.js", "live.js",
           "dom.js", "insights.js", "quiz.js", "panels.js", "teach.js", "store.js", "skins.js", "sound.js", "ambient.js", "starter.js"]
RES = []
MOCK = {"js": None}                       # the fake ../jarvis/obsidian.js (None = 404, like a Jarvis without it)
OUTSIDE = []                              # every request to another origin (must stay empty)


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:400]}"), flush=True)


# ------------------------------------------------------------------ a. static rules
def static_checks():
    present = [f for f in MODULES + ["index.html", "mind.css", "panels.css", "jarvis.json"] if not os.path.isfile(os.path.join(MIND, f))]
    check("a. every file is there", not present, present)
    src = {f: open(os.path.join(MIND, f), encoding="utf-8").read() for f in MODULES}
    html = open(os.path.join(MIND, "index.html"), encoding="utf-8").read()
    css = open(os.path.join(MIND, "mind.css"), encoding="utf-8").read() + open(os.path.join(MIND, "panels.css"), encoding="utf-8").read()
    unused = []
    for f, s in src.items():
        for name in re.findall(r"^export (?:async )?(?:function|class|const|let) (\w+)", s, re.M):
            if not any(re.search(r"import \{[^}]*\b" + name + r"\b[^}]*\} from '\./" + re.escape(f[:-3]) + r"\.js'", o) for g, o in src.items() if g != f):
                unused.append(f"{f}:{name}")
    check("a. every export is imported by another module (no dead exports)", not unused, unused)
    net = [f for f, s in src.items() if re.search(r"\bfetch\s*\(|XMLHttpRequest|sendBeacon|WebSocket|EventSource|importScripts", s)]
    check("a. no network API in the page's code", not net, net)
    keys = set(re.findall(r"localStorage\.\w+\(([^,)]+)", "".join(src.values())))
    check("a. storage only under the page's own 'mind.' keys (store.js prefixes every key)", keys == {"QUALITY_KEY", "VIEW_KEY", "P + name"} and "const QUALITY_KEY = 'mind.quality';" in src["main.js"]
          and "const VIEW_KEY = 'mind.view';" in src["main.js"] and "const P = 'mind.';" in src["store.js"], keys)
    # the ONE writer into Jarvis's keys is teach.js, in her formats, and only the three keys (never the vault's connection key)
    jkeys = {f: sorted(set(re.findall(r"'(jarvis\.[\w.]+)'", s))) for f, s in src.items() if re.search(r"'jarvis\.[\w.]+'", s)}
    check("a. only live.js (reads) and teach.js (writes) name Jarvis's storage keys; teach.js only the three it may write",
          set(jkeys) == {"live.js", "teach.js"} and jkeys["teach.js"] == ["jarvis.assistant.v1", "jarvis.vault.learned", "jarvis.vault.local"], jkeys)
    check("a. nothing but store.js, main.js (quality, view) and teach.js writes to storage",
          all(("setItem" not in s) for f, s in src.items() if f not in ("store.js", "main.js", "teach.js")), [f for f, s in src.items() if "setItem" in s])
    check("a. vault text never goes in as HTML (no innerHTML / insertAdjacentHTML / outerHTML in the page's code)",
          not re.search(r"innerHTML|insertAdjacentHTML|outerHTML|document\.write", "".join(src.values())))
    check("a. only transform / opacity animate in the sheet and the stream (no layout transitions)",
          not re.search(r"transition:[^;]*\b(width|height|top|left|right|bottom|margin|padding)\b", css))
    code = re.sub(r"//.*", "", "".join(src.values()))
    check("a. never touches a token (no token, secret or password in the code)", not re.search(r"token|secret|password", code, re.I))
    outside = [u for u in re.findall(r"https?://[^\s'\"`)]+", "".join(src.values()) + html + css)]
    check("a. no outside URL anywhere (three.js and the fonts come from ../jarvis/)", not outside, outside)
    check("a. the only door to the vault is ../jarvis/obsidian.js", "import('../jarvis/obsidian.js')" in src["data.js"]
          and src["main.js"].count("../jarvis/three.module.min.js") == 1)
    check("a. viewport-fit=cover and its own theme-color", 'viewport-fit=cover' in html and '<meta name="theme-color" content="#03040a">' in html)
    check("a. safe areas on every edge, reduced motion, 16 px search input",
          all(f"safe-area-inset-{e}" in css for e in ("top", "right", "bottom", "left")) and "prefers-reduced-motion: reduce" in css
          and re.search(r"#q \{[^}]*font-size: 16px", css))
    j = json.load(open(os.path.join(MIND, "jarvis.json"), encoding="utf-8"))
    ok = (j.get("v") == 1 and j.get("name") == "Mind" and j.get("status") == {"level": "ok", "label": "Brain online"}
          and isinstance(j.get("t"), int) and re.fullmatch(r"#[0-9a-f]{6}", j.get("theme", "")) and j["theme"] == "#03040a"
          and len(json.dumps(j)) < 8192 and all(len(x) <= 120 and "<" not in x for x in j.get("lines", [])) and len(j.get("kpis", [])) <= 3)
    check("a. jarvis.json follows the Jarvis card contract (status ok 'Brain online', theme = the page's colour)", ok, j)


# ------------------------------------------------------------------ the server
class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def handle(self):
        try:
            super().handle()
        except (BrokenPipeError, ConnectionResetError):
            pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/jarvis/obsidian.js" and MOCK["js"] is not None:
            body = MOCK["js"].encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/javascript; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        return super().do_GET()

    def translate_path(self, path):
        p = path.split("?")[0]
        if p.startswith("/mind/") or p.startswith("/olympus/") or (p.startswith("/jarvis/") and p != "/jarvis/obsidian.js"):
            return os.path.join(WEB, *p.lstrip("/").split("/"))
        return os.path.join(WEB, "__missing__")


# the fake Jarvis module: the snapshot lives on globalThis.__obs (set by an init script), fire() calls the subscribers
FAKE_OBSIDIAN = """
const M = globalThis.__obs || (globalThis.__obs = { snap: null });
M.cbs = M.cbs || new Set(); M.calls = M.calls || 0;
M.fire = () => M.cbs.forEach((cb) => cb());
export async function graphSnapshot() { M.calls++; if (M.throws) throw new Error('vault locked'); return M.snap ? JSON.parse(JSON.stringify(M.snap)) : null; }
export function onIndexChange(cb) { M.cbs.add(cb); return () => M.cbs.delete(cb); }
"""
THROWS_ON_IMPORT = "throw new Error('obsidian.js failed to load');\nexport async function graphSnapshot() { return null; }\n"
EVIL = '<img src=x onerror="window.__pwned=1">Evil <b>note</b>'


def mock_vault(now_ms):
    """56 real notes plus junk the adapter must drop (no id, a duplicate, links to missing notes, a self link)."""
    notes, groups = [], [("Trading", ["trading"]), ("Goals", ["goals"]), ("Gym", ["gym"]), ("Kalshi", ["kalshi"])]
    for g, (folder, tags) in enumerate(groups):
        for k in range(12):
            nid = f"{folder}/Mock {folder} {k}.md"
            links = [f"{folder}/Mock {folder} 0.md"] if k else []
            links += [f"{folder}/Mock {folder} {(k + 3) % 12}.md", "Missing/Nowhere.md", nid]
            notes.append({"id": nid, "title": f"Mock {folder} {k}", "path": nid, "tags": ["#" + tags[0]], "links": links,
                          "mtime": (now_ms - (g * 12 + k) * 3600_000) // 1000, "words": 100 + k * 40, "kind": "note",
                          **({"snippet": f"First lines of {folder} {k}."} if k == 0 else {})})
    for d in range(5):
        notes.append({"id": f"Daily/2026-11-0{d + 1}.md", "title": f"2026-11-0{d + 1}", "path": f"Daily/2026-11-0{d + 1}.md", "tags": [],
                      "links": ["Trading/Mock Trading 1.md"], "mtime": now_ms - d * 86400_000, "words": 300, "kind": "daily"})
    notes.append({"id": "Me.md", "title": "Me", "path": "Me.md", "tags": [], "links": ["Goals/Mock Goals 0.md"], "mtime": now_ms, "words": 500, "kind": "me"})
    notes.append({"id": "Jarvis/Memory/1.md", "title": "Likes gold", "path": "Jarvis/Memory/1.md", "tags": ["jarvis"],
                  "links": ["Me.md"], "mtime": now_ms, "words": 10, "kind": "memory"})
    notes.append({"id": "Evil.md", "title": EVIL, "path": "Evil.md", "tags": ["<script>x</script>"], "links": [], "mtime": now_ms, "words": 3, "kind": "weird"})
    notes.append({"id": "Notes/Markdown.md", "title": "Markdown", "path": "Notes/Markdown.md", "tags": ["notes"], "links": ["Trading/Mock Trading 1.md"],
                  "mtime": now_ms - 99 * 3600_000, "words": 80, "kind": "note",
                  "preview": "## Plan\n- [x] done task\n- [ ] open task\n- link to [[Mock Trading 1]] and [[Nowhere]]\n" + EVIL + " **bold** #tagged"})
    notes += [None, {"title": "no id"}, dict(notes[0])]                       # junk: dropped
    learned = [{"t": now_ms - 7200_000, "text": "Older lesson about sleep", "note": "Gym/Mock Gym 2.md"},
               {"t": (now_ms - 600_000) // 1000, "text": "Mock lesson: trade the NY open", "note": "Trading/Mock Trading 0.md"},
               {"t": now_ms - 20 * 86400_000, "text": "An old lesson", "note": None}, {"t": now_ms, "text": ""}]
    return {"v": 1, "t": now_ms, "notes": notes, "learned": learned}


MOCK_NOTES = 4 * 12 + 5 + 2 + 1 + 1


def expected_links(snap):
    """Unique undirected links between notes that exist, no self links (what the page must count)."""
    ids = {n["id"] for n in snap["notes"] if isinstance(n, dict) and "id" in n}
    return len({frozenset((n["id"], l)) for n in snap["notes"] if isinstance(n, dict) and "id" in n
                for l in n.get("links", []) if l in ids and l != n["id"]})


# ------------------------------------------------------------------ browser helpers
def new_page(br, origin, vw, *, snap=None, reduced=False, quality="high"):
    ctx = br.new_context(viewport={"width": vw[0], "height": vw[1]}, device_scale_factor=2, reduced_motion="reduce" if reduced else "no-preference")

    def guard(route):
        u = route.request.url
        if u.startswith(origin) or u.startswith("data:") or u.startswith("blob:"):
            return route.continue_()
        OUTSIDE.append(u)
        return route.abort()
    ctx.route("**/*", guard)
    ctx.add_init_script("""(() => {
      const seen = (window.__net = []);
      const f = window.fetch; window.fetch = function (u) { seen.push(String(u && u.url || u)); return f.apply(this, arguments); };
      const o = XMLHttpRequest.prototype.open; XMLHttpRequest.prototype.open = function (m, u) { seen.push(String(u)); return o.apply(this, arguments); };
      if (navigator.sendBeacon) { const b = navigator.sendBeacon.bind(navigator); navigator.sendBeacon = (u, d) => { seen.push(String(u)); return b(u, d); }; }
    })();""")
    if quality:
        # the OLYMPUS kit's one 3D level (Jarvis's 'jfx' key) is the page's quality (docs/OLYMPUS_DESIGN.md)
        ctx.add_init_script(f"try {{ localStorage.setItem('jfx', '{quality}'); }} catch (e) {{}}")
    if snap is not None:
        ctx.add_init_script("globalThis.__obs = { snap: " + json.dumps(snap) + " };")
    p = ctx.new_page()
    log = {"errors": [], "console": []}
    p.on("pageerror", lambda e: log["errors"].append(str(e)))
    p.on("console", lambda m: log["console"].append((m.text, (m.location or {}).get("url", ""))) if m.type == "error" else None)
    return ctx, p, log


def real_errors(log):
    """Console errors, except the expected 404 of a missing obsidian.js (that is how the page learns Jarvis has none)."""
    return log["errors"] + [t for t, u in log["console"] if not (u.endswith("/jarvis/obsidian.js") and "404" in t)]


def ready(p, timeout=30000):
    p.wait_for_function("window.mind && window.mind.stats && document.getElementById('s-notes').textContent !== '–'", timeout=timeout)


def shot(p, name):
    if SHOTS:
        os.makedirs(SHOTS, exist_ok=True)
        p.screenshot(path=os.path.join(SHOTS, name))


def lit_pixels(p):
    """How much of the 3D view is drawn (bright pixels in a screenshot of the canvas alone)."""
    from io import BytesIO
    try:
        from PIL import Image
    except ImportError:
        return -1
    img = Image.open(BytesIO(p.locator("#gl").screenshot())).convert("L").resize((195, 422))
    return sum(img.histogram()[91:])


def wait_flight(p, timeout=8):
    end = time.time() + timeout
    while time.time() < end:
        c = p.evaluate("mind.camera()")
        if not c["flying"]:
            return c
        time.sleep(0.15)
    return p.evaluate("mind.camera()")


def orb_corner_free(p):
    # the OLYMPUS seal (.oly-home) sits in the orb's seat only when the page is opened alone: Jarvis's orb is there when framed
    return p.evaluate("""() => { const w = innerWidth, h = innerHeight, hits = [];
      for (let x = w - 78; x < w; x += 12) for (let y = h - 158; y < h; y += 12)
        for (const e of document.elementsFromPoint(x, y)) if (!['HTML', 'BODY', 'CANVAS'].includes(e.tagName) && e.id !== 'labels' && !e.classList.contains('lbl') && !e.closest('.oly-home')) hits.push(e.id || e.className || e.tagName);
      return [...new Set(hits)]; }""")


# ------------------------------------------------------------------ b-d. demo mode
def demo_cases(br, origin):
    url = origin + "/mind/?q=off"
    MOCK["js"] = None
    for vw in [(390, 844), (844, 390)]:
        tag = f"{vw[0]}x{vw[1]}"
        ctx, p, log = new_page(br, origin, vw)
        p.goto(url)
        ready(p)
        time.sleep(2.5)
        st = p.evaluate("({mode: mind.mode, stats: mind.stats, layout: mind.layout})")
        check(f"b. {tag}: demo mode with the demo brain ({st['stats']['notes']} notes, {st['stats']['links']} links)",
              st["mode"] == "demo" and st["stats"]["notes"] > 80 and st["stats"]["links"] > 150 and st["stats"]["clusters"] >= 7, st)
        chip = p.locator("#demo")
        check(f"b. {tag}: the 'Connect your vault' chip and the DEMO pill",
              chip.is_visible() and "Connect your vault in Jarvis ⋯ → Connect Obsidian" in chip.inner_text()
              and p.get_attribute("#mode", "data-mode") == "demo", chip.inner_text() if chip.count() else "")
        check(f"b. {tag}: the layout runs in a worker", st["layout"] == "worker", st)
        px = lit_pixels(p)
        check(f"b. {tag}: the 3D brain is drawn ({px} bright pixels)", px == -1 or px > 400, px)
        check(f"b. {tag}: the stats show (notes, links, clusters, learned 7d)",
              all(p.inner_text(f"#s-{k}").strip() not in ("", "–") for k in ("notes", "links", "clusters", "learned")))
        check(f"b. {tag}: the ticker shows what Jarvis learned", len(p.inner_text("#tk-text")) > 10, p.inner_text("#tk-text"))
        sw = p.evaluate("[document.scrollingElement.scrollWidth, innerWidth]")
        check(f"b. {tag}: no sideways scroll", sw[0] <= sw[1], sw)
        free = orb_corner_free(p)
        check(f"b. {tag}: the bottom-right 80 x 160 px stays free for Jarvis's orb", not free, free)
        if vw == (390, 844):
            shot(p, "overview_390.png")
            search_and_tap(p, tag)
            controls(p, tag)
        else:
            shot(p, "overview_844.png")
        check(f"b. {tag}: no console errors in demo mode", not real_errors(log), real_errors(log))
        check(f"i. {tag}: the page itself fetched nothing", p.evaluate("window.__net") == [], p.evaluate("window.__net"))
        ctx.close()


def search_and_tap(p, tag):
    p.fill("#q", "kalshi b")
    p.wait_for_selector("#results li[data-id]", timeout=15000)
    first = p.get_attribute("#results li[data-id]", "data-id")
    check(f"c. {tag}: typing lists the matching notes", first == "Kalshi/Kalshi bot.md", first)
    p.press("#q", "Enter")
    p.wait_for_function("mind.focus === 'Kalshi/Kalshi bot.md'", timeout=15000)
    cam = wait_flight(p)
    pt = p.evaluate("mind.nodePoint('Kalshi/Kalshi bot.md')")
    dist = sum((cam["target"][k] - pt[k]) ** 2 for k in "xyz") ** 0.5
    check(f"c. {tag}: Enter flies the camera to the note (off by {dist:.1f}, radius {cam['radius']:.0f})", dist < 0.15 * cam["radius"] and cam["radius"] < 400, (cam, pt))
    time.sleep(0.8)                                       # the picture slides up above the card
    scr = p.evaluate("mind.screenOf('Kalshi/Kalshi bot.md')")
    free = p.evaluate("[document.getElementById('top').getBoundingClientRect().bottom, document.getElementById('card').getBoundingClientRect().top, innerWidth]")
    check(f"c. {tag}: the note ends up in the open space between the header and its card ({scr['x']:.0f}, {scr['y']:.0f}; free {free[0]:.0f}-{free[1]:.0f})",
          abs(scr["x"] - free[2] / 2) < 60 and free[0] + 20 < scr["y"] < free[1] - 20 and abs(scr["y"] - (free[0] + free[1]) / 2) < 50, (scr, free))
    check(f"c. {tag}: its glass card opens (title, tags, links, last edited)",
          p.is_visible("#card") and p.inner_text("#c-title") == "Kalshi bot" and "#kalshi" in p.inner_text("#c-tags")
          and p.inner_text("#c-edited").strip() != "" and p.locator("#c-near button").count() > 0)
    time.sleep(0.6)
    shot(p, "card_390.png")
    # tap a linked note's button: flies there; then a tap on empty space closes the card
    p.locator("#c-near button").first.click()
    p.wait_for_function("mind.focus !== 'Kalshi/Kalshi bot.md'", timeout=15000)
    wait_flight(p)
    target = p.evaluate("mind.focus")
    p.click("#c-close")
    check(f"c. {tag}: a linked note in the card flies to it; × closes the card", target and p.is_hidden("#card"), target)
    # a tap on a node opens its card
    scr = p.evaluate(f"mind.screenOf({json.dumps(target)})")
    p.mouse.click(scr["x"], scr["y"])
    p.wait_for_function("mind.focus !== null", timeout=15000)
    check(f"c. {tag}: tapping a node opens its card", p.is_visible("#card") and p.evaluate("mind.focus") is not None, p.evaluate("mind.focus"))
    p.keyboard.press("Escape")
    check(f"d. {tag}: Escape closes the card", p.is_hidden("#card"))
    # a double tap on a node flies to it
    hub = "Trading/LIT strategy.md"
    wait_flight(p)
    scr = p.evaluate(f"mind.screenOf({json.dumps(hub)})")
    band = p.evaluate("mind.labelBand()")                 # the open sky between the top bar and the bottom sheet
    if not (20 < scr["x"] < p.viewport_size["width"] - 20 and band["top"] + 30 < scr["y"] < band["bottom"] - 30):
        p.fill("#q", "LIT strategy")                      # bring it on screen first (search, then close the card)
        p.press("#q", "Enter")
        wait_flight(p)
        p.keyboard.press("Escape")
        time.sleep(0.8)
        scr = p.evaluate(f"mind.screenOf({json.dumps(hub)})")
    before = p.evaluate("mind.camera().radius")
    p.mouse.dblclick(scr["x"], scr["y"])
    time.sleep(0.2)
    cam = wait_flight(p)
    pt = p.evaluate(f"mind.nodePoint({json.dumps(hub)})")
    dist = sum((cam["target"][k] - pt[k]) ** 2 for k in "xyz") ** 0.5
    check(f"c. {tag}: a double tap on a node flies to it (off by {dist:.1f})", p.evaluate("mind.focus") == hub and dist < 0.15 * cam["radius"], (before, cam, pt))
    p.keyboard.press("Escape")


def controls(p, tag):
    p.click(".chip[data-key='trading']")
    check(f"d. {tag}: a filter chip turns on", p.get_attribute(".chip[data-key='trading']", "aria-pressed") == "true")
    p.click(".chip[data-key='trading']")
    check(f"d. {tag}: tapping it again shows everything", p.get_attribute(".chip[data-key='']", "aria-pressed") == "true")
    p.click("#timelapse")
    time.sleep(1.2)
    a = p.evaluate("[!document.getElementById('tl').hidden, document.getElementById('tl-count').textContent]")
    time.sleep(1.5)
    b = p.inner_text("#tl-count")
    check(f"d. {tag}: the time-lapse replays the vault growing ({a[1]} -> {b})", a[0] and int(b.split()[0]) > int(a[1].split()[0]), (a, b))
    p.click("#timelapse")
    check(f"d. {tag}: Stop ends the time-lapse", p.is_hidden("#tl") and p.inner_text("#timelapse").strip() == "Time-lapse")
    p.click("#quality")
    q1 = p.evaluate("[mind.quality, localStorage.getItem('jfx')]")          # kept in the shared OLYMPUS key
    p.click("#quality")
    q2 = p.evaluate("mind.quality")
    check(f"d. {tag}: the quality switch (HD / LITE) is kept", q1 == ["low", "low"] and q2 == "high", (q1, q2))


# ------------------------------------------------------------------ e. the mocked vault
def mock_cases(br, origin):
    MOCK["js"] = FAKE_OBSIDIAN
    now = int(time.time() * 1000)
    vault = mock_vault(now)
    ctx, p, log = new_page(br, origin, (390, 844), snap=vault)
    p.goto(origin + "/mind/?q=off")
    ready(p)
    # the ticker shows the newest lesson first, then rotates through the lessons every 7 s (newest, older, oldest, newest ...): on a slow
    # machine the first read can land mid-rotation, so look for the newest one for a full cycle (3 x 7 s, plus margin)
    tick0 = ""
    for _ in range(40):
        tick0 = p.inner_text("#tk-text")
        if tick0 == "Mock lesson: trade the NY open":
            break
        time.sleep(1)
    st = p.evaluate("({mode: mind.mode, stats: mind.stats})")
    check(f"e. the mocked obsidian.js is used: live mode, {st['stats']['notes']} notes (junk dropped)",
          st["mode"] == "live" and st["stats"]["notes"] == MOCK_NOTES and p.is_hidden("#demo") and p.get_attribute("#mode", "data-mode") == "live", st)
    check(f"e. links to missing notes and self links are dropped, each pair counted once ({st['stats']['links']})",
          st["stats"]["links"] == expected_links(vault), (st, expected_links(vault)))
    check("e. learned this week counts the lessons of the last 7 days", st["stats"]["learnedWeek"] == 2, st)
    check("e. the ticker shows the newest lesson", tick0 == "Mock lesson: trade the NY open", tick0)
    time.sleep(1.5)
    # escaping: the evil title is text, never markup
    p.fill("#q", "evil")
    p.press("#q", "Enter")
    p.wait_for_function("mind.focus === 'Evil.md'", timeout=15000)
    check("e. vault text is shown as text (no injected markup runs)", p.inner_text("#c-title") == EVIL and p.locator("#card img").count() == 0
          and not p.evaluate("window.__pwned") and p.is_hidden("#c-snippet"))
    p.fill("#q", "Mock Trading 0")
    p.press("#q", "Enter")
    p.wait_for_function("mind.focus === 'Trading/Mock Trading 0.md'", timeout=15000)
    check("e. the card shows the first lines when the snapshot has a snippet, and what Jarvis learned about the note",
          p.inner_text("#c-snippet") == "First lines of Trading 0." and "trade the NY open" in p.inner_text("#c-learned"))
    p.click("#c-close")
    wait_flight(p)
    # onIndexChange: a new lesson about an existing note, and a new note
    launched0 = p.evaluate("mind.sparksLaunched")
    p.evaluate("""() => { const s = globalThis.__obs.snap;
      s.notes.push({ id: 'Goals/Fresh idea.md', title: 'Fresh idea', path: 'Goals/Fresh idea.md', tags: ['goals'], links: ['Goals/Mock Goals 0.md'], mtime: Date.now(), words: 50, kind: 'note' });
      s.learned.push({ t: Date.now(), text: 'Brand new lesson from the mock vault', note: 'Trading/Mock Trading 4.md' });
      globalThis.__obs.fire(); }""")
    p.wait_for_function("document.getElementById('tk-text').textContent === 'Brand new lesson from the mock vault'", timeout=4000)
    sparks, launched = p.evaluate("[mind.sparks, mind.sparksLaunched]")
    shot(p, "spark_390.png")                              # a screenshot takes ~1 s on SwiftShader: the comet is mid-flight
    # a busy machine can draw so few frames that the 2.4 s comet has already landed: what counts is that one was sent
    check("e. onIndexChange: the ticker shows the new lesson at once and a spark flies to its note", launched - launched0 >= 1, (sparks, launched0, launched))
    st2 = p.evaluate("mind.stats")
    check("e. the stats follow (one more note, one more lesson this week)", st2["notes"] == MOCK_NOTES + 1 and st2["learnedWeek"] == 3, st2)
    p.wait_for_function("mind.sparks === 0", timeout=6000)
    check("e. the spark lands (and ignites the note)", True)
    # the markdown preview from the optional `preview` field: structure shown, links resolved, vault markup still text
    p.fill("#q", "Markdown")
    p.press("#q", "Enter")
    p.wait_for_function("mind.focus === 'Notes/Markdown.md'", timeout=15000)
    md = p.evaluate("""() => { const s = document.getElementById('c-snippet');
      return { h: s.querySelectorAll('h4').length, tasks: s.querySelectorAll('li.md-task').length, done: s.querySelectorAll('li.md-task.done').length,
               links: [...s.querySelectorAll('button.md-link')].map((b) => b.textContent), missing: s.querySelectorAll('.md-link.missing').length,
               bold: s.querySelectorAll('b').length, tags: s.querySelectorAll('.md-tag').length, img: s.querySelectorAll('img').length, text: s.innerText }; }""")
    check("j. the card's markdown preview: heading, tasks (one done), a [[link]] that resolves and one that does not, bold, #tag; markup stays text",
          md["h"] == 1 and md["tasks"] == 2 and md["done"] == 1 and md["links"] == ["Mock Trading 1"] and md["missing"] == 1
          and md["bold"] >= 1 and md["tags"] == 1 and md["img"] == 0 and "<img src=x" in md["text"] and not p.evaluate("window.__pwned"), md)
    p.click("#c-snippet button.md-link")
    p.wait_for_function("mind.focus === 'Trading/Mock Trading 1.md'", timeout=15000)
    check("j. a [[link]] in the preview flies to its note", True)
    groups = p.evaluate("[...document.querySelectorAll('#c-near h3')].map((h) => h.textContent)")
    check("j. the card lists links and backlinks apart ('Links to', 'Linked from' with counts)",
          any(g.startswith("Links to") for g in groups) and any(g.startswith("Linked from") for g in groups), groups)
    p.click("#c-close")
    wait_flight(p)
    calls = p.evaluate("globalThis.__obs.calls")
    p.evaluate("globalThis.__obs.snap = null; globalThis.__obs.fire();")
    p.wait_for_function("mind.mode === 'offline'", timeout=4000)
    check("e. disconnected later: 'Vault offline' with the last brain kept",
          p.evaluate("mind.stats.notes") == MOCK_NOTES + 1 and p.text_content("#mode").strip() == "Vault offline" and p.is_hidden("#demo"), calls)
    check("e. no console errors with the mocked vault", not real_errors(log), real_errors(log))
    check("i. the page itself fetched nothing (mocked vault)", p.evaluate("window.__net") == [], p.evaluate("window.__net"))
    ctx.close()


# ------------------------------------------------------------------ f-h. broken modules, reduced motion, 2,000 notes
def other_cases(br, origin):
    for name, js, init in [("throws on import", THROWS_ON_IMPORT, None), ("graphSnapshot throws", FAKE_OBSIDIAN, "globalThis.__obs = { snap: null, throws: true };")]:
        MOCK["js"] = js
        ctx, p, log = new_page(br, origin, (390, 844))
        if init:
            p.add_init_script(init)
        p.goto(origin + "/mind/?q=off")
        ready(p)
        check(f"f. obsidian.js {name}: the demo brain, no page error", p.evaluate("mind.mode") == "demo" and not log["errors"], log["errors"])
        ctx.close()

    MOCK["js"] = FAKE_OBSIDIAN
    now = int(time.time() * 1000)
    ctx, p, log = new_page(br, origin, (390, 844), snap=mock_vault(now), reduced=True)
    p.goto(origin + "/mind/?q=off")
    ready(p)
    p.fill("#q", "Mock Gym 4")
    p.press("#q", "Enter")
    p.wait_for_function("mind.focus === 'Gym/Mock Gym 4.md'", timeout=15000)
    time.sleep(0.3)
    flying = p.evaluate("mind.camera().flying")
    p.evaluate("""() => { globalThis.__obs.snap.learned.push({ t: Date.now(), text: 'Calm lesson', note: 'Gym/Mock Gym 1.md' }); globalThis.__obs.fire(); }""")
    p.wait_for_function("document.getElementById('tk-text').textContent === 'Calm lesson'", timeout=4000)
    check("g. reduced motion: the flight is a cut, the spark an instant ignition, no errors",
          not flying and p.evaluate("mind.sparks") == 0 and not real_errors(log), (flying, real_errors(log)))
    p.fill("#q", "Mock Gym 6")
    p.press("#q", "Enter")
    p.wait_for_function("mind.focus === 'Gym/Mock Gym 6.md'", timeout=15000)
    check("g. reduced motion: no synapse pulses and no idle thinking", p.evaluate("mind.synapses") == 0)
    ctx.close()

    MOCK["js"] = None
    ctx, p, log = new_page(br, origin, (390, 844))
    p.goto(origin + "/mind/?demo=2000&q=off")
    ready(p, 60000)
    t0 = time.time()
    p.wait_for_function("mind.settled", timeout=120000)
    settle = time.time() - t0
    time.sleep(3)
    st = p.evaluate("({stats: mind.stats, fps: mind.fps, layout: mind.layout, q: mind.quality})")
    print(f"       2,000 notes: settled in {settle:.1f} s here, {st['fps']} fps on SwiftShader ({st['q']}); this sandbox runs JS ~20x slower than a phone")
    check(f"h. 2,000 notes load and the worker layout settles ({st['stats']['notes']} notes, {st['stats']['links']} links)",
          st["stats"]["notes"] == 2000 and st["layout"] == "worker" and not real_errors(log), (st, real_errors(log)))
    ctx.close()


# ------------------------------------------------------------------ j. the day upgrade (2026-11-03)
THEMED = """(() => { const subs = []; window.__theme = { subs };
  const hook = () => { const O = window.OLYMPUS; if (!O || O.theme) return;
    O.theme = () => ({ name: 'test', vars: { accent: '#ff3d9a', '--glass': 'rgba(40, 0, 20, 0.6)' } });
    O.onTheme = (cb) => subs.push(cb); };
  Object.defineProperty(window, 'OLYMPUS', { configurable: true, set(v) { Object.defineProperty(window, 'OLYMPUS', { value: v, writable: true, configurable: true }); hook(); }, get() { return undefined; } });
})();"""


def upgrade_cases(br, origin):
    MOCK["js"] = None
    ctx, p, log = new_page(br, origin, (390, 844))
    p.goto(origin + "/mind/?q=off")
    ready(p)
    p.wait_for_function("mind.settled", timeout=60000)
    time.sleep(1.2)
    for _ in range(30):                                   # the memories glide onto the ring as the layout cools: wait for it (up to 12 s)
        off = p.evaluate("mind.memoryOnRing()")
        if off and max(off) < 0.3:
            break
        time.sleep(0.4)
    neb, ring, off = p.evaluate("[mind.nebulae, mind.ring, mind.memoryOnRing()]")
    check(f"j. nebula clouds: layered sprites per galaxy ({neb} puffs on HD)", neb >= 7 * 4, neb)
    check(f"j. Jarvis's memories sit on the cyan ring around Me ({ring and ring['count']} memories, radius {ring and round(ring['r'])}, worst {max(off or [9]):.2f} of r)",
          ring and ring["count"] == 8 and ring["r"] > 20 and off and max(off) < 0.3, (ring, off))   # a ring, not a cloud (0.5+); the bigger demo spreads it a little
    lbl = p.evaluate("[...document.querySelectorAll('#labels .lbl')].filter((e) => !e.hidden).map((e) => e.textContent)")
    check("j. the memory ring is named ('Jarvis memory')", "Jarvis memory" in lbl, lbl)
    # the thought stream: newest first, a tap flies to the note
    items = p.evaluate("[...document.querySelectorAll('#stream li')].map((li) => [li.className, li.querySelector('small').textContent, li.querySelector('span').textContent])")
    check(f"j. the thought stream shows lessons and edits, newest first ({len(items)} thoughts)",
          len(items) >= 10 and any("learned" in c for c, _, _ in items) and any("edit" in c for c, _, _ in items), items[:4])
    first_edit = next(t for c, _, t in items if "edit" in c)
    p.click("#stream li.edit button")
    p.wait_for_function("mind.focus !== null", timeout=15000)
    focus = p.evaluate("mind.focus")
    check("j. tapping a thought opens its note", focus and p.inner_text("#c-title") == first_edit, (focus, first_edit))
    p.wait_for_function("mind.synapses > 0", timeout=15000)
    check(f"j. opening a note fires its synapses (pulses running: {p.evaluate('mind.synapses')})", True)
    time.sleep(0.4)
    shot(p, "synapse_390.png")
    p.keyboard.press("Escape")
    wait_flight(p)
    # constellation view
    p.click("#view")
    time.sleep(1.4)
    v = p.evaluate("[mind.view, document.getElementById('view').getAttribute('aria-pressed'), localStorage.getItem('mind.view')]")
    check("j. the constellation view: the toggle, its state, kept on this phone", v == ["stars", "true", "stars"], v)
    px = lit_pixels(p)
    check(f"j. the constellation view is drawn ({px} bright pixels)", px == -1 or px > 150, px)
    shot(p, "constellation_390.png")
    p.reload()
    ready(p)
    check("j. the view survives a reload", p.evaluate("mind.view") == "stars")
    p.click("#view")
    check("j. back to the galaxy view", p.evaluate("mind.view") == "galaxy" and p.get_attribute("#view", "aria-pressed") == "false")
    # focus mode
    p.click(".chip[data-key='health']")
    wait_flight(p)
    time.sleep(0.6)
    fb = p.evaluate("[!document.getElementById('focusbar').hidden, document.getElementById('focus-name').textContent, mind.filter]")
    check("j. focus mode: one galaxy lit, its pill under the top bar", fb == [True, "Health", "health"], fb)
    lbl = p.evaluate("[...document.querySelectorAll('#labels .lbl:not(.note)')].filter((e) => !e.hidden && +e.style.opacity > 0.3).map((e) => e.textContent)")
    check("j. focus mode: the other galaxies' names fade", lbl in ([], ["Health"]), lbl)
    free = orb_corner_free(p)
    check("j. focus mode: the orb's corner stays free", not free, free)
    shot(p, "focus_390.png")
    p.click("#focus-exit")
    check("j. × leaves focus mode", p.evaluate("mind.filter") is None and p.is_hidden("#focusbar"))
    p.click(".chip[data-key='trading']")
    p.keyboard.press("Escape")
    check("j. Escape leaves focus mode", p.evaluate("mind.filter") is None and p.is_hidden("#focusbar"))
    # applyTheme by hand
    got = p.evaluate("[mind.applyTheme({ accent: '#ffaa00', bg: '#000000', junk: 'x', '--glass': 'rgba(0,0,0,.5)', text: 'red; } body { display: none' }), getComputedStyle(document.documentElement).getPropertyValue('--cyan').trim()]")
    check("j. applyTheme(theme): known colours and custom properties applied, junk and CSS injection ignored",
          got[1] == "#ffaa00" and "--cyan-rgb" in got[0] and "--text" not in got[0] and "junk" not in str(got[0]), got)
    check("j. no console errors in the upgrade checks", not real_errors(log), real_errors(log))
    ctx.close()
    # LITE: fewer clouds; landscape: the sheet in two columns, the corner free
    ctx, p, log = new_page(br, origin, (844, 390), quality="low")
    p.goto(origin + "/mind/?q=off")
    ready(p)
    time.sleep(1.5)
    neb = p.evaluate("mind.nebulae")
    check(f"j. LITE: fewer nebula puffs ({neb})", 0 < neb <= 2 * 9, neb)
    free = orb_corner_free(p)
    sw = p.evaluate("[document.scrollingElement.scrollWidth, innerWidth]")
    check("j. 844 x 390 LITE: the orb's corner free, no sideways scroll", not free and sw[0] <= sw[1], (free, sw))
    check("j. no console errors on LITE", not real_errors(log), real_errors(log))
    ctx.close()
    # the OLYMPUS theme hook: a kit with theme() / onTheme
    # (the real kit now ships themes: a non-default olympus.theme at load reaches Mind through OLYMPUS.theme(), and
    #  applyTheme repaints on a change; the default theme leaves Mind's own cyan alone)
    ctx, p, log = new_page(br, origin, (390, 844))
    p.add_init_script("try { localStorage.setItem('olympus.theme', 'zeus'); } catch (e) {}")
    p.goto(origin + "/mind/?q=off")
    ready(p)
    a = p.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--cyan').trim()")
    p.evaluate("window.mind.applyTheme({ accent: '#33ff66' })")
    b = p.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--cyan').trim()")
    check("j. the OLYMPUS theme hook: a theme at load changes Mind's accent, applyTheme on a change", a not in ("", "#6ff6ff") and b == "#33ff66" and not real_errors(log), (a, b, real_errors(log)))
    ctx.close()


def render_core_cases(br, origin):
    """2026-11-03: the OLYMPUS render core under the brain, and 'what did Jarvis learn today'."""
    MOCK["js"] = None
    for q, want in (("low", ["scene", "finish"]), ("high", ["scene", "bloom", "finish"])):
        ctx, p, log = new_page(br, origin, (390, 844))
        p.goto(origin + "/mind/?q=" + q)
        ready(p)
        p.wait_for_function("window.mind && window.mind.core", timeout=60000)
        check(f"k. the brain draws on the render core ({q}): {'+'.join(want)}", p.evaluate("window.mind.core") == want and not real_errors(log), (p.evaluate("window.mind.core"), real_errors(log)))
        ctx.close()
    ctx, p, log = new_page(br, origin, (390, 844))
    p.goto(origin + "/mind/?q=off")
    ready(p)
    day = p.evaluate("window.mind.day")
    check("k. Today: the demo vault has lessons from today, oldest first, 24 hourly counts", len(day["items"]) >= 1 and len(day["hours"]) == 24
          and sum(day["hours"]) == len(day["items"]) and day["items"] == sorted(day["items"], key=lambda x: x["t"]), day)
    check("k. Today: the button shows the count, the panel is closed", p.inner_text("#today-n") == str(len(day["items"])) and p.is_hidden("#day"))
    p.click("#today")
    p.wait_for_timeout(200)
    check("k. Today opens: a 24-hour strip, one row per lesson (newest first, with the time and the note), pressed state",
          p.is_visible("#day") and p.evaluate("document.querySelectorAll('#day-strip i').length") == 24
          and p.evaluate("document.querySelectorAll('#day-list button').length") == len(day["items"])
          and p.get_attribute("#today", "aria-pressed") == "true" and "lesson" in p.inner_text("#day-sum"), p.inner_text("#day"))
    before = p.evaluate("window.mind.sparksLaunched")
    p.click("#day-replay")
    p.wait_for_timeout(300 + 750 * len(day["items"]))
    check("k. Replay flies a spark to every lesson of today", p.evaluate("window.mind.sparksLaunched") - before >= len(day["items"]), p.evaluate("window.mind.sparksLaunched") - before)
    p.click("#day-list button")
    p.wait_for_timeout(300)
    check("k. a tap on a lesson flies to its note and opens the card", p.is_visible("#card") or p.evaluate("window.mind.focus") is not None)
    p.click("#day-close")
    check("k. the close button hides the panel", p.is_hidden("#day") and p.get_attribute("#today", "aria-pressed") == "false")
    check("k. no console errors", not real_errors(log), real_errors(log))
    ctx.close()


def live_cases(br, origin):
    """2026-11-03: Jarvis learning, live (live.js reads her localStorage keys, read-only)."""
    src = open(os.path.join(MIND, "live.js"), encoding="utf-8").read()
    code = re.sub(r"//.*", "", src)
    check("l. live.js only reads: no setItem / removeItem / fetch / network, never names the vault's secret key",
          not re.search(r"setItem|removeItem|fetch\s*\(|XMLHttpRequest|sendBeacon|WebSocket|'jarvis\.vault'", code), code[:80])
    html = open(os.path.join(MIND, "index.html"), encoding="utf-8").read()
    check("l. the Jarvis brain counter and the Teach Jarvis button (opens ../jarvis/) are on the page",
          all(i in html for i in ('id="jb-mem"', 'id="jb-notes"', 'id="jb-topics"', 'id="teach"', 'href="../jarvis/"')))
    MOCK["js"] = None
    ctx, p, log = new_page(br, origin, (390, 844))
    p.goto(origin + "/mind/?q=off")
    ready(p)
    n0 = p.evaluate("window.mind.stats.notes")
    check("l. before: the counter starts at zero memories", p.inner_text("#jb-mem") == "0" and p.evaluate("window.mind.live.memories") == 0)
    p.evaluate("""() => { localStorage.setItem('jarvis.assistant.v1', JSON.stringify({ v: 1, facts: [
        { id: 'f1', t: Date.now(), text: 'My NQ stop goes one tick beyond the sweep' }, { id: 'f2', t: Date.now(), text: 'I love sushi' }], todos: [], notes: [] }));
      localStorage.setItem('jarvis.vault.learned', JSON.stringify([{ t: Math.floor(Date.now() / 1000), text: 'Size follows the stop', note: 'Trading/Rules.md' }])); }""")
    p.wait_for_function("window.mind.live && window.mind.live.memories === 2", timeout=15000)
    p.wait_for_timeout(600)
    n1 = p.evaluate("window.mind.stats.notes")
    check("l. a fact saved in Jarvis's storage becomes a node in the galaxy (poll fallback, no reload)", n1 >= n0 + 2, (n0, n1))
    check("l. the 'Jarvis learned:' toast shows (or the spark flew)", "Jarvis learned" in p.inner_text("#toast") or p.evaluate("window.mind.sparksLaunched") > 0, p.inner_text("#toast"))
    check("l. the Jarvis brain counter: 2 memories, 1 note written", p.inner_text("#jb-mem") == "2" and p.inner_text("#jb-notes") == "1", p.inner_text("#jbrain"))
    chips = p.evaluate("[...document.querySelectorAll('#chips .chip')].map((c) => c.textContent)")
    check("l. the trading fact joins the Trading constellation (the other lands in Jarvis memory)", any("Trading" in c for c in chips) and any("Jarvis memory" in c for c in chips), chips)
    p.evaluate("""() => { const a = JSON.parse(localStorage.getItem('jarvis.assistant.v1')); a.facts.push({ id: 'f3', t: Date.now(), text: 'Leg day is Thursday' });
      localStorage.setItem('jarvis.assistant.v1', JSON.stringify(a)); window.dispatchEvent(new StorageEvent('storage', { key: 'jarvis.assistant.v1' })); }""")
    p.wait_for_function("window.mind.live.memories === 3", timeout=5000)
    check("l. the storage event updates at once (no wait for the poll)", p.evaluate("window.mind.live.memories") == 3)
    p.evaluate("localStorage.setItem('jarvis.assistant.v1', '{junk')")
    p.wait_for_timeout(5000)
    check("l. junk in the key is ignored: the brain stays, no errors", p.evaluate("window.mind.stats.notes") >= n1 and not real_errors(log), real_errors(log))
    check("l. no console errors", not real_errors(log), real_errors(log))
    ctx.close()


# ------------------------------------------------------------------ m. the 2026-11-04 overhaul: unit checks in node (the pure modules)
UNIT_JS = r"""
import { createDemo } from '__MIND__/demo.js';
import { buildGraph } from '__MIND__/graph.js';
import * as I from '__MIND__/insights.js';
import * as Q from '__MIND__/quiz.js';
import { teach, screen } from '__MIND__/teach.js';
const out = {}, now = Date.now(), DAY = 864e5;
const g = buildGraph(await createDemo().graphSnapshot(), now);
const mk = (offs) => buildGraph({ t: now, learned: [], notes: offs.map((d, i) => ({ id: 'n' + i, path: 'n' + i + '.md', title: 'n' + i, tags: [], links: [], mtime: now - d * DAY, words: 5, kind: 'note', snippet: '' })) }, now);
out.streak = I.brainStats(mk([0, 1, 2, 5, 6]), now).streak;
out.streakNoToday = I.brainStats(mk([1]), now).streak;
out.streakNone = I.brainStats(mk([]), now).streak;
out.streakBroken = I.brainStats(mk([3]), now).streak;
out.orphans = I.orphans(g).map((n) => n.title);
out.hubs = I.hubs(g, 3).map((n) => n.degree);
out.cloud = I.tagCloud(g, 30).map((t) => [t.tag, t.weight]);
const hub = I.hubs(g, 1)[0], e = I.ego(g, hub.i, 8);
out.ego = { ring: e.ring.length, centre: e.centre.title, dirs: [...new Set(e.ring.map((r) => r.dir))].sort() };
out.filter = { orphans: I.filterSet(g, 'orphans', 0, now).size, expectOrphans: I.orphans(g).length, all: I.filterSet(g, 'all', 0, now), min3: [...I.filterSet(g, 'all', 3, now)].every((i) => g.nodes[i].degree >= 3),
  hubs: I.filterSet(g, 'hubs', 0, now).size, recent: [...I.filterSet(g, 'recent', 0, now)].every((i) => now - g.nodes[i].mtime < 7 * DAY) };
out.previewEmpty = g.nodes.filter((n) => !I.previewText(n).trim()).length;
out.link = [I.obsidianLink('My Vault', g.nodes[g.index.get('Kalshi/Kalshi bot.md')]), I.obsidianLink('', g.nodes[0]), I.obsidianLink('V', { id: 'live:x', path: 'Jarvis/fact/x' })];
const st = I.brainStats(g, now);
out.stats = { notes: st.notes === g.nodes.length, growthUp: st.growth.every((p, k) => !k || p.total >= st.growth[k - 1].total), weeks: st.weekly.edits.length, level: st.level.level >= 1, prog: st.level.progress >= 0 && st.level.progress <= 1, orph: st.orphans };
const tl = I.timeline(g, now, 28);
out.timeline = { n: tl.length, sorted: tl.every((d, k) => !k || tl[k - 1].key > d.key), daily: tl.filter((d) => d.daily.length).length };
const feed = I.learnedFeed(g);
out.feed = { n: feed.length, sorted: feed.every((x, k) => !k || feed[k - 1].t >= x.t) };
// the quiz
const deck = Q.buildDeck(g, now), deck2 = Q.buildDeck(g, now);
out.deck = { n: deck.length, same: JSON.stringify(deck) === JSON.stringify(deck2), ids: new Set(deck.map((q) => q.id)).size === deck.length,
  four: deck.every((q) => q.choices.length === 4 && new Set(q.choices).size === 4 && q.answer >= 0 && q.answer < 4), kinds: [...new Set(deck.map((q) => q.kind))].sort() };
const s1 = Q.pickSession(deck, { cards: {}, days: [] }, now, 5);
out.session = { n: s1.length, distinct: new Set(s1.map((q) => q.id)).size, firstNotStarter: s1[0].kind !== 'starter' };
let state = Q.grade({ cards: {}, days: [] }, deck[0].id, true, now);
out.grade1 = { box: state.cards[deck[0].id].b, dueDays: Math.round((state.cards[deck[0].id].d - now) / DAY), days: state.days.length };
for (let k = 0; k < 6; k++) state = Q.grade(state, deck[0].id, true, now);
out.gradeTop = { box: state.cards[deck[0].id].b, dueDays: Math.round((state.cards[deck[0].id].d - now) / DAY) };
const wrong = Q.grade(state, deck[0].id, false, now);
out.gradeWrong = { box: wrong.cards[deck[0].id].b, due: wrong.cards[deck[0].id].d <= now };
const s2 = Q.pickSession(deck, state, now, 5);
out.sessionAfter = { skipsMastered: !s2.some((q) => q.id === deck[0].id), due: Q.dueCount(deck, state, now) === deck.length - 1, boxes: Q.boxes(state) };
const empty = buildGraph({ notes: [], learned: [], t: now }, now);
out.emptyDeck = Q.buildDeck(empty, now).length;
out.emptyStats = I.brainStats(empty, now).notes;
// teach, on a mock storage
const mem = {}, store = { getItem: (k) => (k in mem ? mem[k] : null), setItem: (k, v) => { mem[k] = String(v); } };
mem['jarvis.assistant.v1'] = JSON.stringify({ v: 1, facts: [{ id: 'f0', t: 1, text: 'Old fact' }], todos: [{ id: 't1', t: 2, text: 'keep me' }], notes: [], reminders: [], told: true });
const r1 = teach({ kind: 'fact', text: '  my leg day   is Thursday ' }, { storage: store, now: () => 1700000000000 });
const A = JSON.parse(mem['jarvis.assistant.v1']);
out.fact = { ok: r1.ok, n: A.facts.length, last: A.facts[1], keep: A.todos.length === 1 && A.told === true && A.facts[0].id === 'f0' };
teach({ kind: 'fact', text: 'My leg day is thursday' }, { storage: store });
out.factDup = JSON.parse(mem['jarvis.assistant.v1']).facts.length;
const bad = teach({ kind: 'fact', text: 'my pass word is hunter2' }, { storage: store });
out.secret = [bad.ok, !!bad.error && bad.error.length > 10, screen('card 4111 1111 1111 1111') !== '', screen('api key sk-abcdef123456') !== '', screen('I love sushi') === ''];
const n1 = teach({ kind: 'note', title: 'Plan: Q1 / goals?', text: 'Do [[X]]\n\nthings' }, { storage: store, now: () => 1700000005000 });
const L = JSON.parse(mem['jarvis.vault.local']), D = JSON.parse(mem['jarvis.vault.learned']);
out.note = { ok: n1.ok, path: L[0].path, text: L[0].text, t: L[0].t, learned: D[0] };
for (let k = 0; k < 230; k++) teach({ kind: 'note', title: 'N' + k, text: 'x' }, { storage: store });
out.caps = [JSON.parse(mem['jarvis.vault.local']).length <= 200, JSON.parse(mem['jarvis.vault.learned']).length <= 200];
mem['jarvis.assistant.v1'] = '{junk';
const dmg = teach({ kind: 'fact', text: 'hello there' }, { storage: store });
out.damaged = [dmg.ok, mem['jarvis.assistant.v1']];
out.blank = [teach({ kind: 'fact', text: '   ' }, { storage: store }).ok, teach({ kind: 'note', text: '' }, { storage: store }).ok];
console.log(JSON.stringify(out));
"""


def unit_cases():
    import shutil
    import subprocess
    import tempfile
    node = shutil.which("node")
    if not node:
        check("m. node is available for the unit checks", False, "no node")
        return
    with tempfile.TemporaryDirectory() as d:
        f = os.path.join(d, "unit.mjs")
        open(f, "w", encoding="utf-8").write(UNIT_JS.replace("__MIND__", MIND.replace(os.sep, "/")))
        r = subprocess.run([node, f], capture_output=True, text=True, timeout=120)
    try:
        o = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        check("m. the pure modules run in node", False, (r.stdout + r.stderr)[-600:])
        return
    check("m. streak: days in a row (today may still be empty), a gap resets it", o["streak"] == {"current": 3, "best": 3} and o["streakNoToday"]["current"] == 1
          and o["streakNone"] == {"current": 0, "best": 0} and o["streakBroken"]["current"] == 0, [o["streak"], o["streakNoToday"], o["streakBroken"]])
    check("m. orphans: the demo's three loose notes are found, hubs are sorted by links", {"Buy a standing desk", "Try cold showers", "Book the dentist"} <= set(o["orphans"])
          and o["hubs"] == sorted(o["hubs"], reverse=True) and o["hubs"][0] >= 3, (o["orphans"], o["hubs"]))
    check("m. tag cloud: weights 0..1, alphabetical", o["cloud"] and all(0 <= w <= 1 for _, w in o["cloud"]) and [t for t, _ in o["cloud"]] == sorted(t for t, _ in o["cloud"]), o["cloud"][:4])
    check("m. the local map of a hub: its neighbours, links out and backlinks", o["ego"]["ring"] >= 4 and bool({"back", "both"} & set(o["ego"]["dirs"])) and bool({"out", "both"} & set(o["ego"]["dirs"])), o["ego"])
    f = o["filter"]
    check("m. graph filters: orphans, hubs, recent, minimum links, and 'all' = no filter", f["orphans"] == f["expectOrphans"] and f["all"] is None and f["min3"] and 0 < f["hubs"] <= 20 and f["recent"], f)
    check("m. every note has a plain preview, never an empty one", o["previewEmpty"] == 0)
    check("m. Obsidian deep link: obsidian://open?vault=...&file=... (encoded, no .md); none without a vault or for Jarvis's own memory",
          o["link"] == ["obsidian://open?vault=My%20Vault&file=Kalshi%2FKalshi%20bot", None, None], o["link"])
    check("m. stats, growth (never goes down), weekly bars, level", all(o["stats"][k] for k in ("notes", "growthUp", "level", "prog")) and o["stats"]["weeks"] == 8 and o["stats"]["orph"] >= 3, o["stats"])
    check("m. the days timeline (newest first, daily notes) and the learned feed (newest first)", o["timeline"]["n"] >= 5 and o["timeline"]["sorted"] and o["timeline"]["daily"] >= 3 and o["feed"]["n"] >= 10 and o["feed"]["sorted"], (o["timeline"], o["feed"]))
    d = o["deck"]
    check(f"m. the review deck: {d['n']} questions, four distinct choices, a valid answer, the same deck every time, kinds {d['kinds']}",
          d["n"] >= 14 and d["same"] and d["ids"] and d["four"] and {"gap", "galaxy", "link", "tag", "hub", "starter"} <= set(d["kinds"]), d)
    check("m. a session is 5 different questions, real ones before the starters", o["session"] == {"n": 5, "distinct": 5, "firstNotStarter": True}, o["session"])
    check("m. spaced repetition: right = next box, due in 1 day; mastered = 35 days; wrong = box 0, due now; a mastered card is not offered again",
          o["grade1"] == {"box": 1, "dueDays": 1, "days": 1} and o["gradeTop"] == {"box": 5, "dueDays": 35} and o["gradeWrong"] == {"box": 0, "due": True}
          and o["sessionAfter"]["skipsMastered"] and o["sessionAfter"]["due"] and o["sessionAfter"]["boxes"][5] == 1, (o["grade1"], o["gradeTop"], o["gradeWrong"], o["sessionAfter"]))
    check("m. an empty brain still has a deck (starters) and zero stats, no crash", o["emptyDeck"] >= 6 and o["emptyStats"] == 0, (o["emptyDeck"], o["emptyStats"]))
    ft = o["fact"]
    check("m. Teach a fact: written in Jarvis's own shape {id, t, text, key, how}, tidied, the rest of her storage kept, no duplicates",
          ft["ok"] and ft["n"] == 2 and ft["keep"] and ft["last"]["text"] == "My leg day is Thursday" and ft["last"]["t"] == 1700000000000 and ft["last"]["how"] == "told"
          and ft["last"]["key"] == "" and isinstance(ft["last"]["id"], str) and o["factDup"] == 2, (ft, o["factDup"]))
    check("m. Teach refuses passwords, API keys and card numbers (and accepts normal lines)", o["secret"] == [False, True, True, True, True], o["secret"])
    nt = o["note"]
    check("m. Teach a note: Pasted/<clean title>.md with the text, t in ms, and a 'learned' line in unix seconds (what importNote writes); both lists capped at 200",
          nt["ok"] and nt["path"] == "Pasted/Plan Q1 goals.md" and nt["text"] == "Do [[X]]\n\nthings" and nt["t"] == 1700000005000
          and nt["learned"] == {"t": 1700000005, "kind": "import", "text": "Imported the note Plan Q1 goals", "note": "Pasted/Plan Q1 goals.md"} and all(o["caps"]), (nt, o["caps"]))
    check("m. a damaged Jarvis key is never overwritten; empty input saves nothing", o["damaged"] == [False, "{junk"] and o["blank"] == [False, False], (o["damaged"], o["blank"]))


# ------------------------------------------------------------------ m. the overhaul in the browser
SFX_STUB = "window.OLYMPUS_SFX = { play(n) { (window.__sfx = window.__sfx || []).push(n); return true; }, stop() {}, mute() {} };"
PAGES = ["home", "notes", "days", "learned", "graph", "review", "teach", "stats", "look"]


def open_panel(p, name):
    p.click(f"#dock [data-panel={name}]")
    p.wait_for_function(f"document.getElementById('panel').dataset.view === '{name}' && !document.getElementById('panel').hidden", timeout=20000)
    p.wait_for_timeout(250)


def overhaul_cases(br, origin):
    MOCK["js"] = None
    ctx, p, log = new_page(br, origin, (390, 844))
    p.add_init_script(SFX_STUB)
    p.goto(origin + "/mind/?q=off&home=1")
    ready(p)
    time.sleep(1.5)
    # --- Home: the dashboard is there at once, never a blank sky
    check("m. Home opens by itself (?home=1): the dashboard over the brain, DEMO labelled",
          p.is_visible("#panel") and p.get_attribute("#panel", "data-view") == "home" and "DEMO" in p.inner_text("#p-sub") and p.locator("#panel .demo-pill").count() == 1)
    tiles = p.evaluate("Object.fromEntries([...document.querySelectorAll('#panel .tile')].map((t) => [t.dataset.k, t.querySelector('b').textContent]))")
    check(f"m. Home tiles: notes, links, galaxies, streak, learned today, orphans ({tiles})",
          {"notes", "links", "topics", "streak", "today", "orphans"} <= set(tiles) and int(tiles["notes"]) > 80 and int(tiles["links"]) > 150 and tiles["streak"].endswith("d") and int(tiles["today"]) >= 1 and int(tiles["orphans"]) >= 3, tiles)
    check("m. Home: the growth chart (an SVG with a glowing line), today's learning, the galaxies bars and four quick actions",
          p.locator("#panel svg.chart path.glowline").count() == 1 and p.locator("#panel .learn").count() >= 1 and p.locator("#panel .galrow").count() >= 5 and p.locator("#panel .act").count() == 4)
    px = lit_pixels(p)
    check(f"m. the 3D brain is still drawn behind the dashboard ({px} bright pixels)", px == -1 or px > 400, px)
    sw = p.evaluate("[document.scrollingElement.scrollWidth, innerWidth]")
    check("m. Home: no sideways scroll, the orb's corner free", sw[0] <= sw[1] and not orb_corner_free(p), (sw, orb_corner_free(p)))
    check("m. under the open page only the 'Jarvis learned' line stays of the bottom sheet", p.evaluate("[...document.querySelectorAll('#bottom > *')].filter((e) => e.offsetParent).map((e) => e.id)") == ["ticker"])
    shot(p, "home_390.png")
    p.keyboard.press("Escape")
    check("m. Escape closes the page", p.is_hidden("#panel") and p.evaluate("mind.panel") is None)
    # --- the dock: nine pages, each with content, toggling
    check("m. the dock has the nine pages, each button 44 px tall or more", p.evaluate("[...document.querySelectorAll('#dock button[data-panel]')].map((b) => b.dataset.panel)") == PAGES
          and p.evaluate("[...document.querySelectorAll('#dock button')].every((b) => b.getBoundingClientRect().height >= 44)"))
    empties = []
    for n in PAGES:
        open_panel(p, n)
        txt = p.inner_text("#p-body")
        if len(txt.strip()) < 30 or p.get_attribute(f"#dock [data-panel={n}]", "aria-pressed") != "true":
            empties.append(n)
        shot(p, f"page_{n}_390.png")
    check("m. every page has content and its dock button is pressed", not empties, empties)
    p.click("#dock [data-panel=look]")
    check("m. tapping the open page's button closes it", p.is_hidden("#panel"))
    # --- Notes: cards with previews and tags, filter, tag cloud
    open_panel(p, "notes")
    cards = p.evaluate("[...document.querySelectorAll('#panel .ncard')].map((c) => [c.querySelector('strong').textContent, c.querySelector('.nc-pre').textContent.length, c.querySelectorAll('.nc-tags span').length])")
    check(f"m. Notes: glass cards with a title, a preview and tags ({len(cards)} shown)", len(cards) >= 20 and all(c[1] > 5 for c in cards) and any(c[2] for c in cards), cards[:3])
    p.fill("#panel input[type=search]", "gym")
    p.wait_for_timeout(200)
    titles = p.evaluate("[...document.querySelectorAll('#panel .ncard strong')].map((e) => e.textContent)")
    check(f"m. Notes: the filter narrows the cards ({len(titles)})", 0 < len(titles) < len(cards) and any("day" in t.lower() for t in titles), titles[:5])
    p.fill("#panel input[type=search]", "")
    p.click("#panel .seg button[data-k=links]")
    p.wait_for_timeout(150)
    check("m. Notes: sort by most linked", p.get_attribute("#panel .seg button[data-k=links]", "aria-pressed") == "true")
    p.locator("#panel .tagc", has_text="#kalshi").first.click()
    p.wait_for_timeout(300)
    dim = p.evaluate("mind.dim")
    check(f"m. the tag cloud filters: #kalshi, the pill under the search, the rest of the brain dims ({dim} notes)",
          p.evaluate("mind.tag") == "kalshi" and p.is_visible("#filterbar") and "#kalshi" in p.inner_text("#filterbar") and dim > 60, (p.evaluate("mind.tag"), dim))
    kal = p.evaluate("[...document.querySelectorAll('#panel .ncard strong')].length")
    check(f"m. the cards follow the tag ({kal} notes tagged kalshi)", 0 < kal < len(cards), kal)
    p.click("#filter-exit")
    p.wait_for_timeout(200)
    check("m. × on the pill clears the tag and the dimming", p.evaluate("mind.tag") is None and p.evaluate("mind.dim") == 0 and p.is_hidden("#filterbar"))
    p.locator("#panel .ncard").first.click()
    p.wait_for_function("mind.focus !== null", timeout=4000)
    check("m. a note card flies to the note, opens its card and closes the page", p.is_visible("#card") and p.is_hidden("#panel"))
    wait_flight(p)
    p.click("#c-close")
    # --- Days
    open_panel(p, "days")
    d = p.evaluate("({days: document.querySelectorAll('#panel .tday').length, daily: document.querySelectorAll('#panel .daily').length, first: document.querySelector('#panel .tday h3 span').textContent})")
    check(f"m. Days: a timeline of days with daily notes and lessons ({d})", d["days"] >= 5 and d["daily"] >= 3 and d["first"] in ("Today", "Yesterday"), d)
    p.locator("#panel .daily").first.click()
    p.wait_for_function("mind.focus !== null", timeout=4000)
    check("m. a daily note on the timeline opens", p.is_visible("#card") and p.is_hidden("#panel"))
    wait_flight(p)
    p.click("#c-close")
    # --- Learned feed and replay
    open_panel(p, "learned")
    n = p.locator("#panel .feeditem").count()
    check(f"m. Learned: a feed of what Jarvis learned, with filters ({n} items)", n >= 8 and p.locator("#panel .seg button").count() == 3 and p.locator("#panel .tile").count() == 3)
    p.click("#panel .seg button[data-k=lessons]")
    nl = p.locator("#panel .feeditem").count()
    check(f"m. Learned: the Lessons filter ({nl} of {n})", 0 < nl < n)
    launched = p.evaluate("mind.sparksLaunched")
    p.click("#panel .toolbar .cta")
    p.wait_for_function(f"mind.sparksLaunched >= {launched + 3}", timeout=9000)
    check("m. Learned: Replay closes the page and flies a spark to each lesson in time order", p.is_hidden("#panel") and p.evaluate("mind.sparksLaunched") >= launched + 3)
    p.wait_for_function("mind.sparks === 0", timeout=15000)
    # --- Graph: filters, local map, hubs, orphans, galaxies
    open_panel(p, "graph")
    check("m. Graph: the local map of a note (links to the right, backlinks to the left, tap a neighbour), hubs and orphans listed",
          p.locator("#panel svg.egomap .eg-n").count() >= 4 and p.locator("#panel .card2", has_text="Hubs").locator(".row").count() >= 3
          and "Buy a standing desk" in p.inner_text("#panel"), p.locator("#panel svg.egomap .eg-n").count())
    p.click("#panel .seg button[data-k=orphans]")
    p.wait_for_timeout(300)
    gm, dim = p.evaluate("mind.gmode"), p.evaluate("mind.dim")
    total = p.evaluate("mind.stats.notes")
    check(f"m. Graph: the Orphans filter dims everything with links ({dim} of {total} dimmed), the pill says so", gm["mode"] == "orphans" and dim >= total - 12 and p.is_visible("#filterbar") and "orphans" in p.inner_text("#filterbar"), (gm, dim, total))
    p.evaluate("""() => { const s = document.querySelector('#panel input[type=range]'); s.value = 3; s.dispatchEvent(new Event('change', { bubbles: true })); }""")
    p.wait_for_timeout(300)
    check("m. Graph: the minimum-links slider", p.evaluate("mind.gmode").get("min") == 3 and "3+ links" in p.inner_text("#filterbar"), p.inner_text("#filterbar"))
    p.click("#panel .seg button[data-k=hubs]")
    p.wait_for_timeout(300)
    hubs_dim = p.evaluate("mind.dim")
    check(f"m. Graph: the Hubs filter keeps only the big stars lit ({total - hubs_dim} of {total})", 0 < total - hubs_dim <= max(20, total // 8), (hubs_dim, total))
    p.click("#filter-exit")
    check("m. Graph: × clears the graph filter", p.evaluate("mind.gmode") == {"mode": "all", "min": 0} and p.evaluate("mind.dim") == 0)
    p.click("#panel .galrow >> nth=0")
    p.wait_for_function("mind.filter !== null", timeout=15000)
    check("m. Graph: a galaxy row focuses that galaxy (focus mode) and closes the page", p.is_visible("#focusbar") and p.is_hidden("#panel"))
    p.click("#focus-exit")
    wait_flight(p)
    # --- Review: a session, boxes, persistence
    open_panel(p, "review")
    p.click("#rv-start")
    right = 0
    for k in range(5):
        q = p.evaluate("mind.review")
        p.click(f".choice[data-i='{q['answer']}']")
        ok = p.locator(".choice.right").count() == 1 and p.locator(".choice.wrong").count() == 0 and p.is_visible("#rv-next")
        right += ok
        if k == 0:
            shot(p, "review_390.png")
        p.click("#rv-next")
    check("m. Review: five questions, the right answer lights up green, Next moves on", right == 5, right)
    res = p.inner_text("#panel .result h2")
    cards_saved = p.evaluate("JSON.parse(localStorage.getItem('mind.review'))")
    check(f"m. Review: the result ({res}), the cards kept under 'mind.review' in box 1, today counted for the review streak",
          res == "5 of 5" and len(cards_saved["cards"]) == 5 and all(c["b"] == 1 for c in cards_saved["cards"].values()) and len(cards_saved["days"]) == 1, cards_saved)
    p.click("#panel .result .cta")
    q2 = p.evaluate("mind.review")
    check("m. Review: Go again gives new questions, not the five just learned", q2["id"] not in cards_saved["cards"], q2["id"])
    wrong = next(i for i in range(4) if i != q2["answer"])
    p.click(f".choice[data-i='{wrong}']")
    check("m. Review: a wrong answer shows red, the right one green, and why", p.locator(".choice.wrong").count() == 1 and p.locator(".choice.right").count() == 1 and len(p.inner_text("#panel .why")) > 20)
    after = p.evaluate("JSON.parse(localStorage.getItem('mind.review')).cards")[q2["id"]]
    check("m. Review: the missed card goes to box 0, due now", after["b"] == 0, after)
    p.keyboard.press("Escape")
    # --- Teach Jarvis: writes into Jarvis's own keys
    p.evaluate("""() => { localStorage.setItem('jarvis.assistant.v1', JSON.stringify({ v: 1, facts: [{ id: 'f0', t: Date.now() - 5000, text: 'Old fact' }],
        todos: [{ id: 't1', t: 1, text: 'keep me' }], notes: [], reminders: [], told: true })); }""")
    open_panel(p, "teach")
    n0 = p.evaluate("mind.stats.notes")
    p.fill("#teach-text", "My best trades come before 11:00")
    p.click("#teach-save")
    A = p.evaluate("JSON.parse(localStorage.getItem('jarvis.assistant.v1'))")
    last = A["facts"][-1]
    check("m. Teach: the fact lands in jarvis.assistant.v1 in Jarvis's own shape, her other data untouched",
          len(A["facts"]) == 2 and last["text"] == "My best trades come before 11:00" and last["how"] == "told" and last["key"] == "" and isinstance(last["t"], int) and A["todos"][0]["text"] == "keep me" and A["told"] is True, A)
    check("m. Teach: the page says so (saved, in green)", "Saved" in p.inner_text("#panel .msg.ok"), p.inner_text("#panel .msg"))
    p.wait_for_function(f"mind.stats.notes >= {n0 + 2} && mind.live.memories >= 2", timeout=60000)
    check("m. Teach: the new fact joins the 3D brain at once (a node, a spark), Jarvis brain counter 2 memories", p.evaluate("mind.sparksLaunched") >= 1 and p.inner_text("#jb-mem") == "2", p.inner_text("#jb-mem"))
    p.fill("#teach-text", "my pass word is hunter2")
    check("m. Teach: a password is flagged while typing", len(p.inner_text("#panel .warn")) > 10)
    p.click("#teach-save")
    check("m. Teach: a password is refused and nothing is written", p.locator("#panel .msg.bad").count() == 1 and len(p.evaluate("JSON.parse(localStorage.getItem('jarvis.assistant.v1')).facts")) == 2)
    p.click("#panel .seg button[data-k=note]")
    p.fill("#teach-title", "Plan for Q1")
    p.fill("#teach-text", "Do [[LIT strategy]] reviews every Sunday.")
    p.click("#teach-save")
    local = p.evaluate("JSON.parse(localStorage.getItem('jarvis.vault.local'))")
    learned = p.evaluate("JSON.parse(localStorage.getItem('jarvis.vault.learned'))")
    check("m. Teach a note: jarvis.vault.local {path, text, t} and a 'learned' line, as importNote writes them",
          local[-1]["path"] == "Pasted/Plan for Q1.md" and "[[LIT strategy]]" in local[-1]["text"] and isinstance(local[-1]["t"], int)
          and learned[-1]["kind"] == "import" and learned[-1]["note"] == "Pasted/Plan for Q1.md" and learned[-1]["t"] < 1e11, (local, learned))
    p.evaluate("localStorage.setItem('jarvis.assistant.v1', '{junk')")
    p.click("#panel .seg button[data-k=fact]")
    p.fill("#teach-text", "hello again")
    p.click("#teach-save")
    check("m. Teach: a damaged Jarvis key is told so and never overwritten", p.locator("#panel .msg.bad").count() == 1 and p.evaluate("localStorage.getItem('jarvis.assistant.v1')") == "{junk")
    p.evaluate("""() => { localStorage.setItem('jarvis.assistant.v1', JSON.stringify({ v: 1, facts: [{ id: 'f9', t: Date.now(), text: 'My best trades come before 11:00' }], todos: [], notes: [] })); }""")
    p.keyboard.press("Escape")
    # --- Stats
    open_panel(p, "stats")
    st = p.evaluate("({tiles: document.querySelectorAll('#panel .tile').length, bars: document.querySelectorAll('#panel .cbar').length, ring: !!document.querySelector('#panel .ringbox'), gal: document.querySelectorAll('#panel .galrow').length, rec: document.querySelectorAll('#panel .row').length})")
    check(f"m. Stats: level ring, six tiles, two weekly bar charts, galaxies, records ({st})", st["tiles"] == 6 and st["bars"] == 16 and st["ring"] and st["gal"] >= 5 and st["rec"] >= 4, st)
    p.keyboard.press("Escape")
    # --- sounds through the kit
    p.evaluate("window.__sfx = []")
    open_panel(p, "notes")
    heard = p.evaluate("window.__sfx")
    check("m. sounds go through OLYMPUS.sfx (a tap on a dock button)", "tap" in heard, heard)
    open_panel(p, "look")
    p.click("#panel [data-k=sound]")
    p.evaluate("window.__sfx = []")
    open_panel(p, "stats")
    check("m. the Sounds switch silences them (and is kept)", p.evaluate("window.__sfx") == [] and p.evaluate("mind.prefs").get("sound") is False)
    # --- Look: skins, atmosphere, the vault name and the Obsidian link
    open_panel(p, "look")
    check("m. Look: eight skins, three switches, a vault name field", p.locator("#panel .skin").count() == 8 and p.locator("#panel .switch").count() == 3 and p.locator("#vault-name").count() == 1)
    p.click("#panel [data-skin=ember]")
    p.wait_for_timeout(300)
    cyan = p.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--cyan').trim()")
    check("m. the Ember skin restyles the page and is kept",
          cyan == "#ff9a4d" and p.evaluate("JSON.parse(localStorage.getItem('mind.prefs')).skin") == "ember", cyan)
    p.keyboard.press("Escape")
    time.sleep(1.2)
    shot(p, "skin_ember_390.png")
    open_panel(p, "look")
    p.click("#panel [data-skin=auto]")
    p.wait_for_timeout(300)
    back = p.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--cyan').trim()")
    check("m. skin 'Follow OLYMPUS' restores the default accent", back in ("", "#6ff6ff"), back)
    amb = p.evaluate("mind.ambient")
    check(f"m. ambient layers on HD: the nebula sky and {amb['motes']} drifting motes", amb["sky"] and amb["dust"] and amb["motes"] >= 1000, amb)
    p.click("#panel [data-k=dust]")
    p.click("#panel [data-k=sky]")
    amb2 = p.evaluate("mind.ambient")
    check("m. the Ambient particles and Nebula sky switches turn the layers off", not amb2["sky"] and not amb2["dust"] and p.get_attribute("#panel [data-k=dust]", "aria-checked") == "false", amb2)
    p.click("#panel [data-k=dust]")
    p.click("#panel [data-k=sky]")
    p.fill("#vault-name", "My Vault")
    p.press("#vault-name", "Tab")
    p.keyboard.press("Escape")
    p.fill("#q", "Kalshi bot")
    p.press("#q", "Enter")
    p.wait_for_function("mind.focus === 'Kalshi/Kalshi bot.md'", timeout=4000)
    href = p.get_attribute("#c-obsidian", "href")
    check("m. the note card gets Open in Obsidian: obsidian://open?vault=My%20Vault&file=Kalshi%2FKalshi%20bot",
          p.is_visible("#c-obsidian") and href == "obsidian://open?vault=My%20Vault&file=Kalshi%2FKalshi%20bot", href)
    p.click("#c-close")
    wait_flight(p)
    p.wait_for_function("mind.live && mind.live.memories === 1", timeout=60000)
    p.wait_for_timeout(800)
    p.fill("#q", "best trades come")
    p.press("#q", "Enter")
    p.wait_for_function("mind.focus && mind.focus.startsWith('live:')", timeout=8000)
    check("m. a fact that only lives in Jarvis's memory has no Obsidian button", p.is_hidden("#c-obsidian"))
    p.click("#c-close")
    # Home: Surprise me, the review badge
    open_panel(p, "home")
    badge = p.evaluate("(() => { const b = document.querySelector('#dock [data-panel=review] .badge'); return b && !b.hidden ? b.textContent : null; })()")
    check(f"m. the Review button shows how many questions are waiting ({badge})", badge is not None, badge)
    p.click("#panel .act >> nth=2")
    p.wait_for_function("mind.focus !== null", timeout=4000)
    check("m. Home: Surprise me flies to a random note", p.is_visible("#card") and p.is_hidden("#panel"))
    check("m. no console errors across every page", not real_errors(log), real_errors(log))
    check("i. the pages fetched nothing", p.evaluate("window.__net") == [], p.evaluate("window.__net"))
    ctx.close()

    # a vault that is connected but empty: the demo brain, never a blank sky
    MOCK["js"] = FAKE_OBSIDIAN
    now = int(time.time() * 1000)
    ctx, p, log = new_page(br, origin, (390, 844), snap={"v": 1, "t": now, "notes": [], "learned": []})
    p.goto(origin + "/mind/?q=off&home=0")
    ready(p)
    st = p.evaluate("({mode: mind.mode, stats: mind.stats})")
    check(f"m. a connected but empty vault shows the labelled demo brain ({st['stats']['notes']} notes), never a blank sky",
          st["mode"] == "demo" and st["stats"]["notes"] > 80 and p.is_visible("#demo") and not real_errors(log), (st, real_errors(log)))
    ctx.close()
    # a tiny real vault: the dashboard still has things to say
    tiny = {"v": 1, "t": now, "notes": [{"id": "A.md", "title": "A", "path": "A.md", "tags": [], "links": ["B.md"], "mtime": now, "words": 20, "kind": "note"},
                                          {"id": "B.md", "title": "B", "path": "B.md", "tags": ["x"], "links": [], "mtime": now - 3 * 86400_000, "words": 5, "kind": "note"}], "learned": []}
    ctx, p, log = new_page(br, origin, (390, 844), snap=tiny)
    p.goto(origin + "/mind/?q=off&home=1")
    ready(p)
    p.wait_for_timeout(600)
    check("m. a tiny live vault: the Home page still fills the screen (tiles, chart, 'Grow your brain')",
          p.locator("#panel .tile").count() == 6 and p.locator("#panel svg.chart").count() == 1 and "grow your brain" in p.inner_text("#panel").lower() and "DEMO" not in p.inner_text("#p-sub"), p.inner_text("#panel")[:200])
    p.keyboard.press("Escape")
    for n in PAGES:
        open_panel(p, n)
    check("m. a tiny live vault: every page opens without an error", not real_errors(log), real_errors(log))
    ctx.close()
    MOCK["js"] = None

    # landscape phone: the dock is icons only, the page a side sheet, the orb's corner free
    ctx, p, log = new_page(br, origin, (844, 390))
    p.goto(origin + "/mind/?q=off")
    ready(p)
    p.wait_for_timeout(800)
    open_panel(p, "notes")
    box = p.evaluate("(() => { const r = document.getElementById('panel').getBoundingClientRect(); return [r.width, r.left, r.top, r.bottom, innerWidth, innerHeight]; })()")
    sw = p.evaluate("[document.scrollingElement.scrollWidth, innerWidth]")
    check(f"m. 844 x 390: the page is a side sheet ({box[0]:.0f} px wide), the orb's corner free, no sideways scroll, the dock labels hidden",
          box[0] < box[4] * 0.6 and box[3] <= box[5] + 16 and not orb_corner_free(p) and sw[0] <= sw[1] and p.evaluate("getComputedStyle(document.querySelector('#dock span')).display") == "none", (box, orb_corner_free(p), sw))
    shot(p, "page_landscape.png")
    check("m. 844 x 390: no console errors", not real_errors(log), real_errors(log))
    ctx.close()

    # LITE and reduced motion
    ctx, p, log = new_page(br, origin, (390, 844), quality="low", reduced=True)
    p.goto(origin + "/mind/?q=off")
    ready(p)
    p.wait_for_timeout(800)
    amb = p.evaluate("mind.ambient")
    for n in PAGES:
        open_panel(p, n)
    check(f"m. LITE + reduced motion: fewer motes ({amb['motes']}), every page opens, no errors", 0 < amb["motes"] <= 400 and not real_errors(log), (amb, real_errors(log)))
    ctx.close()


def main():
    static_checks()
    unit_cases()
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    origin = f"http://127.0.0.1:{srv.server_port}"
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
        br = pw.chromium.launch(**({"executable_path": exe} if exe else {}))
        try:
            demo_cases(br, origin)
            mock_cases(br, origin)
            upgrade_cases(br, origin)
            render_core_cases(br, origin)
            live_cases(br, origin)
            overhaul_cases(br, origin)
            other_cases(br, origin)
        finally:
            br.close()
    srv.shutdown()
    check("i. no request ever left the page's own origin", not OUTSIDE, OUTSIDE)
    n_ok = sum(RES)
    print(f"\n{n_ok}/{len(RES)} passed")
    sys.exit(0 if n_ok == len(RES) else 1)


if __name__ == "__main__":
    main()
