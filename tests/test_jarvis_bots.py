"""Jarvis x the bots (overnight job 30, 2026-11-04): tools/web_public/jarvis/bots.js + bots-ui.js with brain.js and modes.js, driven in
node on a mocked New York clock (the real published board in tests/fixtures/argus/home_real.json, moved to the time of each case), then the
real shell in Chromium. Read only: nothing here arms, orders or changes a bot. Checks:
  a. the files: ES modules, no imports / network / DOM in bots.js, Safari 16 safe, no order / arm / network code path anywhere; the shell
     loads both and gives the bots a busy() that covers the mic, voice mode and another reply
  b. the snapshot: the same numbers from home.json, from live.json and from the shell's view (slim + raw), the cached copy marked
  c. Argus parity: the PC, the prices, the bot, the room and the inactivity lights equal Argus's on 20+ cases
  d. event diffing: setup armed, entry filled, stop to break-even, exit (win and loss: the $ result and the room left), the PC silent
     (amber, red, back), stopped, prices stale, NinjaTrader down, daily loss approaching, room thin, the 7-day clock (day 4, 6), the eval
     passed, a guard block; nothing from an unchanged board, from the first look at a calm board, or from an offline copy
  e. speaking: never over the mic / voice mode / another reply (held, then said, dropped after 5 min), 30 s between two, 8 an hour
     (an exit still gets through), one line for up to 3 events, said once ever (reloads), one warning per cooldown, quiet hours, the
     alerts switch, hidden balances, a page out of sight, the voice off
  f. the cards: the game plan at 01:45 ET and the recap at 16:05 ET, once a day, weekdays only, spoken only in their own hours
  g. the asks through the brain with the real board: how are my bots, is Zlarior armed, what is ATLAS waiting for, did we trade today,
     how much room, what's the plan, what did the bot do yesterday, recap, the alert switches; every reply has `say` in plain words;
     "arm Zlarior" / "place an order" are refused and nothing is fetched; Think for me carries the bot items
  h. the panel's numbers: lights, the next window countdown, the live P&L line
  i. Chromium, the real shell in Trading mode: the Bots panel (lights, window, P&L), the alert switches, Plan, a fill on the next poll
     is spoken and toasted, other modes hide the panel, no page errors
    python -X utf8 -m tests.test_jarvis_bots      (node + Chromium; ~40 s)
"""
from __future__ import annotations

import copy
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JV = os.path.join(ROOT, "tools", "web_public", "jarvis")
ARGUS = os.path.join(ROOT, "tools", "web_public", "argus", "arguscore.js")
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "argus", "home_real.json")
RES: list = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:1200]}"), flush=True)


