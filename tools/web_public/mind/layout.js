// OLYMPUS Mind: the graph layout. A 3D force simulation that turns the vault into galaxies:
//   - every note pushes every other away (Barnes-Hut octree, O(n log n), so ~2,000 notes stay cheap),
//   - links are springs (short inside a cluster, long and weak between clusters),
//   - each cluster is pulled to its own anchor and flattened into a tilted disc (the galaxy look).
// It cools like d3-force (alpha decays to ALPHA_MIN, then the simulation sleeps until the next graph).
// Pure and DOM-free: it runs in layout-worker.js, or on the main thread when module workers are missing.
//   - Jarvis's memories (the `ring` cluster) are held on a tilted ring around "Me" at the centre (the cyan memory ring).
//   anchorsFor(sizes, center) -> {pos, normal, radius}          where each cluster lives (shared with the seeding in main.js)
//   ringSpot(k, count, radius) -> [x, y, z]                      the k-th memory's seat on the ring (also the seeding and the drawn ring)
//   new Layout().setGraph({pos, cluster, edges, sizes, center, ring, alpha}); layout.tick() -> alpha
//   createLayoutHost(onPositions) -> {run(graph), mode}         worker first, main-thread fallback; stale results dropped

const ALPHA_MIN = 0.004;
const DECAY = 1 - Math.pow(ALPHA_MIN, 1 / 300);   // ~300 ticks from a cold start to sleep
const VELOCITY_KEEP = 0.6;
const CHARGE = -26;
const THETA2 = 1.44;                               // Barnes-Hut opening criterion (theta 1.2: a picture, not physics)
const DIST_MIN2 = 4;
const DIST_MAX = 240, DIST_MAX2 = DIST_MAX * DIST_MAX;   // far galaxies stop pushing each other (their anchors hold them)
const LINK_IN = 14, LINK_OUT = 90, LINK_OUT_K = 0.05;
const PULL = 0.07, FLATTEN = 0.1;
const MAX_DEPTH = 18;
const GOLDEN = Math.PI * (3 - Math.sqrt(5));
const RING_PULL = 0.5;                              // the memory ring holds tight: a ring, not a cloud
/** The memory ring's plane (unit normal): tilted toward the camera's usual view so it reads as a ring, not a line. */
export const RING_NORMAL = (() => { const x = 0.32, y = 1, z = 0.22, l = Math.hypot(x, y, z); return [x / l, y / l, z / l]; })();

/** The memory ring's radius for a vault of `total` notes (inside the galaxies, outside Me's glow). */
export function ringRadius(total) { return 30 + 2.6 * Math.sqrt(total); }

/** Seat k of `count` on the memory ring around the origin (where Me sits). */
export function ringSpot(k, count, radius) {
  const [nx, ny, nz] = RING_NORMAL;
  // two axes in the ring's plane: u = normal x Z, w = normal x u
  let ux = ny * 1 - nz * 0, uy = nz * 0 - nx * 1, uz = 0;
  const ul = Math.hypot(ux, uy, uz) || 1; ux /= ul; uy /= ul; uz /= ul;
  const wx = ny * uz - nz * uy, wy = nz * ux - nx * uz, wz = nx * uy - ny * ux;
  const a = (k / Math.max(1, count)) * Math.PI * 2 + 0.4, c = Math.cos(a) * radius, s = Math.sin(a) * radius;
  return [ux * c + wx * s, uy * c + wy * s, uz * c + wz * s];
}

/** Cluster anchors on a Fibonacci sphere (the center cluster, "me", at the origin) and a tilted disc normal per cluster. */
export function anchorsFor(sizes, center = -1) {
  const k = sizes.length;
  const pos = new Float32Array(k * 3), normal = new Float32Array(k * 3);
  let total = 0, biggest = 1;
  for (const s of sizes) { total += s; biggest = Math.max(biggest, s); }
  const radius = 46 + 10 * Math.sqrt(total);
  const ring = k - (center >= 0 && center < k ? 1 : 0);
  let j = 0;
  for (let c = 0; c < k; c++) {
    if (c !== center) {
      const y = ring > 1 ? 1 - (2 * (j + 0.5)) / ring : 0;
      const r = Math.sqrt(1 - y * y), a = j * GOLDEN;
      const d = radius * (0.72 + 0.28 * Math.sqrt(sizes[c] / biggest));
      pos[c * 3] = Math.cos(a) * r * d; pos[c * 3 + 1] = y * d * 0.8; pos[c * 3 + 2] = Math.sin(a) * r * d;
      j++;
    }
    const nx = Math.sin(c * 2.39) * 0.6, ny = 1, nz = Math.cos(c * 1.71) * 0.6;
    const l = Math.hypot(nx, ny, nz);
    normal[c * 3] = nx / l; normal[c * 3 + 1] = ny / l; normal[c * 3 + 2] = nz / l;
  }
  return { pos, normal, radius };
}

