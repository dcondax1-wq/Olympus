// Widget framework: every card on a dashboard page becomes a widget with a drag handle, expand, export (CSV / PNG) and hide.
// Order, size and visibility are saved per page in localStorage (le.dash.layout.<page>, wrapped in try/catch by store()).
import { $, $$, esc, toast } from '../util.js';
import { pref, saveCSV, savePNG } from './kit.js';

const REG = new Map();          // id -> def
const GRIDS = new Map();        // page -> grid element
export const SIZES = [['s', 'S'], ['m', 'M'], ['l', 'L'], ['w', 'W'], ['xl', 'XL']];

// def: { id, page, title, size, sub, mount(body, card), csv() -> {name, rows, cols}, el (adopt an existing card), tall }
export function widget(def) { REG.set(def.id, def); return def; }
export const body = (id) => REG.get(id)?._body || null;
export const meta = (id, html) => { const m = REG.get(id)?._meta; if (m) m.innerHTML = html; };
export const visible = (id) => { const c = REG.get(id)?._card; return !!c && !c.hidden && c.offsetParent !== null; };
export const defsFor = (page) => [...REG.values()].filter(d => d.page === page);

function layout(page) { return { order: [], hidden: [], size: {}, ...pref.get('layout.' + page, {}) }; }
function saveLayout(page, L) { pref.set('layout.' + page, L); }

function toolsHtml(def) {
  return `<div class="w-tools">
    <button class="w-t w-drag" title="Drag to move" aria-label="Drag to move">⠿</button>
    <button class="w-t" data-wa="expand" title="Expand (Esc to close)" aria-label="Expand">⤢</button>
    <button class="w-t" data-wa="export" title="Export ${def.csv ? 'CSV / ' : ''}PNG" aria-label="Export">⇩</button>
    <button class="w-t" data-wa="hide" title="Hide (restore from Layout)" aria-label="Hide">✕</button></div>`;
}

// adopted cards may rebuild their own header (innerHTML): put the tools back whenever they disappear
function ensureTools(card, def) {
  let h = card.querySelector(':scope > .card-h');
  if (!h) { h = document.createElement('div'); h.className = 'card-h w-h-float'; card.prepend(h); }
  if (!h.querySelector('.w-tools')) h.insertAdjacentHTML('beforeend', toolsHtml(def));
}
function makeCard(def) {
  let card = def.el;
  if (card) {
    card.classList.add('w');
    ensureTools(card, def);
    new MutationObserver(() => { if (!card.querySelector(':scope > .card-h > .w-tools')) ensureTools(card, def); }).observe(card, { childList: true });
  } else {
    card = document.createElement('section');
    card.className = 'card w' + (def.cls ? ' ' + def.cls : '');
    card.innerHTML = `<div class="card-h"><h3>${def.title}</h3><div class="w-meta">${def.sub || ''}</div>${toolsHtml(def)}</div><div class="w-body"></div>`;
    def._body = card.querySelector('.w-body');
    def._meta = card.querySelector('.w-meta');
  }
  card.dataset.w = def.id;
  def._card = card;
  return card;
}

// build (or rebuild) one page's grid from the registry and the saved layout
const DEFAULT_ORDER = new Map();
export function buildGrid(page, grid, order) {
  GRIDS.set(page, grid);
  if (order) DEFAULT_ORDER.set(page, order);
  grid.classList.add('wgrid');
  const L = layout(page);
  const defs = defsFor(page);
  const dflt = DEFAULT_ORDER.get(page) || [];
  const rank = (d) => { const i = L.order.indexOf(d.id); if (i >= 0) return i; const j = dflt.indexOf(d.id); return j >= 0 ? 500 + j : 1000 + defs.indexOf(d); };
  defs.sort((a, b) => rank(a) - rank(b));
  for (const d of defs) {
    const card = d._card || makeCard(d);
    card.dataset.size = L.size[d.id] || d.size || 'm';
    card.hidden = L.hidden.includes(d.id);
    grid.appendChild(card);
    if (!d._mounted) { d._mounted = true; try { d.mount?.(d._body || card, card); } catch (e) { console.error('widget mount', d.id, e); } }
  }
  wireGrid(page, grid);
}

function saveOrder(page) {
  const grid = GRIDS.get(page); if (!grid) return;
  const L = layout(page);
  L.order = $$(':scope > .w', grid).map(c => c.dataset.w);
  saveLayout(page, L);
}

