/* OLYMPUS look QA (2026-11-14, team T2 "lock down the looks"; tools/theme_shots.py --qa, tests/test_olympus_themes.py).
 * Evaluated in the page (Playwright: page.evaluate("(a) => (" + src + ")(a)", opts)). Plain ES2017, no imports, reads only.
 * Under a look it reports, from the page's computed styles:
 *   texts     every visible text node (+ inputs, SVG text): its colour, its real background (the layers under it composited: colours,
 *             gradient stops, translucency, the parents' opacity) and its WCAG contrast; low = under 4.5:1 (3:1 for large text).
 *             Each row has its box, so theme_shots.py checks the ones on screen against the screenshot's own pixels.
 *   left      leftovers: a visible element (or its ::before / ::after) whose colour, background, border, outline, SVG fill / stroke, shadow
 *             or gradient is still one of AGORA's own literal colours (opts.agora: 'r,g,b' strings) while the look should repaint it.
 *   money     the gains and losses (+$ / -$, .up / .dn / .pos / .neg / gain / loss ...): green / red hue, readable.
 *   meta      the theme-color meta, color-scheme, ::selection, scrollbar colours, the placeholder ink, the first painted frame (window.__olyQAPaint).
 * window.__olyQA keeps the helpers (focus ring checks after a Tab: __olyQA.focus()). */
