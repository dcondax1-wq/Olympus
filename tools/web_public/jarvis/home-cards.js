// Jarvis home, the cards (2026-11-10, AGORA): a calm front page under the greeting. It mounts into <div id="htoday"> and shows
//   Today (what needs you: the top 3) · NQ bots (one card per account: "Drawdown left $X of $max loss") · Money (the Mint estimate with its range) ·
//   Market day (the Kairos window now and the next event from Pythia) · Ask Jarvis (suggestion chips) · Favourites · Recent apps
// All numbers come from home-data.js (loadHome); this file only draws. Every part always says something in plain words (offline, waiting, demo).
// Taps are the shell's own: [data-app] opens an app, [data-say] asks Jarvis (index.html's delegated click handler), so nothing here opens or asks itself.
// ?demo=1 shows the example data (labelled). Read only: no button here arms, orders or changes a bot.
//
//   window.__jarvisHome = { render(), model(), refresh() }       (tests)
// Safari 16: plain ES2020 module, no optional chaining.
import { loadHome, drawdownLine, usd, ASKS } from './home-data.js';

const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const demo = /[?&]demo=1(?:&|$)/.test(location.search);
let host = null, last = null, busy = false, timer = 0;

const dot = (lv) => `<i class="hc-dot ${lv === 'ok' || lv === 'warn' || lv === 'bad' ? lv : 'off'}" aria-hidden="true"></i>`;
const pnlHtml = (v) => (v == null ? '<span class="hc-n">no P&amp;L yet</span>' : `<span class="hc-n ${v > 0 ? 'up' : v < 0 ? 'dn' : ''}">${esc(usd(v, true))} today</span>`);
const noteDemo = (m) => (m.demo ? '<p class="hc-note">Example numbers (demo). Nothing here is real.</p>' : '');

