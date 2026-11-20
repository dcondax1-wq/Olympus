/* OLYMPUS a11y sweep: our own iPhone rules (day-a11y 2026-11-20, tools/a11y_sweep.py). Runs inside the page, no network.
 * window.__olyA11y.run(opts) -> { rules: { <rule>: [ { sel, text, detail } ] }, meta: {...} }
 * Rules (the OLYMPUS BAR item 6):
 *   tap-target      a visible button / link / control smaller than 44 x 44 px (links inside a sentence are exempt, as in WCAG 2.5.8)
 *   small-text      visible text of 20+ characters under 15 px (body text on a phone)
 *   tiny-text       any visible text under 12 px
 *   fixed-text      text that does not grow when the root font size grows by 25 % (px text: no Dynamic Type)   [needs opts.scaled]
 *   h-scroll        the page scrolls sideways (the widest culprits listed)
 *   bottom-bar      a fixed / sticky bar touching the bottom edge with no env(safe-area-inset-bottom) rule, on a viewport-fit=cover page
 *   motion          with reduced motion on: CSS animations still running forever / longer than 1 s, 3D transforms, a requestAnimationFrame loop
 *   color-only      a money amount coloured red / green with no + / - sign and no word (up, down, loss, profit ...) next to it
 *   no-focus        set from Python (tab through the page, no visible change on the focused element)
 */
