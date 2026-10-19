import { $, esc, fmtN, api, etParts } from './util.js';
import { S, on } from './state.js';

let N = null, M = null;
export function init() { on(() => { if (S.page === 'briefing') render(); }); }
export async function show() {
  render();
  try { [N, M] = await Promise.all([api('/api/news', { params: S.params }), api('/api/markets')]); } catch (e) { /* offline */ }
  render();
}

const major = (p) => p.eq || /PDH|PDL|PWH|PWL|ONH|ONL|LOH|LOL|ASH|ASL|H1H|H1L/.test(p.label);
const todayET = () => { const p = etParts(Date.now() / 1000); return `${p.y}-${String(p.mo).padStart(2, '0')}-${String(p.d).padStart(2, '0')}`; };

// LIT (web_next: S.res.model 'lit'): the day plan from the LIT state (the PC bot's when it runs LIT, else the last bar's)
function litBrief(st) {
  const px = st.price, L0 = st.lit || {}, R = st.lit_rules || {}, sess = st.session || {};
  const setTitle = (id, t) => { const h = document.getElementById(id)?.closest('.card')?.querySelector('.card-h h3'); if (h) h.textContent = t; };
  setTitle('briefLevels', 'LIT levels'); setTitle('briefScen', 'Scenarios · LIT'); setTitle('briefBias', 'Session boxes & target band'); setTitle('briefRegime', 'Volatility · VIX target');
  const lv = (st.active_pools || []).map(p => ({ px: p.price, name: p.label, kind: p.kind === 'vix' ? 'TARGET' : p.side === 'H' ? 'BSL' : 'SSL', cls: p.kind === 'vix' ? 'gold' : p.side === 'H' ? 'bsl' : 'ssl', vix: p.kind === 'vix' }));
  if (px != null) lv.push({ px, name: 'LAST PRICE', kind: '', cls: 'now', now: true });
  lv.sort((a, b) => b.px - a.px);
  const near = px != null ? lv.filter(l => l.now || Math.abs(l.px - px) / px < 0.03) : lv;
  $('#briefLevels').innerHTML = near.length ? `<div class="lvls">${near.map(l => l.now
    ? `<div class="lv now"><span class="mono">${fmtN(l.px)}</span><b>◀ NQ last</b><span></span></div>`
    : `<div class="lv ${l.cls}"><span class="mono">${fmtN(l.px)}</span><span>${esc(l.name)}</span><span class="tagk">${l.kind} ${px != null ? `<span class="mono ${l.px > px ? 'up' : 'dn'}">${l.px > px ? '+' : ''}${fmtN(l.px - px, 1)}</span>` : ''}</span></div>`).join('')}</div>`
    : '<div class="empty">No LIT levels yet.</div>';
  const lvls = lv.filter(l => !l.now && !l.vix);
  const upNear = px != null ? lvls.filter(l => l.px > px).at(-1) : null, dnNear = px != null ? lvls.filter(l => l.px < px)[0] : null;
  const band = L0.open18 && L0.vix_move ? [L0.open18 - L0.vix_move, L0.open18 + L0.vix_move] : null;
  const mon = R.monday?.today;
  const sc = [];
  if (dnNear && mon !== 'high') sc.push(`<div class="scn long"><b>LONG</b> if price sweeps <b>${esc(dnNear.name)} ${fmtN(dnNear.px)}</b> (${fmtN(dnNear.px - px, 1)} pts) by at least half an ATR, after taking an inducement swing, then a bullish displacement candle and a 5m CISD close. Limit at the CISD level for 30 min, a 1m CISD to enter; stop 1 tick under the sweep low. Target ${band ? `<b>${fmtN(band[1])}</b> (18:00 open + one VIX day)` : 'the VIX band'}.</div>`);
  if (upNear && mon !== 'low') sc.push(`<div class="scn short"><b>SHORT</b> if price sweeps <b>${esc(upNear.name)} ${fmtN(upNear.px)}</b> (+${fmtN(upNear.px - px, 1)} pts) the same way: inducement first, bearish displacement, 5m CISD close, then the limit and a 1m CISD; stop 1 tick over the sweep high. Target ${band ? `<b>${fmtN(band[0])}</b> (18:00 open − one VIX day)` : 'the VIX band'}.</div>`);
  sc.push(`<div class="scn none"><b>NO TRADE</b> before 02:00 or after 15:30 ET, after the day's one trade, with a stop under 8 or over 80 pts, or a target under 1.5R.${mon === 'high' ? ' Monday rule: Friday\'s high was taken, shorts only.' : mon === 'low' ? ' Monday rule: Friday\'s low was taken, longs only.' : ''}</div>`);
  $('#briefScen').innerHTML = sc.join('');
  $('#briefBias').innerHTML = `<div class="state-grid">${Object.entries(sess).map(([k, [hi, lo]]) => `<div class="st"><div class="k">${esc(k)}</div><div class="v small">${fmtN(hi)} / ${fmtN(lo)}</div></div>`).join('') || '<div class="muted small">No session box closed yet.</div>'}
    <div class="st"><div class="k">Target band</div><div class="v small">${band ? `${fmtN(band[0], 0)} / ${fmtN(band[1], 0)}` : '—'}</div></div></div>
    <div class="note">${esc(R.monday?.text || 'Monday rule: on')}${R.weekly_stop?.text ? ' · ' + esc(R.weekly_stop.text) : ''}</div>`;
  const today = todayET();
  const ev = (N?.upcoming || []).filter(e => { const p = etParts(e.t); return `${p.y}-${String(p.mo).padStart(2, '0')}-${String(p.d).padStart(2, '0')}` === today; });
  $('#briefNews').innerHTML = ev.length ? `<table class="tbl">${ev.map(e => `<tr><td class="mono">${esc(String(e.time_et || '').slice(-5))}</td><td><span class="imp ${esc(e.impact)}"></span>${esc(e.event)}</td><td class="small muted">${e.impact === 'high' ? `blackout ${esc(blk(e.t, -15))}–${esc(blk(e.t, 30))}` : ''}</td></tr>`).join('')}</table>`
    : '<div class="empty">No high or medium-impact US releases today.</div>';
  const v = N?.volatility || {};
  $('#briefRegime').innerHTML = `<div class="big-status" style="font-size:22px">VIX ${L0.vix ? fmtN(L0.vix, 1) : v.VIX ? fmtN(v.VIX.last) : '—'}</div>
    <div class="acct-row"><span>One-day move from the 18:00 open</span><b>${L0.vix_move ? fmtN(L0.vix_move, 1) + ' pts' : '—'}</b></div>
    <div class="acct-row"><span>18:00 open</span><b>${L0.open18 ? fmtN(L0.open18) : '—'}</b></div>
    <div class="acct-row"><span>VIX / VXN now</span><b>${v.VIX ? fmtN(v.VIX.last) : '—'} / ${v.VXN ? fmtN(v.VXN.last) : '—'}</b></div>
    <div class="muted small" style="margin-top:6px">LIT has no regime rule: a higher VIX only widens the target band. Size follows the stop: $800 up to a 20-pt stop, less beyond.</div>`;
  const g = N?.guard, nx = g?.next_high;
  $('#briefHero').innerHTML = `<div class="bh-l"><div class="mini-label">LIT game plan · ${esc(L0.today || today)}</div>
      <h2>Wait for a LIT level to be swept, then inducement, displacement and a 5m CISD</h2>
      <p>NQ ${px != null ? fmtN(px) : '—'}${band ? ` · target band ${fmtN(band[0], 0)}–${fmtN(band[1], 0)}` : ''} · entries 02:00-15:30 ET, 1 trade a day, flat 15:55${nx ? ` · next red folder: ${esc(nx.event)} ${esc(nx.time_et)}` : ''}</p></div>
    <div class="bh-r"><div class="bh-chip ${g?.allowed === false ? 'block' : 'ok'}">${g ? (g.allowed ? 'CLEAR TO TRADE' : 'STAND DOWN') : 'PAPER'}</div>
      <div class="muted small">${esc(String(st.model_state || '').replace(/^LIT: /, ''))}</div></div>`;
}
function render() {
  const st = S.res?.state;
  if (!st) return;
  if (st.model === 'lit') return litBrief(st);
  const px = st.price, pf = st.profile, m = st.mtf || {}, gm = window.LE_GAMMA?.live;
  const lastDay = S.res.days.at(-1) || {};
  // ---- levels
  const lv = [];
  for (const p of st.active_pools || []) if (major(p)) lv.push({ px: p.price, name: p.label.replace('·', ' '), kind: p.side === 'H' ? 'BSL' : 'SSL', cls: p.side === 'H' ? 'bsl' : 'ssl' });
  if (pf) for (const [k, n] of [['vah', 'Prior VAH'], ['poc', 'Prior POC'], ['val', 'Prior VAL']]) lv.push({ px: pf[k], name: n, kind: 'AMT', cls: 'amt' });
  if (m.midnight_open) lv.push({ px: m.midnight_open, name: 'Midnight open', kind: 'OPEN', cls: 'gold' });
  if (gm && !gm.error) for (const [k, n] of [['call_wall', 'Call wall'], ['flip', 'Gamma flip'], ['put_wall', 'Put wall']]) if (gm[k]?.nq) lv.push({ px: gm[k].nq, name: n, kind: 'GAMMA', cls: 'gamma' });
  lv.push({ px, name: 'LAST PRICE', kind: '', cls: 'now', now: true });
  lv.sort((a, b) => b.px - a.px);
  const near = lv.filter(l => l.now || Math.abs(l.px - px) / px < 0.02);
  $('#briefLevels').innerHTML = `<div class="lvls">${near.map(l => l.now
    ? `<div class="lv now"><span class="mono">${fmtN(l.px)}</span><b>◀ ${S.sym} last</b><span></span></div>`
    : `<div class="lv ${l.cls}"><span class="mono">${fmtN(l.px)}</span><span>${esc(l.name)}</span><span class="tagk">${l.kind} <span class="mono ${l.px > px ? 'up' : 'dn'}">${l.px > px ? '+' : ''}${fmtN(l.px - px, 1)}</span></span></div>`).join('')}</div>`;
  // ---- scenarios (nearest major pool each side -> fade it toward the opposite major pool)
  const above = lv.filter(l => !l.now && l.px > px && l.kind === 'BSL'), below = lv.filter(l => !l.now && l.px < px && l.kind === 'SSL');
  const upNear = above.at(-1), dnNear = below[0];
  const h1 = m.structure?.['1H'] || 0;
  const sc = [];
  if (dnNear) sc.push(`<div class="scn long"><b>LONG</b> if price raids <b>${esc(dnNear.name)} ${fmtN(dnNear.px)}</b> (${fmtN(dnNear.px - px, 1)} pts) and a bullish IFVG closes back inside. Draw: <b>${esc(upNear?.name || 'nearest major high')}</b>${upNear ? ' ' + fmtN(upNear.px) : ''}.${h1 === 1 ? ' <span class="up">1H structure agrees: grades higher.</span>' : h1 === -1 ? ' <span class="dn">Counter to 1H structure: smaller size.</span>' : ''}</div>`);
  if (upNear) sc.push(`<div class="scn short"><b>SHORT</b> if price raids <b>${esc(upNear.name)} ${fmtN(upNear.px)}</b> (+${fmtN(upNear.px - px, 1)} pts) and a bearish IFVG closes back inside. Draw: <b>${esc(dnNear?.name || 'nearest major low')}</b>${dnNear ? ' ' + fmtN(dnNear.px) : ''}.${h1 === -1 ? ' <span class="up">1H structure agrees: grades higher.</span>' : h1 === 1 ? ' <span class="dn">Counter to 1H structure: smaller size.</span>' : ''}</div>`);
  sc.push(`<div class="scn none"><b>NO TRADE</b> if neither side is raided by 11:30, during news blackouts, or once the day has run 1.6× its normal range.</div>`);
  $('#briefScen').innerHTML = sc.join('');
  // ---- bias
  const arrow = (v) => v === 1 ? '<span class="up">▲</span>' : v === -1 ? '<span class="dn">▼</span>' : '<span class="muted">–</span>';
  const dr = m.dealing_range;
  $('#briefBias').innerHTML = `<div class="state-grid">${(m.tfs || []).map(r => `<div class="st"><div class="k">${r.tf} order flow</div><div class="v">${arrow(r.bias)} ${esc(r.last || '—')}</div></div>`).join('')}
    <div class="st"><div class="k">1H / 15m structure</div><div class="v">${arrow(m.structure?.['1H'])} / ${arrow(m.structure?.['15m'])}</div></div>
    <div class="st"><div class="k">Dealing range</div><div class="v">${dr ? `${Math.round(dr.pos * 100)}% · ${dr.pos >= 0.5 ? 'premium' : 'discount'}` : '—'}</div></div></div>
    <div class="note">Open vs prior value: <b>${esc((st.open_loc || '—').toUpperCase())}</b>${pf ? ` · prior POC ${fmtN(pf.poc, 0)}` : ''}</div>`;
  // ---- news today
  const today = todayET();
  const ev = (N?.upcoming || []).filter(e => {
    const p = etParts(e.t); return `${p.y}-${String(p.mo).padStart(2, '0')}-${String(p.d).padStart(2, '0')}` === today;
  });
  $('#briefNews').innerHTML = ev.length ? `<table class="tbl">${ev.map(e => `<tr><td class="mono">${esc(e.time_et.slice(-5))}</td><td><span class="imp ${esc(e.impact)}"></span>${esc(e.event)}</td><td class="small muted">${e.impact === 'high' ? `no entries ${esc(blk(e.t, -15))}–${esc(blk(e.t, 30))}` : ''}</td></tr>`).join('')}</table>`
    : '<div class="empty">No high or medium-impact US releases today.</div>';
  // ---- regime & volatility
  const v = N?.volatility || {};
  const reg = lastDay.regime || '—';
  $('#briefRegime').innerHTML = `<div class="big-status ${reg === 'trending' ? 'dn' : 'up'}" style="font-size:22px">${esc(reg.toUpperCase())}</div>
    <div class="acct-row"><span>10-day trend efficiency</span><b>${lastDay.er10 != null ? fmtN(lastDay.er10, 2) : '—'}</b></div>
    <div class="acct-row"><span>Bot sizing today</span><b>${reg === 'trending' ? 'half size (reversals fail in trends)' : 'normal'}</b></div>
    <div class="acct-row"><span>VIX / VXN</span><b>${v.VIX ? fmtN(v.VIX.last) : '—'} / ${v.VXN ? fmtN(v.VXN.last) : '—'} · ${esc(v.regime || '—')}</b></div>
    ${(M?.alerts || []).slice(0, 3).map(a => `<div class="note ${a.level === 'warn' ? 'dn' : ''}">⚠ ${esc(a.text)}</div>`).join('')}`;
  // ---- hero
  const g = N?.guard;
  const nx = g?.next_high;
  $('#briefHero').innerHTML = `<div class="bh-l"><div class="mini-label">Game plan · ${esc(today)}</div>
      <h2>${reg === 'trending' ? 'Trending market: fade sweeps carefully, half size' : 'Rotational market: sweep reversals are in play'}</h2>
      <p>${S.sym} ${fmtN(px)} · 1H ${h1 === 1 ? 'bullish' : h1 === -1 ? 'bearish' : 'neutral'} · ${dr ? (dr.pos >= 0.5 ? 'in premium of the 1H range' : 'in discount of the 1H range') : ''}${nx ? ` · next red folder: ${esc(nx.event)} ${esc(nx.time_et)}` : ''}</p></div>
    <div class="bh-r"><div class="bh-chip ${g?.allowed ? 'ok' : 'block'}">${g ? (g.allowed ? 'CLEAR TO TRADE' : 'STAND DOWN') : '…'}</div>
      <div class="muted small">${esc(st.model_state)}</div></div>`;
}
const blk = (t, min) => { const p = etParts(t + min * 60); return `${String(p.h).padStart(2, '0')}:${String(p.mi).padStart(2, '0')}`; };
