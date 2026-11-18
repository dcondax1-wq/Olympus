// Jarvis "did we trade today" on the CME trading day (night-jfix 2026-11-18). The futures day runs 18:00 ET -> 17:00 ET the next
// calendar day, the same rule as engine/account_b.trading_day and engine/cme_calendar.trading_date: a 19:00 ET trade on Tuesday is
// Wednesday's. bots.js used the calendar date, so after 18:00 ET it missed the new session's trades (and counted a missing-day trade
// on the wrong day). Offline, node only, a mocked New York clock:
//   TZ=America/New_York node tests/test_jarvis_tradeday.mjs        (run by tests/test_jarvis_skills.py)
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const imp = (p) => import(pathToFileURL(path.join(ROOT, 'tools', 'web_public', p)).href);
global.window = {};
const B = await imp('jarvis/bots.js'), Z = await imp('jarvis/zeus.js');

let fails = 0, passes = 0;
const check = (name, ok, info) => { if (ok) passes++; else { fails++; console.log('FAIL ' + name + (info ? ' :: ' + String(info).slice(0, 500) : '')); } };
// an ET wall-clock moment -> ms (EST -5 in late November, EDT -4 in July)
const et = (ymd, hm, off = 5) => Date.parse(`${ymd}T${hm}:00Z`) + off * 3600e3;

// ------------------------------------------------------------------------------------------------ 1. the rule itself
{
  const C = [['2026-11-17', '09:30', '2026-11-17'], ['2026-11-17', '16:59', '2026-11-17'], ['2026-11-17', '17:30', '2026-11-17'],
    ['2026-11-17', '18:00', '2026-11-18'], ['2026-11-17', '19:05', '2026-11-18'], ['2026-11-17', '23:59', '2026-11-18'],
    ['2026-11-18', '00:10', '2026-11-18'], ['2026-11-22', '18:00', '2026-11-23'],                     // Sunday's open is Monday's session
    ['2026-11-30', '18:30', '2026-12-01'], ['2026-12-31', '19:00', '2027-01-01']];                    // month / year roll
  for (const [d, hm, want] of C) {
    const ms = et(d, hm);
    check(`bots.tradingDay ${d} ${hm}`, B.tradingDay(ms) === want, B.tradingDay(ms));
    check(`bots == zeus ${d} ${hm}`, B.tradingDay(ms) === Z.tradingDay(ms), Z.tradingDay(ms));
    check(`etOf keeps the calendar date ${d} ${hm}`, B.etOf(ms).ymd === d, B.etOf(ms).ymd);
  }
  check('summer (EDT) 18:00 rolls too', B.tradingDay(et('2026-07-14', '18:01', 4)) === '2026-07-15', B.tradingDay(et('2026-07-14', '18:01', 4)));
}

// ------------------------------------------------------------------------------------------------ 2. the asks on a Tuesday evening
const card = (extra) => ({ name: 'Zlarior', status: 'eval', badge: 'LIVE', armed: true, balance: 49200, today_pnl: 0, trades_today: 0, ...extra });
const src = (now, trades, lit) => ({ t: now / 1000 - 60, board: { t: now / 1000 - 60, data_t: now / 1000 - 60, running: true, lit: card(lit), atlas: null, trades } });
const T = (entryMs, exitMs, usd, day) => ({ acct: 'lit', src: 'live', side: 'LONG', qty: 2, entry: 21000, entry_t: entryMs / 1000, exit_t: exitMs / 1000, exit: usd > 0 ? 'TARGET' : 'STOP', usd, ...(day ? { day } : {}) });
const ask = (q, s, now) => B.answer(q, B.snapshot(s, now), now);
{
  // a trade at Tue 19:05 ET with the engine's day (Wed), asked at Tue 20:30 ET: yes
  const now = et('2026-11-17', '20:30');
  const eve = T(et('2026-11-17', '19:05'), et('2026-11-17', '19:40'), 412, '2026-11-18');
  const s1 = B.snapshot(src(now, [eve], { today_pnl: 412, trades_today: 1 }), now);
  check('snapshot day is the session (Wed)', s1.day === '2026-11-18', s1.day);
  const r1 = ask('did we trade today', src(now, [eve], { today_pnl: 412, trades_today: 1 }), now);
  check('19:05 trade counts "today" after 18:00', r1 && /yes, 1 trade this session/i.test(r1.text) && /\+\$412/.test(r1.text), r1 && r1.text);
  // the same trade without a day field (and the PC count missing): the trading day comes from its entry time
  const r2 = ask('did we trade today', src(now, [{ ...eve, day: undefined }], { today_pnl: 412, trades_today: 0 }), now);
  check('no day field -> day from entry_t', r2 && /yes, 1 trade/i.test(r2.text), r2 && r2.text);
  // a 10:00 ET Tuesday trade, asked at 20:30 ET: not this session, but it is named (the session that closed at 17:00)
  const morn = T(et('2026-11-17', '10:00'), et('2026-11-17', '10:45'), -230, '2026-11-17');
  const r3 = ask('did we trade today', src(now, [morn], { today_pnl: 0, trades_today: 0 }), now);
  check('after 18:00: not yet this session', r3 && /not yet this session/i.test(r3.text), r3 && r3.text);
  check('after 18:00: the closed session is named with its $', r3 && /closed at 17:00 ET/.test(r3.text) && /-\$230/.test(r3.text), r3 && r3.text);
  check('after 18:00: the voice says it too', r3 && /Earlier today it traded once/.test(r3.speak), r3 && r3.speak);
  // the same 10:00 trade asked at 15:00 ET: plain yes today
  const day = et('2026-11-17', '15:00');
  const r4 = ask('did we trade today', src(day, [morn], { today_pnl: -230, trades_today: 1 }), day);
  check('daytime: yes today', r4 && /yes, 1 trade today/i.test(r4.text), r4 && r4.text);
  // an evening trade (Mon 19:00 ET = Tue's session) asked Tue 15:00 ET: counts today, never as Monday's
  const monEve = T(et('2026-11-16', '19:00'), et('2026-11-16', '19:30'), 150);
  const r5 = ask('did we trade today', src(day, [monEve], { today_pnl: 150, trades_today: 0 }), day);
  check('Mon 19:00 trade is Tuesday\'s', r5 && /yes, 1 trade today/i.test(r5.text), r5 && r5.text);
  // the recap at 20:30 ET is about the new session, said so
  const rc = B.recapCard(B.snapshot(src(now, [eve], { today_pnl: 412, trades_today: 1 }), now), now);
  check('recap after 18:00 = this session', /So far this session/.test(rc.say) && rc.lines.some((l) => /\+\$412/.test(l)), rc.say + ' | ' + rc.lines.join(' | '));
  // revenge warning: two losses in the evening session are "today"
  const L1 = T(et('2026-11-17', '18:40'), et('2026-11-17', '18:55'), -200, '2026-11-18'), L2 = T(et('2026-11-17', '19:20'), et('2026-11-17', '19:35'), -180, '2026-11-18');
  const prev = B.snapshot(src(now - 600e3, [L1], { today_pnl: -200, trades_today: 1 }), now - 600e3), cur = B.snapshot(src(now, [L1, L2], { today_pnl: -380, trades_today: 2 }), now);
  const ev = B.diff(prev, cur, now);
  check('two evening losses = two losses today', ev.some((x) => /two losses today/.test(x.text || '')), JSON.stringify(ev.map((x) => x.text)));
}

console.log(`test_jarvis_tradeday: ${passes} passed, ${fails} failed`);
process.exit(fails ? 1 : 0);
