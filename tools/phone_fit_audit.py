#!/usr/bin/env python3
"""Phone-fit audit for the OLYMPUS apps (2026-11-10). Read only: it serves tools/web_public on a free local port, opens each app in Chromium (ONE browser, one page at a time)
at 390 x 844 and 375 x 667 with ?demo=1&q=low and checks what a phone user would hit:

  scroll    no horizontal scroll (page scrollWidth <= viewport)
  wide      nothing wider than the viewport (an element sticking out that is not inside its own horizontal scroller)
  clip      no clipped text (overflow hidden / ellipsis boxes whose text is cut)
  tap       every button / link / field / summary / [role=button] is at least 44 x 44 px
  console   no console errors, no failed requests, no off-origin requests (a missing optional *.json is a WARN: the app falls back to its fixture)
  fixed     no heading hidden under a fixed / sticky bar at the top
  contrast  body text at least 4.5:1 (3:1 for large text) against its real background (muted tokens included)

    python tools/phone_fit_audit.py                       all apps, both sizes, table, screenshots in <tmp>/phone_fit
    python tools/phone_fit_audit.py --apps nike,argo --out shots --timeout 90 --json report.json
Exit code 1 when any check FAILs (WARN does not fail). Per-app timeout (default 90 s) turns a stuck app into a FAIL ("timeout") and moves on.
"""
from __future__ import annotations

import argparse
import functools
import glob
import http.server
import json
import os
import sys
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "tools", "web_public")
APPS = ["delphi", "pnyx", "planner", "mint", "mercury", "chrysos", "sibyl", "oikos", "arbiter", "stoa", "aegis", "lyceum", "nike", "kronos", "moirai", "epilogue", "argo", "kairos", "kratos", "pythia", "mintcity", "gallery"]
SIZES = [(390, 844), (375, 667)]
CHECKS = ["scroll", "wide", "clip", "tap", "console", "fixed", "contrast"]

