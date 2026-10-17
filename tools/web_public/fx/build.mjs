// Bundle the 3D / particle effects into one ES module for both dashboards.
//   cd tools/web_public/fx && npm install && npm run build
// Outputs: tools/web_public/fx.js (phone dashboard, published by the cloud monitor) and web_next/js/fx.js (PC dashboard).
import { build } from 'esbuild';
import { copyFileSync, statSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
const here = path.dirname(fileURLToPath(import.meta.url));
const out = path.join(here, '..', 'fx.js');
await build({ entryPoints: [path.join(here, 'src', 'index.js')], bundle: true, format: 'esm', minify: true, target: ['es2020', 'safari15'],
  outfile: out, legalComments: 'none', logLevel: 'warning' });
copyFileSync(out, path.join(here, '..', '..', '..', 'web_next', 'js', 'fx.js'));
console.log(`fx.js ${(statSync(out).size / 1024).toFixed(0)} KB -> tools/web_public/fx.js + web_next/js/fx.js`);
