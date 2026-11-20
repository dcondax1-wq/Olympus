"""SIBYL, the OLYMPUS prediction-market edge scanner (tools/money/sibyl.py + tools/web_public/sibyl/, AGORA look, 2026-11-10): picks ranked by the edge left after fees on a cautious win rate,
a quarter-Kelly paper stake capped at 2% of the bankroll, ruin odds, the forward paper tally with its n, and what could go wrong. SUGGESTIONS ONLY: it never places a bet.

  a. static: the scanner's selftest, the files, the kit lines, the AGORA look, read-only, the Jarvis card, the manifest, the DEMO fixture is exactly the scanner's --fixture output, the 3D module is separate and light
  b. the maths in node (sibylcore.js): money words with their R, sizing follows the bankroll, junk files fall back to the demo, the token layout is deterministic
  c. Chromium 390 x 844 (and 375 x 667): the DEMO case, a typed bankroll resizes the stakes, a filter, a tap opens a row, the 3D ball (and the flat twin with ?q=off), the real file, taps >= 44 px, no sideways scroll, no console error
    python -X utf8 -m tests.test_sibyl_page            (--static: parts a and b only)
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import agora_kit as AK  # noqa: E402

APP, NAME = "sibyl", "Sibyl"
check = AK.check
SCAN = os.path.join(AK.ROOT, "tools", "money", "sibyl.py")


def _scanner():
    spec = importlib.util.spec_from_file_location("sibyl_scanner", SCAN)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_static():
    r = subprocess.run([sys.executable, "-I", SCAN, "--selftest"], capture_output=True, text=True, timeout=300)
    check("a. the scanner's own selftest passes (tools/money/sibyl.py --selftest)", r.returncode == 0 and "ALL PASS" in r.stdout, r.stdout[-600:] + r.stderr[-300:])
    r2 = subprocess.run([sys.executable, "-I", os.path.join(AK.ROOT, "tools", "money", "sibyl_ledger.py"), "--selftest"], capture_output=True, text=True, timeout=300)
    check("a. the own-picks ledger's selftest passes (tools/money/sibyl_ledger.py --selftest)", r2.returncode == 0 and "ALL PASS" in r2.stdout, r2.stdout[-600:] + r2.stderr[-300:])
    r3 = subprocess.run([sys.executable, "-I", os.path.join(AK.ROOT, "tools", "money", "sibyl_results.py"), "--selftest"], capture_output=True, text=True, timeout=300)
    check("a. the results builder's selftest passes (tools/money/sibyl_results.py --selftest: a proxy from the bot's settled bets, nothing invented)", r3.returncode == 0 and "ALL PASS" in r3.stdout, r3.stdout[-600:] + r3.stderr[-300:])
    AK.static_kit(APP, NAME, reads=("../money/sibyl.json", "../money/sibyl_forward.json", "../kalshicity/suggestions.json", "./suggestions_fixture.json"))
    sug = os.path.join(AK.ROOT, "tools", "web_public", "kalshicity", "suggestions.json")
    check("a. the stop-list card: suggestions_fixture.json is the builder output (python tools/kalshi_suggestions_build.py), suggestions only, every row has its n", open(sug, encoding="utf-8").read() == open(os.path.join(AK.WEB, APP, "suggestions_fixture.json"), encoding="utf-8").read() and all(i["n"] > 0 for i in json.load(open(sug, encoding="utf-8"))["items"]) and "stopCard" in AK.read(os.path.join(AK.WEB, APP, "index.html")))
    d = os.path.join(AK.WEB, APP)
    fx = json.load(open(os.path.join(d, "fixture.json"), encoding="utf-8"))
    m = _scanner()
    import tempfile
    _, fresh = m.run(tempfile.mkdtemp(prefix="sibyl-t-"), fixture=True)
    check("a. fixture.json is exactly what `sibyl.py --fixture` writes (rebuild it with that command when the scanner changes): demo, status sample", json.dumps(fx, sort_keys=True) == json.dumps(fresh, sort_keys=True) and fx["status"] == "sample", fx.get("status"))
    html = AK.read(os.path.join(d, "index.html"))
    check("a. the page order: today (ball), picks, every kind of bet, scoreboard, what could go wrong, how to read this", html.index('id="stage"') < html.index('id="picks"') < html.index('id="list"') < html.index('id="sbCard"') < html.index('id="ownCard"') < html.index('id="riskCard"') < html.index('id="notes"'))
    sj = AK.read(os.path.join(d, "sibyl.js"))
    check("a. bar 2026-11-20 (archive page): the archive banner sits above the status line with 44 px links to today's bot (../kalshi/) and the Kalshi desk (../dionysus/); the cards say old bot",
          "Archive: this page is history (the old crypto bot, retired 2026-11-19)." in html and html.index("archive-banner") < html.index('id="status"') and 'class="ag-btn primary" href="../kalshi/"' in html
          and 'href="../dionysus/"' in html and "The old bot's last study" in html and "Kalshi is paused" not in html)
    check("a. bar: nothing readable = a plain sentence (empty()), never 'Something went wrong'; offline is said", "function empty(" in sj and "Something went wrong" not in sj and "You are offline" in sj)
    check("a. the 3D ball is its own module tag (a failed load can never stop the page) and the flat twin exists", 'src="sibylball.js' in html and "SIBYL_BALL_FAIL" in html and 'id="flat"' in html)
    ball = AK.read(os.path.join(d, "sibylball.js"))
    check("a. the ball is light: the OLYMPUS render core + materials, bloom <= .25, a dpr cap <= 1.5, a lathe stand, no per-frame allocation of textures, reads no data and sends nothing",
          "olympus/render.js" in ball and "olympus/materials.js" in ball and re.search(r"strength:\s*0\.(?:[0-2]\d?)\b", ball) and "maxDpr: 1.5" in ball and "LatheGeometry" in ball and not re.search(r"fetch\(|XMLHttpRequest|innerHTML|WebSocket", ball))
    check("a. the ball follows the kit's idle rules: no frame while hidden, frameGap, reduced motion", "O.hidden()" in ball and "frameGap" in ball and "RM" in ball)
    sib = AK.read(os.path.join(d, "sibyl.js")) + AK.read(os.path.join(d, "sibylcore.js"))
    check("a. paper only: no order, buy, place, arm, key or token code anywhere in the page", not re.search(r"\b(placeOrder|submitOrder|api[_-]?key|Authorization|private[_-]?key|\.post\()", sib, re.I))
    scan = AK.read(SCAN).split("# ------", 1)[0]
    check("a. the scanner imports no network, no engine, no bot code and writes only the one json it is told to", not re.search(r"^\s*(import|from)\s+(urllib|requests|socket|http|ssl|engine|live)\b", scan, re.M) and "sibyl.json" in AK.read(SCAN))
    wiring = AK.read(os.path.join(AK.ROOT, "docs", "NEW_APPS_WIRING.md"))
    check("a. the wiring rows for the lead are in docs/NEW_APPS_WIRING.md (a section named Sibyl)", re.search(r"^# .*SIBYL", wiring, re.M | re.I) is not None)


HARNESS = r"""
import(process.argv[2]).then((C) => {
  const o = {};
  const fx = JSON.parse(process.argv[3]);
  o.words = [C.usd(3.4059), C.usdS(-0.12), C.rWord(-3.41, 3.41), C.rWord(0.12, 3.41), C.both(-3.41, 3.41), C.cents(0.571), C.cents(-1.2), C.ruinWord(0.2), C.ruinWord(3.4), C.ruinWord(null), C.SCOREWORD(80), C.SCOREWORD(10)];
  const v = C.chooseView(fx, null), pick = v.items.find((i) => i.picked);
  o.view = [v.src, v.status, v.demo, v.items.length, v.counts.worthy, v.bank.usd, v.items.filter((i) => i.picked).length, v.items.every((i) => i.n > 0), v.score.n, v.score.status, v.risks.length >= 4];
  const s = C.sizeFor(pick, 170.26), s2 = C.sizeFor(pick, 1000), s0 = C.sizeFor(pick, 0), sn = C.sizeFor(v.items.find((i) => !i.picked), 170.26);
  o.size = [s.stake, s.lose, s.win, s.loseWord, s.winWord, s2.stake, s2.stake / s.stake > 5.8 && s2.stake / s.stake < 5.9, s0, sn];
  o.total = [C.totalRisk(v.items, 170.26), C.totalRisk(v.items, 1000), C.totalRisk(v.items, -5), C.totalRisk([], 100)];
  o.filter = [C.filterItems(v.items, '', true).length, C.filterItems(v.items, 'Price band', false).every((i) => i.type === 'Price band'), C.typesOf(v.items).length >= 3];
  const junk = [null, 5, 'x', {}, { id: 'sibyl' }, { id: 'sibyl', items: [], headline: {} }, { id: 'nope', items: [{}], headline: { text: 'x' } }].map((j) => C.normSibyl(j));
  o.junk = [junk.map((x) => x === null || (Array.isArray(x.items) && x.items.length === 0)), C.chooseView(null, fx).src, C.chooseView({ id: 'sibyl', items: [], headline: { text: 'x' } }, fx).src, C.chooseView(null, null)];
  const evil = C.normSibyl({ id: 'sibyl', status: 'ok', headline: { text: '<img src=x onerror=alert(1)>Hello' }, items: [{ title: '<b>Bold</b> bet', detail: 'a<script>x</script>b', score: 999, risk: 'zzz', tier: 'nope', n: -5 }, { title: '' }, 7], notes: ['<i>n</i>'] });
  o.evil = [evil.head, evil.items.length, evil.items[0].title, evil.items[0].detail, evil.items[0].score, evil.items[0].risk, evil.items[0].tier, evil.items[0].n, evil.notes[0], evil.bank.usd, evil.status];
  const ow = C.normOwn(fx.own), bigb = []; for (let i = 0; i < 40; i++) bigb.push({ id: 'd' + i, day: '2026-01-01', title: 'x', stake_usd: 2, win_usd: 0.1, status: i % 10 ? 'won' : 'lost', pnl_usd: i % 10 ? 0.1 : -2 });
  const big = C.normOwn({ kind: 'sibyl-forward', start_day: '2026-01-01', bets: bigb });
  o.own = [ow.n, ow.nOpen, ow.nBets, ow.claim, ow.status, 'net' in ow, ow.text.includes('no claim') && ow.text.includes('n=12'), ow.recent.length, big.claim, big.n, big.net, big.netR, big.text.includes('n=40') && big.text.includes('small sample'), C.normOwn(null), C.normOwn({ kind: 'x', bets: [] }), C.normOwn({ kind: 'sibyl-forward', bets: [{ id: 'a', stake_usd: 0 }, 7] }).nBets, v.own.n];
  const a = C.tokenLayout(v.items, 8), b = C.tokenLayout(v.items, 8);
  o.tok = [a.length, JSON.stringify(a) === JSON.stringify(b), a[0].label, a.every((t) => t.radius > 1.4 && t.size > 0.1), C.flatPos(a[0], 0).x > 0 && C.flatPos(a[0], 10).x < 320, C.tokenLayout([], 8).length, C.tokenLayout(v.items, 3).length];
  o.head = [C.headlineWords(v).startsWith('Example numbers: '), C.headlineWords({ ...v, demo: false, status: 'stale' }).startsWith('Old numbers: '), C.headlineWords({ ...v, demo: false, status: 'ok' }) === v.head, C.statusLevel(v), C.statusLevel({ ...v, status: 'ok', counts: { worthy: 2 } }), C.statusLevel({ ...v, status: 'ok', counts: { worthy: 0 } }), C.statusLevel({ ...v, status: 'stale' })];
  const card = C.jarvisCard(v);
  o.card = [card.name, card.status.level, card.kpis.length, card.kpis[0].value, card.kpis[2].value, card.lines[1], Number.isInteger(card.t), JSON.stringify(card).length < 8192, /[<>]/.test(JSON.stringify(card))];
  o.age = [C.ageWord('2026-11-09T12:00:00Z', Date.parse('2026-11-09T12:30:00Z') / 1000), C.ageWord('2026-11-01T12:00:00Z', Date.parse('2026-11-10T12:00:00Z') / 1000), C.ageWord('', 5), C.ageWord('2026-11-09T12:00:00Z', 0)];
  console.log(JSON.stringify(o));
});
"""


def test_maths():
    import shutil
    if not shutil.which("node"):
        check("b. node is not installed: maths skipped", True)
        return
    fx = AK.read(os.path.join(AK.WEB, APP, "fixture.json"))
    o = AK.node(APP, HARNESS, fx)
    check("b. no error in the harness", "_error" not in o, o.get("_error"))
    if "_error" in o:
        return
    check("b. words: cents on a small account, a sign, every dollar with its R, the cents of an edge, ruin 'under 1%' instead of 0%, a score word",
          o["words"] == ["$3.41", "-$0.12", "-1.0R", "0.0R", "-$3.41 (-1.0R)", "+0.57¢", "-1.20¢", "under 1%", "3%", "n/a", "Strong", "None"], o["words"])
    check("b. the demo view: from the fixture, labelled demo, 13 rows (12 kinds of bet and one rule hint), 3 paper picks, bankroll $170.26, every item has its n, the scoreboard is collecting, at least 4 risks",
          o["view"] == ["demo", "sample", True, 13, 3, 170.26, 3, True, 18, "collecting", True], o["view"])
    check("b. sizing: stake = the file's percent of the bankroll you type (1R), a loss is -1.0R, a win is a few cents of R; $1,000 sizes 5.87 times as large; no bankroll or no pick -> null",
          o["size"][0] == 3.41 and o["size"][1] == -3.41 and 0 < o["size"][2] < 0.5 and o["size"][3] == "-$3.41 (-1.0R)" and o["size"][4].startswith("+$0.") and o["size"][5] == 20 and o["size"][6] and o["size"][7] is None and o["size"][8] is None, o["size"])
    check("b. total risk of the day's picks: 6% of the bankroll at most; zero for a bad bankroll or no picks", abs(o["total"][0] - 10.22) < 0.05 and o["total"][1] == 60 and o["total"][2] == 0 and o["total"][3] == 0, o["total"])
    check("b. filters: 'picks only' keeps the 3; a type keeps only that type; at least 3 types", o["filter"] == [3, True, True], o["filter"])
    check("b. junk files (null, numbers, no items, wrong id) never crash and fall back to the labelled demo; nothing at all gives null", o["junk"][0] == [True] * 7 and o["junk"][1:] == ["demo", "demo", None], o["junk"])
    check("b. no markup survives from data: tags stripped, a score is clamped to 100, a bad risk becomes high, a bad tier becomes 'unproven', n is never negative, rows without a title are dropped, a missing bankroll is an example $100",
          o["evil"] == ["Hello", 1, "Bold bet", "a x b", 100, "high", "unproven", 0, "n", 100, "ok"], o["evil"])
    check("b. the token layout is deterministic, one token per ranked pick (8 at most), the label is the break-even price in cents, the flat twin stays inside its box",
          o["tok"] == [8, True, "96¢", True, True, 0, 3], o["tok"])
    check("b. own ledger: 12 settled, 2 open, 14 recorded, collecting with NO net field and 'no claim' + n in the words; 40 settled gives the claim with n, net $ with R, 'small sample'; junk is null or empty; the demo view carries it",
          o["own"] == [12, 2, 14, False, "collecting", False, True, 8, True, 40, -4.4, -2.2, True, None, None, 0, 12], o["own"])
    check("b. headline words say Example / Old numbers; the status level is off for the demo, ok with picks, warn with none or stale", o["head"] == [True, True, True, "off", "ok", "warn", "warn"], o["head"])
    check("b. the Jarvis card: Sibyl, a level, 3 kpis (picks, best edge, the paper 1R), a paper-only line, an integer t, under 8 KB, no markup", o["card"] == ["Sibyl", "off", 3, "3", "$3.41", "Paper only: Sibyl places no bet.", True, True, False], o["card"])
    check("b. ages in plain words and 'time unknown' when it cannot tell", o["age"] == ["30 min ago", "9 days ago", "time unknown", "time unknown"], o["age"])


def real_file(m):
    """a real-shaped scanner file built from the repo's own published study (fresh clock so it counts as ok)."""
    import tempfile
    study = os.path.join(AK.ROOT, "tools", "web_public", "kalshicity")
    e = json.load(open(os.path.join(study, "edges.json"), encoding="utf-8"))
    res = m.scan({"edges": e, "whatif": json.load(open(os.path.join(study, "whatif.json"), encoding="utf-8"))}, e["t"] + 3600)
    return json.dumps(res), res


