// Live View (owner 2026-10-28): one big full-screen chart with what the bots are doing drawn on it, one colour per
// strategy (Zlarior blue, ATLAS orange, Strategy 3 purple), a switch per strategy, a "What the bot is thinking" panel and
// the narrator's running feed. Dark and 3D by default ("make it look sick, very 3D"), one click to the white theme
// (remembered per browser). Read-only: GET /api/next/liveview (engine/liveview_api.py) every 3 s while the page is open.
// Nothing here talks to the bot's controls. F = full screen (only on this page), Esc leaves it.
// Drawing: ./liveviewchart.js. Two canvases: the chart (redrawn on new data / zoom / resize) and a light overlay that
// animates the live price and the trade lines and draws the crosshair (no full redraw per frame: no jank on the Surface).
// The dashboard's WebGL layer (fx3d.js) is off by default and only mounts its own scene kinds, so the depth here is
// canvas 2D + CSS (perspective, glass, glow); prefers-reduced-motion stops every animation and the card tilt.
// Page section is created here (no index.html change).
import { $, esc, store } from '../util.js';
import { drawChart, drawFx } from './liveviewchart.js';

const ID = 'liveview';
const pref = (k, d) => { try { return store.get(k, d); } catch { return d; } };
const save = (k, v) => { try { store.set(k, v); } catch { /* private window: per session only */ } };
const L = {
  d: null, busy: false, timer: null, tick: null, err: null, tf: pref('lv.tf', '1m'), theme: pref('lv.theme', 'dark') === 'light' ? 'light' : 'dark',
  on: Object.assign({ lit: true, atlas: true, scalp: true, structure: true }, pref('lv.on', {})),
  think: pref('lv.think', true), feed: pref('lv.feed', true), feedF: pref('lv.feedF', 'all'), important: pref('lv.imp', false),
  view: { n: null, end: 0 }, hover: null, seen: 0, at: 0, geo: null, raf: 0, lastFx: 0, fast: false,
};
const PAL = {
  dark: { lit: '#4b7a99', atlas: '#ff9a3d', scalp: '#c9a06a', sys: '#94a3b8', structure: '#e2e8f0' },
  light: { lit: '#4b7a99', atlas: '#ea580c', scalp: '#9c6b3c', sys: '#475569', structure: '#334155' },
};
const NAMES = { lit: 'Zlarior', atlas: 'ATLAS', scalp: 'BLITZ', sys: 'Bot', structure: 'Structure' };
// hidden bots (owner 2026-11-15, dashboard_view.json -> window.OLY_HIDDEN): a hidden BLITZ has no layer switch, legend, card or feed tab
const HIDB = () => !!(globalThis.OLY_HIDDEN && globalThis.OLY_HIDDEN.has('blitz'));
const col = (k) => (PAL[L.theme][k] || PAL[L.theme].sys);
const still = () => matchMedia('(prefers-reduced-motion: reduce)').matches;
const fmtPx = (x) => x == null || isNaN(x) ? '—' : Number(x).toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 2 });
const fmtUsd = (x, sign = true) => x == null || isNaN(x) ? '—' : (sign ? (x > 0 ? '+' : x < 0 ? '-' : '') : '') + '$' + Math.abs(Math.round(x)).toLocaleString('en-US');
const etHM = (t, sec) => new Date(t * 1000).toLocaleTimeString('en-US', { timeZone: 'America/New_York', hour: '2-digit', minute: '2-digit', ...(sec ? { second: '2-digit' } : {}), hour12: false });
function dur(s) {
  s = Math.max(0, Math.round(s));
  const d = Math.floor(s / 86400), h = Math.floor((s % 86400) / 3600), m = Math.floor((s % 3600) / 60), x = s % 60;
  return d ? `${d}d ${h}h` : h ? `${h}h ${String(m).padStart(2, '0')}m` : m ? `${m}m ${String(x).padStart(2, '0')}s` : `${x}s`;
}
const active = () => document.getElementById('page-' + ID)?.classList.contains('active');
const tick = (ok) => ok === true ? '<b class="lv-ok">✓</b>' : ok === false ? '<b class="lv-no">✗</b>' : '<b class="lv-wait">…</b>';

