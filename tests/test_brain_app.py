"""THE BRAIN (day-brain-app 2026-11-24; owner: "a huge brain, where I can directly go to certain areas ... see what trade is coming up soon,
live 3D charts, brain thinking process"): tools/web_public/brain/ + the links on Home, NQ, Pillars and War Room.
  a. static: the files, three.js pinned on cdnjs r160 + the local r160 fallback, OLYMPUS NIGHT (no brown / olive / cyan), no innerHTML,
     read only, no secrets / account ids, learn.json + fixture.json fresh, the links, the forbidden files untouched against origin/pc
  n. node: braincore on the SAMPLE fixture (6 regions, the PC's next / think / levels win, fibs of the leg, an FVG zone), on the real-shape
     post without the new fields (derived from the War Room model, the PC's log), on nothing at all ("NO DATA", no made-up numbers)
  b. Chromium 390 x 844 (Node Playwright, software GL: it waits for data-mode): SAMPLE overview in 3D, a tap on the brain flies into a
     region, the LIT / ATLAS / ORDER FLOW / BLITZ / MARKET LEARN / RISK rooms, the live post replaces the sample, the 2D fallback.
     BRAIN_SHOTS=<dir> saves the shots. BRAIN_NO_BROWSER=1 skips b.
    python -X utf8 -m tests.test_brain_app
"""
from __future__ import annotations

import copy
import functools
import http.server
import json
import os
import re
import subprocess
import sys
import tempfile
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
PUB = os.path.join(ROOT, "tools", "web_public")
APP = os.path.join(PUB, "brain")
FILES = ["index.html", "brain.js", "braincore.js", "brain-scene.js", "chart3d.js", "brain.css", "learn.json", "fixture.json", "manifest.webmanifest", "icon.svg"]
FORBIDDEN = ["tools/web_public/sw.js", "tools/build_web_dashboard.py", "tools/web_public/jarvis/apps.js", "tools/web_public/olympus/olympus.js"]
RES: list = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:700]}"), flush=True)


def read(*p):
    with open(os.path.join(PUB, *p), encoding="utf-8") as fh:
        return fh.read()


def static():
    for f in FILES:
        check(f"a. brain/{f} exists", os.path.exists(os.path.join(APP, f)))
    src = {f: read("brain", f) for f in FILES if f.endswith((".js", ".html", ".css"))}
    allsrc = "\n".join(src.values())
    code = re.sub(r"/\*.*?\*/|(?<![:'\"])//[^\n]*|<!--.*?-->", "", allsrc, flags=re.S)
    check("a. three.js pinned on cdnjs r160 + the local r160 fallback", "https://cdnjs.cloudflare.com/ajax/libs/three.js/0.160.0/three.module.min.js" in src["brain-scene.js"]
          and "../jarvis/three.module.min.js" in src["brain-scene.js"] and os.path.exists(os.path.join(PUB, "jarvis", "three.module.min.js")))
    for c in ["#000", "#16131e", "#3e255e", "#4d2e76", "#9d59ee", "#f1c14b", "#77db89"]:
        check(f"a. palette {c}", c in src["brain.css"])
    check("a. no brown / olive / cyan", not re.search(r"brown|olive|cyan|#8b4513|#a0522d|#808000|#6b8e23|#556b2f|#00ffff|#0ff\b|#5fd0c9|#6fb7ff", code, re.I))
    check("a. no innerHTML / eval", "innerHTML" not in code and "eval(" not in code)
    check("a. read only (no POST, no arm / start / stop / order call)", "method: 'POST'" not in allsrc and "method:'POST'" not in allsrc and not re.search(r"fetch\([^)]*(arm|start|stop|order)", allsrc, re.I))
    data = read("brain", "fixture.json") + read("brain", "learn.json")
    check("a. no secrets / account ids / ntfy topic (code + fixture + learn)", not re.search(r"(api[_-]?key|token|secret|password)\s*[:=]\s*['\"][^'\"]{6,}|\b(MFFU|FFN|APEX)[A-Z]*-?\d{3,}|6018|ntfy\.sh/[a-z0-9_-]{6,}", allsrc + data, re.I))
    check("a. the SAMPLE is labelled on the page", "SAMPLE" in src["brain.js"] and "SAMPLE" in json.loads(read("brain", "fixture.json"))["_about"])
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "build_brain_learn.py"), "--check"], capture_output=True, text=True, timeout=60)
    check("a. brain/learn.json fresh (tools/build_brain_learn.py --check)", r.returncode == 0, r.stdout + r.stderr)
    r = subprocess.run([sys.executable, "-X", "utf8", "-m", "tests.brain_fixture", "--check"], capture_output=True, text=True, timeout=60, cwd=ROOT)
    check("a. brain/fixture.json fresh (tests/brain_fixture.py --check)", r.returncode == 0, r.stdout + r.stderr)
    links = {"Home hero": read("gate", "index.html"), "NQ": read("nq", "index.html"), "Pillars": read("pillars", "index.html"), "War Room": read("warroom", "index.html")}
    for k, v in links.items():
        check(f"a. {k} links the Brain", 'href="../brain/"' in v)
    try:
        diff = subprocess.run(["git", "diff", "--name-only", "origin/pc", "--", *FORBIDDEN], capture_output=True, text=True, timeout=30, cwd=ROOT).stdout.split()
        check("a. the lead's files untouched (sw.js, build_web_dashboard.py, jarvis/apps.js, olympus/olympus.js)", not diff, diff)
    except Exception as e:  # noqa: BLE001
        check("a. the lead's files untouched", False, e)


