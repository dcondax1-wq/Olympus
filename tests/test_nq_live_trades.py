"""NQ LIVE TRADES (night-nq-live 2026-11-27, owner 00:00 ET: "the NQ dashboard still looks poorly done ... make everything better,
3D, higher quality, effects, features"). tools/web_public/nq/live.html + live.js + livecore.js + live.css: an open-trade card per
account (entry, stop, target, R, $ now, time in trade, a stop -> entry -> target bar with the price on it), today's session timeline,
the trade journal (the last 30 closed real trades: $, R, why, entry quality = slip ticks from the PC's fill check "fq"), the win / loss
streak, a one-time pulse on a new fill, honest "no trade open" / no-data states, BLITZ hidden.

  a. static: the new blocks exist, OLYMPUS NIGHT only (no cyan), reduced motion stops the effects, still read only / no storage
  b. node (livecore.js on the REAL PC post of 2026-11-22 + an open LIT long on 2 accounts + closed trades + fq fill checks + a BLITZ row)
  c. browser (node Playwright, ntfy mocked): 390x844 + 1440x900, in a trade / flat, taps >= 44 px, no sideways scroll, no console error,
     a new closed trade on the next poll pulses once. --shots -> research/handoff/2026-11-27/night-nq-live/shots/ (after-*.png)
     --before <web root> -> before-*.png of another copy of the site (the version on origin/pc)
Run: python -X utf8 -m tests.test_nq_live_trades [--shots] [--before DIR]
"""
from __future__ import annotations

import copy
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tests import agora_kit as AK  # noqa: E402
from tests import test_nq_live as NL  # noqa: E402

check = AK.check
NQ = NL.NQ
SHOTS = os.path.join(ROOT, "research", "handoff", "2026-11-27", "night-nq-live", "shots")
et = NL.et
NOW, ENTRY_T = NL.NOW, NL.ENTRY_T


def journal_post(t=NL.T, extra_closed=False):
    """the trade post + closed trades of the last days on the 50K and ATLAS, the PC's fill checks, and a BLITZ row (must stay hidden)"""
    p = NL.trade_post(t=t)
    rows = p["at"]["a"]
    z = next(a for a in rows if a["id"] == "mffu50k_eval" and any(r[1] is None for r in a["tr"]))
    z["tr"] += [[et(2026, 11, 23, 3, 40), et(2026, 11, 23, 4, 30), 1, 3, 25500.0, 25480.0, 25640.0, "TARGET", 828.6, 7.0],
                [et(2026, 11, 20, 6, 16), et(2026, 11, 20, 6, 40), 1, 1, 27784.0, 27735.25, 28174.0, "STOP", -129.4, -1.0]]
    if extra_closed:      # the next poll: the open long closed at its target
        z["tr"] = [r for r in z["tr"] if r[1] is not None] + [[ENTRY_T, NOW - 60, 1, 3, 25650.0, 25630.0, 25760.0, "TARGET", 654.3, 5.5]]
        for a in rows:                       # the 25K #2's copy closed too; the board has no position any more
            if a["id"] == "b25k_2":
                a["tr"] = [[ENTRY_T, NOW - 60, 1, 2, 25650.0, 25630.0, 25760.0, "TARGET", 436.2, 5.5]]
        p["board"]["lit"].pop("position", None)
    rows.append({"id": "blitz", "tr": [[et(2026, 11, 24, 10, 0), et(2026, 11, 24, 10, 10), 1, 2, 25600.0, 25590.0, 25620.0, "TARGET", 77.0, 2.0]]})
    p["fq"] = {"t": t, "fc": [["lit", ENTRY_T, 1, 3, 3, 1.0, None, -1.5, "", "L"],
                              ["lit", et(2026, 11, 23, 3, 40), 1, 3, 3, 6.0, 0.0, -9.0, "slip", "L"],
                              ["atlas", et(2026, 11, 24, 9, 35), -1, 1, 1, 3.0, 2.0, -2.5, "", "L"]]}
    return p


