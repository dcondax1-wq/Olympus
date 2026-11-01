// Jarvis hub service worker: keeps the hub's own screen available offline. Network first for the hub's files; it never
// touches the dashboards it shows (they live outside this folder and keep their own service workers) or the live feed.
// v2 (2026-10-31, Jarvis would not open): each file is saved on its own (one missing file cannot stop the rest), and the saved
// copy answers whenever the site does not answer properly (offline, a 404 or a server error), never an error page.
// v3 (2026-11-01, "Jarvis is just a white screen"): an iPhone Home Screen app shows a blank white screen while its page loads
// or when the load fails. So opening Jarvis never waits on a slow network for more than NAV_WAIT_MS when a saved copy exists
// (the network answer still refreshes the copy for next time), and with no network and no copy it gets a small dark page
// with a Retry button instead of an error.
const CACHE = 'jarvis-v3';
const NAV_WAIT_MS = 3500;
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
const OFFLINE = '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">'
  + '<meta name="theme-color" content="#0b0b0d"><title>Jarvis</title><style>html,body{height:100%;margin:0;background:#0b0b0d;color:#f4f4f6;'
  + 'font:16px/1.45 -apple-system,system-ui,sans-serif}main{min-height:100%;display:grid;place-items:center;text-align:center;padding:24px}'
  + 'p{color:#b3b4ba;margin:8px 0 18px}button{height:44px;padding:0 22px;border-radius:13px;border:0;background:#f4f4f6;color:#0b0b0d;font:inherit;font-weight:650}'
  + '</style></head><body><main><div><b>Jarvis can’t reach the internet</b><p>Check your connection, then try again.</p>'
  + '<button onclick="location.reload()">Retry</button></div></main></body></html>';
const offlinePage = () => new Response(OFFLINE, { status: 200, headers: { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store' } });
const store = (req, r) => { if (r && r.ok) { const c = r.clone(); caches.open(CACHE).then((x) => x.put(req, c)).catch(() => null); } return r; };
self.addEventListener('fetch', (e) => {
  const req = e.request, u = new URL(req.url);
  const scope = new URL(self.registration.scope);
  if (req.method !== 'GET' || u.origin !== scope.origin || !u.pathname.startsWith(scope.pathname)) return;
  if (req.mode === 'navigate') {
    e.respondWith((async () => {
      const net = fetch(req).then((r) => store(req, r));
      net.catch(() => null);
      e.waitUntil(net.catch(() => null));                         // a late answer still refreshes the saved copy
      const copy = await saved(req);
      const slow = new Promise((ok) => setTimeout(() => ok('slow'), copy ? NAV_WAIT_MS : 25000));
      try {
        const r = await Promise.race([net, slow]);
        if (r !== 'slow' && r && r.ok) return r;
        if (copy) return copy;
        if (r !== 'slow' && r) return r;                           // no copy yet: the site's own answer
        return await net;
      } catch (_) {
        return copy || offlinePage();
      }
    })().catch(() => offlinePage()));
    return;
  }
  e.respondWith((async () => {
    try {
      const r = await fetch(req);
      if (r && r.ok) return store(req, r);
      return (await saved(req)) || r;
    } catch (_) {
      return (await saved(req)) || Response.error();
    }
  })());
});
