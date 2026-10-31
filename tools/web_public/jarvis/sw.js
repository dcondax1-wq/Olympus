// Jarvis hub service worker: keeps the hub's own screen available offline. Network first for the hub's files; it never
// touches the dashboards it shows (they live outside this folder and keep their own service workers) or the live feed.
// v2 (2026-10-31, Jarvis would not open): each file is saved on its own (one missing file cannot stop the rest), and the saved
// copy answers whenever the site does not answer properly (offline, a 404 or a server error), never an error page.
const CACHE = 'jarvis-v2';
const SHELL = ['./', './index.html', './manifest.webmanifest?v=j1', './apple-touch-icon.png?v=j1', './icon-192.png?v=j1', './icon-512.png?v=j1'];
self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => Promise.all(SHELL.map((u) => c.add(u).catch(() => null)))));
  self.skipWaiting();
});
self.addEventListener('activate', (e) => {
  e.waitUntil((async () => {
    // Old copies go only once the new one holds the page.
    if (await (await caches.open(CACHE)).match('./index.html')) {
      for (const k of await caches.keys()) if (k.startsWith('jarvis-') && k !== CACHE) await caches.delete(k);
    }
    await self.clients.claim();
  })());
});
async function saved(req) {
  const hit = await caches.match(req, { ignoreSearch: true });
  if (hit || req.mode !== 'navigate') return hit;
  return (await caches.match('./index.html')) || (await caches.match('./'));    // './' is this folder: only Jarvis's own page
}
self.addEventListener('fetch', (e) => {
  const u = new URL(e.request.url);
  const scope = new URL(self.registration.scope);
  if (e.request.method !== 'GET' || u.origin !== scope.origin || !u.pathname.startsWith(scope.pathname)) return;
  e.respondWith((async () => {
    try {
      const r = await fetch(e.request);
      if (r && r.ok) { const c = r.clone(); caches.open(CACHE).then((x) => x.put(e.request, c)).catch(() => null); return r; }
      return (await saved(e.request)) || r;
    } catch (_) {
      return (await saved(e.request)) || Response.error();
    }
  })());
});