# ------------------------------------------------------------------------------------------------ a. static
def part_a():
    f = {n: open(os.path.join(NQ, n), encoding="utf-8").read() for n in ("live.html", "live.js", "livecore.js", "live.css")}
    check("a. the new blocks: open trades by account, the session timeline, the trade journal + streak",
          all(i in f["live.html"] for i in ('id="opens"', 'id="ogrid"', 'id="tl"', 'id="jr"', 'id="streak"')))
    check("a. livecore exports openCards / journal / streak / timeline / slipOf; BLITZ hidden list",
          all(f"export function {n}" in f["livecore.js"] for n in ("openCards", "journal", "streak", "timeline", "slipOf"))
          and "HIDDEN = ['blitz'" in f["livecore.js"])
    check("a. OLYMPUS NIGHT only: no cyan / teal, no brown / olive", not re.search(r"cyan|#0ff\b|#00ffff|teal|#8b4513|olive|brown", f["live.css"], re.I))
    check("a. reduced motion stops every animation (the pulse, the price marker, the new-fill glow)",
          "prefers-reduced-motion: reduce" in f["live.css"] and "animation: none !important" in f["live.css"])
    check("a. still read only: no innerHTML / storage / POST; versions bumped (live.js / live.css / livecore v2)",
          not re.search(r"innerHTML|insertAdjacentHTML|localStorage|sessionStorage|method:\s*['\"]POST|sendBeacon", f["live.js"] + f["livecore.js"])
          and "live.js?v=6" in f["live.html"] and "nqfeed.js?v=1" in f["live.html"] and "live.css?v=4" in f["live.html"] and "livecore.js?v=2" in f["live.js"])


# ------------------------------------------------------------------------------------------------ b. node
def part_b():
    out = NL.node_run({
        "trade": {"now": NOW, "lite": journal_post(), "bars": NL.bars_post()},
        "flat": {"now": NOW, "lite": NL.retime(NL.real(), NL.T)},
        "none": {"now": NOW, "lite": None},
    })
    check("b. node ran", len(out) == 3, list(out))
    if len(out) != 3:
        return
    M = out["trade"]
    O = {o["acct"]: o for o in M["opens"]}
    check("b. ONE CARD PER ACCOUNT in the trade: the 50K (3 MNQ, +$108) and the 25K #2 (2 MNQ, +$72), each with its own $ and +0.9R",
          sorted(O) == ["b25k_2", "mffu50k_eval"] and round(O["mffu50k_eval"]["usd"]) == 108 and round(O["b25k_2"]["usd"]) == 72
          and abs(O["mffu50k_eval"]["r"] - 0.9) < 1e-9 and O["mffu50k_eval"]["name"] == "Zlarior 50K", M["opens"])
    z = O.get("mffu50k_eval", {})
    b = z.get("bar") or {}
    check("b. the bar: entry 25,650 sits 15% of the way from the stop 25,630 to the target 25,760, the price 25,668 at 29%",
          abs(b.get("entry", 0) - 20 / 130) < 1e-6 and abs(b.get("now", 0) - 38 / 130) < 1e-6 and b.get("over") is False, b)
    check("b. card numbers: risk $120 (3 x 20 pts x $2), +$660 at the 5.5R target, in for 37 min, entered 10:05",
          round(z.get("riskUsd")) == 120 and round(z.get("targetUsd")) == 660 and abs(z.get("planR") - 5.5) < 1e-9
          and round(z.get("inFor") / 60) == 37 and z.get("at") == "10:05", z)
    J = M["journal"]
    tk = [(j["day"], j["xAt"] or j["at"]) for j in J]
    check("b. JOURNAL: closed real trades only, newest first (ATLAS today -$26, the 50K's two on the 23rd, ATLAS's real Nov 20 +$514, "
          "the 20th's stop ...); no open trade, no BLITZ",
          [(j["name"], round(j["usd"])) for j in J][:4] == [("ATLAS 25K", -26), ("Zlarior 50K", 300), ("Zlarior 50K", 829), ("ATLAS 25K", 514)]
          and ("Zlarior 50K", -129) in [(j["name"], round(j["usd"])) for j in J] and tk == sorted(tk, reverse=True) and len(J) <= 30
          and not any(j["acct"] == "blitz" for j in J), [(j["name"], j["usd"], j["day"]) for j in J])
    check("b. each row: $, R, why in words, day + times", J and J[0]["why"] == "stop" and J[0]["r"] == -1.1 and J[0]["at"] == "09:35" and J[0]["xAt"] == "09:50"
          and J[0]["day"] == "2026-11-24", J[:1])
    q = {j["day"]: j["slip"] for j in J}
    check("b. entry quality from the PC's fill check: ATLAS 3 ticks = ok, the 50K on the 23rd 6 ticks = poor; no check = none",
          q["2026-11-24"] and q["2026-11-24"]["entry"] == 3 and q["2026-11-24"]["grade"] == "ok"
          and q["2026-11-23"]["entry"] == 6 and q["2026-11-23"]["grade"] == "poor" and q["2026-11-20"] is None and M["fills"] is True, q)
    K = M["streak"]
    check("b. streak: newest is a loss -> '1 loss in a row'; 2 wins / 2 losses of the 4 (+ the ATLAS Nov trades), total $ = the sum",
          K["kind"] == "L" and K["n"] == 1 and K["count"] == len(J) and K["wins"] + K["losses"] + K["be"] == len(J)
          and abs(K["total"] - sum(j["usd"] for j in J)) < 1e-6, K)
    T = M["timeline"]
    pins = {p["name"]: p for p in T["pins"]}
    check("b. timeline: the session starts 18:00 ET the evening before; 'now' at 10:42 = 16h42 of 23 h; the open long and ATLAS's -$26 as pins",
          abs(T["now"] - (16 * 60 + 42) / (23 * 60)) < 1e-3 and "Zlarior 50K" in pins and pins["Zlarior 50K"]["open"] is True
          and pins["ATLAS 25K"]["usd"] < 0 and [m["label"] for m in T["marks"]] == ["02:00", "09:30", "15:30"], T)
    check("b. BLITZ never in today's list either", not any(t["acct"] == "blitz" for t in M["today"]))
    F = out["flat"]
    check("b. flat (the real post): no open card, the journal still holds ATLAS's real November trades",
          F["opens"] == [] and len(F["journal"]) >= 2 and all(not j.get("open") for j in F["journal"]), (F["opens"], F["journal"][:2]))
    N = out["none"]
    check("b. nothing from the PC: no card, an empty journal, no streak", N["opens"] == [] and N["journal"] == [] and N["streak"]["kind"] is None)


