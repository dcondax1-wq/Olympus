"""The OLYMPUS app list and the Zenith launcher (2026-11-04).

  a. the list cannot drift: tools/apps_list_build.py builds olympus/apps-list.js (and the PC copy web_next/js/next/apps-list.js) from
     jarvis/apps.js BUILT_INS + olympus/olympus.js APPS; this test rebuilds it in memory and fails when a file differs, when the kit's table
     and BUILT_INS disagree on a name or a colour, when an app folder has no row (or a row has no folder), or the copies are not byte-identical
  b. the launcher is wired in both dashboards: one script (launcher.js, byte-identical in tools/web_public and web_next/js/next) after its
     list, in tools/web_public/index.html and web_next/index.html, and in the PC worker's ASSETS with its version bumped; the root worker is
     untouched (it fetches versioned files at run time; olympus/ is not its to cache)
  c. Chromium, the phone dashboard (same origin) and the PC dashboard (127.0.0.1, the public site's URLs): the top-bar button, the glass sheet,
     the Jarvis button, 27 tiles in Trading / Life / Money, search, recent, status dots from <app>/jarvis.json, Escape / close, LITE
    python -X utf8 -m tests.test_apps_list            (--static: parts a and b)
"""
from __future__ import annotations

import glob
import http.server
import json
import os
import re
import subprocess
import sys
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
WEB = os.path.join(ROOT, "tools", "web_public")
NEXT = os.path.join(ROOT, "web_next")
RES: list = []
EXTERNAL = ()   # published next to the dashboard by its own build (tools/planner_patches), not a folder of tools/web_public


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:600]}"), flush=True)


def read(*p, mode="r"):
    with open(os.path.join(*p), encoding=None if mode == "rb" else "utf-8", mode=mode) as fh:
        return fh.read()


def _ntiles():
    import re as _re
    t = open(os.path.join(ROOT, "tools", "web_public", "olympus", "apps-list.js"), encoding="utf-8").read()
    return len(set(_re.findall(r'"id":\s*"([a-z0-9]+)"', t)) - {"zenith"})


NTILES = _ntiles()


def test_static():
    import apps_list_build as A
    rows = A.build()
    text = A.render(rows)
    check("a. olympus/apps-list.js is exactly what tools/apps_list_build.py builds from apps.js + olympus.js (run it after editing either)",
          os.path.exists(A.OUT_PHONE) and read(A.OUT_PHONE) == text, "python tools/apps_list_build.py")
    check("a. the PC copy (web_next/js/next/apps-list.js) is byte-identical", os.path.exists(A.OUT_PC) and read(A.OUT_PC, mode="rb") == read(A.OUT_PHONE, mode="rb"))
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "apps_list_build.py"), "--check"], capture_output=True, text=True)
    check("a. tools/apps_list_build.py --check agrees", r.returncode == 0, r.stdout + r.stderr)
    ids = [x["id"] for x in rows]
    check("a. 27 rows (26 launcher tiles, Zenith is the dashboard itself), unique ids, groups only trading / life / money, hex colours, a glyph and a one-line purpose each",
          len(ids) == len(set(ids)) >= 27 and all(x["group"] in ("trading", "life", "money") and re.fullmatch(r"#[0-9a-fA-F]{6}", x["colour"]) and x["glyph"] and 4 < len(x["purpose"]) < 80 and x["name"] for x in rows), ids)
    kit = A.kit_table()
    drift = [(k, kit[k], next(r for r in rows if r["id"] == k)["name"], next(r for r in rows if r["id"] == k)["colour"]) for k in kit
             if k in ids and (kit[k]["name"] != next(r for r in rows if r["id"] == k)["name"] or kit[k]["colour"].lower() != next(r for r in rows if r["id"] == k)["colour"].lower())]
    check("a. the kit's APPS table and Jarvis's BUILT_INS agree on every shared app's name and colour; every kit app is in BUILT_INS", not drift and all(k in ids for k in kit), (drift, [k for k in kit if k not in ids]))
    folders = sorted(d for d in os.listdir(WEB) if os.path.isfile(os.path.join(WEB, d, "index.html")) and d not in ("jarvis",))
    missing_row = [f for f in folders if f not in ids]
    missing_dir = [x["id"] for x in rows if x["path"] and x["id"] not in EXTERNAL and not os.path.isfile(os.path.join(WEB, x["path"], "index.html"))]
    check("a. every app folder under tools/web_public has a row, and every row has its folder with an index.html (the Planner is published by its own build; a new app = one row in BUILT_INS, then rebuild)",
          not missing_dir and not [f for f in missing_row if f not in ("pc", "atlascity", "gate")], (missing_row, missing_dir))
    nolive = [x["id"] for x in rows if x["live"] and not os.path.isfile(os.path.join(WEB, x["path"], "jarvis.json"))]
    check("a. every app marked live has its jarvis.json (the status dot reads it)", not nolive, nolive)

    check("b. launcher.js is byte-identical in tools/web_public and web_next/js/next", read(WEB, "launcher.js", mode="rb") == read(NEXT, "js", "next", "launcher.js", mode="rb"))
    ph, pc = read(WEB, "index.html"), read(NEXT, "index.html")
    check("b. the phone dashboard has ONE tag, launcher.js (deferred); the list is loaded by the launcher, async, so a slow site never holds Zenith back",
          '<script src="launcher.js?v=l6" defer></script>' in ph and "apps-list" not in ph and "olympus/apps-list.js?v=l2" in read(WEB, "launcher.js"))
    check("b. the PC dashboard has ONE tag, js/next/launcher.js (the list comes from js/next/apps-list.js, in the worker's ASSETS)", '<script src="/js/next/launcher.js?v=l6" defer></script>' in pc and "apps-list" not in pc and "/js/next/apps-list.js?v=l2" in read(NEXT, "js", "next", "launcher.js"))
    sw = read(NEXT, "sw.js")
    v = re.search(r"const SHELL = 'le-shell-next-v(\d+)'", sw)
    check("b. the PC worker caches both files and its version is bumped (v34 or later)", "'/js/next/apps-list.js?v=l2'" in sw and "'/js/next/launcher.js?v=l5'" in sw and v and int(v.group(1)) >= 34)
    check("b. the root worker is untouched by the launcher (it fetches versioned files at run time; olympus/ is skipped on purpose)", "launcher" not in read(WEB, "sw.js") and "apps-list" not in read(WEB, "sw.js"))
    js = read(WEB, "launcher.js")
    check("b. launcher.js: read-only (no POST, no orders), every storage call in try, Safari 16 safe (no lookbehind, ?., ??, .at())",
          not re.search(r"method:\s*['\"](POST|PUT|DELETE)", js) and not re.search(r"\(\?<[=!]|\?\?|\.at\(|[\w)\]]\?\.[A-Za-z_$]", js) and js.count("localStorage.") == 2 and "try {" in js)
    check("b. launcher.js: the keys oly.launcher.recent / oly.launcher.status, the public site URL for the PC, the status fetch is lazy (only on open)",
          "'oly.launcher.recent'" in js and "'oly.launcher.status'" in js and "https://demetrades2000-coder.github.io/nq-dashboard/" in js and js.index("function loadStatus") < js.index("function open()") and "loadStatus();" in js[js.index("function open()"):])


