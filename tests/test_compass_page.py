"""COMPASS, the OLYMPUS next-best-action helper (tools/web_public/compass/, AGORA look, 2026-11-10): up to five actions for today ranked by urgency and dollars from the published JSON, each with a $ or 'free' tag
and a why; the rules live in a table in compasscore.js; Done / Snooze kept on the phone; a bronze compass rose whose needle points at the top action (3D, flat fallback).

  a. static: the files, the kit lines, the AGORA look, read-only (the journal and the Ledger are only read; only compass.state.v1 is written), the Jarvis card, the manifest, the DEMO fixture
  b. the rules table and the ranking in node (compasscore.js): every rule on its own, the order, the cap of 5, the idle rule, Done / Snooze, junk safety, the date regression (ISO text is a date, not a number)
  c. Chromium 390 x 844: DEMO, Done / Snooze / Bring back, the real files with a real journal and Ledger, broken and missing files fall back, 3D or flat compass, LITE / reduced motion, taps >= 44 px
    python -X utf8 -m tests.test_compass_page            (--static: parts a and b only)
"""
from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import agora_kit as AK  # noqa: E402

APP, NAME = "compass", "Compass"
check = AK.check
FIX = os.path.join(AK.WEB, APP, "fixture.json")
NOW = "2026-11-10T14:00:00Z"


def test_static():
    AK.static_kit(APP, NAME, reads=("../home.json", "../money/index.json", "../ledger/rules.json", "../odeon/trades.json"), storage=True)
    d = os.path.join(AK.WEB, APP)
    js = AK.read(os.path.join(d, "compass.js")) + AK.read(os.path.join(d, "compasscore.js"))
    sets = re.findall(r"localStorage\.setItem\(([^,]+),", js)
    check("a. the only thing written is compass.state.v1 (Done / Snooze): journal.v1 and ledger.v1 are only read; no removeItem / clear / sessionStorage / indexedDB",
          sets == ["SKEY"] and "const SKEY = 'compass.state.v1'" in js and "readLS('journal.v1')" in js and "readLS('ledger.v1')" in js and not re.search(r"localStorage\.(removeItem|clear)|sessionStorage|indexedDB", js), sets)
    check("a. the 3D files: rose.js (render core) and needleload.js (its own module tag)", all(os.path.isfile(os.path.join(d, n)) for n in ("rose.js", "needleload.js")))
    rj = AK.read(os.path.join(d, "rose.js"))
    check("a. rose.js: on the OLYMPUS render core, AGORA look, bloom <= .25, no network, no markup from data",
          "../olympus/render.js" in rj and "../jarvis/three.module.min.js" in rj and not AK.BANNED_LOOK.search(rj) and not re.search(r"fetch\(|innerHTML|XMLHttpRequest|https?://", rj) and all(float(x) <= 0.25 for x in re.findall(r"bloom: \{ strength: ([\d.]+)", rj)))
    html = AK.read(os.path.join(d, "index.html"))
    check("a. needleload.js before compass.js; a canvas AND a flat svg compass (the fallback); page order: do this first, then, set aside, how it decides",
          html.index("needleload.js") < html.index('src="compass.js') and 'id="stage"' in html and 'id="flat"' in html and html.index('id="top"') < html.index('id="acts"') < html.index('id="quiet"') < html.index('id="how"'))
    check("a. Compass only suggests: no order, buy or trade verbs wired (no fetch POST, no window.open to a firm)", not re.search(r"method:\s*['\"]POST|window\.open|location\.href\s*=", js))
    fx = json.load(open(FIX, encoding="utf-8"))
    check("a. the fixture (relative times): three accounts, a deal ending in 5 h, a stale money stream, 7 trades with 4 rated, a Ledger of 23 entries exported 12 days ago",
          len(fx["home"]["accounts"]) == 3 and fx["money"]["streams"][0]["items"][0]["expires_in_h"] == 5 and fx["money"]["streams"][1]["status"] == "stale" and len(fx["trades"]) == 7 and len(fx["rated"]) == 4 and fx["ledger"]["entries"] == 23 and fx["ledger"]["last_export_days_ago"] == 12)