// ------------------------------------------------------------------ page section + stylesheet (no index.html change)
function ensure() {
  if (!document.querySelector('link[data-lv]')) {
    const l = document.createElement('link'); l.rel = 'stylesheet'; l.href = new URL('../../css/liveview.css?v=4', import.meta.url).href; l.dataset.lv = '1';
    document.head.appendChild(l);
  }
  if (document.getElementById('page-' + ID)) return;
  const ref = document.getElementById('page-cc') || document.querySelector('.page');
  const s = document.createElement('section'); s.className = 'page'; s.id = 'page-' + ID;
  s.innerHTML = '<div class="empty">Loading the Live View…</div>';
  (ref?.parentNode || document.querySelector('main') || document.body).appendChild(s);
}
ensure();

// ------------------------------------------------------------------ shell
function shell(el) {
  const sw = (k) => `<button type="button" class="lv-sw" data-lv-on="${k}" aria-pressed="${!!L.on[k]}" style="--c:${col(k)}"><i></i><span>${esc(NAMES[k])}</span></button>`;
  el.innerHTML = `<div class="lv-root" id="lvRoot" data-theme="${L.theme}">
    <header class="lv-bar">
      <div class="lv-title"><b>Live View</b><span class="lv-px mono" id="lvPx">—</span><span class="lv-src" id="lvSrc"></span></div>
      <div class="lv-ctrls">
        <div class="lv-seg" id="lvTf" role="group" aria-label="Timeframe">${['1m', '5m'].map((t) => `<button type="button" data-v="${t}" aria-pressed="${L.tf === t}">${t}</button>`).join('')}</div>
        <div class="lv-sws" role="group" aria-label="Strategies">${sw('lit')}${sw('atlas')}${HIDB() ? '' : sw('scalp')}${sw('structure')}</div>
        <button type="button" class="lv-btn" id="lvThinkB" aria-pressed="${L.think}" title="What the bot is thinking">🧠 Thinking</button>
        <button type="button" class="lv-btn" id="lvFeedB" aria-pressed="${L.feed}" title="The bot's running feed">Feed</button>
        <button type="button" class="lv-btn" id="lvTheme" title="Dark / light"></button>
        <button type="button" class="lv-btn lv-3d" data-goto="holo" title="Open the Holodeck: the day in 3D, every fill exact, what each bot is thinking">3D</button>
        <button type="button" class="lv-btn lv-fs" id="lvFs" title="Full screen (F)">⛶ <span>Full screen</span> <kbd>F</kbd></button>
      </div>
    </header>
    <div class="lv-main ${L.think ? '' : 'nothink'}" id="lvMain">
      <div class="lv-chartwrap" id="lvWrap"><canvas id="lvCv" aria-label="Live NQ chart"></canvas><canvas id="lvFx" aria-hidden="true"></canvas>
        <div class="lv-ohlc mono" id="lvOhlc"></div><div class="lv-legend" id="lvLeg"></div><div class="lv-note" id="lvNote" hidden></div>
        <div class="lv-zoom"><button type="button" class="lv-btn sm" id="lvZin" title="Zoom in">+</button><button type="button" class="lv-btn sm" id="lvZout" title="Zoom out">−</button><button type="button" class="lv-btn sm" id="lvLive" title="Back to now">Now</button></div></div>
      <aside class="lv-think" id="lvThink" aria-label="What the bot is thinking"></aside>
    </div>
    <section class="lv-feed" id="lvFeed" ${L.feed ? '' : 'hidden'} aria-label="Bot feed">
      <div class="lv-ticker" id="lvTicker" aria-hidden="true"><div class="lv-ticker-r" id="lvTickR"></div></div>
      <div class="lv-feed-h"><b>What the bot says</b>
        <div class="lv-seg sm" id="lvFF">${[['all', 'All'], ['lit', 'Zlarior'], ['atlas', 'ATLAS'], ['scalp', 'BLITZ'], ['sys', 'Bot']].filter(([k]) => !(k === 'scalp' && HIDB())).map(([k, l]) => `<button type="button" data-v="${k}" aria-pressed="${L.feedF === k}">${l}</button>`).join('')}</div>
        <label class="lv-chk"><input type="checkbox" id="lvImp" ${L.important ? 'checked' : ''}> important only</label>
        <span class="lv-muted" id="lvPushes"></span></div>
      <ol class="lv-feed-l" id="lvFeedL"></ol>
    </section>
  </div>`;
  themeBtn();
  wire(el);
}
function themeBtn() { const b = $('#lvTheme'); if (b) b.textContent = L.theme === 'dark' ? '☀ Light' : '☾ Dark'; }
function setTheme(t) {
  L.theme = t; save('lv.theme', t);
  $('#lvRoot').dataset.theme = t; themeBtn();
  document.querySelectorAll('#lvRoot [data-lv-on]').forEach((b) => b.style.setProperty('--c', col(b.dataset.lvOn)));
  paint(); think(); feed();
}

