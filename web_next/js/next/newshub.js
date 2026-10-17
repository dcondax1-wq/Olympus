// News hub (Modules → News hub): /api/next/news = data/news/hub.json, built by `python tools/news_hub.py --out data/news/hub.json`
// (USD calendar scored for NQ with the bot's blackout windows, per-day summaries, scored headlines, bot_now traffic light).
// Page: next high-impact event with a countdown, today for the bot (traffic light from bot_now, blackouts, FOMC, killzone pauses),
// the calendar grouped by day with USD-impact bars and surprise colouring, headlines with tone and relevance.
// A 3D radar mounts over the calendar when 3D is on; the list is the fallback.
import { $, esc, fmtN, etParts, etStr } from '../util.js';
import { sessionAt } from '../app.js';
import { icon } from './icons.js';
import { mount3d } from './fx3d.js';

const KZ = [[570, 690], [810, 930]];
let timer = null, DATA = null, loadedAt = 0;

const num = (v) => (v == null || v === '') ? '—' : esc(String(v));
const impactCls = (e) => e.impact === 'high' ? 'high' : e.impact === 'medium' ? 'med' : 'low';
function etToday() { const p = etParts(Date.now() / 1000); return `${p.y}-${String(p.mo).padStart(2, '0')}-${String(p.d).padStart(2, '0')}`; }
function etNowMin() { const p = etParts(Date.now() / 1000); return p.h * 60 + p.mi; }
function countdown(t) {
  let s = Math.max(0, Math.round(t - Date.now() / 1000));
  const d = Math.floor(s / 86400); s -= d * 86400;
  const h = Math.floor(s / 3600); s -= h * 3600;
  const m = Math.floor(s / 60); s -= m * 60;
  if (d) return `${d}d ${String(h).padStart(2, '0')}h ${String(m).padStart(2, '0')}m`;
  if (h) return `${h}h ${String(m).padStart(2, '0')}m ${String(s).padStart(2, '0')}s`;
  return `${m}m ${String(s).padStart(2, '0')}s`;
}
const short = (s) => { s = Math.max(0, Math.round(s)); return s >= 86400 ? `${Math.floor(s / 86400)}d ${Math.floor(s % 86400 / 3600)}h` : s >= 3600 ? `${Math.floor(s / 3600)}h ${String(Math.floor(s % 3600 / 60)).padStart(2, '0')}m` : `${Math.floor(s / 60)}m`; };
// usd_score is 0..100 (FOMC = 100, CPI / NFP = 95)
function scoreBar(v) {
  if (v == null) return '';
  const w = Math.max(3, Math.min(100, v > 1 ? v : v * 100));
  return `<span class="nx-usd" title="USD impact ${fmtN(v, v > 1 ? 0 : 2)} / 100"><i style="width:${w.toFixed(0)}%"></i></span>`;
}
function surpriseCls(e) {
  if (e.surprise_side) return /up|beat|hot|above|strong/i.test(e.surprise_side) ? 'up' : /down|miss|cold|below|weak/i.test(e.surprise_side) ? 'dn' : '';
  const s = typeof e.surprise === 'number' ? e.surprise : (e.actual && e.forecast ? parseFloat(e.actual) - parseFloat(e.forecast) : null);
  if (s == null || isNaN(s)) return '';
  return s > 0 ? 'up' : s < 0 ? 'dn' : '';
}
// tone for NQ: hawkish and risk-off push it down (magenta), dovish and risk-on push it up (green), neutral grey
function toneChip(t) {
  if (t == null || t === '') return '';
  const s = typeof t === 'number' ? (t > 0.15 ? 'dovish' : t < -0.15 ? 'hawkish' : 'neutral') : String(t).toLowerCase().replace(/_/g, '-');
  const v = /hawk|risk-off|neg|bear/.test(s) ? 'neg' : /dov|risk-on|pos|bull/.test(s) ? 'pos' : 'neu';
  const hint = v === 'neg' ? 'leans down for NQ' : v === 'pos' ? 'leans up for NQ' : 'no lean';
  return `<span class="nx-tone ${v}" title="${hint}">${esc(s)}</span>`;
}
const txt = (b) => typeof b === 'string' ? esc(b) : Array.isArray(b) ? esc(b.join(' · ')) : b && typeof b === 'object' ? esc(`${b.start ?? ''}–${b.end ?? ''}${b.title ? ' ' + b.title : ''}`) : esc(String(b ?? ''));

