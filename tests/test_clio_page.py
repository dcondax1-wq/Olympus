"""CLIO, the OLYMPUS research library (tools/web_public/clio/, AGORA look, 2026-11-09): browse and search the write-ups the site publishes, best and worst ideas by $ a month, a plain reader.

  a. static: the files, the kit lines, the AGORA look, read only (it fetches ../writeups/<slug>.md only for a slug that passed the slug check), the Jarvis card, the manifest, the DEMO fixture
  b. the maths in node (cliocore.js): the $ a month reader, the index checker (three shapes, hostile input), the verdict groups, search, ideas, the plain markdown reader
  c. Chromium 390 x 844 (and 375 x 667): the DEMO library, the real index (writeups/index.json, and the data.json fallback), search, groups, sort, the reader sheet, LITE / reduced motion, taps >= 44 px
    python -X utf8 -m tests.test_clio_page            (--static: parts a and b only)
"""
from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import agora_kit as AK  # noqa: E402

APP, NAME = "clio", "Clio"
check = AK.check


def test_static():
    AK.static_kit(APP, NAME, reads=("../writeups/index.json", "../data.json"))
    js = AK.read(os.path.join(AK.WEB, APP, "clio.js"))
    check("a. the reader fetches only ../writeups/<slug>.md, only after the slug check (a-z, 0-9, hyphens) and with the slug URL-encoded; nothing else is fetched by a built address",
          js.count("fetch(") == 2 and "'../writeups/' + encodeURIComponent(slug) + '.md'" in js and "if (!C.isSlug(slug)) return null;" in js)
    html = AK.read(os.path.join(AK.WEB, APP, "index.html"))
    check("a. the page: a search box with a label, the verdict chips, the ideas, the list, a dialog sheet for the reader (aria-modal, a Close button)",
          'type="search"' in html and 'for="q"' in html and 'id="groups"' in html and 'id="best"' in html and 'id="list"' in html and 'role="dialog"' in html and 'aria-modal="true"' in html and 'id="shClose"' in html)
    fx = json.loads(AK.read(os.path.join(AK.WEB, APP, "fixture.json")))
    ids = [w["slug"] for w in fx["writeups"]]
    check("a. the fixture: 10 example write-ups (slugs demo-*), all verdict groups, some with a $ a month in their own words, positive and negative, and a body for the reader",
          len(ids) == 10 and all(re.fullmatch(r"demo-[a-z-]+", i) for i in ids) and any(w.get("body") for w in fx["writeups"]) and any("-$" in w["summary"] for w in fx["writeups"]) and all(w["title"].startswith("Example") for w in fx["writeups"]))


