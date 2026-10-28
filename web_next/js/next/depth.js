// Depth + motion for PC pages (2026-10-28, owner: "make it look sick, very 3D"). Presentation only, no data:
//   depth(root, kind)   numbers in [data-dp-n="key"] count up the first time they show (or change), and the page gets
//                       .dp-enter for its play-in when it was not drawn in the last minute (a 15-30 s refresh keeps still)
//   tilt                every .dp-tilt card leans toward the mouse with a light that follows it (--rx --ry --mx --my
//                       --px --py on the card; the CSS lives with the page, e.g. css/insight.css)
// Off with prefers-reduced-motion or Settings > Motion off; no tilt on touch screens. The HTML always holds the final
// numbers: the animation only plays them in. The real-account cards have the same look built into realcore.js (it is
// shared with the phone app, which cannot import this module).
const still = () => document.documentElement.dataset.motion === 'off' || matchMedia('(prefers-reduced-motion: reduce)').matches;
const SEEN = {}, NUM = {};
const RE = /^([^\d]*?)(\d[\d,]*(?:\.\d+)?)([\s\S]*)$/;

function count(el, fresh) {
  const key = el.dataset.dpN, txt = el.textContent, m = txt.match(RE);
  if (!m) { delete NUM[key]; return; }
  const to = parseFloat(m[2].replace(/,/g, '')), dec = (m[2].split('.')[1] || '').length;
  const from = fresh || !(key in NUM) ? 0 : NUM[key];
  NUM[key] = to;
  if (from === to || !Number.isFinite(to)) return;
  const f = (v) => m[1] + v.toLocaleString('en-US', { minimumFractionDigits: dec, maximumFractionDigits: dec }) + m[3];
  const t0 = performance.now(), D = fresh ? 1100 : 700;
  el.textContent = f(from);
  const step = (now) => {
    if (!el.isConnected) return;
    const q = Math.min(1, (now - t0) / D), e = 1 - (1 - q) ** 3;
    el.textContent = q < 1 ? f(from + (to - from) * e) : txt;
    if (q < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

export function depth(root, kind = 'page') {
  if (!root) return;
  initTilt();
  const now = Date.now(), fresh = !SEEN[kind] || now - SEEN[kind] > 60000;
  SEEN[kind] = now;
  const nums = root.querySelectorAll('[data-dp-n]');
  if (still()) { nums.forEach((el) => { const m = el.textContent.match(RE); if (m) NUM[el.dataset.dpN] = parseFloat(m[2].replace(/,/g, '')); }); return; }
  if (fresh) { root.classList.add('dp-enter'); setTimeout(() => root.classList.remove('dp-enter'), 2200); }
  nums.forEach((el) => count(el, fresh));
}

let tiltOn = false;
function initTilt() {
  if (tiltOn) return;
  tiltOn = true;
  const fine = matchMedia('(hover: hover) and (pointer: fine)');
  let cur = null, ev = null, raf = 0;
  const reset = (c) => { c.classList.remove('dp-tilting'); for (const p of ['--rx', '--ry', '--px', '--py', '--mx', '--my']) c.style.removeProperty(p); };
  const frame = () => {
    raf = 0;
    const e = ev;
    let c = e?.target?.closest ? e.target.closest('.dp-tilt') : null, up;
    while (c?.parentElement && (up = c.parentElement.closest('.dp-tilt'))) c = up;   // the outermost card under the mouse
    if (cur && cur !== c) reset(cur);
    cur = c;
    if (!c) return;
    const r = c.getBoundingClientRect(), x = (e.clientX - r.left) / r.width, y = (e.clientY - r.top) / r.height;
    const k = 6 * Math.min(1, 340 / Math.max(r.width, r.height));                  // small cards lean up to 6 deg, wide ones less
    c.classList.add('dp-tilting');
    c.style.setProperty('--ry', ((x - 0.5) * k).toFixed(2) + 'deg'); c.style.setProperty('--rx', ((0.5 - y) * k).toFixed(2) + 'deg');
    c.style.setProperty('--px', ((x - 0.5) * 2).toFixed(3)); c.style.setProperty('--py', ((y - 0.5) * 2).toFixed(3));
    c.style.setProperty('--mx', (x * 100).toFixed(1) + '%'); c.style.setProperty('--my', (y * 100).toFixed(1) + '%');
  };
  document.addEventListener('pointermove', (e) => {
    if (e.pointerType !== 'mouse' || !fine.matches || still()) { if (cur) { reset(cur); cur = null; } return; }
    ev = e; if (!raf) raf = requestAnimationFrame(frame);
  }, { passive: true });
  document.documentElement.addEventListener('pointerleave', () => { if (cur) { reset(cur); cur = null; } }, { passive: true });
}
