#!/usr/bin/env python3
"""Perf probe: how smooth each page of a BUILT site runs, on a mid iPhone and on a 4K desktop (team P2, 2026-11-14, docs/OLYMPUS_PERF.md "Perf v2").

    flock -w 2400 /tmp/olympus_browser.lock python -X utf8 tools/perf_probe.py <site folder> [--profiles iphone,4k] [--pages gate,hub-today,...]
        [--json out.json] [--gpu] [--compare <after site>] [--fx high]

tools/phone_budget.py answers "what does a first visit cost on a slow line"; this answers "does it stay smooth once it is open". Per page and profile:
  fcp / lcp      first contentful / largest contentful paint (ms after navigation start; local server, no network throttle: CPU only)
  cls            cumulative layout shift (fonts and late content moving the page)
  tbt / lt_max   total blocking time (sum of long-task time over 50 ms, first paint -> end of the settle window) and the longest task
  lt_after       the longest task that STARTED after the load event + 1 s (the "no long task > 200 ms after load" rule); tasks that start
                 while the trace runs are left out (starting a trace stalls the page by itself)
  idle_ms        main-thread busy time per second while nobody touches the page (CDP TaskDuration over 5 s, no probe running): ~0 = asleep
  fps_idle / fps_scroll   requestAnimationFrame rate while idle / during a synthesized scroll (touch on the phone, wheel on the desktop)
  p95_ms         95th percentile frame time during the scroll
  script / style / layout / paint   main-thread self time per second in each, from a Chromium trace over a second scroll (back up)
  heap_mb        JS heap after the windows
  canvases       every canvas the page made: kind, backing size, CSS size, render scale (backing / (CSS x devicePixelRatio)), on screen,
                 draws per second idle and while scrolling, draw calls per frame (WebGL) / ops per frame (2D)
Profiles: iphone = 390 x 844 at 3x, touch, CPU slowed x4; 4k = 1920 x 1080 at 2x (3840 x 2160 pixels), mouse, CPU as is. The scroll is a
synthesized wheel-style gesture in both (a synthesized TOUCH scroll does not move the page in headless Chromium).
This machine has no GPU: WebGL runs on SwiftShader, so WebGL fps are RELATIVE (before vs after on the same machine), never a real-phone number.
--gpu adds ?gpu=1 (the render core's HD path instead of its software-GL LITE cap). Nothing is written into the site folder.
The arithmetic (trace breakdown, frame stats, tbt, rows, tables) is in plain functions: tests/test_phone_budget.py checks them without a browser.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import phone_budget as PB  # noqa: E402  (serve, launch: the same read-only gzip server and Chromium)

PROFILES = {
    "iphone": {"viewport": (390, 844), "dpr": 3, "mobile": True, "touch": True, "cpu": 4, "gesture": "default"},
    "4k": {"viewport": (1920, 1080), "dpr": 2, "mobile": False, "touch": False, "cpu": 1, "gesture": "mouse"},
}
# the main pages: home, the hubs, the root dashboard, Jarvis and the most used apps / the 3D hero scenes
PAGES = ["gate", "hub-today", "hub-bots", "hub-worlds", "root", "jarvis", "polis", "symposium", "ergasterion", "cities", "nq", "helios", "aegis",
         "mint", "chrysos", "colosseum", "pinakes", "herald", "pythia", "datacity", "arena", "tyche", "oracle", "athena", "pantheon", "settings"]
QUERY = "welcome=0&intro=0"
JARVIS_INIT = "try { sessionStorage.setItem('jarvis.booted', '1'); localStorage.setItem('jarvis.seen', JSON.stringify('j9')); } catch (e) {}"
SETTLE_MS, IDLE_MS, FPS_MS = 3500, 5000, 2500
LONG_AFTER_MS = 200          # the rule: no long task over 200 ms that starts after load + 1 s
GROUPS = {
    "script": ("FunctionCall", "EvaluateScript", "v8.compile", "v8.compileModule", "v8.evaluateModule", "v8.produceCache", "v8.produceModuleCache",
               "TimerFire", "EventDispatch", "FireAnimationFrame", "RunMicrotasks", "V8.Execute", "v8.run", "v8.callFunction", "FireIdleCallback",
               "XHRReadyStateChange", "XHRLoad", "MinorGC", "MajorGC", "ResourceReceivedData"),
    "style": ("UpdateLayoutTree", "RecalculateStyles", "ParseAuthorStyleSheet"),
    "layout": ("Layout",),
    "paint": ("Paint", "PaintImage", "PrePaint", "Layerize", "UpdateLayerTree", "CompositeLayers", "Decode Image", "ImageDecodeTask", "Draw LazyPixelRef"),
    "parse": ("ParseHTML",),
}
TASKS = ("RunTask", "ThreadControllerImpl::RunTask")
CATEGORIES = ["toplevel", "devtools.timeline", "disabled-by-default-devtools.timeline", "v8.execute"]

INIT = r"""
(() => {
  if (window.__pp) return;
  const pp = window.__pp = { lt: [], cls: 0, lcp: 0, fcp: 0, load: 0, cvs: [] };
  const po = (type, fn) => { try { new PerformanceObserver((l) => { for (const e of l.getEntries()) fn(e); }).observe({ type, buffered: true }); } catch (e) {} };
  po('longtask', (e) => pp.lt.push([Math.round(e.startTime), Math.round(e.duration)]));
  po('layout-shift', (e) => { if (!e.hadRecentInput) pp.cls += e.value; });
  po('largest-contentful-paint', (e) => { pp.lcp = e.startTime; });
  po('paint', (e) => { if (e.name === 'first-contentful-paint') pp.fcp = e.startTime; });
  addEventListener('load', () => { pp.load = performance.now(); });
  // every canvas context, its draw calls and drawn frames (a frame = the draws of one task: three.js draws a whole frame in one callback)
  const rec = (cv, kind) => { let r = cv.__pp; if (!r) { r = cv.__pp = { kind, calls: 0, frames: 0, busy: false }; pp.cvs.push(cv); } return r; };
  const gc = HTMLCanvasElement.prototype.getContext;
  HTMLCanvasElement.prototype.getContext = function (kind, ...a) { const c = gc.call(this, kind, ...a); try { if (c) rec(this, String(kind)); } catch (e) {} return c; };
  const hit = (cv) => { const r = cv && cv.__pp; if (!r) return; r.calls++; if (!r.busy) { r.busy = true; r.frames++; queueMicrotask(() => { r.busy = false; }); } };
  const wrap = (P, names) => { if (!P) return; for (const n of names) { const f = P[n]; if (typeof f !== 'function' || f.__pp) continue;
    const w = function (...a) { hit(this.canvas); return f.apply(this, a); }; w.__pp = 1; P[n] = w; } };
  wrap(window.WebGLRenderingContext && WebGLRenderingContext.prototype, ['drawArrays', 'drawElements']);
  wrap(window.WebGL2RenderingContext && WebGL2RenderingContext.prototype, ['drawArrays', 'drawElements', 'drawArraysInstanced', 'drawElementsInstanced', 'drawRangeElements']);
  wrap(window.CanvasRenderingContext2D && CanvasRenderingContext2D.prototype, ['fillRect', 'strokeRect', 'fill', 'stroke', 'drawImage', 'fillText', 'strokeText', 'putImageData']);
  const ge = window.WebGLRenderingContext && WebGLRenderingContext.prototype.getExtension;   // WebGL1 instancing goes through an extension
  if (ge) WebGLRenderingContext.prototype.getExtension = function (n) { const x = ge.call(this, n); const gl = this;
    if (x && n === 'ANGLE_instanced_arrays' && !x.__pp) { x.__pp = 1; for (const m of ['drawArraysInstancedANGLE', 'drawElementsInstancedANGLE']) { const f = x[m]; x[m] = function (...a) { hit(gl.canvas); return f.apply(this, a); }; } }
    return x; };
  const name = (cv) => (cv.id ? '#' + cv.id : '') + (cv.className && typeof cv.className === 'string' ? '.' + cv.className.trim().split(/\s+/).slice(0, 2).join('.') : '')
    || (cv.parentElement ? (cv.parentElement.id ? '#' + cv.parentElement.id : cv.parentElement.tagName.toLowerCase()) + '>canvas' : 'canvas');
  pp.canvases = () => pp.cvs.map((cv) => { const r = cv.__pp, b = cv.getBoundingClientRect(), cs = cv.isConnected ? getComputedStyle(cv) : null;
    const on = !!(cv.isConnected && b.width > 1 && b.height > 1 && b.bottom > 0 && b.right > 0 && b.top < innerHeight && b.left < innerWidth && cs.visibility !== 'hidden' && +cs.opacity > 0);
    return { n: name(cv), kind: r.kind, w: cv.width, h: cv.height, cw: Math.round(b.width), ch: Math.round(b.height), on, live: cv.isConnected, calls: r.calls, frames: r.frames,
      path: location.pathname }; });
  // a frame-time collector (requestAnimationFrame deltas) for a window of ms; the result lands in pp.raf
  pp.rafGo = (ms) => { pp.raf = null; pp.rafEnd = false; const d = []; let last = 0, t0 = 0; const f = (t) => { if (!t0) t0 = t; if (last) d.push(+(t - last).toFixed(2)); last = t;
    if (t - t0 < ms && !pp.rafEnd) requestAnimationFrame(f); else pp.raf = { d, el: t - t0 }; }; requestAnimationFrame(f); return true; };
  pp.rafStop = () => { pp.rafEnd = true; return true; };
})();
"""

SNAP = r"""(() => { const pp = window.__pp; if (!pp) return null;
  return { fcp: pp.fcp, lcp: pp.lcp, cls: +pp.cls.toFixed(4), load: pp.load, lt: pp.lt, canvases: pp.canvases(), dpr: devicePixelRatio,
    heap: performance.memory ? performance.memory.usedJSHeapSize : 0, nodes: document.getElementsByTagName('*').length,
    sh: document.documentElement.scrollHeight, ih: innerHeight, y: scrollY, fx: document.documentElement.getAttribute('data-fx') || '',
    rq: window.OLYMPUS && OLYMPUS.renderScale ? OLYMPUS.renderScale() : null }; })()"""


# ------------------------------------------------------------------------------------------------ pure arithmetic (unit-tested)
def frame_stats(deltas, elapsed_ms=None):
    """requestAnimationFrame deltas (ms) -> {fps, p50, p95, jank (% frames over 2 vsyncs = 33.4 ms), n}"""
    d = [float(x) for x in (deltas or []) if x and x > 0]
    if not d:
        return {"fps": 0.0, "p50": 0.0, "p95": 0.0, "jank": 0.0, "n": 0}
    el = float(elapsed_ms) if elapsed_ms else sum(d)
    s = sorted(d)
    pick = lambda q: s[min(len(s) - 1, int(round(q * (len(s) - 1))))]
    return {"fps": round(len(d) * 1000.0 / max(1.0, el), 1), "p50": round(pick(0.5), 1), "p95": round(pick(0.95), 1),
            "jank": round(100.0 * sum(1 for x in d if x > 33.4) / len(d), 1), "n": len(d)}


def tbt(longtasks, start_ms, end_ms=None):
    """total blocking time: the part over 50 ms of every long task that starts at / after start_ms (and before end_ms)"""
    out = 0
    for st, dur in longtasks or []:
        if st >= (start_ms or 0) and (end_ms is None or st < end_ms):
            out += max(0, dur - 50)
    return int(out)


def longest_after(longtasks, after_ms):
    return max([int(d) for st, d in (longtasks or []) if st >= after_ms] or [0])


def _complete_events(events, keys):
    """X events + B/E pairs (paired per thread) -> {(pid, tid): [(ts, dur, name)]}, microseconds"""
    out, open_ = {}, {}
    for e in events:
        k = (e.get("pid"), e.get("tid"))
        if k not in keys:
            continue
        ph = e.get("ph")
        if ph == "X" and "dur" in e:
            out.setdefault(k, []).append((float(e["ts"]), float(e["dur"]), e.get("name", "")))
        elif ph == "B":
            open_.setdefault(k, []).append((float(e["ts"]), e.get("name", "")))
        elif ph == "E" and open_.get(k):
            ts, nm = open_[k].pop()
            out.setdefault(k, []).append((ts, float(e["ts"]) - ts, nm))
    return out


def trace_breakdown(events, seconds):
    """a Chromium trace (traceEvents) -> main-thread self time per second in script / style / layout / paint / parse / other, and the
    task total. The renderer main thread is the CrRendererMain with the most task time (an app framed by Jarvis runs in the same thread)."""
    keys = {(e.get("pid"), e.get("tid")) for e in events if e.get("ph") == "M" and e.get("name") == "thread_name"
            and (e.get("args") or {}).get("name") == "CrRendererMain"}
    per = _complete_events(events, keys)
    best, best_t = None, -1.0
    for k, evs in per.items():
        t = sum(d for ts, d, n in evs if n in TASKS)
        if t > best_t:
            best, best_t = k, t
    group_of = {}
    for g, names in GROUPS.items():
        for n in names:
            group_of[n] = g
    res = {g: 0.0 for g in list(GROUPS) + ["other"]}
    if best is None:
        res.update({"task": 0.0})
        return {k: 0.0 for k in res}
    evs = sorted(per[best], key=lambda x: (x[0], -x[1]))
    selfs = [d for ts, d, n in evs]
    stack = []                       # indexes of open events
    for i, (ts, dur, nm) in enumerate(evs):
        while stack and evs[stack[-1]][0] + evs[stack[-1]][1] <= ts:
            stack.pop()
        if stack:
            p = stack[-1]
            selfs[p] -= min(dur, evs[p][0] + evs[p][1] - ts)
        stack.append(i)
    for (ts, dur, nm), s in zip(evs, selfs):
        g = group_of.get(nm)
        if g is None:
            if nm in TASKS:
                g = "other"
            elif nm.startswith(("V8.GC", "BlinkGC", "v8.gc", "GC")):
                g = "script"
            else:
                continue          # an event of no group: its self time stays in its parent's
        res[g] += max(0.0, s)
    task = sum(d for ts, d, n in evs if n in TASKS)
    sec = max(0.001, float(seconds))
    out = {k: round(v / 1000.0 / sec, 1) for k, v in res.items()}      # us -> ms per second
    out["task"] = round(task / 1000.0 / sec, 1)
    return out


def canvas_rows(before, after, seconds, dpr):
    """two canvas snapshots (start / end of a window) -> per canvas: backing size, render scale vs devicePixelRatio, draws / s, calls / frame"""
    prev = {(c["path"], i): c for i, c in enumerate(before or [])}
    rows = []
    for i, c in enumerate(after or []):
        p = prev.get((c["path"], i)) or {"calls": 0, "frames": 0}
        calls, frames = max(0, c["calls"] - p["calls"]), max(0, c["frames"] - p["frames"])
        scale = (c["w"] / (c["cw"] * dpr)) if c.get("cw") and dpr else 0.0
        rows.append({"n": c["n"], "path": c["path"], "kind": "2d" if c["kind"] == "2d" else "gl" if "webgl" in c["kind"] else c["kind"],
                     "w": c["w"], "h": c["h"], "cw": c["cw"], "ch": c["ch"], "on": bool(c["on"]), "live": bool(c["live"]),
                     "scale": round(scale, 2), "mp": round(c["w"] * c["h"] / 1e6, 2), "fps": round(frames / max(0.001, seconds), 1),
                     "cpf": round(calls / frames, 1) if frames else 0.0})
    return rows


def summarize(raw):
    """one page x profile run (the probe's raw dict) -> the table row"""
    snap = raw.get("snap") or {}
    lt = snap.get("lt") or []
    fcp, load = float(snap.get("fcp") or 0), float(snap.get("load") or 0)
    idle = raw.get("idle") or {}
    cv_idle = raw.get("cv_idle") or []
    cv_scroll = raw.get("cv_scroll") or []
    gl_on = [c for c in cv_idle if c["kind"] == "gl" and c["live"]]
    row = {
        "fcp": int(round(fcp)), "lcp": int(round(float(snap.get("lcp") or 0))), "cls": float(snap.get("cls") or 0),
        "tbt": tbt(lt, fcp, raw.get("settle_end")), "lt_max": max([int(d) for s, d in lt] or [0]),
        "lt_after": longest_after([x for x in lt if not (raw.get("trace_t0") and raw["trace_t0"] - 50 <= x[0] <= (raw.get("trace_t1") or 1e12))],
                                  load + 1000 if load else 1e12),
        "idle_ms": round(float(idle.get("task_ms_s") or 0), 1), "idle_script": round(float(idle.get("script_ms_s") or 0), 1),
        "fps_idle": (raw.get("fps_idle") or {}).get("fps", 0.0), "fps_scroll": (raw.get("fps_scroll") or {}).get("fps", 0.0),
        "p95_ms": (raw.get("fps_scroll") or {}).get("p95", 0.0), "jank": (raw.get("fps_scroll") or {}).get("jank", 0.0),
        "heap_mb": round(float(snap.get("heap") or 0) / 1048576.0, 1), "nodes": int(snap.get("nodes") or 0),
        "canvases": len(cv_idle), "gl": len(gl_on),
        "cv_idle_fps": max([c["fps"] for c in cv_idle if c["live"]] or [0.0]),
        "cv_off_draws": round(sum(c["fps"] for c in cv_idle if c["live"] and not c["on"]), 1),
        "cv_scroll_fps": max([c["fps"] for c in cv_scroll if c["live"]] or [0.0]),
        "gl_scale": min([c["scale"] for c in gl_on if c["on"] and c["cw"] > 40] or [0.0]),
        "gl_mp": round(sum(c["mp"] for c in gl_on), 2), "gl_cpf": max([c["cpf"] for c in gl_on] or [0.0]),
        "scrolled": int(raw.get("scrolled") or 0), "sh": int(snap.get("sh") or 0),
    }
    row.update({k: (raw.get("trace") or {}).get(k, 0.0) for k in ("script", "style", "layout", "paint", "task")})
    if snap.get("rq"):
        row["rq"] = snap["rq"]
    return row


def lag_score(r):
    """one number to rank the laggiest pages (higher = worse): idle CPU, scroll smoothness, long tasks, GPU pixels drawn while idle"""
    if "error" in r:
        return 0.0
    fps = r.get("fps_scroll") or 0.0
    return round(r.get("idle_ms", 0) * 1.0 + max(0.0, 55.0 - fps) * 4.0 + r.get("lt_max", 0) / 20.0 + r.get("tbt", 0) / 50.0
                 + r.get("cv_idle_fps", 0) * r.get("gl_mp", 0) * 2.0 + r.get("cv_off_draws", 0) * 0.5, 1)


HEAD = ("| page | first paint / LCP ms | TBT ms | longest task ms (after load) | idle main thread ms/s | fps idle / scroll | p95 frame ms | "
        "script / style / layout / paint ms/s | heap MB | canvases (WebGL) | GL draws/s idle | GL MP | GL scale | lag |")


def table_lines(rows):
    out = [HEAD, "|" + "---|" * 14]
    for name, r in rows:
        if "error" in r:
            out.append("| %s | error: %s |%s" % (name, r["error"][:70], " |" * 12))
            continue
        out.append("| %s | %d / %d | %d | %d (%d) | %.1f | %.0f / %.0f | %.0f | %.0f / %.0f / %.0f / %.0f | %.1f | %d (%d) | %.0f | %.2f | %.2f | %.0f |" % (
            name, r["fcp"], r["lcp"], r["tbt"], r["lt_max"], r["lt_after"], r["idle_ms"], r["fps_idle"], r["fps_scroll"], r["p95_ms"],
            r.get("script", 0), r.get("style", 0), r.get("layout", 0), r.get("paint", 0), r["heap_mb"], r["canvases"], r["gl"],
            r["cv_idle_fps"], r["gl_mp"], r["gl_scale"], lag_score(r)))
    return out


def compare_lines(before, after, keys=("fcp", "tbt", "lt_after", "idle_ms", "fps_scroll", "p95_ms", "heap_mb", "cv_idle_fps", "gl_scale")):
    """before / after rows of the same profile -> one line per page: 'a -> b' per key"""
    out = ["| page | " + " | ".join(keys) + " |", "|" + "---|" * (len(keys) + 1)]
    for name in [n for n in after if n in before]:
        a, b = before[name], after[name]
        if "error" in a or "error" in b:
            out.append("| %s | %s |" % (name, (a.get("error") or b.get("error"))[:60]))
            continue
        out.append("| %s | %s |" % (name, " | ".join("%s -> %s" % (_fmt(a.get(k)), _fmt(b.get(k))) for k in keys)))
    return out


def _fmt(v):
    if isinstance(v, float):
        return ("%.2f" % v) if abs(v) < 10 else ("%.0f" % v)
    return str(v)


def page_url(base, name, gpu=False):
    q = QUERY + ("&gpu=1" if gpu else "")
    if name == "root":
        return base + "/?" + q
    if name.startswith("hub-"):
        return base + "/hub/?h=" + name[4:] + "&" + q
    if name.endswith(".html"):
        return base + "/" + name + "?" + q
    return base + "/" + name.strip("/") + "/?" + q


# ------------------------------------------------------------------------------------------------ the browser run
def _metrics(cdp):
    m = {x["name"]: x["value"] for x in cdp.send("Performance.getMetrics")["metrics"]}
    return {k: float(m.get(k, 0.0)) for k in ("TaskDuration", "ScriptDuration", "LayoutDuration", "RecalcStyleDuration", "Timestamp")}


def _all_frames(pg, expr):
    out = []
    for fr in pg.frames:
        try:
            v = fr.evaluate(expr)
        except Exception:
            continue
        if v:
            out.append(v)
    return out


def _canvases(pg):
    rows = []
    for v in _all_frames(pg, "window.__pp ? window.__pp.canvases() : null"):
        rows.extend(v)
    return rows


def measure(br, url, prof, timeout_s=90, trace=True, init=None, settle_ms=SETTLE_MS):
    P = PROFILES[prof]
    ctx = br.new_context(viewport={"width": P["viewport"][0], "height": P["viewport"][1]}, device_scale_factor=P["dpr"], is_mobile=P["mobile"],
                         has_touch=P["touch"], service_workers="block")
    ctx.add_init_script(INIT)
    for s in init or []:
        ctx.add_init_script(s)
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e).splitlines()[0][:160]))
    raw = {}
    try:
        cdp = ctx.new_cdp_session(pg)
        cdp.send("Performance.enable")
        if P["cpu"] > 1:
            cdp.send("Emulation.setCPUThrottlingRate", {"rate": P["cpu"]})
        pg.goto(url, wait_until="load", timeout=timeout_s * 1000)
        pg.wait_for_timeout(settle_ms)
        raw["settle_end"] = pg.evaluate("performance.now()")
        # 1. idle: nobody touches the page, no probe frame loop: what the page costs lying on the table
        m0, c0 = _metrics(cdp), _canvases(pg)
        pg.wait_for_timeout(IDLE_MS)
        m1, c1 = _metrics(cdp), _canvases(pg)
        el = max(0.001, m1["Timestamp"] - m0["Timestamp"])
        raw["idle"] = {"task_ms_s": (m1["TaskDuration"] - m0["TaskDuration"]) * 1000.0 / el, "script_ms_s": (m1["ScriptDuration"] - m0["ScriptDuration"]) * 1000.0 / el,
                       "layout_ms_s": (m1["LayoutDuration"] - m0["LayoutDuration"]) * 1000.0 / el, "style_ms_s": (m1["RecalcStyleDuration"] - m0["RecalcStyleDuration"]) * 1000.0 / el}
        dpr = float(pg.evaluate("devicePixelRatio"))
        raw["cv_idle"] = canvas_rows(c0, c1, el, dpr)
        # 1b. idle frame rate (a probe rAF loop, nobody touching)
        pg.evaluate(f"window.__pp.rafGo({FPS_MS})")
        pg.wait_for_function("window.__pp.raf !== null", timeout=30000)
        r = pg.evaluate("window.__pp.raf")
        raw["fps_idle"] = frame_stats(r["d"], r["el"])
        c2 = _canvases(pg)
        y0 = pg.evaluate("scrollY")
        w, h = P["viewport"]

        def gesture(dist):
            pg.evaluate("window.__pp.rafGo(15000)")
            try:
                cdp.send("Input.synthesizeScrollGesture", {"x": w // 2, "y": int(h * 0.6), "yDistance": dist, "speed": abs(dist),
                                                           "gestureSourceType": P["gesture"], "repeatCount": 1, "preventFling": True})
            except Exception as e:  # a gesture the page swallowed is still a measured window
                raw["gesture_error"] = str(e)[:120]
            pg.evaluate("window.__pp.rafStop()")
            pg.wait_for_function("window.__pp.raf !== null", timeout=30000)
            return pg.evaluate("window.__pp.raf")
        r = gesture(-int(h * 1.6))                           # 2. scroll down: frame rate and long tasks (no trace running)
        raw["fps_scroll"] = frame_stats(r["d"], r["el"])
        c3 = _canvases(pg)
        raw["scrolled"] = int(pg.evaluate("scrollY") - y0)
        raw["cv_scroll"] = canvas_rows(c2, c3, max(0.001, r["el"] / 1000.0), dpr)
        if trace:                                            # 3. the same scroll back up under a trace: where the main thread's time goes
            raw["trace_t0"] = pg.evaluate("performance.now()")
            br.start_tracing(page=pg, categories=CATEGORIES)
            t0 = time.time()
            gesture(int(h * 1.6))
            buf = br.stop_tracing()
            secs = time.time() - t0
            raw["trace_t1"] = pg.evaluate("performance.now()")
            try:
                ev = json.loads(buf)
                ev = ev.get("traceEvents", ev) if isinstance(ev, dict) else ev
                raw["trace"] = trace_breakdown(ev, secs)
            except Exception as e:
                raw["trace_error"] = str(e)[:120]
        raw["snap"] = pg.evaluate(SNAP)
        row = summarize(raw)
        row["errors"] = errs[:5]
        row["cv"] = raw["cv_idle"]
        row["cv_scroll"] = raw["cv_scroll"]
        return row
    except Exception as e:  # a page that never loads is a row, not a crash
        return {"error": str(e).splitlines()[0][:200]}
    finally:
        try:
            ctx.close()
        except Exception:
            pass


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("site")
    ap.add_argument("--pages", default=",".join(PAGES))
    ap.add_argument("--profiles", default="iphone,4k")
    ap.add_argument("--json")
    ap.add_argument("--compare", help="a second built site (the 'after'): each page is measured in both, back to back under the same load")
    ap.add_argument("--gpu", action="store_true", help="add ?gpu=1: the render core's HD path instead of its software-GL LITE cap")
    ap.add_argument("--no-trace", action="store_true")
    ap.add_argument("--fx", default="", help="a stored 3D quality (jfx) for every page: ultra | high | low | off (default: none = Auto)")
    a = ap.parse_args(argv)
    from playwright.sync_api import sync_playwright
    sites = [("before" if a.compare else "", os.path.abspath(a.site))] + ([("after", os.path.abspath(a.compare))] if a.compare else [])
    servers = [(tag, PB.serve(path)) for tag, path in sites]
    out = {}
    if a.json and os.path.isfile(a.json):
        try:
            out = json.load(open(a.json))
        except Exception:
            out = {}
    with sync_playwright() as pw:
        br = PB.launch(pw)
        for prof in [p.strip() for p in a.profiles.split(",") if p.strip()]:
            rows = {tag: [] for tag, _ in sites}
            for name in [p.strip() for p in a.pages.split(",") if p.strip()]:
                init = [JARVIS_INIT] if name == "jarvis" else []
                if a.fx:
                    init.append("try { localStorage.setItem('jfx', %s); } catch (e) {}" % json.dumps(a.fx))
                for tag, (srv, base) in servers:
                    t = time.time()
                    r = measure(br, page_url(base, name, a.gpu), prof, trace=not a.no_trace, init=init)
                    r["wall_s"] = round(time.time() - t, 1)
                    rows[tag].append((name, r))
                    key = prof + ("/" + tag if tag else "")
                    out.setdefault(key, {})[name] = r
                    print(key, name, json.dumps({k: v for k, v in r.items() if k not in ("cv", "cv_scroll")}), flush=True)
                    if a.json:      # after every page: a lock released mid-run keeps what was measured
                        with open(a.json, "w") as fh:
                            json.dump(out, fh, indent=1)
            for tag, _ in sites:
                print("\n## " + prof + (" " + tag if tag else ""))
                print("\n".join(table_lines(rows[tag])))
            if a.compare:
                print("\n## " + prof + ": before -> after")
                print("\n".join(compare_lines(dict(rows["before"]), dict(rows["after"]))))
        br.close()
    for tag, (srv, base) in servers:
        srv.shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
