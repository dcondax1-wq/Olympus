import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import vm from 'node:vm';

const html = await readFile(new URL('../tools/web_public/bridge/index.html', import.meta.url), 'utf8');
const match = html.match(/<script>\s*(if \(!window\.BRIDGE_STATUS_LINE\)[\s\S]*?)<\/script>/);
assert.ok(match, 'inline fallback must run after the external helper');
const missing = { window: {} };
vm.runInNewContext(match[1], missing);
assert.equal(missing.window.BRIDGE_STATUS_LINE({ state: 'in progress' }).text,
  'Job status display unavailable · refresh to retry');
const existing = () => ({ className: 'live', text: 'Existing helper' });
const loaded = { window: { BRIDGE_STATUS_LINE: existing } };
vm.runInNewContext(match[1], loaded);
assert.equal(loaded.window.BRIDGE_STATUS_LINE, existing, 'loaded helper must keep its normal behavior');
console.log('Bridge missing-helper fallback cases passed');