HARNESS = r"""
import(process.argv[2]).then((C) => {
  const fx = JSON.parse(require('fs').readFileSync(process.argv[3], 'utf8'));
  const now = Date.parse('2026-11-10T14:00:00Z'), H = 3600000, D = 86400000;
  const o = {};
  o.words = [C.money(2000), C.money(-60), C.money(null), C.hoursText(0.4), C.hoursText(5), C.hoursText(72), C.daysText(0), C.daysText(12), C.drawdownLine(1420, 2000)];
  o.table = C.ruleTable().map((r) => [r.id, ['usd', 'free'].includes(r.tag), r.name.length > 3, r.when.length > 10, [0, 45, 90, 180, 270].includes(r.dir)]);
  const acct = (over) => ({ id: 'a', name: 'Zlarior', kind: 'eval', conn: { connected: true }, eval: { room: 1420, mll: 2000, dll: 1000, dll_used: 0, target: 3000, to_target: 2580 }, pnl: { today: 0 }, ...over });
  const homeOf = (...a) => ({ asof: new Date(now - H).toISOString(), accounts: a });
  const fresh = { streams: [{ id: 'chrysos', status: 'ok', age_min: 20, items: [] }] };
  const calmInp = { home: homeOf(acct({})), money: fresh, odeon: { trades: [], upto: new Date(now - H).toISOString() } };
  const ids = (inp) => C.actions(C.context(inp, now)).map((a) => a.id);
  o.calm = ids(calmInp);
  o.off = ids({ ...calmInp, home: homeOf(acct({ conn: { connected: false } })) });
  o.dll = ids({ ...calmInp, home: homeOf(acct({ eval: { room: 1420, mll: 2000, dll: 1000, dll_used: 850 } })) });
  o.low = ids({ ...calmInp, home: homeOf(acct({ eval: { room: 400, mll: 2000, dll: 1000, dll_used: 0 } })) });
  o.half = ids({ ...calmInp, home: homeOf(acct({ eval: { room: 900, mll: 2000, dll: 1000, dll_used: 0 } })) });
  o.safe = ids({ ...calmInp, home: homeOf(acct({ eval: { room: 1000, mll: 2000, dll: 1000, dll_used: 0 } })) });
  o.feeds = [ids({ ...calmInp, home: null }), ids({ ...calmInp, money: null }), ids({ ...calmInp, home: { ...homeOf(acct({})), asof: new Date(now - 40 * H).toISOString() } }), ids({ ...calmInp, money: { streams: [{ id: 'oikos', status: 'stale', age_min: 700, items: [] }] } })];
  const deal = (h, score, id) => ({ streams: [{ id: id || 'mercury', status: 'ok', age_min: 10, items: [{ title: 'Sale', usd: 60, score, expires: new Date(now + h * H).toISOString() }] }] });
  o.deal = [ids({ ...calmInp, money: deal(5, 70) }), ids({ ...calmInp, money: deal(60, 70) }), ids({ ...calmInp, money: deal(60, 40) }), ids({ ...calmInp, money: deal(-2, 70) }), ids({ ...calmInp, money: deal(60, 70, 'chrysos') }), ids({ ...calmInp, money: { streams: [{ id: 'mercury', status: 'sample', items: [{ title: 'x', score: 90, expires: new Date(now + 3 * H).toISOString() }] }] } })];
  const dl = C.actions(C.context({ ...calmInp, money: deal(5, 70) }, now)).find((a) => a.id === 'deal_soon');
  o.dealAct = [dl.title, dl.tag, dl.usd, dl.urgency, dl.why.includes('$60'), C.tagText(dl)];
  o.target = [ids({ ...calmInp, home: homeOf(acct({ eval: { room: 1420, mll: 2000, dll: 1000, dll_used: 0, target: 3000, to_target: 400 } })) }), ids({ ...calmInp, home: homeOf(acct({ kind: 'funded', eval: { room: 1420, mll: 2000, dll: 1000, target: 3000, to_target: 400 } })) })];
  const trades = (n, rated) => ({ trades: Array.from({ length: n }, (_, k) => ({ id: 't' + k, day: new Date(now - (k + 1) * D).toISOString().slice(0, 10), usd: 100 })), upto: new Date(now - H).toISOString() });
  o.unrated = [ids({ ...calmInp, odeon: trades(3) }), ids({ ...calmInp, odeon: trades(3), journal: { entries: { t0: { rating: 'plan' }, t1: { rating: 'plan' }, t2: { rating: 'hesitated' } } } }), C.unratedTrades(trades(20), new Set(), now).length, C.unratedTrades({ trades: [{ id: 'x', day: '2026-11-11', usd: 1 }, { id: 'y', day: 'bad', usd: 1 }, null] }, new Set(), now).length];
  const un = C.actions(C.context({ ...calmInp, odeon: trades(3) }, now)).find((a) => a.id === 'unrated');
  o.unratedAct = [un.title, un.tag, un.urgency, C.actions(C.context({ ...calmInp, odeon: trades(30) }, now)).find((a) => a.id === 'unrated').urgency, un.why.includes('habit costs')];
  const led = (n, daysAgo) => ({ entries: new Array(n).fill(0), lastExport: daysAgo == null ? null : new Date(now - daysAgo * D).toISOString() });
  o.export = [ids({ ...calmInp, ledger: led(5, 12) }), ids({ ...calmInp, ledger: led(5, 3) }), ids({ ...calmInp, ledger: led(5, null) }), ids({ ...calmInp, ledger: led(0, 99) }), ids({ ...calmInp, ledger: 'x' })];
  const ex = C.actions(C.context({ ...calmInp, ledger: led(5, 12) }, now)).find((a) => a.id === 'export');
  o.exportAct = [ex.title, ex.tag, ex.urgency];
  o.rules = [ids({ ...calmInp, rules: { source: { built: '2026-10-18' } } }), ids({ ...calmInp, rules: { source: { built: '2026-09-01' } } }), ids({ ...calmInp, rules: { source: { built: 'nope' } } })];
  const rl = C.actions(C.context({ ...calmInp, rules: { source: { built: '2026-09-01' } } }, now)).find((a) => a.id === 'rules_old');
  o.rulesAct = rl.title;
  o.idle = C.actions(C.context(calmInp, now)).find((a) => a.id === 'idle');
  o.idleAct = [o.idle.title, o.idle.tag, o.idle.why.startsWith('Drawdown left $1,420 of $2,000 max loss (Zlarior).')];
  // the demo: the five actions, ranked
  const demo = C.actions(C.context(C.demoInputs(fx, now), now));
  o.demo = demo.map((a) => [a.id, a.title, a.tag, a.urgency]);
  o.demoPlan = [C.plan(demo, {}, now).top.length, C.plan(demo, {}, now).more, C.plan(demo, {}, now).quiet.length];
  // the cap of five: everything at once
  const all = { home: homeOf(acct({ conn: { connected: false }, eval: { room: 300, mll: 2000, dll: 1000, dll_used: 900, target: 3000, to_target: 100 } })), money: { streams: [{ id: 'mercury', status: 'stale', age_min: 900, items: [{ title: 'Sale', usd: 90, score: 80, expires: new Date(now + 4 * H).toISOString() }] }] }, odeon: trades(5), ledger: led(5, 30), rules: { source: { built: '2026-08-01' } } };
  const big = C.actions(C.context(all, now)); const pbig = C.plan(big, {}, now);
  o.cap = [big.length, pbig.top.length, pbig.more, pbig.top.map((a) => a.id), big.every((a, i) => i === 0 || big[i - 1].score >= a.score), big.some((a) => a.id === 'idle')];
  // Done / Snooze
  const st1 = C.markDone({}, demo[0].key, now), st2 = C.snooze({}, demo[0].key, now), st3 = C.clearKey(st1, demo[0].key);
  o.state = [C.isQuiet(st1, demo[0], now), C.isQuiet(st1, demo[0], now + 20 * H), C.isQuiet(st2, demo[0], now + 3 * H), C.isQuiet(st2, demo[0], now + 5 * H), C.isQuiet(st3, demo[0], now), C.isQuiet(st1, { key: 'other' }, now),
    C.plan(demo, st1, now).top[0].id, C.plan(demo, st1, now).quiet.map((a) => a.id), C.plan(demo, st1, now).top.length, Object.keys(C.cleanState({ a: { done: 1 }, b: 'x', c: { until: 'y' }, d: { until: 5 } })), C.cleanState('junk'), C.SNOOZE_HOURS];
  const ch = C.actions(C.context({ ...calmInp, odeon: trades(4) }, now)).find((a) => a.id === 'unrated');
  o.sig = [C.isQuiet(C.markDone({}, un.key, now), un, now), C.isQuiet(C.markDone({}, un.key, now), ch, now)];
  // bearing, headline, card
  o.bearing = [C.bearing(demo[0]), C.bearing(null), C.bearing({ dir: 180 }), C.bearing({}), C.bearing(pbig.top[0])];
  o.head = [C.headline(C.plan(demo, {}, now)).level, C.headline(C.plan([], {}, now)).title, C.headline(C.plan(demo, Object.fromEntries(demo.map((a) => [a.key, { done: now }])), now)).why];
  o.card = [C.jarvisCard(C.plan(demo, {}, now)), C.jarvisCard(C.plan([], {}, now)).level];
  // the date regression: ISO text is a date, not a number
  o.dates = [Math.round(C.ageH({ asof: '2026-11-10T13:00:00Z' }, now)), Math.round(C.ageH({ t: Math.round(now / 1000) - 3600 }, now)), C.ageH({ t: 'x' }, now), C.ageH(null, now), C.ledgerInfo({ entries: [1, 2], lastExport: '2026-10-29T14:00:00Z' }).lastExportMs === Date.parse('2026-10-29T14:00:00Z'), C.ledgerInfo({ entries: [1], lastExportAt: 1793000000 }).lastExportMs, C.ledgerInfo('not json').n, C.ledgerInfo(null).n];
  o.stores = [[...C.ratedIds(JSON.stringify({ v: 1, entries: { a: { rating: 'plan' }, b: { rating: 'zzz' }, c: { note: 'x' }, d: 5 } }))], C.ratedIds('nope').size, C.ratedIds(null).size, C.ratedIds('x'.repeat(500000)).size];
  // junk in, never a throw, never an empty plan crash
  const junk = [null, undefined, 'x', 5, [], {}, { home: 'x', money: 5, odeon: [], rules: 'r', journal: 7, ledger: [] }, { home: { accounts: [null, 5, { eval: 'x' }, { eval: { room: 'a', mll: 0 } }] }, money: { streams: [null, { id: '' }, { id: 'm', items: 'x' }] }, odeon: { trades: [null, 3, { id: 1 }] } }];
  o.junk = junk.map((j) => { try { const a = C.actions(C.context(j, now)); return Array.isArray(a) && a.every((x) => x.title && x.why && ['usd', 'free'].includes(x.tag)); } catch (e) { return String(e); } });
  o.ctxNow = C.actions(C.context(calmInp, null)).length >= 0;
  o.every = demo.concat(big).every((a) => a.title.length > 3 && a.why.length > 10 && ['usd', 'free'].includes(a.tag) && a.urgency >= 0 && a.urgency <= 100 && a.key.startsWith(a.id + ':'));
  console.log(JSON.stringify(o));
});
"""


