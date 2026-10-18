import { $, $$, seg, esc, fmtN, fmt$, fmtS$, fmtR, cls, etStr, store, tradingDay } from './util.js';
import { S, on, loadBars, litStart } from './state.js';
import { TradeChart, LAYERS, LAYERS_LIT } from './chart.js';
import { feed } from './app.js';

let tc = null;
let tf = store.get('chartTf', '5m');
let curDay = null;
let tradeIdx = -1;
let pendingFocus = null;

const TF_SECS = { '1m': 60, '5m': 300, '15m': 900, '1h': 3600 };

export function init() {
  on(() => { if (S.page === 'chart') refresh(); else stale = true; });
  $('#prevDay').onclick = () => stepDay(-1);
  $('#nextDay').onclick = () => stepDay(1);
  $('#prevTrade').onclick = () => stepTrade(-1);
  $('#nextTrade').onclick = () => stepTrade(1);
  $('#fitAll').onclick = () => tc?.fit();
  $('#daySel').onchange = (e) => focusDay(e.target.value);
  document.addEventListener('le-gamma', (e) => { if (tc && S.sym === 'NQ') tc.setAnnotations({ gamma: e.detail?.live }); });
}
let stale = true;

export function show() {
  if (!tc) {
    tc = new TradeChart($('#mainChart'), { legend: $('#mainLegend'), minFvg: S.meta?.instruments?.[S.sym]?.min_fvg ?? 3 });
    const lay = store.get('layers', null);
    if (lay) for (const k in lay) tc.layers[k] = lay[k];
    renderLayerSeg();
  }
  if (stale) refresh();
}
export function retheme() { tc?.applyTheme(); }

const litMode = () => S.res?.model === 'lit';
function renderLayerSeg() {
  const el = $('#chartLayers');
  el.dataset.mode = litMode() ? 'lit' : 'eng';
  el.innerHTML = (litMode() ? LAYERS_LIT : LAYERS).map(([k, label]) => `<button data-k="${k}" class="${tc.layers[k] ? 'on' : ''}">${label}</button>`).join('');
  el.onclick = (e) => {
    const b = e.target.closest('button'); if (!b) return;
    const k = b.dataset.k; tc.setLayer(k, !tc.layers[k]); b.classList.toggle('on', tc.layers[k]);
    store.set('layers', tc.layers);
  };
}

async function refresh() {
  if (!S.res || !tc) return;
  stale = false;
  if ($('#chartLayers').dataset.mode !== (litMode() ? 'lit' : 'eng')) renderLayerSeg();
  const avail = (S.meta.available[litMode() ? 'NQ' : S.sym] || []).filter(x => TF_SECS[x]);
  if (!avail.includes(tf)) tf = '5m';
  seg($('#chartTf'), avail.map(x => [x, x]), tf, async (v) => { tf = v; store.set('chartTf', v); await loadInto(); });
  tc.minFvg = S.meta.instruments[S.sym]?.min_fvg ?? 3;
  const days = S.res.days.map(d => d.date);
  $('#daySel').innerHTML = days.map(d => {
    const dd = S.res.days.find(x => x.date === d);
    return `<option value="${d}">${d} · ${dd.trades ? (dd.pnl >= 0 ? '+' : '') + Math.round(dd.pnl) : '—'}</option>`;
  }).join('');
  await loadInto();
}

async function loadInto() {
  const bars = await loadBars(litMode() ? 'NQ' : S.sym, tf, litStart());   // LIT trades NQ
  tc.setBars(bars, TF_SECS[tf]);
  const r = S.res;
  tc.setAnnotations({ pools: r.pools, ifvgs: r.ifvgs, trades: r.trades, profiles: r.profiles, htf_fvgs: r.htf_fvgs, sweeps: r.events.filter(e => e.type === 'sweep' && e.dir && !e.text.startsWith('Also')),
    mode: r.model === 'lit' ? 'lit' : null, boxes: r.boxes || [] });
  tc.setLegendBase(r.model === 'lit' ? `<b>NQ</b> ${tf} · ET · LIT` : `<b>${S.sym}</b> ${tf} · ET`);
  if (S.sym === 'NQ' && window.LE_GAMMA) tc.setAnnotations({ gamma: window.LE_GAMMA.live });
  if (pendingFocus) { const f = pendingFocus; pendingFocus = null; f(); }
  else focusDay(curDay || lastTradeDay());
}

function lastTradeDay() { return S.res.trades.at(-1)?.day || S.res.days.at(-1)?.date; }

