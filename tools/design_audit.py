"""Olympus design audit (day-arenas / DESIGN team, 2026-11-20). Measures every app of the DESIGN slice against THE OLYMPUS BAR in Chromium at
390x844 (dark and the Ivory light look), and writes a table: what drifts from the kit (olympus/shell.css + agora.css + pulse.css) and what
breaks the bar. Read only: it opens pages, it changes nothing.

    python tools/design_audit.py --site <built site or tools/web_public> [--apps a,b] [--json out.json] [--md out.md]

Per page: kit sheets loaded (agora / shell / pulse), checked in light (<html data-oly-light>), console errors, failed requests, first
contentful paint, longest task, layout shift, sideways scroll, tap targets under 44 px, text under 12 px, text below AA contrast (4.5:1
on its own opaque background, sampled), font families used, card radius values, the page background in light (is it really light).
"""
from __future__ import annotations

import argparse
import functools
import http.server
import json
import os
import sys
import threading

APPS = {"zenith": "index.html#/today", "business": "business/index.html", "plan": "business/plan.html", "ledger": "ledger/index.html",
        "aegis": "aegis/index.html", "demeter": "demeter/index.html", "fates": "fates/index.html", "hera": "hera/index.html",
        "journal": "journal/index.html", "helios": "helios/index.html", "compass": "compass/index.html", "kronos": "kronos/index.html",
        "pnyx": "pnyx/index.html", "chrysos": "chrysos/index.html", "mercury": "mercury/index.html", "oikos": "oikos/index.html",
        "planner": "planner/index.html", "clio": "clio/index.html", "settings": "settings/index.html?tour=0", "atlas": "atlas/index.html"}

INIT = """try{localStorage.setItem('olympus.intro.seen','1');localStorage.setItem('jarvis.intro.seen','1');localStorage.setItem('olympus.sfx.on','0');%s}catch(e){}
window.__cls=0;window.__lt=[];try{new PerformanceObserver(l=>{for(const e of l.getEntries())if(!e.hadRecentInput)window.__cls+=e.value}).observe({type:'layout-shift',buffered:true});
new PerformanceObserver(l=>{for(const e of l.getEntries())window.__lt.push(Math.round(e.duration))}).observe({type:'longtask',buffered:true})}catch(e){}"""

