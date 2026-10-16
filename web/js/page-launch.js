// Launch Control: countdown to the CME Globex reopen (Sunday 18:00 ET), launch checklist with live status,
// "Send test webhook" to the bridge's PAPER URL, and the TradingView alerts this server has received.
// Live orders run TradingView Pine strategy -> webhook bridge (TradersPost / PickMyTrade) -> MFFU Tradovate account,
// so they do not depend on this PC. The Python paper bot here mirrors the same strategy for monitoring.
import { $, $$, esc, api, toast, store, etParts, etOffset, etStr, fmtN } from './util.js';
import { S } from './state.js';
import { sessionAt } from './app.js';

const TICKS_KEY = 'launch.ticks';
let snap = null, lst = null, blk = null, tv = null, built = false, lastLoad = 0;
let hookUrl = '';                        // bridge PAPER webhook URL: memory only, never stored

const CSS = `
#page-launch .lc-hero { display:flex; flex-wrap:wrap; align-items:center; justify-content:space-between; gap:12px; }
#page-launch .lc-count { font-family: var(--mono, 'JetBrains Mono', monospace); font-size: 34px; font-weight: 700; letter-spacing: .5px; line-height: 1.1; }
#page-launch .lc-go { font-size: 15px; padding: 6px 14px; }
#page-launch .lc-row { display:grid; grid-template-columns: 14px minmax(0,1fr) auto; gap: 10px; align-items:start; padding: 10px 4px; border-bottom: 1px solid var(--edge, rgba(255,255,255,.06)); }
#page-launch .lc-row:last-child { border-bottom: 0; }
#page-launch .lc-dot { width: 12px; height: 12px; border-radius: 50%; margin-top: 4px; background: var(--muted); }
#page-launch .lc-dot.good { background: var(--good); box-shadow: 0 0 0 3px color-mix(in srgb, var(--good) 22%, transparent); }
#page-launch .lc-dot.warn { background: var(--warn); box-shadow: 0 0 0 3px color-mix(in srgb, var(--warn) 22%, transparent); }
#page-launch .lc-dot.bad  { background: var(--bad);  box-shadow: 0 0 0 3px color-mix(in srgb, var(--bad) 22%, transparent); }
#page-launch .lc-t { font-weight: 600; }
#page-launch .lc-s { font-size: 12px; margin-left: 6px; }
#page-launch .lc-s.good { color: var(--good-ink, var(--good)); } #page-launch .lc-s.warn { color: var(--warn); } #page-launch .lc-s.bad { color: var(--bad); }
#page-launch .lc-do { font-size: 12.5px; color: var(--ink-2); margin-top: 3px; line-height: 1.5; }
#page-launch .lc-tick { display:flex; align-items:center; gap:6px; font-size: 12.5px; white-space: nowrap; cursor: pointer; }
#page-launch .lc-tick input { width: 18px; height: 18px; accent-color: var(--accent); }
#page-launch .lc-pre { max-height: 160px; overflow: auto; white-space: pre-wrap; }
#page-launch textarea.inp { width: 100%; min-height: 150px; font-family: var(--mono, 'JetBrains Mono', monospace); font-size: 12px; resize: vertical; box-sizing: border-box; }
#page-launch .pill.warn { color: var(--warn); border-color: color-mix(in srgb, var(--warn) 45%, transparent); background: color-mix(in srgb, var(--warn) 9%, transparent); }
@media (max-width: 760px) {
  #page-launch .lc-row { grid-template-columns: 14px minmax(0,1fr); }
  #page-launch .lc-row .lc-tick { grid-column: 2; }
  #page-launch .lc-count { font-size: 26px; }
}`;

function injectCss() {
  if (document.getElementById('lc-css')) return;
  const st = document.createElement('style');
  st.id = 'lc-css'; st.textContent = CSS;
  document.head.appendChild(st);
}

