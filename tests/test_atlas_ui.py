"""ATLAS (strategy 2, the 25K; internal key "second") on the dashboards: the phone's ATLAS bottom tab + page, the Home
two-strategy cards (LIT · 50K / ATLAS · 25K), the ATLAS brain per member, the renames (Second strategies -> ATLAS) and
the PC copy of the renderer. Read-only, ~30 s with Playwright (skipped parts say so).

    python -X utf8 -m tests.test_atlas_ui [--shots <dir>] [--no-browser]

a. engine/second.dashboard_block carries "atlas" (research/second/atlas.json, else the account-B 25K research)
b. secondcore.js: phone and PC copies byte-identical, node --check, SecondUI.atlas / twoCards render in node (stub DOM)
c. the phone app at 390 px (Playwright, sample data.json): bottom bar Home · Brain · ATLAS · Trades · Money · More, the
   Home cards, the ATLAS page (hero, 25K eval card, brain cards for the 3 members, go / no-go, trades, rules, backtest),
   #/second opens ATLAS, the Brain toggle says "ATLAS brain", no page errors, no horizontal scroll; screenshots
d. the PC renderer copy in a static page at 1440 px (Playwright): ATLAS page + two cards, no page errors; screenshot
"""
from __future__ import annotations

import functools
import glob
import http.server
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import second  # noqa: E402

RESULTS = []
DAY = "2026-10-22"


def check(name, ok, detail=None):
    RESULTS.append((name, bool(ok)))
    print(("PASS " if ok else "FAIL ") + name + ("" if ok or detail is None else f"\n     {str(detail)[:400]}"), flush=True)


def _rows(rs, t0, day=DAY, usd=500.0):
    return [{"entry_t": t0 + 1800 * i, "exit_t": t0 + 1800 * i + 900, "exit_kind": "TARGET" if r > 0 else "STOP", "r": r, "dir": 1 if i % 2 else -1,
             "side": "LONG" if i % 2 else "SHORT", "qty": 3, "entry": 25100.25 + i, "stop": 25080.0, "target": 25160.0,
             "usd": round(r * usd, 2), "day": day, "lit": {"taken": True, "usd": round(r * usd, 2)}} for i, r in enumerate(rs)]


def _brain(k, stage, ok_n):
    names = ["Inside its hours", "Trend filter", "Sweep of a level", "5m CISD close", "Stop 8-80 pts", "Target >= 1.5R"]
    ck = [{"k": f"c{i}", "name": n, "val": f"value {i}", "need": "the rule", "ok": True if i < ok_n else (False if i == ok_n else None)}
          for i, n in enumerate(names)]
    return {"stage": stage, "text": f"{k}: waiting for a sweep of the London low", "checks": ck, "first_fail": f"c{ok_n}" if ok_n < len(names) else None,
            "plan": {"side": "long", "entry": 25110.5, "stop": 25090.25, "risk_pts": 20.25, "target": 25170.0, "rr": 2.9, "qty_500": 12, "when": "09:35"},
            "log": [{"text": "09:30 level swept"}, {"text": "09:35 CISD close", "signal": True}], "closed_bars_only": True}


def sample_block(acct_b=False):
    T = 1_792_660_000      # 2026-10-22 morning ET
    led = {"ema_lon_vix": _rows([1.8, -1.0], T) + _rows([2.1, -1.0, 1.4], T - 4 * 86400, day="2026-10-19"),
           "macd_sweep": _rows([-1.0], T + 7200) + _rows([1.6], T - 2 * 86400, day="2026-10-20"),
           "sr_nyreclaim": _rows([2.5, -1.0], T - 6 * 86400, day="2026-10-16")}
    st = {"first_run": T - 10 * 86400, "t": T + 9000, "strategies": {
        k: {"ledger": {str(t["entry_t"]): t for t in v}, "state": {"stage": "waiting", "text": f"{k} waiting", "day": DAY},
            "brain": _brain(k, ["waiting", "armed", "done"][i], [2, 4, 6][i])} for i, (k, v) in enumerate(led.items())}}
    st["strategies"]["lit_asia"] = {"ledger": {}, "state": {"stage": "off", "text": "outside Asia", "day": DAY}}
    route = None
    if acct_b:
        route = {"keys": [], "account": "Sim101", "account_b": {
            "label": "ATLAS Sim102", "account": "Sim102", "plan": "builder25k", "plan_label": "MFFU Builder 25K", "kind": "SIM", "sizing": "need",
            "keys": list(second.ATLAS_KEYS), "enabled": True, "disabled": None,
            "eval": {"balance": 25640.0, "floor": 24000.0, "room": 1640.0, "target": 26500.0, "to_target": 860.0, "session": 4, "status": "open", "start": "2026-10-19"},
            "open": None, "routed": [], "day_pnl": 400.0, "entries_today": 1, "locked": None, "note": "own account"}}
    return second.dashboard_block(st, route=route)


