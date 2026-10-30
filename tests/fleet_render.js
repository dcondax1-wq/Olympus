// tests/test_fleet.py ui_checks: render the phone page (tools/web_public/fleet.js) and the PC page (web_next/js/next/fleet.js)
// in node with stubbed globals, on the heartbeat block / API answer given in argv[2] (a JSON file). Prints one JSON line.
'use strict';
const fs = require('fs');
const path = require('path');
const root = path.resolve(__dirname, '..');
const data = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const out = {};
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

// ---- phone
{
  const VIEWS = {}, PAGES = {}, ALIAS = {}, SCENE = {};
  const GROUPS = [{ id: 'system', pages: [['system', 'Overview', 'modules', '']] }];
  const window = { LIVE: { j: { pc: { fleet: data.hb } } } };
  const head = (a, b, c) => `<header>${a}|${b}|${c}</header>`;
  const statBox = (l, v, s = '', k = '') => `<div class="stat"><span>${l}</span><b class="${k}">${v}</b><em>${s}</em></div>`;
  const usd = (v) => '$' + Math.round(v);
  const susd = (v) => (v > 0 ? '+' : '') + usd(v);
  const cls = (v) => (v > 0 ? 'up' : v < 0 ? 'dn' : '');
  const PAGE = 'fleet';
  const src = fs.readFileSync(path.join(root, 'tools', 'web_public', 'fleet.js'), 'utf8');
  const setInterval = () => 0, clearInterval = () => 0;
  new Function('VIEWS', 'PAGES', 'ALIAS', 'SCENE', 'GROUPS', 'window', 'head', 'statBox', 'usd', 'susd', 'cls', 'esc', 'PAGE', 'setInterval', 'clearInterval', src)(
    VIEWS, PAGES, ALIAS, SCENE, GROUPS, window, head, statBox, usd, susd, cls, esc, PAGE, setInterval, clearInterval);
  const el = { innerHTML: '' };
  VIEWS.fleet(el);
  out.phone = { registered: !!(VIEWS.fleet && PAGES.fleet), grouped: GROUPS[0].pages.some((p) => p[0] === 'fleet'), html: el.innerHTML };
  window.LIVE.j.pc.fleet = null;
  const el2 = { innerHTML: '' };
  VIEWS.fleet(el2);
  out.phone_off = el2.innerHTML;
}

// ---- PC (an ES module: the import line replaced by the two helpers it uses)
(async () => {
  const src = fs.readFileSync(path.join(root, 'web_next', 'js', 'next', 'fleet.js'), 'utf8')
    .replace(/^import .*$/m, '').replace(/^export const fleet/m, 'const fleet');
  const page = { id: 'page-fleet', innerHTML: '', classList: { contains: () => true }, querySelectorAll: () => [] };
  const document = { getElementById: (id) => (id === 'page-fleet' ? page : null), querySelector: () => null, createElement: () => ({}),
                     body: { appendChild: () => 0 } };
  const fetch = async () => ({ json: async () => data.api });
  const $ = (s) => (s === '#page-fleet' ? page : null);
  const fn = new Function('document', 'fetch', '$', 'esc', 'setInterval', 'clearInterval', src + '\nreturn { fleet, draw };');
  const m = fn(document, fetch, $, esc, () => 0, () => 0);
  await m.draw();
  out.pc = page.innerHTML;
  process.stdout.write(JSON.stringify(out));
})().catch((e) => { process.stdout.write(JSON.stringify({ ...out, error: String(e && e.stack || e) })); });
