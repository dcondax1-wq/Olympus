// Where everything stands in the Data City (pure: no three.js, no DOM).
//   layout(city)   -> { items, centers }: one item per building / strategy tower / monument, with x, z, height, width,
//                     colour, lit-window share (sample size) and pulse (rising)
//   streets(c)     -> road segments [x0, z0, x1, z1]: plaza -> every district, a ring road, and each district's cross
//   flyPath(c)     -> the fly-through: [camera point, look-at point] pairs round every district
import { COLORS, clsRank } from './util.js';

const LOT = 2.5;                   // one building lot (world units)
const BLOCK = 5;                   // lots between two streets
const STREET = 0.55;               // extra width of a street, in lots
export const CENTERS = { times: [-52, -46], confluences: [46, -40], while: [0, 66], strategies: [-50, 18] };
const MONUMENT_RING = 15;

/** Height of a combination's building from its $ per trade per micro (losers are short stubs). */
export function heightOf(e) {
  return e > 0 ? 0.7 + Math.pow(e, 0.85) * 0.22 : 0.45 + Math.max(-0.25, e * 0.004);
}

/** Lit windows: the share of a building's windows that are on, from its number of trades (1,000+ = all). */
export function litShare(n) {
  return Math.min(1, Math.log10(Math.max(1, n || 1)) / 3);
}

/** Grid lots round a centre, nearest first, with a street every BLOCK lots; list[i] gets the i-th nearest lot. */
function districtGrid(list, [cx, cz], kind, aspect = 1, spread = 1) {
  if (!list.length) return [];
  const cols = Math.max(1, Math.ceil(Math.sqrt(list.length * aspect)));
  const rows = Math.ceil(list.length / cols);
  const off = (i, n) => i + Math.floor(i / BLOCK) * STREET - (n - 1 + Math.floor((n - 1) / BLOCK) * STREET) / 2;
  const cells = [];
  for (let r = 0; r < rows; r++) for (let c = 0; c < cols; c++) cells.push([cx + off(c, cols) * LOT * spread, cz + off(r, rows) * LOT * spread]);
  cells.sort((a, b) => Math.hypot(a[0] - cx, a[1] - cz) - Math.hypot(b[0] - cx, b[1] - cz));
  return list.map((b, i) => ({ kind, b, x: cells[i][0], z: cells[i][1] }));
}

function dress(it) {
  const b = it.b;
  if (it.kind === 'b') {
    return { ...it, h: heightOf(b.e || 0), w: 1.55, color: COLORS[b.cls] ?? COLORS.grey, lit: litShare(b.n), pulse: b.tr === 'rising' ? 1 : 0 };
  }
  if (it.kind === 's') {
    const perMonth = Math.max(0, b.spans?.['2026']?.per_month || 0);
    return { ...it, h: 3 + Math.sqrt(perMonth) * 0.32, w: 2.6, color: COLORS.strat, lit: 0.8, pulse: 0 };
  }
  return { ...it, h: 7 + Math.max(0, b.e || 0) * 0.12, w: 1.9, color: b.cls === 'gold' ? COLORS.gold : COLORS.monument, lit: 0.95,
           pulse: b.tr === 'rising' ? 1 : 0 };
}

export function layout(city) {
  const by = { times: [], confluences: [], while: [] };
  for (const b of city.buildings || []) if (by[b.d]) by[b.d].push(b);
  for (const k of Object.keys(by)) by[k].sort((a, b) => clsRank(a.cls) - clsRank(b.cls) || (b.e || 0) - (a.e || 0));
  const items = [
    ...districtGrid(by.times, CENTERS.times, 'b'),
    ...districtGrid(by.confluences, CENTERS.confluences, 'b'),
    ...districtGrid(by.while, CENTERS.while, 'b', 1.4),
    ...districtGrid(city.strategies || [], CENTERS.strategies, 's', 1, 1.9),
  ];
  const byId = new Map((city.buildings || []).map((b) => [b.id, b]));
  const monuments = (city.discoveries || []).filter((x) => x.id).map((x) => ({ ...(byId.get(x.id) || {}), ...x }));
  monuments.forEach((b, i) => {
    const a = (i / monuments.length) * Math.PI * 2 + 0.3;
    items.push({ kind: 'd', b, x: Math.cos(a) * MONUMENT_RING, z: Math.sin(a) * MONUMENT_RING });
  });
  return { items: items.map(dress), centers: CENTERS };
}

export function streets(c = CENTERS, ring = 22, half = 30) {
  const segs = Object.values(c).map(([x, z]) => [0, 0, x, z]);
  for (let i = 0; i < 24; i++) {
    const a = (i / 24) * Math.PI * 2, b = ((i + 1) / 24) * Math.PI * 2;
    segs.push([Math.cos(a) * ring, Math.sin(a) * ring, Math.cos(b) * ring, Math.sin(b) * ring]);
  }
  for (const k of ['times', 'confluences', 'while']) {
    const [x, z] = c[k];
    segs.push([x - half, z, x + half, z], [x, z - half, x, z + half]);
  }
  return segs;
}

export function flyPath(c = CENTERS) {
  const T = c.times, F = c.confluences, W = c.while, G = c.strategies;
  const at = ([x, z], y = 2) => [x, y, z];
  return [[[0, 34, -34], [0, 18, 0]], [[F[0] - 10, 16, F[1] - 34], at(F)], [[F[0] + 34, 12, F[1] + 6], at(F)], [[30, 10, 26], [0, 10, 0]],
          [[W[0] + 44, 14, W[1] - 10], at(W)], [[W[0] + 10, 18, W[1] + 46], at(W)], [[W[0] - 44, 12, W[1] + 4], at(W)],
          [[G[0] - 20, 10, G[1] + 14], at(G)], [[T[0] - 34, 14, T[1] + 14], at(T)], [[T[0] + 6, 18, T[1] - 36], at(T)],
          [[-22, 12, -20], [0, 22, 0]], [[-14, 26, 22], [0, 16, 0]]];
}
