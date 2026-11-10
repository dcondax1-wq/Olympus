// COMPASS page (ES module): the next best action. Reads ../home.json, ../money/index.json, ../ledger/rules.json, ../odeon/trades.json and fixture.json (DEMO, never blank); on this phone it READS the journal ratings
// ('journal.v1') and the Ledger ('ledger.v1') and keeps only its own Done / Snooze ('compass.state.v1'). Sends nothing; it only suggests. Text only through textContent / createElementNS. window.COMPASS is the test hook.
// ?demo=1&now=2026-11-10T14:00:00Z opens a given view.
import * as C from './compasscore.js';

const O = window.OLYMPUS || null;
const $ = (id) => document.getElementById(id);
const NS = 'http://www.w3.org/2000/svg';
const SKEY = 'compass.state.v1';
function h(tag, cls, text) { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = String(text); return e; }
function sv(tag, attrs, text) { const e = document.createElementNS(NS, tag); for (const k in attrs || {}) e.setAttribute(k, String(attrs[k])); if (text != null) e.textContent = String(text); return e; }
const clear = (el) => { while (el.firstChild) el.removeChild(el.firstChild); };
const S = { inp: null, list: [], plan: null, state: {}, now: 0, demo: false, forced: false, rose: null, mode: 'flat', ready: false, reason: '', found: [] };
const TONE = { bad: 'bad', warn: 'warn', info: 'info', ok: 'ok' };

async function getJSON(url, ms) {
  const ac = typeof AbortController === 'function' ? new AbortController() : null, timer = ac ? setTimeout(() => ac.abort(), ms || 6000) : 0;
  try { const r = await fetch(url, { cache: 'no-cache', ...(ac ? { signal: ac.signal } : {}) }); return r.ok ? await r.json() : null; } catch (_) { return null; } finally { clearTimeout(timer); }
}
function say(t) { $('status').textContent = t; }
function loadState() { try { return C.cleanState(JSON.parse(localStorage.getItem(SKEY) || '{}')); } catch (_) { return {}; } }
function saveState(v) { try { localStorage.setItem(SKEY, JSON.stringify(v)); } catch (_) { /* private window: the page works without it */ } }
function readLS(k) { try { return localStorage.getItem(k); } catch (_) { return null; } }

function renderFlat(deg) {
  const svg = $('flat'); clear(svg);
  svg.appendChild(sv('circle', { cx: 100, cy: 100, r: 92, fill: '#d9d2c3', stroke: '#9c6b3c', 'stroke-width': 5 }));
  svg.appendChild(sv('circle', { cx: 100, cy: 100, r: 56, fill: 'none', stroke: '#9c6b3c', 'stroke-width': 1.5 }));
  [[0, '#c8a24a'], [90, '#9c6b3c'], [180, '#9c6b3c'], [270, '#9c6b3c']].forEach(([a, col]) => svg.appendChild(sv('path', { d: 'M100 12 L112 78 L100 100 L88 78 Z', fill: col, transform: `rotate(${a} 100 100)` })));
  [['N', 100, 24], ['E', 178, 104], ['S', 100, 184], ['W', 22, 104]].forEach(([t, x, y]) => svg.appendChild(sv('text', { x, y, 'text-anchor': 'middle', 'font-size': 14, 'font-weight': 700, fill: '#5a4326' }, t)));
  const g = sv('g', { class: 'needle', style: `transform: rotate(${deg}deg)` }); g.dataset.deg = String(deg);
  g.appendChild(sv('path', { d: 'M100 22 L108 100 L100 108 L92 100 Z', fill: '#e0b868', stroke: '#7a5a22', 'stroke-width': 1.5 }));
  g.appendChild(sv('path', { d: 'M100 178 L108 100 L100 92 L92 100 Z', fill: '#c96a4a', stroke: '#7a3a24', 'stroke-width': 1.5 }));
  g.appendChild(sv('circle', { cx: 100, cy: 100, r: 7, fill: '#9c6b3c', stroke: '#4a3a28', 'stroke-width': 2 }));
  svg.appendChild(g);
}

function actBtns(box, a, quiet) {
  const b = (label, aria, fn) => { const x = h('button', 'btn', label); x.type = 'button'; x.setAttribute('aria-label', aria); x.addEventListener('click', fn); box.appendChild(x); };
  if (quiet) { b('Bring back', `Bring back: ${a.title}`, () => act(a.key, 'back')); return; }
  b('Done', `Mark done: ${a.title}`, () => act(a.key, 'done'));
  b(`Snooze ${C.SNOOZE_HOURS} h`, `Snooze for ${C.SNOOZE_HOURS} hours: ${a.title}`, () => act(a.key, 'snooze'));
}

function act(key, how) {
  const now = S.now;
  S.state = how === 'done' ? C.markDone(S.state, key, now) : how === 'snooze' ? C.snooze(S.state, key, now) : C.clearKey(S.state, key);
  saveState(S.state);
  render();
  say(how === 'back' ? 'Brought back.' : how === 'done' ? 'Done. It stays hidden for today unless it changes.' : `Snoozed for ${C.SNOOZE_HOURS} hours.`);
}

function actCard(a, rank, quiet) {
  const li = h('li', 'act ' + (TONE[a.tone] || '')), row = h('div', 'row');
  row.appendChild(h('b', '', `${rank ? rank + '. ' : ''}${a.title}`));
  row.appendChild(h('span', 'pill tagpill ' + (a.tag === 'usd' ? 'warn' : 'ok'), a.tag === 'usd' ? `${C.money(a.usd)} (est.)` : 'free'));
  li.appendChild(row); li.appendChild(h('p', '', a.why));
  const bx = h('div', 'btns'); actBtns(bx, a, quiet); li.appendChild(bx);
  return li;
}

