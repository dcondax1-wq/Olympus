import { css, toChart, etWall, prevCalDate, lowerBound, fmtN, etStr } from './util.js';

const alpha = (hex, a) => {
  hex = hex.replace('#', '');
  const n = parseInt(hex.length === 3 ? hex.split('').map(c => c + c).join('') : hex, 16);
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
};

export const LAYERS = [
  ['pools', 'Liquidity'], ['minor', 'Minor swings'], ['htf', 'HTF FVGs'], ['gamma', 'Gamma'], ['sessions', 'Sessions'], ['value', 'Value area'], ['fvg', 'FVGs'],
  ['ifvg', 'Triggers'], ['trades', 'Trades'], ['profile', 'Profile'],
];

export class TradeChart {
  constructor(el, { legend = null, minFvg = 3 } = {}) {
    this.el = el;
    this.legendEl = legend;
    this.minFvg = minFvg;
    this.layers = Object.fromEntries(LAYERS.map(([k]) => [k, k !== 'minor']));
    this.ann = { pools: [], ifvgs: [], trades: [], profiles: {}, days: [] };
    this.bars = []; this.ct = []; this.fvgs = [];
    this.cursorT = Infinity;
    this.tfSecs = 300;
    this.chart = LightweightCharts.createChart(el, {
      autoSize: true,
      crosshair: { mode: 0 },
      timeScale: { timeVisible: true, secondsVisible: false, rightOffset: 8, barSpacing: 7 },
      rightPriceScale: { scaleMargins: { top: 0.08, bottom: 0.12 } },
      handleScale: { axisPressedMouseMove: { time: true, price: true } },
    });
    this.candles = this.chart.addCandlestickSeries({ priceLineVisible: true, lastValueVisible: true });
    this.vol = this.chart.addHistogramSeries({ priceFormat: { type: 'volume' }, priceScaleId: 'vol', lastValueVisible: false, priceLineVisible: false });
    this.chart.priceScale('vol').applyOptions({ scaleMargins: { top: 0.86, bottom: 0 } });
    this.cv = document.createElement('canvas');
    Object.assign(this.cv.style, { position: 'absolute', left: 0, top: 0, pointerEvents: 'none', zIndex: 3 });
    el.appendChild(this.cv);
    this.applyTheme();
    this._sig = '';
    this._dirty = true;
    const loop = () => { this._frame(); this._raf = requestAnimationFrame(loop); };
    this._raf = requestAnimationFrame(loop);
    this.chart.subscribeCrosshairMove((p) => this._legend(p));
  }

  applyTheme() {
    this.col = {
      ink: css('--ink'), ink2: css('--ink-2'), muted: css('--muted'), grid: css('--grid'), axis: css('--axis'),
      surface: css('--surface'), ssl: css('--ssl'), bsl: css('--bsl'), amt: css('--amt'), fvg: css('--fvg'),
      gold: css('--gold'), good: css('--good'), bad: css('--bad'), accent: css('--accent'),
    };
    const c = this.col;
    this.chart.applyOptions({
      layout: { background: { type: 'solid', color: c.surface }, textColor: c.ink2, fontFamily: 'JetBrains Mono, monospace', fontSize: 11 },
      grid: { vertLines: { color: c.grid }, horzLines: { color: c.grid } },
      rightPriceScale: { borderColor: c.axis }, timeScale: { borderColor: c.axis },
      crosshair: { vertLine: { color: c.muted, labelBackgroundColor: c.accent }, horzLine: { color: c.muted, labelBackgroundColor: c.accent } },
    });
    const up = css('--candle-up') || c.good, dn = css('--candle-down') || c.bad;
    const hollow = document.documentElement.dataset.hollow === 'on';
    this.candles.applyOptions({ upColor: hollow ? 'rgba(0,0,0,0)' : up, downColor: dn, borderVisible: hollow,
      borderUpColor: up, borderDownColor: dn, wickUpColor: up, wickDownColor: dn });
    this.setBars(this.bars, this.tfSecs, true);
    this._dirty = true;
  }

