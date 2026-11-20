"""Phone QA sweep of the Olympus site (night-siteqa 2026-11-20). Owner: "the bottom of my screen is still a little funky", "lag, glitches",
"No mistakes". Serves tools/web_public, opens each page as an iPhone (390x844 / 430x932, dark / light, safe areas top 47 + home bar 34 through
CDP Emulation.setSafeAreaInsetsOverride, like tests/test_phone_fit.py) and records per page:
  errors   console errors + page errors (the "Failed to load resource" lines are counted as requests instead)
  bad      same-site requests that failed (404 / 500 / aborted), minus the live data files the publisher writes (LIVE, as tests/test_olympus_shell)
  side     sideways scroll (document wider than the phone) + the first elements that stick out
  under    at the very end of the page, readable content lower than the top of a fixed bottom bar or the home bar
  band     empty band between the last line and the home bar at the end of a scrolling page (the old "funky" slab)
  cls      layout shift score during load (CLS; > 0.1 = a visible jump) + the elements that moved
  long     long tasks over 200 ms (only with --throttle, 4x CPU like an older iPhone)
  clip     text cut off inside its box, or a button cut off by its row
Only 127.0.0.1 is reached; ntfy.sh answers with the tests' lite PC fixture (fake numbers), every other host is aborted.
    flock -w 2400 /tmp/olympus_browser.lock python -X utf8 research/handoff/2026-11-20/siteqa/sweep.py --set main --json /tmp/x.json [--throttle 4] [--combo 390d,430l] [--shots DIR]
"""
from __future__ import annotations

import argparse
import functools
import http.server
import json
import os
import re
import sys
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
WEB = os.path.join(ROOT, "tools", "web_public")
sys.path.insert(0, ROOT)
LIVE = re.compile(r"^(home\.json|data\.json|kalshi\.json|money/|me/me\.json|icons/|alerts\.json|writeups/|status_feed\.json|live\.json|kalshicity/(forward|scan)\.json|kalshi/kit\.json|chart\.png|recaps/|hub/learned\.json|business/business\.json|business/lab_pc\.json|agency/my_leads\.json)")

SETS = {
    "main": [("gate", "gate/index.html"), ("home", "index.html#/today"), ("brain", "index.html#/brain"), ("doors", "hub/doors.html"),
             ("zeus", "hub/zeus.html"), ("steps", "hub/steps.html"), ("help", "hub/help.html"), ("me", "hub/index.html?h=me"),
             ("widget", "widget/index.html"), ("glance", "widget/glance.html")],
    "biz": [("business", "business/index.html"), ("accounts", "business/accounts.html"), ("goals", "business/goals.html"), ("lab", "business/lab.html"),
            ("mffu", "business/mffu.html"), ("plan", "business/plan.html"), ("schedule", "business/schedule.html"), ("security", "business/security.html"),
            ("taxes", "business/taxes.html"), ("week", "business/week.html"), ("work", "business/work.html")],
    "zeusapps": [("nq", "nq/index.html"), ("board", "board/index.html"), ("why", "why/index.html"), ("trading", "trading/index.html"),
                 ("aegis", "aegis/index.html"), ("pnyx", "pnyx/index.html"), ("demeter", "demeter/index.html"), ("fates", "fates/index.html"),
                 ("kronos", "kronos/index.html"), ("journal", "journal/index.html"), ("edge", "journal/edge.html")],
    "money": [("ledger", "ledger/index.html"), ("hera", "hera/index.html"), ("chrysos", "chrysos/index.html"), ("oikos", "oikos/index.html"),
              ("agency", "agency/index.html"), ("mercury", "mercury/index.html")],
    "kalshi": [("kalshi", "kalshi/index.html"), ("dionysus", "dionysus/index.html"), ("kalshicity", "kalshicity/index.html"), ("sibyl", "sibyl/index.html"),
               ("tyche", "tyche/index.html")],
    "more": [("compass", "compass/index.html"), ("helios", "helios/index.html"), ("inbox", "inbox/index.html"), ("planner", "planner/index.html"),
             ("settings", "settings/index.html"), ("atlas", "atlas/index.html"), ("clio", "clio/index.html"), ("jarvis", "jarvis/index.html"),
             ("world", "cities/world/index.html"), ("hubbots", "hub/index.html?h=bots")],
}
COMBOS = {"390d": (390, 844, "dark"), "430d": (430, 932, "dark"), "390l": (390, 844, "light"), "430l": (430, 932, "light")}
INSETS = {"top": 47, "bottom": 34, "left": 0, "right": 0}

