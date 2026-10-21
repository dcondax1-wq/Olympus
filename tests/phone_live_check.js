// Phone app check for tests/test_live_publish.py: Home updates from a changed live.json within one poll.
//   node tests/phone_live_check.js <site dir> <port>
// Serves <site dir> (the phone app files + a small data.json / home.json) on 127.0.0.1:<port>, answers the GitHub API's
// live.json with version A, then switches it to version B and waits for the page to show B without a reload.
// Prints one JSON line: {"ok", "steps": [[name, ok, info]], "polls", "errors"}.
const http = require('http'), fs = require('fs'), path = require('path');
const { chromium } = require('playwright');
const [dir, port] = [process.argv[2], +(process.argv[3] || 8799)];
const T = Math.floor(Date.now() / 1000);
const acct = (toGo, profit, t) => ({ id: 'mffu50k_eval', name: 'MFFU 50K Eval', firm: 'MFFU', plan: 'Builder 50K', kind: 'eval', source: 'pc', badge: 'SIM',
  conn: { present: true, t, age_s: 0, connected: true, has_detail: true, running: true, host: 'SURFACE' },
  eval: { balance: 50000 + profit, profit, to_target: toGo, floor: 48000, room: 2000 + profit, mll: 2000, dll: 1000, dll_used: 0, session: 4, sessions: 10, clock_text: 'session 4 of 10' },
  pnl: { today: profit, week: profit, since_start: profit, traded: 1 }, position: null, orders: [], trades: [], days: [], stats: { n: 1 } });
const live = (label, toGo, profit, t) => ({ v: 1, kind: 'le-live', t, every_s: 60, host: 'SURFACE',
  pc: { running: true, adapter: 'ninjatrader', present: true, t, age_s: 0, silent: false, every_s: 60, host: 'SURFACE', live: true,
    health: { account: { name: 'Sim101', label: 'SIM' }, feed: { age_1m_s: 20, age_5m_s: 100, source: 'ninjatrader' }, lit: { stage: 'levels', text: 'waiting for a sweep' } } },
  pc_verdict: { code: 'SIM', label, level: 'good', reason: 'live check ' + label, checks: [], t }, accounts: [acct(toGo, profit, t)] });
let LIVE = live('LIVE VERSION A', 2500, 500, T - 5);
let apiHits = 0;
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
  const b = await chromium.launch();
  try {
    const p = await b.newPage({ viewport: { width: 390, height: 900 }, isMobile: true, hasTouch: true });
    p.on('pageerror', (e) => errors.push(e.message.slice(0, 200)));
    await p.route('https://api.github.com/**', (r) => { apiHits++; r.fulfill({ status: 200, contentType: 'application/json',
      headers: { 'access-control-allow-origin': '*', 'access-control-expose-headers': 'x-ratelimit-remaining, x-ratelimit-reset', 'x-ratelimit-remaining': '55', 'x-ratelimit-reset': String(T + 3600) },
      body: JSON.stringify(LIVE) }); });
    await p.route('https://raw.githubusercontent.com/**', (r) => r.fulfill({ status: 500, body: 'raw should not be needed' }));
    await p.goto(`http://127.0.0.1:${port}/#/today`);
    await p.waitForFunction(() => document.body.innerText.includes('LIVE VERSION A'), null, { timeout: 20000 }).then(() => step('Home shows live.json A (verdict)', true), () => step('Home shows live.json A (verdict)', false));
    const a = await p.evaluate(() => document.body.innerText);
    step('Home: $ to go from live.json A ($2,500), not data.json ($2,900)', a.includes('2,500') && !a.includes('2,900'), a.match(/To \+\$3,000[\s\S]{0,40}/)?.[0]);
    const chipT = await p.evaluate(() => document.getElementById('liveChip')?.textContent || '');
    step('header chip "live · N s ago"', /live · \d+ s ago/.test(chipT), chipT);
    step('Surface line uses the live check-in (newer than the heartbeat in data.json)', /Surface last check-in/.test(a) && /live from the PC/.test(a), a.match(/Surface[^\n]*\n[^\n]*/)?.[0]);
    const every = await p.evaluate(() => window.LIVE.every);
    const t0 = Date.now();
    LIVE = live('LIVE VERSION B', 1234, 1766, Math.floor(Date.now() / 1000));
    await p.waitForFunction(() => document.body.innerText.includes('LIVE VERSION B'), null, { timeout: (every + 8) * 1000 })
      .then(() => step(`Home updates to live.json B within one poll (${every} s)`, true, ((Date.now() - t0) / 1000).toFixed(1) + ' s'),
        () => step(`Home updates to live.json B within one poll (${every} s)`, false));
    const bb = await p.evaluate(() => document.body.innerText);
    step('Home: $ to go now $1,234 (eval meter / tiles from B)', bb.includes('1,234'));
    step('no page errors', errors.length === 0, errors.join(' | '));
    console.log(JSON.stringify({ ok: steps.every((s) => s[1]), steps, polls: apiHits, errors }));
  } catch (e) {
    console.log(JSON.stringify({ ok: false, steps, error: String(e).slice(0, 300), errors }));
  } finally { await b.close(); srv.close(); }
})();
