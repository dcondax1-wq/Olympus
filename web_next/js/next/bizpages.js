// Business tools on the PC dashboard (read-only; data from GET /api/next/hub/biz = tools/business.py view()):
//   monthly P&L statement (PDF / HTML download), payout eligibility per account, tax year (CSV, not tax advice), next-eval
//   purchase planner, funded scaling calendar (expected + downside), Z06 savings, ROI per account / firm, the expense logs,
//   and the weekly rule-page + discount-code watchers (Prop Firms page). Nothing here touches the bot.
import { esc, fmt$, fmtS$, fmtN, cls } from '../util.js';
import { icon } from './icons.js';

const ok = (v) => v != null && v !== '' && !Number.isNaN(+v);
const usd = (v, d = 0) => (ok(v) ? fmt$(+v, d) : '—');
const sus = (v, d = 0) => (ok(v) ? fmtS$(+v, d) : '—');
const pct = (v, d = 0) => (ok(v) ? (+v).toFixed(d) + '%' : '—');
const card = (title, body, tools = '') => `<section class="card nx-glass hb-card"><div class="card-h"><h3>${title}</h3>${tools ? `<div class="card-tools">${tools}</div>` : ''}</div>${body}</section>`;
const stat = (k, v, sub = '', c = '') => `<div class="nx-stat"><span>${k}</span><b class="${c}">${v}</b>${sub ? `<em>${sub}</em>` : ''}</div>`;
const chip = (t, k = '') => `<span class="nx-chip ${k}">${t}</span>`;
const bad = (x) => (!x ? '<p class="muted small">Not available.</p>' : x.error ? `<p class="muted small">Not available: ${esc(x.error)}</p>` : '');
const tbl = (head, rows) => `<div class="pc-tw"><table class="nx-vtbl pc-t"><thead><tr>${head.map((h) => `<th>${h}</th>`).join('')}</tr></thead><tbody>${rows.join('')}</tbody></table></div>`;
const ST = { ready: ['good', 'can request'], allowed_wait: ['warn', 'allowed, habit says wait'], not_yet: ['', 'not yet'], not_funded: ['', 'eval first'], unknown: ['warn', 'balance missing'] };

