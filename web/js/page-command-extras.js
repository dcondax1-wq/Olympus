// Command Center extras: what-if sliders, edge-decay monitor and MFFU rules gauges (rendered into #cmdWhatIf, #cmdEdge, #cmdRules).
import { $, api, esc, fmt$, fmtS$, fmtN, fmtR, cls, css } from './util.js';
import { S, on, effective } from './state.js';

const CSS = `
#cmdExtras{margin-top:0}
.wi-row{display:grid;grid-template-columns:1fr auto;gap:10px;align-items:center;margin-top:10px;font-size:12.5px;color:var(--ink-2)}
.wi-row b{font-family:var(--mono);color:var(--ink);font-size:13px;min-width:64px;text-align:right}
.wi-row input[type=range]{grid-column:1/-1;width:100%;accent-color:var(--accent);height:22px;margin:0}
.wi-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin-top:14px}
.wi-cell{background:var(--surface-2);border:1px solid var(--border);border-radius:10px;padding:9px 10px;position:relative;overflow:hidden}
.wi-cell .k{font:600 10px var(--display);letter-spacing:.12em;text-transform:uppercase;color:var(--muted)}
.wi-cell .v{font:700 20px var(--display);margin-top:3px;font-variant-numeric:tabular-nums;transition:color .2s}
.wi-cell .d{font:500 11px var(--mono);color:var(--muted);margin-top:2px}
.wi-cell.pending::after{content:"";position:absolute;left:0;right:0;bottom:0;height:2px;background:linear-gradient(90deg,transparent,var(--accent),transparent);animation:wiScan 1s linear infinite}
@keyframes wiScan{from{transform:translateX(-100%)}to{transform:translateX(100%)}}
.wi-cmp{font-size:11.5px;color:var(--muted);margin-top:10px;line-height:1.6}
.wi-cmp b{color:var(--ink)}
.ed-head{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:6px;flex-wrap:wrap}
.ed-pill{font:700 11px var(--display);letter-spacing:.14em;padding:4px 10px;border-radius:99px;border:1px solid var(--border);display:inline-flex;align-items:center;gap:7px}
.ed-pill::before{content:"";width:7px;height:7px;border-radius:50%;background:currentColor;box-shadow:0 0 10px currentColor}
.ed-pill.ok{color:var(--good);border-color:color-mix(in srgb,var(--good) 45%,transparent)}
.ed-pill.watch{color:var(--warn);border-color:color-mix(in srgb,var(--warn) 45%,transparent)}
.ed-pill.bad{color:var(--bad);border-color:color-mix(in srgb,var(--bad) 45%,transparent);animation:edPulse 1.6s ease-in-out infinite}
@keyframes edPulse{0%,100%{box-shadow:0 0 0 0 transparent}50%{box-shadow:0 0 0 5px color-mix(in srgb,var(--bad) 20%,transparent)}}
.ed-svg{width:100%;height:150px;display:block;border-radius:10px;background:linear-gradient(180deg,color-mix(in srgb,var(--surface-2) 70%,transparent),transparent)}
.ed-legend{display:flex;gap:14px;flex-wrap:wrap;font:500 11px var(--mono);color:var(--muted);margin-top:6px}
.ed-legend i{display:inline-block;width:10px;height:3px;vertical-align:middle;margin-right:5px;border-radius:2px}
.gg-wrap{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}
.gg{text-align:center;padding:4px 2px 2px}
.gg svg{width:100%;max-width:132px;height:auto;display:block;margin:0 auto;overflow:visible}
.gg .gv{font:700 15px var(--display);fill:var(--ink)}
.gg .gu{font:500 9px var(--mono);fill:var(--muted)}
.gg .gl{font:600 10px var(--display);letter-spacing:.1em;text-transform:uppercase;color:var(--ink-2);margin-top:2px}
.gg .gs{font:500 10.5px var(--mono);color:var(--muted);margin-top:2px;min-height:14px}
.gg-arc{transition:stroke-dashoffset .8s cubic-bezier(.2,.8,.2,1),stroke .3s}
.gg-verdict{margin-top:10px;font-size:12px;color:var(--ink-2);display:flex;gap:8px;align-items:flex-start}
.gg-verdict .dot{width:8px;height:8px;border-radius:50%;flex:none;margin-top:5px;box-shadow:0 0 8px currentColor;background:currentColor}
@media (max-width:760px){.wi-grid{grid-template-columns:repeat(3,minmax(0,1fr))}.gg-wrap{grid-template-columns:repeat(3,minmax(0,1fr))}.gg svg{max-width:104px}.wi-cell .v{font-size:17px}}
@media (max-width:420px){.wi-grid,.gg-wrap{grid-template-columns:1fr 1fr}}
`;

