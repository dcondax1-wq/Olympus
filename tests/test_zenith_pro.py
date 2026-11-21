"""The Scorecard (2026-11-03 night quest, owner: "make Zenith the best trading dashboard there is"; read-only UI).

  a. static   procore.js byte-identical on both apps; the phone loads procore.js then pro.js after polish.js; caches bumped
              (phone le-public-v51+, PC le-shell-next-v31+); read-only (no fetch / POST in the renderer, nothing that arms or
              routes); Zlarior > Results starts with the Scorecard chip, More > Insight lists it, the PC sidebar Insight has it;
              the journal has tags (hub.js); docs/ZENITH_COMPARISON.md exists; live.json stays network-only in the worker
  b. node     ProUI on synthetic trades: the stats by hand (net, expectancy $ / R, PF, win rate, max drawdown, streaks), the
              score on fixed scales (a better system scores higher), the quick eval sim (all winners pass, all losers fail, the
              same seed = the same numbers, bigger size = faster both ways), the PC trade shape (pnl_r, exit_reason, swept),
              every part draws, $ next to every R, garbage in = no exception
  c. phone    Playwright 390x844 on a copy of tools/web_public with a synthetic data.json: every part draws with no page
              error and no sideways scroll, every Scorecard control is 44 px tall, the Home card, a span switch, the size
              slider, a journal tag shows up in Scorecard > Tags; More > Today links Data City (datacity/) and the
              Strategy Tree (tree/)
  d. PC       server.py + Playwright 1440x900: sidebar Insight > Scorecard, the page from the LIT replay, a part switch

  python -X utf8 -m tests.test_zenith_pro [--shots <dir>]
"""
from __future__ import annotations

import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
RES = []


def check(name, cond, info=""):
    RES.append(bool(cond))
    print(("[PASS] " if cond else "[FAIL] ") + name + ("" if cond else f"  -> {str(info)[:500]}"), flush=True)


def rd(*p):
    with open(os.path.join(ROOT, *p), encoding="utf-8") as f:
        return f.read()


# ------------------------------------------------------------------------------------------------ a. static
def part_a():
    core = rd("tools", "web_public", "procore.js")
    check("a. procore.js byte-identical on both apps", core == rd("web_next", "js", "next", "procore.js"))
    idx = rd("tools", "web_public", "index.html")
    o = [idx.find(f'src="{n}?v=') for n in ("polish.js", "procore.js", "pro.js")]
    check("a. phone index: procore.js then pro.js after polish.js", all(i > 0 for i in o) and o == sorted(o), o)
    sw, psw = rd("tools", "web_public", "sw.js"), rd("web_next", "sw.js")
    check("a. caches: phone le-public-v51+, PC le-shell-next-v31+", int(re.search(r"le-public-v(\d+)", sw).group(1)) >= 51
          and int(re.search(r"le-shell-next-v(\d+)", psw).group(1)) >= 31)
    oth = re.search(r"const OTHER_APPS = \[([^\]]*)\]", sw).group(1)
    check("a. Zenith's worker stays out of datacity/ and tree/ (their own pages)", "'datacity/'" in oth and "'tree/'" in oth, oth)
    check("a. the worker keeps live.json network-only", "live.json" in sw and re.search(r"live\.json[^\n]*network-only|network-only[^\n]*live\.json", sw) is not None)
    for n in ("procore.js", "pro.js"):
        s = rd("tools", "web_public", n)
        check(f"a. {n} is read-only (no fetch, no POST, no arm / route / order call)", "fetch(" not in s and "POST" not in s and "/api/" not in s and "arm_c" not in s and "place_order" not in s)
    pj = rd("web_next", "js", "next", "pro.js")
    check("a. PC pro.js only GETs", "POST" not in pj and "method:" not in pj)
    cl = rd("tools", "web_public", "clean.js")
    check("a. Zlarior > Results starts with the Scorecard; More > Insight lists it", "['Results', ['pro', 'perf'" in cl and "['Insight', ['pro', 'mind'" in cl and "pro: 'Scorecard'" in cl)
    rt = rd("web_next", "js", "next", "routes.js")
    check("a. PC sidebar Insight: Mind, Trader's deck, Scorecard", "['Insight', ['mind', 'deck', 'pro', 'insight']]" in rt and "PAGES.pro = proPage" in rd("web_next", "js", "app.js"))
    hub = rd("tools", "web_public", "hub.js")
    check("a. journal tags (hub.js): tag buttons, a tag filter, tags in the CSV", "data-jtag" in hub and "['jTag', 'tag']" in hub and "'note', 'tags'" in hub and 'hub.js?v=11' in idx)
    check("a. docs/ZENITH_COMPARISON.md lists the competition", os.path.exists(os.path.join(ROOT, "docs", "ZENITH_COMPARISON.md"))
          and all(w in rd("docs", "ZENITH_COMPARISON.md") for w in ("TradeZella", "Tradervue", "Edgewonk", "TraderSync")))


