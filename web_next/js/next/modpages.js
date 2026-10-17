// Module pages new in the redesign: Strategy Rules (STRATEGY.md + live_model.json), Cold-Streak Filter, Risk & Sizing.
import { $, $$, api, esc, fmt$, fmtS$, fmtN, fmtR, cls } from '../util.js';
import { icon } from './icons.js';
import { lineChart } from './viz.js';
import { results$ } from './datahub.js';

const fail = (el, e) => { el.innerHTML = `<div class="banner warn">Could not load: ${esc(e.message)}</div>`; };

// ------------------------------------------------------------------ tiny markdown (headings, nested lists, bold, code, paragraphs)
function inline(s) {
  return esc(s).replace(/`([^`]+)`/g, '<code>$1</code>').replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>').replace(/(^|\W)\*([^*]+)\*(?=\W|$)/g, '$1<i>$2</i>');
}
export function md(text) {
  const out = [], stack = [];
  let para = [];
  const flushP = () => { if (para.length) { out.push(`<p>${inline(para.join(' '))}</p>`); para = []; } };
  const closeTo = (depth) => { while (stack.length > depth) out.push(`</li></${stack.pop()}>`); };
  for (const raw of text.split('\n')) {
    const line = raw.replace(/\s+$/, '');
    const h = line.match(/^(#{1,4})\s+(.*)/);
    const li = line.match(/^(\s*)([-*]|\d+\.)\s+(.*)/);
    if (h) { flushP(); closeTo(0); const n = h[1].length; out.push(`<h${n + 1}>${inline(h[2])}</h${n + 1}>`); }
    else if (li) {
      flushP();
      const depth = Math.floor(li[1].length / 2) + 1, tag = /\d/.test(li[2]) ? 'ol' : 'ul';
      if (depth > stack.length) { while (stack.length < depth) { out.push(`<${tag}><li>`); stack.push(tag); } out.push(inline(li[3])); }
      else { closeTo(depth); out.push(`</li><li>${inline(li[3])}`); }
    } else if (!line.trim()) { flushP(); closeTo(0); }
    else if (stack.length && /^\s+/.test(raw)) out.push(' ' + inline(line.trim()));
    else { closeTo(0); para.push(line.trim()); }
  }
  flushP(); closeTo(0);
  return out.join('');
}

async function showRules() {
  const el = $('#page-rules');
  try {
    const d = await api('/api/next/strategy');
    const lm = d.live_model || {}, p = lm.params || {}, ef = lm.equity_filter || {};
    el.innerHTML = `
      <div class="nx-hero"><div><div class="nx-eyebrow">Strategy rules · locked ${esc(lm.chosen || '')}${lm.locked ? ' · ' + icon('check') + ' locked' : ''}</div>
        <h2>${esc((lm.label || 'Liquidity Engine').split(' (')[0])}</h2><p class="muted">${esc(lm.label || '')}</p></div>
        <button class="btn ghost" data-goto="playbook">${icon('playbook')}Playbook</button></div>
      <div class="nx-steps">${[
        ['Sweep', 'A liquidity pool is taken from 08:00 ET', 'sweep'], ['Trigger', 'IFVG / CISD inside 09:30–11:30 or 13:30–15:30', 'trigger'],
        ['Stop', 'Beyond the sweep extreme, 10–60 pts', 'stop'], ['Target', 'Nearest major pool ≥1.5R, bank 5R on the way', 'target'],
        ['Manage', 'BE at 1R · 30-min time stop · giveback exit · 1 trade/day', 'manage']]
        .map(([t, s], i) => `<div class="nx-step"><span class="nx-step-n">${i + 1}</span><b>${t}</b><span>${s}</span></div>`).join('')}</div>
      <div class="grid cols-3">
        <div class="card nx-glass span-2 nx-md">${md(d.markdown || 'STRATEGY.md not found.')}</div>
        <div class="nx-col">
          <div class="card nx-glass"><div class="card-h"><h3>live_model.json</h3><span class="muted small">what the bot and cloud monitor trade</span></div>
            <div class="nx-kv one">${Object.entries(p).map(([k, v]) => `<div><span class="mono">${esc(k)}</span><b class="mono">${esc(JSON.stringify(v))}</b></div>`).join('')}
            ${Object.entries(ef).map(([k, v]) => `<div><span class="mono">equity_filter.${esc(k)}</span><b class="mono">${esc(JSON.stringify(v))}</b></div>`).join('')}</div></div>
          <div class="card nx-glass"><div class="card-h"><h3>Hard rules</h3></div><ul class="nx-list">
            <li>Futures data only (TradingView CME NQ1!)</li><li>Paper only: never arm live trading</li><li>2–4 setups a week, never fewer than 2</li><li>Evals decided within 2 weeks, never over 3 weeks to pass</li>
            <li>Stop beyond the sweep extreme, never fixed</li><li>Wide stop means less risk: size follows the stop</li>
            <li>Judged on 2026 and 2021-25: adopted only if it holds in both</li></ul></div>
        </div>
      </div>`;
  } catch (e) { fail(el, e); }
}

// ------------------------------------------------------------------ COLD-STREAK FILTER
const sizeWord = (m) => (Math.abs(m - 0.5) < 1e-9 ? 'half' : Math.abs(m - 0.25) < 1e-9 ? 'quarter' : `×${fmtN(m, 2)}`);
async function showCold() {
  const el = $('#page-cold');
  try {
    const [c, r] = await Promise.all([api('/api/next/cold'), results$().catch(() => null)]);
    const cfg = c.config || {}, now = c.now || {}, win = c.window || [], et = c.eval_timing || null;
    const lb = cfg.lookback || 15, thr = cfg.min_sum_r ?? 0, coldM = cfg.cold_mode === 'half' ? (cfg.cold_size ?? 0.5) : 0, word = coldM ? sizeWord(coldM) : 'no';
    const hist = c.history || [];
    // rolling sum of the last `lb` finished trades before each trade (the replay's view of the filter)
    const roll = hist.map((t, i) => ({ t, s: hist.slice(Math.max(0, i - lb), i).reduce((a, x) => a + (x.r || 0), 0) }));
    const y26 = roll.filter(x => String(x.t.day).startsWith('2026'));
    const P = r?.periods || {};
    const maxAbs = Math.max(1, ...win.map(x => Math.abs(x.r)));
    const pct = (v) => fmtN((v || 0) * 100, 0) + '%';
    el.innerHTML = `
      <div class="nx-hero"><div><div class="nx-eyebrow">Cold-streak filter · engine/equity_filter.py</div>
        <h2>${word[0].toUpperCase() + word.slice(1)} size when the last ${lb} signals sum ≤ ${fmtN(thr, 1)}R</h2>
        <p class="muted">Every signal is kept (2–4 setups a week). In a cold streak the bot trades it at ${word} size and goes back to full size as soon as the ${lb}-signal record turns positive. Skip mode had the best PF but paused trading for 14 weeks, so it was rejected; the sensitivity study (Lab → write-ups → parameter-robustness) shows the lookback of ${lb} is the one number that matters.</p></div></div>
      <div class="grid cols-3">
        <div class="card nx-glass nx-state ${!now.enabled ? '' : now.on ? 'good' : 'warn'}">
          <div class="nx-eyebrow">Right now · shadow ledger</div>
          <div class="nx-state-v">${icon(now.on ? 'check' : 'cold')}<b>${!now.enabled ? 'FILTER OFF' : now.on ? 'FULL SIZE' : word.toUpperCase() + ' SIZE'}</b></div>
          <div class="nx-gauge"><div class="nx-gauge-bar"><i style="left:50%"></i><b style="left:${Math.max(2, Math.min(98, 50 + (now.sum_r || 0) / Math.max(6, Math.abs(now.sum_r || 0)) * 48))}%"></b></div>
            <div class="nx-gauge-l"><span>cold</span><span>${fmtN(thr, 1)}R</span><span>warm</span></div></div>
          <div class="nx-kv"><div><span>Sum of last ${now.n ?? 0}</span><b class="${cls(now.sum_r)}">${fmtR(now.sum_r)}</b></div><div><span>Size multiplier</span><b>×${fmtN(now.mult ?? 1, 2)}</b></div></div>
          <div class="note">${esc(now.reason || '')}</div>
        </div>
        ${et ? `<div class="card nx-glass nx-state ${et.verdict === 'go' ? 'good' : 'warn'}">
          <div class="nx-eyebrow">Buy or reset the eval now?</div>
          <div class="nx-state-v">${icon(et.verdict === 'go' ? 'check' : 'clock')}<b>${et.verdict === 'go' ? 'GO' : 'WAIT'}</b></div>
          <div class="nx-kv"><div><span>Pass within 2 weeks</span><b class="up">${pct(et.pass_2w)}</b></div><div><span>Fail within 2 weeks</span><b class="dn">${pct(et.fail_2w)}</b></div>
            <div><span>Pass within 1 month</span><b class="up">${pct(et.pass_1m)}</b></div><div><span>Fail within 1 month</span><b class="dn">${pct(et.fail_1m)}</b></div>
            <div><span>Median sessions to pass</span><b>${et.median_pass}</b></div><div><span>Weeks to funded (median)</span><b>${fmtN(et.funded_wk, 1)}</b></div></div>
          <div class="note">${esc(et.reason || '')} · Monte Carlo, Lab → write-ups → monte-carlo-evals.</div>
        </div>` : ''}
        <div class="card nx-glass ${et ? '' : 'span-2'}"><div class="card-h"><h3>The window · last ${win.length} finished signals</h3><span class="muted small">oldest → newest</span></div>
          <div class="nx-rbars">${win.map(x => `<div class="nx-rbar" title="${esc(x.day || '')} ${fmtR(x.r)}"><i class="${x.r >= 0 ? 'pos' : 'neg'}" style="height:${Math.abs(x.r) / maxAbs * 50}%;${x.r >= 0 ? 'bottom:50%' : 'top:50%'}"></i><span>${esc(String(x.day || '').slice(5))}</span></div>`).join('') || '<div class="empty">No signals recorded yet.</div>'}</div>
        </div>
      </div>
      <div class="card nx-glass"><div class="card-h"><h3>Rolling ${lb}-signal sum · 2026 replay</h3><span class="muted small">below the line = ${word} size</span></div><div id="coldRoll"></div></div>
      <div class="grid cols-2">
        ${['2026 YTD', 'All years'].map(k => P[k] ? `<div class="card nx-glass"><div class="card-h"><h3>${k === 'All years' ? '5 years' : k}</h3></div>
          <div class="nx-kv"><div><span>Trades</span><b>${P[k].trades}</b></div><div><span>Reduced-size trades</span><b>${P[k].half_size_trades}</b></div>
          <div><span>Share reduced</span><b>${fmtN(P[k].half_size_trades / P[k].trades * 100, 0)}%</b></div><div><span>Per week</span><b>${fmtN(P[k].per_week, 1)}</b></div>
          <div><span>PF</span><b>${fmtN(P[k].pf)}</b></div><div><span>Net</span><b class="${cls(P[k].net_usd)}">${fmt$(P[k].net_usd)}</b></div><div><span>Max DD</span><b class="dn">${fmt$(P[k].max_dd)}</b></div></div></div>` : '').join('')}
      </div>`;
    lineChart($('#coldRoll'), y26.map(x => ({ x: x.t.day.slice(5), y: x.s, tip: `<b>${x.t.day}</b><span>prior ${lb}: ${fmtR(x.s)}</span><span>${x.t.half ? word + ' size' : 'full size'} · trade ${fmtR(x.t.r)}</span>` })),
      { h: 220, fmt: (v) => (v > 0 ? '+' : '') + v.toFixed(1) + 'R', ref: thr, color: 'var(--accent-2)' });
  } catch (e) { fail(el, e); }
}

// ------------------------------------------------------------------ RISK & SIZING
// Mirrors engine/sizing.py: the engine's micros (full $ risk up to REF pts, then RISK x REF / stop, floored), then ONE
// multiplier (cold size x late size), floored once, at least 1 micro, at most MAXM. No micro at full size = no trade.
const PV = 2, MAXM = 40;
let SZ = { risk: 800, ref: 20, cold: 0.25, late: 0.5 };
function size(stop, cold, late) {
  const budget = SZ.risk * Math.min(1, SZ.ref / stop);
  const base = Math.min(MAXM, Math.floor(budget / (stop * PV)));
  const mult = (cold ? SZ.cold : 1) * (late ? SZ.late : 1);
  const micros = base <= 0 ? 0 : mult >= 1 ? base : Math.min(MAXM, Math.max(1, Math.floor(base * mult)));
  return { budget, base, mult, micros, real: micros * stop * PV };
}
async function showRisk() {
  const el = $('#page-risk');
  let r = null, lm = null;
  try { r = await results$(); } catch { }
  try { lm = (await api('/api/next/strategy')).live_model || null; } catch { }
  if (lm) {
    const p = lm.params || {}, ef = lm.equity_filter || {}, sz = lm.sizing || {};
    SZ = { risk: +p.risk_usd || 800, ref: +p.risk_ref_stop || 20, cold: ef.cold_mode === 'half' ? +(ef.cold_size ?? 0.5) : 0, late: sz.late_mult == null ? 1 : +sz.late_mult };
  }
  const stops = [10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60];
  el.innerHTML = `
    <div class="nx-hero"><div><div class="nx-eyebrow">Risk &amp; sizing · live_model.json · engine/sizing.py</div><h2>Size follows the stop</h2>
      <p class="muted">Full $${SZ.risk} risk up to a ${SZ.ref}-pt stop; wider stops risk $${SZ.risk} × ${SZ.ref} / stop (a wide stop means <b>less</b> money at risk). MNQ micros at $${PV}/pt, max ${MAXM}.
      Then one multiplier: ${sizeWord(SZ.cold)} size in a cold streak, ${sizeWord(SZ.late)} size on a late entry (the 15-minute structure already turned the trade's way), both together ×${fmtN(SZ.cold * SZ.late, 3)}; rounded down once, never below 1 micro. Fewer than 1 micro at full size means no trade.</p></div></div>
    <div class="grid cols-3">
      <div class="card nx-glass span-2 nx-calc">
        <div class="card-h"><h3>Calculator</h3><div class="nx-switches"><label class="nx-switch-row inline"><span>Cold streak (${sizeWord(SZ.cold)})</span><input type="checkbox" class="nx-switch" id="rkCold"></label>
          <label class="nx-switch-row inline"><span>Late entry (${sizeWord(SZ.late)})</span><input type="checkbox" class="nx-switch" id="rkLate"></label></div></div>
        <div class="nx-range-row"><span>Stop</span><input type="range" id="rkStop" min="10" max="60" step="0.25" value="40"><b class="mono" id="rkStopV">40 pts</b></div>
        <div class="nx-calc-out" id="rkOut"></div>
      </div>
      <div class="card nx-glass"><div class="card-h"><h3>MFFU Builder 50K</h3></div>
        <div class="nx-kv one"><div><span>Profit target</span><b>$3,000</b></div><div><span>Max loss (EOD trailing)</span><b>$2,000</b></div>
          <div><span>Locks at</span><b>$50,100</b></div><div><span>Soft daily loss</span><b>$1,000</b></div><div><span>Max size</span><b>4 minis / 40 micros</b></div>
          <div><span>Trades per day</span><b>1</b></div></div></div>
    </div>
    <div class="card nx-glass"><div class="card-h"><h3>Size by stop</h3><span class="muted small">full · cold (${sizeWord(SZ.cold)}) · late (${sizeWord(SZ.late)}) · cold and late</span></div>
      <div class="table-wrap"><table class="tbl"><tr><th>Stop</th><th>Risk budget</th><th>Micros</th><th>$ at risk</th><th>Cold: micros · $</th><th>Late: micros · $</th><th>Both: micros · $</th><th>1R in $</th></tr>
      ${stops.map(s => { const f = size(s, false, false), c = size(s, true, false), l = size(s, false, true), b = size(s, true, true); const cell = (z) => f.micros ? `${z.micros} · ${fmt$(z.real)}` : '<span class="dn">0 · pass</span>';
        return `<tr><td class="mono"><b>${s} pts</b></td><td class="mono">${fmt$(f.budget)}</td><td>${f.micros || '<span class="dn">0 · pass</span>'}</td>
        <td class="mono">${fmt$(f.real)}</td><td class="mono">${cell(c)}</td><td class="mono">${cell(l)}</td><td class="mono">${cell(b)}</td><td class="mono">${fmt$(f.real)}</td></tr>`; }).join('')}</table></div></div>
    ${r ? `<div class="card nx-glass"><div class="card-h"><h3>What the stops really were · 5 years</h3><span class="muted small">median ${fmtN(r.periods['All years'].median_stop_pts, 1)} pts · median ${r.periods['All years'].median_micros} micros · median ${fmt$(r.periods['All years'].median_risk_usd)} risk</span></div>
      <div class="nx-buckets">${(r.stop_buckets || []).map(b => { const mx = Math.max(...r.stop_buckets.map(x => x.trades)); return `<div class="nx-bucket"><span class="mono">${esc(b.stop_pts)} pts</span>
        <div class="nx-bucket-bar"><i style="width:${b.trades / mx * 100}%"></i></div><b>${b.trades}</b><em class="${cls(b.avg_r)}">${fmtR(b.avg_r)}</em><em>${b.median_micros} micros · ${fmt$(b.median_risk_usd)}</em></div>`; }).join('')}</div></div>` : ''}`;
  const upd = () => {
    const s = +$('#rkStop').value, z = size(s, $('#rkCold').checked, $('#rkLate').checked);
    $('#rkStopV').textContent = fmtN(s, 2) + ' pts';
    $('#rkStop').style.setProperty('--fill', ((s - 10) / 50 * 100) + '%');
    $('#rkOut').innerHTML = `<div><span>Risk budget</span><b>${fmt$(z.budget)}</b></div><div><span>Engine micros</span><b class="${z.base ? '' : 'dn'}">${z.base || '0 · pass'}</b></div>
      <div><span>Multiplier</span><b>×${fmtN(z.mult, 3)}</b></div><div><span>Micros placed</span><b class="${z.micros ? '' : 'dn'}">${z.micros || '0 · pass'}</b></div>
      <div><span>$ at risk</span><b>${fmt$(z.real)}</b></div><div><span>1.5R target</span><b>${fmtS$(z.real * 1.5)}</b></div><div><span>5R bank</span><b class="up">${fmtS$(z.real * 5)}</b></div>
      <div><span>Stop in ticks</span><b>${Math.round(s * 4)}</b></div>`;
  };
  $('#rkStop').oninput = upd; $('#rkCold').onchange = upd; $('#rkLate').onchange = upd; upd();
}

export const rules = { show: showRules };
export const cold = { show: showCold };
export const risk = { show: showRisk };
