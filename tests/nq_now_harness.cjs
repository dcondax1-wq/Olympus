// Node harness for tools/web_public/widget/nq-now.js (tests/test_nq_now.py).
//   node tests/nq_now_harness.cjs pure <post.json|-> <ports.json|-> <now>                 -> JSON: the model + words for that post
//   node tests/nq_now_harness.cjs draw <post.json|-> <ports.json|-> <now> <family> [cache.json] -> JSON: every text drawn, url, refresh
// "draw" runs the whole script in a fake Scriptable (ListWidget, Request, Color, Font, FileManager ...) with the clock fixed at <now>.
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const SRC = path.join(__dirname, '..', 'tools', 'web_public', 'widget', 'nq-now.js');
const [mode, postP, portsP, nowS, fam, cacheP] = process.argv.slice(2);
const post = postP && postP !== '-' ? JSON.parse(fs.readFileSync(postP, 'utf8')) : null;
const ports = portsP && portsP !== '-' ? fs.readFileSync(portsP, 'utf8') : null;
const NOW = +nowS;
const ndjson = (p) => JSON.stringify({ event: 'message', time: p.reporter ? p.reporter.t : p.t, message: JSON.stringify(p) }) + '\n'
  + JSON.stringify({ event: 'keepalive', time: p.t }) + '\nnot json\n';

if (mode === 'pure') {
  const W = require(SRC);
  const P = ports ? JSON.parse(ports) : null, L = post ? W.parseLite(ndjson(post)) : null;
  const m = W.model(L, P, null, NOW);
  process.stdout.write(JSON.stringify({ m, status: W.statusLine(m), junk: W.parseLite('{"message":"{bad"}\n[]\n'),
    usd: [W.usd(-807.2), W.usd(1500, true), W.usd(0, true), W.usd(null)], span: [W.span(600), W.span(7500), W.span(3 * 86400 + 4000)] }));
} else if (mode === 'draw') {
  const texts = [], urls = [];
  let widget = null, presented = null;
  const files = {};
  if (cacheP && cacheP !== '-') files['/docs/nq-now-cache.json'] = fs.readFileSync(cacheP, 'utf8');
  class Stack {
    constructor() { this.kids = []; }
    addStack() { const s = new Stack(); this.kids.push(s); return s; }
    addText(t) { texts.push(String(t)); const o = { text: String(t) }; this.kids.push(o); return o; }
    addImage() { return {}; } addSpacer() { return {}; }
    layoutVertically() {} layoutHorizontally() {} centerAlignContent() {} setPadding() {}
  }
  class ListWidget extends Stack {
    presentSmall() { presented = 'small'; return Promise.resolve(); }
    presentMedium() { presented = 'medium'; return Promise.resolve(); }
    presentLarge() { presented = 'large'; return Promise.resolve(); }
  }
  class FixedDate extends Date { constructor(...a) { if (a.length) super(...a); else super(NOW * 1000); } static now() { return NOW * 1000; } }
  const ctx = {
    ListWidget, console,
    Request: class { constructor(u) { this.url = u; urls.push(u); } loadString() {
      const u = this.url;
      if (u.includes('ntfy')) return post ? Promise.resolve(ndjson(post)) : Promise.reject(new Error('offline'));
      if (u.endsWith('status_feed.json')) return Promise.resolve('{"ntfy":"https://ntfy.sh","topic":"t-test"}');
      if (u.endsWith('nq/ports.json')) return ports ? Promise.resolve(ports) : Promise.reject(new Error('404'));
      return Promise.reject(new Error('404'));
    } },
    Color: class { constructor(h, a) { this.hex = h; this.a = a; } },
    Font: new Proxy({}, { get: () => (n) => ({ size: n }) }),
    LinearGradient: class {}, Point: class { constructor(x, y) { this.x = x; this.y = y; } },
    FileManager: { local: () => ({ documentsDirectory: () => '/docs', joinPath: (a, b) => a + '/' + b, fileExists: (p) => p in files,
      readString: (p) => files[p], writeString: (p, s) => { files[p] = s; } }) },
    Script: { setWidget: (w) => { widget = w; }, complete: () => {
      const w = widget || null;
      process.stdout.write(JSON.stringify({ texts, urls, url: w && w.url, presented, cached: '/docs/nq-now-cache.json' in files ? JSON.parse(files['/docs/nq-now-cache.json']) : null,
        refresh: w && w.refreshAfterDate ? (w.refreshAfterDate.getTime() - NOW * 1000) / 1000 : null }));
    } },
    config: { runsInWidget: fam !== 'app', widgetFamily: fam === 'app' ? undefined : fam },
    args: { widgetParameter: null },
    Intl, Date: FixedDate, JSON, Math, Promise, setTimeout, encodeURIComponent,
  };
  ctx.globalThis = ctx;
  vm.createContext(ctx);
  vm.runInContext(fs.readFileSync(SRC, 'utf8'), ctx, { filename: 'nq-now.js' });
}
