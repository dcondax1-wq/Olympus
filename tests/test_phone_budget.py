"""The real-phone budget pass (QA round 6, docs/QA_ROUND6.md): what the site costs a mid-range iPhone, and that it survives one.

  a. static (no browser): tools/phone_budget.py arithmetic; per-page eager-load budgets on the source pages (blocking KB / files before the
     first paint, three.js never eager on the hero pages that use olympus/lazy3d.js); the contracts in olympus.js (LITE auto-detection,
     the WebGL guard), render.js (context loss / restore, GPU buffers freed on hide), sfx.js (format fallback), lazy3d.js
  b. LITE auto-detection in Chromium: deviceMemory 2 GB / Save-Data -> data-fx=low + data-oly-auto, the owner's stored choice wins; on LITE
     the NQ page never requests three.js and keeps its 2D columns; on HD three.js arrives after the first paint and the 3D mounts
  c. WebGL context loss (WEBGL_lose_context): the render core's page (render-lab) and a bare three.js page (NQ) never go black: the
     still / backdrop shows while lost, data-oly-gl says so, and after restore the core rebuilds (restores >= 1) and draws again
  d. audio: the first tap unlocks (context running); a host with no .m4a (Safari-style format order) falls back to .ogg after one failed
     request; with no audio files at all the synth plays, at most 2 failed requests, no console error, no page error
  e. Jarvis app switching: 10 switches between 3D apps, then home: no AudioContext / WebGL context / canvas of a closed app is still
     alive after GC (WeakRef registry across frames), one app frame at most, JS heap growth bounded
  f. perf v2 (2026-11-14, team P2 "fast and crisp", docs/OLYMPUS_PERF.md "Perf v2"), static: tools/perf_probe.py arithmetic (frame stats, TBT,
     the trace breakdown, canvas rows, the table), the render-scale governor's policy in node (olympus/render-scale.js: ranges per Quality,
     climbing to the full pixel ratio when frames allow, smooth step-downs, CPU-bound frames keep the resolution, failed climbs back off and
     lock: never thrash), and the contracts (render.js / hero-stage.js use the governor, pause off screen, size from a ResizeObserver,
     compile shaders in the background, no MSAA over 2x; the Quality picker in the one jfx key; the cheap paths)
  g. perf v2 in Chromium, the 4K desktop profile (1920 x 1080 at 2x = 3840 x 2160) and the iPhone (390 x 844 at 3x): a canvas renders at the
     full device pixel ratio when its frames allow (Ultra 4K at once; Auto climbs to 3x on the iPhone), slow frames step it down one level
     at a time; the main pages idle at ~0 CPU (and a 3D page scrolled off screen draws nothing); no long task over 200 ms after load
    python -X utf8 -m tests.test_phone_budget            (--static: only a. and f.; or name sections: lite lazy ctx audio switch perf)
Browser parts run under `flock -w 2400 /tmp/olympus_browser.lock` (one browser on the machine).
"""
from __future__ import annotations

import http.server
import json
import os
import re
import subprocess
import sys
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
WEB = os.path.join(ROOT, "tools", "web_public")
import phone_budget as PB  # noqa: E402
import perf_probe as PP  # noqa: E402

RES: list = []
LAZY = {"nq": ("nqscene.js", "nq3d"), "mint": ("mintscene.js", "mint3d"), "helios": ("sunload.js", "helios-sun"), "aegis": ("shieldload.js", "aegis-shield"),
        "chrysos": ("towerload.js", "chrysos-tower"), "symposium": ("hallload.js", "sym-hall")}
# blocking bytes (raw, before gzip) / files before the first paint, per page, on the source tree; root and jarvis are the lead's shells:
# held at today's size so they never grow (root = 528 kB of inline HTML, see the report)
BLOCK_KB, BLOCK_N = 300, 9
SHELL = {"root": (760, 6), "jarvis": (420, 3)}


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:600]}"), flush=True)


def read(p):
    with open(p, encoding="utf-8") as fh:
        return fh.read()