def sample_data(block):
    T = int(time.time())
    acct = {"id": "mffu50k_eval", "name": "MFFU 50K Eval", "firm": "MFFU", "plan": "Builder 50K", "kind": "eval", "source": "pc", "badge": "SIM",
            "conn": {"present": True, "t": T - 30, "age_s": 30, "connected": True, "has_detail": True, "running": True, "host": "SURFACE"},
            "eval": {"balance": 51250, "profit": 1250, "to_target": 1750, "floor": 48500, "room": 2750, "mll": 2000, "dll": 1000, "dll_used": 0,
                     "session": 5, "sessions": 10}, "pnl": {"today": 0, "week": 1250}, "position": None, "orders": [], "trades": [], "days": [], "stats": {"n": 2}}
    brain = {"t": T - 30, "at": "09:41 ET", "stage": {"key": "sweep", "label": "Sweep", "n": 2, "waiting": "Waiting for a sweep of the London low (25,080)"},
             "stages": [["levels", "done"], ["sweep", "now"]], "guards": {}, "levels": [], "setups": [], "log": []}
    return {"built": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(T - 300)),
            "live": {"last_run": T - 300, "runs": 1, "brain": brain,
                     "pc": {"present": True, "t": T - 30, "age_s": 30, "running": True, "every_s": 60, "host": "SURFACE", "brain": brain},
                     "pc_verdict": {"code": "SIM", "label": "ON SIM", "level": "warn", "reason": "Sim101: not your eval"}},
            "accounts": [acct], "results": {"periods": {}}, "trades": [], "strategy": {}, "second": block}


def part_a():
    b = sample_block()
    A = b.get("atlas") or {}
    src = "atlas.json" if os.path.exists(os.path.join(ROOT, "research", "second", "atlas.json")) else "account_b.json"
    check(f"a. dashboard_block['atlas']: name ATLAS, 3 members, numbers + 25K eval odds (from {src})",
          A.get("name") == "ATLAS" and len(A.get("members") or []) == 3 and (A.get("numbers") or A.get("eval25k")) and not A.get("error"), A)
    if src == "account_b.json":
        check("a. fallback numbers = research/second/account_b.json builder25k|need (H1 2-week pass)",
              abs(A["eval25k"]["H1"]["p10"] - json.load(open(os.path.join(ROOT, "research", "second", "account_b.json")))["plans"]["builder25k|need"]["H1"]["p10"]) < 1e-9)
    L = "\n".join(second.readme_lines({"first_run": 1, "t": 2, "strategies": {}}))
    check("a. cloud README section titled 'ATLAS (paper)'", "## ATLAS (paper)" in L, L[:200])


