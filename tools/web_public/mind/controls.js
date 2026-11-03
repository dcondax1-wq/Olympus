// OLYMPUS Mind: the camera rig. Orbit around a target with one finger (or the mouse), pinch or wheel to zoom, a little
// inertia, a gentle ambient camera when idle (a slow orbit plus a soft breathing rise and dolly, eased in, never stored in the
// rig's own angles or radius), and eased flights to a point. Taps and double taps are reported (with the screen point),
// drags are not. Under reduced motion there is no drift, no inertia and flights take a moment instead of a second and a half.
//   new OrbitRig(camera, element, {reduced, onTap(x, y), onDoubleTap(x, y)}) -> rig.update(dt), rig.flyTo(point, radius)

const TAP_MOVE = 10, TAP_MS = 350, DOUBLE_MS = 340, IDLE_DRIFT_AFTER = 4, DRIFT = 0.045;
const BREATHE_PHI = 0.07, BREATHE_R = 0.035;              // the ambient sway: radians of rise, share of the radius
const ease = (t) => (t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2);

export class OrbitRig {
  constructor(camera, el, { reduced = false, onTap = () => {}, onDoubleTap = () => {} } = {}) {
    Object.assign(this, { camera, el, reduced, onTap, onDoubleTap });
    this.target = { x: 0, y: 0, z: 0 };
    this.theta = 0.6; this.phi = 1.15; this.radius = 600;
    this.minR = 20; this.maxR = 4000;
    this.vTheta = 0; this.vPhi = 0;
    this.idle = 0; this.flight = null; this.clock = 0; this.calm = 0;
    this.pointers = new Map(); this.pinch = 0; this.lastTap = null; this.down = null;
    el.addEventListener('pointerdown', (e) => this._down(e));
    el.addEventListener('pointermove', (e) => this._move(e));
    el.addEventListener('pointerup', (e) => this._up(e));
    el.addEventListener('pointercancel', (e) => this._up(e, true));
    el.addEventListener('wheel', (e) => { e.preventDefault(); this._zoom(Math.exp(e.deltaY * 0.0012)); }, { passive: false });
  }

  get busy() { return !!this.flight || this.pointers.size > 0 || Math.abs(this.vTheta) + Math.abs(this.vPhi) > 1e-4; }

  _down(e) {
    this.el.setPointerCapture?.(e.pointerId);
    this.pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
    this.flight = null; this.idle = 0; this.vTheta = this.vPhi = 0;
    if (this.pointers.size === 1) this.down = { x: e.clientX, y: e.clientY, t: performance.now(), moved: 0 };
    else { this.down = null; this.pinch = this._spread(); }
  }

  _move(e) {
    const p = this.pointers.get(e.pointerId);
    if (!p) return;
    const dx = e.clientX - p.x, dy = e.clientY - p.y;
    p.x = e.clientX; p.y = e.clientY;
    this.idle = 0;
    if (this.pointers.size >= 2) {
      const s = this._spread();
      if (this.pinch > 0 && s > 0) this._zoom(this.pinch / s);
      this.pinch = s;
      return;
    }
    if (this.down) this.down.moved += Math.abs(dx) + Math.abs(dy);
    const k = 4.2 / Math.max(320, this.el.clientHeight);
    this.vTheta = -dx * k; this.vPhi = -dy * k;
    this._turn(this.vTheta, this.vPhi);
  }

  _up(e, cancelled = false) {
    if (!this.pointers.has(e.pointerId)) return;
    this.pointers.delete(e.pointerId);
    if (this.pointers.size) { this.pinch = this._spread(); return; }
    const d = this.down;
    this.down = null;
    if (this.reduced) this.vTheta = this.vPhi = 0;
    if (cancelled || !d || d.moved > TAP_MOVE || performance.now() - d.t > TAP_MS) return;
    this.vTheta = this.vPhi = 0;
    const now = performance.now(), last = this.lastTap;
    if (last && now - last.t < DOUBLE_MS && Math.hypot(e.clientX - last.x, e.clientY - last.y) < 30) {
      this.lastTap = null;
      this.onDoubleTap(e.clientX, e.clientY);
    } else {
      this.lastTap = { t: now, x: e.clientX, y: e.clientY };
      this.onTap(e.clientX, e.clientY);
    }
  }

  _spread() {
    const [a, b] = [...this.pointers.values()];
    return a && b ? Math.hypot(a.x - b.x, a.y - b.y) : 0;
  }

  _turn(dTheta, dPhi) {
    this.theta += dTheta;
    this.phi = Math.min(Math.PI - 0.12, Math.max(0.12, this.phi + dPhi));
  }

  _zoom(f) {
    this.flight = null;
    this.radius = Math.min(this.maxR, Math.max(this.minR, this.radius * f));
  }

  /** Fly to look at `point` from `radius` (keeps the viewing angle). */
  flyTo(point, radius, seconds = 1.5) {
    this.flight = {
      t: 0, dur: this.reduced ? 0.01 : seconds,
      from: { ...this.target, r: this.radius },
      to: { x: point.x, y: point.y, z: point.z, r: Math.min(this.maxR, Math.max(this.minR, radius)) },
    };
    this.vTheta = this.vPhi = 0;
  }

  update(dt) {
    this.idle += dt; this.clock += dt;
    if (this.flight) {
      const f = this.flight;
      f.t = Math.min(1, f.t + dt / f.dur);
      const k = ease(f.t);
      this.target.x = f.from.x + (f.to.x - f.from.x) * k;
      this.target.y = f.from.y + (f.to.y - f.from.y) * k;
      this.target.z = f.from.z + (f.to.z - f.from.z) * k;
      // zoom out a little mid-flight for a cinematic arc
      const lift = this.reduced ? 0 : Math.sin(Math.PI * k) * 0.25 * Math.max(f.from.r, f.to.r);
      this.radius = f.from.r + (f.to.r - f.from.r) * k + lift;
      if (f.t >= 1) this.flight = null;
    } else if (!this.pointers.size && !this.reduced) {
      if (Math.abs(this.vTheta) + Math.abs(this.vPhi) > 1e-5) {
        this._turn(this.vTheta, this.vPhi);
        const keep = Math.exp(-dt * 5);
        this.vTheta *= keep; this.vPhi *= keep;
      } else if (this.idle > IDLE_DRIFT_AFTER) {
        this.theta += DRIFT * dt * Math.min(1, (this.idle - IDLE_DRIFT_AFTER) / 2);
      }
    }
    // the ambient sway fades in after the idle wait and out at once on a touch or a flight
    const want = !this.reduced && !this.flight && !this.pointers.size && this.idle > IDLE_DRIFT_AFTER ? 1 : 0;
    this.calm += (want - this.calm) * Math.min(1, dt * (want ? 0.6 : 6));
    const phi = Math.min(Math.PI - 0.12, Math.max(0.12, this.phi + this.calm * BREATHE_PHI * Math.sin(this.clock * 0.11)));
    const s = Math.sin(phi), t = this.target, r = this.radius * (1 + this.calm * BREATHE_R * Math.sin(this.clock * 0.07 + 1.3));
    this.camera.position.set(t.x + r * s * Math.sin(this.theta), t.y + r * Math.cos(phi), t.z + r * s * Math.cos(this.theta));
    this.camera.lookAt(t.x, t.y, t.z);
  }
}
