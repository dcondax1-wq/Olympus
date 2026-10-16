import { $, esc, fmtN, fmtS$, fmtR, cls, etStr, css, api, busy, toast } from './util.js';
import { S, on, cj, baseOpts, effective } from './state.js';

export const FEATURE_LABELS = {
  htf_trend: ['1H structure aligned', 'w_htf'], protected: ['Protected H/L intact', 'w_protected'], lrl: ['Low-resistance path (LRL)', 'w_lrl'],
  hrl: ['High-resistance path (HRL)', 'w_lrl'], amt: ['AMT location (POC / value)', 'w_amt'], smt: ['SMT divergence (NQ↔ES)', 'w_smt'],
  quality: ['Quality pool swept', 'w_quality'], m15_trend: ['15m structure aligned', 'w_m15'], b_1D: ['1D FVG order flow', 'w_mtf'],
  b_4H: ['4H FVG order flow', 'w_mtf'], b_1H: ['1H FVG order flow', 'w_mtf'], b_15m: ['15m FVG order flow', 'w_mtf'],
  pd: ['Premium / discount (1H range)', 'w_pd'], midnight: ['Midnight open side', 'w_midnight'], keylevel: ['HTF key level tapped', 'w_keylevel'],
  dol_align: ['Toward nearest major liquidity (HTF DOL)', 'w_dol'], tgt_major: ['Target is a major pool', null],
  dol_room3: ['≥3R of room to major liquidity', null],
  shallow_raid: ['Shallow raid (≤0.5 ATR past pool)', 'w_shallow'], deep_raid: ['Deep raid (≥1.5 ATR past pool)', null],
  disp_strong: ['Strong displacement (body ≥ 1 ATR)', 'w_disp'], fast_reclaim: ['Fast reclaim (≤3 bars)', 'w_fast'],
  first_hour: ['First hour 09:30–10:30', 'w_first'], multi_sweep: ['Stacked liquidity (2+ pools)', 'w_multi'],
  major_swept: ['Major pool raided', 'w_major'], vol_climax: ['Volume climax on raid', 'w_vol'], vwap_disc: ['Session VWAP side', 'w_vwap'],
  qt_q2_sweep: ['QT: sweep in a 90-min Q2 (manipulation)', null], qt_q2q3: ['QT: Q2 sweep → Q3 entry', null],
  qt_90_open: ['QT: raid beyond the 90-min true open', null], qt_week_open: ['QT: raid beyond weekly true open (Tue)', null],
  amd_day_open: ['AMD / PO3: raid beyond the 18:00 daily open', null], gex_high: ['High dealer gamma (top 25%, prior day)', null],
  gex_low: ['Low dealer gamma (bottom 25%, prior day)', null],
  trig_15m: ['15m IFVG trigger', null], cisd: ['CISD trigger', null], pm: ['PM session', null],
};
let split = null;

export function init() {
  on(render);
  $('#confSplit').onchange = (e) => { split = e.target.value; render(S.res); };
  $('#discFilter').onchange = renderDisc;
  $('#discRun').onclick = async () => {
    await api('/api/discovery/run', {}); toast('Discovery re-scan started: about 2 minutes'); pollDisc();
  };
  injectRegCss();
  $('#cregRun').onclick = runCycle;
}
export function show() { loadDisc(); loadReg(); }

// ---------- confluence registry · learning loop (engine/confluence_search.py, futures only)
const ST = ['ACTIVE', 'PROBATION', 'CANDIDATE', 'RETIRED'];
const ST_NOTE = {
  ACTIVE: 'in the grade / gate (or passed every rule and waits for the lead to apply it)',
  PROBATION: 'helped on some rules, failed others: re-tested every cycle',
  CANDIDATE: 'not enough consistent evidence yet: waiting for more futures history',
  RETIRED: 'did not help this strategy: still re-scanned every cycle and revived if the evidence turns',
};
let reg = null, regTab = 'ACTIVE', regTimer = null, regRunning = false;