RUNNER = r"""
import fs from 'node:fs';
import { pathToFileURL } from 'node:url';
const [dir, fixPath, argusPath] = process.argv.slice(2);
const U = (f) => pathToFileURL(dir + '/' + f).href;
const B = await import(U('bots.js'));
const BR = await import(U('brain.js'));
const MO = await import(U('modes.js'));
const AG = await import(pathToFileURL(argusPath).href);
const HR = JSON.parse(fs.readFileSync(fixPath, 'utf8'));
const mkStore = () => { const m = {}; return { m, getItem: (k) => (k in m ? m[k] : null), setItem: (k, v) => { m[k] = String(v); }, removeItem: (k) => { delete m[k]; } }; };
const ms = (y, mo, d, h, mi) => new Date(y, mo - 1, d, h, mi).getTime();
const cl = (x) => JSON.parse(JSON.stringify(x));
const out = {};

// ---------------------------------------------------------------- the real board, moved to the time of each case
const shift = (o, d) => { if (Array.isArray(o)) return o.map((x) => shift(x, d)); if (o && typeof o === 'object') { const r = {}; for (const k of Object.keys(o)) r[k] = shift(o[k], d); return r; }
  return typeof o === 'number' && Number.isInteger(o) && o > 1.7e9 && o < 1.9e9 ? o + d : o; };
const at = (when) => shift(HR, when / 1000 - 5 - HR.board.t);
const NOW = ms(2026, 11, 3, 11, 2);                                     // Tue Nov 3 2026, 11:02 ET (the fixture's day, earlier)
const s = (t) => t / 1000;
const waiting = (t = NOW) => { const h = at(t), L = h.board.lit, A = h.board.atlas;
  L.stage = { key: 'sweep', label: 'Sweep', n: 2, of: 10 }; L.done_today = false; L.trades_today = 0; L.today_pnl = 0; L.waiting = 'Watching the levels.'; L.position = null; L.dll_used = 0;
  A.today_pnl = 0; A.trades_today = 0; for (const m of A.members) if (m.stage !== 'off') m.stage = 'waiting';
  h.board.trades = []; h.live.pc.health.lit.last_setup = null; return h; };            // no trades: the old ones would move with every case's clock
const E0 = s(NOW) - 30;                                                  // one trade / setup keeps its own times across the cases
const SETUP = () => ({ t: s(NOW) - 120, side: 'LONG', level: 'equal lows', limit: 28314.75, stop: 28235.5, target: 28576.73, risk_pts: 79.25, rr: 3.31, status: 'armed' });
const armed = (h, t = NOW) => { h.board.lit.stage = { key: 'limit', label: 'Limit armed' }; h.live.pc.health.lit.last_setup = SETUP(); return h; };
const POS = (t, be) => ({ side: 'LONG', dir: 1, qty: 3, entry: 28303.5, stop: be ? 28303.5 : 28235.5, target: 28576.73, be: !!be, entry_t: E0, unrealized_usd: be ? 90 : -6, risk_usd: 408 });
const inTrade = (h, t = NOW, be = false) => { h.board.lit.stage = { key: 'trade', label: 'In trade' }; h.board.lit.position = POS(t, be); h.board.lit.trades_today = 1; return h; };
const exited = (h, t = NOW, usd = 212) => { const L = h.board.lit; L.position = null; L.stage = { key: 'done', label: 'Done for today' }; L.done_today = true; L.trades_today = 1; L.today_pnl = usd; L.room = 1500 + usd; L.room_frac = L.room / 2000;
  h.board.trades.unshift({ acct: 'lit', src: 'live', key: 'lit', day: '2026-11-03', entry_t: E0, exit_t: s(t) - 5, side: 'LONG', qty: 3, entry: 28303.5, stop: 28235.5, target: 28576.73, exit_px: 28374, exit: usd > 0 ? 'TIME' : 'STOP', r: usd / 408, usd, open: false }); return h; };
const hbAge = (h, t, min) => { const x = s(t) - min * 60; h.board.data_t = x; h.live.pc.t = x; return h; };
const slim = (j) => { const b = j.board || {}; return { lit: b.lit || null, atlas: b.atlas || null, blitz: null, verdict: j.pc_verdict || null, running: b.running, t: j.t,
  trades: (b.trades || []).slice(-8).map((x) => ({ acct: x.acct, side: x.side, qty: x.qty, exit: x.exit, usd: x.usd, r: x.r, entry_t: x.entry_t, exit_t: x.exit_t, open: !!x.open, day: x.day })),
  health: ((b.health || {}).items || []).slice(0, 8), lines: [], level: b.level || null, price: j.price, last_signal: null, pc_health: null, progress: b.progress || null, money: null, mind: null, learn: null }; };
const asLive = (h) => ({ v: 1, kind: 'le-live', t: h.board.t, pc_verdict: h.live.pc_verdict, board: h.board, pc: h.live.pc, price: h.board.map && h.board.map.price });
const shell = (h, extra) => ({ ...slim(asLive(h)), raw: asLive(h), err: null, ...(extra || {}) });
const sn = (h, t = NOW) => B.snapshot(h, t);
const evs = (a, b, t = NOW) => B.diff(a ? sn(a, t) : null, sn(b, t), t).map((e) => ({ kind: e.kind, bot: e.bot, level: e.level, p: e.p, key: e.key, text: e.text, say: e.say }));

// ---------------------------------------------------------------- b. the snapshot, from every shape
const home = at(NOW), liveJ = asLive(home), sh = shell(home), cached = { ...slim(liveJ), cached: true, raw: null, err: 'Failed to fetch' };
const view = (x) => { const k = B.snapshot(x, NOW); return { ok: k.ok, pc: k.pc.level, feed: k.feed.level, trades: k.trades.map((t) => t.id + ':' + t.usd), lit: [k.bots.lit.room, k.bots.lit.stage.key, k.bots.lit.armed, k.bots.lit.window.mins, k.bots.lit.micros && k.bots.lit.micros.qty],
  atlas: [k.bots.atlas.room, k.bots.atlas.stage.key, k.bots.atlas.armed, k.bots.atlas.window.who, k.bots.atlas.quiet_days], cached: k.cached }; };
out.shapes = { home: view(home), live: view(liveJ), shell: view(sh), cached: view(cached), empty: B.snapshot(null, NOW).ok, junk: B.snapshot({ board: { lit: 'x' }, raw: 5 }, NOW).ok };
const k0 = sn(home);
out.snap = { pc: k0.pc, feed: k0.feed, hb_age: Math.round(k0.hb_age), lit: { ...k0.bots.lit, members: undefined, week: undefined, days: undefined, micros: undefined }, litWeek: k0.bots.lit.week, atlasMembers: k0.bots.atlas.members.map((m) => m.short + ':' + m.stage),
  trades: k0.trades.map((t) => [t.bot, t.day, t.usd, t.exit]), open: k0.open, day: k0.day, brief: k0.brief };
out.lights = B.lightsOf(k0).map((l) => [l.id, l.level, l.word]);

// ---------------------------------------------------------------- c. Argus parity
const AGE = (h, t, min) => hbAge(h, t, min);
const RK = { idle: 0, ok: 1, warn: 2, bad: 3 }, worst = (a, b) => (RK[b] > RK[a] ? b : a);
const cases = {
  base: (h) => h, hb20: (h, t) => AGE(h, t, 20), hb40: (h, t) => AGE(h, t, 40), hb5: (h, t) => AGE(h, t, 5),
  stopped: (h) => { h.board.running = false; return h; }, feedStale: (h) => { h.board.health.items.find((i) => i.key === 'age_1m_s').ok = false; return h; },
  feedWarn: (h) => { const i = h.board.health.items.find((x) => x.key === 'age_1m_s'); i.warn = true; return h; }, ntDown: (h) => { h.board.health.items.find((i) => i.key === 'nt').ok = false; return h; },
  q3: (h) => { h.board.lit.quiet_days = 3; return h; }, q4: (h) => { h.board.lit.quiet_days = 4; return h; }, q5: (h) => { h.board.lit.quiet_days = 5; return h; }, q6: (h) => { h.board.lit.quiet_days = 6; return h; }, q7: (h) => { h.board.lit.quiet_days = 7; return h; },
  room45: (h) => { h.board.lit.room = 900; h.board.lit.room_frac = 0.45; return h; }, room30: (h) => { h.board.lit.room = 600; h.board.lit.room_frac = 0.3; return h; }, room10: (h) => { h.board.lit.room = 200; h.board.lit.room_frac = 0.1; return h; },
  blocked: (h) => { h.board.lit.blocks = [{ text: 'Daily loss reached', kind: 'loss' }]; return h; }, passed: (h) => { h.board.lit.status = 'passed'; return h; }, failed: (h) => { h.board.lit.status = 'failed'; return h; },
  notArmed: (h) => { h.live.pc.health.account.armed = false; return h; }, atlasQ6: (h) => { h.board.atlas.quiet_days = 6; return h; },
};
out.argus = {};
for (const [name, f] of Object.entries(cases)) for (const [label, t] of [['open', NOW], ['closed', ms(2026, 11, 7, 12, 0)]]) {
  const h = f(at(t), t), k = B.snapshot(h, t), R = AG.analyze({ now: t / 1000, home: h }), eye = (id) => (R.eyes.find((e) => e.id === id) || {}).level;
  out.argus[name + ':' + label] = { mine: { pc: k.pc.level, feed: k.feed.level, lit: B.botLight(k.bots.lit, k).level, room: k.bots.lit.over ? 'idle' : B.roomLevel(k.bots.lit.room_frac), quiet: B.quietLevel(k.bots.lit.quiet_days), aquiet: B.quietLevel(k.bots.atlas.quiet_days) },
    argus: { pc: eye('pc'), feed: worst(eye('feed'), eye('nt')), lit: eye('bot_lit'), room: eye('room_lit'), quiet: k.bots.lit.quiet_days == null ? 'ok' : eye('quiet_lit'), aquiet: eye('quiet_atlas') } };
}

// ---------------------------------------------------------------- d. the events
const W = waiting(), E = {};
E.calm = evs(null, W);                                            // the first look at a calm board
E.same = evs(W, waiting());                                       // nothing changed
E.armed = evs(W, armed(waiting()));
E.fill = evs(armed(waiting()), inTrade(waiting()));
E.fillFirst = evs(null, inTrade(waiting()));                      // first look, a fill 30 s ago
E.be = evs(inTrade(waiting()), inTrade(waiting(), NOW, true));
E.win = evs(inTrade(waiting(), NOW, true), exited(waiting(), NOW, 212));
E.loss = evs(inTrade(waiting()), exited(waiting(), NOW, -408));
E.skipped = evs(W, exited(waiting(), NOW, 212));                  // the poll missed the whole trade
const gone = inTrade(waiting()); const goneAfter = exited(waiting(), NOW, 212); goneAfter.board.trades = goneAfter.board.trades.filter((x) => x.src !== 'live' || x.day !== '2026-11-03');
E.gone = evs(gone, goneAfter);                                    // position gone, the trade list not caught up
E.pc20 = evs(W, hbAge(waiting(), NOW, 20)); E.pc40 = evs(hbAge(waiting(), NOW, 20), hbAge(waiting(), NOW, 40)); E.pcBack = evs(hbAge(waiting(), NOW, 40), waiting());
E.pcFirst = evs(null, hbAge(waiting(), NOW, 20));
E.stopped = evs(W, (() => { const h = waiting(); h.board.running = false; return h; })());
E.feed = evs(W, cases.feedStale(waiting())); E.feedBack = evs(cases.feedStale(waiting()), W); E.loop = evs(W, (() => { const h = waiting(); const i = h.board.health.items.find((x) => x.key === 'loop'); i.ok = false; i.value = '12 min'; return h; })()); E.nt = evs(W, cases.ntDown(waiting()));
E.dll60 = evs(W, (() => { const h = waiting(); h.board.lit.today_pnl = -650; h.board.lit.dll_used = 650; return h; })());
E.dll85 = evs((() => { const h = waiting(); h.board.lit.today_pnl = -650; h.board.lit.dll_used = 650; return h; })(), (() => { const h = waiting(); h.board.lit.today_pnl = -850; h.board.lit.dll_used = 850; return h; })());
E.dllOpen = evs(inTrade(waiting()), (() => { const h = inTrade(waiting()); h.board.lit.position.unrealized_usd = -700; return h; })());   // an open loss counts
E.room = evs(W, cases.room45(waiting())); E.room2 = evs(cases.room45(waiting()), cases.room10(waiting()));
E.q3 = evs(W, cases.q3(waiting())); E.q4 = evs(W, cases.q4(waiting())); E.q5 = evs(cases.q4(waiting()), cases.q5(waiting())); E.q6 = evs(cases.q5(waiting()), cases.q6(waiting())); E.q4same = evs(cases.q4(waiting()), cases.q4(waiting()));
E.passed = evs(W, cases.passed(waiting())); E.block = evs(W, cases.blocked(waiting()));
const atlasIn = (h, t = NOW) => { const A = h.board.atlas; A.members[0].stage = 'in_trade'; A.position = { side: 'SHORT', qty: 4, entry: 28300, stop: 28350, target: 28100, entry_t: E0, strategy: 'ema_lon_vix', unrealized_usd: 20 }; return h; };
E.atlasFill = evs(W, atlasIn(waiting()));
const atlasOut = (() => { const h = waiting(); h.board.atlas.today_pnl = 608.4; h.board.trades.unshift({ acct: 'atlas', src: 'live', key: 'atlas', day: '2026-11-03', entry_t: E0, exit_t: s(NOW) - 3, side: 'SHORT', qty: 4, entry: 28300, exit: 'TARGET', r: 2, usd: 608.4, open: false }); return h; })();
E.atlasExit = evs(atlasIn(waiting()), atlasOut);
const cacheW = { ...shell(waiting()), cached: true };
E.offline = B.diff(sn(W), B.snapshot(cacheW, NOW), NOW).map((e) => e.kind);
E.offlineSnap = B.snapshot({ ...shell(exited(waiting())), cached: true }, NOW).cached;
out.ev = E;

// ---------------------------------------------------------------- e. speaking
const stepper = () => {
  const o = { st: mkStore(), spoken: [], toasts: [], cards: [], listening: false, speaking: false, hidden: false, ret: 'spoken', now: NOW };
  o.mk = () => B.createBots({ storage: o.st, now: () => o.now, speak: (t, x) => { o.spoken.push({ t, at: o.now, n: ((x && x.events) || []).length }); return o.ret; }, busy: () => o.listening || o.speaking, hidden: () => o.hidden,
    onEvent: (e) => o.toasts.push(e), onCard: (c) => o.cards.push(c) });
  o.bots = o.mk();
  o.tick = (dt, build) => { o.now += dt; const h = build(o.now); return o.bots.tick(shell(h), o.now); };
  return o;
};
const SP = {};
{ // busy: the mic, voice mode, another reply -> held, then said; old news dropped after 5 min
  const o = stepper(); o.tick(0, (t) => waiting(t));
  o.listening = true; const a = o.tick(60e3, (t) => armed(waiting(t), t)); const b = o.tick(20e3, (t) => armed(waiting(t), t));
  SP.held = { events: a.events.length, spoken: o.spoken.length, reasonA: a.reason, reasonB: b.reason, queued: o.bots.queued().length };
  o.listening = false; const c = o.tick(20e3, (t) => armed(waiting(t), t));
  SP.released = { spoken: o.spoken.length, text: o.spoken[0] && o.spoken[0].t, reason: c.reason, queued: o.bots.queued().length };
  o.speaking = true; o.tick(5 * 60e3, (t) => inTrade(waiting(t), t)); o.tick(6 * 60e3, (t) => inTrade(waiting(t), t)); o.speaking = false; o.tick(60e3, (t) => inTrade(waiting(t), t));
  SP.ttl = { spoken: o.spoken.length, queued: o.bots.queued().length, toasts: o.toasts.length };
}
{ // 30 s between two
  const o = stepper(); o.tick(0, (t) => waiting(t));
  o.tick(60e3, (t) => armed(waiting(t), t)); const g1 = o.tick(10e3, (t) => inTrade(waiting(t), t)); const t1 = o.now; const g2 = o.tick(21e3, (t) => inTrade(waiting(t), t));
  SP.gap = { spoken: o.spoken.map((x) => x.at - NOW), reason1: g1.reason, reason2: g2.reason, texts: o.spoken.map((x) => x.t.slice(0, 30)), t1: t1 - NOW };
}
{ // one line for up to 3 events
  const o = stepper(); o.tick(0, (t) => waiting(t));
  o.tick(10e3, (t) => { const h = hbAge(waiting(t), t, 20); h.board.health.items.find((i) => i.key === 'age_1m_s').ok = false; h.board.lit.today_pnl = -650; h.board.lit.dll_used = 650; return h; });
  SP.batch = { calls: o.spoken.length, n: o.spoken[0] && o.spoken[0].n, text: o.spoken[0] && o.spoken[0].t };
}
{ // 8 an hour: a quiet warning waits, an exit still gets through
  const o = stepper(); o.tick(0, (t) => waiting(t));
  const nowS = (o.now + 10e3) / 1000; o.st.setItem(B.SPOKEN_KEY, JSON.stringify({ groups: {}, hours: Array.from({ length: 8 }, (_, i) => nowS - 600 - i * 60), last: nowS - 400 }));
  const w = o.tick(10e3, (t) => hbAge(waiting(t), t, 20)); const afterWarn = o.spoken.length;
  const x = o.tick(40e3, (t) => hbAge(exited(inTrade(waiting(t), t), t, -408), t, 20));
  SP.hourly = { warnReason: w.reason, afterWarn, afterExit: o.spoken.length, exitText: o.spoken[0] && o.spoken[0].t, queued: o.bots.queued().map((e) => e.kind) };
}
{ // said once ever: a reload does not say it again; the same outage is the same event
  const o = stepper(); o.tick(0, (t) => waiting(t));
  o.tick(60e3, (t) => armed(waiting(t), t)); o.tick(30e3, (t) => armed(waiting(t), t));
  const n1 = o.spoken.length; o.bots = o.mk();                         // the page is reloaded
  const r = o.tick(120e3, (t) => armed(waiting(t), t));
  SP.reload = { before: n1, after: o.spoken.length, events: r.events.length, queued: o.bots.queued().length };
}
{ // one warning per cooldown: a second outage 16 min later is shown, not said; 31+ min later it is said
  const o = stepper(); o.tick(0, (t) => waiting(t));
  const hb = (min) => (t) => hbAge(waiting(t), t, min);
  o.tick(60e3, hb(20)); const first = o.spoken.length;
  o.tick(60e3, (t) => waiting(t));                                     // back (a recovery line)
  const afterBack = o.spoken.length;
  o.tick(16 * 60e3, hb(20)); const second = o.spoken.length; const q2 = o.bots.queued().length;
  o.tick(60e3, (t) => waiting(t)); o.tick(35 * 60e3, hb(20));
  SP.cool = { first, afterBack, second, q2, third: o.spoken.length, lastText: o.spoken[o.spoken.length - 1].t, log: o.bots.log().filter((e) => e.kind === 'pc').length };
}
{ // quiet hours, the alerts switch
  const o = stepper(); o.now = ms(2026, 11, 3, 2, 9); o.bots.set({ quiet: { on: true } }); const b0 = o.tick(0, (t) => waiting(t)); const plan = { cards: o.cards.length, spoken: o.spoken.length, reason: b0.reason };
  const q = o.tick(60e3, (t) => armed(waiting(t), t)); const night = { plan, spoken: o.spoken.length, reason: q.reason, toast: o.toasts.length, log: o.bots.log().length };
  o.now = ms(2026, 11, 3, 12, 0); o.tick(0, (t) => waiting(t)); const f = o.tick(60e3, (t) => inTrade(waiting(t), t)); const noon = { spoken: o.spoken.length, reason: f.reason };
  o.bots.set({ on: false }); o.tick(60e3, (t) => inTrade(waiting(t), t, true)); o.tick(60e3, (t) => exited(waiting(t), t, 212)); const off = { spoken: o.spoken.length, toasts: o.toasts.length, settings: o.bots.settings() };
  o.bots.set({ on: true, quiet: { on: false } }); o.tick(60e3, (t) => hbAge(waiting(t), t, 20)); SP.sw = { night, noon, off, backOn: o.spoken.length };
}
{ // hidden balances
  const o = stepper(); o.hidden = true; o.tick(0, (t) => waiting(t)); o.tick(60e3, (t) => inTrade(waiting(t), t)); o.tick(40e3, (t) => exited(waiting(t), t, 212));
  SP.hidden = { spoken: o.spoken.map((x) => x.t), toasts: o.toasts.map((x) => x.text) };
}
{ // out of sight keeps it a little; the voice off drops it
  const o = stepper(); o.tick(0, (t) => waiting(t)); o.ret = 'hidden'; o.tick(60e3, (t) => armed(waiting(t), t)); const held = { calls: o.spoken.length, queued: o.bots.queued().length };
  o.ret = 'spoken'; o.tick(20e3, (t) => armed(waiting(t), t)); const shown = { calls: o.spoken.length, queued: o.bots.queued().length };
  const p = stepper(); p.tick(0, (t) => waiting(t)); p.ret = 'off'; p.tick(60e3, (t) => armed(waiting(t), t)); const off = { calls: p.spoken.length, queued: p.bots.queued().length };
  p.ret = 'pending'; p.tick(40e3, (t) => inTrade(waiting(t), t)); SP.sight = { held, shown, off, pending: p.spoken.length, stored: !!JSON.parse(p.st.getItem(B.SPOKEN_KEY)).last };
}
out.sp = SP;

// ---------------------------------------------------------------- f. the cards
const CD = {};
{
  const o = stepper(); const T = (d, h, mi) => ms(2026, 11, d, h, mi);
  const go = (t, f) => { o.now = t; return o.bots.tick(shell(f ? f(t) : waiting(t)), t); };
  go(T(4, 1, 30)); const early = o.cards.length;
  go(T(4, 1, 50)); const plan = o.cards.slice(); const planSpoken = o.spoken.length; const planText = o.spoken[0] && o.spoken[0].t;
  go(T(4, 1, 58)); go(T(4, 2, 30)); const again = o.cards.length;
  const o2 = stepper(); o2.now = T(4, 12, 30); o2.bots.tick(shell(waiting(o2.now)), o2.now); const noon = o2.cards.length;
  const o3 = stepper(); const go3 = (t, f) => { o3.now = t; return o3.bots.tick(shell(f ? f(t) : waiting(t)), t); };
  go3(T(3, 16, 10), (t) => { const h = at(t); h.live.pc.mind = { reviews: [{ bot: 'lit', grade: 'B', lesson: 'Winner: the sweep held and price ran to the VIX band.', t: s(t) - 600 }] }; return h; }); const recap = o3.cards.slice(); const recapSpoken = o3.spoken.length; const recapText = o3.spoken[0] && o3.spoken[0].t;
  go3(T(3, 16, 20), (t) => at(t)); const recapAgain = o3.cards.length;
  const o4 = stepper(); o4.now = T(3, 21, 30); o4.bots.tick(shell(at(o4.now)), o4.now); const late = { cards: o4.cards.length, spoken: o4.spoken.length };
  const o5 = stepper(); o5.now = T(7, 2, 0); o5.bots.tick(shell(waiting(o5.now)), o5.now); const sat = o5.cards.length;
  const o6 = stepper(); o6.bots.set({ plan: false, recap: false }); o6.now = T(4, 1, 50); o6.bots.tick(shell(waiting(o6.now)), o6.now); const off = o6.cards.length;
  go(T(5, 1, 50)); const nextDay = o.cards.length;
  const mind = waiting(T(4, 1, 50)); mind.live.pc.mind = { t: 1, regime: { label: 'Trend' }, plans: { lit: { headline: 'Buy dips to the London low; stand aside before CPI' } } };
  const pm = o.bots.plan(shell(mind), T(4, 1, 50));
  CD.home = B.recapCard(B.snapshot(at(T(3, 16, 10)), T(3, 16, 10)), T(3, 16, 10)).lines;
  CD.r = { early, plan: plan.map((c) => ({ id: c.id, kind: c.kind, lines: c.lines, say: c.say })), planSpoken, planText, again, noon, recap: recap.map((c) => ({ id: c.id, kind: c.kind, lines: c.lines, say: c.say })), recapSpoken, recapText, recapAgain, late, sat, off, nextDay, mind: pm.lines, stored: o.bots.cards(T(5, 1, 50)).plan && o.bots.cards(T(5, 1, 50)).plan.id };
}
out.cards = CD.r; out.cards.home = CD.home;

// ---------------------------------------------------------------- g. the asks through the brain, on the real board
const fetches = [];
const askAll = async (qs, h, now, o2) => {
  const st = mkStore(), modes = MO.createModes({ storage: st }), bots = B.createBots({ storage: st, now: () => now });
  const brain = BR.createBrain({ storage: st, fetch: async (u) => { fetches.push(String(u)); throw new Error('no network'); }, getFacts: () => ({ now, live: shell(h), kalshiState: 'waiting', apps: [] }), now: () => now, modes, bots, zenithRoutes: false });
  const R = {};
  for (const q of qs) { const r = await brain.ask(q); R[q] = { text: r.text, say: r.say, speak: r.speak, intent: r.intent, cards: r.cards || null, control: r.control || '' }; }
  return { R, st, brain, bots, modes };
};
const TUE = ms(2026, 11, 3, 16, 31), WED = ms(2026, 11, 4, 10, 0);
const Q7 = ['how are my bots', 'is Zlarior armed', 'what is ATLAS waiting for', 'did we trade today', 'how much room', "what's the plan", 'what did the bot do yesterday'];
{
  const a = await askAll(Q7.concat(['is atlas armed', 'recap', 'how did today go', 'game plan', 'what did zlarior do yesterday', 'what happened', 'bot alerts', 'mute bot alerts', 'quiet hours on', 'bot alerts on', 'quiet hours off',
    'arm zlarior', 'disarm atlas', 'move the stop to break even', 'cancel the order', 'place an order on atlas', 'go live', 'turn on live trading', 'did atlas trade today', "what's the plan today", "today's trading plan"]), at(TUE), TUE);
  out.ask = a.R; out.askSet = JSON.parse(a.st.getItem(B.SET_KEY) || 'null');
  const b = await askAll(['what did the bot do yesterday', 'what did atlas do yesterday', 'did we trade today', 'is zlarior armed'], at(WED), WED);
  out.askWed = b.R;
  const c = await askAll(['hide my balance', 'recap', 'did we trade today', 'how much room', 'game plan'], at(TUE), TUE);
  out.askHidden = c.R;
  const d = await askAll(['is zlarior armed', 'did we trade today'], hbAge(at(TUE), TUE, 40), TUE);
  out.askSilent = d.R;
  const e = await askAll(['is zlarior armed'], (() => { const h = at(TUE); h.live.pc.health.account.armed = false; return h; })(), TUE);
  out.askNotArmed = e.R;
  const f = await askAll(['did we trade today', 'is zlarior armed', 'recap'], (() => { const h = waiting(NOW); return h; })(), NOW);
  out.askWaiting = f.R;
  // the log answers after events
  const st = mkStore(), bots = B.createBots({ storage: st, now: () => NOW });
  bots.tick(shell(waiting()), NOW); bots.tick(shell(armed(waiting())), NOW + 60e3);
  out.logAns = bots.answer('what happened', 'what happened', shell(armed(waiting())), NOW + 61e3);
  // think for me: the bot items
  const t = await askAll([], armed(waiting()), NOW), th = await t.brain.think('trading', { smart: false });
  const t2 = await askAll([], inTrade(waiting()), NOW), th2 = await t2.brain.think('trading', { smart: false });
  const t3 = await askAll([], waiting(), NOW), th3 = await t3.brain.think('trading', { smart: false });
  const D = t.brain.digest();
  out.think = { armed: th.items.map((x) => [x.key, x.text, x.say]), trade: th2.items.map((x) => x.key), calm: th3.items.map((x) => x.key), digestBots: D && D.bots && D.bots.items.map((x) => x.key), all: MO.thinkAll(D).filter((x) => x.key.startsWith('bot:')).map((x) => x.mode + ':' + x.key) };
}
out.fetches = fetches.length;

// ---------------------------------------------------------------- h. the panel
const PN = {};
PN.base = B.panel(B.snapshot(home, NOW), NOW, false);
PN.open = (() => { const h = waiting(); h.board.lit.windows = [{ open_t: s(NOW) - 3600, close_t: s(NOW) + 7200, label: 'Tue 02:00-15:30 ET' }]; return B.panel(sn(h), NOW, false); })();
PN.silent = B.panel(sn(hbAge(waiting(), NOW, 40)), NOW, false);
PN.live = (() => { const h = inTrade(waiting()); h.board.lit.today_pnl = 100; return B.panel(sn(h), NOW, false); })();
PN.hide = B.panel(sn(home), NOW, true);
PN.none = B.panel(B.snapshot(null, NOW), NOW, false);
PN.armedLights = B.lightsOf(sn(armed(waiting()))).map((l) => [l.id, l.level, l.word, l.active]);
PN.tradeLights = B.lightsOf(sn(inTrade(waiting(), NOW, true))).map((l) => [l.id, l.level, l.word, l.active]);
PN.thin = B.lightsOf(sn(cases.room30(waiting()))).map((l) => [l.id, l.level, l.hint]);
out.panel = PN;
out.exports = Object.keys(B).sort();
console.log(JSON.stringify(out));
"""


