// Data → Rejected setups and Data → Sensitivity: two LIT research views fed by files served as /api/next/lab/<name>
//   rejections.json   tools/lit_rejections.py: every 5m CISD candidate with the first LIT rule it failed (spans last N, 2026, H1, H2, 2021-25)
//   sensitivity.json  tools/lit_sensitivity.py: heat-map grids of the live config's key knobs (depth x disp, stop range, t_check, be_off)
import { $, esc, fmtS$, fmtN, cls } from '../util.js';
import { icon } from './icons.js';

async function labFile(name) {
  const r = await fetch('/api/next/lab/' + name);
  if (r.status === 404) return null;
  if (!r.ok) throw new Error('HTTP ' + r.status);
  const d = await r.json();
  return d?.error ? null : d;
}
const hero = (eyebrow, title, desc, built) => `<div class="nx-hero"><div><div class="nx-eyebrow">${eyebrow}${built ? ' · built ' + esc(built) : ''}</div><h2>${title}</h2><p class="muted">${desc}</p></div></div>`;
const empty = (file, cmd) => `<div class="card nx-glass nx-empty-hub"><span class="nx-tile-i">${icon('variants')}</span><h3>Not built yet</h3>
  <p class="muted">This page reads <span class="mono">research/lab/${esc(file)}.json</span>. Build it with <span class="mono">${esc(cmd)}</span>.</p></div>`;
const segBar = (id, items, cur) => `<div class="seg" id="${id}">${items.map(([v, l]) => `<button type="button" data-v="${esc(v)}" class="${v === cur ? 'on' : ''}">${esc(l)}</button>`).join('')}</div>`;
const onSeg = (id, fn) => { const s = $('#' + id); if (s) s.onclick = (e) => { const b = e.target.closest('button[data-v]'); if (b) fn(b.dataset.v); }; };

// ------------------------------------------------------------------ rejected setups
let RJ = null, rjSpan = 'last';
async function showSetups() {
  const el = $('#page-setups'); if (!el) return;
  if (!RJ) { el.innerHTML = '<div class="nx-skel"><i></i><i></i></div>'; try { RJ = await labFile('rejections'); } catch (e) { el.innerHTML = `<div class="banner warn">${esc(e.message)}</div>`; return; } }
  const H = hero(`${icon('variants')} Lab · LIT setups`, 'Why setups were rejected',
    'Every 5-minute CISD the LIT engine saw, with the first rule it failed: the same verdict the day brief writes in its log. A setup that passes every rule is traded, blocked by the 1-trade-a-day rule, or never filled (no tap of the limit in 30 minutes, no 1-minute CISD, or the 1.5R check at the fill).', RJ?.built);
  if (!RJ) { el.innerHTML = H + empty('rejections', 'python -X utf8 tools/lit_rejections.py'); return; }
  const spans = [['last', `Last ${RJ.last_n || 20} sessions`], ['H1', '2026 H1'], ['H2', '2026 H2'], ['2026', '2026'], ['2021-25', '2021-25 ref']];
  const S = RJ.spans?.[rjSpan] || RJ.spans?.last;
  const rows = (S.rules || []).filter((r) => r.n || r.rule === 'traded');
  const mx = Math.max(1, ...rows.map((r) => r.n || 0));
  const bar = (r) => `<div style="height:8px;border-radius:4px;background:${r.rule === 'traded' ? 'var(--good)' : r.rule === 'no_fill' || r.rule === 'day' ? 'var(--gold)' : 'var(--accent)'};width:${Math.round(100 * (r.n || 0) / mx)}%"></div>`;
  const top = rows.filter((r) => r.rule !== 'traded').sort((a, b) => b.n - a.n)[0];
  el.innerHTML = H + `<div class="nx-toolbar">${segBar('rjSpan', spans, rjSpan)}</div>
    <div class="nx-stats">
      <div class="nx-stat"><span>Setups</span><b>${S.setups}</b><em>${S.sessions} sessions · ${fmtN(S.per_session, 1)} a session</em></div>
      <div class="nx-stat"><span>Traded</span><b class="up">${S.traded}</b><em>${S.setups ? fmtN(100 * S.traded / S.setups, 1) : '—'}% of setups</em></div>
      <div class="nx-stat"><span>Rejected</span><b>${S.rejected}</b><em>by a rule, the day rule or no fill</em></div>
      <div class="nx-stat"><span>Top reason</span><b class="dn">${esc(top?.label || '—')}</b><em>${top ? `${top.n} · ${top.pct}% of the rejected` : ''}</em></div>
    </div>
    <div class="card nx-glass"><div class="card-h"><h3>Reasons · ${esc(spans.find((s) => s[0] === rjSpan)?.[1] || '')}</h3><span class="muted small">${esc(S.from || '')} → ${esc(S.to || '')}</span></div>
      <table class="tbl"><thead><tr><th>Reason</th><th style="text-align:right">Setups</th><th style="text-align:right">% of rejected</th><th style="width:40%"></th></tr></thead>
      <tbody>${rows.map((r) => `<tr><td>${esc(r.label)}</td><td class="mono" style="text-align:right">${r.n}</td><td class="mono" style="text-align:right">${r.pct == null ? '—' : r.pct + '%'}</td><td>${bar(r)}</td></tr>`).join('')}</tbody></table></div>
    <div class="card nx-glass"><div class="card-h"><h3>Latest setups</h3><span class="muted small">newest first</span></div>
      <table class="tbl"><thead><tr><th>Day</th><th>5m CISD</th><th>Side</th><th>Verdict</th><th>Why</th></tr></thead>
      <tbody>${(RJ.recent || []).slice(0, 30).map((r) => `<tr><td class="mono">${esc(r.day)}</td><td class="mono">${new Date(r.t * 1000).toLocaleTimeString('en-US', { timeZone: 'America/New_York', hour: '2-digit', minute: '2-digit', hour12: false })}</td>
        <td class="${r.dir > 0 ? 'up' : 'dn'}">${r.dir > 0 ? 'LONG' : 'SHORT'}</td><td>${esc(r.label)}</td><td class="muted small">${esc(r.text)}</td></tr>`).join('')}</tbody></table>
      <p class="muted small" style="margin-top:8px">${esc(RJ.source || '')}</p></div>`;
  onSeg('rjSpan', (v) => { rjSpan = v; showSetups(); });
}

