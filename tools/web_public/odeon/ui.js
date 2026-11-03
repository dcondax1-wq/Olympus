// ODEON UI: the reel list (film reels), the transport (play, speed, scrub with event ticks) and the stats card.
// DOM only; no three.js. Every text goes in with textContent (no HTML from the data).
import { fmtUsd, fmtR, fmtPx, dayLabel, hhmm, heldLabel, exitLabel, outcomeOf, spark } from './data.js';

export const SPEEDS = [1, 2, 5, 10, 20, 60];

const el = (tag, cls, text) => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text != null) e.textContent = text;
  return e;
};

function sparkSvg(tr) {
  const v = spark(tr, 40);
  const lo = Math.min(...v), hi = Math.max(...v), W = 92, H = 34;
  const pts = v.map((p, i) => `${((i / (v.length - 1)) * W).toFixed(1)},${(H - 3 - ((p - lo) / Math.max(1e-6, hi - lo)) * (H - 6)).toFixed(1)}`);
  const ns = 'http://www.w3.org/2000/svg';
  const svg = document.createElementNS(ns, 'svg');
  svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
  svg.setAttribute('aria-hidden', 'true');
  const pl = document.createElementNS(ns, 'polyline');
  pl.setAttribute('points', pts.join(' '));
  svg.append(pl);
  return svg;
}

/** the reel list: one film reel per trade, filters, tap to play */
export class Reels {
  constructor(root, onPick) {
    this.root = root;
    this.list = root.querySelector('#reelList');
    this.sum = root.querySelector('#reelSum');
    this.onPick = onPick;
    this.filter = 'all';
    this.trades = [];
    root.querySelectorAll('.chip[data-f]').forEach((b) => b.addEventListener('click', () => {
      this.filter = b.dataset.f;
      root.querySelectorAll('.chip[data-f]').forEach((x) => x.setAttribute('aria-pressed', String(x === b)));
      this.render();
    }));
  }

  set(trades, demo) {
    this.trades = trades;
    this.demo = demo;
    this.render();
  }

  render(activeId) {
    const f = this.filter;
    const T = this.trades.filter((t) => f === 'all' || (f === 'lit' && t.bot === 'LIT') || (f === 'atlas' && t.bot === 'ATLAS')
      || (f === 'win' && outcomeOf(t) === 'win') || (f === 'loss' && outcomeOf(t) === 'loss'));
    this.list.textContent = '';
    const net = T.reduce((a, t) => a + t.usd, 0);
    const last = this.trades.length ? this.trades[this.trades.length - 1].day : '';
    const first = this.trades.length ? this.trades[0].day : '';
    this.sum.textContent = this.demo ? 'Demo reel (no trades file yet)'
      : `${T.length} reels · ${dayLabel(last)} → ${dayLabel(first)} · net ${fmtUsd(net)}`;
    for (const t of T) {
      const o = outcomeOf(t);
      const li = el('li');
      const b = el('button', 'reel o-' + o);
      b.type = 'button';
      b.dataset.id = t.id;
      if (t.id === (activeId || this.active)) b.setAttribute('aria-current', 'true');
      const top = el('span', 'r-top');
      top.append(el('span', 'r-bot b-' + t.bot.toLowerCase(), t.bot === 'ATLAS' ? 'ATLAS · ' + t.strat : 'LIT'),
        el('span', 'r-src s-' + t.src, t.src === 'backtest' ? 'replay' : t.src));
      const mid = el('span', 'r-mid');
      const info = el('span', 'r-info');
      info.append(el('span', 'r-date', `${dayLabel(t.day)} · ${hhmm(t.entry.t, t.off)} ET`),
        el('span', 'r-side ' + (t.side === 'LONG' ? 'long' : 'short'), `${t.side} · ${t.qty} micro${t.qty === 1 ? '' : 's'}`));
      const res = el('span', 'r-res');
      res.append(el('b', '', fmtR(t.r)), el('span', '', fmtUsd(t.usd)));
      mid.append(info, sparkSvg(t), res);
      b.append(top, mid);
      b.addEventListener('click', () => this.onPick(t.id));
      li.append(b);
      this.list.append(li);
    }
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
