// The Data City's panels: HUD chips, building / strategy / LIT cards, Top 10, Today, Read (with the confluence lift)
// and the search list. Every data string goes in as text (el()), never as HTML.
import { $, el, money, pct, num, signed, cssColor, CLASS_TEXT } from './util.js';

const NS = 'http://www.w3.org/2000/svg';
const SPAN_COLS = [['trades', (o) => o.n ?? '–'], ['/wk', (o) => num(o.tpw, 2)], ['win', (o) => pct(o.win)], ['PF', (o) => num(o.pf, 2)],
                   ['net', (o) => money(o.net)], ['$/mo', (o) => money(o.per_month)], ['2wk pass/fail', (o) => `${num(o.p10, 0)}/${num(o.f10, 0)}%`]];

// ------------------------------------------------------------------------------------------------ panels
export function closeAll() { document.querySelectorAll('.panel.on').forEach((p) => p.classList.remove('on')); }
export function openPanel(id) { closeAll(); $('#' + id).classList.add('on'); }
export function isOpen(id) { return $('#' + id).classList.contains('on'); }

export function toast(text) {
  const t = $('#toast');
  t.textContent = text;
  t.style.display = 'block';
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => { t.style.display = 'none'; }, 2400);
}

// ------------------------------------------------------------------------------------------------ pieces
const badge = (cls, text) => el('span', 'badge b-' + cls, text);

function tile(grid, label, value) {
  const d = el('div');
  d.append(el('small', null, label), el('b', null, value));
  grid.appendChild(d);
}

function spanTable(rows, cols) {
  const t = el('table'), head = el('tr');
  head.appendChild(el('th', null, ''));
  for (const [name] of cols) head.appendChild(el('th', null, name));
  t.appendChild(head);
  for (const [name, o] of rows) {
    const tr = el('tr');
    tr.appendChild(el('td', null, name));
    for (const [, f] of cols) tr.appendChild(el('td', null, f(o || {})));
    t.appendChild(tr);
  }
  return t;
}

function sparkline(values) {
  if (!values || values.length < 2) return null;
  const w = 300, h = 56, lo = Math.min(0, ...values), hi = Math.max(0, ...values), range = (hi - lo) || 1;
  const y = (v) => h - 4 - ((v - lo) / range) * (h - 8);
  const svg = document.createElementNS(NS, 'svg');
  svg.setAttribute('viewBox', `0 0 ${w} ${h}`);
  svg.setAttribute('class', 'spark');
  svg.setAttribute('preserveAspectRatio', 'none');
  svg.setAttribute('role', 'img');
  svg.setAttribute('aria-label', `cumulative $ per micro, ending ${money(values[values.length - 1])}`);
  const zero = document.createElementNS(NS, 'line');
  for (const [k, v] of Object.entries({ x1: 0, x2: w, y1: y(0), y2: y(0), stroke: 'rgba(255,255,255,.18)', 'stroke-dasharray': '3 3' })) zero.setAttribute(k, v);
  const line = document.createElementNS(NS, 'polyline');
  line.setAttribute('points', values.map((v, i) => `${(i / (values.length - 1)) * w},${y(v)}`).join(' '));
  for (const [k, v] of Object.entries({ fill: 'none', stroke: values[values.length - 1] >= 0 ? '#39e59a' : '#ff6b7f', 'stroke-width': 2,
                                         'vector-effect': 'non-scaling-stroke' })) line.setAttribute(k, v);
  svg.append(zero, line);
  return svg;
}

function listRow(ul, key, color, title, sub, right, onClick) {
  const li = el('li'), k = el('span', 'k', key), t = el('span', 't');
  k.style.background = color;
  t.appendChild(el('div', null, title));
  if (sub) t.appendChild(el('small', null, sub));
  li.append(k, t);
  if (right !== undefined) li.appendChild(el('span', 'm ' + (String(right).startsWith('-') ? 'neg' : 'pos'), right));
  li.addEventListener('click', onClick);
  ul.appendChild(li);
}

function cardBody(title, tags) {
  const body = $('#cardBody');
  body.replaceChildren(el('h2', null, title));
  const row = el('div');
  for (const [cls, text] of tags) row.appendChild(badge(cls, text));
  body.appendChild(row);
  return body;
}

