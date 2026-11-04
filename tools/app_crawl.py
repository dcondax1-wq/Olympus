"""Crawler for the OLYMPUS apps (tools/web_public/<app>/): loads each app in Chromium at phone sizes and writes a table of findings.

    python tools/app_crawl.py                                   # every app, 390x844 + 375x667 + 430x932, a local static server
    python tools/app_crawl.py --apps mind,tyche --viewports 390x844
    python tools/app_crawl.py --live                            # the real site (https://demetrades2000-coder.github.io/nq-dashboard/)
    python tools/app_crawl.py --offline                         # block every non-local request: the fixture / demo fallback must kick in
    python tools/app_crawl.py --reduced --intro                 # reduced motion; --intro plays the app intro (?intro=1) and checks it lets go
    python tools/app_crawl.py --out research/crawl --shots /tmp/shots   # table.md + table.json (+ a screenshot per run)

Per app and viewport it records: console errors, page errors, failed requests / HTTP 4xx-5xx, sideways overflow, tap targets under 44 px,
text clipped without an ellipsis, overlapping controls, blank or near-blank screens (a pixel check on the screenshot), WebGL context
loss, listener growth after a few interactions, the intro overlay (not blocking, gone), history spam, controls with no name for a
screen reader, text that does not contrast (solid backgrounds only), raw 'undefined' / 'NaN' / '[object' in the page, a "loading" that never
ends, jargon without an explanation (title / abbr), and empty lists. Read-only: it never writes to an app and sends nothing.
The apps that other work is rewriting are crawled like the rest: the table only reports.
"""
from __future__ import annotations

import argparse
import functools
import glob
import http.server
import io
import json
import os
import re
import sys
import tempfile
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "tools", "web_public")
LIVE = "https://demetrades2000-coder.github.io/nq-dashboard/"
SKIP_APPS = {"jarvis", "fx", "icon_options", "olympus"}          # jarvis has its own crawl; fx / icon_options / olympus are not apps
VIEWPORTS = ["390x844", "375x667", "430x932"]
JARGON = ["IFVG", "CISD", "FDR", "MAE", "MFE", "OOS", "p10", "f10", "dec10", "MLL", "inducement", "displacement", "sweep", "R-multiple", "PF", "EV", "slippage", "drawdown", "expectancy", "confluence", "liquidity"]

# ------------------------------------------------------------------ in-page probes
INIT = """(() => {
  window.__crawl = { lost: 0, restored: 0, ctx: 0, listeners: 0, adds: {}, removes: {}, hist: history.length };
  const ga = EventTarget.prototype.addEventListener, gr = EventTarget.prototype.removeEventListener;
  EventTarget.prototype.addEventListener = function (t, f, o) { if (this === window || this === document) { window.__crawl.listeners++; } return ga.call(this, t, f, o); };
  EventTarget.prototype.removeEventListener = function (t, f, o) { if (this === window || this === document) { window.__crawl.listeners--; } return gr.call(this, t, f, o); };
  const gc = HTMLCanvasElement.prototype.getContext;
  HTMLCanvasElement.prototype.getContext = function (t, ...a) {
    const c = gc.call(this, t, ...a);
    if (c && /webgl/i.test(String(t)) && !this.__cw) { this.__cw = 1; window.__crawl.ctx++; this.addEventListener('webglcontextlost', () => { window.__crawl.lost++; }); this.addEventListener('webglcontextrestored', () => { window.__crawl.restored++; }); }
    return c;
  };
})()"""