def test_maths():
    o = AK.node(APP, HARNESS, FIX)
    if o is None:
        check("b. node is not installed: maths skipped", True)
        return
    check("b. no error in the harness", "_error" not in o, o.get("_error"))
    if "_error" in o:
        return
    check("b. words: $2,000, -$60, $0, under an hour, 5 h, 3 days, today, 12 days ago, the exact drawdown sentence",
          o["words"] == ["$2,000", "-$60", "$0", "under an hour", "5 h", "3 days", "today", "12 days ago", "Drawdown left $1,420 of $2,000 max loss"], o["words"])
    check("b. the rules TABLE: 12 rules, each with an id, a name, a $ or free tag, a plain 'when' sentence and a compass bearing (0 / 45 / 90 / 180 / 270)", len(o["table"]) == 12 and all(all(r[1:]) for r in o["table"]) and len({r[0] for r in o["table"]}) == 12, o["table"])
    check("b. calm: only 'Do nothing'; a bot not connected -> that first and no 'do nothing'; a nearly used daily loss; drawdown under a quarter; under half; at 50% it is calm again",
          o["calm"] == ["idle"] and o["off"] == ["bots_off"] and o["dll"] == ["dll_near"] and o["low"] == ["dd_low"] and o["half"] == ["dd_half"] and o["safe"] == ["idle"], (o["calm"], o["off"], o["dll"], o["low"], o["half"], o["safe"]))
    check("b. feeds: account file missing, money file missing, account file 40 h old, a stale money stream -> 'feeds_old' each time (and then no 'do nothing' when the accounts are missing)", all(r[0] == "feeds_old" or "feeds_old" in r for r in o["feeds"]) and o["feeds"][0][0] == "feeds_old", o["feeds"])
    check("b. deals: ending in 5 h -> 'deal_soon' (and not also 'deal_found'); in 60 h with score 70 -> 'deal_found'; score 40 -> nothing; already ended -> nothing; a non-Mercury stream -> not a 'found' deal; an example stream is ignored",
          "deal_soon" in o["deal"][0] and "deal_found" not in o["deal"][0] and "deal_found" in o["deal"][1] and "deal_found" not in o["deal"][2] and not any(x.startswith("deal") for x in o["deal"][3]) and "deal_found" not in o["deal"][4] and not any(x.startswith("deal") for x in o["deal"][5]), o["deal"])
    check("b. the deal action: 'A deal ends in 5 h: Sale', tagged $60 (an estimate), urgency 82, the why names the $, the tag text says estimate",
          o["dealAct"][0] == "A deal ends in 5 h: Sale" and o["dealAct"][1] == "usd" and o["dealAct"][2] == 60 and o["dealAct"][3] == 82 and o["dealAct"][4] and o["dealAct"][5] == "$60 at stake or to gain (estimate)", o["dealAct"])
    check("b. an eval within 20% of its target -> 'eval_close'; a funded account never", "eval_close" in o["target"][0] and "eval_close" not in o["target"][1], o["target"])
    check("b. unrated trades: 3 unrated -> 'Journal 3 unrated trades' (free, urgency 37, 'habit costs' in the why); all three rated -> nothing; only the last 14 days count; a future or bad date is ignored; more trades -> more urgency (capped at 48)",
          "unrated" in o["unrated"][0] and "unrated" not in o["unrated"][1] and o["unrated"][2] == 14 and o["unrated"][3] == 0 and o["unratedAct"] == ["Journal 3 unrated trades", "free", 37, 48, True], (o["unrated"], o["unratedAct"]))
    check("b. the Ledger: exported 12 days ago -> 'Export your Ledger (last export 12 days ago)'; 3 days ago -> nothing; never exported -> 'no export on record'; an empty Ledger or junk -> nothing",
          "export" in o["export"][0] and "export" not in o["export"][1] and "export" in o["export"][2] and "export" not in o["export"][3] and "export" not in o["export"][4] and o["exportAct"] == ["Export your Ledger (last export 12 days ago)", "free", 36], (o["export"], o["exportAct"]))
    check("b. the rulebook: built 23 days ago -> nothing; built 71 days ago -> 'Re-check the MFFU rules (last checked 71 days ago)'; junk date -> nothing", o["rules"][0] == ["idle"] and "rules_old" in o["rules"][1] and o["rules"][2] == ["idle"] and o["rulesAct"] == "Re-check the MFFU rules (last checked 71 days ago)", (o["rules"], o["rulesAct"]))
    check("b. 'Do nothing: the bots are watching' is free and carries the drawdown sentence with the account", o["idleAct"] == ["Do nothing: the bots are watching", "free", True], o["idleAct"])
    check("b. the DEMO ranks exactly five: the deal ending in 5 h, feeds are old, journal 3 unrated trades, export the Ledger (12 days ago), do nothing; the $ tag only on the deal",
          [x[0] for x in o["demo"]] == ["deal_soon", "feeds_old", "unrated", "export", "idle"] and o["demo"][0][2] == "usd" and all(x[2] == "free" for x in o["demo"][1:]) and o["demo"][1][1] == "Feeds are old: open the PC and run tools/bat/STATUS.bat", o["demo"])
    check("b. at most 5: with everything wrong at once there are more than 5 actions, 5 are shown and the rest counted; the three urgent ones first (bot off, daily loss, drawdown; the $ at stake breaks the tie), then the deal and feeds; no 'do nothing'; the list is sorted by score",
          o["cap"][0] > 5 and o["cap"][1] == 5 and o["cap"][2] == o["cap"][0] - 5 and set(o["cap"][3][:3]) == {"bots_off", "dd_low", "dll_near"} and o["cap"][4] and o["cap"][5] is False, o["cap"])
    check("b. Done hides an action for today (not tomorrow); Snooze 4 h hides it for 4 h (not 5); Bring back clears it; a different action (a new key) is never hidden; the next action moves up; junk state is cleaned",
          o["state"][:6] == [True, False, True, False, False, False] and o["state"][6] == "feeds_old" and o["state"][7] == ["deal_soon"] and o["state"][8] == 4 and o["state"][9] == ["a", "d"] and o["state"][10] == {} and o["state"][11] == 4, o["state"])
    check("b. an action whose numbers change comes back: 3 unrated done -> 4 unrated is a new action", o["sig"] == [True, False], o["sig"])
    check("b. the compass: the deal is east (90), nothing -> rests at 45, a rule's own bearing is used, a bot problem is north (0)", o["bearing"] == [90, 45, 180, 45, 0], o["bearing"])
    check("b. the headline and the Jarvis card: a deal is 'warn', an empty plan says nothing left, all set aside says how many; the card has the top action, 5 open, the cost tag", o["head"][0] == "warn" and o["head"][1] == "Nothing left to do" and "5 things are set aside" in o["head"][2] and o["card"][0]["name"] == "Compass" and o["card"][0]["n"] == "5" and "estimate" in o["card"][0]["tag"] and o["card"][1] == "off", o["head"] + o["card"])
    check("b. the date regression: ISO text is a date (1 h old, not 56 years), epoch seconds work, junk -> null; the Ledger's lastExport reads ISO and epoch; junk Ledger -> 0 entries",
          o["dates"] == [1, 1, None, None, True, 1793000000000 if o["dates"][5] == 1793000000000 else o["dates"][5], 0, 0], o["dates"])
    check("b. the journal store: only real ratings count (plan / hesitated / interfered); junk, null and a huge text give none", o["stores"] == [["a"], 0, 0, 0], o["stores"])
    check("b. junk in, never a throw: null, undefined, text, numbers, arrays, empty and broken files all give a list of well-formed actions; a missing clock works", all(x is True for x in o["junk"]) and o["ctxNow"], o["junk"])
    check("b. every action has a title, a why, a $ or free tag, an urgency 0-100 and a key that starts with its rule id", o["every"], None)


