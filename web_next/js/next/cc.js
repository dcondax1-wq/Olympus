// PC Command center and its read-only companions: Goals, All features, Runbook, Audit evidence, ATLAS setups, Trade log,
// Session calendar. Sources (all GET, nothing here starts, arms, routes, sizes or stops anything):
//   /api/next/cc/home  /cc/calendar  /cc/handoff  /cc/doc?name=  /cc/setups  /cc/atlas_trades  /cc/runbook  /cc/data_files
//   (engine/pc_cc_api.py), /api/next/goals (engine/goals.py, merged later: the Goals page falls back when it 404s),
//   /api/next/trades (LIT replay), /api/next/pc/account (PC routed trades), /api/next/scale (scaling plan).
// The kill switch stays HOLD TO KILL on Bot Control; no button on these pages talks to the bot.
import { $, $$, api, esc, store, toast, downloadFile } from '../util.js';
import { icon } from './icons.js';
import { md } from './lab.js';

// ------------------------------------------------------------------ helpers (the operator pages' card / stat / chip look)
const ok = (v) => v != null && v !== '' && !Number.isNaN(+v);
const usd = (v, d = 0) => (!ok(v) ? '—' : (v < 0 ? '−' : '') + '$' + Math.abs(+v).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d }));
const susd = (v) => (!ok(v) ? '—' : (v > 0 ? '+' : '') + usd(v));
const px = (v) => (ok(v) ? (+v).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '—');
const pct = (v, d = 0) => (ok(v) ? (+v).toFixed(d) + '%' : '—');
const cl = (v) => (v > 0 ? 'up' : v < 0 ? 'dn' : '');
const ETF = new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' });
const hm = (t) => (ok(t) ? ETF.format(new Date(t * 1000)) : '—');
const ago = (s) => (!ok(s) ? '—' : s < 90 ? `${Math.round(s)} s` : s < 5400 ? `${Math.round(s / 60)} min` : s < 172800 ? `${(s / 3600).toFixed(1)} h` : `${Math.round(s / 86400)} d`);
const card = (title, body, tools = '', extra = '') => `<div class="card nx-glass cc-card ${extra}"><div class="card-h"><h3>${title}</h3>${tools ? `<div class="card-tools">${tools}</div>` : ''}</div>${body}</div>`;
const hero = (eyebrow, title, desc, side = '') => `<div class="nx-hero cc-hero"><div><div class="nx-eyebrow">${eyebrow}</div><h2>${title}</h2>${desc ? `<p class="muted">${desc}</p>` : ''}</div>${side}</div>`;
const stat = (k, v, sub = '', c = '') => `<div class="nx-stat"><span>${k}</span><b class="${c}">${v}</b>${sub ? `<em>${sub}</em>` : ''}</div>`;
const chip = (t, k = '') => `<span class="nx-chip ${k}">${t}</span>`;
const go = (id, label, ic = 'right') => `<button type="button" class="nx-chipbtn" data-goto="${id}">${icon(ic)}<span>${esc(label)}</span></button>`;
const empty = (t, s = '') => `<div class="pc-empty"><b>${t}</b>${s ? `<span>${s}</span>` : ''}</div>`;
const src = (t) => `<p class="pc-src">${icon('info')}<span>${t}</span></p>`;
const dot = (v) => `<span class="op-dot ${v === true ? 'good' : v === false ? 'bad' : 'warn'}"></span>`;
const active = (id) => document.getElementById('page-' + id)?.classList.contains('active');
const errBox = (e) => card('Could not load', empty(esc(e?.message || e?.error || String(e)), 'Read-only page: try again in a few seconds.'));
async function getJ(u) { const r = await fetch(u); const d = await r.json().catch(() => ({})); if (!r.ok || d.error) { const e = new Error(d.error || 'HTTP ' + r.status); e.status = r.status; throw e; } return d; }
const bar = (frac, kind = '') => `<div class="cc-bar ${kind}"><i style="width:${Math.max(0, Math.min(100, (frac || 0) * 100)).toFixed(1)}%"></i></div>`;
function copy(text) {
  (navigator.clipboard?.writeText(text) || Promise.reject()).then(() => toast('Copied')).catch(() => {
    const t = document.createElement('textarea'); t.value = text; document.body.appendChild(t); t.select();
    try { document.execCommand('copy'); toast('Copied'); } catch { toast('Copy failed: select the text by hand'); } t.remove();
  });
}
document.addEventListener('click', (e) => { const b = e.target.closest('[data-copy]'); if (b) { e.preventDefault(); copy(b.dataset.copy); } });
function toCSV(rows, cols) {
  cols = cols || Object.keys(rows[0] || {});
  const q = (v) => { const s = v == null ? '' : Array.isArray(v) ? v.join(' | ') : String(v); return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s; };
  return [cols.join(','), ...rows.map((r) => cols.map((c) => q(r[c])).join(','))].join('\n');
}
const csvBtn = (id, label = 'CSV') => `<button type="button" class="nx-chipbtn" id="${id}">${icon('download')}<span>${label}</span></button>`;

// ================================================================== 1. Command center (home)
const H = { d: null, at: 0, timer: null, paused: store.get('nx.cc.paused', false) };

function acctCard(a, kind) {
  if (!a) return card(kind === 'lit' ? 'LIT · Builder 50K' : 'ATLAS · Builder 25K', empty('No data yet'));
  if (a.error) return card(esc(a.name || kind), empty('Could not read this account', esc(a.error)));
  const start = (a.target_balance || 0) - (kind === 'lit' ? 3000 : 1500);
  const prog = ok(a.progress) ? +a.progress : ok(a.profit) && a.target_balance ? Math.max(0, a.profit / (a.target_balance - start)) : 0;
  const roomMax = kind === 'lit' ? 2000 : 1000;
  const roomF = ok(a.room) ? Math.max(0, Math.min(1, a.room / roomMax)) : 0;
  const roomKind = roomF < 0.25 ? 'bad' : roomF < 0.5 ? 'warn' : 'good';
  const st = String(a.status || '').toLowerCase();
  const stK = st === 'passed' ? 'good' : st === 'failed' || st === 'stuck' ? 'bad' : st === 'not set up' ? 'warn' : '';
  const pos = a.position;
  const posHtml = pos ? `<div class="cc-pos">
      <div class="cc-pos-h">${chip(esc(pos.side || (pos.dir > 0 ? 'LONG' : 'SHORT')), pos.dir > 0 || pos.side === 'LONG' ? 'good' : 'bad')}<b>${esc(pos.qty ?? '')} MNQ @ ${px(pos.entry)}</b>
        ${ok(pos.unrealized_usd) ? `<b class="${cl(pos.unrealized_usd)}">${susd(pos.unrealized_usd)}</b>` : ''}</div>
      <div class="cc-pos-g"><span>Stop <b>${px(pos.stop)}</b></span><span>Target <b>${px(pos.target)}</b></span>
        <span>${pos.be ? 'At breakeven' : `BE at <b>${px(pos.be_trigger)}</b>`}</span><span>In trade <b>${ago(pos.time_in_s)}</b></span>
        ${ok(pos.risk_usd) ? `<span>Risk <b>${usd(pos.risk_usd)}</b></span>` : ''}${ok(pos.target_usd) ? `<span>Target pays <b>${usd(pos.target_usd)}</b></span>` : ''}</div></div>`
    : `<div class="cc-flat">${icon('check')}<span>Flat: no open position</span></div>`;
  const anc = kind === 'lit' && a.launch_anchor ? `<div class="cc-note">${icon('info')}<span>Launch anchor (MFFU, ${esc(a.launch_anchor.as_of)}): balance ${usd(a.launch_anchor.balance, 2)}, floor ${usd(a.launch_anchor.floor, 2)}, ${usd(a.launch_anchor.target_balance - a.launch_anchor.balance, 2)} to go.${a.anchor ? ' Loaded in the bot.' : ''}</span></div>` : '';
  return `<div class="card nx-glass cc-card cc-acct ${kind}">
    <div class="cc-acct-h"><div><div class="nx-eyebrow">${esc(a.strategy)} · ${esc(a.plan || '')}</div><h3>${esc(a.name)}</h3>
      <div class="cc-sub">${a.broker_account ? esc(a.broker_account) + ' · ' : ''}${a.badge ? chip(esc(a.badge), a.badge === 'LIVE' ? 'bad' : '') : ''} ${chip(esc(a.status || 'open'), stK)}</div></div>
      <div class="cc-big"><span>Balance</span><b>${usd(a.balance, 2)}</b><em class="${cl(a.profit)}">${susd(a.profit)} in this eval</em></div></div>
    <div class="cc-meter"><div class="cc-meter-h"><span>Progress to target ${usd(a.target_balance)}</span><b>${pct(prog * 100)}</b></div>${bar(prog, 'accent')}
      <div class="cc-meter-s"><span>${usd(a.to_target)} to go</span><span>${a.session ? `session ${a.session} of ${a.sessions || 10}` : 'not started'}</span></div></div>
    <div class="cc-meter"><div class="cc-meter-h"><span>Room to floor ${usd(a.floor, 2)}</span><b class="${roomKind === 'bad' ? 'dn' : ''}">${usd(a.room)}</b></div>${bar(roomF, roomKind)}
      <div class="cc-meter-s"><span>${roomF < 0.25 ? 'thin: the bot sizes down' : 'trailing drawdown cushion'}</span><span>of ${usd(roomMax)}</span></div></div>
    <div class="nx-stats cc-mini">${stat('Today', susd(a.today_pnl), '', cl(a.today_pnl))}${stat('Trades today', `${a.trades_today ?? 0} / ${a.max_trades_day}`)}
      ${stat('Daily loss used', ok(a.dll_used) ? usd(a.dll_used) : '—', ok(a.dll) ? `of ${usd(a.dll)}` : '')}${a.week_pnl != null ? stat('This week', susd(a.week_pnl), '', cl(a.week_pnl)) : ''}</div>
    ${posHtml}${a.note ? `<div class="cc-note warn">${icon('warn')}<span>${esc(a.note)}</span></div>` : ''}${a.disabled ? `<div class="cc-note warn">${icon('warn')}<span>${esc(a.disabled)}</span></div>` : ''}${a.locked ? `<div class="cc-note warn">${icon('warn')}<span>${esc(a.locked)}</span></div>` : ''}${anc}
    <div class="cc-acct-f">${go(kind === 'lit' ? 'accounts' : 'atlas', kind === 'lit' ? 'Account' : 'ATLAS', 'wallet')}${go('goals', 'Goals', 'target')}${go('evaltl', 'Eval timeline', 'calendar')}</div></div>`;
}

