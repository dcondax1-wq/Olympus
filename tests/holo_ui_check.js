// Holodeck UI check for tests/test_holo_ui.py.
//   node tests/holo_ui_check.js <phone site dir> <web_next dir> <web dir> <fixture.json> [<screenshot dir>]
// Phone: serves the phone app (a copy of tools/web_public + a small data.json / home.json), answers GitHub's API with the
// fixture's holo.json / holo_hist.json, drives #/holo at 390x844 (portrait) and 844x390 (sideways). PC: a tiny static server
// (web_next/ first, then web/) with a mocked GET /api/next/holo and /api/next/holo/days, 1440x900. Then WebGL off (2D
// fallback). Prints one JSON line: {"steps": [[name, ok, info]], "errors", "perf"}.
const http = require('http'), fs = require('fs'), path = require('path');
const { chromium } = require('playwright');
const [site, webNext, web, fixPath, shots] = process.argv.slice(2);
const FIX = JSON.parse(fs.readFileSync(fixPath, 'utf8'));
const HOLO = FIX.holo, HIST = FIX.hist;
const T = Math.floor(Date.now() / 1000);
const types = { '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.webmanifest': 'application/manifest+json', '.png': 'image/png', '.svg': 'image/svg+xml', '.woff2': 'font/woff2' };
const steps = [], errors = [], perf = {};
const step = (n, ok, info = '') => steps.push([n, !!ok, String(info).slice(0, 300)]);
const shot = async (p, name) => { if (shots) await p.screenshot({ path: path.join(shots, name) }); };
const GPU = ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'];
const LIVE = { v: 1, kind: 'le-live', t: T - 10, every_s: 60, host: 'SURFACE', pc: { running: true, adapter: 'ninjatrader', present: true, t: T - 10, age_s: 0, live: true },
  pc_verdict: { code: 'LIVE', label: 'TRADING YOUR EVAL', level: 'good', reason: 'ok', checks: [], t: T }, accounts: [] };
