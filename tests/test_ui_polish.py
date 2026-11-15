"""Night 3 (2026-10-30, owner: "more very useful features ... clean it up, organized ... the UI, quality, the effects ...
I wanna be shocked"): the status bar, the three account cards, what matters now, the Sunday open card, the search palette,
the one section order on every bot tab, Money = real money only, the motion system and the once-a-day intro, on both
dashboards (read-only UI).

  a. static   statuscore.js byte-identical on both apps, the phone loads statuscore.js + polish.js after blitz.js and
              polish.css in the head, caches bumped (phone le-public-v46+, PC le-shell-next-v28+), clean.js?v=3 kept,
              read-only (no fetch / POST in the renderers), FEATURES.md lists the features, the PC sidebar sections
  b. node     StatusUI from the live-board fixture (2 and 3 accounts): the status items, the account cards (ring, REAL /
              SIM tag, the day in one line), the Sunday open card on the clock-change weekend (and not on a Tuesday),
              smart empty states; garbage in = no exception
  c. phone    Playwright 390x844 on a copy of tools/web_public: every tab and every bot section renders with no page error
              and no sideways scroll; the status bar folds open; "Everything else on Home" keeps every older card; the
              palette finds a page and opens it; Money opens Real results; the intro shows once a day and is skippable;
              reduced motion = no intro and no animation; frame time while scrolling Home; the light theme
  d. PC       Playwright 1440x900 on server.py: the status bar on Home, the sidebar sections, five sections on BLITZ

  "Money now" (2026-11-04, moneynowcore.js on both apps): the top card of Home that answers in 5 seconds: per account "Drawdown left $X of $max loss"
  (never "X of 10 days"), today's $, the next thing the bot waits for, its status in plain words, a red / amber / green edge, "not published yet"
  for a missing field; static (a), node (b: the model from the boards, edges, missing fields, garbage), phone (c: top of Home, 44 px taps, a tap opens
  the bot), PC (d: first thing in the status box on Home)

  python -X utf8 -m tests.test_ui_polish [--shots <dir>]
"""
from __future__ import annotations

import json
from datetime import date
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

from tests import browser_kit as BK  # noqa: E402  (shared launch: one reused browser, load-scaled timeouts, one retry of a flaky wait)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
RES = []
PERF = {}


def check(name, cond, info=""):
    RES.append(bool(cond))
    print(("[PASS] " if cond else "[FAIL] ") + name + ("" if cond else f"  -> {str(info)[:500]}"), flush=True)


def rd(*p):
    with open(os.path.join(ROOT, *p), encoding="utf-8") as f:
        return f.read()


# ------------------------------------------------------------------------------------------------ a. static
def part_a():
    check("a. statuscore.js byte-identical on both apps", rd("tools", "web_public", "statuscore.js") == rd("web_next", "js", "next", "statuscore.js"))
    idx, psw, sw = rd("tools", "web_public", "index.html"), rd("tools", "web_public", "sw.js"), rd("web_next", "sw.js")
    order = [idx.find(f'src="{n}?v=') for n in ("blitz.js", "statuscore.js", "polish.js")]
    check("a. phone index: statuscore.js then polish.js after blitz.js (last), polish.css in the head", all(i > 0 for i in order) and order == sorted(order)
          and idx.find('polish.css?v=') < idx.find('</head>') and idx.find('polish.css?v=') > 0, order)
    check("a. moneynowcore.js byte-identical on both apps; the phone loads it and moneynow.js after zenith_money.js; the PC polish.js loads it; read-only (no fetch / POST / innerHTML)",
          rd("tools", "web_public", "moneynowcore.js") == rd("web_next", "js", "next", "moneynowcore.js")
          and [idx.find(f'src="{n}?v=') for n in ("zenith_money.js", "moneynowcore.js", "moneynow.js")] == sorted(idx.find(f'src="{n}?v=') for n in ("zenith_money.js", "moneynowcore.js", "moneynow.js"))
          and idx.find('src="moneynow.js?v=') > 0 and "moneynowcore.js" in rd("web_next", "js", "next", "polish.js")
          and not re.search(r"fetch\(|POST|innerHTML|/api/|arm_c", rd("tools", "web_public", "moneynowcore.js")) and "fetch(" not in rd("tools", "web_public", "moneynow.js"))
    check("a. sessioncore.js (window.SessionDay) + sessionday.js: the phone loads them after moneynow.js; read-only (no fetch / POST / innerHTML / arm / route / api)",
          idx.find('src="sessioncore.js?v=') > idx.find('src="moneynow.js?v=') > 0 and idx.find('src="sessionday.js?v=') > idx.find('src="sessioncore.js?v=')
          and not re.search(r"fetch\(|POST|innerHTML|/api/|arm_c|route\(", rd("tools", "web_public", "sessioncore.js")) and "fetch(" not in rd("tools", "web_public", "sessionday.js"))
    check("a. caches: phone le-public-v46+, PC le-shell-next-v28+; clean.js?v=3 kept", int(re.search(r"le-public-v(\d+)", psw).group(1)) >= 46
          and int(re.search(r"le-shell-next-v(\d+)", sw).group(1)) >= 28 and 'clean.js?v=3"' in idx and "/css/polish.css" in sw)
    for n in ("statuscore.js", "polish.js"):
        src = rd("tools", "web_public", n)
        check(f"a. {n} is read-only (no fetch, no POST, no arm / route / order call)", "fetch(" not in src and "POST" not in src and "/api/" not in src and "arm_c" not in src)
    pj = rd("web_next", "js", "next", "polish.js")
    check("a. PC polish.js only GETs (board, news)", "POST" not in pj and "method:" not in pj)
    cl, rt = rd("tools", "web_public", "clean.js"), rd("web_next", "js", "next", "routes.js")
    check("a. one section order on every bot tab (phone): Today · Brain · Trades · Results · Rules", all(
        re.findall(r"\['(Today|Brain|Trades|Results|Rules|Plan|Strategy|Setups|Go live)', \[", cl[cl.index(f"const {k} = ["):cl.index("];", cl.index(f"const {k} = ["))])
        == ["Today", "Brain", "Trades", "Results", "Rules"] for k in ("ZL_SEGS", "AT_SEGS", "BZ_SEGS")))
    bots = rt[rt.index("export const BOTS"):rt.index("export const BOT_CHIP")]
    check("a. one section order on every bot page (PC)", [re.findall(r"\['(\w[\w &]*)', \[", b) for b in re.split(r"\n  \w+: \{", bots)[1:]] == [["Today", "Brain", "Trades", "Results", "Rules"]] * 3,
          [re.findall(r"\['(\w[\w &]*)', \[", b) for b in re.split(r"\n  \w+: \{", bots)[1:]])
    check("a. PC sidebar: Main in plain sections (Bots · Live · Money · Insight)", "export const MAIN_SECTIONS" in rt and "['Bots', ['zlarior', 'atlas', 'blitz']]" in rt
          and "MAIN_SECTIONS" in rd("web_next", "js", "next", "shell.js"))
    check("a. Money tab = real money only (Real results, Accounts today, Eval timeline)", "const TAB_MAIN = { money: ['real', 'realtoday', 'evaltl'] }" in cl)
    fm = rd("web_next", "FEATURES.md")
    check("a. FEATURES.md lists the night-3 features (82+)", "| 82 |" in fm and "Status bar" in fm and "Sunday open" in fm and "palette" in fm.lower())
    pc, nc = rd("tools", "web_public", "polish.css"), rd("web_next", "css", "polish.css")
    check("a. no looping polish animation and no card entrance on the 3D / chart pages (Holodeck, Live View)",
          ':root[data-page="holo"] .pl-tdot' in pc and ':root[data-page="liveview"] .su-dot.live::after' in pc
          and "NO_ENTER = new Set(['today', 'holo', 'liveview'])" in rd("tools", "web_public", "polish.js"))
    check("a. crisp icons on both apps (a heavier, exact stroke on the 24 grid)", "svg.ico { stroke-width: 1.9; shape-rendering: geometricPrecision; }" in pc
          and ".nx svg.ico { stroke-width: 1.9; shape-rendering: geometricPrecision; }" in nc)