JS = r"""
() => {
  const W = innerWidth, out = { scroll: [], wide: [], clip: [], tap: [], fixed: [], contrast: [], minContrast: 21 };
  const name = (e) => (e.id ? '#' + e.id : '') + (typeof e.className === 'string' && e.className.trim() ? '.' + e.className.trim().split(/\s+/).slice(0, 2).join('.') : '') || e.tagName.toLowerCase();
  const label = (e) => e.tagName.toLowerCase() + name(e).replace(/^[a-z0-9]+(?=[#.])/i, '');
  const kit = (e) => { for (let n = e; n && n.nodeType === 1 && n !== document.body && n !== document.documentElement; n = n.parentElement) { const s = (n.id || '') + ' ' + (typeof n.className === 'string' ? n.className : ''); if (/(^|[\s_-])(oly|jarvis|ag-skip|skip)/i.test(s) || n.hasAttribute('data-oly')) return true; } return false; };
  const vis = (e) => { const cs = getComputedStyle(e); if (cs.display === 'none' || cs.visibility === 'hidden' || parseFloat(cs.opacity) === 0) return false; const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  const scrollerOf = (e) => { for (let n = e.parentElement; n && n !== document.body; n = n.parentElement) { const o = getComputedStyle(n).overflowX; if (o === 'auto' || o === 'scroll' || o === 'hidden' || o === 'clip') return n; } return null; };
  if (document.documentElement.scrollWidth > W + 1) out.scroll.push(`scrollWidth ${document.documentElement.scrollWidth} > ${W}`);
  if (document.body.scrollWidth > W + 1) out.scroll.push(`body scrollWidth ${document.body.scrollWidth} > ${W}`);
  const all = [...document.querySelectorAll('body *')];
  for (const e of all) {
    if (e.closest('svg') && e.tagName.toLowerCase() !== 'svg') continue;
    if (kit(e) || !vis(e)) continue;
    const r = e.getBoundingClientRect(), cs = getComputedStyle(e);
    if (cs.position === 'fixed' && (r.right < 0 || r.left > W)) continue;
    if ((r.right > W + 1.5 || r.left < -1.5) && !scrollerOf(e) && cs.position !== 'fixed' && !(r.width <= 2 || r.height <= 2)) out.wide.push(`${label(e)} ${Math.round(r.left)}..${Math.round(r.right)}`);
    if ((cs.overflowX === 'hidden' || cs.overflowX === 'clip' || cs.textOverflow === 'ellipsis') && e.scrollWidth > e.clientWidth + 1 && e.clientWidth > 0 && e.tagName !== 'CANVAS' && e.tagName.toLowerCase() !== 'svg' && /\S/.test(e.textContent || '') && !e.querySelector('canvas,svg')) {
      const own = [...e.childNodes].some((n) => n.nodeType === 3 && /\S/.test(n.textContent)) || e.children.length === 0;
      if (own) out.clip.push(`${label(e)} ${e.scrollWidth}>${e.clientWidth}`);
    }
    if (cs.overflowY === 'hidden' && cs.textOverflow !== 'ellipsis' && e.scrollHeight > e.clientHeight + 2 && e.clientHeight > 0 && /\S/.test(e.textContent || '') && !e.querySelector('canvas,svg') && e.tagName.toLowerCase() !== 'body' && e.tagName.toLowerCase() !== 'html' && cs.display !== 'inline' && !(e.clientHeight > innerHeight * 0.6)) {
      const own = [...e.childNodes].some((n) => n.nodeType === 3 && /\S/.test(n.textContent));
      if (own) out.clip.push(`${label(e)} h ${e.scrollHeight}>${e.clientHeight}`);
    }
  }
  const TAP = 'button, input:not([type=hidden]):not([type=file]), select, textarea, summary, a[href], [role=button], [role=tab], [role=link], [role=menuitem], [role=switch]';
  for (const e of document.querySelectorAll(TAP)) {
    if (kit(e) || !vis(e) || e.disabled) continue;
    const r = e.getBoundingClientRect(); if (r.right < 0 || r.bottom < 0 || r.left > W) continue;
    if (e.tagName === 'INPUT' && /^(checkbox|radio)$/.test(e.type)) { const l = e.closest('label') || (e.id && document.querySelector(`label[for="${e.id}"]`)); const lr = l ? l.getBoundingClientRect() : r; if (lr.height >= 43.5 && lr.width >= 43.5) continue; }
    if (e.tagName === 'A' && getComputedStyle(e).display === 'inline' && e.closest('p, li, dd, .foot, .note') && e.getClientRects().length) { const rr = e.getBoundingClientRect(); if (rr.height < 43.5 && e.closest('p, .foot, .note')) { /* an inline link inside a sentence: WCAG exempts inline text links */ continue; } }
    if (r.height < 43.5 || r.width < 43.5) out.tap.push(`${label(e)} ${Math.round(r.width)}x${Math.round(r.height)}`);
  }
  scrollTo(0, 0);
  const bars = all.filter((e) => { if (!vis(e)) return false; const cs = getComputedStyle(e), r = e.getBoundingClientRect(); return (cs.position === 'fixed' || cs.position === 'sticky') && r.top <= 12 && r.height <= 140 && r.width >= W * 0.6 && !e.closest('svg'); });
  for (const b of bars) {
    const br = b.getBoundingClientRect();
    for (const hd of document.querySelectorAll('h1, h2, h3')) { if (!vis(hd) || b.contains(hd) || kit(hd)) continue; const r = hd.getBoundingClientRect(); if (r.top < br.bottom - 1 && r.bottom > br.top + 1 && r.top > -2) out.fixed.push(`${label(hd)} under ${label(b)}`); }
  }
  const parse = (s) => { const m = /rgba?\(([^)]+)\)/.exec(s); if (!m) return null; const p = m[1].split(/[ ,\/]+/).filter(Boolean).map(parseFloat); return { r: p[0], g: p[1], b: p[2], a: p.length > 3 && Number.isFinite(p[3]) ? p[3] : 1 }; };
  const mix = (top, bot) => ({ r: top.r * top.a + bot.r * (1 - top.a), g: top.g * top.a + bot.g * (1 - top.a), b: top.b * top.a + bot.b * (1 - top.a), a: 1 });
  const lum = (c) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b); };
  const bgOf = (e) => {
    const layers = [];
    for (let n = e; n && n.nodeType === 1; n = n.parentElement) {
      const cs = getComputedStyle(n), c = parse(cs.backgroundColor);
      if (cs.backgroundImage && cs.backgroundImage !== 'none') { const g = /rgba?\([^)]+\)/.exec(cs.backgroundImage); if (g) { const gc = parse(g[0]); if (gc) { layers.push(gc); if (gc.a >= 1) break; } } else return null; }
      if (c && c.a > 0) { layers.push(c); if (c.a >= 1) break; }
    }
    let base = { r: 20, g: 17, b: 14, a: 1 }; for (let i = layers.length - 1; i >= 0; i--) base = mix(layers[i], base); return base;
  };
  const seen = new Set(), walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let t; (t = walker.nextNode());) {
    const txt = t.textContent.trim(); if (!txt) continue;
    const e = t.parentElement; if (!e || seen.has(e) || kit(e) || !vis(e) || e.closest('svg, canvas, script, style, noscript, [aria-hidden=true], [hidden]') || e.closest(':disabled')) continue;
    seen.add(e);
    const cs = getComputedStyle(e); let op = 1; for (let n = e; n && n.nodeType === 1; n = n.parentElement) op *= parseFloat(getComputedStyle(n).opacity);
    const fg0 = parse(cs.color); if (!fg0) continue;
    const bg = bgOf(e); if (!bg) continue;
    const fg = mix({ ...fg0, a: fg0.a * op }, bg), a = lum(fg), b = lum(bg), ratio = (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
    const px = parseFloat(cs.fontSize), large = px >= 24 || (px >= 18.66 && parseInt(cs.fontWeight, 10) >= 700), need = large ? 3 : 4.5;
    out.minContrast = Math.min(out.minContrast, ratio);
    if (ratio < need) out.contrast.push(`${label(e)} ${ratio.toFixed(2)}:1 "${txt.slice(0, 22)}"`);
  }
  return out;
}
"""