# ------------------------------------------------------------------------------------------------ a. static
def test_static():
    raw = {"fcp": 1000, "nav": {"t": 2048, "d": 4096, "e": 300},
           "res": [{"n": "http://x/a.js?v=1", "t": 1024, "d": 3072, "e": 900}, {"n": "http://x/jarvis/three.module.min.js", "t": 10240, "d": 20480, "e": 2000},
                   {"n": "http://x/b.css", "t": 512, "d": 512, "e": 950}], "gl": 2, "gl_page": 1, "heap": 1048576 * 3, "lcp": 1200, "ready": 1500}
    r = PB.summarize(raw)
    check("a. summarize: bytes / requests before the first paint, JS parsed, three.js, contexts",
          r["kb_fcp"] == 3.5 and r["req_fcp"] == 3 and r["req"] == 4 and r["js_kb"] == 23.0 and r["three"] and r["gl"] == 2 and r["gl_page"] == 1
          and r["ready_ms"] == 1500 and r["heap_mb"] == 3.0, r)
    check("a. over_budget names each broken line; a page without a first paint fails",
          PB.over_budget({"fcp_ms": 9000, "kb_fcp": 10, "req_fcp": 3, "js_kb": 10, "gl": 3}) == ["fcp_ms 9000 > 6000", "gl 3 > 1"]
          and "no first paint" in PB.over_budget({"fcp_ms": 0}), PB.over_budget({"fcp_ms": 9000, "gl": 3}))
    t = PB.table_lines([("nq", r), ("x", {"error": "boom"})])
    check("a. the table has a header, a row per page and the error row", len(t) == 4 and t[2].startswith("| nq | 1000 |") and "error: boom" in t[3], t)
    check("a. page_url: root, a folder, a single html file",
          PB.page_url("http://h", "root") == "http://h/" + PB.QUERY and PB.page_url("http://h", "nq") == "http://h/nq/" + PB.QUERY
          and PB.page_url("http://h", "olympus-live.html") == "http://h/olympus-live.html" + PB.QUERY)

    rows = {p: PB.static_row(WEB, p) for p in PB.PAGES if not p.endswith(".html")}
    bad = []
    for p, row in rows.items():
        kb, n = SHELL.get(p, (BLOCK_KB, BLOCK_N))
        if "error" in row or row["block_kb"] > kb or row["block_n"] > n:
            bad.append((p, row.get("block_kb"), row.get("block_n")))
    check(f"a. every page's render-blocking files stay within budget (<= {BLOCK_KB} kB raw / {BLOCK_N} files; root / jarvis held at today's size)", not bad, bad)
    # 2026-11-14 (perf v2): the AGORA kit head (olympus.css, agora.css, polis.css, quiet-net, themes, olympus.js + the page sheet) is 7 files
    # and ~210 kB raw since the 32 looks (themes.js 61 kB): the POLIS libraries themselves stay deferred, which is what this guards
    blk = [os.path.basename(x) for x in PB.eager_files(WEB, os.path.join(WEB, "polis", "index.html"))["blocking"]]
    check("a. Polis: the POLIS libraries are deferred (none of them blocks the first paint; the page + the 7-file kit head, was 13 files / ~380 kB of script)",
          rows["polis"]["block_n"] <= 8 and not [b for b in blk if b.endswith(".js") and b.startswith(("polis", "poliscore"))], [rows["polis"]["block_n"], blk])
    eager3 = [p for p in LAZY if rows[p]["three"]]
    check("a. three.js is never in the eager graph of the lazy 3D pages (" + ", ".join(LAZY) + ")", not eager3, eager3)
    tags = []
    for p, (src, ev) in LAZY.items():
        html = read(os.path.join(WEB, p, "index.html"))
        m = re.search(r'<script src="\.\./olympus/lazy3d\.js[^"]*" data-src="' + re.escape(src) + r'[^"]*" data-skip="lite" data-event="' + re.escape(ev) + r'" defer></script>', html)
        if not m or ('<script type="module" src="' + src) in html:
            tags.append(p)
    check("a. each lazy page loads its 3D module through lazy3d.js (data-src, data-skip=lite, data-event = the module's own ready event), never a module tag", not tags, tags)
    for p, (src, ev) in LAZY.items():
        mod = read(os.path.join(WEB, p, src))
        if ("'" + ev + "'") not in mod:
            tags.append(p + ": " + src + " does not fire " + ev)
    check("a. the data-event of each page is the event its module really fires", not tags, tags)

    oly, rnd, sfx, lz = (read(os.path.join(WEB, "olympus", f)) for f in ("olympus.js", "render.js", "sfx.js", "lazy3d.js"))
    check("a. olympus.js: LITE auto-detection from Save-Data, prefers-reduced-data, a 2g line, deviceMemory, cores (never cores alone on Apple); never stored",
          all(k in oly for k in ("saveData === true", "prefers-reduced-data: reduce", "effectiveType", "deviceMemory", "hardwareConcurrency", "!apple && hc && hc <= 2",
                                 "data-oly-auto", "auto: function"))
          and "var level = stored() || fallback();" in oly and "set(KEY, autoWhy" not in oly)
    check("a. olympus.js: every WebGL canvas gets the guard (getContext wrapped once), the loss is restorable (preventDefault), a still / backdrop shows, data-oly-gl",
          all(k in oly for k in ("P.getContext = wrap", "webglcontextlost", "e.preventDefault()", "oly-gl-still", "webglcontextrestored", "data-oly-gl", "toDataURL('image/jpeg'", "radial-gradient(")))
    check("a. render.js: a lost context draws nothing, a restore rebuilds environment + composer and draws; GPU buffers freed after 20 s hidden and on pagehide",
          all(k in rnd for k in ("webglcontextlost', onLost", "webglcontextrestored', onRestored", "environment(); build(); size(true);", "HIDE_MS = 20000",
                                 "'pagehide', onPageHide", "'pageshow', onPageShow", "removeEventListener('webglcontextlost', onLost)", "restores"))
          and "if (dead || asleep || lost || pageHidden() || offScreen()) return false;" in rnd)
    check("a. sfx.js: a missing format falls back to the other, an HTML answer is never decoded, both missing = synth for the session (no more requests)",
          all(k in sfx for k in ("smpDead", "!smpDead", "text\\/html", "if (!fmtUsed) smpDead = true;", "dead: smpDead")))
    check("a. lazy3d.js: no probe context (WebGL checked without one), after the first paint, never while hidden, skip on LITE (loads on HD)",
          all(k in lz for k in ("WebGLRenderingContext", "requestAnimationFrame", "D.hidden", "O.lite()", "O.onFx", "import(url)", "IntersectionObserver")))


# ------------------------------------------------------------------------------------------------ f. perf v2, static
RQ_NODE = r"""
const RQ = await import(process.argv[1]);
const out = {};
const R = (o) => RQ.range(o);
out.ranges = {
  autoPhone: R({ tier: 'high', chosen: false, maxDpr: 2, device: 3 }), highChosen: R({ tier: 'high', chosen: true, maxDpr: 2, device: 3 }),
  ultraPhone: R({ tier: 'ultra', chosen: true, maxDpr: 1.75, device: 3 }), ultra4k: R({ tier: 'ultra', chosen: true, maxDpr: 2, device: 2 }),
  battery: R({ tier: 'low', chosen: true, maxDpr: 2, device: 3 }), soft: R({ tier: 'ultra', chosen: true, maxDpr: 1.25, device: 3 }),
  saver: R({ tier: 'high', chosen: false, maxDpr: 2, device: 3, saver: true }), software: R({ tier: 'low', software: true, maxDpr: 2, device: 3 }),
};
// a GPU-bound scene: frame ms = cost at dpr 2, scaled by the pixels, quantised to the 60 Hz vsync
const vs = (ms) => Math.ceil(ms / 16.667 - 1e-9) * 16.667;
function run(rg, cost, secs, o) {
  const s = RQ.initial(), x = o || {}, log = [];
  let up = 0; while (up < 6 && RQ.dprAt(rg, up + 1) > RQ.dprAt(rg, up)) up++;
  let dn = 0; while (dn > -4 && RQ.dprAt(rg, dn - 1) < RQ.dprAt(rg, dn)) dn--;
  let t = 0, q0 = 0, i = 0;
  while (t < secs * 1000) {
    const d = RQ.dprAt(rg, s.q), ms = x.at && x.at[i] ? x.at[i] : cost(d);
    t += ms; i++;
    RQ.step(s, t, ms, x.gap || 0, x.work ? x.work(ms) : 0.5, up, dn);
    if (s.q !== q0) { log.push([Math.round(t), s.q, RQ.dprAt(rg, s.q)]); q0 = s.q; }
  }
  return { q: s.q, dpr: RQ.dprAt(rg, s.q), log, locked: Object.keys(s.locked).map(Number), steps: s.steps };
}
const auto = out.ranges.autoPhone;
out.light = run(auto, () => 16.667, 60);
out.heavy = run(auto, (d) => vs(40 * (d / 2) ** 2), 120);
out.holds = run(auto, (d) => vs(16 * Math.max(1, (d / 2.4) ** 2)), 120);
out.cpu = run(auto, () => 40, 30, { work: (ms) => ms * 0.9 });
out.slowGpu = run(out.ranges.ultraPhone, (d) => 300 * (d / 3) ** 2, 40);
out.crawl = run(out.ranges.ultra4k, () => 1500, 120);      // over 1 s a frame (4K on a software GPU): frames, not pauses
out.capped = run(auto, () => 33.33, 30, { gap: 33 });
const hitch = []; for (let k = 0; k < 4000; k++) hitch.push(k % 400 === 200 ? 600 : 16.667);
out.hitch = run(RQ.range({ tier: 'high', chosen: true, maxDpr: 2, device: 2 }), () => 16.667, 60, { at: hitch });
console.log('@@' + JSON.stringify(out));
"""


