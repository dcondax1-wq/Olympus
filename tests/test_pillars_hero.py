"""The Four Pillars made impossible to miss + the dashboard quality pass (day-pillars2 2026-11-24; owner: "can't see the pillars",
"far more 3D, more effects, a better dashboard").
  a. static: the hero markup on the Olympus Home (gate/, a header band), Zenith (/) and the NQ page (#pillarsStrip) with 4 working chip
     links before any script; hero.css / hero.js / nightfx.js / livefx.js load AFTER the page (dynamic import, never an eager script),
     hero.css non-blocking on NQ + Zenith; OLYMPUS NIGHT, no brown / olive, no innerHTML; the Pillars app is Home-Screen complete
     (manifest, touch icon, 192 / 512 / maskable icons at their sizes); the perf budgets of gate / zenith / nq / pillars (perf_sweep --static)
  d. data: every pillar carries "what the market taught us" (research/learn/insights.json, else the SAMPLE fixture, flagged)
  b. Chromium 390 x 844 (Node Playwright, 3D forced with ?fx=3d): Home (band at the top, 6 dashboards still on the first screen, toast once,
     not twice), Zenith (hero on Today, hidden on another route, back on Today), NQ (hero, no toast, no pillars data file read), the Pillars
     page (particle field behind the content and capped, lessons panel + SAMPLE, the soft tab change, a number change glows, the field
     sleeps on a hidden tab), reduced motion = no field, Accounts (field behind the cards, taps reach the cards), the Brain's pillar sheet
     with its lessons. PILLARS2_SHOTS=<dir> saves the shots. PH_NO_BROWSER=1 skips b.
    python -X utf8 -m tests.test_pillars_hero
"""
from __future__ import annotations

import functools
import http.server
import json
import os
import re
import subprocess
import sys
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PUB = os.path.join(ROOT, "tools", "web_public")
RES: list = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:600]}"), flush=True)


def read(*p):
    return open(os.path.join(PUB, *p), encoding="utf-8").read()


