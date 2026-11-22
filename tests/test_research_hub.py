"""Research Hub (day-litedge 2026-11-21): tools/research_hub.py -> tools/web_public/clio/hub.json, and Clio's owner view.

  a. the generator on the real repo: four sections + the library, private-safe (tools/site_privacy scan = 0), the file on disk
     parses and has the same sections
  b. the parsers on a temp repo: TESTED_AND_REJECTED bullets (multi-line, title, date, $ a month, the linked write-up), the
     ledger (FIXED / REFUTED dropped), the Decide cards (open / later only), live vs backtest money, account numbers masked
  c. cliocore hub maths in node: hostile rows dropped, tab / search / family / date filters, sinceOf, viewX
  d. the page at 390 x 844: the hub first with 4 tabs and counts, one-line rows with $, a tap opens the write-up
     (writeups/<slug>.md) or the item's own text, every tap >= 44 px, no sideways scroll, no console error; screenshots when
     AGORA_SHOTS is set

    python -X utf8 -m tests.test_research_hub [--static]
"""
from __future__ import annotations

import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tests import agora_kit as AK  # noqa: E402
from tools import research_hub as R  # noqa: E402

check = AK.check
APP = "clio"


def test_real():
    h = R.build()
    blob = json.dumps(h, separators=(",", ":"), ensure_ascii=False)
    c = h["counts"]
    check("a. the real repo: what works (2 live strategies: Zlarior, ATLAS; no BLITZ), rejected, leads, decisions and the library are all filled",
          c["works"] == 2 and c["rejected"] >= 40 and c["leads"] >= 5 and c["writeups"] >= 100 and {w["bot"] for w in h["works"]} == {"LIT", "ATLAS"}, c)
    check("a. every works row has its 2026 backtest $ a month and its real trades in one plain line", all(w["usd_month"] is not None and "Real so far" in w["line"] for w in h["works"]), [w["line"] for w in h["works"]])
    check("a. private-safe: the site privacy scan finds nothing; no e-mail address, no unmasked account number", not R.privacy_findings(blob) and "@gmail" not in blob, R.privacy_findings(blob)[:3])
    check("a. every rejected / lead row is one line (<= 200 chars) with a title; slugs are site slugs", all(len(r["line"]) <= 200 and r["title"] for r in h["rejected"] + h["leads"])
          and all(not r["slug"] or AK_slug(r["slug"]) for r in h["rejected"] + h["leads"]))
    p = os.path.join(AK.WEB, APP, "hub.json")
    d = json.load(open(p, encoding="utf-8"))
    fl = json.load(open(os.path.join(AK.WEB, "research", "hub.json"), encoding="utf-8"))
    ok = all(set(x) == {"id", "title", "family", "status", "usd_month", "date", "summary", "url"} and x["status"] in ("live", "lead", "rejected", "decide")
             and (x["url"].startswith("../clio/?read=") or x["url"].startswith("../clio/?item=")) for x in fl["items"])
    ids = [x["id"] for x in fl["items"]]
    check("a. research/hub.json (the Cities district): one record per item with the agreed 8 fields, unique ids, live-zlarior + live-atlas, urls into Clio",
          ok and len(ids) == len(set(ids)) and {"live-zlarior", "live-atlas"} <= set(ids) and len(ids) == sum(fl["counts"].values()), fl["counts"])
    check("a. clio/hub.json on disk parses (v 1) with the four sections and the library", d.get("v") == 1 and all(k in d for k in ("works", "rejected", "leads", "decide", "writeups")), list(d)[:8])


def AK_slug(s):
    import re
    return bool(re.match(r"^[a-z0-9][a-z0-9-]{0,79}$", s))