// ---------- manual ticks (localStorage via store(), which already wraps every access in try/catch)
function ticks() { try { const t = store.get(TICKS_KEY, {}); return t && typeof t === 'object' ? t : {}; } catch { return {}; } }
function setTick(id, on) {
  try { const t = ticks(); if (on) t[id] = Math.floor(Date.now() / 1000); else delete t[id]; store.set(TICKS_KEY, t); } catch { /* storage blocked */ }
}

// ---------- time
const now = () => Date.now() / 1000;
function dowOf(p) { return new Date(Date.UTC(p.y, p.mo - 1, p.d)).getUTCDay(); }
export function nextReopen(t = now()) {
  const p = etParts(t);
  const add = (7 - dowOf(p)) % 7;
  for (let k = 0; k < 3; k++) {
    const wall = Date.UTC(p.y, p.mo - 1, p.d + add + 7 * k, 18, 0, 0) / 1000;   // Sunday 18:00 ET as if it were UTC
    const utc = wall - etOffset(wall);
    if (utc > t) return utc;
  }
  return null;
}
function marketOpen(t = now()) {
  const p = etParts(t);
  return sessionAt(p.h * 60 + p.mi, dowOf(p))[0] !== 'Market closed';
}
function dur(s) {
  s = Math.max(0, Math.floor(s));
  const d = Math.floor(s / 86400), h = Math.floor(s % 86400 / 3600), m = Math.floor(s % 3600 / 60), x = s % 60;
  return `${d ? d + 'd ' : ''}${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(x).padStart(2, '0')}`;
}
function age(s) { return s == null ? '—' : s >= 7200 ? `${Math.round(s / 3600)} h` : s >= 120 ? `${Math.round(s / 60)} min` : `${Math.round(s)} s`; }
function etLong(t) {
  const p = etParts(t);
  const d = new Date(Date.UTC(p.y, p.mo - 1, p.d));
  const wd = d.toLocaleDateString('en-US', { weekday: 'long', timeZone: 'UTC' }), md = d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', timeZone: 'UTC' });
  const h12 = ((p.h + 11) % 12) + 1;
  return `${wd} ${md} · ${h12}:${String(p.mi).padStart(2, '0')} ${p.h < 12 ? 'AM' : 'PM'} ET`;
}

// ---------- checklist model
const MANUAL = [
  { id: 'tv2fa', title: 'TradingView 2FA is on',
    todo: 'TradingView → profile picture → Settings → Security → turn on two-factor authentication. TradingView only sends webhook alerts from accounts with 2FA.' },
  { id: 'pine', title: 'Pine strategy is on an MNQ1! 5-minute chart',
    todo: 'Open MNQ1! on a 5-minute chart, paste <span class="mono">tradingview/liquidity_engine.pine</span> (TradingView page → Copy Pine script) into the Pine Editor, Add to chart, then check the inputs (risk, max contracts) match what you want live.' },
  { id: 'alert', title: 'Alert created: message {{strategy.order.alert_message}} → bridge webhook',
    todo: 'Alerts → Create alert. Condition: the Liquidity Engine strategy. Message: exactly <span class="mono">{{strategy.order.alert_message}}</span> and nothing else. Notifications → Webhook URL: the bridge\'s URL. Expiration: open-ended. Keep the chart on MNQ1! 5m.' },
  { id: 'bridge', title: 'Bridge connected to the MFFU Tradovate account',
    todo: 'In TradersPost or PickMyTrade connect Tradovate with your MFFU login, pick the 50K account, map the symbol to MNQ and set a max quantity. Setup notes: <span class="mono">tradingview/BRIDGE_SETUP.md</span>.' },
  { id: 'paper', title: 'Bridge tested in paper / sim first',
    todo: 'Point the alert at the bridge\'s PAPER (sim) strategy first. Use "Send test webhook" below and confirm the paper order shows in the bridge with its stop and target. Only then switch the bridge to the live MFFU account.' },
];

