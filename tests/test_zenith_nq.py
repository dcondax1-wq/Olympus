"""Zenith root page, the NQ pass of 2026-11-11 (tools/web_public/zenith_nq.js + the AGORA layer): one strip above Home with the link "Open the new NQ page" and, when the PC has not
reported for more than 20 minutes, the honest banner in the same words as the NQ app; the last cold (blue / mint / violet) colours of the first screen re-toned.

  a. static   index.html loads zenith_nq.js after zenith_pages.js and before embed.js; read-only, text only; the strip's CSS (44 px link); the same sentence as nq/nqcore.js;
              no cold colour left in the Home curve (zenith_hero.js), the accent rgb token, the eval arc and the intro stars; versions bumped
  b. node     ZenithNQ.model (no data, no report, fresh, 5 hours, 4 days) and its age words = nqcore.js ageWords for a sweep of ages
  c. phone    Playwright 390x844 on a copy of the site: fresh data = the calm strip with the link (44 px, goes to nq/); four days old = the banner with the exact age;
              not on other pages; no sideways scroll; no page error
    python -X utf8 -m tests.test_zenith_nq          (--static: a and b only)
"""
from __future__ import annotations

import colorsys
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
WEB = os.path.join(ROOT, "tools", "web_public")
RES = []
SILENT = "The bots may still be trading; this page just is not hearing from them."


def check(name, cond, info=""):
    RES.append(bool(cond))
    print(("[PASS] " if cond else "[FAIL] ") + name + ("" if cond else f"  -> {str(info)[:900]}"), flush=True)


def rd(*p):
    with open(os.path.join(WEB, *p), encoding="utf-8") as f:
        return f.read()


def cold(txt):
    """Blue / cyan / mint / violet colours (hue 150-330, saturated) in a text: hex and r,g,b triples. The AGORA info blue (aegean) is allowed."""
    out = []
    cols = [(m.group(0), tuple(int(m.group(1)[i:i + 2], 16) for i in (0, 2, 4))) for m in re.finditer(r"#([0-9a-fA-F]{6})\b", txt)]
    cols += [(m.group(0), tuple(int(x) for x in m.groups())) for m in re.finditer(r"(?:rgba?\(|:)\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})", txt)]
    for name, (r, g, b) in cols:
        if max(r, g, b) > 255 or name.lower() in ("#4b7a99", "#7fa7c2", "#2f4a5c"):
            continue
        h, l, s = colorsys.rgb_to_hls(r / 255, g / 255, b / 255)
        if 150 <= h * 360 <= 330 and s > 0.28 and 0.12 < l < 0.92:
            out.append(name)
    return out


