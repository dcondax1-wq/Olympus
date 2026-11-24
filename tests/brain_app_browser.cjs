// Browser part of tests/test_brain_app.py (Node Playwright, software GL). argv: <base url> <shots dir or ''> <scenario json file>. Prints one JSON line.
// The PC post: the real pc_feed.js with fetchLatest answering the scenario's parsed post (or null = the SAMPLE fixture); the chart post via the
// ntfy route; the status feed is the test topic (no signing key). cdnjs is blocked: three.js comes from the site's own r160 copy.
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const [, , BASE, SHOTS, SCF] = process.argv;
const SC = JSON.parse(fs.readFileSync(SCF, 'utf8'));
const REAL = fs.readFileSync(path.join(__dirname, '..', 'tools', 'web_public', 'pc_feed.js'), 'utf8');
const out = {};
const T = (ms) => new Promise((r) => setTimeout(r, ms));
(async () => {
  const b = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  async function page(url, post, opt) {
    const o = opt || {};
    const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: SHOTS ? 2 : 1, hasTouch: true, reducedMotion: o.reduce ? 'reduce' : 'no-preference' });
    const p = await ctx.newPage(), errs = [], off = [];
    p.on('pageerror', (e) => errs.push(String(e)));
    const stub = REAL + `\n;window.PC_FEED.fetchLatest = async function () { return ${JSON.stringify(post || null)}; };`;
    await p.route('**/*', (r) => {
      const u = r.request().url();
      if (/pc_feed\.js/.test(u)) return r.fulfill({ contentType: 'application/javascript', body: stub });
      if (/status_feed\.json/.test(u)) return r.fulfill({ contentType: 'application/json', body: SC.feed });
      if (/ntfy\.sh\/.*-bars\/json/.test(u)) return r.fulfill({ status: 200, body: post ? SC.barsNd : '' });
      if (!u.startsWith(BASE)) { off.push(u); return r.abort(); }
      return r.continue();
    });
    await p.goto(BASE + url, { waitUntil: 'load' });
    await p.waitForFunction(() => window.BRAIN && window.BRAIN.ready(), null, { timeout: 60000 });
    await p.waitForFunction(() => /^(3d|2d)/.test(document.documentElement.dataset.mode || ''), null, { timeout: 120000 });   // software GL is slow
    await p.waitForTimeout(o.wait || 3500);
    return { p, ctx, errs, off };
  }
  const room = (p) => p.evaluate(() => ({
    r: document.getElementById('room').dataset.r, hash: location.hash, status: (document.getElementById('rStatus') || {}).textContent,
    setup: (document.querySelector('#rNext .setup') || {}).textContent || '', chain: [...document.querySelectorAll('#rChain li')].map((x) => x.className + ':' + x.textContent),
    lobes: [...document.querySelectorAll('#rNext .lobe')].map((x) => x.dataset.lobe), wait: (document.getElementById('rWait') || {}).textContent || '',
    dist: (document.getElementById('rDist') || {}).textContent || '', px: [...document.querySelectorAll('#rPx b')].map((x) => x.textContent),
    chart: !!document.getElementById('rChartBox'), chartMode: (document.getElementById('rChartBox') || { dataset: {} }).dataset.mode || null,
    lbls: [...document.querySelectorAll('.lbl')].map((x) => x.textContent), legend: [...document.querySelectorAll('.legend span')].map((x) => x.dataset.k),
    think: [...document.querySelectorAll('#rStream li span')].map((x) => x.textContent), thinkSrc: (document.querySelector('#rThink .src') || {}).textContent || '',
    conf: (document.getElementById('rConf') || {}).textContent || '', week: document.querySelectorAll('#rWeek li em').length, testing: (document.getElementById('rTesting') || {}).textContent || '',
    money: (document.getElementById('rMoney') || {}).textContent || '', learnSrc: (document.querySelector('#rLearn .src') || {}).textContent || '',
    body: document.body.innerText,
  }));
  const geo = (p) => p.evaluate(() => {
    const small = [...document.querySelectorAll('button, a')].filter((e) => { const r = e.getBoundingClientRect(); return r.width && r.height && e.offsetParent !== null && (r.height < 44 || r.width < 44); }).map((e) => (e.className || e.tagName) + ':' + (e.textContent || '').trim().slice(0, 20));
    return { wide: document.documentElement.scrollWidth > innerWidth + 1, small };
  });
  try {
    // 1. no PC post: the SAMPLE fixture, the whole brain in 3D
    let { p, ctx, errs, off } = await page('/brain/?fx=hq', null);
    out.sample = await p.evaluate(() => ({ mode: document.documentElement.dataset.mode, stats: window.BRAIN.stats(), banner: document.getElementById('sample').hidden ? '' : document.getElementById('sample').textContent,
      pill: document.getElementById('pcPill').textContent, tags: [...document.querySelectorAll('.tag')].map((t) => t.dataset.r), dock: [...document.querySelectorAll('.dock .reg')].map((t) => t.dataset.r),
      soon: [...document.querySelectorAll('#rSoon li')].map((x) => x.dataset.r), headline: document.getElementById('headline').textContent }));
    out.sampleGeo = await geo(p);
    if (SHOTS) await p.screenshot({ path: SHOTS + '/brain_overview_sample.png' });
    // a tap on a region of the 3D brain flies in and opens its room
    const pr = await p.evaluate(() => window.BRAIN.project('of')), cr = await p.evaluate(() => { const r = document.getElementById('c').getBoundingClientRect(); return { x: r.left, y: r.top }; });
    await p.evaluate(() => { for (const t of document.querySelectorAll('.tag')) t.style.pointerEvents = 'none'; });   // hit the canvas itself
    if (pr) { await p.mouse.click(cr.x + pr.x, cr.y + pr.y); await T(2500); }
    out.tap = await p.evaluate(() => ({ r: document.getElementById('room').dataset.r, hash: location.hash, sel: (window.BRAIN.stats() || {}).sel }));
    await p.evaluate(() => window.BRAIN.select('lit')); await T(4500);
    out.litSample = await room(p);
    if (SHOTS) { await p.screenshot({ path: SHOTS + '/brain_lit_sample.png' }); await p.screenshot({ path: SHOTS + '/brain_lit_sample_full.png', fullPage: true }); }
    await p.click('.dock .reg[data-r="learn"]'); await T(2500);
    out.learn = await room(p);
    if (SHOTS) await p.screenshot({ path: SHOTS + '/brain_learn_full.png', fullPage: true });
    await p.click('.dock .reg[data-r="risk"]'); await T(2500);
    out.risk = await room(p);
    out.errors = errs; out.off = off; await ctx.close();

    // 2. the real-shape PC post (setup forming, no think / next / levels fields yet): degrades to the PC's log and its words
    ({ p, ctx, errs, off } = await page('/brain/?fx=hq#lit', SC.forming));
    out.litLive = await room(p);
    out.livePill = await p.evaluate(() => [document.getElementById('pcPill').textContent, document.getElementById('sample').hidden]);
    if (SHOTS) await p.screenshot({ path: SHOTS + '/brain_lit_live_full.png', fullPage: true });
    await p.evaluate(() => { location.hash = '#atlas'; }); await T(3000);
    out.atlas = await room(p);
    if (SHOTS) await p.screenshot({ path: SHOTS + '/brain_atlas_live_full.png', fullPage: true });
    await p.evaluate(() => { location.hash = '#of'; }); await T(2000);
    out.of = await room(p);
    await p.evaluate(() => { location.hash = '#blitz'; }); await T(2000);
    out.blitz = await room(p);
    out.liveGeo = await geo(p);
    out.liveErrors = errs; await ctx.close();

    // 3. the same post WITH the new fields (think, next, levels): the PC's own lines win
    ({ p, ctx, errs } = await page('/brain/?fx=hq#lit', SC.formingPlus));
    out.litPlus = await room(p);
    out.plusErrors = errs; await ctx.close();

    // 4. in a trade
    ({ p, ctx, errs } = await page('/brain/?fx=hq#lit', SC.trade));
    out.trade = await room(p);
    if (SHOTS) await p.screenshot({ path: SHOTS + '/brain_lit_trade.png' });
    out.tradeErrors = errs; await ctx.close();

    // 5. the flat 2D brain + reduced motion
    ({ p, ctx, errs } = await page('/brain/?lite=2d#atlas', null, { reduce: true }));
    out.flat = await p.evaluate(() => ({ mode: document.documentElement.dataset.mode, n: document.querySelectorAll('#flat button').length, chart: window.BRAIN.chartMode() }));
    await p.click('#flat button[data-r="risk"]'); await T(800);
    out.flatPick = await p.evaluate(() => document.getElementById('room').dataset.r);
    if (SHOTS) await p.screenshot({ path: SHOTS + '/brain_flat_2d.png' });
    out.flatErrors = errs; await ctx.close();
  } catch (e) { out.fatal = String(e && e.stack || e).slice(0, 800); }
  await b.close();
  console.log(JSON.stringify(out));
})();
