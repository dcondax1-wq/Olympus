// Dionysus merge check for tests/test_dionysus_merge.py (day-kalshi 2026-11-20): the Kalshi City + Sibyl cards on the Dionysus desk
// (fee table with the K8 row, bet size vs going broke, what the old bot taught, Sibyl's paper picks, Kalshi words, the "Older pages" links),
// in Chromium at 390 x 844. The site's own files are served from <site dir>; k8.json from the K8 fixture; money/sibyl*.json are mocked
// (missing on this checkout). Nothing leaves 127.0.0.1 (every other host is aborted).
//   node tests/dionysus_merge.cjs <site dir (tools/web_public)> <k8 fixture> [--shots <dir>]
// Prints one JSON line: {"steps": [[name, ok, info]], "errors": [...]}.
const http = require('http'), fs = require('fs'), path = require('path');
const { chromium } = require('playwright');
const [dir, fxPath] = [path.resolve(process.argv[2]), process.argv[3]];
const SHOTS = process.argv.indexOf('--shots') > 0 ? process.argv[process.argv.indexOf('--shots') + 1] : '';
const K8 = fs.readFileSync(fxPath, 'utf8');
const SIB = JSON.parse(fs.readFileSync(path.join(dir, 'sibyl', 'fixture.json'), 'utf8'));
const SIB_REAL = JSON.stringify(Object.assign({}, SIB, { demo: false, status: 'ok', note: 'test copy' }));
const FWD = JSON.stringify(SIB.own);
const types = { '.html': 'text/html', '.js': 'text/javascript', '.mjs': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png', '.woff2': 'font/woff2', '.webmanifest': 'application/manifest+json' };
const srv = http.createServer((q, s) => {
  const u = decodeURIComponent(q.url.split('?')[0]), f = path.join(dir, u.endsWith('/') ? u + 'index.html' : u);
  if (!f.startsWith(dir) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) { s.writeHead(404); return s.end('nf'); }
  s.writeHead(200, { 'content-type': types[path.extname(f)] || 'application/octet-stream', 'cache-control': 'no-store' });
  fs.createReadStream(f).pipe(s);
});
const steps = [], errors = [];
const step = (n, ok, info = '') => steps.push([n, !!ok, String(typeof info === 'string' ? info : JSON.stringify(info)).slice(0, 600)]);
const HTML = { status: 200, contentType: 'text/html', body: '<!doctype html><p>not here</p>' };

(async () => {
  await new Promise((r) => srv.listen(0, '127.0.0.1', r));
  const origin = `http://127.0.0.1:${srv.address().port}`;
  const br = await chromium.launch({ args: ['--no-sandbox'] });
  async function open(o) {                    // o: {sibyl: 'real'|'junk'|undefined(404), learned: 'junk'|object, sugg: 'junk', demo}
    const ctx = await br.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: SHOTS ? 2 : 1, serviceWorkers: 'block', colorScheme: 'dark', reducedMotion: o.reduced ? 'reduce' : 'no-preference' });
    const off = [];
    await ctx.route('**/*', (r) => {
      const u = r.request().url();
      if (!u.startsWith(origin)) { off.push(u); return r.abort(); }
      if (/\/kalshi\/k8\.json/.test(u)) return r.fulfill({ status: 200, contentType: 'application/json', body: K8 });
      if (/\/money\/sibyl\.json/.test(u)) return o.sibyl === 'real' ? r.fulfill({ status: 200, contentType: 'application/json', body: SIB_REAL }) : o.sibyl === 'junk' ? r.fulfill(HTML) : r.fulfill({ status: 404, body: 'nf' });
      if (/\/money\/sibyl_forward\.json/.test(u)) return o.sibyl === 'real' ? r.fulfill({ status: 200, contentType: 'application/json', body: FWD }) : o.sibyl === 'junk' ? r.fulfill(HTML) : r.fulfill({ status: 404, body: 'nf' });
      if (/\/kalshicity\/learned\.json/.test(u) && o.learned) return o.learned === 'junk' ? r.fulfill(HTML) : r.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(o.learned) });
      if (/\/kalshicity\/suggestions\.json/.test(u) && o.sugg) return r.fulfill(HTML);
      return r.continue();
    });
    const p = await ctx.newPage();
    p.on('pageerror', (e) => errors.push(String(e).slice(0, 300)));
    await p.goto(origin + '/dionysus/' + (o.demo ? '?demo=1' : ''));
    await p.waitForFunction('window.DIONYSUS && window.DIONYSUS.ready()', null, { timeout: 60000 });
    if (SHOTS) await p.waitForTimeout(2500);   // the kit's opening veil fades before a picture
    return { p, ctx, off };
  }
  const vis = (p, id) => p.evaluate((i) => { const e = document.getElementById(i); return !!e && !e.hidden && e.getBoundingClientRect().height > 0; }, id);
  const txt = (p, id) => p.evaluate((i) => (document.getElementById(i) || {}).textContent || '', id);
  const shot = async (p, name, sel) => { if (!SHOTS) return; const f = path.join(SHOTS, `dionysus-merge-${name}.png`); if (sel) { const b = await p.locator(sel).boundingBox(); const y = await p.evaluate(() => scrollY); await p.screenshot({ path: f, fullPage: true, clip: { x: b.x, y: b.y + y, width: b.width, height: b.height } }); } else await p.screenshot({ path: f }); };
  try {
    // 1. the site as it is: learned + suggestions present, Sibyl's files missing
    let { p, ctx, off } = await open({});
    const order = await p.evaluate(() => ['k8Card', 'bal', 'guardCard', 'wiCard', 'scan', 'feeCard', 'ruinCard', 'lessonCard', 'wordsCard', 'foot'].map((i) => { const e = document.getElementById(i); return e ? e.getBoundingClientRect().top + scrollY : -1; }));
    step('the order: K8 today (first, bar 2026-11-20), the old bot\'s balance, the guard, what-if, scan, then fees, going broke, old lessons, words, the foot', order.every((y, i) => y > 0 && (i === 0 || y > order[i - 1])), order);
    step('K8 today still shows at the top (from ../kalshi/k8.json)', await vis(p, 'k8Card'), await txt(p, 'k8Verdict'));
    const fee = await p.evaluate(() => ({ rows: document.querySelectorAll('#feeRows tr').length, k8: [...document.querySelectorAll('#feeRows tr.k8')].map((t) => t.textContent), lead: document.getElementById('feeLead').textContent, note: document.getElementById('feeNote').textContent }));
    step('fee card: 10 price rows from learned.json, the row nearest K8\'s entry marked (K8), the lead says what K8 must win', await vis(p, 'feeCard') && fee.rows === 10 && fee.k8.length === 1 && /50¢ \(K8\)/.test(fee.k8[0]) && /K8 buys near 5\d¢/.test(fee.lead) && /51\.8%/.test(fee.lead), fee);
    step('fee card: the old bot\'s fee bill is labelled "old bot (retired)"', /old bot \(retired\) made \+\$10\.23 before fees, paid \$73\.05/.test(fee.note), fee.note);
    const ruin = await p.evaluate(() => [...document.querySelectorAll('#ruinRows li')].map((l) => [l.className, l.textContent]));
    step('going-broke card: 6 bet sizes, "(today)" reworded, big fixed bets red, small ones green, labelled old bot (retired)',
      await vis(p, 'ruinCard') && ruin.length === 6 && /29% went broke.*what the old bot used/.test(ruin[0][1]) && /bad/.test(ruin[0][0]) && /ok/.test(ruin[2][0]) && !ruin.some((r) => /\(today\)/.test(r[1])) && /old bot \(retired\)/i.test(await txt(p, 'ruinCard')), ruin);
    const les = await p.evaluate(() => ({ rows: [...document.querySelectorAll('#lessonRows li')].map((l) => l.textContent), head: document.getElementById('lessonHead').textContent, notes: document.querySelectorAll('#lessonNotes li').length, note: document.getElementById('lessonNote').textContent }));
    step('old-lessons card: the headline in cents words, the 4 stop / pause rows with $ and n, 3 notes, "retired" said', await vis(p, 'lessonCard') && les.rows.length === 4 && /Lost: Buying at 90 to 95 cents, -\$248\.30 over 581 bets/.test(les.rows[0]) && /95¢ and up/.test(les.head) && les.notes === 3 && /retired/.test(les.note), les);
    step('Sibyl card hidden while money/sibyl*.json are missing', !(await vis(p, 'sibylCard')));
    const words = await p.evaluate(() => ({ terms: document.querySelectorAll('#wordsCard dt').length, sum: document.querySelector('#wordsCard summary').getBoundingClientRect().height }));
    step('Kalshi words: 9 plain terms behind one 44 px tap', words.terms === 9 && words.sum >= 44, words);
    const older = await p.evaluate(() => [...document.querySelectorAll('nav.older a')].map((a) => [a.getAttribute('href'), a.textContent, Math.round(a.getBoundingClientRect().height)]));
    step('the "Older pages (archive)" footer links ../sibyl/ and ../kalshicity/, each tap >= 44 px', JSON.stringify(older.map((x) => x[0])) === '["../sibyl/","../kalshicity/"]' && older.every((x) => x[2] >= 44) && /Older pages \(archive\)/.test(await p.evaluate(() => document.querySelector('nav.older').textContent)), older);
    const live = await p.evaluate(() => ['feeCard', 'ruinCard', 'lessonCard'].map((i) => document.getElementById(i).textContent).join(' '));
    step('no merged card calls the old bot live or running', !/\b(live now|running|is live)\b/i.test(live));
    step('no sideways scroll at 390 px', await p.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
    step('nothing left 127.0.0.1', off.length === 0, off);
    await shot(p, 'top'); await shot(p, 'fees', '#feeCard'); await shot(p, 'ruin', '#ruinCard'); await shot(p, 'lessons', '#lessonCard');
    await p.evaluate(() => { document.querySelector('#wordsCard details').open = true; }); await shot(p, 'words', '#wordsCard'); await shot(p, 'older', 'nav.older');
    await ctx.close();
    // 2. Sibyl's files present (a non-demo copy of its fixture + its paper ledger)
    ({ p, ctx } = await open({ sibyl: 'real' }));
    const sb = await p.evaluate(() => ({ rows: [...document.querySelectorAll('#sibylRows li')].map((l) => l.textContent), head: document.getElementById('sibylHead').textContent, own: document.getElementById('sibylOwn').textContent, pill: document.getElementById('sibylPill').textContent, all: document.getElementById('sibylCard').textContent }));
    step('Sibyl card: the count of picks, up to 3 picks with cautious edge + n, its own paper record, said to be built from the old bot\'s study',
      await vis(p, 'sibylCard') && sb.rows.length === 3 && /^3 paper picks of 12 kinds of bet/.test(sb.head) && /95–97¢.*n=640 bets/.test(sb.rows[0]) && /paper record since 2026-10-27/.test(sb.own) && /old bot's study \(retired\)/.test(sb.all), sb);
    await shot(p, 'sibyl', '#sibylCard');
    await ctx.close();
    // 3. junk everywhere: the merged data cards hide, the rest of the desk still works
    ({ p, ctx } = await open({ sibyl: 'junk', learned: 'junk', sugg: 'junk' }));
    const hid = await Promise.all(['feeCard', 'ruinCard', 'lessonCard', 'sibylCard'].map((i) => vis(p, i)));
    step('junk files (HTML for JSON): fee / going broke / lessons / Sibyl cards hidden; K8 today, the scan and the words still there', hid.every((x) => !x) && await vis(p, 'k8Card') && await vis(p, 'wordsCard') && (await txt(p, 'scan')).length > 20, hid);
    await ctx.close();
    // 4. a JSON object of the wrong shape
    ({ p, ctx } = await open({ learned: { fees: { rows: 'x' }, ruin: { rows: [{ policy: '<b>x</b>', p_ruin: 7 }], bankroll: 55 }, headline: 5 } }));
    step('a learned.json of the wrong shape hides the fee and broke cards (no error)', !(await vis(p, 'feeCard')) && !(await vis(p, 'ruinCard')));
    await ctx.close();
    // 5. the DEMO desk: the merged data cards stay hidden (no example numbers dressed as the old bot's)
    ({ p, ctx } = await open({ demo: true }));
    step('?demo=1: the merged data cards stay hidden, the words card shows', (await Promise.all(['feeCard', 'ruinCard', 'lessonCard', 'sibylCard'].map((i) => vis(p, i)))).every((x) => !x) && await vis(p, 'wordsCard'));
    await ctx.close();
    // 6. FX (day-kalshi 2026-11-20, owner: "some 3D, some effects"): the terminal colours (no gold), nqfx.js only after the first paint, reduced motion = still
    ({ p, ctx } = await open({}));
    await p.waitForFunction('window.OLYMPUS_NQFX && window.DIONYSUS.fx().started', null, { timeout: 30000 }).catch(() => {});
    await p.waitForTimeout(600);
    const look = await p.evaluate(() => {
      const gold = (c) => { for (const m of String(c).matchAll(/rgba?\(([\d.]+), ([\d.]+), ([\d.]+)(?:, ([\d.]+))?\)/g)) { const r = +m[1], g = +m[2], b = +m[3], a = m[4] == null ? 1 : +m[4]; if (a < 0.15) continue;
        const mx = Math.max(r, g, b), mn = Math.min(r, g, b), l = (mx + mn) / 510, sat = mx === mn ? 0 : (mx - mn) / (255 - Math.abs(mx + mn - 255)); let h = 0;
        if (mx !== mn) { h = mx === r ? ((g - b) / (mx - mn)) % 6 : mx === g ? (b - r) / (mx - mn) + 2 : (r - g) / (mx - mn) + 4; h = (h * 60 + 360) % 360; }
        if (h >= 25 && h <= 60 && sat > 0.3 && l > 0.2 && l < 0.85) return m[0]; } return null; };
      const bad = [];
      for (const e of document.querySelectorAll('main#app, main#app *')) { if (!e.getClientRects().length) continue; const cs = getComputedStyle(e);
        for (const k of ['color', 'backgroundColor', 'borderTopColor', 'backgroundImage', 'boxShadow', 'outlineColor']) { const g = gold(cs[k]); if (g) bad.push(`${e.id || e.className || e.tagName} ${k} ${g}`); } }
      const k8 = getComputedStyle(document.getElementById('k8Card')), hero = getComputedStyle(document.getElementById('heroCard'));
      const pt = performance.getEntriesByType('paint').find((x) => x.name === 'first-contentful-paint') || performance.getEntriesByType('paint')[0];
      const fx = performance.getEntriesByType('resource').find((r) => /\/olympus\/nqfx\.js/.test(r.name));
      return { bad: bad.slice(0, 6), n: bad.length, bg: getComputedStyle(document.body).backgroundColor, glow: k8.boxShadow, edge: hero.backgroundImage.slice(0, 160),
        paint: pt ? pt.startTime : null, fx: fx ? fx.startTime : null, tag: !!document.querySelector('script[src*="nqfx.js"][data-fx="dionysus"]'), running: document.getAnimations().filter((a) => a.playState === 'running').length };
    });
    step('FX look: no gold computed anywhere on the desk (cards, pills, tiles, text); navy base #070b14 (the page sky); K8 card lit cyan; the cards have a cyan -> violet gradient edge',
      look.n === 0 && look.bg === 'rgb(7, 11, 20)' && /rgba\(34, 211, 238/.test(look.glow) && /rgba\(34, 211, 238/.test(look.edge) && /rgba\(139, 92, 246/.test(look.edge), look);
    step('FX: olympus/nqfx.js is added by the page only after the first paint (load + idle), and it ran', look.tag && look.paint != null && look.fx != null && look.fx > look.paint, [look.paint, look.fx, look.tag]);
    step('FX: with motion welcome the hero sheen runs', look.running >= 1, look.running);
    await ctx.close();
    ({ p, ctx } = await open({ reduced: true }));
    await p.waitForFunction('window.DIONYSUS.fx().started', null, { timeout: 30000 }).catch(() => {});
    await p.waitForTimeout(2500);
    const still = await p.evaluate(() => ({ running: document.getAnimations().filter((a) => a.playState === 'running').map((a) => (a.animationName || a.constructor.name) + ' ' + ((a.effect && a.effect.target && (a.effect.target.id || a.effect.target.className)) || '')), bal: document.getElementById('bal').textContent, k8: document.getElementById('k8Pool').textContent }));
    step('FX: reduced motion = nothing moves (no running animation after the kit loaded), the balance and K8 numbers show their final text', still.running.length === 0 && /^\$\d/.test(still.bal) && /\d+%/.test(still.k8), still);
    await ctx.close();
    step('no page error in any run', errors.length === 0, errors);
  } catch (e) { step('the harness ran', false, String(e && e.stack || e)); }
  await br.close(); srv.close();
  console.log(JSON.stringify({ steps, errors }));
})();
