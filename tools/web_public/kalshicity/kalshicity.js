// KALSHI CITY page (ES module): loads edges.json + learning_log.json (the learning engine, tools/kalshi_edges.py) and the bot's live numbers (the public
// kalshi-feed), shapes them (cityfeed.js), lays the city out (citylayout.js), draws it (cityscene.js) and writes the words. Text only through
// textContent (no data ever becomes HTML). Read only: nothing here writes anywhere. window.KC is the test hook.
import { RAW, shape, cardOf, headlineOf, usd, pct, evf, pts, STATUS_COLOR, STATUS_WORD, ADVICE, etHour, clockLabel, phaseWord, MIN_N } from './cityfeed.js';
import { layout } from './citylayout.js';

const O = window.OLYMPUS || null;
const $ = (id) => document.getElementById(id);
const S = { model: null, L: null, demo: true, scene: null, view: '', ready: false, error: null, sel: null, logMore: 40, liveFailed: false, preview: null };
const reduced = () => (O ? O.reduced() : !!(window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches));
function h(tag, cls, text) { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = String(text); return e; }
const kids = (el, ...c) => { el.replaceChildren(...c.flat().filter(Boolean)); return el; };

async function getJSON(url, ms = 7000) {
  const ac = typeof AbortController === 'function' ? new AbortController() : null, timer = ac ? setTimeout(() => ac.abort(), ms) : 0;
  try { const r = await fetch(url, { cache: 'no-cache', ...(ac ? { signal: ac.signal } : {}) }); return r.ok ? await r.json() : null; } catch (_) { return null; } finally { clearTimeout(timer); }
}
const dollars = (x) => usd(x);
const smoney = (x) => (x == null ? '-' : `${x < 0 ? '-' : '+'}$${Math.abs(x).toFixed(2)}`);
const dotOf = (e) => { const d = h('span', 'dot'); d.style.background = e.small ? '#8b93a7' : STATUS_COLOR[e.status]; return d; };

// ------------------------------------------------------------------------------------------------ the top card
function renderTop() {
  const m = S.model, bk = m.book;
  $('vText').textContent = headlineOf(m);
  $('oMore').textContent = String(m.counts.doMore);
  $('oStop').textContent = String(m.counts.stop);
  $('oRuin').textContent = bk.ruinNow == null ? '-' : bk.ruinNow >= 0.995 ? '~100%' : pct(bk.ruinNow, 0);
  const bot = [`${bk.name}: ${bk.status || bk.mode || 'unknown'}`, bk.balance != null ? `bankroll ${dollars(bk.balance)}` : '', bk.week != null ? `week ${smoney(bk.week)}` : ''].filter(Boolean).join(' · ');
  const led = m.ledger;
  const seen = led && led.n ? ` · learned from ${led.n}${led.bets_total ? ` of ${led.bets_total.toLocaleString('en-US')}` : ''} bets read one by one, the rest from the bot's totals` : '';
  const age = m.age > 3 * 86400 ? ` · learning is ${Math.floor(m.age / 86400)} days old` : '';
  $('bot').textContent = `${bot}${seen}${age}`;
  $('bot').hidden = false;
  const wx = $('wx'), r = m.regime;
  wx.textContent = `${{ clear: 'Clear', overcast: 'Overcast', rain: 'Rain', storm: 'Storm' }[r.state]}${r.paused ? ' · bot paused (fog)' : ''}`;
  wx.dataset.wx = r.state; wx.title = r.why;
  $('demo').hidden = !S.demo;
}
function renderClock() {
  const hr = S.scene ? S.scene.hour() : (S.preview != null ? S.preview : etHour());
  const c = $('clock');
  c.textContent = `${clockLabel(hr)} ET · ${phaseWord(hr)}${S.preview != null ? ' (preview)' : ''}`;
  c.classList.toggle('preview', S.preview != null);
}

// ------------------------------------------------------------------------------------------------ sheets
const TITLES = { learn: 'What the city learned', board: 'Leaderboard: the best edges', moves: 'Do more · Stop doing', risk: 'Risk and sizing', guide: 'How to read the city', card: '' };