def part_a():
    idx, js, css, core = rd("index.html"), rd("zenith_nq.js"), rd("zenith_agora.css"), rd("nq", "nqcore.js")
    o = [idx.find(f'src="{n}?v=') for n in ("zenith_pages.js", "zenith_nq.js", "embed.js")]
    check("a. index.html loads zenith_nq.js after zenith_pages.js, before embed.js, once", all(i > 0 for i in o) and o == sorted(o) and idx.count("zenith_nq.js") == 1, o)
    check("a. zenith_nq.js is read-only and text-only (no fetch, no POST, no /api/, no arm, no innerHTML, no storage)",
          not re.search(r"fetch\(|POST|/api/|arm_|innerHTML|insertAdjacentHTML|localStorage|XMLHttpRequest|sendBeacon", js) and "textContent" in js)
    check("a. the link says 'Open the new NQ page' and goes to nq/ (the app folder exists)", "'Open the new NQ page'" in js and "a.href = 'nq/'" in js and os.path.isfile(os.path.join(WEB, "nq", "index.html")))
    check("a. the banner sentence is the NQ app's, word for word, and both use the 20-minute / 36-hour rule", SILENT in js and SILENT in core and "FRESH_S = 20 * 60" in js and "FRESH_S = 20 * 60" in core and "STALE_S = 36 * 3600" in js and "STALE_S = 36 * 3600" in core
          and "'Last report from your PC: ' + ageWords(age) + ' ago.'" in js)
    rule = re.search(r"\.zn-nq-a \{[^}]*\}", css)
    check("a. the strip's CSS is in the AGORA layer: a 44 px link, serif title, warm colours, hidden off Home", bool(rule) and "min-height: 44px" in rule.group(0) and ".zn-nq[hidden] { display: none; }" in css and "Iowan Old Style" in css.split(".zn-nq-t {")[1][:200]
          and not cold(css[css.index("/* ---- the NQ note above Home"):]))
    hero = rd("zenith_hero.js")
    check("a. the Home curve (zenith_hero.js) has no cold colour left: bronze to olive / terracotta line, gold target, marble grid", not cold(hero) and "'#9c6b3c'" in hero and "'#a3ae6b' : '#e0795a'" in hero, cold(hero))
    check("a. no cold colour in zenith_nq.js, zenith_money.js, zenith.js, zenith.css, polish.css; the accent rgb token is gold (200,162,74)",
          not any(cold(rd(n)) for n in ("zenith_nq.js", "zenith_money.js", "zenith.js", "zenith.css", "polish.css")) and "--zn-accent-rgb:200,162,74" in css and "109,124,255" not in css,
          {n: cold(rd(n))[:3] for n in ("zenith_nq.js", "zenith_money.js", "zenith.js", "zenith.css", "polish.css")})
    fb = idx[idx.index("function reactorFb("):idx.index("function reactorFb(") + 2600]
    sp = idx[idx.index("const cv = $('#spCv')"):idx.index("const cv = $('#spCv')") + 3200]
    check("a. the eval arc on Home (reactorFb) and the intro (stars, halo) are re-toned: no cold colour", not cold(fb) and not cold(sp), (cold(fb), cold(sp)))
    check("a. changed files are re-versioned so a phone does not keep the old copy: zenith_hero.js?v=3, zenith_money.js?v=3, zenith_agora.css?v=a2",
          'src="zenith_hero.js?v=3"' in idx and 'src="zenith_money.js?v=3"' in idx and 'href="zenith_agora.css?v=a2"' in idx)


NODE = r"""
const path = require('path');
global.window = global;
require(process.argv[2]);
const Z = window.ZenithNQ, n = 1794356000, o = {};
o.cases = [Z.model(null, n), Z.model({}, n), Z.model({ live: { pc: { t: n - 60 } } }, n), Z.model({ live: { pc: { t: n - 1200 } } }, n), Z.model({ live: { pc: { t: n - 1201 } } }, n), Z.model({ live: { pc: { t: n - 5 * 3600 } } }, n),
  Z.model({ board: { data_t: n - 4 * 86400 - 3 * 3600 - 9 } }, n), Z.model({ live: { last_run: n - 36 * 3600 - 1 } }, n), Z.model({ live: { pc: { t: 'x' }, last_run: n - 30 } }, n), Z.model('junk', n), Z.model({ live: { pc: { t: n + 90 } } }, n)];
import(process.argv[3]).then((C) => {
  const bad = [];
  for (let s = 0; s < 12 * 86400; s += 1777) if (Z.ageWords(s) !== C.ageWords(s)) bad.push(s);
  for (const s of [0, 59, 60, 3599, 3600, 86399, 86400, -5, NaN]) if (Z.ageWords(s) !== C.ageWords(s)) bad.push(s);
  o.same = bad; o.fresh = [Z.FRESH_S, C.FRESH_S];
  console.log(JSON.stringify(o));
});
"""


