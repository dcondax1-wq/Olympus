"""DIONYSUS, the OLYMPUS Kalshi desk (tools/web_public/dionysus/, AGORA look, 2026-11-09): the Kalshi bot's numbers, the guard, the what-if, the scan highlights. Suggestions only.

  a. static: the files, the kit lines, the AGORA look, read only (the one web address it may read is the public Kalshi feed), the Jarvis card, the manifest, the DEMO fixture
  b. the maths in node (dionysuscore.js): cents + R words, the feed checker (hostile input), the source order (feed, site mirror, demo), the guard, bets, the what-if, the scan highlights
  c. Chromium 390 x 844 (and 375 x 667): the DEMO desk, the site mirror when the live feed is unreachable, the live feed (mocked), what-if chips, LITE / reduced motion, taps >= 44 px, no console error
    python -X utf8 -m tests.test_dionysus_page            (--static: parts a and b only)
"""
from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import agora_kit as AK  # noqa: E402

APP, NAME = "dionysus", "Dionysus"
check = AK.check
SITE_EDGES = os.path.join(AK.WEB, "kalshicity", "edges.json")
SITE_WHATIF = os.path.join(AK.WEB, "kalshicity", "whatif.json")


def test_static():
    AK.static_kit(APP, NAME, reads=("../kalshicity/edges.json", "../kalshicity/whatif.json"))
    js = AK.read(os.path.join(AK.WEB, APP, "dionysus.js"))
    check("a. the bot's feed is the SAME file the Kalshi page reads, this site's ../kalshi.json (the kalshi-feed repo is retired, polish2 2026-11-19), a plain GET; no key, no header, no POST, no web address",
          "const SITE_FEED = '../kalshi.json';" in js and "kalshi-feed/main" not in js and "githubusercontent" not in js and "Authorization" not in js and "headers" not in js.replace("cache: 'no-cache'", ""))
    html = AK.read(os.path.join(AK.WEB, APP, "index.html"))
    check("a. 'Suggestions only' is said on the page, and nothing on it can place or change a bet (no order / buy / sell words in the code)",
          "Suggestions only" in html and not re.search(r"\b(placeOrder|createOrder|/portfolio/orders|\.post\(|method:)", js))
    check("a. the page order: the balance, the guard, bets, the what-if, the scan", html.index('id="bal"') < html.index('id="guardCard"') < html.index('id="open"') < html.index('id="wiCard"') < html.index('id="scan"'))
    fx = json.loads(AK.read(os.path.join(AK.WEB, APP, "fixture.json")))
    check("a. the fixture has a feed (balance, positions, trades, days), an edges mirror (regime, lists) and a what-if with a picked set", fx["feed"]["balance"] > 0 and fx["feed"]["positions"] and fx["feed"]["trades"] and len(fx["feed"]["days"]) >= 7 and fx["edges"]["lists"]["do_more"] and fx["whatif"]["what_if"]["pick"])


