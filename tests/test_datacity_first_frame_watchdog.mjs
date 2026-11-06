import { test } from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

const city = fs.readFileSync('tools/web_public/datacity/city.js', 'utf8');
const index = fs.readFileSync('tools/web_public/datacity/index.html', 'utf8');
const start = city.indexOf('function failCity(');
const end = city.indexOf('/** After a lost GPU context', start);
assert.ok(start > 0 && end > start);
const { watchFirstFrame } = vm.runInNewContext(city.slice(start, end) + '\n({ watchFirstFrame })');

function harness() {
  let now = 0, nextId = 0, covered = false;
  const tasks = new Map(), listeners = new Map(), failures = [];
  const doc = {
    hidden:false, visibilityState:'visible',
    addEventListener(name, cb) { listeners.set(name, cb); },
    removeEventListener(name, cb) { if (listeners.get(name) === cb) listeners.delete(name); },
  };
  const app = { contextLost:false, firstFrame:false };
  const schedule = (fn, ms) => { const id = ++nextId; tasks.set(id, { fn, due:now+ms }); return id; };
  const cancel = (id) => tasks.delete(id);
  watchFirstFrame(app, (reason) => failures.push(reason.message), { doc, clock:() => now, schedule, cancel, covered:() => covered });
  return {
    app, doc, failures, tasks, listeners,
    setCovered(v) { covered=v; },
    setHidden(v) { doc.hidden=v; listeners.get('visibilitychange')?.(); },
    advance(ms) {
      now+=ms;
      for (let n=0;n<60;n++) {
        const due = [...tasks].find(([,task]) => task.due <= now);
        if (!due) return;
        tasks.delete(due[0]); due[1].fn();
      }
      throw Error('watchdog scheduled too many immediate checks');
    },
  };
}

test('a visible city with no first frame falls back once after five seconds', () => {
  const h=harness();
  h.advance(4999);
  assert.equal(h.failures.length,0);
  h.advance(1);
  assert.equal(h.failures.length,1);
  assert.match(h.failures[0],/did not draw its first frame/);
  assert.equal(h.app.contextLost,true);
  assert.equal(h.tasks.size,0);
  h.advance(5000);
  assert.equal(h.failures.length,1);
});
test('a healthy first frame stops the one-time watchdog', () => {
  const h=harness();
  h.advance(1000);
  h.app.firstFrame=true;
  h.advance(6000);
  assert.equal(h.failures.length,0);
  assert.equal(h.tasks.size,0);
  assert.equal(h.listeners.size,0);
});
test('background and parent-covered periods do not count toward visible timeout', () => {
  const h=harness();
  h.advance(2000);
  h.setHidden(true);
  h.advance(30000);
  assert.equal(h.failures.length,0);
  h.setHidden(false);
  h.advance(2000);
  h.setCovered(true);
  h.advance(30000);
  assert.equal(h.failures.length,0);
  h.setCovered(false); // no synthetic visibilitychange: the watchdog must notice on its own
  h.advance(500); // covered-state poll starts the fresh visible window
  h.advance(4999);
  assert.equal(h.failures.length,0);
  h.advance(1);
  assert.equal(h.failures.length,1);
});
test('the cache tag loads this watchdog and frame success marks firstFrame', () => {
  assert.match(index,/city\.js\?v=[a-z0-9]+/);
  assert.match(city,/this\.city\.render\(dt\);[\s\S]{0,100}this\.firstFrame = true/);
  assert.match(city,/app\.start\(\);\s*watchFirstFrame\(app, fallback\)/);
});
