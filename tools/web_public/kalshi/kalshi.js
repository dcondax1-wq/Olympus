/* Kalshi page (tools/web_public/kalshi/, owner 2026-11-01). The Kalshi bot runs 24/7 on its own server with real money; its
   numbers reach the phone as kalshi.json on the branch `main` of its own repo, demetrades2000-coder/kalshi-feed (contract:
   engine/kalshi_publish.py, docs/KALSHI_PUBLISH.md), sent every minute. This page shows that file, inside Jarvis or on its own: raw.githubusercontent
   first, the GitHub API second, 404 = not connected yet. Read-only: it never talks to Kalshi and places nothing.
   Contract v2 adds two optional lists, `strategies` [{name, mode, running, today_pnl, total_pnl, trades, wins, losses}] and
   `equity` [[unix, balance]] (the bot keeps 24 h of it); without `equity` the curve is the running sum of `days`.
   Sides: yes / no, or the bot's own UP / DOWN. Optional per row: `asset` (else read from the ticker) and `book` / `strategy`.
   Live prices: Kalshi's public API (api.elections.kalshi.com) answers browsers only from kalshi.com (CloudFront 403 for any
   other Origin, checked 2026-11-01), so prices are the bot's own, as of its last update.
   Look: kalshi.css, its own Kalshi theme (index.html sets data-theme="kalshi" before paint; never Jarvis's theme).
   Safari 16 safe: no regex lookbehind, no Array copy methods, no Object.groupBy, no AbortSignal.timeout. */
