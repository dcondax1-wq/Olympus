// Load-time measurement for the Olympus phone site (day-site5 C2). Node Playwright + CDP, 390 x 844, cold cache each run.
// Throttle: "4G" = 150 ms latency, 1.6 Mbps down, 750 Kbps up (CDP Network.emulateNetworkConditions) + CPU 4x slower (Emulation.setCPUThrottlingRate).
// Serves tools/web_public with a tiny static server that gzips text like GitHub Pages does (GZIP=0 turns it off). Requests to any other host are aborted
// (ntfy / cdnjs / fonts: not ours to time, and the pages must work without them), so the numbers are the site's own weight.
// usage: [PUB=<web_public>] [GZIP=0] [REPEAT=1] node speed.cjs [runs=3] [path ...]     default paths: /gate/ /nq/   -> a table + JSON (medians) on stdout
const { chromium } = require('playwright');
const http = require('http'), fs = require('fs'), path = require('path'), zlib = require('zlib');
const PUB = path.resolve(process.env.PUB || path.join(__dirname, '../../../../tools/web_public'));   // PUB=<dir> measures another checkout (the 'before')
const RUNS = +(process.argv[2] || 3) || 3;
const PATHS = process.argv.slice(3).length ? process.argv.slice(3) : ['/gate/', '/nq/'];
const MIME = { '.js': 'application/javascript', '.mjs': 'application/javascript', '.html': 'text/html', '.css': 'text/css', '.json': 'application/json', '.png': 'image/png', '.jpg': 'image/jpeg',
  '.webp': 'image/webp', '.svg': 'image/svg+xml', '.woff2': 'font/woff2', '.webmanifest': 'application/manifest+json', '.glb': 'model/gltf-binary', '.mp3': 'audio/mpeg' };
