// Inject a failure after a city has opened; exercise the actual recovery function
// without creating a WebGL context or depending on a browser test runner.
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
const dir = new URL('../tools/web_public/cities/', import.meta.url);
const source = await readFile(new URL('app.js', dir), 'utf8');
const start = source.indexOf('function fallbackList(why) {');
const end = source.indexOf('\nasync function boot()', start);
assert.ok(start >= 0 && end > start);
const elements = new Map();
for (const id of ['#loading','#qB','#photoB','#backB','#readB','#title','#atlas']) {
  const flags = new Set(id === '#atlas' ? ['behind'] : []);
  elements.set(id, { hidden:false, disabled:false, textContent:'', removed:false,
    classList:{ add:c=>flags.add(c), remove:c=>flags.delete(c), contains:c=>flags.has(c) },
    remove(){this.removed=true;} });
}
const bodyFlags = new Set(['photo']), document = { body:{dataset:{ mode:'city', ready:'true' },classList:{remove:c=>bodyFlags.delete(c)}} };
const sheetFlags = new Set(['on']), sheet = {classList:{remove:c=>sheetFlags.delete(c)}}, nightButton = {hidden:false};
const tagEl = {style:{display:'block'}};
const S = {mode:'city',cur:{spec:{id:'trades-city'}},sheet:'building',photo:true,tour:true,specs:[{dataset:'offline'}],ready:true};
let mounted, ready = 0;
const make = new Function('$','S','document','sheet','nightButton','tagEl','mountWorld','openNestedCity','dsNow','summary','plain','O','DATASETS','realDs',
  source.slice(start,end) + '\nreturn fallbackList;');
const fallbackList = make(id=>elements.get(id),S,document,sheet,nightButton,tagEl,(specs,options)=>{mounted={specs,options};},()=>{},()=>null,()=>null,String,()=>({ready(){ready++;}}),{offline:{remote:true}},async()=>null);
fallbackList('Renderer stopped');
assert.equal(S.mode,'hub'); assert.equal(S.cur,null); assert.equal(S.sheet,null);
assert.equal(document.body.dataset.mode,'hub'); assert.equal(document.body.dataset.ready,'fallback');
assert.ok(!bodyFlags.has('photo') && !sheetFlags.has('on'));
assert.ok(!elements.get('#atlas').classList.contains('behind'));
assert.equal(mounted.options.fallback,true); assert.equal(ready,1);
assert.ok(elements.get('#backB').hidden && elements.get('#readB').hidden && nightButton.hidden);
const css = await readFile(new URL('world.css',dir),'utf8');
assert.match(css,/\.world-lobby\.fallback\{[^}]*overflow:auto;touch-action:pan-y/);
assert.match(css,/@media\(max-width:600px\)[\s\S]*?\.atlas-city-list\{grid-template-columns:1fr\}/);
console.log('PASS: city-mode render failure resets occluding UI and mounts a scrollable, interactive atlas for a narrow phone.');
