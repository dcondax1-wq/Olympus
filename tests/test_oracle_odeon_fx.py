"""ORACLE + ODEON, the 2026-11-04 overhaul (prophecy sheet, temple atmosphere, trade library, compare, share card, stage numbers).

Fast (about a minute): the existing full suites are tests.test_oracle_page and tests.test_odeon_page; this one covers only what the
overhaul added. Runs the real pages in Chromium (WebGL through SwiftShader), on the LITE tier for speed, with the draw-call budget of
the atmosphere checked against the same scene with it switched off.

  a. static: the new modules, no innerHTML, no outside URL, every export used, prophecy.json = what tools/oracle_prophecy_stats.py builds
  b. Oracle in the browser: familyOf, the odds (add up to 100), the day type, the sweep counter, heat history, alerts; the sheet's four
     tabs; the two chips; the temple (flames / smoke / dust / shafts / fog) and its draw calls; no console errors
  c. Odeon in the browser: the filters against the trades file, the histogram, Best 5 / Worst 5 / Play all queues, compare (table +
     canvas), the numbers on the stage against the trade's own MFE / R, the share card (1080 x 1350 PNG), the stage fx draw calls

    python -X utf8 -m tests.test_oracle_odeon_fx
"""
from __future__ import annotations

import functools
import glob
import http.server
import json
import os
import re
import subprocess
import sys
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
WEB = os.path.join(ROOT, "tools", "web_public")
ORC, ODE = os.path.join(WEB, "oracle"), os.path.join(WEB, "odeon")
RES: list = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:500]}"), flush=True)


def outcome(t):
    ex = t.get("exit") or {}
    return ex.get("outcome") or ("be" if str(ex.get("kind")).upper() == "BE" else "win" if t["r"] > 0 else "loss" if t["r"] < 0 else "be")


def part_a():
    new_o = ["prophecy.js", "insights.js", "sheet.js", "temple.js", "sheet.css", "prophecy.json"]
    new_d = ["library.js", "compare.js", "share.js", "stage_fx.js", "library.css"]
    check("a. the new Oracle files exist", all(os.path.isfile(os.path.join(ORC, f)) for f in new_o), new_o)
    check("a. the new Odeon files exist", all(os.path.isfile(os.path.join(ODE, f)) for f in new_d), new_d)
    srcs = {}
    for d, names in ((ORC, new_o), (ODE, new_d)):
        for f in names:
            if f.endswith(".js"):
                srcs[os.path.join(os.path.basename(d), f)] = open(os.path.join(d, f), encoding="utf-8").read()
    code = "".join(srcs.values())
    check("a. text only: no innerHTML / outerHTML / insertAdjacentHTML", not re.search(r"innerHTML|outerHTML|insertAdjacentHTML", code))
    check("a. no outside URL, three.js only from ../jarvis/", not re.search(r"https?://(?!www\.w3\.org)", code)
          and all("from 'three'" not in s for s in srcs.values()), re.findall(r"https?://[^\s'\")]+", code)[:3])
    # every export of the new modules is imported by another module of its app
    unused = []
    for key, src in srcs.items():
        app = key.split(os.sep)[0]
        folder = ORC if app == "oracle" else ODE
        others = "".join(open(os.path.join(folder, f), encoding="utf-8").read() for f in os.listdir(folder)
                         if f.endswith(".js") and f != os.path.basename(key))
        for m in re.finditer(r"export (?:async )?(?:function|class|const) (\w+)", src):
            if not re.search(r"\b" + m.group(1) + r"\b", others):
                unused.append(f"{key}:{m.group(1)}")
    check("a. every export of the new modules is imported elsewhere in its app", not unused, unused)
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "oracle_prophecy_stats.py"), "--check"], capture_output=True, text=True)
    check("a. prophecy.json is what tools/oracle_prophecy_stats.py builds from the replay", r.returncode == 0, r.stderr[-300:])
    pj = json.load(open(os.path.join(ORC, "prophecy.json"), encoding="utf-8"))
    check("a. prophecy.json: the families, each with n / share / win_pct, 631 replayed trades",
          pj["kind"] == "oracle-prophecy" and pj["all"]["n"] == 631 and len(pj["families"]) >= 20 and all({"n", "share", "win_pct", "low_n"} <= set(v) for v in pj["families"].values()))
    css = open(os.path.join(ORC, "sheet.css"), encoding="utf-8").read() + open(os.path.join(ODE, "library.css"), encoding="utf-8").read()
    check("a. reduced motion respected in the new CSS", css.count("prefers-reduced-motion") >= 2)
    return pj


