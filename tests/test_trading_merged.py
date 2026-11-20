"""TRADING round 3 (lead 2026-11-20, the audit's MERGE verdicts): Odeon's reels and the Why study as Trading cards (tools/web_public/trading/merged.js),
lazy-loaded (their files fetch only when the card is about to show; the card keeps its height). Node + static, ~1 s.
    python -X utf8 -m tests.test_trading_merged
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "tools", "web_public")
RES = []


def check(name, cond, info=""):
    RES.append(bool(cond))
    print(("[PASS] " if cond else "[FAIL] ") + name + ("" if cond else f"  -> {str(info)[:900]}"))


def read(p):
    with open(p, encoding="utf-8") as fh:
        return fh.read()


HARNESS = r"""
const fs = require('fs');
import(process.argv[2]).then((M) => {
  const od = JSON.parse(fs.readFileSync(process.argv[3], 'utf8')), wj = JSON.parse(fs.readFileSync(process.argv[4], 'utf8'));
  const R = M.reels(od), W = M.why(wj);
  const o = { n: R.length, first: R[0], blitz: JSON.stringify(R).toLowerCase().includes('blitz'), live: R.filter((r) => r.src === 'LIVE').length,
    liveFirst: R.findIndex((r) => r.src !== 'LIVE') >= R.filter((r) => r.src === 'LIVE').length || R.every((r) => r.src === 'LIVE'),
    hrefs: R.every((r) => r.href.startsWith('../odeon/#reel=')), atlas: M.reels(od, { bot: 'ATLAS' }).every((r) => r.bot === 'ATLAS'),
    why: W && { bots: W.bots.map((b) => b.name), lose: W.bots.map((b) => b.lose.length), check: W.checklist.length, verdict: W.verdict.length > 20, blitz: JSON.stringify(W).toLowerCase().includes('blitz') },
    junk: [null, 5, 'x', {}, { trades: [null, 4, { id: 'a' }] }].map((j) => { try { return [M.reels(j).length, M.why(j) === null || typeof M.why(j) === 'object']; } catch (e) { return 'THROW ' + e.message; } }) };
  console.log(JSON.stringify(o));
}).catch((e) => { console.error(e); process.exit(1); });
"""


def main():
    js, html, tj = read(os.path.join(WEB, "trading", "merged.js")), read(os.path.join(WEB, "trading", "index.html")), read(os.path.join(WEB, "trading", "trading.js"))
    check("a. text only (no innerHTML / storage / fetch in merged.js: trading.js fetches, only when the card shows)",
          not re.search(r"innerHTML|insertAdjacentHTML|fetch\(|localStorage|sessionStorage", js))
    check("a. both cards on Trading before the help card, the reels keep a fixed height (mg-fixed), the small Why file draws with the page and links to the old app (../odeon/, ../why/)",
          html.index('id="reelsCard"') < html.index('id="whyCard"') < html.index('id="helpCard"') and html.count("mg-lazy") == 1 and 'class="mg-fixed"' in html
          and 'href="../odeon/"' in html and 'href="../why/"' in html and ".mg-lazy { min-height" in read(os.path.join(WEB, "trading", "merged.css")))
    check("a. lazy: the two files load inside an IntersectionObserver callback only", "IntersectionObserver" in tj and "watchMerged" in tj
          and tj.index("getJSON('../odeon/trades.json'") > tj.index("const jobs = "))
    exe = shutil.which("node")
    if not exe:
        check("node skipped", True)
        return
    tmp = tempfile.mkdtemp(prefix="trmerged-")
    try:
        m = os.path.join(tmp, "merged.mjs")
        shutil.copy(os.path.join(WEB, "trading", "merged.js"), m)
        h = os.path.join(tmp, "h.cjs")
        with open(h, "w", encoding="utf-8") as fh:
            fh.write(HARNESS)
        r = subprocess.run([exe, h, m, os.path.join(WEB, "odeon", "trades.json"), os.path.join(WEB, "why", "why.json")], capture_output=True, text=True, timeout=60)
        if r.returncode:
            check("node harness runs", False, r.stderr[-600:])
            return
        o = json.loads(r.stdout)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    check(f"b. Odeon reels: {o['n']} reels, LIVE first ({o['live']}), each opens ../odeon/#reel=<id>, the bot filter works, BLITZ never",
          o["n"] >= 20 and o["live"] >= 1 and o["first"]["src"] == "LIVE" and o["liveFirst"] and o["hrefs"] and o["atlas"] and not o["blitz"], o["first"])
    w = o["why"]
    check("b. Why: the verdict, Zlarior + ATLAS with where the lost $ went, the careful-human checklist; BLITZ never",
          w and w["bots"] == ["Zlarior", "ATLAS"] and all(n >= 2 for n in w["lose"]) and w["check"] >= 3 and w["verdict"] and not w["blitz"], w)
    check("c. junk never throws", all(isinstance(j, list) for j in o["junk"]), o["junk"])


if __name__ == "__main__":
    main()
    n, ok = len(RES), sum(RES)
    print(f"\n{ok}/{n} passed")
    sys.exit(0 if ok == n else 1)
