// Live View chart (canvas): candles + one overlay per strategy, each in its own colour. Dark (default, owner 2026-10-28
// "make it look sick, very 3D") or light theme.
//   Zlarior (blue)   today's LIT levels (solid = untouched, dashed = swept, with the time), the setup forming (sweep extreme,
//                    swept level, CISD level), the armed limit as a glass position tool (red risk volume, green reward volume,
//                    until the expiry), today's setups (dot per 5m CISD), the live position with REAL micros and $ on its
//                    entry / stop / target / BE lines, entry and exit marks
//   ATLAS (orange)   EMA 21 / 50 of the 5m bars, S/R levels, paper plans (no size), the real account B position
//   Strategy 3       placeholder (purple), nothing to draw yet
// Two canvases: drawChart(base, data, o) draws everything static (on new data / zoom / resize: every 3 s at most, plus
// while dragging with o.fast = no glow); drawFx(overlay, geo, o) draws only the moving parts (crosshair, the pulse on the
// live price and on the entry / stop / target lines) and is cheap enough for every animation frame.
const THEMES = {
  dark: {
    bg0: '#0b1430', bg1: '#02040c', glow: 'rgba(56,189,248,0.10)', floor: 'rgba(56,189,248,0.17)', grid: 'rgba(148,163,184,0.09)',
    axis: '#8ea0bf', ink: '#e2e8f0', up: '#22e58a', upSide: '#0d7a48', upTop: '#9dffd2', dn: '#ff3d6e', dnSide: '#8a1634', dnTop: '#ffb1c4',
    off: 'rgba(2,6,23,0.35)', lit: '#4f9bff', litSoft: 'rgba(79,155,255,0.45)', atlas: '#ff9a3d', atlas2: '#ff6a1a', scalp: '#b388ff',
    risk: [255, 61, 110], reward: [34, 229, 138], good: '#22e58a', bad: '#ff3d6e', now: 'rgba(148,163,184,0.35)',
    label: 'rgba(5,10,28,0.78)', frame: 'rgba(148,163,184,0.18)', last: '#f8fafc', lastInk: '#020617', cross: 'rgba(186,230,253,0.55)', glowOn: true,
    setupFill: '#0b1430', muted: '#64748b',
  },
  light: {
    bg0: '#ffffff', bg1: '#f6f8fc', glow: 'rgba(37,99,235,0.05)', floor: 'rgba(37,99,235,0.07)', grid: '#eef1f5',
    axis: '#64748b', ink: '#0f172a', up: '#16a34a', upSide: '#0e6b31', upTop: '#86efac', dn: '#dc2626', dnSide: '#8f1717', dnTop: '#fca5a5',
    off: 'rgba(100,116,139,0.06)', lit: '#2563eb', litSoft: 'rgba(37,99,235,0.45)', atlas: '#ea580c', atlas2: '#9a3412', scalp: '#7c3aed',
    risk: [220, 38, 38], reward: [22, 163, 74], good: '#16a34a', bad: '#dc2626', now: '#cbd5e1',
    label: 'rgba(255,255,255,0.85)', frame: '#e2e8f0', last: '#0f172a', lastInk: '#ffffff', cross: '#94a3b8', glowOn: false,
    setupFill: '#ffffff', muted: '#94a3b8',
  },
};
const AX = 82, PADL = 6, TOP = 30, BOT = 22, FUT = 0.17;
const SANS = 'system-ui, -apple-system, Segoe UI, Roboto, sans-serif', MONO = 'ui-monospace, SFMono-Regular, Menlo, Consolas, monospace';
const fmt = (x) => x == null || isNaN(x) ? '' : Number(x).toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 2 });
const HMF = new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', hour: '2-digit', minute: '2-digit', hour12: false });
const hm = (t) => HMF.format(new Date(t * 1000)).replace(/^24/, '00');
const etMin = (t) => { const [h, m] = hm(t).split(':').map(Number); return (h % 24) * 60 + m; };
const rgba = (c, a) => `rgba(${c[0]},${c[1]},${c[2]},${a})`;

