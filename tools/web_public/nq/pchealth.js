// PC HEALTH page (night-nq-home 2026-11-27): renders window.PCHEALTH.checks(lite). textContent only; GET only.
(function () {
  'use strict';
  var ICON = { green: '✓', amber: '!', red: '×', grey: '?' };
  var WORD = { red: 'need you now', amber: 'to watch', green: 'fine', grey: 'not sent' };
  var lite = null;
  function el(tag, cls, txt) { var e = document.createElement(tag); if (cls) e.className = cls; if (txt != null) e.textContent = txt; return e; }
  function card(c, i) {
    var li = el('li', 'ck ' + c.state); li.setAttribute('data-id', c.id); li.style.setProperty('--i', i);
    var d = el('span', 'dot'); d.setAttribute('aria-label', c.state);
    li.appendChild(d); li.appendChild(el('div', 'tt', c.title)); li.appendChild(el('div', 'sy', c.say));
    if (c.fix) li.appendChild(el('div', 'fx', c.fix));
    return li;
  }
  function render() {
    var H = window.PCHEALTH, r = H.checks(lite);
    var hero = document.getElementById('hero'); hero.setAttribute('data-s', r.overall);
    document.getElementById('orb').textContent = ICON[r.overall] || '?';
    document.getElementById('say').textContent = lite ? r.say : 'No report from the PC yet.';
    document.getElementById('meta').textContent = r.age == null ? 'No PC report' : 'PC reported ' + H.ageText(r.age) + ' ago';
    var chips = document.getElementById('chips'); chips.textContent = '';
    ['red', 'amber', 'green', 'grey'].forEach(function (k) { if (r.counts[k]) chips.appendChild(el('span', 'chip ' + k, r.counts[k] + ' ' + WORD[k])); });
    var need = document.getElementById('need'), ok = document.getElementById('ok'); need.textContent = ''; ok.textContent = '';
    var n = 0, m = 0;
    r.checks.forEach(function (c, i) {
      if (c.state === 'red' || c.state === 'amber') { need.appendChild(card(c, i)); n++; } else { ok.appendChild(card(c, i)); m++; }
    });
    document.getElementById('needh').hidden = !n; document.getElementById('okh').hidden = !m;
  }
  function load() {
    if (!window.PC_FEED) { render(); return; }
    window.PC_FEED.fetchLatest({ feedUrl: new URL('../status_feed.json', location.href).href })
      .then(function (j) { lite = j || null; render(); }, function () { render(); });
  }
  render(); load(); setInterval(load, 60000);
})();
