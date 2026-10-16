import { $, $$, esc, fmtN, fmt$, fmtS$, cls, store, css, api, busy, toast } from './util.js';
import { S, on, cj, baseOpts } from './state.js';

export function init() {
  on(render);
  $('#planSel').onchange = (e) => { S.plan = e.target.value; store.set('plan', S.plan); window.LE.run(); };
  $('#evalStart').onchange = () => renderEval();
  $('#mcRun').onclick = runMC;
}
export function show() { }

export function simulateEval(dayPnls, lows, plan) {
  let bal = plan.start, peak = bal, mll = bal - plan.mll, best = 0, active = 0;
  const lock = plan.lock_above == null ? Infinity : plan.start + plan.lock_above;
  const path = [];
  for (let k = 0; k < dayPnls.length; k++) {
    const lowIntra = bal + (lows ? lows[k] : Math.min(0, dayPnls[k]));
    bal += dayPnls[k];
    best = Math.max(best, dayPnls[k]); if (dayPnls[k]) active++;
    if (lowIntra <= mll || bal <= mll) { path.push({ bal, mll }); return { result: 'FAIL', days: k + 1, path }; }
    peak = Math.max(peak, bal);
    mll = Math.min(Math.max(mll, peak - plan.mll), lock);
    path.push({ bal, mll });
    const profit = bal - plan.start;
    const ok = !plan.eval_consistency || (profit > 0 && best <= plan.eval_consistency * profit);
    if (profit >= plan.target && active >= (plan.min_days_eval || 1) && ok) return { result: 'PASS', days: k + 1, path };
  }
  return { result: 'OPEN', days: dayPnls.length, path };
}

function render(res) {
  if (!res) return;
  const plans = S.meta.plans;
  $('#planSel').innerHTML = Object.entries(plans).map(([k, p]) => `<option value="${k}" ${k === S.plan ? 'selected' : ''}>${esc(p.name)}</option>`).join('');
  const p = res.plan;
  $('#railPlan').textContent = p.name;
  $('#propRules').innerHTML = `<table class="tbl">
    ${[['Profit target', fmt$(p.target)], ['Max loss (EOD trailing)', fmt$(p.mll)], ['MLL locks at', p.lock_above == null ? 'keeps trailing' : fmt$(p.start + p.lock_above)], ['Daily loss limit', p.dll ? fmt$(p.dll) + ' soft pause' : 'none'],
      ['Bots / automation', p.automation || '—'],
      ['Max size', `${p.max_minis} minis / ${p.max_minis * 10} micros`], ['Eval consistency', p.eval_consistency ? `best day ≤ ${Math.round(p.eval_consistency * 100)}%` : 'none'], ['Funded consistency', `best day ≤ ${p.consistency * 100}% of cycle`],
      ['Payout buffer', fmt$(p.buffer)], ['Payout min / max', `${fmt$(p.payout_min)} / ${fmt$(p.payout_max)}`], ['Profit split', `${p.split * 100}%`], ['Positions', 'flat before session close']]
      .map(([k, v]) => `<tr><td class="muted">${k}</td><td class="mono" style="text-align:right">${v}</td></tr>`).join('')}</table>
    <div class="muted small" style="margin-top:8px">From MFFU's help center (Oct 2026). Rules change, so confirm on myfundedfutures.com.</div>`;
  $('#evalStart').innerHTML = res.days.map((d, i) => `<option value="${i}">${d.date}</option>`).join('');
  renderEval();
  renderRolling(res);
  renderSizer();
  renderRuin(res);
  renderPayout(res);
  $('#mcStats').innerHTML = '';
  runMC();
  loadFirms();
}

