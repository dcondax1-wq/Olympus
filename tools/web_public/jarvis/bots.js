// Jarvis x the bots (owner 2026-11-04, overnight job 30): Jarvis knows and talks about the two live bots, Zlarior (LIT on the
// 50K) and ATLAS (on the 25K), from the data the site already publishes (live.json / home.json: board.lit, board.atlas,
// board.trades, board.health, the PC's heartbeat and its verdict). One ES module: no imports, no DOM, no network. READ ONLY:
// nothing here arms, orders, sizes or changes anything; it only reads a snapshot and says what it sees. iPhone Safari 16:
// plain ES2020 (no lookbehind, no optional chaining).
//
//   import { createBots } from './bots.js';
//   const bots = createBots({ storage?, speak(text) -> 'spoken'|'pending'|'off'|'hidden'|'none', busy() -> bool, hidden() -> bool,
//                             onEvent(ev), onCard(card) });
//   bots.tick(live, nowMs?)         every minute and on every live.json change: diff against the last snapshot (kept in
//                                   localStorage), queue the spoken alerts, build the 01:45 / 16:05 ET cards, flush the queue
//   bots.answer(raw, q, live, now)  the ask-anything answers (armed, did we trade today, yesterday, game plan, recap, alert
//                                   switches, what happened) -> { text, speak, intent, cards? } | null (not mine)
//   bots.panel(live, now)           the Bots panel: status lights, next window countdown, live P&L line, last events
//   bots.items(live, now)           the "Think for me" items (modes.js reads them from the brain's digest as D.bots.items)
//   bots.settings() / bots.set({ on, quiet: { on, from, to } })     alerts on by default; quiet hours optional (off)
//
// The pure parts (exported for the tests): snapshot(src, now) -> snap; diff(prev, cur, now) -> events; lightsOf(snap, now);
// planCard / recapCard(snap, now); answer(raw, snap, now). src is the shell's liveView() (cards at the top, the full live.json
// as .raw), live.json itself, or home.json (live.pc, board). The light rules are Argus's (tools/web_public/argus/arguscore.js):
// the PC checks in within 15 min (30 min = red while the market is open), the room to the floor under 50% amber and under 25%
// red, the MFFU 7-day inactivity clock amber from day 4 and red from day 6.
//
// Speaking (createBots.flush): never over the mic or another reply (busy()), at least 30 s between two alerts, at most 8 an
// hour (an exit, a fill or a red light always gets through), one event once ever (seen keys kept on the phone), one repeating
// warning once per cooldown, quiet hours (optional), stale news dropped after 5 minutes, and one voice line for up to 3 events.

export const SNAP_KEY = 'jarvis.bots.snap';          // the last snapshot (the next diff starts from it)
export const SEEN_KEY = 'jarvis.bots.seen';          // { event key: seconds }: said once, ever (pruned after 3 days)
export const SET_KEY = 'jarvis.bots.set';            // { on, quiet: { on, from, to }, plan, recap }
export const LOG_KEY = 'jarvis.bots.log';            // the last 30 events (the panel and "what happened")
export const CARD_KEY = 'jarvis.bots.cards';         // { day, plan, recap } the cards built today
export const SPOKEN_KEY = 'jarvis.bots.spoken';      // { group: seconds, hours: [seconds] } the speech rate limits survive a reload
export const INACTIVITY_DAYS = 7;
export const PC_OK_S = 15 * 60, PC_BAD_S = 30 * 60;  // Argus: the PC's heartbeat
export const MIN_GAP_S = 30, PER_HOUR = 8, TTL_S = 300, BATCH = 3;
export const PLAN_MIN = 105, RECAP_MIN = 16 * 60 + 5;                // 01:45 and 16:05 ET
const PLAN_SPEAK_UNTIL = 10 * 60, RECAP_SPEAK_UNTIL = 21 * 60, PLAN_BUILD_UNTIL = 12 * 60;      // spoken only while it is still the plan's / the recap's time

const isObj = (x) => !!x && typeof x === 'object' && !Array.isArray(x);
const arr = (x) => (Array.isArray(x) ? x : []);
const num = (v) => (typeof v === 'number' && Number.isFinite(v) ? v : typeof v === 'string' && v.trim() !== '' && Number.isFinite(+v) ? +v : null);
const str = (v, n) => (typeof v === 'string' ? v : typeof v === 'number' && Number.isFinite(v) ? String(v) : '').replace(/\s+/g, ' ').trim().slice(0, n || 300);
const good = (x) => (isObj(x) && !x.error ? x : null);
const plural = (n, w, p) => `${n} ${n === 1 ? w : p || w + 's'}`;
const lines = (...a) => a.filter((x) => x != null && x !== '').join('\n');

// ------------------------------------------------------------------------------------------------ money and words
export const usd = (v, sign) => { const x = num(v); if (x == null) return null; const a = Math.abs(Math.round(x)); return (sign && x > 0 && a ? '+' : x < 0 && a ? '-' : '') + '$' + a.toLocaleString('en-US'); };
const sayAmt = (v) => { const x = num(v); if (x == null) return null; const w = Math.abs(Math.round(x)); return `${w.toLocaleString('en-US')} dollar${w === 1 ? '' : 's'}`; };
const saySigned = (v) => { const x = num(v); if (x == null) return null; if (Math.abs(x) < 0.5) return 'flat'; return (x > 0 ? 'up ' : 'down ') + sayAmt(x); };
const px = (v) => { const x = num(v); return x == null ? '' : x.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }); };
const px0 = (v) => { const x = num(v); return x == null ? '' : Math.round(x).toLocaleString('en-US'); };
export function dur(mins) {
  const m = Math.max(0, Math.round(num(mins) || 0));
  if (m < 1) return 'under a minute';
  if (m < 60) return `${m} min`;
  const h = Math.floor(m / 60), r = m % 60;
  if (h >= 48) return `${Math.round(h / 24)} days`;
  return `${h} h${r ? ` ${r} min` : ''}`;
}
const durSay = (mins) => { const m = Math.max(0, Math.round(num(mins) || 0)); if (m < 1) return 'under a minute'; if (m < 60) return plural(m, 'minute'); const h = Math.floor(m / 60), r = m % 60; return plural(h, 'hour') + (r ? ' ' + plural(r, 'minute') : ''); };
const ageText = (s) => { s = Math.max(0, Math.round(s)); return s < 90 ? `${s} sec` : s < 5400 ? `${Math.round(s / 60)} min` : s < 172800 ? `${(s / 3600).toFixed(1).replace(/\.0$/, '')} hours` : `${Math.round(s / 86400)} days`; };
const clockSay = (min) => { const h = Math.floor(min / 60) % 24, m = min % 60, h12 = ((h + 11) % 12) + 1; return `${h12}${m ? ':' + String(m).padStart(2, '0') : ''} ${h < 12 ? 'AM' : 'PM'}`; };
// "02:00-15:30 ET" -> "2 AM to 3:30 PM"; "02:00-05:00, 09:30-11:00 ET" -> "2 AM to 5 AM and 9:30 AM to 11 AM"
const hoursSay = (s) => {
  const parts = String(s || '').replace(/\bET\b/g, '').split(',').map((x) => x.trim()).filter(Boolean), out = [];
  for (const p of parts) { const m = /^(\d{1,2}):(\d\d)\s*-\s*(\d{1,2}):(\d\d)$/.exec(p); if (m) out.push(`${clockSay(+m[1] * 60 + +m[2])} to ${clockSay(+m[3] * 60 + +m[4])}`); }
  return out.join(' and ');
};

// ------------------------------------------------------------------------------------------------ the New York clock
const ETF = new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', hourCycle: 'h23', year: 'numeric', month: 'numeric', day: 'numeric', hour: 'numeric', minute: 'numeric', weekday: 'short' });
const WDI = { Sun: 0, Mon: 1, Tue: 2, Wed: 3, Thu: 4, Fri: 5, Sat: 6 };
const WDL = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
const p2 = (n) => String(n).padStart(2, '0');
export function etOf(ms) {
  const p = {};
  for (const x of ETF.formatToParts(new Date(ms))) p[x.type] = x.value;
  const y = +p.year, mo = +p.month, d = +p.day, h = +p.hour % 24, m = +p.minute;
  return { y, mo, d, h, m, min: h * 60 + m, wd: WDI[p.weekday], dn: Math.round(Date.UTC(y, mo - 1, d) / 864e5), ymd: `${y}-${p2(mo)}-${p2(d)}` };
}
const ymdOfDn = (dn) => { const x = new Date(dn * 864e5); return `${x.getUTCFullYear()}-${p2(x.getUTCMonth() + 1)}-${p2(x.getUTCDate())}`; };
/** CME NQ: Sunday 18:00 to Friday 17:00 ET, a halt 17:00-18:00 (exchange holidays are not known here; Argus has the same rule) */
export function marketOpen(ms) {
  const e = etOf(ms);
  if (e.wd === 6) return false;
  if (e.wd === 0) return e.min >= 1080;
  if (e.wd === 5) return e.min < 1020;
  return e.min < 1020 || e.min >= 1080;
}
const prevTradingDn = (dn) => { let d = dn - 1; for (let i = 0; i < 7; i++) { const w = new Date(d * 864e5).getUTCDay(); if (w >= 1 && w <= 5) return d; d--; } return dn - 1; };

// ------------------------------------------------------------------------------------------------ the bots
export const BOTS = [
  { key: 'lit', name: 'Zlarior', size: '50K', rx: /\b(zlarior|z larior|zolarior|zularior|zlario|solarior|lit|the 50 ?k|50k)\b/ },
  { key: 'atlas', name: 'ATLAS', size: '25K', rx: /\b(atlas|at las)\b/ },
];
const BOT = { lit: BOTS[0], atlas: BOTS[1] };
const EXIT_WORD = { TIME: 'a time exit', EOD: 'an end-of-day exit', STOP: 'stopped out', SL: 'stopped out', TARGET: 'the target', TP: 'the target', BE: 'a break-even exit', T15: 'the 15-minute check', CHECK: 'the 15-minute check', FLAT: 'flat at the close' };
const exitWord = (x) => EXIT_WORD[String(x || '').toUpperCase()] || (str(x, 20) ? str(x, 20).toLowerCase() + ' exit' : 'an exit');

