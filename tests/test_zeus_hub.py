"""ZEUS, the trading door's landing (tools/web_public/hub/zeus.html + zeus.js, 2026-11-18, night-zeushub).
  a. the page: AGORA look, title ZEUS, no innerHTML / outside address / write, the big buttons point at pages that exist, Safety is an
     explanation (Tailscale /safety/, never a link), Add an account explains ADD_ACCOUNT.bat + the Start page cards, the footer
  b. the door: olympus/doors.js zeus.home = hub/zeus.html (both copies equal), homeOf(); hub/doors.js shows the landing link first
  c. node, the pure part: entry windows (LIT 02:00-15:30; ATLAS MACD / EMA not Mondays / S/R; weekend, Thanksgiving closed, the
     Nov 27 early close ends entries 13:00; the PC's own window wins), news notes (7 days), PC line (fresh / silent / never),
     account rows from the real MFFU_MODEL.cards (matched by PC id: the 25K #2 eval on its own row, ATLAS funded = payout text)
  f. the Accounts view (2026-11-20, olympus/acct_live.js): Live feed newest first (entries + exits of every account), the open trade's live $,
     the last trades per account, BLITZ out (the phone sizes + safe areas: tests/test_phone_fit.py)
  e. the homes' ZEUS card (olympus/zeus_core.js, 2026-11-18 night-zcard): node summary() = the page's rows; Zenith (index.html#/today)
     starts with it as #page's first child (gone on other pages, back on Home), Jarvis has it right under the greeting (before the tiles):
     PC reported, 3 account lines with $ to pass / payout + today's $, the edge chip, a tap -> hub/zeus.html; silent = red PC SILENT
  d. Chromium 390 x 844 (ntfy routed to a fixture): PC reported, 3 account rows with $ + chips + today's $, the edge chip, the
     ZEUS learned card (status "zl", night-learnloop), two window lines, the buttons; a silent feed + stale board copy = the red PC
     SILENT strip and the learned card's calm placeholder (polish2 2026-11-19: it used to hide); no sideways scroll, 44 px taps, no page errors
    python -X utf8 -m tests.test_zeus_hub        (ZEUS_NO_BROWSER=1 skips d; run d only under flock -w 2400 /tmp/olympus_browser.lock)
"""
from __future__ import annotations

import functools
import glob
import http.server
import json
import os
import re
import subprocess
import sys
import threading
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEB = os.path.join(ROOT, "tools", "web_public")
HUB = os.path.join(WEB, "hub")
RES: list = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:400]}"))


def rd(*p):
    with open(os.path.join(*p), encoding="utf-8") as f:
        return f.read()


def node(body):
    js = json.dumps
    script = (f"const Z = require({js(os.path.join(HUB, 'zeus.js'))}); const MM = require({js(os.path.join(WEB, 'business', 'mffumodel.js'))});"
              f"const BM = require({js(os.path.join(WEB, 'board', 'boardmodel.js'))}); const PC = require({js(os.path.join(WEB, 'business', 'payoutcoach.js'))});"
              f"const D = require({js(os.path.join(WEB, 'olympus', 'doors.js'))}); const out = (x) => console.log('@@' + JSON.stringify(x));\n"
              "try { " + body + " } catch (e) { console.log('@@' + JSON.stringify({ error: String(e && e.stack || e) })); }")
    p = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=60)
    m = [ln for ln in p.stdout.splitlines() if ln.startswith("@@")]
    return json.loads(m[-1][2:]) if m else {"error": (p.stderr or p.stdout)[-400:]}


def lite_fixture(now):
    """A PC core post: Zlarior 50K eval (board card lit + its account row = one account), ATLAS funded 25K, the new 25K #2 eval."""
    return {"v": 1, "kind": "le-live", "lite": True, "t": now - 240, "reporter": {"t": now - 240},
            "board": {"t": now - 240, "data_t": now - 240,
                      "lit": {"name": "Zlarior", "plan": "MFFU Builder 50K", "status": "open", "balance": 49192.78, "floor": 48168.2, "room": 1024.58,
                              "to_target": 3807.22, "today_pnl": 120.0},
                      "atlas": {"name": "ATLAS", "plan": "MFFU Builder 25K", "status": "funded", "stage": "funded", "balance": 25080.0, "floor": 24000.0,
                                "room": 1080.0, "today_pnl": -40.0}},
            "accounts": [{"id": "mffu50k_eval", "kind": "eval", "name": "Zlarior", "plan": "MFFU Builder 50K",
                          "eval": {"balance": 49192.78, "floor": 48168.2, "room": 1024.58, "to_target": 3807.22, "today": 120.0}},
                         {"id": "b25k_2", "kind": "eval", "name": "Zlarior 25K #2", "plan": "MFFU Builder 25K",
                          "eval": {"balance": 25210.0, "floor": 24000.0, "room": 1210.0, "to_target": 1290.0, "today": 210.0}}],
            "eh": {"d": "2026-11-17", "z": ["G", 3.8, 3.9], "a": ["G", 1.9, 1.8, "2026-11-17"], "t": now - 3600}}


