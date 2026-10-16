// Dashboard kit: shared helpers for the cockpit widgets (time, animated numbers, SVG gauges, heat colours,
// "waiting for data" states, cached fetches, CSV / PNG export). No data is ever invented: callers pass null and get a waiting state.
import { esc, css, etParts, etOffset, fmt$, fmtN, store, toast, downloadFile } from '../util.js';

// ------------------------------------------------------------------ New York time
export const KZ = [{ id: 'am', name: 'NY AM killzone', a: 570, b: 690 }, { id: 'pm', name: 'NY PM killzone', a: 810, b: 930 }];
export const LAUNCH_TS = etToTs(2026, 10, 18, 18, 0);          // Sunday 2026-10-18 18:00 ET: TradingView alerts go live

// UTC seconds of an ET wall-clock moment (DST-safe: two passes over the offset)
export function etToTs(y, mo, d, h = 0, mi = 0) {
  const wall = Date.UTC(y, mo - 1, d, h, mi) / 1000;
  let t = wall - etOffset(wall);
  t = wall - etOffset(t);
  return t;
}
export function etNow(ts = Date.now() / 1000) {
  const p = etParts(ts);
  const dow = new Date(Date.UTC(p.y, p.mo - 1, p.d)).getUTCDay();
  return { ts, p, dow, mod: p.h * 60 + p.mi + p.s / 60, date: `${p.y}-${String(p.mo).padStart(2, '0')}-${String(p.d).padStart(2, '0')}` };
}
export const marketOpen = (n = etNow()) => !(n.dow === 6 || (n.dow === 5 && n.mod >= 1020) || (n.dow === 0 && n.mod < 1080) || (n.mod >= 1020 && n.mod < 1080));

// the current / next killzone: {state:'live'|'next', kz, start, end, secs}
export function killzone(ts = Date.now() / 1000) {
  for (let k = 0; k < 9; k++) {
    const n = etNow(ts + k * 86400);
    if (n.dow === 0 || n.dow === 6) continue;
    for (const z of KZ) {
      const s = etToTs(n.p.y, n.p.mo, n.p.d, Math.floor(z.a / 60), z.a % 60), e = etToTs(n.p.y, n.p.mo, n.p.d, Math.floor(z.b / 60), z.b % 60);
      if (ts < e) return ts >= s ? { state: 'live', kz: z, start: s, end: e, secs: e - ts } : { state: 'next', kz: z, start: s, end: e, secs: s - ts };
    }
  }
  return null;
}
export function dur(secs, { short = false } = {}) {
  if (secs == null || !isFinite(secs)) return '—';
  secs = Math.max(0, Math.floor(secs));
  const d = Math.floor(secs / 86400), h = Math.floor(secs % 86400 / 3600), m = Math.floor(secs % 3600 / 60), s = secs % 60;
  const pad = (v) => String(v).padStart(2, '0');
  if (short) return d ? `${d}d ${h}h` : h ? `${h}h ${pad(m)}m` : m ? `${m}m ${pad(s)}s` : `${s}s`;
  return (d ? `${d}d ` : '') + `${pad(h)}:${pad(m)}:${pad(s)}`;
}
export const ago = (secs) => secs == null ? '—' : secs < 60 ? `${Math.round(secs)}s ago` : secs < 3600 ? `${Math.round(secs / 60)}m ago` : secs < 86400 ? `${(secs / 3600).toFixed(1)}h ago` : `${Math.round(secs / 86400)}d ago`;
// Monday (yyyy-mm-dd) of the week holding a yyyy-mm-dd date
export function weekOf(date) {
  const [y, m, d] = date.split('-').map(Number);
  const t = new Date(Date.UTC(y, m - 1, d));
  const dow = t.getUTCDay();
  t.setUTCDate(t.getUTCDate() - ((dow + 6) % 7));
  return t.toISOString().slice(0, 10);
}
// CME trading day of "now": after 18:00 ET it is already tomorrow's session (Fri 17:00 → Sun 18:00 counts as the next Monday)
export function tradingDate(ts = Date.now() / 1000) {
  const n = etNow(ts + 6 * 3600);
  let t = new Date(Date.UTC(n.p.y, n.p.mo - 1, n.p.d));
  while (t.getUTCDay() === 0 || t.getUTCDay() === 6) t.setUTCDate(t.getUTCDate() + 1);
  return t.toISOString().slice(0, 10);
}

