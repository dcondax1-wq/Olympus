// Shell of the redesigned dashboard: sidebar, phone tab bar, Data tab strip, module breadcrumb, Modules tile grid,
// search button and the Settings > Interface card. app.js calls initShell() at boot and onPage(id) on every navigation.
import { $, $$, store, esc } from '../util.js';
import { icon } from './icons.js';
import { TOP, DATA, MODULES, ARCHIVE, HUB, TITLES, groupOf, CC, GROUPS, TABS } from './routes.js';
import { fxLevel, setFxLevel } from './fx3d.js';

const root = document.documentElement;
const pref = { get: (k, d) => store.get('nx.' + k, d), set: (k, v) => store.set('nx.' + k, v) };

const PINS = ['morning', 'livechart', 'perf', 'evalhq', 'strategy', 'live', 'briefing', 'results', 'evals'];

function navLink(p, extra = '') {
  // label span first: the command palette reads the first <span> of each #nav link as the page name (CSS puts the icon first)
  return `<a data-page="${p.id}" ${extra} title="${esc(p.label)}"><span class="nx-nl">${esc(p.label)}</span><span class="nx-ni">${icon(p.icon)}</span></a>`;
}

function buildNav() {
  const nav = $('#nav');
  // grouped sidebar (2026-10-25): Home · Accounts · Trading · Results · Operations · More, each group folds (remembered).
  // Every other page sits in a hidden list so the command palette (reads #nav a[data-page]) still lists all of them.
  const ALL = [...TOP, ...CC, ...DATA, ...MODULES];
  const find = (id) => ALL.find(p => p.id === id) || { id, label: TITLES[id] || id, icon: 'dot' };
  const shut = new Set(pref.get('navShut', []));
  const shown = new Set(GROUPS.flatMap(g => g.ids));
  nav.innerHTML = GROUPS.map(g => `<button type="button" class="nx-nav-sec nx-grp-h${shut.has(g.label) ? ' shut' : ''}" data-grp="${esc(g.label)}" aria-expanded="${!shut.has(g.label)}">${esc(g.label)}<i>${icon('down')}</i></button>` +
    g.ids.map(id => navLink(find(id), `class="nx-gl${shut.has(g.label) ? ' nx-hide' : ''}" data-g="${esc(g.label)}"`)).join('')).join('') +
    `<div class="nx-nav-all" hidden>${ALL.filter(p => !shown.has(p.id) && p.id !== 'data').map(p => `<a data-page="${p.id}"><span>${esc(p.label)}</span></a>`).join('')}${ARCHIVE.map(p => `<a data-page="${p.id}"><span>${esc(TITLES[p.id])}</span></a>`).join('')}</div>`;
  nav.addEventListener('click', (e) => {
    const h = e.target.closest('.nx-grp-h'); if (!h) return;
    const g = h.dataset.grp, now = new Set(pref.get('navShut', []));
    const close = !now.has(g); close ? now.add(g) : now.delete(g);
    pref.set('navShut', [...now]);
    h.classList.toggle('shut', close); h.setAttribute('aria-expanded', String(!close));
    $$(`#nav > a[data-g="${CSS.escape(g)}"]`).forEach(a => a.classList.toggle('nx-hide', close && !a.classList.contains('active')));
  });
  $('#nxTabs').innerHTML = TABS.map(find).map(p =>
    `<button type="button" data-goto="${p.id}" class="nx-tab" data-tab="${p.id}"><span class="nx-ti">${icon(p.icon)}</span><span>${esc(p.id === 'cc' ? 'Home' : p.label)}</span></button>`).join('');
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
    if (d.model === 'lit') {                  // LIT has no cold-streak filter: the badge shows its weekly stop
      const w = d.lit_rules?.weekly_stop;
      b.className = 'nx-tile-b ' + (w && w.mult < 1 ? 'warn' : 'good');
      b.textContent = w ? (w.mult < 1 ? 'weekly stop: half' : `weekly stop ${w.stops}/${w.after}`) : 'LIT: weekly stop';
      return;
    }
    b.className = 'nx-tile-b ' + (d.now.on ? 'good' : 'warn');
    b.textContent = !d.now.enabled ? 'off' : d.now.on ? 'full size' : 'half size';
  }).catch(() => null);
  const b = $('#nxBadge-risk'); if (b) { b.className = 'nx-tile-b'; b.textContent = '$800 · ref 20 pts'; }
  const ab = $('#nxBadge-archive'); if (ab) { ab.className = 'nx-tile-b'; ab.textContent = 'Liquidity Engine · shadow'; }
  const lb = $('#nxBadge-live'); if (lb) { lb.className = 'nx-tile-b good'; lb.textContent = 'LIT'; }
  fetch('/api/next/strategy').then(r => r.ok ? r.json() : null).then(d => {
    const s = $('#nxBadge-strategy'); if (!s || !d?.live_model) return;
    s.className = 'nx-tile-b good'; s.textContent = (d.live_model.locked ? 'locked ' : '') + (d.live_model.chosen || '');
  }).catch(() => null);
  fetch('/api/next/news').then(r => r.ok ? r.json() : null).then(d => {
    const n = $('#nxBadge-newshub'); if (!n || !d) return;
    const hi = (d.events || []).filter(e => e.impact === 'high' && e.t * 1000 > Date.now()).length;
    n.className = 'nx-tile-b ' + (hi ? 'warn' : ''); n.textContent = hi ? `${hi} high-impact ahead` : 'quiet week';
  }).catch(() => null);
}

