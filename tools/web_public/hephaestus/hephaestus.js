// HEPHAESTUS page (ES module): loads data.json (the stored backtest runs, cut by tools/hephaestus_build.py), or the recorded fixture.json (DEMO),
// draws the forge (scene.js) and lets you turn dials. Text only through textContent. Reads only: nothing is sent anywhere, nothing is written
// to the bot. window.HEPH is the test hook.
import { find, byId, tested, anyTested, verdict, table, summary, usd, dec, KIND_COLOR, HALVES } from './hephaestuscore.js';

const O = window.OLYMPUS || null;
const $ = (id) => document.getElementById(id);
const KEY = 'hephaestus.v1';
const S = { data: null, demo: true, dials: {}, sc: null, v: null, scene: null, ready: false, error: null, msg: '' };

function h(tag, cls, text) { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = String(text); return e; }
const store = {
  read() { try { const v = JSON.parse(localStorage.getItem(KEY) || 'null'); return v && typeof v === 'object' ? v : {}; } catch (_) { return {}; } },
  write(v) { try { localStorage.setItem(KEY, JSON.stringify(v)); } catch (_) { /* private mode */ } },
};
async function getJSON(url, ms = 6000) {
  const ac = typeof AbortController === 'function' ? new AbortController() : null, timer = ac ? setTimeout(() => ac.abort(), ms) : 0;
  try { const r = await fetch(url, { cache: 'no-cache', ...(ac ? { signal: ac.signal } : {}) }); return r.ok ? await r.json() : null; } catch (_) { return null; } finally { clearTimeout(timer); }
}
const valid = (d) => !!(d && Array.isArray(d.dials) && Array.isArray(d.scenarios) && d.scenarios.length && d.live && d.live_id);

// ------------------------------------------------------------------------------------------------ dials
function buildDials() {
  const box = $('dials'); box.replaceChildren();
  for (const d of S.data.dials) {
    const g = h('div', 'dial'); g.dataset.dial = d.id;
    const lab = h('span', 'dl', d.label); g.append(lab);
    const chips = h('div', 'chips'); chips.setAttribute('role', 'group'); chips.setAttribute('aria-label', d.label);
    for (const o of d.options) {
      const b = h('button', 'chip', o.label); b.type = 'button'; b.dataset.dial = d.id; b.dataset.v = o.v;
      if (o.live) b.classList.add('live');
      b.addEventListener('click', () => choose(d.id, o.v));
      chips.append(b);
    }
    g.append(chips); box.append(g);
  }
}
function paintDials() {
  for (const b of $('dials').querySelectorAll('.chip')) {
    const id = b.dataset.dial, v = b.dataset.v, on = S.dials[id] === v, ok = tested(S.data, S.dials, id, v);
    b.setAttribute('aria-pressed', String(on));
    b.classList.toggle('nt', !ok);
    b.setAttribute('aria-disabled', String(!ok));
    b.title = ok ? '' : 'Not tested';
  }
}
function choose(id, v) {
  if (S.dials[id] === v) return;
  if (!tested(S.data, S.dials, id, v)) {
    const never = !anyTested(S.data, id, v);
    S.msg = never ? 'Not tested: no stored run has this.' : 'Not tested with the other dials as they are.';
    $('msg').textContent = S.msg; return;
  }
  S.dials = { ...S.dials, [id]: v };
  S.msg = ''; $('msg').textContent = '';
  store.write({ dials: S.dials });
  render(true);
}

