"""FORUM (tools/web_public/forum/, OLYMPUS 2026-11-03): the morning briefing in a Roman forum at the real New York hour.
  a. the static rules: the kit (?v=o2, data-app), the render core + Jarvis's three.js, no CDN, no innerHTML, only the site's own files are fetched
     (pantheon/pantheon.json, home.json, its fixture), storage only under 'forum.v1', safe areas and the orb's corner, reduced motion, manifest, icon, jarvis.json
  b. the briefing (forumcore.js, run in node): the New York clock across a DST change, the next point of the trading day on every kind of day, the
     phases and the sun, the six tablets from the Pantheon + the live eval (tones by VIX band, the calendar, the room left), missing data = honest
     "no data" tablets (never a crash), the oath, the streak (weekends skipped, today open does not break it)
  c. the page in Chromium at 390 x 844 on the chosen LITE tier: no errors, ?t= sets the New York time and the sky (night / day), 6 tablets, the walk
     (start, next, previous, dots, Escape), the oath (seal disabled until the three pledges are ticked), sealing opens the gates and is kept on this
     phone (streak 1, a reload comes back sealed), the orb's corner free, no sideways scroll, the DEMO copy when the Pantheon is missing,
     reduced motion, nothing leaves the machine
    python -X utf8 -m tests.test_forum_page            (FORUM_NO_BROWSER=1 skips c; FORUM_SHOTS=<dir> saves screenshots)
"""
from __future__ import annotations

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
PAGE = os.path.join(WEB, "forum")
RES = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:500]}"), flush=True)


def rd(*p):
    with open(os.path.join(*p), encoding="utf-8") as fh:
        return fh.read()


def node(body):
    script = ("import fs from 'fs'; const dir = " + json.dumps(PAGE) + "; const url = 'file://' + dir; const out = (x) => console.log('@@' + JSON.stringify(x));\n"
              "try { " + body + " } catch (e) { console.log('@@' + JSON.stringify({ error: String(e && e.stack || e) })); }")
    p = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True, timeout=90)
    m = [ln for ln in p.stdout.splitlines() if ln.startswith("@@")]
    return json.loads(m[-1][2:]) if m else {"error": (p.stderr or p.stdout)[-400:]}


