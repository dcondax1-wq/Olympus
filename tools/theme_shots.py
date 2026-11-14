"""OLYMPUS theme contact sheets (docs/OLYMPUS_DESIGN.md "Themes"): every theme on the pages that matter, at 390 x 844.

    python -X utf8 tools/theme_shots.py --site <built site> --out docs/shots/themes [--themes agora,ivory] [--pages gate,jarvis] [--raw <dir>]

<built site> = python tools/build_web_dashboard.py --out <dir> (only its data: data.json, home.json, runs/ ...; every app file is served
from this working tree, so the shots show the code as it is now). One JPEG per theme: <out>/<theme>.jpg (--ext png for PNG), the pages side by side
(Gate, the Gate's Look row, dashboard, Jarvis, NQ, Kalshi, Helios, Polis), each shot 390 x 844 at 1x. --raw keeps the full-size single shots too.
Read only: every request off the local origin is refused; the theme is set through localStorage 'olympus.theme' like the owner's pick.
Run browser work under: flock -w 2400 /tmp/olympus_browser.lock python -X utf8 tools/theme_shots.py ...

THE LOOK QA MATRIX (2026-11-14, team T2 "lock down the looks"; docs/OLYMPUS_DESIGN.md "Look QA"):
    python -X utf8 tools/theme_shots.py --qa --site <built site> --out docs/shots/themes_v2/after [--themes ...] [--pages ...] [--raw <dir>]
    python -X utf8 tools/theme_shots.py --table docs/shots/themes_v2/before docs/shots/themes_v2/after     the QA table (qa.md) from two runs
Every look (32 + the default) on every page that matters (the home, the nine hubs, the dashboard's six tabs, Jarvis, NQ, Aegis, Helios,
Kalshi, Mint, Oikos, Ledger, Planner, Polis, Cities, Symposium) at 390 x 844, and the home + the dashboard at 1440 x 900. The look is
picked the owner's way (OLYMPUS_THEMES.set on a page of the site), in ONE browser tab for the whole run, so every page also opens after
another look was its last (the stale copy a page keeps). Per page (tools/theme_qa.js, evaluated in the page):
  text      every visible text node vs its real background (the layers under it composited, gradient stops, translucency, the parents'
            opacity): WCAG AA (4.5:1, large text 3:1); the ones on screen are measured again on the screenshot's own pixels and only a
            failure there counts (canvas, images and blur are what the eye sees)
  left      leftovers: a visible element (or ::before / ::after) still in one of AGORA's literal colours (every fallback of a theme slot,
            and every warm brown / gold literal not yet tokenized) while the look should repaint it
  money     +$ green and -$ red: the right hue and readable
  frame     the theme-color meta (the iPhone's status bar) = the look's page colour, color-scheme, ::selection, scrollbar, placeholders
  first     the first painted frame already wears the look (no flash of AGORA or of the look picked before)
  focus     a keyboard Tab: the ring shows (outline or ring shadow) at 3:1 against what is under it
One JSON per look (<out>/<look>.json) and a contact sheet per look (<out>/<look>.jpg: every page in a grid). --live adds the storage-event
check (another tab picks a look: every open page repaints without a reload) and --mixcheck the mix (a look per hub reaches each hub page
and the apps filed under it).
"""
from __future__ import annotations

import argparse
import functools
import http.server
import json
import os
import subprocess
import sys
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
WEB = os.path.join(ROOT, "tools", "web_public")
PAGES = [("gate", "gate/", "Gate"), ("look", "gate/", "Gate: Look row"), ("dash", "", "Dashboard"), ("jarvis", "jarvis/", "Jarvis"), ("nq", "nq/?demo=1", "NQ"),
         ("kalshi", "kalshi/", "Kalshi"), ("helios", "helios/?demo=1", "Helios"), ("polis", "polis/?demo=1", "Polis"), ("mint", "mint/?demo=1", "Mint (Money)")]
# the Gate's three ready-made mixes (gate/gate.js COMBOS): --mix trader | luxury | clean
MIXES = {"trader": {"trading": "amber", "money": "stocks", "life": "forest", "worlds": "aurora"},
         "luxury": {"trading": "noir", "money": "royal", "life": "rosegold", "worlds": "sunset"},
         "clean": {"trading": "stocks", "money": "ivory", "life": "ivory", "worlds": "midnight"}}


def _catalog():
    js = ("const g={};require('vm').runInNewContext(require('fs').readFileSync(process.argv[1],'utf8'),{window:g,module:{}});const C=g.OLYMPUS_GATE;"
          "process.stdout.write(JSON.stringify({apps:C.apps.map(a=>[a.id,a.hub||a.district]),hubs:(C.hubs||[]).map(h=>[h.id,h.legacy||''])}))")
    out = subprocess.run(["node", "-e", js, os.path.join(WEB, "olympus", "gate-catalog.js")], capture_output=True, text=True, timeout=30)
    return json.loads(out.stdout)


def of_map():
    """app -> district (the hub, IA v2), from olympus/gate-catalog.js (what the Gate saves with a mix), + each hub page ('hub-<id>')"""
    c = _catalog()
    o = {"today": c["hubs"][0][0] if c["hubs"] else "trading"}
    for aid, d in c["apps"]:
        if d not in ("start", "workshop"):
            o[aid] = d
    for hid, _ in c["hubs"]:
        o["hub-" + hid] = hid
    return o


def mix_districts(combo):
    """a combo written per v1 district, as the Gate saves it: each hub takes its legacy district's look (gate.js comboOf)"""
    c = _catalog()
    return {hid: combo.get(hid) or combo.get(leg) for hid, leg in c["hubs"] if combo.get(hid) or combo.get(leg)} if c["hubs"] else dict(combo)


def theme_ids():
    js = ("const fs=require('fs'),vm=require('vm'),w={addEventListener(){}};vm.runInNewContext(fs.readFileSync(process.argv[1],'utf8'),{window:w,"
          "document:{documentElement:{style:{setProperty(){},removeProperty(){},getPropertyValue(){return ''}},setAttribute(){}},body:null,addEventListener(){},"
          "querySelector(){return null}},localStorage:{getItem(){return null},setItem(){},removeItem(){}}});"
          "process.stdout.write(JSON.stringify(w.OLYMPUS_THEMES.list().map(t=>[t.id,t.name])))")
    out = subprocess.run(["node", "-e", js, os.path.join(WEB, "olympus", "themes.js")], capture_output=True, text=True, timeout=30)
    return json.loads(out.stdout)