// ------------------------------------------------------------------------------------------------ cards
/** A combination (district building or discovery monument). */
export function showBuilding(b, monument) {
  const tags = [[b.cls || 'grey', CLASS_TEXT[b.cls] || b.cls]];
  if (b.fdr) tags.push(['fdr', 'passes FDR']);
  if (b.tr === 'rising' || b.tr === 'decaying') tags.push([b.tr, b.tr]);
  if (monument) tags.push(['fdr', 'discovery']);
  const body = cardBody(b.lab || b.id, tags);
  const big = el('div', 'big');
  big.append(el('span', 'v ' + ((b.e || 0) >= 0 ? 'pos' : 'neg'), money(b.e)), el('span', 'u', 'per trade per MNQ micro, after $2.90 costs'));
  body.appendChild(big);
  const g = el('div', 'grid4');
  tile(g, 'win rate', pct(b.w)); tile(g, 'hit 2R', pct(b.h2)); tile(g, 'trades/week', num(b.tpw, 2)); tile(g, 'R/trade', signed(b.r));
  body.appendChild(g);
  if (b.h1 !== undefined) {
    const g2 = el('div', 'grid4');
    tile(g2, 'hit 1R', pct(b.h1)); tile(g2, 'hit 3R', pct(b.h3)); tile(g2, '30-min pts', num(b.f30, 1)); tile(g2, '60-min pts', num(b.f60, 1));
    body.appendChild(g2);
  }
  body.appendChild(spanTable([['2026', { e: b.e26, w: b.w26, n: b.n26, t: b.tpw26 }], ['2021-25', { e: b.eo, w: b.wo, n: b.no, t: b.tpwo }]],
    [['$/trade', (o) => money(o.e)], ['win', (o) => pct(o.w)], ['trades', (o) => o.n ?? '–'], ['/week', (o) => num(o.t, 2)]]));
  const spark = sparkline(b.sp);
  if (spark) body.append(el('div', 'note', 'Cumulative $ per micro, quarter by quarter'), spark);
  if (b.yrs) {
    body.appendChild(el('div', 'note', 'Per year ($/trade, trades): ' + Object.entries(b.yrs).map(([y, v]) => `${y}: ${money(v[1])} (${v[0]})`).join(' · ')));
  }
  body.appendChild(el('div', 'note', b.text || `Median stop ${num(b.stop, 1)} pts · ${b.n} trades · one trade a day at most.`));
  body.appendChild(el('div', 'note', 'Paper only: the data city proposes, it never changes the bot.'));
  openPanel('card');
}

export function showStrategy(s) {
  const body = cardBody(s.lab, [['fdr', 'sized strategy']]);
  body.appendChild(el('div', 'note', '$500 at risk a trade, size follows the stop (1-40 micros), costs in, MFFU Builder 50K evals started every session.'));
  body.appendChild(spanTable([['2026', s.spans?.['2026']], ['2021-25', s.spans?.['2021-25']]], SPAN_COLS));
  if (s.oos_2025_26) {
    const o = s.oos_2025_26;
    body.appendChild(el('div', 'note', `Picked on 2021-24 only. 2025-26 (never seen): ${o.n} trades, ${signed(o.r, 3)} R a trade, ${money(o.net)} after costs.`));
  }
  if (s.member_text) {
    const ul = el('ul', 'list');
    for (const t of s.member_text) ul.appendChild(el('li', null, t));
    body.appendChild(ul);
  }
  body.appendChild(el('div', 'note', 'Paper only: never routed to an account.'));
  openPanel('card');
}

export function showLit(lit) {
  const body = cardBody(lit ? lit.title : 'LIT (Zlarior)', [['fdr', 'live strategy']]);
  if (lit) {
    const rows = [['2026', lit.spans['2026']], ['2026 H2 (check)', lit.spans['2026 H2']], ['2021-25', lit.spans['2021-25']]].filter((r) => r[1]);
    body.append(spanTable(rows, SPAN_COLS), el('div', 'note', lit.note));
  } else {
    body.appendChild(el('div', 'note', 'Run lit_live was not found.'));
  }
  openPanel('card');
}

// ------------------------------------------------------------------------------------------------ lists
export function hud(data, demo) {
  const g = data.summary?.guard || {}, c = $('#chips');
  c.replaceChildren();
  const chip = (...parts) => {
    const s = el('span', 'chip');
    for (const [bold, text] of parts) s.appendChild(bold ? el('b', null, text) : document.createTextNode(text));
    c.appendChild(s);
  };
  if (demo) c.appendChild(el('span', 'chip demo', 'DEMO CITY'));
  chip([1, (g.tried || 0).toLocaleString()], [0, ' tried']);
  chip([1, (g.tested || 0).toLocaleString()], [0, ' tested']);
  chip([1, String(g.fdr_pos ?? 0)], [0, ` pass FDR · placebo ${g.placebo_fdr ?? 0}`]);
  chip([0, 'data to '], [1, data.last_day || '–']);
}

