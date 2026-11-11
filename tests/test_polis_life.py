"""POLIS life (docs/POLIS_25.md items 11-18): tools/polis_build.py -> olympus/polis.json, drawn by olympus/polis-life.js (lab: olympus/polis-life-lab.html).
  a. the builder on empty inputs: a valid file, every part present and empty, the built-in calendar labelled as such, a stoic line
  b. the builder on the sample site: numbers by hand (amphorae, shelves, torch streaks, trees, statues, herald, oracle, stoic), every
     printed number traced to a fact (audit), every R next to its $, same files + same date = the same bytes
  c. --check: what was written is what is built now; an edited file is caught; the repo's committed polis.json and demo are current
  d. static rules: ES5 (acorn, ecmaVersion 5), no markup from data, nothing fetched from another site, reduced motion and LITE in the CSS
  e. the lab in Chromium at 390 x 844 (under the machine's one-browser lock): no console errors, the demo draws all 8 pieces with the
     right counts, taps >= 44 px, no sideways scroll, herald / festival / amphora taps work, the live file and an empty file never
     draw blank, reduced motion and LITE run no animation
    python -X utf8 -m tests.test_polis_life          POLIS_NO_BROWSER=1 skips part e
"""
from __future__ import annotations

import contextlib
import fcntl
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tests import agora_kit as AK  # noqa: E402
from tools import polis_build as PB  # noqa: E402

JS = os.path.join(AK.WEB, "olympus", "polis-life.js")
LAB = os.path.join(AK.WEB, "olympus", "polis-life-lab.html")
LOCK = "/tmp/olympus_browser.lock"
check = AK.check


def part_a():
    with tempfile.TemporaryDirectory() as tmp:
        doc = PB.build(os.path.join(tmp, "no-site"), "2026-11-11")
        keys = ["herald", "oracle", "festivals", "torch", "grove", "amphorae", "statues", "stoic"]
        check("a. empty inputs: every part is there, the file is valid JSON and says it is paper only", all(k in doc for k in keys) and doc["paper"] is True
              and json.loads(PB.dump(doc)) == doc and doc["kind"] == "olympus-polis" and doc["built"] is None, [k for k in keys if k not in doc])
        check("a. empty inputs: no tree, no amphora, no statue, no torch (unlit), the oracle is silent and says why",
              doc["grove"]["trees"] == [] and doc["amphorae"]["n"] == 0 and doc["amphorae"]["shelves"] == [] and doc["statues"]["items"] == []
              and doc["torch"]["flame"] == "unlit" and doc["oracle"]["facts"] == [] and "No morning game plan" in doc["oracle"]["plain"][0], doc["oracle"])
        f = doc["festivals"]
        check("a. empty inputs: the festivals come from the BUILT-IN table and say so (FOMC = Panathenaia, NFP = Thesmophoria, roll = Synoikia, all in the future)",
              f["builtin"] and f["src"] == "built-in" and "Built-in table" in f["label"] and f["items"] and all(x["days_left"] >= 0 for x in f["items"])
              and {"Panathenaia", "Thesmophoria", "Synoikia"} <= {x["festival"] for x in f["items"]}, [x["festival"] for x in f["items"]])
        check("a. empty inputs: the herald only cries a near festival (nothing else is invented), the stoic line is a public-domain line with its translator",
              all(h["kind"] == "festival" for h in doc["herald"]) and doc["stoic"]["public_domain"] and doc["stoic"]["translator"] and doc["stoic"]["author"] in ("Marcus Aurelius", "Epictetus", "Seneca")
              and not PB.all_audits(doc), doc["herald"])
        with open(os.path.join(tmp, "data.json"), "w") as fh:
            fh.write("{not json")
        os.makedirs(os.path.join(tmp, "pythia"))
        with open(os.path.join(tmp, "pythia", "events.json"), "w") as fh:
            fh.write('{"events": "broken"}')
        bad = PB.build(tmp, "2026-11-11")
        check("a. broken files are treated as missing (no crash): data.json unreadable, a calendar without a list -> the built-in table",
              "data.json" in bad["sources"]["missing"] and bad["festivals"]["builtin"], bad["sources"])


