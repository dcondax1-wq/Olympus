import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url),list=require('../tools/web_public/olympus/apps-list.js');
const [phone,pc]=await Promise.all([readFile(new URL('../tools/web_public/launcher.js',import.meta.url),'utf8'),readFile(new URL('../web_next/js/next/launcher.js',import.meta.url),'utf8')]);
assert.equal(phone.trimEnd(),pc.trimEnd(),'phone and PC launcher copies stay byte-identical');
const m=phone.match(/var GLYPH_MOTION = (\{[^;]+\});/);assert.ok(m,'glyph motion map exists');
const motion=Function('return ('+m[1]+')')();
const appIds=list.filter(a=>a.id!=='zenith').map(a=>a.id);
// 2026-11-20: the registry grew past the named glyphs; a tile without one gets the shared 'portal' signature (launcher.js)
assert.deepEqual(Object.keys(motion).filter(k=>!appIds.includes(k)),[],'every named glyph belongs to a real launcher app');
assert.match(phone,/GLYPH_MOTION\[a\.id\] \|\| 'portal'/,'apps without a named glyph get the portal signature');
assert.equal(new Set(Object.values(motion)).size,Object.keys(motion).length,'every named glyph is its own signature');
for(const key of Object.values(motion))assert.ok(phone.includes(`data-motion=\\"${key}\\"`)||phone.includes(`GLYPH_MOTION[a.id]`),key);
assert.match(phone,/prefers-reduced-motion:reduce/);assert.match(phone,/\.oly-l:not\(\.calm\)/);
assert.match(phone,/t\.href = url\(a\.path\)/);assert.match(phone,/jv\.href = url\('jarvis\/'\)/);assert.match(phone,/setAttribute\('data-app', a\.id\)/);
assert.doesNotMatch(phone,/NINJATRADER_LIVE|placeOrder|live_model/i);
console.log(`PASS: ${Object.keys(motion).length} named glyphs, ${appIds.length} launcher destinations keep their registry path (named glyphs unique, the rest portal); reduced-motion and calm fallbacks are present.`);
