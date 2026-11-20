// NQ desk (nqdash3 2026-11-20, owner: "NQ dashboard: accounts, info, phone notifications exactly when a trade is taken AND closed with results;
// clean, cool effects, quality checks" and "thinking process before and through trades, news, bias"). ES module, shared by nq/ and trading/.
//   accounts(home, biz, nowS)          -> every MFFU account in the owner's order (business/accounts.json): balance, room left, to pass / to payout,
//                                         today's $, a live / stale / plan dot from the PC's 15-minute report
//   thinking(home, news, file, nowS)   -> per bot: "Before the trade" (lean, today's news, key levels, the window, what it waits for), "In the trade"
//                                         (entry, stop, target, R so far, time in trade), "After" (result $ and R, the reel link)
//   quality(home, file, news, nowS)    -> the checks: data freshness, PC heartbeat age, last trade alert, PC-vs-backtest twin mismatches
//   draw.accounts / draw.thinking / draw.quality(el, model)  -> the cards (textContent / createElement only)
// Only what the PC and the cloud already publish: home.json with the PC post laid over it (../pc_feed.js homeOver: accounts, board, live.pc.glance =
// engine/brain_glance, live.reporter), ./news_week.json, ../trading/trades.json. A field that is not there says so; nothing is made up. BLITZ never shows.
// Read only: it sends nothing. Node-tested (tests/test_nq_desk.py).

export const FRESH_S = 20 * 60;          // the PC posts every 15 minutes: older than 20 = stale (pc_feed.js FRESH_S)
export const BEAT_STALE_S = 15 * 60;      // the bot beats every 5 minutes (tools/pc_report.py HB_STALE_S)
const isObj = (x) => !!x && typeof x === 'object' && !Array.isArray(x);
const num = (v) => (v === null || v === undefined || v === '' || !Number.isFinite(+v) ? null : +v);
const arr = (x) => (Array.isArray(x) ? x : []);

// ------------------------------------------------------------------------------------------------ words
export function money(v, sign) {
  const n = num(v); if (n === null) return '-';
  const a = Math.round(Math.abs(n)), s = a.toLocaleString('en-US');
  if (a === 0) return '$0';
  return (n < 0 ? '-' : sign ? '+' : '') + '$' + s;
}
export const rText = (v) => { const n = num(v); return n === null ? '' : `${n >= 0 ? '+' : '-'}${Math.abs(n).toFixed(1)}R`; };
export const px = (v) => { const n = num(v); return n === null ? '-' : n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }); };
export function ageText(s) {
  const n = num(s); if (n === null) return 'unknown';
  if (n < 90) return 'just now';
  if (n < 3600) return `${Math.round(n / 60)} min ago`;
  if (n < 48 * 3600) { const h = Math.floor(n / 3600), m = Math.round((n % 3600) / 60); return m && h < 6 ? `${h} h ${m} min ago` : `${h} h ago`; }
  return `${Math.round(n / 86400)} days ago`;
}
export function etParts(tS) {
  try {
    const p = Object.fromEntries(new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23', weekday: 'short' })
      .formatToParts(new Date(tS * 1000)).map((x) => [x.type, x.value]));
    return { day: `${p.year}-${p.month}-${p.day}`, hm: `${p.hour}:${p.minute}`, wd: p.weekday };
  } catch (_) { const d = new Date(tS * 1000).toISOString(); return { day: d.slice(0, 10), hm: d.slice(11, 16), wd: '' }; }
}
const hmET = (tS) => { const n = num(tS); if (!n) return ''; const p = etParts(n), h = +p.hm.slice(0, 2), m = p.hm.slice(3); return `${h % 12 || 12}:${m} ${h < 12 ? 'AM' : 'PM'} ET`; };
export function mins(s) { const n = Math.max(0, Math.round((num(s) || 0) / 60)); return n < 60 ? `${n} min` : `${Math.floor(n / 60)} h ${n % 60} min`; }

// ------------------------------------------------------------------------------------------------ the PC feed's age
export function feedAge(home, nowS) {
  const pf = isObj(home) && isObj(home.pc_feed) ? home.pc_feed : null, live = isObj(home) && isObj(home.live) ? home.live : {};
  const rt = num(pf && (pf.report_t || pf.t)) || num(isObj(live.reporter) && live.reporter.t);
  const bt = num(isObj(live.pc) && live.pc.t);
  return { report: rt ? Math.max(0, nowS - rt) : null, beat: bt ? Math.max(0, nowS - bt) : null, fromPc: !!rt };
}
function dotOf(age) { return age === null ? 'off' : age <= FRESH_S ? 'live' : 'stale'; }