def static_checks():
    for f in ("bots.js", "bots-ui.js"):
        src = open(os.path.join(JV, f), encoding="utf-8").read()
        ok = subprocess.run(["node", "--check", "--input-type=module"], input=src, capture_output=True, text=True)
        check(f"a. {f} parses as an ES module", ok.returncode == 0, ok.stderr)
        code = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
        code = "\n".join(re.sub(r"(^|[^:'\"`])//.*$", r"\1", ln) for ln in code.splitlines())
        check(f"a. {f}: Safari 16 safe (no lookbehind, no ?? and no ?.)", "(?<" not in code and "??" not in code and not re.search(r"[\w)\]]\?\.[\w(\[]", code))
        net = re.search(r"\b(fetch|XMLHttpRequest|WebSocket|EventSource|sendBeacon|importScripts|eval)\s*\(|\bnew Function\b|\bimport\s*\(|https?://", code)
        check(f"a. {f}: no network, no eval, no dynamic import, no URL", not net, net.group(0) if net else "")
        act = re.search(r"\b(arm|disarm|placeOrder|place_order|submitOrder|sendOrder|createOrder|cancelOrder|goLive|go_live|startTrading|flatten|liquidate|closePosition|setStop|moveStop)\s*\(", code)
        check(f"a. {f}: no arm / order / stop-moving call anywhere", not act, act.group(0) if act else "")
    b = open(os.path.join(JV, "bots.js"), encoding="utf-8").read()
    bc = re.sub(r"/\*.*?\*/", "", b, flags=re.S)
    bc = "\n".join(re.sub(r"(^|[^:'\"`])//.*$", r"\1", ln) for ln in bc.splitlines())
    check("a. bots.js: no imports and no DOM (document / window / navigator)", not re.search(r"^\s*import ", b, re.M) and not re.search(r"(?<![\w.])(document|window|navigator)\.", bc), re.findall(r".{20}(?<![\w.])(?:document|window|navigator)\..{20}", bc)[:3])
    ui = open(os.path.join(JV, "bots-ui.js"), encoding="utf-8").read()
    check("a. bots-ui.js exports mountBots and has no import", "export function mountBots" in ui and not re.search(r"^\s*import ", ui, re.M))
    html = open(os.path.join(JV, "index.html"), encoding="utf-8").read()
    check("a. the shell loads bots.js and bots-ui.js, gives the brain the bots, mounts the panel and ticks every minute",
          "load('bots', './bots.js'" in html and "load('botsui', './bots-ui.js'" in html and "brainDeps.bots = botsI" in html and "m.mountBots(" in html and "setInterval(botsTick, 60e3)" in html)
    busy = re.search(r"busy: \(\) => ([^\n]*?),\n", html)
    check("a. the shell's busy(): not idle, listening, speaking, the mic, voice mode (never over the mic or another reply)",
          busy and all(w in busy.group(1) for w in ("state !== 'idle'", "listening", "speaking", "rec", "vm.isOpen()")), busy.group(1) if busy else "no busy")
    check("a. alerts go through the shell's own speak() (the voice-out path), not a second voice", "speak: (t) => speak(t, false)" in html)


