"""OLYMPUS WORLD page (tools/web_public/cities/world/, night-worlds 2026-11-19): the repo's data as ONE giant night city in three.js
(owner: "all cities should be in one giant city, just different areas for like 1) Kalshi, 2) NQ etc."; "not some 2000's looking play-doh").

  a. static: the files, the kit lines (olympus.js as Cities, gate-nav), three.js r160 and the render core from the site (no CDN, no network
     but the site's own files and the public PC status feed), no browser storage, no markup from data, read only; the Cities app links it
  b. Chromium 390 x 844 (x2): the city renders (hundreds of places, thousands of instanced buildings in a few dozen draw calls), labels,
     a tap on a building opens its card ($ facts, Open), a district button flies there and lists its apps, Find, the frame rate in
     headless (software GL), no console error, every tap >= 44 px, no sideways scroll, Jarvis's corner free
  c. live: a PC feed with Zlarior in a trade -> the chip says so and the bot's place pulses; the Board's events in plain words
  d. no WebGL / ?flat=1: the same city as a list with every app's link; reduced motion: no flyover
    python -X utf8 -m tests.test_world_page             (--static: part a only; --shots: also the phone shots + the video in research/handoff/2026-11-19/worlds/)
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import agora_kit as AK  # noqa: E402

check = AK.check
D = os.path.join(AK.WEB, "cities", "world")
SHOTS = os.path.join(AK.ROOT, "research", "handoff", "2026-11-19", "worlds")
FILES = ("index.html", "world.css", "ow-main.js", "ow-scene.js", "ow-core.js", "ow-shaders.js", "world.json", "icon.svg")


def test_static():
    have = [f for f in FILES if os.path.isfile(os.path.join(D, f))]
    check("a. the files are there (%s)" % ", ".join(FILES), len(have) == len(FILES), sorted(set(FILES) - set(have)))
    html, main, scene, core, sh = (AK.read(os.path.join(D, f)) for f in ("index.html", "ow-main.js", "ow-scene.js", "ow-core.js", "ow-shaders.js"))
    check("a. the kit: olympus.js as the Cities app, gate-nav (Home + Go to), the page's own module last", 'src="../../olympus/olympus.js?v=o15" data-app="cities"' in html
          and "../../olympus/gate-nav.js" in html and html.rindex('src="ow-main.js?v=w3"') > html.index("olympus.js"))
    check("a. three.js r160 from the site (../../jarvis/three.module.min.js, vendored, MIT) and the OLYMPUS render core; no CDN, no http(s) address in the code",
          "from '../../jarvis/three.module.min.js'" in scene and "from '../../olympus/render.js'" in scene and not re.search(r"https?://", main + scene + core + sh))
    check("a. instanced: one InstancedBufferGeometry per kind (buildings, halos, traffic, beams, rings, streaks), never a mesh per building",
          scene.count("instanced(") >= 6 and "InstancedBufferGeometry" in scene and "new THREE.Mesh(new THREE.BoxGeometry" not in scene)
    check("a. no browser storage, no innerHTML / insertAdjacentHTML, no POST / PUT, no order words", not re.search(r"localStorage|sessionStorage|indexedDB|innerHTML|insertAdjacentHTML|method:\s*['\"](POST|PUT|DELETE)", main + scene + core)
          and not re.search(r"\b(place_order|submit_order|arm_live)\b", main + scene + core))
    check("a. phone-safe: the render core caps the pixel ratio at 2 (maxDpr: 2), tiers (onTier: no mirror and fewer lights on low), reduced motion = no flyover",
          "maxDpr: 2" in scene and "rc.onTier(applyTier)" in scene and "mirror.visible = !lowT" in scene and "prefers-reduced-motion" in main and "reduced ? 1 : " in scene)
    # revamp-cities 2026-11-20 (owner: "looks like a 2000's computer built it"): the look's parts stay in (research/handoff/2026-11-20/revamp-cities/LOOK.md)
    check("a. revamp look: one prism for shaped towers (chamfer / taper, a box batch of 10 triangles), lit floors with a far fallback, the sky (uDusk + uNoon daylight), "
          "clouds, the far shore, satellite towns, LED bands, aircraft, light-streak traffic",
          "function prism(box)" in scene and "iShape" in scene and "onFar" in sh and "uDusk" in sh and "uNoon" in sh and "FAR_FS" in sh and "uTowns" in sh and "BAND_FS" in sh
          and "PLANE_FS" in sh and "setDisplay" in scene and "towns" in core and "setDisplay(0, l.text)" in main)
    check("a. the reflection pass never takes exp() of a big positive (the NaN bloom blobs of the first try): heights are abs()'d", "float wy = abs(vW.y);" in sh and "exp(-vW.y" not in sh)
    check("a. reduced motion: the LED text stands still, no aircraft", "reduced ? 0 : 0.035 / rep" in scene and "planes.visible = !reduced" in scene)
    try:
        # cities3 2026-11-20 (owner: "sky from real ET time (day/dusk/night)"): the real sun over New York replaced the market clock
        out = subprocess.run(["node", "--input-type=module", "-e", "import {skyFor} from './ow-core.js'; const t = (s) => skyFor('auto', new Date(s));"
                              "console.log(JSON.stringify([t('2026-11-20T17:00:00Z'), t('2026-11-20T21:20:00Z'), t('2026-11-20T21:55:00Z'), t('2026-11-21T03:00:00Z'), skyFor('night'), skyFor('blue'), skyFor('dusk'), skyFor('day')].map((x) => Math.round(x * 100) / 100)))"],
                             cwd=D, capture_output=True, text=True, timeout=60).stdout.strip()
        check("a. the sky follows the real sun over New York: Nov 20 noon day (2), 16:20 ET sunset (1), 16:55 ET dusk (~0.5), 22:00 night (0); ?sky= night/blue/dusk/day forces it (%s)" % out,
              out == "[2,1,0.47,0,0,0.5,1,2]", out)
    except (OSError, subprocess.SubprocessError) as e:
        check("a. the market-clock sky (node not found: skipped)", True, str(e))
    cities = AK.read(os.path.join(AK.WEB, "cities", "index.html"))
    # cities3 2026-11-20: live district billboards, the sound switch, the frame safe area, the LED colour line out of its comment
    check("a. cities3: district billboards from the PC feed + kalshi.json (C.billboards -> #bills), every sound asks the Settings switch (soundOn), "
          "frame-safe.js loaded, the LED bands get their colour (dC.set on its own line)",
          "C.billboards(lite, kal, now)" in main and "function placeBills()" in main and "function soundOn()" in main and "st.sound === true" in main
          and "OLYMPUS_SFX.cue(" not in main and "frame-safe.js" in html and re.search(r"\n\s*dC\.set\(b\.col, k \* 3\)", scene))
    try:
        fx = os.path.join(AK.ROOT, "tests", "fixtures", "widget", "lite.ndjson")
        js = ("import {billboards} from './ow-core.js'; import fs from 'fs'; let l = null;"
              "for (const x of fs.readFileSync(%s, 'utf8').split('\\n')) { try { const m = JSON.parse(JSON.parse(x).message); if (m.kind === 'le-live' && (!l || m.t > l.t)) l = m; } catch (e) {} }"
              "console.log(JSON.stringify([billboards(l, {balance: 55.2, today_pnl: 1.25, running: true}), billboards(null, null)]))") % json.dumps(fx)
        out = json.loads(subprocess.run(["node", "--input-type=module", "-e", js], cwd=D, capture_output=True, text=True, timeout=60).stdout.strip() or "null")
        b0, b1 = out
        check("a. cities3 billboards: NQ price + every account balance, Kalshi $55.20 today +$1, Money room per account + to pass; nothing = empty lines (%s)" % b0,
              b0["nq"].startswith("NQ 26,431.00") and "$49,193" in b0["nq"] and "$24,887" in b0["nq"] and "$25,000" in b0["nq"] and b0["kalshi"].startswith("KALSHI $55.20  ·  today +$1")
              and "room $1,025 / $887 / $1,000" in b0["money"] and "to pass $3,807 / $1,500" in b0["money"] and b1 == {"nq": "NQ", "kalshi": "", "money": ""}, out)
    except (OSError, subprocess.SubprocessError, ValueError, TypeError) as e:
        check("a. cities3 billboards (node: %s)" % e, False)
    check("a. the Cities app's front screen links Olympus World (world/), as a card with a real frame of the 3D city (world-card.jpg)", 'href="world/"' in cities
          and "world-card.jpg" in cities and os.path.isfile(os.path.join(AK.WEB, "cities", "world-card.jpg")) and os.path.isfile(os.path.join(D, "poster.jpg")))
    w = json.load(open(os.path.join(D, "world.json"), encoding="utf-8"))
    check("a. world.json: 'olympus-world', 4 districts, hundreds of places (%d)" % len(w.get("places", [])), w.get("kind") == "olympus-world" and len(w["districts"]) == 4 and len(w["places"]) > 300)


def feed_body(lite):
    now = int(time.time())
    return "\n".join(json.dumps({"id": str(i), "time": now, "event": "message", "topic": "x", "message": json.dumps(m)}) for i, m in enumerate(lite)) + "\n"


def lite_post(in_trade=True):
    now = int(time.time())
    board = {"lit": {"position": {"entry_t": now - 300, "side": "LONG", "qty": 6}} if in_trade else {}, "atlas": {}}
    return {"v": 1, "kind": "le-live", "lite": True, "t": now - 60, "pc": {"t": now - 60}, "board": board, "reporter": {"t": now - 60}}


def wait_ready(p, origin, q, ms=180000):
    p.goto(f"{origin}/cities/world/{q}")
    p.wait_for_function("window.OWORLD && window.OWORLD.ready()", timeout=ms, polling=300)


def tap_place(p, pid):
    """put the camera over a place and tap its centre on the canvas"""
    p.evaluate("(id) => { document.querySelector('#card').hidden = true; OWORLD.focus(0); const w = OWORLD.world(); const pl = w.places.find((x) => x.id === id); OWORLD.pose({ tx: pl.x, ty: 2, tz: pl.z, dist: 60, yaw: 0, pitch: 0.75 }); }", pid)
    p.wait_for_function("(id) => { const s = OWORLD.screenOf(id); return s && s.front; }", arg=pid, timeout=60000, polling=200)
    p.wait_for_timeout(600)
    s = p.evaluate("(id) => OWORLD.screenOf(id)", pid)
    p.mouse.click(s["x"], s["y"])
    p.wait_for_timeout(500)
    return p.evaluate("() => OWORLD.state()")


def test_page():
    try:
        import playwright  # noqa: F401
    except ImportError:
        check("b. page tests skipped: no Playwright", True)
        return
    srv, origin = AK.serve()
    try:
        with AK.browser() as br:
            topic = AK.status_feed_prefix().rstrip("/").split("/")[-1] or "olympus-nq-status"
            ctx, p, errs, seen, off = AK.page(br, origin, mock={topic + "/json": feed_body([lite_post(True)])})
            p.set_default_timeout(120000)
            t0 = time.time()
            wait_ready(p, origin, "?q=low")
            st = p.evaluate("() => OWORLD.state()")
            sc = st.get("scene") or {}
            check("b. 3D: the city renders in %.1f s (first frame %s ms after the module), hundreds of places (%d), %d districts, %d instanced buildings in %s draw calls (%s triangles)" % (
                time.time() - t0, st.get("firstFrameMs"), st["places"], st["districts"], sc.get("instances", 0), sc.get("calls"), sc.get("triangles")),
                st["mode"] == "3d" and st["places"] > 300 and st["districts"] == 4 and sc.get("instances", 0) > 6000 and 0 < sc.get("calls", 99) < 40 and sc.get("tier") == "low", st)
            p.evaluate("() => OWORLD.skip()")
            p.wait_for_timeout(1500)
            f0 = p.evaluate("() => OWORLD.state().scene.frames")
            p.wait_for_timeout(6000)
            s2 = p.evaluate("() => OWORLD.state()")
            fps = (s2["scene"]["frames"] - f0) / 6.0
            mult = 1.0
            try:
                sys.path.insert(0, os.path.join(AK.ROOT, "tests"))
                import browser_kit as BK
                mult = BK.multiplier()
            except Exception:
                pass
            check("b. frame rate in headless (software GL, no GPU, 390 x 844, low tier): %.1f fps and %.2f ms of JavaScript a frame (median); it keeps drawing (the phone's GPU is far faster, the JS is the part a phone pays the same)" % (fps, s2["scene"]["jsMs"]),
                  fps >= 0.5 / mult and s2["scene"]["jsMs"] < 8 * mult, (fps, s2["scene"]))
            check("b. labels over the city (%d) and the learning ticker has a dated line" % s2["labels"], s2["labels"] >= 3 and re.match(r"^[A-Z][a-z]{2} \d+ · ", s2["ticker"] or ""), (s2["labels"], s2["ticker"]))
            AK.shot(p, "world-low-home")
            s3 = tap_place(p, "app:hub-zeus-html")
            card = p.evaluate("""() => ({ title: document.querySelector('#cardName').textContent, open: [...document.querySelectorAll('#cardBody .btn.go')].map((b) => b.textContent),
              chips: [...document.querySelectorAll('#cardBody .chip')].map((c) => c.textContent), facts: [...document.querySelectorAll('#cardBody .facts b')].map((b) => b.textContent) })""")
            check("b. a tap on a building (the ZEUS tower) selects it and opens its card: name, APP chip, district, 'Open ZEUS'",
                  s3["selected"] == "app:hub-zeus-html" and card["title"] == "ZEUS" and card["open"] == ["Open ZEUS"] and card["chips"][0] == "App" and "NQ" in card["chips"][1], (s3["selected"], card))
            s4 = tap_place(p, "bot:lit")
            facts = p.evaluate("() => [...document.querySelectorAll('#cardBody .facts b')].map((b) => b.textContent)")
            check("b. tap Zlarior's place: its card says what it is in $ (a month, PF), LIVE", s4["selected"] == "bot:lit" and any("$" in f and "a month" in f for f in facts)
                  and p.evaluate("() => document.querySelector('#cardBody .chip').textContent") == "Live", (s4["selected"], facts))
            p.click(".dch[data-d=kalshi]")
            p.wait_for_timeout(300)
            k = p.evaluate("""() => ({ title: document.querySelector('#cardName').textContent, apps: [...document.querySelectorAll('#cardBody .applist')][0].querySelectorAll('button').length,
              pressed: document.querySelector('.dch[aria-pressed=true]').dataset.d, sc: OWORLD.state().scene })""")
            check("b. the Kalshi district button flies there (a warp) and its card lists its 5 apps and its learning quarters", k["title"] == "Kalshi" and k["apps"] == 5 and k["pressed"] == "kalshi"
                  and (k["sc"]["tween"] or k["sc"]["warp"] >= 0), k)
            p.wait_for_function("() => !OWORLD.state().scene.tween", timeout=60000, polling=250)
            pose = p.evaluate("() => OWORLD.pose()")
            kd = p.evaluate("() => OWORLD.world().districts.find((d) => d.id === 'kalshi')")
            check("b. ... and lands over the Kalshi district", abs(pose["tx"] - kd["x"]) < 2 and abs(pose["tz"] - kd["z"]) < 2, (pose, kd["x"], kd["z"]))
            p.click(".dk[data-act=find]")
            p.fill("#sheetBody input", "taxes")
            p.wait_for_timeout(200)
            hits = p.evaluate("() => [...document.querySelectorAll('#sheetBody .res li span')].map((s) => s.firstChild.textContent)")
            p.click("#sheetBody .res li")
            p.wait_for_timeout(400)
            check("b. Find 'taxes' lists the Taxes page first; a tap flies there and opens its card", hits[:1] == ["Taxes"] and p.evaluate("() => document.querySelector('#cardName').textContent") == "Taxes", hits[:5])
            live = p.evaluate("() => ({ chip: document.querySelector('#liveChip').textContent, on: document.querySelector('#liveChip').classList.contains('on'), pc: document.querySelector('#pcText').textContent })")
            check("c. live: the PC feed (mocked: Zlarior LONG) -> 'Zlarior is in a trade · LONG' and 'PC live · ...'", live["on"] and live["chip"] == "Zlarior is in a trade · LONG" and live["pc"].startswith("PC live"), live)
            check("c. the feed was asked through the page's own status_feed.json (the mock answered it), nothing else left the site", bool(p.mocked) and not off, (p.mocked[:2], off[:3]))
            t = AK.taps(p)
            check("b. every tap target is at least 44 x 44 px", not t, t[:6])
            p.evaluate("() => { document.querySelector('#card').hidden = true; document.querySelector('#sheet').hidden = true; }")
            check("b. no sideways scroll, Jarvis's corner (bottom-right) free, no console error", AK.no_sideways(p) and not AK.corner(p) and not errs, (AK.corner(p), errs[:4]))
            ctx.close()
            # no WebGL (or 3D off): the same city as a list
            ctx, p, errs, seen, off = AK.page(br, origin)
            wait_ready(p, origin, "?flat=1")
            f = p.evaluate("() => ({ mode: OWORLD.state().mode, secs: document.querySelectorAll('#flat section').length, links: [...document.querySelectorAll('#flat a[href]')].map((a) => a.getAttribute('href')), canvas: getComputedStyle(document.querySelector('#c')).opacity })")
            check("d. ?flat=1 (no WebGL): a list of the four districts with every app's link (%d), the 3D canvas hidden, never blank" % len(f["links"]),
                  f["mode"] == "2d" and f["secs"] == 4 and len(f["links"]) > 80 and "../../hub/zeus.html" in f["links"] and f["canvas"] == "0", {k: v for k, v in f.items() if k != "links"})
            check("d. no console error in the list", not errs, errs[:3])
            ctx.close()
            ctx, p, errs, seen, off = AK.page(br, origin, reduced=True)
            wait_ready(p, origin, "?q=low")
            r = p.evaluate("() => ({ intro: OWORLD.state().scene.intro, hint: OWORLD.state().hinted })")
            check("d. reduced motion: no flyover (the city is just there) and the 'tap any building' hint shows", r["intro"] is False and r["hint"], r)
            ctx.close()
    finally:
        srv.shutdown()


# ------------------------------------------------------------------------------------------------ the phone shots and the video (--shots)
VIDEO = [  # js before, frames at 24 fps (manual clock): the opening flyover, then flights between districts; 7.9 s in all (<= 8 s)
    (None, 84), ("OWORLD.district('zeus')", 26), ("OWORLD.open('app:hub-zeus-html')", 26), ("OWORLD.district('kalshi')", 26),
    ("document.querySelector('#cardX').click(); document.querySelector('.dk[data-act=home]').click()", 28),
]
SHOT_STEPS = [  # name, js (the flight is finished in one clock step, then a few frames settle)
    ("01-city", "OWORLD.skip()"),
    ("02-nq-district", "OWORLD.district('zeus')"),
    ("03-zeus-card", "OWORLD.open('app:hub-zeus-html')"),
    ("04-zlarior", "OWORLD.open('bot:lit')"),
    ("05-kalshi", "OWORLD.district('kalshi')"),
    ("06-lab-ruins", "OWORLD.open(OWORLD.world().places.find((p) => p.quarter === 'lab' && p.state === 'ruin').id)"),
    ("07-overview", "document.querySelector('#cardX').click(); OWORLD.pose({tx: 0, tz: -12, dist: 380, yaw: -0.4, pitch: 1.0})"),
]


def _shots_page(pw, origin, dsf):
    sys.path.insert(0, os.path.join(AK.ROOT, "tests"))
    import browser_kit as BK
    br = BK.launch(pw)
    ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=dsf, is_mobile=True, has_touch=True)
    ctx.add_init_script("try { localStorage.setItem('jfx', 'high'); } catch (e) {}")
    ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith(origin) else r.abort())
    p = ctx.new_page()
    p.set_default_timeout(600000)
    errs = []
    p.on("pageerror", lambda e: errs.append(str(e)))
    p.goto(f"{origin}/cities/world/?q=high&gpu=1&clock=manual")
    p.wait_for_function("window.OWORLD && window.OWORLD.ready() && OWORLD.state().scene", timeout=600000, polling=500)
    p.wait_for_timeout(1200)
    return ctx, p, errs


def make_shots():
    """phone shots (390 x 844, x2) and a short video, rendered frame by frame on a fixed 24 fps clock (?clock=manual): this machine has no
    GPU, so a real-time recording would be a slideshow; the same scene code draws every frame, the clock just waits for it"""
    os.makedirs(SHOTS, exist_ok=True)
    srv, origin = AK.serve()
    frames = tempfile.mkdtemp(prefix="world-frames-")
    errs = []
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            ctx, p, e1 = _shots_page(pw, origin, 2)
            for name, js in SHOT_STEPS:
                p.evaluate("() => { " + js + " }")
                p.evaluate("() => { OWORLD.step(1300, true); for (let i = 0; i < 24; i++) OWORLD.step(100, true); }")
                p.wait_for_timeout(700)
                p.evaluate("() => OWORLD.step(40)")
                p.screenshot(path=os.path.join(SHOTS, name + ".jpg"), type="jpeg", quality=90, timeout=600000)
                print("  shot:", name, flush=True)
            ctx.close()
            ctx, p, e2 = _shots_page(pw, origin, 1)
            n = 0
            for js, count in VIDEO:
                if js:
                    p.evaluate("() => { " + js + " }")
                for _ in range(count):
                    p.evaluate("() => OWORLD.step(1000 / 24)")
                    p.screenshot(path=os.path.join(frames, "f%04d.jpg" % n), type="jpeg", quality=90, timeout=600000)
                    n += 1
                print("  video:", n, "frames", flush=True)
            ctx.close()
            errs = e1 + e2
        mp4 = os.path.join(SHOTS, "olympus-world.mp4")
        if shutil.which("ffmpeg"):
            for crf in (24, 28, 32, 36):
                subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", "24", "-i", os.path.join(frames, "f%04d.jpg"), "-vf", "scale=390:-2",
                                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", str(crf), "-preset", "slow", "-movflags", "+faststart", mp4], check=True, timeout=1200)
                if os.path.getsize(mp4) < 4_000_000:
                    break
        print("shots + video:", SHOTS, "errors:", errs[:3], flush=True)
        return errs
    finally:
        shutil.rmtree(frames, ignore_errors=True)
        srv.shutdown()


if __name__ == "__main__":
    test_static()
    if "--static" not in sys.argv:
        test_page()
    if "--shots" in sys.argv:
        e = make_shots()
        check("shots: the phone shots and the video were made with no page error", not e and os.path.isfile(os.path.join(SHOTS, "olympus-world.mp4")), e[:3])
    AK.finish()