(function () {
  return function (opts) {
    opts = opts || {};
    const W = innerWidth, H = innerHeight, max = opts.max || 60, d = document, root = d.documentElement;
    const SKIP = '.g-swatches, .g-sw, .g-mini, .g-combo, #looks, #lookMix, #lookTop, #lookBar, .othemes, #themes, #olyThemes, .lk-pick, [data-oly-qa-skip], .oly-grain';
    // scene art keeps its own colours like a 3D canvas does (the 2D fallback scenes, the people's painted portraits, Polis's painted clay,
    // bronze and wood: polis-life.js) and the app tiles in their own identity colours (Polis, Jarvis): never a leftover
    const ART = 'svg.s2d, .pp-portrait, canvas, video, img, svg[class*="pl-"], a.ship svg, a.dl > i, .og-ic, .pl-tablet, li.motion > svg';
    // ---------------------------------------------------------------- colours: any CSS colour -> [r, g, b, a] (0-255, a 0-1)
    const cx = d.createElement('canvas'); cx.width = cx.height = 1; const g2 = cx.getContext('2d', { willReadFrequently: true }); const cache = new Map();
    function col(v) {
      if (v == null) return null;
      v = String(v).trim();
      if (!v || v === 'none' || v === 'currentcolor') return null;
      if (cache.has(v)) return cache.get(v);
      let out = null, m = /^rgba?\(([^)]+)\)$/i.exec(v);
      if (m) { const p = m[1].split(/[\s,/]+/).filter(Boolean).map((x) => (/%$/.test(x) ? parseFloat(x) / 100 : parseFloat(x))); out = [p[0], p[1], p[2], p.length > 3 ? p[3] : 1]; }
      else if (v === 'transparent') out = [0, 0, 0, 0];
      else if ((m = /^color\(srgb\s+([^)]+)\)$/i.exec(v))) { const p = m[1].split(/[\s/]+/).filter(Boolean).map(parseFloat); out = [p[0] * 255, p[1] * 255, p[2] * 255, p.length > 3 ? p[3] : 1]; }
      else {
        try { g2.clearRect(0, 0, 1, 1); g2.fillStyle = '#000'; g2.fillStyle = v; g2.fillRect(0, 0, 1, 1); const x = g2.getImageData(0, 0, 1, 1).data; out = [x[0], x[1], x[2], x[3] / 255]; } catch (e) { out = null; }
      }
      if (out) out = out.map((n, i) => (i < 3 ? Math.round(n) : Math.round(n * 1000) / 1000));
      cache.set(v, out);
      return out;
    }
    const COLRE = /(?:rgba?|color|oklab|oklch|lab|lch|hsla?)\([^()]*(?:\([^()]*\)[^()]*)*\)|#[0-9a-f]{3,8}\b|\btransparent\b/gi;
    const stopsOf = (img) => (img && img !== 'none' ? (img.match(COLRE) || []).map(col).filter(Boolean) : []);
    const over = (f, b) => { const a = f[3]; return [f[0] * a + b[0] * (1 - a), f[1] * a + b[1] * (1 - a), f[2] * a + b[2] * (1 - a), 1]; };
    const lin = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    const lum = (c) => 0.2126 * lin(c[0]) + 0.7152 * lin(c[1]) + 0.0722 * lin(c[2]);
    const ratio = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
    const hex = (c) => '#' + c.slice(0, 3).map((n) => ('0' + Math.round(n).toString(16)).slice(-2)).join('');
    function hue(c) {
      const r = c[0] / 255, g = c[1] / 255, b = c[2] / 255, mx = Math.max(r, g, b), mn = Math.min(r, g, b), dd = mx - mn;
      if (dd < 0.08) return -1;                                                  // a grey: no hue
      let h = mx === r ? ((g - b) / dd) % 6 : mx === g ? (b - r) / dd + 2 : (r - g) / dd + 4; h *= 60; return h < 0 ? h + 360 : h;
    }
    function sel(e) {
      let s = e.tagName.toLowerCase(); if (e.id) s += '#' + e.id;
      const c = typeof e.className === 'string' ? e.className : (e.className && e.className.baseVal) || '';
      if (c.trim()) s += '.' + c.trim().split(/\s+/).slice(0, 2).join('.');
      return s;
    }
    function path(e) { const p = []; for (let x = e; x && x !== d.body && p.length < 3; x = x.parentElement) p.unshift(sel(x)); return p.join(' > '); }
    // ---------------------------------------------------------------- the page's own base (what shows where nothing is painted)
    const rcs = getComputedStyle(root), bcs = d.body ? getComputedStyle(d.body) : null;
    function canvasBase() {
      const r = col(rcs.backgroundColor);
      if (r && r[3] > 0) return [over(r, [255, 255, 255, 1])].concat(stopsOf(rcs.backgroundImage).filter((s) => s[3] > 0).map((s) => over(s, over(r, [255, 255, 255, 1]))));
      const b = bcs ? col(bcs.backgroundColor) : null;                            // the body's background paints the canvas when the root has none
      if (b && b[3] > 0) return [over(b, [255, 255, 255, 1])];
      return [[255, 255, 255, 1]];
    }
    const BASE = canvasBase();
    /** the background candidates under an element: [[r, g, b, 1] ...] (each gradient stop gives one) and how sure we are */
    function bgOf(el) {
      const layers = []; let fade = 1, unsure = '';
      for (let e = el; e && e.nodeType === 1; e = e.parentElement) {
        const cs = getComputedStyle(e);
        fade *= +cs.opacity;
        if (e === root) break;                                                   // the root is the canvas base
        const bc = col(cs.backgroundColor), img = cs.backgroundImage, clipText = /text/.test(cs.backgroundClip + ' ' + (cs.webkitBackgroundClip || ''));
        let st = clipText ? [] : stopsOf(img);
        if (!clipText && img && /url\(/.test(img)) unsure = unsure || 'image';
        if ((cs.backdropFilter && cs.backdropFilter !== 'none') || (cs.webkitBackdropFilter && cs.webkitBackdropFilter !== 'none')) unsure = unsure || '';
        layers.push({ bc: bc && bc[3] > 0 ? bc : null, st: st.length ? st : null });
        const opaqueStops = st.length && st.every((s) => s[3] >= 0.99) && !/url\(/.test(img);
        if ((bc && bc[3] >= 0.99) || opaqueStops) return { cands: compose(layers, null), fade, unsure };
      }
      return { cands: compose(layers, BASE), fade, unsure };
    }
    function compose(layers, base) {
      let c = base ? base.slice() : null;
      for (let i = layers.length - 1; i >= 0; i--) {
        const L = layers[i];
        if (L.bc) c = c ? c.map((x) => over(L.bc, x)) : [over(L.bc, [255, 255, 255, 1])];
        if (L.st) {
          const nx = []; const from = c || [[255, 255, 255, 1]];
          for (const x of from) for (const s of L.st) nx.push(over(s, x));
          if (L.st.some((s) => s[3] < 0.99)) for (const x of from) nx.push(x);
          c = dedupe(nx);
        }
      }
      return dedupe(c || BASE);
    }
    function dedupe(list) { const seen = {}, out = []; for (const x of list) { const k = x.slice(0, 3).map(Math.round).join(','); if (!seen[k]) { seen[k] = 1; out.push(x); } } return out.slice(0, 16); }
    const visible = (cs) => cs.visibility !== 'hidden' && cs.display !== 'none' && +cs.opacity > 0.02;
    function shown(e) {
      for (let x = e; x && x.nodeType === 1; x = x.parentElement) { const cs = getComputedStyle(x); if (!visible(cs)) return false; if (x.hidden) return false; }
      return true;
    }
    function large(cs) { const px = parseFloat(cs.fontSize) || 16, w = parseInt(cs.fontWeight, 10) || 400; return px >= 24 || (px >= 18.66 && w >= 700); }
    function onTop(e, r) {
      const x = Math.min(W - 1, Math.max(0, r.left + Math.min(r.width / 2, 12))), y = Math.min(H - 1, Math.max(0, r.top + r.height / 2));
      const t = d.elementFromPoint(x, y);
      return !!t && (t === e || e.contains(t) || t.contains(e));
    }

    // ---------------------------------------------------------------- 1. text contrast
    const texts = [], low = [];
    // opts.scope: only what sits inside it (a sheet, a toast: theme_shots.py's overlay check)
    const all = opts.scope ? [...d.querySelectorAll('body *')].filter((e) => e.closest(opts.scope)) : d.querySelectorAll('body *');
    const until = opts.screens ? opts.screens * H : Infinity;
    for (let i = 0; i < all.length; i++) {
      const e = all[i];
      if (e.closest(SKIP) || e.closest('[aria-hidden="true"]') || /^(SCRIPT|STYLE|NOSCRIPT|TEMPLATE|OPTION)$/.test(e.tagName)) continue;
      const svgText = e instanceof SVGElement && /^(text|tspan)$/.test(e.tagName.toLowerCase());
      const field = /^(INPUT|TEXTAREA|SELECT)$/.test(e.tagName) && !/^(checkbox|radio|range|color|hidden|button|submit|image|file)$/.test(e.type || '');
      let has = field ? !!(e.value || '').trim() : false;
      if (!field) for (let c = e.firstChild; c; c = c.nextSibling) if (c.nodeType === 3 && c.nodeValue.trim()) { has = true; break; }
      if (!has) continue;
      const r = e.getBoundingClientRect();
      if (r.width < 2 || r.height < 2 || r.bottom < 0 || r.top > until || r.right < 0 || r.left > W) continue;
      const cs = getComputedStyle(e);
      if (!shown(e)) continue;
      if (e.disabled || e.getAttribute('aria-disabled') === 'true') continue;          // inactive controls: WCAG leaves them out
      let fg = col(svgText ? cs.fill : (cs.webkitTextFillColor && cs.webkitTextFillColor !== cs.color ? cs.webkitTextFillColor : cs.color));
      if (!fg || fg[3] === 0) continue;                                                // transparent ink (gradient text): not measured here
      const B = bgOf(e), need = large(cs) ? 3 : 4.5;
      const f = fg.slice(); f[3] = f[3] * B.fade;
      let worst = 99, wb = null;
      for (const b of B.cands) { const v = ratio(over(f, b), b); if (v < worst) { worst = v; wb = b; } }
      const row = { sel: path(e), text: (field ? e.value : e.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 40), fg: hex(fg), a: Math.round(f[3] * 100) / 100,
        bg: hex(wb), cands: B.cands.length, ratio: Math.round(worst * 100) / 100, need, unsure: B.unsure,
        box: [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)], top: r.top < H && r.bottom > 0 ? onTop(e, r) : null };
      texts.push(row);
      if (worst < need) low.push(row);
    }

    // ---------------------------------------------------------------- 2. leftovers: AGORA's own literal colours still on screen
    const own = {};
    const st = root.style;
    for (let q = 0; q < st.length; q++) {                                        // the look's own painted colours are never leftovers
      const v = st.getPropertyValue(st[q]).trim(), c = /^#[0-9a-f]{6}$/i.test(v) ? col(v) : /^\d{1,3},\s*\d{1,3},\s*\d{1,3}$/.test(v) ? v.split(',').map(Number) : null;
      if (c) own[c.slice(0, 3).join(',')] = 1;
    }
    const AG = {}; (opts.agora || []).forEach((k) => { if (!own[k]) AG[k] = 1; });
    const isAg = (c) => c && c[3] >= (opts.minAlpha || 0.12) && AG[c.slice(0, 3).join(',')];
    const left = [], seenL = {};
    const PROPS = ['color', 'background-color', 'border-top-color', 'border-right-color', 'border-bottom-color', 'border-left-color', 'outline-color', 'fill', 'stroke', 'text-decoration-color', 'caret-color'];
    function scanStyle(e, cs, pseudo) {
      for (const p of PROPS) {
        if (p === 'color' && !pseudo) { let t = false; for (let c = e.firstChild; c; c = c.nextSibling) if (c.nodeType === 3 && c.nodeValue.trim()) { t = true; break; } if (!t && !(e instanceof SVGElement)) continue; }
        if (/^border-(\w+)-color$/.test(p) && !(parseFloat(cs.getPropertyValue(p.replace('-color', '-width'))) > 0)) continue;
        if (p === 'outline-color' && (cs.outlineStyle === 'none' || !(parseFloat(cs.outlineWidth) > 0))) continue;
        if ((p === 'fill' || p === 'stroke') && !(e instanceof SVGElement)) continue;
        if (p === 'stroke' && (cs.stroke === 'none' || !(parseFloat(cs.strokeWidth) > 0))) continue;
        if (p === 'text-decoration-color' && !/underline|line-through|overline/.test(cs.textDecorationLine)) continue;
        if (p === 'caret-color' && !/^(INPUT|TEXTAREA)$/.test(e.tagName)) continue;
        const v = cs.getPropertyValue(p), c = col(v);
        if (isAg(c)) add(e, (pseudo || '') + p, v);
      }
      for (const p of ['background-image', 'box-shadow', 'text-shadow']) {
        const v = cs.getPropertyValue(p);
        if (!v || v === 'none' || /url\(/.test(v) && p === 'background-image' && !/gradient/.test(v)) continue;
        const hit = (v.match(COLRE) || []).map(col).find(isAg);
        if (hit) add(e, (pseudo || '') + p, v.slice(0, 90));
      }
    }
    function add(e, p, v) {
      const k = sel(e) + p + v; if (seenL[k]) return; seenL[k] = 1;
      if (left.length < max) left.push({ sel: path(e), prop: p, value: v, text: (e.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 30) });
    }
    for (let i = 0; i < all.length && left.length < max; i++) {
      const e = all[i];
      if (e.closest(SKIP) || e.closest(ART)) continue;
      const r = e.getBoundingClientRect();
      if (r.width < 1 || r.height < 1) continue;
      const cs = getComputedStyle(e);
      if (!visible(cs) || !shown(e)) continue;
      scanStyle(e, cs, '');
      for (const ps of ['::before', '::after']) {
        const pc = getComputedStyle(e, ps);
        if (!pc || pc.content === 'none' || pc.content === 'normal' || pc.display === 'none') continue;
        scanStyle(e, pc, ps);
      }
    }
    const selBg = (() => { try { return d.body ? getComputedStyle(d.body, '::selection').backgroundColor : ''; } catch (e) { return ''; } })();
    for (const [name, c] of (opts.scope ? [] : [['html background', rcs.backgroundColor], ['body background', bcs && bcs.backgroundColor], ['html scrollbar', rcs.scrollbarColor], ['::selection', selBg]])) {
      const hit = (String(c || '').match(COLRE) || []).map(col).find(isAg);
      if (hit) left.push({ sel: name, prop: name, value: c, text: '' });
    }

    // ---------------------------------------------------------------- 3. gains and losses: green and red, readable
    const MONEY_CLS = /(^|[\s_-])(up|dn|down|pos|neg|good|bad|gain|gains|loss|losses|win|lose|profit|plus|minus|green|red|ok|ag-good|ag-bad)($|[\s_-])/i;
    const money = { gains: 0, losses: 0, wrong: [], low: [] };
    for (const t of texts) {
      if (t.ratio === undefined) continue;
    }
    for (let i = 0; i < all.length; i++) {
      const e = all[i];
      if (e.closest(SKIP) || e.closest('[aria-hidden="true"]')) continue;
      let txt = ''; for (let c = e.firstChild; c; c = c.nextSibling) if (c.nodeType === 3) txt += c.nodeValue;
      txt = txt.trim();
      if (!txt || txt.length > 24) continue;
      const signed = /^[+−–-]\s?\$?\s?[\d.,]+[kKmM%R]?$|^[+−–-]?\$\s?[\d.,]+[kKmM]?$/.test(txt) && /[+−–-]/.test(txt.charAt(0) + txt.charAt(1));
      const cls = (typeof e.className === 'string' ? e.className : '') + ' ' + ((e.parentElement && typeof e.parentElement.className === 'string') ? e.parentElement.className : '');
      if (!signed && !MONEY_CLS.test(cls)) continue;
      const r = e.getBoundingClientRect(); if (r.width < 2 || r.height < 2) continue;
      const cs = getComputedStyle(e); if (!shown(e)) continue;
      const fg = col(cs.color); if (!fg) continue;
      const h = hue(fg), green = h >= 70 && h <= 175, red = h >= 330 || (h >= 0 && h <= 28);
      const plus = /^\+/.test(txt), minus = /^[−–-]/.test(txt);
      if (green) money.gains++; if (red) money.losses++;
      if ((plus && red) || (minus && green)) money.wrong.push({ sel: path(e), text: txt, color: hex(fg) });
      if (h >= 0 && (green || red)) {
        const B = bgOf(e), f = fg.slice(); f[3] *= B.fade;
        let worst = 99; for (const b of B.cands) worst = Math.min(worst, ratio(over(f, b), b));
        if (worst < (large(cs) ? 3 : 4.5)) money.low.push({ sel: path(e), text: txt, color: hex(fg), ratio: Math.round(worst * 100) / 100 });
      }
    }

    // ---------------------------------------------------------------- 4. the page frame: status bar, scheme, selection, scrollbar, placeholders, the first frame
    const metaEl = d.querySelector('meta[name="theme-color"]');
    const selC = (() => { try { return getComputedStyle(d.body, '::selection').backgroundColor; } catch (e) { return ''; } })();
    const ph = [];
    d.querySelectorAll('input[placeholder], textarea[placeholder]').forEach((e) => {
      if (e.closest(SKIP) || !shown(e) || e.value) return;
      const r = e.getBoundingClientRect(); if (r.width < 2 || r.height < 2) return;
      const pc = col(getComputedStyle(e, '::placeholder').color); if (!pc) return;
      const B = bgOf(e); let worst = 99; for (const b of B.cands) worst = Math.min(worst, ratio(over(pc, b), b));
      ph.push({ sel: path(e), color: hex(pc), a: pc[3], ratio: Math.round(worst * 100) / 100 });
    });
    const canvases = [...d.querySelectorAll('canvas, video')].map((c) => c.getBoundingClientRect()).filter((r) => r.width > 40 && r.height > 40 && r.bottom > 0 && r.top < H)
      .map((r) => [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)]);
    const pageTop = (() => { const c = BASE[0]; return hex(c); })();
    const out = {
      theme: root.getAttribute('data-oly-theme'), style: root.getAttribute('data-oly-style'), scheme: root.getAttribute('data-oly-scheme'),
      colorScheme: rcs.colorScheme, meta: metaEl ? metaEl.getAttribute('content') : null, pageBase: pageTop, selection: selC, scrollbar: rcs.scrollbarColor,
      first: window.__olyQAPaint || null, nTexts: texts.length, low: low.slice(0, max), nLow: low.length, texts: opts.allTexts ? texts : texts.filter((t) => t.top !== null).slice(0, 400),
      left, money, placeholders: ph, canvases, sx: root.scrollWidth - W, h: root.scrollHeight,
    };
    window.__olyQA = {
      col, ratio, over, bgOf, hex,
      /** the focused element's ring: { sel, kind, color, ratio (ring vs the background under it), ok } */
      focus() {
        const e = d.activeElement; if (!e || e === d.body || e === root) return null;
        const cs = getComputedStyle(e), B = bgOf(e.parentElement || e), r = e.getBoundingClientRect();
        let ring = null, kind = '';
        if (cs.outlineStyle !== 'none' && parseFloat(cs.outlineWidth) >= 1) { ring = col(cs.outlineColor); kind = 'outline ' + cs.outlineWidth; }
        else if (cs.boxShadow && cs.boxShadow !== 'none') { const m = (cs.boxShadow.match(COLRE) || []).map(col).filter((c) => c && c[3] > 0.3); if (m.length) { ring = m[0]; kind = 'shadow'; } }
        let worst = 0;
        if (ring) { worst = 99; for (const b of B.cands) worst = Math.min(worst, ratio(over(ring, b), b)); }
        return { sel: path(e), kind, color: ring ? hex(ring) : null, ratio: Math.round(worst * 100) / 100, ok: !!ring && worst >= 3, box: [Math.round(r.left), Math.round(r.top), Math.round(r.width), Math.round(r.height)] };
      },
    };
    return out;
  };
})()
