// usage: node shots.cjs <outdir> [only]   (day-pillars4: Home Today strip, Pillars panel + DATA page, Brain rooms; 390x844 @2x, SwiftShader)
const { chromium } = require('playwright');
const http = require('http'), fs = require('fs'), path = require('path');
const PUB = path.resolve(__dirname, '../../../../tools/web_public'), OUT = process.argv[2], ONLY = process.argv[3] || '';
const MIME = { '.js': 'application/javascript', '.html': 'text/html', '.css': 'text/css', '.json': 'application/json', '.png': 'image/png', '.svg': 'image/svg+xml', '.woff2': 'font/woff2', '.webmanifest': 'application/manifest+json' };
const srv = http.createServer((q, r) => { let p = decodeURIComponent(q.url.split('?')[0].split('#')[0]); if (p.endsWith('/')) p += 'index.html'; const f = path.join(PUB, p);
  fs.readFile(f, (e, d) => { if (e) { r.writeHead(404); r.end(); return; } r.writeHead(200, { 'content-type': MIME[path.extname(f)] || 'application/octet-stream' }); r.end(d); }); });
srv.listen(0, async () => {
  const B = 'http://127.0.0.1:' + srv.address().port;
  const b = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const job = async (name, url, wait, fn, full) => {
    if (ONLY && !name.includes(ONLY)) return;
    const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, hasTouch: true }); const p = await ctx.newPage(); const errs = [];
    p.on('pageerror', (e) => errs.push(String(e))); p.on('console', (m) => { if (m.type() === 'error') errs.push('console: ' + m.text()); });
    await p.route('**/ntfy.sh/**', (r) => r.fulfill({ status: 200, body: '' })); await p.addInitScript(() => { try { localStorage.setItem('oly.new.pillars', '1'); } catch (_) {} });
    await p.goto(B + url, { waitUntil: 'load' }); await p.waitForTimeout(wait); if (fn) await fn(p);
    await p.screenshot({ path: `${OUT}/${name}.png`, fullPage: !!full }); console.log(name, errs.slice(0, 3).join(' | ')); await ctx.close();
  };
  await job('03_home', '/gate/?fx=hq', 6000);
  await job('04_pillars_panel_lit', '/pillars/?lite=2d#lit', 3000, async (p) => { await p.evaluate(() => { const e = document.getElementById('panel'); if (e) window.scrollTo(0, e.getBoundingClientRect().top + scrollY - 60); }); await p.waitForTimeout(400); });
  await job('05_pillar_data_lit', '/pillars/data.html#lit', 3000, null, true);
  await job('06_pillar_data_of', '/pillars/data.html#of', 3000, null, true);
  await job('07_brain_overview', '/brain/?lite=2d', 4000);
  await job('08_brain_lit', '/brain/?lite=2d#lit', 4000, async (p) => { await p.evaluate(() => { const e = document.getElementById('room'); if (e) window.scrollTo(0, e.getBoundingClientRect().top + scrollY - 10); }); await p.waitForTimeout(400); });
  await b.close(); srv.close();
});
