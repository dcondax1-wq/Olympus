import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { cityResultPage, planCityNetwork } from '../tools/web_public/cities/network-layout.js';
import { cityRoutes } from '../tools/web_public/cities/routes.js?v=r3';
import { mountWorld } from '../tools/web_public/cities/world.js?v=w3';

const GROUPS = {
  trading: ['Trading', '#4f8cff'], research: ['Research', '#a68bff'],
  money: ['Money', '#ff9f43'], kalshi: ['Kalshi', '#ff6b9a'],
  life: ['Life', '#39e59a'], obsidian: ['Obsidian', '#9d8cff'],
};

function catalogue(count = 173) {
  const distribution = [
    ['trading', 78], ['research', 53], ['money', 18],
    ['kalshi', 11], ['life', 8], ['obsidian', 5],
  ].flatMap(([group, total]) => Array.from({ length: total }, () => group)).slice(0, count);
  return distribution.map((group, i) => ({
    id: i === 0 ? 'trades-city' : `city-${i}`,
    name: `City ${i}`,
    group,
    region: `Region ${i % 8}`,
    motto: `Record-backed ${group} skyline`, dataset: `dataset-${i}`, landmark: { label: `Landmark ${i}` },
    palette: { ground: '#101827', accent: GROUPS[group][1] },
  }));
}

test('keeps all 173 entries in a deterministic, HQ-centered network', () => {
  const specs = catalogue();
  const a = planCityNetwork(specs, GROUPS);
  const b = planCityNetwork(specs, GROUPS);
  assert.equal(a.islands.length, 173);
  assert.deepEqual(a.islands.map(({ x, z }) => [x, z]), b.islands.map(({ x, z }) => [x, z]));
  assert.equal(a.islands[a.hqIndex].spec.id, 'trades-city');
  assert.equal(a.islands[a.hqIndex].hq, true);
  assert.equal(a.islands[a.hqIndex].x, 0);
  assert.equal(a.islands[a.hqIndex].z, 0);
  assert.equal(a.districts.length, 6);
  assert.ok(a.radius > 0 && a.radius < 500, `unexpected sprawling map radius: ${a.radius}`);
  assert.ok(a.islands.every((city) => Number.isFinite(city.x) && Number.isFinite(city.z) && city.R > 0));
  assert.equal(a.districts.reduce((sum, district) => sum + district.count, 0), 173);
});

test('places each district capital at its switcher destination and satellites nearby', () => {
  const layout = planCityNetwork(catalogue(), GROUPS);
  for (const district of layout.districts) {
    const capital = layout.islands.find((city) => city.spec.id === district.capitalId);
    assert.ok(capital?.capital, `${district.key} is missing a capital`);
    assert.equal(capital.x, district.x);
    assert.equal(capital.z, district.z);
    assert.ok(layout.islands.filter((city) => city.cont === district.key).length >= 5);
    assert.ok(district.r < 400, `${district.key} satellite ring is too dispersed`);
  }
});

test('falls back to the first real trading city when the preferred HQ is absent', () => {
  const specs = catalogue(12).map((spec) => ({ ...spec, id: spec.id === 'trades-city' ? 'trade-core' : spec.id }));
  const layout = planCityNetwork(specs, GROUPS);
  assert.equal(layout.islands[0].hq, true);
  assert.equal(layout.islands[0].spec.id, 'trade-core');
});

test('routes every catalogue city through a single decorative HQ trunk', () => {
  const layout = planCityNetwork(catalogue(), GROUPS);
  const routes = cityRoutes(layout.islands.map(({ i, cont, hq, capital, x, z }) => ({ i, cont, hq, capital, x, z })), layout.districts);
  assert.equal(routes.hq, layout.hqIndex);
  assert.equal(routes.anchors.length, 6);
  assert.equal(routes.bridges.length, 5);
  const links = Array.from({ length: layout.islands.length }, () => []);
  for (const [a, b] of routes.links) { links[a].push(b); links[b].push(a); }
  const seen = new Set([routes.hq]), queue = [routes.hq];
  while (queue.length) for (const next of links[queue.shift()]) if (!seen.has(next)) { seen.add(next); queue.push(next); }
  assert.equal(seen.size, 173, 'every city is reached from the capital');
  assert.ok(routes.links.length <= 250, 'route count stays comfortably bounded');
});

test('all catalogue IDs are reachable through bounded selector pages', () => {
  const specs = catalogue();
  const walked = [];
  for (let offset = 0; offset < specs.length; offset += 60) walked.push(...cityResultPage(specs, offset, 60));
  assert.deepEqual(walked.map((spec) => spec.id), specs.map((spec) => spec.id));
  assert.ok(cityResultPage(specs, 60, 60).length <= 60);
});