async function loadFirms() {
  let f;
  try { f = await api('/api/firms', { sym: S.sym, tf: S.tf, params: S.params }); } catch (e) { return; }
  const pct = (v) => v == null ? '—' : `${fmtN(v, 0)}%`;
  const best = [...f.rows].filter(r => r.bot_ok).sort((a, b) => (b.mc_pass - a.mc_pass) || ((a.mc_days ?? 99) - (b.mc_days ?? 99)))[0];
  $('#firmTable').innerHTML = `<tr><th>Firm · 50K plan</th><th>Bots?</th><th>Target / max loss</th><th>Lock</th><th>Eval consistency</th><th>Min days</th><th>Max size</th><th>Split</th>
      <th>Pass (rolling)</th><th>Avg days</th><th>Pass (Monte Carlo)</th><th>Funded payout est.</th><th>Price</th></tr>` +
    f.rows.map(r => `<tr${best && r.key === best.key ? ' style="background:color-mix(in srgb,var(--accent) 10%,transparent)"' : ''}>
      <td><b>${esc(r.name)}</b>${best && r.key === best.key ? ' <span class="tag-chip" style="background:var(--accent);color:var(--accent-ink)">best fit</span>' : ''}</td>
      <td class="${r.bot_ok ? 'firm-ok' : 'firm-no'}" title="${esc(r.automation)}">${r.bot_ok ? '✓' : '✗ banned'}</td>
      <td class="mono">${fmt$(r.target)} / ${fmt$(r.mll)}</td><td class="mono">${r.lock == null ? 'trails' : fmt$(r.lock + 50000)}</td>
      <td class="mono">${r.eval_consistency ? Math.round(r.eval_consistency * 100) + '%' : 'none'}</td><td class="mono">${r.min_days ?? '—'}</td>
      <td class="mono">${r.max_minis} NQ</td><td class="mono">${Math.round(r.split * 100)}%</td>
      <td class="mono">${pct(r.rolling_pass)}</td><td class="mono">${r.avg_days ?? '—'}</td>
      <td class="mono ${r.mc_pass >= 90 ? 'up' : r.mc_pass < 60 ? 'dn' : ''}">${pct(r.mc_pass)}</td><td class="mono">${fmt$(r.funded_paid)}</td>
      <td class="small">${esc(r.price || '—')}</td></tr>`).join('');
  $('#firmNote').innerHTML = `${esc(f.note)} <b>Apex bans automation</b>, so the bot can't run there. Topstep allows bots only through the TopstepX API ($29/mo) on your own device.
    Pass odds use this backtest's days, so they share its regime caveat. Hover ✓/✗ for each firm's automation policy.`;
}

function renderEval() {
  const res = S.res; if (!res) return;
  const s = +$('#evalStart').value || 0;
  const days = res.days.slice(s);
  const ev = simulateEval(days.map(d => d.pnl), days.map(d => d.low_intraday), res.plan);
  const labels = days.slice(0, ev.path.length).map(d => d.date.slice(5));
  cj('propEval', {
    type: 'line',
    data: { labels: ['start', ...labels], datasets: [
      { label: 'Balance', data: [res.plan.start, ...ev.path.map(x => x.bal)], borderColor: css('--accent'), borderWidth: 2.2, pointRadius: 2, tension: .1 },
      { label: 'Trailing MLL', data: [res.plan.start - res.plan.mll, ...ev.path.map(x => x.mll)], borderColor: css('--bad'), borderDash: [5, 4], borderWidth: 1.6, pointRadius: 0, stepped: true },
      { label: 'Target', data: [0, ...ev.path].map(() => res.plan.start + res.plan.target), borderColor: css('--good'), borderDash: [2, 3], borderWidth: 1.4, pointRadius: 0 },
    ] },
    options: baseOpts({ plugins: { legend: { display: true, position: 'top', align: 'end' }, tooltip: { callbacks: { label: c => `${c.dataset.label}: ${fmt$(c.parsed.y)}` } } }, scales: { x: { grid: { display: false } }, y: { ticks: { callback: v => '$' + (v / 1000).toFixed(1) + 'k' } } } }),
  });
  const col = ev.result === 'PASS' ? 'up' : ev.result === 'FAIL' ? 'dn' : '';
  $('#propEvalNote').innerHTML = `Started <b>${days[0].date}</b> → <b class="${col}">${ev.result}</b> after <b>${ev.days}</b> trading days.
    Lowest cushion above MLL: <b>${fmt$(Math.min(...ev.path.map(x => x.bal - x.mll)))}</b>. The MLL ratchets up on new end-of-day highs and never moves down.`;
}