function injectRegCss() {
  if (document.getElementById('creg-css')) return;
  const s = document.createElement('style');
  s.id = 'creg-css';
  s.textContent = `
  .creg-wrap { overflow-x: auto; }
  .creg-head, .creg-row { display: grid; grid-template-columns: minmax(190px, 1.25fr) repeat(var(--nf, 6), 44px) minmax(260px, 2fr) 158px;
    gap: 8px; align-items: center; min-width: 900px; }
  .creg-head { font: 700 10.5px var(--display); text-transform: uppercase; letter-spacing: .12em; color: var(--muted); padding: 0 10px 6px; border-bottom: 1px solid var(--grid); }
  .creg-head .conf { color: var(--accent); }
  .creg-row { padding: 9px 10px; border-bottom: 1px solid var(--grid); font-size: 12.5px; position: relative; }
  .creg-row::before { content: ""; position: absolute; left: 0; top: 7px; bottom: 7px; width: 3px; border-radius: 3px; background: var(--grid); }
  .creg-row.active::before { background: var(--good); } .creg-row.probation::before { background: var(--warn); }
  .creg-row.retired::before { background: var(--bad); opacity: .6; } .creg-row.candidate::before { background: var(--accent); opacity: .5; }
  .creg-row:hover { background: color-mix(in srgb, var(--accent) 5%, transparent); }
  .creg-row .nm b { font-weight: 600; } .creg-row .why { color: var(--ink-2); line-height: 1.35; }
  .creg-row .ev { display: flex; flex-direction: column; gap: 3px; }
  .creg-row .ev .dbar { height: 8px; } .creg-row .ev .dbar.tk { height: 5px; opacity: .75; }
  .creg-row .ev .dbar.conf { outline: 1px solid color-mix(in srgb, var(--accent) 45%, transparent); }
  .creg-row .tst { font: 500 11px var(--mono); line-height: 1.45; }
  .creg-prog { height: 6px; border-radius: 3px; background: var(--surface-2); overflow: hidden; margin: 4px 0 8px; }
  .creg-prog > span { display: block; height: 100%; background: var(--accent); transition: width .4s; }
  .creg-sum { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 8px; margin-bottom: 10px; }
  .creg-rec { border: 1px solid var(--border); border-left: 4px solid var(--good); border-radius: 10px; padding: 10px 12px; background: var(--surface-2); margin-bottom: 8px; font-size: 12.5px; }
  .creg-rec.none { border-left-color: var(--muted); }
  .creg-rec code { font: 500 11.5px var(--mono); background: var(--surface); padding: 1px 5px; border-radius: 4px; word-break: break-all; }
  .creg-rec table { margin-top: 8px; }
  .creg-chip { display: inline-block; font: 600 10px var(--sans); padding: 1px 6px; border-radius: 5px; background: var(--surface-3); color: var(--ink-2); margin: 2px 4px 0 0; }
  .creg-chip.hook { color: var(--warn); } .creg-chip.rec { color: var(--good-ink); }
  @media (max-width: 760px) { .creg-head, .creg-row { min-width: 820px; } }`;
  document.head.appendChild(s);
}

async function loadReg() {
  try { reg = await api('/api/confluence/registry'); } catch (e) { reg = { data: null, error: e.message }; }
  regRunning = !!reg.running;
  renderReg();
  if (regRunning) pollReg();
}
async function runCycle() {
  try {
    const r = await api('/api/confluence/run', {});
    toast(r.already ? 'A learning cycle is already running' : 'Learning cycle started: usually under a minute');
    regRunning = true; renderProg({ running: true, step: 0, steps: 6, msg: 'starting' }); pollReg();
  } catch (e) { toast(e.message); }
}
function pollReg() {
  clearTimeout(regTimer);
  regTimer = setTimeout(async () => {
    let st = null;
    try { st = await api('/api/confluence/status'); } catch (e) { st = null; }
    if (st) renderProg(st);
    if (st && st.running) { pollReg(); return; }
    regRunning = false;
    if (st && st.rc && st.rc !== 0) toast('Learning cycle failed: see the server log');
    else if (st && st.rc === 0) toast('Learning cycle finished');
    await loadReg();
  }, 2500);
}
function renderProg(st) {
  const box = $('#cregProg'), btn = $('#cregRun');
  if (!box) return;
  btn.disabled = !!st?.running;
  btn.textContent = st?.running ? 'Running…' : 'Run learning cycle';
  if (!st?.running) { box.innerHTML = ''; return; }
  const pct = Math.round(((st.step || 0) / (st.steps || 6)) * 100);
  box.innerHTML = `<div class="muted small">Step ${st.step || 0} of ${st.steps || 6}: ${esc(st.msg || '')}${st.elapsed_s != null ? ` · ${Math.round(st.elapsed_s)}s` : ''}</div>
    <div class="creg-prog"><span style="width:${Math.max(4, pct)}%"></span></div>`;
}

