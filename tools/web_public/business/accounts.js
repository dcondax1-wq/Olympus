// MY ACCOUNTS page (classic script, read only). Plan from ./accounts.json; live eval numbers from the PC (window.PC_FEED over
// ntfy) when it has reported, else ../home.json. Everything is drawn with textContent. BLITZ's account C is never shown.
(function () {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const isObj = (x) => !!x && typeof x === 'object' && !Array.isArray(x);
  const num = (v) => (typeof v === 'number' && Number.isFinite(v) ? v : (typeof v === 'string' && v.trim() !== '' && Number.isFinite(+v) ? +v : null));
  const usd = (v) => (v == null ? '-' : (v < 0 ? '-$' : '$') + Math.abs(Math.round(v)).toLocaleString('en-US'));
  const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = String(text); return e; };

  async function getJSON(u) {
    try { const r = await fetch(u, { cache: 'no-cache' }); if (r.ok) return await r.json(); } catch (e) { /* none */ }
    return null;
  }

  // one live row per PC account: {match: builder50k | builder25k, stage, to_target, room, balance, today, status, session}
  function liveRows(accounts, second) {
    const out = [];
    for (const a of Array.isArray(accounts) ? accounts : []) {
      if (!isObj(a) || !['eval', 'funded'].includes(a.kind) || a.source === 'cloud' || a.source === 'pc_blitz' || a.id === 'acct_c') continue;
      const e = isObj(a.eval) ? a.eval : {};
      const start = num(e.start_balance);
      out.push({ match: start != null && Math.abs(start - 25000) < 1 ? 'builder25k' : 'builder50k', stage: a.kind,
                 to_target: num(e.to_target), room: num(e.room), balance: num(e.balance), today: num(e.today), status: e.status || '', session: num(e.session) });
    }
    const b = isObj(second) ? second.account_b : null;
    if (isObj(b) && isObj(b.eval) && b.enabled !== false && !out.some((r) => r.match === 'builder25k')) {
      const e = b.eval;
      out.push({ match: 'builder25k', stage: b.stage === 'funded' ? 'funded' : 'eval', to_target: num(e.to_target), room: num(e.room),
                 balance: num(e.balance), today: num(e.today), status: e.status || '', session: num(e.session) });
    }
    return out;
  }

  function kv(dl, rows) {
    dl.textContent = '';
    for (const [k, v] of rows) { dl.appendChild(el('dt', null, k)); dl.appendChild(el('dd', null, v)); }
  }

  function card(a, live) {
    const c = el('section', 'ag-card card');
    const top = el('div', 'row2');
    top.appendChild(el('h3', null, a.name));
    top.appendChild(el('span', 'st ' + (a.status || 'waiting'), a.status === 'live' ? (live ? 'LIVE' : 'RUNNING') : a.status === 'buying' ? 'TO BUY' : 'LATER'));
    c.appendChild(top);
    c.appendChild(el('p', 'meta', a.plan + ' · ' + (live && live.stage === 'funded' ? 'funded' : a.stage)));
    const rows = [];
    if (live) {
      const target = a.plan.includes('25K') ? 1500 : 3000, mll = a.plan.includes('25K') ? 1000 : 2000;
      if (live.to_target != null && live.stage !== 'funded') {
        const done = Math.max(0, Math.min(1, (target - live.to_target) / target));
        const bar = el('div', 'bar'); const i = el('i'); i.style.width = Math.round(done * 100) + '%'; bar.appendChild(i);
        c.appendChild(bar);
        rows.push(['To pass', usd(live.to_target) + ' more profit']);
      }
      if (live.room != null) rows.push(['Room left', usd(live.room) + ' of ' + usd(mll) + ' (lose it all = account ends)']);
      if (live.balance != null) rows.push(['Balance', usd(live.balance)]);
      if (live.today != null) rows.push(['Today', usd(live.today)]);
      if (live.session != null) rows.push(['Trading day', '#' + String(live.session)]);
    }
    rows.push(['Bots on it', a.bots || '-']);
    rows.push(['Next step', a.next || '-']);
    rows.push(['First payout', a.payout || '-']);
    rows.push(['$ a month', (a.usd_month || '-') + ' (estimate)']);
    rows.push(['Cost', a.cost || '-']);
    const dl = el('dl'); kv(dl, rows); c.appendChild(dl);
    return c;
  }

  async function main() {
    const plan = (await getJSON('accounts.json')) || { accounts: [], decisions: [], rules: [] };
    const home = await getJSON('../home.json');
    let accounts = isObj(home) ? home.accounts : null, src = isObj(home) ? 'site' : '', t = 0;
    try {
      if (window.PC_FEED) {
        const lite = await window.PC_FEED.fetchLatest({});
        if (isObj(lite) && Array.isArray(lite.accounts) && lite.accounts.length) { accounts = lite.accounts; src = 'pc'; t = +lite.t || 0; }
      }
    } catch (e) { /* plan only */ }
    const live = liveRows(accounts, isObj(home) ? home.second : null);
    const used = new Set();
    const list = $('list'); list.textContent = '';
    for (const a of plan.accounts || []) {
      let l = null;
      if (a.status === 'live' && a.match) {
        const i = live.findIndex((r, k) => !used.has(k) && r.match === a.match);
        if (i >= 0) { used.add(i); l = live[i]; }
      }
      list.appendChild(card(a, l));
    }
    const n = (s) => (plan.accounts || []).filter((a) => a.status === s).length;
    const cost = (plan.accounts || []).filter((a) => a.status !== 'live').map((a) => { const m = String(a.cost || '').match(/\d+(\.\d+)?/); return m ? +m[0] : null; }).filter((v) => v != null);
    kv($('sum'), [['Running now', String(n('live'))], ['To buy now', String(n('buying'))], ['Later (if MFFU says yes)', String(n('waiting'))],
                  ['Cost to buy the new ones', cost.length ? '~' + usd(cost.reduce((x, y) => x + y, 0)) : '-'], ['Plan updated', plan.updated || '-']]);
    const dec = $('dec'); dec.textContent = '';
    for (const d of plan.decisions || []) dec.appendChild(el('li', null, d));
    kv($('rules'), (plan.rules || []).map((r) => [r[0], r[1]]));
    $('limits').textContent = plan.limits || '';
    $('foot').textContent = plan.note || '';
    const age = t ? Math.max(0, Math.round((Date.now() / 1000 - t) / 60)) : null;
    $('status').textContent = src === 'pc' ? 'Live numbers from your PC, ' + (age < 1 ? 'just now' : age + ' min ago') + '.'
      : src === 'site' ? 'Numbers from the last site update. Your PC has not reported here yet.' : 'Plan only. No live numbers yet.';
  }
  main();
})();