def part_b():
    fx = PB.fixture()
    am, tor, gr, st = fx["amphorae"], fx["torch"], {t["id"]: t for t in fx["grove"]["trees"]}, fx["statues"]["items"]
    lit = PB._sample_trades(PB.SAMPLE_LIT)
    atl = PB._sample_trades(PB.SAMPLE_ATLAS)
    check("b. one amphora per closed trade (20 Zlarior + 4 ATLAS = 24), shelved by month newest first, counts and nets by hand",
          am["n"] == 24 and [(s["month"], s["n"]) for s in am["shelves"]] == [("2026-11", 5), ("2026-10", 12), ("2026-09", 7)]
          and am["shelves"][0]["net"] == round(310 + 640 - 210 + 280 + 260, 2) and sum(s["n"] for s in am["shelves"]) == len(lit) + len(atl), [(s["month"], s["n"], s["net"]) for s in am["shelves"]])
    items = [i for s in am["shelves"] for i in s["items"]]
    check("b. amphora scenes: long = horse, short = dolphin; win / loss / flat from the $ ($2.50 and -$4.10 are scratches); the label carries $ and R",
          all((i["scene"] == "horse") == (i["side"] == "LONG") for i in items) and sorted(i["usd"] for i in items if i["result"] == "flat") == [-4.1, 2.5]
          and all(("R)" in i["label"]) == (i["r"] is not None) for i in items) and any(i["label"] == "+$1,912.50 (+8.0R)" for i in items), [i["label"] for i in items][:5])
    weeks = [(r["week"], r["green"]) for r in tor["weeks"]["rows"]]
    check("b. torch weeks: the week of 2026-09-21 broke '1 trade a day' (2 Zlarior trades on 09-24) and the week of 10-12 was red; 3 green weeks in a row now, best 3",
          weeks == [("2026-09-14", True), ("2026-09-21", False), ("2026-09-28", True), ("2026-10-05", True), ("2026-10-12", False), ("2026-10-19", True), ("2026-10-26", True), ("2026-11-02", True)]
          and tor["weeks"]["streak"] == 3 and tor["weeks"]["best"] == 3 and tor["weeks"]["current"]["net"] == -210 and tor["flame"] == "lit", weeks)
    days = tor["days"]
    broke = [r for r in days["rows"] if not r["kept"]]
    n_days = len({t["day"] for t in lit + atl})
    check("b. torch days: one row per trading day; only 2026-09-24 broke a rule (1 trade a day); the run since then is every later trading day",
          [r["day"] for r in broke] == ["2026-09-24"] and broke[0]["broke"] == ["1 trade a day"] and days["streak"] == len({t["day"] for t in lit + atl if t["day"] > "2026-09-24"})
          and len(days["rows"]) == min(20, n_days), (days["streak"], broke))
    z, a, b, p = gr["mffu50k_eval"], gr["atlas25k"], gr["blitz25k"], gr["cloud_paper"]
    zp = round(-240 + 1912.5 + 310 + 640 - 210, 2)
    check("b. the grove: Zlarior's tree grows with its eval (profit $2,412.50 of $3,000 -> 80%, 4 rings of $500, one olive per winning trade)",
          z["profit"] == zp and z["target"] == 3000 and abs(z["progress"] - round(zp / 3000, 4)) < 1e-9 and z["growth"] == z["progress"] and z["rings"] == 4
          and z["olives"] == sum(1 for t in lit if t["pnl"] > 5) and z["stage"] == "eval" and "80%" in z["line"], z)
    check("b. the grove: ATLAS is funded (a full tree, its $500 payout), BLITZ below its start is thirsty (and says by how much), the cloud's twin is a paper sapling",
          a["stage"] == "funded" and a["growth"] == 1.0 and a["payouts"] == 500 and b["thirsty"] and "$120" in b["line"] and b["growth"] == 0.12
          and p["stage"] == "paper" and "paper" in p["line"].lower() and any("Drawdown left $1,830 of $2,000 max loss" == f["t"] for f in z["facts"]), (a, b["line"]))
    best = sorted([t["pnl"] for t in lit + atl if t["pnl"] > 5], reverse=True)[:5]
    trades = [s for s in st if s["kind"] == "trade"]
    check("b. the hall: the pass and the payout, then the 5 best winning trades by $ (the first is the record, $ with its R on the plaque)",
          [s["kind"] for s in st[:2]] == ["pass", "payout"] and [s["usd"] for s in trades] == best and trades[0]["record"] and not any(s.get("record") for s in trades[1:])
          and trades[0]["plaque"] == "Thu 29 Oct · +$1,912.50 (+8.0R)" and st[0]["figure"] == "nike" and trades[0]["figure"] == "victor", [s["plaque"] for s in st])
    her = fx["herald"]
    kinds = [h["kind"] for h in her]
    check("b. the herald: the pass first, then a near festival (CPI = Dionysia in 2 days), then the newest news; trade lines carry $ and R; Kalshi lines say paper",
          kinds[:2] == ["pass", "festival"] and "Dionysia comes in 2 days" in her[1]["cry"] and any(h["cry"] == "Zlarior returns wounded from the market: -$210 (-1.0R)." for h in her)
          and all("paper" in h["plain"].lower() for h in her if h["kind"] == "kalshi") and any("estimate" in h["cry"].lower() for h in her if h["kind"] == "money") and len(her) <= 8, [h["cry"] for h in her])
    o = fx["oracle"]
    check("b. the oracle: the game plan word for word under a Delphi verse; the VIX band and the 10:30 release in the verse are among its facts; each fact names its file",
          o["plain"][0].startswith("A sweep of the Asia high") and "25,038 to 25,562" in o["verse"] and "10:30" in o["verse"] and not PB.audit(o, ("verse",))
          and all(f["src"] in ("home.json", "data.json") for f in o["facts"]) and o["speaker"]["name"] == "Delia", o)
    check("b. the stoic line answers the day: the last closed trade lost (-$210) -> a line on patience", fx["stoic"]["mood"] == "loss" and fx["stoic"]["text"] in [x[0] for x in PB.STOIC["loss"]], fx["stoic"])
    check("b. no invented numbers: every number printed in the herald, oracle, grove lines and plaques is one of its facts", not PB.all_audits(fx), PB.all_audits(fx))
    check("b. same files + same date = the same bytes; another date moves the countdowns, not the facts", PB.dump(fx) == PB.dump(PB.fixture()), "")
    with tempfile.TemporaryDirectory() as tmp:
        web = PB.sample_site(tmp)
        d2 = PB.build(web, "2026-11-12")
        check("b. a day later: the Dionysia is 1 day away, amphorae unchanged", d2["festivals"]["items"][0]["days_left"] == 1 and d2["amphorae"] == PB.build(web, "2026-11-11")["amphorae"])
        os.remove(os.path.join(web, "data.json"))
        d3 = PB.build(web, "2026-11-11")
        check("b. without data.json the accounts come from home.json (trees still planted), and there are no trades (no amphora is made up)",
              len(d3["grove"]["trees"]) == 4 and d3["sources"]["accounts"] == "home.json" and d3["amphorae"]["n"] == 0 and d3["sources"]["trades"] is None, d3["sources"])


