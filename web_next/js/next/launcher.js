/* OLYMPUS launcher for Zenith (2026-11-04). ONE file, byte-identical in both dashboards (tools/web_public/launcher.js = web_next/js/next/launcher.js):
 * a button in the Zenith top bar opens a glass sheet with every OLYMPUS app. A classic deferred script, the only tag the page needs. The list
 * (olympus/apps-list.js on the phone, js/next/apps-list.js on the PC) is loaded by this script, async, 4 s after the page is up or when the sheet opens, so a
 * slow site never holds Zenith back (a deferred file would). The list is generated from jarvis/apps.js + olympus/olympus.js by tools/apps_list_build.py (window.OLYMPUS_APPS_LIST).
 *   top      a big "Open Olympus (Jarvis)" button, then a search box and your 4 most recent apps
 *   grid     Trading / Life / Money: each app a tile (its glyph in its own colour, name, one plain line, a status dot)
 *   status   the dot comes from <app>/jarvis.json (fetched only when the sheet opens, 4 at a time, 5 s each, kept 5 min in
 *            localStorage 'oly.launcher.status'): green = running well, amber = needs a look, red = a problem, grey = not updated
 *            for 30 minutes, no dot = the app has no status card. A failed fetch keeps the last dot.
 *   links    phone (the site's own origin): the app's folder, "<app>/", in this tab. PC dashboard (localhost:8766 / web_next, which has no apps):
 *            the public site, https://demetrades2000-coder.github.io/nq-dashboard/<app>/, in a new tab.
 *   recent   localStorage 'oly.launcher.recent' = ["oracle", ...], newest first, 4 kept.
 *   quality  LITE / reduced motion (ZenithFX when the page has it, else prefers-reduced-motion): no entrance animation, no glow sweep, no tilt.
 * Read-only: it only reads jarvis.json files and links to pages; it never posts, writes to a bot or touches an account.
 * window.OLYMPUS_LAUNCHER = { open(), close(), isOpen(), state() } (the tests). Never blank: without the list the sheet still has the Jarvis button. */
