// Strategy page (Modules → Strategy, pinned): the locked rulebook in plain language for a non-coder.
// The rule text is hand-written here; every number in it is read from live_model.json (/api/next/strategy) and the headline
// results come from the live-settings replay (/api/next/results). STRATEGY.md itself is on the "Strategy Rules" page.
import { $, api, esc, fmt$, fmtS$, fmtN, cls } from '../util.js';
import { icon } from './icons.js';
import { results$ } from './datahub.js';
import { md, litRulesMd } from './modpages.js';

const fail = (el, e) => { el.innerHTML = `<div class="banner warn">Could not load the strategy: ${esc(e.message)}</div>`; };
const pct = (v) => v == null ? '—' : fmtN(v, v < 10 ? 1 : 0) + '%';
const PV = 2, MAXM = 40;

// months between two yyyy-mm-dd dates (fractional), used for "$ per month"
export function monthsBetween(a, b) {
  const d = (Date.parse(b) - Date.parse(a)) / 864e5;
  return d > 0 ? d / 30.44 : null;
}
export const perMonth = (p) => { const m = monthsBetween(p?.from, p?.to); return m ? p.net / m : null; };

function micros(stop, risk, ref, mult = 1) {
  const budget = risk * Math.min(1, ref / stop) * mult;
  return Math.min(MAXM, Math.floor(budget / (stop * PV)));
}

function periodCard(name, p, tag) {
  if (!p) return '';
  const ev = p.eval || {}, w2 = ev.within_2_weeks || {}, m1 = ev.within_1_month || {}, pm = perMonth(p);
  return `<div class="card nx-glass nx-sp">
    <div class="nx-period-h"><div><div class="nx-eyebrow">${esc(tag)}</div><h3>${esc(name)}</h3><span class="muted small">${esc(p.from)} → ${esc(p.to)}</span></div>
      <span class="nx-badge ${p.pf >= 1.5 ? 'good' : p.pf >= 1 ? '' : 'bad'}">PF ${fmtN(p.pf)}</span></div>
    <div class="nx-sp-big"><b class="${cls(p.net)}">${fmtS$(p.net)}</b><span class="${cls(pm)}">${pm != null ? fmtS$(pm) + ' a month' : ''}</span></div>
    <div class="nx-kv">
      <div><span>Trades a week</span><b class="${p.per_week >= 2 ? 'up' : 'dn'}">${fmtN(p.per_week, 1)}</b></div>
      <div><span>Weeks with 2+</span><b>${pct(p.weeks_2plus_pct)}</b></div>
      <div><span>Win rate</span><b>${pct(p.win_pct)}</b></div>
      <div><span>Max drawdown</span><b class="dn">${fmt$(p.max_dd)}</b></div>
      <div><span>Eval in 2 weeks</span><b><span class="up">${pct(w2.pass_pct)}</span> <i class="muted">/</i> <span class="dn">${pct(w2.fail_pct)}</span></b></div>
      <div><span>Eval in 1 month</span><b><span class="up">${pct(m1.pass_pct)}</span> <i class="muted">/</i> <span class="dn">${pct(m1.fail_pct)}</span></b></div>
    </div></div>`;
}

function yearRow(y, p) {
  const pm = perMonth(p), w2 = p.eval?.within_2_weeks || {}, m1 = p.eval?.within_1_month || {};
  return `<tr><td class="mono"><b>${esc(y)}</b></td><td>${p.trades}</td><td class="${p.per_week >= 2 ? 'up' : 'dn'}">${fmtN(p.per_week, 1)}</td>
    <td class="${p.pf >= 1 ? 'up' : 'dn'}">${fmtN(p.pf)}</td><td class="mono ${cls(p.net)}">${fmtS$(p.net)}</td><td class="mono ${cls(pm)}">${pm != null ? fmtS$(pm) : '—'}</td>
    <td class="mono dn">${fmt$(p.max_dd)}</td><td class="small">${pct(w2.pass_pct)} / <span class="dn">${pct(w2.fail_pct)}</span></td><td class="small">${pct(m1.pass_pct)} / <span class="dn">${pct(m1.fail_pct)}</span></td></tr>`;
}