(() => {
  'use strict';
  // the feed has its own repo (security review 2026-11-01): the Kalshi server's deploy key can write kalshi-feed only, never
  // the Pages site. Raw first, the GitHub API second; a 404 = not connected yet.
  const RAW = 'https://raw.githubusercontent.com/demetrades2000-coder/kalshi-feed/main/kalshi.json';
  const API = 'https://api.github.com/repos/demetrades2000-coder/kalshi-feed/contents/kalshi.json?ref=main';
  const STEP0 = 'Open your kalshi-server chat in the Claude app and paste: Set up Jarvis for my Kalshi bot by following https://demetrades2000-coder.github.io/nq-dashboard/kalshi/SETUP.md';
  // the server script is pinned: the site build writes kit.json next to this page ({"v":1, "file":"kalshi_status_vm.py",
  // "sha256":"<64 hex>"}); with a valid hash the step carries it, else the step stays exactly STEP0
  let STEP = STEP0;
  const pinned = (h) => `${STEP0} (only run kalshi_status_vm.py if its sha256 is ${h})`;
  const paste = () => STEP.slice(STEP.indexOf('paste: ') + 7);     // what goes into the bot's chat (the hash included)
  const TZ = 'America/New_York', STALE_S = 15 * 60, POLL_MS = 60e3, TICK_MS = 30e3, TIMEOUT_MS = 12e3, TR_PAGE = 10, TR_CAP = 40;
  const RANGES = [['1W', 7, 'past week'], ['1M', 30, 'past month'], ['3M', 90, 'past 3 months'], ['All', 0, '']];
  const SORTS = [['closes', 'Soonest'], ['pnl', 'Best'], ['pnl-asc', 'Worst'], ['value', 'Biggest'], ['name', 'A–Z']];
  const SIDES = ['all', 'yes', 'no'];
  const ASSETS = ['BTC', 'ETH', 'SOL', 'XRP', 'DOGE', 'HYPE', 'BNB', 'GOLD', 'SILVER'];

  // ------------------------------------------------------------------ helpers
  const $ = (s) => document.querySelector(s);
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const num = (v) => {
    if (typeof v === 'number') return Number.isFinite(v) ? v : null;
    if (typeof v !== 'string' || !v.trim()) return null;
    const x = +v;
    return Number.isFinite(x) ? x : null;
  };
  const isObj = (v) => !!v && typeof v === 'object' && !Array.isArray(v);
  const arr = (v) => (Array.isArray(v) ? v : []);
  const sum = (a) => a.reduce((s, x) => s + x, 0);
  const MINUS = '−';
  const sgn = (x, sign) => (x < 0 ? MINUS : sign && x > 0 ? '+' : '');
  const usd = (v, sign) => {                                   // real money: always to the cent
    const x = num(v);
    if (x == null) return '—';
    const r = +Math.abs(x).toFixed(2);
    return (r === 0 ? '' : sgn(x, sign)) + '$' + r.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  };
  const short = (a) => (a >= 1e6 ? +(a / 1e6).toFixed(a >= 1e7 ? 0 : 1) + 'M' : a >= 1e3 ? +(a / 1e3).toFixed(a >= 1e4 ? 0 : 1) + 'k'
    : a >= 100 ? String(Math.round(a)) : a >= 10 ? a.toFixed(1) : a.toFixed(2));
  const cmp = (v, sign) => { const x = num(v); if (x == null) return ''; const a = Math.abs(x); return (a < 0.005 ? '' : sgn(x, sign)) + (a < 0.005 ? '0' : short(a)); };
  const pct = (x, sign) => (x == null || !Number.isFinite(x) ? '' : sgn(x, sign) + Math.abs(x * 100).toFixed(Math.abs(x) < 0.1 ? 1 : 0) + '%');
  const cls = (v) => { const x = num(v); return x == null || Math.abs(x) < 0.005 ? '' : x > 0 ? 'up' : 'down'; };
  const cents = (v) => {                                       // 0.42 -> 42¢, 0.9683 -> 96.8¢ (the favourites trade at 95-97¢)
    const x = num(v);
    if (x == null) return '—';
    const c = x <= 1 ? x * 100 : x;
    return (Math.abs(c - Math.round(c)) < 0.05 ? String(Math.round(c)) : c.toFixed(1)) + '¢';
  };
  const dol = (v) => { const x = num(v); return x == null ? null : x > 1 ? x / 100 : x; };     // contract: dollars 0-1 (cents if > 1)
  const fmtN = (x) => (Number.isInteger(x) ? x.toLocaleString('en-US') : String(+x.toFixed(2)));
  const cap = (s) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : '');
  const by = (f, desc) => (a, b) => {
    const x = f(a), y = f(b);
    if (x == null && y == null) return 0;
    if (x == null) return 1;
    if (y == null) return -1;
    return typeof x === 'string' ? (desc ? y.localeCompare(x) : x.localeCompare(y)) : desc ? y - x : x - y;
  };

  const nowS = () => Date.now() / 1000;
  const parseT = (v) => {                                    // unix s / ms / ISO text -> unix seconds
    if (v == null || v === '' || typeof v === 'boolean') return null;
    const x = num(v);
    if (x != null) return x > 1e12 ? x / 1000 : x;
    if (typeof v !== 'string') return null;
    const ms = Date.parse(v.trim().replace(/^(\d{4}-\d{2}-\d{2}) (\d)/, '$1T$2'));    // Safari wants the T
    return Number.isFinite(ms) ? ms / 1000 : null;
  };
  const ago = (t) => {
    const x = parseT(t);
    if (!x) return '';
    const s = Math.max(0, nowS() - x);
    return s < 90 ? 'just now' : s < 3600 ? Math.round(s / 60) + ' min ago' : s < 86400 ? Math.round(s / 3600) + ' h ago' : Math.round(s / 86400) + ' d ago';
  };
  const dtf = (o, tz) => { try { return new Intl.DateTimeFormat('en-US', Object.assign({ timeZone: tz || TZ }, o)); } catch (_) { return null; } };
  const F = {
    when: dtf({ month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }),
    full: dtf({ weekday: 'short', month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' }),
    time: dtf({ hour: 'numeric', minute: '2-digit' }),
    md: dtf({ month: 'short', day: 'numeric' }),
    key: dtf({ year: 'numeric', month: '2-digit', day: '2-digit' }),
    dayL: dtf({ weekday: 'short', month: 'short', day: 'numeric' }, 'UTC'),
    mdU: dtf({ month: 'short', day: 'numeric' }, 'UTC'),
    mon: dtf({ month: 'long', year: 'numeric' }, 'UTC'),
  };
  const ff = (f, t) => { try { return f && t != null ? f.format(new Date(t * 1000)) : ''; } catch (_) { return ''; } };
  const when = (t) => ff(F.when, parseT(t));
  const dayKey = (t) => {                                    // unix seconds -> 'YYYY-MM-DD' in New York
    try {
      const p = {};
      F.key.formatToParts(new Date(t * 1000)).forEach((q) => { p[q.type] = q.value; });
      return p.year && p.month && p.day ? `${p.year}-${p.month}-${p.day}` : '';
    } catch (_) { return ''; }
  };
  const pd = (s) => { const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(s == null ? '' : s).slice(0, 10)); return m ? { y: +m[1], m: +m[2], d: +m[3] } : null; };
  const dayT = (s) => { const p = pd(s); return p ? Date.UTC(p.y, p.m - 1, p.d, 12) / 1000 : null; };   // a day as noon UTC (labels in UTC)
  const dayLabel = (s) => ff(F.dayL, dayT(s)) || String(s);
  const left = (t) => {
    const s = Math.round(t - nowS());
    if (s <= 0) return '';
    const d = Math.floor(s / 86400), h = Math.floor((s % 86400) / 3600), m = Math.floor((s % 3600) / 60);
    return d >= 1 ? `${d}d ${h}h` : h >= 1 ? `${h}h ${m}m` : m >= 1 ? `${m}m` : 'under 1m';
  };
  const closesTxt = (t) => { const l = left(t); return l ? 'closes in ' + l : 'closed · settling'; };
  const cdnCls = (t) => { const s = t - nowS(); return s <= 0 ? ' past' : s < 3600 ? ' soon' : ''; };
  // the side as the bot means it: yes / no, or UP / DOWN (an "up or down" market's YES is UP)
  const sideOf = (r) => {
    const s = String(r.side == null ? '' : r.side).trim().toLowerCase().slice(0, 8);
    if ((s === 'yes' || s === 'no') && /\bup or down\b/i.test(String(r.title || ''))) return s === 'yes' ? 'up' : 'down';
    return s;
  };
  const sideKey = (s) => (s === 'yes' || s === 'up' ? 'yes' : s === 'no' || s === 'down' ? 'no' : '');
  const sideTag = (s) => `<span class="tag ${sideKey(s) || 'unk'}">${s ? esc(s.toUpperCase()) : '—'}</span>`;
  const assetOf = (r) => {
    const a = r.asset == null ? '' : String(r.asset).trim().toUpperCase().slice(0, 6);
    if (a) return a;
    const m = /^KX([A-Z]+)/.exec(String(r.ticker || ''));
    return m ? ASSETS.filter((x) => m[1].indexOf(x) === 0)[0] || '' : '';
  };

  const LS = {
    get(k, d) { try { const v = localStorage.getItem(k); return v == null ? d : JSON.parse(v); } catch (_) { return d; } },
    set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (_) { /* private mode / storage full */ } },
  };
  function theme() {                                          // its own dashboard (owner 2026-11-02): always the Kalshi theme
    document.documentElement.setAttribute('data-theme', 'kalshi');
  }

  // ------------------------------------------------------------------ state
  const ui0 = LS.get('kalshi.ui', null), u = isObj(ui0) ? ui0 : {};
  const S = {
    k: null, raw: '', state: 'loading', busy: false, at: 0, label: '', intro: true,
    ui: {
      range: RANGES.some((r) => r[0] === u.range) ? u.range : '1M',
      sort: SORTS.some((r) => r[0] === u.sort) ? u.sort : 'closes',
      side: SIDES.indexOf(u.side) >= 0 ? u.side : 'all',
    },
    preview: false, q: '', kf: 0, calc: { p: '', c: '' }, trShown: TR_PAGE, cal: '', calSel: '', calGr: '', open: new Set(), scrub: false, pend: false, chart: null, series: null, v: null, pos: [],
  };
  const saveUi = () => LS.set('kalshi.ui', S.ui);
  const cached = LS.get('kalshi.last', null);
  if (isObj(cached)) { S.k = cached; S.raw = JSON.stringify(cached); }

  // ------------------------------------------------------------------ the feed
  async function get(url, headers, ms) {
    let ac = null, tm = 0;
    try { ac = new AbortController(); tm = setTimeout(() => ac.abort(), ms || TIMEOUT_MS); } catch (_) { ac = null; }
    try { return await fetch(url, { cache: 'no-cache', headers: headers || {}, signal: ac ? ac.signal : undefined }); } catch (_) { return null; } finally { clearTimeout(tm); }
  }

  async function load() {
    if (S.busy) return;
    S.busy = true;
    busyUi();
    let r = await get(RAW + '?t=' + Math.floor(Date.now() / 60000));
    if (!r || (!r.ok && r.status !== 404)) r = await get(API, { Accept: 'application/vnd.github.raw+json' });
    let j = null, st = 'error';
    if (r && r.ok) {
      try { j = await r.json(); } catch (_) { j = null; }
      if (isObj(j)) st = 'ok';
    } else if (r && r.status === 404) st = 'waiting';
    S.busy = false;
    S.at = Date.now();
    busyUi();                                                // the spinner stops even when the drawing waits (render below)
    if (st === 'ok') {
      if (S.preview) { S.preview = false; S.raw = ''; }       // real data: the sample preview is over for good
      const raw = JSON.stringify(j), same = raw === S.raw && S.state === 'ok';
      S.k = j; S.raw = raw; S.state = 'ok';
      LS.set('kalshi.last', j);
      if (same) { busyUi(); tick(); return; }               // nothing new: keep the page as it is (open rows, scroll, typing)
    } else S.state = st;
    render();
  }

  // ------------------------------------------------------------------ the data, cleaned for display
  function norm(k) {
    const dm = new Map();
    arr(k.days).forEach((d) => {
      const r = Array.isArray(d) ? [d[0], d[1]] : isObj(d) ? [d.day || d.date, d.pnl] : null;
      if (!r) return;
      const key = String(r[0] == null ? '' : r[0]).slice(0, 10), x = num(r[1]);
      if (pd(key) && x != null) dm.set(key, x);
    });
    const em = new Map();
    arr(k.equity).forEach((p) => {
      const r = Array.isArray(p) ? [p[0], p[1]] : isObj(p) ? [p.t, p.balance != null ? p.balance : p.equity] : null;
      if (!r) return;
      const t = parseT(r[0]), x = num(r[1]);
      if (t != null && t > 1e9 && x != null) em.set(t, x);
    });
    return {
      pos: arr(k.positions).filter(isObj),
      tr: arr(k.trades).filter(isObj).sort(by((t) => parseT(t.t), true)),        // newest first
      days: Array.from(dm.entries()).sort((a, b) => (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0)),
      strat: arr(k.strategies).filter(isObj),
      eq: Array.from(em.entries()).sort((a, b) => a[0] - b[0]),
    };
  }

  const stateOf = (k) => {
    const t = parseT(k.t), fresh = t && nowS() - t < STALE_S;
    return k.running === false ? ['bad', 'Stopped'] : fresh ? ['ok', 'Running'] : ['warn', 'Not updating'];
  };
  const safe = (name, fn) => {
    try { return fn(); } catch (e) {
      try { console.error('kalshi page: the ' + name + ' section failed', e); } catch (_) { /* no console */ }
      return `<section class="card"><p class="muted">The ${esc(name)} section could not be shown.</p></section>`;
    }
  };

  // ------------------------------------------------------------------ sections
  function subHtml() {
    if (previewing()) return '<span class="pill warn" id="pill">Preview</span><span class="ago">sample data, not your account</span>';
    if (S.state === 'waiting') return 'Not connected yet';
    const k = S.k;
    if (!k) return S.state === 'error' ? 'Could not reach the Kalshi feed' : 'Loading…';
    const [lvl, label] = stateOf(k), m = String(k.mode == null ? '' : k.mode).trim().toLowerCase().slice(0, 12), t = parseT(k.t);
    const mode = !m ? '' : m === 'live' ? '<span class="mode live" id="mode">LIVE <i>· real money</i></span>' : `<span class="mode" id="mode">${esc(m.toUpperCase())}</span>`;
    return `<span class="pill ${lvl}" id="pill">${esc(label)}</span>${mode}`
      + (t ? `<span class="ago" data-ago="${t}">updated ${esc(ago(t))}</span>` : '') + (S.state === 'error' ? '<span class="off">offline copy</span>' : '');
  }

  function notesHtml(k) {
    const t = parseT(k.t), age = t ? nowS() - t : Infinity;
    if (S.state === 'error') {
      return `<div class="note bad" role="status"><p><b>Offline copy</b> Can't reach the Kalshi feed${navigator.onLine === false ? ' (this phone is offline)' : ''}, so this is the last copy${t ? `, from ${esc(when(t))} (${esc(ago(t))})` : ''}.</p><button type="button" class="btn ghost" data-act="retry">Try again</button></div>`;
    }
    if (S.state === 'ok' && age > STALE_S) {
      return `<div class="note warn" role="status"><p><b>Not updating</b> The bot's last update came ${t ? esc(ago(t)) : 'a while ago'}; it normally sends one every minute. Its server may have stopped sending.</p></div>`;
    }
    return '';
  }

  function heroHtml(k, v) {
    const bal = num(k.balance), today = dayKey(nowS());
    // today's wins / losses, as in the bot's own money text, when the trades list covers the whole day
    const tt = v.tr.filter((t) => { const x = parseT(t.t); return x && dayKey(x) === today; });
    const whole = v.tr.length < TR_CAP || v.tr.some((t) => { const x = parseT(t.t); return x && dayKey(x) < today; });
    const tw = tt.filter((t) => num(t.pnl) > 0.005).length, tl = tt.filter((t) => num(t.pnl) < -0.005).length;
    // all time: the strategies' own W / L totals; no % there (deposits and withdrawals make the start unknown)
    let aw = 0, al = 0, ok = false;
    v.strat.forEach((s) => { const w = num(s.wins), l = num(s.losses); if (w != null && l != null) { aw += w; al += l; ok = true; } });
    const kp = (lab, val, extra, withPct) => {
      const x = num(val), base = bal != null && x != null ? bal - x : null, p = withPct && base && base > 0 ? pct(x / base, true) : '';
      return `<div><span class="lab">${lab}</span><strong class="fit ${cls(x)}">${esc(usd(x, true))}</strong>${[extra, p].filter(Boolean).map((t) => `<em>${esc(t)}</em>`).join('')}</div>`;
    };
    return `<section class="card hero" id="sec-kpi"><div class="bal"><div><span class="lab">${esc(k.name ? String(k.name).slice(0, 40) : 'Balance')}${k.name ? ' · balance' : ''}</span><strong class="fit">${esc(usd(bal))}</strong></div></div>`
      + `<div class="kpis">${kp('Today', k.today_pnl, whole && tw + tl ? `${tw}W ${tl}L` : '', true)}${kp('This week', k.week_pnl, '', true)}${kp('All time', k.total_pnl, ok && aw + al ? `${fmtN(aw)}W ${fmtN(al)}L` : '', false)}</div>`
      + (k.status ? `<p class="status">${esc(k.status)}</p>` : '') + (k.note ? `<p class="muted">${esc(k.note)}</p>` : '') + '</section>';
  }

  // ---- equity curve: `equity` when published, else the running sum of the daily P&L
  function series(v) {
    if (v.eq.length >= 2) return { kind: 'eq', pts: v.eq };
    if (!v.days.length) return null;
    const f = pd(v.days[0][0]);
    const pts = [[Date.UTC(f.y, f.m - 1, f.d - 1, 12) / 1000, 0, null, '']];
    let c = 0;
    v.days.forEach((d) => { c = Math.round((c + d[1]) * 1e4) / 1e4; pts.push([dayT(d[0]), c, d[1], d[0]]); });
    return { kind: 'days', pts };
  }
  const spanOf = (s) => s.pts[s.pts.length - 1][0] - s.pts[0][0];
  const rangesOf = (s) => RANGES.filter((r) => !r[1] || r[1] * 86400 < spanOf(s) - 86400);
  function cut(s, key) {
    const r = RANGES.find((x) => x[0] === key);
    if (!r || !r[1]) return s.pts;
    const from = s.pts[s.pts.length - 1][0] - r[1] * 86400;
    let i = 0;
    while (i < s.pts.length && s.pts[i][0] < from) i++;
    return s.pts.slice(Math.min(Math.max(0, i - 1), s.pts.length - 2));   // one point before the range: the change is right
  }
  const thin = (p, n) => {
    if (p.length <= n) return p;
    const out = [], step = p.length / n;
    for (let i = 0; i < n; i++) out.push(p[Math.floor(i * step)]);
    out.push(p[p.length - 1]);
    return out;
  };
  const xLabel = (c, t) => (c.kind === 'days' ? ff(F.mdU, t) : c.dt <= 20 * 3600 ? ff(F.time, t) : c.dt <= 8 * 86400 ? ff(F.when, t) : ff(F.md, t));

  function eqHtml(v) {
    const s = series(v);
    S.series = s;
    S.chart = null;
    if (!s) return '<section class="card" id="sec-eq"><div class="card-h"><h2>Equity</h2></div><p class="empty">No history yet: the curve starts with the bot\'s first equity points or daily P&amp;L.</p></section>';
    const avail = rangesOf(s), key = avail.some((r) => r[0] === S.ui.range) ? S.ui.range : 'All', rl = RANGES.find((r) => r[0] === key);
    const pts = cut(s, key);
    const W = 1000, H = 300, PT = 18, PB = 18;
    const t0 = pts[0][0], dt = Math.max(1, pts[pts.length - 1][0] - t0);
    let lo = Infinity, hi = -Infinity;
    pts.forEach((p) => { if (p[1] < lo) lo = p[1]; if (p[1] > hi) hi = p[1]; });
    const flat = hi === lo, pad = flat ? Math.max(0.5, Math.abs(hi) * 0.02) : (hi - lo) * 0.04;
    const ylo = lo - pad, yhi = hi + pad;
    const X = (t) => ((t - t0) / dt) * W, Y = (x) => PT + (1 - (x - ylo) / (yhi - ylo)) * (H - PT - PB);
    const d = thin(pts, 700).map((p, i) => (i ? 'L' : 'M') + X(p[0]).toFixed(1) + ',' + Y(p[1]).toFixed(1)).join('');
    const first = pts[0][1], last = pts[pts.length - 1][1];
    const range = rl[2] || (dt <= 2 * 86400 ? `last ${Math.max(1, Math.round(dt / 3600))} h` : 'since ' + (s.kind === 'eq' ? ff(F.md, t0) : ff(F.mdU, t0)));
    const c = { kind: s.kind, pts, t0, dt, first, i: -1, range, xp: (t) => (X(t) / W) * 100, yp: (x) => (Y(x) / H) * 100 };
    S.chart = c;
    const chips = avail.length > 1 ? `<div class="seg" role="group" aria-label="Range">${avail.map((r) => `<button type="button" data-act="range" data-v="${r[0]}" aria-pressed="${r[0] === key}">${r[0]}</button>`).join('')}</div>` : '';
    const lab = s.kind === 'eq' ? 'Equity' : 'Cumulative P&amp;L', sg = s.kind === 'days';
    const axes = flat ? `<span class="ax" style="top:${Y(hi) / H * 100}%">${esc(usd(hi, sg))}</span>`
      : `<span class="ax" style="top:${Y(hi) / H * 100}%">${esc(usd(hi, sg))}</span><span class="ax" style="top:${Y(lo) / H * 100}%">${esc(usd(lo, sg))}</span>`;
    return `<section class="card" id="sec-eq"><div class="card-h"><h2>${lab}</h2>${chips}</div>`
      + `<div class="eq-read" id="eqRead">${readHtml(-1)}</div>`
      + `<div class="chart" id="chart" tabindex="0" role="img" aria-label="${esc((s.kind === 'eq' ? 'Equity' : 'Cumulative P&L') + ', ' + range + ': from ' + usd(first) + ' to ' + usd(last) + '. Drag or use the arrow keys to read a point.')}">`
      + `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" aria-hidden="true" focusable="false"><defs><linearGradient id="eqFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="currentColor" stop-opacity=".34"/><stop offset="1" stop-color="currentColor" stop-opacity="0"/></linearGradient></defs>`
      + (flat ? '' : `<line class="grid" x1="0" x2="${W}" y1="${Y(hi).toFixed(1)}" y2="${Y(hi).toFixed(1)}"/><line class="grid" x1="0" x2="${W}" y1="${Y(lo).toFixed(1)}" y2="${Y(lo).toFixed(1)}"/>`)
      + `<line class="base" x1="0" x2="${W}" y1="${Y(first).toFixed(1)}" y2="${Y(first).toFixed(1)}"/>`
      + `<path class="area" d="${d}L${W},${H}L0,${H}Z" fill="url(#eqFill)"/><path class="ln" d="${d}"/></svg>`
      + `${axes}<i class="cross" hidden></i><i class="dot" hidden></i></div>`
      + `<div class="xs"><span>${esc(xLabel(c, t0))}</span><span>${esc(xLabel(c, pts[pts.length - 1][0]))}</span></div>`
      + (s.kind === 'days' ? '<p class="muted small">From the daily P&amp;L: no equity points from the bot yet.</p>' : '')
      + '</section>';
  }

  function readHtml(i) {
    const c = S.chart;
    if (!c) return '';
    const idle = i < 0, p = c.pts[idle ? c.pts.length - 1 : i], chg = p[1] - c.first, base = Math.abs(c.first);
    if (c.kind === 'eq') {
      return `<b>${esc(usd(p[1]))}</b><span class="${cls(chg)}">${esc(usd(chg, true))}${base > 0 ? ' (' + esc(pct(chg / base, true)) + ')' : ''}</span>`
        + `<span class="when">${esc(idle ? c.range : ff(F.when, p[0]))}</span>`;
    }
    if (idle) return `<b class="${cls(chg)}">${esc(usd(chg, true))}</b><span class="when">${esc(c.range)}</span>`;
    return `<b class="${cls(p[1])}">${esc(usd(p[1], true))}</b>${p[3] ? `<span class="${cls(p[2])}">day ${esc(usd(p[2], true))}</span><span class="when">${esc(dayLabel(p[3]))}</span>` : '<span class="when">start</span>'}`;
  }

  function bindChart() {
    const el = $('#chart'), c = S.chart;
    if (!el || !c) return;
    const cross = el.querySelector('.cross'), dot = el.querySelector('.dot'), read = $('#eqRead');
    const show = (i) => {
      c.i = i;
      const p = c.pts[i], x = c.xp(p[0]);
      cross.style.left = x + '%'; dot.style.left = x + '%'; dot.style.top = c.yp(p[1]) + '%';
      cross.hidden = false; dot.hidden = false;
      if (read) read.innerHTML = readHtml(i);
    };
    const hide = () => { c.i = -1; cross.hidden = true; dot.hidden = true; if (read) read.innerHTML = readHtml(-1); };
    const at = (cx) => {
      const r = el.getBoundingClientRect();
      if (!r.width) return;
      const t = c.t0 + Math.min(1, Math.max(0, (cx - r.left) / r.width)) * c.dt;
      let lo = 0, hi = c.pts.length - 1;
      while (hi - lo > 1) { const m = (lo + hi) >> 1; if (c.pts[m][0] < t) lo = m; else hi = m; }
      show(Math.abs(c.pts[lo][0] - t) <= Math.abs(c.pts[hi][0] - t) ? lo : hi);
    };
    const end = () => { S.scrub = false; hide(); if (S.pend) { S.pend = false; render(); } };
    el.addEventListener('pointerdown', (e) => {
      if (e.pointerType !== 'mouse') { S.scrub = true; try { el.setPointerCapture(e.pointerId); } catch (_) { /* not capturable */ } }
      at(e.clientX);
    });
    el.addEventListener('pointermove', (e) => { if (S.scrub || e.pointerType === 'mouse') at(e.clientX); });
    el.addEventListener('pointerup', (e) => { if (e.pointerType !== 'mouse') end(); });
    el.addEventListener('pointercancel', end);
    el.addEventListener('pointerleave', (e) => { if (e.pointerType === 'mouse') end(); });
    el.addEventListener('blur', () => { if (!S.scrub) hide(); });
    el.addEventListener('keydown', (e) => {
      const n = c.pts.length;
      let i = c.i < 0 ? n - 1 : c.i;
      if (e.key === 'ArrowLeft') i -= 1; else if (e.key === 'ArrowRight') i += 1; else if (e.key === 'Home') i = 0; else if (e.key === 'End') i = n - 1;
      else if (e.key === 'Escape') { hide(); return; } else return;
      e.preventDefault();
      show(Math.max(0, Math.min(n - 1, i)));
    });
  }

  // ---- daily P&L: bars (last 30 days) and the calendar heat map
  function barsHtml(v) {
    const d = v.days.slice(-30);
    if (!d.length) return '<section class="card" id="sec-days"><div class="card-h"><h2>Daily P&amp;L</h2></div><p class="empty">No daily P&amp;L yet.</p></section>';
    const m = Math.max.apply(null, d.map((x) => Math.abs(x[1]))) || 1, w = 300, h = 64, mid = h / 2, slot = w / Math.max(d.length, 14), off = w - slot * d.length;
    const rects = d.map((x, i) => {
      const val = x[1], bh = Math.max(1, (Math.abs(val) / m) * (mid - 3));
      return `<rect x="${(off + i * slot + 1).toFixed(1)}" y="${(val >= 0 ? mid - bh : mid).toFixed(1)}" width="${Math.max(1, slot - 2).toFixed(1)}" height="${bh.toFixed(1)}" fill="${val >= 0 ? 'var(--ok)' : 'var(--bad)'}"><title>${esc(dayLabel(x[0]))}: ${esc(usd(val, true))}</title></rect>`;
    }).join('');
    const tot = sum(d.map((x) => x[1]));
    return `<section class="card" id="sec-days"><div class="card-h"><h2>Daily P&amp;L · ${d.length} ${d.length === 1 ? 'day' : 'days'}</h2><span class="r ${cls(tot)}">${esc(usd(tot, true))}</span></div>`
      + `<svg class="bars" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" role="img" aria-label="Daily P&amp;L, last ${d.length} days"><line class="mid" x1="0" x2="${w}" y1="${mid}" y2="${mid}"/>${rects}</svg></section>`;
  }

  const ymAdd = (ym, n) => { const y = +ym.slice(0, 4), m = +ym.slice(5, 7) - 1 + n, yy = y + Math.floor(m / 12), mm = ((m % 12) + 12) % 12; return `${yy}-${String(mm + 1).padStart(2, '0')}`; };
  function calHtml(v) {
    if (!v.days.length) return '';
    const map = new Map(v.days), today = dayKey(nowS()) || v.days[v.days.length - 1][0];
    const firstM = v.days[0][0].slice(0, 7), lastM = v.days[v.days.length - 1][0].slice(0, 7), maxM = today.slice(0, 7) > lastM ? today.slice(0, 7) : lastM;
    if (!S.cal || S.cal < firstM || S.cal > maxM) S.cal = lastM;
    const y = +S.cal.slice(0, 4), m = +S.cal.slice(5, 7);
    const dow = (new Date(Date.UTC(y, m - 1, 1)).getUTCDay() + 6) % 7, nd = new Date(Date.UTC(y, m, 0)).getUTCDate();   // Monday first, as the bot's weeks
    const key = (d) => `${S.cal}-${String(d).padStart(2, '0')}`;
    let mx = 0, tot = 0, g = 0, r = 0, n = 0;
    for (let d = 1; d <= nd; d++) {
      const x = map.get(key(d));
      if (x != null) { mx = Math.max(mx, Math.abs(x)); tot += x; n++; if (x > 0.005) g++; else if (x < -0.005) r++; }
    }
    const cells = ['M', 'T', 'W', 'T', 'F', 'S', 'S'].map((c) => `<span class="wd" aria-hidden="true">${c}</span>`);
    cells.push('<span class="wd wk" title="Week total">WK</span>');
    for (let w = 0; w < Math.ceil((dow + nd) / 7); w++) {
      let wt = 0, wn = 0;
      for (let c = 0; c < 7; c++) {
        const d = w * 7 + c - dow + 1;
        if (d < 1 || d > nd) { cells.push('<span class="cd x" aria-hidden="true"></span>'); continue; }
        const k = key(d), x = map.get(k);
        if (x != null) { wt += x; wn++; }
        const lv = x == null ? (k > today ? 'f' : 'e') : Math.abs(x) < 0.005 ? 'z' : (x > 0 ? 'p' : 'n') + Math.max(1, Math.min(4, Math.ceil((Math.abs(x) / (mx || 1)) * 4)));
        cells.push(`<button type="button" class="cd ${lv}${k === today ? ' today' : ''}" data-act="day" data-v="${k}" aria-pressed="${S.calSel === k}" aria-label="${esc(dayLabel(k) + ': ' + (x == null ? 'no P&L' : usd(x, true)))}"><i>${d}</i><em>${x == null ? '' : esc(cmp(x, true))}</em></button>`);
      }
      cells.push(`<span class="cw ${wn ? cls(wt) : ''}">${wn ? esc(cmp(wt, true)) : ''}</span>`);
    }
    const prev = ymAdd(S.cal, -1), next = ymAdd(S.cal, 1), mon = ff(F.mon, Date.UTC(y, m - 1, 15) / 1000);
    S.calGr = n ? `${n} ${n === 1 ? 'day' : 'days'} this month: ${g} green, ${r} red` : 'No P&amp;L this month';
    return `<section class="card" id="sec-cal"><div class="card-h"><h2>P&amp;L calendar</h2><span class="r ${cls(tot)}">${n ? esc(usd(tot, true)) : ''}</span></div>`
      + `<div class="cal-h"><button type="button" class="nav" data-act="month" data-v="${prev}" aria-label="Previous month"${prev < firstM ? ' disabled' : ''}>‹</button>`
      + `<b id="calMonth">${esc(mon)}</b><button type="button" class="nav" data-act="month" data-v="${next}" aria-label="Next month"${next > maxM ? ' disabled' : ''}>›</button></div>`
      + `<div class="cal" role="group" aria-label="${esc('Daily P&L, ' + mon)}">${cells.join('')}</div>`
      + `<p class="muted cal-read" id="calRead" aria-live="polite">${calRead(map)}</p></section>`;
  }
  function calRead(map) {
    const k = S.calSel;
    if (!k) return `${S.calGr}. Tap a day for its P&amp;L.`;
    const x = map.get(k), tr = S.v ? S.v.tr.filter((t) => { const tt = parseT(t.t); return tt && dayKey(tt) === k; }) : [];
    // its week (Monday to Sunday, as the bot's): on a phone the calendar has no week column, so the total is here
    const p = pd(k), dw = (new Date(Date.UTC(p.y, p.m - 1, p.d)).getUTCDay() + 6) % 7;
    let wk = 0, wn = 0;
    for (let i = 0; i < 7; i++) { const x2 = map.get(new Date(Date.UTC(p.y, p.m - 1, p.d - dw + i)).toISOString().slice(0, 10)); if (x2 != null) { wk += x2; wn++; } }
    return `<b>${esc(dayLabel(k))}</b> · ${x == null ? 'no P&amp;L' : `<span class="${cls(x)}">${esc(usd(x, true))}</span>`}`
      + (wn ? ` · its week <span class="${cls(wk)}">${esc(usd(wk, true))}</span>` : '') + (tr.length ? ` · ${tr.length} ${tr.length === 1 ? 'trade' : 'trades'} in the recent list` : '');
  }

  // ---- stats
  function statsHtml(v, k) {
    const pn = v.tr.map((t) => num(t.pnl)).filter((x) => x != null);
    const wins = pn.filter((x) => x > 0.005), losses = pn.filter((x) => x < -0.005);
    const tile = (lab, vals, sub, extra) => `<div class="stat"><span class="lab">${lab}</span>${vals}${sub ? `<em>${sub}</em>` : ''}${extra || ''}</div>`;
    const one = (h) => `<strong class="fit">${h}</strong>`;
    const two = (a, la, b, lb) => `<strong class="fit"><span class="${cls(a)}">${esc(usd(a, true))}</span>${la ? `<small>${esc(la)}</small>` : ''}</strong>`
      + `<strong class="fit"><span class="${cls(b)}">${esc(usd(b, true))}</span>${lb ? `<small>${esc(lb)}</small>` : ''}</strong>`;
    const tiles = [];
    if (pn.length) {
      const nd = wins.length + losses.length, wr = nd ? wins.length / nd : null;
      const aw = wins.length ? sum(wins) / wins.length : null, al = losses.length ? sum(losses) / losses.length : null;
      const gw = sum(wins), gl = -sum(losses);
      let cur = 0, curS = 0;
      for (let i = 0; i < pn.length; i++) { const s = pn[i] > 0.005 ? 1 : pn[i] < -0.005 ? -1 : 0; if (!s) continue; if (!curS) curS = s; if (s !== curS) break; cur++; }
      let run = 0, best = 0;
      for (let i = pn.length - 1; i >= 0; i--) { if (pn[i] > 0.005) { run++; best = Math.max(best, run); } else if (pn[i] < -0.005) run = 0; }
      tiles.push(tile('Win rate', one(wr == null ? '—' : esc(pct(wr))), `${wins.length}W · ${losses.length}L`,
        nd ? `<div class="wl" aria-hidden="true"><i style="width:${(wr * 100).toFixed(1)}%"></i><b style="width:${(100 - wr * 100).toFixed(1)}%"></b></div>` : ''));
      tiles.push(tile('Profit factor', one(gl > 0 ? (gw / gl).toFixed(2) : gw > 0 ? '∞' : '—'), `${esc(usd(gw - gl, true))} net`));
      tiles.push(tile('Avg win / loss', two(aw, 'win', al, 'loss'), aw != null && al ? `payoff ${(aw / -al).toFixed(2)}×` : ''));
      tiles.push(tile('Best / worst', two(Math.max.apply(null, pn), 'best', Math.min.apply(null, pn), 'worst'), ''));
      tiles.push(tile('Streak', one(cur ? `<span class="${curS > 0 ? 'up' : 'down'}">${cur} ${curS > 0 ? (cur === 1 ? 'win' : 'wins') : cur === 1 ? 'loss' : 'losses'}</span>` : '—'),
        best ? `best run ${best} ${best === 1 ? 'win' : 'wins'}` : 'no wins yet'));
    }
    if (v.days.length) {
      const dv = v.days.map((d) => d[1]), g = dv.filter((x) => x > 0.005).length;
      let bi = 0, wi = 0;
      dv.forEach((x, i) => { if (x > dv[bi]) bi = i; if (x < dv[wi]) wi = i; });
      let ds = 0, dS = 0;
      for (let i = dv.length - 1; i >= 0; i--) { const s = dv[i] > 0.005 ? 1 : dv[i] < -0.005 ? -1 : 0; if (!s) continue; if (!dS) dS = s; if (s !== dS) break; ds++; }
      tiles.push(tile('Green days', one(`${g} / ${dv.length}`), `${esc(pct(g / dv.length))}${ds ? ` · now ${ds} ${dS > 0 ? 'green' : 'red'}` : ''}`));
      tiles.push(tile('Best / worst day', two(dv[bi], ff(F.mdU, dayT(v.days[bi][0])), dv[wi], ff(F.mdU, dayT(v.days[wi][0]))), ''));
    }
    const at = k && isObj(k.stats) ? k.stats : null, aw = at ? num(at.wins) : null, al = at ? num(at.losses) : null, ast = at ? num(at.staked) : null, ap = at ? num(at.pnl) : null;
    if (aw != null && al != null && aw + al > 0) {
      tiles.push(tile('All-time win', one(esc(pct(aw / (aw + al)))), `${esc(fmtN(aw))}W · ${esc(fmtN(al))}L${num(at.avg_price) != null ? ' · avg ' + esc(cents(at.avg_price)) : ''}`));
    }
    if (ast != null && ast > 0 && ap != null) tiles.push(tile('All-time ROI', one(`<span class="${cls(ap)}">${esc(pct(ap / ast, true))}</span>`), `${esc(usd(ap, true))} on ${esc(usd(ast))} bet`));
    const s = S.series;
    if (s) {
      let peak = -Infinity, dd = 0, at = 0;
      s.pts.forEach((p) => { if (p[1] > peak) peak = p[1]; if (p[1] - peak < dd) { dd = p[1] - peak; at = peak; } });
      tiles.push(tile(s.kind === 'eq' ? 'Max drawdown' : 'Max drawdown', one(dd < -0.005 ? `<span class="down">${esc(usd(dd, true))}</span>` : esc(usd(0))),
        dd < -0.005 ? (s.kind === 'eq' && at > 0 ? esc(pct(dd / at, true)) + ' from peak' : 'from daily P&amp;L') : 'none so far'));
    }
    const head = `<div class="card-h"><h2>Stats</h2>${pn.length ? `<span class="r muted">last ${pn.length} closed ${pn.length === 1 ? 'trade' : 'trades'}</span>` : ''}</div>`;
    if (!tiles.length) return `<section class="card" id="sec-stats">${head}<p class="empty">No stats yet: they show once trades settle.</p></section>`;
    return `<section class="card" id="sec-stats">${head}${pn.length ? '' : '<p class="muted">No settled trades in the recent list yet; these come from the daily P&amp;L.</p>'}<div class="stats">${tiles.join('')}</div></section>`;
  }

  // ---- strategies (contract v2)
  function stratHtml(v) {
    if (!v.strat.length) return '';
    let tT = 0, tA = 0, tN = 0, tW = 0, tL = 0, hT = false, hA = false, hN = false, hWL = false, on = 0;
    const rows = v.strat.map((s) => {
      const run = s.running === true ? 'on' : s.running === false ? 'off' : '';
      const w = num(s.wins), l = num(s.losses), n = num(s.trades), td = num(s.today_pnl), tot = num(s.total_pnl);
      const wr = w != null && l != null && w + l > 0 ? w / (w + l) : null;
      if (td != null) { tT += td; hT = true; }
      if (tot != null) { tA += tot; hA = true; }
      if (n != null) { tN += n; hN = true; }
      if (w != null && l != null) { tW += w; tL += l; hWL = true; }
      if (run === 'on') on++;
      const mode = s.mode == null ? '' : String(s.mode).trim().toLowerCase().slice(0, 12);
      const sub = [mode === 'live' ? 'Live' : mode.toUpperCase(), n != null ? fmtN(n) + (n === 1 ? ' trade' : ' trades') : '', run === 'on' ? 'running' : run === 'off' ? 'stopped' : ''].filter(Boolean).join(' · ');
      return `<tr><td><div class="nm"><i class="sdot ${run}" aria-hidden="true"></i><b>${esc(s.name == null || s.name === '' ? 'Strategy' : s.name)}</b></div>${sub ? `<small>${esc(sub)}</small>` : ''}</td>`
        + `<td class="${cls(td)}">${esc(usd(td, true))}</td><td class="${cls(tot)}">${esc(usd(tot, true))}</td>`
        + `<td>${wr == null ? '—' : esc(pct(wr))}${w != null && l != null ? `<small>${esc(fmtN(w))}–${esc(fmtN(l))}</small>` : ''}</td></tr>`;
    }).join('');
    const n = v.strat.length, twr = hWL && tW + tL > 0 ? tW / (tW + tL) : null;
    const foot = n > 1 ? `<tfoot><tr><td>All ${n}<small>${hN ? esc(fmtN(tN)) + ' trades' : ''}</small></td><td class="${cls(tT)}">${hT ? esc(usd(tT, true)) : '—'}</td><td class="${cls(tA)}">${hA ? esc(usd(tA, true)) : '—'}</td><td>${twr == null ? '—' : esc(pct(twr))}</td></tr></tfoot>` : '';
    return `<section class="card" id="sec-strat"><div class="card-h"><h2>Strategies · ${n}</h2><span class="r muted">${on} running</span></div>`
      + `<table class="tbl"><thead><tr><th scope="col">Strategy</th><th scope="col">Today</th><th scope="col">Total</th><th scope="col">Win</th></tr></thead><tbody>${rows}</tbody>${foot}</table></section>`;
  }

  // ---- open bets: side tags, countdown, value, P&L; sorted, filtered, searchable
  function posModel(p, i) {
    const side = sideOf(p), n = num(p.contracts), avg = dol(p.avg_price), px = dol(p.price);
    const cost = n != null && avg != null ? n * avg : null;
    const value = num(p.value) != null ? num(p.value) : n != null && px != null ? n * px : null;
    const pnl = num(p.pnl) != null ? num(p.pnl) : px != null && value != null && cost != null ? value - cost : null;
    const title = String(p.title == null || p.title === '' ? (p.ticker == null ? '' : p.ticker) : p.title), ticker = String(p.ticker == null ? '' : p.ticker);
    const prob = unit(p.prob), ref = px != null ? px : avg, edge = prob != null && ref != null ? prob - ref : null;      // v3: the bot's own chance
    return { p, side, sk: sideKey(side), n, avg, px, cost, value, pnl, closes: parseT(p.closes), title, ticker, asset: assetOf(p), key: (ticker || title) + '#' + i,
      prob, edge, ev: edge != null && n != null ? edge * n : null };
  }
  function posHtml(v) {
    const ps = v.pos.map(posModel);
    S.pos = ps;
    const n = ps.length;
    let tv = 0, tp = 0, hv = false, hp = false;
    ps.forEach((m) => { if (m.value != null) { tv += m.value; hv = true; } if (m.pnl != null) { tp += m.pnl; hp = true; } });
    const evs = ps.filter((m) => m.ev != null), evT = sum(evs.map((m) => m.ev)), soon = ps.filter((m) => m.closes != null && m.closes > nowS()).sort(by((m) => m.closes))[0];
    const head = `<div class="card-h"><h2>Open bets · ${n}</h2>${n ? `<span class="r">${hv ? `<span class="muted">${esc(usd(tv))}</span>` : ''}${hv && hp ? ' · ' : ''}${hp ? `<span class="${cls(tp)}">${esc(usd(tp, true))}</span>` : ''}</span>` : ''}</div>`;
    if (!n) return `<section class="card" id="sec-pos">${head}<p class="empty">No open bets right now.</p></section>`;
    const live = evs.length || soon ? `<div class="pos-live">${evs.length ? `<span>Live edge <b class="${cls(evT)}">${esc(usd(evT, true))}</b> EV</span>` : ''}${soon ? `<span>Next settles <b class="cdn${cdnCls(soon.closes)}" data-c="${soon.closes}">${esc(closesTxt(soon.closes))}</b></span>` : ''}</div>` : '';
    const updown = ps.every((m) => m.side === 'up' || m.side === 'down');
    const cnt = { all: n, yes: ps.filter((m) => m.sk === 'yes').length, no: ps.filter((m) => m.sk === 'no').length };
    const lab = { all: 'All', yes: updown ? 'UP' : 'YES', no: updown ? 'DOWN' : 'NO' };
    const ctl = n > 1 ? `<div class="ctl"><div class="seg" role="group" aria-label="Side">${SIDES.map((k) => `<button type="button" data-act="side" data-v="${k}" aria-pressed="${S.ui.side === k}">${lab[k]} <span>${cnt[k]}</span></button>`).join('')}</div>`
      + `<select id="posSort" class="sel" aria-label="Sort open bets">${SORTS.map((s) => `<option value="${s[0]}"${S.ui.sort === s[0] ? ' selected' : ''}>${esc(s[1])}</option>`).join('')}</select></div>` : '';
    const q = n > 5 ? `<input id="posQ" class="q" type="search" placeholder="Search open bets" aria-label="Search open bets" autocomplete="off" autocorrect="off" autocapitalize="off" spellcheck="false" value="${esc(S.q)}">` : '';
    return `<section class="card" id="sec-pos">${head}${live}${ctl}${q}<ul class="rows" id="posList">${posRows()}</ul></section>`;
  }
  function posRows() {
    const q = S.q.trim().toLowerCase(), k = S.ui.sort, n = S.pos.length;
    const list = S.pos.filter((m) => (n < 2 || S.ui.side === 'all' || m.sk === S.ui.side) && (!q || (m.title + ' ' + m.ticker + ' ' + m.asset).toLowerCase().indexOf(q) >= 0))
      .sort(k === 'pnl' ? by((m) => m.pnl, true) : k === 'pnl-asc' ? by((m) => m.pnl) : k === 'value' ? by((m) => m.value, true) : k === 'name' ? by((m) => m.title.toLowerCase()) : by((m) => m.closes));
    if (!list.length) return `<li class="none"><p class="muted">No ${S.ui.side === 'all' ? 'open bets' : 'bets on this side'}${q ? ' match “' + esc(S.q.trim()) + '”' : ''}.</p></li>`;
    return list.map(posRow).join('');
  }
  function posRow(m) {
    const p = m.p;
    const cdn = m.closes != null ? `<span class="cdn${cdnCls(m.closes)}" data-c="${m.closes}">${esc(closesTxt(m.closes))}</span>` : p.closes ? 'closes ' + esc(String(p.closes).slice(0, 16)) : '';
    const ret = m.pnl != null && m.cost ? pct(m.pnl / m.cost, true) : '';
    const dd = (t, d) => `<div><dt>${t}</dt><dd>${d}</dd></div>`;
    const det = [
      m.ticker ? dd('Market', esc(m.ticker)) : '',
      dd('Side', `${m.side ? esc(m.side.toUpperCase()) : '—'}${m.n != null ? ' · ' + esc(fmtN(m.n)) + (m.n === 1 ? ' contract' : ' contracts') : ''}`),
      dd('Cost', `${esc(usd(m.cost))}${m.avg != null ? ' · ' + esc(cents(p.avg_price)) + ' each' : ''}`),
      m.px != null || num(p.value) != null ? dd('Value now', `${esc(usd(m.value))}${m.px != null ? ' · ' + esc(cents(p.price)) + ' each' : ''}`) : '',
      m.n != null && m.cost != null ? dd('If it wins', `pays ${esc(usd(m.n))} · <span class="up">${esc(usd(m.n - m.cost, true))}</span>`) : '',
      m.closes != null ? dd('Closes', esc(ff(F.full, m.closes)) + ' ET') : '',
      m.prob != null ? dd('Live edge', `<span class="${cls(m.edge)}">${esc(edgeC(m.edge))}</span> · chance ${esc(pct(m.prob))}${m.ev != null ? ' · EV ' + esc(usd(m.ev, true)) : ''}`) : '',
      p.category ? dd('Market', esc(String(p.category).slice(0, 40))) : '',
    ].join('');
    const price = num(p.price) != null ? ' → ' + esc(cents(p.price)) : '';
    return `<li class="pos" data-side="${esc(m.sk)}"><details data-k="${esc(m.key)}"${S.open.has(m.key) ? ' open' : ''}><summary><div class="pr">`
      + `<b class="t">${sideTag(m.side)}${m.asset ? `<span class="asset">${esc(m.asset)}</span>` : ''}${esc(m.title)}</b><span class="v ${cls(m.pnl)}">${m.pnl == null ? '<span class="open">OPEN</span>' : esc(usd(m.pnl, true))}</span>`
      + `<small>${esc(m.n == null ? '?' : fmtN(m.n))} × ${esc(cents(p.avg_price))}${price}${m.edge != null ? ` <span class="edge ${cls(m.edge)}">edge ${esc(edgeC(m.edge))}</span>` : ''}</small>`
      + `<span class="v2">${m.value == null ? '' : esc(usd(m.value))}${ret ? ' · ' + esc(ret) : ''}</span>${cdn ? `<small class="cdl">${cdn}</small>` : ''}</div></summary><dl class="dl">${det}</dl></details></li>`;
  }

  // ================================================================== contract v3 (2026-11-03): what Kalshi's own app, Polymarket
  // and the prediction-market trackers show and this page lacked: alerts, live edge, Kelly sizing, P&L by market category, win rate
  // and ROI by price, calibration. Each reads the bot's own v3 list when it sends one (every settled trade), else works it out from
  // the recent trades list (the last 40) and says so. All optional: a v1 / v2 feed shows exactly the sections it showed before.
  const LEVELS = ['bad', 'warn', 'info'];
  const edgeC = (x) => sgn(x, true) + Math.abs(x * 100).toFixed(1) + '¢';           // 0.05 -> '+5.0¢'
  const unit = (v) => { const x = num(v); return x != null && x >= 0 && x <= 1 ? x : null; };
  const settled = (v) => v.tr.filter((t) => num(t.pnl) != null && String(t.action == null ? '' : t.action).trim().toLowerCase() !== 'sell');
  const catOf = (r) => {
    const c = r.category == null ? '' : String(r.category).trim().slice(0, 40);
    if (c) return c;
    const a = assetOf(r);
    return a ? ({ BTC: 'Bitcoin', ETH: 'Ethereum', SOL: 'Solana', DOGE: 'Dogecoin', GOLD: 'Gold', SILVER: 'Silver' }[a] || a) : 'Other';
  };
  const roiTxt = (pnl, st) => (st > 0 && pnl != null ? pct(pnl / st, true) : '—');
  const fromNote = (n) => `<p class="muted small src">From the last ${n} settled ${n === 1 ? 'trade' : 'trades'} in the list: the bot's own totals show once it sends them.</p>`;

  // ---- alerts: the bot's own list, plus what the page sees (a bet settling within 15 min, a losing run, a quiet bot)
  function alertsList(k, v) {
    const out = [];
    arr(k.alerts).filter(isObj).forEach((a) => {
      const tx = a.text == null ? '' : String(a.text).trim().slice(0, 160);
      const lv = String(a.level == null ? '' : a.level).trim().toLowerCase();
      if (tx) out.push({ t: parseT(a.t), lv: LEVELS.indexOf(lv) >= 0 ? lv : 'info', tx });
    });
    v.pos.forEach((p) => {
      const c = parseT(p.closes), s = c ? c - nowS() : 0;
      if (c && s > 0 && s < 900) out.push({ t: c, lv: 'info', tx: 'Settles soon: ' + String(p.title || p.ticker || 'an open bet').slice(0, 100), c });
    });
    if (!Array.isArray(k.alerts)) {
      let run = 0;
      for (let i = 0; i < v.tr.length; i++) { const x = num(v.tr[i].pnl); if (x == null) continue; if (x < -0.005) run++; else if (x > 0.005) break; }
      if (run >= 3) out.push({ t: parseT(v.tr[0].t), lv: 'warn', tx: `${run} losses in a row` });
    }
    return out.sort((a, b) => LEVELS.indexOf(a.lv) - LEVELS.indexOf(b.lv) || (b.t || 0) - (a.t || 0)).slice(0, 12);
  }
  function alertsHtml(k, v) {
    const a = alertsList(k, v), bad = a.filter((x) => x.lv !== 'info').length;
    const head = `<div class="card-h"><h2>Alerts${a.length ? ' · ' + a.length : ''}</h2>${bad ? `<span class="r down">${bad} need${bad === 1 ? 's' : ''} you</span>` : ''}</div>`;
    if (!a.length) return `<section class="card al-card" id="sec-al">${head}<p class="calm"><i aria-hidden="true"></i>All quiet: nothing needs you.</p></section>`;
    return `<section class="card al-card" id="sec-al">${head}<ul class="al">${a.map((x) => `<li class="${x.lv}"><i aria-hidden="true"></i><span>${esc(x.tx)}</span>`
      + `<small${x.c ? ` class="cdn soon" data-c="${x.c}"` : ''}>${x.c ? esc(closesTxt(x.c)) : x.t ? esc(ago(x.t)) : ''}</small></li>`).join('')}</ul></section>`;
  }

  // ---- Kelly: the bot's own settings (fraction, bankroll, max bet, min edge), else a quarter Kelly of the balance
  const kellyCfg = (k) => {
    const c = isObj(k.kelly) ? k.kelly : {}, f = unit(c.fraction), b = num(c.bankroll), mb = num(c.max_bet), me = unit(c.min_edge);
    return { f: f && f > 0 ? f : 0.25, own: f != null && f > 0, bank: b != null && b > 0 ? b : num(k.balance), max: mb != null && mb > 0 ? mb : null, minEdge: me };
  };
  // full Kelly for a binary contract bought at price c with a chance p of paying $1: (p - c) / (1 - c)
  const kellyF = (p, c) => (p == null || c == null || c <= 0 || c >= 1 ? null : (p - c) / (1 - c));
  function kellyHtml(k, v) {
    const cfg = kellyCfg(k), ps = v.pos.map(posModel).filter((m) => m.prob != null && (m.px != null || m.avg != null));
    const fr = S.kf || cfg.f, fl = fr === 1 ? 'Full' : fr === 0.5 ? '½' : fr === 0.25 ? '¼' : Math.round(fr * 100) + '%';
    const bank = cfg.bank;
    const rows = ps.map((m) => {
      const c = m.px != null ? m.px : m.avg, f = kellyF(m.prob, c), raw = f != null && f > 0 && bank ? f * fr * bank : 0, cap = cfg.max != null && raw > cfg.max;
      const want = cap ? cfg.max : raw, cost = m.cost, ratio = want > 0 && cost != null ? cost / want : null;
      const tag = f == null ? '' : f <= 0 ? '<span class="kt bad">no edge</span>' : ratio == null ? '' : ratio > 1.5 ? '<span class="kt warn">over</span>' : ratio < 0.5 ? '<span class="kt">under</span>' : '<span class="kt ok">on size</span>';
      return `<li><b class="t">${sideTag(m.side)}${esc(m.title)}</b><span class="v ${f != null && f > 0 ? 'up' : 'down'}">${f == null ? '—' : esc(pct(Math.max(-1, f), false))}</span>`
        + `<small>chance ${esc(pct(m.prob))} vs ${esc(cents(c))} · edge ${esc(edgeC(m.prob - c))}</small>`
        + `<small class="kk">${esc(fl)} Kelly ${esc(usd(want))}${cap ? ' (max bet)' : ''} · bet ${esc(usd(cost))} ${tag}</small></li>`;
    }).join('');
    const seg = `<div class="seg" role="group" aria-label="Kelly fraction">${[[0.25, '¼'], [0.5, '½'], [1, 'Full']].map((x) => `<button type="button" data-act="kf" data-v="${x[0]}" aria-pressed="${fr === x[0]}">${x[1]}</button>`).join('')}</div>`;
    const c0 = S.calc;
    return `<section class="card" id="sec-kelly"><div class="card-h"><h2>Edge &amp; sizing</h2>${seg}</div>`
      + `<p class="muted small">Kelly = the share of the bankroll a bet is worth: (chance − price) ÷ (1 − price). ${cfg.own ? `The bot sizes at ${esc(pct(cfg.f))} Kelly` : 'Most pros bet a quarter of it'}${bank ? ` · bankroll ${esc(usd(bank))}` : ''}${cfg.max ? ` · max bet ${esc(usd(cfg.max))}` : ''}${cfg.minEdge != null ? ` · min edge ${esc((cfg.minEdge * 100).toFixed(1))}¢` : ''}.</p>`
      + (rows ? `<ul class="rows kel">${rows}</ul>` : '<p class="empty">No open bet carries the bot\'s own chance yet (the <code>prob</code> field): try the calculator.</p>')
      + `<div class="calc" role="group" aria-label="Kelly calculator"><label><span class="lab">Your chance %</span><input id="kcP" class="q" type="text" inputmode="decimal" autocomplete="off" value="${esc(c0.p)}" aria-label="Your chance in percent"></label>`
      + `<label><span class="lab">Price ¢</span><input id="kcC" class="q" type="text" inputmode="decimal" autocomplete="off" value="${esc(c0.c)}" aria-label="Price in cents"></label>`
      + `<output id="kcOut" class="calc-o" aria-live="polite">${calcOut(cfg, fr)}</output></div></section>`;
  }
  function calcOut(cfg, fr) {
    const p = num(S.calc.p), c = num(S.calc.c);
    if (p == null || c == null || p <= 0 || p >= 100 || c <= 0 || c >= 100) return '<span class="muted">Type a chance and a price (1-99).</span>';
    const pp = p / 100, cc = c / 100, f = kellyF(pp, cc), ev = pp - cc;
    if (f <= 0) return `<b class="down">No bet</b><span>edge ${esc(edgeC(ev))} · the price is above your chance</span>`;
    const bank = cfg.bank, stake = bank ? Math.min(f * fr * bank, cfg.max || Infinity) : null;
    return `<b class="up">${esc(pct(f * fr))} of the bankroll</b><span>edge ${esc(edgeC(ev))} · ROI ${esc(pct(ev / cc, true))} a contract</span>`
      + (stake != null ? `<span>bet ${esc(usd(stake))} ≈ ${esc(fmtN(Math.floor(stake / cc)))} contracts</span>` : '');
  }

  // ---- P&L by market category
  function catRows(k, v) {
    if (Array.isArray(k.categories)) {
      return { own: true, rows: arr(k.categories).filter(isObj).map((c) => ({ name: String(c.name == null ? '' : c.name).slice(0, 40), group: c.group == null ? '' : String(c.group).slice(0, 30),
        n: num(c.trades), w: num(c.wins), l: num(c.losses), pnl: num(c.pnl), st: num(c.staked) })).filter((c) => c.name) };
    }
    const m = new Map();
    settled(v).forEach((t) => {
      const name = catOf(t), r = m.get(name) || { name, group: '', n: 0, w: 0, l: 0, pnl: 0, st: 0 }, x = num(t.pnl), c = num(t.contracts), px = dol(t.price);
      r.n++; r.pnl += x; if (x > 0.005) r.w++; else if (x < -0.005) r.l++;
      if (c != null && px != null) r.st += Math.abs(c) * px;
      m.set(name, r);
    });
    return { own: false, rows: Array.from(m.values()) };
  }
  function catHtml(k, v) {
    const d = catRows(k, v), rows = d.rows.sort(by((r) => r.pnl, true));
    if (!rows.length) return '';
    const mx = Math.max.apply(null, rows.map((r) => Math.abs(r.pnl || 0))) || 1, n = sum(rows.map((r) => r.n || 0));
    return `<section class="card" id="sec-cat"><div class="card-h"><h2>By market · ${rows.length}</h2><span class="r muted">${esc(fmtN(n))} trades</span></div>`
      + `<ul class="brk">${rows.map((r) => {
        const wr = r.w != null && r.l != null && r.w + r.l > 0 ? r.w / (r.w + r.l) : null, w = Math.max(2, (Math.abs(r.pnl || 0) / mx) * 50);
        return `<li><div class="bk-t"><b>${esc(r.name)}</b>${r.group ? `<small>${esc(r.group)}</small>` : ''}<span class="v ${cls(r.pnl)}">${esc(usd(r.pnl, true))}</span></div>`
          + `<div class="dv" aria-hidden="true"><i class="${(r.pnl || 0) < 0 ? 'neg' : 'pos'}" style="width:${w.toFixed(1)}%"></i></div>`
          + `<small>${esc(fmtN(r.n || 0))} ${r.n === 1 ? 'trade' : 'trades'}${wr == null ? '' : ' · win ' + esc(pct(wr))}${r.st ? ' · ROI ' + esc(roiTxt(r.pnl, r.st)) : ''}</small></li>`;
      }).join('')}</ul>${d.own ? '' : fromNote(n)}</section>`;
  }

  // ---- win rate and ROI by entry price: is the bot paid enough for the risk at each price?
  const EDGES = [0, 0.2, 0.4, 0.6, 0.8, 0.9, 0.95, 0.97, 0.99, 1.0001];
  function bucketRows(k, v) {
    if (Array.isArray(k.buckets)) {
      return { own: true, rows: arr(k.buckets).filter(isObj).map((b) => ({ lo: unit(b.lo), hi: unit(b.hi), n: num(b.trades), w: num(b.wins), l: num(b.losses), pnl: num(b.pnl), st: num(b.staked) }))
        .filter((b) => b.lo != null && b.hi != null && b.lo < b.hi).sort(by((b) => b.lo)) };
    }
    const m = new Map();
    settled(v).forEach((t) => {
      const px = dol(t.price), x = num(t.pnl), c = num(t.contracts);
      if (px == null || px <= 0 || px >= 1.0001) return;
      let i = 0; while (i < EDGES.length - 2 && px >= EDGES[i + 1]) i++;
      const r = m.get(i) || { lo: EDGES[i], hi: Math.min(1, EDGES[i + 1]), n: 0, w: 0, l: 0, pnl: 0, st: 0 };
      r.n++; r.pnl += x; if (x > 0.005) r.w++; else if (x < -0.005) r.l++;
      if (c != null) r.st += Math.abs(c) * px;
      m.set(i, r);
    });
    return { own: false, rows: Array.from(m.values()).sort(by((b) => b.lo)) };
  }
  const cRange = (lo, hi) => `${Math.round(lo * 100)}–${Math.round(hi * 100)}¢`;
  function bucketHtml(k, v) {
    const d = bucketRows(k, v), rows = d.rows;
    if (!rows.length) return '';
    const n = sum(rows.map((r) => r.n || 0));
    // the win rate a bucket needs to break even is about the price paid (fees aside): the staked share of the contracts' payout
    const body = rows.map((r) => {
      const wr = r.w != null && r.l != null && r.w + r.l > 0 ? r.w / (r.w + r.l) : null, need = (r.lo + r.hi) / 2, short = r.pnl != null ? r.pnl < -0.005 : wr != null && wr + 0.0001 < need;
      return `<tr><td>${esc(cRange(r.lo, r.hi))}<small>${esc(fmtN(r.n || 0))} ${r.n === 1 ? 'trade' : 'trades'}</small></td>`
        + `<td class="${wr == null ? '' : short ? 'down' : 'up'}">${wr == null ? '—' : esc(pct(wr))}<small>needs ~${esc(pct(need))}</small></td>`
        + `<td class="${cls(r.pnl)}">${esc(roiTxt(r.pnl, r.st))}</td><td class="${cls(r.pnl)}">${esc(usd(r.pnl, true))}</td></tr>`;
    }).join('');
    return `<section class="card" id="sec-bk"><div class="card-h"><h2>By price</h2><span class="r muted">${esc(fmtN(n))} trades</span></div>`
      + `<table class="tbl"><thead><tr><th scope="col">Paid</th><th scope="col">Win</th><th scope="col">ROI</th><th scope="col">P&amp;L</th></tr></thead><tbody>${body}</tbody></table>`
      + `<p class="muted small">A contract bought at 96¢ must win about 96% of the time to break even: red = that price range lost money.</p>${d.own ? '' : fromNote(n)}</section>`;
  }

  // ---- calibration: when the bot (or the price) said X%, how often did it win?
  function calibRows(k, v) {
    if (Array.isArray(k.calibration)) {
      return { own: true, basis: String(k.calib_basis || '') === 'model' ? 'model' : 'price',
        rows: arr(k.calibration).filter(isObj).map((c) => ({ p: unit(c.p), n: num(c.n), hit: unit(c.hit) })).filter((c) => c.p != null && c.hit != null && c.n >= 1) };
    }
    const m = new Map();
    let model = true;
    const st = settled(v);
    st.forEach((t) => { if (unit(t.prob) == null) model = false; });
    st.forEach((t) => {
      const p = model ? unit(t.prob) : dol(t.price), x = num(t.pnl);
      if (p == null || p <= 0 || p > 1) return;
      let i = 0; while (i < EDGES.length - 2 && p >= EDGES[i + 1]) i++;
      const r = m.get(i) || { s: 0, n: 0, w: 0 };
      r.s += p; r.n++; if (x > 0.005) r.w++;
      m.set(i, r);
    });
    return { own: false, basis: model && st.length ? 'model' : 'price', rows: Array.from(m.values()).map((r) => ({ p: r.s / r.n, n: r.n, hit: r.w / r.n })).sort(by((r) => r.p)) };
  }
  function calibHtml(k, v) {
    const d = calibRows(k, v), rows = d.rows;
    if (!rows.length) return '';
    const n = sum(rows.map((r) => r.n)), lo0 = Math.min.apply(null, rows.map((r) => Math.min(r.p, r.hit)));
    const lo = Math.max(0, lo0 > 0.6 ? Math.floor((lo0 - 0.02) * 20) / 20 : Math.floor((lo0 - 0.05) * 10) / 10), span = 1 - lo, W = 300, P = 8;
    const X = (x) => P + ((x - lo) / span) * (W - 2 * P), Y = (y) => W - P - ((y - lo) / span) * (W - 2 * P);
    const gap = sum(rows.map((r) => r.n * (r.hit - r.p))) / n, big = rows.slice().sort(by((r) => r.n, true))[0];
    const ticks = []; for (let t = lo; t <= 1.0001; t += span > 0.5 ? 0.25 : 0.05) ticks.push(+t.toFixed(2));
    const dots = rows.map((r) => `<circle cx="${X(r.p).toFixed(1)}" cy="${Y(r.hit).toFixed(1)}" r="${Math.min(12, 4 + Math.sqrt(r.n) * 0.9).toFixed(1)}" class="${r.hit + 0.0001 < r.p ? 'cb-n' : 'cb-p'}"><title>${esc(pct(r.p))} said, ${esc(pct(r.hit))} won (${r.n})</title></circle>`).join('');
    const what = d.basis === 'model' ? "the bot's own chance" : 'the price paid (the market\'s chance)';
    return `<section class="card" id="sec-cb"><div class="card-h"><h2>Calibration</h2><span class="r ${gap < -0.005 ? 'down' : gap > 0.005 ? 'up' : 'muted'}">${esc(sgn(gap, true) + Math.abs(gap * 100).toFixed(1))} pts</span></div>`
      + `<div class="cb"><svg viewBox="0 0 ${W} ${W}" role="img" aria-label="${esc(`Calibration, ${n} settled bets: ${rows.map((r) => pct(r.p) + ' said, ' + pct(r.hit) + ' won').join('; ')}`)}">`
      + ticks.map((t) => `<line class="cb-g" x1="${X(t).toFixed(1)}" x2="${X(t).toFixed(1)}" y1="${P}" y2="${W - P}"/><line class="cb-g" y1="${Y(t).toFixed(1)}" y2="${Y(t).toFixed(1)}" x1="${P}" x2="${W - P}"/>`).join('')
      + `<line class="cb-d" x1="${X(lo)}" y1="${Y(lo)}" x2="${X(1)}" y2="${Y(1)}"/>${dots}</svg>`
      + ticks.map((t, i) => `<span class="cb-t${i === 0 ? ' a0' : i === ticks.length - 1 ? ' a1' : ''}" style="left:${(X(t) / W * 100).toFixed(1)}%">${Math.round(t * 100)}%</span>`).join('')
      + '<span class="cb-ax cb-y">↑ won · said →</span></div>'
      + `<p class="muted small">Predicted = ${esc(what)}. On the line = honest odds; above it = the bets win more than they cost (green), below = less (red). `
      + `Biggest group: ${esc(pct(big.p))} said, ${esc(pct(big.hit))} won, ${esc(fmtN(big.n))} ${big.n === 1 ? 'bet' : 'bets'}.</p>${d.own ? '' : fromNote(n)}</section>`;
  }

  // ---- the ticker tape under the header: open bets and the latest results, scrolling (still with reduced motion)
  function tapeHtml(v) {
    const it = [];
    v.pos.slice(0, 6).forEach((p) => { const m = posModel(p, 0); it.push(`<span>${sideTag(m.side)}${esc((m.asset || '') + ' ' + cents(p.avg_price))}${m.prob != null ? ` <em class="up">edge ${esc(edgeC(m.edge))}</em>` : ''}${m.closes ? ` <em>${esc(left(m.closes) || 'settling')}</em>` : ''}</span>`); });
    settled(v).slice(0, 10).forEach((t) => { const x = num(t.pnl), a = assetOf(t); it.push(`<span>${esc(a || catOf(t))} <em class="${cls(x)}">${esc(usd(x, true))}</em></span>`); });
    if (!it.length) return '';
    const run = it.join('<b aria-hidden="true">◆</b>');
    return `<div class="tape-in">${run}<b aria-hidden="true">◆</b>${run}<b aria-hidden="true">◆</b></div>`;
  }

  // ---- recent trades, grouped by day, with show more
  function tradesHtml(v) {
    const tr = v.tr, n = tr.length;
    if (!n) return '<section class="card" id="sec-tr"><div class="card-h"><h2>Recent trades</h2></div><p class="empty">No trades yet.</p></section>';
    const shown = Math.min(n, Math.max(TR_PAGE, S.trShown)), rest = n - shown;
    const dp = new Map(v.days), today = dayKey(nowS()), yday = dayKey(nowS() - 86400);
    const out = [];
    let last = null;
    tr.slice(0, shown).forEach((t) => {
      const tt = parseT(t.t), k = tt ? dayKey(tt) : '';
      if (k !== last) {
        last = k;
        const p = dp.get(k);
        out.push(`<li class="day">${esc(k === today ? 'Today' : k === yday ? 'Yesterday' : k ? dayLabel(k) : 'Earlier')}${p != null ? `<span class="${cls(p)}">${esc(usd(p, true))}</span>` : ''}</li>`);
      }
      const side = sideOf(t), c = num(t.contracts), pnl = num(t.pnl), act = String(t.action == null ? '' : t.action).trim().toLowerCase(), a = assetOf(t);
      const what = [cap(act), c == null ? '' : fmtN(c)].filter(Boolean).join(' ') + (num(t.price) == null ? '' : ' @ ' + cents(t.price));
      const strat = t.strategy != null ? String(t.strategy) : t.book != null ? String(t.book) : '';
      out.push(`<li class="row"><b class="t">${sideTag(side)}${a ? `<span class="asset">${esc(a)}</span>` : ''}${esc(t.title || t.ticker || '')}</b>`
        + `<span class="v ${cls(pnl)}">${pnl != null ? esc(usd(pnl, true)) : act === 'sell' ? '' : '<span class="open">OPEN</span>'}</span>`
        + `<small>${esc(what)}${tt ? ' · ' + esc(ff(F.time, tt)) : ''}${strat ? ' · ' + esc(strat.slice(0, 40)) : ''}</small></li>`);
    });
    const more = n > TR_PAGE ? `<button type="button" class="more" data-act="more">${rest > 0 ? `Show ${Math.min(TR_PAGE, rest)} more · ${rest} left` : 'Show fewer'}</button>` : '';
    return `<section class="card" id="sec-tr"><div class="card-h"><h2>Recent trades</h2><span class="r muted">${shown} of ${n}</span></div><ul class="rows" id="trList">${out.join('')}</ul>${more}</section>`;
  }

  // ---- preview while not connected (owner can't see his dashboard until the bot's chat finishes the setup): a built-in sample
  // in the real bot's shape. Built on every draw, never kept: not in S.k / S.raw, not the offline copy, not in any cache; real
  // data (or a real copy on this phone) ends it and hides the button.
  const previewing = () => S.preview && !S.k && S.state !== 'ok';
  function sample() {
    const now = Math.floor(Date.now() / 1000), today = dayKey(now) || '2026-11-01', p = pd(today);
    let seed = 20261101;
    const rnd = () => { seed = (seed * 48271) % 2147483647; return seed / 2147483647; };
    const r2 = (x) => Math.round(x * 100) / 100;
    const trades = [];
    let t = now - 240;
    for (let i = 0; i < 16; i++) {
      const close = Math.ceil((t + 60) / 900) * 900, c = i % 7 === 3 ? 'BTCD' : i % 11 === 6 ? 'GOLD' : ['ETH', 'BTC', 'HYPE'][i % 3];
      const n = 10 + Math.floor(rnd() * 10), price = r2(95.5 + rnd() * 2) / 100, win = rnd() < 0.9;
      const title = c === 'BTCD' ? `Bitcoin above $80,500 at ${ff(F.time, Math.ceil(close / 3600) * 3600)} ET ${ff(F.md, close)}` : c === 'GOLD' ? 'Gold 5 PM close'
        : `${c} up or down · 15 min to ${ff(F.time, close)} ET ${ff(F.md, close)}`;
      trades.push({ t, ticker: `KX${c}${c === 'BTCD' || c === 'GOLD' ? '' : '15M'}-SAMPLE-${i + 1}`, title, side: c === 'BTCD' || c === 'GOLD' ? (rnd() < 0.7 ? 'yes' : 'no') : rnd() < 0.6 ? 'UP' : 'DOWN',
        action: 'buy', contracts: n, price, pnl: i === 0 ? null : r2(win ? n * (1 - price) - 0.02 * n : -n * price - 0.02 * n) });
      t -= 1500 + Math.floor(rnd() * 1800);
    }
    const todayPnl = r2(sum(trades.filter((x) => x.pnl != null && dayKey(x.t) === today).map((x) => x.pnl)));
    const days = [];
    for (let i = 29; i >= 1; i--) days.push([new Date(Date.UTC(p.y, p.m - 1, p.d - i)).toISOString().slice(0, 10), r2(-6 + rnd() * 9.5)]);
    days.push([today, todayPnl]);
    const equity = [];
    let bal = 67.1;
    for (let i = 96; i >= 1; i--) { bal = r2(Math.max(64, bal + (rnd() - 0.47) * 0.5)); equity.push([now - i * 900, bal]); }
    equity.push([now, 68.12]);
    const first = trades[0];
    return {
      v: 1, kind: 'kalshi', name: 'Sample bot', mode: 'live', running: true, t: now - 30, pub_t: now - 20, balance: 68.12,
      status: 'Sample · 3 live strategies · 1 open bet', note: 'Sample data, not your account',
      today_pnl: todayPnl, week_pnl: -6.4, total_pnl: -14.45,
      kelly: { fraction: 0.25, bankroll: 68.12, max_bet: 20 },
      alerts: [{ t: now - 1800, level: 'warn', text: 'Sample alert: 2 losses in a row on HYPE' }],
      positions: [{ ticker: first.ticker, title: first.title, side: first.side, contracts: first.contracts, avg_price: first.price, prob: 0.985,
        value: r2(first.contracts * first.price), closes: new Date((Math.ceil((now + 60) / 900) * 900) * 1000).toISOString() }],
      trades, days, equity,
      strategies: [
        { name: '15-min favourites', mode: 'live', running: true, today_pnl: r2(todayPnl - 0.41), total_pnl: -21.37, trades: 612, wins: 571, losses: 41 },
        { name: 'Late favourite (BTC hourly)', mode: 'live', running: true, today_pnl: 0.41, total_pnl: 5.12, trades: 48, wins: 45, losses: 3 },
        { name: 'Gold 5 PM', mode: 'live', running: true, today_pnl: 0, total_pnl: 1.8, trades: 9, wins: 8, losses: 1 },
      ],
    };
  }
  const previewBar = () => '<div class="note sample" id="previewBar" role="status"><p><b>Sample data, not your account</b>'
    + '<span>How this page looks once your bot is connected.</span></p><button type="button" class="btn ghost" data-act="exit-preview">Exit preview</button></div>';

  // ---- waiting / error / loading
  const waitHtml = () => '<section class="card wait"><h2>Connect your Kalshi bot</h2><p>Your Kalshi bot runs on its own server. One paste in its own chat connects it to Jarvis:</p>'
    + `<code id="step">${esc(STEP)}</code><div class="wait-a"><button type="button" class="btn" data-act="copy">Copy the message</button><span class="muted" id="copied" role="status"></span></div>`
    + '<p class="muted">After that it sends its numbers here every minute, by itself.</p>'
    + `<ul class="feat" aria-label="What this page shows once connected">${['Balance &amp; P&amp;L', 'Alerts', 'Open bets · live edge', 'Kelly sizing', 'By market', 'By price', 'Calibration', 'P&amp;L calendar', 'Equity curve']
      .map((f) => `<li>${f}</li>`).join('')}</ul>`
    + (S.k ? '' : '<button type="button" class="quiet" data-act="preview">Preview with sample data</button>') + '</section>';
  const errHtml = () => `<section class="card err"><p class="muted">No connection to the Kalshi feed right now${navigator.onLine === false ? ' (this phone is offline)' : ''}. Tap Refresh to try again.</p>`
    + '<div><button type="button" class="btn ghost" data-act="retry">Try again</button></div></section>';
  const skelHtml = () => '<div class="sk sk1" aria-hidden="true"></div><div class="sk sk2" aria-hidden="true"></div><div class="sk sk3" aria-hidden="true"></div>';

  function footHtml() {
    if (previewing()) return 'Sample data for the preview, not your account: none of these numbers are real.';
    const k = S.k;
    if (!k || S.state === 'waiting') return 'Read-only. The Kalshi bot runs on its own server.';
    const pt = parseT(k.pub_t);
    return `Read-only · the bot's own numbers and prices, as of its last update${pt ? ' · sent ' + esc(when(pt)) : ''}`;
  }

  // ------------------------------------------------------------------ render
  function fit(root) {                    // shrink a number until it fits its box (long values, wide fonts): never cut off
    (root || document).querySelectorAll('.fit').forEach((el) => {
      el.style.fontSize = '';
      if (el.scrollWidth <= el.clientWidth + 0.5) return;
      let fs = parseFloat(getComputedStyle(el).fontSize) || 14;
      for (let i = 0; i < 24 && fs > 9 && el.scrollWidth > el.clientWidth + 0.5; i++) { fs -= 0.5; el.style.fontSize = fs + 'px'; }
    });
  }

  function render() {
    // not while a finger reads the chart or the iPhone's sort picker is open (a new body would close it): right after
    if (S.scrub || (document.activeElement && document.activeElement.id === 'posSort')) { S.pend = true; return; }
    const body = $('#body');
    if (!body) return;
    const ae = document.activeElement, fid = ae && ae.id && body.contains(ae) ? ae.id : '';
    let sel = null;
    try { sel = fid && typeof ae.selectionStart === 'number' ? [ae.selectionStart, ae.selectionEnd] : null; } catch (_) { sel = null; }
    $('#sub').innerHTML = subHtml();
    let html;
    const pv = previewing();
    if (S.state === 'waiting' && !pv) html = waitHtml();
    else if (!S.k && !pv) html = S.state === 'error' ? errHtml() : skelHtml();
    else {
      const k = pv ? sample() : S.k, v = norm(k);
      S.v = v;
      html = [pv ? previewBar() : notesHtml(k), safe('balance', () => heroHtml(k, v)), safe('alerts', () => alertsHtml(k, v)), safe('equity', () => eqHtml(v)),
        safe('open bets', () => posHtml(v)), safe('sizing', () => kellyHtml(k, v)), safe('strategies', () => stratHtml(v)), safe('markets', () => catHtml(k, v)),
        safe('prices', () => bucketHtml(k, v)), safe('calibration', () => calibHtml(k, v)), safe('daily P&L', () => barsHtml(v)), safe('calendar', () => calHtml(v)),
        safe('stats', () => statsHtml(v, k)), safe('trades', () => tradesHtml(v))].join('');
    }
    S.label = S.k && S.state !== 'waiting' ? stateOf(S.k)[1] : '';
    const data = !!S.k && S.state !== 'waiting';
    body.classList.toggle('intro', data && S.intro);         // the panels rise in once, not on every minute's update
    if (data) S.intro = false;
    body.innerHTML = html;
    body.setAttribute('aria-busy', !S.k && S.state === 'loading' ? 'true' : 'false');
    body.setAttribute('data-state', pv ? 'preview' : S.state === 'waiting' ? 'waiting' : !S.k ? S.state : S.state === 'error' ? 'offline' : S.label === 'Not updating' && S.state === 'ok' ? 'stale' : S.state === 'loading' ? 'loading' : 'ok');
    const foot = $('#foot');
    if (foot) foot.innerHTML = footHtml();
    const tape = $('#tape');
    if (tape) { let th = ''; try { th = S.v && (S.k || pv) && S.state !== 'waiting' ? tapeHtml(S.v) : ''; } catch (_) { th = ''; } tape.innerHTML = th; tape.hidden = !th; }
    bindChart();
    fit(body);
    if (fid) {
      const nEl = document.getElementById(fid);
      if (nEl) {
        try { nEl.focus({ preventScroll: true }); } catch (_) { nEl.focus(); }
        if (sel && nEl.setSelectionRange) { try { nEl.setSelectionRange(sel[0], sel[1]); } catch (_) { /* not a text field */ } }
      }
    }
    busyUi();
  }

  function swap(id, html) {
    const el = document.getElementById(id);
    if (!el) { render(); return; }
    const t = document.createElement('div');
    t.innerHTML = html;
    const n = t.firstElementChild;
    if (n) { el.replaceWith(n); fit(n); } else el.remove();
  }

  function busyUi() {
    const b = $('#refresh');
    if (b) b.setAttribute('aria-busy', S.busy ? 'true' : 'false');
  }

  function tick() {
    document.querySelectorAll('[data-ago]').forEach((n) => { n.textContent = 'updated ' + ago(+n.getAttribute('data-ago')); });
    document.querySelectorAll('.cdn[data-c]').forEach((n) => { const c = +n.getAttribute('data-c'); n.textContent = closesTxt(c); n.className = 'cdn' + cdnCls(c); });
    if (S.k && S.state !== 'waiting' && stateOf(S.k)[1] !== S.label) render();       // e.g. 15 min without an update: the stale note
  }

  // ------------------------------------------------------------------ interactions (delegated: the sections are re-rendered)
  document.addEventListener('click', (e) => {
    const b = e.target && e.target.closest ? e.target.closest('[data-act]') : null;
    if (!b || b.disabled) return;
    const a = b.getAttribute('data-act'), val = b.getAttribute('data-v') || '';
    if (a === 'kf') { const f = +val; S.kf = [0.25, 0.5, 1].indexOf(f) >= 0 ? f : 0; if (S.v) swap('sec-kelly', kellyHtml(previewing() ? sample() : S.k, S.v)); }
    else if (a === 'range') { S.ui.range = val; saveUi(); if (S.v) { swap('sec-eq', eqHtml(S.v)); bindChart(); } }
    else if (a === 'side') {
      S.ui.side = SIDES.indexOf(val) >= 0 ? val : 'all';
      saveUi();
      document.querySelectorAll('[data-act="side"]').forEach((x) => x.setAttribute('aria-pressed', String(x.getAttribute('data-v') === S.ui.side)));
      const l = $('#posList');
      if (l) l.innerHTML = posRows();
    } else if (a === 'more') {
      const n = S.v ? S.v.tr.length : 0;
      S.trShown = S.trShown >= n ? TR_PAGE : S.trShown + TR_PAGE;
      if (S.v) swap('sec-tr', tradesHtml(S.v));
      if (S.trShown === TR_PAGE) { const sec = $('#sec-tr'); if (sec && sec.scrollIntoView) sec.scrollIntoView({ block: 'nearest' }); }
      const nb = $('#sec-tr .more');
      if (nb) nb.focus({ preventScroll: true });
    } else if (a === 'month') {
      S.cal = /^\d{4}-\d{2}$/.test(val) ? val : '';
      S.calSel = '';
      if (S.v) swap('sec-cal', calHtml(S.v));
      const lab = b.getAttribute('aria-label'), f = Array.prototype.filter.call(document.querySelectorAll('#sec-cal .nav'), (x) => x.getAttribute('aria-label') === lab)[0];
      if (f && !f.disabled) f.focus({ preventScroll: true });
    } else if (a === 'day') {
      S.calSel = S.calSel === val ? '' : val;
      document.querySelectorAll('#sec-cal .cd[data-v]').forEach((x) => x.setAttribute('aria-pressed', String(x.getAttribute('data-v') === S.calSel)));
      const r = $('#calRead');
      if (r && S.v) r.innerHTML = calRead(new Map(S.v.days));
    } else if (a === 'retry') load();
    else if (a === 'copy') copyStep();
    else if (a === 'preview' || a === 'exit-preview') {
      S.preview = a === 'preview' && !S.k;
      S.cal = ''; S.calSel = ''; S.trShown = TR_PAGE; S.q = '';
      render();
      try { window.scrollTo(0, 0); } catch (_) { /* old browser */ }
      const f = $(S.preview ? '#previewBar button' : '[data-act="preview"]');
      if (f) f.focus({ preventScroll: true });
    }
  });
  document.addEventListener('change', (e) => {
    if (e.target && e.target.id === 'posSort') { S.ui.sort = SORTS.some((s) => s[0] === e.target.value) ? e.target.value : 'closes'; saveUi(); const l = $('#posList'); if (l) l.innerHTML = posRows(); }
  });
  document.addEventListener('input', (e) => {
    if (e.target && (e.target.id === 'kcP' || e.target.id === 'kcC')) {
      S.calc[e.target.id === 'kcP' ? 'p' : 'c'] = String(e.target.value || '').replace(/[^\d.]/g, '').slice(0, 6);
      const o = $('#kcOut'), k = previewing() ? sample() : S.k;
      if (o && k) o.innerHTML = calcOut(kellyCfg(k), S.kf || kellyCfg(k).f);
      return;
    }
    if (e.target && e.target.id === 'posQ') { S.q = String(e.target.value || '').slice(0, 80); const l = $('#posList'); if (l) l.innerHTML = posRows(); }
  });
  document.addEventListener('focusout', (e) => {
    if (e.target && e.target.id === 'posSort' && S.pend && !S.scrub) setTimeout(() => { if (S.pend && document.activeElement !== e.target) { S.pend = false; render(); } }, 0);
  });
  document.addEventListener('toggle', (e) => {
    const d = e.target;
    if (d && d.matches && d.matches('details[data-k]')) { const k = d.getAttribute('data-k'); if (d.open) S.open.add(k); else S.open.delete(k); }
  }, true);

  function copyStep() {
    const done = (ok) => { const n = $('#copied'); if (n) n.textContent = ok ? 'Copied' : 'Selected: copy it from the menu'; };
    const pick = () => {
      try { const r = document.createRange(); r.selectNodeContents($('#step')); const s = window.getSelection(); s.removeAllRanges(); s.addRange(r); } catch (_) { /* nothing to select */ }
      done(false);
    };
    try { navigator.clipboard.writeText(paste()).then(() => done(true), pick); } catch (_) { pick(); }
  }

  // ------------------------------------------------------------------ the kit's pin (kit.json, same origin, 3 s at most)
  async function kit() {
    const r = await get('kit.json', {}, 3000);
    if (!r || !r.ok) return;
    let j = null;
    try { j = await r.json(); } catch (_) { return; }
    const h = j && typeof j === 'object' && typeof j.sha256 === 'string' ? j.sha256 : '';
    if (!/^[0-9a-f]{64}$/.test(h)) return;
    STEP = pinned(h);
    const el = $('#step');
    if (el) el.textContent = STEP;
  }

  // ------------------------------------------------------------------ offline
  function offline() {                // sw.js: the page opens without a connection, never on a browser error page
    try {
      if (!('serviceWorker' in navigator)) return;
      navigator.serviceWorker.register('sw.js', { scope: './' }).catch(() => null);
    } catch (_) { /* no service worker here */ }
  }

  // ------------------------------------------------------------------ start
  theme();
  $('#refresh').addEventListener('click', () => load());
  render();                         // the saved copy (or the loading cards) at once, then the feed
  load();
  setInterval(() => { if (document.visibilityState === 'visible') load(); }, POLL_MS);
  setInterval(() => { if (document.visibilityState === 'visible') tick(); }, TICK_MS);
  document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'visible' && Date.now() - S.at > 15e3) load(); });
  window.addEventListener('pageshow', (e) => { if (e.persisted) load(); });
  window.addEventListener('online', () => load());
  let rz = 0;
  window.addEventListener('resize', () => { cancelAnimationFrame(rz); rz = requestAnimationFrame(() => fit()); });
  try {                             // Jarvis's fonts swap in after the first paint: numbers are fitted again then
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(() => fit());
    if (document.fonts && document.fonts.addEventListener) document.fonts.addEventListener('loadingdone', () => fit());
  } catch (_) { /* no font loading API */ }
  kit();
  offline();
})();