export function focusDay(d) {
  if (!tc || !d) return;
  curDay = d;
  $('#daySel').value = d;
  const bars = tc.bars;
  const idx = bars.map((b, i) => [b, i]).filter(([b]) => b.d === d);
  if (!idx.length) return;
  // show from prior evening 18:00 through the session
  const from = litMode() ? 60 : 480;
  const a = idx.find(([b]) => b.mod >= from && b.mod < 1080)?.[1] ?? idx[0][1];
  const z = idx.at(-1)[1];
  tc.focusRange(bars[a].t, bars[Math.min(z, bars.length - 1)].t, Math.round(60 * 300 / TF_SECS[tf]));
  renderSide(d);
}

function stepDay(k) {
  const days = S.res.days.map(x => x.date);
  const i = days.indexOf(curDay);
  focusDay(days[Math.max(0, Math.min(days.length - 1, i + k))]);
}
function stepTrade(k) {
  const n = S.res.trades.length;
  if (!n) return;
  tradeIdx = tradeIdx < 0 ? (k > 0 ? 0 : n - 1) : Math.max(0, Math.min(n - 1, tradeIdx + k));
  showTrade(tradeIdx);
}
function showTrade(i) {
  const t = S.res.trades[i];
  curDay = t.day;
  $('#daySel').value = t.day;
  tc.focusRange(t.entry_t - 3 * 3600, t.exit_t + 3600, 10);
  renderSide(t.day, t);
}
export function openTrade(i) {
  tradeIdx = i;
  if (tc && !stale) showTrade(i);
  else pendingFocus = () => showTrade(i);
}
export function openDay(d) {
  if (tc && !stale) focusDay(d);
  else pendingFocus = () => focusDay(d);
}

function renderSide(d, sel = null) {
  const r = S.res;
  const day = r.days.find(x => x.date === d) || {};
  const trs = r.trades.filter(t => t.day === d);
  const evs = r.events.filter(e => tradingDay(e.t) === d);
  const pf = r.profiles?.[d];
  let html = `<div class="card-h"><h3>${d}</h3><span class="pill ${day.pnl > 0 ? 'good' : day.pnl < 0 ? 'bad' : ''}">${fmtS$(day.pnl || 0)}</span></div>`;
  if (pf) html += `<div class="state-grid" style="margin-bottom:10px"><div class="st"><div class="k">prior POC</div><div class="v">${fmtN(pf.poc, 2)}</div></div><div class="st"><div class="k">prior VA</div><div class="v small">${fmtN(pf.val, 0)} – ${fmtN(pf.vah, 0)}</div></div></div>`;
  for (const t of (sel ? [sel] : trs)) html += tradeCard(t);
  if (!trs.length) html += `<div class="note">No trade this session.</div>`;
  html += `<div class="mini-label" style="margin:12px 0 6px">Session log</div><div class="feed" id="sideFeed"></div>`;
  $('#chartSide').innerHTML = html;
  feed($('#sideFeed'), evs);
}

