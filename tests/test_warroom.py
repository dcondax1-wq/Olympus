"""THE WAR ROOM (day-warroom 2026-11-24; owner ~08:30 ET: "We used to have steps for our entries, like what the brain was thinking. I want
to see that for each, everything combined ... I want to know exactly what we are doing at all times"): tools/web_public/warroom/.
Four scenarios built from the PC's real post of 2026-11-20 (tests/fixtures/truth/pc_post.json, its glance re-dated) and the real chart
packer (tools/pc_report.pack_bars), on Tue 2026-11-24 09:52 ET: idle, setup forming, in a trade, stale (the PC silent for 2 hours).
  a. static   the page, its modules, text only through textContent, no POST / beacon / eval, OLYMPUS NIGHT only, the Home Screen kit,
              linked FIRST on Home (gate), NQ, Pillars and the Strategy Brain; NQ still under its 300 KB budget; the War Room's own budget
  b. node     warcore.build: LIT's 10 stages (now / next / done), ATLAS's 3 lobes with their own steps, BLITZ's 6 (hidden: off, never live
              data), ORDER FLOW's 5; what the next step waits for WITH the numbers (the sweep size from ATR, the level, the distance);
              the meter and the windows' countdowns; the narration newest first; the chart's levels; the open trade's live $ / R; the
              milestones; staleness; account ids never in the model
  c. Chromium 390 x 844: the four scenarios (shots), ladders + meters + countdowns ticking, the story typed, the chart drawn, the trade
              card, the stale banner, the alert switch (off by default), reduced motion, taps >= 44 px, no sideways scroll, no error
    python -X utf8 -m tests.test_warroom [--static] [--shots <dir>]
"""
from __future__ import annotations

import copy
import datetime as dt
import json
import math
import os
import random
import re
import shutil
import subprocess
import sys
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
from tests import agora_kit as AK  # noqa: E402
import pc_report as PR  # noqa: E402

check = AK.check
WEB = AK.WEB
WR = os.path.join(WEB, "warroom")
PC = json.load(open(os.path.join(ROOT, "tests", "fixtures", "truth", "pc_post.json"), encoding="utf-8"))
NOW = int(dt.datetime(2026, 11, 24, 9, 52, tzinfo=ZoneInfo("America/New_York")).timestamp())
TOPIC = "olympus-nq-status-00000000c0ffee00"
FEED = json.dumps({"ntfy": "https://ntfy.sh", "topic": TOPIC, "note": "test"})


def rd(*p):
    with open(os.path.join(*p), encoding="utf-8") as fh:
        return fh.read()


# ------------------------------------------------------------------------------------------------ the scenarios
def et(hm):
    h, m = map(int, hm.split(":"))
    return int(dt.datetime(2026, 11, 24, h, m, tzinfo=ZoneInfo("America/New_York")).timestamp())


def bars_post(kind, now):
    """60 five-minute bars to now: a drift around 26,230, a sweep of the London low 26,190.25 at 09:40 and a strong candle back up (forming /
    trade); in a trade, the 50K + 25K #2 are LONG from 09:46 with the stop 1 tick under the sweep extreme."""
    end = now // 300 * 300
    rnd, p, bars = random.Random(7), 26236.0, []
    for i in range(60):
        t = end - (59 - i) * 300
        o = p
        drift = -14.0 if et("09:30") <= t < et("09:40") and kind != "idle" else 16.0 if et("09:40") <= t < et("09:50") and kind != "idle" else 0.0
        c = round((o + drift + 0.3 * (26240.0 - o) * (drift == 0.0) + rnd.gauss(0, 14.0)) * 4) / 4
        hi, lo = max(o, c) + rnd.randint(8, 60) * 0.25, min(o, c) - rnd.randint(8, 60) * 0.25
        if kind != "idle" and t == et("09:40"):
            lo = 26178.25                                       # the sweep extreme: 12 pts through 26,190.25
        bars.append((t, o, hi, lo, c))
        p = c
    acc = {"z50k": ["Zlarior 50K", "LIT", "LIVE"], "z25k2": ["Zlarior 25K #2", "LIT"], "atlas25f": ["ATLAS funded 25K", "ATLAS", "SIM"]}
    opens, closed = [], []
    if kind == "trade":
        e = bars[-2][4]
        opens = [{"k": "z50k", "s": 1, "q": 4, "t": et("09:46"), "e": e, "sl": 26178.0, "tp": e + 120.0},
                 {"k": "z25k2", "s": 1, "q": 1, "t": et("09:46"), "e": e, "sl": 26178.0, "tp": e + 120.0}]
    closed = [{"k": "atlas25f", "s": -1, "q": 2, "t": et("03:45"), "e": 26380.75, "xt": et("05:10"), "x": 26122.75, "usd": 1028.2, "r": 6.6, "why": "TARGET"}]
    post = PR.pack_bars(bars, opens, closed, acc, now=now, data_t=now - 30, sym="MNQ 12-26", forming=True, day=PR._cme_day(now), trades_t=now - 60)
    return post, bars


