import { store } from './util.js';

// [id, name, mode, description, swatches: page, surface, accent, up, down, ink, display font]
export const SKINS = [
  ['obsidian', 'AGORA', 'dark', 'Marble, bronze and gold on warm night. The OLYMPUS look, the default.', ['#14110e', '#1d1914', '#c8a24a', '#7f8a52', '#c96a4a', '#f3ece0'], 'Iowan Old Style'],
  ['gold', 'Gold Rush', 'dark', 'Black and gold with gilded numbers and a wide wordmark.', ['#070604', '#110e08', '#e6b450', '#e6b450', '#6b5a3a', '#fbf3e0'], 'Unbounded'],
  ['carbon', 'Carbon', 'dark', 'Graphite monochrome, grotesk type. Nothing loud.', ['#0e0e0f', '#161618', '#f5f5f5', '#e8e8e8', '#5a5a60', '#f5f5f5'], 'Space Grotesk'],
  ['arctic', 'Arctic', 'light', 'Crisp icy light theme.', ['#e6eff8', '#fbfdff', '#0077ff', '#0f9d58', '#e0353b', '#0a1726'], 'Oxanium'],
  ['swiss', 'Swiss', 'light', 'White paper, black ink, international orange. Flat.', ['#f6f6f4', '#ffffff', '#ff4f00', '#111111', '#ff4f00', '#111111'], 'Space Grotesk'],
].map(([id, name, mode, desc, sw, font]) => ({ id, name, mode, desc, sw, font }));

const DEFAULTS = { skin: 'obsidian', density: 'comfortable', ticker: false, motion: true, hollow: false, accent: null, sound: false };
export const A = { ...DEFAULTS, ...store.get('appearance', {}) };
// one-time move to the redesigned look; any theme picked after this is kept
if (!store.get('nxSkinMigrated', false)) { A.skin = 'obsidian'; A.accent = null; store.set('nxSkinMigrated', true); }
// AGORA pass 2026-11-10: everyone lands on the AGORA look once; the neon skins are gone
if (!store.get('nxAgoraMigrated', false)) { A.skin = 'obsidian'; A.accent = null; store.set('nxAgoraMigrated', true); }
// clean-up pass 2026-10-25: the scrolling ticker starts off once (Settings > Appearance > Ticker tape turns it back on)
if (!store.get('nxCleanMigrated', false)) { A.ticker = false; store.set('nxCleanMigrated', true); }

const hexA = (hex, a) => {
  const n = parseInt(hex.replace('#', ''), 16);
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
};

export function applyAppearance() {
  const r = document.documentElement;
  const sk = SKINS.find(s => s.id === A.skin) || SKINS[0];
  r.dataset.skin = sk.id;
  r.dataset.theme = sk.mode;
  r.dataset.density = A.density;
  r.dataset.ticker = A.ticker ? 'on' : 'off';
  r.dataset.motion = A.motion ? 'on' : 'off';
  r.dataset.hollow = A.hollow ? 'on' : 'off';
  // the one token writer (zenithcore.js, shared with the phone and the Olympus themes); the inline path when it is missing
  const Z = window.ZenithFX, tok = { accent: A.accent || null, glow: A.accent ? hexA(A.accent, 0.35) : null };
  if (Z) Z.applyTokens(tok);
  else if (A.accent) { r.style.setProperty('--accent', A.accent); r.style.setProperty('--glow', tok.glow); }
  else { r.style.removeProperty('--accent'); r.style.removeProperty('--glow'); }
  store.set('appearance', A);
}

export function setAppearance(patch) {
  Object.assign(A, patch);
  applyAppearance();
  document.dispatchEvent(new CustomEvent('le-appearance'));
}

// ---- cursor spotlight on panels: zenithcore.js's glass (an edge light + a small tilt, the same as the phone, jfx quality,
// the Olympus theme); the old --mx / --my spotlight when it is missing. depth.js keeps its own tilt on .dp-tilt cards.
export function installSpotlight() {
  const Z = window.ZenithFX;
  if (Z) { Z.css(); Z.glass(document.body, '.card, .kpi, .guard, .pr-card, .rc-card, .bl-card, .sc-card, .mn-card', { deg: 3, skip: '.dp-tilt, .dp-tilt *' }); Z.followOlympus(); return; }
  document.addEventListener('pointermove', (e) => {
    const el = e.target.closest?.('.card, .kpi, .guard');
    if (!el) return;
    const b = el.getBoundingClientRect();
    el.style.setProperty('--mx', `${e.clientX - b.left}px`);
    el.style.setProperty('--my', `${e.clientY - b.top}px`);
  }, { passive: true });
}

// ---- count-up for headline numbers (keeps the original prefix / suffix / decimals)
export function countUp(root) {
  if (!A.motion || matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  for (const el of root.querySelectorAll('.kpi .v')) {
    const txt = el.textContent;
    const m = txt.match(/-?[\d,]*\.?\d+/);
    if (!m) continue;
    const target = parseFloat(m[0].replace(/,/g, ''));
    if (!isFinite(target) || target === 0) continue;
    const dec = (m[0].split('.')[1] || '').length;
    const pre = txt.slice(0, m.index), post = txt.slice(m.index + m[0].length);
    const t0 = performance.now(), dur = 700;
    const step = (now) => {
      const k = Math.min(1, (now - t0) / dur), e = 1 - Math.pow(1 - k, 3);
      el.textContent = pre + (target * e).toLocaleString('en-US', { minimumFractionDigits: dec, maximumFractionDigits: dec }) + post;
      if (k < 1) requestAnimationFrame(step); else el.textContent = txt;
    };
    requestAnimationFrame(step);
  }
}

// ---- deterministic mini chart for theme previews
export function previewSvg(sk) {
  const [, , acc, up, down] = sk.sw;
  let x = 6, p = 50, out = '', seed = sk.id.length * 7 + 3;
  const rnd = () => (seed = (seed * 9301 + 49297) % 233280) / 233280;
  for (let k = 0; k < 16; k++) {
    const o = p, c = p + (rnd() - 0.45) * 18, h = Math.max(o, c) + rnd() * 6, l = Math.min(o, c) - rnd() * 6;
    const col = c >= o ? up : down, y = (v) => 70 - v * 0.62;
    out += `<line x1="${x + 3}" x2="${x + 3}" y1="${y(h)}" y2="${y(l)}" stroke="${col}" stroke-width="1"/>
      <rect x="${x}" y="${Math.min(y(o), y(c))}" width="6" height="${Math.max(1.5, Math.abs(y(o) - y(c)))}" fill="${col}" rx="1"/>`;
    p = c; x += 11;
  }
  return `<svg viewBox="0 0 186 64" preserveAspectRatio="none"><line x1="0" x2="186" y1="22" y2="22" stroke="${acc}" stroke-dasharray="4 3" opacity=".8"/>${out}</svg>`;
}
