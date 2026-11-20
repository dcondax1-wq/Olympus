// DIONYSUS page (ES module): the Kalshi desk. The bot's numbers from the public kalshi.json feed (read only, the same file the Kalshi page reads), else the site's own kalshicity/edges.json mirror,
// else fixture.json (DEMO). A guard check, a what-if of past bets and the scan highlights: SUGGESTIONS ONLY, nothing here places, changes or stops a bet. It sends nothing and keeps nothing.
// Text only through textContent / createElementNS. window.DIONYSUS is the test hook.
import * as C from './dionysuscore.js';

const O = window.OLYMPUS || null;
const $ = (id) => document.getElementById(id);
function h(tag, cls, text) { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = String(text); return e; }
const clear = (el) => { while (el.firstChild) el.removeChild(el.firstChild); };
const sign = (v) => (v > 0 ? 'pos' : v < 0 ? 'neg' : '');
const S = { k8: null, book: null, edges: null, whatif: null, fixture: null, demo: false, pick: '', now: 0, ready: false, hl: null, wi: null, g: null };
const SRC = { feed: 'Live feed', site: 'The site\'s copy (the live feed was not reachable)', demo: 'Example numbers' };

async function getJSON(url, ms) {
  const ac = typeof AbortController === 'function' ? new AbortController() : null, timer = ac ? setTimeout(() => ac.abort(), ms || 6000) : 0;
  try { const r = await fetch(url, { cache: 'no-cache', ...(ac ? { signal: ac.signal } : {}) }); return r.ok ? await r.json() : null; } catch (_) { return null; } finally { clearTimeout(timer); }
}
// the feed is this site's own copy (pc_publish puts the Kalshi bot's feed next to the pages as kalshi.json), nothing else: the old kalshi-feed
// repo on the suspended account is retired (polish2 2026-11-19). A host that answers a missing file with its index page gives HTML: not an object = none.
const SITE_FEED = '../kalshi.json';
async function getFeed(ms) { const j = await getJSON(SITE_FEED, ms); return j && typeof j === 'object' && !Array.isArray(j) ? j : null; }
function say(t) { $('status').textContent = t; }
const tile = (box, k, v, n, cls) => { const t = h('div', 'tile'); t.appendChild(h('small', '', k)); t.appendChild(h('b', cls || '', v)); if (n) t.appendChild(h('span', '', n)); box.appendChild(t); };

function renderHero() {
  const b = S.book, risk = b.stake || 10;
  $('botName').textContent = b.name;
  const st = $('botPill'); st.textContent = S.demo ? 'Example' : b.running ? 'Running' : b.status || 'Not running'; st.className = 'pill ' + (S.demo ? 'info' : b.running ? 'ok' : 'warn');
  $('bal').textContent = C.usd(b.balance);
  const t = $('heroTiles'); clear(t);
  tile(t, 'Today', C.usdS(b.today), C.rWord(b.today, risk), sign(b.today)); tile(t, 'This week', C.usdS(b.week), C.rWord(b.week, risk), sign(b.week)); tile(t, 'All time', C.usdS(b.total), C.rWord(b.total, risk), sign(b.total));
  $('srcNote').textContent = `${SRC[b.src]}${b.src === 'demo' ? '' : ', updated ' + C.ageWord(b.t, S.now)}. 1R is the bot's average bet (${C.usd(risk)}).`;
}

function renderGuard() {
  const g = S.g = C.guard(S.book, S.edges && S.edges.regime); const card = $('guardCard');
  $('guardTitle').textContent = g.title; $('guardText').textContent = g.text; card.dataset.level = g.level;
  const p = $('guardPill'); p.textContent = { ok: 'Calm', warn: 'Watch', bad: 'Resting', off: 'No reading' }[g.level]; p.className = 'pill ' + (g.level === 'off' ? '' : g.level);
}