function statementHTML(s, prev) {
  if (!s || s.error) return bad(s);
  const B = s.business || {}, T = s.trading || {};
  const link = (m, h) => `/api/next/hub/biz/statement/${encodeURIComponent(m)}${h ? '?html=1' : ''}`;
  const btns = [s, prev].filter((x) => x && x.month).map((x) => `<a class="btn ghost sm" href="${link(x.month)}" target="_blank" rel="noopener">${icon('reports')}<span>${esc(x.month)} PDF</span></a>`).join('')
    + `<a class="btn ghost sm" href="${link(s.month, 1)}" target="_blank" rel="noopener">${icon('external')}<span>HTML</span></a>`;
  return `<div class="nx-stats hb-mini">${stat('Fees', usd(B.fees_total, 2), esc(s.month))}${stat('Payouts', usd(B.payouts_total, 2))}${stat('Net this month', sus(B.net, 2), '', cls(B.net))}
      ${stat('Year to date', sus(B.ytd_net, 2), `since the start ${sus(B.all_net, 2)}`, cls(B.ytd_net))}</div>
    <p class="small">Bot trades routed: <b>${T.trades || 0}</b> (${T.wins || 0} won, ${T.losses || 0} lost), account P&amp;L <b class="${cls(T.pnl)}">${sus(T.pnl, 2)}</b>. <span class="muted">${esc(T.note || '')}</span></p>
    <div class="nx-toolbar">${btns}</div><p class="muted small">${esc(s.tax_label || '')}</p>`;
}
function payoutHTML(p) {
  if (!p || p.error) return bad(p);
  return tbl(['Account', 'Status', 'What to do', 'Ask when profit ≥'], (p.rows || []).map((r) => {
    const s = ST[r.status] || ['', r.status];
    return `<tr><td><b>${esc((r.firm || '').replace('MyFundedFutures', 'MFFU'))} ${esc(r.plan || '')}</b><br><span class="muted small">${esc(r.stage || '')}</span></td><td>${chip(esc(s[1]), s[0])}</td>
      <td class="hb-wrap small">${esc(r.text || '')}${(r.checks || []).map((c) => `<br>${c.ok ? '✓' : '✗'} ${esc(c.rule)} <span class="muted">${esc(c.now)}</span>`).join('')}</td><td>${usd(r.need_habit)}<br><span class="muted small">buffer ${usd(r.rules?.buffer)} + ${usd(Math.max(r.rules?.pay_min || 0, r.habit || 0))}</span></td></tr>`;
  })) + `<p class="muted small">${icon('info')} ${esc(p.how || '')} A phone push goes out once when an account can request.</p>`;
}
function taxHTML(t) {
  if (!t || t.error) return bad(t);
  return `<div class="hb-note warn">${icon('warn')}<b>${esc(t.label || 'Not tax advice')}</b></div>
    <div class="nx-stats hb-mini">${stat('Fees ' + esc(t.year), usd(t.fees, 2))}${stat('Payouts', usd(t.payouts, 2))}${stat('Net', sus(t.net, 2), '', cls(t.net))}${stat('Set aside', usd(t.set_aside, 2), `${pct(t.pct)} of positive net`)}</div>
    ${tbl(['Quarter', 'Fees', 'Payouts', 'Net', 'Set aside'], (t.quarters || []).map((q) => `<tr><td>${esc(q.q)}</td><td>${usd(q.fees, 2)}</td><td>${usd(q.payouts, 2)}</td><td class="${cls(q.net)}">${sus(q.net, 2)}</td><td>${usd(q.set_aside, 2)}</td></tr>`))}
    <div class="nx-toolbar"><a class="btn ghost sm" href="/api/next/hub/biz/tax/${encodeURIComponent(t.year)}.csv">${icon('download')}<span>tax_${esc(t.year)}.csv</span></a></div>
    <p class="muted small">${esc(t.note || '')}</p>`;
}
function plannerHTML(p) {
  if (!p || p.error) return bad(p);
  const code = (c) => `<span class="nx-chip ${c.st === 'confirmed' ? 'good' : 'warn'}" title="${esc([c.off, c.seen, c.from].filter(Boolean).join(' · '))}">${/^\(/.test(c.code) ? esc(c.code) : `<b class="mono" data-copy="${esc(c.code)}">${esc(c.code)}</b>`} ${esc(c.st || '')}</span>`;
  return `<div class="nx-stats hb-mini">${stat('Cash for evals', usd(p.cash, 2), `budget ${usd(p.budget)} − fees ${usd(p.fees_paid, 2)} + payouts ${usd(p.payouts)}`)}${stat('Stagger', `${p.stagger} sessions`, `last start ${esc(p.last_start)}`)}</div>
    <div class="hb-steps">${(p.steps || []).map((s, i) => `<div class="hb-step ${s.due ? '' : 'off'}"><i>${i + 1}</i><div><b>${esc(s.name || s.plan)}</b> ${s.due ? chip('buy now', 'good') : chip(esc(s.wait || 'later'))}
        <p class="small">${esc(s.why || '')} · from ${esc(s.date)}${ok(s.h2_month) ? ` · ~${usd(s.h2_month)}/mo H2` : ''}</p><div class="nx-chips">${(s.codes || []).map(code).join('')}</div></div>
      <div class="hb-step-n"><b>${usd(s.price, 2)}</b><em>${esc(s.price_basis || '')}</em>${ok(s.list) && s.list !== s.price ? `<em class="muted">list ${usd(s.list, 2)}</em>` : ''}</div></div>`).join('')}</div>
    <p class="muted small">${icon('info')} ${esc(p.rule || '')}</p><p class="muted small">${icon('warn')} ${esc(p.warn || '')}</p>`;
}
function calendarHTML(c) {
  if (!c || c.error) return bad(c);
  const tr = c.trio || {};
  return `<div class="nx-stats hb-mini">${stat('Trio, expected', `${usd(tr.h2_month)}/mo`, `months 4-6 ${usd(tr.h2_m46)}/mo · Jul-Oct trades`)}${stat('Downside', `${sus(tr.down_month)}/mo`, '2021-25 trades', cls(tr.down_month))}${stat('Lose money in 6 mo', pct(tr.h2_lose_6m, 1), 'H2 Monte Carlo')}</div>
    ${tbl(['Month', 'Buy', 'Accounts', 'Expected $', 'Cumulative', 'Downside cum.'], (c.rows || []).map((r) => `<tr><td>${esc(r.month)}</td><td class="hb-wrap small">${esc((r.buy || []).join(', ') || '—')}</td><td>${r.accounts}</td>
      <td class="${cls(r.usd)}">${sus(r.usd)}</td><td class="${cls(r.cum)}"><b>${sus(r.cum)}</b></td><td class="${cls(r.down_cum)}">${sus(r.down_cum)}</td></tr>`))}
    <p class="muted small">${esc(c.how || '')}</p><p class="muted small">${icon('warn')} ${esc(c.warn || '')}</p>`;
}
function goalHTML(g) {
  if (!g || g.error) return bad(g);
  const m = (x) => (ok(x) ? `${fmtN(x, 0)} months` : 'never on this rate');
  return `<div><b>${esc(g.name)}</b> <span class="muted small">${usd(g.target)}${g.placeholder ? ' (placeholder price: set yours)' : ''}</span>
      <div class="pc-meter"><i style="width:${Math.max(0, Math.min(100, g.pct || 0)).toFixed(1)}%"></i></div><span class="small">${usd(g.saved, 0)} saved (${pct(g.pct, 1)}) · ${usd(g.left)} to go</span></div>
    <div class="nx-kv sm"><div><span>Expected, 3 accounts (${usd(g.rate_h2)}/mo)</span><b>${m(g.months_h2)}</b></div><div><span>Conservative, Builder 50K alone (${usd(g.rate_cons)}/mo)</span><b>${m(g.months_cons)}</b></div>
      <div><span>Downside, 2021-25 trades (${sus(g.rate_down)}/mo)</span><b>${ok(g.rate_down) && g.rate_down > 0 ? m(g.left / (g.rate_down * (g.share || 1))) : 'never'}</b></div></div>
    <p class="muted small">${esc(g.how || '')} ${esc(g.note || '')}</p>`;
}
function roiHTML(r) {
  if (!r || r.error) return bad(r);
  const T = r.total || {};
  return tbl(['Account', 'Stage', 'Fees', 'Payouts', 'Net', 'ROI', 'Days to 1st payout'], (r.accounts || []).map((a) => `<tr><td><b>${esc((a.firm || '').replace('MyFundedFutures', 'MFFU'))} ${esc(a.plan || '')}</b></td><td>${esc(a.stage || '')}</td><td>${usd(a.fees, 2)}</td><td>${usd(a.payouts, 2)}</td>
      <td class="${cls(a.net)}">${sus(a.net, 2)}</td><td>${pct(a.roi_pct)}</td><td>${ok(a.days_to_first_payout) ? a.days_to_first_payout : '—'}</td></tr>`))
    + tbl(['Firm', 'Accounts', 'Fees', 'Payouts', 'Net', 'ROI'], [...(r.firms || []).map((f) => `<tr><td><b>${esc(f.firm)}</b></td><td>${f.accounts}</td><td>${usd(f.fees, 2)}</td><td>${usd(f.payouts, 2)}</td><td class="${cls(f.net)}">${sus(f.net, 2)}</td><td>${pct(f.roi_pct)}</td></tr>`),
      `<tr><td><b>All</b></td><td></td><td>${usd(T.fees, 2)}</td><td>${usd(T.payouts, 2)}</td><td class="${cls(T.net)}"><b>${sus(T.net, 2)}</b></td><td>${pct(T.roi_pct)}</td></tr>`])
    + `<p class="muted small">${esc(r.how || '')}</p>`;
}
function logsHTML(v) {
  const L = v.logs || {}, F = v.files || {};
  return `<div class="nx-kv sm"><div><span>Expense log</span><b class="mono">${esc(F.expenses || '')} · ${L.expenses_rows ?? 0} rows</b></div><div><span>Payout log</span><b class="mono">${esc(F.payouts || '')} · ${L.payouts_rows ?? 0} rows</b></div>
    <div><span>Excel tracker</span><b class="mono">${esc(F.tracker || '')}</b></div><div><span>Keep them equal</span><b class="mono">${esc(F.sync || '')}</b></div></div>
    <p class="muted small">Add a row: <span class="mono">python tools/business.py add-expense --usd 115.40 --firm "Lucid Trading" --account lucid_50k --type "Eval purchase" --desc "LucidPro 50K eval"</span> (copies it into the Excel file too). Settings (budget, habit, goal, tax %): <span class="mono">${esc(F.settings || '')}</span>.</p>`;
}