def part_b(tmp):
    core = os.path.join(tmp, "nqcore.mjs")
    shutil.copy(os.path.join(WEB, "nq", "nqcore.js"), core)
    js = os.path.join(tmp, "zn_nq_node.cjs")
    open(js, "w").write(NODE)
    p = subprocess.run(["node", js, os.path.join(WEB, "zenith_nq.js"), core], capture_output=True, text=True, timeout=60)
    if p.returncode:
        check("b. node runs ZenithNQ", False, p.stderr[:1500])
        return
    O = json.loads(p.stdout.strip().splitlines()[-1])
    c = O["cases"]
    check("b. no data yet = no banner; data without any report time = 'No report from your PC yet.'", c[0] == {"banner": False} and c[1]["banner"] and c[1]["title"] == "No report from your PC yet." and c[1]["text"] == SILENT and c[9] == {"banner": False}, (c[0], c[1], c[9]))
    check("b. a report up to 20 minutes old = no banner (also a clock a little ahead); 20 min 1 s = the banner", not c[2]["banner"] and not c[3]["banner"] and c[4]["banner"] and c[4]["title"] == "Last report from your PC: 20 minutes ago." and not c[10]["banner"], c[2:5])
    check("b. 5 hours = 'Last report from your PC: 5 hours ago.' (warn); 4 days = '... 4 days 3 hours ago.' (bad); over 36 hours = bad; the cloud run time is the last fallback",
          c[5]["title"] == "Last report from your PC: 5 hours ago." and c[5]["level"] == "warn" and c[5]["text"] == SILENT and c[6]["title"] == "Last report from your PC: 4 days 3 hours ago." and c[6]["level"] == "bad"
          and c[7]["level"] == "bad" and not c[8]["banner"], c[5:9])
    check("b. the age words are the NQ app's for every age tried (nqcore.js ageWords), and both call 20 minutes fresh", O["same"] == [] and O["fresh"] == [1200, 1200], O["same"][:5])