INIT = r"""
try { localStorage.setItem('olympus.intro.seen','1'); localStorage.setItem('jarvis.intro.seen','1'); localStorage.setItem('olympus.sfx.on','0'); } catch (e) {}
window.__lt = []; window.__cls = 0; window.__shifts = [];
try { new PerformanceObserver(l => { for (const e of l.getEntries()) window.__lt.push([Math.round(e.startTime), Math.round(e.duration)]); }).observe({ type: 'longtask', buffered: true }); } catch (e) {}
try { new PerformanceObserver(l => { for (const e of l.getEntries()) { if (e.hadRecentInput) continue; window.__cls += e.value;
  if (e.value > 0.005) window.__shifts.push([Math.round(e.startTime), +e.value.toFixed(3), (e.sources || []).slice(0, 3).map(s => { const n = s.node;
    if (!n || !n.tagName) return '?'; return (n.tagName + (n.id ? '#' + n.id : '') + (typeof n.className === 'string' && n.className ? '.' + n.className.trim().split(/\s+/).slice(0, 2).join('.') : '')).slice(0, 50)
      + ' ' + Math.round(s.previousRect.y) + '>' + Math.round(s.currentRect.y); })]); } }).observe({ type: 'layout-shift', buffered: true }); } catch (e) {}
"""

SCROLLER = """window.__scroller = () => { const se = document.scrollingElement; if (se.scrollHeight > innerHeight + 4) return se; let best = se, h = 0;
  for (const e of document.querySelectorAll('*')) { const s = getComputedStyle(e); if ((s.overflowY === 'auto' || s.overflowY === 'scroll') && e.scrollHeight > e.clientHeight + 4 && e.clientHeight > innerHeight * .5 && e.scrollHeight > h) { h = e.scrollHeight; best = e; } }
  return best; }"""

