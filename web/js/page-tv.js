import { $, esc, api, toast, busy } from './util.js';
import { S } from './state.js';
import { run } from './app.js';

let pine = '', status = null;

export function init() { }
export async function show() {
  try { status = await api('/api/tv/status'); } catch (e) { status = null; }
  render();
  if (!pine) {
    // /api/tv/pine returns plain text (not JSON), so read it as text
    try { const r = await fetch('/api/tv/pine'); pine = r.ok ? await r.text() : ''; } catch (e) { pine = ''; }
    renderPine();
  }
}

function render() {
  renderPine();
  renderImport();
  renderHook();
  renderKnows();
}

function renderPine() {
  $('#tvPine').innerHTML = `
    <ol class="tv-steps">
      <li>Open <b>MNQ1!</b> (or NQ1!) on a <b>5-minute</b> chart in TradingView.</li>
      <li>Open the <b>Pine Editor</b> (bottom of the chart), paste the script, press <b>Add to chart</b>.</li>
      <li>Open the <b>Strategy Tester</b> tab. On Premium plans use <b>Deep Backtesting</b> for multi-year history.</li>
      <li>Compare with the bot: same rules, same defaults, TradingView's fill model. Expect similar trades, not identical ones.</li>
    </ol>
    <div class="row gap" style="margin:8px 0"><button class="btn primary sm" id="tvCopy" ${pine ? '' : 'disabled'}>Copy Pine script</button>
      <a class="btn ghost sm" href="/api/tv/pine?download=1">Download .pine</a><span class="muted small">${pine ? pine.split('\n').length + ' lines · includes the giveback exit' : 'loading…'}</span></div>
    <pre class="code" id="tvPineCode">${esc(pine ? pine.slice(0, 1600) + (pine.length > 1600 ? '\n… (full script copies)' : '') : '')}</pre>`;
  $('#tvCopy').onclick = async () => {
    try { await navigator.clipboard.writeText(pine); toast('Pine script copied: paste it into the Pine Editor'); }
    catch (e) { toast('Copy blocked by the browser: use Download .pine'); }
  };
}

function renderImport() {
  const d = status?.data || {};
  const fmt = (k) => d[k] ? `${d[k].from} → ${d[k].to} · ${d[k].bars.toLocaleString()} bars` : 'none';
  $('#tvDataState').textContent = d.NQ ? `NQ 5m: ${d.NQ.days} days` : 'no NQ data';
  $('#tvImport').innerHTML = `
    <ol class="tv-steps">
      <li>On the MNQ1! / NQ1! <b>5-minute</b> chart, click the <b>⋯</b> (or ⌄) next to the chart name → <b>Export chart data…</b>.</li>
      <li>Time format <b>ISO</b>, then Export. Scroll the chart back first: TradingView exports only the bars it has loaded (up to ~20k).</li>
      <li>Pick the file here. Bars are merged into the bot's futures history; TradingView data wins on overlap. Repeat for more history.</li>
    </ol>
    <div class="row gap" style="margin:8px 0">
      <select class="sel sm" id="tvSym"><option value="NQ">NQ / MNQ → NQ</option><option value="ES">ES / MES → ES</option></select>
      <label class="btn primary sm" for="tvFile">Choose TradingView CSV…</label><input type="file" id="tvFile" accept=".csv,text/csv" style="display:none">
      <span class="muted small" id="tvImpMsg"></span></div>
    <div class="kv small"><div><span class="muted">NQ 5m in the bot</span><b class="mono">${fmt('NQ')}</b></div><div><span class="muted">ES 5m in the bot</span><b class="mono">${fmt('ES')}</b></div></div>
    <div class="note">After an import the backtest re-runs on the new history automatically. Yahoo's 60-day refresh never overwrites imported bars.</div>`;
  $('#tvFile').onchange = async (e) => {
    const f = e.target.files[0]; if (!f) return;
    const text = await f.text();
    const sym = $('#tvSym').value;
    $('#tvImpMsg').textContent = `importing ${f.name} (${Math.round(f.size / 1024)} KB)…`;
    busy(true);
    try {
      const r = await fetch(`/api/tv/import?sym=${sym}`, { method: 'POST', headers: { 'Content-Type': 'text/plain' }, body: text }).then(x => x.json());
      if (r.error) throw new Error(r.error);
      $('#tvImpMsg').textContent = `✓ ${r.rows.toLocaleString()} rows → ${r.bars_5m.toLocaleString()} five-minute bars (${r.from} → ${r.to})`;
      toast('TradingView data imported · re-running the backtest');
      try { status = await api('/api/tv/status'); } catch (_) { }
      renderImport(); renderKnows();
      await run();
    } catch (err) { $('#tvImpMsg').textContent = '✗ ' + err.message; }
    busy(false);
    e.target.value = '';
  };
}