function lightsHtml(L) {
  if (!L?.length) return empty('No health data');
  return `<div class="cc-lights">${L.map((l) => `<div class="cc-light ${l.ok === true ? 'good' : l.ok === false ? 'bad' : 'idle'}" title="${esc(l.fix || l.detail)}">
    ${dot(l.ok)}<div><b>${esc(l.label)}</b><span>${esc(l.detail)}</span>${l.ok === false && l.fix ? `<button type="button" class="cc-fix" data-copy="${esc(l.fix)}">${icon('copy')}<em>${esc(l.fix)}</em></button>` : ''}</div></div>`).join('')}</div>`;
}

// the launch checklist (engine/launch_check.py via /api/next/cc/home "launch"): on top until every line is green
function launchHtml(Lc) {
  if (!Lc || Lc.error || !Array.isArray(Lc.items)) return '';
  const st = (s) => (s === 'good' ? true : s === 'bad' ? false : null);
  const counted = Lc.items.filter((i) => i.state !== 'info');
  const good = counted.filter((i) => i.state === 'good').length;
  if (Lc.all_green) return `<div class="cc-banner good cc-launch-ok">${icon('check')}<span><b>Launch checklist: all ${counted.length} green.</b> Arming stays your own step (docs/GO_LIVE_TONIGHT.md).</span></div>`;
  return card(`${icon('flag')}Launch checklist · ${good} of ${counted.length} green`,
    `${bar(good / Math.max(1, counted.length), 'good')}<div class="cc-lights cc-launch">${Lc.items.map((l) => `<div class="cc-light ${l.state === 'good' ? 'good' : l.state === 'bad' ? 'bad' : 'idle'}">
      ${dot(st(l.state))}<div><b>${esc(l.label)}</b><span>${esc(l.detail)}</span>${l.state === 'bad' && l.fix ? `<button type="button" class="cc-fix" data-copy="${esc(l.fix)}">${icon('copy')}<em>${esc(l.fix)}</em></button>` : ''}</div></div>`).join('')}</div>
    <p class="muted small">Launch 18:00 ET; the bot must run from 01:55 ET. Each red line: click its command to copy it. Read-only: nothing here arms or starts the bot.</p>`,
    '', 'cc-launch-card');
}

function nextStep(d) {
  const red = (d.lights || []).find((l) => l.ok === false);
  if (red) return { k: 'bad', t: `${red.label}: ${red.detail}`, fix: red.fix };
  if (!d.running) return { k: 'warn', t: 'The bot is stopped. When NinjaTrader is open and connected, start it on Bot Control.', go: 'botctl' };
  if ((d.lights || []).some((l) => l.key === 'startup' && l.ok == null)) return { k: 'warn', t: 'Waiting for STARTUP RECONCILED (a poll or two). Nothing to do unless it stays red.' };
  return { k: 'good', t: 'All green. Nothing to do: the bot trades on its own. Check back after the entry window.' };
}

function banners(d) {
  const day = d.day || {}, out = [];
  if (day.closed) out.push(`<div class="cc-banner bad">${icon('warn')}<span><b>Market closed today</b> (CME holiday). No session.</span></div>`);
  if (day.early_close) out.push(`<div class="cc-banner warn">${icon('clock')}<span><b>Early close today at ${esc(day.early_close)} ET.</b> The bot moves its flat time and entry cutoff before the halt.</span></div>`);
  if (day.dst) out.push(`<div class="cc-banner warn">${icon('clock')}<span><b>Clock change in ${day.dst.days} day(s): ${esc(day.dst.date)}.</b> ${esc(day.dst.text)}</span></div>`);
  const hi = (day.news?.events || []).filter((e) => e.tier1);
  if (hi.length) out.push(`<div class="cc-banner warn">${icon('news')}<span><b>High-impact news today:</b> ${hi.map((e) => `${esc(e.time || hm(e.t))} ${esc(e.title)}`).join(' · ')}. Entries pause 2 min around Tier-1 releases.</span></div>`);
  return out.join('');
}

function statusText(d) {
  const L = d.lit || {}, A = d.atlas || {};
  const lines = [`Liquidity Engine status ${d.et}`, `Verdict: ${d.verdict?.label || '?'} (${d.verdict?.reason || ''})`,
    `LIT 50K: balance ${usd(L.balance, 2)}, ${usd(L.to_target)} to target, room ${usd(L.room)}, today ${susd(L.today_pnl)}${L.position ? `, IN TRADE ${L.position.side} ${L.position.qty}` : ', flat'}`,
    `ATLAS 25K: ${A.configured === false ? 'not set up' : `balance ${usd(A.balance, 2)}, ${usd(A.to_target)} to target, room ${usd(A.room)}, today ${susd(A.today_pnl)}`}`,
    `Waiting for: ${d.waiting?.say || ''}`,
    `Health: ${(d.lights || []).map((l) => `${l.label} ${l.ok === true ? 'OK' : l.ok === false ? 'RED' : '-'}`).join(', ')}`,
    `Version ${d.version || '?'}`];
  return lines.join('\n');
}

function phaseHtml(p) {
  if (!p) return '';
  const left = ok(p.min_left) ? `${Math.floor(p.min_left / 60)} h ${p.min_left % 60} min` : '';
  return `<div class="cc-phase ${p.entries ? 'on' : ''}">${dot(p.entries ? true : null)}<div><b>${esc(p.label)}</b><span>${esc(p.next)}${left ? ` in ${left}` : ''}</span></div></div>`;
}