// ------------------------------------------------------------------------------------------------ the snapshot
function beOf(p) {
  if (!p) return false;
  if (p.be === true) return true;
  const e = num(p.entry), s = num(p.stop), long = /long|buy/i.test(str(p.side, 10)) || p.dir === 1;
  if (e == null || s == null) return false;
  return long ? s >= e : s <= e;
}
function stageOf(key, c) {
  if (key === 'lit') {
    const st = isObj(c.stage) ? c.stage : {};
    return { key: str(st.key, 20) || (c.done_today ? 'done' : ''), label: str(st.label, 40) };
  }
  const ms = arr(c.members).filter((m) => isObj(m) && m.stage && m.stage !== 'off' && m.stage !== 'error');
  if (ms.some((m) => /trade/i.test(m.stage))) return { key: 'trade', label: 'In trade' };
  if (ms.some((m) => /armed|limit|pending|setup/i.test(m.stage))) return { key: 'limit', label: 'Setup armed' };
  if (ms.length && ms.every((m) => m.stage === 'done')) return { key: 'done', label: 'Done for today' };
  return { key: ms.length ? 'waiting' : 'off', label: ms.length ? 'Waiting' : 'Outside hours' };
}
/** the next entry window from the bot's list (relative to now, so a snapshot a few minutes old still counts down right) */
export function windowOf(key, c, now) {
  const wins = [];
  if (key === 'lit') for (const w of arr(c.windows)) if (isObj(w)) wins.push({ ...w, who: 'Zlarior' });
  if (key !== 'lit') for (const m of arr(c.members)) if (isObj(m) && m.stage !== 'error') for (const w of arr(m.windows)) if (isObj(w)) wins.push({ ...w, who: str(m.short, 12) });
  const live = wins.filter((w) => num(w.close_t) != null && num(w.open_t) != null).sort((a, b) => a.open_t - b.open_t);
  const open = live.filter((w) => w.open_t * 1000 <= now && w.close_t * 1000 > now)[0];
  if (open) return { open: true, who: open.who, open_t: open.open_t, close_t: open.close_t, mins: Math.max(0, Math.round((open.close_t * 1000 - now) / 60e3)), label: str(open.label, 40) };
  const nxt = live.filter((w) => w.open_t * 1000 > now)[0];
  if (nxt) return { open: false, who: nxt.who, open_t: nxt.open_t, close_t: nxt.close_t, mins: Math.max(0, Math.round((nxt.open_t * 1000 - now) / 60e3)), label: str(nxt.label, 40) };
  const w0 = isObj(c.window) ? c.window : {};
  return { open: !!w0.open, who: BOT[key].name, open_t: num(w0.open_t), close_t: num(w0.close_t), mins: null, label: str(w0.text, 80) };
}
const sizeIn = (plan) => { const m = /(\d+)\s*k\b/i.exec(str(plan, 40)); return m ? m[1] + 'K' : ''; };
function botOf(key, c, ctx) {
  const bot = BOT[key], now = ctx.now;
  const status = str(c.status, 20).toLowerCase();
  const pos0 = isObj(c.position) ? c.position : null;
  const position = pos0 ? { side: str(pos0.side, 10).toUpperCase() || (pos0.dir === -1 ? 'SHORT' : 'LONG'), qty: num(pos0.qty), entry: num(pos0.entry), stop: num(pos0.stop), target: num(pos0.target),
    entry_t: num(pos0.entry_t), be: beOf(pos0), unreal: num(pos0.unrealized_usd), risk_usd: num(pos0.risk_usd) } : null;
  const stage = stageOf(key, c);
  const armed_setup = !position && (stage.key === 'limit' || stage.key === 'cisd1m');
  const ls = ctx.lastSetup && key === 'lit' ? ctx.lastSetup : null;
  const setupOpen = ls && !/filled|expired|done|cancel/i.test(str(ls.status, 20));
  const mll = num(c.mll), room = num(c.room), rf = num(c.room_frac) != null ? num(c.room_frac) : room != null && mll ? Math.max(0, Math.min(1, room / mll)) : null;
  const today = num(c.today_pnl), dll = num(c.dll);
  let used = num(c.dll_used);                                   // the card's own count is the booked loss today; an open loss counts too (MFFU's limit is on equity)
  if (used == null && today != null) used = Math.max(0, -today);
  if (position && position.unreal != null && position.unreal < 0) used = (used || 0) - position.unreal;
  const over = /passed|failed|lost|not set up/.test(status);
  const blocks = arr(c.blocks).filter(isObj).map((b) => ({ text: str(b.text, 160), kind: str(b.kind, 20), fix: str(b.fix, 160) }));
  const armedAcct = key === 'lit' ? (ctx.account && typeof ctx.account.armed === 'boolean' ? ctx.account.armed : null)
    : (str(c.badge, 10).toUpperCase() === 'LIVE' && c.configured !== false && !blocks.some((b) => b.kind === 'account') ? true : c.configured === false ? false : null);
  return {
    key, name: bot.name, size: sizeIn(c.plan) || bot.size, plan: str(c.plan, 40), broker: str(c.broker, 30), badge: str(c.badge, 10),
    status, over, armed: armedAcct, stage, armed_setup, setup: armed_setup && setupOpen ? { side: str(ls.side, 10), limit: num(ls.limit), stop: num(ls.stop), target: num(ls.target), risk_pts: num(ls.risk_pts), t: num(ls.t) } : null,
    setup_id: armed_setup ? String((setupOpen && num(ls.t)) || ctx.day + ':' + (num(c.trades_today) || 0)) : '',
    position, trades_today: num(c.trades_today) || 0, max_day: num(c.max_day), today_pnl: today, week_pnl: num(c.week_pnl),
    room, room_frac: rf, floor: num(c.floor), mll, dll, dll_used: used, to_target: num(c.to_target), balance: num(c.balance), session: num(c.session),
    quiet_days: num(c.quiet_days), blocks, waiting: str(c.waiting, 260), window: windowOf(key, c, now), done: stage.key === 'done' || c.done_today === true,
    micros: isObj(c.micros) ? { qty: num(c.micros.qty), risk_usd: num(c.micros.risk_usd), win_usd: num(c.micros.win_usd), risk_pts: num(c.micros.risk_pts), tgt_pts: num(c.micros.tgt_pts), what: str(c.micros.what, 160) } : null,
    hours: key === 'lit' ? str(isObj(c.window) ? c.window.hours : '', 60) : arr(c.members).filter((m) => isObj(m) && m.stage !== 'off' && m.hours).map((m) => `${str(m.short, 8)} ${str(m.hours, 40)}`).join('; '),
    members: arr(c.members).filter(isObj).map((m) => ({ short: str(m.short, 10), stage: str(m.stage, 16), text: str(m.text, 120), hours: str(m.hours, 40) })),
  };
}
const tradeId = (key, t) => `${key}:${num(t.entry_t) || ''}`;
/** Everything the bots' voice needs from one reading of the feed. snap.ok = false when there is nothing to read. */
export function snapshot(src, nowMs) {
  const now = num(nowMs) != null ? num(nowMs) : Date.now();
  const s = isObj(src) ? src : {};
  const full = isObj(s.raw) ? s.raw : s;
  const liveB = isObj(full.live) ? full.live : {};
  const board = good(full.board) || {};
  const pc = isObj(full.pc) ? full.pc : isObj(liveB.pc) ? liveB.pc : {};
  const verdict = good(full.pc_verdict) || good(liveB.pc_verdict) || good(s.verdict) || null;
  const cards = { lit: good(board.lit) || good(s.lit), atlas: good(board.atlas) || good(s.atlas) };
  const out = { ok: false, now, cached: !!s.cached, t: null, hb_t: null, hb_age: null, open: marketOpen(now), day: etOf(now).ymd, pc: null, feed: null, bots: {}, trades: [], plan: '', brief: null };
  if (!cards.lit && !cards.atlas) return out;
  out.ok = true;
  out.t = num(full.t) || num(s.t) || num(board.t) || (typeof full.built === 'string' && Number.isFinite(Date.parse(full.built)) ? Date.parse(full.built) / 1000 : null);
  const hbT = num(board.data_t) || (pc.present !== false && num(pc.t)) || out.t;
  out.hb_t = hbT || null;
  out.hb_age = hbT ? Math.max(0, now / 1000 - hbT) : null;
  const running = board.running != null ? board.running : s.running != null ? s.running : pc.running;
  const health = isObj(pc.health) ? pc.health : {};
  const items = {};
  for (const it of arr(isObj(board.health) ? board.health.items : null).length ? arr(board.health.items) : arr(s.health)) if (isObj(it) && it.key) items[it.key] = it;
  const lvOf = (it) => (!it ? 'idle' : it.ok === false ? 'bad' : it.warn ? 'warn' : it.ok ? 'ok' : 'idle');
  // the PC (Argus pcEye): fresh within 15 min is green; a silent PC is amber, then red after 30 min while the market is open
  let pcLevel, pcWord, pcText;
  if (!hbT) { pcLevel = 'warn'; pcWord = 'no report'; pcText = 'No check-in time from the PC.'; }
  else if (running === false) { pcLevel = 'bad'; pcWord = 'stopped'; pcText = 'The PC is on but the bot is stopped.'; }
  else if (out.hb_age < PC_OK_S) { pcLevel = 'ok'; pcWord = 'checking in'; pcText = `Last check-in ${ageText(out.hb_age)} ago.`; }
  else if (!out.open) { pcLevel = 'idle'; pcWord = 'quiet'; pcText = `No check-in for ${ageText(out.hb_age)}. Fine while the market is closed.`; }
  else { pcLevel = out.hb_age > PC_BAD_S ? 'bad' : 'warn'; pcWord = `silent ${ageText(out.hb_age)}`; pcText = `No check-in from the PC for ${ageText(out.hb_age)}.`; }
  out.pc = { level: pcLevel, word: pcWord, text: pcText, running: running == null ? null : !!running, adapter: str(pc.adapter, 20), verdict: verdict ? { code: str(verdict.code, 20), label: str(verdict.label, 60), level: str(verdict.level, 10), reason: str(verdict.reason, 160) } : null };
  const feedIt = items.age_1m_s || items.age_5m_s, nt = items.nt;
  const feedLevel = !out.open ? 'idle' : !feedIt ? 'idle' : lvOf(feedIt);
  const ntLevel = !nt || (!out.open && nt.ok === false) ? 'idle' : lvOf(nt);               // Argus: a NinjaTrader that is off is fine while the market is closed
  out.feed = { level: feedLevel === 'idle' && ntLevel !== 'idle' ? ntLevel : (feedLevel === 'bad' || ntLevel === 'bad') ? 'bad' : (feedLevel === 'warn' || ntLevel === 'warn') ? 'warn' : feedLevel,
    word: feedLevel === 'bad' ? 'stale' : ntLevel === 'bad' ? 'NinjaTrader down' : feedLevel === 'ok' ? 'fresh' : feedLevel === 'idle' ? (out.open ? 'no reading' : 'market closed') : 'slow',
    text: str(feedLevel === 'bad' || feedLevel === 'warn' ? feedIt && feedIt.detail : ntLevel === 'bad' || ntLevel === 'warn' ? nt && nt.detail : feedIt && feedIt.detail, 160),
    nt_down: ntLevel === 'bad' };
  const lp = items.loop;                                   // "Last poll": the bot's own loop; the PC can check in while the bot has stopped polling
  out.loop = { level: !out.open ? 'idle' : lvOf(lp), value: lp ? str(lp.value, 20) : '' };
  const lastSetup = isObj(health.lit) && isObj(health.lit.last_setup) ? health.lit.last_setup : null;
  const ctx = { now, day: out.day, account: isObj(health.account) ? health.account : null, lastSetup };
  for (const k of ['lit', 'atlas']) if (cards[k]) out.bots[k] = botOf(k, cards[k], ctx);
  // the trades: the live ones for a LIVE card (the paper twin has the same entry time and would count twice)
  const all = arr(board.trades).length ? arr(board.trades) : arr(s.trades);
  for (const t of all) {
    if (!isObj(t)) continue;
    const key = /atlas|second|_b\b|\bb$/i.test(str(t.acct, 30)) ? 'atlas' : /blitz|_c\b|\bc$/i.test(str(t.acct, 30)) ? 'blitz' : 'lit';
    const b = out.bots[key];
    if (!b) continue;
    const src2 = str(t.src, 10);
    if (src2 && b.badge === 'LIVE' && src2 !== 'live') continue;
    const id = tradeId(key, t);
    if (out.trades.some((x) => x.id === id)) continue;
    out.trades.push({ id, bot: key, day: str(t.day, 10), entry_t: num(t.entry_t), exit_t: num(t.exit_t), side: str(t.side, 10).toUpperCase(), qty: num(t.qty), entry: num(t.entry),
      usd: num(t.usd), r: num(t.r), exit: str(t.exit, 20), open: !!t.open, strategy: str(t.strategy || t.src_key, 20) });
  }
  const mind = isObj(pc.mind) ? pc.mind : isObj(s.mind) ? s.mind : null;
  const plans = mind && isObj(mind.plans) ? mind.plans : {};
  out.plan = str((isObj(plans.lit) ? plans.lit.headline : '') || (Object.values(plans).find((p) => isObj(p) && str(p.headline, 200)) || {}).headline, 200);
  out.reviews = arr(mind && mind.reviews).filter(isObj).map((r) => ({ bot: str(r.bot, 12), grade: str(r.grade, 4), lesson: str(r.lesson, 240), t: num(r.t) })).filter((r) => r.lesson);
  const brief = isObj(liveB.brief) ? liveB.brief : null;
  out.brief = brief ? { recap: isObj(brief.recap) ? { day: str(brief.recap.day, 10), text: str(brief.recap.text, 240), lesson: str(brief.recap.lesson, 240), setups: str(brief.recap.setups, 240) } : null,
    prev: isObj(brief.prev) && isObj(brief.prev.recap) ? { day: str(brief.prev.day, 10), pnl: num(brief.prev.recap.pnl), text: str(brief.prev.recap.text, 240), n: arr(brief.prev.recap.trades).length } : null } : null;
  const prog = isObj(board.progress) ? board.progress : isObj(s.progress) ? s.progress : {};
  for (const k of ['lit', 'atlas']) {
    const b = out.bots[k], w = isObj(prog[k]) && isObj(prog[k].week) ? prog[k].week : null;
    if (b && w) b.week = { n: num(w.n), lo: num(w.lo), hi: num(w.hi), usd: num(w.usd), days: arr(w.days).filter(isObj).map((d) => ({ day: str(d.day, 10), n: num(d.n), usd: num(d.usd) })) };
    if (b && cards[k] && Array.isArray(cards[k].days)) b.days = cards[k].days.filter((d) => Array.isArray(d)).map((d) => ({ day: str(d[0], 10), usd: num(d[1]) }));
  }
  return out;
}

