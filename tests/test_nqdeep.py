"""NQ DEEP kit (tools/web_public/nqdeep.js + nqdeep.css, night-nqdash2 2026-11-20): the deeper views on the NQ pages, checked with sample data.
  a. static: the kit is wired where it is drawn (trading/ 9. Deep dive, nq/ news + waiting + fills, business/mffu.html first payout), text only
     (no innerHTML), no fetch / storage of its own, colours only from tokens, motion opacity only, the exports are current (tools/nqdash_export.py --check)
  b. node, on the real trades.json and hand-made rows: R / $ distribution, drawdown, LIVE vs twin in R, streaks, best / worst, hour x weekday,
     the timeline levels, the fill line (never invented), the payout range (payday.json), the news week, the source tag + age, junk input never throws
    python -X utf8 -m tests.test_nqdeep
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "tools", "web_public")
RES: list[tuple[str, bool]] = []


def check(name: str, ok: bool, info=None) -> None:
    RES.append((name, bool(ok)))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + ("" if ok or info is None else f"  -> {info}"))


def read(p: str) -> str:
    with open(os.path.join(WEB, p), encoding="utf-8") as fh:
        return fh.read()


def test_static() -> None:
    js, css = read("nqdeep.js"), read("nqdeep.css")
    check("a. text only: no innerHTML / insertAdjacentHTML / eval in the kit", not re.search(r"innerHTML|insertAdjacentHTML|\beval\(|new Function", js))
    check("a. the kit fetches nothing and keeps nothing", not re.search(r"\bfetch\(|XMLHttpRequest|localStorage|sessionStorage|indexedDB|sendBeacon", js))
    check("a. Safari 16 safe (no lookbehind, no .at())", not re.search(r"\(\?<[=!]|\.at\(", js))
    hexes = [h for h in re.findall(r"#[0-9a-fA-F]{3,6}\b", css) if not re.search(r"var\([^)]*" + re.escape(h), css)]
    check("a. css colours only through tokens (a hex only as a var() fallback)", not hexes, hexes[:5])
    anim = re.findall(r"@keyframes[^{]+\{(.*?)\}\s*\}", css, re.S)
    check("a. motion: opacity only, and none under reduced motion", all("transform" not in a and "width" not in a for a in anim) and "prefers-reduced-motion" in css)
    t, n, m = read("trading/index.html"), read("nq/index.html"), read("business/mffu.html")
    check("a. wired: trading 9. Deep dive with its 8 boxes", all(f'id="{i}"' in t for i in ("deepCard", "dUnder", "dTwin", "dDistR", "dDistUsd", "dHeat", "dStreak", "dExt", "dTime"))
          and "../nqdeep.js" in t and "../nqdeep.css" in t)
    check("a. wired: nq news card + the kit; mffu the kit before mffu.js", 'id="newsWeek"' in n and "../nqdeep.js" in n
          and m.index("../nqdeep.js") < m.index("mffu.js?"))
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "nqdash_export.py"), "--check"], capture_output=True, text=True)
    check("a. business/payday.json + nq/news_week.json are current (tools/nqdash_export.py --check)", r.returncode == 0, r.stdout.strip())
    pub = read("business/payday.json") + read("nq/news_week.json")
    check("a. privacy: the exports hold no account id, balance or email", not re.search(r"@|balance|\b\d{6,}\b|acct_?id", pub, re.I))


NODE = r"""
const K = require(process.argv[1]), D = K.core, out = {};
const F = require(process.argv[2]), PD = require(process.argv[3]), NW = require(process.argv[4]);
const lit = F.trades.filter((r) => r.bot === 'LIT' && r.src === 'backtest');
const mk = (day, hm, usd, r, src, extra) => Object.assign({ src: src || 'live', bot: 'LIT', ak: 'z50k', day, hm, t: Date.parse(day + 'T' + hm + ':00Z') / 1000, usd, r, e: 100, s: 99, tg: 108, x: usd > 0 ? 108 : 99, side: 'LONG', k: usd > 0 ? 'TARGET' : 'STOP' }, extra || {});
const S = [mk('2026-11-02', '09:00', 400, 2), mk('2026-11-03', '09:00', -200, -1), mk('2026-11-04', '10:00', -200, -1), mk('2026-11-05', '10:00', -200, -1),
           mk('2026-11-06', '09:00', 900, 4.5), mk('2026-11-09', '09:00', 0.2, 0), mk('2026-11-10', '09:00', 300, 1.5)];
