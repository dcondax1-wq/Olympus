"""Night 3 (2026-10-30, owner: "more very useful features ... clean it up, organized ... the UI, quality, the effects ...
I wanna be shocked"): the status bar, the three account cards, what matters now, the Sunday open card, the search palette,
the one section order on every bot tab, Money = real money only, the motion system and the once-a-day intro, on both
dashboards (read-only UI).

  a. static   statuscore.js byte-identical on both apps, the phone loads statuscore.js + polish.js after blitz.js and
              polish.css in the head, caches bumped (phone le-public-v46+, PC le-shell-next-v28+), clean.js?v=3 kept,
              read-only (no fetch / POST in the renderers), FEATURES.md lists the features, the PC sidebar sections
  b. node     StatusUI from the live-board fixture (2 and 3 accounts): the status items, the account cards (ring, REAL /
              SIM tag, the day in one line), the Sunday open card on the clock-change weekend (and not on a Tuesday),
              smart empty states; garbage in = no exception
  c. phone    Playwright 390x844 on a copy of tools/web_public: every tab and every bot section renders with no page error
              and no sideways scroll; the status bar folds open; "Everything else on Home" keeps every older card; the
              palette finds a page and opens it; Money opens Real results; the intro shows once a day and is skippable;
              reduced motion = no intro and no animation; frame time while scrolling Home; the light theme
  d. PC       Playwright 1440x900 on server.py: the status bar on Home, the sidebar sections, five sections on BLITZ

  python -X utf8 -m tests.test_ui_polish [--shots <dir>]
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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
RES = []
PERF = {}


def check(name, cond, info=""):
    RES.append(bool(cond))
    print(("[PASS] " if cond else "[FAIL] ") + name + ("" if cond else f"  -> {str(info)[:500]}"), flush=True)


def rd(*p):
    with open(os.path.join(ROOT, *p), encoding="utf-8") as f:
        return f.read()


# ------------------------------------------------------------------------------------------------ a. static
def part_a():
    check("a. statuscore.js byte-identical on both apps", rd("tools", "web_public", "statuscore.js") == rd("web_next", "js", "next", "statuscore.js"))
    idx, psw, sw = rd("tools", "web_public", "index.html"), rd("tools", "web_public", "sw.js"), rd("web_next", "sw.js")
    order = [idx.find(f'src="{n}?v=') for n in ("blitz.js", "statuscore.js", "polish.js")]
    check("a. phone index: statuscore.js then polish.js after blitz.js (last), polish.css in the head", all(i > 0 for i in order) and order == sorted(order)
          and idx.find('polish.css?v=') < idx.find('</head>') and idx.find('polish.css?v=') > 0, order)
    check("a. caches: phone le-public-v46+, PC le-shell-next-v28+; clean.js?v=3 kept", int(re.search(r"le-public-v(\d+)", psw).group(1)) >= 46
          and int(re.search(r"le-shell-next-v(\d+)", sw).group(1)) >= 28 and 'clean.js?v=3"' in idx and "/css/polish.css" in sw)
    for n in ("statuscore.js", "polish.js"):
        src = rd("tools", "web_public", n)
        check(f"a. {n} is read-only (no fetch, no POST, no arm / route / order call)", "fetch(" not in src and "POST" not in src and "/api/" not in src and "arm_c" not in src)
    pj = rd("web_next", "js", "next", "polish.js")
    check("a. PC polish.js only GETs (board, news)", "POST" not in pj and "method:" not in pj)
    cl, rt = rd("tools", "web_public", "clean.js"), rd("web_next", "js", "next", "routes.js")
    check("a. one section order on every bot tab (phone): Today · Brain · Trades · Results · Rules", all(
        re.findall(r"\['(Today|Brain|Trades|Results|Rules|Plan|Strategy|Setups|Go live)', \[", cl[cl.index(f"const {k} = ["):cl.index("];", cl.index(f"const {k} = ["))])
        == ["Today", "Brain", "Trades", "Results", "Rules"] for k in ("ZL_SEGS", "AT_SEGS", "BZ_SEGS")))
    bots = rt[rt.index("export const BOTS"):rt.index("export const BOT_CHIP")]
    check("a. one section order on every bot page (PC)", [re.findall(r"\['(\w[\w &]*)', \[", b) for b in re.split(r"\n  \w+: \{", bots)[1:]] == [["Today", "Brain", "Trades", "Results", "Rules"]] * 3,
          [re.findall(r"\['(\w[\w &]*)', \[", b) for b in re.split(r"\n  \w+: \{", bots)[1:]])
    check("a. PC sidebar: Main in plain sections (Bots · Live · Money · Insight)", "export const MAIN_SECTIONS" in rt and "['Bots', ['zlarior', 'atlas', 'blitz']]" in rt
          and "MAIN_SECTIONS" in rd("web_next", "js", "next", "shell.js"))
    check("a. Money tab = real money only (Real results, Accounts today, Eval timeline)", "const TAB_MAIN = { money: ['real', 'realtoday', 'evaltl'] }" in cl)
    fm = rd("web_next", "FEATURES.md")
    check("a. FEATURES.md lists the night-3 features (82+)", "| 82 |" in fm and "Status bar" in fm and "Sunday open" in fm and "palette" in fm.lower())


# ------------------------------------------------------------------------------------------------ b. node
NODE_JS = r"""
global.window = {}; global.document = undefined;
const dir = process.argv[2], fs = require('fs');
for (const n of ['missioncore.js', 'deckcore.js', 'statuscore.js']) require(dir + '/' + n);
const F = JSON.parse(fs.readFileSync(process.argv[3], 'utf8')), S = window.StatusUI, out = { bad: 0 };
const thu = Date.parse('2026-10-30T01:15:00Z') / 1000, tue = Date.parse('2026-10-27T15:00:00Z') / 1000;
const M2 = { now: F.now, where: 'phone', board: F.b2 }, M3 = { now: F.now, where: 'phone', board: F.b3 };
out.items2 = S.items(M2).map((x) => [x.k, x.lvl, x.value]); out.sum2 = S.summary(M2);
out.acc2 = S.accounts(M2, { where: 'phone' }); out.acc3 = S.accounts(M3, { where: 'phone' }); out.bar = S.bar(M3, { open: true, more: '<a>x</a>' });
out.one = ['lit', 'atlas', 'blitz'].map((k) => { const A = window.MissionUI.accounts(M3).find((a) => a.key === k); return A ? S.oneLine(A, M3).text : null; });
out.sunThu = S.sunday({ now: thu, board: F.b2 }); out.sunTue = S.sunday({ now: tue, board: F.b2 }); out.dst = S.dstNext(thu);
out.empty = ['trades', 'real', 'blitz', 'mind', 'feed', 'x'].map((k) => S.empty(k, M2));
const sat = Date.parse('2026-10-31T16:00:00Z') / 1000;
out.pcSat = S.items({ now: sat, board: Object.assign({}, F.b2, { data_t: sat - 150000 }) }).find((x) => x.k === 'pc');
out.pcTue = S.items({ now: tue, board: Object.assign({}, F.b2, { data_t: tue - 7200 }) }).find((x) => x.k === 'pc');
out.mkt = S.market(M2); out.mktNone = S.market({ board: {} }); out.hasMap = !!(F.b2.map && F.b2.map.price != null);
for (const g of [null, {}, { board: 5 }, { board: { lit: 'x', health: { items: 3 } } }, { board: { lit: { position: 5, window: 'y', days: 7 } }, news: 'n' }, { board: { map: { price: 'x', nearest_above: 3 } } }, { board: { map: { price: 5, nearest_above: { price: 1 }, nearest_below: { price: 9 } } } }]) {
  try { S.items(g); S.bar(g); S.accounts(g); S.sunday(g || {}); S.empty('trades', g); S.market(g); S.week(g); } catch (e) { out.bad++; out.err = String(e.stack).slice(0, 300); }
}
process.stdout.write(JSON.stringify(out) + '\n');
"""


def part_b(tmp):
    node = shutil.which("node")
    if not node:
        print("[SKIP] b. node render: node not installed")
        return
    from tests import test_space_ui as SU
    now = int(time.time())
    b2, b3 = SU.boards(now)
    b2["lit"]["badge"], b2["atlas"]["badge"] = "LIVE", "SIM"
    b3["lit"]["badge"], b3["atlas"]["badge"] = "LIVE", "SIM"
    fp = os.path.join(tmp, "f.json")
    json.dump({"now": now, "b2": b2, "b3": b3}, open(fp, "w"), default=str)
    jp = os.path.join(tmp, "r.js")
    open(jp, "w").write(NODE_JS)
    r = subprocess.run([node, jp, os.path.join(ROOT, "tools", "web_public"), fp], capture_output=True, text=True, timeout=60)
    try:
        o = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        check("b. node render ran", False, (r.stdout or "")[-300:] + (r.stderr or "")[-600:])
        return
    keys = [x[0] for x in o["items2"]]
    check("b. status items: PC bot, NinjaTrader, feed, Zlarior, ATLAS, BLITZ, alerts (+ the next window when there is one)",
          keys[:1] == ["pc"] and "nt" in keys and "feed" in keys and keys.index("lit") < keys.index("atlas") < keys.index("blitz") and keys[-1] == "alerts", o["items2"])
    check("b. one summary: a level and one sentence", o["sum2"]["lvl"] in ("good", "warn", "bad") and o["sum2"]["title"], o["sum2"])
    a2, a3 = o["acc2"], o["acc3"]
    check("b. account cards: Zlarior · ATLAS · BLITZ (a paper placeholder until its 25K), the eval ring, $ to the target, the REAL / SIM tag",
          a2.count('<a class="su-acct') == 3 and 'su-acct ph' in a2 and a2.count("su-ring") >= 3 and "to the target" in a2 and ">REAL<" in a2 and ">SIM<" in a2, a2[:400])
    check("b. three real accounts: BLITZ gets its own card with numbers (no placeholder)", a3.count('<a class="su-acct') == 3 and 'su-acct ph' not in a3)
    check("b. the day in one line per bot (Zlarior in a trade)", o["one"][0] and o["one"][0].startswith("In a LONG") and all(o["one"]), o["one"])
    check("b. the status bar: a fold with every line and its fix, the extra links", 'data-su-toggle' in o["bar"] and 'su-list' in o["bar"] and '<a>x</a>' in o["bar"])
    st = re.sub(r"<[^>]+>", " ", o["sunThu"])
    check("b. Sunday open (Thu 21:15 ET before the clock change): clocks back 1 hour on Sun Nov 1, CME reopens Sun 18:00 ET, each bot's first step, BLITZ off",
          "Clocks go back 1 hour" in st and "Sun Nov 1" in st and "Sun 18:00 ET" in st and "Mon 02:00 ET" in st and "Off until its own 25K" in st and "Set time automatically" in st, st[:500])
    check("b. Sunday open: not on a Tuesday; the next clock change is 2026-11-01 06:00 UTC (back)", o["sunTue"] == "" and o["dst"]["t"] == 1793512800 and o["dst"]["way"] == "back", (o["sunTue"][:80], o["dst"]))
    check("b. smart empty states say what will appear and when", all("su-empty" in e for e in o["empty"]) and "within a minute" in o["empty"][0] and "never routed" in o["empty"][2])
    check("b. a quiet PC: grey 'off for the weekend' on Saturday, amber / red on a trading day", o["pcSat"]["lvl"] == "idle" and "weekend" in o["pcSat"]["value"]
          and o["pcTue"]["lvl"] in ("warn", "bad"), (o["pcSat"], o["pcTue"]))
    check("b. NQ now: the price between the nearest levels above / below (a ladder), nothing without a price", o["mktNone"] == ""
          and (not o["hasMap"] or ("su-mkt" in o["mkt"] and "NQ" in o["mkt"])), o["mkt"][:300])
    check("b. garbage in: no exception", o["bad"] == 0, o.get("err"))


# ------------------------------------------------------------------------------------------------ c. phone
ROUTES = [("Home", "#/today"), ("Zlarior", "#/lit"), ("Zlarior Brain", "#/brain"), ("Zlarior Trades", "#/trades"), ("Zlarior Results", "#/perf"), ("Zlarior Rules", "#/strategy"),
          ("ATLAS", "#/atlas"), ("ATLAS Brain", "#/atlas/brain"), ("ATLAS Trades", "#/atlas/trades"), ("ATLAS Results", "#/atlas/results"), ("ATLAS Rules", "#/atlas/setups"),
          ("BLITZ", "#/blitz"), ("BLITZ Brain", "#/blitz/brain"), ("BLITZ Trades", "#/blitz/trades"), ("BLITZ Results", "#/blitz/results"), ("BLITZ Rules", "#/blitz/rules"),
          ("BLITZ Go live", "#/blitz/golive"), ("Money", "#/real"), ("Accounts today", "#/realtoday"), ("More", "#/system"), ("Money plan (More)", "#/money"),
          ("Mission Control", "#/mission"), ("Settings", "#/settings")]


def part_c(F, tmp, shots):
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        print("[SKIP] c. phone Playwright: playwright not installed")
        return
    from tests import test_blitz_tab as TB
    s = TB.site(tmp, F)
    lvp = os.path.join(tmp, "liveview.json")
    json.dump(F["lv"], open(lvp, "w"), default=str)
    srv = TB.serve(s)
    base = f"http://127.0.0.1:{srv.server_address[1]}/"
    lj = json.dumps(TB.live_json(F, "off"), default=str)
    sh = (lambda pg, n: pg.screenshot(path=os.path.join(shots, n))) if shots else (lambda *a: None)

    def page(br, errs, w=390, h=844, motion="no-preference", init=""):
        ctx = br.new_context(viewport={"width": w, "height": h}, device_scale_factor=2, is_mobile=True, has_touch=True, reduced_motion=motion, timezone_id="America/New_York")
        ctx.clock.install(time=F["T"])
        if init:
            ctx.add_init_script(init)
        pg = ctx.new_page()
        pg.on("pageerror", lambda e: errs.append(f"pageerror: {str(e)[:240]}"))
        for host in ("**/api.github.com/**", "**/raw.githubusercontent.com/**"):
            pg.route(host, lambda r: r.fulfill(path=lvp, content_type="application/json") if "liveview.json" in r.request.url
                     else r.fulfill(status=200, body=lj, content_type="application/json") if "/live.json" in r.request.url else r.fulfill(status=404, body="{}"))
        return ctx, pg

    no_x = lambda pg: pg.evaluate("() => document.documentElement.scrollWidth - innerWidth")
    with sync_playwright() as p:
        br = TB.launch(p)
        errs = []
        ctx, pg = page(br, errs)
        pg.goto(base + "?fxoff#/today")
        pg.wait_for_selector(".pl-home .su-bar", timeout=30000)
        pg.wait_for_function("() => window.LIVE && window.LIVE.j", timeout=30000)
        pg.wait_for_timeout(1200)
        if pg.query_selector("#moInstX"):
            pg.click("#moInstX")
            pg.wait_for_timeout(300)
        H = pg.evaluate("() => { const h = document.querySelector('#page > .pl-home'); return { kids: [...h.children].map(c => c.className.split(' ')[0]), accts: [...h.querySelectorAll('.su-acct')].map(a => a.dataset.bot), height: document.documentElement.scrollHeight }; }")
        check("c. Home: the greeting, status bar, the three account cards (Zlarior · ATLAS · BLITZ), what matters now, quick tiles", H["kids"][:4] == ["pl-hi", "su-bar", "su-accts", "pl-now"] and "pl-quick" in H["kids"]
              and H["accts"] == ["lit", "atlas", "blitz"], H)
        PERF["home_height_px"] = H["height"]
        check("c. Home is short and calm (under 2,600 px at 390 wide with everything else folded)", H["height"] < 2600, H["height"])
        wk = pg.evaluate("() => { const w = document.querySelector('.pl-home .su-week'); return w ? [...w.querySelectorAll('li > b')].map(b => b.textContent) : null; }")
        prog = (F["board"].get("progress") or {})
        check("c. Home: this week's real trades vs each bot's goal (Mon-Fri dots), when the board has its progress", (wk is None and not prog) or (wk and "Zlarior" in wk), (wk, list(prog)))
        hid = pg.evaluate("() => [...document.querySelectorAll('#page > .mc-strip, #page > .rc-homebox, #page > .bz-home, #page > .cl-list')].map(e => [e.className.split(' ')[0], e.offsetParent === null])")
        check("c. Home: every older card is still there, folded (Mission strip, real accounts, deck + Mind, one tap away)", len(hid) >= 3 and all(x[1] for x in hid), hid)
        pg.click("[data-su-toggle]")
        pg.wait_for_timeout(450)
        op = pg.evaluate("() => { const b = document.querySelector('.su-bar'); return { open: b.classList.contains('open'), h: b.querySelector('.su-list').getBoundingClientRect().height, rows: b.querySelectorAll('.su-list > li').length }; }")
        check("c. the status bar opens every line (PC bot, NinjaTrader, feed, each bot, alerts)", op["open"] and op["h"] > 100 and op["rows"] >= 6, op)
        sh(pg, "polish_phone_status_open.png")
        pg.click("[data-su-toggle]")
        pg.click("#page > .pl-fold")
        pg.wait_for_timeout(400)
        shown = pg.evaluate("() => [...document.querySelectorAll('#page > .mc-strip, #page > .bz-home')].every(e => e.offsetParent !== null)")
        check("c. 'Everything else on Home' shows the older cards in one tap (remembered)", shown and pg.evaluate("() => localStorage.getItem('le.pl.homeAll')") == "true")
        pg.click("#page > .pl-fold")
        pg.wait_for_timeout(300)
        sh(pg, "polish_phone_home.png")
        mk = pg.evaluate("() => { const m = document.querySelector('.pl-home .su-mkt'); return m ? m.innerText.replace(/\\s+/g, ' ').slice(0, 120) : null; }")
        check("c. Home: NQ now with the nearest levels (when the board has a price)", mk is None or "NQ" in mk, mk)
        # keyboard: an account card is a tab stop and Enter opens its bot
        pg.focus(".pl-home .su-acct[data-bot='atlas']")
        pg.keyboard.press("Enter")
        pg.wait_for_timeout(600)
        check("c. keyboard: the account cards are tab stops, Enter opens the bot (ATLAS)", pg.evaluate("() => location.hash") == "#/atlas", pg.evaluate("() => location.hash"))
        pg.evaluate("() => { location.hash = '#/today'; }")
        pg.wait_for_timeout(600)
        # every tab and section
        bad = []
        for name, h in ROUTES:
            pg.evaluate(f"() => {{ location.hash = '{h}'; }}")
            pg.wait_for_timeout(900)
            st = pg.evaluate("() => ({ x: document.documentElement.scrollWidth - innerWidth, n: document.querySelector('#page').children.length, t: (document.querySelector('#page').innerText || '').length, err: /Could not draw this page/.test(document.querySelector('#page').innerText) })")
            if st["x"] > 1 or st["n"] < 1 or st["t"] < 40 or st["err"]:
                bad.append((name, st))
        check(f"c. all {len(ROUTES)} tab / section pages render, no 'could not draw', no sideways scroll at 390 px", not bad, bad)
        segs = {}
        for k, h in (("lit", "#/lit"), ("atlas", "#/atlas"), ("blitz", "#/blitz")):
            pg.evaluate(f"() => {{ location.hash = '{h}'; }}")
            pg.wait_for_timeout(700)
            segs[k] = pg.eval_on_selector_all("#sub .zl-seg button", "els => els.map(e => e.textContent.trim())")
        check("c. Zlarior, ATLAS and BLITZ: the same five sections in the same order", all(v == ["Today", "Brain", "Trades", "Results", "Rules"] for v in segs.values()), segs)
        ind = pg.evaluate("() => { const i = document.querySelector('#tabs > .pl-tabind'), a = document.querySelector('#tabs a.on'); return i && a ? { t: i.dataset.t, on: a.dataset.t, w: Math.round(parseFloat(i.style.width)), aw: a.offsetWidth } : null; }")
        check("c. the bottom bar: one pill slides to the open tab, in its colour (BLITZ)", ind and ind["t"] == "blitz" == ind["on"] and abs(ind["w"] - ind["aw"]) <= 1, ind)
        td = pg.evaluate("() => [...document.querySelectorAll('#tabs a .pl-tdot')].map(d => d.parentNode.dataset.t + ':' + d.dataset.s)")
        check("c. the bottom bar: a light on a bot's tab while it is in a trade (Zlarior)", "lit:trade" in td, td)
        col = pg.evaluate("() => getComputedStyle(document.documentElement).getPropertyValue('--bot').trim()")
        top = pg.query_selector("#page > .pl-bot .su-acct[data-bot='blitz']")
        check("c. a bot tab opens on its account card, in the bot's colour (BLITZ purple)", top is not None and col.lower() in ("#b388ff", "var(--bz)") , col)
        pg.click("#tabs a[data-t='money']")
        pg.wait_for_timeout(900)
        mo = pg.evaluate("() => ({ hash: location.hash, chips: [...document.querySelectorAll('#sub .strip button')].map(b => b.dataset.go) })")
        check("c. Money tab opens Real results; its pages are real money only (Real results · Accounts today · Eval timeline)", mo["hash"] == "#/real" and mo["chips"][:2] == ["real", "realtoday"]
              and not any(c in mo["chips"] for c in ("money", "props", "whatif", "scale")), mo)
        pg.evaluate("() => { location.hash = '#/system'; }")
        pg.wait_for_timeout(700)
        sec = pg.eval_on_selector_all(".cl-sec h4", "els => els.filter(e => e.offsetParent !== null).map(e => e.firstChild.textContent.trim())")
        check("c. More: grouped (Today · Insight · Bot and health · Trades · Money planning · This app · Advanced)", sec[:6] == ["Today", "Insight", "Bot and health", "Trades", "Money planning", "This app"] and "Advanced" in sec, sec)
        # the palette
        pg.click("#plFind")
        pg.wait_for_selector("#plPal.on #plQ", timeout=5000)
        pg.fill("#plQ", "atlas trades")
        pg.wait_for_timeout(250)
        first = pg.eval_on_selector("#plL li.on b", "e => e.textContent")
        sh(pg, "polish_phone_palette.png")
        pg.keyboard.press("Enter")
        pg.wait_for_timeout(700)
        check("c. the search palette: 'atlas trades' -> ATLAS · Trades, Enter opens it", "ATLAS" in first and "Trades" in first and pg.evaluate("() => location.hash") == "#/atlas/trades"
              and not pg.query_selector("#plPal.on"), (first, pg.evaluate("() => location.hash")))
        pg.keyboard.press("/")
        pg.wait_for_selector("#plPal.on", timeout=3000)
        pg.keyboard.press("Escape")
        pg.wait_for_timeout(300)
        check("c. the palette: '/' opens it, Escape closes it", not pg.query_selector("#plPal.on"))
        # the header status dot on every page: its verdict, a tap opens the status bar on Home
        dot = pg.evaluate("() => { const b = document.getElementById('plStat'); return b ? b.className : null; }")
        pg.click("#plStat")
        pg.wait_for_timeout(900)
        opened = pg.evaluate("() => location.hash === '#/today' && !!document.querySelector('.pl-home .su-bar.open')")
        check("c. the header status dot (green / amber / red) on every page; a tap opens the status bar on Home", dot and re.search(r"\b(good|warn|bad)\b", dot) and opened, (dot, opened))
        pg.click("[data-su-toggle]")
        # frame time while scrolling Home (the UI itself; the 3D scene is measured by tests.test_space_ui)
        pg.evaluate("() => { location.hash = '#/today'; }")
        pg.wait_for_timeout(1200)
        fr = pg.evaluate("""() => new Promise((res) => { const d = []; let last = performance.now(), n = 0; const H = document.documentElement.scrollHeight - innerHeight;
          function f(t) { d.push(t - last); last = t; n++; scrollTo(0, (Math.sin(n / 18) * 0.5 + 0.5) * H); if (n < 150) requestAnimationFrame(f); else { d.shift(); d.sort((a, b) => a - b); res({ n: d.length, p50: d[d.length >> 1], p95: d[Math.floor(d.length * 0.95)] }); } }
          requestAnimationFrame(f); })""")
        PERF["phone_scroll_frame_ms"] = fr
        check("c. frame time while scrolling Home: median <= 20 ms, p95 <= 50 ms (headless, software GPU)", fr["p50"] <= 20 and fr["p95"] <= 50, fr)
        # layout shift of a fresh open of Home (the first 4 s: home.json, data.json, live.json and the late cards landing);
        # the scroll above scrolls the page, which is no shift. The scrolled position is reset first.
        pg.evaluate("() => scrollTo(0, 0)")
        ctx.add_init_script("""window.__ls = []; try { new PerformanceObserver((l) => { for (const e of l.getEntries()) if (!e.hadRecentInput)
          window.__ls.push([+e.value.toFixed(4), Math.round(e.startTime), (e.sources || []).map((x) => x.node ? (x.node.id || String(x.node.className || x.node.nodeName).split(' ')[0]) : '?').join(',')]); }).observe({ type: 'layout-shift', buffered: true }); } catch (e) {}""")
        pg.reload()                          # a new document (a goto to the same URL + hash would stay in the page)
        pg.wait_for_selector(".pl-home .su-acct", timeout=30000)
        pg.wait_for_timeout(4000)
        cls_ = pg.evaluate("""() => new Promise((res) => { let s = 0; try { new PerformanceObserver((l) => { for (const e of l.getEntries()) if (!e.hadRecentInput) s += e.value; }).observe({ type: 'layout-shift', buffered: true }); } catch (e) {} setTimeout(() => res(s), 600); })""")
        PERF["phone_layout_shift"] = round(cls_, 4)
        PERF["phone_layout_shift_top"] = sorted(pg.evaluate("() => window.__ls || []"), key=lambda x: -x[0])[:4]
        check("c. no layout shift to speak of on a fresh open of Home (CLS < 0.1)", cls_ < 0.1, cls_)
        check("c. phone: no page errors", not errs, errs[:4])
        ctx.close()
        # the intro: once a day, skippable (a real phone, not an automated browser)
        e2 = []
        real = "Object.defineProperty(Navigator.prototype, 'webdriver', { get: () => false });"
        ctx, pg = page(br, e2, init=real)
        t0 = time.time()
        pg.route("**/fonts.g*/**", lambda r: r.abort())       # no web fonts here: the page loads at once, like the installed app
        pg.goto(base + "#/today", wait_until="commit")
        pg.wait_for_selector("#splash #spSkip", timeout=10000)
        vis = pg.is_visible("#splash")
        sh(pg, "polish_phone_intro.png")
        tk = time.time()
        fading = pg.evaluate("() => { const b = document.getElementById('spSkip'); if (b) b.click(); const s = document.getElementById('splash'); return !s || s.classList.contains('out'); }")      # a tap on Skip: it starts to fade in the same frame
        pg.wait_for_function("() => !document.getElementById('splash')", timeout=10000)   # it fades at once; the removal timer can wait on a busy first load here
        gone_s = round(time.time() - tk, 2)
        PERF["intro_skip_s"] = gone_s
        pg.reload()
        pg.wait_for_selector(".pl-home", timeout=30000)
        again = pg.query_selector("#splash") is not None
        check("c. the intro: shows on the first open of the day, Skip removes it at once, not again the same day", vis and fading and not again and not e2, (vis, fading, again, gone_s, e2[:2]))
        ctx.close()
        # Settings > Intro off: no intro even on a new day
        e5 = []
        ctx, pg = page(br, e5, init=real + "try { localStorage.setItem('le.intro', 'false'); } catch (e) {}")
        pg.goto(base + "#/settings")
        pg.wait_for_selector("#plIntro", timeout=30000)
        off = pg.evaluate("() => ({ intro: !!document.getElementById('splash'), box: document.getElementById('plIntro').checked })")
        check("c. Settings > Intro: the switch is there; off = no intro", not off["intro"] and off["box"] is False and not e5, (off, e5[:2]))
        ctx.close()
        # reduced motion: no intro, no animation on the new parts
        e3 = []
        ctx, pg = page(br, e3, motion="reduce", init=real)
        pg.goto(base + "#/today")
        pg.wait_for_selector(".pl-home .su-acct", timeout=30000)
        pg.wait_for_timeout(800)
        rm = pg.evaluate("() => ({ intro: !!document.getElementById('splash'), anims: [...document.querySelectorAll('#page, #page .pl-home, #page .pl-home *')].reduce((n, e) => n + e.getAnimations().length, 0) })")
        check("c. reduced motion: no intro, no animation on the page or its new cards", not rm["intro"] and rm["anims"] == 0 and not e3, (rm, e3[:2]))
        ctx.close()
        # the light theme, sideways
        e4 = []
        ctx, pg = page(br, e4, 844, 390, init="try { localStorage.setItem('le.theme', JSON.stringify('light')); } catch (e) {}")
        pg.goto(base + "?fxoff#/today")
        pg.wait_for_selector(".pl-home .su-acct", timeout=30000)
        pg.wait_for_timeout(600)
        ink = pg.evaluate("() => getComputedStyle(document.querySelector('.su-sum b')).color")
        check("c. light theme, sideways 844x390: dark ink on light glass, no sideways scroll, no errors", sum(int(x) for x in re.findall(r"\d+", ink)[:3]) < 300 and no_x(pg) <= 1 and not e4, (ink, no_x(pg), e4[:2]))
        sh(pg, "polish_phone_light_landscape.png")
        ctx.close()
        br.close()
    srv.shutdown()


# ------------------------------------------------------------------------------------------------ d. PC
def part_d(F, shots):
    try:
        from playwright.sync_api import sync_playwright
        import uvicorn  # noqa: F401
    except Exception:
        print("[SKIP] d. PC Playwright: playwright / uvicorn not installed")
        return
    import copy
    import socket
    import threading
    from tests.shots_board import free_port, snapshot_files, restore_files
    from tests import test_blitz_tab as TB
    import atexit
    snap = snapshot_files()
    atexit.register(restore_files, snap)
    for k, v in (("LE_NO_AUTOSTART", "1"), ("LE_HEARTBEAT", "0"), ("LE_LIVE_PUBLISH", "0"), ("LE_EXEC_AUDIT", "0")):
        os.environ[k] = v
    import uvicorn
    import server
    from engine import board_api
    board_api.board_view = lambda bot, now=None: copy.deepcopy(F["board"])
    port = free_port()
    srv = uvicorn.Server(uvicorn.Config(server.app, host="127.0.0.1", port=port, log_level="warning"))
    threading.Thread(target=srv.run, daemon=True).start()
    for _ in range(300):
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
            break
        except OSError:
            time.sleep(0.1)
    base = f"http://127.0.0.1:{port}"
    with sync_playwright() as p:
        br = TB.launch(p)
        ctx = br.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
        ctx.clock.install(time=F["T"])
        pg = ctx.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(f"pc pageerror: {str(e)[:240]}"))
        pg.add_init_script("localStorage.setItem('page', 'cc');")
        pg.goto(base + "/?fxoff", wait_until="domcontentloaded")
        pg.wait_for_function("() => window.LE && window.LE.go", timeout=60000)
        ok = False
        for _ in range(3):
            TB.pc_go(pg, "cc")
            try:
                pg.wait_for_selector("#page-cc.active > #nxStatusHome .su-bar", timeout=30000)
                ok = True
                break
            except Exception:
                pass
        check("d. PC Home: the status bar on top", ok and pg.evaluate("() => document.querySelector('#page-cc').firstElementChild.id") == "nxStatusHome")
        subs = pg.eval_on_selector_all("#nav .nx-main-sub", "els => els.map(e => e.textContent.trim())")
        side = pg.eval_on_selector_all("#nav > a.nx-gl[data-g='Main']", "els => els.map(e => e.dataset.page)")
        check("d. PC sidebar: Bots · Live · Money · Insight headings, each page once, BLITZ right after ATLAS", subs == ["Bots", "Live", "Money", "Insight"] and len(side) == len(set(side))
              and side.index("blitz") == side.index("atlas") + 1, (subs, side))
        nd = pg.evaluate("() => [...document.querySelectorAll('#nav a .nx-bdot')].map(d => d.parentNode.dataset.page + ':' + d.dataset.s)")
        check("d. PC sidebar: a light next to a bot while it is in a trade (Zlarior)", "zlarior:trade" in nd, nd)
        if shots:
            pg.screenshot(path=os.path.join(shots, "polish_pc_home_1440.png"))
        seg = []
        for _ in range(3):                   # the PC app may open Start by itself on its first health ping: go again
            TB.pc_go(pg, "blitz")
            pg.wait_for_timeout(1500)
            seg = pg.eval_on_selector_all("#nxSub .nx-botseg button", "els => els.map(e => e.textContent.trim())")
            if seg:
                break
        check("d. PC BLITZ: Today · Brain · Trades · Results · Rules", seg == ["Today", "Brain", "Trades", "Results", "Rules"], seg)
        # Ctrl K finds each bot's sections and the status verdict
        pg.keyboard.press("Control+k")
        pg.wait_for_timeout(500)
        pg.fill("#cpInput", "atlas rules")
        pg.wait_for_timeout(400)
        first = pg.evaluate("() => (document.querySelector('#cpList .cp-it.on b') || {}).textContent || ''")
        pg.fill("#cpInput", "status")
        pg.wait_for_timeout(400)
        st = pg.evaluate("() => [...document.querySelectorAll('#cpList .cp-it b')].map(b => b.textContent).join(' | ')")
        pg.keyboard.press("Escape")
        check("d. PC Ctrl K: 'atlas rules' -> ATLAS · Rules; 'status' -> the status verdict", "ATLAS · Rules" in first and "Status:" in st, (first, st[:200]))
        check("d. PC: no page errors", not errs, errs[:4])
        br.close()
    srv.should_exit = True


def main():
    shots = ""
    if "--shots" in sys.argv:
        shots = sys.argv[sys.argv.index("--shots") + 1]
        os.makedirs(shots, exist_ok=True)
    part_a()
    tmp = tempfile.mkdtemp(prefix="le_ui_polish_")
    try:
        part_b(tmp)
        from tests import test_blitz_tab as TB
        F = TB.build()
        part_c(F, tmp, shots)
        part_d(F, shots)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if PERF:
        print("perf:", json.dumps(PERF))
    print(f"\nUI polish: {sum(RES)}/{len(RES)} " + ("ALL PASS" if all(RES) else "FAILED"))
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
