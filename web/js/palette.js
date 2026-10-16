// Command palette: Ctrl+K or "/" opens a glassy launcher with fuzzy page jumps, actions and an in-app glossary.
import { $, $$, api, esc, toast } from './util.js';
import { S } from './state.js';
import { go, run } from './app.js';

// built-in glossary so the palette explains terms even when the server is unreachable; /api/extras/glossary replaces it
let GLOSS = [
  { term: 'IFVG', name: 'Inversion fair value gap', short: 'A fair value gap that price closes through, flipping it from support to resistance (or back). The bot\'s entry trigger after a sweep.', long: 'A fair value gap is a three-candle imbalance. When price later closes completely through it, the gap inverts: a bullish FVG that was support becomes resistance. After a liquidity sweep, the first IFVG that closes back inside the range confirms the reversal and sets the entry zone.' },
  { term: 'CISD', name: 'Change in state of delivery', short: 'A close through the opening price of the last opposing candle series. The fallback trigger when the reversal leg has no FVG.', long: 'After a sweep, a close through the open of the first candle of the raid means the market stopped delivering in the raid direction. Used only when the leg printed no fair value gap to invert.' },
  { term: 'Sweep', name: 'Liquidity sweep / raid', short: 'Price trades through a resting pool of stops (a prior high or low) and fails to continue. Nothing is armed until a pool has been swept.', long: 'Buy stops rest above highs (BSL), sell stops below lows (SSL). A sweep fills them and reverses. The sweep extreme becomes the protected point: the reversal is valid only while price stays on the right side of it.' },
  { term: 'DOL', name: 'Draw on liquidity', short: 'The pool price is most likely heading to next; the bot\'s profit target.', long: 'After a sweep on one side the market usually rotates to untaken liquidity on the other side. The bot targets the next quality pool and skips the trade if it is closer than the minimum R.' },
  { term: 'LRL / HRL', name: 'Low / high resistance liquidity', short: 'LRL is a clean, untested level that price slices through easily; HRL has been defended before and takes more effort to break.', long: 'A raid through a high-resistance level is more likely to be a true sweep and reverse. Pool quality feeds the confluence score through w_lrl.' },
  { term: 'Giveback', name: 'Giveback exit rule', short: 'Once a trade reached +0.5R and then closes back below entry, the bot exits instead of waiting for the full stop.', long: 'Reaching +0.5R and surrendering the whole move is the signature of a failed reversal. Leaving at the first close back through entry turns a -1R loser into roughly a scratch. The only exit signal that improved every tested period.' },
  { term: 'Killzone', name: 'Killzone', short: 'High-volume windows: London 02:00-05:00, NY AM 09:30-11:30, NY PM 13:30-15:30 ET.', long: 'Entries are only allowed inside the configured entry windows. Sweeps from 08:00 ET can arm a setup for the killzone.' },
  { term: 'MLL', name: 'Trailing maximum loss limit', short: 'The prop-firm drawdown line: trails end-of-day balance highs by $2,000 and locks at start + $100.', long: 'The account fails if balance or intraday low touches the line. The Command Center shows the cushion above it.' },
  { term: 'Premium / discount', name: 'Premium and discount', short: 'Where price sits in the 1H dealing range: above the midpoint is premium (favour shorts), below is discount (favour longs).', long: 'Longs score higher when the sweep lands in discount, shorts in premium. The edge held on both sides of the split in NQ and ES.' },
];

const PAGE_ICON = { analytics: '▥', ops: '⌁', launch: '⏻', command: '◎', briefing: '☀', chart: '▤', live: '●', news: '⚡', backtest: '∑', replay: '⏵', regime: '◐', conf: '⧉', robust: '⚗', prop: '⛨', report: '▦', journal: '✎', playbook: '❖', review: '◈', memory: '⛁', tv: '⇄', settings: '⚙' };

