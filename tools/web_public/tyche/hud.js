// TYCHE HUD: the DOM over the 3D view. It only reads the Model (data.js) and writes text nodes only (textContent): feed text is never parsed as HTML.
//   top: balance, today / week P&L, open bets, win rate, ROI, the next settlement (counting down)
//   dock (bottom left, the orb's corner kept free): the view tabs, and per view the Kelly slider + legend, the pools' totals,
//   the Scales' reading; a tapped coin's numbers
//   labels: the scene's anchors (countdowns on coins, pools, the balance, the pans, the towers) placed in 2D
import { usd, pct, cents, edgeC, countdown, ago } from './fmt.js';
import { kellyStake } from './data.js';

export const KELLY_STOPS = [0.25, 0.5, 1];
const KELLY_NAMES = ['¼', '½', 'Full'], KELLY_WORDS = ['a quarter Kelly', 'a half Kelly', 'full Kelly'];
const ORB = { w: 80, h: 160 };
const $ = (id) => document.getElementById(id);
const signOf = (x) => (x == null || Math.abs(x) < 0.005 ? 'flat' : x > 0 ? 'up' : 'down');

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text != null) e.textContent = text;
  return e;
}
function set(id, text, sign) {
  const e = $(id);
  if (!e) return;
  if (e.textContent !== text) e.textContent = text;
  if (sign !== undefined) e.dataset.sign = sign;
}

export class Hud {
  constructor(handlers = {}) {
    this.on = handlers;
    this.model = null;
    this.colors = new Map();
    this.view = 'wheel';
    this.kelly = 0;                 // index into KELLY_STOPS
    this.selected = null;
    this.pool = new Map();          // label id -> element
    this.layer = $('labels');
    document.querySelectorAll('.tabs button').forEach((b) => b.addEventListener('click', () => this.on.view && this.on.view(b.dataset.view)));
    $('kelly').addEventListener('input', (e) => this.on.kelly && this.on.kelly(+e.target.value));
    $('s-close').addEventListener('click', () => this.on.select && this.on.select(null));
    $('quality').addEventListener('click', () => this.on.quality && this.on.quality());
  }

  // ------------------------------------------------------------------ chips and numbers
  /** The source chip: live / stale / unlinked (404: demo) / offline (demo) / demo (asked for) / loading. */
  mode(mode, model) {
    const m = $('mode'), txt = {
      loading: 'CONNECTING', live: model && model.mode === 'paper' ? 'PAPER' : 'LIVE', stale: `LAST SEEN ${model ? ago(model.age).toUpperCase() : ''}`.trim(),
      unlinked: 'Not linked yet: demo', offline: 'Offline: demo', demo: 'DEMO',
    }[mode] || mode;
    m.dataset.mode = mode;
    m.lastElementChild.textContent = txt;
    m.title = mode === 'unlinked' ? 'Your Kalshi bot is not linked yet: this is a demo. The Kalshi page shows the one step to link it.' : '';
  }

  quality(q) {
    const b = $('quality');
    b.textContent = q === 'high' ? 'HD' : 'LITE';
    b.setAttribute('aria-pressed', String(q === 'high'));
  }

  render(model, colors) {
    this.model = model;
    this.colors = colors;
    set('h-balance', usd(model.balance));
    set('h-today', usd(model.today, true), signOf(model.today));
    set('h-week', usd(model.week, true), signOf(model.week));
    set('h-open', String(model.open.length));
    set('h-win', pct(model.stats.winRate));
    set('h-roi', pct(model.stats.roi, true), signOf(model.stats.roi));
    set('h-next-title', model.next ? model.next.title : 'No open bet');
    this.legend();
    this.pools();
    this.scales();
    this.kellySum();
    if (this.selected && !model.open.some((o) => o.key === this.selected)) this.select(null);
    else if (this.selected) this.select(this.selected);
  }

  /** Once a second: every countdown, and the age in a LAST SEEN chip. */
  tick(now) {
    const m = this.model;
    if (!m) return;
    set('h-next-cd', m.next ? countdown(m.next.closes - now) : '–');
    if (this.selected) {
      const o = m.open.find((x) => x.key === this.selected);
      if (o) set('s-cd', countdown(o.closes != null ? o.closes - now : null));
    }
  }

  legend() {
    const ul = $('legend'), m = this.model, names = m.order.filter((n) => m.open.some((o) => o.category === n)).slice(0, 6);
    ul.textContent = '';
    names.forEach((n) => {
      const li = el('li'), d = el('span', 'dot');
      d.style.color = this.colors.get(n);
      li.append(d, document.createTextNode(n));
      ul.append(li);
    });
  }

  // ------------------------------------------------------------------ Kelly
  setKelly(i) {
    this.kelly = i;
    const s = $('kelly');
    if (+s.value !== i) s.value = String(i);
    s.setAttribute('aria-valuetext', KELLY_WORDS[i]);
    set('k-frac', KELLY_NAMES[i]);
    this.kellySum();
    if (this.selected) this.select(this.selected);
  }

