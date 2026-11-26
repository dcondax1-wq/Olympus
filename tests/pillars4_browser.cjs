// Browser part of tests/test_pillars.py section p (day-pillars4): the pillar DATA page, the Pillars "go deeper" row + crumbs, the Home Today strip,
// the Brain's brain-feed age. Node Playwright; argv: <base url> <shots dir or ''> <post json file>. Prints one JSON line.
// fetchLatest answers the Accounts test's post + a brain feed (bf) + an open ATLAS trade (lite.at).
const { chromium } = require('playwright');
const fs = require('fs');
const [, , BASE, SHOTS, POSTF] = process.argv;
const POST = JSON.parse(fs.readFileSync(POSTF, 'utf8'));
const REAL = fs.readFileSync(require('path').join(__dirname, '..', 'tools', 'web_public', 'pc_feed.js'), 'utf8');
const stub = (post) => REAL + `\n;(function(){ var P = ${JSON.stringify(post)}; window.PC_FEED.fetchLatest = async function () { return P ? JSON.parse(JSON.stringify(P)) : null; }; })();`;
const AT = '?at=' + encodeURIComponent(POST.at_iso);
const out = {};
(async () => {
  const b = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  async function page(url, post, readyWait) {
    const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: SHOTS ? 2 : 1, hasTouch: true });
    const p = await ctx.newPage(), errs = [];
    p.on('pageerror', (e) => errs.push(String(e)));
    await p.route('**/pc_feed.js*', (r) => r.fulfill({ contentType: 'application/javascript', body: stub(post) }));
    await p.route('**/ntfy.sh/**', (r) => r.fulfill({ status: 200, body: '' }));
    await p.addInitScript(() => { try { localStorage.setItem('oly.new.pillars', '1'); } catch (_) {} });
    await p.goto(BASE + url, { waitUntil: 'load' });
    if (readyWait) await p.waitForFunction(() => document.documentElement.dataset.ready === '1', null, { timeout: 40000 });
    await p.waitForTimeout(1500);
    return { p, ctx, errs };
  }
  const wide = (p) => p.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1);
  const all = [];
  try {
    // ---- the LIT data page, live post ----
    let { p, ctx, errs } = await page('/pillars/data.html' + AT + '#lit', POST.post, true);
    out.lit = await p.evaluate(() => {
      const t = (id) => (document.getElementById(id) || {}).textContent || '';
      return { title: t('ttl'), crumbs: (document.querySelector('.crumbs') || {}).textContent || '', back: document.getElementById('back').getAttribute('href'), pill: t('pcPill'), sample: !document.getElementById('sample').hidden,
        status: t('dStatus'), week: t('kWeek'), month: t('kMonth'), win: t('kWin'), pf: t('kPf'), rows: document.querySelectorAll('#dTradeTable tbody tr').length,
        srcs: [...document.querySelectorAll('#dTradeTable tbody tr')].map((r) => r.dataset.src), feed: t('dFeedAge'), feedCls: (document.getElementById('dFeedAge') || {}).className || '',
        setup: t('dSetup'), steps: [...document.querySelectorAll('#dSteps li')].map((x) => x.className + ':' + x.textContent), rej: t('dRejN'), mill: t('dMill'),
        lessons: document.querySelectorAll('#dLessons li').length, sections: [...document.querySelectorAll('#data > section')].map((s) => s.id), tabs: [...document.querySelectorAll('.dtabs a')].map((a) => a.getAttribute('href')),
        spark: ((document.querySelector('#dSpark svg') || {}).outerHTML || '').slice(0, 160) + ' / ' + ((document.querySelector('#dSpark .sx b') || {}).textContent || ''), foot: [...document.querySelectorAll('#dfoot a')].map((a) => a.getAttribute('href')), brainLink: !!document.querySelector('#dNext a.go[href="../brain/#lit"]') };
    });
    out.litWide = await wide(p);
    if (SHOTS) { await p.screenshot({ path: SHOTS + '/05_pillar_data_lit.png' }); await p.screenshot({ path: SHOTS + '/05b_pillar_data_lit_full.png', fullPage: true }); }
    // a tab switches the pillar in place
    await p.click('.dtabs a[href="#atlas"]'); await p.waitForTimeout(500);
    out.atlas = await p.evaluate(() => ({ title: document.getElementById('ttl').textContent, hash: location.hash, rows: document.querySelectorAll('#dTradeTable tbody tr').length, open: (document.getElementById('dOpen') || {}).textContent || '',
      month: (document.getElementById('kMonth') || {}).textContent || '', back: document.getElementById('back').getAttribute('href') }));
    if (SHOTS) await p.screenshot({ path: SHOTS + '/05c_pillar_data_atlas.png' });
    all.push(...errs); await ctx.close();
    // ---- ORDER FLOW data page ----
    ({ p, ctx, errs } = await page('/pillars/data.html' + AT + '#of', POST.post, true));
    out.of = await p.evaluate(() => ({ days: (document.getElementById('kDays') || {}).textContent || '', looks: (document.getElementById('kLooks') || {}).textContent || '', designs: document.querySelectorAll('#dFlow .design').length,
      money: (document.getElementById('dMoney') || {}).textContent || '', trades: !!document.getElementById('dTradeTable'), rej: (document.getElementById('dRejN') || {}).textContent || '' }));
    out.ofWide = await wide(p);
    if (SHOTS) await p.screenshot({ path: SHOTS + '/06_pillar_data_of.png', fullPage: true });
    all.push(...errs); await ctx.close();
    // ---- no post at all: SAMPLE label on the live parts, money still real ----
    ({ p, ctx, errs } = await page('/pillars/data.html' + AT + '#lit', null, true));
    out.none = await p.evaluate(() => ({ sample: !document.getElementById('sample').hidden, pill: document.getElementById('pcPill').textContent, rows: document.querySelectorAll('#dTradeTable tbody tr').length,
      feed: (document.querySelector('#dNext .fage') || {}).textContent || '' }));
    all.push(...errs); await ctx.close();
    // ---- the Pillars page: crumbs, back to Home, the go-deeper row ----
    ({ p, ctx, errs } = await page('/pillars/' + AT + '#atlas', POST.post, true));
    out.pillars = await p.evaluate(() => ({ back: document.querySelector('.top .back').getAttribute('href'), crumbs: (document.querySelector('.top .crumbs') || {}).textContent || '',
      go: [...document.querySelectorAll('#pGo a')].map((a) => a.getAttribute('href')), foot: (document.getElementById('footData') || {}).getAttribute('href') }));
    if (SHOTS) { await p.evaluate(() => { const e = document.getElementById('panel'); window.scrollTo(0, e.getBoundingClientRect().top + scrollY - 130); }); await p.waitForTimeout(300); await p.screenshot({ path: SHOTS + '/04_pillars_panel_atlas.png' }); }
    all.push(...errs); await ctx.close();
    // ---- Home: the Today strip ----
    ({ p, ctx, errs } = await page('/gate/' + AT, POST.post, false));
    await p.waitForFunction(() => { const s = document.getElementById('todayStrip'); return s && s.dataset.ready === 'post'; }, null, { timeout: 30000 }).catch(() => {});
    out.home = await p.evaluate(() => {
      const s = document.getElementById('todayStrip'), r = (q) => { const e = document.querySelector(q); return e ? e.getBoundingClientRect() : null; };
      return { ready: s && s.dataset.ready, cells: s ? [...s.querySelectorAll('a')].map((a) => a.textContent) : [], hrefs: s ? [...s.querySelectorAll('a')].map((a) => new URL(a.href).pathname + new URL(a.href).hash) : [],
        h: s ? Math.round(s.getBoundingClientRect().height) : 0, stripBottom: s ? Math.round(s.getBoundingClientRect().bottom) : 0, q: Math.round(r('#q').top), grid: Math.round(r('.g-agrid').top), more: Math.round(r('#moreBtn').bottom) };
    });
    out.homeWide = await wide(p);
    if (SHOTS) await p.screenshot({ path: SHOTS + '/03_home.png' });
    all.push(...errs); await ctx.close();
    // ---- the Brain: the brain feed's age on Next trade ----
    ({ p, ctx, errs } = await page('/brain/' + AT + '&lite=2d#lit', POST.post, true));
    out.brain = await p.evaluate(() => ({ feed: (document.getElementById('rFeedAge') || {}).textContent || '', cls: (document.getElementById('rFeedAge') || {}).className || '',
      setup: (document.querySelector('#rNext .setup') || {}).textContent || '', steps: [...document.querySelectorAll('#rChain li')].map((x) => x.className + ':' + x.textContent),
      src: [...document.querySelectorAll('#rNext .src')].map((x) => x.textContent).join(' '), back: document.getElementById('back').getAttribute('href'), crumb: document.getElementById('crN').textContent, data: (document.getElementById('rData') || { getAttribute: () => '' }).getAttribute('href'), top: getComputedStyle(document.querySelector('.top')).backgroundColor }));
    if (SHOTS) { await p.evaluate(() => { const e = document.getElementById('room'); window.scrollTo(0, e.getBoundingClientRect().top + scrollY - 70); }); await p.waitForTimeout(300); await p.screenshot({ path: SHOTS + '/08_brain_lit.png' }); }
    all.push(...errs); await ctx.close();
  } catch (e) { out.fatal = String(e && e.stack || e).slice(0, 600); }
  out.errors = all;
  await b.close();
  console.log(JSON.stringify(out));
})();