function eventRow(e, now) {
  const past = e.t && e.t < now;
  return `<div class="nx-ev ${impactCls(e)} ${past ? 'past' : ''} ${e.blackout ? 'bo' : ''}">
    <span class="nx-ev-t mono">${esc(e.time_et || (e.t ? etStr(e.t) : ''))}</span>
    <span class="nx-ev-i" title="${esc(e.impact || '')} impact"></span>
    <span class="nx-ev-m"><b>${esc(e.title || '')}</b>
      <span class="nx-ev-sub">${e.kind_label || e.kind ? `<i>${esc(e.kind_label || e.kind)}</i>` : ''}${e.source ? `<i>${esc(e.source)}</i>` : ''}
        ${e.blackout ? `<i class="warn-t">blackout ${esc(e.blackout_start || '')}${e.blackout_end ? '–' + esc(e.blackout_end) : ''}</i>` : ''}${e.in_killzone || e.blackout_hits_killzone ? `<i class="kz">${e.killzone ? esc(e.killzone) + ' ' : ''}killzone${e.blackout_hits_killzone ? ' · bot pauses' : ''}</i>` : ''}
        ${e.confidence === 'inferred' ? '<i>time inferred</i>' : ''}${e.url ? `<a href="${esc(e.url)}" target="_blank" rel="noopener">source ${icon('external')}</a>` : ''}</span></span>
    <span class="nx-ev-n"><span class="${surpriseCls(e)}"><em>actual</em>${num(e.actual)}</span><span><em>forecast</em>${num(e.forecast)}</span><span><em>previous</em>${num(e.previous)}</span></span>
    ${scoreBar(e.usd_score)}
  </div>`;
}

function trafficLight(d, today, nowMin) {
  const bn = d.bot_now || {}, nb = bn.next_blackout || null, rules = bn.rules || {};
  const p = etParts(Date.now() / 1000), dow = new Date(Date.UTC(p.y, p.mo - 1, p.d)).getUTCDay(), weekend = dow === 0 || dow === 6;
  let light = 'green', title = 'Clear to trade', sub = '';
  if (bn.in_blackout) { light = 'red'; title = 'In a blackout: no new entries'; sub = (bn.reasons || []).map(txt).join(' · ') || 'high-impact release window'; }
  else if (bn.fomc_today && bn.fomc_pm_off !== false && nowMin >= 780) { light = 'red'; title = 'FOMC day: no entries after 13:00'; sub = 'the bot is flat into the statement'; }
  else if (bn.fomc_today) { light = 'amber'; title = 'FOMC day: entries stop at 13:00 ET'; sub = nb ? `next blackout ${esc(nb.start)}–${esc(nb.end)} · ${esc(nb.title || '')}` : ''; }
  else if (nb && nb.date === today && nb.in_s != null && nb.in_s < 7200) { light = 'amber'; title = `Blackout at ${esc(nb.start)} · ${esc(nb.title || '')}`; sub = `in ${short(nb.in_s)} · no new entries ${esc(nb.start)}–${esc(nb.end)}`; }
  else if (weekend) { light = 'off'; title = 'Market closed'; sub = nb ? `next blackout ${esc(nb.date === today ? '' : (nb.date || ''))} ${esc(nb.start)}–${esc(nb.end)} · ${esc(nb.title || '')}` : 'nothing scheduled'; }
  else sub = nb ? `next blackout ${nb.date === today ? 'today' : esc(nb.date || '')} ${esc(nb.start)}–${esc(nb.end)} · ${esc(nb.title || '')}${nb.in_s != null ? ' · in ' + short(nb.in_s) : ''}` : 'no blackout ahead';
  const rule = rules.before_min != null ? `${rules.before_min} min before to ${rules.after_min} min after a high-impact USD release${rules.fomc_pm_off ? ' · FOMC: nothing after 13:00' : ''}${rules.flatten_min ? ' · flat ' + rules.flatten_min + ' min before' : ''}` : '';
  return `<div class="nx-light ${light}"><i></i><div><b>${title}</b>${sub ? `<span>${sub}</span>` : ''}${rule ? `<em>${esc(rule)}</em>` : ''}</div></div>`;
}

