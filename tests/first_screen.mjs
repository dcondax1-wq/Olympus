// night-seedata 2026-11-23: the first-screen check (owner: "seeing my data is hard"). Serves tools/web_public, answers the ntfy
// poll with a PC-feed fixture (ndjson), opens each page at 390x844 (?at=), prints the text visible in the first screen as JSON.
// Needs node's playwright (the cloud has it); tests skip it where it is missing. Usage: node first_screen.mjs <web_public> <feed.ndjson> <iso at> [pages]
import { createRequire } from 'module';
const require = createRequire(import.meta.url);
const { chromium } = require('playwright');
import http from 'http'; import fs from 'fs'; import path from 'path';
const ROOT = process.argv[2], FEED = fs.readFileSync(process.argv[3], 'utf8'), AT = process.argv[4];
const PAGES = (process.argv[5] || 'gate/index.html,nq/index.html,business/mffu.html,cities/hub.html,nq/trading_home.html').split(',');
const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png', '.webp': 'image/webp' };
const srv = http.createServer((q, r) => {
  let p = decodeURIComponent(q.url.split('?')[0]); if (p.endsWith('/')) p += 'index.html';
  const f = path.join(ROOT, p);
  fs.readFile(f, (e, b) => { if (e) { r.writeHead(404); r.end(); return; }
    if (p === '/status_feed.json' && process.env.NET_STUB_KEEP_VK !== '1') {   // day-guard2 pins the PC's key; the fixture feed is unsigned
      try { const d = JSON.parse(b.toString('utf8')); delete d.vk; delete d.vks; b = Buffer.from(JSON.stringify(d)); } catch (x) { /* as is */ }
    }
    r.writeHead(200, { 'Content-Type': MIME[path.extname(f)] || 'application/octet-stream' }); r.end(b); });
}).listen(0);
const port = srv.address().port, origin = `http://127.0.0.1:${port}`;
const br = await chromium.launch();
const out = {};
for (const pg of PAGES) {
  const ctx = await br.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1 });
  await ctx.route('**/*', (rt) => {
    const u = rt.request().url();
    if (u.includes('json?poll=1') || u.includes('/json?')) return rt.fulfill({ status: 200, contentType: 'application/x-ndjson', body: FEED });
    if (!u.startsWith(origin)) return rt.fulfill({ status: 404, body: '' });
    return rt.continue();
  });
  const p = await ctx.newPage(); const errs = [];
  p.on('pageerror', (e) => errs.push(String(e).slice(0, 160)));
  try {
    await p.goto(`${origin}/${pg}${pg.includes('?') ? '&' : '?'}at=${AT}`, { waitUntil: 'load', timeout: 45000 });
    await p.waitForTimeout(4000);
    const txt = await p.evaluate(() => {
      const H = window.innerHeight, seen = []; const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
      let n; while ((n = w.nextNode())) { const s = n.textContent.replace(/\s+/g, ' ').trim(); if (!s) continue;
        const el = n.parentElement; if (!el) continue; const cs = getComputedStyle(el); if (cs.visibility === 'hidden' || cs.display === 'none') continue;
        const rc = el.getBoundingClientRect(); if (rc.width === 0 || rc.height === 0) continue; if (rc.top < H && rc.bottom > 0) seen.push(s); }
      return seen.join(' | ').slice(0, 3000);
    });
    out[pg] = { first: txt, errs };
  } catch (e) { out[pg] = { error: String(e).slice(0, 200) }; }
  await ctx.close();
}
await br.close(); srv.close();
console.log(JSON.stringify(out, null, 1));
