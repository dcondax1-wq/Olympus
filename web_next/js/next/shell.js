// Shell of the redesigned dashboard: sidebar, phone tab bar, Data tab strip, module breadcrumb, Modules tile grid,
// search button and the Settings > Interface card. app.js calls initShell() at boot and onPage(id) on every navigation.
import { $, $$, store, esc } from '../util.js';
import { icon } from './icons.js';
import { TOP, DATA, MODULES, TITLES, groupOf } from './routes.js';

const root = document.documentElement;
const pref = { get: (k, d) => store.get('nx.' + k, d), set: (k, v) => store.set('nx.' + k, v) };

const PINS = ['live', 'briefing', 'results', 'cold'];

function navLink(p, extra = '') {
  // label span first: the command palette reads the first <span> of each #nav link as the page name (CSS puts the icon first)
  return `<a data-page="${p.id}" ${extra} title="${esc(p.label)}"><span class="nx-nl">${esc(p.label)}</span><span class="nx-ni">${icon(p.icon)}</span></a>`;
}

function buildNav() {
  const nav = $('#nav');
  // visible: the six top-level pages. Hidden: every sub page, so the command palette (reads #nav a[data-page]) lists them.
  nav.innerHTML = TOP.map(p => navLink(p)).join('') +
    `<div class="nx-nav-sec">Pinned</div>` +
    PINS.map(id => [...DATA, ...MODULES].find(p => p.id === id)).map(p => navLink(p, 'class="nx-pin"')).join('') +
    `<div class="nx-nav-all" hidden>${[...DATA, ...MODULES].filter(p => !PINS.includes(p.id)).map(p => `<a data-page="${p.id}"><span>${esc(p.label)}</span></a>`).join('')}</div>`;
  $('#nxTabs').innerHTML = TOP.filter(p => p.id !== 'settings').map(p =>
    `<button type="button" data-goto="${p.id}" class="nx-tab" data-tab="${p.id}"><span class="nx-ti">${icon(p.icon)}</span><span>${p.label}</span></button>`).join('');
  $('#nxCollapse').innerHTML = icon('collapse') + '<span>Collapse</span>';
  $('#nxSearch .nx-search-i').innerHTML = icon('search');
}

function buildModules() {
  const el = $('#page-modules');
  el.innerHTML = `
    <div class="nx-hero">
      <div><div class="nx-eyebrow">Modules</div><h2>Every tool the engine runs on</h2>
        <p class="muted">Strategy, risk, research and connections. Tap a tile to open it; the command palette (Ctrl K) reaches all of them too.</p></div>
      <label class="nx-field nx-find">${icon('search')}<input id="nxModFind" class="inp" placeholder="Filter modules" autocomplete="off"></label>
    </div>
    <div class="nx-tiles" id="nxTiles">${MODULES.map(m => `
      <button type="button" class="nx-tile" data-goto="${m.id}" data-k="${esc((m.label + ' ' + m.desc).toLowerCase())}">
        <span class="nx-tile-i">${icon(m.icon)}</span>
        <span class="nx-tile-t">${esc(m.label)}</span>
        <span class="nx-tile-d">${esc(m.desc)}</span>
        <span class="nx-tile-b" id="nxBadge-${m.id}"></span>
        <span class="nx-tile-go">${icon('right')}</span>
      </button>`).join('')}
    </div>
    <div class="nx-eyebrow" style="margin:26px 2px 10px">App</div>
    <div class="nx-tiles compact">
      <button type="button" class="nx-tile" data-goto="settings"><span class="nx-tile-i">${icon('settings')}</span><span class="nx-tile-t">Settings</span><span class="nx-tile-d">Themes, phone app, interface</span><span class="nx-tile-go">${icon('right')}</span></button>
    </div>
    <div class="nx-eyebrow" style="margin:26px 2px 10px">Data</div>
    <div class="nx-tiles compact">${DATA.map(m => `
      <button type="button" class="nx-tile" data-goto="${m.id}"><span class="nx-tile-i">${icon(m.icon)}</span>
        <span class="nx-tile-t">${esc(m.label)}</span><span class="nx-tile-d">${esc(m.desc)}</span><span class="nx-tile-go">${icon('right')}</span></button>`).join('')}
    </div>`;
  $('#nxModFind').oninput = (e) => {
    const q = e.target.value.trim().toLowerCase();
    $$('#nxTiles .nx-tile').forEach(t => { t.hidden = q && !t.dataset.k.includes(q); });
  };
  // live badges
  fetch('/api/next/cold').then(r => r.ok ? r.json() : null).then(d => {
    const b = $('#nxBadge-cold'); if (!b || !d?.now) return;
    b.className = 'nx-tile-b ' + (d.now.on ? 'good' : 'warn');
    b.textContent = !d.now.enabled ? 'off' : d.now.on ? 'full size' : 'half size';
  }).catch(() => null);
  const b = $('#nxBadge-risk'); if (b) { b.className = 'nx-tile-b'; b.textContent = '$800 · ref 20 pts'; }
}

