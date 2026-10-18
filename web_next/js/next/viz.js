// Small SVG charts for the new pages: area line with crosshair tooltip, diverging bars with per-bar tooltip.
// Thin marks, recessive grid, one axis, text in ink tokens. Colors come from CSS tokens (--accent, --good, --bad).
import { esc } from '../util.js';

let uid = 0;
const fmtK = (v) => (v < 0 ? '−' : '') + '$' + (Math.abs(v) >= 1000 ? (Math.abs(v) / 1000).toFixed(Math.abs(v) >= 10000 ? 0 : 1) + 'k' : Math.round(Math.abs(v)));

function ticks(lo, hi, n = 4) {
  const span = hi - lo || 1, step0 = span / n, mag = Math.pow(10, Math.floor(Math.log10(step0)));
  const step = [1, 2, 2.5, 5, 10].map(m => m * mag).find(s => s >= step0) || step0;
  const out = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(+v.toFixed(6));
  return out;
}

// points: [{x: label, y: number, tip?: html}]
export function lineChart(el, points, { h = 220, fmt = fmtK, zero = true, color = 'var(--accent)', ref = null } = {}) {
  if (!el) return;
  if (!points?.length) { el.innerHTML = '<div class="empty">No data.</div>'; return; }
  const W = Math.max(320, el.clientWidth || 640), H = h, L = 52, R = 12, T = 12, B = 24;
  const ys = points.map(p => p.y).concat(zero ? [0] : []).concat(ref != null ? [ref] : []);
  let lo = Math.min(...ys), hi = Math.max(...ys);
  const pad = (hi - lo) * 0.06 || 1; lo -= pad; hi += pad;
  const X = (i) => L + (points.length === 1 ? 0 : i / (points.length - 1) * (W - L - R));
  const Y = (v) => T + (1 - (v - lo) / (hi - lo)) * (H - T - B);
  const id = 'nxg' + (++uid);
  const line = points.map((p, i) => `${i ? 'L' : 'M'}${X(i).toFixed(1)} ${Y(p.y).toFixed(1)}`).join('');
  const base = Y(Math.max(lo, Math.min(hi, 0)));
  const tk = ticks(lo, hi);
  const xl = [0, Math.floor(points.length / 3), Math.floor(points.length * 2 / 3), points.length - 1].filter((v, i, a) => a.indexOf(v) === i);
  el.innerHTML = `<div class="nx-viz" style="height:${H}px"><svg viewBox="0 0 ${W} ${H}" width="100%" height="${H}" preserveAspectRatio="none">
    <defs><linearGradient id="${id}" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="${color}" stop-opacity=".28"/><stop offset="1" stop-color="${color}" stop-opacity="0"/></linearGradient></defs>
    ${tk.map(v => `<line x1="${L}" x2="${W - R}" y1="${Y(v)}" y2="${Y(v)}" class="nx-grid"/><text x="${L - 8}" y="${Y(v) + 4}" text-anchor="end" class="nx-axis">${fmt(v)}</text>`).join('')}
    ${zero && lo < 0 && hi > 0 ? `<line x1="${L}" x2="${W - R}" y1="${base}" y2="${base}" class="nx-zero"/>` : ''}
    ${ref != null ? `<line x1="${L}" x2="${W - R}" y1="${Y(ref)}" y2="${Y(ref)}" class="nx-ref"/>` : ''}
    <path d="${line}L${X(points.length - 1)} ${base}L${X(0)} ${base}Z" fill="url(#${id})"/>
    <path d="${line}" fill="none" stroke="${color}" stroke-width="2" vector-effect="non-scaling-stroke" stroke-linejoin="round"/>
    ${xl.map(i => `<text x="${X(i)}" y="${H - 6}" text-anchor="${i === 0 ? 'start' : i === points.length - 1 ? 'end' : 'middle'}" class="nx-axis">${esc(String(points[i].x))}</text>`).join('')}
    <line class="nx-cross" y1="${T}" y2="${H - B}" x1="-10" x2="-10"/><circle class="nx-dot" r="4.5" cx="-10" cy="-10" style="fill:${color}"/>
  </svg><div class="nx-tip" hidden></div></div>`;
  const box = el.querySelector('.nx-viz'), svg = box.querySelector('svg'), tip = box.querySelector('.nx-tip');
  const cross = svg.querySelector('.nx-cross'), dot = svg.querySelector('.nx-dot');
  const move = (e) => {
    const r = svg.getBoundingClientRect();
    const sx = (e.clientX - r.left) / r.width * W;
    const i = Math.max(0, Math.min(points.length - 1, Math.round((sx - L) / (W - L - R) * (points.length - 1))));
    const p = points[i], px = X(i), py = Y(p.y);
    cross.setAttribute('x1', px); cross.setAttribute('x2', px); dot.setAttribute('cx', px); dot.setAttribute('cy', py);
    tip.hidden = false;
    tip.innerHTML = p.tip || `<b>${esc(String(p.x))}</b><span>${fmt(p.y)}</span>`;
    const left = px / W * r.width;
    tip.style.left = Math.min(r.width - tip.offsetWidth - 4, Math.max(4, left + 12)) + 'px';
    tip.style.top = Math.max(4, py / H * r.height - 40) + 'px';
  };
  box.onpointermove = move; box.onpointerdown = move;
  box.onpointerleave = () => { tip.hidden = true; cross.setAttribute('x1', -10); cross.setAttribute('x2', -10); dot.setAttribute('cx', -10); };
}

