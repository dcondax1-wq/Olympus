// DAPHNE app: the state, the playback clock, touch, the HUD, the bottom sheet (THE SEARCH / TOP RULES), the rule cards and
// the top-10 sheet. Data and layout: core.js; everything drawn on the canvas: paint.js.
//
// URL: #root=<root id> opens a root, #top opens the top 10, #rules opens the TOP RULES tab. ?at=<ms> freezes the playback
// clock (screenshots).
import * as C from './core.js?v=d3';
import { paint, ancestry, bestPath, GROW_MS, IGNITE_MS, LENS_MS } from './paint.js?v=d3';

const O = window.OLYMPUS || null;   // the OLYMPUS kit (../olympus/olympus.js): one 3D quality for every app, the veil, themes

const ZOOM_MIN = 0.6, ZOOM_MAX = 7;
const JARVIS_ORIGIN = 'https://demetrades2000-coder.github.io';

const $ = (id) => document.getElementById(id);
const app = $('app'), canvas = $('stage'), ctx = canvas.getContext('2d', { alpha: false });
const query = new URLSearchParams(location.search);
const frozenAt = query.has('at') ? Number(query.get('at')) : null;
const reduced = O ? O.reduced() : matchMedia('(prefers-reduced-motion: reduce)').matches;
const SIDE_PANEL = matchMedia('(orientation: landscape) and (max-height: 520px)');   // as in tree.css

const S = {
  model: null, rootId: null, root: null, tree: null, layouts: new Map(),
  lens: 'train', lensPrev: 'train', lensAt: 0, t0: 0, view: { s: 1, x: 0, y: 0 }, geo: null, w: 0, h: 0, dpr: 1,
  // 2: full (dpr up to 2), 1: light (1.5), 0: lightest (1). The owner's OLYMPUS choice wins; else the phone decides
  quality: O && O.chosen() ? (O.fx() === 'off' ? 0 : O.lite() ? 1 : 2) : O && O.lite() ? 1 : (devicePixelRatio >= 2 && (navigator.hardwareConcurrency || 4) >= 4) ? 2 : 1,
  frameMs: 16, slowSince: 0, selected: null, hudAt: -1, lit: -1, tab: 'search',
  maxScore: 1, maxOos: 1, maxN: 1, minN: 60, positiveLeaves: [], leafCount: 0, theme: null,
};

// ------------------------------------------------------------------------------------------------ data
async function loadDoc() {
  for (const name of ['tree.json', 'demo.json']) {
    try {
      const res = await fetch(name, { cache: 'no-cache' });
      if (res.ok) return await res.json();
    } catch (e) { /* try the next source */ }
  }
  throw new Error('no tree.json and no demo.json next to this page');
}

/** Show a root's tree and play its search from the start (already grown when the phone asks for reduced motion). */
function selectRoot(id) {
  const m = S.model;
  if (!m.trees[id]) id = m.featured[0];
  S.rootId = id;
  S.root = m.byId[id];
  if (!S.layouts.has(id)) S.layouts.set(id, C.layoutTree(m.trees[id]));
  S.tree = S.layouts.get(id);
  S.selected = null;
  hideCard();
  const nodes = S.tree.nodes;
  S.minN = m.meta.min_n || 60;
  S.maxN = Math.max(...nodes.map((n) => n.n), S.minN + 1);
  S.maxScore = Math.max(1e-6, ...nodes.map((n) => n.score || 0));
  S.maxOos = Math.max(1e-6, ...nodes.map((n) => Math.abs(n.oos || 0)));
  const N = Math.max(1, nodes.length - 1);
  nodes.forEach((n, k) => {
    const f = k / N;
    n.appear = GROW_MS * (f < 0.5 ? 2 * f * f : 1 - Math.pow(-2 * f + 2, 2) / 2) * 0.96;   // ease in-out
    n.width = 0.45 + 1.35 * Math.log1p(n.n / S.minN) / Math.log1p(S.maxN / S.minN);
    n.path = null;
  });
  S.positiveLeaves = nodes.filter((n) => !n.kids.length && (n.score || 0) > 0);
  S.view = { s: 1, x: 0, y: 0 };
  S.lit = -1; S.hudAt = -1;
  S.t0 = performance.now() - (reduced ? GROW_MS + IGNITE_MS : 0);
  document.querySelectorAll('.seed').forEach((b) => b.setAttribute('aria-current', String(b.dataset.root === id)));
  document.querySelectorAll('#rules li').forEach((li) => li.classList.toggle('cur', li.dataset.root === id));
  const seed = document.querySelector(`.seed[data-root="${CSS.escape(id)}"]`);
  if (seed) seed.scrollIntoView({ block: 'nearest', inline: 'center', behavior: reduced ? 'auto' : 'smooth' });
  try { history.replaceState(null, '', location.search + '#root=' + encodeURIComponent(id)); } catch (e) { /* sandboxed frame */ }
  renderStatic();
  resize();
}

