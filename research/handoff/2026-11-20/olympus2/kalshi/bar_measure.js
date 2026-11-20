// node measure.js <tag> <outdir>   (server on 127.0.0.1:8765 serving tools/web_public)
const { chromium } = require('playwright');
const fs = require('fs');
const tag = process.argv[2] || 'before';
const out = process.argv[3] || '.';
const PAGES = (process.argv[4] || 'dionysus,sibyl,kalshicity').split(',');
const BASE = 'http://127.0.0.1:8765/';

async function audit(page) {
  return page.evaluate(() => {
    const vis = (el) => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el); return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
    const name = (el) => (el.getAttribute('aria-label') || el.getAttribute('title') || el.textContent || el.getAttribute('aria-labelledby') && (document.getElementById(el.getAttribute('aria-labelledby')) || {}).textContent || (el.querySelector('img[alt]') || {}).alt || '').trim();
    const ctrls = [...document.querySelectorAll('a[href],button,input,select,summary,[role=button]')].filter(vis);
    const unnamed = ctrls.filter((el) => { if (el.tagName === 'INPUT' || el.tagName === 'SELECT') { return !(el.labels && el.labels.length) && !el.getAttribute('aria-label'); } return !name(el); }).map((e) => e.outerHTML.slice(0, 90));
    const tiny = ctrls.filter((el) => { const r = el.getBoundingClientRect(); return r.height < 44 || r.width < 44; }).map((e) => { const r = e.getBoundingClientRect(); return (e.id || e.tagName.toLowerCase() + '.' + (e.className || '') + ':' + (e.textContent || '').trim().slice(0, 20)) + ' ' + Math.round(r.width) + 'x' + Math.round(r.height); });
    const noalt = [...document.querySelectorAll('img')].filter((i) => !i.hasAttribute('alt')).length;
    const hs = [...document.querySelectorAll('h1,h2,h3,h4,h5,h6')].filter(vis).map((h) => +h.tagName[1]);
    let jumps = 0; for (let i = 1; i < hs.length; i++) if (hs[i] > hs[i - 1] + 1) jumps++;
    const h1 = hs.filter((x) => x === 1).length;
    const hscroll = document.documentElement.scrollWidth > window.innerWidth + 1;
    const blurs = [...document.querySelectorAll('*')].filter((el) => { const s = getComputedStyle(el); const b = s.backdropFilter || s.webkitBackdropFilter; return b && b !== 'none' && vis(el); }).length;
    const status = (document.getElementById('status') || document.getElementById('vText') || {}).textContent || '';
    const blank = (document.body.innerText || '').trim().length < 40;
    return { unnamed, tiny, noalt, headingJumps: jumps, h1, hscroll, blurs, status: status.trim().slice(0, 140), blank, archive: !!document.querySelector('.archive-banner') };
  });
}

async function run(br, app, mode) {
  const ctx = await br.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: mode === 'normal' ? 2 : 1, isMobile: true, hasTouch: true, colorScheme: mode === 'light' ? 'light' : 'dark', serviceWorkers: 'block' });
  const page = await ctx.newPage();
  const errs = [], fails = [];
  page.on('pageerror', (e) => errs.push('pageerror: ' + e.message.slice(0, 160)));
  page.on('console', (m) => { if (m.type() === 'error') errs.push('console: ' + m.text().slice(0, 160)); });
  page.on('response', (r) => { if (r.status() >= 400) fails.push(r.status() + ' ' + r.url().replace(BASE, '')); });
  page.on('requestfailed', (r) => { const u = r.url(); if (u.startsWith(BASE)) fails.push('failed ' + u.replace(BASE, '')); });
  await page.route('**/*', (route) => {
    const u = route.request().url();
    if (!u.startsWith(BASE)) return route.abort();
    if (mode === 'nodata' && /\.json(\?|$)/.test(u) && !/manifest|jarvis\.json/.test(u)) return route.fulfill({ status: 404, body: 'nope' });
    if (mode === 'junk' && /\.json(\?|$)/.test(u) && !/manifest|jarvis\.json/.test(u)) return route.fulfill({ status: 200, contentType: 'application/json', body: '{"oops": [1,2' });
    return route.continue();
  });
  await page.addInitScript(() => { window.__lt = []; try { new PerformanceObserver((l) => { for (const e of l.getEntries()) window.__lt.push(Math.round(e.duration)); }).observe({ type: 'longtask', buffered: true }); } catch (e) {} });
  const t0 = Date.now();
  try { await page.goto(BASE + app + '/', { waitUntil: 'load', timeout: 30000 }); } catch (e) { errs.push('goto: ' + e.message.slice(0, 100)); }
  await page.waitForTimeout(mode === 'normal' ? 4000 : 2500);
  const a = await audit(page);
  const lt = await page.evaluate(() => window.__lt);
  if (mode === 'normal' || mode === 'light') await page.screenshot({ path: `${out}/${app}-${tag}${mode === 'light' ? '-light' : ''}.png` });
  if (mode === 'normal') {
    // offline: reload with every request failing after the HTML
    await ctx.setOffline(false);
  }
  await ctx.close();
  return { app, mode, loadMs: Date.now() - t0, errors: errs, failed: [...new Set(fails)], longTasks: lt.length, longMax: lt.length ? Math.max(...lt) : 0, longSum: lt.reduce((x, y) => x + y, 0), ...a };
}

(async () => {
  const br = await chromium.launch({ args: ['--use-gl=swiftshader', '--enable-webgl', '--ignore-gpu-blocklist', '--enable-unsafe-swiftshader'] });
  const res = [];
  for (const app of PAGES) for (const mode of ['normal', 'light', 'nodata', 'junk']) res.push(await run(br, app, mode));
  await br.close();
  fs.writeFileSync(`${out}/measure-${tag}.json`, JSON.stringify(res, null, 1));
  for (const r of res) console.log(JSON.stringify({ app: r.app, mode: r.mode, err: r.errors.length, fail: r.failed.length, lt: r.longTasks, ltMax: r.longMax, ltSum: r.longSum, unnamed: r.unnamed.length, tiny: r.tiny.length, noalt: r.noalt, hj: r.headingJumps, h1: r.h1, hscroll: r.hscroll, blurs: r.blurs, blank: r.blank, archive: r.archive, status: r.status }));
})();
