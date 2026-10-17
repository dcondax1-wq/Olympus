// News hub (Modules → News hub): /api/next/news (research hub.json built by the news agent). Next high-impact event with a
// countdown, what today means for the bot (blackouts, FOMC, killzone events), the 7-day calendar with USD-impact bars and
// surprise colouring, headlines with tone and relevance. A 3D radar mounts over the calendar when 3D is on; the list is the fallback.
import { $, esc, fmtN, etParts, etStr } from '../util.js';
import { sessionAt } from '../app.js';
import { icon } from './icons.js';
import { mount3d } from './fx3d.js';

const KZ = [[570, 690], [810, 930]];
const DOW = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
let timer = null, DATA = null, loadedAt = 0;

const hhmm = (m) => `${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`;
const num = (v) => (v == null || v === '') ? '—' : esc(String(v));
const impactCls = (e) => e.impact === 'high' ? 'high' : e.impact === 'medium' ? 'med' : 'low';
function etToday() { const p = etParts(Date.now() / 1000); return `${p.y}-${String(p.mo).padStart(2, '0')}-${String(p.d).padStart(2, '0')}`; }
function etNowMin() { const p = etParts(Date.now() / 1000); return p.h * 60 + p.mi; }
function dayLabel(date) {
  const today = etToday();
  if (date === today) return 'Today';
  const d = new Date(date + 'T12:00:00Z'), t = new Date(today + 'T12:00:00Z'), diff = Math.round((d - t) / 864e5);
  if (diff === 1) return 'Tomorrow';
  if (diff === -1) return 'Yesterday';
  return `${DOW[d.getUTCDay()]} ${date.slice(5)}`;
}
function countdown(t) {
  let s = Math.max(0, Math.round(t - Date.now() / 1000));
  const d = Math.floor(s / 86400); s -= d * 86400;
  const h = Math.floor(s / 3600); s -= h * 3600;
  const m = Math.floor(s / 60); s -= m * 60;
  if (d) return `${d}d ${String(h).padStart(2, '0')}h ${String(m).padStart(2, '0')}m`;
  if (h) return `${h}h ${String(m).padStart(2, '0')}m ${String(s).padStart(2, '0')}s`;
  return `${m}m ${String(s).padStart(2, '0')}s`;
}
function scoreBar(v, max) {
  if (v == null) return '';
  const w = Math.max(3, Math.min(100, (v / (max || 1)) * 100));
  return `<span class="nx-usd" title="USD impact ${fmtN(v, v > 1 ? 0 : 2)}"><i style="width:${w.toFixed(0)}%"></i></span>`;
}
function surpriseCls(e) {
  const s = typeof e.surprise === 'number' ? e.surprise : (e.actual != null && e.forecast != null ? parseFloat(e.actual) - parseFloat(e.forecast) : null);
  if (s == null || isNaN(s)) return '';
  return s > 0 ? 'up' : s < 0 ? 'dn' : '';
}
function toneChip(t) {
  if (t == null) return '';
  const v = typeof t === 'number' ? (t > 0.15 ? 'pos' : t < -0.15 ? 'neg' : 'neu') : /pos|bull|risk.on/i.test(t) ? 'pos' : /neg|bear|risk.off/i.test(t) ? 'neg' : 'neu';
  const l = v === 'pos' ? 'positive' : v === 'neg' ? 'negative' : 'neutral';
  return `<span class="nx-tone ${v}">${l}</span>`;
}
function blackoutText(b) {
  if (b == null) return '';
  if (typeof b === 'string') return esc(b);
  if (Array.isArray(b) && b.length >= 2 && typeof b[0] === 'number') return `${hhmm(b[0])}–${hhmm(b[1])}`;
  if (typeof b === 'object') { const a = b.start ?? b.from ?? b[0], z = b.end ?? b.to ?? b[1]; return esc(`${typeof a === 'number' ? hhmm(a) : a ?? ''}–${typeof z === 'number' ? hhmm(z) : z ?? ''}${b.title ? ' · ' + b.title : ''}`); }
  return esc(String(b));
}

function eventRow(e, max, now) {
  const past = e.t && e.t < now;
  return `<div class="nx-ev ${impactCls(e)} ${past ? 'past' : ''} ${e.blackout ? 'bo' : ''}">
    <span class="nx-ev-t mono">${esc(e.time_et || (e.t ? etStr(e.t) : ''))}</span>
    <span class="nx-ev-i" title="${esc(e.impact || '')} impact"></span>
    <span class="nx-ev-m"><b>${esc(e.title || '')}</b>
      <span class="nx-ev-sub">${e.kind ? `<i>${esc(e.kind)}</i>` : ''}${e.source ? `<i>${esc(e.source)}</i>` : ''}${e.blackout ? '<i class="warn-t">blackout</i>' : ''}${e.in_killzone ? '<i class="kz">in killzone</i>' : ''}${e.url ? `<a href="${esc(e.url)}" target="_blank" rel="noopener">source ${icon('external')}</a>` : ''}</span></span>
    <span class="nx-ev-n"><span class="${surpriseCls(e)}"><em>actual</em>${num(e.actual)}</span><span><em>forecast</em>${num(e.forecast)}</span><span><em>previous</em>${num(e.previous)}</span></span>
    ${scoreBar(e.usd_score, max)}
  </div>`;
}