function wire(el) {
  $('#lvTf', el).onclick = (e) => { const b = e.target.closest('button[data-v]'); if (!b) return; L.tf = b.dataset.v; save('lv.tf', L.tf); L.view = { n: null, end: 0 }; $$set('#lvTf button', (x) => x.setAttribute('aria-pressed', x.dataset.v === L.tf)); load(true); };
  el.querySelectorAll('[data-lv-on]').forEach((b) => { b.onclick = () => { const k = b.dataset.lvOn; L.on[k] = !L.on[k]; save('lv.on', L.on); b.setAttribute('aria-pressed', L.on[k]); paint(); think(); }; });
  $('#lvThinkB', el).onclick = (e) => { L.think = !L.think; save('lv.think', L.think); e.currentTarget.setAttribute('aria-pressed', L.think); $('#lvMain').classList.toggle('nothink', !L.think); think(); requestAnimationFrame(() => paint()); };
  $('#lvFeedB', el).onclick = (e) => { L.feed = !L.feed; save('lv.feed', L.feed); e.currentTarget.setAttribute('aria-pressed', L.feed); $('#lvFeed').hidden = !L.feed; requestAnimationFrame(() => paint()); };
  $('#lvTheme', el).onclick = () => setTheme(L.theme === 'dark' ? 'light' : 'dark');
  $('#lvFF', el).onclick = (e) => { const b = e.target.closest('button[data-v]'); if (!b) return; L.feedF = b.dataset.v; save('lv.feedF', L.feedF); $$set('#lvFF button', (x) => x.setAttribute('aria-pressed', x.dataset.v === L.feedF)); feed(); };
  $('#lvImp', el).onchange = (e) => { L.important = e.target.checked; save('lv.imp', L.important); feed(); };
  $('#lvFs', el).onclick = toggleFs;
  $('#lvZin', el).onclick = () => zoom(1 / 1.4);
  $('#lvZout', el).onclick = () => zoom(1.4);
  $('#lvLive', el).onclick = () => { L.view = { n: null, end: 0 }; paint(); };
  const cv = $('#lvCv', el);
  cv.addEventListener('wheel', (e) => { e.preventDefault(); zoom(e.deltaY > 0 ? 1.15 : 1 / 1.15); }, { passive: false });
  let drag = null, dragRaf = 0;
  cv.addEventListener('pointerdown', (e) => { drag = { x: e.clientX, end: L.view.end }; cv.setPointerCapture(e.pointerId); });
  const endDrag = () => { if (drag) { drag = null; L.fast = false; paint(); } };
  cv.addEventListener('pointerup', endDrag); cv.addEventListener('pointercancel', endDrag);
  cv.addEventListener('pointermove', (e) => {
    const r = cv.getBoundingClientRect();
    L.hover = { x: e.clientX - r.left, y: e.clientY - r.top };
    if (drag && L.geo) {
      const di = Math.round((e.clientX - drag.x) / L.geo.bw);
      const n = (L.d?.bars || []).length;
      const nv = Math.max(0, Math.min(n - 10, drag.end + di));
      if (nv !== L.view.end) { L.view.end = nv; L.fast = true; if (!dragRaf) dragRaf = requestAnimationFrame(() => { dragRaf = 0; paint(); }); }
      return;
    }
    fx(true);
  });
  cv.addEventListener('pointerleave', () => { L.hover = null; fx(true); });
  cv.addEventListener('dblclick', () => { L.view = { n: null, end: 0 }; paint(); });
  new ResizeObserver(() => paint()).observe($('#lvWrap', el));
  // the cards tilt a little towards the pointer (CSS 3D); off with prefers-reduced-motion
  const th = $('#lvThink', el);
  th.addEventListener('pointermove', (e) => {
    if (still()) return;
    const c = e.target.closest('.lv-card'); if (!c) return;
    const r = c.getBoundingClientRect();
    c.style.setProperty('--ry', `${((e.clientX - r.left) / r.width - 0.5) * 5}deg`);
    c.style.setProperty('--rx', `${-((e.clientY - r.top) / r.height - 0.5) * 4}deg`);
    c.classList.add('tilt');
  });
  th.addEventListener('pointerout', (e) => { const c = e.target.closest('.lv-card'); if (c && !c.contains(e.relatedTarget)) { c.classList.remove('tilt'); c.style.removeProperty('--rx'); c.style.removeProperty('--ry'); } });
}
const $$set = (sel, fn) => document.querySelectorAll(sel).forEach(fn);
function zoom(f) {
  const n = (L.d?.bars || []).length; if (!n) return;
  const cur = L.view.n || L.geo?.n || Math.min(n, L.tf === '1m' ? 120 : 200);
  L.view.n = Math.max(20, Math.min(n, Math.round(cur * f)));
  paint();
}