  setBars(bars, tfSecs = 300, keepView = false) {
    this.bars = bars || [];
    this.tfSecs = tfSecs;
    this.ct = this.bars.map(b => toChart(b.t));
    this.candles.setData(this.bars.map((b, i) => ({ time: this.ct[i], open: b.o, high: b.h, low: b.l, close: b.c })));
    const g = alpha(this.col?.good || '#0ca30c', .35), r = alpha(this.col?.bad || '#d03b3b', .35);
    this.vol.setData(this.bars.map((b, i) => ({ time: this.ct[i], value: b.v, color: b.c >= b.o ? g : r })));
    this._computeFvgs();
    this._markers();
    this._dirty = true;
  }

  appendBar(b) {
    this.bars.push(b);
    const t = toChart(b.t);
    this.ct.push(t);
    this.candles.update({ time: t, open: b.o, high: b.h, low: b.l, close: b.c });
    const g = alpha(this.col.good, .35), r = alpha(this.col.bad, .35);
    this.vol.update({ time: t, value: b.v, color: b.c >= b.o ? g : r });
    this._computeFvgs(Math.max(0, this.bars.length - 3));
    this._dirty = true;
  }

  setAnnotations(a) { this.ann = { ...this.ann, ...a }; this._markers(); this._dirty = true; }
  setLayer(k, on) { this.layers[k] = on; this._markers(); this._dirty = true; }
  setCursor(t) { this.cursorT = t; this._markers(); this._dirty = true; }

  focusRange(t0, t1, padBars = 20) {
    if (!this.ct.length) return;
    const a = lowerBound(this.ct, toChart(t0)), b = lowerBound(this.ct, toChart(t1));
    this.chart.timeScale().setVisibleLogicalRange({ from: Math.max(0, a - padBars), to: Math.min(this.ct.length + 10, b + padBars) });
  }
  fit() { this.chart.timeScale().fitContent(); }
  scrollToEnd(bars = 160) {
    const n = this.ct.length;
    this.chart.timeScale().setVisibleLogicalRange({ from: n - bars, to: n + 10 });
  }

  // ------------------------------------------------------------ FVG detection on the displayed timeframe
  _computeFvgs(from = 0) {
    const B = this.bars;
    if (from === 0) this.fvgs = [];
    const minSz = this.minFvg * (this.tfSecs >= 3600 ? 3 : this.tfSecs >= 900 ? 1.6 : this.tfSecs <= 60 ? 0.6 : 1);
    const have = new Set(from ? this.fvgs.slice(-20).map(f => f.i) : []);
    for (let i = Math.max(2, from); i < B.length; i++) {
      if (have.has(i)) continue;
      if (B[i].l - B[i - 2].h >= minSz) this.fvgs.push({ i, i0: i - 2, top: B[i].l, bot: B[i - 2].h, dir: 1, end: null, inv: null });
      else if (B[i - 2].l - B[i].h >= minSz) this.fvgs.push({ i, i0: i - 2, top: B[i - 2].l, bot: B[i].h, dir: -1, end: null, inv: null });
    }
    // lifecycle: a gap is inverted when a candle body closes through its far side
    for (const f of this.fvgs) {
      if (f.end != null) continue;
      for (let k = f.i + 1; k < B.length; k++) {
        if ((f.dir === 1 && B[k].c < f.bot) || (f.dir === -1 && B[k].c > f.top)) { f.end = k; f.inv = k; break; }
        if (k - f.i > 60) { f.end = k; break; }
      }
    }
  }

