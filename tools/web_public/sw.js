// Home Screen app service worker: works offline with the last data it saw.
// Page + data.json: network-first (fresh when online, cached copy offline). Versioned files (?v=...): cache-first, and a
// new version of a file (fx.js?v=<hash> after a rebuild) drops the old one from the cache.
// Everything else: cached copy at once, refreshed in the background.
const CACHE = 'le-public-v4';
const SHELL = ['./', './index.html', './manifest.webmanifest', './icons/icon-192.png?v=orb1', './icons/apple-touch-icon.png?v=orb1', './icons/icon-512.png?v=orb1'];
self.addEventListener('install', (e) => { e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).catch(() => null)); self.skipWaiting(); });
self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k)))));
  self.clients.claim();
});
const prune = (u) => caches.open(CACHE).then((c) => c.keys().then((ks) => ks.forEach((k) => {
  const ku = new URL(k.url); if (ku.pathname === u.pathname && ku.search !== u.search) c.delete(k);
}))).catch(() => null);
self.addEventListener('fetch', (e) => {
  const req = e.request, url = new URL(req.url);
  if (req.method !== 'GET' || url.origin !== location.origin) return;
  const put = (key, res) => { if (res && res.ok) { const c = res.clone(); caches.open(CACHE).then((x) => x.put(key, c)); } return res; };
  const isData = url.pathname.endsWith('data.json'), isPage = req.mode === 'navigate' || url.pathname.endsWith('/') || url.pathname.endsWith('index.html');
  if (isData || isPage) {
    const key = isData ? './data.json' : './index.html';
    e.respondWith(fetch(req).then((r) => put(key, r)).catch(() => caches.match(key)));
    return;
  }
  if (url.search.includes('v=')) { e.respondWith(caches.match(req).then((hit) => hit || fetch(req).then((r) => { prune(url); return put(req, r); }))); return; }
  e.respondWith(caches.match(req).then((hit) => { const net = fetch(req).then((r) => put(req, r)).catch(() => hit); return hit || net; }));
});