function renderTop(a) {
  const top = $('top'), why = $('why'), tag = $('tag'), pill = $('pill'), bx = $('topBtns'); clear(bx);
  if (!a) {
    const hl = C.headline(S.plan);
    top.textContent = hl.title; why.textContent = hl.why; tag.textContent = ''; pill.textContent = 'All quiet'; pill.className = 'pill ok'; return;
  }
  top.textContent = a.title; why.textContent = a.why; tag.textContent = `Rule: ${a.rule}. Cost or gain: ${C.tagText(a)}. Urgency ${a.urgency} of 100.`;
  pill.textContent = { bad: 'Act now', warn: 'Soon', info: 'When you can', ok: 'Waiting is the action' }[a.tone]; pill.className = 'pill ' + (TONE[a.tone] || '');
  actBtns(bx, a, false);
}

function renderHow() {
  const ul = $('how'); clear(ul);
  for (const r of C.ruleTable()) {
    const li = h('li', 'rule'); const row = h('div', 'row'); row.appendChild(h('b', '', r.name)); row.appendChild(h('span', 'pill ' + (r.tag === 'usd' ? 'warn' : 'ok'), r.tag === 'usd' ? '$ estimate' : 'free'));
    li.appendChild(row); li.appendChild(h('small', '', r.when)); ul.appendChild(li);
  }
  $('inputs').textContent = S.demo ? 'These are example inputs (DEMO). Once the site\'s own files are there, Compass uses them.' : `Files found: ${S.found.length ? S.found.join(', ') : 'none'}.`;
}

function render() {
  S.list = C.actions(C.context(S.inp, S.now));
  S.plan = C.plan(S.list, S.state, S.now);
  const p = S.plan, a = p.top[0] || null;
  $('demo').hidden = !S.demo; try { $('lite').hidden = !(O && O.lite && O.lite()); } catch (_) { $('lite').hidden = true; }
  renderTop(a); renderFlat(C.bearing(a));
  if (S.rose && S.rose.ok) S.rose.set({ bearing: C.bearing(a) });
  const ul = $('acts'); clear(ul);
  p.top.slice(1).forEach((x, i) => ul.appendChild(actCard(x, i + 2, false)));
  if (!p.top.slice(1).length) ul.appendChild(h('li', 'note', a ? 'Nothing else needs you today.' : 'Nothing is open.'));
  const qc = $('quietCard'), q = $('quiet'); clear(q); qc.hidden = !p.quiet.length; p.quiet.forEach((x) => q.appendChild(actCard(x, 0, true)));
  renderHow();
  const hl = C.headline(p);
  say(a ? `Compass: ${a.title}. ${C.tagText(a)}.` : `Compass: ${hl.title}.`);
  try { if (O && O.ready) O.ready(); } catch (_) { /* the veil lifts by itself */ }
}

// rose.js is loaded by its own module tag (needleload.js) so the page still works when three.js or WebGL is missing: wait for it (6 s at most), else keep the flat compass
function waitRose() {
  return new Promise((resolve, reject) => {
    if (window.__compassRose) { resolve(window.__compassRose); return; }
    const done = (v, e) => { clearTimeout(tm); window.removeEventListener('compass-rose', on); if (e) reject(e); else resolve(v); };
    const on = () => done(window.__compassRose);
    const tm = setTimeout(() => done(null, new Error('the 3D compass did not load')), 6000);
    window.addEventListener('compass-rose', on);
  });
}
async function startRose() {
  const canvas = $('stage'), flat = $('flat');
  let T = null;
  try { T = await waitRose(); } catch (e) { S.reason = String(e && e.message ? e.message : e); }
  const reduced = (() => { try { return matchMedia('(prefers-reduced-motion: reduce)').matches; } catch (_) { return false; } })();
  if (T) {
    let t = null;
    try { t = T.createRose(canvas, { reduced }); } catch (e) { S.reason = String(e && e.message ? e.message : e); }
    if (t && t.ok) { S.rose = t; S.mode = '3d'; canvas.hidden = false; flat.setAttribute('hidden', ''); t.set({ bearing: C.bearing(S.plan.top[0]) }); document.documentElement.dataset.compass = '3d'; return; }
    if (t && t.reason) S.reason = t.reason;
  }
  S.mode = 'flat'; canvas.hidden = true; flat.removeAttribute('hidden'); document.documentElement.dataset.compass = 'flat';
}

async function boot() {
  const q = new URLSearchParams(location.search); S.forced = q.get('demo') === '1';
  const nowQ = Date.parse(q.get('now') || ''); S.now = Number.isFinite(nowQ) ? nowQ : Date.now();
  const [fx, home, money, rules, odeon] = await Promise.all([getJSON('./fixture.json'), S.forced ? null : getJSON('../home.json'), S.forced ? null : getJSON('../money/index.json'),
    S.forced ? null : getJSON('../ledger/rules.json'), S.forced ? null : getJSON('../odeon/trades.json')]);
  S.found = [['home.json', home], ['money/index.json', money], ['ledger/rules.json', rules], ['odeon/trades.json', odeon]].filter((x) => x[1]).map((x) => x[0]);
  const real = !S.forced && (S.found.length > 0);
  S.demo = !real;
  S.inp = real ? { home, money, rules, odeon, journal: readLS('journal.v1'), ledger: readLS('ledger.v1') } : C.demoInputs(fx, S.now);
  S.state = loadState();
  render();
  await startRose();
  S.ready = true;
}
window.COMPASS = { S, C, ready: () => S.ready, render, get mode() { return S.mode; }, get rose() { return S.rose; } };
boot().catch((e) => { say('Something went wrong: ' + (e && e.message ? e.message : e)); try { if (O && O.fail) O.fail('Compass could not start'); } catch (_) { /* nothing */ } });