// ------------------------------------------------------------------ shared math (ports of engine/analytics.py)
function simEval(pnls, plan, lows) {
  let bal = plan.start, peak = bal, mll = bal - plan.mll;
  const lock = plan.lock_above != null ? plan.start + plan.lock_above : Infinity;
  const cons = plan.eval_consistency; let best = 0, active = 0;
  for (let k = 0; k < pnls.length; k++) {
    const dp = pnls[k];
    const lowIntra = bal + (lows ? lows[k] : Math.min(0, dp));
    bal += dp; best = Math.max(best, dp); if (dp !== 0) active++;
    if (lowIntra <= mll || bal <= mll) return { result: 'FAIL', days: k + 1, balance: bal };
    peak = Math.max(peak, bal); mll = Math.min(Math.max(mll, peak - plan.mll), lock);
    const profit = bal - plan.start;
    const consistent = !cons || (profit > 0 && best <= cons * profit);
    if (profit >= plan.target && active >= (plan.min_days_eval || 0) && consistent) return { result: 'PASS', days: k + 1, balance: bal };
  }
  return { result: 'OPEN', days: pnls.length, balance: bal };
}
function rollingEvals(pnls, plan, lows) {
  let pass = 0, fail = 0; const dtp = [];
  for (let s = 0; s < pnls.length; s++) {
    const r = simEval(pnls.slice(s), plan, lows.slice(s));
    if (r.result === 'PASS') { pass++; dtp.push(r.days); } else if (r.result === 'FAIL') fail++;
  }
  const done = pass + fail;
  return { pass, fail, done, rate: done ? pass / done * 100 : null, avgDays: dtp.length ? dtp.reduce((a, b) => a + b, 0) / dtp.length : null };
}

// ------------------------------------------------------------------ (a) what-if sliders
const W = { risk: null, maxT: null, mcSeq: 0, mcTimer: null, mc: null, mcKey: '' };

function whatIfSkeleton() {
  const el = $('#cmdWhatIf'); if (!el) return;
  el.innerHTML = `<div class="card-h"><h3>What-if · risk &amp; frequency</h3><span class="pill" id="wiPill">instant</span></div>
    <div class="wi-row"><span>Risk per trade</span><b id="wiRiskV">—</b><input type="range" id="wiRisk" min="200" max="600" step="25"></div>
    <div class="wi-row"><span>Max trades per day</span><b id="wiMaxV">—</b><input type="range" id="wiMax" min="1" max="4" step="1"></div>
    <div class="wi-grid">
      <div class="wi-cell" id="wiDays"><div class="k">Days to pass</div><div class="v">—</div><div class="d"></div></div>
      <div class="wi-cell" id="wiWorst"><div class="k">Worst day</div><div class="v">—</div><div class="d">vs $1,000 DLL</div></div>
      <div class="wi-cell" id="wiOdds"><div class="k">Pass odds</div><div class="v">—</div><div class="d"></div></div>
    </div>
    <div class="wi-cmp" id="wiCmp"></div>`;
  const sync = () => { W.risk = +$('#wiRisk').value; W.maxT = +$('#wiMax').value; renderWhatIf(S.res); scheduleMC(); };
  $('#wiRisk').oninput = sync; $('#wiMax').oninput = sync;
}

