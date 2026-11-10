"""Jarvis x Kalshi (job 3, 2026-11-04): tools/web_public/jarvis/kalshi-brain.js with brain.js and modes.js, driven in node on a fixed clock with the REAL data:
the Kalshi feed (research/kalshi/feed_snapshot_2026-11-04.json: balance $55.81, paused, 1,836 bets) and the engine's own files (tools/web_public/kalshicity/edges.json,
learning_log.json, learned.json). Read only: nothing here orders, sizes or changes the bot. Checks:
  a. the files: an ES module with no imports / network / DOM, Safari 16 safe (no optional chaining, no lookbehind), no order / arm word; the shell loads it, the brain and
     the modes carry their delimited blocks, the Money tile line; sw.js is not edited by this job
  b. the snapshot: the real numbers (paused, $55.81, week -$3.30, the engine's do-more / stop lists, the ruin band), the feed alone, the engine alone (not live)
  c. the diff: nothing at the first look and from an unchanged feed or an engine-only copy; paused, resumed, the balance floor, the daily loss over 10%, a 98c favourite lost
     (a 60c loss or a $1 loss is not), a new DO MORE / STOP lesson, the risk of ruin moving
  d. speaking: held while busy then said, 30 s apart, 8 an hour (a pause still gets through), once ever, one line for up to 3 events, quiet hours, the switch, hidden balances
  e. the asks through the brain with the real data: how is Kalshi, is it running, what should I stop, my best edge, the risks, how much should I bet (always "suggestion, your call"),
     what did Kalshi learn today; every reply has speak; "place a Kalshi order" is refused; the NQ bots' own questions are untouched; nothing is fetched
  f. Think for me and Business mode: the Kalshi items, the quick asks
  g. Chromium, the real shell: the module loads, the Kalshi tile on the Money cards carries the engine's line, typed asks are answered from the real data (what to stop, best
     edge, how much to bet), a pause on the next poll is spoken and toasted, no page errors, nothing leaves the machine
    python -X utf8 -m tests.test_jarvis_kalshi        (node ~5 s + Chromium ~60 s; JK_NO_BROWSER=1 skips g)
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JV = os.path.join(ROOT, "tools", "web_public", "jarvis")
KC = os.path.join(ROOT, "tools", "web_public", "kalshicity")
FEED = os.path.join(ROOT, "research", "kalshi", "feed_snapshot_2026-11-04.json")
RES = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:900]}"), flush=True)


def rd(*p):
    with open(os.path.join(*p), encoding="utf-8") as fh:
        return fh.read()


RUNNER = r"""
import fs from 'node:fs';
import { pathToFileURL } from 'node:url';
const [dir, kc, feedPath] = process.argv.slice(1);
const U = (f) => pathToFileURL(dir + '/' + f).href;
const K = await import(U('kalshi-brain.js')), BR = await import(U('brain.js')), MO = await import(U('modes.js'));
const J = (p) => JSON.parse(fs.readFileSync(p, 'utf8'));
const FEED = J(feedPath), EDGES = J(kc + '/edges.json'), LOG = J(kc + '/learning_log.json'), LEARNED = J(kc + '/learned.json');
const cl = (x) => JSON.parse(JSON.stringify(x));
const mkStore = () => { const m = {}; return { m, getItem: (k) => (k in m ? m[k] : null), setItem: (k, v) => { m[k] = String(v); }, removeItem: (k) => { delete m[k]; } }; };
const NOW = (FEED.t + 600) * 1000;                       // ten minutes after the feed's own time
const DATA = { edges: EDGES, log: LOG, learned: LEARNED };
const out = {};
const live = (over) => Object.assign(cl(FEED), over || {});
const running = (over) => live(Object.assign({ running: true, status: 'Running' }, over || {}));