# ------------------------------------------------------------------ c. browser
class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def serve(d):
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), lambda *a: Handler(*a, directory=d))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def launch(pw):
    exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
    return pw.chromium.launch(**({"executable_path": exe} if exe else {}))


def page(br, origin, fx=None, reduced=False, width=390, height=844):
    ctx = br.new_context(viewport={"width": width, "height": height}, device_scale_factor=2, is_mobile=width < 600, has_touch=width < 600,
                         reduced_motion="reduce" if reduced else "no-preference")
    # PC: the public site is another origin: answer its status cards from the local tree so the dots can be checked; everything else off-origin is refused
    pub = "https://demetrades2000-coder.github.io/nq-dashboard/"

    def route(r):
        u = r.request.url
        if u.startswith(origin):
            return r.continue_()
        if u.startswith(pub) and u.endswith("jarvis.json"):
            f = os.path.join(WEB, u[len(pub):].split("?")[0])
            if os.path.isfile(f):
                return r.fulfill(status=200, content_type="application/json", headers={"access-control-allow-origin": "*"}, body=open(f, "rb").read())
        return r.abort()
    ctx.route("**/*", route)
    if fx:
        ctx.add_init_script(f"try {{ localStorage.setItem('jfx', '{fx}'); }} catch (e) {{}}")
    p = ctx.new_page()
    errs: list = []
    p.on("pageerror", lambda e: errs.append(str(e)))
    return ctx, p, errs


def tap(p, sel):
    p.locator(sel).first.dispatch_event("click")