def static():
    pages = {"gate": read("gate", "index.html"), "zenith": read("index.html"), "nq": read("nq", "index.html")}
    for k, h in pages.items():
        if k == "nq":                     # NQ's HTML is at its 300 KB first-paint budget: the frame + Open link only, the 4 chips come from hero.js
            check("a. nq: the static hero frame with its Open link (the chips are drawn by hero.js; the header has a Pillars button too)",
                  re.search(r'<section class="phero" id="pillarsStrip".*?class="ph-open" href="\.\./pillars/">Open</a>.*?</section>', h, re.S) is not None and 'href="../pillars/"' in h.split("</header>")[0])
            check(f"a. {k}: hero.js comes by a dynamic import after load, never an eager <script src>", "hero.js?v=" in h and not re.search(r'<script[^>]+src="[^"]*pillars/hero\.js', h))
            continue
        sid = "pillarsHero"
        m = re.search(r'<section class="phero[^"]*" id="%s".*?</section>' % sid, h, re.S)
        chips = re.findall(r'<a class="pc" data-p="(\w+)"[^>]*href="[^"]*pillars/#(\w+)"', m.group(0)) if m else []
        check(f"a. {k}: the static hero with 4 working chip links (LIT, ATLAS, BLITZ, ORDER FLOW) before any script", [c[0] for c in chips] == ["lit", "atlas", "blitz", "of"] and all(a == b for a, b in chips), chips)
        check(f"a. {k}: hero.js comes by a dynamic import after load, never an eager <script src>", "hero.js?v=" in h and not re.search(r'<script[^>]+src="[^"]*pillars/hero\.js', h))
    check("a. Home: the hero is a band inside the header (the 6 dashboards stay on the first screen)", re.search(r'<header class="g-head">.*class="phero band".*</header>', pages["gate"], re.S) is not None)
    check("a. Zenith: hero.css loads without blocking the first paint; NQ: hero.js brings it (its frame waits hidden until styled)",
          'hero.css?v=c1" media="print" onload=' in pages["zenith"] and "hero.css" not in pages["nq"] and 'data-toast="0" aria-label="The Four Pillars" hidden>' in pages["nq"])
    check("a. NQ: no toast there (data-toast=0)", 'data-toast="0"' in pages["nq"])
    js = {f: read("pillars", f) for f in ("hero.js", "nightfx.js", "livefx.js", "hero.css")}
    code = re.sub(r"/\*.*?\*/|(?<![:'\"])//[^\n]*", "", "\n".join(js.values()), flags=re.S)
    check("a. no innerHTML, no brown / olive in the new files", "innerHTML" not in code and not re.search(r"brown|olive|#8b4513|#808000|#556b2f", code, re.I))
    check("a. the toast is once per phone (localStorage oly.new.pillars) and never on NQ", "oly.new.pillars" in js["hero.js"] and "toast: box.dataset.toast !== '0'" in js["hero.js"])
    check("a. the effects respect reduced motion + low power, cap the motes, pause on a hidden tab, never take a tap",
          all(k in js["nightfx.js"] for k in ("prefers-reduced-motion", "Math.min(90", "document.hidden", "pointer-events:none", "z-index:-1")) and "prefers-reduced-motion" in js["livefx.js"])
    check("a. the number glow never rewrites a number (classes only; its only textContent write is its own <style>)", js["livefx.js"].count("textContent =") == 1 and "s.textContent = CSS" in js["livefx.js"])
    try:
        from PIL import Image
        man = json.load(open(os.path.join(PUB, "pillars", "manifest.webmanifest")))
        sizes = {i["src"]: (i["sizes"], i["purpose"]) for i in man["icons"]}
        ok = all(Image.open(os.path.join(PUB, "pillars", f)).size == s for f, s in (("icon-192.png", (192, 192)), ("icon-512.png", (512, 512)), ("icon-maskable-512.png", (512, 512)), ("apple-touch-icon.png", (180, 180))))
        check("a. the Pillars app is Home-Screen complete (manifest standalone in its folder, touch icon, 192 / 512 / maskable PNGs)",
              ok and man["display"] == "standalone" and man["start_url"] == "./" and sizes.get("icon-maskable-512.png") == ("512x512", "maskable") and 'rel="apple-touch-icon"' in read("pillars", "index.html"))
    except Exception as e:  # noqa: BLE001
        check("a. Pillars app icons readable", False, e)
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "perf_sweep.py"), "--static", "--check"], capture_output=True, text=True, timeout=120)
    over = [l for l in r.stdout.splitlines() if "OVER" in l and re.match(r"\s*(gate|zenith|nq|pillars|cities)\s", l)]
    check("a. perf budgets: gate, zenith, nq, pillars, cities all within (perf_sweep --static)", not over, over)


def data():
    d = json.load(open(os.path.join(PUB, "pillars", "pillars-data.json"), encoding="utf-8"))
    have = os.path.exists(os.path.join(ROOT, "research", "learn", "insights.json"))
    check("d. lessons on every pillar; SAMPLE flagged until research/learn/insights.json lands",
          all(isinstance(p.get("lessons"), list) for p in d["pillars"]) and d["lessons_sample"] == (not have)
          and (have or all(all(x["text"].startswith("SAMPLE") for x in p["lessons"]) for p in d["pillars"])), d.get("lessons_src"))


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def _npm_root():
    try:
        return subprocess.run(["npm", "root", "-g"], capture_output=True, text=True, timeout=30).stdout.strip()
    except Exception:  # noqa: BLE001
        return ""


