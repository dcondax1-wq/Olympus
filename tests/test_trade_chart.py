"""Trade pictures (engine/trade_chart.py): one renderer for every strategy's trades, the cloud / PC / examples pipeline and
the pages that show them. Read-only, ~2 min (Playwright parts skip when it is missing).

    python -X utf8 -m tests.test_trade_chart [--shots <dir>] [--no-browser]

a. one stored 2026 trade of each strategy (LIT, LIT + Asia, EMA, MACD, S/R, Asia hunt, trend hunt) renders without error:
   1600 x 900 PNG, 25-400 KB, the setup rebuilt by the strategy's own code ("markers"), plain-words alt text
b. the markups are drawn (artist gids on the figure): entry, stop, target, exit, candles, legend + per strategy (LIT: swept
   level, sweep wick, inducement, displacement, 5m CISD, limit, 1m CISD; EMA: EMA 21 / 50, swept swing, pullback, CISD;
   MACD: level, sweep, CISD, MACD panel, divergence on price and on MACD; S/R: the day's levels, sweep, inducement, reclaim
   candle; stop hunts: hunted pool, hunt wick, strong candle, structure, resweep (Asia) / limit + inducement (trend))
c. no look-ahead in the "known" style: every bright ("k:") markup ends by the entry, every faded ("a:") candle closes after
   it, the plan lines start at it; and the markups known at the entry are the same when the picture is drawn 5 minutes after
   the entry (bars cut there) as when it is drawn after the exit
d. cloud dry run (cloud_hook on a fake state: LIT ledger + ATLAS / candidate ledgers): charts/<key>/<id>.png + index.json,
   nothing redrawn on the next run, an open trade redrawn once it finished, the site copy (site/charts + data.json view)
e. PC: PcCharts draws in a background thread; /api/next/charts + /api/next/chart/<id> serve them (and the examples)
f. tradepics.js / secondcore.js phone and PC copies byte-identical, node --check, SecondUI v7 shows the pictures (node)
g. Playwright: the phone app at 390 px (ATLAS brain cards with their latest picture, the "Trade pictures" strip, the
   full-screen viewer: open, next, close; LIT on Bot Brain and Trades) and the PC renderer at 1440 px; no console errors,
   no horizontal scroll
"""
from __future__ import annotations

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
from engine import trade_chart as TC  # noqa: E402

RESULTS = []
NEED = {
    "lit": {"k:level", "k:sweep", "k:idm", "k:disp", "k:cisd", "k:limit", "k:cisd1"},
    "lit_asia": {"k:level", "k:sweep", "k:disp", "k:cisd", "k:limit"},
    "ema_lon_vix": {"k:ema21", "k:ema50", "k:swing", "k:sweep", "k:cisd", "k:span", "a:ema21"},
    "macd_sweep": {"k:level", "k:sweep", "k:cisd", "k:macd", "k:div_price", "k:div_macd"},
    "sr_nyreclaim": {"k:level", "k:sr_level", "k:sweep", "k:idm", "k:reclaim"},
    "sh_asia": {"k:pool", "k:sweep", "k:disp", "k:mss", "k:resweep"},
    "sh_trend": {"k:pool", "k:sweep", "k:disp", "k:mss", "k:limit", "k:idm"},
}
COMMON = {"k:entry", "plan:stop", "plan:target", "a:exit", "k:candles", "legend"}


def check(name, ok, detail=None):
    RESULTS.append((name, bool(ok)))
    print(("PASS " if ok else "FAIL ") + name + ("" if ok or detail is None else f"\n     {str(detail)[:500]}"), flush=True)


def pick(key):
    """A finished 2026 H2 trade of the strategy that lasted 20+ minutes (newest first)."""
    T = TC._research_trades(key, "2026-07-01", "2026-10-16")
    for t in reversed(T):
        n = TC.norm_trade(t)
        if n.get("exit_t") and n["exit_t"] - n["entry_t"] >= 1200:
            return n
    return TC.norm_trade(T[-1])


