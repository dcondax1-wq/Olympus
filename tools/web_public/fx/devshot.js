// Screenshot fx views from dev.html (Playwright + SwiftShader).
//   NODE_PATH=$(npm root -g) node devshot.js <view> [width] [height] [wait_ms] [out.png] [query]
//   NODE_PATH=$(npm root -g) node devshot.js --batch shots.json      one browser for many shots:
//     [{ "view": "constellation", "w": 390, "h": 360, "wait": 4000, "out": "a.png", "query": "runs=150",
//        "tap": [x, y] | "tapItem" (taps the first pickable item: window.__view.devTapPoint()), "shots": [[ms, "b.png"], ...] }]
//   Prints console errors / warnings, the picked row after a tap and the view's draw calls per frame.
const { chromium } = require('playwright');
const fs = require('fs');
async function shot(b, o) {
  const { view = 'galaxy', w = 390, h = 360, wait = 4000, out = `dev_${view}.png`, query = '' } = o;
  const p = await b.newPage({ viewport: { width: +w, height: +h + 40 }, deviceScaleFactor: o.dpr || 2, hasTouch: !!o.touch, isMobile: !!o.touch });
  const errs = []; p.on('pageerror', e => errs.push('PAGEERR ' + e.message)); p.on('console', m => { if (['error', 'warning'].includes(m.type())) errs.push(m.type() + ' ' + m.text().slice(0, 300)); });
  await p.goto(`http://127.0.0.1:8797/fx/dev.html?view=${view}&h=${h}&${query}`);
  await p.waitForFunction(() => window.__ready === true, null, { timeout: 60000 }).catch(() => errs.push('not ready'));
  let t = 0;
  for (const [ms, file] of (o.shots || [])) { await p.waitForTimeout(ms - t); t = ms; await p.screenshot({ path: file }); }
  await p.waitForTimeout(Math.max(0, +wait - t));
  let info = '';
  if (o.tap) {
    let pt = o.tap;
    if (pt === 'tapItem') pt = await p.evaluate(() => window.__view?.devTapPoint?.() || null);
    if (pt) {
      const box = await p.evaluate(() => { const r = document.getElementById('box').getBoundingClientRect(); return [r.left, r.top]; });
      if (o.touch) await p.touchscreen.tap(box[0] + pt[0], box[1] + pt[1]); else await p.mouse.click(box[0] + pt[0], box[1] + pt[1]);
      await p.waitForTimeout(o.afterTap || 900);
      info += ' tap@' + pt.map(v => Math.round(v)).join(',') + ' picked=' + (await p.evaluate(() => JSON.stringify(window.__picked)))?.slice(0, 140);
    } else info += ' no tap point';
  }
  if (o.hover) {
    const box = await p.evaluate(() => { const r = document.getElementById('box').getBoundingClientRect(); return [r.left, r.top]; });
    await p.mouse.move(box[0] + o.hover[0], box[1] + o.hover[1]); await p.waitForTimeout(700);
  }
  const calls = await p.evaluate(() => { const v = window.__view; return v ? v.renderer.info.render.calls + ' calls ' + v.renderer.info.render.points + ' pts ' + v.renderer.info.render.triangles + ' tris' : 'no view'; });
  await p.screenshot({ path: out });
  console.log(out + ': ' + calls + info + '\n  ' + (errs.join('\n  ') || 'no errors'));
  await p.close();
}
(async () => {
  const args = process.argv.slice(2);
  const list = args[0] === '--batch' ? JSON.parse(fs.readFileSync(args[1], 'utf8'))
    : [{ view: args[0] || 'galaxy', w: args[1] || 390, h: args[2] || 360, wait: args[3] || 4000, out: args[4], query: args[5] || '' }];
  const b = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  try { for (const o of list) await shot(b, o); } finally { await b.close(); }
})();