function renderHome() {
  const el = $('#page-cc'); if (!el) return;
  const d = H.d;
  if (!d) { el.innerHTML = hero('Command center', 'Loading…', '') + `<div class="cc-skel"></div>`; return; }
  if (d.error) { el.innerHTML = hero('Command center', 'Both accounts at a glance', '') + errBox(d); return; }
  const v = d.verdict || {};
  const lvl = v.level === 'good' ? 'good' : v.level === 'bad' ? 'bad' : 'warn';
  const ns = nextStep(d);
  const w = d.waiting || {};
  el.innerHTML = hero(`Command center · ${esc(d.et || '')}`, 'Both accounts at a glance',
    'LIT on the MFFU Builder 50K and ATLAS on the Builder 25K. Read-only: nothing here sends an order.',
    `<div class="op-verdict ${lvl}">${dot(lvl === 'good' ? true : lvl === 'bad' ? false : null)}<b>${esc(v.label || (d.running ? 'RUNNING' : 'STOPPED'))}</b><em>${esc(v.reason || '')}</em></div>`) +
    launchHtml(d.launch) + banners(d) +
    `<div class="cc-now ${ns.k}">${icon(ns.k === 'good' ? 'check' : 'warn')}<div><span class="nx-eyebrow">What to do now</span><b>${esc(ns.t)}</b></div>
      ${ns.fix ? `<button type="button" class="nx-chipbtn" data-copy="${esc(ns.fix)}">${icon('copy')}<span>Copy the fix</span></button>` : ns.go ? go(ns.go, 'Bot Control', 'power') : ''}</div>
    <div class="cc-two">${acctCard(d.lit, 'lit')}${acctCard(d.atlas, 'atlas')}</div>
    <div class="grid cols-2 cc-row">
      ${card('What the bot is waiting for', `<div class="cc-wait"><b>${esc(w.say || '—')}</b>${w.model_state ? `<span class="mono">${esc(w.model_state)}</span>` : ''}
        ${(w.setups_today || []).length ? `<div class="cc-setups">${w.setups_today.map((s) => `<div>${chip(esc(s.side), s.side === 'LONG' ? 'good' : 'bad')}<span>${esc(s.level || '')} · limit ${px(s.limit)} · stop ${px(s.stop)} · ${ok(s.rr) ? (+s.rr).toFixed(1) + 'R' : ''}</span><em>${hm(s.t)}</em></div>`).join('')}</div>` : '<span class="muted small">No LIT setup yet today.</span>'}</div>
        ${phaseHtml(d.day?.phase)}`, go('brain', 'Bot Brain', 'brain') + go('livechart', 'Live chart', 'chart'))}
      ${card('Health lights', lightsHtml(d.lights), go('ntpanel', 'NinjaTrader', 'sources') + go('runbook', 'Runbook', 'rules'))}
    </div>
    <div class="grid cols-2 cc-row">
      ${card('News today', (d.day?.news?.events || []).length ? `<ul class="op-list">${d.day.news.events.map((e) => `<li><span class="op-t mono">${esc(e.time || hm(e.t))}</span><span class="op-k ${e.tier1 ? 'news' : ''}">${icon(e.tier1 ? 'warn' : 'dot')}</span><span class="op-x">${esc(e.title)}${e.impact ? ` <span class="muted small">${esc(e.impact)}</span>` : ''}</span><span></span></li>`).join('')}</ul>` : empty('No USD events listed for today.'), go('newshub', 'News hub', 'radar'))}
      ${card('Latest bot log', (d.log || []).length ? `<ul class="op-list">${d.log.map((r) => `<li><span class="op-t mono">${hm(r.t)}</span><span class="op-k ${r.type === 'risk' || r.type === 'error' || r.type === 'kill' ? 'stop' : r.type === 'order' ? 'entry' : ''}">${icon(r.type === 'order' ? 'play' : r.type === 'system' ? 'info' : 'warn')}</span><span class="op-x">${esc(r.text)}</span><span></span></li>`).join('')}</ul>` : empty('No log rows yet.'), go('botlog', 'Bot log', 'reports'))}
    </div>
    <div class="cc-foot">
      <span>${dot(!H.paused)}${H.paused ? 'Auto-refresh paused' : 'Refreshes every 15 s'} · updated <b id="ccAgo">0 s</b> ago</span>
      <span>version <b class="mono">${esc(d.version || '?')}</b>${d.branch ? ` · ${esc(d.branch)}` : ''}</span>
      <span class="cc-sp"></span>
      <button type="button" class="nx-chipbtn" id="ccPause">${icon(H.paused ? 'play' : 'pause')}<span>${H.paused ? 'Resume' : 'Pause'}</span></button>
      <button type="button" class="nx-chipbtn" id="ccCopy">${icon('copy')}<span>Copy status</span></button>
      <button type="button" class="nx-chipbtn" id="ccNow">${icon('refresh')}<span>Refresh</span></button>
    </div>
    ${src('From the PC bot\'s own state (engine/pc_cc_api.py): eval cards, guards, NinjaTrader files, the heartbeat and today\'s log. Read-only.')}`;
  $('#ccPause').onclick = () => { H.paused = !H.paused; store.set('nx.cc.paused', H.paused); renderHome(); };
  $('#ccCopy').onclick = () => copy(statusText(d));
  $('#ccNow').onclick = () => loadHome(true);
}

async function loadHome(force) {
  if (!force && H.paused && H.d) return;
  try { H.d = await getJ('/api/next/cc/home'); } catch (e) { H.d = H.d && !H.d.error ? H.d : { error: e.message }; }
  H.at = Date.now();
  if (active('cc')) renderHome();
}
setInterval(() => { const a = $('#ccAgo'); if (a) a.textContent = ago((Date.now() - H.at) / 1000); }, 1000);
export const cc = {
  show: () => {
    renderHome(); loadHome(true);
    clearInterval(H.timer); H.timer = setInterval(() => { if (active('cc')) loadHome(); else clearInterval(H.timer); }, 15000);
  },
};

// ================================================================== 2. Goals (engine/goals.py when merged, else built here)
function goalsFallback(h) {
  const accs = [h?.lit, h?.atlas].filter(Boolean).map((a) => ({
    name: a.name, kind: 'eval', profit: a.profit, target: a.target_balance && a.balance != null ? (a.profit || 0) + (a.to_target || 0) : null,
    room: a.room, floor: a.floor, sessions_used: a.session || 0, sessions_max: a.sessions || 10, status: a.status, balance: a.balance,
  }));
  const wk = (() => {
    const now = new Date(), mon = new Date(now); mon.setDate(now.getDate() - ((now.getDay() + 6) % 7)); const d0 = mon.toISOString().slice(0, 10);
    const lt = (h?.lit?.trades || []).filter((t) => t.day >= d0).length;
    const at = (h?.atlas?.trades || []).filter((t) => t.t && new Date(t.t * 1000).toISOString().slice(0, 10) >= d0 && t.side !== 'exit').length;
    return { trades: lt + at, lit: lt, atlas: at, target_min: 2, target_max: 4 };
  })();
  const atr = (h?.atlas?.trades || []).filter((t) => t.side === 'exit' && ok(t.pnl));
  return { fallback: true, accounts: accs, week: wk,
    atlas_scorecard: { trades: atr.length, of: 20, wins: atr.filter((t) => t.pnl > 0).length, net: atr.reduce((s, t) => s + +t.pnl, 0) } };
}

function kv(o, skip = []) {
  return Object.entries(o || {}).filter(([k, v]) => !skip.includes(k) && (typeof v !== 'object' || v == null))
    .map(([k, v]) => `<div class="cc-kv"><span>${esc(k.replace(/_/g, ' '))}</span><b>${typeof v === 'number' ? (Math.abs(v) >= 100 ? v.toLocaleString('en-US', { maximumFractionDigits: 2 }) : +v.toFixed(3)) : esc(v)}</b></div>`).join('');
}