function renderRolling(res) {
  const r = res.rolling;
  const cells = r.runs.map(x => {
    const bg = x.result === 'PASS' ? 'var(--good)' : x.result === 'FAIL' ? 'var(--bad)' : 'var(--axis)';
    return `<div style="background:${bg}" title="start ${x.start}: ${x.result} in ${x.days} days">${x.result === 'OPEN' ? '…' : x.days}</div>`;
  }).join('');
  $('#propRolling').innerHTML = `<div class="grid kpis small">
      <div class="kpi"><div class="k">Pass rate</div><div class="v ${r.pass_rate >= 50 ? 'up' : 'dn'}">${r.pass_rate ?? '—'}%</div></div>
      <div class="kpi"><div class="k">Passed / failed</div><div class="v">${r.pass} / ${r.fail}</div></div>
      <div class="kpi"><div class="k">Avg days to pass</div><div class="v">${r.avg_days_to_pass ?? '—'}</div></div>
      <div class="kpi"><div class="k">Still open</div><div class="v">${r.open}</div></div></div>
    <div class="rgrid">${cells}</div>
    <div class="muted small" style="margin-top:8px">One cell per start date (oldest → newest); the number is trading days to the outcome. Green = passed, red = failed, grey = still running at data end. Overlapping windows, so the starts are not independent samples.</div>`;
}

async function runMC() {
  if (!S.res) return;
  busy(true);
  try {
    const r = await api('/api/montecarlo', { sym: S.sym, tf: S.tf, params: S.params, plan: S.plan, runs: +$('#mcRuns').value || 2000, horizon: +$('#mcDays').value || 60 });
    const L = Array.from({ length: r.horizon }, (_, i) => i + 1);
    const b = r.bands;
    cj('mcFan', {
      type: 'line',
      data: { labels: L, datasets: [
        { label: 'p95', data: b['95'], borderColor: 'transparent', pointRadius: 0, fill: false },
        { label: 'p5–p95', data: b['5'], borderColor: 'transparent', backgroundColor: 'rgba(57,135,229,.12)', pointRadius: 0, fill: '-1' },
        { label: 'p75', data: b['75'], borderColor: 'transparent', pointRadius: 0, fill: false },
        { label: 'p25–p75', data: b['25'], borderColor: 'transparent', backgroundColor: 'rgba(57,135,229,.24)', pointRadius: 0, fill: '-1' },
        { label: 'Median', data: b['50'], borderColor: css('--accent'), borderWidth: 2, pointRadius: 0 },
        { label: 'Target +$3k', data: L.map(() => S.res.plan.target), borderColor: css('--good'), borderDash: [3, 3], borderWidth: 1.2, pointRadius: 0 },
        { label: 'Initial MLL -$2k', data: L.map(() => -S.res.plan.mll), borderColor: css('--bad'), borderDash: [3, 3], borderWidth: 1.2, pointRadius: 0 },
      ] },
      options: baseOpts({ plugins: { legend: { display: true, position: 'top', align: 'end', labels: { filter: i => !['p95', 'p75'].includes(i.text) } }, tooltip: { callbacks: { label: c => `${c.dataset.label}: ${fmt$(c.parsed.y)}` } } },
        scales: { x: { title: { display: true, text: 'trading days' }, grid: { display: false } }, y: { ticks: { callback: v => '$' + v } } } }),
    });
    const f = r.funded;
    $('#mcStats').innerHTML = [
      ['Eval pass', r.pass_prob + '%', 'up'], ['Eval fail', r.fail_prob + '%', 'dn'], ['Median days to pass', r.median_days_to_pass ?? '—'], ['p90 days to pass', r.p90_days_to_pass ?? '—'],
      ['Funded: ≥1 payout', f.p_at_least_one + '%'], ['Funded: all 5 payouts', f.p_all_five + '%'], ['Avg paid to you', fmt$(f.avg_paid_to_trader), 'up'], ['Funded blow rate', f.blow_rate + '%'],
    ].map(([k, v, c]) => `<div class="kpi"><div class="k">${k}</div><div class="v ${c || ''}">${v}</div></div>`).join('') +
      `<div class="note" style="grid-column:1/-1">Resamples the ${S.res.days.length} backtested sessions with replacement. It assumes the future looks like this sample, which came from one market regime, so read these odds as an <b>optimistic upper bound</b>. Funded stats model the sim-funded stage (buffer, 50% consistency, $2k cap, 5 payouts).</div>`;
  } catch (e) { toast('Monte Carlo failed: ' + e.message); }
  busy(false);
}

