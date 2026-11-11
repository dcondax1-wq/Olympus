"""ERGASTERION v2, the OLYMPUS AI agent factory (tools/ergasterion_build.py + tools/web_public/ergasterion/, AGORA look, 2026-11-11): "an AI agent factory where you can really see, first
person, what everyone is doing, then researching and learning from it for everything". Four halls (Money, Trading, Research, Library) with doors, one station for each real worker (5 money
machines, 3 NQ bots, Mind, the Kalshi bot, Prometheus, Hephaestus, Cronos, the task queue, the dev agents): a marble figure doing its job, a status lamp, a speech bubble with its latest
finding, a conveyor of labelled crates; a day replay (24 h / 7 days, play, speed, jump to last failure); the research pipeline wall (Idea -> Testing -> Verdict from the Archive index);
the learning engine (lessons with dedupe, a strength score, sources, categories, 'what changed our mind', lessons.json for Jarvis); a 'what next' planner; first person with eased
joystick + look, collision with walls and doors, a minimap with you-are-here, follow a worker, a calm tour; and THE BUILDERS' CAMP outside the front door: a desert caravan camp with a tent,
a worker, a banner, a cycling scroll of commit messages, a crate stack and brazier smoke for each build agent (builders.json = handoff/agents_now.json joined with git). Read only: it never starts a worker and never trades.

  a. static: the builder's selftest, --check and determinism, queue.json / lessons.json against the raw files, the files, the kit lines, the AGORA look, read-only, the DEMO fixture
  b. the maths in node (ergasterioncore.js): statuses, halls / walls / doors, bubbles and crates, the replay stream, the pipeline, the learning board, the planner, junk input
  c. Chromium 390 x 844: DEMO, a worker card and its crates, the replay, the pipeline, the board, the 3D factory (pick, walk, walls, follow, tour, budget) or the plan, LITE, real files
    python -X utf8 -m tests.test_ergasterion_page            (--static: parts a and b only)
    browser part (one browser on the machine): flock -w 2400 /tmp/olympus_browser.lock python -X utf8 -m tests.test_ergasterion_page
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import agora_kit as AK  # noqa: E402

APP, NAME = "ergasterion", "Ergasterion"
check = AK.check
D = os.path.join(AK.WEB, APP)
BUILD = os.path.join(AK.ROOT, "tools", "ergasterion_build.py")
KALSHI = "https://raw.githubusercontent.com/demetrades2000-coder/kalshi-feed/main/kalshi.json"
SCENES = {"stars", "smoke", "coins", "embers", "neurons", "skyline", "torches", "threads", "streaks", "bars", "leaves", "columns", "shards", "rings", "maze"}
READS = ("./builders.json", "./queue.json", "../home.json", "../money/index.json", "../cronos/status.json", "../prometheus/forge.json", "../hephaestus/data.json")
BUDGET = {"calls": 45, "triangles": 150000}        # the high tier's budget for the whole factory (floor.js draws about 15 calls / 40k triangles before post-processing)


def test_static():
    r = subprocess.run([sys.executable, BUILD, "--selftest"], capture_output=True, text=True)
    check("a. the builder's own selftest passes (tools/ergasterion_build.py --selftest: queue, write-ups, event stream, lessons dedupe + strength, what changed our mind, pipeline, determinism)", r.returncode == 0 and "ALL PASS" in r.stdout and r.stdout.count("[PASS]") >= 16, r.stdout[-700:] + r.stderr[-300:])
    r2 = subprocess.run([sys.executable, BUILD, "--check"], capture_output=True, text=True)
    check("a. queue.json and lessons.json are EXACTLY what `python tools/ergasterion_build.py` writes now (rebuild after QUEUE.md, a write-up, a research run or the Archive index changes; git and the money run times are ignored)", r2.returncode == 0, r2.stdout[-300:])
    tmp = tempfile.mkdtemp(prefix="erg-")
    outs = []
    for k in ("a", "b"):
        o = os.path.join(tmp, k, "ergasterion", "queue.json")
        subprocess.run([sys.executable, BUILD, "--out", o], capture_output=True, text=True)
        outs.append((json.load(open(o, encoding="utf-8")), AK.read(os.path.join(os.path.dirname(o), "lessons.json"))))
    for d in (outs[0][0], outs[1][0]):
        d.pop("git", None)
    check("a. the builder is deterministic: two builds into two folders give the same queue.json (git aside) and byte-identical lessons.json, and both equal the committed files", outs[0][0] == outs[1][0] and outs[0][1] == outs[1][1] and outs[0][1] == AK.read(os.path.join(D, "lessons.json")))
    q = json.load(open(os.path.join(D, "queue.json"), encoding="utf-8"))
    qmd = AK.read(os.path.join(AK.ROOT, "handoff", "QUEUE.md"))
    n_open, n_done = len(re.findall(r"^- \[ \]", qmd, re.M)), len(re.findall(r"^- \[[xX]\]", qmd, re.M))
    check("a. queue.json counts the real tasks of handoff/QUEUE.md (open / done), and every open task listed is really in the file", q["queue"]["open"] == n_open and q["queue"]["done"] == n_done and all(t["id"] and not t["done"] for t in q["queue"]["tasks"]), (q["queue"]["open"], n_open))
    bad = [x["src"] for x in q["learnings"] if not os.path.isfile(os.path.join(AK.ROOT, x["src"]))]
    check("a. every learning names a source file that exists, a date, a worker and a sentence (no learning without its source)", not bad and all(x["d"] and x["who"] and x["text"] and x["src"] for x in q["learnings"]) and len(q["learnings"]) >= 10, bad[:3])
    wu = [f for f in os.listdir(os.path.join(AK.ROOT, "research", "writeups")) if f.endswith(".md") and f.upper() != "INDEX.MD"]
    check("a. the write-up index is real: the count equals the files, the newest 12 exist, 'tested and rejected' has write-ups and the reference bullets", q["writeups"]["count"] == len(wu) and len(q["writeups"]["latest"]) == 12 and all(os.path.isfile(os.path.join(AK.ROOT, x["file"])) for x in q["writeups"]["latest"]) and q["rejected"] and q["rejected_ref"])
    ev = q["events"]
    check("a. the event stream: dated, newest first, each with a worker, a kind, plain text and its source; research runs (batched), write-ups and the Mind are all in it; nothing older than 45 days before the newest",
          len(ev) >= 30 and all(isinstance(e["t"], int) and e["t"] > 0 and e["who"] and e["text"] and e["src"] and e["kind"] for e in ev) and all(ev[i]["t"] >= ev[i + 1]["t"] for i in range(len(ev) - 1))
          and {"run", "writeup"} <= {e["kind"] for e in ev} and ev[0]["t"] - ev[-1]["t"] <= 45 * 86400 and any("research run" in e["text"] for e in ev), (len(ev), sorted({e["kind"] for e in ev})))
    L = q["lessons"]
    lsrc = [s["src"] for x in L for s in x["sources"] if not os.path.isfile(os.path.join(AK.ROOT, s["src"]))]
    norm = [re.sub(r"[^a-z0-9]+", " ", x["text"].lower()).strip() for x in L]
    check("a. the learning engine: every lesson has a category, a strength >= 1 that is at least its listed sources, source files that all exist, and no two lessons with the same words (deduped)",
          len(L) >= 20 and not lsrc and all(x["cat"] in ("NQ strategy", "Kalshi", "money", "process", "app") and x["strength"] >= len(x["sources"]) >= 1 and x["text"] for x in L) and len(set(norm)) == len(norm) and any(x["strength"] >= 2 for x in L), lsrc[:3])
    ch = q["changed"]
    k95 = [c for c in ch if c["src"].endswith("kalshi_edge_A.md")]
    check("a. 'what changed our mind' is lifted from the write-ups: the Kalshi 95c pocket (\"95c and above is +1.4% per $\") that did not hold market-wide is there with its file, and team B's pocket that vanished",
          ch and all(os.path.isfile(os.path.join(AK.ROOT, c["src"])) and c["text"] for c in ch) and k95 and k95[0]["was"] == "95c and above is +1.4% per $" and "not an edge" in k95[0]["text"] and k95[0]["cat"] == "Kalshi"
          and k95[0]["text"] in re.sub(r"\s+", " ", AK.read(os.path.join(AK.ROOT, k95[0]["src"]))) and any(c["src"].endswith("kalshi_edge_B.md") and "vanished" in c["text"] for c in ch), ch[:2])
    arch = json.load(open(os.path.join(AK.WEB, "archive", "index.json"), encoding="utf-8"))
    pc = q["pipeline"]["counts"]
    check("a. the pipeline is the Archive's own count: ideas = runs, testing = open, adopted and rejected as in archive/index.json, per family too, with the newest 20 moves",
          pc == {"ideas": arch["counts"]["runs"], "testing": arch["counts"]["open"], "adopted": arch["counts"]["adopted"], "rejected": arch["counts"]["rejected"]} and pc["ideas"] == pc["testing"] + pc["adopted"] + pc["rejected"]
          and {f["name"]: f["runs"] for f in q["pipeline"]["families"]} == {f["name"]: f["runs"] for f in arch["families"]} and len(q["pipeline"]["moves"]) == 20 and q["pipeline"]["moves"][0]["d"] >= q["pipeline"]["moves"][-1]["d"], pc)
    lj = json.load(open(os.path.join(D, "lessons.json"), encoding="utf-8"))
    check("a. lessons.json for Jarvis ('what did we learn this week'): one plain sentence to say, the week's lessons, the strongest, what changed, counts per category, under 16 KB, no markup",
          lj["v"] == 1 and 40 < len(lj["say"]) <= 520 and isinstance(lj["week"], list) and lj["top"] and lj["changed"] and set(lj["counts"]) == {"NQ strategy", "Kalshi", "money", "process", "app"} and lj["asof"] == q["asof"]
          and all(x["sources"] and x["text"] for x in lj["week"] + lj["top"]) and os.path.getsize(os.path.join(D, "lessons.json")) < 16384 and not re.search(r"[<>]", json.dumps(lj)), lj["say"][:200])
    bj = json.load(open(os.path.join(D, "builders.json"), encoding="utf-8"))
    an = json.load(open(os.path.join(AK.ROOT, "handoff", "agents_now.json"), encoding="utf-8"))
    check("a. builders.json (the Builders' camp): one row per agent of handoff/agents_now.json with its name, job, area and branch; an agent with git activity has dated commits, a last-commit time, files and folders; one without is labelled 'job only, no live activity' and has none; no markup",
          bj["v"] == 1 and bj["source"] in ("git", "file") and [a["name"] for a in bj["agents"]] == [a["name"] for a in an["agents"]][:16] and all(a["job"] and a["id"] and isinstance(a["commits"], list) for a in bj["agents"])
          and all((a["last_t"] > 0 and all(c["t"] > 0 and c["s"] for c in a["commits"]) and len(a["commits"]) <= 8 and isinstance(a["folders"], list)) if a["live"] else (a["note"] == "job only, no live activity" and not a["commits"] and a["last_t"] == 0) for a in bj["agents"])
          and (bj["source"] == "git") == any(a["live"] for a in bj["agents"]) and not re.search(r"[<>]", json.dumps(bj)), bj["source"])
    check("a. no secrets or markup in queue.json", not re.search(r"[<>]|api[_-]?key|password|secret|ghp_|sk-[a-z0-9]{10}", json.dumps(q), re.I))
    AK.static_kit(APP, NAME, reads=READS, allow_urls=(KALSHI,))
    js = AK.read(os.path.join(D, "ergasterion.js")) + AK.read(os.path.join(D, "ergasterioncore.js"))
    check("a. Ergasterion only informs: no localStorage / cookie of its own, no POST, no window.open, nothing started, bought or traded", not re.search(r"localStorage|sessionStorage|indexedDB|method:\s*['\"]POST|window\.open|location\.href\s*=", js))
    check("a. the 3D files: floor.js (render core) and floorload.js (its own module tag, before the page)", all(os.path.isfile(os.path.join(D, n)) for n in ("floor.js", "floorload.js")))
    fl = AK.read(os.path.join(D, "floor.js"))
    check("a. floor.js: on the OLYMPUS render core, AGORA look, bloom <= .25, no network / markup from data, LITE falls back (ok false), reduced motion zeroes the animation",
          "../olympus/render.js" in fl and "../jarvis/three.module.min.js" in fl and not AK.BANNED_LOOK.search(fl) and not re.search(r"fetch\(|innerHTML|XMLHttpRequest|https?://", fl)
          and all(float(x) <= 0.25 for x in re.findall(r"bloom: \{ strength: ([\d.]+)", fl)) and "q === 'low' || q === 'off'" in fl and "const mot = reduced ? 0 : 1" in fl)
    check("a. floor.js is light: every repeated part goes through batch() into ONE InstancedMesh per batch (12 batches), the 15 bubbles are one mesh on one atlas, the crate tags and hall signs another; no per-worker sprites or meshes",
          fl.count("new THREE.InstancedMesh") == 1 and len(re.findall(r"= batch\(|, \w+ = batch\(", fl)) >= 6 and fl.count("batch(") >= 13 and "THREE.Sprite" not in fl and fl.count("atlas(2048, 1024)") == 3 and fl.count("new THREE.Mesh(") <= 6)
    check("a. floor.js has the Builders' camp: tents and dunes are two more batches, the banners and scrolls ONE mesh on a third atlas, the figures reuse the factory's batches; smoke only for a working builder; the scroll cycles commit messages and stands still under reduced motion",
          all(k in fl for k in ("CAMP_SPOTS", "campFrame(", "drawCamp(", "tent = batch(", "dune = batch(", "'camp:' + camp[j].id", "b.scroll[idx]")) and "if (st !== 'working') hide(lamp.im, PUFF0" in fl and "mot ? Math.floor((t + j * 1.7) / 5.5) % n : 0" in fl)
    check("a. floor.js: first person from the core (walk with wall and station collision, eased joystick and look, follow camera, the calm tour, the hall you are in), a figure for each job, crates and boards you can tap",
          all(k in fl for k in ("walk(", "followCam", "tourCam(", "ease(", "hallOf(", "DOORS", "HALLS", "pulse(", "projectCrate")) and all("'" + j + "'" in fl for j in ("wheel", "scribe", "oracle", "smith", "scales")) and "o.onPick(hit.id, hit.crate)" in fl)
    html = AK.read(os.path.join(D, "index.html"))
    check("a. floorload.js before ergasterion.js; the 3D stage AND the flat plan exist; page order: hero, floor, worker card, the Builders' camp, builder card, replay, workers, ticker, pipeline, learning board, what next",
          html.index("floorload.js") < html.index('src="ergasterion.js') and 'id="stage"' in html and 'id="plan"' in html and 'id="mini"' in html
          and html.index('id="hero"') < html.index('id="floorCard"') < html.index('id="sheet"') < html.index('id="campCard"') < html.index('id="bsheet"') < html.index('id="replayCard"') < html.index('id="workersCard"') < html.index('id="tickerCard"') < html.index('id="pipeCard"') < html.index('id="boardCard"') < html.index('id="nextCard"'))
    check("a. PEOPLE: the shared kit is an optional module tag (olympus/people.js) before the page; a Talk prompt in the stage, 'People here' with a Stand-up button, the built-in chat card, Talk buttons and a face in both cards",
          html.index("../olympus/people.js?v=p1") < html.index('src="ergasterion.js') and all(k in html for k in ('id="talkBtn"', 'id="peopleCard"', 'id="standBtn"', 'id="chatCard"', 'id="chatQs"', 'id="sheetTalk"', 'id="bsheetTalk"', 'id="sheetFace"', 'id="bsheetFace"'))
          and html.index('id="floorCard"') < html.index('id="peopleCard"') < html.index('id="chatCard"') < html.index('id="sheet"'))
    check("a. floor.js: the workers are cartoon PERSONS, not statues: a seeded look per person (skin, hair, tunic) from the core, eyes that blink, mitten hands; poses wave (on approach) / talk (chat open) / cheer / slump; the person turns to face you and a marble disc marks it; olympus/people3d.js is an optional import for its spec() colours",
          all(k in fl for k in ("lookOf(i)", "'wave'", "'talk'", "'cheer'", "'slump'", "focus(key)", "Math.atan2(camP.x - fx, camP.z - fz)", "import('../olympus/people3d.js')", ".catch(", "blink", "HS = 9")) and "MARBLE); fig.add" not in fl)
    pjs = AK.read(os.path.join(D, "ergasterion.js"))
    check("a. the page talks through the kit only when it is really there (window.OLYMPUS_PEOPLE with open), inside try / catch, and falls back to its own chat; it never needs the kit",
          "window.OLYMPUS_PEOPLE" in pjs and "typeof K.open === 'function'" in pjs and pjs.count("catch (_)") >= 8 and "C.answer(row, qid" in pjs and "K.standup" in pjs and "K.portrait" in pjs)
    check("a. the replay controls are real controls: a range slider, Play, Speed, 'Jump to last failure', 24 hours / 7 days; the tour and follow controls exist",
          all(k in html for k in ('id="scrub"', 'type="range"', 'id="playBtn"', 'id="speedBtn"', 'id="failBtn"', 'id="r24"', 'id="r7"', 'id="tourBtn"', 'id="follow"', 'id="lanes"')))
    na = json.load(open(os.path.join(AK.ROOT, "tools", "new_apps.json"), encoding="utf-8"))
    row = next((a for a in na["apps"] if a["id"] == APP), None)
    check("a. the row in tools/new_apps.json: group trading, a description under 80 characters, an existing intro scene, a transition, an ambient bed, an accent and a glyph (--apply is for the lead)",
          row is not None and row["group"] == "trading" and len(row["description"]) < 80 and row["flavour"][0] in SCENES and len(row["flavour"]) == 3 and row["transition"]["kind"] and row["ambient"] and re.match(r"^#[0-9a-f]{6}$", row["accent"]) and row["glyph"], row)
    fx = json.load(open(os.path.join(D, "fixture.json"), encoding="utf-8"))
    fq = fx["queue"]
    check("a. the fixture covers all 15 workers' inputs and the v2 blocks (events, money runs, lessons with sources, what changed, pipeline, data gaps), every text says Example, times are counted back from now",
          len(fx["money"]["streams"]) == 5 and len(fx["home"]["accounts"]) == 3 and fx["cron"]["tasks"] and fq["learnings"] and fq["git"]["commits"] and len(fq["events"]) >= 8 and fq["money_runs"] and len(fq["lessons"]) >= 6 and fq["changed"] and fq["pipeline"]["families"] and fq["gaps"]
          and all(x["text"].startswith("Example") for x in fq["events"] + fq["lessons"] + fq["changed"] + fq["money_runs"]) and all("ago_h" in e for e in fq["events"]) and all("d_ago" in x and x["sources"] for x in fq["lessons"]))
    fb = fx["builders"]["agents"]
    check("a. the fixture has an example Builders' camp: 10 agents named Example, with working / quiet / merged / job-only cases, times counted back from now", len(fb) == 10 and all(a["name"].startswith("Example") and a["job"].startswith("Example") for a in fb) and any(a["merged"] for a in fb) and any(not a["live"] for a in fb) and all("ago_min" in c for a in fb for c in a["commits"]))


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
  // the ticker and each worker's own lessons
  const ev = C.events(W, now, 30);
  o.events = [ev.length > 5, ev.every((e, i) => i === 0 || ev[i - 1].t >= e.t), ev.every((e) => e.t <= now + H), ev[0].name];
  const L = C.lessons(W, now, 12);
  o.lessons = [L.length <= 12, L.length > 5, L.every((l) => l.src && l.text && l.name), L.every((l, i) => i === 0 || (L[i - 1].ms == null ? -1 : L[i - 1].ms) >= (l.ms == null ? -1 : l.ms) || l.ms == null), Math.max(...Object.values(L.reduce((a, l) => (a[l.who] = (a[l.who] || 0) + 1, a), {}))) <= 3, L.filter((l) => l.week).length];
  // v2: the four halls, jobs, what a worker says, its crates
  const st = C.STATIONS, hallOk = st.every((s) => { const h = C.HALLS.find((x) => x.id === s.hall); return h && s.x > h.x0 + 2 && s.x < h.x1 - 2 && s.z > h.z0 + 2 && s.z < h.z1 - 2 && C.hallOf(s).id === s.hall; });
  o.halls = [C.HALLS.map((h) => h.name).join(), C.DOORS.length, hallOk, st.every((s) => !!C.JOB_WORD[s.job]), new Set(st.map((s) => s.job)).size, C.HALLS.map((h) => st.filter((s) => s.hall === h.id).length).join(),
    Math.min(...st.flatMap((a, i) => st.slice(i + 1).map((b) => Math.hypot(a.x - b.x, a.z - b.z)))) >= 2 * C.STATION_R + 0.9, C.hallOf({ x: -3, z: -3 }).id + C.hallOf({ x: 3, z: -3 }).id + C.hallOf({ x: -3, z: 3 }).id + C.hallOf({ x: 3, z: 3 }).id, C.hallOf(C.START).id, C.hallOf(null).id];
  o.say = [by(W, 'cronos').say, by(real1, 'chrysos').say, by(W, 'sibyl').say, by(W, 'oikos').say, W.every((w) => w.say && w.say.length <= 110), W.every((w) => w.crates.length <= 5 && w.crates.every((c) => c.tag && c.tag.length <= 16 && c.text)), by(W, 'queue').crates.map((c) => c.tag).join('|'), C.crateTag('Example commit: a new app page'), C.crateTag(''), by(W, 'sibyl').crates.length === by(W, 'sibyl').outputs.length];
  // collision: walls, doors, stations; walking; easing; the tour
  const wall = C.resolveCollision(0.1, 3, st), wall2 = C.resolveCollision(-0.2, -8, st), door = C.resolveCollision(0.1, 5, st), door2 = C.resolveCollision(6.5, 0.1, st), wz = C.resolveCollision(3, -0.2, st), jamb = C.resolveCollision(0.1, 6.15, st), stuck = C.resolveCollision(7.1, -7.3, st), out = C.resolveCollision(99, -99, st);
  o.walls = [wall.x === C.WALL_T && wall.z === 3, wall2.x === -C.WALL_T, door.x === 0.1 && door.z === 5, door2.z === 0.1 && door2.x === 6.5, wz.z === -C.WALL_T, jamb.x === C.WALL_T, Math.hypot(stuck.x - 7, stuck.z + 7.5) >= C.STATION_R - 1e-6, out.x === C.BOUNDS.x && out.z === -C.BOUNDS.z];
  // the camp outside the front door
  const evilRow = { id: 'x', doing: '<b>d</b>', crates: [{ text: '<i>c</i>', t: 5 }], learned: [{ text: '<u>l</u>', src: '<s>' }], health: '<h>', role: '<r>', src: '<q>', status: 'failed' };
  const cst = st.concat(C.CAMP_SPOTS), cOut = C.resolveCollision(99, 99, cst), cW = C.resolveCollision(-99, 15, cst), wallS = C.resolveCollision(3, 9.8, cst), wallS2 = C.resolveCollision(3, 10.4, cst), doorS = C.resolveCollision(6.5, 10, cst), tentIn = C.resolveCollision(4.6, 15.9, cst);
  let ps = { x: C.START.x, z: C.START.z }, trail = []; for (let i = 0; i < 70; i++) { ps = C.walk(ps, Math.PI, { fwd: 1, side: 0 }, 0.05, cst); trail.push(C.hallOf(ps).id); }
  let pb = { x: 6.5, z: 14 }; for (let i = 0; i < 200; i++) pb = C.walk(pb, 0, { fwd: 1, side: 0 }, 0.05, cst);
  o.camp = [cOut.x === C.CAMP.x1 - 0.6 && cOut.z === C.CAMP.z1 - 0.6, cW.x === C.CAMP.x0 + 0.6, wallS.z === C.BOUNDS.z, wallS2.z === C.CAMP.door.z1, doorS.x === 6.5 && doorS.z === 10, Math.hypot(tentIn.x - 4.5, tentIn.z - 15.8) >= C.STATION_R - 1e-6,
    trail[0] === 'library' && trail[trail.length - 1] === 'camp', ps.z > 12 && Math.abs(ps.x - 6.5) < 1e-9, C.hallOf(pb).id === 'library' || C.hallOf(pb).id === 'trading', C.CAMP_SPOTS.length, C.hallOf({ x: 6.5, z: 15 }).name,
    C.CAMP_SPOTS.every((c) => c.x > C.CAMP.x0 + 1.5 && c.x < C.CAMP.x1 - 1.5 && c.z - 2.6 > C.CAMP.z0 && c.z < C.CAMP.z1 - 1.5), Math.min(...C.CAMP_SPOTS.flatMap((a, i) => C.CAMP_SPOTS.slice(i + 1).map((b) => Math.hypot(a.x - b.x, a.z - b.z)))) >= 3,
    C.HALLS.length];
  const bnow = Date.parse('2026-11-11T02:00:00Z'), BD = C.builders(C.resolveBuilders(fx.builders, bnow), bnow, true), HD = C.allHands(BD, fx.builders, true), realB = JSON.parse(fs.readFileSync(process.argv[5], 'utf8'));
  const BRl = C.builders(realB, bnow, false), fileOnly = C.builders({ source: 'file', agents: realB.agents.map((a) => ({ name: a.name, job: a.job, area: a.area, branch: a.branch, live: false, commits: [], last_t: 0 })) }, bnow, false);
  const one = (x) => C.builders({ agents: [Object.assign({ name: 'A', job: 'J', live: true }, x)] }, bnow)[0];
  o.builders = [BD.length, BD.map((b) => b.status).join(), BD.every((b) => b.sample && b.scroll.length >= 1 && b.id && b.line), HD.line, HD.list.map((b) => b.status).join(), HD.counts.working + HD.counts.quiet + HD.counts.done + HD.counts.job === 10,
    BD[0].crates === 3 && BD[0].commits.length === 3 && BD[0].commits[0].t > BD[0].commits[1].t, BD[7].shipped.length === 2 && BD[7].scroll[0].startsWith('Shipped: '), BD[9].status === 'job' && BD[9].line === 'Job only, no live activity.' && BD[9].scroll[0].indexOf('no live activity') > 0 && BD[9].commits.length === 0 && BD[9].mins === null,
    BD.every((b, i) => b.x === C.CAMP_SPOTS[i].x && b.z === C.CAMP_SPOTS[i].z)];
  o.buildersReal = [BRl.length === realB.agents.length, BRl.every((b) => ['working', 'quiet', 'done', 'job'].includes(b.status) && b.name && b.job && !b.sample), BRl.every((b) => (b.status === 'job') === !b.live), fileOnly.every((b) => b.status === 'job' && !b.commits.length && b.crates === 0), C.allHands(fileOnly, { source: 'file' }).note,
    /job line only/.test(C.allHands(fileOnly, { source: 'file' }).line), one({ last_t: bnow / 1000 - 5 * 60 }).status, one({ last_t: bnow / 1000 - 16 * 60 }).status, one({ last_t: bnow / 1000 - 60, merged: true }).status, one({ live: false, last_t: bnow / 1000 }).status, one({ last_t: 'x' }).status,
    C.builders(null, bnow).length, C.allHands([], null).line, !/[<>]/.test(JSON.stringify(C.builders({ agents: [null, 5, { name: '<b>n</b>', job: '<i>j</i>', live: true, last_t: bnow / 1000, commits: [null, { t: bnow / 1000, s: '<s>c</s>' }, { s: 'no time' }], folders: [{ name: '<f>', n: 'x' }], shipped: 'x' }] }, bnow))),
    C.builders({ agents: new Array(14).fill({ name: 'x', job: 'y' }) }, bnow).length];
  // people
  const PP = C.people(W, BD), cron = by(W, 'cronos'), ansC = C.QUESTIONS.map((q) => C.answer(cron, q[0], now, C.suggestions(W, demo.queue, now))), sib = by(W, 'sibyl'), ansS = C.QUESTIONS.map((q) => C.answer(sib, q[0], now, []));
  const ansB = C.QUESTIONS.map((q) => C.answer(BD[0], q[0], bnow)), ansJ = C.QUESTIONS.map((q) => C.answer(BD[9], q[0], bnow)), ansD = C.QUESTIONS.map((q) => C.answer(BD[7], q[0], bnow));
  o.people = [PP.length, C.personId('chrysos') + '|' + C.personId('lit') + '|' + C.personId('kalshi') + '|' + C.personId('mind') + '|' + C.personId('cronos'), C.builderIds('worktree-agent-a8fa04fb59e01df25').join('|'), C.builderIds('').length, new Set(PP.map((x) => x.pid)).size === PP.length && new Set(PP.map((x) => x.key)).size === PP.length,
    C.HALLS.map((h) => C.peopleHere(PP, h.id).length).join() + ',' + C.peopleHere(PP, 'camp').length, PP.every((x) => x.name && x.line && x.word && x.title && x.pids.length), C.talkTarget({ x: 4.3, z: 5.9 }, PP).key, C.talkTarget({ x: 6.5, z: 9 }, PP), C.talkTarget({ x: 0.5, z: 12.4 }, PP).key,
    new Set(PP.map((x) => JSON.stringify(C.lookOf(x.look)))).size >= 12, C.QUESTIONS.map((q) => q[0]).join()];
  o.answers = [ansC.map((a) => a.text), ansC.every((a) => a.text && a.sources.join() === 'cronos/status.json'), ansS[2].text + '|' + ansS[2].sources.join(), ansS[5].text, ansB.map((a) => a.text), ansJ[3].text, ansJ[5].text, ansD[3].text, ansB[0].sources.join(), ansJ[0].sources.join(),
    C.answer(null, 'doing', now).text, C.answer(by(real1, 'chrysos'), 'sure', now).text, !/[<>]/.test(JSON.stringify(C.QUESTIONS.map((q) => C.answer(evilRow, q[0], now)))), C.answer(by(W, 'kalshi'), 'next', now, C.suggestions(W, demo.queue, now)).text];
  let p = { x: C.START.x, z: C.START.z }, inside = false, crossed = 0; const path = [];
  for (let i = 0; i < 400; i++) { p = C.walk(p, 0, { fwd: 1, side: 0 }, 0.05, st); if (st.some((s) => Math.hypot(p.x - s.x, p.z - s.z) < C.STATION_R - 1e-6)) inside = true; path.push(C.hallOf(p).id); }
  let w2 = { x: 2, z: 5 }; for (let i = 0; i < 200; i++) w2 = C.walk(w2, 0, { fwd: 1, side: 0 }, 0.05, st);                // north from the Library, not at a door: the wall holds
  let w3 = { x: -4, z: -5 }; for (let i = 0; i < 300; i++) w3 = C.walk(w3, -Math.PI / 2, { fwd: 1, side: 0 }, 0.05, st);     // east through the Money / Trading door
  o.walk = [!inside, path[0] === 'library' && path[path.length - 1] === 'trading', p.z < -5, w2.z === C.WALL_T && w2.x === 2, C.hallOf(w3).id === 'trading' && w3.x > 4, Math.abs(C.walk({ x: 5, z: 5 }, 0, { fwd: 1 }, 1, []).z - 4.66) < 1e-9, C.walk({ x: 5, z: 5 }, Math.PI / 2, { fwd: 1 }, 0.1, []).x < 5, C.nearest({ x: 3, z: -6 }, st).id, C.nearest({ x: 6.5, z: 8 }, st, 1)];
  let e = 0; for (let i = 0; i < 60; i++) e = C.ease(e, 1, 1 / 60, 9);
  o.ease = [C.ease(0, 1, 0.016, 9) > 0 && C.ease(0, 1, 0.016, 9) < 0.2, e > 0.99 && e <= 1, C.ease(0, 1, 0.016, 0) === 1, C.ease(0.5, 0.5, 0.1, 9) === 0.5, Math.abs(C.ease(0, 1, 0.032, 9) - C.ease(C.ease(0, 1, 0.016, 9), 1, 0.016, 9)) < 1e-9];
  const tour = []; for (let t = 0; t < C.TOUR_S; t += 0.5) tour.push(C.tourCam(t, false));
  const step = Math.max(...tour.slice(1).map((c, i) => Math.hypot(c.x - tour[i].x, c.z - tour[i].z)));
  o.tour = [tour.every((c) => Math.abs(c.x) < C.BOUNDS.x && Math.abs(c.z) < C.BOUNDS.z && c.y > 5 && c.look.y < 2), new Set(tour.map((c) => c.hall)).size, step < 0.5, C.tourCam(0, false).hall, C.tourCam(5, true).y === C.tourCam(50, true).y && C.tourCam(5, true).x === 0, Math.hypot(C.tourCam(C.TOUR_S, false).x - C.tourCam(0, false).x, C.tourCam(C.TOUR_S, false).z - C.tourCam(0, false).z) < 1e-6];
  const fc = C.followCam(st[0], 3, true);
  o.follow = [fc.look.x === st[0].x, fc.z > st[0].z, fc.y > 1.5];
  // the day replay
  const E = C.stream(demo, W, now), w24 = C.replayWindow(E, now, '24h'), w7 = C.replayWindow(E, now, '7d');
  o.stream = [E.length >= 25, E.every((x, i) => i === 0 || E[i - 1].t <= x.t), E.every((x) => x.t <= now + H && x.who && x.name && x.text && C.IDS.includes(x.who)), [...new Set(E.map((x) => x.kind))].sort().join(), E.every((x) => x.sample), new Set(E.map((x) => x.who + x.t + x.text)).size === E.length, E.filter((x) => !x.ok).map((x) => x.who).sort().join()];
  o.win = [w24.events.length, w7.events.length, w24.events.every((x) => w7.events.includes(x)), w24.fails, w7.fails, w24.shifted, w24.note, w24.t1 === now && w24.span === D && w7.span === 7 * D, C.replayWindow(E, now, 'zz').range];
  const far = C.replayWindow(E, now + 60 * D, '24h'), none = C.replayWindow([], now, '7d');
  o.shift = [far.shifted, far.events.length > 0, far.t1 === E[E.length - 1].t, /Nothing ran in the last 24 hours/.test(far.note), none.events.length, none.note, C.replayAt(none, 0.5).done, C.lastFailure(none, 1)];
  const a0 = C.replayAt(w7, 0), a5 = C.replayAt(w7, 0.5), a1 = C.replayAt(w7, 1), aJ = C.replayAt(w7, NaN);
  o.at = [a0.done, a1.done === w7.events.length, a5.done <= a1.done && a5.done >= a0.done, a1.recent.length <= 6 && a1.recent.every((x, i) => i === 0 || a1.recent[i - 1].t >= x.t), a1.recent[0].t === E[E.length - 1].t, a1.active.length > 0 && a1.active.every((id) => C.IDS.includes(id)), aJ.f === 1, Object.values(a1.counts).reduce((s, n) => s + n, 0) === a1.done, C.replayAt(w7, 5).f, C.replayAt(w7, -5).f];
  const lf = C.lastFailure(w24, 1), lf7 = C.lastFailure(w7, 1), early = C.lastFailure(w7, 0.01), okWin = C.replayWindow(E.filter((x) => x.ok), now, '7d');
  o.fail = [lf.e.who, lf.e.ok, lf.f > 0 && lf.f < 1, /FAILED/.test(lf.e.text), lf7.e.t >= C.lastFailure(w7, lf7.f).e.t, C.lastFailure(w7, lf7.f).e.who, early.e.t === lf7.e.t, C.lastFailure(okWin, 1), C.replayAt(w7, lf7.f + 0.001).recent.some((x) => !x.ok)];
  const ln = C.lanes(w7);
  o.lanes = [ln.length, ln.every((r) => r.ticks.length && r.ticks.every((t) => t.f >= 0 && t.f <= 1)), ln.reduce((s, r) => s + r.ticks.length, 0) === w7.events.length, C.nextEvent(w7, 0) > 0, C.nextEvent(w7, 1), C.clockText(Date.parse('2026-11-10T06:05:00Z')), C.clockText(null)];
  const RE = C.stream({ queue: real }, real1, Date.parse('2026-11-12T00:00:00Z'));
  o.realStream = [RE.length >= 30, RE.every((x) => !x.sample), RE.some((x) => x.kind === 'run') && RE.some((x) => x.kind === 'writeup'), C.replayWindow(RE, Date.parse('2027-06-01T00:00:00Z'), '7d').shifted];
  // the pipeline wall
  const P = C.pipeline(real, false), PD = C.pipeline(demo.queue, true), P0 = C.pipeline(null), PJ = C.pipeline({ pipeline: { counts: { ideas: 'x', adopted: -4 }, families: [null, { name: '<b>f</b>', runs: 0, adopted: 9 }], moves: [null, { id: '<i>', verdict: 'zz' }] } });
  o.pipe = [P.ok, P.lanes.map((l) => l.id).join(), P.lanes.map((l) => l.n).join() === [real.pipeline.counts.ideas, real.pipeline.counts.testing, real.pipeline.counts.adopted, real.pipeline.counts.rejected].join(), P.lanes[0].n === P.lanes[1].n + P.lanes[2].n + P.lanes[3].n,
    P.families.every((f) => Math.abs(f.pa + f.pr + f.po - 1) < 1e-9 && f.href.startsWith('../archive/?find=')), P.moves.length === 20 && P.moves.every((m) => m.href.startsWith('../archive/?find=') && ['adopted', 'rejected', 'open'].includes(m.verdict)), P.lanes.every((l) => l.href.startsWith('../archive/')), /ideas were tested and stored/.test(P.line),
    PD.sample && PD.ok && PD.lanes[0].n === 240, P0.ok, P0.line, PJ.ok, !/[<>]/.test(JSON.stringify(PJ)), PJ.moves[0].verdict];
  // the learning board
  const B = C.board(demo.queue, W, now, true), BR = C.board(real, real1, Date.parse('2026-11-11T12:00:00Z'), false), B0 = C.board(null, [], now);
  o.board = [B.week.length >= 5 && B.week.length <= 8, B.week.every((l, i) => i === 0 || B.week[i - 1].strength >= l.strength), B.week[0].strength, B.all.every((l) => l.sources.length && l.sources.every((s) => s.src) && C.CATS.includes(l.cat) && l.strength >= 1), B.top[0].strength >= B.top[B.top.length - 1].strength, B.top[0].strength,
    Object.values(B.cats).reduce((s, n) => s + n, 0) === B.all.length, B.changed.length, B.changed[0].was, B.all.every((l) => l.sample), new Set(B.all.map((l) => l.text.toLowerCase())).size === B.all.length, /Example lessons/.test(B.note), Object.keys(B.cats).filter((c) => B.cats[c] > 0).length];
  const dup = C.board({ lessons: [{ text: 'Same lesson here.', cat: 'Kalshi', who: 'kalshi', d: '2026-11-09', strength: 2, sources: [{ src: 'a.md', d: '2026-11-09' }, { src: 'b.md' }] }, { text: 'same  LESSON here', cat: 'Kalshi', who: 'kalshi', d: '2026-11-08', strength: 1, sources: [{ src: 'c.md' }] }, { text: 'No source lesson.', sources: [] }, { text: 'Bad cat.', cat: 'zz', who: 'nobody', d: 'x', strength: 'q', sources: [{ src: 's.md' }] }] }, [], now);
  o.boardReal = [BR.all.length >= 20, BR.all.every((l) => l.sources.length && !l.sample), BR.changed.some((c) => c.was === '95c and above is +1.4% per $' && /kalshi_edge_A\.md$/.test(c.src) && c.cat === 'Kalshi'), BR.week.length, BR.week.every((l) => l.week), /Strength counts the independent files that agree/.test(BR.note),
    dup.all.length, dup.all[0].strength, dup.all[1].cat + '|' + dup.all[1].who + '|' + dup.all[1].strength + '|' + (dup.all[1].ms === null), B0.all.length, B0.note, C.strengthWord(1), C.strengthWord(3)];
  // the planner
  const S = C.suggestions(W, demo.queue, now), SR = C.suggestions(real1, real, now);
  o.sugg = [S.map((s) => s.title), S.every((s, i) => i === 0 || S[i - 1].w >= s.w), S.every((s) => s.next && s.why && s.ev && s.kind && s.rank), C.suggestions(C.buildWorkers({ home: { accounts: [] } }, now).map((w) => Object.assign({}, w, { status: 'working', missing: false, n: null })), { queue: { open: 0 } }, now)[0].title,
    S.map((s) => s.kind).join(), S.map((s) => s.rank).join('') === '12345678'.slice(0, S.length), S.length <= 8, SR.map((s) => s.title), SR.filter((s) => s.kind === 'gap').length, !S.some((s) => /\$\d/.test(s.ev))];
  // junk and hostile text
  const evilIn = { home: 5, money: { streams: [null, 3, { id: 'chrysos', name: '<b>x</b>', headline: '<img src=x onerror=alert(1)>', items: [{ title: '<script>1</script>' }, null], notes: [7, '<i>n</i>'] }] }, kalshi: 'q', cron: { tasks: { z: 5, '<k>': { ok: false, last_run_t: now / 1000, error: '<e>' } } }, forge: [], heph: 'x',
    queue: { learnings: [null, { who: 'chrysos', text: '<u>t</u>', src: '<s>' }, { who: 'zzz' }], queue: { open: 'x', tasks: [null, { id: '<x>', text: 'ok' }] }, mind: 3, git: { commits: [null, { t: 'zz', s: '<q>' }, { t: now / 1000, s: '<c>' }] }, rejected: [null, 4], writeups: { latest: [null] },
      events: [null, 5, { t: now / 1000 - 60, who: '<w>', text: '<b>e</b>', src: '<s>', kind: '<k>' }, { t: 'x', who: 'lit', text: 'no time' }], money_runs: 'x', lessons: [null, { text: '<b>l</b>', sources: [{ src: '<s>' }] }], changed: [null, { text: '<i>c</i>', src: '<s>', was: '<w>' }], pipeline: { counts: null, families: 'x', moves: [{ id: '<m>' }] }, gaps: [null, { name: '<g>', last: '2026-01-01' }] } };
  const evil = C.buildWorkers(evilIn, NaN), evilW = C.buildWorkers(evilIn, now), eS = C.stream(evilIn, evilW, now), eW = C.replayWindow(eS, now, '24h');
  const raw = JSON.stringify([evil, evilW, eS, C.board(evilIn.queue, evilW, now), C.pipeline(evilIn.queue), C.suggestions(evilW, evilIn.queue, now), C.lanes(eW), C.replayAt(eW, 1)]);
  o.junk = [evil.length, !/[<>]/.test(raw), C.buildWorkers(null, now).length, C.events(null || [], now).length, C.lessons([], now).length, C.suggestions([], null, now).length, C.toMs('zz'), C.toMs('2026-11-10 02:00') === Date.parse('2026-11-10T02:00:00Z'), C.toMs(1793394000) === 1793394000000, C.toMs(1793394000000) === 1793394000000, C.money(-1420), C.moneyS(312), C.agoText(null, now), C.agoText(now - 5 * 60000, now), C.agoText(now - 3 * H, now), C.agoText(now - 5 * D, now),
    eS.length >= 2 && eS.every((x) => C.IDS.includes(x.who)), C.stream(null, null, now).length, C.stream('x', 5, NaN).length];
  const card = C.jarvisCard(W, demo.queue, now, true);
  o.card = [card.name, card.status.level, card.status.label, card.kpis.length, card.kpis[1].value, card.lines.length, Number.isInteger(card.t), JSON.stringify(card).length < 8192];
  console.log(JSON.stringify(o));
});
"""