def part_a():
    html, js, core = rd(HUB, "zeus.html"), rd(HUB, "zeus.js"), rd(WEB, "olympus", "zeus_core.js")
    check("a. files: hub/zeus.html + hub/zeus.js", os.path.isfile(os.path.join(HUB, "zeus.html")) and os.path.isfile(os.path.join(HUB, "zeus.js")))
    check("a. AGORA look: data-theme agora, the kit's agora.css, viewport-fit=cover, title ZEUS",
          'data-theme="agora"' in html and "olympus/agora.css" in html and "viewport-fit=cover" in html and "<title>ZEUS</title>" in html)
    check("a. text only: no innerHTML / insertAdjacentHTML / document.write / eval, no outside address",
          not re.search(r"innerHTML|insertAdjacentHTML|document\.write|\beval\(", js + core) and not re.search(r"https?://", js + core)
          and not re.search(r'(src|href)="https?://', html))
    methods = re.findall(r"method:\s*'([A-Z]+)'", js)
    # the one thing the card keeps on the phone: its own height (key olympus.zeus.cardh, phone QA 2026-11-19), never data
    core_nh = re.sub(r"localStorage\.(getItem|setItem)\(HKEY", "", core)
    check("a. read only: no POST / PUT / DELETE (only GET + one HEAD for the weekly review); the card stores only its height",
          methods == ["HEAD"] and "localStorage" not in js + core_nh and "HKEY = 'olympus.zeus.cardh'" in core
          and not re.findall(r"method:", core), methods)
    # the data + the account matching live in olympus/zeus_core.js (2026-11-18, night-zcard: shared with the Zenith and Jarvis home cards;
    # its paths are relative to olympus/, so '../board/board.json' is the same file)
    check("a. data: PC_FEED.fetchLatest + ../board/board.json + ../business/accounts.json, Board pick + MFFU cards (zeus_core.js), ../pythia/events.json",
          "F.fetchLatest(" in core and "url('../board/board.json')" in core and "url('../business/accounts.json')" in core and "BM.pick(" in core and "MM.cards(" in core
          and "ZC.summary(" in js and "ZC.fetchAll(" in js and "'../pythia/events.json'" in js and "BM.pick(" not in js and "MM.cards(" not in js)
    order = [m for m in re.findall(r'<script src="([^"?]+)', html) if m not in ("../olympus/warp.js", "../olympus/themes.js")]   # the world-to-world jump (tests.test_warp) and the OLYMPUS look (themes.js, day-manual NAV) are not data
    check("a. scripts: pc_feed, payoutcoach, mffumodel, boardmodel (after mffumodel), edge_chip, the Decide card, the shared zeus_core, the Accounts "
          "view's acct_live (2026-11-20), zeus.js last",
          order == ["../pc_feed.js", "../business/payoutcoach.js", "../business/mffumodel.js", "../board/boardmodel.js", "../edge_chip.js",
                    "../business/decide.js", "../olympus/zeus_core.js", "../olympus/acct_live.js", "zeus.js"], order)
    check("a. the ZEUS edge chip mounts here (data-edge-chip, ../edge.json)", 'id="edgeChip" data-edge-chip data-edge-src="../edge.json"' in html)
    hrefs = re.findall(r'class="zs-btn"(?: id="\w+")? href="([^"]+)"', html)
    want = ["../business/mffu.html", "../trading/", "../index.html#/brain", "../board/", "../business/lab.html", "../business/accounts.html#coach", "../business/week.html"]
    check("a. the big buttons in order: My accounts (MFFU view), Trades & calendar, Brain, Board, ZEUS Lab, Payouts, Weekly review", hrefs == want, hrefs)

    def exists(h):
        p = h.split("#")[0].replace("../", "")
        p = p + "index.html" if p.endswith("/") else p
        return os.path.isfile(os.path.join(WEB, p))
    missing = [h for h in want[:-1] if not exists(h)]
    check("a. every button's page exists (Payouts = accounts.html#coach, the coach card)", not missing and 'id="coach"' in rd(WEB, "business", "accounts.html"), missing)
    check("a. Weekly review: hidden until business/week.html answers (a HEAD check)", 'id="btnWeek" href="../business/week.html" hidden' in html and "method: 'HEAD'" in js)
    safety = html[html.index('id="safety"'):html.index('id="addAcct"')]
    check("a. Safety (pause / flatten) explains the PC's private Tailscale link + /safety/, never a link to it, never arms",
          "Tailscale" in safety and "/safety/" in safety and "href" not in safety and "never arm" in safety.replace("can never arm", "never arm"), safety[:200])
    add = html[html.index('id="addAcct"'):]
    check("a. Add an account explains ADD_ACCOUNT.bat and the Start page cards, added NOT armed", "ADD_ACCOUNT.bat" in add and "Start page" in add and "NOT armed" in add)
    check("a. the footer: ZEUS = Zlarior (LIT) + ATLAS + the engine", "ZEUS = Zlarior (LIT) + ATLAS + the engine" in html)
    check("a. top to bottom: Right now (PC + accounts + edge chip), Today, Open (buttons), footer",
          html.index('id="pc"') < html.index('id="accts"') < html.index('id="edgeChip"') < html.index('id="wins"') < html.index('id="notes"')
          < html.index('class="zs-btns"') < html.index('class="zs-foot"'))