# ------------------------------------------------------------------------------------------------ b. node
NODE_JS = r"""
global.window = {}; global.document = undefined;
const dir = process.argv[2], fs = require('fs');
for (const n of ['missioncore.js', 'deckcore.js', 'statuscore.js', 'moneynowcore.js', 'sessioncore.js']) require(dir + '/' + n);
const F = JSON.parse(fs.readFileSync(process.argv[3], 'utf8')), S = window.StatusUI, out = { bad: 0 };
const thu = Date.parse('2026-10-30T01:15:00Z') / 1000, tue = Date.parse('2026-10-27T15:00:00Z') / 1000;
const M2 = { now: F.now, where: 'phone', board: F.b2 }, M3 = { now: F.now, where: 'phone', board: F.b3 };
out.items2 = S.items(M2).map((x) => [x.k, x.lvl, x.value]); out.sum2 = S.summary(M2);
out.acc2 = S.accounts(M2, { where: 'phone' }); out.acc3 = S.accounts(M3, { where: 'phone' }); out.bar = S.bar(M3, { open: true, more: '<a>x</a>' });
out.one = ['lit', 'atlas', 'blitz'].map((k) => { const A = window.MissionUI.accounts(M3).find((a) => a.key === k); return A ? S.oneLine(A, M3).text : null; });
out.sunThu = S.sunday({ now: thu, board: F.b2 }); out.sunTue = S.sunday({ now: tue, board: F.b2 }); out.dst = S.dstNext(thu);
out.empty = ['trades', 'real', 'blitz', 'mind', 'feed', 'x'].map((k) => S.empty(k, M2));
const sat = Date.parse('2026-10-31T16:00:00Z') / 1000;
out.pcSat = S.items({ now: sat, board: Object.assign({}, F.b2, { data_t: sat - 150000 }) }).find((x) => x.k === 'pc');
out.pcTue = S.items({ now: tue, board: Object.assign({}, F.b2, { data_t: tue - 7200 }) }).find((x) => x.k === 'pc');
out.mkt = S.market(M2); out.mktNone = S.market({ board: {} }); out.hasMap = !!(F.b2.map && F.b2.map.price != null);
for (const g of [null, {}, { board: 5 }, { board: { lit: 'x', health: { items: 3 } } }, { board: { lit: { position: 5, window: 'y', days: 7 } }, news: 'n' }, { board: { map: { price: 'x', nearest_above: 3 } } }, { board: { map: { price: 5, nearest_above: { price: 1 }, nearest_below: { price: 9 } } } }]) {
  try { S.items(g); S.bar(g); S.accounts(g); S.sunday(g || {}); S.empty('trades', g); S.market(g); S.week(g); } catch (e) { out.bad++; out.err = String(e.stack).slice(0, 300); }
}
const MN = window.MoneyNow, cp = (o) => JSON.parse(JSON.stringify(o));
const mk = (mut) => { const b = cp(F.b3); mut(b); return { now: F.now, where: 'phone', board: b }; };
out.mn2 = MN.model(M2); out.mn3 = MN.model(M3); out.mnNone = MN.model({}); out.mnNoneHtml = MN.html({}, { where: 'phone' });
out.mnHtml3 = MN.html(M3, { where: 'phone' }); out.mnPc = MN.html(M3, { where: 'pc' });
out.mnRaw = window.MissionUI.accounts(M3).map((a) => [a.key, a.placeholder, a.room, a.mll, a.today]);
out.mnRed = MN.model(mk((b) => { b.lit.room = 300; b.lit.room_frac = 0.15; })).rows[0].edge;
out.mnAmb = MN.model(mk((b) => { b.lit.room = 800; b.lit.room_frac = 0.4; })).rows[0].edge;
out.mnMiss = MN.model(mk((b) => { delete b.lit.room; delete b.lit.today_pnl; delete b.lit.mll; delete b.lit.room_frac; }));
out.mnMissHtml = MN.html(mk((b) => { delete b.lit.room; delete b.lit.today_pnl; delete b.lit.mll; delete b.lit.room_frac; }), { where: 'phone' });
out.mnStop = MN.model(Object.assign(mk(() => {}), { board: Object.assign(cp(F.b3), { running: false }) })).bot;
out.mnOld = MN.model({ now: F.now, where: 'phone', board: Object.assign(cp(F.b3), { data_t: F.now - 7200 }) }).bot;
out.mnEvil = MN.html(mk((b) => { b.lit.name = '<img src=x onerror=1>'; b.lit.waiting = '"><script>1</script>'; b.lit.position = null; }), { where: 'phone' });
out.lnPc = MN.line(M3, { where: 'pc' }); out.lnStop = MN.line(Object.assign(mk(() => {}), { board: Object.assign(cp(F.b3), { running: false }) }), { where: 'pc' });
out.lnNone = MN.line({}, { where: 'pc' }); out.lnEvil = MN.line(mk((b) => { b.lit.name = '<img src=x onerror=1>'; }), { where: 'pc' }); out.lnArmed = MN.model(M3).rows.filter((r) => /^(Armed|In a trade)/.test(r.status.text)).map((r) => r.name);
for (const g of [null, {}, { board: 5 }, { board: { lit: 'x', health: { items: 3 } } }, { board: { lit: { room: 'x', mll: {}, today_pnl: [], position: 5 } }, now: 'n' }]) {
  try { MN.model(g); MN.html(g); MN.html(g, { where: 'pc' }); MN.line(g); MN.line(g, { where: 'phone' }); } catch (e) { out.bad++; out.err = String(e.stack).slice(0, 300); }
}
const SD = window.SessionDay, T = F.sd || {}, nm = (M) => { const m = SD.model(M); return { mode: m.mode, pill: m.pill, edge: m.edge, states: m.rows.map((r) => r.state), keys: m.rows.map((r) => r.key), t: m.rows.map((r) => r.t), tEnd: m.rows.map((r) => r.tEnd), todo: m.todo, doing: m.doing, left: m.left, day: m.day, holiday: m.holiday, news: m.news, newsKnown: m.newsKnown }; };
out.sd = {};
for (const [k, t] of Object.entries(T)) out.sd[k] = nm({ now: t, where: 'phone', board: Object.assign(cp(F.b3), { data_t: t - 30 }) });
out.sdNoBoard = Object.fromEntries(Object.entries(T).map(([k, t]) => [k, nm({ now: t })]));
out.sdHtml = SD.html({ now: T.open, where: 'phone', board: F.b3, news: F.news }, { go: (p) => 'data-go="' + p + '"' });
out.sdHtmlNone = SD.html({ now: T.open }, {}); out.sdHtmlNoNews = SD.html({ now: T.open, news: [] }, {});
out.sdHtmlHol = SD.html({ now: T.holiday, news: [] }, {});
out.sdNews = SD.model({ now: T.open, news: F.news }).news;
out.sdStop = SD.model({ now: T.open, board: Object.assign(cp(F.b3), { running: false, data_t: T.open - 30 }) }).todo;
out.sdBlocked = SD.model({ now: T.open, board: (() => { const b = cp(F.b3); b.data_t = T.open - 30; b.lit.position = null; b.lit.blocks = [{ kind: 'rule', text: 'Daily loss limit <b>hit</b>.' }]; return b; })() }).todo;
out.sdHol = [2026, 2027, 2028].map((y) => SD.holidays(y));
for (const g of [null, {}, { board: 5 }, { news: 'x' }, { news: [null, { t: 'x' }, { t: 1, title: {} }], now: 'n' }, { now: NaN }]) {
  try { SD.model(g); SD.html(g); SD.html(g, {}); } catch (e) { out.bad++; out.err = String(e.stack).slice(0, 300); }
}
process.stdout.write(JSON.stringify(out) + '\n');
"""