def core_post(kind, now):
    """the real post re-dated to now (stale: 2 hours old), with each scenario's glance"""
    P = copy.deepcopy(PC)
    t = now - (2 * 3600 if kind == "stale" else 240)
    P["t"] = t
    P["reporter"]["t"] = t
    P["pc"]["glance"]["t"] = t - 60
    P["price"] = 26236.0
    lit, atl = P["pc"]["glance"]["bots"][0], P["pc"]["glance"]["bots"][1]
    lit["lv"] = [["London low", 26190.25, 46.0], ["Equal highs", 26291.5, 55.0], ["PDH", 26370.75, 134.0], ["Asia low", 26120.0, 116.0]]
    lit["log"] = [["09:50", "Displacement up: body 0.9 ATR back above the London low"], ["09:40", "London low 26,190.25 swept by 12.0 pts (1.2 ATR)"],
                  ["09:12", "Mapping: 11 levels, nearest London low 26,190.25"]]
    if kind == "idle":
        lit.update(stage="Levels (1/10)", wait="Watching 11 levels; nothing swept yet today.", arm=[], why="No setup yet today. Watching 11 levels.")
        lit["log"] = lit["log"][2:]
        atl.update(wait="EMA: watching for a pullback; MACD: watching; S/R: watching", why="EMA: no setup yet · MACD: no sweep yet · S/R: no sweep yet", arm=[])
        atl["log"] = [["09:31", "S/R: window open, levels pdh 26,370.75 / pdl 26,120.00"]]
    elif kind in ("forming", "stale"):
        lit.update(stage="5m CISD (5/10)", wait="5m CISD closed through 26,232.50 at 09:50: checking the setup (stop 1 tick under 26,178.25).",
                   arm=[{"side": "LONG", "text": "forming", "trig": "5m CISD already closed through 26,232.50: see the setup card."}],
                   why="09:50 LONG setup forming after the London low sweep.", chk=[6, 9])
    else:  # trade
        lit.update(stage="In trade (9/10)", wait="Long 4 micros from 09:46: stop 26,178.00, target the VIX band.", arm=[],
                   why="09:46 LONG setup traded.", pos={"side": "LONG", "qty": 4, "entry": 26240.0, "stop": 26178.0, "target": 26360.0})
    P["glog"] = {"lit": lit["log"], "atlas": atl["log"]}
    return P


def ndjson(*posts):
    return "".join(json.dumps({"event": "message", "time": int(p.get("rt") or p.get("t") or 0), "message": json.dumps(p, separators=(",", ":"))}) + "\n" for p in posts)


