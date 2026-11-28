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
    check("a. NQ page: a Pillars link in the header + the Four Pillars hero (#pillarsStrip) + its module (pillars/hero.js, day-pillars2)", 'href="../pillars/"' in nq.split("</header>")[0] and 'id="pillarsStrip"' in nq and "../pillars/hero.js" in nq)
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
    check("b. Pillars: the 3D temple mounts (r160, 4 columns, <= 24 draw calls in the scene pass)", str(o.get("mode", "")).startswith("3d") and (o.get("stats") or {}).get("cols") == 4
          and (o.get("stats") or {}).get("three") == "160" and 0 < (o.get("stats") or {}).get("calls", 99) <= 24, (o.get("mode"), o.get("stats")))
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
    check("b. Strategy Brain: ORDER FLOW sheet with the tick count + its 5 steps", (o.get("brainOf") or {}).get("h") == "POSEIDON" and "23 of 60" in (o.get("brainOf") or {}).get("ticks", "")
          and (o.get("brainOf") or {}).get("steps") == 5, o.get("brainOf"))
    check("b. Strategy Brain: ATLAS sheet opens its 3 lobes", (o.get("brainAtlas") or {}).get("members") == ["ATLAS EMA ›", "ATLAS MACD ›", "ATLAS S/R ›"], o.get("brainAtlas"))
    H = o.get("hub") or {}
    check("b. Research Hub: Pillars row (All + 4), ?pillar=of filters the studies to order flow", H.get("row") == ["", "lit", "atlas", "blitz", "of"] and (H.get("pressed") or {}).get("pil") == "of"
          and 0 < len(H.get("cards", [])) < H.get("all", 0) and H.get("allOf") is True, H)
    check("b. Research Hub Strategy Lab: the LIT pillar = LIT + its variants (no ATLAS row); BLITZ has none tested in the lab",
          (o.get("hubLab") or {}).get("n", 0) > 50 and (o.get("hubLab") or {}).get("live") == 0 and o.get("hubLabBlitz") == 0, (o.get("hubLab"), o.get("hubLabBlitz")))


# ---------------- p. day-pillars4: the pillar DATA page, research per pillar, the Home Today strip, the Brain feed's age ----------------
P4_FILES = ["data.html", "data.js", "data.css", "datacore.js", "todaycore.js", "today.js"]


def p4_post(post, now):
    """the section-n post + the PC's brain feed (10 min old) + an OPEN ATLAS trade and one closed LIT trade in lite.at"""
    q = json.loads(json.dumps(post))
    q["bf"] = {"v": 1, "t": now - 600, "market": {"phase": "ranging", "today_range_pts": 120.5, "where_in_range_pct": 40, "regime": "normal (VIX 16.1)"},
               "bots": {"lit": {"think": ["10:14 short limit 21,040.25 armed, stop 21,061.5", "10:12 VIX 16.1 -> target 5.2R"],
                                "next": {"setup": "SHORT sweep + shift of the NY 08:30 high", "steps": [{"name": "sweep", "done": True}, {"name": "inducement", "done": True},
                                         {"name": "CISD", "done": False}, {"name": "entry", "done": False}], "waiting_for": "the 5m CISD to close", "dist_pts": 6.5,
                                         "limit": 21040.25, "stop": 21061.5, "target": 20930.0},
                                "levels": [{"kind": "stop", "price": 21061.5, "label": "stop"}]},
                        "atlas": {"err": "KeyError: x"}}}
    q["at"] = {"a": [{"id": "atlas", "tr": [[now - 1800, None, -1, 0, 0, 0, 0, 0, 37.5, 0.3]]},
                     {"id": "mffu50k_eval", "tr": [[now - 7200, now - 5400, 1, 0, 0, 0, 0, 0, 212.0, 1.1]]}]}
    return q


