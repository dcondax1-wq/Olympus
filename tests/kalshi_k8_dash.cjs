// K8 day dashboard check for tests/test_kalshi_k8_dash.py (day-kalshi 2026-11-20): the Kalshi page's K8 status card (today's windows +
// countdowns, Thanksgiving skip, price vs fair, the bet log, the day / week / peak bars, edge health) and the Dionysus "K8 today" panel,
// in Chromium at 390 x 844 with a frozen clock. Feeds: the PC card through a stub ntfy host (status_feed.json -> ntfy.example), the site's
// kalshi/k8.json from tests/fixtures/k8_plan_sample.json (or 404 / junk). Nothing leaves 127.0.0.1 (every other host is aborted).
//   node tests/kalshi_k8_dash.cjs <site dir (tools/web_public)> <k8 fixture> [--shots <dir>]
// Prints one JSON line: {"steps": [[name, ok, info]], "errors": [...]}.
const http = require('http'), fs = require('fs'), path = require('path');
const { chromium } = require('playwright');
const [dir, fxPath] = [path.resolve(process.argv[2]), process.argv[3]];
const SHOTS = process.argv.indexOf('--shots') > 0 ? process.argv[process.argv.indexOf('--shots') + 1] : '';
const FX = fs.readFileSync(fxPath, 'utf8');
const types = { '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png', '.woff2': 'font/woff2', '.webmanifest': 'application/manifest+json' };
const srv = http.createServer((q, s) => {
  const u = decodeURIComponent(q.url.split('?')[0]), f = path.join(dir, u.endsWith('/') ? u + 'index.html' : u);
  if (!f.startsWith(dir) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) { s.writeHead(404); return s.end('nf'); }
  s.writeHead(200, { 'content-type': types[path.extname(f)] || 'application/octet-stream', 'cache-control': 'no-store' });
  fs.createReadStream(f).pipe(s);
});
const ET = (iso) => new Date(iso).getTime();              // the tests' moments are written with their New York offset (-05:00)
const steps = [], errors = [];
const step = (n, ok, info = '') => steps.push([n, !!ok, String(typeof info === 'string' ? info : JSON.stringify(info)).slice(0, 600)]);
const k8old = { m: 'P', nx: null, b: 55, s: 2.5, td: [1, 1, 1.61], l: 'WWLWLLWWWL', wk: [4.3, 13.75], dd: [6.2, 19.25], wr: [41, 71], lp: 1 };
const k8new = (x) => Object.assign({}, k8old, { td: [1, 0, 0], dy: [2.15, 8], e: [70, 72, 52.1],
  lg: [['g17', '11-19', 4, 53, 1.79, 'W'], ['s17', '11-19', 4, 55, -2.2, 'L'], ['g5', '11-20', 4, 51, 1.84, 'W'], ['g17', '11-20', 4, 53, 1.79, 'W'], ['g5', '11-23', 4, 52, null, 'o']] }, x || {});
const card = (st, k8, u) => ({ kind: 'kalshi_live_pub', v: 1, st, net: 0, f: 0, o: 0, cap: 55, stop: 8, u, k8 });