# ------------------------------------------------------------------------------------------------ a. static
def test_static():
    html, js, core, css = rd(WR, "index.html"), rd(WR, "warroom.js"), rd(WR, "warcore.js"), rd(WR, "warroom.css")
    check("a. the page: its module and stylesheet, the ladders, the overview, the trades, the chart canvas, the story, the alert switch, the sources",
          'src="warroom.js?v=' in html and 'href="warroom.css?v=' in html and all(f'id="{i}"' in html for i in ("ladders", "over", "trades", "chart", "feed", "pushBtn", "stale", "headline", "srcs")))
    check("a. text only through textContent: no innerHTML / eval / document.write; read only: no POST / beacon / WebSocket; storage only the phone's own conveniences",
          not re.search(r"innerHTML|outerHTML|insertAdjacentHTML|document\.write|\beval\s*\(|sendBeacon|WebSocket|method:\s*['\"]POST", js + core)
          and set(re.findall(r"'(oly\.wr\.[a-z]+)'", js)) == {"oly.wr.memo", "oly.wr.push", "oly.wr.seen"} and "localStorage" not in core)
    check("a. the model is pure (no DOM, no fetch, no storage) and the alerts are OFF by default (store.get('oly.wr.push', false))",
          not re.search(r"document\.|window\.|fetch\(|localStorage", core) and "store.get('oly.wr.push', false) === true" in js)
    check("a. no Arm / Start / Stop / Flatten / Close control: the War Room only watches", not re.search(r">\s*(Arm|Start|Stop|Flatten|Close)\b", html) and "placeOrder" not in js)
    cols = {c.lower() for c in re.findall(r"#[0-9a-fA-F]{6}\b", css + js + core)}
    allowed = {"#000000", "#16131e", "#1d1828", "#3e255e", "#4d2e76", "#9d59ee", "#f1c14b", "#77db89", "#ff6b8a", "#f3eefc", "#a99cc2", "#241d33", "#0c0a12",
               "#1a1300", "#04140a", "#3a1020", "#ffd3dc", "#ffe7a8", "#e9dcb4", "#f6e3ad", "#0b0812", "#6fb7ff"}
    check("a. OLYMPUS NIGHT only (black, #16131e cards, violet outlines, glow #9d59ee, gold, mint; no brown / olive)", cols <= allowed, sorted(cols - allowed))
    check("a. glass panels with a gold hairline; motion is transform / opacity; html.wr-low and reduced motion turn every loop off",
          "backdrop-filter" in css and "rgba(241,193,75" in css and "html.wr-low *" in css and "prefers-reduced-motion: reduce" in css)
    mf = json.loads(rd(WR, "manifest.webmanifest"))
    check("a. the Home Screen kit: capable, status bar, title 'War Room', theme-color, viewport-fit, manifest (standalone, 192 / 512 / maskable)",
          'name="apple-mobile-web-app-capable" content="yes"' in html and 'name="mobile-web-app-capable" content="yes"' in html and 'content="War Room"' in html
          and "viewport-fit=cover" in html and mf["display"] == "standalone" and mf["start_url"] == "./" and {i["purpose"] for i in mf["icons"]} >= {"any", "maskable"})
    gate, nq, pil, mind = rd(WEB, "gate", "index.html"), rd(WEB, "nq", "index.html"), rd(WEB, "pillars", "index.html"), rd(WEB, "cities", "mind", "index.html")
    first = lambda s, anchor: s.find('warroom/') != -1 and s.find('warroom/') < s.find(anchor)  # noqa: E731
    check("a. linked FIRST: Home (above the pillars band), NQ (the first header button), the Pillars page and the Strategy Brain (in their top bars)",
          first(gate, 'id="pillarsHero"') and first(nq, 'href="../pillars/"') and first(pil, 'id="said"') and first(mind, '<h1>Strategy Brain'),
          [first(gate, 'id="pillarsHero"'), first(nq, 'href="../pillars/"'), first(pil, 'id="said"'), first(mind, '<h1>Strategy Brain')])
    import phone_budget as PB
    nqr, wr = PB.static_row(WEB, "nq"), PB.static_row(WEB, "warroom")
    check("a. perf budget: NQ still <= 300 KB blocking; the War Room <= 60 KB blocking, <= 240 KB eager JS, no three.js",
          nqr["block_kb"] <= 300 and wr["block_kb"] <= 60 and wr["eager_js_kb"] <= 240 and not wr["three"], (nqr["block_kb"], wr))


