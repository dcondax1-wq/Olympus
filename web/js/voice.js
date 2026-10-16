// Voice briefing: a "Listen" control injected into the Briefing hero that reads the game plan aloud (Web Speech API).
import { $, $$, toast } from './util.js';

const CSS = `
#briefVoice{display:inline-flex;align-items:center;gap:6px;margin-top:4px}
#briefVoice .btn{display:inline-flex;align-items:center;gap:6px}
#briefVoice .vb-eq{display:inline-flex;align-items:flex-end;gap:2px;height:12px;width:16px}
#briefVoice .vb-eq i{width:3px;background:currentColor;border-radius:1px;height:30%;animation:vbEq 1s ease-in-out infinite}
#briefVoice .vb-eq i:nth-child(2){animation-delay:.15s}#briefVoice .vb-eq i:nth-child(3){animation-delay:.3s}#briefVoice .vb-eq i:nth-child(4){animation-delay:.45s}
#briefVoice.paused .vb-eq i{animation-play-state:paused}
@keyframes vbEq{0%,100%{height:30%}50%{height:100%}}
@media (max-width:760px){#briefVoice{margin-top:8px}}
`;

const supported = () => typeof window !== 'undefined' && 'speechSynthesis' in window && 'SpeechSynthesisUtterance' in window;
let state = 'idle';   // idle | speaking | paused
let voice = null;

function pickVoice() {
  const vs = speechSynthesis.getVoices() || [];
  if (!vs.length) return null;
  const en = vs.filter(v => /^en(-|_)?/i.test(v.lang));
  const prefs = [/natural/i, /google us english/i, /aria/i, /jenny/i, /guy/i, /samantha/i, /daniel/i, /google uk english/i, /microsoft .* english/i];
  for (const re of prefs) { const v = en.find(x => re.test(x.name)); if (v) return v; }
  return en.find(v => v.default) || en[0] || vs[0];
}

// turn the dashboard's compact notation into something that reads naturally
function spoken(s) {
  return String(s || '')
    .replace(/\s+/g, ' ')
    .replace(/·/g, ', ').replace(/→/g, ' to ').replace(/–/g, ' to ').replace(/\s*\|\s*/g, ', ')
    .replace(/\bNQ\b/g, 'N Q').replace(/\bES\b/g, 'E S').replace(/\bMNQ\b/g, 'micro N Q')
    .replace(/\bIFVG\b/g, 'inversion fair value gap').replace(/\bFVG\b/g, 'fair value gap').replace(/\bCISD\b/g, 'change in state of delivery')
    .replace(/\bBSL\b/g, 'buy side liquidity').replace(/\bSSL\b/g, 'sell side liquidity').replace(/\bDOL\b/g, 'draw on liquidity')
    .replace(/\bPDH\b/g, 'prior day high').replace(/\bPDL\b/g, 'prior day low').replace(/\bPWH\b/g, 'prior week high').replace(/\bPWL\b/g, 'prior week low')
    .replace(/\bONH\b/g, 'overnight high').replace(/\bONL\b/g, 'overnight low').replace(/\bPOC\b/g, 'point of control').replace(/\bVAH\b/g, 'value area high').replace(/\bVAL\b/g, 'value area low')
    .replace(/\bVIX\b/g, 'vix').replace(/\bVXN\b/g, 'V X N').replace(/\bMLL\b/g, 'max loss line').replace(/\bER\b/g, 'efficiency')
    .replace(/\bET\b/g, 'eastern').replace(/\b1H\b/g, 'one hour').replace(/\b15m\b/g, 'fifteen minute').replace(/\b4H\b/g, 'four hour').replace(/\b1D\b/g, 'daily')
    .replace(/\bpts\b/g, 'points').replace(/\+(\d)/g, 'plus $1').replace(/(^|\s)-(\d)/g, '$1minus $2')
    .replace(/[▲]/g, 'bullish').replace(/[▼]/g, 'bearish').replace(/[◀▶●○■□☐✔✖⚠]/g, '')
    .replace(/\.\s*\./g, '.').trim();
}

