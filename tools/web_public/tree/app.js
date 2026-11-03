// DAPHNE app: draws the strategy-tree search on a canvas, plays it back node by node, lights the best path, and
// runs the HUD, the seeds (other roots), the rule cards and the top-10 sheet. Data and layout: core.js.
//
// URL: #root=<root id> opens a root, #top opens the top 10. ?at=<ms> freezes the playback clock (screenshots).

import * as C from './core.js?v=d1';

const O = window.OLYMPUS || null;   // the OLYMPUS kit (../olympus/olympus.js): one 3D quality for every app, the veil

const GROW_MS = 6500;            // the whole search grows in this long
const EDGE_MS = 340;             // one branch grows in this long
const FADE_MS = 800;             // a cut branch dims over this long
const IGNITE_MS = 1300;          // the best path lights up root to leaf
const PULSE_EVERY = 1150, PULSE_MS = 1800, SPARK_EVERY = 210, SPARK_MS = 1500;
const ZOOM_MIN = 0.6, ZOOM_MAX = 7;
const BG = '#030705';
const JARVIS_ORIGIN = 'https://demetrades2000-coder.github.io';

const $ = (id) => document.getElementById(id);
const app = $('app'), canvas = $('stage'), ctx = canvas.getContext('2d', { alpha: false });
const query = new URLSearchParams(location.search);
const frozenAt = query.has('at') ? Number(query.get('at')) : null;
const reduced = O ? O.reduced() : matchMedia('(prefers-reduced-motion: reduce)').matches;
const SIDE_PANEL = matchMedia('(orientation: landscape) and (max-height: 520px)');   // as in tree.css

const S = {
  model: null, rootId: null, root: null, tree: null, layouts: new Map(),
  lens: 'train', t0: 0, view: { s: 1, x: 0, y: 0 }, geo: null, w: 0, h: 0, dpr: 1,
  // 2: full (dpr up to 2), 1: light (1.5), 0: lightest (1). The owner's OLYMPUS choice wins; else the phone decides
  quality: O && O.chosen() ? (O.fx() === 'off' ? 0 : O.lite() ? 1 : 2) : O && O.lite() ? 1 : (devicePixelRatio >= 2 && (navigator.hardwareConcurrency || 4) >= 4) ? 2 : 1,
  frameMs: 16, slowSince: 0, selected: null, hudAt: -1, lit: -1,
  maxScore: 1, maxOos: 1, maxN: 1, minN: 60, positiveLeaves: [],
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
    n.strands = n.n >= 4 * S.minN ? 3 : n.n >= 2 * S.minN ? 2 : 1;
    n.path = null;
  });
  S.positiveLeaves = nodes.filter((n) => !n.kids.length && (n.score || 0) > 0);
  S.view = { s: 1, x: 0, y: 0 };
  S.lit = -1; S.hudAt = -1;
  S.t0 = performance.now() - (reduced ? GROW_MS + IGNITE_MS : 0);
  document.querySelectorAll('.seed').forEach((b) => b.setAttribute('aria-current', String(b.dataset.root === id)));
  const seed = document.querySelector(`.seed[data-root="${CSS.escape(id)}"]`);
  if (seed) seed.scrollIntoView({ block: 'nearest', inline: 'center', behavior: reduced ? 'auto' : 'smooth' });
  try { history.replaceState(null, '', location.search + '#root=' + encodeURIComponent(id)); } catch (e) { /* sandboxed frame */ }
  renderStatic();
  resize();
}