  // ------------------------------------------------------------ markers (entries / exits / sweeps)
  _markers() {
    if (!this.ct.length) { this.candles.setMarkers([]); return; }
    const m = [];
    const snap = (t) => { const k = Math.min(this.ct.length - 1, Math.max(0, lowerBound(this.ct, toChart(t)) - (this.ct.includes(toChart(t)) ? 0 : 1))); return this.ct[k]; };
    const first = this.bars[0]?.t ?? 0, last = this.bars[this.bars.length - 1]?.t ?? 0;
    const inView = (t) => t >= first && t <= last + this.tfSecs && t <= this.cursorT;
    if (this.layers.trades) {
      for (const tr of this.ann.trades || []) {
        if (!inView(tr.entry_t)) continue;
        const L = tr.dir === 1;
        m.push({ time: snap(tr.entry_t), position: L ? 'belowBar' : 'aboveBar', color: L ? this.col.good : this.col.bad, shape: L ? 'arrowUp' : 'arrowDown', text: `${L ? 'L' : 'S'} ${tr.trigger}` });
        if (inView(tr.exit_t)) {
          m.push({ time: snap(tr.exit_t), position: L ? 'aboveBar' : 'belowBar', color: tr.pnl > 0 ? this.col.good : this.col.bad, shape: 'circle', text: `${tr.pnl_r > 0 ? '+' : ''}${tr.pnl_r.toFixed(1)}R` });
        }
        // in-trade warning signs the bot logged (first firing of each exit signal); the one it acted on is marked ✕
        for (const [name, x] of Object.entries(tr.xsig || {})) {
          const t = tr.entry_t + (x.k || 0) * this.tfSecs;
          if (!inView(t) || t > tr.exit_t) continue;
          const acted = tr.exit_signal === name;
          m.push({ time: snap(t), position: L ? 'aboveBar' : 'belowBar', color: acted ? this.col.bad : this.col.gold, shape: acted ? 'square' : 'circle', size: 0.6, text: (acted ? '✕ ' : '⚠ ') + name });
        }
      }
    }
    if (this.layers.pools) {
      for (const ev of this.ann.sweeps || []) {
        if (!inView(ev.t)) continue;
        m.push({ time: snap(ev.t), position: ev.dir === 1 ? 'belowBar' : 'aboveBar', color: this.col.gold, shape: 'square', text: 'sweep' });
      }
    }
    m.sort((a, b) => a.time - b.time);
    this.candles.setMarkers(m);
  }

  // ------------------------------------------------------------ coordinate helpers
  _xc(ctime) {
    const ts = this.chart.timeScale();
    const n = this.ct.length;
    if (!n) return null;
    let k = lowerBound(this.ct, ctime);
    let logical;
    if (k >= n) logical = n - 1 + (ctime - this.ct[n - 1]) / this.tfSecs;
    else if (k === 0) logical = (ctime - this.ct[0]) / this.tfSecs;
    else if (this.ct[k] === ctime) logical = k;
    else logical = k - 1 + Math.min(1, (ctime - this.ct[k - 1]) / this.tfSecs);
    return ts.logicalToCoordinate(logical);
  }
  _x(ts) { return this._xc(toChart(ts)); }
  _y(p) { return this.candles.priceToCoordinate(p); }

  _frame() {
    const w = this.el.clientWidth, h = this.el.clientHeight;
    if (!w || !h) return;
    const vr = this.chart.timeScale().getVisibleLogicalRange();
    const ref = this.bars.length ? this.bars[this.bars.length - 1].c : 0;
    const sig = `${w}x${h}|${vr ? vr.from.toFixed(2) + ':' + vr.to.toFixed(2) : ''}|${this._y(ref)}|${this._y(ref * 1.001)}`;
    if (sig === this._sig && !this._dirty) return;
    this._sig = sig; this._dirty = false;
    this._draw(w, h, vr);
  }