function buildSub(page) {
  const el = $('#nxSub');
  const g = groupOf(page);
  if (g === 'data') {
    el.innerHTML = `<div class="nx-strip" role="tablist">${DATA.map(p =>
      `<button type="button" role="tab" data-goto="${p.id}" class="${p.id === page ? 'on' : ''}" aria-selected="${p.id === page}">${icon(p.icon)}<span>${esc(p.label)}</span></button>`).join('')}</div>`;
    el.querySelector('.on')?.scrollIntoView({ inline: 'center', block: 'nearest' });
    el.hidden = false;
  } else if (g === 'archive') {
    const i = ARCHIVE.findIndex(p => p.id === page);
    const prev = ARCHIVE[(i - 1 + ARCHIVE.length) % ARCHIVE.length], next = ARCHIVE[(i + 1) % ARCHIVE.length];
    el.innerHTML = `<div class="nx-modbar">
      <button type="button" class="nx-back" data-goto="archive">${icon('back')}<span>Archive</span></button>
      <span class="nx-modbar-sp"></span>
      <button type="button" class="nx-chipbtn" data-goto="${prev.id}" title="${esc(prev.label)}">${icon('left')}<span>${esc(prev.label)}</span></button>
      <button type="button" class="nx-chipbtn" data-goto="${next.id}" title="${esc(next.label)}"><span>${esc(next.label)}</span>${icon('right')}</button></div>`;
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
  $$('#nxTabs .nx-tab').forEach(t => t.classList.toggle('on', t.dataset.tab === g || ((g === 'settings' || g === 'archive') && t.dataset.tab === 'modules')));
  $('#nxCrumb').textContent = g === 'data' ? 'Data' : g === 'modules' && page !== 'modules' ? 'Modules' : g === 'archive' ? 'Archive · previous strategy' : '';
  buildSub(page);
  requestAnimationFrame(() => { $('#page-' + page)?.scrollTo?.(0, 0); });
  document.title = `${TITLES[page] || 'Liquidity Engine'} · Liquidity Engine`;   // the app's name; the strategy is LIT
}

function interfaceCard() {
  const el = $('#nxInterface'); if (!el) return;
  const row = (id, label, sub, on) => `<label class="nx-switch-row"><span><b>${label}</b><span class="muted small">${sub}</span></span>
    <input type="checkbox" class="nx-switch" id="${id}" ${on ? 'checked' : ''}></label>`;
  el.innerHTML = row('nxOptCollapse', 'Compact sidebar', 'Icons only on desktop', pref.get('collapsed', false)) +
    row('nxOptPins', 'Pinned shortcuts', 'Eval HQ, Strategy, Paper Bot (LIT), Briefing, Results, Evals in the sidebar', pref.get('pins', true)) +
    `<div class="nx-switch-row"><span><b>3D effects</b><span class="muted small">Galaxy background, card glow, tap sparks, Live Oracle, trade galaxy, month city. Lite saves battery.</span></span>
      <div class="seg sm" id="nxOptFx">${[['max', 'Max'], ['lite', 'Lite'], ['off', 'Off']].map(([v, l]) => `<button type="button" data-v="${v}" class="${fxLevel() === v ? 'on' : ''}">${l}</button>`).join('')}</div></div>` +
    `<div class="note">Classic dashboard: start the server with <span class="mono">LE_UI=classic</span> to get the previous look. Every page is shared, so both stay in sync.</div>`;
  $('#nxOptCollapse').onchange = (e) => setCollapsed(e.target.checked);
  $('#nxOptFx').onclick = (e) => { const b = e.target.closest('button'); if (!b) return; $$('#nxOptFx button').forEach(x => x.classList.toggle('on', x === b)); setFxLevel(b.dataset.v); };
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
