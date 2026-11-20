"""JARVIS FX (day-jarvis 2026-11-20, owner via lead: "It needs some 3D, it needs some effects ... NO GOLD"): jarvis/jfx.css + jarvis/jfx.js,
the switcher without gold (jarvis/switcher.js) and the cyan / violet temple mark (jarvis/mark.svg). Chromium at 390 x 844 on the hub test's
site copy (tests.test_jarvis_hub), the PC's post fed from a fixture:
  a. the files: the FX sheet and script never hold the first paint (media=print swap, defer); no gold in them; the switcher's CSS has no gold
     except a warning's amber; the temple mark has no gold
  b. Jarvis home: the ZEUS card is navy glass with a cyan edge and a cyan -> violet title; the KALSHI / NQ tiles glow; no gold on the card,
     tiles, orb ring or title mark; the $ roll-up draws over the number while the real text is the final value all along, and lands
  c. the switcher: a card leans in 3D under the finger (rotateX / rotateY, a glare) and lets go on lift; the orb ring is cyan / violet
  d. reduced motion: no roll-ups; Ivory (light): blue / violet ink, no gold accent; no page errors
    python -X utf8 -m tests.test_jarvis_fx      (~60 s)
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "tools", "web_public")
JV = os.path.join(WEB, "jarvis")
RESULTS = []
GOLD = re.compile(r"#(?:c8a24a|dcbd6e|e0b060|e6bb62|e2b65c|fbe7b0|b0802f|ecd49a)\b|200,\s*162,\s*74|224,\s*176,\s*96", re.I)


def check(name, ok, info=None):
    RESULTS.append((name, bool(ok)))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:400]}"))


def read(*p):
    return open(os.path.join(*p), encoding="utf-8").read()


def part_a():
    page = read(JV, "index.html")
    check("a. jfx.css after the first paint (media=print, swapped on load) and jfx.js deferred: the start is not held",
          '<link rel="stylesheet" id="jfx" href="jfx.css?v=1" media="print" onload="this.media=\'all\'">' in page and '<script src="jfx.js?v=1" defer></script>' in page)
    css, js, mark = read(JV, "jfx.css"), read(JV, "jfx.js"), read(JV, "mark.svg")
    check("a. no gold in jfx.css, jfx.js or the temple mark (cyan / blue / violet)", not GOLD.search(css) and not GOLD.search(js) and not GOLD.search(mark)
          and "#22d3ee" in css and "#8b5cf6" in css and "#22d3ee" in mark, [GOLD.findall(x)[:3] for x in (css, js, mark)])
    sw = read(JV, "switcher.js")
    block = sw[sw.index("const CSS = `"):sw.index("`;", sw.index("const CSS = `"))]
    left = [ln[:90] for ln in block.splitlines() if GOLD.search(ln) and not re.search(r"\.warn\b|lv-warn", ln)]
    check("a. the switcher's CSS: no gold except a warning's amber; its accents are --nx-hi (cyan) / --nx-vi (violet)", not left and "--nx-hi:#22d3ee" in block, left[:3])
    check("a. the temple mark in the title and the footer is mark.svg (not the gold icon)", page.count('src="mark.svg?v=1"') == 2)
    check("a. jfx.js: classic script, no innerHTML, no network", "innerHTML" not in js and "fetch(" not in js and not re.search(r"^\s*(import|export)\s", js, re.M))


def site_copy(tmp):
    from tests import test_jarvis_hub as H
    v = H.site(tmp, "C", "asis")
    r = os.path.join(tmp, v.strip("/"))
    with open(os.path.join(r, "status_feed.json"), "w", encoding="utf-8") as f:
        f.write('{"topic": "fx-topic", "ntfy": "https://ntfy.sh"}')
    shutil.copy(os.path.join(WEB, "pc_feed.js"), r)
    for d in ("business", "board"):
        if not os.path.exists(os.path.join(r, d)):
            shutil.copytree(os.path.join(WEB, d), os.path.join(r, d))
    return H, v


def page(H, br, host, v, ivory=False, reduce=False):
    ctx, p, errs, kal = H.new_page(br, reduced_motion="reduce" if reduce else "no-preference")
    live = json.loads(json.dumps(H.LIVE))
    live["t"] = int(time.time()) - 60
    if isinstance(live.get("pc_health"), dict):
        live["pc_health"]["t"] = int(time.time()) - 90
    line = json.dumps({"id": "x", "time": int(time.time()) - 60, "event": "message", "topic": "fx-topic", "message": json.dumps(live)})
    ctx.route(re.compile(r"^https://ntfy\.sh/.*"), lambda r: r.fulfill(status=200, content_type="application/x-ndjson", body=line + "\n"))
    ctx.add_init_script("try { ['jarvis.tour.seen','olympus.tour.done','jarvis.pinHint'].forEach((k) => localStorage.setItem(k, '1')); localStorage.setItem('jarvis.intro', 'off');"
                        " localStorage.setItem('jarvis.speak', 'off');" + (" localStorage.setItem('olympus.theme', 'ivory'); localStorage.setItem('olympus.theme.v', '2');" if ivory else "") + " } catch (e) {}"
                        # watch the roll-ups: every frame a rolling number is drawn, note what it showed and what its real text was
                        " window.__rolls = []; new MutationObserver((l) => { for (const m of l) { const e = m.target; if (e.classList && e.classList.contains('on') && e.dataset.roll)"
                        " window.__rolls.push([e.dataset.roll, e.textContent]); } }).observe(document, { attributes: true, attributeFilter: ['data-roll'], subtree: true });")
    p.goto(host + v + "jarvis/")
    H.ready(p)
    p.wait_for_function("window.JFX && window.JFX.ready", timeout=20000)
    return ctx, p, errs


def colours(p, sel, pseudo=None):
    return p.evaluate("([s, ps]) => { const e = document.querySelector(s); if (!e) return null; const c = getComputedStyle(e, ps);"
                      " return [c.color, c.backgroundColor, c.borderTopColor, c.borderLeftColor, c.backgroundImage].join(' | '); }", [sel, pseudo])


def is_gold(s):
    """an rgb(...) in the gold / amber family: red high, green a bit lower, blue far lower"""
    for r, g, b in re.findall(r"rgba?\((\d+),\s*(\d+),\s*(\d+)", s or ""):
        r, g, b = int(r), int(g), int(b)
        if r > 150 and 110 < g < r and b < g - 50:
            return True
    return False


def main():
    part_a()
    from playwright.sync_api import sync_playwright
    tmp = tempfile.mkdtemp(prefix="jfx_")
    try:
        H, v = site_copy(tmp)
        srv = H.serve(tmp)
        host = f"http://127.0.0.1:{srv.server_address[1]}/"
        with sync_playwright() as pw:
            br = H.launch(pw)
            ctx, p, errs = page(H, br, host, v)
            p.wait_for_function("document.querySelectorAll('.zeus-card .zeus-b').length >= 2", timeout=30000)
            p.wait_for_timeout(2500)
            z = {k: colours(p, s, ps) for k, s, ps in (("card", ".zeus-card", None), ("title", ".zeus-t", None), ("edge", ".zeus-card", "::before"),
                                                      ("kbox", "#kbox", None), ("nbox", "#nbox", None), ("orb", ".nx-orb", "::after"))}
            check("b. ZEUS: navy glass, a cyan top edge, the cyan -> violet gradient title", "rgb(34, 211, 238)" in z["card"] and "linear-gradient" in z["edge"]
                  and "rgb(103, 232, 249)" in z["title"] and "rgb(167, 139, 250)" in z["title"], z)
            check("b. the KALSHI / NQ tiles glow (a cyan / violet layer and edge)", "radial-gradient" in (z["kbox"] or "") and "rgb(34, 211, 238)" in (z["kbox"] or "")
                  and "rgb(139, 92, 246)" in (z["nbox"] or ""), {k: z[k] for k in ("kbox", "nbox")})
            check("b. no gold on the ZEUS card, its title, the tiles or the orb ring", not any(is_gold(x) for x in z.values()), z)
            fin = p.evaluate("[...document.querySelectorAll('.zeus-b, .zeus-d, .hc-n, .tile .t-v > b, #npnl, #kusd')].map((e) => e.textContent)")
            rolls = p.evaluate("window.__rolls")
            mid = [r for r in rolls if r[0] != r[1]]
            check("b. the $ roll-up: numbers rolled (drawn over), while their real text was the final value", p.evaluate("window.JFX.rolls") >= 2 and mid
                  and all(r[1] in fin for r in rolls), {"rolls": p.evaluate("window.JFX.rolls"), "sample": rolls[:4], "final": fin})
            check("b. every roll landed: nothing still drawn over the number", p.evaluate("document.querySelectorAll('.jfx-roll.on').length") == 0)
            # c. the switcher
            p.click("#nxOrb")
            p.wait_for_function("document.getElementById('nxRoot').classList.contains('on')", timeout=20000)
            p.wait_for_timeout(700)
            box = p.evaluate("(() => { const c = [...document.querySelectorAll('.nx-card[data-nx]')].find((x) => { const r = x.getBoundingClientRect(); return r.left >= 0 && r.right <= innerWidth; });"
                             " if (!c) return null; const r = c.getBoundingClientRect(); return { x: r.left + r.width * 0.8, y: r.top + r.height * 0.2, id: c.dataset.nx }; })()")
            tilt = None
            if box:
                p.mouse.move(box["x"], box["y"])
                p.mouse.down()
                p.wait_for_timeout(120)
                tilt = p.evaluate("(id) => { const c = document.querySelector(`.nx-card[data-nx=\"${id}\"]`); return { t: c.style.transform, on: c.classList.contains('jfx-tilt'), glare: !!c.querySelector('.jfx-glare') }; }", box["id"])
                p.mouse.up()
                p.wait_for_timeout(120)
                after = p.evaluate("(id) => { const c = document.querySelector(`.nx-card[data-nx=\"${id}\"]`); return { t: c.style.transform, on: c.classList.contains('jfx-tilt') }; }", box["id"])
            check("c. a switcher card leans in 3D under the finger (rotateX + rotateY, a glare) and lets go on lift",
                  tilt and "rotateX(" in tilt["t"] and tilt["on"] and tilt["glare"] and not after["on"] and "rotateX(" not in after["t"], (tilt, box))
            ring = colours(p, ".nx-orb", "::after")
            check("c. the orb's ring is cyan / violet", "rgb(34, 211, 238)" in (ring or "") and not is_gold(ring), ring)
            check("b-c. no page errors", not errs, errs[:3])
            ctx.close()
            # d. reduced motion, Ivory
            ctx, p, errs = page(H, br, host, v, reduce=True)
            p.wait_for_function("document.querySelectorAll('.zeus-card .zeus-b').length >= 2", timeout=30000)
            p.wait_for_timeout(1500)
            check("d. reduced motion: no roll-ups (the numbers just show)", p.evaluate("window.JFX.rolls") == 0 and not p.evaluate("window.__rolls"), p.evaluate("window.JFX.rolls"))
            ctx.close()
            ctx, p, errs = page(H, br, host, v, ivory=True)
            p.wait_for_timeout(1500)
            acc = p.evaluate("(() => { const c = getComputedStyle(document.documentElement); return [c.getPropertyValue('--c').trim(), c.getPropertyValue('--oly-th-a8').trim(), c.getPropertyValue('--oly-th-a7').trim(),"
                             " getComputedStyle(document.querySelector('.pm[aria-current=\"page\"]') || document.body).backgroundImage + getComputedStyle(document.querySelector('.pm[aria-current=\"page\"]') || document.body).backgroundColor]; })()")
            hexgold = [x for x in acc[:3] if GOLD.search(x) or re.match(r"#(?:[6-9a-f][0-9a-f])(?:[4-9a-f][0-9a-f])(?:[0-3][0-9a-f])$", x, re.I)]
            check("d. Ivory (light): the accent is blue / violet ink, not gold (the current-page pill too)", not hexgold and not is_gold(acc[3]) and p.evaluate("document.documentElement.dataset.olyScheme") == "light", acc)
            check("d. no page errors (reduced motion, Ivory)", not errs, errs[:3])
            ctx.close()
            br.close()
        srv.shutdown()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    bad = [n for n, ok in RESULTS if not ok]
    print(f"\njarvis fx: {len(RESULTS) - len(bad)}/{len(RESULTS)} {'ALL PASS' if not bad else 'FAILED'}")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.path.insert(0, ROOT)
    sys.exit(main())
