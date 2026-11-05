import assert from 'node:assert/strict';
import fs from 'node:fs';
import { Forge } from '../tools/web_public/prometheus/forgecore.js';
import { heatRgb } from '../tools/web_public/prometheus/lineage.js';

const html = fs.readFileSync('tools/web_public/prometheus/index.html','utf8');
const css = fs.readFileSync('tools/web_public/prometheus/forge.css','utf8');
const js = fs.readFileSync('tools/web_public/prometheus/forge.js','utf8');
const data = JSON.parse(fs.readFileSync('tools/web_public/prometheus/forge.json','utf8'));
const F = new Forge(data), g = 0, best = F.best(g), hud = F.hud(g);

assert.match(html,/id="nogl" class="forge-flat"/);
assert.match(html,/forge\.css\?v=f6/);
assert.match(html,/forge\.js\?v=f6/);
for (const cls of ['flat-vault','flat-core','flat-anvil','flat-ingot','flat-summary','flat-lineage','flat-pop','flat-node']) assert.match(css,new RegExp(`\\.${cls}`));
assert.match(css,/data-fx="low"/);
assert.match(css,/data-fx="off"/);
assert.match(css,/prefers-reduced-motion: reduce/);
assert.match(js,/Keep live LIT · no proven replacement/);
assert.match(js,/F\.lineageUpTo\(g\)\.slice\(-5\)/);
assert.match(js,/gen\.slice\(0, 4\)/);
assert.match(js,/renderChips\(\);\s*measureBars\(\);/);
assert.equal(hud.id,best.id);
assert.equal(typeof F.verdict().liveBest,'boolean');
assert.match(heatRgb(F.heat(best.f)),/^rgb\(\d+,\d+,\d+\)$/);
assert.ok(F.lineageUpTo(F.nGens-1).length > 0);

console.log('prometheus fallback: stored generation, verdict, heat and lineage presentation checks pass');