def part_f():
    """f. the Accounts view (2026-11-20, night-tradealerts: olympus/acct_live.js): the Live feed strip, the open trade with its live $, the last
    5 trades per account, matched to the plan row by the PC id; text only, no network."""
    al = rd(WEB, "olympus", "acct_live.js")
    check("f. acct_live.js: pure (no DOM, no fetch, no storage, no innerHTML, no outside address)",
          not re.search(r"document\.|fetch\(|localStorage|innerHTML|https?://", al))
    html = rd(HUB, "zeus.html")
    check("f. the page: Accounts first (PC line, Live feed, the account cards held by two placeholders from the first paint), reduce-motion respected",
          html.index('id="hLive"') < html.index('id="pc"') < html.index('id="feed"') < html.index('id="accts"') and ">Accounts</h2>" in html
          and html.count('class="zs-acct skel"') == 2 and "prefers-reduced-motion: reduce" in html)
    al_path = os.path.join(WEB, "olympus", "acct_live.js")
    js = json.dumps
    script = (f"const A = require({js(al_path)}); const now = 1795050000;"
              "const plan = { accounts: [{ key: 'zlarior', name: 'Zlarior', pc: ['mffu50k_eval', 'lit'] }, { key: 'fresh25', name: 'Zlarior 25K #2', pc: ['b25k_2'] },"
              " { key: 'blitz', name: 'BLITZ', pc: ['acct_c'] }] };"
              "const lite = { price: 21051.5, t: now - 60, at: { a: [{ id: 'mffu50k_eval', tr: [[now - 90000, now - 89000, 1, 4, 21010, 20990, 21060, 'TARGET', 398.1, 2.5],"
              " [now - 9000, now - 8000, -1, 4, 21100, 21120, 21040, 'STOP', -163.8, -1], [now - 3000, null, 1, 4, 21034.25, 21012, 21090.5, null, null, null]] },"
              " { id: 'b25k_2', tr: [[now - 2900, now - 1200, 1, 2, 21036, 21014, 21090.5, 'TARGET', 214.1, 2.4]] }, { id: 'acct_c', tr: [[now - 100, null, 1, 9, 1, 0, 2]] }] } };"
              "const r = A.trades(lite, plan); const o = A.open(r, 'zlarior', lite.price, lite.t, now);"
              "console.log('@@' + JSON.stringify({ n: r.length, keys: [...new Set(r.map((x) => x.key))], names: [...new Set(r.map((x) => x.name))],"
              " feed: A.feed(r, now, 4).map((e) => e.kind + '|' + e.name + '|' + e.text), o, last: A.last(r, 'zlarior', 5, now).map((t) => t.usd),"
              " stale: A.open(r, 'zlarior', lite.price, now - 7200, now).live }));")
    p = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=60)
    m = [ln for ln in p.stdout.splitlines() if ln.startswith("@@")]
    v = json.loads(m[-1][2:]) if m else {"error": p.stderr[-300:]}
    check("f. trades: every real account's newest trades by the plan row's PC ids (Zlarior 50K, Zlarior 25K #2), BLITZ left out",
          v.get("n") == 4 and v.get("keys") == ["zlarior", "fresh25"] and v.get("names") == ["Zlarior 50K", "Zlarior 25K #2"], v)
    check("f. Live feed: newest first, entries AND exits across accounts ('closed LONG +$214 (target)', 'LONG 2 @ 21,036.00')",
          v.get("feed") == ["exit|Zlarior 25K #2|closed LONG +$214 (target)", "entry|Zlarior 25K #2|LONG 2 @ 21,036.00", "entry|Zlarior 50K|LONG 4 @ 21,034.25",
                            "exit|Zlarior 50K|closed SHORT -$164 (stop)"], v.get("feed"))
    o = v.get("o") or {}
    check("f. the open trade: LONG 4 @ 21,034.25, live +$138 at the PC's 21,051.50, stop -$178, target +$450; an old price = no live $",
          o.get("text") == "LONG 4 @ 21,034.25" and o.get("live") == 138 and o.get("risk") == -178 and o.get("gain") == 450 and v.get("stale") is None, v)
    check("f. the last trades, newest first, the open one left out", v.get("last") == [-163.8, 398.1], v.get("last"))


