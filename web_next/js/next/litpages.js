// LIT panels on the PC dashboard (the same litkit.js as the phone site: tools/web_public/litkit.js, copied to /js/litkit.js
// by `cd tools/web_public/fx && npm run build`):
//   Modules → LIT Day plan    (#page-litday)     day clock (3D 'dayclock' / 2D svg), what happens next, pre-session checklist, week planner
//   Modules → LIT Levels      (#page-litlevels)  setup tracker (3D 'pipeline' + step rail), levels board, liquidity map (3D 'liqmap')
//   Modules → Eval cockpit    (#page-litcockpit) MFFU balance / room / daily limit, what one stop-out or winner does, odds from here
//   Today (command): a strip with the day clock and the setup tracker above the command grid
// Data: the PC bot's LIT state (/api/live/state: state.lit, state.session, state.active_pools, setups, position, lit_rules, ledger,
// bars), /api/next/lit_extra (plan, size rule, rules, boxes, 2026 stats), /api/dash/eval (the paper eval), /api/next/news?compact=1.
import * as LK from '../litkit.js?v=95dd2b40';
import { $, api, esc, fmt$ } from '../util.js';
import { L, onLive } from '../dash/live.js';
import { mount3d } from './fx3d.js';

let X = null, EV = null, EVat = 0, NW = null, NWat = 0, cur = null;
async function extras() {
  const now = Date.now();
  const jobs = [];
  if (!X) jobs.push(api('/api/next/lit_extra').then((d) => { if (d && !d.error) X = d; }).catch(() => null));
  if (now - EVat > 60000) { EVat = now; jobs.push(api('/api/dash/eval').then((d) => { EV = d; }).catch(() => null)); }
  if (now - NWat > 600000) { NWat = now; jobs.push(api('/api/next/news?compact=1').then((d) => { NW = d; }).catch(() => null)); }
  await Promise.all(jobs);
}
function ctx() {
  const ev = EV?.state ? { balance: EV.state.balance, profit: EV.state.profit, to_target: EV.target?.remaining, trailing_mll: EV.mll?.level, cushion: EV.mll?.cushion } : null;
  return LK.fromPC(L.live || {}, { plan: X?.plan, sizing: X?.sizing, rules: X?.rules, boxes: X?.boxes, stats: X?.stats, eval: ev,
    ledger: LK.pcLedger(L.live?.ledger), news: NW?.events || [], newsRules: NW?.bot_now?.rules || null, newsDays: NW?.days || [] });
}
const fxBox = (id, kind, h, fb = '') => `<div class="nx-fxwrap"><div class="fx3d ${kind}" id="${id}" style="height:${h}px"></div><div class="nx-2d" id="${id}2d">${fb}</div></div>`;
const card = (title, body, tools = '') => `<div class="card nx-glass"><div class="card-h"><h3>${title}</h3>${tools ? `<div class="card-tools">${tools}</div>` : ''}</div>${body}</div>`;
const hero = (eyebrow, title, desc) => `<div class="nx-hero"><div><div class="nx-eyebrow">${eyebrow}</div><h2>${title}</h2><p class="muted">${desc}</p></div></div>`;
const noBot = () => !L.live?.state || L.live.state.model !== 'lit'
  ? `<div class="card nx-glass"><div class="muted">The PC paper bot is not running LIT right now (Modules → Paper Bot). The panels show the rules and the 2026 numbers; levels and setups appear once it runs.</div></div>` : '';
function phase(C) { if (C.closed) return 'Market closed'; const p = LK.et(C.now), m = p.min; return m >= 1080 || m < 120 ? 'Asia session' : m < 300 ? 'London session' : m < 570 ? 'Pre-market' : m < 690 ? 'New York AM' : m < 810 ? 'New York lunch' : m < 960 ? 'New York PM' : m < 1020 ? 'After hours' : 'Daily halt'; }