PROBE = r"""(jargon) => {
  const W = innerWidth, H = innerHeight;
  const vis = (e) => { const r = e.getBoundingClientRect(), s = getComputedStyle(e); return r.width > 0 && r.height > 0 && s.display !== 'none' && s.visibility !== 'hidden' && +s.opacity > 0.05 && r.bottom > 0 && r.right > 0 && r.top < H && r.left < W; };
  const label = (e) => (e.getAttribute('aria-label') || e.title || (e.textContent || '').trim().slice(0, 24) || e.id || e.className || e.tagName).toString().slice(0, 40);
  const key = (e) => e.tagName.toLowerCase() + (e.id ? '#' + e.id : '') + (typeof e.className === 'string' && e.className ? '.' + e.className.trim().split(/\s+/).slice(0, 2).join('.') : '');
  const sel = 'button, a[href], input:not([type=hidden]), select, textarea, summary, [role=button], [role=tab], [role=switch], [onclick], [tabindex]:not([tabindex="-1"])';
  const hit = (e) => { const r = e.getBoundingClientRect(), x = Math.min(W - 1, Math.max(0, r.left + r.width / 2)), y = Math.min(H - 1, Math.max(0, r.top + r.height / 2)), t = document.elementFromPoint(x, y); return !!t && (e === t || e.contains(t) || t.contains(e)); };
  const ctl = [...document.querySelectorAll(sel)].filter((e) => vis(e) && hit(e));       // on screen and not under something else
  const small = [], seen = new Set();
  for (const e of ctl) {
    const r = e.getBoundingClientRect();
    if (e.tagName === 'A' && e.closest('p, li, .note, .small') && r.height > 14) continue;      // an inline text link
    if (e.tagName === 'INPUT' && e.closest('label')) { const lr = e.closest('label').getBoundingClientRect(); if (lr.width >= 43.5 && lr.height >= 43.5) continue; }      // the whole label is the target
    if (r.width < 43.5 || r.height < 43.5) { const k = key(e) + Math.round(r.width) + 'x' + Math.round(r.height); if (!seen.has(k)) { seen.add(k); small.push(key(e) + ' ' + Math.round(r.width) + 'x' + Math.round(r.height) + ' "' + label(e).slice(0, 18) + '"'); } }
  }
  const clipped = [];
  for (const e of document.querySelectorAll('body *')) {
    if (clipped.length > 8) break;
    if (!e.childNodes.length || ![...e.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim().length > 2)) continue;
    const s = getComputedStyle(e);
    if (!vis(e)) continue;
    if (/^(SVG|CANVAS)$/i.test(e.tagName) || e.clientWidth <= 0 || s.textOverflow === 'ellipsis' || !/hidden|clip/.test(s.overflowX) || (e.className && /\b(vh|sr-only|visually-hidden)\b/.test(e.className))) continue;
    const rg = document.createRange(); rg.selectNodeContents(e);                        // the TEXT must run past the box (a shine pseudo-element widening scrollWidth is not clipping)
    const rr = rg.getBoundingClientRect(), er = e.getBoundingClientRect();
    if (rr.right > er.right + 2 || rr.left < er.left - 2) clipped.push(key(e) + ' "' + (e.textContent || '').trim().slice(0, 24) + '"');
  }
  const overlaps = [], boxes = ctl.filter((e) => /^(BUTTON|A|INPUT|SELECT)$/.test(e.tagName)).slice(0, 160).map((e) => [e, e.getBoundingClientRect()]);
  for (let i = 0; i < boxes.length && overlaps.length < 6; i++) for (let j = i + 1; j < boxes.length && overlaps.length < 6; j++) {
    const [a, A] = boxes[i], [b, B] = boxes[j];
    if (a.contains(b) || b.contains(a)) continue;
    const ox = Math.min(A.right, B.right) - Math.max(A.left, B.left), oy = Math.min(A.bottom, B.bottom) - Math.max(A.top, B.top);
    if (ox > 4 && oy > 4 && (ox * oy) / Math.min(A.width * A.height, B.width * B.height) > 0.3) overlaps.push(label(a) + ' x ' + label(b));
  }
  const off = [...document.querySelectorAll('body *')].filter((e) => { const s = getComputedStyle(e); return s.position === 'fixed' && vis(e); }).filter((e) => { const r = e.getBoundingClientRect(), s = getComputedStyle(e); if (s.pointerEvents === 'none' && !(e.textContent || '').trim()) return false; return r.right > W + 2 || r.left < -2; }).slice(0, 5).map(key);   // a decorative glow bigger than the screen is fine
  const cut = [];
  for (const e of document.querySelectorAll('body *')) {                       // text or a control running past the screen edge, inside nothing that scrolls sideways
    if (cut.length >= 6) break;
    if (/^(SVG|CANVAS|PATH|IMG|VIDEO|SCRIPT|STYLE)$/i.test(e.tagName) || e.closest('svg')) continue;
    if (!(/^(BUTTON|A|INPUT|SELECT)$/.test(e.tagName) || [...e.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim().length > 1)) || !vis(e)) continue;
    const r = e.getBoundingClientRect();
    if (!(r.right > W + 2 || r.left < -2)) continue;
    let sc = false;
    for (let n = e.parentElement; n; n = n.parentElement) { const st = getComputedStyle(n); if (/auto|scroll/.test(st.overflowX) || (st.overflowX === 'hidden' && n.getBoundingClientRect().right > W + 2 && n !== document.body && n !== document.documentElement)) { sc = true; break; } }
    if (!sc && getComputedStyle(e).position !== 'absolute') cut.push(key(e) + ' ' + Math.round(r.left) + '..' + Math.round(r.right) + ' "' + (e.textContent || '').trim().slice(0, 16) + '"');
  }
  const unnamed = ctl.filter((e) => { if (e.tagName === 'INPUT' && e.type === 'range') return false; const n = (e.getAttribute('aria-label') || e.getAttribute('aria-labelledby') || e.title || e.innerText || e.value || e.placeholder || (e.querySelector('img[alt]') || {}).alt || '').toString().trim(); return !n && !(e.id && document.querySelector('label[for="' + e.id + '"]')); }).slice(0, 8).map(key);
  const lum = (c) => { const m = c.match(/[\d.]+/g); if (!m) return null; const [r, g, b, a] = m.map(Number); if (m.length > 3 && a < 0.5) return null; const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
  const bgOf = (e) => { for (let n = e; n && n !== document.documentElement; n = n.parentElement) { const s = getComputedStyle(n); if (s.backgroundImage !== 'none') return null; const l = lum(s.backgroundColor); if (l !== null) return l; } return lum(getComputedStyle(document.body).backgroundColor) ?? 0; };
  const low = [];
  for (const e of document.querySelectorAll('body *')) {
    if (low.length >= 6) break;
    if (![...e.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim().length > 3) || !vis(e)) continue;
    const s = getComputedStyle(e), fg = lum(s.color), bg = bgOf(e);
    if (fg === null || bg === null) continue;
    const ratio = (Math.max(fg, bg) + 0.05) / (Math.min(fg, bg) + 0.05), px = parseFloat(s.fontSize);
    if (ratio < (px >= 18 || (px >= 14 && +s.fontWeight >= 700) ? 3 : 4.5)) low.push(key(e) + ' ' + ratio.toFixed(1) + ':1 "' + e.textContent.trim().slice(0, 20) + '"');
  }
  const text = (document.body.innerText || '');
  const bad = (text.match(/undefined|NaN|\[object|Infinity|null\b/g) || []).slice(0, 4);
  const loading = /^\s*(loading|building the|waking|please wait|connecting)/i.test(text.trim().slice(0, 40));          // the page's first words are still a loading message
  const jg = jargon.filter((w) => new RegExp('(^|[^A-Za-z])' + w + '([^A-Za-z]|$)').test(text) && !document.querySelector('abbr[title*="' + w + '" i], [title*="' + w + '" i]')).slice(0, 8);
  const emptyLists = [...document.querySelectorAll('ul, ol, table tbody, [role=list], .list')].filter((e) => vis(e) && !e.children.length && !(e.textContent || '').trim()).slice(0, 4).map(key);
  const imgs = [...document.querySelectorAll('img')].filter((i) => vis(i) && !i.hasAttribute('alt')).length;
  return { cut, overflow: document.scrollingElement.scrollWidth > W + 1 || document.body.scrollWidth > W + 1, sw: document.scrollingElement.scrollWidth, small, clipped, overlaps, off, unnamed, low, bad, loading, jargon: jg, emptyLists, imgs,
    textLen: text.trim().length, ctl: ctl.length, title: document.title, lang: document.documentElement.lang || '', hist: history.length };
}"""