async function goals() {
  const el = $('#page-goals'); if (!el) return;
  el.innerHTML = hero('Goals', 'Where each account stands', '') + `<div class="cc-skel"></div>`;
  let g = null, why = '';
  try { g = await getJ('/api/next/goals'); } catch (e) { why = e.status === 404 ? 'not merged yet' : e.message; }
  let h = H.d;
  if (!g) { try { h = h && !h.error ? h : await getJ('/api/next/cc/home'); } catch { h = null; } g = goalsFallback(h); }
  let sc = null; try { sc = await getJ('/api/next/scale'); } catch { sc = null; }
  if (!active('goals')) return;
  const accs = g.accounts || [];
  const W = g.week || {}, S = g.atlas_scorecard || {};
  const wkT = +(W.trades ?? W.count ?? 0), wkMin = +(W.target_min ?? W.min ?? 2), wkMax = +(W.target_max ?? W.max ?? 4);
  const scN = +(S.trades ?? S.n ?? 0), scOf = +(S.of ?? S.target ?? 20);
  el.innerHTML = hero('Goals', 'Where each account stands',
    'Eval progress, this week\'s trade target (2-4 a week), the ATLAS 20-trade scorecard and the scaling plan.',
    g.fallback ? `<div class="op-verdict warn">${dot(null)}<b>Built from the bot</b><em>/api/next/goals ${esc(why || 'unavailable')}: this page reads the Command center data instead.</em></div>` : '') +
    `<div class="cc-two">${accs.map((a) => {
      const tgt = ok(a.target) ? +a.target : null, prof = ok(a.profit) ? +a.profit : 0;
      const f = tgt ? Math.max(0, Math.min(1, prof / tgt)) : 0;
      const sF = a.sessions_max ? Math.min(1, (a.sessions_used || 0) / a.sessions_max) : 0;
      return card(esc(a.name || a.kind || 'Account'), `
        <div class="cc-meter"><div class="cc-meter-h"><span>Profit ${susd(prof)} of ${usd(tgt)}</span><b>${pct(f * 100)}</b></div>${bar(f, 'accent')}</div>
        <div class="cc-meter"><div class="cc-meter-h"><span>Sessions used</span><b>${a.sessions_used ?? 0} / ${a.sessions_max ?? '—'}</b></div>${bar(sF, sF > 0.8 ? 'warn' : '')}
          <div class="cc-meter-s"><span>goal: pass in 10 sessions (2 weeks), never more than 15</span></div></div>
        <div class="cc-kvs">${kv(a, ['name', 'kind', 'profit', 'target', 'sessions_used', 'sessions_max'])}</div>`);
    }).join('') || empty('No accounts reported')}</div>
    <div class="grid cols-3 cc-row">
      ${card('This week: trades', `<div class="cc-ring">${ring(Math.min(1, wkT / wkMax), wkT >= wkMin ? 'good' : 'warn')}<div><b>${wkT}</b><span>of ${wkMin}-${wkMax} a week</span></div></div>
        <div class="cc-kvs">${kv(W, ['trades', 'count', 'target_min', 'target_max', 'min', 'max'])}</div>`)}
      ${card('ATLAS 20-trade scorecard', `<div class="cc-ring">${ring(Math.min(1, scN / scOf), 'accent')}<div><b>${scN}</b><span>of ${scOf} trades</span></div></div>
        <div class="cc-dots">${Array.from({ length: scOf }, (_, i) => `<i class="${i < scN ? 'on' : ''}"></i>`).join('')}</div>
        <div class="cc-kvs">${kv(S, ['trades', 'n', 'of', 'target'])}</div>`, go('atlas', 'ATLAS', 'atlas'))}
      ${card('Payout and scale', sc && !sc.error ? `<p class="cc-sent">${esc(sc.sentence || '')}</p>${sc.next ? `<div class="cc-meter"><div class="cc-meter-h"><span>${esc(sc.next.action || 'next step')}</span><b>${pct(sc.next.progress)}</b></div>${bar((sc.next.progress || 0) / 100, 'good')}</div>` : ''}
        <div class="cc-kvs">${kv(sc.money || {})}</div>` : empty('Scaling plan not available', esc(sc?.error || '')), go('scale', 'Scaling plan', 'prop'))}
    </div>
    ${src(g.fallback ? 'Fallback: accounts from /api/next/cc/home; week = PC routed trades since Monday; scorecard = ATLAS closed trades the bot routed.' : 'From /api/next/goals (engine/goals.py).')}`;
}
function ring(f, k = '') {
  const r = 30, c = 2 * Math.PI * r;
  return `<svg class="cc-ringsvg ${k}" viewBox="0 0 72 72" width="72" height="72"><circle cx="36" cy="36" r="${r}" class="bg"/><circle cx="36" cy="36" r="${r}" class="fg" stroke-dasharray="${(c * f).toFixed(1)} ${c.toFixed(1)}"/></svg>`;
}

// ================================================================== 3. Eval timeline
async function evaltl() {
  const el = $('#page-evaltl'); if (!el) return;
  el.innerHTML = hero('Eval timeline', 'Session by session', '') + `<div class="cc-skel"></div>`;
  let a = null, cal = null;
  try { a = await getJ('/api/next/pc/account?bars=0'); } catch (e) { a = { error: e.message }; }
  try { cal = await getJ('/api/next/cc/calendar?days=15'); } catch { cal = null; }
  if (!active('evaltl')) return;
  if (a.error) { el.innerHTML = hero('Eval timeline', 'Session by session', '') + errBox(a); return; }
  const ev = a.eval || {}, days = a.days || [];
  const rows = Array.isArray(days) ? days : Object.entries(days).map(([d, v]) => ({ day: d, pnl: v }));
  const used = ev.session || 0, max = ev.sessions || 10;
  const gap = Math.max(0, used - rows.length);              // sessions the eval counted without a bot trade (no P&L row)
  const future = (cal?.rows || []).filter((r) => !rows.some((x) => x.day === r.day)).slice(0, Math.max(0, 15 - rows.length - gap));
  el.innerHTML = hero('Eval timeline', 'Session by session', `LIT eval from ${esc(ev.start || '—')}: ${esc(ev.clock_text || '')}. Goal: decided within 10 sessions, never more than 15.`) +
    `<div class="nx-stats">${stat('Sessions used', `${used} / ${max}`)}${stat('Profit', susd(ev.profit), `${usd(ev.to_target)} to go`, cl(ev.profit))}${stat('Room', usd(ev.room), `floor ${usd(ev.floor, 2)}`)}${stat('Status', esc(ev.status || 'open'))}</div>` +
    card('Timeline', `<div class="cc-tl">${rows.map((r, i) => `<div class="cc-tl-d ${r.pnl > 0 ? 'up' : r.pnl < 0 ? 'dn' : ''}"><em>${i + 1}</em><b>${susd(r.pnl)}</b><span>${esc(r.day)}</span></div>`).join('')}
      ${Array.from({ length: gap }, (_, i) => `<div class="cc-tl-d"><em>${rows.length + i + 1}</em><b>$0</b><span>no bot trade</span></div>`).join('')}
      ${future.map((r, i) => `<div class="cc-tl-d fut ${r.closed ? 'closed' : ''}"><em>${rows.length + gap + i + 1}</em><b>${r.closed ? 'closed' : r.early_close ? 'early ' + esc(r.early_close) : '·'}</b><span>${esc(r.day)}${r.dst ? ' · DST' : ''}</span></div>`).join('')}</div>
      <div class="cc-tl-marks"><span style="left:${(10 / 15) * 100}%">10 sessions (2 weeks)</span><span style="left:99%">15</span></div>`) +
    src('Played days from the PC bot\'s eval tracker (/api/next/pc/account); upcoming days from /api/next/cc/calendar (early closes, holidays, DST).');
}

// ================================================================== 4. Session calendar
async function sesscal() {
  const el = $('#page-sesscal'); if (!el) return;
  let d; try { d = await getJ('/api/next/cc/calendar?days=20'); } catch (e) { el.innerHTML = errBox(e); return; }
  el.innerHTML = hero('Session calendar', 'The next 20 trading days', 'Early closes, CME holidays and the US clock change, so nothing surprises the bot or you.') +
    card('Days', `<div class="op-tw"><table class="op-tab"><tr><th>Day</th><th>Weekday</th><th>Session</th><th>Note</th></tr>${d.rows.map((r) => `<tr class="${r.closed ? 'muted' : ''}"><td class="mono">${esc(r.day)}</td><td>${esc(r.weekday)}</td>
      <td>${r.closed ? chip('closed', 'bad') : r.early_close ? chip('early close ' + esc(r.early_close) + ' ET', 'warn') : chip('normal', 'good')}</td>
      <td>${r.dst ? `${chip('DST', 'warn')} first session on the new time (${esc(r.dst)})` : r.early_close ? 'flat and entry cutoff move before the halt' : ''}</td></tr>`).join('')}</table></div>`, csvBtn('calCsv')) +
    src('engine/lit_live.early_close + engine/guards.full_closure (the same rules the bot uses) and the US DST dates.');
  $('#calCsv').onclick = () => downloadFile('session_calendar.csv', toCSV(d.rows), 'text/csv');
}