HARNESS = r"""
const fs = require('fs');
import(process.argv[2]).then((C) => {
  const fx = JSON.parse(fs.readFileSync(process.argv[3], 'utf8')), o = {};
  o.pm = ['$823 a month', '-$51 a month', '−$51 a month', 'about $4,467 / mo', 'x $2,670/mo', '+$100 per month', '$1,234.50 a month', 'no money here', '$5 a monthly', '$12 a year', '', null, 'lost -$640 a month and $30 a month'].map(C.perMonth);
  o.words = [C.money(2100), C.moneyS(-640), C.moneyS(0), C.dayWord('2026-11-04'), C.dayWord('x')];
  o.groups = ['adopt-candidate (one)', 'Adopted', 'live now', 'promising - x', 'finding', 'rejected - costs', 'dead end', 'info - none', 'reference', 'archive', 'zzz', '', null].map(C.groupOf);
  const ix = C.normIndex(fx);
  o.fx = { n: ix.length, first: ix[0].slug, last: ix[ix.length - 1].slug, sorted: ix.every((r, i) => i === 0 || ix[i - 1].date >= r.date), pm: Object.fromEntries(ix.map((r) => [r.slug.replace('demo-', ''), r.pm])), groups: C.counts(ix), body: ix.filter((r) => r.body).length, runs: ix[0].runs };
  const rec = (slug, extra) => ({ slug, title: 'T ' + slug, summary: 's', status: 'info', date: '2026-01-01', ...extra });
  const shapes = [C.normIndex({ writeups: [rec('a')] }), C.normIndex({ docs: { writeups: [rec('b')] } }), C.normIndex([rec('c')])];
  o.shapes = shapes.map((x) => x && x[0].slug);
  const evil = C.normIndex({ writeups: [null, 5, 'x', rec('Bad Slug'), rec('../x'), rec('a/b'), rec(''), rec('ok-1', { title: '<b>Bold</b> <script>x</script>idea' }), rec('ok-1'), rec('ok-2', { title: '   ' }), rec('ok-3', { date: 'yesterday', status: 'ADOPT-candidate', summary: 'y'.repeat(900) }),
    rec('ok-4', { usd_month: '$300', summary: 'made $5 a month' }), rec('ok-5', { summary: 'a <i>b</i> $70 a month', status: 'rejected - $9 a month' }), rec('ok-6', { summary: 'none', title: 'about $44 a month' }), rec('ok-7', { runs: 'x', words: 'y', body: 'z'.repeat(20000) })] });
  const by = Object.fromEntries(evil.map((r) => [r.slug, r]));
  o.evil = { slugs: evil.map((r) => r.slug).sort(), title: by['ok-1'].title, date: by['ok-3'].date, group: by['ok-3'].group, sum: by['ok-3'].summary.length, pm4: by['ok-4'].pm, pm5: [by['ok-5'].pm, by['ok-5'].summary], pm6: by['ok-6'].pm, ok7: [by['ok-7'].runs, by['ok-7'].words, by['ok-7'].body.length, by['ok-7'].family],
    none: [C.normIndex(null), C.normIndex('x'), C.normIndex({}), C.normIndex({ writeups: [] }), C.normIndex({ writeups: [null] }), C.normIndex({ docs: 5 })] };
  const big = C.normIndex({ writeups: Array.from({ length: 500 }, (_, i) => rec('w-' + i, { date: '2026-01-01' })) });
  o.cap = big.length;
  // search / filter / sort
  const V = (opts) => C.view(ix, opts).map((r) => r.slug.replace('demo-', ''));
  o.tok = [C.tokens('Size  Friday!!'), C.tokens(''), C.tokens(null), C.tokens('a b c d e f g h i j k').length, C.tokens('$2,100 a-b 58%')];
  o.view = { all: V({}).length, adopt: V({ group: 'adopt' }), rejected: V({ group: 'rejected' }).length, q1: V({ q: 'friday' }), q2: V({ q: 'size stop' }), q3: V({ q: 'SIZE nothing' }), q4: V({ q: 'timing' }), q5: V({ q: 'rejected', group: 'rejected' }).length, q6: V({ q: '2026-11-04' }),
    money: V({ sort: 'money' }), old: V({ sort: 'old' })[0], moneyGroup: V({ sort: 'money', group: 'rejected' }) };
  const id = C.ideas(ix);
  o.ideas = { best: id.best.map((r) => [r.slug.replace('demo-', ''), r.pm]), worst: id.worst.map((r) => [r.slug.replace('demo-', ''), r.pm]), ranked: id.ranked, unranked: id.unranked, empty: [C.ideas([]).best.length, C.ideas([]).worst.length] };
  // the markdown reader
  const md = '---\ntitle: x\nfamily: y\n---\n\n# Title **bold**\n\nA [link](http://evil.example/x) and `code` <script>bad()</script> text.\n\n```\nhidden code\n```\n\n- first item\n* second item\n\n| A | B |\n|---|---|\n| one | two |\n\n<!-- comment -->\n<div>\n\nlast line';
  const bl = C.plainMd(md);
  o.md = { kinds: bl.map((b) => b.k).join(','), texts: bl.map((b) => b.t), cap: C.plainMd('word '.repeat(2000), 300).slice(-1)[0].t.startsWith('…the rest'), capN: C.plainMd('para one\n'.repeat(500), 100).length, empty: [C.plainMd('').length, C.plainMd(null).length, C.plainMd('---\nx\n---').length] };
  o.slug = [C.isSlug('demo-a'), C.isSlug('Demo'), C.isSlug('../x'), C.isSlug(''), C.isSlug(5), C.isSlug('a'.repeat(81)), C.isSlug('2026-11-03-money-plan')];
  const card = C.jarvisCard(ix, true), card2 = C.jarvisCard(ix, false);
  o.card = [card.name, card.status.label, card2.status.label, card.kpis.map((k) => k.value).join('|'), card.lines[0], card.lines[0].length <= 120, C.jarvisCard(C.normIndex({ writeups: [rec('z')] }), false).lines[0]];
  console.log(JSON.stringify(o));
});
"""


