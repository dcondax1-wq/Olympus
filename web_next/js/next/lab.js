// Lab pages: the research run library (every backtest stored with its trades and days, tools/runlib.py) and the research
// write-ups. Sources: /api/next/runs, /api/next/run/<id>, /api/next/writeups (engine/next_api.py, read-only).
import { $, $$, api, esc, fmt$, fmtS$, fmtN, fmtR, cls, store } from '../util.js';
import { go } from '../app.js';
import { icon } from './icons.js';
import { mount3d } from './fx3d.js';

const FAM = { baseline: 'Baseline', risk: 'Risk & sizing', stops: 'Stops', targets: 'Targets', management: 'Management', bias: 'Bias', filters: 'Filters',
  timing: 'Timing', other: 'Other' };
const STAT = { baseline: ['Baseline', ''], 'adopt-candidate': ['Adopt candidate', 'good'], promising: ['Promising', 'info'], rejected: ['Rejected', 'bad'],
  info: ['Analysis', ''], finding: ['Finding', 'info'] };
const pct = (v) => v == null ? '—' : fmtN(v, v < 10 ? 1 : 0) + '%';
const chip = (txt, kind = '') => `<span class="nx-chip ${kind}">${txt}</span>`;
const statChip = (s) => { const [l, k] = STAT[s] || [s || '—', '']; return `<span class="nx-badge ${k}">${esc(l)}</span>`; };