// ------------------------------------------------------------------------------------------------ geometry
/** Canvas size (dpr capped by the quality level) and the fan's geometry between the top bar and the bottom sheet.
 *  Layout is read here only (on resize, a root, a tab), never in the frame loop. */
function resize() {
  const cap = S.quality >= 2 ? 2 : S.quality === 1 ? 1.5 : 1;
  S.dpr = Math.min(devicePixelRatio || 1, cap);
  O?.mode(S.quality < 2);
  S.w = canvas.clientWidth; S.h = canvas.clientHeight;
  canvas.width = Math.round(S.w * S.dpr); canvas.height = Math.round(S.h * S.dpr);
  const side = SIDE_PANEL.matches;
  const seeds = $('seeds').getBoundingClientRect();
  const top = document.querySelector('.hud-top').getBoundingClientRect();
  $('foot').style.bottom = `${Math.round(S.h - seeds.top)}px`;
  $('foot').style.top = side ? `${Math.round(top.bottom)}px` : '';
  const foot = $('foot').getBoundingClientRect();
  const left = side ? foot.right - 30 : 0;
  const baseY = (side ? seeds.top : foot.top + 18) - 8;
  const ceiling = top.bottom + 4;
  const cx = (left + S.w) / 2, halfW = (S.w - left) / 2 - 10, spread = 1.2;
  S.geo = { cx, baseY, spread, ry: Math.max(80, baseY - ceiling), rx: Math.max(60, halfW / Math.sin(spread)) };
  document.querySelector('.tools').style.top = `${Math.round(top.bottom - 4)}px`;
}

// ------------------------------------------------------------------------------------------------ HUD
function set(id, html) { const el = $(id); if (el.innerHTML !== html) el.innerHTML = html; }

function updateHud(t) {
  const bucket = Math.min(40, Math.floor(t / 150));
  if (bucket === S.hudAt) return;
  S.hudAt = bucket;
  const st = S.root.tree, f = Math.min(1, t / GROW_MS);
  const best = f >= 1 ? st.best : Math.max(0, ...S.tree.nodes.filter((n) => n.appear <= t).map((n) => n.score || 0));
  set('topo', `TOPOLOGY · NODES <b>${C.int(Math.round(st.nodes * f))}</b> · CUT <b>${f >= 1 ? st.cut_pct : Math.round(st.cut_pct * f)}%</b>` +
    ` · BEST <b>${best.toFixed(3)}</b> · BOUND <b>${st.bound.toFixed(3)}</b>`);
}