// ------------------------------------------------------------------------------------------------ the numbers
function renderTable() {
  const body = $('rows'); body.replaceChildren();
  const sc = S.sc;
  if (!sc) { const tr = h('tr'), td = h('td', '', 'Not tested'); td.colSpan = 3; tr.append(td); body.append(tr); return; }
  for (const r of table(S.data, sc)) {
    const tr = h('tr'); tr.dataset.row = r.k; tr.append(h('td', '', r.label));
    for (const hf of HALVES) {
      const c = r.cells[hf], td = h('td', c.cls); td.dataset.half = hf;
      td.append(h('b', '', c.v));
      if (!c.same) td.append(h('i', '', 'live ' + c.ref));
      tr.append(td);
    }
    body.append(tr);
  }
}
function render(strike) {
  const sc = find(S.data, S.dials);
  S.sc = sc; S.v = verdict(S.data, sc);
  paintDials(); renderTable();
  const v = S.v;
  $('vh').textContent = v.head; $('vp').textContent = v.plain;
  $('vs').textContent = v.flags.length ? v.flags.join(' ') : (sc ? summary(S.data, sc) : '');
  const col = KIND_COLOR[v.kind] || KIND_COLOR.none;
  $('verdict').dataset.kind = v.kind; $('verdict').style.setProperty('--vk', col);
  document.documentElement.dataset.kind = v.kind;
  const live = byId(S.data, S.data.live_id);
  $('src').textContent = sc ? `Stored run: ${sc.run}${sc.base_confirm ? ` (1m confirm window ${sc.base_confirm})` : ''}. ${sc.label}.` : 'No stored run for this mix of dials.';
  $('ref2125').textContent = sc && sc.ref2125 && sc.ref2125.net != null ? `2021-25 for reference only (never a gate): ${usd(sc.ref2125.net)}, PF ${dec(sc.ref2125.pf)}, ${dec(sc.ref2125.tpw)} trades a week.` : '';
  if (S.scene) {
    const ratio = sc && live && live.y26 && live.y26.net > 0 ? Math.sqrt(Math.max(0.01, sc.y26.net / live.y26.net)) : 1;
    S.scene.setState({ color: col, scale: sc ? ratio : 0.5, kind: v.kind });
    if (strike) S.scene.strike();
  }
}
function renderRejected() {
  const box = $('rej'); box.replaceChildren();
  for (const r of S.data.rejected || []) { const c = h('div', 'card'); c.append(h('b', '', r.title), h('span', '', r.text)); box.append(c); }
}

// ------------------------------------------------------------------------------------------------ Jarvis card
function card() {
  const live = S.data ? byId(S.data, S.data.live_id) : null, y = (live && live.y26) || {}, h2 = (live && live.h2) || {};
  return { v: 1, name: 'Hephaestus', status: { level: S.demo ? 'off' : 'ok', label: S.demo ? 'Demo data' : 'Read-only workshop' },
    kpis: [{ label: '2026 net (live)', value: usd(y.net) }, { label: 'Jul-Oct PF', value: dec(h2.pf) }, { label: 'Trades / week', value: dec(y.tpw) }],
    lines: ['Turn a dial: stored 2026 results, Jan-Jun against Jul-Oct.', 'It changes nothing in the bot.'], t: Math.floor(Date.now() / 1000), open: '#dials', theme: '#0b0608', stale_after: 2592000 };
}
function postCard() {
  if (S.demo || !O || !O.framed) return;
  try { window.parent.postMessage({ jarvis: 1, href: location.href, card: card() }, 'https://demetrades2000-coder.github.io'); } catch (_) { /* not inside Jarvis */ }
}

// ------------------------------------------------------------------------------------------------ start
async function startScene() {
  try {
    const { createForge } = await import('./scene.js');
    S.scene = createForge($('view'), { O });
    $('lite').hidden = !S.scene.lite();
    S.scene.onQuality(() => { $('lite').hidden = !S.scene.lite(); });
  } catch (e) {
    S.error = 'scene: ' + ((e && e.message) || e);
    document.documentElement.dataset.noscene = '1';
    if (O) O.ready();
  }
}

async function main() {
  const scene = startScene();
  let data = await getJSON('data.json');
  S.demo = false;
  if (!valid(data)) { data = await getJSON('fixture.json'); S.demo = true; }
  if (!valid(data)) { S.error = 'no data'; $('honest').textContent = 'No stored results could be loaded. Nothing is changed in the bot.'; await scene; if (O) O.ready(); document.body.dataset.ready = '1'; return; }
  S.data = data; S.demo = S.demo || !!data.demo;
  $('demo').hidden = !S.demo;
  const saved = store.read().dials;
  S.dials = { ...data.live };
  if (saved && typeof saved === 'object' && find(data, { ...data.live, ...saved })) S.dials = { ...data.live, ...saved };
  buildDials(); renderRejected();
  $('reset').addEventListener('click', () => { S.dials = { ...S.data.live }; S.msg = ''; $('msg').textContent = ''; store.write({ dials: S.dials }); render(true); });
  render(false);
  await scene;
  if (S.scene) render(false);
  S.ready = true;
  document.body.dataset.ready = '1';
  postCard();
}

window.HEPH = {
  state: () => ({ ready: S.ready, demo: S.demo, dials: { ...S.dials }, scenario: S.sc ? S.sc.id : null, run: S.sc ? S.sc.run : null, verdict: S.v ? { kind: S.v.kind, head: S.v.head } : null,
    scene: S.scene ? S.scene.stats() : null, error: S.error, msg: S.msg }),
  set: (id, v) => choose(id, v),
  card,
};
main().catch((e) => { S.error = String((e && e.message) || e); document.body.dataset.ready = '1'; if (O) O.ready(); });