out.distR = D.dist(lit, 'r'); out.distU = D.dist(lit, 'usd'); out.distS = D.dist(S, 'r');
out.uw = D.underwater(S); out.uwLit = D.underwater(lit);
out.st = D.streaks(S); out.ex = D.extremes(S, 2); out.heat = D.heat(S);
out.tl = D.timeline(S[0]); out.tlBad = D.timeline({ e: null });
const twinRows = S.concat([mk('2026-11-02', '09:00', 800, 2.1, 'backtest'), mk('2026-11-03', '09:00', -400, -1, 'backtest'), mk('2026-11-06', '09:00', 1600, 4, 'backtest')]);
out.twin = D.twinR(twinRows, 'LIT', 'z50k'); out.twinNone = D.twinR(lit, 'LIT', 'z50k');
out.fill = D.fillLine({ bots: [{ key: 'lit', name: 'Zlarior', fills: { line: 'Real fills so far: 2 ticks worse', n: 5 } }, { key: 'k8', name: 'K8' }] }, 'LIT');
out.fillNone = D.fillLine({ bots: [{ key: 'atlas' }] }, 'ATLAS'); out.fillJunk = D.fillLine('x', 'LIT');
out.pay = D.payout('Zlarior 50K', PD, 'H2', '2026-11-20'); out.payAtlas = D.payout('ATLAS 25K funded', PD, 'H2', '2026-11-20');
out.payBlitz = D.payout('BLITZ', PD, 'H2', '2026-11-20'); out.payNone = D.payout('Zlarior 50K', null, 'H2', '2026-11-20');
out.news = D.weekNews(NW, '2026-11-18', '15:00'); out.newsSat = D.weekNews({ events: [{ date: '2026-11-23', time: '08:30', title: 'X', impact: 'high' }, { date: '2026-11-23', time: '09:00', title: 'Low one', impact: 'low' }] }, '2026-11-21', '');
out.tag = D.tag(S, Date.parse('2026-11-10T12:00:00Z') / 1000); out.tagMix = D.tag(twinRows); out.tagBlitz = D.tag([mk('2026-11-02', '09:00', 5, 1, 'live', { bot: 'BLITZ' })]);
let junk = true; try { for (const j of [null, 1, 'x', [null, {}, { day: 'bad' }], { trades: 1 }]) { D.dist(j, 'r'); D.underwater(j); D.streaks(j); D.extremes(j); D.heat(j); D.twinR(j, 'LIT'); D.tag(j); D.weekNews(j, '2026-11-20'); D.payout('x', j); } } catch (e) { junk = String(e); }
out.junk = junk;
console.log(JSON.stringify(out));
"""


def test_node() -> None:
    r = subprocess.run(["node", "-e", NODE, os.path.join(WEB, "nqdeep.js"), os.path.join(WEB, "trading", "trades.json"),
                        os.path.join(WEB, "business", "payday.json"), os.path.join(WEB, "nq", "news_week.json")], capture_output=True, text=True, timeout=60)
    if r.returncode:
        check("b. node runs the kit", False, r.stderr[-400:])
        return
    o = json.loads(r.stdout)
    dr, du = o["distR"], o["distU"]
    n_lit = sum(b["n"] for b in dr["buckets"])
    check("b. R spread: every LIT backtest trade in one 0.5R bar (-2R..+8R), -1R stops sit in the -1R bar", n_lit == dr["n"] == 120
          and next(b for b in dr["buckets"] if b["mid"] == -1)["n"] >= 30, (n_lit, dr["n"]))
    check("b. $ spread: round bar width, every trade counted, 12 bars at most", du["n"] == 120 and sum(b["n"] for b in du["buckets"]) == 120 and len(du["buckets"]) <= 12 and du["w"] in (25, 50, 100, 200, 250, 500, 1000, 2000, 5000))
    uw = o["uw"]
    check("b. drawdown: +400, -600 over 3 days, back above the peak on day 5; worst -$600 on Thu 5 Nov", uw["maxDD"] == -600 and uw["maxDDDay"] == "2026-11-05"
          and uw["recoveredDay"] == "2026-11-06" and uw["nowDD"] == 0 and uw["net"] == 1000.2, uw)
    check("b. drawdown on the real LIT backtest = the research file's max DD (-$2,195.6 in H1)", o["uwLit"]["maxDD"] == -2195.6, o["uwLit"]["maxDD"])
    st = o["st"]
    check("b. streaks: longest 3 losses, now 2 wins (the break-even in between does not end it), record 3 W 3 L 1 B", st["bestL"] == 3 and st["bestW"] == 2
          and st["cur"] == 2 and st["curK"] == "W" and (st["wins"], st["losses"], st["be"]) == (3, 3, 1), st)
    ex = o["ex"]
    check("b. best / worst: +$900 and +$400 first; worst are the -$200 trades; no 0 in either", [x["usd"] for x in ex["best"]] == [900, 400]
          and all(x["usd"] == -200 for x in ex["worst"]) and len(ex["worst"]) == 2)
    h = o["heat"]
    cell = next(c for g in h["grid"] if g["h"] == 9 for c in g["cells"] if c["w"] == 1)
    check("b. hour x weekday: Mon 09:00 = 2 trades, 50% (+$400 and a break-even); only hours that traded; best / worst need 3 trades", cell["n"] == 2 and cell["pct"] == 50
          and [g["h"] for g in h["grid"]] == [9, 10] and h["best"] is None and h["worst"] is None)
    tl = o["tl"]
    check("b. timeline: the levels box (long, entry 100, stop 99, target 108, out 108) and a sentence; no levels -> nothing", tl["long"] and tl["lo"] == 99 and tl["hi"] == 108
          and "in 100.00, stop 99.00" in tl["text"] and o["tlBad"] is None)
    tw = o["twin"]
    check("b. LIVE vs twin in R: live +5.0R vs backtest +5.1R over the same days, gap -0.1R", tw["liveR"] == 5.0 and tw["backR"] == 5.1 and tw["gap"] == -0.1 and tw["n"] == 7 and tw["nBack"] == 3, tw)
    check("b. no LIVE rows -> no twin, no made-up gap", o["twinNone"]["n"] == 0 and o["twinNone"]["gap"] is None)
    check("b. fill cost: the PC's own line for LIT; none for a bot without fills or junk (never invented)", o["fill"]["line"].startswith("Real fills so far") and o["fill"]["n"] == 5
          and o["fillNone"]["line"] == "" and o["fillJunk"]["line"] == "")
    p, pa = o["pay"], o["payAtlas"]
    check("b. payout range: the 50K's p10 / median / p90 from payday.json, in order, today on the left", p and p["lo"] <= p["med"] <= p["hi"] and 0 <= p["posLo"] <= p["posMed"] <= 1
          and "First payout most likely" in p["text"], p)
    check("b. payout: ATLAS funded found by name; BLITZ and no plan -> none", pa and pa["id"] == "A25" and o["payBlitz"] is None and o["payNone"] is None)
    nw = o["news"]
    wed = next(d for d in nw["days"] if d["day"] == "2026-11-18")
    check("b. news week: Mon-Fri of the week, Wed 18 Nov's FOMC minutes 14:00 is past at 15:00, the next one after the week named", [d["day"] for d in nw["days"]][0] == "2026-11-16"
          and wed["today"] and wed["events"] and wed["events"][0]["past"] and nw["next"] and nw["next"]["day"] > "2026-11-20", nw)
    ns = o["newsSat"]
    check("b. news on a Saturday shows the coming week; a low-impact line is left out", ns["from"] == "2026-11-23" and ns["n"] == 1)
    check("b. source tag: LIVE / MIXED with the newest day and its age; a BLITZ row never counts", o["tag"]["src"] == "LIVE" and "newest Tue 10 Nov" in o["tag"]["text"]
          and "ago" in o["tag"]["text"] and o["tagMix"]["src"] == "MIXED" and o["tagBlitz"]["src"] == "")
    check("b. junk input never throws", o["junk"] is True, o["junk"])


if __name__ == "__main__":
    test_static()
    test_node()
    ok = sum(1 for _, k in RES if k)
    print(f"\n{ok}/{len(RES)} passed")
    sys.exit(0 if ok == len(RES) else 1)