const money = (v) => v == null ? '—' : fmtS$(v);
function lbar(p, max, cls2 = '') {
  if (!p || p.lift == null) return `<div class="dbar na ${cls2}" title="${esc(p?.slice || '')}: not enough samples (${p?.n_on ?? 0} with / ${p?.n_off ?? 0} without)"><span></span></div>`;
  const w = Math.min(50, Math.abs(p.lift) / max * 50);
  return `<div class="dbar ${cls2}" title="${esc(p.slice)}${p.role === 'confirm' ? ' (out-of-sample)' : ''}: ${fmtR(p.lift)} lift · ${p.n_on} with / ${p.n_off} without">
    <span class="${p.lift > 0 ? 'pos' : 'neg'}" style="${p.lift > 0 ? 'left:50%' : `left:${50 - w}%`};width:${w}%"></span></div>`;
}
function bestTest(it) {
  const ts = it.tests || [];
  if (!ts.length) return null;
  const rank = { pass: 2, partial: 1, fail: 0 };
  return ts.slice().sort((a, b) => (rank[b.result.verdict] - rank[a.result.verdict]) || (b.result.d_nq - a.result.d_nq))[0];
}

function renderReg() {
  const meta = $('#cregMeta'), sum = $('#cregSummary'), board = $('#cregBoard');
  if (!sum) return;
  renderProg({ running: regRunning, step: 0, steps: 6, msg: 'running' });
  const d = reg?.data;
  if (!d || !d.items) {
    sum.innerHTML = `<div class="empty">${reg?.error ? esc(reg.error) : regRunning ? 'First learning cycle running…' : 'No registry yet. Press <b>Run learning cycle</b>.'}</div>`;
    board.innerHTML = ''; $('#cregTabs').innerHTML = ''; meta.textContent = ''; return;
  }
  const L = d.last_run || {}, b = d.baseline || {}, folds = d.folds || [];
  meta.textContent = `NQ futures ${d.data.NQ.from} → ${d.data.NQ.to} · ${d.data.NQ.sessions} sessions · ${d.data.NQ.candidates} candidates · ES check · ${d.generated}`;
  $('#cregRule').innerHTML = `<b>How it learns.</b> Each cycle re-runs the engine on NQ futures, cuts the history into ${folds.length} week-block folds
    (${folds.filter(f => f.role === 'decide').length} decide · ${folds.filter(f => f.role === 'confirm').length} confirm, outlined bars = out-of-sample), and measures every recorded feature's lift on all candidates (thick bar) and on taken trades (thin bar), plus ES.
    The sign is decided on the earlier folds and must hold on the later ones. Sign-stable features are then tested as grade weights and filters with a real re-run; live ones are tested for removal.
    ${esc(d.rule?.text || '')} Nothing goes live automatically: passing changes are recommendations for the lead. <span class="creg-chip hook">needs engine hook</span> = tested by re-scaling the trade list; the engine cannot express it yet.`;

  // ---- last-run summary
  const counts = L.counts || {};
  const tb = L.tpw_before || {}, ta = L.tpw_after;
  const k = [
    ['Active', counts.ACTIVE ?? 0, 'in the grade / gate'], ['Probation', counts.PROBATION ?? 0, 're-tested nightly'],
    ['Candidate', counts.CANDIDATE ?? 0, 'collecting evidence'], ['Retired', counts.RETIRED ?? 0, 'did not help'],
    ['Trades / week', `${fmtN(tb.NQ, 1)}${ta ? ' → ' + fmtN(ta.NQ, 1) : ''}`, `NQ · target 2–4 · ES ${fmtN(tb.ES, 1)}`],
    ['NQ baseline', money(b.nq_total), `${b.nq_n} trades · ES ${money(b.es_total)}`],
  ];
  const c = L.combined;
  const nm = (id) => d.items[id]?.name || id;
  const foldTbl = c ? `<table class="tbl"><tr><th></th>${folds.map(f => `<th class="r">${esc(f.label)}${f.role === 'confirm' ? ' <span class="muted">OOS</span>' : ''}</th>`).join('')}<th class="r">NQ total</th><th class="r">ES</th></tr>
      <tr><td>Before</td>${b.folds.map(p => `<td class="r mono ${cls(p.pnl)}">${money(p.pnl)}<div class="muted small">${fmtN(p.tpw, 1)}/wk</div></td>`).join('')}<td class="r mono ${cls(b.nq_total)}">${money(b.nq_total)}<div class="muted small">${fmtN(b.nq_tpw, 1)}/wk</div></td><td class="r mono ${cls(b.es_total)}">${money(b.es_total)}</td></tr>
      <tr><td>After</td>${c.fold_pnl.map((v, j) => `<td class="r mono ${cls(v)}">${money(v)}<div class="muted small">${fmtN(c.fold_tpw[j], 1)}/wk</div></td>`).join('')}<td class="r mono ${cls(c.nq_total)}">${money(c.nq_total)}<div class="muted small">${fmtN(c.nq_tpw, 1)}/wk</div></td><td class="r mono ${cls(c.es_total)}">${money(c.es_total)}</td></tr></table>` : '';
  const recHtml = (L.recommended_items || []).length
    ? `<div class="creg-rec"><b>Recommended for the lead</b> · ${L.recommended_items.map(i => esc(nm(i))).join(' + ')}
        <div style="margin-top:6px">${Object.keys(L.recommended_params || {}).length ? `Engine params: <code>${esc(JSON.stringify(L.recommended_params))}</code>` : ''}
        ${(L.recommended_hooks || []).length ? ` <span class="creg-chip hook">needs engine hook</span> <code>${esc(JSON.stringify(L.recommended_hooks))}</code>` : ''}</div>
        <div class="muted small" style="margin-top:4px">NQ ${money(c.d_nq)} (out-of-sample ${money(c.d_confirm)}, 90% CI of the gain ${money(c.ci90_d_nq?.[0])} … ${money(c.ci90_d_nq?.[1])}) · ES ${money(c.d_es)}</div>${foldTbl}</div>`
    : `<div class="creg-rec none">No change passed the adoption rule this cycle; the current grade stays as it is.</div>`;
  const changes = [
    (L.added || []).length ? `Added / re-weighted: ${L.added.map(i => esc(nm(i))).join(', ')}` : '',
    (L.retired_live || []).length ? `Retirement recommended (live today): ${L.retired_live.map(i => esc(nm(i))).join(', ')}` : '',
    (L.newly_retired || []).length ? `${L.newly_retired.length} newly retired` : '',
  ].filter(Boolean).join(' · ');
  sum.innerHTML = `<div class="creg-sum">${k.map(([a, v, s]) => `<div class="kpi"><div class="k">${a}</div><div class="v" style="font-size:20px">${v}</div><div class="s">${s}</div></div>`).join('')}</div>
    ${recHtml}<div class="muted small">Last cycle ${esc(L.started || '')} · ${L.n_tests ?? 0} tests · ${L.n_backtests ?? 0} backtests · ${L.secs ?? '?'}s${changes ? ' · ' + changes : ''}</div>`;

  // ---- tabs + board
  const all = Object.values(d.items).filter(it => !it.stale);
  if (!ST.includes(regTab)) regTab = 'ACTIVE';
  const tabs = $('#cregTabs');
  tabs.innerHTML = ST.map(s => `<button data-v="${s}" class="${s === regTab ? 'on' : ''}">${s} <span class="muted">${all.filter(x => x.status === s).length}</span></button>`).join('');
  tabs.onclick = (e) => { const bt = e.target.closest('button'); if (!bt) return; regTab = bt.dataset.v; renderReg(); };
  $('#cregTabNote').textContent = ST_NOTE[regTab];
  const tested = (it) => (it.tests || []).length ? 0 : 1;
  const rows = all.filter(it => it.status === regTab)
    .sort((a, b2) => (b2.live - a.live) || (tested(a) - tested(b2)) || ((bestTest(b2)?.result.d_nq ?? -1e9) - (bestTest(a)?.result.d_nq ?? -1e9)) || a.name.localeCompare(b2.name));
  const nf = folds.length + 1;
  const max = Math.max(0.5, ...rows.flatMap(it => (it.evidence?.candidates.per || []).map(p => Math.abs(p.lift || 0))));
  board.innerHTML = `<div class="creg-wrap"><div class="creg-head" style="--nf:${nf}"><span>Confluence</span>
      ${folds.map(f => `<span class="mono ${f.role === 'confirm' ? 'conf' : ''}" title="${esc(f.from)} → ${esc(f.to)} · ${f.sessions} sessions · ${f.role}">${esc(f.name)}</span>`).join('')}<span class="mono" title="ES futures, robustness check">ES</span>
      <span>Decision · reason</span><span>Best test</span></div>
    ${rows.map(it => {
      const ev = it.evidence;
      const cells = ev ? ev.candidates.per.map((p, j) => `<div class="ev">${lbar(p, max, p.role === 'confirm' ? 'conf' : '')}${lbar(ev.taken.per[j], max, 'tk' + (p.role === 'confirm' ? ' conf' : ''))}</div>`).join('')
        : Array.from({ length: nf }, () => '<div class="ev"><div class="dbar na"><span></span></div></div>').join('');
      const bt = bestTest(it), r = bt?.result;
      const sc = it.scan;
      const tst = r ? `<div class="tst" title="${esc(bt.label)}${r.fails.length ? ' · failed: ' + esc(r.fails.join('; ')) : ''}">
          <span class="pill ${r.verdict === 'pass' ? 'ok' : r.verdict === 'partial' ? '' : 'bad'}">${r.verdict}</span> ${esc(bt.label)}<br>
          NQ <span class="${cls(r.d_nq)}">${money(r.d_nq)}</span> · OOS <span class="${cls(r.d_confirm)}">${money(r.d_confirm)}</span><br>
          ES <span class="${cls(r.d_es)}">${money(r.d_es)}</span> · ${fmtN(r.nq_tpw, 1)}/wk</div>` : `<div class="tst muted">${sc ? esc(sc.verdict.toLowerCase()) + ' · not tested' : '—'}</div>`;
      return `<div class="creg-row ${it.status.toLowerCase()}" style="--nf:${nf}">
        <div class="nm"><b>${esc(it.name)}</b><div>
          <span class="creg-chip">${esc(it.mechanism)}${it.weight ? ' · w ' + it.weight : ''}</span>
          ${it.live ? '<span class="creg-chip">live</span>' : ''}${it.recommended ? '<span class="creg-chip rec">recommended</span>' : ''}${it.needs_engine_hook ? '<span class="creg-chip hook">needs engine hook</span>' : ''}
          ${sc ? `<span class="creg-chip" title="lift sign decided on earlier folds; ${sc.agree}/${sc.valid} folds agree; out-of-sample ${sc.wf_confirm ? 'confirms' : 'does not confirm'}">${esc(sc.verdict)} ${sc.sign > 0 ? 'helps' : sc.sign < 0 ? 'hurts' : ''}</span>` : ''}
          ${ev?.candidates.ci90 ? `<span class="creg-chip" title="90% bootstrap interval of the pooled NQ candidate lift">CI ${fmtR(ev.candidates.ci90[0])}…${fmtR(ev.candidates.ci90[1])}</span>` : ''}</div>
          <div class="muted small">${it.added ? 'added ' + esc(it.added) : ''}${it.retired ? 'retired ' + esc(it.retired) : ''}${!it.added && !it.retired ? 'first seen ' + esc(it.first_seen || '') : ''}</div></div>
        ${cells}
        <div class="why"><b>${esc((it.decision || '').toUpperCase())}</b> · ${esc(it.reason || '')}</div>
        ${tst}</div>`;
    }).join('') || '<div class="empty">Nothing here this cycle.</div>'}</div>`;
}

