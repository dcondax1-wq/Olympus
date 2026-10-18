// Data → Evals and Data → Intraday: two Lab views fed by research files served as /api/next/lab/<name>
//   montecarlo.json    {built, paths:[{days:[balances], result, days_n}], hist:{pass_days, fail_days}, prob:{pass_2w, fail_2w, pass_3w, pass_4w, pass_6w, open_60}, press:{...}}
//   intraday_heat.json {cells:[{dow, hour, n, avg_r, net}], periods:{...}}
// Both pages render a friendly empty state while the research agents have not produced the file yet (404).
import { $, $$, esc, fmt$, fmtS$, fmtN, fmtR, cls } from '../util.js';
import { icon } from './icons.js';
import { mount3d } from './fx3d.js';
import { results$ } from './datahub.js';

const START = 50000, TARGET = 53000, MAXLOSS = 2000;
const pct = (v) => v == null ? '—' : fmtN(v, v < 10 ? 1 : 0) + '%';

async function labFile(name) {
  const r = await fetch('/api/next/lab/' + name);
  if (r.status === 404) return null;
  if (!r.ok) throw new Error('HTTP ' + r.status);
  const d = await r.json();
  return d?.error ? null : d;
}
function emptyCard(title, file, why) {
  return `<div class="card nx-glass nx-empty-hub"><span class="nx-tile-i">${icon('variants')}</span><h3>${esc(title)}</h3>
    <p class="muted">${esc(why)} It reads <span class="mono">research/lab/${esc(file)}.json</span>, which the research agents are producing; this page fills itself as soon as the file exists.</p>
    <div class="nx-chips"><button class="btn ghost" data-goto="results">${icon('results')}Results</button><button class="btn ghost" data-goto="lab">${icon('variants')}Experiments</button></div></div>`;
}
// probabilities may come as fractions (0..1) or percents
function asPct(o) {
  if (!o) return null;
  const vals = Object.values(o).filter(v => typeof v === 'number');
  const k = vals.length && Math.max(...vals) <= 1 ? 100 : 1;
  return Object.fromEntries(Object.entries(o).map(([a, v]) => [a, typeof v === 'number' ? v * k : v]));
}
const median = (a) => { if (!a?.length) return null; const s = [...a].sort((x, y) => x - y); const m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; };