# ------------------------------------------------------------------------------------------------ b. node
HARNESS = r"""
const path = require('path'), fs = require('fs'), W = process.argv[2], X = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
(async () => {
  const C = await import(path.join(W, 'warroom', 'warcore.js'));
  const base = { brief: require(path.join(W, 'nq', 'brief.json')), pillars: require(path.join(W, 'pillars', 'pillars-data.json')) };
  const out = {};
  for (const k of Object.keys(X.sc)) {
    const M = C.build({ ...base, lite: X.sc[k].core, bars: X.sc[k].bars }, X.now, []);
    out[k] = { head: M.headline, pc: M.pc, price: M.price, atr: M.atr, next: M.next, ms: M.milestones, pos: M.positions,
      bots: M.bots.map((b) => ({ id: b.id, pill: b.pill, step: b.stepText, hidden: b.hidden, now: b.now, next: b.next, meter: b.meter, win: b.window,
        groups: b.groups.map((g) => ({ id: g.id, name: g.name, state: g.state || '', needs: g.needs || '', steps: g.steps.map((s) => s.state) })) })),
      chart: { state: M.chart.state, n: M.chart.candles.length, kinds: M.chart.levels.map((l) => l.who + ':' + l.kind), off: M.chart.off.length },
      feed: M.feed.map((f) => [f.t, f.hm, f.who, f.kind, f.text]), json: JSON.stringify(M) };
  }
  const prev = C.build({ ...base, lite: X.sc.idle.core, bars: X.sc.idle.bars }, X.now, []), nxt = C.build({ ...base, lite: X.sc.forming.core, bars: X.sc.forming.bars }, X.now, []);
  out.changes = C.changes(prev, nxt, X.now);
  out.none = C.build(base, X.now, []);
  out.weekend = C.windowState([['02:00', '15:30']], X.sat, 'LIT');
  out.clock = [C.clock(3725), C.clock(59), C.dur(3900)];
  out.atr = C.atr14([[0,1,2,0,1],[1,1,3,0,2],[2,2,4,1,3],[3,3,5,2,4],[4,4,6,3,5],[5,5,7,4,6],[6,6,8,5,7],[7,7,9,6,8],[8,8,10,7,9],[9,9,11,8,10],[10,10,12,9,11],[11,11,13,10,12],[12,12,14,11,13],[13,13,15,12,14],[14,14,16,13,15]], false);
  out.prices = C.pricesIn('Enters if price comes back to 26,244.50 before 10:05 ET · stop 26,339.50 · target 26,100.00 · 5m CISD already closed through 26,117.50');
  console.log(JSON.stringify(out));
})().catch((e) => { console.error(e && e.stack || e); process.exit(1); });
"""


def scenarios(now=NOW):
    out = {}
    for k in ("idle", "forming", "trade", "stale"):
        b, raw = bars_post(k, now)
        out[k] = {"core": core_post(k, now), "bars": b, "raw": raw}
    return out