def serve(site, virtual=None):
    """the working tree's web_public, then the built site's data; virtual = { '/path': (bytes, content type) } answered as files"""
    virtual = virtual or {}

    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def end_headers(self):
            self.send_header("Cache-Control", "no-store")
            super().end_headers()

        def send_head(self):
            v = virtual.get(self.path.split("?")[0])
            if v is None:
                return super().send_head()
            import io
            self.send_response(200)
            self.send_header("Content-Type", v[1])
            self.send_header("Content-Length", str(len(v[0])))
            self.end_headers()
            return io.BytesIO(v[0])

        def translate_path(self, path):
            here = http.server.SimpleHTTPRequestHandler.translate_path(self, path)       # under WEB
            if os.path.exists(here) or not site:
                return here
            rel = os.path.relpath(here, WEB)
            return os.path.join(site, rel)                                                 # the built site's data (data.json, home.json, runs/)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(H, directory=WEB))
    srv.handle_error = lambda *a: None
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


LEFT = os.path.join(ROOT, "tools", "theme_leftovers.js")


def shoot(br, origin, theme, key, path, raw, leftovers=False, mix=None):
    ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1, is_mobile=True, has_touch=True, service_workers="block",
                         reduced_motion="reduce")
    ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith(origin) else r.abort())
    ctx.add_init_script("try { sessionStorage.setItem('jarvis.booted', '1'); localStorage.setItem('jarvis.seen', JSON.stringify('j9'));"
                        " localStorage.setItem('jarvis.intro', 'off'); localStorage.setItem('olympus.intro', 'off'); localStorage.setItem('olympus.theme.v', '2');"
                        f" localStorage.setItem('olympus.theme', {json.dumps(theme)});"
                        + (f" localStorage.setItem('olympus.themeMix', {json.dumps(json.dumps(mix))});" if mix else "") + " } catch (e) {}")
    p = ctx.new_page()
    p.set_default_timeout(60000)
    errs: list = []
    p.on("pageerror", lambda e: errs.append(str(e)))
    try:
        p.goto(f"{origin}/{path}", wait_until="load")
        if key == "jarvis":
            p.wait_for_function("document.documentElement.dataset.ready === '1'", timeout=60000)
        p.wait_for_timeout(3500 if key in ("jarvis", "dash", "kalshi") else 2200)
        if key == "look":                                                  # the Gate scrolled to its Look row (the theme picker)
            p.evaluate("() => { const s = document.getElementById('lookSec'); if (s) s.scrollIntoView({ block: 'center' }); }")
            p.wait_for_timeout(400)
        f = os.path.join(raw, f"{'mix' if mix else theme}-{key}.png")
        p.screenshot(path=f)
        if leftovers:
            left = p.evaluate("(a) => (" + open(LEFT, encoding="utf-8").read() + ")(a)", {"max": 25})
            for x in left:
                print(f"    leftover {theme}/{key}: {x['sel']} {x['prop']}={x['value']} '{x['text']}'  <- {x['rule']}")
        return f, errs
    finally:
        ctx.close()


def sheet(files, labels, out, title, sw=390, sh=844):
    from PIL import Image, ImageDraw, ImageFont
    pad, top, scale = 14, 56, 0.62
    w, h = int(sw * scale), int(sh * scale)
    im = Image.new("RGB", (pad + len(files) * (w + pad), top + h + pad), (24, 24, 26))
    dr = ImageDraw.Draw(im)
    try:
        f1 = ImageFont.truetype("DejaVuSans-Bold.ttf", 22)
        f2 = ImageFont.truetype("DejaVuSans.ttf", 14)
    except OSError:
        f1 = f2 = ImageFont.load_default()
    dr.text((pad, 12), title, fill=(240, 240, 240), font=f1)
    for i, (fp, lab) in enumerate(zip(files, labels)):
        x = pad + i * (w + pad)
        dr.text((x, top - 20), lab, fill=(200, 200, 200), font=f2)
        im.paste(Image.open(fp).convert("RGB").resize((w, h), Image.LANCZOS), (x, top))
    if out.endswith(".jpg"):
        im.save(out, quality=84, optimize=True, progressive=True)
    else:
        im.save(out, optimize=True)


