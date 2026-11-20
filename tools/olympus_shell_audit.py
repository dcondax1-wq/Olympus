"""Olympus main-pages audit (night-revamp-main, 2026-11-20). Owner: "The bottom of my screen is still a little funky ... lag, glitches."

For each MAIN page (Gate, Zenith, Jarvis, Doors, a hub, Settings) in Chromium at iPhone sizes (390x844, 430x932), with the iPhone
home-bar inset emulated (34 px, CDP Emulation.setSafeAreaInsetsOverride when the browser has it):
  - console errors, page errors, failed requests (404 / 500)
  - sideways scroll (document wider than the screen)
  - fixed bottom bars whose keys reach the home indicator (lower than 21 px from the edge), and page content hidden under a fixed bottom bar at the end of the page
  - speed at 4x CPU throttle: time to load, long tasks (count, total ms), frames dropped while scrolling
  - optional screenshots (--shots DIR --tag before|after), dark and light

    python tools/olympus_shell_audit.py --base http://127.0.0.1:8811/ [--shots research/handoff/2026-11-20/revamp-main --tag after] [--json out.json]
Used by tests/test_olympus_shell.py (no shots, no throttle) and by hand for the before / after numbers.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

PAGES = [
    ("gate", "gate/index.html"),
    ("zenith", "index.html#/today"),
    ("jarvis", "jarvis/index.html"),
    ("doors", "hub/doors.html"),
    ("hub", "hub/index.html?h=bots"),
    ("settings", "settings/index.html"),
]
SIZES = [(390, 844), (430, 932)]
INSET = 34   # the iPhone home bar

# JS run in the page: what a phone owner would call "funky" at the bottom
PROBE = r"""(inset) => {
  const W = innerWidth, H = innerHeight, de = document.documentElement;
  const out = { sideways: Math.max(de.scrollWidth, document.body ? document.body.scrollWidth : 0) - W, bars: [], hidden: [] };
  const all = document.querySelectorAll('body *');
  const fixed = [];
  for (const el of all) {
    const cs = getComputedStyle(el);
    if (cs.position !== 'fixed' && cs.position !== 'sticky') continue;
    if (cs.display === 'none' || cs.visibility === 'hidden' || +cs.opacity === 0) continue;
    const r = el.getBoundingClientRect();
    if (r.width < W * 0.5 || r.height < 24 || r.height > H * 0.5) continue;
    if (r.bottom < H - 90 || r.bottom > H + 2 || r.top < H * 0.55) continue;   // a bar at the bottom (glued, or floating a little above the edge)
    if (cs.pointerEvents === 'none' && !el.textContent.trim()) continue;
    fixed.push(el);
    // the bar's tappable content must sit above the home bar
    let lowest = 0;
    el.querySelectorAll('a,button,input,[role=button],[role=tab]').forEach(c => { const q = c.getBoundingClientRect(); if (q.width && q.height) lowest = Math.max(lowest, q.bottom); });
    out.bars.push({ sel: (el.id ? '#' + el.id : el.tagName.toLowerCase() + (el.className && typeof el.className === 'string' ? '.' + el.className.trim().split(/\s+/).join('.') : '')),
      top: Math.round(r.top), gap: Math.round(H - r.bottom), lowestTap: Math.round(lowest), clears: lowest === 0 || lowest <= H - 21 });     // above the home indicator (its top is ~13 px up; the owner wants bars low, not floating)
  }
  // at the end of the page, nothing readable may hide under a bottom bar
  if (fixed.length) {
    const barTop = Math.min(...fixed.map(e => e.getBoundingClientRect().top));
    const leaves = [];
    for (const el of all) {
      if (fixed.some(f => f.contains(el))) continue;
      if (el.children.length && !(el.matches('a,button'))) continue;
      const t = (el.textContent || '').trim(); if (!t && !el.matches('a,button,input,img,canvas')) continue;
      const cs = getComputedStyle(el); if (cs.visibility === 'hidden' || cs.display === 'none' || +cs.opacity === 0) continue;
      let p = el, gone = false; while (p && p !== document.body) { const s = getComputedStyle(p); if (s.display === 'none' || s.visibility === 'hidden' || (s.position === 'fixed' && !fixed.includes(p))) { gone = true; break; } p = p.parentElement; }
      if (gone) continue;
      const r = el.getBoundingClientRect();
      if (r.width < 2 || r.height < 2 || r.bottom <= barTop + 1 || r.top >= H) continue;
      leaves.push(t.slice(0, 40) || el.tagName);
    }
    out.hidden = leaves.slice(0, 5);
  }
  return out;
}"""

# the element the page really scrolls: the document, else the tallest overflow:auto box (Jarvis scrolls #home)
SCROLLER = """window.__scroller = () => { const se = document.scrollingElement; if (se.scrollHeight > innerHeight + 4) return se; let best = se, h = 0;
  for (const e of document.querySelectorAll('*')) { const s = getComputedStyle(e); if ((s.overflowY === 'auto' || s.overflowY === 'scroll') && e.scrollHeight > e.clientHeight + 4 && e.clientHeight > innerHeight * .5 && e.scrollHeight > h) { h = e.scrollHeight; best = e; } }
  return best; }"""

LONG = "window.__lt=[];try{new PerformanceObserver(l=>{for(const e of l.getEntries())window.__lt.push(e.duration)}).observe({type:'longtask',buffered:true})}catch(e){}"


def run(base, shots=None, tag="", throttle=4, sizes=SIZES, pages=PAGES, schemes=("dark",)):
    from playwright.sync_api import sync_playwright
    res = []
    with sync_playwright() as pw:
        br = pw.chromium.launch()
        for name, path in pages:
            for (w, h) in sizes:
                for scheme in schemes:
                    ctx = br.new_context(viewport={"width": w, "height": h}, device_scale_factor=2 if shots else 1, is_mobile=True, has_touch=True,
                                         color_scheme=scheme, service_workers="block")
                    ctx.add_init_script("try{localStorage.setItem('olympus.intro.seen','1');localStorage.setItem('jarvis.intro.seen','1');localStorage.setItem('olympus.sfx.on','0')}catch(e){}")
                    ctx.add_init_script(LONG)
                    p = ctx.new_page()
                    errs, bad = [], []
                    p.on("console", lambda m, errs=errs: errs.append(m.text[:160]) if m.type == "error" else None)
                    p.on("pageerror", lambda e, errs=errs: errs.append("pageerror: " + str(e)[:160]))
                    p.on("response", lambda r, bad=bad: bad.append(f"{r.status} {r.url[len(base):][:90]}") if r.status >= 400 and r.url.startswith(base) else None)
                    cdp = ctx.new_cdp_session(p)
                    inset_ok = False
                    try:
                        cdp.send("Emulation.setSafeAreaInsetsOverride", {"insets": {"top": 47, "bottom": INSET, "left": 0, "right": 0}})
                        inset_ok = True
                    except Exception:
                        pass
                    if throttle and throttle > 1:
                        cdp.send("Emulation.setCPUThrottlingRate", {"rate": throttle})
                    import time
                    t0 = time.time()
                    try:
                        p.goto(base + path, wait_until="load", timeout=90000)
                    except Exception as e:  # noqa: BLE001
                        errs.append("goto: " + str(e)[:120])
                    load_ms = int((time.time() - t0) * 1000)
                    p.wait_for_timeout(2500)
                    # scroll through the page and count dropped frames (a frame > 34 ms = a visible stutter)
                    jank = p.evaluate(SCROLLER + """; new Promise(res => { const se = window.__scroller(); let n = 0, drop = 0, last = performance.now(), y = 0;
                        const max = Math.max(0, se.scrollHeight - innerHeight); const step = () => { const t = performance.now(); if (t - last > 34) drop++; last = t; n++;
                        y = Math.min(max, y + 40); se.scrollTop = y; if (n < 60) requestAnimationFrame(step); else res({ frames: n, dropped: drop }); }; requestAnimationFrame(step); })""")
                    p.evaluate(SCROLLER + '; window.__scroller().scrollTop = 1e6'); p.wait_for_timeout(600)
                    probe = p.evaluate(PROBE, INSET)
                    lt = p.evaluate("window.__lt||[]")
                    r = {"page": name, "w": w, "h": h, "scheme": scheme, "load_ms": load_ms, "long_tasks": len(lt), "long_ms": int(sum(lt)),
                         "dropped": jank["dropped"], "frames": jank["frames"], "errors": errs[:8], "bad": sorted(set(bad))[:8], "inset_emulated": inset_ok, **probe}
                    res.append(r)
                    if shots:
                        p.evaluate(SCROLLER + "; window.__scroller().scrollTop=0")
                        p.wait_for_timeout(300)
                        p.screenshot(path=os.path.join(shots, f"{tag}-{name}-{w}-{scheme}.png"))
                        p.evaluate(SCROLLER + "; window.__scroller().scrollTop=1e6")
                        p.wait_for_timeout(300)
                        p.screenshot(path=os.path.join(shots, f"{tag}-{name}-{w}-{scheme}-bottom.png"))
                    ctx.close()
        br.close()
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8811/")
    ap.add_argument("--shots")
    ap.add_argument("--tag", default="now")
    ap.add_argument("--throttle", type=float, default=4)
    ap.add_argument("--json")
    ap.add_argument("--light", action="store_true", help="also light scheme")
    ap.add_argument("--only")
    a = ap.parse_args()
    pages = [x for x in PAGES if not a.only or x[0] in a.only.split(",")]
    res = run(a.base, a.shots, a.tag, a.throttle, pages=pages, schemes=("dark", "light") if a.light else ("dark",))
    for r in res:
        print(f"{r['page']:9} {r['w']}x{r['h']} {r['scheme']:5} load {r['load_ms']:6}ms  long {r['long_tasks']:3}/{r['long_ms']:6}ms  drop {r['dropped']:2}/{r['frames']}  "
              f"side {r['sideways']:3}  bars {[(b['sel'][:30], b['clears']) for b in r['bars']]}  hidden {r['hidden'][:2]}  err {len(r['errors'])} bad {len(r['bad'])}")
        for e in r["errors"] + r["bad"]:
            print("      ", e)
    if a.json:
        with open(a.json, "w") as f:
            json.dump(res, f, indent=1)


if __name__ == "__main__":
    sys.exit(main())