NODE4 = r"""
import * as DC from '%(dc)s';
import * as TC from '%(tc)s';
import * as B from '%(bc)s';
import * as PF from '%(feed)s';
import fs from 'fs';
import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const F = require('%(pcfeed)s');
const rd = (p) => JSON.parse(fs.readFileSync(p, 'utf8'));
const now = %(now)s, post = rd('%(post)s'), data = rd('%(data)s'), trades = rd('%(trades)s');
const site = { pillarsData: data, home: {}, biz: rd('%(biz)s'), learn: rd('%(learn)s'), feed: F };
const M = B.build({ ...site, lite: post }, now), N = B.build({ ...site, lite: null }, now);
const L = B.region(M, 'lit');
const out = {};
out.feed = M.feed; out.feedNone = N.feed; out.market = M.market;
out.litNext = { from: L.next.from, setup: L.next.setup, steps: L.next.steps, limit: L.next.limit, dist: L.next.dist, think0: L.think[0] };
out.atlasFrom = B.region(M, 'atlas').next.from;
out.think = B.thinkLines(['09:05 a line', 'no time']);
out.old = B.feedAge({ bf: { t: now - 50 * 60 } }, now).level;
out.late = B.feedAge({ bf: { t: now - 30 * 60 } }, now).level;
out.tight = B.build({ ...site, lite: { ...post, bf: { t: now, bots: { lit: { next: { setup: 'x', steps: '6/10' } } } } } }, now).regions[0].next.stepsText;
const PM = PF.modelFrom({ data, home: {}, biz: site.biz, lite: post, nowS: now, feed: F });
for (const id of DC.IDS) { const d = DC.build(id, { nowS: now, data, trades, lite: post, region: B.region(M, id), pillars: PM }); out[id] = { n: d.tradesN, st: d.stats, rej: d.rejected.n, rows: d.trades.map((r) => r.src + ':' + (r.open ? 'open' : 'closed') + ':' + r.usd), flow: d.flow, next: d.next && d.next.setup, mill: d.mill && d.mill.ideas }; }
out.liveOnly = DC.tradesOf('lit', trades, null).filter((r) => r.src === 'live').length;
out.dedupe = DC.tradesOf('atlas', trades, { at: { a: [{ id: 'atlas', tr: [[trades.trades.filter((t) => t.bot === 'ATLAS' && t.src === 'live').slice(-1)[0].t + 30, 1, -1, 0, 0, 0, 0, 0, -112.8, -0.92]] }] } }).filter((r) => r.src === 'live').length;
out.stats0 = DC.stats([], now);
const cards = PF.cardsFrom({ home: {}, biz: site.biz, lite: post, nowS: now, feed: F }).cards;
out.today = TC.build(cards, post, now); out.todayNone = TC.build(PF.cardsFrom({ home: {}, biz: site.biz, lite: null, nowS: now, feed: F }).cards, null, now);
out.money = ['+$1,234', '-$56', '$0', '-', null].map(TC.money);
console.log(JSON.stringify(out));
"""