// ---------- discovery leaderboard
let disc = null, discTimer = null;
async function loadDisc() {
  try { disc = await api('/api/discovery'); } catch (e) { disc = null; }
  renderDisc();
  if (disc?.running) pollDisc();
}
function pollDisc() {
  clearTimeout(discTimer);
  discTimer = setTimeout(async () => { await loadDisc(); }, 8000);
}
function renderDisc() {
  const box = $('#discBoard');
  if (!disc?.data) { box.innerHTML = `<div class="empty">${disc?.running ? 'Scanning every confluence across every period…' : 'No scan yet. Press Re-scan.'}</div>`; return; }
  const d0 = disc.data, mode = $('#discFilter').value;
  // owner rule: real CME futures only. Older scans carry CFD slices: hide those columns.
  const keep = d0.slices.map((s, j) => /CFD|NQX|ESX/i.test(s.name) ? -1 : j).filter(j => j >= 0);
  const hidden = d0.slices.length - keep.length;
  const d = { ...d0, slices: keep.map(j => d0.slices[j]), features: d0.features.map(x => ({ ...x, per: keep.map(j => x.per[j]) })) };
  box.style.setProperty('--ns', d.slices.length);
  $('#discMeta').textContent = `${d.n_features} features · ${d.counts.STABLE} stable · ${d.counts.LEANING} leaning · ${d.generated}${hidden ? ` · ${hidden} non-futures columns hidden (verdicts and pooled from an older scan; the registry above is futures-only)` : ''}${disc.running ? ' · re-scanning…' : ''}`;
  let rows = d.features;
  if (mode === 'signal') rows = rows.filter(x => x.verdict !== 'NOISE');
  if (mode === 'new') rows = rows.filter(x => x.is_new);
  const max = Math.max(0.5, ...rows.flatMap(x => x.per.map(p => Math.abs(p.lift || 0))));
  const bar = (p) => {
    if (p.lift == null) return `<div class="dbar na" title="${esc(p.slice)}: not enough samples"><span></span></div>`;
    const w = Math.min(50, Math.abs(p.lift) / max * 50);
    return `<div class="dbar" title="${esc(p.slice)}: ${fmtR(p.lift)} lift · ${p.n_on} with / ${p.n_off} without">
      <span class="${p.lift > 0 ? 'pos' : 'neg'}" style="${p.lift > 0 ? 'left:50%' : `left:${50 - w}%`};width:${w}%"></span></div>`;
  };
  box.innerHTML = `<div class="disc-head"><span>#</span><span>Confluence</span><span>Verdict</span>
      ${d.slices.map(s => `<span class="mono" title="${s.n} candidates · avg ${fmtR(s.avg_r ?? 0)}">${esc(s.name)}</span>`).join('')}
      <span>Pooled</span><span title="same lift measured on taken trades only">Taken</span><span>t</span><span>Seen</span></div>
    ${rows.map((x, k) => `<div class="disc-row ${x.verdict.toLowerCase()}">
      <span class="mono muted">${k + 1}</span>
      <span>${esc(x.name)}${x.is_new ? ' <i class="tag-new">NEW</i>' : ''}<em class="muted small"> ${x.sign > 0 ? 'helps' : 'hurts'}</em></span>
      <span><b class="verdict">${x.verdict}</b> <span class="muted small">${x.agree}/${x.slices_ok}</span></span>
      ${x.per.map(bar).join('')}
      <span class="mono ${cls(x.pooled)}">${fmtR(x.pooled)}</span>
      <span class="mono ${x.pooled_taken == null ? 'muted' : cls(x.pooled_taken)}" title="${x.n_taken || 0} taken trades with it">${x.pooled_taken == null ? '—' : fmtR(x.pooled_taken)}</span>
      <span class="mono">${fmtN(x.t, 1)}</span>
      <span class="mono muted">${Math.round(x.freq * 100)}%</span></div>`).join('') || '<div class="empty">Nothing in this filter.</div>'}`;
}

