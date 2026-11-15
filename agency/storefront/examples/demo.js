/* Example demo sites: the "open now" badge, the demo forms and the screenshot mode. Nothing is sent anywhere. */
(function () {
  'use strict';
  var d = document;
  var root = d.documentElement;
  var q = location.search;
  root.classList.add('js');
  if (/[?&]shot\b/.test(q)) { root.classList.add('shot'); }

  // ?now=2026-11-13T18:30 fixes the clock (tests, screenshots); screenshot mode uses a Friday evening
  var m = /[?&]now=([0-9T:-]+)/.exec(q);
  var now = m ? new Date(m[1]) : (root.classList.contains('shot') ? new Date('2026-11-13T18:30:00') : new Date());

  function hm(h) {
    var hh = Math.floor(h);
    var mm = Math.round((h - hh) * 60);
    var ap = hh >= 12 && hh < 24 ? 'pm' : 'am';
    var h12 = hh % 12 === 0 ? 12 : hh % 12;
    return h12 + (mm ? ':' + (mm < 10 ? '0' : '') + mm : '') + ap;
  }

  // <p data-hours='{"0":[12,21],"1":null,...}'> (0 = Sunday, hours as 17.5 = 5:30pm)
  Array.prototype.forEach.call(d.querySelectorAll('[data-hours]'), function (el) {
    var hours;
    try { hours = JSON.parse(el.getAttribute('data-hours')); } catch (e) { return; }
    var day = now.getDay();
    var t = now.getHours() + now.getMinutes() / 60;
    var today = hours[String(day)];
    var text;
    var open = false;
    if (today && t >= today[0] && t < today[1]) {
      open = true;
      text = 'Open now · until ' + hm(today[1]);
    } else {
      var later = today && t < today[0];
      if (later) {
        text = 'Closed now · opens ' + hm(today[0]) + ' today';
      } else {
        for (var i = 1; i <= 7; i++) {
          var nd = (day + i) % 7;
          var h = hours[String(nd)];
          if (h) { text = 'Closed now · opens ' + hm(h[0]) + (i === 1 ? ' tomorrow' : ' ' + ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'][nd]); break; }
        }
      }
    }
    if (text) {
      el.textContent = text;
      el.classList.toggle('is-open', open);
      el.classList.toggle('is-closed', !open);
      el.hidden = false;
    }
  });

  // demo forms: a friendly note instead of sending
  Array.prototype.forEach.call(d.querySelectorAll('[data-demo-form]'), function (f) {
    var b = f.querySelector('[data-demo-send]');
    var msg = f.querySelector('[data-demo-msg]');
    if (!b || !msg) { return; }
    b.addEventListener('click', function () {
      msg.hidden = false;
      msg.textContent = 'This is a demo, so nothing was sent. On your real website this request goes straight to your phone and email.';
    });
  });

  // chips in the demo booking box: one choice per group
  Array.prototype.forEach.call(d.querySelectorAll('[data-pick]'), function (g) {
    g.addEventListener('click', function (e) {
      var b = e.target.closest('button');
      if (!b) { return; }
      Array.prototype.forEach.call(g.querySelectorAll('button'), function (x) { x.setAttribute('aria-pressed', x === b ? 'true' : 'false'); });
    });
  });
})();