function renderStatic() {
  const m = S.model, r = S.root, meta = m.meta, best = r.best;
  const idx = m.roots.findIndex((x) => x.id === r.id) + 1;
  $('demo').hidden = !m.demo;
  set('rule', `RULE · ${esc(r.text.toUpperCase())}`);
  set('crit', `CRITERION: MEAN EXCESS · TRAIN ≤ ${meta.train_end} · ROOTS ${idx}/${m.roots.length} · DEPTH ${meta.depth}` +
    ` · MIN ${meta.min_n} TRADES`);
  const tr = best.train || {}, te = best.test || {}, y = best.y2026 || {};
  const cell = (name, v, f = C.usd) => `${name} <span class="${C.sign(v)}">${f(v)}</span>`;
  set('money', [cell('$/TRADE/µ TRAIN', tr.mean), cell('TEST', te.mean), cell('2026', y.mean),
    cell('· TEST $/MO 1µ', te.mo_1, C.money), cell('BOT', te.mo_bot, C.money)].join(' '));
  const path = bestPath(S).slice(1);
  $('nsteps').textContent = path.length;
  document.querySelector('.sheet-tabs [data-tab="search"]').textContent = `THE SEARCH · ${path.length} STEP${path.length === 1 ? '' : 'S'}`;
  const conds = m.conds;
  $('steps').innerHTML = path.length ? path.map((n) => `<li><span class="c">${esc(conds[n.cond] ? conds[n.cond][3] : '?')}</span>` +
    `<span class="v">${(n.score || 0).toFixed(2)}</span></li>`).join('')
    : '<li class="empty"><span class="c">no condition beats the plain root</span></li>';
  S.lit = -1;
  const st = r.tree, scale = Math.max(st.bound, 1e-6);
  const bar = (name, v, color) => `<div class="bar"><span>${name}</span><i style="--w:${Math.max(0, Math.min(100, 100 * v / scale)).toFixed(1)}%;--c:${color}"></i><span>${v.toFixed(2)}</span></div>`;
  $('bars').innerHTML = bar('GAP', st.bound - st.best, 'var(--amber)') + bar('BOUND', st.bound, 'rgba(70,255,154,.45)') + bar('BEST', st.best, 'var(--green)');
  $('roots').innerHTML = m.roots.map((x) => `<i class="${x.tree.open ? 'open' : ''}${x.id === r.id ? ' cur' : ''}" title="${esc(x.key)} ${C.variant(x)}"></i>`).join('');
  const complete = m.roots.filter((x) => !x.tree.open).length;
  $('rootsLegend').textContent = `${complete} SEARCHED TO THE END · ${m.roots.length - complete} OPEN · ${C.int(meta.nodes)} NODES IN ALL`;
  renderVerdict();
}

// the honest verdict, on top: does the whole search beat chance, and does this root's best rule hold out of sample
function renderVerdict() {
  const m = S.model, r = S.root, h = m.honesty, real = h.real || {}, plc = (h.placebo || []).map((p) => p.hold_pct);
  const held = r.best.holds, chance = C.beatsChance(h), te = r.best.test || {};
  $('verdict').className = 'verdict ' + (chance ? 'ok' : 'no');
  set('verdict', `<b class="vt">${chance ? 'BEATS CHANCE' : 'CHANCE LEVEL'}</b>` +
    `<span>${real.hold}/${real.best_rules} best rules hold out of sample (${real.hold_pct}%)` +
    (plc.length ? ` · shuffled conditions ${plc.map((p) => p + '%').join(' / ')}` : '') + `</span>` +
    `<span>THIS ROOT: <b class="${held ? 'pos' : 'neg'}">${held ? 'HOLDS' : 'FAILS'}</b> · ` +
    (te.n ? `test ${C.usd(te.mean)}/trade on ${te.n} trades` : 'no test trades') + `</span>`);
}

function lightSteps(lit) {
  document.querySelectorAll('#steps li').forEach((li, i) => li.classList.toggle('lit', i < lit));
}

function esc(s) { return String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])); }