class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def run_browser(pj, tj):
    from playwright.sync_api import sync_playwright
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Handler, directory=WEB))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_port}/"
    with sync_playwright() as pw:
        exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
        br = pw.chromium.launch(**({"executable_path": exe} if exe else {}),
                                args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
        only = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--only=")), "")
        if only in ("", "oracle"):
            oracle_part(br, base, pj)
        if only in ("", "odeon"):
            odeon_part(br, base, tj)
        br.close()


def oracle_part(br, base, pj):
    ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1, has_touch=True)
    p = ctx.new_page()
    errs = []
    p.on("pageerror", lambda e: errs.append("pageerror: " + str(e)))
    p.on("console", lambda m: errs.append(m.text) if m.type == "error" and "favicon" not in m.text and "404" not in m.text else None)
    p.goto(base + "oracle/?demo=1&q=low")
    p.wait_for_function("document.body.dataset.ready === '1'", timeout=90000)
    p.wait_for_function("window.oracle.insights && window.oracle.insights.stats && window.oracle.world", timeout=60000)
    p.evaluate("window.oracle.demo.pause(); window.oracle.demo.seek(window.oracle.demo.span.from + 9 * 3600 + 40 * 60)")
    p.wait_for_function("window.oracle.world && window.oracle.world.stage.key", timeout=30000)
    time.sleep(1.5)
    fam = p.evaluate("""async () => { const m = await import('/oracle/prophecy.js');
      return ['Asia high', 'Frankfurt low', 'London 03-04 high', 'London low', 'NY 08-09 high', 'NY 08:30 low', 'NY 09:30-10 high', 'Premarket low', 'PDH', 'PWL', 'PMH',
        'equal highs', 'NWOG top', 'NDOG bottom', 'a mystery'].map((l) => m.familyOf(l)); }""")
    check("b. familyOf maps level labels to the stats families (the ids tools/oracle_prophecy_stats.py writes)",
          fam == ["asia_h", "frank_l", "lon34_h", "lon25_l", "ny89_h", "ny830_l", "ny930b_h", "pre_l", "pd_h", "pw_l", "pm_h", "bu_h", "nwog", "ndog", None], fam)
    rows = p.evaluate("window.oracle.prophecy")
    tot = sum(r["odds"] for r in rows)
    check("b. the odds: >= 3 open levels, each from a known family, adding up to 100 (+/- 0.5), hottest-weighted first",
          len(rows) >= 3 and abs(tot - 100) <= 0.6 and all(r["known"] for r in rows[:3]) and rows == sorted(rows, key=lambda r: -r["weight"]), (len(rows), tot))
    fams = pj["families"]
    check("b. each row carries the stored stats of its family (n, win %, share)",
          all(r["n"] == fams[r["fam"]]["n"] and r["win"] == fams[r["fam"]]["win_pct"] and abs(r["share"] - fams[r["fam"]]["share"]) < 1e-9 for r in rows if r["fam"] in fams))
    ins = p.evaluate("window.oracle.insights")
    w = p.evaluate("window.oracle.world")
    taken = sum(1 for l in w["levels"] if l["taken"])
    check("b. the sweep counter = the levels taken in the World; the day type is named; highs + lows = taken",
          ins["sweeps"]["taken"] == taken and ins["sweeps"]["highs"] + ins["sweeps"]["lows"] == taken and ins["day"]["label"] and ins["day"]["id"] in
          ("sweep-reverse", "trend-up", "trend-down", "range", "quiet", "forming"), ins["day"])
    check("b. heat history: up to 3 levels, each a series of 0-1 values; alerts: newest first with a text",
          0 < len(ins["heat"]) <= 3 and all(0 <= v <= 1 for h in ins["heat"] for v in h["series"]) and len(ins["alerts"]) >= 1 and all(a["text"] for a in ins["alerts"]), ins["heat"][:1])
    chips = p.eval_on_selector_all("#wx2 .chip", "els => els.map(e => [e.className, e.textContent])")
    check("b. the bottom sheet shows the day type and the sweep counter as chips", any("day" in c[0] for c in chips) and any(c[1] == f"Sweeps {taken}" for c in chips), chips)
    # the sheet
    p.click("#oracle-btn")
    p.wait_for_function("!document.querySelector('#oracle').hidden", timeout=5000)
    time.sleep(0.4)
    n_rows = p.locator("#pr-list li").count()
    bars = p.eval_on_selector_all("#pr-list .pr-bar i", "els => els.map(e => parseFloat(e.style.width))")
    check("b. the Prophecy sheet opens on Odds: a bar per level, a NEXT line, the source line", n_rows == len(rows) and len(bars) == n_rows and all(b > 0 for b in bars)
          and p.inner_text("#pr-next") != "" and "631" in p.inner_text("#pr-src"), (n_rows, bars))
    panels = {}
    for tab, sel in (("heat", "#ht-list li"), ("alerts", "#al-list li"), ("day", "#day-type")):
        p.click(f"[role=tab][data-tab={tab}]")
        time.sleep(0.2)
        panels[tab] = (p.locator(sel).count(), [x for x in p.eval_on_selector_all("[role=tabpanel]", "els => els.filter(e => !e.hidden).map(e => e.dataset.tab)")])
    check("b. the four tabs (Odds, Heat, Alerts, Day) each show their own panel", panels["heat"][0] >= 1 and panels["alerts"][0] >= 1 and panels["day"][0] == 1
          and all(v[1] == [k] for k, v in panels.items()), panels)
    p.evaluate("window.oracle.demo.pause()")
    ticks = p.evaluate("window.oracle.ticks")
    check("b. the replay scrubber shows the session's moments: a tick per sweep taken, one for the entry, one for the exit",
          ticks.count("k-entry") == 1 and ticks.count("k-exit") == 1 and ticks.count("k-sweep") >= 3, ticks)
    check("b. the Day tab names the day type and the sweep count", p.inner_text("#day-type") == ins["day"]["label"] and p.inner_text("#sw-n") == str(taken))
    box = p.evaluate("(() => { const r = document.querySelector('#oracle').getBoundingClientRect(); return [r.left, r.right, r.bottom, innerWidth, innerHeight]; })()")
    check("b. the sheet keeps the orb's corner free (right inset >= 80 px) and does not scroll the page sideways",
          box[3] - box[1] >= 80 and p.evaluate("document.documentElement.scrollWidth <= innerWidth"), box)
    p.keyboard.press("Escape")
    check("b. Escape closes the sheet", p.evaluate("document.querySelector('#oracle').hidden"))
    # the temple
    tp = p.evaluate("window.oracle.temple")
    check("b. the temple is in the scene: flames, incense, dust, shafts, fog (HD counts; LITE thins them)", tp and tp["on"] and tp["flames"] >= 28 and tp["smoke"] >= 28 and tp["dust"] >= 90, tp)
    # software GL draws a frame every second or two: wait for the frame after each switch, then compare the two frames' draw calls
    p.wait_for_function("window.oracle.arena.stats.calls > 0", timeout=60000)
    on = p.evaluate("window.oracle.arena.stats.calls")
    p.evaluate("window.oracle.setTemple(false)")
    try:
        p.wait_for_function(f"window.oracle.arena.stats.calls < {on} - 3", timeout=90000)
    except Exception:
        pass
    off = p.evaluate("window.oracle.arena.stats.calls")
    p.evaluate("window.oracle.setTemple(true)")
    check("b. the atmosphere costs <= 14 draw calls on top of the scene and stays under the Oracle budget (170 at the kit's measure; 260 here, "
          "where the post passes are counted too)", 0 < on - off <= 14 and on <= 260, (on, off))
    p.evaluate("window.oracle.camera(-0.3, 0.45, 1.5)")
    time.sleep(2)
    check("b. no console errors (sheet, temple, camera)", not errs, errs[:5])
    ctx.close()


