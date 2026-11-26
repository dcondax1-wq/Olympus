// Browser half of tests/test_brain_learned.py: brain/learned.html at 390 x 844. Args: base url, shots dir ('' = none). Prints one JSON line.
const { chromium } = require('playwright');
(async () => {
  const [base, shots] = process.argv.slice(2);
  const o = {};
  const b = await chromium.launch();
  try {
    const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: shots ? 2 : 1 });
    const p = await ctx.newPage();
    o.errors = []; o.off = []; o.methods = [];
    p.on('pageerror', (e) => o.errors.push(String(e)));
    p.on('console', (m) => { if (m.type() === 'error') o.errors.push(m.text()); });
    p.on('request', (r) => { if (!r.url().startsWith(base)) o.off.push(r.url()); if (r.method() !== 'GET') o.methods.push(r.method()); });
    await p.goto(`${base}/brain/learned.html`, { waitUntil: 'networkidle' });
    await p.waitForSelector('html[data-mode="ready"]', { timeout: 15000 });
    await p.waitForTimeout(600);
    o.page = await p.evaluate(() => ({
      wide: document.documentElement.scrollWidth > innerWidth + 1,
      small: [...document.querySelectorAll('a,button')].filter((e) => { const r = e.getBoundingClientRect(); return r.width && getComputedStyle(e).display !== 'none' && (r.height < 44 || r.width < 44); }).map((e) => e.textContent.trim().slice(0, 30)),
      tiles: document.querySelectorAll('#hero .tile').length, ideas: document.querySelectorAll('#grad .idea').length,
      tl: document.querySelectorAll('#tl li.x').length, next: document.querySelectorAll('#next li').length,
      funnel: document.querySelectorAll('#funnel .fn').length, mill: document.querySelectorAll('#mill .fn').length,
      health: document.querySelectorAll('#health .band').length, text: document.body.innerText,
      bg: getComputedStyle(document.body).backgroundColor }));
    if (shots) { await p.screenshot({ path: `${shots}/learned_top.png` }); await p.screenshot({ path: `${shots}/learned_full.png`, fullPage: true }); }
    await p.click('#filt button[data-f="lit"]');
    await p.waitForTimeout(150);
    o.lit = await p.evaluate(() => ({ chips: [...document.querySelectorAll('#tl li.x small')].map((x) => x.textContent), pressed: document.querySelector('#filt button[data-f="lit"]').getAttribute('aria-pressed') }));
    if (shots) await p.locator('#sTime').screenshot({ path: `${shots}/learned_lit_lessons.png` });
    const more = await p.$('#tlMore:not([hidden])');
    if (more) { const n0 = await p.$$eval('#tl li.x', (x) => x.length); await more.click(); o.more = [n0, await p.$$eval('#tl li.x', (x) => x.length)]; }
    // no learn.json at all: an honest empty page, no error
    const p2 = await ctx.newPage();
    o.emptyErrors = []; p2.on('pageerror', (e) => o.emptyErrors.push(String(e)));
    await p2.route('**/brain/learn.json', (r) => r.fulfill({ status: 404, body: '' }));
    await p2.goto(`${base}/brain/learned.html`, { waitUntil: 'networkidle' });
    await p2.waitForSelector('html[data-mode="empty"]', { timeout: 15000 });
    o.empty = await p2.evaluate(() => document.getElementById('hero').innerText);
    // a learn.json from before this view (no 'learning' block): every card says why it is empty
    const p3 = await ctx.newPage();
    o.oldErrors = []; p3.on('pageerror', (e) => o.oldErrors.push(String(e)));
    await p3.route('**/brain/learn.json', (r) => r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ v: 1, journal: [{ date: '2026-11-20', pillar: 'lit', text: 'old lesson', status: 'watching', n: null, usd: null }], state: {} }) }));
    await p3.goto(`${base}/brain/learned.html`, { waitUntil: 'networkidle' });
    await p3.waitForSelector('html[data-mode="ready"]', { timeout: 15000 });
    o.old = await p3.evaluate(() => ({ grad: document.getElementById('grad').innerText, tl: document.querySelectorAll('#tl li.x').length }));
    // the Brain page links here
    const p4 = await ctx.newPage();
    await p4.goto(`${base}/brain/index.html#lit`, { waitUntil: 'domcontentloaded' });
    o.brainLink = await p4.evaluate(() => !!document.querySelector('#learnedLink[href="learned.html"]'));
  } catch (e) { o.fatal = String(e); }
  await b.close();
  console.log(JSON.stringify(o));
})();