// bars: [{x: label, y: number, tip?: html}] positive = good, negative = bad
export function barChart(el, bars, { h = 200, fmt = fmtK, labelEvery = 0 } = {}) {
  if (!el) return;
  if (!bars?.length) { el.innerHTML = '<div class="empty">No data.</div>'; return; }
  const W = Math.max(320, el.clientWidth || 640), H = h, L = 52, R = 8, T = 10, B = 22;
  let lo = Math.min(0, ...bars.map(b => b.y)), hi = Math.max(0, ...bars.map(b => b.y));
  const pad = (hi - lo) * 0.06 || 1; lo -= lo < 0 ? pad : 0; hi += pad;
  const Y = (v) => T + (1 - (v - lo) / (hi - lo)) * (H - T - B);
  const bw = (W - L - R) / bars.length, gap = Math.min(2, bw * 0.2);
  const every = labelEvery || Math.ceil(bars.length / 8);
  const tk = ticks(lo, hi);
  el.innerHTML = `<div class="nx-viz" style="height:${H}px"><svg viewBox="0 0 ${W} ${H}" width="100%" height="${H}" preserveAspectRatio="none">
    ${tk.map(v => `<line x1="${L}" x2="${W - R}" y1="${Y(v)}" y2="${Y(v)}" class="nx-grid"/><text x="${L - 8}" y="${Y(v) + 4}" text-anchor="end" class="nx-axis">${fmt(v)}</text>`).join('')}
    ${bars.map((b, i) => {
      const x = L + i * bw + gap / 2, y0 = Y(0), y1 = Y(b.y), top = Math.min(y0, y1), hh = Math.max(1, Math.abs(y1 - y0));
      return `<rect data-i="${i}" x="${x.toFixed(1)}" y="${top.toFixed(1)}" width="${Math.max(1, bw - gap).toFixed(1)}" height="${hh.toFixed(1)}" rx="${Math.min(3, (bw - gap) / 2)}" class="nx-bar ${b.y >= 0 ? 'pos' : 'neg'}"/>`;
    }).join('')}
    <line x1="${L}" x2="${W - R}" y1="${Y(0)}" y2="${Y(0)}" class="nx-zero"/>
    ${bars.map((b, i) => i % every === 0 ? `<text x="${L + i * bw + bw / 2}" y="${H - 6}" text-anchor="middle" class="nx-axis">${esc(String(b.x))}</text>` : '').join('')}
  </svg><div class="nx-tip" hidden></div></div>`;
  const box = el.querySelector('.nx-viz'), svg = box.querySelector('svg'), tip = box.querySelector('.nx-tip');
  const move = (e) => {
    const r = svg.getBoundingClientRect();
    const i = Math.max(0, Math.min(bars.length - 1, Math.floor(((e.clientX - r.left) / r.width * W - L) / bw)));
    const b = bars[i];
    svg.querySelectorAll('.nx-bar.hl').forEach(x => x.classList.remove('hl'));
    svg.querySelector(`.nx-bar[data-i="${i}"]`)?.classList.add('hl');
    tip.hidden = false;
    tip.innerHTML = b.tip || `<b>${esc(String(b.x))}</b><span>${fmt(b.y)}</span>`;
    const left = (L + i * bw + bw / 2) / W * r.width;
    tip.style.left = Math.min(r.width - tip.offsetWidth - 4, Math.max(4, left + 10)) + 'px';
    tip.style.top = '6px';
  };
  box.onpointermove = move; box.onpointerdown = move;
  box.onpointerleave = () => { tip.hidden = true; svg.querySelectorAll('.nx-bar.hl').forEach(x => x.classList.remove('hl')); };
}

// animated count-up for a number element: el.dataset.v = target, format fn
export function countTo(el, target, fmt, dur = 750) {
  if (!el) return;
  if (matchMedia('(prefers-reduced-motion: reduce)').matches || !isFinite(target)) { el.textContent = fmt(target); return; }
  const t0 = performance.now();
  const step = (now) => {
    const k = Math.min(1, (now - t0) / dur), e = 1 - Math.pow(1 - k, 3);
    el.textContent = fmt(target * e);
    if (k < 1) requestAnimationFrame(step); else el.textContent = fmt(target);
  };
  requestAnimationFrame(step);
}
export function countAll(root) {
  root.querySelectorAll('[data-count]').forEach(el => {
    const v = +el.dataset.count, kind = el.dataset.fmt || 'n', dec = +(el.dataset.dec || 0);
    const f = kind === '$' ? (x) => (x < 0 ? '−$' : '$') + Math.abs(x).toLocaleString('en-US', { maximumFractionDigits: 0 })
      : kind === 's$' ? (x) => (x > 0 ? '+$' : x < 0 ? '−$' : '$') + Math.abs(x).toLocaleString('en-US', { maximumFractionDigits: 0 })
        : kind === '%' ? (x) => x.toFixed(dec) + '%'
          : kind === 'r' ? (x) => (x > 0 ? '+' : '') + x.toFixed(dec || 2) + 'R'
            : (x) => x.toLocaleString('en-US', { minimumFractionDigits: dec, maximumFractionDigits: dec });
    countTo(el, v, f);
  });
}
