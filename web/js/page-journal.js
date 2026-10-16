import { $, $$, esc, fmtN, fmtS$, fmtR, cls, etStr, store } from './util.js';
import { S, on } from './state.js';
import { go } from './app.js';
import * as chartPage from './page-chart.js';

const TAGS = ['A+ setup', 'Followed plan', 'Early exit', 'News day', 'Chop / HRL', 'Clean LRL run', 'Would skip', 'Lesson'];
let J = store.get('journal', {});
const key = (t) => `${S.sym}-${t.entry_t}`;

export function init() { on(render); }
export function show() { render(S.res); }

function render(res) {
  if (!res) return;
  const trs = res.trades.slice().reverse();
  $('#journalList').innerHTML = trs.map(t => {
    const j = J[key(t)] || {};
    return `<div class="journal-item" data-k="${key(t)}">
      <div class="row gap" style="justify-content:space-between">
        <div class="row gap"><span class="dir ${t.dir === 1 ? 'L' : 'S'}">${t.dir === 1 ? 'LONG' : 'SHORT'}</span><b class="mono">${t.day} ${etStr(t.entry_t)}</b>
          <span class="small muted">${t.trigger} · ${esc(t.pools.map(p => p.split('·').pop()).slice(0, 2).join(', '))} → ${esc(t.target_label)}</span></div>
        <div class="row gap"><b class="mono ${cls(t.pnl)}">${fmtS$(t.pnl)} · ${fmtR(t.pnl_r)}</b>
          <span class="stars">${[1, 2, 3, 4, 5].map(n => `<button data-star="${n}" class="${(j.rating || 0) >= n ? 'on' : ''}">★</button>`).join('')}</span>
          <button class="btn ghost sm" data-open="${S.res.trades.indexOf(t)}">chart</button></div></div>
      <div style="margin-top:6px">${TAGS.map(g => `<button class="tag-chip" data-tag="${esc(g)}" style="border:0;cursor:pointer;${(j.tags || []).includes(g) ? 'background:var(--accent);color:#fff' : ''}">${esc(g)}</button>`).join('')}</div>
      <textarea placeholder="What did the tape say? Why did it work or fail?">${esc(j.note || '')}</textarea></div>`;
  }).join('') || '<div class="empty">No trades yet.</div>';
  const list = $('#journalList');
  list.oninput = (e) => {
    if (e.target.tagName !== 'TEXTAREA') return;
    const k = e.target.closest('[data-k]').dataset.k;
    J[k] = { ...(J[k] || {}), note: e.target.value }; store.set('journal', J);
  };
  list.onclick = (e) => {
    const item = e.target.closest('[data-k]'); if (!item) return;
    const k = item.dataset.k;
    if (e.target.dataset.star) { J[k] = { ...(J[k] || {}), rating: +e.target.dataset.star }; store.set('journal', J); render(S.res); }
    if (e.target.dataset.tag) {
      const tags = new Set(J[k]?.tags || []); const g = e.target.dataset.tag; tags.has(g) ? tags.delete(g) : tags.add(g);
      J[k] = { ...(J[k] || {}), tags: [...tags] }; store.set('journal', J); render(S.res);
    }
    if (e.target.dataset.open) { chartPage.openTrade(+e.target.dataset.open); go('chart'); }
  };
  // insights
  const rows = TAGS.map(g => {
    const ts = res.trades.filter(t => (J[key(t)]?.tags || []).includes(g));
    return { g, n: ts.length, pnl: ts.reduce((a, t) => a + t.pnl, 0) };
  }).filter(r => r.n);
  const rated = res.trades.filter(t => J[key(t)]?.rating);
  const avgRating = rated.length ? rated.reduce((a, t) => a + J[key(t)].rating, 0) / rated.length : null;
  const hi = rated.filter(t => J[key(t)].rating >= 4), lo = rated.filter(t => J[key(t)].rating <= 2);
  $('#journalStats').innerHTML = `<div class="state-grid">
      <div class="st"><div class="k">Journaled</div><div class="v">${Object.keys(J).filter(k => k.startsWith(S.sym)).length} / ${res.trades.length}</div></div>
      <div class="st"><div class="k">Avg rating</div><div class="v">${avgRating ? avgRating.toFixed(1) + ' ★' : '—'}</div></div>
      <div class="st"><div class="k">4-5★ trades P&L</div><div class="v ${cls(hi.reduce((a, t) => a + t.pnl, 0))}">${fmtS$(hi.reduce((a, t) => a + t.pnl, 0))}</div></div>
      <div class="st"><div class="k">1-2★ trades P&L</div><div class="v ${cls(lo.reduce((a, t) => a + t.pnl, 0))}">${fmtS$(lo.reduce((a, t) => a + t.pnl, 0))}</div></div></div>
    <div class="mini-label" style="margin:12px 0 6px">P&L by tag</div>
    ${rows.length ? `<table class="tbl">${rows.map(r => `<tr><td>${esc(r.g)}</td><td class="mono">${r.n}</td><td class="mono ${cls(r.pnl)}" style="text-align:right">${fmtS$(r.pnl)}</td></tr>`).join('')}</table>` : '<div class="muted small">Tag trades to see which conditions pay.</div>'}
    <div class="note">Rate each trade by how cleanly it matched the model, not by its result. Over time this shows whether A+ setups really outperform.</div>`;
}
