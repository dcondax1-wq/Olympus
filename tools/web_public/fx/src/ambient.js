// Ambient life for the 3D scenes (2026-11-04): dust motes, fireflies, light shafts and a faint aurora, from the OLYMPUS effects kit
// (olympus/fx-core.js, fx-three.js, fx-sky.js: ES modules / one classic script; esbuild aliases their three import to this bundle's own
// three, so there is still one three.js in fx.js). Used by the Trade Galaxy, the Month City and the eval Reactor; the Holodeck and the
// space background do not use it (the Holodeck stays at its low tier cap).
//   ambient(view, 'galaxy' | 'city' | 'reactor')  -> view.ambient = { sync(), stop() }
// The View calls sync() when it attaches / detaches, scrolls in or out of view, and resizes (a tier change): the effects exist only
// while the view is on screen, at the view's own tier (rcore.tierFor: the owner's jfx can only lower it; reduced motion = none):
//   ultra  dust + fireflies + 3 light shafts + 4 aurora curtains          (about 9 draw calls)
//   high   dust + fireflies + 3 aurora curtains                          (about 5 draw calls)
//   low    a few dust motes only                                         (1 draw call)
// Everything is pooled and capped by the kit (particles <= 2000 / 1200 / 400 per effect); the motes are ONE GPU buffer each, every
// motion is in the vertex shader, so no per-frame JS beyond four uniform writes.
import '../../olympus/fx-core.js';                 // first: the other kit modules read window.OLYMPUS_FX when they load
import { particles } from '../../olympus/fx-three.js';
import '../../olympus/fx-sky.js';                  // godRays, aurora
import { Q, theme } from './core.js';
import { tierFor } from './rcore.js';

const FX = window.OLYMPUS_FX;
const hex = (c) => '#' + c.getHexString();
const mix = (c, k) => hex(c.clone().lerp(new c.constructor('#ffffff'), k));

// sizes are fractions of the view's camera distance L (the scenes frame themselves with L), so the effects follow the framing
const PRESETS = {
  galaxy: { dust: [360, 220, 90], fire: [34, 22], shafts: 3, shaftK: 0.22, y: 0.1, L: 13 },     // the galaxy already has its own 1500 dust + aurora curtain: lighter here
  city: { dust: [640, 400, 140], fire: [46, 30], shafts: 3, shaftK: 0.3, y: 0.05, L: 18 },
  reactor: { dust: [520, 320, 120], fire: [36, 24], shafts: 3, shaftK: 0.3, y: 0.35, L: 12 },
};

// the mote systems live inside one kit effect so the kit's tier caps, pooling and cleanup apply (it stops everything it made)
if (FX && !FX.has('sceneAmbient')) {
  FX.define('sceneAmbient', { kind: 'scene', group: 'ambient', desc: 'dust motes and fireflies that follow a 3D view\'s framing (camera distance and target)', make(scene, o, ctx) {
    const v = o.view, P = o.preset, systems = [];
    const dn = ctx.count(...P.dust), fn = ctx.tier === 'low' ? 0 : ctx.count(P.fire[0], P.fire[1], 0);
    const pr = { scene, renderer: v.renderer, camera: v.camera };
    const a = theme.accent, b = theme.accent2;
    if (dn > 0) systems.push({ s: particles(ctx, pr, { mode: 'dust', n: dn, box: [20, 9, 15], center: [0, 3, 0], vel: [0.03, 0.05, 0.02], size: 0.1, sway: [0.6, 0.35, 0.6], color: mix(b, 0.45), seed: 5 }),
      box: [1.5, 0.75, 1.15], up: 0.1, size: 0.0085, sway: 0.045 });
    if (fn > 0) systems.push({ s: particles(ctx, pr, { mode: 'firefly', n: fn, box: [18, 4, 12], center: [0, 2, 0], vel: [0, 0, 0], size: 0.3, sway: [1.4, 0.8, 1.4], color: hex(b), color2: hex(a), seed: 17 }),
      box: [1.35, 0.4, 0.95], up: -0.05, size: 0.013, sway: 0.1 });
    ctx.tick(() => {
      const L = v.L || P.L, T = v.T;
      for (const m of systems) {
        const u = m.s.uniforms;
        u.uBox.value.set(L * m.box[0], L * m.box[1], L * m.box[2]);
        u.uCenter.value.set(T.x, T.y + L * m.up, T.z);
        u.uSize.value = L * m.size;
        u.uSway.value.set(L * m.sway, L * m.sway * 0.6, L * m.sway);
      }
    });
    return {};
  } });
}

export function ambient(view, kind) {
  const P = PRESETS[kind];
  if (!P || !FX) return null;
  let hs = [], tier = null;
  const stop = () => { for (const h of hs) { try { h.stop(); } catch (e) { /* already gone */ } } hs = []; tier = null; };
  const start = (t) => {
    tier = t;
    const L = P.L, sc = view.scene, a = theme.accent, b = theme.accent2;
    hs.push(FX.sceneAmbient(sc, { view, preset: P, tier: t }));
    if (t === 'low') return;
    if (t === 'ultra') hs.push(FX.godRays(sc, { tier: t, count: P.shafts, position: [0, L * 0.95, -L * 0.2], length: L * 1.15, intensity: P.shaftK, spread: 0.2, color: mix(b, 0.6), seed: 6 }));
    hs.push(FX.aurora(sc, { tier: t, width: L * 5.2, height: L * 1.25, position: [0, L * (1.05 + P.y), -L * 2.7], intensity: 0.32, colors: [hex(b), hex(a), '#c084fc'], seed: 8 }));
  };
  const ctl = {
    stop,
    sync() {
      const want = view.attached && view.visible && !view.broken && Q.level !== 'off' && !Q.reduced;
      if (!want) { if (hs.length) stop(); return; }
      const t = tierFor(view.rc && view.rc.cap);
      if (t !== tier) { stop(); start(t); }
    },
    get tier() { return tier; },
    get running() { return hs.length > 0; },
  };
  view.ambient = ctl;
  return ctl;
}
