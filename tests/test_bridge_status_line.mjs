import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import vm from 'node:vm';

const code = await readFile(new URL('../tools/web_public/bridge/status-line.js', import.meta.url), 'utf8');
const context = { window: {} };
vm.runInNewContext(code, context);
const line = context.window.BRIDGE_STATUS_LINE;
assert.match(line({ state: 'in_progress', files: 2 }).text, /Last reported: in progress/);
assert.doesNotMatch(line({ state: 'in_progress', files: 2 }).text, /is working/);
assert.match(line({ state: 'in progress', files: 1 }).text, /Last reported: in progress \(1 file\)/);
assert.match(line({ state: 'blocked', files: 0 }).text, /needs review/);
assert.match(line({ state: 'done', files: 1 }).text, /1 file delivered/);
assert.match(line(null).text, /Waiting/);
console.log('Bridge published status truth cases passed');
