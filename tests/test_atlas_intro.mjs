import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const html = fs.readFileSync(path.join(root, 'atlas', 'index.html'), 'utf8');
const css = fs.readFileSync(path.join(root, 'atlas', 'atlas.css'), 'utf8');
const intro = fs.readFileSync(path.join(root, 'atlas', 'atlas-intro.js'), 'utf8');

test('Atlas entrance is versioned without replacing the standalone hub', () => {
  assert.match(html, /atlas\.css\?v=7/);
  assert.match(html, /atlas-intro\.js\?v=1/);
  assert.match(html, /hub\.js\?v=1/);
  assert.match(html, /The full directory/);
  assert.match(html, /Every arena\.<br><em>One command center\.<\/em>/);
});

test('entrance is short, skippable, accessible, and LITE-safe', () => {
  assert.match(intro, /q=off\|q=low/);
  assert.match(intro, /prefers-reduced-motion: reduce/);
  assert.match(intro, /seen \? 420 : 2200/);
  assert.match(intro, /Enter Olympus Atlas now/);
  assert.match(intro, /e\.key === 'Escape'/);
  assert.match(css, /\.at-intro button\{[^}]*min-height:48px/);
  assert.match(css, /@media\(prefers-reduced-motion:reduce\)\{\.at-intro\{display:none\}/);
});

test('entrance remains read-only', () => {
  assert.doesNotMatch(intro, /fetch\s*\(|WebSocket|XMLHttpRequest|placeOrder|submitOrder|NINJATRADER_LIVE/i);
});