  /** "¼ Kelly: $X across N bets · the bot has $Y on them": what Kelly would stake on the open coins at this fraction. */
  kellySum() {
    const m = this.model, p = $('k-sum');
    if (!m) return;
    p.textContent = '';
    const bets = m.open.filter((o) => o.prob != null && o.ref != null);
    if (!bets.length) { p.textContent = 'Kelly needs the bot\'s own chance per bet (prob): the halos show once it sends it.'; return; }
    const f = KELLY_STOPS[this.kelly];
    let want = 0, have = 0, capped = 0;
    bets.forEach((o) => { const k = kellyStake(o.prob, o.ref, f, m.kelly); want += k.stake || 0; have += o.cost || 0; if (k.capped) capped++; });
    p.append(document.createTextNode(`${KELLY_NAMES[this.kelly]} Kelly: `), el('b', null, usd(want)), document.createTextNode(` on ${bets.length} bets (halo)`),
      document.createTextNode(' · bot has '), el('b', null, usd(have)), document.createTextNode(capped ? ` · ${capped} at the ${usd(m.kelly.maxBet)} max` : ''));
  }

  // ------------------------------------------------------------------ the panels
  pools() {
    const m = this.model, st = m.stats;
    set('pl-w', st.wins != null ? st.wins.toLocaleString('en-US') : '–');
    set('pl-l', st.losses != null ? st.losses.toLocaleString('en-US') : '–');
    set('pl-tot', usd(m.total != null ? m.total : st.pnl, true), signOf(m.total != null ? m.total : st.pnl));
    set('pl-src', m.equity.src === 'equity' ? '' : m.equity.src === 'days' ? ' (from the daily P&L)' : ' (no curve in the feed yet)');
  }

  scales() {
    const m = this.model, c = m.calibration;
    set('sc-said', pct(c.said));
    set('sc-won', pct(c.won));
    const gap = c.said != null && c.won != null ? c.won - c.said : null;
    set('sc-gap', gap == null ? '–' : `${gap < 0 ? '−' : '+'}${Math.abs(gap * 100).toFixed(1)} pts`, signOf(gap == null ? null : gap * 100));
    const who = c.basis === 'model' ? "the bot's own chance" : 'the price paid';
    set('sc-text', !c.n ? 'No settled bets to weigh yet.'
      : `${c.n.toLocaleString('en-US')} settled bets. Predicted = ${who}. ${gap > 0.005 ? 'The right pan sinks: they won more than they said.' : gap < -0.005 ? 'The left pan sinks: they won less than they said.' : 'Level: honest odds.'}${c.own ? '' : ' (from the recent trades list)'}`);
    const rows = m.buckets.rows.filter((r) => r.roi != null);
    if (!rows.length) { set('sc-best', 'The skyline shows ROI by the price paid once bets settle.'); return; }
    const best = rows.slice().sort((a, b) => b.roi - a.roi)[0], worst = rows.slice().sort((a, b) => a.roi - b.roi)[0];
    const rng = (r) => `${Math.round(r.lo * 100)}–${Math.round(r.hi * 100)}¢`;
    set('sc-best', `Skyline = ROI by price paid. Best ${rng(best)} ${pct(best.roi, true)}${worst !== best ? ` · worst ${rng(worst)} ${pct(worst.roi, true)}` : ''}.`);
  }

  setView(v) {
    this.view = v;
    document.querySelectorAll('.tabs button').forEach((b) => b.setAttribute('aria-selected', String(b.dataset.view === v)));
    document.querySelectorAll('.panel').forEach((p) => { p.hidden = p.dataset.view !== v || (v === 'wheel' && !!this.selected); });
  }

  /** A coin's numbers in the sheet (null closes it). */
  select(key) {
    const m = this.model, o = key && m ? m.open.find((x) => x.key === key) : null;
    this.selected = o ? key : null;
    $('sheet').hidden = !o;
    this.setView(this.view);
    if (!o) return;
    set('s-title', o.title);
    $('s-dot').style.color = this.colors.get(o.category) || '#ffcf5a';
    const side = $('s-side');
    side.textContent = (o.side || '—').toUpperCase();
    side.className = 'side' + (o.side === 'no' || o.side === 'down' ? ' no' : '');
    set('s-cat', o.category + (o.strategy ? ' · ' + o.strategy : ''));
    const k = kellyStake(o.prob, o.ref, KELLY_STOPS[this.kelly], m.kelly);
    const rows = [
      ['Stake', o.cost != null ? `${usd(o.cost)} · ${o.contracts} @ ${cents(o.avg)}` : '—'],
      ['Price now', cents(o.px)],
      ["Bot's chance", o.prob != null ? pct(o.prob) : 'not sent'],
      ['Edge', edgeC(o.edge)],
      [`${KELLY_NAMES[this.kelly]} Kelly`, k.stake == null ? '—' : k.stake <= 0 ? 'no bet' : usd(k.stake) + (k.capped ? ' (max bet)' : '')],
      ['Open P&L', usd(o.pnl, true)],
    ];
    const dl = $('s-rows');
    dl.textContent = '';
    rows.forEach(([a, b]) => dl.append(el('dt', null, a), el('dd', null, b)));
    this.tick(Date.now() / 1000);
  }