# ------------------------------------------------------------------------------------------------ c. browser (node Playwright)
DRIVER = r"""
const { chromium } = require('playwright');
const fs = require('fs');
const C = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const TAPS = `(${C.taps})()`, SIDE = `(${C.side})()`;
(async () => {
  const br = await chromium.launch();
  const out = {};
  for (const s of C.runs) {
    const ctx = await br.newContext({ viewport: { width: s.w, height: s.h }, deviceScaleFactor: s.shot ? 2 : 1, isMobile: s.w < 600, hasTouch: s.w < 600, reducedMotion: s.reduced ? 'reduce' : 'no-preference' });
    let body = fs.readFileSync(s.feed, 'utf8'); const off = [], errs = [];
    await ctx.route('**/*', (r) => { const u = r.request().url();
      if (u.includes('json?poll=1')) return r.fulfill({ status: 200, contentType: 'application/json', headers: { 'Access-Control-Allow-Origin': '*' }, body });
      if (!u.startsWith(C.origin)) { off.push(u); return r.abort(); } return r.continue(); });
    const p = await ctx.newPage();
    p.on('pageerror', (e) => errs.push(String(e)));
    p.on('console', (m) => { if (m.type() === 'error' && !/Failed to load resource|net::ERR/.test(m.text())) errs.push(m.text()); });
    await p.goto(`${C.origin}/nq/live.html?at=${C.at}`);
    await p.waitForFunction('window.NQ_LIVE && window.NQ_LIVE.ready() && window.NQ_LIVE.S.lite', null, { timeout: 60000 });
    await p.waitForTimeout(700);
    const read = () => p.evaluate(() => ({
      opens: [...document.querySelectorAll('.lv-oc')].map((e) => ({ key: e.dataset.key, pnl: e.querySelector('.lv-opnl b') && e.querySelector('.lv-opnl b').textContent,
        bar: !!e.querySelector('.lv-prog .now'), nowLeft: e.querySelector('.lv-prog .now') && e.querySelector('.lv-prog .now').style.left })),
      opensHidden: document.getElementById('opens') ? document.getElementById('opens').hidden : null,
      jr: [...document.querySelectorAll('#jr li')].map((e) => e.textContent), streak: [...document.querySelectorAll('.lv-sk b')].map((e) => e.textContent),
      pins: document.querySelectorAll('#tl circle').length, tlText: [...document.querySelectorAll('#tl text')].map((e) => e.textContent),
      wide: [...document.querySelectorAll('#app *')].filter((e) => e.offsetParent && e.getBoundingClientRect().right > innerWidth + 0.5).map((e) => e.className + ':' + Math.round(e.getBoundingClientRect().right)),
      tiny: [...document.querySelectorAll('body *')].filter((e) => !e.closest('.nqn-dock') && (e.offsetParent !== null || e instanceof SVGElement)).filter((e) => [...e.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim()))
        .map((e) => { let px = parseFloat(getComputedStyle(e).fontSize); const svg = e instanceof SVGElement && e.ownerSVGElement;
          if (svg) { const vb = svg.viewBox && svg.viewBox.baseVal, r = svg.getBoundingClientRect(); if (vb && vb.height && r.height) px *= r.height / vb.height; if (!r.height) return null; }
          return px < 11.95 ? (e.className && e.className.baseVal !== undefined ? e.className.baseVal : e.className || e.tagName) + ' ' + px.toFixed(1) + 'px "' + e.textContent.trim().slice(0, 20) + '"' : null; }).filter(Boolean),
      fresh: document.querySelectorAll('.lv-new').length, flat: !document.getElementById('flat').hidden,
      anim: document.querySelector('.lv-prog .now') ? getComputedStyle(document.querySelector('.lv-prog .now')).animationName : null,
      txt: document.getElementById('app').textContent }));
    const o = await read();
    o.taps = await p.evaluate(TAPS); o.side = await p.evaluate(SIDE);
    if (s.shot) { await p.evaluate(() => document.getAnimations().forEach((a) => { try { a.pause(); a.currentTime = 900; } catch (e) {} }));
      await p.screenshot({ path: s.shot, fullPage: false }); if (s.full) await p.screenshot({ path: s.full, fullPage: true }); }
    if (s.feed2) {            // the next poll: a new closed trade -> its row pulses once
      body = fs.readFileSync(s.feed2, 'utf8');
      await p.waitForTimeout(21000);           // past the 5 s ticker (the page knows what it has seen) and pc_feed's 20 s shared answer
      await p.evaluate(() => window.NQ_LIVE.refresh());
      await p.waitForTimeout(400);
      o.after = await read();
    }
    o.off = off; o.errs = errs; out[s.name] = o;
    await ctx.close();
  }
  await br.close();
  console.log(JSON.stringify(out));
})().catch((e) => { console.error(e); process.exit(1); });
"""


