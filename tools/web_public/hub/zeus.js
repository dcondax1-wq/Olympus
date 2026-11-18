/* ZEUS (hub/zeus.html, 2026-11-18, night-zeushub): what the owner opens when he thinks "trading". One page, phone first:
 *   1. live strip   "PC reported X min ago" (red when silent) + each account: name, stage chip, balance, $ to pass / payout, today's $
 *                   Data: PC_FEED.fetchLatest (core + ext merged) + ../board/board.json fallback + ../business/accounts.json (plan),
 *                   matched by PC id / Name exactly like the Board (BOARD_MODEL.pick for the PC age, MFFU_MODEL.cards for the rows)
 *   2. ZEUS edge chip (../edge_chip.js) for Zlarior and ATLAS
 *   3. today        the next entry window of Zlarior and ATLAS (the PC's own window when it sent one, else the same hours as
 *                   engine/live_board.py: LIT 02:00-15:30, ATLAS MACD 02:00-05:00 + 09:30-11:00, EMA 03:00-09:30 not Mondays,
 *                   S/R 09:30-12:00; weekends + CME closures skipped, an early close ends entries 15 min before the halt) and the
 *                   news / early-close notes of the next 7 days from ../pythia/events.json (data/news + the CME holiday rules); none = skipped
 *   4. big buttons  + the Safety and Add-an-account explanations (never a link: safety lives on the PC's private Tailscale link)
 * Read only: no write, no order, nothing armed. Text only through textContent. Classic script: window.ZEUS_HUB (module.exports in node:
 * the pure part, tests/test_zeus_hub.py). */