// ------------------------------------------------------------------ Monte Carlo fan (2D fallback)
function fanSvg(paths, h = 300) {
  const W = 900, H = h, L = 58, R = 14, T = 12, B = 26;
  const pick = paths.length > 60 ? paths.filter((_, i) => i % Math.ceil(paths.length / 60) === 0).slice(0, 60) : paths;
  const n = Math.max(2, ...pick.map(p => p.days.length));
  let lo = Math.min(START - MAXLOSS - 400, ...pick.flatMap(p => p.days)), hi = Math.max(TARGET + 400, ...pick.flatMap(p => p.days));
  const X = (i) => L + i / (n - 1) * (W - L - R), Y = (v) => T + (1 - (v - lo) / (hi - lo)) * (H - T - B);
  const col = (r) => r === 'PASS' || r === 'pass' ? 'var(--good)' : r === 'FAIL' || r === 'fail' ? 'var(--bad)' : 'var(--muted)';
  const line = (d) => d.map((v, i) => `${i ? 'L' : 'M'}${X(i).toFixed(1)} ${Y(v).toFixed(1)}`).join('');
  const tk = [START - MAXLOSS, START, TARGET].concat(hi > TARGET + 2500 ? [TARGET + 2500] : []);
  const xs = [0, 10, 20, 30, 40, 60].filter(d => d < n);
  return `<div class="nx-viz" style="height:${H}px"><svg viewBox="0 0 ${W} ${H}" width="100%" height="${H}" preserveAspectRatio="none">
    <rect x="${L}" y="${Y(hi)}" width="${W - L - R}" height="${Math.max(0, Y(TARGET) - Y(hi))}" fill="var(--good)" opacity=".06"/>
    <rect x="${L}" y="${Y(START - MAXLOSS)}" width="${W - L - R}" height="${Math.max(0, Y(lo) - Y(START - MAXLOSS))}" fill="var(--bad)" opacity=".07"/>
    ${tk.map(v => `<line x1="${L}" x2="${W - R}" y1="${Y(v)}" y2="${Y(v)}" class="${v === START ? 'nx-zero' : 'nx-grid'}"/><text x="${L - 8}" y="${Y(v) + 4}" text-anchor="end" class="nx-axis">$${(v / 1000).toFixed(0)}k</text>`).join('')}
    <line x1="${L}" x2="${W - R}" y1="${Y(TARGET)}" y2="${Y(TARGET)}" stroke="var(--good)" stroke-dasharray="5 4" vector-effect="non-scaling-stroke"/>
    <line x1="${L}" x2="${W - R}" y1="${Y(START - MAXLOSS)}" y2="${Y(START - MAXLOSS)}" stroke="var(--bad)" stroke-dasharray="5 4" vector-effect="non-scaling-stroke"/>
    ${xs.map(d => `<line x1="${X(d)}" x2="${X(d)}" y1="${T}" y2="${H - B}" class="nx-grid"/><text x="${X(d)}" y="${H - 7}" text-anchor="middle" class="nx-axis">${d === 0 ? 'start' : d === 10 ? '2 wk' : d === 20 ? '1 mo' : d + 'd'}</text>`).join('')}
    ${pick.map(p => `<path d="${line(p.days)}" fill="none" stroke="${col(p.result)}" stroke-width="1.2" opacity=".5" vector-effect="non-scaling-stroke"/>`).join('')}
  </svg></div>
  <div class="nx-legend"><span><i style="background:var(--good)"></i>passed · reached +$3,000</span><span><i style="background:var(--bad)"></i>failed · hit the $2,000 trailing max loss</span><span><i style="background:var(--muted)"></i>still open</span></div>`;
}
function histSvg(hist, h = 160) {
  const P = hist?.pass_days || [], F = hist?.fail_days || [];
  if (!P.length && !F.length) return '<div class="empty">No decision-day histogram in the file.</div>';
  const maxD = Math.max(10, ...P, ...F), bins = Math.ceil(maxD / 5);
  const cnt = (a) => { const o = new Array(bins).fill(0); a.forEach(d => { o[Math.min(bins - 1, Math.floor(Math.max(0, d - 1) / 5))]++; }); return o; };
  const cp = cnt(P), cf = cnt(F), tot = P.length + F.length || 1, mx = Math.max(1, ...cp, ...cf) / tot;
  const W = 900, H = h, L = 40, R = 10, T = 10, B = 24, bw = (W - L - R) / bins;
  const Y = (v) => T + (1 - v / mx) * (H - T - B);
  return `<div class="nx-viz" style="height:${H}px"><svg viewBox="0 0 ${W} ${H}" width="100%" height="${H}" preserveAspectRatio="none">
    ${cp.map((v, i) => `<rect x="${(L + i * bw + 2).toFixed(1)}" y="${Y(v / tot).toFixed(1)}" width="${(bw / 2 - 3).toFixed(1)}" height="${(H - B - Y(v / tot)).toFixed(1)}" rx="2" fill="var(--good)" opacity=".85"/>
      <rect x="${(L + i * bw + bw / 2 + 1).toFixed(1)}" y="${Y(cf[i] / tot).toFixed(1)}" width="${(bw / 2 - 3).toFixed(1)}" height="${(H - B - Y(cf[i] / tot)).toFixed(1)}" rx="2" fill="var(--bad)" opacity=".85"/>
      <text x="${L + i * bw + bw / 2}" y="${H - 7}" text-anchor="middle" class="nx-axis">wk ${i + 1}</text>`).join('')}
    <line x1="${L}" x2="${W - R}" y1="${H - B}" y2="${H - B}" class="nx-zero"/>
    <line x1="${L + 2 * bw}" x2="${L + 2 * bw}" y1="${T}" y2="${H - B}" stroke="var(--warn)" stroke-dasharray="4 4" vector-effect="non-scaling-stroke"/>
  </svg></div><div class="nx-legend"><span><i style="background:var(--good)"></i>passes by week decided</span><span><i style="background:var(--bad)"></i>fails</span><span><i style="background:var(--warn)"></i>the 2-week line</span></div>`;
}