// ------------------------------------------------------------------ full screen (Fullscreen API; a CSS fallback where it is missing)
function isFs() { return document.fullscreenElement === $('#lvRoot') || $('#lvRoot')?.classList.contains('lv-max'); }
function toggleFs() {
  const r = $('#lvRoot'); if (!r) return;
  if (document.fullscreenElement) { document.exitFullscreen?.(); return; }
  if (r.classList.contains('lv-max')) { r.classList.remove('lv-max'); fsLabel(); paint(); return; }
  if (r.requestFullscreen) r.requestFullscreen().catch(() => { r.classList.add('lv-max'); fsLabel(); paint(); });
  else { r.classList.add('lv-max'); fsLabel(); paint(); }
}
function fsLabel() { const b = $('#lvFs'); if (b) b.querySelector('span').textContent = isFs() ? 'Exit full screen' : 'Full screen'; }
document.addEventListener('fullscreenchange', () => { fsLabel(); setTimeout(paint, 60); });
window.addEventListener('keydown', (e) => {
  if (!active() || e.ctrlKey || e.metaKey || e.altKey) return;
  const a = document.activeElement;
  if (a && (a.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(a.tagName))) return;
  if (e.key === 'f' || e.key === 'F') { e.preventDefault(); e.stopImmediatePropagation(); toggleFs(); }
  else if (e.key === 'Escape' && $('#lvRoot')?.classList.contains('lv-max')) { $('#lvRoot').classList.remove('lv-max'); fsLabel(); paint(); e.stopImmediatePropagation(); }
}, true);

// ------------------------------------------------------------------ data
async function load(force) {
  if (L.busy && !force) return;
  L.busy = true;
  try {
    const r = await fetch(`/api/next/liveview?tf=${encodeURIComponent(L.tf)}`, { cache: 'no-store' });
    const d = await r.json().catch(() => ({ error: 'HTTP ' + r.status }));
    if (!r.ok || d.error) throw new Error(d.error || 'HTTP ' + r.status);
    L.d = d; L.err = null; L.at = Date.now();
  } catch (e) { L.err = e.message; }
  finally { L.busy = false; }
  if (active()) { paint(); think(); feed(); top(); }
}

function top() {
  const d = L.d; if (!d) { if (L.err) $('#lvSrc').innerHTML = `<b class="lv-no">●</b> ${esc(L.err)}`; return; }
  $('#lvPx').textContent = `NQ ${fmtPx(d.price)}`;
  const stale = d.feed?.stale, live = d.running && !stale;
  const dot = L.err ? '<b class="lv-no lv-dot">●</b> connection lost · ' : stale ? '<b class="lv-no lv-dot">●</b> FEED STALE · ' : live ? '<b class="lv-ok lv-dot live">●</b> live · ' : '<b class="lv-wait lv-dot">●</b> bot stopped · ';
  $('#lvSrc').innerHTML = `${dot}${esc(d.source || '')} · ${esc(d.tf)} · ${etHM(d.t, true)} ET${d.account ? ' · ' + esc(d.account) : ''}`;
}

