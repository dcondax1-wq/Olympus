"""Phone screenshots (390 x 844) of the two K8 pages, fed by the dry run's REAL Nov 16-19 paper ledger (research/kalshi_k8_monday/dryrun.py):
  kalshi-live.png   the PC's private page (engine/kalshi_web.PAGE), its /status from kalshi_web.status_view on that ledger (the key
                    shown as checked with a $55 balance: the Monday picture, no real key)
  kalshi-page.png   the public Kalshi page (tools/web_public/kalshi/) with the PC card (engine/kalshi_live.read_card on that ledger)
Run under the browser lock:  flock -w 2400 /tmp/olympus_browser.lock python research/kalshi_k8_monday/shots.py
"""
from __future__ import annotations

import functools
import http.server
import json
import os
import sys
import tempfile
import threading

import k8m_data as D

sys.path.insert(0, D.ROOT)
sys.path.insert(0, os.path.join(D.ROOT, "tests"))
from engine import kalshi_clock as KC, kalshi_live as KL, kalshi_web as KW  # noqa: E402
import dryrun  # noqa: E402
import browser_kit as BK  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

OUT = os.path.join(D.ROOT, "research", "handoff", "2026-11-20", "kalshi8")


def main():
    os.makedirs(OUT, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="k8shot-")
    w, _, cfg = dryrun.run("paper", tmp)
    w.clock.t = KC.et_epoch(dryrun.DAYS[-1], 21, 40)               # Thu Nov 19, 9:40 PM ET (tonight)
    KW._S.update(state_dir=w.sd, env=w.env, http=w.fake, clock=w.clock, spawn=lambda sd: 0)
    st = KW.status_view()
    st["key"] = {"saved": True, "ok": True, "balance": 55.0, "checked": st["t"], "why": None}
    st["bankroll"] = dict(st["bankroll"], balance=55.0, rule=KC.bankroll_rule(55), fits=True)
    st["warn"] = ""
    st["loop"] = True
    card = KL.read_card(now=w.clock(), state_dir=w.sd)
    ext = json.dumps({"event": "message", "time": 1, "message": json.dumps({"kind": "le-live-ext", "t": int(w.clock()), "part": 0, "of": 1,
                                                                               "x": {"kalshi_live": card}})}) + "\n"
    site = os.path.join(D.ROOT, "tools", "web_public")
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(http.server.SimpleHTTPRequestHandler, directory=site))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    with sync_playwright() as pw:
        br = BK.launch(pw)
        ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, color_scheme="dark")
        p = ctx.new_page()
        p.route("**/kalshi-live/status", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(st)))
        p.route("**/kalshi-live/", lambda r: r.fulfill(status=200, content_type="text/html", body=KW.PAGE))
        p.goto(base + "/kalshi-live/")
        p.wait_for_function("document.querySelector('#st .chips') !== null", timeout=20000)
        p.wait_for_timeout(1200)
        p.screenshot(path=os.path.join(OUT, "kalshi-live.png"))
        p.screenshot(path=os.path.join(OUT, "kalshi-live-full.png"), full_page=True)
        p2 = ctx.new_page()
        p2.route("**/status_feed.json", lambda r: r.fulfill(status=200, content_type="application/json",
                                                            body=json.dumps({"topic": "k8demo", "ntfy": "https://ntfy.example"})))
        p2.route("https://ntfy.example/**", lambda r: r.fulfill(status=200, content_type="application/x-ndjson", body=ext))
        p2.goto(base + "/kalshi/")
        p2.wait_for_function("document.querySelectorAll('#k8s .k8s-l span').length > 0", timeout=30000)
        p2.wait_for_timeout(1500)
        p2.evaluate("document.getElementById('kpaused').scrollIntoView({block: 'start'}); window.scrollBy(0, -70)")
        p2.wait_for_timeout(500)
        p2.screenshot(path=os.path.join(OUT, "kalshi-page.png"))
        geo = p2.evaluate("""() => { const W = window.innerWidth, de = document.documentElement, e = document.getElementById('k8s'), r = e.getBoundingClientRect();
            return {noSideScroll: de.scrollWidth <= de.clientWidth, inGutter: r.left >= 15.5 && r.right <= W - 15.5}; }""")
        geo2 = p.evaluate("() => ({noSideScroll: document.documentElement.scrollWidth <= document.documentElement.clientWidth})")
        print("kalshi page", geo, "live page", geo2, "card bytes", len(json.dumps(card, separators=(",", ":"))))
        ctx.close()
    srv.shutdown()
    json.dump({"card": card, "status_keys": sorted(st)}, open(os.path.join(OUT, "shots.json"), "w"), indent=1, default=str)


if __name__ == "__main__":
    main()
