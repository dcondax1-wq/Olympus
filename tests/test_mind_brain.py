"""Strategy Brain (day-mind 2026-11-23): cities/mind/ = one 3D brain, a lobe per strategy we trade (LIT/Zlarior, ATLAS EMA, MACD, S/R)
plus the research lobes; tap a lobe = its step chain + live state from the PC glance + every trade as a timeline on a 5m mini-chart.
  a. static: files there, three.js pinned on cdnjs (r160) with the local r160 fallback, OLYMPUS NIGHT colours (no brown / olive), read only
     (no arm / start / stop / order call), no secrets or account ids, no innerHTML, BLITZ not a lobe, low-power + reduced-motion rules
  n. node: the modules parse; mindcore on the real odeon/trades.json + cities/brain-data.json (every strategy lobe has trades, LIT's chain
     = sweep -> inducement -> CISD -> entry -> stop -> VIX-band target, a LIT backtest timeline has every step's time, stop = 1 tick beyond
     the sweep extreme, 5m bars), live state from a glance (fresh / stale / missing / off)
  b. Chromium 390 x 844 (Node Playwright): 3D mounts, no page error, no sideways scroll, the live chain, trades + timeline chart, research
     lobe, canvas tap picks a lobe, the 2D fallback. MIND_SHOTS=<dir> saves the screenshots. MB_NO_BROWSER=1 skips b.
    python -X utf8 -m tests.test_mind_brain
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
WEB = os.path.join(PUB, "cities", "mind")
FILES = ["index.html", "mind.js", "mindcore.js", "mind-scene.js", "mind.css"]
RES: list = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:600]}"), flush=True)


def read(n):
    return open(os.path.join(WEB, n), encoding="utf-8").read()


def static():
    for f in FILES:
        check(f"a. {f} exists", os.path.exists(os.path.join(WEB, f)))
    src = {f: read(f) for f in FILES}
    allsrc = "\n".join(src.values())
    check("a. three.js pinned on cdnjs r160", "https://cdnjs.cloudflare.com/ajax/libs/three.js/0.160.0/three.module.min.js" in src["mind-scene.js"])
    check("a. local r160 fallback", "../../jarvis/three.module.min.js" in src["mind-scene.js"] and os.path.exists(os.path.join(PUB, "jarvis", "three.module.min.js")))
    check("a. no other external script", not re.search(r"<script[^>]+src=\"https?://", src["index.html"]))
    for c in ["#000", "#16131e", "#3e255e", "#4d2e76", "#9d59ee", "#f1c14b", "#77db89"]:
        check(f"a. palette {c}", c in src["mind.css"] or c in src["mind-scene.js"])
    code = re.sub(r"/\*.*?\*/|(?<![:'\"])//[^\n]*|<!--.*?-->", "", allsrc, flags=re.S)       # the code without its comments
    check("a. no brown / olive", not re.search(r"brown|olive|#8b4513|#a0522d|#808000|#6b8e23|#556b2f", code, re.I))
    check("a. read only (no arm / start / stop / order call)", not re.search(r"\b(fetch|post)\([^)]*(arm|start|stop|order)", allsrc, re.I) and "method: 'POST'" not in allsrc)
    check("a. no innerHTML", "innerHTML" not in code)
    check("a. no secrets", not re.search(r"(api[_-]?key|token|secret|password)\s*[:=]\s*['\"][^'\"]{6,}", allsrc, re.I))
    check("a. no account ids (MFFU / NinjaTrader ids, ntfy topic)", not re.search(r"\b(MFFU|FFN|APEX|TPT|SIM)[A-Z]*-?\d{4,}|\bntfy\.sh/[a-z0-9_-]{6,}", allsrc, re.I))
    check("a. BLITZ is not a lobe", "BLITZ" not in src["mindcore.js"].split("export const LOBES")[1].split("];")[0])
    check("a. low power + reduced motion + hidden tab rules", all(k in src["mind-scene.js"] for k in ["isLowPower", "cfg.reduce", "visibilitychange", "ST.low"]) and "prefers-reduced-motion" in src["mind.js"])
    check("a. 2D fallback", "?lite=2d" in src["mindcore.js"] + src["mind.js"] or "lite=2d" in src["mind.js"])
    check("a. pc_feed.js wired", "../../pc_feed.js" in src["index.html"] and "status_feed.json" in src["mind.js"])


NODE_CORE = r"""
import * as M from '%(core)s';
import fs from 'fs';
const f = JSON.parse(fs.readFileSync('%(trades)s')), d = JSON.parse(fs.readFileSync('%(data)s')), o = {};
o.counts = Object.fromEntries(M.LOBES.filter((l) => l.kind === 'strategy').map((l) => [l.id, M.tradesFor(l.id, f).length]));
o.litChain = M.CHAINS.lit.map((s) => s.label);
const bt = M.tradesFor('lit', f).find((t) => t.src === 'backtest' && t.sweep);
const tl = M.timeline('lit', bt); o.btSteps = tl.steps.map((s) => [s.key, s.hm]); o.bars = tl.bars.length; o.win = M.chartWindow(tl).bars.length;
o.stopTick = bt.side === 'LONG' ? +(bt.sweep.ext_px - bt.stop).toFixed(2) : +(bt.stop - bt.sweep.ext_px).toFixed(2);
o.stopText = tl.steps.find((s) => s.key === 'stop').text; o.result = tl.result; o.usd = tl.usd; o.setup = tl.setup.hm;
o.firstSrc = M.tradesFor('lit', f)[0].src;
o.research = M.LOBES.filter((l) => l.kind === 'research').map((l) => M.research(l.id, d).total);
const g = { t: 1000, bots: [{ id: 'lit', stage: '5m CISD (5/10)', on: true }, { id: 'atlas', lobes: [{ id: 'ema', st: 'armed', text: 'x' }, { id: 'macd', st: 'off', text: 'off' }] }] };
o.fresh = M.live('lit', g, 1100); o.stale = M.live('lit', g, 1000 + 3600); o.none = M.live('lit', null, 0); o.ema = M.live('ema', g, 1100); o.off = M.live('macd', g, 1100);
const L = M.placeLabels([{ id: 'a', x: 100, y: 100, w: 80, h: 14, pri: 1 }, { id: 'b', x: 104, y: 102, w: 80, h: 14, pri: 2 }, { id: 'c', x: 102, y: 101, w: 80, h: 14, pri: 1 },
  { id: 'd', x: 101, y: 100, w: 80, h: 14, pri: 0 }, { id: 'e', x: 100, y: 99, w: 80, h: 14, pri: 0 }], { w: 400, h: 300 });