def test_node():
    exe = shutil.which("node")
    if not exe:
        check("b. node tests skipped: no node", True)
        return
    import tempfile
    sc = scenarios()
    tmp = tempfile.mkdtemp(prefix="wr-")
    try:
        f = os.path.join(tmp, "x.json")
        sat = int(dt.datetime(2026, 11, 28, 10, 0, tzinfo=ZoneInfo("America/New_York")).timestamp())
        json.dump({"now": NOW, "sat": sat, "sc": {k: {"core": v["core"], "bars": v["bars"]} for k, v in sc.items()}}, open(f, "w"))
        hp = os.path.join(tmp, "h.cjs")
        open(hp, "w").write(HARNESS)
        r = subprocess.run([exe, hp, WEB, f], capture_output=True, text=True, timeout=120)
        if r.returncode:
            check("b. the model runs in node", False, r.stderr[-800:])
            return
        o = json.loads(r.stdout)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    B = {k: {b["id"]: b for b in o[k]["bots"]} for k in ("idle", "forming", "trade", "stale")}
    fl = B["forming"]["lit"]
    check("b. LIT: its 10 engine stages; at 5m CISD (5/10) steps 1-4 passed, 5 now, 6 next, the rest waiting; 'now' = the PC's own words",
          fl["groups"][0]["steps"] == ["done"] * 4 + ["now", "next"] + ["wait"] * 4 and fl["step"] == "5/10" and fl["now"]["text"].startswith("5m CISD closed through 26,232.50")
          and fl["next"]["label"] == "Limit armed" and "6 of 9 checks passed" in fl["next"]["text"], (fl["groups"][0]["steps"], fl["next"]))
    il = B["idle"]["lit"]
    atr = o["idle"]["atr"]
    check("b. idle LIT: the next step says exactly what it waits for, with the numbers: a sweep of >= 0.5 ATR (from the last 14 5m bars) below the London low at 26,190.25 / above the Equal highs, and how far",
          atr and il["next"]["label"] == "Sweep" and f"a sweep of ≥ {math.floor(atr * 5 + 0.5) / 10:g} pts below the London low at 26,190.25" in il["next"]["text"]
          and "Equal highs at 26,291.50" in il["next"]["text"] and "from the last 14 5m bars" in il["next"]["text"] and "pts away" in il["next"]["text"], (atr, il["next"]))
    fa = B["forming"]["atlas"]
    check("b. ATLAS: three lobes, each its own 5 steps and hours (EMA done; MACD armed with its trigger 'until 11:00 ET'; S/R in its window, waiting for a sweep)",
          [g["name"] for g in fa["groups"]] == ["EMA", "MACD", "S/R"] and all(len(g["steps"]) == 5 for g in fa["groups"]) and fa["groups"][0]["steps"] == ["done"] * 5
          and fa["groups"][1]["state"] == "armed" and "until 11:00 ET" in fa["groups"][1]["needs"] and fa["groups"][2]["needs"].startswith("Needs a signal"), [(g["name"], g["state"], g["needs"]) for g in fa["groups"]])
    bl, of = B["forming"]["blitz"], B["forming"]["of"]
    check("b. BLITZ: its 6 steps, all off, HIDDEN · PAPER (never live data); ORDER FLOW: its 5 steps, recording first, 0 of 60 tick days",
          len(bl["groups"][0]["steps"]) == 6 and set(bl["groups"][0]["steps"]) == {"off"} and bl["pill"] == "HIDDEN · PAPER" and bl["hidden"]
          and len(of["groups"][0]["steps"]) == 5 and of["groups"][0]["steps"][0] == "now" and of["step"] == "0/60 days", (bl["pill"], of["step"], of["groups"][0]["steps"]))
    check("b. how close to a trade: idle LIT 'Far' 6%, forming LIT 'Close' 64%, in a trade 'In a trade' 100%; the LIT window open until 15:30 with the time left",
          (il["meter"]["word"], il["meter"]["pct"]) == ("Far", 6) and (fl["meter"]["word"], fl["meter"]["pct"]) == ("Close", 64)
          and (B["trade"]["lit"]["meter"]["word"], B["trade"]["lit"]["meter"]["pct"]) == ("In a trade", 100) and fl["win"]["state"] == "open" and fl["win"]["to"] == "15:30"
          and 0.35 < fl["meter"]["time"] < 0.5, (il["meter"], fl["meter"], fl["win"]))
    nx = o["forming"]["next"]
    check("b. the next window and its countdown target: ATLAS EMA 03:00 tomorrow (MACD / S/R / LIT already open); a Saturday says Monday",
          nx and nx["who"] == "ATLAS EMA" and nx["at"] == "03:00" and nx["s"] > NOW and o["weekend"]["state"] == "weekend" and "Monday" in o["weekend"]["text"], (nx, o["weekend"]))
    fd = o["forming"]["feed"]
    check("b. the story newest first, in plain words with times: the PC's thoughts (09:50 displacement, 09:40 sweep), the windows that opened, the ATLAS trade's exit",
          [r[0] for r in fd] == sorted([r[0] for r in fd], reverse=True) and any(r[1] == "09:50" and "Displacement up" in r[4] for r in fd)
          and any(r[1] == "09:40" and "swept by 12.0 pts" in r[4] for r in fd) and any("ATLAS S/R window opened" in r[4] for r in fd)
          and any(r[3] == "exit" and "ATLAS out on ATLAS funded 25K" in r[4] and "+$1,028" in r[4] for r in fd), [r[1:] for r in fd[:8]])
    ch = o["forming"]["chart"]
    check("b. the chart: the last 24 bars (2 hours) with LIT's levels (London low, Equal highs) and the CISD line drawn; the far ones listed off the chart",
          ch["n"] == 24 and "lit:level" in ch["kinds"] and "lit:cisd" in ch["kinds"] and ch["off"] >= 1, ch)
    tp = o["trade"]["pos"]
    p0 = tp[0] if tp else {}
    check("b. in a trade: one card per account (Zlarior 50K LONG 4, 25K #2 LONG 1) with live $ = pts x $2 x micros, R from the stop, time in trade, what closes it",
          len(tp) == 2 and p0["acct"] == "Zlarior 50K" and p0["side"] == "LONG" and p0["q"] == 4 and abs(p0["usd"] - p0["pts"] * 2 * 4) < 0.01
          and abs(p0["r"] - p0["pts"] / abs(p0["entry"] - p0["stop"])) < 1e-6 and p0["since"] == NOW - et("09:46") and "stop at 26,178.00" in p0["close"] and "15:55" in p0["close"], p0)
    check("b. the headline: in a trade first; forming = the closest bot and what it needs; idle = quiet + the next window",
          o["trade"]["head"].startswith("In a trade: LIT LONG 4 micros") and o["forming"]["head"].startswith("ATLAS is imminent") and o["idle"]["head"].startswith("Quiet"),
          (o["trade"]["head"], o["forming"]["head"], o["idle"]["head"]))
    st = o["stale"]["pc"]
    check("b. honest staleness: fresh 'PC 4 min ago'; stale (2 h) = level bad + the banner 'Stale: your PC last spoke 2 h 0 min ago'; no post = 'no word yet', every bot 'No data'",
          o["forming"]["pc"]["text"] == "PC 4 min ago" and o["forming"]["pc"]["level"] == "ok" and st["level"] == "bad" and st["banner"].startswith("Stale: your PC last spoke 2 h 0 min ago")
          and o["none"]["pc"]["level"] == "none" and [b["meter"]["word"] for b in o["none"]["bots"][:2]] == ["No data", "No data"], (o["forming"]["pc"], st))
    ms = [m["key"] for m in o["forming"]["ms"]]
    sb = {b["id"]: b for b in o["stale"]["bots"]}
    check("b. stale: the words say where the bots WERE ('Was close'), the headline starts 'As of 07:52 ET (the PC is silent)'",
          sb["lit"]["meter"]["word"] == "Was close" and o["stale"]["head"].startswith("As of 07:52 ET (the PC is silent): "), (sb["lit"]["meter"], o["stale"]["head"]))
    check("b. milestones (the optional alerts): LIT 5/10, ATLAS MACD armed; in a trade: the position", "lit:5" in ms and "atlas:macd:armed" in ms
          and any(m["key"].startswith("pos:lit:Zlarior 50K") for m in o["trade"]["ms"]), (ms, o["trade"]["ms"]))
    check("b. no made-up lines: a finished lobe's old plan is never drawn (EMA is done), the first post is never a 'change', the next window names its day",
          "atlas:target" not in o["forming"]["chart"]["kinds"] and not any("unknown" in r[4] for r in fd) and o["forming"]["next"]["day"] == "tomorrow"
          and "tomorrow 03:00" in o["idle"]["head"], (o["forming"]["chart"]["kinds"], o["idle"]["head"]))
    check("b. what changed between two posts, in plain words: 'LIT moved to 5/10 (5m CISD)' and the MACD lobe's change",
          any(c["text"].startswith("LIT moved to 5/10 (5m CISD)") for c in o["changes"]), o["changes"])
    js = " ".join(o[k]["json"] for k in ("idle", "forming", "trade", "stale"))
    check("b. account ids never in the model: the glance's 'mode' (it holds part of ATLAS's account id) is never copied", "6018" not in js and "MFFUSF" not in js)
    check("b. helpers: clock 1:02:05 / 0:59, 1 h 5 min; ATR(14) of complete bars; the PC's prices read from its own words (limit, stop, target, the CISD line)",
          o["clock"] == ["1:02:05", "0:59", "1 h 5 min"] and o["atr"] == 3 and o["prices"] == {"limit": 26244.5, "stop": 26339.5, "target": 26100, "cisd": 26117.5}, (o["clock"], o["atr"], o["prices"]))


