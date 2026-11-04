// TYCHE scene effects (2026-11-04), from the OLYMPUS effects library (../olympus/fx-*.js): water-light caustics on the floor, a few gold motes in
// the air, and a ceremonial ring of light when the wheel is spun. The scene's own tier follows OLYMPUS.fx(); the library's tiers do the same,
// so LITE / off draw less or nothing. Never needed: any failure here leaves the scene as it was.
const FX = () => window.OLYMPUS_FX || null;
const FLOOR_Y = -6;                       // pools.js FLOOR_Y
let target = null, ready = null;

export function startSceneFx(scene, { lite = false } = {}) {
  const fx = FX();
  if (!fx || !scene || !scene.scene) return null;
  target = { scene: scene.scene, camera: scene.camera, renderer: scene.renderer, rc: scene.rc };
  ready = Promise.all(['fx-sky.js', 'fx-weather.js', 'fx-surface.js'].map((f) => import('../olympus/' + f + '?v=f1'))).then(() => {
    const hs = [fx.caustics(target, { position: [5, FLOOR_Y + 0.08, -1], size: 34, intensity: 0.42, color: '#ffcf7a' })];
    if (!lite) hs.push(fx.dust(target, { color: '#ffe08a', box: [18, 9, 12], center: [2, -1, 0], count: 420, size: 0.08 }));
    return hs;
  }).catch(() => null);
  return ready;
}

/** a tap on the wheel: a ring of gold light from the hub (a one-shot; the library keeps at most one running per call and cleans it up) */
export function ceremony() {
  const fx = FX();
  if (!fx || !target || !ready) return null;
  try { return fx.shockwave(target, { position: [0, 0.3, 0], radius: 7, color: '#ffcf5a', seconds: 1.8 }); } catch (_) { return null; }
}