function edgeRow(e, i, extra) {
  const b = h('button', `row-btn${e.small ? ' grey' : ''}`); b.type = 'button'; b.dataset.id = e.id;
  const nm = h('span', 'nm'); nm.append(dotOf(e), document.createTextNode(e.label));
  const sm = h('small', '', `${e.n} bets${e.small ? ' (too few)' : ''} · ${e.status.toLowerCase()}${extra ? ` · ${extra}` : ''}`); nm.append(sm);
  b.append(h('span', 'rk', i == null ? '' : String(i + 1)), nm, h('span', 'ev', e.ev == null ? '-' : evf(e.ev)));
  b.addEventListener('click', () => selectEdge(e.id, true));
  return b;
}
function listOf(ids, make, empty) {
  const ul = h('ul', 'list');
  if (!ids.length) return h('p', '', empty);
  ids.forEach((id, i) => { const e = S.model.byId.get(id); if (e) { const li = h('li'); li.append(make(e, i)); ul.append(li); } });
  return ul;
}

function learnView() {
  const m = S.model, log = m.log.slice().reverse();
  const ul = h('ul', 'list log');
  log.slice(0, S.logMore).forEach((x) => {
    const li = h('li'), bar = h('span', 'bar');
    bar.style.background = x.advice ? ADVICE[x.advice].color : 'rgba(255,255,255,.25)';
    const body = h('div');
    body.append(h('small', '', `${x.d}${x.kind === 'run' ? ' · read' : ''}`));
    if (x.id && m.byId.has(x.id)) { const b = h('button', '', x.text); b.type = 'button'; b.addEventListener('click', () => selectEdge(x.id, true)); body.append(b); } else body.append(document.createTextNode(x.text));
    li.append(bar, body); ul.append(li);
  });
  const out = [h('p', 'strong', 'Every time the engine re-measures the bets, what it learned is written here with the date. Old lines are never rewritten.'), log.length ? ul : h('p', '', 'Nothing learned yet.')];
  if (log.length > S.logMore) { const b = h('button', 'more', `Show ${Math.min(40, log.length - S.logMore)} more`); b.type = 'button'; b.addEventListener('click', () => { S.logMore += 40; openSheet('learn'); }); out.push(b); }
  return out;
}
function boardView() {
  const m = S.model;
  const small = m.edges.filter((e) => e.small && e.size === 1).sort((a, b) => b.n - a.n).slice(0, 6).map((e) => e.id);
  return [h('p', 'strong', 'The edges with the biggest proven lead over the market (win rate low end minus the market\'s own odds). Tap one to fly to its building.'),
    listOf(m.lists.board.slice(0, 15), (e, i) => edgeRow(e, i), 'No edge has 30 bets yet.'),
    small.length ? h('h3', '', 'Too few bets to rank (grey)') : null, small.length ? listOf(small, (e) => edgeRow(e, null), '') : null];
}
function movesView() {
  const m = S.model, L = m.lists;
  return [h('h3', '', `Do more (${m.counts.doMore})`), h('p', '', 'Proven to beat the odds, and worth a stake. The stake is a quarter of a conservative Kelly, never more.'),
    listOf(L.doMore, (e, i) => edgeRow(e, i, e.stake ? `stake ${usd(e.stake)}` : ''), 'Nothing is proven strongly enough yet. That is the honest answer for now.'),
    h('h3', '', `Stop doing (${m.counts.stop})`), h('p', '', 'Proven to lose money, or losing in every window.'),
    listOf(L.stop, (e, i) => edgeRow(e, i, `lost ${usd(Math.abs(e.pnl || 0))}`), 'Nothing is proven to lose yet.'),
    h('h3', '', `Watch (${m.counts.watch})`), h('p', '', 'Fading, or losing but not yet proven. Do not add size.'),
    listOf(L.watch.slice(0, 8), (e, i) => edgeRow(e, i), 'None.')];
}
function riskView() {
  const bk = S.model.book, rows = h('ul', 'kv');
  const add = (k, v, tone) => { const li = h('li', tone || ''); li.append(h('span', 'k', k), h('span', 'v', v)); rows.append(li); };
  add('Bankroll', bk.balance == null ? '-' : dollars(bk.balance));
  add('Average bet', bk.stakeAvg == null ? '-' : `${dollars(bk.stakeAvg)}${bk.stakeFrac != null ? ` (${pct(bk.stakeFrac, 0)} of the bankroll)` : ''}`, bk.stakeFrac > 0.1 ? 'bad' : '');
  add('Win rate / break-even', bk.w == null ? '-' : `${pct(bk.w)} / ${pct(bk.p)}`);
  add('Profit per $1 staked', bk.ev == null ? '-' : `${evf(bk.ev)} after fees`, bk.ev > 0 ? 'ok' : 'bad');
  add('Kelly for the whole book', bk.kellyBook == null ? '-' : bk.kellyBook > 0 ? pct(bk.kellyBook) : 'none: no edge overall', bk.kellyBook > 0 ? 'ok' : 'bad');
  add('Chance of losing half at this bet size', bk.ruinNow == null ? '-' : bk.ruinNow >= 0.995 ? 'about 100%' : `up to ${pct(bk.ruinNow, 0)}`, bk.ruinNow > 0.3 ? 'bad' : '');
  add('...at a quarter Kelly', bk.ruinKelly == null ? '-' : `up to ${pct(bk.ruinKelly, 1)}`, 'ok');
  add('Last 7 days / 30 days', `${smoney(bk.pnl7)} / ${smoney(bk.pnl30)}`);
  add('Worst day / best day', `${bk.worstDay == null ? '-' : usd(bk.worstDay)} / ${bk.bestDay == null ? '-' : usd(bk.bestDay)}`);
  const lines = [];
  if (bk.stakeFrac > 0.1) lines.push('Each bet is a big slice of the bankroll. When almost every bet wins, one loss costs as much as many wins; sizing down is the safest change.');
  if (bk.kellyBook != null && bk.kellyBook <= 0) lines.push('Across everything the bot has done, wins have not beaten the break-even rate after fees. Only the proven edges (Moves) deserve a stake.');
  return [h('p', 'strong', 'Kelly says how much of the bankroll an edge deserves. "Losing half" is an upper bound for the chance the bankroll ever falls to half while betting that size.'), rows,
    ...lines.map((t) => h('p', 'warnbox', t)), h('p', '', 'A what-if on the bot\'s own numbers. It never places or changes an order.')];
}
function guideView() {
  const lg = (color, text) => { const d = h('div', 'legend'); const sw = h('span', 'sw'); sw.style.background = color; d.append(sw, h('span', '', text)); return d; };
  return [h('p', 'strong', 'Each building is one edge: a slice of the bot\'s bets (a strategy, a market, a price band, an hour, yes or no, or a mix).'),
    lg('#ffd86a', 'Height: profit per $1 staked (after fees). A losing edge is a low stub.'),
    lg('#35f0b0', 'Roof glow: the recent win rate. Roof colour is the status: green growing, gold holding, orange fading, red dead, blue new.'),
    lg('#ffcf5a', 'Windows: the bets. Gold windows won, red windows lost.'),
    lg('#8b93a7', 'Grey and low: fewer than 30 bets. Too few to trust: no verdict, no stake.'),
    lg('#8f9bff', 'Going up with a crane: a new edge. Crumbling with embers: one that just died.'),
    lg('#2ef2d0', 'Roads: capital out (cool cars), bets that came back (gold won, red lost). Pink cars are the bot\'s open orders.'),
    lg('#ff9a3c', 'Weather is the last 7 days: clear, overcast, rain, storm. Fog means the bot is paused. Day and night follow New York time.'),
    lg('#ffe08a', 'The gold beam marks the best proven edge. The red/green lighthouse shows the risk of ruin.'),
    h('p', 'warnbox', 'The dark towers far away are scenery: they carry no data. Only buildings inside a district are real edges.'),
    S.startedDemo ? null : demoButton(),
    h('p', '', `The engine re-measures every edge each time it runs: win rate against the market's odds, profit per $1, a 95% range, a luck test (z), the last 7 and 30 days, and a Kelly stake. Anything under ${MIN_N} bets stays grey. Read only: it never places or changes an order.`)];
}
function demoButton() {
  const b = h('button', 'more', S.showingDemo ? 'Back to the real city' : 'Preview the demo city (invented bets, after weeks of learning)'); b.type = 'button';
  b.addEventListener('click', () => showDemo(!S.showingDemo));
  return b;
}
async function showDemo(on) {
  if (on) {
    S.fx = S.fx || await getJSON('fixture.json', 12000);
    if (!S.fx) return;
    S.real = S.model; S.model = shape(S.fx.edges, { entries: S.fx.log }, null);
  } else if (S.real) S.model = S.real;
  S.showingDemo = !!on; S.demo = S.startedDemo || !!on; S.sel = null; S.L = layout(S.model);
  if (S.scene) { S.scene.select(null); S.scene.rebuild(S.model, S.L); }
  renderTop(); openSheet('guide');
}
function cardView() {
  const e = S.model.byId.get(S.sel); if (!e) return [h('p', '', 'Select a building.')];
  const c = cardOf(e, S.model.book), rows = h('ul', 'kv');
  c.rows.forEach(([k, v, tone]) => { const li = h('li', tone || ''); li.append(h('span', 'k', k), h('span', 'v', v)); rows.append(li); });
  const st = h('span', 'badge', e.small ? 'NEW' : e.status); st.style.color = e.small ? '#8b93a7' : STATUS_COLOR[e.status];
  const ad = h('span', 'badge', c.advice.word); ad.style.color = c.advice.color;
  const pr = h('div', 'pillrow'); pr.append(st, ad);
  return [pr, c.banner ? h('p', 'warnbox', c.banner) : null, h('p', 'strong', `${c.statusWord}. ${c.advice.text}`), rows];
}

