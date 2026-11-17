"""Screenshots of the Bot Brain (PC dashboard tabs at 1440 and 390 px wide, the phone app's Brain page at 390 px) with a
console-error check. Needs Playwright + Chromium and a running dashboard server.

    python -X utf8 -m tests.shots_brain --pc http://127.0.0.1:8766 --out <dir>
    python -X utf8 -m tests.shots_brain --phone <dir with index.html + data.json> --out <dir>
    python -X utf8 -m tests.shots_brain --phone-demo --out <dir>     # the All-bots tab on a temp copy of tools/web_public with
                                                                      # a demo data.json (fresh, then 45 min old = red); checks the DOM

Exit code 1 when a page logs a console error or fails to draw the Brain.
"""
from __future__ import annotations

import argparse
import functools
import http.server
import os
import sys
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _launch(p):
    """Chromium for Playwright; falls back to any chromium under PLAYWRIGHT_BROWSERS_PATH when the bundled build is missing."""
    try:
        return p.chromium.launch()
    except Exception:
        import glob
        root = os.environ.get("PLAYWRIGHT_BROWSERS_PATH", "/opt/pw-browsers")
        for exe in sorted(glob.glob(os.path.join(root, "chromium-*", "chrome-linux", "chrome")), reverse=True):
            return p.chromium.launch(executable_path=exe)
        raise


# errors of this sandbox, not of the page: external CDNs (Chart.js, fonts) are unreachable, so the Today page's charts fail
ENV_ERR = ("ERR_TUNNEL_CONNECTION_FAILED", "ERR_NAME_NOT_RESOLVED", "ERR_INTERNET_DISCONNECTED", "Chart is not defined",
           "Failed to load resource")


def _real(text):
    return not any(k in text for k in ENV_ERR)


TABS = ["now", "levels", "setups", "sizing", "trade", "guards", "log", "replay"]


def pc_shots(base, out, errors):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        br = _launch(p)
        for w, h in ((1440, 1000), (390, 844)):
            ctx = br.new_context(viewport={"width": w, "height": h}, device_scale_factor=1)
            pg = ctx.new_page()
            pg.on("console", lambda m, w=w: errors.append(f"pc {w}: {m.text}") if m.type == "error" and _real(m.text) else None)
            pg.on("pageerror", lambda e, w=w: errors.append(f"pc {w} pageerror: {e}") if _real(str(e)) else None)
            pg.add_init_script("localStorage.setItem('page', 'brain'); localStorage.setItem('nx.page', 'brain');")
            pg.goto(base + "/?fxfixed", wait_until="domcontentloaded")
            pg.wait_for_timeout(1500)
            pg.evaluate("() => { const a = document.querySelector('[data-page=\"brain\"], [data-goto=\"brain\"]'); if (a) a.click(); }")
            pg.wait_for_selector("#page-brain.active .bb-tabs", timeout=20000)
            # the live Brain arrives with the first /api/next/brain answer (the server may still be busy with its boot)
            pg.wait_for_function("() => document.querySelector('#page-brain .bb-wait, #page-brain .nx-empty-hub h3') && "
                                 "!/Loading/.test(document.querySelector('#page-brain .nx-empty-hub h3')?.textContent || '')", timeout=90000)
            for tab in TABS:
                pg.evaluate(f"() => document.querySelector('#bbTab button[data-v=\"{tab}\"]').click()")
                if tab == "replay":
                    pg.wait_for_selector("#bbRange", timeout=60000)
                    pg.wait_for_selector("#bbRView", timeout=60000)
                else:
                    pg.wait_for_timeout(400)
                pg.wait_for_timeout(600)
                ok = pg.evaluate("() => !!document.querySelector('#page-brain .bb-tabs') && !/Could not draw/.test(document.querySelector('#page-brain').innerText)")
                if not ok:
                    errors.append(f"pc {w}: tab {tab} did not draw")
                path = os.path.join(out, f"pc_brain_{tab}_{w}.png")
                pg.screenshot(path=path, full_page=(w == 390 or tab in ("setups", "levels")))
                print("shot", path)
            if w == 1440:                    # the scrubber: one step back, then a log line jump
                pg.evaluate("() => document.querySelector('#bbPrev').click()")
                pg.wait_for_timeout(1500)
                pg.screenshot(path=os.path.join(out, "pc_brain_replay_scrub_1440.png"))
            ctx.close()
        br.close()