function today(m) {
  const items = m.today.items;
  const rows = items.length ? items.map((x) => {
    const attr = x.app ? `data-app="${esc(x.app)}"` : `data-say="${esc(x.say || 'What should I do today?')}"`;
    return `<li><button class="hc-row" type="button" ${attr}>${dot(x.tone)}<span>${esc(x.text)}</span><b aria-hidden="true">›</b></button></li>`;
  }).join('') : `<li class="hc-empty">${m.online ? 'Nothing needs you right now. Jarvis will say so here when something does.' : 'You are offline, so Jarvis cannot check. Nothing is wrong that it knows of.'}</li>`;
  return `<article class="hc-card hc-today" aria-labelledby="hcT"><h2 id="hcT">Today${items.length ? `<span class="hc-badge">${items.length + m.today.more}</span>` : ''}</h2><ul class="hc-list">${rows}</ul>`
    + (m.today.more ? `<button class="hc-more" type="button" data-say="What should I do today?">${m.today.more} more</button>` : '') + '</article>';
}
function bots(m) {
  const cards = m.bots.length ? m.bots.map((b) => `<button class="hc-bot" type="button" data-app="${esc(b.app || 'zenith')}" aria-label="${esc(b.name)}: ${esc(drawdownLine(b))}">`
    + `<span class="hc-bh">${dot(b.level)}<b>${esc(b.name)}</b><em>${esc(b.size)}</em></span>${pnlHtml(b.pnl)}<span class="hc-dd">${esc(drawdownLine(b))}</span>`
    + (b.text ? `<span class="hc-sub">${esc(b.text)}</span>` : '') + '</button>').join('')
    : `<button class="hc-bot hc-wide" type="button" data-app="zenith"><span class="hc-bh">${dot('')}<b>No bot report yet</b></span><span class="hc-sub">${m.online ? 'Waiting for the PC to check in. Your accounts are not affected: the bots just have not reported.' : 'You are offline. The bots keep running on the PC on their own.'}</span></button>`;
  return `<section class="hc-sec" aria-labelledby="hcB"><h2 id="hcB">NQ bots</h2><div class="hc-strip">${cards}</div></section>`;
}
function money(m) {
  const k = m.money;
  const body = k ? `<span class="hc-big">${esc(usd(k.base))}<small> a month</small></span><span class="hc-sub">Estimate, range ${esc(usd(k.low))} to ${esc(usd(k.high))}</span><span class="hc-sub">${esc(k.text)} ${esc(k.note)}</span>`
    : '<span class="hc-big hc-dim">No estimate yet</span><span class="hc-sub">Waiting for the money machines to publish. Open Mint to see them.</span>';
  return `<button class="hc-card hc-money" type="button" data-app="mint" aria-label="Money estimate, open Mint"><span class="hc-k">Money · estimate</span>${body}</button>`;
}
function day(m) {
  const w = m.day.now, e = m.day.next;
  const a = w ? `<button class="hc-row hc-day" type="button" data-app="kairos">${dot(w.entries ? 'ok' : '')}<span><b>${esc(w.label)}</b>${w.text ? ' · ' + esc(w.text) : ''}${w.until ? `<small>${esc(w.until)}</small>` : ''}</span><b aria-hidden="true">›</b></button>`
    : '<p class="hc-empty">The trading windows are not available right now. Times are New York (ET).</p>';
  const b = e ? `<button class="hc-row hc-day" type="button" data-app="pythia">${dot(e.impact === 'high' ? 'warn' : '')}<span><b>Next: ${esc(e.title)}</b><small>${esc(e.when)}${e.impact ? ' · ' + esc(e.impact) + ' impact' : ''}</small></span><b aria-hidden="true">›</b></button>`
    : '<p class="hc-empty">No market event on the calendar I can read. Open Pythia for the full list.</p>';
  return `<article class="hc-card hc-mday" aria-labelledby="hcD"><h2 id="hcD">Market day</h2>${a}${b}</article>`;
}
function ask() {
  return `<article class="hc-card hc-ask" aria-labelledby="hcA"><h2 id="hcA">Ask Jarvis</h2><div class="hc-chips" role="group" aria-label="Things to ask">${ASKS.map((q) => `<button class="hc-chip" type="button" data-say="${esc(q)}">${esc(q)}</button>`).join('')}</div></article>`;
}
function appRow(title, list, empty, id) {
  const body = list.length ? list.map((a) => `<button class="hc-app" type="button" data-app="${esc(a.id)}" aria-label="${esc(a.name)}"><i aria-hidden="true">${esc(a.glyph)}</i><span>${esc(a.name)}</span></button>`).join('')
    : `<p class="hc-empty">${empty}</p>`;
  return `<section class="hc-sec" aria-labelledby="${id}"><h2 id="${id}">${title}</h2><div class="hc-apps">${body}</div></section>`;
}
function favs(m) {
  const fav = appRow('Favourites', m.favs, 'Pin the apps you open most: hold the orb, then press and hold an app. Or <button class="hc-link" type="button" data-hc="welcome">pick three now</button>.', 'hcF');
  const rec = m.recent.length ? appRow('Recent', m.recent, '', 'hcR') : '';
  return fav + rec;
}

export function render(m) {
  if (!host) return '';
  host.innerHTML = noteDemo(m) + today(m) + bots(m) + `<div class="hc-two">${money(m)}${day(m)}</div>` + ask() + favs(m);
  host.setAttribute('data-ready', '1');
  return host.innerHTML;
}
export async function refresh() {
  if (busy || !host) return last;
  busy = true;
  try { last = await loadHome({ demo }); } catch (_) { last = last || null; }
  busy = false;
  if (last) render(last);
  return last;
}
function visible() { return !document.hidden && document.documentElement.getAttribute('data-mode') === 'jarvis'; }
function start() {
  host = document.getElementById('htoday');
  if (!host) return;
  host.addEventListener('click', (e) => { const w = e.target.closest('[data-hc="welcome"]'); if (w && window.OLYMPUS_WELCOME && window.OLYMPUS_WELCOME.open) window.OLYMPUS_WELCOME.open(); });
  // first paint at once from nothing (plain words, never blank), then the real thing as soon as Jarvis has its facts
  render({ demo, online: navigator.onLine !== false, today: { items: [], more: 0 }, bots: [], money: null, day: { now: null, next: null }, favs: [], recent: [] });
  let tries = 0;
  const first = () => { refresh().then(() => { if (!(window.__jarvis && window.__jarvis.facts) && ++tries < 20) setTimeout(first, 500); }); };
  first();
  timer = setInterval(() => { if (visible()) refresh(); }, 15000);
  window.addEventListener('online', refresh); window.addEventListener('offline', refresh);
  document.addEventListener('visibilitychange', () => { if (visible()) refresh(); });
  window.__jarvisHome = { render: () => last && render(last), model: () => last, refresh };
}
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start); else start();