# ------------------------------------------------------------------------------------------------ fixtures
def trades(n=120, seed=7, start="2026-01-05"):
    """Synthetic LIT-like trades (data.json shape): ~45% stop at -1R, 30% breakeven, 25% winners 2-6R, $250 risk."""
    r = random.Random(seed)
    import datetime as dt
    d = dt.date.fromisoformat(start)
    out = []
    while len(out) < n:
        d += dt.timedelta(days=1)
        if d.weekday() > 4 or r.random() < 0.45:
            continue
        x = r.random()
        R = -1.02 if x < 0.45 else 0.02 if x < 0.75 else round(2 + r.random() * 4, 2)
        t0 = int(dt.datetime(d.year, d.month, d.day, 14, 30, tzinfo=dt.timezone.utc).timestamp()) + r.randint(0, 3) * 3600
        out.append({"day": d.isoformat(), "entry_t": t0, "exit_t": t0 + r.randint(10, 300) * 60, "side": "LONG" if r.random() < 0.5 else "SHORT",
                    "r": R, "pnl": round(R * 250, 2), "exit": "STOP" if R < -0.5 else "BE" if R < 0.5 else "TARGET", "qty": 2, "risk_usd": 250,
                    "risk_pts": 50, "mfe": max(R, 0) + 0.5, "lv": [r.choice(["asia20", "lon23", "ny930", "pd", "bu"])]})
    return out


def board(T):
    tr = [{"acct": "lit", "src": "live", "day": "2026-10-28", "entry_t": T - 5 * 86400, "exit_t": T - 5 * 86400 + 900, "side": "SHORT", "qty": 5, "r": -1.03, "usd": -437.0, "exit": "STOP", "open": False},
          {"acct": "lit", "src": "live", "day": "2026-10-29", "entry_t": T - 4 * 86400, "exit_t": T - 4 * 86400 + 900, "side": "LONG", "qty": 3, "r": 2.5, "usd": 610.0, "exit": "TARGET", "open": False}]
    return {"v": 1, "t": T - 60, "data_t": T - 60, "trades": tr,
            "lit": {"id": "lit", "name": "Zlarior", "plan": "MFFU Builder 50K", "badge": "LIVE", "balance": 49273.8, "floor": 48168.2, "room": 1105.6, "mll": 2000.0,
                    "to_target": 3726.2, "target_balance": 53000.0, "profit": -726.2, "status": "open", "session": 6, "sessions": 10, "micros": {"risk_usd": 188.0}},
            "atlas": {"id": "atlas", "name": "ATLAS", "plan": "MFFU Builder 25K", "badge": "LIVE", "balance": 24750.0, "floor": 24000.0, "room": 750.0, "mll": 1000.0,
                      "to_target": 1750.0, "target_balance": 26500.0, "profit": -250.0, "session": 6, "sessions": 10},
            "progress": {"lit": {"sessions_max": 15, "odds": {"rows": {"H2": {"label": "2026 H2 (check)", "p10": 58.6, "f10": 20.9}}}}}}


