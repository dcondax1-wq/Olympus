// UX chrome: keyboard shortcuts (+ help overlay), zen mode, TV-wall fullscreen with page rotation, quick theme switcher,
// floating risk calculator, notification bell, terminal status bar and the extra command-palette actions.
// Nothing here places orders or arms anything.
import { $, $$, esc, fmt$, fmtN, toast, etStr } from '../util.js';
import { S, effective } from '../state.js';
import { SKINS, A, setAppearance } from '../skins.js';
import { L, onLive, openCenter } from './live.js';
import { openLayout, defsFor, expand } from './widgets.js';
import { pref, dur, killzone, etNow, marketOpen, savePNG, dashIndex, LAUNCH_TS } from './kit.js';

let GO = null;
const typing = (el) => el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.tagName === 'SELECT' || el.isContentEditable);
const root = document.documentElement;

// ------------------------------------------------------------------ popovers
function closePops() { $$('.pop, .pop-scrim').forEach(p => p.remove()); }
function pop(html, { anchor = null, cls = '', scrim = false, id = '' } = {}) {
  closePops();
  if (scrim) { const s = document.createElement('div'); s.className = 'pop-scrim'; s.onclick = closePops; document.body.appendChild(s); }
  const p = document.createElement('div'); p.className = 'pop ' + cls; if (id) p.id = id; p.innerHTML = html;
  document.body.appendChild(p);
  if (anchor) {
    const r = anchor.getBoundingClientRect();
    p.style.top = Math.min(innerHeight - p.offsetHeight - 8, r.bottom + 8) + 'px';
    p.style.left = Math.max(8, Math.min(innerWidth - p.offsetWidth - 8, r.right - p.offsetWidth)) + 'px';
  } else { p.style.top = Math.max(16, (innerHeight - p.offsetHeight) / 3) + 'px'; p.style.left = Math.max(8, (innerWidth - p.offsetWidth) / 2) + 'px'; }
  if (!scrim) setTimeout(() => document.addEventListener('pointerdown', function off(e) { if (!p.contains(e.target) && !e.target.closest('[data-pop-anchor]')) { p.remove(); document.removeEventListener('pointerdown', off); } }), 0);
  return p;
}

// ------------------------------------------------------------------ theme switcher (dark / light / skin)
function themePop(anchor) {
  const draw = (mode) => {
    const list = SKINS.filter(s => mode === 'all' || s.mode === mode);
    return `<div class="thm-modes seg sm">${['all', 'dark', 'light'].map(m => `<button data-m="${m}" class="${m === mode ? 'on' : ''}">${m}</button>`).join('')}</div>
      <div class="thm-grid">${list.map(s => `<button class="thm ${A.skin === s.id ? 'on' : ''}" data-sk="${s.id}"><span class="sw" style="background:${s.sw[0]}"><span style="background:${s.sw[2]}"></span><span style="background:${s.sw[3]}"></span></span><span>${esc(s.name)}<small>${s.mode}</small></span></button>`).join('')}</div>
      <div class="row gap" style="margin-top:8px;justify-content:space-between"><span class="muted small">D toggles dark / light</span><a class="link" data-goto="settings">All appearance settings →</a></div>`;
  };
  const p = pop(draw('all'), { anchor });
  p.onclick = (e) => {
    const m = e.target.closest('[data-m]'); if (m) { p.innerHTML = draw(m.dataset.m); return; }
    const b = e.target.closest('[data-sk]'); if (!b) return;
    const sk = SKINS.find(s => s.id === b.dataset.sk);
    pref.set(sk.mode === 'light' ? 'lastLight' : 'lastDark', sk.id);
    setAppearance({ skin: sk.id });
    $$('.thm', p).forEach(x => x.classList.toggle('on', x === b));
  };
}
export function toggleDarkLight() {
  const cur = SKINS.find(s => s.id === A.skin) || SKINS[0];
  pref.set(cur.mode === 'light' ? 'lastLight' : 'lastDark', cur.id);
  const next = cur.mode === 'light' ? pref.get('lastDark', 'terminal') : pref.get('lastLight', 'arctic');
  setAppearance({ skin: next });
  toast(`Theme: ${SKINS.find(s => s.id === next)?.name || next}`);
}

