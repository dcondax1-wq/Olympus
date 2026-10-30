// PC dashboard: the Fleet (2026-10-30, copy trading to the follower accounts).
//   #fleet   every follower (engine/fleet.py): firm + plan, stage (eval / funded / LIVE), status, balance, room to the firm's
//            floor (EOD / intraday trailing the firm's way), daily loss left, $ to the target, today / this week, the open
//            copy, slippage vs the lead's fill, the last copy it skipped and why, rule warnings (unverified / unknown values);
//            the leads' own accounts; the fleet kill flag; the firm catalog (plans, verified / unknown counts, the owner's
//            prices only); "Add an account" (the 3 steps + a form) and per-account buttons Off / On, Kill / Un-kill,
//            Passed -> funded, Record a payout, Remove, and Kill ALL.
// Data: GET /api/next/fleet (engine/fleet_api.py), every 15 s while the page is open. Buttons: POST /api/next/fleet/set (the
// CLI engine/fleet.run on data/fleet.json; PC only, cloud-blocked). Nothing here ARMS an account: a real account is armed
// in the console (--arm) and still needs the typed phrase at the bot's start + NINJATRADER_LIVE=1.
import { $, esc } from '../util.js';

(function ensure() {
  if (!document.getElementById('page-fleet')) {
    const ref = document.getElementById('page-cc') || document.querySelector('section.page');
    const s = document.createElement('section'); s.className = 'page'; s.id = 'page-fleet';
    s.innerHTML = '<div class="empty">Loading the fleet…</div>';
    if (ref?.parentNode) ref.parentNode.insertBefore(s, ref.nextSibling); else document.body.appendChild(s);
  }
})();

const S = { timer: null, d: null, firm: null, msg: '', busy: false, formOpen: false };
const active = () => document.getElementById('page-fleet')?.classList.contains('active');
const ok = (v) => v !== null && v !== undefined && v !== '' && !Number.isNaN(+v);
const usd = (v) => (!ok(v) ? '—' : (+v < 0 ? '−$' : '$') + Math.abs(+v).toLocaleString('en-US', { maximumFractionDigits: 0 }));
const susd = (v) => (!ok(v) ? '—' : (+v > 0 ? '+' : '') + usd(v));
const tone = (v) => (+v > 0 ? 'good' : +v < 0 ? 'bad' : '');
const stat = (label, value, sub = '', k = '') => `<div class="nx-stat"><span>${esc(label)}</span><b class="${k}">${value}</b>${sub ? `<em>${sub}</em>` : ''}</div>`;
const WRAP = ' style="white-space:normal;height:auto;min-height:24px;padding:3px 9px;max-width:100%"';   // long warnings wrap on a phone-width window
const STATUS = { running: ['Running', ''], passed: ['EVAL PASSED', 'good'], failed: ['FAILED', 'bad'], killed: ['KILLED', 'bad'], off: ['Off', ''], 'not running': ['Bot not running', ''] };
const STEPS = `<ol class="muted"><li>Buy the account (your own price + the firm's current code; never the list price).</li>
  <li>Log it in NinjaTrader 8 (its Name shows in the Accounts tab); test it on Sim first.</li>
  <li>Fill in the form below (or one line on this PC: <code>python -X utf8 -m engine.fleet --add --id &lt;id&gt; --lead zlarior --plan &lt;plan&gt; --account "&lt;Name&gt;" --start &lt;day&gt;</code>).</li></ol>
  <p class="muted">Nothing here arms an account: a real account copies only after <code>python -X utf8 -m engine.fleet --arm &lt;id&gt;</code> AND the live phrase at the bot's start. Step by step: docs/ADD_ACCOUNT.md.</p>`;

async function post(body, confirmText) {
  if (S.busy) return;
  if (confirmText && !window.confirm(confirmText)) return;
  S.busy = true;
  try {
    const r = await fetch('/api/next/fleet/set', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) });
    const d = await r.json().catch(() => ({}));
    S.msg = d.ok ? (d.out || 'Saved.') : `Not saved: ${d.error || d.out || 'HTTP ' + r.status}`;
  } catch (e) { S.msg = `Not saved: ${e.message}`; }
  S.busy = false;
  draw();
}

