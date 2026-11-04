// Zenith pages, PC glue (2026-11-04, JOB 28): the PC copy of tools/web_public/zenith_pages.js on the shared zenpagescore.js.
// A page with nothing to show yet gets the "what you will see here" card with a clearly marked sample; a page that is still loading
// gets ghost cards; key figures roll up the first time a page opens. Read-only: nothing is sent; the chips only open a page.
(function () {
  'use strict';
  const ZP = window.ZenithPages;
  if (!ZP) return;
  const SKIP = new Set(['cc', 'liveview', 'holo', 'mission', 'chart', 'livechart', 'settings', 'start', 'zlarior', 'atlas', 'blitz']);
  const txt = (e) => (e && e.textContent ? e.textContent.replace(/\s+/g, ' ').trim() : '');
  let t = 0, tp = 0;
  const cur = () => {
    const el = document.querySelector('.nx .page.active'); if (!el) return null;
    const route = (el.id || '').replace(/^page-/, '');
    if (!route || SKIP.has(route)) return null;
    const d = el.querySelector('.hero p, .note, :scope > p');
    return { el, i: { route, title: txt(document.getElementById('pageTitle')) || route, desc: d ? txt(d).slice(0, 220) : '', go: (r) => { if (window.LE && window.LE.go) window.LE.go(r === 'lit' ? 'zlarior' : r === 'today' ? 'cc' : r); } } };
  };
  // loading / key figures soon after a redraw; the sample card only once the page has stayed quiet and thin for ~1.5 s (no flash while data arrives)
  function run() {
    t = 0; const c = cur(); if (!c) return;
    try { ZP.prune(c.el); if (ZP.skeleton(c.el)) return; ZP.rolls(c.el, c.i.route); } catch (e) { console.warn('zenith pages', e); }
  }
  function sample() {
    tp = 0; const c = cur(); if (!c) return;
    try { ZP.peek(c.el, c.i); } catch (e) { console.warn('zenith pages', e); }
  }
  const soon = (ms) => { clearTimeout(t); t = setTimeout(run, ms == null ? 500 : ms); clearTimeout(tp); tp = setTimeout(sample, 1500 + (ms || 0)); };
  const root = document.querySelector('.nx .main') || document.body;
  if (typeof MutationObserver !== 'undefined') new MutationObserver((ms) => {
    for (const m of ms) {
      const tg = m.target;
      if (tg.closest && tg.closest('.zp-peek, .zp-skel')) continue;
      if (m.type === 'childList' && [...m.addedNodes, ...m.removedNodes].length && [...m.addedNodes, ...m.removedNodes].every((n) => n.nodeType === 1 && (n.classList.contains('zp-peek') || n.classList.contains('zp-skel')))) continue;
      if (tg.closest && !tg.closest('.page')) continue;
      soon(); return;
    }
  }).observe(root, { childList: true, subtree: true, attributes: true, attributeFilter: ['class'] });
  addEventListener('resize', () => soon(700));
  soon(800);
})();