function renderBets() {
  const b = S.book, risk = b.stake || 10, op = $('open'), rc = $('recent'); clear(op); clear(rc);
  for (const p of b.positions) { const li = h('li', 'bet'); li.appendChild(h('b', '', p.title)); li.appendChild(h('span', 'note', `${p.side.toUpperCase()} · ${p.contracts} at ${Math.round(p.price * 100)}¢ · risking ${C.usd(p.risk)}`)); op.appendChild(li); }
  if (!b.positions.length) op.appendChild(h('li', 'note', b.src === 'site' ? 'Open bets are in the live feed; this copy only has the totals.' : 'No open bets right now.'));
  for (const t of b.trades.slice(0, 5)) { const li = h('li', 'bet'); li.appendChild(h('b', sign(t.pnl), `${C.usdS(t.pnl)} (${C.betR(t)})`)); li.appendChild(h('span', 'note', `${t.title} · ${t.side.toUpperCase()} ${t.contracts} at ${Math.round(t.price * 100)}¢`)); rc.appendChild(li); }
  if (!b.trades.length) rc.appendChild(h('li', 'note', 'No settled bets in this copy of the numbers.'));
  $('betsNote').textContent = `A bet's R is its result over what it risked. Your average bet is ${C.usd(risk)}.`;
}

function renderWhatIf() {
  const w = S.wi = C.normWhatIf(S.whatif), seg = $('sets'); clear(seg); const box = $('wiTiles'); clear(box);
  if (!w) { $('wiText').textContent = 'No what-if has been published yet. It appears after enough settled bets (about 100).'; $('wiWhy').textContent = ''; return; }
  if (!S.pick || !w.sets.some((s) => s.id === S.pick)) S.pick = (w.sets.find((s) => s.isPick) || w.sets[0]).id;
  for (const s of w.sets) {
    const b = h('button', 'ag-chip', s.isBase ? 'As it is' : s.id); b.type = 'button'; b.dataset.id = s.id; b.setAttribute('aria-pressed', s.id === S.pick ? 'true' : 'false'); b.setAttribute('aria-label', s.name);
    b.addEventListener('click', () => { S.pick = s.id; renderWhatIf(); say(`${s.name}: ${C.usdS(s.net)} on the past bets.`); }); seg.appendChild(b);
  }
  const s = w.sets.find((x) => x.id === S.pick), risk = S.book.stake || w.typical || 10;
  $('wiName').textContent = s.name;
  tile(box, 'Past bets, net', C.usdS(s.net), `${C.rWord(s.net, risk)} · ${s.bets} bets`, sign(s.net)); tile(box, 'Worst dip', C.usd(-s.dip), C.rWord(-s.dip, risk), 'neg'); tile(box, 'Chance of ruin', s.ruinPct + '%', `half the money lost: ${s.halfPct}%`);
  $('wiText').textContent = s.isBase ? 'This is the bot as it trades now, on the same past bets.' : `${C.usdS(s.gain)} better than the bot as it is on the same past bets (${C.rWord(s.gain, risk)}).`;
  $('wiWhy').textContent = (s.id === w.pick && w.recommend ? w.recommend + ' ' : '') + (w.why || '');
}

function renderScan() {
  const hl = S.hl = C.highlights(S.edges), box = $('scan'); clear(box);
  if (!hl) { box.appendChild(h('p', 'lead', 'No scan has been published yet. It looks at every kind of bet the bot makes and ranks them.')); return; }
  const block = (title, cls, items, empty) => { const d = h('div', 'sblock ' + cls); d.appendChild(h('h3', '', title)); const ul = h('ul', 'plain');
    for (const x of items) ul.appendChild(h('li', '', C.edgeLine(x))); if (!items.length) ul.appendChild(h('li', 'note', empty)); d.appendChild(ul); box.appendChild(d); };
  block('Worth a paper test', 'more', hl.more, 'Nothing stands out.'); block('Worth avoiding', 'stop', hl.stop, 'Nothing stands out.'); block('Keep watching', 'watch', hl.watch, 'Nothing yet.');
  if (hl.edges != null) box.appendChild(h('p', 'note', `${hl.edges} kinds of bet checked, ${hl.proven} look proven. Looking back, not a promise.`));
}