test('real catalogue HQ trunk bridges land on every visible district capital and reach all 173 cities', () => {
  const specs = JSON.parse(readFileSync(new URL('../tools/web_public/cities/cities.json', import.meta.url), 'utf8')).cities;
  assert.equal(specs.length, 173);
  assert.equal(new Set(specs.map((spec) => spec.id)).size, 173, 'real catalogue IDs are unique');
  const layout = planCityNetwork(specs, GROUPS);
  const routes = cityRoutes(layout.islands.map(({ i, cont, hq, capital, x, z }) => ({ i, cont, hq, capital, x, z })), layout.districts);
  const hq = layout.islands.find((city) => city.hq);
  assert.ok(hq, 'the real Trades City headquarters is selected');
  assert.equal(layout.islands[hq.i].spec.id, 'trades-city');
  assert.equal(routes.hq, hq.i);

  const trunkKeys = new Set(routes.bridges.map(([from, to]) => `${from}:${to}`));
  const localLengths = routes.links
    .filter(([from, to]) => !trunkKeys.has(`${from}:${to}`))
    .map(([from, to]) => Math.hypot(
      layout.islands[from].x - layout.islands[to].x,
      layout.islands[from].z - layout.islands[to].z
    ));
  assert.equal(localLengths.length, specs.length - layout.districts.length, 'each district uses a spanning tree');
  const averageLocalLength = localLengths.reduce((sum, length) => sum + length, 0) / localLengths.length;
  assert.ok(averageLocalLength <= 70, `average local route length ${averageLocalLength.toFixed(1)} exceeds the 70-unit budget`);
  assert.ok(Math.max(...localLengths) <= 100, `longest local route ${Math.max(...localLengths).toFixed(1)} exceeds the 100-unit budget`);

  const capitals = layout.districts.map((district) => {
    const capital = layout.islands.find((city) => city.spec.id === district.capitalId);
    assert.ok(capital?.capital, `${district.key} switcher target is its selected capital`);
    return { district, index: capital.i };
  });
  assert.deepEqual(
    capitals.filter(({ district }) => !district.hq).map(({ index }) => index).sort((a, b) => a - b),
    routes.bridges.map(([from, to]) => {
      assert.equal(from, hq.i, 'every trunk starts at HQ');
      return to;
    }).sort((a, b) => a - b),
    'each HQ trunk bridge ends at the capital shown for that district'
  );
  assert.deepEqual(
    routes.anchors.slice().sort((a, b) => a - b),
    capitals.map(({ index }) => index).sort((a, b) => a - b),
    'local route anchors are the selected visible capitals'
  );

  const links = Array.from({ length: specs.length }, () => []);
  for (const [a, b] of routes.links) { links[a].push(b); links[b].push(a); }
  const seen = new Set([hq.i]), queue = [hq.i];
  while (queue.length) for (const next of links[queue.shift()]) if (!seen.has(next)) { seen.add(next); queue.push(next); }
  assert.equal(seen.size, specs.length, 'all real catalogue cities remain connected to HQ');
});

test('Cities app actually renders the planned network and connected selector', () => {
  const app = readFileSync(new URL('../tools/web_public/cities/app.js', import.meta.url), 'utf8');
  const page = readFileSync(new URL('../tools/web_public/cities/index.html', import.meta.url), 'utf8');
  assert.ok(app.includes("import { cityResultPage, planCityNetwork } from './network-layout.js?v=n1';"));
  assert.ok(app.includes('const network = planCityNetwork(S.specs, GROUPS);'));
  assert.ok(app.includes('S.islands = layoutIslands();'));
  assert.ok(app.includes('const routes = cityRoutes(S.islands.map('));
  assert.ok(app.includes('capital: s.capital, x: s.x, z: s.z'), 'the WebGL route builder receives real city coordinates');
  const world = readFileSync(new URL('../tools/web_public/cities/world.js', import.meta.url), 'utf8');
  assert.ok(world.includes('capital, x, z }) => ({ i, cont, hq, capital, x, z })'), 'the fallback route builder receives real city coordinates');
  assert.ok(app.includes('cityResultPage(hit, 0, shown)'));
  assert.ok(app.includes('if (hit.length > shown)'));
  assert.ok(app.includes("S.mode === 'city'"));
  assert.ok(page.includes('id="networkHQ"'));
  assert.ok(page.includes('data-network-district="trading"'));
  assert.ok(page.includes('data-network-district="kalshi"'));
});