# at the very end of the page: the lowest readable thing vs the fixed bottom bars and the home bar
MEASURE = r"""(sb) => {
  const H = innerHeight, W = innerWidth, de = document.documentElement;
  const nm = (e) => (e.tagName + (e.id ? '#' + e.id : '') + (typeof e.className === 'string' && e.className.trim() ? '.' + e.className.trim().split(/\s+/).slice(0, 2).join('.') : '')).slice(0, 48);
  const bars = [], fixedAll = [];
  for (const e of document.querySelectorAll('body *')) {
    const s = getComputedStyle(e);
    if (s.position !== 'fixed' && s.position !== 'sticky') continue;
    if (s.position === 'fixed') fixedAll.push(e);
    if (s.display === 'none' || s.visibility === 'hidden' || +s.opacity < 0.05) continue;
    const r = e.getBoundingClientRect();
    if (r.width < 8 || r.height < 8 || r.height > H * 0.6 || r.bottom < H * 0.75 || r.top > H - 2) continue;
    if (s.pointerEvents === 'none' && !e.textContent.trim()) continue;
    if (s.position === 'sticky' && r.bottom < H - 4) continue;
    bars.push({ el: e, top: r.top, id: nm(e) });
  }
  const inFixed = (e) => fixedAll.some((f) => f.contains(e));
  let last = 0, lastEl = '';
  const hidden = [];
  const barTop = bars.length ? Math.min(...bars.map((b) => b.top)) : H;
  const limit = Math.min(barTop, H - sb);
  for (const e of document.querySelectorAll('body *')) {
    if (/^(SCRIPT|STYLE|TEMPLATE|NOSCRIPT|OPTION)$/.test(e.tagName)) continue;
    const own = [...e.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim()) || /^(A|BUTTON|INPUT|SELECT|IMG|TEXTAREA)$/.test(e.tagName);
    if (!own) continue;
    if (inFixed(e)) continue;
    const shut = e.closest('details:not([open])'); if (shut && !e.closest('summary')) continue;
    let r = e.getBoundingClientRect();
    if (!/^(A|BUTTON|INPUT|SELECT|IMG|TEXTAREA)$/.test(e.tagName)) {             // a text block: its words, not its padding
      let t = Infinity, b = -Infinity;
      for (const n of e.childNodes) { if (n.nodeType !== 3 || !n.textContent.trim()) continue; const rg = document.createRange(); rg.selectNodeContents(n);
        for (const q of rg.getClientRects()) { if (q.width < 1) continue; t = Math.min(t, q.top); b = Math.max(b, q.bottom); } }
      if (b > t) r = { top: t, bottom: b, width: r.width, height: b - t };
    }
    if (r.height < 2 || r.width < 2) continue;
    let top = r.top, bot = r.bottom, gone = false;
    for (let p = e; p && p !== de; p = p.parentElement) {
      const s = getComputedStyle(p);
      if (s.display === 'none' || s.visibility === 'hidden' || +s.opacity < 0.05) { gone = true; break; }
      if (p !== e && p !== document.body && (s.overflowY !== 'visible' || s.overflowX !== 'visible')) { const q = p.getBoundingClientRect(); top = Math.max(top, q.top); bot = Math.min(bot, q.bottom); }
      if (s.clipPath && s.clipPath !== 'none' && /inset\(50%|circle\(0/.test(s.clipPath)) { gone = true; break; }
      if (s.clip && s.clip !== 'auto') { gone = true; break; }
    }
    if (gone || bot - top < 2 || top >= H) continue;
    if (bot > last) { last = bot; lastEl = nm(e) + ' "' + (e.textContent || e.value || '').trim().slice(0, 28) + '"'; }
    if (bot > limit + 0.5 && hidden.length < 4) hidden.push(nm(e) + ' "' + (e.textContent || '').trim().slice(0, 24) + '" ' + Math.round(top) + '-' + Math.round(bot));
  }
  const sc = window.__scroller ? window.__scroller() : document.scrollingElement;
  return { W, H, sw: Math.max(de.scrollWidth, document.body ? document.body.scrollWidth : 0), last: Math.round(last), lastEl, hidden,
           bars: bars.map((b) => [b.id, Math.round(b.top)]), barTop: Math.round(barTop), limit: Math.round(limit),
           scrolls: sc.scrollHeight > sc.clientHeight + 4 };
}"""

WIDE = r"""(() => { const W = innerWidth, out = [];
  for (const e of document.querySelectorAll('body *')) { const r = e.getBoundingClientRect(), s = getComputedStyle(e);
    if (s.position === 'fixed' || r.width < 1 || s.visibility === 'hidden') continue;
    let p = e.parentElement, clip = false; while (p && p !== document.body) { const o = getComputedStyle(p).overflowX; if (o === 'auto' || o === 'scroll' || o === 'hidden' || o === 'clip') { clip = true; break; } p = p.parentElement; }
    if (!clip && r.right > 0 && (r.right > W + 1.5 || r.left < -1.5)) out.push((e.tagName + '.' + (typeof e.className === 'string' ? e.className : '')).slice(0, 40) + ' ' + Math.round(r.left) + '..' + Math.round(r.right)); if (out.length > 4) break; }
  return out; })()"""

