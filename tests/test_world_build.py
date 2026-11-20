"""OLYMPUS WORLD builder (tools/world_build.py -> tools/web_public/cities/world/world.json, night-worlds 2026-11-19): the repo's data as ONE
giant city ("all cities should be in one giant city, just different areas for like 1) Kalshi, 2) NQ etc."). No browser.

  a. the real build: four districts = the four doors (olympus/doors.js), every app of olympus/apps-list.js is a building with its own link,
     hundreds of learning places from the Lab, the Archive, Data City, Kalshi (K8 too), the accounts and the bots; their states follow the data
  b. the plan: every place has street cells, no cell is used twice, the cells sit in their district's wedge outside the plaza, the city is round
  c. learning: a new Lab idea appears at its quarter's edge and the old places keep their spots; rejected = ruins, adopted runs = bright
  d. privacy and the hidden bots: no PC account ids, no e-mail, no 'last 4'; BLITZ (hidden by dashboard_view.json) never appears
  e. the file: deterministic, compact (< 300 KB), the shipped world.json is the tool's output shape; --check writes nothing
  f. the page's core in node (ow-core.js): planWorld (thousands of instances, finite, deterministic, fewer on low), poses, picking,
     labels that never overlap, the live overlay (a bot in a trade, the Board's events in fixed words only), search
    python -X utf8 -m tests.test_world_build
"""
from __future__ import annotations

import copy
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import world_build as WB  # noqa: E402

RES = []
WORLD_DIR = os.path.join(ROOT, "tools", "web_public", "cities", "world")


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:600]}"), flush=True)


def strip(w):
    w = copy.deepcopy(w)
    w.pop("built", None)
    w.pop("days", None)
    return w