function scenario(res, risk, maxT) {
  const base = Number(res.params?.risk_usd || effective().risk_usd || 350);
  const ratio = risk / base;
  const byDay = {};
  for (const t of res.trades) (byDay[t.day] ||= []).push(t);
  const pnls = [], lows = [], dayTr = [];
  for (const d of res.days) {
    const ts = (byDay[d.date] || []).slice(0, maxT);
    const p = ts.reduce((a, t) => a + t.pnl, 0) * ratio;
    pnls.push(p); lows.push(Math.min(0, (d.low_intraday ?? Math.min(0, d.pnl)) * ratio)); dayTr.push(ts.length);
  }
  const plan = res.plan;
  const ev = simEval(pnls, plan, lows);
  const roll = rollingEvals(pnls, plan, lows);
  const n = dayTr.reduce((a, b) => a + b, 0);
  const net = pnls.reduce((a, b) => a + b, 0);
  const worst = pnls.length ? Math.min(...pnls) : 0;
  const best = pnls.length ? Math.max(...pnls) : 0;
  const dllHits = pnls.filter(p => p <= -(plan.dll || 1000)).length;
  return { ratio, base, pnls, ev, roll, n, net, worst, best, dllHits, weeks: res.days.length / 5 };
}

// LIT (web_next: S.res.model 'lit'): $800 base risk, 1 trade a day; the Monte Carlo resamples the LIT replay days locally
function litRanges(res) {
  const lit = res.model === 'lit', r = $('#wiRisk'), m = $('#wiMax');
  if (!r || r.dataset.mode === (lit ? 'lit' : 'eng')) return;
  r.dataset.mode = lit ? 'lit' : 'eng';
  Object.assign(r, lit ? { min: 400, max: 1200, step: 50 } : { min: 200, max: 600, step: 25 });
  Object.assign(m, lit ? { min: 1, max: 1 } : { min: 1, max: 4 });
  m.disabled = lit;
}
function mcLocal(pnls, lows, plan, runs = 1500, horizon = 60) {
  let seed = 7; const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
  let pass = 0, fail = 0; const dtp = [];
  for (let k = 0; k < runs; k++) {
    const p = [], l = [];
    for (let j = 0; j < horizon; j++) { const i = Math.floor(rnd() * pnls.length); p.push(pnls[i]); l.push(lows[i]); }
    const r = simEval(p, plan, l);
    if (r.result === 'PASS') { pass++; dtp.push(r.days); } else if (r.result === 'FAIL') fail++;
  }
  dtp.sort((a, b) => a - b);
  return { pass_prob: Math.round(pass / runs * 1000) / 10, fail_prob: Math.round(fail / runs * 1000) / 10, median_days_to_pass: dtp.length ? dtp[Math.floor(dtp.length / 2)] : null };
}

