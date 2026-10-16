// ---------- formatting
export const fmt$ = (v, d = 0) => (v == null || isNaN(v)) ? '—' : (v < 0 ? '-$' : '$') + Math.abs(v).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });
export const fmtS$ = (v, d = 0) => (v == null || isNaN(v)) ? '—' : (v > 0 ? '+' : '') + fmt$(v, d);
export const fmtN = (v, d = 2) => (v == null || isNaN(v)) ? '—' : Number(v).toLocaleString('en-US', { minimumFractionDigits: d, maximumFractionDigits: d });
export const fmtR = (v) => (v == null || isNaN(v)) ? '—' : (v > 0 ? '+' : '') + Number(v).toFixed(2) + 'R';
export const cls = (v) => v > 0 ? 'up' : v < 0 ? 'dn' : '';
export const $ = (s, el = document) => el.querySelector(s);
export const $$ = (s, el = document) => [...el.querySelectorAll(s)];
export const esc = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
export const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
export const clamp = (x, a, b) => Math.max(a, Math.min(b, x));

// ---------- New York time.  Chart time = UTC seconds shifted by the ET offset, so the chart's axis reads ET.
const offCache = new Map();
const dtf = new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', hourCycle: 'h23', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit' });
export function etParts(ts) {
  const p = {};
  for (const x of dtf.formatToParts(new Date(ts * 1000))) p[x.type] = x.value;
  return { y: +p.year, mo: +p.month, d: +p.day, h: +p.hour, mi: +p.minute, s: +p.second };
}
export function etOffset(ts) {
  const k = Math.floor(ts / 3600);
  let v = offCache.get(k);
  if (v === undefined) {
    const p = etParts(k * 3600);
    v = (Date.UTC(p.y, p.mo - 1, p.d, p.h, p.mi, p.s) / 1000) - k * 3600;
    offCache.set(k, v);
  }
  return v;
}
export const toChart = (ts) => ts + etOffset(ts);
export const fromChart = (ct) => ct - etOffset(ct - etOffset(ct));
export function etStr(ts, withDate = false) {
  const p = etParts(ts);
  const hm = `${String(p.h).padStart(2, '0')}:${String(p.mi).padStart(2, '0')}`;
  return withDate ? `${p.y}-${String(p.mo).padStart(2, '0')}-${String(p.d).padStart(2, '0')} ${hm}` : hm;
}
// CME trading day (18:00 ET -> 17:00 ET) of a UTC timestamp
export function tradingDay(ts) {
  const p = etParts(ts + 6 * 3600);
  return `${p.y}-${String(p.mo).padStart(2, '0')}-${String(p.d).padStart(2, '0')}`;
}
// chart-time of an ET wall-clock moment on a calendar date (yyyy-mm-dd)
export function etWall(dateStr, minutes) {
  const [y, m, d] = dateStr.split('-').map(Number);
  return Date.UTC(y, m - 1, d, 0, 0, 0) / 1000 + minutes * 60;
}
export function prevCalDate(dateStr) {
  const [y, m, d] = dateStr.split('-').map(Number);
  const t = new Date(Date.UTC(y, m - 1, d) - 86400000);
  return t.toISOString().slice(0, 10);
}

// ---------- api
export async function api(path, body) {
  const opt = body === undefined ? {} : { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) };
  const r = await fetch(path, opt);
  const j = await r.json();
  if (!r.ok || j.error) throw new Error(j.error || r.statusText);
  return j;
}

// ---------- tiny store
export const store = {
  get(k, d) { try { const v = localStorage.getItem('le.' + k); return v == null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem('le.' + k, JSON.stringify(v)); } catch { } },
};

export function toast(msg, ms = 2400) {
  const t = $('#toast');
  t.textContent = msg; t.classList.add('on');
  clearTimeout(t._h); t._h = setTimeout(() => t.classList.remove('on'), ms);
}
export function busy(on) { $('#busy').classList.toggle('on', !!on); }

export function seg(el, items, value, onChange) {
  el.innerHTML = items.map(([v, label]) => `<button data-v="${esc(v)}" class="${String(v) === String(value) ? 'on' : ''}">${label}</button>`).join('');
  el.onclick = (e) => {
    const b = e.target.closest('button'); if (!b) return;
    $$('button', el).forEach(x => x.classList.toggle('on', x === b));
    onChange(b.dataset.v);
  };
}
export function downloadFile(name, text, type = 'text/plain') {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([text], { type }));
  a.download = name; a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 2000);
}
export function lowerBound(arr, x) { let lo = 0, hi = arr.length; while (lo < hi) { const m = (lo + hi) >> 1; if (arr[m] < x) lo = m + 1; else hi = m; } return lo; }
