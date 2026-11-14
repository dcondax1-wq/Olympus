/* OLYMPUS themes (2026-11-03, docs/OLYMPUS_DESIGN.md "Themes"): whole-system palettes as DATA, and the small engine that applies
 * them. One key on the shared origin, localStorage 'olympus.theme' = a theme id; Jarvis's Look sheet writes it, and every page
 * (Jarvis, the nine 3D apps, Zenith, Kalshi) reads it at start and on the 'storage' event.
 *
 * A classic ES5 script (no module, never throws). It sets window.OLYMPUS_THEMES:
 *   list()            the themes in picker order: [{ id, name, greek, tag, scheme, tokens, stage?, jarvis? }]
 *   id() / get(id)    the stored id (unknown or missing = 'agora', the default) / one theme
 *   tokens(id, where) the resolved palette. where = 'page' (Jarvis: the full palette, light themes light) or 'stage' (the 3D
 *                     apps, Zenith, Kalshi: surfaces that are dark by design; a light theme gives its dark 'stage' variant there)
 *   apply(where)      paints <html>: data-oly-theme / data-oly-scheme, the --oly-* tokens, color-scheme and the theme-color meta.
 *                     The default theme (AGORA) writes NOTHING inline: the stylesheets' own values (olympus.css :root, jarvis.css) are the AGORA palette.
 *   set(id)           stores the choice and applies it; on(cb) is told (tokens, id) after every change, cross-tab too
 *   mix(a, b, t)      blends two '#rrggbb' (or 0xrrggbb numbers; the result keeps the type of a); t = 0 returns a untouched
 *   harmonise(app, accent, t)  an app's identity colour with its hue turned toward the accent by t (0 = untouched)
 *
 * Every theme carries every token in TOKENS (tests/test_olympus_themes.py checks it). The 3D tints: fog / sky / emissive / bloom,
 * mixed into each app's own scene colours by 'mix' (0 = the app's colours untouched), and 'harmony' = how far an app's identity
 * colour leans toward the theme accent (0 = untouched). So the default theme (mix 0, harmony 0, no inline vars) changes nothing.
 */
