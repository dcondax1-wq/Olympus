// Liquidity Engine service worker: makes the dashboard installable and keeps the app shell available offline.
// API calls are never cached (they are live state). Static files are network-first with a cache fallback.
const SHELL = 'le-shell-next-v16';   // v15 (2026-10-25): Command center, grouped sidebar, cc.js / cc.css; v14 (2026-10-23): trade pictures (tradepics.js, pics.js); v13: ATLAS page + Today two-strategy cards and the Scaling plan; v12: scale / ATLAS; v11: Second strategies; v10: Bot Brain
const ASSETS = ['/', '/index.html', '/css/app.css', '/css/theme.css', '/css/skins.css', '/css/dash.css', '/css/next.css', '/css/hub.css', '/css/ops.css', '/css/cc.css', '/manifest.webmanifest', '/icons/icon.svg?v=k31025'];

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
