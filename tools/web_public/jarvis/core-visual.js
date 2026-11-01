// Jarvis core: the animated centrepiece of Jarvis mode. One 2D canvas, no libraries, no network: an arc-reactor HUD
// (graduated rings, segmented arcs, a scanning comet, reactor coils, a waveform ring, orbiting electrons, particles,
// glow and small data glyphs).
//   mountCore(el, {size}) -> {setState(s), setLevel(v), destroy()}      (+ stats() for the demo and the tests)
//   idle       calm breathing, slow drift
//   listening  the rings react to the level, ripples fall inward, the tick ring lights like a meter
//   thinking   fast orbit: rings spin, electrons whirl on three orbits, particles stream
//   speaking   a waveform pulse around the core, ripples thrown outward with the voice
//   alert      red / amber flare, strobing segments, warning marks, shock waves
// setLevel(0..1) drives the voice pulse; without calls for 0.6 s a built-in envelope per state keeps it alive.
// Crisp on retina (devicePixelRatio, max 2). Drops detail when frames run slow. Pauses when the page is hidden or the
// core is off-screen. Under prefers-reduced-motion it draws one static frame per state and never loops.
// iPhone Safari 16 safe: no conic gradients, no roundRect, no newer syntax.

const STATES = ['idle', 'listening', 'thinking', 'speaking', 'alert'];
const WORD = ['STANDBY', 'LISTENING', 'THINKING', 'SPEAKING', 'ALERT'];
const TAU = Math.PI * 2;
// palette per state: [rings, accent, core] (rgb)
const PAL = [
  [[56, 196, 255], [140, 228, 255], [222, 247, 255]],
  [[36, 232, 208], [150, 255, 232], [224, 255, 247]],
  [[112, 120, 255], [198, 138, 255], [236, 230, 255]],
  [[86, 220, 255], [255, 234, 196], [255, 251, 242]],
  [[255, 52, 44], [255, 164, 36], [255, 224, 196]],
];
// per state: [spin, scan rev/s, breath, wave gain, particle speed, brightness]
const PRM = [
  [1, 0.09, 1, 0.1, 1, 0.9],
  [1.6, 0.2, 0.3, 0.45, 1.4, 1],
  [7, 1.4, 0.15, 0.08, 7, 1],
  [1.8, 0.3, 0.2, 1, 2, 1.1],
  [3, 0.7, 0, 0.3, 3.5, 1.15],
];
const SEG = [0, 0.19, 0.23, 0.07, 0.34, 0.15, 0.53, 0.04, 0.61, 0.2, 0.85, 0.1];   // segmented ring: start, length (turns)
// detail per tier (0 = leanest): particles, waveform bars, ticks
const NP = [24, 50, 90, 150], NB = [36, 48, 72, 96], NT = [60, 72, 120, 120];
const STATIC_L = [0.08, 0.5, 0.35, 0.75, 0.6];         // the level shown in the reduced-motion frame
const clamp = (v, a, b) => (v < a ? a : v > b ? b : v);