def phone_shots(root, out, errors):
    from playwright.sync_api import sync_playwright
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=root)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        with sync_playwright() as p:
            br = _launch(p)
            ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, service_workers="block")
            pg = ctx.new_page()
            pg.route("**/api.github.com/**", lambda r: r.abort())
            pg.route("**/raw.githubusercontent.com/**", lambda r: r.abort())
            pg.on("console", lambda m: errors.append(f"phone: {m.text}") if m.type == "error" and _real(m.text) else None)
            pg.on("pageerror", lambda e: errors.append(f"phone pageerror: {e}") if _real(str(e)) else None)
            for sub in ("now", "levels", "setups", "log"):
                pg.goto(f"{base}/index.html?fxfixed#/brain", wait_until="domcontentloaded")
                pg.wait_for_selector(".bz-tabs", timeout=30000)
                pg.evaluate(f"() => {{ const b = document.querySelector('#brTab button[data-v=\"{sub}\"]'); if (b) b.click(); }}")
                pg.wait_for_timeout(700)
                path = os.path.join(out, f"phone_brain_{sub}_390.png")
                pg.screenshot(path=path, full_page=True)
                print("shot", path)
            pg.goto(f"{base}/index.html?fxfixed#/today", wait_until="domcontentloaded")
            pg.wait_for_timeout(2500)
            pg.screenshot(path=os.path.join(out, "phone_home_390.png"))
            br.close()
    finally:
        srv.shutdown()


def demo_data(now, age_s):
    """A data.json with the PC's glance (engine/brain_glance shape), BLITZ planted to prove it never shows, a tag in a text."""
    g = {"v": 1, "t": now - age_s, "bots": [
        {"id": "lit", "name": "Zlarior", "what": "LIT · MFFU Builder 50K", "on": True, "armed": True, "mode": "LIVE", "stage": "Limit armed (6/10)",
         "wait": "SHORT limit armed at 30,754.75 until 06:15 ET: waiting for price to pull back to it.",
         "why": "09:35 LONG setup, no trade: sweep 0.31 ATR deep (needs >= 0.5 ATR) <img src=x onerror=alert(1)>",
         "lv": [["NY 08-09 high", 30790.25, 35.5], ["Asia low", 30612.0, -142.75]],
         "arm": [{"side": "SHORT", "text": "stop 30,773.75 · target 30,602.75 (8.0R)",
                  "trig": "Enters if price comes back to 30,754.75 before 06:15 ET, then a 1-minute close back its way."}],
         "pos": {"side": "SHORT", "qty": 6, "entry": 30754.75, "stop": 30773.75, "target": 30602.75, "risk_usd": 228, "tgt_usd": 1824, "now_usd": 96},
         "day": 96, "room": 1145, "mll": 2000, "log": [["06:02", "Limit armed at 30,754.75"], ["05:55", "5m CISD down closed"]]},
        {"id": "atlas", "name": "ATLAS", "what": "EMA · MACD · S/R · MFFU Builder 25K", "on": True, "armed": True, "mode": "LIVE",
         "wait": "MACD: waiting for its 09:30 window", "day": 0, "room": 822, "mll": 1000},
        {"id": "blitz", "name": "BLITZ", "what": "hidden", "on": True}]}
    return {"live": {"pc": {"present": True, "running": True, "t": now - age_s, "age_s": age_s, "glance": g},
                     "reporter": {"t": now - 60, "server": True}}}


