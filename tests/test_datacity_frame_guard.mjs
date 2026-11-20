import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const city = fs.readFileSync('tools/web_public/datacity/city.js', 'utf8');
const index = fs.readFileSync('tools/web_public/datacity/index.html', 'utf8');
const start = city.indexOf('  start() {\n');
const end = city.indexOf('\n  }\n}', start);
assert.ok(start > 0 && end > start);

function run(failAt) {
  const scheduled = [], failures = [];
  const env = {
    performance: { now: () => 0 },
    requestAnimationFrame: (fn) => scheduled.push(fn),
    location: { hash: '#keep' }, P: { has: () => true }, O: null,
    document: { hidden:false, body:{ classList:{ contains:()=>false } } },
  };
  const method = vm.runInNewContext('({' + city.slice(start, end + 4) + '})', env).start;
  let renders = 0;
  const app = {
    contextLost:false, calm:true, quality:'hq',
    route(){}, checkGold(){}, stepFlashes(){}, stepTimeline(){}, updateCam(){},
    orbit:{ update(){ if (failAt === 'orbit') throw Error('orbit failed'); }, at:{}, view:{target:{}} },
    city:{ render(){ renders++; }, renderer:{info:{render:{calls:1,triangles:2}}}, beam:{at:null}, camera:{} },
    minimap:{ draw(){ if (failAt === 'minimap') throw Error('minimap failed'); } },
    updateTag(){},
    onRenderFailure(e){ failures.push(e.message); this.contextLost=true; },
  };
  method.call(app);
  scheduled.shift()(50);
  scheduled.shift()(80);
  return { failures, renders, remaining:scheduled.length };
}

test('camera control exceptions show fallback and stop the queued loop', () => {
  assert.deepEqual(run('orbit'), { failures:['orbit failed'], renders:0, remaining:0 });
});
test('post-render minimap exceptions show fallback and stop the queued loop', () => {
  assert.deepEqual(run('minimap'), { failures:['minimap failed'], renders:1, remaining:0 });
});
test('cached clients receive the frame guard', () => {
  assert.match(index, /city\.js\?v=[\w.-]+/);
});
