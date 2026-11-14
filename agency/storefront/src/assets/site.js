/* Agency storefront: small progressive enhancements. Every page works without this file (links and forms are plain HTML).
   No tracking, no network calls: it only reads the page and the address bar. Plain ES5-style code for older iPhones. */
(function () {
  'use strict';
  var d = document;
  var root = d.documentElement;
  root.classList.add('js');

  function $(sel, el) { return (el || d).querySelector(sel); }
  function $$(sel, el) { return Array.prototype.slice.call((el || d).querySelectorAll(sel)); }
  function param(name) {
    var m = new RegExp('[?&]' + name + '=([^&#]*)').exec(location.search);
    return m ? decodeURIComponent(m[1].replace(/\+/g, ' ')) : '';
  }

  // 1. colour preview: add ?preset=ocean (or coral, forest) to any address
  var pre = param('preset');
  if (/^(coral|ocean|forest)$/.test(pre)) { root.setAttribute('data-preset', pre); root.classList.remove('brand-custom'); }

  // 2. the year at the bottom never looks old
  var year = String(new Date().getFullYear());
  $$('[data-year]').forEach(function (el) { if (+year > +el.textContent) { el.textContent = year; } });

  // 3. the phone menu
  var btn = $('.menu-btn');
  var nav = $('#site-nav');
  if (btn && nav) {
    btn.hidden = false;
    var setOpen = function (open) {
      nav.classList.toggle('open', open);
      btn.setAttribute('aria-expanded', open ? 'true' : 'false');
      btn.lastElementChild.textContent = open ? 'Close' : 'Menu';
    };
    btn.addEventListener('click', function () { setOpen(!nav.classList.contains('open')); });
    nav.addEventListener('click', function (e) { if (e.target.closest('a')) { setOpen(false); } });
    d.addEventListener('keydown', function (e) { if (e.key === 'Escape' && nav.classList.contains('open')) { setOpen(false); btn.focus(); } });
    d.addEventListener('click', function (e) { if (nav.classList.contains('open') && !e.target.closest('.top')) { setOpen(false); } });
  }

  // 4. contact page: ?plan=growth (from a pricing button) picks that plan
  var plan = param('plan');
  if (plan) {
    $$('input[name="plan"]').forEach(function (r) { if (r.value === plan) { r.checked = true; } });
  }

  // 5. forms: one tap = one send (and Back after sending gives a working button again)
  $$('form[data-netlify]').forEach(function (f) {
    var b = $('button[type="submit"]', f);
    var label = b ? b.firstChild.textContent : '';
    f.addEventListener('submit', function (e) {
      if (f.id === 'grader' && !graderReady(e)) { return; }
      if (b) { b.disabled = true; b.setAttribute('aria-busy', 'true'); b.firstChild.textContent = 'Sending... '; }
    });
    window.addEventListener('pageshow', function (e) {
      if (e.persisted && b) { b.disabled = false; b.removeAttribute('aria-busy'); b.firstChild.textContent = label; }
    });
  });

  // 6. the free website check
  var form = $('#grader');
  var site = $('#g-site');
  var noSite = $('#g-nosite');
  var RING = 326.73;

  function cleanUrl(v) {
    v = (v || '').trim().replace(/\s+/g, '');
    if (!v) { return ''; }
    if (!/^https?:\/\//i.test(v)) { v = 'https://' + v; }
    try {
      var u = new URL(v);
      if (!/\./.test(u.hostname)) { return ''; }
      return u.protocol + '//' + u.host + (u.pathname === '/' ? '' : u.pathname);
    } catch (err) { return ''; }
  }

  function grade(score) {
    if (score >= 90) { return ['A', 'Great shape', 'Your website is doing its job. A few small touches could still bring more calls.']; }
    if (score >= 75) { return ['B', 'Good, with easy wins', 'You are close. Fix the items below and you will catch the customers who slip away today.']; }
    if (score >= 60) { return ['C', 'Losing some calls', 'Customers are finding you but some leave before they call. The fixes below are quick.']; }
    if (score >= 45) { return ['D', 'Losing a lot of calls', 'Your website is turning customers away. The good news: every item below is fixable in days.']; }
    return ['F', 'Costing you customers', 'Most people who find this site will call someone else. A new site fixes all of this at once.']; }

  function update() {
    var qs = $$('.q', form);
    var got = 0;
    var max = 0;
    var answered = 0;
    var fixes = [];
    qs.forEach(function (q) {
      var w = +q.getAttribute('data-w');
      var pick = $('input:checked', q);
      q.classList.toggle('answered', !!pick);
      if (!pick) { return; }
      answered += 1;
      max += w;
      if (pick.value === 'yes') { got += w; } else {
        if (pick.value === 'unsure') { got += w / 2; }
        fixes.push({ w: pick.value === 'no' ? w : w / 2, q: $('.qt', q).textContent, fix: q.getAttribute('data-fix'), unsure: pick.value === 'unsure' });
      }
    });
    var bar = $('#g-bar');
    if (bar) { bar.style.width = Math.round(100 * answered / qs.length) + '%'; }
    var box = $('#result');
    if (!answered) { box.hidden = true; return; }
    box.hidden = false;
    var score = Math.round(100 * got / max);
    var g = grade(score);
    var done = answered === qs.length;
    $('#g-score').textContent = String(score);
    $('#g-grade').textContent = g[0];
    $('#g-head').textContent = done ? g[1] : 'So far: ' + g[1].toLowerCase();
    $('#g-sub').textContent = done ? g[2] : 'Based on ' + answered + ' of ' + qs.length + ' answers. Keep going for your full score.';
    box.className = 'card result g-' + g[0].toLowerCase();
    $('#g-ring').style.strokeDashoffset = String(RING * (1 - score / 100));
    $('#g-score-in').value = done ? String(score) : score + ' (' + answered + '/' + qs.length + ' answered)';
    $('#g-grade-in').value = g[0];
    fixes.sort(function (a, b) { return b.w - a.w; });
    var list = $('#g-fixes');
    list.textContent = '';
    fixes.slice(0, 3).forEach(function (f) {
      var li = d.createElement('li');
      var s = d.createElement('strong');
      s.textContent = f.fix;
      li.appendChild(s);
      li.appendChild(d.createTextNode(f.unsure ? 'You were not sure: we will check this one in your report.' : 'You answered no to: ' + f.q));
      list.appendChild(li);
    });
    $('#g-fixes-box').hidden = !fixes.length;
  }

  function showSite() {
    var u = cleanUrl(site.value);
    var line = $('#g-for');
    if (!u) { line.hidden = true; return u; }
    line.hidden = false;
    $('#g-host').textContent = u.replace(/^https?:\/\//, '');
    $('#g-open').href = u;
    return u;
  }

  function graderReady(e) {
    var err = $('#g-err');
    var u = showSite();
    if (!u && !noSite.checked) {
      e.preventDefault();
      err.hidden = false;
      err.textContent = 'Please type your website address at the top (or tick "I don\'t have a website yet").';
      site.focus();
      return false;
    }
    if (u) { site.value = u; }
    err.hidden = true;
    return true;
  }

  if (form && site) {
    var start = $('#g-start');
    start.addEventListener('click', function (e) {
      if (noSite.checked) { return; }
      if (!showSite()) {
        e.preventDefault();
        site.focus();
        site.setAttribute('aria-invalid', 'true');
        $('#g-site-help').textContent = 'Type your website address first, for example joesplumbing.com.';
      } else {
        site.removeAttribute('aria-invalid');
      }
    });
    site.addEventListener('change', showSite);
    site.addEventListener('keydown', function (e) { if (e.key === 'Enter') { e.preventDefault(); start.click(); } });
    noSite.addEventListener('change', function () {
      $('#g-nosite-box').hidden = !noSite.checked;
      $('#quiz').hidden = noSite.checked;
      $('#result').hidden = noSite.checked || !$('.q input:checked', form);
      start.hidden = noSite.checked;
    });
    form.addEventListener('change', function (e) { if (e.target.type === 'radio') { update(); } });
    var fromUrl = param('site');
    if (fromUrl) { site.value = fromUrl; showSite(); }
    update();
  }
})();