# ------------------------------------------------------------------------------------------------ scenarios (the War Room's)
def scenarios():
    from tests import test_warroom as T
    from tests import brain_fixture as BF
    now = T.NOW

    def parsed(core):
        nd = T.ndjson(core)
        js = "const F = require(%s); process.stdout.write(JSON.stringify(F.parseLatest(require('fs').readFileSync(0, 'utf8'))));" % json.dumps(os.path.join(PUB, "pc_feed.js"))
        r = subprocess.run(["node", "-e", js], input=nd, capture_output=True, text=True, timeout=30)
        return json.loads(r.stdout)
    forming = parsed(T.core_post("forming", now))
    trade = parsed(T.core_post("trade", now))
    fx = BF.make()
    plus = copy.deepcopy(forming)
    lit_fx = fx["lite"]["pc"]["glance"]["bots"][0]
    for b in plus["pc"]["glance"]["bots"]:
        if b.get("id") == "lit":
            b.update(think=lit_fx["think"], next=lit_fx["next"], levels=lit_fx["levels"])
    bars, _ = T.bars_post("forming", now)
    tbars, _ = T.bars_post("trade", now)
    return {"now": now, "forming": forming, "trade": trade, "plus": plus, "bars": bars, "tbars": tbars, "fixture": fx,
            "feed": T.FEED, "barsNd": T.ndjson(bars), "at_iso": __import__("datetime").datetime.fromtimestamp(now, __import__("datetime").timezone.utc).isoformat()}