// ================================================================== 5. Runbook (emergency first, big)
async function runbook() {
  const el = $('#page-runbook'); if (!el) return;
  let d; try { d = await getJ('/api/next/cc/runbook'); } catch (e) { el.innerHTML = errBox(e); return; }
  const em = d.sections.find((s) => s.emergency);
  const rest = d.sections.filter((s) => !s.emergency);
  const withCopy = (html) => html.replace(/<code>((?:python|powershell)[^<]+)<\/code>/g, (m, c) => `<code>${c}</code><button type="button" class="cc-copy" data-copy="${c.replace(/&quot;/g, '"').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&amp;/g, '&').replace(/"/g, '&quot;')}" title="Copy">${icon('copy')}</button>`);
  el.innerHTML = hero('Runbook', 'Start, check, recover', 'The startup and recovery runbook. The emergency page comes first: get flat first, ask questions later.') +
    (em ? `<div class="cc-emerg"><div class="cc-emerg-h">${icon('warn')}<h2>EMERGENCY</h2><span>Any ONE of these is enough</span></div>
      <ol class="cc-emerg-steps">
        <li><b>HOLD TO KILL</b> on Bot Control (hold 1.5 s). Flattens every connected account; the bot stops for today. ${go('botctl', 'Open Bot Control', 'power')}<br><span class="muted">From PowerShell when the dashboard is down:</span> <code>python -m engine.ninjatrader --kill</code><button type="button" class="cc-copy" data-copy="python -m engine.ninjatrader --kill">${icon('copy')}</button></li>
        <li>In <b>NinjaTrader</b>: right-click a chart or the Positions tab &gt; <b>Flatten Everything</b>.</li>
        <li>Away from the PC: phone &gt; <b>Tradovate / MFFU app</b> &gt; the account &gt; <b>Flatten / Exit all</b>.</li></ol>
      <div class="cc-emerg-b lab-md">${withCopy(md(em.body.replace(/^\*\*Get flat first[^\n]*\n+/, '').replace(/^1\.[\s\S]*?\n\n(?=\|)/, '')))}</div></div>` : '') +
    `<div class="cc-toc">${rest.map((s, i) => `<a href="#rb${i}" data-rb="${i}">${esc(s.title)}</a>`).join('')}</div>` +
    rest.map((s, i) => card(esc(s.title), `<div class="lab-md">${withCopy(md(s.body))}</div>`, '', 'cc-rb" id="rb' + i)).join('') +
    card('Every command in the runbook', `<div class="cc-cmds">${(d.commands || []).map((c) => `<div><code>${esc(c)}</code><button type="button" class="cc-copy" data-copy="${esc(c)}">${icon('copy')}</button></div>`).join('')}</div>`) +
    src(esc(d.source) + ' (read-only; copy buttons only copy text).');
  $$('#page-runbook [data-rb]').forEach((a) => { a.onclick = (e) => { e.preventDefault(); document.getElementById('rb' + a.dataset.rb)?.scrollIntoView({ behavior: 'smooth', block: 'start' }); }; });
}

// ================================================================== 6. Audit evidence (handoff 2026-10-25)
const AU = { file: store.get('nx.au.file', 'README.md'), q: '', st: 'all' };
function matrixFrom(text) {
  const i = text.indexOf('## EXECUTION_TEST_MATRIX');
  if (i < 0) return [];
  const rows = text.slice(i).split('\n').filter((l) => /^\|/.test(l)).map((l) => l.replace(/^\||\|$/g, '').split('|').map((c) => c.trim()));
  const [head, , ...body] = rows;
  return body.map((r) => Object.fromEntries((head || []).map((h, k) => [h, r[k] || ''])));
}
async function audit() {
  const el = $('#page-audit'); if (!el) return;
  let L, A5;
  try { [L, A5] = await Promise.all([getJ('/api/next/cc/handoff'), getJ('/api/next/cc/doc?name=A5_execution.md').catch(() => null)]); } catch (e) { el.innerHTML = errBox(e); return; }
  const M = A5 ? matrixFrom(A5.text) : [];
  const cnt = (s) => M.filter((r) => (r.Status || '').toUpperCase() === s).length;
  const vd = String(L.verdict || '').replace(/^A\.\s*/, '');
  el.innerHTML = hero('Audit evidence · 2026-10-25', esc(vd.split(':').slice(1).join(':').trim() || vd || 'Pre-launch audit'),
    'What the pre-launch audit proved, what only you can prove on the PC tonight, and every file behind it.',
    `<div class="op-verdict ${/READY/.test(vd) ? 'good' : 'warn'}">${dot(/READY/.test(vd) ? true : null)}<b>${esc(vd.split(':')[0] || 'Verdict')}</b><em>${esc(L.folder)}</em></div>`) +
    `<div class="nx-stats">${stat('Execution tests', M.length)}${stat('PASS', cnt('PASS'), 'fake-folder / unit', 'up')}${stat('UNTESTED here', cnt('UNTESTED'), 'owner: Sim101 roundtrip', cnt('UNTESTED') ? 'dn' : '')}${stat('Files', L.files.length, 'in the handoff folder')}</div>` +
    card('EXECUTION_TEST_MATRIX', `<div class="cc-filters"><input class="inp" id="auQ" placeholder="Search scenarios" value="${esc(AU.q)}">
        <div class="seg sm" id="auSt">${['all', 'PASS', 'UNTESTED'].map((s) => `<button type="button" data-v="${s}" class="${AU.st === s ? 'on' : ''}">${s}</button>`).join('')}</div></div>
      <div class="op-tw" id="auM"></div>`, csvBtn('auCsv')) +
    `<div class="grid cc-audit">${card('Files', `<div class="cc-files">${L.files.filter((f) => /\.(md|csv|txt|json)$/i.test(f.name)).map((f) => `<button type="button" class="cc-file ${f.name === AU.file ? 'on' : ''}" data-f="${esc(f.name)}"><span class="cc-fk ${f.kind}">${esc(f.kind)}</span><span>${esc(f.name)}</span><em>${(f.size / 1024).toFixed(f.size < 10240 ? 1 : 0)} KB</em></button>`).join('')}</div>`)}
      <div id="auDoc"></div></div>` +
    src('research/handoff/2026-10-25/ (README.md, A1-A5 reports, ledgers, logs). Read-only viewer; Download saves a copy.');
  const drawM = () => {
    const q = AU.q.toLowerCase();
    const rows = M.filter((r) => (AU.st === 'all' || (r.Status || '').toUpperCase() === AU.st) && (!q || Object.values(r).join(' ').toLowerCase().includes(q)));
    $('#auM').innerHTML = `<table class="op-tab"><tr><th>Scenario</th><th>Class</th><th>Expected</th><th>Status</th><th>Log</th></tr>${rows.map((r) => `<tr><td><b>${esc(r.Scenario)}</b></td><td class="small">${esc(r['Test class'])}</td><td class="small">${esc(r.Expected).replace(/`([^`]+)`/g, '<code>$1</code>')}</td>
      <td>${chip(esc(r.Status), r.Status === 'PASS' ? 'good' : 'warn')}</td><td class="small mono">${esc(r['Log path']).replace(/`/g, '')}</td></tr>`).join('')}</table>`;
  };
  drawM();
  $('#auQ').oninput = (e) => { AU.q = e.target.value; drawM(); };
  $('#auSt').onclick = (e) => { const b = e.target.closest('button'); if (!b) return; AU.st = b.dataset.v; $$('#auSt button').forEach((x) => x.classList.toggle('on', x === b)); drawM(); };
  $('#auCsv').onclick = () => downloadFile('EXECUTION_TEST_MATRIX.csv', toCSV(M), 'text/csv');
  const open = async (name) => {
    AU.file = name; store.set('nx.au.file', name);
    $$('#page-audit .cc-file').forEach((b) => b.classList.toggle('on', b.dataset.f === name));
    const box = $('#auDoc'); box.innerHTML = card(esc(name), '<div class="cc-skel"></div>');
    let d; try { d = await getJ('/api/next/cc/doc?name=' + encodeURIComponent(name)); } catch (e) { box.innerHTML = errBox(e); return; }
    let body;
    if (d.kind === 'md') body = `<div class="lab-md">${md(d.text)}</div>`;
    else if (d.kind === 'csv') body = csvTable(d.text);
    else body = `<pre class="cc-pre">${esc(d.text)}</pre>`;
    box.innerHTML = card(esc(name), body + (d.truncated ? '<p class="muted small">Showing the first 600 KB.</p>' : ''), `<button type="button" class="nx-chipbtn" id="auDl">${icon('download')}<span>Download</span></button>`);
    $('#auDl').onclick = () => downloadFile(name.split('/').pop(), d.text, d.kind === 'csv' ? 'text/csv' : 'text/plain');
  };
  $$('#page-audit .cc-file').forEach((b) => { b.onclick = () => open(b.dataset.f); });
  open(L.files.some((f) => f.name === AU.file) ? AU.file : 'README.md');
}
function parseCSV(text) {
  const rows = []; let row = [], cur = '', q = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (q) { if (c === '"') { if (text[i + 1] === '"') { cur += '"'; i++; } else q = false; } else cur += c; }
    else if (c === '"') q = true; else if (c === ',') { row.push(cur); cur = ''; }
    else if (c === '\n') { row.push(cur); rows.push(row); row = []; cur = ''; } else if (c !== '\r') cur += c;
  }
  if (cur || row.length) { row.push(cur); rows.push(row); }
  return rows;
}
function csvTable(text, max = 400) {
  const rows = parseCSV(text);
  const [h, ...b] = rows;
  return `<div class="op-tw cc-csv"><table class="op-tab"><tr>${(h || []).map((c) => `<th>${esc(c)}</th>`).join('')}</tr>${b.slice(0, max).map((r) => `<tr>${r.map((c) => `<td class="${/^-?[\d.]+$/.test(c) ? 'r mono' : ''}">${esc(c)}</td>`).join('')}</tr>`).join('')}</table></div>${b.length > max ? `<p class="muted small">${max} of ${b.length} rows shown; Download has them all.</p>` : ''}`;
}

