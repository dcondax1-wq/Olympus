// Home Screen app service worker: works offline with the last data it saw.
// Page + data.json + home.json: network-first (fresh when online, cached copy offline). Versioned files (?v=...): cache-first, and a
// new version of a file (fx.js?v=<hash> after a rebuild, runs/<id>.json?v=<hash> and writeups/<slug>.md?v=<hash> after a
// new backtest or write-up) drops the old one from the cache, so a run or write-up opened once stays readable offline.
// Everything else: cached copy at once, refreshed in the background.
// Phone notifications (Web Push from the cloud monitor and the PC bot, engine/push.py): every push shows a notification and
// counts on the app badge; a tap opens the app at the notice (#/activity/<key>).
const CACHE = 'le-public-v12';
const BADGE = 'le-badge', BADGE_URL = './__badge';
const SHELL = ['./', './index.html', './manifest.webmanifest', './icons/icon-192.png?v=drop1', './icons/apple-touch-icon.png?v=drop1', './icons/icon-512.png?v=drop1'];
self.addEventListener('install', (e) => { e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).catch(() => null)); self.skipWaiting(); });
self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== CACHE && k !== BADGE).map((k) => caches.delete(k)))));
  self.clients.claim();
});
const prune = (u) => caches.open(CACHE).then((c) => c.keys().then((ks) => ks.forEach((k) => {
  const ku = new URL(k.url); if (ku.pathname === u.pathname && ku.search !== u.search) c.delete(k);
}))).catch(() => null);
self.addEventListener('fetch', (e) => {
  const req = e.request, url = new URL(req.url);
  if (req.method !== 'GET' || url.origin !== location.origin) return;
  const put = (key, res) => { if (res && res.ok) { const c = res.clone(); caches.open(CACHE).then((x) => x.put(key, c)); } return res; };
  const isData = url.pathname.endsWith('data.json') || url.pathname.endsWith('home.json'), isPage = req.mode === 'navigate' || url.pathname.endsWith('/') || url.pathname.endsWith('index.html');
  if (isData || isPage) {
    const key = isData ? (url.pathname.endsWith('home.json') ? './home.json' : './data.json') : './index.html';
    e.respondWith(fetch(req).then((r) => put(key, r)).catch(() => caches.match(key)));
    return;
  }
  if (url.search.includes('v=')) { e.respondWith(caches.match(req).then((hit) => hit || fetch(req).then((r) => { prune(url); return put(req, r); }))); return; }
  e.respondWith(caches.match(req).then((hit) => { const net = fetch(req).then((r) => put(req, r)).catch(() => hit); return hit || net; }));
});

// ---- notifications
const badgeGet = () => caches.open(BADGE).then((c) => c.match(BADGE_URL)).then((r) => (r ? r.text() : '0')).then((t) => +t || 0).catch(() => 0);
const badgeSet = (n) => caches.open(BADGE).then((c) => c.put(BADGE_URL, new Response(String(n)))).catch(() => null);
const safeHash = (u) => (typeof u === 'string' && /^#\/[\w\-/:.%]*$/.test(u) ? u : '#/activity');
self.addEventListener('push', (e) => {
  let d = {};
  try { d = e.data ? e.data.json() : {}; } catch (_) { d = { body: e.data ? e.data.text() : '' }; }
  const title = String(d.title || 'Liquidity Engine').slice(0, 120);
  const opts = { body: String(d.body || '').slice(0, 600), icon: 'icons/icon-192.png?v=drop1', badge: 'icons/icon-192.png?v=drop1',
    data: { url: safeHash(d.url), key: d.key || null, t: d.t || null }, timestamp: d.t ? d.t * 1000 : Date.now() };
  if (d.tag) { opts.tag = String(d.tag); opts.renotify = true; }
  if (d.require) { opts.requireInteraction = true; opts.vibrate = [400, 150, 400, 150, 400]; }   // the Surface-offline alert stays until tapped
  e.waitUntil(Promise.all([
    self.registration.showNotification(title, opts),
    badgeGet().then((n) => badgeSet(n + 1).then(() => (self.navigator && self.navigator.setAppBadge ? self.navigator.setAppBadge(n + 1) : null))).catch(() => null),
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((cs) => cs.forEach((c) => c.postMessage({ type: 'push', d }))).catch(() => null),
  ]));
});
self.addEventListener('notificationclick', (e) => {
  e.notification.close();
  const hash = safeHash(e.notification.data && e.notification.data.url);
  const url = new URL('./' + hash, self.registration.scope).href;
  e.waitUntil(self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((cs) => {
    const c = cs.find((x) => x.url.startsWith(self.registration.scope));
    if (c) { c.postMessage({ type: 'open', hash }); return c.focus ? c.focus() : null; }
    return self.clients.openWindow(url);
  }));
});
// the push service replaced this phone's subscription: subscribe again with the same key (the app then shows the new code)
self.addEventListener('pushsubscriptionchange', (e) => {
  const key = e.oldSubscription && e.oldSubscription.options && e.oldSubscription.options.applicationServerKey;
  if (!key) return;
  e.waitUntil(self.registration.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: key }).catch(() => null));
});
