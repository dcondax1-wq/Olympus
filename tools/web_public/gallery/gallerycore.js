// AGORA GALLERY core (pure maths and data, node-tested): the shelf (19 shapes in four groups), the 2D drawings used as the never-blank fallback and as
// the shelf icons, wrap-around stepping, the camera distance that fits a stage, the quality choice and the drag inertia. No DOM, no three.js.
// shapes3d.js (olympus/) owns the real list of shapes; fixture.json mirrors its names and meanings, a test keeps the two equal.

export const GROUPS = ['Temples and monuments', 'Time and counsel', 'Wealth and trade', 'War and glory'];
export const MODES = ['auto', 'high', 'lite'];
export const MODE_LABEL = { auto: 'Auto', high: 'High', lite: 'Lite' };

// 64 x 64 line drawings, stroke = currentColor. [tag, attrs]
const P = (d, extra) => ['path', Object.assign({ d }, extra || {})];
const R = (x, y, w, h, extra) => ['rect', Object.assign({ x, y, width: w, height: h }, extra || {})];
const C = (cx, cy, r, extra) => ['circle', Object.assign({ cx, cy, r }, extra || {})];
const E = (cx, cy, rx, ry, extra) => ['ellipse', Object.assign({ cx, cy, rx, ry }, extra || {})];
export const GLYPHS = {
  doric: [R(17, 8, 30, 7), P('M24 15v34M32 15v34M40 15v34'), R(15, 49, 34, 6)],
  ionic: [R(15, 8, 34, 5), C(23, 20, 5), C(41, 20, 5), P('M27 25v24M37 25v24'), R(15, 49, 34, 6)],
  temple: [P('M7 25 32 9l25 16Z'), R(10, 25, 44, 4), P('M15 29v22M25 29v22M39 29v22M49 29v22'), R(5, 51, 54, 6)],
  lighthouse: [P('M23 57 27 26h10l4 31Z'), R(25, 17, 14, 9), P('M26 17l6-9 6 9'), P('M12 14l8 3M52 14l-8 3M32 3v2')],
  obelisk: [P('M27 55 29 19 32 8l3 11 2 36Z'), R(21, 55, 22, 4)],
  sundial: [E(32, 40, 25, 11), P('M32 40V16l13 24Z'), P('M13 40h4M47 40h4M20 33l3 3M44 33l-3 3')],
  hourglass: [P('M16 7h32M16 57h32'), P('M19 7c0 14 13 16 13 25S19 43 19 57M45 7c0 14-13 16-13 25s13 11 13 25'), P('M25 50h14')],
  owl: [E(32, 39, 15, 18), C(25, 29, 5.5), C(39, 29, 5.5), P('M30 34l2 5 2-5Z'), P('M19 12l7 11M45 12l-7 11'), P('M24 52v5M40 52v5')],
  scroll: [R(15, 15, 34, 34, { rx: 2 }), E(15, 32, 4, 17), E(49, 32, 4, 17), P('M22 25h22M22 32h22M22 39h14')],
  amphora: [P('M26 7h12M28 7v10M36 7v10'), P('M28 17C14 23 14 41 23 50l4 7h10l4-7c9-9 9-27-5-33'), P('M28 14c-9 0-9 9-2 9M36 14c9 0 9 9 2 9')],
  coinstack: [E(20, 50, 11, 4), E(20, 43, 11, 4), E(20, 36, 11, 4), P('M9 36v14M31 36v14'), E(45, 50, 11, 4), E(45, 43, 11, 4), P('M34 43v7M56 43v7')],
  scales: [P('M32 10v42M18 20h28'), P('M10 38l8-18 8 18ZM38 38l8-18 8 18Z'), P('M10 38h16M38 38h16'), P('M22 54h20')],
  pillarbar: [R(9, 38, 9, 17), R(20, 28, 9, 27), R(31, 34, 9, 21), R(42, 18, 9, 37), P('M5 56h54')],
  trireme: [P('M7 39h50l-7 10H16Z'), P('M32 39V9'), P('M32 11h14v19H32Z'), P('M4 55q7-4 14 0t14 0 14 0 14 0')],
  laurel: [P('M32 56C13 53 7 34 11 14M32 56c19-3 25-22 21-42'), E(14, 26, 2.5, 5), E(12, 38, 2.5, 5), E(20, 47, 2.5, 5), E(50, 26, 2.5, 5), E(52, 38, 2.5, 5), E(44, 47, 2.5, 5), P('M29 57l-4 5M35 57l4 5')],
  shield: [C(32, 32, 23), C(32, 32, 9), P('M32 9v14M32 41v14M9 32h14M41 32h14')],
  helmet: [P('M13 38C13 21 21 10 32 10s19 11 19 28v17h-9V40H22v15h-9Z'), P('M19 13c7-9 19-9 26 0'), P('M32 28v12')],
  lyre: [P('M19 56C9 45 11 26 21 12M45 56c10-11 8-30-2-44'), P('M19 13h26'), P('M26 13v40M32 13v40M38 13v40'), E(32, 52, 14, 5)],
  brazier: [P('M15 28h34l-7 13H22Z'), P('M24 41l-6 16M40 41l6 16M32 41v16'), P('M32 5c8 8 9 14 0 19-9-5-8-11 0-19Z')],
};