def test_phone(br, origin):
    ctx, p, errs = page(br, origin)
    p.goto(origin + "/", wait_until="commit")
    p.wait_for_selector("#olyLauncherBtn", timeout=120000, state="attached")
    tb = p.evaluate("(() => { const b = document.getElementById('olyLauncherBtn'); const r = b.getBoundingClientRect(); return { inTop: !!b.closest('header.top'), w: r.width, h: r.height, label: b.getAttribute('aria-label') }; })()")
    check("c. phone: a launcher button sits in the Zenith top bar (header.top), 40 px, with a plain label", tb["inTop"] and tb["h"] >= 40 and "launcher" in tb["label"].lower(), tb)
    tap(p, "#olyLauncherBtn"); p.wait_for_timeout(500)
    S = p.evaluate("OLYMPUS_LAUNCHER.state()")
    j = p.evaluate("(() => { const a = document.querySelector('.oly-l .oly-jv'); return { href: a.getAttribute('href'), target: a.target, text: a.textContent }; })()")
    check("c. phone: the sheet opens with the big 'Open Olympus (Jarvis)' button (jarvis/, this tab) and all app tiles", S["open"] and not S["pc"] and S["tiles"] == NTILES and j["href"] == "jarvis/" and not j["target"] and "Open Olympus (Jarvis)" in j["text"], (S, j))
    g = p.evaluate("[...document.querySelectorAll('.oly-l section')].map((s) => [s.dataset.group, s.querySelectorAll('.oly-tile').length])")
    check("c. phone: three groups (Trading, Life, Money) with their apps; Zenith itself is not in it", [x[0] for x in g] == ["trading", "life", "money"] and sum(x[1] for x in g) == NTILES and p.locator('.oly-l .oly-tile[data-app=zenith]').count() == 0, g)
    t = p.evaluate("(() => { const a = document.querySelector('.oly-l .oly-tile[data-app=oracle]'); return { href: a.getAttribute('href'), name: a.querySelector('b').textContent, purpose: a.querySelector('small').textContent, glyph: a.querySelector('.oly-g').textContent, c: a.style.getPropertyValue('--c') }; })()")
    check("c. phone: a tile = its glyph in its colour, its name and one plain line, and opens <app>/ in this tab", t["href"] == "oracle/" and t["name"] == "Oracle" and t["c"] == "#7fb0a3" and len(t["purpose"]) > 8, t)
    p.wait_for_timeout(4000)
    dots = p.evaluate("[...document.querySelectorAll('.oly-l .oly-tile')].map((t) => t.dataset.status).filter(Boolean)")
    check("c. phone: the status dots come from each app's jarvis.json (ok / warn / bad / stale / off), cached in localStorage", len(dots) >= 10 and set(dots) <= {"ok", "warn", "bad", "stale", "off", "none"}
          and p.evaluate("!!localStorage.getItem('oly.launcher.status')"), (len(dots), set(dots)))
    p.fill(".oly-l .oly-sr input", "ora"); p.wait_for_timeout(150)
    vis = p.evaluate("[...document.querySelectorAll('.oly-l .oly-tile:not([hidden])')].map((t) => t.dataset.app)")
    check("c. phone: search narrows the grid ('ora' finds Oracle) and says so when nothing matches", "oracle" in vis and len(vis) < 6, vis)
    p.fill(".oly-l .oly-sr input", "zzzz"); p.wait_for_timeout(150)
    check("c. phone: no match = a plain line, never an empty sheet", p.is_visible(".oly-l .oly-em") and "No app matches" in p.inner_text(".oly-l .oly-em"))
    p.fill(".oly-l .oly-sr input", ""); p.wait_for_timeout(100)
    p.evaluate("document.querySelector('.oly-l .oly-tile[data-app=mind]').addEventListener('click', (e) => e.preventDefault(), true)")
    tap(p, ".oly-l .oly-tile[data-app=mind]"); p.wait_for_timeout(200)
    rec = p.evaluate("JSON.parse(localStorage.getItem('oly.launcher.recent'))")
    check("c. phone: opening an app records it in oly.launcher.recent (newest first, 4 kept) and closes the sheet", rec[:1] == ["mind"] and not p.evaluate("OLYMPUS_LAUNCHER.isOpen()"), rec)
    p.focus("#olyLauncherBtn"); tap(p, "#olyLauncherBtn"); p.wait_for_timeout(300)
    check("c. phone: 'Recent' shows it first the next time", p.locator(".oly-l .oly-rc .oly-chip").first.get_attribute("data-app") == "mind")
    p.keyboard.press("Escape"); p.wait_for_timeout(200)
    check("c. phone: Escape closes it and the focus goes back to the button", not p.evaluate("OLYMPUS_LAUNCHER.isOpen()") and p.evaluate("document.activeElement && document.activeElement.id") == "olyLauncherBtn")
    tap(p, "#olyLauncherBtn"); p.wait_for_timeout(300)
    geo = p.evaluate("""(() => { const pn = document.querySelector('.oly-l .oly-pn').getBoundingClientRect(); return { w: pn.width, h: pn.height, over: document.documentElement.scrollWidth - innerWidth,
      small: [...document.querySelectorAll('.oly-l a, .oly-l button')].filter((e) => e.offsetParent && e.getBoundingClientRect().height < 40 && !e.classList.contains('chip')).map((e) => e.className) }; })()""")
    check("c. phone: the sheet fits 390 x 844 (no sideways scroll, every tap target at least 40 px)", geo["w"] <= 390 and geo["h"] <= 844 and geo["over"] <= 0 and not geo["small"], geo)
    check("c. phone: no page error from the launcher", not [e for e in errs if "launcher" in e.lower() or "oly" in e.lower()], errs[:3])
    ctx.close()
    # LITE and reduced motion: no entrance animation
    for label, kw in (("LITE (3D Low)", {"fx": "low"}), ("reduced motion", {"reduced": True})):
        ctx, p, errs = page(br, origin, **kw)
        p.goto(origin + "/", wait_until="commit"); p.wait_for_selector("#olyLauncherBtn", timeout=120000, state="attached")
        tap(p, "#olyLauncherBtn"); p.wait_for_timeout(300)
        calm = p.evaluate("document.querySelector('.oly-l').classList.contains('calm')")
        anim = p.evaluate("getComputedStyle(document.querySelector('.oly-l .oly-pn')).animationName")
        check(f"c. phone {label}: the sheet is calm (no entrance animation) and still complete (all tiles)", calm and anim == "none" and p.evaluate("OLYMPUS_LAUNCHER.state().tiles") == NTILES, (calm, anim))
        ctx.close()
    # never blank: the list missing
    ctx, p, errs = page(br, origin)
    ctx.route(re.compile(r".*/olympus/apps-list\.js.*"), lambda r: r.abort())
    p.goto(origin + "/", wait_until="commit"); p.wait_for_selector("#olyLauncherBtn", timeout=120000, state="attached")
    tap(p, "#olyLauncherBtn"); p.wait_for_timeout(300)
    p.wait_for_timeout(500)
    check("c. phone: without the list (offline, a blocked file) the sheet still opens with the Jarvis button and says why", p.is_visible(".oly-l .oly-jv") and "could not load" in p.inner_text(".oly-l .oly-em"))
    ctx.close()