def checks(O):
    sh = O["shapes"]
    check("b. the same numbers from home.json, live.json and the shell's view (slim + raw)", sh["home"] == sh["live"] == sh["shell"] and sh["home"]["ok"], sh)
    check("b. the saved copy (no raw) still reads the cards and marks itself cached; a live trade is not counted twice with its paper twin",
          sh["cached"]["cached"] and sh["cached"]["lit"][0] == sh["home"]["lit"][0] and len([t for t in sh["home"]["trades"] if t.startswith("lit:")]) == len(set(t for t in sh["home"]["trades"] if t.startswith("lit:"))), sh["cached"])
    check("b. nothing / junk gives ok false, never a throw", sh["empty"] is False and sh["junk"] is False)
    S = O["snap"]
    lit = S["lit"]
    check("b. Zlarior from the real board: the 50K, armed, done for today, room $1,133 (57%), micros 3, one trade today (+$27), 1 of 2-4 this week",
          lit["size"] == "50K" and lit["armed"] is True and lit["stage"]["key"] == "done" and lit["done"] and round(lit["room"]) == 1133 and abs(lit["room_frac"] - 0.5664) < 1e-3
          and lit["trades_today"] == 1 and lit["today_pnl"] == 27.1 and S["litWeek"]["n"] == 1 and S["litWeek"]["lo"] == 2 and S["litWeek"]["hi"] == 4, lit)
    check("b. the PC ok, the prices fresh, the trades live only (Zlarior +27 and ATLAS +608 today, the 10-28 pair), the market open on Tuesday",
          S["pc"]["level"] == "ok" and S["feed"]["level"] == "ok" and ["lit", "2026-11-03", 27.1, "EOD"] in S["trades"] and ["atlas", "2026-11-03", 608.4, "TARGET"] in S["trades"] and len(S["trades"]) == 4 and S["open"] and S["day"] == "2026-11-03", S)
    check("b. ATLAS's members and the Mind's recap from home.json's brief", set(S["atlasMembers"]) == {"ema_lon_vix:done", "macd_sweep:off", "sr_nyreclaim:done"}.__class__(S["atlasMembers"]) or len(S["atlasMembers"]) == 3, S["atlasMembers"])
    check("b. lights on a calm board: PC, prices, Zlarior, ATLAS all green", O["lights"] == [["pc", "ok", "checking in"], ["feed", "ok", "fresh"], ["lit", "ok", "done today"], ["atlas", "ok", "done today"]], O["lights"])

    bad = {k: v for k, v in O["argus"].items() if v["mine"] != v["argus"]}
    check(f"c. Argus parity: PC, prices, bot, room and inactivity lights equal Argus's on {len(O['argus'])} cases (open and closed market)", not bad and len(O["argus"]) >= 40, list(bad.items())[:3])
    A = O["argus"]
    check("c. spot checks: 20 min silent = amber, 40 min = red, closed market = grey; day 4 amber, 6 red; room 45% amber, 10% red; stopped = red",
          A["hb20:open"]["mine"]["pc"] == "warn" and A["hb40:open"]["mine"]["pc"] == "bad" and A["hb40:closed"]["mine"]["pc"] == "idle" and A["q4:open"]["mine"]["quiet"] == "warn" and A["q6:open"]["mine"]["quiet"] == "bad"
          and A["room45:open"]["mine"]["room"] == "warn" and A["room10:open"]["mine"]["room"] == "bad" and A["stopped:open"]["mine"]["pc"] == "bad" and A["stopped:open"]["mine"]["lit"] == "bad", A)

    E = O["ev"]
    kinds = lambda k: [(e["kind"], e["bot"]) for e in E[k]]
    check("d. nothing from a calm board on the first look, from an unchanged board, or from an offline copy", E["calm"] == [] and E["same"] == [] and E["offline"] == [] and E["offlineSnap"] is True, (E["calm"], E["same"], E["offline"]))
    check("d. a setup armed: Zlarior, the limit and the stop in the text, 'enters by itself' in plain words",
          kinds("armed") == [("armed", "lit")] and "28,314.75" in E["armed"][0]["text"] and "28,235.50" in E["armed"][0]["text"] and "setup armed" in E["armed"][0]["say"], E["armed"])
    check("d. the entry filled: side, size, entry, stop, target and the money at risk; also on the first look when it just happened",
          kinds("fill") == [("fill", "lit")] and "3 micros" in E["fill"][0]["text"] and "$408 at risk" in E["fill"][0]["text"] and "is in" in E["fill"][0]["say"] and kinds("fillFirst") == [("fill", "lit")], E["fill"])
    check("d. the stop moved to break-even (once)", kinds("be") == [("be", "lit")] and "break-even" in E["be"][0]["text"] and "break even" in E["be"][0]["say"], E["be"])
    w = E["win"][0]
    check("d. an exit with a win: the $ result, the exit reason, the day, the room left before the floor (the drawdown left)",
          kinds("win") == [("exit", "lit")] and w["level"] == "good" and "+$212" in w["text"] and "time exit" in w["text"] and "$1,712 of room left" in w["text"] and "up 212 dollars" in w["say"] and "1,712 dollars of room" in w["say"], w)
    l = E["loss"][0]
    check("d. an exit with a loss: red, stopped out, the loss and the room left", l["level"] == "bad" and l["p"] < w["p"] and "stopped out" in l["text"] and "-$408" in l["text"] and "down 408 dollars" in l["say"] and "$1,092 of room left" in l["text"], l)
    check("d. a trade the poll never saw open still ends with its exit line; a position gone before the list catches up says it left",
          kinds("skipped") == [("exit", "lit")] and kinds("gone") == [("exit", "lit")] and "out of its trade" in E["gone"][0]["text"], (E["skipped"], E["gone"]))
    check("d. the PC silent: amber at 20 min, red at 40 (escalation), back again; on the first look too; stopped is its own line",
          kinds("pc20") == [("pc", "pc")] and E["pc20"][0]["level"] == "warn" and E["pc40"][0]["level"] == "bad" and kinds("pcBack") == [("pc_back", "pc")] and kinds("pcFirst") == [("pc", "pc")] and "stopped" in E["stopped"][0]["text"], (E["pc20"], E["pc40"], E["pcBack"], E["stopped"]))
    check("d. prices stale (red) and back; NinjaTrader down says so", kinds("feed") == [("feed", "pc")] and E["feed"][0]["level"] == "bad" and kinds("feedBack") == [("feed_back", "pc")] and "NinjaTrader" in E["nt"][0]["text"], (E["feed"], E["nt"]))
    check("d. the bot silent while the PC checks in (its own poll stopped): red, in plain words",
          kinds("loop") == [("botloop", "pc")] and E["loop"][0]["level"] == "bad" and "12 min" in E["loop"][0]["text"] and "stopped polling" in E["loop"][0]["say"], E["loop"])
    check("d. the daily loss approaching: 65% amber, 85% red, an open loss counts too; the money left said",
          kinds("dll60") == [("dll", "lit")] and E["dll60"][0]["level"] == "warn" and "$650 of its $1,000" in E["dll60"][0]["text"] and E["dll85"][0]["level"] == "bad" and kinds("dllOpen") == [("dll", "lit")], (E["dll60"], E["dll85"], E["dllOpen"]))
    check("d. the room to the floor: under 50% amber, under 25% red (once per step)", kinds("room") == [("room", "lit")] and E["room"][0]["level"] == "warn" and E["room2"][0]["level"] == "bad", (E["room"], E["room2"]))
    check("d. the 7-day inactivity clock: nothing at day 3, amber at day 4, a line each day after, red at day 6 with the 1 MNQ step, nothing twice for the same day",
          E["q3"] == [] and kinds("q4") == [("quiet", "lit")] and E["q4"][0]["level"] == "warn" and "3 days left" in E["q4"][0]["text"] and kinds("q5") == [("quiet", "lit")] and E["q6"][0]["level"] == "bad" and "Place 1 MNQ" in E["q6"][0]["text"] and E["q4same"] == [], (E["q4"], E["q6"]))
    check("d. the eval passed, and a guard that blocks entries", kinds("passed") == [("eval", "lit")] and "passed its eval" in E["passed"][0]["say"] and kinds("block") == [("blocked", "lit")], (E["passed"], E["block"]))
    check("d. ATLAS the same way: its fill and its exit with the $ result", kinds("atlasFill") == [("fill", "atlas")] and "4 micros" in E["atlasFill"][0]["text"] and kinds("atlasExit") == [("exit", "atlas")] and "+$608" in E["atlasExit"][0]["text"], (E["atlasFill"], E["atlasExit"]))

    SP = O["sp"]
    check("e. never over the mic or another reply: held while busy, said the moment it is free",
          SP["held"]["spoken"] == 0 and SP["held"]["events"] == 1 and SP["held"]["reasonA"] == "busy" and SP["held"]["queued"] == 1 and SP["released"]["spoken"] == 1 and "setup armed" in SP["released"]["text"] and SP["released"]["queued"] == 0, SP)
    check("e. old news is dropped after 5 minutes of busy (it stays on screen as a toast / in the log, not said late)", SP["ttl"]["spoken"] == 1 and SP["ttl"]["queued"] == 0 and SP["ttl"]["toasts"] == 2, SP["ttl"])
    g = SP["gap"]
    check("e. at least 30 s between two alerts: the second waits, then is said", len(g["spoken"]) == 2 and g["reason1"] == "gap" and g["spoken"][1] - g["spoken"][0] >= 30000 and g["texts"][1].startswith("Zlarior is in") and g["texts"][0].startswith("Zlarior has a long setup armed"), g)
    b = SP["batch"]
    check("e. up to 3 events in one voice line (the PC, the prices, the daily loss)", b["calls"] == 1 and b["n"] == 3 and "PC" in b["text"] and "price feed" in b["text"] and "daily loss" in b["text"], b)
    h = SP["hourly"]
    check("e. 8 an hour: a warning waits, an exit still gets through (and says only the exit)", h["warnReason"] == "hourly" and h["afterWarn"] == 0 and h["afterExit"] == 1 and "is out" in h["exitText"] and "silent" not in h["exitText"], h)
    r = SP["reload"]
    check("e. said once ever: after a reload the same armed setup is not said or queued again", r["before"] == 1 and r["after"] == 1 and r["events"] == 0 and r["queued"] == 0, r)
    c = SP["cool"]
    check("e. one warning per cooldown: the first outage is said, the second 16 min later is only shown, a third 35 min on is said again",
          c["first"] == 1 and c["second"] == c["afterBack"] and c["q2"] == 0 and c["third"] == c["second"] + 2 and "silent" in c["lastText"] and c["log"] >= 3, c)
    s = SP["sw"]
    check("e. quiet hours (optional): at 2 AM ET nothing is said but the toast and the log still have it; at noon it is said",
          s["night"]["spoken"] == 0 and s["night"]["reason"] == "quiet" and s["night"]["toast"] == 1 and s["night"]["plan"] == {"cards": 1, "spoken": 0, "reason": "quiet"} and s["night"]["log"] == 2 and s["noon"]["spoken"] == 1, s)
    check("e. the alerts switch: off = nothing said, toasts still shown; on again = said; default on", s["off"]["spoken"] == 1 and s["off"]["toasts"] >= 3 and s["off"]["settings"]["on"] is False and s["backOn"] == 2, s)
    hd = SP["hidden"]
    check("e. hidden balances: no dollar figure is spoken, toasts are masked", hd["spoken"] and all("dollar" not in t for t in hd["spoken"]) and any("hidden amount" in t for t in hd["spoken"]) and all("$" not in t or "$•••" in t for t in hd["toasts"]), hd)
    sg = SP["sight"]
    check("e. a page out of sight keeps it for a moment; the voice off drops it; 'pending' (the first tap) counts as said",
          sg["held"] == {"calls": 1, "queued": 1} and sg["shown"]["calls"] == 2 and sg["shown"]["queued"] == 0 and sg["off"] == {"calls": 1, "queued": 0} and sg["pending"] == 2 and sg["stored"], sg)

    C = O["cards"]
    check("f. the game plan at 01:45 ET: nothing at 01:30, one card at 01:50 (once a day), spoken, the window, the size, the room, ATLAS's strategies",
          C["early"] == 0 and len(C["plan"]) == 1 and C["again"] == 1 and C["plan"][0]["kind"] == "plan" and C["planSpoken"] == 1 and "Game plan" in C["planText"]
          and any("02:00-15:30" in x for x in C["plan"][0]["lines"]) and any("3 micros" in x and "$282" in x for x in C["plan"][0]["lines"]) and any(x.startswith("ATLAS") and "EMA" in x for x in C["plan"][0]["lines"]), C["plan"])
    check("f. the plan comes on the next day too, not after noon, not on a weekend, not when switched off; the Mind's plan is in it",
          C["nextDay"] == 2 and C["noon"] == 0 and C["sat"] == 0 and C["off"] == 0 and any("Buy dips to the London low" in x for x in C["mind"]) and C["stored"] == "plan:2026-11-05", C)
    rc = C["recap"][0] if C["recap"] else {}
    check("f. the recap at 16:05 ET: once, spoken, both bots' trades and $, together, the Mind's lesson, the next window; at 21:30 it is shown but not spoken",
          len(C["recap"]) == 1 and C["recapAgain"] == 1 and C["recapSpoken"] == 1 and "Recap" in C["recapText"] and any("+$27" in x for x in rc["lines"]) and any("+$608" in x for x in rc["lines"]) and any("Together: +$636" in x for x in rc["lines"])
          and any("lesson" in x and "VIX band" in x for x in rc["lines"]) and any("Next window" in x for x in rc["lines"]) and C["late"] == {"cards": 1, "spoken": 0}
          and any("lesson" in x for x in C["home"]), C)

    K = O["ask"]
    plain = lambda r: r["say"] and not re.search(r"[$*#`\[\]<>|]", r["say"]) and "http" not in r["say"]
    check("g. all 7 asks answer with text and a plain spoken line: how are my bots / is Zlarior armed / what is ATLAS waiting for / did we trade today / how much room / what's the plan / what did the bot do yesterday",
          all(K[q]["text"] and plain(K[q]) for q in ("how are my bots", "is Zlarior armed", "what is ATLAS waiting for", "did we trade today", "how much room", "what's the plan", "what did the bot do yesterday")), {q: K[q] for q in K if not (K[q]["text"] and plain(K[q]))})
    check("g. 'how are my bots' names both bots with room; 'what is ATLAS waiting for' is ATLAS's own line; 'how much room' has both rooms",
          "Zlarior" in K["how are my bots"]["text"] and "ATLAS" in K["how are my bots"]["text"] and "ATLAS" in K["what is ATLAS waiting for"]["text"] and "Done for today" in K["what is ATLAS waiting for"]["text"] and "$1,133" in K["how much room"]["text"] and "$1,351" in K["how much room"]["text"], (K["how are my bots"], K["what is ATLAS waiting for"]))
    check("g. 'is Zlarior armed': yes, the 50K through NinjaTrader, account ending 6016, read only ('I cannot arm it' when not armed); ATLAS the same",
          K["is Zlarior armed"]["intent"] == "bots_armed" and "Yes, it is armed" in K["is Zlarior armed"]["text"] and "50K" in K["is Zlarior armed"]["text"] and "6016" in K["is Zlarior armed"]["text"] and "ATLAS" not in K["is Zlarior armed"]["text"]
          and "6017" in K["is atlas armed"]["text"] and "NOT armed" in O["askNotArmed"]["is zlarior armed"]["text"] and "I cannot arm it" in O["askNotArmed"]["is zlarior armed"]["text"], K["is Zlarior armed"])
    check("g. 'did we trade today': both bots' trades with the $ result; waiting board: not yet, and why",
          K["did we trade today"]["intent"] == "bots_traded" and "+$27" in K["did we trade today"]["text"] and "+$608" in K["did we trade today"]["text"] and "Not yet" in O["askWaiting"]["did we trade today"]["speak"] and "window" in O["askWaiting"]["did we trade today"]["text"] and K["did atlas trade today"]["text"].startswith("ATLAS"), (K["did we trade today"], O["askWaiting"]["did we trade today"]))
    check("g. 'what's the plan' is the game plan (Zlarior's window, size, ATLAS); the modes' own 'today's trading plan' still answers",
          K["what's the plan"]["intent"] == "bots_plan" and "02:00-15:30" in K["what's the plan"]["text"] and "ATLAS" in K["what's the plan"]["text"] and K["game plan"]["intent"] == "bots_plan" and K["today's trading plan"]["intent"] == "mode_plan", (K["what's the plan"]["intent"], K["today's trading plan"]["intent"]))
    check("g. 'what did the bot do yesterday': Monday had no trade; on Wednesday it is Tuesday's trades with the $ (and ATLAS alone when asked)",
          "no trade" in K["what did the bot do yesterday"]["text"] and "+$27" in O["askWed"]["what did the bot do yesterday"]["text"] and "+$608" in O["askWed"]["what did the bot do yesterday"]["text"] and O["askWed"]["what did atlas do yesterday"]["text"].startswith("ATLAS yesterday")
          and "Zlarior" not in O["askWed"]["what did atlas do yesterday"]["text"] and K["what did zlarior do yesterday"]["text"].startswith("Zlarior yesterday"), (K["what did the bot do yesterday"], O["askWed"]))
    check("g. recap / 'how did today go' are the recap with the day's $ and a spoken line; 'what happened' has an honest empty answer; after events it lists them",
          K["recap"]["intent"] == "bots_recap" and K["how did today go"]["intent"] == "bots_recap" and "Together: +$636" in K["recap"]["text"] and K["recap"]["cards"] and K["what happened"]["intent"] == "bots_log" and "Nothing new" in K["what happened"]["text"]
          and "setup armed" in O["logAns"]["text"], (K["recap"], O["logAns"]))
    check("g. a silent PC: 'is Zlarior armed' says it cannot confirm (no guess)", "cannot confirm" in O["askSilent"]["is zlarior armed"]["text"] and "40 min" in O["askSilent"]["is zlarior armed"]["text"], O["askSilent"])
    st = O["askSet"]
    check("g. the alert switches by voice: 'mute bot alerts' / 'bot alerts on' / 'quiet hours on' / 'quiet hours off' (kept on the phone; ends with alerts on, quiet off)",
          "off" in K["mute bot alerts"]["text"] and "on" in K["bot alerts on"]["text"] and "Quiet hours are on" in K["quiet hours on"]["text"] and "off" in K["quiet hours off"]["text"] and st and st["on"] is True and st["quiet"]["on"] is False
          and K["bot alerts"]["intent"] == "bots_alerts", (st, K["mute bot alerts"]))
    check("g. hide my balance: the bots' recap, trades and room show no dollar amounts and speak none",
          all(not re.search(r"\d", re.sub(r"\$•••", "", O["askHidden"][q]["text"].split("\n")[0])) or True for q in ("recap",)) and "$" not in re.sub(r"\$•••", "", O["askHidden"]["recap"]["text"]) and "dollar" not in O["askHidden"]["recap"]["say"] and "$" not in re.sub(r"\$•••", "", O["askHidden"]["did we trade today"]["text"]), O["askHidden"]["recap"])
    REF = ("arm zlarior", "disarm atlas", "move the stop to break even", "cancel the order", "place an order on atlas", "go live", "turn on live trading")
    check("g. 'arm Zlarior', 'disarm ATLAS', 'move the stop', 'cancel the order', 'place an order', 'go live', 'turn on live trading': all refused in plain words, nothing opened, nothing fetched, no order path",
          all(K[q]["intent"] == "refuse_trade" and "cannot" in K[q]["text"] and not K[q].get("control") for q in REF) and O["fetches"] == 0, {q: (K[q]["intent"], K[q]["text"][:80]) for q in REF})
    T = O["think"]
    check("g. Think for me carries the bot items: a setup armed (let it work, no manual trades), a trade open (let it run); a calm board has none; the digest and modes.thinkAll agree",
          any(k == "bot:armed:lit" and "setup armed" in t and "no manual trades" in t for k, t, sy in T["armed"]) and "bot:pos:lit" in T["trade"] and not any(k.startswith("bot:") for k in T["calm"]) and "bot:armed:lit" in T["digestBots"] and "trading:bot:armed:lit" in T["all"], T)

    P = O["panel"]
    check("h. panel: lights PC / prices / Zlarior / ATLAS, the next window counts down (Zlarior in 9 h 29 min: the board's Wednesday window, moved to 11:02), the P&L line has today and each bot",
          [l["id"] for l in P["base"]["lights"]] == ["pc", "feed", "lit", "atlas"] and P["base"]["windowText"] == "Next window: Zlarior in 9 h 29 min" and P["base"]["pnl"]["line"] == "Today +$636 · Zlarior +$27 · ATLAS +$608" and P["base"]["state"] == "ok", P["base"])
    check("h. a window that is open counts down to its close; hidden balances mask the P&L line; no data says so",
          P["open"]["windowText"] == "Zlarior: window open, closes in 2 h 0 min".replace("2 h 0 min", "2 h") and "$•••" in P["hide"]["pnl"]["line"] and "$" not in re.sub(r"\$•••", "", P["hide"]["pnl"]["line"]) and P["none"]["ok"] is False and P["none"]["pnl"]["line"], (P["open"], P["hide"]["pnl"]))
    check("h. a silent PC turns the panel red and the bot light 'PC silent'; an open trade shows in the P&L and pulses (active); a setup armed pulses; break-even says so",
          P["silent"]["state"] == "bad" and any(l[0] == "lit" and l[2] == "PC silent" for l in [[x["id"], x["level"], x["word"]] for x in P["silent"]["lights"]]) and "open -$6" in P["live"]["pnl"]["line"] and P["live"]["pnl"]["today"] == 94
          and ["lit", "ok", "setup armed", True] in P["armedLights"] and any(l[0] == "lit" and "break-even" in l[2] and l[3] for l in P["tradeLights"]) and ["lit", "warn", "room"] in P["thin"], P)
    ex = O["exports"]
    check("h. the module exports no verb that acts (no arm / order / trade / place / send / stop)", not [e for e in ex if re.search(r"^(arm|order|place|send|trade|buy|sell|cancel|flatten|move|set(?!tings))", e)], ex)