function buildRows() {
  const t = ticks(), out = [];
  for (const m of MANUAL) out.push({ ...m, kind: 'manual', req: true, st: t[m.id] ? 'good' : 'warn', label: t[m.id] ? 'done' : 'to do', ticked: !!t[m.id] });

  // news blackout list -> Pine input
  {
    const tk = t.blackouts, present = blk?.present;
    const fresh = present && blk.mtime && now() - blk.mtime < 8 * 86400;
    const stale = present && tk && blk.mtime && blk.mtime > tk;      // a new list was written after the tick
    let st = 'warn', label = 'pending', todo;
    if (!present) {
      todo = 'Next week\'s list is not generated yet (<span class="mono">tradingview/blackouts.txt</span>). Status: <b>pending</b>. When it appears here, copy it into the Pine strategy\'s news blackout input.';
    } else {
      todo = `${blk.lines ?? 0} blackout time(s), file written ${blk.mtime ? etStr(blk.mtime, true) + ' ET' : '—'}: <span class="mono">${esc((blk.compact || '').slice(0, 160))}</span><br>
        <a class="link" href="#" id="lcCopyBlk">copy (one line)</a> · <a class="link" href="/api/launch/blackouts?raw=1" target="_blank" rel="noopener">full file with notes</a>, then paste into the Pine strategy's blackout input (Settings → Inputs) and save. Read the file's notes for FOMC days.`;
      if (!fresh) { st = 'bad'; label = 'list is old'; todo += ' The file is more than a week old: regenerate it for next week.'; }
      else if (tk && !stale) { st = 'good'; label = 'pasted'; }
      else { label = stale ? 'new list: paste again' : 'paste it'; }
    }
    out.push({ id: 'blackouts', title: 'Next week\'s news blackout list pasted into the Pine input', kind: 'manual', req: true, st, label, todo, ticked: !!tk && !stale });
  }

  // paper bot on this PC (auto)
  {
    const ad = snap?.cfg?.adapter || '';
    let st, label, todo;
    if (!snap) { st = 'bad'; label = 'server?'; todo = 'Could not read /api/live/state.'; }
    else if (snap.running && /live/i.test(ad)) { st = 'bad'; label = 'LIVE adapter'; todo = 'This PC\'s bot is on a LIVE adapter while the bridge already trades the MFFU account: that risks <b>duplicate orders</b>. Stop it and restart it in <b>paper</b> on the <a class="link" data-goto="live">Live Bot</a> page.'; }
    else if (snap.running && ad !== 'paper') { st = 'warn'; label = 'running · ' + ad; todo = 'The mirror should run on the <b>paper</b> adapter so it never touches the account the bridge trades.'; }
    else if (snap.running) { st = 'good'; label = 'running · paper'; todo = `Mirroring the strategy on paper since ${snap.started_at ? etStr(snap.started_at, true) + ' ET' : '—'}.`; }
    else { st = 'warn'; label = 'stopped'; todo = 'Optional but recommended: start the paper bot on the <a class="link" data-goto="live">Live Bot</a> page (adapter: Paper) to monitor and learn alongside the live strategy.'; }
    // a LIVE adapter here would double the bridge's orders on the same account: that one blocks the launch
    out.push({ id: 'paperbot', title: 'Paper bot running on this PC (mirror)', kind: 'auto', req: false, block: label === 'LIVE adapter', st, label, todo });
  }

  // feed freshness (auto)
  {
    const h = snap?.health || {}, a = h.data_age_s, open = marketOpen();
    let st, label, todo;
    if (!snap?.running) { st = 'warn'; label = 'no feed'; todo = 'The feed is read by the paper bot: start it to see data age.'; }
    else if (a == null) { st = 'warn'; label = 'waiting'; todo = 'No bar received yet.'; }
    else if (!open) { st = 'good'; label = 'market closed'; todo = `Last bar ${age(a)} old: normal while CME is closed. It should drop under 10 min after the Sunday 18:00 ET reopen.`; }
    else if (a > 600 || h.stale) { st = 'bad'; label = `stale · ${age(a)}`; todo = 'Market is open but bars are old. Check the internet connection and the Live Bot page log; restart the bot if it stays stale.'; }
    else { st = 'good'; label = `fresh · ${age(a)}`; todo = `Data source ${esc(h.data_source || '—')}.`; }
    out.push({ id: 'feed', title: 'Data feed fresh', kind: 'auto', req: false, st, label, todo });
  }

  // PC autostart (auto)
  {
    let st, label, todo;
    if (!lst) { st = 'warn'; label = 'unknown'; todo = 'Could not read /api/launch/status.'; }
    else if (!lst.status_ps1 && !lst.install_ps1) { st = 'warn'; label = 'not installed'; todo = 'Autostart scripts are not in <span class="mono">scripts/</span> yet. The live strategy does not need this PC; only the paper mirror does.'; }
    else {
      st = lst.task_installed === false ? 'warn' : 'good';
      label = lst.task_installed ? 'task installed' : lst.task_installed === false ? 'task not installed' : 'scripts present';
      todo = `${lst.task_installed === false ? 'Install once (PowerShell in the project folder): <span class="mono">powershell -ExecutionPolicy Bypass -File .\\scripts\\install_autostart.ps1</span><br>' : ''}Check any time: <span class="mono">powershell -ExecutionPolicy Bypass -File .\\scripts\\status.ps1</span>${lst.autostart_record ? ' · a resume record is saved, so the paper bot restarts after a reboot.' : ' · no resume record yet: start the paper bot once so a reboot can resume it.'}`;
    }
    out.push({ id: 'autostart', title: 'PC autostart for the paper mirror', kind: 'auto', req: false, st, label, todo });
  }

  // MFFU rules (manual acknowledgement)
  out.push({ id: 'mffu', title: 'MFFU rules understood', kind: 'manual', req: true, st: t.mffu ? 'good' : 'warn', label: t.mffu ? 'acknowledged' : 'read + tick', ticked: !!t.mffu,
    todo: 'Daily loss limit <b>$1,000 (soft)</b>: the day stops, the account survives. Max loss <b>$2,000 trailing, end of day</b>: hitting it ends the account. Automation is allowed only with the <b>owner present</b> and supervising during the session. Know how to flatten in the bridge and in Tradovate.' });
  return out;
}

