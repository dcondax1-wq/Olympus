// PC dashboard: BLITZ, the Mind and Trader's deck (2026-10-29 night, owner: "make a separate tab ... improve dashboard
// features"; read-only: nothing here talks to the bot).
//   #blitz   strategy 3, the scalper: Today · Brain · Trades · Results · Rules · Go live (sidebar Main after ATLAS; the part
//            sits in nx.bzPart, set by shell.js's section bar). Renderer ./blitzcore.js (window.BlitzUI, byte-identical to
//            tools/web_public/blitzcore.js).
//   #mind    the Mind (Brain v2): regime, game plans, similar setups, A-F reviews, ideas, alerts, IQ (./mindcore.js); its
//            cards also sit on the Zlarior Bot Brain, ATLAS > Brain, BLITZ > Brain and Home; nothing without the block.
//   #deck    Trader's deck (./deckcore.js): risk meter, next 24 h, eval odds, real P&L calendar, journal, notification
//            center, since you last looked, Holodeck replays; Home gets the digest, the risk meter, the next 24 h + the Mind.
//   Mission Control gets "Replay a day in the Holodeck"; a link with data-day opens the Holodeck on that day (nx.holoDay).
// Data: GET /api/next/blitz (engine/blitz.card of the bot's paper shadow + account C's block; 404 = an older server),
// /api/next/liveview?tf=1m (BLITZ's live layer, the Mind, the feed), /api/next/board (board.js, cached),
// /api/next/mind (the Mind; 404 = not built yet), /api/next/goals (calendar), /api/next/news?compact=1.
import { $, esc, store } from '../util.js';
import { boardData } from './board.js';

const V = 1;
const ensureSec = (id, txt, after) => {
  if (document.getElementById('page-' + id)) return;
  const ref = document.getElementById('page-' + after) || document.querySelector('section.page');
  const s = document.createElement('section'); s.className = 'page'; s.id = 'page-' + id; s.innerHTML = `<div class="empty">${txt}</div>`;
  if (ref && ref.parentNode) ref.parentNode.insertBefore(s, ref.nextSibling); else document.body.appendChild(s);
};
ensureSec('blitz', 'Loading BLITZ…', 'atlas');
ensureSec('mind', 'Loading the Mind…', 'blitz');
ensureSec('deck', 'Loading Trader\'s deck…', 'mind');

const cores = {};
function core(name, glob) {
  if (window[glob]) return Promise.resolve();
  if (!cores[name]) cores[name] = new Promise((ok, bad) => {
    const s = document.createElement('script');
    s.src = new URL(`./${name}.js?v=${V}`, import.meta.url).href;
    s.onload = () => ok(); s.onerror = () => { cores[name] = null; bad(new Error(name + '.js did not load')); };
    document.head.appendChild(s);
  });
  return cores[name];
}
const allCores = () => Promise.all([core('blitzcore', 'BlitzUI'), core('mindcore', 'MindUI'), core('deckcore', 'DeckUI')]);
async function getJSON(url) { try { const r = await fetch(url, { cache: 'no-store' }); if (!r.ok) return null; const j = await r.json(); return j && !j.error ? j : null; } catch { return null; } }

// one cache per source (the pages poll every 15-30 s; the Live View data is the heaviest, kept 20 s)
const C = {};
async function cached(key, url, maxAge) {
  const c = C[key];
  if (c && Date.now() - c.at < maxAge) return c.v;
  if (c && c.busy) return c.busy;
  const busy = getJSON(url).then((v) => { C[key] = { v: v ?? (c ? c.v : null), at: Date.now() }; return C[key].v; });
  C[key] = { ...(c || {}), busy, at: c ? c.at : 0 };
  return busy;
}
const go = (id, arg) => `data-goto="${esc(id)}"${arg ? (id === 'holo' ? ` data-day="${esc(arg)}"` : id === 'blitz' ? ` data-bzpart="${esc(arg)}"` : ` data-arg="${esc(arg)}"`) : ''}`;
document.addEventListener('click', (e) => {          // capture: before app.js go(), so the Holodeck opens on that day
  const h = e.target.closest('[data-goto="holo"][data-day]'); if (h) store.set('nx.holoDay', h.dataset.day);
}, true);

