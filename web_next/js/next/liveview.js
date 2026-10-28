// Live View (owner 2026-10-28): one big full-screen chart on a WHITE background with what the bots are doing drawn on it,
// one colour per strategy (Zlarior blue, ATLAS orange, Strategy 3 purple), a switch per strategy, a "What the bot is
// thinking" panel and the narrator's running feed. Read-only: GET /api/next/liveview (engine/liveview_api.py) every 3 s
// while the page is open. Nothing here talks to the bot's controls. F = full screen (only on this page), Esc leaves it.
// Drawing: ./liveviewchart.js (canvas). Page section is created here (no index.html change).
import { $, esc, store } from '../util.js';
import { drawChart } from './liveviewchart.js';

const ID = 'liveview';
const L = {
  d: null, busy: false, timer: null, tick: null, err: null, tf: store.get('lv.tf', '1m'),
  on: Object.assign({ lit: true, atlas: true, scalp: true }, store.get('lv.on', {})),
  think: store.get('lv.think', true), feed: store.get('lv.feed', true), feedF: store.get('lv.feedF', 'all'), important: store.get('lv.imp', false),
  view: { n: null, end: 0 }, hover: null, seen: 0, at: 0,
};
const STRAT = { lit: ['Zlarior', '#2563eb'], atlas: ['ATLAS', '#ea580c'], scalp: ['Strategy 3', '#7c3aed'], sys: ['Bot', '#475569'] };
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
    const l = document.createElement('link'); l.rel = 'stylesheet'; l.href = new URL('../../css/liveview.css?v=1', import.meta.url).href; l.dataset.lv = '1';
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
  const sw = (k) => `<button type="button" class="lv-sw" data-lv-on="${k}" aria-pressed="${!!L.on[k]}" style="--c:${STRAT[k][1]}"><i></i><span>${esc(STRAT[k][0])}</span></button>`;
  el.innerHTML = `<div class="lv-root" id="lvRoot">
    <header class="lv-bar">
      <div class="lv-title"><b>Live View</b><span class="lv-px mono" id="lvPx">—</span><span class="lv-src" id="lvSrc"></span></div>
      <div class="lv-ctrls">
        <div class="lv-seg" id="lvTf" role="group" aria-label="Timeframe">${['1m', '5m'].map((t) => `<button type="button" data-v="${t}" aria-pressed="${L.tf === t}">${t}</button>`).join('')}</div>
        <div class="lv-sws" role="group" aria-label="Strategies">${sw('lit')}${sw('atlas')}${sw('scalp')}</div>
        <button type="button" class="lv-btn" id="lvThinkB" aria-pressed="${L.think}" title="What the bot is thinking">🧠 Thinking</button>
        <button type="button" class="lv-btn" id="lvFeedB" aria-pressed="${L.feed}" title="The bot's running feed">Feed</button>
        <button type="button" class="lv-btn lv-fs" id="lvFs" title="Full screen (F)">⛶ <span>Full screen</span> <kbd>F</kbd></button>
      </div>
    </header>
    <div class="lv-main ${L.think ? '' : 'nothink'}" id="lvMain">
      <div class="lv-chartwrap" id="lvWrap"><canvas id="lvCv" aria-label="Live NQ chart"></canvas>
        <div class="lv-ohlc mono" id="lvOhlc"></div><div class="lv-legend" id="lvLeg"></div><div class="lv-note" id="lvNote" hidden></div>
        <div class="lv-zoom"><button type="button" class="lv-btn sm" id="lvZin" title="Zoom in">+</button><button type="button" class="lv-btn sm" id="lvZout" title="Zoom out">−</button><button type="button" class="lv-btn sm" id="lvLive" title="Back to now">Now</button></div></div>
      <aside class="lv-think" id="lvThink" aria-label="What the bot is thinking"></aside>
    </div>
    <section class="lv-feed" id="lvFeed" ${L.feed ? '' : 'hidden'} aria-label="Bot feed">
      <div class="lv-feed-h"><b>What the bot says</b>
        <div class="lv-seg sm" id="lvFF">${[['all', 'All'], ['lit', 'Zlarior'], ['atlas', 'ATLAS'], ['sys', 'Bot']].map(([k, l]) => `<button type="button" data-v="${k}" aria-pressed="${L.feedF === k}">${l}</button>`).join('')}</div>
        <label class="lv-chk"><input type="checkbox" id="lvImp" ${L.important ? 'checked' : ''}> important only</label>
        <span class="lv-muted" id="lvPushes"></span></div>
      <ol class="lv-feed-l" id="lvFeedL"></ol>
    </section>
  </div>`;
  wire(el);
}