function verdict(rows) {
  // required rows decide the launch; optional (mirror) rows only warn, except a blocking one (LIVE adapter on this PC)
  const bad = rows.filter(r => r.st === 'bad' && (r.req || r.block));
  const open = rows.filter(r => r.req && r.st !== 'good');
  const optRed = rows.filter(r => r.st === 'bad' && !r.req && !r.block).length;
  if (bad.length) return { go: false, text: `NO-GO · ${bad.length} red`, why: `Fix first: ${bad.map(r => r.title.split(':')[0]).join(' · ')}` };
  if (open.length) return { go: false, text: `NO-GO · ${open.length} open`, why: `Still to do: ${open.map(r => r.title.split(':')[0]).join(' · ')}` };
  return { go: true, text: 'GO', why: `All required items are green.${optRed ? ' The paper mirror on this PC needs attention, but live trading does not depend on it.' : ''} Watch the first session live.` };
}

// ---------- render
function skeleton() {
  $('#page-launch').innerHTML = `
    <div class="banner info">Live orders run <b>TradingView Pine strategy → webhook bridge (TradersPost / PickMyTrade) → MFFU Tradovate account</b>, so they keep working with this PC off. The paper bot on this PC mirrors the same strategy for monitoring and learning. Real CME futures data only.</div>
    <div class="grid cols-2">
      <div class="card"><div class="card-h"><h3>Countdown · CME Globex reopen</h3><span class="pill" id="lcMkt"></span></div>
        <div class="lc-hero"><div><div class="lc-count" id="lcCount">--:--:--</div><div class="muted small" id="lcWhen"></div></div></div>
        <div class="note">Futures reopen every Sunday 6:00 PM ET. The first fills of the week can be thin: the strategy's own session windows decide when it trades.</div></div>
      <div class="card"><div class="card-h"><h3>Go / No-go</h3><span class="pill lc-go" id="lcGo">…</span></div>
        <div id="lcGoWhy" class="small"></div>
        <div class="kv small" id="lcGoKv"></div>
        <div class="row gap" style="margin-top:8px"><button class="btn ghost sm" id="lcRefresh">⟳ Re-check</button><span class="muted small" id="lcAt"></span></div></div>
    </div>
    <div class="card" style="margin-bottom:14px"><div class="card-h"><h3>Launch checklist</h3><span class="muted small">ticks are saved in this browser only</span></div><div id="lcList"><div class="empty">Checking…</div></div></div>
    <div class="grid cols-2">
      <div class="card"><div class="card-h"><h3>Send test webhook · bridge PAPER URL</h3><span class="pill" id="lcTestState">idle</span></div>
        <ol class="tv-steps">
          <li>In the bridge, open the <b>paper / sim</b> strategy and copy its webhook URL.</li>
          <li>Paste it here. It stays in this page's memory only: never saved, never logged.</li>
          <li>Send. The server forwards the sample entry (1 MNQ buy with stop and target) and shows the bridge's answer.</li>
        </ol>
        <div class="banner warn" style="margin:8px 0">Use the <b>PAPER</b> webhook only. A live URL would place a real order on the funded account.</div>
        <input class="inp mono sm" id="lcUrl" type="text" autocomplete="off" autocapitalize="off" spellcheck="false" placeholder="https://… (bridge PAPER webhook URL)" style="width:100%;box-sizing:border-box">
        <div class="mini-label" style="margin:10px 0 4px">Payload (edit to match the bridge's format if needed)</div>
        <textarea class="inp" id="lcPayload" spellcheck="false"></textarea>
        <div class="row gap" style="margin-top:8px"><button class="btn primary sm" id="lcSend">Send test webhook</button><button class="btn ghost sm" id="lcReset">Reset sample</button><button class="btn ghost sm" id="lcForget">Forget URL</button></div>
        <div id="lcTestOut" style="margin-top:10px"></div></div>
      <div class="card"><div class="card-h"><h3>TradingView alerts received here</h3><span class="pill" id="lcHookState"></span></div>
        <div id="lcAlerts"><div class="empty">Loading…</div></div></div>
    </div>`;
  $('#lcRefresh').onclick = () => load(true);
  const u = $('#lcUrl');
  u.value = hookUrl;
  u.oninput = () => { hookUrl = u.value.trim(); };
  $('#lcForget').onclick = () => { hookUrl = ''; u.value = ''; toast('URL cleared from this page'); };
  $('#lcReset').onclick = () => { $('#lcPayload').value = JSON.stringify(lst?.sample || {}, null, 2); };
  $('#lcSend').onclick = sendTest;
  $('#lcList').addEventListener('change', (e) => {
    const cb = e.target.closest('input[data-tick]'); if (!cb) return;
    setTick(cb.dataset.tick, cb.checked); renderList();
  });
  $('#lcList').addEventListener('click', async (e) => {
    if (!e.target.closest('#lcCopyBlk')) return;
    e.preventDefault();
    try { await navigator.clipboard.writeText(blk?.compact ?? blk?.text ?? ''); toast('Blackout list copied: paste it into the Pine input'); } catch { toast('Copy blocked: open the full file and copy by hand'); }
  });
  built = true;
}