function renderSizer() {
  const spec = S.meta.instruments[S.sym];
  const el = $('#sizer');
  const st = store.get('sizer', { stop: 25, risk: 350 });
  el.innerHTML = `<div class="form-grid">
    <span>Stop (points)</span><input class="inp" id="szStop" type="number" value="${st.stop}" step="0.25">
    <span>Risk ($)</span><input class="inp" id="szRisk" type="number" value="${st.risk}" step="25"></div><div id="szOut" style="margin-top:12px"></div>`;
  const calc = () => {
    const stop = +$('#szStop').value, risk = +$('#szRisk').value;
    store.set('sizer', { stop, risk });
    const micros = Math.min(40, Math.floor(risk / (stop * spec.micro_pv)));
    const minis = Math.min(4, Math.floor(risk / (stop * spec.mini_pv)));
    const pctMll = risk / S.res.plan.mll * 100;
    $('#szOut').innerHTML = `<div class="state-grid">
      <div class="st"><div class="k">M${S.sym} contracts</div><div class="v">${micros}</div></div>
      <div class="st"><div class="k">${S.sym} contracts</div><div class="v">${minis}</div></div>
      <div class="st"><div class="k">Actual risk (micros)</div><div class="v">${fmt$(micros * stop * spec.micro_pv)}</div></div>
      <div class="st"><div class="k">% of MLL</div><div class="v ${pctMll > 25 ? 'dn' : 'up'}">${fmtN(pctMll, 1)}%</div></div>
      <div class="st"><div class="k">Losses to breach</div><div class="v">${Math.floor(S.res.plan.mll / Math.max(1, micros * stop * spec.micro_pv))}</div></div>
      <div class="st"><div class="k">Wins (2.5R) to target</div><div class="v">${Math.ceil(S.res.plan.target / Math.max(1, 2.5 * micros * stop * spec.micro_pv))}</div></div></div>
      <div class="note">${pctMll > 25 ? '⚠ Over 25% of the max loss per trade. A normal losing streak can end the account.' : '✓ Inside the 10–25% of MLL per-trade band, which survives normal losing streaks.'}</div>`;
  };
  el.oninput = calc; calc();
}