// ================================================================== 7. ATLAS per setup
const AS = { span: store.get('nx.as.span', 'H1'), sort: 'net_pnl', dir: -1, book: store.get('nx.as.book', '') };
const AS_COLS = [['setup_id', 'Setup'], ['label', 'Variant'], ['trades', 'Trades'], ['net_pnl', 'Net $'], ['per_month', '$ / month'], ['PF', 'PF'], ['positive_trade_rate', 'Win %'],
  ['average_win', 'Avg win'], ['average_loss', 'Avg loss'], ['max_drawdown', 'Max DD'], ['weekly_frequency', '/ week'], ['weeks_2plus_pct', '% wks 2+'], ['net_ex_top3', 'Net ex top 3']];
async function atlassetups() {
  const el = $('#page-atlassetups'); if (!el) return;
  let d; try { d = await getJ('/api/next/cc/setups'); } catch (e) { el.innerHTML = errBox(e); return; }
  if (!AS.book || !d.books.includes(AS.book)) AS.book = d.books[0] || '';
  const draw = () => {
    const rows = d.rows.filter((r) => r.span === AS.span && r.book === AS.book).sort((a, b) => ((+a[AS.sort] || 0) - (+b[AS.sort] || 0)) * AS.dir);
    const fmt = (k, v) => k === 'setup_id' ? `<b>${esc(String(v).replace(/^ATLAS_/, ''))}</b>` : k === 'label' ? esc(v) : /pnl|average|drawdown|per_month|net_ex/.test(k) ? `<span class="${cl(v)}">${usd(v)}</span>` : /rate|pct/.test(k) ? pct(v, 1) : ok(v) ? (+v).toLocaleString('en-US', { maximumFractionDigits: 2 }) : esc(v ?? '—');
    $('#asT').innerHTML = rows.length ? `<table class="op-tab cc-sort"><tr>${AS_COLS.map(([k, l]) => `<th data-k="${k}" class="${k === AS.sort ? 'on' : ''} ${k !== 'setup_id' && k !== 'label' ? 'r' : ''}">${l}${k === AS.sort ? (AS.dir < 0 ? ' ▾' : ' ▴') : ''}</th>`).join('')}</tr>
      ${rows.map((r) => `<tr class="${/POOLED/.test(r.setup_id) ? 'cc-tot' : ''}">${AS_COLS.map(([k]) => `<td class="${k !== 'setup_id' && k !== 'label' ? 'r mono' : ''}">${fmt(k, r[k])}</td>`).join('')}</tr>`).join('')}</table>` : empty('No rows for this span / book');
    $$('#asT th[data-k]').forEach((th) => { th.onclick = () => { if (AS.sort === th.dataset.k) AS.dir = -AS.dir; else { AS.sort = th.dataset.k; AS.dir = -1; } draw(); }; });
  };
  el.innerHTML = hero('ATLAS per setup', 'Which ATLAS setup earns what', 'London EMA, MACD sweep and the NY reclaim (S/R), each alone and pooled. H1 = Jan-Jun 2026 (picked), H2 = Jul-Oct (check); 2021-25 is a reference line.') +
    card('Per setup', `<div class="cc-filters"><div class="seg sm" id="asSpan">${d.spans.map((s) => `<button type="button" data-v="${esc(s)}" class="${s === AS.span ? 'on' : ''}">${esc(s)}</button>`).join('')}</div>
      <select class="inp" id="asBook">${d.books.map((b) => `<option ${b === AS.book ? 'selected' : ''}>${esc(b)}</option>`).join('')}</select></div><div class="op-tw" id="asT"></div>`, csvBtn('asCsv')) +
    `<div class="cc-note">${icon('info')}<span>H2 rests on few trades (15 MACD, 16 S/R). Without the top 3 winners each, H2 is EMA +$499, MACD −$2,621, S/R +$140 (audit README). Treat H2 rates as about ±10 points.</span></div>` +
    `<div id="asLedger"></div>` + src(esc(d.source) + ' · ledger: ATLAS_TRADE_LEDGER.csv');
  draw();
  $('#asSpan').onclick = (e) => { const b = e.target.closest('button'); if (!b) return; AS.span = b.dataset.v; store.set('nx.as.span', AS.span); $$('#asSpan button').forEach((x) => x.classList.toggle('on', x === b)); draw(); };
  $('#asBook').onchange = (e) => { AS.book = e.target.value; store.set('nx.as.book', AS.book); draw(); };
  $('#asCsv').onclick = () => downloadFile('atlas_per_setup.csv', toCSV(d.rows), 'text/csv');
  // the 2026 ATLAS trade ledger
  try {
    const t = await getJ('/api/next/cc/atlas_trades?year=2026');
    const box = $('#asLedger'); if (!box) return;
    const net = t.rows.reduce((s, r) => s + (+r.pnl || 0), 0);
    const hasPx = t.rows.some((r) => ok(r.entry_px));
    box.innerHTML = card(`ATLAS trades 2026 · ${esc(t.book)}`, `<div class="nx-stats cc-mini">${stat('Trades', t.rows.length)}${stat('Net', susd(net), '', cl(net))}${stat('Win %', pct(100 * t.rows.filter((r) => r.pnl > 0).length / Math.max(1, t.rows.length), 0))}</div>` +
      `<div class="op-tw cc-scroll"><table class="op-tab"><tr><th>Day</th><th>Setup</th><th>Side</th>${hasPx ? '<th class="r">Entry</th><th class="r">Stop</th><th class="r">Exit</th>' : '<th class="r">Risk pts</th><th class="r">Micros</th>'}<th>How</th><th class="r">R</th><th class="r">$</th></tr>${t.rows.slice(0, 300).map((r) => `<tr><td class="mono">${esc(r.entry_et || r.day)}</td><td>${esc(String(r.setup_id || '').replace(/^ATLAS_/, ''))}</td><td>${chip(r.dir > 0 ? 'LONG' : 'SHORT', r.dir > 0 ? 'good' : 'bad')}</td>${hasPx ? `<td class="r mono">${px(r.entry_px)}</td><td class="r mono">${px(r.stop_px)}</td><td class="r mono">${px(r.exit_px)}</td>` : `<td class="r mono">${ok(r.risk_pts) ? (+r.risk_pts).toFixed(2) : '—'}</td><td class="r mono">${esc(r.qty ?? '')}</td>`}<td>${esc(r.exit)}</td><td class="r mono ${cl(r.r)}">${ok(r.r) ? (+r.r).toFixed(2) : '—'}</td><td class="r mono ${cl(r.pnl)}">${susd(r.pnl)}</td></tr>`).join('')}</table></div>`,
      `<select class="inp sm" id="asLb">${t.books.map((b) => `<option ${b === t.book ? 'selected' : ''}>${esc(b)}</option>`).join('')}</select>` + csvBtn('asLCsv'));
    $('#asLCsv').onclick = () => downloadFile('atlas_trades_2026.csv', toCSV(t.rows), 'text/csv');
    $('#asLb').onchange = async (e) => { const x = await getJ('/api/next/cc/atlas_trades?year=2026&book=' + encodeURIComponent(e.target.value)); t.rows = x.rows; t.book = x.book; atlassetups(); };
  } catch { /* the ledger is optional */ }
}