def test_maths():
    o = AK.node(APP, HARNESS, os.path.join(AK.WEB, APP, "fixture.json"))
    if o is None:
        check("b. node is not installed: maths skipped", True)
        return
    check("b. no error in the harness", "_error" not in o, o.get("_error"))
    if "_error" in o:
        return
    check("b. the '$ a month' reader: quotes the FIRST figure in the text, with its sign (-, unicode minus, +), commas, cents, '/ mo' and 'per month'; none -> null; 'a year' is not a month; 'a monthly' is not a month",
          o["pm"] == [823, -51, -51, 4467, 2670, 100, 1234.5, None, None, None, None, None, -640], o["pm"])
    check("b. words: $2,100, -$640, $0, 'Nov 4, 2026', junk -> empty", o["words"] == ["$2,100", "-$640", "$0", "Nov 4, 2026", ""], o["words"])
    check("b. verdict groups: adopt (adopt-candidate, adopted, live), promising, finding, rejected (dead), info (reference), archive, other; junk -> other",
          o["groups"] == ["adopt", "adopt", "adopt", "promising", "finding", "rejected", "rejected", "info", "info", "archive", "other", "other", "other"], o["groups"])
    f = o["fx"]
    check("b. the fixture index: 10 records, newest first, 2 adopt / 2 promising / 1 finding / 4 rejected / 1 reference, one body; the $ a month of each comes from its own sentence (+2,100 size, -640 Friday, -1,200 VIX band, -15 slippage ...)",
          f["n"] == 10 and f["first"] == "demo-size-by-stop" and f["last"] == "demo-mood-filter" and f["sorted"] and f["groups"]["adopt"] == 2 and f["groups"]["promising"] == 2 and f["groups"]["finding"] == 1 and f["groups"]["rejected"] == 4 and f["groups"]["info"] == 1 and f["body"] == 1
          and f["pm"]["size-by-stop"] == 2100 and f["pm"]["friday-skip"] == -640 and f["pm"]["vix-target"] == -1200 and f["pm"]["slippage"] == -15 and f["pm"]["news-filter"] == -30 and f["pm"]["london-only"] == 1800 and f["runs"] == 2, f)
    check("b. three index shapes are read: { writeups }, the site's data.json { docs: { writeups } }, a bare list", o["shapes"] == ["a", "b", "c"], o["shapes"])
    e = o["evil"]
    check("b. a hostile index: bad slugs (space, capitals, '../', '/', empty), duplicates, junk rows and a blank title are dropped; tags and script text stripped from titles / summaries (900 -> 420 chars); a bad date -> empty; the stated usd_month wins over the text; summary before title / status for the $ a month; junk numbers -> 0",
          e["slugs"] == ["ok-1", "ok-3", "ok-4", "ok-5", "ok-6", "ok-7"] and e["title"] == "Bold x idea", e)
    check("b. ... details: date, group, summary cap, usd_month, text order, runs / words / body cap",
          e["date"] == "" and e["group"] == "adopt" and e["sum"] == 420 and e["pm4"] == 300 and e["pm5"][0] == 70 and "<" not in e["pm5"][1] and e["pm6"] == 44 and e["ok7"] == [0, 0, 8000, "other"], e)
    check("b. no list / no usable rows -> null (the page then shows the demo, labelled); 500 rows are capped at 400", e["none"] == [None] * 6 and o["cap"] == 400, (e["none"], o["cap"]))
    check("b. search tokens: lower-cased words, junk ignored, at most 8, '$' and '%' kept", o["tok"] == [["size", "friday"], [], [], 8, ["$2", "100", "a-b", "58%"]], o["tok"])
    v = o["view"]
    check("b. view: all 10; the adopt group is size + eval speed; 4 rejected; 'friday' finds one; 'size stop' needs BOTH words; a word nowhere finds nothing; family 'timing' is searchable; a date is searchable; the money sort keeps only ranked ones, best first; 'old' puts the oldest first",
          v["all"] == 10 and v["adopt"] == ["size-by-stop", "eval-speed"] and v["rejected"] == 4 and v["q1"] == ["friday-skip"] and v["q2"] == ["size-by-stop"] and v["q3"] == [] and set(v["q4"]) == {"london-only", "friday-skip"} and v["q5"] == 4 and v["q6"] == ["size-by-stop"]
          and v["money"][0] == "size-by-stop" and v["money"][-1] == "vix-target" and v["old"] == "mood-filter" and v["moneyGroup"][0] == "news-filter" and v["moneyGroup"][-1] == "vix-target", v)
    i = o["ideas"]
    check("b. best and worst five by the $ a month they quote: best = size +$2,100, London +$1,800, scale-in +$950, eval speed +$400, Asia +$120; worst = VIX band -$1,200, Friday -$640, mood -$310, news -$30, slippage -$15; the unranked are counted; an empty library is safe",
          i["best"] == [["size-by-stop", 2100], ["london-only", 1800], ["scale-in", 950], ["eval-speed", 400], ["asia-slot", 120]] and i["worst"] == [["vix-target", -1200], ["friday-skip", -640], ["mood-filter", -310], ["news-filter", -30], ["slippage", -15]] and i["ranked"] == 10 and i["unranked"] == 0 and i["empty"] == [0, 0], i)
    m = o["md"]
    check("b. the reader: the front matter, code fences, the comment / div lines and the table rule are dropped; links keep only their words; bold / code marks and tags vanish; headings, list items, table rows ('A · B') and paragraphs keep their kind",
          m["kinds"] == "h,p,li,li,row,row,p" and m["texts"][0] == "Title bold" and m["texts"][1] == "A link and code bad() text." and "hidden code" not in " ".join(m["texts"]) and "first item" in m["texts"] and "second item" in m["texts"] and "A · B" in m["texts"] and "one · two" in m["texts"] and m["texts"][-1] == "last line" and "http" not in " ".join(m["texts"]) and "<" not in " ".join(m["texts"]), m)
    check("b. the reader is capped (a '…the rest is in the full write-up' line ends it), and empty / null / front-matter-only text gives no blocks", m["cap"] and m["capN"] == 13 and m["empty"] == [0, 0, 0], m)
    check("b. slug check: lower-case letters, digits and hyphens only, up to 80; '../x', capitals, numbers, empty are refused; a real slug (2026-11-03-money-plan) passes", o["slug"] == [True, False, False, False, False, False, True], o["slug"])
    c = o["card"]
    check("b. the Jarvis card: Clio, 'Demo library' vs '10 write-ups', 10 | 2 | 4, the best idea with its $ a month in one line <= 120; no ranked idea -> a friendly line",
          c[0] == "Clio" and c[1] == "Demo library" and c[2] == "10 write-ups" and c[3] == "10|2|4" and c[4] == "Best idea: Example: size follows the stop (+$2,100 a month)." and c[5] and c[6] == "Search the research in plain words.", c)


