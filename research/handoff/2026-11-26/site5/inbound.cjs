// Inbound-link census for every app in olympus/gate-catalog.js (day-site5): which pages/scripts outside the app's own folder point at it.
// Registry files that list EVERY app (the catalog, apps lists, the service worker, nav/search shells) are counted apart: a link there is not "someone opens it".
// usage: node inbound.cjs [web_public dir]   -> JSON on stdout
const fs = require('fs'), path = require('path');
const PUB = path.resolve(process.argv[2] || path.join(__dirname, '../../../../tools/web_public'));
const G = require(path.join(PUB, 'olympus/gate-catalog.js'));
const REG = /(^|\/)(gate-catalog\.js|apps-list\.js|apps\.js|olympus\.js|sw\.js|manual-sw\.js|gate-nav\.js|intro\.js|transitions\.js|launcher\.js|launch\.js|help\.json|help\.js|whatsnew\.json|doors\.js|cities-data\.json|brain-data\.json|hub-data\.json|world.*\.json|index\.json)$/;
const files = [];
(function walk(d) { for (const n of fs.readdirSync(d)) { const p = path.join(d, n); const s = fs.statSync(p); if (s.isDirectory()) { if (!/node_modules|fonts|\.git/.test(n)) walk(p); } else if (/\.(html|js|json|css|webmanifest)$/.test(n) && s.size < 3e6) files.push(p); } })(PUB);
const text = Object.fromEntries(files.map((f) => [path.relative(PUB, f), fs.readFileSync(f, 'utf8')]));
const out = {};
for (const a of G.apps) {
  const dir = a.path.split('/')[0] || a.id, own = dir + '/';
  const rx = new RegExp(`(["'(=\\s/]|\\.\\./)${dir.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}/`, 'g');
  const real = [], reg = [];
  for (const [f, t] of Object.entries(text)) {
    if (f.startsWith(own)) continue;
    rx.lastIndex = 0; if (!rx.test(t)) continue;
    (REG.test(f) ? reg : real).push(f);
  }
  out[a.id] = { dir, retired: G.retired(a.id), fold: a.fold, hub: a.hub, label: a.label, arena: (G.arenaOf(a.id) || {}).id, real: real.sort(), reg: reg.sort(),
    exists: fs.existsSync(path.join(PUB, dir)) };
}
console.log(JSON.stringify(out));
