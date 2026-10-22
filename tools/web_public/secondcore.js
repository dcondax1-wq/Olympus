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
  const STAGE = { waiting: ['Waiting', C.mut], armed: ['Armed', C.warn], in_trade: ['In a paper trade', C.acc], done: ['Done today', C.good], off: ['Off hours', C.mut], error: ['Error', C.bad] };
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
    return `<div class="sc-card"><div class="sc-eyebrow">PAPER · ${esc(s.short || s.key)}${s.on ? '' : ' · OFF'}</div><h3>${esc(s.label)}</h3>
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
  function css() { if (!document.getElementById('sc-css')) { const s = document.createElement('style'); s.id = 'sc-css'; s.textContent = CSS; document.head.appendChild(s); } }
  function render(el, S, opts) {
    css();
    opts = opts || {};
    try {
      if (!S || !(S.strategies || []).length) {
        el.innerHTML = `<div class="sc-card"><b>No second strategies in this build.</b><p class="sc-note">${esc((S && S.error) || 'The next cloud run adds them (second_model.json).')}</p></div>`;
        return;
      }
      el.innerHTML = `<div class="sc-banner"><b>PAPER ONLY.</b> ${esc(S.note || 'Nothing is traded. LIT and the eval account are unchanged.')}${S.source ? ' Source: ' + esc(S.source) + '.' : ''}</div>`
        + S.strategies.map((s) => strat(s, opts.live)).join('');
    } catch (e) { el.innerHTML = `<div class="sc-card"><b>This page failed to draw</b><p class="sc-note">${esc(String(e && e.message || e))}</p></div>`; }
  }
  window.SecondUI = { render, version: 1 };
})();