// ------------------------------------------------------------------------------------------------ the PC's chart post (le-bars): the open trades
// chart = { opens: post.open (rows {k, s, q, t, e, sl, tp, be}), last: the last bar's close, t: the post's data time } (the page decodes the bars
// with nqbars.js and hands this in). The freshest word on an open trade: its stop as it is NOW (a moved stop), and the $ at the last bar.
const CHART_ACCT = { z50k: 'zlarior', z25k2: 'fresh25', atlas25f: 'atlas', rapid25: 'rapid1', rapid: 'rapid1' };
export function chartOpen(chart, pick, nowS) {
  if (!isObj(chart)) return null;
  const r = arr(chart.opens).find((x) => isObj(x) && pick(String(x.k || '')) && num(x.e) !== null && num(x.t) !== null);
  if (!r) return null;
  const dir = num(r.s) < 0 ? -1 : 1, q = num(r.q) || 1, e = num(r.e), sl = num(r.sl), tp = num(r.tp), last = num(chart.last);
  const moved = !!r.be || (sl !== null && (dir > 0 ? sl >= e : sl <= e));
  return { k: r.k, side: dir > 0 ? 'LONG' : 'SHORT', qty: q, entry: e, stop: sl, target: tp, stopMoved: moved,
    locked: moved && sl !== null ? (sl - e) * dir * q * 2 : null, target_usd: tp !== null ? Math.abs(tp - e) * q * 2 : null,
    now: last !== null ? (last - e) * dir * q * 2 : null, last, lastAge: num(chart.t) ? Math.max(0, nowS - chart.t) : null,
    since: Math.max(0, nowS - r.t) };
}

// ------------------------------------------------------------------------------------------------ 1. the accounts strip
const PLAN = { zlarior: ['mffu50k_eval', 'lit'], fresh25: ['b25k_2'], atlas: ['atlas', 'acct_b'], rapid1: ['rapid'] };
const SHORT = { zlarior: 'Zlarior 50K', fresh25: 'Zlarior 25K #2', atlas: 'ATLAS 25K', rapid1: 'Rapid EOD 25K' };
const BOARD_OF = { zlarior: 'lit', atlas: 'atlas' };

export function accounts(home, biz, nowS, chart) {
  const h = isObj(home) ? home : {}, board = isObj(h.board) ? h.board : {}, list = arr(h.accounts).filter(isObj);
  const plan = arr(isObj(biz) ? biz.accounts : null).filter((a) => isObj(a) && !/blitz/i.test(String(a.key) + a.name));
  const order = plan.length ? plan : Object.keys(PLAN).map((key) => ({ key, name: SHORT[key], pc: PLAN[key] }));
  const fa = feedAge(h, nowS), out = [], used = new Set();
  for (const p of order) {
    const ids = arr(p.pc).length ? arr(p.pc) : (PLAN[p.key] || []);
    const acc = list.find((a) => ids.includes(a.id) && a.source !== 'cloud' && a.live) || null;
    const card = BOARD_OF[p.key] && isObj(board[BOARD_OF[p.key]]) && fa.fromPc ? board[BOARD_OF[p.key]] : null;
    const ev = acc && isObj(acc.eval) ? acc.eval : {};
    const funded = /funded/i.test(String(p.stage || '') + (card && card.status) + (ev.status || ''));
    const bal = num(ev.balance) ?? num(card && card.balance), room = num(ev.room) ?? num(card && card.room), mll = num(ev.mll) ?? num(card && card.mll);
    const today = num(ev.today) ?? num(acc && isObj(acc.pnl) && acc.pnl.today) ?? num(card && card.today_pnl);
    const goal = funded ? (num(card && card.to_target) ?? num(ev.to_target)) : (num(ev.to_target) ?? num(card && card.to_target));
    const has = bal !== null;
    if (acc) used.add(acc.id);
    const connT = num(acc && isObj(acc.conn) && acc.conn.t);
    const age = has ? Math.max(connT ? nowS - connT : 0, fa.report ?? 0, 0) : null;     // an old report makes every number in it old
    const planned = !has && /buying|planned|plan/i.test(String(p.status || '') + (p.stage || ''));
    out.push({
      key: p.key, name: SHORT[p.key] || p.name || p.key, plan: p.plan || '', stage: funded ? 'Funded' : 'Eval',
      has, balance: bal, room, mll, roomFrac: room !== null && mll ? Math.max(0, Math.min(1, room / mll)) : null, today,
      goalLabel: funded ? 'To payout' : 'To pass', goal, goalText: goal === null ? (funded && card && card.payout_text ? 'see payout line' : '-') : goal <= 0 ? (funded ? 'Payout ready' : 'Target reached') : money(goal),
      payoutText: funded && card && card.payout_text ? String(card.payout_text) : '',
      dot: has ? dotOf(age) : planned ? 'plan' : 'off', ageText: has ? ageText(age) : planned ? 'plan only: no PC numbers yet' : 'no PC numbers',
      open: chartOpen(chart, (k) => CHART_ACCT[k] === p.key, nowS),
    });
  }
  out.sort((a, b) => (a.dot === 'plan') - (b.dot === 'plan'));
  // an account the PC lists that the plan file does not name yet (a new extra account): it still shows, after the planned ones
  for (const a of list) {
    if (used.has(a.id) || !a.live || a.source === 'cloud' || /blitz/i.test(String(a.id) + a.name) || !isObj(a.eval)) continue;
    if (Object.values(PLAN).some((ids) => ids.includes(a.id))) continue;
    const e = a.eval, connT = num(isObj(a.conn) && a.conn.t), age = Math.max(connT ? nowS - connT : 0, fa.report ?? 0, 0);
    out.push({ key: a.id, name: String(a.name || a.id), plan: a.plan || '', stage: /funded/i.test(e.status || '') ? 'Funded' : 'Eval', has: num(e.balance) !== null,
      balance: num(e.balance), room: num(e.room), mll: num(e.mll), roomFrac: num(e.room) !== null && num(e.mll) ? Math.max(0, Math.min(1, e.room / e.mll)) : null,
      today: num(e.today), goalLabel: 'To pass', goal: num(e.to_target), goalText: num(e.to_target) === null ? '-' : money(e.to_target), payoutText: '',
      dot: dotOf(age), ageText: ageText(age) });
  }
  return out;
}

