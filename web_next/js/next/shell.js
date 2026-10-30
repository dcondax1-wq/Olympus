// Shell of the redesigned dashboard: sidebar, phone tab bar, Data tab strip, module breadcrumb, Modules tile grid,
// search button and the Settings > Interface card. app.js calls initShell() at boot and onPage(id) on every navigation.
import { $, $$, store, esc } from '../util.js';
import { icon } from './icons.js';
import { TOP, DATA, MODULES, ARCHIVE, HUB, TITLES, groupOf, CC, GROUPS, TABS, NAV_NAMES, groupIds, BOTS, BOT_CHIP, botOf, MAIN_SECTIONS } from './routes.js';
import { fxLevel, setFxLevel, fxBg, setFxBg } from './fx3d.js';
import { moreMenu } from './menu.js';

const root = document.documentElement;
const pref = { get: (k, d) => store.get('nx.' + k, d), set: (k, v) => store.set('nx.' + k, v) };


function navLink(p, extra = '') {
  // label span first: the command palette reads the first <span> of each #nav link as the page name (CSS puts the icon first)
  const name = NAV_NAMES[p.id] || p.label;
  return `<a data-page="${p.id}" ${extra} title="${esc(TITLES[p.id] || p.label)}"><span class="nx-nl">${esc(name)}</span><span class="nx-ni">${icon(p.icon)}</span></a>`;
}

// which sidebar groups are folded: "Advanced" starts folded (key navShut.v2, so the old six-group state does not carry over)
const shutSet = () => new Set(pref.get('navShut.v2', ['Advanced']));
function paintNav() {
  const shut = shutSet();
  $$('#nav > .nx-grp-h').forEach(h => { const c = shut.has(h.dataset.grp); h.classList.toggle('shut', c); h.setAttribute('aria-expanded', String(!c)); });
  $$('#nav > .nx-gl').forEach(a => a.classList.toggle('nx-hide', shut.has(a.dataset.g) && !a.classList.contains('active')));
  $$('#nav > .nx-nav-sub').forEach(d => d.classList.toggle('nx-hide', shut.has(d.dataset.g)));
}

function buildNav() {
  const nav = $('#nav');
  // cleaned sidebar (2026-10-25; PM: Home, Zlarior, ATLAS, Results, All tools; the bot pages hold their sections) and one "Advanced" group,
  // folded by default, with four small sections. Every other page sits in a hidden list so the command palette
  // (reads #nav a[data-page]) still lists all of them; renamed entries are listed there under their page title too.
  const ALL = [...TOP, ...CC, ...DATA, ...MODULES];
  const find = (id) => ALL.find(p => p.id === id) || { id, label: TITLES[id] || id, icon: 'dot' };
  const shown = new Set(GROUPS.flatMap(groupIds));
  const links = (g, ids) => ids.map(id => navLink(find(id), `class="nx-gl" data-g="${esc(g.label)}"`)).join('');
  // 2026-10-30: the Main items in plain sections (routes.js MAIN_SECTIONS: Bots · Live · Money · Insight); each id once
  const mainLinks = (g) => {
    if (!Array.isArray(MAIN_SECTIONS) || !MAIN_SECTIONS.length) return links(g, g.ids);
    const used = new Set(), out = [];
    for (const [t, ids] of MAIN_SECTIONS) {
      const L = ids.filter((id) => g.ids.includes(id) && !used.has(id)); if (!L.length) continue;
      L.forEach((id) => used.add(id));
      out.push((t ? `<div class="nx-nav-sub nx-main-sub" data-g="${esc(g.label)}">${esc(t)}</div>` : '') + links(g, L));
    }
    const rest = g.ids.filter((id) => !used.has(id));
    return out.join('') + (rest.length ? links(g, rest) : '');
  };
  nav.innerHTML = GROUPS.map(g => {
    if (!g.advanced) return g.label === 'Main' ? mainLinks(g) : links(g, g.ids);
    return `<button type="button" class="nx-nav-sec nx-grp-h nx-adv-h" data-grp="${esc(g.label)}"><span>${esc(g.label)}</span><i>${icon('down')}</i></button>` +
      g.sections.map(s => `<div class="nx-nav-sub" data-g="${esc(g.label)}">${esc(s.label)}</div>` + links(g, s.ids)).join('');
  }).join('') +
    `<div class="nx-nav-all" hidden>${ALL.filter(p => (!shown.has(p.id) || NAV_NAMES[p.id]) && p.id !== 'data' && p.id !== 'zlarior').map(p => `<a data-page="${p.id}"><span>${esc(TITLES[p.id] || p.label)}</span></a>`).join('')}${ARCHIVE.map(p => `<a data-page="${p.id}"><span>${esc(TITLES[p.id])}</span></a>`).join('')}</div>`;
  paintNav();
  nav.addEventListener('click', (e) => {
    const h = e.target.closest('.nx-grp-h'); if (!h) return;
    const g = h.dataset.grp, now = shutSet();
    now.has(g) ? now.delete(g) : now.add(g);
    pref.set('navShut.v2', [...now]);
    paintNav();
  });
  $('#nxTabs').innerHTML = TABS.map(find).map(p =>
    `<button type="button" data-goto="${p.id}" class="nx-tab" data-tab="${p.id}"><span class="nx-ti">${icon(p.icon)}</span><span>${esc(NAV_NAMES[p.id] || p.label)}</span></button>`).join('');
  $('#nxCollapse').innerHTML = icon('collapse') + '<span>Collapse</span>';
  $('#nxSearch .nx-search-i').innerHTML = icon('search');
}

