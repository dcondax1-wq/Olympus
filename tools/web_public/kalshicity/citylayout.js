// KALSHI CITY layout (pure ES module, no three.js): where every district, building, road and scenery tower stands. Deterministic: the same
// model always gives the same city. One district per market (Bitcoin, Ethereum, Dogecoin, ...) on a ring round Downtown, which holds the
// edges that belong to no single market (a strategy, a price band, a side, an hour). Inside a district the biggest edges stand in the middle.
// Each district is a grid with a cross of streets through its middle; an avenue runs from Downtown to its centre.
import { MIN_N, ageDays } from './cityfeed.js';

export const SP = 4.4;                 // grid cell
export const COLORS = {
  Downtown: '#2ef2d0', Bitcoin: '#ff9a1f', Ethereum: '#8f9bff', Dogecoin: '#ffd23f', XRP: '#4fb2ff', Solana: '#b36bff', HYPE: '#6dffd0', BNB: '#f3ba2f', Gold: '#ffe08a', Silver: '#cfd8ee', Other: '#9fb0cf',
};
const SPARE = ['#ff6b9d', '#5eead4', '#a3e635', '#fb7185', '#38bdf8', '#f59e0b'];
export const colorOf = (name, i = 0) => COLORS[name] || SPARE[i % SPARE.length];
const clamp01 = (x) => Math.max(0, Math.min(1, x));
export function rng(seed) { let s = seed >>> 0 || 1; return () => { s = (Math.imul(s, 1664525) + 1013904223) >>> 0; return s / 4294967296; }; }
const hashStr = (str) => { let h = 2166136261; for (let i = 0; i < str.length; i++) h = Math.imul(h ^ str.charCodeAt(i), 16777619); return h >>> 0; };

/** The building of one edge: footprint, height and the numbers the shader needs. evMax = the model's biggest EV. */
export function buildingOf(e, evMax, dayIso) {
  const size = 1.15 + 1.45 * clamp01(Math.log10(1 + e.n) / 3);
  let h;
  if (e.small) h = 1.4 + 5.5 * clamp01(e.n / MIN_N);
  else if (e.ev > 0) h = 2.6 + 27 * Math.sqrt(clamp01(e.ev / evMax));
  else h = 1.8 + 2.6 * clamp01(Math.abs(e.ev || 0) / 0.1);                  // a losing edge is a low stub
  const dead = e.status === 'DEAD';
  const sinceAge = ageDays(e.since, dayIso), firstAge = ageDays(e.first, dayIso);
  const mode = dead && sinceAge <= 3 ? 2 : (firstAge <= 3 ? 1 : 0);          // 1 = going up, 2 = crumbling
  const wRecent = e.win.d7.n >= 10 && e.win.d7.w != null ? e.win.d7.w : e.w;
  const glow = clamp01(((wRecent == null ? 0.6 : wRecent) - 0.6) / 0.4) * (e.small ? 0.3 : 1) * (dead ? 0.35 : 1);
  return {
    w: size, d: size * (0.8 + 0.4 * ((hashStr(e.id) % 100) / 100)), h: dead && mode === 0 ? h * 0.18 : h, fullH: h, mode,
    glow: Math.max(0.04, glow), lit: clamp01(Math.log10(1 + e.n) / 3.3) * (dead ? 0.35 : 1), loss: Math.min(0.6, Math.max(0.02, 1 - (e.w == null ? 0.9 : e.w))),
  };
}

function slots(count, reserve) {
  const half = Math.max(2, Math.ceil(Math.sqrt(count + (reserve ? 12 : 0))) + 1), cells = [];
  for (let i = -half; i < half; i++) for (let j = -half; j < half; j++) {
    const x = (i + 0.5) * SP, z = (j + 0.5) * SP;
    if (reserve && Math.hypot(x, z) < reserve) continue;
    cells.push([x, z, Math.hypot(x, z) + 0.001 * (i + j)]);
  }
  cells.sort((a, b) => a[2] - b[2] || a[0] - b[0]);
  return cells.slice(0, count);
}