def part_b(tmp):
    node = shutil.which("node")
    if not node:
        print("[SKIP] b. node render: node not installed")
        return
    from tests import test_space_ui as SU
    now = int(time.time())
    b2, b3 = SU.boards(now)
    b2["lit"]["badge"], b2["atlas"]["badge"] = "LIVE", "SIM"
    b3["lit"]["badge"], b3["atlas"]["badge"] = "LIVE", "SIM"
    fp = os.path.join(tmp, "f.json")
    from zoneinfo import ZoneInfo
    from datetime import datetime
    ET = ZoneInfo("America/New_York")
    et = lambda y, mo, d, h, mi=0: int(datetime(y, mo, d, h, mi, tzinfo=ET).timestamp())
    SDT = {"early": et(2026, 11, 4, 1, 30), "plan": et(2026, 11, 4, 1, 50), "open": et(2026, 11, 4, 10, 0), "late": et(2026, 11, 4, 15, 40), "flat": et(2026, 11, 4, 16, 0),
           "over": et(2026, 11, 4, 16, 30), "friover": et(2026, 11, 6, 17, 30), "sat": et(2026, 11, 7, 12, 0), "sun": et(2026, 11, 8, 20, 0), "holiday": et(2026, 11, 26, 10, 0),
           "eveholiday": et(2026, 11, 25, 16, 30), "dstbefore": et(2026, 3, 6, 10, 0), "dstafter": et(2026, 3, 10, 10, 0)}
    SDN = [{"t": et(2026, 11, 4, 10, 30), "title": "CPI <img src=x onerror=1>", "impact": "high"}, {"t": et(2026, 11, 4, 14, 0), "title": "FOMC minutes", "impact": "fomc"},
           {"t": et(2026, 11, 4, 11, 0), "title": "Low news", "impact": "low"}, {"t": et(2026, 11, 3, 10, 0), "title": "Yesterday", "impact": "high"}, {"t": et(2026, 11, 4, 18, 0), "title": "After the close", "impact": "high"}]
    json.dump({"now": now, "b2": b2, "b3": b3, "sd": SDT, "news": SDN}, open(fp, "w"), default=str)
    jp = os.path.join(tmp, "r.js")
    open(jp, "w").write(NODE_JS)
    r = subprocess.run([node, jp, os.path.join(ROOT, "tools", "web_public"), fp], capture_output=True, text=True, timeout=60)
    try:
        o = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        check("b. node render ran", False, (r.stdout or "")[-300:] + (r.stderr or "")[-600:])
        return
    keys = [x[0] for x in o["items2"]]
    check("b. status items: PC bot, NinjaTrader, feed, Zlarior, ATLAS, BLITZ, alerts (+ the next window when there is one)",
          keys[:1] == ["pc"] and "nt" in keys and "feed" in keys and keys.index("lit") < keys.index("atlas") < keys.index("blitz") and keys[-1] == "alerts", o["items2"])
    check("b. one summary: a level and one sentence", o["sum2"]["lvl"] in ("good", "warn", "bad") and o["sum2"]["title"], o["sum2"])
    a2, a3 = o["acc2"], o["acc3"]
    check("b. account cards: Zlarior · ATLAS · BLITZ (a paper placeholder until its 25K), the eval ring, $ to the target, the REAL / SIM tag",
          a2.count('<a class="su-acct') == 3 and 'su-acct ph' in a2 and a2.count("su-ring") >= 3 and "to the target" in a2 and ">REAL<" in a2 and ">SIM<" in a2, a2[:400])
    check("b. three real accounts: BLITZ gets its own card with numbers (no placeholder)", a3.count('<a class="su-acct') == 3 and 'su-acct ph' not in a3)
    check("b. the day in one line per bot (Zlarior in a trade)", o["one"][0] and o["one"][0].startswith("In a LONG") and all(o["one"]), o["one"])
    check("b. the status bar: a fold with every line and its fix, the extra links", 'data-su-toggle' in o["bar"] and 'su-list' in o["bar"] and '<a>x</a>' in o["bar"])
    st = re.sub(r"<[^>]+>", " ", o["sunThu"])
    check("b. Sunday open (Thu 21:15 ET before the clock change): clocks back 1 hour on Sun Nov 1, CME reopens Sun 18:00 ET, each bot's first step, BLITZ off",
          "Clocks go back 1 hour" in st and "Sun Nov 1" in st and "Sun 18:00 ET" in st and "Mon 02:00 ET" in st and "Off until its own 25K" in st and "Set time automatically" in st, st[:500])
    check("b. Sunday open: not on a Tuesday; the next clock change is 2026-11-01 06:00 UTC (back)", o["sunTue"] == "" and o["dst"]["t"] == 1793512800 and o["dst"]["way"] == "back", (o["sunTue"][:80], o["dst"]))
    check("b. smart empty states say what will appear and when", all("su-empty" in e for e in o["empty"]) and "within a minute" in o["empty"][0] and "never routed" in o["empty"][2])
    check("b. a quiet PC: grey 'off for the weekend' on Saturday, amber / red on a trading day", o["pcSat"]["lvl"] == "idle" and "weekend" in o["pcSat"]["value"]
          and o["pcTue"]["lvl"] in ("warn", "bad"), (o["pcSat"], o["pcTue"]))
    check("b. NQ now: the price between the nearest levels above / below (a ladder), nothing without a price", o["mktNone"] == ""
          and (not o["hasMap"] or ("su-mkt" in o["mkt"] and "NQ" in o["mkt"])), o["mkt"][:300])
    check("b. garbage in: no exception", o["bad"] == 0, o.get("err"))
    # --- Money now: dynamic counts (the rows follow the accounts the board really has)
    n_real = sum(1 for a in o["mnRaw"] if not a[1])
    r2, r3 = o["mn2"]["rows"], o["mn3"]["rows"]
    check(f"b. Money now: one row per real account, Zlarior and ATLAS always, BLITZ only when it has its own account ({len(r2)} rows on 2 accounts, {len(r3)} on {n_real})",
          [r["key"] for r in r2] == ["lit", "atlas"] and [r["key"] for r in r3] == ["lit", "atlas", "blitz"][:max(2, n_real)] and len(r3) == max(2, n_real), (o["mn2"]["rows"][0]["key"], o["mnRaw"]))
    h3 = o["mnHtml3"]
    txt = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h3))
    ok = True
    for r, raw in zip(r3, o["mnRaw"]):
        room, mll, today = raw[2], raw[3], raw[4]
        ok &= (f"${round(room):,}" in txt and f"of ${round(mll):,} max loss" in txt and r["room"] == room and r["mll"] == mll and r["today"] == today)
    check("b. Money now: 'Drawdown left $X of $max loss' with the board's own room and max loss for every account, today's $ next to it, never 'of 10 days'",
          ok and h3.count("Drawdown left") == len(r3) and h3.count("max loss") == len(r3) and "10 days" not in txt and "session" not in txt.lower() and h3.count('class="mn-r"') == len(r3), txt[:400])
    check("b. Money now: each row says what the bot waits for (an open trade: its target / stop) and its status in plain words (In a trade / Running / Armed ...)",
          all(r["next"] and r["status"]["text"] for r in r3) and "target" in r3[0]["next"] and r3[0]["status"]["text"].startswith("In a trade") and h3.count('class="mn-nx"') == len(r3), [r["next"] for r in r3])
    check("b. Money now: edge colours: a healthy board is green, 15% of the drawdown left is red, 40% is amber", o["mn3"]["edge"] == "good" and o["mnRed"] == "bad" and o["mnAmb"] == "warn", (o["mn3"]["edge"], o["mnRed"], o["mnAmb"]))
    check("b. Money now: the PC bot in plain words: running, stopped (red), quiet for 2 hours (amber / red) - from the same check-in the status bar reads",
          o["mn3"]["bot"]["text"].startswith("Bot running") and o["mnStop"]["text"] == "Bot stopped" and o["mnStop"]["edge"] == "bad" and o["mnOld"]["text"].startswith("Bot quiet") and o["mnOld"]["edge"] in ("warn", "bad"), (o["mnStop"], o["mnOld"]))
    miss = o["mnMissHtml"]
    check("b. Money now: a field the board does not carry says 'not published yet' (never a blank): room, max loss, today", o["mnMiss"]["rows"][0]["room"] is None and o["mnMiss"]["rows"][0]["edge"] in ("warn", "bad")
          and miss.count("not published yet") >= 2 and ">$<" not in miss and "undefined" not in miss and "NaN" not in miss and "null" not in miss, re.sub(r"<[^>]+>", " ", miss)[:300])
    nh = o["mnNoneHtml"]
    check("b. Money now: no board at all (nothing published yet): the card is still there, Zlarior and ATLAS rows, every field 'not published yet', amber",
          len(o["mnNone"]["rows"]) == 2 and nh.count("mn-row") == 2 and nh.count("not published yet") >= 6 and "mn-card a" in nh and o["mnNone"]["edge"] == "warn", nh[:200])
    check("b. Money now: the PC variant links with data-goto (zlarior / atlas / blitz), the phone with data-go (lit / atlas / blitz); text from the board never becomes markup",
          'data-goto="zlarior"' in o["mnPc"] and 'data-go="lit"' in h3 and "<img" not in o["mnEvil"] and "<script" not in o["mnEvil"] and "&lt;img" in o["mnEvil"])
    ltxt = lambda h: re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", h)).strip()
    check("b. status strip (MoneyNow.line): one line with the bot's state + last check-in age and which bots are armed, a data-goto link, a red/amber/green dot",
          o["lnPc"].count('<a class="mn-line') == 1 and 'data-goto="cc"' in o["lnPc"] and ltxt(o["lnPc"]).startswith("Bot running") and "Armed:" in o["lnPc"]
          and all(n in o["lnPc"] for n in o["lnArmed"]) and 'class="mn-line g"' in o["lnPc"], ltxt(o["lnPc"]))
    check("b. status strip: a stopped bot is red, no board at all still says something plain ('not published yet'), never blank / undefined / NaN",
          'class="mn-line r"' in o["lnStop"] and "Bot stopped" in o["lnStop"] and "not published yet" in ltxt(o["lnNone"]) and not re.search(r"undefined|NaN|null", o["lnNone"] + o["lnStop"]), (ltxt(o["lnStop"]), ltxt(o["lnNone"])))
    check("b. status strip: text from the board never becomes markup", "<img" not in o["lnEvil"])
    # --- Today's session (SessionDay): the modes follow the ET clock, the sentence and the countdown follow the mode
    sd = o["sd"]
    want = {"early": "before", "plan": "plan", "open": "open", "late": "late", "flat": "flat", "over": "over", "friover": "over", "sat": "weekend", "sun": "weekend", "holiday": "open", "eveholiday": "over"}
    check(f"b. session card: the mode follows the New York clock for {len(want)} moments (before / plan / open / late / flat / over / weekend)", all(sd[k]["mode"] == v for k, v in want.items()), {k: sd[k]["mode"] for k in want})
    st = lambda k: ",".join(sd[k]["states"])
    check("b. session card: the four windows (game plan, entry window, flat, recap) go next -> now -> done through the day; over a weekend only the first is 'next'",
          sd["early"]["keys"] == ["plan", "window", "flat", "recap"] and st("early") == "next,later,later,later" and st("plan") == "now,next,later,later" and st("open") == "done,now,next,later"
          and st("late") == "done,done,next,later" and st("flat") == "done,done,now,next" and st("over") == "done,done,done,now" and st("sat") == "next,later,later,later", {k: st(k) for k in sd})
    check("b. session card: the times are real ET on both sides of the clock change (01:45, 02:00 -> 15:30 = 13.5 h, 15:55) in March and November",
          all(sd[k]["tEnd"][1] - sd[k]["t"][1] == 13.5 * 3600 and sd[k]["t"][1] - sd[k]["t"][0] == 15 * 60 and sd[k]["t"][2] - sd[k]["t"][1] == 13.5 * 3600 + 25 * 60 for k in ("dstbefore", "dstafter", "open"))
          and sd["open"]["t"][1] == et(2026, 11, 4, 2, 0) and sd["dstafter"]["t"][1] == et(2026, 3, 10, 2, 0) and sd["dstbefore"]["t"][1] == et(2026, 3, 6, 2, 0), (sd["open"]["t"], sd["dstafter"]["t"]))
    L = lambda k: sd[k]["left"]
    check("b. session card: exact time left: to the 01:45 plan (15 min), to the window opening (10 min), to the 15:30 close (5.5 h), to the flat time (15 min), to the next game plan once over, Monday over a weekend",
          L("early")["left"] == 900 and L("early")["kind"] == "plan" and L("plan")["left"] == 600 and L("plan")["kind"] == "window" and L("open")["left"] == 5.5 * 3600 and L("open")["kind"] == "closes"
          and L("late")["left"] == 900 and L("late")["kind"] == "flat" and L("flat")["left"] == 300 and L("over")["left"] == et(2026, 11, 5, 1, 45) - SDT["over"] and L("friover")["left"] == et(2026, 11, 9, 1, 45) - SDT["friover"]
          and L("sat")["left"] == et(2026, 11, 9, 1, 45) - SDT["sat"] and L("sun")["left"] == et(2026, 11, 9, 1, 45) - SDT["sun"] and all(L(k)["left"] > 0 for k in sd), {k: L(k) for k in ("over", "friover", "sat")})
    one = lambda t: bool(t) and t.endswith(".") and t.count(". ") == 0 and len(t) < 170
    check("b. session card: ONE sentence for what to do now in every moment, with and without a board ('Nothing: ...' while the bot just works)",
          all(one(sd[k]["todo"]) for k in sd) and all(one(o["sdNoBoard"][k]["todo"]) for k in sd) and o["sdNoBoard"]["over"]["todo"] == "You are flat, session over, review in Mnemosyne." and "still open" in sd["over"]["todo"]
          and "closed" in sd["sat"]["todo"] and "01:45" in sd["sat"]["todo"] and o["sdNoBoard"]["open"]["todo"] == "Nothing: the bot is waiting for a sweep (bot state: not published yet).", ([sd[k]["todo"] for k in sd], o["sdNoBoard"]["open"]["todo"]))
    check("b. session card: the PC bot stopped = 'Check the PC' sentence; a blocked bot = 'do not trade by hand' with the reason as plain text",
          o["sdStop"].startswith("Check the PC") and "stopped" in o["sdStop"] and o["sdBlocked"].startswith("Nothing: the bot is blocked") and "do not trade by hand" in o["sdBlocked"], (o["sdStop"], o["sdBlocked"]))
    hh = o["sdHtml"]
    exp_news = [n for n in SDN if n["impact"] in ("high", "fomc") and n["t"] > SDT["open"] - 600 and et(2026, 11, 4, 0, 0) <= n["t"] <= et(2026, 11, 4, 17, 0)]
    check(f"b. session card: news flags from the calendar the page carries ({len(exp_news)} of {len(SDN)} entries qualify: high-impact, today, not past), marked inside the entry window, escaped",
          len(o["sdNews"]) == len(exp_news) and hh.count('class="sd-flag a"') == len(exp_news) and "inside the entry window" in hh and "<img" not in hh and "&lt;img" in hh, (len(o["sdNews"]), len(exp_news)))
    check("b. session card: never blank - no calendar says 'not published yet', an empty calendar says 'No big US news left today', every card has the 4 window rows, the one-sentence box and a countdown",
          "News calendar: not published yet" in o["sdHtmlNone"] and "No big US news left today" in o["sdHtmlNoNews"] and all(h.count('class="sd-row') == 4 and "What to do now" in h and "data-sd-cd=" in h for h in (hh, o["sdHtmlNone"], o["sdHtmlNoNews"]))
          and not re.search(r"undefined|NaN|null", hh + o["sdHtmlNone"] + o["sdHtmlNoNews"]), re.sub(r"<[^>]+>", " ", o["sdHtmlNone"])[:300])
    hol = o["sdHol"]
    check("b. session card: US/CME holidays from rules (Thanksgiving = 4th Thursday, Good Friday from Easter): flagged on the day and the evening before; never on a weekend",
          sd["holiday"]["holiday"] and sd["holiday"]["holiday"]["name"] == "Thanksgiving" and sd["eveholiday"]["holiday"] and sd["eveholiday"]["holiday"]["name"] == "Thanksgiving" and "Thanksgiving" in o["sdHtmlHol"]
          and hol[0]["2026-04-03"] == "Good Friday" and hol[1]["2027-03-26"] == "Good Friday" and hol[0]["2026-11-26"] == "Thanksgiving" and hol[1]["2027-11-25"] == "Thanksgiving"
          and all(date.fromisoformat(k).weekday() < 5 for h in hol for k in h) and sd["open"]["holiday"] is None, hol[0])