function fit(cv) {
  const dpr = Math.min(2, window.devicePixelRatio || 1);
  const W = Math.max(200, cv.clientWidth), H = Math.max(160, cv.clientHeight);
  if (cv.width !== Math.round(W * dpr) || cv.height !== Math.round(H * dpr)) { cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr); }
  const g = cv.getContext('2d');
  g.setTransform(dpr, 0, 0, dpr, 0, 0);
  return { g, W, H };
}

export function drawChart(cv, d, o) {
  const C = THEMES[o.theme === 'light' ? 'light' : 'dark'];
  const { g, W, H } = fit(cv);
  const glow = C.glowOn && !o.fast;
  const pw = W - AX - PADL, ph = H - TOP - BOT, right = PADL + pw;
  // ---- background: deep gradient + a soft light from the top
  const bgG = g.createLinearGradient(0, 0, 0, H);
  bgG.addColorStop(0, C.bg0); bgG.addColorStop(1, C.bg1);
  g.fillStyle = bgG; g.fillRect(0, 0, W, H);
  const rg = g.createRadialGradient(W * 0.45, -H * 0.1, 10, W * 0.45, -H * 0.1, H * 1.1);
  rg.addColorStop(0, C.glow); rg.addColorStop(1, 'rgba(0,0,0,0)');
  g.fillStyle = rg; g.fillRect(0, 0, W, H);
  floor(g, C, PADL, TOP, pw, ph);
  const bars = d.bars || [];
  if (!bars.length) return null;
  const secs = d.tf === '5m' ? 300 : 60;
  const N = bars.length;
  const n = Math.max(10, Math.min(N, o.view?.n || (d.tf === '1m' ? 120 : 200)));
  const end = Math.max(0, Math.min(N - 10, o.view?.end || 0));
  const i1 = N - 1 - end, i0 = Math.max(0, i1 - n + 1);
  const barsW = pw * (1 - FUT);
  const bw = barsW / n;
  const X = (i) => PADL + (i - i0 + 0.5) * bw;
  const T0 = bars[0][0];
  const xt = (t) => {                                   // unix time -> x (bars' grid; after the last bar: extrapolated)
    if (t >= bars[N - 1][0]) return X(N - 1 + (t - bars[N - 1][0]) / secs);
    if (t <= T0) return X((t - T0) / secs);
    let lo2 = 0, hi2 = N - 1;
    while (lo2 < hi2) { const m = (lo2 + hi2 + 1) >> 1; if (bars[m][0] <= t) lo2 = m; else hi2 = m - 1; }
    return X(lo2 + Math.min(1, (t - bars[lo2][0]) / secs));
  };
  // ---- price range: the visible bars + what must be seen (the open trade, the armed setup)
  let lo = Infinity, hi = -Infinity;
  for (let i = i0; i <= i1; i++) { lo = Math.min(lo, bars[i][3]); hi = Math.max(hi, bars[i][2]); }
  const rng0 = Math.max(4, hi - lo);
  const want = [];      // [price, how far (x the bars' range) it may stretch the scale]: a far target stays an edge arrow
  const S = d.strategies || {};
  const lit = S.lit || {}, at = S.atlas || {};
  const far = (l) => /target/.test(l.id || '') ? 0.6 : 2.5;
  if (o.on.lit) {
    for (const l of lit.lines || []) if (l.price != null) want.push([l.price, far(l)]);
    if (lit.setup) for (const k of ['ext', 'cisd', 'level']) if (lit.setup[k] != null) want.push([lit.setup[k], 2.5]);
  }
  if (o.on.atlas) for (const l of at.lines || []) if (l.strong && l.price != null) want.push([l.price, far(l)]);
  for (const [p, k] of want) if (p > lo - k * rng0 && p < hi + k * rng0) { lo = Math.min(lo, p); hi = Math.max(hi, p); }
  const pad = (hi - lo) * 0.06 || 2;
  lo -= pad; hi += pad;
  const Y = (p) => TOP + (hi - p) / (hi - lo) * ph;
  const inY = (p) => p != null && p >= lo && p <= hi;
  const pulses = [];   // lines the overlay makes breathe {y, x0, x1, color}
  // ---- outside the Zlarior entry window (02:00-15:30 ET): shaded
  g.fillStyle = C.off;
  let runA = null;
  for (let i = i0; i <= i1 + 1; i++) {
    const outW = i <= i1 && (() => { const m = etMin(bars[i][0]); return m < 120 || m >= 930; })();
    if (outW && runA == null) runA = i;
    if ((!outW || i > i1) && runA != null) { g.fillRect(X(runA) - bw / 2, TOP, (i - runA) * bw, ph); runA = null; }
  }
  // ---- grid + axes
  const step = niceStep((hi - lo) / Math.max(3, Math.floor(ph / 48)));
  g.font = `11px ${MONO}`;
  g.textBaseline = 'middle';
  g.strokeStyle = C.grid; g.lineWidth = 1; g.fillStyle = C.axis; g.textAlign = 'left';
  for (let p = Math.ceil(lo / step) * step; p <= hi; p += step) {
    const y = Math.round(Y(p)) + 0.5;
    g.beginPath(); g.moveTo(PADL, y); g.lineTo(right, y); g.stroke();
    g.fillText(fmt(p), right + 6, y);
  }
  g.textAlign = 'center'; g.textBaseline = 'alphabetic';
  const every = d.tf === '1m' ? (n > 400 ? 120 : n > 200 ? 60 : 30) : (n > 200 ? 240 : 120);
  for (let i = i0; i <= i1; i++) {
    const m = etMin(bars[i][0]);
    if (m % every === 0) {
      const x = Math.round(X(i)) + 0.5;
      g.strokeStyle = C.grid; g.beginPath(); g.moveTo(x, TOP); g.lineTo(x, TOP + ph); g.stroke();
      g.fillStyle = C.axis; g.fillText(hm(bars[i][0]), x, H - 6);
    }
  }
  const xNow = X(i1) + bw / 2;
  g.save(); g.setLineDash([2, 4]); g.strokeStyle = C.now; g.beginPath(); g.moveTo(xNow, TOP); g.lineTo(xNow, TOP + ph); g.stroke(); g.restore();

  const tags = [], notes = [], off = { up: [], dn: [] };
  g.save(); g.beginPath(); g.rect(PADL, TOP, pw, ph); g.clip();          // layers stay inside the plot
  const hline = (p, x0, x1, color, dash, w = 1, gl = 0) => {
    if (!inY(p)) return;
    const y = Math.round(Y(p)) + 0.5;
    g.save(); g.strokeStyle = color; g.lineWidth = w; if (dash) g.setLineDash(dash);
    if (glow && gl) { g.shadowColor = color; g.shadowBlur = gl; }
    g.beginPath(); g.moveTo(Math.max(PADL, x0), y); g.lineTo(Math.min(right, x1), y); g.stroke(); g.restore();
  };

  // ================================================================ ATLAS (under the candles): EMAs + S/R
  if (o.on.atlas) {
    const ema = (rows, color, dash, w) => {
      if (!rows?.length) return;
      g.save(); g.strokeStyle = color; g.lineWidth = w; if (dash) g.setLineDash(dash);
      if (glow) { g.shadowColor = color; g.shadowBlur = 10; }
      g.beginPath();
      let started = false;
      for (const [t, v] of rows) {
        if (t + 300 < bars[i0][0] || t > bars[i1][0] + 300) continue;
        const x = xt(t + 300), y = Y(v);                  // a 5m EMA value is known when its bar closes
        if (!started) { g.moveTo(x, y); started = true; } else g.lineTo(x, y);
      }
      g.stroke(); g.restore();
      const last = rows[rows.length - 1];
      if (last && inY(last[1])) tags.push({ y: Y(last[1]), text: fmt(last[1]), color, small: true });
    };
    ema(at.ema21, C.atlas, null, 1.8);
    ema(at.ema50, C.atlas2, [6, 4], 1.6);
    for (const l of at.levels || []) {
      if (!inY(l.price)) continue;
      hline(l.price, PADL, right, C.atlas, [8, 3, 2, 3], 1, 4);
      notes.push({ x: right - 4, y: Y(l.price) - 7, text: `${l.label} ${fmt(l.price)}`, color: C.atlas, align: 'right', size: 10 });
    }
  }

  // ================================================================ Zlarior levels (under the candles)
  if (o.on.lit) {
    for (const l of lit.levels || []) {
      if (!inY(l.price)) {
        if (!l.taken && l.price != null) (l.price > hi ? off.up : off.dn).push(l);
        continue;
      }
      if (l.taken) {
        if (l.taken_t && l.taken_t < bars[i0][0]) continue;     // swept before the visible bars: nothing to show
        const x1 = l.taken_t ? xt(l.taken_t) : right;
        hline(l.price, PADL, x1, C.litSoft, [5, 4]);
        if (W >= 600) notes.push({ x: Math.min(x1, right) + 4, y: Y(l.price) - 7, text: `✓ ${l.label} swept ${l.taken_hm || ''}`, color: C.litSoft, align: 'left', size: 10 });
      } else {
        hline(l.price, PADL, right, C.lit, null, 1.2, 8);
        tags.push({ y: Y(l.price), text: fmt(l.price), color: C.lit, small: true });
        notes.push({ x: xNow - 6, y: Y(l.price) - 7, text: l.label, color: C.lit, align: 'right', size: 10.5 });
      }
    }
  }

  // ================================================================ candles: extruded 3D bodies with a neon bloom
  const cw = Math.max(1, Math.min(14, bw * 0.62));
  const dep = cw >= 4 ? Math.min(4, cw * 0.35) : 0;            // extrusion depth (right + up)
  for (let i = i0; i <= i1; i++) {
    const [, op, h, l, c] = bars[i], x = X(i), up = c >= op;
    const col = up ? C.up : C.dn;
    const y0 = Y(Math.max(op, c)), y1 = Math.max(Y(Math.min(op, c)), y0 + 1);
    const xl = x - cw / 2;
    g.strokeStyle = col; g.lineWidth = 1;
    g.beginPath(); g.moveTo(Math.round(x) + 0.5, Y(h)); g.lineTo(Math.round(x) + 0.5, Y(l)); g.stroke();
    if (dep) {
      g.fillStyle = up ? C.upSide : C.dnSide;                 // side face
      g.beginPath(); g.moveTo(xl + cw, y0); g.lineTo(xl + cw + dep, y0 - dep); g.lineTo(xl + cw + dep, y1 - dep); g.lineTo(xl + cw, y1); g.closePath(); g.fill();
      g.fillStyle = up ? C.upTop : C.dnTop;                   // top face
      g.beginPath(); g.moveTo(xl, y0); g.lineTo(xl + dep, y0 - dep); g.lineTo(xl + cw + dep, y0 - dep); g.lineTo(xl + cw, y0); g.closePath(); g.fill();
    }
    if (glow) { g.shadowColor = col; g.shadowBlur = 9; }
    g.fillStyle = col;
    g.fillRect(xl, y0, cw, y1 - y0);
    if (glow) g.shadowBlur = 0;
    if (cw >= 5 && y1 - y0 > 3) { g.fillStyle = 'rgba(255,255,255,0.28)'; g.fillRect(xl, y0, 1, y1 - y0); }   // bevel highlight
  }
  g.shadowBlur = 0;

  // ================================================================ glass position tool (risk / reward volumes with depth)
  const box = (x0, x1, pEntry, pStop, pTgt, label) => {
    if (pEntry == null) return;
    x0 = Math.max(PADL, x0); x1 = Math.min(right - 10, x1);
    if (x1 <= x0) return;
    const vol = (pA, colr) => {
      if (pA == null) return;
      const ya = Math.min(Y(pEntry), Y(pA)), yb = Math.max(Y(pEntry), Y(pA)), dz = 10;
      const fg = g.createLinearGradient(0, ya, 0, yb);
      fg.addColorStop(0, rgba(colr, 0.22)); fg.addColorStop(1, rgba(colr, 0.07));
      g.fillStyle = fg; g.fillRect(x0, ya, x1 - x0, yb - ya);                         // front face
      g.fillStyle = rgba(colr, 0.16);                                                 // right side face
      g.beginPath(); g.moveTo(x1, ya); g.lineTo(x1 + dz, ya - dz); g.lineTo(x1 + dz, yb - dz); g.lineTo(x1, yb); g.closePath(); g.fill();
      g.fillStyle = rgba(colr, 0.26);                                                 // top face
      g.beginPath(); g.moveTo(x0, ya); g.lineTo(x0 + dz, ya - dz); g.lineTo(x1 + dz, ya - dz); g.lineTo(x1, ya); g.closePath(); g.fill();
      g.strokeStyle = rgba(colr, 0.55); g.lineWidth = 1; g.strokeRect(x0 + 0.5, ya + 0.5, x1 - x0 - 1, yb - ya - 1);
      g.strokeStyle = 'rgba(255,255,255,0.22)'; g.beginPath(); g.moveTo(x0 + 1, ya + 1.5); g.lineTo(x1 - 1, ya + 1.5); g.stroke();   // glass edge
    };
    vol(pStop, C.risk); vol(pTgt, C.reward);
    if (label) notes.push({ x: x0 + 6, y: Y(pEntry) + (pTgt != null && pTgt < pEntry ? -9 : 11), text: label, color: C.ink, align: 'left', size: 10.5, bold: true });
  };
  if (o.on.lit) {
    const s = lit.setup;
    if (s && s.ext != null && s.ext_t) {
      const x = xt(s.ext_t), y = Y(s.ext), d0 = s.dir || 1;
      if (inY(s.ext)) {
        g.save(); g.fillStyle = C.lit; if (glow) { g.shadowColor = C.lit; g.shadowBlur = 12; }
        g.beginPath();
        if (d0 > 0) { g.moveTo(x, y + 4); g.lineTo(x - 6, y + 14); g.lineTo(x + 6, y + 14); } else { g.moveTo(x, y - 4); g.lineTo(x - 6, y - 14); g.lineTo(x + 6, y - 14); }
        g.fill(); g.restore();
        notes.push({ x, y: y + (d0 > 0 ? 24 : -22), text: `sweep extreme ${fmt(s.ext)}`, color: C.lit, align: 'center', size: 10.5, bold: true });
      }
      if (s.level != null) hline(s.level, x - 12 * bw, x + 6 * bw, C.lit, null, 2.4, 10);
      if (s.cisd != null && !s.armed) {
        hline(s.cisd, x, right, C.lit, [2, 3], 1.6, 8);
        if (inY(s.cisd)) notes.push({ x: xNow + 6, y: Y(s.cisd) - 8, text: `CISD ${d0 > 0 ? 'close above' : 'close below'} ${fmt(s.cisd)}${s.cisd_closed ? ' ✓' : ''}`, color: C.lit, align: 'left', size: 10.5, bold: true });
      }
      const st = { sweep: 'Sweep', inducement: 'Inducement', displacement: 'Waiting for displacement', cisd5: 'CISD' }[s.stage] || s.stage;
      if (inY(s.ext)) notes.push({ x, y: y + (d0 > 0 ? 37 : -35), text: `${s.side || ''} setup · ${st}`, color: C.lit, align: 'center', size: 10 });
    }
    const a = s?.armed;
    if (a && a.limit != null) {
      const x0 = a.armed_t ? xt(a.armed_t) : xNow, x1 = Math.max(xNow + 0.6 * (right - xNow), a.expires_t ? xt(a.expires_t) : xNow);
      box(x0, x1, a.limit, a.stop, a.target, `${a.status === 'tapped' ? 'TAPPED · waiting for a 1m CISD ·' : 'ARMED'} ${a.side || ''} limit ${fmt(a.limit)}`);
    }
    const pos = lit.position;
    if (pos && pos.entry != null) {
      const x0 = pos.entry_t ? xt(pos.entry_t) : xNow;
      box(x0, right, pos.entry, pos.stop, pos.target, null);
      if (pos.entry_t && inY(pos.entry)) {
        const d0 = pos.dir || (pos.side === 'LONG' ? 1 : -1), y = Y(pos.entry);
        g.save(); g.fillStyle = C.lit; if (glow) { g.shadowColor = C.lit; g.shadowBlur = 12; }
        g.beginPath();
        if (d0 > 0) { g.moveTo(x0, y); g.lineTo(x0 - 7, y + 11); g.lineTo(x0 + 7, y + 11); } else { g.moveTo(x0, y); g.lineTo(x0 - 7, y - 11); g.lineTo(x0 + 7, y - 11); }
        g.fill(); g.restore();
      }
    }
    for (const l of lit.lines || []) {
      if (l.price == null) continue;
      const color = l.tone === 'good' ? C.good : l.tone === 'bad' ? C.bad : C.lit;
      const x0 = l.t0 ? xt(l.t0) : PADL;
      if (!inY(l.price)) { (l.price > hi ? off.up : off.dn).push({ label: l.label, price: l.price, color }); continue; }
      hline(l.price, x0, right, color, l.style === 'dash' ? [7, 4] : l.style === 'dot' ? [2, 3] : null, l.strong ? 2 : 1.4, l.strong ? 12 : 6);
      if (l.strong || l.id === 'limit') pulses.push({ y: Math.round(Y(l.price)) + 0.5, x0: Math.max(PADL, x0), x1: right, color });
      tags.push({ y: Y(l.price), text: fmt(l.price), color, strong: l.strong });
      notes.push(l.strong ? { x: xNow + 8, y: Y(l.price) - 9, text: l.label, color, align: 'left', size: 11.5, bold: true }
        : { x: right - 4, y: Y(l.price) - 8, text: l.label, color, align: 'right', size: 11, bold: false });
    }
    for (const m of lit.marks || []) {
      if (m.t < bars[i0][0] - secs || m.t > bars[i1][0] + secs || !inY(m.price)) continue;
      const x = xt(m.t), y = Y(m.price);
      if (m.kind === 'setup') {
        const col = { armed: C.lit, tapped: C.lit, filled: C.good, no_fill: '#f59e0b', rejected: C.muted, blocked: C.muted }[m.status] || C.muted;
        g.save(); g.fillStyle = C.setupFill; g.strokeStyle = col; g.lineWidth = 2; if (glow) { g.shadowColor = col; g.shadowBlur = 8; }
        g.beginPath(); g.arc(x, y, 4.5, 0, Math.PI * 2); g.fill(); g.stroke(); g.restore();
        if (m.status === 'rejected' || m.status === 'blocked') { g.strokeStyle = col; g.lineWidth = 1.5; g.beginPath(); g.moveTo(x - 3, y - 3); g.lineTo(x + 3, y + 3); g.moveTo(x + 3, y - 3); g.lineTo(x - 3, y + 3); g.stroke(); }
        if (n <= 400) notes.push({ x, y: y - 12, text: { rejected: 'rejected', filled: 'filled', armed: 'armed', tapped: 'tapped', no_fill: 'no fill' }[m.status] || 'skipped', color: col, align: 'center', size: 9.5 });
      } else {
        const ex = m.kind === 'exit';
        const col = ex ? ((m.pnl || 0) >= 0 ? C.good : C.bad) : C.lit;
        g.save(); g.fillStyle = col; if (glow) { g.shadowColor = col; g.shadowBlur = 10; }
        g.beginPath(); g.rect(x - 4, y - 4, 8, 8); g.fill(); g.restore();
        notes.push({ x: x + 8, y: y + (ex ? 14 : -12), text: ex ? `EXIT ${m.text || ''} ${m.pnl != null ? (m.pnl >= 0 ? '+' : '-') + '$' + Math.abs(Math.round(m.pnl)).toLocaleString('en-US') : ''}` : `${m.side === 'buy' ? 'BUY' : 'SELL'} ${m.qty || ''} @ ${fmt(m.price)}${m.ok === false ? ' NOT placed' : ''}`, color: col, align: 'left', size: 10.5, bold: true });
      }
    }
  }
  if (o.on.atlas) {
    for (const l of at.lines || []) {
      if (!inY(l.price)) { if (l.strong) (l.price > hi ? off.up : off.dn).push({ label: l.label, price: l.price, color: C.atlas }); continue; }
      const x0 = l.t0 ? xt(l.t0) : PADL;
      hline(l.price, x0, right, C.atlas, l.style === 'dash' ? [7, 4] : l.style === 'dot' ? [2, 3] : null, l.strong ? 2 : 1.3, l.strong ? 12 : 5);
      if (l.strong) pulses.push({ y: Math.round(Y(l.price)) + 0.5, x0: Math.max(PADL, x0), x1: right, color: C.atlas });
      tags.push({ y: Y(l.price), text: fmt(l.price), color: C.atlas, strong: l.strong });
      notes.push({ x: right - 4, y: Y(l.price) + 10, text: l.label, color: C.atlas, align: 'right', size: 10.5, bold: !!l.strong });
    }
  }

  g.restore();                                                           // end of the plot clip
  // ---- last price
  const last = bars[N - 1][4];
  const live = inY(last) ? { x: X(i1), y: Y(last), color: last >= bars[N - 1][1] ? C.up : C.dn } : null;
  if (live) { hline(last, PADL, right, C.last, [1, 2], 1); tags.push({ y: Y(last), text: fmt(last), color: C.last, ink: C.lastInk, strong: true, last: true }); }

  // ---- labels (de-overlapped), off-screen arrows, price tags
  g.textBaseline = 'middle';
  const placed = [];
  g.font = `10.5px ${SANS}`;
  const edge = (list, top) => {
    list.sort((a, b) => top ? a.price - b.price : b.price - a.price);
    list.slice(0, 3).forEach((l, k) => {
      const y = top ? TOP + 10 + k * 13 : TOP + ph - 10 - k * 13;
      const t = `${top ? '▲' : '▼'} ${l.label} ${fmt(l.price)} (${fmt(Math.abs(l.price - last))} pts)`;
      const w = g.measureText(t).width;
      g.fillStyle = C.label; g.fillRect(right - w - 8, y - 6, w + 6, 12);
      g.fillStyle = l.color || C.lit; g.textAlign = 'right'; g.fillText(t, right - 4, y);
      placed.push({ x: right - w - 8, y, w: w + 6 });
    });
  };
  if (o.on.lit || o.on.atlas) { edge(off.up, true); edge(off.dn, false); }
  for (const nt of notes) {
    g.font = `${nt.bold ? '600 ' : ''}${nt.size || 11}px ${SANS}`;
    const w = g.measureText(nt.text).width;
    let x = nt.align === 'right' ? nt.x - w : nt.align === 'center' ? nt.x - w / 2 : nt.x;
    x = Math.max(PADL + 2, Math.min(right - w - 2, x));
    let y = nt.y;
    for (let k = 0; k < 6; k++) {
      const hit = placed.find((p) => Math.abs(p.y - y) < 12 && x < p.x + p.w && x + w > p.x);
      if (!hit) break;
      y = hit.y + (y <= hit.y ? -12 : 12);
    }
    if (y < TOP + 6 || y > TOP + ph - 4) continue;
    placed.push({ x, y, w });
    g.fillStyle = C.label; g.fillRect(x - 3, y - 7, w + 6, 14);
    g.fillStyle = nt.color; g.textAlign = 'left'; g.fillText(nt.text, x, y);
  }
  tags.sort((a, b) => a.y - b.y);
  for (let k = 1; k < tags.length; k++) if (tags[k].y - tags[k - 1].y < 15) tags[k].y = tags[k - 1].y + 15;
  g.font = `600 11px ${MONO}`;
  for (const t of tags) {
    if (t.y < TOP - 4 || t.y > TOP + ph + 4) continue;
    g.save();
    if (glow && t.strong) { g.shadowColor = t.color; g.shadowBlur = 10; }
    g.fillStyle = t.color; roundRect(g, right + 1, t.y - 8, AX - 3, 16, 4); g.fill(); g.restore();
    g.fillStyle = t.ink || (C.glowOn ? '#020617' : '#fff'); g.textAlign = 'left'; g.fillText(t.text, right + 6, t.y + 0.5);
  }
  g.strokeStyle = C.frame; g.lineWidth = 1; g.strokeRect(PADL + 0.5, TOP + 0.5, pw - 1, ph - 1);
  return { bw, n, i0, i1, lo, hi, TOP, ph, PADL, right, W, H, AX, bars, X, pulses, live, theme: o.theme === 'light' ? 'light' : 'dark' };
}

