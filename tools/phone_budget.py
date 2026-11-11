#!/usr/bin/env python3
"""Phone budget: what each page of a BUILT site costs a mid-range iPhone on a slow line (QA Round 6, "real-phone budget pass").

    flock -w 2400 /tmp/olympus_browser.lock python tools/phone_budget.py <site folder> [--pages root,jarvis,polis] [--json out.json]
        [--cpu 4] [--net fast3g|none] [--extra <file.html> ...]

<site folder> is the output of tools/build_web_dashboard.py. The tool serves it read only on a free local port, opens each page at
390 x 844 (touch, device pixel ratio 2) with the CPU slowed down x4 and the DevTools "Fast 3G" line (562.5 ms round trip,
~1.44 Mbit/s down), service workers blocked (a first visit), and records per page:
  fcp_ms        first contentful paint (the browser's own paint timing)
  kb_fcp        bytes over the wire before that paint (the page + every response that ended before it)
  req_fcp       requests that ended before the paint
  req / kb      every request and byte within 6 s after the load event (what a first visit really pulls)
  js_kb         JavaScript the browser had to parse (decoded size of every .js / .mjs response)
  three         three.js (jarvis/three.module.min.js) was loaded
  gl            WebGL contexts the page created
Nothing is written into the site folder. ONE browser on the machine: always run it under the flock lock.

The arithmetic is in plain functions (summarize, over_budget, table_lines) so tests/test_phone_budget.py checks it without a browser.
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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H = 390, 844
QUERY = "?welcome=0&intro=0"
# the 20 most used pages (QA Round 6); 'root' = the site's index.html
PAGES = ["root", "jarvis", "polis", "symposium", "ergasterion", "cities", "nq", "kalshi", "helios", "aegis", "mint", "planner",
         "herald", "pinakes", "colosseum", "pythia", "nike", "chrysos", "sibyl", "olympus-live.html"]
# DevTools "Fast 3G" (Lighthouse's throttling numbers): 150 ms RTT x 3.75, 1.6 Mbit/s x 0.9 down, 750 kbit/s x 0.9 up
NET = {"fast3g": {"offline": False, "latency": 562.5, "downloadThroughput": 1.6e6 * 0.9 / 8, "uploadThroughput": 750e3 * 0.9 / 8}}
SETTLE_MS = 6000
# budgets per page on that line (a mid iPhone is ~4x faster than this throttled CPU on parse; the bar is "first paint < 2 s on a mid iPhone")
BUDGET = {"fcp_ms": 6000, "kb_fcp": 450, "req_fcp": 30, "js_kb": 1600, "gl": 1}
THREE = "three.module.min.js"

INIT = r"""
(() => {
  try { performance.setResourceTimingBufferSize(5000); } catch (e) {}
  window.__pb = { gl: 0, lost: 0, fcp: 0, lcp: 0, ready: 0, cvs: [] };
  const mark = () => { if (!window.__pb.ready && document.documentElement.getAttribute('data-oly-state') === 'ready') window.__pb.ready = performance.now(); };
  try { new MutationObserver(mark).observe(document.documentElement, { attributes: true, attributeFilter: ['data-oly-state'] }); } catch (e) {}
  const g = HTMLCanvasElement.prototype.getContext;
  HTMLCanvasElement.prototype.getContext = function (kind, ...rest) {
    const had = this.__pbgl;
    const c = g.call(this, kind, ...rest);
    if (c && /webgl/.test(String(kind)) && !had) { this.__pbgl = true; window.__pb.gl++; window.__pb.cvs.push(this); this.addEventListener('webglcontextlost', () => window.__pb.lost++); }
    return c;
  };
  try { new PerformanceObserver((l) => { for (const e of l.getEntries()) if (e.name === 'first-contentful-paint') window.__pb.fcp = e.startTime; })
    .observe({ type: 'paint', buffered: true }); } catch (e) {}
  try { new PerformanceObserver((l) => { for (const e of l.getEntries()) window.__pb.lcp = e.startTime; }).observe({ type: 'largest-contentful-paint', buffered: true }); } catch (e) {}
})();
"""

COLLECT = r"""
(() => {
  const nav = performance.getEntriesByType('navigation')[0] || {};
  const res = performance.getEntriesByType('resource').map((r) => ({ n: r.name, t: r.transferSize || 0, d: r.decodedBodySize || 0, e: r.responseEnd, i: r.initiatorType }));
  const paint = performance.getEntriesByType('paint').find((p) => p.name === 'first-contentful-paint');
  return { fcp: paint ? paint.startTime : (window.__pb && window.__pb.fcp) || 0, nav: { t: nav.transferSize || 0, d: nav.decodedBodySize || 0, e: nav.responseEnd || 0 },
    res, gl: window.__pb ? window.__pb.gl : 0, gl_page: window.__pb ? window.__pb.cvs.filter((c) => c.isConnected).length : 0,
    lcp: window.__pb ? window.__pb.lcp : 0, ready: window.__pb ? window.__pb.ready : 0, state: document.documentElement.getAttribute('data-oly-state') || '', heap: performance.memory ? performance.memory.usedJSHeapSize : 0 };
})()
"""


# ------------------------------------------------------------------------------------------------ pure arithmetic (unit-tested)
def is_js(url):
    p = url.split("?")[0].split("#")[0].lower()
    return p.endswith(".js") or p.endswith(".mjs")


def summarize(raw):
    """raw = COLLECT's result -> the page's row (numbers rounded for the table)."""
    fcp = float(raw.get("fcp") or 0)
    nav = raw.get("nav") or {}
    res = raw.get("res") or []
    before = [r for r in res if fcp and r.get("e", 0) <= fcp]
    kb = lambda xs: sum(int(x.get("t") or 0) for x in xs) / 1024.0
    return {
        "fcp_ms": int(round(fcp)),
        "kb_fcp": round((int(nav.get("t") or 0) / 1024.0) + kb(before), 1),
        "req_fcp": 1 + len(before),
        "req": 1 + len(res),
        "kb": round((int(nav.get("t") or 0) / 1024.0) + kb(res), 1),
        "js_kb": round(sum(int(r.get("d") or 0) for r in res if is_js(r.get("n", ""))) / 1024.0, 1),
        "three": any(THREE in r.get("n", "") for r in res),
        "gl": int(raw.get("gl") or 0),
        "gl_page": int(raw.get("gl_page") or 0),
        "lcp_ms": int(round(float(raw.get("lcp") or 0))),
        "ready_ms": int(round(float(raw.get("ready") or 0))),
        "heap_mb": round(int(raw.get("heap") or 0) / 1048576.0, 1),
    }


def over_budget(row, budget=None):
    """the budget lines a row breaks (empty = within budget)"""
    b = dict(BUDGET, **(budget or {}))
    out = []
    for k in ("fcp_ms", "kb_fcp", "req_fcp", "js_kb", "gl"):
        if k in row and row[k] is not None and row[k] > b[k]:
            out.append("%s %s > %s" % (k, row[k], b[k]))
    if not row.get("fcp_ms"):
        out.append("no first paint")
    return out


def table_lines(rows):
    head = "| page | first paint ms | KB before paint | req before paint | req total | KB total | JS parsed KB | three.js | WebGL contexts |"
    out = [head, "|" + "---|" * 9]
    for name, r in rows:
        if "error" in r:
            out.append("| %s | error: %s | | | | | | | |" % (name, r["error"][:60]))
            continue
        out.append("| %s | %d | %.0f | %d | %d | %.0f | %.0f | %s | %d |" % (name, r["fcp_ms"], r["kb_fcp"], r["req_fcp"], r["req"], r["kb"],
                                                                      r["js_kb"], "yes" if r["three"] else "no", r["gl"]))
    return out


# ------------------------------------------------------------------------------------------------ static: what a page loads eagerly (no browser)
_TAG = re.compile(r"<(script|link)\b([^>]*)>", re.I)
_ATTR = re.compile(r"""([a-zA-Z_:-]+)\s*(?:=\s*("[^"]*"|'[^']*'|[^\s>]+))?""")
_IMPORT = re.compile(r"""(?:^|[;\s}])(?:import\s*(?:[\w*{}\s,$]+?\s*from\s*)?|export\s*(?:\*|\{[^}]*\})\s*from\s*)["']([^"']+\.m?js)(?:\?[^"']*)?["']""", re.M)


