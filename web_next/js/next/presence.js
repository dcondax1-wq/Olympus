// Bot page: "I'm here" check-in, pause new entries, weekly hands-off score, presence log (engine/presence_api.py).
//   GET /api/next/presence, /api/next/handsoff; POST /api/next/presence/checkin|checkout, /api/next/pause, /api/next/pause/clear
// Files only on the PC: nothing here starts, arms or sizes a trade; a pause only blocks NEW entries.
import { api, esc, toast } from '../util.js';

const P = { at: 0, pr: null, ho: null, busy: false };
const card = (title, body, tools = '') => `<section class="card nx-glass bc-card"><div class="card-h"><h3>${title}</h3>${tools ? `<div class="card-tools">${tools}</div>` : ''}</div>${body}</section>`;
const usd = (v) => (v == null ? '' : `${v < 0 ? '-' : '+'}$${Math.abs(Math.round(v)).toLocaleString('en-US')}`);
const CSS = `.pz-row{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:8px 0}
.pz-big{font:700 15px var(--sans);padding:12px 22px;border-radius:12px}
.pz-line{font:600 14px var(--sans);margin:4px 0 2px}.pz-mut{color:var(--muted);font-size:12.5px}
.pz-score{font:750 40px var(--sans);line-height:1}.pz-ok{color:var(--good,#3ecf8e)}.pz-warn{color:var(--warn,#e9b44c)}.pz-bad{color:var(--bad,#ff6b6b)}
.pz-list{display:flex;flex-direction:column;gap:6px;margin-top:10px}.pz-item{display:grid;grid-template-columns:auto 1fr auto;gap:8px;font-size:13px;align-items:baseline}
.pz-item small{grid-column:2/4;color:var(--muted)}.pz-weeks{display:flex;gap:10px;flex-wrap:wrap;margin-top:10px;font-size:12.5px;color:var(--muted)}
.pz-tab{width:100%;border-collapse:collapse;font-size:12.5px}.pz-tab td,.pz-tab th{padding:4px 6px;border-bottom:1px solid var(--line,#2a2f3a);text-align:left}
.pz-in{background:transparent;color:var(--ink);border:1px solid var(--line,#2a2f3a);border-radius:8px;padding:6px 8px}`;

function scoreCls(s) { return s >= 80 ? 'pz-ok' : s >= 50 ? 'pz-warn' : 'pz-bad'; }

function deskHTML(pr) {
  const st = pr?.status || {}, pz = pr?.pause;
  return card("I'm at the desk", `
    <div class="pz-line">${esc(st.line || 'Not checked in yet')}</div>
    <div class="pz-mut">MFFU wants you watching while the bot trades. A check-in lasts ${st.hours || 4} h. Guard <b>presence_required</b>: ${st.guard ? 'ON (no new entry without a check-in)' : 'OFF (log only)'}.</div>
    <div class="pz-row"><button type="button" class="btn primary pz-big" data-pz="in">I'm here</button>
      <button type="button" class="btn ghost" data-pz="out">I'm leaving</button></div>
    <div class="pz-line" style="margin-top:12px">${pz ? `New entries paused until ${esc(pz.label || '')}` : 'New entries: allowed'}</div>
    <div class="pz-mut">A pause blocks new entries only; an open trade keeps its stop and target.</div>
    <div class="pz-row">${pz ? '<button type="button" class="btn primary" data-pz="resume">Resume entries</button>' : ''}
      <button type="button" class="btn ghost" data-pz="tomorrow">Pause until tomorrow</button>
      <input type="time" class="pz-in" id="pzTime" value="10:00" aria-label="pause until (New York time)">
      <button type="button" class="btn ghost" data-pz="until">Pause until this time (ET)</button></div>`);
}