PROBE = r"""() => {
  const W = innerWidth, de = document.documentElement, out = {};
  const sheets = [...document.querySelectorAll('link[rel=stylesheet]')].map((l) => l.getAttribute('href') || '');
  // Zenith carries the shell layer inline (<style id="oly-shell">) and AGORA as its own zenith_agora.css layer: both count
  out.kit = { agora: sheets.some((h) => /olympus\/agora\.css|zenith_agora\.css/.test(h)), shell: sheets.some((h) => /olympus\/shell\.css/.test(h)) || !!document.getElementById('oly-shell'), pulse: sheets.some((h) => /olympus\/pulse\.css/.test(h)) };
  out.lightReady = de.hasAttribute('data-oly-light');
  out.sideways = Math.max(de.scrollWidth, document.body ? document.body.scrollWidth : 0) - W;
  const fcp = performance.getEntriesByName('first-contentful-paint')[0]; out.fcp = fcp ? Math.round(fcp.startTime) : null;
  const vis = (e) => { const r = e.getBoundingClientRect(); const cs = getComputedStyle(e); return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none' && +cs.opacity > 0.05; };
  const taps = [...document.querySelectorAll('a[href], button, [role=button], [role=tab], input:not([type=hidden]), select, summary')].filter(vis);
  // a switch / checkbox inside a row label that is >= 44 px tall: the whole row is the tap target (iOS Settings style)
  // an invisible ring (::before / ::after, position absolute, a negative inset) widens the tap: count it (Zenith's header keys)
  const ring = (e) => Math.max(0, ...['::before', '::after'].map((p) => { const c = getComputedStyle(e, p); return c.content !== 'none' && c.position === 'absolute' && parseFloat(c.top) < 0 ? -2 * parseFloat(c.top) : 0; }));
  out.small = taps.filter((e) => { const r = e.getBoundingClientRect(); const lab = e.closest('label'); return r.height + ring(e) < 43.5 && !e.closest('p, li > span, .pu-note') && !(lab && lab.getBoundingClientRect().height >= 43.5); })
    .slice(0, 400).map((e) => (e.id ? '#' + e.id : (e.className && typeof e.className === 'string' ? '.' + e.className.split(' ')[0] : e.tagName.toLowerCase())) + ':' + Math.round(e.getBoundingClientRect().height));
  out.smallN = out.small.length; out.small = [...new Set(out.small)].slice(0, 8);
  const texts = []; const tw = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  while (tw.nextNode() && texts.length < 1500) { const n = tw.currentNode; if (n.textContent.trim().length > 1 && n.parentElement && vis(n.parentElement)) texts.push(n.parentElement); }
  const uniq = [...new Set(texts)];
  const px = (e) => parseFloat(getComputedStyle(e).fontSize);
  out.tiny = uniq.filter((e) => px(e) < 12 && !e.closest('svg')).length;
  const fams = {}; for (const e of uniq) { const f = getComputedStyle(e).fontFamily.split(',')[0].replace(/["']/g, '').trim(); fams[f] = (fams[f] || 0) + 1; }
  out.fonts = Object.entries(fams).sort((a, b) => b[1] - a[1]).slice(0, 6).map(([f, n]) => f + ' ' + n);
  const rgb = (c) => { const m = String(c).match(/[\d.]+/g); if (!m) return [0, 0, 0, 0]; const v = m.map(Number);   // color(srgb r g b / a) is 0..1
    return /^color\(/.test(String(c)) ? v.slice(0, 3).map((x) => x * 255).concat(v.length > 3 ? [v[3]] : []) : v; };
  const lum = (c) => { const v = c.slice(0, 3).map((x) => { x /= 255; return x <= 0.03928 ? x / 12.92 : Math.pow((x + 0.055) / 1.055, 2.4); }); return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2]; };
  const bgOf = (e) => { let x = e; while (x) { const c = rgb(getComputedStyle(x).backgroundColor); if (c.length >= 3 && (c[3] === undefined || c[3] > 0.6) && !(c.length > 3 && c[3] === 0)) return c; if (getComputedStyle(x).backgroundImage !== 'none' && x !== document.body && x !== de) return null; x = x.parentElement; }
    return rgb(getComputedStyle(document.body).backgroundColor); };
  const bad = [];
  for (const e of uniq.slice(0, 600)) {
    const bg = bgOf(e); if (!bg) continue; const fg = rgb(getComputedStyle(e).color); if (fg.length > 3 && fg[3] < 0.5) continue;
    const L1 = lum(fg), L2 = lum(bg), r = (Math.max(L1, L2) + 0.05) / (Math.min(L1, L2) + 0.05);
    const big = px(e) >= 18.66 || (px(e) >= 14 && +getComputedStyle(e).fontWeight >= 700);
    if (r < (big ? 3 : 4.5)) bad.push((e.id ? '#' + e.id : e.className && typeof e.className === 'string' ? '.' + e.className.split(' ')[0] : e.tagName.toLowerCase()) + ' ' + r.toFixed(1) + ':' + e.textContent.trim().slice(0, 24));
  }
  out.lowContrastN = bad.length; out.lowContrast = [...new Set(bad)].slice(0, 6);
  const radii = {}; for (const e of document.querySelectorAll('.card, .ag-card, section, article')) { if (!vis(e)) continue; const r = getComputedStyle(e).borderTopLeftRadius; if (r !== '0px') radii[r] = (radii[r] || 0) + 1; }
  out.radii = Object.entries(radii).sort((a, b) => b[1] - a[1]).slice(0, 5).map(([r, n]) => r + 'x' + n);
  out.bg = getComputedStyle(document.body).backgroundColor; out.h = de.scrollHeight;
  return out;
}"""


def serve(site):
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(H, directory=site))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}/"


