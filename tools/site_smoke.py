#!/usr/bin/env python3
"""Site smoke: open EVERY app page of a BUILT site in a phone-sized browser and say plainly which ones are broken.

    flock -w 2400 /tmp/olympus_browser.lock python tools/site_smoke.py <site folder> --out <folder> [--json out.json] [--apps a,b,c]

<site folder> is the output of tools/build_web_dashboard.py. The tool serves it on a free local port (read only), opens the root page and every
folder with an index.html at 390 x 844 with ?demo=1&q=low&welcome=0&intro=0, waits until the intro film is over and content is there, and records per app:
  HTTP status, console errors, uncaught exceptions, failed same-origin requests, visibly non-blank (text length + painted pixels), sideways overflow,
  a title / app marker, the time to first content. It saves one screenshot per app (after the intro) and contact sheets (grids of 12 with names).
Hard failures (exit 1): bad HTTP status, an uncaught exception, a console error, a failed script / style / page request, a blank page, a timeout.
Warnings (exit 0): sideways overflow, no title / app marker, a missing optional data file, a request that tried to leave the site.
ONE browser on the machine: always run it under the flock lock. Nothing is written into the site folder. It never pushes or publishes anything.

The analysis is in plain functions (discover, classify, painted_share, table_lines, sheets_plan) so tests/test_site_smoke.py checks it without a browser.
"""
from __future__ import annotations

import argparse
import functools
import http.server
import io
import json
import os
import re
import sys
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUERY = "?demo=1&q=low&welcome=0&intro=0"
W, H = 390, 844
MIN_TEXT = 40                 # characters of visible text below which a page counts as empty
MIN_PAINTED = 0.01            # share of pixels that differ from the page's main colour below which a page with little text counts as unpainted
VEIL_SLOW_MS = 8000           # the kit's loading veil lifts by itself after 12 s: lasting longer than this means the app never said it is ready
NOTHING = 0.003               # below this share nothing at all is on the screen, whatever the text says (hidden text, a stuck cover)
CODE_EXT = (".js", ".mjs", ".css", ".html", ".htm", ".wasm")
# console noise that is not a defect of the page: the request list already carries failed loads, and software GL warns about itself
IGNORE_CONSOLE = re.compile(r"Failed to load resource|net::ERR_|GPU stall|WebGL.*(software|fallback|deprecated)|GL_INVALID|swiftshader|Automatic fallback to software|"
                            r"the server responded with a status of 404", re.I)
HARD = ("status", "exception", "console", "request", "blank", "timeout", "intro", "veil")


# ------------------------------------------------------------------------------------------------ pure analysis (unit-tested)
def discover(site):
    """The pages to open: '' (the root) first, then every folder that has an index.html, by name."""
    apps = [""] if os.path.isfile(os.path.join(site, "index.html")) else []
    for name in sorted(os.listdir(site)):
        if os.path.isfile(os.path.join(site, name, "index.html")):
            apps.append(name)
    return apps


def pick(apps, only):
    """--apps a,b,c: keep these (in the site's order); 'root' or '/' names the root page. Unknown names are returned too so they can be reported."""
    if not only:
        return list(apps), []
    want = [("" if x.strip() in ("root", "/", ".") else x.strip().strip("/")) for x in only.split(",") if x.strip()]
    return [a for a in apps if a in want], [x for x in want if x not in apps]


def is_code(url):
    path = url.split("?")[0].split("#")[0].lower()
    return path.endswith(CODE_EXT) or path.endswith("/")


def console_errors(lines):
    """the console lines that are real errors (resource-load echoes and software-GL chatter are left out)"""
    return [str(x)[:300] for x in lines if x and not IGNORE_CONSOLE.search(str(x))]


def painted_share(png_bytes):
    """Share (0..1) of the screenshot's pixels that differ from its most common colour; None when Pillow is not installed or the image is unreadable."""
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(png_bytes)).convert("RGB").resize((98, 211))
    except Exception:
        return None
    px = list(im.getdata())
    counts = {}
    for p in px:
        k = (p[0] >> 3, p[1] >> 3, p[2] >> 3)             # nearby shades are one colour
        counts[k] = counts.get(k, 0) + 1
    return round(1 - max(counts.values()) / len(px), 4)