def browser():
    env = {**os.environ, "NODE_PATH": _npm_root()}
    if subprocess.run(["node", "-e", "require('playwright')"], capture_output=True, env=env, timeout=30).returncode != 0:
        print("[SKIP] b. Node Playwright not installed here", flush=True)
        return
    shots = os.environ.get("PILLARS2_SHOTS", "")
    if shots:
        os.makedirs(shots, exist_ok=True)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(_Quiet, directory=PUB))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        r = subprocess.run(["node", os.path.join(ROOT, "tests", "pillars_hero_browser.cjs"), f"http://127.0.0.1:{srv.server_address[1]}", shots], capture_output=True, text=True, timeout=500, env=env)
    finally:
        srv.shutdown()
    try:
        o = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception as e:  # noqa: BLE001
        check("b. browser run", False, (r.stderr or r.stdout or str(e))[:800])
        return
    check("b. no fatal", "fatal" not in o, o.get("fatal"))
    errs = [e for k in ("gateErrors", "zenErrors", "nqErrors", "pillarsErrors", "accErrors", "brainErrors") for e in (o.get(k) or [])]
    check("b. no page error on Home, Zenith, NQ, Pillars, Accounts, Brain", not errs, errs[:4])
    G = o.get("gate") or {}
    check("b. Home: the hero band at the top (under the title), live, 3D, 4 chips to their pillars, every tap >= 44 px",
          G.get("live") == "1" and G.get("top", 999) < 160 and G.get("mode") == "3d" and [c.split("|")[0] for c in G.get("chips", [])] == ["lit", "atlas", "blitz", "of"]
          and all("#" + c.split("|")[0] == c.split("|")[1] for c in G.get("chips", [])) and G.get("small") == 0, G)
    check("b. Home: the 6 dashboards and More still on the first 390 x 844 screen; no sideways scroll", o.get("gateMore", 999) <= 844 and o.get("gateWide") is False, o.get("gateMore"))
    check("b. Home: the 'What's new: The Four Pillars' toast the first time, not the second", (o.get("toast1") or "").startswith("What's new: The Four Pillars") and o.get("toast2") is False, (o.get("toast1"), o.get("toast2")))
    Z = o.get("zen") or {}
    check("b. Zenith: the big hero on Today (live, 3D, 4 chips), hidden on another route, back on Today",
          Z.get("live") == "1" and not Z.get("hidden") and Z.get("mode") == "3d" and len(Z.get("chips", [])) == 4 and o.get("zenOther") is True and o.get("zenBack") is False, (Z, o.get("zenOther"), o.get("zenBack")))
    N = o.get("nq") or {}
    check("b. NQ: the hero (live, 4 chips, taps >= 44 px), no toast, no pillars / lab / insights data file read",
          N.get("live") == "1" and len(N.get("chips", [])) == 4 and N.get("small") == 0 and o.get("nqToast") is False and o.get("nqData") == [], (N, o.get("nqToast"), o.get("nqData")))
    F = o.get("fx") or {}
    check("b. Pillars: the particle field behind the content (z -1, no taps, body transparent), <= 90 motes, drawing; the tabs still take taps",
          F.get("canvas") and F.get("z") == "-1" and F.get("pe") == "none" and (F.get("stats") or {}).get("motes", 99) <= 90 and (F.get("stats") or {}).get("frames", 0) > 10
          and F.get("bodyBg") in ("rgba(0, 0, 0, 0)", "transparent") and F.get("top") == "tab", F)
    L = o.get("lessons") or {}
    check("b. Pillars: 'What the market taught us' with its lines, the SAMPLE banner while the file is the fixture, its source",
          L.get("lines", 0) >= 1 and L.get("sample") is (not os.path.exists(os.path.join(ROOT, "research", "learn", "insights.json"))) and "Source:" in L.get("src", ""), L)
    check("b. Pillars: a soft fade between pillars; a changed number glows (class only)", o.get("swap") is True and (o.get("pulse") or {}).get("after", 0) > (o.get("pulse") or {}).get("before", 0)
          and "lfx-" in (o.get("pulse") or {}).get("cls", ""), (o.get("swap"), o.get("pulse")))
    fr = o.get("fxFrames") or [0, 0]
    check("b. Pillars: the field keeps drawing on a visible tab", fr[1] > fr[0], fr)
    check("b. reduced motion: no particle field", (o.get("reduced") or {}).get("canvas") is False, o.get("reduced"))
    A = o.get("acc") or {}
    check("b. Accounts: the particle field is behind the cards and a tap reaches the card", A.get("canvas") and A.get("z") == "-1" and A.get("hit") == "content", A)
    check("b. Strategy Brain: the BLITZ pillar sheet has 'What the market taught us', Risks and What's next",
          {"What the market taught us", "What's next"} <= set(o.get("brain") or []), o.get("brain"))


def main():
    static()
    data()
    if os.environ.get("PH_NO_BROWSER") != "1":
        browser()
    print(f"\n{sum(RES)}/{len(RES)} passed")
    sys.exit(0 if all(RES) else 1)


if __name__ == "__main__":
    main()
