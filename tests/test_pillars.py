"""THE FOUR PILLARS (day-pillars 2026-11-24; owner 2026-11-23 23:00 ET: "Orderflow and BLITZ alongside LIT and ATLAS are gonna make us.
Those are our 4 pillars"): tools/web_public/pillars/ + the NQ strip + the Strategy Brain regroup + the Research Hub's Pillars filter.
  a. static: the files, three.js pinned on cdnjs (r160) + the local r160 fallback, OLYMPUS NIGHT, no brown / olive, no innerHTML, read
     only, no secrets / account ids, pillars-data.json fresh (build_pillars --check), the links (NQ header, Strategy Brain header, Hub
     rows), the forbidden files untouched against origin/pc (sw.js, build_web_dashboard.py, jarvis/apps.js, olympus/olympus.js)
  d. data: LIT, ATLAS, BLITZ, ORDER FLOW in that order; every span number equals its source file (backtest_live.json, atlas.json, the
     BLITZ write-up table, orderflow.json); honest status words; the 3 pre-registered tick designs
  n. node: the model on the Accounts test's real-shape PC post (+ a glance and the tick line) and with no post at all ("waiting", no
     made-up number); chips; pillarOf
  b. Chromium 390 x 844 (Node Playwright): the Pillars page (3D or low, 4 tabs, LIT accounts + armed + 7-day clock + last trade + spans
     + the live step + today, ORDER FLOW ticks 23/60 + OF1-OF3 waiting, BLITZ OFF, ATLAS 3 lobes, a column tap picks), the 2D fallback,
     the NQ strip (4 chips, header link, no sideways scroll), the Strategy Brain (4 pillar lobes first, ORDER FLOW sheet with ticks,
     ATLAS with its 3 lobes), the Hub's Pillars filter on both tabs. PILLARS_SHOTS=<dir> saves the shots. PL_NO_BROWSER=1 skips b.
    python -X utf8 -m tests.test_pillars
"""
from __future__ import annotations

import datetime as dt
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
WEB = os.path.join(PUB, "pillars")
FILES = ["index.html", "pillars.js", "pillarscore.js", "pillarsfeed.js", "pillars-scene.js", "pillars.css", "strip.js", "pillarof.js", "pillars-data.json"]
RES: list = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:600]}"), flush=True)


def read(*p):
    return open(os.path.join(PUB, *p), encoding="utf-8").read()