HARNESS = r"""
const fs = require('fs');
import(process.argv[2]).then((C) => {
  const fx = JSON.parse(fs.readFileSync(process.argv[3], 'utf8')), edges = JSON.parse(fs.readFileSync(process.argv[4], 'utf8')), wi = JSON.parse(fs.readFileSync(process.argv[5], 'utf8')), o = {};
  o.words = [C.usd(55.8136), C.usd(-81.77), C.usd(-0.001), C.usd(1234.5), C.usd('x'), C.usdS(3.4), C.usdS(-18.6), C.usdS(0), C.rWord(-81.77, 10.8), C.rWord(3.4, 10), C.rWord(5, 0), C.both(-18.6, 10.01), C.cents(0.0149), C.cents(-0.0111), C.cents(0), C.pct(0.1325), C.pct(0.365, 1), C.pct(null)];
  o.labels = [C.labelWords('95-97c'), C.labelWords('<20c'), C.labelWords('99c+'), C.labelWords('at 60-80c'), C.labelWords('XRP'), C.labelWords(null), C.labelWords('<b>x</b> 5c')];
  o.age = [C.ageWord(1000, 1030), C.ageWord(1000, 1000 + 45 * 60), C.ageWord(1000, 1000 + 3 * 3600), C.ageWord(1000, 1000 + 3 * 86400), C.ageWord(null, 5), C.ageWord(5, 0)];
  const f = C.normFeed(fx.feed);
  o.feed = { src: f.src, bal: f.balance, run: f.running, today: f.today, week: f.week, total: f.total, stake: f.stake, days: f.days.length, pos: f.positions.map((p) => [p.side, p.contracts, p.risk]), tr: f.trades.map((t) => t.t), first: [f.trades[0].pnl, f.trades[0].risk, C.betR(f.trades[0])], loss: [f.trades[1].pnl, f.trades[1].risk, C.betR(f.trades[1])], strat: f.strategies.length };
  const evil = [C.normFeed(null), C.normFeed('x'), C.normFeed({}), C.normFeed({ balance: 'abc' }), C.normFeed({ balance: '12.5', positions: [null, 5, { title: '<i>x</i>', contracts: 'y' }], trades: [{ pnl: 'z' }, { pnl: 1, t: 1, contracts: 2, price: 0.5, title: 'a<b>' }], days: [['bad', 1], ['2026-11-01', 'x'], ['2026-11-02', 2.346]] })];
  o.evil = [evil[0], evil[1], evil[2], evil[3], evil[4].balance, evil[4].positions.length, evil[4].positions[0].title, evil[4].trades.length, evil[4].trades[0].title, evil[4].days, evil[4].stake, evil[4].running, evil[4].name];
  const s = C.bookFromEdges(edges);
  o.site = [s.src, s.balance, s.status, s.running, s.week, s.total, s.pnl7, s.worst, s.best, s.days.length > 10, C.bookFromEdges({}), C.bookFromEdges(null), C.bookFromEdges({ book: { balance: 'x' } })];
  const ch = (a, b, c) => { const x = C.chooseBook(a, b, c); return x ? [x.src, x.balance] : null; };
  o.choose = [ch(fx.feed, edges, fx), ch(null, edges, fx), ch(null, null, fx), ch({ bad: 1 }, { bad: 1 }, fx), ch(null, null, null), ch(null, null, { feed: { balance: 'x' } })];
  // the guard
  const dem = C.chooseBook(fx.feed, null, null), mk = (x) => ({ ...dem, ...x });
  const g1 = C.guard(s, edges.regime), g2 = C.guard(mk({ running: true, days: [] }), { pnl7: -14.3, paused: false }), g3 = C.guard(mk({ days: [['2026-11-01', 3], ['2026-11-02', 4.5]] }), null), g4 = C.guard(mk({ days: [] }), null);
  o.guard = [[g1.level, g1.title, g1.p7, g1.text], [g2.level, g2.title, g2.text], [g3.level, g3.p7, g3.text], [g4.level, g4.title, g4.p7], C.sumDays([['a', 1], ['b', 2], ['c', 3]], 2)];
  o.guardFallback = C.guard(dem, null).p7;
  // what-if
  const w = C.normWhatIf(wi);
  o.wi = { n: w.n, enough: w.enough, pick: w.pick, sets: w.sets.map((x) => [x.id, x.gain, x.ruinPct, x.halfPct, x.isBase, x.isPick]), rec: w.recommend.startsWith('The data supports A'), why: w.why.startsWith('You are down $81.77'), none: [C.normWhatIf(null), C.normWhatIf({}), C.normWhatIf({ what_if: { sets: [] } }), C.normWhatIf({ what_if: { sets: [{ net: 'x' }] } })] };
  // scan
  const hl = C.highlights(edges);
  o.scan = { more: hl.more.map((x) => [x.label, x.n, C.edgeLine(x)]), stop: hl.stop.map((x) => x.label), watch: hl.watch.length, proven: hl.proven, edges: hl.edges, none: [C.highlights(null), C.highlights({ edges: [], lists: {} }), C.highlights({ edges: 5, lists: 5 })] };
  const card = C.jarvisCard(dem, g2);
  o.card = [card.name, card.status.level, card.kpis.map((k) => k.value).join('|'), card.lines.every((l) => l.length <= 120), card.lines[1], Object.keys(card).sort().join()];
  console.log(JSON.stringify(o));
});
"""