def node_rq():
    mod = os.path.join(WEB, "olympus", "render-scale.js")
    p = subprocess.run(["node", "--input-type=module", "-e", RQ_NODE, "file://" + mod], capture_output=True, text=True, timeout=120)
    m = [ln for ln in p.stdout.splitlines() if ln.startswith("@@")]
    return json.loads(m[-1][2:]) if m else {"error": (p.stderr or p.stdout)[-600:]}


def test_perf_static():
    fs = PP.frame_stats([16.7] * 50 + [50.0, 100.0])
    check("f. perf_probe.frame_stats: fps from the frame deltas, the 95th percentile, jank = frames over two vsyncs",
          fs["n"] == 52 and 50 < fs["fps"] < 57 and fs["p50"] == 16.7 and fs["p95"] == 16.7 and fs["jank"] == round(100 * 2 / 52, 1) and PP.frame_stats([])["fps"] == 0, fs)
    lt = [[100, 80], [900, 300], [2000, 40], [5000, 260]]
    check("f. TBT = the part over 50 ms of each long task from the first paint on; the longest task after load + 1 s",
          PP.tbt(lt, 500) == 250 + 210 and PP.tbt(lt, 0, 1000) == 30 + 250 and PP.longest_after(lt, 3000) == 260 and PP.longest_after(lt, 6000) == 0,
          [PP.tbt(lt, 500), PP.tbt(lt, 0, 1000), PP.longest_after(lt, 3000)])
    ev = [{"ph": "M", "name": "thread_name", "pid": 1, "tid": 2, "args": {"name": "CrRendererMain"}},
          {"ph": "M", "name": "thread_name", "pid": 9, "tid": 9, "args": {"name": "CrRendererMain"}},
          {"ph": "X", "name": "RunTask", "pid": 1, "tid": 2, "ts": 0, "dur": 10000},
          {"ph": "X", "name": "FunctionCall", "pid": 1, "tid": 2, "ts": 1000, "dur": 4000},
          {"ph": "X", "name": "Layout", "pid": 1, "tid": 2, "ts": 2000, "dur": 1000},           # a layout forced by the script: layout, not script
          {"ph": "B", "name": "UpdateLayoutTree", "pid": 1, "tid": 2, "ts": 6000}, {"ph": "E", "name": "UpdateLayoutTree", "pid": 1, "tid": 2, "ts": 7000},
          {"ph": "X", "name": "Paint", "pid": 1, "tid": 2, "ts": 8000, "dur": 500},
          {"ph": "X", "name": "RunTask", "pid": 9, "tid": 9, "ts": 0, "dur": 900},              # another renderer with less work: not the page
          {"ph": "X", "name": "Paint", "pid": 3, "tid": 3, "ts": 0, "dur": 9000}]               # not a main thread
    bd = PP.trace_breakdown(ev, 1.0)
    check("f. trace breakdown: self time per second on the page's main thread (script 3, layout 1, style 1, paint 0.5, other 4.5, tasks 10 ms/s)",
          bd["script"] == 3.0 and bd["layout"] == 1.0 and bd["style"] == 1.0 and bd["paint"] == 0.5 and bd["other"] == 4.5 and bd["task"] == 10.0, bd)
    c0 = [{"n": "#a", "kind": "webgl2", "w": 780, "h": 400, "cw": 390, "ch": 200, "on": True, "live": True, "calls": 10, "frames": 2, "path": "/x/"}]
    c1 = [dict(c0[0], calls=310, frames=62), {"n": "b", "kind": "2d", "w": 10, "h": 10, "cw": 0, "ch": 0, "on": False, "live": True, "calls": 5, "frames": 5, "path": "/x/"}]
    cr = PP.canvas_rows(c0, c1, 2.0, 3)
    check("f. canvas rows: draws per second, calls per frame, render scale = backing / (CSS x devicePixelRatio), megapixels",
          cr[0]["fps"] == 30.0 and cr[0]["cpf"] == 5.0 and cr[0]["scale"] == 0.67 and cr[0]["mp"] == 0.31 and cr[0]["kind"] == "gl" and cr[1]["kind"] == "2d" and cr[1]["fps"] == 2.5, cr)
    raw = {"snap": {"fcp": 400, "lcp": 900, "cls": 0.01, "load": 1000, "lt": [[600, 120], [2500, 210]], "heap": 8 * 1048576, "nodes": 300},
           "idle": {"task_ms_s": 3.2}, "fps_idle": {"fps": 60.0}, "fps_scroll": {"fps": 58.0, "p95": 18.0, "jank": 1.0},
           "cv_idle": [dict(cr[0], fps=0.0)], "cv_scroll": cr, "trace": {"script": 2.0, "style": 1.0, "layout": 0.5, "paint": 3.0, "task": 20.0}, "trace_t0": 2400, "trace_t1": 3000}
    row = PP.summarize(raw)
    check("f. summarize: a page row (TBT, longest task after load without the ones the trace caused, idle CPU, fps, canvases, render scale)",
          row["tbt"] == 70 + 160 and row["lt_max"] == 210 and row["lt_after"] == 0 and row["idle_ms"] == 3.2 and row["fps_scroll"] == 58.0 and row["gl"] == 1
          and row["gl_scale"] == 0.67 and row["heap_mb"] == 8.0 and row["paint"] == 3.0, row)
    t = PP.table_lines([("nq", row), ("x", {"error": "boom"})])
    check("f. the perf table: a header, a row per page (14 columns) and the error row", len(t) == 4 and t[2].startswith("| nq | 400 / 900 |") and t[2].count("|") == 15 and "error: boom" in t[3], t)
    check("f. page_url: the hubs, the root, an app, ?gpu=1", PP.page_url("http://h", "hub-today") == "http://h/hub/?h=today&" + PP.QUERY
          and PP.page_url("http://h", "root") == "http://h/?" + PP.QUERY and PP.page_url("http://h", "nq", True) == "http://h/nq/?" + PP.QUERY + "&gpu=1")

    r = node_rq()
    if r.get("error"):
        check("f. node runs olympus/render-scale.js", False, r["error"])
    else:
        g = r["ranges"]
        check("f. render scale: Auto on an iPhone = budget 2x, may climb to the full 3x; a chosen High holds 2x; Ultra 4K starts at the full 3x (app caps >= 1.5 lifted)",
              g["autoPhone"] == {"floor": 1, "budget": 2, "ceil": 3} and g["highChosen"]["ceil"] == 2 and g["ultraPhone"] == {"floor": 1.5, "budget": 3, "ceil": 3}, g)
        check("f. render scale: Ultra 4K on a 4K screen (2x) = 2x; Battery = 1.5x; a soft backdrop (maxDpr < 1.5) and software GL never climb; battery saver <= 1.5x",
              g["ultra4k"]["budget"] == 2 == g["ultra4k"]["ceil"] and g["battery"]["ceil"] == 1.5 and g["soft"]["ceil"] == 1.25 and g["software"]["ceil"] == g["software"]["budget"]
              and g["saver"]["ceil"] <= 1.5, g)
        L, H, Hd = r["light"], r["heavy"], r["holds"]
        gaps = [b[0] - a[0] for a, b in zip(H["log"], H["log"][1:])]
        check("f. a light scene climbs to the full 3x (one level at a time, >= 2.5 s apart), never down", L["dpr"] == 3 and len(L["log"]) == 3
              and all(x[1] > 0 for x in L["log"]) and all(b[0] - a[0] >= 2500 for a, b in zip(L["log"], L["log"][1:])), L)
        check("f. a heavy scene steps DOWN smoothly (one level per step, >= 1.2 s apart) to where it keeps full rate (1.19x), and the failed climb is locked (bounded changes: never thrash)",
              abs(H["dpr"] - 1.19) < 0.01 and all(g2 >= 1200 for g2 in gaps) and all(abs(b[1] - a[1]) == 1 for a, b in zip(H["log"], H["log"][1:])) and H["locked"] and H["steps"] <= 12, H)
        check("f. a GPU that holds 2.4x settles at 2.38x after at most 3 failed tries of 2.83x (back-off), then stays", abs(Hd["dpr"] - 2.38) < 0.01 and Hd["steps"] <= 8 and Hd["locked"] == [2], Hd)
        check("f. frames slowed by the page's own JavaScript keep the resolution (a smaller buffer would only blur); a capped idle (30 fps) changes nothing; one 600 ms hitch a few seconds never lowers it",
              r["cpu"]["steps"] == 0 and r["capped"]["steps"] == 0 and r["hitch"]["steps"] == 0, [r["cpu"], r["capped"], r["hitch"]])
        check("f. a very slow GPU (300 ms frames at 3x) still steps down (windows by time, not only by 30 frames); frames over 1 s twice in a row are frames, not a pause (1.5 s frames at 4K reach the floor)",
              r["slowGpu"]["q"] <= -2 and r["slowGpu"]["dpr"] <= 2.2 and r["crawl"]["dpr"] == 1 and r["crawl"]["steps"] >= 3, [r["slowGpu"], r["crawl"]])

    rnd, hs, rs = (read(os.path.join(WEB, "olympus", f)) for f in ("render.js", "hero-stage.js", "render-scale.js"))
    check("f. render.js: the governor sizes every core canvas (Ultra 4K = 3x), no MSAA over 2x, off screen = no frame (IntersectionObserver), the CSS box from a ResizeObserver, shaders compiled in the background",
          all(k in rnd for k in ("from './render-scale.js'", "ultra: { dpr: 3,", "RQ.dpr(myRange())", "RQ.frame(ft", "hiDpr", "new IntersectionObserver", "offScreen()",
                                 "new ResizeObserver", "renderer.compileAsync(scene, camera)", "warm() {", "onScreen: !offScreen()"))
          and "canvas.clientWidth || canvas.width || 1" not in rnd and "if (dead || asleep || lost || pageHidden() || offScreen()) return false;" in rnd)
    check("f. hero-stage.js: the same governor, sleeps off screen / hidden / covered (OLYMPUS.hidden), keeps the kit's idle frame cap, compiles in the background",
          all(k in hs for k in ("from './render-scale.js'", "RQ.dpr(myRange())", "O.hidden", "O.frameGap", "compileAsync", "RQ.frame(now")) and "draw about once a second" not in hs)
    check("f. render-scale.js: no three.js, no DOM needed, one governor per page (window.OLYMPUS_RQ), ?rs= pins a ratio for screenshots",
          not re.search(r"^\s*import\b", rs, re.M) and "document." not in rs and "OLYMPUS_RQ" in rs and "get('rs')" in rs)
    sc = read(os.path.join(WEB, "settings", "settingscore.js"))
    check("f. the Quality picker: Auto / Battery / High / Ultra 4K (+ Still) in the one 3D-quality key jfx (no new key)",
          "['low', 'Battery'" in sc and "['high', 'High'" in sc and "['ultra', 'Ultra 4K'" in sc and "['off', 'Still'" in sc and "fx: 'jfx'" in sc and "olympus.quality" not in sc)
    jv, ag, st = read(os.path.join(WEB, "jarvis", "index.html")), read(os.path.join(WEB, "olympus", "agora.css")), read(os.path.join(WEB, "settings", "settings.css"))
    check("f. cheap paths: Jarvis' 2D stars stop behind the 3D sky; AGORA's sky is a root background (no full repaint per scroll frame); Settings' cards drop the live blur",
          "const behind3d = () => root.dataset.bg3d === 'on'" in jv and 'html[data-theme="agora"] body { background: transparent; }' in ag
          and "backdrop-filter: blur(var(--oly-blur, 14px)) saturate(1.3)" not in st)


