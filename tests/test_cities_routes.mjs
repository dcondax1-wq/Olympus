import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { cityRoutes } from '../tools/web_public/cities/routes.js';

const cfg = JSON.parse(await readFile(new URL('../tools/web_public/cities/cities.json', import.meta.url), 'utf8'));
const worlds = [...new Set(cfg.cities.map(c => c.group))].map(key => ({ key }));
const islands = cfg.cities.map((c, i) => ({ i, cont: c.group }));
const graph = cityRoutes(islands, worlds);
assert.deepEqual(cityRoutes(islands, worlds), graph, 'route layout is deterministic');
const atlasMembers = ['atlas-ema-city', 'atlas-macd-city', 'atlas-sr-city'];
assert.ok(islands.length >= 170 + atlasMembers.length, 'original catalogue plus three ATLAS member Cities');
for (const id of atlasMembers) assert.ok(cfg.cities.some(city => city.id === id), `${id} remains on the graph`);
assert.equal(graph.bridges.length, worlds.length, 'all six worlds have a bridge');
assert.ok(graph.links.length < islands.length * 2, 'bounded route and vertex budget');
const seenEdges = new Set(), adj = islands.map(() => []);
for (const [a, b] of graph.links) {
  assert.ok(Number.isInteger(a) && Number.isInteger(b) && a !== b && a >= 0 && b >= 0 && a < islands.length && b < islands.length);
  const key = [a, b].sort((x, y) => x - y).join(':');
  assert.ok(!seenEdges.has(key), 'no duplicate route'); seenEdges.add(key);
  adj[a].push(b); adj[b].push(a);
}
const reached = new Set([0]), queue = [0];
for (const i of queue) for (const next of adj[i]) if (!reached.has(next)) { reached.add(next); queue.push(next); }
assert.equal(reached.size, islands.length, 'every city belongs to one connected navigable world');
assert.ok(adj.every(a => a.length), 'every city has a lightway');
for (const [a, b] of graph.bridges) assert.notEqual(islands[a].cont, islands[b].cont, 'bridges cross worlds');
assert.ok(graph.links.length * 12 * 2 < 7000, 'high-tier route segment budget');
console.log(`PASS: ${reached.size} cities, ${worlds.length} worlds and ${graph.links.length} deterministic bounded routes form one network.`);
