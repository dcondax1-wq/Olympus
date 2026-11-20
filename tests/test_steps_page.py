"""Your steps (tools/web_public/hub/steps.html + steps.js + steps.json, 2026-11-20, night-ownersteps).
  a. steps.json is valid; every item has where / what / why / steps / a copy line; no private ids, addresses or tailnet names
  b. help.json lists the page; the page uses textContent only
  c. Chromium 390 x 844 (browser lock): loads with no console errors, 6 cards, Copy works, Done tick saved + survives reload, no sideways scroll
    python -X utf8 -m tests.test_steps_page     (STEPS_NO_BROWSER=1 skips c; run c only under flock -w 2400 /tmp/olympus_browser.lock)
"""
from __future__ import annotations

import functools
import glob
import http.server
import json
import os
import re
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HUB = os.path.join(ROOT, "tools", "web_public", "hub")
WEB = os.path.dirname(HUB)
RES: list = []
PRIVATE = re.compile(r"ts\.net|tailscale\.net|@[A-Za-z0-9-]+\.[a-z]{2,}|dcondax1|demetrades|\b100\.\d{1,3}\.\d{1,3}\.\d{1,3}\b|\b[A-Z]{3,6}\d{8,}\b|MFFUEVRPD|\bPA-?\d{4,}", re.I)


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:400]}"))


def rd(n):
    with open(os.path.join(HUB, n), encoding="utf-8") as f:
        return f.read()


def part_a():
    raw = rd("steps.json")
    data = json.loads(raw)
    items = data["items"]
    check("a. steps.json valid, 8 items, ids unique, numbered 1..8", len(items) == 8 and len({i["id"] for i in items}) == 8
          and [i["n"] for i in items] == list(range(1, 9)), [i.get("id") for i in items])
    bad = [i["id"] for i in items if not (i.get("where") in ("PC", "Phone") and i.get("title") and i.get("what") and i.get("why")
                                          and i.get("copy") and 2 <= len(i.get("steps") or []) <= 4)]
    check("a. every item: where (PC/Phone), what, why, 2-4 steps, a copy line", not bad, bad)
    check("a. no private ids, emails, tailnet names or IPs in steps.json / steps.html / steps.js",
          not PRIVATE.search(raw + rd("steps.html") + rd("steps.js")), PRIVATE.findall(raw))
    ids = {i["id"]: i for i in items}
    check("a. facts: phrases, min-room line, 4:44 PM, $2.50, 02:00-15:30",
          "I ACCEPT LIVE RISK" in ids["rapid-add"]["copy"] and ids["atlas-room"]["copy"] == "python -X utf8 -m engine.account_b --min-room 0"
          and "I ACCEPT KALSHI LIVE RISK" in ids["kalshi-live"]["copy"] and "4:44" in ids["kalshi-live"]["title"] and "$2.50" in raw
          and "02:00" in ids["pc-on"]["title"] and "15:30" in ids["pc-on"]["title"])
    h = json.loads(rd("help.json"))
    check("b. help.json lists 'steps' linking to steps.html", any(i["id"] == "steps" and i["link"]["href"] == "steps.html" for i in h["items"]))
    js = rd("steps.js")
    check("b. steps.js: textContent only (no innerHTML), localStorage in try/catch", "innerHTML" not in js and "try {" in js and "localStorage" in js)


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def part_c():
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:  # noqa: BLE001
        print(f"[SKIP] c. browser (playwright missing: {e})")
        return
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=WEB))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}/hub/steps.html"
    try:
        with sync_playwright() as pw:
            exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
            br = pw.chromium.launch(**({"executable_path": exe} if exe else {}))
            ctx = br.new_context(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True)
            ctx.route(re.compile(r"^https?://(?!127\.0\.0\.1)"), lambda r: r.fulfill(status=204, body=""))
            errs: list = []
            p = ctx.new_page()
            p.set_default_timeout(30000)
            p.on("pageerror", lambda e: errs.append(str(e)))
            p.on("console", lambda m: errs.append(m.text) if m.type == "error" and "ERR_" not in m.text and "404" not in m.text else None)
            p.goto(url)
            p.wait_for_function("window.STEPS_PAGE && window.STEPS_PAGE.ready")
            n = p.eval_on_selector_all(".st-card", "e => e.length")
            cnt = p.text_content("#count")
            check("c. 390 px: 8 cards, '8 to do, 0 done'", n == 8 and cnt.strip() == "8 to do, 0 done", (n, cnt))
            p.click("#rapid-add .st-copy button")
            p.wait_for_timeout(200)
            check("c. Copy answers (Copied / Selected)", p.text_content("#rapid-add .st-copy button") in ("Copied", "Selected"))
            p.check("#rapid-add .st-done input")
            check("c. Done tick: card dimmed, count '7 to do, 1 done'", p.text_content("#count").strip() == "7 to do, 1 done"
                  and p.evaluate("document.getElementById('rapid-add').classList.contains('is-done')"))
            p.reload()
            p.wait_for_function("window.STEPS_PAGE && window.STEPS_PAGE.ready")
            check("c. the tick survives a reload (localStorage)", p.is_checked("#rapid-add .st-done input"))
            wide = p.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
            small = p.evaluate("[...document.querySelectorAll('.st-nav a, .st-copy button, .st-done')].map(e => e.getBoundingClientRect()).filter(r => r.width > 0 && (r.height < 44 || r.width < 44)).length")
            check("c. no sideways scroll, every tap >= 44 px", wide and small == 0, (wide, small))
            check("c. no console / page errors", not errs, errs)
            br.close()
    finally:
        srv.shutdown()


def main():
    part_a()
    if not os.environ.get("STEPS_NO_BROWSER"):
        part_c()
    n = sum(RES)
    print(f"\nsteps_page: {n}/{len(RES)} " + ("ALL PASS" if n == len(RES) else "FAILED"))
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    raise SystemExit(main())
