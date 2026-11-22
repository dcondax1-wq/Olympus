// Browser check of tools/web_public/nq/trading_home.html at 390x844 (run by tests/test_trading_home.py). Prints PASS / FAIL lines.
const http = require('http'), fs = require('fs'), path = require('path');
const { chromium } = require('playwright');
const web = process.argv[2];
const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png' };
const srv = http.createServer((q, r) => {
  const f = path.join(web, decodeURIComponent(q.url.split('?')[0]));
  if (!f.startsWith(web) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) { r.writeHead(404); return r.end(); }
  r.writeHead(200, { 'Content-Type': MIME[path.extname(f)] || 'application/octet-stream' }); r.end(fs.readFileSync(f));
});
const out = [];
const check = (n, c, i) => out.push((c ? 'PASS ' : 'FAIL ') + n + (c ? '' : '   -> ' + JSON.stringify(i)));
(async () => {
  await new Promise((ok) => srv.listen(0, '127.0.0.1', ok));
  const base = 'http://127.0.0.1:' + srv.address().port;
  const now = Math.floor(Date.now() / 1000);
  const mk = (running, rpBadge, kaOn) => ({ t: now - 120, board: { running }, accounts: [
    { id: 'z', name: 'MFFU 50K Eval', badge: 'LIVE', source: 'pc', kind: 'eval', eval: { to_target: 3807 }, conn: { running } },
    { id: 'rp', name: 'Rapid EOD 25K', badge: rpBadge, source: 'pc', kind: 'eval', eval: { to_target: 1500 }, conn: { running } }],
    k7: { a: [{ id: 'z', nm: 'Zlarior', on: kaOn }] } });
  const browser = await chromium.launch();
  async function open(lite) {
    const ctx = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 1 });
    const pg = await ctx.newPage();
    const errs = [], posts = [];
    pg.on('pageerror', (e) => errs.push(String(e)));
    pg.on('request', (r) => { if (r.method() !== 'GET') posts.push(r.method()); });
    await pg.addInitScript('window.__LITE__ = ' + JSON.stringify(lite) + ';');
    await pg.route('**/pc_feed.js', (route) => route.fulfill({ contentType: 'text/javascript',
      body: fs.readFileSync(path.join(web, 'pc_feed.js'), 'utf8') + '\n;window.PC_FEED.fetchLatest=function(){return Promise.resolve(window.__LITE__);};' }));
    await pg.goto(base + '/nq/trading_home.html');
    await pg.waitForSelector('li.row');
    await pg.waitForTimeout(300);
    return { pg, errs, posts, ctx };
  }
  try {
    let { pg, errs, posts, ctx } = await open(mk(false, 'Sim', false));
    const texts = await pg.$$eval('li.row', (a) => a.map((x) => x.innerText));
    const ov = await pg.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    const bg = await pg.evaluate(() => getComputedStyle(document.body).backgroundColor);
    const card = await pg.evaluate(() => getComputedStyle(document.querySelector('li.row')).backgroundColor);
    const small = await pg.evaluate(() => [...document.querySelectorAll('button')].every((b) => b.getBoundingClientRect().height >= 44));
    const shot = path.join(process.env.TMPDIR || '/tmp', 'trading_home_390.png');
    await pg.screenshot({ path: shot });
    check('j. phone 390x844: 5 lines, no sideways scroll, black page + #16131e cards, no JS error',
      texts.length === 5 && ov <= 0 && bg === 'rgb(0, 0, 0)' && card === 'rgb(22, 19, 30)' && !errs.length, [texts.length, ov, bg, card, errs]);
    check('j2. unchecked lines say what to do and the menu number (bot off 2, keep-alive 3, alerts 5, Rapid held 2)',
      /press 2/.test(texts[0]) && /press 3/.test(texts[1]) && /press 5/.test(texts[2]) && /press 2/.test(texts[3]) && /Rapid EOD 25K/.test(texts[3]), texts);
    check('j3. the next step is in dollars ($1,500 for the Rapid)', /\$1,500/.test(texts[4]), texts[4]);
    check('j4. buttons are 44px tall; the page sends nothing (GET only)', small && !posts.length, [small, posts]);
    await pg.click('button.tick'); await pg.waitForTimeout(200);
    const t2 = await pg.$$eval('li.row', (a) => a.map((x) => x.innerText));
    check("j5. 'I got my test alert' ticks the alerts line (this phone only)", /You saw a test alert/.test(t2[2]), t2[2]);
    await ctx.close();
    ({ pg, errs, ctx } = await open(mk(true, 'LIVE', true)));
    const t3 = await pg.$$eval('li.row', (a) => a.map((x) => x.innerText));
    const pill = await pg.innerText('#left');
    check('j6. all armed + running + keep-alive on: only the alerts tick is left ("1 to do")', pill === '1 to do' && !/press 2/.test(t3.join(' ')), [pill, t3]);
    await ctx.close();
    ({ pg, errs, ctx } = await open(null));
    const t4 = await pg.$$eval('li.row', (a) => a.map((x) => x.innerText));
    check('j7. no PC report at all: nothing shows done and each line says what to do', t4.length === 5 && /No report from the PC/.test(t4[0]) && !/✓/.test(t4.join('')), t4);
    await ctx.close();
  } catch (e) { check('j. page check ran', false, String(e).slice(0, 300)); }
  await browser.close(); srv.close();
  console.log(out.join('\n'));
})();
