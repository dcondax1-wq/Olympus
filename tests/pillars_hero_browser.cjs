// Browser part of tests/test_pillars_hero.py (Node Playwright). argv: <base url> <shots dir or ''>. Prints one JSON line.
const { chromium } = require('playwright');
const [, , BASE, SHOTS] = process.argv;
const out = {};
(async () => {
  const b = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const ctxOf = (o) => b.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: SHOTS ? 2 : 1, hasTouch: true, ...(o || {}) });
  const go = async (ctx, url, wait) => { const p = await ctx.newPage(), errs = []; p.on('pageerror', (e) => errs.push(String(e)));
    await p.route('**/ntfy.sh/**', (r) => r.fulfill({ status: 200, body: '' })); await p.goto(BASE + url, { waitUntil: 'load' }); await p.waitForTimeout(wait || 3500); return { p, errs }; };
  const hero = (p, sel) => p.evaluate((sel) => { const h = document.querySelector(sel); if (!h) return null; const r = h.getBoundingClientRect(), st = h.querySelector('.ph-stage');
    return { top: Math.round(r.top), h: Math.round(r.height), hidden: h.hidden, live: h.dataset.live, mode: st && st.dataset.mode, chips: [...h.querySelectorAll('.pc')].map((a) => a.dataset.p + '|' + a.getAttribute('href').replace(/^.*\/pillars\//, '') + '|' + a.textContent),
      small: [...h.querySelectorAll('a')].filter((a) => { const q = a.getBoundingClientRect(); return q.width && (q.width < 44 || q.height < 44); }).length }; }, sel);
  try {
    // ---- the Olympus Home (gate): the hero band, the toast once, the 6 dashboards still on the first screen ----
    let ctx = await ctxOf();
    let { p, errs } = await go(ctx, '/gate/?fx=3d', 4500);
    out.gate = await hero(p, '#pillarsHero');
    out.gateMore = await p.evaluate(() => Math.round(document.getElementById('moreBtn').getBoundingClientRect().bottom));
    out.toast1 = await p.evaluate(() => { const t = document.getElementById('pillarsNew'); return t ? t.textContent : null; });
    out.gateWide = await p.evaluate(() => document.documentElement.scrollWidth > innerWidth + 1);
    if (SHOTS) await p.screenshot({ path: SHOTS + '/1_home_hero_toast.png' });
    out.gateErrors = errs; await p.close();
    ({ p, errs } = await go(ctx, '/gate/?fx=3d', 3000));
    out.toast2 = await p.evaluate(() => !!document.getElementById('pillarsNew'));
    if (SHOTS) await p.screenshot({ path: SHOTS + '/2_home_hero.png' });
    await p.close(); await ctx.close();
    // ---- Zenith (/): the big hero on Today only ----
    ctx = await ctxOf();
    ({ p, errs } = await go(ctx, '/?fx=3d', 5000));
    out.zen = await hero(p, '#pillarsHero');
    if (SHOTS) await p.screenshot({ path: SHOTS + '/3_zenith_hero.png' });
    await p.evaluate(() => { location.hash = '#/bots'; }); await p.waitForTimeout(500);
    out.zenOther = await p.evaluate(() => document.getElementById('pillarsHero').hidden);
    await p.evaluate(() => { location.hash = '#/today'; }); await p.waitForTimeout(500);
    out.zenBack = await p.evaluate(() => document.getElementById('pillarsHero').hidden);
    out.zenErrors = errs; await ctx.close();
    // ---- NQ: the hero at the top, no toast, no extra data file ----
    ctx = await ctxOf();
    const p3 = await ctx.newPage(), e3 = [], urls = [];
    p3.on('pageerror', (e) => e3.push(String(e))); p3.on('request', (r) => urls.push(r.url()));
    await p3.route('**/ntfy.sh/**', (r) => r.fulfill({ status: 200, body: '' }));
    await p3.goto(BASE + '/nq/?fx=3d'); await p3.waitForTimeout(5000);
    out.nq = await hero(p3, '#pillarsStrip');
    out.nqToast = await p3.evaluate(() => !!document.getElementById('pillarsNew'));
    out.nqData = urls.filter((u) => /\.json(\?|$)/.test(u) && /pillars|lab-data|insights/.test(u)).map((u) => u.replace(BASE, ''));
    if (SHOTS) await p3.screenshot({ path: SHOTS + '/4_nq_hero.png' });
    out.nqErrors = e3; await ctx.close();
    // ---- the Pillars page: the particle field, the lessons panel, the soft tab change, the number glow ----
    ctx = await ctxOf();
    ({ p, errs } = await go(ctx, '/pillars/?fx=3d#lit', 4000));
    out.fx = await p.evaluate(() => { const c = document.getElementById('olyNightFx'); return { canvas: !!c, z: c && getComputedStyle(c).zIndex, pe: c && getComputedStyle(c).pointerEvents, stats: window.__nightfx && window.__nightfx.stats(),
      bodyBg: getComputedStyle(document.body).backgroundColor, top: (() => { const t = document.querySelector('.ptab'); const r = t.getBoundingClientRect(); const e = document.elementFromPoint(r.left + 5, r.top + 5); return e && e.closest('.ptab') ? 'tab' : (e && e.id) || (e && e.tagName); })() }; });
    out.lessons = await p.evaluate(() => { const s = document.getElementById('pLessons'); return s && { sample: !!document.getElementById('pLessonsSample'), lines: s.querySelectorAll('li').length, src: s.querySelector('.src').textContent }; });
    if (SHOTS) await p.screenshot({ path: SHOTS + '/5_pillars_fx.png' });
    if (SHOTS) { await p.evaluate(() => document.getElementById('pLessons').scrollIntoView({ block: 'center' })); await p.waitForTimeout(300); await p.screenshot({ path: SHOTS + '/6_pillars_lessons.png' }); }
    await p.click('.ptab[data-p="blitz"]'); await p.waitForTimeout(100);
    out.swap = await p.evaluate(() => document.getElementById('panel').classList.contains('swap'));
    await p.waitForTimeout(1200);
    out.pulse = await p.evaluate(async () => { const b = document.querySelector('#spans tbody td:nth-child(5)'); const before = window.__livefx ? window.__livefx.pulses() : -1;
      b.textContent = '$1,234'; await new Promise((r) => setTimeout(r, 120)); return { before, after: window.__livefx ? window.__livefx.pulses() : -1, cls: b.className }; });
    await p.evaluate(() => document.dispatchEvent(new Event('visibilitychange')));
    out.fxFrames = await p.evaluate(async () => { const a = window.__nightfx.stats().frames; await new Promise((r) => setTimeout(r, 600)); return [a, window.__nightfx.stats().frames]; });
    out.pillarsErrors = errs; await ctx.close();
    // reduced motion: no particle field, the hero 2D
    ctx = await ctxOf({ reducedMotion: 'reduce' });
    ({ p, errs } = await go(ctx, '/pillars/#lit', 3000));
    out.reduced = await p.evaluate(() => ({ canvas: !!document.getElementById('olyNightFx') }));
    await ctx.close();
    // ---- Accounts: the particle field behind the cards, taps still reach them ----
    ctx = await ctxOf();
    ({ p, errs } = await go(ctx, '/nq/accounts.html?fx=3d', 4500));
    out.acc = await p.evaluate(() => { const c = document.getElementById('olyNightFx'); const card = document.querySelector('.ac-card, h1'); const r = card.getBoundingClientRect();
      const e = document.elementFromPoint(r.left + r.width / 2, r.top + Math.min(20, r.height / 2)); return { canvas: !!c, z: c && getComputedStyle(c).zIndex, hit: e ? e.id === 'olyNightFx' ? 'canvas' : 'content' : null }; });
    if (SHOTS) await p.screenshot({ path: SHOTS + '/7_accounts_fx.png' });
    out.accErrors = errs; await ctx.close();
    // ---- the Strategy Brain still mounts with its pillar sheets + lessons ----
    ctx = await ctxOf();
    ({ p, errs } = await go(ctx, '/cities/mind/', 4000));
    await p.click('button.lobe[data-lobe="blitz"]'); await p.waitForTimeout(600);
    out.brain = await p.evaluate(() => [...document.querySelectorAll('#body h3')].map((h) => h.textContent));
    out.brainErrors = errs; await ctx.close();
  } catch (e) { out.fatal = String(e && e.stack || e); }
  await b.close();
  console.log(JSON.stringify(out));
})();
