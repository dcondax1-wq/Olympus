// usage: node shots.cjs <outdir> [only]
const { chromium } = require('playwright');
const http = require('http'), fs = require('fs'), path = require('path');
const PUB = '/home/user/Olympus/tools/web_public', OUT = process.argv[2], ONLY = process.argv[3] || '';
const MIME = { '.js': 'application/javascript', '.html': 'text/html', '.css': 'text/css', '.json': 'application/json', '.png': 'image/png', '.svg': 'image/svg+xml', '.woff2': 'font/woff2', '.webmanifest': 'application/manifest+json' };
const srv = http.createServer((q, r) => { let p = decodeURIComponent(q.url.split('?')[0].split('#')[0]); if (p.endsWith('/')) p += 'index.html'; const f = path.join(PUB, p);
  fs.readFile(f, (e, d) => { if (e) { r.writeHead(404); r.end(); return; } r.writeHead(200, { 'content-type': MIME[path.extname(f)] || 'application/octet-stream' }); r.end(d); }); });
srv.listen(0, async () => {
  const B = 'http://127.0.0.1:' + srv.address().port;
  const b = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const fresh = async (url, wait) => { const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, hasTouch: true }); const p = await ctx.newPage(); const errs = [];
    p.on('pageerror', (e) => errs.push(String(e))); p.on('console', (m) => { if (m.type() === 'error') errs.push('console: ' + m.text()); });
    await p.route('**/ntfy.sh/**', (r) => r.fulfill({ status: 200, body: '' })); await p.addInitScript(() => { try { localStorage.setItem('oly.new.pillars', '1'); } catch (_) {} });
    await p.goto(B + url, { waitUntil: 'load' }); await p.waitForTimeout(wait); return { p, ctx, errs }; };
  const job = async (name, url, wait, fn) => { if (ONLY && !name.includes(ONLY)) return; const { p, ctx, errs } = await fresh(url, wait); if (fn) await fn(p); await p.screenshot({ path: `${OUT}/${name}.png` });
    const st = await p.evaluate(() => window.__pillars ? window.__pillars.stats() : null).catch(() => null); console.log(name, JSON.stringify(st), errs.slice(0, 3).join(' | ')); await ctx.close(); };
  await job('1_pillars', '/pillars/?fx=hq#lit', 6000);
  await job('2_pillars_tap_atlas', '/pillars/?fx=hq#lit', 4500, async (p) => { const pr = await p.evaluate(() => window.__pillars.project('atlas')); const r = await p.evaluate(() => { const b = document.getElementById('c').getBoundingClientRect(); return [b.left, b.top]; }); await p.mouse.click(r[0] + pr.x, r[1] + pr.y + 90); await p.waitForTimeout(3500); });
  await job('3_pillars_intro_mid', '/pillars/?fx=hq#lit', 1300);
  await job('4_gate', '/gate/?fx=hq', 6000);
  await job('5_nq', '/nq/?fx=hq', 7000);
  await job('7_pillars_low', '/pillars/?lite=1#lit', 6000);
  await job('8_zenith', '/?fx=hq', 8000);
  await job('6_pillars_2d', '/pillars/?lite=2d#of', 3000);
  await b.close(); srv.close();
});
