/* OLYMPUS gate-nav (2026-11-12): the way back to the Gate and a "Go to..." search sheet, on any app. One line in the app's <head>, after agora-ui.js:
 *     <script src="../olympus/gate-nav.js?v=g1" defer></script>
 * - The app's existing back link ("< Olympus" from the AGORA shell, or an own "Olympus" link) becomes "< Gate" and opens the Gate (gate/). A page with no
 *   back link gets a slim row (Gate on the left, Go to on the right) above its header: in the page flow, never floating over its content.
 * - "Go to" sits on the right of the same top row (and as a 44 px icon in the compact bar that appears on scroll): a sheet with a search box (name, purpose,
 *   plain words: olympus/gate-catalog.js, the Gate's own list), the last apps opened, Start here and the four districts. Nothing near Jarvis's orb corner.
 * - Remembers this app as opened (localStorage 'gate.recent.v1', the Gate's Recent row), in try / catch. Inside Jarvis (framed) it only remembers.
 * Classic script, ES5, no markup from data (textContent / createElementNS), same-origin files only, no other storage, no network but the catalog file. */
(function () {
  'use strict';
  var d = document, w = window;
  if (w.OLYMPUS_GATE_NAV) return;
  var me = d.currentScript, NS = 'http://www.w3.org/2000/svg', KEY = 'gate.recent.v1';
  var framed = (function () { try { return w.top !== w; } catch (e) { return true; } })();
  var root = (function () { try { return new w.URL('../', me && me.src ? me.src : w.location.href).href; } catch (e) { return '../'; } })();
  var GATE = root + 'gate/index.html';
  var appId = (function () {
    var a = me && me.getAttribute('data-app'); if (a) return a;
    var o = d.querySelector('script[data-app]'); if (o) return o.getAttribute('data-app');
    var m = /\/([a-z0-9-]+)\/(index\.html)?$/.exec(w.location.pathname || ''); return m ? m[1] : '';
  })();
  var S = { placed: false, sheet: null, opener: null, cat: null, catTried: false };

  function el(tag, cls, text) { var e = d.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function sv(tag, attrs) { var e = d.createElementNS(NS, tag); for (var k in attrs) if (Object.prototype.hasOwnProperty.call(attrs, k)) e.setAttribute(k, attrs[k]); return e; }
  function clear(n) { while (n && n.firstChild) n.removeChild(n.firstChild); }
  function recent() { try { var r = JSON.parse(w.localStorage.getItem(KEY) || '[]'); return r instanceof Array ? r.filter(function (x) { return typeof x === 'string'; }) : []; } catch (e) { return []; } }
  function remember(id) { if (!id) return; try { var r = recent().filter(function (x) { return x !== id; }); r.unshift(id); w.localStorage.setItem(KEY, JSON.stringify(r.slice(0, 8))); } catch (e) { /* private mode */ } }
  function hrefOf(a) { var p = a.path || ''; return root + (p === '' ? 'index.html' : /\/$/.test(p) ? p + 'index.html' : p); }
  function searchIcon(cls) { var s = sv('svg', { 'class': cls || 'gn-ic', viewBox: '0 0 24 24', 'aria-hidden': 'true' }); s.appendChild(sv('circle', { cx: '10.5', cy: '10.5', r: '6.5' })); s.appendChild(sv('path', { d: 'M15.5 15.5 21 21' })); return s; }
  function backIcon() { var s = sv('svg', { 'class': 'gn-ic', viewBox: '0 0 24 24', 'aria-hidden': 'true' }); s.appendChild(sv('path', { d: 'M15 5l-7 7 7 7' })); return s; }

  remember(appId);
  w.OLYMPUS_GATE_NAV = { v: 1, gate: GATE, app: appId, open: function () { openSheet(null); }, close: closeSheet, placed: function () { return S.placed; } };
  if (framed) return;

  /* ------------------------------------------------------------------------------------------ the look (AGORA tokens, with their values as fallbacks) */
  var CSS = [
    '.gn-row{display:flex;align-items:center;justify-content:space-between;gap:10px;min-height:44px;margin:0 0 6px;padding:0}',
    '.gn-row.gn-own{padding:calc(env(safe-area-inset-top,0px) + 4px) calc(env(safe-area-inset-right,0px) + 12px) 0 calc(env(safe-area-inset-left,0px) + 12px)}',
    '.gn-back{display:inline-flex;align-items:center;gap:2px;min-height:44px;min-width:44px;padding:0 10px 0 2px;border-radius:12px;color:var(--ag-gold,#c8a24a);font:600 1.0625rem/1 var(--ag-sans,-apple-system,system-ui,sans-serif);text-decoration:none;-webkit-touch-callout:none}',
    '.gn-ic{width:20px;height:20px;fill:none;stroke:currentColor;stroke-width:2.2;stroke-linecap:round;stroke-linejoin:round;flex:none}',
    '.gn-go{display:inline-flex;align-items:center;justify-content:center;gap:6px;min-height:44px;min-width:44px;padding:0 14px;border-radius:999px;border:1px solid var(--ag-line,#3a3228);background:rgba(29,25,20,.82);color:var(--ag-text,#f3ece0);font:600 .9375rem/1 var(--ag-sans,-apple-system,system-ui,sans-serif);cursor:pointer;-webkit-tap-highlight-color:transparent;white-space:nowrap}',
    '.gn-go .gn-ic{width:17px;height:17px;stroke:var(--ag-gold,#c8a24a)}',
    '.gn-go.gn-icon{padding:0;width:44px;border-color:transparent;background:transparent}',
    '.tags .gn-go,.gn-slot .gn-go{margin-left:2px}',
    'main#app>header.top.ag-hasnav>.gn-slot{grid-column:2;grid-row:1;align-self:center;display:flex;gap:6px}',
    '.gn-scrim{position:fixed;inset:0;z-index:9500;background:rgba(10,8,6,.62)}',
    '.gn-scrim[hidden],.gn-sheet[hidden]{display:none}',
    '.gn-sheet{position:fixed;z-index:9501;left:0;right:0;bottom:0;max-width:560px;margin:0 auto;max-height:calc(100% - env(safe-area-inset-top,0px) - 24px);display:flex;flex-direction:column;box-sizing:border-box;',
    '  border:1px solid var(--ag-line-gold,rgba(200,162,74,.42));border-bottom:0;border-radius:22px 22px 0 0;background:var(--ag-s1,#1d1914);color:var(--ag-text,#f3ece0);box-shadow:0 -10px 30px rgba(0,0,0,.45);',
    '  padding:8px calc(env(safe-area-inset-right,0px) + 16px) 0 calc(env(safe-area-inset-left,0px) + 16px);font:400 1rem/1.4 var(--ag-sans,-apple-system,system-ui,sans-serif);text-align:left}',
    '.gn-sheet *{box-sizing:border-box}',
    '.gn-head{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:2px 0 10px}',
    '.gn-head h2{margin:0;font:600 1.375rem/1.15 var(--ag-serif,"Iowan Old Style",Palatino,Georgia,serif);color:var(--ag-text,#f3ece0)}',
    '.gn-close{min-height:44px;min-width:64px;padding:0 14px;border-radius:12px;border:1px solid var(--ag-line,#3a3228);background:var(--ag-s2,#26211b);color:var(--ag-text,#f3ece0);font:600 1rem/1 inherit;cursor:pointer}',
    '.gn-search{position:relative;margin:0 0 6px}',
    '.gn-search .gn-ic{position:absolute;left:13px;top:50%;margin-top:-10px;color:var(--ag-muted,#a89c88);pointer-events:none}',
    '.gn-search input{display:block;width:100%;min-height:48px;padding:0 12px 0 42px;border-radius:14px;border:1px solid var(--ag-line,#3a3228);background:var(--ag-s0,#14110e);color:var(--ag-text,#f3ece0);font:400 1.0625rem/1.2 inherit;-webkit-appearance:none;appearance:none}',
    '.gn-search input:focus{outline:none;border-color:var(--ag-gold,#c8a24a)}',
    '.gn-search input::placeholder{color:var(--ag-muted,#a89c88);opacity:1}',
    '.gn-body{overflow-y:auto;-webkit-overflow-scrolling:touch;overscroll-behavior:contain;padding:0 0 calc(env(safe-area-inset-bottom,0px) + 20px)}',
    '.gn-sec{margin:14px 0 6px;color:var(--ag-gold,#c8a24a);font:600 .9375rem/1.2 var(--ag-serif,"Iowan Old Style",Palatino,Georgia,serif)}',
    '.gn-list{display:flex;flex-direction:column;border:1px solid var(--ag-line,#3a3228);border-radius:16px;background:var(--ag-s0,#14110e);overflow:hidden}',
    '.gn-item{display:flex;align-items:center;gap:12px;min-height:56px;padding:8px 14px;color:var(--ag-text,#f3ece0);text-decoration:none;border-top:1px solid rgba(58,50,40,.7)}',
    '.gn-item:first-child{border-top:0}',
    '.gn-item b{display:block;font:600 1rem/1.25 inherit}',
    '.gn-item small{display:block;color:var(--ag-muted,#a89c88);font-size:.8125rem;line-height:1.3}',
    '.gn-item.gn-gate{background:linear-gradient(180deg,var(--ag-s2,#26211b),var(--ag-s1,#1d1914))}',
    '.gn-item.gn-gate b{font-family:var(--ag-serif,"Iowan Old Style",Palatino,Georgia,serif);font-size:1.125rem;color:var(--ag-gold,#c8a24a)}',
    '.gn-dists{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}',
    '.gn-dist{display:flex;align-items:center;min-height:48px;padding:0 14px;border-radius:14px;border:1px solid var(--ag-line,#3a3228);background:var(--ag-s2,#26211b);color:var(--ag-text,#f3ece0);text-decoration:none;font:600 1rem/1.2 var(--ag-serif,"Iowan Old Style",Palatino,Georgia,serif)}',
    '.gn-empty{margin:10px 2px;color:var(--ag-soft,#cfc4b2)}',
    'html.gn-locked,html.gn-locked body{overflow:hidden}',
    '@media (prefers-reduced-motion:no-preference){.gn-sheet.gn-in{animation:gn-up .34s cubic-bezier(.2,.7,.2,1)}.gn-scrim.gn-in{animation:gn-fade .26s ease-out}.gn-go:active,.gn-back:active{opacity:.6}}',
    '@keyframes gn-up{from{transform:translateY(100%)}to{transform:none}}@keyframes gn-fade{from{opacity:0}to{opacity:1}}',
    '@media (max-width:359px){.gn-go:not(.gn-icon) span{display:none}.gn-go:not(.gn-icon){padding:0;width:44px}}'
  ].join('\n');

  /* ------------------------------------------------------------------------------------------ the top row */
  function goButton(iconOnly) {
    var b = el('button', 'gn-go' + (iconOnly ? ' gn-icon' : '')); b.type = 'button';
    b.setAttribute('aria-haspopup', 'dialog'); b.setAttribute('aria-label', 'Go to another app'); b.setAttribute('data-gn', 'go');
    b.appendChild(searchIcon()); if (!iconOnly) b.appendChild(el('span', '', 'Go to'));
    b.addEventListener('click', function () { openSheet(b); });
    return b;
  }
  function toGate(a, arrowText) {   // an existing back link becomes the way to the Gate
    a.href = GATE; a.setAttribute('aria-label', 'Back to the Gate'); a.title = 'The Gate: every app'; a.setAttribute('data-gn', 'gate');
    var label = a.querySelector('span');
    if (label && a.querySelector('svg')) label.textContent = 'Gate'; else a.textContent = (arrowText || '◂') + ' Gate';
  }
  function gateLink() { var a = el('a', 'gn-back'); a.href = GATE; a.setAttribute('aria-label', 'Back to the Gate'); a.setAttribute('data-gn', 'gate'); a.appendChild(backIcon()); a.appendChild(el('span', '', 'Gate')); return a; }
  function topOf(n) { var r = n.getBoundingClientRect(); return r.top + (w.pageYOffset || 0); }
  function place() {
    if (S.placed || !d.body) return;
    var st = el('style'); st.setAttribute('data-gn', 'css'); st.textContent = CSS; d.head.appendChild(st);
    var head = d.querySelector('main#app > header.top') || d.querySelector('header.top') || d.querySelector('header');
    // 1. the AGORA shell's back row: "< Olympus" -> "< Gate", Go to on the right of the same row
    var nb = head && head.querySelector(':scope > .ag-navback');
    if (nb) {
      toGate(nb);
      var tags = head.querySelector(':scope > .tags');
      if (tags) tags.appendChild(goButton(false)); else { var slot = el('div', 'gn-slot'); slot.appendChild(goButton(false)); head.appendChild(slot); }
    } else {
      // 2. an own "Olympus" back link near the top of the page (e.g. Kalshi's): it becomes the Gate link, inside a row with Go to
      var own = null, cands = d.querySelectorAll('a.olyback, a[href="../jarvis/"], a[href="../jarvis/index.html"]');
      for (var i = 0; i < cands.length && !own; i++) if (/olympus/i.test(cands[i].textContent || '') && topOf(cands[i]) < 200) own = cands[i];
      if (own) {
        var row = el('div', 'gn-row'); own.parentNode.insertBefore(row, own); row.appendChild(own); toGate(own, '←'); row.appendChild(goButton(false));
      } else {
        // 3. no back link: a slim row of our own, in the page flow. A header that floats over a scene as a panel (Cities) takes it as its first line;
        //    a header that floats as a row over a full-bleed picture (Polis over its sky) gets the row above that picture, so nothing is covered.
        var row2 = el('div', 'gn-row'); row2.appendChild(gateLink()); row2.appendChild(goButton(false));
        var cs = head ? w.getComputedStyle(head) : null, floats = cs && /fixed|absolute|sticky/.test(cs.position || '');
        var rowFlex = cs && /flex/.test(cs.display || '') && !/column/.test(cs.flexDirection || '');
        var host = floats && rowFlex && head.offsetParent && head.offsetParent !== d.body && head.offsetParent.parentNode ? head.offsetParent : null;
        if (host) { row2.className += ' gn-own'; host.parentNode.insertBefore(row2, host); }
        else if (floats) head.insertBefore(row2, head.firstChild);
        else if (head && head.parentNode) head.parentNode.insertBefore(row2, head);
        else { row2.className += ' gn-own'; d.body.insertBefore(row2, d.body.firstChild); }
      }
    }
    // the compact bar of the AGORA shell (shown once the title scrolls away): the same two ways
    var bar = d.querySelector('.ag-appbar');
    if (bar) {
      var bb = bar.querySelector('.ag-navback'); if (bb) toGate(bb);
      var end = bar.querySelector('.ag-appbar-end'); if (end) { var g = goButton(true); g.tabIndex = -1; end.appendChild(g); }
    }
    S.placed = true;
    loadCatalog();
  }

  /* ------------------------------------------------------------------------------------------ the catalog (the Gate's list; the generated apps list if it is missing) */
  function loadCatalog(then) {
    if (w.OLYMPUS_GATE) { S.cat = w.OLYMPUS_GATE; if (then) then(); return; }
    if (S.catTried) { if (then) then(); return; }
    S.catTried = true;
    var s = el('script'); s.src = root + 'olympus/gate-catalog.js?v=g1'; s.async = true;
    s.onload = function () { S.cat = w.OLYMPUS_GATE || null; if (then) then(); else refresh(); };
    s.onerror = function () {
      var s2 = el('script'); s2.src = root + 'olympus/apps-list.js'; s2.async = true;
      s2.onload = function () { S.cat = fromList(w.OLYMPUS_APPS_LIST); if (then) then(); else refresh(); };
      s2.onerror = function () { if (then) then(); };
      d.head.appendChild(s2);
    };
    d.head.appendChild(s);
  }
  function fromList(L) {
    if (!(L instanceof Array)) return null;
    var apps = L.map(function (r, i) { return { id: r.id === 'zenith' ? 'today' : r.id, path: r.path || '', name: r.name, label: r.name, line: r.purpose || '', district: r.group, section: 'top', words: '', rank: i }; });
    return { apps: apps, byId: function (id) { for (var i = 0; i < apps.length; i++) if (apps[i].id === id) return apps[i]; return null; },
      find: function (q) { var t = String(q || '').toLowerCase(); return apps.filter(function (a) { return (a.name + ' ' + a.line + ' ' + a.id).toLowerCase().indexOf(t) >= 0; }).slice(0, 8); } };
  }

  /* ------------------------------------------------------------------------------------------ the sheet */
  function item(a, cls) {
    var r = el('a', 'gn-item' + (cls ? ' ' + cls : '')); r.href = hrefOf(a); r.setAttribute('data-app', a.id);
    var t = el('span'); t.appendChild(el('b', '', a.label || a.name));
    var sub = (a.name && a.label && a.name !== a.label ? a.name + ' · ' : '') + (a.line || '');
    if (sub) t.appendChild(el('small', '', sub));
    r.appendChild(t);
    r.addEventListener('click', function () { remember(a.id); });
    return r;
  }
  function build() {
    var scrim = el('div', 'gn-scrim'), sh = el('section', 'gn-sheet');
    scrim.hidden = true; sh.hidden = true;
    sh.setAttribute('role', 'dialog'); sh.setAttribute('aria-modal', 'true'); sh.setAttribute('aria-labelledby', 'gnH');
    var head = el('div', 'gn-head'), h = el('h2', '', 'Go to'); h.id = 'gnH';
    var close = el('button', 'gn-close', 'Close'); close.type = 'button'; close.setAttribute('aria-label', 'Close');
    head.appendChild(h); head.appendChild(close);
    var box = el('div', 'gn-search'), inp = el('input'); inp.type = 'search'; inp.id = 'gnQ';
    inp.setAttribute('placeholder', 'money, risk, kalshi, journal...'); inp.setAttribute('aria-label', 'Find an app'); inp.setAttribute('autocomplete', 'off'); inp.setAttribute('autocapitalize', 'off'); inp.setAttribute('spellcheck', 'false'); inp.setAttribute('enterkeyhint', 'go');
    box.appendChild(searchIcon()); box.appendChild(inp);
    var body = el('div', 'gn-body'); body.setAttribute('aria-live', 'polite');
    sh.appendChild(head); sh.appendChild(box); sh.appendChild(body);
    d.body.appendChild(scrim); d.body.appendChild(sh);
    close.addEventListener('click', closeSheet); scrim.addEventListener('click', closeSheet);
    inp.addEventListener('input', refresh);
    inp.addEventListener('keydown', function (e) { if (e.key !== 'Enter') return; var f = body.querySelector('a.gn-item[data-app]'); if (f && inp.value) { e.preventDefault(); remember(f.getAttribute('data-app')); w.location.href = f.href; } });
    d.addEventListener('keydown', function (e) {
      if (!S.sheet) return;
      if (e.key === 'Escape' || e.key === 'Esc') { e.preventDefault(); closeSheet(); return; }
      if (e.key !== 'Tab') return;
      var f = sh.querySelectorAll('a[href], button, input'); if (!f.length) return;
      if (e.shiftKey && d.activeElement === f[0]) { e.preventDefault(); f[f.length - 1].focus(); } else if (!e.shiftKey && d.activeElement === f[f.length - 1]) { e.preventDefault(); f[0].focus(); }
    });
    var y0 = null;
    head.addEventListener('touchstart', function (e) { y0 = e.touches[0].clientY; }, { passive: true });
    head.addEventListener('touchmove', function (e) { if (y0 != null && e.touches[0].clientY - y0 > 70) { y0 = null; closeSheet(); } }, { passive: true });
    S.sheet = null; S.el = { scrim: scrim, sh: sh, inp: inp, body: body, close: close };
  }
  function refresh() {
    if (!S.el) return;
    var body = S.el.body, q = (S.el.inp.value || '').replace(/^\s+|\s+$/g, ''), C = S.cat; clear(body);
    if (q) {
      var hits = C ? C.find(q, 8) : [];
      if (hits.length) { var l = el('div', 'gn-list'); hits.forEach(function (a) { l.appendChild(item(a)); }); body.appendChild(l); }
      else body.appendChild(el('p', 'gn-empty', C ? 'Nothing found for "' + q + '". Try a plain word like money, risk or news.' : 'The app list did not load. The Gate below has every app.'));
    }
    var g = el('div', 'gn-list'); g.style.marginTop = q ? '12px' : '4px';
    g.appendChild(item({ id: 'gate', path: 'gate/', label: 'The Gate', name: '', line: 'Every app, in two taps' }, 'gn-gate'));
    body.appendChild(g);
    if (q) return;
    if (C) {
      var rec = recent().filter(function (id) { return id !== appId; }).map(C.byId).filter(function (a) { return a && a.district !== 'workshop'; }).slice(0, 4);
      if (rec.length) { body.appendChild(el('h3', 'gn-sec', 'Recent')); var rl = el('div', 'gn-list'); rec.forEach(function (a) { rl.appendChild(item(a)); }); body.appendChild(rl); }
      var st = ['today', 'nq', 'jarvis'].map(C.byId).filter(Boolean);
      if (st.length) { body.appendChild(el('h3', 'gn-sec', 'Start here')); var sl = el('div', 'gn-list'); st.forEach(function (a) { sl.appendChild(item(a)); }); body.appendChild(sl); }
    }
    body.appendChild(el('h3', 'gn-sec', 'Districts'));
    var ds = el('div', 'gn-dists');
    [['trading', 'Trading'], ['money', 'Money'], ['life', 'Life'], ['worlds', 'Worlds']].forEach(function (x) { var a = el('a', 'gn-dist', x[1]); a.href = GATE + '?d=' + x[0]; ds.appendChild(a); });
    body.appendChild(ds);
  }
  function openSheet(opener) {
    if (!S.el) build();
    S.sheet = true; S.opener = opener || null;
    S.el.inp.value = ''; refresh();
    if (!S.cat) loadCatalog(refresh);
    S.el.scrim.hidden = false; S.el.sh.hidden = false;
    S.el.scrim.className = 'gn-scrim gn-in'; S.el.sh.className = 'gn-sheet gn-in';
    d.documentElement.className += ' gn-locked';
    try { S.el.close.focus({ preventScroll: true }); } catch (e) { S.el.close.focus(); }
  }
  function closeSheet() {
    if (!S.sheet || !S.el) return;
    S.sheet = null; S.el.scrim.hidden = true; S.el.sh.hidden = true;
    d.documentElement.className = d.documentElement.className.replace(/\s*gn-locked/g, '');
    if (S.opener && S.opener.focus) { try { S.opener.focus({ preventScroll: true }); } catch (e) { S.opener.focus(); } }
  }
  w.addEventListener('pageshow', function (e) { if (e.persisted) closeSheet(); });

  var go = function () { try { place(); } catch (e) { /* the app works without it */ } };
  if (d.readyState === 'loading') d.addEventListener('DOMContentLoaded', go); else go();
})();