def _attrs(s):
    out = {}
    for k, v in _ATTR.findall(s):
        out[k.lower()] = v.strip("'\"") if v else ""
    return out


def _local(base_dir, site, ref):
    ref = ref.split("#")[0].split("?")[0]
    if not ref or re.match(r"^[a-z]+:", ref, re.I) or ref.startswith("//"):
        return None
    p = os.path.normpath(os.path.join(site, ref.lstrip("/")) if ref.startswith("/") else os.path.join(base_dir, ref))
    return p if p.startswith(os.path.abspath(site)) and os.path.isfile(p) else None


def module_graph(path, site, seen=None):
    """every file a module pulls in through static imports (dynamic import() is lazy and not followed)"""
    seen = set() if seen is None else seen
    if path in seen:
        return seen
    seen.add(path)
    try:
        src = open(path, encoding="utf-8", errors="replace").read()
    except OSError:
        return seen
    if len(src) > 400_000 and src.count("\n") < 50:   # a minified bundle: its own imports are inlined
        return seen
    for ref in _IMPORT.findall(src):
        p = _local(os.path.dirname(path), site, ref)
        if p:
            module_graph(p, site, seen)
    return seen


def eager_files(site, html_path):
    """-> {'blocking': [files that hold the first paint], 'eager': [every file loaded without a user action]} (absolute paths).
    Blocking = stylesheets + classic scripts without defer / async in the document. Eager = blocking + deferred / async / module scripts
    and their static imports + modulepreloads."""
    site = os.path.abspath(site)
    html = open(html_path, encoding="utf-8", errors="replace").read()
    html = re.sub(r"<!--.*?-->", "", html, flags=re.S)
    d = os.path.dirname(os.path.abspath(html_path))
    blocking, eager = [], set()
    for tag, rest in _TAG.findall(html):
        a = _attrs(rest)
        if tag.lower() == "link":
            rel = a.get("rel", "").lower()
            if "stylesheet" in rel or rel == "modulepreload":
                p = _local(d, site, a.get("href", ""))
                if p:
                    if "stylesheet" in rel and "media" not in a:
                        blocking.append(p)
                    eager.update(module_graph(p, site) if rel == "modulepreload" else {p})
            continue
        src = a.get("src")
        if not src:
            continue
        p = _local(d, site, src)
        if not p:
            continue
        if a.get("type") == "module":
            eager.update(module_graph(p, site))
        else:
            eager.add(p)
            if "defer" not in a and "async" not in a:
                blocking.append(p)
    eager.update(blocking)
    return {"blocking": sorted(set(blocking)), "eager": sorted(eager)}