// ------------------------------------------------------------------------------------------------ geometry
/** Canvas size (dpr capped by the quality level) and the fan's geometry between the header and the search panel. */
function resize() {
  const cap = S.quality >= 2 ? 2 : S.quality === 1 ? 1.5 : 1;
  S.dpr = Math.min(devicePixelRatio || 1, cap);
  O?.mode(S.quality < 2);
  S.w = canvas.clientWidth; S.h = canvas.clientHeight;
  canvas.width = Math.round(S.w * S.dpr); canvas.height = Math.round(S.h * S.dpr);
  // the search panel sits on the seeds (and, as a left column on a landscape phone, under the header)
  const side = SIDE_PANEL.matches;
  const seeds = $('seeds').getBoundingClientRect();
  const top = document.querySelector('.hud-top').getBoundingClientRect();
  $('foot').style.bottom = `${Math.round(S.h - seeds.top)}px`;
  $('foot').style.top = side ? `${Math.round(top.bottom)}px` : '';
  const foot = $('foot').getBoundingClientRect();
  const left = side ? foot.right - 30 : 0;
  const baseY = (side ? seeds.top : foot.top + 18) - 8;
  const ceiling = top.bottom + 4;
  const cx = (left + S.w) / 2;
  const half = (S.w - left) / 2 - 10;
  const spread = 1.2;
  S.geo = { cx, baseY, spread, ry: Math.max(80, baseY - ceiling), rx: Math.max(60, half / Math.sin(spread)) };
  document.querySelector('.tools').style.top = `${Math.round(top.bottom - 4)}px`;
}

function curve(p, q, n) {
  // a branch leaves its parent going up, then bends out to the child
  const dy = p[1] - q[1];
  const b = n.bend * 14;
  return [p[0], p[1] - dy * 0.55, q[0] - (q[0] - p[0]) * 0.28 + b, q[1] + dy * 0.32];
}

function bezierAt(p, c, q, t) {
  const u = 1 - t;
  const x = u * u * u * p[0] + 3 * u * u * t * c[0] + 3 * u * t * t * c[2] + t * t * t * q[0];
  const y = u * u * u * p[1] + 3 * u * u * t * c[1] + 3 * u * t * t * c[3] + t * t * t * q[1];
  return [x, y];
}

function positions(t) {
  const sway = S.quality >= 2 && !reduced && frozenAt === null;
  for (const n of S.tree.nodes) {
    const [x, y] = C.place(n, S.geo);
    const k = sway ? Math.sin(t * 0.00055 + n.phase) * n.r * 3.2 : 0;
    n.x = x + k; n.y = y - Math.abs(k) * 0.3;
  }
}

// ------------------------------------------------------------------------------------------------ colours
// buckets keep the stroke count low: every branch of one colour and width class goes into one Path2D
const RGB = { pos: '70,255,154', hot: '190,255,215', dim: '80,170,120', cut: '60,120,90', open: '245,184,74', red: '255,107,127', na: '110,150,130' };

function tone(n, t) {
  const age = t - n.appear - EDGE_MS;
  if (S.lens === 'test') {
    if (n.oos === null || !Number.isFinite(n.oos) || !n.oosN) return ['na', 0.1];
    const a = 0.16 + 0.6 * Math.min(1, Math.abs(n.oos) / S.maxOos);
    return [n.oos > 0 ? 'pos' : 'red', n.status === C.CUT ? a * 0.45 : a];
  }
  if (n.status === C.CUT) {
    const f = Math.min(1, Math.max(0, age / FADE_MS));
    return ['cut', 0.55 - 0.45 * f];                       // born bright, fades as the bound cuts it
  }
  if (n.status === C.OPEN) return ['open', 0.16];
  const s = n.score || 0;
  if (s <= 0) return ['dim', 0.16];
  const f = Math.min(1, s / S.maxScore);
  return [f > 0.7 ? 'hot' : 'pos', 0.18 + 0.55 * f];
}

// ------------------------------------------------------------------------------------------------ drawing
function frame(now) {
  const t = frozenAt !== null ? frozenAt : now - S.t0;
  const { s, x, y } = S.view;
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.globalCompositeOperation = 'source-over';
  ctx.fillStyle = BG;
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  if (!S.tree || !S.tree.root) return;
  ctx.setTransform(S.dpr * s, 0, 0, S.dpr * s, S.dpr * x, S.dpr * y);
  positions(t);
  drawGround();
  ctx.globalCompositeOperation = 'lighter';
  drawBranches(t, s);
  drawBest(t, s);
  drawMotes(t, s);
  drawSelection(s);
  updateHud(t);
}