function render(el, d) {
  const now = Date.now() / 1000, today = etToday(), nowMin = etNowMin();
  const events = [...(d.events || [])].sort((a, b) => (a.t || 0) - (b.t || 0));
  const maxScore = Math.max(1e-9, ...events.map(e => e.usd_score || 0));
  const next = (d.next && d.next.t) ? d.next : (d.next?.event?.t ? d.next.event : events.find(e => e.impact === 'high' && e.t > now) || events.find(e => e.t > now) || null);
  const days = (d.days || []).length ? d.days : [...new Set(events.map(e => e.date))].map(date => ({ date, label: dayLabel(date), n_high: events.filter(e => e.date === date && e.impact === 'high').length }));
  const todayD = days.find(x => x.date === today) || null;
  const todayEv = events.filter(e => e.date === today);
  const kzEv = todayEv.filter(e => e.in_killzone);
  const boList = todayD?.blackouts || todayEv.filter(e => e.blackout).map(e => `${e.time_et || ''} ${e.title || ''}`.trim());
  const inKz = KZ.some(([a, b]) => nowMin >= a && nowMin < b);
  const p = etParts(now), dow = new Date(Date.UTC(p.y, p.mo - 1, p.d)).getUTCDay();
  const [sessName] = sessionAt(nowMin, dow);
  const hl = [...(d.headlines || [])].sort((a, b) => (b.t || 0) - (a.t || 0)).slice(0, 40);
  const maxRel = Math.max(1e-9, ...hl.map(h => h.score || 0));

  el.innerHTML = `
    <div class="nx-hero"><div><div class="nx-eyebrow">${icon('radar')} News hub · built ${esc(d.built || '')}</div><h2>What can move NQ this week</h2>
      <p class="muted">High-impact US releases, the bot's blackout windows (no new entries from 15 min before to 30 min after; closed 5 min before), FOMC days and the headlines that matter. Research says news days traded no differently; the blackout is a safety net, not an edge.</p></div>
      <button class="btn ghost" data-goto="news">${icon('news')}Markets &amp; News</button></div>

    <div class="grid cols-3 nx-nh-top">
      <div class="card nx-glass span-2 nx-nh-hero ${next ? impactCls(next) : ''}">
        <div class="nx-eyebrow">Next ${next?.impact === 'high' ? 'high-impact' : ''} event</div>
        ${next ? `<h3>${esc(next.title)}</h3>
          <div class="nx-nh-when"><span class="mono">${esc(next.date || '')} · ${esc(next.time_et || etStr(next.t))} ET</span>${next.blackout ? '<span class="nx-chip warn">blackout</span>' : ''}${next.in_killzone ? '<span class="nx-chip kz">in killzone</span>' : ''}${next.kind ? `<span class="nx-chip">${esc(next.kind)}</span>` : ''}</div>
          <div class="nx-count-dn mono" id="nhCount" data-t="${next.t}">${countdown(next.t)}</div>
          <div class="nx-nh-fp"><span><em>forecast</em><b>${num(next.forecast)}</b></span><span><em>previous</em><b>${num(next.previous)}</b></span><span><em>USD impact</em><b>${scoreBar(next.usd_score, maxScore)}</b></span></div>`
        : '<h3>Nothing high-impact on the calendar</h3><p class="muted">The week ahead is quiet for US releases.</p>'}
      </div>
      <div class="card nx-glass nx-nh-today">
        <div class="nx-eyebrow">Today for the bot · ${esc(today)}</div>
        <div class="nx-nh-flags">
          <div class="${todayD?.fomc ? 'on bad' : ''}">${icon(todayD?.fomc ? 'warn' : 'check')}<span>${todayD?.fomc ? 'FOMC day · no entries after 13:00' : 'Not an FOMC day'}</span></div>
          <div class="${boList.length ? 'on warn' : ''}">${icon('clock')}<span>${boList.length ? `${boList.length} blackout window${boList.length === 1 ? '' : 's'}` : 'No blackout windows'}</span></div>
          <div class="${kzEv.length ? 'on warn' : ''}">${icon('target')}<span>${kzEv.length ? `${kzEv.length} release${kzEv.length === 1 ? '' : 's'} inside a killzone` : 'Killzones are clear'}</span></div>
          <div>${icon('today')}<span>${esc(sessName)}${inKz ? ' · killzone live' : ''}</span></div>
        </div>
        ${boList.length ? `<ul class="nx-list small nx-bo">${boList.map(b => `<li>${blackoutText(b)}</li>`).join('')}</ul>` : ''}
        ${todayD?.summary ? `<p class="muted small">${esc(todayD.summary)}</p>` : ''}
      </div>
    </div>

    <div class="card nx-glass fx-card" data-fx-card hidden><div class="card-h"><h3>News radar · the week around the killzones</h3><span class="muted small">each blip is a release · gold rings are the killzones · drag to turn</span></div><div class="fx3d newsradar" id="nhRadar"></div></div>

    <div class="card nx-glass nx-flush nx-cal"><div class="card-h nx-cal-h"><h3>${icon('calendar')} Seven days</h3><span class="muted small">${events.length} events · <i class="nx-dot-i high"></i> high <i class="nx-dot-i med"></i> medium <i class="nx-dot-i low"></i> low · bar = USD impact</span></div>
      ${days.map(day => { const ev = events.filter(e => e.date === day.date); return `<section class="nx-day ${day.date === today ? 'today' : ''}">
        <header><b>${esc(day.label || dayLabel(day.date))}</b><span class="mono muted">${esc(day.date)}</span>
          ${day.fomc ? '<span class="nx-chip warn">FOMC</span>' : ''}${day.n_high ? `<span class="nx-chip high">${day.n_high} high</span>` : ''}${(day.blackouts || []).length ? `<span class="nx-chip">${day.blackouts.length} blackout${day.blackouts.length === 1 ? '' : 's'}</span>` : ''}
          ${day.summary ? `<span class="muted small nx-day-s">${esc(day.summary)}</span>` : ''}</header>
        ${ev.map(e => eventRow(e, maxScore, now)).join('') || '<div class="empty small">No releases.</div>'}</section>`; }).join('') || '<div class="empty">No events in the file.</div>'}
    </div>

    <div class="card nx-glass"><div class="card-h"><h3>Headlines</h3><span class="muted small">newest first · tone · relevance to NQ</span></div>
      <div class="nx-hl">${hl.map(h => `<a class="nx-hl-row" href="${esc(h.url || '#')}" ${h.url ? 'target="_blank" rel="noopener"' : ''}>
        <span class="nx-hl-m"><b>${esc(h.title)}</b><span class="nx-hl-sub"><i>${esc(h.source || '')}</i><i class="mono">${h.t ? etStr(h.t, true) + ' ET' : ''}</i>${toneChip(h.tone)}</span></span>
        <span class="nx-rel" title="relevance"><i style="width:${Math.max(4, Math.min(100, (h.score || 0) / maxRel * 100)).toFixed(0)}%"></i></span></a>`).join('') || '<div class="empty">No headlines in the file.</div>'}</div></div>`;

  mount3d('news-radar', $('#nhRadar'), 'newsradar', { now, events, killzones: KZ, session: sessName });
  clearInterval(timer);
  timer = setInterval(() => { const c = $('#nhCount'); if (!c || !c.isConnected) { clearInterval(timer); return; } c.textContent = countdown(+c.dataset.t); }, 1000);
}