// ------------------------------------------------------------------ risk calculator
function riskCalc() {
  const p = effective();
  const st = pref.get('rc', { risk: p.risk_usd || 350, stop: 40, inst: 'MNQ', entry: '', rr: 2 });
  const html = `<h4>Risk calculator <button class="btn ghost sm" id="rcX">✕</button></h4>
    <div class="rc-in"><label>Risk per trade ($)</label><input id="rcRisk" type="number" step="25" value="${st.risk}">
      <label>Stop distance (pts)</label><input id="rcStop" type="number" step="0.25" value="${st.stop}">
      <label>Instrument</label><select id="rcInst"><option ${st.inst === 'MNQ' ? 'selected' : ''}>MNQ</option><option ${st.inst === 'NQ' ? 'selected' : ''}>NQ</option></select>
      <label>Target (R)</label><input id="rcRR" type="number" step="0.25" value="${st.rr}">
      <label>Entry price (opt.)</label><input id="rcEntry" type="number" step="0.25" value="${st.entry}" placeholder="${L.live?.state?.price ?? ''}"></div>
    <div class="rc-out" id="rcOut"></div>
    <div class="rc-note">MNQ $2/pt · NQ $20/pt · MFFU 50K cap 40 micros / 4 minis. Information only: this tool places nothing.</div>`;
  const pp = pop(html, { cls: 'rc-panel', scrim: true, id: 'rcPop' });
  const calc = () => {
    const risk = +$('#rcRisk').value || 0, stop = +$('#rcStop').value || 0, inst = $('#rcInst').value, rr = +$('#rcRR').value || 0, entry = parseFloat($('#rcEntry').value);
    pref.set('rc', { risk, stop, inst, entry: isFinite(entry) ? entry : '', rr });
    const ppt = inst === 'NQ' ? 20 : 2, cap = inst === 'NQ' ? 4 : 40;
    const raw = stop > 0 ? Math.floor(risk / (stop * ppt)) : 0, qty = Math.min(cap, raw);
    const act = qty * stop * ppt, tgtPts = stop * rr;
    const cell = (k, v, s = '') => `<div class="kst"><div class="k">${k}</div><div class="v">${v}</div>${s ? `<div class="s">${s}</div>` : ''}</div>`;
    $('#rcOut').innerHTML = cell('Size', `${qty} ${inst}`, raw > cap ? `capped from ${raw}` : qty ? '' : 'stop too wide') + cell('Actual risk', fmt$(act), `${fmtN(act / 2000 * 100, 0)}% of $2k MLL`) +
      cell('Target', `+${fmtN(tgtPts, 2)} pts`, fmt$(qty * tgtPts * ppt)) + cell('Losses to MLL', act ? Math.floor(2000 / act) : '—', 'in a row from start') +
      (isFinite(entry) ? cell('Long SL / TP', `${fmtN(entry - stop, 2)}`, `TP ${fmtN(entry + tgtPts, 2)}`) + cell('Short SL / TP', `${fmtN(entry + stop, 2)}`, `TP ${fmtN(entry - tgtPts, 2)}`) : '');
  };
  pp.oninput = calc; calc();
  $('#rcX').onclick = closePops;
  setTimeout(() => $('#rcStop')?.focus(), 30);
}

