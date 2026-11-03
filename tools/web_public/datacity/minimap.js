// The minimap: every district as a square in its sign colour, the plaza, the harbor, the watched buildings, and the
// camera with its view wedge. Redrawn a few times a second (never in the frame loop's hot path); a tap reports the world
// point and the district under it.
const SIZE = 112;            // CSS px

export class Minimap {
  /** canvas: the <canvas>; L: layout(); onPick(x, z, district|null) */
  constructor(canvas, L, onPick) {
    this.c = canvas; this.L = L; this.onPick = onPick;
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    canvas.width = canvas.height = Math.round(SIZE * dpr);
    canvas.style.width = canvas.style.height = SIZE + 'px';
    this.g = canvas.getContext('2d');
    this.g.scale(dpr, dpr);
    const b = L.bounds, pad = 12;
    this.span = Math.max(b.x1 - b.x0, b.z1 - b.z0) + pad * 2;
    this.cx = (b.x0 + b.x1) / 2; this.cz = (b.z0 + b.z1) / 2;
    this.pins = [];
    this.t = 0;
    canvas.addEventListener('click', (e) => {
      const r = canvas.getBoundingClientRect();
      const [x, z] = this.toWorld(e.clientX - r.left, e.clientY - r.top);
      const d = L.districts.find((q) => Math.abs(q.cx - x) <= (q.wide ? q.w / 2 : q.half) && Math.abs(q.cz - z) <= q.half) || null;
      onPick(x, z, d);
    });
  }

  toMap(x, z) { return [((x - this.cx) / this.span + 0.5) * SIZE, ((z - this.cz) / this.span + 0.5) * SIZE]; }
  toWorld(px, py) { return [(px / SIZE - 0.5) * this.span + this.cx, (py / SIZE - 0.5) * this.span + this.cz]; }

  /** camera: THREE camera; target: what it looks at */
  draw(camera, target, dt = 1) {
    this.t += dt;
    if (this.t < 0.2) return;
    this.t = 0;
    const g = this.g, s = SIZE / this.span;
    g.clearRect(0, 0, SIZE, SIZE);
    g.fillStyle = 'rgba(6,8,20,.72)';
    g.fillRect(0, 0, SIZE, SIZE);
    for (const d of this.L.districts) {
      const [x, y] = this.toMap(d.cx, d.cz), hw = (d.wide ? d.w / 2 : d.half) * s, hh = d.half * s;
      g.fillStyle = d.css + (d.kind === 'harbor' ? '33' : '55');
      g.strokeStyle = d.css;
      g.lineWidth = 1;
      g.fillRect(x - hw, y - hh, hw * 2, hh * 2);
      g.strokeRect(x - hw, y - hh, hw * 2, hh * 2);
    }
    const [px, py] = this.toMap(0, 0);
    g.fillStyle = '#3fd8ff';
    g.beginPath(); g.arc(px, py, Math.max(2, this.L.plazaR * s * 0.5), 0, Math.PI * 2); g.fill();
    g.fillStyle = '#ffd36b';
    for (const [x, z] of this.pins) { const [a, b] = this.toMap(x, z); g.fillRect(a - 1.5, b - 1.5, 3, 3); }
    const [cx, cy] = this.toMap(camera.position.x, camera.position.z), [tx, ty] = this.toMap(target.x, target.z);
    const a = Math.atan2(ty - cy, tx - cx), fov = 0.55;
    g.fillStyle = 'rgba(255,255,255,.16)';
    g.beginPath(); g.moveTo(cx, cy); g.arc(cx, cy, 34, a - fov, a + fov); g.closePath(); g.fill();
    g.fillStyle = '#fff';
    g.beginPath(); g.arc(Math.max(3, Math.min(SIZE - 3, cx)), Math.max(3, Math.min(SIZE - 3, cy)), 3, 0, Math.PI * 2); g.fill();
  }
}