// ================================================================== 8. Trade log (filters + CSV)
const TL = { src: store.get('nx.tl.src', 'replay'), side: 'all', exit: 'all', month: 'all', q: '', minR: '', rows: null, pc: null };
async function tradelog() {
  const el = $('#page-tradelog'); if (!el) return;
  if (!TL.rows) {
    el.innerHTML = hero('Trade log', 'Every trade, filtered your way', '') + '<div class="cc-skel"></div>';
    try { TL.rows = (await getJ('/api/next/trades?year=2026')).trades || []; } catch { TL.rows = []; }
    try { TL.pc = (await getJ('/api/next/pc/account?bars=0')).trades || []; } catch { TL.pc = []; }
  }
  if (!active('tradelog')) return;
  const base = TL.src === 'pc' ? TL.pc.map((t) => ({ ...t, side: t.side, exit: t.exit || t.reason })) : TL.rows;
  const months = [...new Set(base.map((t) => String(t.day || '').slice(0, 7)).filter(Boolean))].sort().reverse();
  const exits = [...new Set(base.map((t) => t.exit).filter(Boolean))].sort();
  el.innerHTML = hero('Trade log', 'Every trade, filtered your way', 'The LIT 2026 replay (live settings, costs in) or the trades the PC bot routed. Filter, then export what you see as CSV.') +
    card('Filters', `<div class="cc-filters wrap">
      <div class="seg sm" id="tlSrc">${[['replay', 'LIT replay 2026'], ['pc', 'PC routed']].map(([v, l]) => `<button type="button" data-v="${v}" class="${TL.src === v ? 'on' : ''}">${l}</button>`).join('')}</div>
      <div class="seg sm" id="tlSide">${['all', 'LONG', 'SHORT'].map((v) => `<button type="button" data-v="${v}" class="${TL.side === v ? 'on' : ''}">${v}</button>`).join('')}</div>
      <select class="inp" id="tlExit"><option value="all">every exit</option>${exits.map((x) => `<option ${TL.exit === x ? 'selected' : ''}>${esc(x)}</option>`).join('')}</select>
      <select class="inp" id="tlMonth"><option value="all">every month</option>${months.map((x) => `<option ${TL.month === x ? 'selected' : ''}>${esc(x)}</option>`).join('')}</select>
      <input class="inp" id="tlMinR" type="number" step="0.5" placeholder="min R" value="${esc(TL.minR)}" style="width:90px">
      <input class="inp" id="tlQ" placeholder="Search levels, tags, day" value="${esc(TL.q)}">
      <button type="button" class="nx-chipbtn" id="tlReset">${icon('close')}<span>Reset</span></button></div>`) +
    `<div class="nx-stats" id="tlStats"></div>` + card('Trades', '<div class="op-tw cc-scroll" id="tlT"></div>', csvBtn('tlCsv', 'Export CSV')) +
    src('LIT replay: research/lab/backtest_live.json (/api/next/trades). PC routed: the bot\'s own ledger (/api/next/pc/account).');
  const filt = () => base.filter((t) => (TL.side === 'all' || t.side === TL.side) && (TL.exit === 'all' || t.exit === TL.exit) && (TL.month === 'all' || String(t.day).startsWith(TL.month))
    && (TL.minR === '' || (+t.r || 0) >= +TL.minR) && (!TL.q || JSON.stringify([t.day, t.pools, t.conf_tags, t.target_label, t.exit, t.swept]).toLowerCase().includes(TL.q.toLowerCase())));
  const draw = () => {
    const rows = filt();
    const net = rows.reduce((s, t) => s + (+t.pnl || 0), 0), w = rows.filter((t) => t.pnl > 0), l = rows.filter((t) => t.pnl < 0);
    const gw = w.reduce((s, t) => s + +t.pnl, 0), gl = -l.reduce((s, t) => s + +t.pnl, 0);
    const avgR = rows.length ? rows.reduce((s, t) => s + (+t.r || 0), 0) / rows.length : null;
    $('#tlStats').innerHTML = stat('Trades', rows.length, `of ${base.length}`) + stat('Net', susd(net), '', cl(net)) + stat('Win %', rows.length ? pct(100 * w.length / rows.length) : '—') +
      stat('PF', gl ? (gw / gl).toFixed(2) : w.length ? '∞' : '—') + stat('Avg R', ok(avgR) ? (avgR > 0 ? '+' : '') + avgR.toFixed(2) + 'R' : '—', '', cl(avgR));
    $('#tlT').innerHTML = rows.length ? `<table class="op-tab"><tr><th>Day</th><th>Side</th><th class="r">Entry</th><th class="r">Stop</th><th class="r">Exit</th><th>Exit</th><th class="r">Qty</th><th class="r">R</th><th class="r">$</th><th>Levels</th></tr>${rows.slice(0, 500).map((t) => `<tr><td class="mono">${esc(t.day)}</td><td>${chip(esc(t.side), t.side === 'LONG' ? 'good' : 'bad')}</td><td class="r mono">${px(t.entry)}</td><td class="r mono">${px(t.stop)}</td><td class="r mono">${px(t.exit_price ?? t.exit_px)}</td><td>${esc(t.exit || '')}</td><td class="r mono">${esc(t.qty ?? '')}</td><td class="r mono ${cl(t.r)}">${ok(t.r) ? (+t.r).toFixed(2) : '—'}</td><td class="r mono ${cl(t.pnl)}">${susd(t.pnl)}</td><td class="small">${esc((t.pools || []).join(', '))}</td></tr>`).join('')}</table>` : empty('No trade matches these filters');
  };
  draw();
  const seg = (id, key) => { $(id).onclick = (e) => { const b = e.target.closest('button'); if (!b) return; TL[key] = b.dataset.v; if (key === 'src') { store.set('nx.tl.src', TL.src); TL.exit = 'all'; TL.month = 'all'; tradelog(); return; } $$(id + ' button').forEach((x) => x.classList.toggle('on', x === b)); draw(); }; };
  seg('#tlSrc', 'src'); seg('#tlSide', 'side');
  $('#tlExit').onchange = (e) => { TL.exit = e.target.value; draw(); };
  $('#tlMonth').onchange = (e) => { TL.month = e.target.value; draw(); };
  $('#tlMinR').oninput = (e) => { TL.minR = e.target.value; draw(); };
  $('#tlQ').oninput = (e) => { TL.q = e.target.value; draw(); };
  $('#tlReset').onclick = () => { Object.assign(TL, { side: 'all', exit: 'all', month: 'all', q: '', minR: '' }); tradelog(); };
  $('#tlCsv').onclick = () => downloadFile(`trades_${TL.src}.csv`, toCSV(filt(), ['day', 'side', 'entry', 'stop', 'target', 'exit_price', 'exit', 'qty', 'risk_pts', 'r', 'pnl', 'pools', 'target_label']), 'text/csv');
}

// ================================================================== 9. All features (directory + quick tools)
// n = a new read-only feature of this upgrade (counted); the directory also links every older page.
export const FEATURES = [
  ['Command center', 'cc', [
    ['Both accounts side by side', 'LIT 50K and ATLAS 25K cards on one screen'], ['Progress to target bars', 'profit vs the pass target, $ to go'],
    ['Room to floor gauge', 'trailing-drawdown cushion, turns amber / red when thin'], ['Today strip', 'today $, trades today / max, daily loss used, this week'],
    ['Open position card', 'side, micros, entry, stop, target, BE trigger, time in trade, $ now'], ['What the bot waits for', 'one plain sentence + the setups seen today'],
    ['Session phase + countdown', 'overnight / entry window / manage / flat / CME break, time to the next step'],
    ['Light: bar feed', 'NinjaTrader bars age, FEED STALE'], ['Light: NinjaTrader connection', 'connection file state'], ['Light: PC clock', 'drift vs internet time'],
    ['Light: STARTUP RECONCILED', 'the startup gate, with its reason when DISARMED'], ['Light: account allowlist', 'is this account listed; copy the fix'],
    ['Light: one bot per account', 'the duplicate-process lock'], ['Light: phone heartbeat', 'last push to the phone / cloud'], ['Light: kill switch', 'off / used today'],
    ['Light: bot loop', 'last poll age, errors in a row'], ['What to do now', 'the first red light and its fix, or "all green"'],
    ['Early close / holiday / DST banner', 'today and the clock change on Nov 1'], ['News today', 'USD events, Tier-1 flagged'], ['Latest bot log', 'risk, order and system rows'],
    ['Copy status', 'a plain-text status for a message'], ['Auto-refresh with pause', 'every 15 s, last-updated stamp'], ['Version stamp', 'which commit the PC runs'],
    ['Launch anchor note', 'the MFFU balance 49,710.80 / floor 48,168.20 / $3,289.20 to go']]],
  ['Goals', 'goals', [['Eval progress per account', 'from engine/goals.py, or built from the bot'], ['Weekly trade target', '2-4 a week ring'],
    ['ATLAS 20-trade scorecard', 'dots and stats'], ['Payout and scale progress', 'the scaling plan step and its progress'], ['Graceful fallback', 'works before /api/next/goals is merged']]],
  ['Eval timeline', 'evaltl', [['Session-by-session P&L', 'every eval day, with the 10 / 15 session marks'], ['Upcoming sessions', 'early closes, holidays and DST ahead']]],
  ['Session calendar', 'sesscal', [['Next 20 trading days', 'normal / early close / closed / DST'], ['Calendar CSV', 'export']]],
  ['Runbook', 'runbook', [['Emergency steps, big', 'HOLD TO KILL, Flatten Everything, the MFFU app'], ['Runbook sections + jump list', 'start, check, shutdown, recovery'],
    ['Copy buttons on every command', 'no typing mistakes'], ['Every command in one list', 'from the runbook']]],
  ['Audit evidence', 'audit', [['Audit verdict banner', 'READY_FOR_ISOLATED_SIM'], ['EXECUTION_TEST_MATRIX', 'search and PASS / UNTESTED filter'], ['Matrix CSV', 'export'],
    ['Handoff file browser', 'README, A1-A5, ledgers, logs'], ['Markdown / CSV viewer', 'reads each file in the page'], ['Download any audit file', 'one click']]],
  ['ATLAS per setup', 'atlassetups', [['Per-setup table', 'EMA / MACD / S/R and pooled, H1 / H2 / ref, sortable'], ['Book switch', 'alone vs routed books'], ['Per-setup CSV', 'export'],
    ['ATLAS 2026 trade ledger', 'every trade with entry, stop, exit, R, $'], ['Ledger CSV', 'export']]],
  ['Trade log', 'tradelog', [['Trade log: two sources', 'LIT replay 2026 or the PC routed trades'], ['Filters', 'side, exit, month, min R, search'],
    ['Filtered summary', 'trades, net $, win %, PF, avg R'], ['Filtered CSV export', 'exactly what you see']]],
  ['All features', 'features', [['Feature directory with search', 'this page'], ['Data freshness', 'how old each data file is'], ['Points to $ calculator', 'points x micros x $2'],
    ['ET / your time converter', 'the bot runs on New York time']]],
  ['Shell', null, [['Grouped sidebar', 'Home, Accounts, Trading, Results, Operations, More, each group folds'], ['Command palette', 'Ctrl K reaches every page, the new ones too'],
    ['Go-to shortcuts', 'G then H / P / F / W / Q / J / E…, 1-6 for the top pages'], ['Dark / light button', 'in the top bar (D also works)'], ['Smooth page transitions', 'fade-in pages, hover states on cards']]],
];
export const FEATURE_COUNT = FEATURES.reduce((s, [, , l]) => s + l.length, 0);