# text cut inside its own box (overflow hidden, no ellipsis), a control cut by its row, a control off the screen sideways
CLIP = r"""(() => { const W = innerWidth, H = innerHeight, out = [];
  const nm = (e) => (e.tagName + (e.id ? '#' + e.id : '') + (typeof e.className === 'string' && e.className.trim() ? '.' + e.className.trim().split(/\s+/).slice(0, 2).join('.') : '')).slice(0, 48);
  const shown = (e) => { for (let p = e; p && p !== document.documentElement; p = p.parentElement) { const s = getComputedStyle(p);
      if (s.display === 'none' || s.visibility === 'hidden' || +s.opacity < 0.05) return false; if (p.tagName === 'DETAILS' && !p.open && !e.closest('summary')) return false; } return true; };
  for (const e of document.querySelectorAll('body *')) {
    if (out.length > 7) break;
    const s = getComputedStyle(e); if (s.display === 'inline' || s.display === 'contents' || s.display === 'none') continue;
    const r = e.getBoundingClientRect(); if (r.width < 4 || r.height < 4) continue;
    const own = [...e.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim());
    const ctl = /^(BUTTON|A|SELECT|INPUT|LABEL|SUMMARY)$/.test(e.tagName) || e.getAttribute('role') === 'button' || e.getAttribute('role') === 'tab';
    if (own && (s.overflowX === 'hidden' || s.overflowX === 'clip') && s.textOverflow !== 'ellipsis' && e.scrollWidth > e.clientWidth + 2 && e.clientWidth > 0 && !/^(INPUT|SELECT|TEXTAREA)$/.test(e.tagName)) {
      if (shown(e)) out.push('cut sideways: ' + nm(e) + ' "' + e.textContent.trim().slice(0, 30) + '" ' + e.scrollWidth + '>' + e.clientWidth); continue; }
    if (own && (s.overflowY === 'hidden' || s.overflowY === 'clip') && e.scrollHeight > e.clientHeight + 3 && e.clientHeight > 0 && !/-webkit-box/.test(s.display) && s.webkitLineClamp === 'none') {
      if (shown(e)) out.push('cut below: ' + nm(e) + ' "' + e.textContent.trim().slice(0, 30) + '" ' + e.scrollHeight + '>' + e.clientHeight); continue; }
    if (ctl) {
      if (s.position !== 'fixed' && r.right > 0 && (r.right > W + 1 || r.left < -1) && r.top < H * 4) {
        let sc = false; for (let p = e.parentElement; p && p !== document.body; p = p.parentElement) { const o = getComputedStyle(p).overflowX; if (o === 'auto' || o === 'scroll') { sc = true; break; } }
        if (!sc && shown(e)) out.push('off screen: ' + nm(e) + ' "' + e.textContent.trim().slice(0, 30) + '" ' + Math.round(r.left) + '..' + Math.round(r.right));
        continue; }
      for (let p = e.parentElement; p && p !== document.documentElement; p = p.parentElement) {
        const q = getComputedStyle(p);
        if (q.overflowX === 'auto' || q.overflowX === 'scroll' || q.overflowY === 'auto' || q.overflowY === 'scroll') break;
        if (q.overflowX === 'hidden' || q.overflowX === 'clip' || q.overflowY === 'hidden' || q.overflowY === 'clip') {
          const b = p.getBoundingClientRect();
          if (b.width > 4 && b.height > 4 && (r.right > b.right + 1.5 || r.left < b.left - 1.5 || r.bottom > b.bottom + 1.5 || r.top < b.top - 1.5) && shown(e))
            out.push('control cut by ' + nm(p) + ': ' + nm(e) + ' "' + e.textContent.trim().slice(0, 24) + '"');
          break; }
      }
    }
  }
  return out; })()"""


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def lite_msg():
    from tests.test_phone_fit import lite_fixture
    now = int(time.time())
    return json.dumps({"id": "x1", "time": now - 240, "event": "message", "topic": "t", "message": json.dumps(lite_fixture(now))})


