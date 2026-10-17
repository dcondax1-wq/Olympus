// usage: NODE_PATH=$(npm root -g) node shot.js <size> 'scene[?k=v&...]' ...   (static server on :8799 serving this folder)
// writes out/<scene><TAG>_<size>.png ; TAG env adds a suffix
const { chromium } = require('playwright');
(async () => {
  const [,, size, ...specs] = process.argv; const tag = process.env.TAG || '';
  const b = await chromium.launch({ args: ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const p = await b.newPage({ viewport: { width: +size, height: +size } });
  p.on('pageerror', e => console.log('PAGEERR', e.message));
  p.on('console', m => { if (m.type() === 'error' || m.type() === 'warning') console.log('CONSOLE', m.text().slice(0, 400)); });
  try {
    for (const spec of specs) {
      const [s, extra = ''] = spec.split('?'); const t0 = Date.now();
      await p.goto(`http://127.0.0.1:8799/render.html?scene=${s}&size=${size}${extra ? '&' + extra : ''}`);
      await p.waitForFunction(() => window.__done, null, { timeout: 300000 });
      const name = (process.env.NAME || s) + tag;
      await p.screenshot({ path: `out/${name}_${size}.png`, timeout: 240000 });
      console.log(name, size, ((Date.now() - t0) / 1000).toFixed(1) + 's');
    }
  } finally { await b.close(); }
})();
