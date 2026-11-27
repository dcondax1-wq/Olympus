"""The Kalshi City + Sibyl merge into Dionysus (day-kalshi 2026-11-20, AUDIT research/handoff/2026-11-20/revamp-main/AUDIT.md: "dionysus = Kalshi
desk; absorbs Sibyl, Kalshi City"). Plain cards, no 3D, no blur: Kalshi's fee per contract with K8's row marked (kalshicity/learned.json), bet size
vs going broke (learned.json ruin), what the old bot taught (learned.json + kalshicity/suggestions.json), Sibyl's paper picks + its own record
(money/sibyl.json + money/sibyl_forward.json), Kalshi words, and an "Older pages (archive)" footer to ../sibyl/ and ../kalshicity/ (kept as they are).
Everything but the fee rule is the old crypto bot's history (retired 2026-11-19) and says so.
  a. static: the reads (same origin, 4 s), the cards + ids, text only, the ?v bump, the old pages untouched and still linked, no 3D / blur
  b. node maths: feeTable / ruinTable / oldLessons / sibylView on the real files and on junk
  c. Chromium 390 x 844 (node Playwright, tests/dionysus_merge.cjs): the cards show / hide, K8 row, links, junk, demo
    python -X utf8 -m tests.test_dionysus_merge          (--static: parts a and b; run c under flock -w 2400 /tmp/olympus_browser.lock)
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "tools", "web_public")
D = os.path.join(WEB, "dionysus")
FX = os.path.join(ROOT, "tests", "fixtures", "k8_plan_sample.json")
RES: list = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}" + ("" if ok else f"  -> {str(info)[:500]}"))


def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def part_static():
    js, html, css, core = (read(os.path.join(D, n)) for n in ("dionysus.js", "index.html", "dionysus.css", "dionysuscore.js"))
    for u in ("../kalshicity/learned.json", "../kalshicity/suggestions.json", "../money/sibyl.json", "../money/sibyl_forward.json"):
        check(f"a. reads {u} same-origin with a 4 s limit, skipped in the demo", f"forced ? null : getJSON('{u}', 4000)" in js)
    check("a. the new cards exist with their ids, data cards hidden until filled; the words card is static text",
          all(f'id="{i}"' in html for i in ("feeCard", "ruinCard", "lessonCard", "sibylCard", "wordsCard"))
          and all(re.search(rf'id="{i}"[^>]*hidden', html) for i in ("feeCard", "ruinCard", "lessonCard", "sibylCard")))
    check("a. the K8 today panel is the first card (today's bot first, bar 2026-11-20), then the old bot's balance, before every merged card",
          html.index('id="k8Card"') < html.index('id="bal"') < html.index('id="guardCard"') < html.index('id="feeCard"'))
    check("a. 'Older pages (archive)' links ../sibyl/ and ../kalshicity/", 'Older pages (archive)' in html and 'href="../sibyl/"' in html and 'href="../kalshicity/"' in html)
    check("a. the old bot's numbers are labelled as retired history", html.count("Old bot (retired)") >= 2 and "OLD = 'old bot (retired)'" in core)
    v = re.findall(r'dionysus\.(css|js)\?v=(\w+)', html)
    check("a. CLS 0 (Olympus 2 PERF): K8 today is on the page from the first paint at its full height (class loading, min-height), never hidden later; the status line keeps 3 lines",
          'class="ag-card card k8 loading" id="k8Card"' in html and ".k8.loading { min-height: 660px; }" in css and "#status { min-height:" in css and "card.hidden = !k" not in js)
    check("a. ?v bumped: dionysus.css?v=a8, dionysus.js?v=a8 (FX terminal look, 2026-11-20)", v == [("css", "a8"), ("js", "a7")], v)
    check("a. text only (no innerHTML), no 3D, no blur, no new library", "innerHTML" not in js and "three" not in js.lower() and "backdrop-filter" not in css and "blur(" not in css
          and not re.search(r"<script[^>]+src=\"https?:", html))
    check("a. a junk file hides only its own card (try / hide per card)", "$(id).hidden = true" in js)
    check("a. the old folders are still there (sibyl/, kalshicity/ index pages)", os.path.isfile(os.path.join(WEB, "sibyl", "index.html")) and os.path.isfile(os.path.join(WEB, "kalshicity", "index.html")))
    fx_tag = re.search(r'<script[^>]+nqfx\.js', html)
    check("a. FX (owner 2026-11-20 'some 3D, some effects'): the kit olympus/nqfx.js?v=n6 is added by dionysus.js after load + idle (no tag in the HTML, so the first paint is unchanged), themed OLYMPUS NIGHT (black, violet, lavender; owner 2026-11-20)",
          not fx_tag and "const FX_SRC = '../olympus/nqfx.js?v=n6';" in js and "requestIdleCallback" in js and "NQ.theme(FX_COLORS)" in js and "cyan: '#9d59ee'" in js and "#22d3ee" not in js and "NQ.roll(" in js and "NQ.win(" in js)
    night = css.split("TERMINAL look")[1] if "TERMINAL look" in css else ""
    cyan = re.findall(r"#(?:22d3ee|67e8f9|3b82f6|070b14|0b1220)\b|34, 211, 238|59, 130, 246", night, re.I)
    check("a. OLYMPUS NIGHT look (owner 2026-11-20): no cyan / navy in the page's block; black base, violet edges (#3e255e / #4d2e76) and light #9d59ee, mint win, red loss; the html accent is violet, theme-color black",
          "TERMINAL look" in night + css and not cyan and "--ag-night: #000000" in night and "#3e255e" in night and "#4d2e76" in night and "rgba(157, 89, 238" in night and "--ag-olive: #77db89" in night
          and "--ag-terra: #ef4444" in night and "'--oly-accent', '#9d59ee'" in html and 'content="#000000"' in html, cyan)
    motion = css.split("TERMINAL look")[1] if "TERMINAL look" in css else ""
    anims = [m.start() for m in re.finditer(r"animation:", motion)]
    np_ = motion.find("@media (prefers-reduced-motion: no-preference)")
    check("a. FX: every CSS animation of the terminal look sits under prefers-reduced-motion: no-preference (reduced motion = nothing moves); no WebGL of its own",
          anims and np_ >= 0 and all(a > np_ and a < motion.find("@media (prefers-reduced-motion: reduce)") for a in anims) and "webgl" not in js.lower(), anims)
    check("a. no sw.js of Dionysus's own (nothing for the lead's worker list)", not os.path.exists(os.path.join(D, "sw.js")))


HARNESS = r"""
const fs = require('fs');
import(process.argv[2]).then((C) => {
  const L = JSON.parse(fs.readFileSync(process.argv[3], 'utf8')), S = JSON.parse(fs.readFileSync(process.argv[4], 'utf8')), SB = JSON.parse(fs.readFileSync(process.argv[5], 'utf8'));
  const o = {};
  const f = C.feeTable(L); o.fee = [f.rows.length, f.rows[0], f.rows[9], f.total, f.gross, f.net, f.bets];
  o.feeBad = [C.feeTable(null), C.feeTable({}), C.feeTable({ fees: { rows: 'x' } }), C.feeTable({ fees: { rows: [{ price: 2, fee_per_contract: 1, breakeven_win_rate: 0.5 }, { price: 'x' }] } })];
  const r = C.ruinTable(L); o.ruin = [r.rows.length, r.rows[0].policy, r.rows[0].ruin, r.bank, r.floor, r.days];
  o.ruinBad = [C.ruinTable(null), C.ruinTable({ ruin: { rows: [{ policy: 'a', p_ruin: 7 }], bankroll: 55 } }), C.ruinTable({ ruin: { rows: [{ policy: '<b>x</b>', p_ruin: 0.5 }], bankroll: 'x' } })];
  const l = C.oldLessons(L, S); o.les = [l.items.length, l.items.map((i) => i.verdict).join(), l.items[0].net, l.items[0].n, l.notes.length, l.bets, !!l.head];
  o.lesBad = [C.oldLessons(null, null), C.oldLessons({}, { items: 'x' }), C.oldLessons({ headline: '<i>x</i> y' }, null).head];
  o.sib = [C.sibylView(SB, null), (() => { const v = C.sibylView({ ...SB, demo: false, status: 'ok' }, SB.own); return [v.picks.length, v.counts, v.picks[0].title, v.own.start, v.own.claim, v.own.n]; })()];
  o.sibBad = [C.sibylView(null, null), C.sibylView({ id: 'x' }, { kind: 'none' }), C.sibylView('x', 5)];
  console.log(JSON.stringify(o));
});
"""


def part_maths():
    node = shutil.which("node")
    if not node:
        check("b. node is not installed: maths skipped", True)
        return
    sys.path.insert(0, ROOT)
    from tests import agora_kit as AK
    o = AK.node("dionysus", HARNESS, os.path.join(WEB, "kalshicity", "learned.json"), os.path.join(WEB, "kalshicity", "suggestions.json"), os.path.join(WEB, "sibyl", "fixture.json"))
    if "_error" in o:
        check("b. the harness ran", False, o["_error"])
        return
    check("b. fee table: 10 rows, 50¢ = 1.75¢ fee / must win 51.8%, 99¢ = 0.07¢ / 99.1%; the old bot's fee bill $73.05, +$10.23 gross, -$62.82 net, 1836 bets",
          o["fee"] == [10, {"price": 50, "fee": 1.75, "be": 51.8}, {"price": 99, "fee": 0.07, "be": 99.1}, 73.05, 10.23, -62.82, 1836], o["fee"])
    check("b. fee table on junk = null (null, {}, rows not a list, only bad rows)", o["feeBad"] == [None, None, None, None], o["feeBad"])
    check("b. ruin: 6 rows, the first is the old bot's 6 contracts at 29%, $55.81 start, $6 floor, 90 days", o["ruin"] == [6, "fixed 6 contracts (today)", 0.2895, 55.81, 6, 90], o["ruin"])
    check("b. ruin on junk = null (no file, a chance above 100%, a bankroll that is not a number)", o["ruinBad"] == [None, None, None], o["ruinBad"])
    check("b. old lessons: the 3 stops + 1 pause, -$248.30 over 581 first, 3 notes, 1836 bets, a headline", o["les"] == [4, "stop,stop,stop,pause", -248.3, 581, 3, 1836, True], o["les"])
    check("b. old lessons on junk = null, tags stripped from a headline", o["lesBad"] == [None, None, "x y"], o["lesBad"])
    check("b. Sibyl: its demo file is ignored (null without a ledger); a real file gives 3 picks of 12, 95–97¢ first, the ledger since 2026-10-27",
          o["sib"][0] is None and o["sib"][1][:3] == [3, {"edges": 12, "worthy": 3}, "95–97¢"] and o["sib"][1][3] == "2026-10-27", o["sib"])
    check("b. Sibyl on junk = null", o["sibBad"] == [None, None, None], o["sibBad"])


def part_browser():
    node = shutil.which("node")
    if not node:
        check("c. node is not installed: browser part skipped", True)
        return
    groot = subprocess.run(["npm", "root", "-g"], capture_output=True, text=True).stdout.strip()
    paths = [x for x in (groot, "/opt/node-tools/node_modules", os.environ.get("NODE_PATH", "")) if x]
    env = {**os.environ, "NODE_PATH": os.pathsep.join(paths)}
    args = [node, os.path.join(ROOT, "tests", "dionysus_merge.cjs"), WEB, FX]
    if os.environ.get("DIONYSUS_SHOTS"):
        args += ["--shots", os.environ["DIONYSUS_SHOTS"]]
    r = subprocess.run(args, capture_output=True, text=True, env=env, timeout=900)
    try:
        out = json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        if "Cannot find module 'playwright'" in r.stderr:
            check("c. node Playwright is not installed: browser part skipped", True)
            return
        check("c. the browser harness ran", False, (r.stdout[-400:], r.stderr[-800:]))
        return
    for name, ok, info in out["steps"]:
        check("c. " + name, ok, info)


def main():
    part_static()
    part_maths()
    if "--static" not in sys.argv:
        part_browser()
    n = sum(RES)
    print(f"\ndionysus merge: {n}/{len(RES)} " + ("ALL PASS" if n == len(RES) else "FAILED"))
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