const fmtPx = (x) => Number(x).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const etHMS = (t) => new Intl.DateTimeFormat('en-US', { timeZone: 'America/New_York', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false }).format(new Date(t * 1000)).replace(/^24/, '00');
function dayDoc(day) {
  if (!day || day === HOLO.day) return HOLO;
  const D = HIST.days.find((x) => x.day === day);
  return D ? { v: 1, kind: 'le-holo', t: HIST.t, day: D.day, live: false, bars: D.bars, bots: HOLO.bots, fills: D.fills, trades: D.trades, orders: [], thoughts: D.thoughts, levels: [], structure: null, now: null } : null;
}
function serve(roots, api) {
  return new Promise((res) => {
    const srv = http.createServer((q, s) => {
      const u = decodeURIComponent(q.url.split('?')[0]);
      if (api && u.startsWith('/api/')) { const r = api(u, new URL(q.url, 'http://x').searchParams); s.writeHead(r ? 200 : 404, { 'content-type': 'application/json' }); return s.end(JSON.stringify(r || { error: 'not in this test' })); }
      for (const dir of roots) {
        const f = path.join(dir, u.endsWith('/') ? u + 'index.html' : u);
        if (f.startsWith(path.resolve(dir)) && fs.existsSync(f) && fs.statSync(f).isFile()) {
          s.writeHead(200, { 'content-type': types[path.extname(f)] || 'application/octet-stream', 'cache-control': 'no-store' });
          return fs.createReadStream(f).pipe(s);
        }
      }
      s.writeHead(404); s.end('nf');
    }).listen(0, '127.0.0.1', () => res(srv));
  });
}
async function ghRoutes(p, hits) {
  await p.route('https://api.github.com/**', (r) => {
    const u = r.request().url(), f = /holo_hist\.json/.test(u) ? HIST : /holo\.json/.test(u) ? HOLO : /liveview\.json/.test(u) ? null : LIVE;
    if (hits) hits.push(u.replace(/^.*contents\//, '').replace(/\?.*$/, ''));
    if (!f) return r.fulfill({ status: 404, contentType: 'application/json', headers: { 'access-control-allow-origin': '*' }, body: '{"message":"Not Found"}' });
    r.fulfill({ status: 200, contentType: 'application/json',
      headers: { 'access-control-allow-origin': '*', 'access-control-expose-headers': 'x-ratelimit-remaining, x-ratelimit-reset', 'x-ratelimit-remaining': '55', 'x-ratelimit-reset': String(T + 3600) },
      body: JSON.stringify(f) });
  });
  await p.route('https://raw.githubusercontent.com/**', (r) => r.fulfill({ status: 500, body: 'raw should not be needed' }));
}
const waitHolo = (p, ms = 90000) => p.waitForFunction(() => { const v = window.HOLO?.ui?.view || window.LE?.holo?.view; return v && v.counts().bars > 0 && v.stats().frames > 3; }, null, { timeout: ms });
const V = (expr) => `(() => { const H = window.HOLO?.ui || window.LE?.holo; const v = H?.view; return (${expr}); })()`;

// shared checks on a mounted Holodeck (phone or PC)
async function core(p, tag) {
  const nF = HOLO.fills.length, nT = HOLO.trades.length;
  const c = await p.evaluate(V('v.counts()'));
  step(`${tag}: the scene mounts (WebGL canvas, ${c.bars} bars)`, c.bars === HOLO.bars['1m'].length && await p.evaluate(() => !!document.querySelector('.hd-gl canvas')), JSON.stringify(c));
  const dom = await p.evaluate(() => document.querySelectorAll('.hd-labs .hd-fill').length);
  step(`${tag}: every fill drawn (${nF} orbs + labels = the fixture's fills)`, c.fills === nF && dom === nF && c.fillsShown === nF, `view ${c.fills} shown ${c.fillsShown} labels ${dom}`);
  step(`${tag}: trade volumes (${nT}) + the LIT setup anatomy`, c.trades === nT && c.tradesShown === nT && c.setups >= 1, JSON.stringify(c));
  const th = await p.evaluate(() => [...document.querySelectorAll('.hd-labs .hd-thought')].filter((e) => e.style.visibility === 'visible').length);
  step(`${tag}: holographic thought panels on screen`, th >= 1 && c.thoughts === HOLO.thoughts.length, `visible ${th} of ${c.thoughts}`);
  const minds = await p.evaluate(() => [...document.querySelectorAll('.hd-mind header b')].map((x) => x.textContent).join(','));
  step(`${tag}: Minds panel: Zlarior, ATLAS, BLITZ`, minds === 'Zlarior,ATLAS,BLITZ', minds);
  // the exact fill: focus Zlarior's real entry from the Fills list, its label + card show the exact price and second
  const f = HOLO.fills.find((x) => x.real && x.kind === 'entry') || HOLO.fills[0];
  await p.click('.hd-tabs button[data-t="fills"]');
  await p.click(`.hd-list button[data-id="${f.id}"]`);
  await p.waitForTimeout(1600);
  await p.evaluate(() => document.querySelector('#hdStage').scrollIntoView({ block: 'start' })); await p.waitForTimeout(300);
  const lab = await p.evaluate((id) => { const e = document.querySelector(`.hd-labs .hd-fill[data-id="${id}"]`); const r = e.getBoundingClientRect(); return { txt: e.textContent, vis: e.style.visibility, x: r.x, y: r.y, w: r.width, focus: e.classList.contains('focus'), card: document.querySelector('#hdCard:not([hidden]) #hdFillTxt')?.textContent || '' }; }, f.id);
  step(`${tag}: fill label shows the exact price + time (${fmtPx(f.px)} · ${etHMS(f.t)})`, lab.txt.includes(fmtPx(f.px)) && lab.txt.includes(etHMS(f.t)) && lab.vis === 'visible' && lab.focus, JSON.stringify(lab));
  step(`${tag}: fill card: side, qty, price, second, bot, REAL, slip vs the model`, lab.card.includes(`${f.side} ${f.qty} MNQ @ ${fmtPx(f.px)} · ${etHMS(f.t)} ET`) && /REAL/.test(lab.card) && /slip \+1 tick \(model/.test(lab.card), lab.card);
  if (shots) await p.locator('#hdStage').screenshot({ path: path.join(shots, `${tag}_fill_closeup.png`) });
  await p.click('#hdX');
  await p.click('.hd-tabs button[data-t="minds"]');
}
// replay: bars build, fills pop in time order (every sample: the fills shown = the fills with t <= T)
async function replay(p, tag) {
  const first = Math.min(...HOLO.fills.map((x) => x.t));
  await p.evaluate(V('(H.setSpeed(120), H.replay(' + (first - 240) + '), 1)'));
  await p.waitForTimeout(400);
  const samples = await p.evaluate(async (fills) => {
    const H = window.HOLO?.ui || window.LE?.holo, out = [];
    for (let k = 0; k < 22; k++) {
      await new Promise((r) => setTimeout(r, 150));
      const v = H.view, c = v.counts(), T = c.T;
      const want = fills.filter((f) => f.t <= T).map((f) => f.id).sort().join(','), got = v.fills.filter((F) => F.g.visible).map((F) => F.f.id).sort().join(',');
      out.push({ T, bars: c.barsShown, ok: want === got, n: got ? got.split(',').length : 0 });
    }
    return out;
  }, HOLO.fills.map((x) => ({ id: x.id, t: x.t })));
  const grow = samples.at(-1).bars > samples[0].bars && samples.at(-1).T > samples[0].T;
  step(`${tag}: replay advances (bars ${samples[0].bars} -> ${samples.at(-1).bars}, ${etHMS(samples[0].T)} -> ${etHMS(samples.at(-1).T)})`, grow, JSON.stringify(samples.slice(0, 3)));
  step(`${tag}: fills pop exactly when they happened (every sample: shown = t <= replay time)`, samples.every((s) => s.ok) && samples.at(-1).n >= 1, JSON.stringify(samples.filter((s) => !s.ok).slice(0, 2)));
  await shot(p, `${tag}_replay.png`);
  await p.evaluate(V('(H.pause(), 1)'));
}
async function dayPicker(p, tag) {
  const other = HIST.days.find((d) => d.day !== HOLO.day);
  await p.selectOption('#hdDay', other.day);
  const ok = await p.waitForFunction((d) => { const H = window.HOLO?.ui || window.LE?.holo; return H.state.day === d && H.view.counts().fills === H.state.d.fills.length; }, other.day, { timeout: 15000 }).then(() => true, () => false);
  const n = await p.evaluate(V('v.counts().fills'));
  step(`${tag}: day picker loads ${other.day} (${n} fills = ${other.fills.length})`, ok && n === other.fills.length, n);
  const tl = await p.evaluate(() => [...document.querySelectorAll('#hdDay option')].map((o) => o.value).filter(Boolean).length);
  step(`${tag}: day picker lists every archived day (${HIST.days.length})`, tl === HIST.days.length, tl);
  await p.selectOption('#hdDay', '');
  await p.waitForFunction((d) => (window.HOLO?.ui || window.LE?.holo).state.day === d, HOLO.day, { timeout: 15000 }).catch(() => null);
}
async function frames(p, tag) {
  await p.waitForTimeout(1200);
  const s = await p.evaluate(V('v.stats()'));
  perf[tag] = s;
  // 3D Lite (no bloom, no reflection): the frame time there too, then back to Max
  await p.evaluate(V('(v.setQuality("lite"), 1)')); await p.waitForTimeout(1500);
  perf[tag + '_lite'] = await p.evaluate(V('v.stats()'));
  await p.evaluate(V('(v.setQuality("max"), 1)')); await p.waitForTimeout(300);
  step(`${tag}: frame time sane (${s.msAvg} ms a frame, ${s.fps} fps, ${s.calls} draw calls, bloom ${s.bloom})`, s.msAvg > 0 && s.msAvg < 400 && s.frames > 10, JSON.stringify(s));
}

(async () => {
  const phoneSrv = await serve([site]);
  const pcSrv = await serve([webNext, web], (u, q) => {
    if (u === '/api/next/holo') return dayDoc(q.get('day'));
    if (u === '/api/next/holo/days') return { days: HIST.days.map((d) => ({ day: d.day, trades: d.trades.length, usd: d.trades.reduce((a, t) => a + (t.usd || 0), 0) })) };
    return null;
  });
  const PH = `http://127.0.0.1:${phoneSrv.address().port}`, PC = `http://127.0.0.1:${pcSrv.address().port}`;
  const b = await chromium.launch({ args: GPU });
  try {
    // ---------------------------------------------------------------- phone portrait
    {
      const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 2 });
      const p = await ctx.newPage(); p.on('pageerror', (e) => errors.push('phone: ' + e.message.slice(0, 200)));
      const hits = []; await ghRoutes(p, hits);
      await p.goto(`${PH}/?fxfixed#/today`);
      await p.waitForSelector('.hd-home', { timeout: 20000 }).then(() => step('phone: Home has the Holodeck button (next to Live View)', true), () => step('phone: Home has the Holodeck button (next to Live View)', false));
      const next = await p.evaluate(() => { const a = document.querySelector('.lv-home'), b = document.querySelector('.hd-home'); return !!a && a.nextElementSibling === b; });
      step('phone: the Holodeck button sits right under Live View', next);
      await p.evaluate(() => document.querySelector('.hd-home').scrollIntoView({ block: 'center' }));
      await shot(p, 'phone_home.png');
      await p.click('.hd-home');
      await waitHolo(p).then(() => step('phone: #/holo opens, holo.json from the GitHub API', true), async () => step('phone: #/holo opens, holo.json from the GitHub API', false, await p.evaluate(() => location.hash + ' ' + (document.querySelector('#hdNote')?.textContent || ''))));
      step('phone: reads holo.json + holo_hist.json from the live branch (API)', hits.some((h) => h === 'holo.json') && hits.some((h) => h === 'holo_hist.json'), hits.join(','));
      await p.waitForTimeout(1500);
      await shot(p, 'phone_portrait_live.png');
      await core(p, 'phone');
      await replay(p, 'phone');
      await dayPicker(p, 'phone');
      await frames(p, 'phone');
      // full screen the iPhone way (no Fullscreen API: the page covers the screen), as tests/phone_liveview_check.js does
      await p.evaluate(() => { Element.prototype.requestFullscreen = undefined; Element.prototype.webkitRequestFullscreen = undefined; window.scrollTo(0, 0); });
      await p.click('#hdFs'); await p.waitForTimeout(1200);
      const fs1 = await p.evaluate(() => { const r = (window.HOLO.ui.root).getBoundingClientRect(); return { x: r.x, y: r.y, w: r.width, h: r.height, max: window.HOLO.ui.isFs() }; });
      step('phone: full screen covers the screen (portrait)', fs1.max && fs1.x === 0 && fs1.y === 0 && fs1.w === 390 && Math.abs(fs1.h - 844) < 2, JSON.stringify(fs1));
      await shot(p, 'phone_portrait_fullscreen.png');
      await p.setViewportSize({ width: 844, height: 390 }); await p.waitForTimeout(1500);
      const fs2 = await p.evaluate(() => { const r = window.HOLO.ui.root.getBoundingClientRect(), s = document.querySelector('#hdStage').getBoundingClientRect(); return { w: r.width, h: r.height, sw: s.width, sh: s.height }; });
      step('phone: sideways (844x390) the stage fills the screen', fs2.w === 844 && Math.abs(fs2.h - 390) < 2 && fs2.sh > 230 && fs2.sw > 500, JSON.stringify(fs2));
      await shot(p, 'phone_landscape_fullscreen.png');
      await p.evaluate(V('(H.setSpeed(60), H.replay(' + (HOLO.trades.find((t) => t.bot === 'lit').entry.t - 1500) + '), 1)')); await p.waitForTimeout(2500);
      await p.evaluate(V('(H.pause(), 1)'));
      await shot(p, 'phone_landscape_replay.png');
      await p.click('#hdFs'); await p.waitForTimeout(400);
      step('phone: Exit leaves full screen', await p.evaluate(() => !window.HOLO.ui.isFs()));
      await p.setViewportSize({ width: 390, height: 844 });
      // Mission Control link + More > Today
      await p.evaluate(() => { location.hash = '#/mission'; }); await p.waitForTimeout(1200);
      step('phone: Mission Control links to the Holodeck', await p.evaluate(() => !!document.querySelector('#page .hd-home, .hd-mc')));
      await p.evaluate(() => { location.hash = '#/system'; }); await p.waitForTimeout(1200);
      step('phone: More > Today lists the Holodeck', await p.evaluate(() => !!document.querySelector('#page [data-go="holo"]') && PAGES.holo.label === 'Holodeck'), await p.evaluate(() => [...document.querySelectorAll('#page [data-go]')].slice(0, 12).map((x) => x.dataset.go).join(',')));
      await ctx.close();
    }
    // ---------------------------------------------------------------- PC 1440x900
    {
      const ctx = await b.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 });
      const p = await ctx.newPage(); p.on('pageerror', (e) => errors.push('pc: ' + e.message.slice(0, 200)));
      await p.goto(`${PC}/?fxfixed`);
      await p.waitForFunction(() => window.LE && typeof window.LE.go === 'function', null, { timeout: 20000 }).catch(() => null);
      let open = false;
      for (let k = 0; k < 8 && !open; k++) { await p.evaluate(() => window.LE.go('holo')); await p.waitForTimeout(900); open = await p.evaluate(() => !!document.querySelector('#page-holo.active .hd-root')); }
      const navs = await p.evaluate(() => [...document.querySelectorAll('#nav [data-page], #nav [data-goto]')].map((x) => x.dataset.page || x.dataset.goto));
      step('pc: the Holodeck page opens (Main, right after Live View)', open && navs.indexOf('holo') === navs.indexOf('liveview') + 1 && navs.indexOf('liveview') >= 0, navs.join(','));
      await waitHolo(p).then(() => step('pc: GET /api/next/holo drawn', true), async () => step('pc: GET /api/next/holo drawn', false, await p.evaluate(() => document.querySelector('#hdNote')?.textContent || '')));
      await p.waitForTimeout(1500);
      await shot(p, 'pc_live.png');
      await core(p, 'pc');
      // a thought from the Minds timeline: the replay jumps there, then its holographic panel (3D label) opens the card
      await p.evaluate(() => document.querySelector('.hd-tl button[data-jump="thought"]')?.click()); await p.waitForTimeout(1200);
      await p.evaluate(() => document.querySelector('#hdX')?.click()); await p.waitForTimeout(200);
      const thId = await p.evaluate(() => [...document.querySelectorAll('.hd-labs .hd-thought')].find((e) => e.style.visibility === 'visible')?.dataset.id);
      if (thId) { await p.evaluate((id) => document.querySelector(`.hd-labs .hd-thought[data-id="${id}"]`).click(), thId); await p.waitForTimeout(500); }
      step('pc: click a thought panel -> its card', await p.evaluate(() => document.querySelector('#hdCard')?.dataset.kind === 'thought' && !document.querySelector('#hdCard').hidden), thId);
      await p.evaluate(() => document.querySelector('#hdX')?.click());
      // jump to trade from the list: the anatomy card
      const lit = HOLO.trades.find((t) => t.bot === 'lit');
      await p.click('.hd-tabs button[data-t="trades"]'); await p.click(`.hd-list button[data-id="${lit.id}"]`); await p.waitForTimeout(1500);
      const card = await p.evaluate(() => document.querySelector('#hdCard .hd-anat')?.textContent || '');
      step('pc: jump to trade: the setup anatomy 1 Sweep -> 2 Inducement -> 3 Displacement -> 4 CISD -> 5 Entry', /1Sweep.*2Inducement.*3Displacement.*4CISD.*5Entry/.test(card.replace(/\s+/g, '')), card.slice(0, 200));
      await p.click('#hdX');
      await p.evaluate(V('(H.setSpeed(30), H.replay(' + (lit.setup.t_sweep - 600) + '), 1)')); await p.waitForTimeout(3000); await p.evaluate(V('(H.pause(), 1)'));
      await shot(p, 'pc_replay_setup.png');
      await replay(p, 'pc');
      await dayPicker(p, 'pc');
      for (const cam of ['flat', '3d']) { await p.click(`#hdCam button[data-v="${cam}"]`); await p.waitForTimeout(1200); if (cam === 'flat') await shot(p, 'pc_flat.png'); }
      step('pc: camera presets Flat / 3D', await p.evaluate(V('v.counts().preset')) === '3d');
      await p.click('#hdCam button[data-v="fly"]'); await p.waitForTimeout(2500);
      const fly = await p.evaluate(V('v.counts()'));
      await shot(p, 'pc_fly.png');
      step('pc: Fly: the cinematic fly-through runs with the replay', fly.mode === 'fly' && await p.evaluate(V('H.state.playing')), JSON.stringify(fly));
      await p.evaluate(V('(H.pause(), v.preset("3d"), 1)'));
      await frames(p, 'pc');
      await p.evaluate(() => { Element.prototype.requestFullscreen = undefined; Element.prototype.webkitRequestFullscreen = undefined; });
      await p.click('#hdFs'); await p.waitForTimeout(1200);
      const fs = await p.evaluate(() => { const r = window.LE.holo.root.getBoundingClientRect(); return { w: r.width, h: r.height, fs: window.LE.holo.isFs() }; });
      step('pc: full screen covers the window', fs.fs && fs.w === 1440 && Math.abs(fs.h - 900) < 2, JSON.stringify(fs));
      await shot(p, 'pc_fullscreen.png');
      await p.click('#hdFs'); await p.waitForTimeout(300);
      // Live View has the 3D button
      await p.evaluate(() => window.LE.go('liveview')); await p.waitForTimeout(1500);
      step('pc: Live View has a "3D" button to the Holodeck', await p.evaluate(() => !!document.querySelector('#page-liveview .lv-3d[data-goto="holo"]')));
      await ctx.close();
    }
    // ---------------------------------------------------------------- WebGL off: the 2D fallback
    {
      const ctx = await b.newContext({ viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 2 });
      await ctx.addInitScript(() => { const g = HTMLCanvasElement.prototype.getContext; HTMLCanvasElement.prototype.getContext = function (k, o) { return /webgl/i.test(k) ? null : g.call(this, k, o); }; });
      const p = await ctx.newPage(); p.on('pageerror', (e) => errors.push('2d: ' + e.message.slice(0, 200)));
      await ghRoutes(p);
      await p.goto(`${PH}/#/holo`);
      const ok = await p.waitForFunction(() => window.HOLO?.ui?.root?.dataset.r === '2d' && document.querySelectorAll('#hdOv2 .hd-fill').length > 0, null, { timeout: 20000 }).then(() => true, () => false);
      const ink = await p.evaluate(() => { const c = document.querySelector('#hdCv'); const d = c.getContext('2d').getImageData(0, 0, c.width, c.height).data; const s = new Set(); for (let i = 0; i < d.length; i += 4 * 97) s.add((d[i] >> 4) * 256 + (d[i + 1] >> 4) * 16 + (d[i + 2] >> 4)); return { w: c.width, colours: s.size, fills: document.querySelectorAll('#hdOv2 .hd-fill').length, gl: !!document.querySelector('.hd-gl canvas') }; });
      step('WebGL off: the 2D fallback draws the chart + the fills', ok && ink.colours > 25 && ink.fills > 0 && !ink.gl, JSON.stringify(ink));
      await shot(p, 'phone_2d_fallback.png');
      await ctx.close();
    }
  } catch (e) { steps.push(['harness', false, String(e && e.stack || e).slice(0, 400)]); }
  finally { await b.close(); phoneSrv.close(); pcSrv.close(); }
  step('no page errors', errors.length === 0, errors.join(' | '));
  console.log(JSON.stringify({ steps, errors, perf }));
})();