function render(el, d) {
  const now = Date.now() / 1000, today = etToday(), nowMin = etNowMin();
  const events = [...(d.events || [])].sort((a, b) => (a.t || 0) - (b.t || 0));
  const next = (d.next && d.next.t) ? d.next : events.find(e => e.impact === 'high' && e.t > now) || events.find(e => e.t > now) || null;
  const days = (d.days || []).length ? d.days : [...new Set(events.map(e => e.date))].map(date => ({ date, label: date, n_high: events.filter(e => e.date === date && e.impact === 'high').length }));
  const todayD = days.find(x => x.is_today) || days.find(x => x.date === today) || null;
  const todayEv = events.filter(e => e.date === today);
  const kzEv = todayEv.filter(e => e.in_killzone || e.blackout_hits_killzone);
  const boList = todayD?.blackouts || todayEv.filter(e => e.blackout).map(e => `${e.blackout_start || e.time_et || ''}-${e.blackout_end || ''} ${e.title || ''}`.trim());
  const pauses = todayD?.killzone_pauses || [];
  const inKz = KZ.some(([a, b]) => nowMin >= a && nowMin < b);
  const p = etParts(now), dow = new Date(Date.UTC(p.y, p.mo - 1, p.d)).getUTCDay();
  const [sessName] = sessionAt(nowMin, dow);
  const hl = [...(d.headlines || [])].sort((a, b) => (b.t || 0) - (a.t || 0)).slice(0, 40);
  const maxRel = Math.max(1, ...hl.map(h => h.score || 0));
  const fomc = !!(todayD?.fomc || d.bot_now?.fomc_today);
  const bn = d.bot_now || {};
  const ahead = days.filter(x => !x.past || x.is_today), earlier = days.filter(x => x.past && !x.is_today);

  const dayBlock = (day) => { const ev = events.filter(e => e.date === day.date); return `<section class="nx-day ${day.is_today || day.date === today ? 'today' : ''} ${day.past && !day.is_today ? 'past' : ''} ${day.heaviest ? 'heavy' : ''}">
    <header><b>${day.is_today || day.date === today ? 'Today · ' : ''}${esc(day.label || day.date)}</b>${day.label && day.label !== day.date ? `<span class="mono muted">${esc(day.date)}</span>` : ''}
      ${day.holiday ? '<span class="nx-chip">holiday</span>' : ''}${day.fomc ? '<span class="nx-chip warn">FOMC</span>' : ''}${day.n_high ? `<span class="nx-chip high">${day.n_high} high</span>` : ''}${day.heaviest ? '<span class="nx-chip">heaviest day</span>' : ''}
      ${(day.killzone_pauses || []).length ? `<span class="nx-chip kz">bot pauses ${day.killzone_pauses.map(txt).join(', ')}</span>` : (day.blackouts || []).length ? `<span class="nx-chip">${day.blackouts.length} blackout${day.blackouts.length === 1 ? '' : 's'} · outside killzones</span>` : ''}
      ${day.summary ? `<span class="muted small nx-day-s">${esc(day.summary)}</span>` : ''}</header>
    ${ev.map(e => eventRow(e, now)).join('') || '<div class="empty small">No USD releases.</div>'}</section>`; };

  el.innerHTML = `
    <div class="nx-hero"><div><div class="nx-eyebrow">${icon('radar')} News hub · built ${esc(String(d.built || '').replace('T', ' ').slice(0, 16))}${d.offline ? ' · offline build from cached sources' : ''}</div><h2>What can move NQ this week</h2>
      <p class="muted">High-impact US releases scored for NQ, the bot's blackout windows (no new entries from 15 min before to 30 min after; closed 5 min before), FOMC days and the headlines that matter. Research says news days traded no differently; the blackout is a safety net, not an edge.</p></div>
      <button class="btn ghost" data-goto="news">${icon('news')}Markets &amp; News</button></div>

    <div class="grid cols-3 nx-nh-top">
      <div class="card nx-glass span-2 nx-nh-hero ${next ? impactCls(next) : ''}">
        <div class="nx-eyebrow">Next ${next?.impact === 'high' ? 'high-impact' : ''} event${next?.kind_label ? ' · ' + esc(next.kind_label) : ''}</div>
        ${next ? `<h3>${esc(next.title)}</h3>
          <div class="nx-nh-when"><span class="mono">${esc(next.label || `${next.date || ''} · ${next.time_et || etStr(next.t)}`)} ET</span>${next.blackout ? `<span class="nx-chip warn">blackout ${esc(next.blackout_start || '')}–${esc(next.blackout_end || '')}</span>` : ''}${next.in_killzone || next.blackout_hits_killzone ? `<span class="nx-chip kz">${esc(next.killzone || '')} killzone${next.blackout_hits_killzone ? ' · bot pauses' : ''}</span>` : ''}</div>
          <div class="nx-count-dn mono" id="nhCount" data-t="${next.t}">${countdown(next.t)}</div>
          <div class="nx-nh-fp"><span><em>forecast</em><b>${num(next.forecast)}</b></span><span><em>previous</em><b>${num(next.previous)}</b></span><span><em>USD impact</em><b>${scoreBar(next.usd_score)} <i class="mono small">${next.usd_score ?? '—'}</i></b></span></div>`
        : '<h3>Nothing high-impact on the calendar</h3><p class="muted">The days ahead are quiet for US releases.</p>'}
      </div>
      <div class="card nx-glass nx-nh-today">
        <div class="nx-eyebrow">Today for the bot · ${esc(todayD?.label || today)}</div>
        ${trafficLight(d, today, nowMin)}
        <div class="nx-nh-flags">
          <div class="${fomc ? 'on bad' : ''}">${icon(fomc ? 'warn' : 'check')}<span>${fomc ? 'FOMC day · no entries after 13:00' : 'Not an FOMC day'}</span></div>
          <div class="${pauses.length ? 'on warn' : ''}">${icon('target')}<span>${pauses.length ? `Bot will not enter ${pauses.map(txt).join(', ')} (release in a killzone)` : kzEv.length ? `${kzEv.length} release${kzEv.length === 1 ? '' : 's'} inside a killzone` : 'Killzones are clear'}</span></div>
          <div class="${boList.length ? 'on' : ''}">${icon('clock')}<span>${boList.length ? `${boList.length} blackout window${boList.length === 1 ? '' : 's'} today` : 'No blackout windows today'}</span></div>
          <div>${icon('today')}<span>${esc(sessName)}${inKz ? ' · killzone live' : ''}</span></div>
        </div>
        ${boList.length ? `<ul class="nx-list small nx-bo">${boList.map(b => `<li>${txt(b)}</li>`).join('')}</ul>` : ''}
        ${(todayD?.fed_speakers || []).length ? `<p class="muted small">Fed speakers: ${esc(todayD.fed_speakers.join(', '))}</p>` : ''}
        ${todayD?.summary ? `<p class="muted small">${esc(todayD.summary)}</p>` : ''}
      </div>
    </div>
    ${(d.notes || []).length ? `<div class="nx-notes">${d.notes.map(n => `<span class="nx-chip">${icon('info')} ${esc(n)}</span>`).join('')}</div>` : ''}

    <div class="card nx-glass fx-card" data-fx-card hidden><div class="card-h"><h3>News radar · the week around the killzones</h3><span class="muted small">each blip is a release · gold rings are the killzones · drag to turn</span></div><div class="fx3d newsradar" id="nhRadar"></div></div>

    <div class="card nx-glass nx-flush nx-cal"><div class="card-h nx-cal-h"><h3>${icon('calendar')} ${ahead.length ? ahead.length + ' days ahead' : 'Calendar'}</h3><span class="muted small">${events.length} events · <i class="nx-dot-i high"></i> high <i class="nx-dot-i med"></i> medium <i class="nx-dot-i low"></i> low · bar = USD impact / 100</span></div>
      ${ahead.map(dayBlock).join('') || '<div class="empty">No events in the file.</div>'}
      ${earlier.length ? `<details class="nx-earlier"><summary>Earlier · ${earlier.length} day${earlier.length === 1 ? '' : 's'} with results</summary>${earlier.map(dayBlock).join('')}</details>` : ''}
    </div>

    <div class="card nx-glass"><div class="card-h"><h3>Headlines</h3><span class="muted small">newest first · tone for NQ · relevance</span></div>
      <div class="nx-hl">${hl.map(h => `<a class="nx-hl-row" href="${esc(h.url || '#')}" ${h.url ? 'target="_blank" rel="noopener"' : ''}>
        <span class="nx-hl-m"><b>${esc(h.title)}</b><span class="nx-hl-sub"><i>${esc(h.source || '')}</i><i class="mono">${h.time_et ? esc(h.time_et) + ' ET' : h.t ? etStr(h.t, true) + ' ET' : ''}</i>${toneChip(h.tone)}</span></span>
        <span class="nx-rel" title="relevance ${esc(String(h.score ?? ''))}"><i style="width:${Math.max(4, Math.min(100, (h.score || 0) / maxRel * 100)).toFixed(0)}%"></i></span></a>`).join('') || `<div class="empty">No headlines in the file${d.offline ? ' (built offline from cached sources)' : ''}.</div>`}</div></div>
    ${(d.sources || []).length ? `<p class="muted small nx-src">Sources: ${d.sources.map(s => `${esc(s.name)}${s.ok === false ? ' (down)' : ''}`).join(' · ')}</p>` : ''}`;

  mount3d('news-radar', $('#nhRadar'), 'newsradar', { now, events, killzones: KZ, session: sessName, bot_now: bn });
  clearInterval(timer);
  timer = setInterval(() => { const c = $('#nhCount'); if (!c || !c.isConnected) { clearInterval(timer); return; } c.textContent = countdown(+c.dataset.t); }, 1000);
}