def classify(rec):
    """One page's record -> (ok, problems, warnings). problems are hard failures; each is 'kind: plain words'."""
    problems, warnings = [], []
    if rec.get("timeout"):
        problems.append(f"timeout: no answer within {rec.get('limit_s', 40)} s")
    st = rec.get("status")
    if st is not None and st != 200:
        problems.append(f"status: the page answered HTTP {st}")
    elif st is None and not rec.get("timeout"):
        problems.append("status: the page did not load")
    for e in rec.get("exceptions") or []:
        problems.append("exception: " + str(e)[:200])
    for e in console_errors(rec.get("console") or []):
        problems.append("console: " + e[:200])
    for r in rec.get("failed") or []:
        url, code = str(r.get("url", "")), r.get("status")
        short = url.split("://", 1)[-1].split("/", 1)[-1][:120]
        if is_code(url):
            problems.append(f"request: {short} answered {code or 'nothing'}")
        else:
            warnings.append(f"missing data: {short} ({code or 'no answer'})")
    if st == 200 and not rec.get("timeout"):
        text, painted, canvases = rec.get("text_len") or 0, rec.get("painted"), rec.get("canvases") or 0
        veil = rec.get("veil_ms")
        if rec.get("veil_stuck") or (isinstance(veil, (int, float)) and veil > VEIL_SLOW_MS):
            problems.append(f"veil: the loading cover stayed {'over 14' if rec.get('veil_stuck') else round(veil / 1000)} s (the app never calls OLYMPUS.ready(), so the kit waits for its 12 s safety lift)")
        if rec.get("intro_stuck"):
            problems.append("intro: the intro film did not end within 15 s (it covers the app)")
        if painted is not None and (painted < NOTHING or (painted < MIN_PAINTED and text < MIN_TEXT and not canvases)):
            problems.append(f"blank: nothing is painted ({painted:.1%} of the screen differs from the background)")
        elif text < MIN_TEXT and not canvases:
            problems.append(f"blank: only {text} characters of text and no canvas")
        if rec.get("overflow_px"):
            warnings.append(f"sideways overflow: {rec['overflow_px']} px wider than the phone")
        if not rec.get("title"):
            warnings.append("no page title")
        if rec.get("kit") is False:
            warnings.append("no app marker (the OLYMPUS kit tag with data-app)")
        if rec.get("err_banner"):
            problems.append("console: the page shows the kit's error banner: " + str(rec["err_banner"])[:160])
    for u in (rec.get("off_origin") or [])[:3]:
        warnings.append("tried to leave the site: " + str(u)[:100])
    return (not problems), problems, warnings


def judge(records):
    out = []
    for r in records:
        ok, problems, warnings = classify(r)
        out.append({**r, "ok": ok, "problems": problems, "warnings": warnings})
    return out


def name_of(app):
    return app or "(root)"


def table_lines(results):
    """The SIMPLE table: app / ok / problem (the first problem, or the first warning, in plain words)."""
    rows = [("app", "ok", "first content", "problem")]
    for r in results:
        note = r["problems"][0] if r["problems"] else (("warning: " + r["warnings"][0]) if r["warnings"] else "")
        more = len(r["problems"]) - 1 if r["problems"] else len(r["warnings"]) - 1
        if more > 0:
            note += f" (+{more} more)"
        t = r.get("first_content_ms")
        rows.append((name_of(r["app"]), "ok" if r["ok"] else "FAIL", f"{t / 1000:.1f} s" if isinstance(t, (int, float)) else "-", note[:150]))
    w = [max(len(row[i]) for row in rows) for i in range(3)]
    lines = [f"{row[0]:<{w[0]}}  {row[1]:<{w[1]}}  {row[2]:>{w[2]}}  {row[3]}".rstrip() for row in rows]
    lines.insert(1, "-" * min(110, max(len(x) for x in lines)))
    return lines


def summary(results):
    bad = [r for r in results if not r["ok"]]
    warn = [r for r in results if r["ok"] and r["warnings"]]
    return {"pages": len(results), "ok": len(results) - len(bad), "failed": len(bad), "with_warnings": len(warn), "failed_apps": [name_of(r["app"]) for r in bad]}