function renderCount() {
  if (!built) return;
  const t = now(), nx = nextReopen(t), open = marketOpen(t);
  $('#lcCount').textContent = nx ? 'T−' + dur(nx - t) : '—';
  $('#lcWhen').textContent = nx ? 'next reopen ' + etLong(nx) : '';
  const m = $('#lcMkt');
  m.textContent = open ? 'Globex OPEN' : 'market closed';
  m.className = 'pill ' + (open ? 'good' : '');
}

function renderList() {
  if (!built) return;
  const rows = buildRows();
  $('#lcList').innerHTML = rows.map(r => `<div class="lc-row">
      <span class="lc-dot ${r.st}" title="${r.st}"></span>
      <div><span class="lc-t">${esc(r.title)}</span><span class="lc-s ${r.st}">${esc(r.label)}</span>${r.req ? '' : ' <span class="muted small">· optional</span>'}
        <div class="lc-do">${r.todo}</div></div>
      ${r.kind === 'manual' ? `<label class="lc-tick"><input type="checkbox" data-tick="${r.id}" ${r.ticked ? 'checked' : ''}> done</label>` : '<span class="muted small">auto</span>'}
    </div>`).join('');
  const v = verdict(rows), g = $('#lcGo');
  g.textContent = v.text; g.className = 'pill lc-go ' + (v.go ? 'good' : 'bad');
  $('#lcGoWhy').textContent = v.why;
  const n = (s) => rows.filter(r => r.st === s).length;
  $('#lcGoKv').innerHTML = `<div><span class="muted">Green / amber / red</span><b class="mono">${n('good')} / ${n('warn')} / ${n('bad')}</b></div>
    <div><span class="muted">Required items done</span><b class="mono">${rows.filter(r => r.req && r.st === 'good').length} / ${rows.filter(r => r.req).length}</b></div>
    <div><span class="muted">Paper mirror</span><b class="mono">${snap?.running ? 'running · ' + esc(snap.cfg?.adapter || '') : 'stopped'}</b></div>`;
  $('#lcAt').textContent = lastLoad ? 'checked ' + etStr(lastLoad / 1000) + ' ET' : '';
}