def part_b():
    a, b = rd(WEB, "olympus", "doors.js"), rd(ROOT, "web_next", "js", "next", "doors.js")
    check("b. olympus/doors.js = web_next/js/next/doors.js", a == b)
    r = node("out({ home: D.door('zeus').home, h: D.homeOf('zeus'), m: D.homeOf('money'), n: D.door('zeus').items.length })")
    check("b. the ZEUS door's home is hub/zeus.html; other doors land on the Doors page", r.get("home") == "hub/zeus.html" and r.get("h") == "hub/zeus.html"
          and r.get("m") == "hub/doors.html#money" and 5 <= (r.get("n") or 0) <= 8, r)
    dj = rd(HUB, "doors.js")
    check("b. the Doors page shows the door's landing first (dr.home -> a big 'Open ZEUS' row)", "if (dr.home)" in dj and "'Open ' + dr.title.split(' ')[0]" in dj
          and dj.index("if (dr.home)") < dj.index("dr.items.forEach"))


def part_c():
    ev = os.path.join(WEB, "pythia", "events.json")
    plan = os.path.join(WEB, "business", "accounts.json")
    now = int(time.time())
    r = node(f"""
      const ev = require({json.dumps(ev)}), cal = Z.calendar(ev), T = (s) => Date.parse(s) / 1000;
      const L = (k, s, lite) => Z.windowLine(k, T(s), cal, lite || null).text;
      const pcLite = {{ board: {{ lit: {{ window: {{ open: false, open_t: T('2026-11-19T07:00:00Z'), close_t: T('2026-11-19T20:30:00Z') }} }} }} }};
      out({{ pre: L('lit', '2026-11-18T06:00:00Z'), open: L('lit', '2026-11-18T15:00:00Z'), after: L('lit', '2026-11-18T21:00:00Z'),
             thx: L('lit', '2026-11-26T15:00:00Z'), early: L('lit', '2026-11-27T17:50:00Z'), sat: L('lit', '2026-11-21T15:00:00Z'),
             monA: L('atlas', '2026-11-23T08:30:00Z'), tueA: L('atlas', '2026-11-24T10:30:00Z'), lateA: L('atlas', '2026-11-24T17:30:00Z'),
             pc: Z.windowLine('lit', T('2026-11-18T21:00:00Z'), cal, pcLite), closed: cal.closed['2026-11-26'] === true, ec: cal.early['2026-11-27'],
             notes: Z.notes(ev, T('2026-11-24T12:00:00Z'), 7), none: Z.notes(null, T('2026-11-24T12:00:00Z'), 7) }});
    """)
    check("c. Zlarior: before 02:00 'Next: Today 02:00-15:30', inside 'Open now until 15:30', after 15:30 'Tomorrow'",
          str(r.get("pre", "")).startswith("Next: Today 02:00-15:30 ET") and str(r.get("open", "")).startswith("Open now: until 15:30 ET")
          and str(r.get("after", "")).startswith("Next: Tomorrow 02:00-15:30 ET"), r)
    check("c. Thanksgiving closed -> Fri Nov 27, where the 13:15 early close ends entries at 13:00; Saturday -> Monday",
          r.get("closed") is True and r.get("ec") == 795 and str(r.get("thx", "")).startswith("Next: Tomorrow 02:00-13:00 ET")
          and str(r.get("early", "")).startswith("Open now: until 13:00 ET") and str(r.get("sat", "")).startswith("Next: Mon Nov 23 02:00-15:30 ET"), r)
    check("c. ATLAS: Monday 03:30 = MACD open (EMA skips Mondays), Tuesday 05:30 = EMA open until 09:30, 12:30 = tomorrow's MACD 02:00",
          str(r.get("monA", "")).startswith("Open now: MACD until 05:00") and str(r.get("tueA", "")).startswith("Open now: EMA until 09:30")
          and str(r.get("lateA", "")).startswith("Next: Tomorrow MACD 02:00-05:00 ET"), r)
    pc = r.get("pc") or {}
    check("c. the PC's own window wins when it sent one ('from your PC')", "from your PC" in str(pc.get("sub")) and "02:00-15:30" in str(pc.get("text")), pc)
    nt = (r.get("notes") or {}).get("items") or []
    kinds = [x.get("kind") for x in nt]
    check("c. notes, next 7 days from Nov 24: Thanksgiving closed + the Nov 27 early close, in day order; no calendar -> null (skipped)",
          "closed" in kinds and "early" in kinds and [x["day"] for x in nt] == sorted(x["day"] for x in nt) and r.get("none") is None, nt)

    lite = lite_fixture(now)
    r2 = node(f"""
      const plan = require({json.dumps(plan)}), lite = {json.dumps(lite)}, now = {now};
      const cards = MM.cards({{ lite, plan, board: null, coach: PC, today: Z.et(now).day }}, now);
      const rows = cards.map((c) => Z.acctRow(c, now));
      const fresh = Z.pcLine(BM, BM.pick({{ lite, plan }}, now), now);
      const copy = {{ kind: 'olympus-board', src: 'cloud', t: now - 3600, pc: {{ t: now - 10 * 86400 }}, accounts: [] }};
      const old = Z.pcLine(BM, BM.pick({{ site: copy, plan }}, now), now), never = Z.pcLine(BM, BM.pick({{ plan }}, now), now);
      out({{ rows, fresh, old, never }});
    """)
    rows = {x["key"]: x for x in r2.get("rows") or []}
    z, a, f = rows.get("zlarior") or {}, rows.get("atlas") or {}, rows.get("fresh25") or {}
    check("c. rows matched by PC id: Zlarior 50K eval, ATLAS funded, the 25K #2 eval on its OWN row; the Rapid plan (not bought) left out; no BLITZ",
          set(rows) == {"zlarior", "atlas", "fresh25"} and z.get("balance") == 49192.78 and f.get("balance") == 25210.0 and a.get("balance") == 25080.0, list(rows))
    check("c. eval rows: '$ to pass' + today's $ (+$120 / +$210); chips Evaluation",
          z.get("goal") == "$3,807 to pass" and z.get("todayText") == "Today: +$120" and f.get("goal") == "$1,290 to pass" and f.get("todayText") == "Today: +$210"
          and z.get("cls") == "eval" and z.get("chip") == "Evaluation", (z, f))
    check("c. ATLAS funded: chip Sim Funded, the payout coach's sentence, today -$40", a.get("cls") == "funded" and a.get("chip") == "Sim Funded"
          and re.search(r"PAYOUT READY|Not yet|MFFU would pay|Type the balance", str(a.get("goal"))) and a.get("todayText") == "Today: -$40", a)
    fr, old, nev = r2.get("fresh") or {}, r2.get("old") or {}, r2.get("never") or {}
    check("c. PC line: 'PC reported 4 min ago' (fresh feed), red PC SILENT on a 10-day-old copy, 'never reported' with nothing",
          fr.get("text") == "PC reported 4 min ago" and fr.get("silent") is False and old.get("silent") is True and "10 days ago" in str(old.get("text"))
          and nev.get("silent") is True and "never" in str(nev.get("text")), (fr, old, nev))


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def part_d():
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:  # noqa: BLE001
        print(f"[SKIP] d. browser (playwright missing: {e})")
        return
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=WEB))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}/hub/zeus.html"
    now = int(time.time())
    zl = {"d": time.strftime("%Y-%m-%d", time.localtime(now)), "t": now - 3600, "p": 1,
          "s": "Zlarior 1 trade +$208, edge GREEN, nothing to change \u00b7 ATLAS no trade, edge AMBER, slipping in calm markets: watching"}
    msg = json.dumps({"id": "x1", "time": now - 240, "event": "message", "topic": "t", "message": json.dumps({**lite_fixture(now), "zl": zl})})
    stale = {"v": 1, "kind": "olympus-board", "t": now - 3600, "src": "cloud", "pc": {"t": now - 10 * 86400, "via": "heartbeat", "stale": True},
             "accounts": [], "events": []}
    try:
        with sync_playwright() as pw:
            exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
            br = pw.chromium.launch(**({"executable_path": exe} if exe else {}))
            ctx = br.new_context(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True)
            errs: list = []
            p = ctx.new_page()
            p.set_default_timeout(30000)
            p.on("pageerror", lambda e: errs.append(str(e)))
            p.route("**/ntfy.sh/**", lambda r: r.fulfill(status=200, content_type="application/x-ndjson", body=msg + "\n"))
            p.goto(base)
            p.wait_for_function("window.ZEUS_PAGE && window.ZEUS_PAGE.ready")
            pc = p.evaluate("(() => { const b = document.getElementById('pc'); return { cls: b.className, t: b.textContent }; })()")
            accts = p.eval_on_selector_all(".zs-acct", "els => els.map(e => ({ k: e.dataset.key, t: e.textContent }))")
            txt = {a["k"]: a["t"] for a in accts}
            check("d. 390 px: 'PC reported 4 min ago' (not red), rows Zlarior $49,193 / ATLAS Sim Funded / Zlarior 25K #2 $25,210 with $ to pass + today's $",
                  "good" in pc["cls"] and "PC reported 4 min ago" in pc["t"] and "$49,193" in txt.get("zlarior", "") and "$3,807 to pass" in txt.get("zlarior", "")
                  and "Today: +$120" in txt.get("zlarior", "") and "Sim Funded" in txt.get("atlas", "") and "$25,210" in txt.get("fresh25", ""), (pc, accts))
            edge = p.evaluate("(() => { const e = document.getElementById('edgeChip'); return { hidden: e.hidden, t: e.textContent }; })()")
            check("d. the ZEUS edge chip shows Zlarior + ATLAS (from the PC's eh)", not edge["hidden"] and "GREEN" in edge["t"] and "ATLAS" in edge["t"], edge)
            lc = p.evaluate("(() => { const s = document.getElementById('learned'); return { hidden: s.hidden, rows: s.querySelectorAll('li').length, t: s.textContent }; })()")
            check("d. ZEUS learned card (the PC's nightly line, status 'zl'): one row per strategy, 1 idea for Decide, 'changed nothing'",
                  not lc["hidden"] and lc["rows"] == 2 and "Zlarior" in lc["t"] and "slipping in calm markets" in lc["t"] and "1 idea" in lc["t"]
                  and "changed nothing" in lc["t"], lc)
            wins = p.eval_on_selector_all(".zs-win", "els => els.map(e => e.textContent)")
            check("d. Today: two window lines (Zlarior, ATLAS), each 'Open now' or 'Next'",
                  len(wins) == 2 and wins[0].startswith("Zlarior") and wins[1].startswith("ATLAS") and all(re.search(r"Open now|Next:|No entry window", w) for w in wins), wins)
            btns = p.eval_on_selector_all(".zs-btn:not([hidden]), .zs-info summary", "els => els.map(e => { const r = e.getBoundingClientRect(); return [e.textContent.trim().split(/\\s{2,}|(?<=[a-z])(?=[A-Z])/)[0], Math.round(r.width), Math.round(r.height)]; })")
            small = [b for b in btns if b[1] < 44 or b[2] < 44]
            check("d. the big buttons (6 links + Safety + Add an account; Weekly review hidden: no week.html), every tap >= 44 px",
                  len(btns) == (8 if not os.path.isfile(os.path.join(WEB, "business", "week.html")) else 9) and not small, (btns, small))
            p.click("#safety summary")
            sh = p.evaluate("(() => { const s = document.getElementById('safety'); return { open: s.open, links: s.querySelectorAll('a').length, t: s.textContent }; })()")
            wide = p.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
            taps = p.evaluate("[...document.querySelectorAll('.zs-nav a, .zs-nav button')].every((e) => e.getBoundingClientRect().height >= 44)")
            check("d. Safety opens an explanation (Tailscale, /safety/), no link in it; no sideways scroll; top buttons 44 px",
                  sh["open"] and sh["links"] == 0 and "/safety/" in sh["t"] and wide and taps, (sh["open"], sh["links"], wide, taps))
            p2 = ctx.new_page()
            p2.on("pageerror", lambda e: errs.append(str(e)))
            p2.route("**/ntfy.sh/**", lambda r: r.fulfill(status=200, body=""))
            p2.route("**/board/board.json*", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(stale)))
            p2.route("**/hub/learned.json*", lambda r: r.fulfill(status=404, body=""))
            p2.goto(base)
            p2.wait_for_function("window.ZEUS_PAGE && window.ZEUS_PAGE.ready")
            pc2 = p2.evaluate("(() => { const b = document.getElementById('pc'); return { cls: b.className, t: b.textContent, bg: getComputedStyle(b).backgroundColor, role: b.getAttribute('role') }; })()")
            n2 = p2.eval_on_selector_all(".zs-acct", "els => els.map(e => e.dataset.key)")
            check("d. silent feed + 10-day-old board copy: the strip is RED 'PC SILENT: last report 10 days ago' (role alert), plan rows still shown",
                  "bad" in pc2["cls"] and "PC SILENT" in pc2["t"] and "10 days ago" in pc2["t"] and pc2["role"] == "alert" and pc2["bg"] != "rgba(0, 0, 0, 0)"
                  and "zlarior" in n2, (pc2, n2))
            lw = p2.evaluate("(() => { const s = document.getElementById('learned'), b = document.getElementById('learnBox'); return { hidden: s.hidden, cls: b.className, t: b.textContent, li: b.querySelectorAll('li').length }; })()")
            check("d. no learned line anywhere (silent feed, no learned.json): the ZEUS learned card shows a calm 'First nightly report after today's close' (never hidden, no rows)",
                  lw["hidden"] is False and "wait" in lw["cls"] and lw["t"].startswith("First nightly report after today's close") and "ZEUS changes nothing" in lw["t"] and lw["li"] == 0, lw)
            check("d. no page errors", not errs, errs)
            br.close()
    finally:
        srv.shutdown()