// ------------------------------------------------------------------------------------------------ the pre-market brief (./brief.json, helper day-brief)
// Read when present, never needed: its contract (docs/BRIEF.md on day-brief) was not out when this was written, so the reader takes the likely
// shapes and ignores the rest. -> { bias: {side, text} | null, levels: [{label, px, dist}], news: [{time, title, past}], waiting: '', recap: '', day }
const pickArr = (o, ...ks) => { for (const k of ks) if (Array.isArray(o && o[k])) return o[k]; return []; };
const pickStr = (o, ...ks) => { for (const k of ks) { const v = o && o[k]; if (typeof v === 'string' && v.trim()) return v.trim(); } return ''; };
export function briefFor(brief, botId, nowS) {
  if (!isObj(brief)) return null;
  const day = pickStr(brief, 'day', 'date', 'session');
  if (day && nowS && day !== etParts(nowS).day) return null;           // yesterday's brief is not today's plan
  const bots = brief.bots, b = Array.isArray(bots) ? bots.find((x) => isObj(x) && String(x.id || x.key || x.bot || '').toLowerCase().startsWith(botId)) || null
    : isObj(bots) ? bots[botId] || bots[botId === 'lit' ? 'zlarior' : botId] || null : null;
  const bz = isObj(b && b.bias) ? b.bias : isObj(brief.bias) ? brief.bias : null, bs = typeof brief.bias === 'string' ? brief.bias : '';
  const side = String((bz && (bz.side || bz.call || bz.dir)) || bs || '').toUpperCase().match(/LONG|SHORT|NEUTRAL|FLAT/);
  const bias = side ? { side: side[0] === 'FLAT' ? 'NEUTRAL' : side[0], text: pickStr(bz, 'why', 'text', 'reason', 'line') , conf: num(bz && (bz.conf ?? bz.confidence ?? bz.score)) } : null;
  const levels = pickArr(b, 'levels').concat(b && pickArr(b, 'levels').length ? [] : pickArr(brief, 'levels', 'key_levels')).map((x) => (Array.isArray(x)
    ? { label: String(x[0] || ''), px: num(x[1]), dist: num(x[2]) } : isObj(x) ? { label: String(x.label || x.name || ''), px: num(x.px ?? x.price ?? x.level), dist: num(x.dist ?? x.pts) } : null))
    .filter((x) => x && x.px !== null).slice(0, 6);
  const hm = nowS ? etParts(nowS).hm : '';
  const news = pickArr(brief, 'news', 'events').filter(isObj).filter((e) => !e.date || !day || e.date === day)
    .map((e) => ({ time: String(e.time || e.hm || ''), title: String(e.title || e.name || ''), past: !!(e.time && hm && e.time < hm) })).filter((e) => e.title);
  return { bias, levels, news, waiting: pickStr(b, 'waiting', 'wait', 'waiting_for'), recap: pickStr(b, 'recap', 'after') || pickStr(isObj(brief.recap) ? brief.recap : null, botId) || (typeof brief.recap === 'string' ? brief.recap : ''), day };
}

