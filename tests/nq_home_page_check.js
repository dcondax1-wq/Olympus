// Browser check for nq/trading_home.html (tiles) + nq/pchealth.html at 390x844 with the REAL PC post of 2026-11-27 (moved to 2 min ago),
// plus an OLD copy (5 h) and NO report. Prints one JSON line. node tests/nq_home_page_check.js <web root> <fixture>
const http = require('http'), fs = require('fs'), path = require('path');
const { chromium } = require('playwright');
const web = path.resolve(process.argv[2]), fix = path.resolve(process.argv[3]);
const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png' };
const srv = http.createServer((q, r) => {
  const f = path.join(web, decodeURIComponent(q.url.split('?')[0]));
  if (!f.startsWith(web) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) { r.writeHead(404); return r.end(); }
  r.writeHead(200, { 'Content-Type': MIME[path.extname(f)] || 'application/octet-stream' }); r.end(fs.readFileSync(f));
});
function shifted(ago) {
  const lite = JSON.parse(fs.readFileSync(fix, 'utf8')), d = Math.floor(Date.now() / 1000) - ago - lite.t;
  for (const k of ['t', 'ext_t']) if (lite[k]) lite[k] += d;
  if (lite.reporter) lite.reporter.t += d;
  return lite;
}
(async () => {
  await new Promise((ok) => srv.listen(0, '127.0.0.1', ok));
  const base = 'http://127.0.0.1:' + srv.address().port, out = {};
  const browser = await chromium.launch();
  for (const [name, lite] of [['fresh', shifted(120)], ['old', shifted(5 * 3600)], ['none', null]]) {
    for (const p of ['trading_home', 'pchealth']) {
      const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, permissions: ['clipboard-read', 'clipboard-write'] });
      const pg = await ctx.newPage(), errs = [], sends = [];
      pg.on('pageerror', (e) => errs.push(String(e)));
      pg.on('request', (r) => { if (r.method() !== 'GET') sends.push(r.method() + ' ' + r.url()); else if (!r.url().startsWith(base)) sends.push('outside ' + r.url()); });
      await pg.addInitScript('window.__LITE__ = ' + JSON.stringify(lite) + ';');
      await pg.route('**/pc_feed.js', (route) => route.fulfill({ contentType: 'text/javascript',
        body: fs.readFileSync(path.join(web, 'pc_feed.js'), 'utf8') + '\n;window.PC_FEED.fetchLatest=function(){return Promise.resolve(window.__LITE__);};' }));
      await pg.goto(base + '/nq/' + p + '.html');
      await pg.waitForTimeout(700);
      out[name + '_' + p] = await pg.evaluate(() => {
        const q = (s) => Array.from(document.querySelectorAll(s));
        const small = q('a,button').filter((e) => { const r = e.getBoundingClientRect(); return r.width && r.height < 44 && !e.closest('.foot'); }).map((e) => e.textContent.trim().slice(0, 30));
        return { side: document.documentElement.scrollWidth - document.documentElement.clientWidth, bg: getComputedStyle(document.body).backgroundColor,
          rows: q('li.row').length, tiles: q('a.tile').map((a) => [a.dataset.id, a.className.replace('tile ', ''), a.querySelector('.tb').textContent, a.querySelector('.ts').textContent]),
          hero: (document.getElementById('hero') || {}).dataset ? document.getElementById('hero').dataset.s : null, say: (document.getElementById('say') || {}).textContent || null,
          cards: q('li.ck').map((l) => [l.dataset.id, l.className.replace('ck ', '')]), text: document.body.innerText, small };
      });
      if (p === 'pchealth' && name === 'fresh') {
        await pg.click('#copy'); await pg.waitForTimeout(200);
        out[name + '_' + p].clip = await pg.evaluate(() => navigator.clipboard.readText().catch(() => 'READ FAILED'));
      }
      out[name + '_' + p].errs = errs; out[name + '_' + p].sends = sends;
      await ctx.close();
    }
  }
  await browser.close(); srv.close();
  console.log(JSON.stringify(out));
})();