def gids(fig):
    out = set()
    for a in fig.findobj():
        g = a.get_gid() if hasattr(a, "get_gid") else None
        if g:
            out.add(g)
    return out


def part_abc(df5, b1, tmp):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from PIL import Image
    rows = {}
    for key in TC.ORDER:
        t = pick(key)
        now = t["exit_t"] + 300
        p = os.path.join(tmp, "a", key, TC.trade_id(t) + ".png")
        t0 = time.time()
        try:
            row = TC.make(key, t, df5, b1, path=p, now=now, src="backtest")
        except Exception as e:
            check(f"a. {key}: renders", False, f"{e.__class__.__name__}: {e}")
            continue
        sec = time.time() - t0
        im = Image.open(p)
        kb = os.path.getsize(p) / 1024
        rows[key] = (t, row)
        check(f"a. {key} {row['tid']}: 1600x900 PNG, {kb:.0f} KB, setup rebuilt, {sec:.1f} s",
              im.size == (1600, 900) and 25 <= kb <= 400 and row["markers"] and sec < 15, (im.size, kb, row["markers"]))
        alt = row["alt"]
        check(f"a. {key}: alt text in plain words (side, entry, stop, target, result)",
              t["entry"] is None or (TC.side_of(t["dir"]).lower() in alt and "Stop" in alt and "target" in alt and "Result" in alt), alt)
        # b. the markups on the figure
        sp = TC.build_spec(key, t, df5, b1, now=now, src="backtest")
        b1d = sp.pop("_bars1", None)
        w = TC._cut(TC._bars(df5), t["entry_t"] - 2 * 86400, t["exit_t"] + 7200)
        w = {k: v[(w["t"] + 300) <= now] for k, v in w.items()}
        one = TC._bars(b1d if b1d is not None else b1)
        one = {k: v[(one["t"] + 60) <= now] for k, v in one.items()}
        meta = TC.render(sp, w, one, None)
        fig = meta["fig"]
        g = gids(fig)
        need = COMMON | NEED[key]
        check(f"b. {key}: markups drawn ({', '.join(sorted(NEED[key]))})", need <= g, sorted(need - g))
        texts = [x.get_text() for x in fig.findobj(matplotlib.text.Text)]
        check(f"b. {key}: plain-word labels (stop ... beyond ..., target, exit result, why it entered, ET axis)",
              any(s.startswith("stop ") and "beyond" in s for s in texts) and any(s.startswith("target ") for s in texts)
              and any(s.startswith("exit ") or s == "still open" for s in texts) and "Why it entered" in texts and "time (ET)" in texts,
              [s for s in texts if s][:12])
        plt.close(fig)
        # c. look-ahead: bright = known by the entry
        et = t["entry_t"]
        bad = [m for m in meta["marks"] if m["gid"].startswith("k:") and m.get("t1") is not None and m["t1"] > et]
        late = [m for m in meta["marks"] if m["gid"].startswith("a:candles") and m["t1"] is not None and m["t1"] <= et]
        plan = [m for m in meta["marks"] if m["gid"].startswith("plan:") and m["t0"] < et]
        check(f"c. {key}: every bright markup ends by the entry, faded candles close after it, the plan starts at it",
              not bad and not late and not plan, (bad[:3], late[:2], plan[:2]))
        sp2 = TC.build_spec(key, t, df5, b1, now=et + 300, src="backtest")
        f = lambda S: sorted((p_["kind"], p_["t"], p_.get("px")) for p_ in S["points"] if p_.get("t") and p_["t"] <= et and p_["kind"] in ("sweep", "idm", "swing")) + \
            sorted((c["kind"], c["t"]) for c in S["candles"] if c["t"] + 300 <= et) + \
            sorted((h["kind"], h["px"], h["t0"]) for h in S["hlines"] if h["kind"] in ("cisd", "mss")) + \
            sorted((lv["px"], lv["label"]) for lv in S["levels"] if lv.get("role") == "swept")
        a_, b_ = f(sp), f(sp2)
        check(f"c. {key}: the markups known at the entry are the same with the bars cut 5 min after the entry", a_ == b_ and len(a_) >= 3,
              (a_, b_))
    return rows