// ------------------------------------------------------------------------------------------------ 2. the thinking, per bot
const BOTS = [{ id: 'lit', name: 'Zlarior', what: 'LIT', acct: ['lit', 'zlarior'] }, { id: 'atlas', name: 'ATLAS', what: 'EMA · MACD · S/R', acct: ['atlas'] }];

export function todayNews(news, nowS) {
  const d = etParts(nowS), hm = d.hm;
  return arr(isObj(news) ? news.events : null).filter((e) => isObj(e) && e.date === d.day && /high/i.test(e.impact || 'high'))
    .map((e) => ({ time: e.time || '', title: String(e.title || ''), past: !!e.time && e.time < hm }));
}
export function nextNews(news, nowS) {
  const d = etParts(nowS).day;
  return arr(isObj(news) ? news.events : null).filter((e) => isObj(e) && e.date > d && /high/i.test(e.impact || 'high')).sort((a, b) => (a.date + a.time < b.date + b.time ? -1 : 1))[0] || null;
}
/** the lean: the side of the setup it has armed (engine/brain_glance "arm"), else the side its own words name; never guessed */
export function lean(g, card) {
  const a = arr(g && g.arm).find((x) => isObj(x) && /LONG|SHORT/i.test(x.side || ''));
  if (a) return a.text === 'forming' ? { side: a.side.toUpperCase(), why: `setup forming: ${a.trig || ''}`.trim(), trig: '' }
    : { side: a.side.toUpperCase(), why: `setup armed: ${a.text || ''}`.trim(), trig: a.trig || '' };
  const w = `${(g && g.wait) || ''} ${(card && card.waiting) || ''}`, m = /\b(long|short)\b/i.exec(w);
  if (m) return { side: m[1].toUpperCase(), why: 'from what it says it is waiting for', trig: '' };
  return { side: null, why: 'No lean yet: it waits for a sweep before it picks a side.', trig: '' };
}

function tradesOf(home, bot) {
  return arr(isObj(home) && isObj(home.board) ? home.board.trades : null).filter((t) => isObj(t) && bot.acct.includes(String(t.acct || t.key || '').toLowerCase()) && t.src !== 'paper');
}
function reelOf(file, bot, entryT) {
  const rows = arr(isObj(file) ? file.trades : null).filter((r) => isObj(r) && r.src === 'live' && r.bot === (bot.id === 'lit' ? 'LIT' : 'ATLAS') && Math.abs((+r.t || 0) - entryT) <= 600);
  const r = rows.find((x) => x.odeon) || rows[0];
  return r && r.odeon ? '../odeon/#reel=' + encodeURIComponent(r.odeon) : '';
}

