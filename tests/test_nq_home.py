"""NQ TRADING HOME launcher + PC HEALTH (night-nq-home 2026-11-27; owner: "the NQ dashboard still looks poorly done ... 3D, effects";
PC Health = "what I open when something feels wrong").
tools/web_public/nq/trading_home.html (+ trading_home_core.js tiles()) and nq/pchealth.html/.js/.css (+ pchealth_core.js).

  a. static: textContent only (no innerHTML / eval), no sends, OLYMPUS NIGHT colours (no cyan / brown), reduced motion handled
  b. node: the REAL PC post of 2026-11-27 (tests/fixtures/nq_home): PC Health = red, first the ready check (ATLAS not armed), NinjaTrader
     connect-on-startup amber, backup amber, Telegram / OneDrive grey ("does not send this yet"), version bc74f71 green, 312 tick days;
     a held-back update is red with the plain reason; an old report greys the greens; no report = red; ids masked; BLITZ hidden.
     tiles(): today $, 4/4 armed, Flat, next window + news, 312 days, brain stage, $ to pass, PC health; today() unchanged (5 lines)
  c. browser 390x844: fresh / old (5 h) / none; no sideways scroll, no page error, GET only to the page's own host, taps >= 44 px
Run: python -X utf8 -m tests.test_nq_home
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NQ = os.path.join(ROOT, "tools", "web_public", "nq")
FIX = os.path.join(ROOT, "tests", "fixtures", "nq_home", "real_post_2026-11-27.json")
RESULTS = []


def check(name, cond, info=""):
    RESULTS.append(bool(cond))
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"   -> {info!r}"[:600]))


def static():
    for f in ("pchealth.html", "pchealth.js", "pchealth.css", "pchealth_core.js", "trading_home.html", "trading_home_core.js"):
        src = open(os.path.join(NQ, f), encoding="utf-8").read()
        check(f"a. {f}: no innerHTML / eval / storage writes / sends",
              not re.search(r"innerHTML|outerHTML|insertAdjacentHTML|\beval\(|new Function|sendBeacon|method:\s*['\"]POST|XMLHttpRequest", src))
        check(f"a. {f}: no cyan / brown", not re.search(r"#0ff\b|#00ffff|cyan|#8b4513|olive|brown", src, re.I))
    for f in ("pchealth.css", "trading_home.html"):
        check(f"a. {f}: prefers-reduced-motion", "prefers-reduced-motion" in open(os.path.join(NQ, f), encoding="utf-8").read())
    h = open(os.path.join(NQ, "trading_home.html"), encoding="utf-8").read()
    check("a. trading home links PC Health", 'href="pchealth.html"' in h and "pchealth_core.js" in h)
    check("a. pchealth links back to Trading Home", 'href="trading_home.html"' in open(os.path.join(NQ, "pchealth.html"), encoding="utf-8").read())


NODE = r"""
const [H, T, fix, news] = process.argv.slice(1).map((p, i) => i < 2 ? require(p) : JSON.parse(require('fs').readFileSync(p, 'utf8')));
const L = fix, now = L.t + 120, clone = () => JSON.parse(JSON.stringify(L)), out = {};
out.real = H.checks(L, { now });
const held = clone(); held.ck.up = { v: 'bc74f71', p: '1234567', b: ['engine/live.py'] }; out.held = H.checks(held, { now });
const pend = clone(); pend.ck.up = { v: 'bc74f71', p: '1234567' }; out.pend = H.checks(pend, { now });
out.old = H.checks(L, { now: L.t + 5 * 3600 });
out.none = H.checks(null, { now });
const al = clone(); al.al = { tg: true, od: false, ut: L.t - 3600 }; out.al = H.checks(al, { now });
const id = clone(); id.ck.acc[0][0] = 'MFFUEVBLDR12346016'; id.ck.acc[0][1] = 0; out.mask = H.checks(id, { now });
out.tiles = T.tiles(L, { now, news: news.events, health: H });
out.tilesOld = T.tiles(L, { now: L.t + 5 * 3600, news: news.events, health: H });
out.tilesNone = T.tiles(null, { now });
const op = clone(); op.board.trades.unshift({ acct: 'lit', member: 'LIT', side: 'LONG', qty: 2, open: true, usd: 180 }); out.tilesOpen = T.tiles(op, { now, health: H });
const bz = clone(); bz.ck.acc.push(['BLITZ 50K', 0, 0, 0]); out.tilesBlitz = T.tiles(bz, { now, health: H });
out.today = T.today(L, { now });
out.todayReal = out.today;
const un = clone(); un.ar.atlas = [0, 0]; un.ck.acc.forEach((r) => { if (/atlas/i.test(r[0])) r[1] = 0; }); out.unarmed = H.checks(un, { now }); out.todayUnarmed = T.today(un, { now });
out.cut1 = T.tidyCut('Press 2 (Start bot) and type it yourself (Claud');
out.cut2 = T.tidyCut('one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen ab');
out.nn = T.nextNews([{ date: '2026-12-04', time: '08:30', title: 'NFP', impact: 'high' }, { date: '2026-11-20', time: '08:30', title: 'old', impact: 'high' }], Date.UTC(2026, 10, 27) / 1000);
console.log(JSON.stringify(out));
"""


def node():
    p = subprocess.run(["node", "-e", NODE, os.path.join(NQ, "pchealth_core.js"), os.path.join(NQ, "trading_home_core.js"), FIX,
                        os.path.join(NQ, "news_week.json")], capture_output=True, text=True)
    if p.returncode:
        check("b. cores run under node", False, p.stderr[-500:])
        return
    o = json.loads(p.stdout)
    by = lambda r: {c["id"]: c for c in r["checks"]}  # noqa: E731
    r, c = o["real"], by(o["real"])
    check("b. real post: overall amber, first = ready check", r["overall"] == "amber" and r["checks"][0]["id"] == "ready" and "Ready check" in r["say"], r["say"])
    check("b. QA#1: rd says ATLAS not armed but ck.acc/ar say armed -> amber 'disagree', not a hard NOT READY; its age shown",
          c["ready"]["state"] == "amber" and "disagree" in c["ready"]["say"] and "NOT READY" not in c["ready"]["say"] and "2 min ago" in c["ready"]["say"], c["ready"])
    u = by(o["unarmed"])["ready"]
    check("b. QA#1: really not armed -> red NOT READY, fix never cut mid-word", u["state"] == "red" and "NOT READY" in u["say"] and "(Claud" not in u["fix"]
          and u["fix"].endswith("yourself."), u)
    tr = o["todayReal"]["lines"][0]
    check("b. QA#1 Trading Home: the ready line says 'checking', no 'press 1' next to rd's 'press 2', age shown", tr["id"] == "ready" and "checking" in tr["say"]
          and tr["menu"] is None and "(Claud" not in tr["say"] and "ago" in tr["say"], tr)
    tu = o["todayUnarmed"]["lines"][0]
    check("b. QA#1 Trading Home really not armed: NOT READY + whole-word fix, no duplicate menu", "NOT READY for 02:00: ATLAS 25K is not armed." in tu["say"]
          and "yourself." in tu["say"] and "(Claud" not in tu["say"] and tu["menu"] is None, tu)
    check("b. tidyCut: unclosed bracket dropped, long cut ends on a whole word", o["cut1"] == "Press 2 (Start bot) and type it yourself." and o["cut2"].endswith("…")
          and not o["cut2"].endswith("ab…"), (o["cut1"], o["cut2"]))
    check("b. NinjaTrader connect-on-startup off = amber with the fix", c["nt"]["state"] == "amber" and "Connect on startup" in c["nt"]["fix"], c["nt"])
    check("b. backup amber, version green bc74f71 + 'updates itself hourly'", c["backup"]["state"] == "amber" and c["version"]["state"] == "green"
          and "bc74f71" in c["version"]["say"] and "hourly" in c["version"]["say"], (c["backup"], c["version"]))
    check("b. all 4 armed green, clock green, 312 tick days", c["armed"]["state"] == "green" and "All 4 armed" in c["armed"]["say"]
          and c["clock"]["state"] == "green" and "312 tick days" in c["ticks"]["say"], (c["armed"], c["ticks"]))
    check("b. Telegram + OneDrive honest grey", c["alerts"]["state"] == "grey" and c["onedrive"]["state"] == "grey" and "does not send" in c["onedrive"]["say"])
    check("b. report 2 min green", c["report"]["state"] == "green" and "2 min" in c["report"]["say"], c["report"])
    check("b. every check has a state + one sentence", all(x["state"] in ("green", "amber", "red", "grey") and x["say"] for x in r["checks"]))
    h = by(o["held"])["version"]
    check("b. held-back update = red with the plain reason + fix", h["state"] == "red" and "HELD BACK" in h["say"] and "engine/live.py" in h["say"] and h["fix"], h)
    check("b. a waiting update = amber 'within the hour'", by(o["pend"])["version"]["state"] == "amber" and "within the hour" in by(o["pend"])["version"]["say"])
    old = by(o["old"])
    check("b. 5 h old report: report red, greens turn grey 'Old report'", old["report"]["state"] == "red" and old["clock"]["state"] == "grey"
          and old["clock"]["say"].startswith("Old report"), (old["report"], old["clock"]))
    check("b. no report = red, one item", o["none"]["overall"] == "red" and len(o["none"]["checks"]) == 1)
    a = by(o["al"])
    check("b. 'al' block read when sent (Telegram green, OneDrive green, last update)", a["alerts"]["state"] == "green" and a["onedrive"]["state"] == "green"
          and a.get("updated", {}).get("state") == "green", (a["alerts"], a["onedrive"], a.get("updated")))
    m = by(o["mask"])["armed"]
    check("b. account ids masked", "MFFUEVBLDR" not in json.dumps(o["mask"]) and "…6016" in m["say"] and m["state"] == "red", m)
    t = {x["id"]: x for x in o["tiles"]}
    check("b. tiles: today / armed / trade / event / of / brain / target / health", list(t) == ["today", "armed", "trade", "event", "of", "brain", "target", "health"], list(t))
    check("b. tiles real numbers", t["today"]["big"] == "$0" and t["armed"]["big"] == "4 / 4" and t["trade"]["big"] == "Flat" and t["of"]["big"] == "312 days"
          and t["target"]["big"] == "$3,822" and t["brain"]["big"].startswith("Displacement") and t["health"]["tone"] == "gold", t)
    check("b. next event = Fri 02:00 window + a real news line", t["event"]["big"] == "Fri 02:00 ET" and "news:" in t["event"]["sub"], t["event"])
    check("b. every tile links a real page", all(os.path.exists(os.path.join(NQ, x["href"])) for x in o["tiles"]))
    check("b. old report marks the tiles", all(x["sub"].startswith("Old report") for x in o["tilesOld"] if x["id"] != "health"))
    check("b. no report: tiles honest '-'/'no report'", o["tilesNone"][0]["big"] == "no report" and all(x["big"] in ("-", "no report") for x in o["tilesNone"]))
    to = {x["id"]: x for x in o["tilesOpen"]}["trade"]
    check("b. open trade tile", to["big"] == "LONG 2" and "$180" in to["sub"] and to["tone"] == "gold", to)
    check("b. BLITZ hidden from the armed tile", {x["id"]: x for x in o["tilesBlitz"]}["armed"]["big"] == "4 / 4")
    check("b. today() unchanged: 5 checklist lines + fleet", len(o["today"]["lines"]) >= 5, len(o["today"]["lines"]))
    check("b. nextNews skips past events", o["nn"] and o["nn"]["title"] == "NFP", o["nn"])


def browser():
    if not shutil.which("node") or not os.path.isdir("/opt/node22/lib/node_modules/playwright"):
        print("SKIP c. browser part: no node + playwright here")
        return
    p = subprocess.run(["node", os.path.join(ROOT, "tests", "nq_home_page_check.js"), os.path.join(ROOT, "tools", "web_public"), FIX],
                       capture_output=True, text=True, timeout=240, env={**os.environ, "NODE_PATH": "/opt/node22/lib/node_modules"})
    if p.returncode:
        check("c. page check ran", False, p.stderr[-500:])
        return
    o = json.loads(p.stdout.strip().splitlines()[-1])
    for k, v in o.items():
        check(f"c. {k}: no sideways scroll, no error, GET only, taps >= 44", v["side"] <= 0 and not v["errs"] and not v["sends"] and not v["small"],
              (v["side"], v["errs"], v["sends"], v["small"]))
        check(f"c. {k}: black background", v["bg"] in ("rgb(0, 0, 0)", "rgba(0, 0, 0, 0)") or "rgb(0, 0, 0)" in v["bg"], v["bg"])
        check(f"c. {k}: no full account id, no BLITZ", not re.search(r"MFFU[A-Z]{2,}\d{5,}", v["text"]) and "BLITZ" not in v["text"])
    f = o["fresh_trading_home"]
    check("c. trading home: 5 checklist rows kept + 8 tiles", f["rows"] >= 5 and len(f["tiles"]) == 8, (f["rows"], len(f["tiles"])))
    check("c. trading home: PC health tile amber (QA#1 disagreement), stays in place", [x[0] for x in f["tiles"]].index("health") == 7 and f["tiles"][7][1].startswith("gold"), f["tiles"][7])
    check("c. trading home: no '(Claud' anywhere", "(Claud" not in f["text"])
    g = o["fresh_pchealth"]
    check("c. pchealth: amber hero + the ready check first", g["hero"] == "amber" and g["cards"][0][0] == "ready" and "Ready check" in g["say"], (g["hero"], g["cards"][:2]))
    clip = g.get("clip") or ""
    check("c. pchealth 'Copy for Claude' copies every check in plain text", clip.startswith("PC Health: 4 things need you") and "(Claud" not in clip and clip.count("\n- [") == len(g["cards"])
          and "[amber] Ready check" in clip and not re.search(r"MFFU[A-Z]{2,}\d{4,}", clip), clip[:200])
    check("c. pchealth old: report red", dict(o["old_pchealth"]["cards"]).get("report") == "red")
    check("c. pchealth none: 'No report from the PC yet.'", o["none_pchealth"]["say"] == "No report from the PC yet.", o["none_pchealth"]["say"])
    nt = {x[0]: x for x in o["none_trading_home"]["tiles"]}
    check("c. trading home none: today says no report, health red first", nt["today"][2] == "no report" and o["none_trading_home"]["tiles"][0][0] == "health", nt.get("today"))


def main() -> int:
    static()
    node()
    browser()
    bad = RESULTS.count(False)
    print(f"\n{len(RESULTS) - bad}/{len(RESULTS)} passed")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