function openSheet(view) {
  S.view = view;
  const e = view === 'card' ? S.model.byId.get(S.sel) : null;
  $('sheetTitle').textContent = view === 'card' ? (e ? e.label : '') : TITLES[view];
  kids($('sheetBody'), view === 'learn' ? learnView() : view === 'board' ? boardView() : view === 'moves' ? movesView() : view === 'risk' ? riskView() : view === 'guide' ? guideView() : cardView());
  $('sheet').hidden = false;
  $('sheetBody').scrollTop = 0;
  document.querySelectorAll('#pills button').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.view === view)));
  try { history.replaceState(null, '', view === 'card' ? location.pathname + location.search : '#' + view); } catch (_) { /* framed */ }
}
function closeSheet() {
  S.view = ''; $('sheet').hidden = true;
  document.querySelectorAll('#pills button').forEach((b) => b.setAttribute('aria-pressed', 'false'));
  if (S.sel) { S.sel = null; if (S.scene) S.scene.select(null); }
  try { history.replaceState(null, '', location.pathname + location.search); } catch (_) { /* framed */ }
}
function selectEdge(id, fly) {
  if (!id || !S.model.byId.has(id)) { if (S.view === 'card') closeSheet(); return; }
  S.sel = id;
  if (S.scene) { S.scene.select(id); if (fly) S.scene.focus(id); }
  openSheet('card');
}

