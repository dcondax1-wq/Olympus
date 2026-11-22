// tests/test_site_factory.py --browser: open sites at phone width, report scroll width, errors, call dock; save shots.
'use strict';
const { chromium } = require('playwright'); const http = require('http'), fs = require('fs'), path = require('path');
const [root, out, ...paths] = process.argv.slice(2);
const T = { '.html': 'text/html', '.json': 'application/json', '.css': 'text/css', '.js': 'text/javascript', '.png': 'image/png', '.jpg': 'image/jpeg' };
const srv = http.createServer((q, r) => { let p = path.join(root, decodeURIComponent(q.url.split('?')[0])); if (fs.existsSync(p) && fs.statSync(p).isDirectory()) p += '/index.html';
  if (!p.startsWith(root) || !fs.existsSync(p)) { r.writeHead(404); return r.end(); } r.writeHead(200, { 'content-type': T[path.extname(p)] || 'text/plain' }); fs.createReadStream(p).pipe(r); });
srv.listen(0, async () => {
  const port = srv.address().port, b = await chromium.launch(), res = [];
  for (const [i, u] of paths.entries()) {
    const pg = await b.newPage({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1 }); const errs = [];
    pg.on('pageerror', (e) => errs.push(String(e))); pg.on('console', (m) => { if (m.type() === 'error') errs.push(m.text()); });
    await pg.goto(`http://localhost:${port}/${u}`); await pg.waitForTimeout(u.includes('factory') ? 1500 : 700);
    const sw = await pg.evaluate(() => document.documentElement.scrollWidth);
    const dock = await pg.evaluate(() => { const d = document.querySelector('.dock a[href^="tel:"]'); if (!d) return false; const r = d.getBoundingClientRect(); return r.bottom <= innerHeight && r.height >= 44; });
    await pg.screenshot({ path: path.join(out, (u.includes('factory') ? 'gallery' : 'site-' + (i + 1)) + '.png'), fullPage: !u.includes('factory') });
    res.push({ u, sw, errs, dock }); await pg.close();
  }
  await b.close(); srv.close(); console.log(JSON.stringify(res));
});