// ------------------------------------------------------------------------------------------------ the lights (Argus's rules)
export const roomLevel = (rf) => (rf == null ? 'idle' : rf < 0.25 ? 'bad' : rf < 0.5 ? 'warn' : 'ok');
export const dllLevel = (used, dll) => { if (used == null || !dll) return 'ok'; const f = used / dll; return f >= 0.8 ? 'bad' : f >= 0.6 ? 'warn' : 'ok'; };
export const quietLevel = (q) => (q == null ? 'ok' : q >= 6 ? 'bad' : q >= 4 ? 'warn' : 'ok');
const RANK = { ok: 0, idle: 0, warn: 1, bad: 2 };
/** one bot's light: { level, word, active } (active = a setup armed or a trade open: the light pulses) */
export function botLight(b, snap) {
  if (!b) return { level: 'idle', word: 'no data', active: false };
  const no = (level, word) => ({ level, word, active: false });
  if (b.status === 'not set up') return no('idle', 'not set up');
  if (/passed/.test(b.status)) return no('ok', 'eval passed');
  if (/failed|lost/.test(b.status)) return no('bad', 'eval ended');
  if (b.blocks.length) return no('bad', 'blocked');
  if (snap.pc && snap.pc.running === false) return no('bad', 'stopped');
  if (snap.pc && snap.pc.level === 'bad') return no('bad', 'PC silent');
  if (snap.pc && snap.pc.level === 'idle' && !snap.open) return no('idle', 'resting');
  if (snap.pc && snap.pc.level === 'warn') return no('warn', 'unsure');
  if (b.armed === false) return no('warn', 'not armed');
  if (b.position) return { level: 'ok', word: `in a ${b.position.side.toLowerCase()}${b.position.be ? ', stop at break-even' : ''}`, active: true };
  if (b.armed_setup) return { level: 'ok', word: 'setup armed', active: true };
  if (b.done) return no('ok', 'done today');
  return no('ok', b.window.open ? 'watching' : 'waiting for its window');
}
export function lightsOf(snap) {
  if (!snap || !snap.ok) return [];
  const out = [{ id: 'pc', label: 'PC', level: snap.pc.level, word: snap.pc.word, active: false }, { id: 'feed', label: 'Prices', level: snap.feed.level, word: snap.feed.word, active: false }];
  for (const k of ['lit', 'atlas']) { const b = snap.bots[k]; if (b) { const l = botLight(b, snap); const rl = roomLevel(b.over ? null : b.room_frac), ql = quietLevel(b.over ? null : b.quiet_days), dl = dllLevel(b.dll_used, b.dll);
    const worst = [l.level, rl, ql, dl].reduce((a, x) => (RANK[x] > RANK[a] ? x : a), 'ok');
    out.push({ id: k, label: b.name, level: l.level === 'idle' ? 'idle' : worst, word: l.word, active: l.active, hint: worst !== l.level ? (rl === worst ? 'room' : ql === worst ? 'inactive' : 'daily loss') : '' }); } }
  return out;
}