# ------------------------------------------------------------------------------------------------ the browser
class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def serve():
    class Srv(http.server.ThreadingHTTPServer):
        daemon_threads = True

        def handle_error(self, request, client_address):
            pass
    srv = Srv(("127.0.0.1", 0), lambda *a: Handler(*a, directory=WEB))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def new_page(br, origin, init=None, fx=None, block_off_site=True):
    ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, is_mobile=True, has_touch=True, service_workers="block")
    if fx:
        ctx.add_init_script(f"try {{ localStorage.setItem('jfx', '{fx}'); }} catch (e) {{}}")
    for s in init or []:
        ctx.add_init_script(s)
    if block_off_site:
        ctx.route(re.compile(r"^(?!" + re.escape(origin) + ").*"), lambda r: r.abort())
    p = ctx.new_page()
    p.__errs = []
    p.on("pageerror", lambda e: p.__errs.append("pageerror: " + str(e)))
    p.on("console", lambda m: p.__errs.append(m.text) if m.type == "error" else None)
    return ctx, p


def requested(p, part):
    return p.evaluate("(s) => performance.getEntriesByType('resource').filter((r) => r.name.indexOf(s) >= 0).map((r) => [r.name, r.startTime])", part)


MEM2 = "Object.defineProperty(Navigator.prototype, 'deviceMemory', { get: () => 2, configurable: true });"
SAVE = "Object.defineProperty(Navigator.prototype, 'connection', { get: () => ({ saveData: true, effectiveType: '4g', addEventListener() {} }), configurable: true });"


