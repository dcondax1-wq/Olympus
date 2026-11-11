// HERALD scene (ES module): a small marble newsstand whose scroll unrolls today's headline (three r160, ../jarvis/three.module.min.js, no post passes).
//   the stand    a plinth, two short columns and a low roof slab in marble, a bronze rail between the columns
//   the scroll   two bronze-capped rollers and an ivory sheet; show(kicker, lines) rolls it up and lets it fall open again with the new headline (900 ms, instant on reduced motion)
//   cost         it draws only while the scroll moves: a still stand costs nothing
// createStand(canvas, { O }) -> { show(kicker, lines), open(), frames(), dispose() } or null when WebGL is not available (the page then draws its flat scroll)
import * as THREE from '../jarvis/three.module.min.js';

const SW = 3.6, SH = 2.5;
const ease = (t) => 1 - Math.pow(1 - t, 3);

function sheetTexture(kicker, lines) {
  const c = document.createElement('canvas'); c.width = 720; c.height = 500;
  const g = c.getContext('2d');
  g.fillStyle = '#efe6d2'; g.fillRect(0, 0, 720, 500);
  g.strokeStyle = '#9c6b3c'; g.lineWidth = 3; g.strokeRect(18, 18, 684, 464); g.lineWidth = 1; g.strokeRect(28, 28, 664, 444);
  g.fillStyle = '#7a5a2c'; g.textAlign = 'center'; g.textBaseline = 'middle';
  g.font = '600 30px -apple-system, system-ui, sans-serif'; g.fillText(kicker || 'The Olympus Herald', 360, 78, 620);
  g.fillStyle = '#9c6b3c'; g.fillRect(250, 108, 220, 2);
  g.fillStyle = '#2a2217';
  const n = Math.max(1, lines.length), size = n <= 2 ? 68 : n === 3 ? 58 : 50, lh = size * 1.18, y0 = 290 - ((n - 1) * lh) / 2;
  g.font = `600 ${size}px 'Iowan Old Style', 'Palatino Linotype', Palatino, Georgia, serif`;
  lines.forEach((ln, i) => g.fillText(ln, 360, y0 + i * lh, 630));
  const t = new THREE.CanvasTexture(c); t.colorSpace = THREE.SRGBColorSpace; t.anisotropy = 4;
  return t;
}