def real_index():
    rows = []
    for i, (slug, title, status, summary) in enumerate([
        ("2026-11-03-slippage", "How much slippage each bot survives", "info - no switch", "Zlarior barely notices it: the MFFU 50K slot goes from $823 a month to $712 a month at +8 ticks."),
        ("2026-11-03-night-rnd", "Night R&D: where the bots sit", "adopt-candidate (owner decides)", "Zlarior copy on the free 25K: worth about $540 a month more."),
        ("friday-skip", "Skip Fridays", "rejected - costs money", "Skipping Fridays lost -$310 a month.")]):
        rows.append({"slug": slug, "title": title, "family": "risk", "date": f"2026-11-0{3 - min(i, 2)}", "status": status, "summary": summary, "runs": ["a"], "words": 900})
    return json.dumps({"writeups": rows})


def test_page():
    try:
        import playwright  # noqa: F401
    except ImportError:
        check("c. page tests skipped: no Playwright", True)
        return
    srv, origin = AK.serve({"/writeups/index.json": None, "/data.json": None})
    try:
        with AK.browser() as br:
            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, APP, "")
            d = p.evaluate("""() => ({ demo: !document.querySelector('#demo').hidden, items: document.querySelectorAll('#list .wu').length, count: document.querySelector('#count').textContent, chips: [...document.querySelectorAll('#groups button')].map((b) => b.textContent), best: [...document.querySelectorAll('#best li')].map((l) => l.textContent),
              worst: document.querySelector('#worst li').textContent, note: document.querySelector('#ideasNote').textContent, first: document.querySelector('#list .wu h3').textContent, font: getComputedStyle(document.querySelector('h1')).fontFamily, bg: getComputedStyle(document.body).backgroundColor, h1: document.querySelectorAll('h1').length }) """)
            check("c. no index on the site: the DEMO library appears by itself (never blank): 10 example write-ups, verdict chips with counts, the best five and the worst five by $ a month, the newest first",
                  d["demo"] and d["items"] == 10 and d["count"] == "10 write-ups" and d["chips"][0] == "All 10" and "Adopted or ready 2" in d["chips"] and len(d["best"]) == 5 and d["best"][0].startswith("+$2,100 a month") and d["worst"].startswith("-$1,200 a month") and d["first"] == "Example: size follows the stop" and "10 of 10" in d["note"], d)
            check("c. AGORA look: serif title, warm dark body, one h1", any(f in d["font"] for f in ("Palatino", "Iowan", "Georgia")) and d["bg"] == "rgb(20, 17, 14)" and d["h1"] == 1, d)
            AK.shot(p, "clio-demo")
            p.locator("#q").fill("friday")
            p.wait_for_timeout(200)
            s = p.evaluate("() => [document.querySelectorAll('#list .wu').length, document.querySelector('#count').textContent, document.querySelector('#list .wu h3').textContent, document.querySelector('#status').textContent]")
            check("c. type 'friday': one write-up, the count says so (and what for), the status line is spoken", s[0] == 1 and "1 write-up for" in s[1] and "Friday" in s[2], s)
            p.locator("#q").fill("zzzz")
            p.wait_for_timeout(150)
            z = p.evaluate("() => document.querySelector('#list .empty').textContent")
            check("c. a search with no match says so in plain words and offers a way out", "Nothing matches" in z and "simpler" in z, z)
            p.locator("#q").fill("")
            p.locator("#groups [data-g=rejected]").click()
            p.wait_for_timeout(150)
            r = p.evaluate("() => [document.querySelectorAll('#list .wu').length, document.querySelector('#groups [aria-pressed=true]').dataset.g]")
            p.locator("#sorts [data-s=money]").click()
            p.wait_for_timeout(150)
            r2 = p.evaluate("() => [...document.querySelectorAll('#list .wu .ag-num')].map((e) => e.textContent)")
            check("c. the Rejected chip shows 4; 'Best $ a month' sorts by the money they quote (least bad first)", r == [4, "rejected"] and r2[0] == "-$30 a month" and r2[-1] == "-$1,200 a month", (r, r2))
            p.locator("#groups [data-g=all]").click()
            p.locator("#sorts [data-s=new]").click()
            p.wait_for_timeout(100)
            p.locator("#list .wu button").first.click()
            p.wait_for_timeout(300)
            sh = p.evaluate("""() => ({ open: !document.querySelector('#sheet').hidden, title: document.querySelector('#shTitle').textContent, text: document.querySelector('#shBody').innerText, active: document.activeElement.id, scrim: !document.querySelector('#scrim').hidden })""")
            check("c. tap Read: the sheet opens as a dialog with the title, the example text in plain blocks (heading, list item, the table row as 'Wide · 4 · +$310'), focus moves to Close", sh["open"] and sh["scrim"] and sh["title"] == "Example: size follows the stop" and "What we found" in sh["text"] and "Wide · 4 · +$310" in sh["text"] and "Does a wide stop deserve fewer contracts?" in sh["text"] and sh["active"] == "shClose", sh)
            check("c. every tap target is at least 44 x 44 px (with the sheet open)", not AK.taps(p), AK.taps(p)[:5])
            p.keyboard.press("Escape")
            p.wait_for_timeout(200)
            cl = p.evaluate("() => [document.querySelector('#sheet').hidden, document.activeElement.textContent]")
            check("c. Escape closes the sheet and puts focus back on the Read button that opened it", cl[0] is True and cl[1] == "Read", cl)
            check("c. no sideways scroll; Jarvis's corner is free; no console error; nothing off the origin", AK.no_sideways(p) and not AK.corner(p) and not errs and not off, (errs[:3], off[:3]))
            ctx.close()
            # ---- the real index
            srv2, origin2 = AK.serve({"/writeups/index.json": real_index(), "/writeups/2026-11-03-slippage.md": "---\ntitle: x\n---\n# Slippage\n\nZlarior barely notices it.\n\n- one tick costs little\n"})
            ctx, p, errs, seen, off = AK.page(br, origin2)
            AK.open_app(p, origin2, APP, "")
            q = p.evaluate("() => ({ demo: !document.querySelector('#demo').hidden, n: document.querySelectorAll('#list .wu').length, best: document.querySelector('#best li').textContent, worst: document.querySelector('#worst li').textContent, chips: [...document.querySelectorAll('#groups button')].map((b) => b.textContent) })")
            check("c. the real index (writeups/index.json): no DEMO chip, 3 write-ups, the best idea from their own sentences ($823 a month first), the worst (-$310 a month)", not q["demo"] and q["n"] == 3 and q["best"].startswith("+$823 a month") and q["worst"].startswith("-$310 a month"), q)
            p.locator("#list .wu button").first.click()
            p.wait_for_timeout(500)
            t = p.evaluate("() => [document.querySelector('#shBody').innerText, document.querySelector('#shTitle').textContent]")
            check("c. Read fetches that write-up's text (writeups/<slug>.md) and shows it plain; the front matter is gone", "Zlarior barely notices it." in t[0] and "one tick costs little" in t[0] and "title: x" not in t[0] and any("writeups/2026-11-03-slippage.md" in u for u in seen), (t, seen[-3:]))
            ctx.close()
            srv2.shutdown()
            # ---- the data.json fallback
            srv3, origin3 = AK.serve({"/writeups/index.json": None, "/data.json": json.dumps({"docs": json.loads(real_index())})})
            ctx, p, errs, seen, off = AK.page(br, origin3)
            AK.open_app(p, origin3, APP, "")
            f = p.evaluate("() => [!document.querySelector('#demo').hidden, document.querySelectorAll('#list .wu').length]")
            check("c. no writeups/index.json but data.json has the docs list: the library reads it (no DEMO chip)", f == [False, 3], f)
            ctx.close()
            srv3.shutdown()
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