def test_auto_lite(br, origin):
    rows = {}
    for name, init, fx in (("plain", [], None), ("memory", [MEM2], None), ("savedata", [SAVE], None), ("owner", [MEM2], "high")):
        ctx, p = new_page(br, origin, init, fx)
        p.goto(origin + "/nq/?welcome=0&intro=0")
        p.wait_for_function("window.NQ && window.NQ.ready()", timeout=30000)
        p.wait_for_timeout(1500)
        rows[name] = p.evaluate("[document.documentElement.dataset.fx, document.documentElement.getAttribute('data-oly-auto') || '', OLYMPUS.auto(), OLYMPUS.lite(), OLYMPUS.chosen()]")
        rows[name].append(len(requested(p, "three.module.min.js")))
        rows[name].append(p.evaluate("!document.getElementById('fallback') || getComputedStyle(document.getElementById('fallback')).visibility !== 'hidden'"))
        ctx.close()
    check("b. no low-end signal on this machine: HD (data-fx=high, no auto)", rows["plain"][:3] == ["high", "", ""], rows["plain"])
    check("b. deviceMemory 2 GB: LITE by itself (data-fx=low, data-oly-auto=memory), not stored as the owner's choice",
          rows["memory"][:5] == ["low", "memory", "memory", True, False], rows["memory"])
    check("b. Save-Data: LITE by itself (save-data)", rows["savedata"][:3] == ["low", "save-data", "save-data"], rows["savedata"])
    check("b. the owner's stored choice wins over the signals (jfx=high on a 2 GB device: HD, no auto)", rows["owner"][:4] == ["high", "", "", False], rows["owner"])
    check("b. on auto-LITE the NQ page never requests three.js (~650 kB of script) and keeps its 2D columns",
          rows["memory"][5] == 0 and rows["savedata"][5] == 0 and rows["memory"][6] is True, rows)


def test_lazy_hd(br, origin):
    ctx, p = new_page(br, origin, [], "high")
    p.goto(origin + "/nq/?welcome=0&intro=0&gpu=1")
    p.wait_for_function("window.NQ && window.NQ.ready() && window.OLYMPUS_LAZY3D && OLYMPUS_LAZY3D.list().some((x) => x.ok)", timeout=45000)
    p.wait_for_function("!!window.NQ3D", timeout=20000)
    fcp = p.evaluate("(performance.getEntriesByType('paint').find((e) => e.name === 'first-contentful-paint') || {}).startTime || 0")
    three = requested(p, "three.module.min.js")
    ok3d = p.wait_for_function("window.NQ.S.scene === 'webgl' || window.NQ.S.scene === '2d'", timeout=20000) and p.evaluate("window.NQ.S.scene")
    check("b. HD: three.js is requested once, after the first paint (lazy3d), and the 3D columns mount",
          len(three) == 1 and fcp > 0 and three[0][1] >= fcp and ok3d == "webgl", [fcp, three, ok3d])
    gl = p.evaluate("OLYMPUS.gl()")
    check("b. HD: one live WebGL context on the page, at most 2 made (nqscene's own probe + its renderer; lazy3d makes none)", gl["live"] == 1 and gl["made"] <= 2, gl)
    check("b. HD: no console error, no page error (a missing optional data file in the source tree is the browser's own network line)",
          not [e for e in p.__errs if "Failed to load resource" not in e], p.__errs)
    ctx.close()


CENTER_DARK = """(sel) => new Promise((res) => {
  const c = document.querySelector(sel); const r = c.getBoundingClientRect(); res([r.left + r.width / 2, r.top + r.height / 2, r.width, r.height]);
})"""


def center_rgb(p, xy):
    from PIL import Image
    import io
    im = Image.open(io.BytesIO(p.screenshot())).convert("RGB")
    k = im.width / 390.0
    box = (int((xy[0] - 40) * k), int((xy[1] - 40) * k), int((xy[0] + 40) * k), int((xy[1] + 40) * k))
    px = [im.getpixel((x, y)) for x in range(box[0], box[2], 4) for y in range(box[1], box[3], 4)]
    return [round(sum(c[i] for c in px) / len(px)) for i in range(3)]


def test_context_loss(br, origin, shots=None):
    # the render core's own page: a scene drawn through createRenderer
    ctx, p = new_page(br, origin, [], None)
    p.goto(origin + "/olympus/render-lab.html?q=low")
    p.wait_for_function("window.__lab && window.__lab.rc && window.__lab.rc.stats().calls > 0", timeout=45000)
    p.wait_for_timeout(2500)                                   # past 1.5 s of frames: the still is taken
    xy = p.evaluate(CENTER_DARK, "canvas")
    before = center_rgb(p, xy)
    p.evaluate("window.__lx = window.__lab.renderer.getContext().getExtension('WEBGL_lose_context'); window.__lx.loseContext()")
    p.wait_for_function("document.documentElement.getAttribute('data-oly-gl') === 'lost'", timeout=10000)
    p.wait_for_timeout(400)
    lost = center_rgb(p, xy)
    bg = p.evaluate("(() => { const o = document.querySelector('.oly-gl-still'); return o ? getComputedStyle(o).backgroundImage : ''; })()")
    place = p.evaluate("""(() => { const o = document.querySelector('.oly-gl-still'), c = document.querySelector('canvas'), a = o.getBoundingClientRect(), b = c.getBoundingClientRect();
      return [o.previousSibling === c, Math.abs(a.left - b.left) + Math.abs(a.top - b.top) + Math.abs(a.width - b.width) + Math.abs(a.height - b.height)]; })()""")
    if shots:
        p.screenshot(path=os.path.join(shots, "ctx_lost.jpg"), type="jpeg", quality=70)
    p.evaluate("window.__lx.restoreContext()")
    p.wait_for_function("document.documentElement.getAttribute('data-oly-gl') === 'ok' && window.__lab.rc.stats().restores >= 1", timeout=15000)
    p.wait_for_timeout(1500)
    st = p.evaluate("(() => { const s = window.__lab.rc.stats(); return [s.lost, s.restores, s.calls, s.passes, s.env]; })()")
    after = center_rgb(p, xy)
    if shots:
        p.screenshot(path=os.path.join(shots, "ctx_restored.jpg"), type="jpeg", quality=70)
    dark = lambda c: max(c) < 14 or min(c) > 240               # black, or the browser's own white "lost" placeholder
    check("c. render core, context lost: the canvas shows the still / AGORA backdrop (never black), html[data-oly-gl=lost]",
          not dark(lost) and "url(\"data:image/jpeg" in bg and "radial-gradient" in bg, [before, lost, bg[:80]])
    check("c. the still sits right after the canvas in the page (its own stacking: never over the page's text) and exactly over its box",
          place[0] is True and place[1] < 2, place)
    check("c. render core, restored: the core rebuilt (restores >= 1) and draws again, the picture is back (not black)",
          st[0] is False and st[1] >= 1 and st[2] > 0 and not dark(after), [st, after])
    check("c. render core: no console error, no page error through the loss and the restore",
          not [e for e in p.__errs if "Context Lost" not in e and "context lost" not in e.lower()], p.__errs)
    ctx.close()

    # a bare three.js page (NQ's columns): the kit's guard alone
    ctx, p = new_page(br, origin, [], "high")
    p.goto(origin + "/nq/?welcome=0&intro=0&gpu=1")
    p.wait_for_function("window.NQ && window.NQ.S.scene === 'webgl' && window.NQ3D.frames() > 5", timeout=60000)
    sel = "#scene3d canvas"
    p.evaluate("(s) => { window.__lx = document.querySelector(s).getContext('webgl2').getExtension('WEBGL_lose_context'); window.__lx.loseContext(); }", sel)
    p.wait_for_function("document.documentElement.getAttribute('data-oly-gl') === 'lost'", timeout=10000)
    bg = p.evaluate("(() => { const o = document.querySelector('.oly-gl-still'); return o ? getComputedStyle(o).backgroundImage : ''; })()")
    xy = p.evaluate(CENTER_DARK, sel)
    lost = center_rgb(p, xy)
    if shots:
        p.screenshot(path=os.path.join(shots, "ctx_lost_nq.jpg"), type="jpeg", quality=70)
    p.evaluate("window.__lx.restoreContext()")
    p.wait_for_function("document.documentElement.getAttribute('data-oly-gl') === 'ok'", timeout=15000)
    gone = p.evaluate("!document.querySelector('.oly-gl-still') && document.querySelector('#scene3d canvas').style.visibility !== 'hidden'")
    check("c. bare three.js page (NQ): the guard's overlay shows the backdrop while lost (not black, not the browser's white placeholder) and goes on restore",
          ("radial-gradient" in bg or "url(" in bg) and max(lost) >= 14 and min(lost) <= 240 and gone, [bg[:80], lost, gone])
    ctx.close()


