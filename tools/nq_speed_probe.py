#!/usr/bin/env python3
"""NQ SPEED probe (night-nq-speed 2026-11-27): how fast each NQ page has the PC's live numbers on a phone.

    python -X utf8 tools/nq_speed_probe.py [--pages index,live,accounts,brain] [--net 4g|slow4g] [--runs 3]
        [--variant before|after|both] [--json out.json] [--md out.md] [--shots DIR]

Chromium 390 x 844, CPU x4, service workers blocked (a cold visit), the REAL public ntfy topic (status_feed.json, signed posts:
nothing faked, nothing mocked) under the network line:  4g = 9 Mbps down / 170 ms RTT (a phone on LTE), slow4g = Lighthouse's
1.6 Mbps / 150 ms (+ the 4x CPU). Per page and visit:
  feed_ms     the first time PC_FEED.fetchLatest() answered on the page (the post every widget waits for)
  dom_ms      nq/index only: the line "Source: your PC's status report" on screen (the page drew the PC's numbers)
  cache_ms    after only: when nqfeed.js had the kept post ready (the WARM visit can paint numbers + their age from here)
  fetches     ntfy + status_feed.json requests during the visit (duplicates show here)
  kb_feed     bytes of those requests
Variants: before = the pages as they are; after = the same page with <script src="nqfeed.js"> injected right after ../pc_feed.js
(in the browser only: the repo's HTML is not touched; the page owners add that one tag, LEAD_WIRES.md). Each variant runs a cold
visit then a warm one (same browser profile, localStorage kept). Median of --runs.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import phone_budget as PB  # noqa: E402

SITE = os.path.join(ROOT, "tools", "web_public")
NETS = {"4g": {"offline": False, "latency": 170, "downloadThroughput": 9e6 / 8, "uploadThroughput": 1.5e6 / 8},
        "slow4g": {"offline": False, "latency": 150, "downloadThroughput": 1.6e6 / 8, "uploadThroughput": 750e3 / 8}}
PAGES = {"index": "nq/index.html", "live": "nq/live.html", "accounts": "nq/accounts.html", "brain": "nq/brain.html"}
TAG = '<script src="nqfeed.js?v=1"></script>'
LIVE_SITE = "https://dcondax1-wq.github.io/"     # the published site: its home.json / learned.json (built in the cloud, not in the repo)
BUILT = ("home.json", "hub/learned.json")


def built_files():
    """the published site's built files, read once (in memory only, never written): the local folder has none, and nq/index.html
    falls back to its DEMO without home.json (it then never asks for the PC's post)"""
    import ssl
    import urllib.request
    ca = "/root/.ccr/ca-bundle.crt"
    ctx = ssl.create_default_context(cafile=ca) if os.path.exists(ca) else ssl.create_default_context()
    out = {}
    for rel in BUILT:
        try:
            with urllib.request.urlopen(LIVE_SITE + rel, timeout=20, context=ctx) as r:
                out[rel] = r.read()
        except Exception as e:  # noqa: BLE001
            print(f"(no {rel} from the published site: {e})", file=sys.stderr)
    return out

# records the first answer of PC_FEED.fetchLatest (whoever set it: pc_feed.js, then nqfeed.js's wrapper) + when nqfeed had its cache
INIT = r"""
(() => {
  window.__nqp = { feed: null, cache: null, calls: 0 };
  const wrapApi = (api) => {
    if (!api || api.__nqpWrapped) return api;
    let fn = api.fetchLatest;
    const w = (f) => function () { window.__nqp.calls++; const p = f.apply(this, arguments);
      Promise.resolve(p).then((v) => { if (v && window.__nqp.feed == null) window.__nqp.feed = performance.now(); }, () => {}); return p; };
    Object.defineProperty(api, 'fetchLatest', { configurable: true, get: () => fn, set: (v) => { fn = v && !v.__nqpW ? Object.assign(w(v), { __nqpW: 1 }) : v; } });
    api.fetchLatest = fn; api.__nqpWrapped = true; return api;
  };
  let pf; Object.defineProperty(window, 'PC_FEED', { configurable: true, get: () => pf, set: (v) => { pf = wrapApi(v); } });
  let nf; Object.defineProperty(window, 'NQ_FEED', { configurable: true, get: () => nf, set: (v) => { nf = v; try { if (v && v.cached && v.cached()) window.__nqp.cache = performance.now(); } catch (e) {} } });
})();
"""


def _visit(ctx, url, net, cpu, marker, timeout_s=30):
    page = ctx.new_page()
    cdp = ctx.new_cdp_session(page)
    cdp.send("Network.enable")
    cdp.send("Network.emulateNetworkConditions", net)
    cdp.send("Emulation.setCPUThrottlingRate", {"rate": cpu})
    reqs = []
    page.on("requestfinished", lambda r: reqs.append(r) if ("ntfy" in r.url or "status_feed.json" in r.url) else None)
    page.goto(url, wait_until="commit", timeout=timeout_s * 1000)
    t_end = time.time() + timeout_s
    dom = None
    while time.time() < t_end:
        st = page.evaluate("() => ({ feed: window.__nqp && window.__nqp.feed, cache: window.__nqp && window.__nqp.cache, calls: window.__nqp && window.__nqp.calls,"
                           " dom: %s })" % ("document.body && document.body.innerText.includes(%s) ? performance.now() : null" % json.dumps(marker) if marker else "null"))
        if st["dom"] and dom is None:
            dom = st["dom"]
        if st["feed"] and (dom or not marker):
            break
        page.wait_for_timeout(100)
    page.wait_for_timeout(1500)          # the late duplicates (a 2nd widget's own fetch) land in the count
    st = page.evaluate("() => window.__nqp")
    kb = 0.0
    for r in reqs:
        try:
            kb += (r.sizes().get("responseBodySize", 0) or 0) / 1024
        except Exception:
            pass
    row = {"feed_ms": round(st["feed"]) if st.get("feed") else None, "dom_ms": round(dom) if dom else None,
           "cache_ms": round(st["cache"]) if st.get("cache") else None, "fetches": len(reqs),
           "ntfy": sum(1 for r in reqs if "ntfy" in r.url), "kb_feed": round(kb, 1), "calls": st.get("calls")}
    return page, row


def run(pages, net_name, runs, variants, shots=None):
    from playwright.sync_api import sync_playwright
    srv, base = PB.serve(SITE)
    built = built_files()
    out = []
    try:
        with sync_playwright() as pw:
            br = PB.launch(pw)
            for v in variants:
                for name in pages:
                    rel = PAGES[name]
                    samples = {"cold": [], "warm": []}
                    for i in range(runs):
                        ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1, service_workers="block")
                        ctx.add_init_script(INIT)
                        for rel_b, body_b in built.items():
                            ctx.route(f"{base}/{rel_b}*", lambda route, _b=body_b: route.fulfill(status=200, content_type="application/json", body=_b))
                        if v == "after":
                            def inject(route, _rel=rel):
                                resp = route.fetch()
                                body = resp.text()
                                body2 = re.sub(r'(<script src="\.\./pc_feed\.js[^"]*"></script>)', r"\1" + TAG, body, count=1)
                                route.fulfill(response=resp, body=body2)
                            ctx.route(re.compile(r".*/" + re.escape(rel) + r"(\?.*)?$"), inject)
                        marker = "your PC's status report" if name == "index" else None
                        for visit in ("cold", "warm"):
                            page, row = _visit(ctx, f"{base}/{rel}", NETS[net_name], 4, marker)
                            if shots and i == 0 and visit == "warm":
                                os.makedirs(shots, exist_ok=True)
                                page.screenshot(path=os.path.join(shots, f"{v}_{name}_390x844.png"))
                            page.close()
                            samples[visit].append(row)
                        ctx.close()
                    for visit, rows in samples.items():
                        med = {}
                        for k in ("feed_ms", "dom_ms", "cache_ms", "fetches", "ntfy", "kb_feed", "calls"):
                            vals = [r[k] for r in rows if r.get(k) is not None]
                            med[k] = round(statistics.median(vals), 1) if vals else None
                        out.append({"variant": v, "page": name, "visit": visit, "net": net_name, "runs": runs, **med})
                        print(json.dumps(out[-1]), flush=True)
            br.close()
    finally:
        srv.shutdown()
    return out


