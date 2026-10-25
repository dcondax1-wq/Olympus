// Keyboard shortcuts of the PC dashboard. ? shows the list. G then a letter jumps to a page, 1-6 to the top pages.
// The single-letter tools of the classic layer (web/js/dash/ux.js: Z zen, F TV wall, T themes, D dark / light, R risk
// calculator, N notifications, W layout, X snapshot, M sound on / off) keep working; Ctrl K or / opens the command palette.
// SAFETY: no key starts, stops, arms or kills the bot. K is NOT kill: the kill switch is only the HOLD TO KILL button on
// Bot Control (held 1.5 s). Pressing K only says so.
import { $, esc, toast } from '../util.js';

export const GO = [
  ['h', 'cc', 'Command center (home)'], ['y', 'command', 'Today'], ['p', 'goals', 'Goals'], ['f', 'features', 'All features'],
  ['w', 'runbook', 'Runbook (emergency)'], ['q', 'audit', 'Audit evidence'], ['j', 'tradelog', 'Trade log'], ['x', 'atlassetups', 'ATLAS per setup'],
  ['z', 'sesscal', 'Session calendar'], ['b', 'botctl', 'Bot Control'], ['a', 'accounts', 'Accounts'], ['c', 'chart', 'Chart'],
  ['l', 'livechart', 'Live chart (LIT levels)'], ['o', 'botlog', 'Bot log'], ['n', 'ntpanel', 'NinjaTrader'],
  ['i', 'timeline', 'Session timeline'], ['m', 'morning', 'Morning report'], ['v', 'livesettings', 'Live settings'],
  ['t', 'trades', 'Trades'], ['r', 'results', 'Results'], ['e', 'evalhq', 'Eval HQ'], ['d', 'data', 'Data'],
  ['u', 'modules', 'Modules'], ['s', 'settings', 'Settings'],
];
export const NUM = ['cc', 'goals', 'command', 'botctl', 'accounts', 'trades'];
export const SINGLE = [
  ['?', 'This list'], ['Ctrl K  or  /', 'Command palette (search every page)'], ['M', 'Sound alerts on / off (mute)'],
  ['Z', 'Zen mode'], ['F', 'TV-wall fullscreen'], ['T', 'Theme switcher'], ['D', 'Dark / light'], ['R', 'Risk calculator'],
  ['N', 'Notification center'], ['W', 'Widget layout'], ['X', 'Snapshot page as PNG'], ['Esc', 'Close'],
];
const typing = (el) => !!el && (el.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName));
let gAt = 0;

function kbd(k) { return k.split('  or  ').map((x) => x.split(' then ').map((y) => `<kbd>${esc(y)}</kbd>`).join(' then ')).join(' or '); }
export function helpHTML() {
  return `<div class="op-keys" role="dialog" aria-label="Keyboard shortcuts"><div class="op-keys-h"><h3>Keyboard shortcuts</h3><button type="button" class="btn ghost sm" id="opKeysX">Close</button></div>
    <div class="op-keys-safe"><b>Kill switch: no key.</b> Only the HOLD TO KILL button on Bot Control (hold 1.5 s). K does nothing. No key starts, stops or arms the bot.</div>
    <div class="op-keys-g"><div><h4>Go to (press G, then)</h4>${GO.map(([k, , l]) => `<div class="op-kr"><span>${esc(l)}</span><span>${kbd('G then ' + k.toUpperCase())}</span></div>`).join('')}</div>
    <div><h4>Top pages</h4>${NUM.map((p, i) => `<div class="op-kr"><span>${esc((GO.find((g) => g[1] === p) || [0, 0, p])[2])}</span><span>${kbd(String(i + 1))}</span></div>`).join('')}
    <h4 style="margin-top:14px">Tools</h4>${SINGLE.map(([k, l]) => `<div class="op-kr"><span>${esc(l)}</span><span>${kbd(k)}</span></div>`).join('')}</div></div>
    <p class="muted small">Shortcuts are ignored while you type in a field.</p></div>`;
}
export function showHelp() {
  let ov = document.getElementById('opKeysOv');
  if (ov) { ov.remove(); return; }
  ov = document.createElement('div'); ov.id = 'opKeysOv'; ov.className = 'op-keys-ov';
  ov.innerHTML = helpHTML();
  document.body.appendChild(ov);
  ov.addEventListener('mousedown', (e) => { if (e.target === ov) ov.remove(); });
  $('#opKeysX').onclick = () => ov.remove();
}

function onKey(e) {
  if (e.ctrlKey || e.metaKey || e.altKey || typing(document.activeElement)) return;
  if (document.querySelector('#cpOverlay.on')) return;
  const ov = document.getElementById('opKeysOv');
  if (e.key === 'Escape' && ov) { ov.remove(); e.stopImmediatePropagation(); return; }
  const k = e.key.length === 1 ? e.key.toLowerCase() : e.key;
  const go = window.LE?.go;
  if (gAt && Date.now() - gAt < 1300) {
    gAt = 0;
    const hit = GO.find(([x]) => x === k);
    if (hit) { e.preventDefault(); e.stopImmediatePropagation(); ov?.remove(); go?.(hit[1]); }
    else e.stopImmediatePropagation();
    return;
  }
  if (k === 'g') { gAt = Date.now(); e.preventDefault(); e.stopImmediatePropagation(); return; }
  if (e.key === '?') { e.preventDefault(); e.stopImmediatePropagation(); showHelp(); return; }
  if (/^[1-6]$/.test(e.key)) { e.preventDefault(); e.stopImmediatePropagation(); go?.(NUM[+e.key - 1]); return; }
  if (k === 'k') { e.preventDefault(); e.stopImmediatePropagation(); toast('No kill shortcut: use HOLD TO KILL on Bot Control', 3500); }
}

export function initKeys() {
  window.addEventListener('keydown', onKey, true);       // capture: runs before the classic layer's own key handler
  window.LE = Object.assign(window.LE || {}, { keys: { GO, NUM, help: showHelp } });
}