NODE = r"""
const fs = require('fs'); global.window = {}; global.localStorage = undefined;
eval(fs.readFileSync(process.argv[2], 'utf8'));
const U = window.ProUI, F = JSON.parse(fs.readFileSync(process.argv[3], 'utf8')), out = {};
const mk = (rs) => rs.map((r, i) => ({ day: `2026-03-${String(2 + i).padStart(2, '0')}`, entry_t: 1772460000 + i * 86400, exit_t: 1772460000 + i * 86400 + 1800, r, pnl: r * 100, side: 'LONG', exit: r > 0.5 ? 'TARGET' : r < -0.5 ? 'STOP' : 'BE' }));
// hand case: +3R, -1R, -1R, 0, +2R  ($300, -100, -100, 0, 200)
const H = mk([3, -1, -1, 0, 2]).map((t) => U.norm(t)), S = U.stats(H, 1, 5);
out.hand = { net: S.net, exp: S.exp, expR: S.expR, pf: S.pf, wins: S.wins, losses: S.losses, be: S.be, mdd: S.mdd, bl: S.bl, bw: S.bw, worstRun: S.worstRun, winX: S.winX };
const good = U.score(U.stats(mk([3, -1, 4, -1, 0, 3, -1, 5, 0, 2]).map((t) => U.norm(t)), 1, 10)), bad = U.score(U.stats(mk([1, -1, -1, 0.5, -1, -1, 1, -1, 0, -1]).map((t) => U.norm(t)), 1, 10));
out.score = { good: good.v, bad: bad.v, ax: good.ax.length, inRange: [good, bad].every((s) => s.v >= 0 && s.v <= 100), grade: good.g };
const W = mk(Array(12).fill(5)).map((t) => U.norm(t)), L = mk(Array(12).fill(-25)).map((t) => U.norm(t));
out.sim = { win: U.evalSim(W, 12, 1, 300), lose: U.evalSim(L, 12, 1, 300) };
const T = F.trades.map((t) => U.norm(t)).filter(Boolean);
const e1 = U.evalSim(T, 200, 1, 800), e1b = U.evalSim(T, 200, 1, 800), e2 = U.evalSim(T, 200, 2, 800);
out.det = JSON.stringify(e1) === JSON.stringify(e1b); out.e1 = e1; out.e2 = e2;
const pcT = U.norm({ day: '2026-03-02', entry_t: 1772460000, exit_t: 1772461800, pnl: 250, pnl_r: 1.0, exit_reason: 'TARGET', swept: ['lon23_l', 'bu_h'], side: 'LONG' });
out.pc = { r: pcT.r, exit: pcT.exit, lv: pcT.lv };
const pages = {};
for (const span of ['2026', 'H2', 'H1', '2021-25', 'real']) {
  const M = U.model({ now: F.T, span, mult: 1, trades: F.trades, real: F.board.trades, periods: {}, board: F.board, tags: { [U.tid(F.trades[0])]: ['A+ setup'] } });
  for (const [p] of U.PARTS) { const h = U.page(M, p, {}); pages[span + '/' + p] = { len: h.length, err: /Could not draw/.test(h), dollar: (h.match(/\$/g) || []).length, R: (h.match(/[0-9]R\b/g) || []).length }; }
}
out.pages = pages;
const M = U.model({ now: F.T, span: '2026', trades: F.trades, board: F.board, real: F.board.trades });
out.home = U.home(M, {}); out.tagsHtml = U.page(U.model({ now: F.T, span: '2026', trades: F.trades, tags: { [U.tid(F.trades[0])]: ['A+ setup'] } }), 'tags', {});
let gErr = null; try { for (const g of [null, 1, 'x', {}, { trades: [null, 1, 'x', {}, { day: 5 }], board: { lit: 3 }, real: 'x' }, { trades: [{ r: 'a', pnl: null }] }]) { const m = U.model(g); for (const [p] of U.PARTS) U.page(m, p, {}); U.home(m, {}); } } catch (e) { gErr = String(e && e.stack); }
out.gErr = gErr;
console.log(JSON.stringify(out));
"""