async function show() {
  const el = $('#page-strategy'); if (!el) return;
  el.innerHTML = '<div class="nx-skel"><i></i><i></i><i></i></div>';
  let d, r = null;
  try { d = await api('/api/next/strategy'); } catch (e) { fail(el, e); return; }
  try { r = await results$(); } catch { r = null; }
  const lm = d.live_model || {}, p = lm.params || {}, ef = lm.equity_filter || {}, sz = lm.sizing || {};
  if (lm.model === 'lit') { el.innerHTML = litPage(lm, d.markdown, r); return; }
  const risk = +(p.risk_usd ?? 800), ref = +(p.risk_ref_stop ?? 20), beTrend = p.be_at_r_trending ?? 3, perDay = p.max_trades_day ?? 1;
  const lb = ef.lookback ?? 15, thr = ef.min_sum_r ?? 0, coldMode = ef.cold_mode || 'half', coldSize = ef.cold_size ?? (coldMode === 'half' ? 0.5 : 0.25);
  const late = sz.late_mult ?? 0.5, press = sz.press;
  const frac = (x) => x === 0.25 ? 'a quarter' : x === 0.5 ? 'half' : x === 1 ? 'full' : `${Math.round(x * 100)}%`;
  const FRAC = (x) => frac(x).toUpperCase();
  const P = r?.periods || {};
  const years = Object.keys(P).filter(k => /^\d{4}$/.test(k) && k < '2026');
  const has2125 = !!P['2021-25'];
  const ex = (stop) => `${micros(stop, risk, ref)} micros · ${fmt$(micros(stop, risk, ref) * stop * PV)} at risk`;

  const steps = [
    ['Sweep', `From <b>08:00 ET</b>, price trades at least one tick through a liquidity pool: the prior day or week high/low, overnight, London or Asia high/low, a 1-hour swing, or equal highs/lows. Taking a <b>low</b> arms a <b>long</b>, taking a <b>high</b> arms a <b>short</b>. The setup expires 60 minutes after the last new extreme.`, 'sweep'],
    ['Trigger', `Only inside the killzones <b>09:30–11:30</b> and <b>13:30–15:30 ET</b>: the first 5-minute candle whose body closes back through the fair value gap of the leg that made the sweep (<b>IFVG</b>). If that leg has no gap, a close back through the run that made the extreme (<b>CISD</b>). Fill at the next candle's open.`, 'trigger'],
    ['Stop', `Beyond the <b>sweep extreme</b> plus 2 points, never at a fixed distance. At least <b>10 pts</b>, at most <b>60 pts</b>; wider than that means the far side of the gap, or no trade. A wide stop means fewer micros, so <b>less</b> money at risk.`, 'stop'],
    ['Target', `The nearest untaken <b>major</b> pool at least <b>1.5R</b> away. When that draw is farther than <b>5R</b>, profit is banked at 5R on the way. <b>No major pool in range means no trade</b>: there are no made-up targets.`, 'target'],
    ['Manage', `Breakeven at <b>+1R</b> (<b>+${fmtN(beTrend, 0)}R</b> on a trending day, when the 10-day efficiency is above 0.45). Out after <b>30 minutes</b> if the trade has not reached +0.5R. <b>Giveback exit</b>: once it was +0.5R, a close back through the entry closes it. Flat by <b>15:55 ET</b>. <b>${perDay} trade a day</b>.`, 'manage'],
  ];
  const sizing = [
    [icon('money'), `$${fmtN(risk, 0)} at risk`, `up to a ${fmtN(ref, 0)}-pt stop. Wider stops risk $${fmtN(risk, 0)} × ${fmtN(ref, 0)} ÷ stop: a 40-pt stop risks ${fmt$(risk * ref / 40)}, a 60-pt stop about ${fmt$(risk * ref / 60)}. Micros = risk ÷ (stop × $${PV}), max ${MAXM}.`],
    [icon('regime'), `${FRAC(0.5)} size in a trending market`, `10-day efficiency above 0.45: reversal trades against a trend get less money, not fewer trades.`],
    [icon('clock'), `${FRAC(late)} size on a late entry`, `when the 15-minute structure has already turned the trade's way at entry. Part of the move is gone; these trades lost money in both 2021–25 and 2026.`],
    [icon('cold'), `${FRAC(coldSize)} size in a cold streak`, `when the last ${lb} finished signals add up to ${fmtN(thr, 0)}R or less. Every setup is still taken; full size returns on its own as soon as the record turns positive.`],
    [icon('scale'), 'Multiply once, round down once', `the size rules multiply (cold streak × late entry × trend), rounded down to whole micros once. The floor is <b>1 micro</b>, so no setup is ever skipped for size.`],
  ];
  const stops = [12, 20, 30, 40, 50, 60];
  const sizeTable = `<div class="table-wrap"><table class="tbl nx-sizetbl"><tr><th>Stop</th><th>Risk budget</th><th>Full</th><th>Late (${frac(late)})</th><th>Cold (${frac(coldSize)})</th><th>Cold + late</th></tr>
    ${stops.map(s => { const b = risk * Math.min(1, ref / s); const m = (k) => Math.max(1, micros(s, risk, ref, k));
      return `<tr><td class="mono"><b>${s} pts</b></td><td class="mono">${fmt$(b)}</td><td>${m(1)} <i class="muted small">· ${fmt$(m(1) * s * PV)}</i></td><td>${m(late)}</td><td>${m(coldSize)}</td><td>${m(coldSize * late)}</td></tr>`; }).join('')}</table></div>`;

  el.innerHTML = `
    <div class="nx-hero"><div><div class="nx-eyebrow">${icon('strategy')} Strategy · the rulebook${lm.locked ? ' · locked' : ''}</div>
      <h2>${esc((lm.label || 'Liquidity Engine, eval mode').split(' (')[0])}</h2>
      <p class="muted">NQ futures as MNQ micros ($${PV} a point), 5-minute candles, New York time. One liquidity sweep, one trigger, one trade a day, aimed at 2–4 trades a week. Below is what the bot does, in order, with the live numbers.</p></div>
      <div class="nx-hero-acts"><button class="btn ghost" data-goto="rules">${icon('rules')}Exact text</button><button class="btn ghost" data-goto="results">${icon('results')}Results</button></div></div>

    <div class="card nx-glass nx-version"><div class="nx-version-h">${icon('check')}<div><b>Version ${esc(lm.chosen || '—')}</b><span class="muted small">${esc(lm.model || 'engine')} · ${esc(lm.sym || 'NQ')} · ${lm.locked ? 'locked' : 'draft'}</span></div></div>
      <p>${esc(lm.lock_note || 'No lock note.')}</p>
      ${press ? `<div class="banner info">Fast-eval press is ON: ${esc(JSON.stringify(press))}</div>` : `<p class="muted small">Fast-eval press (full $${fmtN(risk, 0)} on any stop while the eval is less than $1,000 down) is built in and <b>off</b>. It halves the time to pass but fails about twice as many evals; the owner turns it on.</p>`}</div>

    <div class="nx-eyebrow nx-sec">The five steps</div>
    <ol class="nx-rules">${steps.map(([t, s], i) => `<li class="nx-rule"><span class="nx-step-n">${i + 1}</span><div><b>${t}</b><p>${s}</p></div></li>`).join('')}</ol>

    <div class="nx-eyebrow nx-sec">Size follows the stop</div>
    <div class="nx-sizing">${sizing.map(([ic, t, s]) => `<div class="nx-size"><span class="nx-size-i">${ic}</span><div><b>${t}</b><p>${s}</p></div></div>`).join('')}</div>
    <div class="card nx-glass"><div class="card-h"><h3>Micros by stop</h3><span class="muted small">$${fmtN(risk, 0)} budget to ${fmtN(ref, 0)} pts · MNQ $${PV}/pt · max ${MAXM} · floor 1</span></div>${sizeTable}
      <p class="muted small">Examples from 2026: a 13.75-pt stop is ${ex(13.75)}; a 53-pt stop is ${ex(53)}.</p></div>

    <div class="nx-eyebrow nx-sec">Guard rails</div>
    <div class="card nx-glass"><ul class="nx-list nx-guards">
      <li><b>${perDay} trade a day.</b> Done for the day after a winner.</li>
      <li><b>No new entries</b> from 15 minutes before to 30 minutes after a high-impact US release, after 13:00 on FOMC days, or once the day's range has reached 1.6× its 20-day average.</li>
      <li><b>News:</b> an open trade is closed 5 minutes before a high-impact release.</li>
      <li><b>Paper only.</b> The PC bot and the cloud monitor never place real orders; MFFU needs the owner present for live trading.</li>
      <li><b>Futures data only:</b> TradingView CME NQ1!, judged on 2026 <b>and</b> 2021–25. A change is adopted only when it holds in both and keeps 2–4 trades a week.</li>
    </ul></div>

    ${r ? `<div class="nx-eyebrow nx-sec">How it did · exact live-loop replay, costs included · built ${esc(r.meta?.built || '')}</div>
    <div class="grid cols-2 nx-sp-grid">${periodCard('2026 YTD', P['2026 YTD'], 'This year')}${has2125 ? periodCard('2021-25', P['2021-25'], 'Five earlier years') : ''}${periodCard('All years', P['All years'], 'Everything since 2021-11')}</div>
    ${!has2125 && years.length ? `<div class="card nx-glass"><div class="card-h"><h3>Each earlier year</h3><span class="muted small">eval = MFFU 50K, a new one started every trading day · pass / fail</span></div>
      <div class="table-wrap"><table class="tbl"><tr><th>Year</th><th>Trades</th><th>/wk</th><th>PF</th><th>Net</th><th>$ / month</th><th>Max DD</th><th>Eval 2 wk</th><th>Eval 1 mo</th></tr>
      ${years.map(y => yearRow(y, P[y])).join('')}</table></div></div>` : ''}
    <div class="note">${esc(r.meta?.method || '')}</div>` : '<div class="banner warn">Results are not available: run <span class="mono">python tools/export_backtest.py</span> to rebuild research/lab/backtest_live.json.</div>'}`;
}