export function thinking(home, news, file, nowS, chart, brief) {
  const h = isObj(home) ? home : {}, live = isObj(h.live) ? h.live : {}, board = isObj(h.board) ? h.board : {};
  const glance = isObj(live.pc) && isObj(live.pc.glance) ? live.pc.glance : null, fa = feedAge(h, nowS);
  const day = etParts(nowS).day, tn = todayNews(news, nowS), nx = nextNews(news, nowS);
  const nd = (d) => { const t = Date.parse(d + 'T12:00:00Z'); return isNaN(t) ? d : new Date(t).toLocaleDateString('en-US', { timeZone: 'UTC', weekday: 'short', day: 'numeric', month: 'short' }); };
  return BOTS.map((bot) => {
    const g = glance ? arr(glance.bots).find((b) => isObj(b) && b.id === bot.id) || null : null;
    const card = fa.fromPc && isObj(board[bot.id]) ? board[bot.id] : null;
    const tr = tradesOf(h, bot), open = tr.find((t) => t.open), closed = tr.filter((t) => !t.open && num(t.exit_t)).sort((a, b) => b.exit_t - a.exit_t);
    const last = closed.find((t) => etParts(t.exit_t).day === day) || null;
    const pos = g && isObj(g.pos) ? g.pos : null;
    const co = chartOpen(chart, (k) => (bot.id === 'atlas' ? /^atlas/.test(k) : /^z/.test(k)), nowS);
    const L = lean(g, card), bf = briefFor(brief, bot.id, nowS);
    const lv = arr(g && g.lv).slice(0, 6).filter((x) => Array.isArray(x) && num(x[1]) !== null).map((x) => ({ label: String(x[0] || ''), px: num(x[1]), dist: num(x[2]) }));
    const before = {
      lean: L, news: tn.length || !bf ? tn : bf.news, next: nx ? `${nd(nx.date)} ${nx.time} ET, ${nx.title}` : '',
      bias: bf && bf.bias ? bf.bias : null, recap: bf ? bf.recap : '',
      levels: lv.length ? lv : bf ? bf.levels : [],
      window: String((card && isObj(card.window) && card.window.text) || (card && isObj(card.window) && card.window.open ? 'In its entry window now' : '') || ''),
      windowOpen: !!(card && isObj(card.window) && card.window.open),
      waiting: String((g && g.wait) || (card && card.waiting) || (bf && bf.waiting) || ''), why: String((g && g.why) || ''),
      log: arr(g && g.log).slice(0, 3).filter(Array.isArray).map((x) => `${x[0] ? x[0] + ' ' : ''}${x[1] || ''}`),
    };
    let inTrade = null;
    if (co) {                                  // the chart post: the stop as it is now and the $ at the last bar
      const risk = num(pos && pos.risk_usd);
      inTrade = { ...co, risk, r: risk && co.now !== null ? co.now / risk : null, src: 'chart' };
      if (inTrade.since === null && open) inTrade.since = Math.max(0, nowS - (+open.entry_t || nowS));
    } else if (pos || open) {
      const p = pos || {}, side = String(p.side || (open && open.side) || '').toUpperCase();
      const risk = num(p.risk_usd), now = num(p.now_usd) ?? num(open && open.usd), et = num(open && open.entry_t);
      inTrade = { side, qty: num(p.qty), entry: num(p.entry), stop: num(p.stop), target: num(p.target), risk, target_usd: num(p.tgt_usd), now,
        r: risk && now !== null ? now / risk : num(open && open.r), since: et ? Math.max(0, nowS - et) : null, stopMoved: false, locked: null, lastAge: null };
    }
    if (inTrade && inTrade.side) before.lean = { side: inTrade.side, why: 'in this trade now.', trig: '' };
    const after = last ? { usd: num(last.usd), r: num(last.r), exit: String(last.exit || ''), side: String(last.side || '').toUpperCase(), at: hmET(last.exit_t),
      reel: reelOf(file, bot, +last.entry_t || 0) } : null;
    const phase = inTrade ? 'in' : after ? 'after' : 'before';
    return { id: bot.id, name: bot.name, what: bot.what, phase, has: !!(g || card), on: g ? !!g.on : null, mode: g && g.mode ? String(g.mode) : '',
      age: fa.report, before, inTrade, after };
  });
}

