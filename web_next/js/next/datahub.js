// Data hub pages: Results (live replay), Tested Variants, What the Bot Learned, Study Trades.
// Sources: /api/next/results, /api/next/variants, /api/next/study (engine/next_api.py).
import { $, $$, api, esc, fmt$, fmtS$, fmtN, fmtR, cls, store } from '../util.js';
import { go } from '../app.js';
import { icon } from './icons.js';
import { lineChart, barChart, countAll } from './viz.js';
import { mount3d } from './fx3d.js';

let RES = null;
async function results$() { if (!RES) RES = await api('/api/next/results'); return RES; }
const fail = (el, e) => { el.innerHTML = `<div class="banner warn">Could not load: ${esc(e.message)}</div>`; };
const pct = (v) => v == null ? '—' : fmtN(v, v < 10 ? 1 : 0) + '%';

// ------------------------------------------------------------------ RESULTS
function periodCard(name, p, tag) {
  const ev = p.eval || {}, w2 = ev.within_2_weeks || {}, m1 = ev.within_1_month || {}, b2b = ev.back_to_back || {};
  const ok2 = p.per_week >= 2;
  return `<div class="card nx-glass nx-period">
    <div class="nx-period-h"><div><div class="nx-eyebrow">${esc(tag)}</div><h3>${esc(name)}</h3><span class="muted small">${esc(p.from)} → ${esc(p.to)}</span></div>
      <span class="nx-badge ${p.pf >= 1.5 ? 'good' : p.pf >= 1 ? '' : 'bad'}">PF ${fmtN(p.pf)}</span></div>
    <div class="nx-big ${cls(p.net)}" data-count="${p.net}" data-fmt="s$">${fmtS$(p.net)}</div>
    <div class="nx-kv">
      <div><span>Trades</span><b>${p.trades}</b></div>
      <div><span>Per week</span><b class="${ok2 ? 'up' : 'dn'}">${fmtN(p.per_week, 1)}</b></div>
      <div><span>Weeks with 2+</span><b>${pct(p.weeks_2plus_pct)}</b></div>
      <div><span>Win rate</span><b>${pct(p.win_pct)}</b></div>
      <div><span>Max drawdown</span><b class="dn">${fmt$(p.max_dd)}</b></div>
      <div><span>Worst day</span><b>${fmt$(p.worst_day)}</b></div>
      <div><span>Median stop</span><b>${fmtN(p.median_stop_pts, 1)} pts</b></div>
      <div><span>Half-size trades</span><b>${p.half_size_trades ?? '—'}</b></div>
    </div>
    <div class="nx-evals">
      <div class="nx-eval"><span>Eval in 2 weeks</span><div class="nx-pf"><b class="up">${pct(w2.pass_pct)}</b><i>pass</i><b class="dn">${pct(w2.fail_pct)}</b><i>fail</i></div>
        <div class="nx-meter2"><i class="p" style="width:${w2.pass_pct || 0}%"></i><i class="f" style="width:${w2.fail_pct || 0}%"></i></div></div>
      <div class="nx-eval"><span>Eval in 1 month</span><div class="nx-pf"><b class="up">${pct(m1.pass_pct)}</b><i>pass</i><b class="dn">${pct(m1.fail_pct)}</b><i>fail</i></div>
        <div class="nx-meter2"><i class="p" style="width:${m1.pass_pct || 0}%"></i><i class="f" style="width:${m1.fail_pct || 0}%"></i></div></div>
      <div class="nx-eval"><span>Back-to-back evals</span><div class="nx-pf"><b class="up">${b2b.passed ?? '—'}</b><i>passed</i><b class="dn">${b2b.failed ?? '—'}</b><i>failed</i></div></div>
    </div>
  </div>`;
}

function runsStrip(runs) {
  return `<div class="nx-runs">${(runs || []).map(r => `<span class="nx-run ${r.result === 'PASS' ? 'pass' : r.result === 'FAIL' ? 'fail' : 'open'}" title="${esc(r.start)} · ${r.result} after ${r.sessions} sessions">
    ${icon(r.result === 'PASS' ? 'check' : r.result === 'FAIL' ? 'close' : 'clock')}<b>${esc(r.start.slice(2))}</b><i>${r.sessions}d</i></span>`).join('')}</div>`;
}