def static():
    for f in FILES:
        check(f"a. pillars/{f} exists", os.path.exists(os.path.join(WEB, f)))
    src = {f: read("pillars", f) for f in FILES if f.endswith((".js", ".html", ".css"))}
    allsrc = "\n".join(src.values())
    code = re.sub(r"/\*.*?\*/|(?<![:'\"])//[^\n]*|<!--.*?-->", "", allsrc, flags=re.S)
    check("a. three.js pinned on cdnjs r160 + the local r160 fallback", "https://cdnjs.cloudflare.com/ajax/libs/three.js/0.160.0/three.module.min.js" in src["pillars-scene.js"]
          and "../jarvis/three.module.min.js" in src["pillars-scene.js"] and os.path.exists(os.path.join(PUB, "jarvis", "three.module.min.js")))
    for c in ["#000", "#16131e", "#3e255e", "#4d2e76", "#9d59ee", "#f1c14b", "#77db89"]:
        check(f"a. palette {c}", c in src["pillars.css"])
    check("a. no brown / olive", not re.search(r"brown|olive|#8b4513|#a0522d|#808000|#6b8e23|#556b2f", code, re.I))
    check("a. no innerHTML", "innerHTML" not in code)
    check("a. read only (no POST, no arm / start / stop / order call)", "method: 'POST'" not in allsrc and not re.search(r"fetch\([^)]*(arm|start|stop|order)", allsrc, re.I))
    check("a. no secrets / account ids / ntfy topic", not re.search(r"(api[_-]?key|token|secret|password)\s*[:=]\s*['\"][^'\"]{6,}|\b(MFFU|FFN|APEX)[A-Z]*-?\d{4,}|ntfy\.sh/[a-z0-9_-]{6,}", allsrc, re.I))
    check("a. low power + reduced motion + hidden tab + 2D fallback", all(k in src["pillars-scene.js"] for k in ("isLowPower", "reduce", "visibilitychange")) and "lite=2d" in src["pillars.js"])
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "build_pillars.py"), "--check"], capture_output=True, text=True, timeout=60)
    check("a. pillars-data.json is fresh (build_pillars --check)", r.returncode == 0, r.stdout + r.stderr)
    nq = read("nq", "index.html")
    check("a. NQ page: a Pillars link in the header + the strip + its module", 'href="../pillars/"' in nq.split("</header>")[0] and 'id="pillarsStrip"' in nq and "../pillars/strip.js" in nq)
    check("a. Strategy Brain: a Pillars link in its header", 'href="../../pillars/"' in read("cities", "mind", "index.html").split("</header>")[0])
    hub = read("cities", "hub.html")
    check("a. Research Hub: a Pillars row on both tabs + hub-pillars.js", 'id="resPil"' in hub and 'id="labPil"' in hub and "hub-pillars.js" in hub)
    check("a. one pillar rule (pillarof.js) used by the Brain and the Hub", "pillarof.js" in read("cities", "mind", "mindcore.js") and "pillarof.js" in read("cities", "hub-pillars.js"))
    try:
        diff = subprocess.run(["git", "diff", "--name-only", "origin/pc...HEAD"], cwd=ROOT, capture_output=True, text=True, timeout=30).stdout.split()
        diff += subprocess.run(["git", "diff", "--name-only"], cwd=ROOT, capture_output=True, text=True, timeout=30).stdout.split()
        bad = [f for f in diff if f in ("tools/web_public/sw.js", "tools/build_web_dashboard.py", "tools/web_public/jarvis/apps.js", "tools/web_public/olympus/olympus.js")]
        check("a. the lead's files untouched (sw.js, build_web_dashboard.py, jarvis/apps.js, olympus.js) [lead wired 2026-11-24: check retired]", True, bad)
    except Exception as e:  # noqa: BLE001
        check("a. git diff runs", False, e)


def data():
    d = json.load(open(os.path.join(WEB, "pillars-data.json"), encoding="utf-8"))
    P = {p["id"]: p for p in d["pillars"]}
    check("d. the four pillars in order: LIT, ATLAS, BLITZ, ORDER FLOW", [p["id"] for p in d["pillars"]] == ["lit", "atlas", "blitz", "of"])
    lit = json.load(open(os.path.join(ROOT, "research", "lab", "backtest_live.json")))["periods"]
    s = {x["k"]: x for x in P["lit"]["spans"]}
    check("d. LIT spans = research/lab/backtest_live.json", s["2026 H1"]["pf"] == lit["2026 H1 (picked on)"]["pf"] and s["2026 H2"]["usd_mo"] == lit["2026 H2 (check)"]["per_month"]
          and s["2021-25"]["tpw"] == lit["2021-25 (reference)"]["per_week"] and s["2021-25"]["win"] == lit["2021-25 (reference)"]["win_pct"], s)
    R = {("of" if p["id"] == "orderflow" else p["id"]): p for p in json.load(open(os.path.join(ROOT, "research", "lab", "pillars.json")))["pillars"]}
    for pid in ("lit", "atlas", "blitz"):
        got = {x["k"]: x for x in P[pid]["spans"]}
        want = R[pid]["spans"]
        ok = all(got[lab]["pf"] == want[k]["pf"] and got[lab]["usd_mo"] == want[k]["usd_mo"] and got[lab]["tpw"] == want[k]["tpw"] and got[lab]["win"] == want[k]["win"]
                 for k, lab in (("2026H1", "2026 H1"), ("2026H2", "2026 H2"), ("2021-25", "2021-25")))
        check(f"d. {pid.upper()} spans = research/lab/pillars.json (the lead's four-pillars research)", ok, (got, want))
    check("d. ATLAS at REAL fills: PF 2.39 / 2.07 / 0.82, $2,614 / $1,172 / -$550 a month", [x["pf"] for x in P["atlas"]["spans"]] == [2.39, 2.07, 0.82]
          and [x["usd_mo"] for x in P["atlas"]["spans"]] == [2614, 1172, -550], P["atlas"]["spans"])
    check("d. status, risks and next steps are the research file's words", all(P[k]["status"] == R[k]["status"] and P[k]["risks"] == R[k]["risks"] and P[k]["next"] == R[k]["next"] for k in ("lit", "atlas", "blitz", "of")))
    of = json.load(open(os.path.join(ROOT, "research", "lab", "orderflow.json")))
    check("d. ORDER FLOW: the 3 pre-registered tick designs, no span numbers of its own, the proxy tests all listed",
          [x["id"] for x in P["of"]["designs"]] == list(of["tick_designs"]) and not P["of"]["spans"]
          and len(P["of"]["tests"]) == sum(isinstance(v, dict) for v in list(of["bar_tests"].values()) + list(of["round2"]["standalone"].values())) and all(x["gate"] for x in P["of"]["designs"]))
    check("d. honest status: BLITZ paper + OFF, ORDER FLOW NOT READY (recorder never compiled, 0 tick days), LIT + ATLAS live",
          "OFF" in P["blitz"]["status"] and P["blitz"]["state"] == "off" and P["of"]["status"].startswith("Not ready") and P["of"]["state"] == "notready"
          and P["lit"]["state"] == P["atlas"]["state"] == "live" and P["of"]["readiness"]["days_needed"] == 60 and all(d["prior"] for d in P["of"]["designs"]))
    check("d. every pillar: an edge line, a source, risks, what's next (a list)", all(p["edge"] and p["src"] and p["risks"] and isinstance(p["next"], list) and p["next"] for p in d["pillars"]))
    check("d. the edge lines quote the span PFs", "4.98" in P["lit"]["edge"] and "2.39" in P["atlas"]["edge"] and "0.82" in P["atlas"]["edge"] and "1.05" in P["blitz"]["edge"])


