// usage: NODE_PATH=$(npm root -g) node svg2png.js <size> <out_dir> file1.svg file2.svg ...
const { chromium } = require('playwright');
const fs = require('fs'), path = require('path');
(async () => {
  const [,, size, outDir, ...files] = process.argv;
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: +size, height: +size } });
  for (const f of files) {
    const svg = fs.readFileSync(f, 'utf8');
    await p.setContent(`<html><body style="margin:0;background:#000"><img src="data:image/svg+xml;base64,${Buffer.from(svg).toString('base64')}" style="width:${size}px;height:${size}px;display:block"></body></html>`);
    await p.waitForTimeout(150);
    const out = path.join(outDir, path.basename(f, '.svg') + `_${size}.png`);
    await p.screenshot({ path: out });
    console.log(out);
  }
  await b.close();
})();