/** model (cityfeed.shape) -> the whole city's geometry */
export function layout(model, prev = null) {
  const groups = new Map();
  for (const e of model.edges) {
    const key = e.dims[1] !== '*' ? e.dims[1] : 'Downtown';
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push(e);
  }
  if (!groups.has('Downtown')) groups.set('Downtown', []);
  const weight = (list) => list.reduce((s, e) => s + (e.size === 1 ? e.n : 0), 0);
  const names = [...groups.keys()].filter((k) => k !== 'Downtown').sort((a, b) => weight(groups.get(b)) - weight(groups.get(a)) || (a < b ? -1 : 1));
  const RESERVE = 9;
  const mk = (key, list, reserve) => {
    list.sort((a, b) => a.size - b.size || b.n - a.n || (a.id < b.id ? -1 : 1));
    const cells = slots(list.length, reserve), ext = cells.reduce((m, c) => Math.max(m, Math.abs(c[0]), Math.abs(c[1])), 0);
    return { key, name: key, list, cells, half: Math.max(8, ext + SP * 0.75), count: list.length, color: colorOf(key, names.indexOf(key)) };
  };
  const down = mk('Downtown', groups.get('Downtown'), RESERVE);
  const ds = names.map((k) => mk(k, groups.get(k), 0));
  const m = ds.length, maxHalf = ds.reduce((a, d) => Math.max(a, d.half), 10);
  const ring = m ? Math.max(down.half + maxHalf + 24, (2 * maxHalf + 18) / (2 * Math.sin(Math.PI / Math.max(2, m)))) : 0;
  const districts = [{ ...down, cx: 0, cz: 0, ez: [0, 1], ex: [1, 0], ang: 0 }];
  ds.forEach((d, i) => {
    const ang = -Math.PI / 2 + (i / m) * Math.PI * 2, cx = Math.cos(ang) * ring, cz = Math.sin(ang) * ring;
    const ez = [-cx / ring, -cz / ring];                                   // the local +z axis points at Downtown
    districts.push({ ...d, cx, cz, ez, ex: [-ez[1], ez[0]], ang });
  });
  const buildings = [];
  const evMax = model.evMax || 0.02;
  for (const d of districts) {
    const yaw = Math.atan2(-d.ex[1], d.ex[0]);
    d.cells.forEach((c, i) => {
      const e = d.list[i];
      if (!e) return;
      const x = d.cx + c[0] * d.ex[0] + c[1] * d.ez[0], z = d.cz + c[0] * d.ex[1] + c[1] * d.ez[1];
      buildings.push({ id: e.id, e, district: d.key, x, z, yaw, ...buildingOf(e, evMax, model.day) });
    });
  }
  // roads: an avenue from Downtown out to and through each district, a cross street through each district, a ring road round Downtown
  const roads = [];
  for (const d of districts.slice(1)) {
    roads.push({ kind: 'avenue', district: d.key, x0: 0, z0: 0, x1: d.cx - d.ez[0] * d.half, z1: d.cz - d.ez[1] * d.half, w: 3.4 });
    roads.push({ kind: 'cross', district: d.key, x0: d.cx - d.ex[0] * d.half, z0: d.cz - d.ex[1] * d.half, x1: d.cx + d.ex[0] * d.half, z1: d.cz + d.ex[1] * d.half, w: 2.4 });
  }
  const rr = down.half + 7, seg = 40;
  for (let i = 0; i < seg; i++) {
    const a0 = (i / seg) * Math.PI * 2, a1 = ((i + 1) / seg) * Math.PI * 2;
    roads.push({ kind: 'ring', district: 'Downtown', x0: Math.cos(a0) * rr, z0: Math.sin(a0) * rr, x1: Math.cos(a1) * rr, z1: Math.sin(a1) * rr, w: 2.6 });
  }
  // the Lab: one small district per research idea on an outer ring, three towers each (looking back, live, live bets collected)
  const labs = [];
  let labR = 0;
  const H = model.hyp;
  if (H && H.hyps.length) {
    const n = H.hyps.length, R = (m ? ring + maxHalf : 30) + LAB_HALF + 18, parts = ['back', 'live', 'prog'];
    const maxG = Math.max(5, ...H.hyps.flatMap((h) => [Math.abs(h.back.gain), Math.abs(h.live.gain)]));
    labR = R;
    H.hyps.forEach((h, i) => {
      const ang = -Math.PI / 2 + Math.PI / n + (i / n) * Math.PI * 2, cx = Math.cos(ang) * R, cz = Math.sin(ang) * R;
      const ez = [-cx / R, -cz / R], ex = [-ez[1], ez[0]], yaw = Math.atan2(-ex[1], ex[0]);
      parts.forEach((part, k) => {
        const off = (k - 1) * LAB_GAP;
        buildings.push({ id: `hyp:${h.id}:${part}`, district: 'Lab', lab: h.id, part, x: cx + off * ex[0], z: cz + off * ex[1], yaw, ...hypBuilding(h, part, maxG, prev) });
      });
      labs.push({ key: h.id, name: h.short, cx, cz, ez, ex, half: LAB_HALF, color: LAB_COLORS[i % LAB_COLORS.length], count: 3, ang, yaw });
    });
    const Rr = R + LAB_HALF + 4, seg = 72;
    for (let i = 0; i < seg; i++) {
      const a0 = (i / seg) * Math.PI * 2, a1 = ((i + 1) / seg) * Math.PI * 2;
      roads.push({ kind: 'labring', district: 'Lab', x0: Math.cos(a0) * Rr, z0: Math.sin(a0) * Rr, x1: Math.cos(a1) * Rr, z1: Math.sin(a1) * Rr, w: 2.4 });
    }
    labs.forEach((d) => roads.push({ kind: 'labspur', district: 'Lab', x0: d.cx - d.ez[0] * (LAB_HALF - 1), z0: d.cz - d.ez[1] * (LAB_HALF - 1), x1: -d.ez[0] * Rr, z1: -d.ez[1] * Rr, w: 2.0 }));
  }
  const extent = (labs.length ? labR + LAB_HALF + 4 : ring + maxHalf) + 30;
  return { districts, buildings, roads, ring, extent, ringRoad: rr, downHalf: down.half, reserve: RESERVE, labs, labRing: labR, edgeCount: buildings.length - labs.length * 3 };
}

