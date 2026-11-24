// Browser part of tests/test_pillars.py (Node Playwright). argv: <base url> <shots dir or ''> <post json file>. Prints one JSON line.
// The PC post is the real pc_feed.js with fetchLatest answering the Accounts test's post (+ a glance and the tick line).
const { chromium } = require('playwright');
const fs = require('fs');
const [, , BASE, SHOTS, POSTF] = process.argv;
const POST = JSON.parse(fs.readFileSync(POSTF, 'utf8'));
const REAL = fs.readFileSync(require('path').join(__dirname, '..', 'tools', 'web_public', 'pc_feed.js'), 'utf8');
const STUB = REAL + `\n;(function(){ var P = ${JSON.stringify(POST.post)}; window.PC_FEED.fetchLatest = async function () { return P ? JSON.parse(JSON.stringify(P)) : null; }; })();`;
const AT = '?at=' + encodeURIComponent(POST.at_iso);
const out = {};
(async () => {
  const b = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  async function page(url, wait) {
    const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: SHOTS ? 2 : 1, hasTouch: true });
    const p = await ctx.newPage(), errs = [];
    p.on('pageerror', (e) => errs.push(String(e)));
    await p.route('**/pc_feed.js*', (r) => r.fulfill({ contentType: 'application/javascript', body: STUB }));
    await p.route('**/ntfy.sh/**', (r) => r.fulfill({ status: 200, body: '' }));
    await p.goto(BASE + url, { waitUntil: 'load' });
    if (wait) await p.waitForFunction(() => document.documentElement.dataset.ready === '1', null, { timeout: 30000 });
    await p.waitForTimeout(1800);
    return { p, ctx, errs };
  }
  const wide = (p) => p.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1);
  try {
    // ---- the Pillars page ----
    let { p, ctx, errs } = await page('/pillars/' + AT + '#lit', true);
    out.mode = await p.evaluate(() => document.documentElement.dataset.mode);
    out.stats = await p.evaluate(() => (window.__pillars ? window.__pillars.stats() : null));
    out.tabs = await p.evaluate(() => [...document.querySelectorAll('.ptab')].map((t) => t.dataset.p + ':' + t.querySelector('small').textContent));
    out.lit = await p.evaluate(() => ({ status: document.getElementById('pStatus').textContent, accts: [...document.querySelectorAll('#pAccounts .acct .nm')].map((x) => x.textContent),
      arm: [...document.querySelectorAll('#pAccounts .arm')].map((x) => x.textContent), clock: document.querySelectorAll('#pAccounts .ck').length,
      last: (document.getElementById('pLast') || {}).textContent, spans: document.querySelectorAll('#spans tbody tr').length,
      now: [...document.querySelectorAll('#pChain li.now')].map((x) => x.dataset.step), today: document.querySelectorAll('#pToday .tchip').length }));
    out.tips = await p.evaluate(() => [...document.querySelectorAll('.tip')].map((t) => t.textContent));
    out.wide = await wide(p);
    if (SHOTS) { await p.screenshot({ path: SHOTS + '/1_pillars_390x844.png' }); await p.screenshot({ path: SHOTS + '/2_pillars_lit_full.png', fullPage: true }); }
    await p.click('.ptab[data-p="of"]'); await p.waitForTimeout(400);
    out.of = await p.evaluate(() => ({ ticks: (document.getElementById('pTicks') || {}).textContent || '', designs: [...document.querySelectorAll('.design')].map((d) => d.dataset.d + ':' + d.querySelector('.w').textContent),
      bar: (document.querySelector('#pTicks .bar i') || {}).style ? document.querySelector('#pTicks .bar i').style.width : '', now: [...document.querySelectorAll('#pChain li.now')].map((x) => x.dataset.step),
      hash: location.hash }));
    if (SHOTS) await p.screenshot({ path: SHOTS + '/3_pillars_orderflow_full.png', fullPage: true });
    await p.click('.ptab[data-p="blitz"]'); await p.waitForTimeout(400);
    out.blitz = await p.evaluate(() => ({ status: document.getElementById('pStatus').textContent, arm: [...document.querySelectorAll('#pAccounts .arm')].map((x) => x.textContent),
      spans: [...document.querySelectorAll('#spans tbody tr')].map((r) => r.children[3].textContent), off: document.querySelectorAll('#pChain li.off').length, today: document.getElementById('pToday').textContent }));
    if (SHOTS) await p.screenshot({ path: SHOTS + '/4_pillars_blitz.png', fullPage: true });
    await p.click('.ptab[data-p="atlas"]'); await p.waitForTimeout(400);
    out.atlas = await p.evaluate(() => ({ status: document.getElementById('pStatus').textContent, lobes: document.querySelectorAll('#pChain .lobes div').length, spans: document.querySelectorAll('#spans tbody tr').length }));
    // a tap on a column picks its pillar
    await p.evaluate(() => scrollTo(0, 0)); await p.waitForTimeout(600);
    const pr = await p.evaluate(() => window.__pillars && window.__pillars.project('of'));
    const cr = await p.evaluate(() => { const r = document.getElementById('c').getBoundingClientRect(); return { x: r.left, y: r.top, h: r.height }; });
    if (pr) { await p.mouse.click(cr.x + pr.x, cr.y + pr.y + 60); await p.waitForTimeout(500); out.colPick = await p.evaluate(() => document.getElementById('panel').dataset.p); }
    out.errors = errs; await ctx.close();
    // the 2D fallback + no post at all
    ({ p, ctx, errs } = await page('/pillars/?lite=2d#of', true));
    out.flat = await p.evaluate(() => [document.documentElement.dataset.mode, document.querySelectorAll('#flat .col').length]);
    await p.click('#flat .col[data-p="lit"]'); await p.waitForTimeout(300); out.flatPick = await p.evaluate(() => document.getElementById('panel').dataset.p);
    out.flatErrors = errs; await ctx.close();
    // ---- the NQ page: header link + the 4-chip strip ----
    ({ p, ctx, errs } = await page('/nq/' + AT, false));
    await p.waitForFunction(() => document.querySelectorAll('#pillarsStrip .pc').length === 4, null, { timeout: 20000 }).catch(() => {});
    out.nq = await p.evaluate(() => ({ link: !!document.querySelector('.top a[href="../pillars/"]'), chips: [...document.querySelectorAll('#pillarsStrip .pc')].map((c) => c.dataset.p + ':' + c.querySelector('span').textContent),
      hrefs: [...document.querySelectorAll('#pillarsStrip .pc')].map((c) => c.getAttribute('href').replace(/^.*\/pillars\//, '')) }));
    out.nqWide = await wide(p);
    if (SHOTS) { await p.evaluate(() => document.getElementById('pillarsStrip').scrollIntoView({ block: 'center' })); await p.waitForTimeout(300); await p.screenshot({ path: SHOTS + '/5_nq_pillars_strip.png' }); }
    out.nqErrors = errs; await ctx.close();
    // ---- the Strategy Brain: 4 pillar lobes, research neurons around them ----
    ({ p, ctx, errs } = await page('/cities/mind/' + AT, true));
    out.brain = await p.evaluate(() => ({ stats: window.__mind && window.__mind.stats(), link: !!document.querySelector('.top a[href="../../pillars/"]'),
      chips: [...document.querySelectorAll('button.lobe')].slice(0, 4).map((b) => b.dataset.lobe) }));
    if (SHOTS) await p.screenshot({ path: SHOTS + '/6_brain_pillars.png' });
    await p.click('button.lobe[data-lobe="of"]'); await p.waitForTimeout(600);
    out.brainOf = await p.evaluate(() => ({ h: document.querySelector('#body h2').textContent, ticks: (document.getElementById('pillarTicks') || {}).textContent || '', steps: document.querySelectorAll('#chain li').length }));
    if (SHOTS) await p.screenshot({ path: SHOTS + '/7_brain_orderflow.png' });
    await p.click('button.lobe[data-lobe="atlas"]'); await p.waitForTimeout(500);
    out.brainAtlas = await p.evaluate(() => ({ h: document.querySelector('#body h2').textContent, members: [...document.querySelectorAll('#body .arrows button')].map((b) => b.textContent) }));
    out.brainErrors = errs; await ctx.close();
    // ---- the Research Hub: Pillars filter on both tabs ----
    ({ p, ctx, errs } = await page('/cities/hub.html?pillar=of', false));
    await p.waitForTimeout(800);
    out.hub = await p.evaluate(() => ({ row: [...document.querySelectorAll('#resPil .chip')].map((c) => c.dataset.pil), pressed: (document.querySelector('#resPil [aria-pressed="true"]') || {}).dataset,
      cards: [...document.querySelectorAll('#cards .cd')].map((c) => c.dataset.s), all: window.ResearchHub ? window.ResearchHub.S.data.cards.length : 0,
      allOf: window.ResearchHub ? window.ResearchHub.filtered().every((c) => window.HubPillar.ofCard(c) === 'of') : false }));
    if (SHOTS) { await p.evaluate(() => document.getElementById('resPil').scrollIntoView({ block: 'start' })); await p.evaluate(() => scrollBy(0, -120)); await p.waitForTimeout(300); await p.screenshot({ path: SHOTS + '/8_hub_pillars_filter.png' }); }
    await p.click('#tabs button[data-tab="lab"]'); await p.waitForSelector('#labTable', { timeout: 15000 });
    await p.click('#labPil [data-pil="lit"]'); await p.waitForTimeout(300);
    out.hubLab = await p.evaluate(() => ({ n: document.querySelectorAll('#labTable .lr').length, live: [...document.querySelectorAll('#labTable .lr .ln')].map((x) => x.textContent).filter((t) => /ATLAS/.test(t)).length }));
    await p.click('#labPil [data-pil="blitz"]'); await p.waitForTimeout(300);
    out.hubLabBlitz = await p.evaluate(() => document.querySelectorAll('#labTable .lr').length);
    out.hubWide = await wide(p);
    out.hubErrors = errs; await ctx.close();
  } catch (e) { out.fatal = String(e && e.stack || e); }
  await b.close();
  console.log(JSON.stringify(out));
})();