function litCard(t) {
  const L = t.dir === 1, rep = t.report || {};
  return `<div class="card" style="box-shadow:none;background:var(--surface-2);margin-bottom:10px">
    <div class="card-h"><span class="dir ${L ? 'L' : 'S'}">${L ? 'LONG' : 'SHORT'} · ${esc(t.qty_label)}</span><b class="mono ${cls(t.pnl)}">${fmtS$(t.pnl)} · ${fmtR(t.pnl_r)}</b></div>
    <div class="state-grid">
      <div class="st"><div class="k">Entry · ${esc(t.entry_kind || 'LIT')}</div><div class="v">${fmtN(t.entry)} <span class="muted small">${etStr(t.entry_t)}</span></div></div>
      <div class="st"><div class="k">Exit · ${esc(t.exit_reason)}</div><div class="v">${fmtN(t.exit_price)} <span class="muted small">${etStr(t.exit_t)}</span></div></div>
      <div class="st"><div class="k">Stop · beyond the sweep</div><div class="v dn">${fmtN(t.stop0 ?? t.stop)}</div></div>
      <div class="st"><div class="k">Target · ${fmtN(t.rr, 2)}R</div><div class="v up">${fmtN(t.target)}</div></div>
      <div class="st"><div class="k">Risk</div><div class="v">${fmtN(t.risk_pts, 2)} pts · ${fmt$(t.risk_usd)}</div></div>
      <div class="st"><div class="k">Best point</div><div class="v">${t.mfe != null ? fmtR(t.mfe) : '—'}</div></div>
    </div>
    <div class="note"><b>Swept</b> ${esc(t.pools.join(', ') || '—')}${t.sweep_ext != null ? ` (extreme ${fmtN(t.sweep_ext)})` : ''}<br>5m CISD ${t.cisd_level != null ? fmtN(t.cisd_level) : '—'} · target <b>${esc(t.target_label)}</b>${t.half || t.weekly_stop ? ' · <span class="dn">half size (weekly stop)</span>' : ''}</div>
    ${(rep.why || []).length ? `<div class="small" style="margin-top:6px;line-height:1.55">${rep.why.map(w => `• ${esc(w)}`).join('<br>')}</div>` : ''}
    ${rep.result ? `<div class="small muted" style="margin-top:6px">${esc(rep.result)}${(rep.lessons || []).length ? ' · ' + esc(rep.lessons.join('; ')) : ''}</div>` : ''}
    <div style="margin-top:6px">${(t.conf_tags || []).map(x => `<span class="tag-chip">${esc(x)}</span>`).join('')}</div>
  </div>`;
}
export function tradeCard(t) {
  if (t.trigger === 'LIT') return litCard(t);
  const L = t.dir === 1;
  return `<div class="card" style="box-shadow:none;background:var(--surface-2);margin-bottom:10px">
    <div class="card-h"><span class="dir ${L ? 'L' : 'S'}">${L ? 'LONG' : 'SHORT'} · ${esc(t.qty_label)}</span><b class="mono ${cls(t.pnl)}">${fmtS$(t.pnl)} · ${fmtR(t.pnl_r)}</b></div>
    <div class="state-grid">
      <div class="st"><div class="k">Entry</div><div class="v">${fmtN(t.entry)} <span class="muted small">${etStr(t.entry_t)}</span></div></div>
      <div class="st"><div class="k">Exit · ${t.exit_reason}</div><div class="v">${fmtN(t.exit_price)} <span class="muted small">${etStr(t.exit_t)}</span></div></div>
      <div class="st"><div class="k">Stop</div><div class="v dn">${fmtN(t.stop0 ?? t.stop)}</div></div>
      <div class="st"><div class="k">Target · ${t.rr}R</div><div class="v up">${fmtN(t.target)}</div></div>
      <div class="st"><div class="k">Risk</div><div class="v">${fmtN(t.risk_pts, 2)} pts</div></div>
      <div class="st"><div class="k">MFE / MAE</div><div class="v">${fmtN(t.mfe, 2)}R / ${fmtN(t.mae, 2)}R</div></div>
    </div>
    <div class="note"><b>${t.trigger}</b> after sweeping ${esc(t.pools.join(', '))}<br>Draw on liquidity: <b>${esc(t.target_label)}</b> · score ${t.score}</div>
    ${t.mtf_bias ? `<div class="machine" style="margin:8px 0 0">${Object.entries(t.mtf_bias).map(([tf, v]) => `<span class="${v * t.dir > 0 ? 'on' : ''}" style="${v * t.dir < 0 ? 'background:var(--bad);color:#fff' : ''}">${tf} ${v === 1 ? '▲' : v === -1 ? '▼' : '–'}</span>`).join('')}
      ${t.pd_pos != null ? `<span>${Math.round(t.pd_pos * 100)}% of range</span>` : ''}${t.key_level ? `<span class="on">${esc(t.key_level)}</span>` : ''}</div>` : ''}
    ${t.checklist ? `<div class="grade-row"><span class="grade g-${esc(t.grade).replace('+', 'p')}">${esc(t.grade)}</span>
      <span class="small muted">${t.grade_points} pts · size ×${t.grade_mult}</span></div>
      <div class="checklist">${t.checklist.map(c => `<div class="ck ${c.state > 0 ? 'yes' : c.state < 0 ? 'no' : 'na'} ${c.weight ? '' : 'ctx'}">
        <span class="ic">${c.state > 0 ? '✓' : c.state < 0 ? '✗' : '–'}</span><span>${esc(c.label)}</span><span class="w">${c.weight ? (c.state * c.weight > 0 ? '+' : c.state * c.weight < 0 ? '−' : '') + (c.state ? c.weight : 0) : 'info'}</span></div>`).join('')}</div>` : ''}
    <div style="margin-top:6px">${t.conf_tags.map(x => `<span class="tag-chip">${esc(x)}</span>`).join('')}</div>
  </div>`;
}