# ------------------------------------------------------------------------------------------------ c. browser
SNAP = """() => { const q = (s) => [...document.querySelectorAll(s)];
  return { ladders: q('.lad').map((e) => e.id), litSteps: q('#lad-lit .steps .st').map((e) => e.className.replace('st ', '')),
    lobes: q('#lad-atlas .lobe').length, lobeSteps: q('#lad-atlas .lobe .st').length, blitz: q('#lad-blitz .st').map((e) => e.className.replace('st ', '')),
    ofSteps: q('#lad-of .st').length, nowTx: (document.querySelector('#lad-lit .st.now .tx') || {}).textContent || '', nextTx: (document.querySelector('#lad-lit .st.next .tx') || {}).textContent || '',
    over: q('.ot').map((e) => [e.querySelector('b').textContent, e.querySelector('.ring span').textContent, e.querySelector('small').textContent]),
    head: document.getElementById('headline').textContent, pc: document.getElementById('pcText').textContent, level: document.getElementById('pcPill').dataset.level,
    stale: !document.getElementById('stale').hidden, staleText: document.getElementById('stale').textContent, trades: q('.trd').length,
    trade: (document.querySelector('.trd') || {}).textContent || '', feed: q('#feed li').map((e) => e.textContent), cds: q('.cd').map((e) => e.textContent),
    chartEmpty: !document.getElementById('chartEmpty').hidden, legend: document.getElementById('chartLegend').textContent,
    inked: (() => { const c = document.getElementById('chart'), x = c.getContext('2d').getImageData(0, 0, c.width, c.height).data; let n = 0; for (let i = 3; i < x.length; i += 16) if (x[i]) n++; return n; })(),
    fx: !!document.getElementById('olyNightFx'), low: window.WARROOM.low, push: document.getElementById('pushBtn').getAttribute('aria-pressed'), body: document.body.innerText }; }"""