def test_maths():
    out = AK.node(APP, HARNESS, os.path.join(D, "fixture.json"), os.path.join(D, "queue.json"), os.path.join(D, "builders.json"))
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
    check("b. each worker's own lessons: at most 12, each with its source, newest first, at most 3 from one worker, the week flagged", out["lessons"][:5] == [True, True, True, True, True] and out["lessons"][5] >= 5, out["lessons"])
    check("b. FOUR HALLS (Money, Trading, Research, Library) joined by 4 doors; every station stands well inside its own hall, has one of the 5 jobs, and no two platforms touch; the front door is in the Library",
          out["halls"][0] == "Money hall,Trading hall,Research hall,Library" and out["halls"][1] == 4 and out["halls"][2] and out["halls"][3] and out["halls"][4] == 5 and out["halls"][5] == "5,4,4,2" and out["halls"][6] and out["halls"][7] == "moneytradingresearchlibrary" and out["halls"][8] == "library" and out["halls"][9] == "library", out["halls"])
    check("b. speech bubbles: a failed worker says its run failed, a missing file says so, a worker with a dated lesson says that lesson, a stale one says 'Old news'; every bubble is short; crates = its outputs (at most 5) with short tags",
          out["say"][0].startswith("My last run failed.") and out["say"][1].startswith("No file from me yet") and out["say"][2] == "Example: only 1 pick survives out-of-sample." and out["say"][3].startswith("Old news: ") and out["say"][4] and out["say"][5]
          and out["say"][6] == "cities-layout|inbox-noise|ledger-headline|gate-full-run" and out["say"][7] == "a new app page" and out["say"][8] == "output" and out["say"][9], out["say"])
    check("b. collision: an inner wall pushes you back to its face on your side, a door lets you through, a door jamb does not, a platform is solid, the outer walls hold", out["walls"] == [True] * 8, out["walls"])
    check("b. THE BUILDERS' CAMP lies outside the front door: the south wall still holds except in the doorway, the camp has its own bounds, a tent is solid, walking south from the front door takes you out into the camp, 10 tent spots with room between them, the factory keeps its 4 halls",
          out["camp"][:9] == [True] * 9 and out["camp"][9] == 10 and out["camp"][10] == "Builders' camp" and out["camp"][11] and out["camp"][12] and out["camp"][13] == 4, out["camp"])
    check("b. builders (demo): 10 example agents: working (a commit in the last 15 minutes), quiet, done (merged, its scroll reads 'Shipped: ...'), job only (no git: 'Job only, no live activity', no commits invented); crates = commits today; All hands orders working first and counts add up",
          out["builders"][0] == 10 and out["builders"][1] == "working,working,working,working,quiet,quiet,quiet,done,quiet,job" and out["builders"][2] and out["builders"][3] == "10 build agents: 4 working now, 4 quiet, 1 done, 1 with a job line only. Example agents, not the real ones."
          and out["builders"][4].startswith("working,working,working,working,quiet") and out["builders"][4].endswith("done,job") and out["builders"][5:] == [True] * 5, out["builders"])
    check("b. builders (the repo's builders.json, and the same agents WITHOUT git): real rows are never flagged sample; without git every agent is 'job only' with no commits and the note says so; 5 min = working, 16 min = quiet, merged = done, not live or no time = job; junk is cleaned; at most 10 tents",
          out["buildersReal"][:4] == [True] * 4 and "no live activity" in out["buildersReal"][4] and out["buildersReal"][5] and out["buildersReal"][6:11] == ["working", "quiet", "done", "job", "job"] and out["buildersReal"][11] == 0
          and out["buildersReal"][12].startswith("No build agents are listed") and out["buildersReal"][13] and out["buildersReal"][14] == 10, out["buildersReal"])
    check("b. PEOPLE: 25 individuals (15 workers + 10 builders), each with a stable person id (scanner:chrysos, bot:lit, bot:kalshi, mind, villager:cronos, builder:<branch-short>), a one-liner and its hall; 'People here' = 5 / 4 / 4 / 2 and 10 in the camp; the Talk prompt needs you within 3 m; looks differ",
          out["people"][0] == 25 and out["people"][1] == "scanner:chrysos|bot:lit|bot:kalshi|mind|villager:cronos" and out["people"][2] == "builder:a8fa04fb59e01df25|builder:a8fa04fb" and out["people"][3] == 0 and out["people"][4] and out["people"][5] == "5,4,4,2,10" and out["people"][6]
          and out["people"][7] == "w:queue" and out["people"][8] is None and out["people"][9] == "b:camp1" and out["people"][10] and out["people"][11] == "doing,last,learned,stuck,next,sure", out["people"])
    a = out["answers"]
    check("b. the built-in chat answers six questions from the worker's own row only: a failed worker says 'Yes' it is stuck and names its planner step; a lesson comes with its source; sample data is 'not at all' sure; nothing invented when there is no file",
          "scheduled jobs" in a[0][0] and a[0][1].startswith("My last output") and a[0][3].startswith("Yes. ") and a[0][4].startswith("Cronos failed its last run. First step: ") and a[0][5].startswith("Not at all: these are example numbers") and a[1]
          and a[2] == "Example: only 1 pick survives out-of-sample. (2026-11-10)|money/sibyl.json" and a[10] == "I have nothing on record." and a[11] == "I cannot be: I have no file to read." and a[12] and "only 4 settled trades" in a[13], (a[0], a[2], a[11]))
    check("b. a builder answers from git: its job and status, its last commit with its age, 'No: I committed 4 min ago', what git can vouch for; a job-only agent says it cannot tell (no live activity); a merged one is not stuck",
          a[4][0].startswith("My job: Example: a calm look in every app. Working: last commit 4 min ago.") and a[4][1].startswith("My last commit, 4 min ago: ") and a[4][3] == "No: I committed 4 min ago." and "example builder" in a[4][5]
          and a[5].startswith("I cannot tell you: there is no live activity") and a[7] == "No: my work is merged into the release." and a[8] == "builders.json (git at build time)" and a[9] == "handoff/agents_now.json", (a[4], a[5]))
    check("b. walking: straight ahead from the front door you cross the Library and go THROUGH the door into the Trading hall without ever entering a platform; away from a door the wall stops you; east from the Money hall you reach the Trading hall; forward is -z, yaw turns",
          out["walk"][:7] == [True] * 7 and out["walk"][7] == "lit" and out["walk"][8] is None, out["walk"])
    check("b. smooth controls: easing moves part of the way each frame, arrives, is frame-rate independent (two half frames = one frame), and jumps at once under reduced motion (rate 0)", out["ease"] == [True] * 5, out["ease"])
    check("b. the calm tour: one closed lap that stays above the factory, looks down, passes all 4 halls, never jumps, starts over the Library; reduced motion gets one still view of everything", out["tour"][0] and out["tour"][1] == 4 and out["tour"][2] and out["tour"][3] == "library" and out["tour"][4] and out["tour"][5], out["tour"])
    check("b. follow camera: behind and above the worker, looking at it", out["follow"] == [True, True, True], out["follow"])
    check("b. the replay stream merges every dated source oldest first (research runs, write-ups, the Mind, the queue, commits, money machines, every Cronos job, each worker's last run), never in the future, no duplicates; the demo's events are all flagged sample; its failures are Cronos and Arbiter",
          out["stream"][:3] == [True, True, True] and {"commit", "job", "money", "run", "writeup", "mind", "task"} <= set(out["stream"][3].split(",")) and out["stream"][4] and out["stream"][5] and out["stream"][6] == "arbiter,cronos", out["stream"])
    check("b. the replay window: last 24 h is inside last 7 days, failures are counted, the note says how many events / workers / failed, an unknown range falls back to 24 h",
          0 < out["win"][0] < out["win"][1] and out["win"][2] and out["win"][3] == 1 and out["win"][4] == 2 and out["win"][5] is False and re.match(r"\d+ events from \d+ workers, 1 failed\.", out["win"][6]) and out["win"][7] and out["win"][8] == "24h", out["win"])
    check("b. an empty window is honest: it moves back to end on the newest event and SAYS 'Nothing ran in the last 24 hours'; no events at all says so and nothing throws",
          out["shift"][:4] == [True, True, True, True] and out["shift"][4] == 0 and out["shift"][5] == "No dated events at all yet." and out["shift"][6] == 0 and out["shift"][7] is None, out["shift"])
    check("b. scrubbing: at the start nothing has happened, at the end everything has; the last 6 events newest first; who is busy at the cursor; the counts add up; the cursor is clamped to 0..1",
          out["at"][0] == 0 and out["at"][1:8] == [True] * 7 and out["at"][8] == 1 and out["at"][9] == 0, out["at"])
    check("b. 'jump to last failure': the newest failed event (Cronos in the last 24 h), pressing again goes to the one before it (Arbiter, in the 7 days), from the very start it still finds the newest, a clean window gives none",
          out["fail"][0] == "cronos" and out["fail"][1] is False and out["fail"][2] and out["fail"][3] and out["fail"][4] and out["fail"][5] == "arbiter" and out["fail"][6] and out["fail"][7] is None and out["fail"][8], out["fail"])
    check("b. the lane strip: one row per worker that ran, every mark inside the window, as many marks as events; 'next event' steps forward (reduced motion play); the clock is plain UTC text",
          out["lanes"][0] >= 10 and out["lanes"][1] and out["lanes"][2] and out["lanes"][3] and out["lanes"][4] == 1 and out["lanes"][5] == "Tue 11-10 06:05 UTC" and out["lanes"][6] == "", out["lanes"])
    check("b. the REAL event stream (queue.json of the repo): research runs and write-ups, nothing flagged sample; months later the window honestly shifts back to the newest event", out["realStream"] == [True, True, True, True], out["realStream"])
    check("b. the pipeline wall: lanes Idea, Testing, Adopted, Rejected carry the builder's counts (idea = testing + adopted + rejected), every family's bar adds to 100% and links into the Archive, 20 newest moves; the demo is flagged sample; no data says so; junk is cleaned",
          out["pipe"][0] and out["pipe"][1] == "ideas,testing,adopted,rejected" and out["pipe"][2:9] == [True] * 7 and out["pipe"][9] is False and out["pipe"][10] == "No pipeline counts are published yet." and out["pipe"][11] is False and out["pipe"][12] and out["pipe"][13] == "open", out["pipe"])
    check("b. the Learning board (demo): the week's lessons strongest first (3 files agree on top), every lesson has sources and a category, the strongest overall has 4, counts per category add up, 'what changed our mind' keeps the old belief, all flagged example, 5 categories used",
          out["board"][0] and out["board"][1] and out["board"][2] == 3 and out["board"][3] and out["board"][4] and out["board"][5] == 4 and out["board"][6] and out["board"][7] == 2 and out["board"][8] == "95c and above is +1.4% per $" and out["board"][9] and out["board"][10] and out["board"][11] and out["board"][12] == 5, out["board"])
    check("b. the Learning board (real queue.json): 20+ lessons each with its source, the Kalshi 95c flip is on 'what changed our mind' with its file; the same words twice are one lesson, a lesson with no source is dropped, a bad category / worker / strength is repaired; no data says so",
          out["boardReal"][0] and out["boardReal"][1] and out["boardReal"][2] and out["boardReal"][4] and out["boardReal"][5] and out["boardReal"][6] == 2 and out["boardReal"][7] == 2 and out["boardReal"][8] == "process|dev|1|true" and out["boardReal"][9] == 0
          and out["boardReal"][10] == "No lessons are written down yet." and out["boardReal"][11:] == ["1 file so far", "3 files agree"], out["boardReal"])
    t = out["sugg"][0]
    check("b. 'what next' planner: ranked by weight, a failure first, then stale feeds, data gaps, small samples, open runs, a changed belief, the queue; every row has a why, a 'worth it' in plain words (never a dollar guess) and a first step; nothing to do says so",
          t[0] == "Cronos failed its last run" and "Oikos is stale" in t and any("only 4 settled trades" in x for x in t) and any("data sets end weeks before" in x for x in t) and any("runs with no verdict" in x for x in t) and any("belief changed" in x for x in t) and any("open tasks" in x for x in t)
          and out["sugg"][1] and out["sugg"][2] and out["sugg"][3] == "Nothing is waiting" and out["sugg"][5] and out["sugg"][6] and out["sugg"][9], out["sugg"])
    check("b. the planner on the real repo with no worker files: the many missing stations are ONE row ('N workers have no file here'), not eight", out["sugg"][8] == 1 and any(re.match(r"\d+ workers have no file here", x) for x in out["sugg"][7]), out["sugg"][7])
    check("b. junk and hostile input: nothing throws (workers, stream, board, pipeline, planner, lanes), no '<' or '>' survives into any text, an unknown worker becomes the dev agents, bad dates give null, money words are plain",
          out["junk"][0] == 15 and out["junk"][1] and out["junk"][2] == 15 and out["junk"][3:6] == [0, 0, 1] and out["junk"][6] is None and out["junk"][7:10] == [True, True, True] and out["junk"][10:12] == ["-$1,420", "+$312"] and out["junk"][12:16] == ["no time on record", "5 min ago", "3 h ago", "5 days ago"]
          and out["junk"][16] and out["junk"][17:] == [0, 0], out["junk"])
    check("b. the Jarvis card: Ergasterion, 'off' in demo, 3 kpis, the headline and the newest lesson, an integer t, under 8 KB", out["card"][:3] == ["Ergasterion", "off", "Demo data"] and out["card"][3] == 3 and out["card"][4] == "2" and out["card"][5] in (1, 2) and out["card"][6] and out["card"][7], out["card"])