def test_parsers():
    tmp = tempfile.mkdtemp(prefix="hub-")
    W = os.path.join(tmp, "w"); os.makedirs(W)
    open(os.path.join(W, "skip-fridays-2026-11-02.md"), "w").write("---\ntitle: Skip Fridays\nfamily: timing\ndate: 2026-11-02\nstatus: rejected - costs\n"
                                                                    "summary: Skipping Fridays lost -$640 a month.\n---\n# x\n")
    open(os.path.join(W, "lead-a.md"), "w").write("---\ntitle: A lead\nfamily: risk\ndate: 2026-11-05\nstatus: promising - paper only\nsummary: Up $120 a month in one half.\n---\n")
    open(os.path.join(W, "INDEX.md"), "w").write("# index\n")
    tar = os.path.join(tmp, "tar.md")
    open(tar, "w").write("## Tested and rejected\n- **Skip Fridays (2026-11-02, `skip-fridays-2026-11-02.md`):** both halves lose,\n"
                         "  $5,000 / $2,000 a month vs today. Account MFFUEVBLDR123456789 note.\n- **Old idea (2026-10-01):** -$51 a month. Done.\n")
    led = os.path.join(tmp, "led.md")
    open(led, "w").write("| Date | Finding | $ / risk | Status |\n|---|---|---|---|\n| 2026-11-20 | A fixed thing | x | FIXED abc |\n"
                         "| 2026-11-19 | Still open | $30 a month | WATCH (later) |\n| 2026-11-18 | Not real | y | REFUTED |\n")
    dec = os.path.join(tmp, "dec.json")
    json.dump({"items": [{"id": "a", "question": "Add X?", "why": "More money for the same risk each month. Second sentence.", "usd_month": 300, "status": "open"},
                         {"id": "b", "question": "Old", "why": "w", "status": "yes"}, {"id": "c", "question": "Later?", "why": "z", "status": "later"}]}, open(dec, "w"))
    trd = os.path.join(tmp, "t.json")
    json.dump({"trades": [{"bot": "LIT", "src": "backtest", "day": "2026-01-05", "usd": 1000}, {"bot": "LIT", "src": "backtest", "day": "2026-02-05", "usd": 500},
                          {"bot": "LIT", "src": "live", "day": "2026-11-16", "usd": -129.4}, {"bot": "BLITZ", "src": "live", "day": "2026-11-16", "usd": 99}]}, open(trd, "w"))
    old = (R.WRITEUPS, R.TAR, R.LEDGER, R.DECIDE, R.TRADES)
    R.WRITEUPS, R.TAR, R.LEDGER, R.DECIDE, R.TRADES = W, tar, led, dec, trd
    try:
        h = R.build()
    finally:
        R.WRITEUPS, R.TAR, R.LEDGER, R.DECIDE, R.TRADES = old
    rj = {r["title"]: r for r in h["rejected"]}
    s = rj.get("Skip Fridays", {})
    check("b. a TESTED_AND_REJECTED bullet over 2 lines: title, date, linked write-up slug, its first $ a month, the account number masked",
          s.get("date") == "2026-11-02" and s.get("slug") == "skip-fridays-2026-11-02" and s.get("usd_month") == 2000.0 and "123456789" not in json.dumps(h) and "6789" in s.get("text", ""), s)
    check("b. a rejected write-up already linked by a bullet is not listed twice; an unlinked bullet keeps its own text",
          sum(1 for r in h["rejected"] if r["slug"] == "skip-fridays-2026-11-02") == 1 and rj.get("Old idea", {}).get("usd_month") == -51.0, list(rj))
    check("b. leads: the promising write-up + the ledger row still open; FIXED and REFUTED rows dropped",
          sorted(r["title"] for r in h["leads"]) == ["A lead", "Still open"], [r["title"] for r in h["leads"]])
    check("b. decisions: only open / later cards, with their $ a month and the first sentence of why",
          [d["id"] for d in h["decide"]] == ["a", "c"] and h["decide"][0]["usd_month"] == 300 and h["decide"][0]["line"] == "More money for the same risk each month.", h["decide"])
    z = next(w for w in h["works"] if w["bot"] == "LIT")
    check("b. works: backtest $ a month over its months ($750), real trades summed (-$129), BLITZ never listed",
          z["usd_month"] == 750 and z["real_usd"] == -129 and z["real_n"] == 1 and all(w["bot"] != "BLITZ" for w in h["works"]), z)
    check("b. the library: front matter read, INDEX.md skipped, newest first", [w["slug"] for w in h["writeups"]] == ["lead-a", "skip-fridays-2026-11-02"], [w["slug"] for w in h["writeups"]])