SAFARI_FMT = """(() => { const f = HTMLMediaElement.prototype.canPlayType; HTMLMediaElement.prototype.canPlayType = function (t) {
  return /ogg/.test(String(t)) ? '' : f.call(this, t); }; })();"""


def test_audio(br, origin):
    out = {}
    for name, block in (("no-m4a", r"\.m4a(\?|$)"), ("none", r"\.(m4a|ogg)(\?|$)")):
        ctx, p = new_page(br, origin, [SAFARI_FMT], None)
        audio = []
        ctx.on("request", lambda r: audio.append(r.url) if re.search(r"/assets/audio/.*\.(m4a|ogg)", r.url) else None)
        p.route(re.compile(r".*/assets/audio/.*" + block), lambda r: r.fulfill(status=404, body="not here", content_type="text/plain"))
        p.goto(origin + "/nq/?welcome=0&intro=0")
        p.wait_for_function("window.NQ && window.NQ.ready() && !!window.OLYMPUS_SFX", timeout=30000)
        st0 = p.evaluate("OLYMPUS_SFX.state().ctxState")
        p.touchscreen.tap(195, 300)
        p.wait_for_timeout(300)
        p.mouse.click(195, 320)
        p.wait_for_function("OLYMPUS_SFX.state().unlocked && OLYMPUS_SFX.state().ctxState === 'running'", timeout=10000)
        p.wait_for_function("(() => { const s = OLYMPUS_SFX.samples(); return s.pending.length === 0 && (s.loaded.length > 0 || s.dead); })()", timeout=20000)
        sm = p.evaluate("OLYMPUS_SFX.samples()")
        played = p.evaluate("OLYMPUS_SFX.play('tap')")
        p.wait_for_timeout(500)
        out[name] = {"before_tap": st0, "samples": {k: sm[k] for k in ("fmt", "loaded", "failed", "dead")}, "played": played,
                     "m4a": len([u for u in audio if ".m4a" in u]), "ogg": len([u for u in audio if ".ogg" in u]),
                     "errors": [e for e in p.__errs if "Failed to load resource" not in e]}
        ctx.close()
    a, b = out["no-m4a"], out["none"]
    check("d. before the first tap nothing sounds (no running context); the tap unlocks it (running)", a["before_tap"] in ("none", "suspended") and b["before_tap"] in ("none", "suspended"), out)
    check("d. a host without .m4a (Safari's format order): falls back to .ogg, the files load, at most 2 failed .m4a requests",
          a["samples"]["fmt"] == "ogg" and "ui" in a["samples"]["loaded"] and not a["samples"]["dead"] and a["m4a"] <= 2, a)
    check("d. no audio files at all: the synth plays (play() true), the recorded layer stops trying (dead), at most 2 + 2 failed requests",
          b["played"] is True and b["samples"]["dead"] is True and b["m4a"] <= 2 and b["ogg"] <= 2, b)
    check("d. no console error and no page error in either case (the failed loads are the browser's own network lines)", not a["errors"] and not b["errors"], out)


REG = """(() => {
  const top = (() => { try { return window.top.__pbReg ? window.top : window; } catch (e) { return window; } })();
  // add() runs in the TOP window's realm: the arrays and WeakRefs it makes belong to the top window (an array or WeakRef made in the app's
  // frame and kept by the top window would keep that frame's whole realm, and every canvas in it, alive: the very leak this measures)
  if (window === window.top) window.__pbReg = { ac: [], gl: [], cv: [], add(kind, x, path) { this[kind].push([new WeakRef(x), String(path)]); } };
  const reg = () => { try { return window.top.__pbReg; } catch (e) { return null; } };
  const A = window.AudioContext || window.webkitAudioContext;
  if (A) { const W = function (...a) { const c = new A(...a); const r = reg(); if (r) r.add('ac', c, location.pathname); return c; }; W.prototype = A.prototype; window.AudioContext = W; window.webkitAudioContext = W; }
  const g = HTMLCanvasElement.prototype.getContext;
  HTMLCanvasElement.prototype.getContext = function (k, ...rest) {
    const c = g.call(this, k, ...rest);
    if (c && /webgl/.test(String(k)) && !this.__pbr) { this.__pbr = 1; const r = reg(); if (r) { r.add('gl', c, location.pathname); r.add('cv', this, location.pathname); } }
    return c;
  };
})();"""
ALIVE = """(() => { const r = window.__pbReg, n = (xs) => xs.filter((x) => x[0].deref()).map((x) => x[1]);
  return { ac: n(r.ac), gl: n(r.gl), cv: n(r.cv), made: [r.ac.length, r.gl.length], frames: document.querySelectorAll('iframe').length,
    heap: performance.memory ? performance.memory.usedJSHeapSize : 0 }; })()"""


