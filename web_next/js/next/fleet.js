// PC dashboard: the Fleet (2026-10-30, copy trading to the follower accounts; read-only: it never arms, routes, kills or
// changes the bot; the switches are the CLI lines it shows).
//   #fleet   every follower (engine/fleet.py): firm + plan, stage (eval / funded / LIVE), status, balance, room to the firm's
//            floor (EOD / intraday trailing the firm's way), daily loss left, $ to the target, today / this week, the open
//            copy, slippage vs the lead's fill, the last copy it skipped and why, rule warnings (unverified / unknown values);
//            the leads' own accounts; the fleet kill flag; the firm catalog (plans, verified / unknown counts, the owner's
//            prices only) with the "Add an account" steps (docs/ADD_ACCOUNT.md).
// Data: GET /api/next/fleet (engine/fleet_api.py), every 15 s while the page is open.
import { $, esc } from '../util.js';

(function ensure() {
  if (!document.getElementById('page-fleet')) {
    const ref = document.getElementById('page-cc') || document.querySelector('section.page');
    const s = document.createElement('section'); s.className = 'page'; s.id = 'page-fleet';
    s.innerHTML = '<div class="empty">Loading the fleet…</div>';
    if (ref?.parentNode) ref.parentNode.insertBefore(s, ref.nextSibling); else document.body.appendChild(s);
  }
})();

const S = { timer: null, d: null, firm: null };
const active = () => document.getElementById('page-fleet')?.classList.contains('active');
const ok = (v) => v !== null && v !== undefined && !Number.isNaN(+v);
const usd = (v) => (!ok(v) ? '—' : (+v < 0 ? '−$' : '$') + Math.abs(+v).toLocaleString('en-US', { maximumFractionDigits: 0 }));
const susd = (v) => (!ok(v) ? '—' : (+v > 0 ? '+' : '') + usd(v));
const tone = (v) => (+v > 0 ? 'good' : +v < 0 ? 'bad' : '');
const stat = (label, value, sub = '', k = '') => `<div class="nx-stat"><span>${esc(label)}</span><b class="${k}">${value}</b>${sub ? `<em>${sub}</em>` : ''}</div>`;
const STATUS = { running: ['Running', ''], passed: ['EVAL PASSED', 'good'], failed: ['FAILED', 'bad'], killed: ['KILLED', 'bad'], off: ['Off', ''], 'not running': ['Bot not running', ''] };
const STEPS = `<ol class="muted"><li>Buy the account (your own price + the firm's current code; never the list price).</li>
  <li>Log it in NinjaTrader 8 (its Name shows in the Accounts tab); test it on Sim first.</li>
  <li>One line on this PC: <code>python -X utf8 -m engine.fleet --add --id &lt;id&gt; --lead zlarior --plan &lt;plan&gt; --account "&lt;Name&gt;" --start &lt;day&gt;</code></li></ol>
  <p class="muted">Nothing is ever armed for you: a real account copies only after <code>--arm &lt;id&gt;</code> AND the live phrase at the bot's start. Step by step: docs/ADD_ACCOUNT.md.</p>`;

function card(a) {
  if (a.error) return `<div class="card nx-glass"><div class="card-h"><h3>${esc(a.name || a.id)}</h3></div><p class="muted">${esc(a.error)}</p></div>`;
  const st = STATUS[a.status] || [a.status || '—', ''];
  const lab = a.label || 'PAPER';
  const isLive = a.stage === 'live';
  const o = a.open;
  const tiles = [
    stat('Balance', usd(a.balance), `start ${usd(a.start)}`),
    isLive ? stat('Daily stop left', usd(a.day_left), `week ${usd(a.week_left)}`) : stat('Room to the floor', usd(a.room), `floor ${usd(a.floor)} · day ${usd(a.day_left)}`),
    stat('Today', susd(a.today), `week ${susd(a.week)}`, tone(a.today)),
    a.stage === 'eval' ? stat('To target', usd(a.to_target), `${esc(a.days_traded ?? 0)} days traded`) : stat('Copies', esc(a.trades ?? 0), a.payout && a.payout.ready ? 'payout ready' : ''),
  ].join('');
  const chips = [
    `<span class="nx-chip">${o ? `${esc(o.side)} ${esc(o.qty)} @ ${esc(o.entry)}` : 'flat'}</span>`,
    ok(a.slip_ticks) ? `<span class="nx-chip">slippage vs lead ${+a.slip_ticks > 0 ? '+' : ''}${esc(a.slip_ticks)} ticks (${esc(a.slip_n)})</span>` : '',
    a.stagger_ms ? `<span class="nx-chip">stagger ${esc(a.stagger_ms)} ms</span>` : '',
    a.unknown && a.unknown.length ? `<span class="nx-chip warn">unknown rules: ${esc(a.unknown.slice(0, 4).join(', '))}</span>` : '',
  ].join('');
  const sz = a.size ? `<p class="muted">Last size: ${esc(a.size.qty)} micros (lead ${esc(a.size.lead_qty)}) · ${esc((a.size.reasons || []).slice(-1)[0] || '')}</p>` : '';
  const sk = a.last_skip ? `<p class="muted">Last copy skipped: ${esc(a.last_skip.why)}</p>` : '';
  const warn = (a.warn || []).map((w) => `<span class="nx-chip warn">${esc(w)}</span>`).join(' ');
  return `<div class="card nx-glass fx-card"><div class="card-h"><h3>${esc(a.name || a.id)} <span class="nx-badge ${lab === 'LIVE' || lab === 'REAL' ? 'bad' : ''}">${esc(lab)}</span></h3>
    <div class="card-tools"><span class="nx-badge ${st[1]}">${esc(st[0])}</span></div></div>
    <p class="muted">${esc(a.firm || '')} ${esc(a.plan || '')} · ${esc(isLive ? 'LIVE account' : a.stage === 'funded' ? 'funded' : 'eval')} · copies ${esc(a.lead_name || a.lead)}${a.nt_account ? ` · ${esc(a.nt_account)}` : ''}${a.why ? ` · ${esc(a.why)}` : ''}</p>
    <div class="nx-kv">${tiles}</div><div>${chips}</div>${sz}${sk}${warn ? `<div>${warn}</div>` : ''}</div>`;
}