function renderK8() {                       // K8 today: the site's ../kalshi/k8.json (Kalshi's public results); absent = the panel hides
  const card = $('k8Card'), k = S.k8 ? C.k8Panel(S.k8, S.now * 1000) : null;
  card.hidden = !k;
  if (!k) return;
  $('k8Note').textContent = `Kalshi's public results${k.through ? ' through ' + k.through : ''}, not our bets. Fair = the price where the bet breaks even after the fee.`;
  const ul = $('k8Legs'); clear(ul);
  for (const L of k.legs) {
    const li = h('li', 'k8leg'); li.appendChild(h('b', '', `${L.at ? L.at + ' ET ' : ''}${L.name}`));
    li.appendChild(h('span', 'note', `fair ${L.fair == null ? '–' : L.fair + '¢'}${L.rate == null ? '' : ` · won ${Math.round(L.rate * 100)}%${L.n ? ' of ' + L.n : ''}`}`));
    const wl = h('span', 'k8wl'); for (const c of L.last10.split('')) wl.appendChild(h('i', c === 'W' ? 'w' : 'l', c)); if (!L.last10) wl.appendChild(h('span', 'note', 'no results yet'));
    li.appendChild(wl); ul.appendChild(li);
  }
  const pc = (x) => (x == null ? '–' : Math.round(x * 100) + '%');
  const pr = $('k8Pool'); clear(pr);
  pr.appendChild(h('span', '', 'All legs, won last 30: ')); pr.appendChild(h('b', k.l30, pc(k.r30))); pr.appendChild(h('span', '', ' · last 60: ')); pr.appendChild(h('b', k.l60, pc(k.r60)));
  pr.appendChild(h('span', '', ` · OFF under ${Math.round(k.min * 100)}%`));
  const v = $('k8Verdict'); v.textContent = k.verdict; v.className = 'pill ' + ({ ok: 'ok', watch: 'warn', off: 'bad' }[k.level] || '');
  $('k8Noise').textContent = k.noise; $('k8Noise').hidden = !k.noise;
}

function render() {
  $('demo').hidden = !S.demo; try { $('lite').hidden = !(O && O.lite && O.lite()); } catch (_) { $('lite').hidden = true; }
  renderHero(); renderK8(); renderGuard(); renderBets(); renderWhatIf(); renderScan();
  say(`${S.book.name}: balance ${C.usd(S.book.balance)}. ${S.g.title}. ${S.g.text}`);
  S.ready = true;
  try { if (O && O.ready) O.ready(); } catch (_) { /* the veil lifts by itself */ }
}

async function boot() {
  const q = new URLSearchParams(location.search), forced = q.get('demo') === '1', at = q.get('at');
  S.now = at && Number.isFinite(Date.parse(at)) ? Date.parse(at) / 1000 : Date.now() / 1000;
  const [fx, feed, edges, wi, k8] = await Promise.all([getJSON('./fixture.json'), forced ? null : getFeed(5000), forced ? null : getJSON('../kalshicity/edges.json'), forced ? null : getJSON('../kalshicity/whatif.json'),
    forced ? null : getJSON('../kalshi/k8.json', 3000)]);
  S.k8 = k8 && typeof k8 === 'object' && !Array.isArray(k8) ? k8 : null;
  S.fixture = fx; const book = C.chooseBook(feed, edges, fx); if (!book) throw new Error('no numbers');
  S.book = book; S.demo = book.src === 'demo';
  S.edges = S.demo ? (fx && fx.edges) || null : edges; S.whatif = S.demo ? (fx && fx.whatif) || null : wi;
  render();
}
window.DIONYSUS = { S, C, ready: () => S.ready, render };
boot().catch((e) => { say('Something went wrong: ' + (e && e.message ? e.message : e)); try { if (O && O.fail) O.fail('Dionysus could not start'); } catch (_) { /* nothing */ } });