def stack(files, out):
    """the per-theme sheets one under another (the before / after overview)"""
    from PIL import Image
    ims = [Image.open(f).convert("RGB") for f in files]
    w, h = max(i.width for i in ims), sum(i.height for i in ims)
    big = Image.new("RGB", (w, h), (24, 24, 26))
    y = 0
    for i in ims:
        big.paste(i, (0, y))
        y += i.height
    big = big.resize((w * 3 // 4, h * 3 // 4), Image.LANCZOS)
    big.save(out, quality=80, optimize=True, progressive=True)


# ================================================================================================ the look QA matrix (2026-11-14, team T2)
QA_JS = os.path.join(ROOT, "tools", "theme_qa.js")
GATE_Q = "?now=2026-11-12T15:00:00Z"
HUBS = ["today", "bots", "kalshi", "money", "plan", "research", "jarvis", "worlds", "settings"]
HUB_NAMES = {"today": "Today", "bots": "Bots & Evals", "kalshi": "Kalshi", "money": "My Money", "plan": "Plan & Day", "research": "Research", "jarvis": "Jarvis",
             "worlds": "Worlds", "settings": "Settings & Help"}
DASH_TABS = [("home", "mission", "Home"), ("zlarior", "lit", "Zlarior"), ("atlas", "atlas", "ATLAS"), ("blitz", "blitz", "BLITZ"), ("money", "real", "Money"), ("more", "system", "More")]
APPS_QA = [("jarvis", "jarvis/", "Jarvis"), ("nq", "nq/?demo=1", "NQ"), ("aegis", "aegis/?demo=1", "Aegis"), ("helios", "helios/?demo=1", "Helios"),
           ("kalshi", "kalshi/", "Kalshi"), ("mint", "mint/?demo=1", "Mint"), ("oikos", "oikos/?demo=1", "Oikos"), ("ledger", "ledger/?demo=1", "Ledger"),
           ("planner", "planner/?demo=1", "Planner"), ("polis", "polis/?demo=1", "Polis"), ("cities", "cities/?demo=1", "Cities"), ("symposium", "symposium/?demo=1", "Symposium")]
# (key, path, label, viewport)
MATRIX = ([("home", "gate/" + GATE_Q, "Home", "phone")] + [(f"hub-{h}", f"hub/index.html?h={h}", f"Hub: {HUB_NAMES[h]}", "phone") for h in HUBS]
          + [(f"dash-{k}", f"index.html#/{r}", f"Dashboard: {lab}", "phone") for k, r, lab in DASH_TABS]
          + [(k, p, lab, "phone") for k, p, lab in APPS_QA]
          + [("home-desk", "gate/" + GATE_Q, "Home 1440", "desk"), ("dash-desk", "index.html#/mission", "Dashboard 1440", "desk")])
VIEW = {"phone": dict(viewport={"width": 390, "height": 844}, device_scale_factor=1, is_mobile=True, has_touch=True),
        "desk": dict(viewport={"width": 1440, "height": 900}, device_scale_factor=1)}
BOOT = ("try { sessionStorage.setItem('jarvis.booted', '1'); localStorage.setItem('jarvis.seen', JSON.stringify('j9')); localStorage.setItem('jarvis.intro', 'off');"
        " localStorage.setItem('olympus.intro', 'off'); localStorage.setItem('olympus.theme.v', '2'); } catch (e) {}")
# the first painted frame: what the page wore then (the look attribute, the page colour), and every later change of the look attribute
FIRST = """(() => { const rec = window.__olyQAPaint = { first: null, changes: [] }, d = document;
  const snap = () => { const r = d.documentElement; if (!r) return null; const cs = getComputedStyle(r), b = d.body ? getComputedStyle(d.body) : null;
    return { t: Math.round(performance.now()), theme: r.getAttribute('data-oly-theme'), style: r.getAttribute('data-oly-style'), html: cs.backgroundColor, img: (cs.backgroundImage || '').slice(0, 60),
      body: b ? b.backgroundColor : null, ink: b ? b.color : cs.color }; };
  requestAnimationFrame(() => { rec.first = snap(); });
  try { new MutationObserver((m) => { for (const x of m) if (x.attributeName === 'data-oly-theme' && x.target === d.documentElement)
    rec.changes.push({ t: Math.round(performance.now()), v: d.documentElement.getAttribute('data-oly-theme'), afterFirst: !!rec.first }); })
    .observe(d, { attributes: true, subtree: true, attributeFilter: ['data-oly-theme'] }); } catch (e) { /* old engine */ }
})();"""
SET_PAGE = b"<!doctype html><meta charset=utf-8><title>qa</title><script src=\"/olympus/themes.js\"></script><body>look picker stand-in</body>"


def agora_palette():
    """AGORA's own literal colours, as 'r,g,b': every fallback of a theme slot in the site's sheets and scripts (what the tokenizer replaced),
    the engine's AGORA reference ramp, and every warm brown / gold literal of the app sheets the tokenizer has not reached yet"""
    import glob
    import re
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import theme_tokenize as TOK
    out, rx_hex, rx_tri = set(), re.compile(r"var\(--oly-th-[\w-]+, (#[0-9a-fA-F]{6}|#[0-9a-fA-F]{3})\)"), re.compile(r"var\(--oly-th-[\w-]+-rgb, (\d{1,3}),\s*(\d{1,3}),\s*(\d{1,3})\)")
    hexes = re.compile(r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})(?![0-9a-fA-F\w-])")
    skip = ("three", "fx.js", "holocore", "/vendor/", "three-addons", ".min.js", "people-data", "athens", "hellas", "metropolis")

    def rgb(h):
        h = h.lstrip("#")
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    for fp in glob.glob(os.path.join(WEB, "**", "*.*"), recursive=True):
        if not fp.endswith((".css", ".html", ".js")) or any(k in fp for k in skip) or os.path.getsize(fp) > 900_000:
            continue
        try:
            txt = open(fp, encoding="utf-8").read()
        except (OSError, UnicodeDecodeError):
            continue
        for m in rx_hex.finditer(txt):
            out.add(rgb(m.group(1)))
        for m in rx_tri.finditer(txt):
            out.add(tuple(int(m.group(i)) for i in (1, 2, 3)))
        if fp.endswith(".css"):                                   # app sheets not tokenized yet: their warm browns / golds are AGORA's too
            body = TOK.untokenize(txt)
            for m in hexes.finditer(re.sub(r"/\*.*?\*/", "", body, flags=re.S)):
                r, g, b = rgb(m.group(1))
                sl = TOK.slot(r, g, b, "naw")
                if sl and (sl[0] == "a" or sl == "warn" or (r > b + 4)):
                    out.add((r, g, b))
    for fam in ("#14110e #1d1914 #26211b #3a3228 #a89c88 #cfc4b2 #f3ece0 #3b2c1e #9c6b3c #c8a24a #dcbd6e #f5e6c4 #7f8a52 #a0ac6e #c96a4a #e08a6b #e0b060").split():
        out.add(rgb(fam))
    out.discard((0, 0, 0))
    out.discard((255, 255, 255))
    return sorted(",".join(map(str, c)) for c in out)


def kalshi_feed():
    """a kalshi.json for the Kalshi page (the publisher's own sample, fresh): the site build has none"""
    import time
    try:
        from engine import kalshi_publish as kp
        now = time.time()
        raw = dict(getattr(kp, "SAMPLE_V3", None) or getattr(kp, "SAMPLE_V2", None) or kp.SAMPLE)
        raw["t"] = int(now) - 60
        return json.dumps(kp.clean(raw, now)).encode()
    except Exception as e:                                       # the page then shows its own "could not reach the feed" state
        print("kalshi sample:", e)
        return None


def dominant(arr):
    """the colour most of a box shows (its background): the most common colour, quantised, then averaged inside that bin"""
    import numpy as np
    px = arr.reshape(-1, 3)
    if not len(px):
        return None
    q = (px >> 3).astype(np.int32)
    key = (q[:, 0] << 10) | (q[:, 1] << 5) | q[:, 2]
    vals, counts = np.unique(key, return_counts=True)
    k = vals[counts.argmax()]
    return px[key == k].mean(axis=0).tolist()


def _lum(c):
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    return 0.2126 * ch(c[0]) + 0.7152 * ch(c[1]) + 0.0722 * ch(c[2])


def _ratio(a, b):
    x, y = _lum(a), _lum(b)
    return (max(x, y) + 0.05) / (min(x, y) + 0.05)


def _hexrgb(h):
    h = h.lstrip("#")
    return [int(h[i:i + 2], 16) for i in (0, 2, 4)]


def pixel_check(png, rows, vw, vh):
    """the text rows on screen, measured on the screenshot: (fails, checked). A row passes when its ink over the background its box
    mostly shows reaches its need; covered rows (top == False) are skipped."""
    import numpy as np
    from PIL import Image
    im = np.asarray(Image.open(png).convert("RGB")).astype(np.int32)
    H, W = im.shape[:2]
    fails, n = [], 0
    for r in rows:
        if not r.get("top"):
            continue
        x, y, w, h = r["box"]
        x0, y0, x1, y1 = max(0, x), max(0, y), min(W, x + w), min(H, y + h)
        if x1 - x0 < 2 or y1 - y0 < 2:
            continue
        fg = _hexrgb(r["fg"])
        box = im[y0:y1, x0:x1].reshape(-1, 3)
        # the background is what the box shows besides the ink: pixels near the text colour (the glyphs) are left out first, so a bold
        # title on a textured or gradient card is not read as text on itself; a box that is ALL ink-coloured (truly invisible text) stays
        far = box[((box - np.array(fg)) ** 2).sum(axis=1) > 30 ** 2]
        bg = dominant(far if len(far) >= 0.1 * len(box) else box)
        if bg is None:
            continue
        a = r.get("a", 1)
        ink = [fg[i] * a + bg[i] * (1 - a) for i in range(3)]
        v = _ratio(ink, bg)
        n += 1
        if v < r["need"]:
            fails.append(dict(r, px=round(v, 2), pxbg="#%02x%02x%02x" % tuple(int(c) for c in bg)))
    return fails, n


def top_colour(png):
    import numpy as np
    from PIL import Image
    im = np.asarray(Image.open(png).convert("RGB"))
    return [int(c) for c in np.median(im[0:3, :, :].reshape(-1, 3), axis=0)]


def settle(p, key, first_dash):
    """wait until the page has drawn what the owner sees"""
    try:
        if key == "jarvis":
            p.wait_for_function("document.documentElement.dataset.ready === '1'", timeout=60000)
            p.wait_for_timeout(2500)
        elif key.startswith("dash"):
            if first_dash:
                p.wait_for_function("() => !document.querySelector('#page > .skel')", timeout=30000)
            p.wait_for_timeout(1800 if first_dash else 1300)
        elif key.startswith("home"):
            p.wait_for_function("() => window.GATE && window.GATE.ready()", timeout=30000)
            p.wait_for_timeout(500)
        elif key.startswith("hub"):
            p.wait_for_function("() => window.HUB && window.HUB.ready()", timeout=30000)
            p.wait_for_timeout(500)
        elif key == "kalshi":
            p.wait_for_function("() => { const b = document.getElementById('body'); return b && b.dataset.state && b.dataset.state !== 'loading'; }", timeout=30000)
            p.wait_for_timeout(700)
        else:
            p.wait_for_function("() => document.documentElement.hasAttribute('data-oly-theme')", timeout=30000)
            p.wait_for_timeout(2600 if key in ("cities", "symposium", "polis", "nq", "aegis", "helios") else 1600)
    except Exception as e:                                        # still measured: the report says it did not settle
        return str(e)[:160]
    return ""


def set_look(p, origin, look, mix=None):
    """the owner's way: the engine's own set() / setMix() on a page of the site (so the engine does what a pick does)"""
    p.goto(origin + "/__qa/set.html", wait_until="load")
    p.evaluate("([id, mix]) => { const T = window.OLYMPUS_THEMES; T.set(id); if (mix) T.setMix(mix); }", [look, mix])


# the overlays a page can open (name, open, the scope to check, close): the gate-nav "Go to" sheet, an AGORA toast, an AGORA sheet
OVERLAYS = [
    ("goto-sheet", "() => { if (window.OLYMPUS_GATE_NAV) OLYMPUS_GATE_NAV.open(); }", ".gn-sheet", "() => { if (window.OLYMPUS_GATE_NAV) OLYMPUS_GATE_NAV.close(); }"),
    ("toast", "() => { if (window.AGORA && AGORA.toast) AGORA.toast('Saved. +$312 won, -$60 lost today.', { kind: 'ok', ms: 6000 }); }", ".ag-toast", ""),
    ("sheet", "() => { if (!window.AGORA || !AGORA.sheet) return; const b = document.createElement('p'); b.textContent = 'Drawdown left $1,420 of $2,000. +$312 won, -$60 lost.';"
     " window.__qaSheet = AGORA.sheet({ title: 'A sheet', body: b }); }", ".ag-sheet", "() => { if (window.__qaSheet) window.__qaSheet.close(); }"),
]
OVERLAY_PAGES = ("nq", "mint", "hub-money")


def overlays(p, src, raw, look, key, agora):
    """open each overlay, check what is inside it (its text on its own pixels, AGORA leftovers), close it: { name: {...} }"""
    out = {}
    for name, opener, scope, closer in OVERLAYS:
        try:
            p.evaluate(opener)
            p.wait_for_timeout(450)
            if not p.evaluate("(s) => !!document.querySelector(s)", scope):
                continue
            shot = os.path.join(raw, f"{look}-{key}-{name}.png")
            p.screenshot(path=shot)
            rep = p.evaluate("(a) => (" + src + ")(a)", {"agora": agora if look != "agora" else [], "max": 12, "scope": scope + ", " + scope + " *"})
            fails, n = pixel_check(shot, rep["texts"], 390, 844)
            out[name] = {"n": n, "lowPx": fails[:6], "left": rep["left"][:6], "ok": not fails and not rep["left"]}
            if closer:
                p.evaluate(closer)
            p.wait_for_timeout(300)
            os.remove(shot)
        except Exception as e:
            out[name] = {"ok": False, "error": str(e)[:160]}
    return out


def qa_page(p, origin, key, path, raw, look, agora, focus=True, first_dash=True, screens=2):
    errs: list = []
    on_err = lambda e: errs.append(str(e)[:200])        # noqa: E731
    p.on("pageerror", on_err)
    src = open(QA_JS, encoding="utf-8").read()
    try:
        if key.startswith("dash") and not first_dash:
            p.evaluate("(h) => { location.hash = h; }", "#" + path.split("#", 1)[1])
        else:
            p.goto(f"{origin}/{path}", wait_until="load")
        slow = settle(p, key, first_dash)
        p.evaluate("() => window.scrollTo(0, 0)")
        p.wait_for_timeout(150)
        vw, vh = p.viewport_size["width"], p.viewport_size["height"]
        shot = os.path.join(raw, f"{look}-{key}.png")
        p.screenshot(path=shot)
        rep = p.evaluate("(a) => (" + src + ")(a)", {"agora": agora if look != "agora" else [], "max": 40})          # the default: AGORA is its own colour
        fails, checked = pixel_check(shot, rep["texts"], vw, vh)
        below = [r for r in rep["low"] if r.get("top") is None and r["box"][1] >= vh and not r.get("unsure")]
        for s in range(1, screens):                               # the next screen down: measured on its own pixels too
            if rep["h"] <= vh * s + 40:
                break
            p.evaluate("(y) => window.scrollTo(0, y)", int(vh * 0.92 * s))
            p.wait_for_timeout(350)
            shot2 = os.path.join(raw, f"{look}-{key}-s{s + 1}.png")
            p.screenshot(path=shot2)
            r2 = p.evaluate("(a) => (" + src + ")(a)", {"agora": [], "max": 10})
            f2, c2 = pixel_check(shot2, r2["texts"], vw, vh)
            seen = {(x["sel"], x["text"]) for x in fails}
            fails += [x for x in f2 if (x["sel"], x["text"]) not in seen]
            checked += c2
            shown = {(x["sel"], x["text"]) for x in r2["texts"] if x.get("top") is not None}
            below = [r for r in below if (r["sel"], r["text"]) not in shown and r["box"][1] >= vh * (0.92 * s + 1)]
            os.remove(shot2)
            p.evaluate("() => window.scrollTo(0, 0)")
            p.wait_for_timeout(120)
        rings = []
        if focus:
            for _ in range(3):
                p.keyboard.press("Tab")
                p.wait_for_timeout(60)
                f = p.evaluate("() => window.__olyQA && window.__olyQA.focus()")
                if f:
                    rings.append(f)
            p.evaluate("() => { try { document.activeElement && document.activeElement.blur(); } catch (e) {} window.scrollTo(0, 0); }")
        ov = overlays(p, src, raw, look, key, agora) if key in OVERLAY_PAGES else {}
        top = top_colour(shot)
        rep.pop("texts", None)
        first = rep.get("first") or {}
        fr = first.get("first") or {}
        flash = ""
        if not (key.startswith("dash") and not first_dash):
            want = rep["theme"] or "agora"
            got = fr.get("theme") or "agora"
            if fr and got != want:
                flash = f"first frame wore {got}, then {want}"
            elif not fr:
                flash = "no frame recorded"
        meta_ok = True
        if look != "agora" and rep.get("meta"):
            mc = _hexrgb(rep["meta"]) if rep["meta"].startswith("#") and len(rep["meta"]) == 7 else None
            meta_ok = bool(mc) and sum((mc[i] - top[i]) ** 2 for i in range(3)) ** 0.5 < 60 and rep["meta"].lower() != "#14110e"
        res = {"key": key, "path": path, "theme": rep["theme"], "style": rep["style"], "scheme": rep["scheme"], "colorScheme": rep["colorScheme"], "meta": rep["meta"],
               "top": "#%02x%02x%02x" % tuple(top), "selection": rep["selection"], "scrollbar": rep["scrollbar"], "nTexts": rep["nTexts"], "checkedPx": checked,
               "lowPx": fails[:25], "nLowPx": len(fails), "lowBelow": below[:15], "nLowBelow": len(below), "left": rep["left"], "money": rep["money"],
               "placeholders": [x for x in rep["placeholders"] if x["ratio"] < 4.5], "first": first, "flash": flash, "focus": rings, "sx": rep["sx"],
               "errors": errs[:4], "slow": slow, "shot": shot, "overlays": ov}
        res["verdict"] = {
            "text": not fails and not below,
            "left": not rep["left"],
            "money": not rep["money"]["wrong"],                  # +$ in green, -$ in red (their readability is the text check)
            "frame": meta_ok and rep["sx"] <= 0,
            "first": not flash,
            "focus": all(f["ok"] for f in rings) if rings else True,
            "overlay": all(x.get("ok") for x in ov.values()),
        }
        return res
    except Exception as e:
        return {"key": key, "path": path, "error": str(e)[:400], "errors": errs[:4], "verdict": {"load": False}}
    finally:
        p.remove_listener("pageerror", on_err)


def run_matrix(br, origin, looks, pages, out, raw, agora, focus=True, screens=2, log=print):
    """every look on every page in one tab per viewport (the look picked the owner's way between looks); one JSON + one sheet per look"""
    import time
    ctxs, pp = {}, {}
    for v in ("phone", "desk"):
        if any(x[3] == v for x in pages):
            c = br.new_context(service_workers="block", reduced_motion="reduce", **VIEW[v])
            c.route("**/*", lambda r: r.continue_() if r.request.url.startswith(origin) else r.abort())
            c.add_init_script(BOOT)
            c.add_init_script(FIRST)
            ctxs[v] = c
            pp[v] = c.new_page()
            pp[v].set_default_timeout(60000)
    for tid, name in looks:
        t0 = time.time()
        for v in pp:
            set_look(pp[v], origin, tid)
        res, last = {}, {}
        for key, path, label, v in pages:
            first_dash = not (key.startswith("dash") and last.get(v, "").startswith("dash") and v == "phone")
            r = qa_page(pp[v], origin, key, path, raw, tid, agora, focus=focus and v == "phone", first_dash=first_dash, screens=screens if v == "phone" else 1)
            last[v] = key
            r["label"] = label
            r["view"] = v
            res[key] = r
            bad = [k for k, ok in r.get("verdict", {}).items() if not ok]
            if bad:
                log(f"  {tid:10s} {key:14s} " + ", ".join(bad) + _why(r))
        json.dump({"look": tid, "name": name, "pages": res}, open(os.path.join(out, f"{tid}.json"), "w", encoding="utf-8"), indent=1)
        grid_sheet([res[k[0]].get("shot") for k in pages], [k[2] for k in pages], [k[3] for k in pages],
                   [not [x for x, ok in res[k[0]].get("verdict", {}).items() if not ok] for k in pages], os.path.join(out, f"{tid}.jpg"), f"{name}  ({tid})")
        log(f"{tid}: {sum(1 for r in res.values() if all(r.get('verdict', {}).values()))}/{len(res)} pages clean in {time.time() - t0:.0f}s")
    for c in ctxs.values():
        c.close()


def _why(r):
    if r.get("error"):
        return "  (" + r["error"][:120] + ")"
    bits = []
    if r.get("nLowPx") or r.get("nLowBelow"):
        x = (r.get("lowPx") or r.get("lowBelow"))[0]
        bits.append(f"text {r.get('nLowPx', 0)}+{r.get('nLowBelow', 0)} e.g. {x['sel'][-40:]} '{x['text'][:18]}' {x['fg']} on {x.get('pxbg', x['bg'])} {x.get('px', x['ratio'])}")
    if r.get("left"):
        x = r["left"][0]
        bits.append(f"left {len(r['left'])} e.g. {x['sel'][-40:]} {x['prop']}={x['value'][:40]}")
    m = r.get("money") or {}
    if m.get("wrong") or m.get("low"):
        x = (m.get("wrong") or m.get("low"))[0]
        bits.append(f"money {len(m.get('wrong', []))}/{len(m.get('low', []))} e.g. '{x['text']}' {x['color']}")
    if r.get("flash"):
        bits.append("flash: " + r["flash"])
    if not r.get("verdict", {}).get("frame", True):
        bits.append(f"frame meta {r.get('meta')} vs top {r.get('top')} sx {r.get('sx')}")
    if not r.get("verdict", {}).get("focus", True):
        f = [x for x in r.get("focus", []) if not x["ok"]][0]
        bits.append(f"focus {f['sel'][-30:]} {f['kind']} {f['color']} {f['ratio']}")
    for n, o in (r.get("overlays") or {}).items():
        if not o.get("ok"):
            bits.append(f"overlay {n}: " + str((o.get("lowPx") or o.get("left") or [o.get("error")])[0])[:120])
    return "  (" + "; ".join(bits) + ")"


def grid_sheet(files, labels, views, oks, out, title, scale=0.36):
    """one look on every page: phone shots in rows, the 1440 shots after them; a red label = an issue on that page"""
    from PIL import Image, ImageDraw, ImageFont
    pw, ph = int(390 * scale), int(844 * scale)
    dw, dh = int(1440 * scale * 0.5), int(900 * scale * 0.5)
    pad, lab, top, cols = 8, 16, 40, 10
    tiles = list(zip(files, labels, views, oks))
    ph_t = [t for t in tiles if t[2] == "phone"]
    dk_t = [t for t in tiles if t[2] != "phone"]
    rows = (len(ph_t) + cols - 1) // cols
    W = pad + cols * (pw + pad)
    H = top + rows * (ph + lab + pad) + ((dh + lab + pad) if dk_t else 0) + pad
    im = Image.new("RGB", (W, H), (24, 24, 26))
    dr = ImageDraw.Draw(im)
    try:
        f1 = ImageFont.truetype("DejaVuSans-Bold.ttf", 18)
        f2 = ImageFont.truetype("DejaVuSans.ttf", 10)
    except OSError:
        f1 = f2 = ImageFont.load_default()
    dr.text((pad, 10), title, fill=(240, 240, 240), font=f1)
    for i, (f, lb, v, ok) in enumerate(ph_t):
        x, y = pad + (i % cols) * (pw + pad), top + (i // cols) * (ph + lab + pad)
        dr.text((x, y), lb[:26], fill=(170, 220, 170) if ok else (255, 120, 110), font=f2)
        if f and os.path.exists(f):
            im.paste(Image.open(f).convert("RGB").resize((pw, ph), Image.LANCZOS), (x, y + lab))
    y = top + rows * (ph + lab + pad)
    for i, (f, lb, v, ok) in enumerate(dk_t):
        x = pad + i * (dw + pad)
        dr.text((x, y), lb[:40], fill=(170, 220, 170) if ok else (255, 120, 110), font=f2)
        if f and os.path.exists(f):
            im.paste(Image.open(f).convert("RGB").resize((dw, dh), Image.LANCZOS), (x, y + lab))
    im.save(out, quality=74, optimize=True, progressive=True)


def live_check(br, origin, pages, a="midnight", b="ivory", log=print):
    """another tab picks a look: every open page repaints at once, no reload (the storage event); then back"""
    ctx = br.new_context(service_workers="block", reduced_motion="reduce", **VIEW["phone"])
    ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith(origin) else r.abort())
    ctx.add_init_script(BOOT)
    p, q = ctx.new_page(), ctx.new_page()
    set_look(q, origin, a)
    out = {}
    for key, path, label, v in pages:
        if v != "phone" or (key.startswith("dash") and key != "dash-home"):
            continue
        try:
            p.goto(f"{origin}/{path}", wait_until="load")
            settle(p, key, True)
            js = "() => [document.documentElement.dataset.olyTheme, getComputedStyle(document.body).backgroundColor, getComputedStyle(document.documentElement).backgroundColor]"
            before = p.evaluate(js)
            q.evaluate("(id) => window.OLYMPUS_THEMES.set(id)", b)
            try:
                p.wait_for_function("(id) => document.documentElement.dataset.olyTheme === id", arg=b, timeout=4000)
            except Exception:
                pass
            p.wait_for_timeout(400)
            after = p.evaluate(js)
            q.evaluate("(id) => window.OLYMPUS_THEMES.set(id)", a)
            try:
                p.wait_for_function("(id) => document.documentElement.dataset.olyTheme === id", arg=a, timeout=4000)
            except Exception:
                pass
            p.wait_for_timeout(300)
            back = p.evaluate(js)
            ok = after[0] == b and (after[1] != before[1] or after[2] != before[2]) and back[0] == a
            out[key] = {"ok": ok, "before": before, "after": after, "back": back}
            if not ok:
                log(f"  live {key}: {before} -> {after} -> {back}")
        except Exception as e:
            out[key] = {"ok": False, "error": str(e)[:200]}
            log(f"  live {key}: {str(e)[:160]}")
    ctx.close()
    return out


MIX_LOOKS = {"today": "amber", "bots": "terminal", "kalshi": "stocks", "money": "ivory", "plan": "forest", "research": "nord", "jarvis": "royal", "worlds": "aurora", "settings": "zen"}
MIX_PROBE = {"today": "helios/?demo=1", "bots": "nq/?demo=1", "kalshi": "kalshi/", "money": "mint/?demo=1", "plan": "planner/?demo=1", "research": "symposium/?demo=1",
             "jarvis": "jarvis/", "worlds": "cities/?demo=1", "settings": "settings/"}


def mix_check(br, origin, log=print):
    """a look per hub (the Gate's Mix): each hub page and an app filed under it open in their hub's look"""
    of = of_map()
    ctx = br.new_context(service_workers="block", reduced_motion="reduce", **VIEW["phone"])
    ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith(origin) else r.abort())
    ctx.add_init_script(BOOT)
    p = ctx.new_page()
    set_look(p, origin, "midnight", {"district": MIX_LOOKS, "app": {}, "of": of})
    out = {}
    for h, want in MIX_LOOKS.items():
        app = MIX_PROBE[h].split("/")[0]
        for kind, url, page_id in (("hub", f"hub/index.html?h={h}", "hub-" + h), ("app", MIX_PROBE[h], app)):
            try:
                p.goto(f"{origin}/{url}", wait_until="load")
                p.wait_for_function("() => document.documentElement.hasAttribute('data-oly-theme')", timeout=30000)
                p.wait_for_timeout(500)
                got = p.evaluate("() => [document.documentElement.dataset.olyTheme, (window.OLYMPUS_THEMES && OLYMPUS_THEMES.page()) || '']")
                exp = MIX_LOOKS.get(of.get(page_id, ""), "midnight")
                out[f"{h}:{kind}"] = {"ok": got[0] == exp, "want": exp, "got": got[0], "page": got[1], "url": url, "filed": of.get(page_id)}
                if got[0] != exp:
                    log(f"  mix {h} {kind} {url}: wanted {exp}, got {got}")
            except Exception as e:
                out[f"{h}:{kind}"] = {"ok": False, "error": str(e)[:200], "url": url}
                log(f"  mix {h} {kind} {url}: {str(e)[:160]}")
    ctx.close()
    return out