function wire(el) {
  $('#lvTf', el).onclick = (e) => { const b = e.target.closest('button[data-v]'); if (!b) return; L.tf = b.dataset.v; store.set('lv.tf', L.tf); L.view = { n: null, end: 0 }; $$set('#lvTf button', (x) => x.setAttribute('aria-pressed', x.dataset.v === L.tf)); load(true); };
  el.querySelectorAll('[data-lv-on]').forEach((b) => { b.onclick = () => { const k = b.dataset.lvOn; L.on[k] = !L.on[k]; store.set('lv.on', L.on); b.setAttribute('aria-pressed', L.on[k]); paint(); think(); }; });
  $('#lvThinkB', el).onclick = (e) => { L.think = !L.think; store.set('lv.think', L.think); e.currentTarget.setAttribute('aria-pressed', L.think); $('#lvMain').classList.toggle('nothink', !L.think); requestAnimationFrame(paint); };
  $('#lvFeedB', el).onclick = (e) => { L.feed = !L.feed; store.set('lv.feed', L.feed); e.currentTarget.setAttribute('aria-pressed', L.feed); $('#lvFeed').hidden = !L.feed; requestAnimationFrame(paint); };
  $('#lvFF', el).onclick = (e) => { const b = e.target.closest('button[data-v]'); if (!b) return; L.feedF = b.dataset.v; store.set('lv.feedF', L.feedF); $$set('#lvFF button', (x) => x.setAttribute('aria-pressed', x.dataset.v === L.feedF)); feed(); };
  $('#lvImp', el).onchange = (e) => { L.important = e.target.checked; store.set('lv.imp', L.important); feed(); };
  $('#lvFs', el).onclick = toggleFs;
  $('#lvZin', el).onclick = () => zoom(1 / 1.4);
  $('#lvZout', el).onclick = () => zoom(1.4);
  $('#lvLive', el).onclick = () => { L.view = { n: null, end: 0 }; paint(); };
  const cv = $('#lvCv', el);
  cv.addEventListener('wheel', (e) => { e.preventDefault(); zoom(e.deltaY > 0 ? 1.15 : 1 / 1.15); }, { passive: false });
  let drag = null;
  cv.addEventListener('pointerdown', (e) => { drag = { x: e.clientX, end: L.view.end }; cv.setPointerCapture(e.pointerId); });
  cv.addEventListener('pointerup', () => { drag = null; });
  cv.addEventListener('pointermove', (e) => {
    const r = cv.getBoundingClientRect();
    if (drag && L.geo) {
      const di = Math.round((e.clientX - drag.x) / L.geo.bw);
      const n = (L.d?.bars || []).length;
      L.view.end = Math.max(0, Math.min(n - 10, drag.end + di));
      paint(); return;
    }
    L.hover = { x: e.clientX - r.left, y: e.clientY - r.top }; paint(true);
  });
  cv.addEventListener('pointerleave', () => { L.hover = null; paint(true); });
  cv.addEventListener('dblclick', () => { L.view = { n: null, end: 0 }; paint(); });
  new ResizeObserver(() => paint()).observe($('#lvWrap', el));
}
const $$set = (sel, fn) => document.querySelectorAll(sel).forEach(fn);
function zoom(f) {
  const n = (L.d?.bars || []).length; if (!n) return;
  const cur = L.view.n || L.geo?.n || Math.min(n, L.tf === '1m' ? 180 : 288);
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
  const dot = L.err ? '<b class="lv-no">●</b> connection lost · ' : stale ? '<b class="lv-no">●</b> FEED STALE · ' : live ? '<b class="lv-ok">●</b> live · ' : '<b class="lv-wait">●</b> bot stopped · ';
  $('#lvSrc').innerHTML = `${dot}${esc(d.source || '')} · ${esc(d.tf)} · ${etHM(d.t, true)} ET${d.account ? ' · ' + esc(d.account) : ''}`;
}