export function fillTop(data, open) {
  const body = $('#topBody'), ul = el('ul', 'list'), top = data.top10 || [];
  body.replaceChildren(el('h2', null, 'Top 10: what holds in 2026 and 2021-25'),
    el('div', 'note', 'Ranked by the weaker of the two periods. Gold = also positive in every year with 8+ trades and passes the noise guard.'));
  top.forEach((t, i) => listRow(ul, i + 1, cssColor(t.cls), t.lab, `${pct(t.w)} win · ${num(t.tpw, 2)}/wk${t.tr !== 'steady' ? ' · ' + t.tr : ''}`,
                                money(t.e), () => open(t.id)));
  if (!top.length) ul.appendChild(el('li', null, 'Nothing holds in both periods yet.'));
  body.appendChild(ul);
}

export function fillToday(data, open) {
  const body = $('#todayBody'), ul = el('ul', 'list');
  body.replaceChildren(el('h2', null, "Today's discoveries"),
    el('div', 'note', `Data to ${data.last_day || '–'}. The best distinct findings (N = new on the board), then the top setups that fired that day.`));
  (data.discoveries || []).forEach((d, i) => listRow(ul, d.new ? 'N' : i + 1, cssColor(d.cls), d.text, d.tr !== 'steady' ? d.tr : '', undefined, () => open(d.id)));
  body.appendChild(ul);
  if ((data.today || []).length) {
    const fired = el('ul', 'list');
    data.today.forEach((t) => listRow(fired, '•', '#3fd8ff', t.lab, `entered ${t.at} ET · ${signed(t.R)} R`, money(t.pnl), () => open(t.id)));
    body.append(el('div', 'note', `Fired on ${data.last_day}:`), fired);
  }
}

export function fillRead(data) {
  const g = data.summary?.guard || {}, body = $('#aboutBody');
  body.replaceChildren(el('h2', null, 'How to read the city'));
  const p = (t) => body.appendChild(el('div', 'note', t));
  p('Every building is one combination: a time, a confluence (sweep, FVG, IFVG, CISD, displacement, VWAP, gap fill, news) and up to two "while" states (VWAP side, EMA trend, ATR, VIX, London vs Asia, day type, gap, ES-NQ SMT, weekday, DST, news day).');
  p('Each is a mini-backtest on CME NQ1! 5m bars: one trade a day, entry at the next bar, stop 1 tick beyond the structure, target 2R or the close after 2 hours, $1.90 commission + 2 ticks slippage per micro.');
  p('Height = $ per trade per micro. Gold = positive in 2026, in 2021-25 and in every year with 8+ trades AND passes the Benjamini-Hochberg false-discovery guard. Green = positive in both periods. Amber = one period only. Grey = noise or a loser. Lit windows = sample size. A pulsing roof = rising lately.');
  p(`Honesty: ${(g.tried || 0).toLocaleString()} combinations tried, ${(g.tested || 0).toLocaleString()} with 30+ trades, ${g.fdr_pos ?? '–'} pass the FDR guard (a shuffled-sign placebo passes ${g.placebo_fdr ?? '–'}). Picked on 2021-24 only, ${g.holdout?.picked_2021_24 ?? '–'} combinations; ${g.holdout?.pct_positive ?? '–'}% stayed positive in 2025-26. Most of the city is noise, and the city says so.`);
  p('The middle tower is LIT (Zlarior), the live strategy. Paper only: nothing here changes the bot.');
  const lift = data.lift || [];
  if (!lift.length) return;
  body.appendChild(el('h2', 'sub', 'What the city learned about confluences'));
  p('What one "while" state adds to the same trigger and window, in R per trade after costs (median over every base with 30+ trades). "Both" = share of bases where it helps in 2026 AND in 2021-25.');
  const top = Math.max(...lift.map((x) => Math.abs(x.med_r))) || 1, ul = el('ul', 'lift');
  for (const x of lift) {
    const li = el('li'), bar = el('span', 'lb'), fill = el('i', x.med_r >= 0 ? 'up' : 'dn');
    fill.style.width = `${Math.round((50 * Math.abs(x.med_r)) / top)}%`;
    bar.appendChild(fill);
    li.append(el('span', 'ln', x.lab), bar, el('span', 'lv ' + (x.med_r >= 0 ? 'pos' : 'neg'), `${signed(x.med_r)}R`),
              el('span', 'lp', `both ${Math.round(x.both_pct)}%`));
    ul.appendChild(li);
  }
  body.appendChild(ul);
}

/** The search list (the 25 best matches). */
export function fillFound(hits, open) {
  const ul = $('#findList');
  ul.replaceChildren();
  for (const it of hits.slice(0, 25)) {
    listRow(ul, '', cssColor(it.b.cls), it.b.lab, `${pct(it.b.w)} win · ${num(it.b.tpw, 2)}/wk · ${it.b.n} trades`, money(it.b.e), () => open(it));
  }
  if (!hits.length) ul.appendChild(el('li', null, 'No building matches.'));
}
