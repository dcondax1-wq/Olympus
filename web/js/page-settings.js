import { $, $$, esc, seg, api, toast } from './util.js';
import { SKINS, A, setAppearance, previewSvg } from './skins.js';
import { chime } from './sound.js';

const ACCENTS = ['#4c8dff', '#ff2bd6', '#00d1ff', '#39ff78', '#ffb000', '#ff2e4d', '#a78bfa', '#f5f5f5'];
const EVENTS = [['sweep', 'Liquidity sweeps'], ['signal', 'Signals (IFVG confirmed)'], ['entry', 'Entries'], ['exit', 'Exits'],
  ['guard', 'Trade-guard changes (news / volatility)'], ['daily', 'End-of-day report'], ['regime', 'Regime changes']];

export function init() {
  document.addEventListener('le-appearance', () => { if ($('#page-settings').classList.contains('active')) render(); });
}
export function show() { render(); loadAlerts(); loadNet(); }

// ---------- open on your phone: LAN / Tailscale addresses + QR codes
async function loadNet() {
  let n;
  try { n = await api('/api/net'); } catch (e) { $('#phoneOut').innerHTML = '<div class="empty">Could not read network addresses.</div>'; return; }
  const addrs = [];
  if (n.tailscale) addrs.push({ label: 'Anywhere · Tailscale', url: `http://${n.tailscale}:${n.port}`, hint: 'Works away from home when your phone is signed in to the same Tailscale account.', best: true });
  for (const ip of n.lan) addrs.push({ label: 'Home Wi-Fi', url: `http://${ip}:${n.port}`, hint: 'Phone and this computer on the same network.' });
  $('#netState').textContent = n.tailscale ? '● Tailscale on' : 'LAN only';
  $('#netState').className = 'pill ' + (n.tailscale ? 'good' : '');
  $('#phoneOut').innerHTML = `
    <div class="phone-grid">
      ${addrs.map((a, k) => `<div class="phone-addr ${a.best ? 'best' : ''}">
        <div class="qr" id="qr${k}"></div>
        <div class="pa-meta"><div class="mini-label">${esc(a.label)}</div><a class="mono pa-url" href="${esc(a.url)}" target="_blank" rel="noopener">${esc(a.url)}</a>
          <div class="small muted">${esc(a.hint)}</div><button class="btn ghost sm" data-copy="${esc(a.url)}">Copy link</button></div></div>`).join('')}
    </div>
    <ol class="tv-steps small" style="margin-top:10px">
      <li>Scan a code with your phone's camera (or type the address).</li>
      <li><b>iPhone</b>: Share → <b>Add to Home Screen</b>. <b>Android</b>: ⋮ menu → <b>Add to Home screen</b> / <b>Install app</b>.</li>
      <li>It opens full-screen like an app, with the bottom tab bar. Keep this computer and the server running; the bot and data live here.</li>
    </ol>
    <div class="note">${n.tailscale ? 'Tailscale is running on this computer, so the first address works from anywhere once the Tailscale app on your phone is signed in to the same account (free).' : 'For access away from home, install Tailscale on this computer and your phone (free): a private address appears here.'} Anyone on these private networks can open the dashboard; it has no login, so keep it to your own devices.</div>`;
  $('#phoneOut').onclick = async (e) => { const b = e.target.closest('[data-copy]'); if (!b) return; try { await navigator.clipboard.writeText(b.dataset.copy); toast('Link copied'); } catch (_) { toast('Copy blocked'); } };
  if (!window.QRCode) {
    await new Promise((res) => { const s = document.createElement('script'); s.src = 'https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js'; s.onload = res; s.onerror = res; document.head.appendChild(s); });
  }
  if (window.QRCode) addrs.forEach((a, k) => { const el = $('#qr' + k); if (el) new QRCode(el, { text: a.url, width: 132, height: 132, colorDark: '#0b1017', colorLight: '#ffffff', correctLevel: QRCode.CorrectLevel.M }); });
}