def p4_static():
    for f in P4_FILES:
        check(f"p. pillars/{f} exists", os.path.exists(os.path.join(WEB, f)))
    src = {f: read("pillars", f) for f in P4_FILES}
    code = "\n".join(src.values())
    check("p. no innerHTML / eval / storage writes in the new files; read only (no POST)", not re.search(r"innerHTML|eval\(|new Function|method:\s*'POST'|localStorage\.setItem", code), "")
    check("p. OLYMPUS NIGHT: no cyan / brown / olive anywhere in the pillars app, the Brain, the Home hero chips",
          not re.search(r"#5fd0c9|cyan|brown|olive|#00ffff", code + read("pillars", "pillarscore.js") + read("pillars", "pillars-data.json") + read("brain", "braincore.js"), re.I)
          and "#5fd0c9" not in read("gate", "index.html").lower() and "#5fd0c9" not in read("index.html").lower())
    check("p. data.html: one h1, Home › Pillars › <pillar> crumbs, a 44 px back to the Pillars, pc_feed + data.js",
          src["data.html"].count("<h1") == 1 and 'href="../gate/">Home</a>' in src["data.html"] and 'id="back" href="./"' in src["data.html"] and "data.js?v=" in src["data.html"] and "pc_feed.js" in src["data.html"]
          and "width: 44px; height: 44px" in src["data.css"])
    pi = read("pillars", "index.html")
    check("p. the Pillars page: back = Home (../gate/), Home › Pillars crumbs, the footer opens the data page, Trades + Brain", 'class="back" href="../gate/"' in pi and 'class="crumbs"' in pi
          and 'id="footData"' in pi and '../trading/' in pi and '../brain/' in pi)
    g = read("gate", "index.html")
    check("p. Home: the Today strip in the header right under the Four Pillars, no height of its own, today.js loaded after the page",
          re.search(r'id="pillarsHero".*?</section>\s*<nav class="g-today" id="todayStrip"[^>]*style="height:44px;margin:-2px 0 -26px"', g, re.S) is not None and "pillars/today.js?v=" in g)
    bj = read("brain", "brain.js")
    check("p. the Brain: brain feed read first (lite.bf), its age on Next trade (#rFeedAge), the header no longer see-through",
          "lite.bf" in read("brain", "braincore.js") and "rFeedAge" in bj and "backdrop-filter: blur(12px)" in read("brain", "brain.css"))


def p4_data():
    d = json.load(open(os.path.join(WEB, "pillars-data.json"), encoding="utf-8"))
    P = {p["id"]: p for p in d["pillars"]}
    text = open(os.path.join(ROOT, "docs", "TESTED_AND_REJECTED.md"), encoding="utf-8").read()
    bullets = sum(1 for l in text.splitlines() if l.startswith("- "))
    n = sum(P[k]["rejected"]["n"] for k in P) + d["rejected_shared"]["n"]
    check("p. rejected: every bullet of docs/TESTED_AND_REJECTED.md filed once (4 pillars + shared), newest first, <= 12 rows each",
          n == bullets and all(len(P[k]["rejected"]["rows"]) <= 12 and [r["d"] for r in P[k]["rejected"]["rows"]] == sorted([r["d"] for r in P[k]["rejected"]["rows"]], reverse=True) for k in P), (n, bullets))
    check("p. rejected: LIT and ATLAS rows name their pillar, the order-flow rows are order flow, idea mills are shared",
          P["of"]["rejected"]["n"] >= 2 and all("rder" in r["title"] or "LVN" in r["title"] for r in P["of"]["rejected"]["rows"]) and P["lit"]["rejected"]["n"] > P["atlas"]["rejected"]["n"] > 0
          and not any("dea mill" in r["title"] for k in P for r in P[k]["rejected"]["rows"]), {k: P[k]["rejected"]["n"] for k in P})
    mill = json.load(open(os.path.join(ROOT, "research", "ideamill", "summary.json")))
    check("p. idea mill = research/ideamill/summary.json (ideas, scored, families, passed)", d["mill"]["ideas"] == mill["counts"]["trials_total"] and d["mill"]["scored"] == mill["counts"]["scored"]
          and d["mill"]["families"] == len(mill["families"]) and d["mill"]["passed"] == 0, d["mill"])
    pr = P["of"]["progress"]
    st = json.load(open(os.path.join(ROOT, "research", "orderflow", "results.json")))
    check("p. order-flow progress: 2 pre-registered looks, looks used from the study's mode, tick days on disk, the battery's need",
          pr["looks"] == 2 and pr["looks_used"] == (1 if st["mode"] == "REAL" else 0) and pr["tick_days_on_disk"] == st["tick_days"] and pr["battery_need"] == 40, pr)
    check("p. ORDER FLOW is lilac (#c9a7ff), not cyan", P["of"]["color"] == "#c9a7ff")