# ------------------------------------------------------------------------------------------------ c. phone
ROUTES = [("Home", "#/today"), ("Zlarior", "#/lit"), ("Zlarior Brain", "#/brain"), ("Zlarior Trades", "#/trades"), ("Zlarior Results", "#/perf"), ("Zlarior Rules", "#/strategy"),
          ("ATLAS", "#/atlas"), ("ATLAS Brain", "#/atlas/brain"), ("ATLAS Trades", "#/atlas/trades"), ("ATLAS Results", "#/atlas/results"), ("ATLAS Rules", "#/atlas/setups"),
          ("BLITZ", "#/blitz"), ("BLITZ Brain", "#/blitz/brain"), ("BLITZ Trades", "#/blitz/trades"), ("BLITZ Results", "#/blitz/results"), ("BLITZ Rules", "#/blitz/rules"),
          ("BLITZ Go live", "#/blitz/golive"), ("Money", "#/real"), ("Accounts today", "#/realtoday"), ("More", "#/system"), ("Money plan (More)", "#/money"),
          ("Mission Control", "#/mission"), ("Settings", "#/settings")]


def part_c(F, tmp, shots):
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        print("[SKIP] c. phone Playwright: playwright not installed")
        return
    from tests import test_blitz_tab as TB
    s = TB.site(tmp, F)
    lvp = os.path.join(tmp, "liveview.json")
    json.dump(F["lv"], open(lvp, "w"), default=str)
    srv = TB.serve(s)
    base = f"http://127.0.0.1:{srv.server_address[1]}/"
    lj = json.dumps(TB.live_json(F, "off"), default=str)
    sh = (lambda pg, n: pg.screenshot(path=os.path.join(shots, n))) if shots else (lambda *a: None)

    def page(br, errs, w=390, h=844, motion="no-preference", init=""):
        ctx = br.new_context(viewport={"width": w, "height": h}, device_scale_factor=2, is_mobile=True, has_touch=True, reduced_motion=motion, timezone_id="America/New_York")
        ctx.add_init_script("try { localStorage.setItem('oly.hiddenBots', '[]'); } catch (e) {}")   # BLITZ shown for these pinned checks (hidden by default since 2026-11-15: tests.test_hidden_bots / test_blitz_tab)
        ctx.clock.install(time=F["T"])
        if init:
            ctx.add_init_script(init)
        pg = ctx.new_page()
        pg.on("pageerror", lambda e: errs.append(f"pageerror: {str(e)[:240]}"))
        for host in ("**/api.github.com/**", "**/raw.githubusercontent.com/**"):
            pg.route(host, lambda r: r.fulfill(path=lvp, content_type="application/json") if "liveview.json" in r.request.url
                     else r.fulfill(status=200, body=lj, content_type="application/json") if "/live.json" in r.request.url else r.fulfill(status=404, body="{}"))
        return ctx, pg

    no_x = lambda pg: pg.evaluate("() => document.documentElement.scrollWidth - innerWidth")
    with sync_playwright() as p:
        br = BK.launch(p)
        errs = []
        ctx, pg = page(br, errs)
        pg.goto(base + "?fxoff#/today")
        pg.wait_for_selector(".pl-home .su-bar", timeout=30000)
        pg.wait_for_function("() => window.LIVE && window.LIVE.j", timeout=30000)
        pg.wait_for_timeout(1200)
        if pg.query_selector("#moInstX"):
            pg.click("#moInstX")
            pg.wait_for_timeout(300)
        H = pg.evaluate("() => { const h = document.querySelector('#page > .pl-home'); return { kids: [...h.children].map(c => c.className.split(' ')[0]), accts: [...h.querySelectorAll('.su-acct')].map(a => a.dataset.bot), height: document.documentElement.scrollHeight }; }")
        check("c. Home: the greeting, status bar, the three account cards (Zlarior · ATLAS · BLITZ), what matters now, quick tiles", H["kids"][:4] == ["pl-hi", "su-bar", "su-accts", "pl-now"] and "pl-quick" in H["kids"]
              and H["accts"] == ["lit", "atlas", "blitz"], H)
        MNP = pg.evaluate("""() => { const c = document.querySelector('.pl-home > .pl-hi > #mnCard'); if (!c) return null; const rows = [...c.querySelectorAll('.mn-row')];
          return { n: rows.length, top: Math.round(c.getBoundingClientRect().top), after: [...c.parentNode.children].indexOf(c), kids: [...c.parentNode.children].slice(0, 4).map(e => e.id || e.className.split(' ')[0]),
            taps: rows.map(r => Math.round(r.getBoundingClientRect().height)), w: rows.map(r => Math.round(r.getBoundingClientRect().width)), keys: rows.map(r => r.dataset.mn), txt: c.innerText.replace(/\\s+/g, ' '),
            edge: c.className, x: document.documentElement.scrollWidth - innerWidth }; }""")
        exp = pg.evaluate("() => Math.max(2, window.MissionUI.accounts(window.POLISH.model()).filter((a) => a && !a.placeholder).length)")      # the accounts the board really has
        check(f"c. Money now: the top card of Home, inside the greeting box right after the date line ({MNP and MNP['n']} rows), the Home order kept, no sideways scroll",
              MNP and MNP["after"] == 2 and MNP["kids"][2] == "mnCard" and MNP["n"] >= 2 and MNP["x"] <= 1 and H["kids"][:4] == ["pl-hi", "su-bar", "su-accts", "pl-now"], MNP)
        check("c. Money now: one row per account the board has (Zlarior, ATLAS, BLITZ when it exists), every row is a 44 px tap, 'Drawdown left $... of $... max loss' and a status word, no 'X of 10 days'",
              MNP and MNP["keys"][:2] == ["lit", "atlas"] and MNP["n"] == exp and all(h >= 44 for h in MNP["taps"]) and all(w >= 300 for w in MNP["w"])
              and MNP["txt"].count("Drawdown left") == MNP["n"] and MNP["txt"].count("max loss") >= MNP["n"] and "10 days" not in MNP["txt"] and "next" in MNP["txt"].lower() and "Bot " in MNP["txt"] and "NaN" not in MNP["txt"], MNP)
        pg.click("#mnCard .mn-row[data-mn='atlas']")
        pg.wait_for_timeout(700)
        check("c. Money now: tapping a row opens that bot (ATLAS)", pg.evaluate("() => location.hash") == "#/atlas", pg.evaluate("() => location.hash"))
        pg.evaluate("() => { location.hash = '#/today'; }")
        pg.wait_for_selector(".pl-home > .pl-hi > #mnCard", timeout=20000)
        pg.wait_for_selector(".pl-home > .pl-hi > #sdCard", timeout=20000)
        SDP = pg.evaluate("""() => { const c = document.querySelector('.pl-home > .pl-hi > #sdCard'); if (!c) return null; const rows = [...c.querySelectorAll('.sd-row')], fl = [...c.querySelectorAll('.sd-flag')];
          const cd = c.querySelector('[data-sd-cd]'); return { rows: rows.length, flags: fl.length, keys: rows.map(r => r.dataset.sd), prev: c.previousElementSibling && c.previousElementSibling.id, kids: [...c.parentNode.children].slice(0, 5).map(e => e.id || e.className.split(' ')[0]),
            taps: rows.concat(fl).map(r => Math.round(r.getBoundingClientRect().height)), txt: c.innerText.replace(/\\s+/g, ' '), cd: cd ? cd.textContent : null, x: document.documentElement.scrollWidth - innerWidth, h: Math.round(c.getBoundingClientRect().height),
            todo: c.querySelector('.sd-todo') ? c.querySelector('.sd-todo').textContent : '', edge: c.className }; }""")
        check(f"c. Today's session: a card right under Money now ({SDP and SDP['rows']} windows + {SDP and SDP['flags']} flag rows, {SDP and SDP['h']} px), the Home order kept, every row a 44 px tap, no sideways scroll",
              SDP and SDP["prev"] == "mnCard" and SDP["kids"][2:4] == ["mnCard", "sdCard"] and SDP["rows"] == 4 and SDP["keys"] == ["plan", "window", "flat", "recap"] and SDP["flags"] >= 1
              and all(h >= 44 for h in SDP["taps"]) and SDP["x"] <= 1, SDP)
        check("c. Today's session: 'Bot now', 'What to do now' as one sentence, the next window with a ticking H:MM:SS countdown, times in ET, never 'undefined' / 'NaN'",
              SDP and "what to do now" in SDP["txt"].lower() and "bot now" in SDP["txt"].lower() and re.fullmatch(r"\d+:\d\d:\d\d", SDP["cd"] or "") and "ET" in SDP["txt"] and SDP["todo"].endswith(".")
              and not re.search(r"undefined|NaN|null", SDP["txt"]), SDP)
        cd0 = pg.evaluate("() => document.querySelector('#sdCard [data-sd-cd]').textContent")
        pg.wait_for_timeout(2400)
        cd1 = pg.evaluate("() => document.querySelector('#sdCard [data-sd-cd]').textContent")
        sec = lambda v: sum(int(x) * m for x, m in zip(v.split(":"), (3600, 60, 1)))
        check("c. Today's session: the countdown ticks down every second", sec(cd1) < sec(cd0), (cd0, cd1))
        pg.click("#sdCard .sd-row[data-sd='window']")
        pg.wait_for_timeout(700)
        check("c. Today's session: tapping the entry window opens Zlarior", pg.evaluate("() => location.hash") == "#/lit", pg.evaluate("() => location.hash"))
        pg.evaluate("() => { location.hash = '#/today'; }")
        pg.wait_for_selector(".pl-home > .pl-hi > #sdCard", timeout=20000)
        sh(pg, "session_card_phone.png")
        sh(pg, "money_now_phone.png")
        PERF["home_height_px"] = H["height"]
        check("c. Home is short and calm (under 3,500 px at 390 wide with everything else folded; the Money now card is about 330 px and Today's session about 500 px of it)", H["height"] < 3500, H["height"])
        wk = pg.evaluate("() => { const w = document.querySelector('.pl-home .su-week'); return w ? [...w.querySelectorAll('li > b')].map(b => b.textContent) : null; }")
        prog = (F["board"].get("progress") or {})
        check("c. Home: this week's real trades vs each bot's goal (Mon-Fri dots), when the board has its progress", (wk is None and not prog) or (wk and "Zlarior" in wk), (wk, list(prog)))
        hid = pg.evaluate("() => [...document.querySelectorAll('#page > .mc-strip, #page > .rc-homebox, #page > .bz-home, #page > .cl-list')].map(e => [e.className.split(' ')[0], e.offsetParent === null])")
        check("c. Home: every older card is still there, folded (Mission strip, real accounts, deck + Mind, one tap away)", len(hid) >= 3 and all(x[1] for x in hid), hid)
        pg.click("[data-su-toggle]")
        pg.wait_for_timeout(450)
        op = pg.evaluate("() => { const b = document.querySelector('.su-bar'); return { open: b.classList.contains('open'), h: b.querySelector('.su-list').getBoundingClientRect().height, rows: b.querySelectorAll('.su-list > li').length }; }")
        check("c. the status bar opens every line (PC bot, NinjaTrader, feed, each bot, alerts)", op["open"] and op["h"] > 100 and op["rows"] >= 6, op)
        sh(pg, "polish_phone_status_open.png")
        pg.click("[data-su-toggle]")
        pg.click("#page > .pl-fold")
        pg.wait_for_timeout(400)
        shown = pg.evaluate("() => [...document.querySelectorAll('#page > .mc-strip, #page > .bz-home')].every(e => e.offsetParent !== null)")
        check("c. 'Everything else on Home' shows the older cards in one tap (remembered)", shown and pg.evaluate("() => localStorage.getItem('le.pl.homeAll')") == "true")
        pg.click("#page > .pl-fold")
        pg.wait_for_timeout(300)
        sh(pg, "polish_phone_home.png")
        mk = pg.evaluate("() => { const m = document.querySelector('.pl-home .su-mkt'); return m ? m.innerText.replace(/\\s+/g, ' ').slice(0, 120) : null; }")
        check("c. Home: NQ now with the nearest levels (when the board has a price)", mk is None or "NQ" in mk, mk)
        # keyboard: an account card is a tab stop and Enter opens its bot
        pg.focus(".pl-home .su-acct[data-bot='atlas']")
        pg.keyboard.press("Enter")
        pg.wait_for_timeout(600)
        check("c. keyboard: the account cards are tab stops, Enter opens the bot (ATLAS)", pg.evaluate("() => location.hash") == "#/atlas", pg.evaluate("() => location.hash"))
        pg.evaluate("() => { location.hash = '#/today'; }")
        pg.wait_for_timeout(600)
        # every tab and section
        bad = []
        for name, h in ROUTES:
            pg.evaluate(f"() => {{ location.hash = '{h}'; }}")
            pg.wait_for_timeout(900)
            st = pg.evaluate("() => ({ x: document.documentElement.scrollWidth - innerWidth, n: document.querySelector('#page').children.length, t: (document.querySelector('#page').innerText || '').length, err: /Could not draw this page/.test(document.querySelector('#page').innerText) })")
            if st["x"] > 1 or st["n"] < 1 or st["t"] < 40 or st["err"]:
                bad.append((name, st))
        check(f"c. all {len(ROUTES)} tab / section pages render, no 'could not draw', no sideways scroll at 390 px", not bad, bad)
        pg.evaluate("() => { location.hash = '#/deck'; }")
        pg.wait_for_timeout(2400)
        nt = pg.evaluate("() => document.querySelectorAll('#page > .pl-toc button').length")
        if nt >= 3:
            pg.click("#page > .pl-toc button:nth-child(3)")
            pg.wait_for_timeout(900)
        sy = pg.evaluate("() => scrollY")
        check("c. long pages: 'On this page' chips (Trader's deck), a tap scrolls to that card", nt >= 5 and sy > 200, (nt, sy))
        pg.evaluate("() => scrollTo(0, 0)")
        segs = {}
        for k, h in (("lit", "#/lit"), ("atlas", "#/atlas"), ("blitz", "#/blitz")):
            pg.evaluate(f"() => {{ location.hash = '{h}'; }}")
            pg.wait_for_timeout(700)
            segs[k] = pg.eval_on_selector_all("#sub .zl-seg button", "els => els.map(e => e.textContent.trim())")
        check("c. Zlarior, ATLAS and BLITZ: the same five sections in the same order", all(v == ["Today", "Brain", "Trades", "Results", "Rules"] for v in segs.values()), segs)
        ind = pg.evaluate("() => { const i = document.querySelector('#tabs > .pl-tabind'), a = document.querySelector('#tabs a.on'); return i && a ? { t: i.dataset.t, on: a.dataset.t, w: Math.round(parseFloat(i.style.width)), aw: a.offsetWidth } : null; }")
        check("c. the bottom bar: one pill slides to the open tab, in its colour (BLITZ)", ind and ind["t"] == "blitz" == ind["on"] and abs(ind["w"] - ind["aw"]) <= 1, ind)
        td = pg.evaluate("() => [...document.querySelectorAll('#tabs a .pl-tdot')].map(d => d.parentNode.dataset.t + ':' + d.dataset.s)")
        check("c. the bottom bar: a light on a bot's tab while it is in a trade (Zlarior)", "lit:trade" in td, td)
        col = pg.evaluate("() => getComputedStyle(document.documentElement).getPropertyValue('--bot').trim()")
        top = pg.query_selector("#page > .pl-bot .su-acct[data-bot='blitz']")
        check("c. a bot tab opens on its account card, in the bot's colour (BLITZ purple)", top is not None and col.lower() in ("#b388ff", "var(--bz)") , col)
        pg.click("#tabs a[data-t='money']")
        pg.wait_for_timeout(900)
        mo = pg.evaluate("() => ({ hash: location.hash, chips: [...document.querySelectorAll('#sub .strip button')].map(b => b.dataset.go) })")
        check("c. Money tab opens Real results; its pages are real money only (Real results · Accounts today · Eval timeline)", mo["hash"] == "#/real" and mo["chips"][:2] == ["real", "realtoday"]
              and not any(c in mo["chips"] for c in ("money", "props", "whatif", "scale")), mo)
        pg.evaluate("() => { location.hash = '#/system'; }")
        pg.wait_for_timeout(700)
        sec = pg.eval_on_selector_all(".cl-sec h4", "els => els.filter(e => e.offsetParent !== null).map(e => e.firstChild.textContent.trim())")
        check("c. More: grouped (Today · Insight · Bot and health · Trades · Money planning · This app · Advanced)", sec[:6] == ["Today", "Insight", "Bot and health", "Trades", "Money planning", "This app"] and "Advanced" in sec, sec)
        # the palette
        pg.click("#plFind")
        pg.wait_for_selector("#plPal.on #plQ", timeout=5000)
        pg.fill("#plQ", "atlas trades")
        pg.wait_for_timeout(250)
        first = pg.eval_on_selector("#plL li.on b", "e => e.textContent")
        sh(pg, "polish_phone_palette.png")
        pg.keyboard.press("Enter")
        pg.wait_for_timeout(700)
        check("c. the search palette: 'atlas trades' -> ATLAS · Trades, Enter opens it", "ATLAS" in first and "Trades" in first and pg.evaluate("() => location.hash") == "#/atlas/trades"
              and not pg.query_selector("#plPal.on"), (first, pg.evaluate("() => location.hash")))
        pg.keyboard.press("/")
        pg.wait_for_selector("#plPal.on", timeout=3000)
        pg.keyboard.press("Escape")
        pg.wait_for_timeout(300)
        check("c. the palette: '/' opens it, Escape closes it", not pg.query_selector("#plPal.on"))
        # the header status dot on every page: its verdict, a tap opens the status bar on Home
        dot = pg.evaluate("() => { const b = document.getElementById('plStat'); return b ? b.className : null; }")
        pg.click("#plStat")
        pg.wait_for_timeout(900)
        opened = pg.evaluate("() => location.hash === '#/today' && !!document.querySelector('.pl-home .su-bar.open')")
        check("c. the header status dot (green / amber / red) on every page; a tap opens the status bar on Home", dot and re.search(r"\b(good|warn|bad)\b", dot) and opened, (dot, opened))
        pg.click("[data-su-toggle]")
        # frame time while scrolling Home (the UI itself; the 3D scene is measured by tests.test_space_ui)
        pg.evaluate("() => { location.hash = '#/today'; }")
        pg.wait_for_timeout(1200)
        fr = pg.evaluate("""() => new Promise((res) => { const d = []; let last = performance.now(), n = 0; const H = document.documentElement.scrollHeight - innerHeight;
          function f(t) { d.push(t - last); last = t; n++; scrollTo(0, (Math.sin(n / 18) * 0.5 + 0.5) * H); if (n < 150) requestAnimationFrame(f); else { d.shift(); d.sort((a, b) => a - b); res({ n: d.length, p50: d[d.length >> 1], p95: d[Math.floor(d.length * 0.95)] }); } }
          requestAnimationFrame(f); })""")
        PERF["phone_scroll_frame_ms"] = fr
        check("c. frame time while scrolling Home: median <= 20 ms, p95 <= 50 ms (headless, software GPU)", fr["p50"] <= BK.limit_ms(20, "scroll p50") and fr["p95"] <= BK.limit_ms(50, "scroll p95"), fr)
        # layout shift of a fresh open of Home (the first 4 s: home.json, data.json, live.json and the late cards landing);
        # the scroll above scrolls the page, which is no shift. The scrolled position is reset first.
        pg.evaluate("() => scrollTo(0, 0)")
        ctx.add_init_script("""window.__ls = []; try { new PerformanceObserver((l) => { for (const e of l.getEntries()) if (!e.hadRecentInput)
          window.__ls.push([+e.value.toFixed(4), Math.round(e.startTime), (e.sources || []).map((x) => x.node ? (x.node.id || String(x.node.className || x.node.nodeName).split(' ')[0]) : '?').join(',')]); }).observe({ type: 'layout-shift', buffered: true }); } catch (e) {}""")
        pg.reload()                          # a new document (a goto to the same URL + hash would stay in the page)
        pg.wait_for_selector(".pl-home .su-acct", timeout=30000)
        pg.wait_for_timeout(4000)
        cls_ = pg.evaluate("""() => new Promise((res) => { let s = 0; try { new PerformanceObserver((l) => { for (const e of l.getEntries()) if (!e.hadRecentInput) s += e.value; }).observe({ type: 'layout-shift', buffered: true }); } catch (e) {} setTimeout(() => res(s), 600); })""")
        PERF["phone_layout_shift"] = round(cls_, 4)
        PERF["phone_layout_shift_top"] = sorted(pg.evaluate("() => window.__ls || []"), key=lambda x: -x[0])[:4]
        check("c. no layout shift to speak of on a fresh open of Home (CLS < 0.1)", cls_ < 0.1, cls_)
        check("c. phone: no page errors", not errs, errs[:4])
        ctx.close()
        # the intro: once a day, skippable (a real phone, not an automated browser)
        e2 = []
        real = "Object.defineProperty(Navigator.prototype, 'webdriver', { get: () => false });"
        ctx, pg = page(br, e2, init=real)
        t0 = time.time()
        pg.route("**/fonts.g*/**", lambda r: r.abort())       # no web fonts here: the page loads at once, like the installed app
        pg.goto(base + "#/today", wait_until="commit")
        pg.wait_for_selector("#splash #spSkip", timeout=10000)
        vis = pg.is_visible("#splash")
        sh(pg, "polish_phone_intro.png")
        tk = time.time()
        fading = pg.evaluate("() => { const b = document.getElementById('spSkip'); if (b) b.click(); const s = document.getElementById('splash'); return !s || s.classList.contains('out'); }")      # a tap on Skip: it starts to fade in the same frame
        pg.wait_for_function("() => !document.getElementById('splash')", timeout=10000)   # it fades at once; the removal timer can wait on a busy first load here
        gone_s = round(time.time() - tk, 2)
        PERF["intro_skip_s"] = gone_s
        pg.reload()
        pg.wait_for_selector(".pl-home", timeout=30000)
        again = pg.query_selector("#splash") is not None
        check("c. the intro: shows on the first open of the day, Skip removes it at once, not again the same day", vis and fading and not again and not e2, (vis, fading, again, gone_s, e2[:2]))
        ctx.close()
        # Settings > Intro off: no intro even on a new day
        e5 = []
        ctx, pg = page(br, e5, init=real + "try { localStorage.setItem('le.intro', 'false'); } catch (e) {}")
        pg.goto(base + "#/settings")
        pg.wait_for_selector("#plIntro", timeout=30000)
        off = pg.evaluate("() => ({ intro: !!document.getElementById('splash'), box: document.getElementById('plIntro').checked })")
        check("c. Settings > Intro: the switch is there; off = no intro", not off["intro"] and off["box"] is False and not e5, (off, e5[:2]))
        ctx.close()
        # reduced motion: no intro, no animation on the new parts
        e3 = []
        ctx, pg = page(br, e3, motion="reduce", init=real)
        pg.goto(base + "#/today")
        pg.wait_for_selector(".pl-home .su-acct", timeout=30000)
        pg.wait_for_timeout(800)
        rm = pg.evaluate("() => ({ intro: !!document.getElementById('splash'), anims: [...document.querySelectorAll('#page, #page .pl-home, #page .pl-home *')].reduce((n, e) => n + e.getAnimations().length, 0) })")
        check("c. reduced motion: no intro, no animation on the page or its new cards", not rm["intro"] and rm["anims"] == 0 and not e3, (rm, e3[:2]))
        ctx.close()
        # the light theme, sideways
        e4 = []
        ctx, pg = page(br, e4, 844, 390, init="try { localStorage.setItem('le.theme', JSON.stringify('light')); } catch (e) {}")
        pg.goto(base + "?fxoff#/today")
        pg.wait_for_selector(".pl-home .su-acct", timeout=30000)
        pg.wait_for_timeout(600)
        ink = pg.evaluate("() => getComputedStyle(document.querySelector('.su-sum b')).color")
        check("c. light theme, sideways 844x390: dark ink on light glass, no sideways scroll, no errors", sum(int(x) for x in re.findall(r"\d+", ink)[:3]) < 300 and no_x(pg) <= 1 and not e4, (ink, no_x(pg), e4[:2]))
        sh(pg, "polish_phone_light_landscape.png")
        ctx.close()
        br.close()
    srv.shutdown()