// b. the snapshots
{
  const s = K.snapshot(FEED, DATA, NOW), f = K.snapshot(FEED, null, NOW), e = K.snapshot(null, DATA, NOW), n = K.snapshot(null, null, NOW);
  out.snap = { ok: s.ok, paused: s.paused, running: s.running, status: s.status, balance: s.balance, today: s.today, week: s.week, total: s.total, live: s.live, stale: s.stale, mode: s.mode,
    doMore: s.doMore.map((x) => x.id), stop: s.stop.map((x) => x.id), counts: s.counts, ruin: s.ruin, band: s.ruinBand, lessons: s.lessons.length, todayLessons: s.todayLessons.length, losses: s.losses.length,
    trades: s.trades.length, regime: s.regime, hasLearned: !!s.learned, stakeFrac: s.stakeFrac };
  out.feedOnly = { ok: f.ok, paused: f.paused, counts: f.counts, ruin: f.ruin, doMore: f.doMore.length };
  out.engineOnly = { ok: e.ok, live: e.live, balance: e.balance, paused: e.paused };
  out.none = { ok: n.ok };
  out.engineDo = EDGES.lists.do_more; out.engineStop = EDGES.lists.stop; out.engineCounts = EDGES.counts; out.engineRuin = EDGES.book.ruin_now;
}
// c. the diff
{
  const base = K.snapshot(running(), DATA, NOW), compact = (s) => ({ ok: s.ok, t: s.t, paused: s.paused, balance: s.balance, dayLossFrac: s.dayLossFrac, trades: s.trades, ruinBand: s.ruinBand, ek: s.lessons.map((x) => x.ek), eng: !!s.counts, ymd: s.ymd });
  const P = compact(base), d = (over, data, setg) => K.diff(P, K.snapshot(running(over), data || DATA, NOW + 60e3), NOW + 60e3, setg).map((e) => ({ kind: e.kind, key: e.key, level: e.level, p: e.p, text: e.text, say: e.say }));
  out.d = {};
  out.d.first = K.diff(null, base, NOW).length;
  out.d.same = d({}).length;
  out.d.engineOnly = K.diff(P, K.snapshot(null, DATA, NOW + 60e3), NOW + 60e3).length;
  out.d.lateEngine = K.diff(Object.assign({}, P, { eng: false, ek: [] }), K.snapshot(running(), DATA, NOW + 60e3), NOW + 60e3).length;
  out.d.paused = K.diff(compact(K.snapshot(running(), DATA, NOW)), K.snapshot(FEED, DATA, NOW + 60e3), NOW + 60e3).map((e) => e.kind);
  out.d.resumed = K.diff(compact(K.snapshot(FEED, DATA, NOW)), K.snapshot(running(), DATA, NOW + 60e3), NOW + 60e3).map((e) => e.kind);
  const lowP = compact(K.snapshot(running({ balance: 41 }), DATA, NOW)); lowP.balance = 41;
  out.d.floor = K.diff(Object.assign({}, P, { balance: 41 }), K.snapshot(running(), Object.assign({}, DATA), NOW + 60e3), NOW + 60e3, { floor: 50 }).map((e) => ({ kind: e.kind, text: e.text }));
  out.d.floorNo = K.diff(Object.assign({}, P, { balance: 61 }), K.snapshot(running(), DATA, NOW + 60e3), NOW + 60e3, { floor: 40 }).map((e) => e.kind);
  out.d.dayloss = K.diff(P, K.snapshot(running({ today_pnl: -6.5, balance: 55.81 }), DATA, NOW + 60e3), NOW + 60e3).map((e) => ({ kind: e.kind, text: e.text }));
  out.d.dayloss2 = K.diff(Object.assign({}, P, { dayLossFrac: 0.12 }), K.snapshot(running({ today_pnl: -7, balance: 55.81 }), DATA, NOW + 60e3), NOW + 60e3).map((e) => e.kind);
  const tr = (pnl, price, t) => ({ t, ticker: 'KXBTCD-X' + t, title: 'Bitcoin above $77,400', side: 'yes', action: 'buy', contracts: 6, price, pnl, category: 'Bitcoin', strategy: 'Late favourite (BTC hourly)' });
  const withTrades = (arrT) => running({ trades: arrT.concat(FEED.trades) });
  out.d.big = K.diff(P, K.snapshot(withTrades([tr(-5.89, 0.98, FEED.t + 100)]), DATA, NOW + 60e3), NOW + 60e3).map((e) => ({ kind: e.kind, text: e.text, say: e.say, p: e.p }));
  out.d.bigNo = [tr(-5.89, 0.6, FEED.t + 101), tr(-1.0, 0.98, FEED.t + 102), tr(2.0, 0.98, FEED.t + 103)].map((t) => K.diff(P, K.snapshot(withTrades([t]), DATA, NOW + 60e3), NOW + 60e3).length);
  const log2 = cl(LOG); log2.entries.push({ d: EDGES.day, t: FEED.t + 200, kind: 'learned', id: '*~Gold~*~*~*', status: 'HOLDING', advice: 'do_more', n: 40, ev: 0.02, text: 'Learned: Gold: EV +$0.020 per $1 over 40 bets: DO MORE', ek: 'x|verdict|do_more' });
  log2.entries.push({ d: EDGES.day, t: FEED.t + 201, kind: 'learned', id: 'a', status: 'DEAD', advice: 'stop', n: 40, ev: -0.1, text: 'Learned: HYPE: EV -$0.100 per $1 over 40 bets: STOP', ek: 'y|verdict|stop' });
  const lessonEv = K.diff(P, K.snapshot(running(), { edges: EDGES, log: log2, learned: LEARNED }, NOW + 60e3), NOW + 60e3);
  out.d.lesson = lessonEv.map((e) => ({ kind: e.kind, text: e.text, say: e.say }));
  const E2 = cl(EDGES); E2.book.ruin_now = 0.05;
  out.d.ruinDown = K.diff(P, K.snapshot(running(), { edges: E2, log: LOG, learned: LEARNED }, NOW + 60e3), NOW + 60e3).map((e) => ({ kind: e.kind, level: e.level, text: e.text }));
  const E3 = cl(EDGES); E3.book.ruin_now = 0.99; const P3 = Object.assign({}, P, { ruinBand: 'low' });
  out.d.ruinUp = K.diff(P3, K.snapshot(running(), { edges: E3, log: LOG, learned: LEARNED }, NOW + 60e3), NOW + 60e3).map((e) => ({ kind: e.kind, level: e.level }));
}
// d. speaking
{
  const spoken = [], toasts = [];
  const mk = (st, o2) => K.createKalshiBrain(Object.assign({ storage: st, now: () => NOW, speak: (t) => { spoken.push(t); return 'spoken'; }, onEvent: (e) => toasts.push(e) }, o2 || {}));
  const st = mkStore(); let busy = false, hid = false;
  const kb = mk(st, { busy: () => busy, hidden: () => hid }); kb.setData(DATA);
  const r0 = kb.tick(running(), NOW);
  out.sp = { first: { events: r0.events.length, spoken: r0.spoken.length } };
  busy = true;
  const r1 = kb.tick(FEED, NOW + 60e3);
  out.sp.busy = { events: r1.events.map((e) => e.kind), spoken: r1.spoken.length, reason: r1.reason, queued: kb.queued().length };
  busy = false;
  const r2 = kb.flush(NOW + 70e3);
  out.sp.said = { n: r2.spoken.length, text: spoken[0] || '' };
  const r3 = kb.tick(running(), NOW + 80e3);                                         // resumed, but inside 30 s of the last one
  out.sp.gap = { events: r3.events.map((e) => e.kind), spoken: r3.spoken.length, reason: r3.reason };
  const r4 = kb.flush(NOW + 110e3);
  out.sp.afterGap = { spoken: r4.spoken.map((e) => e.kind) };
  const again = mk(st, {}); again.setData(DATA);
  const rr = again.tick(FEED, NOW + 120e3);
  out.sp.reload = { events: rr.events.length };                                      // the pause key (the feed's own time) is said once ever
  out.sp.log = kb.log().length; out.sp.toasts = toasts.length;
  // a batch of three: a pause, the floor, a big loss in one reading
  const st2 = mkStore(), spoken2 = []; const kb2 = K.createKalshiBrain({ storage: st2, now: () => NOW, speak: (t) => { spoken2.push(t); return 'spoken'; } }); kb2.setData(DATA);
  kb2.set({ floor: 60 }); kb2.tick(running({ balance: 70 }), NOW);
  const trb = { t: FEED.t + 500, ticker: 'KXBTCD-BIG', title: 'Bitcoin above $77,400', side: 'yes', action: 'buy', contracts: 6, price: 0.98, pnl: -5.89, category: 'Bitcoin' };
  const rb = kb2.tick(running({ balance: 55, trades: [trb].concat(FEED.trades) }), NOW + 60e3);
  out.sp.batch = { events: rb.events.map((e) => e.kind).sort(), spoken: spoken2.length, text: spoken2[0] || '' };
  // 8 an hour: the hour is already full (8 alerts said in the last hour): a calm lesson is dropped, a pause still gets through
  const st3 = mkStore(), sp3 = []; const kb3 = K.createKalshiBrain({ storage: st3, now: () => NOW, speak: (t) => { sp3.push(t); return 'spoken'; } }); kb3.setData(DATA);
  kb3.tick(running(), NOW);
  const nowS = (NOW + 60e3) / 1000;
  st3.setItem(K.SPOKEN_KEY, JSON.stringify({ groups: {}, hours: [1, 2, 3, 4, 5, 6, 7, 8].map((i) => nowS - 600 - i * 60), last: nowS - 100 }));
  const lg = cl(LOG); lg.entries.push({ d: EDGES.day, t: FEED.t + 300, kind: 'learned', id: 'z', status: 'HOLDING', advice: 'do_more', n: 40, ev: 0.02, text: 'Learned: Zed: DO MORE', ek: 'zed' }); kb3.setData({ log: lg });
  const rl = kb3.tick(running(), NOW + 60e3);
  const rp = kb3.tick(FEED, NOW + 120e3);
  out.sp.hourly = { lessonEvents: rl.events.map((e) => e.kind), lessonSpoken: rl.spoken.length, lessonReason: rl.reason, pauseSpoken: rp.spoken.map((e) => e.kind) };
  // quiet hours, the switch, hidden balances
  const st4 = mkStore(), sp4 = []; const kb4 = K.createKalshiBrain({ storage: st4, now: () => NOW, hidden: () => true, speak: (t) => { sp4.push(t); return 'spoken'; } }); kb4.setData(DATA);
  kb4.tick(running({ balance: 70 }), NOW); kb4.set({ floor: 60 });
  kb4.tick(live({ balance: 55, running: true, status: 'Running' }), NOW + 60e3);
  out.sp.hidden = sp4[0] || '';
  const st5 = mkStore(), sp5 = []; const kb5 = K.createKalshiBrain({ storage: st5, now: () => NOW, speak: (t) => { sp5.push(t); return 'spoken'; } }); kb5.setData(DATA);
  kb5.tick(running(), NOW);
  const etNow = K.etOf(NOW + 60e3); kb5.set({ quiet: { on: true, from: String(etNow.h - 1 < 0 ? 23 : etNow.h - 1).padStart(2, '0') + ':00', to: String((etNow.h + 1) % 24).padStart(2, '0') + ':00' } });
  const rq = kb5.tick(FEED, NOW + 60e3); out.sp.quiet = { events: rq.events.length, spoken: sp5.length, reason: rq.reason };
  const st6 = mkStore(), sp6 = []; const kb6 = K.createKalshiBrain({ storage: st6, now: () => NOW, speak: (t) => { sp6.push(t); return 'spoken'; } }); kb6.setData(DATA);
  kb6.tick(running(), NOW); kb6.set({ on: false }); kb6.tick(FEED, NOW + 60e3);
  out.sp.off = { spoken: sp6.length, settings: kb6.settings().on };
}
// e. the asks through the brain
const fetches = [];
const brainFor = (feedObj, data) => {
  const st = mkStore(), modes = MO.createModes({ storage: st }), kb = K.createKalshiBrain({ storage: st, now: () => NOW }); kb.setData(data === undefined ? DATA : data);
  const brain = BR.createBrain({ storage: st, fetch: async (u) => { fetches.push(String(u)); throw new Error('no network'); }, getFacts: () => ({ now: NOW, live: null, kalshi: feedObj, kalshiState: feedObj ? 'ok' : 'waiting', apps: [] }), now: () => new Date(NOW), modes, kalshiBrain: kb });
  return { brain, kb, st, modes };
};
const ASK = ['how is kalshi', 'is the kalshi bot running', 'what should I stop doing on kalshi', "what's my best kalshi edge", 'what are the kalshi risks', 'how much should I bet', 'what did kalshi learn today',
  'how much should i bet on kalshi', 'is kalshi paused', 'turn kalshi alerts off', 'turn kalshi alerts on', 'kalshi alerts floor 30', 'place a kalshi order', 'how are the bots', "what's the plan", 'how is the kalshi edge', 'kalshi lessons', 'is kalshi making money', 'what should i stop on kalshi'];
{
  const b = brainFor(FEED);
  const R = {};
  for (const q of ASK) { const r = await b.brain.ask(q); R[q] = { text: r.text, speak: r.speak, say: r.say, intent: r.intent, cards: r.cards || null, control: r.control || '' }; }
  out.ask = R; out.askSet = JSON.parse(b.st.getItem(K.SET_KEY) || 'null');
  const b2 = brainFor(null, null); const r2 = await b2.brain.ask('how is kalshi'); out.askNone = { text: r2.text, intent: r2.intent };
  const b3 = brainFor(running(), DATA); const r3 = await b3.brain.ask('is the kalshi bot running'); out.askRun = { text: r3.text, speak: r3.speak };
  const b4 = brainFor(running({ today_pnl: -8, balance: 50 }), DATA); const r4 = await b4.brain.ask('what are the kalshi risks'); out.askLoss = r4.text;
  out.fetches = fetches.slice();
}
// f. think for me, business quick asks
{
  const b = brainFor(FEED);
  const t = await b.brain.ask('think for me'), tb = MO.thinkAll({ et: { h: 12, min: 720, y: 2026, mo: 11, d: 4, dn: 1, wd: 3 }, kalshiBrain: { items: b.kb.items(FEED, NOW) }, kalshi: { state: 'ok', run: 'paused' }, market: { open: false }, priorities: [], accounts: [] });
  out.items = b.kb.items(FEED, NOW).map((x) => ({ p: x.p, key: x.key, label: x.label, text: x.text, action: x.action }));
  out.think = tb.filter((x) => /^kalshi:/.test(x.key)).map((x) => ({ key: x.key, mode: x.mode, label: x.label, action: x.action, say: x.say }));
  out.quick = MO.MODES.business.quick;
  out.line = b.kb.line(FEED, NOW);
  out.thinkAsk = { intent: t.intent, hasKalshi: /kalshi/i.test(t.text || '') };
}
console.log('@@' + JSON.stringify(out));
"""


def run_node():
    p = subprocess.run(["node", "--input-type=module", "-e", RUNNER, JV, KC, FEED], capture_output=True, text=True, timeout=120)
    m = [ln for ln in p.stdout.splitlines() if ln.startswith("@@")]
    if not m:
        return {"error": (p.stderr or p.stdout)[-1500:]}
    return json.loads(m[-1][2:])


def part_a():
    js = rd(JV, "kalshi-brain.js")
    check("a. kalshi-brain.js is a plain ES module: no import, no fetch / XHR / WebSocket, no document / window, no order or arm code path",
          not re.search(r"^\s*import\s|\bfetch\(|XMLHttpRequest|WebSocket|sendBeacon|\bdocument\.|\bwindow\.", js, re.M) and not re.search(r"place_order|placeOrder|createOrder|\barm\(|disarm\(|/orders", js))
    check("a. Safari 16 safe: no optional chaining, no nullish operator, no lookbehind regex", not re.search(r"\?\.[A-Za-z_\[(]|\?\?", js) and not re.search(r"\(\?<[=!]", js))
    html, brain, modes = rd(JV, "index.html"), rd(JV, "brain.js"), rd(JV, "modes.js")
    check("a. the shell loads the module, gives it the busy() of the mic / voice mode / another reply, fetches only the site's own kalshicity files, and shows the tile line",
          "load('kbrain', './kalshi-brain.js'" in html and "brainDeps.kalshiBrain = kbI" in html and "within(ready.kbrain, 4000)" in html and "busy: () => state !== 'idle' || listening || speaking" in html.split("KALSHI-BRAIN")[1]
          and all(x in html for x in ("../kalshicity/edges.json", "../kalshicity/learning_log.json", "../kalshicity/learned.json")) and "kbI.line(k, Date.now())" in html)
    check("a. brain.js and modes.js carry their delimited KALSHI-BRAIN blocks (the option, the ask after the bots', the digest items; the Think-for-me items and the Business quick asks)",
          brain.count("KALSHI-BRAIN") >= 3 and "kb.answer(raw, q, V.f && V.f.kalshi, V.now)" in brain and "kalshiBrain: kb" in brain and "D.kalshiBrain" in modes and "How much should I bet?" in modes)
    check("a. the lead listed the new file in the shell worker (sw.js SHELL), so the offline copy is whole", "kalshi-brain" in rd(JV, "sw.js"))


def part_bcd(R):
    s = R["snap"]
    check("b. the real feed + engine snapshot: paused, $55.81, week -$3.30, mode live, the engine's do-more / stop lists and counts, the ruin band, the lessons",
          s["ok"] and s["paused"] and s["running"] is False and s["status"] == "Paused" and abs(s["balance"] - 55.8136) < 1e-6 and s["today"] == 0 and abs(s["week"] + 3.3) < 1e-9 and s["mode"] == "live" and s["live"]
          and s["doMore"] == R["engineDo"] and s["stop"] == R["engineStop"] and s["counts"]["doMore"] == R["engineCounts"]["do_more"] and s["counts"]["stop"] == R["engineCounts"]["stop"]
          and abs(s["ruin"] - R["engineRuin"]) < 1e-9 and s["band"] == "high" and s["lessons"] >= 1 and s["todayLessons"] >= 1 and s["hasLearned"] and s["trades"] == 40 and s["losses"] >= 1, s)
    check("b. the feed alone still gives the bot's numbers (no edges), the engine alone gives a not-live copy, nothing at all is not ok",
          R["feedOnly"]["ok"] and R["feedOnly"]["paused"] and R["feedOnly"]["counts"] is None and R["feedOnly"]["ruin"] is None and R["engineOnly"]["ok"] and not R["engineOnly"]["live"] and not R["none"]["ok"], (R["feedOnly"], R["engineOnly"]))
    d = R["d"]
    check("c. nothing at the first look, nothing from an unchanged feed, nothing from an engine-only copy, and nothing when the engine's files arrive after the first look (the old log is not new)", d["first"] == 0 and d["same"] == 0 and d["engineOnly"] == 0 and d["lateEngine"] == 0, d)
    check("c. paused and resumed: the bot going from running to paused, and back", d["paused"] == ["paused"] and d["resumed"] == ["resumed"], (d["paused"], d["resumed"]))
    check("c. the balance floor: crossing down says it ($50 floor, $41 to $55.81 is up so it is silent; a $70 to $55 drop under $60 speaks); above the floor is silent",
          d["floorNo"] == [] and d["floor"] == [] and R["sp"]["batch"]["events"].count("floor") == 1, (d["floor"], d["floorNo"]))
    check("c. a daily loss over 10% of the opening balance is flagged once (-$6.50 on $62.31 opening = 10.4%), not again while it stays over",
          [e["kind"] for e in d["dayloss"]] == ["dayloss"] and "10%" in d["dayloss"][0]["text"] and d["dayloss2"] == [], d["dayloss"])
    check("c. a big loss: a 98c favourite that lost $5.89 is an alert (priority 2.3, 'a 98c favourite lost'); a 60c loss, a $1 loss and a win are not",
          [e["kind"] for e in d["big"]] == ["bigloss"] and "98c favourite lost" in d["big"][0]["text"] and "98 cent favourite" in d["big"][0]["say"] and d["big"][0]["p"] < 2.7 and d["bigNo"] == [0, 0, 0], (d["big"], d["bigNo"]))
    check("c. a new DO MORE / STOP lesson in the learning log is one alert that names the first and counts the rest; the same lessons never twice",
          [e["kind"] for e in d["lesson"]] == ["lesson"] and "Kalshi learned something new" in d["lesson"][0]["text"] and "more lesson" in d["lesson"][0]["text"] and "Do more" in d["lesson"][0]["say"], d["lesson"])
    check("c. the risk of ruin moving: down from high is good news (ok), up from low is a warning", [(e["kind"], e["level"]) for e in d["ruinDown"]] == [("ruin", "ok")] and [(e["kind"], e["level"]) for e in d["ruinUp"]] == [("ruin", "warn")], (d["ruinDown"], d["ruinUp"]))
    sp = R["sp"]
    check("d. the first look says nothing; a pause while busy is queued and not said; when she is free it is said once, as plain words",
          sp["first"] == {"events": 0, "spoken": 0} and sp["busy"]["events"] == ["paused"] and sp["busy"]["spoken"] == 0 and sp["busy"]["reason"] == "busy" and sp["busy"]["queued"] == 1 and sp["said"]["n"] == 1 and "paused" in sp["said"]["text"].lower(), sp)
    check("d. 30 seconds between two alerts (the resume is held, then said), and a reload does not repeat an alert it has said", sp["gap"]["spoken"] == 0 and sp["gap"]["reason"] == "gap" and sp["afterGap"]["spoken"] == ["resumed"] and sp["reload"]["events"] == 0, sp)
    check("d. up to three events become one voice line (a pause-class batch: the floor and a 98c favourite lost together)", sp["batch"]["events"] == ["bigloss", "floor"] and sp["batch"]["spoken"] == 1 and "favourite" in sp["batch"]["text"] and "floor" in sp["batch"]["text"], sp["batch"])
    check("d. 8 an hour: with the hour full a calm lesson is logged but not said (hourly), and a pause still gets through", sp["hourly"]["lessonEvents"] == ["lesson"] and sp["hourly"]["lessonSpoken"] == 0 and sp["hourly"]["lessonReason"] == "hourly" and sp["hourly"]["pauseSpoken"] == ["paused"], sp["hourly"])
    check("d. hidden balances are masked in the spoken line; quiet hours say nothing (and drop the queue); the switch off says nothing; events are still logged",
          "$" not in sp["hidden"] and not re.search(r"\d+ dollars", sp["hidden"]) and sp["hidden"] != "" and sp["quiet"]["spoken"] == 0 and sp["quiet"]["reason"] == "quiet" and sp["off"] == {"spoken": 0, "settings": False} and sp["log"] >= 2 and sp["toasts"] >= 2, sp)


def part_e(R):
    a = R["ask"]
    ok_say = all((a[q]["speak"] or a[q]["say"]) for q in a)
    check("e. every reply has words to say (speak) and the replies are not empty", ok_say and all(a[q]["text"] for q in a), [q for q in a if not (a[q]["speak"] or a[q]["say"])])
    k = a["how is kalshi"]
    check("e. how is Kalshi: paused, $55.81, this week -$3.30, the weather, 1 to do more and 1 to stop, the risk of ruin; a Kalshi City card that opens kalshicity",
          k["intent"] == "kalshi_status" and "paused" in k["text"] and "$55.81" in k["text"] and "-$3.30" in k["text"] and "1 edge to do more, 1 to stop" in k["text"] and "chance of losing half" in k["text"]
          and k["cards"] and k["cards"][0]["open"] == "kalshicity" and "paused" in k["speak"].lower(), k)
    r = a["is the kalshi bot running"]
    check("e. is the Kalshi bot running: No, paused, with its status and how long ago; a running bot says Yes", r["intent"] == "kalshi_running" and r["text"].startswith("No: the Kalshi bot is paused") and "status: Paused" in r["text"]
          and R["askRun"]["text"].startswith(("Yes", "No")) and a["is kalshi paused"]["intent"] == "kalshi_running", (r["text"], R["askRun"]))
    st = a["what should I stop doing on kalshi"]
    check("e. what should I stop on Kalshi: the engine's proven STOP list (XRP, -$106.63 over 192 bets), the watch list, the research's negatives, and 'suggestion, your call'",
          st["intent"] == "kalshi_stop" and "XRP" in st["text"] and "$106.63" in st["text"] and "192 bets" in st["text"] and "Suggestion, your call" in st["text"] and "Suggestion, your call" in st["speak"] and "90-95c" in st["text"], st)
    b = a["what's my best kalshi edge"]
    check("e. my best Kalshi edge: the engine's DO MORE edge (95-97c, 715 bets), the quarter-Kelly stake, 'thin edge', suggestion, your call",
          b["intent"] == "kalshi_best" and "95-97c" in b["text"] and "715 bets" in b["text"] and "quarter-Kelly stake" in b["text"] and "Suggestion, your call" in b["text"] and "95-97c" in b["speak"], b)
    rk = a["what are the kalshi risks"]
    check("e. the Kalshi risks: the chance of losing half at the average bet (about 100%), the bot paused, the weather, the research's ruin table (1 / 3 / 6 contracts), one loss erases about 50 wins",
          rk["intent"] == "kalshi_risk" and "about 100%" in rk["text"] and "paused" in rk["text"] and "29%" in rk["text"] and "50 wins" in rk["text"] and "smaller bets" in rk["speak"], rk)
    bt = a["how much should I bet"]
    check("e. how much should I bet: always 'suggestion, your call', the bankroll, the average bet and its share, the research's ruin by size, the Kelly stake of the best edge, 1 to 3 contracts; never an order",
          bt["intent"] == "kalshi_size" and bt["text"].startswith("Suggestion, your call") and "$55.81" in bt["text"] and "19%" in bt["text"] and "1 to 3 contracts" in bt["text"] and "quarter-Kelly stake" in bt["text"] and "Suggestion, your call" in bt["speak"]
          and a["how much should i bet on kalshi"]["intent"] == "kalshi_size", bt)
    ln = a["what did kalshi learn today"]
    check("e. what did Kalshi learn today: the engine's lessons of its day, DO MORE / STOP first, in plain words, with the honest line that it measures the bot's own bets", ln["intent"] == "kalshi_learned" and "Learned:" in ln["text"] and "DO MORE" in ln["text"]
          and "measuring the bot's own bets" in ln["text"] and a["kalshi lessons"]["intent"] == "kalshi_learned", ln)
    al = R["askSet"]
    check("e. the alert switches: off, on, a balance floor of $30 (kept on the phone)", a["turn kalshi alerts off"]["intent"] == "kalshi_alerts" and "off" in a["turn kalshi alerts off"]["text"] and "on" in a["turn kalshi alerts on"]["text"]
          and a["kalshi alerts floor 30"]["text"].startswith("Done: I will tell you when Kalshi drops under $30") and al["on"] is True and al["floor"] == 30, (a["turn kalshi alerts off"], al))
    check("e. 'place a Kalshi order' is refused (no order tool exists), and the NQ bots' own questions are untouched (no kalshi intent)",
          not a["place a kalshi order"]["intent"].startswith("kalshi_") and not a["how are the bots"]["intent"].startswith("kalshi_") and not a["what's the plan"]["intent"].startswith("kalshi_"), (a["place a kalshi order"]["intent"], a["how are the bots"]["intent"]))
    check("e. no feed and no engine: she says she cannot see Kalshi and does not guess; while running the bot is 'running'; a daily loss shows in the risks",
          R["askNone"]["intent"] in ("kalshi", "kalshi_nodata") and ("Kalshi" in R["askNone"]["text"]) and "down" in R["askLoss"].lower(), (R["askNone"], R["askLoss"][:200]))
    check("e. nothing was fetched by the brain or the module (the shell loads the files, the module never does)", R["fetches"] == [], R["fetches"])


def part_f(R):
    it = R["items"]
    check("f. Think for me items (feed paused, ruin high, one stop, one best, lessons today): the pause first, then the bet size, what to stop, the best edge, what it learned; each an ask action",
          [x["key"] for x in it] == ["kalshi:paused", "kalshi:ruin", "kalshi:stop", "kalshi:best", "kalshi:learned"] and all(x["action"]["type"] == "ask" for x in it) and it[0]["p"] < it[1]["p"] < it[2]["p"] < it[3]["p"], it)
    th = R["think"]
    check("f. the modes' Think for me list carries them in Business mode with their asks and spoken words", len(th) == 5 and all(x["mode"] == "business" and x["action"] and x["say"] for x in th), th)
    q = R["quick"]
    check("f. Business mode's quick asks: how is Kalshi, best edge, what to stop, risks, how much to bet, what it learned (plus the rest as before)",
          all(x in q for x in ("How is Kalshi?", "What's my best Kalshi edge?", "What should I stop on Kalshi?", "Kalshi risks", "How much should I bet?", "What did Kalshi learn today?", "How close am I to my money goal?", "Plan for more accounts")), q)
    check("f. the Money tile line: the engine's counts and the ruin risk", R["line"] == "1 do more · 1 stop · ruin risk ~100%", R["line"])
    check("f. 'think for me' still answers through the brain", R["thinkAsk"]["intent"] is not None)


def part_browser():
    import copy
    import shutil
    import tempfile
    import time
    from tests import test_jarvis_hub as H
    tmp = tempfile.mkdtemp(prefix="le_jarvis_kalshi_web_")
    path = H.site(tmp, "A", "asis")
    srv = H.serve(tmp)
    base_dir = os.path.join(tmp, "A", "nq-dashboard")
    os.makedirs(os.path.join(base_dir, "kalshicity"), exist_ok=True)
    for f in ("edges.json", "learning_log.json", "learned.json"):
        shutil.copy(os.path.join(KC, f), os.path.join(base_dir, "kalshicity", f))
    url = f"http://127.0.0.1:{srv.server_address[1]}/" + path
    feed = json.loads(rd(FEED))
    now = int(time.time())
    running = {**copy.deepcopy(feed), "t": now - 60, "running": True, "status": "Running", "balance": 70.0}
    paused = {**copy.deepcopy(feed), "t": now - 30}
    kal = {"on": True, "j": running}
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            exe = next(iter(sorted(__import__("glob").glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
            br = pw.chromium.launch(**({"executable_path": exe} if exe else {}))
            ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1, service_workers="block")
            H.feeds(ctx, kal)
            ctx.add_init_script("try { sessionStorage.setItem('jarvis.booted', '1'); localStorage.setItem('jarvis.seen', JSON.stringify('j9')); } catch (e) {}")
            ctx.add_init_script(H.FAKE_VOICE)
            outside = []
            ctx.on("request", lambda r: not r.url.startswith(("http://127.0.0.1", "data:", "blob:", "https://api.github.com", "https://raw.githubusercontent.com", "https://api.coingecko.com")) and outside.append(r.url))
            p = ctx.new_page()
            errs = []
            p.on("pageerror", lambda e: errs.append(str(e)))
            p.goto(url + "jarvis/")
            H.ready(p, timeout=180000)
            p.wait_for_function("document.documentElement.dataset.kbrain === 'module' && document.documentElement.dataset.brain === 'module'", timeout=180000, polling=200)
            def ask(q):                    # typed into the real form (the fake voice hides nothing it needs)
                p.evaluate("document.getElementById('talk').innerHTML = ''")
                p.evaluate("(q) => { const i = document.getElementById('q'); i.value = q; document.getElementById('ask').requestSubmit(); }", q)
                p.wait_for_function("document.querySelectorAll('.msg.j').length > 0", timeout=30000)
                return p.locator(".msg.j").first.inner_text()
            t1 = ask("what should I stop doing on kalshi")
            check("g. Chromium, the real shell: 'what should I stop doing on Kalshi' is answered from the engine's files (XRP, suggestion, your call)", "XRP" in t1 and "Suggestion, your call" in t1, t1[:300])
            t2 = ask("how much should I bet")
            check("g. ...'how much should I bet' (a suggestion with the bankroll and the research's ruin table, never an order)", t2.startswith("Suggestion, your call") and "contracts" in t2, t2[:300])
            t3 = ask("what's my best kalshi edge")
            check("g. ...the best edge (95-97c)", "95-97c" in t3, t3[:300])
            # a pause on the next poll: spoken and toasted
            kal["j"] = {**paused, "t": int(time.time()) - 20, "balance": 70.0}
            p.evaluate("import('./data.js').then((D) => D.refreshKalshi())")
            p.wait_for_function("window.__said && window.__said.some((s) => /Kalshi bot just paused/.test(s[0]))", timeout=90000, polling=200)
            toast = p.evaluate("(document.getElementById('toast') || {}).textContent || ''")
            check("g. a pause on the next poll is said out loud ('The Kalshi bot just paused') and toasted", "paused" in toast.lower(), toast)
            kb = p.evaluate("JSON.parse(localStorage.getItem('jarvis.kalshi.log') || '[]').map((e) => e.kind)")
            check("g. the alert is logged on the phone (jarvis.kalshi.log) and the first look said nothing", "paused" in kb and "lesson" not in kb, kb)
            line = p.evaluate("(document.getElementById('kbLine') || {}).textContent || ''")
            check("g. the Kalshi tile on the Money cards carries the engine's line (1 do more · 1 stop · ruin risk ~100%)", "do more" in line and "stop" in line and "ruin risk" in line, line)
            check("g. no page errors, and nothing left the machine", not errs and not outside, (errs, outside[:3]))
            br.close()
    finally:
        srv.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    part_a()
    R = run_node()
    if R.get("error"):
        check("node runs the module, the brain and the modes", False, R["error"])
    else:
        part_bcd(R)
        part_e(R)
        part_f(R)
    if os.environ.get("JK_NO_BROWSER") != "1":
        part_browser()
    print(f"\n{sum(RES)}/{len(RES)} passed")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