def part_b(F, tmp):
    fp = os.path.join(tmp, "fx.json")
    json.dump(F, open(fp, "w"))
    js = os.path.join(tmp, "node_check.js")
    open(js, "w").write(NODE)
    p = subprocess.run(["node", js, os.path.join(ROOT, "tools", "web_public", "procore.js"), fp], capture_output=True, text=True, timeout=120)
    if p.returncode:
        check("b. node runs ProUI", False, p.stderr[:1500])
        return
    O = json.loads(p.stdout.strip().splitlines()[-1])
    h = O["hand"]
    check("b. stats by hand: net $300, expectancy $60 / +0.6R, PF 2.5, 2 W / 2 L / 1 BE, win rate 50% (BE out)",
          abs(h["net"] - 300) < 1e-6 and abs(h["exp"] - 60) < 1e-6 and abs(h["expR"] - 0.6) < 1e-9 and abs(h["pf"] - 2.5) < 1e-9
          and (h["wins"], h["losses"], h["be"]) == (2, 2, 1) and abs(h["winX"] - 50) < 1e-9, h)
    check("b. max drawdown -$200, 2 losses in a row, worst losing run -$200", abs(h["mdd"] + 200) < 1e-6 and h["bl"] == 2 and abs(h["worstRun"] + 200) < 1e-6, h)
    s = O["score"]
    check("b. Zenith score: 6 axes on fixed scales, 0-100, a better system scores higher", s["ax"] == 6 and s["inRange"] and s["good"] > s["bad"] + 20, s)
    sm = O["sim"]
    check("b. eval sim: all winners pass every eval, all losers fail every eval", sm["win"]["p10"] == 100 and sm["lose"]["f10"] == 100 and sm["win"]["med"] >= 1, sm)
    check("b. eval sim: the same seed = the same numbers; 2x size passes AND fails more than 1x", O["det"] and O["e2"]["p10"] >= O["e1"]["p10"] and O["e2"]["f15"] >= O["e1"]["f15"], (O["e1"], O["e2"]))
    check("b. the PC trade shape (pnl_r, exit_reason, swept) reads the same", O["pc"] == {"r": 1.0, "exit": "TARGET", "lv": ["lon23", "bu"]}, O["pc"])
    P = O["pages"]
    bad = {k: v for k, v in P.items() if v["err"] or v["len"] < 300}
    check(f"b. every part draws for every span ({len(P)} pages)", not bad, bad)
    noD = {k: v for k, v in P.items() if v["R"] and not v["dollar"]}
    check("b. money next to R: every page that shows R also shows $", not noD and P["2026/score"]["dollar"] > 30, noD)
    check("b. Home card: score, grade, $ a trade, $ a month, the 50K's $ to go", all(w in O["home"] for w in ("Grade", "a trade", "/mo", "$3,726 to go")), O["home"][:400])
    check("b. Tags: $ by a journal tag", "A+ setup" in O["tagsHtml"] and "1 of" in O["tagsHtml"], O["tagsHtml"][:300])
    check("b. garbage in = no exception", O["gErr"] is None, O["gErr"])


# ------------------------------------------------------------------------------------------------ c. phone
def site(tmp, F):
    from tests import test_blitz_tab as TB
    s = os.path.join(tmp, "site")
    shutil.copytree(os.path.join(ROOT, "tools", "web_public"), s, ignore=shutil.ignore_patterns("fx", "node_modules", "icon_options", "jarvis", "kalshi"))
    T = F["T"]
    data = {"built": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(T - 600)),
            "live": {"last_run": T - 600, "runs": 1, "pc": {"present": True, "t": T - 60, "age_s": 60, "running": True, "every_s": 60, "host": "SURFACE"}},
            "accounts": [], "results": {"periods": {}}, "trades": list(reversed(F["trades"])), "strategy": {}, "board": F["board"],
            "news": {"events": []}, "goals": {"calendar": {"news": [], "early_close": []}}}
    for n in ("data.json", "home.json"):
        json.dump(data, open(os.path.join(s, n), "w"))
    return s, TB