test('GPU fallback mounts a connected city SVG and 173 accessible city controls', () => {
  class TextStub {
    constructor(value) { this.nodeType = 3; this.textContent = String(value); }
  }
  class ElementStub {
    constructor(tagName) {
      this.tagName = tagName;
      this.attributes = Object.create(null);
      this.children = [];
      this.style = { setProperty() {} };
      this.hidden = false;
      this._text = '';
      this.classList = {
        add: (...tokens) => { const current = new Set((this.attributes.class || '').split(/\\s+/).filter(Boolean)); tokens.forEach((token) => current.add(token)); this.attributes.class = [...current].join(' '); },
        contains: (token) => (this.attributes.class || '').split(/\\s+/).includes(token),
      };
    }
    setAttribute(name, value) { this.attributes[name] = String(value); }
    getAttribute(name) { return this.attributes[name] ?? null; }
    append(...nodes) { this.children.push(...nodes); }
    appendChild(node) { this.children.push(node); return node; }
    replaceChildren(...nodes) { this.children = []; this.append(...nodes); }
    addEventListener() {}
    set type(value) { this.setAttribute('type', value); }
    set className(value) { this.setAttribute('class', value); }
    get className() { return this.getAttribute('class') || ''; }
    set textContent(value) { this.children = []; this._text = String(value); }
    get textContent() { return this._text + this.children.map((child) => child.textContent || '').join(''); }
  }
  const body = new ElementStub('body');
  const priorDocument = globalThis.document;
  globalThis.document = {
    body,
    querySelector: () => null,
    createElement: (tag) => new ElementStub(tag),
    createElementNS: (_namespace, tag) => new ElementStub(tag),
    createTextNode: (value) => new TextStub(value),
  };
  const descendants = (root) => {
    const all = [];
    const visit = (node) => {
      if (!node || node.nodeType === 3) return;
      all.push(node);
      for (const child of node.children || []) visit(child);
    };
    visit(root);
    return all;
  };
  try {
    const specs = JSON.parse(readFileSync(new URL('../tools/web_public/cities/cities.json', import.meta.url), 'utf8')).cities;
    assert.equal(specs.length, 173);
    assert.equal(new Set(specs.map((spec) => spec.id)).size, 173, 'published IDs are unique');
    const actualCounts = Object.fromEntries(Object.keys(GROUPS).map((group) => [group, specs.filter((spec) => spec.group === group).length]));
    assert.deepEqual(actualCounts, { trading: 78, research: 53, money: 18, kalshi: 11, life: 8, obsidian: 5 });
    const lobby = mountWorld(specs, { fallback: true, onExplore: () => {}, describe: () => ({ demo: true, line: 'Sample record' }) });
    assert.equal(body.children[0], lobby, 'fallback lobby is returned and mounted');
    const nodes = descendants(lobby);
    const map = nodes.find((node) => node.tagName === 'svg' && node.getAttribute('role') === 'img');
    assert.ok(map, 'accessible SVG city map is present');
    assert.match(map.getAttribute('aria-label'), /173 real catalogue cities inside one connected night metropolis/);
    assert.ok(descendants(map).some((node) => node.tagName === 'text' && node.textContent === 'OLYMPUS HQ'), 'real HQ label is rendered');
    const search = nodes.find((node) => node.tagName === 'input' && node.getAttribute('type') === 'search');
    assert.equal(search?.getAttribute('aria-label'), 'Search the city atlas');
    const cityButtons = nodes.filter((node) => node.tagName === 'button' && node.classList.contains('atlas-city'));
    assert.equal(cityButtons.length, 173);
    assert.deepEqual(cityButtons.map((button) => button.getAttribute('data-city-id')), specs.map((spec) => spec.id), 'every real catalog city has its own matching selector control');
    for (const [index, button] of cityButtons.entries()) {
      assert.equal(button.getAttribute('type'), 'button');
      assert.equal(button.getAttribute('aria-label'), `${specs[index].name}. ${GROUPS[specs[index].group][0]} district. ${specs[index].motto}`);
      assert.ok(button.textContent.includes(specs[index].name), `city control ${index} has the real catalog name`);
    }
    assert.equal(nodes.filter((node) => node.tagName === 'button' && node.classList.contains('atlas-filter')).length, 7, 'All + six district filters are present');
  } finally {
    if (priorDocument === undefined) delete globalThis.document;
    else globalThis.document = priorDocument;
  }
});


test('spatial route module uses a fresh cache tag in both WebGL and fallback callers', () => {
  const app = readFileSync(new URL('../tools/web_public/cities/app.js', import.meta.url), 'utf8');
  const world = readFileSync(new URL('../tools/web_public/cities/world.js', import.meta.url), 'utf8');
  assert.ok(app.includes("from './routes.js?v=r3'"), 'the WebGL app fetches the local-route update');
  assert.ok(world.includes("from './routes.js?v=r3'"), 'the GPU fallback fetches the same local-route update');
});

