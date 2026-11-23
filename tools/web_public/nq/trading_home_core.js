// TRADING HOME core (owner 2026-11-22): the 5-line "Today" checklist (+ a READY / NOT READY line first when the post carries the PC's ready check) from the PC's PUBLIC status post only (status_feed.json,
// read by ../pc_feed.js). Pure: no DOM, no fetch. Browser: window.TRADING_HOME; node tests: module.exports. Sends nothing, arms nothing.
// Each line: {id, ok: true | false | null (null = the phone cannot see it), title, say (plain words), menu (the TRADE_HOME number on the PC)}.
(function (root) {
  'use strict';
  const isObj = (x) => x !== null && typeof x === 'object' && !Array.isArray(x);
  const num = (v) => (v == null || v === '' || !Number.isFinite(+v) ? null : +v);
  const usd = (n) => '$' + Math.round(Math.abs(n)).toLocaleString('en-US');
  const FRESH_S = 30 * 60, ALERT_OK_DAYS = 30;

  function ageText(s) {
    if (s == null) return 'never';
    s = Math.max(0, Math.round(s));
    return s < 90 ? s + ' s' : s < 5400 ? Math.round(s / 60) + ' min' : (s / 3600).toFixed(1) + ' h';
  }
  const realAccounts = (lite) => (Array.isArray(lite && lite.accounts) ? lite.accounts : [])
    .filter((a) => isObj(a) && a.id && !/blitz/i.test(String(a.id)) && a.source !== 'cloud');
  const nameOf = (a) => String(a.name || a.id).replace(/^MFFU\s+/i, '');

  // the next money step in $ for the closest account: an eval needs +$X to pass, a funded one $X more to the max payout
  function nextStep(lite, mffuView) {
    const out = [];
    for (const a of realAccounts(lite)) {
      const ev = isObj(a.eval) ? a.eval : {};
      const funded = /funded/i.test(String(a.kind || '') + ' ' + String(a.stage || '') + ' ' + String(a.plan || '') + ' ' + String(ev.status || ''));
      if (funded && typeof mffuView === 'function') {
        let v = null;
        try { v = mffuView({ kind: 'funded', plan: a.plan, name: a.name, id: a.id, balance: ev.balance, room: ev.room, floor: ev.floor }); } catch (e) { v = null; }
        if (v && v.goal && v.goal.need != null) { out.push({ n: v.goal.need, t: nameOf(a) + ': ' + (v.goal.ready ? 'ask the ' + usd(v.goal.ask) + ' payout now' : usd(v.goal.need) + ' more profit, then ask the ' + usd(v.goal.ask) + ' payout') }); continue; }
      }
      const tt = num(ev.to_target);
      if (!funded && tt != null) out.push({ n: Math.max(0, tt), t: nameOf(a) + ' needs +' + usd(tt) + ' to pass the eval' });
    }
    out.sort((x, y) => x.n - y.n);
    return out.length ? out[0].t : null;
  }

  // night-truth 2026-11-22: one line per account (Zlarior 50K, ATLAS, every extra account): armed / running, room $, today $, next
  // window. Armed comes from the core's "ar" (engine/brain_glance.armed_map: 1 = armed and the live gate passed); the badge "LIVE" only
  // says the account is a real one (an older PC without "ar": the badge, marked "?").
  const size = (t) => { const m = /(25|50|100|150)\s*k/i.exec(String(t || '')); return m ? m[1] + 'K' : ''; };
  function winText(c) {
    const w = isObj(c) && isObj(c.window) ? c.window : null;
    if (!w) return null;
    if (w.open) return 'window open now';
    return String(w.text || '').replace(/^next entry window\s*/i, 'next ') || null;
  }
  function accountRows(lite) {
    const L = isObj(lite) ? lite : {};
    const bd = isObj(L.board) ? L.board : {}, ar = isObj(L.ar) ? L.ar : null, pc = isObj(L.pc) ? L.pc : {};
    const lit = isObj(bd.lit) ? bd.lit : null, atl = isObj(bd.atlas) ? bd.atlas : null;
    const litWin = winText(lit), rows = [];
    const armedOf = (id, badge) => (ar && id in ar ? { v: ar[id] === 1 || ar[id] === true, sure: true }
      : badge == null ? { v: null, sure: false } : { v: String(badge).toUpperCase() === 'LIVE', sure: false });
    if (lit) rows.push({ id: 'lit', name: String(lit.name || 'Zlarior') + ' ' + (size(lit.plan) || '50K'), armed: armedOf('lit', lit.badge),
      run: L.board && L.board.running != null ? !!L.board.running : pc.running, room: num(lit.room), today: num(lit.today_pnl), win: litWin, funded: false });
    if (atl && atl.configured !== false) rows.push({ id: 'atlas', name: 'ATLAS ' + (size(atl.plan) || '25K') + (/funded/i.test(String(atl.status || atl.plan || '')) ? ' funded' : ''),
      armed: armedOf('atlas', atl.badge), run: L.board && L.board.running != null ? !!L.board.running : pc.running, room: num(atl.room),
      today: num(atl.today_pnl), win: winText(atl), funded: /funded/i.test(String(atl.status || '')) });
    for (const a of realAccounts(L)) {
      const ev = isObj(a.eval) ? a.eval : {};
      if (a.id === 'atlas' || a.id === 'mffu50k_eval') continue;
      if (lit && num(ev.balance) === num(lit.balance) && num(ev.floor) === num(lit.floor)) continue;   // the bot's main account = the lit card
      const conn = isObj(a.conn) ? a.conn : {};
      const nm = /rapid/i.test(String(a.id) + ' ' + String(a.plan || '')) ? 'Rapid EOD ' + (size(a.plan) || size(a.name) || '')
        : String(a.name || a.id).replace(/^MFFU\s+/i, '').replace(/\bBuilder\s+/i, '');
      rows.push({ id: String(a.id), name: nm.trim(), armed: armedOf(String(a.id), a.badge), run: conn.running != null ? !!conn.running : a.running,
        room: num(ev.room), today: num(ev.today) != null ? num(ev.today) : num(isObj(a.pnl) ? a.pnl.today : null), win: litWin,
        funded: String(a.kind || '') === 'funded' });
    }
    return rows;
  }
  function rowText(r) {
    const arm = r.armed.v === true ? 'ARMED' : r.armed.v === false ? 'NOT armed' : 'armed ?';
    const run = r.run === true ? 'running' : r.run === false ? 'STOPPED' : 'running ?';
    const sg = (n) => (n == null ? '-' : (n > 0.5 ? '+' : n < -0.5 ? '-' : '') + usd(n));
    return arm + (r.armed.sure || r.armed.v == null ? '' : ' ?') + ', ' + run + ' · room ' + (r.room == null ? '-' : usd(r.room)) +
      ' · today ' + sg(r.today) + ' · ' + (r.win || 'next window: -');
  }

  function today(lite, o) {
    o = o || {};
    const now = num(o.now) != null ? +o.now : Date.now() / 1000;
    const L = isObj(lite) ? lite : null;
    const age = L && num(L.t) ? now - +L.t : null;
    const fresh = age != null && age <= FRESH_S;
    const accts = L ? realAccounts(L) : [];
    const out = [];

    // 0 READY / NOT READY (engine/readiness via the status post's "rd" block, day-ready 2026-11-22): the PC's own pre-window self-check
    const rd = L && fresh && isObj(L.rd) ? L.rd : null;
    const rds = rd && (rd.s === 'ok' || rd.s === 'warn' || rd.s === 'no') ? rd.s : null;
    if (rds) out.push({ id: 'ready', ok: rds === 'ok' || rds === 'warn' ? true : rds === 'no' ? false : null, tone: rds === 'no' ? 'gold' : rds ? 'mint' : null, title: 'Ready to trade',
      say: rds === 'ok' ? 'READY' + (rd.w ? ' for ' + rd.w : '') + '. The PC checked its clock, NinjaTrader, bars and accounts.' :
        rds === 'warn' ? 'READY, 1 to watch: ' + (rd.b || 'see the PC') + '.' :
        'NOT READY' + (rd.w ? ' for ' + rd.w : '') + ': ' + (rd.b || 'see the PC') + '. ' + (rd.f || 'On the PC: double-click HEALTH_CHECK.bat.'),
      menu: rds === 'no' ? 1 : null });

    // 1 bot running
    let run = null;
    if (L && fresh) {
      const flags = [isObj(L.board) ? L.board.running : undefined, isObj(L.pc) ? L.pc.running : undefined].concat(accts.map((a) => (isObj(a.conn) ? a.conn.running : undefined)));
      run = flags.some((f) => f === true) ? true : flags.some((f) => f === false) ? false : null;
    }
    out.push({ id: 'bot', ok: !L || !fresh ? false : run, title: 'Bot running',
      say: run === true ? 'Running. The PC reported ' + ageText(age) + ' ago.' :
        !L ? 'No report from the PC at all. On the PC: double-click TRADE_HOME, press 2 (Start bot).' :
        !fresh ? 'The PC has been silent ' + ageText(age) + '. On the PC: double-click TRADE_HOME, press 1 to look, then 2 (Start bot).' :
        'The bot is not running. On the PC: double-click TRADE_HOME, press 2 (Start bot) and type the phrase.',
      menu: run === true ? null : 2 });

    // 2 keep-alive
    const rows = L && isObj(L.k7) && Array.isArray(L.k7.a) ? L.k7.a.filter((r) => isObj(r) && r.on != null) : [];
    const off = rows.filter((r) => r.on !== true);
    const kok = !rows.length ? null : off.length === 0;
    out.push({ id: 'keepalive', ok: kok, title: 'Keep-alive on',
      say: kok === true ? 'On for ' + rows.length + ' account(s): MFFU will not close them for 7 idle days.' :
        kok === false ? 'Off for ' + off.map((r) => r.nm || r.id).join(', ') + '. On the PC: TRADE_HOME, press 3, type KEEP ALIVE ON yourself.' :
        'The phone cannot see it. On the PC: TRADE_HOME, press 1 (Status), or press 3 to turn it on.',
      menu: kok === true ? null : 3 });

    // 3 alerts: the public post does not carry it, so the owner ticks it after a test alert reached his phone
    const at = num(o.alertsOkAt);
    const aok = at != null && now - at <= ALERT_OK_DAYS * 86400;
    out.push({ id: 'alerts', ok: aok, title: 'Phone alerts OK',
      say: aok ? 'You saw a test alert ' + Math.max(0, Math.round((now - at) / 86400)) + ' day(s) ago.' :
        'Not checked lately. On the PC: TRADE_HOME, press 5 (Phone alerts), send a test, then tap "I got my test alert" below.',
      menu: aok ? null : 5, tick: true });

    // 4 every account armed: the core's "ar" (1 = armed + live gate passed) for every account row; an older PC: badge LIVE as before
    const rowsA = L ? accountRows(L) : [];
    const held = rowsA.filter((r) => r.armed.v !== true);
    const arm = !L || !fresh ? null : !rowsA.length ? false : held.length === 0;
    out.push({ id: 'armed', ok: arm, title: 'Every account armed',
      say: arm === true ? rowsA.length + ' account(s) armed.' :
        !rowsA.length && L && fresh ? 'No account is on the bot yet. On the PC: TRADE_HOME, press 4 (Add an account).' :
        arm === false ? held.map((r) => r.name).join(', ') + ' not armed. On the PC: TRADE_HOME, press 2 (Start bot) and type the phrase yourself.' :
        'Cannot tell: the PC is silent. On the PC: TRADE_HOME, press 1 (Status).',
      menu: arm === true ? null : rowsA.length || !L || !fresh ? 2 : 4 });
    // 4b one line per account (owner's ask): armed / running, room $, today $, next window
    for (const r of rowsA) {
      out.push({ id: 'acct:' + r.id, ok: !fresh ? null : r.armed.v === true && r.run === true ? true : false, title: r.name,
        say: (fresh ? '' : 'Old report (' + ageText(age) + '): ') + rowText(r), menu: null, acct: true });
    }

    // 5 next money step
    const step = L ? nextStep(L, o.mffuView) : null;
    out.push({ id: 'next', ok: step != null ? true : null, title: 'Next step in $',
      say: step != null ? step : 'No account numbers yet. On the PC: TRADE_HOME, press 1 (Status).', menu: step != null ? null : 1 });
    return { age, fresh, lines: out, left: out.filter((x) => x.ok !== true).length };
  }

  const API = { today, nextStep, ageText, accountRows, rowText, FRESH_S, ALERT_OK_DAYS };
  root.TRADING_HOME = API;
  if (typeof module !== 'undefined' && module.exports) module.exports = API;
})(typeof window !== 'undefined' ? window : globalThis);