// ------------------------------------------------------------------ sensitivity heat maps
let SN = null, snSpan = 'H2', snM = 'net';
const METRICS = [['net', 'Net $'], ['pf', 'PF'], ['tpw', 'Trades / wk']];
function grid(g, live) {
  const xs = g.x.values, ys = g.y ? g.y.values : [null];
  const val = (c) => c?.[snSpan]?.[snM];
  const base = live?.[snSpan]?.[snM];
  const vals = g.cells.map(val).filter((v) => v != null);
  const span = Math.max(1e-9, ...vals.map((v) => Math.abs(v - (base ?? 0))));
  const at = (x, y) => g.cells.find((c) => c.x === x && c.y === y);
  const fmt = (v) => v == null ? '—' : snM === 'net' ? fmtS$(v) : fmtN(v, 2);
  const cell = (c) => {
    if (!c) return '<div class="nx-hc empty"></div>';
    const v = val(c), d = base == null || v == null ? 0 : v - base, a = Math.min(0.85, 0.12 + 0.7 * Math.abs(d) / span);
    return `<div class="nx-hc ${d >= 0 ? 'pos' : 'neg'}" style="--a:${a.toFixed(2)};${c.live ? 'outline:2px solid var(--gold);outline-offset:-2px' : ''}"
      title="H1 ${fmtS$(c.H1.net)} PF ${c.H1.pf} · H2 ${fmtS$(c.H2.net)} PF ${c.H2.pf} · ${c['2026'].tpw}/wk · 2021-25 ${fmtS$(c['2021-25'].net)}">
      <b>${fmt(v)}</b><span>${c.live ? 'LIVE' : (snM === 'net' && base != null ? fmtS$(d) + ' vs live' : '')}</span></div>`;
  };
  const yl = (y) => y == null ? '' : String(y);
  return `<div class="nx-heat" style="--cols:${xs.length}">
    <div class="nx-hh"><b>${esc(g.y ? g.y.key : '')}</b><i>${esc(g.x.key)} →</i></div>${xs.map((x) => `<div class="nx-hh"><b>${esc(String(x))}</b></div>`).join('')}
    ${ys.map((y) => `<div class="nx-hr"><b>${esc(yl(y))}</b></div>${xs.map((x) => cell(at(x, y))).join('')}`).join('')}</div>`;
}
async function showSens() {
  const el = $('#page-sensitivity'); if (!el) return;
  if (!SN) { el.innerHTML = '<div class="nx-skel"><i></i><i></i></div>'; try { SN = await labFile('sensitivity'); } catch (e) { el.innerHTML = `<div class="banner warn">${esc(e.message)}</div>`; return; } }
  const H = hero(`${icon('robust')} Lab · LIT sensitivity`, 'How sharp is each knob?',
    'The live LIT settings with one or two knobs moved, replayed by the engine (LIT size rule, costs in). Green = more than live, red = less, the gold frame is the live cell. A plateau (neighbours about as good) is safe; a knob whose neighbours fall off is sharp. Judge on H1 (picked) and H2 (check); 2021-25 is a reference.', SN?.built);
  if (!SN || SN.strategy?.indexOf('LIT') !== 0) { el.innerHTML = H + empty('sensitivity', 'python -X utf8 tools/lit_sensitivity.py'); return; }
  const L = SN.live || {};
  el.innerHTML = H + `<div class="nx-toolbar">${segBar('snSpan', [['H1', '2026 H1'], ['H2', '2026 H2'], ['2026', '2026'], ['2021-25', '2021-25 ref']], snSpan)}${segBar('snM', METRICS, snM)}</div>
    <div class="nx-stats">${['H1', 'H2', '2026', '2021-25'].map((s) => `<div class="nx-stat"><span>Live · ${s}</span><b class="${cls(L[s]?.net)}">${fmtS$(L[s]?.net)}</b><em>PF ${L[s]?.pf ?? '—'} · ${L[s]?.tpw ?? '—'}/wk · $${(L[s]?.per_month ?? 0).toLocaleString('en-US')}/mo</em></div>`).join('')}</div>
    ${(SN.grids || []).map((g) => { const nb = g.neighbours || {}; return `<div class="card nx-glass"><div class="card-h"><h3>${esc(g.title)}</h3>
      <span class="muted small">${nb.n ? `${nb.profitable_both}/${nb.n} neighbours profitable in both halves · ${nb.beat_live_both} beat live in both · H2 ${fmtS$(nb.h2_min)} … ${fmtS$(nb.h2_max)}` : ''}</span></div>${grid(g, L)}</div>`; }).join('')}
    <p class="muted small">${esc(SN.method || '')}</p>`;
  onSeg('snSpan', (v) => { snSpan = v; showSens(); });
  onSeg('snM', (v) => { snM = v; showSens(); });
}

export const setups = { show: showSetups };
export const sensitivity = { show: showSens };
