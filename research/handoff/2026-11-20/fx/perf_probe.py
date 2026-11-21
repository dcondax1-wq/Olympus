"""Board / Ledger / Hera / Business speed: LCP, CLS, TBT (long tasks over 50 ms, first 10 s), KB on the wire. 390x844, 4x CPU slowdown,
our code + the live site's data files (scan.py's server). Median of 3 runs.
    python research/handoff/2026-11-20/fx/perf_probe.py [apps...] --out FILE"""
import http.server, json, os, statistics, sys, threading
HERE = os.path.dirname(os.path.abspath(__file__))
src = open(os.path.join(HERE, "..", "olympus2", "archive", "scan.py")).read().replace("main()\n", "")
_argv = sys.argv; sys.argv = [sys.argv[0]]
exec(compile(src, "scan", "exec"))
sys.argv = _argv
ROOT = os.path.abspath(os.path.join(HERE, *[".."] * 4, "tools", "web_public"))
out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else None
apps = [a for a in sys.argv[1:] if not a.startswith("--") and a != out] or ["board", "ledger", "hera", "business"]
srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H); port = srv.server_address[1]
threading.Thread(target=srv.serve_forever, daemon=True).start()
INIT = """window.__p = { cls: 0, lcp: 0, tbt: 0 };
window.__p.src = []; new PerformanceObserver((l) => { for (const e of l.getEntries()) if (!e.hadRecentInput) { window.__p.cls += e.value; for (const s of e.sources || []) { const n = s.node; window.__p.src.push([Math.round(e.value * 1000) / 1000, n && n.nodeType === 1 ? (n.id || n.className || n.tagName).toString().slice(0, 40) : String(n && n.nodeName), Math.round(e.startTime)]); } } }).observe({ type: 'layout-shift', buffered: true });
new PerformanceObserver((l) => { const e = l.getEntries(); if (e.length) window.__p.lcp = e[e.length - 1].startTime; }).observe({ type: 'largest-contentful-paint', buffered: true });
new PerformanceObserver((l) => { for (const e of l.getEntries()) window.__p.tbt += Math.max(0, e.duration - 50); }).observe({ type: 'longtask', buffered: true });"""
from playwright.sync_api import sync_playwright
res = {}
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    for app in apps:
        runs = []
        for _ in range(3):
            c = b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True); pg = c.new_page()
            cdp = c.new_cdp_session(pg); cdp.send("Emulation.setCPUThrottlingRate", {"rate": 4})
            if "--slow" in sys.argv: cdp.send("Network.enable"); cdp.send("Network.emulateNetworkConditions", {"offline": False, "latency": 150, "downloadThroughput": 200000, "uploadThroughput": 90000})
            pg.add_init_script(INIT); kb = [0]
            def r(resp):
                try: kb[0] += int(resp.request.sizes().get("responseBodySize") or 0)
                except Exception: pass
            pg.on("response", r)
            if "--heights" in sys.argv:
                pg.goto(f"http://127.0.0.1:{port}/{app}/", wait_until="commit")
                H_JS = "() => [...document.querySelectorAll('#app > *')].slice(0, 9).map((e) => (e.id || e.className || e.tagName).toString().slice(0, 18) + ':' + Math.round(e.getBoundingClientRect().height))"
                for t in (1500, 2500, 3500, 8000):
                    pg.wait_for_timeout(t - (0 if t == 1500 else {2500: 1500, 3500: 2500, 8000: 3500}[t])); print(t, pg.evaluate(H_JS))
                c.close(); break
            pg.goto(f"http://127.0.0.1:{port}/{app}/", wait_until="load", timeout=60000); pg.wait_for_timeout(10000)
            m = pg.evaluate("() => window.__p"); m["kb"] = round(kb[0] / 1024); runs.append(m); c.close()
        res[app] = {k: round(statistics.median(r[k] for r in runs), 3 if k == "cls" else 0) for k in ("lcp", "cls", "tbt", "kb")}
        print(app, res[app], flush=True)
        if "--why" in sys.argv: print(sorted([x for r in runs for x in r.get("src", [])], reverse=True)[:12])
    b.close()
if out: json.dump(res, open(out, "w"), indent=1)
