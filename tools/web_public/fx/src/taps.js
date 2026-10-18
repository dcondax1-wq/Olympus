// Tap sparks: a full-screen 2D canvas above the UI. Every tap on a control throws a ring and a spray of neon sparks.
// Time-based (same speed on slow phones), capped (fast repeated taps on one button stay small) and the loop only runs
// while sparks are alive. A tap (click, so never a scroll) on empty background goes to setBgTap's handler instead
// (index.js: a ripple through the 3D background) plus two soft rings.
const SEL = '.btn, .seg button, .tile, .trade, .tabs a, .nav a, .chipbtn, .strip button, .opt, .dd-btn, .swatch, .iconbtn, .nx-tile, .nx-trade, #nav a, .nx-tab, .nx-strip button, .nx-chipbtn, .nx-back, .nx-search, .nx-select-btn, .nx-opt, .fx-tap';
const MAX_PARTS = 260, MAX_RINGS = 8;
let cv, g, dpr = 1, parts = [], rings = [], raf = 0, last = 0, colors = ['#6d7cff', '#3ee0c8', '#ff2bd6', '#c084fc', '#ffffff'], on = true;
let lastEl = null, lastAt = 0, bgTap = null;
// anything that is not empty background: controls, cards, 3D views, sheets, navigation, media, text being selected
const BLOCK = 'a, button, input, select, textarea, label, summary, details, [role=button], [role=tab], [role=dialog], [contenteditable], .card, .nx-card, .fx3d, .hero3d, .tile, '
  + '.trade, .sheet, .modal, .menu, .dd-pop, nav, header, footer, #nav, #tabs, #sub, .sub, .nx-side, .nx-tabbar, .tabs, .chip, .chips, .seg, .strip, table, svg, img, video, canvas, ' + SEL;

function size() { dpr = Math.min(2, devicePixelRatio || 1); cv.width = innerWidth * dpr; cv.height = innerHeight * dpr; cv.style.width = innerWidth + 'px'; cv.style.height = innerHeight + 'px'; }
function loop(now) {
  raf = 0;
  const dt = Math.min(0.05, (now - last) / 1000 || 0.016), f = dt * 60; last = now;
  g.setTransform(dpr, 0, 0, dpr, 0, 0);
  g.clearRect(0, 0, innerWidth, innerHeight);
  g.globalCompositeOperation = 'lighter';
  for (const r of rings) {
    r.t += dt; if (r.t <= 0) continue;   // delayed ring: not started yet
    const k = Math.min(1, r.t / r.life), rr = r.r0 + (r.r1 - r.r0) * (1 - Math.pow(1 - k, 3));
    g.strokeStyle = r.c; g.globalAlpha = (1 - k) * 0.9; g.lineWidth = 2.2 * (1 - k) + 0.5;
    g.beginPath(); g.arc(r.x, r.y, Math.max(0.1, rr), 0, Math.PI * 2); g.stroke();
  }
  const damp = Math.pow(0.93, f);
  for (const p of parts) {
    p.t += dt; p.vx *= damp; p.vy = p.vy * damp + 0.09 * f; p.x += p.vx * f; p.y += p.vy * f;
    const a = 1 - Math.min(1, p.t / p.life);
    g.globalAlpha = a; g.fillStyle = p.c;
    g.beginPath(); g.arc(p.x, p.y, p.s * (0.6 + a * 0.6), 0, Math.PI * 2); g.fill();
    g.globalAlpha = a * 0.35; g.beginPath(); g.arc(p.x, p.y, p.s * 3.2 * a + 1, 0, Math.PI * 2); g.fill();
  }
  g.globalAlpha = 1; g.globalCompositeOperation = 'source-over';
  parts = parts.filter(p => p.t < p.life); rings = rings.filter(r => r.t < r.life);
  if (parts.length || rings.length) raf = requestAnimationFrame(loop); else g.clearRect(0, 0, innerWidth, innerHeight);
}
export function spark(x, y, n = 18, palette = colors, power = 1) {
  if (!cv || !on) return;
  n = Math.min(n, MAX_PARTS - parts.length);
  for (let i = 0; i < n; i++) {
    const a = Math.random() * Math.PI * 2, sp = (1.6 + Math.random() * 4.2) * power;
    parts.push({ x, y, vx: Math.cos(a) * sp, vy: Math.sin(a) * sp - 1.2 * power, t: 0, life: (26 + Math.random() * 24) / 60, s: 1 + Math.random() * 1.8, c: palette[i % palette.length] });
  }
  rings.push({ x, y, r0: 4, r1: 34 * power, t: 0, life: 26 / 60, c: palette[0] });
  rings.push({ x, y, r0: 2, r1: 20 * power, t: -4 / 60, life: 30 / 60, c: palette[1] || palette[0] });
  if (rings.length > MAX_RINGS) rings.splice(0, rings.length - MAX_RINGS);
  if (!raf) { last = performance.now(); raf = requestAnimationFrame(loop); }
}
export function initTaps(opts = {}) {
  if (cv) return;
  cv = document.createElement('canvas'); cv.className = 'fx-taps'; cv.setAttribute('aria-hidden', 'true');
  Object.assign(cv.style, { position: 'fixed', inset: '0', pointerEvents: 'none', zIndex: '1400' });
  document.body.appendChild(cv); g = cv.getContext('2d'); size();
  addEventListener('resize', size);
  document.addEventListener('pointerdown', (e) => {
    if (!on || !e.isPrimary) return;
    const t = e.target.closest?.(SEL); if (!t || t.disabled) return;
    // the same control tapped again quickly (stepping a replay, say) only gets a small puff
    const now = performance.now(), rapid = t === lastEl && now - lastAt < 350; lastEl = t; lastAt = now;
    const big = t.matches('.tile, .nx-tile, .trade, .nx-trade, .btn.primary');
    spark(e.clientX, e.clientY, rapid ? 6 : big ? 26 : 16, colors, rapid ? 0.6 : big ? 1.25 : 1);
  }, { passive: true, capture: true });
  document.addEventListener('click', (e) => {
    if (!on || !bgTap || e.button !== 0) return;
    const t = e.target; if (!t || !t.closest || t.closest(BLOCK)) return;
    try { if (String(getSelection?.() || '').length) return; } catch { }
    if (bgTap(e.clientX, e.clientY) !== false) spark(e.clientX, e.clientY, 0, [colors[2] || colors[0], colors[1] || colors[0]], 1.5);
  }, { passive: true, capture: true });
  if (opts.colors) colors = opts.colors;
}
export function setBgTap(fn) { bgTap = fn; }
export function setTapColors(c) { colors = c; }
export function setTaps(v) { on = v; }