function renderHook() {
  const h = status?.hook || {};
  $('#tvHookState').textContent = h.recent?.length ? `${h.recent.length} received` : 'waiting';
  const url = `${h.public_base || location.origin}/api/tv/webhook?key=${h.key || '…'}`;
  $('#tvHook').innerHTML = `
    <p class="small">TradingView alerts (Pine <code>alert()</code> calls or any alert with a webhook) land in the <b>Live Bot</b> feed and go out through your phone alerts. Use it to mirror TradingView signals next to the bot's own, or to feed its sweeps and IFVGs from TradingView's data.</p>
    <div class="note" style="margin-top:0">Live orders do <b>not</b> go through this PC: the Pine strategy's alert goes to the bridge (TradersPost / PickMyTrade) which trades the MFFU Tradovate account. This webhook is an <b>optional second alert</b> for monitoring only. See <a class="link" data-goto="launch">Launch Control</a>.</div>
    <div class="form-grid small">
      <span>Webhook URL</span><div class="row gap"><input class="inp mono sm" id="tvHookUrl" value="${esc(url)}" readonly style="flex:1;min-width:0"><button class="btn ghost sm" id="tvHookCopy">Copy</button><button class="btn ghost sm" id="tvHookRotate" title="New secret key">Rotate key</button></div>
      <span>Alert message</span><pre class="code sm">{"source":"tradingview","symbol":"{{ticker}}","event":"{{strategy.order.action}}","price":{{close}},"note":"{{strategy.order.comment}}"}</pre>
    </div>
    <div class="note">TradingView's servers must be able to reach this computer: on your home Wi-Fi or Tailscale they cannot. Expose the port with a tunnel (Cloudflare Tunnel / ngrok) and paste its public URL below; the key in the URL is the only credential, so keep the URL private.</div>
    <div class="row gap" style="margin-top:8px"><input class="inp sm" id="tvPublic" placeholder="https://your-tunnel.example.com" value="${esc(h.public_base || '')}" style="flex:1;min-width:160px"><button class="btn ghost sm" id="tvPublicSave">Save public URL</button></div>
    ${h.recent?.length ? `<div class="mini-label" style="margin:12px 0 6px">Recent</div>${h.recent.slice(0, 6).map(r => `<div class="small muted mono">${new Date(r.t * 1000).toLocaleString()} · ${esc(JSON.stringify(r.body)).slice(0, 140)}</div>`).join('')}` : ''}`;
  $('#tvHookCopy').onclick = async () => { try { await navigator.clipboard.writeText($('#tvHookUrl').value); toast('Webhook URL copied'); } catch (e) { toast('Copy blocked'); } };
  $('#tvHookRotate').onclick = async () => { status = { ...status, hook: await api('/api/tv/hook', { rotate: true }) }; renderHook(); toast('New webhook key'); };
  $('#tvPublicSave').onclick = async () => { status = { ...status, hook: await api('/api/tv/hook', { public_base: $('#tvPublic').value.trim() }) }; renderHook(); toast('Saved'); };
}

function renderKnows() {
  const r = S.res, d = status?.data || {};
  const st = r?.stats;
  $('#tvKnows').innerHTML = `
    <div class="kv small">
      <div><span class="muted">Futures history loaded</span><b class="mono">${d.NQ ? `${d.NQ.days} sessions (${d.NQ.from} → ${d.NQ.to})` : '—'}</b></div>
      <div><span class="muted">Imported from TradingView</span><b class="mono">${d.NQ?.imported_days ? d.NQ.imported_days + ' sessions' : 'none yet'}</b></div>
      <div><span class="muted">Current backtest</span><b class="mono">${st ? `${st.trades} trades · PF ${st.profit_factor} · ${st.net >= 0 ? '+' : ''}$${Math.round(st.net).toLocaleString()}` : '—'}</b></div>
      <div><span class="muted">Data used</span><b class="mono">real CME futures only (NQ${d.ES ? ' + ES' : ''})</b></div>
    </div>
    <div class="note">Every TradingView export you add becomes part of the bot's futures record: the Backtest, Regimes and Confluence Lab pages all re-test on it. The record is only about 10 weeks today; the goal is a full year or more of real MNQ / NQ bars.</div>`;
}