// ------------------------------------------------------------------ chart: static layer + animated overlay
function paint() {
  const cv = $('#lvCv'); if (!cv || !active()) return;
  const d = L.d;
  if (!d) return;
  L.geo = drawChart(cv, d, { on: L.on, view: L.view, tf: L.tf, theme: L.theme, fast: L.fast });
  document.querySelectorAll('#lvRoot [data-lv-on="structure"]').forEach((b) => { b.hidden = !d.structure; });
  const leg = ['lit', 'atlas', 'scalp'].filter((k) => L.on[k] && !(k === 'scalp' && HIDB())).map((k) => {
    const s = d.strategies?.[k] || {};
    const what = k === 'lit' ? 'levels · setup · position' : k === 'atlas' ? 'EMA 21 / 50 · S/R · plans · position' : (s.placeholder ? 'not running yet' : 'band · signals · PAPER position');
    return `<span style="--c:${col(k)}"><i></i>${esc(k === 'scalp' ? 'BLITZ (paper)' : s.name || NAMES[k])} <em>${esc(what)}</em></span>`;
  }).join('');
  $('#lvLeg').innerHTML = leg;
  const note = $('#lvNote');
  const msg = !d.bars?.length ? 'No bars yet: the bot shows its NinjaTrader bars here once it runs.' : '';
  note.hidden = !msg; note.textContent = msg;
  fx(true);
  loop();
}
function fx(readout) {
  const c = $('#lvFx'); if (!c || !L.d) return;
  const r = drawFx(c, L.geo, { t: performance.now(), hover: L.hover, still: still() });
  if (readout) {
    const d = L.d, b = r.hoverBar || (d.bars || [])[d.bars.length - 1];
    $('#lvOhlc').innerHTML = b ? `<span>${etHM(b[0])} ET</span> O <b>${fmtPx(b[1])}</b> H <b>${fmtPx(b[2])}</b> L <b>${fmtPx(b[3])}</b> C <b class="${b[4] >= b[1] ? 'lv-ok' : 'lv-no'}">${fmtPx(b[4])}</b>${r.hoverPx != null ? ` <span class="lv-muted">· cursor ${fmtPx(r.hoverPx)}</span>` : ''}` : '';
  }
}
function loop() {                       // ~30 fps on the overlay only, while the page is on screen
  if (L.raf || still()) return;
  const step = (ts) => {
    if (!active() || document.hidden) { L.raf = 0; return; }
    if (ts - L.lastFx > 33) { L.lastFx = ts; fx(false); }
    L.raf = requestAnimationFrame(step);
  };
  L.raf = requestAnimationFrame(step);
}
document.addEventListener('visibilitychange', () => { if (!document.hidden && active()) loop(); });