# ------------------------------------------------------------------------------------------------ LIFE on the floor (life.js, 2026-11-11 world director): the day, the events, the kits
LIFE_HARNESS = r"""
const url = require('url');
Promise.all([import(url.pathToFileURL(process.argv[2]).href), import(url.pathToFileURL(process.argv[3]).href)]).then(([L, C]) => {
  const o = {}, S = C.STATIONS, byHall = {}; S.forEach((s, i) => { (byHall[s.hall] = byHall[s.hall] || []).push(i); });
  const who = (i) => ({ i, hall: S[i].hall, home: { x: S[i].x, z: S[i].z - 0.12 }, k: byHall[S[i].hall].indexOf(i), n: byHall[S[i].hall].length });
  const day = (sod, opt) => S.map((s, i) => L.scheduleAt(who(i), sod, opt || {}));
  o.clock = [L.secOfDay(Date.UTC(2026, 10, 11, 9, 33, 0), 0), L.secOfDay(Date.UTC(2026, 10, 11, 9, 33, 0), -120), L.clockWord('quiet'), L.clockWord('09:30'), L.clockWord('25:00'), L.secOfDay(L.atClock(L.QUIET))];
  o.same = JSON.stringify(day(34380)) === JSON.stringify(day(34380)) && JSON.stringify(day(40000)) === JSON.stringify(day(40000));
  const su = day(34380, {});                                          // 09:33: the stand-up
  o.standup = Object.keys(byHall).map((h) => { const A = byHall[h].map((i) => su[i]); const G = L.GATHER[h]; return [h, A.filter((a) => a.act === 'speak').length, A.every((a) => a.act === 'standup' || a.act === 'speak'), Math.max(...A.map((a) => Math.hypot(a.x - G.x, a.z - G.z)))]; });
  const sf = S.map((s, i) => L.scheduleAt(who(i), 34380, { failed: i === 12 }));
  o.failedStays = [sf[12].act, sf[12].x === S[12].x, day(34380, { reduced: true }).every((a) => a.act === 'work' && !a.away)];
  o.quiet = day(L.QUIET).every((a) => a.act === 'work' && !a.away);
  // the whole day at 2 s: nobody leaves its hall or walks through another worker's spot; every worker reads its board ~48 times; a hall is never empty
  let out = 0, through = 0, empty = 0; const visits = S.map(() => 0), prev = S.map(() => 'work');
  for (let sod = 0; sod < 86400; sod += 2) { const D = day(sod);
    D.forEach((a, i) => { const h = C.HALLS.find((x) => x.id === S[i].hall); if (a.x < h.x0 + 0.4 || a.x > h.x1 - 0.4 || a.z < h.z0 + 0.4 || a.z > h.z1 - 0.4) out++;
      S.forEach((q, j) => { if (j !== i && Math.hypot(q.x - a.x, q.z - 0.12 - a.z) < 0.8) through++; }); if (a.act === 'board' && prev[i] !== 'board') visits[i]++; prev[i] = a.act; });
    if (!(sod >= 34200 && sod < 34560)) for (const h in byHall) if (!byHall[h].some((i) => D[i].act === 'work')) empty++; }
  o.dayWalk = [out, through, Math.min(...visits), Math.max(...visits), empty];
  // the camp: a working builder carries a crate to the cart and walks back; quiet ones less often; done / job stay
  const home = { x: C.CAMP_SPOTS[1].x, z: C.CAMP_SPOTS[1].z - 1.9 }, seen = new Set(); let minD = 99;
  for (let s = 0; s < 80; s += 0.25) { const a = L.campAt(1, home, 'working', s, {}); seen.add(a.act + (a.crate ? '+crate' : '')); if (a.act === 'drop') minD = Math.min(minD, Math.hypot(a.x - L.CART.x, a.z - L.CART.z)); }
  let quietTrips = 0; for (let s = 0; s < 300; s += 1) if (L.campAt(1, home, 'quiet', s, {}).act === 'carry') quietTrips++;
  o.camp = [[...seen].sort().join(','), +minD.toFixed(2), quietTrips > 0 && quietTrips < 30, L.campAt(1, home, 'job', 10, {}).act, L.campAt(1, home, 'working', 10, { reduced: true }).act, L.cartCount([{ today: 3 }, { today: 30 }, { today: null }, null])];
  const g = L.campAt(2, home, 'job', 1000 + 6, { gatherAt: 1000, n: 10 }); o.campGather = [g.act, Math.hypot(g.x - L.GATHER.camp.x, g.z - L.GATHER.camp.z) < 2.2];
  // events: only real changes; nothing without a previous snapshot; a sample pipeline never celebrates
  const snap0 = L.snapshot([{ id: 'lit', status: 'working' }], [{ branch: 'b1', status: 'quiet', today: 2 }], { lanes: [{ id: 'adopted', n: 3 }] }, { accounts: [{ id: 'mffu', eval: { room: 1 } }] });
  const snap1 = L.snapshot([{ id: 'lit', status: 'failed' }], [{ branch: 'b1', status: 'done', today: 4 }], { lanes: [{ id: 'adopted', n: 4 }] }, { accounts: [{ id: 'mffu', eval: { passed: true } }] });
  o.events = [L.diffEvents(null, snap1).length, L.diffEvents(snap0, snap1).map((e) => e.kind).join(), L.diffEvents(snap1, snap1).length, L.diffEvents(snap0, { ...snap1, sample: true }).map((e) => e.kind).includes('adopted'), L.diffEvents(snap0, snap1).filter(L.isBig).length];
  const now = Date.parse('2026-11-11T12:00:00Z');
  o.recent = [L.recentMerges([{ status: 'done', branch: 'x', name: 'X', shipped: [{ t: now - 10 * 60000 }] }, { status: 'done', branch: 'y', name: 'Y', shipped: [{ t: now - 90 * 60000 }] }, { status: 'done', sample: true, branch: 'z', name: 'Z', shipped: [{ t: now - 60000 }] }], now, 30).map((e) => e.who).join()];
  // the hammer: one hit per quarter turn of 2 pi; the LOD picker: nearest first, capped, the shown one kept a little longer
  o.hits = [L.hits(0, Math.PI / 2), L.hits(0, 2 * Math.PI), L.hits(1, 1.01) + L.hits(1.01, 1.02)];
  o.lod = [L.nearSet([{ key: 'a', d: 3 }, { key: 'b', d: 1 }, { key: 'c', d: 9 }], 2, 4.6, []).join(), L.nearSet([{ key: 'a', d: 3 }, { key: 'b', d: 1 }], 1, 4.6, []).join(), L.nearSet([{ key: 'a', d: 5.2 }], 1, 4.6, ['a']).join(), L.nearSet([{ key: 'a', d: 5.2 }], 1, 4.6, []).length, L.nearSet(null, 2, 4).length];
  // the optional kits: no window = nothing happens, nothing throws; a stub window gets the calls
  o.noKit = [L.burst('sparks', { x: 1, y: 2 }, [0, 0, 0]), L.soundAt('clank', { x: 0, y: 0, z: 0 }, 'success'), L.sayLine('mind', 'hi'), L.showWork('mind', {})];
  const calls = []; global.window = { OLYMPUS_FX: { burst: (k, at) => calls.push('burst:' + k + ':' + (at.world ? at.world.length : 0)) }, OLYMPUS: { sound: Object.assign(() => true, { at: (n) => calls.push('at:' + n) }), cue: (n) => calls.push('cue:' + n) },
    OLYMPUS_PEOPLE: { say: (id, t, op) => calls.push('say:' + id + ':' + op.scene), show: (id, w) => calls.push('show:' + id + ':' + w.kind) } };
  o.kit = [L.burst('sparks', { x: 1, y: 2 }, [1, 2, 3]), L.soundAt('clank', {}, 'success'), L.sayLine('mind', 'hello', { scene: 'ergasterion' }), L.showWork('mind', { kind: 'work' }), calls.join('|')];
  global.window = { OLYMPUS_FX: { confetti: () => calls.push('confetti'), sparkleBurst: () => calls.push('sparkle') }, OLYMPUS: { cue: (n) => calls.push('cue:' + n) }, OLYMPUS_PEOPLE: { say: () => { throw new Error('x'); } } };
  o.old = [L.burst('confetti', { x: 1, y: 2 }), L.burst('sparks', { x: 1, y: 2 }), L.soundAt('fanfare', {}, 'success'), L.soundAt('clank', {}), L.sayLine('mind', 'hi')];
  console.log(JSON.stringify(o));
}).catch((e) => { console.error(e && e.stack || e); process.exit(1); });
"""