function emptyState(el, why) {
  el.innerHTML = `
    <div class="nx-hero"><div><div class="nx-eyebrow">${icon('radar')} News hub</div><h2>What can move NQ this week</h2></div></div>
    <div class="card nx-glass nx-empty-hub"><span class="nx-tile-i">${icon('radar')}</span>
      <h3>The news hub has no data yet</h3>
      <p class="muted">${esc(why)} The hub reads <span class="mono">data/news/hub.json</span>, built by <span class="mono">python tools/news_hub.py --out data/news/hub.json</span> (the cloud monitor runs it on every pass). This page fills itself as soon as the file exists. Until then the classic Markets &amp; News page has the Forex Factory calendar and headlines.</p>
      <div class="nx-chips"><button class="btn primary" data-goto="news">${icon('news')}Open Markets &amp; News</button><button class="btn ghost" data-goto="briefing">${icon('briefing')}Briefing</button></div></div>`;
}

async function show() {
  const el = $('#page-newshub'); if (!el) return;
  if (!DATA || Date.now() - loadedAt > 120000) {
    if (!DATA) el.innerHTML = '<div class="nx-skel"><i></i><i></i><i></i></div>';
    try {
      const r = await fetch('/api/next/news');
      if (r.status === 404) { DATA = null; emptyState(el, 'Nothing is published at /api/next/news yet.'); return; }
      if (!r.ok) throw new Error('HTTP ' + r.status);
      const d = await r.json(); loadedAt = Date.now();
      if (d?.error && !(d.events || []).length) { DATA = null; emptyState(el, d.error); return; }
      DATA = d;
    } catch (e) { if (!DATA) { emptyState(el, `Could not load it: ${e.message}.`); return; } }
  }
  render(el, DATA);
}
export const newshub = { show };