function buildSub(page) {
  const el = $('#nxSub');
  const g = groupOf(page);
  if (g === 'data') {
    el.innerHTML = `<div class="nx-strip" role="tablist">${DATA.map(p =>
      `<button type="button" role="tab" data-goto="${p.id}" class="${p.id === page ? 'on' : ''}" aria-selected="${p.id === page}">${icon(p.icon)}<span>${esc(p.label)}</span></button>`).join('')}</div>`;
    el.querySelector('.on')?.scrollIntoView({ inline: 'center', block: 'nearest' });
    el.hidden = false;
  } else if (g === 'modules' && page !== 'modules') {
    const i = MODULES.findIndex(p => p.id === page);
    const prev = MODULES[(i - 1 + MODULES.length) % MODULES.length], next = MODULES[(i + 1) % MODULES.length];
    el.innerHTML = `<div class="nx-modbar">
      <button type="button" class="nx-back" data-goto="modules">${icon('back')}<span>Modules</span></button>
      <span class="nx-modbar-sp"></span>
      <button type="button" class="nx-chipbtn" data-goto="${prev.id}" title="${esc(prev.label)}">${icon('left')}<span>${esc(prev.label)}</span></button>
      <button type="button" class="nx-chipbtn" data-goto="${next.id}" title="${esc(next.label)}"><span>${esc(next.label)}</span>${icon('right')}</button></div>`;
    el.hidden = false;
  } else { el.innerHTML = ''; el.hidden = true; }
}

export function onPage(page) {
  const g = groupOf(page);
  root.dataset.page = page;
  root.dataset.group = g;
  $$('#nav > a').forEach(a => a.classList.toggle('active', a.dataset.page === page || a.dataset.page === g));
  $$('#nxTabs .nx-tab').forEach(t => t.classList.toggle('on', t.dataset.tab === g || (g === 'settings' && t.dataset.tab === 'modules')));
  $('#nxCrumb').textContent = g === 'data' ? 'Data' : g === 'modules' && page !== 'modules' ? 'Modules' : '';
  buildSub(page);
  requestAnimationFrame(() => { $('#page-' + page)?.scrollTo?.(0, 0); });
  document.title = `${TITLES[page] || 'Liquidity Engine'} · Liquidity Engine`;
}

function interfaceCard() {
  const el = $('#nxInterface'); if (!el) return;
  const row = (id, label, sub, on) => `<label class="nx-switch-row"><span><b>${label}</b><span class="muted small">${sub}</span></span>
    <input type="checkbox" class="nx-switch" id="${id}" ${on ? 'checked' : ''}></label>`;
  el.innerHTML = row('nxOptCollapse', 'Compact sidebar', 'Icons only on desktop', pref.get('collapsed', false)) +
    row('nxOptPins', 'Pinned shortcuts', 'Liquidity Engine, Briefing, Results, Cold-Streak in the sidebar', pref.get('pins', true)) +
    `<div class="note">Classic dashboard: start the server with <span class="mono">LE_UI=classic</span> to get the previous look. Every page is shared, so both stay in sync.</div>`;
  $('#nxOptCollapse').onchange = (e) => setCollapsed(e.target.checked);
  $('#nxOptPins').onchange = (e) => { pref.set('pins', e.target.checked); root.dataset.pins = e.target.checked ? 'on' : 'off'; };
}

function setCollapsed(on) {
  pref.set('collapsed', on);
  root.dataset.side = on ? 'mini' : 'full';
  const c = $('#nxOptCollapse'); if (c) c.checked = on;
  setTimeout(() => window.dispatchEvent(new Event('resize')), 260);
}

export function initShell() {
  buildNav();
  buildModules();
  interfaceCard();
  root.dataset.side = pref.get('collapsed', false) ? 'mini' : 'full';
  root.dataset.pins = pref.get('pins', true) ? 'on' : 'off';
  $('#nxCollapse').onclick = () => setCollapsed(root.dataset.side !== 'mini');
  $('#nxSearch').onclick = () => { const b = $('#cpBtn'); if (b) b.click(); else document.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', ctrlKey: true })); };
  // the top bar hides its border until the page scrolls
  document.addEventListener('scroll', (e) => {
    if (e.target?.classList?.contains('page')) root.classList.toggle('nx-scrolled', e.target.scrollTop > 4);
  }, true);
  addEventListener('scroll', () => root.classList.toggle('nx-scrolled', scrollY > 4), { passive: true });
}