NODE = r"""
import * as B from '%(core)s';
import fs from 'fs';
const rd = (p) => JSON.parse(fs.readFileSync(p, 'utf8'));
const X = rd('%(sc)s'), P = '%(pub)s/';
const site = { learn: rd(P + 'brain/learn.json'), pillarsData: rd(P + 'pillars/pillars-data.json'), brief: rd(P + 'nq/brief.json'), biz: rd(P + 'business/accounts.json'), payday: rd(P + 'business/payday.json') };
const pick = (M) => ({ mode: M.mode, ids: M.regions.map((r) => r.id), pulse: M.pulse, headline: M.headline,
  r: Object.fromEntries(M.regions.map((r) => [r.id, { status: r.status, next: r.next && { setup: r.next.setup, waiting: r.next.waiting, limit: r.next.limit, stop: r.next.stop, target: r.next.target,
    dist: r.next.dist, from: r.next.from, pct: r.next.pct, steps: r.next.steps && r.next.steps.length, inTrade: r.next.inTrade, rr: r.next.rr },
    chain: r.chain.map((c) => c.id + ':' + c.steps.length), think: r.think.map((t) => t.text), thinkFrom: r.thinkFrom,
    chart: r.chart && { state: r.chart.state, n: r.chart.candles.length, kinds: r.chart.levels.map((l) => l.kind + ':' + l.price + (l.price2 != null ? '-' + l.price2 : '')) },
    learn: { conf: r.learn.confidence, word: r.learn.confWord, week: r.learn.week.length, lessons: r.learn.lessons.length, src: r.learn.src },
    money: { accts: r.money.accounts.length, day: r.money.day, room: r.money.room, rooms: r.money.rooms } }])) });
const out = {
  sample: pick(B.build({ ...site, lite: X.fixture.lite, bars: X.fixture.bars, sample: true }, X.fixture.now)),
  live: pick(B.build({ ...site, lite: X.forming, bars: X.bars }, X.now)),
  plus: pick(B.build({ ...site, lite: X.plus, bars: X.bars }, X.now)),
  trade: pick(B.build({ ...site, lite: X.trade, bars: X.tbars }, X.now)),
  none: pick(B.build({}, X.now)),
  rows: B.levelRows([{ k: 'fvg', p: 10, p2: 12 }, ['PDH', 20], { kind: 'TP', price: 30 }, { k: 'x' }, 'junk']),
  think: B.thinkLines(['a', ['09:40', 'b'], { hm: '09:41', text: 'c' }, { x: 1 }, null]),
  fibs: B.fibs({ price: 100, price2: 200 }).map((f) => f.price),
};
console.log(JSON.stringify(out));
"""


