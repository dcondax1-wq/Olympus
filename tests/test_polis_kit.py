"""The POLIS kit (tools/web_public/olympus/polis.js + polis.css, lab olympus/polis-lab.html, docs/POLIS_KIT.md).

  a. static: the files, ES5 only (no arrow functions, let/const, template strings, ?. ??), no external URL, no storage writes, no console.log,
     the docs explain the Attic method
  b. node unit checks: greekNumeral, the astronomy against Meeus' worked examples and published 2026 new moons, atticDate (known dates, and
     every day 2015-2040 is consistent: months 29/30 days, years 12/13 months, Poseideon II only in 13-month years), pottery() returns a
     well-formed SVG for every motif in both styles and all frames
  c. a headless browser check of polis-lab.html: no console errors, every piece is on the page and drawn, 44 px taps, no sideways scroll at
     390 px, desktop width, reduced motion and LITE stop every animation

    python -X utf8 -m tests.test_polis_kit            (static + node only: --static; the browser part needs the shared lock:)
    flock -w 2400 /tmp/olympus_browser.lock python -X utf8 -m tests.test_polis_kit
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
import unicodedata
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
WEB = os.path.join(ROOT, "tools", "web_public")
KIT = os.path.join(WEB, "olympus")
JS, CSS, LAB = os.path.join(KIT, "polis.js"), os.path.join(KIT, "polis.css"), os.path.join(KIT, "polis-lab.html")
DOC = os.path.join(ROOT, "docs", "POLIS_KIT.md")
NAMES = ["owl", "laurel", "trireme", "bull", "horse", "lyre", "torch", "amphora", "warrior", "scales", "dolphin", "olive"]
RES: list = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:900]}"), flush=True)


def read(p):
    with open(p, encoding="utf-8") as fh:
        return fh.read()


# ------------------------------------------------------------------ a. static
def test_static():
    for p in (JS, CSS, LAB, DOC):
        check(f"a. {os.path.relpath(p, ROOT)} exists", os.path.exists(p))
    if not all(os.path.exists(p) for p in (JS, CSS, LAB, DOC)):
        return
    js, css, lab, doc = read(JS), read(CSS), read(LAB), read(DOC)
    code = re.sub(r"//[^\n]*|/\*.*?\*/", "", js, flags=re.S)
    code = re.sub(r"'(?:\\.|[^'\\])*'", "''", code)
    bad = [m for m in ("=>", "`", "?.", "??") if m in code] + [w for w in ("let ", "const ", "class ") if re.search(r"(^|[;{(\s])" + w, code)]
    check("a. polis.js is ES5 (no => ` ?. ?? let const class)", not bad, bad)
    ext = []
    for name, src in (("polis.js", js), ("polis.css", css), ("polis-lab.html", lab)):
        for u in re.findall(r"https?://[^\s'\"<>)]+", src):
            if not u.startswith("http://www.w3.org/2000/svg"):
                ext.append((name, u))
    check("a. nothing is loaded from outside the site (no external URL)", not ext, ext)
    check("a. no storage writes, no console.log in the kit", "localStorage" not in js and "console.log" not in js)
    check("a. the kit exposes every piece", all(f"P.{k} = " in js for k in ("meander", "columnFrame", "inscribe", "greekNumeral", "pottery", "mosaic", "coin", "atticDate", "sundial", "lamp", "laurel")))
    check("a. LITE and reduced motion are handled in JS and CSS", "prefers-reduced-motion" in js and "prefers-reduced-data" in js and "OLYMPUS" in js
          and "html.polis-still" in css and "@media (prefers-reduced-motion: reduce)" in css)
    check("a. the docs explain the Attic method (Meeus, crescent, solstice, Poseideon II, limits)",
          all(w in doc for w in ("Meeus", "crescent", "solstice", "Poseideon II", "archon", "Noumenia")) and "Meeus" in js)
    check("a. the docs list wiring for apps", "Wiring" in doc or "wiring" in doc)


# ------------------------------------------------------------------ b. node unit checks
NODE = r"""
const fs = require('fs'), vm = require('vm');
const ctx = { window: { location: { search: '' } }, Intl, Date, Math };
vm.createContext(ctx); vm.runInContext(fs.readFileSync(process.argv[1], 'utf8'), ctx);
const P = ctx.window.OLYMPUS_POLIS, out = {};
out.num = {}; [1, 6, 9, 10, 11, 90, 99, 444, 900, 999, 1000, 2026, 9999, 23820, 0, -5, 3.6].forEach(n => out.num[n] = P.greekNumeral(n));
out.upper = P.greekNumeral(2026, { upper: true });
out.nm1977 = P.astro.newMoonJDE(-283); out.sol1962 = P.astro.juneSolsticeJDE(1962);
out.nm2026 = []; for (let k = 321; k <= 334; k++) out.nm2026.push(P.attic.newMoonMs(k));
out.known = {}; ['2026-07-15', '2026-07-16', '2026-10-12', '2026-11-10', '2026-11-11', '2027-01-01'].forEach(d => { const a = P.atticDate(d); out.known[d] = [a.label, a.dayName, a.year.label, a.year.months]; });
out.fromDate = P.atticDate(new Date(Date.UTC(2026, 10, 11, 15, 0))).label;
// every day 2015-01-01 .. 2040-12-31
const days = []; let t = Date.UTC(2015, 0, 1); const end = Date.UTC(2040, 11, 31);
for (; t <= end; t += 864e5) { const a = P.atticDate(new Date(t).toISOString().slice(0, 10)); days.push([a.month, a.day, a.monthDays, a.year.months, a.year.start, a.intercalary ? 1 : 0]); }
out.days = days;
out.pots = {}; P.potteryNames.forEach(n => ['black', 'red'].forEach(s => ['tondo', 'tile', 'none'].forEach(f => out.pots[n + '|' + s + '|' + f] = P.pottery(n, { style: s, frame: f, size: 96 }))));
out.names = P.potteryNames;
out.twice = [P.pottery('owl'), P.pottery('owl')];
out.sess = [P.sessionNow({ h: 10, mi: 0, wd: 3 }).id, P.sessionNow({ h: 19, mi: 0, wd: 3 }).id, P.sessionNow({ h: 3, mi: 0, wd: 3 }).id, P.sessionNow({ h: 12, mi: 0, wd: 6 }).id, P.sessionNow({ h: 17, mi: 30, wd: 2 }).id];
out.usd = [P.fmtUsd(1240), P.fmtUsd(-380.4), P.fmtUsd(0)];
process.stdout.write(JSON.stringify(out));
"""

PUBLISHED_2026 = ["2026-01-18T19:52", "2026-02-17T12:01", "2026-03-19T01:23", "2026-04-17T11:52", "2026-05-16T20:01", "2026-06-15T02:54",
                  "2026-07-14T09:44", "2026-08-12T17:37", "2026-09-11T03:27", "2026-10-10T15:50", "2026-11-09T07:02", "2026-12-09T00:52"]


def test_node():
    try:
        r = subprocess.run(["node", "-e", NODE, JS], capture_output=True, text=True, timeout=240)
    except Exception as e:  # pragma: no cover
        check("b. node runs the kit", False, e)
        return
    check("b. node loads polis.js without a DOM", r.returncode == 0, r.stderr[-800:])
    if r.returncode:
        return
    o = json.loads(r.stdout)
    want = {"1": "αʹ", "6": "ϛʹ", "9": "θʹ", "10": "ιʹ", "11": "ιαʹ", "90": "ϟʹ", "99": "ϟθʹ", "444": "υμδʹ", "900": "ϡʹ", "999": "ϡϟθʹ",
            "1000": "͵αʹ", "2026": "͵βκϛʹ", "9999": "͵θϡϟθʹ", "23820": "βΜ ͵γωκʹ", "0": "", "-5": "−εʹ", "3.6": "δʹ"}
    nfc = lambda x: unicodedata.normalize("NFC", x or "")
    bad = {k: (o["num"].get(k), v) for k, v in want.items() if nfc(o["num"].get(k)) != nfc(v)}
    check("b. greekNumeral: units, stigma, koppa, sampi, thousands, myriads, 0, negative, rounding", not bad, bad)
    check("b. greekNumeral upper case", nfc(o["upper"]) == nfc("͵ΒΚϚʹ"), o["upper"])
    check("b. Meeus example 49.a: new moon 1977 Feb (JDE 2443192.65118, within 90 s)", abs(o["nm1977"] - 2443192.65118) < 90 / 86400, o["nm1977"])
    check("b. Meeus example 27.a: June solstice 1962 (JDE 2437837.39245, within 60 s)", abs(o["sol1962"] - 2437837.39245) < 60 / 86400, o["sol1962"])
    import datetime as dt
    got = [dt.datetime.fromtimestamp(ms / 1000, dt.timezone.utc).replace(tzinfo=None) for ms in o["nm2026"]]
    worst = 0.0
    for s in PUBLISHED_2026:
        t = dt.datetime.fromisoformat(s)
        worst = max(worst, min(abs((g - t).total_seconds()) for g in got) / 60)
    check(f"b. the 12 new moons of 2026 match the published times (worst {worst:.1f} min, limit 3)", worst <= 3, worst)
    k = o["known"]
    check("b. atticDate: 2026-07-16 = Hekatombaion 1 (Noumenia), Olympiad 701.2", k["2026-07-16"][:3] == ["Hekatombaion 1", "Noumenia", "Olympiad 701.2"], k["2026-07-16"])
    check("b. atticDate: 2026-07-15 is the last day of the old year (Hene kai Nea)", k["2026-07-15"][1] == "Hene kai Nea" and k["2026-07-15"][2] == "Olympiad 701.1", k["2026-07-15"])
    check("b. atticDate: 2026-10-12 = Pyanepsion 1, 2026-11-10 = Pyanepsion 30, 2026-11-11 = Maimakterion 1",
          k["2026-10-12"][0] == "Pyanepsion 1" and k["2026-11-10"][0] == "Pyanepsion 30" and k["2026-11-11"][0] == "Maimakterion 1", k)
    check("b. atticDate from a Date (New York calendar day)", o["fromDate"] == "Maimakterion 1", o["fromDate"])
    days = o["days"]
    errs = []
    lens = {}
    years = {}
    for i, d in enumerate(days):
        month, day, mlen, ymonths, ystart, inter = d
        if mlen not in (29, 30):
            errs.append(("month length", i, d))
        if ymonths not in (12, 13):
            errs.append(("year length", i, d))
        if inter and ymonths != 13:
            errs.append(("intercalary in a 12-month year", i, d))
        if not 1 <= day <= mlen:
            errs.append(("day out of range", i, d))
        if i:
            p = days[i - 1]
            if day == 1:
                if p[1] != p[2]:
                    errs.append(("month ended early", i, p, d))
            elif not (day == p[1] + 1 and month == p[0]):
                errs.append(("not contiguous", i, p, d))
        if day == 1:
            lens[mlen] = lens.get(mlen, 0) + 1
        years[ystart] = ymonths
    check(f"b. every day 2015-2040 ({len(days)} days) is consistent (months 29/30, years 12/13, contiguous)", not errs, errs[:5])
    thirteen = sum(1 for v in years.values() if v == 13)
    check(f"b. leap years near the Metonic rate (7 in 19): {thirteen} of {len(years)} years have 13 months", 0.3 <= thirteen / len(years) <= 0.45, years)
    check(f"b. full and hollow months both common ({lens})", lens.get(29, 0) > 100 and lens.get(30, 0) > 100, lens)
    check("b. the names: every month name is Attic", {d[0] for d in days} <= {"Hekatombaion", "Metageitnion", "Boedromion", "Pyanepsion", "Maimakterion", "Poseideon", "Poseideon II",
                                                                             "Gamelion", "Anthesterion", "Elaphebolion", "Mounichion", "Thargelion", "Skirophorion"})
    check("b. potteryNames are the 12 motifs", o["names"] == NAMES, o["names"])
    bad = []
    for key, svg in o["pots"].items():
        try:
            root = ET.fromstring(svg)
            ok = root.tag == "{http://www.w3.org/2000/svg}svg" and root.get("viewBox") == "0 0 120 120" and root.get("role") == "img" and root.get("aria-label")
            paths = root.findall(".//{http://www.w3.org/2000/svg}path")
            ds = [p.get("d") or "" for p in paths]
            if not ok or len(paths) < 3 or any(("NaN" in d or "undefined" in d or not d) for d in ds) or len(svg) > 60000:
                bad.append((key, len(paths), len(svg)))
            ids = [e.get("id") for e in root.iter() if e.get("id")]
            refs = set(re.findall(r"url\(#([^)]+)\)", svg))
            if len(ids) != len(set(ids)) or not refs <= set(ids):
                bad.append((key, "ids", sorted(refs - set(ids))))
        except ET.ParseError as e:
            bad.append((key, str(e)))
    check(f"b. pottery(): {len(o['pots'])} SVGs (12 motifs x 2 styles x 3 frames) are well-formed, labelled, no NaN, every url(#id) defined", not bad, bad[:6])
    a, b = o["twice"]
    ida, idb = set(re.findall(r'id="([^"]+)"', a)), set(re.findall(r'id="([^"]+)"', b))
    check("b. two pottery() calls never share an id (safe to put many on one page)", ida and not (ida & idb))
    check("b. sessionNow: RTH, Asia, London, weekend, daily break", o["sess"] == ["rth", "asia", "london", "closed", "break"], o["sess"])
    check("b. fmtUsd", o["usd"] == ["+$1,240", "−$380", "$0"], o["usd"])


# ------------------------------------------------------------------ c. browser
class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def test_browser():
    from playwright.sync_api import sync_playwright
    from tests import browser_kit as BK
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(_Quiet, directory=WEB))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    origin = f"http://127.0.0.1:{srv.server_address[1]}"
    with sync_playwright() as pw:
        br = BK.launch(pw)

        def open_page(q="", w=390, h=844, reduced=False):
            ctx = br.new_context(viewport={"width": w, "height": h}, device_scale_factor=1, is_mobile=w < 600, has_touch=w < 600,
                                 reduced_motion="reduce" if reduced else "no-preference")
            ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith(origin) else r.abort())
            p = ctx.new_page()
            p.set_default_timeout(120000)
            errs: list = []
            p.on("pageerror", lambda e: errs.append("pageerror " + str(e)))
            p.on("console", lambda m: errs.append(m.type + " " + m.text) if m.type in ("error", "warning") else None)
            p.on("requestfailed", lambda r: errs.append("requestfailed " + r.url))
            p.goto(origin + "/olympus/polis-lab.html" + q, wait_until="load")
            p.wait_for_function("() => window.__polisLab && window.__polisLab.ready", timeout=60000)
            p.wait_for_timeout(2500)
            return ctx, p, errs

        ctx, p, errs = open_page()
        info = p.evaluate("""() => {
          const q = s => document.querySelectorAll(s).length;
          const blank = c => { const g = c.getContext('2d'), d = g.getImageData(0, 0, c.width, c.height).data; let mn = 255, mx = 0;
            for (let i = 0; i < d.length; i += 4 * 97) { const v = d[i] + d[i + 1] + d[i + 2]; if (v < mn) mn = v; if (v > mx) mx = v; } return mx - mn < 12; };
          const small = [...document.querySelectorAll('button, input, [role=button], a[href]')].filter(e => { const r = e.getBoundingClientRect(); return r.width && (r.height < 44 && !e.classList.contains('polis-num')); }).map(e => e.id || e.className || e.tagName);
          const nums = [...document.querySelectorAll('.polis-num')].map(e => { const r = e.getBoundingClientRect(); const cs = getComputedStyle(e, '::after'); return r.height + parseFloat(cs.top) * -1 + parseFloat(cs.bottom) * -1; });
          return { errors: window.__polisLab.errors, pots: q('#pots svg.polis-pot'), icons: q('#icons svg'), meanders: q('svg.polis-meander'), meanderPaths: q('svg.polis-meander .polis-m-path'),
            cols: q('.polis-colframe .polis-cf-col'), orders: [...document.querySelectorAll('.polis-colframe')].map(e => e.dataset.polisOrder),
            mosaics: q('canvas.polis-mosaic'), blank: [...document.querySelectorAll('canvas.polis-mosaic')].filter(blank).length,
            coins: q('.polis-coin svg'), coinStates: [...document.querySelectorAll('.polis-coin')].map(e => e.dataset.state),
            dial: q('.polis-sundial svg'), dialText: (document.querySelector('.polis-sd-time') || {}).textContent, lamps: q('.polis-lamp svg'), laurels: q('.polis-laurel svg'),
            attic: (document.querySelector('#today-attic .polis-attic') || {}).textContent, atticRows: q('#attic-table tbody tr'),
            nums: q('.polis-num'), numH: nums, small, sw: document.documentElement.scrollWidth, still: document.documentElement.classList.contains('polis-still'),
            anims: document.getAnimations().length };
        }""")
        check("c. phone 390: the lab loads with no console error, warning or failed request", not errs and not info["errors"], errs + info["errors"])
        check("c. 12 pottery figures + 6 tile icons", info["pots"] == 12 and info["icons"] == 6, (info["pots"], info["icons"]))
        check("c. 4 meander borders are drawn (paths present)", info["meanders"] == 4 and info["meanderPaths"] >= 10, (info["meanders"], info["meanderPaths"]))
        check("c. 3 column frames: doric / ionic / corinthian (rank record -> corinthian)", info["cols"] == 6 and info["orders"] == ["doric", "ionic", "corinthian"], info["orders"])
        check("c. 5 mosaics are drawn and none is blank", info["mosaics"] == 5 and info["blank"] == 0, (info["mosaics"], info["blank"]))
        check("c. 4 coins: win / loss / flat / win", info["coins"] == 4 and info["coinStates"] == ["win", "loss", "flat", "win"], info["coinStates"])
        check("c. sundial, 2 lamps, 4 laurels", info["dial"] == 1 and info["lamps"] == 2 and info["laurels"] == 4 and "New York" in (info["dialText"] or ""), info)
        check("c. today's Attic date is shown, the table has 5 rows", bool(info["attic"]) and info["atticRows"] == 5, (info["attic"], info["atticRows"]))
        check("c. numbers in inscriptions are wrapped for Greek numerals with a >= 44 px tap area", info["nums"] >= 2 and all(h >= 44 for h in info["numH"]), info["numH"])
        check("c. every control is at least 44 px tall", not info["small"], info["small"])
        check("c. no sideways scroll at 390 px", info["sw"] <= 390, info["sw"])
        check("c. motion is on at full quality (animations running, not still)", not info["still"] and info["anims"] > 0, info)
        # interactions
        p.click("#t-red")
        red = p.evaluate("document.querySelectorAll('#pots svg.polis-pot.red').length")
        p.click("#c-loss")
        p.wait_for_timeout(300)
        st1 = p.evaluate("document.querySelector('#c4 .polis-coin').dataset.state")
        p.click("#c-win")
        p.wait_for_timeout(200)
        st2 = p.evaluate("[document.querySelector('#c4 .polis-coin').dataset.state, document.querySelector('#c4 .polis-coin').classList.contains('flip')]")
        p.fill("#attic-in", "2026-10-12")
        p.dispatch_event("#attic-in", "change")
        out = p.text_content("#attic-out")
        p.tap(".polis-num") if p.evaluate("'ontouchstart' in window") else p.click(".polis-num")
        on = p.evaluate("document.querySelector('.polis-num').classList.contains('on')")
        check("c. red-figure tab redraws the 12 pots in red-figure", red == 12, red)
        check("c. a loss dulls the coin to bronze, a win flips it back to silver", st1 == "loss" and st2 == ["win", True], (st1, st2))
        check("c. the date field gives the Attic date (2026-10-12 -> Pyanepsion 1)", (out or "").startswith("Pyanepsion 1"), out)
        check("c. tapping a number shows its Greek numeral", on)
        check("c. no error after the interactions", not errs, errs)
        ctx.close()

        for label, q, red_m in (("reduced motion", "", True), ("LITE (?lite=1)", "?lite=1", False)):
            ctx, p, errs = open_page(q, reduced=red_m)
            r = p.evaluate("""() => ({ still: document.documentElement.classList.contains('polis-still'),
                anims: document.getAnimations().filter(a => a.playState === 'running').map(a => (a.animationName || a.transitionProperty || '?') + ':' + (a.effect && a.effect.target && a.effect.target.getAttribute && (a.effect.target.getAttribute('class') || a.effect.target.tagName))),
                live: document.querySelectorAll('svg.polis-meander.live').length, dpr: Math.max(...[...document.querySelectorAll('canvas.polis-mosaic')].map(c => c.width / c.getBoundingClientRect().width)) })""")
            check(f"c. {label}: no console error, the page is marked still and nothing animates", not errs and r["still"] and not r["anims"] and r["live"] == 0, (errs, r))
            if q:
                check("c. LITE draws the mosaics at 1x", r["dpr"] <= 1.01, r["dpr"])
            ctx.close()

        ctx, p, errs = open_page("?t=2026-11-11T03:00:00Z")
        night = p.evaluate("[document.querySelector('.polis-sundial').dataset.night, document.querySelector('.polis-sundial').dataset.session]")
        ctx.close()
        ctx, p, errs2 = open_page("?t=2026-11-11T15:00:00Z", w=1280, h=900)
        day = p.evaluate("[document.querySelector('.polis-sundial').dataset.night, document.querySelector('.polis-sundial').dataset.session, document.documentElement.scrollWidth]")
        ctx.close()
        check("c. sundial at 22:00 New York: night (moon hand), Asia session", night == ["1", "asia"], night)
        check("c. sundial at 10:00 New York on desktop 1280: daylight, RTH, no sideways scroll, no error", day[:2] == ["0", "rth"] and day[2] <= 1280 and not errs and not errs2, (day, errs, errs2))
        br.close()
    srv.shutdown()


def main():
    test_static()
    test_node()
    if "--static" not in sys.argv:
        test_browser()
    n, ok = len(RES), sum(RES)
    print(f"\n{ok}/{n} passed", flush=True)
    sys.exit(0 if ok == n else 1)


if __name__ == "__main__":
    main()