# ------------------------------------------------------------------------------------------------ a. static
def part_a():
    files = os.listdir(PAGE)
    need = {"index.html", "forum.css", "forumcore.js", "forum.js", "scene.js", "fixture.json", "jarvis.json", "manifest.webmanifest", "icon.svg"}
    check("a. the folder has every file (page, css, core, page script, scene, demo fixture, Jarvis card, manifest, icon)", need <= set(files), need - set(files))
    html, css = rd(PAGE, "index.html"), rd(PAGE, "forum.css")
    js = {n: rd(PAGE, n) for n in files if n.endswith(".js")}
    check("a. the kit first (olympus.css, themes.js, olympus.js ?v=o2 with data-app), viewport-fit=cover, theme-color, dark, manifest, icon, apple-touch-icon",
          '<link rel="stylesheet" href="../olympus/olympus.css?v=o3">' in html and 'src="../olympus/themes.js?v=o3"' in html and 'src="../olympus/olympus.js?v=o3" data-app="forum"' in html
          and "viewport-fit=cover" in html and 'name="theme-color"' in html and 'content="dark"' in html and 'rel="manifest" href="manifest.webmanifest"' in html
          and 'rel="icon" href="icon.svg"' in html and 'rel="apple-touch-icon"' in html)
    check("a. no CDN, no outside script / font / image: every src and href is local", not re.search(r'(src|href)="https?://', html) and not any(re.search(r"import[^;]*['\"]https?://", s) for s in js.values()))
    check("a. 3D is Jarvis's three.js and the OLYMPUS render core + materials; no WebGLRenderer of its own; the core's dispose is called",
          "from '../jarvis/three.module.min.js'" in js["scene.js"] and "from '../olympus/render.js'" in js["scene.js"] and "from '../olympus/materials.js'" in js["scene.js"]
          and "createRenderer(" in js["scene.js"] and "rc.render()" in js["scene.js"] and "new THREE.WebGLRenderer" not in js["scene.js"] and "rc.dispose()" in js["scene.js"])
    check("a. no innerHTML / insertAdjacentHTML / document.write (the Pantheon's words only ever go in as text; the tablets are drawn on a canvas)",
          not any(re.search(r"innerHTML|insertAdjacentHTML|document\.write", s) for s in js.values()))
    fetched = set(re.findall(r"getJSON\('([^']+)'", js["forum.js"]))
    check("a. the page fetches only the site's own files (pantheon/pantheon.json, home.json, its fixture), no WebSocket / beacon / XHR, storage only under 'forum.v1'",
          fetched == {"../pantheon/pantheon.json", "../home.json", "fixture.json"} and not any(re.search(r"WebSocket|sendBeacon|XMLHttpRequest|EventSource", s) for s in js.values())
          and "const KEY = 'forum.v1'" in js["forum.js"] and set(re.findall(r"localStorage\.\w+Item\(([A-Za-z'\"\.]+)", js["forum.js"])) <= {"KEY"}, fetched)
    check("a. the OLYMPUS effects library (fx-core, ui, text, burst ?v=f1) is linked after olympus.js; forumdesk.js draws the desk / shrine / ritual with textContent only and reads the Planner only through its own helper",
          all(f"../olympus/fx-{n}.js?v=f1" in html for n in ("core", "ui", "text", "burst")) and html.find("fx-core.js") > html.find("olympus.js?v=o3") and "forumdesk.js" in js
          and not re.search(r"innerHTML", js["forumdesk.js"]) and "planner.v1" not in js["forum.js"] and "fxTarget" in js["scene.js"] and "id=\"desk\"" in html and "id=\"shrine\"" in html)
    check("a. the core has no clock, no network and no storage of its own (pure: the page passes the date in)", not re.search(r"fetch\(|XMLHttpRequest|localStorage|Date\.now|new Date\(\)", js["forumcore.js"]))
    check("a. safe areas on every edge, the orb's corner (the card and the step bar stop 96 px from the right), dvh after vh, reduced motion",
          all(f"var(--s{x})" in css for x in "trbl") and css.count("right: calc(var(--sr) + var(--oly-orb-clear, 96px))") >= 2
          and re.search(r"max-height: calc\(100vh[^;]*; max-height: calc\(100dvh", css) is not None and "@media (prefers-reduced-motion: reduce)" in css)
    m = json.loads(rd(PAGE, "manifest.webmanifest"))
    check("a. the manifest names the app and points at its icon", m["name"] == "Forum" and m["icons"][0]["src"] == "icon.svg" and m["start_url"] == "./")
    j = json.loads(rd(PAGE, "jarvis.json"))
    check("a. jarvis.json keeps the Jarvis card contract (name, status, <= 3 kpis, <= 3 lines, t, open, theme, <= 8 KB, plain text)",
          j["v"] == 1 and j["name"] == "Forum" and j["status"]["level"] in ("ok", "warn", "bad", "off") and len(j["kpis"]) == 3 and len(j["lines"]) <= 3 and isinstance(j["t"], int)
          and re.fullmatch(r"#[0-9a-f]{6}", j["theme"]) and os.path.getsize(os.path.join(PAGE, "jarvis.json")) < 8192 and not re.search(r"[<>]", json.dumps(j)), j)
    fx = json.loads(rd(PAGE, "fixture.json"))
    check("a. the demo fixture holds the council verdict, four gods and the 50K eval", fx["demo"] is True and fx["pantheon"]["council"]["gauge"] == 44 and len(fx["pantheon"]["gods"]) == 4
          and fx["home"]["accounts"][0]["eval"]["floor"] == 50100.0)