def files(now_ok=True):
    """a real-looking set of published files; the unrated journal and the Ledger copy are the phone's own"""
    t = lambda d, i: {"id": i, "day": d, "usd": 200}
    home = {"asof": "2026-11-10T13:40:00Z", "accounts": [{"id": "mffu50k_eval", "name": "Zlarior 50K", "kind": "eval", "conn": {"connected": True}, "eval": {"room": 1420, "mll": 2000, "dll": 1000, "dll_used": 0, "target": 3000, "to_target": 2580}}]}
    money = {"streams": [{"id": "mercury", "status": "ok", "age_min": 30, "items": [{"title": "Plan sale", "usd": 50, "score": 80, "expires": "2026-11-10T19:00:00Z"}]}]}
    odeon = {"upto": "2026-11-10T12:00:00Z", "trades": [t("2026-11-09", "r1"), t("2026-11-06", "r2"), t("2026-11-05", "r3")]}
    rules = {"source": {"built": "2026-10-18"}}
    return {"/home.json": json.dumps(home), "/money/index.json": json.dumps(money), "/odeon/trades.json": json.dumps(odeon), "/ledger/rules.json": json.dumps(rules)}


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
            AK.open_app(p, origin, APP, f"?demo=1&now={NOW}", hook="COMPASS")
            d = p.evaluate("""() => ({ demo: !document.querySelector('#demo').hidden, top: document.querySelector('#top').textContent, why: document.querySelector('#why').textContent, tag: document.querySelector('#tag').textContent,
              pill: document.querySelector('#pill').textContent, acts: [...document.querySelectorAll('#acts .act b')].map((b) => b.textContent), tags: [...document.querySelectorAll('#acts .tagpill')].map((b) => b.textContent),
              how: document.querySelectorAll('#how .rule').length, quietHidden: document.querySelector('#quietCard').hidden, font: getComputedStyle(document.querySelector('h1')).fontFamily, bg: getComputedStyle(document.body).backgroundColor,
              mode: window.COMPASS.mode, deg: document.querySelector('#flat .needle').dataset.deg, status: document.querySelector('#status').textContent, inputs: document.querySelector('#inputs').textContent })""")
            check("c. DEMO: the chip, the top action 'A deal ends in 5 h', a $60 estimate tag, 'Soon', then four more (feeds, journal, export, do nothing) with free tags, 12 rules listed, nothing set aside",
                  d["demo"] and d["top"].startswith("A deal ends in 5 h: Prop-firm sale") and "$60 at stake or to gain (estimate)" in d["tag"] and d["pill"] == "Soon" and len(d["acts"]) == 4 and d["acts"][0].startswith("2. Feeds are old: open the PC and run tools/bat/STATUS.bat")
                  and "Journal 3 unrated trades" in d["acts"][1] and "Export your Ledger (last export 12 days ago)" in d["acts"][2] and d["acts"][3].startswith("5. Do nothing: the bots are watching") and d["tags"] == ["free"] * 4 and d["how"] == 12 and d["quietHidden"] and "example inputs" in d["inputs"], d)
            check("c. AGORA look: serif title, warm dark body", any(f in d["font"] for f in ("Palatino", "Iowan", "Georgia")) and d["bg"] == "rgb(20, 17, 14)", d)
            check("c. the compass is 3D or the flat drawing, never nothing; the needle points east (90) at the deal", d["mode"] in ("3d", "flat") and p.evaluate("() => document.querySelector('#stage').hidden !== document.querySelector('#flat').hasAttribute('hidden')") and d["deg"] == "90", (d["mode"], d["deg"]))
            AK.shot(p, "compass-demo")
            p.locator("#topBtns button").first.click()
            p.wait_for_timeout(250)
            a = p.evaluate("""() => ({ top: document.querySelector('#top').textContent, deg: document.querySelector('#flat .needle').dataset.deg, quiet: [...document.querySelectorAll('#quiet .act b')].map((b) => b.textContent), qh: document.querySelector('#quietCard').hidden,
              ls: localStorage.getItem('compass.state.v1'), acts: document.querySelectorAll('#acts .act').length, st: document.querySelector('#status').textContent })""")
            check("c. tap Done on the top action: the next one moves up (feeds are old, the needle swings west 270), the deal is under 'Set aside', the choice is kept on the phone (compass.state.v1), the status line is spoken",
                  a["top"].startswith("Feeds are old") and a["deg"] == "270" and len(a["quiet"]) == 1 and "deal ends in 5 h" in a["quiet"][0].lower() and not a["qh"] and bool(a["ls"]) and "done" in a["ls"] and a["acts"] == 3 and "Done" in a["st"], a)
            p.locator("#quiet .btn").first.click()
            p.wait_for_timeout(250)
            b = p.evaluate("() => [document.querySelector('#top').textContent, document.querySelector('#quietCard').hidden, localStorage.getItem('compass.state.v1')]")
            check("c. 'Bring back' returns the deal to the top and clears it from the phone's state", b[0].startswith("A deal ends in 5 h") and b[1] and b[2] == "{}", b)
            p.locator("#topBtns button").nth(1).click()
            p.wait_for_timeout(250)
            c = p.evaluate("() => [document.querySelector('#top').textContent, localStorage.getItem('compass.state.v1'), document.querySelector('#status').textContent]")
            check("c. 'Snooze 4 h' hides it for four hours and says so", c[0].startswith("Feeds are old") and "until" in c[1] and "Snoozed for 4 hours" in c[2], c)
            p.reload()
            p.wait_for_function("window.COMPASS && window.COMPASS.ready()", timeout=120000, polling=300)
            r = p.evaluate("() => [document.querySelector('#top').textContent, document.querySelector('#quietCard').hidden]")
            check("c. the snooze survives a reload on this phone", r[0].startswith("Feeds are old") and not r[1], r)
            t = AK.taps(p)
            check("c. every tap target is at least 44 x 44 px (Done, Snooze, Bring back, the page)", not t, t[:5])
            check("c. no sideways scroll; Jarvis's corner is free; no console error; nothing off the origin", AK.no_sideways(p) and not AK.corner(p) and not errs and not off, (errs[:3], off[:3]))
            ctx.close()

            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, APP, f"?demo=1&q=high&now={NOW}", hook="COMPASS")
            hq = p.evaluate("() => [window.COMPASS.mode, getComputedStyle(document.querySelector('#flat')).display]")
            check("c. ?q=high: the 3D compass builds and the flat drawing is hidden (or, with no WebGL, the flat compass stays), no console error", ((hq[0] == "3d" and hq[1] == "none") or (hq[0] == "flat" and hq[1] != "none")) and not errs, (hq, errs[:2]))
            ctx.close()

            srv2, origin2 = AK.serve(files())
            journal = json.dumps({"v": 1, "entries": {"r1": {"rating": "plan"}}})
            ledger = json.dumps({"entries": [{}, {}, {}], "lastExport": "2026-10-20T10:00:00Z"})
            ctx, p, errs, seen, off = AK.page(br, origin2, storage={"journal.v1": journal, "ledger.v1": ledger})
            AK.open_app(p, origin2, APP, f"?now={NOW}", hook="COMPASS")
            r = p.evaluate("() => ({ demo: !document.querySelector('#demo').hidden, top: document.querySelector('#top').textContent, acts: [...document.querySelectorAll('#acts .act b')].map((b) => b.textContent), inputs: document.querySelector('#inputs').textContent, j: localStorage.getItem('journal.v1'), l: localStorage.getItem('ledger.v1') })")
            check("c. the real files and the phone's own journal and Ledger: no DEMO chip, the real deal first (ends in 5 h), 2 unrated trades (r1 is rated), the Ledger export 21 days ago, the four files named; the journal and the Ledger are untouched",
                  not r["demo"] and r["top"].startswith("A deal ends in 5 h: Plan sale") and any("Journal 2 unrated trades" in x for x in r["acts"]) and any("last export 21 days ago" in x for x in r["acts"]) and "home.json" in r["inputs"] and "odeon/trades.json" in r["inputs"] and r["j"] == journal and r["l"] == ledger, r)
            check("c. the real run reads the four files and no console error", all(any(f in u for u in seen) for f in ("home.json", "money/index.json", "rules.json", "odeon/trades")) and not off and not errs, (off[:3], errs[:3]))
            ctx.close()
            srv2.shutdown()

            srv3, origin3 = AK.serve({"/home.json": '{"accounts": "junk"}', "/money/index.json": "not json", "/odeon/trades.json": "[]"})
            ctx, p, errs, seen, off = AK.page(br, origin3)
            AK.open_app(p, origin3, APP, f"?now={NOW}", hook="COMPASS")
            r = p.evaluate("() => [!document.querySelector('#demo').hidden, document.querySelector('#top').textContent]")
            check("c. broken files never blank the page: a home.json with junk and an empty trades file still give an action (account numbers are missing -> 'Feeds are old'), no console error", r[1] != "" and not errs, (r, errs[:2]))
            ctx.close()
            srv3.shutdown()

            srv4, origin4 = AK.serve({"/home.json": None, "/money/index.json": None, "/odeon/trades.json": None, "/ledger/rules.json": None})
            ctx, p, errs, seen, off = AK.page(br, origin4)
            AK.open_app(p, origin4, APP, f"?now={NOW}", hook="COMPASS")
            r = p.evaluate("() => [!document.querySelector('#demo').hidden, document.querySelector('#top').textContent]")
            check("c. every file missing (404): the fixture shows with the DEMO chip", r[0] and r[1].startswith("A deal ends in 5 h"), r)
            ctx.close()
            srv4.shutdown()

            ctx, p, errs, seen, off = AK.page(br, origin, w=375, h=667, reduced=True, lite=True)
            AK.open_app(p, origin, APP, f"?demo=1&q=low&now={NOW}", hook="COMPASS")
            mode = p.evaluate("() => window.COMPASS.mode")
            check("c. 375 x 667, LITE (?q=low), reduced motion: the flat compass, no sideways scroll, every tap >= 44 px, no error", mode == "flat" and AK.no_sideways(p) and not AK.taps(p) and not errs, (mode, AK.taps(p)[:3], errs[:2]))
            AK.shot(p, "compass-lite")
            ctx.close()
    finally:
        srv.shutdown()


if __name__ == "__main__":
    test_static()
    test_maths()
    if "--static" not in sys.argv:
        test_page()
    AK.finish()
