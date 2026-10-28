// AI Insights (owner's 50-feature list, group C, items 21-30): one read-only page over GET /api/next/insight
// (engine/insight_api.py). Every panel is plain language first, numbers second, and phone-friendly (one column at 390 px).
//   21 setup radar · 22 next entry window · 23 live vs backtest · 24 drift alarm · 25 setup grade · 26 similar past trades
//   27 market regime · 28 LIT levels map · 29 ATLAS members · 30 Strategy 3 (research)
// Nothing here starts, arms, routes, sizes or stops anything. The page section and its stylesheet are added by this module
// (index.html stays untouched); app.js registers the page as PAGES.insight.
import { $, esc, store } from '../util.js';
import { icon } from './icons.js';

// ------------------------------------------------------------------ page shell (section + stylesheet)
(function ensure() {
  if (!document.querySelector('link[href="/css/insight.css"]')) {
    const l = document.createElement('link'); l.rel = 'stylesheet'; l.href = '/css/insight.css'; document.head.appendChild(l);
  }
  if (!document.getElementById('page-insight')) {
    const ref = document.getElementById('page-board') || document.querySelector('section.page');
    const s = document.createElement('section'); s.className = 'page'; s.id = 'page-insight';
    s.innerHTML = '<div class="empty">Loading AI Insights…</div>';
    if (ref?.parentNode) ref.parentNode.appendChild(s); else document.body.appendChild(s);
  }
})();

// ------------------------------------------------------------------ helpers
const ok = (v) => v != null && v !== '' && !Number.isNaN(+v);
const usd = (v) => (!ok(v) ? '—' : (v < 0 ? '−' : '') + '$' + Math.abs(Math.round(+v)).toLocaleString('en-US'));
const susd = (v) => (!ok(v) ? '—' : (v > 0 ? '+' : '') + usd(v));
const num = (v, d = 2) => (ok(v) ? (+v).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d }) : '—');
const px = (v) => num(v, 2);
const R = (v) => (ok(v) ? (v > 0 ? '+' : '') + (+v).toFixed(2) + 'R' : '—');
const pct = (v) => (ok(v) ? Math.round(+v) + '%' : '—');
const cl = (v) => (v > 0 ? 'up' : v < 0 ? 'dn' : '');
const chip = (t, k = '') => `<span class="nx-chip ${k}">${t}</span>`;
const card = (n, title, ic, sentence, body, extra = '') => `<article class="card nx-glass in-card ${extra}">
  <div class="in-h"><span class="in-n">${n}</span><span class="in-i">${icon(ic)}</span><h3>${title}</h3></div>
  ${sentence ? `<p class="in-say">${sentence}</p>` : ''}${body}</article>`;
const errCard = (n, title, ic, e) => card(n, title, ic, '', `<div class="in-empty">Could not build this panel: ${esc(e)}</div>`);
const bar = (f, k = '') => `<div class="in-bar ${k}"><i style="width:${Math.max(0, Math.min(100, (f || 0) * 100)).toFixed(1)}%"></i></div>`;
const dur = (s) => {
  if (!ok(s)) return '—';
  s = Math.max(0, Math.round(s));
  const d = Math.floor(s / 86400), h = Math.floor((s % 86400) / 3600), m = Math.floor((s % 3600) / 60), x = s % 60;
  return d ? `${d}d ${h}h` : h ? `${h}h ${String(m).padStart(2, '0')}m` : m ? `${m}m ${String(x).padStart(2, '0')}s` : `${x}s`;
};
const STAGE_K = { armed: 'good', signal: 'good', open: 'good', in_trade: 'good', trade: 'good', waiting: '', off: '', done: '', error: 'bad' };
const stageChip = (s) => chip(esc(s || '—'), STAGE_K[s] ?? '');
const STATUS = { on_track: ['On track', 'good'], above: ['Above', 'good'], below: ['Below', 'bad'], collecting: ['Collecting', 'warn'], no_trades: ['No live trades yet', ''] };
const side = (s) => (String(s || '').toUpperCase().startsWith('L') ? `<b class="up">LONG</b>` : String(s || '') ? `<b class="dn">SHORT</b>` : '');
const zl = (s) => String(s ?? '').replace(/^LIT\b/, 'Zlarior');