def test_build():
    w = WB.build()
    ps = w["places"]
    ids = [p["id"] for p in ps]
    check("a. a world: v2 'olympus-world', four districts in door order (ZEUS Trading, Kalshi, More, Money), every district has apps",
          w["v"] == 2 and w["kind"] == "olympus-world" and [d["id"] for d in w["districts"]] == ["zeus", "kalshi", "more", "money"] and all(d["apps"] > 0 for d in w["districts"]),
          [(d["id"], d["apps"]) for d in w["districts"]])
    check("a. hundreds of places (> 300), unique ids, 4,000+ real tests as buildings", len(ps) > 300 and len(set(ids)) == len(ids) and w["counts"]["buildings"] >= 4000, (len(ps), w["counts"]))
    rows = WB.apps_list()
    hrefs = {p.get("href") for p in ps if p["kind"] == "app"}
    missing = [r["id"] for r in rows if (r.get("path") or "index.html") not in hrefs]
    check("a. every app of apps-list.js is a building that opens its own page (%d apps)" % len(rows), rows and not missing, missing)
    doors = {dd["id"]: dd for dd in WB.doors()}
    wrong = [p["id"] for p in ps if p["kind"] == "app" and p["id"].startswith("app:") and p["id"][4:] in {i for dd in doors.values() for i in dd["ids"]}
             and p["district"] != next(k for k, dd in doors.items() if p["id"][4:] in dd["ids"])]
    check("a. each app sits in the district of its door (doors.js is the one filing): Kalshi apps in Kalshi, Mint in Money, Data City in More",
          not wrong and next(p for p in ps if p["id"] == "app:kalshicity")["district"] == "kalshi" and next(p for p in ps if p["id"] == "app:mintcity")["district"] == "money"
          and next(p for p in ps if p["id"] == "app:datacity")["district"] == "more", wrong)
    shortcut = [p["name"] for p in ps if p["kind"] == "app" and p["district"] == "zeus"][:8]
    check("a. ZEUS Trading's downtown starts with the owner's own shortcuts, plain names first (My accounts, Bots right now, ...)", shortcut[:2] == ["My accounts", "Bots right now"], shortcut)
    extra = {p["href"] for p in ps if p["kind"] == "app"}
    check("a. the NQ district also has the ZEUS home, the MFFU center, the Lab page and Atlas City", {"hub/zeus.html", "business/mffu.html", "business/lab.html", "atlascity/"} <= extra)
    by = {p["id"]: p for p in ps}
    check("a. the live bots are in the NQ core: Zlarior (one building per 2026 trade: 120+) and ATLAS, both live, with $ a month on their cards",
          by.get("bot:lit", {}).get("district") == "zeus" and len(by["bot:lit"]["b"]) // 3 >= 120 and by["bot:lit"]["state"] == "live" and "bot:atlas" in by
          and any("a month" in v for _, v in by["bot:lit"]["facts"]) and any("$" in v for _, v in by["bot:atlas"]["facts"]), by.get("bot:lit", {}).get("facts"))
    accts = [p for p in ps if p["kind"] == "account"]
    check("a. the MFFU accounts are vault towers in the NQ core, named with their size and stage (Zlarior 50K (eval), ATLAS 25K (funded), ...), the planned one is scaffolding",
          len(accts) >= 3 and all(p["quarter"] == "core" for p in accts) and any(p["name"] == "Zlarior 50K (eval)" for p in accts) and any(p["name"] == "ATLAS 25K (funded)" for p in accts)
          and any(p["state"] == "planned" for p in accts) and all(re.search(r"\d+K", p["name"]) for p in accts), [p["name"] for p in accts])
    lab = [p for p in ps if p["quarter"] == "lab"]
    L = WB.load("tools/web_public/business/lab.json", {})
    rej = [r["id"] for r in L.get("rows") or [] if r.get("status") == "rejected" and r.get("bot") in ("lit", "atlas")]
    check("a. every ZEUS Lab idea is a place in the NQ Lab quarter; a rejected one is a ruin (all its buildings state 0), its card says the $ it changed",
          len(lab) >= len(rej) and all(by["lab:" + i]["state"] == "ruin" and set(by["lab:" + i]["b"][1::3]) == {0} for i in rej)
          and all(any("a month vs today" in v for _, v in by["lab:" + i]["facts"]) for i in rej if any(k.startswith("Jan") for k, _ in by["lab:" + i]["facts"])), len(lab))
    res = [p for p in ps if p["kind"] == "research"]
    runs = sum(len(p["b"]) // 3 for p in res)
    check("a. the Archive's stored backtests are buildings of research places (2,000+), adopted runs bright (3), rejected ones ruins (0)",
          runs >= 2000 and any(3 in p["b"][1::3] for p in res) and sum(p["b"][1::3].count(0) for p in res) > 1000, runs)
    k = [p for p in ps if p["district"] == "kalshi"]
    check("a. the Kalshi district: its door's apps (one tower each), the bets studied (strategies, markets, bands, hypotheses), the K8 gold & silver legs and the Kalshi write-ups",
          sum(1 for p in k if p["kind"] == "app") >= len({it["href"] for dd in WB.doors() if dd["id"] == "kalshi" for it in dd["items"]}) and any(p["quarter"] == "kbets" for p in k) and any(p["id"].startswith("k8:") for p in k)
          and any(p["quarter"] == "kresearch" for p in k), sorted({p["quarter"] for p in k}))
    k8 = next((p for p in k if p["id"] == "k8:a-gold"), None)
    check("a. a K8 leg's card: bets and $ on the months it was learned on and checked on", k8 is not None and any("bets" in v and "$" in v for _, v in k8["facts"]), k8 and k8["facts"])
    dc = [p for p in ps if p["quarter"] == "datacity"]
    check("a. Data City's nine quarters live in More next to the Data City app, one building per tested combo (1,000+)", len(dc) == 9 and sum(len(p["b"]) // 3 for p in dc) >= 1000, len(dc))
    dec = [p for p in ps if p["quarter"] == "decisions"]
    n_open = sum(1 for x in (WB.load("tools/web_public/business/decisions.json", {}) or {}).get("items") or [] if isinstance(x, dict) and x.get("id") and str(x.get("status") or "open") == "open")
    check("a. Money: the open decisions waiting for a yes (only those: an answered one is no longer a place) are scaffolding with a link to the Board (%d open)" % n_open,
          len(dec) == n_open and all(p["state"] == "planned" and p.get("href") == "board/" for p in dec), len(dec))
    check("a. every card is plain words: a name, a one-line 'what it is', facts, a 'how to read it' line; no markup", all(p["name"] and p["line"] and isinstance(p["facts"], list) and isinstance(p["how"], int) for p in ps)
          and not re.search(r"<[a-z/]", json.dumps(w)), "")
    feed = w["feed"]
    check("a. the learning feed: newest first, dated, each line points at a place (or none), at most 48", 0 < len(feed) <= 48 and all(feed[i]["d"] >= feed[i + 1]["d"] for i in range(len(feed) - 1))
          and all(f["id"] is None or f["id"] in by for f in feed), feed[:3])
    return w


def test_plan(w):
    ps = w["places"]
    C, PL, R = w["cell"], w["plaza"], w["R"]
    used = {}
    dup = []
    for p in ps:
        for c in p["cells"]:
            k = tuple(c)
            if k in used:
                dup.append((k, used[k], p["id"]))
            used[k] = p["id"]
    check("b. every place has street cells, never shared (%d cells used)" % len(used), all(p["cells"] for p in ps) and not dup, dup[:3])
    out = [p["id"] for p in ps for c in p["cells"] if math.hypot(c[0] * C, c[1] * C) < PL - 1e-6 or math.hypot(c[0] * C, c[1] * C) > R + 1e-6]
    check("b. no cell on the plaza, none beyond the city radius (R = %.0f)" % R, not out, out[:3])
    D = {d["id"]: d for d in w["districts"]}
    bad = []
    for p in ps:
        d = D[p["district"]]
        for c in p["cells"]:
            if not WB.in_arc(math.atan2(c[1] * C, c[0] * C), d["a0"] - 1e-6, d["a1"] + 1e-6):
                bad.append(p["id"])
                break
    check("b. each place's cells lie in its district's wedge (the districts are real areas of one city)", not bad, bad[:4])
    spans = [((d["a1"] - d["a0"]) % (2 * math.pi)) for d in w["districts"]]
    check("b. the four wedges cover the whole circle; ZEUS Trading (the most to learn) is the biggest and faces north (the first view)",
          abs(sum(spans) - 2 * math.pi) < 1e-3 and spans[0] == max(spans) and math.sin((w["districts"][0]["a0"] + w["districts"][0]["a1"]) / 2) < -0.9, [round(math.degrees(s)) for s in spans])
    near = {}
    for p in ps:
        near.setdefault(p["district"], []).append((math.hypot(p["x"], p["z"]), p["kind"]))
    ok = all(min(r for r, k in v if k == "app") <= min(r for r, k in v if k != "app") + C * 1.5 for v in near.values() if any(k == "app" for _, k in v) and any(k != "app" for _, k in v))
    check("b. downtown first: in every district the app towers stand closest to the plaza, the learning quarters further out", ok, {k: sorted(v)[:3] for k, v in near.items()})
    fl = w["filler"]
    check("b. the city fabric: free cells inside the city become blocks of buildings (levels 1-9, a few parks), and a ragged ring of outskirts",
          len(fl) > 200 and all(0 <= f[2] <= 9 for f in fl) and any(f[2] == 0 for f in fl) and not any(tuple(f[:2]) in used for f in fl), len(fl))


def test_learning(w0):
    src = WB.load
    lab = WB.load("tools/web_public/business/lab.json", {})

    def fake(rel, default=None):
        if str(rel).endswith("business/lab.json"):
            L = copy.deepcopy(lab)
            L["rows"].append({"id": "zz_new_idea", "bot": "lit", "who": "Zlarior", "title": "Zlarior: a brand new idea", "what": "Something new.", "status": "parked",
                              "registered": "2026-12-31", "usd_month_by": {}})
            return L
        return src(rel, default)
    WB.load = fake
    try:
        w1 = WB.build()
    finally:
        WB.load = src
    a = {p["id"]: p["cells"] for p in w0["places"]}
    b = {p["id"]: p["cells"] for p in w1["places"]}
    kept = sum(1 for k, v in a.items() if b.get(k) == v)
    new = next((p for p in w1["places"] if p["id"] == "lab:zz_new_idea"), None)
    lab_r = [math.hypot(p["x"], p["z"]) for p in w1["places"] if p["quarter"] == "lab"]
    check("c. a new Lab idea (born today) becomes a scaffold place in the Lab quarter at its outer edge; the old places keep their spots (%d of %d)" % (kept, len(a)),
          new is not None and new["quarter"] == "lab" and new["state"] == "planned" and math.hypot(new["x"], new["z"]) >= sorted(lab_r)[len(lab_r) // 2] and kept >= len(a) * 0.97,
          (new and (new["x"], new["z"]), kept))


def test_privacy(w):
    txt = json.dumps(w)
    plan = WB.load("tools/web_public/business/accounts.json", {})
    pc_ids = sorted({i for a in plan.get("accounts") or [] for i in (a.get("pc") or []) if isinstance(i, str) and re.search(r"[_0-9]", i)})
    check("d. no PC account ids, no e-mail address, no 'last 4' / last4 fields in the world file", not [i for i in pc_ids if i in txt] and not re.search(r"[\w.+-]+@[\w-]+\.\w", txt)
          and "last4" not in txt and not re.search(r"\blast 4\b", txt, re.I), [i for i in pc_ids if i in txt])
    check("d. the hidden bots (dashboard_view.json: BLITZ) never appear: no place, no fact, no feed line; the file says which bots are hidden",
          "blitz" in [h.lower() for h in w["hidden_bots"]] and not re.search(r"blitz", json.dumps({k: w[k] for k in ("places", "feed")}), re.I), "")


def test_file(w):
    w2 = WB.build()
    check("e. deterministic: two builds are the same (but the build time)", json.dumps(strip(w)) == json.dumps(strip(w2)))
    raw = json.dumps(w, separators=(",", ":"), ensure_ascii=False).encode()
    check("e. compact: under 300 KB (%d KB); buildings are [height 0-255, state 0-5, day] triples" % (len(raw) // 1024),
          len(raw) < 300_000 and all(len(p["b"]) % 3 == 0 and all(0 <= v <= 255 for v in p["b"][0::3]) and set(p["b"][1::3]) <= set(range(6)) for p in w["places"]))
    shipped = WB.load(os.path.join(WORLD_DIR, "world.json"), {})
    check("e. the shipped cities/world/world.json is this tool's output (same places, districts and counts)", shipped.get("kind") == "olympus-world"
          and [p["id"] for p in shipped.get("places", [])] == [p["id"] for p in w["places"]] and shipped.get("counts") == w["counts"],
          (len(shipped.get("places", [])), shipped.get("counts")))
    tmp = tempfile.mkdtemp(prefix="world-")
    try:
        r = subprocess.run([sys.executable, "-X", "utf8", os.path.join(ROOT, "tools", "world_build.py"), "--check"], capture_output=True, text=True, timeout=120, cwd=tmp)
        check("e. --check prints the counts and writes nothing", r.returncode == 0 and "places" in r.stdout and not os.listdir(tmp), r.stdout[-300:] + r.stderr[-300:])
        out = os.path.join(tmp, "w.json")
        r = subprocess.run([sys.executable, "-X", "utf8", os.path.join(ROOT, "tools", "world_build.py"), "--out", out], capture_output=True, text=True, timeout=120)
        check("e. --out writes a valid world.json there", r.returncode == 0 and json.load(open(out, encoding="utf-8"))["kind"] == "olympus-world", r.stderr[-300:])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


HARNESS = r"""
const fs = require('fs');
import(process.argv[2]).then((C) => {
  const w = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
  const o = {};
  const A = C.planWorld(w, { tier: 'high' }), B = C.planWorld(w, { tier: 'high' }), L = C.planWorld(w, { tier: 'low' });
  let nan = 0; for (const k of ['pos', 'size', 'info', 'tint', 'misc']) for (const v of A[k]) if (!Number.isFinite(v)) nan++;
  let neg = 0; for (let i = 0; i < A.n; i++) if (!(A.size[i * 3] > 0 && A.size[i * 3 + 1] > 0 && A.size[i * 3 + 2] > 0)) neg++;
  let st = new Set(); for (let i = 0; i < A.n; i++) st.add(A.info[i * 4 + 2]);
  let maxH = 0; for (let i = 0; i < A.n; i++) maxH = Math.max(maxH, A.pos[i * 3 + 1] + A.size[i * 3 + 1]);
  o.plan = { n: A.n, low: L.n, same: Buffer.from(A.pos.buffer).equals(Buffer.from(B.pos.buffer)), nan, neg, states: [...st].sort(), places: A.places.length, maxH: Math.round(maxH),
    halos: A.halos.length, rings: A.rings.length, beams: A.beams.length, slots: A.slots, data: A.stats.data };
  const home = C.homePose(w), cam = C.poseToCam(home), ov = C.poseToCam(C.overviewPose(w));
  o.cam = { home: cam.pos.map(Math.round), look: cam.look.map(Math.round), over: ov.pos[1] > cam.pos[1] * 2, finite: [home, C.overviewPose(w), ...w.districts.map((d) => C.districtPose(w, d))].every((p) => Object.values(p).every(Number.isFinite)) };
  const lp = C.lerpPose({ tx: 0, tz: 0, dist: 10, yaw: 3.0, pitch: 0.3 }, { tx: 10, tz: 10, dist: 40, yaw: -3.0, pitch: 0.5 }, 0.5);
  o.lerp = [Math.round(lp.dist), Math.round(lp.tx), Math.abs(lp.yaw) > 3];
  const cp = C.clampPose({ tx: 1e6, tz: 0, dist: 1e9, yaw: 99, pitch: -5 }, w), bad = C.clampPose({ tx: NaN, tz: 0, dist: NaN, yaw: 0, pitch: NaN }, w);
  o.clamp = [Math.round(Math.hypot(cp.tx, cp.tz)) <= w.R + 61, cp.dist <= w.R * 3.6 + 1, cp.pitch >= 0.1, Math.abs(cp.yaw) <= Math.PI, Object.values(bad).every(Number.isFinite)];
  const cands = [{ i: 1, sx: 100, sy: 100, rpx: 30, front: true, kind: 'research' }, { i: 2, sx: 112, sy: 104, rpx: 20, front: true, kind: 'app' }, { i: 3, sx: 300, sy: 300, rpx: 10, front: false, kind: 'app' }];
  o.pick = [C.pick(cands, 106, 102), C.pick(cands, 100, 100) , C.pick(cands, 300, 300), C.pick(cands, 600, 600), C.pick([], 1, 1)];
  const lab = C.chooseLabels([{ key: 'a', sx: 100, sy: 200, w: 80, h: 20 }, { key: 'b', sx: 110, sy: 205, w: 80, h: 20 }, { key: 'c', sx: 100, sy: 300, w: 80, h: 20 }, { key: 'd', sx: -50, sy: 300, w: 80, h: 20 }], 5, 390, 844);
  o.labels = lab;
  const lite = { t: 1000, board: { lit: { position: { entry_t: 990, side: 'SHORT' } }, atlas: { position: null } } };
  o.live = [C.pcLine(lite, 1060).text, C.pcLine(lite, 1000 + 7200).silent, C.pcLine(null, 5).text, JSON.stringify(C.positions(lite)), JSON.stringify(C.positions(null))];
  const places = w.places.map((p) => ({ ...p }));
  const ev = { events: [{ t: 5, kind: 'owner_note', acct: 'atlas', text: 'secret 1234' }, { t: 9, kind: 'eval_passed', acct: 'atlas', text: 'ATLAS passed: balance $26,620 ends 1234' }, { t: 7, kind: 'bot_started', text: 'x' }] };
  o.board = C.boardLines(ev, places);
  const L2 = { built: '2099-01-01 00:00', rows: [{ id: w.places.find((p) => p.id.startsWith('lab:') && p.state === 'ruin').id.slice(4), status: 'shadow' }, { id: 'nope', status: 'adopted' }] };
  o.labch = C.labChanges(L2, w);
  o.search = [C.search(w.places.map((p, i) => ({ raw: p, i })), 'kalshi').slice(0, 3).map((x) => x.raw.name), C.search(w.places, '').length, C.search(w.places.map((p) => ({ raw: p })), 'taxes').length > 0];
  o.words = [C.usd(-326), C.usd(5562), C.usd(14, true), C.usd(NaN), C.ago(30), C.ago(600), C.dateText('2026-11-18'), C.addDays('2026-10-17', 33)];
  o.feed = C.feedLines(w, [{ id: 'bot:lit', text: 'live' }]).slice(0, 2).map((x) => x.text);
  console.log(JSON.stringify(o));
}).catch((e) => { console.log(JSON.stringify({ _error: String(e && e.stack || e) })); });
"""


def test_core(w):
    node = shutil.which("node")
    if not node:
        check("f. node is not installed: the core checks are skipped", True)
        return
    tmp = tempfile.mkdtemp(prefix="owcore-")
    try:
        core = os.path.join(tmp, "ow-core.mjs")
        shutil.copy(os.path.join(WORLD_DIR, "ow-core.js"), core)
        wj = os.path.join(tmp, "w.json")
        with open(wj, "w", encoding="utf-8") as fh:
            json.dump(w, fh)
        h = os.path.join(tmp, "h.cjs")
        with open(h, "w", encoding="utf-8") as fh:
            fh.write(HARNESS)
        r = subprocess.run([node, h, core, wj], capture_output=True, text=True, timeout=120)
        o = json.loads(r.stdout or "{}") if r.stdout.strip().startswith("{") else {"_error": r.stderr[-500:]}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    check("f. the core runs in node", "_error" not in o, o.get("_error"))
    if "_error" in o:
        return
    p = o["plan"]
    check("f. planWorld: thousands of instances (%d high, %d low), every number finite, sizes positive, the same city every time, all six building states used" % (p["n"], p["low"]),
          p["n"] > 6000 and p["low"] < p["n"] and p["nan"] == 0 and p["neg"] == 0 and p["same"] and p["states"] == [0, 1, 2, 3, 4, 5] and p["places"] == len(w["places"]), p)
    check("f. the Gate spire (46) is the tallest thing; halos only where the light is (live, bright, shortcuts) + the plaza; rings and searchlights on the live parts",
          44 <= p["maxH"] <= 60 and len(w["places"]) // 8 <= p["halos"] <= len(w["places"]) // 2 + 1 and p["rings"] >= 5 and p["beams"] >= 6 and p["slots"] == len(w["places"]) + 5, p)
    c = o["cam"]
    check("f. the first view looks north from the south at the NQ district; the overview is high above; every pose finite", c["home"][2] > 0 and c["look"][2] < 0 and c["over"] and c["finite"], c)
    check("f. poses blend the short way round and in log distance; a wild pose is clamped (inside the city, pitch 0.1-1.45, NaN healed)",
          o["lerp"] == [20, 5, True] and all(o["clamp"]), (o["lerp"], o["clamp"]))
    check("f. picking: the nearest centre for its size wins, an app wins a near tie, behind the camera never, empty space = -1", o["pick"] == [2, 1, -1, -1, -1], o["pick"])
    check("f. labels never overlap and never leave the screen", o["labels"] == ["a", "c"], o["labels"])
    lv = o["live"]
    check("f. live: 'PC live · just now', silent after 30 min, a plain line with no report; Zlarior's open SHORT is read from the board card, nothing for ATLAS",
          lv[0] == "PC live · just now" and lv[1] is True and lv[2] == "PC: no live report here" and '"lit":{"side":"SHORT"' in lv[3] and '"atlas":null' in lv[3] and lv[4] == '{"lit":null,"atlas":null,"blitz":null}', lv)
    b = o["board"]
    check("f. the Board's events become fixed plain words (an owner note and an event's own text are never shown), newest first, pointing at the account",
          [x["text"] for x in b] == ["ATLAS 25K (funded): passed its eval", "The bots started on your PC"] and b[0]["id"] == "acct:atlas" and "1234" not in json.dumps(b), b)
    check("f. a newer lab.json turns a ruin into a growing place (only places already in the city)", len(o["labch"]) == 1 and o["labch"][0]["state"] == "growing", o["labch"])
    check("f. search finds the Kalshi apps first, nothing for an empty box, taxes is found", o["search"][0][:2] == ["Kalshi bot", "Kalshi desk"] and o["search"][1] == 0 and o["search"][2], o["search"])
    check("f. words: -$326, $5,562, +$14, '-', just now, 10 min ago, Nov 18, 33 days after Oct 17 = Nov 19", o["words"] == ["-$326", "$5,562", "+$14", "-", "just now", "10 min ago", "Nov 18", "2026-11-19"], o["words"])
    check("f. the ticker: live lines first, then the dated learning feed", o["feed"][0] == "live" and re.match(r"^[A-Z][a-z]{2} \d+ · ", o["feed"][1] or ""), o["feed"])


if __name__ == "__main__":
    w = test_build()
    test_plan(w)
    test_learning(w)
    test_privacy(w)
    test_file(w)
    test_core(w)
    bad = RES.count(False)
    print(f"\n{len(RES) - bad}/{len(RES)} passed", flush=True)
    sys.exit(1 if bad else 0)