// ------------------------------------------------------------------------------------------------ the events (diff of two snapshots)
const EV = (kind, bot, level, p, key, text, say, extra) => Object.assign({ kind, bot, level, p, key, group: kind + ':' + bot, cool: 0, text, say: say || text }, extra || {});
function tradeLine(t) { return `${t.side ? t.side.toLowerCase() + ' ' : ''}${t.qty ? plural(t.qty, 'micro') + ', ' : ''}${exitWord(t.exit)}, ${usd(t.usd, true) || '$?'}${t.r != null ? ` (${t.r > 0 ? '+' : ''}${t.r.toFixed(1)}R)` : ''}`; }
/** The events between two snapshots. prev = null (the first look): only the things that are true now and not yet said. */
export function diff(prev, cur, now) {
  if (!cur || !cur.ok) return [];
  const out = [], nowS = (num(now) != null ? num(now) : cur.now) / 1000;
  const offline = !!cur.cached;
  const P = prev && prev.ok ? prev : null;
  // --- the PC and the prices: only a live reading speaks (a phone that lost its signal says nothing about the PC)
  if (!offline) {
    const pl = cur.pc.level, ol = P ? P.pc.level : 'ok';
    if ((pl === 'warn' || pl === 'bad') && (!P || RANK[pl] > RANK[ol] || ol === 'ok' || ol === 'idle')) {
      const stopped = cur.pc.running === false, key = `pc:${stopped ? 'stopped' : pl}:${Math.round(cur.hb_t || 0)}`;
      out.push(EV('pc', 'pc', pl, pl === 'bad' ? 2 : 3.2, key, stopped ? 'The bot is stopped on the PC. Open the Start page on the PC and press Start trading.' : `The PC has been silent for ${ageText(cur.hb_age)}: the bots cannot trade until it checks in. Check it is on, awake and online.`,
        stopped ? 'The bot is stopped on the PC.' : `The PC has been silent for ${ageText(cur.hb_age)}. The bots cannot trade until it checks in.`, { cool: 1800 }));
    } else if (P && (ol === 'warn' || ol === 'bad') && pl === 'ok') out.push(EV('pc_back', 'pc', 'good', 6, `pcback:${Math.round(cur.hb_t || 0)}`, 'The PC is checking in again.', 'The PC is checking in again.', { cool: 900 }));
    const fl = cur.feed.level, fo = P ? P.feed.level : 'ok';
    if ((fl === 'bad' || fl === 'warn') && (!P || RANK[fl] > RANK[fo] || fo === 'ok' || fo === 'idle')) {
      out.push(EV('feed', 'pc', fl, fl === 'bad' ? 2.4 : 3.6, `feed:${fl}:${Math.floor(cur.now / 3600e3)}`, cur.feed.nt_down ? 'NinjaTrader is disconnected: no new entries until it is back.' : `The price feed is ${fl === 'bad' ? 'stale' : 'slow'}${cur.feed.text ? ' (' + cur.feed.text + ')' : ''}: the bots hold new entries until it is fresh.`,
        cur.feed.nt_down ? 'NinjaTrader is disconnected. No new entries until it is back.' : `The price feed is ${fl === 'bad' ? 'stale' : 'slow'}. The bots hold new entries until it is fresh.`, { cool: 1800 }));
    } else if (P && (fo === 'bad' || fo === 'warn') && fl === 'ok') out.push(EV('feed_back', 'pc', 'good', 6.2, `feedback:${Math.floor(cur.now / 3600e3)}`, 'The price feed is fresh again.', 'The price feed is fresh again.', { cool: 900 }));
  }
  if (!offline && cur.pc.level === 'ok') {                      // the PC is checking in but the bot itself has stopped polling the market
    const ll = cur.loop ? cur.loop.level : 'idle', lo = P && P.loop ? P.loop.level : 'ok';
    if ((ll === 'bad' || ll === 'warn') && (!P || RANK[ll] > RANK[lo] || lo === 'ok' || lo === 'idle'))
      out.push(EV('botloop', 'pc', ll, ll === 'bad' ? 2.1 : 3.3, `loop:${ll}:${Math.floor(cur.now / 3600e3)}`, `The bot is not polling the market (last poll ${cur.loop.value || 'a while ago'}): the PC is on, but the bot is not watching. Open the bot window on the PC.`,
        'The bot has stopped polling the market. The PC is on, but the bot is not watching.', { cool: 1800 }));
  }
  for (const k of ['lit', 'atlas']) {
    const b = cur.bots[k], a = P ? P.bots[k] : null;
    if (!b) continue;
    const nm = b.name;
    // --- a setup armed
    if (b.armed_setup && !(a && a.armed_setup && a.setup_id === b.setup_id) && P && !offline) {
      const su = b.setup, side = su && su.side ? su.side.toLowerCase() : '';
      out.push(EV('armed', k, 'info', 2.5, `armed:${k}:${b.setup_id}`, `${nm} has ${side ? 'a ' + side : 'a'} setup armed${su && su.limit ? `: limit ${px(su.limit)}, stop ${px(su.stop)}` : ''}. It waits for price to tap the limit and confirm, then enters by itself. No manual trades now.`,
        `${nm} has ${side ? 'a ' + side : 'a'} setup armed${su && su.limit ? `. Limit at ${px0(su.limit)}${su.risk_pts ? `, stop ${Math.round(su.risk_pts)} points away` : ''}` : ''}. It enters by itself if price confirms.`));
    }
    // --- the entry filled (a fill seen live, or one from the last 10 minutes when this is the first look)
    const p = b.position;
    if (p && !(a && a.position && a.position.entry_t === p.entry_t) && (P || (p.entry_t && nowS - p.entry_t < 600)) && !offline) {
      const risk = p.risk_usd != null ? p.risk_usd : p.qty && p.entry != null && p.stop != null ? Math.abs(p.entry - p.stop) * 2 * p.qty : null;
      out.push(EV('fill', k, 'info', 1.8, `fill:${k}:${p.entry_t || b.setup_id || Math.floor(cur.now / 60e3)}`,
        `${nm} is in: ${p.side.toLowerCase()}${p.qty ? ' ' + plural(p.qty, 'micro') : ''}${p.entry != null ? ' at ' + px(p.entry) : ''}${p.stop != null ? `, stop ${px(p.stop)}` : ''}${p.target != null ? `, target ${px(p.target)}` : ''}${risk != null ? `. About ${usd(risk)} at risk` : ''}.`,
        `${nm} is in. ${p.side[0] + p.side.slice(1).toLowerCase()}${p.qty ? ', ' + plural(p.qty, 'micro') : ''}${p.entry != null && p.stop != null ? `, stop ${Math.round(Math.abs(p.entry - p.stop))} points away` : ''}${risk != null ? `, about ${sayAmt(risk)} at risk` : ''}.`));
    }
    // --- the stop moved to break-even
    if (p && p.be && a && a.position && a.position.entry_t === p.entry_t && !a.position.be && !offline) {
      out.push(EV('be', k, 'good', 2.2, `be:${k}:${p.entry_t}`, `${nm} moved its stop to break-even${p.stop != null ? ' (' + px(p.stop) + ')' : ''}. This trade should not lose money now, costs aside.`,
        `${nm} moved its stop to break even. This trade should not lose money now.`));
    }
    // --- the exit: a trade that closed since the last look (its result, and the drawdown left)
    const prevClosed = new Set(P ? P.trades.filter((t) => !t.open && t.exit_t).map((t) => t.id) : []);
    const closed = cur.trades.filter((t) => t.bot === k && !t.open && t.exit_t && !prevClosed.has(t.id) && (P || nowS - t.exit_t < 1200));
    for (const t of closed) {
      if (offline) break;
      const left = b.room != null ? ` You have ${usd(b.room)} of room left before the floor${b.mll ? ` (of ${usd(b.mll)})` : ''}.` : '';
      const leftSay = b.room != null ? ` You have ${sayAmt(b.room)} of room left before the floor.` : '';
      const day = b.today_pnl != null ? ` Day ${usd(b.today_pnl, true)}.` : '';
      out.push(EV('exit', k, t.usd == null ? 'info' : t.usd > 0 ? 'good' : t.usd < 0 ? 'bad' : 'info', t.usd != null && t.usd < 0 ? 1.5 : 1.7, `exit:${k}:${t.entry_t}`, `${nm} is out: ${tradeLine(t)}.${day}${left}`,
        `${nm} is out. ${t.side ? t.side[0] + t.side.slice(1).toLowerCase() + ' ' : ''}trade, ${exitWord(t.exit)}${t.usd != null ? ', ' + (saySigned(t.usd) || '') : ''}.${leftSay}`));
    }
    if (!closed.length && a && a.position && !p && !offline && !cur.trades.some((t) => t.bot === k && t.entry_t === a.position.entry_t)) {       // gone, and the trade list has not caught up
      out.push(EV('exit', k, 'info', 1.9, `exit:${k}:${a.position.entry_t}`, `${nm} is out of its trade.${b.today_pnl != null ? ` Day ${usd(b.today_pnl, true)}.` : ''}${b.room != null ? ` Room left ${usd(b.room)}.` : ''}`,
        `${nm} is out of its trade.${b.today_pnl != null ? ' The day is ' + saySigned(b.today_pnl) + '.' : ''}`));
    }
    // --- the eval passed or ended
    if (a && a.status !== b.status && /passed|failed|lost/.test(b.status)) {
      const pass = /passed/.test(b.status);
      out.push(EV('eval', k, pass ? 'good' : 'bad', 1.2, `eval:${k}:${b.status}`, pass ? `${nm} passed its eval. No new trades on it: time for the next step.` : `${nm}'s eval ended (${b.status}). Tell Claude and set up the next account.`,
        pass ? `${nm} passed its eval.` : `${nm}'s eval has ended.`));
    }
    // --- a guard blocks new entries
    for (const bl of b.blocks) if (bl.text && !(a && a.blocks.some((x) => x.text === bl.text)) && !b.over && !offline)
      out.push(EV('blocked', k, 'warn', 3, `block:${k}:${bl.text.slice(0, 40)}:${Math.floor(cur.now / 3600e3)}`, `${nm} is blocked: ${bl.text}${bl.fix ? ' ' + bl.fix : ''}`, `${nm} is blocked. ${bl.text}`, { cool: 3600 }));
    if (offline || b.over) continue;
    // --- the daily loss approaching
    const dl = dllLevel(b.dll_used, b.dll), dlo = a ? dllLevel(a.dll_used, a.dll) : 'ok';
    if (dl !== 'ok' && (RANK[dl] > RANK[dlo] || !a)) {
      const left = b.dll - b.dll_used;
      out.push(EV('dll', k, dl, dl === 'bad' ? 1.4 : 3, `dll:${k}:${dl}:${cur.day}`, `${nm} has used ${usd(b.dll_used)} of its ${usd(b.dll)} daily loss limit (${usd(left)} left). ${dl === 'bad' ? 'It is close: no manual trades.' : 'Keep an eye on it.'}`,
        `${nm} has used ${sayAmt(b.dll_used)} of its ${sayAmt(b.dll)} daily loss limit. ${sayAmt(left)} left.`, { cool: 1200 }));
    }
    // --- the room to the floor shrinking (Argus: under 50% amber, under 25% red)
    const rl = roomLevel(b.room_frac), rlo = a ? roomLevel(a.room_frac) : 'ok';
    if ((rl === 'warn' || rl === 'bad') && (RANK[rl] > RANK[rlo] || !a))
      out.push(EV('room', k, rl, rl === 'bad' ? 1.6 : 3.5, `room:${k}:${rl}:${cur.day}`, `${nm} has ${usd(b.room)} of room left before the max-loss floor (${Math.round(b.room_frac * 100)}% of ${usd(b.mll)}). ${rl === 'bad' ? 'Close to the floor: no manual trades.' : 'It sizes down by itself.'}`,
        `${nm} has ${sayAmt(b.room)} of room left before the floor. ${rl === 'bad' ? 'That is close.' : ''}`, { cool: 3600 }));
    // --- the 7-day inactivity clock (Argus: amber from day 4, red from day 6)
    const q = b.quiet_days;
    if (q != null && q >= 4 && !(a && a.quiet_days === q)) {
      const left = Math.max(0, INACTIVITY_DAYS - q), lv = quietLevel(q);
      out.push(EV('quiet', k, lv, lv === 'bad' ? 2.6 : 4, `quiet:${k}:${q}:${cur.day}`, `${nm} has had no trade for ${plural(q, 'day')}. MFFU can close an eval after ${INACTIVITY_DAYS}: ${plural(left, 'day')} left.${lv === 'bad' ? ' Place 1 MNQ by hand today so the clock restarts.' : ''}`,
        `${nm} has gone ${plural(q, 'day')} with no trade. MFFU closes an eval at ${INACTIVITY_DAYS}.${lv === 'bad' ? ' Place one micro by hand today.' : ''}`, { cool: 20 * 3600 }));
    }
  }
  return out.sort((x, y) => x.p - y.p);
}

