// The OLYMPUS render core for the 3D layer (2026-11-03; docs/OLYMPUS_RENDER.md): every View draws through createRenderer()
// from tools/web_public/olympus/render.js instead of a bare WebGLRenderer: ACES filmic tone mapping, 4x MSAA on the scene
// buffer (FXAA on Lite), a half-resolution bloom pass, and one finish pass (vignette, film grain, light aberration).
// esbuild aliases the core's three import (jarvis/three.module.min.js, r160) to this bundle's own three, so there is one
// three.js in fx.js. The scenes keep their own shaders ('display' space: their colours are screen colours, as before).
import { createRenderer } from '../../olympus/render.js';
import { Q } from './core.js';

const LEVELS = ['ultra', 'high', 'low', 'off'];
const chosen = () => { try { const v = localStorage.getItem('jfx'); return LEVELS.includes(v) ? v : null; } catch { return null; } };
const kit = () => (typeof window !== 'undefined' && window.OLYMPUS) || null;

// the tier a view should run on: Max = ultra on a PC, high on a phone; Lite = low; the owner's 'jfx' choice (Jarvis / Settings)
// can only lower it; reduced motion = low; a slow phone (Q.tierCap) = low. cap: the most a view may use ('high' for a full-screen backdrop).
export function tierFor(cap) {
  let t = Q.level === 'lite' ? 'low' : Q.phone ? 'high' : 'ultra';
  const O = kit(), j = (O && O.chosen && O.chosen() && O.fx && O.fx()) || chosen(), rank = (x) => LEVELS.indexOf(x);
  if (j && j !== 'off' && rank(j) > rank(t)) t = j;
  if (cap && rank(cap) > rank(t)) t = cap;
  if (Q.reduced || Q.tierCap) t = 'low';
  return t;
}

// opts: { cap, env: 'night' | 'none', bloom, grade, maxDpr }
export function makeCore(view, opts = {}) {
  const rc = createRenderer({ canvas: view.canvas, scene: view.scene, camera: view.camera, quality: tierFor(opts.cap), alpha: !!view.opts.alpha, space: 'display',
    env: opts.env || 'none', adapt: false, autoSize: false, fitCamera: false, theme: null, maxDpr: opts.maxDpr || view.opts.dprMax || 2, exposure: 1,
    bloom: { strength: 0.6, radius: 0.5, threshold: 0.7, ...(opts.bloom || {}) }, grade: { grain: 0.03, vignette: 0.3, aberration: 0.0018, ...(opts.grade || {}) },
    onQuality: () => view.resize?.() });
  rc.cap = opts.cap || null;
  return rc;
}

// size the core to w x h CSS px, then apply the dashboard's own adaptive scale (Q.dprScale) on top of the tier's pixel ratio
export function sizeCore(rc, w, h) {
  rc.resize(w, h);
  if (Q.dprScale !== 1) {
    const r = rc.renderer, d = r.getPixelRatio() * Q.dprScale;
    r.setPixelRatio(d); r.setSize(w, h, false);
    if (rc.composer) { rc.composer.setPixelRatio(d); rc.composer.setSize(w, h); }
  }
}