async function showEvals() {
  const el = $('#page-evals'); if (!el) return;
  el.innerHTML = '<div class="nx-skel"><i></i><i></i></div>';
  let mc = null, res = null;
  try { mc = await labFile('montecarlo'); } catch (e) { el.innerHTML = `<div class="banner warn">Could not load the Monte Carlo file: ${esc(e.message)}</div>`; return; }
  try { res = await results$(); } catch { res = null; }
  const P = res?.periods || {};
  const hist = (k) => { const p = P[k]; if (!p) return ''; const w = p.eval?.within_2_weeks || {}, m = p.eval?.within_1_month || {};
    return `<tr><td><b>${esc(k === 'All years' ? '5 years' : k)}</b></td><td>${p.trades}</td><td><span class="up">${pct(w.pass_pct)}</span> / <span class="dn">${pct(w.fail_pct)}</span></td><td><span class="up">${pct(m.pass_pct)}</span> / <span class="dn">${pct(m.fail_pct)}</span></td><td>${p.eval?.back_to_back ? `${p.eval.back_to_back.passed} / ${p.eval.back_to_back.failed}` : '—'}</td></tr>`; };
  const histCard = res ? `<div class="card nx-glass"><div class="card-h"><h3>What really happened · rolling starts in the replay</h3><span class="muted small">a new MFFU 50K eval started every trading day · pass / fail</span></div>
    <div class="table-wrap"><table class="tbl"><tr><th>Period</th><th>Trades</th><th>Within 2 weeks</th><th>Within 1 month</th><th>Back-to-back</th></tr>${hist('2026 YTD')}${hist('All years')}</table></div></div>` : '';
  const litM = mc?.strategy_model === 'lit';
  const hero = `<div class="nx-hero"><div><div class="nx-eyebrow">${icon('evals')} Lab · evals${litM ? ' · LIT 2026' : ''}${mc?.built ? ' · built ' + esc(mc.built) : ''}</div><h2>How fast does an eval get decided?</h2>
    <p class="muted">Owner's rule: an eval should be <b>decided within 2 weeks</b> and never take over 3 weeks to pass. MFFU Builder 50K: +$3,000 target, $2,000 trailing max loss. Each path below is one simulated eval drawn from ${litM ? 'LIT’s 2026 sessions (the judged year; settings picked on Jan–Jun, checked on Jul–Oct)' : 'the strategy\'s own trading days'}.</p></div>
    ${litM ? `<button class="btn ghost" data-goto="archive">${icon('archive')}Previous strategy’s odds</button>` : `<button class="btn ghost" data-goto="prop">${icon('prop')}Prop firms</button>`}</div>`;
  if (!mc) { el.innerHTML = hero + emptyCard('No Monte Carlo yet', 'montecarlo', 'The eval simulation has not been published.') + histCard; return; }

  const lock = asPct(mc.prob) || {}, pressRaw = mc.press?.prob || (mc.press && typeof mc.press.pass_2w === 'number' ? mc.press : null), press = asPct(pressRaw);
  const pressLabel = mc.press?.label || mc.press?.name || (litM ? 'Fast-eval sizing (off)' : 'Fast-eval press');
  const pressNote = mc.press_rule || mc.press?.note || 'full $800 on any stop while the eval is less than $1,000 down';
  // rows: [key, label, colour class, kind] kind: pct (higher better) · pctBad (lower better) · n (sessions, lower better) · $ (drawdown, smaller better)
  const rows = [['pass_2w', 'Passed within 2 weeks', 'up', 'pct'], ['fail_2w', 'Failed within 2 weeks', 'dn', 'pctBad'], ['dec_2w', 'Decided within 2 weeks', '', 'pct'],
    ['pass_3w', 'Passed within 3 weeks', 'up', 'pct'], ['fail_3w', 'Failed within 3 weeks', 'dn', 'pctBad'], ['pass_4w', 'Passed within 1 month', 'up', 'pct'], ['fail_4w', 'Failed within 1 month', 'dn', 'pctBad'],
    ['pass_6w', 'Passed within 6 weeks', 'up', 'pct'], ['fail_6w', 'Failed within 6 weeks', 'dn', 'pctBad'], ['pass_60', 'Passed within 60 sessions', 'up', 'pct'], ['fail_60', 'Failed within 60 sessions', 'dn', 'pctBad'], ['open_60', 'Still open after 60 sessions', '', 'pctBad'],
    ['pass_days_median', 'Median sessions to pass', '', 'n'], ['pass_days_p90', 'Slowest 10% of passes take', '', 'n'], ['dd_median', 'Median drawdown on the way', '', '$'], ['dd_p90', 'Worst 10% drawdown', '', '$'], ['dd_worst', 'Worst drawdown seen', '', '$']];
  const dec = (o) => o && o.pass_2w != null && o.fail_2w != null ? o.pass_2w + o.fail_2w : null;
  const get = (o, k) => k === 'dec_2w' ? dec(o) : o?.[k];
  const fmtK = (v, kind) => v == null ? '—' : kind === 'n' ? fmtN(v, 0) + ' sessions' : kind === '$' ? fmt$(v) : pct(v);
  const paths = mc.paths || [], results = paths.map(p => String(p.result || '').toUpperCase());
  const nPass = results.filter(r => r === 'PASS').length, nFail = results.filter(r => r === 'FAIL').length;
  const medPass = lock.pass_days_median ?? median(mc.hist?.pass_days), medFail = median(mc.hist?.fail_days);
  const slow = (mc.hist?.pass_days || []).length ? (mc.hist.pass_days.filter(d => d > 15).length / mc.hist.pass_days.length * 100) : null;
  const exact = Array.isArray(mc.exact) ? mc.exact : [];
  const ch = mc.chain && typeof mc.chain === 'object' ? Object.entries(mc.chain).filter(([, v]) => v && typeof v === 'object') : [];
  const exactCard = exact.length ? `<div class="card nx-glass"><div class="card-h"><h3>What really happened · rolling starts in the replay</h3><span class="muted small">a new MFFU 50K eval started on every trading day · pass / fail</span></div>
    <div class="table-wrap"><table class="tbl"><tr><th>Period</th><th>Starts</th><th>Within 2 weeks</th><th>Within 3 weeks</th><th>Within 1 month</th><th>Within 60 sessions</th><th>Median sessions to pass</th></tr>
    ${exact.map(x => `<tr><td><b>${esc(x.pool === 'all' ? 'All years' : x.pool)}${x.mode && x.mode !== 'live' ? ' · ' + esc(x.mode) : ''}</b></td><td>${x.n_starts ?? '—'}</td><td><span class="up">${pct(x.pass_2w)}</span> / <span class="dn">${pct(x.fail_2w)}</span></td><td><span class="up">${pct(x.pass_3w)}</span> / <span class="dn">${pct(x.fail_3w)}</span></td><td><span class="up">${pct(x.pass_4w)}</span> / <span class="dn">${pct(x.fail_4w)}</span></td><td><span class="up">${pct(x.pass_60)}</span> / <span class="dn">${pct(x.fail_60)}</span> · open ${pct(x.open_60)}</td><td class="mono">${x.pass_med ?? '—'}</td></tr>`).join('')}</table></div></div>` : histCard;
  const chainCard = ch.length ? `<div class="card nx-glass"><div class="card-h"><h3>To a funded account · back-to-back evals</h3><span class="muted small">a new eval the day after each pass or fail</span></div>
    <div class="table-wrap"><table class="tbl"><tr><th>Case</th><th>Evals per pass</th><th>Weeks to funded (median)</th><th>Funded in 3 mo</th><th>6 mo</th><th>12 mo</th><th>Months of fees</th></tr>
    ${ch.map(([k, v]) => `<tr><td><b>${esc(k)}</b></td><td class="mono">${v.evals_per_pass_mean != null ? fmtN(v.evals_per_pass_mean, 2) : '—'}</td><td class="mono">${v.weeks_to_funded_median != null ? fmtN(v.weeks_to_funded_median, 1) : '—'}</td><td>${pct(v.funded_3m)}</td><td>${pct(v.funded_6m)}</td><td>${pct(v.funded_12m)}</td><td class="mono">${v.months_fees_mean != null ? fmtN(v.months_fees_mean, 1) : '—'}</td></tr>`).join('')}</table></div></div>` : '';
  el.innerHTML = hero + `
    <div class="nx-stats">
      <div class="nx-stat"><span>Decided in 2 weeks</span><b class="${(dec(lock) || 0) >= 50 ? 'up' : ''}">${pct(dec(lock))}</b><em>pass ${pct(lock.pass_2w)} · fail ${pct(lock.fail_2w)}</em></div>
      <div class="nx-stat"><span>Passed in 1 month</span><b class="up">${pct(lock.pass_4w)}</b><em>${pct(lock.pass_3w)} within 3 weeks · ${pct(lock.pass_60)} in 60 sessions</em></div>
      <div class="nx-stat"><span>Median sessions to pass</span><b>${medPass != null ? fmtN(medPass, 0) : '—'}</b><em>${slow != null ? pct(slow) + ' of passes slower than 3 weeks' : lock.pass_days_p90 != null ? 'slowest 10% take ' + fmtN(lock.pass_days_p90, 0) + '+' : ''}</em></div>
      <div class="nx-stat"><span>Simulated evals</span><b>${paths.length || '—'}</b><em>${nPass} passed · ${nFail} failed${medFail != null ? ' · fails take ~' + fmtN(medFail, 0) + ' sessions' : ''}</em></div>
    </div>
    ${mc.plan || mc.method ? `<p class="muted small nx-method">${esc(mc.plan || '')}${mc.plan && mc.method ? ' · ' : ''}${esc(mc.method || '')}${mc.paths_pool ? ' · paths shown: ' + esc(mc.paths_pool) : ''}</p>` : ''}
    <div class="card nx-glass fx-card" data-fx-card hidden><div class="card-h"><h3>Eval paths in 3D</h3><span class="muted small">every simulated account · green reaches the target, red hits the max loss · drag to turn</span></div><div class="fx3d montecarlo" id="evMc"></div></div>
    <div class="card nx-glass"><div class="card-h"><h3>Probability table · lock vs ${esc(pressLabel)}</h3><span class="muted small">${press ? esc(pressNote) : 'press column appears when the file has it'}</span></div>
      <div class="table-wrap"><table class="tbl nx-prob"><tr><th>Outcome</th><th>Locked strategy</th>${press ? `<th>${esc(pressLabel)}</th><th>Difference</th>` : ''}</tr>
      ${rows.filter(([k]) => get(lock, k) != null || get(press, k) != null).map(([k, l, c, kind]) => { const a = get(lock, k), b = get(press, k); const d = a != null && b != null ? b - a : null; const good = kind === 'pct' ? d > 0 : d < 0;
        const dtxt = d == null ? '—' : kind === '$' ? fmtS$(d) : (d > 0 ? '+' : '') + fmtN(d, kind === 'n' ? 0 : 1) + (kind === 'n' ? '' : ' pts');
        return `<tr class="${k === 'dec_2w' ? 'nx-prob-key' : ''}"><td>${l}</td><td class="mono ${c}"><b>${fmtK(a, kind)}</b></td>${press ? `<td class="mono ${c}">${fmtK(b, kind)}</td><td class="mono ${d == null || Math.abs(d) < 1e-9 ? 'muted' : good ? 'up' : 'dn'}">${dtxt}</td>` : ''}</tr>`; }).join('')}</table></div>
      ${press ? `<p class="muted small">Green difference = better for the owner's rule (decided fast, fewer fails, smaller drawdown). The press passes faster but fails more; it is built in and off until the owner turns it on.</p>` : ''}</div>
    <div class="card nx-glass"><div class="card-h"><h3>Fan of ${Math.min(60, paths.length)} paths</h3><span class="muted small">account balance per session · start $50,000 · target $53,000 · max loss $48,000</span></div>${paths.length ? fanSvg(paths) : '<div class="empty">No paths in the file.</div>'}</div>
    <div class="card nx-glass"><div class="card-h"><h3>When evals get decided</h3><span class="muted small">share of all simulated evals, by week</span></div>${histSvg(mc.hist)}</div>
    ${exactCard}${chainCard}
    ${mc.writeup ? `<div class="note">Write-up: <span class="mono">${esc(mc.writeup)}</span> (Data → Write-ups). ${esc(mc.strategy || '')}</div>` : ''}`;
  mount3d('lab-montecarlo', $('#evMc'), 'montecarlo', { paths, start: START, target: TARGET, maxLoss: MAXLOSS, prob: lock });
}

// ------------------------------------------------------------------ Intraday heat (weekday × hour)
const DN = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'];
const ist = { per: 'all' };
// dow may be a name ("Mon"), python weekday (0 = Mon) or 1-based / JS getDay (1 = Mon): numbers above 4 mean 1-based
function normCells(cells) {
  const nums = (cells || []).map(c => c.dow).filter(d => typeof d === 'number');
  const oneBased = nums.length && Math.max(...nums) > 4;
  const out = [];
  for (const c of cells || []) {
    let d = typeof c.dow === 'number' ? (oneBased ? c.dow - 1 : c.dow) : DN.findIndex(n => String(c.dow).toLowerCase().startsWith(n.toLowerCase()));
    if (d == null || d < 0 || d > 4) continue;
    out.push({ ...c, d, h: +c.hour });
  }
  return out;
}
function heatGrid(cells, lit = false) {
  const C = normCells(cells);
  if (!C.length) return '<div class="empty">No cells.</div>';
  const hours = [...new Set(C.map(c => c.h))].sort((a, b) => a - b);
  const maxN = Math.max(1, ...C.map(c => c.n || 0)), maxA = Math.max(0.3, ...C.map(c => Math.abs(c.avg_r || 0)));
  const at = (d, h) => C.find(c => c.d === d && c.h === h);
  const kz = (h) => lit ? h >= 2 && h < 16 : (h >= 9 && h < 12) || (h >= 13 && h < 16);     // LIT enters 02:00-15:30
  const cell = (c, h) => {
    if (!c || !c.n) return `<div class="nx-hc empty ${kz(h) ? 'kz' : ''}"></div>`;
    const a = c.avg_r || 0, k = Math.min(1, Math.abs(a) / maxA), al = 0.18 + 0.72 * k * (0.5 + 0.5 * Math.min(1, c.n / maxN));
    return `<div class="nx-hc ${a >= 0 ? 'pos' : 'neg'} ${kz(h) ? 'kz' : ''}" style="--a:${al.toFixed(2)}" title="${DN[c.d]} ${String(h).padStart(2, '0')}:00 ET · ${c.n} trades · avg ${fmtR(a)} · ${fmtS$(c.net)}"><b>${fmtR(a)}</b><span>${c.n} · ${fmtS$(c.net)}</span></div>`;
  };
  const dayTot = DN.map((_, d) => C.filter(c => c.d === d).reduce((s, c) => ({ n: s.n + (c.n || 0), net: s.net + (c.net || 0) }), { n: 0, net: 0 }));
  const hourTot = hours.map(h => C.filter(c => c.h === h).reduce((s, c) => ({ n: s.n + (c.n || 0), net: s.net + (c.net || 0) }), { n: 0, net: 0 }));
  return `<div class="nx-heat" style="--cols:${DN.length}">
    <div class="nx-hh"></div>${DN.map((n, d) => `<div class="nx-hh"><b>${n}</b><span class="${cls(dayTot[d].net)}">${fmtS$(dayTot[d].net)}</span><i>${dayTot[d].n}</i></div>`).join('')}
    ${hours.map((h, i) => `<div class="nx-hr ${kz(h) ? 'kz' : ''}"><b>${String(h).padStart(2, '0')}:00</b><span class="${cls(hourTot[i].net)}">${fmtS$(hourTot[i].net)}</span><i>${hourTot[i].n}</i></div>${DN.map((_, d) => cell(at(d, h), h)).join('')}`).join('')}
  </div>
  <div class="nx-legend"><span><i style="background:var(--good)"></i>positive avg R</span><span><i style="background:var(--bad)"></i>negative avg R</span><span>stronger colour = bigger edge and more trades</span><span><i style="background:var(--gold)"></i>${lit ? 'LIT entry window' : 'killzone hours'}</span></div>`;
}
async function showIntraday() {
  const el = $('#page-intraday'); if (!el) return;
  el.innerHTML = '<div class="nx-skel"><i></i><i></i></div>';
  let d = null;
  try { d = await labFile('intraday_heat'); } catch (e) { el.innerHTML = `<div class="banner warn">Could not load the intraday file: ${esc(e.message)}</div>`; return; }
  const litH = d?.strategy_model === 'lit';
  const hero = `<div class="nx-hero"><div><div class="nx-eyebrow">${icon('heat')} Lab · intraday${litH ? ' · LIT' : ''}${d?.built ? ' · built ' + esc(d.built) : ''}</div><h2>Which hours and weekdays pay</h2>
    <p class="muted">${litH ? 'Every LIT replay trade placed by weekday and entry hour (ET), 01:00 to 15:00. Green cells made money per trade, red lost. LIT enters 02:00–15:30 (London and New York); most 2026 trades enter before 08:00. 2026 is the judged year; H1 picked, H2 checked, 2021-25 a reference.'
      : 'Every replay trade placed by weekday and entry hour (ET). Green cells made money per trade, red lost; the killzones 09:30–11:30 and 13:30–15:30 are where the bot is allowed to enter. Read it as context: hour filters were tested and none held in both periods.'}</p></div>
    <button class="btn ghost" data-goto="trades">${icon('trades')}Trades</button></div>`;
  if (!d) { el.innerHTML = hero + emptyCard('No intraday heat map yet', 'intraday_heat', 'The weekday × hour study has not been published.'); return; }
  const per = d.periods && typeof d.periods === 'object' ? Object.entries(d.periods).filter(([, v]) => Array.isArray(v) || Array.isArray(v?.cells)) : [];
  const cellsOf = (k) => k === 'all' ? d.cells || [] : (Array.isArray(d.periods[k]) ? d.periods[k] : d.periods[k].cells);
  if (ist.per !== 'all' && !per.find(([k]) => k === ist.per)) ist.per = 'all';
  const C = cellsOf(ist.per), N = C.reduce((s, c) => s + (c.n || 0), 0), net = C.reduce((s, c) => s + (c.net || 0), 0);
  const best = [...normCells(C)].filter(c => c.n >= 5).sort((a, b) => (b.avg_r || 0) - (a.avg_r || 0));
  el.innerHTML = hero + `
    ${per.length ? `<div class="nx-toolbar"><div class="seg" id="ihPer">${[['all', d.cells_label || 'All years'], ...per.map(([k]) => [k, k])].map(([k, l]) => `<button data-v="${esc(k)}" class="${ist.per === k ? 'on' : ''}">${esc(l)}</button>`).join('')}</div></div>` : ''}
    <div class="nx-stats">
      <div class="nx-stat"><span>Trades</span><b>${N}</b><em>${esc(ist.per === 'all' ? (d.cells_label || 'all years') : ist.per)}</em></div>
      <div class="nx-stat"><span>Net</span><b class="${cls(net)}">${fmtS$(net)}</b><em>all cells</em></div>
      <div class="nx-stat"><span>Best cell (5+ trades)</span><b class="up">${best[0] ? `${DN[best[0].d]} ${String(best[0].h).padStart(2, '0')}:00` : '—'}</b><em>${best[0] ? fmtR(best[0].avg_r) + ' avg · ' + best[0].n + ' trades' : ''}</em></div>
      <div class="nx-stat"><span>Worst cell (5+ trades)</span><b class="dn">${best.length ? `${DN[best.at(-1).d]} ${String(best.at(-1).h).padStart(2, '0')}:00` : '—'}</b><em>${best.length ? fmtR(best.at(-1).avg_r) + ' avg · ' + best.at(-1).n + ' trades' : ''}</em></div>
    </div>
    <div class="card nx-glass fx-card" data-fx-card hidden><div class="card-h"><h3>Heat towers</h3><span class="muted small">height = trades, colour = avg R · drag to turn</span></div><div class="fx3d heat" id="ihHeat"></div></div>
    <div class="card nx-glass"><div class="card-h"><h3>Weekday × entry hour</h3><span class="muted small">avg R per trade · trades · net $</span></div>${heatGrid(C, litH)}</div>`;
  $('#ihPer')?.addEventListener('click', (e) => { const b = e.target.closest('button'); if (b) { ist.per = b.dataset.v; showIntraday(); } });
  mount3d('lab-heat', $('#ihHeat'), 'heat', { cells: normCells(C).map(c => ({ dow: c.d, hour: c.h, n: c.n, avg_r: c.avg_r, net: c.net })), label: ist.per === 'all' ? (d.cells_label || 'All years') : ist.per });
}

export const evals = { show: showEvals };
export const intraday = { show: showIntraday };