// ------------------------------------------------------------------ zen + TV wall
export function setZen(on) {
  on = on ?? root.dataset.zen !== 'on';
  root.dataset.zen = on ? 'on' : 'off';
  window.dispatchEvent(new Event('resize'));
  if (on) toast('Zen mode · press Z or Esc to exit');
}
let wallT = null, wallStart = 0;
const WALL_PAGES = ['command', 'analytics', 'ops'];
export async function setWall(on) {
  on = on ?? root.dataset.wall !== 'on';
  root.dataset.wall = on ? 'on' : 'off';
  clearInterval(wallT);
  if (on) {
    try { if (!document.fullscreenElement) await document.documentElement.requestFullscreen?.(); } catch { }
    const secs = pref.get('wallSecs', 45);
    let i = Math.max(0, WALL_PAGES.indexOf(S.page));
    if (!WALL_PAGES.includes(S.page)) GO?.(WALL_PAGES[0]);
    wallStart = Date.now();
    wallT = setInterval(() => {
      const k = (Date.now() - wallStart) / (secs * 1000);
      const bar = $('#wallBar i'); if (bar) bar.style.width = Math.min(100, k * 100) + '%';
      if (k >= 1 && pref.get('wallRotate', true)) { i = (i + 1) % WALL_PAGES.length; GO?.(WALL_PAGES[i]); wallStart = Date.now(); }
    }, 250);
    toast(`TV wall · rotating ${WALL_PAGES.join(' → ')} every ${secs}s · F or Esc to exit`, 3500);
  } else if (document.fullscreenElement) { try { await document.exitFullscreen(); } catch { } }
  window.dispatchEvent(new Event('resize'));
}
document.addEventListener('fullscreenchange', () => { if (!document.fullscreenElement && root.dataset.wall === 'on') setWall(false); });

// ------------------------------------------------------------------ shortcuts
const KEYS = [
  ['Ctrl K  or  /', 'Command palette'], ['?', 'This help'], ['G then C', 'Command Center'], ['G then A', 'Deep Stats'], ['G then O', 'Ops & Data'], ['G then L', 'Live bot'],
  ['G then K', 'Launch control'], ['G then H', 'Chart'], ['G then B', 'Backtest'], ['G then N', 'Markets & news'], ['G then M', 'Trade memory'], ['G then S', 'Settings'],
  ['1 … 5', 'Command · Stats · Ops · Live · Chart'], ['Z', 'Zen mode'], ['F', 'TV-wall fullscreen'], ['T', 'Theme switcher'], ['D', 'Dark / light'], ['R', 'Risk calculator'],
  ['N', 'Notifications'], ['W', 'Widget layout'], ['X', 'Snapshot page as PNG'], ['M', 'Sound alerts on / off'], ['Esc', 'Close / exit modes'],
];
const GMAP = { c: 'command', a: 'analytics', o: 'ops', l: 'live', k: 'launch', h: 'chart', b: 'backtest', n: 'news', m: 'memory', s: 'settings', r: 'replay', p: 'prop', w: 'review', f: 'conf', j: 'journal', g: 'regime' };
const NUM = ['command', 'analytics', 'ops', 'live', 'chart'];
function helpPop() {
  pop(`<div class="kbd-help"><h4>Keyboard shortcuts</h4><div class="kbd-grid">${KEYS.map(([k, d]) => `<div><span>${esc(d)}</span><span>${k.split('  or  ').map(x => x.split(' then ').map(y => `<kbd>${esc(y)}</kbd>`).join(' then ')).join(' or ')}</span></div>`).join('')}</div>
    <div class="muted small" style="margin-top:10px">Shortcuts are ignored while typing in a field. Widgets: drag ⠿ to move, ⤢ to expand, ⇩ to export.</div></div>`, { scrim: true });
}
let gPending = 0;
function onKey(e) {
  // Esc closes popovers / drawers even while a field inside them has focus
  if (e.key === 'Escape' && ($('.pop') || $('.w-drawer.on'))) { closePops(); $$('.w-drawer.on').forEach(d => d.classList.remove('on')); document.activeElement?.blur?.(); return; }
  if (e.ctrlKey || e.metaKey || e.altKey || typing(document.activeElement)) return;
  if ($('#cpOverlay.on')) return;
  const k = e.key.toLowerCase();
  if (e.key === 'Escape') {
    if ($('.pop')) { closePops(); return; }
    if ($('.w-drawer.on')) { $$('.w-drawer.on').forEach(d => d.classList.remove('on')); return; }
    if ($('.w.expanded')) return;
    if (root.dataset.wall === 'on') { setWall(false); return; }
    if (root.dataset.zen === 'on') { setZen(false); return; }
    return;
  }
  if (gPending && Date.now() - gPending < 1200) { gPending = 0; if (GMAP[k]) { e.preventDefault(); GO?.(GMAP[k]); } return; }
  if (k === 'g') { gPending = Date.now(); return; }
  if (e.key === '?') { e.preventDefault(); helpPop(); return; }
  if (/^[1-5]$/.test(e.key)) { GO?.(NUM[+e.key - 1]); return; }
  const act = { z: () => setZen(), f: () => setWall(), t: () => themePop($('#thmBtn')), d: toggleDarkLight, r: riskCalc, n: openCenter, w: () => openLayout(S.page), x: snapshot, m: () => $('#soundBtn')?.click() }[k];
  if (act) { e.preventDefault(); act(); }
}
export function snapshot() { const el = $('#page-' + S.page); if (el) savePNG(el, 'liquidity_' + S.page); }

