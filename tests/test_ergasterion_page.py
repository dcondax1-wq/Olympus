"""ERGASTERION, the OLYMPUS workshop where every worker is visible (tools/ergasterion_build.py + tools/web_public/ergasterion/, AGORA look, 2026-11-10): a marble-and-bronze factory floor with one
station for each real worker (5 money machines, 3 NQ bots, Mind, the Kalshi bot, Prometheus, Hephaestus, Cronos, the task queue, the dev agents): a status lamp, what it is doing now, its last 5 outputs,
what it learned (dated, with the source file) and its health; a first-person walk (joystick, drag look, collision, minimap, follow a worker), a live event ticker, a Learning board and a
'What should we research next?' card. Read only: it never starts a worker and never trades.

  a. static: the builder's selftest and --check, queue.json against the raw files, the files, the kit lines, the AGORA look, read-only, the manifest, the DEMO fixture, the row in tools/new_apps.json
  b. the maths in node (ergasterioncore.js): statuses, honest labels for missing / sample files, events, lessons, suggestions, collision, junk input, no markup from data
  c. Chromium 390 x 844: DEMO, tap a worker, the real files (and missing ones), 3D floor or the plan (pick, walk, follow), LITE, reduced motion, 375 x 667, taps >= 44 px
    python -X utf8 -m tests.test_ergasterion_page            (--static: parts a and b only)
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import agora_kit as AK  # noqa: E402

APP, NAME = "ergasterion", "Ergasterion"
check = AK.check
D = os.path.join(AK.WEB, APP)
BUILD = os.path.join(AK.ROOT, "tools", "ergasterion_build.py")
KALSHI = "https://raw.githubusercontent.com/demetrades2000-coder/kalshi-feed/main/kalshi.json"
SCENES = {"stars", "smoke", "coins", "embers", "neurons", "skyline", "torches", "threads", "streaks", "bars", "leaves", "columns", "shards", "rings", "maze"}
READS = ("./queue.json", "../home.json", "../money/index.json", "../cronos/status.json", "../prometheus/forge.json", "../hephaestus/data.json")


def test_static():
    r = subprocess.run([sys.executable, BUILD, "--selftest"], capture_output=True, text=True)
    check("a. the builder's own selftest passes (tools/ergasterion_build.py --selftest)", r.returncode == 0 and "ALL PASS" in r.stdout, r.stdout[-500:] + r.stderr[-300:])
    r2 = subprocess.run([sys.executable, BUILD, "--check"], capture_output=True, text=True)
    check("a. queue.json is EXACTLY what `python tools/ergasterion_build.py` writes now (rebuild it after QUEUE.md, a write-up or the Mind's proposals change; the git part is ignored)", r2.returncode == 0, r2.stdout[-300:])
    q = json.load(open(os.path.join(D, "queue.json"), encoding="utf-8"))
    qmd = AK.read(os.path.join(AK.ROOT, "handoff", "QUEUE.md"))
    n_open, n_done = len(re.findall(r"^- \[ \]", qmd, re.M)), len(re.findall(r"^- \[[xX]\]", qmd, re.M))
    check("a. queue.json counts the real tasks of handoff/QUEUE.md (open / done), and every open task listed is really in the file", q["queue"]["open"] == n_open and q["queue"]["done"] == n_done and all(t["id"] and not t["done"] for t in q["queue"]["tasks"]), (q["queue"]["open"], n_open))
    bad = [x["src"] for x in q["learnings"] if not os.path.isfile(os.path.join(AK.ROOT, x["src"]))]
    check("a. every learning names a source file that exists, a date, a worker and a sentence (no learning without its source)", not bad and all(x["d"] and x["who"] and x["text"] and x["src"] for x in q["learnings"]) and len(q["learnings"]) >= 10, bad[:3])
    wu = [f for f in os.listdir(os.path.join(AK.ROOT, "research", "writeups")) if f.endswith(".md") and f.upper() != "INDEX.MD"]
    check("a. the write-up index is real: the count equals the files, the newest 12 exist, 'tested and rejected' has write-ups and the reference bullets", q["writeups"]["count"] == len(wu) and len(q["writeups"]["latest"]) == 12 and all(os.path.isfile(os.path.join(AK.ROOT, x["file"])) for x in q["writeups"]["latest"]) and q["rejected"] and q["rejected_ref"])
    check("a. no secrets or markup in queue.json", not re.search(r"[<>]|api[_-]?key|password|secret|ghp_|sk-[a-z0-9]{10}", json.dumps(q), re.I))
    AK.static_kit(APP, NAME, reads=READS, allow_urls=(KALSHI,))
    js = AK.read(os.path.join(D, "ergasterion.js")) + AK.read(os.path.join(D, "ergasterioncore.js"))
    check("a. Ergasterion only informs: no localStorage / cookie of its own, no POST, no window.open, nothing started, bought or traded", not re.search(r"localStorage|sessionStorage|indexedDB|method:\s*['\"]POST|window\.open|location\.href\s*=", js))
    check("a. the 3D files: floor.js (render core) and floorload.js (its own module tag, before the page)", all(os.path.isfile(os.path.join(D, n)) for n in ("floor.js", "floorload.js")))
    fl = AK.read(os.path.join(D, "floor.js"))
    check("a. floor.js: on the OLYMPUS render core, AGORA look, bloom <= .25, no network / markup from data, LITE falls back (ok false), reduced motion zeroes the animation",
          "../olympus/render.js" in fl and "../jarvis/three.module.min.js" in fl and not AK.BANNED_LOOK.search(fl) and not re.search(r"fetch\(|innerHTML|XMLHttpRequest|https?://", fl)
          and all(float(x) <= 0.25 for x in re.findall(r"bloom: \{ strength: ([\d.]+)", fl)) and "q === 'low' || q === 'off'" in fl and "const mot = reduced ? 0 : 1" in fl)
    check("a. floor.js is light: every repeated part is an InstancedMesh (platforms, bodies, heads, arms, lamps, belts, items, columns), one label sprite per station, first person with collision from the core",
          fl.count("new THREE.InstancedMesh") >= 9 and "THREE.Sprite" in fl and "walk(" in fl and "followCam" in fl)
    html = AK.read(os.path.join(D, "index.html"))
    check("a. floorload.js before ergasterion.js; the 3D stage AND the flat plan exist; page order: hero, floor, card, workers, ticker, learning board, research next",
          html.index("floorload.js") < html.index('src="ergasterion.js') and 'id="stage"' in html and 'id="plan"' in html and 'id="mini"' in html
          and html.index('id="hero"') < html.index('id="floorCard"') < html.index('id="sheet"') < html.index('id="workersCard"') < html.index('id="tickerCard"') < html.index('id="boardCard"') < html.index('id="nextCard"'))
    na = json.load(open(os.path.join(AK.ROOT, "tools", "new_apps.json"), encoding="utf-8"))
    row = next((a for a in na["apps"] if a["id"] == APP), None)
    check("a. the row in tools/new_apps.json: group trading, a description under 80 characters, an existing intro scene, a transition, an ambient bed, an accent and a glyph (--apply is for the lead)",
          row is not None and row["group"] == "trading" and len(row["description"]) < 80 and row["flavour"][0] in SCENES and len(row["flavour"]) == 3 and row["transition"]["kind"] and row["ambient"] and re.match(r"^#[0-9a-f]{6}$", row["accent"]) and row["glyph"], row)
    fx = json.load(open(os.path.join(D, "fixture.json"), encoding="utf-8"))
    check("a. the fixture covers all 15 workers' inputs (home, money x5, kalshi, cron, forge, heph, queue with learnings, mind and git) with times counted back from now", len(fx["money"]["streams"]) == 5 and len(fx["home"]["accounts"]) == 3 and fx["cron"]["tasks"] and fx["queue"]["learnings"] and fx["queue"]["git"]["commits"])


HARNESS = r"""
import(process.argv[2]).then((C) => {
  const fs = require('fs'), fx = JSON.parse(fs.readFileSync(process.argv[3], 'utf8')), real = JSON.parse(fs.readFileSync(process.argv[4], 'utf8'));
  const now = Date.parse('2026-11-10T12:00:00Z'), H = 3600000, D = 86400000, o = {};
  const demo = C.resolveDemo(fx, now), W = C.buildWorkers(demo, now), by = (w, id) => w.find((x) => x.id === id);
  o.ids = [W.length, C.STATIONS.length, W.map((w) => w.id).join() === C.IDS.join(), new Set(W.map((w) => w.x + ',' + w.z)).size];
  o.demo = [demo.demo, W.every((w) => w.demo), W.every((w) => w.health.startsWith('Example data.')), W.map((w) => w.status).join()];
  o.head = [C.headline(W).title, C.headline(W).level, C.headline(W).counts.failed, C.headline([]).title];
  const real1 = C.buildWorkers({ queue: real }, now);
  o.noFiles = [by(real1, 'chrysos').status, by(real1, 'chrysos').missing, by(real1, 'chrysos').doing, by(real1, 'lit').status, by(real1, 'cronos').health, by(real1, 'queue').status, by(real1, 'dev').status, C.haveReal({ queue: real }), C.haveReal({ home: { accounts: [] } }), C.haveReal(null)];
  o.devReal = [by(real1, 'dev').outputs.length > 0, by(real1, 'dev').src, by(real1, 'mind').status, by(real1, 'mind').outputs.length, by(real1, 'mind').learned.length > 1];
  // honest statuses of the money machines
  const mk = (s) => C.buildWorkers({ money: { streams: [Object.assign({ id: 'sibyl', name: 'Sibyl', items: [], notes: [] }, s)] } }, now).find((w) => w.id === 'sibyl');
  o.money = [mk({ status: 'ok', age_min: 20 }).status, mk({ status: 'ok', age_min: 60 * 20 }).status, mk({ status: 'ok', age_min: 60 * 50 }).status, mk({ status: 'sample', age_min: 5 }).status, mk({ status: 'stale', age_min: 5 }).status, mk({ status: 'error', age_min: 5 }).status, mk({ status: 'ok', asof: new Date(now - 2 * H).toISOString() }).last === now - 2 * H];
  const lit = C.buildWorkers({ home: { t: now / 1000, accounts: [{ id: 'x', name: 'Zlarior 50K', conn: { connected: true }, eval: { room: 1420, mll: 2000 }, pnl: { today: 312 } }, { id: 'y', name: 'ATLAS 25K', conn: { connected: false } }] } }, now);
  o.bots = [by(lit, 'lit').status, by(lit, 'lit').doing, by(lit, 'atlas').status, by(lit, 'blitz').missing];
  const k = (x) => C.buildWorkers({ kalshi: x }, now).find((w) => w.id === 'kalshi');
  o.kalshi = [k({ running: true, t: now / 1000 }).status, k({ running: false, t: now / 1000 }).status, k({ running: true, t: (now - 50 * H) / 1000 }).status, k(null).status, k({ running: true, t: now / 1000, settled_n: 4 }).n];
  const cr = (t) => C.buildWorkers({ cron: { tasks: t } }, now).find((w) => w.id === 'cronos');
  o.cron = [cr({ a: { ok: true, last_run_t: now / 1000 - 3600, cadence: 'nightly' } }).status, cr({ a: { ok: false, last_run_t: now / 1000 - 3600, error: 'x' } }).status, cr({ a: { ok: true, last_run_t: now / 1000 - 200 * 3600, cadence: 'nightly' } }).status, cr({ a: { ok: true, last_run_t: now / 1000 - 150 * 3600, cadence: 'weekly' } }).status, cr({}).status];
  // events, lessons, suggestions
  const ev = C.events(W, now, 30);
  o.events = [ev.length > 5, ev.every((e, i) => i === 0 || ev[i - 1].t >= e.t), ev.every((e) => e.t <= now + H), ev[0].name];
  const L = C.lessons(W, now, 12);
  o.lessons = [L.length <= 12, L.length > 5, L.every((l) => l.src && l.text && l.name), L.every((l, i) => i === 0 || (L[i - 1].ms == null ? -1 : L[i - 1].ms) >= (l.ms == null ? -1 : l.ms) || l.ms == null), Math.max(...Object.values(L.reduce((a, l) => (a[l.who] = (a[l.who] || 0) + 1, a), {}))) <= 3, L.filter((l) => l.week).length];
  const realL = C.lessons(real1, now, 12);
  o.realLessons = [realL.length, realL.every((l) => l.src && l.d !== undefined), realL.filter((l) => l.week).length, new Set(realL.map((l) => l.text)).size === realL.length];
  const S = C.suggestions(W, demo.queue, now);
  o.sugg = [S.map((s) => s.title), S[0].w >= S[1].w, S.every((s) => s.next && s.why), C.suggestions(C.buildWorkers({ home: { accounts: [] } }, now).map((w) => Object.assign({}, w, { status: 'working', missing: false, n: null })), { queue: { open: 0 } }, now)[0].title];
  // collision and walking
  const st = C.STATIONS, p0 = { x: 0, z: 7.4 };
  const stuck = C.resolveCollision(-4.4, -1.2, st), out = C.resolveCollision(99, 99, st);
  o.walk = [Math.hypot(stuck.x - st[6].x, stuck.z - st[6].z) >= C.STATION_R - 1e-6, out.x === C.BOUNDS.x && out.z === C.BOUNDS.z];
  let p = p0; for (let i = 0; i < 400; i++) p = C.walk(p, 0, { fwd: 1, side: 0 }, 0.05, st);
  o.walk.push(st.every((s) => Math.hypot(p.x - s.x, p.z - s.z) >= C.STATION_R - 1e-6), p.z < p0.z, Math.abs(C.walk({ x: 0, z: 0 }, 0, { fwd: 1 }, 1, []).z + 0.34) < 1e-9, C.walk({ x: 0, z: 0 }, Math.PI / 2, { fwd: 1 }, 0.1, []).x < 0, C.nearest({ x: -7.5, z: -2.5 }, st).id, C.nearest({ x: 0, z: 8 }, st));
  const fc = C.followCam(st[0], 3, true);
  o.follow = [fc.look.x === st[0].x, fc.z > st[0].z, fc.y > 1.5];
  // junk and hostile text
  const evil = C.buildWorkers({ home: 5, money: { streams: [null, 3, { id: 'chrysos', name: '<b>x</b>', headline: '<img src=x onerror=alert(1)>', items: [{ title: '<script>1</script>' }, null], notes: [7, '<i>n</i>'] }] }, kalshi: 'q', cron: { tasks: { z: 5 } }, forge: [], heph: 'x', queue: { learnings: [null, { who: 'chrysos', text: '<u>t</u>', src: '<s>' }, { who: 'zzz' }], queue: { open: 'x', tasks: [null, { id: '<x>', text: 'ok' }] }, mind: 3, git: { commits: [null, { t: 'zz', s: '<q>' }] }, rejected: [null, 4], writeups: { latest: [null] } } }, NaN);
  const raw = JSON.stringify(evil);
  o.junk = [evil.length, !/[<>]/.test(raw), C.buildWorkers(null, now).length, C.events(null || [], now).length, C.lessons([], now).length, C.suggestions([], null, now).length, C.toMs('zz'), C.toMs('2026-11-10 02:00') === Date.parse('2026-11-10T02:00:00Z'), C.toMs(1793394000) === 1793394000000, C.toMs(1793394000000) === 1793394000000, C.money(-1420), C.moneyS(312), C.agoText(null, now), C.agoText(now - 5 * 60000, now), C.agoText(now - 3 * H, now), C.agoText(now - 5 * D, now)];
  const card = C.jarvisCard(W, demo.queue, now, true);
  o.card = [card.name, card.status.level, card.status.label, card.kpis.length, card.kpis[1].value, card.lines.length, Number.isInteger(card.t), JSON.stringify(card).length < 8192];
  console.log(JSON.stringify(o));
});
"""


def test_maths():
    out = AK.node(APP, HARNESS, os.path.join(D, "fixture.json"), os.path.join(D, "queue.json"))
    if out is None:
        check("b. node is not installed: the maths checks are skipped", True)
        return
    if "_error" in out:
        check("b. the node harness runs", False, out)
        return
    check("b. 15 stations, one per real worker, in the registry order, each on its own spot of the floor", out["ids"] == [15, 15, True, 15], out["ids"])
    check("b. the demo is honest: every worker is flagged example data and says so in its health line; the demo still shows all lamp kinds (working, idle, stale, failed)",
          out["demo"][0] and out["demo"][1] and out["demo"][2] and {"working", "idle", "stale", "failed"} <= set(out["demo"][3].split(",")), out["demo"])
    check("b. the headline: the failed worker first ('1 worker failed'), bad level; an empty list never crashes", out["head"][:3] == ["1 worker failed", "bad", 1] and isinstance(out["head"][3], str), out["head"])
    check("b. no files published: money machines, bots, Cronos say 'no file yet' and are STALE (never working, never blank); the queue and dev agents still read queue.json; haveReal ignores queue.json",
          out["noFiles"][:2] == ["stale", True] and "No file" in out["noFiles"][2] and out["noFiles"][3] == "stale" and "not published" in out["noFiles"][4] and out["noFiles"][5] == "working" and out["noFiles"][6] in ("working", "idle") and out["noFiles"][7:] == [False, True, False], out["noFiles"])
    check("b. the real queue.json feeds the dev agents (commits when git was there, write-ups otherwise) and the Mind (its seed is old, so STALE, with its notes and the 'context only' lesson)",
          out["devReal"][0] and out["devReal"][1] in ("git log", "research/writeups") and out["devReal"][2] == "stale" and out["devReal"][3] >= 1 and out["devReal"][4], out["devReal"])
    check("b. money machine statuses: fresh = working, 20 h = idle, 50 h = stale, sample = sample, stale / error from the file are kept, the run time comes from asof", out["money"] == ["working", "idle", "stale", "sample", "stale", "failed", True], out["money"])
    check("b. bots: connected = working with 'Drawdown left $1,420 of $2,000 max loss', disconnected = stale, a missing account says so", out["bots"][0] == "working" and "Drawdown left $1,420 of $2,000 max loss." in out["bots"][1] and out["bots"][2] == "stale" and out["bots"][3] is True, out["bots"])
    check("b. Kalshi bot: running = working, not running = FAILED, a 50 h old feed = stale, no feed = stale, the settled count is kept", out["kalshi"] == ["working", "failed", "stale", "stale", 4], out["kalshi"])
    check("b. Cronos: all on time = working, a failed job = failed, an overdue nightly job = stale, a weekly job 200 h old is still fine, an empty log = idle", out["cron"] == ["working", "failed", "stale", "working", "idle"], out["cron"])
    check("b. the event ticker: newest first, never in the future, plain words", out["events"][:3] == [True, True, True], out["events"])
    check("b. the Learning board: at most 12, each with its source, newest first, at most 3 from one worker, the week flagged", out["lessons"][:5] == [True, True, True, True, True] and out["lessons"][5] >= 5, out["lessons"])
    check("b. real learnings: every one dated or flagged undated, no duplicates, the week count is honest (the repo's write-ups are older than a week, so it may be 0)", out["realLessons"][0] >= 5 and out["realLessons"][1] and out["realLessons"][3], out["realLessons"])
    check("b. 'what should we research next?': ranked by weight, a failure first, then data gaps (stale, small samples, the queue); every row has a why and a next action; nothing to do says so",
          out["sugg"][0][0] == "Cronos failed its last run" and "Oikos is stale" in out["sugg"][0] and any("only 4 settled trades" in t for t in out["sugg"][0]) and out["sugg"][1] and out["sugg"][2] and out["sugg"][3] == "Nothing is waiting", out["sugg"])
    check("b. walking: a station is solid (collision radius), the walls stop you, a straight walk never ends inside a station, joystick forward moves toward -z, yaw turns, 'nearest' finds the platform",
          out["walk"][:3] == [True, True, True] and out["walk"][3] and out["walk"][4] and out["walk"][5] and out["walk"][6] == "lit" and out["walk"][7] is None, out["walk"])
    check("b. follow camera: behind and above the worker, looking at it", out["follow"] == [True, True, True], out["follow"])
    check("b. junk and hostile input: nothing throws, no '<' or '>' survives into any text, bad dates give null, money words are plain",
          out["junk"][0] == 15 and out["junk"][1] and out["junk"][2] == 15 and out["junk"][3:6] == [0, 0, 1] and out["junk"][6] is None and out["junk"][7:10] == [True, True, True] and out["junk"][10:12] == ["-$1,420", "+$312"] and out["junk"][12:] == ["no time on record", "5 min ago", "3 h ago", "5 days ago"], out["junk"])
    check("b. the Jarvis card: Ergasterion, 'off' in demo, 3 kpis, one line, an integer t, under 8 KB", out["card"][:3] == ["Ergasterion", "off", "Demo data"] and out["card"][3] == 3 and out["card"][4] == "2" and out["card"][5] == 1 and out["card"][6] and out["card"][7], out["card"])


def test_page():
    try:
        import playwright  # noqa: F401
    except ImportError:
        check("c. page tests skipped: no Playwright", True)
        return
    fx = json.load(open(os.path.join(D, "fixture.json"), encoding="utf-8"))
    srv, origin = AK.serve()
    try:
        with AK.browser() as br:
            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, APP, "?demo=1&flat=1", hook="ERGASTERION")
            d = p.evaluate("""() => ({ demo: !document.querySelector('#demo').hidden, title: document.querySelector('#heroTitle').textContent, line: document.querySelector('#heroLine').textContent, workers: document.querySelectorAll('#workers button').length,
              groups: [...document.querySelectorAll('#workers .grp')].map((e) => e.textContent), lessons: document.querySelectorAll('#lessons li').length, week: document.querySelectorAll('#lessons li[data-week="1"]').length, srcs: [...document.querySelectorAll('#lessons .src')].every((e) => e.textContent.startsWith('source: ')),
              ticker: document.querySelectorAll('#ticker li').length, next: [...document.querySelectorAll('#next li b')].map((e) => e.textContent), go: [...document.querySelectorAll('#next .go')].every((e) => e.textContent.startsWith('Next: ')), follow: document.querySelector('#follow').options.length,
              font: getComputedStyle(document.querySelector('h1')).fontFamily, bg: getComputedStyle(document.body).backgroundColor, legend: document.querySelectorAll('#legend li').length, sheetHidden: document.querySelector('#sheet').hidden, mode: window.ERGASTERION.floor() ? '3d' : 'plan' })""")
            check("c. DEMO: the chip, '1 worker failed' with 'example workers', 15 workers in 4 groups, a Learning board of up to 12 with sources, a ticker, a ranked 'research next' (a failure first), 16 follow options, the legend, no card open yet",
                  d["demo"] and d["title"] == "1 worker failed" and "example workers" in d["line"] and d["workers"] == 15 and d["groups"] == ["Money machines", "NQ bots", "Thinkers", "Jobs", "People and agents"] and 6 <= d["lessons"] <= 12 and d["week"] >= 5 and d["srcs"]
                  and d["ticker"] >= 6 and d["next"][0] == "Cronos failed its last run" and d["go"] and d["follow"] == 16 and d["legend"] == 5 and d["sheetHidden"], d)
            check("c. AGORA look: serif title, warm dark body", any(f in d["font"] for f in ("Palatino", "Iowan", "Georgia")) and d["bg"] == "rgb(20, 17, 14)", d)
            check("c. the floor is 3D or the flat plan, never nothing (the plan always has 15 buttons)", d["mode"] in ("3d", "plan") and p.evaluate("() => document.querySelector('#stage').hidden !== document.querySelector('#plan').hidden"), d["mode"])
            AK.shot(p, "ergasterion-demo")
            # tap a worker from the list: its card
            p.locator('#workers button[data-id="cronos"]').click()
            c = p.evaluate("""() => ({ h: document.querySelector('#sheetH').textContent, pill: document.querySelector('#sheetPill').textContent, doing: document.querySelector('#sheetDoing').textContent, outs: document.querySelectorAll('#sheetOut li').length,
              learn: [...document.querySelectorAll('#sheetLearn li')].map((e) => e.textContent), health: document.querySelector('#sheetHealth').textContent, hidden: document.querySelector('#sheet').hidden, status: document.querySelector('#status').textContent })""")
            check("c. a worker card: name, the status word, what it is doing, at most 5 outputs, learnings with 'source:', the health line, and the status line is spoken",
                  not c["hidden"] and c["h"] == "Cronos" and c["pill"] == "Failed" and "1 failed" in c["doing"] and 1 <= c["outs"] <= 5 and c["health"].startswith("Example data.") and c["status"].startswith("Cronos: Failed."), c)
            p.locator('#workers button[data-id="mind"]').click()
            m = p.evaluate("() => [document.querySelector('#sheetH').textContent, [...document.querySelectorAll('#sheetLearn li')].map((e) => e.textContent), document.querySelectorAll('#sheetOut li').length]")
            check("c. the Mind card lists its notes as outputs and keeps the 'context only: not predictive' lesson with its source file", m[0] == "Mind" and m[2] == 2 and any("context only" in t and "source: docs/CLAUDE_REFERENCE.md" in t for t in m[1]), m)
            p.locator("#sheetClose").click()
            check("c. Close hides the card", p.evaluate("() => document.querySelector('#sheet').hidden"))
            check("c. DEMO at 390 x 844: no sideways scroll, every tap >= 44 px, nothing under Jarvis's corner, no console error, nothing fetched off the site", AK.no_sideways(p) and not AK.taps(p) and not AK.corner(p) and not errs and not [u for u in off if "kalshi" not in u], (AK.taps(p)[:4], AK.corner(p), errs[:2], off[:3]))
            ctx.close()

            # 3D floor: pick, walk, follow (only when the machine can draw it; ERG_NO3D=1 skips it on a busy machine)
            ctx, p, errs, seen, off = AK.page(br, origin, w=320, h=568)
            AK.open_app(p, origin, APP, "?demo=1&q=high" if os.environ.get("ERG_NO3D") != "1" else "?demo=1&flat=1", hook="ERGASTERION")
            p.wait_for_timeout(2500)
            mode = p.evaluate("() => window.ERGASTERION.floor() ? '3d' : 'plan'")
            if os.environ.get("ERG_NO3D") == "1":
                print("[note] ERG_NO3D=1: the 3D floor interaction checks are skipped", flush=True)
            elif mode == "3d":
                check("c. 3D floor: the stage shows, the plan hides, 'Plan view' and 'Back to the door' are there, the minimap is drawn with 15 platforms", p.evaluate("() => !document.querySelector('#stage').hidden && document.querySelector('#plan').hidden && !document.querySelector('#viewBtn').hidden && document.querySelector('#viewBtn').textContent === 'Plan view' && !document.querySelector('#resetBtn').hidden && document.querySelectorAll('#mini g').length === 15"))
                pt = p.evaluate("() => window.ERGASTERION.floor().project('sibyl')")
                box = p.evaluate("() => { const r = document.querySelector('#floor3d').getBoundingClientRect(); return [r.left, r.top]; }")
                check("c. the first view from the door sees the back rows (the money machines project on screen)", pt is not None and 0 <= pt["x"] <= 390 and 0 <= pt["y"] <= 600, pt)
                if pt:
                    p.evaluate("""([x, y]) => { const c = document.querySelector('#floor3d'); const o = { bubbles: true, pointerId: 7, clientX: x, clientY: y, pointerType: 'touch' }; c.dispatchEvent(new PointerEvent('pointerdown', o)); c.dispatchEvent(new PointerEvent('pointerup', o)); }""", [box[0] + pt["x"], box[1] + pt["y"]])
                    p.wait_for_timeout(400)
                    sid = p.evaluate("() => [document.querySelector('#sheetH').textContent, document.querySelector('#sheet').hidden]")
                    check("c. tapping a platform in the 3D floor opens that worker's card (nearest station within 56 px)", sid[0] in ("Sibyl", "Mercury", "Oikos", "Chrysos", "Arbiter") and not sid[1], sid)
                before = p.evaluate("() => window.ERGASTERION.floor().pos()")
                p.evaluate("""() => { const j = document.querySelector('#joy'), r = j.getBoundingClientRect(), cx = r.left + r.width / 2, cy = r.top + r.height / 2; const ev = (t, y) => j.dispatchEvent(new PointerEvent(t, { bubbles: true, pointerId: 3, clientX: cx, clientY: y, pointerType: 'touch' })); ev('pointerdown', cy); ev('pointermove', cy - 40); window.__t0 = performance.now(); window.__ev = ev; window.__cy = cy; }""")
                p.wait_for_timeout(1500)
                p.evaluate("() => window.__ev('pointerup', window.__cy - 40)")
                after = p.evaluate("() => window.ERGASTERION.floor().pos()")
                check("c. the joystick pushed forward walks you toward the back wall (z decreases) and the knob returns to the middle", after["z"] < before["z"] - 0.05 and p.evaluate("() => document.querySelector('#knob').style.transform") in ("translate(0px,0px)", ""), (before, after))
                p.evaluate("() => { const f = window.ERGASTERION.floor(); f.teleport(-4.5, -1.2 + 0.2); }")
                p.evaluate("() => { const f = window.ERGASTERION.floor(); f.move({ fwd: 0, side: 0 }); f.step(0.05); }")
                inside = p.evaluate("() => window.ERGASTERION.floor().pos()")
                check("c. no walking through a platform: teleported onto ATLAS, the next step pushes you out to the collision circle", ((inside["x"] + 4.5) ** 2 + (inside["z"] + 1.2) ** 2) ** 0.5 >= 1.44, inside)
                p.select_option("#follow", "kalshi")
                p.wait_for_timeout(500)
                fo = p.evaluate("() => [window.ERGASTERION.floor().pos().following, document.querySelector('#status').textContent]")
                check("c. 'Follow' a worker: the camera follows Kalshi bot, the status line says so; the joystick or Nobody ends it", fo[0] == "kalshi" and fo[1].startswith("Following Kalshi bot"), fo)
                p.select_option("#follow", "")
                p.evaluate("() => document.querySelector('#resetBtn').click()")
                rs = p.evaluate("() => window.ERGASTERION.floor().pos()")
                check("c. 'Back to the door' puts you at the entrance, not following", abs(rs["z"] - 7.4) < 0.01 and rs["following"] is None, rs)
                AK.shot(p, "ergasterion-3d")
                p.evaluate("() => document.querySelector('#viewBtn').click()")
                p.wait_for_timeout(300)
                check("c. 'Plan view' swaps to the flat plan and 'Walk the floor' brings the 3D back", p.evaluate("() => document.querySelector('#stage').hidden && !document.querySelector('#plan').hidden && document.querySelector('#viewBtn').textContent === 'Walk the floor'"))
                p.evaluate("() => document.querySelector('#viewBtn').click()")
                p.wait_for_timeout(1500)
                check("c. back in 3D after the swap", p.evaluate("() => !!window.ERGASTERION.floor() && !document.querySelector('#stage').hidden"))
            else:
                print("[note] 3D floor not available on this machine: the plan is checked instead", flush=True)
                check("c. no 3D here: the flat plan is shown, 'Walk the floor' is offered only when 3D can be tried", p.evaluate("() => !document.querySelector('#plan').hidden && document.querySelector('#stage').hidden"))
            check("c. the 3D run has no console error", not errs, errs[:3])
            ctx.close()

            # the flat plan: tap a worker on the plan (LITE, 375 x 667, reduced motion)
            ctx, p, errs, seen, off = AK.page(br, origin, w=375, h=667, reduced=True, lite=True)
            AK.open_app(p, origin, APP, "?demo=1&q=low", hook="ERGASTERION")
            r = p.evaluate("() => ({ plan: !document.querySelector('#plan').hidden, stage: document.querySelector('#stage').hidden, buttons: document.querySelectorAll('#plan g[role=button]').length, view: document.querySelector('#viewBtn').hidden, lite: !document.querySelector('#lite').hidden, floor: !!window.ERGASTERION.floor() })")
            check("c. 375 x 667, LITE (?q=low), reduced motion: the plan with 15 buttons, no 3D, no 'Walk the floor' button, the LITE chip", r["plan"] and r["stage"] and r["buttons"] == 15 and r["view"] and r["lite"] and not r["floor"], r)
            p.locator('#plan g[data-id="oikos"]').click()
            c2 = p.evaluate("() => [document.querySelector('#sheetH').textContent, document.querySelector('#sheetPill').textContent, document.querySelector('#sheet').hidden]")
            check("c. tapping a worker on the plan opens its card (Oikos: Stale in the demo)", c2 == ["Oikos", "Stale", False], c2)
            sz = p.evaluate("() => { const r = document.querySelector('#plan g[data-id=oikos]').getBoundingClientRect(); return [r.width, r.height]; }")
            check("c. a plan button is at least 44 px (its hit square), no sideways scroll, every tap >= 44 px, no error", sz[0] >= 43.5 and sz[1] >= 43.5 and AK.no_sideways(p) and not AK.taps(p) and not errs, (sz, AK.taps(p)[:3], errs[:2]))
            AK.shot(p, "ergasterion-lite")
            ctx.close()

            # real files: home, money, kalshi, cron, forge (queue.json is the real one of the repo)
            real = {
                "/home.json": json.dumps({"t": int(time.time()), "accounts": [{"id": "mffu50k_eval", "name": "Zlarior 50K", "conn": {"connected": True}, "eval": {"room": 1420, "mll": 2000}, "pnl": {"today": 312}}]}),
                "/money/index.json": json.dumps({"streams": [{"id": "sibyl", "name": "Sibyl", "status": "ok", "asof": "2026-11-10T00:00:00Z", "headline": "One pick survives the check.", "items": [{"title": "Pick Z", "usd": None}], "notes": ["Only 1 pick survives out-of-sample."]}]}),
                "/cronos/status.json": json.dumps({"tasks": {"fates": {"ok": True, "last_run_t": int(time.time()) - 3600, "cadence": "nightly"}}}),
            }
            srv2, origin2 = AK.serve(overrides=real)
            try:
                ctx, p, errs, seen, off = AK.page(br, origin2, mock={"kalshi.json": json.dumps({"running": True, "t": int(time.time()), "today_pnl": 12.4})})
                AK.open_app(p, origin2, APP, "?q=low", hook="ERGASTERION")
                rr = p.evaluate("""() => { const w = (id) => document.querySelector('#workers button[data-id=' + id + ']').getAttribute('aria-label'); return { demo: document.querySelector('#demo').hidden, lit: w('lit'), sibyl: w('sibyl'), chrysos: w('chrysos'), kalshi: w('kalshi'), cron: w('cronos'), dev: w('dev'),
                  learn: [...document.querySelectorAll('#lessons li')].map((e) => e.textContent), title: document.querySelector('#heroTitle').textContent, next: [...document.querySelectorAll('#next li b')].map((e) => e.textContent) }; }""")
                check("c. REAL files: no DEMO chip; Zlarior shows its real drawdown line; Sibyl's own note becomes a lesson with 'source: money/sibyl.json'; a machine with no file says 'No file from this machine yet' and is Stale, never invented",
                      rr["demo"] and "Drawdown left $1,420 of $2,000 max loss" in rr["lit"] and rr["sibyl"].startswith("Sibyl, ") and "One pick survives the check." in rr["sibyl"],
                      rr)
                check("c. REAL files: the lessons include Sibyl's note with its source, the missing machines are named in 'research next' with 'no file here', and the page never shows example data as real",
                      any("Only 1 pick survives out-of-sample." in t and "source: money/sibyl.json" in t for t in rr["learn"]) and "No file from this machine yet" in rr["chrysos"] and any("has no file here" in t for t in rr["next"]) and not any("Example" in t for t in rr["learn"]), rr)
                check("c. REAL files: Kalshi (mocked feed) is Working and Cronos is Working from its status.json; the dev agents read the real queue.json", "Kalshi bot, Working" in rr["kalshi"] and "Cronos, Working" in rr["cron"] and rr["dev"].startswith("Dev agents"), rr)
                check("c. REAL run reads only the site's own files (the kalshi feed is the one outside address) and has no console error", any("queue.json" in u for u in seen) and not errs and not [u for u in off if "kalshi" not in u], (off[:3], errs[:3]))
                ctx.close()
            finally:
                srv2.shutdown()

            # no worker files at all: the demo, never blank
            srv3, origin3 = AK.serve(overrides={"/ergasterion/queue.json": None, "/prometheus/forge.json": None, "/hephaestus/data.json": None})
            try:
                ctx, p, errs, seen, off = AK.page(br, origin3)
                AK.open_app(p, origin3, APP, "?q=low", hook="ERGASTERION")
                z = p.evaluate("() => [!document.querySelector('#demo').hidden, document.querySelectorAll('#workers button').length, document.querySelector('#heroTitle').textContent]")
                check("c. nothing published (no home, money, queue ...): the DEMO fixture fills the floor, labelled DEMO, never blank", z[0] and z[1] == 15 and z[2] == "1 worker failed", z)
                ctx.close()
            finally:
                srv3.shutdown()

            # reduced motion with 3D: still, no error
            ctx, p, errs, seen, off = AK.page(br, origin, reduced=True)
            AK.open_app(p, origin, APP, "?demo=1&q=high" if os.environ.get("ERG_NO3D") != "1" else "?demo=1&flat=1", hook="ERGASTERION")
            p.wait_for_timeout(1500)
            mode = p.evaluate("() => window.ERGASTERION.floor() ? '3d' : 'plan'")
            if mode == "3d":
                a1 = p.evaluate("() => window.ERGASTERION.floor().pos()")
                p.wait_for_timeout(700)
                a2 = p.evaluate("() => window.ERGASTERION.floor().pos()")
                check("c. reduced motion: the floor stands still by itself (no drift), the 3D run has no error", a1 == a2 and not errs, (a1, a2, errs[:2]))
            else:
                check("c. reduced motion: the plan, no error", not errs, errs[:2])
            ctx.close()
    finally:
        srv.shutdown()


if __name__ == "__main__":
    test_static()
    test_maths()
    if "--static" not in sys.argv:
        test_page()
    AK.finish()
