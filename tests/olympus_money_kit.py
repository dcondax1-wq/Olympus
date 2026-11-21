"""Shared helpers of tests/test_ares_page.py and tests/test_plutus_page.py (the two money apps, 2026-11-03).

A throw-away copy of the site (the app folder + ../olympus + the Jarvis assets the page links + optionally the data.json fixture)
served from 127.0.0.1, and a Playwright Chromium page at 390 x 844 that records every page error, console error and failed request.
"""
from __future__ import annotations

import functools
import glob
import http.server
import os
import shutil
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "tools", "web_public")
FIX = os.path.join(ROOT, "tests", "fixtures", "olympus_money", "data_min.json")
JARVIS_FILES = ("three.module.min.js", "orbitron.woff2", "rajdhani-400.woff2", "rajdhani-500.woff2", "rajdhani-600.woff2", "rajdhani-700.woff2", "icon-192.png",
                "ask.js")   # the kit adds the Ask Jarvis button (jarvis/ask.js) to every kit app since 2026-11-20 (olympus.js)
RES = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:500]}"), flush=True)


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def site(tmp, app, name, data=True, drop=()):
    """-> (server, url of the app page). `drop`: files of the app folder to delete (to test the fallbacks)."""
    base = os.path.join(tmp, name)
    shutil.copytree(os.path.join(WEB, app), os.path.join(base, app))
    shutil.copytree(os.path.join(WEB, "olympus"), os.path.join(base, "olympus"))
    os.makedirs(os.path.join(base, "jarvis"))
    for f in JARVIS_FILES:
        src = os.path.join(WEB, "jarvis", f)
        if os.path.exists(src):
            shutil.copy(src, os.path.join(base, "jarvis", f))
    link_assets(base)
    if data:
        shutil.copy(FIX, os.path.join(base, "data.json"))
    for f in drop:
        os.remove(os.path.join(base, app, f))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(_Quiet, directory=base))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}/{app}/"


def root_readers(base):
    """The site's root reader of the PC's status post (night-feedsB 2026-11-18: home_feed.js, loaded by the ZEUS Trading apps before the
    kit) and what it imports, as on the real site: without a post (the tests' ntfy answers "{}") it leaves home.json / data.json alone."""
    for f in ("home_feed.js", "pc_feed.js", "status_feed.json", os.path.join("business", "payoutcoach.js")):
        src, out = os.path.join(WEB, f), os.path.join(base, f)
        if os.path.exists(src) and not os.path.exists(out):
            os.makedirs(os.path.dirname(out), exist_ok=True)
            shutil.copy(src, out)


def link_assets(base):
    """The built site always publishes assets/ (the CC0 sounds, scans and HDRIs the shared kit uses; tools/build_web_dashboard.py copies it).
    QA Round 7: without it the kit's first-tap UI sound asked for assets/audio/ui.m4a and ui.ogg and got two 404 console lines on every tap
    test of these throw-away sites, which no real visitor ever sees. A link (a copy where links are not allowed) keeps the copy cheap."""
    root_readers(base)
    dst = os.path.join(base, "assets")
    if os.path.exists(dst):
        return
    try:
        os.symlink(os.path.join(WEB, "assets"), dst, target_is_directory=True)
    except OSError:
        shutil.copytree(os.path.join(WEB, "assets"), dst)


def browser(pw):
    exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
    return pw.chromium.launch(**({"executable_path": exe} if exe else {}), args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader"])


def open_page(br, url, errs, hook, reduced=False, wait_site=True):
    ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, reduced_motion="reduce" if reduced else "no-preference")
    p = ctx.new_page()
    p.on("pageerror", lambda e: errs.append("pageerror: " + str(e)))
    p.on("console", lambda m: errs.append("console: " + m.text) if m.type == "error" else None)
    p.on("requestfailed", lambda r: errs.append("requestfailed: " + r.url))
    p.goto(url)
    p.wait_for_function(f"window.{hook} && window.{hook}.ready", timeout=150000)
    if wait_site:
        p.wait_for_function(f"window.{hook}.siteLoaded === true", timeout=150000)
    p.wait_for_timeout(600)
    return ctx, p


ORB_JS = """() => {
  const W = innerWidth, H = innerHeight, box = {l: W - 80, t: H - 160, r: W, b: H};
  return [...document.querySelectorAll('button, input, a:not(.oly-home), .sheet, .reason, .acct, .line')].filter((e) => {
    if (e.closest('[hidden]')) return false; let r = e.getBoundingClientRect(); if (!r.width || !r.height) return false;
    const sh = e !== document.getElementById('sheet') && e.closest('.sheet');
    if (sh) { const c = sh.getBoundingClientRect(); r = {left: Math.max(r.left, c.left), right: Math.min(r.right, c.right), top: Math.max(r.top, c.top), bottom: Math.min(r.bottom, c.bottom)}; if (r.bottom <= r.top) return false; }   // scrolled out of the sheet: clipped there
    return r.right > box.l && r.left < box.r && r.bottom > box.t && r.top < box.b; }).map((e) => e.id || e.className || e.tagName); }"""


def orb_hits(p):
    return p.evaluate(ORB_JS)


def tidy_errors(errs, allow=()):
    """errors that are not an allowed missing file (a 404 shows up as one console line + one failed request)"""
    return [e for e in errs if not any(a in e for a in allow) and "404" not in e]