const CSS = `
#cpOverlay{position:fixed;inset:0;z-index:900;display:none;align-items:flex-start;justify-content:center;padding:12vh 16px 16px;background:color-mix(in srgb,var(--page,#05080d) 55%,transparent);backdrop-filter:blur(10px) saturate(1.2);-webkit-backdrop-filter:blur(10px) saturate(1.2)}
#cpOverlay.on{display:flex;animation:cpIn .14s ease-out}
@keyframes cpIn{from{opacity:0;transform:translateY(-6px)}to{opacity:1;transform:none}}
.cp{width:min(640px,100%);background:color-mix(in srgb,var(--surface) 88%,transparent);border:1px solid var(--border);border-radius:16px;box-shadow:0 30px 80px rgba(0,0,0,.55),0 0 0 1px color-mix(in srgb,var(--accent) 18%,transparent),0 0 60px var(--glow);overflow:hidden}
.cp-in{display:flex;align-items:center;gap:10px;padding:12px 14px;border-bottom:1px solid var(--border)}
.cp-in i{font-style:normal;color:var(--accent);font-size:16px}
.cp-in input{flex:1;background:transparent;border:0;outline:0;color:var(--ink);font:500 16px var(--sans);min-width:0}
.cp-in kbd{font:500 10.5px var(--mono);color:var(--muted);border:1px solid var(--border);border-radius:6px;padding:2px 6px}
.cp-list{max-height:min(54vh,460px);overflow:auto;padding:6px}
.cp-sec{font:600 10px var(--display);letter-spacing:.16em;text-transform:uppercase;color:var(--muted);padding:8px 10px 4px}
.cp-it{display:flex;align-items:center;gap:12px;padding:9px 10px;border-radius:10px;cursor:pointer;color:var(--ink-2)}
.cp-it i{font-style:normal;width:22px;text-align:center;color:var(--accent);opacity:.85}
.cp-it b{color:var(--ink);font-weight:600}
.cp-it small{color:var(--muted);margin-left:auto;font:500 11px var(--mono);white-space:nowrap}
.cp-it.on{background:color-mix(in srgb,var(--accent) 16%,transparent);box-shadow:inset 2px 0 0 var(--accent)}
.cp-it mark{background:transparent;color:var(--accent);font-weight:700}
.cp-foot{display:flex;gap:14px;padding:8px 14px;border-top:1px solid var(--border);font:500 11px var(--mono);color:var(--muted)}
.cp-empty{padding:26px;text-align:center;color:var(--muted)}
.cp-gl{padding:18px 20px 20px}
.cp-gl .mini-label{color:var(--accent)}
.cp-gl h2{font-family:var(--display);margin:4px 0 10px;font-size:22px}
.cp-gl p{color:var(--ink-2);line-height:1.6;margin:0 0 10px;font-size:13.5px}
.cp-gl .cp-back{margin-top:6px}
@media (max-width:760px){#cpOverlay{padding:8px}.cp-in kbd{display:none}.cp-list{max-height:64vh}}
`;

let items = [], filtered = [], sel = 0, mode = 'list';
// other modules (dash/ux.js) add actions + widget jumps here; each provider returns palette items at open time
const EXTRA = [];
export const addPaletteItems = (fn) => { EXTRA.push(fn); };

function pageItems() {
  return $$('#nav a[data-page]').map(a => ({ kind: 'page', key: a.dataset.page, label: a.querySelector('span')?.textContent || a.dataset.page, icon: PAGE_ICON[a.dataset.page] || '▸', hint: 'page', do: () => go(a.dataset.page) }));
}

function actionItems() {
  const syms = $$('#symSeg button').map(b => b.dataset.v);
  const other = syms.find(s => s !== S.sym) || (S.sym === 'NQ' ? 'ES' : 'NQ');
  return [
    { kind: 'action', key: 'run', label: 'Run backtest', icon: '▶', hint: 'action', do: () => run() },
    { kind: 'action', key: 'refresh', label: 'Refresh data from Yahoo', icon: '⟳', hint: 'action', do: () => $('#refreshData')?.click() },
    { kind: 'action', key: 'sound', label: 'Toggle sound alerts', icon: '🔔', hint: 'action', do: () => $('#soundBtn')?.click() },
    { kind: 'action', key: 'sym', label: `Switch symbol to ${other}`, icon: '⇄', hint: `${S.sym} → ${other}`, do: () => { const b = $(`#symSeg button[data-v="${other}"]`); if (b) b.click(); else toast(`${other} data is not loaded`); } },
    { kind: 'action', key: 'qr', label: 'Open phone QR codes', icon: '▦', hint: 'settings', do: () => { go('settings'); setTimeout(() => $('#phoneOut')?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 60); } },
    { kind: 'action', key: 'kill', label: 'Kill switch (flatten & stop bot)', icon: '■', hint: 'live bot', do: () => { go('live'); setTimeout(() => { const k = $('#lvKill'); if (k) { k.scrollIntoView({ behavior: 'smooth', block: 'center' }); k.animate([{ boxShadow: '0 0 0 0 var(--bad)' }, { boxShadow: '0 0 0 14px transparent' }], { duration: 900, iterations: 3 }); } }, 120); } },
    { kind: 'action', key: 'review', label: 'Copy this week\'s review', icon: '⎘', hint: 'weekly review', do: () => { go('review'); setTimeout(() => $('#rvCopy')?.click(), 250); } },
    { kind: 'action', key: 'theme', label: 'Themes & appearance', icon: '◑', hint: 'settings', do: () => go('settings') },
  ];
}