def part_c(tmp, shots):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("[SKIP] c. phone Playwright: playwright not installed")
        return
    from tests import test_blitz_tab as TB
    F = TB.build()
    s = TB.site(tmp, F)
    lvp = os.path.join(tmp, "liveview.json")
    json.dump(F["lv"], open(lvp, "w"), default=str)
    srv = TB.serve(s)
    base = f"http://127.0.0.1:{srv.server_address[1]}/"
    sh = (lambda pg, n: pg.screenshot(path=os.path.join(shots, n))) if shots else (lambda *a: None)
    SNAP = """() => { const b = document.getElementById('znNq'), a = document.getElementById('znNqLink'); if (!b) return null; const r = a.getBoundingClientRect(), br = b.getBoundingClientRect(), pg = document.getElementById('page').getBoundingClientRect();
      return { hidden: b.hidden || getComputedStyle(b).display === 'none', level: b.dataset.level, title: b.querySelector('.zn-nq-t').textContent, text: b.querySelector('.zn-nq-x').textContent, link: a.textContent, href: a.href,
        h: Math.round(r.height), w: Math.round(r.width), top: Math.round(br.top), above: br.bottom <= pg.top + 1, font: getComputedStyle(b.querySelector('.zn-nq-t')).fontFamily, x: document.documentElement.scrollWidth - innerWidth,
        prev: b.previousElementSibling && b.previousElementSibling.id, next: b.nextElementSibling && b.nextElementSibling.id }; }"""
    try:
        with sync_playwright() as p:
            br = TB.launch(p)
            errs = []
            ctx, pg = TB.phone_ctx(br, F, lvp, "off", errs)
            pg.goto(base + "#/today")
            pg.wait_for_selector(".pl-home .su-accts", timeout=30000)
            pg.wait_for_selector("#znNq", timeout=15000)
            pg.wait_for_timeout(900)
            if pg.query_selector("#moInstX"):
                pg.click("#moInstX")
            A = pg.evaluate(SNAP)
            check("c. Home with a fresh report (1 minute old): the calm strip above the page, no banner, the visible link 'Open the new NQ page' (44 px tall) that goes to nq/",
                  A and not A["hidden"] and A["level"] == "ok" and A["title"] == "The three NQ bots on one page" and A["link"] == "Open the new NQ page" and A["href"].endswith("/nq/") and A["h"] >= 44 and A["w"] >= 44 and A["above"]
                  and A["next"] == "page" and A["top"] < 400 and A["x"] <= 0, A)
            check("c. AGORA look: the strip's title is the serif", any(f in A["font"] for f in ("Palatino", "Iowan", "Georgia")), A["font"])
            sh(pg, "zenith_nq_fresh.png")
            pg.evaluate("() => { location.hash = '#/perf'; }")
            pg.wait_for_timeout(1300)
            B = pg.evaluate(SNAP)
            check("c. on another page (Performance) the strip is hidden; back on Home it shows again", B and B["hidden"])
            pg.evaluate("() => { location.hash = '#/today'; }")
            pg.wait_for_timeout(1300)
            check("c. ...and back on Home it shows again", not pg.evaluate(SNAP)["hidden"])
            ctx.close()
            # four days old: rewrite the site's data so the PC's last report is 4 days 3 hours before the page's clock
            T = F["T"]
            for n in ("data.json", "home.json"):
                d = json.load(open(os.path.join(s, n)))
                old = T - 4 * 86400 - 3 * 3600 - 30
                d["live"]["last_run"] = old
                d["live"]["pc"].update({"t": old, "age_s": T - old, "silent": True})
                if isinstance(d.get("board"), dict):
                    d["board"]["data_t"] = old
                json.dump(d, open(os.path.join(s, n), "w"), default=str)
            ctx, pg = TB.phone_ctx(br, F, lvp, "off", errs)
            for pat in ("**/api.github.com/**", "**/raw.githubusercontent.com/**"):      # the old phone live feed is gone too (it would overlay a fresh PC report)
                pg.route(pat, lambda r: r.fulfill(status=404, body="{}"))
            pg.goto(base + "#/today")
            pg.wait_for_selector("#znNq", timeout=30000)
            pg.wait_for_function("() => document.getElementById('znNq').dataset.level === 'bad'", timeout=20000)
            S = pg.evaluate(SNAP)
            check("c. Home with a report 4 days 3 hours old: the banner 'Last report from your PC: 4 days 3 hours ago.' + the honest sentence, in the first screen, with the link (44 px)",
                  S and not S["hidden"] and S["level"] == "bad" and S["title"] == "Last report from your PC: 4 days 3 hours ago." and S["text"] == SILENT and S["link"] == "Open the new NQ page" and S["h"] >= 44 and S["top"] < 400 and S["x"] <= 0, S)
            sh(pg, "zenith_nq_stale.png")
            pg.click("#znNqLink")
            pg.wait_for_function("window.NQ && window.NQ.ready()", timeout=60000)
            N = pg.evaluate("() => ({ path: location.pathname, banner: !document.querySelector('#banner').hidden, t: document.querySelector('#bannerTitle').textContent, demo: !document.querySelector('#demo').hidden })")
            check("c. a tap on the link opens the NQ page, which shows the same sentence from the same data (no DEMO chip)", N["path"].endswith("/nq/") and N["banner"] and N["t"] == "Last report from your PC: 4 days 3 hours ago." and not N["demo"], N)
            sh(pg, "zenith_nq_to_nq.png")
            check("c. no page error", not errs, errs[:3])
            ctx.close()
            br.close()
    finally:
        srv.shutdown()


if __name__ == "__main__":
    shots = sys.argv[sys.argv.index("--shots") + 1] if "--shots" in sys.argv else ""
    if shots:
        os.makedirs(shots, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="zn-nq-")
    try:
        part_a()
        part_b(tmp)
        if "--static" not in sys.argv:
            part_c(tmp, shots)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    bad = RES.count(False)
    print(f"\n{len(RES) - bad}/{len(RES)} passed", flush=True)
    sys.exit(1 if bad else 0)
