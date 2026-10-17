// Bundle the 3D / particle effects into one ES module for both dashboards.
//   cd tools/web_public/fx && npm install && npm run build
// Outputs: tools/web_public/fx.js (phone dashboard, published by the cloud monitor) and web_next/js/fx.js (PC dashboard).
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
const v = createHash('sha1').update(readFileSync(out)).digest('hex').slice(0, 8);
const stamp = (file, re, rep) => {
  const p = path.join(root, file), s = readFileSync(p, 'utf8'), t = s.replace(re, rep);
  if (!re.test(s)) throw new Error('version stamp not found in ' + file);
  if (t !== s) writeFileSync(p, t);
};
stamp('tools/web_public/index.html', /const FXV = '?[\w]*'?;/, `const FXV = '${v}';`);
stamp('web_next/js/next/fx3d.js', /\/js\/fx\.js\?v=[\w]*/, `/js/fx.js?v=${v}`);
console.log(`fx.js ${(statSync(out).size / 1024).toFixed(0)} KB, v=${v} -> tools/web_public/fx.js + web_next/js/fx.js`);