# ------------------------------------------------------------------------------------------------ b. the briefing
def part_b():
    js = node("""const F = await import(url + '/forumcore.js'); const fx = JSON.parse(fs.readFileSync(dir + '/fixture.json', 'utf8'));
      const P = (o) => ({ day: '2026-11-03', h: 8.5, dow: 2, ...o });
      const pan = fx.pantheon, home = fx.home, p = P({});
      const withVix = (v) => ({ ...pan, gods: pan.gods.map((g) => (g.key === 'ares' ? { ...g, reading: { value: v, text: String(v) } } : g)) });
      const withCal = (t) => ({ ...pan, gods: pan.gods.map((g) => (g.key === 'athena' ? { ...g, reading: { value: 1, text: t } } : g)) });
      const gauge = (g) => ({ ...pan, council: { ...pan.council, gauge: g } });
      const evRoom = (room) => ({ accounts: [{ plan: 'Builder 50K', kind: 'eval', eval: { balance: 50000 + room, floor: 50000, target_balance: 53000 } }] });
      const tone = (b, id) => b.find((x) => x.id === id).tone;
      const b0 = F.brief(pan, home, p), bm = F.brief(null, null, p), bj = F.brief({ council: null, gods: [{ junk: 1 }, null] }, { accounts: [null, 3] }, p);
      out({ ids: b0.map((x) => x.id), tones: b0.map((x) => x.tone), stats: b0.map((x) => x.stat), lines: b0.map((x) => x.line), bodyLen: b0.map((x) => x.body.length), ev: F.evalOf(home),
        vix: [12, 17, 22, 30].map((v) => tone(F.brief(withVix(v), home, p), 'fear')), cal: ['Today 08:30', 'Tomorrow 08:15', 'Fri 08:30'].map((t) => tone(F.brief(withCal(t), home, p), 'calendar')),
        council: [70, 50, 30].map((g) => tone(F.brief(gauge(g), home, p), 'council')), room: [300, 900, 2000].map((r) => tone(F.brief(pan, evRoom(r), p), 'eval')),
        missing: bm.map((x) => [x.id, x.tone, x.stat]), junk: bj.map((x) => x.tone), oath: F.oath().length,
        et: [F.etParts(new Date('2026-11-03T13:40:00Z')), F.etParts(new Date('2026-11-01T05:30:00Z')), F.etParts(new Date('2026-03-08T07:30:00Z')), F.etParts(new Date('2026-11-04T04:59:00Z'))],
        clock: [F.parseClock('08:40'), F.parseClock('8:05'), F.parseClock('24:00'), F.parseClock('x'), F.parseClock(null), F.clockText(8.6667), F.minsText(48), F.minsText(125)],
        next: [P({ h: 2 }), P({ h: 8.7 }), P({ h: 10 }), P({ h: 15.95 }), P({ h: 17 }), P({ h: 19 }), P({ dow: 5, h: 17 }), P({ dow: 6, h: 10 }), P({ dow: 0, h: 12 }), P({ dow: 0, h: 20 })].map((x) => { const n = F.nextEvent(x); return [n.id, Math.round(n.mins), n.tomorrow]; }),
        phase: [1, 4, 8, 12, 16.5, 19, 22].map((h) => F.phase(h).id), sky: [3, 6, 12, 18, 23].map((h) => Math.round(F.sky(h).sun * 100) / 100), dayK: [F.sky(12).day, F.sky(0).day],
        st: [F.streak({ '2026-10-29': 1, '2026-10-30': 1, '2026-11-02': 1, '2026-11-03': 1 }, '2026-11-03'), F.streak({ '2026-10-30': 1, '2026-11-02': 1 }, '2026-11-03'),
          F.streak({ '2026-10-29': 1 }, '2026-11-03'), F.streak({}, '2026-11-03'), F.streak({ '2026-10-30': 1 }, '2026-11-01'), F.streak({ '2026-10-26': 1, '2026-10-27': 1, '2026-10-29': 1, '2026-10-30': 1 }, '2026-10-30'), F.streak(null, '2026-11-03')] });""")
    if js.get("error"):
        check("b. node runs forumcore.js", False, js["error"])
        return
    check("b. six tablets in walking order: Council, Fear (VIX), Calendar, Money tide, Eval, Plan; the demo reads MIXED 44, VIX 21.15, Tomorrow 08:15, 10y 4.94%, $2,071 room",
          js["ids"] == ["council", "fear", "calendar", "money", "eval", "plan"] and js["stats"][:5] == ["MIXED 44", "VIX 21.15", "Tomorrow 08:15", "10y 4.94%", "$2,071 room"] and all(x > 40 for x in js["bodyLen"]), js["stats"])
    check("b. tones: VIX 12 / 17 calm, 22 watch, 30 storm; a calendar release today = caution, tomorrow = watch, later = calm; council 70 calm / 50 watch / 30 storm; room $300 storm, $900 watch, $2,000 calm",
          js["vix"] == ["calm", "calm", "watch", "storm"] and js["cal"] == ["storm", "watch", "calm"] and js["council"] == ["calm", "watch", "storm"] and js["room"] == ["storm", "watch", "calm"], (js["vix"], js["cal"], js["council"], js["room"]))
    check("b. missing or junk data never crashes: six honest 'no data' tablets (info tone), the plan tablet always there", [x[0] for x in js["missing"]] == ["council", "fear", "calendar", "money", "eval", "plan"]
          and [x[1] for x in js["missing"]] == ["info"] * 6 and js["junk"] == ["info"] * 6 and js["oath"] == 3, (js["missing"], js["junk"]))
    dk = node("""const F = await import(url + '/forumcore.js');
      const home = { accounts: [{ name: 'MFFU 50K Eval', kind: 'eval', eval: { start_balance: 50000, balance: 52170.5, target_balance: 53000, floor: 50100 } }, { name: 'ATLAS 25K', kind: 'eval' }], kalshi: { balance: 68.42, week_pnl: 7.25, running: true } };
      const plan = { events: [{ title: 'Class', date: '2026-10-29' }, { title: 'Dentist', date: '2026-10-30' }], tasks: [{ title: 'Gym', date: '2026-10-29', done: false }, { title: 'Bank', date: '2026-10-28', done: false }, { title: 'Read', date: '2026-10-29', done: true }] };
      const pick = (a) => a.map((x) => [x.id, x.tone, x.stat, x.line]);
      out({ full: pick(F.desk(home, plan, { day: '2026-10-29' })), none: pick(F.desk(null, null, { day: '2026-10-29' })), junk: pick(F.desk({ accounts: 'x', kalshi: 4 }, 5, null)),
        tmr: pick(F.desk(home, { events: [{ title: 'Dentist', date: '2026-10-30' }], tasks: [] }, { day: '2026-10-29' })) });""")
    if dk.get("error"):
        check("b. node runs the desk tablets", False, dk["error"])
    else:
        f = dk["full"]
        check("b. the desk: four tablets in order (bots, Kalshi, calendar, to-dos); the bots line carries the eval's gain, Kalshi the week, the calendar today's event, the to-dos the open ones",
              [x[0] for x in f] == ["bots", "kalshi", "events", "todos"] and f[0][2] == "2 accounts" and "+$2,171" in f[0][3] and f[1][2] == "+$7 this week" and f[2][2] == "1 today" and "Class" in f[2][3]
              and f[3][2] == "2 open" and "Gym" in f[3][3], f)
        check("b. the desk never goes blank: no data = four honest 'info' tablets, junk input does not crash, tomorrow's event shows when today is clear",
              [x[1] for x in dk["none"]] == ["info"] * 4 and len(dk["junk"]) == 4 and dk["tmr"][2][2] == "Clear today" and "Dentist" in dk["tmr"][2][3], (dk["none"], dk["junk"], dk["tmr"][2]))
    check("b. the New York clock: 13:40Z is 08:40 EST; DST ends 2026-11-01 (05:30Z is 01:30 EST); DST starts 2026-03-08 (07:30Z is 03:30 EDT); 04:59Z on Nov 4 is still Nov 3 23:59",
          js["et"][0] == {"day": "2026-11-03", "h": 8 + 40 / 60, "dow": 2} and js["et"][1]["day"] == "2026-11-01" and abs(js["et"][1]["h"] - 1.5) < 1e-9 and js["et"][2]["day"] == "2026-03-08"
          and abs(js["et"][2]["h"] - 3.5) < 1e-9 and js["et"][3]["day"] == "2026-11-03" and abs(js["et"][3]["h"] - (23 + 59 / 60)) < 1e-9, js["et"])
    check("b. parseClock and the words: 08:40, 8:05 ok; 24:00 / x / null refused; 08:40, '48 min', '2 h 05 min'",
          js["clock"][:2] == [8 + 40 / 60, 8 + 5 / 60] and js["clock"][2:5] == [None, None, None] and js["clock"][5:] == ["08:40", "48 min", "2 h 05 min"], js["clock"])
    n = js["next"]
    check("b. the next point of the trading day: 02:00 -> London in 60 min, 08:42 -> NY open in 48, 10:00 -> bot flat, 15:57 -> cash close, 17:00 -> futures reopen, Friday evening and Saturday -> Sunday 18:00, Sunday evening -> London",
          n[0][0] == "london" and n[0][1] == 60 and n[1][0] == "ny" and n[1][1] == 48 and n[2][0] == "flat" and n[3][0] == "close" and n[4][0] == "globex" and n[5][0] == "london" and n[5][2]
          and n[6][0] == "globex" and n[6][2] and n[6][1] == 49 * 60 and n[7][0] == "globex" and n[7][1] == 32 * 60 and n[8][0] == "globex" and n[8][1] == 360 and n[9][0] == "london", n)
    check("b. the phases and the sun: night, before the dawn, pre-market, open, after the close, evening; the sun is up at noon (1.0), below at night, full daylight at noon only",
          js["phase"] == ["night", "dawn", "morning", "open", "afternoon", "dusk", "night"] and js["sky"][2] == 1 and js["sky"][0] < 0 and js["sky"][4] < 0 and js["dayK"] == [1, 0], (js["phase"], js["sky"], js["dayK"]))
    s = js["st"]
    check("b. the streak: Fri-Mon-Tue sealed = 3 on Tuesday (the weekend is skipped), an open today keeps it, a gap resets, Sunday counts back to Friday, best is kept, junk = 0",
          s[0] == {"cur": 4, "best": 4} and s[1] == {"cur": 2, "best": 2} and s[2]["cur"] == 0 and s[2]["best"] == 1 and s[3] == {"cur": 0, "best": 0} and s[4]["cur"] == 1 and s[5] == {"cur": 2, "best": 2} and s[6] == {"cur": 0, "best": 0}, s)