// ------------------------------------------------------------------------------------------------ 4. quality checks
const lvl = (ok, warn) => (ok ? 'ok' : warn ? 'warn' : 'bad');
export function twinCheck(file) {
  const live = arr(isObj(file) ? file.trades : null).filter((r) => isObj(r) && r.src === 'live');
  let match = 0, miss = 0, none = 0; const bad = [];
  for (const r of live) {
    const tw = isObj(r.twin) ? (r.twin.backtest || r.twin.paper) : null;
    if (!isObj(tw)) { none++; continue; }
    if (tw.side === r.side && tw.k === r.k) match++; else { miss++; bad.push(`${r.day} ${r.an || r.bot}: live ${r.side} ${r.k}, twin ${tw.side} ${tw.k}`); }
  }
  return { n: live.length, match, miss, none, bad };
}
export function quality(home, file, news, nowS, edge, chart) {
  const h = isObj(home) ? home : {}, fa = feedAge(h, nowS), live = isObj(h.live) ? h.live : {}, rep = isObj(live.reporter) ? live.reporter : {};
  const rows = [];
  rows.push({ k: 'report', label: 'PC report', value: fa.report === null ? 'not received on this page' : ageText(fa.report),
    level: fa.report === null ? 'bad' : lvl(fa.report <= FRESH_S, fa.report <= 3 * 3600), note: 'every 15 min from your PC' });
  rows.push({ k: 'beat', label: 'Bot heartbeat', value: fa.beat === null ? 'unknown' : ageText(fa.beat),
    level: fa.beat === null ? 'warn' : lvl(fa.beat <= BEAT_STALE_S, fa.beat <= 3600), note: 'the bot beats every 5 min' });
  const built = h.built ? Date.parse(h.built) / 1000 : null;
  const tDay = isObj(file) && isObj(file.data_branch) ? file.data_branch.to : null;
  const fileAge = tDay ? Math.max(0, (Date.parse(etParts(nowS).day) - Date.parse(tDay)) / 86400) : null;
  rows.push({ k: 'data', label: 'Site data', value: `${built ? 'home.json ' + ageText(nowS - built) : 'home.json date unknown'}${tDay ? ` · trades to ${tDay}` : ' · no data-branch upload in trades.json'}`,
    level: lvl(built !== null && nowS - built < 6 * 3600 && fileAge !== null && fileAge <= 3, true), note: 'the cloud build + the nightly trade upload' });
  const na = num(rep.na);
  let alertT = na, how = 'the PC says';
  if (!alertT) {
    const tt = arr(isObj(h.board) ? h.board.trades : null).filter((t) => isObj(t) && t.src !== 'paper').flatMap((t) => [num(t.entry_t), num(t.exit_t)]).filter((x) => x);
    alertT = tt.length ? Math.max(...tt) : null; how = 'the newest entry / exit the PC reported (an alert goes out then)';
  }
  rows.push({ k: 'alert', label: 'Last trade alert', value: alertT ? `${ageText(nowS - alertT)} (${hmET(alertT)})` : 'none in the last report', level: alertT ? 'ok' : 'warn', note: how });
  const tw = twinCheck(file);
  rows.push({ k: 'twin', label: 'PC vs backtest twin', value: tw.n ? `${tw.match} match · ${tw.miss} differ · ${tw.none} no twin yet` : 'no LIVE trade in trades.json',
    level: tw.miss ? 'bad' : tw.n && tw.match ? 'ok' : 'warn', note: tw.bad[0] || 'same side and same exit as the replay = the bot does what the backtest does', bad: tw.bad });
  const news0 = isObj(news) && news.to ? news.to : null;
  rows.push({ k: 'news', label: 'News calendar', value: news0 ? `covers to ${news0}` : 'missing', level: news0 && news0 >= etParts(nowS).day ? 'ok' : 'warn', note: "the bot's high-impact US list" });
  // the chart candles (the PC's le-bars post): about hourly while the bots trade (01:50-16:10 ET weekdays), at once on an entry / exit / stop move
  if (isObj(chart) && num(chart.t)) {
    const ca = Math.max(0, nowS - chart.t), p = etParts(nowS), inHours = !/Sat|Sun/.test(p.wd) && p.hm >= '01:50' && p.hm <= '16:10';
    rows.push({ k: 'bars', label: 'Chart candles', value: `last bar ${ageText(ca)} (${hmET(chart.t)})`, level: !inHours || ca <= 80 * 60 ? 'ok' : ca <= 3 * 3600 ? 'warn' : 'bad',
      note: inHours ? 'the PC sends candles about hourly while the bots trade, and at once on each entry, exit or stop move' : 'outside the bots\' hours the candles rest' });
  }
  // the edge check's inputs (../edge.json, tools/edge_health.py): LIT re-runs on the newest bars; ATLAS reads a stored backtest run that stops when it
  // was made (2026-11-20: Oct 16, LEAD_WIRES nqdash3 F), so its "last 40 sessions" are not the latest 40
  const eh = isObj(edge) && isObj(edge.eh) ? edge.eh : null;
  if (eh) {
    const today = etParts(nowS).day, old = (d) => (d ? Math.round((Date.parse(today) - Date.parse(d)) / 86400000) : null);
    const ad = Array.isArray(eh.a) ? eh.a[3] : null, lo = old(eh.d), ao = old(ad), worstD = Math.max(lo ?? 99, ao ?? 99);
    rows.push({ k: 'edge', label: 'Edge check data', value: `LIT to ${eh.d || '?'}${ad ? ` · ATLAS to ${ad}` : ''}`, level: worstD <= 4 ? 'ok' : worstD <= 10 ? 'warn' : 'bad',
      note: ao !== null && ao > 4 ? `ATLAS's edge light uses a backtest that stops ${ao} days ago: read its PF as old` : 'the ZEUS edge chip on Trading reads this' });
  }
  const worst = rows.some((r) => r.level === 'bad') ? 'bad' : rows.some((r) => r.level === 'warn') ? 'warn' : 'ok';
  return { rows, level: worst, okN: rows.filter((r) => r.level === 'ok').length };
}

// ------------------------------------------------------------------------------------------------ drawing (DOM only from here)
const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = String(text); return e; };
const clear = (n) => { while (n.firstChild) n.removeChild(n.firstChild); };
const DOT = { live: 'Live: the PC reported in the last 20 min', stale: 'Stale: the PC has not reported for over 20 min', plan: 'Planned: no PC numbers yet', off: 'No PC numbers' };