// the perspective floor: lines running to a vanishing point on the horizon + rows closer together towards it
function floor(g, C, x, y, w, h) {
  const top = y + h * 0.58, bot = y + h, vx = x + w * 0.5, vy = top - h * 0.2;
  g.save();
  g.beginPath(); g.rect(x, top, w, bot - top); g.clip();
  const fade = g.createLinearGradient(0, top, 0, bot);
  fade.addColorStop(0, 'rgba(0,0,0,0)'); fade.addColorStop(1, C.floor);
  g.strokeStyle = fade; g.lineWidth = 1;
  for (let k = -14; k <= 14; k++) { g.beginPath(); g.moveTo(vx, vy); g.lineTo(vx + k * w / 9, bot + 40); g.stroke(); }
  for (let k = 1; k <= 9; k++) { const yy = top + (bot - top) * Math.pow(k / 9, 1.8); g.beginPath(); g.moveTo(x, yy); g.lineTo(x + w, yy); g.stroke(); }
  g.restore();
}

function roundRect(g, x, y, w, h, r) {
  g.beginPath(); g.moveTo(x + r, y); g.lineTo(x + w - r, y); g.quadraticCurveTo(x + w, y, x + w, y + r); g.lineTo(x + w, y + h - r);
  g.quadraticCurveTo(x + w, y + h, x + w - r, y + h); g.lineTo(x + r, y + h); g.quadraticCurveTo(x, y + h, x, y + h - r);
  g.lineTo(x, y + r); g.quadraticCurveTo(x, y, x + r, y); g.closePath();
}