function emptyState(el, why) {
  el.innerHTML = `
    <div class="nx-hero"><div><div class="nx-eyebrow">${icon('radar')} News hub</div><h2>What can move NQ this week</h2></div></div>
    <div class="card nx-glass nx-empty-hub"><span class="nx-tile-i">${icon('radar')}</span>
      <h3>The news hub has no data yet</h3>
      <p class="muted">${esc(why)} The hub file (<span class="mono">research/lab/hub.json</span>) is written by the news agent on every cloud-monitor run; this page fills itself as soon as it exists. Until then the classic Markets &amp; News page has the Forex Factory calendar and headlines.</p>
      <div class="nx-chips"><button class="btn primary" data-goto="news">${icon('news')}Open Markets &amp; News</button><button class="btn ghost" data-goto="briefing">${icon('briefing')}Briefing</button></div></div>`;
}

async function show() {
  const el = $('#page-newshub'); if (!el) return;
  if (!DATA || Date.now() - loadedAt > 120000) {
    if (!DATA) el.innerHTML = '<div class="nx-skel"><i></i><i></i><i></i></div>';
    try {
      const r = await fetch('/api/next/news');
      if (r.status === 404) { DATA = null; emptyState(el, 'Nothing is published at /api/next/news (404).'); return; }
      if (!r.ok) throw new Error('HTTP ' + r.status);
      DATA = await r.json(); loadedAt = Date.now();
      if (DATA?.error) { emptyState(el, DATA.error); DATA = null; return; }
    } catch (e) { emptyState(el, `Could not load it: ${e.message}.`); return; }
  }
  render(el, DATA);
}
export const newshub = { show };
