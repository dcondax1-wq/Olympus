// OLYMPUS Mind: the small DOM helpers every overlay module shares. Vault text only ever goes in through textContent.
//   $(id), el(tag, props, kids), svg(tag, attrs, kids), fmt / big (numbers), ago(t, now), dayKey / dayLabel (local days)
export const $ = (id) => document.getElementById(id);
export const fmt = new Intl.NumberFormat('en-US');
const compact = new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 1 });
export const big = (n) => (n >= 10000 ? compact.format(n) : fmt.format(n));     // 12.3K fits a stat tile

/** el('button', {class, text, style: {'--c': x}, onclick, 'aria-label': ...}, [children]) */
export function el(tag, props = {}, kids = []) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (v == null || v === false) continue;
    if (k === 'text') e.textContent = v;
    else if (k === 'style') for (const [p, x] of Object.entries(v)) e.style.setProperty(p, x);
    else if (k.startsWith('on')) e.addEventListener(k.slice(2), v);
    else e.setAttribute(k, v === true ? '' : v);
  }
  for (const c of kids) if (c != null && c !== false) e.append(c);
  return e;
}

const SVGNS = ['http:', '', 'www.w3.org', '2000', 'svg'].join('/');     // the SVG namespace name (an identifier, nothing is fetched from it)
export function svg(tag, attrs = {}, kids = []) {
  const e = document.createElementNS(SVGNS, tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v == null) continue;
    if (k === 'text') e.textContent = v;
    else if (k.startsWith('on')) e.addEventListener(k.slice(2), v);
    else e.setAttribute(k, v);
  }
  for (const c of kids) if (c != null) e.append(c);
  return e;
}

export function ago(t, now = Date.now()) {
  if (!t) return 'unknown';
  const s = Math.max(0, (now - t) / 1000);
  if (s < 60) return 'just now';
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  if (s < 86400 * 30) return `${Math.floor(s / 86400)} d ago`;
  const d = new Date(t), sameYear = d.getFullYear() === new Date(now).getFullYear();
  return d.toLocaleDateString('en-US', sameYear ? { month: 'short', day: 'numeric' } : { month: 'short', year: 'numeric' });
}

/** The local calendar day of a time, as YYYY-MM-DD. */
export function dayKey(t) {
  const d = new Date(t);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

/** 'Today', 'Yesterday' or 'Mon, Nov 2' for a YYYY-MM-DD key. */
export function dayLabel(key, now = Date.now()) {
  if (key === dayKey(now)) return 'Today';
  if (key === dayKey(now - 864e5)) return 'Yesterday';
  const [y, m, d] = key.split('-').map(Number);
  return new Date(y, m - 1, d).toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
}