  _draw(w, h, vr) {
    const dpr = window.devicePixelRatio || 1;
    const cv = this.cv;
    if (cv.width !== Math.round(w * dpr) || cv.height !== Math.round(h * dpr)) {
      cv.width = Math.round(w * dpr); cv.height = Math.round(h * dpr);
      cv.style.width = w + 'px'; cv.style.height = h + 'px';
    }
    const g = cv.getContext('2d');
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    g.clearRect(0, 0, w, h);
    if (!this.bars.length || !vr) return;
    const psW = this.chart.priceScale('right').width();
    const tsH = this.chart.timeScale().height();
    const W = w - psW, H = h - tsH;
    g.save();
    g.beginPath(); g.rect(0, 0, W, H); g.clip();
    const c = this.col;
    const n = this.bars.length;
    const i0 = Math.max(0, Math.floor(vr.from) - 2), i1 = Math.min(n - 1, Math.ceil(vr.to) + 2);
    const tA = this.bars[i0].t, tB = this.bars[i1].t + this.tfSecs;
    const cur = Math.min(this.cursorT, this.bars[n - 1].t + this.tfSecs);
    const xEnd = this._x(cur) ?? W;
    g.font = '600 10px JetBrains Mono, monospace';
    g.textBaseline = 'middle';

    // ---- session bands + killzones
    const days = [...new Set(this.bars.slice(i0, i1 + 1).map(b => b.d))].filter(Boolean);
    if (this.layers.sessions) {
      for (const D of days) {
        const pd = prevCalDate(D);
        const bands = [
          [etWall(pd, 1200), etWall(D, 0), alpha(c.amt, .05), 'ASIA'],
          [etWall(D, 120), etWall(D, 300), alpha(c.ssl, .05), 'LONDON'],
          [etWall(D, 570), etWall(D, 690), alpha(c.gold, .07), 'NY AM KZ'],
          [etWall(D, 810), etWall(D, 930), alpha(c.gold, .05), 'NY PM KZ'],
        ];
        for (const [a, b, col, lab] of bands) {
          const xa = this._xc(a), xb = this._xc(b);
          if (xa == null || xb == null || xb < 0 || xa > W) continue;
          g.fillStyle = col; g.fillRect(xa, 0, xb - xa, H);
          g.fillStyle = c.muted; g.globalAlpha = .7; g.fillText(lab, xa + 4, 10); g.globalAlpha = 1;
        }
        // RTH open line
        const xo = this._xc(etWall(D, 570));
        if (xo != null && xo > 0 && xo < W) { g.strokeStyle = alpha(c.gold, .5); g.setLineDash([2, 3]); g.beginPath(); g.moveTo(xo, 0); g.lineTo(xo, H); g.stroke(); g.setLineDash([]); }
      }
    }

    // ---- value area (prior RTH profile projected onto the day)
    if (this.layers.value) {
      for (const D of days) {
        const pf = this.ann.profiles?.[D];
        if (!pf) continue;
        const xa = Math.max(0, this._xc(etWall(prevCalDate(D), 1080)) ?? 0);
        let xb = this._xc(etWall(D, 1020)); if (xb == null) continue; xb = Math.min(xb, xEnd);
        if (xb < 0 || xa > W) continue;
        const yh = this._y(pf.vah), yl = this._y(pf.val), yp = this._y(pf.poc);
        if (yh == null || yl == null) continue;
        g.fillStyle = alpha(c.amt, .07); g.fillRect(xa, yh, xb - xa, yl - yh);
        g.strokeStyle = alpha(c.amt, .55); g.lineWidth = 1; g.setLineDash([5, 4]);
        for (const y of [yh, yl]) { g.beginPath(); g.moveTo(xa, y); g.lineTo(xb, y); g.stroke(); }
        g.setLineDash([]); g.strokeStyle = alpha(c.amt, .9); g.lineWidth = 1.5;
        g.beginPath(); g.moveTo(xa, yp); g.lineTo(xb, yp); g.stroke();
        g.fillStyle = c.amt;
        g.fillText('pVAH', xa + 4, yh - 7); g.fillText('pPOC', xa + 4, yp - 7); g.fillText('pVAL', xa + 4, yl + 8);
      }
    }

    // ---- higher-timeframe FVGs / inversions (1D / 4H / 1H PD arrays)
    if (this.layers.htf) {
      g.font = '700 10px JetBrains Mono, monospace';
      for (const z of this.ann.htf_fvgs || []) {
        if (z.t0 > tB || z.t0 > this.cursorT) continue;
        const end = z.t1 != null && z.t1 <= this.cursorT ? z.t1 : null;
        if (end != null && end < tA) continue;
        const xa = Math.max(-5, this._x(z.t0) ?? -5), xb = end != null ? this._x(end) : xEnd;
        const yt = this._y(z.top), yb = this._y(z.bot);
        if (xb == null || yt == null || yb == null) continue;
        const inv = z.inv_t != null && z.inv_t <= this.cursorT;
        const col = (z.dir === 1) !== inv ? c.good : c.bad;   // inverted gaps flip role
        const w = z.tf === '1D' ? 2 : z.tf === '4H' ? 1.6 : 1.2;
        g.fillStyle = alpha(col, z.tf === '1H' ? .06 : .09);
        g.fillRect(xa, yt, xb - xa, yb - yt);
        g.strokeStyle = alpha(col, .75); g.lineWidth = w; g.setLineDash(inv ? [5, 4] : []);
        g.strokeRect(xa, yt, xb - xa, yb - yt); g.setLineDash([]);
        const lab = `${z.tf} ${inv ? 'IFVG' : 'FVG'}`;
        const lx = Math.max(4, Math.min(xb - 60, W - 70));
        g.fillStyle = col; g.fillText(lab, lx, yt + 8);
      }
      g.font = '600 10px JetBrains Mono, monospace';
    }

    // ---- FVGs (auto, displayed timeframe)
    if (this.layers.fvg) {
      for (const f of this.fvgs) {
        if (f.i > i1 || (f.end != null && f.end < i0)) continue;
        if (this.bars[f.i].t > this.cursorT) continue;
        const xa = this._xc(this.ct[f.i0]);
        let endIdx = f.end ?? Math.min(n - 1, f.i + 60);
        let xb = this._xc(this.ct[Math.min(endIdx, n - 1)]);
        if (this.bars[Math.min(endIdx, n - 1)].t > this.cursorT) xb = xEnd;
        const yt = this._y(f.top), yb = this._y(f.bot);
        if (xa == null || xb == null || yt == null || yb == null) continue;
        const col = f.dir === 1 ? c.good : c.bad;
        g.fillStyle = alpha(col, .10); g.fillRect(xa, yt, Math.max(2, xb - xa), yb - yt);
        g.strokeStyle = alpha(col, .35); g.lineWidth = 1; g.strokeRect(xa, yt, Math.max(2, xb - xa), yb - yt);
        if (f.inv != null && this.bars[f.inv].t <= this.cursorT) {
          const xi = this._xc(this.ct[f.inv]);
          g.fillStyle = alpha(col === c.good ? c.bad : c.good, .9);
          g.fillText('i', xi + 3, (yt + yb) / 2);
        }
      }
    }

    // ---- liquidity pools
    if (this.layers.pools) {
      const labels = [];
      for (const p of this.ann.pools || []) {
        if (p.t0 > tB || p.t0 > this.cursorT) continue;
        if (p.kind.startsWith('IT') && !p.eq && !this.layers.minor) continue;
        const taken = p.t1 != null && p.t1 <= this.cursorT;
        if (taken && p.t1 < tA) continue;
        const retired = !taken && p.t2 != null && p.t2 <= this.cursorT;
        if (retired && p.t2 < tA) continue;
        const xa = Math.max(-5, this._x(p.t0) ?? -5);
        const xb = taken ? this._x(p.t1) : retired ? this._x(p.t2) : xEnd;
        const y = this._y(p.price);
        if (y == null || xb == null || xb < 0) continue;
        const col = p.side === 'H' ? c.bsl : c.ssl;
        const strong = p.strength >= 2 || p.eq;
        g.strokeStyle = alpha(col, taken ? .45 : (strong ? .95 : .6));
        g.lineWidth = p.eq ? 2 : strong ? 1.5 : 1;
        g.setLineDash(taken ? [3, 3] : p.kind.startsWith('IT') ? [6, 3] : []);
        g.beginPath(); g.moveTo(xa, y); g.lineTo(xb, y); g.stroke(); g.setLineDash([]);
        if (taken) {  // sweep x
          g.strokeStyle = c.gold; g.lineWidth = 2;
          g.beginPath(); g.moveTo(xb - 4, y - 4); g.lineTo(xb + 4, y + 4); g.moveTo(xb + 4, y - 4); g.lineTo(xb - 4, y + 4); g.stroke();
        }
        if (!p.kind.startsWith('IT') || p.eq) labels.push({ x: taken ? xb : Math.min(xb, W) , y, text: `${p.label.replace('·', ' ')} ${fmtN(p.price, 2)}`, col, taken });
      }
      // de-collide labels
      labels.sort((a, b) => a.y - b.y);
      let lastY = -99;
      for (const L of labels) {
        if (Math.abs(L.y - lastY) < 11) continue;
        lastY = L.y;
        const tw = g.measureText(L.text).width;
        const x = L.taken ? L.x + 7 : Math.max(4, L.x - tw - 8);
        g.fillStyle = alpha(c.surface, .8); g.fillRect(x - 3, L.y - 7, tw + 6, 13);
        g.fillStyle = L.col; g.globalAlpha = L.taken ? .6 : 1; g.fillText(L.text, x, L.y); g.globalAlpha = 1;
      }
    }

    // ---- live dealer gamma levels (QQQ -> NQ) across the latest session
    const gm = this.ann.gamma;
    if (this.layers.gamma && gm && !gm.error && this.cursorT === Infinity) {
      const lastDay = this.bars[n - 1].d;
      const k0 = this.bars.findIndex(b => b.d === lastDay);
      const xa = Math.max(0, this._x(this.bars[Math.max(0, k0)].t) ?? 0);
      g.font = '700 10px JetBrains Mono, monospace';
      for (const [lab, lv, col] of [['CALL WALL', gm.call_wall, c.bad], ['Γ FLIP', gm.flip, c.amt], ['PUT WALL', gm.put_wall, c.good]]) {
        if (!lv || lv.nq == null) continue;
        const y = this._y(lv.nq);
        if (y == null || y < 0 || y > H) continue;
        g.strokeStyle = col; g.lineWidth = 1.6; g.setLineDash([8, 4]);
        g.beginPath(); g.moveTo(xa, y); g.lineTo(W, y); g.stroke(); g.setLineDash([]);
        const txt = `${lab} ${fmtN(lv.nq, 0)}`;
        const tw = g.measureText(txt).width;
        g.fillStyle = alpha(c.surface, .85); g.fillRect(xa + 4, y - 15, tw + 8, 13);
        g.fillStyle = col; g.fillText(txt, xa + 8, y - 8);
      }
      g.font = '600 10px JetBrains Mono, monospace';
    }

    // ---- engine trigger IFVG / CISD zones
    if (this.layers.ifvg) {
      for (const z of this.ann.ifvgs || []) {
        if (z.t1 > this.cursorT || z.t1 < tA - 7200 || z.t0 > tB) continue;
        const xa = this._x(z.t0), xb = this._x(z.t1 + this.tfSecs * 3);
        const yt = this._y(z.top), yb = this._y(z.bottom);
        if (xa == null || xb == null || yt == null || yb == null) continue;
        const col = z.dir === 1 ? c.good : c.bad;
        g.fillStyle = alpha(col, .22); g.fillRect(xa, Math.min(yt, yb), xb - xa, Math.abs(yb - yt));
        g.strokeStyle = col; g.lineWidth = 1.5; g.strokeRect(xa, Math.min(yt, yb), xb - xa, Math.abs(yb - yt));
        g.fillStyle = col; g.font = '700 10px JetBrains Mono, monospace';
        g.fillText(`${z.type} ✓`, xa + 3, Math.min(yt, yb) - 7);
        g.font = '600 10px JetBrains Mono, monospace';
      }
    }

    // ---- trades (position tool)
    if (this.layers.trades) {
      for (const tr of this.ann.trades || []) {
        if (tr.entry_t > this.cursorT || tr.entry_t > tB || tr.exit_t < tA) continue;
        const open = tr.exit_t > this.cursorT;
        const xa = this._x(tr.entry_t);
        const xb = open ? xEnd : this._x(tr.exit_t + this.tfSecs);
        const ye = this._y(tr.entry), yt = this._y(tr.target), ys = this._y(tr.stop0 ?? tr.stop);
        if (xa == null || xb == null || ye == null || yt == null || ys == null) continue;
        const wdt = Math.max(6, xb - xa);
        g.fillStyle = alpha(c.good, .16); g.fillRect(xa, Math.min(ye, yt), wdt, Math.abs(yt - ye));
        g.fillStyle = alpha(c.bad, .16); g.fillRect(xa, Math.min(ye, ys), wdt, Math.abs(ys - ye));
        g.strokeStyle = c.ink2; g.lineWidth = 1.2; g.beginPath(); g.moveTo(xa, ye); g.lineTo(xa + wdt, ye); g.stroke();
        g.strokeStyle = alpha(c.good, .9); g.beginPath(); g.moveTo(xa, yt); g.lineTo(xa + wdt, yt); g.stroke();
        g.strokeStyle = alpha(c.bad, .9); g.beginPath(); g.moveTo(xa, ys); g.lineTo(xa + wdt, ys); g.stroke();
        let txt;
        if (open) {
          const last = this.bars[n - 1].c;
          const r = (last - tr.entry) * tr.dir / tr.risk_pts;
          txt = `${tr.dir === 1 ? 'LONG' : 'SHORT'} ${tr.qty_label} · open ${r >= 0 ? '+' : ''}${r.toFixed(2)}R`;
        } else txt = `${tr.dir === 1 ? 'LONG' : 'SHORT'} ${tr.qty_label} · ${tr.exit_reason} ${tr.pnl_r > 0 ? '+' : ''}${tr.pnl_r.toFixed(2)}R  ${tr.pnl >= 0 ? '+' : '-'}$${Math.abs(tr.pnl).toFixed(0)}`;
        const ty = Math.min(yt, ys, ye) - 9;
        const tw = g.measureText(txt).width;
        g.fillStyle = open ? c.accent : (tr.pnl > 0 ? c.good : c.bad);
        g.fillRect(xa, ty - 7, tw + 10, 14);
        g.fillStyle = '#fff'; g.fillText(txt, xa + 5, ty);
        g.fillStyle = c.muted;
        g.fillText(`TP ${tr.target_label}`, xa + wdt + 4, yt);
      }
    }
    g.restore();

    // ---- volume profile on the right edge for the last visible day
    if (this.layers.profile) {
      const D = this.bars[i1].d;
      const pf = this.ann.profiles?.[D];
      if (pf && pf.hist?.length) {
        const maxV = Math.max(...pf.hist);
        const pw = Math.min(130, W * 0.18);
        g.save(); g.beginPath(); g.rect(0, 0, W, H); g.clip();
        for (let k = 0; k < pf.hist.length; k++) {
          const p0 = pf.lo + k * pf.bin, p1 = p0 + pf.bin;
          const y0 = this._y(p1), y1 = this._y(p0);
          if (y0 == null || y1 == null) continue;
          const len = pf.hist[k] / maxV * pw;
          const inVA = p0 >= pf.val - 1e-9 && p1 <= pf.vah + 1e-9;
          const isPoc = pf.poc >= p0 && pf.poc < p1;
          g.fillStyle = isPoc ? alpha(c.gold, .75) : inVA ? alpha(c.amt, .38) : alpha(c.muted, .25);
          g.fillRect(W - len, y0 + 0.5, len, Math.max(1, y1 - y0 - 1));
        }
        g.fillStyle = c.muted; g.fillText(`prior RTH profile (${pf.date})`, W - pw, 22);
        g.restore();
      }
    }
  }

  _legend(p) {
    if (!this.legendEl) return;
    const d = p?.seriesData?.get(this.candles);
    if (!d) { this.legendEl.innerHTML = this._legendBase || ''; return; }
    const ch = d.close - d.open;
    this.legendEl.innerHTML = `${this._legendBase || ''} &nbsp; O <b>${fmtN(d.open)}</b> H <b>${fmtN(d.high)}</b> L <b>${fmtN(d.low)}</b> C <b class="${ch >= 0 ? 'up' : 'dn'}">${fmtN(d.close)}</b>`;
  }
  setLegendBase(html) { this._legendBase = html; if (this.legendEl) this.legendEl.innerHTML = html; }
}