def phone_demo(out, errors):
    """The All-bots tab on a temp site: every bot card, no BLITZ, the open trade's $, the PC age, red when stale, text as text."""
    import json
    import shutil
    import tempfile
    import time
    from playwright.sync_api import sync_playwright
    src = os.path.join(ROOT, "tools", "web_public")
    tmp = tempfile.mkdtemp(prefix="brain_demo_")
    try:
        site = os.path.join(tmp, "site")
        shutil.copytree(src, site, ignore=shutil.ignore_patterns("*.png", "*.jpg", "*.mp4", "*.webm", "*.glb"))
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=site)
        srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{srv.server_address[1]}"
        try:
            with sync_playwright() as p:
                br = _launch(p)
                for name, age in (("fresh", 120), ("stale", 45 * 60)):
                    with open(os.path.join(site, "data.json"), "w", encoding="utf-8") as fh:
                        json.dump(demo_data(int(time.time()), age), fh)
                    ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, service_workers="block")
                    pg = ctx.new_page()
                    for pat in ("**/api.github.com/**", "**/raw.githubusercontent.com/**", "**/ntfy.sh/**", "**/status_feed.json*", "**/home.json*"):
                        pg.route(pat, lambda r: r.abort())
                    pg.on("console", lambda m: errors.append(f"demo: {m.text}") if m.type == "error" and _real(m.text) else None)
                    pg.on("pageerror", lambda e: errors.append(f"demo pageerror: {e}") if _real(str(e)) else None)
                    pg.on("dialog", lambda d: (errors.append("demo: a dialog opened (text was run as HTML)"), d.dismiss()))
                    pg.goto(f"{base}/index.html?fxfixed#/brain", wait_until="domcontentloaded")
                    pg.wait_for_selector(".bz-all .bzb", timeout=30000)
                    pg.wait_for_timeout(600)
                    r = pg.evaluate("""() => ({bots: [...document.querySelectorAll('.bz-all .bzb')].map(e => e.dataset.bot),
                        fresh: document.querySelector('.bzf').className, big: document.querySelector('.bzf-big').textContent,
                        text: document.querySelector('.bz-all').textContent, img: document.querySelectorAll('.bz-all img').length,
                        wide: document.documentElement.scrollWidth})""")
                    want_bad = name == "stale"
                    if r["bots"] != ["lit", "atlas"]:
                        errors.append(f"demo {name}: bot cards {r['bots']} (want lit, atlas; never blitz)")
                    if ("bad" in r["fresh"]) != want_bad or "PC last reported" not in r["big"]:
                        errors.append(f"demo {name}: freshness box {r['fresh']!r} {r['big']!r}")
                    for need in ("$228", "$1,824", "Room left", "$1,145 of $2,000", "Enters if price comes back to", "Last thoughts",
                                 "Levels it watches today", "ARMED"):
                        if need not in r["text"]:
                            errors.append(f"demo {name}: '{need}' missing")
                    if r["img"] or "<img src=x" not in r["text"]:
                        errors.append(f"demo {name}: a text was not shown as plain text")
                    if r["wide"] > 390:
                        errors.append(f"demo {name}: the page scrolls sideways ({r['wide']} px)")
                    path = os.path.join(out, f"phone_brain_all_{name}_390.png")
                    pg.screenshot(path=path, full_page=True)
                    print("shot", path)
                    ctx.close()
                br.close()
        finally:
            srv.shutdown()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pc")
    ap.add_argument("--phone")
    ap.add_argument("--phone-demo", action="store_true")
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    os.makedirs(a.out, exist_ok=True)
    errors: list = []
    if a.pc:
        pc_shots(a.pc.rstrip("/"), a.out, errors)
    if a.phone:
        phone_shots(a.phone, a.out, errors)
    if a.phone_demo:
        phone_demo(a.out, errors)
    for e in errors:
        print("ERROR", e)
    print("console errors:", len(errors))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