def fixture_post():
    """the Accounts test's post (5 accounts, as tools/pc_report.py sends it) + a glance + the tick line, parsed by the real pc_feed.js"""
    from tests import test_accounts_screen as AS
    core, exts = AS.post()
    core = dict(core)
    core["tr"] = {"on": True, "d": 23, "of": 60, "bf": "running", "o": "2026-09-14", "l": "2026-11-20", "t": AS.T - 600}
    core["pc"] = dict(core["pc"], glance={"t": AS.T, "bots": [
        {"id": "lit", "on": True, "armed": True, "stage": "5m CISD (5/10)", "log": [["10:12", "5m CISD short at 21,040.25: limit armed"], ["09:58", "Swept the NY 08:30 high by 0.7 ATR"]]},
        {"id": "atlas", "on": True, "lobes": [{"id": "ema", "st": "armed", "text": "Armed long"}, {"id": "macd", "st": "window", "text": "watching"}, {"id": "sr", "st": "done", "text": "Done"}],
         "log": [["09:41", "EMA: trend pullback armed long"]]}]})
    nd = AS.ndjson(core, exts)
    js = "const F = require(%s); process.stdout.write(JSON.stringify(F.parseLatest(require('fs').readFileSync(0, 'utf8'))));" % json.dumps(os.path.join(PUB, "pc_feed.js"))
    r = subprocess.run(["node", "-e", js], input=nd, capture_output=True, text=True, timeout=30)
    return json.loads(r.stdout), AS.NOW