def part_d(df5, b1, tmp):
    out = os.path.join(tmp, "dash")
    T = {k: pick(k) for k in ("lit", "ema_lon_vix", "sh_trend")}
    led = {}
    lt = T["lit"]
    led[str(lt["entry_t"])] = {"day": lt["day"], "side": TC.side_of(lt["dir"]), "exit": lt["exit_kind"], "exit_ts": lt["exit_t"], "R": lt["r"],
                               "usd": lt["usd"], "qty": lt["qty"], "taken": True}
    e = T["ema_lon_vix"]
    e_open = {**e, "exit_kind": "OPEN", "exit_t": None, "exit": None, "r": 0.0, "usd": 0.0}
    st = {"ledger": led, "second": {"strategies": {"ema_lon_vix": {"ledger": {str(e["entry_t"]): e_open}},
                                                   "sh_trend": {"ledger": {str(T["sh_trend"]["entry_t"]): T["sh_trend"]}}}}}
    now1 = e["entry_t"] + 600
    # the LIT and S/H trades finished before now1? use each trade's own picture time: one run per "now"
    now = max(lt["exit_t"], T["sh_trend"]["exit_t"], now1) + 300
    st["second"]["strategies"]["ema_lon_vix"]["ledger"][str(e["entry_t"])] = e_open
    t0 = time.time()
    r1 = TC.cloud_hook(out, st, df5, b1, now=now, max_age_d=400)
    s1 = time.time() - t0
    ix = json.load(open(os.path.join(out, "charts", "index.json")))
    have = {k: len(v) for k, v in ix["strategies"].items()}
    files = [os.path.join(out, "charts", k, r["tid"] + ".png") for k, v in ix["strategies"].items() for r in v]
    check(f"d. cloud run 1: {len(r1.get('made') or [])} pictures in {s1:.1f} s -> charts/<key>/<id>.png + index.json",
          have.get("lit") == 1 and have.get("ema_lon_vix") == 1 and have.get("sh_trend") == 1 and all(os.path.exists(f) for f in files)
          and not r1.get("error") and not r1.get("errors"), (r1, have))
    ema_row = ix["strategies"]["ema_lon_vix"][0]
    check("d. the open EMA trade's picture says open", ema_row["open"] and ema_row["exit_kind"] == "OPEN", ema_row)
    r2 = TC.cloud_hook(out, st, df5, b1, now=now + 300, max_age_d=400)
    check("d. cloud run 2 (nothing new): nothing drawn", r2.get("made") == [], r2)
    st["second"]["strategies"]["ema_lon_vix"]["ledger"][str(e["entry_t"])] = e
    r3 = TC.cloud_hook(out, st, df5, b1, now=max(now, e["exit_t"] + 300), max_age_d=400)
    ix = json.load(open(os.path.join(out, "charts", "index.json")))
    er = ix["strategies"]["ema_lon_vix"][0]
    check("d. cloud run 3: the EMA trade finished -> its picture is redrawn with the exit", r3.get("made") == [TC.chart_id("ema_lon_vix", e)]
          and not er["open"] and er["exit_kind"] == e["exit_kind"], (r3, er.get("exit_kind")))
    site = os.path.join(tmp, "site")
    os.makedirs(site, exist_ok=True)
    v = TC.site_copy(os.path.join(out, "charts"), site)
    ok_urls = all(os.path.exists(os.path.join(site, x["url"].split("?")[0])) for s in v["strategies"].values() for x in s["items"] + s["examples"])
    check("d. site copy: site/charts/<key>/<id>.png + examples, data.json view with urls (newest first)",
          v["counts"]["live"] == 3 and v["counts"]["examples"] >= 7 and ok_urls and "lit" in v["strategies"], v["counts"])
    hv = TC.compact_view(v)
    check("d. home.json cut: <= 3 pictures per strategy", all(len(s["items"]) + len(s["examples"]) <= 3 for s in hv["strategies"].values()))
    return out, v