def test_maths():
    o = AK.node(APP, HARNESS, os.path.join(AK.WEB, APP, "fixture.json"), SITE_EDGES, SITE_WHATIF)
    if o is None:
        check("b. node is not installed: maths skipped", True)
        return
    check("b. no error in the harness", "_error" not in o, o.get("_error"))
    if "_error" in o:
        return
    check("b. money words with cents and R: $55.81, -$81.77, tiny -> $0.00, $1,234.50, junk -> $0.00, +$3.40, -$18.60, $0.00, '-7.6R', '+0.3R', no risk -> 0.0R, '-$18.60 (-1.9R)', cents +1.5¢ / -1.1¢, percent",
          o["words"] == ["$55.81", "-$81.77", "$0.00", "$1,234.50", "$0.00", "+$3.40", "-$18.60", "$0.00", "-7.6R", "+0.3R", "0.0R", "-$18.60 (-1.9R)", "+1.5¢", "-1.1¢", "0.0¢", "13%", "36.5%", ""], o["words"])
    check("b. scan labels in plain words: 95–97¢, under 20¢, 99¢ and up, 'at 60-80c' -> '60–80¢ bets', plain text stays, null -> empty, tags stripped",
          o["labels"] == ["95–97¢", "under 20¢", "99¢ and up", "60–80¢ bets", "XRP", "", "x 5¢"], o["labels"])
    check("b. feed age: just now, 45 min ago, 3 h ago, 3 days ago, unknown time", o["age"] == ["just now", "45 min ago", "3 h ago", "3 days ago", "time unknown", "time unknown"], o["age"])
    f = o["feed"]
    check("b. the feed: balance $170.26, running, today +3.4 / week -18.6 / total -89.74, one bet averages $10.01 (staked / bets), 9 days, open bets with what they risk (8 x 96¢ = $7.68), newest settled bet first, a bet's R = result over risk",
          f["src"] == "feed" and f["bal"] == 170.26 and f["run"] is True and f["today"] == 3.4 and f["week"] == -18.6 and f["total"] == -89.74 and f["stake"] == 10.01 and f["days"] == 9 and f["pos"] == [["yes", 8, 7.68], ["no", 6, 5.7]]
          and f["tr"] == sorted(f["tr"], reverse=True) and f["first"] == [0.4, 9.6, "0.0R"] and f["loss"] == [-8.46, 8.46, "-1.0R"] and f["strat"] == 2, f)
    e = o["evil"]
    check("b. a hostile feed: null / text / empty / no balance -> null; a thin one is cleaned (string balance read, junk positions and trades dropped, tags removed, bad days dropped, 2.346 -> 2.35, not running)",
          e[:4] == [None] * 4 and e[4] == 12.5 and e[5] == 1 and "<" not in e[6] and e[7] == 1 and "<" not in e[8] and e[9] == [["2026-11-02", 2.35]] and e[10] == 1.0 and e[11] is False and e[12] == "Kalshi bot", e)
    s = o["site"]
    check("b. the site's own mirror (kalshicity/edges.json 'book'): $55.81, Paused (not running), week -3.30, total -81.77, last 7 days -56.64, worst day -101.64, best 81.18, 30 days; empty / junk -> null",
          s[:9] == ["site", 55.81, "Paused", False, -3.3, -81.77, -56.64, -101.64, 81.18] and s[9] is True and s[10:] == [None, None, None], s)
    check("b. which numbers win: the live feed, then the site's copy, then the labelled demo; junk everywhere -> demo; no fixture either -> nothing (the page then says so)",
          o["choose"] == [["feed", 170.26], ["site", 55.81], ["demo", 170.26], ["demo", 170.26], None, None], o["choose"])
    g = o["guard"]
    check("b. the guard: the site's regime (-$56.64, paused) = 'The guard has the bot resting' (bad); a losing week while the bot still bets = warn; a good week = calm with its R; no days = no reading; the fallback adds the last 7 days of the feed",
          g[0][:3] == ["bad", "The guard has the bot resting", -56.64] and "lost $56.64" in g[0][3] and "paused until the week turns" in g[0][3] and g[1][:2] == ["warn", "A losing week"] and "still betting" in g[1][2] and g[2][:2] == ["ok", 7.5] and "+$7.50" in g[2][2]
          and g[3] == ["off", "No guard reading yet", None] and g[4] == 5 and o["guardFallback"] == -6.7, g)
    w = o["wi"]
    check("b. the what-if on the site's file: 4 rule sets, 'as it is' is the base (gain 0, 13% ruin, 37% lose half), A is $248.30 better with 0% ruin and is the picked set, the recommendation and the 'why' text come through; no / empty / junk file -> null",
          w["n"] == 1836 and w["enough"] and w["pick"] == "A" and w["sets"][0] == ["asis", 0, 13, 37, True, False] and w["sets"][1] == ["A", 248.3, 0, 4, False, True] and len(w["sets"]) == 4 and w["rec"] and w["why"] and w["none"] == [None] * 4, w)
    sc = o["scan"]
    check("b. the scan: the 'do more' bet in plain words with its numbers, the 'stop' bet, three watch items, 18 of 49 proven; no / empty / junk file -> null",
          sc["more"][0][0] == "95–97¢ bets" and sc["more"][0][1] == 715 and sc["more"][0][2].startswith("95–97¢ bets: +1.5¢ per $1 over 715 bets (+$136.98 so far)") and sc["stop"] == ["XRP"] and sc["watch"] == 3 and sc["proven"] == 18 and sc["edges"] == 49 and sc["none"] == [None] * 3, sc)
    c = o["card"]
    check("b. the Jarvis card: Dionysus, level from the guard, balance / today / week, lines <= 120 and 'suggestions only', no stray keys", c[0] == "Dionysus" and c[1] == "warn" and c[2] == "$170.26|+$3.40|-$18.60" and c[3] and c[4].startswith("Suggestions only") and c[5] == "kpis,lines,name,status,t,theme,v", c)