HARNESS = r"""
const fs = require('fs');
import(process.argv[2]).then((C) => {
  const o = {};
  const raw = { built: '2026-11-21', works: [{ title: 'A', line: 'l', usd_month: 100, slug: 'a-1' }], rejected: [null, 5, { title: '' }, { title: '<b>X</b> idea', line: 'y'.repeat(500), slug: '../x', family: 'timing', date: '2026-11-20' },
    { title: 'Old', line: 'old one', date: '2026-01-02', family: 'risk' }], leads: [], decide: [{ title: 'D', usd_month: '$300' }], writeups: [{ slug: 'w-1', title: 'W', date: '2026-11-01', status: 'rejected' }], lab: { files: 3, edge_light: { lit: 'GREEN' } } };
  const h = C.normHub(raw);
  o.counts = C.hubCounts(h);
  o.clean = [h.rejected[0].title, h.rejected[0].line.length, h.rejected[0].slug, h.rejected[0].family];
  o.q = [C.hubView(h, 'rejected', { q: 'idea' }).length, C.hubView(h, 'rejected', { q: 'zzz' }).length, C.hubView(h, 'rejected', { family: 'risk' }).length, C.hubView(h, 'rejected', { since: '2026-11-01' }).length];
  o.money = [C.hubMoney(h.works[0]), C.hubMoney(h.decide[0]), C.hubMoney(h.rejected[1])];
  o.since = [C.sinceOf('30', '2026-11-21'), C.sinceOf('all', '2026-11-21'), C.sinceOf('7', 'x')];
  o.none = [C.normHub(null), C.normHub({}), C.normHub({ works: [] })];
  o.lib = [h.writeups.length, h.lab.lit];
  o.city = [C.cityHref({ id: 'live-zlarior' }), C.cityHref({ id: '../x' }), C.cityHref(null), C.hubFind(C.normHub({ works: [{ title: 'Z', id: 'live-z' }] }), 'live-z').title];
  const lib = C.normIndex({ writeups: [{ slug: 'a', title: 'A', family: 'risk', date: '2026-11-20', status: 'info' }, { slug: 'b', title: 'B', family: 'timing', date: '2026-01-01', status: 'info' }] });
  o.vx = [C.viewX(lib, { family: 'risk' }).map((r) => r.slug), C.viewX(lib, { since: '2026-11-01' }).map((r) => r.slug), C.viewX(lib, {}).length];
  console.log(JSON.stringify(o));
});
"""


def test_core():
    o = AK.node(APP, HARNESS)
    if o is None:
        check("c. node is not installed: maths skipped", True)
        return
    check("c. hostile hub rows dropped (null, number, blank title); tags stripped, a line capped at 200, a bad slug emptied, family kept",
          o["counts"] == {"works": 1, "rejected": 2, "leads": 0, "decide": 1} and o["clean"] == ["X idea", 200, "", "timing"], o)
    check("c. hub filters: search, family, date", o["q"] == [1, 0, 1, 1], o["q"])
    check("c. $ words: +$100 a month, +$300 a month (a '$300' string), none -> ''", o["money"] == ["+$100 a month", "+$300 a month", ""], o["money"])
    check("c. sinceOf: 30 days back, 'all' -> '', a bad day -> ''", o["since"] == ["2026-10-22", "", ""], o["since"])
    check("c. no hub / empty hub -> null (the page falls back to the demo hub, labelled)", o["none"] == [None, None, None], o["none"])
    check("c. the hub carries the library and the edge light; viewX filters the library by family and date",
          o["lib"] == [1, "GREEN"] and o["vx"] == [["a"], ["a"], 2], (o["lib"], o["vx"]))
    check("c. city links: ../cities/?fly=<id> only for a safe id; hubFind finds a row by id", o["city"] == ["../cities/?fly=live-zlarior", "", "", "Z"], o["city"])


