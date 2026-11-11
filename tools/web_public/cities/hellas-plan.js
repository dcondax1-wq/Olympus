// HELLAS plan: where everything stands. Pure maths (no three.js, no DOM), seeded, so the same data always gives the same world.
//   layoutWorld(poleis)  the Greek world: regions (mainland masses and island groups), one marker per polis, land, hills, trade routes
//   planPolis(polis)     one polis, generated from its rows: agora + acropolis in the middle, districts around it, villages (blocks of
//                        streets) inside a district, one house per row. Walls around, a gate to the south.
//   polisCollider(plan)  the walking grid (house boxes, the acropolis rock, the wall) for athens-world.js walkStep()
// x grows east, z grows south, y is up. READ ONLY scenery.
import { rng, hash32 } from './util.js';
import { PLACES, REGIONS } from './hellas-names.js';

export const BUDGET = { high: { calls: 45, tris: 160000 }, low: { calls: 28, tris: 80000 }, world: { calls: 30 } };
export const TIER = { // what a tier may draw
  low: { blocks: 5, hills: 40, ships: 0, trees: 60, npcs: 0, dpr: 1.25, detail: false },
  high: { blocks: 12, hills: 110, ships: 36, trees: 220, npcs: 36, dpr: 2, detail: true },
  ultra: { blocks: 14, hills: 150, ships: 48, trees: 320, npcs: 60, dpr: 2, detail: true },
};
const SHAPE = { crete: [2.3, .5], euboea: [.6, 1.5], ionia: [.75, 1.35], aeolis: [.8, 1.25], caria: [.85, 1.2], macedonia: [1.5, .75], thrace: [1.35, .7], epirus: [.8, 1.25], ionian: [.6, 1.6], dodecanese: [.8, 1.2] };
const GOLDEN = 2.399963229728653;
export const markerR = (p) => (p.capital ? 34 : 7 + 1.7 * Math.sqrt(Math.min(p.size, 130)));