const srv = http.createServer((q, r) => {
  let p = decodeURIComponent(q.url.split('?')[0].split('#')[0]); if (p.endsWith('/')) p += 'index.html';
  const f = path.join(PUB, p);
  if (!f.startsWith(PUB)) { r.writeHead(403); r.end(); return; }
  fs.readFile(f, (e, d) => {
    if (e) { r.writeHead(404); r.end(); return; }
    const type = MIME[path.extname(f)] || 'application/octet-stream', gz = process.env.GZIP !== '0' && /text|javascript|json|svg|manifest/.test(type) && /gzip/.test(q.headers['accept-encoding'] || '');
    r.writeHead(200, { 'content-type': type, 'cache-control': 'no-cache', ...(gz ? { 'content-encoding': 'gzip' } : {}) }); r.end(gz ? zlib.gzipSync(d, { level: 6 }) : d);
  });
});
const med = (xs) => { const s = xs.filter((x) => x != null).sort((a, b) => a - b); return s.length ? s[Math.floor((s.length - 1) / 2)] : null; };
srv.listen(0, async () => {
  const BASE = 'http://127.0.0.1:' + srv.address().port;
  const b = await chromium.launch();
  const out = {};
  for (const url of PATHS) {
    const runs = [];
    for (let i = 0; i < RUNS; i++) {
      const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 3, isMobile: true, hasTouch: true,
        userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1' });
      await ctx.route((u) => !u.href.startsWith(BASE) && !u.href.startsWith('data:') && !u.href.startsWith('blob:'), (r) => r.abort());
      if (process.env.REPEAT === '1') await ctx.addInitScript(() => {   // REPEAT=1: a second open the same New York day (the Home's intro plays once a day)
        try { localStorage.setItem('oly.homefx.day', new Intl.DateTimeFormat('en-CA', { timeZone: 'America/New_York' }).format(new Date())); } catch (_) { /* fine */ }
      });
      await ctx.addInitScript(() => {
        try { localStorage.setItem('oly.new.pillars', '1'); } catch (_) { /* fine */ }
        window.__lcp = null; window.__cls = 0;
        try { new PerformanceObserver((l) => { for (const e of l.getEntries()) window.__lcp = e.startTime; }).observe({ type: 'largest-contentful-paint', buffered: true }); } catch (_) { /* fine */ }
        try { new PerformanceObserver((l) => { for (const e of l.getEntries()) if (!e.hadRecentInput) window.__cls += e.value; }).observe({ type: 'layout-shift', buffered: true }); } catch (_) { /* fine */ }
      });
      const p = await ctx.newPage();
      const cdp = await ctx.newCDPSession(p);
      await cdp.send('Network.enable');
      await cdp.send('Network.emulateNetworkConditions', { offline: false, latency: 150, downloadThroughput: (1.6 * 1024 * 1024) / 8, uploadThroughput: (750 * 1024) / 8 });
      await cdp.send('Emulation.setCPUThrottlingRate', { rate: 4 });
      const req = new Map(); let bytesLoad = null;
      cdp.on('Network.responseReceived', (e) => { const r = req.get(e.requestId) || {}; r.type = e.type; r.url = e.response.url; req.set(e.requestId, r); });
      cdp.on('Network.loadingFinished', (e) => { const r = req.get(e.requestId) || {}; r.bytes = e.encodedDataLength; r.done = Date.now(); req.set(e.requestId, r); });
      const t0 = Date.now();
      await p.goto(BASE + url, { waitUntil: 'load', timeout: 120000 });
      const tLoadWall = Date.now() - t0;
      const sum = (f) => [...req.values()].filter(f).reduce((s, r) => s + (r.bytes || 0), 0);
      bytesLoad = { all: sum(() => true), n: [...req.values()].filter((r) => r.bytes != null).length };
      await p.waitForTimeout(6000);                                         // what keeps downloading after load (lazy 3D, polls): it still competes for the phone's bandwidth
      const m = await p.evaluate(() => {
        const n = performance.getEntriesByType('navigation')[0] || {}, fcp = performance.getEntriesByName('first-contentful-paint')[0];
        return { fcp: fcp ? fcp.startTime : null, lcp: window.__lcp, dcl: n.domContentLoadedEventEnd || null, load: n.loadEventEnd || null, cls: window.__cls };
      });
      const all = [...req.values()].filter((r) => r.bytes != null);
      runs.push({ ...m, loadWall: tLoadWall, kbLoad: bytesLoad.all / 1024, reqLoad: bytesLoad.n, kb6s: sum(() => true) / 1024, req6s: all.length,
        jsKb6s: sum((r) => r.type === 'Script') / 1024, imgKb6s: sum((r) => r.type === 'Image') / 1024,
        top: all.sort((a, c) => (c.bytes || 0) - (a.bytes || 0)).slice(0, 8).map((r) => `${Math.round(r.bytes / 1024)}KB ${String(r.url).replace(BASE, '')}`) });
      await ctx.close();
    }
    const k = (key) => med(runs.map((r) => r[key]));
    out[url] = { runs: RUNS, fcp: k('fcp'), lcp: k('lcp'), dcl: k('dcl'), load: k('load'), cls: k('cls'), kbLoad: k('kbLoad'), reqLoad: k('reqLoad'), kb6s: k('kb6s'), req6s: k('req6s'), jsKb6s: k('jsKb6s'), imgKb6s: k('imgKb6s'), top: runs[0].top };
  }
  await b.close(); srv.close();
  const f = (v, d = 0) => (v == null ? '-' : (+v).toFixed(d));
  console.log('page    FCP ms  LCP ms  DCL ms  load ms  CLS    KB@load req@load  KB@+6s req@+6s JS KB@+6s img KB@+6s');
  for (const [u, o] of Object.entries(out)) console.log(`${u.padEnd(7)} ${f(o.fcp).padStart(6)}  ${f(o.lcp).padStart(6)}  ${f(o.dcl).padStart(6)}  ${f(o.load).padStart(7)}  ${f(o.cls, 3)}  ${f(o.kbLoad).padStart(6)}  ${f(o.reqLoad).padStart(6)}  ${f(o.kb6s).padStart(6)}  ${f(o.req6s).padStart(6)}  ${f(o.jsKb6s).padStart(8)}  ${f(o.imgKb6s).padStart(9)}`);
  console.log(JSON.stringify(out));
});