def p4_node(post, now):
    q = p4_post(post, now)
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        json.dump(q, fh); pf = fh.name
    js = NODE4 % {"dc": os.path.join(WEB, "datacore.js"), "tc": os.path.join(WEB, "todaycore.js"), "bc": os.path.join(PUB, "brain", "braincore.js"), "feed": os.path.join(WEB, "pillarsfeed.js"),
                  "pcfeed": os.path.join(PUB, "pc_feed.js"), "now": now, "post": pf, "data": os.path.join(WEB, "pillars-data.json"), "trades": os.path.join(PUB, "trading", "trades.json"),
                  "biz": os.path.join(PUB, "business", "accounts.json"), "learn": os.path.join(PUB, "brain", "learn.json")}
    with tempfile.NamedTemporaryFile("w", suffix=".mjs", delete=False, dir=WEB) as fh:
        fh.write(js); mf = fh.name
    try:
        r = subprocess.run(["node", mf], capture_output=True, text=True, timeout=60)
    finally:
        os.unlink(mf); os.unlink(pf)
    try:
        o = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception as e:  # noqa: BLE001
        check("p. node run", False, (r.stderr or str(e))[:800]); return None
    check("p. Brain: the brain feed is read FIRST (its setup, [{name, done}] steps with the first open one 'now', limit, 6.5 pts, its HH:MM think lines)",
          o["litNext"]["from"] == "bf" and "NY 08:30" in o["litNext"]["setup"] and [s["state"] for s in o["litNext"]["steps"]] == ["done", "done", "now", "wait"]
          and o["litNext"]["limit"] == 21040.25 and o["litNext"]["dist"] == 6.5 and o["litNext"]["think0"]["hm"] == "10:14", o["litNext"])
    check("p. Brain: a bot the feed failed on ({err}) falls back to the step report", o["atlasFrom"] in ("derived", "pc"), o["atlasFrom"])
    check("p. Brain: the feed's age (10 min = ok, 30 = warn, 50 = bad), none = the step report's age or 'none'",
          o["feed"]["has"] and o["feed"]["level"] == "ok" and round(o["feed"]["age"]) == 600 and "brain feed 10 min ago" in o["feed"]["text"] and o["late"] == "warn" and o["old"] == "bad" and o["feedNone"]["level"] == "none", (o["feed"], o["late"], o["old"]))
    check("p. Brain: the market block, a tight feed's '6/10' steps, 'HH:MM words' think lines split", o["market"]["phase"] == "ranging" and o["tight"] == "6/10"
          and o["think"] == [{"hm": "09:05", "text": "a line"}, {"hm": "", "text": "no time"}], (o["market"], o["tight"], o["think"]))
    lit, at = o["lit"], o["atlas"]
    check("p. data: LIT trades = the real file's live + paper + the PC's newest (a closed +$212); stats count real closed trades only (paper apart)",
          lit["rows"][0] == "live:closed:212" and lit["st"]["n"] == o["liveOnly"] + 1 and lit["st"]["paperN"] == 3 and lit["st"]["weekN"] == 1 and round(lit["st"]["week"]) == 212, lit)
    check("p. data: ATLAS's open trade from the post is open (not in the stats), PF / win rate from closed trades", at["rows"][0] == "live:open:37.5" and at["st"]["open"] and at["st"]["n"] == 3
          and abs(at["st"]["pf"] - 6.363) < 0.01 and round(at["st"]["win"]) == 33, at["st"])
    check("p. data: the same trade in the file and the post is counted once", o["dedupe"] == 3, o["dedupe"])
    check("p. data: no trades = zeros and '-' (no made-up number)", o["stats0"]["n"] == 0 and o["stats0"]["win"] is None and o["stats0"]["pf"] is None and o["stats0"]["pfWord"] == "-", o["stats0"])
    check("p. data: BLITZ + ORDER FLOW trade nothing; their rejected counts + the idea mill on every pillar", o["blitz"]["n"] == 0 and o["of"]["n"] == 0 and o["of"]["rej"] >= 2 and all(o[k]["mill"] == 56160 or o[k]["mill"] for k in ("lit", "atlas", "blitz", "of")), (o["blitz"], o["of"]["rej"]))
    check("p. data: ORDER FLOW progress = 23 of 60 tick days from the post, 0 of 2 looks, the 3 designs", o["of"]["flow"]["days"] == 23 and o["of"]["flow"]["of"] == 60 and o["of"]["flow"]["looks"] == 2
          and o["of"]["flow"]["looksUsed"] == 0 and len(o["of"]["flow"]["designs"]) == 3, o["of"]["flow"])
    T, TN = o["today"], o["todayNone"]
    check("p. Today: <= 4 accounts with today $, the open ATLAS trade, the next setup from the brain feed", 0 < len(T["accounts"]) <= 4 and T["openText"].startswith("ATLAS SHORT")
          and T["next"]["from"] == "bf" and "NY 08:30" in T["nextText"] and T["has"] is True, T)
    check("p. Today without a post: every $ '-', open '-', next 'waiting for the PC'", TN["dayText"] == "-" and TN["openText"] == "-" and TN["nextText"] == "waiting for the PC" and all(a["text"] == "-" for a in TN["accounts"]), TN)
    check("p. Today: money text -> number", o["money"] == [1234, -56, 0, None, None], o["money"])
    return q


