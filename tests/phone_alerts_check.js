// Phone app check for tests/test_alerts_plus.py: the #/ack page, "Got it", the alert levels and the critical banner.
//   node tests/phone_alerts_check.js <site dir> <port>
// Serves <site dir> on 127.0.0.1:<port>, answers the ntfy relay (GET: one open critical alert from the PC; POST: recorded).
// Prints one JSON line: {"ok", "steps": [[name, ok, info]], "posts", "errors"}.
const http = require('http'), fs = require('fs'), path = require('path');
const { chromium } = require('playwright');
const [dir, port] = [process.argv[2], +(process.argv[3] || 8823)];
const T = Math.floor(Date.now() / 1000);
const ID = 'feed_stale:2026-10-21';
const crit = { le: 'crit', src: 'pc', t: T - 60, open: [{ id: ID, kind: 'feed_stale', title: 'FEED STALE: new entries blocked', body: 'NinjaTrader bars stale.', first: T - 600, n: 2 }] };
const posts = [];
const types = { '.html': 'text/html', '.js': 'text/javascript', '.json': 'application/json', '.webmanifest': 'application/manifest+json', '.png': 'image/png', '.svg': 'image/svg+xml' };
const srv = http.createServer((q, s) => {
  const u = decodeURIComponent(q.url.split('?')[0]), f = path.join(dir, u.endsWith('/') ? u + 'index.html' : u);
  if (!f.startsWith(path.resolve(dir)) || !fs.existsSync(f)) { s.writeHead(404); return s.end('nf'); }
  s.writeHead(200, { 'content-type': types[path.extname(f)] || 'application/octet-stream', 'cache-control': 'no-store' });
  fs.createReadStream(f).pipe(s);
}).listen(port, '127.0.0.1');
(async () => {
  const steps = [], errors = [];
  const step = (n, ok, info = '') => steps.push([n, !!ok, String(info).slice(0, 300)]);
  const b = require('./net_stub.cjs').wrap(await chromium.launch());   // ntfy.sh answers "{}": never the PC's real status
  try {
    const p = await b.newPage({ viewport: { width: 390, height: 900 }, isMobile: true, hasTouch: true });
    p.on('pageerror', (e) => errors.push(e.message.slice(0, 200)));
    await p.route('https://ntfy.sh/**', (r) => {
      const q = r.request();
      if (q.method() === 'POST') { try { posts.push(JSON.parse(q.postData() || '{}')); } catch (e) { posts.push({ bad: q.postData() }); } return r.fulfill({ status: 200, headers: { 'access-control-allow-origin': '*' }, body: '{}' }); }
      const acked = posts.some((x) => x.le === 'ack' && x.id === ID);
      const lines = [{ event: 'message', time: T - 60, message: JSON.stringify(crit) }].concat(acked ? [{ event: 'message', time: T, message: JSON.stringify({ le: 'ack', id: ID }) }] : []);
      r.fulfill({ status: 200, headers: { 'access-control-allow-origin': '*' }, contentType: 'application/x-ndjson', body: lines.map((x) => JSON.stringify(x)).join('\n') });
    });
    await p.route('https://api.github.com/**', (r) => r.fulfill({ status: 404, headers: { 'access-control-allow-origin': '*' }, body: '{}' }));
    await p.route('https://raw.githubusercontent.com/**', (r) => r.fulfill({ status: 404, body: 'nf' }));
    await p.goto(`http://127.0.0.1:${port}/#/today`);
    await p.waitForSelector('#apBan .ap-ban', { timeout: 20000 }).then(() => step('Today: red banner for the open critical alert', true), () => step('Today: red banner for the open critical alert', false));
    await p.goto(`http://127.0.0.1:${port}/#/ack/${encodeURIComponent(ID)}`);
    await p.waitForSelector(`[data-ack="${ID}"]`, { timeout: 20000 }).then(() => step('#/ack lists the alert with a Got it button', true), () => step('#/ack lists the alert with a Got it button', false));
    const txt = await p.evaluate(() => document.body.innerText);
    step('#/ack shows the title and the repeat count', txt.includes('FEED STALE: new entries blocked') && /sent 2 of 6/.test(txt), txt.slice(0, 200));
    await p.click(`[data-ack="${ID}"]`).catch(() => null);
    await p.waitForFunction(() => !document.querySelector('[data-ack]'), null, { timeout: 10000 }).catch(() => null);
    step('Got it posts {le: ack, id} to the relay', posts.some((x) => x.le === 'ack' && x.id === ID), JSON.stringify(posts));
    step('Got it: the alert leaves the list', !(await p.$(`[data-ack="${ID}"]`)));
    await p.goto(`http://127.0.0.1:${port}/#/settings`);
    await p.waitForSelector('#apLevels [data-lk="armed"][data-lv="silent"]', { timeout: 20000 }).then(() => step('Settings: Alert levels card', true), () => step('Settings: Alert levels card', false));
    await p.click('#apLevels [data-lk="armed"][data-lv="silent"]').catch(() => null);
    await p.waitForTimeout(500);
    step('levels: Silent posts {le: prefs, prefs: {armed: silent}}', posts.some((x) => x.le === 'prefs' && x.prefs && x.prefs.armed === 'silent'), JSON.stringify(posts.slice(-2)));
    step('no page errors', errors.length === 0, errors.join(' | '));
    console.log(JSON.stringify({ ok: steps.every((s) => s[1]), steps, posts: posts.length, errors }));
  } catch (e) {
    console.log(JSON.stringify({ ok: false, steps, error: String(e).slice(0, 300), errors }));
  } finally { await b.close(); srv.close(); }
})();