const P = { d: null, err: null, timer: null, tick: null, at: 0, replay: store.get('nx.in.replay', null), loading: false };

async function load(force = false) {
  if (P.loading) return;
  P.loading = true;
  try {
    const q = P.replay?.day ? `?day=${encodeURIComponent(P.replay.day)}&hm=${encodeURIComponent(P.replay.hm || '16:00')}` : '';
    const r = await fetch('/api/next/insight' + q, { cache: 'no-store' });
    const d = await r.json().catch(() => ({}));
    if (!r.ok || d.error) throw new Error(d.error || 'HTTP ' + r.status);
    P.d = d; P.err = null; P.at = Date.now();
  } catch (e) { P.err = e.message || String(e); }
  P.loading = false;
  draw();
}

// ------------------------------------------------------------------ panels
function pRadar(x) {
  if (!x || x.error) return errCard(21, 'Setup radar', 'radar', x?.error || 'no data');
  const L = x.lit || {};
  const sides = (L.sides || []).map((s) => `<div class="in-side">
      <div class="in-row"><span>${side(s.side)} ${s.allowed === false ? chip('not allowed today', 'warn') : ''}</span>${stageChip(s.stage)}</div>
      ${s.swept?.length ? `<div class="in-sub">Swept: ${esc(s.swept.slice(0, 4).join(', '))}${s.depth_atr != null ? ` · ${num(s.depth_atr)} ATR deep` : ''}</div>` : ''}
      ${s.needs?.length ? `<div class="in-sub">Still needs: ${s.needs.map(esc).join(' · ')}</div>` : s.text ? `<div class="in-sub">${esc(s.text)}</div>` : ''}
    </div>`).join('');
  const near = (arr, k) => (arr || []).slice(0, 2).map((l) => `<span class="nx-chip ${k}">${esc(l.label)} ${px(l.price)} <i>${l.dist > 0 ? '+' : ''}${num(l.dist, 0)} pts</i></span>`).join('');
  const members = (x.atlas || []).map((m) => `<div class="in-mem">
      <div class="in-row"><b>${esc(m.short || m.key)}</b>${m.candidate ? chip('candidate') : ''}${stageChip(m.stage)}</div>
      <div class="in-sub">${esc(m.text || '')}</div>
      ${m.checks_n ? `<div class="in-chk">${bar(m.checks_ok / m.checks_n, m.ready ? 'good' : 'accent')}<span>${m.checks_ok}/${m.checks_n} rule checks pass${m.first_fail ? ` · first miss: ${esc(m.first_fail)}` : ''}</span></div>` : ''}
    </div>`).join('');
  const body = `<div class="in-block"><div class="in-row"><b>Zlarior (LIT)</b>${chip(`step ${L.stage_n || '?'} of 10 · ${esc(L.stage_label || '?')}`, L.stage === 'trade' || L.stage === 'limit' || L.stage === 'cisd1m' ? 'good' : '')}</div>
      ${bar((L.stage_n || 0) / 10, 'accent')}
      <p class="in-txt">${esc(L.text || '')}</p>
      <div class="nx-chips">${near(L.nearest?.above, '')}${near(L.nearest?.below, '')}</div>
      <div class="in-sides">${sides}</div></div>
    <div class="in-block"><div class="in-row"><b>ATLAS (paper)</b><span class="muted">EMA · MACD · S/R + 2 candidates</span></div>${members || '<div class="in-empty">ATLAS has not run yet.</div>'}</div>`;
  return card(21, 'Setup radar', 'radar', esc(x.summary || ''), body, 'in-wide');
}