def static_row(site, name):
    """the eager cost of one page from the files alone: KB that block the first paint, eager JS KB, three.js eager or not"""
    if name in ("root", "/", ""):
        html = os.path.join(site, "index.html")
    elif name.endswith(".html"):
        html = os.path.join(site, name)
    else:
        html = os.path.join(site, name.strip("/"), "index.html")
    if not os.path.isfile(html):
        return {"error": "missing"}
    f = eager_files(site, html)
    size = lambda xs: sum(os.path.getsize(x) for x in xs) / 1024.0
    js = [x for x in f["eager"] if is_js(x)]
    return {"html_kb": round(os.path.getsize(html) / 1024.0, 1), "block_kb": round(size(f["blocking"]) + os.path.getsize(html) / 1024.0, 1),
            "block_n": len(f["blocking"]) + 1, "eager_js_kb": round(size(js), 1), "eager_n": len(f["eager"]) + 1,
            "three": any(x.endswith(THREE) for x in f["eager"]), "files": [os.path.relpath(x, site) for x in f["eager"]]}


def page_url(base, name):
    if name in ("root", "/", ""):
        return base + "/" + QUERY
    if name.endswith(".html"):
        return base + "/" + name + QUERY
    return base + "/" + name.strip("/") + "/" + QUERY


# ------------------------------------------------------------------------------------------------ the browser run
_GZ = {}
_GZIP_EXT = (".html", ".htm", ".js", ".mjs", ".css", ".json", ".svg", ".txt", ".md", ".webmanifest")


