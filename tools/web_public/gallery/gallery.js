// AGORA GALLERY page (ES module; imports only gallerycore.js): the shelf, the name and meaning of the shape on the pedestal, the quality buttons and the 2D drawing that
// is always there. The 3D stage lives in stage.js (window.GALLERY3D); if it is missing or cannot start, this page still shows every shape as a drawing.
// Reads fixture.json only and sends nothing. Text only through textContent / createElementNS. window.GALLERY is the test hook.
import * as C from './gallerycore.js';

const O = window.OLYMPUS || null;
const $ = (id) => document.getElementById(id);
const NS = 'http://www.w3.org/2000/svg';
function h(tag, cls, text) { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = String(text); return e; }
function sv(tag, attrs) { const e = document.createElementNS(NS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); return e; }
const clear = (el) => { while (el.firstChild) el.removeChild(el.firstChild); };
const S = { items: [], i: 0, focus: false, mode: 'auto', sample: false, three: false, ready: false, buttons: {}, tiles: {} };

async function getJSON(url, ms) {
  const ac = typeof AbortController === 'function' ? new AbortController() : null, timer = ac ? setTimeout(() => ac.abort(), ms || 6000) : 0;
  try { const r = await fetch(url, { cache: 'no-cache', ...(ac ? { signal: ac.signal } : {}) }); return r.ok ? await r.json() : null; } catch (_) { return null; } finally { clearTimeout(timer); }
}
function say(t) { $('status').textContent = t; }
function drawGlyph(svg, id) {
  clear(svg);
  for (const [tag, attrs] of C.GLYPHS[id] || C.GLYPHS.doric) svg.appendChild(sv(tag, attrs));
}
function stage() { return window.GALLERY3D && window.GALLERY3D.ok ? window.GALLERY3D : null; }

function renderShelf() {
  const box = $('shelf'); clear(box); S.tiles = {};
  for (const grp of C.grouped(S.items)) {
    const sec = h('section'), grid = h('div', 'grid');
    sec.appendChild(h('h3', null, grp.name));
    for (const s of grp.items) {
      const b = h('button', 'shape'); b.type = 'button'; b.setAttribute('aria-pressed', 'false'); b.dataset.id = s.id;
      b.setAttribute('aria-label', `${s.name}. ${s.means}`);
      const svg = sv('svg', { viewBox: '0 0 64 64', fill: 'none', stroke: 'currentColor', 'stroke-width': '3', 'stroke-linecap': 'round', 'stroke-linejoin': 'round', 'aria-hidden': 'true' });
      drawGlyph(svg, s.id);
      b.appendChild(svg); b.appendChild(h('span', null, s.name));
      b.addEventListener('click', () => select(C.indexOf(S.items, s.id), true));
      grid.appendChild(b); S.tiles[s.id] = b;
    }
    sec.appendChild(grid); box.appendChild(sec);
  }
}
function renderQuality() {
  const box = $('quality'); clear(box); S.buttons = {};
  for (const m of C.MODES) {
    const b = h('button', 'btn', C.MODE_LABEL[m]); b.type = 'button'; b.dataset.mode = m; b.setAttribute('aria-pressed', String(m === S.mode));
    b.addEventListener('click', () => setMode(m));
    box.appendChild(b); S.buttons[m] = b;
  }
}
function liteNow() { const g = stage(); return g ? !!g.info().lite : true; }

