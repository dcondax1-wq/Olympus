"""EVAL ECONOMICS (day-evalroi 2026-11-27): tools/roi_build.py -> nq/roi.json, nq/roicore.js, nq/roi.html, the Accounts card.

    python -X utf8 -m tests.test_evalroi [--static]

  a. roi.json = tools/roi_build.build() from the stored sims (same rows, same best); the owner's REAL prices ($91.80 / $63 / $97.20 / $165,
     never list); MFFU slots: only the Rapid EOD 25K / 50K have a free funded slot today; best next buy = the free plan with the most
     2026-like $ (Rapid EOD 50K), its line names the 2025-like loss; every plan loses money in a 2025-like market (the caveat is true)
  b. roicore (node): $ per $1 good / bad, payback months, the slot line; earned = the PC's funded trackers' "pt" (none = "no payout
     recorded yet", never $0 made up as a payout); spent = $295.00-$315.00 (one 25K's price not recorded: a range, not a guess)
  c. browser 390 x 844: roi.html shows the best move, spent / paid / net, 4 plan cards, the caveat; taps >= 44 px, no sideways scroll,
     no text under 12 px, nothing off the site, no console error; the Accounts page shows the card linking to roi.html
"""
from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tests import agora_kit as AK  # noqa: E402
from tests import test_accounts_screen as TA  # noqa: E402
from tools import roi_build as RB  # noqa: E402

check = AK.check
NQ = os.path.join(ROOT, "tools", "web_public", "nq")


def part_a():
    F = json.load(open(os.path.join(NQ, "roi.json"), encoding="utf-8"))
    B = RB.build()
    strip = lambda d: {k: v for k, v in d.items() if k != "made"}  # noqa: E731
    check("a. roi.json = roi_build.build() from the stored sims (rebuild it after a new run)", strip(F) == strip(B))
    P = {r["name"]: r for r in F["rows"]}
    check("a. the owner's real prices: Builder 50K $91.80, 25K $63, Rapid EOD 25K $97.20, Rapid EOD 50K $165",
          [P[n]["price"] for n in ("Builder 50K", "Builder 25K", "Rapid EOD 25K", "Rapid EOD 50K")] == [91.8, 63.0, 97.2, 165.0], P.keys())
    check("a. MFFU slots today: Builder 50K / 25K full; Rapid EOD 25K and 50K one free (the 5th funded slot)",
          [P[n]["free"] for n in ("Builder 50K", "Builder 25K", "Rapid EOD 25K", "Rapid EOD 50K")] == [0, 0, 1, 1])
    b = F["best"]
    check("a. best next buy = the free plan with the most 2026-like $ (Rapid EOD 50K); the line names its 2025-like loss and the card to decide",
          b["key"] == "mffu_rapid_eod_50k" and "2025-like market it loses" in b["line"] and "plan-rapid50k" in b["card"], b)
    check("a. the caveat is true: every plan's 6-month net is negative in a 2025-like market (and positive in a 2026-like one)",
          all(r["markets"]["Y25"]["net6"] < 0 < r["markets"]["H2"]["net6"] for r in F["rows"]), [(r["name"], r["markets"]["Y25"]["net6"]) for r in F["rows"]])


def node(js):
    r = subprocess.run(["node", "--input-type=module", "-e", js], capture_output=True, text=True, cwd=NQ, timeout=60)
    if r.returncode:
        raise RuntimeError(r.stderr[-600:])
    return json.loads(r.stdout)


def part_b():
    o = node("""
import * as C from './roicore.js'; import fs from 'fs';
const roi = JSON.parse(fs.readFileSync('roi.json'));
const none = C.model(roi, null), paid = C.model(roi, { mf: { a: [{ id: 'atlas', f: { pt: 800, pn: 1 } }, { id: 'x', f: { pn: 0 } }] } }), zero = C.model(roi, { mf: { a: [{ id: 'atlas', f: { pn: 0, pt: 0 } }] } });
console.log(JSON.stringify({ none: { e: none.earnedText, spent: none.spent.text, net: none.net, rows: none.rows }, paid: { e: paid.earnedText, net: paid.net }, zero: zero.earnedText, cav: none.caveat }));
""")
    R = {r["name"]: r for r in o["none"]["rows"]}
    z = R["Builder 50K"]
    check("b. a plan card: $38 per $1 (2026-like) vs $0.29 (2025-like), payback at the first payout ~1.6 months, slots full = re-buy only",
          z["goodPer"] == 37.78 and z["badPer"] == 0.29 and any("about 1.6 months" in l for l in z["lines"]) and "re-buy only" in z["slot"]
          and z["verdict"] == "+EV only in a 2026-like market", z)
    check("b. Rapid EOD 50K: one free slot, $54 per $1 in a 2026-like market", R["Rapid EOD 50K"]["free"] and R["Rapid EOD 50K"]["goodPer"] == 54.18, R["Rapid EOD 50K"])
    check("b. spent so far = $295-$315 (a range: which 25K cost $43 is not recorded); no tracker = 'none recorded yet'; net = -$315 to -$295",
          o["none"]["spent"] == "$295-$315" and o["none"]["e"] == "none recorded yet" and o["none"]["net"] == {"lo": -315, "hi": -295}, o["none"])
    check("b. paid to you = the trackers' pt ($800 from 1 payout -> net +$485 to +$505); a tracker with 0 payouts = '$0 so far'",
          o["paid"]["e"] == "$800 from 1 payout" and o["paid"]["net"] == {"lo": 485, "hi": 505} and o["zero"].startswith("$0 so far"), (o["paid"], o["zero"]))
    check("b. the honest caveat names the 2025-like market", "2025-like" in o["cav"] and "loses money" in o["cav"])


