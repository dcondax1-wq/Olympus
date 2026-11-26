// Shots for day-site5 C (390 x 844 @2x): Home, the "Everything else" arena (its Archive chip), the Archive door. usage: [PUB=<web_public>] node shots.cjs <outdir>
const { chromium } = require('playwright'); const http = require('http'), fs = require('fs'), path = require('path');
const PUB = path.resolve(process.env.PUB || path.join(__dirname, '../../../../tools/web_public')), OUT = process.argv[2];
const MIME = { '.js': 'application/javascript', '.html': 'text/html', '.css': 'text/css', '.json': 'application/json', '.png': 'image/png', '.svg': 'image/svg+xml', '.woff2': 'font/woff2', '.webmanifest': 'application/manifest+json' };
const srv = http.createServer((q, r) => { let p = decodeURIComponent(q.url.split('?')[0].split('#')[0]); if (p.endsWith('/')) p += 'index.html'; const f = path.join(PUB, p);
  fs.readFile(f, (e, d) => { if (e) { r.writeHead(404); r.end(); return; } r.writeHead(200, { 'content-type': MIME[path.extname(f)] || 'application/octet-stream' }); r.end(d); }); });
srv.listen(0, async () => {
  const B = 'http://127.0.0.1:' + srv.address().port, b = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader'] });
  const shot = async (name, url, wait, full) => { const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, hasTouch: true });
    await ctx.route((u) => !u.href.startsWith(B), (r) => r.abort()); await ctx.addInitScript(() => { try { localStorage.setItem('oly.new.pillars', '1'); } catch (_) {} });
    const p = await ctx.newPage(); await p.goto(B + url, { waitUntil: 'load' }); await p.waitForTimeout(wait); await p.screenshot({ path: `${OUT}/${name}.png`, fullPage: !!full }); await ctx.close(); };
  await shot('c1_home', '/gate/', 7000);
  await shot('c2_arena_else', '/hub/arena.html?a=else', 2500, true);
  await shot('c3_archive_door', '/hub/arena.html?a=archive', 2500, true);
  await b.close(); srv.close();
});