export function layoutWorld(poleis, seed = 'hellas') {
  const regions = REGIONS.map((R) => ({ ...R, poleis: [], r: 60, cx: R.x, cz: R.z }));
  const rb = new Map(regions.map((R) => [R.key, R]));
  // names: a real Greek place per polis, picked by its id (the capital keeps "Athens")
  const used = new Set(['Athens']);
  for (const p of poleis) {
    if (p.fixedName) { p.name = p.fixedName; continue; }
    let k = hash32('name:' + p.id) % PLACES.length, guard = 0; while (used.has(PLACES[k]) && guard++ < PLACES.length) k = (k + 1) % PLACES.length;
    p.name = guard >= PLACES.length ? `${PLACES[k]} ${Math.floor(used.size / PLACES.length) + 1}` : PLACES[k]; used.add(p.name);
  }
  for (const p of poleis) { const R = rb.get(p.region) || regions[0]; p.region = R.key; p.regionName = R.name; p.mr = markerR(p); R.poleis.push(p); }
  // inside a region: a sunflower spiral, the biggest polis in the middle, then a few rounds that push neighbours apart
  for (const R of regions) {
    const L = R.poleis.sort((a, b) => (b.capital ? 1 : 0) - (a.capital ? 1 : 0) || b.size - a.size || (a.id < b.id ? -1 : 1)), n = L.length; if (!n) { R.r = 0; continue; }
    const [sx, sz] = SHAPE[R.key] || [1, 1], gap = R.kind === 'isles' ? 40 : 16, sp = (R.kind === 'isles' ? 78 : 52) * .6 * Math.sqrt(n), a0 = (hash32(seed + ':' + R.key) % 628) / 100;
    L.forEach((p, k) => { const rr = sp * Math.sqrt((k + .35) / n), th = a0 + k * GOLDEN; p.lx = Math.cos(th) * rr * sx; p.lz = Math.sin(th) * rr * sz; });
    for (let it = 0; it < 40; it++) for (let i = 0; i < n; i++) for (let j = i + 1; j < n; j++) {
      const a = L[i], b = L[j], dx = b.lx - a.lx, dz = b.lz - a.lz, d = Math.hypot(dx, dz) || .01, need = a.mr + b.mr + gap; if (d >= need) continue;
      const push = (need - d) / 2, ux = dx / d, uz = dz / d, wa = i === 0 ? 0 : 1, wb = 1; a.lx -= ux * push * wa; a.lz -= uz * push * wa; b.lx += ux * push * (wa ? wb : 2); b.lz += uz * push * (wa ? wb : 2);
    }
    R.r = Math.max(...L.map((p) => Math.hypot(p.lx, p.lz) + p.mr)) + 30; R.rx = Math.max(...L.map((p) => Math.abs(p.lx) + p.mr)) + 30; R.rz = Math.max(...L.map((p) => Math.abs(p.lz) + p.mr)) + 30;
  }
  // regions keep their place on the map but never overlap: push the centres apart (Attica, the capital's land, stays)
  const live = regions.filter((R) => R.poleis.length);
  for (let it = 0; it < 60; it++) for (let i = 0; i < live.length; i++) for (let j = i + 1; j < live.length; j++) {
    const a = live[i], b = live[j], dx = b.cx - a.cx, dz = b.cz - a.cz, need = { x: a.rx + b.rx + 44, z: a.rz + b.rz + 44 };
    const ox = need.x - Math.abs(dx), oz = need.z - Math.abs(dz); if (ox <= 0 || oz <= 0) continue;
    const fa = a.key === 'attica' ? 0 : b.key === 'attica' ? 1 : .5, fb = 1 - fa;
    if (ox < oz) { const s = dx >= 0 ? 1 : -1; a.cx -= s * ox * fa; b.cx += s * ox * fb; } else { const s = dz >= 0 ? 1 : -1; a.cz -= s * oz * fa; b.cz += s * oz * fb; }
  }
  const land = [], hills = [];
  for (const R of live) {
    for (const p of R.poleis) { p.x = Math.round((R.cx + p.lx) * 10) / 10; p.z = Math.round((R.cz + p.lz) * 10) / 10; delete p.lx; delete p.lz; }
    if (R.kind === 'isles') for (const p of R.poleis) land.push({ x: p.x, z: p.z, r: p.mr + 16, region: R.key });
    else {
      land.push({ x: R.cx, z: R.cz, r: Math.min(R.rx, R.rz) * .7, region: R.key });
      for (const p of R.poleis) land.push({ x: p.x, z: p.z, r: p.mr + 30, region: R.key });
      const r = rng(hash32(seed + ':hills:' + R.key)), want = Math.ceil(R.poleis.length * .8) + 2;
      for (let k = 0, guard = 0; k < want && guard < want * 12; guard++) {
        const q = R.poleis[Math.floor(r() * R.poleis.length)], th = r() * 6.283, d = q.mr + 14 + r() * 12, x = q.x + Math.cos(th) * d, z = q.z + Math.sin(th) * d;
        if (R.poleis.some((p) => Math.hypot(p.x - x, p.z - z) < p.mr + 11)) continue;
        hills.push({ x, z, r: 7 + r() * 9, h: 6 + r() * 16, region: R.key }); k++;
      }
    }
  }
  const xs = poleis.map((p) => p.x), zs = poleis.map((p) => p.z);
  const bounds = { x0: Math.min(...xs) - 90, x1: Math.max(...xs) + 90, z0: Math.min(...zs) - 90, z1: Math.max(...zs) + 90 };
  bounds.cx = (bounds.x0 + bounds.x1) / 2; bounds.cz = (bounds.z0 + bounds.z1) / 2; bounds.w = bounds.x1 - bounds.x0; bounds.h = bounds.z1 - bounds.z0;
  poleis.forEach((p, i) => { p.idx = i; });
  return { regions: live, land, hills, routes: tradeRoutes(poleis), bounds };
}