def browser_run(origin, runs):
    tmp = tempfile.mkdtemp(prefix="le_nqlt_")
    try:
        at = dt.datetime.fromtimestamp(NOW, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        cfg = {"origin": origin, "at": at, "taps": AK.TAPS, "side": AK.SIDEWAYS, "runs": []}
        for r in runs:
            r = dict(r)
            for k in ("feed", "feed2"):
                if r.get(k) is not None:
                    fp = os.path.join(tmp, f"{r['name']}-{k}.ndjson")
                    open(fp, "w", encoding="utf-8").write(r[k])
                    r[k] = fp
            cfg["runs"].append(r)
        cp = os.path.join(tmp, "cfg.json")
        json.dump(cfg, open(cp, "w", encoding="utf-8"))
        dp = os.path.join(tmp, "drv.cjs")
        open(dp, "w", encoding="utf-8").write(DRIVER)
        r = subprocess.run(["node", dp, cp], capture_output=True, text=True, timeout=600, cwd=tmp)
        if r.returncode:
            print(r.stderr[-3000:])
            return {}
        return json.loads(r.stdout.strip().splitlines()[-1])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def node_playwright() -> bool:
    r = subprocess.run(["node", "-e", "require('playwright')"], capture_output=True, text=True)
    return r.returncode == 0


def shots_runs(prefix, shots):
    nd = NL.ndjson
    trade, flat = nd(journal_post(), NL.bars_post()), nd(NL.retime(NL.real(), NL.T))
    runs = []
    for name, feed, w, h in (("trade", trade, 390, 844), ("flat", flat, 390, 844), ("trade", trade, 1440, 900)):
        r = {"name": f"{name}-{w}", "feed": feed, "w": w, "h": h}
        if shots:
            r["shot"] = os.path.join(SHOTS, f"{prefix}-{w}-{name}.png")
            r["full"] = os.path.join(SHOTS, f"{prefix}-{w}-{name}-full.png") if w == 390 else None
        runs.append(r)
    return runs


def part_c():
    if not node_playwright():
        print("  (node playwright missing: browser part skipped)")
        return
    shots = "--shots" in sys.argv
    if shots:
        os.makedirs(SHOTS, exist_ok=True)
    if "--before" in sys.argv:                  # the same views of another copy of the site (origin/pc before this work)
        AK.WEB, keep = sys.argv[sys.argv.index("--before") + 1], AK.WEB
        srv, origin = AK.serve({"/home.json": None})
        try:
            browser_run(origin, shots_runs("before", True))
        finally:
            srv.shutdown()
            AK.WEB = keep
    srv, origin = AK.serve({"/home.json": None})
    try:
        nd = NL.ndjson
        runs = shots_runs("after", shots)
        runs.append({"name": "pulse", "feed": nd(journal_post(), NL.bars_post()), "feed2": nd(journal_post(t=NL.T + 60, extra_closed=True)), "w": 390, "h": 844})
        runs.append({"name": "real-390", "feed": nd(NL.retime(NL.real(), NL.T)), "w": 390, "h": 844})
        runs.append({"name": "trade-360", "feed": nd(journal_post(), NL.bars_post()), "w": 360, "h": 780})
        runs.append({"name": "old-390", "feed": nd(journal_post(t=NL.T - 2 * 86400 - 3 * 3600 - 7 * 60)), "w": 390, "h": 844})   # long age words in every chip
        runs.append({"name": "reduced", "feed": nd(journal_post(), NL.bars_post()), "w": 390, "h": 844, "reduced": True})
        out = browser_run(origin, runs)
    finally:
        srv.shutdown()
    check("c. the browser runs", len(out) == len(runs), list(out))
    if len(out) != len(runs):
        return
    t = out["trade-390"]
    check("c. 390x844 in a trade: one card per account (+$108 on the 50K, +$72 on the 25K #2), each with the stop -> target bar and the price marker",
          [o["pnl"] for o in t["opens"]] == ["+$108", "+$72"] and all(o["bar"] for o in t["opens"]) and t["opens"][0]["nowLeft"].startswith("29.2")
          and t["opensHidden"] is False, t["opens"])
    check("c. the journal rows (ATLAS -$26 first) with entry quality; the streak chips; no BLITZ anywhere",
          t["jr"] and "ATLAS 25K" in t["jr"][0] and "-$26" in t["jr"][0] and "entry +3 ticks" in t["jr"][0]
          and t["streak"][0] == "1 loss" and "BLITZ" not in t["txt"], (t["jr"][:2], t["streak"]))
    check("c. the timeline: pins for today's trades (close pins share ONE label: '2 OPEN · -$26', never overlapping), the 02:00 / 09:30 / 15:30 marks, 'now'",
          t["pins"] >= 2 and all(x in t["tlText"] for x in ("02:00", "09:30", "15:30", "now")) and "2 OPEN · -$26" in t["tlText"], t["tlText"])
    check("c. the price marker breathes (nowPulse); reduced motion: no animation at all",
          t["anim"] == "nowPulse" and out["reduced"]["anim"] == "none", (t["anim"], out["reduced"]["anim"]))
    f = out["flat-390"]
    check("c. flat: the honest 'no open trade' card, no account cards, the journal still there",
          f["flat"] and f["opensHidden"] is True and not f["opens"] and len(f["jr"]) >= 2, f)
    P = out["pulse"]
    check("c. first paint: nothing pulses; the next poll brings a closed trade -> its journal row pulses once (.lv-new), the cards are gone",
          P["fresh"] == 0 and P["after"]["fresh"] >= 1 and "+$654" in P["after"]["jr"][0] and P["after"]["opensHidden"] is True, (P["fresh"], P["after"]["fresh"], P["after"]["jr"][:1]))
    for name, o in out.items():
        check(f"c. {name}: every label >= 12 px on screen (chips, ages, journal meta, chart + timeline text)", not o["tiny"], o["tiny"][:6])
        check(f"c. {name}: every chip / card inside the screen (no zoom-out on a phone)", not o["wide"], o["wide"][:5])
        check(f"c. {name}: taps >= 44 px, no sideways scroll, nothing off the site, no console error",
              not o["taps"] and o["side"] and not o["off"] and not o["errs"], (o["taps"][:4], o["off"][:3], o["errs"][:3]))


def main():
    part_a()
    part_b()
    part_c()
    return AK.finish()


if __name__ == "__main__":
    sys.exit(main())