def part_c():
    try:
        import playwright  # noqa: F401
    except ImportError:
        print("  (playwright not installed: browser part skipped)")
        return
    at = dt.datetime.fromtimestamp(TA.NOW, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    srv, origin = AK.serve({"/home.json": None})
    SMALL = """() => { const out = []; const w = document.createTreeWalker(document.getElementById('app'), NodeFilter.SHOW_TEXT);
      for (let n = w.nextNode(); n; n = w.nextNode()) { const t = n.textContent.trim(); if (!t) continue; const e = n.parentElement;
        if (!e || !e.offsetParent) continue; const fs = parseFloat(getComputedStyle(e).fontSize); if (fs < 12) out.push(t.slice(0, 30) + ' ' + fs); } return out; }"""
    try:
        with AK.browser() as br:
            ctx, p, errs, seen, off = AK.page(br, origin, w=390, h=844, mock={"json?poll=1": TA.ndjson(*TA.post())})
            p.goto(f"{origin}/nq/roi.html")
            p.wait_for_function("window.NQ_ROI && window.NQ_ROI.ready()", timeout=60000)
            p.wait_for_timeout(300)
            o = p.evaluate("""() => ({ best: document.getElementById('best').textContent, plans: document.querySelectorAll('.rp').length,
                bestCard: (document.querySelector('.rp.best h2') || {}).textContent, so: document.getElementById('sofar').textContent, cav: document.getElementById('caveat').textContent })""")
            check("c. roi.html 390: the best move (Rapid EOD 50K), spent / paid / net, 4 plan cards (the best one marked), the caveat",
                  "Best next money move" in o["best"] and "Rapid EOD 50K" in o["best"] and o["plans"] == 4 and o["bestCard"] == "Rapid EOD 50K"
                  and "$295-$315" in o["so"] and "2025-like" in o["cav"], o)
            check("c. roi.html: taps >= 44 px, no sideways scroll, no text under 12 px, nothing off the site, no console error",
                  not AK.taps(p) and AK.no_sideways(p) and not p.evaluate(SMALL) and not off and not errs, (AK.taps(p)[:3], p.evaluate(SMALL)[:3], off[:2], errs[:2]))
            if "--shots" in sys.argv:
                sd = os.path.join(ROOT, "research", "handoff", "2026-11-27", "evalroi", "shots"); os.makedirs(sd, exist_ok=True)
                p.screenshot(path=os.path.join(sd, "roi-390.png")); p.screenshot(path=os.path.join(sd, "roi-390-full.png"), full_page=True)
            ctx.close()
            ctx, p, errs, seen, off = AK.page(br, origin, w=390, h=844, mock={"json?poll=1": TA.ndjson(*TA.post())})
            p.goto(f"{origin}/nq/accounts.html?at={at}")
            p.wait_for_function("window.NQ_ACCOUNTS && window.NQ_ACCOUNTS.ready()", timeout=60000)
            c = p.evaluate("() => { const a = document.getElementById('roiCard'); return a ? { hidden: a.hidden, href: a.getAttribute('href'), t: a.textContent } : null; }")
            check("c. Accounts: the eval economics card links to roi.html with the best next buy", c and not c["hidden"] and c["href"] == "roi.html"
                  and "Rapid EOD 50K at $165.00" in c["t"] and not errs, c)
            ctx.close()
    finally:
        srv.shutdown()


def main():
    part_a()
    part_b()
    if "--static" not in sys.argv:
        part_c()
    return AK.finish()


if __name__ == "__main__":
    sys.exit(main())