function renderRuin(res) {
  const s = res.stats;
  const wins = res.trades.filter(t => t.pnl > 0);
  const avgWinR = wins.length ? wins.reduce((a, t) => a + t.pnl_r, 0) / wins.length : 2;
  const el = $('#ruin');
  el.innerHTML = `<div class="form-grid">
    <span>Win rate %</span><input class="inp" id="rrWr" type="number" value="${s.win_rate}">
    <span>Avg win (R)</span><input class="inp" id="rrW" type="number" value="${avgWinR.toFixed(2)}" step="0.1">
    <span>Risk / trade $</span><input class="inp" id="rrRisk" type="number" value="${res.params.risk_usd}" step="25">
    <span>Trades</span><input class="inp" id="rrN" type="number" value="120"></div><div id="rrOut" style="margin-top:12px"></div>`;
  const calc = () => {
    const wr = +$('#rrWr').value / 100, w = +$('#rrW').value, risk = +$('#rrRisk').value, N = +$('#rrN').value;
    const plan = res.plan;
    let pass = 0, fail = 0;
    const R = 4000;
    let seed = 1;
    const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
    for (let r = 0; r < R; r++) {
      let bal = 0, peak = 0, mll = -plan.mll;
      for (let k = 0; k < N; k++) {
        bal += rnd() < wr ? w * risk : -risk;
        if (bal <= mll) { fail++; break; }
        peak = Math.max(peak, bal); mll = Math.min(Math.max(mll, peak - plan.mll), plan.lock_above ?? Infinity);
        if (bal >= plan.target) { pass++; break; }
      }
    }
    const exp = wr * w - (1 - wr);
    $('#rrOut').innerHTML = `<div class="state-grid">
      <div class="st"><div class="k">Expectancy</div><div class="v ${cls(exp)}">${exp >= 0 ? '+' : ''}${exp.toFixed(2)}R</div></div>
      <div class="st"><div class="k">Breakeven win rate</div><div class="v">${(100 / (1 + w)).toFixed(1)}%</div></div>
      <div class="st"><div class="k">Hit target first</div><div class="v up">${(pass / R * 100).toFixed(1)}%</div></div>
      <div class="st"><div class="k">Breach first</div><div class="v dn">${(fail / R * 100).toFixed(1)}%</div></div></div>
      <div class="note">Trade-level simulation of the trailing max loss. Change risk per trade to see how sizing moves your odds.</div>`;
  };
  el.oninput = calc; calc();
}

function renderPayout(res) {
  const p = res.plan;
  const days = res.days.filter(d => d.trades);
  const profit = res.days.reduce((a, d) => a + d.pnl, 0);
  const best = Math.max(0, ...res.days.map(d => d.pnl));
  const qual = res.days.filter(d => d.pnl > 0).length;
  const pct = profit > 0 ? best / profit * 100 : null;
  const ok = (c) => c ? '<span class="up">✔</span>' : '<span class="dn">✖</span>';
  $('#payoutCheck').innerHTML = `<table class="tbl">
    <tr><td>Period profit</td><td class="mono ${cls(profit)}" style="text-align:right">${fmtS$(profit)}</td><td>${ok(profit > p.buffer + p.payout_min)}</td></tr>
    <tr><td>Above buffer (${fmt$(p.buffer)}) + $500</td><td class="mono" style="text-align:right">${fmt$(Math.max(0, profit - p.buffer))}</td><td>${ok(profit - p.buffer >= p.payout_min)}</td></tr>
    <tr><td>Best day share (≤ ${p.consistency * 100}%)</td><td class="mono" style="text-align:right">${pct != null ? pct.toFixed(1) + '%' : '—'}</td><td>${ok(pct != null && pct <= p.consistency * 100)}</td></tr>
    <tr><td>Winning (qualifying) days</td><td class="mono" style="text-align:right">${qual}</td><td>${ok(qual >= p.payout_min_days)}</td></tr>
    <tr><td>Active trading days</td><td class="mono" style="text-align:right">${days.length}</td><td>${ok(true)}</td></tr>
    <tr><td>First payout estimate (80%)</td><td class="mono up" style="text-align:right">${fmt$(Math.min(p.payout_max, Math.max(0, profit - p.buffer)) * p.split)}</td><td></td></tr></table>
    <div class="muted small" style="margin-top:8px">Treats the whole backtest as one sim-funded cycle. "Stop after a winner" keeps single days from dominating, which helps the 50% rule.</div>`;
}