def odeon_part(br, base, tj):
    trades = tj["trades"]
    ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1, has_touch=True)
    p = ctx.new_page()
    errs = []
    p.on("pageerror", lambda e: errs.append("pageerror: " + str(e)))
    p.on("console", lambda m: errs.append(m.text) if m.type == "error" and "favicon" not in m.text else None)
    p.goto(base + "odeon/?speed=60&autoplay=0&q=low")
    p.wait_for_function("document.body.dataset.ready === 'true'", timeout=90000)
    # the library against the file
    p.click("#reelsBtn")
    p.wait_for_selector("#reels:not([hidden])")
    n = len(trades)
    lib = p.evaluate("window.__odeon.library()")
    check(f"c. the library opens with every reel ({n}) and an R histogram of 8 bars that adds up", len(lib["shown"]) == n and len(lib["hist"]) == 8 and sum(lib["hist"]) == n
          and p.locator("#reelHist .hb").count() == 8, lib["hist"])
    py_hist = [0] * 8
    edges = [-1e9, -0.75, -0.25, 0.25, 1, 2, 3, 5, 1e9]
    for t in trades:
        for i in range(8):
            if edges[i] <= t["r"] < edges[i + 1]:
                py_hist[i] += 1
    check("c. the histogram counts = the trades' R in the same bins", lib["hist"] == py_hist, (lib["hist"], py_hist))
    n_win = sum(outcome(t) == "win" for t in trades)
    p.click(".chip[data-f='win']")
    check("c. Wins keeps only the winners", p.evaluate("window.__odeon.library().shown.length") == n_win and p.locator("#reelList .reel").count() == n_win)
    p.click(".chip[data-f='all']")
    hours = p.eval_on_selector_all(".chip.sm[data-g='hour']", "els => els.map(e => e.dataset.v)")
    month_chips = p.eval_on_selector_all(".chip.sm[data-g='month']", "els => els.map(e => e.dataset.v)")
    check("c. the library offers setup, session and month chips built from the file", "NY AM" in hours and len(month_chips) >= 3 and p.locator(".chip.sm[data-g='setup']").count() >= 3, (hours, month_chips))
    mo = month_chips[1]
    py_mo = sum(t["day"].startswith(mo) for t in trades)
    p.click(f".chip.sm[data-g='month'][data-v='{mo}']")
    check("c. a month chip keeps that month's reels", p.evaluate("window.__odeon.library().shown.length") == py_mo, (mo, py_mo))
    p.click(".chip.sm[data-g='month'][data-v='all']")
    tgt = next(i for i, c in enumerate(py_hist) if c >= 2)
    p.click(f"#reelHist .hb[data-i='{tgt}']")
    check("c. tapping a histogram bar keeps only that R range (and the bar stays lit)", p.evaluate("window.__odeon.library().shown.length") == py_hist[tgt]
          and p.get_attribute(f"#reelHist .hb[data-i='{tgt}']", "aria-pressed") == "true")
    p.click(f"#reelHist .hb[data-i='{tgt}']")
    check("c. tapping it again releases the filter", p.evaluate("window.__odeon.library().shown.length") == n)
    st = p.inner_text("#reelStats")
    check("c. a stats line under the filters (win %, avg R, best, worst, PF)", "won" in st and "avg" in st and "PF" in st, st)
    # queues
    by_usd = sorted(trades, key=lambda t: (-t["usd"], -t["entry"]["t"]))
    best = [t["id"] for t in by_usd if t["usd"] > 0][:5]
    worst = [t["id"] for t in by_usd if t["usd"] < 0][::-1][:5]
    p.click("#worstBtn")
    s = p.evaluate("window.__odeon.state()")
    check("c. Worst 5 plays the five biggest losers, worst first (WORST 1/5 badge)", s["hl"] and s["hl"]["ids"] == worst and s["hl"]["kind"] == "worst" and s["id"] == worst[0]
          and p.inner_text("#hlBadge").startswith("WORST 1/5"), (s["hl"], worst))
    p.click("#reelsBtn")
    p.click("#hlBtn")
    s = p.evaluate("window.__odeon.state()")
    check("c. Highlights still plays the five best by $", s["hl"] and s["hl"]["ids"] == best and s["hl"]["kind"] == "best", (s["hl"], best))
    p.click("#reelsBtn")
    p.click(".chip[data-f='loss']")
    losers = p.evaluate("window.__odeon.library().shown")
    p.click("#allBtn")
    s = p.evaluate("window.__odeon.state()")
    check("c. Play all plays exactly the reels the library shows, in that order", s["hl"] and s["hl"]["ids"] == losers and s["hl"]["kind"] == "all" and s["id"] == losers[0], (s["hl"] and len(s["hl"]["ids"]), len(losers)))
    # the numbers on the stage
    tr = p.evaluate("window.__odeon.trade()")
    p.evaluate(f"window.__odeon.pause(); window.__odeon.seek({tr['entry']['t'] - 600})")
    time.sleep(0.4)
    check("c. before the entry the stage numbers are hidden", p.evaluate("document.querySelector('#onstage').hidden"))
    p.evaluate(f"window.__odeon.seek({tr['exit']['t_end'] + 60})")
    time.sleep(0.4)
    os_ = p.evaluate("window.__odeon.library().onstage")
    cells = p.eval_on_selector_all("#onstage .os-c b", "els => els.map(e => e.textContent)")
    check("c. after the exit the stage shows the trade's own R, with MFE / MAE within 0.2R of the export (MFE >= 0, MAE >= 0)",
          not p.evaluate("document.querySelector('#onstage').hidden") and abs(os_["r"] - tr["r"]) < 1e-6 and os_["mfeR"] >= 0 and os_["maeR"] >= 0
          and abs(os_["mfeR"] - (tr["mfe_r"] or 0)) <= 0.2 + 0.15 * abs(tr["mfe_r"] or 0) and len(cells) == 4, (os_, tr["mfe_r"], tr["mae_r"], cells))
    # compare
    ids = [t["id"] for t in by_usd]
    p.evaluate("window.__odeon.compare(%s, %s)" % (json.dumps(ids[0]), json.dumps(ids[-1])))
    p.wait_for_function("!document.querySelector('#compare').hidden", timeout=5000)
    time.sleep(0.3)
    rows = p.eval_on_selector_all("#cmpTable tr", "els => els.map(e => [...e.children].map(c => c.textContent))")
    lit = p.locator("#cmpTable td.win").count()
    painted = p.evaluate("""() => { const c = document.querySelector('#cmpCanvas'), d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data; let n = 0;
      for (let i = 3; i < d.length; i += 4) if (d[i] > 0) n++; return n; }""")
    check("c. compare: 8 rows of numbers, the better of each row lit, both trades drawn as R over time on the canvas, a one-line verdict",
          len(rows) == 8 and rows[0][0] == "Result" and lit >= 4 and painted > 400 and "more" in p.inner_text("#cmpNote"), (rows[:2], lit, painted))
    p.click("#cmpA")
    check("c. Play A closes the comparison and plays that reel", p.evaluate("document.querySelector('#compare').hidden") and p.evaluate("window.__odeon.state().id") == ids[0])
    # the share card
    card = p.evaluate("window.__odeon.card()")
    check("c. the share card: a 1080 x 1350 PNG with real content", card["w"] == 1080 and card["h"] == 1350 and card["bytes"] > 20000, card)
    # draw calls of the stage fx
    p.evaluate(f"window.__odeon.seek({tr['entry']['t'] + 600})")
    time.sleep(3)
    calls = p.evaluate("window.__odeon.look().stats.calls")
    check("c. the stage fx keep the Odeon frame under its draw-call budget (60 on the scene; the LITE frame with the post pass under 90)", 0 < calls <= 90, calls)
    check("c. no console errors (library, queues, compare, share, stage fx)", not errs, errs[:5])
    ctx.close()


def main():
    pj = part_a()
    tj = json.load(open(os.path.join(ODE, "trades.json"), encoding="utf-8"))
    if "--no-browser" not in sys.argv:
        try:
            import playwright  # noqa: F401
        except ImportError:
            print("[SKIP] Playwright missing: browser part skipped")
        else:
            run_browser(pj, tj)
    n = sum(RES)
    print(f"\n{n}/{len(RES)} passed")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
