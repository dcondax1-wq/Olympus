// Bundle the 3D / particle effects into one ES module for both dashboards.
//   cd tools/web_public/fx && npm install && npm run build
// Outputs: tools/web_public/fx.js (phone dashboard, published by the cloud monitor) and web_next/js/fx.js (PC dashboard);
// it also copies tools/web_public/litkit.js (the LIT panels) to web_next/js/litkit.js and tools/web_public/tradechart.js (the
// TradingView-style trade chart) to web_next/js/tradechart.js.
// The bundle's content hash is stamped into both pages' import URL (fx.js?v=<hash>), so a phone's service worker, which
// keeps versioned files forever, fetches the new bundle after every rebuild.
import { build } from 'esbuild';
import { copyFileSync, statSync, readFileSync, writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
const here = path.dirname(fileURLToPath(import.meta.url));
const root = path.join(here, '..', '..', '..');
const out = path.join(here, '..', 'fx.js');
await build({ entryPoints: [path.join(here, 'src', 'index.js')], bundle: true, format: 'esm', minify: true, target: ['es2020', 'safari15'],
  outfile: out, legalComments: 'none', logLevel: 'warning' });
copyFileSync(out, path.join(root, 'web_next', 'js', 'fx.js'));
// the LIT panels (plain ES module, not bundled): one source for both dashboards
copyFileSync(path.join(here, '..', 'litkit.js'), path.join(root, 'web_next', 'js', 'litkit.js'));
// the trade chart (plain ES module, not bundled): one source for both dashboards
copyFileSync(path.join(here, '..', 'tradechart.js'), path.join(root, 'web_next', 'js', 'tradechart.js'));
// deep space + Mission Control (2026-10-29): the CSS sky / glass, the Mission Control styles and renderer, one source each
copyFileSync(path.join(here, '..', 'space.css'), path.join(root, 'web_next', 'css', 'space.css'));
copyFileSync(path.join(here, '..', 'mission.css'), path.join(root, 'web_next', 'css', 'mission.css'));
copyFileSync(path.join(here, '..', 'missioncore.js'), path.join(root, 'web_next', 'js', 'next', 'missioncore.js'));
// Holodeck (2026-10-29): the page UI and its styles, one source each (the 3D scene itself is in this bundle: src/holo.js)
copyFileSync(path.join(here, '..', 'holocore.js'), path.join(root, 'web_next', 'js', 'next', 'holocore.js'));
copyFileSync(path.join(here, '..', 'holo.css'), path.join(root, 'web_next', 'css', 'holo.css'));
const v = createHash('sha1').update(readFileSync(out)).digest('hex').slice(0, 8);
const stamp = (file, re, rep, soft = false) => {
  const p = path.join(root, file), s = readFileSync(p, 'utf8'), t = s.replace(re, rep);
  if (!re.test(s)) { if (soft) { console.warn('version stamp not found in ' + file + ' (skipped)'); return; } throw new Error('version stamp not found in ' + file); }
  if (t !== s) writeFileSync(p, t);
};
if (process.env.STAMP !== '0') {     // STAMP=0 npm run build: bundle only, leave the pages alone (parallel page edits)
  stamp('tools/web_public/index.html', /const FXV = '?[\w]*'?;/, `const FXV = '${v}';`);
  stamp('web_next/js/next/fx3d.js', /\/js\/fx\.js\?v=[\w]*/, `/js/fx.js?v=${v}`);
  // the LIT panels module (litkit.js) gets its own content hash in both pages' import URL
  const lv = createHash('sha1').update(readFileSync(path.join(here, '..', 'litkit.js'))).digest('hex').slice(0, 8);
  stamp('tools/web_public/index.html', /const LKV = '?[\w]*'?;/, `const LKV = '${lv}';`);
  stamp('web_next/js/next/litpages.js', /\.\.\/litkit\.js\?v=[\w]*/, `../litkit.js?v=${lv}`);
  // the trade chart module (tradechart.js): its content hash in the phone page (const TCV) and in every PC page that imports it
  const tv = createHash('sha1').update(readFileSync(path.join(here, '..', 'tradechart.js'))).digest('hex').slice(0, 8);
  stamp('tools/web_public/index.html', /const TCV = '?[\w]*'?;/, `const TCV = '${tv}';`, true);
  // Holodeck: holocore.js + holo.css content hashes in both pages (the phone's service worker keeps versioned files forever),
  // then holo.js's own hash in the phone page's script tag
  const hc = createHash('sha1').update(readFileSync(path.join(here, '..', 'holocore.js'))).digest('hex').slice(0, 8);
  const hs = createHash('sha1').update(readFileSync(path.join(here, '..', 'holo.css'))).digest('hex').slice(0, 8);
  for (const f of ['tools/web_public/holo.js', 'web_next/js/next/holo.js']) {
    stamp(f, /holocore\.js\?v=[\w]*/, `holocore.js?v=${hc}`, true);
    stamp(f, /holo\.css\?v=[\w]*/, `holo.css?v=${hs}`, true);
  }
  const hj = createHash('sha1').update(readFileSync(path.join(here, '..', 'holo.js'))).digest('hex').slice(0, 8);
  stamp('tools/web_public/index.html', /holo\.js\?v=[\w]*/, `holo.js?v=${hj}`, true);
  for (const f of ['web_next/js/next/trades.js', 'web_next/js/next/litpages.js']) {
    try { readFileSync(path.join(root, f)); } catch { continue; }
    stamp(f, /\.\.\/tradechart\.js\?v=[\w]*/g, `../tradechart.js?v=${tv}`, true);
  }
}
console.log(`fx.js ${(statSync(out).size / 1024).toFixed(0)} KB, v=${v} -> tools/web_public/fx.js + web_next/js/fx.js`);