# ------------------------------------------------------------------------------------------------ d. PC
def part_d(F, shots):
    try:
        from playwright.sync_api import sync_playwright
        import uvicorn  # noqa: F401
    except Exception:
        print("[SKIP] d. PC Playwright: playwright / uvicorn not installed")
        return
    import copy
    import socket
    import threading
    from tests.shots_board import free_port, snapshot_files, restore_files
    from tests import test_blitz_tab as TB
    import atexit
    snap = snapshot_files()
    atexit.register(restore_files, snap)
    for k, v in (("LE_NO_AUTOSTART", "1"), ("LE_HEARTBEAT", "0"), ("LE_LIVE_PUBLISH", "0"), ("LE_EXEC_AUDIT", "0")):
        os.environ[k] = v
    import uvicorn
    import server
    from engine import hidden_bots as _hbz   # BLITZ shown for these pinned checks (hidden by default since 2026-11-15)
    _hbz.FORCE = ()
    from engine import board_api
    board_api.board_view = lambda bot, now=None: copy.deepcopy(F["board"])
    port = free_port()
    srv = uvicorn.Server(uvicorn.Config(server.app, host="127.0.0.1", port=port, log_level="warning"))
    threading.Thread(target=srv.run, daemon=True).start()
    for _ in range(300):
        try:
            socket.create_connection(("127.0.0.1", port), timeout=0.2).close()
            break
        except OSError:
            time.sleep(0.1)
    base = f"http://127.0.0.1:{port}"
    with sync_playwright() as p:
        br = BK.launch(p)
        ctx = br.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
        ctx.add_init_script("try { localStorage.setItem('oly.hiddenBots', '[]'); } catch (e) {}")   # BLITZ shown for these pinned checks (hidden by default since 2026-11-15: tests.test_hidden_bots / test_blitz_tab)
        ctx.clock.install(time=F["T"])
        pg = ctx.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(f"pc pageerror: {str(e)[:240]}"))
        pg.add_init_script("localStorage.setItem('page', 'cc'); localStorage.setItem('oly.hiddenBots', '[]');")
        pg.goto(base + "/?fxoff", wait_until="domcontentloaded")
        pg.wait_for_function("() => window.LE && window.LE.go", timeout=60000)
        ok = False
        for _ in range(3):
            TB.pc_go(pg, "cc")
            try:
                pg.wait_for_selector("#page-cc.active > #nxStatusHome .su-bar", timeout=30000)
                ok = True
                break
            except Exception:
                pass
        pg.wait_for_selector("#nxStatusHome #mnCard", timeout=30000)
        MND = pg.evaluate("""() => { const c = document.querySelector('#nxStatusHome > #mnCard'); if (!c) return null; const rows = [...c.querySelectorAll('.mn-row')];
          return { n: rows.length, first: document.querySelector('#nxStatusHome').firstElementChild.id, keys: rows.map(r => r.dataset.mn), goto: rows.map(r => r.getAttribute('data-goto')), taps: rows.map(r => Math.round(r.getBoundingClientRect().height)),
            txt: c.innerText.replace(/\\s+/g, ' '), x: document.documentElement.scrollWidth - innerWidth, bar: !!document.querySelector('#nxStatusHome .su-bar') }; }""")
        check(f"d. PC Home: the Money now card is the first thing in the status box ({MND and MND['n']} rows), the status bar right below it, 'Drawdown left $.. of $.. max loss' per account, rows link to the bots",
              MND and MND["first"] == "mnCard" and MND["bar"] and MND["keys"][:2] == ["lit", "atlas"] and MND["goto"][:2] == ["zlarior", "atlas"] and all(h >= 44 for h in MND["taps"])
              and MND["txt"].count("Drawdown left") == MND["n"] and "max loss" in MND["txt"] and "10 days" not in MND["txt"] and "next" in MND["txt"].lower() and MND["x"] <= 1, MND)
        # --- the one-line sticky status strip on EVERY page (dynamic: the first pages of the sidebar, then a long one scrolled)
        pages = pg.eval_on_selector_all("#nav a[data-page]", "els => els.map(e => e.dataset.page)")
        pages = [x for x in dict.fromkeys(["cc"] + pages) if pg.evaluate("(id) => !!document.getElementById('page-' + id)", x)][:8]
        bad = []
        for pid in pages:
            TB.pc_go(pg, pid)
            pg.wait_for_timeout(700)
            pg.evaluate("() => window.scrollTo(0, 400)")
            pg.wait_for_timeout(200)
            L = pg.evaluate("""() => { const w = document.getElementById('nxLine'); if (!w) return null; const a = w.querySelector('a.mn-line'); const r = (a || w).getBoundingClientRect();
              return { n: document.querySelectorAll('#nxLine').length, after: w.previousElementSibling && w.previousElementSibling.className, pos: getComputedStyle(w).position, h: Math.round(r.height), top: Math.round(w.getBoundingClientRect().top),
                scroll: document.documentElement.scrollHeight > innerHeight + 500, txt: w.innerText.replace(/\\s+/g, ' '), goto: a && a.getAttribute('data-goto'), x: document.documentElement.scrollWidth - innerWidth }; }""")
            if not (L and L["n"] == 1 and "topbar" in (L["after"] or "") and L["pos"] == "sticky" and L["h"] >= 44 and L["goto"] == "cc" and "bot" in L["txt"].lower() and "undefined" not in L["txt"] and L["x"] <= 1
                    and (not L["scroll"] or 0 <= L["top"] <= 4)):
                bad.append((pid, L))
        check(f"d. PC status strip: on all {len(pages)} pages checked ({', '.join(pages[:4])} ...) exactly one sticky line under the top bar with 'Bot ...' + Armed, 44 px or taller, stays at the top when scrolled, links Home", pages and not bad, bad[:2])
        TB.pc_go(pg, "cc")
        pg.wait_for_selector("#page-cc.active > #nxStatusHome .su-bar", timeout=30000)
        pg.evaluate("() => window.scrollTo(0, 0)")
        check("d. PC Home: the status bar on top", ok and pg.evaluate("() => document.querySelector('#page-cc').firstElementChild.id") == "nxStatusHome")
        subs = pg.eval_on_selector_all("#nav .nx-main-sub", "els => els.map(e => e.textContent.trim())")
        side = pg.eval_on_selector_all("#nav > a.nx-gl[data-g='Main']", "els => els.map(e => e.dataset.page)")
        check("d. PC sidebar: Bots · Live · Money · Insight headings, each page once, BLITZ right after ATLAS", subs == ["Bots", "Live", "Money", "Insight"] and len(side) == len(set(side))
              and side.index("blitz") == side.index("atlas") + 1, (subs, side))
        nd = pg.evaluate("() => [...document.querySelectorAll('#nav a .nx-bdot')].map(d => d.parentNode.dataset.page + ':' + d.dataset.s)")
        check("d. PC sidebar: a light next to a bot while it is in a trade (Zlarior)", "zlarior:trade" in nd, nd)
        if shots:
            pg.screenshot(path=os.path.join(shots, "polish_pc_home_1440.png"))
        seg = []
        for _ in range(3):                   # the PC app may open Start by itself on its first health ping: go again
            TB.pc_go(pg, "blitz")
            pg.wait_for_timeout(1500)
            seg = pg.eval_on_selector_all("#nxSub .nx-botseg button", "els => els.map(e => e.textContent.trim())")
            if seg:
                break
        check("d. PC BLITZ: Today · Brain · Trades · Results · Rules", seg == ["Today", "Brain", "Trades", "Results", "Rules"], seg)
        # Ctrl K finds each bot's sections and the status verdict
        pg.keyboard.press("Control+k")
        pg.wait_for_timeout(500)
        pg.fill("#cpInput", "atlas rules")
        pg.wait_for_timeout(400)
        first = pg.evaluate("() => (document.querySelector('#cpList .cp-it.on b') || {}).textContent || ''")
        pg.fill("#cpInput", "status")
        pg.wait_for_timeout(400)
        st = pg.evaluate("() => [...document.querySelectorAll('#cpList .cp-it b')].map(b => b.textContent).join(' | ')")
        pg.keyboard.press("Escape")
        check("d. PC Ctrl K: 'atlas rules' -> ATLAS · Rules; 'status' -> the status verdict", "ATLAS · Rules" in first and "Status:" in st, (first, st[:200]))
        check("d. PC: no page errors", not errs, errs[:4])
        br.close()
    srv.should_exit = True


def main():
    shots = ""
    if "--shots" in sys.argv:
        shots = sys.argv[sys.argv.index("--shots") + 1]
        os.makedirs(shots, exist_ok=True)
    part_a()
    tmp = tempfile.mkdtemp(prefix="le_ui_polish_")
    try:
        part_b(tmp)
        from tests import test_blitz_tab as TB
        F = TB.build()
        part_c(F, tmp, shots)
        part_d(F, shots)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    if PERF:
        print("perf:", json.dumps(PERF))
    print(f"\nUI polish: {sum(RES)}/{len(RES)} " + ("ALL PASS" if all(RES) else "FAILED"))
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
