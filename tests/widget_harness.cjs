// Node harness for tools/web_public/widget/olympus-widget.js (tests/test_widget.py).
//   node tests/widget_harness.cjs pure  <lite.ndjson> <home.json> <now>          -> JSON of the pure parts
//   node tests/widget_harness.cjs draw  <lite.ndjson> <home.json> <family> <param> -> JSON of every text the Scriptable widget drew
// "draw" runs the whole script inside a fake Scriptable (ListWidget, Request, DrawContext ...): Request serves the fixture files.
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const SRC = path.join(__dirname, '..', 'tools', 'web_public', 'widget', 'olympus-widget.js');
const [mode, liteP, homeP, a3, a4] = process.argv.slice(2);
const lite = liteP && liteP !== '-' ? fs.readFileSync(liteP, 'utf8') : '';
const home = homeP && homeP !== '-' ? fs.readFileSync(homeP, 'utf8') : '';

if (mode === 'pure') {
  const W = require(SRC);
  const now = +a3;
  const L = W.parseLite(lite), H = home ? JSON.parse(home) : null;
  const out = {
    lite_t: L && L.reporter && L.reporter.t, lite_kind: L && L.kind,
    pick: W.pick(L, H, null, now), site_only: W.pick(null, H, null, now),
    cached: W.pick(null, null, { v: 1, t: now - 7200, accounts: [{ name: 'X', balance: 1 }], pc: {} }, now),
    none: W.pick(null, null, null, now), junk: W.parseLite('{"message": "{bad"}\n[]\n'),
    k: [W.kalshiNext(now), W.kalshiNext(Date.UTC(2026, 10, 20, 12, 0) / 1000), W.kalshiNext(Date.UTC(2026, 10, 21, 12, 0) / 1000),
      W.kalshiNext(Date.UTC(2026, 10, 26, 12, 0) / 1000), W.kalshiNext(Date.UTC(2026, 6, 15, 8, 0) / 1000)],
    kp: W.kalshiPaper({ paper: { net: 5.68, per100_day: 1.06, updated: '2026-11-17T22:33:30+00:00' } }),
    usd: [W.usd(-807.22), W.usd(1500, true), W.usd(0, true), W.usd(null), W.usd(1234567.4)],
    ago: [W.ago(30), W.ago(600), W.ago(7200), W.ago(400000)],
    feed: [W.feedUrl({ ntfy: 'https://ntfy.sh/', topic: 'abc' }), W.feedUrl(null)],
  };
  process.stdout.write(JSON.stringify(out));
} else if (mode === 'draw') {
  const texts = [], urls = [], images = [], symbols = [];
  let widget = null, presented = null;
  class Stack {
    constructor() { this.kids = []; }
    addStack() { const s = new Stack(); this.kids.push(s); return s; }
    addText(t) { texts.push(String(t)); const o = { text: String(t) }; this.kids.push(o); return o; }
    addImage(img) { images.push(img); const o = { image: img }; this.kids.push(o); return o; }
    addSpacer() { return {}; }
    layoutVertically() {} layoutHorizontally() {} centerAlignContent() {} setPadding() {}
  }
  class ListWidget extends Stack {
    presentSmall() { presented = 'small'; return Promise.resolve(); }
    presentMedium() { presented = 'medium'; return Promise.resolve(); }
    presentLarge() { presented = 'large'; return Promise.resolve(); }
  }
  const files = {};
  const ctx = {
    ListWidget, console, SFSymbol: { named: (n) => { symbols.push(n); return { image: { sf: n } }; } },
    Request: class { constructor(u) { this.url = u; urls.push(u); } loadString() {
      const u = this.url;
      if (u.includes('ntfy')) return lite ? Promise.resolve(lite) : Promise.reject(new Error('offline'));
      if (u.endsWith('home.json')) return home ? Promise.resolve(home) : Promise.reject(new Error('offline'));
      if (u.endsWith('status_feed.json')) return Promise.resolve('{"ntfy":"https://ntfy.sh","topic":"t-test"}');
      if (u.endsWith('rewards.json')) return Promise.resolve('{"paper":{"net":5.68,"per100_day":1.06,"updated":"2026-11-17T22:33:30+00:00"}}');
      return Promise.reject(new Error('404'));
    } },
    Color: Object.assign(class { constructor(h, a) { this.hex = h; this.a = a; } }, { dynamic: (l, d) => ({ l, d }) }),
    Font: new Proxy({}, { get: () => (n) => ({ size: n }) }),
    LinearGradient: class {}, Point: class { constructor(x, y) { this.x = x; this.y = y; } },
    Size: class { constructor(w, h) { this.w = w; this.h = h; } }, Rect: class { constructor(x, y, w, h) { Object.assign(this, { x, y, w, h }); } },
    Path: class { addRoundedRect() {} }, DrawContext: class { addPath() {} setFillColor() {} fillPath() {} getImage() { return { img: 1 }; } },
    FileManager: { local: () => ({ documentsDirectory: () => '/docs', joinPath: (a, b) => a + '/' + b, fileExists: (p) => p in files,
      readString: (p) => files[p], writeString: (p, s) => { files[p] = s; } }) },
    Script: { setWidget: (w) => { widget = w; }, complete: () => {
      const links = [], walk = (n) => { if (!n || !n.kids) return; if (n !== widget && n.url) links.push({ url: n.url, text: flat(n).join(' ') }); n.kids.forEach(walk); };
      const flat = (n) => (n.text != null ? [n.text] : n.kids ? [].concat(...n.kids.map(flat)) : []);
      walk(widget);
      process.stdout.write(JSON.stringify({ texts, urls, url: widget && widget.url, links, symbols, images: images.length, presented, cached: Object.keys(files).length,
        refresh: widget && widget.refreshAfterDate ? widget.refreshAfterDate.getTime() - Date.now() : null }));
    } },
    config: { runsInWidget: a3 !== 'app', widgetFamily: a3 === 'app' ? undefined : a3 },
    args: { widgetParameter: a4 && a4 !== '-' ? a4 : null },
    Intl, Date, JSON, Math, Promise, setTimeout, encodeURIComponent,
  };
  ctx.globalThis = ctx;
  vm.createContext(ctx);
  vm.runInContext(fs.readFileSync(SRC, 'utf8'), ctx, { filename: 'olympus-widget.js' });
}
