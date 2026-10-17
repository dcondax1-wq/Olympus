// usage: NODE_PATH=$(npm root -g) node shot3d.js <size> scene1 scene2 ...   (server on :8799 serving this folder)
const { chromium } = require('playwright');
(async () => {
  const [,, size, ...scenes] = process.argv; const extra = process.env.Q ? '&' + process.env.Q : '', tag = process.env.TAG || '';
  const b = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const p = await b.newPage({ viewport: { width: +size, height: +size } });
  p.on('pageerror', e => console.log('PAGEERR', e.message)); p.on('console', m => { if (m.type() === 'error' || m.type() === 'warning') console.log('CONSOLE', m.text().slice(0, 200)); });
  for (const s of scenes) {
    const t0 = Date.now();
    await p.goto(`http://127.0.0.1:8799/render.html?scene=${s}&size=${size}${extra}`);
    await p.waitForFunction(() => window.__done === true, null, { timeout: 180000 });
    await p.screenshot({ path: `out/${s}${tag}_${size}.png` });
    console.log(s, size, ((Date.now() - t0) / 1000).toFixed(1) + 's');
  }
  await b.close();
})();