def test_life():
    exe = shutil.which("node")
    if not exe:
        check("b. node is not installed: the LIFE checks are skipped", True)
        return
    tmp = tempfile.mkdtemp(prefix="ag-erg-life-")
    try:
        life, core = os.path.join(tmp, "life.mjs"), os.path.join(tmp, "core.mjs")
        shutil.copy(os.path.join(D, "life.js"), life)
        shutil.copy(os.path.join(D, "ergasterioncore.js"), core)
        h = os.path.join(tmp, "h.cjs")
        with open(h, "w", encoding="utf-8") as fh:
            fh.write(LIFE_HARNESS)
        r = subprocess.run([exe, h, life, core], capture_output=True, text=True, timeout=120)
        if r.returncode:
            check("b. LIFE: the node harness runs", False, r.stderr[-800:])
            return
        o = json.loads(r.stdout)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    check("b. LIFE clock: 09:33 UTC is second 34380 of the day (and 2 h later two hours east), '?clock=quiet' = 10:05:20, '09:30' reads, '25:00' does not; atClock round-trips",
          o["clock"] == [34380, 34380 + 7200, 36320, 34200, None, 36320], o["clock"])
    check("b. LIFE is deterministic: the same clock gives the same scene, to the centimetre", o["same"])
    check("b. LIFE 09:33 STAND-UP: in each of the four halls everyone is in the ring (<= 1.6 m from the hall's middle) and exactly ONE person speaks",
          all(x[1] == 1 and x[2] and x[3] <= 1.6 for x in o["standup"]) and len(o["standup"]) == 4, o["standup"])
    check("b. LIFE: a worker whose run FAILED stays slumped at its station (no stand-up for it); reduced motion = everyone stays at work", o["failedStays"] == ["work", True, True], o["failedStays"])
    check("b. LIFE '?clock=quiet': at 10:05:20 every worker is at its own station (the moment the 3D tests use)", o["quiet"])
    check(f"b. LIFE over a whole day (2 s steps): nobody leaves its hall ({o['dayWalk'][0]}), nobody walks through another worker's spot ({o['dayWalk'][1]}), every worker reads its queue board {o['dayWalk'][2]}-{o['dayWalk'][3]} times, and no hall is ever left with nobody at work outside the stand-up ({o['dayWalk'][4]})",
          o["dayWalk"][0] == 0 and o["dayWalk"][1] == 0 and o["dayWalk"][2] >= 40 and o["dayWalk"][4] == 0, o["dayWalk"])
    check("b. LIFE camp: a working builder works, carries a crate (crate in its arms) to the cart, sets it down beside it (< 1.2 m) and walks back; a quiet one carries less often; a 'job only' one and reduced motion stay at the table; the cart counts the real commits (33, 24 shown)",
          o["camp"][0] == "carry+crate,drop,walk,work" and o["camp"][1] < 1.2 and o["camp"][2] and o["camp"][3] == "work" and o["camp"][4] == "work" and o["camp"][5] == {"n": 33, "shown": 24}, o["camp"])
    check("b. LIFE camp gathering: for a big number the builders gather round the fire and cheer", o["campGather"] == ["cheer", True], o["campGather"])
    check("b. LIFE events from real data only: no previous snapshot = nothing; a failed run, a merge, new commits, a new adopted run and a passed eval are found; the same snapshot twice = nothing; a SAMPLE pipeline never celebrates an adopted run; 2 big numbers",
          o["events"] == [0, "fail,merge,commit,adopted,eval", 0, False, 2], o["events"])
    check("b. LIFE: a fresh merge (10 min ago) is cheered on the first visit, an old one (90 min) and a sample one are not", o["recent"] == ["x"], o["recent"])
    check("b. LIFE hammer: one blow (sparks + clank) per quarter turn, none in between; the near-figure picker takes the nearest within 4.6 m, honours the cap and keeps a shown figure a little longer",
          o["hits"] == [1, 4, 0] and o["lod"] == ["b,a", "b", "a", 0, 0], (o["hits"], o["lod"]))
    check("b. LIFE kits are optional: with no window nothing is called and nothing throws", o["noKit"] == [False, False, False, False], o["noKit"])
    check("b. LIFE with the new kits: fx.burst('sparks', {x, y, world}), OLYMPUS.sound.at('clank'), OLYMPUS_PEOPLE.say(id, text, {scene}) and show(id, {kind}) are each called once",
          o["kit"][:4] == ["burst", "at", True, True] and o["kit"][4] == "burst:sparks:3|at:clank|say:mind:ergasterion|show:mind:work", o["kit"])
    check("b. LIFE with today's kits: confetti -> FX.confetti, sparks -> FX.sparkleBurst, a big moment -> the 'success' cue, a clank without sound.at -> silence, a say() that throws -> our own bubble",
          o["old"] == ["confetti", "sparkleBurst", "cue", False, False], o["old"])


