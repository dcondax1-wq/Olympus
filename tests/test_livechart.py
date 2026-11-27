"""The NQ live chart (day-livechart 2026-11-27): what the bots see, drawn on the NQ chart. lcmodel.js (pure, node) + nqchart.js's live layer.

  a. static   lcmodel.js pure (no document / window / fetch), text only, GET only, chart.css v3 has the live styles, taps >= 44, reduced motion
  b. node     the glance -> stage 4/10, ATLAS armed SHORT, the bots' levels + a sweep on the bars, absorption today only, EMA 50, open trade $,
              today's halt from brief.json (13:15, today only), the ticker newest first with emojis, the next trigger, private bars + the forming
              bar, the honest stamp (LIVE <= 20 s on the private link, "As of HH:MM ET" on the public feed)
  c. Chromium 390 x 844 + 1440 (public feed, fixture bars + a glance post): the stage strip, the chips, the ticker, the next line, the EMA,
              the stop / target lines with $, the halt line drawn, replay scrubs and comes back, a tap on the sweep opens why; a stale feed says so;
              the private link (?priv=1 + /api/live/state) shows LIVE from your PC, the forming bar, and a tick glides the last close
    python -X utf8 -m tests.test_livechart [--static] [--shots]

lcmodel.js inputs (all optional; a missing one = that layer is not drawn, never invented):
  lite    the PC's status post (pc_feed.js): price + t, pc.glance.bots (lit / atlas: stage, lv, arm, pos, wait, why, log, px), ext glog
  priv    the bot's own snapshot on the private link (GET /api/live/state: bars = its last 5-minute bars, state.price, last_poll)
  brief   nq/brief.json (day, early_close); ofroom nq/of_room.json (day, levels: px, side, read, t)
  bars / candles  the raw bars [t, o, h, l, c] and nqbars.model's candles (New York wall time)
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import subprocess
import sys
import tempfile
from zoneinfo import ZoneInfo

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import agora_kit as AK  # noqa: E402
from tests import test_nq_chart as T  # noqa: E402

check = AK.check
D = os.path.join(AK.WEB, "nq")
ET = ZoneInfo("America/New_York")
NOW = int(dt.datetime(2026, 11, 27, 12, 40, tzinfo=ET).timestamp())      # the day after Thanksgiving, CME halts 13:15 ET
SHOTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "research", "handoff", "2026-11-27", "livechart", "shots")


def glance(post_info, now=NOW):
    bars, op = post_info["bars"], post_info["opens"][0]
    today = [b for b in bars if b[0] >= now - 15 * 3600]
    sw = next(b for b in today[5:] if b[4] - b[3] >= 1.0)                    # a bar whose close sits >= 1 point over its low: its low + 0.25 is swept
    asia_lo = sw[3] + 0.25
    hi = max(b[2] for b in bars) + 30
    lit = {"id": "lit", "name": "Zlarior", "on": True, "mode": "eval", "stage": "Displacement (4/10)", "wait": "Waiting for a 5m CISD after the Asia low sweep",
           "why": "Asia low swept; displacement up needed before an entry.", "arm": [{"side": "LONG", "text": "armed long", "trig": "a 5m close over 21,520 (CISD) -> LONG, stop 1 tick under the sweep"}],
           "lv": [["Asia low", asia_lo, 12.0], ["PD high", hi, -30.0]], "px": bars[-1][4],
           "pos": {"side": "SHORT", "qty": 6, "entry": op["e"], "stop": op["sl"], "target": op["tp"], "risk_usd": 222, "tgt_usd": 735, "now_usd": 12}}
    atlas = {"id": "atlas", "name": "ATLAS", "on": True, "mode": "funded", "stage": "", "arm": [{"side": "SHORT", "text": "armed short", "trig": "a pullback into the 5m EMA 50"}],
             "lv": [["EMA 50", bars[-1][4] + 3, 3.0]], "px": bars[-1][4]}
    glog = {"lit": [["12:38", "Asia low swept at the open, watching for displacement"], ["12:20", "Entered SHORT 6 micros"], ["11:55", "No trade: waiting for the sweep"]],
            "atlas": [["12:35", "Armed SHORT under the EMA 50"], ["12:05", "Stopped out -$44"]]}
    return {"kind": "le-live", "lite": True, "t": now - 30, "price": bars[-1][4], "pc": {"glance": {"t": now - 30, "bots": [lit, atlas]}}, "glog": glog}, asia_lo


def core_body(lite, t):
    return json.dumps({"event": "message", "time": t, "message": json.dumps(lite)}) + "\n"


def test_static():
    js, lm, css = (AK.read(os.path.join(D, n)) for n in ("nqchart.js", "lcmodel.js", "chart.css"))
    feed = AK.read(os.path.join(D, "nqchartfeed.js"))
    html = AK.read(os.path.join(D, "index.html"))
    check("a. perf: the page loads only the small feed (nqchartfeed.js) eagerly; the view (nqchart.js + lcmodel.js) loads on first view (IntersectionObserver) or idle",
          'src="nqchartfeed.js?v=' in html and 'src="nqchart.js' not in html and "IntersectionObserver" in feed and "'./nqchart.js?v=" in feed and "lcmodel.js?v" not in feed)
    check("a. lcmodel.js is pure (no document / window / fetch / storage) and nqchart.js imports it", not re.search(r"\bdocument\.|\bwindow\.|\bfetch\(|localStorage", re.sub(r"//[^\n]*", "", lm))
          and "from './lcmodel.js?v=" in js)
    check("a. text only (no innerHTML / eval), GET only (no POST / socket), the private poll only reads /api/live/state",
          not re.search(r"\.innerHTML|insertAdjacentHTML|\beval\s*\(|new Function", js + lm) and not re.search(r"method:\s*['\"]POST|WebSocket|sendBeacon", js) and "'/api/live/state'" in js)
    check("a. chart.css v3 has the live layer; replay buttons + scrubber + why close >= 44 px; reduced motion stops the flash / pulses",
          "chart.css?v=3" in js and re.search(r"\.lcbtn \{[^}]*min-height: 44px", css) and re.search(r"\.lcscrub \{[^}]*height: 44px", css)
          and re.search(r"\.lcwx \{[^}]*width: 44px; height: 44px", css) and re.search(r"prefers-reduced-motion[^@]*\.lcflash \{ display: none", css))
    cyan = re.findall(r"#(?:67e8f9|22d3ee|06b6d4|0ff|00ffff)\b", js + css, re.I)
    check("a. OLYMPUS NIGHT only: no cyan, no olive / brown", not cyan and not re.search(r"olive|brown|#8b6f47|#6b5d3f", re.sub(r"/\*.*?\*/", "", css, flags=re.S) + re.sub(r"//[^\n]*", "", lm), re.I), cyan)
    check("a. no text under 12 px in the live styles", not [x for x in re.findall(r"(\d+(?:\.\d+)?)px/", css.split("day-livechart")[1]) if float(x) < 12])


NODE = r"""
import(process.argv[2]).then(async (L) => {
  const B = await import(process.argv[3]);
  const fs = require('fs'), post = JSON.parse(fs.readFileSync(process.argv[4], 'utf8')), lite = JSON.parse(fs.readFileSync(process.argv[5], 'utf8')), now = +process.argv[6];
  const bars = B.unpack(post), m = B.model(post, 'all', now);
  const brief = { day: '2026-11-27', early_close: '13:15' }, of = { day: '2026-11-27', levels: [{ label: 'Asia low', px: 21400, side: 'low', read: 'absorbed', t: now - 900 }, { label: 'PDH', px: 21600, side: 'high', read: 'untouched', t: null }] };
  const v = L.live({ lite, priv: null, brief, ofroom: of, bars, candles: m.candles, nowS: now });
  const o = { stage: v.stage, atlas: v.atlasArm && v.atlasArm.side, lv: v.levels.map((x) => [x.label, x.src]), sweeps: v.sweeps.map((w) => w.label), absorb: v.absorb.length,
    ema: v.ema.length, emaLast: v.ema.length ? v.ema[v.ema.length - 1].time === m.candles[m.candles.length - 1].time : false, trades: v.trades.map((t) => [t.name, t.side, t.risk, t.tgt]),
    halt: v.halt && v.halt.text, haltOk: v.haltT === now + 35 * 60, ticker: v.ticker.map((r) => r.hm + r.emoji), next: v.next, };
  o.oldOf = L.live({ lite, brief, ofroom: { ...of, day: '2026-11-26' }, bars, candles: m.candles, nowS: now }).absorb.length;
  o.oldBrief = L.haltT({ day: '2026-11-26', early_close: '13:15' }, now);
  o.empty = L.live({ lite: null, brief: null, ofroom: null, bars: [], candles: [], nowS: now });
  const pb = bars.filter((b) => b[0] < Math.floor(now / 300) * 300).map((b) => ({ time: b[0], open: b[1], high: b[2], low: b[3], close: b[4], volume: 10 }));
  const P = L.privBars({ bars: pb, state: { price: 21500.5 }, last_poll: now - 2 });
  o.priv = [P.bars.length, P.price, P.t];
  o.form = L.forming(P.bars[P.bars.length - 1], [{ t: now - 20, p: 1 }, { t: now + 60, p: 21500 }, { t: now + 85, p: 21510.25 }], now + 90);
  o.formOld = L.forming(P.bars[P.bars.length - 2], [{ t: now, p: 1 }], now);
  o.st = [L.stamp('private', now - 2, now), L.stamp('private', now - 120, now), L.stamp('public', now - 3 * 3600, now), L.stamp('public', null, now)];
  o.emo = ['Asia low swept', 'No trade: news', 'Stopped out', 'Entered LONG', 'thinking'].map(L.emoji);
  console.log(JSON.stringify(o));
});
"""


def test_node():
    post, info = T.fixture(NOW)
    lite, asia = glance(info)
    with tempfile.TemporaryDirectory() as td:
        pp, lp, hp = os.path.join(td, "post.json"), os.path.join(td, "lite.json"), os.path.join(td, "h.cjs")
        json.dump(post, open(pp, "w")); json.dump(lite, open(lp, "w")); open(hp, "w").write(NODE)
        r = subprocess.run(["node", hp, "file://" + os.path.join(D, "lcmodel.js"), "file://" + os.path.join(D, "nqbars.js"), pp, lp, str(NOW)], capture_output=True, text=True, timeout=60)
    o = json.loads(r.stdout.strip().splitlines()[-1]) if r.returncode == 0 and r.stdout.strip() else {}
    check("b. LIT's stage 'Displacement (4/10)' -> label + 4 of 10; ATLAS armed SHORT", o.get("stage") == {"label": "Displacement", "n": 4, "of": 10} and o.get("atlas") == "SHORT", (o.get("stage"), r.stderr[-400:]))
    check("b. the bots' levels (LIT's + the order-flow room's today; ATLAS's EMA row is not a level), deduped",
          ["Asia low", "lit"] in o.get("lv", []) and ["PD high", "lit"] in o.get("lv", []) and not any(x[0].startswith("EMA") for x in o.get("lv", [])) and ["PDH", "of"] in o.get("lv", []), o.get("lv"))
    check("b. the Asia low is swept on today's bars (through by a tick, closed back)", "Asia low" in o.get("sweeps", []), o.get("sweeps"))
    check("b. absorption: today's order-flow room only (yesterday's replay draws nothing)", o.get("absorb") == 1 and o.get("oldOf") == 0, (o.get("absorb"), o.get("oldOf")))
    check("b. ATLAS's EMA 50 on the bars, its last point on the newest candle", o.get("ema", 0) >= 100 and o.get("emaLast"), o.get("ema"))
    check("b. the open trade with $ risk / $ target", o.get("trades") == [["Zlarior", "SHORT", 222, 735]], o.get("trades"))
    check("b. today's halt 13:15 ET from brief.json (35 min after 12:40); yesterday's brief = no halt line", o.get("haltOk") and "13:15" in (o.get("halt") or "") and o.get("oldBrief") is None, o.get("halt"))
    check("b. the ticker: both bots' thoughts, newest first, with emojis", (o.get("ticker") or [])[:3] == ["12:38🧹", "12:35🎯", "12:20🚀"], o.get("ticker"))
    check("b. the next trigger: LIT's armed trigger first", (o.get("next") or {}).get("bot") == "Zlarior" and (o.get("next") or {}).get("side") == "LONG" and "CISD" in (o.get("next") or {}).get("text", ""), o.get("next"))
    e = o.get("empty") or {}
    check("b. nothing from the PC = nothing drawn (no stage, no levels, no ticker, no next)", e.get("stage") is None and e.get("levels") == [] and e.get("ticker") == [] and e.get("next") is None, e)
    check("b. private link: the snapshot's bars + price + last poll; the forming bar opens at the last close, its high / low only from seen prices",
          o.get("priv", [0])[0] >= 170 and o["priv"][1] == 21500.5 and o.get("form") and o["form"][4] == 21510.25 and o["form"][2] >= 21510.25 and o.get("formOld") is None, (o.get("priv"), o.get("form")))
    st = o.get("st") or [{}] * 4
    check("b. the stamp: LIVE from your PC <= 20 s; an older private poll says 'as of'; the public feed says 'As of HH:MM ET (3 hours ago)'; none = waiting",
          st[0].get("live") and st[0]["text"].startswith("LIVE from your PC") and not st[1].get("live") and "as of" in st[1]["text"]
          and st[2]["cls"] == "old" and st[2]["text"].startswith("As of 09:40 ET (3 hours ago)") and st[3]["text"] == "Waiting for the PC", st)
    check("b. emojis: swept 🧹, no trade ⏳ (before news), stop 🛑, entered 🚀, default 🧠", o.get("emo") == ["🧹", "⏳", "🛑", "🚀", "🧠"], o.get("emo"))


SNAP = """() => { const S = window.NQCHART.S, q = (id) => document.getElementById(id), tx = (id) => (q(id) ? q(id).textContent : '');
  const c = q('chartFx'); let ink = 0; if (c) { const g = c.getContext('2d'), d = g.getImageData(0, 0, c.width, c.height).data; for (let i = 3; i < d.length; i += 160) if (d[i] > 0) ink++; }
  return { stamp: tx('lcStamp'), stampCls: q('lcStamp') ? q('lcStamp').className : '', stage: tx('lcStage'), on: document.querySelectorAll('#lcStage .lcsteps i.on').length,
    steps: document.querySelectorAll('#lcStage .lcsteps i').length, atlas: tx('lcAtlas'), halt: tx('lcHalt'), next: tx('lcNext'),
    tick: [...document.querySelectorAll('#lcTicker li')].map((l) => l.textContent), ema: S.emaS ? S.emaS.data().length : 0, emaT: S.emaS ? S.emaS.options().title : '',
    lines: (S.lines || []).map((l) => l.options().title), gl: (S.glLines || []).map((l) => l.options().title), n: S.model ? S.model.candles.length : 0,
    last: S.model && S.model.candles.length ? S.model.candles[S.model.candles.length - 1] : null, drawn: S.series ? S.series.data().length : 0,
    priv: S.privOn, replay: S.replay, scrub: !!q('lcScrub'), why: q('lcWhy') && !q('lcWhy').hidden ? q('lcWhy').textContent : '', ink,
    halts: S.live && S.live.halt ? S.live.halt.text : '' }; }"""


def tap_sweep(p):
    """the screen point of the first bot sweep (to tap it): the view moved onto it (a refresh may move it back: tried 3 times)"""
    pt = None
    for _ in range(3):
        p.evaluate("() => { const S = window.NQCHART.S; S.mode = 'user'; const w = S.live.sweeps[0], i = S.model.candles.findIndex((c) => c.time === w.time); S.chart.timeScale().setVisibleLogicalRange({ from: i - 30, to: i + 30 }); document.getElementById('chartBox').scrollIntoView({block:'center', behavior:'instant'}); }")
        p.wait_for_timeout(400)
        pt = p.evaluate("""() => { const S = window.NQCHART.S, w = (S.live.sweeps || [])[0]; if (!w) return null;
          const x = S.chart.timeScale().timeToCoordinate(w.time), y = S.series.priceToCoordinate(w.price), r = document.getElementById('chart').getBoundingClientRect();
          return x == null || y == null ? null : { x: r.left + x, y: r.top + y, ok: x >= 0 && x <= r.width }; }""")
        if pt and pt["ok"]:
            break
    return pt


def test_page(shots=False):
    try:
        import playwright  # noqa: F401
    except ImportError:
        check("c. page tests skipped: no Playwright", True)
        return
    from tests import test_nq_page as NP
    post, info = T.fixture(NOW)
    old, oinfo = T.fixture(NOW, age_s=3 * 3600)
    lite, asia = glance(info)
    real = NP.time.time
    NP.time.time = lambda: float(NOW)
    try:
        home = NP.home_json(180)
    finally:
        NP.time.time = real
    brief = json.dumps({"v": 1, "day": "2026-11-27", "early_close": "13:15", "headline": "Test day"})
    ofroom = json.dumps({"v": 1, "day": "2026-11-27", "levels": [{"label": "Asia low", "px": asia, "side": "low", "read": "absorbed", "t": NOW - 1500}]})
    # the footprint strip (day-ofroom2's ofstrip.js): a stub module here, so this suite checks only the hook (today's of_strip.json -> mount -> tap = crosshair)
    strip = json.dumps({"day": "2026-11-27", "tick": 0.25, "bucket": 2.0, "bars": [{"t": "12:30", "o": 1, "h": 2, "l": 0, "c": 1, "v": 10, "d": 2, "big": 0, "cells": [], "abs": []}]})
    stub = "window.OFSTRIP = { mount: (el, d, o) => { window.__ofs = { n: d.bars.length, o }; el.textContent = 'footprint'; return { update() {}, select(i) { window.__ofsSel = i; }, destroy() {} }; } };"
    srv, origin = AK.serve({"/status_feed.json": T.FEED, "/home.json": home, "/nq/brief.json": brief, "/nq/of_room.json": ofroom, "/nq/of_strip.json": strip})
    bars_url, core_url = f"/{T.TOPIC}-bars/json", f"/{T.TOPIC}/json"
    fixed = lambda p: p.clock.set_fixed_time(dt.datetime.fromtimestamp(NOW, dt.timezone.utc))  # noqa: E731
    try:
        with AK.browser() as br:
            for w, h in ((390, 844), (1440, 900)):
                ctx, p, errs, seen, off = AK.page(br, origin, w=w, h=h, mock={bars_url: T.ndjson(post), core_url: core_body(lite, NOW - 30)})
                fixed(p)
                p.route("**/nq/ofstrip.js*", lambda r: r.fulfill(status=200, content_type="text/javascript", body=stub))
                p.route("**/nq/ofstrip.css*", lambda r: r.fulfill(status=200, content_type="text/css", body="/* stub */"))
                T.open_chart(p, origin)
                p.wait_for_function("document.getElementById('lcStage') && window.NQCHART.S.live && window.NQCHART.S.live.halt", timeout=20000)
                p.evaluate("document.getElementById('chartCard').scrollIntoView({block:'start'})")
                p.wait_for_timeout(500)
                s = p.evaluate(SNAP)
                check(f"c. {w}px: the stage strip: Zlarior Displacement 4/10 (10 steps, 4 lit); ATLAS armed SHORT chip; the halt chip 13:15",
                      "Displacement 4/10" in s["stage"] and s["steps"] == 10 and s["on"] == 4 and s["atlas"] == "ATLAS armed SHORT" and "13:15" in s["halt"], s)
                check(f"c. {w}px: the honest stamp from the public feed ('As of 12:39 ET (just now) · the public feed')", s["stamp"].startswith("As of 12:39 ET") and "public feed" in s["stamp"], s["stamp"])
                check(f"c. {w}px: the ticker newest first with emojis + the next trigger line", len(s["tick"]) == 5 and s["tick"][0].startswith("🧹12:38") and "Next trade if (Zlarior LONG)" in s["next"], (s["tick"][:2], s["next"]))
                check(f"c. {w}px: ATLAS's EMA 50 drawn, rose for its armed SHORT", s["ema"] > 100 and "SHORT" in s["emaT"], (s["ema"], s["emaT"]))
                check(f"c. {w}px: the open trade's stop / target lines carry $ (-$222 / +$735)", any("-$222" in t for t in s["lines"]) and any("+$735" in t for t in s["lines"]), s["lines"])
                pt = tap_sweep(p)
                if pt:
                    p.touchscreen.tap(pt["x"], pt["y"])
                    p.wait_for_timeout(300)
                s2 = p.evaluate(SNAP)
                check(f"c. {w}px: a tap on the swept Asia low opens why (plain words) with a 44 px close", pt and "Asia low was swept" in s2["why"], (pt, s2["why"][:120]))
                if pt and s2["why"]:
                    b = p.locator("#lcWhy .lcwx").bounding_box()
                    check(f"c. {w}px: ... its close is >= 44 px and closes it", b and b["height"] >= 44)
                    if w == 390:
                        shot(p, "livechart_390", shots)
                    p.locator("#lcWhy .lcwx").tap()
                if w == 1440:
                    shot(p, "livechart_1440", shots)
                if w == 390:
                    p.wait_for_function("window.__ofs", timeout=15000)
                    leg = p.evaluate("() => { window.__ofs.o.onSelect({ t: '12:30' }, 0); return [window.__ofs.n, document.getElementById('lcStrip').textContent, document.getElementById('chartLeg').textContent]; }")
                    check("c. 390px: today's of_strip.json loads the footprint strip (lazily) under the ticker; a tap on its 12:30 bar moves the chart's readout to 12:30",
                          leg[0] == 1 and leg[1] == "footprint" and leg[2].startswith("12:30"), leg)
                    sel = p.evaluate("""() => { window.__ofsSel = null; const S = window.NQCHART.S, r = document.getElementById('lcScrub');
                      const i = S.model.candles.findIndex((c) => new Date(c.time * 1000).toISOString().slice(11, 16) === '12:30'); r.value = String(i); r.dispatchEvent(new Event('input'));
                      const out = window.__ofsSel; document.getElementById('lcLive').click(); return out; }""")
                    check("c. 390px: the replay scrubber on the 12:30 candle selects the strip's 12:30 footprint bar (synced by time)", sel == 0, sel)
                n0 = s["drawn"]
                p.locator("#lcScrub").evaluate("(r) => { r.value = String(+r.min + 10); r.dispatchEvent(new Event('input')); }")
                p.wait_for_timeout(300)
                s3 = p.evaluate(SNAP)
                check(f"c. {w}px: replay: the scrubber draws the day up to the chosen bar; 'Live' brings it all back", s3["replay"] is not None and s3["drawn"] < n0, (s3["drawn"], n0))
                p.locator("#lcLive").click()
                p.wait_for_timeout(300)
                s4 = p.evaluate(SNAP)
                check(f"c. {w}px: ... back to live", s4["replay"] is None and s4["drawn"] == n0, (s4["drawn"], n0))
                check(f"c. {w}px: no sideways scroll, taps >= 44 px, no console error", AK.no_sideways(p) and not AK.taps(p) and not errs, (AK.taps(p)[:3], errs[:3]))
                ctx.close()
            # a stale public feed: bars 3 hours old, the glance post 3 hours old -> the stamp says so in rose, no LIVE anywhere
            lite_old, _ = glance(oinfo, NOW - 3 * 3600)
            ctx, p, errs, seen, off = AK.page(br, origin, mock={bars_url: T.ndjson(old), core_url: core_body(lite_old, NOW - 3 * 3600)})
            fixed(p)
            T.open_chart(p, origin)
            p.wait_for_function("document.getElementById('lcStamp')", timeout=20000)
            s = p.evaluate(SNAP)
            check("c. stale feed: 'As of 09:39 ET (3 hours ago) · the public feed' in rose, never LIVE", re.match(r"As of 09:(39|40) ET \(3 hours ago\)", s["stamp"]) and "old" in s["stampCls"] and "LIVE" not in s["stamp"], s["stamp"])
            check("c. ... no sideways scroll, no console error", AK.no_sideways(p) and not errs, errs[:3])
            ctx.close()
            # the private link: the PC's own snapshot (GET /api/live/state) every 3 s -> LIVE from your PC + the forming bar; a new price glides in
            pb = [{"time": b[0], "open": b[1], "high": b[2], "low": b[3], "close": b[4], "volume": 10} for b in info["bars"][:-1]]
            snap = json.dumps({"running": True, "state": {"price": pb[-1]["close"] + 4.25}, "last_poll": NOW - 2, "bars": pb})
            ctx, p, errs, seen, off = AK.page(br, origin, mock={bars_url: T.ndjson(post), core_url: core_body(lite, NOW - 30), "/api/live/state": snap})
            fixed(p)
            T.open_chart(p, origin, "?priv=1")
            p.wait_for_function("window.NQCHART.S.privOn && document.getElementById('lcStamp') && /LIVE from your PC/.test(document.getElementById('lcStamp').textContent)", timeout=20000)
            p.evaluate("document.getElementById('chartCard').scrollIntoView({block:'start'})")
            p.wait_for_timeout(400)
            s = p.evaluate(SNAP)
            check("c. private link: 'LIVE from your PC', the PC's 179 bars + the forming bar (opens at the last close, closes at the PC's price)",
                  s["priv"] and s["stamp"].startswith("LIVE from your PC") and "live" in s["stampCls"] and s["n"] == 180 and abs(s["last"]["close"] - (pb[-1]["close"] + 4.25)) < 1e-6
                  and abs(s["last"]["open"] - pb[-1]["close"]) < 1e-6, (s["stamp"], s["n"], s["last"]))
            p.evaluate(f"() => {{ const S = window.NQCHART.S; S.privSeen.push({{ t: {NOW}, p: {pb[-1]['close'] + 9.5} }}); window.NQCHART.liveTick(); }}")
            p.wait_for_timeout(800)
            s2 = p.evaluate(SNAP)
            check("c. private link: a new price glides the forming bar's close to it (same bar count, the chart's last bar updated)",
                  s2["n"] == 180 and abs(s2["last"]["close"] - (pb[-1]["close"] + 9.5)) < 1e-6 and s2["drawn"] == 180, (s2["n"], s2["last"]))
            check("c. private link: the reads are GET /api/live/state (mocked here), no console error", any("/api/live/state" in u for u in p.mocked) and not errs, errs[:3])
            shot(p, "livechart_private_390", shots)
            ctx.close()
    finally:
        srv.shutdown()


def shot(p, name, on):
    if on:
        os.makedirs(SHOTS, exist_ok=True)
        p.screenshot(path=os.path.join(SHOTS, name + ".png"), full_page=False)


if __name__ == "__main__":
    test_static()
    test_node()
    if "--static" not in sys.argv:
        test_page(shots="--shots" in sys.argv)
    AK.finish()
