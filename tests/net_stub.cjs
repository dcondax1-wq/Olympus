// Node twin of tests/net_stub.py (2026-11-18): the browser harnesses never read the PC's REAL public ntfy status topic.
//   const NS = require('./net_stub.cjs');
//   const b = NS.wrap(await chromium.launch());   // every b.newContext() / b.newPage() answers ntfy.sh with "{}"
//   NS.stub(ctxOrPage, body)                       // the same route by hand, or with a fixture body (ntfy /json?poll=1 lines)
// Registered first, so a harness's own later p.route('https://ntfy.sh/**') still wins (Playwright tries the newest route first).
const NTFY = '**/ntfy.sh/**';
const hits = [];
// day-guard2: the site's status_feed.json pins the PC's real key ("vk"); fixtures are unsigned -> the test copy is served without
// vk / vks (NET_STUB_KEEP_VK=1 keeps it). The signature path itself: tests/test_status_sign.py + test_guard2.py.
async function unpinned(r) {
  try {
    const resp = await r.fetch(), d = JSON.parse(await resp.text());
    if (d && typeof d === 'object' && process.env.NET_STUB_KEEP_VK !== '1') { delete d.vk; delete d.vks; }
    return r.fulfill({ response: resp, body: JSON.stringify(d), contentType: 'application/json' });
  } catch (e) { try { return r.fallback(); } catch (e2) { return undefined; } }
}
async function stub(target, body = '{}') {
  await target.route('**/status_feed.json', unpinned);
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