export function createStand(canvas, { O = null } = {}) {
  let renderer;
  try { renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: 'low-power' }); } catch (_) { return null; }
  if (!renderer || !renderer.getContext || !renderer.getContext()) return null;
  const reduced = () => { try { return O ? O.reduced() : !!(window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches); } catch (_) { return false; } };
  renderer.setClearColor(0x000000, 0);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = 1.25;
  const scene = new THREE.Scene(), camera = new THREE.PerspectiveCamera(30, 1.4, 0.1, 60);
  scene.add(new THREE.HemisphereLight('#fff1d6', '#4a3a28', 1.2));
  const sun = new THREE.DirectionalLight('#ffd9a0', 1.6); sun.position.set(-4, 6, 7); scene.add(sun);
  const marble = new THREE.MeshStandardMaterial({ color: '#ece4d2', roughness: 0.5, metalness: 0 });
  const dark = new THREE.MeshStandardMaterial({ color: '#cfc5b0', roughness: 0.55, metalness: 0 });
  const bronze = new THREE.MeshStandardMaterial({ color: '#9c6b3c', roughness: 0.5, metalness: 0.25 });
  const gold = new THREE.MeshStandardMaterial({ color: '#c8a24a', roughness: 0.4, metalness: 0.3 });
  const made = [];
  const add = (geo, mat, x, y, z, parent) => { made.push(geo); const m = new THREE.Mesh(geo, mat); m.position.set(x, y, z); (parent || scene).add(m); return m; };
  add(new THREE.BoxGeometry(6.2, 0.26, 1.7), dark, 0, -1.95, 0);
  add(new THREE.BoxGeometry(5.6, 0.16, 1.4), marble, 0, -1.74, 0);
  for (const s of [-1, 1]) { add(new THREE.CylinderGeometry(0.2, 0.23, 3.5, 20), marble, s * 2.45, 0.08, 0); add(new THREE.BoxGeometry(0.62, 0.14, 0.62), dark, s * 2.45, 1.9, 0); add(new THREE.BoxGeometry(0.6, 0.12, 0.6), dark, s * 2.45, -1.62, 0); }
  add(new THREE.BoxGeometry(6.0, 0.2, 1.5), marble, 0, 2.07, 0);
  const ped = new THREE.Shape(); ped.moveTo(-3.1, 0); ped.lineTo(3.1, 0); ped.lineTo(0, 0.62); ped.closePath();
  const pg = new THREE.ExtrudeGeometry(ped, { depth: 1.5, bevelEnabled: false }); made.push(pg);
  const pm = new THREE.Mesh(pg, marble); pm.position.set(0, 2.17, -0.75); scene.add(pm);
  const medal = add(new THREE.CylinderGeometry(0.15, 0.15, 0.04, 24), gold, 0, 2.4, 0.78); medal.rotation.x = Math.PI / 2;
  // the scroll: the top roller hangs from the roof, the sheet falls from it, the bottom roller rides its lower edge
  const top = 1.55, rollGeo = new THREE.CylinderGeometry(0.1, 0.1, SW + 0.5, 16), capGeo = new THREE.SphereGeometry(0.14, 14, 10); made.push(rollGeo, capGeo);
  const roller = (y) => { const g = new THREE.Group(); const r = new THREE.Mesh(rollGeo, bronze); r.rotation.z = Math.PI / 2; g.add(r); for (const s of [-1, 1]) { const c = new THREE.Mesh(capGeo, gold); c.position.x = s * (SW / 2 + 0.25); g.add(c); } g.position.set(0, y, 0.2); scene.add(g); return g; };
  roller(top); const low = roller(top);
  const sheetGeo = new THREE.PlaneGeometry(SW, SH); sheetGeo.translate(0, -SH / 2, 0); made.push(sheetGeo);
  const sheetMat = new THREE.MeshBasicMaterial({ color: '#ffffff', toneMapped: false });
  const sheet = new THREE.Mesh(sheetGeo, sheetMat); sheet.position.set(0, top, 0.2); scene.add(sheet);
  let tex = null, pending = null, pos = 0, to = 0, raf = 0, stopped = false, frames = 0, dirty = true, last = 0;
  function swap() { if (!pending) return; if (tex) tex.dispose(); tex = sheetTexture(pending[0], pending[1]); sheetMat.map = tex; sheetMat.needsUpdate = true; pending = null; }
  function lay() {
    const e = Math.max(0.02, ease(pos)); sheet.scale.y = e; low.position.y = top - SH * e;
    if (tex) { tex.repeat.set(1, e); tex.offset.set(0, 1 - e); }                           // the sheet shows the top part of the page as it falls open, never a squashed one
  }
  function size() {
    const w = canvas.clientWidth || 320, h = canvas.clientHeight || 240, dpr = Math.min(window.devicePixelRatio || 1, 2);
    if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) { renderer.setPixelRatio(dpr); renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix(); dirty = true; }
    const dist = Math.max(3.5 / (Math.tan((camera.fov * Math.PI / 180) / 2) * camera.aspect), 2.75 / Math.tan((camera.fov * Math.PI / 180) / 2)) + 0.9;
    camera.position.set(0, 0.45, dist); camera.lookAt(0, 0.35, 0);
  }
  function step(dt) {
    if (pos === to) { if (to === 0 && pending) { swap(); to = 1; return true; } return false; }
    const k = reduced() ? 1 : dt / (to === 1 ? 0.9 : 0.35);
    pos = Math.abs(to - pos) <= k ? to : pos + Math.sign(to - pos) * k;
    return true;
  }
  function frame(now) {
    raf = requestAnimationFrame(frame);
    if (stopped || document.hidden) return;
    const dt = last ? Math.min(0.1, (now - last) / 1000) : 0.016; last = now;
    size();
    const moving = step(dt);
    if (!moving && !dirty) return;
    lay(); renderer.render(scene, camera); dirty = false; frames++;
  }
  raf = requestAnimationFrame(frame);
  return {
    show(kicker, lines) { pending = [String(kicker || ''), (lines || []).map(String)]; to = 0; dirty = true; if (reduced()) { pos = 0; swap(); pos = 1; to = 1; } },
    open: () => pos, frames: () => frames,
    dispose() { stopped = true; cancelAnimationFrame(raf); try { made.forEach((g) => g.dispose()); if (tex) tex.dispose(); renderer.dispose(); } catch (_) { /* gone */ } },
  };
}