// ------------------------------------------------------------------------------------------------ the bottom sheet: THE SEARCH / TOP RULES
function setTab(tab) {
  S.tab = tab;
  document.querySelectorAll('.sheet-tabs button').forEach((b) => b.setAttribute('aria-selected', String(b.dataset.tab === tab)));
  document.querySelectorAll('.pane').forEach((p) => { p.hidden = p.dataset.pane !== tab; });
  resize();
}
function buildRules() {
  const m = S.model;
  $('rules').innerHTML = m.top.map((r, i) => {
    const te = r.test || {}, root = m.byId[r.root] || {};
    return `<li data-root="${esc(r.root)}" class="${r.root === S.rootId ? 'cur' : ''}"><span class="rk">#${i + 1}</span>` +
      `<span class="nm"><b>${esc(r.key)}</b> ${root.target_r ? C.variant(root) : ''}<small>${esc(r.steps.join(' · '))}</small></span>` +
      `<span class="mo ${C.sign(te.mean)}">${C.usd(te.mean)}<small>TEST/TR</small></span>` +
      `<span class="tag ${r.holds ? 'ok' : 'no'}">${r.holds ? 'HOLDS' : 'FAILS'}</span></li>`;
  }).join('');
  const held = m.top.filter((r) => r.holds).length;
  $('rulesNote').textContent = `${held} OF THE TOP ${m.top.length} HOLD OUT OF SAMPLE · TAP ONE TO GROW ITS TREE · $ A TRADE A MICRO AFTER COSTS`;
}

// ------------------------------------------------------------------------------------------------ seeds
function buildSeeds() {
  const m = S.model;
  $('seeds').innerHTML = m.featured.map((id) => {
    const r = m.byId[id], te = r.best.test || {};
    return `<button type="button" class="seed" data-root="${esc(id)}" aria-current="false" aria-label="${esc(r.key)} ${C.variant(r)}">` +
      `<canvas width="128" height="60"></canvas><b>${esc(r.key)}</b><small>${C.variant(r)}<span class="${C.sign(te.mean)}">TEST ${C.usd(te.mean)}</span></small></button>`;
  }).join('');
  document.querySelectorAll('.seed').forEach((b) => {
    drawSeed(b.querySelector('canvas'), b.dataset.root);
    b.addEventListener('click', () => selectRoot(b.dataset.root));
  });
}

function drawSeed(cv, id) {
  if (!S.layouts.has(id)) S.layouts.set(id, C.layoutTree(S.model.trees[id]));
  const L = S.layouts.get(id), g = cv.getContext('2d');
  const geo = { cx: cv.width / 2, baseY: cv.height - 3, spread: 1.2, ry: cv.height - 8, rx: (cv.width / 2 - 4) / Math.sin(1.2) };
  g.fillStyle = '#030705'; g.fillRect(0, 0, cv.width, cv.height);
  g.globalCompositeOperation = 'lighter';
  for (const n of L.nodes) {
    const p = L.byId.get(n.parent);
    if (!p) continue;
    const [x1, y1] = C.place(p, geo), [x2, y2] = C.place(n, geo);
    g.lineWidth = Math.max(0.5, 1.6 - 0.25 * n.depth);
    g.strokeStyle = n.best ? 'rgba(225,255,235,.9)' : n.status === C.CUT ? 'rgba(60,120,90,.25)' : 'rgba(70,255,154,.32)';
    g.beginPath(); g.moveTo(x1, y1); g.quadraticCurveTo(x1, (y1 + y2) / 2, x2, y2); g.stroke();
  }
}