def part_e(df5, b1, tmp, dash):
    pc = os.path.join(tmp, "pc")
    e = pick("ema_lon_vix")
    res = TC.second_run("ema_lon_vix", df5, b1, e["exit_t"] + 300)
    P = TC.PcCharts(root=pc)
    t0 = time.time()
    started = P.tick([], {"strategies": {"ema_lon_vix": res}}, df5, b1, e["exit_t"] + 300)
    again = P.tick([], {"strategies": {"ema_lon_vix": res}}, df5, b1, e["exit_t"] + 300)
    tick_s = time.time() - t0
    while P.busy and time.time() - t0 < 120:
        time.sleep(0.2)
    ix = TC.Store(pc).ix
    n = sum(len(v) for v in ix["strategies"].values())
    check(f"e. PcCharts: drawn in a background thread ({n} pictures in {time.time() - t0:.1f} s, poll not blocked)",
          started and n >= 1 and not P.error and tick_s < 0.5, (P.error, tick_s))
    check("e. PcCharts: a busy worker skips the tick (returns at once)", again is False)
    try:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
    except Exception:
        print("[SKIP] e. API: fastapi TestClient not installed")
        return
    from engine import chart_api
    old = chart_api._dirs
    chart_api._dirs = lambda: (pc, TC.EXAMPLES)
    try:
        app = FastAPI()
        app.include_router(chart_api.router)
        c = TestClient(app)
        r = c.get("/api/next/charts")
        d = r.json()
        it = (d.get("strategies") or {}).get("ema_lon_vix", {}).get("items") or []
        check("e. GET /api/next/charts: the PC's pictures + the examples, with image urls", r.status_code == 200 and it and it[0]["url"].startswith("/api/next/chart/ema_lon_vix.")
              and all((d["strategies"].get(k) or {}).get("examples") for k in TC.ORDER), {k: len(v.get("examples") or []) for k, v in (d.get("strategies") or {}).items()})
        r2 = c.get(it[0]["url"]) if it else None
        check("e. GET /api/next/chart/<id>: the PNG", r2 is not None and r2.status_code == 200 and r2.headers["content-type"] == "image/png"
              and r2.content[:4] == b"\x89PNG")
        ex = d["strategies"]["lit"]["examples"][0]
        r3 = c.get(ex["url"])
        check("e. GET /api/next/chart/<id>?ex=1: an example", r3.status_code == 200 and r3.content[:4] == b"\x89PNG")
        check("e. bad id -> 404", c.get("/api/next/chart/..%2Fsecrets").status_code == 404 and c.get("/api/next/chart/nope.2026-01-01_0000_long").status_code == 404)
    finally:
        chart_api._dirs = old
    from engine import next_api
    app2 = FastAPI()
    app2.include_router(next_api.router)
    r = TestClient(app2).get("/api/next/charts")
    check("e. /api/next/charts mounted on the dashboard router (engine/next_api.py)", r.status_code == 200 and "strategies" in r.json(), r.status_code)