function pWindows(x) {
  if (!x || x.error) return errCard(22, 'Next entry window', 'clock', x?.error || 'no data');
  const rows = (x.rows || []).map((w) => {
    const n = w.next;
    const st = !n ? chip('no window', '') : n.open ? chip('open', 'good') : chip('closed');
    const cd = !n ? '' : n.open ? `closes in <b class="in-cd" data-to="${n.end_t}">${dur(n.closes_in_s)}</b>` :
      `opens in <b class="in-cd" data-to="${n.start_t}">${dur(n.opens_in_s)}</b> <span class="muted">(${esc(n.start_day || '')} ${esc(n.start_hm || '')} ET)</span>`;
    return `<div class="in-win"><div class="in-row"><b>${esc(w.short || w.label)}</b>${w.candidate ? chip('candidate') : ''}${st}</div>
      <div class="in-sub">${esc(w.window || '—')}${w.note ? ` · ${esc(w.note)}` : ''}</div><div class="in-count">${cd}</div></div>`;
  }).join('');
  const open = (x.rows || []).filter((w) => w.next?.open).map((w) => w.short || w.label);
  const say = open.length ? `Open now: ${esc(open.join(', '))}.` : 'No entry window is open right now.';
  return card(22, 'Next entry window', 'clock', say, `<div class="in-wins">${rows}</div><p class="in-foot">${esc(x.note || '')}</p>`);
}

function pScore(x) {
  if (!x || x.error) return errCard(23, 'Live vs backtest', 'robust', x?.error || 'no data');
  const rows = (x.rows || []).map((r) => {
    const [lab, k] = STATUS[r.status] || [r.status_text || '—', ''];
    const h1 = r.research?.H1 || {}, h2 = r.research?.H2 || {};
    const live = r.live || {};
    const exp = r.expected_20?.cum_r ? `after 20 trades the backtest expects ${R(r.expected_20.cum_r[0])} to ${R(r.expected_20.cum_r[2])} (middle ${R(r.expected_20.cum_r[1])})` : '';
    return `<div class="in-sc">
      <div class="in-row"><b>${esc(zl(r.label))}</b>${chip(lab + (r.pct != null ? ` · p${Math.round(r.pct)}` : ''), k)}</div>
      <div class="in-sub">Live: ${live.n || 0} trades${live.n ? ` · ${live.cum_r != null ? R(live.cum_r) : R(live.avg_r) + ' a trade'} · ${susd(live.usd ?? live.net)}` : ''}${r.detail ? ` · ${esc(r.detail)}` : ''}</div>
      <div class="in-grid4">
        <div><span>H1 PF</span><b>${num(h1.pf)}</b></div><div><span>H2 PF</span><b>${num(h2.pf)}</b></div>
        <div><span>H2 net</span><b class="${cl(h2.net)}">${susd(h2.net)}</b></div><div><span>H2 $/mo</span><b class="${cl(h2.per_month)}">${susd(h2.per_month)}</b></div>
      </div>
      <div class="in-sub">${h2.tpw != null ? `${num(h2.tpw)} trades a week in H2 · ` : ''}${exp}</div></div>`;
  }).join('');
  const below = (x.rows || []).filter((r) => r.status === 'below').map((r) => zl(r.label));
  const say = below.length ? `Below the expected band: ${esc(below.join(', '))}. Check the trades before acting.` :
    (x.rows || []).some((r) => r.live?.n) ? 'Every strategy with live trades is inside its expected band.' : 'No live trades yet: the bands are ready for the first ones.';
  return card(23, 'Live vs backtest', 'robust', say, `<div class="in-scs">${rows}</div><p class="in-foot">${esc(x.note || '')}</p>`, 'in-wide');
}

function pDrift(x) {
  if (!x || x.error) return errCard(24, 'Drift alarm', 'alerts', x?.error || 'no data');
  const k = { bad: 'bad', warn: 'warn', good: 'good' }[x.state] || '';
  const big = { bad: 'ALARM', warn: 'WATCH', good: 'OK', none: 'TOO EARLY' }[x.state] || '—';
  const rows = (x.drift || []).map((d) => `<div class="in-row in-line"><span>${esc(d.strategy || '?')}</span>${chip(esc(d.level || 'n/a'), { bad: 'bad', warn: 'warn', good: 'good' }[d.level] || '')}</div>
    <div class="in-sub">${esc(d.text || d.error || '')}</div>`).join('');
  const an = (x.anomalies || []).length ? `<div class="in-sub">Recent anomalies: ${(x.anomalies || []).map((a) => esc(a.text || a.kind || '')).join(' · ')}</div>` : '';
  return card(24, 'Drift alarm', 'alerts', esc(x.text || ''),
    `<div class="in-big ${k}">${big}</div>${rows}${an}<p class="in-foot">${esc(x.rule || '')} Source: ${esc(x.source || '')}.</p>`);
}