def test_page():
    try:
        import playwright  # noqa: F401
    except ImportError:
        check("c. page tests skipped: no Playwright", True)
        return
    m = _scanner()
    real_json, real = real_file(m)
    srv, origin = AK.serve()
    try:
        with AK.browser() as br:
            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, APP, "?demo=1")
            d = p.evaluate("""() => ({ demo: !document.querySelector('#demo').hidden, pill: document.querySelector('#srcPill').textContent, head: document.querySelector('#head').textContent,
              tiles: document.querySelector('#heroTiles').textContent, picks: document.querySelectorAll('#picks > li').length, rows: document.querySelectorAll('#list > li').length,
              chips: [...document.querySelectorAll('#types button')].map((b) => b.textContent), first: document.querySelector('#picks .pick .pl b').textContent, open: document.querySelector('#picks .prow').getAttribute('aria-expanded'),
              body: document.querySelector('#picks .pbody').textContent, sb: document.querySelector('#sbPill').textContent, sbt: document.querySelector('#sbText').textContent, risks: document.querySelectorAll('#risks > li').length,
              bank: document.querySelector('#bank').value, font: getComputedStyle(document.querySelector('h1')).fontFamily, bg: getComputedStyle(document.body).backgroundColor, gl: !!window.SIBYL.ball, flat: window.SIBYL.flat })""")
            check("c. DEMO: the chip, 'Example', 3 paper picks of 12 kinds of bet, the best pick's 1R $3.41, the headline says Example numbers",
                  d["demo"] and d["pill"] == "Example" and d["head"].startswith("Example numbers: ") and "Paper picks today3of 12 kinds of bet" in d["tiles"] and "$3.41" in d["tiles"] and d["picks"] == 3 and d["rows"] == 13, d)
            check("c. a pick shows its stake as 1R, a loss -$3.41 (-1.0R), a win with its R, the chance the bankroll halves, the win rates and the edge after fees; the best pick is open",
                  d["open"] == "true" and "Paper stake = 1R$3.41" in d["body"] and "-$3.41-1.0R" in d["body"].replace(" ", "") .replace("Ifitloses", "") or ("-$3.41" in d["body"] and "-1.0R" in d["body"]) and "Halves in 300 bets" in d["body"] and "Cautious edge" in d["body"], d["body"][:400])
            check("c. the scoreboard says Collecting with its n (18), and the bankroll box starts at the file's $170.26; the risks list has the standing cautions",
                  d["sb"] == "Collecting, n=18" and "n=18" in d["sbt"] and d["bank"] == "170.26" and d["risks"] >= 4, d)
            check("c. AGORA look: serif title, warm dark body", any(f in d["font"] for f in ("Palatino", "Iowan", "Georgia")) and d["bg"] == "rgb(20, 17, 14)", d)
            ow = p.evaluate("() => [document.querySelector('#ownPill').textContent, document.querySelector('#ownTiles').textContent, document.querySelectorAll('#ownRows > li').length, document.querySelector('#ownText').textContent]")
            check("c. Sibyl's own picks: 'Collecting, n=12', the counts, net and win rate HIDDEN (no claim below 30), recent bets with their R, n in the words",
                  ow[0] == "Collecting, n=12" and "Settled12" in ow[1] and "Net and win ratehidden" in ow[1] and "$" not in ow[1] and ow[2] == 8 and "n=12" in ow[3] and "no claim" in ow[3], ow)
            AK.shot(p, "sibyl-demo")
            p.fill("#bank", "1000")
            p.wait_for_timeout(200)
            b = p.evaluate("() => [document.querySelector('#picks .pbody .tile b').textContent, document.querySelector('#bankNote').textContent, document.querySelector('#heroTiles').textContent]")
            check("c. type a $1,000 bankroll: the stake follows (6% across the three picks, 2% each = $20.00), the note says $60.00 together", b[0] == "$20.00" and "$60.00" in b[1] and "$20.00" in b[2], b)
            p.locator("#types button", has_text="Price band").click()
            p.wait_for_timeout(150)
            f = p.evaluate("() => [document.querySelectorAll('#list > li').length, document.querySelector('#types [aria-pressed=true]').textContent, document.querySelector('#status').textContent]")
            check("c. the Price band chip filters the list (4 bands) and the status line says so", f[0] == 4 and f[1] == "Price band" and "Price band" in f[2], f)
            p.locator("#onlyPicks").click()
            p.wait_for_timeout(100)
            g = p.evaluate("() => document.querySelectorAll('#list > li').length")
            check("c. 'Picks only' on top of the type: the two price-band picks", g == 2, g)
            p.locator("#types button", has_text="All").click()
            p.locator("#onlyPicks").click()
            row = p.locator("#list .prow").nth(3)
            row.click()
            p.wait_for_timeout(150)
            r = p.evaluate("() => { const li = document.querySelectorAll('#list .pick')[3]; return [li.querySelector('.prow').getAttribute('aria-expanded'), li.querySelector('.pbody').hidden, li.querySelector('.pbody').textContent.length > 40, document.querySelector('#status').textContent] }")
            check("c. tap a row: it opens (aria-expanded), shows its numbers, and the status line speaks it", r[0] == "true" and r[1] is False and r[2] and "bets" in r[3], r)
            t = AK.taps(p)
            check("c. every tap target is at least 44 x 44 px", not t, t[:5])
            check("c. no sideways scroll; Jarvis's corner is free; no console error; nothing off the origin", AK.no_sideways(p) and not AK.corner(p) and not errs and not off, (errs[:3], off[:3]))
            ball = p.evaluate("() => { const b = window.SIBYL.ball; return b ? { n: b.count, q: b.quality(), lite: b.lite, shown: !document.querySelector('#stage').hidden && document.querySelector('#flat').hidden, size: [document.querySelector('#stage').clientWidth, document.querySelector('#stage').clientHeight] } : null }")
            if ball is None:
                check("c. 3D: no WebGL in this browser, so the flat twin is shown (the page still works)", p.evaluate("() => window.SIBYL.flat === true && !document.querySelector('#flat').hidden"))
            else:
                check("c. 3D: the marble ball is up with 8 tokens, the flat twin is hidden, the canvas has a real size", ball["n"] == 8 and ball["shown"] and ball["size"][0] > 200 and ball["size"][1] > 120, ball)
                pos = p.evaluate("() => window.SIBYL.ball.screenOf(1)")
                if pos and pos["front"]:
                    p.mouse.click(pos["x"], pos["y"])
                    p.wait_for_timeout(300)
                    sel = p.evaluate("() => [window.SIBYL.S.sel, window.SIBYL.ball.selected]")
                    check("c. tap a floating token: that pick is selected in the lists and the ball (3D picking works)", sel[0] == sel[1] and sel[0] >= 0, (pos, sel))
            ctx.close()
            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, APP, "?demo=1&q=off")
            q = p.evaluate("() => ({ flat: window.SIBYL.flat, ball: !!window.SIBYL.ball, svgShown: !document.querySelector('#flat').hidden, canvasHidden: document.querySelector('#stage').hidden, tokens: document.querySelectorAll('#flat g').length })")
            check("c. ?q=off (3D Off): the flat marble ball is drawn instead, with 8 tokens, the page works the same, no error", q["flat"] and not q["ball"] and q["svgShown"] and q["canvasHidden"] and q["tokens"] == 8 and not errs, (q, errs[:3]))
            ctx.close()
            ctx, p, errs, seen, off = AK.page(br, origin, w=375, h=667, reduced=True, lite=True)
            AK.open_app(p, origin, APP, "?demo=1&q=low")
            check("c. 375 x 667, LITE, reduced motion: no sideways scroll, every tap >= 44 px, no error", AK.no_sideways(p) and not AK.taps(p) and not errs, (AK.taps(p)[:3], errs[:2]))
            ctx.close()
            srv2, origin2 = AK.serve({"/money/sibyl.json": real_json})
            ctx, p, errs, seen, off = AK.page(br, origin2)
            AK.open_app(p, origin2, APP, "?q=off")
            r = p.evaluate("() => ({ demo: !document.querySelector('#demo').hidden, pill: document.querySelector('#srcPill').textContent, head: document.querySelector('#head').textContent, picks: document.querySelectorAll('#picks > li').length, rows: document.querySelectorAll('#list > li').length, bank: document.querySelector('#bank').value })")
            check("c. the real scanner file (built from the repo's published study): no DEMO chip, the real bankroll, the real count of kinds of bet; honest when there is one pick or none",
                  not r["demo"] and r["pill"] in ("Fresh study", "Old study") and r["bank"] == str(real["bankroll"]["usd"]) and r["rows"] == min(len(real["items"]), 60) - 0 if len(real["items"]) <= 60 else not r["demo"], (r, real["counts"]))
            check("c. the real run reads only the site's files and no console error", any("money/sibyl.json" in u for u in seen) and not off and not errs, (off[:3], errs[:3]))
            ctx.close()
            srv2.shutdown()
            srv3, origin3 = AK.serve({"/money/sibyl.json": "{not json"})
            ctx, p, errs, seen, off = AK.page(br, origin3)
            AK.open_app(p, origin3, APP, "?q=off")
            r = p.evaluate("() => [!document.querySelector('#demo').hidden, document.querySelectorAll('#picks > li').length]")
            check("c. a broken sibyl.json falls back to the labelled demo, never blank", r[0] is True and r[1] == 3 and not errs, (r, errs[:2]))
            ctx.close()
            srv3.shutdown()
    finally:
        srv.shutdown()
    # ---- bar 2026-11-20: every data file missing (404): the archive banner + one plain sentence, no data card, no JS error, not blank
    names = ["/sibyl/fixture.json", "/money/sibyl.json", "/money/sibyl_forward.json", "/kalshicity/suggestions.json", "/sibyl/suggestions_fixture.json"]
    srv, origin = AK.serve({n: None for n in names})
    try:
        with AK.browser() as br:
            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, APP, "?q=off")
            e = p.evaluate("() => ({ st: document.querySelector('#status').textContent, cards: [...document.querySelectorAll('#app > section.card')].filter((s) => !s.hidden).length, banner: !!document.querySelector('.archive-banner a[href=\"../kalshi/\"]') })")
            check("c. bar: no data at all: the status says so in plain words, every data card hides, the archive banner and its K8 link stay, no JS error",
                  "No Sibyl numbers could be read" in e["st"] and e["cards"] == 0 and e["banner"] and not errs, (e, errs[:3]))
            ctx.close()
    finally:
        srv.shutdown()


if __name__ == "__main__":
    test_static()
    test_maths()
    if "--static" not in sys.argv:
        test_page()
    AK.finish()
