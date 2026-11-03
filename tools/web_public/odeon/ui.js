// ODEON UI: the reels gallery (3D poster cards, best $ first), the transport (play, speed, scrub with event ticks), the
// stats card.
// DOM only; no three.js. Every text goes in with textContent (no HTML from the data).
import { fmtUsd, fmtR, fmtPx, dayLabel, hhmm, heldLabel, exitLabel, outcomeOf, spark } from './data.js';

export const SPEEDS = [1, 2, 5, 10, 20, 60];

const el = (tag, cls, text) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text != null) e.textContent = text;
  return e;
};

/** The poster's art: the trade's tape as a glowing line, the entry marked (an SVG, built once per card). */
function posterArt(tr) {
  const v = spark(tr, 48);
  const lo = Math.min(...v), hi = Math.max(...v), W = 160, H = 64;
  const y = (p) => H - 6 - ((p - lo) / Math.max(1e-6, hi - lo)) * (H - 14);
  const pts = v.map((p, i) => `${((i / (v.length - 1)) * W).toFixed(1)},${y(p).toFixed(1)}`);
  const ns = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(ns, 'svg');
  svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
  svg.setAttribute('preserveAspectRatio', 'none');
  svg.setAttribute('aria-hidden', 'true');
  const area = document.createElementNS(ns, 'polygon');
  area.setAttribute('points', `0,${H} ${pts.join(' ')} ${W},${H}`);
  area.setAttribute('class', 'p-area');
  const pl = document.createElementNS(ns, 'polyline');
  pl.setAttribute('points', pts.join(' '));
  pl.setAttribute('class', 'p-line');
  const B = tr.B, ix = Math.max(0, Math.min(v.length - 1, Math.round(((tr.entry.t - B.t[0]) / Math.max(1, B.t[B.n - 1] - B.t[0])) * (v.length - 1))));
  const dot = document.createElementNS(ns, 'circle');
  dot.setAttribute('cx', ((ix / (v.length - 1)) * W).toFixed(1));
  dot.setAttribute('cy', y(tr.entry.px).toFixed(1));
  dot.setAttribute('r', '3');
  dot.setAttribute('class', 'p-entry');
  svg.append(area, pl, dot);
  return svg;
}

/** The reels in the order the gallery shows them: 'usd' = the best $ first (the owner's default), 'new' = newest first. */
export function sortReels(trades, by) {
  const T = trades.slice();
  if (by === 'usd') T.sort((a, b) => b.usd - a.usd || b.entry.t - a.entry.t);
  else T.sort((a, b) => b.entry.t - a.entry.t);
  return T;
}

const SRC = { backtest: 'replay', paper: 'paper', real: 'real', pc: 'pc bars' };

/** The reels gallery: one 3D poster card per trade (sorted by $ or by date), filters, tap to play */
export class Reels {
  constructor(root, onPick) {
    this.root = root;
    this.list = root.querySelector('#reelList');
    this.sum = root.querySelector('#reelSum');
    this.note = root.querySelector('#reelNote');
    this.onPick = onPick;
    this.filter = 'all';
    this.sort = 'usd';
    this.trades = [];
    const group = (sel, key) => root.querySelectorAll(sel).forEach((b) => b.addEventListener('click', () => {
      this[key] = b.dataset[key === 'filter' ? 'f' : 's'];
      root.querySelectorAll(sel).forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
      this.render();
    }));
    group('.chip[data-f]', 'filter');
    group('.chip[data-s]', 'sort');
  }

  set(trades, demo) {
    this.trades = trades;
    this.demo = demo;
    this.render();
  }

  /** a line above the posters (e.g. the trade Oracle asked for has no film yet); '' hides it */
  say(text) {
    this.note.textContent = text || '';
    this.note.hidden = !text;
  }