function pGrade(x) {
  if (!x || x.error) return errCard(25, 'Setup grade', 'star', x?.error || 'no data');
  const s = x.setup, t = x.last_trade;
  const g = s?.grade || t?.grade || '?';
  const gk = { A: 'good', B: '', C: 'warn' }[g] || '';
  let body = `<div class="in-grade"><div class="in-letter ${gk}">${esc(g)}</div><div>`;
  if (s) {
    body += `<div class="in-row"><b>${side(s.side)} setup ${esc(s.hm || '')} ET</b>${chip(esc(s.status || ''), s.status === 'filled' || s.status === 'armed' ? 'good' : '')}</div>
      <div class="in-sub">${s.points} of 4 points · ${s.rules_ok}/${s.rules_n} LIT rules pass · ${esc(s.source || '')}</div></div></div>
      <ul class="in-pts">${(s.detail || []).map((p) => `<li class="${p.ok ? 'ok' : p.ok === false ? 'no' : ''}"><span>${p.ok ? '✓' : p.ok === false ? '✗' : '·'}</span><div><b>${esc(p.label)}</b><em>${esc(p.text || '')}</em></div></li>`).join('')}</ul>`;
  } else {
    body += `<div class="in-sub">No setup today yet: the last trade is shown.</div></div></div>`;
  }
  if (t) body += `<div class="in-sub in-last">Last trade ${esc(t.day || '')}: ${side(t.side)} ${esc(t.exit || '')} ${R(t.r)} (${susd(t.pnl)}) · grade ${esc(t.grade || '?')}${t.cause ? ` · cause ${esc(t.cause)}` : ''} · ${esc(t.source || '')}</div>`;
  return card(25, 'Setup grade & confidence', 'star', esc(x.text || ''), body);
}

function pSimilar(x) {
  if (!x || x.error) return errCard(26, 'Similar past trades', 'stats', x?.error || 'no data');
  const G = x.groups || [];
  const tbl = `<div class="in-tbl"><table><thead><tr><th>Group</th><th>Trades</th><th>Won</th><th>Avg R</th><th>$ a trade</th><th>Net</th></tr></thead><tbody>${G.map((g) =>
    `<tr><td>${esc(g.name)}</td><td>${g.n}</td><td>${pct(g.win)}</td><td class="${cl(g.avg_r)}">${R(g.avg_r)}</td><td class="${cl(g.avg_usd)}">${susd(g.avg_usd)}</td><td class="${cl(g.net)}">${susd(g.net)}</td></tr>`).join('')}</tbody></table></div>`;
  const first = G[0]?.trades || [];
  const list = first.length ? `<div class="in-sub">Latest of “${esc(G[0].name)}”:</div><div class="in-trades">${first.map((t) =>
    `<div class="in-tr"><span>${esc(t.day)}</span>${side(t.side)}<span>${esc(t.exit || '')}</span><b class="${cl(t.r)}">${R(t.r)}</b><span class="${cl(t.pnl)}">${susd(t.pnl)}</span></div>`).join('')}</div>` : '';
  return card(26, 'Similar past trades', 'stats', esc(x.text || ''), tbl + list + `<p class="in-foot">${esc(x.source || '')}</p>`);
}