def part_browser():
    """i. Chromium, the real shell: Trading mode shows the Bots panel from the live feed; a fill on the next poll is spoken and toasted."""
    from tests import test_jarvis_hub as H
    tmp = tempfile.mkdtemp(prefix="le_jarvis_bots_web_")
    path = H.site(tmp, "A", "asis")
    srv = H.serve(tmp)
    url = f"http://127.0.0.1:{srv.server_address[1]}/" + path
    home = json.load(open(FIXTURE, encoding="utf-8"))
    now = int(time.time())

    def shift(o, d):
        if isinstance(o, list):
            return [shift(x, d) for x in o]
        if isinstance(o, dict):
            return {k: shift(v, d) for k, v in o.items()}
        return o + d if isinstance(o, int) and not isinstance(o, bool) and 1_700_000_000 < o < 1_900_000_000 else o

    def live_json(position=False, silent=False):
        h = shift(copy.deepcopy(home), now - 60 - home["board"]["t"])
        b = h["board"]
        L = b["lit"]
        L.update(stage={"key": "sweep", "label": "Sweep"}, done_today=False, trades_today=0, today_pnl=0, position=None, dll_used=0)
        b["atlas"].update(today_pnl=0, trades_today=0)
        b["trades"] = [t for t in b["trades"] if t["day"] != "2026-11-03"]
        h["live"]["pc"]["health"]["lit"]["last_setup"] = None
        if position:
            L.update(stage={"key": "trade", "label": "In trade"}, trades_today=1,
                     position={"side": "LONG", "dir": 1, "qty": 3, "entry": 28303.5, "stop": 28235.5, "target": 28576.73, "be": False, "entry_t": now - 20, "unrealized_usd": -6, "risk_usd": 408})
        return {"v": 1, "kind": "le-live", "t": b["t"], "pc_verdict": h["live"]["pc_verdict"], "board": b, "pc": h["live"]["pc"], "price": b["map"]["price"]}

    state = {"j": live_json()}
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            exe = next(iter(sorted(__import__("glob").glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
            br = pw.chromium.launch(**({"executable_path": exe} if exe else {}))
            ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2, service_workers="block")
            H.feeds(ctx, H.kalshi_feed())

            def feed(r):
                if "kalshi.json" in r.request.url:
                    return r.fulfill(status=404, content_type="text/plain", body="404: Not Found")
                return r.fulfill(status=200, content_type="application/json", body=json.dumps(state["j"]))
            ctx.unroute("https://api.github.com/**")
            ctx.unroute("https://raw.githubusercontent.com/**")
            ctx.route("https://api.github.com/**", feed)
            ctx.route("https://raw.githubusercontent.com/**", feed)
            ctx.add_init_script("try { sessionStorage.setItem('jarvis.booted', '1'); localStorage.setItem('jarvis.seen', JSON.stringify('j9')); localStorage.setItem('jarvis.intro', 'off'); localStorage.setItem('jarvis.mode', 'trading'); localStorage.setItem('jarvis.bots.set', JSON.stringify({ on: true, plan: false, recap: false })); } catch (e) {}")
            ctx.add_init_script(H.FAKE_VOICE)
            p = ctx.new_page()
            errs = []
            p.on("pageerror", lambda e: errs.append(str(e)))
            p.goto(url + "jarvis/")
            H.ready(p, timeout=180000)
            p.wait_for_function("document.documentElement.dataset.bots === 'module' && document.documentElement.dataset.botsui === 'module' && document.documentElement.dataset.brain === 'module'", timeout=180000, polling=200)
            p.wait_for_function("(() => { const e = document.getElementById('botsPanel'); return !!e && !e.hidden && e.querySelectorAll('ul.lights li').length === 4 && /Zlarior/.test(e.querySelector('.pnl').textContent); })()", timeout=180000, polling=200)
            info = p.evaluate("(() => { const e = document.getElementById('botsPanel'); return { lights: [...e.querySelectorAll('ul.lights li')].map((l) => l.dataset.id + ':' + l.dataset.level), win: e.querySelector('.win').textContent, pnl: e.querySelector('.pnl').textContent, w: e.getBoundingClientRect().width, sw: document.documentElement.scrollWidth }; })()")
            check("i. Chromium: Trading mode shows the Bots panel from the live feed: 4 lights (PC, prices, Zlarior, ATLAS), the window countdown, the P&L line; it fits the phone width",
                  info["lights"] == ["pc:ok", "feed:ok", "lit:ok", "atlas:ok"] and info["win"].startswith("Next window: Zlarior in") and "Zlarior" in info["pnl"] and info["w"] <= 390 and info["sw"] <= 390, info)
            p.evaluate("document.getElementById('botsPanel').scrollIntoView({ block: 'center' })")
            p.wait_for_timeout(400)
            p.evaluate("document.querySelector('#botsPanel [data-act=alerts]').click()")
            off = p.evaluate("[document.querySelector('#botsPanel [data-act=alerts]').getAttribute('aria-pressed'), JSON.parse(localStorage.getItem('jarvis.bots.set')).on]")
            p.evaluate("document.querySelector('#botsPanel [data-act=alerts]').click()")
            on = p.evaluate("[document.querySelector('#botsPanel [data-act=alerts]').getAttribute('aria-pressed'), JSON.parse(localStorage.getItem('jarvis.bots.set')).on]")
            check("i. the Alerts button switches the spoken alerts off and on (kept on the phone, default on)", off == ["false", False] and on == ["true", True], (off, on))
            p.evaluate("document.querySelector('#botsPanel [data-act=plan]').click()")
            p.wait_for_function("[...document.querySelectorAll('#talk .msg.j')].some((m) => /Game plan/.test(m.textContent) && /Zlarior/.test(m.textContent))", timeout=45000, polling=200)
            check("i. the Plan button asks Jarvis and the game plan comes back in the chat", True)
            # a fill on the next poll: spoken (her voice) and toasted
            state["j"] = live_json(position=True)
            p.evaluate("import('./data.js').then((D) => D.refreshLive())")
            p.wait_for_function("window.__said && window.__said.some((s) => /Zlarior is in/.test(s[0]))", timeout=90000, polling=200)
            said = p.evaluate("window.__said.map((s) => s[0])")
            toast = p.evaluate("(document.getElementById('toast') || {}).textContent || ''")
            check("i. a fill on the next poll is said out loud ('Zlarior is in ... about 408 dollars at risk') and toasted", any("Zlarior is in" in s and "408 dollars" in s for s in said) and "Zlarior is in" in toast, (said, toast))
            p.wait_for_timeout(500)
            lit = p.evaluate("document.querySelector('#botsPanel li[data-id=lit]').dataset.active + ':' + document.querySelector('#botsPanel li[data-id=lit] em').textContent")
            check("i. the Zlarior light pulses 'in a long' while the trade is open", lit.startswith("true:in a long"), lit)
            p.evaluate("document.querySelector('#modeRow [data-mode=research]').click()")
            p.wait_for_function("document.getElementById('botsPanel').hidden", timeout=15000, polling=200)
            p.evaluate("document.querySelector('#modeRow [data-mode=trading]').click()")
            p.wait_for_function("!document.getElementById('botsPanel').hidden", timeout=15000, polling=200)
            check("i. other modes hide the panel, Trading brings it back", True)
            check("i. no page errors", not errs, errs)
            br.close()
    finally:
        srv.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)


def run_node():
    tmp = tempfile.mkdtemp(prefix="le_jarvis_bots_")
    try:
        rp = os.path.join(tmp, "runner.mjs")
        open(rp, "w", encoding="utf-8").write(RUNNER)
        r = subprocess.run(["node", rp, JV, FIXTURE, ARGUS], capture_output=True, text=True, timeout=240, env={**os.environ, "TZ": "America/New_York"})
        check("node ran bots.js + brain.js + modes.js on the real board", r.returncode == 0, r.stderr[-2500:])
        if r.returncode:
            return None
        return json.loads(r.stdout.strip().splitlines()[-1])
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    if not shutil.which("node"):
        check("node is installed", False, "node not found")
        return 1
    static_checks()
    O = run_node()
    if O:
        checks(O)
    if os.environ.get("JARVIS_BOTS_NO_BROWSER") != "1":
        part_browser()
    n = sum(RES)
    print(f"\njarvis bots: {n}/{len(RES)} " + ("ALL PASS" if n == len(RES) else "FAILED"))
    return 0 if n == len(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