/** trade routes: related poleis (same source and family) joined into a shortest tree, the shortest links first, at most `cap` in all */
export function tradeRoutes(poleis, cap = 110) {
  const fam = new Map(); for (const p of poleis) { const k = p.src + '|' + p.family; (fam.get(k) || fam.set(k, []).get(k)).push(p); }
  const out = [];
  for (const [family, L] of fam) {
    if (L.length < 2) continue; const inTree = [L[0]], rest = L.slice(1);
    while (rest.length) { let best = null; for (const a of inTree) for (let j = 0; j < rest.length; j++) { const d = Math.hypot(a.x - rest[j].x, a.z - rest[j].z); if (!best || d < best.d) best = { a, j, d }; }
      const b = rest.splice(best.j, 1)[0]; inTree.push(b); out.push({ a: best.a.idx, b: b.idx, d: best.d, family }); }
  }
  return out.sort((p, q) => p.d - q.d || p.a - q.a || p.b - q.b).slice(0, cap);
}

/** a seeded voyage: n poleis from different regions, the capital first when asked. key changes the route (the date, a tap count). */
export function voyage(world, key = 'today', n = 6) {
  const r = rng(hash32('voyage:' + key)), regs = world.regions.slice().sort((a, b) => hash32(key + a.key) - hash32(key + b.key)), out = [];
  for (const R of regs) { if (out.length >= n) break; const L = R.poleis.filter((p) => !p.capital && p.rows.length); if (L.length) out.push(L[Math.floor(r() * L.length)]); }
  return out;
}

// ------------------------------------------------------------------ one polis
export const LOT = 11, STREET = 8, DGAP = 13, MAX_DISTRICTS = 6, MAX_VILLAGES = 10, VILLAGE_MAX = 36;
const D_TINT = ['#c8a24a', '#7f8a52', '#c96a4a', '#4b7a99', '#9c6b3c', '#b9a98e'];

