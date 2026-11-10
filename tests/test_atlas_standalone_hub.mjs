import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', 'tools', 'web_public');
const html = fs.readFileSync(path.join(root, 'atlas', 'index.html'), 'utf8');
const css = fs.readFileSync(path.join(root, 'atlas', 'atlas.css'), 'utf8');
const atlas = fs.readFileSync(path.join(root, 'atlas', 'atlas.js'), 'utf8');
const hub = fs.readFileSync(path.join(root, 'atlas', 'hub.js'), 'utf8');

test('standalone Atlas presents one Olympus command center', () => {
  assert.match(html, /Command center \/ Atlas/);
  assert.match(html, /Every arena\.<br><em>One command center\.<\/em>/);
  assert.match(html, /The full directory/);
  assert.match(html, /hub\.js\?v=1/);
  assert.match(html, /atlas\.css\?v=8/);
  assert.equal((html.match(/data-jump-filter=/g) || []).length, 5);
  assert.equal((html.match(/class="command-glass"/g) || []).length, 1);
});

test('directory keeps every arena discoverable and routes stay in the project', () => {
  for (const zone of ['market', 'research', 'risk', 'command', 'life']) {
    assert.match(atlas, new RegExp(`id:'${zone}'`));
    assert.match(html, new RegExp(`data-filter="${zone}"`));
  }
  assert.match(atlas, /const link = \(a\) => '\.\.\/'/);
  const hrefs = [...html.matchAll(/<a[^>]+href="([^"]+)"/g)].map((match) => match[1]);
  assert.ok(hrefs.length >= 7);
  assert.ok(hrefs.every((href) => href.startsWith('../') || href.startsWith('./') || href.startsWith('#')));
  assert.doesNotMatch(html + hub, /https?:\/\//);
});

test('phone controls remain large and the command grid is responsive', () => {
  assert.match(css, /\.home\{[^}]*min-height:44px/);
  assert.match(css, /\.search input\{height:100%;min-height:44px/);
  assert.match(css, /\.filters button\{[^}]*min-height:44px/);
  assert.match(css, /\.star\{[^}]*width:44px;height:44px/);
  assert.match(hub, /data-focus-search/);
  assert.match(hub, /data-jump-filter/);
  assert.match(hub, /prefers-reduced-motion: reduce/);
});

test('hub is read-only and does not introduce order or account actions', () => {
  assert.doesNotMatch(hub, /fetch\s*\(|WebSocket|XMLHttpRequest|placeOrder|submitOrder|NINJATRADER_LIVE/i);
  assert.match(hub, /localStorage\.getItem\('olympus\.atlas\.v1'\)/);
});