const mean = (a) => a.length ? a.reduce((x, y) => x + y, 0) / a.length : null;

function renderExitSig(res) {
  const box = $('#exitSig');
  if (!box) return;
  const xs = res.exit_signals || [];
  const p = effective();
  const rules = new Set(String(p.exit_rules || '').split(',').map(s => s.trim()).filter(Boolean));
  if (!xs.length) { box.innerHTML = '<div class="empty">No exit signals fired in this run.</div>'; return; }
  const max = Math.max(0.3, ...xs.map(x => Math.abs(x.avg_gain || 0)));
  box.innerHTML = `<table class="tbl"><tr><th>Signal</th><th>Status</th><th class="r">Fired</th><th class="r">Acted</th><th>Avg gain if we had left</th><th class="r">Helped</th><th class="r">Hurt</th><th class="r">Total</th></tr>
    ${xs.map(x => {
      const st = rules.has(x.key) ? '<span class="pill ok">RULE</span>' : x.learned ? '<span class="pill ok">LEARNED</span>' : (x.n || 0) >= (p.exit_learn_min || 20) ? '<span class="pill">rejected</span>' : '<span class="pill muted">learning</span>';
      const g = x.avg_gain, w = g == null ? 0 : Math.min(50, Math.abs(g) / max * 50);
      const bar = g == null ? '—' : `<div class="dbar" style="min-width:140px"><span class="${g > 0 ? 'pos' : 'neg'}" style="${g > 0 ? 'left:50%' : `left:${50 - w}%`};width:${w}%"></span></div>`;
      return `<tr><td><b>${esc(x.key)}</b><div class="muted small">${esc(x.label)}</div></td><td>${st}</td><td class="r mono">${x.n}</td><td class="r mono">${x.acted}</td>
        <td><div class="row gap" style="align-items:center">${bar}<span class="mono ${cls(g)}">${g == null ? '' : fmtR(g)}</span></div></td>
        <td class="r mono">${x.helped == null ? '—' : Math.round(x.helped * 100) + '%'}</td><td class="r mono">${x.hurt == null ? '—' : Math.round(x.hurt * 100) + '%'}</td>
        <td class="r mono ${cls(x.total_gain)}">${x.total_gain == null ? '—' : fmtR(x.total_gain)}</td></tr>`;
    }).join('')}</table>`;
}