// ------------------------------------------------------------------------------------------------ cards
function showNode(n) {
  const m = S.model, r = S.root, sess = m.meta.sessions || {};
  S.selected = n;
  const path = ancestry(S, n).slice(1);
  const chips = `<span class="chip root">${esc(r.key)} ${C.variant(r)}</span>` + path.map((p) => `<span class="chip">${esc(m.conds[p.cond][3])}</span>`).join('');
  const words = esc(r.text) + (path.length ? ', only when ' + path.map((p) => esc(m.conds[p.cond][4])).join('; ') : '') + '.';
  const tr = C.nodeMoney(r, n, 'train', sess), te = C.nodeMoney(r, n, 'test', sess);
  const row = (name, x) => `<tr><td>${name}</td><td>${C.int(x.n)}</td><td class="${C.sign(x.mean)}">${C.usd(x.mean)}</td>` +
    `<td class="${C.sign(x.excess)}">${n.depth ? C.usd(x.excess) : '—'}</td><td class="${C.sign(x.mo)}">${C.money(x.mo)}</td></tr>`;
  const isBest = n.best && n === S.tree.bestPath[S.tree.bestPath.length - 1];
  const bot = isBest ? `<tr><td>BOT SIZE $/MO</td><td colspan="4" class="${C.sign(r.best.test.mo_bot)}">TRAIN ${C.money(r.best.train.mo_bot)} · TEST ${C.money(r.best.test.mo_bot)} · 2026 ${C.money((r.best.y2026 || {}).mo_bot)}</td></tr>` : '';
  const verdict = n.depth ? C.holds(r, n, m.meta.min_test_n || 10, sess) : null;
  const tag = !n.depth ? '<span class="tag na">THE PLAIN ROOT</span>'
    : verdict === null ? '<span class="tag na">TOO FEW TEST TRADES</span>'
    : verdict ? '<span class="tag ok">HOLDS OUT OF SAMPLE</span>' : '<span class="tag no">FAILS OUT OF SAMPLE</span>';
  $('cardBody').innerHTML = `<h3 id="cardTitle">NODE ${n.id} · DEPTH ${n.depth} · ${C.STATUS_WORDS[n.status]}${isBest ? ' · BEST' : ''}</h3>` +
    `<div class="chips">${chips}</div><p class="words">${words}</p>` +
    `<table class="nums"><thead><tr><th></th><th>TRADES</th><th>$/TRADE/µ</th><th>VS ROOT</th><th>$/MO 1µ</th></tr></thead><tbody>` +
    row(`TRAIN ≤ ${m.meta.train_end.slice(0, 4)}`, tr) + row('TEST 2025-26', te) + bot + '</tbody></table>' +
    `<p class="note">SCORE ${(n.score || 0).toFixed(2)} · BOUND ${(n.bound || 0).toFixed(2)} (nothing below this branch can score more)</p>${tag}`;
  $('card').hidden = false;
}

function hideCard() { $('card').hidden = true; S.selected = null; }

function showTop() {
  const m = S.model, h = m.honesty.real || {};
  $('topSub').textContent = `${C.int(h.nodes)} nodes searched on ${h.roots} roots. ${h.hold} of ${h.best_rules} best rules hold out of sample` +
    ((m.honesty.placebo || []).length ? `; with shuffled conditions ${(m.honesty.placebo || []).map((p) => p.hold_pct + '%').join(' / ')} do.` : '.') +
    ` $ per trade per micro after $1.90 costs; bot size = $${m.meta.bot_risk_usd} risk a trade.`;
  const cols = [['train', `TRAIN ≤${m.meta.train_end.slice(0, 4)}`], ['test', 'TEST 25-26'], ['y2026', '2026']];
  $('toplist').innerHTML = m.top.map((r, i) => {
    const rows = cols.map(([k, name]) => {
      const x = r[k] || {};
      return `<tr><td>${name}</td><td>${C.int(x.n || 0)}</td><td class="${C.sign(x.mean)}">${C.usd(x.mean)}</td><td>${x.win ?? '—'}${x.win !== undefined ? '%' : ''}</td>` +
        `<td>${x.tpw ?? '—'}</td><td class="${C.sign(x.mo_bot)}">${C.money(x.mo_bot)}</td></tr>`;
    }).join('');
    const root = m.byId[r.root] || {};
    return `<li data-root="${esc(r.root)}"><div class="hd"><span class="rk">#${i + 1}</span><b>${esc(r.key)}</b><small>${root.target_r ? C.variant(root) : ''}</small>` +
      `<span class="tag ${r.holds ? 'ok' : 'no'}">${r.holds ? 'HOLDS' : 'FAILS'}</span></div>` +
      `<div class="chips">${r.steps.map((s) => `<span class="chip">${esc(s)}</span>`).join('')}</div>` +
      `<table class="nums"><thead><tr><th></th><th>N</th><th>$/TR/µ</th><th>WIN</th><th>TR/WK</th><th>BOT $/MO</th></tr></thead><tbody>${rows}</tbody></table></li>`;
  }).join('');
  $('top').hidden = false;
}