// ------------------------------------------------------------------------------------------------ the cards (game plan 01:45 ET, recap 16:05 ET)
const sideWord = (s) => (s ? s[0] + s.slice(1).toLowerCase() : '');
function botPlanLines(b, snap) {
  const L = [], S = [];
  const win = b.key === 'lit' ? (b.hours || '02:00-15:30 ET') : '';
  if (b.over) { L.push(`${b.name}: ${b.status === 'passed' ? 'the eval is passed, no new trades on it' : 'not trading (' + (b.status || 'no account') + ')'}.`); S.push(`${b.name} is not trading right now.`); return { L, S }; }
  if (b.key === 'lit') {
    L.push(`${b.name} (${b.size}): entry window ${win.replace(' ET', '')} ET, one trade a day at most, flat by 3:55 PM.`);
    S.push(`${b.name}'s window is ${hoursSay(win)}. One trade at most.`);
  } else {
    const ms = b.members.filter((m) => m.stage !== 'off' && m.stage !== 'error');
    L.push(`${b.name} (${b.size}): ${ms.length ? ms.map((m) => `${m.short} ${m.hours.replace(' ET', '')}`).join(', ') + ' ET' : 'no strategy in its hours today'}${b.max_day ? `; at most ${b.max_day} trades a day` : ''}.`);
    S.push(`${b.name} runs ${ms.length ? plural(ms.length, 'strategy', 'strategies') : 'nothing'} today${b.max_day ? `, at most ${b.max_day} trades` : ''}.`);
  }
  if (b.micros && b.micros.qty) { L.push(`Typical size ${plural(b.micros.qty, 'micro')}${b.micros.risk_usd != null ? `: about ${usd(b.micros.risk_usd)} at risk, ${usd(b.micros.win_usd)} if the target is hit` : ''}.`); S.push(`Typical size ${plural(b.micros.qty, 'micro')}${b.micros.risk_usd != null ? `, about ${sayAmt(b.micros.risk_usd)} at risk` : ''}.`); }
  if (b.room != null) { L.push(`Room ${usd(b.room)}${b.room_frac != null ? ` (${Math.round(b.room_frac * 100)}% of the drawdown)` : ''}${b.to_target != null ? `, ${usd(b.to_target)} to the target` : ''}.`); S.push(`Room ${sayAmt(b.room)}${b.to_target != null ? `, ${sayAmt(b.to_target)} to the target` : ''}.`); }
  if (b.quiet_days != null && b.quiet_days >= 3) { L.push(`No trade for ${plural(b.quiet_days, 'day')}: MFFU closes an eval at ${INACTIVITY_DAYS}.`); S.push(`${plural(b.quiet_days, 'day')} with no trade. Watch the seven day rule.`); }
  return { L, S };
}
export function planCard(snap, now) {
  const e = etOf(now), lines0 = [], say = [`Game plan for ${WDL[e.wd]}.`];
  if (!snap || !snap.ok) return { id: 'plan:' + e.ymd, kind: 'plan', day: e.ymd, title: 'Game plan', lines: ['I cannot see the bots right now, so I have no plan to read.'], say: 'I cannot see the bots right now, so I have no plan to read.', t: Math.floor(now / 1000) };
  for (const k of ['lit', 'atlas']) { const b = snap.bots[k]; if (!b) continue; const r = botPlanLines(b, snap); lines0.push(...r.L); say.push(...r.S); }
  if (snap.plan) { lines0.push(`The Mind: ${snap.plan}`); say.push(`The Mind says ${snap.plan}`); }
  if (snap.pc && snap.pc.level !== 'ok' && snap.pc.level !== 'idle') { lines0.push(`Heads up: ${snap.pc.text}`); say.push(`Heads up. ${snap.pc.text}`); }
  else { lines0.push('Your job: PC and NinjaTrader on, no manual trades. The bots do the rest.'); }
  return { id: 'plan:' + e.ymd, kind: 'plan', day: e.ymd, title: 'Game plan', tag: '01:45 ET', lines: lines0, say: say.join(' '), t: Math.floor(now / 1000) };
}
function dayTrades(snap, key, ymd) { return snap.trades.filter((t) => t.bot === key && t.day === ymd && !(t.open && !t.entry_t)); }
export function recapCard(snap, now) {
  const e = etOf(now), L = [], say = [e.min >= RECAP_MIN ? 'Recap for today.' : 'So far today.'];
  if (!snap || !snap.ok) return { id: 'recap:' + e.ymd, kind: 'recap', day: e.ymd, title: 'Recap', lines: ['I cannot see the bots right now, so I have no recap to read.'], say: 'I cannot see the bots right now, so I have no recap to read.', t: Math.floor(now / 1000) };
  let tot = 0, any = false;
  for (const k of ['lit', 'atlas']) {
    const b = snap.bots[k];
    if (!b) continue;
    const ts = dayTrades(snap, k, e.ymd);
    const pnl = b.today_pnl != null ? b.today_pnl : ts.reduce((s, t) => s + (t.usd || 0), 0);
    if (b.today_pnl != null) { tot += b.today_pnl; any = true; }
    const wk = b.week && b.week.n != null ? ` Week: ${b.week.n} trade${b.week.n === 1 ? '' : 's'}${b.week.lo != null ? ` (goal ${b.week.lo}-${b.week.hi})` : ''}.` : '';
    if (ts.length) {
      L.push(`${b.name}: ${ts.length === 1 ? tradeLine(ts[0]) : plural(ts.length, 'trade') + ' (' + ts.map((t) => usd(t.usd, true)).join(', ') + ')'}. Day ${usd(pnl, true)}.${b.room != null ? ` Room left ${usd(b.room)}.` : ''}${wk}`);
      say.push(`${b.name} ${ts.length === 1 ? 'traded once' : 'traded ' + ts.length + ' times'} and the day is ${saySigned(pnl)}.${b.room != null ? ` Room left ${sayAmt(b.room)}.` : ''}`);
    } else {
      const why = b.over ? 'not trading' : b.armed_setup ? 'a setup is still armed' : b.done ? 'done for the day' : snap.pc.level === 'bad' ? 'the PC was silent' : 'no setup that passed its rules';
      L.push(`${b.name}: no trade today (${why}).${b.room != null ? ` Room ${usd(b.room)}.` : ''}${wk}`);
      say.push(`${b.name} did not trade today: ${why}.`);
    }
    if (b.quiet_days != null && b.quiet_days >= 3) { L.push(`${b.name} has gone ${plural(b.quiet_days, 'day')} with no trade (MFFU closes an eval at ${INACTIVITY_DAYS}).`); say.push(`${plural(b.quiet_days, 'day')} with no trade on ${b.name}.`); }
  }
  if (any) { L.push(`Together: ${usd(tot, true)} today.`); }
  const rv = arr(snap.reviews).filter((r) => r.t && etOf(r.t * 1000).ymd === e.ymd).sort((a, b) => b.t - a.t)[0];       // the Mind's lesson of today (live.json pc.mind.reviews, else home.json's brief)
  const lesson = rv ? rv.lesson : snap.brief && snap.brief.recap && snap.brief.recap.day === e.ymd ? snap.brief.recap.lesson : '';
  if (lesson) { L.push(`The Mind's lesson: ${lesson}`); say.push(`The lesson: ${lesson}`); }
  const lit = snap.bots.lit, nxt = lit && lit.window && lit.window.mins != null && !lit.window.open ? lit.window : null;
  if (nxt) { L.push(`Next window: ${nxt.who} ${nxt.label ? nxt.label.replace(/^next entry window /, '') : 'in ' + dur(nxt.mins)} (in ${dur(nxt.mins)}).`); say.push(`Next window in ${durSay(nxt.mins)}.`); }
  return { id: 'recap:' + e.ymd, kind: 'recap', day: e.ymd, title: 'Recap', tag: '16:05 ET', lines: L, say: say.join(' '), t: Math.floor(now / 1000) };
}

