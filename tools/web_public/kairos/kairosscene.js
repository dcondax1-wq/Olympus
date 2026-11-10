// KAIROS scene (ES module): a marble sundial ring. Twenty-four gold pillars stand round a marble ring, one for each New York hour, midnight at the far side and clockwise like the 2D ring.
// The current hour's pillar is lit (warm emissive, taller) and a gold hand points at the minute. Hours the bots may enter (02:00 to 15:30) stand a little taller than the quiet ones.
// Warm sun, no bloom, one small mesh set: light on a phone, still on reduced motion, a LITE tier with fewer segments. No WebGL -> createSundial returns null (the page then shows the flat ring only).
// createSundial(canvas, { O }) -> { set(mod), hour(), lit(), dispose() }   mod = minutes since midnight New York
import * as THREE from '../jarvis/three.module.min.js';

export const hourOf = (mod) => Math.floor((((mod % 1440) + 1440) % 1440) / 60);
export const pillarHeight = (h) => (h >= 2 && h < 16 ? 0.95 : 0.6);          // the entry hours (02:00 to 15:30) stand taller

export function createSundial(canvas, { O = null } = {}) {
  let renderer;
  try { renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: 'low-power' }); } catch (_) { return null; }
  if (!renderer || !renderer.getContext || !renderer.getContext()) return null;
  const reduced = () => { try { return O ? O.reduced() : !!(window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches); } catch (_) { return false; } };
  const lite = () => { try { return !!(O && O.lite && O.lite()); } catch (_) { return false; } };
  renderer.setClearColor(0x000000, 0); renderer.outputColorSpace = THREE.SRGBColorSpace;
  const scene = new THREE.Scene(), camera = new THREE.PerspectiveCamera(34, 1, 0.1, 60);
  scene.add(new THREE.HemisphereLight('#f0dcb4', '#3a2c1e', 0.9));
  const sun = new THREE.DirectionalLight('#ffd9a0', 1.4); sun.position.set(-5, 8, 5); scene.add(sun);
  const marble = new THREE.MeshStandardMaterial({ color: '#d8cdb8', roughness: 0.42, metalness: 0.05 });
  const bronze = new THREE.MeshStandardMaterial({ color: '#9c6b3c', roughness: 0.45, metalness: 0.7 });
  const seg = lite() ? 40 : 72;
  const group = new THREE.Group(); scene.add(group);
  const disc = new THREE.Mesh(new THREE.LatheGeometry([[0.5, 0], [3.4, 0], [3.5, 0.12], [3.3, 0.3], [2.1, 0.3], [2.0, 0.12], [0.5, 0.12]].map(([r, y]) => new THREE.Vector2(r, y)), seg), marble); group.add(disc);
  const rim = new THREE.Mesh(new THREE.TorusGeometry(3.42, 0.06, 8, seg), bronze); rim.rotation.x = Math.PI / 2; rim.position.y = 0.16; group.add(rim);
  const hub = new THREE.Mesh(new THREE.CylinderGeometry(0.34, 0.42, 0.5, 24), bronze); hub.position.y = 0.4; group.add(hub);
  const goldDim = new THREE.MeshStandardMaterial({ color: '#e0bf68', roughness: 0.4, metalness: 0.5, emissive: '#5a4210', emissiveIntensity: 0.35 });
  const goldLit = new THREE.MeshStandardMaterial({ color: '#ffe08a', roughness: 0.3, metalness: 0.4, emissive: '#ffc860', emissiveIntensity: 1.3 });
  const pillars = [];
  for (let h = 0; h < 24; h++) {
    const a = (h / 24) * Math.PI * 2, H = pillarHeight(h);
    const m = new THREE.Mesh(new THREE.CylinderGeometry(0.1, 0.13, 1, lite() ? 8 : 14), goldDim);
    m.scale.y = H; m.position.set(Math.sin(a) * 2.7, 0.3 + H / 2, -Math.cos(a) * 2.7); group.add(m);
    const cap = new THREE.Mesh(new THREE.SphereGeometry(0.15, 10, 8), bronze); cap.position.set(m.position.x, 0.3 + H + 0.1, m.position.z); group.add(cap);
    pillars.push({ m, H });
  }
  const hand = new THREE.Mesh(new THREE.BoxGeometry(0.07, 0.07, 2.5), goldLit); hand.position.y = 0.62; group.add(hand);
  const glow = new THREE.PointLight('#e0b060', 6, 6, 1.6); group.add(glow);
  let mod = 0, lit = -1, dirty = true, raf = 0, stopped = false, frames = 0, th = 0, last = 0;
  function apply() {
    const h = hourOf(mod), a = (mod / 1440) * Math.PI * 2;
    if (h !== lit) {
      if (lit >= 0) { pillars[lit].m.material = goldDim; pillars[lit].m.scale.y = pillars[lit].H; pillars[lit].m.position.y = 0.3 + pillars[lit].H / 2; }
      const p = pillars[h]; p.m.material = goldLit; p.m.scale.y = p.H * 1.5; p.m.position.y = 0.3 + (p.H * 1.5) / 2; lit = h;
      glow.position.set(p.m.position.x, 0.3 + p.H * 1.5 + 0.5, p.m.position.z);
    }
    hand.rotation.y = Math.PI - a; hand.position.set(Math.sin(a) * 1.25, 0.62, -Math.cos(a) * 1.25);
    dirty = true;
  }
  function size() {
    const w = canvas.clientWidth || 320, hh = canvas.clientHeight || 300, dpr = Math.min(window.devicePixelRatio || 1, lite() ? 1 : 2);
    if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(hh * dpr)) { renderer.setPixelRatio(dpr); renderer.setSize(w, hh, false); camera.aspect = w / hh; camera.updateProjectionMatrix(); dirty = true; }
  }
  function frame(now) {
    raf = requestAnimationFrame(frame);
    if (stopped || document.hidden) return;
    const r = canvas.getBoundingClientRect(); if (r.bottom < -40 || r.top > innerHeight + 40) return;
    const dt = last ? Math.min(0.1, (now - last) / 1000) : 0.016; last = now;
    size();
    if (!reduced()) { th = Math.sin(now / 1000 * 0.2) * 0.35; dirty = true; }
    if (!dirty) return;
    const d = camera.aspect < 0.9 ? 15 : 12; group.rotation.y = th;
    camera.position.set(0, 6.2, d); camera.lookAt(0, 0.4, 0);
    renderer.render(scene, camera); dirty = false; frames++;
  }
  raf = requestAnimationFrame(frame);
  apply();
  return {
    set(m) { const v = typeof m === 'number' && Number.isFinite(m) ? m : 0; if (v !== mod) { mod = v; apply(); } },
    hour: () => hourOf(mod), lit: () => lit, frames: () => frames,
    dispose() { stopped = true; cancelAnimationFrame(raf); try { renderer.dispose(); } catch (_) { /* gone */ } },
  };
}