def part_c(F, tmp, shots):
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        print("[SKIP] c. phone Playwright: playwright not installed")
        return
    s, TB = site(tmp, F)
    srv = TB.serve(s)
    base = f"http://127.0.0.1:{srv.server_address[1]}/"
    sh = (lambda pg, n: pg.screenshot(path=os.path.join(shots, n))) if shots else (lambda *a: None)
    with sync_playwright() as p:
        br = TB.launch(p)
        errs = []
        ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True, timezone_id="America/New_York")
        ctx.clock.install(time=F["T"])
        ctx.add_init_script("try { localStorage.setItem('le.pl.intro', JSON.stringify(new Date().toISOString().slice(0, 10))); } catch (e) {}")
        pg = ctx.new_page()
        pg.on("pageerror", lambda e: errs.append(f"pageerror: {str(e)[:240]}"))
        for host in ("**/api.github.com/**", "**/raw.githubusercontent.com/**", "**/fonts.googleapis.com/**"):
            pg.route(host, lambda r: r.fulfill(status=404, body="{}"))
        pg.goto(base + "?fxoff#/today")
        pg.wait_for_selector(".pl-home", timeout=30000)
        pg.wait_for_selector(".pr-home:not(.pr-home-wait)", timeout=15000)   # the placeholder until data.json is there (pro.js 2026-11-21)
        hc = pg.evaluate("() => { const h = document.querySelector('.pr-home'), q = document.querySelector('.pl-quick'); return { after: !!q && q.nextElementSibling && q.nextElementSibling.contains(h), text: h.textContent, hgt: h.getBoundingClientRect().height }; }")
        check("c. Home: the Scorecard card right under the quick tiles (score, $ a trade, $/mo)", hc["after"] and "Grade" in hc["text"] and "/mo" in hc["text"] and hc["hgt"] >= 44, hc)
        for part in ("score", "pace", "risk", "playbook", "sim", "tags"):
            pg.evaluate(f"location.hash = '#/pro/{part}'")
            pg.wait_for_selector(f".pr-wrap[data-pr-part='{part}']", timeout=10000)
            pg.wait_for_timeout(500)
            r = pg.evaluate("""() => ({ x: document.documentElement.scrollWidth - innerWidth, err: /Could not draw/.test(document.querySelector('#page').textContent),
                small: [...document.querySelectorAll('.pr-wrap button, .pr-wrap input, .pr-wrap a')].filter((b) => b.offsetParent !== null && b.offsetHeight < 44).map((b) => b.outerHTML.slice(0, 80) + ' ' + b.offsetHeight),
                chip: (document.querySelector('#sub .zl-chips .on') || {}).textContent || '' })""")
            check(f"c. Scorecard > {part}: draws, no sideways scroll, every control 44 px, the Results chip lit", r["x"] <= 0 and not r["err"] and not r["small"] and r["chip"].strip() == "Scorecard", r)
            sh(pg, f"pro_{part}.png")
        pg.evaluate("location.hash = '#/pro/score'")
        pg.wait_for_selector(".pr-wrap[data-pr-part='score']")
        pg.click("[data-pr-span='H2']")
        pg.wait_for_timeout(500)
        check("c. the span switch redraws (H2 · check) and is remembered", pg.evaluate("() => document.querySelector('[data-pr-span=\"H2\"]').classList.contains('on') && localStorage.getItem('le.pro.span') === '\"H2\"'"))
        pg.evaluate("location.hash = '#/pro/sim'")
        pg.wait_for_selector("[data-pr-mult]")
        pg.evaluate("() => { const r = document.querySelector('[data-pr-mult]'); r.value = '2'; r.dispatchEvent(new Event('input', { bubbles: true })); r.dispatchEvent(new Event('change', { bubbles: true })); }")
        pg.wait_for_timeout(500)
        check("c. the size slider: 2x is shown and remembered", "2.00x" in pg.inner_text("[data-pr-mult-l]") and pg.evaluate("() => localStorage.getItem('le.pro.mult')") == "2")
        pg.evaluate("location.hash = '#/journal'")
        pg.wait_for_selector("button[data-jtag]", state="attached", timeout=10000)
        pg.evaluate("() => { const d = document.querySelector('.hb-note'); d.open = true; }")
        pg.click("button[data-jtag='A+ setup']")
        tags = pg.evaluate("() => localStorage.getItem('le.jtags')")
        pg.evaluate("location.hash = '#/pro/tags'")
        pg.wait_for_selector(".pr-wrap[data-pr-part='tags']")
        pg.click("[data-pr-span='2026']")
        pg.wait_for_timeout(500)
        txt = pg.inner_text("#pr-tags")
        check("c. a journal tag shows in Scorecard > Tags with its $", tags and "A+ setup" in tags and "A+ setup" in txt and "$" in txt, (tags, txt[:300]))
        sh(pg, "pro_tags_after.png")
        pg.evaluate("location.hash = '#/system'")
        pg.wait_for_timeout(600)
        ins = pg.evaluate("() => { const s = [...document.querySelectorAll('.cl-sec')].find((x) => (x.querySelector('h4') || {}).textContent?.trim().startsWith('Insight')); return s ? [...s.querySelectorAll('.cl-row')].map((r) => r.dataset.go) : []; }")
        check("c. More > Insight starts with the Scorecard", ins[:1] == ["pro"], ins)
        site_links = pg.evaluate("() => [...document.querySelectorAll('a.cl-site')].map((a) => [a.textContent.trim().split('\\n')[0].trim(), a.getAttribute('href'), a.offsetHeight, (a.closest('.cl-sec').querySelector('h4') || {}).textContent.trim()])")
        check("c. More > Today: Data City (datacity/) and the Strategy Tree (tree/) as plain relative links, 44 px+",
              [(x[1], x[3]) for x in site_links] == [("datacity/", "Today"), ("tree/", "Today")] and all(x[2] >= 44 for x in site_links)
              and "Strategy Tree" in site_links[1][0] and "Data City" in site_links[0][0], site_links)
        pg.fill("#clQ", "tree")
        pg.wait_for_timeout(200)
        check("c. More search finds the Strategy Tree", pg.evaluate("() => { const a = document.querySelector('a.cl-site[data-site=\"tree\"]'); return !!a && !a.hidden && a.offsetParent !== null; }"))
        check("c. no page errors", not errs, errs)
        br.close()
    srv.shutdown()


