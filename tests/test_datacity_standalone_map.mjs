import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const html = fs.readFileSync('tools/web_public/datacity/map.html', 'utf8');
const index = fs.readFileSync('tools/web_public/datacity/index.html', 'utf8');
const city = fs.readFileSync('tools/web_public/datacity/city.js', 'utf8');
const code = html.match(/<script>([\s\S]*?)<\/script>/)?.[1];
assert.ok(code, 'standalone map has its own classic script');
const context = vm.createContext({ URLSearchParams, URL, location: { search: '', href: 'https://example.test/datacity/map.html' } });
vm.runInContext(code, context);
const nine = ['times','confluences','week','seasons','volatility','gaps','orange','esnq','while'];
const sample = {
  summary: { guard: { tried: 114200, tested: 32164, districts: Object.fromEntries(nine.map((key, i) => [key,{tested:i+1,gold:0}])) } },
  sections: nine.map((key) => ({key,name:key.toUpperCase()})),
  buildings: [{id:'asia-long',d:'times',lab:'Asia long',cls:'green',e:12,n:45}],
  dict: { trigs:[['sweep','prior low sweep',1]], wins:['asia'], win_lab:['Asia'], districts:nine, fams:[], any:'Any time' },
  skyline: { cols:['t','w','k1','k2','d','cls','e','n'], rows:[[0,0,-1,-1,1,0,7,60]] },
};

test('all city network routes stay under the GitHub Pages project base', () => {
  const routes = ['../cities/', './', '../kalshicity/'];
  const base = new URL('https://example.github.io/nq-dashboard/datacity/');
  for (const route of routes) {
    assert.ok(new URL(route, base).pathname.startsWith('/nq-dashboard/'), route + ' escapes the project base');
    assert.ok(index.includes('href="' + route + '"'), '3D page missing ' + route);
    assert.ok(html.includes('href="' + route + '"'), '2D map missing ' + route);
    assert.ok(city.includes("'" + route + "'"), 'no-WebGL fallback missing ' + route);
  }
  assert.match(index, /city\.js\?v=dcgfx2/, 'updated fallback script cache key');
  assert.doesNotMatch(index + html, /href="\/(?:cities|datacity|kalshicity)\//, 'no domain-root city links');
});

test('standalone route has no WebGL, module, or Three dependency', () => {
  assert.doesNotMatch(html, /type=["']module|three\.js|three\.module|WebGLRenderingContext|import\s+.*from/);
  assert.match(index, /href="\.\/map\.html" aria-label="Map view without 3D"/);
  assert.match(html, /id="back3d">Try 3D/);
  assert.match(index, /\.cams button,\.cams a\{width:56px;min-height:44px/);
});
test('the nine research districts and their tested counts render from data', () => {
  const sections = vm.runInContext('districtView(city)', vm.createContext({ city:sample, ...context }));
  assert.equal(sections.length, 9);
  assert.equal(sections[0].key, 'times');
  assert.equal(sections[8].tested, 9);
});
test('search covers rich cards and compact skyline records', () => {
  context.city = sample;
  const rich = vm.runInContext("results(city, 'times', 'Asia long')", context);
  const compact = vm.runInContext("results(city, 'confluences', 'prior low sweep')", context);
  assert.equal(rich.length, 1);
  assert.equal(compact.length, 1);
  assert.equal(compact[0].n, 60);
});
test('bundled fixture supplies all nine districts and searchable skyline records', () => {
  context.fixture = JSON.parse(fs.readFileSync('tools/web_public/datacity/fixture.json', 'utf8'));
  assert.equal(vm.runInContext('districtView(fixture).length', context), 9);
  assert.ok(vm.runInContext("results(fixture, 'times', 'Asia').length", context) > 0);
  assert.ok(vm.runInContext("results(fixture, 'week', 'Thursday').length", context) > 0);
});
test('missing live data falls back to bundled fixture, explicit demo skips live', async () => {
  const calls = [];
  const fetcher = async (path) => {
    calls.push(path);
    if (path === './city.json') throw Error('offline');
    return { ok:true, json: async () => sample };
  };
  context.fetcher = fetcher;
  const result = await vm.runInContext('readCity(fetcher, false)', context);
  assert.equal(result.demo, true);
  assert.deepEqual(calls, ['./city.json','./fixture.json']);
  calls.length=0;
  const demo = await vm.runInContext('readCity(fetcher, true)', context);
  assert.equal(demo.demo, true);
  assert.deepEqual(calls, ['./fixture.json']);
});