function pick(b, ...keys) { for (const k of keys) if (b && b[k] != null && b[k] !== '') return b[k]; return null; }
function renderAlerts() {
  if (!built) return;
  const h = tv?.hook || {}, rec = h.recent || [];
  $('#lcHookState').textContent = rec.length ? `${rec.length} received` : 'none yet';
  const url = `${h.public_base || location.origin}/api/tv/webhook?key=${h.key || '…'}`;
  const num = (v) => { if (v == null) return '—'; if (typeof v === 'object') v = pick(v, 'stopPrice', 'limitPrice', 'price'); return v == null || isNaN(+v) ? esc(String(v ?? '—')) : fmtN(+v, 2); };
  const table = rec.length ? `<div class="table-wrap"><table class="tbl"><tr><th>Time (ET)</th><th>Action</th><th>Symbol</th><th>Qty</th><th>Price</th><th>Stop</th><th>Target</th></tr>
    ${rec.slice(0, 20).map(r => {
      const b = r.body && typeof r.body === 'object' ? r.body : {};
      const act = pick(b, 'action', 'event', 'side', 'sentiment') ?? (b.text ? String(b.text).slice(0, 40) : '—');
      return `<tr title="${esc(JSON.stringify(r.body ?? '').slice(0, 600))}"><td class="mono">${etStr(r.t, true).slice(5)}</td><td>${esc(String(act))}</td><td class="mono">${esc(String(pick(b, 'ticker', 'symbol') ?? '—'))}</td>
        <td class="mono">${esc(String(pick(b, 'quantity', 'qty', 'contracts') ?? '—'))}</td><td class="mono">${num(pick(b, 'price', 'close'))}</td>
        <td class="mono">${num(pick(b, 'stopLoss', 'stop', 'sl'))}</td><td class="mono">${num(pick(b, 'takeProfit', 'target', 'tp'))}</td></tr>`;
    }).join('')}</table></div>` : '<div class="empty">No TradingView alerts have reached this server since it started.</div>';
  $('#lcAlerts').innerHTML = `${table}
    <div class="note"><b>Optional mirror.</b> The live alert goes to the bridge and does not need this PC. To also see each live order here, add a <b>second alert</b> on the same strategy with the same message, pointing at this server's webhook. TradingView must reach this PC from the internet, so it needs a tunnel (Cloudflare Tunnel / ngrok): set its public URL on the <a class="link" data-goto="tv">TradingView page</a>. Without a tunnel this list stays empty, and that is fine.</div>
    <div class="row gap" style="margin-top:8px"><input class="inp mono sm" id="lcMyHook" value="${esc(url)}" readonly style="flex:1;min-width:0"><button class="btn ghost sm" id="lcMyHookCopy">Copy</button></div>
    <div class="muted small" style="margin-top:4px">${h.public_base ? 'Public base set.' : 'No public tunnel URL saved: TradingView cannot reach the address above.'} The key in the URL is the only credential: keep it private.</div>`;
  $('#lcMyHookCopy').onclick = async () => { try { await navigator.clipboard.writeText($('#lcMyHook').value); toast('Webhook URL copied'); } catch { toast('Copy blocked'); } };
}