const rs = { eq: store.get('nx.resEq', '2026') };
async function showResults() {
  const el = $('#page-results');
  try {
    const d = await results$();
    const P = d.periods, m = d.meta;
    const years = Object.keys(P).filter(k => /^\d{4}$/.test(k));
    el.innerHTML = `
      <div class="nx-hero">
        <div><div class="nx-eyebrow">Results · exact live-loop replay · built ${esc(m.built)}</div><h2>${esc(m.strategy.split(' (')[0])}</h2>
          <p class="muted">${esc(m.data?.source || '')}: ${esc(m.data?.first_session)} → ${esc(m.data?.last_session)}, ${m.data?.sessions} sessions. Costs: ${esc(m.costs?.instrument)}, $${m.costs?.commission_round_trip_per_micro}/micro round trip, ${m.costs?.slippage_pts} pt slippage.</p></div>
        <button class="btn ghost" data-goto="trades">${icon('trades')}All trades</button>
      </div>
      <div class="grid cols-2">${periodCard('2026 YTD', P['2026 YTD'], 'This year')}${periodCard('5 years', P['All years'], '2021-11 → today')}</div>
      <div class="card nx-glass"><div class="card-h"><h3>Equity</h3>
        <div class="seg sm" id="resEqSeg">${[['2026', '2026'], ['all', '5 years']].map(([v, l]) => `<button data-v="${v}" class="${rs.eq === v ? 'on' : ''}">${l}</button>`).join('')}</div></div>
        <div id="resEq"></div></div>
      <div class="card nx-glass"><div class="card-h"><h3>Net by month</h3><span class="muted small">every month since 2021-11 · hover a bar</span></div><div id="resMonths"></div></div>
      <div class="card nx-glass fx-card" data-fx-card hidden><div class="card-h"><h3>Month city · net P&amp;L of every month</h3><span class="muted small">towers up = profit, down = loss · drag to turn · click a tower</span></div><div class="fx3d city" id="resCity"></div></div>
      <div class="grid cols-2">
        <div class="card nx-glass"><div class="card-h"><h3>By year</h3><span class="muted small">a change is adopted only if it holds in 2026 and 2021-25</span></div>
          <div class="table-wrap"><table class="tbl"><tr><th>Year</th><th>Trades</th><th>/wk</th><th>2+ wks</th><th>Win</th><th>PF</th><th>Net</th><th>Max DD</th><th>Eval 1mo</th></tr>
          ${years.map(y => { const p = P[y]; return `<tr><td class="mono"><b>${y}</b></td><td>${p.trades}</td><td class="${p.per_week >= 2 ? 'up' : 'dn'}">${fmtN(p.per_week, 1)}</td><td>${pct(p.weeks_2plus_pct)}</td>
            <td>${pct(p.win_pct)}</td><td class="${p.pf >= 1 ? 'up' : 'dn'}">${fmtN(p.pf)}</td><td class="mono ${cls(p.net)}">${fmtS$(p.net)}</td><td class="mono">${fmt$(p.max_dd)}</td>
            <td class="small">${pct(p.eval?.within_1_month?.pass_pct)} / <span class="dn">${pct(p.eval?.within_1_month?.fail_pct)}</span></td></tr>`; }).join('')}</table></div></div>
        <div class="card nx-glass"><div class="card-h"><h3>By stop size</h3><span class="muted small">wide stop = fewer micros = less $ risk</span></div>
          <div class="table-wrap"><table class="tbl"><tr><th>Stop pts</th><th>Trades</th><th>Win</th><th>Avg R</th><th>Micros</th><th>$ risk</th></tr>
          ${(d.stop_buckets || []).map(b => `<tr><td class="mono"><b>${esc(b.stop_pts)}</b></td><td>${b.trades}</td><td>${pct(b.win_pct)}</td><td class="mono ${cls(b.avg_r)}">${fmtR(b.avg_r)}</td>
            <td>${b.median_micros}</td><td class="mono">${fmt$(b.median_risk_usd)}</td></tr>`).join('')}</table></div></div>
      </div>
      <div class="card nx-glass"><div class="card-h"><h3>Back-to-back MFFU evals</h3><span class="muted small">start a new eval the day after each one ends · 5 years</span></div>
        ${runsStrip(P['All years'].eval?.back_to_back?.runs)}</div>
      <div class="note">${esc(m.method || '')}</div>`;
    countAll(el);
    drawEq(d);
    const months = Object.entries(d.months || {});
    mount3d('results-city', $('#resCity'), 'city', d.months || {});
    barChart($('#resMonths'), months.map(([k, v]) => ({ x: k.slice(2), y: v.net, tip: `<b>${k}</b><span>${fmtS$(v.net)}</span><span>${v.trades} trades · ${v.wins} wins</span>` })), { h: 210 });
    $('#resEqSeg').onclick = (e) => { const b = e.target.closest('button'); if (!b) return; rs.eq = b.dataset.v; store.set('nx.resEq', rs.eq); $$('#resEqSeg button').forEach(x => x.classList.toggle('on', x === b)); drawEq(d); };
  } catch (e) { fail(el, e); }
}
function drawEq(d) {
  let eq = 0, peak = 0;
  const days = (d.days || []).filter(x => rs.eq === 'all' || x.date.startsWith('2026'));
  lineChart($('#resEq'), days.map(x => {
    eq += x.pnl; peak = Math.max(peak, eq);
    return { x: x.date.slice(2), y: eq, tip: `<b>${x.date}</b><span>day ${fmtS$(x.pnl)} · ${x.trades} trade${x.trades === 1 ? '' : 's'}</span><span>total ${fmtS$(eq)} · from peak ${fmt$(eq - peak)}</span>` };
  }), { h: 240 });
}

