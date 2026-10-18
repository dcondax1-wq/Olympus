import { $, seg, esc, fmtN, fmtS$, cls, etStr, store, toast, tradingDay } from './util.js';
import { S, on, loadBars } from './state.js';
import { TradeChart } from './chart.js';
import { feed } from './app.js';

let tc = null, bars = [], ctx0 = 0, start = 0, end = 0, k = 0, timer = null, speed = store.get('rpSpeed', 5);
let day = null, evs = [], lastShown = 0;
let pp = { pos: null, realized: 0, n: 0, wins: 0 };
let stale = true;

export function init() {
  on(() => { stale = true; if (S.page === 'replay') setupDays(); });
  $('#rpPlay').onclick = () => (timer ? pause() : play());
  $('#rpStart').onclick = () => { pause(); jump(start); };
  $('#rpBack').onclick = () => { pause(); jump(Math.max(start, k - 1)); };
  $('#rpFwd').onclick = () => { pause(); stepFwd(); };
  $('#rpNextEv').onclick = () => { pause(); nextEvent(); };
  $('#rpScrub').oninput = (e) => { pause(); jump(start + (+e.target.value)); };
  $('#rpDay').onchange = (e) => loadDay(e.target.value);
  $('#ppBuy').onclick = () => practice(1);
  $('#ppSell').onclick = () => practice(-1);
  $('#ppFlat').onclick = () => practice(0);
  seg($('#rpSpeed'), [[1, '1×'], [2, '2×'], [5, '5×'], [10, '10×'], [25, '25×']], speed, (v) => { speed = +v; store.set('rpSpeed', speed); if (timer) { pause(); play(); } });
  document.addEventListener('keydown', (e) => {
    if (S.page !== 'replay' || e.target.matches('input,select,textarea')) return;
    if (e.code === 'Space') { e.preventDefault(); timer ? pause() : play(); }
    if (e.code === 'ArrowRight') { pause(); stepFwd(); }
    if (e.code === 'ArrowLeft') { pause(); jump(Math.max(start, k - 1)); }
    if (e.key === 'b') practice(1);
    if (e.key === 's') practice(-1);
    if (e.key === 'f') practice(0);
  });
}

export function show() {
  if (!tc) tc = new TradeChart($('#rpChart'), { legend: $('#rpLegend'), minFvg: S.meta?.instruments?.[S.sym]?.min_fvg ?? 3 });
  if (stale) setupDays();
}
export function retheme() { tc?.applyTheme(); }

async function setupDays() {
  if (!S.res || !tc) return;
  stale = false;
  bars = await loadBars(S.res?.model === 'lit' ? 'NQ' : S.sym, S.tf);   // LIT trades NQ
  const days = S.res.days;
  $('#rpDay').innerHTML = days.map(d => `<option value="${d.date}">${d.date} ${d.trades ? (d.pnl > 0 ? '★ +' : '☆ ') + Math.round(d.pnl) : ''}</option>`).reverse().join('');
  const pick = S.res.trades.length ? S.res.trades.at(-1).day : days.at(-1).date;
  $('#rpDay').value = pick;
  tc.setAnnotations({ pools: S.res.pools, ifvgs: S.res.ifvgs, trades: S.res.trades, profiles: S.res.profiles, htf_fvgs: S.res.htf_fvgs, sweeps: S.res.events.filter(e => e.type === 'sweep' && e.dir && !e.text.startsWith('Also')),
    mode: S.res.model === 'lit' ? 'lit' : null, boxes: S.res.boxes || [] });
  loadDay(pick);
}

function loadDay(d) {
  pause();
  day = d;
  const idx = [];
  bars.forEach((b, i) => { if (b.d === d) idx.push(i); });
  if (!idx.length) return;
  ctx0 = Math.max(0, idx[0] - Math.round(13 * 3600 / secs()));
  // LIT enters 02:00-15:30 ET (most trades 02:00-08:00): the replay starts at 01:00; the previous engine's at 08:00
  const from = S.res?.model === 'lit' ? 60 : 480;
  start = idx.find(i => bars[i].mod >= from && bars[i].mod < 1080) ?? idx[0];
  end = idx.at(-1);
  evs = S.res.events.filter(e => tradingDay(e.t) === d);
  pp = { pos: null, realized: 0, n: 0, wins: 0 };
  $('#rpScrub').max = end - start;
  jump(start, true);
}
const secs = () => ({ '1m': 60, '5m': 300 }[S.tf] || 300);

function jump(i, fit = false) {
  k = Math.max(start, Math.min(end, i));
  tc.setBars(bars.slice(ctx0, k + 1), secs());
  tc.setCursor(bars[k].t);
  tc.setLegendBase(`<b>REPLAY</b> ${S.res?.model === 'lit' ? 'NQ · LIT' : S.sym} ${day}`);
  if (fit || true) tc.scrollToEnd(Math.round(12 * 3600 / secs()));
  lastShown = 0;
  update();
}