def part_e_static():
    zen, jar, core = rd(WEB, "index.html"), rd(WEB, "jarvis", "index.html"), rd(WEB, "olympus", "zeus_core.js")
    check("e. both homes load the ONE shared module (olympus/zeus_core.js) and the ZEUS page uses it too; the card links hub/zeus.html",
          'src="olympus/zeus_core.js?v=' in zen and "Z.keep(pg" in zen and 'src="../olympus/zeus_core.js?v=' in jar and 'id="zeusCard" data-zeus-card' in jar
          and 'src="../olympus/zeus_core.js?v=' in rd(HUB, "zeus.html") and "url('../hub/zeus.html')" in core)
    check("e. Jarvis: the ZEUS card sits right after the greeting, before the three tiles", jar.index('id="hello"') < jar.index('id="zeusCard"') < jar.index('id="hfirst"'))
    check("e. zeus_core.js: text only, GET only, no outside address, nothing stored but its own height",
          not re.search(r"innerHTML|insertAdjacentHTML|document\.write|\beval\(|https?://|method:|localStorage", re.sub(r"localStorage\.(getItem|setItem)\(HKEY", "", core)))
    now = int(time.time())
    plan = os.path.join(WEB, "business", "accounts.json")
    r = node(f"""
      const C = require({json.dumps(os.path.join(WEB, 'olympus', 'zeus_core.js'))}), plan = require({json.dumps(plan)}), lite = {json.dumps(lite_fixture(now))}, now = {now};
      const s = C.summary({{ lite, plan, BM, MM, coach: PC }}, now);
      const cards = MM.cards({{ lite, plan, board: null, coach: PC, today: Z.et(now).day }}, now).map((c) => Z.acctRow(c, now));
      out({{ pc: s.pc, rows: s.rows, same: JSON.stringify(s.rows) === JSON.stringify(cards), mode: s.mode }});
    """)
    keys = [x.get("key") for x in r.get("rows") or []]
    check("e. node: summary() = the ZEUS page's rows (same matching, not a copy): 3 real accounts, 'PC reported 4 min ago'",
          r.get("same") is True and set(keys) == {"zlarior", "atlas", "fresh25"} and (r.get("pc") or {}).get("text") == "PC reported 4 min ago", r)