// ------------------------------------------------------------------ markdown (escape first, then a small safe subset)
function inline(s) {
  return s.replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>').replace(/(^|[\s(])\*([^*\s][^*]*)\*/g, '$1<i>$2</i>')
    .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
}
export function md(src) {
  const L = esc(src || '').split('\n'), out = [];
  let i = 0;
  const para = [];
  const flush = () => { if (para.length) { out.push(`<p>${inline(para.join(' '))}</p>`); para.length = 0; } };
  while (i < L.length) {
    const l = L[i];
    if (/^```/.test(l)) { flush(); const buf = []; i++; while (i < L.length && !/^```/.test(L[i])) buf.push(L[i++]); i++; out.push(`<pre><code>${buf.join('\n')}</code></pre>`); continue; }
    const h = l.match(/^(#{1,6})\s+(.*)$/);
    if (h) { flush(); const n = Math.min(6, h[1].length + 1); out.push(`<h${n}>${inline(h[2])}</h${n}>`); i++; continue; }
    if (/^\s*\|/.test(l)) {
      flush(); const rows = [];
      while (i < L.length && /^\s*\|/.test(L[i])) rows.push(L[i++]);
      const cells = (r) => r.trim().replace(/^\||\|$/g, '').split('|').map(c => c.trim());
      const isSep = (r) => /-/.test(r) && !r.replace(/[|:\-\s]/g, '').length;
      const body = rows.filter(r => !isSep(r));
      const [head, ...rest] = body;
      out.push(`<div class="table-wrap"><table class="tbl"><tr>${cells(head || '').map(c => `<th>${inline(c)}</th>`).join('')}</tr>${rest.map(r => `<tr>${cells(r).map(c => `<td>${inline(c)}</td>`).join('')}</tr>`).join('')}</table></div>`);
      continue;
    }
    if (/^\s*([-*]|\d+\.)\s+/.test(l)) {
      flush(); const ol = /^\s*\d+\./.test(l), items = [];
      while (i < L.length && /^\s*([-*]|\d+\.)\s+/.test(L[i])) items.push(L[i++].replace(/^\s*([-*]|\d+\.)\s+/, ''));
      out.push(`<${ol ? 'ol' : 'ul'}>${items.map(x => `<li>${inline(x)}</li>`).join('')}</${ol ? 'ol' : 'ul'}>`);
      continue;
    }
    if (/^&gt;\s?/.test(l)) { flush(); const q = []; while (i < L.length && /^&gt;\s?/.test(L[i])) q.push(L[i++].replace(/^&gt;\s?/, '')); out.push(`<blockquote>${inline(q.join(' '))}</blockquote>`); continue; }
    if (/^\s*(-{3,}|\*{3,})\s*$/.test(l)) { flush(); out.push('<hr>'); i++; continue; }
    if (!l.trim()) { flush(); i++; continue; }
    para.push(l.trim()); i++;
  }
  flush();
  return out.join('');
}

// ------------------------------------------------------------------ experiments (run library)
// scope: which strategy's runs the list shows. LIT (live, reference run lit_live) by default; 'engine' = the previous strategy's
// experiments (Archive), judged against its own lock (archive_baseline). /api/next/runs tags every row with `strategy`.
const st = { fam: store.get('nx.labFam', 'all'), status: 'all', q: '', sel: null, data: null, base: null, cache: new Map(), scope: null };
const liveStrat = () => st.data?.live_strategy || 'engine';
const scopeNow = () => liveStrat() === 'lit' ? (st.scope || 'lit') : 'all';
const baseFor = (scope) => scope === 'engine' ? (st.data?.archive_baseline || 'baseline') : (st.data?.baseline || 'baseline');

function delta(v, b, kind = 'num', better = 'up') {
  if (v == null || b == null) return '';
  const d = v - b; if (Math.abs(d) < 1e-9) return '<i class="nx-d">=</i>';
  const good = better === 'up' ? d > 0 : d < 0;
  const txt = kind === '$' ? fmtS$(d) : kind === 'pct' ? (d > 0 ? '+' : '') + fmtN(d, 1) : (d > 0 ? '+' : '') + fmtN(d, 2);
  return `<i class="nx-d ${good ? 'up' : 'dn'}">${txt}</i>`;
}
const pf = (s, b) => `<span class="nx-pfd">${pct(s.p10)} / <span class="dn">${pct(s.f10)}</span>${b && b.p10 != null ? delta(s.p10, b.p10, 'pct') : ''}</span>`;
function spanRow(label, s, b) {
  if (!s?.n) return `<tr><td>${label}</td><td colspan="14" class="muted">no trades</td></tr>`;
  const dec = s.dec10 ?? (s.p10 != null && s.f10 != null ? s.p10 + s.f10 : null);
  return `<tr><td><b>${label}</b></td><td>${s.n}</td><td class="${s.tpw >= 2 ? 'up' : 'dn'}">${fmtN(s.tpw, 2)}</td><td>${pct(s.win)}</td>
    <td>${fmtN(s.pf)} ${delta(s.pf, b?.pf)}</td><td class="mono ${cls(s.net)}">${fmtS$(s.net)} ${delta(s.net, b?.net, '$')}</td><td class="mono ${cls(s.per_month)}">${s.per_month != null ? fmtS$(s.per_month) : '—'} ${delta(s.per_month, b?.per_month, '$')}</td>
    <td class="mono">${fmt$(s.dd)} ${delta(s.dd, b?.dd, '$')}</td>
    <td>${pf(s, b)}</td><td>${pct(dec)} ${delta(dec, b?.dec10 ?? (b?.p10 != null ? b.p10 + b.f10 : null), 'pct')}</td><td>${pct(s.p15)} / <span class="dn">${pct(s.f15)}</span></td>
    <td>${pct(s.p20)} / <span class="dn">${pct(s.f20)}</span></td><td class="${s.slow_pass > 50 ? 'dn' : ''}">${pct(s.slow_pass)}</td><td class="mono">${s.pass_med != null ? fmtN(s.pass_med, 0) : '—'}</td><td>${esc(s.b2b || '—')}</td></tr>`;
}
function runCard(r, base) {
  const a = r.spans?.['2026'] || {}, b = r.spans?.['2021-25'] || {}, A = base?.spans?.['2026'] || {}, B = base?.spans?.['2021-25'] || {};
  const isB = r.id === base?.id;
  const k = (s, S, lbl) => `<div class="nx-rk"><span>${lbl}</span><b>PF ${fmtN(s.pf)} ${!isB ? delta(s.pf, S.pf) : ''}</b>
    <em class="${cls(s.net)}">${fmtS$(s.net)} ${!isB ? delta(s.net, S.net, '$') : ''}${s.per_month != null ? ` <i class="nx-pm">${fmtS$(s.per_month)}/mo</i>` : ''}</em>
    <em>${fmtN(s.tpw, 1)}/wk · DD ${fmt$(s.dd)}</em>
    <em class="nx-rk-ev" title="eval decided within 2 weeks · passed / failed within 2 weeks">2wk ${pct(s.dec10 ?? (s.p10 != null && s.f10 != null ? s.p10 + s.f10 : null))} ${!isB ? delta(s.dec10, S.dec10, 'pct') : ''} · <span class="up">${pct(s.p10)}</span>/<span class="dn">${pct(s.f10)}</span></em></div>`;
  return `<button type="button" class="nx-runcard ${esc(r.status)}" data-id="${esc(r.id)}">
    <div class="nx-runcard-h">${statChip(r.status)}${r.family !== 'baseline' ? chip(esc(FAM[r.family] || r.family)) : ''}</div>
    <h4>${esc(r.title)}</h4><p class="muted small">${esc(r.verdict || r.question || '')}</p>
    <div class="nx-rks">${k(a, A, '2026')}${k(b, B, '2021-25')}</div></button>`;
}
function constellationData(rows, baseId = 'baseline') {
  const g = (r, k, f) => r.spans?.[k]?.[f] ?? null;
  return { baseline: baseId, runs: rows.map(r => ({ id: r.id, title: r.title, family: r.family, status: r.status, pf26: g(r, '2026', 'pf'), pf21: g(r, '2021-25', 'pf'),
    net26: g(r, '2026', 'net'), net21: g(r, '2021-25', 'net'), tpw26: g(r, '2026', 'tpw'), tpw21: g(r, '2021-25', 'tpw'), dd21: g(r, '2021-25', 'dd'),
    p20_21: g(r, '2021-25', 'p20'), f20_21: g(r, '2021-25', 'f20') })) };
}

async function getRun(id) {
  if (!st.cache.has(id)) st.cache.set(id, await api('/api/next/run/' + encodeURIComponent(id)));
  return st.cache.get(id);
}

function equitySvg(series, h = 230) {
  const W = 900, H = h, L = 56, R = 14, T = 12, B = 24;
  const cum = series.map(s => { let e = 0; return s.days.map(d => (e += d[1])); });
  const n = Math.max(...cum.map(c => c.length));
  const all = cum.flat().concat([0]); let lo = Math.min(...all), hi = Math.max(...all); const pad = (hi - lo) * 0.06 || 1; lo -= pad; hi += pad;
  const X = (i) => L + (n <= 1 ? 0 : i / (n - 1) * (W - L - R)), Y = (v) => T + (1 - (v - lo) / (hi - lo)) * (H - T - B);
  const path = (c) => c.map((v, i) => `${i ? 'L' : 'M'}${X(i).toFixed(1)} ${Y(v).toFixed(1)}`).join('');
  const days = series[0].days, yr = []; let last = '';
  days.forEach((d, i) => { const y = d[0].slice(0, 4); if (y !== last) { yr.push([i, y]); last = y; } });
  return `<div class="nx-viz" style="height:${H}px"><svg viewBox="0 0 ${W} ${H}" width="100%" height="${H}" preserveAspectRatio="none">
    <line x1="${L}" x2="${W - R}" y1="${Y(0)}" y2="${Y(0)}" class="nx-zero"/>
    ${[lo + pad, (lo + hi) / 2, hi - pad].map(v => `<text x="${L - 8}" y="${Y(v) + 4}" text-anchor="end" class="nx-axis">${fmtS$(Math.round(v / 100) * 100)}</text>`).join('')}
    ${yr.map(([i, y]) => `<line x1="${X(i)}" x2="${X(i)}" y1="${T}" y2="${H - B}" class="nx-grid"/><text x="${X(i) + 4}" y="${H - 6}" class="nx-axis">${y}</text>`).join('')}
    ${cum.map((c, k) => `<path d="${path(c)}" fill="none" stroke="${series[k].color}" stroke-width="${k ? 1.6 : 2.2}" ${k ? 'stroke-dasharray="5 4" opacity=".75"' : ''} vector-effect="non-scaling-stroke"/>`).join('')}
  </svg></div><div class="nx-legend">${series.map((s, k) => `<span><i style="background:${s.color}"></i>${esc(s.label)} ${fmtS$(cum[k].at(-1) || 0)}</span>`).join('')}</div>`;
}

async function renderDetail(el, id) {
  el.innerHTML = '<div class="nx-skel"><i></i><i></i></div>';
  if (!st.data) { try { st.data = await api('/api/next/runs'); } catch { /* the reference run falls back to "baseline" */ } }
  let r, b;
  const meta = (st.data?.runs || []).find(x => x.id === id), bid = baseFor(liveStrat() === 'lit' && meta?.strategy === 'engine' ? 'engine' : 'lit');
  try { [r, b] = await Promise.all([getRun(id), id === bid ? null : getRun(bid).catch(() => null)]); }
  catch (e) { el.innerHTML = `<div class="banner warn">Could not load run ${esc(id)}: ${esc(e.message)}</div>`; return; }
  const B = b?.spans || {};
  const plist = Object.entries({ ...(r.params || {}), ...(r.sizing || {}) });
  const tr = (r.trades || []).map(a => Object.fromEntries(r.trade_cols.map((c, i) => [c, a[i]])));
  el.innerHTML = `
    <div class="nx-hero"><div><button type="button" class="nx-back" id="labBack">${icon('back')}<span>All experiments</span></button>
      <div class="nx-eyebrow">${esc(FAM[r.family] || r.family)} · built ${esc(r.built || '')}</div><h2>${esc(r.title)}</h2>
      <p class="muted">${esc(r.question || '')}</p></div><div>${statChip(r.status)}</div></div>
    <div class="card nx-glass"><div class="card-h"><h3>Verdict</h3>${r.writeup ? `<button class="nx-chipbtn" type="button" data-wu="${esc(r.writeup)}"><span>Read the write-up</span>${icon('right')}</button>` : ''}</div>
      <p>${esc(r.verdict || '—')}</p>${r.notes ? `<p class="muted small">${esc(r.notes)}</p>` : ''}
      ${plist.length ? `<div class="nx-chips">${plist.map(([k, v]) => chip(`<i>${esc(k)}</i> ${esc(typeof v === 'object' ? JSON.stringify(v) : String(v))}`)).join('')}</div>` : '<p class="muted small">Same settings as the live strategy.</p>'}</div>
    <div class="card nx-glass"><div class="card-h"><h3>Headline numbers${b ? ' vs the live strategy' : ''}</h3><span class="muted small">exact live-loop replay, costs included</span></div>
      <div class="table-wrap"><table class="tbl nx-spans"><tr><th>Period</th><th>Trades</th><th>/wk</th><th>Win</th><th>PF</th><th>Net</th><th>$ / mo</th><th>Max DD</th><th>Eval 2 wk pass / fail</th><th>Decided 2 wk</th><th>3 wk pass / fail</th><th>1 mo pass / fail</th><th>Slow passes (&gt;3 wk)</th><th>Median sessions to pass</th><th>Back-to-back</th></tr>
        ${spanRow('2026', r.spans['2026'], B['2026'])}${spanRow('2021-25', r.spans['2021-25'], B['2021-25'])}${spanRow('All years', r.spans.all, B.all)}</table></div>
      <p class="muted small">${b ? 'Small coloured numbers: difference from the live strategy (green = better). ' : ''}Owner's rule: an eval should be decided within 2 weeks and never take over 3 weeks to pass, with 2–4 trades a week.</p></div>
    <div class="card nx-glass"><div class="card-h"><h3>Equity${b ? ' vs the live strategy' : ''}</h3><span class="muted small">cumulative net $ per session</span></div>
      <div class="fx3d ribbon" id="labRibbon" data-fx-card hidden></div><div id="labEq"></div></div>
    <div class="card nx-glass"><div class="card-h"><h3>By year</h3></div><div class="table-wrap"><table class="tbl"><tr><th>Year</th><th>Trades</th><th>Win</th><th>PF</th><th>Net</th></tr>
      ${Object.entries(r.years || {}).map(([y, v]) => `<tr><td class="mono"><b>${y}</b></td><td>${v.n}</td><td>${pct(v.win)}</td><td class="${(v.pf || 0) >= 1 ? 'up' : 'dn'}">${fmtN(v.pf)}</td><td class="mono ${cls(v.net)}">${fmtS$(v.net)}</td></tr>`).join('')}</table></div></div>
    <div class="card nx-glass"><div class="card-h"><h3>Trades · ${tr.length}</h3><span class="muted small">newest first</span></div>
      <div class="table-wrap"><table class="tbl"><tr><th>Day</th><th>Side</th><th>Trigger</th><th>Stop</th><th>Micros</th><th>Exit</th><th>R</th><th>$</th></tr>
      ${tr.slice(-120).reverse().map(t => `<tr><td class="mono">${esc(t.day)}</td><td class="${t.dir === 1 ? 'up' : 'dn'}">${t.dir === 1 ? 'LONG' : 'SHORT'}${t.half ? ' ½' : ''}</td><td>${esc(t.trigger || '')}</td>
        <td class="mono">${fmtN(t.risk_pts, 1)}</td><td>${t.qty}</td><td class="small">${esc(t.exit || '')}</td><td class="mono ${cls(t.r)}">${fmtR(t.r)}</td><td class="mono ${cls(t.pnl)}">${fmtS$(t.pnl)}</td></tr>`).join('')}</table></div>
      ${tr.length > 120 ? `<p class="muted small">Showing the newest 120 of ${tr.length}.</p>` : ''}</div>`;
  $('#labBack').onclick = () => { st.sel = null; render(); };
  el.querySelector('[data-wu]')?.addEventListener('click', (e) => { wst.sel = e.currentTarget.dataset.wu; go('writeups'); });
  const series = [{ label: r.title, color: '#7c8cff', days: r.days.map(d => [d[0], d[1]]) }];
  if (b) series.push({ label: bid === 'baseline' && liveStrat() === 'lit' ? 'Previous strategy (archive lock)' : 'Live strategy', color: '#3ee0c8', days: b.days.map(d => [d[0], d[1]]) });
  $('#labEq').innerHTML = equitySvg(series);
  mount3d('lab-ribbon', $('#labRibbon'), 'ribbon', { series });
}

async function render() {
  const el = $('#page-lab'); if (!el) return;
  if (st.sel) return renderDetail(el, st.sel);
  if (!st.data) el.innerHTML = '<div class="nx-skel"><i></i><i></i><i></i></div>';
  try { st.data = await api('/api/next/runs'); } catch (e) { el.innerHTML = `<div class="banner warn">Could not load the run library: ${esc(e.message)}</div>`; return; }
  const sc = scopeNow(), all = st.data.runs || [], rows = sc === 'all' ? all : all.filter(r => (r.strategy || 'engine') === sc);
  const base = all.find(r => r.id === baseFor(sc)), nLit = all.filter(r => r.strategy === 'lit').length, nOld = all.length - nLit;
  const fams = ['all', ...new Set(rows.map(r => r.family))];
  const shown = rows.filter(r => (st.fam === 'all' || r.family === st.fam) && (st.status === 'all' || r.status === st.status)
    && (!st.q || (r.title + ' ' + r.question + ' ' + r.verdict + ' ' + r.id).toLowerCase().includes(st.q)));
  const n = (s) => rows.filter(r => r.status === s).length;
  el.innerHTML = `
    <div class="nx-hero"><div><div class="nx-eyebrow">Lab · research run library · ${sc === 'engine' ? esc(st.data.archive_label || 'Archive: previous strategy') : sc === 'lit' ? 'LIT' : ''} · ${rows.length} runs · updated ${esc(st.data.built || '')}</div>
      <h2>${sc === 'engine' ? 'The previous strategy’s experiments (archive)' : sc === 'lit' ? 'LIT: every backtest, stored with its data' : 'Every backtest, stored with its data'}</h2>
      <p class="muted">${sc === 'lit' ? 'Each experiment is LIT with one idea changed, tuned and judged on 2026 only (picked on Jan–Jun, checked on Jul–Oct); 2021-25 is a reference line. The reference card is the live LIT run (lit_live). Cards show PF, net $, $ a month and the 2-week eval odds.'
        : sc === 'engine' ? 'Each run is the Liquidity Engine (the strategy before LIT) with one idea changed, judged on 2026 and 2021-25 against its own lock (run baseline). None of them is live.'
        : 'Each experiment is the exact live-loop replay with one idea changed, judged on 2026 and on 2021-25. A change is adopted only if it holds in both, keeps 2–4 trades a week and gets evals decided within 2 weeks. Cards show PF, net $, $ a month and the 2-week eval odds.'}</p></div>
      <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center">${sc !== 'all' ? `<div class="seg" id="labScope">${[['lit', `LIT · ${nLit}`], ['engine', `Archive · ${nOld}`]].map(([v, l]) => `<button class="${v === sc ? 'on' : ''}" data-v="${v}">${l}</button>`).join('')}</div>` : ''}
      <button class="btn ghost" type="button" data-goto="writeups">${icon('reports')}Write-ups</button></div></div>
    <div class="nx-stats">
      <div class="nx-stat"><span>Runs</span><b>${rows.length}</b><em>stored with every trade</em></div>
      <div class="nx-stat"><span>Adopt candidates</span><b class="up">${n('adopt-candidate')}</b><em>better in both periods</em></div>
      <div class="nx-stat"><span>Promising</span><b>${n('promising')}</b><em>help one period, no harm</em></div>
      <div class="nx-stat"><span>Rejected</span><b class="dn">${n('rejected')}</b><em>kept so we never redo them</em></div>
    </div>
    <div class="card nx-glass fx-card" data-fx-card hidden><div class="card-h"><h3>Constellation · every run</h3><span class="muted small">right = better 2021-25 PF, up = better 2026 PF · click a star</span></div><div class="fx3d constellation" id="labConst"></div></div>
    <div class="nx-toolbar">
      <div class="seg" id="labFam">${fams.map(f => `<button class="${f === st.fam ? 'on' : ''}" data-v="${f}">${f === 'all' ? 'All' : esc(FAM[f] || f)}</button>`).join('')}</div>
      <div class="seg" id="labStat">${['all', 'adopt-candidate', 'promising', 'rejected', 'info'].map(s => `<button class="${s === st.status ? 'on' : ''}" data-v="${s}">${s === 'all' ? 'Any status' : esc((STAT[s] || [s])[0])}</button>`).join('')}</div>
      <label class="nx-field grow">${icon('search')}<input class="inp" id="labQ" placeholder="Search experiments…" value="${esc(st.q)}" autocomplete="off"></label>
    </div>
    <div class="nx-count muted small">${shown.length} of ${rows.length} runs</div>
    <div class="nx-runs-grid" id="labGrid">${shown.map(r => runCard(r, base)).join('') || '<div class="empty">No runs match.</div>'}</div>`;
  $('#labScope')?.addEventListener('click', (e) => { const b = e.target.closest('button'); if (b) { st.scope = b.dataset.v; st.fam = 'all'; render(); } });
  mount3d('lab-constellation', $('#labConst'), 'constellation', constellationData(rows, base?.id), { onPick: (run) => { if (run?.id) { st.sel = run.id; render(); } } });
  $('#labFam').onclick = (e) => { const b = e.target.closest('button'); if (b) { st.fam = b.dataset.v; store.set('nx.labFam', st.fam); render(); } };
  $('#labStat').onclick = (e) => { const b = e.target.closest('button'); if (b) { st.status = b.dataset.v; render(); } };
  let tq; $('#labQ').oninput = (e) => { clearTimeout(tq); tq = setTimeout(() => { st.q = e.target.value.trim().toLowerCase(); render().then(() => { const q = $('#labQ'); q?.focus(); q?.setSelectionRange(q.value.length, q.value.length); }); }, 220); };
  $('#labGrid').onclick = (e) => { const c = e.target.closest('.nx-runcard'); if (c) { st.sel = c.dataset.id; render(); } };
}
export const experiments = { show: () => render() };
export function openRun(id) { st.sel = id; go('lab'); }
export function openArchiveRuns() { st.scope = 'engine'; st.sel = null; st.fam = 'all'; go('lab'); }

// ------------------------------------------------------------------ write-ups
const wst = { data: null, sel: null, kind: 'lit' };
async function renderWriteups() {
  const el = $('#page-writeups'); if (!el) return;
  if (!wst.data) {
    el.innerHTML = '<div class="nx-skel"><i></i><i></i></div>';
    try { wst.data = await api('/api/next/writeups'); } catch (e) { el.innerHTML = `<div class="banner warn">Could not load write-ups: ${esc(e.message)}</div>`; return; }
  }
  const items = wst.data.items || [];
  if (wst.sel) {
    const w = items.find(x => x.slug === wst.sel);
    if (w) {
      el.innerHTML = `<div class="nx-hero"><div><button type="button" class="nx-back" id="wuBack">${icon('back')}<span>All write-ups</span></button>
        <div class="nx-eyebrow">${esc(w.kind === 'archive' ? 'Archive report' : FAM[w.family] || w.family || 'Write-up')}${w.date ? ' · ' + esc(w.date) : ''}</div><h2>${esc(w.title)}</h2>
        ${w.summary ? `<p class="muted">${esc(w.summary)}</p>` : ''}</div>${w.status ? statChip(w.status) : ''}</div>
        ${(w.runs || []).length ? `<div class="nx-chips" style="margin-bottom:14px">${w.runs.map(id => `<button type="button" class="nx-chip link" data-run="${esc(id)}">${icon('variants')} ${esc(id)}</button>`).join('')}</div>` : ''}
        <article class="card nx-glass nx-md">${md(w.body)}</article>`;
      $('#wuBack').onclick = () => { wst.sel = null; renderWriteups(); };
      el.querySelectorAll('[data-run]').forEach(b => b.onclick = () => openRun(b.dataset.run));
      el.scrollTop = 0;
      return;
    }
    wst.sel = null;
  }
  const KINDS = [['lit', 'LIT write-ups', (x) => x.kind === 'writeup' && x.strategy === 'lit'], ['engine', 'Previous strategy (archive)', (x) => x.kind === 'writeup' && x.strategy !== 'lit'],
    ['archive', 'Older reports', (x) => x.kind === 'archive']];
  if (!KINDS.some(k => k[0] === wst.kind)) wst.kind = 'lit';
  const list = items.filter(KINDS.find(k => k[0] === wst.kind)[2]);
  el.innerHTML = `
    <div class="nx-hero"><div><div class="nx-eyebrow">Lab · write-ups</div><h2>Research write-ups</h2>
      <p class="muted">Plain-language reports on every experiment: what was tested, the numbers, and the verdict. LIT (the live strategy) first; the Liquidity Engine’s write-ups and the older reports are kept as the archive.</p></div>
      <div class="seg" id="wuKind">${KINDS.map(([v, l, f]) => `<button class="${v === wst.kind ? 'on' : ''}" data-v="${v}">${l} · ${items.filter(f).length}</button>`).join('')}</div></div>
    <div class="nx-wu-grid">${list.map(w => `<button type="button" class="nx-wucard" data-slug="${esc(w.slug)}">
      <div class="nx-runcard-h">${w.status ? statChip(w.status) : ''}${w.family ? chip(esc(FAM[w.family] || w.family)) : ''}${w.date ? `<span class="muted small">${esc(w.date)}</span>` : ''}</div>
      <h4>${esc(w.title)}</h4><p class="muted small">${esc(w.summary || (w.body || '').replace(/[#*`|>-]/g, ' ').slice(0, 180) + '…')}</p></button>`).join('') || '<div class="empty">No write-ups yet: the research runs write them as they finish.</div>'}</div>`;
  $('#wuKind').onclick = (e) => { const b = e.target.closest('button'); if (b) { wst.kind = b.dataset.v; renderWriteups(); } };
  el.querySelector('.nx-wu-grid').onclick = (e) => { const c = e.target.closest('.nx-wucard'); if (c) { wst.sel = c.dataset.slug; renderWriteups(); } };
}
export const writeups = { show: () => { wst.data = null; renderWriteups(); } };
