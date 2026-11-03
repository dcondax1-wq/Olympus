// ORACLE demo: a real session replayed when there is no live data (demo_day.json, 2026-01-22: the London sweeps of the Asia
// high and the PDH, then the NY short at 09:24 that banked +6.4R). Built from the stored bars by engine/brain.replay
// (python -X utf8 -m tests.test_oracle_page --regen). docAt(t) gives a live.json-shaped doc at any second of the day, so the
// demo goes through the same normalize() as the real feed.
import { etParts, etToUnix, hm } from './time.js';

const ATLAS_HOURS = { ema_lon_vix: ['EMA', [[180, 570]]], macd_sweep: ['MACD', [[120, 300], [570, 660]]], sr_nyreclaim: ['S/R', [[570, 720]]] };

export async function loadDemo(url = 'demo_day.json') {
  const r = await fetch(url, { cache: 'no-cache' });
  if (!r.ok) throw new Error('demo ' + r.status);
  const fx = await r.json();
  if (!fx || fx.kind !== 'oracle-demo' || !Array.isArray(fx.bars) || !fx.bars.length) throw new Error('not a demo day');
  return fx;
}

/** Price inside a 5m bar: open -> the far wick -> the other wick -> close (the path a candle most likely took). */
function priceAt(fx, t) {
  const B = fx.bars;
  let lo = 0, hi = B.length - 1;
  if (t <= B[0][0]) return B[0][1];
  if (t >= B[hi][0] + 300) return B[hi][4];
  while (lo < hi) { const m = (lo + hi + 1) >> 1; if (B[m][0] <= t) lo = m; else hi = m - 1; }
  const [t0, o, h, l, c] = B[lo], f = Math.min(1, (t - t0) / 300);
  const path = c >= o ? [o, l, h, c] : [o, h, l, c];
  const k = Math.min(2, Math.floor(f * 3)), u = f * 3 - k;
  return path[k] + (path[k + 1] - path[k]) * u;
}

/** The replay span: 00:30 ET (Asia's end) to 11:00 ET (after the trade), and the slow parts (the sweeps and the entry). */
export function span(fx) {
  const p = etParts(fx.bars[fx.bars.length - 1][0]);
  const at = (h, m) => etToUnix(p.y, p.mo, p.d, h, m);
  return { from: at(0, 30), to: at(11, 0), slow: [[at(2, 50), at(4, 0)], [at(8, 40), at(9, 55)]] };
}

export function docAt(fx, t) {
  const price = Math.round(priceAt(fx, t) * 4) / 4;
  let fr = fx.frames[0];
  for (const f of fx.frames) if (f.t <= t) fr = f;
  const tr = fr.trade && fr.trade.entry_t <= t && t < fx.trade.exit_t ? fr.trade : null;
  const mod = etParts(t).mod;
  return {
    kind: 'le-live', demo: true, t, price,
    pc: {
      brain: {
        price, atr: fr.atr, stage: fr.stage, stages: fr.stages, day_pnl: fr.day_pnl,
        levels: fx.levels.filter((l) => l.from_t <= t).map((l) => ({ label: l.label, price: l.price, kind: l.kind,
          taken: l.taken_t != null && l.taken_t <= t, taken_hm: l.taken_t != null && l.taken_t <= t ? hm(l.taken_t - 300) : null })),
        guards: { vix: fx.vix },
        trade: tr ? { ...tr, price } : null,
      },
      mind: { regime: fx.regime },
    },
    board: {
      lit: { today_pnl: fr.day_pnl || 0 },
      atlas: { members: Object.entries(ATLAS_HOURS).map(([key, [short, wins]]) => {
        const on = wins.some(([a, b]) => mod >= a && mod < b);
        return { key, short, stage: on ? 'waiting' : 'off', window: { open: on } };
      }) },
    },
    bars: fx.bars.filter((b) => b[0] + 300 <= t).map((b) => [b[0] + 300, b[4]]),
  };
}