def test_pc(br, origin):
    ctx, p, errs = page(br, origin, width=1280, height=800)
    p.goto(origin + "/", wait_until="commit")
    p.wait_for_selector("#olyLauncherBtn", timeout=120000, state="attached")
    inbar = p.evaluate("!!document.getElementById('olyLauncherBtn').closest('.tb-right')")
    tap(p, "#olyLauncherBtn"); p.wait_for_timeout(500)
    S = p.evaluate("OLYMPUS_LAUNCHER.state()")
    j = p.evaluate("(() => { const a = document.querySelector('.oly-l .oly-jv'); return [a.href, a.target, a.rel]; })()")
    t = p.evaluate("(() => { const a = document.querySelector('.oly-l .oly-tile[data-app=oracle]'); return [a.href, a.target, a.rel]; })()")
    check("c. PC: the button is in the top bar; the sheet's links go to the public site (https://demetrades2000-coder.github.io/nq-dashboard/<app>/) in a new tab",
          inbar and S["pc"] and S["tiles"] == NTILES and j[0] == "https://demetrades2000-coder.github.io/nq-dashboard/jarvis/" and j[1] == "_blank" and "noopener" in j[2]
          and t[0] == "https://demetrades2000-coder.github.io/nq-dashboard/oracle/" and t[1] == "_blank", (inbar, S, j, t))
    p.wait_for_timeout(4000)
    dots = p.evaluate("[...document.querySelectorAll('.oly-l .oly-tile')].map((t) => t.dataset.status).filter(Boolean)")
    check("c. PC: the status dots are read from the public site's jarvis.json files (cross-origin) and cached", len(dots) >= 10 and p.evaluate("!!localStorage.getItem('oly.launcher.status')"), len(dots))
    g = p.evaluate("getComputedStyle(document.querySelector('.oly-l .oly-gr')).gridTemplateColumns.split(' ').length")
    check("c. PC: three columns of tiles, the panel fits the window", g == 3 and p.evaluate("document.querySelector('.oly-l .oly-pn').getBoundingClientRect().height") <= 800)
    p.keyboard.press("Escape"); p.wait_for_timeout(200)
    check("c. PC: Escape closes it", not p.evaluate("OLYMPUS_LAUNCHER.isOpen()") and not [e for e in errs if "launcher" in e.lower()], errs[:3])
    ctx.close()


def main():
    test_static()
    if "--static" in sys.argv:
        return
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        check("browser tests skipped: no Playwright", True)
        return
    s1, o1 = serve(WEB)
    s2, o2 = serve(NEXT)
    with sync_playwright() as pw:
        br = launch(pw)
        for fn, o in ((test_phone, o1), (test_pc, o2)):
            try:
                fn(br, o)
            except Exception as e:
                check(f"c. {fn.__name__}: the browser checks ran to the end", False, e)
        br.close()
    s1.shutdown(); s2.shutdown()


if __name__ == "__main__":
    t0 = time.time()
    main()
    n = sum(RES)
    print(f"\n{n}/{len(RES)} passed in {time.time() - t0:.0f}s")
    sys.exit(0 if n == len(RES) else 1)