function stepFwd() {
  if (k >= end) { pause(); toast('End of session'); return false; }
  k++;
  tc.appendBar(bars[k]);
  tc.setCursor(bars[k].t);
  const ts = tc.chart.timeScale();
  const vr = ts.getVisibleLogicalRange();
  if (vr && vr.to < tc.bars.length + 2) ts.scrollToRealTime();
  update();
  return true;
}

function play() {
  if (k >= end) jump(start);
  $('#rpPlay').textContent = '⏸ Pause';
  timer = setInterval(() => { if (!stepFwd()) pause(); }, 1000 / speed);
}
function pause() {
  clearInterval(timer); timer = null;
  $('#rpPlay').textContent = '▶ Play';
}
function nextEvent() {
  const t = bars[k].t;
  const ev = evs.find(e => e.t > t && ['sweep', 'signal', 'entry', 'exit', 'skip'].includes(e.type));
  if (!ev) { toast('No more bot events this session'); return; }
  let i = k;
  while (i < end && bars[i].t < ev.t) i++;
  jump(i);
}

function update() {
  const b = bars[k];
  const t = b.t;
  $('#rpTime').textContent = `${etStr(t, true)} ET`;
  $('#rpScrub').value = k - start;
  const shown = evs.filter(e => e.t <= t).reverse();
  feed($('#rpFeed'), shown, { newSince: lastShown || t - 1 });
  lastShown = t;
  // bot P&L as of cursor
  let botReal = 0, botOpen = 0, openTxt = '';
  for (const tr of S.res.trades.filter(x => x.day === day)) {
    if (tr.exit_t <= t) botReal += tr.pnl;
    else if (tr.entry_t <= t) {
      botOpen = (b.c - tr.entry) * tr.dir * tr.qty * S.meta.instruments[S.sym].micro_pv;
      openTxt = `${tr.dir === 1 ? 'LONG' : 'SHORT'} open`;
    }
  }
  const ppOpen = pp.pos ? (b.c - pp.pos.entry) * pp.pos.dir * pp.pos.qty * S.meta.instruments[S.sym].micro_pv : 0;
  $('#rpHud').innerHTML = `<div class="chip">${fmtN(b.c)}</div>
    <div class="chip">BOT <span class="${cls(botReal + botOpen)}">${fmtS$(botReal + botOpen)}</span>${openTxt ? ' · ' + openTxt : ''}</div>
    <div class="chip">YOU <span class="${cls(pp.realized + ppOpen)}">${fmtS$(pp.realized + ppOpen)}</span>${pp.pos ? (pp.pos.dir === 1 ? ' · LONG' : ' · SHORT') : ''}</div>`;
  $('#ppStats').innerHTML = `
    <div class="st"><div class="k">Your realized</div><div class="v ${cls(pp.realized)}">${fmtS$(pp.realized)}</div></div>
    <div class="st"><div class="k">Your open</div><div class="v ${cls(ppOpen)}">${fmtS$(ppOpen)}</div></div>
    <div class="st"><div class="k">Your trades</div><div class="v">${pp.n} · ${pp.n ? Math.round(pp.wins / pp.n * 100) : 0}% win</div></div>
    <div class="st"><div class="k">Bot so far</div><div class="v ${cls(botReal + botOpen)}">${fmtS$(botReal + botOpen)}</div></div>
    <div class="muted small" style="grid-column:span 2">Keys: <b>Space</b> play/pause · <b>← →</b> step · <b>B</b> buy · <b>S</b> sell · <b>F</b> flat</div>`;
}

function practice(dir) {
  const b = bars[k];
  const pv = S.meta.instruments[S.sym].micro_pv;
  const qty = Math.max(1, Math.min(40, +$('#ppQty').value || 1));
  const close = () => {
    if (!pp.pos) return;
    const pnl = (b.c - pp.pos.entry) * pp.pos.dir * pp.pos.qty * pv - pp.pos.qty * 1.5;
    pp.realized += pnl; pp.n++; if (pnl > 0) pp.wins++;
    toast(`Closed ${pp.pos.dir === 1 ? 'long' : 'short'}: ${fmtS$(pnl)}`);
    pp.pos = null;
  };
  if (dir === 0) close();
  else if (pp.pos && pp.pos.dir !== dir) close();
  else if (!pp.pos) { pp.pos = { dir, qty, entry: b.c, t: b.t }; toast(`${dir === 1 ? 'Bought' : 'Sold'} ${qty} M${S.sym} @ ${fmtN(b.c)}`); }
  update();
}