function renderInfo() {
  const s = S.items[S.i]; if (!s) return;
  $('shapeGroup').textContent = s.group; $('shapeName').textContent = s.name; $('shapePos').textContent = C.position(S.i, S.items.length);
  $('shapeMeans').textContent = s.means;
  drawGlyph($('flatSvg'), s.id);
  for (const id in S.tiles) S.tiles[id].setAttribute('aria-pressed', String(id === s.id));
  $('focusBtn').setAttribute('aria-pressed', String(S.focus));
  $('focusBtn').textContent = S.focus ? 'Back to the shelf view' : 'Look closer';
  const g = stage(), info = g ? g.info() : null;
  if (info && info.both) {
    const here = info.lite ? info.both.lite : info.both.hd, other = info.lite ? info.both.hd : info.both.lite;
    $('tTris').textContent = C.fmt(here.tris); $('tTrisNote').textContent = `${info.lite ? 'Lite' : 'High'}; ${info.lite ? 'High' : 'Lite'} has ${C.fmt(other.tris)}`;
    $('tDraws').textContent = C.fmt(here.draws); $('tDrawsNote').textContent = `${info.lite ? 'Lite' : 'High'}; ${info.lite ? 'High' : 'Lite'} has ${C.fmt(other.draws)}`;
    $('qualityNote').textContent = C.qualityWords(info.lite);
    $('lite').hidden = !info.lite;
  } else {
    $('tTris').textContent = '-'; $('tTrisNote').textContent = '3D is not running'; $('tDraws').textContent = '-'; $('tDrawsNote').textContent = 'showing the drawing';
    $('qualityNote').textContent = 'Your device could not start 3D, so each shape is shown as a drawing. The shelf works the same.';
    $('lite').hidden = true;
  }
  for (const m in S.buttons) S.buttons[m].setAttribute('aria-pressed', String(m === S.mode));
  $('stageBox').classList.toggle('no3d', !g);
  $('hint').textContent = g ? (S.focus ? 'Close up. Drag to turn. Tap to step back.' : 'Drag to turn. Tap to look closer.') : 'A drawing of the shape (3D is not available here).';
  say(`${s.name}. ${C.position(S.i, S.items.length)}. ${s.means}`);
}

function select(i, focus) {
  S.i = C.step(i, 0, S.items.length);
  if (focus != null) S.focus = !!focus;
  const g = stage(), s = S.items[S.i];
  if (g) { g.show(s.id); g.setFocus(S.focus); }
  renderInfo();
  const t = S.tiles[s.id]; if (t && t.scrollIntoView && focus) { try { $('stageCard').scrollIntoView({ block: 'nearest', behavior: 'smooth' }); } catch (_) { /* fine */ } }
}
function toggleFocus() { S.focus = !S.focus; const g = stage(); if (g) g.setFocus(S.focus); renderInfo(); }
function setMode(m) {
  S.mode = C.MODES.indexOf(m) >= 0 ? m : 'auto';
  const g = stage(); if (g) g.setMode(S.mode);
  renderInfo();
  if (O && O.cue) { try { O.cue('tap'); } catch (_) { /* sound is optional */ } }
}

function waitFor3D(ms) {
  return new Promise((res) => {
    if (window.GALLERY3D) return res(window.GALLERY3D);
    const t = setTimeout(() => res(window.GALLERY3D || { ok: false, reason: 'timeout' }), ms);
    window.addEventListener('gallery:stage', () => { clearTimeout(t); res(window.GALLERY3D); }, { once: true });
  });
}

async function boot() {
  const q = new URLSearchParams(location.search);
  const fx = await getJSON('./fixture.json');
  S.items = C.shelf(fx); S.sample = !(fx && Array.isArray(fx.shapes) && fx.shapes.length);
  $('sample').hidden = !S.sample;
  const want = q.get('shape'); S.i = want ? C.indexOf(S.items, want) : 0;
  S.mode = C.MODES.indexOf(q.get('mode')) >= 0 ? q.get('mode') : 'auto';
  S.focus = q.get('focus') === '1';
  renderShelf(); renderQuality();
  $('prev').addEventListener('click', () => select(S.i - 1)); $('next').addEventListener('click', () => select(S.i + 1));
  $('focusBtn').addEventListener('click', toggleFocus);
  window.addEventListener('gallery:tap', toggleFocus);
  window.addEventListener('gallery:changed', () => { if (S.ready) renderInfo(); });
  window.addEventListener('keydown', (e) => { if (e.target && /INPUT|TEXTAREA|SELECT/.test(e.target.tagName)) return; if (e.key === 'ArrowLeft') select(S.i - 1); else if (e.key === 'ArrowRight') select(S.i + 1); });
  renderInfo();                                         // the drawing and the words are on screen before 3D is even asked
  S.ready = false; say('Loading the stage...');
  const g = await waitFor3D(12000);
  S.three = !!(g && g.ok);
  if (S.three && S.mode !== 'auto') g.setMode(S.mode);
  select(S.i, S.focus);
  S.ready = true;
  try { if (O && O.ready) O.ready(); } catch (_) { /* the veil lifts by itself */ }
}
window.GALLERY = { S, C, ready: () => S.ready, select, setMode, toggleFocus, liteNow };
boot().catch((e) => { say('Something went wrong: ' + (e && e.message ? e.message : e)); try { if (O && O.fail) O.fail('The gallery could not start'); } catch (_) { /* nothing */ } });