(function () {
  'use strict';
  if (window.OLYMPUS_LAUNCHER) return;
  var d = document, root = d.documentElement;
  var PUBLIC = 'https://demetrades2000-coder.github.io/nq-dashboard/';
  var RECENT_KEY = 'oly.launcher.recent', STATUS_KEY = 'oly.launcher.status', RECENT_MAX = 4, STATUS_TTL = 5 * 60 * 1000, STALE_S = 30 * 60, FETCH_MS = 5000, PARALLEL = 4;
  var GROUPS = [['trading', 'Trading'], ['life', 'Life'], ['money', 'Money']];
  // Every app keeps its registry glyph and receives a small visual signature. These names are presentation only:
  // routes, status, order and the generated app list remain the existing sources of truth.
  var GLYPH_MOTION = { oracle:'scan', odeon:'curtain', fates:'thread', datacity:'rise', tree:'leaf', prometheus:'flame', pantheon:'lightning', ares:'shield', forum:'banner', labyrinth:'maze', argus:'blink', nemesis:'scale', chronos:'tick', hephaestus:'forge', cities:'flight', kalshicity:'flow', journal:'ripple', ledger:'vault', inbox:'letter', settings:'control', bridge:'portal', planner:'calendar', mind:'neuron', arena:'laurel', athena:'owl', kalshi:'market', tyche:'coin', hermes:'wing', plutus:'treasure', atlas:'cartography', observatory:'lens' };
  var isPC = false, base = '';                                  // decided at mount (the PC dashboard's own top bar is there, or port 8766)
  var st = { open: false, q: '', apps: [], tiles: {}, status: {}, fetching: false, lastFetch: 0, built: false };
  var els = {}, lastFocus = null;

  function get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function set(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* private mode: this visit only */ } }
  function json(k, fb) { try { var v = JSON.parse(get(k) || 'null'); return v == null ? fb : v; } catch (e) { return fb; } }
  function calm() {
    try { if (window.ZenithFX && (ZenithFX.still && ZenithFX.still() || ZenithFX.lite && ZenithFX.lite())) return true; } catch (e) { /* the media query below */ }
    try { return !!(window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches); } catch (e) { return false; }
  }
  function el(tag, cls, text) { var e = d.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = String(text); return e; }
  function rgb(hex) { var h = String(hex || '#a855f7'); return [1, 3, 5].map(function (i) { return parseInt(h.substr(i, 2), 16) || 0; }).join(', '); }
  function url(path) { return base + path; }

  // ---------------------------------------------------------------- the list (Zenith itself is not in its own launcher)
  var listState = 'idle', waiters = [];                         // idle | loading | done | failed
  function loadList(cb) {
    if (window.OLYMPUS_APPS_LIST || listState === 'failed') { if (cb) cb(); return; }
    if (cb) waiters.push(cb);
    if (listState === 'loading') return;
    listState = 'loading';
    var s = d.createElement('script'), fin = function () { listState = window.OLYMPUS_APPS_LIST ? 'done' : 'failed'; var w = waiters; waiters = []; w.forEach(function (f) { try { f(); } catch (e) { /* */ } }); };
    s.async = true; s.src = isPC ? '/js/next/apps-list.js?v=l2' : 'olympus/apps-list.js?v=l1';
    s.onload = fin; s.onerror = fin;
    (d.head || root).appendChild(s);
  }
  function apps() {
    var L = window.OLYMPUS_APPS_LIST;
    if (!L || !L.length) return [];
    var out = [];
    for (var i = 0; i < L.length; i++) if (L[i].id !== 'zenith' && L[i].path) out.push(L[i]);
    return out;
  }

  // ---------------------------------------------------------------- recent
  function recent() { var r = json(RECENT_KEY, []); return Array.isArray(r) ? r.filter(function (x) { return typeof x === 'string'; }).slice(0, RECENT_MAX) : []; }
  function touch(id) { var r = recent().filter(function (x) { return x !== id; }); r.unshift(id); set(RECENT_KEY, JSON.stringify(r.slice(0, RECENT_MAX))); }

  // ---------------------------------------------------------------- status dots
  var WORDS = { ok: 'Running well', warn: 'Needs a look', bad: 'A problem', stale: 'Not updated for a while', off: 'Resting', none: 'No status card' };
  function level(card) {
    var lv = card && card.status && card.status.level, t = card && +card.t;
    if (lv !== 'ok' && lv !== 'warn' && lv !== 'bad' && lv !== 'off') return 'none';
    if (lv !== 'off' && t && Date.now() / 1000 - t > STALE_S) return 'stale';
    return lv;
  }
  function paintDot(id) {
    var tile = st.tiles[id]; if (!tile) return;
    var s = st.status[id], lv = s ? s.lv : 'none', dot = tile.querySelector('.oly-dot');
    dot.className = 'oly-dot ' + lv;
    var label = s && s.label ? WORDS[lv] + ': ' + s.label : WORDS[lv];
    dot.title = label; dot.setAttribute('aria-label', label);
    tile.setAttribute('data-status', lv);
  }
  function fetchJson(u) {
    return new Promise(function (res) {
      var done = false, ac = typeof AbortController === 'function' ? new AbortController() : null;
      var timer = setTimeout(function () { if (!done) { done = true; if (ac) ac.abort(); res(undefined); } }, FETCH_MS);
      fetch(u, { cache: 'no-cache', credentials: 'omit', signal: ac ? ac.signal : undefined }).then(function (r) { return r.ok ? r.json() : null; }).then(function (j) {
        if (!done) { done = true; clearTimeout(timer); res(j); }
      }, function () { if (!done) { done = true; clearTimeout(timer); res(undefined); } });
    });
  }
  function loadStatus() {
    var saved = json(STATUS_KEY, {}); if (saved && typeof saved === 'object') for (var k in saved) if (!st.status[k] && saved[k] && saved[k].lv) st.status[k] = saved[k];
    st.apps.forEach(function (a) { paintDot(a.id); });
    if (st.fetching || Date.now() - st.lastFetch < 2 * 60 * 1000) return;
    var fresh = Object.keys(st.status).length && st.apps.filter(function (a) { return a.live; }).every(function (a) { return st.status[a.id] && Date.now() - (st.status[a.id].at || 0) < STATUS_TTL; });
    if (fresh) return;
    st.fetching = true; st.lastFetch = Date.now();
    var todo = st.apps.filter(function (a) { return a.live; }), i = 0, running = 0;
    function next() {
      while (running < PARALLEL && i < todo.length) {
        (function (a) {
          running++;
          fetchJson(url(a.path + 'jarvis.json')).then(function (card) {
            if (card === undefined) { /* no answer: the last dot stays */ }
            else { st.status[a.id] = { lv: level(card), label: card && card.status && card.status.label ? String(card.status.label).slice(0, 48) : '', at: Date.now() }; paintDot(a.id); }
            running--; next();
          });
        })(todo[i++]);
      }
      if (i >= todo.length && running === 0 && st.fetching) { st.fetching = false; set(STATUS_KEY, JSON.stringify(st.status)); }
    }
    next();
  }

  // ---------------------------------------------------------------- the sheet
  var CSS = [
    '.oly-lbtn{display:inline-grid;grid-auto-flow:column;align-items:center;justify-content:center;gap:7px;min-width:40px;height:40px;padding:0 11px;border-radius:12px;cursor:pointer;color:var(--ink-2,#a9b1c3);',
    'background:rgba(22,26,35,.7);border:1px solid var(--line,rgba(160,170,220,.14));font:700 12px/1 var(--font,Inter,system-ui,sans-serif);letter-spacing:.08em;transition:color .18s,border-color .18s,box-shadow .18s}',
    '.oly-lbtn:hover,.oly-lbtn:focus-visible{color:var(--ink,#eef1f8);border-color:rgba(168,85,247,.6);box-shadow:0 0 16px rgba(168,85,247,.3)}',
    '.oly-lbtn svg{width:18px;height:18px;display:block}.oly-lbtn .t{display:none}@media(min-width:900px){.oly-lbtn .t{display:inline}}',
    '.oly-lbtn.float{position:fixed;top:calc(10px + env(safe-area-inset-top,0px));right:calc(12px + env(safe-area-inset-right,0px));z-index:8000;background:rgba(10,12,22,.82)}',
    '.oly-l{position:fixed;left:0;top:0;right:0;bottom:0;z-index:9000;display:flex;align-items:flex-end;justify-content:center;font-family:var(--font,Inter,system-ui,sans-serif)}',
    '.oly-l[hidden]{display:none}.oly-l .oly-bd{position:absolute;left:0;top:0;right:0;bottom:0;background:rgba(3,4,10,.62);-webkit-backdrop-filter:blur(6px);backdrop-filter:blur(6px)}',
    '.oly-l .oly-pn{position:relative;isolation:isolate;width:100%;max-width:640px;max-height:90vh;max-height:90dvh;display:flex;flex-direction:column;border-radius:22px 22px 0 0;overflow:hidden;color:#eef1f8;',
    'background:linear-gradient(165deg,rgba(26,18,52,.94),rgba(9,11,22,.96) 55%);-webkit-backdrop-filter:blur(18px);backdrop-filter:blur(18px);border:1px solid rgba(168,85,247,.38);border-bottom:0;',
    'box-shadow:0 -18px 60px rgba(0,0,0,.55),0 0 50px rgba(168,85,247,.18),inset 0 1px 0 rgba(255,255,255,.08)}',
    '.oly-l .oly-pn::before,.oly-l .oly-pn::after{content:"";position:absolute;inset:-12%;z-index:-1;pointer-events:none;background-repeat:repeat}',
    '.oly-l .oly-pn::before{opacity:.62;background-image:radial-gradient(circle,#fff 0 1px,transparent 1.4px),radial-gradient(circle,#a98cff 0 1.2px,transparent 1.7px),radial-gradient(circle,#6be7ff 0 .8px,transparent 1.3px);background-size:83px 79px,131px 127px,57px 61px;background-position:11px 17px,42px 9px,3px 33px;filter:drop-shadow(0 0 4px rgba(184,160,255,.7))}',
    '.oly-l .oly-pn::after{inset:0;opacity:.7;background:radial-gradient(ellipse at 18% 24%,rgba(91,51,190,.25),transparent 28%),radial-gradient(ellipse at 82% 46%,rgba(34,190,230,.16),transparent 32%),linear-gradient(140deg,transparent 20%,rgba(169,128,255,.07) 48%,transparent 72%)}',
    '.oly-l:not(.calm) .oly-pn::before{animation:olyStars 18s linear infinite}.oly-l:not(.calm) .oly-pn::after{animation:olyNebula 9s ease-in-out infinite alternate}@keyframes olyStars{to{transform:translate3d(-34px,28px,0)}}@keyframes olyNebula{to{opacity:.9;transform:scale(1.05) translate3d(1.5%,-1%,0)}}',
    '.oly-l .oly-hd,.oly-l .oly-sc{position:relative;z-index:1}',
    '.oly-l.pc{align-items:center}.oly-l.pc .oly-pn{border-radius:22px;border-bottom:1px solid rgba(168,85,247,.38);max-height:84vh;max-width:760px}',
    '.oly-l:not(.calm) .oly-pn{animation:olyUp .34s cubic-bezier(.2,.8,.2,1)}.oly-l:not(.calm) .oly-bd{animation:olyFade .25s ease}',
    '@keyframes olyUp{from{transform:translateY(40px);opacity:0}to{transform:none;opacity:1}}@keyframes olyFade{from{opacity:0}to{opacity:1}}',
    '.oly-l .oly-hd{display:flex;align-items:center;gap:10px;padding:14px 16px 8px;padding-top:calc(14px)}.oly-l .oly-hd h2{flex:1;margin:0;font:800 15px/1 var(--display,Oxanium,Inter,sans-serif);letter-spacing:.3em;color:#c9a8ff;text-shadow:0 0 18px rgba(168,85,247,.55)}',
    '.oly-l .oly-x{width:44px;height:44px;border-radius:50%;border:1px solid rgba(255,255,255,.14);background:rgba(255,255,255,.06);color:#eef1f8;font-size:22px;line-height:1;cursor:pointer}',
    '.oly-l .oly-sc{overflow-y:auto;-webkit-overflow-scrolling:touch;overscroll-behavior:contain;padding:4px 14px calc(18px + env(safe-area-inset-bottom,0px))}',
    '.oly-l .oly-jv{position:relative;display:flex;align-items:center;gap:14px;width:100%;min-height:64px;padding:12px 16px;border-radius:18px;text-decoration:none;color:#fff;overflow:hidden;isolation:isolate;',
    'background:linear-gradient(120deg,rgba(124,58,237,.55),rgba(56,189,248,.28));border:1px solid rgba(190,150,255,.55);box-shadow:0 0 30px rgba(168,85,247,.35)}',
    '.oly-l .oly-jv::before{content:"";position:absolute;left:-40%;top:-120%;width:80%;height:340%;background:linear-gradient(90deg,transparent,rgba(255,255,255,.22),transparent);transform:rotate(18deg);z-index:-1}',
    '.oly-l:not(.calm) .oly-jv::before{animation:olySweep 4.5s ease-in-out infinite}@keyframes olySweep{0%,60%{left:-60%}100%{left:130%}}',
    '.oly-l .oly-jv .oly-o{flex:none;display:grid;place-items:center;width:42px;height:42px;border-radius:50%;border:1.5px solid rgba(255,255,255,.7);font:800 20px/1 var(--display,Oxanium,sans-serif);box-shadow:0 0 18px rgba(255,255,255,.35),inset 0 0 12px rgba(255,255,255,.18)}',
    '.oly-l .oly-jv b{display:block;font:700 16px/1.2 var(--font,Inter,sans-serif)}.oly-l .oly-jv small{display:block;margin-top:2px;font-size:12px;color:rgba(255,255,255,.78)}.oly-l .oly-jv .oly-go{margin-left:auto;font-size:22px;opacity:.85}',
    '.oly-l .oly-sr{position:relative;margin:12px 0 4px}.oly-l .oly-sr input{width:100%;height:46px;border-radius:14px;border:1px solid rgba(255,255,255,.14);background:rgba(0,0,0,.32);color:#eef1f8;padding:0 14px;font:500 16px var(--font,Inter,sans-serif);outline:0}',
    '.oly-l .oly-sr input:focus{border-color:rgba(168,85,247,.8);box-shadow:0 0 0 3px rgba(168,85,247,.22)}',
    '.oly-l h3{margin:16px 2px 8px;font:700 11px/1 var(--font,Inter,sans-serif);letter-spacing:.2em;text-transform:uppercase;color:#9aa3bd}',
    '.oly-l .oly-rc{display:flex;gap:8px;overflow-x:auto;padding:2px 0 4px;scrollbar-width:none}.oly-l .oly-rc::-webkit-scrollbar{display:none}',
    '.oly-l .oly-chip{flex:none;display:inline-flex;align-items:center;gap:8px;min-height:44px;padding:0 14px 0 8px;border-radius:999px;border:1px solid rgba(255,255,255,.14);background:rgba(255,255,255,.05);color:#eef1f8;text-decoration:none;font:600 13px var(--font,Inter,sans-serif)}',
    '.oly-l .oly-chip i,.oly-l .oly-tile .oly-g{display:grid;place-items:center;font-style:normal;border-radius:50%;color:var(--c);background:rgba(var(--cr),.14);border:1.5px solid var(--c);box-shadow:0 0 12px rgba(var(--cr),.4)}',
    '.oly-l .oly-chip i{width:28px;height:28px;font:700 14px/1 var(--display,Oxanium,sans-serif)}',
    '.oly-l .oly-gr{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px}.oly-l.pc .oly-gr{grid-template-columns:repeat(3,minmax(0,1fr))}',
    '.oly-l .oly-tile{position:relative;display:flex;align-items:center;gap:11px;min-height:64px;padding:10px 12px;border-radius:16px;text-decoration:none;color:#eef1f8;min-width:0;',
    'background:linear-gradient(160deg,rgba(var(--cr),.13),rgba(255,255,255,.035));border:1px solid rgba(var(--cr),.34);transition:transform .16s,box-shadow .2s,border-color .2s}',
    '.oly-l .oly-tile:hover,.oly-l .oly-tile:focus-visible{border-color:var(--c);box-shadow:0 0 22px rgba(var(--cr),.35);transform:translateY(-1px);outline:0}.oly-l .oly-tile:active{transform:scale(.98)}',
    '.oly-l:not(.calm) .oly-tile{animation:olyUp .4s cubic-bezier(.2,.8,.2,1) both;animation-delay:calc(var(--i,0)*18ms)}',
    '.oly-l .oly-tile .oly-g{position:relative;flex:none;width:40px;height:40px;font:700 18px/1 var(--display,Oxanium,sans-serif);transform-origin:50% 50%;will-change:transform,filter}',
    '.oly-l .oly-tile .oly-g::after,.oly-l .oly-chip i::after{content:"";position:absolute;inset:-5px;border:1px solid rgba(var(--cr),.28);border-radius:inherit;opacity:.55}',
    '.oly-l:not(.calm) [data-motion="scan"] .oly-g,.oly-l:not(.calm) [data-motion="blink"] .oly-g,.oly-l:not(.calm) [data-motion="owl"] .oly-g,.oly-l:not(.calm) [data-motion="lens"] .oly-g{animation:olyGlyphScan 2.8s ease-in-out infinite var(--phase)}',
    '.oly-l:not(.calm) [data-motion="curtain"] .oly-g,.oly-l:not(.calm) [data-motion="banner"] .oly-g,.oly-l:not(.calm) [data-motion="wing"] .oly-g{animation:olyGlyphSway 3.4s ease-in-out infinite alternate var(--phase)}',
    '.oly-l:not(.calm) [data-motion="thread"] .oly-g,.oly-l:not(.calm) [data-motion="flow"] .oly-g,.oly-l:not(.calm) [data-motion="ripple"] .oly-g,.oly-l:not(.calm) [data-motion="neuron"] .oly-g{animation:olyGlyphPulse 2.7s ease-in-out infinite var(--phase)}',
    '.oly-l:not(.calm) [data-motion="rise"] .oly-g,.oly-l:not(.calm) [data-motion="flame"] .oly-g,.oly-l:not(.calm) [data-motion="forge"] .oly-g,.oly-l:not(.calm) [data-motion="treasure"] .oly-g{animation:olyGlyphRise 3.1s ease-in-out infinite var(--phase)}',
    '.oly-l:not(.calm) [data-motion="leaf"] .oly-g,.oly-l:not(.calm) [data-motion="flight"] .oly-g,.oly-l:not(.calm) [data-motion="laurel"] .oly-g{animation:olyGlyphFloat 3.8s ease-in-out infinite alternate var(--phase)}',
    '.oly-l:not(.calm) [data-motion="lightning"] .oly-g,.oly-l:not(.calm) [data-motion="shield"] .oly-g,.oly-l:not(.calm) [data-motion="market"] .oly-g{animation:olyGlyphCharge 3s ease-in-out infinite var(--phase)}',
    '.oly-l:not(.calm) [data-motion="scale"] .oly-g,.oly-l:not(.calm) [data-motion="tick"] .oly-g,.oly-l:not(.calm) [data-motion="coin"] .oly-g,.oly-l:not(.calm) [data-motion="control"] .oly-g{animation:olyGlyphTurn 5.2s ease-in-out infinite var(--phase)}',
    '.oly-l:not(.calm) [data-motion="maze"] .oly-g,.oly-l:not(.calm) [data-motion="vault"] .oly-g,.oly-l:not(.calm) [data-motion="letter"] .oly-g,.oly-l:not(.calm) [data-motion="portal"] .oly-g,.oly-l:not(.calm) [data-motion="calendar"] .oly-g,.oly-l:not(.calm) [data-motion="cartography"] .oly-g{animation:olyGlyphGate 3.6s ease-in-out infinite var(--phase)}',
    '@keyframes olyGlyphScan{0%,100%{filter:drop-shadow(0 0 4px var(--c));transform:scale(.96)}50%{filter:drop-shadow(0 0 13px var(--c));transform:scale(1.08)}}@keyframes olyGlyphSway{to{transform:perspective(70px) rotateY(14deg) rotate(-3deg)}}@keyframes olyGlyphPulse{50%{transform:scale(1.1);box-shadow:0 0 22px rgba(var(--cr),.62)}}@keyframes olyGlyphRise{0%,100%{transform:translateY(2px)}50%{transform:translateY(-3px) scale(1.06);filter:drop-shadow(0 4px 9px var(--c))}}',
    '@keyframes olyGlyphFloat{to{transform:translate3d(2px,-3px,0) rotate(4deg)}}@keyframes olyGlyphCharge{0%,72%,100%{filter:drop-shadow(0 0 3px var(--c))}76%{filter:drop-shadow(0 0 15px #fff);transform:scale(1.1)}80%{transform:scale(.96)}}@keyframes olyGlyphTurn{50%{transform:rotate(12deg) scale(1.05)}}@keyframes olyGlyphGate{50%{transform:perspective(80px) rotateY(-16deg) scale(1.04);box-shadow:0 0 18px rgba(var(--cr),.55)}}',
    '.oly-l .oly-tile .oly-tx{min-width:0;display:flex;flex-direction:column;gap:2px}.oly-l .oly-tile b{font:700 14px/1.15 var(--font,Inter,sans-serif);overflow-wrap:anywhere}',
    '.oly-l .oly-tile small{font-size:11.5px;line-height:1.25;color:#a9b1c3;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}',
    '.oly-dot{position:absolute;top:9px;right:9px;width:9px;height:9px;border-radius:50%;background:transparent;border:1px solid rgba(255,255,255,.25)}',
    '.oly-dot.ok{background:#2ee59d;border-color:#2ee59d;box-shadow:0 0 8px #2ee59d}.oly-dot.warn{background:#f7b955;border-color:#f7b955;box-shadow:0 0 8px #f7b955}.oly-dot.bad{background:#ff5a7a;border-color:#ff5a7a;box-shadow:0 0 8px #ff5a7a}',
    '.oly-dot.stale,.oly-dot.off{background:#6f788b;border-color:#6f788b}.oly-dot.none{display:none}',
    '.oly-l .oly-em{margin:18px 4px;text-align:center;color:#a9b1c3;font-size:14px}.oly-l .oly-ft{margin:14px 2px 0;font-size:11.5px;color:#6f788b;text-align:center}',
    '@media(prefers-reduced-motion:reduce){.oly-l *{animation:none!important;transition:none!important}}'
  ].join('');

  function build() {
    if (st.built) return;
    st.built = true;
    var style = el('style'); style.textContent = CSS; (d.head || root).appendChild(style);
    var o = el('div', 'oly-l' + (isPC ? ' pc' : '')); o.hidden = true; o.setAttribute('role', 'dialog'); o.setAttribute('aria-modal', 'true'); o.setAttribute('aria-label', 'OLYMPUS apps');
    var bd = el('div', 'oly-bd'); bd.addEventListener('click', close);
    var pn = el('div', 'oly-pn');
    var hd = el('div', 'oly-hd'); hd.appendChild(el('h2', '', 'OLYMPUS'));
    var x = el('button', 'oly-x', '×'); x.type = 'button'; x.setAttribute('aria-label', 'Close the app launcher'); x.addEventListener('click', close);
    hd.appendChild(x);
    var sc = el('div', 'oly-sc');
    var jv = el('a', 'oly-jv'); jv.href = url('jarvis/'); jv.setAttribute('data-app', 'jarvis'); if (isPC) { jv.target = '_blank'; jv.rel = 'noopener'; }
    var jo = el('span', 'oly-o', 'Ο'); jo.setAttribute('aria-hidden', 'true');
    var jt = el('span'); jt.appendChild(el('b', '', 'Open Olympus (Jarvis)')); jt.appendChild(el('small', '', 'Talk to Jarvis, switch apps, see everything at once'));
    jv.appendChild(jo); jv.appendChild(jt); jv.appendChild(el('span', 'oly-go', '›'));
    jv.addEventListener('click', function () { close(); });
    var sr = el('div', 'oly-sr'), inp = el('input'); inp.type = 'search'; inp.placeholder = 'Search apps'; inp.setAttribute('aria-label', 'Search apps'); inp.autocomplete = 'off'; inp.setAttribute('autocapitalize', 'off'); inp.spellcheck = false; inp.enterKeyHint = 'go';
    inp.addEventListener('input', function () { st.q = inp.value; filter(); });
    inp.addEventListener('keydown', function (e) { if (e.key === 'Enter') { var t = sc.querySelector('.oly-tile:not([hidden])'); if (t) t.click(); } });
    sr.appendChild(inp);
    var rcH = el('h3', '', 'Recent'), rc = el('div', 'oly-rc');
    var body = el('div', 'oly-bodyg'), em = el('p', 'oly-em', ''); em.hidden = true;
    var ft = el('p', 'oly-ft', isPC ? 'Apps open on the public site, in a new tab.' : 'Apps open on this site. Dots: green = running well, amber = look, red = a problem, grey = not updated.');
    sc.appendChild(jv); sc.appendChild(sr); sc.appendChild(rcH); sc.appendChild(rc); sc.appendChild(body); sc.appendChild(em); sc.appendChild(ft);
    pn.appendChild(hd); pn.appendChild(sc); o.appendChild(bd); o.appendChild(pn); d.body.appendChild(o);
    els = { o: o, pn: pn, x: x, inp: inp, rc: rc, rcH: rcH, body: body, em: em, sc: sc, jv: jv };
    o.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') { e.stopPropagation(); close(); return; }
      if (e.key !== 'Tab') return;
      var f = o.querySelectorAll('a[href],button,input'), vis = [].filter.call(f, function (n) { return !n.closest('[hidden]') && n.offsetParent !== null; });
      if (!vis.length) return;
      var first = vis[0], last = vis[vis.length - 1];
      if (e.shiftKey && d.activeElement === first) { e.preventDefault(); last.focus(); } else if (!e.shiftKey && d.activeElement === last) { e.preventDefault(); first.focus(); }
    });
  }

  function tile(a, i, chip) {
    var t = el('a', chip ? 'oly-chip' : 'oly-tile'); t.href = url(a.path); t.setAttribute('data-app', a.id);
    t.style.setProperty('--c', a.colour); t.style.setProperty('--cr', rgb(a.colour)); t.style.setProperty('--i', String(i)); t.style.setProperty('--phase', (-((i * 37) % 29) / 10) + 's');
    t.setAttribute('data-motion', GLYPH_MOTION[a.id] || 'portal');
    if (isPC) { t.target = '_blank'; t.rel = 'noopener'; }
    var g = el(chip ? 'i' : 'span', chip ? '' : 'oly-g', a.glyph); g.setAttribute('aria-hidden', 'true');
    if (chip) { t.appendChild(g); t.appendChild(d.createTextNode(a.name)); }
    else {
      var tx = el('span', 'oly-tx'); tx.appendChild(el('b', '', a.name)); tx.appendChild(el('small', '', a.purpose));
      t.appendChild(g); t.appendChild(tx);
      var dot = el('i', 'oly-dot none'); t.appendChild(dot);
      t.setAttribute('data-q', (a.name + ' ' + a.purpose + ' ' + a.groupName + ' ' + a.id).toLowerCase());
    }
    t.addEventListener('click', function () { touch(a.id); if (isPC) setTimeout(renderRecent, 0); else close(); });
    return t;
  }
  function renderRecent() {
    var ids = recent(), byId = {}; st.apps.forEach(function (a) { byId[a.id] = a; });
    var list = ids.map(function (id) { return byId[id]; }).filter(Boolean);
    els.rc.replaceChildren.apply(els.rc, list.map(function (a, i) { return tile(a, i, true); }));
    els.rc.hidden = els.rcH.hidden = !list.length || !!st.q;
  }
  function render() {
    st.apps = apps(); st.tiles = {};
    var frag = [], n = 0;
    GROUPS.forEach(function (g) {
      var list = st.apps.filter(function (a) { return a.group === g[0]; });
      if (!list.length) return;
      var sec = el('section'); sec.setAttribute('data-group', g[0]); sec.appendChild(el('h3', '', g[1]));
      var gr = el('div', 'oly-gr');
      list.forEach(function (a) { var t = tile(a, n++, false); st.tiles[a.id] = t; gr.appendChild(t); });
      sec.appendChild(gr); frag.push(sec);
    });
    els.body.replaceChildren.apply(els.body, frag);
    if (!st.apps.length) { els.em.hidden = false; els.em.textContent = listState === 'loading' ? 'Loading the apps...' : 'The app list could not load. Open Olympus (Jarvis) above and pick an app there.'; }
    else els.em.hidden = true;
    renderRecent(); filter();
  }
  function filter() {
    var q = st.q.trim().toLowerCase(), shown = 0;
    st.apps.forEach(function (a) { var t = st.tiles[a.id]; var ok = !q || t.getAttribute('data-q').indexOf(q) >= 0; t.hidden = !ok; if (ok) shown++; });
    els.body.querySelectorAll('section').forEach(function (s) { s.hidden = !s.querySelector('.oly-tile:not([hidden])'); });
    if (st.apps.length) { els.em.hidden = shown > 0; if (!shown) els.em.textContent = 'No app matches "' + st.q.trim().slice(0, 40) + '".'; }
    renderRecent();
  }

  function open() {
    if (st.open) return;
    build(); st.open = true; lastFocus = d.activeElement;
    els.o.classList.toggle('calm', calm());
    render();
    els.o.hidden = false;
    if (!window.OLYMPUS_APPS_LIST) loadList(function () { if (st.open) { render(); loadStatus(); } });
    root.style.overflow = 'hidden';
    try { if (window.ZenithFX && ZenithFX.glass && !calm()) ZenithFX.glass(els.pn, '.oly-tile', { deg: 4 }); } catch (e) { /* the plain tiles */ }
    setTimeout(function () { try { els.x.focus(); } catch (e) { /* */ } }, 30);
    loadStatus();
  }
  function close() {
    if (!st.open) return;
    st.open = false; els.o.hidden = true; root.style.overflow = '';
    try { if (lastFocus && lastFocus.focus) lastFocus.focus(); } catch (e) { /* */ }
  }

  // ---------------------------------------------------------------- the top-bar button
  var ICON = '<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><circle cx="5" cy="5" r="2"/><circle cx="12" cy="5" r="2"/><circle cx="19" cy="5" r="2"/><circle cx="5" cy="12" r="2"/><circle cx="12" cy="12" r="2"/><circle cx="19" cy="12" r="2"/><circle cx="5" cy="19" r="2"/><circle cx="12" cy="19" r="2"/><circle cx="19" cy="19" r="2"/></svg>';
  function mount() {
    if (d.getElementById('olyLauncherBtn') || !d.body) return;
    isPC = location.port === '8766' || !!d.querySelector('header.nx-top, .tb-right'); base = isPC ? PUBLIC : '';
    build();                                                   // the style first: the button needs it
    var b = el('button', 'oly-lbtn'); b.type = 'button'; b.id = 'olyLauncherBtn';
    b.setAttribute('aria-haspopup', 'dialog'); b.setAttribute('aria-label', 'Open the OLYMPUS app launcher'); b.title = 'OLYMPUS apps';
    b.innerHTML = ICON; b.appendChild(el('span', 't', 'OLYMPUS'));
    b.addEventListener('click', open);
    var host = d.querySelector('header.top') || d.querySelector('.tb-right');
    if (host) {
      var anchor = isPC ? d.getElementById('soundBtn') || host.firstChild : d.getElementById('refresh');
      if (anchor && anchor.parentNode === host) host.insertBefore(b, anchor); else host.appendChild(b);
    } else { b.className += ' float'; d.body.appendChild(b); }
  }
  setTimeout(function () { loadList(); }, 4000);                 // warm the list after the page is up (async: it never blocks the page)
  window.OLYMPUS_LAUNCHER = { open: open, close: close, isOpen: function () { return st.open; },
    state: function () { return { open: st.open, pc: isPC, apps: st.apps.length || apps().length, tiles: Object.keys(st.tiles).length, q: st.q, recent: recent(), status: JSON.parse(JSON.stringify(st.status)), base: base }; } };
  if (d.readyState === 'loading') d.addEventListener('DOMContentLoaded', mount); else mount();
}());