function briefingText() {
  const hero = $('#briefHero');
  if (!hero) return '';
  const parts = [];
  const label = hero.querySelector('.mini-label')?.textContent, h2 = hero.querySelector('h2')?.textContent, p = hero.querySelector('p')?.textContent, chip = hero.querySelector('.bh-chip')?.textContent;
  if (label) parts.push(label.replace('Game plan', 'Game plan for'));
  if (chip) parts.push(chip.trim() === 'CLEAR TO TRADE' ? 'The bot is clear to trade.' : chip.trim() === 'STAND DOWN' ? 'The bot is standing down.' : '');
  if (h2) parts.push(h2 + '.');
  if (p) parts.push(p + '.');
  const sc = $$('#briefScen .scn').map(e => e.textContent.trim()).filter(Boolean);
  if (sc.length) parts.push('Scenarios. ' + sc.map(s => s.replace(/^(LONG|SHORT|NO TRADE)/, (m) => m.charAt(0) + m.slice(1).toLowerCase() + ':')).join(' '));
  const reg = $('#briefRegime .big-status')?.textContent?.trim();
  if (reg) parts.push(`Regime: ${reg.toLowerCase()}.`);
  const rows = $$('#briefRegime .acct-row').slice(0, 2).map(r => r.textContent.replace(/\s+/g, ' ').trim());
  if (rows.length) parts.push(rows.join('. ') + '.');
  const news = $$('#briefNews tr').map(r => { const tds = $$('td', r); return tds.length >= 2 ? `${tds[0].textContent.trim()} ${tds[1].textContent.trim()}` : ''; }).filter(Boolean);
  parts.push(news.length ? `News today: ${news.join(', ')}.` : ($('#briefNews .empty') ? 'No high-impact U.S. releases today.' : ''));
  const lv = $$('#briefLevels .lv').slice(0, 7).map(l => l.textContent.replace(/\s+/g, ' ').trim());
  if (lv.length) parts.push('Nearest levels: ' + lv.join('. ') + '.');
  return spoken(parts.filter(Boolean).join(' '));
}

function setState(s) { state = s; paint(); }
function paint() {
  const box = $('#briefVoice'); if (!box) return;
  box.classList.toggle('paused', state === 'paused');
  const eq = '<span class="vb-eq"><i></i><i></i><i></i><i></i></span>';
  box.innerHTML = state === 'idle'
    ? `<button class="btn ghost sm" id="vbPlay" title="Read the briefing aloud">🔊 Listen</button>`
    : `<button class="btn sm ${state === 'speaking' ? 'primary' : 'ghost'}" id="vbPause" title="${state === 'speaking' ? 'Pause' : 'Resume'}">${state === 'speaking' ? eq + ' Pause' : '▶ Resume'}</button><button class="btn ghost sm" id="vbStop" title="Stop">■</button>`;
  $('#vbPlay') && ($('#vbPlay').onclick = play);
  $('#vbPause') && ($('#vbPause').onclick = () => { if (state === 'speaking') { speechSynthesis.pause(); setState('paused'); } else { speechSynthesis.resume(); setState('speaking'); } });
  $('#vbStop') && ($('#vbStop').onclick = stop);
}

function play() {
  const text = briefingText();
  if (!text) { toast('The briefing is still loading'); return; }
  speechSynthesis.cancel();
  voice = voice || pickVoice();
  // long texts are split by sentence: some engines (Chrome desktop) stop silently after ~15s of a single utterance
  const chunks = text.match(/[^.!?]+[.!?]+(\s|$)|[^.!?]+$/g) || [text];
  let n = 0;
  const speak = () => {
    if (n >= chunks.length || state === 'idle') { if (n >= chunks.length) setState('idle'); return; }
    const u = new SpeechSynthesisUtterance(chunks[n++].trim());
    if (voice) u.voice = voice;
    u.lang = voice?.lang || 'en-US'; u.rate = 1.02; u.pitch = 1;
    u.onend = speak;
    u.onerror = (e) => { if (e.error !== 'interrupted' && e.error !== 'canceled') toast('Speech stopped: ' + e.error); setState('idle'); };
    speechSynthesis.speak(u);
  };
  setState('speaking');
  speak();
}
export function stop() { if (!supported()) return; state = 'idle'; speechSynthesis.cancel(); paint(); }

function mount() {
  const hero = $('#briefHero');
  if (!hero || $('#briefVoice') || !hero.querySelector('h2')) return;
  const box = document.createElement('div'); box.id = 'briefVoice';
  (hero.querySelector('.bh-r') || hero).appendChild(box);
  paint();
}

export function initVoice() {
  if (!supported()) return;          // no Web Speech API: nothing is injected
  const st = document.createElement('style'); st.id = 'vbStyle'; st.textContent = CSS; document.head.appendChild(st);
  const hero = $('#briefHero');
  if (!hero) return;
  new MutationObserver(() => mount()).observe(hero, { childList: true });
  mount();
  speechSynthesis.onvoiceschanged = () => { voice = pickVoice(); };
  voice = pickVoice();
  // leaving the briefing page or closing the tab stops the reader
  document.addEventListener('visibilitychange', () => { if (document.hidden && state !== 'idle') stop(); });
  $('#nav')?.addEventListener('click', (e) => { const a = e.target.closest('a[data-page]'); if (a && a.dataset.page !== 'briefing' && state !== 'idle') stop(); });
  window.LE = Object.assign(window.LE || {}, { listen: play, stopListening: stop });
}
