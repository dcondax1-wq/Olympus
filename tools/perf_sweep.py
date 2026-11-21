#!/usr/bin/env python3
"""PERF + OFFLINE sweep of every VISIBLE app on a phone profile (day-quality, Olympus v2 team PERF, 2026-11-20).

    python -X utf8 tools/perf_sweep.py [--site tools/web_public] [--pages nq,ledger,...] [--json out.json] [--md out.md]
        [--no-offline] [--net fast3g|none] [--cpu 4] [--check]   (--check: exit 1 when an app breaks its budget in tools/perf_budgets.json)
    python -X utf8 tools/perf_sweep.py --static --check      no browser, < 1 s: the eager files of each app vs the "static" budgets
    python -X utf8 tools/perf_sweep.py --lock --compare --md after.md --json after.json
                                                             ONE command after a landing: the sweep (taking the browser lock itself),
                                                             then before -> after per app vs research/.../perf/baseline.json

The visible apps = olympus/apps-list.js minus olympus/doors.js ARCHIVE (+ jarvis/, gate/, hub/). Built on tools/phone_budget.py (the same
read-only gzip server, Chromium, Fast-3G line and x4 CPU at 390 x 844, service workers blocked for the cold visit). Per app:
  kb / req / js_kb / img_kb / font_kb   bytes over the wire on first open (6 s after load), by kind; top3 = the 3 biggest files
  fcp_ms / lcp_ms                       first / largest contentful paint on that line
  lt_n / lt_max / tbt                   long tasks (> 50 ms) count, the longest, total blocking time (sum of each task's time over 50 ms)
  cls                                   cumulative layout shift
  heap_mb                               JS heap after the settle window
  errors                                console errors + page errors (the Olympus bar: 0)
  sideways                              the page scrolls sideways at 390 px (bar: never)
  offline                               second visit with the service worker allowed, then the network cut and a reload:
                                        "ok" (opens, shows text) / "blank" / "error <why>"; age = it shows a data age ("5 min ago",
                                        "as of", "updated") / sw = a service worker controls the page
The arithmetic (rows, budgets, the table) is plain functions: tests/test_perf_sweep.py checks them without a browser and runs one small
real page. ONE browser at a time: tests/run_area.py takes the browser lock itself; by hand: flock -w 2400 /tmp/olympus_browser.lock.
Read-only: nothing is written into the site folder.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import phone_budget as PB  # noqa: E402

SITE = os.path.join(ROOT, "tools", "web_public")
BASELINE = os.path.join(ROOT, "research", "handoff", "2026-11-20", "olympus2", "perf", "baseline.json")
DIFF_KEYS = (("fcp_ms", "first paint ms"), ("lcp_ms", "largest paint ms"), ("kb", "KB first open"), ("lt_max", "longest task ms"),
             ("tbt", "TBT ms"), ("cls", "CLS"), ("errors", "errors"))
BUDGETS = os.path.join(ROOT, "tools", "perf_budgets.json")
EXTRA_PAGES = ["jarvis", "gate", "hub"]
IMG = (".png", ".jpg", ".jpeg", ".webp", ".avif", ".gif", ".svg", ".ico")
FONT = (".woff2", ".woff", ".ttf", ".otf")
# files the publish build writes (tools/build_web_dashboard.py, gh_publish): a 404 on them in the repo tree is expected, not an app error
BUILT = re.compile(r"/(home|data|kalshi|live|status)\.json|/money/[^/?]+\.json|/me/me\.json|/hub/learned\.json|/push_relay\.json|/charts/|/icons/|/writeups/index\.json"
                   r"|/kalshi/kit\.json|/agency/my_leads\.json|/business/business\.json")
AGE_RX = re.compile(r"(\b\d+\s*(?:s|sec|min|m|h|hr|hour|hours|d|day|days)\s+ago\b|\bas of\b|\bupdated\b|\blast (?:data|update|seen|report)|\bjust now\b|\bstale\b|\bold\b)", re.I)

MORE = r"""
(() => {
  window.__ps = { lt: [], cls: 0, err: [], shifts: [] };
  const who = (n) => { try { if (!n || !n.tagName) return '?'; let s = n.tagName.toLowerCase() + (n.id ? '#' + n.id : '') +
    (n.className && typeof n.className === 'string' ? '.' + n.className.trim().split(/\s+/).slice(0, 2).join('.') : '');
    const p = n.parentElement; return (p && p.tagName ? (p.id ? '#' + p.id : p.tagName.toLowerCase()) + ' > ' : '') + s; } catch (e) { return '?'; } };
  try { new PerformanceObserver((l) => { for (const e of l.getEntries()) window.__ps.lt.push([e.startTime, e.duration]); })
    .observe({ type: 'longtask', buffered: true }); } catch (e) {}
  try { new PerformanceObserver((l) => { for (const e of l.getEntries()) if (!e.hadRecentInput) { window.__ps.cls += e.value;
      if (e.value >= 0.02) window.__ps.shifts.push([Math.round(e.startTime), +e.value.toFixed(3), (e.sources || []).slice(0, 2).map((x) => who(x.node)).join(' + ')]); } })
    .observe({ type: 'layout-shift', buffered: true }); } catch (e) {}
})();
"""
COLLECT2 = r"""
(() => ({ lt: (window.__ps || {}).lt || [], cls: (window.__ps || {}).cls || 0, shifts: ((window.__ps || {}).shifts || []).sort((a, b) => b[1] - a[1]).slice(0, 4),
  sideways: Math.max(document.documentElement.scrollWidth, document.body ? document.body.scrollWidth : 0) > Math.min(window.innerWidth, screen.width || 1e9) + 1,
  sw: !!(navigator.serviceWorker && navigator.serviceWorker.controller) }))()