def sheets_plan(n, per=12, cols=4):
    """How n screenshots are laid on contact sheets: [(first index, count, cols, rows)]."""
    plan = []
    for i in range(0, n, per):
        k = min(per, n - i)
        plan.append((i, k, cols, (k + cols - 1) // cols))
    return plan


def contact_sheets(shots, out, per=12, cols=4, cell=(195, 422)):
    """shots = [(name, png path, ok)] -> sheet-<k>.jpg files (a grid of thumbnails with the app's name; a failed app has a red bar). Needs Pillow."""
    try:
        from PIL import Image, ImageDraw
    except Exception:
        return []
    made, label = [], 22
    for k, (i0, n, c, rows) in enumerate(sheets_plan(len(shots), per, cols)):
        sheet = Image.new("RGB", (c * (cell[0] + 8) + 8, rows * (cell[1] + label + 8) + 8), "#14110e")
        d = ImageDraw.Draw(sheet)
        for j in range(n):
            name, path, ok = shots[i0 + j]
            x, y = 8 + (j % c) * (cell[0] + 8), 8 + (j // c) * (cell[1] + label + 8)
            d.rectangle([x, y, x + cell[0], y + label - 2], fill="#26211b" if ok else "#8c3a24")
            d.text((x + 5, y + 5), name[:28] + ("" if ok else "  FAIL"), fill="#f3ece0")
            try:
                im = Image.open(path).convert("RGB")
                im = im.crop((0, 0, im.width, min(im.height, int(im.width * cell[1] / cell[0])))).resize(cell)
                sheet.paste(im, (x, y + label))
            except Exception:
                d.rectangle([x, y + label, x + cell[0], y + label + cell[1]], outline="#8c3a24")
                d.text((x + 8, y + label + 8), "no screenshot", fill="#c96a4a")
        p = os.path.join(out, f"sheet-{k + 1:02d}.jpg")
        sheet.save(p, quality=82)
        made.append(p)
    return made


# ------------------------------------------------------------------------------------------------ the local site (read only)
class _Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def serve(site):
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(_Handler, directory=site))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"


# ------------------------------------------------------------------------------------------------ the browser run
PROBE = """() => { const d = document, b = d.body; const err = d.querySelector('.oly-err-msg');
  return { text_len: b ? (b.innerText || '').replace(/\\s+/g, ' ').trim().length : 0, canvases: d.querySelectorAll('canvas, svg').length, title: (d.title || '').trim(),
    kit: !!d.querySelector('script[data-app], [data-oly-app]'), overflow_px: Math.max(0, d.documentElement.scrollWidth - innerWidth - 1),
    err_banner: err && err.offsetParent !== null ? err.textContent : '', intro: window.__olyAppIntro ? window.__olyAppIntro.state : 'none' }; }"""
VEIL_UP = "() => !!document.querySelector('.oly-veil:not(.out)')"
INTRO_OVER = "() => { const s = window.__olyAppIntro; return !s || ['done', 'skipped', 'off', 'failed'].indexOf(s.state) >= 0; }"


def launch(pw):
    sys.path.insert(0, os.path.join(ROOT, "tests"))
    try:
        import browser_kit as BK
        return BK.launch(pw)
    except Exception:
        import glob
        exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
        return pw.chromium.launch(args=["--no-sandbox", "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"], **({"executable_path": exe} if exe else {}))


def visit(br, origin, app, out, limit_s=40, query=QUERY):
    rec = {"app": app, "url": f"/{app + '/' if app else ''}{query}", "status": None, "console": [], "exceptions": [], "failed": [], "off_origin": [], "limit_s": limit_s, "timeout": False}
    ctx = br.new_context(viewport={"width": W, "height": H}, device_scale_factor=1, is_mobile=True, has_touch=True, reduced_motion="no-preference", service_workers="block")
    ctx.add_init_script("try { localStorage.setItem('jfx', 'low'); localStorage.setItem('oly.intro', 'off'); } catch (e) {}")

    def route(r):
        u = r.request.url
        if u.startswith(origin) or u.startswith("data:") or u.startswith("blob:"):
            r.continue_()
        else:
            rec["off_origin"].append(u)
            r.abort()
    ctx.route("**/*", route)
    p = ctx.new_page()
    p.set_default_timeout(limit_s * 1000)
    p.on("pageerror", lambda e: rec["exceptions"].append(str(e)))
    p.on("console", lambda m: rec["console"].append(m.text) if m.type == "error" else None)
    p.on("response", lambda r: rec["failed"].append({"url": r.url, "status": r.status}) if r.url.startswith(origin) and r.status >= 400 and r.url.split("?")[0] != (origin + "/" + (app + "/" if app else "")) else None)
    p.on("requestfailed", lambda r: rec["failed"].append({"url": r.url, "status": None}) if r.url.startswith(origin) and "ERR_ABORTED" not in str(r.failure or "") else None)
    t0 = time.time()
    left = lambda: max(1.0, limit_s - (time.time() - t0))     # noqa: E731
    try:
        resp = p.goto(origin + rec["url"], wait_until="domcontentloaded", timeout=limit_s * 1000)
        rec["status"] = resp.status if resp else None
        try:
            p.wait_for_function("() => document.body && ((document.body.innerText || '').trim().length >= %d || document.querySelector('canvas'))" % MIN_TEXT, timeout=min(15.0, left()) * 1000, polling=200)
            rec["first_content_ms"] = int((time.time() - t0) * 1000)
        except Exception:
            rec["first_content_ms"] = None
        try:
            p.wait_for_function(INTRO_OVER, timeout=min(15.0, left()) * 1000, polling=200)
        except Exception:
            rec["intro_stuck"] = True
        if p.evaluate(VEIL_UP):                                # the kit's loading veil: wait for it to lift so the screenshot shows the app, and time it
            try:
                p.wait_for_function("() => !document.querySelector('.oly-veil:not(.out)')", timeout=min(14.0, left()) * 1000, polling=100)
            except Exception:
                rec["veil_stuck"] = True
        rec["veil_ms"] = int((time.time() - t0) * 1000) if not rec.get("veil_stuck") else None
        p.wait_for_timeout(int(min(1.5, left()) * 1000))
        rec.update(p.evaluate(PROBE))
        shot = p.screenshot(timeout=min(20.0, left()) * 1000)
        rec["painted"] = painted_share(shot)
        rec["shot"] = os.path.join(out, f"{app or '_root'}.png")
        with open(rec["shot"], "wb") as fh:
            fh.write(shot)
    except Exception as e:                                    # a timeout or a crash of this page: recorded, the run goes on
        if "Timeout" in type(e).__name__ or "timeout" in str(e).lower():
            rec["timeout"] = True
        else:
            rec["exceptions"].append("smoke: " + str(e).splitlines()[0][:200])
    finally:
        rec["seconds"] = round(time.time() - t0, 1)
        try:
            ctx.close()
        except Exception:
            pass
    return rec


def run(site, out, only=None, limit_s=40, query=QUERY, log=print):
    from playwright.sync_api import sync_playwright
    apps, unknown = pick(discover(site), only)
    os.makedirs(out, exist_ok=True)
    srv, origin = serve(site)
    records = [{"app": u, "status": 404, "url": f"/{u}/", "note": "no such app folder in the site"} for u in unknown]
    try:
        with sync_playwright() as pw:
            br = launch(pw)
            for i, app in enumerate(apps):
                rec = visit(br, origin, app, out, limit_s, query)
                ok, problems, _ = classify(rec)
                log(f"[{i + 1}/{len(apps)}] {name_of(app):<16} {'ok' if ok else 'FAIL: ' + problems[0][:110]}  ({rec['seconds']} s)")
                records.append(rec)
    finally:
        srv.shutdown()
    return judge(records)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Open every app page of a built site in a phone-sized browser and report what is broken.")
    ap.add_argument("site", help="the built site folder (output of tools/build_web_dashboard.py)")
    ap.add_argument("--out", default=None, help="folder for the screenshots and contact sheets (default: <site>_smoke next to the site)")
    ap.add_argument("--apps", default=None, help="only these apps, comma separated ('root' = the root page)")
    ap.add_argument("--json", default=None, help="also write the full records here")
    ap.add_argument("--timeout", type=int, default=40, help="seconds per app (default 40)")
    ap.add_argument("--query", default=QUERY)
    a = ap.parse_args(argv)
    site = os.path.abspath(a.site)
    if not os.path.isdir(site) or not discover(site):
        print(f"site_smoke: {site} is not a built site (no index.html found)")
        return 2
    out = os.path.abspath(a.out or site.rstrip("/\\") + "_smoke")
    results = run(site, out, a.apps, a.timeout, a.query)
    sheets = contact_sheets([(name_of(r["app"]), r.get("shot") or "", r["ok"]) for r in results], out)
    s = summary(results)
    print()
    print("\n".join(table_lines(results)))
    print()
    print(f"{s['ok']} of {s['pages']} pages ok, {s['failed']} failed, {s['with_warnings']} ok with warnings. Screenshots: {out} ({len(sheets)} contact sheets)")
    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump({"v": 1, "site": site, "query": a.query, "viewport": [W, H], "summary": s, "sheets": sheets, "results": results}, fh, indent=1)
    if s["failed"]:
        print("FAILED: " + ", ".join(s["failed_apps"]))
    return 1 if s["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