export class Layout {
  constructor() { this.n = 0; this.alpha = 0; this.cap = 0; }

  setGraph({ pos, cluster, edges, sizes, center = -1, ring = -1, alpha = 1 }) {
    const n = (this.n = cluster.length);
    this.pos = pos;
    this.vel = new Float32Array(n * 3);
    this.cluster = cluster;
    this.alpha = n ? alpha : 0;
    this.center = center;
    const { pos: anchor, normal } = anchorsFor(sizes, center);
    this.anchor = anchor; this.normal = normal;
    // the memory ring: each memory's seat, in order (NaN = a free note)
    this.seat = null;
    if (ring >= 0 && center >= 0 && cluster.indexOf(center) >= 0) {
      const members = [];
      for (let i = 0; i < n; i++) if (cluster[i] === ring) members.push(i);
      this.me = cluster.indexOf(center);                           // the ring turns with Me, wherever the springs pull it
      const r = ringRadius(n);
      this.seat = new Float32Array(n * 3).fill(NaN);
      members.forEach((i, k) => this.seat.set(ringSpot(k, members.length, r), i * 3));
    }
    // springs (d3-force link): strength 1 / min degree, bias toward the lighter end
    const m = edges.length >> 1, deg = new Uint16Array(n);
    for (let e = 0; e < m * 2; e++) deg[edges[e]]++;
    this.edges = edges;
    this.linkLen = new Float32Array(m); this.linkK = new Float32Array(m); this.linkBias = new Float32Array(m);
    for (let e = 0; e < m; e++) {
      const s = edges[e * 2], t = edges[e * 2 + 1], same = cluster[s] === cluster[t];
      this.linkLen[e] = same ? LINK_IN : LINK_OUT;
      this.linkK[e] = (same ? 1 : LINK_OUT_K) / Math.max(1, Math.min(deg[s], deg[t]));
      this.linkBias[e] = deg[s] / (deg[s] + deg[t]);
    }
    this.weight = new Float32Array(n);
    for (let i = 0; i < n; i++) this.weight[i] = 1 + Math.min(3, deg[i] * 0.12);
    this.next = new Int32Array(n);
    this._grow(n * 4 + 64);
    this.stack = new Int32Array(MAX_DEPTH * 8 + 16);
  }

  tick() {
    if (!this.n) return (this.alpha = 0);
    const a = this.alpha, p = this.pos, v = this.vel;
    this._build();
    this._repel(a);
    this._springs(a);
    this._galaxies(a);
    for (let i = 0; i < p.length; i++) { v[i] *= VELOCITY_KEEP; p[i] += v[i]; }
    this.alpha -= this.alpha * DECAY;
    return this.alpha;
  }

  _grow(cap) {
    if (cap <= this.cap) return;
    this.cap = cap;
    this.ox = new Float32Array(cap); this.oy = new Float32Array(cap); this.oz = new Float32Array(cap); this.half = new Float32Array(cap);
    this.kid = new Int32Array(cap); this.head = new Int32Array(cap);
    this.mass = new Float32Array(cap); this.mx = new Float32Array(cap); this.my = new Float32Array(cap); this.mz = new Float32Array(cap);
  }

  _cell(x, y, z, h) {
    if (this.cells >= this.cap) this._regrow();
    const c = this.cells++;
    this.ox[c] = x; this.oy[c] = y; this.oz[c] = z; this.half[c] = h; this.kid[c] = -1; this.head[c] = -1;
    return c;
  }

  _regrow() {                                       // keep the tree built so far, double the room
    const old = ['ox', 'oy', 'oz', 'half', 'kid', 'head', 'mass', 'mx', 'my', 'mz'].map((k) => this[k]);
    this.cap = 0; this._grow(old[0].length * 2);
    ['ox', 'oy', 'oz', 'half', 'kid', 'head', 'mass', 'mx', 'my', 'mz'].forEach((k, i) => this[k].set(old[i]));
  }