test('in-world app switcher reaches the three reciprocal city routes and stays touch-accessible on mobile', () => {
  const app = readFileSync(new URL('../tools/web_public/cities/app.js', import.meta.url), 'utf8');
  const page = readFileSync(new URL('../tools/web_public/cities/index.html', import.meta.url), 'utf8');
  const navStart = page.indexOf('<nav class="network-bar" id="cityNetwork"');
  const navEnd = page.indexOf('</nav>', navStart);
  assert.ok(navStart >= 0 && navEnd > navStart, 'the switcher is inside the Cities page, not a separate home screen');
  const nav = page.slice(navStart, navEnd + '</nav>'.length);
  assert.ok(nav.includes('id="networkApps"') && nav.includes('aria-label="Open connected city dashboards"') && nav.includes('aria-haspopup="dialog"'),
    'the APPS switcher has an accessible name and opens a dialog');
  assert.ok(app.includes("$('#networkApps').addEventListener('click', openNetworkApps);"), 'APPS invokes the route dialog');
  assert.ok(page.includes('<section class="sheet" id="sheet" role="dialog" aria-labelledby="sheetTitle">'));
  assert.ok(page.includes('body[data-ready=true] .network-bar,body[data-ready=fallback] .network-bar{display:flex}'),
    'the City Network stays exposed in rendered and GPU-fallback states');
  assert.ok(page.includes('.network-key,.network-apps,.network-strip button{flex:0 0 auto;min-height:44px;'),
    'all HQ, district, and APPS controls keep a phone-safe touch height');
  assert.ok(page.includes('.network-strip button{min-width:44px;padding:0 11px}'),
    'every district switch stays at least 44px wide');
  assert.match(page, /@media\(max-width:600px\)[\s\S]*?height:50px[\s\S]*?\.network-key\{width:44px\}/,
    'the phone rail leaves room for 44px controls and keeps HQ phone-safe');
  assert.match(page, /\.network-strip\{[^}]*overflow-x:auto/,
    'district tabs can scroll without pushing APPS off the phone');
  assert.match(page, /@media\(max-width:600px\)[\s\S]*?\.network-apps\{width:50px\}/,
    'APPS remains a fixed-width control at phone sizes');
  assert.ok(page.includes("import('./app.js?v=o18').catch(recover);"), 'the updated controller has a fresh entry cache tag');
  assert.ok(app.includes("const fx = S.stage?.tier?.() || (O() ? O().fx() : 'high')"),
    'the HD/LITE label follows the renderer tier forced by ?q=low');
  assert.ok(page.includes('.pill{min-height:44px'), 'destination links in the dialog retain 44px touch targets');

  const begin = app.indexOf('function openNetworkApps() {');
  const end = app.indexOf('\nfunction syncNetwork()', begin);
  assert.ok(begin >= 0 && end > begin, 'the in-world app switcher has a bounded implementation');
  const node = (tagName, className = '', textContent = '') => ({
    tagName, className, textContent, attributes: Object.create(null), children: [], listeners: Object.create(null),
    append(...children) { this.children.push(...children); },
    setAttribute(name, value) { this.attributes[name] = String(value); },
    addEventListener(type, callback) { this.listeners[type] = callback; },
  });
  const body = node('div');
  let opened = null;
  const openSheet = (view, title, render) => { opened = { view, title }; render(body); };
  const openNetworkApps = new Function('openSheet', 'el', 'S', app.slice(begin, end) + '\nreturn openNetworkApps;');
  openNetworkApps(openSheet, node, { specs: Array.from({ length: 173 }) })();
  assert.deepEqual(opened, { view: 'network', title: 'Connected city apps' });
  const actions = body.children.find((child) => child.className === 'actions');
  assert.ok(actions, 'Data City and Kalshi City appear inside the in-world dialog');
  const links = actions.children.filter((child) => child.tagName === 'a');
  assert.deepEqual(links.map((link) => [link.textContent, link.href, link.attributes['aria-label']]), [
    ['Open Data City', '../datacity/', 'Open Data City'],
    ['Open Kalshi City', '../kalshicity/', 'Open Kalshi City'],
  ]);
  const routes = [
    new URL('./', 'https://olympus.test/cities/').pathname,
    ...links.map((link) => new URL(link.href, 'https://olympus.test/cities/').pathname),
  ];
  assert.deepEqual(routes, ['/cities/', '/datacity/', '/kalshicity/']);
  assert.equal(new Set(routes).size, 3, 'the reciprocal switcher reaches each city exactly once');
  assert.ok(body.children.some((child) => child.tagName === 'button' && child.textContent === 'Browse all 173 cities'),
    'the current Cities route also keeps its paged in-world catalogue available');
});