SHORT = {"text": "contrast", "left": "AGORA leftover", "money": "+$/-$", "frame": "status bar", "first": "flash", "focus": "focus ring", "overlay": "sheet/toast",
         "load": "load"}
ART_SEL = ("svg.s2d", "pp-portrait")                         # scene art: its own colours, like a 3D canvas (not a leftover)


def look_issues(r, base=None):
    """the issues of one page under one look that the default (AGORA) does not have on the same page: {check: [what]} (empty = pass)"""
    if not r:
        return None
    if r.get("error"):
        return {"load": [r["error"][:100]]}

    def fps(x):
        out = {}
        for t in (x.get("lowPx") or []) + (x.get("lowBelow") or []):
            out.setdefault("text", {})[(t["sel"], t["text"])] = f"{t['sel'][-40:]} '{t['text'][:20]}' {t['fg']} on {t.get('pxbg', t['bg'])} {t.get('px', t['ratio'])}:1"
        for t in x.get("left") or []:
            if not any(a in t["sel"] for a in ART_SEL):
                out.setdefault("left", {})[(t["sel"], t["prop"])] = f"{t['sel'][-40:]} {t['prop']}={str(t['value'])[:40]}"
        for t in (x.get("money") or {}).get("wrong") or []:
            out.setdefault("money", {})[(t["sel"], t["text"])] = f"'{t['text']}' in {t['color']}"
        for t in x.get("focus") or []:
            if not t["ok"]:
                out.setdefault("focus", {})[(t["sel"],)] = f"{t['sel'][-40:]} {t['kind'] or 'no ring'} {t['color']} {t['ratio']}:1"
        for n, o in (x.get("overlays") or {}).items():
            if not o.get("ok"):
                out.setdefault("overlay", {})[(n,)] = n + ": " + "; ".join([f"'{t['text'][:16]}' {t.get('px')}:1" for t in o.get("lowPx", [])[:2]]
                                                                      + [f"{t['prop']}={str(t['value'])[:30]}" for t in o.get("left", [])[:2]] + [o.get("error", "")]).strip("; ")
        return out
    mine, theirs = fps(r), fps(base or {})
    out = {}
    for k, v in mine.items():
        new = [w for key, w in v.items() if key not in theirs.get(k, {})]
        if new:
            out[k] = new
    if r.get("flash"):
        out["first"] = [r["flash"]]
    # the frame: the status bar follows the look (not AGORA's #14110e under another look) and nothing scrolls sideways
    meta = str(r.get("meta") or "").lower()
    if base is not None and (meta in ("", "#14110e") or r.get("sx", 0) > 0):
        out["frame"] = [f"status bar {meta or 'missing'} (page top {r.get('top')})" + (f", {r.get('sx')} px sideways" if r.get("sx", 0) > 0 else "")]
    return out