// ------------------------------------------------------------------ thinking panel
function stepper(stages) {
  if (!stages?.length) return '';
  const cur = stages.find((s) => s.state === 'now');
  return `<ol class="lv-steps">${stages.map((s) => `<li class="${esc(s.state)}" title="${esc(s.n + '. ' + s.label)}"><i>${s.n}</i></li>`).join('')}</ol>`
    + (cur ? `<div class="lv-stepnow">Step ${cur.n} of ${stages.length}: <b>${esc(cur.label)}</b></div>` : '');
}
function checks(list) {
  if (!list?.length) return '';
  return `<ul class="lv-checks">${list.map((c) => `<li>${tick(c.ok)}<div><b>${esc(c.label)}</b>${c.text ? `<small>${esc(c.text)}</small>` : ''}</div></li>`).join('')}</ul>`;
}
const cd = (t, label) => t ? `<span class="lv-cd" data-cd="${t}" data-l="${esc(label)}">${esc(label)} ${dur(t - nowT())}</span>` : '';
const nowT = () => L.d ? L.d.t + Math.round((Date.now() - L.at) / 1000) : Date.now() / 1000;
function posBox(p, color, real) {
  if (!p) return '';
  const q = p.qty;
  const lines = [`<b>${esc(p.side || '')}${q ? ` ${q} MNQ` : ''}</b> @ ${fmtPx(p.entry)}${p.account ? ` · ${esc(p.account)}` : ''}`];
  if (real && q) {
    lines.push(`now <b class="${(p.unrealized_usd || 0) >= 0 ? 'lv-ok' : 'lv-no'}">${fmtUsd(p.unrealized_usd)}</b>${p.unrealized_r_now != null ? ` (${p.unrealized_r_now >= 0 ? '+' : ''}${Number(p.unrealized_r_now).toFixed(2)}R)` : ''}`);
    const d = p.dir || (p.side === 'LONG' ? 1 : -1);
    if (p.stop != null && p.entry != null) lines.push(`stop ${fmtPx(p.stop)} = <b class="lv-no">${fmtUsd((p.stop - p.entry) * d * 2 * q)}</b>`);
    if (p.target != null && p.entry != null) lines.push(`target ${fmtPx(p.target)} = <b class="lv-ok">${fmtUsd((p.target - p.entry) * d * 2 * q)}</b>`);
  } else lines.push('<span class="lv-muted">model trade, not routed on an account: no real size</span>');
  return `<div class="lv-pos" style="--c:${color}">${lines.map((x) => `<div>${x}</div>`).join('')}</div>`;
}
function think() {
  const el = $('#lvThink'); if (!el || !L.d) return;
  if (!L.think) { el.innerHTML = ''; return; }
  const open = new Set([...el.querySelectorAll('details[open]')].map((x) => x.dataset.k));   // keep what the owner unfolded
  const S = L.d.strategies || {};
  const out = [];
  const lit = S.lit;
  if (lit && L.on.lit) {
    const t = lit.thinking || {};
    out.push(`<article class="lv-card" style="--c:${col('lit')}"><header><i></i><b>Zlarior</b><span class="lv-pill">${esc(t.stage?.label || '—')}${t.stage?.n ? ` · ${t.stage.n}/10` : ''}</span></header>
      ${lit.error ? `<p class="lv-no">${esc(lit.error)}</p>` : ''}
      ${stepper(t.stages)}
      <p class="lv-head">${esc(t.headline || 'Waiting for the first Brain snapshot')}</p>
      ${t.detail && t.detail !== t.headline ? `<p class="lv-muted small">${esc(t.detail)}</p>` : ''}
      <div class="lv-chips">${(t.distance || []).map((x) => `<span class="lv-chip"><b class="mono">${fmtPx(x.pts)}</b> pts ${esc(x.label)}</span>`).join('')}
        ${t.stop_preview ? `<span class="lv-chip">stop would be <b class="mono">${fmtPx(t.stop_preview)}</b> pts</span>` : ''}</div>
      <div class="lv-chips">${t.window ? `<span class="lv-chip ${t.window.open ? 'on' : ''}">${cd(t.window.t, t.window.open ? 'window closes in' : 'window opens in')}</span>` : ''}
        ${t.expires ? `<span class="lv-chip on">${cd(t.expires.t, 'limit expires in')}</span>` : ''}</div>
      ${posBox(lit.position, col('lit'), lit.position && !lit.position.paper)}
      ${checks(t.checklist)}
    </article>`);
  }
  const at = S.atlas;
  if (at && L.on.atlas) {
    const mem = (at.members || []).filter((m) => !m.candidate), cand = (at.members || []).filter((m) => m.candidate);
    const row = (m) => `<details class="lv-mem" data-k="${esc(m.key)}" ${open.has(m.key) ? 'open' : ''}><summary><b>${esc(m.short)}</b><span class="lv-pill">${esc(m.stage || '—')}</span>${m.window ? `<span class="lv-muted small">${cd(m.window.t, m.window.open ? 'closes in' : 'opens in')}</span>` : ''}
        <p>${esc(m.text || '')}</p></summary>${checks(m.checks)}${m.first_fail ? `<p class="lv-muted small">first rule that fails: <b>${esc(m.first_fail)}</b></p>` : ''}</details>`;
    out.push(`<article class="lv-card" style="--c:${col('atlas')}"><header><i></i><b>ATLAS</b><span class="lv-pill">${esc(at.account || 'paper')}</span></header>
      ${at.error ? `<p class="lv-no">${esc(at.error)}</p>` : ''}${at.empty ? `<p class="lv-muted">${esc(at.empty)}</p>` : ''}
      ${posBox(at.position, col('atlas'), !!at.position)}
      ${mem.map(row).join('')}
      ${cand.length ? `<details class="lv-mem lv-cand" data-k="_cand" ${open.has('_cand') ? 'open' : ''}><summary><b>Other paper strategies</b><span class="lv-pill">research · paper</span></summary>${cand.map(row).join('')}</details>` : ''}
    </article>`);
  }
  const sc = S.scalp;
  if (sc && L.on.scalp && !HIDB()) {
    const th = sc.thinking || {};
    const pp = (p) => p ? `<div><b>${esc(p.ledger)}</b>: ${esc(p.side)} ${p.qty ? `${p.qty} MNQ` : '(no size)'} @ ${fmtPx(p.entry)} · now <b class="${(p.unrealized_usd || 0) >= 0 ? 'lv-ok' : 'lv-no'}">${fmtUsd(p.unrealized_usd)}</b> · stop ${fmtPx(p.stop)} = <b class="${(p.stop_usd || 0) >= 0 ? 'lv-ok' : 'lv-no'}">${fmtUsd(p.stop_usd)}</b></div>` : '';
    const p1 = sc.position, p2 = sc.position50 && (!p1 || sc.position50.ledger !== p1.ledger) ? sc.position50 : null;
    const sigs = (sc.signals || []).filter((x) => !x.ledger).slice(-4).reverse();
    out.push(`<article class="lv-card" style="--c:${col('scalp')}"><header><i></i><b>BLITZ</b><span class="lv-pill">${sc.placeholder ? 'not running' : 'PAPER · never routed'}</span></header>
      ${sc.error ? `<p class="lv-no">${esc(sc.error)}</p>` : ''}
      <p class="lv-head">${esc(th.headline || sc.text || '')}</p>
      ${p1 || p2 ? `<div class="lv-pos lv-paper" style="--c:${col('scalp')}"><div class="lv-paper-t">PAPER position · simulated accounts</div>${pp(p1)}${pp(p2)}</div>` : ''}
      ${th.eval ? `<p class="small">${esc(th.eval)}</p>` : ''}${th.funded50 ? `<p class="small">${esc(th.funded50)}</p>` : ''}
      ${sigs.length ? `<ul class="lv-checks">${sigs.map((x) => `<li>${tick(x.taken ? true : null)}<div><b>${esc(new Date(x.t * 1000).toLocaleTimeString('en-US', { timeZone: 'America/New_York', hour: '2-digit', minute: '2-digit', hour12: false }))} ${esc(x.side)} signal</b><small>${esc(x.text)}</small></div></li>`).join('')}</ul>` : ''}
      ${sc.placeholder ? `<p class="lv-muted">${esc(sc.text || '')}</p>` : ''}
      <p class="small lv-bzgo"><a class="lv-bzlink" data-goto="blitz" style="display:inline-flex;align-items:center;min-height:44px;color:inherit;font-weight:650;text-decoration:none;cursor:pointer">Open BLITZ: band, trades, results, go live ›</a></p></article>`);
  }
  // market structure (2026-10-29, liveview_api.view() "structure" when present): the summary + each frame's trend / last break
  const st = L.d.structure;
  if (st && typeof st === 'object' && L.on.structure !== false) {
    const fr = st.frames || {}, up = (v) => v === 1 || /up|bull|long/i.test(String(v)), hmS = (t) => (t ? new Date(t * 1000).toLocaleTimeString('en-US', { timeZone: 'America/New_York', hour: '2-digit', minute: '2-digit', hour12: false }) : '');
    const chip = (k) => { const F = fr[k]; if (!F) return ''; const e = F.last_event, tr = String(F.trend || '—');
      return `<li><b>${esc(k)}</b><span class="lv-pill ${up(tr) ? 'lv-ok' : /down|bear|short/i.test(tr) ? 'lv-no' : ''}">${esc(tr)}</span>${e ? `<small>${esc(e.kind || 'BOS')} ${up(e.dir) ? '▲' : '▼'} ${fmtPx(e.price)}${e.t ? ' · ' + hmS(e.t) : ''}</small>` : '<small>no break yet</small>'}</li>`; };
    const z = st.zone, pools = (Array.isArray(st.pools) ? st.pools : []).filter((p) => p && !p.swept && p.price != null);
    const bsl = pools.filter((p) => /^b/i.test(p.side || '')).sort((a, b) => a.price - b.price)[0], ssl = pools.filter((p) => /^s/i.test(p.side || '')).sort((a, b) => b.price - a.price)[0];
    out.push(`<article class="lv-card lv-struct" style="--c:${col('structure')}"><header><i></i><b>Market structure</b><span class="lv-pill">${esc(z ? (z.premium ? 'in premium' : 'in discount') : 'structure')}</span></header>
      ${st.summary ? `<p class="lv-head">${esc(st.summary)}</p>` : ''}<ul class="lv-frames">${['5m', '15m', '1h'].map(chip).join('')}</ul>
      ${z && z.lo != null && z.hi != null ? `<p class="small">Range ${fmtPx(z.lo)} – ${fmtPx(z.hi)} · equilibrium ${fmtPx(z.eq != null ? z.eq : (z.lo + z.hi) / 2)}</p>` : ''}
      ${(() => { const ps = st.per_strategy && typeof st.per_strategy === 'object' ? st.per_strategy : {}, nm = { lit: 'Zlarior', atlas: 'ATLAS', scalp: 'BLITZ', blitz: 'BLITZ' };
        const rows = Object.entries(ps).map(([k, v]) => [nm[k] || k, typeof v === 'string' ? v : v && typeof v === 'object' ? (v.text || v.note || v.summary || v.headline || '') : '']).filter((r) => r[1]);
        return rows.length ? `<ul class="lv-frames lv-ps">${rows.map(([n, t]) => `<li><b>${esc(n)}</b><small>${esc(String(t).slice(0, 160))}</small></li>`).join('')}</ul>` : ''; })()}
      ${bsl || ssl ? `<p class="small">Liquidity: ${bsl ? `buy side ${fmtPx(bsl.price)}${bsl.label ? ' (' + esc(bsl.label) + ')' : ''}` : ''}${bsl && ssl ? ' · ' : ''}${ssl ? `sell side ${fmtPx(ssl.price)}${ssl.label ? ' (' + esc(ssl.label) + ')' : ''}` : ''}</p>` : ''}</article>`);
  }
  el.innerHTML = out.join('') || '<p class="lv-muted">Switch a strategy on to see what it is thinking.</p>';
}

