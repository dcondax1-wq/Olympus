// Node twin of tests/net_stub.py (2026-11-18): the browser harnesses never read the PC's REAL public ntfy status topic.
//   const NS = require('./net_stub.cjs');
//   const b = NS.wrap(await chromium.launch());   // every b.newContext() / b.newPage() answers ntfy.sh with "{}"
//   NS.stub(ctxOrPage, body)                       // the same route by hand, or with a fixture body (ntfy /json?poll=1 lines)
// Registered first, so a harness's own later p.route('https://ntfy.sh/**') still wins (Playwright tries the newest route first).
const NTFY = '**/ntfy.sh/**';
const hits = [];
async function stub(target, body = '{}') {
  await target.route(NTFY, (r) => { hits.push(r.request().url()); return r.fulfill({ status: 200, contentType: 'application/json', headers: { 'access-control-allow-origin': '*' }, body }); });
  return target;
}
function wrap(browser) {
  if (browser._ntfyStubbed || process.env.NET_STUB_OFF === '1') return browser;   // NET_STUB_OFF=1: only to compare with the real feed
  browser._ntfyStubbed = true;
  const ctx = browser.newContext.bind(browser), page = browser.newPage.bind(browser);
  browser.newContext = async (...a) => stub(await ctx(...a));
  browser.newPage = async (...a) => { const p = await page(...a); await stub(p.context()); return p; };
  return browser;
}
module.exports = { NTFY, hits, stub, wrap };
