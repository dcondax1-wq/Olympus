// System > Strategy > Second strategies (phone; loaded by index.html with one <script defer> after secondcore.js;
// read-only): the PAPER second strategies next to LIT (EMA London pullback, MACD sweep divergence, S/R NY reclaim):
// rules in plain words, today's state, paper trades and $, the backtest H1 / H2 / 2025 / 2021-24 and "with LIT".
// From data.json "second" (engine/second.dashboard_block, built by tools/build_web_dashboard.py), with the PC's live cut
// (live.json / heartbeat "second", engine/second.compact) laid over the state when present. Renderer: secondcore.js.
// Classic script that uses the main page's helpers (D, VIEWS, GROUPS, PAGES, head, emptyBox) when they exist.
(function () {
  'use strict';
  if (typeof GROUPS === 'undefined' || typeof VIEWS === 'undefined') return;
  function view(el) {
    const S = (typeof D !== 'undefined' && D && D.second) || null;
    const live = (typeof D !== 'undefined' && D && D.live && D.live.pc && D.live.pc.second) || null;
    el.innerHTML = (typeof head === 'function' ? head('Strategy · paper', 'Second strategies',
      'EMA, MACD and S/R next to LIT on paper: rules, today, paper trades, backtest') : '<h2>Second strategies</h2>') + '<div id="scRoot"></div>';
    const root = el.querySelector('#scRoot');
    if (!window.SecondUI) { root.innerHTML = '<div class="card">secondcore.js did not load.</div>'; return; }
    window.SecondUI.render(root, S, { live });
  }
  function install() {
    const G = GROUPS.find((g) => g.id === 'system') || GROUPS[GROUPS.length - 1];
    if (!G) return;
    const i = G.pages.findIndex((p) => p[0] === 'strategy');
    if (!G.pages.some((p) => p[0] === 'second')) G.pages.splice(i >= 0 ? i + 1 : 1, 0, ['second', 'Second strategies', 'rules', 'EMA / MACD / S/R next to LIT, paper only']);
    PAGES.second = { id: 'second', label: 'Second strategies', icon: 'rules', desc: 'EMA / MACD / S/R next to LIT, paper only', group: G.id };
    VIEWS.second = view;
    if (typeof SCENE !== 'undefined') SCENE.second = 'eval';
    if (typeof ALIAS !== 'undefined') Object.assign(ALIAS, { ema: 'second', macd: 'second', sr: 'second', paper2: 'second', second_strategies: 'second' });
    if (typeof nav === 'function') { nav(); if (typeof route === 'function' && /^#\/(second|ema|macd|sr)\b/.test(location.hash)) route(); }
  }
  install();
})();
