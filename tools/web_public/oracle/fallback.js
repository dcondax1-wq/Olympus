// A usable city view when WebGL is unavailable. This 2D canvas remains read-only
// and keeps Oracle's HUD and replay working on software-only browsers.
const fract = (x) => x - Math.floor(x);
const rand = (n) => fract(Math.sin(n * 127.1 + 53.7) * 43758.5453);

export class FallbackCity {
  constructor(canvas, reduced) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.reduced = reduced;
    this.world = null;
    this.last = -Infinity;
    this.buildings = [];
    for (let z = 0; z < 11; z++) for (let x = 0; x < 15; x++) {
      if ((x === 7 && z > 1) || (z === 5 && x > 2 && x < 13)) continue;
      // Two small buildings per plot make the fallback read like the reference
      // night skyline while the clear cross streets still frame the radar.
      for (let sub = 0; sub < 2; sub++) {
        const n = x + z * 15 + sub * 165;
        this.buildings.push({ x: x + sub * .42, z: z + (sub ? .22 : .04),
          h: 14 + rand(n + 7) * 54 + (n % 23 === 0 ? 40 : 0),
          width: 0.43 + rand(n + 3) * .15, light: rand(n + 11) });
      }
    }
    this.buildings.sort((a, b) => a.x + a.z - b.x - b.z);
    this.resize();
  }

  setWorld(w) { this.world = w; this.last = -Infinity; }
  resize() {
    const dpr = Math.min(1.5, devicePixelRatio || 1);
    this.w = this.canvas.clientWidth || innerWidth;
    this.h = this.canvas.clientHeight || innerHeight;
    this.canvas.width = Math.round(this.w * dpr);
    this.canvas.height = Math.round(this.h * dpr);
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    this.last = -Infinity;
  }

  frame(t) {
    if (t - this.last < (this.reduced ? 10000 : 55)) return;
    this.last = t;
    const c = this.ctx, W = this.w, H = this.h;
    // Fill the phone viewport beneath Oracle's HUD: the former half-scale
    // footprint read as a small diagram instead of a city at 390px wide.
    const scale = Math.min(W / 12, H / 24), cx = W * 0.51, cy = H * 0.70;
    const project = (x, z) => ({ x: cx + (x - z - 2) * scale * 0.7,
      y: cy + (x + z - 11) * scale * 0.27 });
    const sky = c.createLinearGradient(0, 0, 0, H);
    sky.addColorStop(0, '#040711'); sky.addColorStop(.55, '#111b36'); sky.addColorStop(1, '#060710');
    c.fillStyle = sky; c.fillRect(0, 0, W, H);
    const halo = c.createRadialGradient(W * .53, H * .42, 4, W * .53, H * .42, W * .55);
    halo.addColorStop(0, 'rgba(60,163,225,.22)'); halo.addColorStop(1, 'rgba(12,19,43,0)');
    c.fillStyle = halo; c.fillRect(0, 0, W, H);
    c.save(); c.translate(cx, cy);
    c.strokeStyle = 'rgba(86,191,232,.16)'; c.lineWidth = 1;
    for (let i = -18; i < 19; i++) {
      c.beginPath(); c.moveTo(-W, i * scale * .55); c.lineTo(W, i * scale * .55); c.stroke();
    }
    c.restore();
    // Footprint roads frame the city and lead to the market observatory.
    for (let i = 0; i < 11; i++) {
      const a = project(7, i), b = project(8, i);
      c.strokeStyle = 'rgba(105,225,255,.18)';
      c.lineWidth = Math.max(2, scale * .26);
      c.beginPath(); c.moveTo(a.x, a.y); c.lineTo(b.x, b.y); c.stroke();
    }
    for (const b of this.buildings) {
      const p = project(b.x, b.z), size = scale * b.width * .56, rise = b.h * scale * .047;
      if (p.x < -size * 3 || p.x > W + size * 3 || p.y < -rise - 30 || p.y > H + 30) continue;
      const x = p.x, y = p.y, top = y - rise;
      c.fillStyle = b.light > .22 ? 'rgba(237,91,18,.34)' : 'rgba(19,184,94,.32)';
      c.beginPath(); c.moveTo(x - size * .7, y + size * .05);
      c.lineTo(x + size * .8, y - size * .55); c.lineTo(x + size * 2.5, y + size * .03);
      c.lineTo(x + size * .8, y + size * .63); c.closePath(); c.fill();
      c.fillStyle = b.light > .86 ? '#41435b' : '#252b43';
      c.beginPath(); c.moveTo(x, top); c.lineTo(x + size, top - size * .33);
      c.lineTo(x + size * 1.8, top); c.lineTo(x + size * .8, top + size * .33);
      c.closePath(); c.fill();
      const face = c.createLinearGradient(x, top, x + size * 2, y);
      face.addColorStop(0, b.light > .86 ? '#343c5c' : '#20283d');
      face.addColorStop(1, '#080c1b');
      c.fillStyle = face;
      c.beginPath(); c.moveTo(x, top); c.lineTo(x + size * .8, top + size * .33);
      c.lineTo(x + size * .8, y + size * .33); c.lineTo(x, y); c.closePath(); c.fill();
      c.fillStyle = '#11182b';
      c.beginPath(); c.moveTo(x + size * .8, top + size * .33); c.lineTo(x + size * 1.8, top);
      c.lineTo(x + size * 1.8, y); c.lineTo(x + size * .8, y + size * .33); c.closePath(); c.fill();
      c.strokeStyle = b.light > .18 ? 'rgba(255,159,72,.72)' : 'rgba(72,227,157,.72)';
      c.lineWidth = Math.max(1, size * .09);
      c.beginPath(); c.moveTo(x + size * .81, top + size * .45); c.lineTo(x + size * .81, y + size * .12); c.stroke();
      for (let row = 1; row < Math.min(11, rise / 6); row++) {
        if (rand(b.x * 31 + b.z * 71 + row) < .20) continue;
        const yy = top + row * rise / 10;
        c.fillStyle = b.light > .18 ? 'rgba(255,161,43,.95)' : 'rgba(61,248,139,.9)';
        c.fillRect(x + size * .17, yy + size * .17, Math.max(1, size * .16), Math.max(1, size * .13));
        c.fillRect(x + size * 1.14, yy, Math.max(1, size * .16), Math.max(1, size * .13));
      }
    }
    // Decorative skyways sit above the roofline; market routes below use
    // separate world levels and cannot be confused with these fixed arcs.
    for (const [color, lift, z] of [['rgba(255,154,65,.72)', 62, 2], ['rgba(72,227,157,.66)', 82, 5], ['rgba(132,199,255,.55)', 47, 8]]) {
      const a = project(1, z), b = project(13, z);
      c.strokeStyle = color; c.lineWidth = 1.6; c.beginPath();
      for (let k = 0; k <= 32; k++) {
        const t = k / 32, x = a.x + (b.x - a.x) * t, y = a.y + (b.y - a.y) * t - Math.sin(t * Math.PI) * lift;
        if (!k) c.moveTo(x, y); else c.lineTo(x, y);
      }
      c.stroke();
    }
    const core = project(7, 5), glow = c.createRadialGradient(core.x, core.y - 25, 2, core.x, core.y - 25, scale * 5);
    glow.addColorStop(0, 'rgba(101,238,255,.43)'); glow.addColorStop(1, 'rgba(40,118,210,0)');
    c.fillStyle = glow; c.fillRect(core.x - scale * 5, core.y - scale * 5, scale * 10, scale * 10);
    c.strokeStyle = '#9aeaff'; c.lineWidth = 2;
    c.beginPath(); c.ellipse(core.x, core.y, scale * 1.6, scale * .55, 0, 0, Math.PI * 2); c.stroke();
    c.strokeStyle = '#7ee6ff'; c.lineWidth = 3;
    c.beginPath(); c.moveTo(core.x, core.y); c.lineTo(core.x, core.y - scale * 6); c.stroke();
    const levels = (this.world && this.world.levels || []).filter(l => !l.taken).slice(0, 4);
    levels.forEach((l, i) => {
      const p = project(3 + i * 3, 2 + (i % 2) * 7);
      const lift = 16 + i * 7;
      c.strokeStyle = l.dist >= 0 ? '#7fe9ff' : '#dba5ff';
      // Read-only light conduits keep the observatory and the open level
      // pillars connected even when WebGL is unavailable.
      c.lineWidth = 1.5;
      c.beginPath(); c.moveTo(core.x, core.y); c.lineTo(p.x, p.y); c.stroke();
      c.beginPath(); c.ellipse(p.x, p.y, scale * .38, scale * .15, 0, 0, Math.PI * 2); c.stroke();
      c.lineWidth = 2;
      c.beginPath(); c.moveTo(p.x, p.y); c.lineTo(p.x, p.y - lift); c.stroke();
      c.fillStyle = c.strokeStyle;
      c.beginPath(); c.arc(p.x, p.y - lift, 3.5, 0, Math.PI * 2); c.fill();
    });
    c.fillStyle = 'rgba(170,222,247,.85)';
    c.font = '600 11px Rajdhani, sans-serif';
    c.textAlign = 'center';
    c.fillText('ORACLE · DELPHI', core.x, core.y - scale * 7);
  }
}