def part_f(view):
    pairs = [("tools/web_public/tradepics.js", "web_next/js/next/tradepics.js"), ("tools/web_public/secondcore.js", "web_next/js/next/secondcore.js")]
    for a, b in pairs:
        check(f"f. {os.path.basename(a)}: phone and PC copies byte-identical", open(os.path.join(ROOT, a), "rb").read() == open(os.path.join(ROOT, b), "rb").read())
    node = shutil.which("node")
    if not node:
        print("[SKIP] f. node not found")
        return
    for f in ("tools/web_public/tradepics.js", "tools/web_public/secondcore.js", "tools/web_public/second.js", "tools/web_public/brain.js"):
        r = subprocess.run([node, "--check", os.path.join(ROOT, f)], capture_output=True, text=True)
        check(f"f. node --check {f}", r.returncode == 0, r.stderr)
    tmp = tempfile.mkdtemp()
    try:
        for f in ("pics.js", "second.js", "brain.js", "trades.js"):
            g = os.path.join(tmp, f.replace(".js", ".mjs"))
            shutil.copy(os.path.join(ROOT, "web_next", "js", "next", f), g)
            r = subprocess.run([node, "--check", g], capture_output=True, text=True)
            check(f"f. node --check web_next/js/next/{f} (module)", r.returncode == 0, r.stderr)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    from tests.test_atlas_ui import sample_block
    S = json.dumps(sample_block(), default=str)
    js = ("const fs=require('fs');const window={};global.window=window;const document={head:{appendChild(){}},documentElement:{classList:{add(){},remove(){}}},"
          "getElementById(){return null},createElement(){return {}},addEventListener(){},querySelectorAll(){return []}};global.document=document;"
          f"eval(fs.readFileSync({json.dumps(os.path.join(ROOT, 'tools/web_public/tradepics.js'))},'utf8'));"
          f"eval(fs.readFileSync({json.dumps(os.path.join(ROOT, 'tools/web_public/secondcore.js'))},'utf8'));"
          f"const U=window.SecondUI;const el={{innerHTML:'',querySelectorAll(){{return []}}}};const S={S};const CH={json.dumps(view, default=str)};"
          "U.atlas(el,S,{charts:CH});const h=el.innerHTML;const b={innerHTML:''};U.brain(b,U.brainList(S,'cloud'),{charts:CH});"
          "console.log(JSON.stringify({v:U.version,cards:(h.match(/tp-card/g)||[]).length,strip:h.includes('Trade pictures'),th:(h.match(/tp-th/g)||[]).length,"
          "fail:h.includes('failed to draw'),bc:(b.innerHTML.match(/tp-card/g)||[]).length,alt:/alt=\"[A-Z][^\"]{40,}/.test(h)}));")
    jf = os.path.join(tempfile.mkdtemp(), "f.js")
    open(jf, "w", encoding="utf-8").write(js)
    r = subprocess.run([node, jf], capture_output=True, text=True)
    shutil.rmtree(os.path.dirname(jf), ignore_errors=True)
    try:
        o = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        o = {"err": r.stderr[-500:]}
    check("f. SecondUI v7: each member's brain card shows its latest picture, the ATLAS page a 'Trade pictures' strip, alt text",
          o.get("v", 0) >= 7 and o.get("cards", 0) >= 3 and o.get("strip") and o.get("th", 0) >= 3 and not o.get("fail") and o.get("bc", 0) >= 3 and o.get("alt"), o)