function drawAccounts(box, list) {
  clear(box);
  for (const a of list) {
    const c = el('article', 'dk-acct'); c.dataset.key = a.key; c.dataset.dot = a.dot;
    const top = el('div', 'dk-row'); const n = el('b', 'dk-name', a.name);
    const d = el('span', 'dk-dot ' + a.dot); d.setAttribute('role', 'img'); d.setAttribute('aria-label', DOT[a.dot]); d.title = DOT[a.dot];
    top.appendChild(d); top.appendChild(n); top.appendChild(el('span', 'dk-stage', a.stage)); c.appendChild(top);
    if (!a.has) { c.appendChild(el('p', 'dk-none', a.ageText)); box.appendChild(c); continue; }
    c.appendChild(el('p', 'dk-bal ag-num', money(a.balance)));
    const kv = el('dl', 'dk-kv');
    const add = (k, v, cls) => { kv.appendChild(el('dt', '', k)); kv.appendChild(el('dd', 'ag-num ' + (cls || ''), v)); };
    add('Today', money(a.today, true), a.today > 0.5 ? 'pos' : a.today < -0.5 ? 'neg' : '');
    add('Room left', money(a.room), a.roomFrac !== null && a.roomFrac < 0.3 ? 'neg' : '');
    add(a.goalLabel, a.goalText);
    c.appendChild(kv);
    if (a.roomFrac !== null) {
      const m = el('div', 'dk-meter'); m.setAttribute('role', 'img'); m.setAttribute('aria-label', `${Math.round(a.roomFrac * 100)} percent of the max loss left`);
      const i = el('i', a.roomFrac < 0.3 ? 'bad' : a.roomFrac < 0.55 ? 'warn' : 'ok'); i.style.setProperty('--w', `${Math.round(a.roomFrac * 100)}%`); m.appendChild(i); c.appendChild(m);
    }
    if (a.open) {
      const o = a.open, t = el('p', 'dk-open');
      t.appendChild(el('b', 'dk-side ' + o.side.toLowerCase(), `${o.side} ${o.qty}`));
      t.appendChild(document.createTextNode(` @ ${px(o.entry)}${o.now !== null ? ` · ${money(o.now, true)}` : ''}${o.stopMoved ? ' · stop at break-even' : ''}`));
      c.appendChild(t);
    }
    c.appendChild(el('p', 'dk-age', a.ageText));
    box.appendChild(c);
  }
}