function toolsHtml() {
  return `<div class="grid cols-3 cc-row">
    ${card('Points to $', `<div class="cc-calc"><label>Points <input class="inp" id="tcPts" type="number" value="20" step="0.25"></label><label>Micros (MNQ) <input class="inp" id="tcQty" type="number" value="10" step="1"></label>
      <div class="cc-calc-r"><span>=</span><b id="tcOut">$400</b></div><p class="muted small">MNQ pays $2 a point a micro (NQ $20). Plain arithmetic: it does not change the bot's size.</p></div>`)}
    ${card('ET / your time', `<div class="cc-calc"><label>ET time <input class="inp" id="tzEt" type="time" value="09:30"></label><div class="cc-calc-r"><span>your PC</span><b id="tzOut">—</b></div>
      <div class="cc-tz">${['02:00', '09:30', '15:30', '15:55', '18:00'].map((t) => `<span><em>${t} ET</em><b data-tz="${t}"></b></span>`).join('')}</div></div>`)}
    ${card('Data freshness', '<div id="dfT">' + '<div class="cc-skel sm"></div></div>', '', '')}
  </div>`;
}
function etToLocal(hhmm) {
  const [h, m] = hhmm.split(':').map(Number);
  const now = new Date();
  const ny = new Date(now.toLocaleString('en-US', { timeZone: 'America/New_York' }));
  const off = now - ny;                                   // local - ET in ms
  const d = new Date(ny); d.setHours(h, m, 0, 0);
  return new Date(+d + off).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}
async function features() {
  const el = $('#page-features'); if (!el) return;
  const { DATA, MODULES, ARCHIVE } = await import('./routes.js');
  const q0 = store.get('nx.ft.q', '');
  el.innerHTML = hero('All features', `${FEATURE_COUNT} new read-only features, and every page`,
    'Everything the PC dashboard can show, grouped. New = added in the 2026-10-25 upgrade. Every feature only reads; the kill switch stays HOLD TO KILL on Bot Control.',
    `<label class="nx-field nx-find">${icon('search')}<input id="ftQ" class="inp" placeholder="Find a feature" value="${esc(q0)}" autocomplete="off"></label>`) +
    `<div class="cc-feat" id="ftL">${FEATURES.map(([g, page, list]) => `<div class="card nx-glass cc-card cc-fg" data-k="${esc((g + ' ' + list.map((x) => x.join(' ')).join(' ')).toLowerCase())}">
      <div class="card-h"><h3>${esc(g)}</h3><div class="card-tools">${chip(list.length + ' new', 'good')}${page ? go(page, 'Open') : ''}</div></div>
      <ul>${list.map(([n, dsc]) => `<li data-k="${esc((n + ' ' + dsc).toLowerCase())}"><b>${esc(n)}</b><span>${esc(dsc)}</span></li>`).join('')}</ul></div>`).join('')}</div>` +
    `<div class="nx-eyebrow" style="margin:22px 2px 10px">Quick tools</div>` + toolsHtml() +
    `<div class="nx-eyebrow" style="margin:22px 2px 10px">Every other page</div>` +
    `<div class="nx-tiles compact cc-pages">${[...MODULES, ...DATA, ...ARCHIVE].map((m) => `<button type="button" class="nx-tile" data-goto="${m.id}" data-k="${esc((m.label + ' ' + (m.desc || '')).toLowerCase())}"><span class="nx-tile-i">${icon(m.icon)}</span><span class="nx-tile-t">${esc(m.label)}</span><span class="nx-tile-d">${esc(m.desc || '')}</span><span class="nx-tile-go">${icon('right')}</span></button>`).join('')}</div>`;
  const filter = (q) => {
    q = q.trim().toLowerCase(); store.set('nx.ft.q', q);
    $$('#ftL .cc-fg').forEach((c) => { const lis = $$('li', c); let any = false; lis.forEach((li) => { const m = !q || li.dataset.k.includes(q) || c.dataset.k.startsWith(q); li.hidden = !m; any = any || m; }); c.hidden = !any; });
    $$('#page-features .cc-pages .nx-tile').forEach((t) => { t.hidden = q && !t.dataset.k.includes(q); });
  };
  $('#ftQ').oninput = (e) => filter(e.target.value); filter(q0);
  const calc = () => { const v = (+$('#tcPts').value || 0) * (+$('#tcQty').value || 0) * 2; $('#tcOut').textContent = usd(v, v % 1 ? 2 : 0); };
  $('#tcPts').oninput = calc; $('#tcQty').oninput = calc; calc();
  const tz = () => { $('#tzOut').textContent = etToLocal($('#tzEt').value || '09:30'); $$('[data-tz]').forEach((b) => { b.textContent = etToLocal(b.dataset.tz); }); };
  $('#tzEt').oninput = tz; tz();
  try {
    const d = await getJ('/api/next/cc/data_files');
    $('#dfT').innerHTML = `<table class="op-tab">${d.rows.map((r) => `<tr><td>${dot(r.missing ? null : r.age_s < 3 * 86400)}</td><td>${esc(r.name)}</td><td class="r mono">${r.missing ? 'missing' : ago(r.age_s) + ' old'}</td></tr>`).join('')}</table>`;
  } catch (e) { $('#dfT').innerHTML = empty('Not available', esc(e.message)); }
}

export const pages = {
  cc, goals: { show: goals }, evaltl: { show: evaltl }, sesscal: { show: sesscal }, runbook: { show: runbook }, audit: { show: audit },
  atlassetups: { show: atlassetups }, tradelog: { show: tradelog }, features: { show: features },
};

// ------------------------------------------------------------------ top-bar dark / light button (D does the same)
export function initCC() {
  const right = $('.nx-top .tb-right');
  if (right && !$('#ccTheme')) {
    const b = document.createElement('button');
    b.type = 'button'; b.className = 'btn ghost icon'; b.id = 'ccTheme'; b.title = 'Dark / light (D)';
    const paint = () => { b.innerHTML = icon(document.documentElement.dataset.theme === 'light' ? 'moon' : 'sun'); };
    paint();
    b.onclick = async () => {
      try { const ux = await import('../dash/ux.js'); ux.toggleDarkLight(); }
      catch { const r = document.documentElement; r.dataset.theme = r.dataset.theme === 'light' ? 'dark' : 'light'; }
      setTimeout(paint, 30);
    };
    right.insertBefore(b, $('#themeBtn') || null);
    new MutationObserver(paint).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
  }
}
