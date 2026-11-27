// NQ app worker (night-nq-nav 2026-11-27, scope tools/web_public/nq/): the NQ pages open offline after one visit, never on a browser
// error page. The site worker (../sw.js) leaves nq/ alone ('own folders'), so this is the only worker here. Registered by nqnav.js.
// - pages (navigations): network first, at most NAV_WAIT_MS when a saved copy exists; a bad / failed answer = the saved copy; with no copy,
//   a small OLYMPUS NIGHT page "Offline" with a Retry button;
// - versioned files (?v=): the exact saved copy at once (a new version is a new URL), refreshed behind;
// - every other same-origin GET (json, unversioned js / css, images): network first, the saved copy when the network fails;
// - other sites (the PC status feed on ntfy.sh, fonts) are never touched: the pill reads them live or shows its saved number;
// - only 'nqnav-' caches are ever deleted; at most MAX_ITEMS entries are kept (oldest out).
const CACHE = 'nqnav-n1';
const NAV_WAIT_MS = 3500;
const MAX_ITEMS = 160;
const SHELL = ['./', './index.html', './live.html', './accounts.html', './brain.html', './nqnav.js?v=1', './nqnav.css?v=1', './manifest.webmanifest', './icon.svg', './icon-192.png'];

const OFFLINE = '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">' +
  '<meta name="theme-color" content="#000000"><title>NQ · offline</title><style>html,body{margin:0;height:100%;background:#000;color:#ece6f7;font:16px/1.5 system-ui,-apple-system,sans-serif}' +
  'main{min-height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:24px;box-sizing:border-box;text-align:center}' +
  '.c{max-width:340px;padding:26px 22px;border-radius:20px;background:#16131e;border:1px solid #4d2e76;box-shadow:0 0 30px rgba(157,89,238,.35)}' +
  'h1{margin:0 0 8px;font-size:22px;color:#f1c14b}p{margin:0 0 18px;color:#a99cc0}button{min-height:44px;padding:0 22px;border-radius:12px;border:1px solid #f1c14b;background:#f1c14b;color:#1a1208;font:600 15px system-ui,sans-serif}' +
  '</style></head><body><main><div class="c"><h1>Offline</h1><p>This NQ page is not saved on this phone yet and the network is down. The bots on the PC keep running; this is only the phone.</p>' +
  '<button onclick="location.reload()">Retry</button></div></main></body></html>';

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => Promise.all(SHELL.map((u) => c.add(u).catch(() => null)))).catch(() => null));
  self.skipWaiting();
});
self.addEventListener('activate', (e) => {
  e.waitUntil((async () => {
    for (const k of await caches.keys()) if (k.startsWith('nqnav-') && k !== CACHE) await caches.delete(k);
    await self.clients.claim();
  })());
});

async function put(req, res) {
  if (!res || !res.ok || res.type === 'opaque') return;
  try {
    const c = await caches.open(CACHE);
    await c.put(req, res);
    const keys = await c.keys();
    for (let i = 0; i < keys.length - MAX_ITEMS; i++) await c.delete(keys[i]);
  } catch (_) { /* full or private mode */ }
}
const late = (p, ms) => Promise.race([p, new Promise((r) => setTimeout(() => r(null), ms))]);

async function page(e) {
  const req = e.request, saved = await caches.match(req, { ignoreSearch: true });
  const net = fetch(req).then((r) => { if (r && r.ok) e.waitUntil(put(req, r.clone())); return r; }).catch(() => null);
  const r = saved ? await late(net, NAV_WAIT_MS) : await net;
  if (r && r.ok) return r;
  if (saved) return saved;
  if (r) return r;                                           // a real answer (a 404 stays a 404: never called "offline")
  return new Response(OFFLINE, { status: 200, headers: { 'Content-Type': 'text/html; charset=utf-8', 'Cache-Control': 'no-store' } });
}
async function versioned(e) {
  const req = e.request, saved = await caches.match(req);
  const net = fetch(req).then((r) => { if (r && r.ok) e.waitUntil(put(req, r.clone())); return r; }).catch(() => null);
  if (saved) { e.waitUntil(net); return saved; }
  return (await net) || new Response('', { status: 504 });
}
async function other(e) {
  const req = e.request;
  try {
    const r = await fetch(req);
    if (r && r.ok) e.waitUntil(put(req, r.clone()));
    if (r && r.ok) return r;
    return (await caches.match(req)) || r;
  } catch (_) {
    return (await caches.match(req)) || new Response('', { status: 504 });
  }
}

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return;
  let u; try { u = new URL(req.url); } catch (_) { return; }
  if (u.origin !== self.location.origin) return;          // ntfy.sh, fonts, anything else: the browser's own way
  if (req.mode === 'navigate') { e.respondWith(page(e)); return; }
  if (req.headers.get('range')) return;                    // media ranges: never cached
  if (/[?&]v=/.test(u.search)) { e.respondWith(versioned(e)); return; }
  e.respondWith(other(e));
});