// ------------------------------------------------------------------ animated numbers
const reduced = () => document.documentElement.dataset.motion === 'off' || matchMedia('(prefers-reduced-motion: reduce)').matches;
// tween an element's number from its last value to v; flashes up / down. fmt formats the in-between values.
export function tickTo(el, v, fmt = (x) => fmtN(x, 0), { dur: ms = 650, flash = true } = {}) {
  if (!el) return;
  if (v == null || !isFinite(v)) { el.textContent = '—'; el._v = null; return; }
  const from = el._v;
  el._v = v;
  if (from == null || reduced() || from === v) { el.textContent = fmt(v); return; }
  if (flash) { el.classList.remove('flash-up', 'flash-dn'); void el.offsetWidth; el.classList.add(v > from ? 'flash-up' : 'flash-dn'); }
  const t0 = performance.now();
  cancelAnimationFrame(el._raf);
  const step = (now) => {
    const k = Math.min(1, (now - t0) / ms), e = 1 - Math.pow(1 - k, 3);
    el.textContent = fmt(from + (v - from) * e);
    if (k < 1) el._raf = requestAnimationFrame(step); else el.textContent = fmt(v);
  };
  el._raf = requestAnimationFrame(step);
}

// ------------------------------------------------------------------ SVG pieces
// ring gauge (0..1) with a centred value: used for killzone countdown, readiness, pass odds
export function ring(frac, { size = 120, stroke = 10, color = 'var(--accent)', track = 'var(--surface-3)', value = '', unit = '', glow = true, cls = '' } = {}) {
  const r = (size - stroke) / 2 - 2, c = size / 2, len = 2 * Math.PI * r, f = Math.max(0, Math.min(1, frac || 0));
  return `<svg class="ring ${cls}" viewBox="0 0 ${size} ${size}" width="${size}" height="${size}" aria-hidden="true">
    <circle cx="${c}" cy="${c}" r="${r}" fill="none" stroke="${track}" stroke-width="${stroke}"/>
    <circle class="ring-arc" cx="${c}" cy="${c}" r="${r}" fill="none" stroke="${color}" stroke-width="${stroke}" stroke-linecap="round"
      stroke-dasharray="${len.toFixed(2)}" stroke-dashoffset="${(len * (1 - f)).toFixed(2)}" transform="rotate(-90 ${c} ${c})" ${glow ? `style="filter:drop-shadow(0 0 5px ${color})"` : ''}/>
    ${value !== '' ? `<text x="${c}" y="${c + (unit ? 1 : 5)}" text-anchor="middle" class="ring-v">${esc(value)}</text>` : ''}
    ${unit ? `<text x="${c}" y="${c + 15}" text-anchor="middle" class="ring-u">${esc(unit)}</text>` : ''}</svg>`;
}
// half-arc speedometer (0..1) with optional threshold tick
export function arcGauge(frac, { color = 'var(--accent)', value = '', unit = '', mark = null, w = 150 } = {}) {
  const r = 52, cx = 70, cy = 66, f = Math.max(0, Math.min(1, frac || 0));
  const P = (a) => [cx + r * Math.cos(Math.PI * (1 + a)), cy + r * Math.sin(Math.PI * (1 + a))];
  const [sx, sy] = P(0), [ex, ey] = P(1), len = Math.PI * r;
  const track = `M${sx} ${sy} A${r} ${r} 0 0 1 ${ex} ${ey}`;
  let tick = '';
  if (mark != null) { const [mx, my] = P(mark), [mx2, my2] = [cx + (r + 9) * Math.cos(Math.PI * (1 + mark)), cy + (r + 9) * Math.sin(Math.PI * (1 + mark))]; tick = `<line x1="${mx}" y1="${my}" x2="${mx2}" y2="${my2}" stroke="var(--ink-2)" stroke-width="2"/>`; }
  return `<svg class="arcg" viewBox="0 0 140 84" width="${w}" aria-hidden="true"><path d="${track}" fill="none" stroke="var(--surface-3)" stroke-width="10" stroke-linecap="round"/>
    <path class="ring-arc" d="${track}" fill="none" stroke="${color}" stroke-width="10" stroke-linecap="round" stroke-dasharray="${len.toFixed(1)}" stroke-dashoffset="${(len * (1 - f)).toFixed(1)}" style="filter:drop-shadow(0 0 5px ${color})"/>
    ${tick}<text x="${cx}" y="${cy - 6}" text-anchor="middle" class="ring-v">${esc(value)}</text><text x="${cx}" y="${cy + 10}" text-anchor="middle" class="ring-u">${esc(unit)}</text></svg>`;
}
// sparkline path in a w×h box (null-safe)
export function spark(vals, { w = 120, h = 32, color = 'var(--accent)', fill = true, zero = false } = {}) {
  const v = (vals || []).filter(x => x != null && isFinite(x));
  if (v.length < 2) return '';
  let lo = Math.min(...v), hi = Math.max(...v);
  if (zero) { lo = Math.min(lo, 0); hi = Math.max(hi, 0); }
  const span = hi - lo || 1;
  const pts = v.map((x, i) => [i / (v.length - 1) * (w - 2) + 1, h - 2 - (x - lo) / span * (h - 4)]);
  const line = pts.map((p, i) => (i ? 'L' : 'M') + p[0].toFixed(1) + ' ' + p[1].toFixed(1)).join(' ');
  const id = 'ks' + Math.random().toString(36).slice(2, 8);
  const z = zero && lo < 0 && hi > 0 ? `<line x1="0" x2="${w}" y1="${(h - 2 - (0 - lo) / span * (h - 4)).toFixed(1)}" y2="${(h - 2 - (0 - lo) / span * (h - 4)).toFixed(1)}" stroke="var(--muted)" stroke-dasharray="2 3" opacity=".6"/>` : '';
  const [ex, ey] = pts.at(-1);
  return `<svg class="kspark" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" aria-hidden="true">
    <defs><linearGradient id="${id}" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="${color}" stop-opacity=".32"/><stop offset="1" stop-color="${color}" stop-opacity="0"/></linearGradient></defs>
    ${z}${fill ? `<path d="${line} L${w - 1} ${h} L1 ${h} Z" fill="url(#${id})"/>` : ''}<path d="${line}" fill="none" stroke="${color}" stroke-width="1.6" vector-effect="non-scaling-stroke" stroke-linejoin="round"/>
    <circle cx="${ex}" cy="${ey}" r="2.2" fill="${color}"/></svg>`;
}
// horizontal progress bar with optional band markers [{at:0..1,label}]
export function bar(frac, { color = 'var(--accent)', marks = [], cls = '' } = {}) {
  const f = Math.max(0, Math.min(1, frac || 0));
  return `<div class="kbar ${cls}"><div class="kbar-fill" style="width:${(f * 100).toFixed(1)}%;--c:${color}"></div>
    ${marks.map(m => `<i class="kbar-mark" style="left:${(Math.max(0, Math.min(1, m.at)) * 100).toFixed(1)}%" title="${esc(m.label || '')}"></i>`).join('')}</div>`;
}

