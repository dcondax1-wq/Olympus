// Liquidity Engine service worker: makes the dashboard installable and keeps the app shell available offline.
// API calls are never cached (they are live state). Static files are network-first with a cache fallback.
// v28 (2026-10-30 night 3): Home's status bar + the Sunday open card (js/next/polish.js + statuscore.js), the sidebar in plain
// sections (Bots · Live · Money · Insight), Today · Brain · Trades · Results · Rules on every bot page, css/polish.css (motion).
const SHELL = 'le-shell-next-v32';  // was   // v32 (2026-11-03 day): js/next/zenithcore.js (shared with the phone: glass cards with an edge light + a small tilt, jfx quality, Olympus themes through one token function; skins.js writes its accent through it); // v31 (2026-11-03): the Scorecard (js/next/pro.js + procore.js, sidebar Insight: Zenith score, expectancy $, eval pace, underwater vs the MFFU floor, playbook, what-if sizing, $ by tag); // v27 (2026-10-29 night): the BLITZ page after ATLAS in the sidebar (js/next/blitz.js + blitzcore.js: Today · Brain · Trades · Results · Rules · Go live), the Mind page + cards (mindcore.js, GET /api/next/mind), Trader's deck (deckcore.js: risk meter, next 24 h, eval odds, real P&L calendar, journal, notification center, since you last looked, Holodeck replays), Holodeck day links (js/next/holo.js), GET /api/next/blitz (server.py); v26 (2026-10-29): the Holodeck page (js/next/holo.js + holocore.js, css/holo.css, js/fx.js holo.js: the day in 3D, every fill exact, what every bot is thinking, replay; GET /api/next/holo, /api/next/holo/days), the 3D button on Live View; v25 (2026-10-29): deep space (css/space.css: the static CSS sky + glass; js/fx.js space.js: Earth, the eclipse, the Sun, stars, the bots' satellites, shooting stars; 3D on by default), Mission Control (js/next/mission.js + missioncore.js, css/mission.css), Live View structure layer (liveviewchart.js, liveview.css); v24 (2026-10-28 PM): the 3D / glass look on Home "Today · real accounts", Real results and AI Insights (realcore.js v2, real.js, depth.js, insight.js, insight.css?v=2); v23 (2026-10-28): Home "Today · real accounts" cards + Safety card, the Real results page (realcore.js, real.js, cc.js, routes.js), REAL next to every paper figure (boardcore.js v2, tradepics.js v2), engine/live_board.py "real"; v22 (2026-10-27): the Run / Stop switch at the top of every page (runswitch.js, start.css, app.js, botctl.js, start.js, cc.js); v21 (2026-10-26 PM): one "Start trading" button + Start page first when the bot is stopped (start.js, start.css, app.js); v20 (2026-10-26): Start & Accounts page (start.js, start.css); v19 (2026-10-25 PM): Goals page "Funded & payouts" cards (cc.js, engine/funded_life.py); v18 (2026-10-25 PM): "Zlarior" (the LIT bot's display name): sidebar Home · Zlarior · ATLAS · Results · All tools, bot pages with sections (routes.js BOTS); v17 (2026-10-25 PM): K3 icon + clean-up pass: six-item sidebar + Advanced, lean top bar with a ⋯ menu, calm Home, clean.css, 3D off by default; v15 (2026-10-25): Command center, grouped sidebar, cc.js / cc.css; v14 (2026-10-23): trade pictures (tradepics.js, pics.js); v13: ATLAS page + Today two-strategy cards and the Scaling plan; v12: scale / ATLAS; v11: Second strategies; v10: Bot Brain
const ASSETS = ['/', '/index.html', '/css/app.css', '/css/theme.css', '/css/skins.css', '/css/dash.css', '/css/next.css', '/css/hub.css', '/css/ops.css', '/css/cc.css', '/css/clean.css', '/css/start.css', '/manifest.webmanifest', '/icons/icon.svg?v=p111030'];
ASSETS.push('/css/insight.css?v=2');   // AI Insights page (js/next/insight.js; v2 = the 3D / glass look)
ASSETS.push('/css/liveview.css');   // Live View page (js/next/liveview.js)
ASSETS.push('/css/space.css?v=1', '/css/mission.css?v=1');   // deep space + Mission Control (2026-10-29)
ASSETS.push('/css/holo.css');   // the Holodeck (js/next/holo.js, 2026-10-29)
ASSETS.push('/css/polish.css?v=1');
ASSETS.push('/js/next/zenithcore.js?v=1');   // 2026-11-03 day: the shared Zenith look core (byte-identical to tools/web_public/zenithcore.js)   // night 3: status bar, motion (js/next/polish.js, 2026-10-30)

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(SHELL).then((c) => c.addAll(ASSETS)).catch(() => null));
  self.skipWaiting();
});
self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== SHELL).map((k) => caches.delete(k)))));
  self.clients.claim();
});
self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET' || url.pathname.startsWith('/api/')) return;
  if (url.origin !== location.origin) return;
  e.respondWith(
    fetch(e.request).then((res) => {
      if (res.ok) { const copy = res.clone(); caches.open(SHELL).then((c) => c.put(e.request, copy)); }
      return res;
    }).catch(() => caches.match(e.request).then((hit) => hit || (url.pathname === '/' ? caches.match('/index.html') : undefined)))
  );
});