def part_g(view, site_dir, shots):
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        print("[SKIP] g. Playwright not installed")
        return
    from tests.test_atlas_ui import _launch, _serve, sample_block, sample_data
    tmp = tempfile.mkdtemp()
    site = os.path.join(tmp, "site")
    shutil.copytree(os.path.join(ROOT, "tools", "web_public"), site, ignore=shutil.ignore_patterns("fx", "node_modules"))
    shutil.copytree(os.path.join(site_dir, "charts"), os.path.join(site, "charts"))
    data = sample_data(sample_block())
    data["charts"] = view
    json.dump(data, open(os.path.join(site, "data.json"), "w"), default=str)
    json.dump({**data, "charts": TC.compact_view(view)}, open(os.path.join(site, "home.json"), "w"), default=str)
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
            pg.goto(url + "?fxoff#/atlas/brain")            # 2026-10-25 PM: the ATLAS tab in parts; the member brains are its Brain section
            pg.wait_for_selector("#atRoot .at-hero", state="attached", timeout=20000)
            pg.wait_for_timeout(800)
            n_cards = pg.eval_on_selector_all("#atRoot .sb-card .tp-card", "e => e.length")
            n_th = pg.eval_on_selector_all("#atRoot .at-pics .tp-th", "e => e.length")
            check("g. phone ATLAS: each member's brain card has its latest picture + the 'Trade pictures' strip",
                  n_cards == 3 and n_th >= 3, (n_cards, n_th))
            pg.eval_on_selector("#atRoot .sb-card .tp-big", "e => e.scrollIntoView()")
            pg.wait_for_function("() => { const i = document.querySelector('#atRoot .sb-card .tp-big img'); return i && i.complete && i.naturalWidth > 0; }", timeout=15000)
            nat = pg.eval_on_selector("#atRoot .sb-card .tp-big img", "i => [i.naturalWidth, i.naturalHeight, i.alt.length, i.getAttribute('loading')]")
            check("g. phone: the picture loads (1600 x 900, lazy, alt text), the skeleton goes away",
                  nat[0] == 1600 and nat[1] == 900 and nat[2] > 40 and nat[3] == "lazy"
                  and pg.eval_on_selector("#atRoot .sb-card .tp-big .tp-sk", "e => e.classList.contains('ok')"), nat)
            ov = pg.evaluate("() => document.documentElement.scrollWidth - innerWidth")
            check("g. phone ATLAS: no horizontal scroll at 390 px", ov <= 1, ov)
            if shots:
                pg.screenshot(path=os.path.join(shots, "phone_atlas_pics_390.png"))
            pg.tap("#atRoot .sb-card .tp-big")
            pg.wait_for_selector(".tp-lb.on", timeout=5000)
            pg.wait_for_function("() => document.querySelector('.tp-lb').classList.contains('ok')", timeout=10000)
            n1 = pg.inner_text(".tp-lb-n")
            box = pg.eval_on_selector(".tp-lb-img", "e => { const r = e.getBoundingClientRect(); return [Math.round(r.width), Math.round(r.height)]; }")
            check("g. phone: tap = full-screen viewer, the picture fills the width", box[0] >= 380 and n1.startswith("1 /"), (box, n1))
            if shots:
                pg.screenshot(path=os.path.join(shots, "phone_viewer_390.png"))
            # swipe left (pointer events on the stage) -> the next trade
            st = pg.eval_on_selector(".tp-lb-stage", "e => { const r = e.getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; }")
            pg.evaluate("""([x, y]) => { const s = document.querySelector('.tp-lb-stage');
                const ev = (t, cx) => s.dispatchEvent(new PointerEvent(t, {pointerId: 7, clientX: cx, clientY: y, bubbles: true, pointerType: 'touch'}));
                ev('pointerdown', x + 120); ev('pointermove', x + 40); ev('pointermove', x - 60); ev('pointerup', x - 80); }""", st)
            pg.wait_for_timeout(300)
            n2 = pg.inner_text(".tp-lb-n")
            check("g. phone viewer: swipe = the next trade", n2.startswith("2 /"), (n1, n2))
            pg.evaluate("""([x, y]) => { const s = document.querySelector('.tp-lb-stage');
                const ev = (t, id, cx) => s.dispatchEvent(new PointerEvent(t, {pointerId: id, clientX: cx, clientY: y, bubbles: true, pointerType: 'touch'}));
                ev('pointerdown', 1, x - 30); ev('pointerdown', 2, x + 30); ev('pointermove', 1, x - 90); ev('pointermove', 2, x + 90); ev('pointerup', 1, x - 90); ev('pointerup', 2, x + 90); }""", st)
            sc = pg.eval_on_selector(".tp-lb-img", "e => e.style.transform")
            check("g. phone viewer: pinch = zoom", "scale(" in sc and float(sc.split("scale(")[1].split(")")[0]) > 2.0, sc)
            pg.keyboard.press("Escape")
            pg.wait_for_timeout(200)
            check("g. phone viewer: closes", not pg.is_visible(".tp-lb.on"))
            pg.goto(url + "?fxoff#/trades")
            pg.wait_for_timeout(1500)
            check("g. phone Trades: 'Trade pictures · LIT' strip", pg.eval_on_selector_all(".tp-trades .tp-th", "e => e.length") >= 3)
            pg.goto(url + "?fxoff#/brain")
            pg.wait_for_timeout(1200)
            check("g. phone Bot Brain (LIT): the latest LIT picture", pg.eval_on_selector_all(".bz-pic .tp-big", "e => e.length") == 1)
            ov = pg.evaluate("() => document.documentElement.scrollWidth - innerWidth")
            check("g. phone Bot Brain: no horizontal scroll at 390 px", ov <= 1, ov)
            if shots:
                pg.screenshot(path=os.path.join(shots, "phone_brain_390.png"))
            check("g. no page / console errors on the phone", not errs, errs[:5])
            # PC renderer copies at 1440 px
            pc = os.path.join(tmp, "pc")
            os.makedirs(pc)
            for f in ("secondcore.js", "tradepics.js"):
                shutil.copy(os.path.join(ROOT, "web_next", "js", "next", f), os.path.join(pc, f))
            shutil.copytree(os.path.join(site_dir, "charts"), os.path.join(pc, "charts"))
            json.dump(sample_block(), open(os.path.join(pc, "s.json"), "w"), default=str)
            json.dump(view, open(os.path.join(pc, "c.json"), "w"), default=str)
            open(os.path.join(pc, "index.html"), "w").write(
                "<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width'><title>Trade pictures PC check</title>"
                "<style>body{background:#0b0d12;color:#e8ecf4;font:14px system-ui;margin:0;padding:24px;max-width:1240px}</style>"
                "<div id=at></div><script src='tradepics.js'></script><script src='secondcore.js'></script><script>"
                "Promise.all([fetch('s.json').then(r=>r.json()),fetch('c.json').then(r=>r.json())]).then(([S,CH])=>{"
                "window.SecondUI.atlas(document.getElementById('at'),S,{charts:CH});document.body.dataset.done=1;});</script>")
            srv2 = _serve(pc)
            try:
                pg2 = b.new_page(viewport={"width": 1440, "height": 1000})
                errs2 = []
                pg2.on("pageerror", lambda e: errs2.append(str(e)[:200]))
                pg2.on("console", lambda m: errs2.append(m.text[:200]) if m.type == "error" and "favicon" not in m.text
                       and "Failed to load resource" not in m.text else None)
                pg2.goto(f"http://127.0.0.1:{srv2.server_address[1]}/")
                pg2.wait_for_selector("body[data-done]", timeout=10000)
                pg2.wait_for_timeout(800)
                n = pg2.eval_on_selector_all(".sb-card .tp-card", "e => e.length")
                pg2.click(".sb-card .tp-big")
                pg2.wait_for_selector(".tp-lb.on", timeout=5000)
                pg2.keyboard.press("ArrowRight")
                n2 = pg2.inner_text(".tp-lb-n")
                if shots:
                    pg2.screenshot(path=os.path.join(shots, "pc_viewer_1440.png"))
                pg2.keyboard.press("Escape")
                check("g. PC 1440 px: brain cards with pictures, the viewer opens, arrow = next trade, no console errors",
                      n == 3 and n2.startswith("2 /") and not errs2, (n, n2, errs2[:3]))
                if shots:
                    pg2.screenshot(path=os.path.join(shots, "pc_atlas_pics_1440.png"), full_page=True)
            finally:
                srv2.shutdown()
            b.close()
    finally:
        srv.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    args = sys.argv[1:]
    shots = args[args.index("--shots") + 1] if "--shots" in args else None
    if shots:
        os.makedirs(shots, exist_ok=True)
    tmp = tempfile.mkdtemp()
    t0 = time.time()
    try:
        df5, b1 = TC.research_bars()
        part_abc(df5, b1, tmp)
        dash, view = part_d(df5, b1, tmp)
        part_e(df5, b1, tmp, dash)
        part_f(view)
        if "--no-browser" not in args:
            part_g(view, os.path.join(tmp, "site"), shots)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    n_ok = sum(1 for _, ok in RESULTS if ok)
    print(f"\n{n_ok}/{len(RESULTS)} passed in {time.time() - t0:.0f} s")
    return 0 if n_ok == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