async function sources(withLv = true) {
  const [blz, lv, board, mind, goals, news] = await Promise.all([
    cached('blitz', '/api/next/blitz', 10000), withLv ? cached('lv', '/api/next/liveview?tf=1m', 20000) : Promise.resolve(C.lv ? C.lv.v : null),
    boardData(10000).catch(() => null), cached('mind', '/api/next/mind', 20000), cached('goals', '/api/next/goals', 300000), cached('news', '/api/next/news?compact=1', 600000)]);
  const mn = [mind, lv && lv.mind, blz && blz.mind].filter((x) => window.MindUI && window.MindUI.has(x)).sort((a, b) => (+b.t || 0) - (+a.t || 0))[0] || null;
  const ev = news && Array.isArray(news.events) ? news.events.filter((e) => e && +e.t).map((e) => ({ t: +e.t, title: e.title, impact: String(e.impact || 'high').toLowerCase() })) : [];
  const bd = board && !board.error ? board : null;
  return { blz, lv, board: bd, mind: mn, cal: goals && goals.calendar ? goals.calendar : null, news: ev, acc: (blz && blz.account_c) || null };
}
const bModel = (S) => window.BlitzUI.model({ now: Date.now() / 1000, where: 'pc', lv: S.lv, card: S.blz && S.blz.card ? S.blz.card : S.blz, ac: S.acc, board: S.board && S.board.blitz, preflight: S.blz && S.blz.preflight });
const dModel = (S) => ({ now: Date.now() / 1000, where: 'pc', board: S.board, lv: S.lv, mind: S.mind, news: S.news, cal: S.cal, acc: S.acc });
const active = (id) => document.getElementById('page-' + id)?.classList.contains('active');
const timers = {};
function every(id, ms, fn) { clearInterval(timers[id]); timers[id] = setInterval(() => { if (!active(id)) { clearInterval(timers[id]); return; } if (!document.hidden && !document.querySelector(`#page-${id} details[open]:hover`)) fn(); }, ms); }

// ------------------------------------------------------------------ BLITZ
async function drawBlitz() {
  const el = $('#page-blitz'); if (!el) return;
  try { await allCores(); } catch (e) { el.innerHTML = `<div class="banner warn">${esc(e.message)}</div>`; return; }
  const S = await sources(true);
  const part = store.get('nx.bzPart', 'today');
  const P = window.BlitzUI.PARTS.map((p) => p[0]).includes(part) ? part : 'today';
  const y = el.scrollTop;
  el.innerHTML = `<div class="nx-bz">${window.BlitzUI.page(bModel(S), P, { go, mind: P === 'brain' ? window.MindUI.bot(S.mind, 'blitz', { go }) : '' })}</div>`;
  window.BlitzUI.wire(el);
  el.scrollTop = y;
}
export const blitz = { show: () => { const el = $('#page-blitz'); if (el && !el.querySelector('.bl-wrap')) el.innerHTML = '<div class="nx-skel"><i></i><i></i></div>'; drawBlitz(); every('blitz', 15000, drawBlitz); } };

// ------------------------------------------------------------------ Mind
async function drawMind() {
  const el = $('#page-mind'); if (!el) return;
  try { await allCores(); } catch (e) { el.innerHTML = `<div class="banner warn">${esc(e.message)}</div>`; return; }
  const S = await sources(true);
  el.innerHTML = window.MindUI.page(S.mind, { go });
}
export const mind = { show: () => { drawMind(); every('mind', 20000, drawMind); } };

// ------------------------------------------------------------------ Trader's deck
async function drawDeck() {
  const el = $('#page-deck'); if (!el) return;
  try { await allCores(); } catch (e) { el.innerHTML = `<div class="banner warn">${esc(e.message)}</div>`; return; }
  const S = await sources(true);
  el.innerHTML = window.DeckUI.page(dModel(S), { go });
  window.DeckUI.wire(el, () => { el.innerHTML = window.DeckUI.page(dModel(S), { go }); });
}
export const deck = { show: () => { drawDeck(); every('deck', 20000, drawDeck); } };