def test_page():
    try:
        import playwright  # noqa: F401
    except ImportError:
        check("d. page tests skipped: no Playwright", True)
        return
    hub = json.load(open(os.path.join(AK.WEB, APP, "hub.json"), encoding="utf-8"))
    slug = next(r["slug"] for r in hub["rejected"] if r["slug"])
    srv, origin = AK.serve({"/writeups/index.json": None, "/data.json": None,
                            f"/writeups/{slug}.md": "---\ntitle: x\n---\n# The write-up\n\nWhat we found: it lost money in both halves.\n"})
    try:
        with AK.browser() as br:
            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, APP, "")
            d = p.evaluate("""() => ({ tabs: [...document.querySelectorAll('#hubTabs button')].map((b) => b.textContent), first: document.querySelector('main section').id,
              rows: document.querySelectorAll('#hubList .hrow').length, money: [...document.querySelectorAll('#hubList .hm')].map((e) => e.textContent), note: document.querySelector('#hubNote').textContent,
              demo: !document.querySelector('#demo').hidden, lib: document.querySelectorAll('#list .wu').length, bg: getComputedStyle(document.body).backgroundColor })""")
            check("d. the hub comes first: 4 tabs with counts (What works now 2, Tried and rejected, Open leads, Money decisions), the 2 live strategies with $ a month, the edge check named",
                  d["first"] == "hub" and len(d["tabs"]) == 4 and d["tabs"][0] == "What works now 2" and d["tabs"][1].startswith("Tried and rejected ") and d["rows"] == 2
                  and all("a month" in m for m in d["money"]) and "Edge check" in d["note"], d)
            check("d. the library reads the hub's own list when writeups/index.json is missing (no DEMO chip, no 8 MB data.json)", not d["demo"] and d["lib"] > 0, d)
            AK.shot(p, "research-hub-works")
            p.locator("#hubTabs [data-t=rejected]").click()
            p.wait_for_timeout(150)
            n0 = p.evaluate("() => document.querySelectorAll('#hubList .hrow').length")
            p.locator("#q").fill("fills")
            p.wait_for_timeout(200)
            n1 = p.evaluate("() => [document.querySelectorAll('#hubList .hrow').length, document.querySelector('#hubNote').textContent]")
            check("d. Tried and rejected: 12 rows a page, the search box filters them too (and the note says what for)", n0 == 12 and 0 < n1[0] <= 12 and 'for "fills"' in n1[1], (n0, n1))
            p.locator("#q").fill("")
            p.wait_for_timeout(150)
            AK.shot(p, "research-hub-rejected")
            # tap a row with a write-up
            idx = p.evaluate("(s) => [...document.querySelectorAll('#hubList .hrow')].findIndex((b) => b.textContent.includes('tap to read'))", slug)
            more = 0
            while idx < 0 and more < 10:
                p.locator("#hubMore").click(); p.wait_for_timeout(100); more += 1
                idx = p.evaluate("() => [...document.querySelectorAll('#hubList .hrow')].findIndex((b) => b.textContent.includes('tap to read'))")
            p.locator("#hubList .hrow").nth(idx).click()
            p.wait_for_timeout(500)
            sh = p.evaluate("() => ({ open: !document.querySelector('#sheet').hidden, text: document.querySelector('#shBody').innerText, active: document.activeElement.id })")
            check("d. tap a row with a write-up: the reader sheet opens and fetches writeups/<slug>.md, focus on Close",
                  sh["open"] and sh["active"] == "shClose" and any("/writeups/" in u and u.endswith(".md") for u in seen), (sh["text"][:120], seen[-2:]))
            ch = p.evaluate("() => [!document.querySelector('#shCity').hidden, document.querySelector('#shCity').getAttribute('href')]")
            check("d. the sheet has 'See it in the city' -> ../cities/?fly=<the item's id> (the Cities Lab & Research district)",
                  ch[0] and ch[1].startswith("../cities/?fly=rejected-"), ch)
            AK.shot(p, "research-hub-reader")
            check("d. every tap target is at least 44 x 44 px (sheet open)", not AK.taps(p), AK.taps(p)[:5])
            p.keyboard.press("Escape")
            p.locator("#hubTabs [data-t=leads]").click()
            p.wait_for_timeout(150)
            idx = p.evaluate("() => [...document.querySelectorAll('#hubList .hrow')].findIndex((b) => !b.textContent.includes('tap to read'))")
            p.locator("#hubList .hrow").nth(max(idx, 0)).click()
            p.wait_for_timeout(300)
            t = p.evaluate("() => [!document.querySelector('#sheet').hidden, document.querySelector('#shBody').innerText.length]")
            check("d. tap a row without a write-up (a ledger finding): the sheet shows its own text, nothing fetched", t[0] and t[1] > 10, t)
            p.keyboard.press("Escape")
            p.locator("#hubTabs [data-t=decide]").click()
            p.wait_for_timeout(150)
            AK.shot(p, "research-hub-decide")
            dd = p.evaluate("() => document.querySelectorAll('#hubList .hrow').length")
            check("d. Money decisions: the open Decide cards", dd == len(hub["decide"]), dd)
            check("d. OLYMPUS NIGHT (black), no sideways scroll, Jarvis's corner free, no console error, nothing off the origin",
                  d["bg"] in ("rgb(0, 0, 0)", "rgba(0, 0, 0, 0)") and AK.no_sideways(p) and not AK.corner(p) and not errs and not off, (d["bg"], errs[:3], off[:3]))
            ctx.close()
            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, APP, "?item=live-zlarior")
            p.wait_for_timeout(400)
            dl = p.evaluate("() => [!document.querySelector('#sheet').hidden, document.querySelector('#shTitle').textContent, document.querySelector('#shCity').getAttribute('href')]")
            check("d. deep link ?item=live-zlarior (the city's link back) opens that item with its city link", dl[0] and dl[1] == "Zlarior (LIT)" and dl[2] == "../cities/?fly=live-zlarior", dl)
            ctx.close()
            srv2, origin2 = AK.serve({"/writeups/index.json": None, "/data.json": None, "/clio/hub.json": None})
            ctx, p, errs, seen, off = AK.page(br, origin2)
            AK.open_app(p, origin2, APP, "")
            z = p.evaluate("() => [document.querySelectorAll('#hubTabs button').length, document.querySelector('#hubNote').textContent]")
            check("d. no hub.json on the site: the example hub shows, labelled DEMO (never blank)", z[0] == 4 and "DEMO" in z[1], z)
            ctx.close()
            srv2.shutdown()
    finally:
        srv.shutdown()


if __name__ == "__main__":
    test_real()
    test_parsers()
    test_core()
    if "--static" not in sys.argv:
        test_page()
    AK.finish()