// ------------------------------------------------------------------------------------------------ the panel and "Think for me"
export function panel(snap, now, hide) {
  const m = (s) => (hide ? String(s).replace(/[+-]?\$\d[\d,]*/g, '$•••') : s);
  if (!snap || !snap.ok) return { ok: false, lights: [], window: null, pnl: { line: 'No data from the bots yet.', today: null }, state: 'idle' };
  const lights = lightsOf(snap);
  let win = null;
  for (const k of ['lit', 'atlas']) {
    const b = snap.bots[k];
    if (!b || b.over || b.window.mins == null) continue;
    if (!win || (b.window.open && !win.open) || (b.window.open === win.open && b.window.mins < win.mins)) win = { bot: k, who: b.window.who || b.name, open: b.window.open, mins: b.window.mins, label: b.window.label };
  }
  const who = win ? (win.bot === 'lit' ? 'Zlarior' : `ATLAS ${win.who}`) : '';
  const windowText = win ? (win.open ? `${who}: window open, closes in ${dur(win.mins)}` : `Next window: ${who} in ${dur(win.mins)}`) : 'No entry window in the feed.';
  let today = 0, any = false, unreal = 0;
  const parts = [];
  for (const k of ['lit', 'atlas']) {
    const b = snap.bots[k];
    if (!b) continue;
    const ur = b.position && b.position.unreal != null ? b.position.unreal : 0;
    if (b.today_pnl != null) { today += b.today_pnl + ur; any = true; parts.push(`${b.name} ${usd(b.today_pnl + ur, true)}`); }
    unreal += ur;
  }
  const line = any ? `Today ${usd(today, true)} · ${parts.join(' · ')}${unreal ? ` · open ${usd(unreal, true)}` : ''}` : 'No P&L in the feed.';
  const worst = lights.reduce((a, l) => (RANK[l.level] > RANK[a] ? l.level : a), 'ok');
  return { ok: true, lights, window: win ? { ...win, text: m(windowText) } : null, windowText: m(windowText), pnl: { today: any ? today : null, unreal, line: m(line) }, state: worst, stale: snap.cached || (snap.hb_age != null && snap.hb_age > PC_OK_S) };
}
export function items(snap, now) {
  const out = [], add = (p, key, text, say, label, action) => out.push({ p, mode: 'trading', key: 'bot:' + key, text, say: say || text, label: label || 'Status', action: action || { type: 'ask', value: 'How are the bots?' } });
  if (!snap || !snap.ok || snap.cached) return out;
  for (const k of ['lit', 'atlas']) {
    const b = snap.bots[k];
    if (!b || b.over) continue;
    if (b.position) add(2.9, `pos:${k}`, `${b.name} is in a ${b.position.side.toLowerCase()}${b.position.be ? ' with its stop at break-even' : ''}. Let it run: the stop and target are set, no manual orders.`, `${b.name} is in a ${b.position.side.toLowerCase()} trade. Let it run.`);
    else if (b.armed_setup) add(3.1, `armed:${k}`, `${b.name} has a setup armed. It enters by itself if price confirms: no manual trades.`, `${b.name} has a setup armed. Let it work.`);
    else if (!b.window.open && b.window.mins != null && b.window.mins <= 45 && snap.pc.level !== 'bad' && !b.done) add(5.6, `soon:${k}`, `${b.name}'s window opens in ${dur(b.window.mins)}. Check the PC and NinjaTrader are on.`, `${b.name}'s window opens in ${durSay(b.window.mins)}. Check the PC and NinjaTrader.`, 'Check', { type: 'ask', value: 'Is everything OK?' });
    const dl = dllLevel(b.dll_used, b.dll);
    if (dl !== 'ok') add(dl === 'bad' ? 1.6 : 3.4, `dll:${k}`, `${b.name} has used ${usd(b.dll_used)} of its ${usd(b.dll)} daily loss limit today. No manual trades on it.`, `${b.name} is near its daily loss limit.`, 'How much room?', { type: 'ask', value: 'How much room is left?' });
  }
  const e = etOf(now);
  if (e.wd >= 1 && e.wd <= 5 && e.min >= RECAP_MIN && e.min < RECAP_SPEAK_UNTIL) add(7.9, 'recap', 'The bots\' recap for today is ready.', 'The bots recap for today is ready.', 'Recap', { type: 'ask', value: 'Recap' });
  else if (e.wd >= 1 && e.wd <= 5 && e.min >= PLAN_MIN && e.min < PLAN_SPEAK_UNTIL) add(7.9, 'plan', 'The bots\' game plan for today is ready.', 'The bots game plan for today is ready.', 'Game plan', { type: 'ask', value: 'Game plan' });
  return out.sort((a, c) => a.p - c.p);
}