def table(rows):
    L = ["| variant | page | visit | feed ready ms | 'PC report' on screen ms | cached post ready ms | feed requests (ntfy) | feed KB |", "|---|---|---|---|---|---|---|---|"]
    f = lambda x: "-" if x is None else (str(int(x)) if isinstance(x, (int, float)) and float(x).is_integer() else str(x))
    for r in rows:
        L.append(f"| {r['variant']} | {r['page']} | {r['visit']} | {f(r['feed_ms'])} | {f(r['dom_ms'])} | {f(r['cache_ms'])} | {f(r['fetches'])} ({f(r['ntfy'])}) | {f(r['kb_feed'])} |")
    return L


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--pages", default="index,live,accounts,brain")
    ap.add_argument("--net", default="4g", choices=sorted(NETS))
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--variant", default="both", choices=["before", "after", "both"])
    ap.add_argument("--json")
    ap.add_argument("--md")
    ap.add_argument("--shots")
    a = ap.parse_args(argv)
    pages = [p for p in a.pages.split(",") if p in PAGES]
    variants = ["before", "after"] if a.variant == "both" else [a.variant]
    rows = run(pages, a.net, a.runs, variants, a.shots)
    lines = table(rows)
    print("\n".join(lines))
    if a.json:
        json.dump(rows, open(a.json, "w"), indent=1)
    if a.md:
        open(a.md, "w").write(f"# NQ speed probe ({a.net}, CPU x4, 390x844, real ntfy feed, median of {a.runs})\n\n" + "\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