function render() {
  $('#skinGallery').innerHTML = SKINS.map(s => {
    const [page, surf, acc, , , ink] = s.sw;
    return `<button class="skin ${A.skin === s.id ? 'on' : ''}" data-skin="${s.id}" aria-pressed="${A.skin === s.id}">
      <div class="pv" style="background:${page}">
        <div class="bar"><span class="dot" style="background:${acc};box-shadow:0 0 10px ${acc}"></span>
          <span class="ttl" style="color:${ink};font-family:'${s.font}'">${esc(s.name)}</span>
          <span class="num" style="color:${acc};font-family:'${s.font}'">+$14,190</span></div>
        <div style="background:${surf};border-radius:8px;padding:4px 6px">${previewSvg(s)}</div>
      </div>
      <div class="meta"><b>${esc(s.name)}</b><span>${esc(s.desc)}</span><span class="mode">${s.mode} · ${esc(s.font)}</span></div></button>`;
  }).join('');
  $('#skinGallery').onclick = (e) => {
    const b = e.target.closest('[data-skin]'); if (!b) return;
    setAppearance({ skin: b.dataset.skin, accent: null });
    toast('Theme: ' + SKINS.find(s => s.id === b.dataset.skin).name);
  };
  const tog = (id, on) => `<button class="btn ${on ? 'primary' : 'ghost'} sm" id="${id}">${on ? 'On' : 'Off'}</button>`;
  $('#appearanceOut').innerHTML = `
    <div class="set-row"><div class="lbl"><b>Density</b><span>Compact fits more on screen</span></div><div class="seg sm" id="setDensity"></div></div>
    <div class="set-row"><div class="lbl"><b>Accent color</b><span>Override the theme's accent</span></div>
      <div class="swatches" id="setAccent">${ACCENTS.map(c => `<button style="background:${c}" data-c="${c}" class="${A.accent === c ? 'on' : ''}" title="${c}"></button>`).join('')}
        <input type="color" id="setAccentPick" value="${A.accent || '#4c8dff'}" title="Custom accent"><button class="btn ghost sm" id="setAccentReset">Reset</button></div></div>
    <div class="set-row"><div class="lbl"><b>Ticker tape</b><span>Live market strip under the top bar</span></div>${tog('setTicker', A.ticker)}</div>
    <div class="set-row"><div class="lbl"><b>Animations</b><span>Count-ups, tape, pulses, page transitions</span></div>${tog('setMotion', A.motion)}</div>
    <div class="set-row"><div class="lbl"><b>Hollow up-candles</b><span>Classic hollow / filled candle style</span></div>${tog('setHollow', A.hollow)}</div>
    <div class="set-row"><div class="lbl"><b>Sound alerts</b><span>Chimes for sweeps, signals, fills and guard changes</span></div>
      <div class="row gap">${tog('setSound', A.sound)}<button class="btn ghost sm" id="setSoundTest">Test</button></div></div>`;
  seg($('#setDensity'), [['comfortable', 'Comfortable'], ['compact', 'Compact']], A.density, (v) => setAppearance({ density: v }));
  $('#setAccent').onclick = (e) => { const b = e.target.closest('[data-c]'); if (b) setAppearance({ accent: b.dataset.c }); };
  $('#setAccentPick').oninput = (e) => setAppearance({ accent: e.target.value });
  $('#setAccentReset').onclick = () => setAppearance({ accent: null });
  $('#setTicker').onclick = () => setAppearance({ ticker: !A.ticker });
  $('#setMotion').onclick = () => setAppearance({ motion: !A.motion });
  $('#setHollow').onclick = () => setAppearance({ hollow: !A.hollow });
  $('#setSound').onclick = () => { setAppearance({ sound: !A.sound }); if (A.sound) chime('test'); };
  $('#setSoundTest').onclick = () => chime('test', true);
}

async function loadAlerts() {
  let c;
  try { c = await api('/api/alerts'); } catch (e) { return; }
  $('#alertState').textContent = c.telegram_on || c.discord_on ? `● ${[c.telegram_on && 'Telegram', c.discord_on && 'Discord'].filter(Boolean).join(' + ')}` : 'not set up';
  $('#alertState').className = 'pill ' + (c.telegram_on || c.discord_on ? 'good' : '');
  $('#alertsOut').innerHTML = `
    <div class="form-grid">
      <span>Telegram bot token</span><input class="inp" id="alTgTok" placeholder="from @BotFather" value="${esc(c.telegram_token)}" autocomplete="off">
      <span>Telegram chat id</span><input class="inp" id="alTgChat" placeholder="your chat id" value="${esc(c.telegram_chat)}" autocomplete="off">
      <span>Discord webhook</span><input class="inp" id="alDc" placeholder="https://discord.com/api/webhooks/…" value="${esc(c.discord_webhook)}" autocomplete="off">
    </div>
    <div class="mini-label" style="margin:14px 0 6px">Send me</div>
    <div class="checks">${EVENTS.map(([k, l]) => `<label class="row gap small"><input type="checkbox" data-ev="${k}" ${c.events[k] ? 'checked' : ''}> ${l}</label>`).join('')}</div>
    <div class="row gap" style="margin-top:12px"><button class="btn primary sm" id="alSave">Save</button><button class="btn ghost sm" id="alTest">Send test</button></div>
    <div class="note">Stored only on this computer (data/alerts.json). Telegram: message <b>@BotFather</b> → /newbot for a token, send your bot a message, then get your chat id from <b>@userinfobot</b>. Discord: channel settings → Integrations → Webhooks.</div>
    ${c.recent.length ? `<div class="mini-label" style="margin:12px 0 6px">Recent</div>${c.recent.slice().reverse().slice(0, 5).map(r => `<div class="small muted">${new Date(r.t * 1000).toLocaleTimeString()} · ${esc(r.kind)} · ${esc(JSON.stringify(r.result))}</div>`).join('')}` : ''}`;
  const body = () => ({
    telegram_token: $('#alTgTok').value, telegram_chat: $('#alTgChat').value, discord_webhook: $('#alDc').value,
    events: Object.fromEntries($$('[data-ev]').map(x => [x.dataset.ev, x.checked])),
  });
  $('#alSave').onclick = async () => { await api('/api/alerts', body()); toast('Alert settings saved'); loadAlerts(); };
  $('#alTest').onclick = async () => {
    await api('/api/alerts', body());
    const r = await api('/api/alerts/send', { text: '✅ Liquidity Engine: test alert. Your phone alerts are working.', force: true });
    toast(r.sent ? 'Test sent: ' + JSON.stringify(r.result) : 'Nothing configured yet');
    loadAlerts();
  };
}