function hideTop() { $('top').hidden = true; }

// ------------------------------------------------------------------------------------------------ the lens: TRAIN / TEST
// a wavefront climbs the tree from the root (paint.js lensOf), the screen flashes the lens's colour and a stamp says what
// the out-of-sample test did to this root's best rule
function setLens(lens) {
  if (lens === S.lens) return;
  S.lensPrev = S.lens; S.lens = lens; S.lensAt = reduced ? performance.now() - LENS_MS * 2 : performance.now();
  document.querySelectorAll('.lens button').forEach((x) => x.setAttribute('aria-checked', String(x.dataset.lens === lens)));
  app.dataset.lens = lens;
  const fx = $('lensFx'), held = S.root && S.root.best.holds;
  $('lensT').textContent = lens === 'test' ? 'OUT OF SAMPLE · 2025-26' : 'IN SAMPLE · TRAIN ≤ ' + String(S.model.meta.train_end).slice(0, 4);
  $('lensS').textContent = lens === 'test' ? (held ? 'THIS ROOT\'S BEST RULE HOLDS' : 'THIS ROOT\'S BEST RULE FAILS') : 'WHAT THE SEARCH SAW';
  $('lensS').className = lens === 'test' ? (held ? 'pos' : 'neg') : '';
  fx.className = 'lens-fx ' + lens;
  fx.style.opacity = reduced ? '1' : '0';
  fx.hidden = false;
  S.fxAt = performance.now();                                        // loop() fades it in and out (opacity only: no layout)
  clearTimeout(setLens.timer);
  setLens.timer = setTimeout(() => { fx.hidden = true; S.fxAt = 0; }, FX_MS);
}
const FX_MS = 1700;
function stepFx(now) {
  if (!S.fxAt || reduced) return;
  const f = (now - S.fxAt) / FX_MS, fx = $('lensFx');
  if (f >= 1) { fx.hidden = true; S.fxAt = 0; return; }
  const o = f < 0.14 ? f / 0.14 : f < 0.7 ? 1 : Math.max(0, 1 - (f - 0.7) / 0.3);
  fx.style.opacity = o.toFixed(3);
  fx.style.transform = `scale(${(f < 0.14 ? 1.12 - 0.12 * f / 0.14 : 1 - 0.02 * Math.max(0, f - 0.7) / 0.3).toFixed(4)})`;
}

// ------------------------------------------------------------------------------------------------ OLYMPUS themes
// applyTheme(tokens): {bg, accent, text, dim, panel, line} or CSS variable names ('--x': value). The canvas reads the
// background on the next frame. Hooked to OLYMPUS.theme() / onTheme when the kit has them.
const THEME_VARS = { bg: '--bg', accent: '--green', text: '--text', dim: '--dim', panel: '--panel', line: '--line', ink: '--ink' };
export function applyTheme(tok) {
  if (!tok || typeof tok !== 'object') return;
  const root = document.documentElement.style;
  for (const [k, v] of Object.entries(tok)) {
    if (typeof v !== 'string') continue;
    if (k.startsWith('--')) root.setProperty(k, v); else if (THEME_VARS[k]) root.setProperty(THEME_VARS[k], v);
  }
  S.theme = tok;
  if (typeof (tok.bg || tok['--bg']) === 'string') S.bg = tok.bg || tok['--bg'];
}
window.applyTheme = applyTheme;
function hookTheme() {
  if (!O) return;
  try { if (typeof O.theme === 'function') applyTheme(O.theme()); } catch (e) { /* kit without themes */ }
  try { if (typeof O.onTheme === 'function') O.onTheme(applyTheme); } catch (e) { /* kit without themes */ }
}