function render(res) {
  if (!res || !res.shadows) return;
  renderExitSig(res);
  const sh = res.shadows;
  const days = res.days.map(d => d.date);
  if (!split || !days.includes(split)) split = days.includes('2026-09-22') ? '2026-09-22' : days[Math.floor(days.length * 0.6)];
  $('#confSplit').innerHTML = days.map(d => `<option ${d === split ? 'selected' : ''}>${d}</option>`).join('');
  const taken = sh.filter(s => s.taken), rej = sh.filter(s => !s.taken);
  const p = effective();
  const k = [
    ['Candidate signals', sh.length, `${(sh.length / Math.max(1, res.days.length) * 5).toFixed(1)} per week`],
    ['Taken', taken.length, `avg ${fmtR(mean(taken.map(s => s.r)))}`],
    ['Rejected / blocked', rej.length, `avg ${fmtR(mean(rej.map(s => s.r)))}`],
    ['Filter value', fmtR((mean(taken.map(s => s.r)) ?? 0) - (mean(sh.map(s => s.r)) ?? 0)), 'taken vs all candidates'],
    ['Learner', p.learn ? 'ON' : 'off', p.learn ? `min ${p.learn_min} shadows` : 'rule-based scoring'],
  ];
  $('#confKpis').innerHTML = k.map(([a, b, c]) => `<div class="kpi"><div class="k">${a}</div><div class="v">${b}</div><div class="s">${c}</div></div>`).join('');

  // ---- feature table
  const rows = Object.entries(FEATURE_LABELS).map(([key, [label, w]]) => {
    const part = (S2) => {
      const on = S2.filter(s => (s.f[key] ?? 0) > 0).map(s => s.r), off = S2.filter(s => (s.f[key] ?? 0) <= 0).map(s => s.r);
      return { n: on.length, edge: on.length && off.length ? mean(on) - mean(off) : null, r: mean(on) };
    };
    const a = part(sh.filter(s => s.day < split)), b = part(sh.filter(s => s.day >= split)), all = part(sh);
    const cons = a.edge != null && b.edge != null && a.edge * b.edge > 0 && Math.min(Math.abs(a.edge), Math.abs(b.edge)) > 0.15;
    return { key, label, w: w ? p[w] : null, a, b, all, cons };
  });
  const e = (x) => x == null ? '<span class="muted">—</span>' : `<span class="${cls(x)}">${x > 0 ? '+' : ''}${x.toFixed(2)}R</span>`;
  $('#confTable').innerHTML = `<tr><th>Confluence</th><th>Weight</th><th>n</th><th>Avg R when present</th><th>Edge before</th><th>Edge after</th><th>Stable?</th></tr>` +
    rows.map(r => `<tr><td>${esc(r.label)}</td><td class="mono">${r.w ?? '—'}</td><td class="mono">${r.all.n}</td><td class="mono">${e(r.all.r)}</td><td class="mono">${e(r.a.edge)}</td><td class="mono">${e(r.b.edge)}</td>
      <td>${r.cons ? (r.a.edge > 0 ? '<span class="tag-chip" style="background:var(--good);color:#fff">helps</span>' : '<span class="tag-chip" style="background:var(--bad);color:#fff">hurts</span>') : '<span class="muted small">noise</span>'}</td></tr>`).join('');
  const stable = rows.filter(r => r.cons);
  $('#confNote').innerHTML = `Edge = avg R with the confluence present minus avg R without it. <b>Stable</b> means the same sign and over 0.15R on both sides of the split. ${stable.length} of ${rows.length} pass on ${sh.length} candidates. Small samples make most edges noise; collect more history before trusting a weight.`;

  // ---- MTF buckets
  const buckets = [-4, -3, -2, -1, 0, 1, 2, 3, 4].map(v => ({ v, rs: sh.filter(s => s.f.mtf_net === v).map(s => s.r) })).filter(b => b.rs.length);
  cj('confMtf', {
    type: 'bar',
    data: { labels: buckets.map(b => (b.v > 0 ? '+' : '') + b.v), datasets: [{ data: buckets.map(b => mean(b.rs)), backgroundColor: buckets.map(b => mean(b.rs) >= 0 ? css('--good') : css('--bad')), borderRadius: 4, borderSkipped: 'start' }] },
    options: baseOpts({ plugins: { legend: { display: false }, tooltip: { callbacks: { label: c => `${fmtR(c.parsed.y)} · ${buckets[c.dataIndex].rs.length} candidates · ${Math.round(buckets[c.dataIndex].rs.filter(r => r > 0).length / buckets[c.dataIndex].rs.length * 100)}% win` } } },
      scales: { x: { title: { display: true, text: '−4 against … +4 with' }, grid: { display: false } }, y: { ticks: { callback: v => v + 'R' } } } }),
  });
  // ---- premium / discount buckets (direction-adjusted: 0 = deepest discount for longs / premium for shorts)
  const pdB = [['beyond', -9, 0], ['0–25%', 0, .25], ['25–50%', .25, .5], ['50–75%', .5, .75], ['75–100%', .75, 1], ['far side', 1, 9]].map(([lab, a, z]) => {
    const rs = sh.filter(s => s.f.pd_pos != null).filter(s => { const v = s.dir === 1 ? s.f.pd_pos : 1 - s.f.pd_pos; return v >= a && v < z; }).map(s => s.r);
    return { lab, rs };
  }).filter(b => b.rs.length);
  cj('confPd', {
    type: 'bar',
    data: { labels: pdB.map(b => b.lab), datasets: [{ data: pdB.map(b => mean(b.rs)), backgroundColor: pdB.map(b => mean(b.rs) >= 0 ? css('--good') : css('--bad')), borderRadius: 4, borderSkipped: 'start' }] },
    options: baseOpts({ plugins: { legend: { display: false }, tooltip: { callbacks: { label: c => `${fmtR(c.parsed.y)} · ${pdB[c.dataIndex].rs.length} candidates` } } },
      scales: { x: { grid: { display: false }, ticks: { maxRotation: 0, autoSkip: false, font: { size: 10 } } }, y: { ticks: { callback: v => v + 'R' } } } }),
  });

  // ---- learner
  const log = res.learner_log || [];
  $('#learnState').textContent = p.learn ? `on · ${log.length} decisions` : 'off';
  let html = '';
  if (log.length) {
    const w = log.at(-1).w;
    const ent = Object.entries(w).filter(([k]) => FEATURE_LABELS[k] || k === 'rr_plan').sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]));
    const mx = Math.max(0.01, ...ent.map(([, v]) => Math.abs(v)));
    html += `<div class="muted small" style="margin-bottom:6px">Latest model (fit on ${log.at(-1).n} resolved shadows, base ${fmtR(log.at(-1).mu)}). Took ${log.filter(x => x.take).length} of ${log.length}.</div><div class="bars-list">` +
      ent.map(([k2, v]) => `<div class="bl-row"><span class="lbl">${esc(FEATURE_LABELS[k2]?.[0] || 'planned R')}</span><div class="bl-track"><div class="mid"></div><div class="fill" style="${v >= 0 ? `left:50%;width:${Math.abs(v) / mx * 50}%;background:var(--good)` : `right:50%;width:${Math.abs(v) / mx * 50}%;background:var(--bad)`}"></div></div><span class="mono small ${cls(v)}">${v > 0 ? '+' : ''}${v.toFixed(2)}</span><span></span><span></span></div>`).join('') + '</div>';
  } else {
    html += `<div class="note">The learner refits a ridge regression on shadow trades already resolved at each decision (no lookahead) and takes a trade only when predicted R ≥ threshold.
      On 50 days of NQ it <b>underperformed</b> the rule-based filter out-of-sample (+0.33R vs +0.74R per trade): ~40 resolved examples is too few. It's built and ready for when more history accumulates.</div>`;
  }
  html += `<div class="row gap" style="margin-top:10px"><button class="btn primary sm" id="learnCmp">Compare learner vs rules</button></div><div id="learnCmpOut"></div>`;
  $('#learnOut').innerHTML = html;
  $('#learnCmp').onclick = compare;

  // ---- shadow log
  $('#shadowTable').innerHTML = `<tr><th></th><th>Signal (ET)</th><th>Side</th><th>Trigger</th><th>Score</th><th>MTF net</th><th>PD</th><th>Key level</th><th>Virtual R</th></tr>` +
    sh.slice().reverse().map(s => `<tr><td>${s.taken ? '●' : '<span class="muted">○</span>'}</td><td class="mono">${s.day} ${etStr(s.t)}</td><td><span class="dir ${s.dir === 1 ? 'L' : 'S'}">${s.dir === 1 ? 'LONG' : 'SHORT'}</span></td>
      <td>${s.trigger}</td><td class="mono">${s.score}</td><td class="mono ${cls(s.f.mtf_net)}">${s.f.mtf_net > 0 ? '+' : ''}${s.f.mtf_net}</td><td class="mono">${s.f.pd_pos != null ? Math.round(s.f.pd_pos * 100) + '%' : '—'}</td>
      <td>${s.f.keylevel ? '✓' : ''}</td><td class="mono ${cls(s.r)}">${fmtR(s.r)}</td></tr>`).join('');
}

async function compare() {
  busy(true);
  try {
    const [a, b] = await Promise.all([
      api('/api/backtest', { sym: S.sym, tf: S.tf, params: { ...S.params, learn: false }, plan: S.plan }),
      api('/api/backtest', { sym: S.sym, tf: S.tf, params: { ...S.params, learn: true }, plan: S.plan }),
    ]);
    const row = (n, r) => `<tr><td>${n}</td><td class="mono">${r.stats.trades}</td><td class="mono ${cls(r.stats.net)}">${fmtS$(r.stats.net)}</td><td class="mono">${r.stats.profit_factor}</td><td class="mono">${fmtR(r.stats.avg_r)}</td></tr>`;
    $('#learnCmpOut').innerHTML = `<table class="tbl" style="margin-top:8px"><tr><th>Mode</th><th>Trades</th><th>Net</th><th>PF</th><th>Avg R</th></tr>${row('Rule-based score', a)}${row('Walk-forward learner', b)}</table>`;
  } catch (e) { toast(e.message); }
  busy(false);
}