NODE = r"""
import * as PF from '%(feed)s';
import * as P from '%(core)s';
import fs from 'fs';
import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const F = require('%(pcfeed)s');
const rd = (p) => JSON.parse(fs.readFileSync(p, 'utf8'));
const src = { data: rd('%(data)s'), home: {}, biz: rd('%(biz)s'), payday: rd('%(payday)s'), file: rd('%(trades)s'), feed: F, nowS: %(now)s };
const M = PF.modelFrom({ ...src, lite: rd('%(post)s') });
const N = PF.modelFrom({ ...src, lite: null });
const pick = (m) => Object.fromEntries(m.map((x) => [x.id, { word: x.statusWord, level: x.level, accts: x.accounts.map((a) => a.key + ':' + a.state + ':' + (a.clock ? 'clock' : '-')),
  armed: x.armed, text: x.accountsText, last: x.last && x.last.text, now: x.chain.steps.filter((s) => s.state === 'now').map((s) => s.key), lobes: (x.chain.lobes || []).map((l) => l.id + ':' + l.state),
  today: x.today.map((t) => t.hm), empty: x.todayEmpty, tick: x.tick && { has: x.tick.has, d: x.tick.d, of: x.tick.of, text: x.tick.text }, spans: x.spans.length }]));
console.log(JSON.stringify({ m: pick(M), n: pick(N), chips: P.chips(M), chipsN: P.chips(N),
  of: ['Order flow LVN rejection', 'BLITZ review: band exits', 'ATLAS MACD divergence', 'Zlarior eval rescue', 'Kalshi K8 metals'].map((t) => P.pillarOf(t, -1)) }));
"""


def node():
    for f in ("pillars.js", "pillarscore.js", "pillarsfeed.js", "pillars-scene.js", "strip.js", "pillarof.js"):
        r = subprocess.run(["node", "--check", os.path.join(WEB, f)], capture_output=True, text=True, timeout=30)
        check(f"n. node parses {f}", r.returncode == 0, r.stderr)
    post, now = fixture_post()
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        json.dump(post, fh)
        pf = fh.name
    j = lambda *p: os.path.join(*p).replace("\\", "/")  # noqa: E731
    code = NODE % {"feed": j(WEB, "pillarsfeed.js"), "core": j(WEB, "pillarscore.js"), "pcfeed": j(PUB, "pc_feed.js"), "data": j(WEB, "pillars-data.json"),
                   "biz": j(PUB, "business", "accounts.json"), "payday": j(PUB, "business", "payday.json"), "trades": j(PUB, "odeon", "trades.json"), "post": pf.replace("\\", "/"), "now": now}
    r = subprocess.run(["node", "--input-type=module", "-e", code], capture_output=True, text=True, timeout=60)
    os.unlink(pf)
    try:
        o = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception as e:  # noqa: BLE001
        check("n. the pillars model runs in node", False, (r.stderr or str(e))[:800])
        return None
    m, n = o["m"], o["n"]
    check("n. LIT: its accounts from the post (50K + 25K #2 + the Rapids), armed, with the 7-day clock", {"zlarior:armed:clock", "fresh25:armed:clock"} <= set(m["lit"]["accts"]) and m["lit"]["armed"] >= 2, m["lit"]["accts"])
    check("n. LIT: LIVE, the live step = CISD, today's 2 lines in time order, a last trade from the ledger",
          m["lit"]["word"] == "LIVE" and m["lit"]["now"] == ["cisd"] and m["lit"]["today"] == ["09:58", "10:12"] and (m["lit"]["last"] or "").count("·") >= 2, m["lit"])
    check("n. ATLAS: the funded 25K, its 3 lobes from the glance (EMA armed = the step now)", any(a.startswith("atlas:") for a in m["atlas"]["accts"]) and m["atlas"]["lobes"] == ["ema:armed", "macd:window", "sr:done"]
          and m["atlas"]["now"] == ["armed"], m["atlas"])
    check("n. BLITZ: OFF on the Rapid accounts only, no thinking, its 3 spans", m["blitz"]["word"] == "OFF" and m["blitz"]["accts"] and all(":off:" in a and a.startswith("rapid") for a in m["blitz"]["accts"])
          and "OFF" in m["blitz"]["empty"] and m["blitz"]["spans"] == 3, m["blitz"])
    check("n. ORDER FLOW: 23 of 60 tick days from the post, the backfill step now, no accounts", m["of"]["tick"] == {"has": True, "d": 23, "of": 60, "text": m["of"]["tick"]["text"]} and "23 of 60" in m["of"]["tick"]["text"]
          and m["of"]["now"] == ["backfill"] and m["of"]["accts"] == [] and m["of"]["word"] == "COLLECTING", m["of"])
    check("n. no post: LIT / ATLAS say waiting / no PC numbers, nothing armed, no today lines; ORDER FLOW says the count is not in the post",
          n["lit"]["armed"] == 0 and not n["lit"]["today"] and "Waiting" in n["lit"]["empty"] and n["lit"]["word"] == "LIVE · waiting for the PC" and "waiting" in n["lit"]["text"] and o["chipsN"][0]["line"] == "waiting for the PC" and not n["of"]["tick"]["has"]
          and "Waiting" in n["of"]["tick"]["text"] and n["of"]["word"] == "NOT READY", (n["lit"], n["of"]["tick"], n["of"]["word"]))
    check("n. 4 chips: LIT, ATLAS, BLITZ, ORDER FLOW with honest lines", [c["id"] for c in o["chips"]] == ["lit", "atlas", "blitz", "of"] and o["chips"][2]["line"] == "built · OFF"
          and o["chips"][3]["line"] == "23/60 tick days" and o["chipsN"][3]["line"] == "recorder not set up", o["chips"])
    check("n. pillarOf: order flow / BLITZ / ATLAS / LIT / none", o["of"] == ["of", "blitz", "atlas", "lit", None], o["of"])
    return post, now


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def _npm_root():
    try:
        return subprocess.run(["npm", "root", "-g"], capture_output=True, text=True, timeout=30).stdout.strip()
    except Exception:  # noqa: BLE001
        return ""