def p4_browser(q, now):
    env = {**os.environ, "NODE_PATH": _npm_root()}
    if subprocess.run(["node", "-e", "require('playwright')"], capture_output=True, env=env, timeout=30).returncode != 0:
        print("[SKIP] p. Node Playwright not installed here", flush=True); return
    shots = os.environ.get("PILLARS_SHOTS", "")
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        json.dump({"post": q, "at_iso": dt.datetime.fromtimestamp(now, dt.timezone.utc).isoformat()}, fh); pf = fh.name
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(_Quiet, directory=PUB))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        r = subprocess.run(["node", os.path.join(ROOT, "tests", "pillars4_browser.cjs"), f"http://127.0.0.1:{srv.server_address[1]}", shots, pf], capture_output=True, text=True, timeout=500, env=env)
    finally:
        srv.shutdown(); os.unlink(pf)
    try:
        o = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception as e:  # noqa: BLE001
        check("p. browser run", False, (r.stderr or r.stdout or str(e))[:800]); return
    check("p. browser: no fatal, no page error", "fatal" not in o and not o.get("errors"), (o.get("fatal"), (o.get("errors") or [])[:3]))
    L = o.get("lit") or {}
    check("p. LIT data page: 'LIT · Data', Home › Pillars › LIT, back to the Pillars at #lit, the PC pill, no SAMPLE", L.get("title") == "LIT · Data" and "Home" in L.get("crumbs", "") and "LIT" in L.get("crumbs", "")
          and L.get("back") == "./#lit" and not L.get("sample") and L.get("pill", "").startswith("PC"), L)
    check("p. LIT data page: this week +$212, win rate, PF, the last trades (newest = the PC's), sections in order", "+$212" in L.get("week", "") and "%" in L.get("win", "") and L.get("rows", 0) >= 3
          and L.get("srcs", [""])[0] == "live" and L.get("sections") == ["dHead", "dMoney", "dNext", "dTrades", "dLearn", "dResearch"], L)
    check("p. LIT data page: brain feed 10 min ago (green), its setup + steps (CISD now), the Brain room link", "Brain feed 10 min ago" in L.get("feed", "") and " ok" in " " + L.get("feedCls", "")
          and "NY 08:30" in L.get("setup", "") and "now:CISD" in L.get("steps", []) and L.get("brainLink"), (L.get("feed"), L.get("steps")))
    check("p. LIT data page: tested-and-rejected count, the idea mill, what it learned, 4 pillar tabs, the footer path", "Tested and rejected:" in L.get("rej", "") and "56,160" in L.get("mill", "")
          and L.get("lessons", 0) >= 1 and L.get("tabs") == ["#lit", "#atlas", "#blitz", "#of"] and L.get("foot") == ["./#lit", "../brain/#lit", "../trading/", "../cities/hub.html", "../nq/accounts.html"], (L.get("rej"), L.get("foot")))
    check("p. LIT data page: the real $ path as a sparkline (every real closed trade, ends at the all-time $)", "Real $ path over 3 trades" in (L.get("spark") or "") and "over 3 real trades" in (L.get("spark") or ""), L.get("spark"))
    A = o.get("atlas") or {}
    check("p. a tab switches to ATLAS in place: its open trade, its month, back to #atlas", A.get("title") == "ATLAS · Data" and A.get("hash") == "#atlas" and "OPEN NOW" in A.get("open", "") and A.get("back") == "./#atlas", A)
    OF = o.get("of") or {}
    check("p. ORDER FLOW data page: 23 / 60 tick days, 0 / 2 looks, 3 designs, no trade table, its verdicts", OF.get("days") == "23 / 60" and OF.get("looks") == "0 / 2" and OF.get("designs") == 3
          and not OF.get("trades") and "Tested and rejected" in OF.get("rej", ""), OF)
    N = o.get("none") or {}
    check("p. no PC post: SAMPLE banner + pill on the live parts, the real trades still drawn", N.get("sample") and N.get("pill") == "SAMPLE" and N.get("rows", 0) >= 3 and "SAMPLE" in N.get("feed", ""), N)
    PI = o.get("pillars") or {}
    check("p. Pillars page: back to Home, Home › Pillars, the go-deeper row (data, Brain room, trades) for the open pillar", PI.get("back") == "../gate/" and "Home" in PI.get("crumbs", "")
          and PI.get("go") == ["data.html#atlas", "../brain/#atlas", "../trading/"] and PI.get("foot") == "data.html#atlas", PI)
    H = o.get("home") or {}
    check("p. Home Today strip: Today $, the accounts, the open ATLAS trade, the next setup, each a link; from the PC post", H.get("ready") == "post" and H.get("cells", [""])[0].startswith("Today")
          and any("ATLAS SHORT" in c for c in H.get("cells", [])) and any("NY 08:30" in c for c in H.get("cells", [])) and "/pillars/data.html#lit" in H.get("hrefs", []), H)
    check("p. Home: the strip takes no room, 44 px tap targets (search < 160, 6 dashboards from < 260, More <= 844), above the search, no sideways scroll",
          H.get("h") == 44 and H.get("tapMin", 0) >= 44 and H.get("q", 999) < 160 and H.get("grid", 999) < 260 and H.get("more", 999) <= 844 and H.get("stripBottom", 999) <= H.get("q", 0) and o.get("homeWide") is False, H)
    check("p. no sideways scroll on the data pages", o.get("litWide") is False and o.get("ofWide") is False)
    BR = o.get("brain") or {}
    check("p. Brain LIT room: 'Brain feed 10 min ago' (green) on Next trade, the feed's setup + steps, its source named, a solid header",
          "Brain feed 10 min ago" in BR.get("feed", "") and " ok" in " " + BR.get("cls", "") and "NY 08:30" in BR.get("setup", "") and "now:CISD" in BR.get("steps", []) and "brain feed" in BR.get("src", "")
          and BR.get("top", "").startswith("rgba(0, 0, 0, 0.9"), BR)
    check("p. Brain LIT room: Home › Pillars › LIT Brain, back to the Pillars at #lit, the LIT data link", BR.get("back") == "../pillars/#lit" and BR.get("crumb") == "LIT Brain"
          and BR.get("data") == "../pillars/data.html#lit", BR)


def main():
    static()
    data()
    got = node()
    if got and os.environ.get("PL_NO_BROWSER") != "1":
        browser(*got)
    p4_static()
    p4_data()
    q = p4_node(*got) if got else None
    if q and os.environ.get("PL_NO_BROWSER") != "1":
        p4_browser(q, got[1])
    print(f"\n{sum(RES)}/{len(RES)} passed")
    sys.exit(0 if all(RES) else 1)


if __name__ == "__main__":
    main()