  render() {
    const f = this.filter;
    const T = sortReels(this.trades.filter((t) => f === 'all' || (f === 'lit' && t.bot === 'LIT') || (f === 'atlas' && t.bot === 'ATLAS')
      || (f === 'win' && outcomeOf(t) === 'win') || (f === 'loss' && outcomeOf(t) === 'loss')), this.sort);
    this.list.textContent = '';
    const net = T.reduce((a, t) => a + t.usd, 0);
    const days = this.trades.map((t) => t.day).sort();
    this.sum.textContent = this.demo ? 'Demo reel (no trades file yet)'
      : `${T.length} reels · ${dayLabel(days[0] || '')} → ${dayLabel(days[days.length - 1] || '')} · net ${fmtUsd(net)}`;
    T.forEach((t, k) => {
      const o = outcomeOf(t);
      const li = el('li');
      const b = el('button', 'reel o-' + o);
      b.type = 'button';
      b.dataset.id = t.id;
      b.style.setProperty('--i', String(Math.min(k, 18)));
      if (t.id === this.active) b.setAttribute('aria-current', 'true');
      b.setAttribute('aria-label', `${t.bot === 'ATLAS' ? 'ATLAS ' + t.strat : 'LIT'} ${t.side.toLowerCase()} ${dayLabel(t.day)}: ${fmtUsd(t.usd)}, ${fmtR(t.r)}`);
      const poster = el('span', 'poster');
      poster.append(posterArt(t), el('span', 'p-rank', this.sort === 'usd' ? '#' + (k + 1) : dayLabel(t.day).split(' ').slice(1).join(' ')),
        el('b', 'p-usd', fmtUsd(t.usd)), el('span', 'p-r', fmtR(t.r)));
      const top = el('span', 'r-top');
      top.append(el('span', 'r-bot b-' + t.bot.toLowerCase(), t.bot === 'ATLAS' ? 'ATLAS · ' + t.strat : 'LIT'),
        el('span', 'r-src s-' + t.src, SRC[t.src] || t.src));
      const info = el('span', 'r-info');
      info.append(el('span', 'r-date', `${dayLabel(t.day)} · ${hhmm(t.entry.t, t.off)} ET`),
        el('span', 'r-side ' + (t.side === 'LONG' ? 'long' : 'short'), `${t.side} · ${t.qty} micro${t.qty === 1 ? '' : 's'} · ${exitLabel(t.exit.kind).toLowerCase()}`));
      b.append(poster, top, info);
      b.addEventListener('click', () => this.onPick(t.id));
      li.append(b);
      this.list.append(li);
    });
  }

  mark(id) {
    this.active = id;
    this.list.querySelectorAll('.reel').forEach((b) => (b.dataset.id === id ? b.setAttribute('aria-current', 'true') : b.removeAttribute('aria-current')));
  }
}

/** play / pause, speed, the scrubber (with the caption rows as ticks) and the clock */
export class Transport {
  constructor(root, h) {
    this.root = root;
    this.h = h; // { toggle(), speed(x), seek(T), restart() }
    this.play = root.querySelector('#play');
    this.speedBtn = root.querySelector('#speed');
    this.scrub = root.querySelector('#scrub');
    this.ticks = root.querySelector('#ticks');
    this.clock = document.getElementById('clock');
    this.left = document.getElementById('tLeft');
    this.play.addEventListener('click', () => h.toggle());
    this.speedBtn.addEventListener('click', () => {
      const i = SPEEDS.indexOf(this.speed);
      h.speed(SPEEDS[(i + 1) % SPEEDS.length]);
    });
    root.querySelector('#restart').addEventListener('click', () => h.restart());
    const seek = () => h.seek(this.t0 + (Number(this.scrub.value) / 1000) * (this.t1 - this.t0));
    this.scrub.addEventListener('input', seek);
    this.scrub.addEventListener('change', seek);
  }