(function () {
  'use strict';
  var CLICK = 'a[href],button,[role=button],[role=link],[role=tab],[role=switch],[role=checkbox],[role=menuitem],input:not([type=hidden]),select,textarea,summary,[onclick],[tabindex]:not([tabindex="-1"])';

  function vis(el) {
    if (!el || !el.getClientRects || !el.getClientRects().length) return false;
    var s = getComputedStyle(el);
    if (s.visibility === 'hidden' || s.display === 'none' || parseFloat(s.opacity) === 0) return false;
    for (var p = el; p && p.nodeType === 1; p = p.parentElement) {
      var ps = getComputedStyle(p);
      if (parseFloat(ps.opacity) === 0 || ps.visibility === 'hidden') return false;
      if (p.getAttribute('aria-hidden') === 'true' && p !== document.body) { /* still visible to the eye: keep */ }
      if (p.hasAttribute('inert') || p.hidden) return false;
    }
    var r = el.getBoundingClientRect();
    return r.width > 1 && r.height > 1;   // a 1 px screen-reader-only box (.sr / .visually-hidden) is not on screen
  }

  function sel(el) {
    if (!el || el.nodeType !== 1) return '';
    var parts = [], n = el, depth = 0;
    while (n && n.nodeType === 1 && depth < 4) {
      var s = n.tagName.toLowerCase();
      if (n.id) { parts.unshift(s + '#' + n.id); break; }
      var c = (typeof n.className === 'string' ? n.className : (n.getAttribute('class') || '')).trim().split(/\s+/).filter(Boolean).slice(0, 2);
      if (c.length) s += '.' + c.join('.');
      parts.unshift(s);
      n = n.parentElement; depth++;
    }
    return parts.join(' > ');
  }
  function txt(el) { return ((el.getAttribute && (el.getAttribute('aria-label') || '')) || (el.innerText || el.value || '') || '').replace(/\s+/g, ' ').trim().slice(0, 60); }

  function ownText(el) {   // the element's direct text (not its children's)
    var t = '';
    for (var i = 0; i < el.childNodes.length; i++) if (el.childNodes[i].nodeType === 3) t += el.childNodes[i].nodeValue;
    return t.replace(/\s+/g, ' ').trim();
  }

  function textEls() {
    var out = [], all = document.body ? document.body.getElementsByTagName('*') : [];
    for (var i = 0; i < all.length; i++) {
      var el = all[i], tn = el.tagName;
      if (tn === 'SCRIPT' || tn === 'STYLE' || tn === 'NOSCRIPT' || tn === 'svg' || tn === 'SVG' || el.closest('svg')) continue;
      var t = ownText(el);
      if (t.length < 2 || !/[A-Za-z0-9$]/.test(t)) continue;
      if (!vis(el)) continue;
      out.push({ el: el, t: t });
    }
    return out;
  }

  function inlineInText(el) {          // a link inside a sentence (WCAG target-size inline exemption)
    if (el.tagName !== 'A') return false;
    var d = getComputedStyle(el).display;
    if (d !== 'inline') return false;
    var p = el.parentElement;
    if (!p) return false;
    var own = ownText(p);
    return own.length > 25;
  }

  function onScreenish(r) { return r.bottom > -2000 && r.right > 0 && r.left < innerWidth + 50; }

  function tapTargets() {
    var out = [], seen = new Set(), list = document.querySelectorAll(CLICK);
    for (var i = 0; i < list.length; i++) {
      var el = list[i];
      if (seen.has(el)) continue; seen.add(el);
      if (!vis(el) || el.disabled) continue;
      if (el.type === 'radio' || el.type === 'checkbox') {   // a labelled box: the label is the target
        var lab = el.closest('label') || (el.id && document.querySelector('label[for="' + el.id + '"]'));
        if (lab && vis(lab)) { var lr = lab.getBoundingClientRect(); if (lr.width >= 44 && lr.height >= 44) continue; }
      }
      if (inlineInText(el)) continue;
      // a control inside a bigger control is not its own target
      var par = el.parentElement && el.parentElement.closest(CLICK);
      var r = el.getBoundingClientRect();
      if (!onScreenish(r)) continue;
      if (r.width >= 43.5 && r.height >= 43.5) continue;
      if (par && vis(par)) { var pr = par.getBoundingClientRect(); if (pr.width >= 43.5 && pr.height >= 43.5) continue; }
      out.push({ sel: sel(el), text: txt(el), detail: Math.round(r.width) + 'x' + Math.round(r.height) });
    }
    return out;
  }

  function textSizes(scaledBefore) {
    var small = [], tiny = [], els = textEls(), sizes = [];
    for (var i = 0; i < els.length; i++) {
      var el = els[i].el, fs = parseFloat(getComputedStyle(el).fontSize);
      sizes.push(fs);
      if (el.closest('[aria-hidden="true"]')) continue;
      if (fs < 12) tiny.push({ sel: sel(el), text: els[i].t.slice(0, 60), detail: fs.toFixed(1) + 'px' });
      else if (fs < 15 && els[i].t.length >= 20) small.push({ sel: sel(el), text: els[i].t.slice(0, 60), detail: fs.toFixed(1) + 'px' });
    }
    return { small: small, tiny: tiny, els: els };
  }

  function hScroll(vw) {
    // vw = the phone's width (from the sweep): a mobile browser zooms OUT to fit wide content, so innerWidth itself grows
    var se = document.scrollingElement || document.documentElement, W = vw || innerWidth, zoomed = innerWidth > W + 1;
    var sw = Math.max(se.scrollWidth, document.body ? document.body.scrollWidth : 0);
    if (sw <= W + 1 && !zoomed) return [];
    // is the overflow actually scrollable (overflow-x: hidden on html/body hides it)?
    var hs = getComputedStyle(document.documentElement).overflowX, bs = document.body ? getComputedStyle(document.body).overflowX : 'visible';
    var before = se.scrollLeft; se.scrollLeft = 50; var moved = se.scrollLeft > 0; se.scrollLeft = before;
    if (!zoomed && !moved && (hs === 'hidden' || hs === 'clip' || bs === 'hidden' || bs === 'clip')) return [];
    var culprits = [], all = document.body.getElementsByTagName('*');
    for (var i = 0; i < all.length && culprits.length < 400; i++) {
      var el = all[i], r = el.getBoundingClientRect();
      if (r.right <= W + 1 || r.width === 0) continue;
      if (el.closest && (function (e) { for (; e && e !== document.body; e = e.parentElement) if (getComputedStyle(e).position === 'fixed') return true; return false; })(el)) continue;  // fixed layers do not widen the page
      // inside a sideways scroller of its own: fine
      var ok = false;
      for (var p = el.parentElement; p && p !== document.body; p = p.parentElement) {
        var ox = getComputedStyle(p).overflowX;
        if (ox === 'auto' || ox === 'scroll' || ox === 'hidden' || ox === 'clip') { ok = true; break; }
      }
      if (!ok) culprits.push({ el: el, w: r.right });
    }
    // keep the outermost culprits
    var top = culprits.filter(function (c) { return !culprits.some(function (o) { return o !== c && o.el.contains(c.el); }); });
    top.sort(function (a, b) { return b.w - a.w; });
    var out = top.slice(0, 5).map(function (c) { return { sel: sel(c.el), text: txt(c.el).slice(0, 40), detail: 'right edge ' + Math.round(c.w) + 'px > ' + W + 'px' }; });
    if (!out.length) out.push({ sel: 'html', text: '', detail: 'page ' + Math.max(sw, innerWidth) + 'px wide on a ' + W + 'px screen' });
    return out;
  }

  function cssRules() {
    var out = [];
    function walk(list) {
      for (var i = 0; i < list.length; i++) {
        var r = list[i];
        if (r.cssRules && !r.selectorText) { try { walk(r.cssRules); } catch (e) {} continue; }
        if (r.selectorText) out.push(r);
      }
    }
    for (var s = 0; s < document.styleSheets.length; s++) { try { walk(document.styleSheets[s].cssRules); } catch (e) { /* cross-origin */ } }
    return out;
  }

  function bottomBars() {
    var meta = document.querySelector('meta[name=viewport]'), cover = meta && /viewport-fit\s*=\s*cover/.test(meta.getAttribute('content') || '');
    if (!cover) return [];
    // a rule is safe when it uses env(safe-area-inset-bottom) itself or through a custom property (--sab: env(...); padding: var(--sab))
    var rules = cssRules(), vars = {}, grew = true;
    while (grew) {
      grew = false;
      rules.forEach(function (r) {
        for (var i = 0; i < r.style.length; i++) {
          var k = r.style[i]; if (k.indexOf('--') !== 0 || vars[k]) continue;
          var v = r.style.getPropertyValue(k);
          if (/safe-area-inset-bottom/.test(v) || Object.keys(vars).some(function (n) { return v.indexOf('var(' + n) >= 0; })) { vars[k] = 1; grew = true; }
        }
      });
    }
    var names = Object.keys(vars);
    var safe = rules.filter(function (r) { var t = r.cssText; return /safe-area-inset-bottom/.test(t) || names.some(function (n) { return t.indexOf('var(' + n) >= 0 && !/^\s*--/.test(t.split('{')[1] || ''); }); });
    var out = [], all = document.body.getElementsByTagName('*'), H = innerHeight;
    for (var i = 0; i < all.length; i++) {
      var el = all[i], s = getComputedStyle(el);
      if (s.position !== 'fixed' && !(s.position === 'sticky' && s.bottom !== 'auto')) continue;
      if (!vis(el)) continue;
      var r = el.getBoundingClientRect();
      if (r.bottom < H - 6 || r.height > H * 0.6 || r.height < 8) continue;
      if (!el.querySelector(CLICK) && !el.matches(CLICK) && ownText(el).length < 2 && !(el.innerText || '').trim()) continue;  // a decorative layer
      var ok = false;
      for (var p = el; p && p.nodeType === 1 && !ok; p = p.parentElement) {
        for (var k = 0; k < safe.length; k++) { try { if (p.matches(safe[k].selectorText)) { ok = true; break; } } catch (e) {} }
        if (p.style && /safe-area-inset-bottom/.test(p.getAttribute('style') || '')) ok = true;
        if (p !== el && getComputedStyle(p).position === 'static') break;
      }
      if (!ok) out.push({ sel: sel(el), text: txt(el).slice(0, 40), detail: s.position + ', bottom ' + Math.round(H - r.bottom) + 'px, no safe-area padding' });
    }
    return out;
  }

  function motion(rafPerSec) {
    var out = [];
    try {
      var anims = document.getAnimations ? document.getAnimations() : [];
      var n = 0;
      for (var i = 0; i < anims.length; i++) {
        var a = anims[i];
        if (a.playState !== 'running') continue;
        var t = a.effect && a.effect.getComputedTiming ? a.effect.getComputedTiming() : {};
        var forever = t.iterations === Infinity, dur = (t.duration || 0) * (t.iterations === Infinity ? 1 : (t.iterations || 1));
        if (!forever && dur < 1000) continue;
        var tg = a.effect && a.effect.target;
        if (tg && !vis(tg)) continue;
        if (n++ < 6) out.push({ sel: sel(tg), text: a.animationName || (a.constructor && a.constructor.name) || '', detail: (forever ? 'runs forever' : Math.round(dur) + 'ms') + ' with reduced motion on' });
      }
      if (n > 6) out.push({ sel: '…', text: '', detail: (n - 6) + ' more running animations' });
    } catch (e) {}
    var all = document.body.getElementsByTagName('*'), k3 = 0;
    for (var j = 0; j < all.length && k3 < 3; j++) {
      var s = getComputedStyle(all[j]);
      if (s.transform && s.transform.indexOf('matrix3d') === 0 && vis(all[j])) {
        var m = s.transform.slice(9, -1).split(',').map(parseFloat);
        // a pure 2D matrix written as 3D (translateZ(0) hacks) is not motion
        if (Math.abs(m[2]) > 0.01 || Math.abs(m[6]) > 0.01 || Math.abs(m[8]) > 0.01 || Math.abs(m[9]) > 0.01 || Math.abs(m[11]) > 0.0005) {
          out.push({ sel: sel(all[j]), text: '', detail: '3D transform with reduced motion on' }); k3++;
        }
      }
    }
    if (rafPerSec >= 20) out.push({ sel: 'window', text: 'requestAnimationFrame', detail: Math.round(rafPerSec) + ' frames/s keep drawing with reduced motion on (a 3D or canvas loop)' });
    return out;
  }

  function hueOf(c) {
    var m = /rgba?\(([^)]+)\)/.exec(c); if (!m) return null;
    var v = m[1].split(',').map(parseFloat), r = v[0] / 255, g = v[1] / 255, b = v[2] / 255;
    var mx = Math.max(r, g, b), mn = Math.min(r, g, b), d = mx - mn, l = (mx + mn) / 2;
    if (d < 0.08) return null;
    var s = d / (1 - Math.abs(2 * l - 1)); if (s < 0.3) return null;
    var h = mx === r ? ((g - b) / d) % 6 : mx === g ? (b - r) / d + 2 : (r - g) / d + 4;
    h = (h * 60 + 360) % 360;
    if (h < 22 || h >= 335) return 'red';
    if (h >= 85 && h < 165) return 'green';
    return null;
  }
  var MONEY = /^\(?\$\s?\d[\d,]*(\.\d+)?k?\)?$/i, SIGNED = /[+\-−–]|\(\$/, WORDS = /\b(up|down|loss|lost|losses|gain|gained|profit|won|win|red|green|over|under|behind|ahead|left|owed|fee|cost|paid|spent|need|to go|short|fees|out|in|payouts?|income|refund|saved|tax|net)\b/i;
  function colorOnly() {
    var out = [], els = textEls();
    for (var i = 0; i < els.length && out.length < 8; i++) {
      var t = els[i].t, el = els[i].el;
      if (!MONEY.test(t) || SIGNED.test(t)) continue;
      var hue = hueOf(getComputedStyle(el).color);
      if (!hue) continue;
      var ctx = ((el.parentElement && el.parentElement.innerText) || '').replace(/\s+/g, ' ');
      if (ctx.length < 120 && WORDS.test(ctx)) continue;
      if (el.getAttribute('aria-label') && WORDS.test(el.getAttribute('aria-label'))) continue;
      out.push({ sel: sel(el), text: t, detail: hue + ' amount with no sign or word' });
    }
    return out;
  }

  window.__olyA11y = {
    vis: vis, sel: sel,
    snapshotSizes: function () {
      var els = textEls();
      window.__olySizes = els.map(function (x) { return [x.el, parseFloat(getComputedStyle(x.el).fontSize)]; });
      return els.length;
    },
    fixedText: function (factor) {     // after the root font size went x factor: which text did not grow
      var out = [], n = 0, list = window.__olySizes || [];
      for (var i = 0; i < list.length; i++) {
        var el = list[i][0], before = list[i][1];
        if (!el.isConnected || !vis(el) || el.closest('[aria-hidden="true"]')) continue;
        n++;
        var now = parseFloat(getComputedStyle(el).fontSize);
        if (now < before * (1 + (factor - 1) * 0.5)) out.push({ sel: sel(el), text: ownText(el).slice(0, 50), detail: before.toFixed(1) + 'px stays ' + now.toFixed(1) + 'px' });
      }
      return { fails: out, checked: n };
    },
    run: function (opts) {
      opts = opts || {};
      var r = {}, ts = textSizes();
      if (opts.layout !== false) {
        r['tap-target'] = tapTargets();
        r['small-text'] = ts.small;
        r['tiny-text'] = ts.tiny;
        r['h-scroll'] = hScroll(opts.vw);
        r['bottom-bar'] = bottomBars();
      }
      if (opts.motion) r.motion = motion(opts.rafPerSec || 0);
      if (opts.color !== false) r['color-only'] = colorOnly();
      return { rules: r, meta: { texts: ts.els.length, controls: document.querySelectorAll(CLICK).length, title: document.title, w: innerWidth, h: innerHeight, theme: document.documentElement.getAttribute('data-oly-theme') || '', scheme: document.documentElement.getAttribute('data-oly-scheme') || '', bg: getComputedStyle(document.body).backgroundColor } };
    }
  };
})();