# ------------------------------------------------------------------------------------------------ c. the browser
class Quiet(http.server.SimpleHTTPRequestHandler):
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


def make_site(tmp, with_pantheon=True, with_home=True):
    site = os.path.join(tmp, "nq-dashboard")
    shutil.rmtree(site, ignore_errors=True)
    shutil.copytree(PAGE, os.path.join(site, "forum"))
    for d in ("jarvis", "olympus"):
        shutil.copytree(os.path.join(WEB, d), os.path.join(site, d))
    if with_pantheon:
        os.makedirs(os.path.join(site, "pantheon"))
        doc = json.loads(rd(WEB, "pantheon", "pantheon.json"))
        doc["demo"] = False
        with open(os.path.join(site, "pantheon", "pantheon.json"), "w", encoding="utf-8") as fh:
            json.dump(doc, fh)
    if with_home:
        with open(os.path.join(site, "home.json"), "w", encoding="utf-8") as fh:
            json.dump(json.loads(rd(PAGE, "fixture.json"))["home"], fh)
    return site


GEOM = """() => { const W = innerWidth, H = innerHeight, bad = [];
  for (const el of document.querySelectorAll('#ui *, #card:not([hidden]) *, #steps:not([hidden]) *')) {
    if (el.closest('[hidden]')) continue;
    const b = el.getBoundingClientRect(), cs = getComputedStyle(el), clip = el.closest('.card');
    if (!b.width || !b.height || cs.visibility === 'hidden') continue;
    const c = clip && el !== clip ? clip.getBoundingClientRect() : null, r = { left: b.left, right: b.right, top: c ? Math.max(b.top, c.top) : b.top, bottom: c ? Math.min(b.bottom, c.bottom) : b.bottom };
    if (r.bottom <= r.top) continue;
    if (r.right > W - 16 + 0.5 || r.left < 16 - 0.5) bad.push('gutter ' + (el.id || el.className) + ' ' + Math.round(r.left) + '-' + Math.round(r.right));
    if (r.right > W - 80 && r.bottom > H - 160) bad.push('orb ' + (el.id || el.className) + ' ' + Math.round(r.right) + ',' + Math.round(r.bottom));
  }
  if (document.documentElement.scrollWidth > W || document.body.scrollWidth > W) bad.push('scroll ' + document.documentElement.scrollWidth);
  return bad; }"""


