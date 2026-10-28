// Live View chart (canvas, white background): candles + one overlay per strategy, each in its own colour.
//   Zlarior (blue)   today's LIT levels (solid = untouched, dashed = swept, with the time), the setup forming (sweep extreme,
//                    swept level, CISD level), the armed limit as a position tool (red risk box, green reward box, until the
//                    expiry), today's setups (dot per 5m CISD: armed / filled / rejected), the live position with REAL micros
//                    and $ on its entry / stop / target / BE lines, entry and exit marks
//   ATLAS (orange)   EMA 21 / 50 of the 5m bars, S/R levels, paper plans (no size), the real account B position
//   Strategy 3       placeholder (purple), nothing to draw yet
// drawChart(canvas, data, {on, view, hover, tf}) -> geometry for the page (bar width, the bar under the cursor).
const C = {
  bg: '#ffffff', grid: '#eef1f5', axis: '#64748b', ink: '#0f172a', up: '#16a34a', dn: '#dc2626', off: 'rgba(100,116,139,0.06)',
  lit: '#2563eb', litSoft: 'rgba(37,99,235,0.45)', atlas: '#ea580c', atlas2: '#9a3412', scalp: '#7c3aed',
  risk: 'rgba(220,38,38,0.10)', reward: 'rgba(22,163,74,0.10)', good: '#16a34a', bad: '#dc2626',
};
const AX = 82, PADL = 6, TOP = 30, BOT = 22, FUT = 0.17;
const fmt = (x) => x == null || isNaN(x) ? '' : Number(x).toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 2 });
const hm = (t) => new Date(t * 1000).toLocaleTimeString('en-US', { timeZone: 'America/New_York', hour: '2-digit', minute: '2-digit', hour12: false });
const etMin = (t) => { const [h, m] = hm(t).split(':').map(Number); return (h % 24) * 60 + m; };

