// Hub pages of the PC dashboard (read-only): Prop Firms, Business, Market, Learn, System.
//   Prop Firms (#page-firms)    comparison table with filters, a card per firm with every rule marked confirmed / unconfirmed /
//                               conflict, discount codes with copy buttons, live accounts, LIT fit, what to buy next
//   Business   (#page-business) eval odds from the current state, floor gauge, MFFU compliance, payout calendar, live-move
//                               guide, fees + net P&L, tax set-aside (not advice), Z06 goal, scaling + withdrawal planners
//   Market     (#page-market)   VIX / VXN regime + target band, overnight recap, levels map, week calendar, mega-cap
//                               earnings, CME holidays + early closes, roll countdown
//   Learn      (#page-learn)    LIT learning center (steps + diagram + glossary), research library, strategy versions,
//                               trade gallery
//   System     (#page-system)   upgrades tracker, PC uptime, discipline log, data quality
// API (GETs only): /api/next/hub/firms|business|market|learn|system, /api/next/hub/odds. Nothing here touches the bot.
import { $, $$, api, esc, fmt$, fmtS$, fmtN, cls, etStr, toast } from '../util.js';
import { icon } from './icons.js';

const H = {};
const ok = (v) => v != null && v !== '' && !Number.isNaN(+v);
const pct = (v, d = 1) => (ok(v) ? (+v).toFixed(d).replace(/\.0$/, '') + '%' : '—');
const usd = (v, d = 0) => (ok(v) ? fmt$(+v, d) : '—');
const kusd = (v) => (!ok(v) ? '—' : (v < 0 ? '−' : '') + '$' + (Math.abs(v) >= 10000 ? (Math.abs(v) / 1000).toFixed(1) + 'k' : Math.round(Math.abs(v)).toLocaleString('en-US')));
const isActive = (id) => document.getElementById('page-' + id)?.classList.contains('active');
const card = (title, body, tools = '', extra = '') => `<section class="card nx-glass hb-card ${extra}"><div class="card-h"><h3>${title}</h3>${tools ? `<div class="card-tools">${tools}</div>` : ''}</div>${body}</section>`;
const hero = (eyebrow, title, desc, side = '') => `<div class="nx-hero"><div><div class="nx-eyebrow">${eyebrow}</div><h2>${title}</h2>${desc ? `<p class="muted">${desc}</p>` : ''}</div>${side}</div>`;
const stat = (k, v, sub = '', c = '') => `<div class="nx-stat"><span>${k}</span><b class="${c}">${v}</b>${sub ? `<em>${sub}</em>` : ''}</div>`;
const chip = (t, k = '') => `<span class="nx-chip ${k}">${t}</span>`;
const empty = (t, s = '') => `<div class="pc-empty"><b>${esc(t)}</b>${s ? `<span>${esc(s)}</span>` : ''}</div>`;
const meter = (f, k = '') => `<div class="pc-meter ${k}"><i style="width:${Math.max(0, Math.min(100, f * 100)).toFixed(1)}%"></i></div>`;
const sec = (t, id = '') => `<div class="hb-sec" ${id ? `id="${id}"` : ''}>${t}</div>`;
const errBox = (x) => (x && x.error ? empty('Not available', x.error) : '');
const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const fDate = (d) => { if (!d) return '—'; const [y, m, dd] = String(d).slice(0, 10).split('-').map(Number); return `${MON[m - 1]} ${dd}${y !== new Date().getFullYear() ? ', ' + y : ''}`; };
const ST = { confirmed: ['good', 'confirmed'], unconfirmed: ['warn', 'unconfirmed'], conflict: ['bad', 'conflict'] };
const stBadge = (st) => { const s = ST[st] || ['', st || '?']; return `<span class="hb-st ${s[0]}" title="${esc(s[1])}">${esc(s[1])}</span>`; };
const fv = (x) => (x && typeof x === 'object' && 'v' in x ? x.v : x);
const segH = (id, items, v) => `<div class="seg sm" id="${id}">${items.map(([k, l]) => `<button type="button" data-v="${esc(k)}" class="${k === v ? 'on' : ''}">${esc(l)}</button>`).join('')}</div>`;

async function get(key, path, force) {
  if (!force && H[key] && Date.now() - H[key + 'At'] < 60000) return H[key];
  try { H[key] = await api(path); H[key + 'At'] = Date.now(); } catch (e) { H[key] = H[key] || { error: e.message }; }
  return H[key];
}

function copyText(t) {
  const done = () => toast(`Copied ${t}: verify the discount at checkout`);
  if (navigator.clipboard?.writeText) return navigator.clipboard.writeText(t).then(done).catch(() => fallback());
  return fallback();
  function fallback() {
    const a = document.createElement('textarea'); a.value = t; a.style.position = 'fixed'; a.style.opacity = '0'; document.body.appendChild(a); a.select();
    try { document.execCommand('copy'); done(); } catch { toast('Copy failed: ' + t); }
    a.remove();
  }
}
document.addEventListener('click', (e) => { const b = e.target.closest('[data-copy]'); if (b) copyText(b.dataset.copy); });

// ------------------------------------------------------------------ small SVG pieces
function spark(vals, { w = 160, h = 36, color = 'var(--accent)' } = {}) {
  const v = (vals || []).filter(ok).map(Number); if (v.length < 2) return '';
  const lo = Math.min(...v), hi = Math.max(...v), r = hi - lo || 1;
  const pts = v.map((x, i) => `${(i / (v.length - 1) * w).toFixed(1)},${(h - 3 - (x - lo) / r * (h - 6)).toFixed(1)}`).join(' ');
  return `<svg class="hb-spark" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" width="100%" height="${h}"><polyline points="${pts}" fill="none" stroke="${color}" stroke-width="1.6" vector-effect="non-scaling-stroke"/></svg>`;
}
function gauge(f, label, sub, level) {
  f = Math.max(0, Math.min(1, f || 0));
  const a = Math.PI * (1 - f), x = 100 + 80 * Math.cos(a), y = 100 - 80 * Math.sin(a);
  const col = level === 'danger' ? 'var(--bad)' : level === 'watch' ? 'var(--warn)' : 'var(--good)';
  return `<svg class="hb-gauge" viewBox="0 0 200 118" role="img" aria-label="${esc(label)}"><path d="M20 100 A80 80 0 0 1 180 100" fill="none" stroke="var(--surface-3)" stroke-width="14" stroke-linecap="round"/>
    <path d="M20 100 A80 80 0 0 1 ${x.toFixed(1)} ${y.toFixed(1)}" fill="none" stroke="${col}" stroke-width="14" stroke-linecap="round"/>
    <text x="100" y="86" text-anchor="middle" class="hb-g-v">${esc(label)}</text><text x="100" y="108" text-anchor="middle" class="hb-g-s">${esc(sub)}</text></svg>`;
}
function bars(rows, { h = 70, key = 'v', max = null, color = 'var(--accent)', label = (r) => '' } = {}) {
  if (!rows?.length) return '';
  const m = max ?? Math.max(1, ...rows.map((r) => +r[key] || 0));
  const w = 100 / rows.length;
  return `<svg class="hb-bars" viewBox="0 0 100 ${h}" preserveAspectRatio="none" width="100%" height="${h}">${rows.map((r, i) => {
    const v = Math.max(0, +r[key] || 0), bh = v / m * (h - 4);
    return `<rect x="${(i * w + w * 0.15).toFixed(2)}" y="${(h - bh).toFixed(2)}" width="${(w * 0.7).toFixed(2)}" height="${bh.toFixed(2)}" rx="0.8" fill="${color}" opacity="${v ? 0.9 : 0.25}"><title>${esc(label(r))}</title></rect>`;
  }).join('')}</svg>`;
}