function drawGround() {
  const { cx, baseY, rx } = S.geo;
  const g = ctx.createRadialGradient(cx, baseY, 0, cx, baseY, Math.min(rx, 260));
  g.addColorStop(0, 'rgba(70,255,154,.16)'); g.addColorStop(1, 'rgba(70,255,154,0)');
  ctx.fillStyle = g;
  ctx.fillRect(cx - 280, baseY - 280, 560, 300);
  ctx.strokeStyle = 'rgba(70,255,154,.22)';
  ctx.lineWidth = 1 / S.view.s;
  ctx.beginPath(); ctx.moveTo(cx - S.geo.rx, baseY + 0.5); ctx.lineTo(cx + S.geo.rx, baseY + 0.5); ctx.stroke();
  label(`${S.root.key} · ${C.variant(S.root)}`, cx + 18 / S.view.s, baseY - 5 / S.view.s, 'left', 'rgba(190,255,215,.7)');
}

function label(text, x, y, align, color) {
  const s = S.view.s;
  ctx.font = `600 ${9.5 / s}px ui-monospace, "SF Mono", Menlo, monospace`;
  ctx.textAlign = align;
  ctx.fillStyle = color;
  ctx.fillText(text, x, y);
}

function drawBranches(t, s) {
  const buckets = new Map();
  const growing = [];
  const dots = new Path2D();
  const sep = 1.1 / s;
  for (const n of S.tree.nodes) {
    if (n.parent < 0 || t < n.appear) continue;
    const p = S.tree.byId.get(n.parent);
    if (!p) continue;
    const g = Math.min(1, (t - n.appear) / EDGE_MS);
    const P = [p.x, p.y], Q = [n.x, n.y], c = curve(P, Q, n);
    if (g < 1) { growing.push([P, c, Q, g]); continue; }
    const [col, alpha] = tone(n, t);
    const wk = n.width > 1.3 ? 2 : n.width > 0.85 ? 1 : 0;
    const ak = Math.round(alpha * 10);
    const key = `${col}|${wk}|${ak}`;
    let path = buckets.get(key);
    if (!path) { path = new Path2D(); buckets.set(key, path); }
    const strands = S.quality >= 1 ? n.strands : 1;
    for (let k = 0; k < strands; k++) {
      const o = (k - (strands - 1) / 2) * sep;
      path.moveTo(P[0] + o, P[1]);
      path.bezierCurveTo(c[0] + o, c[1], c[2] + o * 1.6, c[3], Q[0] + o * 0.6, Q[1]);
    }
    if (!n.kids.length && n.status !== C.CUT && (S.lens === 'test' ? n.oos > 0 : n.score > 0)) {
      dots.rect(n.x - 0.9 / s, n.y - 0.9 / s, 1.8 / s, 1.8 / s);
    }
  }
  for (const [key, path] of buckets) {
    const [col, wk, ak] = key.split('|');
    ctx.strokeStyle = `rgba(${RGB[col]},${ak / 10})`;
    ctx.lineWidth = [0.55, 0.9, 1.35][wk] / s;
    ctx.stroke(path);
  }
  ctx.fillStyle = 'rgba(190,255,215,.55)';
  ctx.fill(dots);
  // branches still growing: a bright tip runs out along the curve (one stroke for all of them)
  const shoots = new Path2D();
  for (const [P, c, Q, g] of growing) {
    shoots.moveTo(P[0], P[1]);
    for (let i = 1; i <= 10; i++) { const [px, py] = bezierAt(P, c, Q, (i / 10) * g); shoots.lineTo(px, py); }
  }
  ctx.strokeStyle = 'rgba(190,255,215,.7)';
  ctx.lineWidth = 0.9 / s;
  ctx.stroke(shoots);
  for (const [P, c, Q, g] of growing) {
    const [tx, ty] = bezierAt(P, c, Q, g);
    glow(tx, ty, 6 / s, '210,255,225', 0.9);
  }
  // the root
  glow(S.tree.root.x, S.tree.root.y, 18 / s, RGB.pos, 0.9);
}