// ------------------------------------------------------------------ TESTED VARIANTS
const vs = { sort: 'y2026.pf', dir: -1, q: '', period: 'both' };
async function showVariants() {
  const el = $('#page-variants');
  try {
    const v = await api('/api/next/variants');
    const cols = v.columns || {};
    const keys = ['n', 'tpw', 'wk2', 'win', 'pf', 'net', 'dd', 'stop', 'p10', 'f10', 'p20', 'f20', 'b2b'];
    const get = (r, path) => path.split('.').reduce((o, k) => o?.[k], r);
    const draw = () => {
      let rows = (v.rows || []).filter(r => !vs.q || r.name.toLowerCase().includes(vs.q));
      rows = rows.sort((a, b) => { const x = get(a, vs.sort), y = get(b, vs.sort); return ((typeof x === 'number' ? x : -1e9) - (typeof y === 'number' ? y : -1e9)) * vs.dir; });
      const periods = vs.period === 'both' ? ['y2026', 'y5'] : [vs.period];
      const cell = (r, p, k) => {
        const x = r[p]?.[k];
        if (x == null) return '<td class="muted">—</td>';
        const c = k === 'net' ? cls(x) : k === 'pf' ? (x >= 1.5 ? 'up' : x < 1 ? 'dn' : '') : k === 'tpw' ? (x >= 2 ? '' : 'dn') : k === 'dd' ? 'dn' : '';
        const t = k === 'net' || k === 'dd' ? fmtS$(x) : typeof x === 'number' && !Number.isInteger(x) ? fmtN(x, k === 'pf' ? 2 : 1) : esc(x);
        return `<td class="mono ${c}">${t}</td>`;
      };
      $('#varTable').innerHTML = `<table class="tbl nx-vtbl"><thead><tr><th rowspan="${periods.length > 1 ? 2 : 1}" class="nx-sticky">Variant</th>
        ${periods.map(p => `<th colspan="${keys.length}" class="nx-grp">${p === 'y2026' ? '2026' : '5 years'}</th>`).join('')}</tr>
        ${periods.length > 1 ? `<tr>${periods.map(p => keys.map(k => th(p, k)).join('')).join('')}</tr>` : ''}
        ${periods.length === 1 ? `<tr><th class="nx-sticky"></th>${keys.map(k => th(periods[0], k)).join('')}</tr>` : ''}</thead>
        <tbody>${rows.map(r => `<tr><td class="nx-sticky"><b>${esc(r.name)}</b></td>${periods.map(p => keys.map(k => cell(r, p, k)).join('')).join('')}</tr>`).join('')}</tbody></table>`;
      $$('#varTable th[data-s]').forEach(h => h.onclick = () => { const s = h.dataset.s; vs.dir = vs.sort === s ? -vs.dir : -1; vs.sort = s; draw(); });
    };
    const th = (p, k) => `<th data-s="${p}.${k}" title="${esc(cols[k] || k)}" class="nx-sort ${vs.sort === p + '.' + k ? 'on' : ''}">${esc(k)}${vs.sort === p + '.' + k ? icon(vs.dir < 0 ? 'down' : 'up') : ''}</th>`;
    el.innerHTML = `
      <div class="nx-hero"><div><div class="nx-eyebrow">Tested variants · built ${esc(v.built || '')}</div><h2>${(v.rows || []).length} variants, two periods</h2>
        <p class="muted">${esc(v.note || '')}. Adopted only if it holds in 2026 <b>and</b> 2021-25 and keeps 2+ trades a week.</p></div></div>
      <div class="nx-toolbar">
        <div class="seg" id="varPer">${[['both', 'Both'], ['y2026', '2026'], ['y5', '5 years']].map(([k, l]) => `<button data-v="${k}" class="${vs.period === k ? 'on' : ''}">${l}</button>`).join('')}</div>
        <label class="nx-field grow">${icon('search')}<input class="inp" id="varQ" placeholder="Filter variants (engine, ATM, tgt, stop…)" autocomplete="off"></label>
      </div>
      <div class="card nx-glass nx-flush"><div class="table-wrap nx-wide" id="varTable"></div></div>
      <div class="card nx-glass"><div class="card-h"><h3>Columns</h3></div><div class="nx-legend">${keys.map(k => `<span><b class="mono">${k}</b> ${esc(cols[k] || '')}</span>`).join('')}</div></div>`;
    $('#varPer').onclick = (e) => { const b = e.target.closest('button'); if (!b) return; vs.period = b.dataset.v; if (!vs.sort.startsWith(vs.period) && vs.period !== 'both') vs.sort = vs.period + '.pf'; $$('#varPer button').forEach(x => x.classList.toggle('on', x === b)); draw(); };
    $('#varQ').oninput = (e) => { vs.q = e.target.value.trim().toLowerCase(); draw(); };
    draw();
  } catch (e) { fail(el, e); }
}