// ================================================================== 1. PROP FIRMS
const F = { filter: 'all', q: '', sort: 'net_month_h2', dir: -1 };
const COLS = [
  ['plan', 'Firm · plan'], ['bot', 'Bot'], ['price_real', 'Price (real)'], ['target', 'Target'], ['daily_loss', 'Daily loss'], ['eval_consistency', 'Eval best day'],
  ['payout_split', 'Split'], ['payout_consistency', 'Payout rule'], ['p10_h2', 'Pass 2 wk H2'], ['pass_med_h2', 'Median pass'], ['funded_month_h2', 'Funded $/mo H2'],
  ['net_month_h2', '6-mo net $/mo H2'], ['status', 'Status'],
];
function firmRows(d) {
  let rows = (d.table || []).slice();
  if (F.filter === 'bot') rows = rows.filter((r) => r.bot === 'yes');
  else if (F.filter === 'nocons') rows = rows.filter((r) => /none/i.test(String(r.eval_consistency || '')));
  else if (F.filter !== 'all') rows = rows.filter((r) => r.firm_id === F.filter);
  if (F.q) { const q = F.q.toLowerCase(); rows = rows.filter((r) => JSON.stringify(r).toLowerCase().includes(q)); }
  const k = F.sort;
  rows.sort((a, b) => { const x = a[k], y = b[k]; if (ok(x) && ok(y)) return (x - y) * F.dir; return String(x ?? '').localeCompare(String(y ?? '')) * F.dir; });
  return rows;
}
function botChip(b) { return b === 'yes' ? chip('bot OK', 'good') : /no/.test(b || '') ? chip(esc(b), 'high') : chip(esc(b || '?'), 'warn'); }
function tableHTML(d) {
  const rows = firmRows(d);
  const td = (r, k) => {
    const v = r[k];
    if (k === 'plan') return `<td class="nx-sticky"><b>${esc(r.firm.replace(/ \(.+\)/, ''))}</b><br><span class="muted small">${esc(r.plan)}</span></td>`;
    if (k === 'bot') return `<td>${botChip(v)}</td>`;
    if (k === 'price_real') return `<td><b>${usd(v, 2)}</b><br><span class="muted small">${r.price_kind === 'owner' ? 'your price' : r.price_kind === 'code' ? 'with a code' : 'list'} · list ${usd(r.price_list)}</span></td>`;
    if (k === 'target') return `<td>${usd(v)}</td>`;
    if (k === 'p10_h2' || k === 'pass_med_h2') return `<td class="${k === 'p10_h2' && v >= 40 ? 'up' : ''}">${k === 'p10_h2' ? pct(v) : ok(v) ? fmtN(v, 0) + ' sess' : '—'}</td>`;
    if (k === 'funded_month_h2' || k === 'net_month_h2') return `<td class="${cls(v)}"><b>${kusd(v)}</b></td>`;
    return `<td class="hb-wrap">${esc(String(v ?? '—')).slice(0, 90)}</td>`;
  };
  return `<div class="pc-tw hb-tw"><table class="nx-vtbl pc-t hb-t"><thead><tr>${COLS.map(([k, l]) => `<th class="nx-sort ${F.sort === k ? 'on' : ''} ${k === 'plan' ? 'nx-sticky' : ''}" data-sort="${k}">${esc(l)}${F.sort === k ? icon(F.dir < 0 ? 'down' : 'up') : ''}</th>`).join('')}</tr></thead>
    <tbody>${rows.map((r) => `<tr data-plan="${esc(r.plan_id)}">${COLS.map(([k]) => td(r, k)).join('')}</tr>`).join('') || `<tr><td colspan="${COLS.length}">${empty('No plan matches the filter.')}</td></tr>`}</tbody></table></div>
    <p class="muted small">${icon('info')} LIT numbers: exact live LIT trades of 2026, eval sizing tuned per plan; H2 = Jul-Oct (the honest rate). 6-month net = payouts − every fee, from buying the eval. On 2021-25 every plan loses money (LIT has no edge there).</p>`;
}
function factRow(label, x) {
  if (x == null) return '';
  const v = fv(x);
  const src = (x.src || []).map((s) => `<a href="${esc(H.firms?.sources?.[s] || '#')}" target="_blank" rel="noopener" title="${esc(H.firms?.sources?.[s] || s)}">${esc(s)}</a>`).join(' ');
  return `<div class="hb-fact"><span>${esc(label)}</span><b>${esc(typeof v === 'object' ? JSON.stringify(v) : String(v))}</b>${x.st ? stBadge(x.st) : ''}${x.n ? `<em>${esc(x.n)}</em>` : ''}${src ? `<i class="hb-src">${src}</i>` : ''}</div>`;
}
function litFit(l) {
  if (!l) return '<p class="muted small">No LIT replay for this plan.</p>';
  const h1 = l.H1 || {}, h2 = l.H2 || {};
  return `<div class="hb-fit"><div><span>Pass / fail in 2 wk</span><b>${pct(h2.p10)} / ${pct(h2.f10)}</b><em>H1 ${pct(h1.p10)} / ${pct(h1.f10)}</em></div>
    <div><span>Pass eventually</span><b>${pct(h2.p60)}</b><em>median ${ok(h2.pass_med) ? h2.pass_med : '—'} sessions</em></div>
    <div><span>Funded $/mo</span><b>${kusd(h2.funded_month)}</b><em>H1 ${kusd(h1.funded_month)} · lost ${pct(h2.funded_lost_6m)} in 6 mo</em></div>
    <div><span>6-mo net $/mo</span><b class="${cls(h2.net_month_6m)}">${kusd(h2.net_month_6m)}</b><em>H1 ${kusd(h1.net_month_6m)} · 2021-25 ${kusd((l['2021-25'] || {}).net_month_6m)}</em></div></div>`;
}
function planCard(p) {
  const ev = p.eval || {}, fu = p.funded || {}, po = p.payouts || {}, pr = p.price || {};
  return `<div class="hb-plan"><div class="hb-plan-h"><b>${esc(p.name)}</b>${chip(esc(p.status || ''), /recommended|owner/.test(p.status || '') ? 'good' : /ruled out/.test(p.status || '') ? 'high' : '')}
      <span class="hb-price">${pr.owner ? `<b>${usd(pr.owner, 2)}</b> your price` : pr.with_code ? `<b>${usd(pr.with_code, 2)}</b> with a code` : ''} · list ${usd(fv(pr.list), 2)} ${pr.list?.st ? stBadge(pr.list.st) : ''}</span></div>
    ${litFit(p.lit)}
    <details><summary>Rules: eval, funded, payouts, news</summary><div class="hb-facts">
      ${Object.entries(ev).map(([k, x]) => factRow('Eval · ' + k.replace(/_/g, ' '), x)).join('')}
      ${Object.entries(fu).map(([k, x]) => factRow('Funded · ' + k.replace(/_/g, ' '), x)).join('')}
      ${Object.entries(po).map(([k, x]) => factRow('Payout · ' + k.replace(/_/g, ' '), x)).join('')}
      ${factRow('News', p.news)}${pr.type ? `<div class="hb-fact"><span>Price type</span><b>${esc(pr.type)}</b></div>` : ''}
    </div></details>${p.caveat ? `<p class="small warn-t">${icon('warn')} ${esc(p.caveat)}</p>` : ''}</div>`;
}
function firmCard(f) {
  return card(`${esc(f.name)} ${botChip(f.bot_friendly)}`, `<p class="small">${esc(f.summary)}</p>
    <div class="hb-facts">${factRow('Bots', f.bots)}${factRow('Copy trading', f.copy_trading)}${factRow('Platforms', f.platforms)}${factRow('Account caps', f.account_caps)}</div>
    ${(f.plans || []).map(planCard).join('')}`, f.site ? `<a class="btn ghost sm" href="${esc(f.site)}" target="_blank" rel="noopener">${icon('external')}<span>Site</span></a>` : '', 'hb-firm');
}
function codesHTML(d) {
  const rows = [];
  for (const f of d.firms || []) for (const c of f.codes || []) rows.push({ firm: f.name, ...c });
  return `<div class="hb-codes">${rows.map((c) => `<div class="hb-code"><div><b class="mono">${esc(c.code)}</b>${/^\(/.test(c.code) ? '' : `<button type="button" class="btn ghost sm" data-copy="${esc(c.code)}" title="Copy the code">${icon('copy')}<span>Copy</span></button>`}</div>
      <span class="small"><b>${esc(c.off)}</b> · ${esc(c.firm.replace(/ \(.+\)/, ''))}</span><span class="muted small">${esc(c.applies || '')} seen ${esc(c.seen)} ${stBadge(c.st)}</span>${c.n ? `<em class="muted small">${esc(c.n)}</em>` : ''}</div>`).join('')}</div>
    <div class="hb-sales">${(d.firms || []).filter((f) => f.sales).map((f) => `<p class="small"><b>${esc(f.name.replace(/ \(.+\)/, ''))}:</b> ${esc(fv(f.sales))} ${stBadge(f.sales.st)}</p>`).join('')}</div>
    <p class="muted small">${icon('warn')} Codes change weekly and most come from affiliate pages: verify at checkout. Searched ${esc(d.searched || '')}.</p>`;
}
function liveHTML(d) {
  const K = [['when', 'When you move'], ['how', 'How'], ['changes', 'What changes'], ['closes_others', 'Other accounts'], ['risk_rules', 'Live risk rules'], ['reports', 'What traders report']];
  return `<div class="hb-live">${(d.firms || []).map((f) => `<div class="hb-live-c"><div class="hb-live-h"><b>${esc(f.name.replace(/ \(.+\)/, ''))}</b>${botChip(f.bot_friendly)}</div>
    ${K.map(([k, l]) => { const x = (f.live || {})[k]; return x ? `<div class="hb-fact"><span>${l}</span><b>${esc(fv(x))}</b>${stBadge(x.st)}</div>` : ''; }).join('')}</div>`).join('')}</div>`;
}
function nextHTML(d) {
  const nx = d.next || {};
  let cum = 0, cash = 0;
  return `<div class="hb-steps">${(nx.steps || []).map((s, i) => { cum += +s.h2_per_month || 0; cash += +s.cash || 0; const pl = (d.table || []).find((r) => r.plan_id === s.plan) || {};
    return `<div class="hb-step"><i>${i + 1}</i><div><b>${esc(pl.firm ? pl.firm.replace(/ \(.+\)/, '') + ' ' + pl.plan : s.plan)}</b> <span class="muted small">${esc(s.when)}</span><p class="small">${esc(s.why)}</p></div>
      <div class="hb-step-n"><b>${usd(s.cash, 2)}</b><em>+${kusd(s.h2_per_month)}/mo H2</em><em class="muted">total ${usd(cash, 0)} · ${kusd(cum)}/mo</em></div></div>`; }).join('')}</div>
    <p class="small">${esc(nx.combo || '')}</p><p class="muted small">${icon('info')} Same LIT signals on every account: more money, the same bad months. Source: ${esc(nx.source || '')}.</p>`;
}
function combosHTML(d) {
  const name = (id) => { const r = (d.table || []).find((x) => x.plan_id === id); return r ? (r.firm.replace(/ \(.+\)/, '').replace('MyFundedFutures', 'MFFU') + ' ' + r.plan) : id; };
  return `<div class="pc-tw"><table class="nx-vtbl pc-t"><thead><tr><th>Accounts (same signals)</th><th>$/mo H2</th><th>H1</th><th>Months 4-6 H2</th><th>6 mo lose $</th><th>All lost</th></tr></thead><tbody>
    ${(d.combos || []).slice(0, 10).map((c) => `<tr><td class="hb-wrap">${c.plans.map(name).map(esc).join(' + ')}</td><td class="${cls(c.net_month_h2)}"><b>${kusd(c.net_month_h2)}</b></td><td>${kusd(c.net_month_h1)}</td><td>${kusd(c.months4_6_h2)}</td><td>${pct(c.neg_6m_h2)}</td><td>${pct(c.all_lost)}</td></tr>`).join('')}</tbody></table></div>
    <p class="muted small">Every combination on the same 1,500 Monte Carlo paths (research/lit/funded_firms.json); 6 months from buying, net of fees. MFFU Rapid rows need MFFU's written OK first.</p>`;
}
async function renderFirms(force) {
  const el = $('#page-firms'); if (!el || !isActive('firms')) return;
  const d = await get('firms', '/api/next/hub/firms', force);
  if (!d || d.error) { el.innerHTML = hero('Prop firms', 'Prop firm hub', '') + empty('No firm data.', d?.error || ''); return; }
  const c = d.counts || {};
  const firms = [['all', 'All plans'], ['bot', 'Bot allowed'], ['nocons', 'No eval best-day rule'], ...(d.firms || []).map((f) => [f.id, f.name.replace(/ \(.+\)/, '').replace('MyFundedFutures', 'MFFU')])];
  el.innerHTML = `<div class="hb-page">${hero(`${icon('prop')} Prop firms · ${esc(d.built || '')}`, 'Which firm, which plan, what it pays the LIT bot',
      `Rules, prices, codes, payouts, bot policy and live accounts for ${(d.firms || []).length} firms. Every rule is marked <b>confirmed</b>, <b>unconfirmed</b> or <b>conflict</b> with its source. Paper only.`,
      `<div class="nx-chips">${chip(`${c.facts || 0} facts`)}${chip(`${c.confirmed || 0} confirmed`, 'good')}${chip(`${c.unconfirmed || 0} unconfirmed`, 'warn')}${chip(`${c.conflict || 0} conflict`, 'high')}</div>`)}
    <div class="grid cols-2">${card('What to buy next', nextHTML(d), `<span class="muted small">from the funded write-ups</span>`)}${card('Discount codes', codesHTML(d), '<span class="muted small">copy, then verify at checkout</span>')}</div>
    ${card('Compare every plan', `<div class="nx-toolbar">${segH('hbFirmF', firms, F.filter)}<label class="nx-field">${icon('search')}<input id="hbFirmQ" class="inp" placeholder="Search rules" value="${esc(F.q)}" autocomplete="off"></label></div><div id="hbFirmT">${tableHTML(d)}</div>`)}
    ${sec('Firms')}<div class="hb-firms">${(d.firms || []).map(firmCard).join('')}</div>
    ${sec('Live accounts: moving from sim-funded to real money')}${card('When and how each firm moves you live', liveHTML(d), '<span class="muted small">never arm live for the bot: MFFU needs you present</span>')}
    ${sec('Combinations')}${card('Two or three accounts together', combosHTML(d))}
    ${card('Not for this bot', `<div class="hb-facts">${(d.excluded || []).map((x) => `<div class="hb-fact"><span>${esc(x.firm)}</span><b>${esc(x.why)}</b></div>`).join('')}</div>`)}
    <details class="card nx-glass hb-card"><summary><b>Sources (${Object.keys(d.sources || {}).length})</b> <span class="muted small">${esc(d.how_to_read || '')}</span></summary><div class="hb-srcs">${Object.entries(d.sources || {}).map(([k, u]) => `<div><span class="mono">${esc(k)}</span><a href="${esc(u)}" target="_blank" rel="noopener">${esc(u)}</a></div>`).join('')}</div></details></div>`;
  bindFirms(el, d);
}
function bindFirms(el, d) {
  const redraw = () => { $('#hbFirmT').innerHTML = tableHTML(d); bindSort(); };
  const bindSort = () => $$('#hbFirmT th[data-sort]').forEach((th) => { th.onclick = () => { const k = th.dataset.sort; F.dir = F.sort === k ? -F.dir : -1; F.sort = k; redraw(); }; });
  $$('#hbFirmF button').forEach((b) => { b.onclick = () => { F.filter = b.dataset.v; $$('#hbFirmF button').forEach((x) => x.classList.toggle('on', x === b)); redraw(); }; });
  const q = $('#hbFirmQ'); if (q) q.oninput = () => { F.q = q.value.trim(); redraw(); };
  bindSort();
}

// ================================================================== 2. BUSINESS
const B = { budget: 400, payout: null, tax: null, keep: null, reinvest: null };
function oddsHTML(o, ev) {
  if (!o || o.error) return empty('No eval odds.', o?.error || '');
  return `<div class="nx-stats hb-mini">${stat('Pass by session 10', pct(o.pass_left), `${o.left} sessions left`, 'up')}${stat('Fail by session 10', pct(o.fail_left), '', o.fail_left > 10 ? 'dn' : '')}
    ${stat('Pass eventually', pct(o.pass_ever), `fail ${pct(o.fail_ever)}`)}${stat('Median to pass', ok(o.med_sessions_to_pass) ? fmtN(o.med_sessions_to_pass, 0) + ' sess' : '—', 'from this balance')}</div>
    <div class="hb-explore"><label>Profit $ <input id="hbOP" class="inp" type="number" step="50" value="${Math.round(o.profit)}"></label><label>Session <input id="hbOS" class="inp" type="number" min="1" max="60" value="${o.session}"></label>
    <button type="button" class="btn ghost sm" id="hbOGo">${icon('refresh')}<span>What if</span></button><span class="muted small" id="hbOR"></span></div>
    <p class="muted small">${esc(o.method)}. ${esc(o.sizing_note)}.</p>`;
}
function floorHTML(g) {
  if (!g || g.error) return empty('No floor data.', g?.error || '');
  const f = Math.min(1, (g.room || 0) / 2000);
  return `<div class="hb-gauge-w">${gauge(f, usd(g.room), 'room to the floor', g.level)}<div class="nx-kv one">
      <div><span>Floor (trailing)</span><b>${usd(g.floor)}</b></div><div><span>Typical LIT stop-outs it holds</span><b>${fmtN(g.stopouts_typical, 1)} × ${usd(g.typical_risk)}</b></div>
      <div><span>Worst-case stop-outs</span><b>${fmtN(g.stopouts_worst, 1)} × ${usd(g.worst_risk)}</b></div><div><span>Risk of ruin (fail eventually)</span><b class="${g.ruin_ever > 20 ? 'dn' : ''}">${pct(g.ruin_ever)}</b></div>
      <div><span>Fail within 2 weeks</span><b>${pct(g.ruin_2wk)}</b></div></div></div><p class="muted small">${esc(g.sizing_cap)}. ${esc(g.risk_source)}.</p>`;
}
function complianceHTML(c) {
  if (!c || c.error) return empty('No compliance data.', c?.error || '');
  return `<div class="hb-rules">${c.rows.map((r) => `<div class="hb-rule ${r.ok === true ? 'g' : r.ok === false ? 'r' : 'a'}"><i>${icon(r.ok === true ? 'check' : r.ok === false ? 'warn' : 'info')}</i>
    <div><b>${esc(r.rule)}</b><span>${esc(r.now)}</span><em class="muted small">${esc(r.limit)}${r.note ? ' · ' + esc(r.note) : ''}</em></div></div>`).join('')}</div>
    <p class="muted small">${c.ok ? 'Every rule that can be checked is green.' : 'A rule needs attention.'} ${c.unknown ? `${c.unknown} unknown (bot not running or no trade yet).` : ''} ${esc(c.source)}</p>`;
}
function payoutsHTML(p) {
  if (!p || p.error) return empty('No payout data.', p?.error || '');
  return `<div class="hb-pay">${p.rows.map((r) => `<div class="hb-pay-r"><div class="hb-pay-c"><b>${ok(r.countdown_days) ? r.countdown_days : '—'}</b><span>days</span></div>
    <div><b>${esc(r.firm)} ${esc(r.plan)}</b> ${chip(esc(r.stage), r.stage === 'funded' ? 'good' : '')}<p class="small">First payout ≈ <b>${fDate(r.first_payout_est)}</b>${r.pass_est ? ` (eval pass ≈ ${fDate(r.pass_est)})` : ''}</p>
      <p class="muted small">${esc(r.need)}</p><p class="muted small">Rules: buffer ${usd(r.rules?.buffer)}, ${usd(r.rules?.pay_min)}-${usd(r.rules?.pay_max)} a request, ${pct((r.rules?.split || 0) * 100, 0)} split, best day ≤ ${pct((r.rules?.consistency || 0) * 100, 0)}, ${r.rules?.max_payouts || '?'} sim payouts then live.</p></div></div>`).join('')}</div>
    <p class="muted small">${icon('info')} ${esc(p.rows[0]?.est_basis || '')}</p>`;
}
function liveGuideHTML(l) {
  if (!l || l.error) return '';
  return `<ol class="hb-ol">${l.steps.map((s) => `<li>${esc(s)}</li>`).join('')}</ol><button type="button" class="btn ghost sm" data-goto="firms">${icon('prop')}<span>Each firm's live rules</span></button>`;
}
function pnlHTML(p, tax) {
  return `<div class="nx-stats hb-mini">${stat('Fees paid', usd(p.fees_paid, 2), p.fees_planned ? `${usd(p.fees_planned, 2)} planned` : '')}${stat('Payouts', usd(p.payouts, 2))}${stat('Net', fmtS$(p.net, 2), 'payouts − fees', cls(p.net))}${stat('Tax set-aside', usd(tax?.set_aside, 2), `${pct(tax?.pct, 0)} of net profit`)}</div>
    <div class="pc-tw"><table class="nx-vtbl pc-t"><thead><tr><th>Date</th><th>Item</th><th>$</th></tr></thead><tbody>
    ${[...(p.expenses || []).map((e) => ({ ...e, usd: -e.usd })), ...(p.payouts_rows || [])].sort((a, b) => String(b.date).localeCompare(String(a.date))).map((e) => `<tr class="${e.planned ? 'hb-planned' : ''}"><td>${esc(e.date)}</td><td class="hb-wrap">${esc(e.item || e.firm || 'payout')}${e.planned ? ' ' + chip('planned', 'warn') : ''}</td><td class="${cls(e.usd)}">${fmtS$(e.usd, 2)}</td></tr>`).join('')}</tbody></table></div>
    <p class="muted small">Source: ${esc(p.source)} (edit it to add payouts and fees). Recurring costs: ${usd(p.recurring_month)}/month.</p>`;
}
function taxHTML(t) {
  if (!t || t.error) return '';
  return `<div class="hb-note warn">${icon('warn')}<b>${esc(t.label)}</b></div><div class="hb-explore"><label>Set aside % <input id="hbTax" class="inp" type="number" min="0" max="60" value="${B.tax ?? t.pct}"></label><span id="hbTaxR" class="small"></span></div>
    <p class="muted small">${esc(t.note)}</p>`;
}
function goalHTML(g, gf) {
  if (!g || g.error) return '';
  return `<div class="hb-goal"><svg viewBox="0 0 120 40" class="hb-car" aria-hidden="true"><path d="M6 30 L14 22 Q30 13 52 13 L76 13 Q92 14 104 22 L114 26 Q116 30 112 31 L8 31 Z" fill="color-mix(in srgb, var(--accent) 35%, transparent)" stroke="var(--accent)" stroke-width="1.2"/><circle cx="30" cy="31" r="6" fill="var(--surface-3)" stroke="var(--ink-2)"/><circle cx="92" cy="31" r="6" fill="var(--surface-3)" stroke="var(--ink-2)"/></svg>
    <div><b>${esc(g.name)}</b> <span class="muted small">${usd(g.target)} · ${esc(g.note || '')}</span>${meter((g.saved || 0) / (g.target || 1))}<span class="small">${usd(g.saved, 0)} saved (${pct(g.pct)})</span></div></div>
    <div class="nx-kv sm"><div><span>Down payment ${usd(g.down_payment)}</span><b>${ok(g.months_to_down) ? fmtN(g.months_to_down, 1) + ' months' : '—'}</b></div>
      <div><span>Full price, 2 MFFU accounts (${kusd(g.plan_month)}/mo)</span><b>${ok(g.months_to_goal) ? fmtN(g.months_to_goal, 0) + ' months' : '—'}</b></div>
      <div><span>Full plan (${kusd(gf?.plan_month)}/mo)</span><b>${ok(gf?.months_to_goal) ? fmtN(gf.months_to_goal, 0) + ' months' : '—'}</b></div></div>
    <p class="muted small">${esc(g.basis)}. Paper estimates at the Jul-Oct rate; 2021-25 says LIT can also pay nothing.</p>`;
}
function scalingHTML(s) {
  if (!s || s.error) return '';
  return `<div class="hb-explore"><label>Budget $ <input id="hbBud" class="inp" type="number" min="0" step="10" value="${B.budget}"></label><span id="hbBudR" class="small"></span></div><div id="hbBudL"></div><p class="muted small">${esc(s.note)}</p>`;
}
function drawScaling(s) {
  const el = $('#hbBudL'); if (!el) return;
  let left = B.budget, mo = 0;
  const rows = (s.steps || []).map((x) => { const buy = left >= x.cash; if (buy) { left -= x.cash; mo += x.h2_per_month; } return { ...x, buy }; });
  el.innerHTML = `<div class="hb-steps">${rows.map((x, i) => `<div class="hb-step ${x.buy ? '' : 'off'}"><i>${i + 1}</i><div><b>${esc(x.name || x.plan)}</b> <span class="muted small">${esc(x.when)}</span></div><div class="hb-step-n"><b>${usd(x.cash, 2)}</b><em>${x.buy ? 'buy' : 'later'} · +${kusd(x.h2_per_month)}/mo</em></div></div>`).join('')}</div>`;
  const r = $('#hbBudR'); if (r) r.innerHTML = `buys ${rows.filter((x) => x.buy).length} · about <b>${kusd(mo)}/mo</b> (H2) once funded · ${usd(left, 2)} left`;
}
function withdrawHTML(w) {
  if (!w) return '';
  const v = (k, d) => B[k] ?? d;
  return `<div class="hb-explore wrap"><label>Payouts $/mo <input id="hbWP" class="inp" type="number" min="0" step="50" value="${v('payout', w.default_month)}"></label><label>Tax % <input id="hbWT" class="inp" type="number" min="0" max="60" value="${v('tax', w.tax_pct)}"></label>
    <label>Keep % <input id="hbWK" class="inp" type="number" min="0" max="100" value="${v('keep', w.keep_pct)}"></label><label>Reinvest % <input id="hbWR" class="inp" type="number" min="0" max="100" value="${v('reinvest', w.reinvest_pct)}"></label></div>
    <div id="hbWOut"></div><p class="muted small">MFFU Builder 50K: requests ${usd(w.mffu.min)}-${usd(w.mffu.max)}, ${pct(w.mffu.split * 100, 0)} to you, every ${w.mffu.cycle_days} trading days, best day ≤ 50% of the cycle, buffer ${usd(w.mffu.buffer)} first. ${esc(w.note || '')}</p>`;
}
function drawWithdraw(b) {
  const el = $('#hbWOut'); if (!el) return;
  const n = (id) => +($('#' + id)?.value || 0);
  const pay = n('hbWP'), tax = n('hbWT'), keep = n('hbWK'), re = n('hbWR');
  Object.assign(B, { payout: pay, tax, keep, reinvest: re });
  const after = pay * (1 - tax / 100), k = after * keep / 100, r = after * re / 100, sp = Math.max(0, after - k - r);
  const goal = b.goal || {}; const left = Math.max(0, (goal.target || 0) - (goal.saved || 0));
  const req = Math.ceil(pay / 0.8 / 2000);
  el.innerHTML = `<div class="nx-stats hb-mini">${stat('Tax pot', usd(pay * tax / 100), '/month')}${stat('Goal fund', usd(k), ok(k) && k > 0 ? `${goal.name || 'goal'} in ${fmtN(left / k, 0)} mo` : '')}${stat('Back into evals', usd(r), `${fmtN(r / 116, 1)} funded accounts / mo at $116`)}${stat('Spending', usd(sp), '/month')}</div>
    <p class="muted small">${usd(pay)} a month to you means about ${usd(pay / 0.8)} of account profit and ${req} payout request${req === 1 ? '' : 's'} at the $2,000 cap.</p>`;
}
async function renderBusiness(force) {
  const el = $('#page-business'); if (!el || !isActive('business')) return;
  const b = await get('biz', '/api/next/hub/business', force);
  if (!b || b.error) { el.innerHTML = hero('Business', 'Prop business', '') + empty('No business data.', b?.error || ''); return; }
  const ev = b.eval || {};
  el.innerHTML = `<div class="hb-page">${hero(`${icon('wallet')} Business · paper`, 'The eval, the payouts and the money',
      `Your MFFU eval right now, what it takes to get paid, what the business has cost and earned, and planners for the next accounts. ${esc(b.disclaimer)}`)}
    <div class="nx-stats">${stat('Eval balance', usd(ev.balance, 2), `${fmtS$(ev.profit, 2)} · session ${ev.session ?? '—'} of ${ev.sessions ?? 10}`)}${stat('To the target', usd(ev.to_target), `target ${usd(ev.target_balance)}`)}
      ${stat('Room to the floor', usd(ev.room), `floor ${usd(ev.floor)}${ev.locked ? ' (locked)' : ''}`, ev.room < 800 ? 'dn' : '')}${stat('Daily loss used', usd(ev.dll_used), `of ${usd(ev.dll)} soft`)}</div>
    <p class="muted small hb-srcline">${icon('info')} Eval from ${esc(b.eval_source || '—')}.</p>
    ${sec('Eval risk')}
    <div class="grid cols-2">${card('Live eval odds · from this balance', oddsHTML(b.odds, ev), '<span class="muted small">Monte Carlo, conditioned</span>')}${card('Floor distance · risk of ruin', floorHTML(b.floor))}</div>
    ${card('MFFU rules check · now', complianceHTML(b.compliance), '<span class="muted small">Builder 50K</span>')}
    ${sec('Getting paid')}
    <div class="grid cols-2">${card('Payout calendar · eligibility countdown', payoutsHTML(b.payouts))}${card('Moving to a live account', liveGuideHTML(b.live))}</div>
    ${sec('Money')}
    <div class="grid cols-2">${card('Fees, payouts and net business P&amp;L', pnlHTML(b.pnl || {}, b.tax))}${card('Tax set-aside · not tax advice', taxHTML(b.tax))}</div>
    <div class="grid cols-2">${card('Goal tracker · Z06', goalHTML(b.goal, b.goal_full_plan))}${card('Withdrawal planner · payout habit', withdrawHTML(b.withdraw))}</div>
    ${card('Funded scaling planner · budget → which evals when', scalingHTML(b.scaling))}</div>`;
  bindBusiness(el, b);
}
function bindBusiness(el, b) {
  const go = $('#hbOGo');
  if (go) go.onclick = async () => {
    const p = +($('#hbOP').value || 0), s = +($('#hbOS').value || 1);
    try { const o = await api(`/api/next/hub/odds?profit=${encodeURIComponent(p)}&session=${encodeURIComponent(s)}`); $('#hbOR').innerHTML = `pass by session 10 <b>${pct(o.pass_left)}</b> · fail ${pct(o.fail_left)} · eventually ${pct(o.pass_ever)} (${o.n_states} states)`; }
    catch (e) { $('#hbOR').textContent = e.message; }
  };
  const tx = $('#hbTax');
  const taxDraw = () => { const v = +(tx.value || 0); B.tax = v; const base = Math.max(0, b.pnl?.net || 0); $('#hbTaxR').innerHTML = `set aside <b>${usd(base * v / 100, 2)}</b> of ${usd(base, 2)} net · on each $1,000 payout ${usd(10 * v)}`; };
  if (tx) { tx.oninput = taxDraw; taxDraw(); }
  const bud = $('#hbBud');
  if (bud) { bud.oninput = () => { B.budget = +(bud.value || 0); drawScaling(b.scaling); }; drawScaling(b.scaling); }
  ['hbWP', 'hbWT', 'hbWK', 'hbWR'].forEach((id) => { const i = $('#' + id); if (i) i.oninput = () => drawWithdraw(b); });
  drawWithdraw(b);
}

// ================================================================== 3. MARKET
function vixHTML(v) {
  if (!v || v.error) return empty('No VIX data.', v?.error || '');
  const one = (x, n) => (x ? `<div class="hb-vix"><span>${n}</span><b>${fmtN(x.close, 2)}</b><em class="${cls(x.chg_5d)}">${fmtS$(x.chg_5d, 2).replace('$', '')} in 5 days · ${pct(x.pct_1y, 0)} of the last year below</em>${spark(x.spark)}<em class="muted">${esc(x.date)}</em></div>` : '');
  return `<div class="hb-vixs">${one(v.vix, 'VIX')}${one(v.vxn, 'VXN (Nasdaq)')}</div>
    <div class="nx-kv sm"><div><span>Regime</span><b class="hb-reg ${esc(v.regime)}">${esc(v.regime || '—')}</b></div><div><span>Target band (1 VIX day)</span><b>±${fmtN(v.move_pts, 0)} pts</b></div>
      <div><span>Band / typical stop</span><b>${fmtN(v.r_room, 1)}R</b></div><div><span>18:00 open</span><b>${ok(v.open18) ? fmtN(v.open18, 2) : '—'}</b></div>
      ${v.band ? `<div><span>Shorts target / longs target</span><b>${fmtN(v.band[0], 2)} / ${fmtN(v.band[1], 2)}</b></div>` : ''}</div>
    <p class="muted small">${esc(v.rule)}. Typical stop ${fmtN(v.typical_stop, 0)} pts. ${v.stale_days > 3 ? `<span class="warn-t">VIX file is ${v.stale_days} days old.</span>` : ''}</p>`;
}
function overnightHTML(o) {
  if (!o || o.error) return empty('No overnight data.', o?.error || '');
  return `<p class="small"><b>${esc(o.overnight?.text || '')}</b></p>${o.monday?.text ? `<p class="small">${esc(o.monday.text)}</p>` : ''}
    <div class="pc-tw"><table class="nx-vtbl pc-t"><thead><tr><th>Box (ET)</th><th>High</th><th>Low</th><th>Range</th><th>Taken</th></tr></thead><tbody>
    ${(o.boxes || []).map((b) => `<tr><td><b>${esc(b.label)}</b> <span class="muted small">${esc(b.window)}</span></td><td>${ok(b.high) ? fmtN(b.high, 2) : '—'}</td><td>${ok(b.low) ? fmtN(b.low, 2) : '—'}</td>
      <td>${ok(b.high) && ok(b.low) ? fmtN(b.high - b.low, 1) : '—'}</td><td>${b.status !== 'done' ? chip(esc(b.status)) : `${b.high_taken_t ? chip('high ' + etStr(b.high_taken_t), 'warn') : ''}${b.low_taken_t ? chip('low ' + etStr(b.low_taken_t), 'warn') : ''}${!b.high_taken_t && !b.low_taken_t ? chip('untouched', 'good') : ''}`}</td></tr>`).join('')}</tbody></table></div>
    <p class="muted small">Session ${esc(o.day)} · ${(o.swept || []).length} level(s) swept so far: ${(o.swept || []).slice(0, 6).map((s) => esc(s.label) + (ok(s.depth_atr) ? ` (${fmtN(s.depth_atr, 1)} ATR)` : '')).join(', ') || 'none'}. ${esc(o.source)}.</p>`;
}
function ladder(lv) {
  // the 16 levels nearest the price, one label row each (never overlapping), joined to their true price on a scale at the left
  const rows = (lv.all || []).filter((r) => ok(r.price)); if (!rows.length || !ok(lv.price)) return '';
  const near = rows.slice().sort((a, b) => Math.abs(a.dist) - Math.abs(b.dist)).slice(0, 16).sort((a, b) => b.price - a.price);
  const ps = [...near.map((r) => r.price), lv.price], hi = Math.max(...ps), lo = Math.min(...ps), rg = hi - lo || 1;
  const RH = 17, H0 = 16 + (near.length + 1) * RH, y = (p) => 10 + (hi - p) / rg * (H0 - 20);
  const above = near.filter((r) => r.price >= lv.price).length;
  const slot = (i) => 12 + (i < above ? i : i + 1) * RH;              // the price gets its own row between above and below
  const py = 12 + above * RH;
  return `<svg class="hb-ladder" viewBox="0 0 370 ${H0}" width="100%"><line class="ax" x1="40" x2="40" y1="8" y2="${H0 - 8}"/>
    ${near.map((r, i) => { const ly = slot(i); return `<g class="${r.taken ? 'tk' : r.side === 'H' ? 'h' : 'l'}"><line x1="34" x2="46" y1="${y(r.price).toFixed(1)}" y2="${y(r.price).toFixed(1)}"/>
      <path d="M46 ${y(r.price).toFixed(1)} L96 ${ly.toFixed(1)} L104 ${ly.toFixed(1)}" fill="none"/><text x="108" y="${(ly + 3.5).toFixed(1)}">${esc(r.label)}${r.taken ? ' ✓' : ''}</text>
      <text x="250" y="${(ly + 3.5).toFixed(1)}" class="d">${fmtN(r.price, 2)}</text><text x="366" y="${(ly + 3.5).toFixed(1)}" text-anchor="end" class="d">${r.dist > 0 ? '+' : ''}${fmtN(r.dist, 0)}</text></g>`; }).join('')}
    <path class="px" d="M30 ${y(lv.price).toFixed(1)} L50 ${y(lv.price).toFixed(1)} L96 ${py.toFixed(1)} L104 ${py.toFixed(1)}" fill="none"/><text class="pxt" x="108" y="${(py + 3.5).toFixed(1)}">price ${fmtN(lv.price, 2)}</text></svg>`;
}
function levelsHTML(lv) {
  if (!lv || lv.error) return empty('No levels.', lv?.error || '');
  return `<div class="hb-lv">${ladder(lv)}<div class="pc-tw"><table class="nx-vtbl pc-t"><thead><tr><th>Level</th><th>Price</th><th>Points away</th><th></th></tr></thead><tbody>
    ${(lv.rows || []).map((r) => `<tr><td><b>${esc(r.label)}</b></td><td>${fmtN(r.price, 2)}</td><td class="${r.dist > 0 ? 'up' : 'dn'}">${r.dist > 0 ? '+' : ''}${fmtN(r.dist, 2)}</td><td>${r.taken ? chip('taken', 'warn') : chip('untaken', 'good')}</td></tr>`).join('')}</tbody></table></div></div>
    <p class="muted small">${esc(lv.note)} Session ${esc(lv.day)}.</p>`;
}
function calHTML(c) {
  if (!c || c.error) return empty('No calendar.', c?.error || '');
  return `${c.stale ? `<div class="hb-note warn">${icon('warn')}<span>${esc(c.note)}. Showing the last events in the file.</span></div>` : ''}
    <div class="hb-cal">${(c.rows || []).map((e) => `<div class="hb-ev ${esc(e.impact)}"><span class="mono">${esc(e.weekday || '')} ${esc(fDate(e.date))} ${esc(e.time_et || '')}</span><b>${esc(e.title)}</b>
      ${chip(esc(e.impact || ''), e.impact === 'high' ? 'high' : '')}${e.blackout ? chip(`blackout ${esc(e.blackout_start)}-${esc(e.blackout_end)}`, 'kz') : ''}<em class="muted small">${e.forecast ? 'f ' + esc(e.forecast) : ''}${e.previous ? ' · p ' + esc(e.previous) : ''}${e.actual ? ' · a ' + esc(e.actual) : ''}</em></div>`).join('')}</div>
    <p class="muted small">Week ${esc(c.week?.[0])} → ${esc(c.week?.[1])}. ${esc(c.source)}, built ${esc(String(c.built || '').slice(0, 16))}.</p>`;
}
function earnHTML(e) {
  if (!e || e.error) return empty('No earnings.', e?.error || '');
  return `<div class="hb-earn">${(e.rows || []).filter((r) => r.days >= -2).map((r) => `<div class="hb-er ${r.this_week ? 'on' : ''}"><b class="mono">${esc(r.sym)}</b><span>${esc(fDate(r.date))} ${esc(r.time)}</span>
      <em>${r.days === 0 ? 'today' : r.days > 0 ? `in ${r.days} d` : `${-r.days} d ago`} · LIT session ${esc(fDate(r.lit_session))}</em>${stBadge(/confirm/.test(r.st) ? 'confirmed' : r.st === 'conflict' ? 'conflict' : 'unconfirmed')}</div>`).join('')}</div>
    <p class="muted small">${esc(e.how || '')} ${e.fetched ? 'Fetched: ' + esc(e.fetched) : 'Live fetch unavailable: maintained file ' + esc(e.source) + ' (' + esc(e.updated) + ').'}</p>`;
}
function holHTML(h) {
  if (!h || h.error) return empty('No holidays.', h?.error || '');
  return `<div class="hb-hol">${(h.rows || []).slice(0, 12).map((r) => `<div class="${esc(r.kind)}"><span class="mono">${esc(r.weekday)} ${esc(fDate(r.date))}</span><b>${r.kind === 'closed' ? 'Closed' : 'Halt ' + esc(r.halt_et) + ' ET'}</b><em class="muted small">${r.days} d · ${r.eval_session ? 'counts as an eval session' : 'not a session'}</em></div>`).join('')}</div>
    <p class="muted small">${esc(h.mffu)}. ${esc(h.source)}.</p>`;
}
function rollHTML(r) {
  if (!r || r.error) return empty('No roll data.', r?.error || '');
  return `<div class="hb-roll"><div class="hb-pay-c big"><b>${r.days_to_roll}</b><span>days to the roll</span></div><div class="nx-kv one">
      <div><span>Now → next</span><b>${esc(r.current)} → ${esc(r.next)} (${esc(r.mnq)})</b></div><div><span>CME roll date</span><b>${fDate(r.roll_date)}</b></div>
      <div><span>TradingView NQ1! switch</span><b>${fDate(r.tv_switch)} (${r.days_to_switch} d)</b></div><div><span>Expiry</span><b>${fDate(r.expiry)} (${r.days_to_expiry} d)</b></div>
      <div><span>Last roll</span><b>${esc(r.last_roll?.from)} → ${esc(r.last_roll?.to)} gap ${fmtN(r.last_roll?.gap, 2)} pts</b></div></div></div>
    <ol class="hb-ol">${(r.checklist || []).map((x) => `<li>${esc(x)}</li>`).join('')}</ol><p class="muted small">${esc(r.rule)}.</p>`;
}
async function renderMarket(force) {
  const el = $('#page-market'); if (!el || !isActive('market')) return;
  const m = await get('mkt', '/api/next/hub/market', force);
  if (!m || m.error) { el.innerHTML = hero('Market', 'Market', '') + empty('No market data.', m?.error || ''); return; }
  el.innerHTML = `<div class="hb-page">${hero(`${icon('regime')} Market · NQ`, 'What the market brings this week',
      'Volatility and the LIT target band, the overnight map, the levels, the week\'s news, mega-cap earnings, holidays and the contract roll.')}
    <div class="grid cols-2">${card('VIX / VXN regime · target band', vixHTML(m.vix))}${card('Overnight recap · Asia and London', overnightHTML(m.overnight))}</div>
    ${card('Weekly / monthly levels map', levelsHTML(m.levels), '<span class="muted small">PWH/PWL · PMH/PML · PDH/PDL · NWOG/NDOG</span>')}
    <div class="grid cols-2">${card('Economic calendar · this week', calHTML(m.calendar))}${card('NQ mega-cap earnings', earnHTML(m.earnings), '<span class="muted small">AAPL MSFT NVDA AMZN GOOGL META TSLA AVGO</span>')}</div>
    <div class="grid cols-2">${card('CME holidays + early closes', holHTML(m.holidays))}${card('Contract roll countdown', rollHTML(m.roll))}</div></div>`;
}

// ================================================================== 4. LEARN
const L = { verdict: 'all', q: '', gq: '' };
function diagram() {
  // a long LIT setup, schematic: level, inducement, sweep, displacement, CISD, limit + 1m confirmation, stop, VIX band target
  const C = [[40, 70, 74, 60, 78], [58, 74, 80, 66, 70], [76, 70, 72, 58, 62], [94, 62, 66, 52, 56], [112, 56, 58, 40, 44], [130, 44, 47, 22, 26],
    [148, 26, 34, 18, 32], [166, 32, 60, 30, 58], [184, 58, 66, 52, 64], [202, 62, 64, 50, 54], [220, 54, 72, 52, 70], [238, 70, 90, 68, 88], [256, 88, 110, 86, 108]];
  const Y = (v) => 150 - v;
  return `<svg class="hb-diag" viewBox="0 0 340 170" width="100%" role="img" aria-label="LIT long setup diagram">
    <line x1="20" x2="300" y1="${Y(40)}" y2="${Y(40)}" class="lv"/><text x="22" y="${Y(40) + 12}" class="t">level (e.g. Asia low)</text>
    <line x1="80" x2="140" y1="${Y(52)}" y2="${Y(52)}" class="idm"/><text x="64" y="${Y(52) - 4}" class="t">inducement</text>
    ${C.map(([x, o, h, l, c]) => `<line x1="${x}" x2="${x}" y1="${Y(h)}" y2="${Y(l)}" class="w"/><rect x="${x - 5}" y="${Y(Math.max(o, c))}" width="10" height="${Math.max(1.5, Math.abs(c - o))}" class="${c >= o ? 'u' : 'd'}"/>`).join('')}
    <circle cx="148" cy="${Y(18)}" r="9" class="ring"/><text x="140" y="${Y(10)}" class="t">sweep ≥ 0.5 ATR</text>
    <line x1="160" x2="300" y1="${Y(32)}" y2="${Y(32)}" class="cisd"/><text x="252" y="${Y(32) + 12}" class="t">CISD = limit</text>
    <text x="172" y="${Y(68)}" class="t">displacement ≥ 0.8 ATR</text>
    <line x1="140" x2="300" y1="${Y(17)}" y2="${Y(17)}" class="stop"/><text x="252" y="${Y(17) + 12}" class="t r">stop 1 tick beyond</text>
    <line x1="200" x2="300" y1="${Y(112)}" y2="${Y(112)}" class="tgt"/><text x="222" y="${Y(112) - 4}" class="t g">target: VIX band (≥ 1.5R, bank 8R)</text>
    <path d="M202 ${Y(52)} l6 -6 l6 6" class="arr"/><text x="190" y="${Y(42)}" class="t">1m CISD → buy</text></svg>`;
}
function learnHTML(x) {
  if (!x || x.error) return empty('No playbook.', x?.error || '');
  return `<div class="hb-learn">${diagram()}<ol class="hb-steps2">${(x.steps || []).map((s) => `<li><b>${esc(s.title)}</b><span>${esc(s.text)}</span></li>`).join('')}</ol></div>
    <details><summary>Session clocks</summary>${(x.clocks || []).map((c) => `<p class="small">${esc(c.replace(/\*\*/g, ''))}</p>`).join('')}</details>`;
}
function glossHTML(x) {
  const q = L.gq.toLowerCase();
  const rows = (x?.glossary || []).filter((g) => !q || (g.term + ' ' + g.meaning).toLowerCase().includes(q));
  return `<div class="hb-gloss">${rows.map((g) => `<div><b>${esc(g.term)}</b><span>${esc(g.meaning)}</span></div>`).join('') || empty('No term matches.')}</div>`;
}
const VERD = { candidate: 'good', adopted: 'good', rejected: 'high', promising: 'kz', finding: '', info: '' };
function libHTML(lib) {
  if (!lib || lib.error) return empty('No library.', lib?.error || '');
  const q = L.q.toLowerCase();
  const rows = (lib.rows || []).filter((r) => (L.verdict === 'all' || r.verdict === L.verdict) && (!q || (r.title + ' ' + r.summary + ' ' + r.family).toLowerCase().includes(q)));
  return `<p class="muted small">${rows.length} of ${(lib.rows || []).length} write-ups</p><div class="hb-lib">${rows.slice(0, 60).map((r) => `<div class="hb-wu"><div>${chip(esc(r.verdict), VERD[r.verdict] || '')}${chip(esc(r.family))}<span class="muted small">${esc(r.date || '')}</span></div>
    <b>${esc(r.title)}</b><p class="small">${esc(r.summary.slice(0, 320))}${r.summary.length > 320 ? '…' : ''}</p><button type="button" class="btn ghost sm" data-goto="writeups">${icon('reports')}<span>Read in Write-ups</span></button></div>`).join('')}</div>`;
}
function versionsHTML(v) {
  if (!v || v.error) return empty('No history.', v?.error || '');
  const sw = Object.keys(v.switches_on || {});
  return `<p class="small">Live now: <b>${esc(v.current?.model || 'lit')}</b>${v.current?.chosen ? ' · ' + esc(v.current.chosen) : ''}${sw.length ? ' · upgrades on: ' + sw.map(esc).join(', ') : ''}</p>
    ${(v.locks || []).map((l) => `<p class="muted small">${esc(l)}</p>`).join('')}
    <div class="hb-tl">${(v.rows || []).map((r) => `<div class="${r.strategy === 'LIT' ? 'lit' : ''}"><span class="mono">${esc(r.date)}</span><i></i><b>${esc(r.title)}</b><em class="mono muted">${esc(r.sha)}</em></div>`).join('')}</div><p class="muted small">${esc(v.source)}</p>`;
}
function miniChart(c) {
  const b = c.bars || []; if (b.length < 3) return '';
  const all = [...b.flatMap((x) => [x[2], x[3]]), c.stop, c.target, c.entry].filter(ok);
  const hi = Math.max(...all), lo = Math.min(...all), rg = hi - lo || 1, W = 240, Hh = 120, bw = W / b.length;
  const y = (p) => 4 + (hi - p) / rg * (Hh - 8);
  const xi = (t) => { let i = b.findIndex((x) => x[0] >= t); if (i < 0) i = b.length - 1; return i * bw + bw / 2; };
  const line = (p, k) => (ok(p) ? `<line class="${k}" x1="${xi(c.entry_t).toFixed(1)}" x2="${W}" y1="${y(p).toFixed(1)}" y2="${y(p).toFixed(1)}"/>` : '');
  return `<svg class="hb-mc" viewBox="0 0 ${W} ${Hh}" preserveAspectRatio="none" width="100%" height="${Hh}">${b.map((x, i) => `<line class="w" x1="${(i * bw + bw / 2).toFixed(1)}" x2="${(i * bw + bw / 2).toFixed(1)}" y1="${y(x[2]).toFixed(1)}" y2="${y(x[3]).toFixed(1)}"/><rect class="${x[4] >= x[1] ? 'u' : 'd'}" x="${(i * bw + bw * 0.18).toFixed(1)}" width="${(bw * 0.64).toFixed(1)}" y="${y(Math.max(x[1], x[4])).toFixed(1)}" height="${Math.max(0.6, Math.abs(y(x[1]) - y(x[4]))).toFixed(1)}"/>`).join('')}
    ${line(c.stop, 'stop')}${line(c.target, 'tgt')}${line(c.entry, 'ent')}${ok(c.exit_px) ? `<circle class="x" cx="${xi(c.exit_t).toFixed(1)}" cy="${y(c.exit_px).toFixed(1)}" r="3"/>` : ''}</svg>`;
}
function galleryHTML(g) {
  if (!g || g.error) return empty('No gallery.', g?.error || '');
  const imgs = (g.images || []).map((i) => `<a class="hb-gi" href="${esc(i.url)}" target="_blank" rel="noopener"><img src="${esc(i.url)}" alt="${esc(i.name)}" loading="lazy"><span class="small">${esc(i.name)}</span></a>`).join('');
  return `<div class="hb-gal">${imgs}${(g.charts || []).map((c) => `<div class="hb-gc"><div class="hb-gc-h"><b>${esc(fDate(c.day))}</b>${chip(esc(c.side), c.side === 'LONG' ? 'good' : 'high')}<span class="${cls(c.pnl)}">${fmtS$(c.pnl, 0)} · ${ok(c.r) ? (c.r > 0 ? '+' : '') + fmtN(c.r, 1) + 'R' : ''}</span></div>
    ${miniChart(c)}<span class="muted small">${esc(c.exit)} · stop ${fmtN(c.risk_pts, 1)} pts · ${(c.levels || []).map((l) => esc(l.label)).join(', ')}</span></div>`).join('')}</div>
    <p class="muted small">${esc(g.source)}. Green line target, red stop, blue entry, dot = exit.</p>`;
}
async function renderLearn(force) {
  const el = $('#page-learn'); if (!el || !isActive('learn')) return;
  const d = await get('learn', '/api/next/hub/learn', force);
  if (!d || d.error) { el.innerHTML = hero('Learn', 'Learn', '') + empty('No data.', d?.error || ''); return; }
  const cnt = d.library?.counts || {};
  el.innerHTML = `<div class="hb-page">${hero(`${icon('learned')} Learn · LIT`, 'How LIT works, and everything we tested', 'The model as the bot trades it, a glossary, every research write-up with its verdict, how the strategy changed, and real trades drawn small.')}
    ${card('LIT learning center · a long setup, step by step', learnHTML(d.learn))}
    ${card('Glossary', `<label class="nx-field">${icon('search')}<input id="hbGQ" class="inp" placeholder="Find a term" value="${esc(L.gq)}" autocomplete="off"></label><div id="hbGL">${glossHTML(d.learn)}</div>`, `<span class="muted small">${esc(d.learn?.source || '')}</span>`)}
    ${card('Research library', `<div class="nx-toolbar">${segH('hbLV', [['all', `All ${(d.library?.rows || []).length}`], ['candidate', `Candidates ${cnt.candidate || 0}`], ['rejected', `Rejected ${cnt.rejected || 0}`], ['promising', `Promising ${cnt.promising || 0}`], ['finding', `Findings ${cnt.finding || 0}`], ['info', `Info ${cnt.info || 0}`]], L.verdict)}
      <label class="nx-field">${icon('search')}<input id="hbLQ" class="inp" placeholder="Search write-ups" value="${esc(L.q)}" autocomplete="off"></label></div><div id="hbLL">${libHTML(d.library)}</div>`)}
    <div class="grid cols-2">${card('Strategy version history', versionsHTML(d.versions))}${card('Trade gallery · LIT 2026', galleryHTML(d.gallery))}</div></div>`;
  const lq = $('#hbLQ'); if (lq) lq.oninput = () => { L.q = lq.value.trim(); $('#hbLL').innerHTML = libHTML(d.library); };
  $$('#hbLV button').forEach((b) => { b.onclick = () => { L.verdict = b.dataset.v; $$('#hbLV button').forEach((x) => x.classList.toggle('on', x === b)); $('#hbLL').innerHTML = libHTML(d.library); }; });
  const gq = $('#hbGQ'); if (gq) gq.oninput = () => { L.gq = gq.value.trim(); $('#hbGL').innerHTML = glossHTML(d.learn); };
}

// ================================================================== 5. SYSTEM
function upgradesHTML(u) {
  if (!u || u.error) return empty('No data.', u?.error || '');
  const bt = u.backtest || {}, base = bt.base?.rule || {};
  const all3 = bt.combos?.all3?.rule || {};
  const live = u.live || {};
  const row = (name, r, on) => `<tr><td><b>${esc(name)}</b>${on != null ? ' ' + chip(on ? 'on' : 'off', on ? 'good' : '') : ''}</td><td>${fmtN(r?.H1?.pf, 2)} / ${fmtN(r?.H2?.pf, 2)}</td><td class="${cls(r?.H2?.net)}">${kusd(r?.H1?.net)} / <b>${kusd(r?.H2?.net)}</b></td><td>${kusd(r?.H2?.per_month)}</td><td>${kusd(r?.H2?.dd)}</td></tr>`;
  return `<div class="pc-tw"><table class="nx-vtbl pc-t"><thead><tr><th>Backtest (2026)</th><th>PF H1 / H2</th><th>Net H1 / H2</th><th>$/mo H2</th><th>DD H2</th></tr></thead><tbody>
    ${row('LIT without the upgrades', base)}${(bt.switches || []).map((s) => row(s.name, s.rule, s.on)).join('')}${all3.H2 ? row('All 3 together', all3) : ''}</tbody></table></div>
    ${live.placeholder ? `<div class="hb-note">${icon('clock')}<span>${esc(live.text)}</span></div>` : `<div class="nx-stats hb-mini">${stat('Paper with upgrades', fmtS$(live.with?.net, 0), `${live.with?.n} trades since ${esc(live.with?.since || '')}`, cls(live.with?.net))}${stat('Paper without (lit_base)', fmtS$(live.without?.net, 0), `${live.without?.n} trades`, cls(live.without?.net))}${stat('Difference', fmtS$((live.with?.net || 0) - (live.without?.net || 0), 0), 'the upgrades so far')}</div>`}
    <p class="muted small">${esc(live.source || '')}. ${esc(bt.how || '')}.</p>`;
}
function uptimeHTML(u) {
  if (!u || u.error) return empty('No uptime data.', u?.error || '');
  const cov = u.session_cover || [];
  const avg = cov.length ? cov.reduce((s, x) => s + x.pct, 0) / cov.length : null;
  return `<div class="nx-stats hb-mini">${stat('Server up now', u.server_s != null ? fmtN(u.server_s / 3600, 1) + ' h' : '—')}${stat('Session cover (01:55-16:00)', pct(avg), 'last 14 days, weekdays')}${stat('Restarts (30 d)', u.restarts_30d ?? '—')}</div>
    ${bars(u.days, { key: 'up_h', max: 24, label: (r) => `${r.weekday} ${r.date}: ${r.up_h} h` })}<div class="hb-axis">${(u.days || []).map((d) => `<span>${esc(d.weekday[0])}</span>`).join('')}</div>
    ${u.empty ? `<div class="hb-note">${icon('info')}<span>${esc(u.empty)}</span></div>` : ''}<p class="muted small">${esc(u.need)}. ${esc(u.source)}.</p>`;
}
const DK = { kill: ['power', 'high'], stop: ['stop', 'warn'], start: ['play', 'good'], restart: ['refresh', ''], update: ['download', ''], crash: ['warn', 'high'] };
function disciplineHTML(d) {
  if (!d || d.error) return empty('No log.', d?.error || '');
  return `<div class="nx-chips">${Object.entries(d.counts || {}).map(([k, n]) => chip(`${esc(k)} ${n}`, (DK[k] || [])[1] || '')).join('')}${chip(`manual ${d.manual || 0}`)}</div>
    ${d.rows?.length ? `<div class="hb-log">${d.rows.slice(0, 40).map((r) => `<div><span class="mono">${r.t ? etStr(r.t, true).slice(5) : '—'}</span><i>${icon((DK[r.kind] || ['dot'])[0])}</i><b>${esc(r.text)}</b><em class="muted small">${esc(r.src)}${r.manual ? ' · manual' : ''}</em></div>`).join('')}</div>` : `<div class="hb-note">${icon('info')}<span>${esc(d.empty)}</span></div>`}
    <p class="muted small">${esc(d.source)}</p>`;
}
function dataqHTML(q) {
  if (!q || q.error) return empty('No data check.', q?.error || '');
  const f1 = (f) => (f.missing ? `<div class="hb-dq"><b>${esc(f.file)}</b>${chip('missing', 'high')}</div>` : `<div class="hb-dq"><div><b>${esc(f.file)}</b>${chip(`${(f.rows || 0).toLocaleString('en-US')} bars`)}${chip(`last ${f.last ? etStr(f.last, true) : '—'} ET`, f.age_h > 96 ? 'warn' : '')}${f.short_sessions ? chip(`${f.short_sessions} short sessions`, 'warn') : chip('sessions complete', 'good')}</div>
      ${bars((f.sessions || []).map((s) => ({ v: s.pct, ...s })), { key: 'v', max: 100, h: 40, label: (s) => `${s.day}: ${s.bars}/${s.expected} bars (${s.pct}%)` })}
      <span class="muted small">last ${(f.sessions || []).length} sessions, bars vs a full 23 h session · ${f.gaps_over_3_bars} in-session gaps over 3 bars in the file${(f.intraday_gaps || []).length ? ` · latest gap ${etStr(f.intraday_gaps[0].from, true)} (${f.intraday_gaps[0].min} min)` : ''}</span></div>`);
  return `${(q.files || []).map((f) => (f.error ? empty(f.error) : f1(f))).join('')}
    <div class="hb-rules">${(q.checks || []).map((c) => `<div class="hb-rule ${c.ok ? 'g' : 'r'}"><i>${icon(c.ok ? 'check' : 'warn')}</i><div><b>${esc(c.name)}</b></div></div>`).join('')}</div>
    <p class="muted small">NinjaTrader archive: ${q.nt_archive?.files || 0} file(s)${q.nt_archive?.note ? ' · ' + esc(q.nt_archive.note) : ''}. VIX last ${esc(q.vix_last || '—')} · news built ${esc(String(q.news_built || '—').slice(0, 16))}. ${esc(q.source)}.</p>`;
}
async function renderSystem(force) {
  const el = $('#page-system'); if (!el || !isActive('system')) return;
  const [s, l] = await Promise.all([get('sys', '/api/next/hub/system', force), get('learn', '/api/next/hub/learn', force)]);
  if (!s || s.error) { el.innerHTML = hero('System', 'System', '') + empty('No system data.', s?.error || ''); return; }
  el.innerHTML = `<div class="hb-page">${hero(`${icon('sources')} System`, 'Is the machine doing its job?', 'The 3 upgrades with and without, PC uptime through the 01:55-16:00 window, every manual kill / stop / restart, and the bar data the bot trades on.')}
    ${card('Upgrades tracker · with vs without (15-min check, scale-in, BE + costs)', upgradesHTML(l?.upgrades))}
    <div class="grid cols-2">${card('PC uptime · last 14 days', uptimeHTML(s.uptime))}${card('Discipline log · kills, stops, restarts', disciplineHTML(s.discipline))}</div>
    ${card('Data quality · 1m / 5m coverage, feed gaps', dataqHTML(s.dataq))}</div>`;
}

export const firms = { show: () => renderFirms(true) };
export const business = { show: () => renderBusiness(true) };
export const market = { show: () => renderMarket(true) };
export const learn = { show: () => renderLearn(true) };
export const system = { show: () => renderSystem(true) };