function renderWhatIf(res) {
  if (!res || !$('#wiRisk')) return;
  litRanges(res);
  const cur = Number(res.params?.risk_usd || effective().risk_usd || 350);
  if (W.risk == null) { const [lo, hi, st] = res.model === 'lit' ? [400, 1200, 50] : [200, 600, 25]; W.risk = Math.max(lo, Math.min(hi, Math.round(cur / st) * st)); $('#wiRisk').value = W.risk; }
  if (W.maxT == null) { W.maxT = Math.max(1, Math.min(4, Number(res.params?.max_trades_day || effective().max_trades_day || 2))); $('#wiMax').value = W.maxT; }
  $('#wiRiskV').textContent = fmt$(W.risk); $('#wiMaxV').textContent = String(W.maxT);
  const sc = scenario(res, W.risk, W.maxT);
  const base = scenario(res, cur, Number(res.params?.max_trades_day || effective().max_trades_day || 2));
  const set = (id, v, sub, c) => { const e = $(id); e.querySelector('.v').textContent = v; e.querySelector('.v').className = 'v ' + (c || ''); if (sub != null) e.querySelector('.d').innerHTML = sub; };
  const dtp = sc.ev.result === 'PASS' ? sc.ev.days : sc.roll.avgDays;
  set('#wiDays', dtp != null ? `~${Math.round(dtp)}d` : '—', sc.ev.result === 'PASS' ? `from day 1 · ${sc.ev.result}` : sc.ev.result === 'FAIL' ? `<span class="dn">fails day ${sc.ev.days} from day 1</span>` : 'avg of passing starts', sc.ev.result === 'FAIL' ? 'dn' : '');
  set('#wiWorst', fmt$(sc.worst), sc.dllHits ? `<span class="dn">${sc.dllHits} day${sc.dllHits > 1 ? 's' : ''} hit the $1,000 stop</span>` : 'never hit the $1,000 stop', sc.worst <= -800 ? 'dn' : sc.worst <= -500 ? '' : 'up');
  const mc = W.mc && W.mcKey === `${W.risk}|${W.maxT}` ? W.mc : null;
  set('#wiOdds', mc ? mc.pass_prob + '%' : sc.roll.rate != null ? Math.round(sc.roll.rate) + '%' : '—',
    mc ? `Monte Carlo · fail ${mc.fail_prob}% · median ${mc.median_days_to_pass ?? '—'}d` : `rolling starts ${sc.roll.pass}/${sc.roll.done} · MC pending…`,
    (mc ? mc.pass_prob : sc.roll.rate) >= 60 ? 'up' : (mc ? mc.pass_prob : sc.roll.rate) < 35 ? 'dn' : '');
  $('#wiOdds').classList.toggle('pending', !mc);
  $('#wiPill').textContent = mc ? 'Monte Carlo' : 'rescaled locally';
  const dn = sc.net - base.net, dw = sc.worst - base.worst;
  $('#wiCmp').innerHTML = `At <b>${fmt$(W.risk)}</b> risk and <b>${W.maxT}</b> trade${W.maxT > 1 ? 's' : ''}/day the sample nets <b class="${cls(sc.net)}">${fmtS$(sc.net)}</b> over ${sc.n} trades (${fmtN(sc.n / sc.weeks, 1)}/wk), ${dn === 0 && dw === 0 ? 'the current setting' : `<b class="${cls(dn)}">${fmtS$(dn)}</b> vs now with the worst day <b class="${cls(dw)}">${fmtS$(dw)}</b> different`}.
    Best day ${fmt$(sc.best)} is ${sc.net > 0 ? Math.round(sc.best / sc.net * 100) + '% of profit' : 'n/a'}${sc.net > 0 && sc.best / sc.net > 0.5 ? ' <span class="dn">(over the 50% rule)</span>' : ''}. ${res.model === 'lit' ? `Local numbers rescale the LIT replay days (${esc(res.range?.[0] || '')} → ${esc(res.range?.[1] || '')}); the Monte Carlo resamples those days. LIT sizes $800 up to a 20-pt stop and takes 1 trade a day.` : 'Local numbers rescale the backtest days; the Monte Carlo re-runs the model with these settings.'}`;
}

function scheduleMC() {
  clearTimeout(W.mcTimer);
  W.mcTimer = setTimeout(async () => {
    if (!S.res) return;
    const key = `${W.risk}|${W.maxT}`, seq = ++W.mcSeq;
    if (S.res.model === 'lit') {
      const sc = scenario(S.res, W.risk, W.maxT);
      const lows = S.res.days.map(d => Math.min(0, (d.low_intraday ?? Math.min(0, d.pnl)) * sc.ratio));
      W.mc = mcLocal(sc.pnls, lows, S.res.plan); W.mcKey = key;
      renderWhatIf(S.res);
      return;
    }
    try {
      const r = await api('/api/montecarlo', { sym: S.sym, tf: S.tf, plan: S.plan, params: { ...S.params, risk_usd: W.risk, max_trades_day: W.maxT }, runs: 1500, horizon: 60 });
      if (seq !== W.mcSeq) return;
      W.mc = r; W.mcKey = key;
      renderWhatIf(S.res);
    } catch (e) { if (seq === W.mcSeq) { $('#wiOdds .d').innerHTML = `<span class="dn">MC failed: ${esc(e.message)}</span>`; $('#wiOdds').classList.remove('pending'); } }
  }, 400);
}