function catalog(F) {
  const firms = F || [];
  if (!firms.length) return '';
  const f = firms.find((x) => x.id === S.firm) || firms[0];
  const m = (v) => (v === 'none' ? 'none' : ok(v) ? usd(v) : '?');
  const rows = (f.plans || []).map((p) => `<tr><td>${esc(p.name)}</td><td>${m(p.target)}</td><td>${m(p.dd)} ${esc(p.dd_type || '?')}</td>
    <td>${m(p.dll)} ${esc(p.dll_type && p.dll_type !== 'none' ? p.dll_type : '')}</td><td>${p.micros ?? '?'}</td>
    <td>${p.cons === 'none' ? 'none' : ok(p.cons) ? Math.round(p.cons * 100) + '%' : '?'}</td><td>${p.price ? usd(p.price) + ' (yours)' : '—'}</td>
    <td>${esc(p.verified)} / ${esc(p.unknown)}</td></tr>`).join('');
  return `<div class="card nx-glass"><div class="card-h"><h3>Firm rules</h3><div class="card-tools">${firms.map((x) => `<button class="nx-chip" data-firm="${esc(x.id)}">${esc(x.name)}</button>`).join(' ')}</div></div>
    <p class="muted">${esc(f.name)}: bots ${esc(f.bots ?? 'unknown')}, hedging ${esc(f.hedging ?? 'unknown')}, NinjaTrader ${f.ninjatrader === false ? 'not offered' : f.ninjatrader ? 'yes' : 'unknown'}${f.flat_by ? `, flat by ${esc(f.flat_by)} ET` : ''}.
    "?" = unknown (never guessed); verified / unknown = how many of the plan's values the repo's research confirmed. Prices: only yours.</p>
    <table class="nx-vtbl"><thead><tr><th>Plan</th><th>Target</th><th>Max loss</th><th>Daily loss</th><th>Micros</th><th>Best day</th><th>Price</th><th>Verified / unknown</th></tr></thead><tbody>${rows}</tbody></table></div>`;
}

async function draw() {
  const el = $('#page-fleet'); if (!el) return;
  let d = S.d;
  try { const r = await fetch('/api/next/fleet'); d = await r.json(); S.d = d; } catch (e) { if (!d) { el.innerHTML = `<p class="muted">${esc(e.message)}</p>`; return; } }
  if (!active()) return;
  const acc = d.accounts || [];
  const T = d.totals || {};
  const head = `<header class="nx-hero cc-hero"><div><div class="nx-eyebrow">Accounts · copy trading</div><h2>Fleet</h2>
    <p class="muted">${acc.length ? 'Every follower account copies its lead (Zlarior / ATLAS / BLITZ), sized from its own room and its firm\'s rules, never opposite another of your accounts.' : 'Off: no follower accounts yet. Add one in 3 steps below.'} Refreshes every 15 s.</p></div></header>`;
  const kill = d.kill ? `<div class="card nx-glass"><div class="card-h"><h3>FLEET KILL ON</h3></div><p class="muted">Every follower is flat and copies nothing. <code>python -X utf8 -m engine.fleet --unkill all</code></p></div>` : '';
  const tot = acc.length ? `<div class="nx-kv">${stat('Followers', esc(acc.length), `${esc(T.open || 0)} open now`)}${stat('Today, all', susd(T.today), '', tone(T.today))}${stat('This week, all', susd(T.week), '', tone(T.week))}${stat('Passed / failed', `${esc(T.passed || 0)} / ${esc(T.failed || 0)}`, T.live ? `${esc(T.live)} real / LIVE` : 'paper / Sim')}</div>` : '';
  const leads = (d.leads || []).length ? `<div class="card nx-glass"><div class="card-h"><h3>Leads</h3></div><p class="muted">${(d.leads || []).map((l) => `${esc(l.name)} (${esc(l.account || '')}, ${esc(l.plan || '')}): ${l.open ? esc(l.open.side + ' ' + l.open.qty) : 'flat'}`).join(' · ')}</p></div>` : '';
  const notes = (d.notes || []).length ? `<div class="card nx-glass"><div class="card-h"><h3>Fleet notices</h3></div>${(d.notes || []).slice(-8).reverse().map((n) => `<p class="muted"><b>${esc(n.title)}</b> ${esc(n.body)}</p>`).join('')}</div>` : '';
  el.innerHTML = head + kill + tot + leads + acc.map(card).join('') + notes
    + `<div class="card nx-glass"><div class="card-h"><h3>Add an account</h3></div>${STEPS}</div>` + catalog(d.firms);
  el.querySelectorAll('[data-firm]').forEach((b) => b.addEventListener('click', () => { S.firm = b.dataset.firm; draw(); }));
}

export const fleet = {
  show: () => {
    draw();
    clearInterval(S.timer);
    S.timer = setInterval(() => { if (active()) draw(); else clearInterval(S.timer); }, 15000);
  },
};