  load(tr) {
    this.tr = tr;
    this.t0 = tr.tStart;
    this.t1 = tr.tEnd;
    this.ticks.textContent = '';
    const keep = { sweep: 1, entry: 1, exit: 1, be: 1, cisd5: 1 };
    for (const e of tr.events) {
      if (!keep[e.k]) continue;
      const b = el('button', 'tick k-' + e.k + (e.outcome ? ' o-' + e.outcome : ''));
      b.type = 'button';
      b.style.left = (((e.t - this.t0) / (this.t1 - this.t0)) * 100).toFixed(2) + '%';
      b.setAttribute('aria-label', `Jump to ${e.k} at ${hhmm(e.t, tr.off)} ET`);
      b.addEventListener('click', () => this.h.seek(e.t - (e.k === 'exit' ? 20 * tr.B.s : 3 * tr.B.s)));
      this.ticks.append(b);
    }
  }

  setSpeed(x) {
    this.speed = x;
    this.speedBtn.textContent = x + 'x';
    this.speedBtn.setAttribute('aria-label', `Speed ${x}x (1x = one minute of market per second)`);
  }

  setPlaying(on, ended) {
    this.play.dataset.state = ended ? 'ended' : on ? 'playing' : 'paused';
    this.play.setAttribute('aria-label', ended ? 'Replay' : on ? 'Pause' : 'Play');
  }

  sync(T, pnl) {
    const tr = this.tr;
    if (!tr) return;
    if (document.activeElement !== this.scrub) this.scrub.value = String(Math.round(((T - this.t0) / (this.t1 - this.t0)) * 1000));
    this.clock.textContent = hhmm(T, tr.off) + ' ET';
    this.left.textContent = pnl.live ? `${fmtUsd(pnl.usd)} · ${fmtR(pnl.r)}` : T < tr.entry.t ? 'waiting for the setup' : 'closed';
    this.left.dataset.sign = pnl.live ? (pnl.usd >= 0 ? 'up' : 'down') : '';
  }
}

/** the card after the trade: $, R, MFE / MAE, time in trade, the backtest twin */
export function fillStats(card, tr) {
  const o = outcomeOf(tr);
  card.dataset.outcome = o;
  const set = (id, v) => { const x = card.querySelector('#' + id); if (x) x.textContent = v; };
  set('stKind', exitLabel(tr.exit.kind));
  set('statUsd', fmtUsd(tr.usd));
  set('statR', fmtR(tr.r));
  set('stTitle', `${tr.bot === 'ATLAS' ? 'ATLAS · ' + tr.strat : 'LIT'} ${tr.side.toLowerCase()} · ${dayLabel(tr.day)}`);
  set('stMfe', `${fmtR(tr.mfe_r || 0)} · ${fmtUsd(tr.mfe_usd || 0, false)}`);
  set('stMae', `${fmtR(-(tr.mae_r || 0))} · ${fmtUsd(-(tr.mae_usd || 0))}`);
  set('stHeld', heldLabel(tr.held_min));
  set('stPrices', `${fmtPx(tr.entry.px)} → ${fmtPx(tr.exit.px)}`);
  set('stTimes', `${hhmm(tr.entry.t, tr.off)} → ${hhmm(tr.exit.t, tr.off)} ET`);
  set('stSize', `${tr.qty} micro${tr.qty === 1 ? '' : 's'} · risk ${fmtUsd(tr.risk_usd, false)} (${tr.risk_pts.toFixed(2)} pts)`);
  let twin;
  if (tr.twin) {
    const tw = tr.twin;
    twin = `${tw.src === 'paper' ? 'Paper (cloud) twin' : 'Backtest twin'}: ${tw.r != null ? fmtR(tw.r) : '—'}`
      + (tw.usd != null ? `, ${fmtUsd(tw.usd)}` : '') + (tw.exit ? ` (${exitLabel(tw.exit).toLowerCase()})` : '');
  } else if (tr.src === 'backtest') {
    twin = 'This reel is the backtest itself (live settings, costs in).';
  } else {
    twin = 'No backtest twin for this trade.';
  }
  set('stTwin', twin);
}