// ------------------------------------------------------------------ WHAT THE BOT LEARNED
const ls = { v: 'all' };
async function showLearned() {
  const el = $('#page-learned');
  try {
    const d = await results$();
    const L = d.lessons || {}, sm = L.summary || {}, f = L.factors || [];
    const kind = (v) => v.startsWith('better') ? 'good' : v.startsWith('worse') ? 'bad' : v.startsWith('not enough') ? 'na' : 'mixed';
    const draw = () => {
      const rows = f.filter(x => ls.v === 'all' || kind(x.verdict) === ls.v);
      $('#lrnRows').innerHTML = rows.map(x => `<div class="nx-lesson ${kind(x.verdict)}">
        <div class="nx-lesson-h"><span class="nx-eyebrow">${esc(x.factor)}</span><b>${esc(x.value)}</b><span class="nx-verdict ${kind(x.verdict)}">${icon(kind(x.verdict) === 'good' ? 'up' : kind(x.verdict) === 'bad' ? 'down' : 'minus')}${esc(x.verdict)}</span></div>
        <div class="nx-lesson-b">
          <div><span>2021-25</span><b class="${cls(x.avg_r_2021_25)}">${fmtR(x.avg_r_2021_25)}</b><i>${x.n_2021_25} trades · win ${pct(x.win_2021_25)}</i></div>
          <div><span>2026</span><b class="${cls(x.avg_r_2026)}">${fmtR(x.avg_r_2026)}</b><i>${x.n_2026} trades · win ${pct(x.win_2026)}</i></div>
        </div></div>`).join('') || '<div class="empty">Nothing in this group.</div>';
    };
    const cnt = (k) => f.filter(x => kind(x.verdict) === k).length;
    el.innerHTML = `
      <div class="nx-hero"><div><div class="nx-eyebrow">What the bot learned · ${f.length} factors checked</div><h2>Only what held in both periods counts</h2>
        <p class="muted">${esc(sm.how_it_learns || '')}</p></div>
        <button class="btn ghost" data-goto="memory">${icon('memory')}Trade memory</button></div>
      <div class="nx-stats">
        <div class="nx-stat"><span>Baseline avg R</span><b class="${cls(sm.baseline_avg_r?.['2021_25'])}">${fmtR(sm.baseline_avg_r?.['2021_25'])}</b><em>2021-25</em></div>
        <div class="nx-stat"><span>Baseline avg R</span><b class="${cls(sm.baseline_avg_r?.['2026'])}">${fmtR(sm.baseline_avg_r?.['2026'])}</b><em>2026</em></div>
        <div class="nx-stat"><span>Wins hit target</span><b>${pct(sm.wins?.hit_target_pct)}</b><em>${sm.wins?.count} wins · avg ${fmtR(sm.wins?.avg_win_r)}</em></div>
        <div class="nx-stat"><span>Losses never +0.3R</span><b>${pct(sm.losses?.never_reached_0_3R_pct)}</b><em>${sm.losses?.count} losses</em></div>
        <div class="nx-stat"><span>Were +1R, then lost</span><b class="dn">${pct(sm.losses?.were_plus_1R_then_lost_pct)}</b><em>stopped in 2 bars ${pct(sm.losses?.stopped_within_2_bars_pct)}</em></div>
      </div>
      <div class="nx-toolbar"><div class="seg" id="lrnSeg">${[['all', `All ${f.length}`], ['good', `Lean in ${cnt('good')}`], ['bad', `Avoid ${cnt('bad')}`], ['mixed', `Mixed ${cnt('mixed')}`], ['na', `Thin ${cnt('na')}`]]
        .map(([k, l]) => `<button data-v="${k}" class="${ls.v === k ? 'on' : ''}">${l}</button>`).join('')}</div></div>
      <div class="nx-lessons" id="lrnRows"></div>`;
    $('#lrnSeg').onclick = (e) => { const b = e.target.closest('button'); if (!b) return; ls.v = b.dataset.v; $$('#lrnSeg button').forEach(x => x.classList.toggle('on', x === b)); draw(); };
    draw();
  } catch (e) { fail(el, e); }
}