// glows are pre-drawn sprites (one radial gradient each, drawn once), stamped with drawImage: cheap on a phone GPU
const SPRITES = {};
function sprite(rgb) {
  if (SPRITES[rgb]) return SPRITES[rgb];
  const c = document.createElement('canvas');
  c.width = c.height = 64;
  const g = c.getContext('2d'), grad = g.createRadialGradient(32, 32, 0, 32, 32, 32);
  grad.addColorStop(0, `rgba(${rgb},1)`); grad.addColorStop(0.35, `rgba(${rgb},.45)`); grad.addColorStop(1, `rgba(${rgb},0)`);
  g.fillStyle = grad; g.fillRect(0, 0, 64, 64);
  return (SPRITES[rgb] = c);
}

function glow(x, y, r, rgb, alpha = 1) {
  ctx.globalAlpha = alpha;
  ctx.drawImage(sprite(rgb), x - r, y - r, 2 * r, 2 * r);
  ctx.globalAlpha = 1;
}

function pathPoint(path, f) {
  // a point at fraction f (0..1) along a root-to-node path of nodes
  const L = path.length - 1;
  if (L < 1) return [path[0].x, path[0].y];
  const pos = Math.min(L - 1e-6, Math.max(0, f * L));
  const i = Math.floor(pos), a = path[i], b = path[i + 1];
  const P = [a.x, a.y], Q = [b.x, b.y];
  return bezierAt(P, curve(P, Q, b), Q, pos - i);
}

function strokePath(path, upto, width, color) {
  ctx.strokeStyle = color; ctx.lineWidth = width;
  ctx.beginPath();
  const L = path.length - 1, steps = Math.max(1, Math.ceil(upto * L * 14));
  for (let i = 0; i <= steps; i++) {
    const [px, py] = pathPoint(path, (i / steps) * upto);
    if (i) ctx.lineTo(px, py); else ctx.moveTo(px, py);
  }
  ctx.stroke();
}

function bestPath() {
  const leaf = S.tree.bestPath[S.tree.bestPath.length - 1];
  return leaf ? ancestry(leaf) : [S.tree.root];
}

function ancestry(n) {
  if (n.path) return n.path;
  const out = [n];
  while (out[0].parent >= 0 && S.tree.byId.get(out[0].parent)) out.unshift(S.tree.byId.get(out[0].parent));
  n.path = out;
  return out;
}

function drawBest(t, s) {
  const path = bestPath();
  if (path.length < 2) return;
  const ig = Math.min(1, Math.max(0, (t - GROW_MS) / IGNITE_MS));
  if (ig <= 0) return;
  const testFail = S.lens === 'test' && !(C.holds(S.root, path[path.length - 1], S.model.meta.min_test_n || 10, S.model.meta.sessions || {}));
  const rgb = testFail ? RGB.red : '120,255,180';
  strokePath(path, ig, 10 / s, `rgba(${rgb},.06)`);
  strokePath(path, ig, 4.5 / s, `rgba(${rgb},.22)`);
  strokePath(path, ig, 1.7 / s, testFail ? 'rgba(255,170,180,.95)' : 'rgba(225,255,235,.95)');
  const head = pathPoint(path, ig);
  glow(head[0], head[1], 20 / s, rgb, 0.85);
  const lit = Math.floor(ig * (path.length - 1) + 1e-6);
  if (lit !== S.lit) { S.lit = lit; lightSteps(lit); }
  if (ig >= 1) {
    const leaf = path[path.length - 1];
    glow(leaf.x, leaf.y, (26 + 5 * Math.sin(t * 0.004)) / s, rgb, 0.9);
    const right = leaf.x < S.geo.cx;
    const tag = S.lens === 'test' ? `TEST ${C.usd(S.root.best.test.mean)}` : `BEST ${(leaf.score || 0).toFixed(2)}`;
    label(tag, leaf.x + (right ? 14 : -14) / s, leaf.y - 10 / s, right ? 'left' : 'right', testFail ? 'rgba(255,170,180,.95)' : 'rgba(225,255,235,.95)');
  }
}

