/* agency sites: the one small script (ES5, same origin, nothing fetched). Without it the page still works:
   it only adds the "Open now" line, marks today's hours, closes the menu after a tap and, on a PREVIEW, keeps the
   form from posting before the site is live. Original, CC0. */
(function () {
  'use strict';
  var d = document;
  var DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

  function data() {
    var el = d.getElementById('site-data');
    if (!el) return null;
    try { return JSON.parse(el.textContent); } catch (e) { return null; }
  }

  function clock(m) {
    m = m % 1440;
    if (m === 0) return 'midnight';
    if (m === 720) return 'noon';
    var h = Math.floor(m / 60), mm = m % 60, s = h < 12 ? 'AM' : 'PM';
    h = h % 12 || 12;
    return h + (mm ? ':' + (mm < 10 ? '0' : '') + mm : '') + ' ' + s;
  }

  function now(tz) {
    var dt = new Date(), wd = (dt.getDay() + 6) % 7, mins = dt.getHours() * 60 + dt.getMinutes();
    try {
      var parts = new Intl.DateTimeFormat('en-US', { timeZone: tz, weekday: 'short', hour: 'numeric', minute: 'numeric', hourCycle: 'h23' }).formatToParts(dt);
      var map = {};
      for (var i = 0; i < parts.length; i++) map[parts[i].type] = parts[i].value;
      var idx = DAYS.indexOf(map.weekday);
      if (idx >= 0) { wd = idx; mins = (parseInt(map.hour, 10) % 24) * 60 + parseInt(map.minute, 10); }
    } catch (e) { /* old browser: the visitor's own clock */ }
    return { day: wd, mins: mins };
  }

  function state(week, t) {
    var today = week[t.day] || [], prev = week[(t.day + 6) % 7] || [], i;
    for (i = 0; i < prev.length; i++) if (prev[i][1] > 1440 && t.mins < prev[i][1] - 1440) return { open: true, until: prev[i][1] };
    for (i = 0; i < today.length; i++) if (t.mins >= today[i][0] && t.mins < today[i][1]) return { open: true, until: today[i][1], from: today[i][0] };
    for (var k = 0; k < 7; k++) {
      var day = (t.day + k) % 7, ivs = week[day] || [];
      for (i = 0; i < ivs.length; i++) if (k > 0 || ivs[i][0] > t.mins) return { open: false, day: k === 0 ? 'today' : k === 1 ? 'tomorrow' : DAYS[day], at: ivs[i][0] };
    }
    return { open: false };
  }

  var D = data();
  if (D && D.week) {
    var t = now(D.tz), s = state(D.week, t), text;
    if (s.open) text = s.from === 0 && s.until >= 1440 ? 'Open 24 hours today' : 'Open now, until ' + clock(s.until);
    else text = s.day ? 'Closed now, opens ' + s.day + ' at ' + clock(s.at) : 'Closed now';
    var els = d.querySelectorAll('[data-open]');
    for (var i = 0; i < els.length; i++) { els[i].textContent = text; els[i].className = 'state ' + (s.open ? 'open' : 'closed'); }
    var rows = d.querySelectorAll('[data-days]');
    for (var r = 0; r < rows.length; r++) if ((',' + rows[r].getAttribute('data-days') + ',').indexOf(',' + t.day + ',') >= 0) rows[r].className += ' today';
  }

  var menu = d.querySelector('details.menu');
  if (menu) menu.addEventListener('click', function (e) { if (e.target && e.target.tagName === 'A') menu.removeAttribute('open'); });

  var form = d.querySelector('form[data-preview]');
  if (form) form.addEventListener('submit', function (e) {
    e.preventDefault();
    var msg = d.getElementById('formmsg');
    if (msg) msg.textContent = 'This is a preview, so nothing was sent. On the live site this message goes straight to the business.';
  });
})();