def node(sc):
    for f in ("brain.js", "braincore.js", "brain-scene.js", "chart3d.js"):
        r = subprocess.run(["node", "--check", os.path.join(APP, f)], capture_output=True, text=True, timeout=30)
        check(f"n. node parses {f}", r.returncode == 0, r.stderr)
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        json.dump(sc, fh)
        pf = fh.name
    j = lambda *p: os.path.join(*p).replace("\\", "/")  # noqa: E731
    r = subprocess.run(["node", "--input-type=module", "-e", NODE % {"core": j(APP, "braincore.js"), "sc": pf.replace("\\", "/"), "pub": j(PUB)}], capture_output=True, text=True, timeout=90)
    os.unlink(pf)
    try:
        o = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception as e:  # noqa: BLE001
        check("n. braincore runs in node", False, (r.stderr or str(e))[:900])
        return
    S, L, PL, TR, N = o["sample"], o["live"], o["plus"], o["trade"], o["none"]
    check("n. six regions in order: LIT, ATLAS, BLITZ, ORDER FLOW, MARKET LEARN, RISK", S["ids"] == ["lit", "atlas", "blitz", "of", "learn", "risk"] and S["mode"] == "sample", S["ids"])
    sl = S["r"]["lit"]
    check("n. SAMPLE LIT: the PC's next line wins (setup, 7 steps, limit / stop / target, 3.5 pts, 3.1R)", sl["next"]["from"] == "pc" and sl["next"]["steps"] == 7 and sl["next"]["limit"] == 26232.5
          and sl["next"]["stop"] == 26178.0 and sl["next"]["target"] == 26401.5 and sl["next"]["dist"] == 3.5 and abs(sl["next"]["rr"] - 3.1) < 0.01, sl["next"])
    check("n. SAMPLE LIT: the think lines first (newest = the checks), the chart has 48 bars + sweep / limit / stop / target / FVG zone / 4 fibs",
          sl["thinkFrom"] == "think" and sl["think"][0].startswith("Checks 6 of 9") and sl["chart"]["n"] == 48
          and {"sweep:26190.25", "entry:26232.5", "stop:26178", "target:26401.5", "fvg:26205-26214.75"} <= set(sl["chart"]["kinds"])
          and sum(k.startswith("fib:") for k in sl["chart"]["kinds"]) == 4 and not any(k.startswith("level:26190.25") for k in sl["chart"]["kinds"]), sl)
    check("n. learning from brain/learn.json: LIT has this week's lessons, the confidence is not invented", sl["learn"]["week"] >= 1 and sl["learn"]["conf"] is None
          and sl["learn"]["word"] == "not scored yet" and "insights" in sl["learn"]["src"], sl["learn"])
    ll = L["r"]["lit"]
    check("n. live post without the new fields: LIT derived from the War Room (5m CISD, the CISD line as the limit, the stop from its words), the PC's log as thinking",
          ll["next"]["from"] == "derived" and "5m CISD" in ll["next"]["setup"] and ll["thinkFrom"] == "log" and any("London low" in t for t in ll["think"])
          and ll["chain"] == ["lit:10"] and ll["chart"]["n"] == 48 and ll["next"]["pct"] > 0, ll)
    check("n. live ATLAS: its 3 lobes, a chart", L["r"]["atlas"]["chain"] == ["ema:4", "macd:4", "sr:4"] or len(L["r"]["atlas"]["chain"]) == 3, L["r"]["atlas"]["chain"])
    check("n. the new fields on the real post: the PC's next / think / levels win", PL["r"]["lit"]["next"]["from"] == "pc" and PL["r"]["lit"]["thinkFrom"] == "think"
          and "fvg:26205-26214.75" in PL["r"]["lit"]["chart"]["kinds"], PL["r"]["lit"])
    check("n. in a trade: LIT says so, entry / stop / target from the open trade", TR["r"]["lit"]["next"]["inTrade"] is True and TR["r"]["lit"]["next"]["stop"] == 26178.0, TR["r"]["lit"]["next"])
    check("n. BLITZ OFF (paper), ORDER FLOW collecting 23 of 60 from the tick line, MARKET LEARN = the weekly lessons, RISK from the glance rooms",
          S["r"]["blitz"]["status"] == "OFF" and "23 of 60" in S["r"]["of"]["next"]["setup"] and S["r"]["learn"]["status"] == "WEEKLY"
          and len(S["r"]["risk"]["money"]["rooms"]) == 2 and S["r"]["risk"]["money"]["rooms"][0]["room"] == 1025, (S["r"]["blitz"]["status"], S["r"]["of"]["next"], S["r"]["risk"]["money"]))
    nl = N["r"]["lit"]
    check("n. nothing at all: NO DATA, no prices, no chart bars, no PC thinking (only the schedule), risk waiting (nothing made up)",
          N["mode"] == "none" and nl["status"] in ("NO DATA", "LIVE · waiting for the PC") and nl["next"]["limit"] is None and nl["next"]["stop"] is None and nl["chart"]["n"] == 0
          and nl["thinkFrom"] == "none" and all("window" in t for t in nl["think"]) and N["r"]["risk"]["status"] == "WAITING", (N["mode"], nl))
    check("n. pulse 0..1 for every region", all(0 <= v <= 1 for v in S["pulse"].values()) and len(S["pulse"]) == 6, S["pulse"])
    check("n. levelRows: FVG zone, [label, price], TP alias, junk dropped", o["rows"] == [{"kind": "fvg", "price": 10, "price2": 12, "label": "fvg"}, {"kind": "level", "price": 20, "price2": None, "label": "PDH"},
          {"kind": "target", "price": 30, "price2": None, "label": "TP"}], o["rows"])
    check("n. thinkLines: strings, [hm, text], {hm, text}; junk dropped", [t["text"] for t in o["think"]] == ["a", "b", "c"] and o["think"][1]["hm"] == "09:40", o["think"])
    check("n. fibs of a 100 -> 200 leg: 150, 138.25, 129.5, 121", o["fibs"] == [150, 138.25, 129.5, 121], o["fibs"])


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def browser(sc):
    try:
        npm = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True, timeout=30).stdout.strip()
    except Exception:  # noqa: BLE001
        npm = ""
    env = {**os.environ, "NODE_PATH": npm}
    if subprocess.run(["node", "-e", "require('playwright')"], capture_output=True, env=env, timeout=30).returncode != 0:
        print("[SKIP] b. Node Playwright not installed here", flush=True)
        return
    shots = os.environ.get("BRAIN_SHOTS", "")
    if shots:
        os.makedirs(shots, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        json.dump({"forming": sc["forming"], "formingPlus": sc["plus"], "trade": sc["trade"], "feed": sc["feed"], "barsNd": sc["barsNd"]}, fh)
        pf = fh.name
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(_Quiet, directory=PUB))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        r = subprocess.run(["node", os.path.join(ROOT, "tests", "brain_app_browser.cjs"), f"http://127.0.0.1:{srv.server_address[1]}", shots, pf],
                           capture_output=True, text=True, timeout=900, env=env)
    finally:
        srv.shutdown()
        os.unlink(pf)
    try:
        o = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception as e:  # noqa: BLE001
        check("b. browser run", False, (r.stderr or r.stdout or str(e))[:900])
        return
    check("b. no fatal", "fatal" not in o, o.get("fatal"))
    errs = [e for k in ("errors", "liveErrors", "plusErrors", "tradeErrors", "flatErrors") for e in (o.get(k) or [])]
    check("b. no page error in the 5 runs", not errs, errs[:4])
    check("b. nothing off the site but the blocked cdnjs copy (the local r160 loads instead)", all("cdnjs.cloudflare.com" in u for u in o.get("off", [])), o.get("off"))
    s = o.get("sample") or {}
    st = s.get("stats") or {}
    check("b. SAMPLE overview: the brain in 3D (r160, hq, 7,000 neurons, synapses, <= 10 draw calls)", str(s.get("mode", "")).startswith("3d") and st.get("three") == "160"
          and st.get("neurons", 0) >= 2600 and st.get("synapses", 0) > 300 and 0 < st.get("calls", 99) <= 10, (s.get("mode"), st))
    check("b. SAMPLE overview: the SAMPLE banner + pill, 6 region tags, a 6-region dock, 'Coming up soon' ranks the trading regions",
          "SAMPLE" in s.get("banner", "") and s.get("pill") == "SAMPLE" and s.get("tags") == ["lit", "atlas", "blitz", "of", "learn", "risk"] and s.get("dock") == s.get("tags")
          and s.get("soon", [])[:1] in (["atlas"], ["lit"]) and len(s.get("soon", [])) == 4, s)
    check("b. a tap on the brain flies into that region (ORDER FLOW: the room opens, #of in the address)", (o.get("tap") or {}) == {"r": "of", "hash": "#of", "sel": "of"}, o.get("tap"))
    ls = o.get("litSample") or {}
    check("b. LIT room (SAMPLE): next trade with its 7 steps (Limit now), waiting for, 3.5 pts, limit / stop / target", "London low" in ls.get("setup", "") and len(ls.get("chain", [])) == 7
          and "now:Limit" in ls.get("chain", []) and "checks" in ls.get("wait", "") and ls.get("dist", "").startswith("3.5 pts") and ls.get("px") == ["26,232.50", "26,178.00", "26,401.50"], ls)
    check("b. LIT room: the live 3D chart with the levels labelled (swept level, limit, stop, target, FVG, fibs)", ls.get("chart") and ls.get("chartMode") == "3d"
          and {"sweep", "entry", "stop", "target", "fvg", "fib"} <= set(ls.get("legend", [])) and any("swept" in x for x in ls.get("lbls", [])) and any(x.startswith("stop") for x in ls.get("lbls", [])), ls)
    check("b. LIT room: the thinking stream (7 PC lines + the day's story), learning (not scored yet, this week's lessons), today $ with SAMPLE",
          len(ls.get("think", [])) >= 7 and ls["think"][0].startswith("Checks") and "reasoning" in ls.get("thinkSrc", "") and ls.get("conf") == "not scored yet" and ls.get("week", 0) >= 1
          and "SAMPLE" in ls.get("money", "") and "$1,025" in ls.get("money", ""), {k: ls.get(k) for k in ("think", "thinkSrc", "conf", "week", "money")})
    lr = o.get("learn") or {}
    check("b. MARKET LEARN room: the market read, this week's shared lessons, the source named", lr.get("r") == "learn" and "Market now" in lr.get("body", "") and lr.get("week", 0) >= 1 and "insights.json" in lr.get("learnSrc", ""), {k: lr.get(k) for k in ("r", "week", "learnSrc")})
    rk = o.get("risk") or {}
    check("b. RISK room: every account once + the LIT / ATLAS room meters", rk.get("r") == "risk" and "LIT room" in rk.get("money", "") and "ATLAS room" in rk.get("money", "") and "Zlarior 50K" in rk.get("money", ""), rk.get("money", "")[:300])
    lv = o.get("litLive") or {}
    check("b. the real post replaces the SAMPLE: no banner, the PC pill, LIT 5m CISD from its steps, its log as thinking (the fuller lines named as not sent yet)",
          (o.get("livePill") or [None, False])[1] is True and "PC" in (o.get("livePill") or [""])[0] and "5m CISD" in lv.get("setup", "") and any(c.startswith("now:") for c in lv.get("chain", []))
          and any("London low" in t for t in lv.get("think", [])) and "not in its report yet" in lv.get("thinkSrc", "") and "SAMPLE" not in lv.get("money", ""), {k: lv.get(k) for k in ("setup", "chain", "thinkSrc")})
    at = o.get("atlas") or {}
    check("b. ATLAS room: 3 lobes with their steps, a chart", at.get("r") == "atlas" and at.get("lobes") == ["ema", "macd", "sr"] and at.get("chart"), {k: at.get(k) for k in ("r", "lobes", "chart")})
    check("b. ORDER FLOW room: 23 of 60 not in this post -> 'Not collecting yet' honest; BLITZ room OFF, not thinking", (o.get("of") or {}).get("r") == "of" and (o.get("blitz") or {}).get("status") == "OFF"
          and "not thinking" in (o.get("blitz") or {}).get("body", ""), ((o.get("of") or {}).get("setup"), (o.get("blitz") or {}).get("status")))
    pl = o.get("litPlus") or {}
    check("b. the PC's new fields on a real post: its next line + think lines + FVG drawn", "London low sweep" in pl.get("setup", "") and pl.get("think", [""])[0].startswith("Checks") and "fvg" in pl.get("legend", []), {k: pl.get(k) for k in ("setup", "legend")})
    tr = o.get("trade") or {}
    check("b. in a trade: IN A TRADE on the LIT room, entry / stop / target", "IN A TRADE" in tr.get("body", "") and tr.get("px", [None, None])[1] == "26,178.00", tr.get("px"))
    check("b. no sideways scroll at 390; every tap target >= 44 px", (o.get("sampleGeo") or {}).get("wide") is False and (o.get("liveGeo") or {}).get("wide") is False
          and not (o.get("sampleGeo") or {}).get("small") and not (o.get("liveGeo") or {}).get("small"), (o.get("sampleGeo"), o.get("liveGeo")))
    check("b. 2D fallback (?lite=2d, reduced motion): 6 glowing regions, the chart in 2D, a tap opens a room", (o.get("flat") or {}) == {"mode": "2d", "n": 6, "chart": "2d"} and o.get("flatPick") == "risk", (o.get("flat"), o.get("flatPick")))
    check("b. account ids never on screen", all("6018" not in (o.get(k) or {}).get("body", "") and "MFFUSF" not in (o.get(k) or {}).get("body", "") for k in ("litLive", "atlas", "trade", "risk")))


def main():
    static()
    sc = scenarios()
    node(sc)
    if os.environ.get("BRAIN_NO_BROWSER") != "1":
        browser(sc)
    print(f"\n{sum(RES)}/{len(RES)} passed")
    sys.exit(0 if all(RES) else 1)


if __name__ == "__main__":
    main()