// ---- the moving layer: crosshair + the pulse on the live price and the trade lines. t = ms (animation clock); still = no motion.
export function drawFx(cv, geo, o) {
  const { g, W, H } = fit(cv);
  g.clearRect(0, 0, W, H);
  if (!geo) return { hoverBar: null, hoverPx: null };
  const C = THEMES[geo.theme];
  const ph01 = o.still ? 0.5 : (Math.sin((o.t || 0) / 520) + 1) / 2;          // 0..1, ~3.3 s a breath
  for (const p of geo.pulses) {
    g.save(); g.strokeStyle = p.color; g.globalAlpha = 0.15 + 0.35 * ph01; g.lineWidth = 3 + 3 * ph01;
    if (C.glowOn) { g.shadowColor = p.color; g.shadowBlur = 10 + 10 * ph01; }
    g.beginPath(); g.moveTo(p.x0, p.y); g.lineTo(p.x1, p.y); g.stroke(); g.restore();
  }
  if (geo.live) {
    const { x, y, color } = geo.live;
    const k = o.still ? 0.3 : ((o.t || 0) % 1800) / 1800;
    g.save();
    g.strokeStyle = color; g.globalAlpha = 1 - k; g.lineWidth = 2;
    g.beginPath(); g.arc(x, y, 4 + 16 * k, 0, Math.PI * 2); g.stroke();
    g.globalAlpha = 1; g.fillStyle = color; if (C.glowOn) { g.shadowColor = color; g.shadowBlur = 14; }
    g.beginPath(); g.arc(x, y, 3.5, 0, Math.PI * 2); g.fill();
    g.restore();
  }
  let hoverBar = null, hoverPx = null;
  const hv = o.hover;
  if (hv && hv.x > geo.PADL && hv.x < geo.right && hv.y > geo.TOP && hv.y < geo.TOP + geo.ph) {
    const i = Math.max(geo.i0, Math.min(geo.i1, Math.round((hv.x - geo.PADL) / geo.bw - 0.5 + geo.i0)));
    hoverBar = geo.bars[i];
    hoverPx = geo.hi - (hv.y - geo.TOP) / geo.ph * (geo.hi - geo.lo);
    g.save(); g.strokeStyle = C.cross; g.setLineDash([3, 3]);
    g.beginPath(); g.moveTo(geo.X(i), geo.TOP); g.lineTo(geo.X(i), geo.TOP + geo.ph); g.moveTo(geo.PADL, hv.y); g.lineTo(geo.right, hv.y); g.stroke(); g.restore();
    g.fillStyle = C.glowOn ? '#38bdf8' : '#334155'; roundRect(g, geo.right + 1, hv.y - 8, geo.AX - 3, 16, 4); g.fill();
    g.fillStyle = C.glowOn ? '#020617' : '#fff'; g.font = `600 11px ${MONO}`; g.textAlign = 'left'; g.textBaseline = 'middle';
    g.fillText(fmt(Math.round(hoverPx * 4) / 4), geo.right + 6, hv.y + 0.5);
  }
  return { hoverBar, hoverPx };
}

function niceStep(raw) {
  const p = Math.pow(10, Math.floor(Math.log10(Math.max(raw, 1e-6))));
  const f = raw / p;
  return (f < 1.5 ? 1 : f < 3 ? 2 : f < 7 ? 5 : 10) * p;
}