(async () => {
  await new Promise((r) => srv.listen(0, '127.0.0.1', r));
  const origin = `http://127.0.0.1:${srv.address().port}`;
  const br = await chromium.launch({ args: ['--no-sandbox'] });
  async function open(o) {                                  // o: {at, card, k8: 'fx' | '404' | 'junk' | object, w}
    const ctx = await br.newContext({ viewport: { width: o.w || 390, height: 844 }, deviceScaleFactor: SHOTS ? 2 : 1, serviceWorkers: 'block', colorScheme: 'dark' });
    const off = [];
    await ctx.route('**/*', (r) => {
      const u = r.request().url();
      if (u.startsWith(origin)) {
        if (/\/kalshi\/k8\.json/.test(u)) {
          if (o.k8 === 'fx') return r.fulfill({ status: 200, contentType: 'application/json', body: FX });
          if (o.k8 === 'junk') return r.fulfill({ status: 200, contentType: 'text/html', body: '<!doctype html><p>not here</p>' });
          if (o.k8 && typeof o.k8 === 'object') return r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(o.k8) });
          return r.fulfill({ status: 404, body: 'nf' });
        }
        if (/\/status_feed\.json/.test(u)) return r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ topic: 'k8demo', ntfy: 'https://ntfy.example' }) });
        return r.continue();
      }
      if (u.startsWith('https://ntfy.example/') && o.card) {
        const ext = JSON.stringify({ event: 'message', time: 1, message: JSON.stringify({ kind: 'le-live-ext', t: 2, part: 0, of: 1, x: { kalshi_live: o.card } }) }) + '\n';
        return r.fulfill({ status: 200, contentType: 'application/x-ndjson', headers: { 'access-control-allow-origin': '*' }, body: ext });
      }
      off.push(u);
      return r.abort();
    });
    const p = await ctx.newPage();
    p.on('pageerror', (e) => errors.push(String(e).slice(0, 300)));
    await p.clock.setFixedTime(new Date(o.at));
    await p.goto(origin + (o.app === 'dionysus' ? `/dionysus/?at=${new Date(o.at).toISOString()}` : '/kalshi/'));
    if (o.app === 'dionysus') await p.waitForFunction('window.DIONYSUS && window.DIONYSUS.ready()', null, { timeout: 60000 });
    else {
      await p.waitForFunction('document.querySelectorAll("#k8s-w li").length === 5', null, { timeout: 30000 });
      if (o.card) await p.waitForFunction('document.querySelectorAll("#k8s .k8s-l span").length > 0', null, { timeout: 30000 });
      await p.waitForTimeout(1500);                        // k8.json (3 s at most) and one countdown tick
    }
    return { ctx, p, off };
  }
  const T = (p, sel) => p.evaluate((s) => { const e = document.querySelector(s); return e ? e.innerText : null; }, sel);
  const geo = (p) => p.evaluate(() => { const W = innerWidth, de = document.documentElement, e = document.getElementById('k8s'), r = e.getBoundingClientRect();
    const cut = [...e.querySelectorAll('li, dd, span, b, p')].filter((x) => x.scrollWidth > x.clientWidth + 1 && getComputedStyle(x).display !== 'inline').length;
    return { side: de.scrollWidth <= de.clientWidth, gutter: r.left >= 15.5 && r.right <= W - 15.5, cut }; });
  const shot = async (p, name, at) => {
    if (!SHOTS) return;
    await p.evaluate((sel) => { const e = document.querySelector(sel) || document.getElementById('k8s'); const top = sel === '#k8s' || sel === '#k8d'; e.scrollIntoView({ block: top ? 'start' : 'end' }); window.scrollBy(0, top ? -12 : 12); }, at || '#k8s');
    await p.waitForTimeout(400);
    await p.screenshot({ path: path.join(SHOTS, name) });
  };
  try {
    // 1. an OLD PC card (no dy / e / lg) and no k8.json: the windows still render, the new parts hide or fall back, the old card stays
    let { ctx, p, off } = await open({ at: '2026-11-20T03:00:00-05:00', card: card('paper', k8old, '2026-11-20T07:59:00Z'), k8: '404' });
    let w = await T(p, '#k8s-w'), y = await T(p, '#k8s-y'), all = await T(p, '#k8s');
    const rows = await p.evaluate(() => [...document.querySelectorAll('#k8s-w li')].map((li) => [li.dataset.leg, li.className, li.querySelector('b').textContent, li.querySelector('em').textContent]));
    step('w1. Fri 11-20 03:00 ET: today\'s 5 windows in New York time, a countdown each (gold DOWN 05:15 in 2h 15m, silver DOWN 16:00 in 13h 0m, the two UP legs 16:45 in 13h 45m)',
      w.includes('Today, Fri 11-20') && JSON.stringify(rows) === JSON.stringify([['g5', 'lv', '05:15', 'in 2h 15m'], ['s5', 'pp', '05:15', 'in 2h 15m'], ['s16', 'pp', '16:00', 'in 13h 0m'], ['g17', 'lv', '16:45', 'in 13h 45m'], ['s17', 'lv', '16:45', 'in 13h 45m']]), rows);
    const pap = await p.evaluate(() => { const a = getComputedStyle(document.querySelector('#k8s-w li.lv')), b = getComputedStyle(document.querySelector('#k8s-w li.pp')); return [parseFloat(a.fontSize), parseFloat(b.fontSize), +b.opacity]; });
    step('w2. the 2 paper legs are smaller and greyed and say "paper only"', pap[1] < pap[0] && pap[2] < 1 && (w.match(/paper only/g) || []).length === 2, pap);
    step('d1. old PC card + no k8.json: no price-vs-fair, no bet log (lg missing), edge health says "No numbers yet"; the old card text stays (PAPER, $55.00, the week / peak bars)',
      !(await p.$('#k8s-pf')) && !(await p.$('#k8s-log')) && y.includes('No numbers yet') && all.includes('PAPER') && all.includes('$55.00') && all.includes('−$4.30 of −$13.75') && all.includes('−$6.20 of −$19.25'), y);
    step('b1. old card: the today bar falls back to the day stop (−$8.00) with nothing used', all.includes('Today (day stop)') && all.includes('$0.00 of −$8.00'), all.slice(0, 600));
    await p.clock.setFixedTime(new Date('2026-11-20T05:15:30-05:00'));
    await p.waitForTimeout(1300);
    let cd = await p.evaluate(() => [...document.querySelectorAll('#k8s-w em')].map((e) => [e.textContent, e.className]));
    step('w3. 05:15:30 ET: gold DOWN says "now" (green), the evening legs count down', cd[0][0] === 'now' && cd[0][1] === 'now' && cd[3][0] === 'in 11h 29m', cd);
    await p.clock.setFixedTime(new Date('2026-11-20T16:50:00-05:00'));
    await p.waitForTimeout(1300);
    cd = await p.evaluate(() => [...document.querySelectorAll('#k8s-w em')].map((e) => e.textContent));
    step('w4. 16:50 ET: the morning legs and silver 16:00 "done", the UP legs "now"', JSON.stringify(cd) === JSON.stringify(['done', 'done', 'done', 'now', 'now']), cd);
    await p.clock.setFixedTime(new Date('2026-11-20T17:10:00-05:00'));
    await p.waitForTimeout(1300);
    w = await T(p, '#k8s-w');
    step('w5. after the last window on Friday: the list moves to "Next, Mon 11-23" with counts in days of hours', w.includes('Next, Mon 11-23') && w.includes('in 60h 5m'), w);
    const g1 = await geo(p);
    step('w6. 390 px: no sideways scroll, the card inside the 16 px gutters, nothing cut off', g1.side && g1.gutter && g1.cut === 0, g1);
    step('w7. nothing asked outside 127.0.0.1 but the stub status host', off.length === 0, off.slice(0, 3));
    await ctx.close();

    // 2. Thanksgiving: Thu 11-26 03:00 ET, the morning legs run, the evening legs are skipped (CME holiday)
    ({ ctx, p } = await open({ at: '2026-11-26T03:00:00-05:00', k8: 'fx' }));
    cd = await p.evaluate(() => [...document.querySelectorAll('#k8s-w em')].map((e) => e.textContent));
    w = await T(p, '#k8s-w');
    step('t1. Thanksgiving Thu 11-26: gold / silver DOWN 05:15 count down, silver 16:00 and both UP legs say "skipped (CME holiday)"',
      w.includes('Today, Thu 11-26') && JSON.stringify(cd) === JSON.stringify(['in 2h 15m', 'in 2h 15m', 'skipped (CME holiday)', 'skipped (CME holiday)', 'skipped (CME holiday)']), cd);
    y = await T(p, '#k8s-y');
    step('h1. no PC card, k8.json there: edge health from the pool labelled "Kalshi results, not our bets" (63% / 70% / 51.9¢ = Healthy)',
      y.includes('Kalshi results, not our bets') && y.includes('63%') && y.includes('70%') && y.includes('51.9¢') && (await p.getAttribute('#k8s-eh', 'data-v')) === 'ok' && y.includes('Healthy'), y);
    step('p1. no PC card: price vs fair from Kalshi\'s last price (gold DOWN paid 52¢ · fair 71¢ · edge +19¢)', y.includes('paid 52¢ · fair 71¢ · edge +19¢'), y);
    await ctx.close();

    // 3. LIVE Monday 11-23 05:20 ET with the new card fields + k8.json: price vs fair colours, the bet log, the three bars, Healthy
    ({ ctx, p } = await open({ at: '2026-11-23T05:20:00-05:00', card: card('live', k8new({ m: 'L' }), '2026-11-23T10:19:00Z'), k8: 'fx' }));
    y = await T(p, '#k8s-y'); all = await T(p, '#k8s');
    const pf = await p.evaluate(() => [...document.querySelectorAll('#k8s-pf li')].map((li) => [li.dataset.leg, li.innerText.replace(/\s+/g, ' '), (li.querySelector('b') || {}).className]));
    step('p2. price vs fair per live leg: gold DOWN today = our bet (paid 52¢ · fair 71¢ · edge +19¢, green); gold UP Kalshi 53¢ vs 73¢ +20¢ green; silver UP 55¢ vs 53¢ edge −2¢ red',
      pf.length === 3 && pf[0][0] === 'g5' && pf[0][1].includes('our bet today') && pf[0][1].includes('paid 52¢ · fair 71¢ · edge +19¢') && pf[0][2] === 'k8-g'
      && pf[1][1].includes('paid 53¢ · fair 73¢ · edge +20¢') && pf[1][2] === 'k8-g' && pf[2][1].includes('paid 55¢ · fair 53¢ · edge −2¢') && pf[2][2] === 'k8-r', pf);
    const red = await p.evaluate(() => [getComputedStyle(document.querySelector('#k8s-pf .k8-g')).color, getComputedStyle(document.querySelector('#k8s-pf .k8-r')).color]);
    step('p3. the green and red edges are different colours', red[0] !== red[1], red);
    const log = await p.evaluate(() => [...document.querySelectorAll('#k8s-log li')].map((li) => li.innerText));
    step('l1. the bet log: the last 5 bets, newest first, in plain words ("Mon 11-23 gold DOWN 05:15: 4 at 52¢, open", "Fri 11-20 gold UP 16:45: 4 at 53¢, WON +$1.79", "Thu 11-19 silver UP 16:45: 4 at 55¢, LOST −$2.20")',
      log.length === 5 && log[0] === 'Mon 11-23 gold DOWN 05:15: 4 at 52¢, open' && log[1] === 'Fri 11-20 gold UP 16:45: 4 at 53¢, WON +$1.79' && log[2] === 'Fri 11-20 gold DOWN 05:15: 4 at 51¢, WON +$1.84'
      && log[3] === 'Thu 11-19 silver UP 16:45: 4 at 55¢, LOST −$2.20' && (await T(p, '#k8s-log')).includes('(live)'), log);
    step('b2. three stop bars: today −$2.15 of −$8.00, this week −$4.30 of −$13.75, from the peak −$6.20 of −$19.25',
      all.includes('Today (day stop)') && all.includes('−$2.15 of −$8.00') && all.includes('−$4.30 of −$13.75') && all.includes('−$6.20 of −$19.25') && (await p.$$('#k8s .k8s-b i')).length === 3, all.slice(0, 900));
    step('h2. edge health from our bets (live): 70% / 72% won, 52.1¢ paid = Healthy', y.includes('our bets (live)') && y.includes('70%') && y.includes('72%') && y.includes('52.1¢') && (await p.getAttribute('#k8s-eh', 'data-v')) === 'ok', y);
    step('m1. the live card says LIVE and the g5 window is "now"', all.includes('LIVE') && (await p.textContent('#k8w-0')) === 'now');
    const g2 = await geo(p);
    step('m2. live, 390 px: no sideways scroll, inside the gutters, nothing cut off', g2.side && g2.gutter && g2.cut === 0, g2);
    await shot(p, 'kalshi-k8-live.png');
    await ctx.close();

    // 3b. each live bet's last 20 windows (card ls): one would pause (display only), the others plain; no ls = no block
    ({ ctx, p } = await open({ at: '2026-11-23T05:20:00-05:00', card: card('paper', k8new({ ls: [['g5', 15, 20, 0, 0], ['g17', 13, 20, 0, 0], ['s17', 9, 20, 1, 0]] }), '2026-11-23T10:19:00Z'), k8: 'fx' }));
    const ls = await p.evaluate(() => [...document.querySelectorAll('#k8s-ls li')].map((li) => [li.dataset.leg, li.innerText, li.className]));
    const lh = await T(p, '#k8s-ls');
    step('s1. each bet\'s last 20: "gold DOWN: won 15 of the last 20", silver UP in red "would pause: won 9 of the last 20 (resumes at 12)", and it says the bot does not pause on it yet',
      ls.length === 3 && ls[0][1].includes('won 15 of the last 20') && ls[2][1].includes('would pause: won 9 of the last 20 (resumes at 12)') && ls[2][2] === 'off'
      && lh.includes('shown only'), [ls, lh]);
    await shot(p, 'kalshi-k8-legs.png', '#k8s-ls');
    await ctx.close();
    ({ ctx, p } = await open({ at: '2026-11-23T05:20:00-05:00', card: card('live', k8new({ m: 'L', ls: [['s17', 9, 20, 1, 1]] }), '2026-11-23T10:19:00Z'), k8: 'fx' }));
    const ls2 = await T(p, '#k8s-ls');
    step('s2. when the bot obeys the rule: "silver UP paused: won 9 of the last 20 (resumes at 12)"',
      ls2.includes('paused: won 9 of the last 20 (resumes at 12)') && !ls2.includes('shown only'), ls2);
    await ctx.close();

    // 3c. K8 LIVE DAY (round 3): the big countdown to the next LIVE window, what the bot will do, $ left before each stop, the help box
    ({ ctx, p } = await open({ at: '2026-11-23T14:30:00-05:00', card: card('paper', k8new({ td: [1, 1, 1.61], dy: [0, 8], wk: [0, 13.75], dd: [0, 19.25] }), '2026-11-23T19:29:00Z'), k8: 'fx' }));
    let dd = { big: await T(p, '#k8d-big'), lab: await T(p, '#k8d-lab'), at: await T(p, '#k8d-at'), x: await T(p, '#k8d-x'), help: await T(p, '#k8d-help') };
    step('v1. Mon 14:30 ET, PAPER: big countdown 2:15:20 to the 16:45 live bet (gold UP + silver UP), "PAPER: ... records ... with no money", results at 17:00',
      /^2:15:(20|19|18)$/.test(dd.big) && dd.lab.includes('gold UP + silver UP') && dd.at.includes('16:45 ET') && dd.at.includes('17:00') && dd.x.includes('PAPER:') && dd.x.includes('no money'), dd);
    const sl = await p.evaluate(() => [...document.querySelectorAll('#k8d-s div')].map((x) => x.innerText.replace(/\s+/g, ' ')));
    step('v2. $ left before each stop: today $8.00 of $8.00, week $13.75 of $13.75, from the peak $19.25 of $19.25; room for 3 more bets (2 of today\'s 3 left)',
      sl.length === 3 && sl[0].includes('$8.00 of $8.00') && sl[1].includes('$13.75 of $13.75') && sl[2].includes('$19.25 of $19.25')
      && (await T(p, '#k8d-fit')).includes('Room for 3 more') && (await T(p, '#k8d-fit')).includes('2 of today\'s 3 left'), [sl, await T(p, '#k8d-fit')]);
    const lg2 = await p.evaluate(() => [...document.querySelectorAll('#k8d-legs li')].map((x) => [x.dataset.leg, x.innerText.replace(/\s+/g, ' ')]));
    step('v3. the 2 legs of the window with the last price vs fair (gold UP last 53¢ · fair 73¢ · +20¢)', lg2.length === 2 && lg2[0][0] === 'g17' && lg2[0][1].includes('last 53¢ · fair 73¢') && lg2[0][1].includes('+20¢'), lg2);
    step('v4. "If something looks wrong": the PC page STOP (:8444/kalshi-live/), ZEUS Safety PAUSE / KILL, KALSHI_STOP.bat, the Kalshi app; filled bets settle by themselves',
      dd.help.includes(':8444/kalshi-live/') && dd.help.includes('STOP (off now)') && dd.help.includes('ZEUS Safety') && dd.help.includes('KALSHI_STOP.bat') && dd.help.includes('Kalshi app') && dd.help.includes('settles by itself'), dd.help);
    await shot(p, 'kalshi-k8-liveday.png', '#k8d');
    await shot(p, 'kalshi-k8-liveday-help.png', '#k8d-help');
    await ctx.close();
    ({ ctx, p } = await open({ at: '2026-11-23T14:30:00-05:00', card: card('live', k8new({ m: 'L', td: [1, 0, -2.15], dy: [2.15, 8], wk: [11.0, 13.75], dd: [11.0, 19.25] }), '2026-11-23T19:29:00Z'), k8: 'fx' }));
    dd = { x: await T(p, '#k8d-x'), fit: await T(p, '#k8d-fit') };
    step('v5. LIVE with $2.75 left this week: "At 16:45:20 ET it buys 1 of gold UP + silver UP" (only one $2.59 bet fits), room for 1',
      dd.x.includes('At 16:45:20 ET it buys 1 of gold UP + silver UP') && dd.fit.includes('Room for 1 more'), dd);
    await ctx.close();
    ({ ctx, p } = await open({ at: '2026-11-23T14:30:00-05:00', card: card('live', k8new({ m: 'L', td: [1, 0, -2.15], dy: [2.15, 8], wk: [12.0, 13.75], dd: [12, 19.25] }), '2026-11-23T19:29:00Z'), k8: 'fx' }));
    dd = { x: await T(p, '#k8d-x') };
    step('v6. LIVE with $1.75 left this week: "It will NOT bet: a stop is reached"', dd.x.includes('It will NOT bet') && dd.x.includes('a stop is reached'), dd);
    await ctx.close();
    ({ ctx, p } = await open({ at: '2026-11-26T08:00:00-05:00', card: card('paper', k8new(), '2026-11-26T12:59:00Z'), k8: 'fx' }));
    dd = { lab: await T(p, '#k8d-lab'), at: await T(p, '#k8d-at') };
    step('v7. Thanksgiving Thu 08:00 ET: the evening skips, so the next live bet is Fri 11-27 05:15 gold DOWN', dd.lab.includes('gold DOWN') && dd.at.includes('Fri 11-27') && dd.at.includes('05:15'), dd);
    await ctx.close();

    // 4. the verdicts: Watch (within 5 points of a line) and OFF line crossed (win rate, then price creep)
    for (const [e, v, word, name] of [[[61, 66, 50], 'watch', 'Watch', 'h3. 61% won last 30 (within 5 of 58%) = Watch'],
      [[55, 60, 50], 'off', 'OFF line crossed', 'h4. 55% won last 30 (under 58%) = OFF line crossed'],
      [[70, 70, 59.4], 'off', 'OFF line crossed', 'h5. paying 59.4¢ on average (over 58¢) = OFF line crossed (price creep)'],
      [[70, 70, 54], 'watch', 'Watch', 'h6. paying 54¢ (within 5 of 58¢) = Watch'], [[null, null, null], 'ok', 'Healthy', 'h7. our e all null (no bets yet): falls back to the pool (Kalshi results), Healthy']]) {
      ({ ctx, p } = await open({ at: '2026-11-23T05:20:00-05:00', card: card('paper', k8new({ e }), '2026-11-23T10:19:00Z'), k8: 'fx' }));
      y = await T(p, '#k8s-eh');
      const cl = await p.evaluate(() => [...document.querySelectorAll('#k8s-eh .k8e-g b')].map((b) => b.className));
      step(name, (await p.getAttribute('#k8s-eh', 'data-v')) === v && y.includes(word) && (e[0] == null ? y.includes('Kalshi results, not our bets') : y.includes('our bets (paper)')), [y, cl]);
      if (v === 'ok' && e[0] == null) await shot(p, 'kalshi-k8-paper.png');
      await ctx.close();
    }

    // 5. junk k8.json (the host's HTML page) and junk card fields: treated as absent, nothing breaks, nothing runs
    ({ ctx, p } = await open({ at: '2026-11-23T04:00:00-05:00', card: card('paper', Object.assign({}, k8old, { dy: 'x', e: 'bad', lg: [null, 5, ['<img src=x onerror=window.__pwn=1>', '<b>', 'x', '<i>', null, 'W']] }), '2026-11-23T08:59:00Z'), k8: 'junk' }));
    y = await T(p, '#k8s-y');
    step('j1. junk k8.json + junk card fields: no price-vs-fair, the bad bet shows as "a K8 bet", no markup injected, edge health "No numbers yet"',
      !(await p.$('#k8s-pf')) && y.includes('a K8 bet') && y.includes('size not known') && y.includes('No numbers yet') && (await p.evaluate(() => !window.__pwn && !document.querySelector('#k8s img, #k8s script'))), y);
    await ctx.close();

    // 6. Dionysus "K8 today": the panel from ../kalshi/k8.json; absent / junk = hidden
    ({ ctx, p } = await open({ app: 'dionysus', at: '2026-11-23T10:30:00Z', k8: 'fx' }));
    const d = await p.evaluate(() => ({ hidden: document.getElementById('k8Card').hidden, t: document.getElementById('k8Card').innerText, legs: document.querySelectorAll('#k8Legs li').length,
      chips: [...document.querySelectorAll('#k8Legs li')].map((li) => li.querySelectorAll('.k8wl i').length), pill: document.getElementById('k8Verdict').textContent,
      side: document.documentElement.scrollWidth <= innerWidth + 1 }));
    step('dz1. Dionysus "K8 today": 3 live legs with New York times and fair prices (05:15 ET gold DOWN fair 71¢, 16:45 ET gold UP fair 73¢, silver UP 53¢), 10 W/L each, pool 63% / 70% vs OFF under 58%, the noise sentence, Healthy',
      !d.hidden && d.legs === 3 && JSON.stringify(d.chips) === '[10,10,10]' && d.t.includes('05:15 ET gold DOWN') && d.t.includes('fair 71¢') && d.t.includes('16:45 ET gold UP') && d.t.includes('fair 53¢')
      && d.t.includes('63%') && d.t.includes('70%') && d.t.includes('OFF under 58%') && d.t.includes('happens by luck about 3 times in 100') && d.pill === 'Healthy' && d.side, d);
    if (SHOTS) { await p.evaluate(() => { document.getElementById('k8Card').scrollIntoView({ block: 'start' }); window.scrollBy(0, -110); }); await p.waitForTimeout(400); await p.screenshot({ path: path.join(SHOTS, 'dionysus-k8.png') }); }
    await ctx.close();
    for (const k of ['404', 'junk']) {
      ({ ctx, p } = await open({ app: 'dionysus', at: '2026-11-23T10:30:00Z', k8: k }));
      step(`dz2. Dionysus with k8.json ${k === '404' ? 'missing' : 'junk (HTML)'}: the panel hides, the desk still renders`,
        await p.evaluate(() => document.getElementById('k8Card').hidden && document.getElementById('bal').textContent.startsWith('$')));
      await ctx.close();
    }
  } catch (e) {
    step('harness error', false, String(e && e.stack || e).slice(0, 600));
  }
  step('z. no page errors', errors.length === 0, errors.slice(0, 3));
  await br.close();
  srv.close();
  console.log(JSON.stringify({ steps, errors }));
})();