// ------------------------------------------------------------------ (b) edge-decay monitor
function renderEdge(res) {
  const el = $('#cmdEdge'); if (!el) return;
  const rs = (res?.trades || []).map(t => t.pnl_r);
  const n = rs.length;
  const head = (pill, pc, txt) => `<div class="card-h"><h3>Edge decay · rolling expectancy</h3><span class="ed-pill ${pc}" id="edPill">${pill}</span></div>`;
  if (n < 6) { el.innerHTML = head('NO DATA', '', '') + '<div class="empty">Need at least 6 trades to measure drift.</div>'; return; }
  const Wn = Math.min(20, Math.max(5, Math.floor(n / 2)));
  const mu = rs.reduce((a, b) => a + b, 0) / n;
  const sd = Math.sqrt(rs.reduce((a, b) => a + (b - mu) ** 2, 0) / Math.max(1, n - 1));
  const se = sd / Math.sqrt(Wn);
  const roll = [];
  for (let i = Wn - 1; i < n; i++) { let s = 0; for (let k = i - Wn + 1; k <= i; k++) s += rs[k]; roll.push(s / Wn); }
  const last = roll.at(-1);
  const z = se > 0 ? (last - mu) / se : 0;
  const status = z <= -2 || (mu > 0 && last < 0 && z <= -1) ? ['DEGRADED', 'bad'] : z <= -1 ? ['WATCH', 'watch'] : ['HEALTHY', 'ok'];
  // sparkline
  const Wd = 420, H = 150, px = 10, py = 14;
  const lo = Math.min(mu - 2.4 * se, ...roll), hi = Math.max(mu + 2.4 * se, ...roll), span = hi - lo || 1;
  const X = (i) => px + i / Math.max(1, roll.length - 1) * (Wd - 2 * px), Y = (v) => py + (hi - v) / span * (H - 2 * py);
  const path = roll.map((v, i) => (i ? 'L' : 'M') + X(i).toFixed(1) + ' ' + Y(v).toFixed(1)).join(' ');
  const col = status[1] === 'ok' ? css('--good') : status[1] === 'watch' ? css('--warn') : css('--bad');
  const acc = css('--accent');
  const gid = 'edg' + Math.random().toString(36).slice(2, 7);
  const zero = lo < 0 && hi > 0 ? `<line x1="${px}" x2="${Wd - px}" y1="${Y(0)}" y2="${Y(0)}" stroke="var(--muted)" stroke-dasharray="2 4" opacity=".6"/>` : '';
  const svg = `<svg class="ed-svg" viewBox="0 0 ${Wd} ${H}" preserveAspectRatio="none" aria-label="rolling expectancy">
    <defs><linearGradient id="${gid}" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="${col}" stop-opacity=".35"/><stop offset="1" stop-color="${col}" stop-opacity="0"/></linearGradient></defs>
    <rect x="${px}" y="${Y(mu + 2 * se)}" width="${Wd - 2 * px}" height="${Math.max(1, Y(mu - 2 * se) - Y(mu + 2 * se))}" fill="${acc}" opacity=".10"/>
    <rect x="${px}" y="${Y(mu + se)}" width="${Wd - 2 * px}" height="${Math.max(1, Y(mu - se) - Y(mu + se))}" fill="${acc}" opacity=".10"/>
    <line x1="${px}" x2="${Wd - px}" y1="${Y(mu)}" y2="${Y(mu)}" stroke="${acc}" stroke-dasharray="4 4" opacity=".9"/>${zero}
    <path d="${path} L${X(roll.length - 1)} ${H - py} L${X(0)} ${H - py} Z" fill="url(#${gid})"/>
    <path d="${path}" fill="none" stroke="${col}" stroke-width="2" vector-effect="non-scaling-stroke" stroke-linejoin="round"/>
    <circle cx="${X(roll.length - 1)}" cy="${Y(last)}" r="4" fill="${col}"><animate attributeName="r" values="3.5;5.5;3.5" dur="1.8s" repeatCount="indefinite"/></circle>
    <text x="${Wd - px - 2}" y="${Y(mu) - 4}" text-anchor="end" font-size="9" font-family="JetBrains Mono" fill="${acc}">full-sample ${fmtR(mu)}</text></svg>`;
  const plain = status[0] === 'HEALTHY'
    ? `The last ${Wn} trades average <b>${fmtR(last)}</b>, within noise of the full-sample <b>${fmtR(mu)}</b> (${z >= 0 ? '+' : ''}${z.toFixed(1)}σ). The edge is behaving like its history.`
    : status[0] === 'WATCH'
      ? `The last ${Wn} trades average <b>${fmtR(last)}</b>, ${Math.abs(z).toFixed(1)}σ below the full-sample <b>${fmtR(mu)}</b>. Not yet significant, but check the regime and the recent exit-reason mix before sizing up.`
      : `The last ${Wn} trades average <b>${fmtR(last)}</b>, ${Math.abs(z).toFixed(1)}σ below the full-sample <b>${fmtR(mu)}</b>. That is outside the 2σ band: cut size or stand aside until expectancy returns to the band.`;
  el.innerHTML = head(status[0], status[1]) + svg +
    `<div class="ed-legend"><span><i style="background:${col}"></i>rolling ${Wn}-trade mean</span><span><i style="background:${acc}"></i>full sample ± 1σ / 2σ</span><span>n = ${n}</span></div>
    <div class="note">${plain}</div>`;
}

