// Phone Live View check for tests/test_phone_liveview.py.
//   node tests/phone_liveview_check.js <site dir> <port> <liveview.json> [<screenshot dir>]
// Serves <site dir> (the phone app files + a small data.json / home.json) on 127.0.0.1:<port>, answers the GitHub API's
// liveview.json with the given file (and live.json with a small one), then drives #/liveview like a phone: Home button,
// chart drawn, thinking cards, feed, 1m / 5m, full screen (portrait + sideways), the back gesture, the "PC not sending"
// banner. Prints one JSON line: {"ok", "steps": [[name, ok, info]], "errors"}.
const http = require('http'), fs = require('fs'), path = require('path');
const { chromium } = require('playwright');
const [dir, port, lvPath, shots] = [process.argv[2], +(process.argv[3] || 8798), process.argv[4], process.argv[5] || ''];
let LV = JSON.parse(fs.readFileSync(lvPath, 'utf8'));
const T = Math.floor(Date.now() / 1000);
LV.t = T - 20;
const LIVE = { v: 1, kind: 'le-live', t: T - 10, every_s: 60, host: 'SURFACE', pc: { running: true, adapter: 'ninjatrader', present: true, t: T - 10, age_s: 0, live: true },
  pc_verdict: { code: 'LIVE', label: 'TRADING YOUR EVAL', level: 'good', reason: 'ok', checks: [], t: T }, accounts: [] };