def part_b():
    a = os.path.join(ROOT, "tools", "web_public", "secondcore.js")
    p = os.path.join(ROOT, "web_next", "js", "next", "secondcore.js")
    check("b. secondcore.js: phone and PC copies byte-identical", open(a, "rb").read() == open(p, "rb").read())
    node = shutil.which("node")
    if not node:
        check("b. node available", False, "node not found")
        return
    for f in (a, os.path.join(ROOT, "tools", "web_public", "second.js")):
        r = subprocess.run([node, "--check", f], capture_output=True, text=True)
        check(f"b. node --check {os.path.relpath(f, ROOT)}", r.returncode == 0, r.stderr)
    tmp = tempfile.mkdtemp()
    try:
        g = os.path.join(tmp, "second.mjs")
        shutil.copy(os.path.join(ROOT, "web_next", "js", "next", "second.js"), g)
        r = subprocess.run([node, "--check", g], capture_output=True, text=True)
        check("b. node --check web_next/js/next/second.js (module)", r.returncode == 0, r.stderr)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    for ab in (False, True):
        data = json.dumps(sample_block(ab), default=str)
        js = ("const fs=require('fs');const window={};const document={head:{appendChild(){}},getElementById(){return null},"
              "createElement(){return {}}};global.window=window;global.document=document;"
              f"eval(fs.readFileSync({json.dumps(a)},'utf8'));const U=window.SecondUI;const el={{innerHTML:''}};const S={data};"
              "U.atlas(el,S,{});const h=el.innerHTML;const c=U.atlasCard(S,null,null);const two=U.twoCards([{name:'LIT',plan:'50K',status:'ON SIM',lvl:'warn',today:0,week:1,prog:.4},c]);"
              "console.log(JSON.stringify({v:U.version,fail:h.includes('failed to draw'),brain:(h.match(/sb-card/g)||[]).length,go:h.includes('Go / no-go'),"
              "bt:h.includes('Backtest numbers'),ev:h.includes('25K eval odds'),rules:h.includes('Rules in plain words'),lit:h.includes('never opposite to LIT'),"
              "acct:h.includes('Sim102'),st:c.status,two:two.includes('at-two-c')&&two.includes('ATLAS'),other:h.includes('Other paper shadows')}));")
        r = subprocess.run([node, "-e", js], capture_output=True, text=True)
        try:
            o = json.loads(r.stdout.strip().splitlines()[-1])
        except Exception:
            o = {"err": r.stderr[-400:]}
        tag = "SIM on account B" if ab else "paper"
        check(f"b. SecondUI v5 atlas() renders ({tag}): 3 brain cards, go / no-go, backtest + 25K odds, rules, with LIT, other shadows",
              o.get("v") == 5 and not o.get("fail") and o.get("brain") == 3 and o.get("go") and o.get("bt") and o.get("ev") and o.get("rules")
              and o.get("lit") and o.get("other") and (o.get("acct") if ab else True), o)
        check(f"b. atlasCard status ({tag})", o.get("st") == ("SIM" if ab else "PAPER") and o.get("two"), o.get("st"))


def _launch(p):
    try:
        return p.chromium.launch()
    except Exception:
        for exe in sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"), reverse=True):
            return p.chromium.launch(executable_path=exe)
        raise


def _serve(d):
    class Q(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a, **k):
            pass
    h = functools.partial(Q, directory=d)
    s = http.server.ThreadingHTTPServer(("127.0.0.1", 0), h)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s