// ------------------------------------------------------------------ (c) MFFU rules gauges
function gauge(id, frac, color, value, unit, label, sub) {
  const r = 44, cx = 60, cy = 58, a0 = 135, a1 = 405;
  const pol = (a) => [cx + r * Math.cos(a * Math.PI / 180), cy + r * Math.sin(a * Math.PI / 180)];
  const [sx, sy] = pol(a0), [ex, ey] = pol(a1);
  const len = 2 * Math.PI * r * (a1 - a0) / 360;
  const f = Math.max(0, Math.min(1, frac));
  const track = `M${sx.toFixed(1)} ${sy.toFixed(1)} A${r} ${r} 0 1 1 ${ex.toFixed(1)} ${ey.toFixed(1)}`;
  return `<div class="gg" id="${id}"><svg viewBox="0 0 120 108">
      <path d="${track}" fill="none" stroke="var(--surface-3)" stroke-width="9" stroke-linecap="round"/>
      <path class="gg-arc" d="${track}" fill="none" stroke="${color}" stroke-width="9" stroke-linecap="round" stroke-dasharray="${len.toFixed(1)}" stroke-dashoffset="${(len * (1 - f)).toFixed(1)}" style="filter:drop-shadow(0 0 6px ${color})"/>
      <text x="${cx}" y="${cy + 2}" text-anchor="middle" class="gv">${esc(value)}</text>
      <text x="${cx}" y="${cy + 15}" text-anchor="middle" class="gu">${esc(unit)}</text></svg>
    <div class="gl">${label}</div><div class="gs">${sub}</div></div>`;
}

