// Jarvis hub service worker: keeps the hub's own screen available offline. Network first for the hub's files; it never
// touches the dashboards it shows (they live outside this folder and keep their own service workers) or the live feed.
// v2 (2026-10-31, Jarvis would not open): each file is saved on its own (one missing file cannot stop the rest), and the saved
// copy answers whenever the site does not answer properly (offline, a 404 or a server error), never an error page.
// v3 (2026-11-01, "Jarvis is just a white screen"): an iPhone Home Screen app shows a blank white screen while its page loads
// or when the load fails. So opening Jarvis never waits on a slow network for more than NAV_WAIT_MS when a saved copy exists
// (the network answer still refreshes the copy for next time), and with no network and no copy it gets a small dark page
// with a Retry button instead of an error.
// v4 (2026-11-01, Jarvis + Zenith modes): the app is split into modules (data.js, jarvis.css and the parts built on their own:
// brain.js, core-visual.js, apps.js, zenith-mode.js, three.module.min.js). Each is saved on its own, so a part that is not on
// the site yet is skipped. The old Jarvis look came back with it: its fonts (Orbitron, Rajdhani; OFL.txt) are saved too.
// Only the navigation races the network (NAV_WAIT_MS): a page answered from the saved copy gets its own files from the saved
// copy at once (stale-while-revalidate: the network refreshes them for next time), so a slow network never stacks one wait per
// file (QA 2026-11-01: first paint 7 s instead of 3.6 s). A page fresh from the network gets fresh files (the same version),
// falling back to the saved copy after NAV_WAIT_MS. Fonts and images always come from the saved copy first.
const CACHE = 'jarvis-v4';
const NAV_WAIT_MS = 3500;
const SHELL = ['./', './index.html', './manifest.webmanifest?v=j2', './apple-touch-icon.png?v=j2', './icon-192.png?v=j2', './icon-512.png?v=j2',
  './jarvis.css?v=j4', './data.js', './brain.js', './core-visual.js', './apps.js', './zenith-mode.js',
  './three.module.min.js', './orbitron.woff2', './rajdhani-400.woff2', './rajdhani-500.woff2', './rajdhani-600.woff2', './rajdhani-700.woff2'];
const STATIC_RX = /\.(woff2|png|svg|jpg|webp|webmanifest)$/i;
// how each page was answered ('cache' | 'net'), by its client id; lastNav when the browser gives no client ids
const navFrom = new Map();
let lastNav = { from: 'net', at: 0 };
function markNav(e, from) {
  lastNav = { from, at: Date.now() };
  if (e.resultingClientId) { navFrom.set(e.resultingClientId, from); if (navFrom.size > 24) navFrom.delete(navFrom.keys().next().value); }
}
function pageFromCopy(e) {
  const f = e.clientId && navFrom.get(e.clientId);
  return f ? f === 'cache' : lastNav.from === 'cache' && Date.now() - lastNav.at < 30000;
}
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
// only Jarvis's own cache: any page of this origin can write CacheStorage, so an origin-wide lookup could be fed another
// page's copy (security review 2026-11-01)
async function saved(req) {
  const c = await caches.open(CACHE);
  const hit = await c.match(req, { ignoreSearch: true });
  if (hit || req.mode !== 'navigate') return hit;
  return (await c.match('./index.html')) || (await c.match('./'));    // './' is this folder: only Jarvis's own page
}
const OFFLINE = '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">'
  + '<meta name="theme-color" content="#000000"><title>Jarvis</title><style>html,body{height:100%;margin:0;background:#000;color:#ece9f2;'
  + 'font:16px/1.45 -apple-system,system-ui,sans-serif}main{min-height:100%;display:grid;place-items:center;text-align:center;padding:24px;'
  + 'background:radial-gradient(ellipse at 50% 40%,#140a24,#000 65%)}b{letter-spacing:.3em;color:#e9ddff;text-shadow:0 0 14px #a855f7}'
  + 'p{color:#8a8499;margin:10px 0 18px}button{height:44px;padding:0 22px;border-radius:14px;border:1px solid #a855f7;background:rgba(168,85,247,.25);color:#fff;'
  + 'font:inherit;font-weight:650;box-shadow:0 0 16px rgba(168,85,247,.45)}'
  + '</style></head><body><main><div><b>J.A.R.V.I.S.</b><p>Jarvis can’t reach the internet. Check your connection, then try again.</p>'
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
        if (r !== 'slow' && r && r.ok) { markNav(e, 'net'); return r; }
        if (copy) { markNav(e, 'cache'); return copy; }
        if (r !== 'slow' && r) return r;                           // no copy yet: the site's own answer
        return await net;
      } catch (_) {
        markNav(e, 'cache');
        return copy || offlinePage();
      }
    })().catch(() => offlinePage()));
    return;
  }
  e.respondWith((async () => {
    const net = fetch(req);
    net.then((r) => store(req, r)).catch(() => null);
    e.waitUntil(net.catch(() => null));                          // the saved copy is refreshed for next time
    const copy = await saved(req);
    // stale-while-revalidate: fonts and images, and every file of a page that came from the saved copy
    if (copy && (STATIC_RX.test(u.pathname) || pageFromCopy(e))) return copy;
    try {
      // a page fresh from the network: its files fresh too, the saved copy only if the network stalls
      const r = copy ? await Promise.race([net, new Promise((ok) => setTimeout(() => ok(null), NAV_WAIT_MS))]) : await net;
      if (r && r.ok) return r;
      return copy || (await saved(req)) || r || Response.error();
    } catch (_) {
      return (await saved(req)) || Response.error();
    }
  })());
});
