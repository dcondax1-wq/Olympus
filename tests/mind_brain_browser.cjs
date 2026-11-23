// Browser part of tests/test_mind_brain.py (Node Playwright; Python Playwright is not on every box). Prints one JSON line of results.
// argv: <base url> <shots dir or ''>. home.json is replaced by a fixture with a fresh PC glance (LIT at 5/10, ATLAS EMA armed) so the
// live path is exercised without the PC; everything else is the real site files.
const { chromium } = require('playwright');
const [, , BASE, SHOTS] = process.argv;
const out = {};
(async () => {
  const b = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const now = Math.floor(Date.now() / 1000);
  const home = { live: { pc: { glance: { t: now - 120, bots: [
    { id: 'lit', name: 'Zlarior', stage: '5m CISD (5/10)', wait: 'a 5m CISD back through 21,000.00', on: true },
    { id: 'atlas', name: 'ATLAS', on: true, lobes: [{ id: 'ema', st: 'armed', text: 'Armed (long): entry at the next 5m open' }, { id: 'macd', st: 'window', text: 'watching the Asia low' }, { id: 'sr', st: 'done', text: 'Done for today' }] }] } } } };
  async function page(q) {
    const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: SHOTS ? 2 : 1, hasTouch: true });
    const p = await ctx.newPage(), errs = [];
    p.on('pageerror', (e) => errs.push(String(e)));
    await p.route('**/home.json', (r) => r.fulfill({ contentType: 'application/json', body: JSON.stringify(home) }));
    await p.route('**/status_feed.json', (r) => r.fulfill({ status: 404, body: '' }));
    await p.goto(BASE + '/cities/mind/' + (q || ''), { waitUntil: 'load' });
    await p.waitForFunction(() => document.documentElement.dataset.ready === '1', null, { timeout: 30000 });
    await p.waitForTimeout(1500);
    return { p, errs, ctx };
  }
  try {
    const { p, errs, ctx } = await page('');
    out.mode = await p.evaluate(() => document.documentElement.dataset.mode);
    out.stats = await p.evaluate(() => (window.__mind ? window.__mind.stats() : null));
    out.sideways = await p.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1);
    out.layout = await p.evaluate(() => { const c = document.getElementById('c').getBoundingClientRect(), n = document.getElementById('lobes').getBoundingClientRect(), h = document.querySelector('.top').getBoundingClientRect();
      return { canvasTop: c.top, canvasBottom: c.bottom, headerBottom: h.bottom, navTop: n.top, navBottom: n.bottom, vh: innerHeight }; });
    out.labels = await p.evaluate(() => { const v = [...document.querySelectorAll('.tip')].filter((d) => d.style.display !== 'none').map((d) => d.getBoundingClientRect());
      let o = 0; for (let i = 0; i < v.length; i++) for (let j = i + 1; j < v.length; j++) { const a = v[i], b = v[j]; if (a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom) o++; } return { shown: v.length, overlaps: o }; });
    out.pill = await p.textContent('#pcPill');
    if (SHOTS) await p.screenshot({ path: SHOTS + '/1_brain_390x844.png' });
    await p.click('button.lobe[data-lobe="lit"]'); await p.waitForTimeout(700);
    out.litNow = await p.evaluate(() => [...document.querySelectorAll('#chain li')].map((li) => li.dataset.step + ':' + li.className));
    out.litState = await p.textContent('#liveState');
    if (SHOTS) await p.screenshot({ path: SHOTS + '/2_lit_chain_live.png' });
    out.trades = await p.evaluate(() => document.querySelectorAll('#trades .tr').length);
    out.tl = await p.evaluate(() => { const s = document.querySelector('#timeline svg'); return s ? { candles: s.querySelectorAll('rect').length - 1, marks: s.querySelectorAll('circle').length, chips: document.querySelectorAll('#tlrow .tlstep').length } : null; });
    await p.evaluate(() => document.getElementById('tlwrap').scrollIntoView());
    if (SHOTS) { await p.waitForTimeout(300); await p.screenshot({ path: SHOTS + '/3_lit_trade_timeline.png' }); }
    // a backtest trade with every engine step: the 3rd row
    await p.click('#trades .tr:nth-child(5)'); await p.waitForTimeout(300);
    out.tlFull = await p.evaluate(() => [...document.querySelectorAll('#tlrow .tlstep')].filter((x) => !x.classList.contains('miss')).length);
    await p.evaluate(() => document.getElementById('tlwrap').scrollIntoView());
    if (SHOTS) { await p.waitForTimeout(300); await p.screenshot({ path: SHOTS + '/4_lit_backtest_timeline.png' }); }
    await p.click('button.lobe[data-lobe="ema"]'); await p.waitForTimeout(500);
    out.emaNow = await p.evaluate(() => [...document.querySelectorAll('#chain li.now')].map((li) => li.dataset.step));
    out.emaTrades = await p.evaluate(() => document.querySelectorAll('#trades .tr').length);
    await p.click('button.lobe[data-lobe="sr"]'); await p.waitForTimeout(500);
    out.srDone = await p.evaluate(() => document.querySelectorAll('#chain li.done').length);
    await p.evaluate(() => document.getElementById('tlwrap').scrollIntoView());
    if (SHOTS) { await p.waitForTimeout(300); await p.screenshot({ path: SHOTS + '/5_atlas_sr_timeline.png' }); }
    await p.evaluate(() => document.getElementById('lobes').scrollLeft = 9999);
    await p.click('button.lobe[data-lobe="r_lit"]'); await p.waitForTimeout(500);
    out.finds = await p.evaluate(() => document.querySelectorAll('#body .find').length);
    await p.click('#close'); await p.waitForTimeout(400);
    out.closed = await p.evaluate(() => document.getElementById('sheet').getAttribute('aria-hidden'));
    // a tap on the canvas at a lobe's projected spot opens that lobe
    const pr = await p.evaluate(() => window.__mind && window.__mind.project('sr'));
    const cr = await p.evaluate(() => { const r = document.getElementById('c').getBoundingClientRect(); return { x: r.left, y: r.top }; });
    if (pr) { await p.mouse.click(cr.x + pr.x, cr.y + pr.y); await p.waitForTimeout(500); out.canvasPick = await p.evaluate(() => document.querySelector('#body h2') && document.querySelector('#body h2').textContent); }
    out.errors = errs; await ctx.close();
    const lp = await page('?lite=1');
    out.lowMode = await lp.p.evaluate(() => document.documentElement.dataset.mode); out.lowStats = await lp.p.evaluate(() => window.__mind && window.__mind.stats());
    out.lowErrors = lp.errs; await lp.ctx.close();
    const f = await page('?lite=2d');
    out.flatMode = await f.p.evaluate(() => document.documentElement.dataset.mode);
    await f.p.click('#flat g[data-lobe="macd"]'); await f.p.waitForTimeout(500);
    out.flatPick = await f.p.textContent('#body h2');
    if (SHOTS) await f.p.screenshot({ path: SHOTS + '/6_fallback_2d.png' });
    out.flatErrors = f.errs; await f.ctx.close();
  } catch (e) { out.fatal = String(e && e.stack || e); }
  await b.close();
  console.log(JSON.stringify(out));
})();