// ------------------------------------------------------------------ feed: glowing ticker (the newest) + the list
function feed() {
  const ol = $('#lvFeedL'); if (!ol || !L.d) return;
  const all = L.d.narrator || [];
  let rows = all;
  if (L.feedF !== 'all') rows = rows.filter((m) => m.strat === L.feedF);
  if (L.important) rows = rows.filter((m) => m.level !== 'dim');
  const newest = Math.max(0, ...all.map((m) => m.id));
  const fresh = L.seen ? newest > L.seen : false;
  ol.innerHTML = rows.slice(0, 100).map((m) => `<li class="lv-m ${esc(m.level)} ${L.seen && m.id > L.seen ? 'new' : ''}" style="--c:${col(m.strat)}">
    <time class="mono">${esc(m.hm || '')}</time><i></i><div><b>${esc(m.title)}</b> <span>${esc(m.text)}</span></div></li>`).join('') || '<li class="lv-muted">Nothing yet today.</li>';
  const tk = all.filter((m) => m.level !== 'dim').slice(0, 8);
  const item = (m) => `<span class="lv-tk ${esc(m.level)}" style="--c:${col(m.strat)}"><i></i><time>${esc(m.hm || '')}</time> <b>${esc(m.title)}</b> ${esc(m.text.length > 110 ? m.text.slice(0, 108) + '…' : m.text)}</span>`;
  const sig = tk.map((m) => m.id).join(',');
  if (sig !== L.tickSig) {           // rebuilt only when the newest messages change (the scroll keeps running)
    L.tickSig = sig;
    const strip = tk.map(item).join('');
    $('#lvTickR').innerHTML = strip ? strip + strip : '<span class="lv-tk"><b>The bot is quiet</b> nothing important yet today</span>';
    $('#lvTickR').style.animationDuration = `${Math.max(30, tk.length * 9)}s`;
  }
  if (fresh || !L.seen) L.seen = newest;
  const pk = L.d.push_kinds || {};
  const on = Object.values(pk).filter((x) => x.on).map((x) => x.label);
  $('#lvPushes').textContent = on.length ? `phone push: ${on.join(', ')}` : 'phone push: off';
}

function countdowns() {
  document.querySelectorAll('#page-liveview [data-cd]').forEach((s) => { s.textContent = `${s.dataset.l} ${dur(+s.dataset.cd - nowT())}`; });
}

export const liveview = {
  show: () => {
    ensure();
    window.LE = Object.assign(window.LE || {}, { liveview: { load: () => load(true), state: L, theme: setTheme } });   // app.js sets window.LE after the imports
    const el = document.getElementById('page-' + ID);
    if (!el.querySelector('#lvRoot')) shell(el);
    load(true);
    clearInterval(L.timer); clearInterval(L.tick);
    L.timer = setInterval(() => { if (!active()) { clearInterval(L.timer); return; } if (!document.hidden) load(false); }, 3000);
    L.tick = setInterval(() => { if (!active()) { clearInterval(L.tick); return; } countdowns(); }, 1000);
  },
};