function scoreHTML(ho) {
  const w = (ho?.weeks || [])[0];
  if (!w) return card('Hands-off score', '<div class="pc-empty"><b>No data yet.</b></div>');
  const items = w.events.slice().reverse().map((i) => `<div class="pz-item"><span class="pz-mut">${esc(i.when)}</span><b>${esc(i.label)}</b>
      <span class="${i.points ? 'pz-bad' : 'pz-mut'}">-${i.points}</span><small>${esc(i.detail ? i.detail + ' · ' : '')}${esc(i.note || '')}${i.usd != null ? ` (${usd(i.usd)})` : ''}</small></div>`).join('');
  const prev = (ho.weeks || []).slice(1).map((x) => `<span>${esc(x.label)}: <b class="${scoreCls(x.score)}">${x.score}</b>${x.n ? ` (${x.n})` : ''}</span>`).join('');
  return card('Hands-off score · this week', `
    <div class="pz-row"><span class="pz-score ${scoreCls(w.score)}">${w.score}</span><span><b>${esc(w.verdict)}</b><br><span class="pz-mut">${esc(w.label)} · 100 minus points each time a person stepped in${w.usd != null ? ` · cost vs backtest ${usd(w.usd)}` : ''}</span></span></div>
    <div class="pz-list">${items || '<div class="pz-mut">No manual trades, closes, kills, stops, pauses, settings changes or hand restarts this week.</div>'}</div>
    ${prev ? `<div class="pz-weeks">${prev}</div>` : ''}`);
}

function logHTML(pr) {
  const s = pr?.summary || {}, tr = pr?.trades || [], ws = pr?.windows || [];
  const rows = tr.slice(0, 20).map((t) => `<tr><td>${esc(t.time)}</td><td>${esc(t.side)} ${esc(t.qty ?? '')}</td>
      <td class="${t.present ? 'pz-ok' : 'pz-warn'}">${t.present ? 'present' : 'not checked in'}</td><td>${t.overlap_min} of ${t.trade_min} min</td></tr>`).join('');
  const wins = ws.slice(0, 12).map((w) => `<tr><td>${esc(w.label)}</td><td>${esc(w.src)}</td><td>${w.minutes} min</td><td>${w.open ? 'now' : esc(w.ended || '')}</td></tr>`).join('');
  return card('Presence log', `
    <div class="pz-line">${esc(s.line || '')}</div><div class="pz-mut">Last ${pr?.days || 14} days · ${s.present_h ?? 0} h checked in</div>
    <table class="pz-tab" style="margin-top:8px"><tr><th>Bot trade</th><th>Side</th><th>You</th><th>Overlap</th></tr>${rows || '<tr><td colspan="4" class="pz-mut">No bot trades in this period.</td></tr>'}</table>
    <table class="pz-tab" style="margin-top:12px"><tr><th>Checked in</th><th>From</th><th>Length</th><th>Ended</th></tr>${wins || '<tr><td colspan="4" class="pz-mut">No check-ins yet.</td></tr>'}</table>`);
}

async function load(force) {
  if (!force && Date.now() - P.at < 20000 && P.pr) return;
  P.at = Date.now();
  const [pr, ho] = await Promise.all([api('/api/next/presence').catch(() => null), api('/api/next/handsoff').catch(() => null)]);
  P.pr = pr; P.ho = ho;
}

async function act(el, what) {
  if (P.busy) return;
  P.busy = true;
  try {
    if (what === 'in') { const r = await api('/api/next/presence/checkin', {}); toast(r.status?.line || 'Checked in'); }
    else if (what === 'out') { await api('/api/next/presence/checkout', {}); toast('Checked out'); }
    else if (what === 'resume') { await api('/api/next/pause/clear', {}); toast('New entries allowed again'); }
    else if (what === 'tomorrow' || what === 'until') {
      const until = what === 'tomorrow' ? 'tomorrow' : (el.querySelector('#pzTime')?.value || '');
      const r = await api('/api/next/pause', { until }); toast(`No new entries until ${r.label}`);
    }
  } catch (e) { toast(String(e.message || e), 4000); }
  P.busy = false;
  await mount(el, true);
}

export async function mount(el, force = false) {
  if (!el) return;
  if (!document.getElementById('pzCss')) { const s = document.createElement('style'); s.id = 'pzCss'; s.textContent = CSS; document.head.appendChild(s); }
  await load(force);
  if (el.contains(document.activeElement) && document.activeElement.id === 'pzTime') return;   // do not wipe the time being typed
  const html = `<div class="bc-grid3">${deskHTML(P.pr)}${scoreHTML(P.ho)}${logHTML(P.pr)}</div>`;
  if (el._h === html) return;
  el._h = html;
  el.innerHTML = html;
  el.onclick = (e) => { const b = e.target.closest('[data-pz]'); if (b) act(el, b.dataset.pz); };
}