// ------------------------------------------------------------------ the Lab (one district per research idea)
export const LAB_HALF = 9.5, LAB_GAP = 5.8;
export const LAB_COLORS = ['#7cf0ff', '#b3ff8a', '#ffb86b', '#ff8fd0', '#a9a0ff', '#ffe36b', '#7dffd1', '#ff8a8a', '#9fd0ff', '#d0ff7c'];
const PART_WORD = { back: 'looking back', live: 'live', prog: 'live bets collected' };
const gainH = (g, maxG) => (g > 0 ? 3 + 24 * Math.sqrt(clamp01(g / maxG)) : g < 0 ? 1.7 + 2.0 * clamp01(-g / maxG) : 1.3);       // a loss is a low stub, nothing is ever invisible
/** One tower of an idea: back = what the rule would have added looking back, live = what it adds on bets since it was registered, prog = how many live bets are collected
 *  (a crane over it until 30). `prev` = the dollars stored on the viewer's last visit: a tower that moved since then resizes in front of them (mode 3). */
export function hypBuilding(h, part, maxG, prev) {
  const win = part === 'live' ? h.live : h.back, filter = h.kind === 'filter';
  const g = part === 'prog' ? 0 : win.gain;
  const n = part === 'back' ? (filter ? h.back.nSkip : h.back.nAll) : h.nLive;
  const key = `${h.id}:${part}`, nowV = part === 'prog' ? h.nLive : g;
  const hh = part === 'prog' ? 1.4 + 11 * Math.sqrt(clamp01(h.needed ? h.nLive / h.needed : 0)) : gainH(g, maxG);
  const status = part === 'back' ? h.back.status : part === 'live' ? h.live.status : 'NEW';
  const small = part === 'prog' || (filter ? n < MIN_N : part === 'live' && n < MIN_N) || h.kind === 'data';
  let mode = part === 'prog' && h.nLive < MIN_N ? 1 : 0, from = 0;
  if (prev && prev[key] != null && Math.abs(prev[key] - nowV) >= (part === 'prog' ? 1 : 0.5)) {
    const old = part === 'prog' ? 1.4 + 11 * Math.sqrt(clamp01(h.needed ? prev[key] / h.needed : 0)) : gainH(prev[key], maxG);
    mode = 3; from = Math.min(4, Math.max(0.05, old / hh));
  }
  const w = win.w == null ? 0.9 : win.w, size = 1.6 + 0.9 * clamp01(Math.log10(1 + n) / 3);
  const glow = part === 'back' ? 0.28 : part === 'live' ? 0.35 + 0.6 * clamp01(h.nLive / Math.max(MIN_N, h.needed)) : 0.3;
  const e = { id: `hyp:${h.id}:${part}`, label: `${h.name}: ${PART_WORD[part]}`, dims: ['*', '*', '*', '*', '*'], kind: 'hyp', size: 1, n, wins: 0, w, p: null, ev: null, pnl: g, status, small, advice: 'collect',
    lab: true, hyp: h.id, part, first: '', since: '', last: null, win: { d7: { n: 0 }, d30: { n: 0 }, led: { n: 0 } } };
  return { e, w: size, d: size * 0.9, h: hh, fullH: hh, mode, from, glow, lit: clamp01(Math.log10(1 + n) / 3.3), loss: Math.min(0.6, Math.max(0.02, 1 - w)) };
}

/** The scenery: dark towers with no data (the far skyline), as many as the biggest tier needs, in a fixed random order. */
export function scenery(L, count = 4200) {
  const r = rng(36), out = [], R0 = L.extent * 0.98, R1 = R0 + 250;
  let guard = 0;
  while (out.length < count && guard++ < count * 4) {
    const a = r() * Math.PI * 2, rad = R0 + (R1 - R0) * Math.sqrt(r());
    const far = (rad - R0) / (R1 - R0);                                     // the skyline rises with distance, like a bowl round the city
    out.push({ x: Math.cos(a) * rad, z: Math.sin(a) * rad, w: 2 + r() * 5, d: 2 + r() * 5, h: 4 + Math.pow(r(), 2.0) * (14 + 80 * far), yaw: r() * Math.PI, seed: r(), lit: 0.1 + r() * 0.5 });
  }
  return out;
}