// ------------------------------------------------------------------ pages
async function showDay() {
  cur = 'litday'; const el = $('#page-litday'); if (!el) return;
  await extras(); if (cur !== 'litday') return;
  const C = ctx();
  el.innerHTML = hero(`LIT day · ${esc(C.day)} · ET`, phase(C), 'The LIT trading day from the 18:00 open to the 17:00 close: the session boxes LIT takes its levels from, the 02:00-15:30 entry window, USD news and the bot’s trade. 95 of 120 LIT trades in 2026 entered 02:00-08:00 ET: NinjaTrader and this PC must be up from about 01:55 ET.')
    + noBot()
    + card('Day clock', fxBox('nxLitClock', 'dayclock', 440, LK.clockSVG(C)), '<span class="muted small">18:00 → 17:00 ET</span>')
    + `<div class="grid cols-2">${card('What happens next', LK.planHTML(C))}${card('Before the session', LK.readyHTML(C))}</div>`
    + card('This week', LK.weekHTML(C));
  mount3d('pc-litclock', $('#nxLitClock'), 'dayclock', LK.clockData(C), {});
}
async function showLevels() {
  cur = 'litlevels'; const el = $('#page-litlevels'); if (!el) return;
  await extras(); if (cur !== 'litlevels') return;
  const C = ctx(), R = LK.rail(C), Lv = LK.levels(C).filter((r) => !r.target);
  el.innerHTML = hero(`LIT levels · NQ ${C.price ? C.price.toLocaleString('en-US', { minimumFractionDigits: 2 }) : '—'}`, esc(R.why[0].toUpperCase() + R.why.slice(1)),
      `${Lv.length} levels today, ${Lv.filter((r) => r.taken).length} taken. LIT waits for one to be swept by half an ATR or more, then for inducement, displacement and a 5-minute CISD; then a limit at the CISD level for 30 minutes and a 1-minute CISD.`)
    + noBot()
    + card('Setup tracker', `<div class="nx-fxwrap"><div class="fx3d pipeline" id="nxLitRail" style="height:300px"></div><div class="nx-2d"></div></div><div style="margin-top:14px">${LK.railHTML(C)}</div>`)
    + `<div class="grid cols-2">${card('Levels board', LK.levelsHTML(C, { max: 20 }), '<span class="muted small">pts · $ per MNQ</span>')}
      ${card('Liquidity map', fxBox('nxLitLiq', 'liqmap', 520, '<div class="muted small">3D is off: the board on the left has every level.</div>'))}</div>`;
  mount3d('pc-litrail', $('#nxLitRail'), 'pipeline', LK.railData(C), {});
  const pools = Lv.filter((r) => !r.taken && Number.isFinite(r.dist)).map((r) => ({ price: r.price, side: r.side, label: r.label.split(' · ')[0], strength: r.strength }));
  mount3d('pc-litliq', $('#nxLitLiq'), 'liqmap', { price: C.price, pools, bars: C.bars.slice(-40), position: C.position }, {});
}
let span = 'H2';
async function showCockpit() {
  cur = 'litcockpit'; const el = $('#page-litcockpit'); if (!el) return;
  await extras(); if (cur !== 'litcockpit') return;
  const C = ctx(), K = LK.cockpit(C), sim = LK.evalSim(C, { span });
  el.innerHTML = hero('MFFU Builder 50K · eval cockpit (paper)', `${fmt$(K.toTarget)} to pass · ${fmt$(K.cushion)} of room`, 'What the next LIT trade can do to the paper eval, and the odds from this balance. Owner’s rule: decided within 2 weeks (10 sessions), passed within 3 (15).')
    + `<div class="grid cols-2">${card('Cockpit', LK.cockpitHTML(C, sim))}
      ${card('From here · simulated evals', fxBox('nxLitMc', 'montecarlo', 460, `<div class="muted">${sim ? `${sim.pass10}% pass / ${sim.fail10}% fail within 2 weeks; ${sim.pass15}% pass within 3 weeks; median ${sim.med ?? '—'} sessions.` : 'No 2026 sessions.'}</div>`),
        `<div class="seg sm" id="nxCkSpan">${[['H2', '2026 H2'], ['2026', '2026']].map(([v, l]) => `<button type="button" data-v="${v}" class="${v === span ? 'on' : ''}">${l}</button>`).join('')}</div>`)}</div>`
    + card('Before the session', LK.readyHTML(C));
  $('#nxCkSpan').onclick = (e) => { const b = e.target.closest('button[data-v]'); if (b) { span = b.dataset.v; showCockpit(); } };
  if (sim) mount3d('pc-litmc', $('#nxLitMc'), 'montecarlo', LK.simPayload(sim), {});
}

// ------------------------------------------------------------------ Today strip (command page)
async function todayStrip() {
  const t = $('#nxToday3'); if (!t) return;
  let box = $('#nxLitToday');
  if (!box) { box = document.createElement('div'); box.id = 'nxLitToday'; box.className = 'nx-today3'; t.parentNode.insertBefore(box, t); }
  await extras();
  const C = ctx();
  if (!L.live?.state || L.live.state.model !== 'lit') { box.innerHTML = ''; return; }
  const sig = JSON.stringify([C.model_state, C.position?.stop, Object.keys(C.setups || {}), C.dayTrades.length, Math.floor(C.now / 60)]);
  if (sig === box.dataset.sig) return; box.dataset.sig = sig;
  box.innerHTML = `<div class="card nx-glass nx-t3"><div class="card-h"><h3>LIT day · ${esc(phase(C))}</h3><div class="card-tools"><button class="btn ghost sm" type="button" data-goto="litday">Day plan</button></div></div>
      ${fxBox('nxLitTClock', 'dayclock', 320, LK.clockSVG(C))}<div style="margin-top:12px">${LK.planHTML(C, { compact: true })}</div></div>
    <div class="card nx-glass nx-t3"><div class="card-h"><h3>Setup tracker</h3><div class="card-tools"><button class="btn ghost sm" type="button" data-goto="litlevels">Levels</button></div></div>${LK.railHTML(C)}</div>`;
  mount3d('pc-littoday', $('#nxLitTClock'), 'dayclock', LK.clockData(C), {});
}

export const litday = { show: showDay };
export const litlevels = { show: showLevels };
export const litcockpit = { show: showCockpit };
export function initLitToday() {
  todayStrip();
  let at = 0;   // an open LIT page redraws with the live poll at most every 30 s (it replaces its HTML)
  onLive(() => { todayStrip(); if (Date.now() - at < 30000) return; if (cur && document.getElementById('page-' + cur)?.classList.contains('active')) { at = Date.now(); ({ litday: showDay, litlevels: showLevels, litcockpit: showCockpit })[cur]?.(); } });
  setInterval(() => { if (!document.hidden) todayStrip(); }, 60000);
}
