// Screenshot one or more fx views from dev.html.  NODE_PATH=$(npm root -g) node devshot.js <view> [width] [height] [wait_ms] [out.png] [query]
const { chromium } = require('playwright');
(async () => {
  const [,, view = 'galaxy', w = '390', h = '360', wait = '4000', out = `dev_${view}.png`, extra = ''] = process.argv;
  const b = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const p = await b.newPage({ viewport: { width: +w, height: +h + 40 }, deviceScaleFactor: 2 });
  const errs = []; p.on('pageerror', e => errs.push('PAGEERR ' + e.message)); p.on('console', m => { if (['error', 'warning'].includes(m.type())) errs.push(m.type() + ' ' + m.text().slice(0, 300)); });
  await p.goto(`http://127.0.0.1:8797/fx/dev.html?view=${view}&h=${h}&${extra}`);
  await p.waitForFunction(() => window.__ready === true, null, { timeout: 60000 }).catch(() => errs.push('not ready'));
  await p.waitForTimeout(+wait);
  await p.screenshot({ path: out });
  console.log(errs.join('\n') || 'no errors'); await b.close();
})();