def test_page(shots=None):
    try:
        import playwright  # noqa: F401
    except ImportError:
        check("c. page tests skipped: no Playwright", True)
        return
    sc = scenarios()
    srv, origin = AK.serve({"/status_feed.json": FEED})
    out = {}
    try:
        with AK.browser() as br:
            for k in ("idle", "forming", "trade", "stale"):
                ctx, p, errs, seen, off = AK.page(br, origin, mock={f"/{TOPIC}-bars/json": ndjson(sc[k]["bars"]), f"/{TOPIC}/json": ndjson(sc[k]["core"])},
                                                  storage={"olympus.theme": "night"})
                p.clock.set_fixed_time(dt.datetime.fromtimestamp(NOW, dt.timezone.utc))
                p.goto(f"{origin}/warroom/?fx=3d")
                p.wait_for_function("window.WARROOM && window.WARROOM.ready()", timeout=60000)
                p.wait_for_timeout(2600)                              # the typed line ends, the bars ease in
                s = p.evaluate(SNAP)
                s["errs"], s["off"], s["taps"], s["side"] = errs, off, AK.taps(p), AK.no_sideways(p)
                if shots:
                    os.makedirs(shots, exist_ok=True)
                    p.screenshot(path=os.path.join(shots, f"warroom_{k}.png"))
                    if k in ("forming", "trade"):
                        p.screenshot(path=os.path.join(shots, f"warroom_{k}_full.png"), full_page=True)
                if k == "forming":
                    cd0 = p.evaluate("[...document.querySelectorAll('.cd')].map((e) => e.textContent)")
                    p.clock.set_fixed_time(dt.datetime.fromtimestamp(NOW + 5, dt.timezone.utc))
                    p.wait_for_timeout(1300)
                    s["tick"] = cd0 != p.evaluate("[...document.querySelectorAll('.cd')].map((e) => e.textContent)")
                    p.click("#pushBtn")
                    s["push2"] = [p.get_attribute("#pushBtn", "aria-pressed"), p.evaluate("localStorage.getItem('oly.wr.push')")]
                    p.reload()
                    p.wait_for_function("window.WARROOM && window.WARROOM.ready()", timeout=60000)
                    s["push3"] = p.get_attribute("#pushBtn", "aria-pressed")
                out[k] = s
                ctx.close()
            ctx, p, errs, seen, off = AK.page(br, origin, reduced=True, mock={f"/{TOPIC}-bars/json": ndjson(sc["forming"]["bars"]), f"/{TOPIC}/json": ndjson(sc["forming"]["core"])})
            p.clock.set_fixed_time(dt.datetime.fromtimestamp(NOW, dt.timezone.utc))
            p.goto(f"{origin}/warroom/")
            p.wait_for_function("window.WARROOM && window.WARROOM.ready()", timeout=60000)
            p.wait_for_timeout(900)
            out["reduced"] = p.evaluate("({ low: window.WARROOM.low, fx: !!document.getElementById('olyNightFx'), caret: !!document.querySelector('.caret'), "
                                        "first: (document.querySelector('#feed li .tx') || {}).textContent || '' })")
            ctx.close()
    finally:
        srv.shutdown()
    F, I, T, S = out["forming"], out["idle"], out["trade"], out["stale"]
    check("c. no page error; nothing off the site but the (mocked) PC status topic and its chart twin", all(not out[k]["errs"] and not out[k]["off"] for k in ("idle", "forming", "trade", "stale")),
          [(k, out[k]["errs"][:2], out[k]["off"][:2]) for k in ("idle", "forming", "trade", "stale")])
    check("c. all bots side by side: the overview (LIT, ATLAS, BLITZ, ORDER FLOW: a ring with %, the word) and a ladder each",
          [o[0] for o in F["over"]] == ["LIT", "ATLAS", "BLITZ", "POSEIDON"] and F["ladders"] == ["lad-lit", "lad-atlas", "lad-blitz", "lad-of"] and F["over"][0][1:] == ["64%", "Close"], F["over"])
    check("c. the ladders: LIT 10 (4 passed, now, next), ATLAS 3 lobes x 5 steps, BLITZ 6 off, ORDER FLOW 5; the current step shows the PC's words, the next what it waits for",
          F["litSteps"] == ["done"] * 4 + ["now", "next"] + ["wait"] * 4 and F["lobes"] == 3 and F["lobeSteps"] == 15 and F["blitz"] == ["off"] * 6 and F["ofSteps"] == 5
          and F["nowTx"].startswith("5m CISD closed through 26,232.50") and F["nextTx"].startswith("Needs its checks to pass"), (F["litSteps"], F["nowTx"], F["nextTx"]))
    check("c. idle: the next step's numbers on screen (a sweep of >= X pts below the London low at 26,190.25), the headline 'Quiet', LIT 'Far'",
          re.search(r"Needs a sweep of ≥ [\d.]+ pts below the London low at 26,190\.25", I["nextTx"]) and I["head"].startswith("Quiet") and I["over"][0][2] == "Far", (I["nextTx"], I["head"]))
    check("c. the countdowns tick every second (window left / next opening)", F.get("tick") is True and len(F["cds"]) >= 4, F["cds"][:6])
    check("c. the story of the day: newest first with times, the newest line typed out in full", F["feed"] and any("09:40" in x and "swept by 12.0 pts" in x for x in F["feed"])
          and any("ATLAS S/R window opened" in x for x in F["feed"]), F["feed"][:5])
    check("c. the chart is drawn (ink on the canvas) with its legend (LIT levels, the CISD line); the trade lines when in a trade",
          F["inked"] > 500 and not F["chartEmpty"] and "LIT levels" in F["legend"] and "LIT cisd" in F["legend"] and "LIT stop" in T["legend"] and "LIT target" in T["legend"], (F["inked"], F["legend"], T["legend"]))
    check("c. in a trade: a big card per account (LONG 4 micros, Zlarior 50K) with live $, R, entry / stop / target, time in trade, what closes it; the headline says so",
          T["trades"] == 2 and "LIT LONG 4 micros · Zlarior 50K" in T["trade"] and re.search(r"[+-]\$[\d,]+", T["trade"]) and "R" in T["trade"] and "Time in trade" in T["trade"]
          and "Closes on the stop at 26,178.00" in T["trade"] and T["head"].startswith("In a trade"), T["trade"][:300])
    check("c. stale: the striped banner 'Stale: your PC last spoke 2 h 0 min ago', the PC pill red; fresh: 'PC 4 min ago', green, no banner",
          S["stale"] and S["staleText"].startswith("Stale: your PC last spoke 2 h 0 min ago") and S["level"] == "bad" and F["pc"] == "PC 4 min ago" and F["level"] == "ok" and not F["stale"], (S["staleText"], F["pc"]))
    check("c. the alert switch: off by default, on when tapped, remembered on this phone", F["push"] == "false" and F.get("push2") == ["true", "true"] and F.get("push3") == "true", (F["push"], F.get("push2"), F.get("push3")))
    check("c. effects: the particle field behind the page; reduced motion = no field, no typing (the whole line at once)",
          F["fx"] and not F["low"] and out["reduced"]["low"] and not out["reduced"]["fx"] and not out["reduced"]["caret"] and len(out["reduced"]["first"]) > 20, (F["fx"], out["reduced"]))
    check("c. taps >= 44 px, no sideways scroll at 390 x 844", all(not out[k]["taps"] and out[k]["side"] for k in ("idle", "forming", "trade", "stale")), [(k, out[k]["taps"][:4]) for k in out if k != "reduced"])
    check("c. no account id on the screen (the glance's mode is never shown)", all("6018" not in out[k]["body"] and "MFFUSF" not in out[k]["body"] for k in ("idle", "forming", "trade", "stale")))


if __name__ == "__main__":
    args = sys.argv[1:]
    shots = args[args.index("--shots") + 1] if "--shots" in args else None
    test_static()
    test_node()
    if "--static" not in args:
        test_page(shots)
    AK.finish()