export function planPolis(polis) {
  const r = rng(hash32('polis:' + polis.id)), rows = polis.rows || [];
  const dm = new Map();
  rows.forEach((row) => { const d = String(row.district || 'Old quarter'), v = String(row.village || 'Houses'); const m = dm.get(d) || dm.set(d, new Map()).get(d); (m.get(v) || m.set(v, []).get(v)).push(row); });
  const count = (m) => [...m.values()].reduce((s, l) => s + l.length, 0);
  let dl = [...dm].sort((a, b) => count(b[1]) - count(a[1]) || (a[0] < b[0] ? -1 : 1));
  if (dl.length > MAX_DISTRICTS) { const tail = dl.slice(MAX_DISTRICTS - 1), m = new Map(); for (const [d, vm] of tail) for (const [v, l] of vm) m.set(`${d}: ${v}`, l); dl = dl.slice(0, MAX_DISTRICTS - 1).concat([['Other quarters', m]]); }
  const A = 22 + Math.sqrt(rows.length) * 1.5, districts = [], villages = [], houses = [], rects = [];
  const a0 = (hash32('turn:' + polis.id) % 628) / 100;
  dl.forEach(([dname, vm], di) => {
    let vl = [...vm].sort((a, b) => b[1].length - a[1].length || (a[0] < b[0] ? -1 : 1));
    if (vl.length > MAX_VILLAGES) { const tail = vl.slice(MAX_VILLAGES - 1); vl = vl.slice(0, MAX_VILLAGES - 1).concat([['More houses', tail.flatMap((e) => e[1])]]); }
    const parts = []; for (const [vn, list] of vl) for (let k = 0; k < list.length; k += VILLAGE_MAX) parts.push([list.length > VILLAGE_MAX ? `${vn} (${k / VILLAGE_MAX + 1})` : vn, list.slice(k, k + VILLAGE_MAX)]);
    const blocks = parts.map(([name, list]) => { const cols = Math.ceil(Math.sqrt(list.length * 1.25)), rws = Math.ceil(list.length / cols); return { name, list, cols, rws, w: cols * LOT, d: rws * LOT }; });
    const area = blocks.reduce((s, b) => s + (b.w + STREET) * (b.d + STREET), 0), Wt = Math.max(...blocks.map((b) => b.w), Math.sqrt(area) * 1.2);
    let cx = 0, cz = 0, sh = 0, W = 0;
    for (const b of blocks) { if (cx > 0 && cx + b.w > Wt) { cx = 0; cz += sh + STREET; sh = 0; } b.x0 = cx; b.z0 = cz; cx += b.w + STREET; sh = Math.max(sh, b.d); W = Math.max(W, b.x0 + b.w); }
    const H = cz + sh, ang = dl.length === 1 ? Math.PI / 2 : a0 + di * Math.PI * 2 / dl.length, ux = Math.cos(ang), uz = Math.sin(ang);
    let px = 0, pz = 0;
    for (let d = A + Math.min(W, H) / 2; d < 4000; d += 3) {
      px = ux * d; pz = uz * d; const x0 = px - W / 2, x1 = px + W / 2, z0 = pz - H / 2, z1 = pz + H / 2;
      const nx = Math.max(x0, Math.min(0, x1)), nz = Math.max(z0, Math.min(0, z1)); if (Math.hypot(nx, nz) < A + 4) continue;
      if (rects.some((q) => x0 < q.x1 + DGAP && x1 > q.x0 - DGAP && z0 < q.z1 + DGAP && z1 > q.z0 - DGAP)) continue;
      break;
    }
    const rect = { x0: px - W / 2, x1: px + W / 2, z0: pz - H / 2, z1: pz + H / 2 }; rects.push(rect);
    const D = { idx: di, name: dname, x: px, z: pz, w: W, h: H, tint: D_TINT[di % D_TINT.length], villages: [], houses: 0, ...rect }; districts.push(D);
    for (const b of blocks) {
      const vx0 = rect.x0 + b.x0, vz0 = rect.z0 + b.z0, V = { idx: villages.length, name: b.name, district: di, x: vx0 + b.w / 2, z: vz0 + b.d / 2, w: b.w, d: b.d, x0: vx0, z0: vz0, houses: [] };
      b.list.forEach((row, j) => {
        const col = j % b.cols, rw = Math.floor(j / b.cols), w = 6 + r() * 2.2, d = 6 + r() * 2.2, rot = r() < .5, jx = (r() - .5) * 1.6, jz = (r() - .5) * 1.6;
        const h = { i: houses.length, x: vx0 + (col + .5) * LOT + jx, z: vz0 + (rw + .5) * LOT + jz, w, d, h: 4.4 + (row.size || 0) * 6.5 + r() * 1.2, rot, tone: row.tone || 'plain', row, district: di, village: V.idx };
        h.hx = (rot ? d : w) / 2 * 1.08; h.hz = (rot ? w : d) / 2 * 1.08; houses.push(h); V.houses.push(h.i);
      });
      villages.push(V); D.villages.push(V.idx); D.houses += b.list.length;
    }
  });
  let R = A + 30; for (const q of rects) for (const [x, z] of [[q.x0, q.z0], [q.x1, q.z0], [q.x0, q.z1], [q.x1, q.z1]]) R = Math.max(R, Math.hypot(x, z) + 14);
  return { id: polis.id, houses, villages, districts, R, agoraR: A, hillR: A * .46, gold: !!polis.gold, start: { x: 0, z: A * .78, yaw: 0 }, gate: { x: 0, z: R }, total: rows.length };
}