def serve():
    class H(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def end_headers(self):
            self.send_header("Cache-Control", "no-store")
            super().end_headers()
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(H, directory=WEB))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


def launch(pw):
    try:
        sys.path.insert(0, os.path.join(ROOT, "tests"))
        import browser_kit as BK
        return BK.launch(pw)
    except Exception:
        exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
        return pw.chromium.launch(args=["--no-sandbox", "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"], **({"executable_path": exe} if exe else {}))


def audit_one(br, origin, app, w, h, timeout, shots, q="low"):
    """-> {check: [issues]} plus 'status' of each check: PASS / WARN / FAIL"""
    t0 = time.time()
    ctx = br.new_context(viewport={"width": w, "height": h}, device_scale_factor=1, is_mobile=True, has_touch=True, reduced_motion="reduce")
    ctx.add_init_script("try { localStorage.setItem('jfx', 'low'); } catch (e) {}")
    bad_req, soft, off, errs = [], [], [], []

    def route(r):
        u = r.request.url
        if not u.startswith(origin):
            off.append(u[:80])
            r.abort()
        else:
            r.continue_()
    ctx.route("**/*", route)
    p = ctx.new_page()
    p.set_default_timeout(timeout * 1000)
    p.on("pageerror", lambda e: errs.append("pageerror: " + str(e)[:140]))
    p.on("console", lambda m: errs.append("console: " + m.text[:140]) if m.type == "error" and "Failed to load resource" not in m.text and "net::ERR" not in m.text else None)
    p.on("requestfailed", lambda r: None if r.url.startswith("http") and not r.url.startswith(origin) else bad_req.append(r.url[-60:] + " " + str(r.failure)[:30]))

    def resp(r):
        if r.status >= 400 and r.url.startswith(origin):
            (soft if r.url.split("?")[0].endswith(".json") else bad_req).append(f"{r.status} {r.url[len(origin):][:60]}")
    p.on("response", resp)
    res = {k: [] for k in CHECKS}
    res["minContrast"] = None
    try:
        p.goto(f"{origin}/{app}/?demo=1&q={q}", wait_until="load", timeout=timeout * 1000)
        hook = app.upper()
        try:
            p.wait_for_function(f"!window.{hook} || !window.{hook}.ready || window.{hook}.ready()", timeout=min(timeout, 40) * 1000, polling=300)
        except Exception:
            res["console"].append("page never reported ready")
        p.wait_for_timeout(900)
        p.evaluate("document.getAnimations().forEach((a) => { try { a.finish(); } catch (e) {} })")
        if time.time() - t0 > timeout:
            raise TimeoutError("timeout")
        r = p.evaluate(JS)
        for k in ("scroll", "wide", "clip", "tap", "fixed", "contrast"):
            res[k] = r[k]
        res["minContrast"] = r["minContrast"]
        os.makedirs(shots, exist_ok=True)
        p.screenshot(path=os.path.join(shots, f"{app}-{w}x{h}.png"), full_page=True)
    except Exception as e:  # noqa: BLE001
        res["console"].append(f"{'timeout' if 'imeout' in type(e).__name__ or 'imeout' in str(e) else type(e).__name__}: {str(e)[:100]}")
    res["console"] += errs + bad_req
    res["warn"] = [f"missing optional file {s}" for s in soft] + [f"off-origin request blocked: {u}" for u in off]
    ctx.close()
    res["secs"] = round(time.time() - t0, 1)
    return res