export function bizSections(v) {
  if (!v || v.error) return card('Business tools', bad(v || { error: 'no data' }));
  const sec = (t) => `<div class="hb-sec">${t}</div>`;
  return `${sec('Statement, payouts and taxes')}
    <div class="grid cols-2">${card('Monthly P&amp;L statement', statementHTML(v.statement, v.statement_prev), '<span class="muted small">PDF</span>')}${card('Payout eligibility · per account', payoutHTML(v.payouts))}</div>
    <div class="grid cols-2">${card('Tax year · not tax advice', taxHTML(v.tax))}${card('ROI per account and firm', roiHTML(v.roi))}</div>
    ${sec('Growing the business')}
    ${card('Next eval to buy · purchase planner', plannerHTML(v.planner), '<span class="muted small">your prices · codes: verify at checkout</span>')}
    <div class="grid cols-2">${card('Funded scaling calendar · expected and downside', calendarHTML(v.calendar))}${card('Z06 savings', goalHTML(v.goal))}</div>
    ${card('Expense and payout logs', logsHTML(v))}
    <p class="muted small">${esc(v.disclaimer || '')}</p>`;
}

export function watchCard(v) {
  const w = (v && v.watch && !v.watch.error) ? v.watch : null;
  if (!w) return card('Weekly watchers · rule pages and codes', bad(v?.watch || { error: 'no watcher data yet' }));
  const R = w.rules || {}, C = w.codes || {};
  const rules = `<p class="small">Rule pages: <b>${R.ok || 0}</b> of ${R.pages || 0} read OK${R.updated ? ` · last run ${esc(R.updated)}` : ' · not run yet'}.</p>
    ${(R.changes || []).length ? tbl(['Changed', 'Firm', 'Page'], R.changes.map((c) => `<tr><td>${esc(c.seen)}</td><td>${esc(c.firm)}</td><td class="hb-wrap"><a href="${esc(c.url)}" target="_blank" rel="noopener">${esc(c.key)}</a></td></tr>`)) : '<p class="muted small">No rule-page change seen.</p>'}
    ${(R.failing || []).length ? `<p class="muted small">${icon('warn')} Unreachable: ${R.failing.map((f) => `${esc(f.key)} (${esc(f.error)})`).join(', ')}. Never pushes; tried again next week.</p>` : ''}`;
  const codes = (C.rows || []).length ? tbl(['Firm', 'Code', 'Off', 'Seen', 'Source'], C.rows.map((c) => `<tr><td>${esc(c.firm_name || c.firm)}</td><td><b class="mono" data-copy="${esc(c.code)}">${esc(c.code)}</b> ${chip('unverified', 'warn')}${c.new ? ' ' + chip('new') : ''}</td><td>${esc(c.off || '—')}</td><td>${esc(c.seen || '')}</td><td class="hb-wrap small">${esc(c.source || '')}</td></tr>`))
    : '<p class="muted small">No new codes found yet.</p>';
  return card('Weekly watchers · rule pages and discount codes', `${rules}<h4>New discount codes (unverified)</h4>${codes}
    <p class="muted small">${icon('info')} ${esc(w.schedule || '')}. Codes come from third-party pages: verify at checkout. A changed page means "read it again", not that a rule changed.</p>`);
}