// ------------------------------------------------------------------------------------------------ the answers
const norm = (raw) => String(raw == null ? '' : raw).toLowerCase().replace(/[’‘`´]/g, "'").replace(/[^a-z0-9$&%'.:+\- ]+/g, ' ').replace(/\s+/g, ' ').replace(/[.:]+$/g, '').trim()
  .replace(/^(hey |hi |ok |okay |yo )?jarvis\s+(?=\S)/, '').replace(/\s+jarvis$/, '').replace(/^(please|can you|could you|would you|tell me|let me know|so)\s+(?=\S)/, '').replace(/\s+please$/, '').trim();
const botsIn = (q) => BOTS.filter((b) => b.rx.test(q)).map((b) => b.key);
const needData = () => ({ text: 'I cannot see the bots\' live feed right now, so I will not guess. Check the signal, then the PC.', speak: 'I cannot see the bots right now.', intent: 'bots_nodata' });
const freshNote = (snap) => (snap.cached ? `(This is the copy saved on the phone from ${ageText(Math.max(0, snap.now / 1000 - (snap.t || 0)))} ago: the live feed is not answering.)` : snap.pc && (snap.pc.level === 'warn' || snap.pc.level === 'bad') ? `(${snap.pc.text})` : '');
export function answer(raw, snap, now, extra) {
  const q = norm(raw), x = isObj(extra) ? extra : {};
  if (!q) return null;
  const sel = botsIn(q), only = sel.length > 0 && !/\b(bots|both|all|everything|each)\b/.test(q), keys = only ? sel : ['lit', 'atlas'];
  const R = (text, speak, intent, more) => Object.assign({ text, speak, intent }, more || {});
  const e = etOf(now);

  // arming, disarming, and moving a stop or an order are never Jarvis's: she reads the bots, she does not touch them
  if (/^(?:please )?(?:re-?arm|disarm|unarm|arm)\b|\b(?:arm|disarm) (?:the |my |its )?(?:bots?|zlarior|atlas|lit|live|account|eval|everything|it)\b|^(?:move|change|raise|lower|widen|tighten|cancel|set) (?:the |my |its )?(?:stop|stops|target|order|orders)\b|^(?:take|put) (?:the )?(?:bots?|zlarior|atlas) (?:live|off)\b|^(?:turn on|switch on|enable|start|activate) (?:the )?(?:live|real)\b/.test(q))
    return R('I am afraid I cannot do that, sir: I only read the bots. Arming, orders and stops stay with you, on the PC and in NinjaTrader (and MFFU wants you present for live trading).', 'I cannot do that. I only read the bots. Arming, orders and stops stay with you.', 'refuse_trade');
  // alert switches ("mute bot alerts", "bot alerts on", "quiet hours on", "what alerts do you have")
  const sw = /^(?:(?:turn |switch )?(mute|stop|silence|disable|pause)(?: the)? (?:bots?|trading|bot) (?:alerts?|announcements?|updates?)|(?:turn |switch )?(?:bots?|trading|bot) (?:alerts?|announcements?) (on|off)|(?:turn |switch )?(on|off) (?:the )?(?:bots?|trading|bot) (?:alerts?|announcements?)|(?:unmute|enable|resume|start) (?:the )?(?:bots?|trading|bot) (?:alerts?|announcements?|updates?)|stop announcing(?: the bots?)?|(?:turn |switch )?quiet hours (on|off)|(?:turn |switch )?(on|off) quiet hours)$/.exec(q);
  if (sw && typeof x.set === 'function') {
    const word = sw.slice(1).filter(Boolean)[0];
    if (/quiet hours/.test(q)) { const on = /\bon\b/.test(q); x.set({ quiet: { on } }); return R(on ? 'Quiet hours are on: no bot alerts spoken from 11 PM to 6 AM ET (they still show on screen).' : 'Quiet hours are off: bot alerts can be spoken any time.', on ? 'Quiet hours are on. I will stay quiet from 11 PM to 6 AM.' : 'Quiet hours are off.', 'bots_alerts', ); }
    const off = /^(mute|stop|silence|disable|pause)$/.test(word) || word === 'off' || /^stop announcing/.test(q);
    x.set({ on: !off });
    return R(off ? 'Bot alerts are off: I will not speak about the bots unless you ask. Say "bot alerts on" to bring them back.' : 'Bot alerts are on: I tell you when a setup is armed, a trade is filled, the stop moves to break-even, a trade closes, or something needs you.',
      off ? 'Bot alerts are off.' : 'Bot alerts are on.', 'bots_alerts');
  }
  if (/^(?:what (?:are|is) (?:my )?(?:the )?bots? alerts?|bot alerts?(?: settings?)?|how do (?:the )?bots? alerts? work)$/.test(q)) {
    const st = typeof x.settings === 'function' ? x.settings() : { on: true, quiet: { on: false } };
    return R(`Bot alerts are ${st.on ? 'on' : 'off'}${st.quiet && st.quiet.on ? `, quiet hours ${st.quiet.from}-${st.quiet.to} ET` : ''}. I speak when a setup is armed, an entry fills, the stop moves to break-even, a trade closes (with the result and the room left), the PC or the price feed goes quiet, the daily loss or the room gets close, and when the 7-day inactivity clock reaches day 4 and 6. Never more than one a half minute, 8 an hour, and never over you or another answer. Say "mute bot alerts" or "quiet hours on".`,
      `Bot alerts are ${st.on ? 'on' : 'off'}. I speak when something needs you, never over another answer.`, 'bots_alerts');
  }
  const isPlan = /^(?:what'?s|what is|show me|show|give me|read me|read|tell me)?\s*(?:the |my |today'?s |this morning'?s )?(?:bots?'? )?(?:game ?plan|morning plan|plan)(?: for (?:the )?(?:bots?|zlarior|atlas|lit|today|the day|the morning))?$/.test(q) && !/^(?:plan|show|show me)$/.test(q);
  const isRecap = /^(?:what'?s |show me |give me |read me |read |tell me )?(?:the |my |today'?s )?(?:bots?'? )?(?:end of day |daily |eod |day |evening )?(?:recap|wrap ?up)(?: for (?:the )?(?:bots?|today|the day))?$|^how did (?:today|the day) go$|^how did (?:we|the bots?|zlarior|atlas|the bot) do(?: today)?$/.test(q);
  const isArmed = /\barmed\b|\bdisarmed\b/.test(q) && (sel.length || /\bbots?\b/.test(q) || /^(?:are|is) (?:we|it|everything) armed$/.test(q));
  const isTraded = /^(?:did|have|has|was there|were there|any)\b/.test(q) && /\b(?:trade[sd]?|trades|trading|entry|entries|entered|filled|fill|take a trade|got in|get in)\b/.test(q) && (/\b(?:today|so far|yet|this morning|tonight|at all)\b/.test(q) || /\b(?:did|have|has) (?:we|you|i|the bots?|zlarior|atlas|lit|the bot)\b.*\b(?:trade[sd]?|take a trade|entered|got in)$/.test(q));
  const isYest = /\byesterday\b/.test(q) && (sel.length || /\b(?:bots?|we|trade[sd]?|trades|trading|do|did|done|happen(?:ed)?)\b/.test(q)) && !/\bkalshi\b/.test(q);
  const isLog = /^(?:what happened|what'?s (?:new|happened)|anything (?:new|happen(?:ed)?)|any news|what did the bots? (?:just )?do|bots? (?:news|events|log)|what'?s the latest|latest from the bots?)$/.test(q) || /^what did (?:zlarior|atlas|the bot|the bots) (?:just )?do$/.test(q);
  if (!(isPlan || isRecap || isArmed || isTraded || isYest || isLog)) return null;
  if (!snap || !snap.ok) return R(needData().text, needData().speak, 'bots_nodata');
  const fn = freshNote(snap);

  if (isArmed) {
    const out = [], say = [];
    for (const k of keys) {
      const b = snap.bots[k];
      if (!b) { out.push(`${BOT[k].name}: not in the feed.`); say.push(`${BOT[k].name} is not in the feed.`); continue; }
      const acct = b.broker ? ` (account ending ${b.broker.slice(-4)})` : '';
      const what = b.position ? `It is in a ${b.position.side.toLowerCase()} trade right now.` : b.armed_setup ? 'A setup is armed and waiting for price.' : b.done ? 'It is done for today.' : b.waiting ? (b.waiting.indexOf('. ') > 0 ? b.waiting.slice(0, b.waiting.indexOf('. ') + 1) : b.waiting) : 'No setup yet.';
      if (snap.pc.level === 'bad') { out.push(`${b.name}${acct}: I cannot confirm: the PC has not checked in for ${ageText(snap.hb_age || 0)}.`); say.push(`I cannot confirm ${b.name}. The PC has been silent for ${ageText(snap.hb_age || 0)}.`); continue; }
      if (b.armed === true) { out.push(`${b.name}${acct}: Yes, it is armed. It can send real orders to the ${b.size} account through NinjaTrader. ${what}`); say.push(`Yes, ${b.name} is armed and routes orders to the ${b.size} account. ${what.replace(/^It is /, 'It is ')}`); }
      else if (b.armed === false) { out.push(`${b.name}${acct}: It is running but NOT armed, so it will not send orders. If you want it trading, arm it yourself on the PC Start page. I cannot arm it.`); say.push(`${b.name} is running but not armed. It will not send orders. Arming is yours to do on the PC.`); }
      else { out.push(`${b.name}${acct}: The feed does not say if it is armed (badge ${b.badge || 'missing'}). ${what}`); say.push(`The feed does not say if ${b.name} is armed. ${what}`); }
    }
    if (fn) out.push(fn);
    return R(lines(...out), say.join(' '), 'bots_armed');
  }
  if (isTraded) {
    const out = [], say = [];
    for (const k of keys) {
      const b = snap.bots[k];
      if (!b) { out.push(`${BOT[k].name}: not in the feed.`); continue; }
      const ts = dayTrades(snap, k, e.ymd), n = Math.max(ts.length, b.trades_today || 0);
      if (b.position) { out.push(`${b.name}: yes, it is in a ${b.position.side.toLowerCase()}${b.position.qty ? ' ' + plural(b.position.qty, 'micro') : ''} right now${b.position.unreal != null ? ` (${usd(b.position.unreal, true)} open)` : ''}.`); say.push(`Yes. ${b.name} is in a ${b.position.side.toLowerCase()} trade right now.`); }
      else if (n > 0) { out.push(`${b.name}: yes, ${plural(n, 'trade')} today${ts.length ? ': ' + ts.map(tradeLine).join('; ') : ''}. Day ${usd(b.today_pnl, true) || 'missing'}.`); say.push(`Yes. ${b.name} traded ${n === 1 ? 'once' : n + ' times'} and the day is ${saySigned(b.today_pnl) || 'missing'}.`); }
      else {
        const why = b.armed_setup ? 'a setup is armed and waiting' : b.over ? 'it is not trading (' + b.status + ')' : snap.pc.level === 'bad' ? 'the PC is silent' : b.window.open ? 'its window is open and no setup has passed its rules yet' : b.window.mins != null ? `its window opens in ${dur(b.window.mins)}` : 'no setup yet';
        out.push(`${b.name}: not yet today: ${why}.`); say.push(`Not yet. ${b.name}: ${why}.`);
      }
    }
    if (fn) out.push(fn);
    return R(lines(...out), say.join(' '), 'bots_traded');
  }
  if (isYest) {
    const dn = prevTradingDn(e.dn), ymd = ymdOfDn(dn), out = [], say = [];
    const dname = dn === e.dn - 1 ? 'yesterday' : WDL[new Date(dn * 864e5).getUTCDay()];
    for (const k of keys) {
      const b = snap.bots[k];
      if (!b) continue;
      const ts = dayTrades(snap, k, ymd).filter((t) => !t.open);
      const wd = b.week && b.week.days.find((d) => d.day === ymd), dd = (b.days || []).find((d) => d.day === ymd);
      if (ts.length) { const tot = ts.reduce((s, t) => s + (t.usd || 0), 0); out.push(`${b.name} ${dname}: ${ts.map(tradeLine).join('; ')}. Day ${usd(tot, true)}.`); say.push(`${b.name} ${dname}: ${ts.length === 1 ? 'one trade' : ts.length + ' trades'}, ${saySigned(tot)}.`); }
      else if (wd && wd.n != null && wd.n > 0) { out.push(`${b.name} ${dname}: ${plural(wd.n, 'trade')}, day ${usd(wd.usd, true)}.`); say.push(`${b.name} ${dname}: ${wd.n === 1 ? 'one trade' : wd.n + ' trades'}, ${saySigned(wd.usd)}.`); }
      else if (dd && dd.usd != null && Math.abs(dd.usd) > 0) { out.push(`${b.name} ${dname}: day ${usd(dd.usd, true)}.`); say.push(`${b.name} ${dname}: ${saySigned(dd.usd)}.`); }
      else if (wd && wd.n === 0 || (b.days && !dd)) { out.push(`${b.name} ${dname}: no trade.`); say.push(`${b.name} did not trade ${dname}.`); }
      else { out.push(`${b.name} ${dname}: not in the feed's recent list.`); say.push(`${dname} is not in my recent list for ${b.name}.`); }
    }
    if (k0(keys) === 'lit' && snap.brief && snap.brief.prev && snap.brief.prev.day === ymd && snap.brief.prev.text && !out.length) out.push(snap.brief.prev.text);
    if (!out.length) return R(`${dname[0].toUpperCase() + dname.slice(1)} is not in the feed's recent list. Zenith's Trades page has the full log: say "open trades".`, `${dname} is not in my recent list.`, 'bots_yesterday');
    return R(lines(...out), say.join(' '), 'bots_yesterday');
  }
  if (isLog) {
    const log = typeof x.log === 'function' ? x.log() : [];
    const rec = log.filter((l) => !sel.length || sel.includes(l.bot)).slice(0, 5);
    if (!rec.length) return R('Nothing new from the bots since I started watching on this phone. Ask "how are the bots" for the status.', 'Nothing new from the bots.', 'bots_log');
    return R(lines('Latest from the bots:', ...rec.map((l) => `${l.hm} ${l.text}`)), rec[0].say || rec[0].text, 'bots_log');
  }
  if (isRecap) {
    const c = recapCard(snap, now);
    return R(lines(c.title + (e.min >= RECAP_MIN ? '' : ' (so far today)'), ...c.lines, fn), c.say, 'bots_recap', { cards: [{ title: 'Recap', lines: c.lines.slice(0, 5), open: 'zenith' }] });
  }
  // the game plan: the morning card, else built now
  const c = planCard(snap, now);
  return R(lines(c.title, ...c.lines, fn), c.say, 'bots_plan', { cards: [{ title: 'Game plan', lines: c.lines.slice(0, 5), open: 'zenith' }] });
}
const k0 = (a) => (a.length === 1 ? a[0] : '');