def gc(p, n=4):
    for _ in range(n):
        p.evaluate("window.gc && window.gc()")
        p.wait_for_timeout(250)


def test_switch_memory(br, origin):
    ctx, p = new_page(br, origin, [REG, "try { sessionStorage.setItem('jarvis.booted', '1'); localStorage.setItem('jarvis.seen', JSON.stringify('j9')); } catch (e) {}"], "high")
    p.goto(origin + "/jarvis/?welcome=0&intro=0")
    p.wait_for_function("window.__jarvis && document.documentElement.dataset.ready", timeout=60000)
    apps = ["helios", "symposium", "nq", "aegis", "polis", "mint", "chrysos", "ergasterion", "colosseum", "pythia"]
    heaps = []
    for i, a in enumerate(apps):
        p.evaluate("(a) => window.__jarvis.show(a)", a)
        p.wait_for_function("(a) => { const f = document.querySelector('#v-' + a + ' iframe'); return f && f.contentDocument && f.contentDocument.readyState === 'complete'; }", arg=a, timeout=60000)
        p.wait_for_timeout(1500)
        p.mouse.click(195, 460)                                 # a tap inside the app: its sound engine unlocks (an AudioContext per frame)
        p.wait_for_timeout(1200)
        if i in (1, len(apps) - 1):
            gc(p)
            heaps.append(p.evaluate(ALIVE)["heap"])
    # a light 2D app last (Jarvis keeps the last app loaded for a quick return, by design), then home; V8 frees a removed frame's realm
    # only after a few full collections, so GC until nothing more goes (at most 6 rounds)
    p.evaluate("window.__jarvis.show('planner')")
    p.wait_for_function("() => { const f = document.querySelector('#v-planner iframe'); return f && f.contentDocument && f.contentDocument.readyState === 'complete'; }", timeout=60000)
    p.wait_for_timeout(1500)
    p.evaluate("window.__jarvis.show('home')")
    p.wait_for_timeout(1500)
    n0 = None
    for _ in range(6):
        gc(p, 4)
        p.wait_for_timeout(1000)
        alive = p.evaluate(ALIVE)
        n = len(alive["ac"]) + len(alive["cv"])
        if n == n0:
            break
        n0 = n
    kept = "/planner/"
    stray = [x for x in alive["ac"] + alive["cv"] if not x.startswith("/jarvis/") and x != kept]
    grow = (heaps[-1] - heaps[0]) / 1048576.0 if len(heaps) == 2 else None
    check(f"e. 10 app switches in Jarvis: at most one app frame kept (now {alive['frames']})", alive["frames"] <= 1, alive)
    check("e. after the switches + GC no AudioContext / WebGL canvas of a closed app is still alive (made: %d audio contexts, %d WebGL contexts)" % tuple(alive["made"]),
          not stray, stray)
    check("e. JS heap growth from switch 2 to switch 10 stays under 25 MB (%.1f MB)" % (grow or -1), grow is not None and grow < 25, heaps)
    check("e. no page error while switching", not [e for e in p.__errs if e.startswith("pageerror")], p.__errs[:6])
    ctx.close()
    return {"alive": alive, "heap_growth_mb": grow}


# ------------------------------------------------------------------------------------------------ g. perf v2 in Chromium (4K desktop + iPhone)
K4 = {"viewport": {"width": 1920, "height": 1080}, "device_scale_factor": 2}
PHONE = {"viewport": {"width": 390, "height": 844}, "device_scale_factor": 3, "is_mobile": True, "has_touch": True}
# a small, cheap scene on the render core (the frames always keep full rate, even on software GL): what a canvas does when its budget allows
SMALL = """async (o) => {
  const { createRenderer } = await import('./render.js'), T = await import('../jarvis/three.module.min.js');
  if (window.__lab && window.__lab.rc) { window.__lab.rc.dispose(); document.getElementById('lab').style.display = 'none'; }
  const cv = document.createElement('canvas'); cv.id = 'small'; cv.style.cssText = 'position:absolute;left:0;top:0;width:160px;height:90px;inset:auto';
  document.body.appendChild(cv);
  const scene = new T.Scene(), cam = new T.PerspectiveCamera(50, 16 / 9, 0.1, 10); cam.position.z = 3;
  scene.add(new T.Mesh(new T.BoxGeometry(1, 1, 1), new T.MeshStandardMaterial({ color: '#c8a24a', roughness: 0.4 })));
  scene.add(new T.HemisphereLight('#fff', '#333', 2));
  const rc = createRenderer({ canvas: cv, scene, camera: cam, maxDpr: 2, env: 'none' });
  let frames = 0; rc.start(() => { frames++; });
  window.__small = { rc, cv, frames: () => frames };
  await new Promise((r) => setTimeout(r, o.wait));
  const s = rc.stats();
  return { backing: [cv.width, cv.height], css: [cv.clientWidth, cv.clientHeight], dpr: s.dpr, range: s.range, q: s.quality, rq: s.rq, frames, compiled: s.compiled, samples: s.samples };
}"""


def idle_task_ms(p, cdp, ms=4000):
    cdp.send("Performance.enable")
    m = lambda: {x["name"]: x["value"] for x in cdp.send("Performance.getMetrics")["metrics"]}
    a = m()
    p.wait_for_timeout(ms)
    b = m()
    return round((b["TaskDuration"] - a["TaskDuration"]) * 1000.0 / max(0.001, b["Timestamp"] - a["Timestamp"]), 1)


LONG = """(() => { window.__lt = []; try { new PerformanceObserver((l) => { for (const e of l.getEntries()) window.__lt.push([Math.round(e.startTime), Math.round(e.duration)]); })
  .observe({ type: 'longtask', buffered: true }); } catch (e) {} })();"""