const PH = { before: 'Before the trade', in: 'In the trade', after: 'After the trade' };
function drawThinking(box, bots, opts) {
  clear(box);
  for (const b of bots) {
    const c = el('article', 'dk-bot'); c.dataset.bot = b.id; c.dataset.phase = b.phase;
    const top = el('div', 'dk-row'); const t = el('h3', 'dk-h', b.name + ' '); t.appendChild(el('small', '', b.what)); top.appendChild(t);
    top.appendChild(el('span', 'dk-phase ' + b.phase, PH[b.phase])); c.appendChild(top);
    const steps = el('ol', 'dk-steps'); steps.setAttribute('aria-label', 'Where it is in the trade');
    for (const k of ['before', 'in', 'after']) { const s = el('li', k === b.phase ? 'on' : '', PH[k].replace(' the trade', '')); if (k === b.phase) s.setAttribute('aria-current', 'step'); steps.appendChild(s); }
    c.appendChild(steps);
    if (!b.has) { c.appendChild(el('p', 'dk-none', "No word from the PC yet: its thinking shows here once the 15-minute report arrives.")); box.appendChild(c); continue; }
    // before (always: it is the plan the trade came from)
    const bf = el('section', 'dk-sec'); bf.appendChild(el('p', 'dk-eye', PH.before));
    const L = b.before.lean, ln = el('p', 'dk-lean'); ln.appendChild(el('b', 'dk-side ' + (L.side ? L.side.toLowerCase() : 'none'), L.side ? `Lean ${L.side}` : 'No lean'));
    ln.appendChild(document.createTextNode(' ' + L.why)); bf.appendChild(ln);
    if (L.trig) bf.appendChild(el('p', 'dk-note', L.trig));
    if (b.before.bias) { const z = b.before.bias, p = el('p', 'dk-line'); p.appendChild(el('b', '', 'Morning brief: '));
      p.appendChild(el('span', 'dk-side ' + (z.side === 'NEUTRAL' ? 'none' : z.side.toLowerCase()), z.side)); p.appendChild(document.createTextNode(' ' + (z.text || ''))); bf.appendChild(p); }
    if (b.before.waiting) { const w = el('p', 'dk-line'); w.appendChild(el('b', '', 'Waiting for: ')); w.appendChild(document.createTextNode(b.before.waiting)); bf.appendChild(w); }
    if (b.before.window) { const w = el('p', 'dk-line'); w.appendChild(el('b', '', b.before.windowOpen ? 'Window: open now. ' : 'Window: ')); w.appendChild(document.createTextNode(b.before.window)); bf.appendChild(w); }
    const nw = el('p', 'dk-line'); nw.appendChild(el('b', '', 'News today: '));
    nw.appendChild(document.createTextNode(b.before.news.length ? b.before.news.map((n) => `${n.time} ${n.title}${n.past ? ' (over)' : ''}`).join(' · ') : `none high-impact${b.before.next ? `. Next: ${b.before.next}` : ''}`)); bf.appendChild(nw);
    if (b.before.levels.length) {
      const ul = el('ul', 'dk-levels'); ul.setAttribute('aria-label', 'Key levels it watches');
      for (const l of b.before.levels) { const li = el('li'); li.appendChild(el('span', '', l.label)); li.appendChild(el('b', 'ag-num', px(l.px))); if (l.dist !== null) li.appendChild(el('small', 'ag-num', `${l.dist > 0 ? '+' : ''}${l.dist} pt`)); ul.appendChild(li); }
      bf.appendChild(ul);
    } else bf.appendChild(el('p', 'dk-note', 'Key levels: not in this report (the PC sends them with its brain glance).'));
    if (b.before.why) bf.appendChild(el('p', 'dk-note', 'Last decision: ' + b.before.why));
    c.appendChild(bf);
    if (b.inTrade) {
      const x = b.inTrade, s = el('section', 'dk-sec live'); s.appendChild(el('p', 'dk-eye', PH.in));
      const big = el('p', 'dk-big ag-num ' + (x.now > 0 ? 'pos' : x.now < 0 ? 'neg' : '')); big.textContent = `${x.side} ${x.now !== null ? money(x.now, true) : ''} ${x.r !== null ? rText(x.r) : ''}`.replace(/\s+/g, ' ').trim(); s.appendChild(big);
      const kv = el('dl', 'dk-kv');
      const stopTxt = x.stopMoved ? `${px(x.stop)} · moved to break-even${x.locked !== null && Math.abs(x.locked) >= 1 ? ` (${money(x.locked, true)} locked)` : ''}`
        : `${px(x.stop)}${x.risk !== null ? ` (-${money(x.risk)})` : ''}`;
      for (const [k, v] of [['Size', x.qty ? `${x.qty} MNQ` : '-'], ['Entry', px(x.entry)], ['Stop', stopTxt], ['Target', `${px(x.target)}${x.target_usd !== null ? ` (+${money(x.target_usd)})` : ''}`],
        ['Open $', x.now !== null ? `${money(x.now, true)}${x.last !== undefined && x.last !== null ? ` at ${px(x.last)}` : ''}` : '-'], ['In trade', x.since !== null ? mins(x.since) : '-']]) { kv.appendChild(el('dt', '', k)); kv.appendChild(el('dd', 'ag-num' + (k === 'Stop' && x.stopMoved ? ' pos' : ''), v)); }
      s.appendChild(kv);
      if (x.lastAge !== null) s.appendChild(el('p', 'dk-note', `Open $ is at the last chart bar from the PC (${ageText(x.lastAge)}); the close alert brings the final $ and R.`));
      c.appendChild(s);
    }
    if (b.after) {
      const x = b.after, s = el('section', 'dk-sec'); s.appendChild(el('p', 'dk-eye', PH.after));
      s.appendChild(el('p', 'dk-big ag-num ' + (x.usd > 0 ? 'pos' : x.usd < 0 ? 'neg' : ''), `${money(x.usd, true)} ${rText(x.r)}`.trim()));
      s.appendChild(el('p', 'dk-note', `${x.side} closed by ${x.exit.toLowerCase() || 'the bot'} at ${x.at}.`));
      if (b.before.recap) s.appendChild(el('p', 'dk-note', b.before.recap));
      if (x.reel) { const a = el('a', 'dk-reel', 'Watch the replay'); a.href = x.reel; s.appendChild(a); } else s.appendChild(el('p', 'dk-note', "Replay after tonight's data upload."));
      c.appendChild(s);
    }
    box.appendChild(c);
  }
  if (opts && opts.age != null) box.dataset.age = String(opts.age);
}

function drawQuality(box, q) {
  clear(box);
  const ul = el('ul', 'dk-q');
  for (const r of q.rows) {
    const li = el('li', 'dk-qr ' + r.level); li.dataset.k = r.k;
    const ic = el('span', 'dk-qi ' + r.level, r.level === 'ok' ? '✓' : r.level === 'warn' ? '!' : '×'); ic.setAttribute('aria-label', r.level === 'ok' ? 'OK' : r.level === 'warn' ? 'Check' : 'Problem');
    li.appendChild(ic); const t = el('div', 'dk-qt'); t.appendChild(el('b', '', r.label)); t.appendChild(el('span', 'ag-num', r.value)); t.appendChild(el('small', '', r.note)); li.appendChild(t);
    ul.appendChild(li);
  }
  box.appendChild(ul);
}
export const draw = { accounts: drawAccounts, thinking: drawThinking, quality: drawQuality };