def part_c(shots):
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        print("[SKIP] c. phone Playwright: playwright not installed")
        return
    tmp = tempfile.mkdtemp()
    site = os.path.join(tmp, "site")
    shutil.copytree(os.path.join(ROOT, "tools", "web_public"), site, ignore=shutil.ignore_patterns("fx", "node_modules"))
    data = sample_data(sample_block(acct_b=True))
    for n in ("data.json", "home.json"):
        json.dump(data, open(os.path.join(site, n), "w"), default=str)
    srv = _serve(site)
    url = f"http://127.0.0.1:{srv.server_address[1]}/"
    try:
        with sync_playwright() as p:
            b = _launch(p)
            pg = b.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
            errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
            pg.on("console", lambda m: errs.append("console: " + m.text[:200]) if m.type == "error" and "Failed to load resource" not in m.text
                  and "api.github.com" not in m.text and "raw.githubusercontent" not in m.text else None)
            pg.route("https://api.github.com/**", lambda r: r.fulfill(status=404, body="{}"))
            pg.route("https://raw.githubusercontent.com/**", lambda r: r.fulfill(status=404, body="{}"))
            pg.goto(url + "?fxoff#/today")
            pg.wait_for_selector(".at-two-c", timeout=20000)
            if pg.query_selector("#moInstX"):
                pg.click("#moInstX")                  # the browser-only "Add to Home Screen" guide (not in the installed app)
                pg.wait_for_selector(".at-two-c", timeout=10000)
            pg.wait_for_timeout(800)
            tabs = pg.eval_on_selector_all("#tabs a span", "els => els.map(e => e.textContent.trim())")
            check("c. phone bottom bar = Home · Brain · ATLAS · Trades · Money · More", tabs == ["Home", "Brain", "ATLAS", "Trades", "Money", "More"], tabs)
            cards = pg.eval_on_selector_all(".at-two-c", "els => els.map(e => e.innerText)")
            check("c. Home: two cards 'LIT' + 'ATLAS' on top (status, today, week, eval)", len(cards) == 2 and cards[0].startswith("LIT") and cards[1].startswith("ATLAS")
                  and "THIS WEEK" in cards[0].upper() and "SIM" in cards[1].upper() and "TO PASS" in cards[0].upper(), cards)
            first = pg.evaluate("() => { const p = document.querySelector('#page'); const c = p.querySelector('.at-two'), h = p.querySelector('.hb-hero'); return !!c && !!h && !!(c.compareDocumentPosition(h) & 4); }")
            check("c. Home: the two cards come first, above the 'Is the bot trading my eval?' card", first and pg.evaluate("() => { const f = document.querySelector('#page').querySelector('.card:not(#moInst), .at-two'); return !!f && f.classList.contains('at-two'); }"))
            box = pg.evaluate("() => [...document.querySelectorAll('.at-two-c')].map(e => { const r = e.getBoundingClientRect(); return [Math.round(r.left), Math.round(r.width)]; })")
            check("c. Home: the cards are side by side at 390 px", len(box) == 2 and box[0][0] < box[1][0] and all(w > 120 for _, w in box), box)
            ov = pg.evaluate("() => document.documentElement.scrollWidth - innerWidth")
            check("c. Home: no horizontal scroll at 390 px", ov <= 1, ov)
            if shots:
                pg.screenshot(path=os.path.join(shots, "phone_home_390.png"))
            pg.click("#tabs a[data-t='atlas']")
            pg.wait_for_selector("#atRoot .at-hero", timeout=10000)
            pg.wait_for_timeout(600)
            t = pg.eval_on_selector("#page", "e => e.textContent")
            n_b = pg.eval_on_selector_all("#atRoot .sb-card", "els => els.length")
            check("c. ATLAS page: 3 member brain cards (EMA, MACD, S/R) with rule checks", n_b == 3 and pg.eval_on_selector_all("#atRoot .sb-ck li", "e => e.length") >= 18, n_b)
            check("c. ATLAS page: hero SIM on Sim102, 25K eval card, go / no-go, trades, rules, backtest, with LIT",
                  "SIM on Sim102" in t and "MFFU Builder 25K" in t and "Go / no-go" in t and "Trades" in t and "Rules in plain words" in t
                  and "Backtest numbers" in t and "never opposite to LIT" in t, t[:600])
            check("c. ATLAS page: no 'Second strateg' / 'Account B' text left", "Second strateg" not in t and "Account B" not in t)
            ov = pg.evaluate("() => document.documentElement.scrollWidth - innerWidth")
            check("c. ATLAS page: no horizontal scroll at 390 px", ov <= 1, ov)
            if shots:
                pg.screenshot(path=os.path.join(shots, "phone_atlas_390.png"))
                pg.screenshot(path=os.path.join(shots, "phone_atlas_390_full.png"), full_page=True)
            pg.goto(url + "?fxoff#/second")
            pg.wait_for_selector("#atRoot .at-hero", timeout=10000)
            check("c. #/second (old push links) opens ATLAS", pg.eval_on_selector("#tabs a.on", "e => e.dataset.t") == "atlas")
            pg.goto(url + "?fxoff#/brain")
            pg.wait_for_timeout(1200)
            bt = pg.inner_text("#page")
            check("c. Bot Brain toggle: 'LIT brain' / 'ATLAS brain'", "LIT brain" in bt and "ATLAS brain" in bt and "Second-strategy" not in bt, bt[:300])
            pg.goto(url + "?fxoff#/system")
            pg.wait_for_timeout(800)
            st = pg.inner_text("#page")
            check("c. More holds the LIT Strategy page (folded in)", "Strategy" in st, st[:300])
            check("c. no page / console errors on the phone", not errs, errs[:5])
            b.close()
    finally:
        srv.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)