def feed_json(balance=321.5):
    return json.dumps({"v": 3, "name": "Kalshi Edge v2", "mode": "live", "status": "Running", "running": True, "t": 1793671200, "balance": balance, "today_pnl": 2.0, "week_pnl": 12.5, "total_pnl": 40.0,
                       "positions": [{"title": "Bitcoin above target", "side": "yes", "contracts": 5, "avg_price": 0.96}],
                       "trades": [{"t": 1793600000, "title": "Gold above target", "side": "no", "contracts": 10, "price": 0.95, "pnl": 0.5}],
                       "days": [["2026-11-01", 3.0], ["2026-11-02", 4.5], ["2026-11-03", -1.0]], "stats": {"trades": 100, "staked": 1000.0}})


def test_page():
    try:
        import playwright  # noqa: F401
    except ImportError:
        check("c. page tests skipped: no Playwright", True)
        return
    srv, origin = AK.serve()
    try:
        with AK.browser() as br:
            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, APP, "?demo=1&at=2026-11-05T12:00:00Z")
            d = p.evaluate("""() => ({ demo: !document.querySelector('#demo').hidden, name: document.querySelector('#botName').textContent, pill: document.querySelector('#botPill').textContent, bal: document.querySelector('#bal').textContent, tiles: document.querySelector('#heroTiles').innerText, src: document.querySelector('#srcNote').textContent,
              guard: document.querySelector('#guardTitle').textContent, gl: document.querySelector('#guardCard').dataset.level, open: document.querySelectorAll('#open li').length, recent: document.querySelectorAll('#recent li').length, r0: document.querySelector('#recent li b').textContent,
              chips: [...document.querySelectorAll('#sets button')].map((b) => b.textContent), on: document.querySelector('#sets [aria-pressed=true]').textContent, wiText: document.querySelector('#wiText').textContent, scan: document.querySelector('#scan').innerText,
              banner: document.body.innerText.includes('Suggestions only'), font: getComputedStyle(document.querySelector('h1')).fontFamily, reads: performance.getEntriesByType('resource').filter((r) => /kalshicity/.test(r.name)).length }) """)
            check("c. DEMO (?demo=1): the chip, 'Example', $170.26 with today / week / all time and their R, the guard is amber 'A losing week', 2 open bets, 5 settled with their R, 'Suggestions only', never reads the site's files",
                  d["demo"] and d["pill"] == "Example" and d["bal"] == "$170.26" and "+$3.40" in d["tiles"] and "-$18.60" in d["tiles"] and "-$89.74" in d["tiles"] and "R" in d["tiles"] and d["gl"] == "warn" and d["guard"] == "A losing week" and d["open"] == 2 and d["recent"] == 5 and "(0.0R)" in d["r0"]
                  and d["banner"] and d["reads"] == 0 and "Example numbers" in d["src"], d)
            check("c. the what-if is on the picked set A ('A · skip the 90–95¢ band'), 'As it is' and B are chips, the text says how much better; the scan shows 'Worth a paper test' with 95–97¢ bets",
                  d["chips"] == ["As it is", "A", "B"] and d["on"] == "A" and "better than the bot as it is" in d["wiText"] and "Worth a paper test" in d["scan"] and "95–97¢ bets" in d["scan"] and "Worth avoiding" in d["scan"], d)
            check("c. AGORA look: a serif title", any(f in d["font"] for f in ("Palatino", "Iowan", "Georgia")))
            AK.shot(p, "dionysus-demo")
            p.locator("#sets [data-id=B]").click()
            p.wait_for_timeout(150)
            b = p.evaluate("() => [document.querySelector('#wiName').textContent, document.querySelector('#wiTiles').innerText, document.querySelector('#status').textContent, document.querySelector('#sets [aria-pressed=true]').textContent]")
            check("c. tap B: its name, net +$79.28 style numbers, worst dip, chance of ruin, the status line is spoken", "B ·" in b[0] and "Past bets, net" in b[1] and "Chance of ruin" in b[1] and "B · only 95" in b[2] and b[3] == "B", b)
            check("c. every tap target is at least 44 x 44 px", not AK.taps(p), AK.taps(p)[:4])
            check("c. no sideways scroll; Jarvis's corner is free; no console error; nothing off the origin", AK.no_sideways(p) and not AK.corner(p) and not errs and not off, (errs[:3], off[:3]))
            ctx.close()
            # ---- no kalshi.json on the site (404 here): the site's kalshicity mirror takes over, labelled
            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, APP, "?at=2026-11-05T12:00:00Z")
            s = p.evaluate("""() => ({ demo: !document.querySelector('#demo').hidden, pill: document.querySelector('#botPill').textContent, bal: document.querySelector('#bal').textContent, src: document.querySelector('#srcNote').textContent, guard: document.querySelector('#guardTitle').textContent,
              gl: document.querySelector('#guardCard').dataset.level, open: document.querySelector('#open').textContent, wi: document.querySelector('#sets [aria-pressed=true]').textContent, scan: document.querySelector('#scan').innerText.includes('95–97¢ bets') })""")
            check("c. the feed was asked on the site (../kalshi.json, absent here), so the kalshicity copy is shown: no DEMO chip, $55.81, 'Paused', 'the site's copy', the guard says the bot is resting, the real what-if (A) and scan",
                  any(u.split("?")[0].endswith("/kalshi.json") for u in seen) and not off and not s["demo"] and s["bal"] == "$55.81" and s["pill"] == "Paused" and "site's copy" in s["src"] and s["guard"] == "The guard has the bot resting" and s["gl"] == "bad" and "live feed" in s["open"] and s["wi"] == "A" and s["scan"], (s, off[:2]))
            ctx.close()
            # ---- the live feed answers (mocked)
            ctx, p, errs, seen, off = AK.page(br, origin, mock={"/kalshi.json": feed_json()})
            AK.open_app(p, origin, APP, "?at=2026-11-05T12:00:00Z")
            l = p.evaluate("""() => ({ demo: !document.querySelector('#demo').hidden, pill: document.querySelector('#botPill').textContent, bal: document.querySelector('#bal').textContent, src: document.querySelector('#srcNote').textContent, tiles: document.querySelector('#heroTiles').innerText,
              open: document.querySelector('#open').innerText, recent: document.querySelector('#recent').innerText, guard: document.querySelector('#guardTitle').textContent })""")
            check("c. the live feed (mocked): no DEMO chip, 'Running', $321.50, 'Live feed', today +$2.00 (+0.2R) with 1R = $10.00, the open bet risks $4.80, the settled bet with its R, the guard from the site's regime",
                  not l["demo"] and l["pill"] == "Running" and l["bal"] == "$321.50" and l["src"].startswith("Live feed") and "+$2.00" in l["tiles"] and "+0.2R" in l["tiles"] and "risking $4.80" in l["open"] and "+$0.50 (+0.1R)" in l["recent"] and "Gold above target" in l["recent"], l)
            check("c. a mocked feed is the only thing that left the page's origin; no console error", len(p.mocked) == 1 and not errs, (p.mocked, errs[:3]))
            ctx.close()
            ctx, p, errs, seen, off = AK.page(br, origin, w=375, h=667, reduced=True, lite=True)
            AK.open_app(p, origin, APP, "?demo=1&q=low")
            check("c. 375 x 667, LITE, reduced motion: no sideways scroll, every tap >= 44 px, no error", AK.no_sideways(p) and not AK.taps(p) and not errs, (AK.taps(p)[:3], errs[:2]))
            ctx.close()
    finally:
        srv.shutdown()


if __name__ == "__main__":
    test_static()
    test_maths()
    if "--static" not in sys.argv:
        test_page()
    AK.finish()