def part_c():
    with tempfile.TemporaryDirectory() as tmp:
        web = PB.sample_site(tmp)
        rc = PB.main(["--web", web, "--date", "2026-11-11"])
        out = os.path.join(web, "olympus", "polis.json")
        ok1 = rc == 0 and PB.main(["--web", web, "--check"]) == 0
        doc = json.load(open(out))
        doc["herald"][0]["cry"] += " (edited)"
        with open(out, "w") as fh:
            fh.write(PB.dump(doc))
        check("c. --check: up to date after a build (exit 0); an edited polis.json is caught (exit 1)", ok1 and PB.main(["--web", web, "--check"]) == 1)
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "polis_build.py"), "--check"], capture_output=True, text=True, cwd=ROOT)
    check("c. the repo's committed olympus/polis.json and the labelled polis-demo.json are what the builder writes now", r.returncode == 0, r.stdout + r.stderr)
    demo = json.load(open(os.path.join(AK.WEB, "olympus", "polis-demo.json")))
    check("c. the demo file is labelled DEMO and 'not real'", demo["demo"] is True and "not real" in demo["label"], demo["label"])


def part_d():
    js, lab = AK.read(JS), AK.read(LAB)
    acorn = "/opt/node-tools/node_modules/acorn/dist/acorn.js"
    node = shutil.which("node")
    if node and os.path.isfile(acorn):
        r = subprocess.run([node, "-e", f"require({json.dumps(acorn)}).parse(require('fs').readFileSync({json.dumps(JS)}, 'utf8'), {{ecmaVersion: 5}})"], capture_output=True, text=True)
        check("d. polis-life.js parses as ES5 (acorn, ecmaVersion 5)", r.returncode == 0, r.stderr[-400:])
        inline = re.search(r"<script>\n(.*?)</script>", lab, re.S).group(1)
        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, "lab.js")
            open(p, "w").write(inline)
            r = subprocess.run([node, "-e", f"require({json.dumps(acorn)}).parse(require('fs').readFileSync({json.dumps(p)}, 'utf8'), {{ecmaVersion: 5}})"], capture_output=True, text=True)
        check("d. the lab's own script is ES5 too", r.returncode == 0, r.stderr[-400:])
    else:
        print("[SKIP] d. node / acorn not on this machine: the browser part still runs the script")
    bad = [p for p in (r"\.innerHTML", r"outerHTML", r"insertAdjacentHTML", r"document\.write", r"\beval\s*\(", r"new Function") if re.search(p, js) or re.search(p, lab)]
    check("d. no markup is built from data (no innerHTML / outerHTML / insertAdjacentHTML / document.write / eval)", not bad, bad)
    urls = [u for u in re.findall(r"https?://[^\s'\"<>)]+", js + lab) if not u.startswith(("http://www.w3.org/",))]
    check("d. nothing from another site: no CDN, no web address but the SVG namespaces; the lab loads only this folder's files", not urls and not re.search(r"<script[^>]+src=\"(?:https?:)?//", lab), urls)
    check("d. reduced motion and LITE stop every animation (the CSS says so; the JS asks OLYMPUS.lite / reduced)", "prefers-reduced-motion:reduce" in js and 'data-oly-lite="1"' in js
          and "O.reduced" in js and "O.lite" in js)
    check("d. tap targets are 44 px in the CSS (buttons, amphorae, festival cards, the facts summary)", js.count("min-height:44px") >= 4 and "min-width:44px" in js and "width:44px" in js)
    check("d. the AGORA look: no neon colours, no glow text-shadow, no techno font, no pure black / white", not AK.BANNED_LOOK.search(js) and "#000000" not in js.lower()
          and not re.search(r"#fff(?:fff)?\b", js, re.I), AK.BANNED_LOOK.findall(js)[:3])
    check("d. the POLIS kit is used only when present (window.OLYMPUS_POLIS, feature-tested) and this file never defines it", "root.OLYMPUS_POLIS;" in js and "OLYMPUS_POLIS =" not in js)