// ------------------------------------------------------------------ status bar
function statusBar() {
  const main = $('.main'); if (!main || $('#sbar')) return;
  const sb = document.createElement('footer'); sb.className = 'sbar'; sb.id = 'sbar';
  sb.innerHTML = `<span class="sb-mode paper" id="sbMode">PAPER</span><span id="sbSrv"><span class="dot-live off"></span> server</span><span id="sbBot">bot —</span><span id="sbData">data —</span>
    <span id="sbKz">entry window —</span><span id="sbApi">dash api —</span><span class="grow" id="sbLast"></span><span id="sbClock">—</span><span><kbd>?</kbd> keys · <kbd>Ctrl K</kbd></span>`;
  main.appendChild(sb);
  const upd = () => {
    const s = L.live, h = s?.health || {}, now = Date.now() / 1000;
    const ad = s?.cfg?.adapter || 'paper';
    $('#sbMode').textContent = s?.cfg?.armed ? 'LIVE ARMED' : ad.toUpperCase();
    $('#sbMode').className = 'sb-mode ' + (ad === 'paper' && !s?.cfg?.armed ? 'paper' : '');
    $('#sbSrv').innerHTML = `<span class="dot-live ${L.online ? '' : L.online === false ? 'bad' : 'off'}"></span> ${L.online ? `<b>${fmtN(L.lat.at(-1)?.ms, 0)}</b> ms` : L.online === false ? 'offline' : 'server'}`;
    $('#sbBot').innerHTML = s ? `bot <b>${s.running ? esc(s.state?.model_state || 'running') : 'stopped'}</b>` : 'bot —';
    const age = h.data_age_s != null ? h.data_age_s + (L.liveAt ? now - L.liveAt : 0) : null;
    $('#sbData').innerHTML = age != null ? `data <b>${h.market_open === false ? 'closed' : dur(age, { short: true })}</b> ${esc(h.data_source || '')}` : 'data —';
    const kz = killzone(now);
    $('#sbKz').innerHTML = kz ? (kz.state === 'live' ? `<b style="color:var(--good)">${kz.kz.name} LIVE</b> ${dur(kz.secs)}` : `${kz.kz.name} in <b>${dur(kz.secs, { short: true })}</b>`) : '';
    const r = L.log?.find(x => x.type !== 'warn');
    $('#sbLast').textContent = r ? `${etStr(r.t)} ${r.text}` : '';
    const n = etNow(now);
    $('#sbClock').innerHTML = `<b>${etStr(now)}</b>:${String(n.p.s).padStart(2, '0')} ET · ${marketOpen(n) ? 'open' : 'closed'} · T−${LAUNCH_TS > now ? dur(LAUNCH_TS - now, { short: true }) : '0'}`;
  };
  setInterval(upd, 1000); onLive(upd);
  const api = async () => { const idx = await dashIndex(); $('#sbApi').innerHTML = idx ? `dash api <b>${idx.size}</b> live` : 'dash api <b>pending</b>'; };
  api(); setInterval(api, 60000);
}

