// BUSINESS page (ES module): reads ./business.json (the PC's own, tools/biz_publish.py) else ./fixture.json (DEMO). Sends nothing.
import * as C from './businesscore.js';

const $ = (id) => document.getElementById(id);
const KEY = 'business.week.v1';
let READY = false;
window.BUSINESS = { ready: () => READY };   // for the tests (tests/agora_kit.open_app)
function h(tag, cls, text) { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }

async function getJSON(url) {
  try { const r = await fetch(url, { cache: 'no-cache' }); return r.ok ? await r.json() : null; } catch (_) { return null; }
}
function loadTicks() { try { return JSON.parse(localStorage.getItem(KEY) || '{}') || {}; } catch (_) { return {}; } }
function saveTicks(t) { try { localStorage.setItem(KEY, JSON.stringify(t)); } catch (_) { /* private window: ticks just do not stay */ } }

function kv(dl, k, v) { dl.appendChild(h('dt', '', k)); dl.appendChild(h('dd', '', v)); }

function render(doc) {
  $('demo').hidden = !doc.sample;
  $('status').textContent = doc.sample ? 'DEMO: example plan, no progress from your PC yet. Run AGENCY_DAY.bat on the PC to see yours.' : `Updated ${doc.asof.replace('T', ' ').slice(0, 16)}.`;
  $('heroM3').textContent = `${C.range(doc.total.usd_m3)} a month`;
  $('heroText').textContent = `In month 3, all models together (estimate). Do now: ${C.firstAction(doc)}`;
  const kvs = $('heroKv'); kvs.textContent = '';
  kv(kvs, 'Month 1', `${C.range(doc.total.usd_m1)} a month`);
  kv(kvs, 'Your hours', `${doc.total.hours[0]}-${doc.total.hours[1]} a week`);
  kv(kvs, 'Real so far', `${C.money(doc.total.real)} a month`);

  const tb = $('tbl').querySelector('tbody'); tb.textContent = '';
  for (const m of doc.models) {
    const tr = h('tr');
    tr.appendChild(h('td', '', m.paused ? `${m.name} (paused)` : m.name));
    tr.appendChild(h('td', 'n', C.range(m.usd_m1)));
    tr.appendChild(h('td', 'n', C.range(m.usd_m3)));
    tr.appendChild(h('td', 'n', `${m.hours[0]}-${m.hours[1]}`));
    tb.appendChild(tr);
  }

  const box = $('models'); box.textContent = '';
  for (const m of doc.models) {
    const s = h('section', `ag-card card model${m.paused ? ' paused' : ''}`);
    const row = h('div', 'row'); row.appendChild(h('h2', '', m.name)); row.appendChild(h('span', `pill ${m.paused ? '' : 'ok'}`, m.paused ? 'Paused' : `${C.range(m.usd_m3)} by month 3`));
    s.appendChild(row);
    s.appendChild(h('p', 'lead', m.what));
    s.appendChild(h('p', 'next', `Next: ${m.next}`));
    if (!m.paused) {
      s.appendChild(h('p', 'note', 'Before the first dollar:'));
      const ul = h('ul'); for (const x of m.first_dollar) ul.appendChild(h('li', '', x)); s.appendChild(ul);
    }
    const d = h('details'); d.appendChild(h('summary', '', `Built (${m.built.length})`));
    const ub = h('ul'); for (const x of m.built) ub.appendChild(h('li', '', x)); d.appendChild(ub); s.appendChild(d);
    s.appendChild(h('p', 'note', `${m.why} More: ${m.doc}`));
    box.appendChild(s);
  }

  const pr = $('prices'); pr.textContent = '';
  for (const p of doc.prices) kv(pr, p.name, C.priceLine(p));

  const ticks = loadTicks(); const wk = $('week'); wk.textContent = '';
  const count = () => { const n = Object.values(ticks).filter(Boolean).length; $('weekPill').textContent = `${n} done`; };
  for (const d of doc.week) {
    wk.appendChild(h('h3', '', `Day ${d.day}: ${d.title}`));
    const ol = h('ol');
    d.tasks.forEach((t, i) => {
      const k = C.taskKey(d.day, i), li = h('li'), lab = h('label', 'chk'), cb = document.createElement('input');
      cb.type = 'checkbox'; cb.checked = !!ticks[k];
      cb.onchange = () => { ticks[k] = cb.checked; saveTicks(ticks); count(); };
      lab.appendChild(cb); lab.appendChild(h('span', '', t)); li.appendChild(lab); ol.appendChild(li);
    });
    wk.appendChild(ol);
  }
  count();
  const ru = $('rules'); ru.textContent = ''; for (const r of doc.rules) ru.appendChild(h('li', '', r));
  renderProp(doc.prop);
}

// the prop accounts' payout plan card (team E 2026-11-16): the money table, when Zlarior can pass / pay, the buying schedule
function renderProp(p) {
  const card = $('prop');
  card.hidden = !p;
  if (!p) return;
  $('propSpan').textContent = p.span || 'replay';
  const tb = $('propTbl').querySelector('tbody'); tb.textContent = '';
  for (const r of p.table) {
    const tr = h('tr');
    tr.appendChild(h('td', '', `${r.accounts} accounts`));
    tr.appendChild(h('td', 'n', C.signed(r.y1)));
    tr.appendChild(h('td', 'n', C.signed(r.steady)));
    tr.appendChild(h('td', 'n', C.signed(r.worst)));
    tr.appendChild(h('td', 'n', r.empty === null ? '-' : `${Math.round(r.empty)}%`));
    tr.appendChild(h('td', 'n', C.signed(r.ref)));
    tb.appendChild(tr);
  }
  const kvs = $('propKv'); kvs.textContent = '';
  const z = p.zlarior;
  if (z) {
    kv(kvs, 'Zlarior passes', z.pass_median ? `about ${z.pass_median} (earliest ${z.pass_earliest || '-'}; ${z.pass_10 ?? '-'}% within 2 weeks, ${z.fail_10 ?? '-'}% fail)` : '-');
    kv(kvs, 'First payout', z.pay_median ? `about ${z.pay_median}, ${C.money(z.pay_usd)} to you (earliest ${z.pay_earliest || '-'}; in your bank about ${z.bank_median || '-'})` : '-');
  }
  for (const b of p.buy) kv(kvs, `Buy ${b.n}`, b.median ? `about ${b.median} (${b.p25 || '-'} to ${b.p75 || '-'})` : 'not within 12 months');
  if (p.plan) kv(kvs, 'Each new account', `${p.plan}${p.price !== null ? `, ${C.money(p.price)}` : ''}`);
  const ul = $('propRules'); ul.textContent = '';
  for (const r of p.rules.concat(p.notes)) ul.appendChild(h('li', '', r));
}

(async function main() {
  const own = C.clean(await getJSON('./business.json'));
  const doc = own || C.clean(await getJSON('./fixture.json'));
  if (!doc) { $('status').textContent = 'No business data yet: run python tools/biz_publish.py on the PC.'; READY = true; return; }
  render(doc);
  READY = true;
})();