@contextlib.contextmanager
def browser_lock(wait=2400):
    """The machine's ONE browser at a time (docs/NIGHT_BRIEF.md round 3): the same lock file `flock -w 2400 /tmp/olympus_browser.lock` takes."""
    fd = os.open(LOCK, os.O_CREAT | os.O_RDWR, 0o666)

    def late(*_):
        raise TimeoutError("the browser lock stayed busy")
    old = signal.signal(signal.SIGALRM, late)
    signal.alarm(wait)                       # a blocking wait queues fairly behind the other flock(1) waiters (a polling one starves)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
    except TimeoutError:
        os.close(fd)
        raise
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)
    try:
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


ANIMS = "() => document.getAnimations().filter(a => a.playState === 'running' && a.effect && a.effect.target && a.effect.target.closest && a.effect.target.closest('.pl-piece')).length"


def part_e():
    empty = json.dumps({"v": 1, "kind": "olympus-polis", "label": "Empty test file.", "herald": [], "oracle": None, "festivals": {"items": []}, "torch": {}, "grove": {}, "amphorae": {}, "statues": {}, "stoic": None})
    srv, origin = AK.serve()
    srv_e, origin_e = AK.serve({"/olympus/polis.json": empty})
    try:
        with browser_lock(), AK.browser() as br:
            ctx, p, errs, seen, off = AK.page(br, origin)
            p.goto(origin + "/olympus/polis-life-lab.html?demo=1")
            p.wait_for_function("window.POLIS_LIFE_LAB && window.POLIS_LIFE_LAB.ready()", timeout=60000)
            p.wait_for_timeout(500)
            n = p.evaluate("""() => ({pieces: document.querySelectorAll('.pl-piece').length, jars: document.querySelectorAll('.pl-jar').length, trees: document.querySelectorAll('.pl-tree').length,
                statues: document.querySelectorAll('.pl-statue').length, fests: document.querySelectorAll('.pl-fest').length, runners: document.querySelectorAll('.pl-frieze use').length,
                lamps: document.querySelectorAll('.pl-lamp').length, leaves: Array.from(document.querySelectorAll('.pl-tree')).map(t => +t.getAttribute('data-leaves')),
                plaque: Array.from(document.querySelectorAll('.pl-plaque-usd')).map(e => e.textContent), label: document.getElementById('label').textContent})""")
            check("e. demo at 390 x 844: all 8 pieces, 24 amphorae, 4 trees, 7 statues, the festivals, a runner per finished week, a lamp per day; labelled DEMO",
                  n["pieces"] == 8 and n["jars"] == 24 and n["trees"] == 4 and n["statues"] == 7 and n["fests"] == 4 and n["runners"] == 6 and n["lamps"] == 20 and "DEMO" in n["label"], n)
            check("e. the trees are full: a funded tree has far more leaves than the thirsty sapling; plaques print $ with R", n["leaves"][1] > 3 * n["leaves"][2] and "+$1,912.50 (+8.0R)" in n["plaque"], n["leaves"])
            check("e. no console error, nothing fetched off this site", not errs and not off, (errs, off))
            check("e. taps >= 44 px and no sideways scroll at 390 px", not AK.taps(p) and AK.no_sideways(p), AK.taps(p))
            c0 = p.text_content(".pl-cry")
            p.click(".pl-hb-nav .pl-btn >> nth=1")
            c1 = p.text_content(".pl-cry")
            p.click(".pl-fest >> nth=0")
            exp = p.get_attribute(".pl-fest >> nth=0", "aria-expanded")
            p.click(".pl-jar >> nth=0")
            det = p.text_content(".pl-amph-detail")
            check("e. taps: the herald's next button changes the line, a festival card opens its meaning, an amphora tells its trade ($ and R)",
                  c0 != c1 and exp == "true" and "Long" in det and "R)" in det, (c0, c1, exp, det))
            check("e. motion is on by default (herald / flame / smoke animate)", p.evaluate(ANIMS) > 0, p.evaluate(ANIMS))
            AK.shot(p, "polis-life-demo")
            ctx.close()
            ctx, p, errs, seen, off = AK.page(br, origin, reduced=True)
            p.goto(origin + "/olympus/polis-life-lab.html?demo=1")
            p.wait_for_function("window.POLIS_LIFE_LAB.ready()", timeout=60000)
            p.wait_for_timeout(400)
            check("e. reduced motion: nothing of POLIS life animates (the loading veil belongs to olympus.js), no error", p.evaluate(ANIMS) == 0 and not errs, (p.evaluate(ANIMS), errs))
            ctx.close()
            ctx, p, errs, seen, off = AK.page(br, origin, lite=True)
            p.goto(origin + "/olympus/polis-life-lab.html?demo=1")
            p.wait_for_function("window.POLIS_LIFE_LAB.ready()", timeout=60000)
            p.wait_for_timeout(400)
            lv = p.evaluate("() => +document.querySelectorAll('.pl-tree')[1].getAttribute('data-leaves')")
            run = p.evaluate("() => document.getAnimations().filter(a => a.playState === 'running' && a.effect && a.effect.target && a.effect.target.closest && a.effect.target.closest('.pl-piece')).map(a => (a.animationName || a.constructor.name) + ' ' + ((a.effect && a.effect.target && a.effect.target.getAttribute && a.effect.target.getAttribute('class')) || ''))")
            check("e. LITE: nothing animates and the trees draw fewer leaves", not run and lv < n["leaves"][1] and not errs, (run[:5], lv, n["leaves"][1], errs))
            ctx.close()
            ctx, p, errs, seen, off = AK.page(br, origin)
            p.goto(origin + "/olympus/polis-life-lab.html")
            p.wait_for_function("window.POLIS_LIFE_LAB.ready()", timeout=60000)
            txt = p.evaluate("() => Array.from(document.querySelectorAll('.pl-piece')).map(e => e.textContent.trim().length)")
            check("e. the live file (repo copy: no site build yet) draws every piece with words, none blank, no error", len(txt) == 8 and min(txt) > 20 and not errs, (txt, errs))
            ctx.close()
            ctx, p, errs, seen, off = AK.page(br, origin_e)
            p.goto(origin_e + "/olympus/polis-life-lab.html")
            p.wait_for_function("window.POLIS_LIFE_LAB.ready()", timeout=60000)
            txt = p.evaluate("() => Array.from(document.querySelectorAll('.pl-piece')).map(e => e.textContent.trim().length)")
            check("e. an empty polis.json: every piece says what it waits for (never blank), no error", len(txt) == 8 and min(txt) > 20 and not errs, (txt, errs))
            ctx.close()
    finally:
        srv.shutdown()
        srv_e.shutdown()


def main():
    part_a()
    part_b()
    part_c()
    part_d()
    if os.environ.get("POLIS_NO_BROWSER") == "1":
        print("[SKIP] e. POLIS_NO_BROWSER=1")
    else:
        part_e()
    AK.finish()


if __name__ == "__main__":
    main()
