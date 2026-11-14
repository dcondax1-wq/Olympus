/* THE GATE (OLYMPUS front door, 2026-11-12). Classic script, ES5, no build step, no network but the site's own files.
 * - "Right now": ../home.json through olympus/truth.js (the one source every app uses for drawdown and data age); a light copy of its rules when truth.js
 *   does not load. Bots on / quiet / old numbers with the exact age, drawdown left, today's $, the next trade window. Older than 6 h: one button "Bring the bots back".
 * - Start here (1 tap), the four district doors (a sheet, most useful first: 2 taps), the search (name, purpose, plain words), Recent (last 4 opened, this phone only).
 * - GATE_BASE ('' at the site root as olympus-live.html, '../' at gate/) prefixes every link. Apps missing from a partial copy are marked "not in this link".
 * - Served from the PC (/site/, the private Tailscale link, docs/LIVE_DASHBOARD.md): "Right now" reads the bot's own /api/site/live.json
 *   over home.json (pc_feed.js overlayHome) and refreshes every minute. Any other copy never asks it.
 * Text only through textContent / createElementNS. Storage: 'gate.recent.v1' (ids) and 'gate.now.v1' (the last numbers seen), both in try / catch. */
(function () {
  'use strict';
  var d = document, w = window, C = w.OLYMPUS_GATE || null, base = w.GATE_BASE || '';
  var LS_RECENT = 'gate.recent.v1', LS_NOW = 'gate.now.v1', STALE_S = 6 * 3600, FRESH_S = 20 * 60;
  var NS = 'http://www.w3.org/2000/svg';
  var S = { list: !!C, now: null, nowDone: false, sheet: null, opener: null, probe: {}, probes: 0 };
  var Q = (function () { var o = {}, s = (w.location.search || '').replace(/^\?/, ''); if (!s) return o; s.split('&').forEach(function (kv) { var p = kv.split('='); if (p[0]) { try { o[decodeURIComponent(p[0])] = decodeURIComponent((p[1] || '').replace(/\+/g, ' ')); } catch (e) { /* skip */ } } }); return o; })();

  function $(id) { return d.getElementById(id); }
  function el(tag, cls, text) { var e = d.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }
  function sv(tag, attrs) { var e = d.createElementNS(NS, tag); for (var k in attrs) if (Object.prototype.hasOwnProperty.call(attrs, k)) e.setAttribute(k, attrs[k]); return e; }
  function clear(n) { while (n && n.firstChild) n.removeChild(n.firstChild); }
  function lsGet(k) { try { var v = w.localStorage.getItem(k); return v ? JSON.parse(v) : null; } catch (e) { return null; } }
  function lsSet(k, v) { try { w.localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* private mode: fine */ } }
  function num(v) { var x = typeof v === 'string' ? parseFloat(v.replace(/[$,\s]/g, '')) : v; return typeof x === 'number' && isFinite(x) ? x : null; }
  function obj(x) { return x && typeof x === 'object' && !(x instanceof Array) ? x : {}; }
  function nowS() { var t = Q.now ? Date.parse(Q.now) : NaN; return (isFinite(t) ? t : Date.now()) / 1000; }
  function money(x) { var v = num(x); if (v == null) return '$0'; var a = Math.abs(Math.round(v)); return (v < 0 && a !== 0 ? '−' : '') + '$' + a.toLocaleString('en-US'); }
  function moneyS(x) { var v = num(x); return v != null && Math.round(v) > 0 ? '+' + money(v) : money(v); }
  function plural(n, word) { return n + ' ' + word + (n === 1 ? '' : 's'); }
  function ageWords(sec) {
    var s = Math.max(0, Math.floor(num(sec) || 0));
    if (s < 60) return 'less than a minute';
    if (s < 3600) return plural(Math.floor(s / 60), 'minute');
    if (s < 86400) { var h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60); return plural(h, 'hour') + (m ? ' ' + plural(m, 'minute') : ''); }
    var dd = Math.floor(s / 86400), hh = Math.floor((s % 86400) / 3600); return plural(dd, 'day') + (hh ? ' ' + plural(hh, 'hour') : '');
  }
  function inWords(sec) { var s = Math.max(0, Math.round(sec / 60)); if (s < 60) return 'in ' + plural(s, 'minute'); var h = Math.floor(s / 60), m = s % 60; return h >= 24 ? 'in ' + plural(Math.floor(h / 24), 'day') + (h % 24 ? ' ' + (h % 24) + ' h' : '') : 'in ' + h + ' h' + (m ? ' ' + m + ' min' : ''); }

  /* ------------------------------------------------------------------------------------------ links */
  function hrefOf(a) { var p = a.path; if (p === '') return base + 'index.html'; if (/\/$/.test(p)) return base + p + 'index.html'; return base + p; }
  function iconOf(a) { return /\/$/.test(a.path) ? base + a.path + 'icon.svg' : null; }
  function recentIds() { var r = lsGet(LS_RECENT); return r instanceof Array ? r.filter(function (x) { return typeof x === 'string'; }) : []; }
  function remember(id) { var r = recentIds().filter(function (x) { return x !== id; }); r.unshift(id); lsSet(LS_RECENT, r.slice(0, 8)); }

  function chevron() { var s = sv('svg', { 'class': 'g-chev', viewBox: '0 0 16 16', 'aria-hidden': 'true' }); s.appendChild(sv('path', { d: 'M6 3l5 5-5 5' })); return s; }
  function icon(a) {
    var box = el('span', 'g-ico'), src = iconOf(a), glyph = (a.name || a.label || '?').charAt(0);
    box.setAttribute('aria-hidden', 'true');
    if (!src) { box.textContent = glyph; return box; }
    var img = el('img'); img.alt = ''; img.width = 40; img.height = 40; img.loading = 'lazy'; img.decoding = 'async';
    img.onerror = function () { if (img.parentNode) img.parentNode.removeChild(img); box.textContent = glyph; };
    img.src = src; box.appendChild(img); return box;
  }
  function row(a) {
    var r = el('a', 'g-row'); r.href = hrefOf(a); r.setAttribute('data-app', a.id);
    var t = el('span', 'g-txt'), sm = el('small');
    t.appendChild(el('b', '', a.label));
    if (a.name && a.name !== a.label) { sm.appendChild(el('i', '', a.name)); sm.appendChild(d.createTextNode(' · ' + a.line)); } else { sm.appendChild(el('i', '', '')); sm.appendChild(d.createTextNode(a.line)); }
    t.appendChild(sm);
    r.appendChild(icon(a)); r.appendChild(t); r.appendChild(chevron());
    r.addEventListener('click', function () { remember(a.id); });
    probe(a);
    if (S.probe[a.id] === 'gone') r.className += ' g-gone';
    return r;
  }
  /* a partial copy of the site (the artifact link) has only some apps: ask once per app, mark the missing ones; any doubt = present */
  function probe(a) {
    if (S.probe[a.id] || !w.fetch || a.path === '') return;
    S.probe[a.id] = 'asking'; S.probes++;
    w.fetch(hrefOf(a), { method: 'HEAD', cache: 'no-store' }).then(function (res) {
      S.probe[a.id] = res.status === 404 ? 'gone' : 'ok';
      if (S.probe[a.id] !== 'gone') return;
      var rs = d.querySelectorAll('[data-app="' + a.id + '"].g-row');
      for (var i = 0; i < rs.length; i++) if (!/g-gone/.test(rs[i].className)) rs[i].className += ' g-gone';
    }).catch(function () { S.probe[a.id] = 'unknown'; });
  }

  /* ------------------------------------------------------------------------------------------ Recent */
  function drawRecent() {
    var box = $('recent'), sec = $('recentSec'); if (!box || !sec || !C) return;
    clear(box);
    var list = recentIds().map(C.byId).filter(function (a) { return a && a.district !== 'workshop'; }).slice(0, 4);
    sec.hidden = !list.length;
    list.forEach(function (a) {
      var c = el('a', 'g-chip'); c.href = hrefOf(a); c.setAttribute('data-app', a.id);
      var ic = icon(a); ic.style.width = ic.style.height = '32px'; ic.style.flexBasis = '32px'; ic.style.borderRadius = '50%'; ic.style.fontSize = '.9375rem';
      c.appendChild(ic); c.appendChild(el('span', '', a.label));
      c.addEventListener('click', function () { remember(a.id); });
      box.appendChild(c);
    });
  }

  /* ------------------------------------------------------------------------------------------ the sheet */
  function districtOf(id) { if (!C) return null; for (var i = 0; i < C.districts.length; i++) if (C.districts[i].id === id) return C.districts[i]; return null; }
  function appsIn(did, sec) { return C.apps.filter(function (a) { return a.district === did && (!sec || a.section === sec); }); }
  function openSheet(did, opener) {
    var D = districtOf(did); if (!D) return false;
    var body = $('sheetBody'), sheet = $('sheet'), scrim = $('scrim');
    $('sheetH').textContent = D.name;
    $('sheetSub').textContent = D.line + ' · ' + appsIn(did).length + ' apps';
    clear(body);
    D.sections.forEach(function (sec) {
      var list = appsIn(did, sec[0]); if (!list.length) return;
      body.appendChild(el('h3', 'g-sec', sec[1]));
      var box = el('div', 'g-list' + (sec[0] === 'top' ? ' g-top' : ''));
      list.forEach(function (a) { box.appendChild(row(a)); });
      body.appendChild(box);
    });
    S.sheet = did; S.opener = opener || null;
    scrim.hidden = false; sheet.hidden = false; body.scrollTop = 0;
    scrim.className = 'g-scrim g-in'; sheet.className = 'g-sheet g-in';
    d.documentElement.className += ' g-locked';
    try { $('sheetClose').focus({ preventScroll: true }); } catch (e) { $('sheetClose').focus(); }
    return true;
  }
  function closeSheet() {
    if (!S.sheet) return;
    $('sheet').hidden = true; $('scrim').hidden = true; S.sheet = null;
    d.documentElement.className = d.documentElement.className.replace(/\s*g-locked/g, '');
    if (S.opener && S.opener.focus) { try { S.opener.focus({ preventScroll: true }); } catch (e) { S.opener.focus(); } }
  }
  function trap(e) {
    if (!S.sheet) return;
    if (e.key === 'Escape' || e.key === 'Esc') { e.preventDefault(); closeSheet(); return; }
    if (e.key !== 'Tab') return;
    var f = $('sheet').querySelectorAll('a[href], button'); if (!f.length) return;
    var first = f[0], last = f[f.length - 1];
    if (e.shiftKey && d.activeElement === first) { e.preventDefault(); last.focus(); } else if (!e.shiftKey && d.activeElement === last) { e.preventDefault(); first.focus(); }
  }
  function swipe() {   // pull the sheet down by its head to close it
    var head = $('sheet'), y0 = null;
    head.addEventListener('touchstart', function (e) { var t = e.target; y0 = (t.closest && t.closest('.g-sheetbody')) ? null : e.touches[0].clientY; }, { passive: true });
    head.addEventListener('touchmove', function (e) { if (y0 != null && e.touches[0].clientY - y0 > 70) { y0 = null; closeSheet(); } }, { passive: true });
  }

  /* ------------------------------------------------------------------------------------------ search */
  function drawResults() {
    var box = $('results'), q = ($('q').value || '').replace(/^\s+|\s+$/g, ''); clear(box);
    if (!q || !C) return;
    var hits = C.find(q, 8);
    if (!hits.length) { box.appendChild(el('p', 'g-empty', 'Nothing found for "' + q + '". Try a plain word like money, risk or news.')); return; }
    hits.forEach(function (a) { box.appendChild(row(a)); });
  }

  /* ------------------------------------------------------------------------------------------ Right now */
  function getJSON(url) {
    if (!w.fetch) return { then: function (ok) { ok(null); return { 'catch': function () {} }; } };
    return w.fetch(url + (url.indexOf('?') < 0 ? '?' : '&') + 't=' + Date.now(), { cache: 'no-store' })
      .then(function (r) { return r.ok ? r.json()['catch'](function () { return null; }) : null; })['catch'](function () { return null; });
  }
  function getTruth(cb) {   // olympus/truth.js is an ES module: a one-line module tag hands it over; 2.5 s, then the light copy below
    if (w.OLYMPUS_TRUTH) { cb(w.OLYMPUS_TRUTH); return; }
    var done = false, fin = function () { if (done) return; done = true; cb(w.OLYMPUS_TRUTH || null); };
    w.addEventListener('gate-truth', fin);
    try {
      var url = new w.URL(base + 'olympus/truth.js?v=q6a', w.location.href).href, s = d.createElement('script');
      s.type = 'module';
      s.textContent = 'import * as T from ' + JSON.stringify(url) + '; window.OLYMPUS_TRUTH = T; window.dispatchEvent(new Event("gate-truth"));';
      d.head.appendChild(s);
    } catch (e) { fin(); return; }
    w.setTimeout(fin, 2500);
  }
  /* the light copy of truth.js's rules, used only when truth.js does not load */
  function lightAges(home, t) {
    var pcT = num(obj(obj(home.live).pc).t); if (pcT == null) pcT = num(obj(home.board).data_t);
    var b = Date.parse(String(home.built || '')), cloudT = isFinite(b) ? b / 1000 : num(obj(home.board).t);
    return { pc: { t: pcT, age: pcT == null ? null : Math.max(0, Math.floor(t - pcT)) }, cloud: { t: cloudT, age: cloudT == null ? null : Math.max(0, Math.floor(t - cloudT)) } };
  }
  function lightAccounts(home) {
    var board = obj(home.board), out = {};
    [['lit', 'Zlarior', '50K', 2000], ['atlas', 'ATLAS', '25K', 1000]].forEach(function (m) {
      var b = obj(board[m[0]]), room = num(b.room);
      out[m[0]] = { has: room != null, name: m[1], size: m[2], room: room, mll: num(b.mll) || m[3], today: num(b.today_pnl) || num(b.today) || 0, paper: false };
    });
    return out;
  }
  var DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
  function etNow(t) {
    try {
      var p = {}, parts = new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', hourCycle: 'h23', weekday: 'short', hour: '2-digit', minute: '2-digit' }).formatToParts(new Date(t * 1000));
      parts.forEach(function (x) { p[x.type] = x.value; });
      return { wd: DAYS.indexOf(p.weekday), min: (parseInt(p.hour, 10) % 24) * 60 + parseInt(p.minute, 10) };
    } catch (e) { var dt = new Date((t - 5 * 3600) * 1000); return { wd: dt.getUTCDay(), min: dt.getUTCHours() * 60 + dt.getUTCMinutes() }; }
  }
  /* LIT takes entries 02:00-15:30 ET on weekdays: the published windows first (they know the holidays), else the clock */
  function nextWindow(home, t) {
    var wins = obj(obj(home.board).lit).windows;
    if (wins instanceof Array) {
      for (var i = 0; i < wins.length; i++) {
        var o = num(obj(wins[i]).open_t), c = num(obj(wins[i]).close_t);
        if (o != null && c != null && c > t) return { open: o <= t, label: String(wins[i].label || ''), inS: o <= t ? c - t : o - t };
      }
    }
    var e = etNow(t), wd = e.wd, OPEN = 120, CLOSE = 930;
    if (wd >= 1 && wd <= 5 && e.min >= OPEN && e.min < CLOSE) return { open: true, label: DAYS[wd] + ' 02:00-15:30 ET', inS: (CLOSE - e.min) * 60 };
    var days = 0, nd = wd;
    if (!(wd >= 1 && wd <= 5 && e.min < OPEN)) { days = 1; nd = (wd + 1) % 7; while (nd === 0 || nd === 6) { days++; nd = (nd + 1) % 7; } }
    return { open: false, label: DAYS[nd] + ' 02:00-15:30 ET', inS: days * 86400 + (OPEN - e.min) * 60 };
  }
  function summarize(home, T) {
    var t = nowS(), ages = null, A = null;
    if (T) { try { ages = T.agesOf(home, t); A = T.accountsOf(home); } catch (e) { ages = null; A = null; } }
    if (!ages || !A) { ages = lightAges(home, t); A = lightAccounts(home); }
    var pc = obj(obj(home.live).pc), board = obj(home.board);
    var running = typeof pc.running === 'boolean' ? pc.running : typeof board.running === 'boolean' ? board.running : null;
    var accts = [], today = 0;
    ['lit', 'atlas'].forEach(function (k) {
      var a = A[k]; if (!a || !a.has) return;
      accts.push({ key: k, name: a.name + ' ' + a.size, room: num(a.room), mll: num(a.mll) });
      today += num(a.today) || 0;
    });
    return { t: t, pcT: ages.pc.t, pcAge: ages.pc.age, cloudAge: ages.cloud ? ages.cloud.age : null, running: running, accts: accts, today: today, win: nextWindow(home, t), truth: !!T };
  }
  function fact(dl, label, value, sub, cls) {   // one cell of the 2 x 2 grid: label, the number, one small line
    var cell = el('div', 'g-fact'), dd = el('dd', cls || '', value);
    cell.appendChild(el('dt', '', label)); cell.appendChild(dd);
    if (sub) cell.appendChild(el('dd', 'g-fsub', sub));
    dl.appendChild(cell);
  }
  function drawNow(N, from) {
    var card = $('now'), badge = $('nowBadge'), line = $('nowLine'), dl = $('nowFacts'), btn = $('bringBack'), foot = $('nowFoot');
    var st, words = N.pcAge == null ? '' : ageWords(N.pcAge);
    if (from === 'none') st = ['none', 'bad', 'No numbers', 'No bot numbers reached this page.'];
    else if (N.pcT == null) st = ['stale', 'bad', 'No report', 'Your PC has not reported yet, so the bots cannot be seen from here.'];
    else if (N.pcAge > STALE_S) st = ['stale', 'bad', 'Old numbers', 'Not hearing from your PC for ' + words + '. These numbers are old.'];
    else if (N.pcAge > FRESH_S) st = ['quiet', 'warn', 'Quiet', 'Last report from your PC ' + words + ' ago. The bots may still be trading.'];
    else if (N.running === false) st = ['stopped', 'warn', 'Stopped', 'Your PC reported ' + words + ' ago: the bots are stopped there.'];
    else st = ['on', 'ok', 'Bots on', 'The bots are on. Last report ' + words + ' ago.'];
    if (from === 'cache') st[3] = 'No new numbers reached this page. The last ones this phone saw are below.';
    card.setAttribute('data-state', st[0]);
    badge.className = 'g-badge ' + st[1]; badge.textContent = st[2]; line.textContent = st[3];
    clear(dl);
    var old = st[0] === 'stale' || from === 'cache';
    if (from !== 'none') {
      N.accts.forEach(function (a) { fact(dl, 'Drawdown left', money(a.room), 'of ' + money(a.mll) + ' max loss, ' + a.name); });
      if (!N.accts.length) fact(dl, 'Drawdown left', 'Not in the report', '');
      fact(dl, old ? 'Last report day' : 'Today', moneyS(N.today), N.accts.length > 1 ? 'both eval accounts' : 'the eval account', N.today > 0.5 ? 'up' : N.today < -0.5 ? 'down' : '');
    }
    var W = N.win || nextWindow({}, nowS());
    fact(dl, 'Trade window', W.open ? 'Open now' : W.label.replace(/ 02:00-15:30 ET$/, ' 02:00 ET'), W.open ? 'until 15:30 ET' : inWords(W.inS));
    dl.hidden = false;
    btn.hidden = !(st[0] === 'stale');
    if (from === 'none') foot.textContent = 'This copy of the site has no live numbers. Bots shows the full status where it can.';
    else if (from === 'cache') foot.textContent = 'Saved on this phone ' + ageWords(nowS() - (N.saved || nowS())) + ' ago.';
    else if (from === 'pc') foot.textContent = 'Live from your PC. Updates every minute.';
    else foot.textContent = old ? '' : (N.cloudAge != null ? 'Cloud copy ' + ageWords(N.cloudAge) + ' old.' : '');
    S.now = { state: st[0], label: st[2], from: from || 'live', truth: !!N.truth };
  }
  /* served by the PC's own bot server through the private Tailscale link (engine/live_site.py serves the site at /site/): the bot's live
     numbers from /api/site/live.json, laid over home.json with pc_feed.js (the same rules as every app), refreshed every minute */
  var ON_PC = /^\/site\//.test(w.location.pathname || ''), LIVE_API = '/api/site/live.json', LIVE_EVERY_MS = 60000;
  function liveOver(home, live) {
    if (!live || live.kind !== 'le-live' || num(live.t) == null) return null;
    var h = home && typeof home === 'object' && !(home instanceof Array) ? home : {};
    if (w.PC_FEED && w.PC_FEED.overlayHome) return w.PC_FEED.overlayHome(h, live, nowS());
    var lv = obj(h.live), pc = {}, k, src = obj(live.pc), out = {};   /* pc_feed.js missing: the essentials only */
    for (k in obj(lv.pc)) pc[k] = lv.pc[k];
    for (k in src) pc[k] = src[k];
    pc.present = true; pc.t = num(live.t); pc.live = true;
    for (k in h) out[k] = h[k];
    out.live = {}; for (k in lv) out.live[k] = lv[k];
    out.live.pc = pc; if (live.pc_verdict) out.live.pc_verdict = live.pc_verdict;
    if (live.board && !live.board.error) out.board = live.board;
    return out;
  }
  function loadNow() {
    var liveP = ON_PC ? getJSON(LIVE_API) : null;
    getJSON(base + 'home.json').then(function (home) {
      if (!liveP) return show(home, null);
      liveP.then(function (live) { show(home, live); });
    });
  }
  function show(home, live) {
    var over = liveOver(home, live);
    if (over) home = over;
    if (!home || typeof home !== 'object' || home instanceof Array) {
      var c = lsGet(LS_NOW);
      if (c && c.N) { c.N.saved = c.saved; c.N.win = null; drawNow(c.N, 'cache'); } else drawNow({ accts: [], today: 0, pcT: null, pcAge: null }, 'none');
      S.nowDone = true; return;
    }
    getTruth(function (T) {
      var N = summarize(home, T);
      drawNow(N, over ? 'pc' : 'live');
      var keep = { pcT: N.pcT, pcAge: N.pcAge, running: N.running, accts: N.accts, today: N.today };
      lsSet(LS_NOW, { saved: nowS(), N: keep });
      S.nowDone = true;
    });
  }

  /* ------------------------------------------------------------------------------------------ Look: the OLYMPUS theme (olympus/themes.js, key 'olympus.theme')
     Six plain looks as swatches (a tiny card in the theme's own page, panel, accent, gain green and loss red); one tap applies it here at once and
     everywhere else (Jarvis's Look sheet shows the same key; another tab follows through the storage event). Hidden when the engine is not served. */
  function look() {
    var T = w.OLYMPUS_THEMES;
    if (!T || !T.plain) return;
    T.apply('page', { meta: true });
    var host = $('looks'), sec = $('lookSec');
    function draw() {
      var cur = T.id(), list = T.plain();
      clear(host);
      for (var i = 0; i < list.length; i++) (function (t) {
        var k = t.tokens, b = el('button', 'g-sw'), p = el('span', 'g-swp'), bar = el('i', 'g-swbar'), up = el('i', 'g-swup', '+$'), dn = el('i', 'g-swdn', '\u2212$');
        b.type = 'button'; b.setAttribute('role', 'radio'); b.setAttribute('aria-checked', String(t.id === cur)); b.setAttribute('data-theme-id', t.id);
        b.setAttribute('aria-label', t.name + ': ' + (t.tag || ''));
        p.setAttribute('aria-hidden', 'true');
        p.style.background = k.bg; p.style.borderColor = k.line; bar.style.background = k.bg2; bar.style.borderColor = k.accent; bar.style.color = k.text;
        up.style.color = k.ok; dn.style.color = k.bad;
        var dot = el('i', 'g-swdot'); dot.style.background = k.accent;
        bar.appendChild(dot); p.appendChild(bar); p.appendChild(up); p.appendChild(dn);
        b.appendChild(p); b.appendChild(el('b', '', t.name)); b.appendChild(el('small', '', (t.tag || '').split(' \u00b7 ')[0]));
        b.addEventListener('click', function () { T.set(t.id); draw(); });
        host.appendChild(b);
      })(list[i]);
      var now = T.get(cur), extra = $('lookHint');
      if (extra && now && !now.plain && now.id !== T.DEFAULT) extra.textContent = 'Now: ' + now.name + ' (picked in Jarvis). One tap below changes it everywhere.';
    }
    T.on(draw);
    draw();
    sec.hidden = false;
  }

  /* ------------------------------------------------------------------------------------------ start */
  function boot() {
    look();
    var tiles = d.querySelectorAll('.g-tile[data-app]');
    for (var i = 0; i < tiles.length; i++) (function (t) { t.addEventListener('click', function () { remember(t.getAttribute('data-app')); }); })(tiles[i]);
    if (C) {
      var doors = d.querySelectorAll('[data-district]');
      for (var j = 0; j < doors.length; j++) (function (b) {
        var did = b.getAttribute('data-district'), sm = b.querySelector('small');
        if (sm && did !== 'workshop') sm.appendChild(el('em', '', ' · ' + appsIn(did).length + ' apps'));
        b.addEventListener('click', function (e) { if (openSheet(did, b)) e.preventDefault(); });
      })(doors[j]);
      $('q').addEventListener('input', drawResults);
      $('q').addEventListener('keydown', function (e) {
        if (e.key !== 'Enter') return;
        var first = $('results').querySelector('a.g-row'); if (!first) return;
        e.preventDefault(); remember(first.getAttribute('data-app')); w.location.href = first.href;
      });
      if (Q.q) { $('q').value = Q.q; drawResults(); }
      drawRecent();
    } else {
      $('findHint').textContent = 'The app list did not load. The doors below open the map of every app.';
      $('q').disabled = true;
    }
    $('sheetClose').addEventListener('click', closeSheet);
    $('scrim').addEventListener('click', closeSheet);
    d.addEventListener('keydown', trap);
    swipe();
    w.addEventListener('pageshow', function (e) { if (e.persisted) { drawRecent(); closeSheet(); } });
    loadNow();
    if (ON_PC && w.setInterval) w.setInterval(function () { if (d.visibilityState !== 'hidden' && !S.sheet) loadNow(); }, LIVE_EVERY_MS);
    if (Q.d && C) openSheet(Q.d, null);
  }

  w.GATE = { ready: function () { return S.nowDone; }, state: S, open: openSheet, close: closeSheet, hrefOf: hrefOf, base: base };
  if (d.readyState === 'loading') d.addEventListener('DOMContentLoaded', boot); else boot();
})();
