// Second strategies (PAPER) page: the one renderer shared by the phone app (tools/web_public/second.js) and the PC
// dashboard (web_next/js/next/second.js loads web_next/js/next/secondcore.js, a byte-identical copy: tests/test_second.py
// checks it). Classic script: window.SecondUI.render(el, S, opts). S = engine/second.dashboard_block (data.json "second" /
// GET /api/next/second), opts.live = the PC's live cut (engine/second.compact from live.json / the heartbeat) laid over
// the state when newer. Per strategy: the rules in plain words, today's state (waiting for / armed / in trade / done), the
// paper trades and $, and the research numbers H1 / H2 / 2025 / 2021-24 alone and "with LIT" on one account. Read-only.
(function () {
  'use strict';
  const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const n0 = (v, d = 0) => (v == null || isNaN(v)) ? '—' : Number(v).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });
  const usd = (v) => (v == null || isNaN(v)) ? '—' : (v > 0 ? '+' : v < 0 ? '-' : '') + '$' + Math.abs(Math.round(v)).toLocaleString('en-US');
  const fR = (v) => (v == null || isNaN(v)) ? '—' : (v > 0 ? '+' : '') + Number(v).toFixed(2) + 'R';
  const cl = (v) => v > 0 ? 'sc-up' : v < 0 ? 'sc-dn' : '';
  const hm = (t) => t ? new Date(t * 1000).toLocaleTimeString('en-US', { timeZone: 'America/New_York', hour: '2-digit', minute: '2-digit', hour12: false }) : '—';
  const px = (v) => (v == null || isNaN(v)) ? '—' : Number(v).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const C = { good: 'var(--good,#22c55e)', bad: 'var(--bad,#ef5350)', warn: 'var(--warn,#d4a72c)', mut: 'var(--muted,#8a93a6)', line: 'var(--line,rgba(140,150,170,.25))', acc: 'var(--accent,#6aa9ff)' };
  const STAGE = { waiting: ['Waiting', C.mut], armed: ['Armed', C.warn], in_trade: ['In a trade', C.acc], done: ['Done today', C.good], off: ['Off hours', C.mut], error: ['Error', C.bad] };
  const PER = [['H1', '2026 H1 (picked)'], ['H2', '2026 H2 (check)'], ['2025', '2025'], ['2021-24', '2021-24']];

  function stateBox(s, src) {
    const st = s || {};
    const [lab, col] = STAGE[st.stage] || ['—', C.mut];
    return `<div class="sc-state" style="border-color:${col}"><span class="sc-pill" style="background:${col}">${esc(lab)}</span>
      <b>${esc(st.text || 'No run yet: the cloud / PC bot fills this in its next run.')}</b>
      <em>${st.day ? 'Session ' + esc(st.day) : ''}${st.window ? ' · entries ' + esc(st.window) : ''}${src ? ' · from the ' + esc(src) : ''}</em></div>`;
  }
  function btTable(bt, lab) {
    if (!bt || bt.error) return `<p class="sc-note">Backtest numbers unavailable${bt && bt.error ? ': ' + esc(bt.error) : ''}.</p>`;
    const row = (lab, x) => !x ? `<tr><td>${esc(lab)}</td><td colspan="7" class="sc-mut">—</td></tr>`
      : `<tr><td>${esc(lab)}</td><td>${n0(x.n)}</td><td>${n0(x.tpw, 2)}</td><td>${n0(x.win, 1)}%</td><td>${n0(x.pf, 2)}</td><td class="${cl(x.net)}">${usd(x.net)}</td><td class="${cl(x.per_month)}">${usd(x.per_month)}</td><td>${usd(x.dd)}</td></tr>`;
    const head = '<tr><th>Period</th><th>Trades</th><th>/week</th><th>Win</th><th>PF</th><th>Net $</th><th>$/month</th><th>Max DD</th></tr>';
    const own = PER.map(([k, l]) => row(l, (bt.own || {})[k])).join('');
    const wl = PER.map(([k, l]) => row(l + ' · LIT + it', (bt.with_lit || {})[k]) + row(l + ' · LIT alone', (bt.lit_only || {})[k])).join('');
    const ev = bt.eval_with_lit || {};
    const evl = ['H1', 'H2'].filter((k) => ev[k]).map((k) => `${k}: 2-week pass/fail ${n0(ev[k].p10, 1)}/${n0(ev[k].f10, 1)}%, 1 month ${n0(ev[k].p20, 1)}/${n0(ev[k].f20, 1)}%`).join(' · ');
    return `<h4>Backtest at $500 risk a trade (costs in)</h4><div class="sc-tw"><table class="sc-t"><thead>${head}</thead><tbody>${own}</tbody></table></div>
      <h4>With LIT on one account (LIT first, no entry while LIT is in a trade, max 2 a day)${lab ? ' · ' + esc(lab) : ''}</h4>
      <div class="sc-tw"><table class="sc-t"><thead>${head}</thead><tbody>${wl}</tbody></table></div>
      ${evl ? `<p class="sc-note">MFFU 50K eval with LIT: ${esc(evl)}</p>` : ''}
      <p class="sc-note">Picked on 2026 H1 only; H2 is the untouched check; 2025 and 2021-24 are references. Run ${esc(bt.run || '—')}${bt.writeup ? ` · write-up <a href="#/writeup/${encodeURIComponent(bt.writeup)}">${esc(bt.writeup)}</a>` : ''}.</p>`;
  }
  function trades(rows) {
    if (!rows || !rows.length) return '<p class="sc-note">No paper trades yet (the ledger starts on the first cloud run with the second strategies on).</p>';
    const body = rows.slice().sort((a, b) => (b.entry_t || 0) - (a.entry_t || 0)).slice(0, 40).map((t) => {
      const L = t.lit || {};
      const open = t.exit_kind === 'OPEN';
      return `<tr><td>${esc(t.day || '')} ${hm(t.entry_t)}</td><td>${t.dir > 0 ? 'LONG' : 'SHORT'}</td><td>${n0(t.qty)}</td><td>${px(t.entry)}</td><td>${px(open ? t.stop_now : t.stop)}</td><td>${px(t.target)}</td>
        <td>${open ? 'open · last ' + px(t.last) : esc(t.exit_kind || '')}</td><td class="${cl(t.r)}">${fR(t.r)}</td><td class="${cl(t.usd)}">${usd(t.usd)}</td>
        <td>${L.taken === false ? '<span class="sc-mut">skipped: ' + esc(L.why || '') + '</span>' : L.taken ? usd(L.usd) + (L.why ? ' <span class="sc-mut">(' + esc(L.why) + ')</span>' : '') : '—'}</td></tr>`;
    }).join('');
    return `<div class="sc-tw"><table class="sc-t"><thead><tr><th>Entry (ET)</th><th>Side</th><th>Micros</th><th>Entry</th><th>Stop</th><th>Target</th><th>Exit</th><th>R</th><th>$ (own)</th><th>With LIT</th></tr></thead><tbody>${body}</tbody></table></div>`;
  }
  function strat(s, live) {
    const lv = live && live.strategies ? live.strategies[s.key] : null;
    const st = lv && lv.state ? lv.state : s.state;
    const src = lv && lv.state ? 'PC (live)' : s.state_src === 'PC' ? 'PC' : 'cloud';
    const p = s.paper || {};
    const rows = (s.trades || []).slice();
    if (lv && lv.trades) for (const t of lv.trades) { const i = rows.findIndex((r) => +r.entry_t === +t.entry_t); if (i < 0) rows.push(t); else if (rows[i].exit_kind === 'OPEN') rows[i] = { ...rows[i], ...t }; }
    const rl = routeOf(s, live);
    return `<div class="sc-card"><div class="sc-eyebrow" style="color:${rl.on ? C.acc : C.warn}">${esc(rl.label)} · ${esc(s.short || s.key)}${s.on ? '' : ' · OFF'}</div><h3>${esc(s.label)}</h3>
      ${s.summary ? `<p class="sc-note">${esc(s.summary)}</p>` : ''}
      ${stateBox(st, src)}
      <div class="sc-stats"><div class="sc-stat"><span>Paper trades</span><b>${n0(p.n)}</b><em>${n0(p.wins)} winners</em></div>
        <div class="sc-stat"><span>Paper $ (own, $500 risk)</span><b class="${cl(p.usd)}">${usd(p.usd)}</b><em>since the ledger started</em></div>
        <div class="sc-stat"><span>With LIT (one account)${s.with_lit_label ? ' · ' + esc(s.with_lit_label) : ''}</span><b class="${cl(p.with_lit_usd)}">${usd(p.with_lit_usd)}</b><em>${n0(p.with_lit_n)} taken</em></div></div>
      ${s.with_lit_note ? `<p class="sc-note"><b>${esc(s.with_lit_label || 'Note')}:</b> ${esc(s.with_lit_note)}</p>` : ''}
      <details open><summary><b>Paper trades</b></summary>${trades(rows)}</details>
      <details><summary><b>Rules in plain words</b></summary><ol class="sc-rules">${(s.rules || []).map((r) => `<li>${esc(r)}</li>`).join('')}</ol></details>
      <details><summary><b>Backtest numbers</b></summary>${btTable(s.backtest, s.with_lit_label)}</details></div>`;
  }
  const CSS = `.sc-card{border:1px solid ${C.line};border-radius:14px;padding:14px 16px;margin:0 0 14px;background:color-mix(in srgb,${C.line} 18%,transparent)}.sc-card h3{margin:2px 0 6px;font-size:16px}.sc-card h4{margin:12px 0 6px;font-size:13px}
.sc-eyebrow{font-size:11.5px;letter-spacing:.05em;text-transform:uppercase;color:${C.warn};font-weight:700}.sc-note{margin:6px 0;font-size:12.5px;line-height:1.5;opacity:.8}.sc-mut{opacity:.65}
.sc-banner{border:1.5px solid ${C.warn};border-radius:12px;padding:10px 12px;margin:0 0 12px;font-size:13px;line-height:1.5;background:color-mix(in srgb,${C.warn} 8%,transparent)}
.sc-state{border:1.5px solid ${C.line};border-radius:12px;padding:10px 12px;margin:10px 0}.sc-state b{display:block;font-size:14px;line-height:1.4;margin-top:6px}.sc-state em{display:block;font-style:normal;font-size:11.5px;opacity:.7;margin-top:4px}
.sc-pill{display:inline-block;color:#fff;font-size:11px;font-weight:700;border-radius:999px;padding:2px 9px}
.sc-stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:8px;margin:10px 0}.sc-stat{border:1px solid ${C.line};border-radius:12px;padding:9px 11px;min-width:0}
.sc-stat span{display:block;font-size:11.5px;opacity:.7}.sc-stat b{display:block;font-size:19px;margin-top:2px}.sc-stat em{display:block;font-style:normal;font-size:11.5px;opacity:.7;margin-top:2px}
.sc-up{color:${C.good}}.sc-dn{color:${C.bad}}.sc-tw{overflow-x:auto;max-width:100%}.sc-t{width:100%;border-collapse:collapse;font-size:12.5px}.sc-t th,.sc-t td{padding:6px 8px;border-bottom:1px solid ${C.line};text-align:left;white-space:nowrap}.sc-t th{font-weight:600;opacity:.8}
.sc-rules{margin:8px 0 4px;padding-left:20px;font-size:13px;line-height:1.55}.sc-rules li{margin:3px 0}.sc-card details{margin:8px 0}.sc-card summary{cursor:pointer;font-size:13.5px}`;
  // ---------------------------------------------------------------- Account B (engine/account_b.py): its own account + eval
  // ab = LiveBot.second_route_info().account_b: {label, account, plan_label, kind, sizing, keys, eval: {balance, floor, room,
  // target, to_target, session, status}, open, routed, day_pnl, entries_today, locked, disabled}
  const EVST = { open: ['Eval running', C.acc], passed: ['Eval PASSED', C.good], failed: ['Eval FAILED', C.bad], stuck: ['Stuck: buy a new one', C.warn] };
  function acctB(ab) {
    if (!ab) return '';
    const ev = ab.eval || {};
    const [lab, col] = EVST[ev.status] || [ev.status || '—', C.mut];
    const op = ab.open;
    const rows = (ab.routed || []).slice().reverse().map((r) => `<tr><td>${hm(r.t)}</td><td>${esc(String(r.side || '').toUpperCase())}</td><td>${n0(r.qty)}</td><td>${esc(r.strategy || r.src || '')}</td><td>${esc(r.reason || '')}</td><td class="${cl(r.pnl)}">${r.pnl == null ? '' : usd(r.pnl)}</td></tr>`).join('');
    return `<div class="sc-card"><div class="sc-eyebrow" style="color:${C.acc}">${esc(ab.kind || '')} · ${esc(ab.label || 'Account B')} · ${esc(ab.plan_label || '')}</div>
      <h3>${esc(ab.label || 'Account B')}: ${esc((ab.keys || []).join(' + '))}</h3>
      ${ab.disabled ? `<p class="sc-note" style="color:${C.bad}">Not trading: ${esc(ab.disabled)}</p>` : ''}
      <div class="sc-state" style="border-color:${col}"><span class="sc-pill" style="background:${col}">${esc(lab)}</span>
        <b>${op ? `In a trade: ${esc(op.side)} ${n0(op.qty)} MNQ (${esc(op.strategy || '')}) from ${px(op.entry)}, stop ${px(op.stop)}, target ${px(op.target)}` : 'Flat'}${ab.locked ? ' · locked today: ' + esc(ab.locked) : ''}</b>
        <em>Own eval${ev.start ? ' from ' + esc(ev.start) : ''}${ev.session ? ' · session ' + n0(ev.session) : ''} · size ${esc(ab.sizing || 'need')} · ${esc(ab.note || '')}</em></div>
      <div class="sc-stats"><div class="sc-stat"><span>Balance</span><b>$${n0(ev.balance)}</b><em>today ${usd(ab.day_pnl)}</em></div>
        <div class="sc-stat"><span>Pass target</span><b>$${n0(ev.target)}</b><em>${ev.to_target != null ? usd(ev.to_target) + ' to go' : ''}</em></div>
        <div class="sc-stat"><span>Room to the max-loss floor</span><b>${usd(ev.room)}</b><em>floor $${n0(ev.floor)}</em></div>
        <div class="sc-stat"><span>Trades today</span><b>${n0(ab.entries_today)}</b><em>max 2 a day</em></div></div>
      ${rows ? `<details><summary><b>Orders on ${esc(ab.account || '')}</b></summary><div class="sc-tw"><table class="sc-t"><thead><tr><th>Time</th><th>Side</th><th>Micros</th><th>Strategy</th><th>Reason</th><th>$</th></tr></thead><tbody>${rows}</tbody></table></div></details>` : ''}</div>`;
  }
  function css() { if (!document.getElementById('sc-css')) { const s = document.createElement('style'); s.id = 'sc-css'; s.textContent = CSS; document.head.appendChild(s); } }
  function render(el, S, opts) {
    css();
    opts = opts || {};
    try {
      if (!S || !(S.strategies || []).length) {
        el.innerHTML = `<div class="sc-card"><b>No second strategies in this build.</b><p class="sc-note">${esc((S && S.error) || 'The next cloud run adds them (second_model.json).')}</p></div>`;
        return;
      }
      const anyR = S.strategies.some((s) => routeOf(s, opts.live).on);
      el.innerHTML = `<div class="sc-banner"><b>${anyR ? 'ROUTED + PAPER.' : 'PAPER ONLY.'}</b> ${esc(S.note || 'Nothing is traded. LIT and the eval account are unchanged.')}${S.source ? ' Source: ' + esc(S.source) + '.' : ''}</div>`
        + acctB((opts.live && opts.live.route && opts.live.route.account_b) || S.account_b || (S.route && S.route.account_b))
        + S.strategies.map((s) => strat(s, opts.live)).join('');
    } catch (e) { el.innerHTML = `<div class="sc-card"><b>This page failed to draw</b><p class="sc-note">${esc(String(e && e.message || e))}</p></div>`; }
  }
  // "ROUTED on Sim101" / "PAPER": the PC's live cut (heartbeat / live.json second.route) first, then the dashboard block
  function routeOf(s, live) {
    const lv = live && live.strategies ? live.strategies[s.key] : null;
    const lab = (lv && lv.route_label) || s.route_label || 'paper';
    const on = lv ? !!lv.route : !!s.route;
    return { on, label: on ? String(lab).toUpperCase().replace(/^ROUTED ON/, 'ROUTED on') : 'PAPER' };
  }

  // ---------------------------------------------------------------- the second-strategy brain (Bot Brain pages)
  // data = {strategies: [{key, label, short, route, route_label, state, brain}], src, t}: one card per strategy with its
  // stage, the "waiting for" sentence, every rule in the engine's order (✓ / ✗ / · not yet; the first ✗ = why no trade),
  // the planned entry / stop / target / size, the S/R levels and today's log. engine/second.py brain (closed bars only).
  const BSTAGE = { waiting: ['Waiting', C.mut], armed: ['Armed', C.warn], in_trade: ['In trade', C.acc], done: ['Done today', C.good],
    off: ['Outside its hours', C.mut], error: ['Error', C.bad] };
  const mk = (o) => o === true ? `<span class="sb-ok y">✓</span>` : o === false ? `<span class="sb-ok n">✗</span>` : `<span class="sb-ok q">·</span>`;
  function brainCard(s) {
    const b = s.brain || {}, st = s.state || {};
    const [lab, col] = BSTAGE[b.stage || st.stage] || ['—', C.mut];
    const ro = !!s.route;
    const ff = b.first_fail;
    const pl = b.plan;
    const checks = (b.checks || []).map((c) => `<li class="${c.ok === false ? 'f' : ''}${c.k === ff ? ' ff' : ''}">${mk(c.ok)}<div><b>${esc(c.name)}</b>${c.val ? `<br><span class="sc-mut">${esc(c.val)}</span>` : ''}${c.need ? `<br><span class="sc-mut">needs ${esc(c.need)}</span>` : ''}</div></li>`).join('');
    const lv = (b.levels || []).length ? `<details><summary><b>Levels of the day</b> (${(b.levels || []).filter((x) => x.known).length} known)</summary><div class="sc-tw"><table class="sc-t"><tbody>${b.levels.map((x) => `<tr><td>${esc(x.name)}</td><td>${px(x.px)}</td><td>${x.known ? 'known' : '<span class="sc-mut">not yet</span>'}</td><td>${esc(x.stage || '')}</td></tr>`).join('')}</tbody></table></div></details>` : '';
    const log = (b.log || []).slice().reverse().map((x) => `<li class="${x.trade ? 'tr' : x.signal ? 'sg' : ''}"><span>${esc(x.text || '')}</span></li>`).join('');
    return `<div class="sc-card sb-card"><div class="sc-eyebrow" style="color:${ro ? C.acc : C.warn}">${ro ? esc(s.route_label || 'ROUTED') : 'PAPER'} · ${esc(s.short || s.key)}</div>
      <h3>${esc(s.label || s.key)}</h3>
      <div class="sc-state" style="border-color:${col}"><span class="sc-pill" style="background:${col}">${esc(lab)}</span><b>${esc(b.text || st.text || '—')}</b>
        <em>${esc((b.focus || {}).label || '')}${b.closed_bars_only !== false ? ' · closed bars only' : ''}${s.src ? ' · ' + esc(s.src) : ''}</em></div>
      ${b.error ? `<p class="sc-note" style="color:${C.bad}">Brain error: ${esc(b.error)}</p>` : ''}
      ${checks ? `<h4>Rules in the engine's order${ff ? ` · stopped at: <span style="color:${C.bad}">${esc(((b.checks || []).find((c) => c.k === ff) || {}).name || ff)}</span>` : ''}</h4><ul class="sb-ck">${checks}</ul>` : ''}
      ${pl ? `<p class="sc-note"><b>${esc(pl.side === 'long' ? 'LONG' : 'SHORT')} plan${pl.estimate ? ' (estimate until the fill bar)' : ''}:</b> entry ${px(pl.entry)} · stop ${px(pl.stop)} (${n0(pl.risk_pts, 2)} pts) · target ${px(pl.target)}${pl.rr ? ` (${n0(pl.rr, 2)}R)` : ''} · ${n0(pl.qty_500)} micros at $500 risk${ro ? ' (on the eval: capped by 60% of the room and the soft daily loss)' : ''}${pl.when ? ' · ' + esc(pl.when) + ' ET' : ''}</p>` : ''}
      ${lv}
      ${log ? `<details open><summary><b>Thought log today</b></summary><ol class="sb-log">${log}</ol></details>` : ''}</div>`;
  }
  const BCSS = `.sb-ck{list-style:none;margin:4px 0 0;padding:0}.sb-ck li{display:flex;gap:8px;padding:6px 0;border-top:1px solid ${C.line};font-size:13px;line-height:1.4}
.sb-ck li.f b{color:${C.bad}}.sb-ck li.ff{background:color-mix(in srgb,${C.bad} 7%,transparent)}
.sb-ok{flex:none;display:inline-grid;place-items:center;width:21px;height:21px;border-radius:7px;font-weight:800;font-size:12px}
.sb-ok.y{color:${C.good};background:color-mix(in srgb,${C.good} 16%,transparent)}.sb-ok.n{color:${C.bad};background:color-mix(in srgb,${C.bad} 16%,transparent)}.sb-ok.q{color:${C.mut}}
.sb-log{list-style:none;margin:4px 0;padding:0}.sb-log li{padding:5px 0;border-bottom:1px solid ${C.line};font-size:12.5px;line-height:1.4}.sb-log li.tr{color:${C.good};font-weight:650}.sb-log li.sg{color:${C.warn};font-weight:650}`;
  function brain(el, data, opts) {
    css();
    if (!document.getElementById('sb-css')) { const t = document.createElement('style'); t.id = 'sb-css'; t.textContent = BCSS; document.head.appendChild(t); }
    opts = opts || {};
    try {
      const L = (data && data.strategies) || [];
      if (!L.length) {
        el.innerHTML = `<div class="sc-card"><b>No second-strategy brain yet.</b><p class="sc-note">${esc((data && data.error) || 'It appears after the PC bot (or the cloud run) has run the second strategies with this version.')}</p></div>`;
        return;
      }
      const nR = L.filter((s) => s.route).length;
      el.innerHTML = `<div class="sc-banner"><b>Second-strategy brain.</b> ${nR ? `${nR} routed to the account next to LIT (LIT first, one position at a time, max 2 trades a day); the rest paper.` : 'All paper: nothing here is traded.'} Each card: what it waits for and every rule in the engine's order (✓ passed · ✗ failed: the first ✗ is why there is no trade · · not decided yet).${data.src ? ' Source: ' + esc(data.src) + (data.t ? ' · ' + hm(data.t) + ' ET' : '') + '.' : ''}</div>`
        + acctB(data.account_b) + L.map(brainCard).join('');
    } catch (e) { el.innerHTML = `<div class="sc-card"><b>The second brain failed to draw</b><p class="sc-note">${esc(String(e && e.message || e))}</p></div>`; }
  }
  // the list from a compact (heartbeat / live.json / /api/next/brain/second) or a dashboard block (data.json "second")
  function brainList(x, src) {
    if (!x) return null;
    const account_b = (x.route && x.route.account_b) || x.account_b || null;
    if (Array.isArray(x.strategies)) return { src, t: x.t, account_b, strategies: x.strategies.map((s) => ({ ...s, src })) };
    return { src, t: x.t, account_b, strategies: Object.entries(x.strategies || {}).map(([key, s]) => ({ key, ...s, src })) };
  }
  window.SecondUI = { render, brain, brainList, acctB, version: 3 };
})();