def test_perf_4k(br, origin):
    # 1. Ultra 4K on a 4K screen: a canvas whose frames allow it renders at the full device pixel ratio from its first frames, and keeps it
    ctx = br.new_context(service_workers="block", **K4)
    ctx.add_init_script("try { localStorage.setItem('jfx', 'ultra'); } catch (e) {}")
    p = ctx.new_page()
    p.goto(origin + "/olympus/render-lab.html?still=1&gpu=1")
    p.wait_for_function("window.__lab && window.__lab.rc", timeout=60000)
    r = p.evaluate(SMALL, {"wait": 3500})
    check("g. 4K (1920 x 1080 at 2x), Ultra 4K: a canvas whose frames allow it renders at the full pixel ratio (160 x 90 CSS -> 320 x 180), the range is 2x..2x, it drew",
          r["backing"] == [320, 180] and r["dpr"] == 2 and r["range"]["ceil"] == 2 and r["range"]["budget"] == 2 and r["frames"] > 20 and r["compiled"] is True, r)
    # 2. slow frames step it down one level at a time (the governor fed 40 ms frames), never more than one level per window, and back up on full-rate frames
    r2 = p.evaluate("""async () => { const s = window.__small; s.rc.stop();
      const a = OLYMPUS_RQ.simulate(new Array(40).fill(40)); s.rc.render(); await new Promise((r) => setTimeout(r, 50)); const b1 = [s.cv.width, s.cv.height];
      const b = OLYMPUS_RQ.simulate(new Array(40).fill(40)); s.rc.render(); await new Promise((r) => setTimeout(r, 50)); const b2 = [s.cv.width, s.cv.height];
      const c = OLYMPUS_RQ.simulate(new Array(400).fill(16.67)); s.rc.render(); await new Promise((r) => setTimeout(r, 50));
      return { a: a.q, b: b.q, c: c.q, b1, b2, back: [s.cv.width, s.cv.height], downs: c.downs, ups: c.ups }; }""")
    check("g. 4K: slow frames step the canvas down ONE level per window (2x -> 1.68x -> 1.41x: 320 -> 268 -> 225 px), full-rate frames bring it back to 2x",
          r2["a"] == -1 and r2["b"] == -2 and r2["b1"][0] == 268 and r2["b2"][0] == 225 and r2["c"] == 0 and r2["back"] == [320, 180], r2)
    # 3. off screen: the canvas scrolled out of view draws nothing (IntersectionObserver), back on screen it draws again
    r3 = p.evaluate("""async () => { const s = window.__small; s.rc.start(() => {});
      const sp = document.createElement('div'); sp.style.cssText = 'position:absolute;left:0;top:0;width:10px;height:6000px'; document.body.appendChild(sp);
      document.documentElement.style.overflow = 'auto'; document.body.style.overflow = 'auto';
      await new Promise((r) => setTimeout(r, 600)); window.scrollTo(0, 4000); await new Promise((r) => setTimeout(r, 900));
      const f0 = s.frames(); await new Promise((r) => setTimeout(r, 1500)); const f1 = s.frames(), off = s.rc.stats().onScreen;
      window.scrollTo(0, 0); await new Promise((r) => setTimeout(r, 1200)); const f2 = s.frames();
      return { scrolled: window.scrollY, f0, f1, f2, off }; }""")
    check("g. a canvas scrolled off screen runs no frame at all (0 frames in 1.5 s, onScreen false) and comes back when scrolled into view",
          r3["f1"] == r3["f0"] and r3["off"] is False and r3["f2"] > r3["f1"], r3)
    ctx.close()

    # 4. the iPhone (3x), Auto: the same canvas climbs from its 2x budget to the full 3x while frames keep full rate (the governor fed 60 fps)
    ctx = br.new_context(service_workers="block", **PHONE)
    p = ctx.new_page()
    p.goto(origin + "/olympus/render-lab.html?still=1&gpu=1")
    p.wait_for_function("window.__lab && window.__lab.rc", timeout=60000)
    r4 = p.evaluate(SMALL, {"wait": 1500})
    r5 = p.evaluate("""async () => { const s = window.__small; s.rc.stop(); OLYMPUS_RQ.reset(true);
      const st = OLYMPUS_RQ.simulate(new Array(700).fill(16.67)); s.rc.render(); await new Promise((r) => setTimeout(r, 50));
      return { q: st.q, ups: st.ups, backing: [s.cv.width, s.cv.height], range: s.rc.stats().range }; }""")
    check("g. iPhone (3x), Auto: the budget is 2x (320 x 180 at first), and full-rate frames climb it to the full 3x (480 x 270), one level per 2.5 s",
          r4["range"] == {"floor": 1, "budget": 2, "ceil": 3} and r4["backing"][0] in (320, 268, 225) and r5["backing"] == [480, 270] and r5["ups"] == 3, [r4, r5])
    ctx.close()

    # 5. the main pages idle at ~0 CPU and run no long task over 200 ms after load (4K profile)
    rows = {}
    for name, path in (("gate", "/gate/"), ("hub", "/hub/?h=today&"), ("settings", "/settings/"), ("root", "/")):
        ctx = br.new_context(service_workers="block", **K4)
        ctx.add_init_script(LONG)
        p = ctx.new_page()
        cdp = ctx.new_cdp_session(p)
        p.goto(origin + path + ("" if path.endswith("&") else "?") + "welcome=0&intro=0", wait_until="load", timeout=60000)
        load = p.evaluate("performance.getEntriesByType('navigation')[0].loadEventEnd")
        p.wait_for_timeout(9000)                                   # past the Settings preview's 8 s of motion after the start
        idle = idle_task_ms(p, cdp, 4000)
        lt = p.evaluate("window.__lt")
        rows[name] = {"idle_ms_s": idle, "lt_after": max([d for s, d in lt if s >= load + 1000] or [0]), "lt": lt[-6:]}
        ctx.close()
    check("g. 4K: the home, a hub, Settings and the root dashboard idle at ~0 CPU (main thread busy < 25 ms per second while nobody touches them)",
          all(r["idle_ms_s"] < 25 for r in rows.values()), rows)
    check("g. 4K: no long task over 200 ms after load on the home, a hub, Settings and the root dashboard", all(r["lt_after"] <= 200 for r in rows.values()), rows)


def main():
    test_static()
    test_perf_static()
    if "--static" in sys.argv:
        return
    from playwright.sync_api import sync_playwright
    from tests import browser_kit as BK
    srv, origin = serve()
    shots = None
    for a in sys.argv:
        if a.startswith("--shots="):
            shots = a.split("=", 1)[1]
    only = [a for a in sys.argv[1:] if not a.startswith("-")]
    with sync_playwright() as pw:
        br = BK.launch(pw, args=["--enable-unsafe-swiftshader", "--ignore-gpu-blocklist", "--enable-precise-memory-info", "--js-flags=--expose-gc",
                                 "--autoplay-policy=user-gesture-required"])
        for name, fn in (("lite", lambda: test_auto_lite(br, origin)), ("lazy", lambda: test_lazy_hd(br, origin)),
                         ("ctx", lambda: test_context_loss(br, origin, shots)), ("audio", lambda: test_audio(br, origin)),
                         ("switch", lambda: print(test_switch_memory(br, origin))), ("perf", lambda: test_perf_4k(br, origin))):
            if only and name not in only:
                continue
            try:
                fn()
            except Exception as e:  # a section that cannot run is a failure with its reason, the others still run
                check(f"{name}: the section ran", False, repr(e)[:400])
        br.close()
    srv.shutdown()


if __name__ == "__main__":
    t0 = time.time()
    main()
    n = sum(RES)
    print(f"\n{n}/{len(RES)} passed in {time.time() - t0:.0f}s")
    sys.exit(0 if n == len(RES) else 1)