// ------------------------------------------------------------------------------------------------ Jarvis card
function card() {
  const m = S.model, bk = m.book;
  return { v: 1, name: 'Kalshi City', status: { level: S.demo ? 'off' : (m.regime.state === 'rain' || m.regime.state === 'storm' ? 'warn' : 'ok'), label: S.demo ? 'Demo data' : `${m.counts.doMore} do more · ${m.counts.stop} stop` },
    kpis: [{ label: 'Do more', value: String(m.counts.doMore) }, { label: 'Stop', value: String(m.counts.stop) }, { label: 'Ruin risk', value: bk.ruinNow == null ? '-' : pct(bk.ruinNow, 0) }],
    lines: [headlineOf(m).slice(0, 120), `Bot ${bk.status || bk.mode}: bankroll ${bk.balance == null ? '-' : dollars(bk.balance)}. Weather: ${m.regime.state}.`.slice(0, 120)],
    t: Math.floor(Date.now() / 1000), open: '#learn', theme: '#06100f', stale_after: 259200 };
}
function postCard() {
  if (S.demo || !O || !O.framed) return;
  try { window.parent.postMessage({ jarvis: 1, href: location.href, card: card() }, 'https://demetrades2000-coder.github.io'); } catch (_) { /* not inside Jarvis */ }
}