export function drawChart(cv, d, o) {
  const dpr = window.devicePixelRatio || 1;
  const W = Math.max(200, cv.clientWidth), H = Math.max(160, cv.clientHeight);
  if (cv.width !== Math.round(W * dpr) || cv.height !== Math.round(H * dpr)) { cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr); }
  const g = cv.getContext('2d');
  g.setTransform(dpr, 0, 0, dpr, 0, 0);
  g.fillStyle = C.bg; g.fillRect(0, 0, W, H);
  const bars = d.bars || [];
  if (!bars.length) return null;
  const secs = d.tf === '5m' ? 300 : 60;
  const N = bars.length;
  const n = Math.max(10, Math.min(N, o.view?.n || (d.tf === '1m' ? 180 : 288)));
  const end = Math.max(0, Math.min(N - 10, o.view?.end || 0));
  const i1 = N - 1 - end, i0 = Math.max(0, i1 - n + 1);
  const pw = W - AX - PADL, ph = H - TOP - BOT;
  const barsW = pw * (1 - FUT);
  const bw = barsW / n;
  const X = (i) => PADL + (i - i0 + 0.5) * bw;
  const T0 = bars[0][0];
  const xt = (t) => {                                   // unix time -> x (bars' grid; after the last bar: extrapolated)
    if (t >= bars[N - 1][0]) return X(N - 1 + (t - bars[N - 1][0]) / secs);
    if (t <= T0) return X((t - T0) / secs);
    let lo = 0, hi = N - 1;
    while (lo < hi) { const m = (lo + hi + 1) >> 1; if (bars[m][0] <= t) lo = m; else hi = m - 1; }
    return X(lo + Math.min(1, (t - bars[lo][0]) / secs));
  };
  // ---- price range: the visible bars + what must be seen (the open trade, the armed setup)
  let lo = Infinity, hi = -Infinity;
  for (let i = i0; i <= i1; i++) { lo = Math.min(lo, bars[i][3]); hi = Math.max(hi, bars[i][2]); }
  const rng0 = Math.max(4, hi - lo);
  const want = [];
  const S = d.strategies || {};
  const lit = S.lit || {}, at = S.atlas || {};
  if (o.on.lit) {
    for (const l of lit.lines || []) if (l.price != null) want.push(l.price);
    if (lit.setup) for (const k of ['ext', 'cisd', 'level']) if (lit.setup[k] != null) want.push(lit.setup[k]);
  }
  if (o.on.atlas) for (const l of at.lines || []) if (l.strong && l.price != null) want.push(l.price);
  for (const p of want) if (p > lo - 2.5 * rng0 && p < hi + 2.5 * rng0) { lo = Math.min(lo, p); hi = Math.max(hi, p); }
  const pad = (hi - lo) * 0.06 || 2;
  lo -= pad; hi += pad;
  const Y = (p) => TOP + (hi - p) / (hi - lo) * ph;
  const inY = (p) => p != null && p >= lo && p <= hi;
  const right = PADL + pw;
  // ---- outside the Zlarior entry window (02:00-15:30 ET): faint grey
  g.fillStyle = C.off;
  let runA = null;
  for (let i = i0; i <= i1 + 1; i++) {
    const outW = i <= i1 && (() => { const m = etMin(bars[i][0]); return m < 120 || m >= 930; })();
    if (outW && runA == null) runA = i;
    if ((!outW || i > i1) && runA != null) { g.fillRect(X(runA) - bw / 2, TOP, (i - runA) * bw, ph); runA = null; }
  }
  // ---- grid + axes
  const step = niceStep((hi - lo) / Math.max(3, Math.floor(ph / 48)));
  g.font = '11px ui-monospace, SFMono-Regular, Menlo, Consolas, monospace';
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
  // "now" divider (the future area holds the plans / position boxes)
  const xNow = X(i1) + bw / 2;
  g.save(); g.setLineDash([2, 4]); g.strokeStyle = '#cbd5e1'; g.beginPath(); g.moveTo(xNow, TOP); g.lineTo(xNow, TOP + ph); g.stroke(); g.restore();

  const tags = [];      // right-axis price tags {y, text, color}
  const notes = [];     // labels in the chart {x, y, text, color, align}
  const off = { up: [], dn: [] };
  const hline = (p, x0, x1, color, dash, w = 1) => {
    if (!inY(p)) return;
    const y = Math.round(Y(p)) + 0.5;
    g.save(); g.strokeStyle = color; g.lineWidth = w; if (dash) g.setLineDash(dash);
    g.beginPath(); g.moveTo(Math.max(PADL, x0), y); g.lineTo(Math.min(right, x1), y); g.stroke(); g.restore();
  };

  // ================================================================ ATLAS (under the candles): EMAs + S/R
  if (o.on.atlas) {
    const ema = (rows, color, dash, w) => {
      if (!rows?.length) return;
      g.save(); g.strokeStyle = color; g.lineWidth = w; if (dash) g.setLineDash(dash); g.beginPath();
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
    ema(at.ema21, C.atlas, null, 1.6);
    ema(at.ema50, C.atlas2, [6, 4], 1.6);
    if (at.ema21?.length) notes.push({ x: PADL + 8, y: TOP + 34, text: 'EMA 21 / 50 (5m)', color: C.atlas, align: 'left', size: 10 });
    for (const l of at.levels || []) {
      if (!inY(l.price)) continue;
      hline(l.price, PADL, right, 'rgba(234,88,12,0.55)', [8, 3, 2, 3]);
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
        const x1 = l.taken_t ? xt(l.taken_t) : right;
        hline(l.price, PADL, x1, C.litSoft, [5, 4]);
        notes.push({ x: Math.min(x1, right) + 4, y: Y(l.price) - 7, text: `✓ ${l.label} swept ${l.taken_hm || ''}`, color: C.litSoft, align: 'left', size: 10 });
      } else {
        hline(l.price, PADL, right, C.lit, null, 1);
        tags.push({ y: Y(l.price), text: fmt(l.price), color: C.lit, small: true });
        notes.push({ x: xNow - 6, y: Y(l.price) - 7, text: l.label, color: C.lit, align: 'right', size: 10.5 });
      }
    }
  }

  // ================================================================ candles
  const cw = Math.max(1, Math.min(14, bw * 0.68));
  for (let i = i0; i <= i1; i++) {
    const [, op, h, l, c] = bars[i], x = X(i), up = c >= op;
    g.strokeStyle = g.fillStyle = up ? C.up : C.dn;
    g.lineWidth = 1;
    g.beginPath(); g.moveTo(Math.round(x) + 0.5, Y(h)); g.lineTo(Math.round(x) + 0.5, Y(l)); g.stroke();
    const y0 = Y(Math.max(op, c)), y1 = Y(Math.min(op, c));
    g.fillRect(x - cw / 2, y0, cw, Math.max(1, y1 - y0));
  }

  // ================================================================ Zlarior setup mock-up, plan, position
  const box = (x0, x1, pEntry, pStop, pTgt, label) => {      // the position tool: red = risk, green = reward
    if (pEntry == null) return;
    x0 = Math.max(PADL, x0); x1 = Math.min(right, x1);
    if (x1 <= x0) return;
    if (pStop != null) { g.fillStyle = C.risk; g.fillRect(x0, Math.min(Y(pEntry), Y(pStop)), x1 - x0, Math.abs(Y(pStop) - Y(pEntry))); }
    if (pTgt != null) { g.fillStyle = C.reward; g.fillRect(x0, Math.min(Y(pEntry), Y(pTgt)), x1 - x0, Math.abs(Y(pTgt) - Y(pEntry))); }
    if (label) notes.push({ x: x0 + 6, y: Y(pEntry) + (pTgt != null && pTgt < pEntry ? -9 : 11), text: label, color: C.ink, align: 'left', size: 10.5, bold: true });
  };
  if (o.on.lit) {
    const s = lit.setup;
    if (s && s.ext != null && s.ext_t) {
      const x = xt(s.ext_t), y = Y(s.ext), d0 = s.dir || 1;
      if (inY(s.ext)) {
        g.fillStyle = C.lit; g.beginPath();
        if (d0 > 0) { g.moveTo(x, y + 4); g.lineTo(x - 6, y + 14); g.lineTo(x + 6, y + 14); } else { g.moveTo(x, y - 4); g.lineTo(x - 6, y - 14); g.lineTo(x + 6, y - 14); }
        g.fill();
        notes.push({ x, y: y + (d0 > 0 ? 24 : -22), text: `sweep extreme ${fmt(s.ext)}`, color: C.lit, align: 'center', size: 10.5, bold: true });
      }
      if (s.level != null) { hline(s.level, x - 12 * bw, x + 6 * bw, C.lit, null, 2.2); }
      if (s.cisd != null && !s.armed) {
        hline(s.cisd, x, right, C.lit, [2, 3], 1.6);
        if (inY(s.cisd)) notes.push({ x: xNow + 6, y: Y(s.cisd) - 8, text: `CISD ${d0 > 0 ? 'close above' : 'close below'} ${fmt(s.cisd)}${s.cisd_closed ? ' ✓' : ''}`, color: C.lit, align: 'left', size: 10.5, bold: true });
      }
      const st = { sweep: 'Sweep', inducement: 'Inducement', displacement: 'Waiting for displacement', cisd5: 'CISD' }[s.stage] || s.stage;
      if (inY(s.ext)) notes.push({ x, y: y + (d0 > 0 ? 37 : -35), text: `${s.side || ''} setup · ${st}`, color: C.lit, align: 'center', size: 10 });
    }
    const a = s?.armed;
    if (a && a.limit != null) {
      const x0 = a.armed_t ? xt(a.armed_t) : xNow, x1 = Math.max(xNow + 0.6 * (right - xNow), a.expires_t ? xt(a.expires_t) : xNow);
      box(x0, x1, a.limit, a.stop, a.target, `ARMED ${a.side || ''} limit ${fmt(a.limit)}`);
    }
    const pos = lit.position;
    if (pos && pos.entry != null) {
      const x0 = pos.entry_t ? xt(pos.entry_t) : xNow;
      box(x0, right, pos.entry, pos.stop, pos.target, null);
      if (pos.entry_t && inY(pos.entry)) {
        const d0 = pos.dir || (pos.side === 'LONG' ? 1 : -1), y = Y(pos.entry);
        g.fillStyle = C.lit; g.beginPath();
        if (d0 > 0) { g.moveTo(x0, y); g.lineTo(x0 - 7, y + 11); g.lineTo(x0 + 7, y + 11); } else { g.moveTo(x0, y); g.lineTo(x0 - 7, y - 11); g.lineTo(x0 + 7, y - 11); }
        g.fill();
      }
    }
    for (const l of lit.lines || []) {
      if (l.price == null) continue;
      const color = l.tone === 'good' ? C.good : l.tone === 'bad' ? C.bad : C.lit;
      const x0 = l.t0 ? xt(l.t0) : PADL;
      if (!inY(l.price)) { (l.price > hi ? off.up : off.dn).push({ label: l.label, price: l.price, color }); continue; }
      hline(l.price, x0, right, color, l.style === 'dash' ? [7, 4] : l.style === 'dot' ? [2, 3] : null, l.strong ? 2 : 1.4);
      tags.push({ y: Y(l.price), text: fmt(l.price), color, strong: l.strong });
      notes.push({ x: right - 4, y: Y(l.price) - 8, text: l.label, color, align: 'right', size: 11, bold: !!l.strong });
    }
    for (const m of lit.marks || []) {
      if (m.t < bars[i0][0] - secs || m.t > bars[i1][0] + secs || !inY(m.price)) continue;
      const x = xt(m.t), y = Y(m.price);
      if (m.kind === 'setup') {
        const col = { armed: C.lit, filled: C.good, no_fill: '#d97706', rejected: '#94a3b8', blocked: '#94a3b8' }[m.status] || '#94a3b8';
        g.fillStyle = '#fff'; g.strokeStyle = col; g.lineWidth = 2; g.beginPath(); g.arc(x, y, 4.5, 0, Math.PI * 2); g.fill(); g.stroke();
        if (m.status === 'rejected' || m.status === 'blocked') { g.beginPath(); g.moveTo(x - 3, y - 3); g.lineTo(x + 3, y + 3); g.moveTo(x + 3, y - 3); g.lineTo(x - 3, y + 3); g.stroke(); }
        if (n <= 400) notes.push({ x, y: y - 12, text: m.status === 'rejected' ? 'rejected' : m.status === 'filled' ? 'filled' : m.status === 'armed' ? 'armed' : m.status === 'no_fill' ? 'no fill' : 'skipped', color: col, align: 'center', size: 9.5 });
      } else {
        const ex = m.kind === 'exit';
        g.fillStyle = ex ? ((m.pnl || 0) >= 0 ? C.good : C.bad) : C.lit;
        g.beginPath(); g.rect(x - 4, y - 4, 8, 8); g.fill();
        notes.push({ x: x + 8, y: y + (ex ? 14 : -12), text: ex ? `EXIT ${m.text || ''} ${m.pnl != null ? (m.pnl >= 0 ? '+' : '-') + '$' + Math.abs(Math.round(m.pnl)).toLocaleString('en-US') : ''}` : `${m.side === 'buy' ? 'BUY' : 'SELL'} ${m.qty || ''} @ ${fmt(m.price)}${m.ok === false ? ' NOT placed' : ''}`, color: g.fillStyle, align: 'left', size: 10.5, bold: true });
      }
    }
  }
  if (o.on.atlas) {
    for (const l of at.lines || []) {
      if (!inY(l.price)) { if (l.strong) (l.price > hi ? off.up : off.dn).push({ label: l.label, price: l.price, color: C.atlas }); continue; }
      hline(l.price, l.t0 ? xt(l.t0) : PADL, right, C.atlas, l.style === 'dash' ? [7, 4] : l.style === 'dot' ? [2, 3] : null, l.strong ? 2 : 1.3);
      tags.push({ y: Y(l.price), text: fmt(l.price), color: C.atlas, strong: l.strong });
      notes.push({ x: right - 4, y: Y(l.price) + 10, text: l.label, color: C.atlas, align: 'right', size: 10.5, bold: !!l.strong });
    }
  }

  // ---- last price
  const last = bars[N - 1][4];
  if (inY(last)) { hline(last, PADL, right, '#0f172a', [1, 2]); tags.push({ y: Y(last), text: fmt(last), color: '#0f172a', strong: true, last: true }); }

  // ---- notes (de-overlapped per column), then the price tags
  g.textBaseline = 'middle';
  const placed = [];
  for (const nt of notes) {
    g.font = `${nt.bold ? '600 ' : ''}${nt.size || 11}px system-ui, -apple-system, Segoe UI, Roboto, sans-serif`;
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
    g.fillStyle = 'rgba(255,255,255,0.82)'; g.fillRect(x - 2, y - 7, w + 4, 14);
    g.fillStyle = nt.color; g.textAlign = 'left'; g.fillText(nt.text, x, y);
  }
  tags.sort((a, b) => a.y - b.y);
  for (let k = 1; k < tags.length; k++) if (tags[k].y - tags[k - 1].y < 15) tags[k].y = tags[k - 1].y + 15;
  g.font = '600 11px ui-monospace, SFMono-Regular, Menlo, Consolas, monospace';
  for (const t of tags) {
    if (t.y < TOP - 4 || t.y > TOP + ph + 4) continue;
    g.fillStyle = t.color; g.fillRect(right + 1, t.y - 8, AX - 3, 16);
    g.fillStyle = '#fff'; g.textAlign = 'left'; g.fillText(t.text, right + 6, t.y + 0.5);
  }
  // ---- levels / lines off the screen: small arrows at the top / bottom edge
  g.font = '10.5px system-ui, -apple-system, Segoe UI, Roboto, sans-serif';
  const edge = (list, top) => {
    list.sort((a, b) => top ? a.price - b.price : b.price - a.price);
    list.slice(0, 3).forEach((l, k) => {
      const y = top ? TOP + 10 + k * 13 : TOP + ph - 10 - k * 13;
      const t = `${top ? '▲' : '▼'} ${l.label} ${fmt(l.price)} (${fmt(Math.abs(l.price - last))} pts)`;
      const w = g.measureText(t).width;
      g.fillStyle = 'rgba(255,255,255,0.85)'; g.fillRect(right - w - 8, y - 6, w + 6, 12);
      g.fillStyle = l.color || C.lit; g.textAlign = 'right'; g.fillText(t, right - 4, y);
    });
  };
  if (o.on.lit || o.on.atlas) { edge(off.up, true); edge(off.dn, false); }

  // ---- crosshair
  let hoverBar = null, hoverPx = null;
  const hv = o.hover;
  if (hv && hv.x > PADL && hv.x < right && hv.y > TOP && hv.y < TOP + ph) {
    const i = Math.max(i0, Math.min(i1, Math.round((hv.x - PADL) / bw - 0.5 + i0)));
    hoverBar = bars[i];
    hoverPx = hi - (hv.y - TOP) / ph * (hi - lo);
    g.save(); g.strokeStyle = '#94a3b8'; g.setLineDash([3, 3]);
    g.beginPath(); g.moveTo(X(i), TOP); g.lineTo(X(i), TOP + ph); g.moveTo(PADL, hv.y); g.lineTo(right, hv.y); g.stroke(); g.restore();
    g.fillStyle = '#334155'; g.fillRect(right + 1, hv.y - 8, AX - 3, 16);
    g.fillStyle = '#fff'; g.font = '11px ui-monospace, monospace'; g.textAlign = 'left'; g.fillText(fmt(Math.round(hoverPx * 4) / 4), right + 6, hv.y + 0.5);
  }
  // frame
  g.strokeStyle = '#e2e8f0'; g.lineWidth = 1; g.strokeRect(PADL + 0.5, TOP + 0.5, pw - 1, ph - 1);
  return { bw, n, i0, i1, hoverBar, hoverPx };
}

function niceStep(raw) {
  const p = Math.pow(10, Math.floor(Math.log10(Math.max(raw, 1e-6))));
  const f = raw / p;
  return (f < 1.5 ? 1 : f < 3 ? 2 : f < 7 ? 5 : 10) * p;
}
