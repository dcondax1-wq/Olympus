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
    python -X utf8 -m tests.test_mind_page
MIND_SHOTS=<dir> also saves screenshots (overview, a node card, the learning spark) there.
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
MODULES = ["main.js", "data.js", "demo.js", "graph.js", "layout.js", "layout-worker.js", "render.js", "controls.js", "ui.js"]
RES = []
MOCK = {"js": None}                       # the fake ../jarvis/obsidian.js (None = 404, like a Jarvis without it)
OUTSIDE = []                              # every request to another origin (must stay empty)


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:400]}"), flush=True)


# ------------------------------------------------------------------ a. static rules
def static_checks():
    present = [f for f in MODULES + ["index.html", "mind.css", "jarvis.json"] if not os.path.isfile(os.path.join(MIND, f))]
    check("a. every file is there", not present, present)
    src = {f: open(os.path.join(MIND, f), encoding="utf-8").read() for f in MODULES}
    html = open(os.path.join(MIND, "index.html"), encoding="utf-8").read()
    css = open(os.path.join(MIND, "mind.css"), encoding="utf-8").read()
    unused = []
    for f, s in src.items():
        for name in re.findall(r"^export (?:async )?(?:function|class|const|let) (\w+)", s, re.M):
            if not any(re.search(r"import \{[^}]*\b" + name + r"\b[^}]*\} from '\./" + re.escape(f[:-3]) + r"\.js'", o) for g, o in src.items() if g != f):
                unused.append(f"{f}:{name}")
    check("a. every export is imported by another module (no dead exports)", not unused, unused)
    net = [f for f, s in src.items() if re.search(r"\bfetch\s*\(|XMLHttpRequest|sendBeacon|WebSocket|EventSource|importScripts", s)]
    check("a. no network API in the page's code", not net, net)
    keys = set(re.findall(r"localStorage\.\w+\(([^,)]+)", "".join(src.values())))
    check("a. storage only under the page's own 'mind.' key", keys == {"QUALITY_KEY"} and "const QUALITY_KEY = 'mind.quality';" in src["main.js"], keys)
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
    notes += [None, {"title": "no id"}, dict(notes[0])]                       # junk: dropped
    learned = [{"t": now_ms - 7200_000, "text": "Older lesson about sleep", "note": "Gym/Mock Gym 2.md"},
               {"t": (now_ms - 600_000) // 1000, "text": "Mock lesson: trade the NY open", "note": "Trading/Mock Trading 0.md"},
               {"t": now_ms - 20 * 86400_000, "text": "An old lesson", "note": None}, {"t": now_ms, "text": ""}]
    return {"v": 1, "t": now_ms, "notes": notes, "learned": learned}


MOCK_NOTES = 4 * 12 + 5 + 2 + 1


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
    url = origin + "/mind/"
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
    p.wait_for_selector("#results li[data-id]", timeout=3000)
    first = p.get_attribute("#results li[data-id]", "data-id")
    check(f"c. {tag}: typing lists the matching notes", first == "Kalshi/Kalshi bot.md", first)
    p.press("#q", "Enter")
    p.wait_for_function("mind.focus === 'Kalshi/Kalshi bot.md'", timeout=3000)
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
    p.wait_for_function("mind.focus !== 'Kalshi/Kalshi bot.md'", timeout=3000)
    wait_flight(p)
    target = p.evaluate("mind.focus")
    p.click("#c-close")
    check(f"c. {tag}: a linked note in the card flies to it; × closes the card", target and p.is_hidden("#card"), target)
    # a tap on a node opens its card
    scr = p.evaluate(f"mind.screenOf({json.dumps(target)})")
    p.mouse.click(scr["x"], scr["y"])
    p.wait_for_function("mind.focus !== null", timeout=3000)
    check(f"c. {tag}: tapping a node opens its card", p.is_visible("#card") and p.evaluate("mind.focus") is not None, p.evaluate("mind.focus"))
    p.keyboard.press("Escape")
    check(f"d. {tag}: Escape closes the card", p.is_hidden("#card"))
    # a double tap on a node flies to it
    hub = "Trading/LIT strategy.md"
    wait_flight(p)
    scr = p.evaluate(f"mind.screenOf({json.dumps(hub)})")
    if not (20 < scr["x"] < p.viewport_size["width"] - 20 and 260 < scr["y"] < p.viewport_size["height"] - 200):
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
    p.goto(origin + "/mind/")
    ready(p)
    st = p.evaluate("({mode: mind.mode, stats: mind.stats})")
    check(f"e. the mocked obsidian.js is used: live mode, {st['stats']['notes']} notes (junk dropped)",
          st["mode"] == "live" and st["stats"]["notes"] == MOCK_NOTES and p.is_hidden("#demo") and p.get_attribute("#mode", "data-mode") == "live", st)
    check(f"e. links to missing notes and self links are dropped, each pair counted once ({st['stats']['links']})",
          st["stats"]["links"] == expected_links(vault), (st, expected_links(vault)))
    check("e. learned this week counts the lessons of the last 7 days", st["stats"]["learnedWeek"] == 2, st)
    check("e. the ticker shows the newest lesson", p.inner_text("#tk-text") == "Mock lesson: trade the NY open", p.inner_text("#tk-text"))
    time.sleep(1.5)
    # escaping: the evil title is text, never markup
    p.fill("#q", "evil")
    p.press("#q", "Enter")
    p.wait_for_function("mind.focus === 'Evil.md'", timeout=3000)
    check("e. vault text is shown as text (no injected markup runs)", p.inner_text("#c-title") == EVIL and p.locator("#card img").count() == 0
          and not p.evaluate("window.__pwned") and p.is_hidden("#c-snippet"))
    p.fill("#q", "Mock Trading 0")
    p.press("#q", "Enter")
    p.wait_for_function("mind.focus === 'Trading/Mock Trading 0.md'", timeout=3000)
    check("e. the card shows the first lines when the snapshot has a snippet, and what Jarvis learned about the note",
          p.inner_text("#c-snippet") == "First lines of Trading 0." and "trade the NY open" in p.inner_text("#c-learned"))
    p.click("#c-close")
    wait_flight(p)
    # onIndexChange: a new lesson about an existing note, and a new note
    p.evaluate("""() => { const s = globalThis.__obs.snap;
      s.notes.push({ id: 'Goals/Fresh idea.md', title: 'Fresh idea', path: 'Goals/Fresh idea.md', tags: ['goals'], links: ['Goals/Mock Goals 0.md'], mtime: Date.now(), words: 50, kind: 'note' });
      s.learned.push({ t: Date.now(), text: 'Brand new lesson from the mock vault', note: 'Trading/Mock Trading 4.md' });
      globalThis.__obs.fire(); }""")
    p.wait_for_function("document.getElementById('tk-text').textContent === 'Brand new lesson from the mock vault'", timeout=4000)
    sparks = p.evaluate("mind.sparks")
    shot(p, "spark_390.png")                              # a screenshot takes ~1 s on SwiftShader: the comet is mid-flight
    check("e. onIndexChange: the ticker shows the new lesson at once and a spark flies to its note", sparks >= 1, sparks)
    st2 = p.evaluate("mind.stats")
    check("e. the stats follow (one more note, one more lesson this week)", st2["notes"] == MOCK_NOTES + 1 and st2["learnedWeek"] == 3, st2)
    p.wait_for_function("mind.sparks === 0", timeout=6000)
    check("e. the spark lands (and ignites the note)", True)
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
        p.goto(origin + "/mind/")
        ready(p)
        check(f"f. obsidian.js {name}: the demo brain, no page error", p.evaluate("mind.mode") == "demo" and not log["errors"], log["errors"])
        ctx.close()

    MOCK["js"] = FAKE_OBSIDIAN
    now = int(time.time() * 1000)
    ctx, p, log = new_page(br, origin, (390, 844), snap=mock_vault(now), reduced=True)
    p.goto(origin + "/mind/")
    ready(p)
    p.fill("#q", "Mock Gym 4")
    p.press("#q", "Enter")
    p.wait_for_function("mind.focus === 'Gym/Mock Gym 4.md'", timeout=3000)
    time.sleep(0.3)
    flying = p.evaluate("mind.camera().flying")
    p.evaluate("""() => { globalThis.__obs.snap.learned.push({ t: Date.now(), text: 'Calm lesson', note: 'Gym/Mock Gym 1.md' }); globalThis.__obs.fire(); }""")
    p.wait_for_function("document.getElementById('tk-text').textContent === 'Calm lesson'", timeout=4000)
    check("g. reduced motion: the flight is a cut, the spark an instant ignition, no errors",
          not flying and p.evaluate("mind.sparks") == 0 and not real_errors(log), (flying, real_errors(log)))
    ctx.close()

    MOCK["js"] = None
    ctx, p, log = new_page(br, origin, (390, 844))
    p.goto(origin + "/mind/?demo=2000")
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


def main():
    static_checks()
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