  _build() {
    const p = this.pos, n = this.n;
    let x0 = Infinity, y0 = Infinity, z0 = Infinity, x1 = -Infinity, y1 = -Infinity, z1 = -Infinity;
    for (let i = 0; i < n; i++) {
      const x = p[i * 3], y = p[i * 3 + 1], z = p[i * 3 + 2];
      if (x < x0) x0 = x; if (x > x1) x1 = x; if (y < y0) y0 = y; if (y > y1) y1 = y; if (z < z0) z0 = z; if (z > z1) z1 = z;
    }
    this.cells = 0;
    this._cell((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2, Math.max(x1 - x0, y1 - y0, z1 - z0) / 2 + 1);
    for (let i = 0; i < n; i++) this._insert(i);
    // centre of mass, children before parents (children always have higher indices)
    const { kid, head, next, weight, mass, mx, my, mz } = this;
    for (let c = this.cells - 1; c >= 0; c--) {
      let m = 0, sx = 0, sy = 0, sz = 0;
      if (kid[c] < 0) {
        for (let j = head[c]; j >= 0; j = next[j]) { const w = weight[j]; m += w; sx += p[j * 3] * w; sy += p[j * 3 + 1] * w; sz += p[j * 3 + 2] * w; }
      } else {
        for (let o = kid[c]; o < kid[c] + 8; o++) { const w = mass[o]; if (w) { m += w; sx += mx[o] * w; sy += my[o] * w; sz += mz[o] * w; } }
      }
      mass[c] = m;
      if (m) { mx[c] = sx / m; my[c] = sy / m; mz[c] = sz / m; }
    }
  }

  _octant(c, i) {
    const p = this.pos;
    return (p[i * 3] >= this.ox[c] ? 1 : 0) | (p[i * 3 + 1] >= this.oy[c] ? 2 : 0) | (p[i * 3 + 2] >= this.oz[c] ? 4 : 0);
  }

  _insert(i) {
    let c = 0;
    for (let depth = 0; ; depth++) {
      if (this.kid[c] < 0) {
        if (this.head[c] < 0 || depth >= MAX_DEPTH) { this.next[i] = this.head[c]; this.head[c] = i; return; }
        const j = this.head[c], h = this.half[c] / 2;     // split the leaf, move its note down one level
        this.head[c] = -1;
        const first = this.cells;
        for (let o = 0; o < 8; o++) this._cell(this.ox[c] + (o & 1 ? h : -h), this.oy[c] + (o & 2 ? h : -h), this.oz[c] + (o & 4 ? h : -h), h);
        this.kid[c] = first;
        const cj = first + this._octant(c, j);
        this.next[j] = -1; this.head[cj] = j;
      }
      c = this.kid[c] + this._octant(c, i);
    }
  }

  _repel(a) {
    const { pos: p, vel: v, kid, head, next, weight, mass, mx, my, mz, ox, oy, oz, half, stack } = this;
    const k = CHARGE * a;
    for (let i = 0; i < this.n; i++) {
      const xi = p[i * 3], yi = p[i * 3 + 1], zi = p[i * 3 + 2];
      let fx = 0, fy = 0, fz = 0, sp = 0;
      stack[sp++] = 0;
      while (sp) {
        const c = stack[--sp];
        if (!mass[c]) continue;
        if (kid[c] < 0) {
          for (let j = head[c]; j >= 0; j = next[j]) {
            if (j === i) continue;
            let dx = p[j * 3] - xi, dy = p[j * 3 + 1] - yi, dz = p[j * 3 + 2] - zi, d2 = dx * dx + dy * dy + dz * dz;
            if (d2 >= DIST_MAX2) continue;
            if (d2 === 0) { dx = (((i * 7919 + j) % 13) - 6) * 0.01 + 0.005; dy = 0.01; d2 = dx * dx + dy * dy; }
            if (d2 < DIST_MIN2) d2 = Math.sqrt(DIST_MIN2 * d2);
            const f = (k * weight[j]) / d2;
            fx += dx * f; fy += dy * f; fz += dz * f;
          }
        } else {
          const dx = mx[c] - xi, dy = my[c] - yi, dz = mz[c] - zi, d2 = dx * dx + dy * dy + dz * dz, s = half[c] * 2;
          if (s * s < THETA2 * d2) {
            if (d2 < DIST_MAX2) { const f = (k * mass[c]) / d2; fx += dx * f; fy += dy * f; fz += dz * f; }
          } else {
            const ex = ox[c] - xi, ey = oy[c] - yi, ez = oz[c] - zi;   // a cube wholly beyond the cutoff is skipped unopened
            if (Math.sqrt(ex * ex + ey * ey + ez * ez) - half[c] * 1.74 >= DIST_MAX) continue;
            for (let o = kid[c]; o < kid[c] + 8; o++) stack[sp++] = o;
          }
        }
      }
      v[i * 3] += fx; v[i * 3 + 1] += fy; v[i * 3 + 2] += fz;
    }
  }

  _springs(a) {
    const { pos: p, vel: v, edges, linkLen, linkK, linkBias } = this;
    for (let e = 0; e < linkLen.length; e++) {
      const s = edges[e * 2] * 3, t = edges[e * 2 + 1] * 3;
      let x = p[t] + v[t] - p[s] - v[s], y = p[t + 1] + v[t + 1] - p[s + 1] - v[s + 1], z = p[t + 2] + v[t + 2] - p[s + 2] - v[s + 2];
      let l = Math.sqrt(x * x + y * y + z * z) || 1e-3;
      l = ((l - linkLen[e]) / l) * a * linkK[e];
      x *= l; y *= l; z *= l;
      const b = linkBias[e];
      v[t] -= x * b; v[t + 1] -= y * b; v[t + 2] -= z * b;
      v[s] += x * (1 - b); v[s + 1] += y * (1 - b); v[s + 2] += z * (1 - b);
    }
  }

  _galaxies(a) {
    const { pos: p, vel: v, cluster, anchor: A, normal: N } = this;
    const kf = FLATTEN * a, seat = this.seat;
    for (let i = 0; i < this.n; i++) {
      const i3s = i * 3;
      if (seat && seat[i3s] === seat[i3s]) {                       // a memory: pulled to its seat on the ring
        const kr = RING_PULL * a, m3 = this.me * 3;
        for (let x = 0; x < 3; x++) v[i3s + x] += (p[m3 + x] + seat[i3s + x] - p[i3s + x]) * kr;
        continue;
      }
      const c = cluster[i] * 3, i3 = i * 3, kp = PULL * a * (cluster[i] === this.center ? 5 : 1);   // "me" holds the centre
      const dx = A[c] - p[i3], dy = A[c + 1] - p[i3 + 1], dz = A[c + 2] - p[i3 + 2];
      const off = -(dx * N[c] + dy * N[c + 1] + dz * N[c + 2]);     // height above the galaxy's disc
      v[i3] += dx * kp - N[c] * off * kf;
      v[i3 + 1] += dy * kp - N[c + 1] * off * kf;
      v[i3 + 2] += dz * kp - N[c + 2] * off * kf;
    }
  }
}

/** Run a layout to sleep in time slices, emitting (positions, asleep) after each slice. Returns stop(). */
export function drive(layout, emit, budgetMs) {
  let timer = 0, stopped = false;
  const slice = () => {
    if (stopped) return;
    const t0 = performance.now();
    do layout.tick(); while (layout.alpha > ALPHA_MIN && performance.now() - t0 < budgetMs);
    emit(layout.pos, layout.alpha <= ALPHA_MIN);
    if (layout.alpha > ALPHA_MIN) timer = setTimeout(slice, 16);
  };
  slice();
  return () => { stopped = true; clearTimeout(timer); };
}

/** The layout off the main thread when possible. onPositions(Float32Array, asleep) gets only the latest graph's results. */
export function createLayoutHost(onPositions) {
  let worker = null, gen = 0, last = null, inline = null, stopInline = null;
  const runInline = (g) => {
    if (stopInline) stopInline();
    inline = inline || new Layout();
    inline.setGraph({ ...g, pos: g.pos.slice() });
    stopInline = drive(inline, (pos, asleep) => onPositions(pos.slice(), asleep), 6);
  };
  try {
    worker = new Worker(new URL('./layout-worker.js', import.meta.url), { type: 'module' });
    worker.onmessage = (e) => { if (e.data.gen === gen) onPositions(e.data.pos, e.data.asleep); };
    worker.onerror = (e) => { e.preventDefault(); worker.terminate(); worker = null; if (last) runInline(last); };
  } catch (_) {
    worker = null;
  }
  return {
    run(g) {
      last = g; gen++;
      if (worker) worker.postMessage({ ...g, pos: g.pos.slice(), gen });
      else runInline(g);
    },
    get mode() { return worker ? 'worker' : 'inline'; },
  };
}
