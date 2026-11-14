"""OLYMPUS theme contact sheets (docs/OLYMPUS_DESIGN.md "Themes"): every theme on the pages that matter, at 390 x 844.

    python -X utf8 tools/theme_shots.py --site <built site> --out docs/shots/themes [--themes agora,ivory] [--pages gate,jarvis] [--raw <dir>]

<built site> = python tools/build_web_dashboard.py --out <dir> (only its data: data.json, home.json, runs/ ...; every app file is served
from this working tree, so the shots show the code as it is now). One JPEG per theme: <out>/<theme>.jpg (--ext png for PNG), the pages side by side
(Gate, the Gate's Look row, dashboard, Jarvis, NQ, Kalshi, Helios, Polis), each shot 390 x 844 at 1x. --raw keeps the full-size single shots too.
Read only: every request off the local origin is refused; the theme is set through localStorage 'olympus.theme' like the owner's pick.
Run browser work under: flock -w 2400 /tmp/olympus_browser.lock python -X utf8 tools/theme_shots.py ...
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


def serve(site):
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def end_headers(self):
            self.send_header("Cache-Control", "no-store")
            super().end_headers()

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
    a = ap.parse_args()
    from playwright.sync_api import sync_playwright
    from tests import browser_kit as BK
    themes = theme_ids()
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
