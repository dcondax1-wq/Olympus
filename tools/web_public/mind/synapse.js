// OLYMPUS Mind: synapses. Glowing pulses that run along the links: a burst out of a note when it is opened or learns
// something (its neighbours first, then theirs), and, while the brain is idle, a quiet "thinking" pulse now and then along a
// random chain of links. Each pulse is a bright head with a short fading tail; one draw call (point sprites), CPU-placed.
// None under reduced motion (the note just ignites).
//   const syn = new Synapses(THREE, material); syn.points -> THREE.Points
//   syn.fire(i, graph, now, colour?) ; syn.think(graph, now) ; syn.update(now, disp, onArrive(i)) -> live pulses

const CAP = 120, TAIL = 4, HOP_S = 0.6, FIRST_FAN = 16, SECOND_FAN = 3, THINK_HOPS = 4;

export const SYNAPSE_VS = `
attribute float aSize, aAlpha; attribute vec3 aColor;
uniform float uScale;
varying vec3 vColor; varying float vA;
void main() {
  vec4 mv = modelViewMatrix * vec4(position, 1.0);
  gl_PointSize = clamp(aSize * uScale / max(1.0, -mv.z), 1.5, 48.0) * step(0.001, aAlpha);
  vA = aAlpha; vColor = aColor;
  gl_Position = projectionMatrix * mv;
}`;

export class Synapses {
  constructor(THREE, material) {
    const T = THREE, P = CAP * TAIL;
    this.T = T;
    this.pos = new Float32Array(P * 3); this.size = new Float32Array(P); this.alpha = new Float32Array(P); this.col = new Float32Array(P * 3);
    const g = new T.BufferGeometry();
    for (const [k, a, s] of [['position', this.pos, 3], ['aSize', this.size, 1], ['aAlpha', this.alpha, 1], ['aColor', this.col, 3]]) {
      g.setAttribute(k, new T.BufferAttribute(a, s).setUsage(T.DynamicDrawUsage));
    }
    this.points = new T.Points(g, material);
    this.live = [];
    this.nextThink = 0;
    this._c = new T.Color();
  }

  get count() { return this.live.length; }

  _add(a, b, t0, colour, chain = 0) {
    if (this.live.length >= CAP) return;
    this.live.push({ a, b, t0, dur: HOP_S * (0.85 + Math.random() * 0.3), colour, chain, arrived: false });
  }

  /** A burst from note i: to its neighbours, then a few of theirs (the "synapse" of opening or learning). */
  fire(i, graph, now, colour = null) {
    const n = graph.nodes[i];
    if (!n) return;
    const near = neighbours(graph, i).slice(0, FIRST_FAN);
    const c = colour ? new this.T.Color(colour) : null;
    near.forEach((j, k) => {
      this._add(i, j, now + k * 0.025, c, 0);
      neighbours(graph, j).filter((m) => m !== i).slice(0, SECOND_FAN).forEach((m, q) => this._add(j, m, now + HOP_S * 0.9 + q * 0.05, c, 0));
    });
  }

  /** Idle thinking: now and then one pulse sets off along a random chain of links. */
  think(graph, now, every = 1.8) {
    if (now < this.nextThink || !graph.edges.length) return;
    this.nextThink = now + every * (0.6 + Math.random() * 0.8);
    const e = Math.floor(Math.random() * (graph.edges.length / 2)) * 2;
    const [a, b] = Math.random() < 0.5 ? [graph.edges[e], graph.edges[e + 1]] : [graph.edges[e + 1], graph.edges[e]];
    this._add(a, b, now, null, THINK_HOPS);
  }

  /** Move every pulse; onArrive(i) when a burst's pulse reaches its note. Returns how many still run. */
  update(now, disp, colours, graph, onArrive) {
    const P = this.pos, S = this.size, A = this.alpha, C = this.col;
    A.fill(0);
    const keep = [];
    for (const p of this.live) {
      const u = (now - p.t0) / p.dur;
      if (u >= 1) {
        if (!p.arrived && onArrive) onArrive(p.b, p.chain > 0);
        if (p.chain > 0) {                                     // thinking: hop on to a neighbour of where it landed
          const next = neighbours(graph, p.b).filter((m) => m !== p.a);
          if (next.length) this._add(p.b, next[Math.floor(Math.random() * next.length)], now, p.colour, p.chain - 1);
        }
        continue;
      }
      keep.push(p);
    }
    this.live = keep.slice(0, CAP);
    this.live.forEach((p, slot) => {
      const u = (now - p.t0) / p.dur;
      const c = p.colour || this._c.setRGB(colours[p.a * 3] * 0.5 + 0.5, colours[p.a * 3 + 1] * 0.5 + 0.5, colours[p.a * 3 + 2] * 0.5 + 0.5);
      for (let k = 0; k < TAIL; k++) {
        const o = slot * TAIL + k, q = Math.max(0, Math.min(1, u - k * 0.05)), e = q * q * (3 - 2 * q);
        for (let x = 0; x < 3; x++) P[o * 3 + x] = disp[p.a * 3 + x] + (disp[p.b * 3 + x] - disp[p.a * 3 + x]) * e;
        S[o] = (k === 0 ? 6.5 : 4.5 - k) * (p.chain > 0 ? 0.75 : 1);
        A[o] = u < 0 ? 0 : Math.sin(Math.PI * Math.min(1, u * 1.05)) * (1 - k / TAIL) * (p.chain > 0 ? 0.55 : 1);
        C[o * 3] = c.r; C[o * 3 + 1] = c.g; C[o * 3 + 2] = c.b;
      }
    });
    const at = this.points.geometry.attributes;
    at.position.needsUpdate = at.aSize.needsUpdate = at.aAlpha.needsUpdate = at.aColor.needsUpdate = true;
    return this.live.length;
  }
}

/** Every note linked to or from note i (cached per graph). */
function neighbours(graph, i) {
  if (!graph._adj) {
    const adj = graph.nodes.map(() => []), E = graph.edges;
    for (let e = 0; e < E.length; e += 2) { adj[E[e]].push(E[e + 1]); adj[E[e + 1]].push(E[e]); }
    graph._adj = adj;
  }
  return graph._adj[i] || [];
}