// FLIP: animate siblings to their new grid slots after a DOM move
function flip(grid, mutate) {
  const cards = $$(':scope > .w', grid);
  const before = new Map(cards.map(c => [c, c.getBoundingClientRect()]));
  mutate();
  if (document.documentElement.dataset.motion === 'off') return;
  for (const c of cards) {
    if (c.classList.contains('dragging')) continue;
    const a = before.get(c), b = c.getBoundingClientRect();
    const dx = a.left - b.left, dy = a.top - b.top;
    if (!dx && !dy) continue;
    c.animate([{ transform: `translate(${dx}px,${dy}px)` }, { transform: 'none' }], { duration: 220, easing: 'cubic-bezier(.2,.8,.2,1)' });
  }
}

function wireGrid(page, grid) {
  if (grid._wired) return;
  grid._wired = true;
  grid.addEventListener('click', (e) => {
    const b = e.target.closest('[data-wa]'); if (!b) return;
    const card = b.closest('.w'); const def = REG.get(card?.dataset.w); if (!def) return;
    if (b.dataset.wa === 'expand') expand(card);
    else if (b.dataset.wa === 'hide') { setHidden(page, def.id, true); toast(`${stripTags(def.title)} hidden · restore it from ⚙ Layout`); }
    else if (b.dataset.wa === 'export') exportMenu(b, def, card);
  });
  // pointer-driven reorder (works with mouse, pen and touch)
  grid.addEventListener('pointerdown', (e) => {
    const h = e.target.closest('.w-drag'); if (!h) return;
    const card = h.closest('.w'); if (!card || card.classList.contains('expanded')) return;
    e.preventDefault();
    h.setPointerCapture?.(e.pointerId);
    card.classList.add('dragging');
    grid.classList.add('is-dragging');
    let lastMove = 0;
    const move = (ev) => {
      const now = performance.now(); if (now - lastMove < 40) return; lastMove = now;
      card.style.pointerEvents = 'none';
      const under = document.elementFromPoint(ev.clientX, ev.clientY);
      card.style.pointerEvents = '';
      const tgt = under?.closest?.('.wgrid > .w');
      if (!tgt || tgt === card || tgt.parentElement !== grid) return;
      const r = tgt.getBoundingClientRect();
      const after = (ev.clientY > r.top + r.height / 2) || (ev.clientX > r.left + r.width / 2 && ev.clientY > r.top);
      flip(grid, () => grid.insertBefore(card, after ? tgt.nextSibling : tgt));
      // auto-scroll the page while dragging near an edge
      const sc = grid.closest('.page');
      if (sc) { if (ev.clientY < 90) sc.scrollBy(0, -24); else if (ev.clientY > innerHeight - 60) sc.scrollBy(0, 24); }
    };
    const up = () => {
      card.classList.remove('dragging'); grid.classList.remove('is-dragging');
      h.removeEventListener('pointermove', move); h.removeEventListener('pointerup', up); h.removeEventListener('pointercancel', up);
      saveOrder(page);
    };
    h.addEventListener('pointermove', move); h.addEventListener('pointerup', up); h.addEventListener('pointercancel', up);
  });
}
const stripTags = (s) => String(s).replace(/<[^>]+>/g, '');

export function setHidden(page, id, hide) {
  const L = layout(page);
  L.hidden = L.hidden.filter(x => x !== id);
  if (hide) L.hidden.push(id);
  saveLayout(page, L);
  const c = REG.get(id)?._card; if (c) c.hidden = hide;
  document.dispatchEvent(new CustomEvent('le-layout', { detail: { page } }));
}
export function setSize(page, id, size) {
  const L = layout(page); L.size[id] = size; saveLayout(page, L);
  const c = REG.get(id)?._card;
  if (c) { const g = c.parentElement; flip(g, () => { c.dataset.size = size; }); }
}
export function resetLayout(page) {
  pref.set('layout.' + page, {});
  const grid = GRIDS.get(page); if (!grid) return;
  flip(grid, () => buildGrid(page, grid));
}
export function move(page, id, delta) {
  const grid = GRIDS.get(page); const c = REG.get(id)?._card; if (!grid || !c) return;
  const sib = delta < 0 ? c.previousElementSibling : c.nextElementSibling?.nextElementSibling;
  flip(grid, () => grid.insertBefore(c, delta < 0 ? sib : (sib || null)));
  if (delta > 0 && !c.nextElementSibling) grid.appendChild(c);
  saveOrder(page);
}