  // ------------------------------------------------------------------ layout
  /** The px the HUD covers on each side, for the camera. */
  band() {
    const top = $('top').getBoundingClientRect(), dock = $('dock').getBoundingClientRect(), H = innerHeight;
    if (top.height > H * 0.8) return { top: 0, bottom: 0, left: top.right, right: 0 };     // landscape: the column on the left
    return { top: top.bottom - 14, bottom: H - dock.top, left: 0, right: 0 };
  }

  /** Is a label at (x, y) in a place it must not be: the orb's corner, under the HUD, off screen? */
  blocked(x, y, w, h) {
    const W = innerWidth, H = innerHeight;
    if (x - w / 2 < 4 || x + w / 2 > W - 4 || y - h < 4 || y > H - 4) return true;
    if (x + w / 2 > W - ORB.w - 6 && y > H - ORB.h - 6) return true;
    const r = this.rects || [];
    return r.some((q) => x + w / 2 > q.left && x - w / 2 < q.right && y > q.top && y - h < q.bottom);
  }

  measure() {
    const r = [$('dock').getBoundingClientRect()], t = $('top');
    const tr = t.getBoundingClientRect();
    if (tr.height > innerHeight * 0.8) r.push(tr); else r.push({ left: tr.left, right: tr.right, top: tr.top, bottom: tr.bottom - 16 });
    this.rects = r;
  }

  /** Place the scene's labels: one element per anchor id, reused frame to frame. */
  labels(list) {
    const seen = new Set(), placed = [];
    list.forEach((a) => {
      if (a.view !== this.view) return;
      const text = this.labelText(a);
      if (!text) return;
      let e = this.pool.get(a.id);
      if (!e) { e = el('div', 'lb'); this.layer.append(e); this.pool.set(a.id, e); e._w = 0; }
      const cls = 'lb ' + a.kind + (a.kind === 'coin' && a.left != null && a.left < 900 ? ' soon' : '') + (a.sel ? ' sel' : '')
        + (a.kind === 'pool' || a.kind === 'pop' ? (a.win ? ' win' : ' loss') : '') + (a.kind === 'tower' && a.row.roi != null ? (a.row.roi < 0 ? ' loss' : ' win') : '');
      if (e.className !== cls) e.className = cls;
      if (e._t !== text) { e.textContent = ''; text.forEach((x, i) => e.append(i ? el('b', null, x) : document.createTextNode(x))); e._t = text; e._w = 0; }
      if (!e._w) { e._w = e.offsetWidth; e._h = e.offsetHeight; }
      const y = a.low ? a.y + e._h + 4 : a.y;             // a "low" label hangs one label-height under its anchor
      if (this.blocked(a.x, y, e._w, e._h)) return;
      const box = { l: a.x - e._w / 2 - 2, r: a.x + e._w / 2 + 2, t: y - e._h - 2, b: y + 2 };
      if (a.kind !== 'pop' && placed.some((q) => box.l < q.r && box.r > q.l && box.t < q.b && box.b > q.t)) return;
      placed.push(box);
      seen.add(a.id);
      e.style.transform = `translate3d(${Math.round(a.x - e._w / 2)}px, ${Math.round(y - e._h)}px, 0)`;
      e.style.opacity = a.kind === 'pop' ? String(Math.max(0, 1 - a.age / 2.4)) : '';
      if (e.hidden) e.hidden = false;
    });
    this.pool.forEach((e, id) => {
      if (seen.has(id)) return;
      if (id.startsWith('p:') && !list.some((a) => a.id === id)) { e.remove(); this.pool.delete(id); return; }
      if (!e.hidden) e.hidden = true;
    });
  }

  /** A label's text as [line, bold line?] (the same array as last frame when nothing changed, so the DOM is left alone). */
  labelText(a) {
    const m = this.model;
    if (!m) return null;
    let t;
    if (a.kind === 'coin') t = [countdown(a.left)];
    else if (a.kind === 'edge') t = [a.text];
    else if (a.kind === 'pool' || a.kind === 'pop') t = [a.text];
    else if (a.kind === 'balance') t = [usd(m.balance)];
    else if (a.kind === 'pan') t = a.side === 'won' ? [`Won ${pct(m.calibration.won)}`] : [`Said ${pct(m.calibration.said)}`];
    else if (a.kind === 'tower') t = [`${Math.round(a.row.lo * 100)}–${Math.round(a.row.hi * 100)}¢`, a.row.roi == null ? '—' : pct(a.row.roi, true, 0)];
    else return null;
    const key = t.join('|');
    const e = this.pool.get(a.id);
    return e && e._t && e._t.join('|') === key ? e._t : t;
  }
}