// ------------------------------------------------------------------ STUDY TRADES
async function showStudy() {
  const el = $('#page-study');
  try {
    const d = await api('/api/next/study');
    const items = d.items || [];
    el.innerHTML = `
      <div class="nx-hero"><div><div class="nx-eyebrow">Study trades · research/study</div><h2>${items.length} trade${items.length === 1 ? '' : 's'} under review</h2>
        <p class="muted">Annotated charts and the engine's numbers for trades you are reviewing. Make more with <span class="mono">tools/trade_gallery.py</span>.</p></div></div>
      <div class="nx-study">${items.map(it => {
        const tr = it.data?.trades || [];
        return `<article class="card nx-glass nx-study-c">
          ${it.image ? `<a class="nx-study-img" href="/api/next/study/file/${encodeURIComponent(it.image)}" target="_blank" rel="noopener"><img loading="lazy" src="/api/next/study/file/${encodeURIComponent(it.image)}" alt="${esc(it.title)} chart"></a>` : ''}
          <div class="nx-study-b"><div class="nx-eyebrow">${esc(it.date)}</div><h3>${esc(it.title)}</h3>
            ${tr.map(t => `<div class="nx-kv sm"><div><span>Side</span><b class="${t.dir === 1 ? 'up' : 'dn'}">${t.dir === 1 ? 'LONG' : 'SHORT'}</b></div><div><span>R</span><b class="${cls(t.r)}">${fmtR(t.r)}</b></div>
              <div><span>P&amp;L</span><b class="${cls(t.pnl)}">${fmtS$(t.pnl)}</b></div><div><span>Stop</span><b>${fmtN(t.risk_pts, 1)} pts</b></div><div><span>Micros</span><b>${t.qty ?? '—'}</b></div>
              <div><span>Exit</span><b>${esc(t.exit || '—')}</b></div></div>`).join('')}
            ${it.data?.params ? `<div class="nx-chips">${Object.entries(it.data.params).map(([k, v]) => `<span class="nx-chip"><i>${esc(k)}</i> ${esc(v)}</span>`).join('')}</div>` : ''}
          </div></article>`;
      }).join('') || '<div class="empty">No study trades yet.</div>'}</div>`;
  } catch (e) { fail(el, e); }
}

export const results = { show: showResults };
export const variants = { show: showVariants };
export const learned = { show: showLearned };
export const study = { show: showStudy };
export { results$, go };