function drawMotes(t, s) {
  if (reduced) return;
  const path = bestPath();
  const after = t - GROW_MS - IGNITE_MS;
  // pulses travel the best path; sparks wander up other positive branches
  if (path.length > 1 && after > 0) {
    const first = Math.floor(Math.max(0, after - PULSE_MS) / PULSE_EVERY);
    for (let k = first; k * PULSE_EVERY <= after; k++) {
      const f = (after - k * PULSE_EVERY) / PULSE_MS;
      if (f < 0 || f > 1) continue;
      const [px, py] = pathPoint(path, f);
      glow(px, py, 11 / s, '225,255,235', 0.95);
    }
  }
  const leaves = S.positiveLeaves;
  if (!leaves.length || t < 600) return;
  const first = Math.floor(Math.max(0, t - SPARK_MS) / SPARK_EVERY);
  for (let k = first; k * SPARK_EVERY <= t; k++) {
    const leaf = leaves[Math.floor(C.hash01(k, 19) * leaves.length)];
    if (leaf.appear + EDGE_MS > k * SPARK_EVERY) continue;
    const f = (t - k * SPARK_EVERY) / SPARK_MS;
    if (f < 0 || f > 1) continue;
    const [px, py] = pathPoint(ancestry(leaf), f);
    glow(px, py, 6 / s, '150,255,195', 0.55 * (1 - f));
  }
}

function drawSelection(s) {
  const n = S.selected;
  if (!n || n.x === undefined) return;
  strokePath(ancestry(n), 1, 1.4 / s, 'rgba(245,184,74,.85)');
  ctx.strokeStyle = 'rgba(245,184,74,.95)';
  ctx.lineWidth = 1.2 / s;
  ctx.beginPath(); ctx.arc(n.x, n.y, 7 / s, 0, Math.PI * 2); ctx.stroke();
}

// ------------------------------------------------------------------------------------------------ HUD
function set(id, html) { const el = $(id); if (el.innerHTML !== html) el.innerHTML = html; }

function updateHud(t) {
  const bucket = Math.min(40, Math.floor(t / 150));
  if (bucket === S.hudAt) return;
  S.hudAt = bucket;
  const r = S.root, st = r.tree, f = Math.min(1, t / GROW_MS);
  const shown = S.tree.nodes.filter((n) => n.appear <= t);
  const best = f >= 1 ? st.best : Math.max(0, ...shown.map((n) => n.score || 0));
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
  // the search steps
  const path = bestPath().slice(1);
  $('nsteps').textContent = path.length;
  const conds = m.conds;
  $('steps').innerHTML = path.length ? path.map((n) => `<li><span class="c">${esc(conds[n.cond] ? conds[n.cond][3] : '?')}</span>` +
    `<span class="v">${(n.score || 0).toFixed(2)}</span></li>`).join('')
    : '<li class="empty"><span class="c">no condition beats the plain root</span></li>';
  S.lit = -1;
  // gap / bound / best bars
  const st = r.tree, scale = Math.max(st.bound, 1e-6);
  const bar = (name, v, color) => `<div class="bar"><span>${name}</span><i style="--w:${Math.max(0, Math.min(100, 100 * v / scale)).toFixed(1)}%;--c:${color}"></i><span>${v.toFixed(2)}</span></div>`;
  $('bars').innerHTML = bar('GAP', st.bound - st.best, 'var(--amber)') + bar('BOUND', st.bound, 'rgba(70,255,154,.45)') + bar('BEST', st.best, 'var(--green)');
  // roots searched to the end vs left open
  $('roots').innerHTML = m.roots.map((x) => `<i class="${x.tree.open ? 'open' : ''}${x.id === r.id ? ' cur' : ''}" title="${esc(x.key)} ${C.variant(x)}"></i>`).join('');
  const complete = m.roots.filter((x) => !x.tree.open).length;
  $('rootsLegend').textContent = `${complete} SEARCHED TO THE END · ${m.roots.length - complete} OPEN · ${C.int(meta.nodes)} NODES IN ALL`;
  // the verdict
  const h = m.honesty, real = h.real || {}, plc = (h.placebo || []).map((p) => p.hold_pct);
  const held = best.holds, chance = C.beatsChance(h);
  const testTxt = te.n ? `TEST ${C.usd(te.mean)}/TRADE ON ${te.n} TRADES` : 'NO TEST TRADES';
  set('verdict', `THIS ROOT'S BEST: <b class="${held ? 'pos' : 'neg'}">${held ? 'HOLDS' : 'FAILS'}</b> OUT OF SAMPLE · ${testTxt}<br>` +
    `ALL ROOTS: <b>${real.hold}/${real.best_rules}</b> HOLD (${real.hold_pct}%)` +
    (plc.length ? ` · SHUFFLED CONDITIONS ${plc.map((p) => p + '%').join(' / ')} → <b class="${chance ? 'pos' : 'neg'}">${chance ? 'BEATS CHANCE' : 'CHANCE LEVEL'}</b>` : ''));
}