const GROUP_OF = { doric: 0, ionic: 0, temple: 0, lighthouse: 0, obelisk: 0, sundial: 1, hourglass: 1, owl: 1, scroll: 1, amphora: 2, coinstack: 2, scales: 2, pillarbar: 2, trireme: 2, laurel: 3, shield: 3, helmet: 3, lyre: 3, brazier: 3 };
export const DEFAULT_ITEMS = Object.keys(GLYPHS).map((id) => ({ id, name: id.charAt(0).toUpperCase() + id.slice(1), means: 'A classical shape of the Agora.', group: GROUPS[GROUP_OF[id] || 0] }));

/** the shelf from the fixture: [{ id, name, means, group }] in fixture order, junk dropped; the built-in list if nothing usable (never blank) */
export function shelf(fx) {
  const out = [], seen = {};
  const src = fx && Array.isArray(fx.shapes) ? fx.shapes : [];
  for (const s of src) {
    if (!s || typeof s.id !== 'string' || !GLYPHS[s.id] || seen[s.id]) continue;
    seen[s.id] = 1;
    out.push({ id: s.id, name: String(s.name || s.id).slice(0, 40), means: String(s.means || '').slice(0, 220), group: GROUPS.indexOf(s.group) >= 0 ? s.group : GROUPS[0] });
  }
  return out.length ? out : DEFAULT_ITEMS.map((s) => Object.assign({}, s));
}
/** [{ name, items:[...] }] in group order, empty groups left out */
export function grouped(items) {
  return GROUPS.map((name) => ({ name, items: items.filter((s) => s.group === name) })).filter((g) => g.items.length);
}
/** previous / next with wrap-around; any junk becomes 0 */
export function step(i, d, n) {
  n = Math.max(1, Math.floor(Number(n)) || 1);
  const k = Math.floor(Number(i)) || 0;
  return (((k + (Math.floor(Number(d)) || 0)) % n) + n) % n;
}
export function indexOf(items, id) { const k = items.findIndex((s) => s.id === id); return k < 0 ? 0 : k; }
export const fmt = (n) => String(Math.round(Number(n) || 0)).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
/** the camera distance that keeps a stage of `halfW` x `halfH` world units in view at vertical field of view `fovDeg` and the stage's aspect; `focus` moves in */
export function fitDistance(fovDeg, aspect, halfW, halfH, focus) {
  const t = Math.tan(((Number(fovDeg) || 34) * Math.PI) / 360), a = Math.max(0.3, Number(aspect) || 1);
  const d = Math.max(halfH / t, halfW / (t * a)) + 0.4;
  return focus ? d * 0.78 : d;
}
/** which quality a choice means: auto follows the render core's own level */
export function modeFor(choice, autoLevel) {
  const m = MODES.indexOf(choice) >= 0 ? choice : 'auto';
  const lite = m === 'lite' || (m === 'auto' && (autoLevel === 'low' || autoLevel === 'off'));
  return { mode: m, lite, level: m === 'high' ? 'high' : m === 'lite' ? 'low' : null };
}
/** drag inertia: the turn speed (rad / s) after dt seconds, gone in about a second; below 0.02 it stops */
export function inertia(v, dt) { const k = v * Math.exp(-3.2 * Math.max(0, dt)); return Math.abs(k) < 0.02 ? 0 : k; }
/** a tap, not a drag: moved less than 8 px and was down for under 450 ms */
export function isTap(movedPx, ms) { return movedPx < 8 && ms < 450; }
/** the line under the name: "Shape 3 of 19" */
export function position(i, n) { return `Shape ${i + 1} of ${n}`; }
/** plain words for a quality level */
export function qualityWords(lite) { return lite ? 'Lite: fewer, simpler pieces for a light phone' : 'High: full detail'; }