class _Quiet(http.server.SimpleHTTPRequestHandler):
    """read only; text files gzip-encoded like GitHub Pages serves them (so 'bytes over the wire' match the real host)"""
    def log_message(self, *a):
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self):
        import gzip
        path = self.translate_path(self.path)
        if os.path.isdir(path):
            path = os.path.join(path, "index.html")
        if "gzip" in (self.headers.get("Accept-Encoding") or "") and os.path.isfile(path) and path.lower().endswith(_GZIP_EXT):
            if not self.path.split("?")[0].endswith("/") and os.path.isdir(self.translate_path(self.path)):
                return super().do_GET()       # the folder redirect
            key = (path, os.path.getmtime(path))
            if key not in _GZ:
                with open(path, "rb") as fh:
                    _GZ[key] = gzip.compress(fh.read(), 6)
            body = _GZ[key]
            self.send_response(200)
            self.send_header("Content-Type", self.guess_type(path))
            self.send_header("Content-Encoding", "gzip")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        return super().do_GET()


def serve(folder):
    h = functools.partial(_Quiet, directory=folder)
    class _Srv(http.server.ThreadingHTTPServer):
        daemon_threads = True

        def handle_error(self, request, client_address):   # a page closed mid-transfer (the next page started): not an error
            pass
    srv = _Srv(("127.0.0.1", 0), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, "http://127.0.0.1:%d" % srv.server_address[1]


def launch(pw):
    import glob
    exe = sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))
    return pw.chromium.launch(args=["--no-sandbox", "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
                                    "--enable-precise-memory-info", "--js-flags=--expose-gc"],
                              **({"executable_path": exe[-1]} if exe else {}))


LOWEND = "Object.defineProperty(Navigator.prototype, 'deviceMemory', { get: () => 2, configurable: true });"


def measure(br, url, cpu=4, net="fast3g", timeout_s=90, lowend=False):
    ctx = br.new_context(viewport={"width": W, "height": H}, device_scale_factor=2, is_mobile=True, has_touch=True,
                         service_workers="block")
    ctx.add_init_script(INIT)
    if lowend:      # a 2 GB device: the kit's LITE auto-detection starts it on low
        ctx.add_init_script(LOWEND)
    pg = ctx.new_page()
    try:
        cdp = ctx.new_cdp_session(pg)
        cdp.send("Network.enable")
        cdp.send("Network.setCacheDisabled", {"cacheDisabled": True})
        if cpu and cpu > 1:
            cdp.send("Emulation.setCPUThrottlingRate", {"rate": cpu})
        if net in NET:
            cdp.send("Network.emulateNetworkConditions", NET[net])
        pg.goto(url, wait_until="load", timeout=timeout_s * 1000)
        pg.wait_for_timeout(SETTLE_MS)
        raw = pg.evaluate(COLLECT)
        return summarize(raw)
    except Exception as e:  # a page that never loads is a row, not a crash
        return {"error": str(e).splitlines()[0][:200]}
    finally:
        ctx.close()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("site")
    ap.add_argument("--pages", default=",".join(PAGES))
    ap.add_argument("--json")
    ap.add_argument("--cpu", type=float, default=4)
    ap.add_argument("--net", default="fast3g")
    ap.add_argument("--lowend", action="store_true", help="report navigator.deviceMemory = 2 (a low-end device: LITE by itself)")
    ap.add_argument("--extra", nargs="*", default=[], help="extra single .html files served next to the site (e.g. olympus-live.html)")
    a = ap.parse_args(argv)
    from playwright.sync_api import sync_playwright
    srv, base = serve(os.path.abspath(a.site))
    extras = {}
    if a.extra:   # serve extra files from their own folder on a second port (the site folder is never written)
        for f in a.extra:
            s2, b2 = serve(os.path.dirname(os.path.abspath(f)))
            extras[os.path.basename(f)] = (s2, b2)
    rows = []
    with sync_playwright() as pw:
        br = launch(pw)
        for name in [p.strip() for p in a.pages.split(",") if p.strip()]:
            if name in extras:
                url = extras[name][1] + "/" + name + QUERY
            elif name.endswith(".html") and not os.path.isfile(os.path.join(a.site, name)):
                rows.append((name, {"error": "not in this site"}))
                continue
            else:
                url = page_url(base, name)
            t = time.time()
            r = measure(br, url, a.cpu, a.net, lowend=a.lowend)
            r["wall_s"] = round(time.time() - t, 1)
            rows.append((name, r))
            print(name, json.dumps(r), flush=True)
        br.close()
    srv.shutdown()
    print("\n".join(table_lines(rows)))
    if a.json:
        with open(a.json, "w") as fh:
            json.dump({"cpu": a.cpu, "net": a.net, "lowend": a.lowend, "rows": dict(rows)}, fh, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