function glossItems() {
  return GLOSS.map(g => ({ kind: 'explain', key: g.term, label: `Explain: ${g.term}`, icon: '?', hint: g.name, do: () => showTerm(g) }));
}

// fuzzy score: substring beats subsequence; earlier and tighter matches score higher. Returns [score, matchedIdx[]]
function fuzzy(q, text) {
  const t = text.toLowerCase(), s = q.toLowerCase();
  if (!s) return [1, []];
  const at = t.indexOf(s);
  if (at >= 0) return [200 - at - (t.length - s.length) * 0.1, Array.from({ length: s.length }, (_, i) => at + i)];
  let i = 0, score = 100, idx = [], last = -1;
  for (const ch of s) {
    const k = t.indexOf(ch, i);
    if (k < 0) return [-1, []];
    score -= (k - (last + 1)) * 3;
    idx.push(k); last = k; i = k + 1;
  }
  return [score, idx];
}
const hl = (text, idx) => { const set = new Set(idx); return [...text].map((c, i) => set.has(i) ? `<mark>${esc(c)}</mark>` : esc(c)).join(''); };

function build() {
  const extra = EXTRA.flatMap(f => { try { return f() || []; } catch { return []; } });
  items = [...pageItems(), ...actionItems(), ...extra, ...glossItems()];
}

function renderList() {
  const q = $('#cpInput').value.trim();
  let exp = q.toLowerCase().startsWith('explain') ? q.slice(7).replace(/^[:\s]+/, '') : null;
  filtered = items.map(it => {
    const target = exp != null && it.kind === 'explain' ? it.key : it.label;
    const [sc, idx] = fuzzy(exp != null ? exp : q, target);
    return { it, sc: exp != null && it.kind !== 'explain' ? -1 : sc, idx, target };
  }).filter(x => x.sc >= 0).sort((a, b) => b.sc - a.sc || a.it.label.localeCompare(b.it.label));
  const ORD = ['page', 'action', 'widget', 'explain'];
  if (!q) filtered.sort((a, b) => ORD.indexOf(a.it.kind) - ORD.indexOf(b.it.kind));
  sel = Math.min(sel, Math.max(0, filtered.length - 1));
  const list = $('#cpList');
  if (!list) return;
  if (!filtered.length) { list.innerHTML = '<div class="cp-empty">Nothing matches. Try a page name, "run", "kill" or "explain ifvg".</div>'; return; }
  let lastKind = null, html = '';
  filtered.forEach((x, i) => {
    if (x.it.kind !== lastKind) { html += `<div class="cp-sec">${{ page: 'Go to', action: 'Actions', widget: 'Widgets on this page', explain: 'Glossary' }[x.it.kind]}</div>`; lastKind = x.it.kind; }
    const label = x.it.kind === 'explain' && exp != null ? `Explain: ${hl(x.it.key, x.idx)}` : hl(x.it.label, x.idx);
    html += `<div class="cp-it ${i === sel ? 'on' : ''}" data-i="${i}"><i>${x.it.icon}</i><b>${label}</b><small>${esc(x.it.hint)}</small></div>`;
  });
  list.innerHTML = html;
  list.querySelector('.cp-it.on')?.scrollIntoView({ block: 'nearest' });
}