export function mountCore(el, opts) {
  if (!el || !el.appendChild) throw new TypeError('mountCore(el): an element is required');
  const size = opts && +opts.size > 0 ? +opts.size : 0;
  const fixed = opts && opts.detail >= 0 && opts.detail <= 3 ? opts.detail | 0 : -1;   // optional: pin the detail tier
  const cv = document.createElement('canvas');
  cv.setAttribute('aria-hidden', 'true');
  cv.style.cssText = 'display:block;margin:0 auto;max-width:100%;height:auto;aspect-ratio:1/1;width:' + (size ? size + 'px' : '100%');
  el.appendChild(cv);
  const g = cv.getContext('2d');
  const mq = window.matchMedia ? window.matchMedia('(prefers-reduced-motion: reduce)') : null;
  let reduced = !!(mq && mq.matches), dead = false, raf = 0, last = 0, t = 0, onScreen = true;
  let S = 0, dpr = 1, tier = fixed < 0 ? 3 : fixed, st = 0, lvIn = 0, lvAt = -1e9, L = 0, flareAt = -9, hex = 0x3a7, frames = 0;
  let acc = 0, nAcc = 0, good = 0, drops = 0, warm = 0, fps = 0, rAcc = 0;
  const W = [1, 0, 0, 0, 0], P = [0, 0, 0, 0, 0, 0], C = [[0, 0, 0], [0, 0, 0], [0, 0, 0]];
  const rot = [0, 0, 0, 0, 0, 0, 0], orb = [0, 2.1, 4.2], rip = [];
  // particles (seeded: the same sky every mount)
  let seed = 7;
  const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
  const N = NP[3], pr = new Float32Array(N), pa = new Float32Array(N), pw = new Float32Array(N), ps = new Float32Array(N), pp = new Float32Array(N);
  for (let i = 0; i < N; i++) {
    pr[i] = 0.3 + 0.7 * rnd(); pa[i] = rnd() * TAU; pw[i] = (0.04 + 0.22 * rnd()) * (rnd() < 0.7 ? 1 : -1);
    ps[i] = 0.6 + 1.5 * rnd(); pp[i] = rnd() * TAU;
  }
  const col = (c, a) => 'rgba(' + (c[0] | 0) + ',' + (c[1] | 0) + ',' + (c[2] | 0) + ',' + clamp(a, 0, 1).toFixed(3) + ')';

  // ---------------------------------------------------------------- size, visibility, motion preference
  function fit() {
    const w = cv.clientWidth || size || 300, d = Math.min(2, window.devicePixelRatio || 1) * (tier ? 1 : 0.75);
    const px = Math.max(1, Math.round(w * d));
    if (cv.width !== px) cv.width = cv.height = px;
    S = w; dpr = px / w;
  }
  const live = () => !dead && !reduced && !document.hidden && onScreen;
  function kick() {
    if (live()) { if (!raf) { last = 0; raf = requestAnimationFrame(frame); } }
    else if (raf) { cancelAnimationFrame(raf); raf = 0; }
  }
  function still() {                      // reduced motion: snap to the state, draw one frame
    for (let i = 0; i < 5; i++) W[i] = i === st ? 1 : 0;
    L = STATIC_L[st]; t = 1.9; flareAt = -9; rip.length = 0; blend(); fit(); draw();
  }
  const onVis = () => kick();
  const onMq = () => { reduced = !!mq.matches; if (reduced) { kick(); still(); } else kick(); };
  document.addEventListener('visibilitychange', onVis);
  if (mq) { if (mq.addEventListener) mq.addEventListener('change', onMq); else if (mq.addListener) mq.addListener(onMq); }
  const io = typeof IntersectionObserver === 'function' ? new IntersectionObserver((es) => { onScreen = es[es.length - 1].isIntersecting; kick(); }) : null;
  if (io) io.observe(cv);
  const resized = () => { const w = cv.clientWidth; if (!w || Math.abs(w - S) < 0.5) return; if (reduced) still(); else fit(); };
  const ro = typeof ResizeObserver === 'function' ? new ResizeObserver(resized) : null;
  if (ro) ro.observe(cv);

  // ---------------------------------------------------------------- per frame
  function frame(now) {
    raf = 0;
    if (!live()) return;
    let ms = last ? now - last : 16.7;
    last = now;
    if (ms > 250) ms = 16.7; else adapt(ms);
    step(Math.min(ms, 50) / 1000);
    draw();
    raf = requestAnimationFrame(frame);
  }
  // quality: every 30 frames look at the mean frame time; under ~45 fps drop a tier, steady 58+ fps for ~3 s climbs back
  function adapt(ms) {
    if (warm < 20) { warm++; return; }
    acc += ms; nAcc++;
    if (nAcc < 30) return;
    const avg = acc / nAcc; acc = nAcc = 0; fps = Math.round(1000 / avg);
    if (fixed >= 0) return;
    if (avg > 22 && tier > 0) { tier--; drops++; good = 0; fit(); }
    else if (avg < 17.5 && tier < 3 && drops < 4) { if (++good >= 6) { tier++; good = 0; fit(); } }
    else good = 0;
  }
  function blend() {
    for (let k = 0; k < 6; k++) { let v = 0; for (let i = 0; i < 5; i++) v += W[i] * PRM[i][k]; P[k] = v; }
    for (let c = 0; c < 3; c++) for (let j = 0; j < 3; j++) { let v = 0; for (let i = 0; i < 5; i++) v += W[i] * PAL[i][c][j]; C[c][j] = v; }
  }
  function synth() {                      // a built-in level per state when the page sends none
    const syl = Math.max(0, Math.sin(t * 7.3)) * (0.6 + 0.4 * Math.sin(t * 1.7)), pause = Math.sin(t * 0.6) > -0.6 ? 1 : 0.15;
    return clamp(W[0] * (0.06 + 0.04 * Math.sin(t * 1.3))
      + W[1] * (0.32 + 0.22 * Math.sin(t * 5.1) * Math.sin(t * 2.3) + 0.08 * Math.sin(t * 13))
      + W[2] * (0.35 + 0.1 * Math.sin(t * 2.2))
      + W[3] * (0.12 + 0.8 * syl * pause) * (0.85 + 0.15 * Math.sin(t * 23))
      + W[4] * (0.45 + 0.55 * Math.pow(Math.max(0, Math.sin(t * TAU * 1.25)), 4)), 0, 1);
  }
  function step(dt) {
    t += dt;
    const k = 1 - Math.exp(-dt * 8);
    let sum = 0;
    for (let i = 0; i < 5; i++) { W[i] += ((i === st ? 1 : 0) - W[i]) * k; sum += W[i]; }
    for (let i = 0; i < 5; i++) W[i] /= sum;
    blend();
    const want = performance.now() - lvAt < 600 ? lvIn : synth();
    L += (want - L) * (1 - Math.exp(-dt * (want > L ? 30 : 7)));
    const sp = P[0] * dt;
    rot[0] -= sp * 0.02; rot[1] += sp * 0.05; rot[2] += sp * 0.11; rot[3] -= sp * 0.08; rot[4] += sp * 0.16; rot[5] -= sp * 0.3;
    rot[6] += dt * P[1] * TAU;
    for (let i = 0; i < 3; i++) orb[i] += dt * (2.2 + i * 0.7) * (0.3 + W[2]);
    const pv = P[4] * dt;
    for (let i = 0; i < N; i++) pa[i] += pw[i] * pv;
    hex = (hex + dt * (3 + 60 * W[2] + 8 * W[4])) % 65536;
    // ripples: inward while listening, outward while speaking, a shock wave per beat on alert
    rAcc += dt * (W[1] * (0.3 + 2 * L) + W[3] * (0.25 + 2.6 * L) + W[4] * 1.25);
    if (rAcc >= 1) { rAcc = 0; ring(st === 1 ? -1 : 1, 0.45 + 0.55 * L); }
    while (rip.length && t - rip[0][0] > 1.3) rip.shift();
  }
  function ring(dir, s) { rip.push([t, dir, s]); if (rip.length > 8) rip.shift(); }

  // ---------------------------------------------------------------- drawing
  function glow(c, a, w) {                // stroke the current path with a soft bloom under a crisp line
    if (tier > 2) { g.lineWidth = w * 5; g.strokeStyle = col(c, a * 0.06); g.stroke(); }
    if (tier > 0) { g.lineWidth = w * 2.4; g.strokeStyle = col(c, a * 0.16); g.stroke(); }
    g.lineWidth = w; g.strokeStyle = col(c, a); g.stroke();
  }
  function circle(r) { g.beginPath(); g.arc(0, 0, r, 0, TAU); }
  function arcs(r, a0, list, scale) {     // several arcs in one path, no joining lines
    g.beginPath();
    for (let i = 0; i < list.length; i += 2) {
      const s = a0 + list[i] * TAU, e = s + list[i + 1] * TAU * scale;
      g.moveTo(r * Math.cos(s), r * Math.sin(s)); g.arc(0, 0, r, s, e);
    }
  }
  function draw() {
    frames++;
    const d = dpr, R = S * 0.47, c0 = C[0], c1 = C[1], c2 = C[2];
    const wL = W[1], wT = W[2], wS = W[3], wA = W[4], gb = P[5];
    const br = (0.5 + 0.5 * Math.sin(t * TAU / 4.8)) * P[2];                   // idle breath
    const stb = wA * Math.pow(0.5 + 0.5 * Math.sin(t * TAU * 1.25), 6);        // alert strobe
    const fe = (t - flareAt) / 1.6, fl = wA * (fe >= 0 && fe < 1 ? (1 - fe) * (1 - fe) : 0);   // alert entry flare
    const lv = L * (wL + wS), hot = gb + 0.35 * lv + 0.5 * fl + 0.25 * stb;
    g.setTransform(1, 0, 0, 1, 0, 0);
    g.globalCompositeOperation = 'source-over';
    g.clearRect(0, 0, cv.width, cv.height);
    if (!S) return;
    g.setTransform(d, 0, 0, d, S * d / 2, S * d / 2);
    g.globalCompositeOperation = 'lighter';
    g.lineCap = 'butt';

    // halo + anamorphic streak
    let gr = g.createRadialGradient(0, 0, R * 0.08, 0, 0, R * 1.04);
    const ha = (0.14 + 0.06 * br + 0.16 * lv + 0.3 * fl + 0.1 * stb) * hot;
    gr.addColorStop(0, col(c0, ha)); gr.addColorStop(0.45, col(c0, ha * 0.32)); gr.addColorStop(1, col(c0, 0));
    g.fillStyle = gr; g.fillRect(-R * 1.04, -R * 1.04, R * 2.08, R * 2.08);
    g.save(); g.scale(1, 0.035);
    gr = g.createRadialGradient(0, 0, 0, 0, 0, R * 1.05);
    gr.addColorStop(0, col(c2, (0.35 + 0.3 * lv + 0.6 * fl) * hot)); gr.addColorStop(1, col(c0, 0));
    g.fillStyle = gr; g.fillRect(-R * 1.05, -R * 1.05, R * 2.1, R * 2.1);
    g.restore();

    // outer graduations; listening lights them like a meter rising from the bottom
    const nt = NT[tier], lit = L * (wL + 0.5 * wS);
    g.beginPath();
    const g2 = [];
    for (let i = 0; i < nt; i++) {
      const a = rot[0] + (i * TAU) / nt, m = i % 10 === 0 ? 0.075 : i % 5 === 0 ? 0.05 : 0.028;
      const ca = Math.cos(a), sa = Math.sin(a), r0 = R * 0.975, r1 = R * (0.975 - m);
      let u = Math.abs(((a - Math.PI / 2) % TAU + TAU) % TAU - Math.PI) / Math.PI;   // 1 at the bottom, 0 at the top
      if (1 - u < lit * 1.05 || (wA > 0.3 && i % 10 < 3)) g2.push(ca, sa, r0, r1);
      else { g.moveTo(r0 * ca, r0 * sa); g.lineTo(r1 * ca, r1 * sa); }
    }
    g.lineWidth = 1; g.strokeStyle = col(c0, 0.42 * gb); g.stroke();
    if (g2.length) {
      g.beginPath();
      for (let i = 0; i < g2.length; i += 4) { g.moveTo(g2[i + 2] * g2[i], g2[i + 2] * g2[i + 1]); g.lineTo(g2[i + 3] * g2[i], g2[i + 3] * g2[i + 1]); }
      glow(wA > 0.5 ? c1 : c2, 0.85 * (wA > 0.3 ? 0.35 + 0.65 * stb : 1), 1.4);
    }
    // cardinal notches outside the graduations
    g.beginPath();
    for (let i = 0; i < 4; i++) { const a = i * Math.PI / 2; g.moveTo(R * 1.0 * Math.cos(a - 0.05), R * 1.0 * Math.sin(a - 0.05)); g.arc(0, 0, R, a - 0.05, a + 0.05); }
    glow(c1, 0.7 * gb, 2);

    // thin ring with four gaps for the data glyphs
    const gapList = [0.035, 0.18, 0.285, 0.18, 0.535, 0.18, 0.785, 0.18];
    arcs(R * 0.885, rot[1], gapList, 1);
    glow(c0, 0.5 * gb, 1);
    if (tier > 1) {
      const fs = Math.max(7, R * 0.045);
      g.font = '600 ' + fs.toFixed(1) + 'px ui-monospace,SFMono-Regular,Menlo,monospace';
      g.textAlign = 'center'; g.textBaseline = 'middle'; g.fillStyle = col(c1, 0.8 * gb);
      let k = 0; for (let i = 1; i < 5; i++) if (W[i] > W[k]) k = i;
      const txt = [WORD[k], (hex | 0).toString(16).toUpperCase().padStart(4, '0'), 'LV ' + String(Math.round(L * 99)).padStart(2, '0'), 'J.A.R.V.I.S'];
      for (let i = 0; i < 4; i++) {
        const a = rot[1] + (i * 0.25) * TAU;
        g.save(); g.rotate(a + Math.PI / 2); g.fillText(txt[i], 0, -R * 0.885); g.restore();
      }
    }

    // segmented ring: listening thickens it with the level, alert strobes it amber
    arcs(R * (0.835 + 0.02 * L * wL), rot[2], SEG, 1);
    glow(stb > 0.5 ? c1 : c0, (0.62 + 0.3 * lv + 0.4 * stb) * gb, R * (0.022 + 0.018 * L * wL));
    // a fine counter-rotating ring just inside
    arcs(R * 0.8, rot[3], SEG, 0.6);
    glow(c0, 0.35 * gb, 1);

    // scanning comet (two in thinking)
    const nc = wT > 0.5 ? 2 : 1, rr = R * 0.775;
    for (let j = 0; j < nc; j++) {
      const h = rot[6] + j * Math.PI;
      for (let i = 0; i < 8; i++) {
        g.beginPath(); g.arc(0, 0, rr, h - (i + 1) * 0.2, h - i * 0.2);
        g.lineWidth = R * 0.012; g.strokeStyle = col(c2, (1 - i / 8) * (1 - i / 8) * 0.8 * gb); g.stroke();
      }
      g.beginPath(); g.arc(rr * Math.cos(h), rr * Math.sin(h), R * 0.012, 0, TAU); g.fillStyle = col(c2, 0.95); g.fill();
    }
    // dotted ring
    g.beginPath(); g.arc(0, 0, R * 0.745, rot[4], rot[4] + TAU);
    g.setLineDash([1, R * 0.03]); g.lineWidth = 1.6; g.strokeStyle = col(c1, 0.55 * gb); g.stroke(); g.setLineDash([]);

    // reactor coils: ten blocks, lit by the voice / strobing on alert
    const r0 = R * (0.62 + 0.02 * L * wL), r1 = R * (0.71 + 0.03 * L * (wL + wS));
    const coil = (i) => {
      const a = rot[3] * 1.5 + i * TAU / 10, b = a + TAU / 10 * 0.74;
      g.moveTo(r1 * Math.cos(a), r1 * Math.sin(a)); g.arc(0, 0, r1, a, b); g.arc(0, 0, r0, b, a, true); g.closePath();
    };
    for (let i = 0; i < 10; i++) {
      const on = wS * L * (0.5 + 0.5 * Math.sin(i * 1.9 + t * 7)) + wL * L * 0.5 + wA * ((i + Math.floor(t * 2.5)) % 2 ? stb : 0.1) + 0.06 + 0.04 * br;
      g.beginPath(); coil(i); g.fillStyle = col(wA > 0.5 && i % 2 ? c1 : c0, on * 0.55 * gb); g.fill();
    }
    g.beginPath();
    for (let i = 0; i < 10; i++) coil(i);
    glow(c0, 0.55 * gb, 1);
    circle(R * 0.585); g.lineWidth = 1; g.strokeStyle = col(c0, 0.3 * gb); g.stroke();

    // listening: three thin rings breathe with the level (out of step), the "ear" of the core
    if (wL > 0.02) {
      for (let i = 0; i < 3; i++) {
        const e = 0.5 + 0.5 * Math.sin(t * (3.1 + i * 1.7) + i * 2);
        circle(R * (0.455 + i * 0.05 + (0.025 + 0.02 * i) * L * e));
        glow(i === 1 ? c2 : c0, wL * (0.18 + 0.6 * L * e) * gb, 1);
      }
    }
    // waveform ring: a fine fringe at rest, the voice when speaking (a spectrum mirrored left / right, echoed inward)
    const nb = NB[tier], rb = R * (0.4 + 0.03 * br), amp = L * P[3];
    g.beginPath();
    const tips = [];
    for (let i = 0; i < nb; i++) {
      const a = -Math.PI / 2 + (i * TAU) / nb, m = Math.min(i, nb - i), q = m / (nb / 2), h = Math.sin(m * 12.9898) * 43758.5453 % 1;
      const s = (0.55 + 0.45 * Math.sin(q * 11 + t * 9.3) * Math.cos(q * 5.3 - t * 6.1)) * (0.55 + 0.45 * Math.sin(t * 13 + h * 40));
      const len = R * (0.012 + 0.24 * amp * s * (1.15 - 0.5 * q) + 0.03 * wT * (0.5 + 0.5 * Math.sin(i * 0.8 - t * 12)));
      const ca = Math.cos(a), sa = Math.sin(a), ri = rb - Math.min(len * 0.35, R * 0.05);
      g.moveTo(ri * ca, ri * sa); g.lineTo((rb + len) * ca, (rb + len) * sa);
      tips.push((rb + len) * ca, (rb + len) * sa);
    }
    g.lineCap = 'round';
    glow(wS > 0.5 ? c2 : c0, (0.55 + 0.4 * lv) * gb, Math.max(1, (TAU * rb / nb) * 0.38));
    g.lineCap = 'butt';
    if (tier > 1 && amp > 0.05) {
      g.beginPath(); g.moveTo(tips[0], tips[1]);
      for (let i = 2; i < tips.length; i += 2) g.lineTo(tips[i], tips[i + 1]);
      g.closePath(); g.lineWidth = 1; g.strokeStyle = col(c0, clamp(amp * 2, 0, 0.7) * gb); g.stroke();
    }

    // ripples
    for (let i = 0; i < rip.length; i++) {
      const [t0, dir, s] = rip[i], k = (t - t0) / 1.3;
      if (k < 0 || k > 1) continue;
      const e = 1 - (1 - k) * (1 - k) * (1 - k);
      circle(R * (dir > 0 ? 0.36 + 0.66 * e : 0.96 - 0.56 * e));
      glow(wA > 0.5 ? c0 : c2, s * (1 - k) * (1 - k) * 0.7, 1.5);
    }

    // orbiting electrons (thinking)
    if (wT > 0.02) {
      for (let i = 0; i < 3; i++) {
        const tilt = rot[5] * 0.3 + i * TAU / 3, rx = R * 0.56, ry = R * 0.17, ph = orb[i];
        g.beginPath(); g.ellipse(0, 0, rx, ry, tilt, 0, TAU); g.lineWidth = 1; g.strokeStyle = col(c1, 0.22 * wT); g.stroke();
        for (let j = 0; j < 4; j++) {
          g.beginPath(); g.ellipse(0, 0, rx, ry, tilt, ph - (j + 1) * 0.28, ph - j * 0.28);
          g.lineWidth = 2.2 - j * 0.4; g.strokeStyle = col(c2, (1 - j / 4) * 0.8 * wT); g.stroke();
        }
        const x = rx * Math.cos(ph), y = ry * Math.sin(ph), ct = Math.cos(tilt), sn = Math.sin(tilt);
        g.beginPath(); g.arc(x * ct - y * sn, x * sn + y * ct, R * 0.018, 0, TAU); g.fillStyle = col(c2, wT); g.fill();
      }
    }

    // particles: drifting motes, streaks when spinning fast
    const np = NP[tier], pull = 1 - 0.18 * L * wL, push = 0.14 * L * wS, trail = Math.min(0.5, P[4] * 0.05);
    for (let b = 0; b < 3; b++) {
      g.beginPath();
      for (let i = b; i < np; i += 3) {
        const r = R * pr[i] * (pull + push * (0.5 + 0.5 * Math.sin(pa[i] * 3 + t * 6)) + wA * 0.03 * Math.sin(t * 40 + i));
        if (trail > 0.12) {
          const a = pa[i], len = trail * Math.abs(pw[i]) * 3, a0 = pw[i] > 0 ? a - len : a;
          g.moveTo(r * Math.cos(a0), r * Math.sin(a0)); g.arc(0, 0, r, a0, a0 + len);
        }
        else { const z = ps[i] * (0.7 + 0.3 * gb); g.rect(r * Math.cos(pa[i]) - z / 2, r * Math.sin(pa[i]) - z / 2, z, z); }
      }
      const tw = 0.35 + 0.65 * (0.5 + 0.5 * Math.sin(t * (1.2 + b * 0.7) + b * 2.1));
      if (trail > 0.12) { g.lineWidth = 1.2; g.strokeStyle = col(b ? c0 : c2, tw * 0.75 * gb); g.stroke(); }
      else { g.fillStyle = col(b ? c0 : c2, tw * 0.8 * gb); g.fill(); }
    }

    // alert: warning marks on the diagonals
    if (wA > 0.02) {
      g.beginPath();
      for (let i = 0; i < 4; i++) {
        const a = Math.PI / 4 + i * Math.PI / 2, ca = Math.cos(a), sa = Math.sin(a), r = R * 0.94, z = R * 0.045;
        g.moveTo((r - z) * ca, (r - z) * sa); g.lineTo(r * ca - z * 0.7 * sa, r * sa + z * 0.7 * ca); g.lineTo(r * ca + z * 0.7 * sa, r * sa - z * 0.7 * ca); g.closePath();
      }
      g.fillStyle = col(c1, wA * (0.3 + 0.7 * stb)); g.fill();
    }

    // core: lens ring, inner ring, white-hot centre
    const cr = R * (0.33 + 0.02 * br + 0.05 * L * (wS + 0.6 * wL) + 0.05 * fl);
    circle(cr); glow(c0, (0.85 + 0.15 * lv) * gb, R * 0.016);
    if (wT > 0.02) {                      // thinking: two bright arcs race round the lens ring
      g.beginPath();
      for (let j = 0; j < 2; j++) { const a = rot[6] * 1.7 + j * Math.PI; g.moveTo(cr * Math.cos(a), cr * Math.sin(a)); g.arc(0, 0, cr, a, a + 1.1); }
      glow(c2, wT, R * 0.022);
    }
    arcs(R * 0.22, -rot[4] * 1.4, [0, 0.13, 0.166, 0.13, 0.333, 0.13, 0.5, 0.13, 0.666, 0.13, 0.833, 0.13], 1);
    glow(c1, 0.6 * gb, R * 0.01);
    gr = g.createRadialGradient(0, 0, 0, 0, 0, cr * 1.15);
    const ci = clamp((0.75 + 0.25 * br + 0.45 * lv + 0.8 * fl + 0.4 * stb) * gb, 0, 1.4);
    gr.addColorStop(0, col(c2, ci)); gr.addColorStop(0.18, col(c2, ci * 0.85)); gr.addColorStop(0.45, col(c0, ci * 0.4)); gr.addColorStop(1, col(c0, 0));
    g.fillStyle = gr; g.fillRect(-cr * 1.15, -cr * 1.15, cr * 2.3, cr * 2.3);
  }

  // ---------------------------------------------------------------- API
  fit(); blend();
  if (reduced) still(); else kick();
  return {
    setState(s) {
      const i = STATES.indexOf(s);
      if (dead || i < 0 || i === st) return;
      st = i;
      if (i === 4) flareAt = t;
      ring(1, i === 4 ? 1 : 0.5);
      if (reduced) still(); else kick();
    },
    setLevel(v) {
      if (dead) return;
      v = +v; lvIn = v > 0 ? (v > 1 ? 1 : v) : 0; lvAt = performance.now();
    },
    destroy() {
      if (dead) return;
      dead = true;
      if (raf) cancelAnimationFrame(raf);
      raf = 0;
      document.removeEventListener('visibilitychange', onVis);
      if (mq) { if (mq.removeEventListener) mq.removeEventListener('change', onMq); else if (mq.removeListener) mq.removeListener(onMq); }
      if (io) io.disconnect();
      if (ro) ro.disconnect();
      cv.remove();
    },
    stats: () => ({ state: STATES[st], level: +L.toFixed(3), tier, fps, frames, running: !!raf, reduced, dpr }),
  };
}