function buttons(a) {
  const b = (act, label, extra = '') => `<button class="nx-chip" data-act="${esc(act)}" data-id="${esc(a.id)}"${extra}>${esc(label)}</button>`;
  return [a.status === 'off' ? b('on', 'Switch on') : b('off', 'Switch off'),
    a.status === 'killed' ? b('unkill', 'Un-kill') : b('kill', 'Kill (flatten now)'),
    a.stage === 'eval' ? b('to_funded', 'Passed → funded') : '', a.stage === 'funded' ? b('payout', 'Record a payout') : '',
    b('remove', 'Remove')].join(' ');
}

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
    ok(a.slip_ticks) ? `<span class="nx-chip"${WRAP}>slippage vs lead ${+a.slip_ticks > 0 ? '+' : ''}${esc(a.slip_ticks)} ticks (${esc(a.slip_n)})</span>` : '',
    a.stagger_ms ? `<span class="nx-chip">stagger ${esc(a.stagger_ms)} ms</span>` : '',
    a.unknown && a.unknown.length ? `<span class="nx-chip warn"${WRAP}>unknown rules: ${esc(a.unknown.slice(0, 4).join(', '))}</span>` : '',
  ].join('');
  const sz = a.size ? `<p class="muted">Last size: ${esc(a.size.qty)} micros (lead ${esc(a.size.lead_qty)}) · ${esc((a.size.reasons || []).slice(-1)[0] || '')}</p>` : '';
  const sk = a.last_skip ? `<p class="muted">Last copy skipped: ${esc(a.last_skip.why)}</p>` : '';
  const warn = (a.warn || []).map((w) => `<span class="nx-chip warn"${WRAP}>${esc(w)}</span>`).join(' ');
  return `<div class="card nx-glass fx-card"><div class="card-h"><h3>${esc(a.name || a.id)} <span class="nx-badge ${lab === 'LIVE' || lab === 'REAL' ? 'bad' : ''}">${esc(lab)}</span></h3>
    <div class="card-tools"><span class="nx-badge ${st[1]}">${esc(st[0])}</span></div></div>
    <p class="muted">${esc(a.firm || '')} ${esc(a.plan || '')} · ${esc(isLive ? 'LIVE account' : a.stage === 'funded' ? 'funded' : 'eval')} · copies ${esc(a.lead_name || a.lead)}${a.nt_account ? ` · ${esc(a.nt_account)}` : ''}${a.why ? ` · ${esc(a.why)}` : ''}</p>
    <div class="nx-kv">${tiles}</div><div>${chips}</div>${sz}${sk}${warn ? `<div>${warn}</div>` : ''}<div>${buttons(a)}</div></div>`;
}