function showTerm(g) {
  mode = 'term';
  $('#cpBody').innerHTML = `<div class="cp-gl"><div class="mini-label">Glossary · ${esc(g.name)}</div><h2>${esc(g.term)}</h2>
    <p><b>${esc(g.short)}</b></p><p>${esc(g.long || '')}</p>
    <div class="row gap cp-back"><button class="btn ghost sm" id="cpBack">← Back</button><button class="btn ghost sm" data-goto="playbook" id="cpPlaybook">Open playbook</button></div></div>`;
  $('#cpBack').onclick = () => { showList(); $('#cpInput').focus(); };
  $('#cpPlaybook').onclick = close;
}
function showList() {
  mode = 'list';
  $('#cpBody').innerHTML = `<div class="cp-list" id="cpList"></div>`;
  $('#cpList').onclick = (e) => { const it = e.target.closest('.cp-it'); if (it) pick(+it.dataset.i); };
  $('#cpList').onmousemove = (e) => { const it = e.target.closest('.cp-it'); if (it && +it.dataset.i !== sel) { sel = +it.dataset.i; $$('.cp-it', $('#cpList')).forEach(x => x.classList.toggle('on', +x.dataset.i === sel)); } };
  renderList();
}
function pick(i) {
  const x = filtered[i]; if (!x) return;
  if (x.it.kind === 'explain') { x.it.do(); return; }
  close();
  try { x.it.do(); } catch (e) { toast('Action failed: ' + e.message); }
}

export function openPalette(prefill = '') {
  build();
  const ov = $('#cpOverlay');
  ov.classList.add('on');
  showList();
  const inp = $('#cpInput');
  inp.value = prefill; sel = 0; renderList();
  setTimeout(() => { inp.focus(); inp.select(); }, 0);
}
export function close() { $('#cpOverlay')?.classList.remove('on'); }
const isOpen = () => $('#cpOverlay')?.classList.contains('on');
const typing = (el) => el && (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA' || el.tagName === 'SELECT' || el.isContentEditable);

export function initPalette() {
  if ($('#cpOverlay')) return;
  const st = document.createElement('style'); st.id = 'cpStyle'; st.textContent = CSS; document.head.appendChild(st);
  const ov = document.createElement('div'); ov.id = 'cpOverlay';
  ov.innerHTML = `<div class="cp" role="dialog" aria-label="Command palette">
      <div class="cp-in"><i>⌘</i><input id="cpInput" placeholder="Jump to a page, run an action, or type “explain ifvg”…" autocomplete="off" spellcheck="false"><kbd>esc</kbd></div>
      <div id="cpBody"></div>
      <div class="cp-foot"><span>↑↓ navigate</span><span>↵ select</span><span>ctrl+K or / to open</span></div></div>`;
  document.body.appendChild(ov);
  ov.addEventListener('mousedown', (e) => { if (e.target === ov) close(); });
  $('#cpInput').addEventListener('input', () => { if (mode !== 'list') showList(); sel = 0; renderList(); });
  $('#cpInput').addEventListener('keydown', (e) => {
    if (mode !== 'list') { if (e.key === 'Escape' || e.key === 'Backspace') { e.preventDefault(); showList(); } return; }
    if (e.key === 'ArrowDown') { e.preventDefault(); sel = Math.min(filtered.length - 1, sel + 1); renderList(); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); sel = Math.max(0, sel - 1); renderList(); }
    else if (e.key === 'Enter') { e.preventDefault(); pick(sel); }
    else if (e.key === 'Tab') { e.preventDefault(); sel = (sel + (e.shiftKey ? -1 : 1) + filtered.length) % Math.max(1, filtered.length); renderList(); }
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && isOpen()) { e.preventDefault(); if (mode === 'term') { showList(); $('#cpInput').focus(); } else close(); return; }
    const combo = (e.ctrlKey || e.metaKey) && !e.shiftKey && !e.altKey && e.key.toLowerCase() === 'k';
    const slash = e.key === '/' && !e.ctrlKey && !e.metaKey && !e.altKey && !typing(document.activeElement);
    if (combo || slash) { e.preventDefault(); if (isOpen() && combo) close(); else openPalette(''); }
  });
  // a small launcher chip in the top bar so phone users (no keyboard) can open it too
  const tb = $('.tb-right');
  if (tb && !$('#cpBtn')) {
    const b = document.createElement('button'); b.className = 'btn ghost icon'; b.id = 'cpBtn'; b.title = 'Command palette (Ctrl+K)'; b.textContent = '⌘';
    b.onclick = () => openPalette('');
    tb.insertBefore(b, tb.firstChild);
  }
  api('/api/extras/glossary').then(r => { if (r?.terms?.length) GLOSS = r.terms; }).catch(() => null);
  window.LE = Object.assign(window.LE || {}, { palette: openPalette, explain: (term) => { const g = GLOSS.find(x => x.term.toLowerCase() === String(term).toLowerCase()); openPalette(g ? `explain ${g.term}` : 'explain '); } });
}
