/* OLYMPUS themes (2026-11-03, docs/OLYMPUS_DESIGN.md "Themes"): whole-system palettes as DATA, and the small engine that applies
 * them. One key on the shared origin, localStorage 'olympus.theme' = a theme id; Jarvis's Look sheet writes it, and every page
 * (Jarvis, the nine 3D apps, Zenith, Kalshi) reads it at start and on the 'storage' event.
 *
 * A classic ES5 script (no module, never throws). It sets window.OLYMPUS_THEMES:
 *   list()            the themes in picker order: [{ id, name, greek, tag, scheme, tokens, stage?, jarvis? }]
 *   id() / get(id)    the stored id (unknown or missing = 'olympus') / one theme
 *   tokens(id, where) the resolved palette. where = 'page' (Jarvis: the full palette, light themes light) or 'stage' (the 3D
 *                     apps, Zenith, Kalshi: surfaces that are dark by design; a light theme gives its dark 'stage' variant there)
 *   apply(where)      paints <html>: data-oly-theme / data-oly-scheme, the --oly-* tokens, color-scheme and the theme-color meta.
 *                     The default theme writes NOTHING inline: the stylesheets' own values stay, so it is today's look exactly.
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
  var KEY = 'olympus.theme', DEFAULT = 'olympus';
  // the token names every theme must define (CSS ones become --oly-<name>; the 3D ones go to the scenes)
  var TOKENS = ['bg', 'bg2', 'glass', 'glass2', 'line', 'edge', 'text', 'dim', 'accent', 'accent2', 'glow', 'ok', 'bad', 'warn', 'shadow',
    'scheme', 'themeColor', 'fog', 'sky', 'emissive', 'bloom', 'mix', 'harmony'];
  var CSS = { bg: 'bg', bg2: 'bg2', glass: 'glass', glass2: 'glass2', line: 'line', edge: 'edge', text: 'text', dim: 'dim', accent: 'tone',
    accent2: 'tone2', glow: 'glow', ok: 'ok', bad: 'bad', warn: 'warn', shadow: 'shadow', fog: 'fog', sky: 'sky', emissive: 'emissive', bloom: 'bloom' };
  // Jarvis's own palette names (jarvis.css :root[data-theme]): a theme that is not the default paints them too
  var JARVIS = ['bg', 'bg2', 'pr', 'txt', 'mut', 'dim', 'dim2', 'dim3', 'c', 'c2', 'c3', 'cr', 'cr2', 'cr3', 'tint', 'neb1', 'neb2', 'neb3', 'grid', 'scan'];

  /* ------------------------------------------------------------------ the themes (data only) */
  var THEMES = [
    { id: 'olympus', name: 'Olympus', greek: 'ΟΛΥΜΠΟΣ', tag: 'Violet + gold · default', scheme: 'dark',
      // today's look: these equal olympus.css's :root values (the default writes nothing inline; Jarvis keeps its own colour)
      tokens: { bg: '#04050c', bg2: '#0d0620', glass: 'rgba(9, 11, 22, .74)', glass2: 'rgba(14, 8, 30, .92)', line: 'rgba(255, 255, 255, .12)',
        edge: 'rgba(168, 85, 247, .38)', text: '#f3f5fb', dim: 'rgba(214, 220, 236, .66)', accent: '#a855f7', accent2: '#ffc94a', glow: '#a95cff',
        ok: '#4ade80', bad: '#ff4d6d', warn: '#fbbf24', shadow: '0 12px 40px rgba(0, 0, 0, .45)', scheme: 'dark', themeColor: '#000000',
        fog: '#04050c', sky: '#0d0620', emissive: '#a855f7', bloom: '#c084fc', mix: 0, harmony: 0 },
      jarvis: null },
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
  function stored() { var v = get(KEY); return by[v] ? v : DEFAULT; }
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
      if (opts && opts.jarvis && j && where === 'page') for (k = 0; k < JARVIS.length; k++) paint('--' + JARVIS[k], j[JARVIS[k]]);
      if (opts && typeof opts.extra === 'function') { var x = opts.extra(t, id) || {}; for (k in x) if (x[k] != null) paint(k, String(x[k])); }
    }
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
    KEY: KEY, DEFAULT: DEFAULT, TOKENS: TOKENS, JARVIS: JARVIS,
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
      put(KEY, id);
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