function lightSteps(lit) {
  document.querySelectorAll('#steps li').forEach((li, i) => li.classList.toggle('lit', i < lit));
}

function esc(s) { return String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c])); }

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
  g.fillStyle = BG; g.fillRect(0, 0, cv.width, cv.height);
  g.globalCompositeOperation = 'lighter';
  g.lineWidth = 0.7;
  for (const n of L.nodes) {
    const p = L.byId.get(n.parent);
    if (!p) continue;
    const [x1, y1] = C.place(p, geo), [x2, y2] = C.place(n, geo);
    g.strokeStyle = n.best ? 'rgba(225,255,235,.9)' : n.status === C.CUT ? 'rgba(60,120,90,.25)' : 'rgba(70,255,154,.32)';
    g.beginPath(); g.moveTo(x1, y1); g.quadraticCurveTo(x1, (y1 + y2) / 2, x2, y2); g.stroke();
  }
}

// ------------------------------------------------------------------------------------------------ cards
function showNode(n) {
  const m = S.model, r = S.root, sess = m.meta.sessions || {};
  S.selected = n;
  const path = ancestry(n).slice(1);
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
    const f = d / Math.max(1, gesture.pinch.d);
    zoomAt(mx, my, f);
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
document.querySelectorAll('.lens button').forEach((b) => b.addEventListener('click', () => {
  S.lens = b.dataset.lens;
  document.querySelectorAll('.lens button').forEach((x) => x.setAttribute('aria-checked', String(x === b)));
}));
$('replay').addEventListener('click', () => selectRoot(S.rootId));
$('openTop').addEventListener('click', showTop);
document.querySelectorAll('[data-close]').forEach((b) => b.addEventListener('click', () => { hideCard(); hideTop(); }));
$('toplist').addEventListener('click', (e) => {
  const li = e.target.closest('li[data-root]');
  if (!li) return;
  hideTop();
  if (S.model.trees[li.dataset.root]) selectRoot(li.dataset.root);
});
addEventListener('keydown', (e) => { if (e.key === 'Escape') { hideCard(); hideTop(); } });
addEventListener('resize', () => { if (S.model) resize(); });
addEventListener('hashchange', route);

function route() {
  const h = decodeURIComponent(location.hash.slice(1));
  if (h === 'top') { showTop(); return; }
  const id = h.startsWith('root=') ? h.slice(5) : null;
  if (id && id !== S.rootId && S.model.trees[id]) selectRoot(id);
}

function loop(now) {
  if (!(O ? O.hidden() : document.hidden)) {                    // hidden tab: no frame (the battery)
    const t0 = performance.now();
    frame(now);
    adapt(performance.now() - t0, now);
    if (O && O.state() === 'loading') O.ready();               // the first frame is drawn: the veil lifts
  }
  requestAnimationFrame(loop);
}

function adapt(ms, now) {
  // a frame that takes more than ~22 ms of drawing on a weak phone steps the quality down (fewer strands, lower dpr)
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
  const h = decodeURIComponent(location.hash.slice(1));
  selectRoot(h.startsWith('root=') ? h.slice(5) : S.model.featured[0]);
  if (h === 'top') showTop();
  postJarvis();
  window.__daphne = { ready: true, state: S };
  requestAnimationFrame(loop);
}

main();