def test_page():
    try:
        import playwright  # noqa: F401
    except ImportError:
        check("c. page tests skipped: no Playwright", True)
        return
    no3d = os.environ.get("ERG_NO3D") == "1"
    srv, origin = AK.serve()
    try:
        with AK.browser() as br:
            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, APP, "?demo=1&flat=1", hook="ERGASTERION")
            d = p.evaluate("""() => ({ demo: !document.querySelector('#demo').hidden, title: document.querySelector('#heroTitle').textContent, line: document.querySelector('#heroLine').textContent, workers: document.querySelectorAll('#workers button').length,
              groups: [...document.querySelectorAll('#workers .grp')].map((e) => e.textContent), lessons: document.querySelectorAll('#lessons li').length, week: document.querySelectorAll('#lessons li[data-week="1"]').length, srcs: [...document.querySelectorAll('#lessons .src, #strong .src, #changed .src')].every((e) => e.textContent.startsWith('source: ')),
              meta: [...document.querySelectorAll('#lessons .meta')].map((e) => e.textContent), was: [...document.querySelectorAll('#changed .was')].map((e) => e.textContent), strong: document.querySelectorAll('#strong li').length, cats: [...document.querySelectorAll('#cats button')].map((e) => e.textContent),
              ticker: document.querySelectorAll('#ticker li').length, next: [...document.querySelectorAll('#next li b')].map((e) => e.textContent), go: [...document.querySelectorAll('#next .go')].every((e) => e.textContent.startsWith('First step: ')), ev: [...document.querySelectorAll('#next .ev')].every((e) => e.textContent.startsWith('Worth it? ') && e.textContent.length > 25) && document.querySelectorAll('#next .ev').length,
              follow: document.querySelector('#follow').options.length, font: getComputedStyle(document.querySelector('h1')).fontFamily, bg: getComputedStyle(document.body).backgroundColor, legend: document.querySelectorAll('#legend li').length, sheetHidden: document.querySelector('#sheet').hidden, mode: window.ERGASTERION.floor() ? '3d' : 'plan',
              planSay: document.querySelector('#planSay').textContent, halls: [...document.querySelectorAll('#plan text')].map((e) => e.textContent).filter((t) => /hall|Library/.test(t)), icons: document.querySelectorAll('#plan g[role=button] g path').length })""")
            check("c. DEMO: the chip, '1 worker failed' with 'example workers', 15 workers in 5 groups, a ticker, 16 follow options, the legend, no card open yet",
                  d["demo"] and d["title"] == "1 worker failed" and "example workers" in d["line"] and d["workers"] == 15 and d["groups"] == ["Money machines", "NQ bots", "Thinkers", "Jobs", "People and agents"] and d["ticker"] >= 6 and d["follow"] == 16 and d["legend"] == 5 and d["sheetHidden"], d)
            check("c. DEMO Learning board: the week's lessons strongest first ('3 files agree' on top), each with its category, date, 'example' and 'source:'; 'what changed our mind' shows the old belief struck through; strongest overall; 6 category chips with counts",
                  5 <= d["lessons"] <= 8 and d["week"] == d["lessons"] and d["srcs"] and "3 files agree" in d["meta"][0] and "Kalshi" in d["meta"][0] and all("example" in m for m in d["meta"]) and d["was"] == ["We believed: 95c and above is +1.4% per $"] and d["strong"] >= 5
                  and len(d["cats"]) == 6 and d["cats"][0].startswith("All (") and any(c.startswith("Kalshi (") for c in d["cats"]), (d["meta"][:2], d["was"], d["cats"]))
            check("c. DEMO 'what next': ranked (a failure first), each row has 'Worth it?' in plain words and a 'First step:'", d["next"][0] == "1. Cronos failed its last run" and d["go"] and d["ev"] == len(d["next"]) and len(d["next"]) >= 6, d["next"])
            check("c. AGORA look: serif title, warm dark body", any(f in d["font"] for f in ("Palatino", "Iowan", "Georgia")) and d["bg"] == "rgb(20, 17, 14)", d)
            check("c. the floor is 3D or the flat plan, never nothing; the LITE plan names the 4 halls, draws each worker's job as a small icon and lets a worker speak under the plan", d["mode"] in ("3d", "plan") and p.evaluate("() => document.querySelector('#stage').hidden !== document.querySelector('#plan').hidden")
                  and d["halls"] == ["Money hall", "Trading hall", "Research hall", "Library"] and d["icons"] >= 15 and " says: " in d["planSay"], (d["mode"], d["halls"], d["icons"], d["planSay"]))
            AK.shot(p, "ergasterion-demo")
            # PEOPLE, fallback path: the shared kit is not loaded here, so the built-in chat answers
            pe = p.evaluate("""() => ({ kit: !!window.OLYMPUS_PEOPLE, places: [...document.querySelectorAll('#places button')].map((b) => b.textContent), here: [...document.querySelectorAll('#peopleList button')].map((b) => b.getAttribute('aria-label')),
              faces: document.querySelectorAll('#peopleList .mini-face svg').length, chat: document.querySelector('#chatCard').hidden, talk: document.querySelector('#talkBtn').hidden })""")
            check("c. PEOPLE HERE (no kit loaded): 5 places with head counts, the Library's two people each with a face, a status dot and 'Talk to ...'; no chat open yet",
                  pe["places"] == ["Money hall (5)", "Trading hall (4)", "Research hall (4)", "Library (2)", "Builders' camp (10)"] and len(pe["here"]) == 2 and pe["here"][0].startswith("Talk to The queue, Working.") and pe["faces"] == 2 and pe["chat"] and pe["talk"], pe)
            if not pe["kit"]:
                p.locator('#places button[data-place="research"]').click()
                p.locator('#peopleList button[data-key="w:cronos"]').click()
                c0 = p.evaluate("() => ({ hidden: document.querySelector('#chatCard').hidden, h: document.querySelector('#chatH').textContent, pill: document.querySelector('#chatPill').textContent, who: document.querySelector('#chatWho').textContent, log: [...document.querySelectorAll('#chatLog li')].map((e) => e.textContent), qs: [...document.querySelectorAll('#chatQs button')].map((b) => b.textContent), face: document.querySelector('#chatFace').dataset.kit, svg: !!document.querySelector('#chatFace svg') })")
                check("c. TALK (fallback): tapping a person opens the built-in chat: its own face, name, status, 'Built-in answers ... only from its own data' with its person id, its one-liner, and six questions to tap",
                      not c0["hidden"] and c0["h"] == "Cronos" and c0["pill"] == "Failed" and "Built-in answers" in c0["who"] and "villager:cronos" in c0["who"] and "cannot place orders" in c0["who"] and c0["log"] == ["Blocked: My last run failed. Failed: datacity."]
                      and c0["qs"] == ["What are you doing?", "What was your last result?", "What did you learn?", "Are you stuck?", "What is next?", "How sure are you?"] and c0["face"] == "0" and c0["svg"], c0)
                for qid in ("doing", "last", "learned", "stuck", "next", "sure"):
                    p.locator(f'#chatQs button[data-q="{qid}"]').click()
                c1 = p.evaluate("() => [...document.querySelectorAll('#chatLog li')].map((e) => [e.className, e.textContent])")
                check("c. TALK (fallback): each of the six questions is answered from the worker's own data with its source ('Are you stuck?' -> 'Yes. ...', 'How sure are you?' -> 'Not at all: these are example numbers')",
                      len(c1) == 12 and [x[0] for x in c1] == ["q", "a"] * 6 and c1[6][1] == "Are you stuck?" and c1[7][1].startswith("Yes. ") and c1[11][1].startswith("Not at all: these are example numbers") and all("source: cronos/status.json" in x[1] for x in c1[1::2]) and c1[9][1].startswith("Cronos failed its last run. First step: "), c1[6:])
                p.locator("#chatClose").click()
                check("c. 'End the chat' closes it", p.evaluate("() => document.querySelector('#chatCard').hidden"))
                p.locator("#standBtn").click()
                p.wait_for_timeout(1900 * 4 + 600)
                su = p.evaluate("() => [[...document.querySelectorAll('#standList li')].map((e) => [e.dataset.key, e.dataset.kit, e.textContent]), document.querySelector('#standBtn').textContent]")
                check("c. STAND-UP (fallback): the four people of the Research hall each say their one line in turn (Cronos: 'Blocked: ...')", [x[0] for x in su[0]] == ["w:mind", "w:prometheus", "w:hephaestus", "w:cronos"] and all(x[1] == "0" for x in su[0]) and su[0][3][2].startswith("Cronos: Blocked: My last run failed.") and su[1] == "Stand-up", su)
                p.locator('#places button[data-place="camp"]').click()
                p.locator('#peopleList button[data-key="b:camp10"]').click()
                p.locator('#chatQs button[data-q="stuck"]').click()
                cb = p.evaluate("() => [document.querySelector('#chatH').textContent, document.querySelector('#chatWho').textContent, [...document.querySelectorAll('#chatLog li.a')].map((e) => e.textContent)]")
                check("c. TALK to a builder in the camp (fallback): an agent with no git activity answers honestly ('I cannot tell you: there is no live activity ...') with its person id builder:<branch>", cb[0] == "Example envoy" and "builder:example-10" in cb[1] and cb[2][0].startswith("I cannot tell you: there is no live activity") and "source: handoff/agents_now.json" in cb[2][0], cb)
                p.locator("#chatClose").click()
            # the Builders' camp (2D camp map, All hands, a builder card)
            cm = p.evaluate("""() => ({ line: document.querySelector('#handsLine').textContent, pill: document.querySelector('#campPill').textContent, tents: document.querySelectorAll('#campMap g[role=button]').length, smoke: document.querySelectorAll('#campMap .smoke').length,
              hands: [...document.querySelectorAll('#hands button')].map((b) => b.getAttribute('aria-label')), scroll: document.querySelector('#campScroll').textContent, note: document.querySelector('#campNote').textContent, go: document.querySelector('#campGo').hidden, bs: document.querySelector('#bsheet').hidden,
              crates: document.querySelectorAll('#campMap g[role=button] rect[rx="0.8"]').length, today: window.ERGASTERION.S.builders.reduce((s, b) => s + b.crates, 0) })""")
            check("c. THE BUILDERS' CAMP (2D camp map): '10 build agents: 4 working now ...' flagged example, 10 tents you can tap, smoke only over the 4 working builders' braziers, a crate per commit today, the scroll reads a commit message, All hands lists all 10 working first",
                  cm["line"].startswith("10 build agents: 4 working now, 4 quiet, 1 done, 1 with a job line only.") and "Example agents" in cm["line"] and cm["pill"] == "4 working" and cm["tents"] == 10 and cm["smoke"] == 8 and len(cm["hands"]) == 10 and ", Working. " in cm["hands"][0] and ", Job only. " in cm["hands"][-1]
                  and ": Example: " in cm["scroll"] and cm["crates"] == cm["today"] > 0 and cm["go"] and cm["bs"], cm)
            p.locator('#campMap g[data-id="camp8"]').click()
            b8 = p.evaluate("""() => ({ h: document.querySelector('#bsheetH').textContent, pill: document.querySelector('#bsheetPill').textContent, job: document.querySelector('#bsheetJob').textContent, line: document.querySelector('#bsheetLine').textContent, hidden: document.querySelector('#bsheet').hidden,
              commits: [...document.querySelectorAll('#bsheetCommits li')].map((e) => e.textContent), folders: document.querySelectorAll('#bsheetFolders li').length, shipped: [...document.querySelectorAll('#bsheetShipped li')].map((e) => e.textContent), status: document.querySelector('#status').textContent })""")
            check("c. tapping a tent opens the builder's card: name, status (Done), its job, 'merged into the release', what it shipped (merged work with times)", not b8["hidden"] and b8["h"] == "Example gladiator" and b8["pill"] == "Done" and b8["job"].startswith("Job: Example:") and "merged into the release" in b8["line"]
                  and len(b8["shipped"]) == 2 and "merged work" in b8["shipped"][0] and b8["commits"] == ["No commits waiting on its branch."] and b8["status"].startswith("Example gladiator: Done."), b8)
            p.locator('#hands button[data-id="camp1"]').click()
            b1 = p.evaluate("() => [document.querySelector('#bsheetH').textContent, document.querySelector('#bsheetPill').textContent, [...document.querySelectorAll('#bsheetCommits li')].map((e) => e.textContent), document.querySelectorAll('#bsheetFolders li').length, document.querySelector('#bsheetLine').textContent]")
            check("c. a working builder's card (from All hands): 'Working: last commit 4 min ago', its last commits with times, the folders it touched, files changed and commits today", b1[0] == "Example mason" and b1[1] == "Working" and len(b1[2]) == 3 and "min ago" in b1[2][0] and "UTC" in b1[2][0] and b1[3] == 2 and "Working: last commit 4 min ago." in b1[4] and "commits today" in b1[4], b1)
            p.locator('#hands button[data-id="camp10"]').click()
            b10 = p.evaluate("() => [document.querySelector('#bsheetPill').textContent, document.querySelector('#bsheetLine').textContent, document.querySelector('#bsheetCommits').textContent]")
            check("c. an agent with no git activity is honest: 'Job only', 'no live activity', no commits shown", b10[0] == "Job only" and "Job only, no live activity." in b10[1] and "only its job line is known" in b10[1] and b10[2] == "No live activity to show.", b10)
            p.locator("#bsheetClose").click()
            # the day replay
            rp = p.evaluate("""() => ({ note: document.querySelector('#replayNote').textContent, rows: document.querySelectorAll('#lanes text').length, marks: document.querySelectorAll('#lanes rect').length, bad: [...document.querySelectorAll('#lanes rect')].filter((r) => r.getAttribute('fill') === '#c96a4a').length,
              scrub: document.querySelector('#scrub').value, now: document.querySelector('#replayNow').textContent, list: document.querySelectorAll('#replayList li').length, p24: document.querySelector('#r24').getAttribute('aria-pressed'), total: window.ERGASTERION.S.win.events.length })""")
            check("c. REPLAY (last 24 hours): the note counts events / workers / failed and says Example, one lane per worker with a mark per event (the failure in red), the slider at the end, the clock and 'N of N events so far', the last events listed",
                  re.search(r"\d+ events from \d+ workers, 1 failed\. Example events\.", rp["note"]) and rp["marks"] == rp["total"] and rp["bad"] == 1 and rp["scrub"] == "1000" and f"{rp['total']} of {rp['total']} events so far" in rp["now"] and "UTC" in rp["now"] and 1 <= rp["list"] <= 6 and rp["p24"] == "true", rp)
            p.evaluate("() => window.ERGASTERION.replay.set(0)")
            r0 = p.evaluate("() => [document.querySelector('#replayNow').textContent, document.querySelector('#replayList').textContent, document.querySelector('#scrub').value]")
            check("c. REPLAY scrubbed to the start: '0 of N events so far' and the list says nothing has happened yet", "0 of " in r0[0] and "Nothing has happened yet" in r0[1] and r0[2] == "0", r0)
            p.locator("#failBtn").click()
            rf = p.evaluate("() => [document.querySelector('#status').textContent, [...document.querySelectorAll('#replayList li')].map((e) => [e.dataset.ok, e.textContent]), Number(document.querySelector('#scrub').value), document.querySelectorAll('#plan g.hot').length]")
            check("c. 'Jump to last failure' moves the slider to the failed run (Cronos, 'FAILED'), shows it on top of the list and says it in the status line", rf[0].startswith("Last failure: Cronos") and rf[1][0][0] == "0" and "FAILED" in rf[1][0][1] and 0 < rf[2] < 1000, rf)
            p.locator("#r7").click()
            r7 = p.evaluate("() => [document.querySelector('#r7').getAttribute('aria-pressed'), window.ERGASTERION.S.win.events.length, document.querySelector('#replayNote').textContent, document.querySelector('#scrub').value]")
            check("c. 'Last 7 days' widens the window: more events, 2 failed, the slider back at now", r7[0] == "true" and r7[1] > rp["total"] and "2 failed" in r7[2] and r7[3] == "1000", r7)
            p.locator("#speedBtn").click()
            p.locator("#speedBtn").click()
            p.locator("#playBtn").click()
            p.wait_for_timeout(1300)
            pl = p.evaluate("() => [document.querySelector('#playBtn').textContent, window.ERGASTERION.S.cur, document.querySelector('#speedBtn').textContent]")
            p.locator("#playBtn").click()
            p.wait_for_timeout(300)
            pz = p.evaluate("() => [document.querySelector('#playBtn').textContent, window.ERGASTERION.S.cur]")
            p.wait_for_timeout(400)
            check("c. Play restarts from the beginning and sweeps forward (16x after two taps on Speed), Pause holds the position", pl[0] == "Pause" and 0.1 < pl[1] < 0.99 and pl[2] == "Speed 16x" and pz[0] == "Play" and pz[1] >= pl[1] and p.evaluate("() => window.ERGASTERION.S.cur") == pz[1], (pl, pz))
            p.evaluate("() => { const s = document.querySelector('#scrub'); s.value = '500'; s.dispatchEvent(new Event('input', { bubbles: true })); }")
            check("c. dragging the slider scrubs the replay (half way = half the window)", abs(p.evaluate("() => window.ERGASTERION.S.cur") - 0.5) < 0.001 and "UTC" in p.evaluate("() => document.querySelector('#scrub').getAttribute('aria-valuetext')"))
            # the pipeline wall
            pp = p.evaluate("""() => ({ line: document.querySelector('#pipeLine').textContent, lanes: [...document.querySelectorAll('#pipeLanes a')].map((a) => [a.dataset.id, a.querySelector('.n').textContent, a.getAttribute('href')]), fams: [...document.querySelectorAll('#pipeFams a')].map((a) => [a.dataset.name, a.getAttribute('href'), a.querySelectorAll('.stack i').length]),
              moves: document.querySelectorAll('#pipeMoves a').length, sum: document.querySelector('#movesBox summary').textContent, note: document.querySelector('#pipeNote').textContent })""")
            check("c. PIPELINE wall: Idea 240 -> Testing 52 -> Adopted 14 / Rejected 174 (example counts), each lane a link into the Archive; families with a 3-part bar, each a link filtered to that family; the newest moves in a fold",
                  "240 ideas were tested" in pp["line"] and "Example counts" in pp["line"] and [x[:2] for x in pp["lanes"]] == [["ideas", "240"], ["testing", "52"], ["adopted", "14"], ["rejected", "174"]] and all(x[2].startswith("../archive/") for x in pp["lanes"])
                  and pp["fams"][0] == ["LIT research", "../archive/?find=LIT%20research", 3] and len(pp["fams"]) == 5 and pp["moves"] == 5 and pp["sum"] == "Newest 5 moves", pp)
            # category chips
            p.locator('#cats button[data-cat="Kalshi"]').click()
            ck = p.evaluate("() => [[...document.querySelectorAll('#lessons li[data-cat], #strong li[data-cat], #changed li[data-cat]')].map((e) => e.dataset.cat), document.querySelector('#cats button[data-cat=Kalshi]').getAttribute('aria-pressed')]")
            check("c. a category chip filters all three lists (Kalshi only)", ck[0] and set(ck[0]) == {"Kalshi"} and ck[1] == "true", ck)
            p.locator('#cats button[data-cat=""]').click()
            # tap a worker from the list: its card, its bubble, its crates
            p.locator('#workers button[data-id="cronos"]').click()
            c = p.evaluate("""() => ({ h: document.querySelector('#sheetH').textContent, pill: document.querySelector('#sheetPill').textContent, doing: document.querySelector('#sheetDoing').textContent, outs: document.querySelectorAll('#sheetOut li').length, role: document.querySelector('#sheetRole').textContent, say: document.querySelector('#sheetSay').textContent,
              tags: [...document.querySelectorAll('#sheetOut .crate .tag')].map((e) => e.textContent), health: document.querySelector('#sheetHealth').textContent, hidden: document.querySelector('#sheet').hidden, status: document.querySelector('#status').textContent, planSay: document.querySelector('#planSay').textContent })""")
            check("c. a worker card: name, the status word, its hall and job, what it SAYS ('My last run failed'), what it is doing, its crates (at most 5, each with a short tag), the health line; the status line is spoken",
                  not c["hidden"] and c["h"] == "Cronos" and c["pill"] == "Failed" and "1 failed" in c["doing"] and 1 <= c["outs"] <= 5 and c["health"].startswith("Example data.") and c["status"].startswith("Cronos: Failed.") and "Research hall" in c["role"] and "turning the search wheel" in c["role"]
                  and c["say"].startswith("Says: My last run failed.") and "datacity" in c["tags"] and c["planSay"].startswith("Cronos says: "), c)
            p.locator('#sheetOut .crate[data-i="0"]').click()
            cr = p.evaluate("() => [document.querySelector('#sheetOut .crate[data-i=\"0\"]').getAttribute('aria-expanded'), getComputedStyle(document.querySelector('#sheetOut .crate[data-i=\"0\"] .full')).whiteSpace, document.querySelectorAll('#sheetOut .crate[aria-expanded=true]').length]")
            check("c. tapping a crate opens it (its full text, when it was made); one crate open at a time", cr == ["true", "normal", 1], cr)
            p.locator('#workers button[data-id="mind"]').click()
            m = p.evaluate("() => [document.querySelector('#sheetH').textContent, [...document.querySelectorAll('#sheetLearn li')].map((e) => e.textContent), document.querySelectorAll('#sheetOut li').length]")
            check("c. the Mind card lists its notes as crates and keeps the 'context only: not predictive' lesson with its source file", m[0] == "Mind" and m[2] == 2 and any("context only" in t and "source: docs/CLAUDE_REFERENCE.md" in t for t in m[1]), m)
            p.locator("#sheetClose").click()
            check("c. Close hides the card", p.evaluate("() => document.querySelector('#sheet').hidden"))
            p.evaluate("() => { document.querySelector('#movesBox').open = true; }")
            check("c. DEMO at 390 x 844: no sideways scroll, every tap >= 44 px (lanes, families, moves, crates, chips, the slider), nothing under Jarvis's corner, no console error, nothing fetched off the site", AK.no_sideways(p) and not AK.taps(p) and not AK.corner(p) and not errs and not [u for u in off if "kalshi" not in u], (AK.taps(p)[:4], AK.corner(p), errs[:2], off[:3]))
            ctx.close()

            # PEOPLE, kit path: a stubbed window.OLYMPUS_PEOPLE (the real module is optional and may be absent)
            STUB = """window.__opened = []; window.__kitMode = 'ok';
              window.OLYMPUS_PEOPLE = { get: (id) => (/^(scanner:|bot:|mind$|villager:cronos|builder:example-1$)/.test(id) ? { id } : null),
                open: (id, o) => { if (window.__kitMode === 'throw') throw new Error('kit broke'); window.__opened.push(id); },
                portrait: (id, size) => { const s = document.createElementNS('http://www.w3.org/2000/svg', 'svg'); s.setAttribute('data-kit-face', id); s.setAttribute('width', size); s.setAttribute('height', size); return s; },
                standup: (ids) => ids.map((id) => ({ id, line: 'KIT says ' + id })) };"""
            ctx, p, errs, seen, off = AK.page(br, origin)
            ctx.add_init_script(STUB)
            AK.open_app(p, origin, APP, "?demo=1&flat=1", hook="ERGASTERION")
            if p.evaluate("() => typeof window.__opened === 'object' && window.OLYMPUS_PEOPLE && window.OLYMPUS_PEOPLE.standup && String(window.OLYMPUS_PEOPLE.open).indexOf('__kitMode') > 0"):
                p.locator('#workers button[data-id="chrysos"]').click()
                kf = p.evaluate("() => [document.querySelector('#sheetFace').dataset.kit, document.querySelector('#sheetFace svg').getAttribute('data-kit-face'), document.querySelector('#sheetTalk').textContent]")
                p.locator("#sheetTalk").click()
                k1 = p.evaluate("() => [window.__opened.slice(), document.querySelector('#chatCard').hidden, document.querySelector('#status').textContent]")
                check("c. KIT path (stubbed OLYMPUS_PEOPLE): the card shows the kit's portrait(id, 44) and 'Talk to Chrysos' calls OLYMPUS_PEOPLE.open('scanner:chrysos'); our own chat card stays closed", kf == ["1", "scanner:chrysos", "Talk to Chrysos"] and k1[0] == ["scanner:chrysos"] and k1[1] and k1[2] == "Talking to Chrysos.", (kf, k1))
                p.locator('#places button[data-place="camp"]').click()
                p.locator('#peopleList button[data-key="b:camp1"]').click()
                p.locator('#peopleList button[data-key="b:camp2"]').click()
                k2 = p.evaluate("() => [window.__opened.slice(), document.querySelector('#chatCard').hidden, document.querySelector('#chatH').textContent]")
                check("c. KIT path: a builder the kit knows opens in the kit (builder:example-1); one the kit does NOT know (get() gives null) falls back to our own chat card, so talking always works", k2[0] == ["scanner:chrysos", "builder:example-1"] and k2[1] is False and k2[2] == "Example scribe", k2)
                p.locator("#chatClose").click()
                p.evaluate("() => { window.__kitMode = 'throw'; }")
                p.locator('#places button[data-place="money"]').click()
                p.locator('#peopleList button[data-key="w:sibyl"]').click()
                k3 = p.evaluate("() => [window.__opened.length, document.querySelector('#chatCard').hidden, document.querySelector('#chatH').textContent]")
                check("c. KIT path: when the kit's open() THROWS, our own chat card opens instead (no error reaches the page)", k3 == [2, False, "Sibyl"] and not errs, (k3, errs[:2]))
                p.locator("#chatClose").click()
                p.locator("#standBtn").click()
                p.wait_for_timeout(1900 * 5 + 600)
                k4 = p.evaluate("() => [...document.querySelectorAll('#standList li')].map((e) => [e.dataset.kit, e.textContent])")
                check("c. KIT path: Stand-up uses the kit's standup() lines for the people it knows (the Money hall's five scanners)", len(k4) == 5 and all(x[0] == "1" for x in k4) and k4[0][1] == "Chrysos: KIT says scanner:chrysos", k4)
            else:
                print("[note] the real people kit is loaded on this site and replaced the stub: the stubbed kit checks are skipped", flush=True)
            check("c. the kit run has no console error", not errs, errs[:3])
            ctx.close()

            # 3D factory: pick, walk, walls, follow, tour, budget (only when the machine can draw it; ERG_NO3D=1 skips it when 3D is impossible)
            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, APP, "?demo=1&q=high&clock=quiet" if not no3d else "?demo=1&flat=1", hook="ERGASTERION")
            p.wait_for_timeout(2500)
            mode = p.evaluate("() => window.ERGASTERION.floor() ? '3d' : 'plan'")
            if no3d:
                print("[note] ERG_NO3D=1: the 3D factory checks are skipped", flush=True)
            elif mode == "3d":
                check("c. 3D factory: the stage shows, the plan hides, 'Plan view', 'Calm tour' and 'Back to the door' are there, the hall chip says Library, the minimap has 15 platforms and the you-are-here arrow",
                      p.evaluate("() => !document.querySelector('#stage').hidden && document.querySelector('#plan').hidden && !document.querySelector('#viewBtn').hidden && document.querySelector('#viewBtn').textContent === 'Plan view' && !document.querySelector('#resetBtn').hidden && !document.querySelector('#tourBtn').hidden && document.querySelector('#hallNow').textContent === 'Library' && document.querySelectorAll('#mini g').length === 15 && document.querySelectorAll('#mini path').length === 1"))
                st = p.evaluate("() => window.ERGASTERION.floor().stats()")
                check(f"c. the budget on the high tier: {st['calls']} draw calls (<= {BUDGET['calls']}) and {st['triangles']} triangles (<= {BUDGET['triangles']}) for the whole factory from the front door", 0 < st["calls"] <= BUDGET["calls"] and 0 < st["triangles"] <= BUDGET["triangles"] and st["batches"] == 12, st)
                pt = p.evaluate("() => window.ERGASTERION.floor().project('queue')")
                box = p.evaluate("() => { const r = document.querySelector('#floor3d').getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; }")
                check("c. the first view from the front door sees the Library's workers (the queue's platform projects on screen)", pt is not None and 0 <= pt["x"] <= box[2] and 0 <= pt["y"] <= box[3], pt)
                tap = """([x, y]) => { const c = document.querySelector('#floor3d'), r = c.getBoundingClientRect(); const o = { bubbles: true, pointerId: 7, clientX: r.left + x, clientY: r.top + y, pointerType: 'touch' }; c.dispatchEvent(new PointerEvent('pointerdown', o)); c.dispatchEvent(new PointerEvent('pointerup', o)); }"""
                if pt:
                    p.evaluate(tap, [pt["x"], pt["y"]])
                    p.wait_for_timeout(400)
                    sid = p.evaluate("() => [document.querySelector('#sheetH').textContent, document.querySelector('#sheet').hidden]")
                    check("c. tapping a worker in the 3D factory opens that worker's card", sid[0] in ("The queue", "Dev agents") and not sid[1], sid)
                p.evaluate("() => { const f = window.ERGASTERION.floor(); f.reset(); f.teleport(4.3, 9.0); }")
                p.wait_for_timeout(500)
                cp = p.evaluate("() => window.ERGASTERION.floor().projectCrate('queue', 0)")
                if cp:
                    p.evaluate(tap, [cp["x"], cp["y"]])
                    p.wait_for_timeout(400)
                    cs = p.evaluate("() => [document.querySelector('#sheetH').textContent, document.querySelectorAll('#sheetOut .crate[aria-expanded=true]').length, document.querySelector('#status').textContent]")
                    check("c. tapping a crate on a conveyor opens the worker's card with THAT crate open and reads it out", cs[0] == "The queue" and cs[1] == 1 and "Crate: " in cs[2], cs)
                else:
                    check("c. a crate of the queue's conveyor projects on screen from in front of it", False, cp)
                p.evaluate("() => window.ERGASTERION.floor().reset()")
                p.wait_for_timeout(300)
                before = p.evaluate("() => window.ERGASTERION.floor().pos()")
                p.evaluate("""() => { const j = document.querySelector('#joy'), r = j.getBoundingClientRect(), cx = r.left + r.width / 2, cy = r.top + r.height / 2; const ev = (t, y) => j.dispatchEvent(new PointerEvent(t, { bubbles: true, pointerId: 3, clientX: cx, clientY: y, pointerType: 'touch' })); ev('pointerdown', cy); ev('pointermove', cy - 40); window.__ev = ev; window.__cy = cy; }""")
                p.wait_for_timeout(1500)
                p.evaluate("() => window.__ev('pointerup', window.__cy - 40)")
                after = p.evaluate("() => window.ERGASTERION.floor().pos()")
                check("c. the joystick pushed forward walks you north from the front door (z decreases, eased) and the knob returns to the middle", after["z"] < before["z"] - 0.05 and abs(before["z"] - 9.0) < 0.01 and p.evaluate("() => document.querySelector('#knob').style.transform") in ("translate(0px,0px)", "translate(0px, 0px)", ""), (before, after))
                p.evaluate("() => { const f = window.ERGASTERION.floor(); f.teleport(7, -7.3); f.move({ fwd: 0, side: 0 }); f.step(0.05); }")
                inside = p.evaluate("() => window.ERGASTERION.floor().pos()")
                check("c. no walking through a platform: teleported onto ATLAS, the next step pushes you out to the collision circle (and you are in the Trading hall)", ((inside["x"] - 7) ** 2 + (inside["z"] + 7.5) ** 2) ** 0.5 >= 1.44 and inside["hall"] == "trading", inside)
                p.evaluate("() => { const f = window.ERGASTERION.floor(); f.teleport(0.1, 2); f.step(0.05); }")
                w1 = p.evaluate("() => window.ERGASTERION.floor().pos()")
                p.evaluate("() => { const f = window.ERGASTERION.floor(); f.teleport(0.1, 5); f.step(0.05); }")
                w2 = p.evaluate("() => window.ERGASTERION.floor().pos()")
                check("c. no walking through a wall: inside the wall between the Research hall and the Library you are pushed to its face; in the doorway you may stand", abs(w1["x"]) >= 0.499 and abs(w2["x"] - 0.1) < 1e-6, (w1, w2))
                p.wait_for_timeout(400)
                check("c. the hall chip follows you (Money hall after a teleport there)", p.evaluate("() => { window.ERGASTERION.floor().teleport(-6, -5); return true; }") and (p.wait_for_timeout(600) or True) and p.evaluate("() => document.querySelector('#hallNow').textContent") == "Money hall")
                # PEOPLE in first person: the Talk prompt within 3 m, the person turns to face you, the marble disc
                p.evaluate("() => { const E = window.ERGASTERION; E.endTalk(); E.floor().teleport(2.2, 8.6, 0); }")
                p.wait_for_timeout(700)
                far = p.evaluate("() => document.querySelector('#talkBtn').hidden")
                p.evaluate("() => window.ERGASTERION.floor().teleport(2.1, 3.68, -Math.PI / 2)")
                p.wait_for_timeout(2600)
                tk = p.evaluate("() => [document.querySelector('#talkBtn').hidden, document.querySelector('#talkBtn').textContent, Math.cos(window.ERGASTERION.floor().facing('w:queue') + Math.PI / 2)]")
                check("c. the Talk prompt: nobody within 3 m = no button; 2.2 m from the queue's scribe = 'Talk to The queue', and it has turned to wave at you (it faces -x, toward where you stand)", far and tk[0] is False and tk[1] == "Talk to The queue" and tk[2] > 0.93, (far, tk))
                p.locator("#talkBtn").click()
                p.wait_for_timeout(900)
                tf = p.evaluate("() => [window.ERGASTERION.floor().focused(), document.querySelector('#chatCard').hidden || !!window.OLYMPUS_PEOPLE, document.querySelector('#sheetH').textContent, Math.cos(window.ERGASTERION.floor().facing('w:queue') + Math.PI / 2), window.ERGASTERION.floor().stats()]")
                check(f"c. pressing Talk opens the chat for that person: it is the focused one (talk pose, marble disc), still facing you, its card is open; inside the budget ({tf[4]['calls']} calls / {tf[4]['triangles']} triangles)", tf[0] == "w:queue" and tf[1] in (False, True) and tf[2] == "The queue" and tf[3] > 0.93 and tf[4]["calls"] <= BUDGET["calls"] and tf[4]["triangles"] <= BUDGET["triangles"], tf)
                AK.shot(p, "ergasterion-3d-talk")
                p.evaluate("() => window.ERGASTERION.endTalk()")
                check("c. ending the chat releases the person (no focus)", p.evaluate("() => window.ERGASTERION.floor().focused()") == "")
                # out through the front door to the Builders' camp
                p.locator("#campGo").click()
                p.wait_for_timeout(1500)
                cg = p.evaluate("() => [window.ERGASTERION.floor().pos(), document.querySelector('#hallNow').textContent, document.querySelector('#mini').getAttribute('viewBox'), document.querySelectorAll('#mini g').length, window.ERGASTERION.floor().stats(), document.querySelector('#status').textContent]")
                check(f"c. 'Walk to the camp': you stand outside the front door facing the desert camp, the chip says Builders' camp, the minimap becomes the camp map with 10 tents; the camp view is inside the budget ({cg[4]['calls']} calls / {cg[4]['triangles']} triangles)",
                      cg[0]["hall"] == "camp" and abs(cg[0]["z"] - 11.0) < 0.01 and abs(abs(cg[0]["yaw"]) - 3.14159) < 0.01 and cg[1] == "Builders' camp" and cg[2] == "0 0 360 250" and cg[3] == 10 and 0 < cg[4]["calls"] <= BUDGET["calls"] and cg[4]["triangles"] <= BUDGET["triangles"] and "camp" in cg[5], cg)
                AK.shot(p, "ergasterion-3d-camp")
                tp = p.evaluate("() => window.ERGASTERION.floor().projectCamp(1)")
                if tp:
                    p.evaluate(tap, [tp["x"], tp["y"]])
                    p.wait_for_timeout(400)
                    tb = p.evaluate("() => [document.querySelector('#bsheet').hidden, document.querySelector('#bsheetH').textContent, document.querySelector('#bsheetWalk').hidden]")
                    check("c. tapping a tent in the 3D camp opens that builder's card (with 'Walk to its tent')", tb[0] is False and tb[1].startswith("Example ") and tb[2] is False, tb)
                else:
                    check("c. a tent projects on screen from the camp entrance", False, tp)
                p.evaluate("() => { const f = window.ERGASTERION.floor(); f.reset(); f.look(Math.PI, 0); }")
                p.wait_for_timeout(700)
                p.evaluate("""() => { const j = document.querySelector('#joy'), r = j.getBoundingClientRect(), cx = r.left + r.width / 2, cy = r.top + r.height / 2; const ev = (t, y) => j.dispatchEvent(new PointerEvent(t, { bubbles: true, pointerId: 5, clientX: cx, clientY: y, pointerType: 'touch' })); ev('pointerdown', cy); ev('pointermove', cy - 44); window.__ev = ev; window.__cy = cy; }""")
                p.wait_for_timeout(5000)
                p.evaluate("() => window.__ev('pointerup', window.__cy - 44)")
                wk = p.evaluate("() => window.ERGASTERION.floor().pos()")
                check("c. the first-person path: from inside the factory, turn round and walk: you go out through the front door into the camp", wk["hall"] == "camp" and wk["z"] > 10.0 and abs(wk["x"] - 6.5) < 0.9, wk)
                p.evaluate("() => { const f = window.ERGASTERION.floor(); f.teleport(3, 9.3); f.step(0.05); f.teleport(3, 9.9); f.step(0.05); }")
                check("c. the factory's south wall is still a wall away from the doorway", abs(p.evaluate("() => window.ERGASTERION.floor().pos().z") - 9.4) < 1e-6)
                p.select_option("#follow", "kalshi")
                p.wait_for_timeout(500)
                fo = p.evaluate("() => [window.ERGASTERION.floor().pos().following, document.querySelector('#status').textContent, window.ERGASTERION.floor().pos().mode]")
                check("c. 'Follow' a worker: the camera follows Kalshi bot, the status line says so", fo[0] == "kalshi" and fo[1].startswith("Following Kalshi bot") and fo[2] == "follow", fo)
                AK.shot(p, "ergasterion-3d-follow")
                p.select_option("#follow", "")
                p.locator("#tourBtn").click()
                p.wait_for_timeout(1600)
                tr = p.evaluate("() => [window.ERGASTERION.floor().pos().mode, document.querySelector('#tourBtn').textContent, document.querySelector('#tourBtn').getAttribute('aria-pressed'), document.querySelector('#hallNow').textContent, document.querySelector('#status').textContent, window.ERGASTERION.floor().stats()]")
                check(f"c. 'Calm tour': the camera flies above the halls by itself ({tr[5]['calls']} calls / {tr[5]['triangles']} triangles from above, inside the budget), the button reads 'Stop the tour', the chip says 'Tour: <hall>'",
                      tr[0] == "tour" and tr[1] == "Stop the tour" and tr[2] == "true" and tr[3].startswith("Tour: ") and "calm tour" in tr[4] and 0 < tr[5]["calls"] <= BUDGET["calls"] and tr[5]["triangles"] <= BUDGET["triangles"], tr)
                AK.shot(p, "ergasterion-3d-tour")
                p.evaluate("""() => { const j = document.querySelector('#joy'), r = j.getBoundingClientRect(), cx = r.left + r.width / 2, cy = r.top + r.height / 2; const ev = (t, y) => j.dispatchEvent(new PointerEvent(t, { bubbles: true, pointerId: 4, clientX: cx, clientY: y, pointerType: 'touch' })); ev('pointerdown', cy - 30); ev('pointerup', cy - 30); }""")
                p.wait_for_timeout(500)
                ts = p.evaluate("() => [window.ERGASTERION.floor().pos().mode, document.querySelector('#tourBtn').textContent]")
                check("c. touching the joystick ends the tour and puts you back on your feet", ts == ["walk", "Calm tour"], ts)
                p.evaluate("() => document.querySelector('#resetBtn').click()")
                rs = p.evaluate("() => window.ERGASTERION.floor().pos()")
                check("c. 'Back to the door' puts you at the front door in the Library, not following", abs(rs["z"] - 9.0) < 0.01 and abs(rs["x"] - 6.5) < 0.01 and rs["following"] is None and rs["hall"] == "library", rs)
                p.wait_for_timeout(900)
                AK.shot(p, "ergasterion-3d")
                p.evaluate("() => { window.ERGASTERION.replay.set(0.2); window.ERGASTERION.replay.play(); }")
                p.wait_for_timeout(900)
                p.evaluate("() => window.ERGASTERION.replay.pause()")
                check("c. the replay runs with the 3D factory up (it lights the busy workers' lamps) without an error", not errs and p.evaluate("() => window.ERGASTERION.S.cur") > 0.2, errs[:2])
                p.evaluate("() => document.querySelector('#viewBtn').click()")
                p.wait_for_timeout(300)
                check("c. 'Plan view' swaps to the flat plan and 'Walk the floor' brings the 3D back", p.evaluate("() => document.querySelector('#stage').hidden && !document.querySelector('#plan').hidden && document.querySelector('#viewBtn').textContent === 'Walk the floor' && document.querySelector('#tourBtn').hidden"))
                p.evaluate("() => document.querySelector('#viewBtn').click()")
                p.wait_for_timeout(1500)
                check("c. back in 3D after the swap", p.evaluate("() => !!window.ERGASTERION.floor() && !document.querySelector('#stage').hidden"))
                check("c. 3D at 390 x 844: every tap >= 44 px, no sideways scroll", AK.no_sideways(p) and not AK.taps(p), AK.taps(p)[:4])
            else:
                print("[note] 3D factory not available on this machine: the plan is checked instead (" + str(p.evaluate("() => window.ERGASTERION.S.why || ''")) + ")", flush=True)
                check("c. no 3D here: the flat plan is shown, 'Walk the floor' is offered only when 3D can be tried", p.evaluate("() => !document.querySelector('#plan').hidden && document.querySelector('#stage').hidden"))
            check("c. the 3D run has no console error", not errs, errs[:3])
            ctx.close()

            # the flat plan: tap a worker on the plan (LITE, 375 x 667, reduced motion)
            ctx, p, errs, seen, off = AK.page(br, origin, w=375, h=667, reduced=True, lite=True)
            AK.open_app(p, origin, APP, "?demo=1&q=low", hook="ERGASTERION")
            r = p.evaluate("() => ({ plan: !document.querySelector('#plan').hidden, stage: document.querySelector('#stage').hidden, buttons: document.querySelectorAll('#plan g[role=button]').length, view: document.querySelector('#viewBtn').hidden, tour: document.querySelector('#tourBtn').hidden, lite: !document.querySelector('#lite').hidden, floor: !!window.ERGASTERION.floor() })")
            check("c. 375 x 667, LITE (?q=low), reduced motion: the 2D plan with 15 buttons, no 3D, no 'Walk the floor' or tour button, the LITE chip", r["plan"] and r["stage"] and r["buttons"] == 15 and r["view"] and r["tour"] and r["lite"] and not r["floor"], r)
            p.locator('#plan g[data-id="oikos"]').click()
            c2 = p.evaluate("() => [document.querySelector('#sheetH').textContent, document.querySelector('#sheetPill').textContent, document.querySelector('#sheet').hidden, document.querySelector('#planSay').textContent]")
            check("c. tapping a worker on the plan opens its card (Oikos: Stale in the demo) and it speaks under the plan ('Old news')", c2[:3] == ["Oikos", "Stale", False] and c2[3].startswith("Oikos says: Old news:"), c2)
            sz = p.evaluate("() => { const r = document.querySelector('#plan g[data-id=oikos]').getBoundingClientRect(); return [r.width, r.height]; }")
            check("c. a plan button is at least 44 px (its hit square), no sideways scroll, every tap >= 44 px, no error", sz[0] >= 43.5 and sz[1] >= 43.5 and AK.no_sideways(p) and not AK.taps(p) and not errs, (sz, AK.taps(p)[:3], errs[:2]))
            p.evaluate("() => window.ERGASTERION.replay.set(0)")
            p.locator("#playBtn").click()
            p.wait_for_timeout(1300)
            rm = p.evaluate("() => [window.ERGASTERION.S.cur, document.querySelector('#replayList li') ? document.querySelectorAll('#replayList li').length : 0]")
            p.evaluate("() => window.ERGASTERION.replay.pause()")
            check("c. reduced motion: Play does not sweep, it steps from event to event (the position sits exactly on an event)", rm[0] > 0 and p.evaluate("(f) => { const w = window.ERGASTERION.S.win; return w.events.some((e) => Math.abs((e.t - w.t0) / w.span - f) < 1e-9) || f === 1; }", rm[0]), rm)
            AK.shot(p, "ergasterion-lite")
            ctx.close()

            # real files: home, money, kalshi, cron (queue.json is the real one of the repo)
            real = {
                "/home.json": json.dumps({"t": int(time.time()), "accounts": [{"id": "mffu50k_eval", "name": "Zlarior 50K", "conn": {"connected": True}, "eval": {"room": 1420, "mll": 2000}, "pnl": {"today": 312}}]}),
                "/money/index.json": json.dumps({"streams": [{"id": "sibyl", "name": "Sibyl", "status": "ok", "asof": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 1800)), "headline": "One pick survives the check.", "items": [{"title": "Pick Z", "usd": None}], "notes": ["Only 1 pick survives out-of-sample."]}]}),
                "/cronos/status.json": json.dumps({"tasks": {"fates": {"ok": True, "last_run_t": int(time.time()) - 3600, "cadence": "nightly"}}}),
            }
            srv2, origin2 = AK.serve(overrides=real)
            try:
                ctx, p, errs, seen, off = AK.page(br, origin2, mock={"kalshi.json": json.dumps({"running": True, "t": int(time.time()), "today_pnl": 12.4})})
                AK.open_app(p, origin2, APP, "?q=low", hook="ERGASTERION")
                rr = p.evaluate("""() => { const w = (id) => document.querySelector('#workers button[data-id=' + id + ']').getAttribute('aria-label'); return { demo: document.querySelector('#demo').hidden, lit: w('lit'), sibyl: w('sibyl'), chrysos: w('chrysos'), kalshi: w('kalshi'), cron: w('cronos'), dev: w('dev'),
                  learn: [...document.querySelectorAll('#lessons li, #strong li')].map((e) => e.textContent), changed: [...document.querySelectorAll('#changed li')].map((e) => e.textContent), title: document.querySelector('#heroTitle').textContent, next: [...document.querySelectorAll('#next li b')].map((e) => e.textContent),
                  lanes: [...document.querySelectorAll('#pipeLanes a .n')].map((e) => e.textContent), fam0: document.querySelector('#pipeFams a').getAttribute('href'), moves: document.querySelectorAll('#pipeMoves a').length, pipe: document.querySelector('#pipeLine').textContent,
                  rnote: document.querySelector('#replayNote').textContent, rlist: [...document.querySelectorAll('#replayList li')].map((e) => e.textContent), all: document.body.textContent }; }""")
                check("c. REAL files: no DEMO chip; Zlarior shows its real drawdown line; Sibyl's own headline; a machine with no file says 'No file from this machine yet' and is Stale, never invented",
                      rr["demo"] and "Drawdown left $1,420 of $2,000 max loss" in rr["lit"] and rr["sibyl"].startswith("Sibyl, ") and "One pick survives the check." in rr["sibyl"] and "No file from this machine yet" in rr["chrysos"], rr["lit"])
                check("c. REAL Learning board: Sibyl's note is a lesson of the week with 'source: money/sibyl.json' next to the builder's lessons; 'what changed our mind' shows the real Kalshi 95c flip; nothing says Example",
                      any("Only 1 pick survives out-of-sample." in t and "source: money/sibyl.json" in t for t in rr["learn"]) and any("We believed: 95c and above is +1.4% per $" in t and "kalshi_edge_A.md" in t for t in rr["changed"]) and not any("Example:" in t for t in rr["learn"] + rr["changed"]), (rr["learn"][:2], rr["changed"][:1]))
                q = json.load(open(os.path.join(D, "queue.json"), encoding="utf-8"))
                pcn = q["pipeline"]["counts"]
                check("c. REAL pipeline wall: the Archive's counts (ideas, testing, adopted, rejected), 20 newest moves, the first family links into the Archive; no 'Example'",
                      [int(x.replace(",", "")) for x in rr["lanes"]] == [pcn["ideas"], pcn["testing"], pcn["adopted"], pcn["rejected"]] and rr["moves"] == 20 and rr["fam0"].startswith("../archive/?find=") and "Example" not in rr["pipe"], (rr["lanes"], rr["fam0"]))
                check("c. REAL replay: the stream is real (the mocked Kalshi run, Sibyl's run, the Cronos job and the commits are in the last 24 hours), not flagged Example; the planner names the missing machines as ONE row",
                      re.search(r"\d+ events? from \d+ workers", rr["rnote"]) and "Example" not in rr["rnote"] and rr["rlist"] and any(re.search(r"workers? ha(ve|s) no file here", t) for t in rr["next"]), (rr["rnote"], rr["next"]))
                rc = p.evaluate("() => [document.querySelector('#handsLine').textContent, document.querySelectorAll('#campMap g[role=button]').length, document.querySelector('#campNote').textContent, [...document.querySelectorAll('#hands .nm')].map((e) => e.textContent)]")
                bj = json.load(open(os.path.join(D, "builders.json"), encoding="utf-8"))
                check("c. REAL Builders' camp: the agents of builders.json by name (never 'Example'), a tent each, and the note says where the activity comes from (git at build time, or job lines only)",
                      "Example" not in rc[0] and rc[1] == min(10, len(bj["agents"])) and sorted(rc[3]) == sorted(a["name"] for a in bj["agents"][:10]) and ("Read from git when the site was built" in rc[2] if bj["source"] == "git" else "no live activity" in rc[2]), rc[:3])
                check("c. REAL files: Kalshi (mocked feed) is Working and Cronos is Working from its status.json; the dev agents read the real queue.json", "Kalshi bot, Working" in rr["kalshi"] and "Cronos, Working" in rr["cron"] and rr["dev"].startswith("Dev agents"), rr["kalshi"])
                check("c. REAL run reads only the site's own files (the kalshi feed is the one outside address) and has no console error; every tap >= 44 px with the real lists", any("queue.json" in u for u in seen) and not errs and not [u for u in off if "kalshi" not in u] and not AK.taps(p) and AK.no_sideways(p), (off[:3], errs[:3], AK.taps(p)[:3]))
                AK.shot(p, "ergasterion-real")
                ctx.close()
            finally:
                srv2.shutdown()

            # no worker files at all: the demo, never blank
            srv3, origin3 = AK.serve(overrides={"/ergasterion/queue.json": None, "/ergasterion/builders.json": None, "/prometheus/forge.json": None, "/hephaestus/data.json": None, "/home.json": None, "/money/index.json": None, "/cronos/status.json": None, "/kalshi.json": None})
            try:
                ctx, p, errs, seen, off = AK.page(br, origin3)
                AK.open_app(p, origin3, APP, "?q=low", hook="ERGASTERION")
                z = p.evaluate("() => [!document.querySelector('#demo').hidden, document.querySelectorAll('#workers button').length, document.querySelector('#heroTitle').textContent, document.querySelectorAll('#lessons li').length, document.querySelectorAll('#pipeLanes a').length, document.querySelectorAll('#lanes rect').length, document.querySelectorAll('#campMap g[role=button]').length, document.querySelector('#handsLine').textContent]")
                check("c. nothing published (no home, money, queue ...): the DEMO fixture fills the floor, the camp, the replay, the pipeline and the board, labelled DEMO, never blank", z[0] and z[1] == 15 and z[2] == "1 worker failed" and z[3] >= 5 and z[4] == 4 and z[5] >= 10 and z[6] == 10 and "Example agents" in z[7], z)
                ctx.close()
            finally:
                srv3.shutdown()

            # reduced motion with 3D: still, no error
            ctx, p, errs, seen, off = AK.page(br, origin, reduced=True)
            AK.open_app(p, origin, APP, "?demo=1&q=high&clock=quiet" if not no3d else "?demo=1&flat=1", hook="ERGASTERION")
            p.wait_for_timeout(1500)
            mode = p.evaluate("() => window.ERGASTERION.floor() ? '3d' : 'plan'")
            if mode == "3d":
                a1 = p.evaluate("() => window.ERGASTERION.floor().pos()")
                p.wait_for_timeout(700)
                a2 = p.evaluate("() => window.ERGASTERION.floor().pos()")
                p.evaluate("() => window.ERGASTERION.setTour(true)")
                p.wait_for_timeout(500)
                t1 = p.evaluate("() => { const c = window.ERGASTERION.floor().rc.camera || null; return window.ERGASTERION.floor().pos().mode; }")
                check("c. reduced motion: the factory stands still by itself (no drift), the tour is one still view from above, the 3D run has no error", a1 == a2 and t1 == "tour" and not errs, (a1, a2, t1, errs[:2]))
            else:
                check("c. reduced motion: the plan, no error", not errs, errs[:2])
            ctx.close()
    finally:
        srv.shutdown()


if __name__ == "__main__":
    test_static()
    test_maths()
    test_life()
    if "--static" not in sys.argv:
        test_page()
    AK.finish()