const CELL = 12;
export function polisCollider(plan) {
  const grid = new Map(), add = (k, o) => { let a = grid.get(k); if (!a) grid.set(k, a = []); a.push(o); };
  const boxes = plan.houses.map((h) => { const b = { x: h.x, z: h.z, hx: h.hx, hz: h.hz }; for (let i = Math.floor((b.x - b.hx - 1) / CELL); i <= Math.floor((b.x + b.hx + 1) / CELL); i++) for (let j = Math.floor((b.z - b.hz - 1) / CELL); j <= Math.floor((b.z + b.hz + 1) / CELL); j++) add(i + ',' + j, b); return b; });
  const hits = (x, z, r = .45) => {
    const d = Math.hypot(x, z); if (d > plan.R - 2.5 || d < plan.hillR + r) return true;
    const seen = grid.get(Math.floor(x / CELL) + ',' + Math.floor(z / CELL));
    if (seen) for (const b of seen) { const px = Math.max(b.x - b.hx, Math.min(x, b.x + b.hx)), pz = Math.max(b.z - b.hz, Math.min(z, b.z + b.hz)); if ((x - px) ** 2 + (z - pz) ** 2 < r * r) return true; }
    return false;
  };
  const move = (x, z, dx, dz, r = .45) => { let nx = x, nz = z; const n = Math.max(1, Math.ceil(Math.hypot(dx, dz) / .35)), sx = dx / n, sz = dz / n; for (let i = 0; i < n; i++) { if (!hits(nx + sx, nz, r)) nx += sx; if (!hits(nx, nz + sz, r)) nz += sz; } return [nx, nz]; };
  return { hits, move, boxes, boxCount: boxes.length };
}

/** villagers walk the street around their village block: always clear of houses. Returns loops; npcOnLoop(n, t) gives x, z, yaw. */
export function polisNpcs(plan, count, seed = 'npc') {
  const r = rng(hash32(seed + ':' + plan.id)), vs = plan.villages.filter((v) => v.houses.length), out = [];
  for (let i = 0; i < count && vs.length; i++) { const v = vs[i % vs.length], m = STREET * .42; out.push({ i, village: v.idx, x0: v.x0 - m, z0: v.z0 - m, w: v.w + m * 2, d: v.d + m * 2, speed: (1 + r() * .6) * (r() < .5 ? 1 : -1), ph: r() }); }
  return out;
}
export function npcOnLoop(n, t) {
  const per = 2 * (n.w + n.d); let s = (((t * n.speed + n.ph * per) % per) + per) % per; const dir = n.speed >= 0 ? 1 : -1;
  if (s < n.w) return { x: n.x0 + s, z: n.z0, yaw: dir > 0 ? Math.PI / 2 : -Math.PI / 2 }; s -= n.w;
  if (s < n.d) return { x: n.x0 + n.w, z: n.z0 + s, yaw: dir > 0 ? Math.PI : 0 }; s -= n.d;
  if (s < n.w) return { x: n.x0 + n.w - s, z: n.z0 + n.d, yaw: dir > 0 ? -Math.PI / 2 : Math.PI / 2 }; s -= n.w;
  return { x: n.x0, z: n.z0 + n.d - s, yaw: dir > 0 ? 0 : Math.PI };
}
/** where a walker stands: district, village, nearest house within 16 m */
export function whereInPolis(plan, x, z) {
  let v = null, vd = 1e9; for (const q of plan.villages) { const dx = Math.max(q.x0 - x, 0, x - (q.x0 + q.w)), dz = Math.max(q.z0 - z, 0, z - (q.z0 + q.d)), d = Math.hypot(dx, dz); if (d < vd) { vd = d; v = q; } }
  if (vd > 14) v = null; let h = null, hd = 16; if (v) for (const i of v.houses) { const q = plan.houses[i], d = Math.hypot(q.x - x, q.z - z); if (d < hd) { hd = d; h = q; } }
  return { district: v ? plan.districts[v.district] : null, village: v, house: h, agora: Math.hypot(x, z) < plan.agoraR };
}
