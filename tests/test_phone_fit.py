"""Phone fit of the NQ pages (owner 2026-11-20: "make everything cleaner ... quality checks"; he still saw a "funky" bottom on iPhone).
The ZEUS hub (hub/zeus.html), My MFFU accounts (business/mffu.html), Trades & calendar (trading/), the Board (board/) at the two iPhone
sizes the owner uses, 390 x 844 and 430 x 932, dark, with the iPhone's safe areas (top 47 px, the home bar 34 px at the bottom, set
through Chromium's Emulation.setSafeAreaInsetsOverride so env(safe-area-inset-*) is real), fed by one PC status fixture:
  a. no sideways scroll (the page is never wider than the phone)
  b. nothing hidden under the bottom: at the very end of the page the last line of content ends above every bar fixed to the bottom
     (a tab bar, the orb) and above the home bar (env(safe-area-inset-bottom))
  c. no page errors; the ZEUS page shows the Live feed strip and one card per account with its last trades and the open trade
SHOTS=<dir> also saves a phone screenshot of each page (viewport, the top) and of its end (the bottom), for the handoff.
    flock -w 2400 /tmp/olympus_browser.lock python -X utf8 -m tests.test_phone_fit
    SHOTS=research/handoff/2026-11-20/tradealerts SHOT_TAG=after flock -w 2400 /tmp/olympus_browser.lock python -X utf8 -m tests.test_phone_fit
"""
from __future__ import annotations

import functools
import http.server
import json
import os
import sys
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "tools", "web_public")
RES: list = []
SIZES = [(390, 844), (430, 932)]
INSETS = {"top": 47, "bottom": 34}
PAGES = [("zeus", "hub/zeus.html", "window.ZEUS_PAGE && window.ZEUS_PAGE.ready"),
         ("mffu", "business/mffu.html", None),
         ("trading", "trading/", None),
         ("board", "board/", None)]


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:500]}"))


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def lite_fixture(now):
    """A PC core post: Zlarior 50K eval + ATLAS funded 25K (board cards), the 25K #2 eval, every account's newest trades ("at"),
    one open Zlarior trade, the PC's price."""
    d0 = now - 26 * 3600
    tr50 = [[d0 - 86400 * 2, d0 - 86400 * 2 + 1800, 1, 4, 21010.0, 20990.0, 21060.0, "TARGET", 398.1, 2.5],
            [d0 - 86400, d0 - 86400 + 900, -1, 4, 21100.0, 21120.0, 21040.0, "STOP", -163.8, -1.0],
            [d0, d0 + 2100, 1, 4, 21034.25, 21012.0, 21090.5, "TARGET", 446.1, 2.5],
            [now - 3000, None, 1, 4, 21034.25, 21012.0, 21090.5, None, None, None]]
    tr25 = [[d0 + 300, d0 + 1500, 1, 2, 21036.0, 21012.0, 21090.5, "STOP", -97.9, -1.0],
            [now - 2900, now - 1200, 1, 2, 21036.0, 21014.0, 21090.5, "TARGET", 214.1, 2.4]]
    tra = [[d0 - 3600, d0 - 1800, -1, 3, 21050.0, 21070.0, 21010.0, "TARGET", 236.2, 2.0]]
    return {"v": 1, "kind": "le-live", "lite": True, "t": now - 240, "reporter": {"t": now - 240}, "price": 21051.5,
            "board": {"t": now - 240, "data_t": now - 240,
                      "lit": {"name": "Zlarior", "plan": "MFFU Builder 50K", "status": "open", "balance": 49192.78, "floor": 48168.2, "room": 1024.58,
                              "to_target": 3807.22, "today_pnl": 120.0},
                      "atlas": {"name": "ATLAS", "plan": "MFFU Builder 25K", "status": "funded", "stage": "funded", "balance": 25080.0, "floor": 24000.0,
                                "room": 1080.0, "today_pnl": -40.0}},
            "accounts": [{"id": "mffu50k_eval", "kind": "eval", "name": "Zlarior", "plan": "MFFU Builder 50K",
                          "eval": {"balance": 49192.78, "floor": 48168.2, "room": 1024.58, "to_target": 3807.22, "today": 120.0}},
                         {"id": "b25k_2", "kind": "eval", "name": "Zlarior 25K #2", "plan": "MFFU Builder 25K",
                          "eval": {"balance": 25210.0, "floor": 24000.0, "room": 1210.0, "to_target": 1290.0, "today": 210.0}}],
            "at": {"t": now - 240, "a": [{"id": "mffu50k_eval", "l4": "6016", "tr": tr50}, {"id": "b25k_2", "l4": "2222", "tr": tr25},
                                         {"id": "atlas", "l4": "6018", "tr": tra}]},
            "eh": {"d": "2026-11-17", "z": ["G", 3.8, 3.9], "a": ["G", 1.9, 1.8, "2026-11-17"], "t": now - 3600}}