function pRegime(x) {
  if (!x || x.error) return errCard(27, 'Market regime', 'regime', x?.error || 'no data');
  const tr = (t, lab) => `<div><span>${lab}</span><b class="${t?.dir === 'up' ? 'up' : t?.dir === 'down' ? 'dn' : ''}">${esc(t?.dir || '—')}</b><em>${t ? `EMA 21 ${t.gap_pts > 0 ? '+' : ''}${num(t.gap_pts, 0)} pts vs 50` : ''}</em></div>`;
  const vb = { low: 'calm', mid: 'normal', high: 'nervous' }[x.vix_band] || '—';
  const n = x.news?.next;
  const rng = (x.ranges || []).map((r) => `<div class="in-rng"><div class="in-row"><b>${esc(r.name)}</b><span class="muted">${esc(r.window)}</span></div>
    <div class="in-sub">${r.range != null ? `${px(r.low)} – ${px(r.high)} · <b>${num(r.range, 0)} pts</b>${r.pct_avg != null ? ` = ${r.pct_avg}% of its 20-day average (${num(r.avg20, 0)})` : ''}` : 'not formed yet'}</div>
    ${r.pct_avg != null ? bar(Math.min(1, r.pct_avg / 200), r.pct_avg > 130 ? 'warn' : 'accent') : ''}</div>`).join('');
  const body = `<div class="in-grid4">
      <div><span>VIX</span><b>${num(x.vix)}</b><em>${vb}</em></div><div><span>VXN</span><b>${num(x.vxn)}</b><em>Nasdaq vol</em></div>
      ${tr(x.t15, '15m trend')}${tr(x.t60, '1h trend')}</div>
    ${x.up != null ? `<div class="in-sub">VIX band (Zlarior's target): 18:00 open ${px(x.open18)} ± ${num(x.move, 0)} pts → <b class="up">${px(x.up)}</b> / <b class="dn">${px(x.dn)}</b></div>` : ''}
    <div class="in-news">${icon('news')}<div>${n ? `<b>Next big news: ${esc(n.event)}</b><span>${esc(n.weekday || '')} ${esc(n.time || '')} ET · in <b class="in-cd" data-to="${n.t}">${dur(n.in_s)}</b></span>` : '<b>No high-impact news in the next 7 days.</b>'}
      ${(x.news?.today || []).length ? `<span class="muted">Today: ${(x.news.today || []).map((e) => `${esc(e.time)} ${esc(e.event)}`).join(' · ')}</span>` : ''}</div></div>
    ${rng}`;
  return card(27, 'Market regime', 'regime', esc(x.text || ''), body);
}

function pLevels(x) {
  if (!x || x.error) return errCard(28, 'LIT levels map', 'map', x?.error || 'no data');
  const price = x.price, atr = x.atr || 1;
  const near = [...(x.untouched || []).map((l) => ({ ...l, sw: false })), ...(x.swept || []).map((l) => ({ ...l, sw: true }))]
    .filter((l) => ok(l.price)).sort((a, b) => Math.abs(a.price - price) - Math.abs(b.price - price)).slice(0, 16)
    .sort((a, b) => b.price - a.price);
  const rows = [];
  let placed = false;
  for (const l of near) {
    if (!placed && l.price < price) { rows.push(`<div class="in-lv now"><span>${px(price)}</span><b>price now</b><em></em></div>`); placed = true; }
    const d = l.price - price;
    rows.push(`<div class="in-lv ${l.sw ? 'sw' : ''} ${l.side === 'H' ? 'hi' : 'lo'}"><span>${px(l.price)}</span><b>${esc(l.label)}</b>
      <em>${l.sw ? `swept ${esc(l.taken_hm || '')}${l.depth_atr != null ? ` · ${num(l.depth_atr)} ATR${l.depth_atr >= 0.5 ? ' ✓' : ''}` : ''}` : `${d > 0 ? '+' : ''}${num(d, 0)} pts · ${num(Math.abs(d) / atr, 1)} ATR`}</em></div>`);
  }
  if (!placed) rows.push(`<div class="in-lv now"><span>${px(price)}</span><b>price now</b><em></em></div>`);
  const legend = `<div class="nx-chips">${chip(`${(x.swept || []).length} swept`, 'warn')}${chip(`${(x.untouched || []).length} untouched`)}${chip('✓ = deep enough for LIT (0.5 ATR)')}</div>`;
  return card(28, 'LIT levels map', 'map', esc(x.text || ''), legend + `<div class="in-ladder">${rows.join('')}</div><p class="in-foot">The 16 levels nearest the price, highest first. Day ${esc(x.day || '')}, ATR ${num(x.atr, 1)} pts.</p>`);
}

function pAtlas(x) {
  if (!x || x.error) return errCard(29, 'ATLAS members', 'atlas', x?.error || 'no data');
  const rows = (x.rows || []).map((m) => {
    const h2 = m.research?.H2;
    return `<div class="in-mem">
      <div class="in-row"><b>${esc(m.short || m.key)} <span class="muted">${esc(m.label || '')}</span></b><span>${m.candidate ? chip('candidate') : ''}${chip(esc(m.route_label || 'paper'))}${stageChip(m.stage)}</span></div>
      <div class="in-sub">${esc(m.text || '')}</div>
      <div class="in-sub">Today: ${m.today?.length ? m.today.map((t) => `${esc(t.hm)} ${esc(t.side)} ${esc(t.exit_kind || 'open')} ${R(t.r)}`).join(' · ') : 'no trade'}
        · Last: ${m.last ? `${esc(m.last.day)} ${esc(m.last.side)} ${esc(m.last.exit_kind || '')} ${R(m.last.r)} (${susd(m.last.usd)})` : '—'}</div>
      ${h2 ? `<div class="in-sub">2026 H2 research: ${h2.n} trades · PF ${num(h2.pf)} · ${susd(h2.net)} (${susd(h2.per_month)}/mo) · ${num(h2.tpw)} a week</div>` : ''}
    </div>`;
  }).join('');
  return card(29, 'ATLAS members', 'atlas', esc(x.text || ''), rows || '<div class="in-empty">No ATLAS run yet.</div>');
}

function pS3(x) {
  if (!x || x.error) return errCard(30, 'Strategy 3 (research)', 'variants', x?.error || 'no data');
  const docs = (x.writeups || []).map((d) => `<div class="in-mem"><div class="in-row"><b>${esc(d.title)}</b>${chip(esc(d.status || ''))}</div><div class="in-sub">${esc(d.summary || '')}</div><div class="in-sub mono">${esc(d.file)}</div></div>`).join('');
  const grids = (x.data || []).filter((g) => g.kind === 'grid');
  const tbl = grids.length ? `<div class="in-tbl"><table><thead><tr><th>Family</th><th>Variants</th><th>Profitable H1 + H2, 2+/wk</th><th>Best (weaker half)</th></tr></thead><tbody>${grids.map((g) =>
    `<tr><td>${esc(g.family || '')} <span class="muted mono">${esc(String(g.file || '').split('/').pop().replace('.json', ''))}</span></td><td>${g.variants}</td><td>${g.both_halves}</td><td>${g.best ? `${esc(g.best.tf)} · PF ${num(g.best.H1?.pf)} / ${num(g.best.H2?.pf)} · ${susd(g.best.H2?.per_month)}/mo H2 · ${num(g.best.H2?.tpw, 1)}/wk` : '—'}</td></tr>`).join('')}</tbody></table></div>` : '';
  const other = (x.data || []).filter((g) => g.kind !== 'grid').map((d) => `<div class="in-sub mono">${esc(d.file)}${d.status ? ' · ' + esc(d.status) : ''}</div>`).join('');
  return card(30, 'Strategy 3 (research)', 'variants', esc(x.text || ''),
    `<div class="in-row"><b>${esc(x.name || 'Strategy 3')}</b>${chip('paper only · not routed')}</div>${docs}${tbl}${other}`, 'in-wide');
}

// ------------------------------------------------------------------ the page
function toolbar(d) {
  const mode = d?.mode || 'live';
  const lab = mode === 'live' ? chip('LIVE · the running bot', 'good') : mode === 'replay' ? chip('REPLAY', 'warn') : chip('BOT OFF · last session', 'warn');
  return `<div class="in-tool">${lab}<span class="muted">${esc(d?.at || '')}${d?.build_ms != null ? ` · built in ${(d.build_ms / 1000).toFixed(1)} s` : ''}</span>
    <span class="in-sp"></span>
    <label class="in-rp"><span>Replay</span><input type="date" id="inDay" min="2026-01-02" max="2026-12-31" value="${esc(P.replay?.day || '')}"><input type="time" id="inHm" value="${esc(P.replay?.hm || '10:00')}"></label>
    <button type="button" class="nx-chipbtn" id="inGo">${icon('replay')}<span>Replay</span></button>
    ${P.replay ? `<button type="button" class="nx-chipbtn" id="inLive">${icon('live')}<span>Back to live</span></button>` : ''}
    <button type="button" class="nx-chipbtn" id="inRefresh">${icon('refresh')}<span>Refresh</span></button></div>`;
}

function headline(d) {
  const L = d.radar?.lit || {}, w = (d.windows?.rows || [])[0]?.next, g = d.grade?.setup?.grade || d.grade?.last_trade?.grade;
  const dk = { bad: 'dn', warn: 'warn', good: 'up' }[d.drift?.state] || '';
  const tile = (k, v, s, c = '') => `<div class="nx-stat"><span>${k}</span><b class="${c}">${v}</b>${s ? `<em>${s}</em>` : ''}</div>`;
  return `<div class="nx-stats in-stats">
    ${d.mode === 'last' ? tile('Zlarior now', 'Bot off', `last session: ${esc(L.stage_label || '—')}`, 'warn') : tile('Zlarior now', esc(L.stage_label || '—'), `step ${L.stage_n || '?'} of 10`)}
    ${tile('Zlarior window', w ? (w.open ? 'open' : 'closed') : '—', w ? (w.open ? `closes in <span class="in-cd" data-to="${w.end_t}">${dur(w.closes_in_s)}</span>` : `opens in <span class="in-cd" data-to="${w.start_t}">${dur(w.opens_in_s)}</span>`) : '', w?.open ? 'up' : '')}
    ${tile('Drift', esc({ bad: 'Alarm', warn: 'Watch', good: 'OK', none: 'Too early' }[d.drift?.state] || '—'), 'live vs backtest', dk)}
    ${tile('Setup grade', esc(g || '—'), esc(d.grade?.confidence?.level ? d.grade.confidence.level + ' confidence' : ''))}
  </div>`;
}

function draw() {
  const el = $('#page-insight'); if (!el) return;
  const d = P.d;
  const hero = `<div class="nx-hero in-hero"><div><div class="nx-eyebrow">${icon('brain')} AI Insights · read-only</div><h2>What the bots see right now</h2>
    <p class="muted">What each strategy waits for, when it may trade next, whether live trading still looks like the backtest, and the market around it. Paper research and real data only; nothing on this page changes the bot.</p></div></div>`;
  if (!d) {
    el.innerHTML = hero + (P.err ? `<div class="banner warn">${esc(P.err)}</div>` : '<div class="in-skel"><i></i><i></i><i></i></div>');
    return;
  }
  el.innerHTML = hero + toolbar(d) + (P.err ? `<div class="banner warn">${esc(P.err)} (showing the last good data)</div>` : '') +
    (d.note ? `<div class="in-note">${icon('info')}<span>${esc(d.note)}</span></div>` : '') + headline(d) +
    `<div class="in-grid">${pRadar(d.radar)}${pWindows(d.windows)}${pGrade(d.grade)}${pScore(d.scorecard)}${pDrift(d.drift)}${pSimilar(d.similar)}${pRegime(d.regime)}${pLevels(d.levels)}${pAtlas(d.atlas)}${pS3(d.strategy3)}</div>`;
  $('#inRefresh').onclick = () => load(true);
  $('#inGo').onclick = () => {
    const day = $('#inDay').value, hm = $('#inHm').value || '10:00';
    if (!day) return;
    P.replay = { day, hm }; store.set('nx.in.replay', P.replay); P.d = null; draw(); load(true);
  };
  const lv = $('#inLive'); if (lv) lv.onclick = () => { P.replay = null; store.set('nx.in.replay', null); P.d = null; draw(); load(true); };
  tickNow();
}

// countdowns tick every second against the server's clock (a replay counts from its own minute)
function tickNow() {
  const d = P.d; if (!d) return;
  const base = d.windows?.now || d.t;
  const nowS = base + (Date.now() - P.at) / 1000 * (d.mode === 'replay' ? 0 : 1);
  document.querySelectorAll('#page-insight .in-cd[data-to]').forEach((e) => { e.textContent = dur(+e.dataset.to - nowS); });
}

const active = () => document.getElementById('page-insight')?.classList.contains('active');
export const insight = {
  show() {
    if (!P.d) draw();
    load();
    clearInterval(P.timer); clearInterval(P.tick);
    P.timer = setInterval(() => { if (!active()) { clearInterval(P.timer); clearInterval(P.tick); return; } if (!P.replay) load(); }, 30000);
    P.tick = setInterval(() => { if (active()) tickNow(); }, 1000);
  },
};