def part_d(shots):
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        print("[SKIP] d. PC Playwright: playwright not installed")
        return
    tmp = tempfile.mkdtemp()
    shutil.copy(os.path.join(ROOT, "web_next", "js", "next", "secondcore.js"), os.path.join(tmp, "secondcore.js"))
    json.dump(sample_block(acct_b=False), open(os.path.join(tmp, "s.json"), "w"), default=str)
    open(os.path.join(tmp, "index.html"), "w").write(
        "<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width'><title>ATLAS PC check</title>"
        "<style>body{background:#0b0d12;color:#e8ecf4;font:14px system-ui;margin:0;padding:24px;max-width:1200px}</style>"
        "<div id=two></div><div id=at></div><script src='secondcore.js'></script><script>"
        "fetch('s.json').then(r=>r.json()).then(S=>{const U=window.SecondUI;"
        "document.getElementById('two').innerHTML=U.twoCards([{name:'LIT',plan:'MFFU Builder 50K',status:'ON SIM',lvl:'warn',today:0,week:1250,prog:.42,progText:'$1,750 to pass · session 5/10',next:'Waiting for a sweep'},U.atlasCard(S,null,null)]);"
        "U.atlas(document.getElementById('at'),S,{});document.body.dataset.done=1;});</script>")
    srv = _serve(tmp)
    try:
        with sync_playwright() as p:
            b = _launch(p)
            pg = b.new_page(viewport={"width": 1440, "height": 1000})
            errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)[:200]))
            pg.goto(f"http://127.0.0.1:{srv.server_address[1]}/")
            pg.wait_for_selector("body[data-done]", timeout=10000)
            t = pg.inner_text("body")
            check("d. PC copy renders the ATLAS page + the two cards (PAPER, 3 brains)", "PAPER" in t and pg.eval_on_selector_all(".sb-card", "e => e.length") == 3
                  and pg.eval_on_selector_all(".at-two-c", "e => e.length") == 2 and not errs, errs or t[:300])
            if shots:
                pg.screenshot(path=os.path.join(shots, "pc_atlas_1440.png"), full_page=True)
            b.close()
    finally:
        srv.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)


def part_e():
    idx = open(os.path.join(ROOT, "tools", "web_public", "index.html"), encoding="utf-8").read()
    sw = open(os.path.join(ROOT, "tools", "web_public", "sw.js"), encoding="utf-8").read()
    ro = open(os.path.join(ROOT, "web_next", "js", "next", "routes.js"), encoding="utf-8").read()
    app = open(os.path.join(ROOT, "web_next", "js", "app.js"), encoding="utf-8").read()
    html = open(os.path.join(ROOT, "web_next", "index.html"), encoding="utf-8").read()
    check("e. phone loads secondcore.js?v=5 + second.js?v=3, SW cache le-public-v26",
          "secondcore.js?v=5" in idx and "second.js?v=3" in idx and "le-public-v26" in sw)
    check("e. PC: top-level ATLAS entry, page-atlas, Today #twoStrat, #second -> atlas",
          "{ id: 'atlas', label: 'ATLAS'" in ro and 'id="page-atlas"' in html and 'id="twoStrat"' in html and "if (page === 'second') page = 'atlas';" in app
          and "atlas: atlasPage" in app and "initTwoCards()" in app)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    shots = None
    if "--shots" in argv:
        shots = argv[argv.index("--shots") + 1]
        os.makedirs(shots, exist_ok=True)
    part_a(); part_b(); part_e()
    if "--no-browser" not in argv:
        part_c(shots); part_d(shots)
    n = sum(1 for _, ok in RESULTS if ok)
    print(f"atlas ui: {n}/{len(RESULTS)} checks passed")
    return 0 if n == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