def pixel_stats(png: bytes):
    """(share of the most common colour, colour spread) of a screenshot: blank screens are one flat colour."""
    from PIL import Image
    import numpy as np
    im = Image.open(io.BytesIO(png)).convert("RGB").resize((96, 208))
    a = np.asarray(im).reshape(-1, 3).astype(int)
    q = (a // 16)
    keys = q[:, 0] * 256 + q[:, 1] * 16 + q[:, 2]
    _, counts = np.unique(keys, return_counts=True)
    return float(counts.max() / len(keys)), float(a.std(axis=0).mean()), int(len(counts))


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def apps_on_disk():
    return sorted(d for d in os.listdir(WEB) if os.path.isfile(os.path.join(WEB, d, "index.html")) and d not in SKIP_APPS)


def _settle(row, base, args, local_host):
    """a 404 of a site-data file (data.json, home.json ...) on the local server is the app's offline path, not an error: listed apart"""
    row["data404"] = sorted({x for x in row["http"] if x.startswith("404")} | set(row.get("data404", [])))
    if base.startswith("http://127.") or args.offline:
        row["http"] = [x for x in row["http"] if not x.startswith("404")]
        row["errors"] = [e for e in row["errors"] if not ("Failed to load resource" in e and "404" in e)]
    if args.offline:
        row["errors"] = [e for e in row["errors"] if "Failed to load resource" not in e]       # the blocked outside requests are meant to fail
        row["failed"] = [u for u in row["failed"] if local_host in u]


def crawl_one(br, base, app, vp, args, shots):
    w, h = (int(x) for x in vp.split("x"))
    ctx = br.new_context(viewport={"width": w, "height": h}, device_scale_factor=1, has_touch=True, **({"reduced_motion": "reduce"} if args.reduced else {}))
    ctx.add_init_script(INIT)
    p = ctx.new_page()
    row = {"app": app, "vp": vp, "errors": [], "failed": [], "http": [], "notes": []}
    local_host = re.sub(r"^https?://", "", base).split("/")[0]
    p.on("pageerror", lambda e: row["errors"].append("pageerror: " + str(e)[:160]))
    p.on("console", lambda m: row["errors"].append("console: " + m.text[:160]) if m.type == "error" and "favicon" not in m.text else None)
    p.on("requestfailed", lambda r: row["failed"].append(r.url[:110]) if "favicon" not in r.url else None)
    p.on("response", lambda r: row["http"].append(f"{r.status} {r.url[:100]}") if r.status >= 400 and "favicon" not in r.url else None)
    if args.offline:
        p.route("**/*", lambda rt: rt.continue_() if local_host in rt.request.url or rt.request.url.startswith(("data:", "blob:")) else rt.abort())
    url = f"{base}{app}/?" + ("intro=1&" if args.intro else "") + (f"q={args.q}" if args.q else "")
    t0 = time.time()
    try:
        p.goto(url, timeout=90000)
    except Exception as e:                                                       # a slow page: record it and go on
        row["errors"].append("goto: " + str(e)[:120])
    time.sleep(args.wait)
    try:
        pr = p.evaluate(PROBE, JARGON)
    except Exception as e:
        row["errors"].append("probe: " + str(e)[:120])
        ctx.close()
        return row
    png = p.screenshot(timeout=120000)
    share, spread, ncol = pixel_stats(png)
    row.update(pr)
    _settle(row, base, args, local_host)
    row.update({"flat": round(share, 3), "spread": round(spread, 1), "colors": ncol, "blank": share > 0.985 or spread < 3.0 or pr["textLen"] < 3 and ncol < 12, "load_s": round(time.time() - t0, 1)})
    cr = p.evaluate("window.__crawl")
    row.update({"ctx": cr["ctx"], "lost": cr["lost"], "listeners": cr["listeners"]})
    # a few interactions: listener growth, the history stack
    try:
        l0 = cr["listeners"]
        p.evaluate("document.dispatchEvent(new Event('visibilitychange'))")
        btns = p.query_selector_all("button:visible")
        for b in btns[:6]:
            try:
                b.click(timeout=1500, no_wait_after=True)
                time.sleep(0.25)
                p.keyboard.press("Escape")
            except Exception:
                pass
        cr2 = p.evaluate("window.__crawl")
        row["listener_growth"] = cr2["listeners"] - l0
        row["hist_after"] = p.evaluate("history.length")          # clicks may legitimately add history (tabs, hashes): only the count at load is flagged
    except Exception as e:
        row["notes"].append("interact: " + str(e)[:80])
    if args.intro:
        try:
            st = p.evaluate("window.__olyAppIntro ? { s: window.__olyAppIntro.state, m: window.__olyAppIntro.mode, why: window.__olyAppIntro.why } : null")
            time.sleep(3.5)
            st2 = p.evaluate("window.__olyAppIntro ? window.__olyAppIntro.state : null")
            top = p.evaluate("(() => { const e = document.elementFromPoint(innerWidth / 2, innerHeight / 2); return e ? e.tagName + (e.id ? '#' + e.id : '') + '.' + (e.className || '') : ''; })()")
            row["intro"] = {"first": st, "after": st2, "top": str(top)[:60]}
            if st2 is not None and st2 not in ("done", "skipped", "off"):
                row["notes"].append(f"intro still {st2} after 6 s")
        except Exception as e:
            row["notes"].append("intro: " + str(e)[:80])
    if shots:
        os.makedirs(shots, exist_ok=True)
        p.screenshot(path=os.path.join(shots, f"{app}_{vp}.jpg"), type="jpeg", quality=70, timeout=120000)
    _settle(row, base, args, local_host)           # late console lines (after the probe) get the same treatment
    ctx.close()
    return row


def flags(r):
    """one-line verdict list of a row"""
    f = []
    if r["errors"]:
        f.append(f"{len(r['errors'])} errors")
    if r["failed"] or r["http"]:
        f.append(f"{len(r['failed']) + len(r['http'])} failed requests")
    if r.get("overflow"):
        f.append(f"sideways overflow ({r.get('sw')} px)")
    if r.get("small"):
        f.append(f"{len(r['small'])} taps < 44 px")
    if r.get("clipped"):
        f.append(f"{len(r['clipped'])} clipped texts")
    if r.get("overlaps"):
        f.append(f"{len(r['overlaps'])} overlapping controls")
    if r.get("off"):
        f.append("fixed element off screen")
    if r.get("cut"):
        f.append(f"{len(r['cut'])} texts / controls cut off at the screen edge")
    if r.get("blank"):
        f.append("BLANK screen")
    if r.get("lost"):
        f.append("WebGL context lost")
    if r.get("listener_growth", 0) > 40:
        f.append(f"listeners +{r['listener_growth']}")
    if r.get("unnamed"):
        f.append(f"{len(r['unnamed'])} controls without a name")
    if r.get("low"):
        f.append(f"{len(r['low'])} low-contrast texts")
    if r.get("bad"):
        f.append("raw " + "/".join(sorted(set(r["bad"]))))
    if r.get("loading"):
        f.append("stuck 'loading'")
    if r.get("jargon"):
        f.append(f"jargon: {', '.join(r['jargon'][:4])}")
    if r.get("emptyLists"):
        f.append("empty list")
    if r.get("hist", 0) > 3:
        f.append(f"history {r['hist']}")
    if r.get("data404"):
        f.append(f"{len(r['data404'])} site-data 404 (offline path)")
    f += r.get("notes", [])
    return f


def table(rows):
    out = ["| app | viewport | findings |", "|---|---|---|"]
    for r in rows:
        out.append(f"| {r['app']} | {r['vp']} | {'; '.join(flags(r)) or 'clean'} |")
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apps", help="comma list (default: every app folder with an index.html except jarvis)")
    ap.add_argument("--viewports", default=",".join(VIEWPORTS))
    ap.add_argument("--live", action="store_true", help="crawl the real site instead of the local static server")
    ap.add_argument("--base", help="a base URL ending in / (overrides --live and the local server)")
    ap.add_argument("--offline", action="store_true", help="block every request that is not the base host")
    ap.add_argument("--reduced", action="store_true", help="prefers-reduced-motion")
    ap.add_argument("--intro", action="store_true", help="play the app intro (?intro=1) and check it lets go")
    ap.add_argument("--q", default="low", help="render tier forced with ?q= (default low: software GL; '' to leave it alone)")
    ap.add_argument("--wait", type=float, default=6.0, help="seconds to let each app settle")
    ap.add_argument("--out", help="folder for table.md and table.json")
    ap.add_argument("--shots", help="folder for one JPEG per run")
    args = ap.parse_args(argv)
    from playwright.sync_api import sync_playwright

    apps = args.apps.split(",") if args.apps else apps_on_disk()
    srv = None
    base = args.base
    if not base and args.live:
        base = LIVE
    if not base:
        srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=WEB))
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{srv.server_port}/"
    rows = []
    try:
        with sync_playwright() as pw:
            exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
            proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")          # the live site goes through the session's egress proxy (TLS stays on)
            kw = {"proxy": {"server": proxy}} if proxy and base.startswith("https://") else {}
            br = pw.chromium.launch(**({"executable_path": exe} if exe else {}), args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"], **kw)
            for app in apps:
                for vp in args.viewports.split(","):
                    r = crawl_one(br, base, app, vp, args, args.shots)
                    rows.append(r)
                    print(f"{app:11s} {vp:8s} {'; '.join(flags(r)) or 'clean'}", flush=True)
            br.close()
    finally:
        if srv:
            srv.shutdown()
    md = table(rows)
    if args.out:
        os.makedirs(args.out, exist_ok=True)
        with open(os.path.join(args.out, "table.md"), "w", encoding="utf-8") as fh:
            fh.write(f"# App crawl {time.strftime('%Y-%m-%d %H:%M')} ({base}{' offline' if args.offline else ''}{' reduced-motion' if args.reduced else ''})\n\n{md}\n")
        with open(os.path.join(args.out, "table.json"), "w", encoding="utf-8") as fh:
            json.dump(rows, fh, indent=1, default=str)
    print("\n" + md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