def part_d(F, shots):
    """The PC dashboard (server.py on a free port, the board from the fixture): sidebar Insight > Scorecard, the page
    from GET /api/next/lit_backtest?period=all (research/lab/backtest_live.json), a part switch."""
    try:
        from playwright.sync_api import sync_playwright
        import uvicorn
    except Exception:
        print("[SKIP] d. PC Playwright: playwright / uvicorn not installed")
        return
    import atexit
    import copy
    import socket
    import threading
    from tests.shots_board import free_port, snapshot_files, restore_files
    from tests import test_blitz_tab as TB
    snap = snapshot_files()
    atexit.register(restore_files, snap)
    for k, v in (("LE_NO_AUTOSTART", "1"), ("LE_HEARTBEAT", "0"), ("LE_LIVE_PUBLISH", "0"), ("LE_EXEC_AUDIT", "0")):
        os.environ[k] = v
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
    with sync_playwright() as p:
        br = TB.launch(p)
        pg = br.new_page(viewport={"width": 1440, "height": 900})
        errs = []
        pg.on("pageerror", lambda e: errs.append(f"pc pageerror: {str(e)[:240]}"))
        pg.goto(f"http://127.0.0.1:{port}/?fxoff", wait_until="domcontentloaded")
        pg.wait_for_function("() => window.LE && window.LE.go", timeout=60000)
        side = pg.eval_on_selector_all("#nav > a.nx-gl[data-g='Main']", "els => els.map(e => e.dataset.page)")
        check("d. PC sidebar: the Scorecard right after Trader's deck (Insight)", "pro" in side and side.index("pro") == side.index("deck") + 1, side)
        TB.pc_go(pg, "pro")
        try:
            pg.wait_for_selector("#page-pro .pr-hero .pr-radar", state="attached", timeout=90000)   # the replay loads in 5-25 s
            ok = TB.pc_go(pg, "pro")             # the app may have opened Start by itself meanwhile
        except Exception:
            ok = False
        txt = pg.evaluate("() => { const e = document.querySelector('#page-pro'); return e ? (e.classList.contains('active') ? '' : '[not active] ') + e.innerText : '[no #page-pro]'; }")
        check("d. PC Scorecard: the score from the LIT replay, $ a trade and $ a month", ok and "Zenith score" in txt.replace("ZENITH SCORE", "Zenith score") and "/ trade" in txt and "a month" in txt, txt[:300])
        if ok:
            pg.click("#page-pro [data-pro-part='risk']")
            pg.wait_for_selector("#page-pro .pr-wrap[data-pr-part='risk'] .pr-uw", timeout=15000)
            check("d. PC Scorecard: a part switch draws the underwater chart", True)
            if shots:
                pg.screenshot(path=os.path.join(shots, "pc_scorecard_risk_1440.png"))
        check("d. PC: no page errors", not errs, errs)
        br.close()
    srv.should_exit = True


def main():
    shots = ""
    if "--shots" in sys.argv:
        shots = sys.argv[sys.argv.index("--shots") + 1]
        os.makedirs(shots, exist_ok=True)
    T = int(time.mktime(time.strptime("2026-11-03 15:00", "%Y-%m-%d %H:%M")))
    F = {"T": T, "trades": trades(), "board": board(T)}
    tmp = tempfile.mkdtemp(prefix="le_pro_")
    try:
        part_a()
        part_b(F, tmp)
        part_c(F, tmp, shots)
        part_d(F, shots)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    n, ok = len(RES), sum(RES)
    print(f"\nScorecard: {ok}/{n} {'ALL PASS' if ok == n else 'FAILURES'}")
    sys.exit(0 if ok == n else 1)


if __name__ == "__main__":
    main()