def run(pages, combos, throttle=0, shots=None, wait_ms=3000):
    from playwright.sync_api import sync_playwright
    from tests import browser_kit as BK
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=WEB))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}/"
    msg = lite_msg()
    out = []
    try:
        with sync_playwright() as pw:
            br = BK.launch(pw)
            for name, path in pages:
                for cb in combos:
                    w, h, scheme = COMBOS[cb]
                    ctx = br.new_context(viewport={"width": w, "height": h}, device_scale_factor=2 if shots else 1, is_mobile=True, has_touch=True,
                                         color_scheme=scheme, reduced_motion="no-preference", service_workers="block")
                    ctx.route("**/*", lambda r: r.continue_() if r.request.url.startswith(base) else r.abort())
                    ctx.route("**/ntfy.sh/**", lambda r: r.fulfill(status=200, content_type="application/x-ndjson", body=msg + "\n"))
                    ctx.add_init_script(INIT)
                    p = ctx.new_page()
                    errs, bad = [], []
                    p.on("console", lambda m, errs=errs: errs.append(m.text[:200]) if m.type == "error" and "Failed to load resource" not in m.text else None)
                    p.on("pageerror", lambda e, errs=errs: errs.append("pageerror: " + str(e)[:200]))
                    p.on("response", lambda r, bad=bad: bad.append(f"{r.status} {r.url[len(base):][:100]}") if r.status >= 400 and r.url.startswith(base) else None)
                    p.on("requestfailed", lambda r, bad=bad: bad.append(f"failed {r.url[len(base):][:100]} {r.failure}") if r.url.startswith(base) else None)
                    cdp = ctx.new_cdp_session(p)
                    try:
                        cdp.send("Emulation.setSafeAreaInsetsOverride", {"insets": INSETS})
                        sb = INSETS["bottom"]
                    except Exception:  # noqa: BLE001
                        sb = 0
                    thr = throttle if (throttle and cb == combos[0]) else 0
                    if thr:
                        cdp.send("Emulation.setCPUThrottlingRate", {"rate": thr})
                    t0 = time.time()
                    try:
                        p.goto(base + path, wait_until="load", timeout=90000)
                    except Exception as e:  # noqa: BLE001
                        errs.append("goto: " + str(e)[:150])
                    load_ms = int((time.time() - t0) * 1000)
                    p.wait_for_timeout(wait_ms * (2 if thr else 1))
                    try:
                        cls = p.evaluate("[window.__cls, window.__shifts.slice(0, 6), window.__lt]")
                        clip = p.evaluate(CLIP)
                        if shots and cb == "390d":
                            p.screenshot(path=os.path.join(shots, f"{name}.png"))
                        p.evaluate(SCROLLER + "; window.__scroller().scrollTop = 1e7; window.scrollTo(0, 1e7)")
                        p.wait_for_timeout(700)
                        m = p.evaluate(MEASURE, sb)
                        wide = p.evaluate(WIDE)
                    except Exception as e:  # noqa: BLE001
                        errs.append("probe: " + str(e)[:150])
                        cls, clip, m, wide = [0, [], []], [], {"W": w, "H": h, "sw": 0, "last": 0, "lastEl": "", "hidden": [], "bars": [], "barTop": h, "limit": h, "scrolls": False}, []
                    lt = cls[2] or []
                    r = {"page": name, "path": path, "combo": cb, "throttle": thr, "load_ms": load_ms, "errors": errs[:8], "bad": sorted(set(bad))[:10],
                         "bad_real": sorted({b for b in bad if not LIVE.match(b.split(" ", 1)[1].split("?")[0])})[:10],
                         "side": m["sw"] - m["W"], "wide": wide, "under": m["hidden"], "last": m["last"], "limit": m["limit"], "lastEl": m["lastEl"],
                         "bars": m["bars"], "band": (m["H"] - sb - m["last"]) if m["scrolls"] else None, "cls": round(cls[0], 3), "shifts": cls[1],
                         "long200": [x for x in lt if x[1] > 200], "long_ms": sum(x[1] for x in lt), "clip": clip}
                    out.append(r)
                    flag = []
                    if r["errors"]: flag.append(f"ERR{len(r['errors'])}")
                    if r["bad_real"]: flag.append(f"404x{len(r['bad_real'])}")
                    if r["side"] > 0 or wide: flag.append(f"SIDE{r['side']}")
                    if r["under"]: flag.append("UNDER")
                    if r["band"] is not None and r["band"] > 120: flag.append(f"BAND{r['band']}")
                    if r["cls"] > 0.1: flag.append(f"CLS{r['cls']}")
                    if r["long200"]: flag.append(f"LONG{len(r['long200'])}")
                    if clip: flag.append(f"CLIP{len(clip)}")
                    print(f"{name:10} {cb} load {load_ms:6}ms cls {r['cls']:.3f} long>200 {len(r['long200'])} side {r['side']} band {r['band']} last {r['last']}/{r['limit']}  {' '.join(flag) or 'ok'}", flush=True)
                    p.close()
                    ctx.close()
    finally:
        srv.shutdown()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="main")
    ap.add_argument("--only")
    ap.add_argument("--combo", default="390d,430l")
    ap.add_argument("--throttle", type=float, default=0)
    ap.add_argument("--shots")
    ap.add_argument("--json")
    a = ap.parse_args()
    pages = [x for s in a.set.split(",") for x in SETS[s]]
    if a.only:
        pages = [x for x in pages if x[0] in a.only.split(",")]
    if a.shots:
        os.makedirs(a.shots, exist_ok=True)
    res = run(pages, a.combo.split(","), a.throttle, a.shots)
    if a.json:
        with open(a.json, "w") as f:
            json.dump(res, f, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