// LIT (live_model.json "model": "lit"): the rules are read from STRATEGY.md (its LIT part), the numbers from the replay
function litPage(lm, markdown, r) {
  const P = r?.periods || {}, L = lm.lit || {}, mode = (lm.lit_sizing || {}).mode || 'normal';
  const cards = [['2026 YTD', 'This year (judged on)'], ['2026 H1 (picked on)', 'Jan–Jun 2026'], ['2026 H2 (check)', 'Jul–Oct 2026: expect this rate'],
    ['2021-25 (reference)', 'Reference only (no 1m data)']].filter(([k]) => P[k]);
  return `
    <div class="nx-hero"><div><div class="nx-eyebrow">${icon('strategy')} Strategy · the rulebook${lm.locked ? ' · locked' : ''} · STRATEGY.md</div>
      <h2>${esc((lm.label || 'LIT').split(' (')[0])}</h2>
      <p class="muted">NQ futures as MNQ micros ($${PV} a point). Setups on 5-minute candles, entry and management on 1-minute candles, New York time. Judged on 2026 only (picked on Jan–Jun, checked on Jul–Oct).</p></div>
      <div class="nx-hero-acts"><button class="btn ghost" data-goto="rules">${icon('rules')}Exact text</button><button class="btn ghost" data-goto="results">${icon('results')}Results</button></div></div>
    <div class="card nx-glass nx-version"><div class="nx-version-h">${icon('check')}<div><b>Version ${esc(lm.chosen || '—')}</b><span class="muted small">${esc(lm.model)} · ${esc(lm.sym || 'NQ')} · ${lm.locked ? 'locked' : 'draft'}</span></div></div>
      <p>${esc(lm.lock_note || 'No lock note.')}</p>
      <p class="muted small">Loss rules: Monday rule <b>${L.monday ? 'on' : 'off'}</b> · weekly stop <b>${L.wk_stop ? `on (after ${L.wk_stop[0]} stop-outs in a week, ×${L.wk_stop[1]} size)` : 'off'}</b> · sizing mode <b>${esc(mode)}</b>${mode === 'normal' ? ' (fast_eval / safe_eval switches are off)' : ''}.</p></div>
    ${r && cards.length ? `<div class="nx-eyebrow nx-sec">How it did · LIT replay, costs included · built ${esc(r.meta?.built || '')}</div>
      <div class="grid cols-2 nx-sp-grid">${cards.map(([k, tag]) => periodCard(k, P[k], tag)).join('')}</div>` : ''}
    <div class="nx-eyebrow nx-sec">The rules, word for word (STRATEGY.md)</div>
    <div class="card nx-glass nx-md">${md(litRulesMd(markdown) || 'STRATEGY.md not found.')}</div>
    ${r ? `<div class="note">${esc(r.meta?.method || '')}</div>` : ''}`;
}

export const strategy = { show };