// ------------------------------------------------------------------ chart
function paint() {
  const cv = $('#lvCv'); if (!cv || !active()) return;
  const d = L.d;
  if (!d) return;
  L.geo = drawChart(cv, d, { on: L.on, view: L.view, hover: L.hover, tf: L.tf });
  const leg = Object.keys(STRAT).filter((k) => k !== 'sys' && L.on[k]).map((k) => {
    const s = d.strategies?.[k] || {};
    const what = k === 'lit' ? 'levels · setup · position' : k === 'atlas' ? 'EMA 21 / 50 · S/R · plans · position' : (s.placeholder ? 'research: no signals yet' : 'signals');
    return `<span style="--c:${STRAT[k][1]}"><i></i>${esc(s.name || STRAT[k][0])} <em>${esc(what)}</em></span>`;
  }).join('');
  $('#lvLeg').innerHTML = leg;
  const h = L.geo?.hoverBar, b = h || (d.bars || [])[d.bars.length - 1];
  $('#lvOhlc').innerHTML = b ? `<span>${etHM(b[0])} ET</span> O <b>${fmtPx(b[1])}</b> H <b>${fmtPx(b[2])}</b> L <b>${fmtPx(b[3])}</b> C <b class="${b[4] >= b[1] ? 'lv-ok' : 'lv-no'}">${fmtPx(b[4])}</b>${L.geo?.hoverPx != null ? ` <span class="lv-muted">· cursor ${fmtPx(L.geo.hoverPx)}</span>` : ''}` : '';
  const note = $('#lvNote');
  const msg = !d.bars?.length ? 'No bars yet: the bot shows its NinjaTrader bars here once it runs.' : '';
  note.hidden = !msg; note.textContent = msg;
}

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
  const S = L.d.strategies || {};
  const out = [];
  const lit = S.lit;
  if (lit && L.on.lit) {
    const t = lit.thinking || {};
    out.push(`<article class="lv-card" style="--c:${STRAT.lit[1]}"><header><i></i><b>Zlarior</b><span class="lv-pill">${esc(t.stage?.label || '—')}${t.stage?.n ? ` · ${t.stage.n}/10` : ''}</span></header>
      ${lit.error ? `<p class="lv-no">${esc(lit.error)}</p>` : ''}
      ${stepper(t.stages)}
      <p class="lv-head">${esc(t.headline || 'Waiting for the first Brain snapshot')}</p>
      ${t.detail && t.detail !== t.headline ? `<p class="lv-muted small">${esc(t.detail)}</p>` : ''}
      <div class="lv-chips">${(t.distance || []).map((x) => `<span class="lv-chip"><b class="mono">${fmtPx(x.pts)}</b> pts ${esc(x.label)}</span>`).join('')}
        ${t.stop_preview ? `<span class="lv-chip">stop would be <b class="mono">${fmtPx(t.stop_preview)}</b> pts</span>` : ''}</div>
      <div class="lv-chips">${t.window ? `<span class="lv-chip ${t.window.open ? 'on' : ''}">${cd(t.window.t, t.window.open ? 'window closes in' : 'window opens in')}</span>` : ''}
        ${t.expires ? `<span class="lv-chip on">${cd(t.expires.t, 'limit expires in')}</span>` : ''}</div>
      ${posBox(lit.position, STRAT.lit[1], lit.position && !lit.position.paper)}
      ${checks(t.checklist)}
    </article>`);
  }
  const at = S.atlas;
  if (at && L.on.atlas) {
    const mem = (at.members || []).filter((m) => !m.candidate), cand = (at.members || []).filter((m) => m.candidate);
    const row = (m) => `<details class="lv-mem"><summary><b>${esc(m.short)}</b><span class="lv-pill">${esc(m.stage || '—')}</span>${m.window ? `<span class="lv-muted small">${cd(m.window.t, m.window.open ? 'closes in' : 'opens in')}</span>` : ''}
        <p>${esc(m.text || '')}</p></summary>${checks(m.checks)}${m.first_fail ? `<p class="lv-muted small">first rule that fails: <b>${esc(m.first_fail)}</b></p>` : ''}</details>`;
    out.push(`<article class="lv-card" style="--c:${STRAT.atlas[1]}"><header><i></i><b>ATLAS</b><span class="lv-pill">${esc(at.account || 'paper')}</span></header>
      ${at.error ? `<p class="lv-no">${esc(at.error)}</p>` : ''}${at.empty ? `<p class="lv-muted">${esc(at.empty)}</p>` : ''}
      ${posBox(at.position, STRAT.atlas[1], !!at.position)}
      ${mem.map(row).join('')}
      ${cand.length ? `<details class="lv-mem lv-cand"><summary><b>Other paper strategies</b><span class="lv-pill">research · paper</span></summary>${cand.map(row).join('')}</details>` : ''}
    </article>`);
  }
  const sc = S.scalp;
  if (sc && L.on.scalp) {
    out.push(`<article class="lv-card" style="--c:${STRAT.scalp[1]}"><header><i></i><b>${esc(sc.name || 'Strategy 3')}</b><span class="lv-pill">${sc.placeholder ? 'research' : 'paper'}</span></header>
      <p class="lv-muted">${esc(sc.text || '')}</p>${(sc.members || []).map((m) => `<p><b>${esc(m.short)}</b> · ${esc(m.stage || '')}: ${esc(m.text || '')}</p>`).join('')}</article>`);
  }
  el.innerHTML = out.join('') || '<p class="lv-muted">Switch a strategy on to see what it is thinking.</p>';
}