// ------------------------------------------------------------------ expand (per-widget maximise)
export function expand(card, on) {
  const want = on ?? !card.classList.contains('expanded');
  $$('.w.expanded').forEach(c => { if (c !== card) c.classList.remove('expanded'); });
  card.classList.toggle('expanded', want);
  document.body.classList.toggle('w-expanded', want);
  let bd = $('#wBackdrop');
  if (!bd) { bd = document.createElement('div'); bd.id = 'wBackdrop'; bd.onclick = () => $$('.w.expanded').forEach(c => expand(c, false)); document.body.appendChild(bd); }
  const btn = card.querySelector('[data-wa="expand"]'); if (btn) btn.textContent = want ? '⤡' : '⤢';
  requestAnimationFrame(() => window.dispatchEvent(new Event('resize')));
}
document.addEventListener('keydown', (e) => { if (e.key === 'Escape') $$('.w.expanded').forEach(c => expand(c, false)); });

// ------------------------------------------------------------------ export menu
function exportMenu(btn, def, card) {
  $('#wMenu')?.remove();
  const m = document.createElement('div'); m.id = 'wMenu'; m.className = 'w-menu';
  m.innerHTML = `${def.csv ? '<button data-x="csv">⇩ Data as CSV</button>' : ''}<button data-x="png">▣ Snapshot PNG</button>`;
  document.body.appendChild(m);
  const r = btn.getBoundingClientRect();
  m.style.top = `${r.bottom + 6}px`; m.style.left = `${Math.max(8, Math.min(innerWidth - 190, r.right - 180))}px`;
  m.onclick = async (e) => {
    const x = e.target.closest('[data-x]')?.dataset.x; if (!x) return;
    m.remove();
    if (x === 'csv') { const d = def.csv(); if (d) saveCSV(d.name || def.id, d.rows, d.cols); else toast('No data yet'); }
    else savePNG(card, 'liquidity_' + def.id);
  };
  setTimeout(() => document.addEventListener('pointerdown', function off(ev) { if (!m.contains(ev.target)) { m.remove(); document.removeEventListener('pointerdown', off); } }), 0);
}

// ------------------------------------------------------------------ layout drawer (show / hide / size / order / reset)
export function openLayout(page) {
  const defs = defsFor(page);
  if (!defs.length) { toast('This page has no customisable widgets'); return; }
  let dr = $('#wDrawer');
  if (!dr) { dr = document.createElement('aside'); dr.id = 'wDrawer'; dr.className = 'w-drawer'; document.body.appendChild(dr); }
  const grid = GRIDS.get(page);
  const draw = () => {
    const order = grid ? $$(':scope > .w', grid).map(c => c.dataset.w) : defs.map(d => d.id);
    const L = layout(page);
    dr.innerHTML = `<div class="wd-h"><b>Layout · ${esc(page)}</b><button class="btn ghost sm" id="wdClose">✕</button></div>
      <div class="muted small" style="margin:0 0 10px">Drag ⠿ on any card to move it. Sizes and visibility are saved in this browser.</div>
      <div class="wd-list">${order.map(id => { const d = REG.get(id); if (!d) return ''; const sz = L.size[id] || d.size || 'm';
        return `<div class="wd-row" data-id="${id}"><label><input type="checkbox" ${L.hidden.includes(id) ? '' : 'checked'}> <span>${stripTags(d.title)}</span></label>
          <div class="seg sm">${SIZES.map(([v, l]) => `<button data-sz="${v}" class="${v === sz ? 'on' : ''}">${l}</button>`).join('')}</div>
          <span class="wd-mv"><button class="w-t" data-mv="-1" title="Move up">▲</button><button class="w-t" data-mv="1" title="Move down">▼</button></span></div>`; }).join('')}</div>
      <div class="row gap" style="margin-top:12px"><button class="btn ghost sm" id="wdReset">Reset this page</button><button class="btn ghost sm" id="wdAll">Show all</button></div>`;
    $('#wdClose', dr).onclick = () => dr.classList.remove('on');
    $('#wdReset', dr).onclick = () => { resetLayout(page); draw(); };
    $('#wdAll', dr).onclick = () => { defs.forEach(d => setHidden(page, d.id, false)); draw(); };
    dr.onchange = (e) => { const row = e.target.closest('.wd-row'); if (row && e.target.type === 'checkbox') setHidden(page, row.dataset.id, !e.target.checked); };
    dr.onclick = (e) => {
      const row = e.target.closest('.wd-row'); if (!row) return;
      const sz = e.target.closest('[data-sz]'); if (sz) { setSize(page, row.dataset.id, sz.dataset.sz); draw(); }
      const mv = e.target.closest('[data-mv]'); if (mv) { move(page, row.dataset.id, +mv.dataset.mv); draw(); }
    };
  };
  draw();
  dr.classList.add('on');
}