# a. + b.: measured in the page (CSS px). "Fixed to the bottom" = position fixed / sticky, visible, not covering the whole screen, its
# bottom edge in the lowest quarter of the screen. The content = every visible element outside those bars with its own text or a control.
MEASURE = r"""(() => {
  const H = innerHeight, W = innerWidth, de = document.documentElement;
  const vis = (e) => { const s = getComputedStyle(e); return s.display !== 'none' && s.visibility !== 'hidden' && +s.opacity > 0.05; };
  const bars = [];
  for (const e of document.querySelectorAll('body *')) {
    const s = getComputedStyle(e);
    if ((s.position !== 'fixed' && s.position !== 'sticky') || !vis(e)) continue;
    const r = e.getBoundingClientRect();
    if (r.width < 8 || r.height < 8 || r.height > H * 0.6 || r.bottom < H * 0.75 || r.top > H) continue;
    if (s.pointerEvents === 'none' && !e.textContent.trim()) continue;
    bars.push({ el: e, top: r.top, id: (e.id || e.className || e.tagName).toString().slice(0, 40) });
  }
  const inBar = (e) => bars.some((b) => b.el.contains(e));
  let last = 0, lastEl = '';
  for (const e of document.querySelectorAll('main *, body > *:not(script):not(style)')) {
    if (inBar(e) || !vis(e)) continue;
    const shut = e.closest('details:not([open])');
    if (shut && !e.closest('summary')) continue;                 // a closed details' body is not on screen
    const own = [...e.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim()) || /^(A|BUTTON|INPUT|SELECT|IMG|SVG|CANVAS)$/.test(e.tagName);
    if (!own) continue;
    const r = e.getBoundingClientRect();
    if (r.height < 1 || r.width < 1) continue;
    if (r.bottom > last) { last = r.bottom; lastEl = (e.tagName + '.' + e.className).slice(0, 50) + ' ' + e.textContent.trim().slice(0, 30); }
  }
  const sb = parseFloat(getComputedStyle(de).getPropertyValue('--zz-sb')) || 0;
  return { W, H, sw: de.scrollWidth, bw: document.body.scrollWidth, last, lastEl, bars: bars.map((b) => [b.id, Math.round(b.top)]),
           barTop: bars.length ? Math.min(...bars.map((b) => b.top)) : H, sb };
})()"""
WIDE = r"""(() => { const W = innerWidth, out = [];
  for (const e of document.querySelectorAll('body *')) { const r = e.getBoundingClientRect(), s = getComputedStyle(e);
    if (s.position === 'fixed' || r.width < 1) continue;
    let p = e.parentElement, clip = false; while (p && p !== document.body) { const o = getComputedStyle(p).overflowX; if (o === 'auto' || o === 'scroll' || o === 'hidden' || o === 'clip') { clip = true; break; } p = p.parentElement; }
    if (!clip && r.right > W + 1.5) out.push((e.tagName + '.' + e.className).slice(0, 40) + ' ' + Math.round(r.right)); if (out.length > 4) break; }
  return out; })()"""


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:  # noqa: BLE001
        print(f"[SKIP] playwright missing: {e}")
        return 0
    shots = os.environ.get("SHOTS")
    tag = os.environ.get("SHOT_TAG", "now")
    if shots:
        shots = shots if os.path.isabs(shots) else os.path.join(ROOT, shots)
        os.makedirs(shots, exist_ok=True)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=WEB))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}/"
    now = int(time.time())
    msg = json.dumps({"id": "x1", "time": now - 240, "event": "message", "topic": "t", "message": json.dumps(lite_fixture(now))})
    try:
        with sync_playwright() as pw:
            br = pw.chromium.launch(args=["--no-sandbox"])
            for w, h in SIZES:
                ctx = br.new_context(viewport={"width": w, "height": h}, device_scale_factor=2, has_touch=True, is_mobile=True,
                                     color_scheme="dark", reduced_motion="reduce")
                ctx.route("**/ntfy.sh/**", lambda r: r.fulfill(status=200, content_type="application/x-ndjson", body=msg + "\n"))
                for name, path, ready in PAGES:
                    p = ctx.new_page()
                    errs: list = []
                    p.on("pageerror", lambda e, errs=errs: errs.append(str(e)))
                    inset = True
                    try:
                        p.context.new_cdp_session(p).send("Emulation.setSafeAreaInsetsOverride", {"insets": INSETS})
                    except Exception:  # noqa: BLE001  (an older Chromium: no safe areas, the checks still run)
                        inset = False
                    p.goto(base + path, wait_until="load", timeout=60000)
                    if ready:
                        try:
                            p.wait_for_function(ready, timeout=30000)
                        except Exception:  # noqa: BLE001
                            pass
                    p.wait_for_timeout(2500)
                    sb = INSETS["bottom"] if inset else 0
                    if shots:
                        p.screenshot(path=os.path.join(shots, f"{name}_{w}x{h}_{tag}_top.png"))
                        if name == "zeus" and w == SIZES[0][0]:
                            p.screenshot(path=os.path.join(shots, f"{name}_{w}x{h}_{tag}_full.png"), full_page=True)
                    p.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
                    p.wait_for_timeout(600)
                    m = p.evaluate(MEASURE)
                    wide = p.evaluate(WIDE)
                    if shots:
                        p.screenshot(path=os.path.join(shots, f"{name}_{w}x{h}_{tag}_end.png"))
                    check(f"a. {name} {w}x{h}: no sideways scroll (page {m['sw']} px on a {m['W']} px phone)", m["sw"] <= m["W"] + 1 and not wide, (m["sw"], wide))
                    limit = min(m["barTop"], m["H"] - sb)
                    check(f"b. {name} {w}x{h}: the last line ends above the bottom bars and the home bar ({round(m['last'])} <= {round(limit)})",
                          m["last"] <= limit + 0.5, (m["lastEl"], m["bars"], m["H"], sb))
                    check(f"c. {name} {w}x{h}: no page errors", not errs, errs[:3])
                    if name == "zeus":
                        z = p.evaluate("""(() => ({ feed: [...document.querySelectorAll('#feed .zs-ev')].map((e) => e.textContent),
                            cards: [...document.querySelectorAll('.zs-acct')].map((e) => ({ k: e.dataset.key, last: e.querySelectorAll('.zs-tr').length,
                              open: (e.querySelector('.zs-open') || {}).textContent || '' })) }))()""")
                        by = {c["k"]: c for c in z["cards"]}
                        check(f"c. zeus {w}x{h}: Live feed strip (newest entries + exits across accounts) and per-account last trades + the open trade",
                              len(z["feed"]) >= 3 and by.get("zlarior", {}).get("last") == 3 and "LONG 4" in by.get("zlarior", {}).get("open", "")
                              and by.get("fresh25", {}).get("last") == 2, z)
                    p.close()
                ctx.close()
            br.close()
    finally:
        srv.shutdown()
    n, ok = len(RES), sum(RES)
    print(f"\nphone fit: {ok}/{n} " + ("ALL PASS" if ok == n else "FAILED"))
    return 0 if ok == n else 1


if __name__ == "__main__":
    sys.exit(main())