// diverging heat colour (good above zero, bad below) as a CSS color-mix string
export function heat(v, max, { neutral = 'var(--surface-2)' } = {}) {
  if (v == null || !isFinite(v) || !max) return neutral;
  const k = Math.min(1, Math.abs(v) / max);
  const pct = Math.round(12 + k * 70);
  return `color-mix(in srgb, ${v >= 0 ? 'var(--good)' : 'var(--bad)'} ${pct}%, ${neutral})`;
}
// sequential (0..1) accent heat
export const heatSeq = (k, col = 'var(--accent)') => `color-mix(in srgb, ${col} ${Math.round(8 + Math.max(0, Math.min(1, k)) * 75)}%, var(--surface-2))`;

// ------------------------------------------------------------------ states
export function waiting(title = 'Waiting for data', sub = '') {
  return `<div class="wait"><div class="wait-dots"><i></i><i></i><i></i></div><b>${esc(title)}</b>${sub ? `<span>${sub}</span>` : ''}</div>`;
}
export const stat = (k, v, sub = '', c = '') => `<div class="kst"><div class="k">${k}</div><div class="v ${c}">${v}</div>${sub ? `<div class="s">${sub}</div>` : ''}</div>`;

// ------------------------------------------------------------------ cached fetch (null on 404 / network error; never throws)
const _cache = new Map();
export async function getJSON(path, { ttl = 30000, body } = {}) {
  const key = path + (body ? JSON.stringify(body) : '');
  const hit = _cache.get(key);
  if (hit && (Date.now() - hit.t < ttl)) return hit.p;
  const p = (async () => {
    try {
      const r = await fetch(path, body === undefined ? {} : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
      if (!r.ok) return null;
      const j = await r.json();
      return j && !j.error ? j : null;
    } catch { return null; }
  })();
  _cache.set(key, { t: Date.now(), p });
  const v = await p;
  if (v == null) _cache.set(key, { t: Date.now() - ttl + 8000, p });   // retry a miss after ~8s, not every render
  return v;
}

// ------------------------------------------------------------------ export
export function toCSV(rows, cols) {
  if (!rows?.length) return '';
  cols = cols || Object.keys(rows[0]);
  const q = (v) => { const s = v == null ? '' : typeof v === 'object' ? JSON.stringify(v) : String(v); return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s; };
  return [cols.join(','), ...rows.map(r => cols.map(c => q(r[c])).join(','))].join('\n');
}
export function saveCSV(name, rows, cols) {
  const txt = toCSV(rows, cols);
  if (!txt) { toast('Nothing to export yet'); return; }
  downloadFile(name.endsWith('.csv') ? name : name + '.csv', txt, 'text/csv');
}
let _h2c = null;
function loadH2C() {
  if (window.html2canvas) return Promise.resolve(window.html2canvas);
  if (_h2c) return _h2c;
  _h2c = new Promise((res, rej) => {
    const s = document.createElement('script');
    s.src = 'https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js';
    s.onload = () => res(window.html2canvas); s.onerror = () => { _h2c = null; rej(new Error('could not load html2canvas')); };
    document.head.appendChild(s);
  });
  return _h2c;
}
export async function savePNG(el, name) {
  try {
    toast('Rendering snapshot…', 1500);
    const h2c = await loadH2C();
    const bg = css('--page') || '#05080f';
    const canvas = await h2c(el, { backgroundColor: bg, scale: Math.min(2, window.devicePixelRatio || 1), logging: false, useCORS: true });
    const a = document.createElement('a');
    a.href = canvas.toDataURL('image/png');
    a.download = `${name}_${new Date().toISOString().slice(0, 16).replace(/[:T]/g, '-')}.png`;
    a.click();
  } catch (e) { toast('Snapshot failed: ' + e.message, 3500); }
}

// tiny persisted prefs for the dashboard layer
export const pref = {
  get: (k, d) => store.get('dash.' + k, d),
  set: (k, v) => store.set('dash.' + k, v),
};
export const money = (v) => fmt$(v);