o.labels = L; o.labelsTop = L.find((q) => q.id === 'b');
o.states = M.chainStates('lit', o.fresh).map((s) => s.state); o.inTrade = M.live('lit', { t: 1, bots: [{ id: 'lit', stage: 'In trade (9/10)' }] }, 2).idx;
console.log(JSON.stringify(o));
"""


def node():
    for f in ["mind.js", "mindcore.js", "mind-scene.js"]:
        r = subprocess.run(["node", "--check", os.path.join(WEB, f)], capture_output=True, text=True, timeout=30)
        check(f"n. node parses {f}", r.returncode == 0, r.stderr)
    code = NODE_CORE % {"core": os.path.join(WEB, "mindcore.js").replace("\\", "/"), "trades": os.path.join(PUB, "odeon", "trades.json").replace("\\", "/"),
                        "data": os.path.join(PUB, "cities", "brain-data.json").replace("\\", "/")}
    r = subprocess.run(["node", "--input-type=module", "-e", code], capture_output=True, text=True, timeout=60)
    try:
        o = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception as e:  # noqa: BLE001
        check("n. mindcore runs", False, (r.stderr or str(e))[:600])
        return
    check("n. every strategy lobe has trades", all(v > 0 for v in o["counts"].values()), o["counts"])
    check("n. LIT chain = sweep > inducement > CISD > entry > stop > VIX-band target", o["litChain"] == ["Sweep", "Inducement", "CISD", "Entry", "Stop", "VIX-band target"], o["litChain"])
    check("n. a LIT backtest timeline times every step", all(hm for _, hm in o["btSteps"]), o["btSteps"])
    check("n. LIT stop = 1 tick beyond the sweep extreme", o["stopTick"] == 0.25 and "1 tick beyond the sweep extreme" in o["stopText"], (o["stopTick"], o["stopText"]))
    check("n. 5m bars + a chart window", o["bars"] > 5 and o["win"] >= 6, (o["bars"], o["win"]))
    check("n. $ result shown", o["result"].startswith(("+$", "-$")) and o["setup"], (o["result"], o["setup"]))
    check("n. real trades listed first", o["firstSrc"] in ("real", "live"), o["firstSrc"])
    check("n. research lobes have findings", all(n > 0 for n in o["research"]), o["research"])
    check("n. live: fresh LIT at 5/10 = CISD now", o["fresh"]["word"] == "live" and o["states"] == ["done", "done", "now", "wait", "wait", "wait"], (o["fresh"], o["states"]))
    check("n. live: old report = stale, none = waiting", o["stale"]["word"] == "stale" and o["none"]["word"] == "waiting" and not o["none"]["has"], (o["stale"], o["none"]))
    check("n. live: ATLAS EMA armed = entry step, MACD off", o["ema"]["idx"] == 3 and o["off"]["word"] == "off", (o["ema"], o["off"]))
    shown = [q for q in o["labels"] if q["show"]]
    ov = sum(1 for i, a in enumerate(shown) for b in shown[i + 1:] if a["x"] < b["x"] + 82 and b["x"] < a["x"] + 82 and a["y"] < b["y"] + 16 and b["y"] < a["y"] + 16)
    check("n. labels: overlapping lobes get moved or hidden, never drawn on top of each other", ov == 0 and len(shown) >= 2 and any(not q["show"] for q in o["labels"]), o["labels"])
    check("n. labels: the higher priority keeps the spot above its lobe", o["labelsTop"]["show"] and o["labelsTop"]["y"] < 100, o["labelsTop"])
    check("n. live: in trade = the target step", o["inTrade"] == 5, o["inTrade"])


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def browser():
    r = subprocess.run(["node", "-e", "require('playwright')"], capture_output=True, text=True, timeout=30, env={**os.environ, "NODE_PATH": _npm_root()})
    if r.returncode != 0:
        print("[SKIP] b. Node Playwright not installed here", flush=True)
        return
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(_Quiet, directory=PUB))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    shots = os.environ.get("MIND_SHOTS", "")
    if shots:
        os.makedirs(shots, exist_ok=True)
    try:
        r = subprocess.run(["node", os.path.join(ROOT, "tests", "mind_brain_browser.cjs"), f"http://127.0.0.1:{srv.server_address[1]}", shots],
                           capture_output=True, text=True, timeout=240, env={**os.environ, "NODE_PATH": _npm_root()})
    finally:
        srv.shutdown()
    try:
        o = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception as e:  # noqa: BLE001
        check("b. browser run", False, (r.stderr or r.stdout or str(e))[:600])
        return
    check("b. no fatal", "fatal" not in o, o.get("fatal"))
    check("b. 3D mounts (three r160)", str(o.get("mode", "")).startswith("3d") and (o.get("stats") or {}).get("lobes") == 10 and (o.get("stats") or {}).get("three") == "160", (o.get("mode"), o.get("stats")))
    check("b. draw calls small", 0 < (o.get("stats") or {}).get("calls", 99) <= 8, o.get("stats"))
    check("b. no page error", not o.get("errors") and not o.get("flatErrors"), (o.get("errors"), o.get("flatErrors")))
    check("b. no sideways scroll at 390", o.get("sideways") is False)
    lay = o.get("layout") or {}
    check("b. brain under the header, lobe cards just below it", lay and lay["canvasTop"] >= lay["headerBottom"] - 30 and 0 <= lay["navTop"] - lay["canvasBottom"] <= 16 and lay["navBottom"] <= lay["vh"], lay)
    check("b. no two lobe names overlap", (o.get("labels") or {}).get("overlaps") == 0 and (o.get("labels") or {}).get("shown", 0) >= 6, o.get("labels"))
    check("b. low-power mode still 3D, light", o.get("lowMode") == "3d-low" and (o.get("lowStats") or {}).get("low") is True and not o.get("lowErrors"), (o.get("lowMode"), o.get("lowStats"), o.get("lowErrors")))
    check("b. PC pill live", "PC live" in (o.get("pill") or ""), o.get("pill"))
    check("b. LIT chain shows CISD now", "cisd:now" in (o.get("litNow") or []) and "Live" in (o.get("litState") or ""), (o.get("litNow"), o.get("litState")))
    check("b. trades + timeline chart", o.get("trades", 0) >= 5 and (o.get("tl") or {}).get("candles", 0) >= 5 and (o.get("tl") or {}).get("chips", 0) >= 8, (o.get("trades"), o.get("tl")))
    check("b. backtest timeline: every step timed", o.get("tlFull", 0) >= 9, o.get("tlFull"))
    check("b. ATLAS EMA armed = entry now, has trades", o.get("emaNow") == ["entry"] and o.get("emaTrades", 0) >= 1, (o.get("emaNow"), o.get("emaTrades")))
    check("b. ATLAS S/R done for today = all steps done", o.get("srDone") == 6, o.get("srDone"))
    check("b. research lobe lists findings", o.get("finds", 0) >= 3, o.get("finds"))
    check("b. close hides the sheet", o.get("closed") == "true")
    check("b. a canvas tap picks a lobe", bool(o.get("canvasPick")), o.get("canvasPick"))
    check("b. 2D fallback works", o.get("flatMode") == "2d" and o.get("flatPick") == "ATLAS MACD", (o.get("flatMode"), o.get("flatPick")))


def _npm_root():
    try:
        return subprocess.run(["npm", "root", "-g"], capture_output=True, text=True, timeout=30).stdout.strip()
    except Exception:  # noqa: BLE001
        return ""


def main():
    static()
    node()
    if os.environ.get("MB_NO_BROWSER") != "1":
        browser()
    print(f"\n{sum(RES)}/{len(RES)} passed")
    sys.exit(0 if all(RES) else 1)


if __name__ == "__main__":
    main()
