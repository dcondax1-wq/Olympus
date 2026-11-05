// Exercise the generated SVG geometry without a browser/GPU. Phone interaction
// and the actual rendered appearance still require a separate visual check.
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { WORLDS } from '../tools/web_public/cities/world.js';
import { cityRoutes } from '../tools/web_public/cities/routes.js';
const dir = new URL('../tools/web_public/cities/', import.meta.url);
const source = await readFile(new URL('world.js', dir), 'utf8');
const cfg = JSON.parse(await readFile(new URL('cities.json', dir), 'utf8'));
const start = source.indexOf('function worldMap(specs) {'), end = source.indexOf('\nexport function mountWorld', start);
assert.ok(start >= 0 && end > start);
const svgNode = (tag, attrs = {}) => ({ tag, attrs, children: [], classList:{add(){}}, append(...nodes){this.children.push(...nodes);}, setAttribute(k,v){this.attrs[k]=v;} });
const worldMap = new Function('svgNode','WORLDS','skyline','cityRoutes',source.slice(start,end)+'\nreturn worldMap;')(svgNode,WORLDS,()=>svgNode('svg'),cityRoutes);
const map = worldMap(cfg.cities);
const paths = map.children.filter(x => x.tag === 'path' && x.attrs.opacity === '.3' && x.attrs['vector-effect'] === 'non-scaling-stroke');
const bridges = map.children.filter(x => x.tag === 'path' && x.attrs.opacity === '.62' && x.attrs['vector-effect'] === 'non-scaling-stroke');
const nodes = map.children.filter(x => x.tag === 'circle' && x.attrs['vector-effect'] === 'non-scaling-stroke');
assert.equal(paths.length, WORLDS.length, 'one route mesh per world');
assert.equal(nodes.length,cfg.cities.length, 'each city has a visible node');
assert.equal(bridges.length,WORLDS.length,'one prominent bridge per world');
assert.ok(paths.every(p => Number(p.attrs['stroke-width']) >= 1.2 && Number(p.attrs.opacity) <= .35),'city routes are legible without washing out the map');
assert.ok(bridges.every(p => Number(p.attrs['stroke-width']) >= 2 && Number(p.attrs.opacity) >= .6));
assert.ok(nodes.every(p => Number(p.attrs.r) >= 3 && Number(p.attrs['stroke-width']) > 0));
assert.ok(WORLDS.slice(3).every(w => w[4] <= 300),'bottom hub labels keep margin inside the viewBox');
assert.ok(WORLDS.filter(w => w[3] > 400).every(w => w[3] <= 510),'right hub skylines keep margin at 390px');
assert.match(map.attrs['aria-label'],/decorative navigation routes/);
const [app, recovery, html] = await Promise.all(['app.js','atlas-entry.js','index.html'].map(n => readFile(new URL(n,dir),'utf8')));
assert.ok(app.includes("./world.js?v=w2") && recovery.includes("./world.js?v=w2"), 'both entry paths request the updated map');
assert.ok(html.includes("./app.js?v=o12") && html.includes("./atlas-entry.js?v=a2") && html.includes("./world.css?v=w2"), 'entry caches refresh with the map and hub panel');
const scene = await readFile(new URL('scene.js',dir),'utf8');
assert.ok(app.includes("./scene.js?v=w4") && scene.includes("./shaders.js?v=s3") && scene.includes("./metropolis.js?v=m2"), 'night city modules refresh through the entry chain');
const worldCss = await readFile(new URL('world.css',dir),'utf8');
assert.match(html,/body\[data-mode=hub\]\[data-ready=true\] \.atlas[^{}]*\{display:none\}/,
  'boot atlas cannot cover the mounted hub portals at 390px');
assert.match(worldCss,/\.atlas-featured\{[^}]*pointer-events:auto\}/,
  'featured hub portals remain tappable');
assert.match(html,/body\[data-mode=hub\] #labels\{display:none\}/, 'projected city labels cannot obscure the hub hero');
assert.match(worldCss,/\.world-lobby:not\(\.fallback\) \.atlas-hero\{[^}]*background:linear-gradient/, 'phone hero has a night panel behind route lights');
console.log(`PASS: ${nodes.length} phone-scaled city nodes and ${paths.length} high-contrast route meshes in the fallback SVG.`);