// ------------------------------------------------------------------ feed
function feed() {
  const ol = $('#lvFeedL'); if (!ol || !L.d) return;
  let rows = L.d.narrator || [];
  if (L.feedF !== 'all') rows = rows.filter((m) => (L.feedF === 'atlas' ? ['atlas', 'scalp'].includes(m.strat) : m.strat === L.feedF));
  if (L.important) rows = rows.filter((m) => m.level !== 'dim');
  const newest = Math.max(0, ...(L.d.narrator || []).map((m) => m.id));
  const fresh = L.seen ? newest > L.seen : false;
  ol.innerHTML = rows.slice(0, 100).map((m) => `<li class="lv-m ${esc(m.level)} ${L.seen && m.id > L.seen ? 'new' : ''}" style="--c:${(STRAT[m.strat] || STRAT.sys)[1]}">
    <time class="mono">${esc(m.hm || '')}</time><i></i><div><b>${esc(m.title)}</b> <span>${esc(m.text)}</span></div></li>`).join('') || '<li class="lv-muted">Nothing yet today.</li>';
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
    window.LE = Object.assign(window.LE || {}, { liveview: { load: () => load(true), state: L } });   // app.js sets window.LE after the imports
    const el = document.getElementById('page-' + ID);
    if (!el.querySelector('#lvRoot')) shell(el);
    load(true);
    clearInterval(L.timer); clearInterval(L.tick);
    L.timer = setInterval(() => { if (!active()) { clearInterval(L.timer); return; } if (!document.hidden) load(false); }, 3000);
    L.tick = setInterval(() => { if (!active()) { clearInterval(L.tick); return; } countdowns(); }, 1000);
  },
};