(function (root) {
  'use strict';
  var isObj = function (x) { return !!x && typeof x === 'object' && !Array.isArray(x); };
  var okN = function (v) { return typeof v === 'number' && isFinite(v); };
  var MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  var DOW = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
  // the bots' entry hours (ET minutes) = engine/live_board.py LIT_WINDOW / ATLAS_WINDOWS / ATLAS_NO_MONDAY
  var BOTS = {
    lit: { name: 'Zlarior', what: 'LIT', hours: '02:00-15:30 ET', note: 'most trades 02:00-08:00', parts: [{ k: 'LIT', r: [[120, 930]] }] },
    atlas: { name: 'ATLAS', what: 'EMA · MACD · S/R', hours: 'MACD 02:00-05:00 + 09:30-11:00 · EMA 03:00-09:30 (not Mon) · S/R 09:30-12:00',
             parts: [{ k: 'MACD', r: [[120, 300], [570, 660]] }, { k: 'EMA', r: [[180, 570]], noMon: true }, { k: 'S/R', r: [[570, 720]] }] }
  };

  var fmt = null;
  function et(tS) {                                       // {day 'yyyy-mm-dd', min, dow} of an epoch second in New York
    if (!fmt) fmt = new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' });
    var p = {}; fmt.formatToParts(new Date(tS * 1000)).forEach(function (x) { p[x.type] = x.value; });
    var day = p.year + '-' + p.month + '-' + p.day;
    return { day: day, min: (+p.hour % 24) * 60 + (+p.minute), dow: new Date(day + 'T12:00:00Z').getUTCDay() };
  }
  function addDays(d, n) { var t = new Date(d + 'T12:00:00Z'); t.setUTCDate(t.getUTCDate() + n); return t.toISOString().slice(0, 10); }
  function dayDiff(a, b) { return Math.round((Date.parse(a + 'T12:00:00Z') - Date.parse(b + 'T12:00:00Z')) / 86400000); }
  function hm(m) { return ('0' + Math.floor(m / 60)).slice(-2) + ':' + ('0' + (m % 60)).slice(-2); }
  function toMin(s) { var m = /^(\d{1,2}):(\d{2})$/.exec(String(s || '')); return m ? +m[1] * 60 + (+m[2]) : null; }
  function dayWord(d, today) {
    var n = dayDiff(d, today);
    if (n === 0) return 'Today';
    if (n === 1) return 'Tomorrow';
    var t = new Date(d + 'T12:00:00Z');
    return DOW[t.getUTCDay()] + ' ' + MON[t.getUTCMonth()] + ' ' + t.getUTCDate();
  }
  function inWords(mins) {
    mins = Math.max(0, Math.round(mins));
    if (mins < 60) return mins + ' min';
    var h = Math.floor(mins / 60), m = mins % 60;
    if (h >= 24) return Math.round(h / 24 * 10) / 10 + ' days';
    return h + ' h' + (m ? ' ' + m + ' min' : '');
  }

  // closed days + early closes from pythia/events.json (closed: true / kind holiday = closed; kind early + close_et = early halt)
  function calendar(evj) {
    var cal = { closed: {}, early: {} };
    (isObj(evj) && Array.isArray(evj.events) ? evj.events : []).forEach(function (e) {
      if (!isObj(e) || !/^\d{4}-\d{2}-\d{2}$/.test(String(e.date || ''))) return;
      if (e.closed === true) cal.closed[e.date] = true;
      var c = toMin(e.close_et);
      if (e.kind === 'early' && c != null) cal.early[e.date] = c;
    });
    return cal;
  }

  // the first window that has not closed yet: {open, day, a, z, who, mins (to open, or to close when open), early}
  function nextWindow(nowS, parts, cal) {
    var n = et(nowS), c = cal || { closed: {}, early: {} }, best = null;
    for (var i = 0; i <= 12 && !best; i++) {
      var d = addDays(n.day, i), dow = new Date(d + 'T12:00:00Z').getUTCDay();
      if (dow === 0 || dow === 6 || c.closed[d]) continue;
      var ec = c.early[d];
      parts.forEach(function (p) {
        if (p.noMon && dow === 1) return;
        p.r.forEach(function (r) {
          var a = r[0], z = ec != null ? Math.min(r[1], ec - 15) : r[1];
          if (z <= a) return;
          if (i === 0 && z <= n.min) return;
          var open = i === 0 && a <= n.min;
          var w = { open: open, day: d, a: a, z: z, who: p.k, early: ec != null ? hm(ec) : null, mins: open ? z - n.min : i * 1440 + a - n.min };
          if (!best || (w.open && !best.open) || (w.open === best.open && (w.open ? w.z > best.z : w.mins < best.mins))) best = w;
        });
      });
    }
    return best;
  }

  // the PC's own window (board card lit / atlas "window": {open, open_t, close_t, who}) when it is still current
  function pcWindow(card, nowS) {
    var w = isObj(card) && isObj(card.window) ? card.window : null;
    if (!w || !okN(+w.open_t) || !okN(+w.close_t) || +w.close_t <= nowS) return null;
    var o = et(+w.open_t), z = et(+w.close_t), open = +w.open_t <= nowS;
    return { open: open, day: o.day, a: o.min, z: z.min, who: w.who || '', early: null, mins: open ? (+w.close_t - nowS) / 60 : (+w.open_t - nowS) / 60, pc: true };
  }

  function windowLine(key, nowS, cal, lite) {
    var B = BOTS[key], card = isObj(lite) && isObj(lite.board) ? lite.board[key] : null;
    var w = pcWindow(card, nowS) || nextWindow(nowS, B.parts, cal), today = et(nowS).day;
    if (!w) return { key: key, name: B.name, text: 'No entry window in the next days', sub: B.hours, open: false };
    var who = key === 'atlas' && w.who ? w.who + ' ' : '';
    var text = w.open ? 'Open now: ' + who + 'until ' + hm(w.z) + ' ET (' + inWords(w.mins) + ' left)'
      : 'Next: ' + dayWord(w.day, today) + ' ' + who + hm(w.a) + '-' + hm(w.z) + ' ET (in ' + inWords(w.mins) + ')';
    var sub = B.hours + (B.note ? ' · ' + B.note : '') + (w.early ? ' · early close ' + w.early + ' ET that day' : '') + (w.pc ? ' · from your PC' : '');
    return { key: key, name: B.name, text: text, sub: sub, open: !!w.open, day: w.day };
  }

  // news + early closes + closed days, today and the next `days` days (high / med news, every early close / holiday)
  function notes(evj, nowS, days) {
    if (!isObj(evj) || !Array.isArray(evj.events)) return null;
    var today = et(nowS).day, last = addDays(today, days == null ? 7 : days), out = [];
    evj.events.forEach(function (e) {
      if (!isObj(e) || !e.date || e.date < today || e.date > last) return;
      var shut = e.closed === true || e.kind === 'holiday', early = e.kind === 'early';
      if (!shut && !early && e.impact !== 'high' && e.impact !== 'med') return;
      out.push({ day: e.date, when: dayWord(e.date, today) + (e.time && !shut ? ' ' + e.time + ' ET' : ''), title: String(e.title || e.kind || ''),
                 kind: shut ? 'closed' : early ? 'early' : String(e.impact), today: e.date === today, check: !!e.verify });
    });
    out.sort(function (a, b) { return a.day < b.day ? -1 : a.day > b.day ? 1 : 0; });
    return { items: out.slice(0, 6), updated: evj.updated || null };
  }

  function usd(v, sign) {
    if (!okN(v)) return '-';
    var s = '$' + Math.abs(Math.round(v)).toLocaleString('en-US');
    return v < 0 ? '-' + s : sign && v > 0 ? '+' + s : s;
  }
  function ago(s) {
    if (s == null || !isFinite(s)) return 'never';
    s = Math.max(0, Math.round(s));
    if (s < 90) return 'just now';
    if (s < 5400) return Math.round(s / 60) + ' min ago';
    if (s < 2 * 86400) return Math.round(s / 3600) + ' h ago';
    return Math.round(s / 86400) + ' days ago';
  }

  // the PC line from the Board's pick (same STALE_S = 30 min): {silent, text}
  function pcLine(BM, res, nowS) {
    var b = res && res.board, t = b && b.pc && okN(+b.pc.t) && +b.pc.t > 0 ? +b.pc.t : null;
    var age = t ? nowS - t : null, silent = age == null || age > (BM && BM.STALE_S || 1800);
    return { silent: silent, age_s: age, mode: res ? res.mode : 'none',
             text: !t ? 'PC SILENT: your PC has never reported here. The bots may not be running.'
               : silent ? 'PC SILENT: last report ' + ago(age) + '. On the PC: STOP BOT, then START BOT.' : 'PC reported ' + ago(age) };
  }

  // one account row from an MFFU_MODEL card: {name, chip, cls, balance, goal, today, src}
  function acctRow(c, nowS) {
    var st = String(c.stage || 'eval'), chip = c.status || 'Evaluation', goal;
    var cls = st === 'funded' ? 'funded' : st === 'passed' ? 'passed' : st === 'failed' || chip === 'Failed' ? 'failed' : 'eval';
    if (cls === 'failed') goal = 'Floor reached: this account is done';
    else if (st === 'funded') goal = c.payout && c.payout.c && c.payout.c.text ? c.payout.c.text : 'Funded: payout status needs the PC\'s payout tracker';
    else if (st === 'passed') goal = 'Passed: waiting for MFFU\'s funded account';
    else goal = c.target && okN(c.target.left) ? usd(c.target.left) + ' to pass' : 'To pass: no live balance yet';
    var today = c.dll && okN(c.dll.today) ? c.dll.today : null;
    var src = c.balance && c.balance.src ? c.balance.src + (c.age_s != null ? ' · ' + ago(c.age_s) : '') : 'no number yet';
    return { key: c.key, name: c.name, chip: chip, cls: cls, balance: c.balance ? c.balance.v : null, goal: goal, today: today,
             todayText: today == null ? 'Today: -' : 'Today: ' + usd(today, true), src: src, planOnly: !!c.planOnly };
  }

  var API = { BOTS: BOTS, et: et, calendar: calendar, nextWindow: nextWindow, pcWindow: pcWindow, windowLine: windowLine, notes: notes,
              pcLine: pcLine, acctRow: acctRow, usd: usd, ago: ago, inWords: inWords };
  root.ZEUS_HUB = API;
  if (typeof module === 'object' && module && module.exports) module.exports = API;
  if (typeof document === 'undefined') return;

  // ------------------------------------------------------------------------------------------------ the page
  var d = document, $ = function (id) { return d.getElementById(id); };
  function el(tag, cls, text) { var e = d.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = String(text); return e; }
  function nowS() { return Math.floor(Date.now() / 1000); }
  function todayET() { return et(nowS()).day; }
  function getJSON(u, ms) {
    var ac = typeof AbortController === 'function' ? new AbortController() : null, tm = ac ? setTimeout(function () { ac.abort(); }, ms || 6000) : 0;
    return fetch(u, ac ? { cache: 'no-cache', signal: ac.signal } : { cache: 'no-cache' }).then(function (r) { return r.ok ? r.json() : null; })
      .catch(function () { return null; }).then(function (j) { clearTimeout(tm); return j; });
  }

  function drawStrip(pl, rows) {
    var s = $('pc');
    s.className = 'zs-pc ' + (pl.silent ? 'bad' : 'good');
    s.setAttribute('role', pl.silent ? 'alert' : 'status');
    s.replaceChildren();
    s.appendChild(el('span', 'zs-dot'));
    s.appendChild(el('b', '', pl.text));
    var box = $('accts'); box.replaceChildren();
    rows.forEach(function (r) {
      var a = el('article', 'zs-acct'); a.setAttribute('data-key', r.key);
      var top = el('div', 'zs-top');
      top.appendChild(el('h3', '', r.name));
      top.appendChild(el('span', 'zs-chip ' + r.cls, (r.planOnly ? 'PLAN · ' : '') + r.chip));
      a.appendChild(top);
      var mid = el('div', 'zs-mid');
      mid.appendChild(el('span', 'zs-bal', usd(r.balance)));
      mid.appendChild(el('span', 'zs-today' + (r.today > 0 ? ' pos' : r.today < 0 ? ' neg' : ''), r.todayText));
      a.appendChild(mid);
      a.appendChild(el('p', 'zs-goal', r.goal));
      a.appendChild(el('p', 'zs-src', 'Source: ' + r.src));
      box.appendChild(a);
    });
    if (!rows.length) box.appendChild(el('p', 'zs-empty', 'No accounts to show yet: the PC has not reported and the plan file did not load.'));
  }

  function drawToday(lines, nt) {
    var w = $('wins'); w.replaceChildren();
    lines.forEach(function (x) {
      var r = el('div', 'zs-win' + (x.open ? ' open' : '')); r.setAttribute('data-bot', x.key);
      r.appendChild(el('b', '', x.name));
      r.appendChild(el('span', '', x.text));
      r.appendChild(el('small', '', x.sub));
      w.appendChild(r);
    });
    var box = $('notes'), ul = $('noteList'); ul.replaceChildren();
    if (!nt) { box.hidden = true; return; }                     // no calendar published: skip
    box.hidden = false;
    nt.items.forEach(function (n) {
      var li = el('li', 'zs-note ' + n.kind + (n.today ? ' today' : ''));
      li.appendChild(el('b', '', n.when));
      li.appendChild(el('span', '', n.title + (n.check ? ' (check)' : '')));
      ul.appendChild(li);
    });
    if (!nt.items.length) ul.appendChild(el('li', 'zs-note none', 'No big news, holiday or early close in the next 7 days.'));
    $('noteSrc').textContent = 'From the risk calendar (data/news + CME holiday rules)' + (nt.updated ? ', updated ' + nt.updated : '') + '. ZEUS stands aside around news by itself.';
  }

  var busy = false;
  function load() {
    if (busy) return Promise.resolve();
    busy = true;
    var BM = root.BOARD_MODEL, MM = root.MFFU_MODEL;
    return Promise.all([getJSON('../business/accounts.json'), getJSON('../board/board.json'), getJSON('../pythia/events.json'),
      root.PC_FEED ? Promise.race([root.PC_FEED.fetchLatest({}), new Promise(function (r) { setTimeout(function () { r(null); }, 8000); })]).catch(function () { return null; }) : null])
      .then(function (v) {
        var plan = v[0], site = v[1], evj = v[2], lite = v[3], now = nowS();
        var res = BM ? BM.pick({ site: site, lite: lite, plan: plan }, now) : null;
        var pl = pcLine(BM, res, now);
        var cards = [];
        try { if (MM) cards = MM.cards({ lite: lite, plan: plan, board: site, coach: root.PAYOUT_COACH, today: todayET() }, now); } catch (e) { cards = []; }
        var rows = cards.filter(function (c) { return !/blitz/i.test(String(c.key)); }).map(function (c) { return acctRow(c, now); });
        drawStrip(pl, rows);
        try { if (root.EDGE_CHIP) root.EDGE_CHIP.update(lite); } catch (e) { /* never the page */ }
        var cal = calendar(evj);
        drawToday([windowLine('lit', now, cal, lite), windowLine('atlas', now, cal, lite)], notes(evj, now, 7));
        $('stamp').textContent = 'Checked ' + new Date(now * 1000).toLocaleTimeString('en-US', { timeZone: 'America/New_York', hour: 'numeric', minute: '2-digit' }) + ' ET'
          + (res ? ' · ' + res.label : '');
        root.ZEUS_PAGE.last = { pc: pl, rows: rows, mode: res ? res.mode : 'none' };
        root.ZEUS_PAGE.ready = true;
      })
      .then(function () { busy = false; }, function () { busy = false; root.ZEUS_PAGE.ready = true; });
  }

  // Weekly review: shown only when business/week.html exists on this site
  function weekly() {
    var a = $('btnWeek'); if (!a) return;
    fetch(a.getAttribute('href'), { method: 'HEAD', cache: 'no-cache' }).then(function (r) { a.hidden = !r.ok; }, function () { a.hidden = true; });
  }

  root.ZEUS_PAGE = { load: load, last: null, ready: false };
  function start() {
    var rb = $('refresh'); if (rb) rb.addEventListener('click', load);
    weekly();
    load();
    setInterval(function () { if (!d.hidden) load(); }, 60000);
    window.addEventListener('pageshow', function (e) { if (e.persisted) load(); });
  }
  if (d.readyState === 'loading') d.addEventListener('DOMContentLoaded', start); else start();
}(typeof window !== 'undefined' ? window : globalThis));