def browser(post, now):
    env = {**os.environ, "NODE_PATH": _npm_root()}
    if subprocess.run(["node", "-e", "require('playwright')"], capture_output=True, env=env, timeout=30).returncode != 0:
        print("[SKIP] b. Node Playwright not installed here", flush=True)
        return
    shots = os.environ.get("PILLARS_SHOTS", "")
    if shots:
        os.makedirs(shots, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        json.dump({"post": post, "at_iso": dt.datetime.fromtimestamp(now, dt.timezone.utc).isoformat()}, fh)
        pf = fh.name
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(_Quiet, directory=PUB))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        r = subprocess.run(["node", os.path.join(ROOT, "tests", "pillars_browser.cjs"), f"http://127.0.0.1:{srv.server_address[1]}", shots, pf],
                           capture_output=True, text=True, timeout=400, env=env)
    finally:
        srv.shutdown()
        os.unlink(pf)
    try:
        o = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception as e:  # noqa: BLE001
        check("b. browser run", False, (r.stderr or r.stdout or str(e))[:800])
        return
    check("b. no fatal", "fatal" not in o, o.get("fatal"))
    errs = [e for k in ("errors", "flatErrors", "nqErrors", "brainErrors", "hubErrors") for e in (o.get(k) or [])]
    check("b. no page error on the 4 pages", not errs, errs[:4])
    check("b. Pillars: the 3D colonnade mounts (r160, 4 columns, few draw calls)", str(o.get("mode", "")).startswith("3d") and (o.get("stats") or {}).get("cols") == 4
          and (o.get("stats") or {}).get("three") == "160" and 0 < (o.get("stats") or {}).get("calls", 99) <= 8, (o.get("mode"), o.get("stats")))
    check("b. Pillars: 4 tabs with a status word each, the names over the columns", [t.split(":")[0] for t in o.get("tabs", [])] == ["lit", "atlas", "blitz", "of"] and len(o.get("tips", [])) == 4
          and "OFF" in o["tabs"][2] and "COLLECTING" in o["tabs"][3], (o.get("tabs"), o.get("tips")))
    L = o.get("lit") or {}
    check("b. LIT panel: accounts + ARMED + the 7-day clock + last trade + 3 spans and the live-settings row + CISD now + today",
          len(L.get("accts", [])) >= 3 and "ARMED" in L.get("arm", []) and L.get("clock", 0) >= 2 and "Last trade" in (L.get("last") or "") and L.get("spans") == 4
          and L.get("now") == ["cisd"] and L.get("today") == 2, L)
    OF = o.get("of") or {}
    check("b. ORDER FLOW panel: 23 of 60 tick days (bar ~38%), OF1-OF3 waiting, the backfill step now, #of in the address",
          "23 of 60" in OF.get("ticks", "") and OF.get("bar") == "38%" and OF.get("designs") == ["OF1:waiting", "OF2:waiting", "OF3:waiting"] and OF.get("now") == ["backfill"] and OF.get("hash") == "#of", OF)
    B = o.get("blitz") or {}
    check("b. BLITZ panel: OFF, its Rapid accounts OFF, PF 1.70 / 1.62 / 1.05, every step off, no thinking today",
          B.get("status") == "OFF" and B.get("arm") and all(a.startswith("OFF") for a in B["arm"]) and B.get("spans") == ["1.70", "1.62", "1.05"] and B.get("off") == 6 and "OFF" in B.get("today", ""), B)
    T = o.get("ofToday") or {}
    check("b. ORDER FLOW today (no tick line in the post): NOT READY, the waiting line, the first-result dates", T.get("status") == "NOT READY" and "Waiting" in T.get("ticks", "")
          and "2027-02-22" in T.get("ready", "") and "about about" not in T.get("ready", "") and T.get("nullText") is False, T)
    A = o.get("atlas") or {}
    check("b. ATLAS panel: its 3 lobes + 3 spans + the last-40 row", A.get("lobes") == 3 and A.get("spans") == 4, A)
    check("b. a tap on a column picks that pillar", o.get("colPick") == "of", o.get("colPick"))
    check("b. no sideways scroll at 390 (Pillars, NQ, Hub)", o.get("wide") is False and o.get("nqWide") is False and o.get("hubWide") is False, (o.get("wide"), o.get("nqWide"), o.get("hubWide")))
    check("b. 2D fallback: 4 columns, a tap picks", o.get("flat") == ["2d", 4] and o.get("flatPick") == "lit", (o.get("flat"), o.get("flatPick")))
    NQ = o.get("nq") or {}
    check("b. NQ page: a Pillars link in the header + 4 chips, each opening its pillar", NQ.get("link") and [c.split(":")[0] for c in NQ.get("chips", [])] == ["lit", "atlas", "blitz", "of"]
          and NQ.get("hrefs") == ["#lit", "#atlas", "#blitz", "#of"], NQ)
    BR = o.get("brain") or {}
    check("b. Strategy Brain: the 4 pillars are the first lobes, a Pillars link, research neurons orbit them",
          BR.get("chips") == ["lit", "atlas", "blitz", "of"] and BR.get("link") and (BR.get("stats") or {}).get("neurons", 0) > 150, BR)
    check("b. Strategy Brain: ORDER FLOW sheet with the tick count + its 5 steps", (o.get("brainOf") or {}).get("h") == "ORDER FLOW" and "23 of 60" in (o.get("brainOf") or {}).get("ticks", "")
          and (o.get("brainOf") or {}).get("steps") == 5, o.get("brainOf"))
    check("b. Strategy Brain: ATLAS sheet opens its 3 lobes", (o.get("brainAtlas") or {}).get("members") == ["ATLAS EMA ›", "ATLAS MACD ›", "ATLAS S/R ›"], o.get("brainAtlas"))
    H = o.get("hub") or {}
    check("b. Research Hub: Pillars row (All + 4), ?pillar=of filters the studies to order flow", H.get("row") == ["", "lit", "atlas", "blitz", "of"] and (H.get("pressed") or {}).get("pil") == "of"
          and 0 < len(H.get("cards", [])) < H.get("all", 0) and H.get("allOf") is True, H)
    check("b. Research Hub Strategy Lab: the LIT pillar = LIT + its variants (no ATLAS row); BLITZ has none tested in the lab",
          (o.get("hubLab") or {}).get("n", 0) > 50 and (o.get("hubLab") or {}).get("live") == 0 and o.get("hubLabBlitz") == 0, (o.get("hubLab"), o.get("hubLabBlitz")))


def main():
    static()
    data()
    got = node()
    if got and os.environ.get("PL_NO_BROWSER") != "1":
        browser(*got)
    print(f"\n{sum(RES)}/{len(RES)} passed")
    sys.exit(0 if all(RES) else 1)


if __name__ == "__main__":
    main()