// ------------------------------------------------------------------ cards on other pages: Home (cc), the Bot Brain, ATLAS > Brain, Mission Control
// cc.js / brain.js / second.js redraw their page: the cards are put back after each redraw (a MutationObserver per page)
const SLOTS = [
  { page: 'cc', id: 'nxDeckHome', where: (el) => el.querySelector('#ccSafe') || el.querySelector('#ccBoard'), html: (S) => window.DeckUI.home(dModel(S), { go }) + window.MindUI.home(S.mind, { go }) },
  { page: 'brain', id: 'nxMindLit', where: (el) => el.firstElementChild, before: true, html: (S) => window.MindUI.bot(S.mind, 'lit', { go }) },
  { page: 'atlas', id: 'nxMindAtlas', where: (el) => el.querySelector('#atRoot'), inside: true, when: () => store.get('nx.atPart', 'today') === 'brain', html: (S) => window.MindUI.bot(S.mind, 'atlas', { go }) },
  { page: 'mission', id: 'nxReplays', where: (el) => el.lastElementChild, html: (S) => window.DeckUI.replays(dModel(S), { go }) },
];
let LAST = null, seenSet = false;
function place(slot) {
  const el = document.getElementById('page-' + slot.page); if (!el || !LAST) return;
  let box = el.querySelector('#' + slot.id);
  if (slot.when && !slot.when()) { if (box) box.remove(); return; }
  let h = ''; try { h = slot.html(LAST); } catch (e) { console.warn(slot.id, e); }
  if (!h) { if (box) box.remove(); return; }
  if (box && box.__h === h) return;
  if (!box) {
    const ref = slot.where(el); if (!ref) return;
    box = document.createElement('div'); box.id = slot.id; box.className = 'nx-dk-slot';
    if (slot.inside) ref.prepend(box); else if (slot.before) ref.parentNode.insertBefore(box, ref); else ref.parentNode.insertBefore(box, ref.nextSibling);
  }
  box.innerHTML = h; box.__h = h;
  if (slot.page === 'cc') window.DeckUI.wire(box, () => { box.__h = ''; place(slot); });
}
async function refreshSlots() {
  const on = SLOTS.filter((s) => active(s.page));
  if (!on.length) return;
  try { await allCores(); } catch { return; }
  LAST = await sources(on.some((s) => s.page !== 'mission'));
  on.forEach(place);
  if (on.some((s) => s.page === 'cc') && !seenSet) { seenSet = true; setTimeout(() => window.DeckUI.markSeen(Date.now() / 1000), 8000); }
}
export function initBlitzSync() {
  for (const s of SLOTS) {
    const el = document.getElementById('page-' + s.page); if (!el || el.__dkObs) continue;
    el.__dkObs = new MutationObserver(() => { if (LAST && active(s.page) && !el.querySelector('#' + s.id)) place(s); });
    el.__dkObs.observe(el, { childList: true, subtree: s.page === 'atlas' });
  }
  refreshSlots();
  clearInterval(timers.slots); timers.slots = setInterval(() => { if (!document.hidden) refreshSlots(); }, 15000);
  addEventListener('hashchange', () => setTimeout(refreshSlots, 400));
  document.addEventListener('click', (e) => { if (e.target.closest('[data-goto],[data-page],#nav a')) setTimeout(refreshSlots, 600); });
}
const st = document.createElement('style'); st.id = 'nx-blitz-css';
st.textContent = '#page-blitz .nx-bz,#page-mind .mn-wrap,#page-deck .dk-wrap{max-width:1280px;margin:0 auto}.nx-dk-slot{margin:14px 0}.nx-dk-slot .dk-home{display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:12px;align-items:start}.nx-dk-slot .mn-home{margin-top:12px}';
document.head.appendChild(st);