def part_e_browser():
    try:
        from playwright.sync_api import sync_playwright
    except Exception as e:  # noqa: BLE001
        print(f"[SKIP] e. browser (playwright missing: {e})")
        return
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=WEB))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}/"
    now = int(time.time())
    msg = json.dumps({"id": "x1", "time": now - 240, "event": "message", "topic": "t", "message": json.dumps(lite_fixture(now))})
    stale = {"v": 1, "kind": "olympus-board", "t": now - 3600, "src": "cloud", "pc": {"t": now - 10 * 86400, "via": "heartbeat", "stale": True},
             "accounts": [], "events": []}
    CARD = """(sel) => { const c = document.querySelector(sel); if (!c) return null; const a = c.querySelector('.zeus-go'), pc = c.querySelector('.zeus-pc'), e = c.querySelector('.zeus-edge');
      return { rows: [...c.querySelectorAll('.zeus-row')].map((r) => [r.dataset.key, r.textContent]), pc: pc.textContent, cls: pc.className, href: a.getAttribute('href'),
        edge: e && !e.hidden ? e.textContent : '', top: Math.round(c.getBoundingClientRect().top), h: Math.round(a.getBoundingClientRect().height),
        wide: document.documentElement.scrollWidth <= innerWidth + 1 }; }"""
    try:
        with sync_playwright() as pw:
            exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
            br = pw.chromium.launch(**({"executable_path": exe} if exe else {}))
            ctx = br.new_context(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True)
            errs: list = []
            ctx.route("**/ntfy.sh/**", lambda r: r.fulfill(status=200, content_type="application/x-ndjson", body=msg + "\n"))
            p = ctx.new_page()
            p.set_default_timeout(45000)
            p.on("pageerror", lambda e: errs.append("zenith: " + str(e)))
            p.goto(base + "index.html#/today")
            p.wait_for_function("document.querySelectorAll('#page > .zeus-card .zeus-row').length === 3 && !!document.querySelector('#page > .zeus-card .zeus-edge:not([hidden])')")
            z = p.evaluate("(" + CARD + ")('#page > .zeus-card')")
            first = p.evaluate("document.querySelector('#page').firstElementChild.className")
            txt = {k: t for k, t in z["rows"]}
            check("e. Zenith Home starts with the ZEUS card: 'PC reported 4 min ago', Zlarior $49,193 · $3,807 to pass · +$120 today, ATLAS Funded + payout line, 25K #2 $25,210",
                  first.startswith("zeus-card") and "PC reported 4 min ago" in z["pc"] and "good" in z["cls"] and "$49,193" in txt.get("zlarior", "")
                  and "$3,807 to pass" in txt.get("zlarior", "") and "+$120 today" in txt.get("zlarior", "") and "Funded" in txt.get("atlas", "")
                  and "$25,210" in txt.get("fresh25", "") and "BLITZ" not in str(z["rows"]), (first, z))
            check("e. Zenith: the edge chip in the card (GREEN, ATLAS), a tap opens hub/zeus.html, a 44 px tap, no sideways scroll",
                  "GREEN" in z["edge"] and "ATLAS" in z["edge"] and z["href"].endswith("/hub/zeus.html") and z["h"] >= 44 and z["wide"], z)
            p.evaluate("location.hash = '#/perf'")
            p.wait_for_timeout(1200)
            gone = p.evaluate("!document.querySelector('#page > .zeus-card')")
            p.evaluate("location.hash = '#/today'")
            p.wait_for_function("!!document.querySelector('#page > .zeus-card .zeus-row')")
            back = p.evaluate("document.querySelector('#page').firstElementChild.className.startsWith('zeus-card')")
            check("e. Zenith: only on Home (gone on Results, first again back on Home)", gone and back, (gone, back))
            j = ctx.new_page()
            j.set_default_timeout(60000)
            j.on("pageerror", lambda e: errs.append("jarvis: " + str(e)))
            j.goto(base + "jarvis/")
            j.wait_for_function("document.querySelectorAll('#zeusCard .zeus-row').length === 3")
            jc = j.evaluate("(" + CARD + ")('#zeusCard .zeus-card')")
            order = j.evaluate("(() => { const z = document.getElementById('zeusCard').getBoundingClientRect(), t = document.getElementById('hfirst').getBoundingClientRect(), h = document.getElementById('hello').getBoundingClientRect(); return [Math.round(h.top), Math.round(z.top), Math.round(t.top)]; })()")
            check("e. Jarvis: the ZEUS card under the greeting, above the tiles: PC reported, the 3 accounts, a tap opens hub/zeus.html",
                  "PC reported 4 min ago" in jc["pc"] and len(jc["rows"]) == 3 and jc["href"].endswith("/hub/zeus.html") and order[0] < order[1] < order[2], (jc, order))
            # phone QA 2026-11-19: the card grew under the opening's hand-off ("Asking your PC..." -> 3 rows -> the chip) and pushed the home
            # down twice. Its space is held from the first frame (this phone's last height, else a typical card) and released once it is full.
            j.wait_for_function("!document.querySelector('#zeusCardBox').style.minHeight && !!localStorage.getItem('olympus.zeus.cardh')", timeout=20000)
            full = j.evaluate("[document.querySelector('#zeusCardBox').offsetHeight, +localStorage.getItem('olympus.zeus.cardh')]")
            j2 = ctx.new_page()
            j2.set_default_timeout(60000)
            j2.on("pageerror", lambda e: errs.append("jarvis2: " + str(e)))
            j2.goto(base + "jarvis/", wait_until="domcontentloaded")
            early = j2.evaluate("(() => { const c = document.querySelector('#zeusCardBox'); return c ? [c.style.minHeight, c.querySelectorAll('.zeus-row').length, c.offsetHeight] : null; })()")
            j2.wait_for_function("document.querySelectorAll('#zeusCard .zeus-row').length === 3 && !document.querySelector('#zeusCardBox').style.minHeight", timeout=20000)
            late = j2.evaluate("document.querySelector('#zeusCardBox').offsetHeight")
            check("e. Jarvis: the ZEUS card holds its full height from the first frame (no jump when the PC's numbers and the chip arrive), "
                  "then keeps the real height for next time", full[0] == full[1] and early and early[0] == f"{full[1]}px" and early[1] == 0
                  and abs(early[2] - late) <= 2, (full, early, late))
            j2.close()
            ctx.unroute("**/ntfy.sh/**")
            ctx.route("**/ntfy.sh/**", lambda r: r.fulfill(status=200, body=""))
            ctx.route("**/board/board.json*", lambda r: r.fulfill(status=200, content_type="application/json", body=json.dumps(stale)))
            s = ctx.new_page()
            s.on("pageerror", lambda e: errs.append("silent: " + str(e)))
            s.goto(base + "index.html#/today")
            s.wait_for_function("!!document.querySelector('#page > .zeus-card .zeus-pc.bad')")
            sc = s.evaluate("(" + CARD + ")('#page > .zeus-card')")
            check("e. silent feed + 10-day-old copy: the card says red 'PC SILENT: last report 10 days ago' (role alert), plan rows still shown",
                  "PC SILENT" in sc["pc"] and "10 days ago" in sc["pc"] and "bad" in sc["cls"] and any(k == "zlarior" for k, _ in sc["rows"]), sc)
            check("e. no page errors from the card", not [e for e in errs if "zeus" in e.lower() or "zc" in e.lower() or "ZEUS_CORE" in e], errs)
            br.close()
    finally:
        srv.shutdown()


def main():
    part_a()
    part_b()
    part_c()
    part_e_static()
    part_f()
    if not os.environ.get("ZEUS_NO_BROWSER"):
        part_d()
        part_e_browser()
    n = sum(RES)
    print(f"\nzeus_hub: {n}/{len(RES)} " + ("ALL PASS" if n == len(RES) else "FAILED"))
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