// ------------------------------------------------------------------ top-bar buttons + page tools
function topButtons() {
  const tb = $('.tb-right'); if (!tb || $('#bellBtn')) return;
  const mk = (id, txt, title, fn) => { const b = document.createElement('button'); b.className = 'btn ghost icon'; b.id = id; b.innerHTML = txt; b.title = title; b.dataset.popAnchor = '1'; b.onclick = fn; return b; };
  const bell = mk('bellBtn', '🔔<span class="badge" id="bellBadge"></span>', 'Notifications (N)', () => openCenter()); bell.classList.add('bell'); bell.textContent = ''; bell.innerHTML = '<span aria-hidden="true">✉</span><span class="badge" id="bellBadge"></span>';
  const thm = mk('thmBtn', '◐', 'Theme switcher (T) · D toggles dark/light', (e) => themePop(e.currentTarget));
  const rc = mk('rcBtn', '⚖', 'Risk calculator (R)', riskCalc);
  const exit = document.createElement('button'); exit.className = 'btn ghost sm'; exit.id = 'zenExit'; exit.textContent = '✕ Exit'; exit.onclick = () => { setWall(false); setZen(false); };
  const sound = $('#soundBtn');
  tb.insertBefore(rc, sound); tb.insertBefore(thm, sound); tb.insertBefore(bell, sound); tb.appendChild(exit);
  if (!$('#wallBar')) { const wb = document.createElement('div'); wb.className = 'wall-bar'; wb.id = 'wallBar'; wb.innerHTML = '<i></i>'; document.body.appendChild(wb); }
}
function commandTools() {
  const pt = $('#cmdTools'); if (!pt) return;
  pt.innerHTML = `<span class="lbl">Command center</span><span class="spacer"></span>
    <button class="btn ghost sm" id="ctLayout" title="Show / hide / resize widgets (W)">⚙ Layout</button><button class="btn ghost sm" id="ctZen" title="Zen mode (Z)">◌ Zen</button>
    <button class="btn ghost sm" id="ctWall" title="TV-wall fullscreen (F)">▣ TV wall</button><button class="btn ghost sm" id="ctSnap" title="Snapshot PNG (X)">⇩ Snapshot</button>`;
  $('#ctLayout').onclick = () => openLayout('command'); $('#ctZen').onclick = () => setZen(); $('#ctWall').onclick = () => setWall(); $('#ctSnap').onclick = snapshot;
}

// ------------------------------------------------------------------ palette actions
export function paletteActions() {
  const page = S.page;
  const acts = [
    ['zen', 'Zen mode on / off', '◌', 'Z', () => setZen()], ['wall', 'TV-wall fullscreen', '▣', 'F', () => setWall()], ['dl', 'Toggle dark / light theme', '◐', 'D', toggleDarkLight],
    ['thm', 'Theme switcher', '◑', 'T', () => themePop($('#thmBtn'))], ['rc', 'Risk calculator', '⚖', 'R', riskCalc], ['nc', 'Notifications', '✉', 'N', openCenter],
    ['lay', `Customise ${page} layout`, '⚙', 'W', () => openLayout(page)], ['snap', 'Snapshot this page as PNG', '⇩', 'X', snapshot], ['keys', 'Keyboard shortcuts', '?', '?', helpPop],
    ['acct', 'Enter real MFFU account numbers', '✎', 'eval', () => { GO?.('command'); setTimeout(() => $('#ckEdit')?.click(), 80); }],
  ].map(([key, label, icon, hint, fn]) => ({ kind: 'action', key, label, icon, hint, do: fn }));
  const wid = defsFor(page).map(d => ({ kind: 'widget', key: 'w-' + d.id, label: `Widget: ${String(d.title).replace(/<[^>]+>|&amp;/g, (m) => m === '&amp;' ? '&' : '')}`, icon: '▦', hint: 'expand',
    do: () => { const c = d._card; if (!c) return; c.hidden = false; c.scrollIntoView({ behavior: 'smooth', block: 'center' }); setTimeout(() => expand(c, true), 350); } }));
  return [...acts, ...wid];
}

export function initUX(go) {
  GO = go;
  topButtons();
  statusBar();
  commandTools();
  document.addEventListener('keydown', onKey);
  root.dataset.zen = 'off'; root.dataset.wall = 'off';
}