// ------------------------------------------------------------------------------------------------ start
async function startScene() {
  try {
    const { createCity } = await import('./cityscene.js');
    S.scene = createCity($('city'), { O, model: S.model, layout: S.L });
    $('lite').hidden = !S.scene.lite();
    S.scene.onQuality(() => { $('lite').hidden = !S.scene.lite(); });
    S.scene.onPick((id) => { if (id) selectEdge(id, false); else if (S.view === 'card') closeSheet(); });
    S.scene.onMode((k) => document.querySelectorAll('#cams button').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.cam === k))));
  } catch (e) {
    S.error = 'scene: ' + ((e && e.message) || e);
    document.documentElement.dataset.noscene = '1';
    if (O) O.ready();
  }
}

function wire() {
  document.querySelectorAll('#pills button').forEach((b) => b.addEventListener('click', () => (S.view === b.dataset.view ? closeSheet() : openSheet(b.dataset.view))));
  document.querySelectorAll('#cams button').forEach((b) => b.addEventListener('click', () => { if (S.scene) S.scene.setMode(b.dataset.cam); document.querySelectorAll('#cams button').forEach((x) => x.setAttribute('aria-pressed', String(x === b))); }));
  $('guideBtn').addEventListener('click', () => (S.view === 'guide' ? closeSheet() : openSheet('guide')));
  $('close').addEventListener('click', closeSheet);
  $('clock').addEventListener('click', () => {                          // live -> 06:00 -> 12:00 -> 18:00 -> 00:00 -> live
    const seq = [null, 6, 12, 18, 0], i = seq.indexOf(S.preview);
    S.preview = seq[(i + 1) % seq.length];
    if (S.scene) S.scene.setHour(S.preview);
    renderClock();
  });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeSheet(); });
  const route = () => { const t = location.hash.slice(1); if (TITLES[t] && t !== 'card') openSheet(t); };
  addEventListener('hashchange', route); route();
  const fit = () => document.documentElement.style.setProperty('--dock-h', Math.ceil($('dock').getBoundingClientRect().height) + 'px');
  fit(); addEventListener('resize', fit);
  if (typeof ResizeObserver === 'function') new ResizeObserver(fit).observe($('dock'));
}

async function main() {
  const [edges, log, live] = await Promise.all([getJSON('edges.json'), getJSON('learning_log.json'), getJSON(RAW, 8000)]);
  S.liveFailed = !live;
  let model = shape(edges, log, live);
  S.demo = !model || model.edges.length < 3;
  if (S.demo) {                                                          // the engine's files are not there: the recorded copy (DEMO)
    const fx = await getJSON('fixture.json', 12000);
    if (fx) model = shape(fx.edges, { entries: fx.log }, null);
  }
  if (!model) { S.error = 'no data'; if (O) O.fail ? O.fail('The city has no data yet.') : O && O.ready(); return; }
  S.model = model; S.L = layout(model); S.startedDemo = S.demo;
  renderTop(); renderClock(); wire();
  await startScene();
  document.body.dataset.ready = '1';
  setInterval(renderClock, 15000);
  if (S.scene) setInterval(() => { if (S.preview == null) renderClock(); }, 5000);
  postCard();
  if (O && S.scene) O.ready();
  S.ready = true;
}

window.KC = {
  state: () => ({ demo: S.demo, ready: S.ready, error: S.error, view: S.view, sel: S.sel, liveUsed: !!(S.model && S.model.liveUsed), n: S.model ? S.model.edges.length : 0, counts: S.model && S.model.counts,
    regime: S.model && S.model.regime, districts: S.L ? S.L.districts.map((d) => d.key) : [], buildings: S.L ? S.L.buildings.length : 0, scene: S.scene ? S.scene.stats() : null, preview: S.preview }),
  model: () => S.model, layout: () => S.L, scene: () => S.scene,
  open: openSheet, close: closeSheet, select: (id) => selectEdge(id, true), where: (id) => (S.scene ? S.scene.where(id) : null), pick: (x, y) => (S.scene ? S.scene.pick(x, y) : null),
  hour: (v) => { S.preview = v; if (S.scene) S.scene.setHour(v); renderClock(); }, mode: (k) => { if (S.scene) S.scene.setMode(k); }, card,
};
main();