def qa_table(before_dir, after_dir, out_md):
    """the QA table: look x page, pass / fixed / known issue (from two --qa runs; an issue the default AGORA has too on that page is the
    default's own, listed once at the end, not counted against a look: the default stays byte for byte as it is)"""
    def load(dd):
        o = {}
        if dd and os.path.isdir(dd):
            for f in sorted(os.listdir(dd)):
                if f.endswith(".json") and not f.startswith("_"):
                    j = json.load(open(os.path.join(dd, f), encoding="utf-8"))
                    o[j["look"]] = j
        return o
    B, A = load(before_dir), load(after_dir)
    looks = [t for t, _ in theme_ids() if t in A or t in B]
    keys = [k for k, *_ in MATRIX]
    labels = {k: lab for k, _, lab, _ in MATRIX}

    def page(j, k):
        return (j or {}).get("pages", {}).get(k)
    lines = ["| Look | " + " | ".join(keys) + " |", "|---|" + "---|" * len(keys)]
    tally = {"pass": 0, "fixed": 0, "known": 0, "n/a": 0}
    notes, per_check = [], {}
    for t in looks:
        row = []
        for k in keys:
            bi = look_issues(page(B.get(t), k), page(B.get("agora"), k) if t != "agora" else None)
            ai = look_issues(page(A.get(t), k), page(A.get("agora"), k) if t != "agora" else None)
            if t == "agora":                                  # the default: only what the theme work could have broken (the flash, the frame)
                ai = {c: v for c, v in (ai or {}).items() if c in ("first", "frame", "load")} if ai is not None else None
                bi = {c: v for c, v in (bi or {}).items() if c in ("first", "frame", "load")} if bi is not None else None
            if ai is None:
                row.append("n/a")
                tally["n/a"] += 1
            elif not ai:
                row.append("fixed" if bi else "pass")
                tally["fixed" if bi else "pass"] += 1
            else:
                row.append("known: " + "/".join(SHORT.get(x, x) for x in ai))
                tally["known"] += 1
                for c, v in ai.items():
                    per_check[c] = per_check.get(c, 0) + 1
                notes.append(f"- **{t} / {labels.get(k, k)}**: " + "; ".join(f"{SHORT.get(c, c)}: {v[0]}" + (f" (+{len(v) - 1} more)" if len(v) > 1 else "") for c, v in ai.items()))
        lines.append(f"| {t} | " + " | ".join(row) + " |")
    own = []
    for k in keys:                                           # the default's own issues (not the looks'): kept, the default is byte for byte as before
        ai = look_issues(page(A.get("agora"), k))
        if ai:
            own.append(f"- **{labels.get(k, k)}**: " + "; ".join(f"{SHORT.get(c, c)}: {v[0]}" + (f" (+{len(v) - 1})" if len(v) > 1 else "") for c, v in ai.items() if c not in ("left",)))
    head = (f"Look QA matrix ({len(looks)} looks x {len(keys)} pages = {len(looks) * len(keys)} cells): {tally['pass']} pass, {tally['fixed']} fixed, "
            f"{tally['known']} known issue" + (f", {tally['n/a']} not run" if tally["n/a"] else "") + ".")
    md = ("# " + head + "\n\nEach cell is one look on one page (390 x 844; `-desk` = 1440 x 900), measured by `tools/theme_shots.py --qa` (`tools/theme_qa.js`): "
          "text contrast on the page's real pixels (AA), AGORA colours left, +$ green / -$ red, the status bar, the first frame (no flash), the keyboard focus ring, "
          "and on NQ / Mint / My Money the Go to sheet, a toast and a sheet. pass = clean before and after, fixed = an issue before, clean now, "
          "known = still open (listed below). An issue the default (Agora) has on the same page is the default's own (listed last), not a look's.\n\n"
          + "\n".join(lines) + "\n\n## Known issues (" + ", ".join(f"{SHORT.get(c, c)} {n}" for c, n in sorted(per_check.items(), key=lambda x: -x[1])) + ")\n\n"
          + ("\n".join(notes) if notes else "None.") + "\n\n## The default's own issues (Agora, kept byte for byte; not part of the look work)\n\n"
          + ("\n".join(own) if own else "None.") + "\n")
    open(out_md, "w", encoding="utf-8").write(md)
    return head


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default="")
    ap.add_argument("--out", default=os.path.join(ROOT, "docs", "shots", "themes"))
    ap.add_argument("--themes", default="")
    ap.add_argument("--pages", default="")
    ap.add_argument("--raw", default="")
    ap.add_argument("--stack", default="", help="also write every sheet stacked into this one .jpg")
    ap.add_argument("--ext", default="jpg")
    ap.add_argument("--mix", default="", help="one of the Gate's combos (trader, luxury, clean): every page under that mix, one sheet")
    ap.add_argument("--leftovers", action="store_true", help="list visible elements still in AGORA's warm browns (use with a blue / green theme)")
    ap.add_argument("--qa", action="store_true", help="the look QA matrix: every look x every page that matters, checked; one JSON + one sheet per look")
    ap.add_argument("--screens", type=int, default=2, help="--qa: how many screens of each page are measured on their pixels (the rest on computed colours)")
    ap.add_argument("--no-focus", action="store_true", help="--qa: skip the keyboard focus ring check")
    ap.add_argument("--live", action="store_true", help="--qa: also the storage-event check (another tab picks a look: every open page repaints)")
    ap.add_argument("--mixcheck", action="store_true", help="--qa: also the mix check (a look per hub reaches each hub page and its apps)")
    ap.add_argument("--table", nargs=2, metavar=("BEFORE", "AFTER"), help="write <AFTER>/../qa.md: look x page, pass / fixed / known issue")
    ap.add_argument("--web", default="", help="serve this copy of tools/web_public instead of the working tree's (e.g. a commit's, for a 'before' run)")
    a = ap.parse_args()
    if a.web:
        global WEB
        WEB = os.path.abspath(a.web)
    if a.table:
        out_md = os.path.join(os.path.dirname(os.path.abspath(a.table[1])), "qa.md")
        print(qa_table(a.table[0], a.table[1], out_md), "->", out_md)
        return 0
    from playwright.sync_api import sync_playwright
    from tests import browser_kit as BK
    themes = theme_ids()
    if a.qa:
        themes = [t for t in themes if t[0] in ([x for x in a.themes.split(",") if x] or [t[0] for t in themes[:32]])]
        pages = [m for m in MATRIX if not a.pages or m[0] in a.pages.split(",")]
        os.makedirs(a.out, exist_ok=True)
        raw = a.raw or os.path.join(a.out, ".raw")
        os.makedirs(raw, exist_ok=True)
        virt = {"/__qa/set.html": (SET_PAGE, "text/html; charset=utf-8")}
        if not (a.site and os.path.exists(os.path.join(a.site, "kalshi.json"))):
            k = kalshi_feed()
            if k:
                virt["/kalshi.json"] = (k, "application/json")
        srv, origin = serve(a.site, virt)
        ag = agora_palette()
        print(f"look QA: {len(themes)} looks x {len(pages)} pages, {len(ag)} AGORA colours watched", flush=True)
        with sync_playwright() as pw:
            br = BK.launch(pw)
            run_matrix(br, origin, themes, pages, a.out, raw, ag, focus=not a.no_focus, screens=a.screens)
            extra = {}
            if a.live:
                extra["live"] = live_check(br, origin, pages)
                print("live (storage event):", sum(1 for x in extra["live"].values() if x.get("ok")), "/", len(extra["live"]), "pages repaint without a reload", flush=True)
            if a.mixcheck:
                extra["mix"] = mix_check(br, origin)
                print("mix:", sum(1 for x in extra["mix"].values() if x.get("ok")), "/", len(extra["mix"]), "hub pages and apps in their hub's look", flush=True)
            if extra:
                json.dump(extra, open(os.path.join(a.out, "_page_checks.json"), "w", encoding="utf-8"), indent=1)
        srv.shutdown()
        return 0
    if a.themes:
        want = a.themes.split(",")
        themes = [t for t in themes if t[0] in want]
    pages = [p for p in PAGES if (p[0] != "mint" or a.mix or "mint" in a.pages) and (not a.pages or p[0] in a.pages.split(","))]
    mix = {"district": mix_districts(MIXES[a.mix]), "app": {}, "of": of_map()} if a.mix else None
    if mix:
        themes = [("agora", f"Mix: {a.mix.title()} (" + ", ".join(f"{k} = {v}" for k, v in MIXES[a.mix].items()) + ")")]
    os.makedirs(a.out, exist_ok=True)
    raw = a.raw or os.path.join(a.out, ".raw")
    os.makedirs(raw, exist_ok=True)
    srv, origin = serve(a.site)
    bad, sheets = 0, []
    with sync_playwright() as pw:
        br = BK.launch(pw)
        for tid, name in themes:
            files = []
            for key, path, label in pages:
                f, errs = shoot(br, origin, tid, key, path, raw, a.leftovers, mix)
                files.append(f)
                if errs:
                    bad += 1
                    print(f"  {tid} {key}: page error {errs[:2]}")
            out = os.path.join(a.out, (f"mix-{a.mix}" if mix else tid) + f".{a.ext}")
            sheet(files, [p[2] for p in pages], out, f"{name}  ({tid})")
            sheets.append(out)
            print("sheet:", out, flush=True)
    srv.shutdown()
    if a.stack:
        stack(sheets, a.stack)
        print("stack:", a.stack)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