// ------------------------------------------------------------------------------------------------ the instance
export function createBots(opts) {
  const o = isObj(opts) ? opts : {};
  const store = () => { if (o.storage) return o.storage; try { return typeof localStorage !== 'undefined' ? localStorage : null; } catch (_) { return null; } };
  const lget = (k, d) => { try { const st = store(), v = st ? st.getItem(k) : null; return v == null ? d : JSON.parse(v); } catch (_) { return d; } };
  const lset = (k, v) => { try { const st = store(); if (st) st.setItem(k, JSON.stringify(v)); } catch (_) { /* not kept */ } };
  const clock = () => (typeof o.now === 'function' ? (o.now() instanceof Date ? o.now().getTime() : +o.now()) : Date.now());
  const call = (f, ...a) => { try { return typeof f === 'function' ? f(...a) : undefined; } catch (_) { return undefined; } };
  const DEF = { on: true, quiet: { on: false, from: '23:00', to: '06:00' }, plan: true, recap: true };
  const settings = () => { const s = lget(SET_KEY, null), q = isObj(s) && isObj(s.quiet) ? s.quiet : {}; return { on: !isObj(s) || s.on !== false, quiet: { on: q.on === true, from: /^\d\d:\d\d$/.test(q.from) ? q.from : DEF.quiet.from, to: /^\d\d:\d\d$/.test(q.to) ? q.to : DEF.quiet.to }, plan: !isObj(s) || s.plan !== false, recap: !isObj(s) || s.recap !== false }; };
  function set(patch) {
    const cur = settings(), p = isObj(patch) ? patch : {};
    const nx = { on: typeof p.on === 'boolean' ? p.on : cur.on, quiet: { ...cur.quiet, ...(isObj(p.quiet) ? p.quiet : {}) }, plan: typeof p.plan === 'boolean' ? p.plan : cur.plan, recap: typeof p.recap === 'boolean' ? p.recap : cur.recap };
    lset(SET_KEY, nx);
    if (!nx.on) queue.length = 0;
    return settings();
  }
  const inQuiet = (nowMs) => {
    const q = settings().quiet;
    if (!q.on) return false;
    const m = (s) => +s.slice(0, 2) * 60 + +s.slice(3), a = m(q.from), b = m(q.to), t = etOf(nowMs).min;
    return a === b ? false : a < b ? t >= a && t < b : t >= a || t < b;
  };
  const queue = [];            // [{ ev, t }]
  let busyLoops = 0, last = { snap: null, events: [], reason: '' };
  const seenGet = (nowS) => { const s = lget(SEEN_KEY, {}), out = {}; for (const k of Object.keys(isObj(s) ? s : {})) if (nowS - s[k] < 3 * 86400) out[k] = s[k]; return out; };
  const spokenGet = () => { const s = lget(SPOKEN_KEY, {}); return { groups: isObj(s) && isObj(s.groups) ? s.groups : {}, hours: isObj(s) && Array.isArray(s.hours) ? s.hours.filter((x) => typeof x === 'number') : [], last: isObj(s) && typeof s.last === 'number' ? s.last : 0 }; };
  const maskSay = (s) => String(s || '').replace(/\b\d+(,\d{3})*(\.\d+)? dollars?( \d+(?! dollars?))?( cents)?/g, 'a hidden amount');
  const maskTxt = (s) => String(s || '').replace(/[+-]?\$\d[\d,]*(\.\d+)?/g, '$•••');
  const hidden = () => call(o.hidden) === true;
  const logAdd = (ev, nowMs) => {
    const log = lget(LOG_KEY, []), e = etOf(nowMs);
    log.unshift({ key: ev.key, kind: ev.kind, bot: ev.bot, level: ev.level, text: ev.text, say: ev.say, t: Math.floor(nowMs / 1000), hm: `${p2(e.h)}:${p2(e.m)}` });
    lset(LOG_KEY, log.slice(0, 30));
  };

  /** speak what is queued, if now is a good time. Returns { spoken: [events], reason } */
  function flush(nowMs) {
    const now = num(nowMs) != null ? num(nowMs) : clock(), nowS = now / 1000, set0 = settings();
    for (let i = queue.length - 1; i >= 0; i--) if (nowS - queue[i].t > (queue[i].ev.ttl || TTL_S)) queue.splice(i, 1);       // old news is not worth saying
    if (!queue.length) return { spoken: [], reason: 'empty' };
    if (!set0.on) { queue.length = 0; return { spoken: [], reason: 'off' }; }
    if (inQuiet(now)) { queue.length = 0; return { spoken: [], reason: 'quiet' }; }
    if (call(o.busy) === true) return { spoken: [], reason: 'busy' };
    const sp = spokenGet();
    if (nowS - sp.last < MIN_GAP_S) return { spoken: [], reason: 'gap' };
    const hours = sp.hours.filter((s) => nowS - s < 3600);
    queue.sort((a, b) => a.ev.p - b.ev.p);
    let pick = queue.filter((it) => !(it.ev.cool && sp.groups[it.ev.group] && nowS - sp.groups[it.ev.group] < it.ev.cool));
    for (const it of queue) if (!pick.includes(it)) it.drop = true;                                                    // inside its cooldown: shown, not said again
    if (hours.length >= PER_HOUR) pick = pick.filter((it) => it.ev.p < 2.7);                                           // an exit, a fill or a red light still gets through
    for (let i = queue.length - 1; i >= 0; i--) if (queue[i].drop) queue.splice(i, 1);
    if (!pick.length) return { spoken: [], reason: hours.length >= PER_HOUR ? 'hourly' : 'cooldown' };
    const take = pick.slice(0, BATCH);
    const say = take.map((it) => it.ev.say).join(' ');
    const r = call(o.speak, hidden() ? maskSay(say) : say, { events: take.map((it) => it.ev) });
    if (r === 'hidden') return { spoken: [], reason: 'hidden' };                                                       // the page is out of sight: keep it a little
    for (const it of take) queue.splice(queue.indexOf(it), 1);
    if (r === 'spoken' || r === 'pending') {
      const groups = { ...sp.groups };
      for (const it of take) groups[it.ev.group] = nowS;
      for (const k of Object.keys(groups)) if (nowS - groups[k] > 86400) delete groups[k];
      lset(SPOKEN_KEY, { groups, hours: hours.concat([nowS]), last: nowS });
      return { spoken: take.map((it) => it.ev), reason: r };
    }
    return { spoken: [], reason: String(r || 'none') };
  }
  function offer(events, nowMs) {
    const nowS = nowMs / 1000, seen = seenGet(nowS), fresh = [];
    for (const ev of events) {
      if (seen[ev.key]) continue;
      seen[ev.key] = nowS; fresh.push(ev);
      logAdd(ev, nowMs);
      call(o.onEvent, hidden() ? { ...ev, text: maskTxt(ev.text), say: maskSay(ev.say) } : ev);
      queue.push({ ev, t: nowS });
    }
    lset(SEEN_KEY, seen);
    return fresh;
  }
  function compact(snap) { return { ok: snap.ok, now: snap.now, t: snap.t, day: snap.day, pc: { level: snap.pc.level, running: snap.pc.running }, feed: { level: snap.feed.level }, loop: snap.loop, bots: snap.bots, trades: snap.trades.filter((t) => t.exit_t || t.open) .slice(0, 12), hb_t: snap.hb_t }; }
  function ingest(live, nowMs) {
    const now = num(nowMs) != null ? num(nowMs) : clock();
    const snap = snapshot(live, now);
    last.snap = snap;
    if (!snap.ok) return { snap, events: [] };
    const prev = lget(SNAP_KEY, null);
    const events = offer(snap.cached ? [] : diff(prev && prev.ok ? prev : null, snap, now), now);
    if (!snap.cached) lset(SNAP_KEY, compact(snap));
    last.events = events;
    return { snap, events };
  }
  const dayKey = (e) => e.ymd;
  function cards(nowMs) { const c = lget(CARD_KEY, null), d = etOf(num(nowMs) != null ? nowMs : clock()).ymd; return isObj(c) && c.day === d ? c : { day: d, plan: null, recap: null }; }
  /** the card due now (01:45 ET plan, 16:05 ET recap, weekdays), built once a day from a live reading */
  function dueCards(snap, nowMs) {
    const e = etOf(nowMs), out = [], c = cards(nowMs);
    if (!snap || !snap.ok || snap.cached || e.wd < 1 || e.wd > 5) return out;
    const sp = settings();
    for (const [kind, start, until, flag, build] of [['plan', PLAN_MIN, PLAN_SPEAK_UNTIL, sp.plan, planCard], ['recap', RECAP_MIN, RECAP_SPEAK_UNTIL, sp.recap, recapCard]]) {
      if (c[kind] || e.min < start || !flag) continue;
      if (kind === 'plan' && e.min >= PLAN_BUILD_UNTIL) continue;              // the morning plan is not built after noon
      const card = build(snap, nowMs);
      c[kind] = card; c.day = dayKey(e);
      out.push(card);
      call(o.onCard, card);
      if (e.min < until) {                                                       // spoken while it is still the plan's / the recap's time
        const ev = EV(kind, 'bots', 'info', 4.5, `${kind}:${e.ymd}`, card.lines.join(' '), card.say, { ttl: 20 * 60, cool: 3600 });
        logAdd(ev, nowMs); queue.push({ ev, t: nowMs / 1000 });
      }
    }
    if (out.length) lset(CARD_KEY, c);
    return out;
  }
  function tick(live, nowMs) {
    const now = num(nowMs) != null ? num(nowMs) : clock();
    const r = ingest(live, now);
    const cardsMade = dueCards(r.snap, now);
    const f = flush(now);
    return { snap: r.snap, events: r.events, cards: cardsMade, spoken: f.spoken, reason: f.reason };
  }
  return {
    tick, ingest, flush, settings, set, snapshot: (live, now) => snapshot(live, num(now) != null ? num(now) : clock()),
    panel: (live, now) => panel(snapshot(live, num(now) != null ? num(now) : clock()), num(now) != null ? num(now) : clock(), hidden()),
    items: (live, now) => items(snapshot(live, num(now) != null ? num(now) : clock()), num(now) != null ? num(now) : clock()),
    answer: (raw, q, live, now) => {
      const t = num(now) != null ? num(now) : clock();
      return answer(raw, snapshot(live, t), t, { set, settings, log: () => lget(LOG_KEY, []) });
    },
    plan: (live, now) => planCard(snapshot(live, num(now) != null ? num(now) : clock()), num(now) != null ? num(now) : clock()),
    recap: (live, now) => recapCard(snapshot(live, num(now) != null ? num(now) : clock()), num(now) != null ? num(now) : clock()),
    cards, log: () => lget(LOG_KEY, []), queued: () => queue.map((it) => it.ev), last: () => last,
    reset() { for (const k of [SNAP_KEY, SEEN_KEY, LOG_KEY, CARD_KEY, SPOKEN_KEY]) { try { const st = store(); if (st) st.removeItem(k); } catch (_) { /* nothing kept */ } } queue.length = 0; },
  };
}
export default createBots;