async function sendTest() {
  const out = $('#lcTestOut'), pill = $('#lcTestState');
  const url = ($('#lcUrl').value || '').trim();
  hookUrl = url;
  if (!/^https:\/\/[^\s/]+/i.test(url)) { out.innerHTML = '<div class="note" style="color:var(--bad)">Paste the full https:// webhook URL first (http is refused).</div>'; return; }
  let payload;
  const raw = ($('#lcPayload').value || '').trim();
  // empty box -> the server sends its own sample entry
  try { payload = raw ? JSON.parse(raw) : null; } catch (e) { out.innerHTML = `<div class="note" style="color:var(--bad)">Payload is not valid JSON: ${esc(e.message)}</div>`; return; }
  if (!confirm('Send this sample entry (1 MNQ buy) to the pasted webhook URL?\n\nOnly continue if it is the bridge\'s PAPER / sim URL.')) return;
  pill.textContent = 'sending…'; pill.className = 'pill';
  $('#lcSend').disabled = true;
  try {
    const r = await fetch('/api/launch/test_webhook', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ url, payload }) });
    let j; try { j = await r.json(); } catch { j = { ok: false, error: `server answered HTTP ${r.status}` }; }
    const good = !!j.ok;
    pill.textContent = j.status != null ? `HTTP ${j.status}` : 'failed'; pill.className = 'pill ' + (good ? 'good' : 'bad');
    out.innerHTML = `<div class="kv small"><div><span class="muted">Bridge answered</span><b class="mono ${good ? 'up' : 'dn'}">${j.status != null ? 'HTTP ' + esc(j.status) : '—'}${j.elapsed_ms != null ? ' · ' + j.elapsed_ms + ' ms' : ''}</b></div></div>
      ${j.error ? `<div class="note" style="color:var(--bad)">${esc(j.error)}</div>` : ''}
      ${j.body != null ? `<div class="mini-label" style="margin:6px 0 4px">Response body</div><pre class="code sm lc-pre">${esc(j.body || '(empty)')}</pre>` : ''}
      <div class="note">${good ? 'Now check the bridge: the paper order should be listed with its stop and target. If the bridge shows an error, adjust the payload format to its documentation.' : 'Not accepted. Check the URL (paper strategy, copied in full) and the payload format the bridge expects.'}</div>`;
  } catch (e) {
    pill.textContent = 'failed'; pill.className = 'pill bad';
    out.innerHTML = `<div class="note" style="color:var(--bad)">${esc(e.message)}</div>`;
  } finally { $('#lcSend').disabled = false; }
}

async function load(force = false) {
  if (!force && Date.now() - lastLoad < 4000) return;
  lastLoad = Date.now();
  const get = (p) => api(p).catch(() => null);
  [snap, lst, blk, tv] = await Promise.all([get('/api/live/state'), get('/api/launch/status'), get('/api/launch/blackouts'), get('/api/tv/status')]);
  if (built && lst?.sample && !$('#lcPayload').value) $('#lcPayload').value = JSON.stringify(lst.sample, null, 2);
  renderList(); renderAlerts();
}

export function init() {
  injectCss();
  setInterval(() => { if (S.page === 'launch') renderCount(); }, 1000);
  setInterval(() => { if (S.page === 'launch' && !document.hidden) load(); }, 15000);
}
export async function show() {
  injectCss();
  if (!built) skeleton();
  renderCount();
  await load(true);
}
