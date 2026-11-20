// Browser check for tests/test_web_leads.py: agency/leads/ with a leads.json (FICTIONAL businesses from the test fixture), then without.
//   node tests/web_leads_page.cjs <site dir (tools/web_public)> <leads.json>
const http = require('http'), fs = require('fs'), path = require('path');
const { chromium } = require('playwright');
const [SITE, LEADS] = process.argv.slice(2);
const MIME = { '.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.json': 'application/json', '.svg': 'image/svg+xml', '.png': 'image/png' };
const S = { leads: 'ok' };
const srv = http.createServer((q, r) => {
  const u = decodeURIComponent(q.url.split('?')[0]);
  if (u === '/agency/leads/leads.json') {
    if (S.leads !== 'ok') { r.writeHead(404); r.end(); return; }
    r.writeHead(200, { 'Content-Type': 'application/json' }); r.end(fs.readFileSync(LEADS)); return;
  }
  const f = path.join(SITE, u.endsWith('/') ? u + 'index.html' : u);
  if (!f.startsWith(SITE) || !fs.existsSync(f) || fs.statSync(f).isDirectory()) { r.writeHead(404); r.end(); return; }
  r.writeHead(200, { 'Content-Type': MIME[path.extname(f)] || 'application/octet-stream' }); r.end(fs.readFileSync(f));
});
const steps = [];
const step = (n, ok, info = '') => steps.push([n, !!ok, String(typeof info === 'string' ? info : JSON.stringify(info)).slice(0, 600)]);
(async () => {
  await new Promise((r) => srv.listen(0, '127.0.0.1', r));
  const origin = `http://127.0.0.1:${srv.address().port}`;
  const br = await chromium.launch({ args: ['--no-sandbox'] });
  const ctx = await br.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: process.env.SHOTS ? 2 : 1 });
  await ctx.route('**/*', (r) => (r.request().url().startsWith(origin) ? r.continue() : r.abort()));
  const p = await ctx.newPage();
  const errs = []; p.on('pageerror', (e) => errs.push(String(e).slice(0, 200)));
  try {
    await p.goto(origin + '/agency/leads/');
    await p.waitForFunction('window.WEBLEADS && window.WEBLEADS.ready()', null, { timeout: 30000 });
    const T = (s) => p.evaluate((x) => { const e = document.querySelector(x); return e ? e.innerText : null; }, s);
    let names = await p.evaluate(() => [...document.querySelectorAll('#list li.lead .ln')].map((e) => e.textContent));
    step('the list: the 3 businesses with a phone (the default "only with a phone"), the hot plumber first, its why and offer, a tel: link',
      names.length === 3 && names[0] === 'Example Plumbing Co (fictional)' && (await T('#list li.lead')).includes('Offer: starter site $1,500 (services, service area, quote form')
      && !!(await p.$('#list li.lead a[href="tel:+13015550101"], #list li.lead a[href^="tel:"]')), names);
    step('the status line and the source: "4 businesses with no website in Frederick", OpenStreetMap + the fetch date, the ODbL credit',
      (await T('#status')).includes('4 businesses with no website in Frederick') && (await T('#srcNote')).includes('OpenStreetMap') && (await T('#foot')).includes('OpenStreetMap contributors'), [await T('#status'), await T('#srcNote')]);
    await p.uncheck('#fPhone');
    names = await p.evaluate(() => [...document.querySelectorAll('#list li.lead .ln')].map((e) => e.textContent));
    step('untick "only with a phone": 4, the auto shop says "No phone on the map: look it up first"', names.length === 4 && (await T('#list')).includes('No phone on the map'), names);
    await p.selectOption('#fHeat', 'hot');
    names = await p.evaluate(() => [...document.querySelectorAll('#list li.lead .ln')].map((e) => e.textContent));
    step('Heat = hot only: the plumber', names.length === 1 && names[0] === 'Example Plumbing Co (fictional)', names);
    await p.selectOption('#fHeat', '');
    await p.selectOption('#fNiche', 'beauty');
    names = await p.evaluate(() => [...document.querySelectorAll('#list li.lead .ln')].map((e) => e.textContent));
    step('Kind = Salon / beauty: the nail salon', names.length === 1 && names[0] === 'Test Nails (fictional)', names);
    await p.selectOption('#fNiche', '');
    await p.selectOption('li.lead[data-id="osm-n1004"] select.stage', 'replied');
    step('stage "Replied" on the nail salon: the Contacted tile counts 1 and the default "New" view drops it',
      (await T('#tiles')).includes('Contacted\n1') && !(await p.$('li.lead[data-id="osm-n1004"]')), await T('#tiles'));
    await p.reload(); await p.waitForFunction('window.WEBLEADS && window.WEBLEADS.ready()');
    await p.selectOption('#fStatus', 'replied');
    names = await p.evaluate(() => [...document.querySelectorAll('#list li.lead .ln')].map((e) => e.textContent));
    const sum = await p.evaluate(() => JSON.parse(localStorage.getItem('agency.leads.summary') || 'null'));
    step('the Agency HQ tile summary on the phone: {n 4, "4 leads found", next, t, pipe {leads 4, called 1, replied 1, ...}}',
      sum && sum.n === 4 && sum.label === '4 leads found' && typeof sum.next === 'string' && sum.pipe.leads === 4 && sum.pipe.called === 1 && sum.pipe.replied === 1 && sum.t > 1.7e9, sum);
    step('after a reload the stage is still there (saved on this phone only): Status = Replied shows the nail salon, its select says Replied',
      names.length === 1 && names[0] === 'Test Nails (fictional)' && (await p.inputValue('li.lead select.stage')) === 'replied', names);
    const st = await p.evaluate(() => [...document.querySelectorAll('li.lead select.stage option')].map((o) => o.textContent));
    step('the 7 stages: New, Demo ready, Contacted, Replied, Call booked, Won, Lost', JSON.stringify(st) === JSON.stringify(['New', 'Demo ready', 'Contacted', 'Replied', 'Call booked', 'Won', 'Lost']), st);
    await p.click('#exportBtn');
    const csv = await p.inputValue('#exportBox');
    step('Export: a CSV with a header, one row per business (4), the stage ("Replied" for the salon, "New" for the others)',
      csv.split('\n')[0].startsWith('name,town,kind,phone') && csv.split('\n').length === 5 && csv.includes('"Test Nails (fictional)"') && csv.includes('"Replied"') && csv.includes('"New"'), csv.slice(0, 300));
    const mig = await p.evaluate(() => JSON.stringify(window.WEBLEADS.migrate({ a: { s: 'called', t: 5 }, b: { s: 'interested' }, c: { s: 'no' }, d: { s: 'junk' } })));
    step('old marks carry over: Called -> Contacted, Interested -> Replied, Not interested -> Lost; junk dropped',
      mig === JSON.stringify({ a: { s: 'contacted', t: 5 }, b: { s: 'replied', t: 0 }, c: { s: 'lost', t: 0 } }), mig);
    const inj = await p.evaluate(() => window.WEBLEADS.toCsv([{ name: '=HYPERLINK("x")', town: 'T' }], {}));
    step('the export is spreadsheet-safe: a cell that looks like a formula starts with a quote mark', inj.includes(`"'=HYPERLINK(""x"")"`), inj);
    const geo = await p.evaluate(() => ({ side: document.documentElement.scrollWidth <= innerWidth, small: [...document.querySelectorAll('#list button, #list a, select, #fPhone')].filter((e) => { const r = e.getBoundingClientRect(); return r.width && r.height < 43.5 && e.id !== 'fPhone'; }).length }));
    step('390 px: no sideways scroll, every button / link / select at least 44 px tall', geo.side && geo.small === 0, geo);
    if (process.env.SHOTS) { await p.selectOption('#fStatus', 'todo'); await p.evaluate(() => { const e = document.getElementById('listCard'); e.scrollIntoView({ block: 'start' }); scrollBy(0, -12); }); await p.waitForTimeout(600); await p.screenshot({ path: path.join(process.env.SHOTS, 'leads-list.png') }); }
    await p.selectOption('#fStatus', 'todo');
    await p.click('li.lead[data-id="osm-n1001"] button[data-act="call"]');
    await p.waitForURL(/call\.html\?handoff=1/, { timeout: 20000 });
    await p.waitForFunction('window.CALLS && window.CALLS.ready()', null, { timeout: 30000 });
    const call = await p.evaluate(() => ({ cur: window.CALLS.S.cur, n: window.CALLS.state.leads.length, lead: window.CALLS.state.leads.find((l) => l.id === 'osm-n1001'),
      ho: localStorage.getItem('agency.calls.handoff.v1'), text: document.body.innerText }));
    step('"Call with script": the call app opens on the plumber (imported once into the owner\'s list, Maryland, the contractor script), the hand-off is cleared',
      call.lead && call.lead.state === 'MD' && call.lead.trade === 'contractor' && call.cur === 'osm-n1001' && call.ho === null && call.text.includes('Example Plumbing Co (fictional)'),
      { cur: call.cur, n: call.n, lead: call.lead && { state: call.lead.state, trade: call.lead.trade }, ho: call.ho });
    if (process.env.SHOTS) { await p.waitForTimeout(800); await p.screenshot({ path: path.join(process.env.SHOTS, 'leads-call.png') }); }
    S.leads = '404';
    await p.goto(origin + '/agency/leads/');
    await p.waitForFunction('window.WEBLEADS && window.WEBLEADS.ready()');
    step('no leads.json on the site: one plain sentence with the PC command, no error', (await T('#status')).includes('python tools/web_leads.py') && (await T('#list')).includes('No businesses yet'), await T('#status'));
    step('no JavaScript error on either page', errs.length === 0, errs);
  } catch (e) {
    step('the harness finished', false, String(e).slice(0, 400));
  }
  await br.close(); srv.close();
  console.log(JSON.stringify(steps));
})();