"""


# ------------------------------------------------------------------------------------------------ pure (unit-tested)
def visible_apps(site=SITE) -> list:
    """[(id, path)] of the apps the Doors page and the launcher show (apps-list minus doors.js ARCHIVE), + Jarvis, Gate, Hub."""
    js = ("global.window={};require(%r);const D=window.OLYMPUS_DOORS;const l=require(%r);const ar=new Set(D.ARCHIVE||[]);"
          "console.log(JSON.stringify(l.filter(a=>!ar.has(a.id)).map(a=>[a.id,a.path])))")
    out = subprocess.run(["node", "-e", js % (os.path.join(site, "olympus", "doors.js"), os.path.join(site, "olympus", "apps-list.js"))],
                         capture_output=True, text=True, timeout=60)
    rows = [tuple(x) for x in json.loads(out.stdout or "[]")]
    have = {p for _i, p in rows}
    return rows + [(p, p + "/") for p in EXTRA_PAGES if p + "/" not in have]


def kind_of(url: str) -> str:
    p = url.split("?")[0].split("#")[0].lower()
    return "js" if p.endswith((".js", ".mjs")) else "img" if p.endswith(IMG) else "font" if p.endswith(FONT) else \
        "css" if p.endswith(".css") else "data" if p.endswith((".json", ".csv", ".md", ".txt")) else "other"


def long_tasks(lt) -> dict:
    ds = [float(d) for _s, d in (lt or [])]
    return {"lt_n": len(ds), "lt_max": int(round(max(ds))) if ds else 0, "tbt": int(round(sum(max(0.0, d - 50) for d in ds)))}


def row_of(raw: dict, raw2: dict, errors: list, site_base: str = "") -> dict:
    r = PB.summarize(raw)
    res = raw.get("res") or []
    by = {}
    for x in res:
        k = kind_of(x.get("n", ""))
        by[k] = by.get(k, 0) + int(x.get("t") or 0)
    top = sorted(res, key=lambda x: -int(x.get("t") or 0))[:3]
    r.update(long_tasks(raw2.get("lt")))
    r.update({"img_kb": round(by.get("img", 0) / 1024, 1), "font_kb": round(by.get("font", 0) / 1024, 1), "css_kb": round(by.get("css", 0) / 1024, 1),
              "data_kb": round(by.get("data", 0) / 1024, 1), "cls": round(float(raw2.get("cls") or 0), 3), "sideways": bool(raw2.get("sideways")),
              "errors": len(errors), "error_list": errors[:5], "shifts": raw2.get("shifts") or [],
              "top3": [f"{x.get('n', '').replace(site_base, '').split('?')[0]} {int(x.get('t') or 0) // 1024} KB" for x in top]})
    return r


def static_rows(site=SITE, pages=None) -> dict:
    """no browser (< 1 s): what each visible app loads WITHOUT a user action, from its files (phone_budget.static_row: the html's
    tags, module imports followed): block_kb = what holds the first paint, eager_js_kb, three = three.js eager. The guard that
    runs at every ship: someone adding three.js or a render-blocking file to an app shows here at once."""
    out = {}
    for app, path in (pages or visible_apps(site)):
        r = PB.static_row(site, path or "root")
        if "error" not in r:
            out[app] = {"block_kb": r["block_kb"], "eager_js_kb": r["eager_js_kb"], "three": r["three"]}
    return out


def static_over(rows: dict, budgets: dict) -> dict:
    b0 = (budgets.get("static") or {}).get("default") or {}
    bad = {}
    for app, r in rows.items():
        b = dict(b0, **((budgets.get("static") or {}).get(app) or {}))
        why = [f"{k} {r[k]} > {lim}" for k, lim in b.items() if k != "three" and isinstance(r.get(k), (int, float)) and r[k] > lim]
        if b.get("three") is False and r.get("three"):
            why.append("three.js loads eagerly")
        if why:
            bad[app] = why
    return bad


def compare(before: dict, after: dict) -> tuple:
    """(table lines, {app: [what got worse]}) before -> after per app; a change under 10% (or 0.02 CLS, 100 ms) is shown as '='"""
    def fmt(k, a, b):
        if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
            return f"{a if a is not None else '-'} -> {b if b is not None else '-'}"
        small = abs(b - a) <= (0.02 if k == "cls" else max(100 if k.endswith("ms") or k in ("tbt", "lt_max") else 0, abs(a) * 0.10))
        arrow = "=" if small else ("better" if b < a else "WORSE")
        return f"{a:g} -> {b:g} {arrow}"
    head = "| app | " + " | ".join(h for _k, h in DIFF_KEYS) + " | offline |"
    out, worse = [head, "|" + "---|" * (len(DIFF_KEYS) + 2)], {}
    for app in list(after) + [a for a in before if a not in after]:
        a, b = before.get(app) or {}, after.get(app) or {}
        if "error" in b or not b:
            out.append(f"| {app} | not measured now{': ' + b['error'][:40] if b.get('error') else ''} |" + " |" * len(DIFF_KEYS))
            continue
        cells = [fmt(k, a.get(k), b.get(k)) for k, _h in DIFF_KEYS]
        w = [h for (k, h), c in zip(DIFF_KEYS, cells) if c.endswith("WORSE")]
        oa, ob = a.get("offline") or "-", b.get("offline") or "-"
        oa, ob = ("ok" if oa == "ok" else "no"), ("ok" if ob == "ok" else "no")
        if oa == "ok" and ob != "ok":
            w.append("offline")
        if w:
            worse[app] = w
        out.append(f"| {app} | " + " | ".join(cells) + f" | {oa} -> {ob} |")
    return out, worse


def load_budgets(path=BUDGETS) -> dict:
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {"default": {}}


def over(app: str, row: dict, budgets: dict) -> list:
    """the budget lines an app breaks: its own budget over the default; numbers are upper bounds, 'offline' must be 'ok'"""
    if "error" in row:
        return [f"did not load: {row['error'][:80]}"]
    b = dict(budgets.get("default") or {}, **(budgets.get(app) or {}))
    out = []
    for k, lim in b.items():
        if k == "offline":
            if lim and row.get("offline") not in (None, "ok", "skipped"):
                out.append(f"offline {row.get('offline')}")
        elif k == "sideways":
            if lim is False and row.get("sideways"):
                out.append("scrolls sideways")
        elif isinstance(lim, (int, float)) and isinstance(row.get(k), (int, float)) and row[k] > lim:
            out.append(f"{k} {row[k]} > {lim}")
    return out


def table(rows: list) -> list:
    head = ("| app | first paint ms | largest paint ms | KB first open | JS KB | img KB | font KB | long tasks (max ms) | TBT ms | CLS | heap MB | errors | sideways | offline |")
    out = [head, "|" + "---|" * 14]
    for app, r in rows:
        if "error" in r:
            out.append(f"| {app} | did not load: {r['error'][:50]} |" + " |" * 12)
            continue
        off = r.get("offline", "")
        off = off + (" +age" if r.get("offline_age") else "") + (" (sw)" if r.get("offline_sw") else "") if off else ""
        out.append(f"| {app} | {r['fcp_ms']} | {r['lcp_ms']} | {r['kb']:.0f} | {r['js_kb']:.0f} | {r['img_kb']:.0f} | {r['font_kb']:.0f} | "
                   f"{r['lt_n']} ({r['lt_max']}) | {r['tbt']} | {r['cls']} | {r['heap_mb']} | {r['errors']} | {'YES' if r['sideways'] else 'no'} | {off} |")
    return out


# ------------------------------------------------------------------------------------------------ the browser run
def serve_https(folder):
    """the same read-only gzip server over https with a throwaway self-signed cert: main.js registers the root service worker only on
    https (as on GitHub Pages), so the offline pass needs it; Chromium runs with --ignore-certificate-errors for this origin only"""
    import ssl
    import tempfile
    srv, base = PB.serve(folder)
    d = tempfile.mkdtemp(prefix="le_perf_cert_")
    key, crt = os.path.join(d, "k.pem"), os.path.join(d, "c.pem")
    subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", key, "-out", crt, "-days", "1",
                    "-subj", "/CN=127.0.0.1"], capture_output=True, check=True, timeout=60)
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(crt, key)
    srv.socket = ctx.wrap_socket(srv.socket, server_side=True)
    return srv, base.replace("http://", "https://")


def launch(pw):
    import glob
    exe = sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))
    return pw.chromium.launch(args=["--no-sandbox", "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
                                    "--enable-precise-memory-info", "--ignore-certificate-errors"],
                              **({"executable_path": exe[-1]} if exe else {}))


def cold(br, url, cpu, net, base):
    ctx = br.new_context(viewport={"width": PB.W, "height": PB.H}, device_scale_factor=2, is_mobile=True, has_touch=True, service_workers="block",
                         ignore_https_errors=True)
    ctx.add_init_script(PB.INIT)
    ctx.add_init_script(MORE)
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append("page: " + str(e).splitlines()[0][:160]))
    built = []

    def on_console(m):
        if m.type != "error":
            return
        u = (m.location or {}).get("url", "") if isinstance(m.location, dict) else ""
        if "Failed to load resource" in m.text and BUILT.search(u or ""):
            built.append(u.replace(base, "").split("?")[0])
            return
        errs.append("console: " + m.text[:120] + (f" [{u.replace(base, '').split('?')[0]}]" if u else ""))
    pg.on("console", on_console)
    try:
        cdp = ctx.new_cdp_session(pg)
        cdp.send("Network.enable")
        cdp.send("Network.setCacheDisabled", {"cacheDisabled": True})
        if cpu and cpu > 1:
            cdp.send("Emulation.setCPUThrottlingRate", {"rate": cpu})
        if net in PB.NET:
            cdp.send("Network.emulateNetworkConditions", PB.NET[net])
        pg.goto(url, wait_until="load", timeout=120000)
        pg.wait_for_timeout(PB.SETTLE_MS)
        r = row_of(pg.evaluate(PB.COLLECT), pg.evaluate(COLLECT2), errs, base)
        r["built_404"] = sorted(set(built))                 # built at publish time: not counted as errors
        return r
    except Exception as e:  # noqa: BLE001
        return {"error": str(e).splitlines()[0][:200]}
    finally:
        ctx.close()


def offline(br, url, home=None) -> dict:
    """as on the phone: the Home Screen app (Zenith, `home`) opened once (it registers the root worker), then the app opened once,
    then the network cut and a reload: does the app still open, and does it show the age of its data?"""
    ctx = br.new_context(viewport={"width": PB.W, "height": PB.H}, device_scale_factor=2, is_mobile=True, has_touch=True, ignore_https_errors=True)
    pg = ctx.new_page()
    try:
        if home:
            pg.goto(home, wait_until="load", timeout=90000)
            try:
                pg.evaluate("navigator.serviceWorker ? Promise.race([navigator.serviceWorker.ready, new Promise((r) => setTimeout(r, 8000))]) : 0")
            except Exception:  # noqa: BLE001
                pass
        pg.goto(url, wait_until="load", timeout=90000)
        try:
            pg.evaluate("navigator.serviceWorker ? Promise.race([navigator.serviceWorker.ready, new Promise((r) => setTimeout(r, 8000))]) : 0")
        except Exception:  # noqa: BLE001
            pass
        pg.wait_for_timeout(4000)                          # the worker's install fills its cache
        pg.reload(wait_until="load", timeout=60000)        # now under the worker's control (clients.claim or not)
        pg.wait_for_timeout(2500)
        sw = bool(pg.evaluate("!!(navigator.serviceWorker && navigator.serviceWorker.controller)"))
        ctx.set_offline(True)
        try:
            pg.reload(wait_until="load", timeout=30000)
        except Exception as e:  # noqa: BLE001
            return {"offline": "error " + str(e).splitlines()[0][:60], "offline_sw": sw, "offline_age": False}
        pg.wait_for_timeout(3000)
        txt = pg.evaluate("document.body ? document.body.innerText : ''") or ""
        blank = len(txt.strip()) < 40 or "ERR_INTERNET_DISCONNECTED" in txt
        return {"offline": "blank" if blank else "ok", "offline_sw": sw, "offline_age": bool(AGE_RX.search(txt))}
    except Exception as e:  # noqa: BLE001
        return {"offline": "error " + str(e).splitlines()[0][:60], "offline_sw": False, "offline_age": False}
    finally:
        ctx.close()


def offline_sweep(site, pages, say=print) -> dict:
    """only the offline leg for each app (tests/test_offline_apps.py): {app: {"offline", "offline_sw", "offline_age"}}"""
    from playwright.sync_api import sync_playwright
    srv, base = serve_https(os.path.abspath(site))
    out = {}
    try:
        with sync_playwright() as pw:
            br = launch(pw)
            for app, path in pages:
                out[app] = offline(br, base + "/" + path + PB.QUERY, base + "/" + PB.QUERY)
                say(f"{app}: {out[app]}")
            br.close()
    finally:
        srv.shutdown()
    return out


def patch_in(site=SITE) -> bool:
    """the root worker answers app folders (LEAD_WIRES 1 of the perf hand-off, appNetFirst) = every app must open offline"""
    try:
        return "appNetFirst" in open(os.path.join(site, "sw.js"), encoding="utf-8").read()
    except OSError:
        return False


def sweep(site, pages, cpu=4, net="fast3g", do_offline=True, say=print) -> list:
    from playwright.sync_api import sync_playwright
    srv, base = serve_https(os.path.abspath(site))
    rows = []
    try:
        with sync_playwright() as pw:
            br = launch(pw)
            for app, path in pages:
                url = base + "/" + path + PB.QUERY
                t0 = time.time()
                r = cold(br, url, cpu, net, base)
                if do_offline and "error" not in r:
                    r.update(offline(br, url, base + "/" + PB.QUERY))
                r["wall_s"] = round(time.time() - t0, 1)
                rows.append((app, r))
                say(f"{app}: " + json.dumps({k: v for k, v in r.items() if k not in ("error_list", "top3")}))
            br.close()
    finally:
        srv.shutdown()
    return rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--site", default=SITE)
    ap.add_argument("--pages", default="")
    ap.add_argument("--json")
    ap.add_argument("--md")
    ap.add_argument("--cpu", type=float, default=4)
    ap.add_argument("--net", default="fast3g")
    ap.add_argument("--no-offline", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--compare", nargs="?", const=BASELINE, default=None, metavar="BEFORE.json",
                    help="after the sweep: before -> after per app vs a saved run (default: today's baseline.json)")
    ap.add_argument("--lock", action="store_true", help="take /tmp/olympus_browser.lock around the browser run (tests/browser_lock.py)")
    ap.add_argument("--static", action="store_true", help="no browser: the eager files of every visible app vs the static budgets")
    a = ap.parse_args(argv)
    if a.static:
        rows = static_rows(a.site)
        bad = static_over(rows, load_budgets())
        for app, r in rows.items():
            print(f"{app:10} block {r['block_kb']:6.0f} KB  eager JS {r['eager_js_kb']:6.0f} KB  three.js {'eager' if r['three'] else 'no'}"
                  + (f"   OVER: {'; '.join(bad[app])}" if app in bad else ""))
        print(f"perf static: {len(rows)} apps, {len(bad)} over budget")
        return 1 if (a.check and bad) else 0
    pages = visible_apps(a.site)
    if a.pages:
        want = [p.strip() for p in a.pages.split(",") if p.strip()]
        pages = [p for p in pages if p[0] in want] + [(w, w + "/") for w in want if w not in {p[0] for p in pages}]
    if a.lock:
        sys.path.insert(0, os.path.join(ROOT, "tests"))
        import browser_lock
        with browser_lock.hold(browser_lock.DEFAULT, 2400):
            rows = sweep(a.site, pages, a.cpu, a.net, not a.no_offline)
    else:
        rows = sweep(a.site, pages, a.cpu, a.net, not a.no_offline)
    budgets = load_budgets()
    lines = table(rows)
    bad = {app: over(app, r, budgets) for app, r in rows}
    bad = {k: v for k, v in bad.items() if v}
    print("\n".join(lines))
    for app, why in bad.items():
        print(f"OVER BUDGET {app}: {'; '.join(why)}")
    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump({"cpu": a.cpu, "net": a.net, "rows": dict(rows), "over": bad}, fh, indent=1)
    if a.md:
        with open(a.md, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
    worse = {}
    if a.compare:
        try:
            with open(a.compare, encoding="utf-8") as fh:
                bj = json.load(fh)
            before = bj.get("rows", bj) if isinstance(bj, dict) else {}
        except (OSError, ValueError) as e:
            before = {}
            print(f"compare: cannot read {a.compare} ({e.__class__.__name__})")
        clines, worse = compare(before, {k: v for k, v in rows})
        print("\n## Before -> after (vs " + os.path.relpath(a.compare, ROOT) + ")\n" + "\n".join(clines))
        for app, w in worse.items():
            print(f"WORSE {app}: {', '.join(w)}")
        if a.md:
            with open(a.md, "a", encoding="utf-8") as fh:
                fh.write("\n## Before -> after (vs " + os.path.relpath(a.compare, ROOT) + ")\n\n" + "\n".join(clines) + "\n")
    print(f"perf sweep: {len(rows)} apps, {len(bad)} over budget" + (f", {len(worse)} worse than before" if a.compare else ""))
    return 1 if (a.check and bad) else 0


if __name__ == "__main__":
    sys.exit(main())