// ------------------------------------------------------------------------------------------------ touch: pan, pinch, tap
const pointers = new Map();
let gesture = null, lastTap = 0;

function toWorld(sx, sy) { const v = S.view; return [(sx - v.x) / v.s, (sy - v.y) / v.s]; }

function zoomAt(sx, sy, f) {
  const v = S.view, s = Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, v.s * f));
  const [wx, wy] = toWorld(sx, sy);
  v.x = sx - wx * s; v.y = sy - wy * s; v.s = s;
}

canvas.addEventListener('pointerdown', (e) => {
  canvas.setPointerCapture(e.pointerId);
  pointers.set(e.pointerId, [e.offsetX, e.offsetY]);
  gesture = { start: performance.now(), moved: 0, pinch: null };
});
canvas.addEventListener('pointermove', (e) => {
  if (!pointers.has(e.pointerId) || !gesture) return;
  const prev = pointers.get(e.pointerId);
  pointers.set(e.pointerId, [e.offsetX, e.offsetY]);
  gesture.moved += Math.hypot(e.offsetX - prev[0], e.offsetY - prev[1]);
  const pts = [...pointers.values()];
  if (pts.length === 1) {
    S.view.x += e.offsetX - prev[0]; S.view.y += e.offsetY - prev[1];
  } else if (pts.length >= 2) {
    const [a, b] = pts, d = Math.hypot(a[0] - b[0], a[1] - b[1]);
    const mx = (a[0] + b[0]) / 2, my = (a[1] + b[1]) / 2;
    if (!gesture.pinch) gesture.pinch = { d, mx, my };
    zoomAt(mx, my, d / Math.max(1, gesture.pinch.d));
    S.view.x += mx - gesture.pinch.mx; S.view.y += my - gesture.pinch.my;
    gesture.pinch = { d, mx, my };
  }
});
function endPointer(e) {
  if (!pointers.has(e.pointerId)) return;
  pointers.delete(e.pointerId);
  if (!gesture || pointers.size) return;
  const quick = performance.now() - gesture.start < 350 && gesture.moved < 8 && !gesture.pinch;
  if (quick) {
    const now = performance.now();
    if (now - lastTap < 300) { S.view = { s: 1, x: 0, y: 0 }; lastTap = 0; } else { lastTap = now; tap(e.offsetX, e.offsetY); }
  }
  gesture = null;
}
canvas.addEventListener('pointerup', endPointer);
canvas.addEventListener('pointercancel', endPointer);
canvas.addEventListener('wheel', (e) => { e.preventDefault(); zoomAt(e.offsetX, e.offsetY, Math.exp(-e.deltaY * 0.0015)); }, { passive: false });

function tap(sx, sy) {
  const [wx, wy] = toWorld(sx, sy);
  const t = frozenAt !== null ? frozenAt : performance.now() - S.t0;
  let best = null, bd = (24 / S.view.s) ** 2;
  for (const n of S.tree.nodes) {
    if (n.appear > t || n.x === undefined) continue;
    const d = ((n.x - wx) ** 2 + (n.y - wy) ** 2) * (n.best ? 0.35 : 1);     // the lit path wins close calls
    if (d < bd) { bd = d; best = n; }
  }
  if (best) showNode(best); else hideCard();
}