function renderRules(res) {
  const el = $('#cmdRules'); if (!el) return;
  if (!res?.days?.length) { el.innerHTML = '<div class="card-h"><h3>MFFU rules · live gauges</h3></div><div class="empty">Run a backtest.</div>'; return; }
  const plan = res.plan || {}, s = res.stats, last = res.days.at(-1);
  const dll = plan.dll || 1000;
  const good = css('--good'), warn = css('--warn'), bad = css('--bad');
  const grade = (x, a, b) => x < a ? good : x < b ? warn : bad;
  // 1 · today's P&L vs the $1,000 daily soft stop (negative days consume the gauge)
  const pnl = last.pnl || 0, used = pnl < 0 ? -pnl / dll : 0;
  const g1 = gauge('ggDay', pnl >= 0 ? Math.min(1, pnl / dll) : used, pnl >= 0 ? good : grade(used, .5, .8), fmtS$(pnl), pnl < 0 ? `${Math.round(used * 100)}% of $${dll.toLocaleString()} stop` : 'last session', 'Daily stop', pnl < 0 ? `${fmt$(dll + pnl)} of room left` : `${last.date.slice(5)} · ${last.trades || 0} trade${last.trades === 1 ? '' : 's'}`);
  // 2 · balance distance to the trailing max-loss line
  const cushion = (last.balance ?? plan.start) - (last.mll ?? plan.start - plan.mll);
  const cfrac = cushion / (plan.mll || 2000);
  const g2 = gauge('ggMll', cfrac, grade(1 - cfrac, .4, .7), fmt$(cushion), `above MLL ${fmtN(last.mll, 0)}`, 'MLL cushion', `balance ${fmtN(last.balance, 0)}${last.mll >= plan.start + (plan.lock_above ?? 1e9) ? ' · locked' : ''}`);
  // 3 · 50% consistency rule
  const pct = s.best_day_pct;
  const g3 = gauge('ggCons', pct != null ? pct / 100 : 0, pct == null ? warn : grade(pct, 40, 50), pct != null ? pct + '%' : '—', 'best day / profit', 'Consistency', pct != null ? `best ${fmt$(s.best_day)} of ${fmt$(s.net)}` : 'no profit yet');
  const issues = [];
  if (used >= .8) issues.push([bad, `Today's loss is ${Math.round(used * 100)}% of the daily stop: no new entries.`]);
  if (cfrac < .3) issues.push([bad, `Only ${fmt$(cushion)} above the max-loss line: one bad day ends the eval.`]);
  else if (cfrac < .6) issues.push([warn, res.model === 'lit' ? `${fmt$(cushion)} of cushion: about ${Math.max(1, Math.floor(cushion / 800))} full-size LIT stop-out${cushion >= 1600 ? 's' : ''} from the line (Modules → Risk & Sizing: safe_eval caps the size).` : `${fmt$(cushion)} of cushion: drawdown-aware sizing is shrinking contracts.`]);
  if (pct != null && pct > 50) issues.push([warn, `Best day is ${pct}% of total profit: a payout would be refused until quieter days catch up.`]);
  const verdict = issues.length ? issues.map(([c, t]) => `<div class="gg-verdict"><span class="dot" style="color:${c}"></span><span>${t}</span></div>`).join('')
    : `<div class="gg-verdict"><span class="dot" style="color:${good}"></span><span>All three MFFU constraints are green on the last session.</span></div>`;
  el.innerHTML = `<div class="card-h"><h3>MFFU rules · live gauges</h3><span class="muted small">last session · ${esc(plan.name || 'Builder 50K')}</span></div><div class="gg-wrap">${g1}${g2}${g3}</div>${verdict}`;
}

// ------------------------------------------------------------------ init
let lastRes = null;
export function initCommandExtras() {
  if (!$('#ceStyle')) { const st = document.createElement('style'); st.id = 'ceStyle'; st.textContent = CSS; document.head.appendChild(st); }
  whatIfSkeleton();
  on((res) => {
    if (!res) return;
    if (res !== lastRes) { W.mc = null; W.mcKey = ''; W.risk = null; W.maxT = null; lastRes = res; }
    renderWhatIf(res); renderEdge(res); renderRules(res);
    if (!W.mc) scheduleMC();
  });
}