function buildModules() {
  const el = $('#page-modules');
  // "All tools" (2026-10-25 clean-up): every page in one place, in plain sections, as compact tiles. The filter box and the
  // command palette (Ctrl K) find any of them. Nothing is hidden: the sidebar's Advanced group is a shortcut to the same pages.
  const tile = (m) => `<button type="button" class="nx-tile" data-goto="${m.id}" data-k="${esc((m.label + ' ' + (m.desc || '')).toLowerCase())}">
        <span class="nx-tile-i">${icon(m.icon)}</span><span class="nx-tile-t">${esc(m.label)}</span>
        <span class="nx-tile-d">${esc(m.desc || '')}</span><span class="nx-tile-b" id="nxBadge-${m.id}"></span><span class="nx-tile-go">${icon('right')}</span></button>`;
  const pick = (ids) => ids.map(id => [...MODULES, ...CC, ...TOP].find(p => p.id === id)).filter(Boolean)
    .map(p => ({ ...p, desc: p.desc || { brain: 'What the bot is thinking right now: levels, setups, sizing, guards (read-only)', atlas: 'Strategy 2 on the 25K: EMA + MACD + S/R, its paper ledger and go / no-go', accounts: 'The LIT 50K account: balance, floor, eval sessions and trades', command: 'The classic Today page: two-strategy cards, bot strip and every widget' }[p.id] || '' }));
  const used = new Set();
  const SECT = [
    ['Accounts and evals', ['accounts', 'atlas', 'goals', 'evalhq', 'evaltl', 'litcockpit', 'mffurules']],
    ['Running the bot', ['command', 'brain', 'livechart', 'morning', 'ntpanel', 'botlog', 'timeline', 'livesettings', 'live', 'launch', 'alerts']],
    ['Help and safety', ['runbook', 'audit', 'sesscal', 'features', 'tv']],
    ['The strategy', ['strategy', 'rules', 'risk', 'litday', 'litlevels']],
    ['Trades and review', ['tradelog', 'atlassetups', 'memory', 'journal', 'review', 'report', 'briefing']],
    ['Market and business', ['newshub', 'news', 'market', 'firms', 'business', 'learn', 'system']],
  ].map(([t, ids]) => { const ps = pick(ids); ps.forEach(p => used.add(p.id)); return [t, ps]; });
  const rest = MODULES.filter(m => !used.has(m.id) && m.id !== 'archive');
  if (rest.length) SECT.push(['More', rest]);
  el.innerHTML = `
    <div class="nx-hero">
      <div><div class="nx-eyebrow">All tools</div><h2>Every page in one place</h2>
        <p class="muted">Grouped by what you want to do. Type to filter, or press Ctrl K from anywhere.</p></div>
      <label class="nx-field nx-find">${icon('search')}<input id="nxModFind" class="inp" placeholder="Filter tools" autocomplete="off"></label>
    </div>
    <div id="nxTiles">${SECT.map(([t, ps]) => `<section class="nx-tsec"><div class="nx-eyebrow nx-tsec-h">${esc(t)}</div><div class="nx-tiles compact">${ps.map(tile).join('')}</div></section>`).join('')}
    <section class="nx-tsec"><div class="nx-eyebrow nx-tsec-h">Results and research</div><div class="nx-tiles compact">${DATA.map(tile).join('')}</div></section>
    <section class="nx-tsec"><div class="nx-eyebrow nx-tsec-h">Archive and app</div><div class="nx-tiles compact">${tile(MODULES.find(m => m.id === 'archive'))}
      <button type="button" class="nx-tile" data-goto="settings" data-k="settings themes phone app interface 3d"><span class="nx-tile-i">${icon('settings')}</span><span class="nx-tile-t">Settings</span><span class="nx-tile-d">Interface, 3D background, themes, phone app, alerts</span><span class="nx-tile-go">${icon('right')}</span></button></div></section>
    <p class="muted small nx-tsec-empty" id="nxModNone" hidden>No tool matches. Try a shorter word, or press Ctrl K.</p></div>`;
  $('#nxModFind').oninput = (e) => {
    const q = e.target.value.trim().toLowerCase();
    $$('#nxTiles .nx-tile').forEach(t => { t.hidden = q && !t.dataset.k.includes(q); });
    $$('#nxTiles .nx-tsec').forEach(sec => { sec.hidden = !sec.querySelector('.nx-tile:not([hidden])'); });
    $('#nxModNone').hidden = !!$('#nxTiles .nx-tile:not([hidden])');
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

// the bot pages (2026-10-25 PM): Zlarior / ATLAS sections as a segmented control, then the section's pages as chips.
// ATLAS parts ("atlas:brain") open the one ATLAS page on that part (store nx.atPart, read by second.js).
export const atPart = () => store.get('nx.atPart', 'today');
export const bzPart = () => store.get('nx.bzPart', 'today');     // BLITZ's part (js/next/blitz.js), 2026-10-29
const botTitle = (it) => BOT_CHIP[it] || TITLES[it.split(':')[0]] || it;
function botBar(b, page) {
  const B = BOTS[b], key = page === 'atlas' && atPart() !== 'today' ? 'atlas:' + atPart() : page === 'blitz' && bzPart() !== 'today' ? 'blitz:' + bzPart() : page;
  let si = B.segs.findIndex(s => s[1].includes(key)); if (si < 0) si = 0;
  const attr = (it) => { const [id, part] = it.split(':'); return `data-goto="${esc(id)}"${id === 'atlas' ? ` data-atpart="${esc(part || 'today')}"` : id === 'blitz' ? ` data-bzpart="${esc(part || 'today')}"` : ''}`; };
  const S = B.segs[si];
  return `<div class="nx-botbar"><div class="nx-botname"><b>${esc(B.name)}</b><span>${esc(B.sub)}</span></div>
    <div class="seg nx-botseg" role="tablist" aria-label="${esc(B.name)} sections">${B.segs.map((s, i) => `<button type="button" role="tab" aria-selected="${i === si}" class="${i === si ? 'on' : ''}" ${attr(s[1][0])}>${esc(s[0])}</button>`).join('')}</div></div>
    ${S[1].length > 1 ? `<div class="nx-strip nx-botchips">${S[1].map(it => `<button type="button" ${attr(it)} class="${it === key ? 'on' : ''}"><span>${esc(botTitle(it))}</span></button>`).join('')}</div>` : ''}`;
}
document.addEventListener('click', (e) => {          // capture: runs before app.js go(), so the ATLAS page draws the asked part
  const t = e.target.closest('[data-goto="atlas"]');
  if (t) store.set('nx.atPart', t.dataset.atpart || 'today');
  const z = e.target.closest('[data-goto="blitz"]');
  if (z) store.set('nx.bzPart', z.dataset.bzpart || 'today');
}, true);

function buildSub(page) {
  const el = $('#nxSub');
  const g = groupOf(page);
  if (BOTS[g]) { el.innerHTML = botBar(g, page); el.hidden = false; return; }
  if (g === 'data') {
    el.innerHTML = `<div class="nx-strip" role="tablist">${DATA.filter(p => !botOf(p.id)).map(p =>
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
  paintNav();                                   // a page inside the folded "Advanced" group still shows its own entry
  $('#nxSetBtn')?.classList.toggle('active', page === 'settings');
  $$('#nxTabs .nx-tab').forEach(t => t.classList.toggle('on', t.dataset.tab === g || ((g === 'settings' || g === 'archive') && t.dataset.tab === 'modules')));
  $('#nxCrumb').textContent = BOTS[g] && page !== 'atlas' && page !== 'blitz' ? BOTS[g].name : g === 'data' ? 'Results' : g === 'modules' && page !== 'modules' ? 'Modules' : g === 'archive' ? 'Archive · previous strategy' : '';
  buildSub(page);
  requestAnimationFrame(() => { $('#page-' + page)?.scrollTo?.(0, 0); });
  document.title = `${TITLES[page] || 'Liquidity Engine'} · Liquidity Engine`;   // the app's name; the strategy is LIT
}

function interfaceCard() {
  const el = $('#nxInterface'); if (!el) return;
  const row = (id, label, sub, on) => `<label class="nx-switch-row"><span><b>${label}</b><span class="muted small">${sub}</span></span>
    <input type="checkbox" class="nx-switch" id="${id}" ${on ? 'checked' : ''}></label>`;
  el.innerHTML = row('nxOptCollapse', 'Compact sidebar', 'Icons only on desktop', pref.get('collapsed', false)) +
    row('nxOptAdv', 'Open "Advanced" in the sidebar', 'Show every page in the sidebar; off keeps it to the six main pages', !shutSet().has('Advanced')) +
    `<div class="nx-switch-row"><span><b>3D background</b><span class="muted small">Deep space (Earth, the Moon's eclipse shadow, the Sun, the bots' satellites, a shooting star per closed trade), card glow, tap sparks, Live Oracle, trade galaxy, month city. On by default; Lite is lighter (30 fps); Off keeps a still star sky.</span></span>
      <div class="seg sm" id="nxOptFx">${[['off', 'Off'], ['lite', 'Lite'], ['max', 'Max']].map(([v, l]) => `<button type="button" data-v="${v}" class="${fxLevel() === v ? 'on' : ''}">${l}</button>`).join('')}</div></div>` +
    `<div class="nx-switch-row"><span><b>Background scene</b><span class="muted small">Deep space (default) or the older particle galaxy</span></span>
      <div class="seg sm" id="nxOptFxBg">${[['space', 'Deep space'], ['galaxy', 'Galaxy']].map(([v, l]) => `<button type="button" data-v="${v}" class="${fxBg() === v ? 'on' : ''}">${l}</button>`).join('')}</div></div>` +
    `<div class="note">Classic dashboard: start the server with <span class="mono">LE_UI=classic</span> to get the previous look. Every page is shared, so both stay in sync.</div>`;
  $('#nxOptCollapse').onchange = (e) => setCollapsed(e.target.checked);
  $('#nxOptFx').onclick = (e) => { const b = e.target.closest('button'); if (!b) return; $$('#nxOptFx button').forEach(x => x.classList.toggle('on', x === b)); setFxLevel(b.dataset.v); };
  $('#nxOptFxBg').onclick = (e) => { const b = e.target.closest('button'); if (!b) return; $$('#nxOptFxBg button').forEach(x => x.classList.toggle('on', x === b)); setFxBg(b.dataset.v); };
  $('#nxOptAdv').onchange = (e) => { const s = shutSet(); e.target.checked ? s.delete('Advanced') : s.add('Advanced'); pref.set('navShut.v2', [...s]); paintNav(); };
}

// ------------------------------------------------------------------ top bar: search, news, clock, bell, dark / light and "⋯"
// The rarely used buttons (symbol, pull bars, reload LIT, risk calculator, themes, sound, settings, shortcuts) move into
// the "⋯" menu with a plain label each. The elements keep their ids and handlers, so every action and key still works.
const TOP_MORE = [['symSeg', 'Market'], ['runBtn', 'Reload'], ['refreshData', 'Pull latest bars'], ['rcBtn', 'Risk calculator (R)'],
  ['thmBtn', 'Theme switcher (T)'], ['soundBtn', 'Sound alerts (M)'], ['themeBtn', 'Settings (G then S)']];
export function tidyTop() {
  const tb = $('.nx-top .tb-right'); if (!tb) return;
  let m = $('#nxTopMore');
  if (!m) {
    tb.insertAdjacentHTML('beforeend', moreMenu(`<div class="nx-more-cap">Tools</div><div id="nxTopMoreL"></div>
      <button type="button" role="menuitem" class="nx-more-i" id="nxKeysBtn"><span>Keyboard shortcuts (?)</span></button>`, 'More: market, reload, themes, sound, settings'));
    m = tb.lastElementChild; m.id = 'nxTopMore';
    $('#nxKeysBtn').onclick = () => window.LE?.keys?.help?.();
  }
  const list = $('#nxTopMoreL');
  for (const [id, label] of TOP_MORE) {
    const e = document.getElementById(id);
    if (!e || e.closest('#nxTopMore')) continue;
    const row = document.createElement('div'); row.className = 'nx-more-row'; row.dataset.for = id;
    row.innerHTML = `<span class="nx-more-l">${esc(label)}</span>`;
    row.appendChild(e);
    row.addEventListener('click', (ev) => { if (ev.target === row || ev.target.classList.contains('nx-more-l')) e.click?.(); });
    const at = [...list.children].find(c => TOP_MORE.findIndex(t => t[0] === c.dataset.for) > TOP_MORE.findIndex(t => t[0] === id));
    list.insertBefore(row, at || null);
  }
  tb.appendChild(m);                                  // the menu stays the last button
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
  root.dataset.pins = 'on';
  const sb = $('#nxSetBtn .nx-ni'); if (sb) sb.innerHTML = icon('settings');
  $('#nxCollapse').onclick = () => setCollapsed(root.dataset.side !== 'mini');
  $('#nxSearch').onclick = () => { const b = $('#cpBtn'); if (b) b.click(); else document.dispatchEvent(new KeyboardEvent('keydown', { key: 'k', ctrlKey: true })); };
  // the top bar hides its border until the page scrolls
  document.addEventListener('scroll', (e) => {
    if (e.target?.classList?.contains('page')) root.classList.toggle('nx-scrolled', e.target.scrollTop > 4);
  }, true);
  addEventListener('scroll', () => root.classList.toggle('nx-scrolled', scrollY > 4), { passive: true });
}
