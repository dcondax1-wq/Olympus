// Home Screen app service worker: the page works offline with the last data it saw.
// data.json is network-first (always fresh when online); the shell is cache-first and refreshed in the background.
const CACHE = 'le-public-v2';
const SHELL = ['./', './index.html', './manifest.webmanifest', './icons/icon-192.png?v=orb1', './icons/apple-touch-icon.png?v=orb1'];
self.addEventListener('install', (e) => { e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).catch(() => null)); self.skipWaiting(); });
self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k)))));
  self.clients.claim();
});
self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET' || url.origin !== location.origin) return;
  const fresh = fetch(e.request).then((r) => { if (r.ok) { const c = r.clone(); caches.open(CACHE).then((x) => x.put(url.pathname.endsWith('data.json') ? './data.json' : e.request, c)); } return r; });
  if (url.pathname.endsWith('data.json')) { e.respondWith(fresh.catch(() => caches.match('./data.json'))); return; }
  e.respondWith(caches.match(e.request).then((hit) => { fresh.catch(() => null); return hit || fresh; }).catch(() => caches.match('./index.html')));
});