(function () {
  'use strict';
  if (window.OLYMPUS_THEMES) return;
  var KEY = 'olympus.theme', DEFAULT = 'agora';     // AGORA is the default since 2026-11-09 (docs/DESIGN_AGORA.md); the old violet look is 'olympus'
  // the token names every theme must define (CSS ones become --oly-<name>; the 3D ones go to the scenes)
  var TOKENS = ['bg', 'bg2', 'glass', 'glass2', 'line', 'edge', 'text', 'dim', 'accent', 'accent2', 'glow', 'ok', 'bad', 'warn', 'shadow',
    'scheme', 'themeColor', 'fog', 'sky', 'emissive', 'bloom', 'mix', 'harmony'];
  var CSS = { bg: 'bg', bg2: 'bg2', glass: 'glass', glass2: 'glass2', line: 'line', edge: 'edge', text: 'text', dim: 'dim', accent: 'tone',
    accent2: 'tone2', glow: 'glow', ok: 'ok', bad: 'bad', warn: 'warn', shadow: 'shadow', fog: 'fog', sky: 'sky', emissive: 'emissive', bloom: 'bloom' };
  // Jarvis's own palette names (jarvis.css :root[data-theme]): a theme that is not the default paints them too
  var JARVIS = ['bg', 'bg2', 'pr', 'txt', 'mut', 'dim', 'dim2', 'dim3', 'c', 'c2', 'c3', 'cr', 'cr2', 'cr3', 'tint', 'neb1', 'neb2', 'neb3', 'grid', 'scan'];

  /* ------------------------------------------------------------------ the reach ramp (2026-11-14, team T1 "themes")
   * The AGORA stylesheets (agora.css, gate.css, the dashboard's sheets, Jarvis's, NQ / Helios / Polis) wrote their colours as literals.
   * tools/theme_tokenize.py rewrote each literal as var(--oly-th-<slot>, <the literal>): the literal stays the fallback, and no stylesheet
   * defines --oly-th-*, so the default theme (which paints nothing) is byte for byte today's look. A slot is the literal's family and
   * its HSL lightness on a fixed grid: n = the warm neutrals (page, panels, lines, text), a = the golds / bronzes, g = the olive greens
   * (gains), r = the terracottas (losses), warn = AGORA's sun. A theme gives, for each family, the colour each AGORA reference colour
   * becomes (REF); every grid step is the blend between the two references around it, so the whole hierarchy (page < panel < raised
   * panel < line < muted < soft < text) follows, inverted for a light theme. Each slot is painted as #rrggbb and as 'r, g, b'
   * (--oly-th-<slot>-rgb, for rgba(var(...), a)). tests/test_olympus_themes.py checks that this grid equals the tool's. */
  var GRID = { n: [0, 100, 2.5], a: [15, 90, 5], g: [15, 90, 5], r: [15, 90, 5] };
  var REF = {
    n: [['deep', '#000000'], ['bg', '#14110e'], ['panel', '#1d1914'], ['lift', '#26211b'], ['line', '#3a3228'], ['muted', '#a89c88'], ['soft', '#cfc4b2'], ['text', '#f3ece0'], ['peak', '#ffffff']],
    a: [['deep', '#3b2c1e'], ['bronze', '#9c6b3c'], ['accent', '#c8a24a'], ['hi', '#dcbd6e'], ['pale', '#f5e6c4']],
    g: [['deep', '#3a4022'], ['fill', '#7f8a52'], ['text', '#a0ac6e'], ['pale', '#d4dcb0']],
    r: [['deep', '#4a2418'], ['fill', '#c96a4a'], ['text', '#e08a6b'], ['pale', '#f2c4b4']]
  };
  // the feel of a theme besides colour: corner radius and the heading / number fonts (agora.css, gate.css and the dashboard read them)
  var FEEL = { radius: '--oly-th-radius', radiusS: '--oly-th-radius-s', radiusL: '--oly-th-radius-l', display: '--oly-th-display', num: '--oly-th-num' };
  var SANS = "-apple-system, 'SF Pro Display', system-ui, 'Helvetica Neue', Arial, sans-serif";
  /** a theme from its ramp: the --oly-* tokens follow from it (page = n.bg, panels = n.panel / lift, text = n.text, dim = n.soft ...) */
  function mk(o) {
    var R = o.ramp, n = R.n, a = R.a, rgbs = function (c, al) { var x = rgbOf(c); return 'rgba(' + x[0] + ', ' + x[1] + ', ' + x[2] + ', ' + al + ')'; };
    var tk = { bg: n.bg, bg2: n.panel, glass: rgbs(n.panel, o.light ? '.92' : '.9'), glass2: rgbs(n.lift, '.97'), line: n.line, edge: rgbs(a.accent, '.42'),
      text: n.text, dim: n.soft, accent: a.accent, accent2: a.hi, glow: a.hi, ok: R.g.text, bad: R.r.text, warn: R.warn,
      shadow: o.light ? '0 6px 18px rgba(60, 45, 20, .12)' : '0 6px 18px rgba(0, 0, 0, .4)', scheme: o.scheme, themeColor: n.bg };
    for (var k in o.scene) tk[k] = o.scene[k];
    var t = { id: o.id, name: o.name, greek: o.greek || '', tag: o.tag, scheme: o.scheme, tokens: tk, ramp: R, feel: o.feel || null, jarvis: o.jarvis, plain: true };
    if (o.stage) {
      var S = o.stage, sn = S.n, sa = S.a;
      t.stageRamp = S;
      t.stage = { bg: sn.bg, bg2: sn.panel, glass: rgbs(sn.panel, '.9'), glass2: rgbs(sn.lift, '.97'), line: sn.line, edge: rgbs(sa.accent, '.42'), text: sn.text,
        dim: sn.soft, accent: sa.accent, accent2: sa.hi, glow: sa.hi, ok: S.g.text, bad: S.r.text, warn: S.warn, shadow: '0 6px 18px rgba(0, 0, 0, .4)', scheme: 'dark', themeColor: sn.bg };
    }
    return t;
  }

  /* ------------------------------------------------------------------ the themes (data only) */
  var THEMES = [
    { id: 'agora', name: 'Agora', greek: 'ΑΓΟΡΑ', tag: 'Marble · bronze · gold · default', scheme: 'dark',
      // the default (docs/DESIGN_AGORA.md): classical, warm, calm. These equal olympus.css's :root values (the default writes nothing
      // inline) and Jarvis's own 'agora' palette in jarvis.css. Scenes keep their own colours (mix 0): warm light, no neon.
      tokens: { bg: '#14110e', bg2: '#1d1914', glass: 'rgba(29, 25, 20, .88)', glass2: 'rgba(38, 33, 27, .96)', line: '#3a3228',
        edge: 'rgba(200, 162, 74, .38)', text: '#f3ece0', dim: '#cfc4b2', accent: '#c8a24a', accent2: '#e0b060', glow: '#c8a24a',
        ok: '#7f8a52', bad: '#c96a4a', warn: '#e0b060', shadow: '0 6px 18px rgba(0, 0, 0, .35)', scheme: 'dark', themeColor: '#14110e',
        fog: '#2a2118', sky: '#3a2a1c', emissive: '#e0b060', bloom: '#f0d9a0', mix: 0, harmony: 0 },
      jarvis: null },
    /* the five plain looks (2026-11-14, owner: "a different theme but keep everything the same, stuff-wise ... multiple theme options. Make it good").
       Only colour, surface, heading / number type and corner radius change; every word and number stays. Every text colour is >= 4.5:1 on the
       page, the panels and the raised panels (WCAG AA, tests/test_olympus_themes.py); gains are green and losses red in every one. No glow. */
    mk({ id: 'ivory', name: 'Ivory', tag: 'Warm paper white · ink · gold · for daylight', scheme: 'light', light: true,
      ramp: { n: { deep: '#f7f4ee', bg: '#f7f4ee', panel: '#fffdf9', lift: '#ffffff', line: '#d9d0c1', muted: '#6b6152', soft: '#4a4237', text: '#1c1813', peak: '#0f0c08' },
        a: { deep: '#efe4cc', bronze: '#c9a96a', accent: '#8a6514', hi: '#7a5810', pale: '#5c420b' },
        g: { deep: '#dde8d3', fill: '#3f7a3a', text: '#2e6b2c', pale: '#1f4d1e' }, r: { deep: '#f4d9d3', fill: '#c0392b', text: '#b0301f', pale: '#7d2216' }, warn: '#8f5a00' },
      // the 3D apps, Kalshi and every page not yet checked in light: a warm graphite night with the same ink-gold (light fog would wash the scenes out)
      stage: { n: { deep: '#0d0c0a', bg: '#15130f', panel: '#1e1b16', lift: '#26231d', line: '#3a352c', muted: '#a39b8c', soft: '#d3cbbd', text: '#f7f3ea', peak: '#ffffff' },
        a: { deep: '#3a2e18', bronze: '#8f7440', accent: '#c9a45c', hi: '#dcc088', pale: '#f3e6c8' },
        g: { deep: '#26391f', fill: '#5fa055', text: '#7cc370', pale: '#c8e8c0' }, r: { deep: '#4a1f18', fill: '#e86a58', text: '#f07a6a', pale: '#f8c8c0' }, warn: '#e8b45a' },
      feel: { radius: '18px', radiusS: '13px', radiusL: '24px' },
      scene: { fog: '#2f2a22', sky: '#3d362b', emissive: '#e2c88a', bloom: '#f6ecd4', mix: 0.5, harmony: 0.25 },
      jarvis: { bg: '#f7f4ee', bg2: '#ffffff', pr: '255,253,249', txt: '#1c1813', mut: '#5f5648', dim: '#e6dfd2', dim2: '#cfc4b0', dim3: '#a8916a',
        c: '#8a6514', c2: '#6e500f', c3: '#6e500f', cr: '138,101,20', cr2: '110,80,15', cr3: '92,66,11', tint: '#fffdf8',
        neb1: '201,169,106', neb2: '230,214,180', neb3: '180,196,210', grid: '.04', scan: '0' } }),
    mk({ id: 'midnight', name: 'Midnight', tag: 'Deep navy glass · soft blue · iPhone calm', scheme: 'dark',
      ramp: { n: { deep: '#05080f', bg: '#0b1220', panel: '#111a2c', lift: '#172237', line: '#283650', muted: '#94a0b8', soft: '#c5cddb', text: '#f2f5fa', peak: '#ffffff' },
        a: { deep: '#0f2a4d', bronze: '#2f6fc4', accent: '#4c9dff', hi: '#7ab6ff', pale: '#cfe3ff' },
        g: { deep: '#123a26', fill: '#30c26a', text: '#4ade80', pale: '#c2f5d6' }, r: { deep: '#4a1820', fill: '#f25c66', text: '#ff7a82', pale: '#ffd0d3' }, warn: '#ffc857' },
      feel: { radius: '20px', radiusS: '14px', radiusL: '26px', display: SANS, num: SANS },
      scene: { fog: '#0a1424', sky: '#0f1d36', emissive: '#6aa8ff', bloom: '#d6e6ff', mix: 0.55, harmony: 0.3 },
      jarvis: { bg: '#0b1220', bg2: '#111a2c', pr: '17,26,44', txt: '#f2f5fa', mut: '#94a0b8', dim: '#172237', dim2: '#283650', dim3: '#3b5378',
        c: '#4c9dff', c2: '#2f6fc4', c3: '#7ab6ff', cr: '76,157,255', cr2: '47,111,196', cr3: '207,227,255', tint: '#e6f0ff',
        neb1: '47,111,196', neb2: '90,140,220', neb3: '120,170,230', grid: '.04', scan: '0' } }),
    mk({ id: 'trader', name: 'Trader', tag: 'Black · one green · square and exact', scheme: 'dark',
      ramp: { n: { deep: '#000000', bg: '#060707', panel: '#0d0f0e', lift: '#131614', line: '#242a27', muted: '#8a948e', soft: '#b9c2bc', text: '#e9eeea', peak: '#ffffff' },
        a: { deep: '#0f2e1d', bronze: '#1f8a4f', accent: '#2ecc71', hi: '#5ee69a', pale: '#c6f6d9' },
        g: { deep: '#0f2e1d', fill: '#2ecc71', text: '#3ddc84', pale: '#c6f6d9' }, r: { deep: '#3d1414', fill: '#ff5a52', text: '#ff6b63', pale: '#ffd2cf' }, warn: '#e6c15c' },
      feel: { radius: '8px', radiusS: '6px', radiusL: '10px', display: SANS, num: SANS },
      scene: { fog: '#050806', sky: '#08100b', emissive: '#3ddc84', bloom: '#c6f6d9', mix: 0.6, harmony: 0.3 },
      jarvis: { bg: '#060707', bg2: '#0d0f0e', pr: '13,15,14', txt: '#e9eeea', mut: '#8a948e', dim: '#131614', dim2: '#242a27', dim3: '#2f5a40',
        c: '#2ecc71', c2: '#1f8a4f', c3: '#5ee69a', cr: '46,204,113', cr2: '31,138,79', cr3: '198,246,217', tint: '#e6fff0',
        neb1: '20,60,40', neb2: '31,138,79', neb3: '40,80,60', grid: '.03', scan: '0' } }),
    mk({ id: 'carbon', name: 'Carbon', tag: 'Graphite greys · one orange', scheme: 'dark',
      ramp: { n: { deep: '#08090a', bg: '#121314', panel: '#191a1c', lift: '#202224', line: '#33363a', muted: '#9a9fa6', soft: '#c9ccd1', text: '#f4f5f6', peak: '#ffffff' },
        a: { deep: '#3d2508', bronze: '#b86e12', accent: '#ff9f0a', hi: '#ffb84d', pale: '#ffe2b8' },
        g: { deep: '#133a1d', fill: '#30d158', text: '#4cd964', pale: '#c6f5d0' }, r: { deep: '#4a1512', fill: '#ff453a', text: '#ff6961', pale: '#ffd0cc' }, warn: '#ffd60a' },
      feel: { radius: '12px', radiusS: '9px', radiusL: '16px', display: "'Helvetica Neue', -apple-system, 'SF Pro Display', system-ui, Arial, sans-serif", num: SANS },
      scene: { fog: '#121314', sky: '#1b1c1e', emissive: '#ffb84d', bloom: '#ffe2b8', mix: 0.6, harmony: 0.25 },
      jarvis: { bg: '#121314', bg2: '#191a1c', pr: '25,26,28', txt: '#f4f5f6', mut: '#9a9fa6', dim: '#202224', dim2: '#33363a', dim3: '#55595f',
        c: '#ff9f0a', c2: '#b86e12', c3: '#ffb84d', cr: '255,159,10', cr2: '184,110,18', cr3: '255,226,184', tint: '#fff3e0',
        neb1: '60,62,66', neb2: '90,92,96', neb3: '184,110,18', grid: '.03', scan: '0' } }),
    mk({ id: 'royal', name: 'Royal', tag: 'Navy · gold · classic', scheme: 'dark',
      ramp: { n: { deep: '#060b18', bg: '#0c1428', panel: '#121c35', lift: '#182442', line: '#2b3a5f', muted: '#9ba6c0', soft: '#cdd3e2', text: '#f6f2e7', peak: '#ffffff' },
        a: { deep: '#3a2e0e', bronze: '#9c7a26', accent: '#d4af37', hi: '#e8c860', pale: '#f6e6b0' },
        g: { deep: '#123a2a', fill: '#3fbf86', text: '#5fd39a', pale: '#c8f2dc' }, r: { deep: '#4a1a22', fill: '#f2606a', text: '#ff8086', pale: '#ffd3d6' }, warn: '#f2c14e' },
      feel: { radius: '14px', radiusS: '10px', radiusL: '20px', display: "Didot, 'Bodoni 72', 'Iowan Old Style', Georgia, serif" },
      scene: { fog: '#0b1530', sky: '#13204a', emissive: '#e8c860', bloom: '#f6e6b0', mix: 0.55, harmony: 0.3 },
      jarvis: { bg: '#0c1428', bg2: '#121c35', pr: '18,28,53', txt: '#f6f2e7', mut: '#9ba6c0', dim: '#182442', dim2: '#2b3a5f', dim3: '#4a5a85',
        c: '#d4af37', c2: '#9c7a26', c3: '#e8c860', cr: '212,175,55', cr2: '156,122,38', cr3: '246,230,176', tint: '#fff6dc',
        neb1: '40,60,120', neb2: '156,122,38', neb3: '60,90,160', grid: '.04', scan: '0' } }),
    /* the earlier looks (2026-11-03), kept selectable in Jarvis's Look sheet and Settings; the Gate shows the plain six above */
    { id: 'olympus', name: 'Olympus Night', greek: 'ΟΛΥΜΠΟΣ', tag: 'Violet + gold · the old look', scheme: 'dark',
      tokens: { bg: '#04050c', bg2: '#0d0620', glass: 'rgba(9, 11, 22, .74)', glass2: 'rgba(14, 8, 30, .92)', line: 'rgba(255, 255, 255, .12)',
        edge: 'rgba(168, 85, 247, .38)', text: '#f3f5fb', dim: 'rgba(214, 220, 236, .66)', accent: '#a855f7', accent2: '#ffc94a', glow: '#a95cff',
        ok: '#4ade80', bad: '#ff4d6d', warn: '#fbbf24', shadow: '0 12px 40px rgba(0, 0, 0, .45)', scheme: 'dark', themeColor: '#000000',
        fog: '#04050c', sky: '#0d0620', emissive: '#a855f7', bloom: '#c084fc', mix: 0, harmony: 0 },
      jarvis: { bg: '#03010a', bg2: '#0d0620', pr: '14,8,30', txt: '#efe9ff', mut: '#958ab3', dim: '#1f1538', dim2: '#3a2766', dim3: '#5233a0',
        c: '#a95cff', c2: '#6d28d9', c3: '#22d3ee', cr: '169,92,255', cr2: '109,40,217', cr3: '226,214,255', tint: '#f5d0fe',
        neb1: '124,58,237', neb2: '37,99,235', neb3: '34,211,238', grid: '.06', scan: '.03' } },
    { id: 'zeus', name: 'Zeus Storm', greek: 'ΖΕΥΣ', tag: 'Electric blue · lightning', scheme: 'dark',
      tokens: { bg: '#02050f', bg2: '#071430', glass: 'rgba(6, 14, 34, .74)', glass2: 'rgba(8, 20, 46, .92)', line: 'rgba(170, 210, 255, .16)',
        edge: 'rgba(120, 190, 255, .48)', text: '#f2f8ff', dim: 'rgba(200, 220, 245, .72)', accent: '#4da3ff', accent2: '#e8f4ff', glow: '#7cc4ff',
        ok: '#4ade80', bad: '#ff5c7a', warn: '#fcd34d', shadow: '0 12px 40px rgba(0, 6, 24, .55)', scheme: 'dark', themeColor: '#02050f',
        fog: '#06142e', sky: '#0a1c3f', emissive: '#6fb8ff', bloom: '#cfe8ff', mix: 0.55, harmony: 0.3 },
      jarvis: { bg: '#02050f', bg2: '#071430', pr: '6,16,40', txt: '#eef6ff', mut: '#8fa8c8', dim: '#0c2142', dim2: '#163a6e', dim3: '#1f56a8',
        c: '#4da3ff', c2: '#1d4ed8', c3: '#e8f4ff', cr: '77,163,255', cr2: '29,78,216', cr3: '220,238,255', tint: '#eef7ff',
        neb1: '29,78,216', neb2: '125,211,252', neb3: '232,244,255', grid: '.06', scan: '.03' } },
    { id: 'poseidon', name: 'Poseidon', greek: 'ΠΟΣΕΙΔΩΝ', tag: 'Deep ocean · aqua', scheme: 'dark',
      tokens: { bg: '#00080c', bg2: '#032029', glass: 'rgba(2, 20, 28, .74)', glass2: 'rgba(3, 28, 38, .92)', line: 'rgba(120, 255, 240, .15)',
        edge: 'rgba(46, 230, 210, .45)', text: '#e6fffb', dim: 'rgba(180, 232, 226, .70)', accent: '#19e3c9', accent2: '#38bdf8', glow: '#2ef2d0',
        ok: '#4ade80', bad: '#ff5c7a', warn: '#fbbf24', shadow: '0 12px 40px rgba(0, 12, 16, .55)', scheme: 'dark', themeColor: '#00080c',
        fog: '#03252e', sky: '#03303d', emissive: '#22e5d0', bloom: '#9ffcf0', mix: 0.55, harmony: 0.3 },
      jarvis: { bg: '#00080c', bg2: '#032029', pr: '4,30,38', txt: '#e6fffb', mut: '#7fb8b2', dim: '#07303a', dim2: '#0b5560', dim3: '#0f7e86',
        c: '#19e3c9', c2: '#0e7490', c3: '#38bdf8', cr: '25,227,201', cr2: '14,116,144', cr3: '190,255,246', tint: '#d6fffa',
        neb1: '14,116,144', neb2: '13,148,136', neb3: '56,189,248', grid: '.05', scan: '.025' } },
    { id: 'hades', name: 'Hades', greek: 'ΑΙΔΗΣ', tag: 'Black · ember red', scheme: 'dark',
      tokens: { bg: '#050102', bg2: '#1a0505', glass: 'rgba(18, 4, 4, .78)', glass2: 'rgba(26, 6, 5, .93)', line: 'rgba(255, 110, 80, .16)',
        edge: 'rgba(255, 69, 40, .45)', text: '#fff0eb', dim: 'rgba(232, 190, 180, .70)', accent: '#ff4528', accent2: '#ff9a3c', glow: '#ff3d1f',
        ok: '#4ade80', bad: '#ff6b81', warn: '#fbbf24', shadow: '0 12px 40px rgba(0, 0, 0, .6)', scheme: 'dark', themeColor: '#050102',
        fog: '#1a0403', sky: '#2a0805', emissive: '#ff4a24', bloom: '#ffb070', mix: 0.6, harmony: 0.35 },
      jarvis: { bg: '#050102', bg2: '#1a0505', pr: '26,6,4', txt: '#fff0eb', mut: '#b48a80', dim: '#2a0a07', dim2: '#5a140c', dim3: '#8f1e10',
        c: '#ff4528', c2: '#b91c1c', c3: '#ff9a3c', cr: '255,69,40', cr2: '185,28,28', cr3: '255,214,200', tint: '#ffe4dc',
        neb1: '153,27,27', neb2: '234,88,12', neb3: '255,154,60', grid: '.05', scan: '.035' } },
    { id: 'athena', name: 'Athena', greek: 'ΑΘΗΝΑ', tag: 'Marble · silver · olive', scheme: 'light',
      // the light theme: marble page, ink text (WCAG AA checked), olive accents. The 3D stage stays a dusk olive-slate (light
      // fog would wash every glow out), and the 'stage' palette dresses the HUD that floats on it.
      tokens: { bg: '#f3f1ea', bg2: '#ffffff', glass: 'rgba(255, 255, 255, .74)', glass2: 'rgba(255, 255, 255, .94)', line: 'rgba(52, 58, 42, .16)',
        edge: 'rgba(122, 134, 74, .50)', text: '#1d211a', dim: '#4a5143', accent: '#55631f', accent2: '#626b77', glow: '#9aa86a',
        ok: '#166534', bad: '#b91c1c', warn: '#92400e', shadow: '0 12px 36px rgba(60, 58, 40, .18)', scheme: 'light', themeColor: '#f3f1ea',
        fog: '#2a3027', sky: '#3a4236', emissive: '#c8d39a', bloom: '#eef0e2', mix: 0.6, harmony: 0.35 },
      stage: { bg: '#161a14', bg2: '#262c22', glass: 'rgba(30, 34, 28, .74)', glass2: 'rgba(36, 41, 33, .93)', line: 'rgba(225, 230, 210, .18)',
        edge: 'rgba(200, 211, 154, .45)', text: '#f6f5ee', dim: 'rgba(222, 226, 210, .74)', accent: '#c8d39a', accent2: '#d9dde3', glow: '#dfe6c0',
        ok: '#4ade80', bad: '#ff6b7f', warn: '#fbbf24', shadow: '0 12px 40px rgba(0, 0, 0, .45)', scheme: 'dark', themeColor: '#161a14' },
      jarvis: { bg: '#f3f1ea', bg2: '#ffffff', pr: '255,255,255', txt: '#1d211a', mut: '#4f5648', dim: '#dcdccf', dim2: '#b9bca8', dim3: '#8c9470',
        c: '#55631f', c2: '#3f4a1c', c3: '#3d4718', cr: '85,99,31', cr2: '63,74,28', cr3: '52,60,24', tint: '#fbfbf5',
        neb1: '154,168,106', neb2: '176,184,196', neb3: '214,206,180', grid: '.04', scan: '0' } },
    { id: 'apollo', name: 'Apollo', greek: 'ΑΠΟΛΛΩΝ', tag: 'Sunrise gold · orange', scheme: 'dark',
      tokens: { bg: '#0a0502', bg2: '#2a1204', glass: 'rgba(30, 14, 4, .74)', glass2: 'rgba(40, 19, 6, .92)', line: 'rgba(255, 200, 120, .17)',
        edge: 'rgba(255, 180, 60, .48)', text: '#fff6e8', dim: 'rgba(240, 215, 180, .72)', accent: '#ffb020', accent2: '#ff6a1a', glow: '#ffc94a',
        ok: '#4ade80', bad: '#ff5c7a', warn: '#fde047', shadow: '0 12px 40px rgba(12, 4, 0, .55)', scheme: 'dark', themeColor: '#0a0502',
        fog: '#241004', sky: '#3a1a05', emissive: '#ffb43c', bloom: '#ffe2a0', mix: 0.55, harmony: 0.3 },
      jarvis: { bg: '#0a0502', bg2: '#2a1204', pr: '34,16,6', txt: '#fff6e8', mut: '#c4a27c', dim: '#3a1d08', dim2: '#6e3810', dim3: '#a85a14',
        c: '#ffb020', c2: '#ea580c', c3: '#ffe08a', cr: '255,176,32', cr2: '234,88,12', cr3: '255,236,190', tint: '#fff3d6',
        neb1: '234,88,12', neb2: '251,191,36', neb3: '255,120,60', grid: '.06', scan: '.03' } },
    { id: 'artemis', name: 'Artemis', greek: 'ΑΡΤΕΜΙΣ', tag: 'Moonlight · silver · indigo', scheme: 'dark',
      tokens: { bg: '#03040c', bg2: '#10142e', glass: 'rgba(10, 12, 30, .74)', glass2: 'rgba(14, 17, 40, .92)', line: 'rgba(200, 210, 255, .15)',
        edge: 'rgba(180, 195, 255, .45)', text: '#f1f3ff', dim: 'rgba(200, 206, 235, .70)', accent: '#b8c4ff', accent2: '#7dd3fc', glow: '#c7d2fe',
        ok: '#4ade80', bad: '#ff5c7a', warn: '#fbbf24', shadow: '0 12px 40px rgba(0, 0, 12, .55)', scheme: 'dark', themeColor: '#03040c',
        fog: '#0e1230', sky: '#141a3a', emissive: '#a5b4fc', bloom: '#e0e7ff', mix: 0.55, harmony: 0.3 },
      jarvis: { bg: '#03040c', bg2: '#10142e', pr: '12,14,36', txt: '#f1f3ff', mut: '#9097b8', dim: '#181c3c', dim2: '#2a3166', dim3: '#3f4a96',
        c: '#b8c4ff', c2: '#4f46e5', c3: '#7dd3fc', cr: '184,196,255', cr2: '79,70,229', cr3: '230,235,255', tint: '#eef1ff',
        neb1: '67,56,202', neb2: '30,64,175', neb3: '125,211,252', grid: '.05', scan: '.03' } },
  ];

  /* ------------------------------------------------------------------ helpers */
  var d = document, root = d.documentElement, subs = [], by = {};
  for (var i = 0; i < THEMES.length; i++) by[THEMES[i].id] = THEMES[i];
  var get = function (k) { try { return localStorage.getItem(k); } catch (e) { return null; } };
  var put = function (k, v) { try { localStorage.setItem(k, v); } catch (e) { /* private mode: this visit only */ } };
  var del = function (k) { try { localStorage.removeItem(k); } catch (e) { /* private mode */ } };
  function hexOf(c) { return typeof c === 'number' ? c : parseInt(String(c).replace('#', '').slice(0, 6), 16); }
  function rgbOf(c) { var n = hexOf(c); return [(n >> 16) & 255, (n >> 8) & 255, n & 255]; }
  function mix(a, b, t) {
    if (!(t > 0) || b == null) return a;                    // 0 (the default theme): the colour untouched, same type and spelling
    t = Math.min(1, t);
    var x = rgbOf(a), y = rgbOf(b), n = 0;
    for (var k = 0; k < 3; k++) n = n * 256 + Math.round(x[k] + (y[k] - x[k]) * t);
    return typeof a === 'number' ? n : '#' + ('000000' + n.toString(16)).slice(-6);
  }
  // an app's identity colour leaning toward the theme accent: its hue turns (the short way round) by t, at most MAX_TURN degrees,
  // and its own saturation and lightness stay. So Tyche stays gold and Oracle cyan in every theme, only warmer or cooler; never
  // a muddy grey (an RGB blend of opposite colours is grey) and never a different colour family.
  var MAX_TURN = 16;
  function hsl(c) {
    var x = rgbOf(c), r = x[0] / 255, g = x[1] / 255, b = x[2] / 255, mx = Math.max(r, g, b), mn = Math.min(r, g, b), l = (mx + mn) / 2, h = 0, s = 0, dd = mx - mn;
    if (dd) { s = dd / (1 - Math.abs(2 * l - 1)); h = mx === r ? ((g - b) / dd) % 6 : mx === g ? (b - r) / dd + 2 : (r - g) / dd + 4; h *= 60; if (h < 0) h += 360; }
    return [h, s, l];
  }
  function fromHsl(h, s, l) {
    var c = (1 - Math.abs(2 * l - 1)) * s, x = c * (1 - Math.abs((h / 60) % 2 - 1)), m = l - c / 2, r = 0, g = 0, b = 0;
    if (h < 60) { r = c; g = x; } else if (h < 120) { r = x; g = c; } else if (h < 180) { g = c; b = x; } else if (h < 240) { g = x; b = c; } else if (h < 300) { r = x; b = c; } else { r = c; b = x; }
    var n = [r, g, b].map(function (v) { return Math.max(0, Math.min(255, Math.round((v + m) * 255))); });
    return '#' + ('000000' + ((n[0] << 16) | (n[1] << 8) | n[2]).toString(16)).slice(-6);
  }
  function harmonise(app, accent, t) {
    if (!(t > 0) || accent == null) return app;
    var a = hsl(app), b = hsl(accent);
    if (b[1] < 0.15) return mix(app, accent, t);             // a grey accent (silver themes): a plain blend toward it
    var dh = ((b[0] - a[0] + 540) % 360) - 180, turn = Math.max(-MAX_TURN, Math.min(MAX_TURN, dh * Math.min(1, t)));
    return fromHsl((a[0] + turn + 360) % 360, a[1], a[2]);
  }
  function theme(id) { return by[id] || by[DEFAULT]; }

  /* ------------------------------------------------------------------ the reach ramp: slots from a theme */
  function lOf(c) { var x = rgbOf(c); return (Math.max(x[0], x[1], x[2]) + Math.min(x[0], x[1], x[2])) / 5.1; }     // HSL lightness, 0..100
  var REFL = {}, fam;
  for (fam in REF) { REFL[fam] = []; for (i = 0; i < REF[fam].length; i++) REFL[fam].push(lOf(REF[fam][i][1])); }
  function solid(c, bg) {                                    // an 'rgba(...)' token as the colour it shows over the page
    var m = /rgba?\(([^)]*)\)/.exec(String(c));
    if (!m) return c;
    var p = m[1].split(','), al = p.length > 3 ? parseFloat(p[3]) : 1, b = rgbOf(bg), n = 0;
    for (var k = 0; k < 3; k++) n = n * 256 + Math.round(parseFloat(p[k]) * al + b[k] * (1 - al));
    return '#' + ('000000' + n.toString(16)).slice(-6);
  }
  // the earlier themes (no ramp of their own): one from their tokens, so they reach the same pages
  function derive(k) {
    var light = k.scheme === 'light', bg = k.bg, txt = k.text, line = solid(k.line, bg), dim = solid(k.dim, bg), x = k.accent, ink = light ? '#000000' : '#ffffff';
    return { n: { deep: light ? bg : mix(bg, '#000000', 0.5), bg: bg, panel: solid(k.bg2, bg), lift: mix(solid(k.bg2, bg), txt, 0.05), line: line, muted: mix(dim, bg, 0.22),
      soft: dim, text: txt, peak: ink }, a: { deep: mix(x, bg, 0.75), bronze: mix(x, bg, 0.35), accent: x, hi: mix(x, ink, 0.22), pale: mix(x, txt, 0.6) },
      g: { deep: mix(k.ok, bg, 0.7), fill: k.ok, text: k.ok, pale: mix(k.ok, txt, 0.6) }, r: { deep: mix(k.bad, bg, 0.7), fill: k.bad, text: k.bad, pale: mix(k.bad, txt, 0.6) },
      warn: k.warn };
  }
  function rampOf(t, w) {
    if (t.ramp) return w === 'stage' && t.stageRamp ? t.stageRamp : t.ramp;
    return derive(tokens(t.id, w));
  }
  function at(spec, f, L) {
    var refs = REF[f], Ls = REFL[f], last = refs.length - 1;
    if (L <= Ls[0]) return spec[refs[0][0]];
    if (L >= Ls[last]) return spec[refs[last][0]];
    for (var k = 0; k < last; k++) if (L < Ls[k + 1]) return mix(spec[refs[k][0]], spec[refs[k + 1][0]], (L - Ls[k]) / (Ls[k + 1] - Ls[k]));
    return spec[refs[last][0]];
  }
  /** every slot of a ramp: { n0: '#rrggbb', ..., a0, g0, r0 ..., warn } */
  function slots(R) {
    var out = {}, f, g, n, s;
    for (f in GRID) { g = GRID[f]; n = Math.round((g[1] - g[0]) / g[2]); for (s = 0; s <= n; s++) out[f + s] = at(R[f], f, g[0] + s * g[2]); }
    out.warn = R.warn;
    return out;
  }
  // A choice saved before AGORA (2026-11-09) may be 'olympus' only because that used to be the default (Jarvis wrote it when a Jarvis colour
  // was picked): it reads as the default (AGORA) until the owner picks a theme again; every pick after that is marked (VKEY) and wins.
  var VKEY = 'olympus.theme.v';
  function stored() { var v = get(KEY); if (v === 'olympus' && get(VKEY) !== '2') return DEFAULT; return by[v] ? v : DEFAULT; }
  function tokens(id, where) {
    var t = theme(id), out = {}, k;
    for (k in t.tokens) out[k] = t.tokens[k];
    if (where === 'stage' && t.stage) for (k in t.stage) out[k] = t.stage[k];
    out.id = t.id; out.name = t.name; out.greek = t.greek;
    return out;
  }

  // the names a page's own first-paint copy painted before this script arrived (Jarvis's <head>: 'olympus.theme.paint')
  var where = null, cur = null, painted = (window.__olyPaint && window.__olyPaint.slice) ? window.__olyPaint.slice() : [];
  var PAINT_KEY = 'olympus.theme.paint';
  /** paints <html>: the default theme writes nothing (the stylesheets' own values = today's look) */
  function apply(w, opts) {
    where = w || where || 'stage';
    var id = stored(), t = tokens(id, where), st = root.style, k, j = theme(id).jarvis;
    for (k = 0; k < painted.length; k++) st.removeProperty(painted[k]);
    painted = [];
    var paint = function (name, v) { st.setProperty(name, v); painted.push(name); };
    if (id !== DEFAULT) {
      for (k in CSS) paint('--oly-' + CSS[k], String(t[k]));
      paint('--oly-tone-rgb', rgbOf(t.accent).join(', '));
      paint('--oly-glow-rgb', rgbOf(t.glow).join(', '));
      paint('color-scheme', t.scheme);
      // the reach ramp (every tokenized stylesheet) and the feel (radius, heading / number fonts); opts.ramp = false keeps a page's own look
      if (!opts || opts.ramp === undefined || (typeof opts.ramp === 'function' ? opts.ramp(t, id) : opts.ramp)) {
        var sl = slots(rampOf(theme(id), where)), fe = theme(id).feel;
        for (k in sl) { paint('--oly-th-' + k, sl[k]); paint('--oly-th-' + k + '-rgb', rgbOf(sl[k]).join(', ')); }
        if (fe) for (k in FEEL) if (fe[k]) paint(FEEL[k], fe[k]);
      }
      // a copy of the shared part, for a page's <head> to paint before this script arrives (the Gate, the dashboard: 'olympus.theme.paint.<where>')
      var gen = {};
      for (k = 0; k < painted.length; k++) gen[painted[k]] = st.getPropertyValue(painted[k]);
      put(PAINT_KEY + '.' + where, JSON.stringify({ id: id, scheme: t.scheme, meta: t.themeColor, vars: gen }));
      if (opts && opts.jarvis && j && where === 'page') for (k = 0; k < JARVIS.length; k++) paint('--' + JARVIS[k], j[JARVIS[k]]);
      if (opts && typeof opts.extra === 'function') { var x = opts.extra(t, id) || {}; for (k in x) if (x[k] != null) paint(k, String(x[k])); }
    } else { del(PAINT_KEY + '.page'); del(PAINT_KEY + '.stage'); }
    root.setAttribute('data-oly-theme', id);
    root.setAttribute('data-oly-scheme', t.scheme);
    if (opts && opts.meta && id !== DEFAULT) {
      var m = d.querySelector('meta[name="theme-color"]');
      if (m) { if (!m.hasAttribute('data-oly-own')) m.setAttribute('data-oly-own', m.getAttribute('content') || ''); m.setAttribute('content', typeof opts.meta === 'function' ? opts.meta(t) : t.themeColor); }
    } else if (opts && opts.meta) {
      var m0 = d.querySelector('meta[name="theme-color"][data-oly-own]');
      if (m0) m0.setAttribute('content', m0.getAttribute('data-oly-own'));
    }
    // a copy of what was painted, for a page that paints before this script loads (Jarvis's <head>, which never waits on it)
    if (opts && opts.cache) {
      var vars = {};
      for (k = 0; k < painted.length; k++) vars[painted[k]] = st.getPropertyValue(painted[k]);
      if (id === DEFAULT) del(PAINT_KEY); else put(PAINT_KEY, JSON.stringify({ id: id, scheme: t.scheme, meta: t.themeColor, vars: vars }));
    }
    cur = id;
    return t;
  }
  var applyOpts = null;
  function emit() {
    var t = tokens(cur, where);
    for (var i = 0; i < subs.length; i++) { try { subs[i](t, cur); } catch (e) { /* one listener never stops the rest */ } }
  }

  /* ------------------------------------------------------------------ the scanline + film-grain layer (an option, off by default) */
  // localStorage 'olympus.grain' = '1': one static, composited layer over the page (fine scanlines + an SVG noise tile), no
  // animation, never a tap. Inline styles, so it needs no stylesheet (Jarvis, Zenith and Kalshi do not load olympus.css).
  var GRAIN_KEY = 'olympus.grain', NOISE = 'url("data:image/svg+xml,%3Csvg xmlns=%27http://www.w3.org/2000/svg%27 width=%27160%27 height=%27160%27%3E'
    + '%3Cfilter id=%27n%27%3E%3CfeTurbulence type=%27fractalNoise%27 baseFrequency=%27.9%27 numOctaves=%272%27 stitchTiles=%27stitch%27/%3E'
    + '%3CfeColorMatrix values=%270 0 0 0 .5 0 0 0 0 .5 0 0 0 0 .5 0 0 0 .55 0%27/%3E%3C/filter%3E%3Crect width=%27100%25%27 height=%27100%25%27 filter=%27url(%23n)%27/%3E%3C/svg%3E")';
  function grain() {
    var on = get(GRAIN_KEY) === '1', el = d.querySelector('.oly-grain');
    root.setAttribute('data-oly-grain', on ? 'on' : 'off');
    if (!on) { if (el && el.parentNode) el.parentNode.removeChild(el); return; }
    if (el || !d.body) return;
    el = d.createElement('div'); el.className = 'oly-grain'; el.setAttribute('aria-hidden', 'true');
    el.style.cssText = 'position:fixed;inset:0;z-index:2147483000;pointer-events:none;opacity:.5;mix-blend-mode:overlay;transform:translateZ(0);'
      + 'background-image:repeating-linear-gradient(0deg,rgba(0,0,0,.16) 0 1px,transparent 1px 3px),' + NOISE + ';background-size:auto,160px 160px';
    d.body.appendChild(el);
  }
  if (d.body) grain(); else d.addEventListener('DOMContentLoaded', grain);

  var API = {
    KEY: KEY, DEFAULT: DEFAULT, TOKENS: TOKENS, JARVIS: JARVIS, GRID: GRID, REF: REF,
    /** the reach ramp's slots for a theme: { n0: '#rrggbb' ... warn } (where = 'page' | 'stage') */
    slots: function (id, w) { var t = theme(id === undefined ? stored() : id); return slots(rampOf(t, w || where || 'stage')); },
    /** the five plain looks + the default, for a short picker (the Gate) */
    plain: function () { var o = []; for (var q = 0; q < THEMES.length; q++) if (THEMES[q].id === DEFAULT || THEMES[q].plain) o.push(THEMES[q]); return o; },
    list: function () { return THEMES.slice(); },
    get: function (id) { return theme(id); },
    id: stored,
    tokens: function (id, w) { return tokens(id === undefined ? stored() : id, w || where || 'stage'); },
    mix: mix,
    harmonise: harmonise,
    rgb: rgbOf,
    /** paint <html> for this page and keep it painted: where = 'page' | 'stage'; opts = { jarvis, cache, meta: true | fn(tokens), extra: fn(tokens, id) -> { '--app-var': value } } */
    apply: function (w, opts) { if (opts) applyOpts = opts; var t = apply(w, applyOpts); return t; },
    set: function (id) {
      if (!by[id]) id = DEFAULT;
      put(KEY, id); put(VKEY, '2');
      if (id !== cur) { apply(where, applyOpts); emit(); }
      return id;
    },
    on: function (cb) { if (typeof cb === 'function') subs.push(cb); },
    /** the scanline + grain layer: grain() = on?, grain(true | false) = set it (stored for every app) */
    grain: function (v) { if (v !== undefined) { put(GRAIN_KEY, v ? '1' : '0'); grain(); } return get(GRAIN_KEY) === '1'; },
  };
  window.OLYMPUS_THEMES = API;
  // another tab or the Jarvis frame around this app changed the theme
  window.addEventListener('storage', function (e) {
    if (e.key === GRAIN_KEY || e.key === null) grain();
    if (e.key !== KEY && e.key !== null) return;
    if (stored() !== cur && where) { apply(where, applyOpts); emit(); }
  });
})();
