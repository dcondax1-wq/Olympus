// Archive: the previous strategy (Liquidity Engine, locked 2026-10-17). LIT replaced it on 2026-10-18; it keeps running as a
// paper shadow and can come back (research/archive/engine-2026-10-17/README.md). Source: /api/next/archive (engine/next_api.py).
import { $, api, esc, fmt$, fmtS$, fmtN, cls } from '../util.js';
import { icon } from './icons.js';
import { ARCHIVE, ARCHIVE_LABEL } from './routes.js';
import { md, openArchiveRuns } from './lab.js';

const pct = (v) => v == null ? '—' : fmtN(v, v < 10 ? 1 : 0) + '%';

async function show() {
  const el = $('#page-archive'); if (!el) return;
  el.innerHTML = '<div class="nx-skel"><i></i><i></i></div>';
  let a;
  try { a = await api('/api/next/archive'); } catch (e) { el.innerHTML = `<div class="banner warn">Could not load the archive: ${esc(e.message)}</div>`; return; }
  const lm = a.live_model || {}, B = a.runs?.baseline?.spans || {}, et = a.cold?.eval_timing || {}, now = a.cold?.now || {};
  const rows = [['Trades a week', (s) => fmtN(s.tpw, 2)], ['Profit factor', (s) => fmtN(s.pf)], ['Net', (s) => `<span class="${cls(s.net)}">${fmtS$(s.net)}</span>`],
    ['$ a month', (s) => fmtS$(s.per_month)], ['Max drawdown', (s) => fmt$(s.dd)], ['Eval pass / fail · 2 weeks', (s) => `${pct(s.p10)} / <span class="dn">${pct(s.f10)}</span>`],
    ['Eval pass / fail · 1 month', (s) => `${pct(s.p20)} / <span class="dn">${pct(s.f20)}</span>`], ['Back-to-back (passed / failed)', (s) => esc(s.b2b || '—')]];
  const cols = [['2026', '2026'], ['2021-25', '2021-25'], ['all', '5 years']];
  const go = String(et.verdict || '').toLowerCase() === 'go';
  el.innerHTML = `
    <div class="nx-hero"><div><div class="nx-eyebrow">Modules · ${esc(ARCHIVE_LABEL)}</div>
      <h2>${esc(String(lm.label || 'Liquidity Engine').split(' (')[0])}</h2>
      <p class="muted">The strategy the bot traded until 2026-10-18 (locked ${esc(lm.chosen || '2026-10-17')}). LIT replaced it; this one keeps running as a paper shadow (cloud monitor, no alerts; the PC bot with <span class="mono">"model": "engine"</span>) and can come back. Nothing here is live.</p></div>
      <button class="btn ghost" type="button" id="arRuns">${icon('variants')}Its ${a.engine_runs || ''} experiments</button></div>
    <div class="banner info"><b>Archived, not deleted.</b> Everything is in <span class="mono">${esc(a.dir || '')}/README.md</span>: the rules in plain words, the numbers, where every file is and the exact steps to switch back.</div>
    <div class="grid cols-2">
      <div class="card nx-glass"><div class="card-h"><h3>Its numbers</h3><span class="muted small">run baseline · exact live-loop replay, costs in</span></div>
        <div class="table-wrap"><table class="tbl"><tr><th></th>${cols.map(([, l]) => `<th>${l}</th>`).join('')}</tr>
          ${rows.map(([l, f]) => `<tr><td>${l}</td>${cols.map(([k]) => `<td class="mono">${B[k] ? f(B[k]) : '—'}</td>`).join('')}</tr>`).join('')}</table></div>
        <p class="muted small">2026 was a good year for it; over 2021-25 the honest range is +$8k to +$17k.</p></div>
      <div class="card nx-glass"><div class="card-h"><h3>Its eval timing · cold-streak filter</h3><span class="nx-badge ${go ? 'good' : 'warn'}">${esc(String(et.verdict || '—').toUpperCase())}</span></div>
        <div class="nx-kv one"><div><span>Filter now</span><b>${!now.enabled ? 'off' : now.on ? 'full size' : 'reduced size (cold streak)'}</b></div><div><span>Last ${now.n ?? 15} signals</span><b class="${cls(now.sum_r)}">${now.sum_r != null ? fmtN(now.sum_r, 2) + 'R' : '—'}</b></div>
          <div><span>Pass / fail in 1 month</span><b>${et.pass_1m != null ? pct(et.pass_1m * 100) + ' / ' + pct(et.fail_1m * 100) : '—'}</b></div></div>
        <p class="muted small">${esc(et.reason || '')} LIT has no cold-streak filter, so its eval timing is always "any session".</p></div>
    </div>
    <div class="nx-eyebrow" style="margin:22px 2px 10px">Its pages</div>
    <div class="nx-tiles compact">${ARCHIVE.map(m => `<button type="button" class="nx-tile" data-goto="${m.id}"><span class="nx-tile-i">${icon(m.icon)}</span>
      <span class="nx-tile-t">${esc(m.label)}</span><span class="nx-tile-d">${esc(m.desc)}</span><span class="nx-tile-go">${icon('right')}</span></button>`).join('')}</div>
    ${a.readme ? `<div class="nx-eyebrow" style="margin:22px 2px 10px">README · how to switch back</div><article class="card nx-glass nx-md">${md(a.readme)}</article>` : ''}`;
  $('#arRuns').onclick = () => openArchiveRuns();
}

export const archive = { show };