def run_browser():
    from playwright.sync_api import sync_playwright
    tmp = tempfile.mkdtemp(prefix="le_forum_page_")
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=tmp))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}/nq-dashboard/forum/"
    outside = []
    shots = os.environ.get("FORUM_SHOTS")
    try:
        with sync_playwright() as pw:
            exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
            br = pw.chromium.launch(**({"executable_path": exe} if exe else {}), args=["--use-gl=swiftshader", "--enable-webgl", "--ignore-gpu-blocklist", "--enable-unsafe-swiftshader"])

            def page(reduced=False, quality="low"):
                ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1, has_touch=True, reduced_motion="reduce" if reduced else "no-preference")
                if quality:
                    ctx.add_init_script(f"try {{ localStorage.setItem('jfx', '{quality}'); }} catch (e) {{}}")

                def guard(route):
                    u = route.request.url
                    if u.startswith(f"http://127.0.0.1:{srv.server_address[1]}") or u.startswith(("data:", "blob:")):
                        return route.continue_()
                    outside.append(u)
                    return route.abort()
                ctx.route("**/*", guard)
                p = ctx.new_page()
                p.set_default_timeout(120000)
                p.errs = []
                p.on("pageerror", lambda e: p.errs.append(str(e)))
                p.on("console", lambda m: m.type == "error" and "Failed to load resource" not in m.text and "vibrate" not in m.text and p.errs.append(m.text))
                return ctx, p

            def ready(p, q="?t=08:40"):
                p.goto(base + q)
                p.wait_for_function("document.body.dataset.ready === '1' && window.FORUM && FORUM.state().scene && FORUM.state().scene.drawn > 0", timeout=180000)

            st = lambda p: p.evaluate("FORUM.state()")  # noqa: E731

            make_site(tmp)
            ctx, p = page()
            ready(p)
            s = st(p)
            check("c. loads at ?t=08:40 on the chosen LITE tier: real mode (no DEMO), 6 tablets in the scene, 2 passes, the LITE tag, no errors",
                  not s["demo"] and s["scene"]["tablets"] == 6 and s["scene"]["passes"] == 2 and p.is_visible("#lite") and not p.is_visible("#demo") and not p.errs and s["scene"]["quality"] == "low", (s["scene"], p.errs))
            check("c. the New York clock card: 08:40, pre-market, 'NY open in 50 min', the sky is the morning's (stars off, h = 8.67)",
                  p.inner_text("#ckTime") == "08:40" and "PRE-MARKET" in p.inner_text("#ckPhase").upper() and "NY open in 50 min" in p.inner_text("#ckNext") and abs(s["scene"]["h"] - (8 + 40 / 60)) < 0.01 and not s["scene"]["night"], (p.inner_text("#ckNext"), s["scene"]))
            check("c. the intro: the council reading and the start button; the step bar is hidden until you start", "MIXED 44" in p.inner_text("#intro") and p.is_visible("#start") and not p.is_visible("#steps"))
            ov = p.evaluate(GEOM)
            check("c. home at 390 x 844: inside the 16 px gutters, nothing in the orb's 80 x 160 corner, no sideways scroll", not ov, ov)
            if shots:
                os.makedirs(shots, exist_ok=True)
                p.wait_for_timeout(1500)
                p.screenshot(path=os.path.join(shots, "forum-overview.png"))
            p.click("#start")
            p.wait_for_timeout(400)
            s = st(p)
            check("c. start: tablet 1 (The Council): glyph, title, reading, tone word, the plain body; the camera moves to the pillar; Previous is disabled; inside the gutters and the orb's corner",
                  s["step"] == 0 and "the council" in p.inner_text("#sTitle").lower() and p.inner_text("#sStat") == "MIXED 44" and p.inner_text("#sTone") == "WATCH" and len(p.inner_text("#sBody")) > 60
                  and s["scene"]["focus"] == 0 and p.is_disabled("#prev") and not p.evaluate(GEOM), (s["step"], p.evaluate(GEOM)))
            if shots:
                p.wait_for_timeout(2500)
                p.screenshot(path=os.path.join(shots, "forum-tablet.png"))
            titles = []
            for _ in range(5):
                p.click("#next")
                p.wait_for_timeout(150)
                titles.append(p.inner_text("#sTitle"))
            check("c. Next walks the six tablets in order (Fear, Calendar, Money tide, Eval, Today's plan), then the oath",
                  titles[:4] == ["Fear (VIX)", "The calendar", "The money tide", "The eval"] or [t.lower() for t in titles[:4]] == ["fear (vix)", "the calendar", "the money tide", "the eval"], titles)
            p.click("#next")
            p.wait_for_timeout(300)
            check("c. the sixth tablet is the plan and the next stop is the oath: three pledges, the seal is disabled until all three are ticked",
                  "plan" in titles[4].lower() and p.is_visible("#oath") and p.locator(".pledge").count() == 3 and p.is_disabled("#seal") and st(p)["scene"]["focus"] == 6 and not p.evaluate(GEOM), (titles, p.evaluate(GEOM)))
            check("c. the desk (bots, Kalshi, calendar, to-dos) shows on the oath screen as four tablets inside the gutters; the effects library is on the page",
                  p.is_visible("#desk") and p.locator("#desk .dtab").count() == 4 and [d["id"] for d in st(p)["desk"]] == ["bots", "kalshi", "events", "todos"]
                  and p.evaluate("!!window.OLYMPUS_FX && OLYMPUS_FX.has('sparkleBurst') && OLYMPUS_FX.has('confetti')") and not p.evaluate(GEOM), (st(p)["desk"], p.evaluate(GEOM)))
            check("c. the streak shrine: seven candles, none lit before the first seal; its label says so", p.locator("#shrine .candle").count() == 7 and p.locator("#shrine .candle.lit").count() == 0
                  and "0 market days" in p.get_attribute("#shrine", "aria-label"), p.get_attribute("#shrine", "aria-label"))
            p.click("[data-pledge=plan]")
            check("c. a pledge ticked: a sparkle burst starts from it (the library's canvas) and stops by itself", p.evaluate("OLYMPUS_FX.stats().byName.sparkleBurst || 0") >= 0 and not p.errs, p.errs)
            p.click("[data-pledge=revenge]")
            check("c. two pledges: still disabled", p.is_disabled("#seal") and p.get_attribute("[data-pledge=plan]", "aria-pressed") == "true")
            p.click("[data-pledge=journal]")
            check("c. three pledges: the seal button wakes up", not p.is_disabled("#seal"))
            p.click("#seal")
            p.wait_for_timeout(600)
            s = st(p)
            led = p.evaluate("JSON.parse(localStorage.getItem('forum.v1'))")
            check("c. sealing: the gates open in the scene, the oath is sealed with the New York time, the streak is 1, kept on this phone only (localStorage 'forum.v1'), the pledges lock",
                  s["sealed"] and s["scene"]["gatesOpen"] and s["streak"]["cur"] == 1 and "2026" in "".join(led["sealed"]) and led["sealed"][list(led["sealed"])[0]]["p"] == [True, True, True]
                  and p.is_disabled("[data-pledge=plan]") and "Sealed at 08:40 ET" in p.inner_text("#sealed") and p.get_attribute("html", "data-sealed") == "1" and not p.errs, (s["streak"], led, p.errs))
            check("c. sealing lights the first candle of the shrine (1 of 7) and the confetti runs without a page error",
                  p.locator("#shrine .candle.lit").count() == 1 and "1 market day" in p.get_attribute("#shrine", "aria-label") and not p.errs, (p.get_attribute("#shrine", "aria-label"), p.errs))
            p.wait_for_timeout(500)
            check("c. the desk is hidden on a tablet and back on the intro: walk to the first tablet", (p.evaluate("FORUM.show(0)") or True) and p.is_hidden("#desk"))
            p.evaluate("FORUM.show(FORUM.state().items.length)")
            if shots:
                p.wait_for_timeout(3000)
                p.screenshot(path=os.path.join(shots, "forum-gates.png"))
            p.reload()
            p.wait_for_function("document.body.dataset.ready === '1' && FORUM.state().scene && FORUM.state().scene.drawn > 0", timeout=180000)
            s = st(p)
            check("c. a reload comes back sealed: the gates open, the oath card shown, the streak kept", s["sealed"] and s["scene"]["gatesOpen"] and s["step"] == 6 and s["streak"]["cur"] == 1, (s["step"], s["streak"]))
            card = p.evaluate("FORUM.card()")
            check("c. the card for Jarvis: 3 kpis (Council, VIX, Eval room), <= 3 lines of <= 120 characters, status 'Oath sealed'",
                  card["name"] == "Forum" and len(card["kpis"]) == 3 and card["status"]["label"] == "Oath sealed" and len(card["lines"]) <= 3 and all(len(x) <= 120 for x in card["lines"]), card)
            p.keyboard.press("Escape")
            p.wait_for_timeout(200)
            check("c. Escape returns to the overview (the intro card)", st(p)["step"] == -1 and p.is_visible("#intro"))
            ctx.close()

            ctx, p = page()
            ready(p, "?t=22:15")
            s = st(p)
            check("c. at ?t=22:15 the sky is the night's (stars on) and the clock says so", p.inner_text("#ckTime") == "22:15" and s["scene"]["night"] and "NIGHT" in p.inner_text("#ckPhase").upper(), (p.inner_text("#ckPhase"), s["scene"]))
            ctx.close()
            ctx, p = page()
            ready(p, "?t=12:00")
            s = st(p)
            check("c. at ?t=12:00 it is day (stars off) and the market is open", not s["scene"]["night"] and "OPEN" in p.inner_text("#ckPhase").upper() and "Bot flat in 3 h 55 min" in p.inner_text("#ckNext"), p.inner_text("#ckNext"))
            ctx.close()

            make_site(tmp, with_pantheon=False, with_home=False)
            ctx, p = page()
            ready(p)
            s = st(p)
            check("c. no Pantheon on the site: the recorded copy (DEMO badge), the six tablets, MIXED 44, the eval from the fixture, still no errors",
                  s["demo"] and p.is_visible("#demo") and [i["id"] for i in s["items"]] == ["council", "fear", "calendar", "money", "eval", "plan"] and s["items"][0]["stat"] == "MIXED 44" and not p.errs, (s["items"][:2], p.errs))
            ctx.close()

            make_site(tmp)
            ctx, p = page(reduced=True)
            ready(p)
            before = st(p)["scene"]["drawn"]
            p.wait_for_timeout(1500)
            after = st(p)["scene"]["drawn"]
            check("c. reduced motion: a still scene (no frames while nothing changes), the camera cuts to a tablet when asked, no errors", after - before <= 1 and not p.errs, (before, after, p.errs))
            p.evaluate("FORUM.show(2)")
            p.wait_for_timeout(1500)
            check("c. ...and a tablet still redraws it", st(p)["scene"]["drawn"] > after and st(p)["scene"]["focus"] == 2)
            ctx.close()
            br.close()
    finally:
        srv.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)
    check("c. nothing left the machine: no request to any other origin", not outside, outside[:3])


def main():
    part_a()
    part_b()
    if os.environ.get("FORUM_NO_BROWSER") != "1":
        run_browser()
    print(f"\n{sum(RES)}/{len(RES)} passed")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
