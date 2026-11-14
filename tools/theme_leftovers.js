/* OLYMPUS theme reach: the AGORA colours left on a page under a theme (tools/theme_shots.py --leftovers, tests/test_olympus_themes.py).
 * Evaluated in the page (Playwright page.evaluate(src)(args)). Under a theme other than the default, any visible element whose text colour,
 * background colour or border colour is still one of AGORA's own warm browns / golds (the literal palette the stylesheets were written in)
 * did not follow the theme. Returns [{ sel, prop, value, text }] (at most `max`), with the stylesheet rule that set it when one is found.
 * Plain ES2017, no imports. */
(function () {
  return function (opts) {
    opts = opts || {};
    var max = opts.max || 40, out = [], seen = {};
    // AGORA's warm neutrals and golds, by hue / chroma: an rgb() that sits in them (and is not a theme's own colour) is a leftover
    var own = {}, st = document.documentElement.style;
    (opts.allow || []).forEach(function (c) { own[c] = 1; });
    for (var q = 0; q < st.length; q++) {                       // the theme's own painted colours (its warn may be amber, its accent gold) are not leftovers
      var v = st.getPropertyValue(st[q]).trim(), m = /^#([0-9a-f]{6})$/i.exec(v);
      if (m) { var n = parseInt(m[1], 16); own['rgb(' + (n >> 16) + ', ' + ((n >> 8) & 255) + ', ' + (n & 255) + ')'] = 1; }
    }
    function key(c) { var x = parse(c); return x ? 'rgb(' + x.r + ', ' + x.g + ', ' + x.b + ')' : c; }
    function parse(c) { var m = /rgba?\(([^)]+)\)/.exec(c || ''); if (!m) return null; var p = m[1].split(/[ ,/]+/).filter(Boolean).map(parseFloat); return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 }; }
    function agora(c) {
      var x = parse(c); if (!x || x.a < 0.35) return false;
      var mx = Math.max(x.r, x.g, x.b), mn = Math.min(x.r, x.g, x.b), ch = mx - mn; if (ch < 6) return false;      // grey: any theme
      var h = 0; if (mx === x.r) h = ((x.g - x.b) / ch) % 6; else if (mx === x.g) h = (x.b - x.r) / ch + 2; else h = (x.r - x.g) / ch + 4; h *= 60; if (h < 0) h += 360;
      return h >= 18 && h <= 52 && x.r > x.b + 4;                                                                          // warm brown / tan / gold
    }
    function sel(e) { var s = e.tagName.toLowerCase(); if (e.id) s += '#' + e.id; if (e.className && typeof e.className === 'string') s += '.' + e.className.trim().split(/\s+/).slice(0, 2).join('.'); return s; }
    function rule(e, prop) {
      for (var i = 0; i < document.styleSheets.length; i++) {
        var rs; try { rs = document.styleSheets[i].cssRules; } catch (x) { continue; }
        var hit = scan(rs, e, prop, document.styleSheets[i].href || 'inline <style>');
        if (hit) return hit;
      }
      return '';
    }
    function scan(rs, e, prop, src) {
      for (var j = rs.length - 1; j >= 0; j--) {
        var r = rs[j];
        if (r.cssRules && !r.selectorText) { var h = scan(r.cssRules, e, prop, src); if (h) return h; continue; }
        if (!r.selectorText || !r.style) continue;
        var v = r.style.getPropertyValue(prop) || (prop === 'background-color' ? r.style.getPropertyValue('background') : '');
        if (!v) continue;
        try { if (e.matches(r.selectorText)) return (src.split('/').pop() || src) + ' :: ' + r.selectorText.slice(0, 90) + ' { ' + prop + ': ' + v.slice(0, 80) + ' }'; } catch (x) { /* a selector this engine does not take */ }
      }
      return '';
    }
    var all = document.querySelectorAll('body *');
    for (var i = 0; i < all.length && out.length < max; i++) {
      var e = all[i], r = e.getBoundingClientRect();
      if (r.width < 2 || r.height < 2 || r.bottom < 0 || r.top > innerHeight * (opts.screens || 1.5)) continue;
      if (e.closest('.g-swatches, .othemes, #themes, [aria-hidden="true"] svg')) continue;     // the theme pickers show every theme on purpose
      var cs = getComputedStyle(e);
      if (cs.visibility === 'hidden' || +cs.opacity === 0 || cs.display === 'none') continue;
      var props = [['background-color', cs.backgroundColor], ['border-top-color', +cs.borderTopWidth.replace('px', '') > 0 ? cs.borderTopColor : '']];
      var hasText = false; for (var c = e.firstChild; c; c = c.nextSibling) if (c.nodeType === 3 && c.nodeValue.trim()) { hasText = true; break; }
      if (hasText) props.push(['color', cs.color]);
      for (var k = 0; k < props.length; k++) {
        var v = props[k][1];
        if (!v || own[key(v)] || !agora(v)) continue;
        var sk = sel(e) + props[k][0] + v; if (seen[sk]) continue; seen[sk] = 1;
        out.push({ sel: sel(e), prop: props[k][0], value: v, text: (e.textContent || '').trim().slice(0, 40), rule: rule(e, props[k][0]) });
        if (out.length >= max) break;
      }
    }
    return out;
  };
})()