def run(apps, sizes, timeout, shots, q="low"):
    from playwright.sync_api import sync_playwright
    srv, origin = serve()
    rows = []
    try:
        with sync_playwright() as pw:
            br = launch(pw)
            for app in apps:
                if not os.path.isfile(os.path.join(WEB, app, "index.html")):
                    rows.append({"app": app, "size": "-", "skipped": True})
                    continue
                for w, h in sizes:
                    rows.append({"app": app, "size": f"{w}x{h}", **audit_one(br, origin, app, w, h, timeout, shots, q)})
    finally:
        srv.shutdown()
    return rows


def table(rows):
    lines = [f"{'app':10} {'size':8} " + " ".join(f"{c:8}" for c in CHECKS) + "  notes"]
    nfail = 0
    for r in rows:
        if r.get("skipped"):
            lines.append(f"{r['app']:10} {'-':8} not present in this tree (skipped)")
            continue
        cells, notes = [], []
        for c in CHECKS:
            bad = r.get(c) or []
            cells.append(f"{'FAIL' if bad else 'ok':8}")
            if bad:
                nfail += 1
                notes.append(f"{c}: {bad[0]}" + (f" (+{len(bad) - 1})" if len(bad) > 1 else ""))
        if r.get("warn"):
            notes.append(f"warn: {r['warn'][0]}" + (f" (+{len(r['warn']) - 1})" if len(r["warn"]) > 1 else ""))
        lines.append(f"{r['app']:10} {r['size']:8} " + " ".join(cells) + "  " + "; ".join(notes))
    lines.append(f"\n{nfail} failing checks over {sum(1 for r in rows if not r.get('skipped'))} app views")
    return "\n".join(lines), nfail


def main(argv=None):
    ap = argparse.ArgumentParser(description="phone-fit audit of the OLYMPUS apps")
    ap.add_argument("--apps", help="comma list (default: every app tonight)")
    ap.add_argument("--out", default=os.path.join(tempfile.gettempdir(), "phone_fit"), help="screenshot folder")
    ap.add_argument("--timeout", type=int, default=90, help="seconds per app view")
    ap.add_argument("--q", default="low", help="the ?q= quality (default low)")
    ap.add_argument("--json", help="write the raw report here")
    ap.add_argument("--small-only", action="store_true", help="only 375 x 667")
    a = ap.parse_args(argv)
    try:
        import playwright  # noqa: F401
    except ImportError:
        print("Playwright is not installed: cannot audit.")
        return 2
    apps = [x.strip() for x in a.apps.split(",")] if a.apps else APPS
    rows = run(apps, SIZES[1:] if a.small_only else SIZES, a.timeout, a.out, a.q)
    txt, nfail = table(rows)
    print(txt)
    print(f"screenshots: {a.out}")
    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump(rows, fh, indent=1)
    return 1 if nfail else 0


if __name__ == "__main__":
    sys.exit(main())