def run(site, apps, shots=None, tag="audit"):
    from playwright.sync_api import sync_playwright
    srv, base = serve(site)
    res = []
    with sync_playwright() as pw:
        br = pw.chromium.launch()
        for app in apps:
            for scheme in ("dark", "light"):
                ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2 if shots else 1, is_mobile=True, has_touch=True, service_workers="block")
                ctx.add_init_script(INIT % ("localStorage.setItem('olympus.theme','ivory');" if scheme == "light" else ""))
                p = ctx.new_page(); errs, bad = [], []
                p.on("pageerror", lambda e, errs=errs: errs.append("page: " + str(e)[:140]))
                p.on("console", lambda m, errs=errs: errs.append(m.text[:140]) if m.type == "error" else None)
                p.on("response", lambda r, bad=bad: bad.append(f"{r.status} {r.url[len(base):][:70]}") if r.status >= 400 and r.url.startswith(base) else None)
                try:
                    p.goto(base + APPS[app], wait_until="load", timeout=60000)
                except Exception as e:  # noqa: BLE001
                    errs.append("goto " + str(e)[:80])
                p.wait_for_timeout(3000)
                o = p.evaluate(PROBE)
                o.update({"app": app, "scheme": scheme, "cls": round(p.evaluate("window.__cls"), 3), "longest": max(p.evaluate("window.__lt") or [0]),
                          "errors": [e for e in errs if "Failed to load resource" not in e][:4], "bad": sorted(set(bad))[:5]})
                if shots:
                    p.screenshot(path=os.path.join(shots, f"{tag}-{app}-{scheme}.jpg"), type="jpeg", quality=72)
                res.append(o)
                ctx.close()
        br.close()
    srv.shutdown()
    return res


def score(o):
    """the bar items this page misses (plain words)"""
    miss = []
    if not o["kit"]["agora"]:
        miss.append("no agora.css")
    if not o["kit"]["shell"]:
        miss.append("no shell.css")
    if o["scheme"] == "light" and sum(int(x) for x in __import__("re").findall(r"\d+", o["bg"])[:3]) / 3 < 140:
        miss.append("stays dark in light")
    if o["errors"]:
        miss.append(f"{len(o['errors'])} console errors")
    if o["bad"]:
        miss.append(f"{len(o['bad'])} failed requests")
    if o["cls"] >= 0.01:
        miss.append(f"layout shift {o['cls']}")
    if o["longest"] > 200:
        miss.append(f"long task {o['longest']} ms")
    if o["fcp"] and o["fcp"] > 1000:
        miss.append(f"first paint {o['fcp']} ms")
    if o["sideways"] > 0:
        miss.append(f"sideways {o['sideways']} px")
    if o["smallN"]:
        miss.append(f"{o['smallN']} taps < 44 px")
    if o["tiny"]:
        miss.append(f"{o['tiny']} texts < 12 px")
    if o["lowContrastN"]:
        miss.append(f"{o['lowContrastN']} low-contrast texts")
    return miss


def table(res):
    lines = ["| app | look | misses | detail |", "|---|---|---|---|"]
    for o in res:
        m = score(o)
        det = "; ".join(x for x in (", ".join(o["small"][:3]) and "taps: " + ", ".join(o["small"][:3]), ", ".join(o["lowContrast"][:2]) and "contrast: " + ", ".join(o["lowContrast"][:2]),
                                    "errors: " + " / ".join(o["errors"][:1]) if o["errors"] else "", "404: " + ", ".join(o["bad"][:2]) if o["bad"] else "") if x)
        lines.append(f"| {o['app']} | {o['scheme']} | {len(m)}: {', '.join(m) or 'clean'} | {det.replace('|', '/')[:220]} |")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", required=True)
    ap.add_argument("--apps")
    ap.add_argument("--json")
    ap.add_argument("--md")
    ap.add_argument("--shots")
    ap.add_argument("--tag", default="audit")
    a = ap.parse_args()
    apps = a.apps.split(",") if a.apps else list(APPS)
    res = run(a.site, apps, a.shots, a.tag)
    t = table(res)
    print(t)
    if a.json:
        json.dump(res, open(a.json, "w"), indent=1)
    if a.md:
        open(a.md, "w").write(t + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