const types = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.webmanifest': 'application/manifest+json', '.png': 'image/png', '.svg': 'image/svg+xml' };
const srv = http.createServer((q, s) => {
  const u = decodeURIComponent(q.url.split('?')[0]), f = path.join(dir, u.endsWith('/') ? u + 'index.html' : u);
  if (!f.startsWith(path.resolve(dir)) || !fs.existsSync(f)) { s.writeHead(404); return s.end('nf'); }
  s.writeHead(200, { 'content-type': types[path.extname(f)] || 'application/octet-stream', 'cache-control': 'no-store' });
  fs.createReadStream(f).pipe(s);
}).listen(port, '127.0.0.1');
(async () => {
  const steps = [], errors = [];
  const step = (n, ok, info = '') => steps.push([n, !!ok, String(info).slice(0, 300)]);
  const shot = async (p, name) => { if (shots) await p.screenshot({ path: path.join(shots, name) }); };
  const b = await chromium.launch();
  try {
    const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 2 });
    await ctx.addInitScript(() => { try { localStorage.setItem('oly.hiddenBots', '[]'); } catch (e) {} });   // BLITZ shown for these pinned checks (hidden by default since 2026-11-15)
    const p = await ctx.newPage();
    p.on('pageerror', (e) => errors.push(e.message.slice(0, 200)));
    let lvHits = 0;
    await p.route('https://api.github.com/**', (r) => {
      const isLv = r.request().url().includes('liveview.json');
      if (isLv) lvHits++;
      r.fulfill({ status: 200, contentType: 'application/json',
        headers: { 'access-control-allow-origin': '*', 'access-control-expose-headers': 'x-ratelimit-remaining, x-ratelimit-reset', 'x-ratelimit-remaining': '55', 'x-ratelimit-reset': String(T + 3600) },
        body: JSON.stringify(isLv ? LV : LIVE) });
    });
    await p.route('https://raw.githubusercontent.com/**', (r) => r.fulfill({ status: 500, body: 'raw should not be needed' }));
    await p.goto(`http://127.0.0.1:${port}/#/today`);
    const LT = '.pl-quick a[data-go="liveview"]';      // 2026-10-30: Home's quick tiles (the old button is under Everything else)
    await p.waitForSelector(LT, { timeout: 20000 }).then(() => step('Home: the Live View tile (under the account cards)', true), () => step('Home: the Live View tile (under the account cards)', false));
    await p.evaluate((s) => document.querySelector(s).scrollIntoView({ block: 'center' }), LT);
    await shot(p, 'phone_home.png');
    await p.click(LT);
    await p.waitForFunction(() => location.hash === '#/liveview' && document.querySelector('#lvRoot'), null, { timeout: 10000 })
      .then(() => step('the button opens #/liveview', true), () => step('the button opens #/liveview', false, location.hash));
    await p.waitForFunction(() => /NQ\s[\d,]/.test(document.querySelector('#lvPx')?.textContent || '') && window.LVP && window.LVP.geo, null, { timeout: 20000 })
      .then(() => step('liveview.json loaded from the GitHub API, price shown', true), async () => step('liveview.json loaded from the GitHub API, price shown', false, await p.evaluate(() => (document.querySelector('#lvSrc') || {}).textContent)));
    const ink = await p.evaluate(() => {
      const c = document.querySelector('#lvCv'); const g = c.getContext('2d'); const d = g.getImageData(0, 0, c.width, c.height).data;
      const seen = new Set(); for (let i = 0; i < d.length; i += 4 * 97) seen.add((d[i] >> 4) * 256 + (d[i + 1] >> 4) * 16 + (d[i + 2] >> 4));
      return { w: c.width, h: c.height, colours: seen.size };
    });
    step('the chart is drawn (canvas full of colours)', ink.w > 300 && ink.colours > 25, JSON.stringify(ink));
    const src = await p.evaluate(() => document.querySelector('#lvSrc').textContent);
    step('top line: live from the PC N s ago', /from the PC \d+ s ago/.test(src), src);
    const cards = await p.evaluate(() => [...document.querySelectorAll('#lvThink .lv-card header b')].map((x) => x.textContent));
    const hasSt = await p.evaluate(() => !!(window.LVP.d && window.LVP.d.structure));
    step('thinking cards: Zlarior, ATLAS, BLITZ (+ Market structure when the PC sends it)', cards.join(',') === 'Zlarior,ATLAS,BLITZ' + (hasSt ? ',Market structure' : ''), cards.join(','));
    const head = await p.evaluate(() => [document.querySelector('#lvThink .lv-card .lv-head')?.textContent || '', window.LVP.d.strategies.lit.thinking.headline]);
    step('Zlarior card says what it is thinking (the PC\'s headline)', head[0] && head[0] === head[1], head.join(' | '));
    const fl = await p.evaluate(() => document.querySelectorAll('#lvFeedL li.lv-m').length);
    step('the feed lists the bot\'s messages', fl >= 1, fl);
    const noX = await p.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1);
    step('no sideways page scroll at phone width', noX, await p.evaluate(() => document.documentElement.scrollWidth));
    await shot(p, 'phone_liveview.png');
    const n1 = await p.evaluate(() => window.LVP.geo && window.LVP.geo.n);
    await p.click('#lvTf button[data-v="5m"]');
    const t5 = await p.evaluate(() => ({ tf: window.LVP.tf, n: window.LVP.geo && window.LVP.geo.n, bars: window.LVP.d.bars5.length }));
    step('5m button: the 5m bars (from bars5)', t5.tf === '5m' && t5.n > 0 && t5.bars > 0, JSON.stringify({ n1, ...t5 }));
    await p.click('#lvTf button[data-v="1m"]');
    // the strategy switch hides its card
    await p.click('[data-lv-on="atlas"]');
    const c2 = await p.evaluate(() => [...document.querySelectorAll('#lvThink .lv-card header b')].map((x) => x.textContent).join(','));
    step('ATLAS switch off hides its card', c2 === 'Zlarior,BLITZ' + (hasSt ? ',Market structure' : ''), c2);
    await p.click('[data-lv-on="atlas"]');
    // full screen (portrait)
    await p.click('#lvFs');
    await p.waitForTimeout(500);
    const fs1 = await p.evaluate(() => { const r = document.querySelector('#lvRoot').getBoundingClientRect(); return { fs: document.fullscreenElement === document.querySelector('#lvRoot'), max: document.querySelector('#lvRoot').classList.contains('lv-max'), w: r.width, h: r.height, top: r.top, label: document.querySelector('#lvFs span').textContent }; });
    step('Full screen covers the whole phone screen', (fs1.fs || fs1.max) && fs1.w >= 389 && fs1.h >= 840 && Math.abs(fs1.top) < 2 && fs1.label === 'Exit', JSON.stringify(fs1));
    await shot(p, 'phone_liveview_full.png');
    await p.click('#lvFs');
    await p.waitForTimeout(400);
    const fs2 = await p.evaluate(() => ({ fs: !!document.fullscreenElement, max: document.querySelector('#lvRoot').classList.contains('lv-max'), inPage: !!document.querySelector('#page #lvRoot') }));
    step('Exit leaves full screen, back in the page', !fs2.fs && !fs2.max && fs2.inPage, JSON.stringify(fs2));
    // sideways: the biggest chart (the CSS full screen, as on an iPhone)
    await p.setViewportSize({ width: 844, height: 390 });
    await p.evaluate(() => { Element.prototype.requestFullscreen = undefined; Element.prototype.webkitRequestFullscreen = undefined; });
    await p.click('#lvFs');
    await p.waitForTimeout(500);
    const land = await p.evaluate(() => ({ max: document.querySelector('#lvRoot').classList.contains('lv-max'), inBody: document.querySelector('#lvRoot').parentNode === document.body, wrap: document.querySelector('#lvWrap').getBoundingClientRect().height, cv: document.querySelector('#lvCv').width }));
    step('sideways + full screen (iPhone way): the chart takes the screen', land.max && land.inBody && land.wrap >= 300, JSON.stringify(land));
    await shot(p, 'phone_liveview_landscape.png');
    // the back gesture leaves the full screen
    await p.evaluate(() => { location.hash = '#/today'; });
    await p.waitForTimeout(500);
    const back = await p.evaluate(() => ({ max: !!document.querySelector('.lv-root.lv-max'), lock: document.documentElement.classList.contains('lv-lock'), hash: location.hash }));
    step('back to Home closes the full screen', !back.max && !back.lock, JSON.stringify(back));
    await p.setViewportSize({ width: 390, height: 844 });
    // the PC stops sending: the banner says so
    LV = { ...LV, t: T - 45 * 60 };
    await p.evaluate(() => { location.hash = '#/liveview'; });
    await p.waitForSelector('#lvRoot');
    await p.evaluate(() => window.LVP.load(true));
    await p.waitForTimeout(300);
    const ban = await p.evaluate(() => { const b = document.querySelector('#lvBan'); return { hidden: b.hidden, text: b.textContent }; });
    step('PC not sending for 45 min: banner says so', !ban.hidden && /PC is not sending/.test(ban.text), JSON.stringify(ban));
    // More lists it under Today
    await p.evaluate(() => { location.hash = '#/system'; });
    await p.waitForTimeout(600);
    const more = await p.evaluate(() => { const s = [...document.querySelectorAll('.cl-sec h4')].find((h) => h.textContent.trim().startsWith('Today')); return s ? s.parentNode.textContent : ''; });
    step('More > Today lists Live View', /Live View/.test(more), more.slice(0, 120));
    step('liveview.json came from the API (no raw needed)', lvHits >= 2, lvHits);
    step('no page errors', errors.length === 0, errors.join(' | '));
    console.log(JSON.stringify({ ok: steps.every((s) => s[1]), steps, errors }));
  } catch (e) {
    console.log(JSON.stringify({ ok: false, steps, error: String(e).slice(0, 300), errors }));
  } finally { await b.close(); srv.close(); }
})();