function form(firms) {
  const opts = ['<option value="live">My own LIVE account (no prop firm)</option>'].concat((firms || []).flatMap((f) => (f.plans || []).map((p) =>
    `<option value="${esc(p.id)}">${esc(f.name)} ${esc(p.name)}${f.bots === 'prohibited' || f.ninjatrader === false || f.bots === 'semi_only' ? ' (paper only: no bot / no NinjaTrader)' : ''}</option>`))).join('');
  const today = new Date().toISOString().slice(0, 10);
  const inp = (k, label, type = 'text', ph = '', val = '') => `<label class="nx-stat"><span>${esc(label)}</span><input data-f="${esc(k)}" type="${type}" placeholder="${esc(ph)}" value="${esc(val)}"></label>`;
  return `<details class="card nx-glass"${S.formOpen ? ' open' : ''} data-form><summary class="card-h"><h3>Add an account</h3></summary>${STEPS}
    <div class="nx-kv">${inp('id', 'Short id', 'text', 'lucid50k')}${inp('name', 'Display name', 'text', 'Lucid 50K')}
      <label class="nx-stat"><span>Copies</span><select data-f="lead"><option value="zlarior">Zlarior (LIT)</option><option value="atlas">ATLAS</option><option value="blitz">BLITZ</option></select></label>
      <label class="nx-stat"><span>Firm + plan</span><select data-f="plan">${opts}</select></label>
      ${inp('account', 'NinjaTrader Name (empty = paper)', 'text', 'Sim102')}${inp('start', 'First day', 'date', '', today)}
      ${inp('balance', 'Live: start balance $', 'number', '10000')}${inp('max_risk', 'Live: max $ a trade', 'number', '150')}
      ${inp('daily_stop', 'Live: daily stop $', 'number', '300')}${inp('weekly_stop', 'Live: weekly stop $', 'number', '600')}
      ${inp('max_micros', 'Live: max micros', 'number', '5')}${inp('stagger_ms', 'Stagger (ms)', 'number', '0')}</div>
    <p><button class="nx-chip" data-add>Add it (not armed)</button></p></details>`;
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

function wire(el) {
  el.querySelectorAll('[data-firm]').forEach((b) => b.addEventListener('click', () => { S.firm = b.dataset.firm; draw(); }));
  const fm = el.querySelector('[data-form]');
  if (fm) fm.addEventListener('toggle', () => { S.formOpen = fm.open; });
  el.querySelectorAll('[data-act]').forEach((b) => b.addEventListener('click', () => {
    const id = b.dataset.id, act = b.dataset.act;
    if (act === 'to_funded') {
      const account = window.prompt('The FUNDED account\'s NinjaTrader Name (the firm gives a new one; empty = keep):', '') ?? null;
      if (account === null) return;
      const start = window.prompt('First funded session (yyyy-mm-dd):', new Date().toISOString().slice(0, 10));
      if (!start) return;
      post({ action: act, id, account, start });
      return;
    }
    if (act === 'payout') {
      const usdv = window.prompt('Payout amount ($) the firm paid:', '');
      if (!usdv) return;
      const day = window.prompt('Day of the payout (yyyy-mm-dd):', new Date().toISOString().slice(0, 10));
      if (!day) return;
      post({ action: act, id, usd: usdv, day });
      return;
    }
    const ask = { kill: `Kill ${id}? Its open copy is closed at market at the next poll and it takes no new copy.`, remove: `Remove ${id} from the fleet?`,
      off: `Switch ${id} off (no new copy; an open one is still managed)?` }[act];
    post({ action: act, id }, ask);
  }));
  const kb = el.querySelector('[data-killall]');
  if (kb) kb.addEventListener('click', () => post({ action: kb.dataset.killall, id: 'all' }, kb.dataset.killall === 'kill' ? 'Kill EVERY follower? All copies are closed at market at the next poll.' : null));
  const add = el.querySelector('[data-add]');
  if (add) add.addEventListener('click', () => {
    const v = {};
    el.querySelectorAll('[data-f]').forEach((x) => { v[x.dataset.f] = x.value; });
    if (v.plan !== 'live') ['balance', 'max_risk', 'daily_stop', 'weekly_stop', 'max_micros'].forEach((k) => delete v[k]);
    post({ action: 'add', ...v }, `Add ${v.id || '?'} (${v.plan}) copying ${v.lead}${v.account ? ` on ${v.account}` : ' on paper'}? It is NOT armed.`);
  });
}

async function draw() {
  const el = $('#page-fleet'); if (!el) return;
  let d = S.d;
  try { const r = await fetch('/api/next/fleet'); d = await r.json(); S.d = d; } catch (e) { if (!d) { el.innerHTML = `<p class="muted">${esc(e.message)}</p>`; return; } }
  if (!active()) return;
  if (el.contains(document.activeElement) && document.activeElement && document.activeElement.matches && document.activeElement.matches('input,select')) return;   // never redraw under the owner's typing
  const acc = d.accounts || [];
  const T = d.totals || {};
  const head = `<header class="nx-hero cc-hero"><div><div class="nx-eyebrow">Accounts · copy trading</div><h2>Fleet</h2>
    <p class="muted">${acc.length ? 'Every follower account copies its lead (Zlarior / ATLAS / BLITZ), sized from its own room and its firm\'s rules, never opposite another of your accounts.' : 'Off: no follower accounts yet. Add one in 3 steps below.'} Refreshes every 15 s.</p></div>
    ${acc.length ? `<div class="hero-r"><button class="nx-chip warn" data-killall="${d.kill ? 'unkill' : 'kill'}">${d.kill ? 'Un-kill the fleet' : 'Kill ALL followers'}</button></div>` : ''}</header>`;
  const msg = S.msg ? `<div class="card nx-glass"><p class="muted">${esc(S.msg).replace(/\n/g, '<br>')}</p></div>` : '';
  const kill = d.kill ? `<div class="card nx-glass"><div class="card-h"><h3>FLEET KILL ON</h3></div><p class="muted">Every follower is flat and copies nothing.</p></div>` : '';
  const warns = (d.warnings || []).length ? `<div class="card nx-glass"><div class="card-h"><h3>Rule warnings</h3></div>${d.warnings.map((w) => `<span class="nx-chip warn"${WRAP}>${esc(w)}</span>`).join(' ')}</div>` : '';
  const tot = acc.length ? `<div class="nx-kv">${stat('Followers', esc(acc.length), `${esc(T.open || 0)} open now`)}${stat('Today, all', susd(T.today), '', tone(T.today))}${stat('This week, all', susd(T.week), '', tone(T.week))}${stat('Passed / failed', `${esc(T.passed || 0)} / ${esc(T.failed || 0)}`, T.live ? `${esc(T.live)} real / LIVE` : 'paper / Sim')}</div>` : '';
  const leads = (d.leads || []).length ? `<div class="card nx-glass"><div class="card-h"><h3>Leads</h3></div><p class="muted">${(d.leads || []).map((l) => `${esc(l.name)} (${esc(l.account || '')}, ${esc(l.plan || '')}): ${l.open ? esc(l.open.side + ' ' + l.open.qty) : 'flat'}`).join(' · ')}</p></div>` : '';
  const notes = (d.notes || []).length ? `<div class="card nx-glass"><div class="card-h"><h3>Fleet notices</h3></div>${(d.notes || []).slice(-8).reverse().map((n) => `<p class="muted"><b>${esc(n.title)}</b> ${esc(n.body)}</p>`).join('')}</div>` : '';
  el.innerHTML = head + msg + kill + warns + tot + leads + acc.map(card).join('') + notes + form(d.firms) + catalog(d.firms);
  wire(el);
}

export const fleet = {
  show: () => {
    draw();
    clearInterval(S.timer);
    S.timer = setInterval(() => { if (active()) draw(); else clearInterval(S.timer); }, 15000);
  },
};