// ------------------------------------------------------------------------------------------------ controls + loop
document.querySelectorAll('.lens button').forEach((b) => b.addEventListener('click', () => setLens(b.dataset.lens)));
document.querySelectorAll('.sheet-tabs button').forEach((b) => b.addEventListener('click', () => setTab(b.dataset.tab)));
$('replay').addEventListener('click', () => selectRoot(S.rootId));
$('openTop').addEventListener('click', showTop);
document.querySelectorAll('[data-close]').forEach((b) => b.addEventListener('click', () => { hideCard(); hideTop(); }));
for (const id of ['toplist', 'rules']) {
  $(id).addEventListener('click', (e) => {
    const li = e.target.closest('li[data-root]');
    if (!li) return;
    hideTop();
    if (S.model.trees[li.dataset.root]) selectRoot(li.dataset.root);
  });
}
addEventListener('keydown', (e) => { if (e.key === 'Escape') { hideCard(); hideTop(); } });
addEventListener('resize', () => { if (S.model) resize(); });
addEventListener('hashchange', route);

function route() {
  const h = decodeURIComponent(location.hash.slice(1));
  if (h === 'top') { showTop(); return; }
  if (h === 'rules') { setTab('rules'); return; }
  const id = h.startsWith('root=') ? h.slice(5) : null;
  if (id && id !== S.rootId && S.model.trees[id]) selectRoot(id);
}

function loop(now) {
  if (!(O ? O.hidden() : document.hidden)) {                    // hidden tab: no frame (the battery)
    const t0 = performance.now(), t = frozenAt !== null ? frozenAt : now - S.t0;
    paint(ctx, S, { t, now: performance.now(), reduced, sway: S.quality >= 2 && !reduced && frozenAt === null, onLit: lightSteps });
    updateHud(t);
    stepFx(performance.now());
    adapt(performance.now() - t0, now);
    if (O && O.state() === 'loading') O.ready();               // the first frame is drawn: the veil lifts
  }
  requestAnimationFrame(loop);
}

function adapt(ms, now) {
  // a frame that takes more than ~22 ms of drawing on a weak phone steps the quality down (no leaves / taper, lower dpr)
  S.frameMs = S.frameMs * 0.92 + ms * 0.08;
  if (S.frameMs > 22 && S.quality > 0 && !(O && O.chosen())) {   // the automatic step down, unless the owner chose
    if (!S.slowSince) S.slowSince = now;
    if (now - S.slowSince > 1500) { S.quality--; S.slowSince = 0; S.frameMs = 12; resize(); }
  } else S.slowSince = 0;
}

async function postJarvis() {
  // inside Jarvis: hand it the card the engine wrote (jarvis.json, tools/strategytree/report.jarvis_card), stamped now
  if (window.parent === window) return;
  let card = { v: 1, name: 'DAPHNE', status: { level: 'off', label: 'Demo data' }, open: '#top', theme: '#030705' };
  if (!S.model.demo) {
    try { const res = await fetch('jarvis.json', { cache: 'no-cache' }); if (res.ok) card = await res.json(); } catch (e) { /* keep the plain card */ }
  }
  card.t = Math.floor(Date.now() / 1000);
  try { window.parent.postMessage({ jarvis: 1, href: location.href, card }, JARVIS_ORIGIN); } catch (e) { /* not in Jarvis */ }
}

async function main() {
  try {
    S.model = C.readDoc(await loadDoc());
    if (!S.model.featured.length) throw new Error('tree.json has no featured trees');
  } catch (e) {
    app.dataset.state = 'error';
    $('loading').textContent = 'NO SEARCH DATA · ' + String(e.message || e).toUpperCase();
    O?.fail('no search data (' + String(e.message || e) + ')');
    return;
  }
  app.dataset.state = 'ready';
  buildSeeds();
  buildRules();
  hookTheme();
  const h = decodeURIComponent(location.hash.slice(1));
  selectRoot(h.startsWith('root=') ? h.slice(5) : S.model.featured[0]);
  if (h === 'top') showTop();
  if (h === 'rules') setTab('rules');
  postJarvis();
  window.__daphne = { ready: true, state: S, setLens, setTab };
  requestAnimationFrame(loop);
}

main();
