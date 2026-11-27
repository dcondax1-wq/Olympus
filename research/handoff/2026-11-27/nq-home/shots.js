// Screenshots of nq/trading_home.html + nq/pchealth.html at 390x844 and 1440x900 with the PC's REAL status post
// (real_post_2026-11-27.json, its time moved to "2 minutes ago"). node shots.js <web root> <out dir> <prefix>
const http = require('http'), fs = require('fs'), path = require('path');
const { chromium } = require('playwright');
const web = path.resolve(process.argv[2]), out = path.resolve(process.argv[3]), pre = process.argv[4] || 'after';
const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png' };
const srv = http.createServer((q, r) => {
  const f = path.join(web, decodeURIComponent(q.url.split('?')[0]));
  if (!f.startsWith(web) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) { r.writeHead(404); return r.end(); }
  r.writeHead(200, { 'Content-Type': MIME[path.extname(f)] || 'application/octet-stream' }); r.end(fs.readFileSync(f));
});
(async () => {
  await new Promise((ok) => srv.listen(0, '127.0.0.1', ok));
  const base = 'http://127.0.0.1:' + srv.address().port;
  const lite = JSON.parse(fs.readFileSync(path.join(__dirname, 'real_post_2026-11-27.json'), 'utf8'));
  const now = Math.floor(Date.now() / 1000), d = now - 120 - lite.t;
  for (const k of ['t', 'ext_t']) if (lite[k]) lite[k] += d;
  if (lite.reporter) lite.reporter.t += d;
  const browser = await chromium.launch();
  const pages = (process.argv[5] || 'trading_home,pchealth').split(',');
  for (const p of pages) {
    if (!fs.existsSync(path.join(web, 'nq', p + '.html'))) continue;
    for (const [w, h, tag] of [[390, 844, '390'], [1440, 900, '1440']]) {
      const ctx = await browser.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 2 });
      const pg = await ctx.newPage();
      const errs = [];
      pg.on('pageerror', (e) => errs.push(String(e)));
      await pg.addInitScript('window.__LITE__ = ' + JSON.stringify(lite) + ';');
      await pg.route('**/pc_feed.js', (route) => route.fulfill({ contentType: 'text/javascript',
        body: fs.readFileSync(path.join(web, 'pc_feed.js'), 'utf8') + '\n;window.PC_FEED.fetchLatest=function(){return Promise.resolve(window.__LITE__);};' }));
      await pg.goto(base + '/nq/' + p + '.html');
      await pg.waitForTimeout(900);
      const ov = await pg.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
      await pg.screenshot({ path: path.join(out, `${pre}_${p}_${tag}.png`), fullPage: true });
      console.log(p, tag, 'sideways', ov, 'errors', errs.length ? errs : 0);
      await ctx.close();
    }
  }
  await browser.close(); srv.close();
})();
