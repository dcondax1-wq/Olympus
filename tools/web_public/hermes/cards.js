// HERMES story cards. deck(w, key, peers) -> [card]; each card:
//   {id, name, colors: [3 x #rrggbb], mode: the scene (fx.js: 0 flow, 1 rays, 2 rings, 3 orbs, 4 aurora, 5 warp, 6 grid),
//    ms: how long it shows, html: its markup (every data text escaped), enter(el, fx, still): counters / lines / particles
//    when it opens, share(): the share image's spec (share.js)}
// Order: money, best, worst, eval, discipline, learned, Data City (if any), Kalshi (or a teaser), Planner (if any),
// the all-time hall, next. A card's parts carry data-z (how far they float off the card in the 3D tilt).
import { esc, usd, tone, plural, dayLabel, span, num, kalshiPeriod, plannerPeriod } from './data.js';

const NBSP = ' ';
const kt = (text, cls = 'title') => `<h1 class="${cls} kt">${String(text).split(' ').map((w, i) => `<span class="w"><span style="--i:${i}">${esc(w)}</span></span>`).join(' ')}</h1>`;
const kick = (p, extra) => `<p class="kicker">${esc(p.label)} · ${esc(span(p))}${extra ? ' · ' + esc(extra) : ''}</p>`;
const counter = (v, cls = '') => `<span class="count ${cls} ${tone(v)}" data-to="${num(v) || 0}">${esc(usd(0))}</span>`;
const R = (r) => (num(r) == null ? '' : `${r > 0 ? '+' : r < 0 ? '−' : ''}${Math.abs(r).toFixed(1)}R`);

// ------------------------------------------------------------------------------------------------ small parts
function sparkSVG(s, cls) {
  const pts = (s && s.points) || [];
  if (pts.length < 2) return '';
  // the scale holds the path, the entry and the stop; the target only when it is near (an 8R target far away would flatten a loss)
  const p0 = Math.min(...pts), p1 = Math.max(...pts), near = (v) => num(v) != null && v >= p0 - (p1 - p0) * 1.5 && v <= p1 + (p1 - p0) * 1.5;
  const lv = [s.stop, s.entry].filter((x) => num(x) != null).concat(near(s.target) ? [s.target] : []);
  const all = pts.concat(lv), lo = Math.min(...all), hi = Math.max(...all), r = hi - lo || 1;
  const W = 320, H = 120, P = 8, X = (i) => P + (i / (pts.length - 1)) * (W - 2 * P), Y = (v) => P + (1 - (v - lo) / r) * (H - 2 * P);
  const d = pts.map((v, i) => `${i ? 'L' : 'M'}${X(i).toFixed(1)} ${Y(v).toFixed(1)}`).join(' ');
  const line = (v, c, t) => (num(v) == null ? '' : `<line x1="0" x2="${W}" y1="${Y(v).toFixed(1)}" y2="${Y(v).toFixed(1)}" class="lvl ${c}"/><text x="${W - 4}" y="${(Y(v) - 4).toFixed(1)}" class="lvt ${c}">${t}</text>`);
  return `<figure class="spark ${cls}"><svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" role="img" aria-label="trade path">
    ${near(s.target) ? line(s.target, 'tgt', 'target') : ''}${line(s.stop, 'stp', 'stop')}${line(s.entry, 'ent', 'entry')}
    <path d="${d}" class="path" pathLength="1"/><circle r="5" class="dot" cx="${X(pts.length - 1).toFixed(1)}" cy="${Y(pts[pts.length - 1]).toFixed(1)}"/></svg>
    <figcaption>${s.kind === 'bars' ? 'Price during the trade (5m closes)' : 'Trade path: entry, best point, exit (not every tick)'}</figcaption></figure>`;
}

function dayBars(days) {
  if (!days || !days.length) return '';
  const m = Math.max(...days.map(([, v]) => Math.abs(v))) || 1;
  return `<div class="bars" aria-label="P&amp;L per day">${days.slice(-23).map(([d, v], i) => `<div class="dbar ${tone(v)}" style="--h:${Math.max(4, Math.abs(v) / m * 100).toFixed(1)}%;--i:${i}"><i></i><b>${esc(dayLabel(d, { weekday: 'narrow' }))}</b></div>`).join('')}</div>`;
}

function ring(p, cls, label) {
  const C = 2 * Math.PI * 52;
  return `<svg viewBox="0 0 120 120" class="ring ${cls}" aria-label="${esc(label)}"><circle cx="60" cy="60" r="52" class="trk"/>
    <circle cx="60" cy="60" r="52" class="arc" style="--c:${C.toFixed(1)};--p:${Math.max(0, Math.min(1, p)).toFixed(4)}"/></svg>`;
}

// ------------------------------------------------------------------------------------------------ the cards
function money(w, p, peers) {
  const all = w.periods.all, kp = kalshiPeriod(peers.kalshi, p), up = p.net >= 0;
  const row = (name, tag, sub, v) => `<li><span>${esc(name)}${tag ? ` <em>${esc(tag)}</em>` : ''}<small>${esc(sub)}</small></span><span class="${tone(v)}">${esc(usd(v))}</span></li>`;
  const bots = p.bots.map((b) => row(b.name, b.paper ? 'paper' : '', plural(b.trades, 'trade'), b.net)).join('');
  const twin = p.paper_twin ? `<p class="note">Paper twin ${esc(usd(p.paper_twin.net))}: the same trades on paper, not counted twice.</p>` : '';
  const ks = kp ? row(kp.name, 'real money', 'Kalshi', kp.net) : '';
  return {
    id: 'money', name: 'The money', colors: up ? ['#04140f', '#1f8f6a', '#f7c948'] : ['#14040a', '#6b1030', '#ff7a8a'], mode: up ? 4 : 1, ms: 8000,
    html: `${kick(p)}${kt(p.trades ? (up ? 'The bots made money' : 'A red stretch. Here it is.') : 'No trades yet')}
      <div class="hero" data-z="3">${counter(p.net, 'xl')}<p class="sub">${esc(plural(p.trades, 'trade'))} · ${p.wins} won · ${p.losses} lost${p.win_pct != null ? ` · ${p.win_pct}% wins` : ''}</p></div>
      <div class="split"><div><small>Won</small><b class="up">${esc(usd(p.won_usd))}</b></div><div><small>Lost</small><b class="down">${esc(usd(p.lost_usd))}</b></div>
      <div><small>Per month</small><b class="${tone(p.per_month)}">${esc(usd(p.per_month, { cents: false }))}</b>${p.key !== 'all' ? `<i>at this pace \u00b7 avg ${esc(usd(all.per_month, { cents: false }))}</i>` : '<i>average</i>'}</div></div>
      ${dayBars(p.days)}<ul class="bots">${bots}${ks}</ul>${twin}`,
    enter(el, fx) {
      if (!p.trades) return;
      fx.burst(up ? 'coins' : 'embers', up ? 60 : 50, { colors: up ? ['#f7c948'] : ['#ff7a8a', '#ffb199'] });
      if (up) fx.burst('confetti', 110, { colors: ['#5ef2a8', '#f7c948', '#ffffff', '#59d0ff', '#ff5edb'] });   // a green week: confetti
    },
    share: () => ({ kicker: `${p.label} · ${span(p)}`, title: 'The money', big: usd(p.net), tone: tone(p.net),
      lines: [`${plural(p.trades, 'trade')}: ${p.wins} won, ${p.losses} lost`, `Won ${usd(p.won_usd)} · Lost ${usd(p.lost_usd)}`,
        `${usd(p.per_month, { cents: false })} a month at this pace`].concat(p.bots.map((b) => `${b.name} ${usd(b.net)}`)) }),
  };
}

function best(w, p) {
  const b = p.best;
  if (!b) return null;
  return {
    id: 'best', name: 'Best trade', colors: ['#03140e', '#0f6b4f', '#5ef2a8'], mode: 0, ms: 7500,
    html: `${kick(p)}${kt('Trade of the week'.replace('week', p.key === 'all' ? 'all time' : p.key))}
      <div class="hero" data-z="3">${counter(b.pnl, 'lg')}<p class="sub">${esc(b.bot)} · ${esc(b.side || '')} · ${esc(dayLabel(b.day, { weekday: 'short', month: 'short', day: 'numeric' }))}${b.time ? ' ' + esc(b.time) : ''} · ${esc(R(b.r))}</p></div>
      ${sparkSVG(b.spark, 'up')}
      <p class="fact">${esc(b.exit ? `Exit: ${b.exit}.` : '')} ${b.qty ? esc(`${b.qty} micros`) + ', ' : ''}${b.risk_pts ? esc(`${b.risk_pts}-pt stop`) : ''}${b.paper ? ' (paper)' : ''}</p>`,
    enter(el, fx) { fx.burst('sparks', 50, { y: 0.55, colors: ['#5ef2a8', '#ffffff'] }); },
    share: () => ({ kicker: `${p.label} · best trade`, title: `${b.bot} · ${dayLabel(b.day)}`, big: usd(b.pnl), tone: 'up', spark: b.spark.points,
      lines: [`${b.side || ''} · ${R(b.r)}${b.exit ? ' · ' + b.exit : ''}`] }),
  };
}

function worst(w, p) {
  const b = p.worst;
  if (!b) {
    if (!p.trades) return null;
    return { id: 'worst', name: 'Worst trade', colors: ['#071410', '#1f5a3a', '#bfffd9'], mode: 2, ms: 5500,
      html: `${kick(p)}${kt('No losing trade. Not one.')}<p class="lesson">Every trade closed green or flat. Enjoy it; it will not always look like this.</p>`,
      enter() {}, share: () => ({ kicker: p.label, title: 'No losing trade', big: '0 losses', tone: 'up', lines: [`${plural(p.trades, 'trade')}, all green or flat`] }) };
  }
  return {
    id: 'worst', name: 'Worst trade', colors: ['#140606', '#5a1a24', '#ff9a6b'], mode: 2, ms: 8500,
    html: `${kick(p)}${kt('The one that hurt')}
      <div class="hero" data-z="3">${counter(b.pnl, 'lg')}<p class="sub">${esc(b.bot)} · ${esc(b.side || '')} · ${esc(dayLabel(b.day, { weekday: 'short', month: 'short', day: 'numeric' }))} · ${esc(R(b.r))}</p></div>
      ${sparkSVG(b.spark, 'down')}<blockquote class="lesson"><small>The lesson</small>${esc(b.lesson || '')}</blockquote>`,
    enter() {},
    share: () => ({ kicker: `${p.label} · worst trade`, title: `${b.bot} · ${dayLabel(b.day)}`, big: usd(b.pnl), tone: 'down', spark: b.spark.points, lines: [b.lesson || ''] }),
  };
}

function evalCard(w, p, peers) {
  const E = w.eval || [];
  if (!E.length) return null;
  const odds = peers.fates ? `<p class="odds"><b>${esc(peers.fates.value)}</b> ${esc(peers.fates.label)} <small>(Fates)</small></p>`
    : w.odds ? `<p class="odds"><b>${esc(w.odds.p10)}%</b> pass within 2 weeks · ${esc(w.odds.f10)}% fail <small>(backtest ${esc(w.odds.span)}, the live sizing)</small></p>` : '';
  const rows = E.map((e) => {
    const done = e.to_target <= 0;
    return `<div class="ev"><div class="rings">${ring(e.progress, 'prog', 'progress to the target')}${ring(e.room_frac, 'room', 'room above the floor')}
      <span class="pct">${Math.round(e.progress * 100)}%</span></div><div class="evt"><b>${esc(e.bot)} · ${esc(e.plan || e.name)}</b>
      <span>${done ? 'Target reached' : `${esc(usd(e.profit))} of ${esc(usd(e.target, { sign: false, cents: false }))} · ${esc(usd(e.to_target, { sign: false, cents: false }))} to go`}</span>
      <span>${e.room != null ? `Floor ${esc(usd(e.room, { sign: false, cents: false }))} below` : ''}${e.session ? ` · session ${esc(e.session)} of ${esc(e.sessions || 10)}` : ''}</span></div></div>`;
  }).join('');
  return {
    id: 'eval', name: 'Evals', colors: ['#040a1a', '#1a3f8f', '#59d0ff'], mode: 6, ms: 8000,
    html: `<p class="kicker">Evals · now</p>${kt('Road to funded')}<div class="evs" data-z="2">${rows}</div>${odds}
      <p class="note">Outer ring: profit to the target. Inner ring: room above the trailing floor.</p>`,
    enter(el, fx) { if (E.some((e) => e.to_target <= 0)) fx.burst('confetti', 90, { colors: ['#59d0ff', '#f7c948', '#ffffff', '#ff5edb'] }); },
    share: () => ({ kicker: 'Evals', title: 'Road to funded', big: `${Math.round(E[0].progress * 100)}%`, tone: E[0].progress >= 1 ? 'up' : 'flat',
      lines: E.map((e) => `${e.bot} ${e.plan || e.name}: ${usd(e.profit)} of ${usd(e.target, { sign: false, cents: false })}, floor ${usd(e.room, { sign: false, cents: false })} below`) }),
  };
}

function disciplineCard(w, p) {
  const d = p.discipline || {};
  if (d.score == null) return null;
  const rows = (d.rules || []).map((r, i) => `<li style="--i:${i}" class="${r.ok ? 'ok' : 'miss'}"><span class="mk">${r.ok ? '✓' : '✕'}</span><span>${esc(r.label)}</span><b>${r.kept}/${r.total}</b></li>`).join('');
  return {
    id: 'discipline', name: 'Discipline', colors: ['#0d0902', '#6b4a0f', '#f5b84a'], mode: 3, ms: 7500,
    html: `${kick(p)}${kt('Discipline score')}<div class="score" data-z="3"><span class="count big" data-to="${d.score}" data-fmt="int">0</span><small>/100</small></div>
      <ul class="rules">${rows}</ul><p class="note">Checked from the trades: ${esc(d.kept)} of ${esc(d.checked)} rule checks kept.</p>`,
    enter(el, fx) { if (d.score >= 90) fx.burst('sparks', 40, { colors: ['#f5b84a', '#fff1c9'] }); },
    share: () => ({ kicker: `${p.label} · discipline`, title: 'Rules kept', big: `${d.score}/100`, tone: d.score >= 90 ? 'up' : d.score >= 70 ? 'flat' : 'down',
      lines: (d.rules || []).map((r) => `${r.ok ? '✓' : '✕'} ${r.label} ${r.kept}/${r.total}`) }),
  };
}

function learnedCard(w) {
  const L = w.learned || [];
  if (!L.length) return null;
  return {
    id: 'learned', name: 'Learned', colors: ['#06041a', '#3a2a9a', '#c08bff'], mode: 0, ms: 9500,
    html: `<p class="kicker">What the bots learned</p>${kt('Smarter than last week')}<ol class="learn">${L.map((x, i) => `<li style="--i:${i}"><small>${esc(x.tag)}</small>${esc(x.text)}</li>`).join('')}</ol>
      <p class="note">Read-only: nothing changes until you approve it.</p>`,
    enter() {}, share: () => ({ kicker: 'What the bots learned', title: 'Smarter than last week', big: `${L.length} lessons`, tone: 'flat', lines: L.map((x) => x.text) }),
  };
}

function discoveryCard(w, p, peers) {
  const d = peers.discovery;
  if (!d) return null;
  return {
    id: 'discovery', name: 'Discovery', colors: ['#021214', '#0b4a52', '#3fb8ad'], mode: 3, ms: 7500,
    html: `<p class="kicker">Data City · discovery of the week</p>${kt(d.title || 'Discovery')}
      ${d.usd != null ? `<div class="hero" data-z="3">${counter(d.usd, 'lg')}</div>` : d.stat ? `<div class="hero"><span class="count lg flat">${esc(d.stat)}</span></div>` : ''}
      <p class="lesson">${esc(d.text)}</p>`,
    enter(el, fx) { fx.burst('sparks', 30, { colors: ['#7af0e0', '#ffffff'] }); },
    share: () => ({ kicker: 'Data City · discovery', title: d.title || 'Discovery', big: d.usd != null ? usd(d.usd) : d.stat || '', tone: tone(d.usd), lines: [d.text] }),
  };
}

function kalshiCard(w, p, peers) {
  const k = kalshiPeriod(peers.kalshi, p);
  if (!k) {
    return { id: 'kalshi', name: 'Kalshi', colors: ['#04100a', '#145a2e', '#9cff6b'], mode: 1, ms: 5000,
      html: `<p class="kicker">Kalshi · coming soon</p>${kt('The prediction bot joins next')}<p class="lesson">Once the Kalshi bot publishes its feed, its week shows up here: real money, wins, losses, the best strategy.</p>`,
      enter() {}, share: () => ({ kicker: 'Kalshi', title: 'Coming soon', big: 'Kalshi', tone: 'flat', lines: ['The prediction bot joins the recap once its feed is live.'] }) };
  }
  return {
    id: 'kalshi', name: 'Kalshi', colors: ['#04100a', '#145a2e', '#6fd64a'], mode: 1, ms: 7000,
    html: `${kick(p, 'real money')}${kt(k.name)}<div class="hero" data-z="3">${counter(k.net, 'lg')}<p class="sub">${k.balance != null ? `Balance ${esc(usd(k.balance, { sign: false }))} · ` : ''}${esc(plural(k.wins, 'win'))} · ${esc(plural(k.losses, 'loss', 'losses'))} (all time)</p></div>
      ${dayBars(k.days)}${k.top ? `<p class="fact">Best strategy: ${esc(k.top.name)} ${esc(usd(k.top.pnl))}</p>` : ''}${k.running ? '' : '<p class="note">The bot reports it is stopped.</p>'}`,
    enter(el, fx) { if (k.net > 0) fx.burst('coins', 40, { colors: ['#9cff6b'] }); },
    share: () => ({ kicker: `${p.label} · Kalshi`, title: k.name, big: usd(k.net), tone: tone(k.net), lines: [k.balance != null ? `Balance ${usd(k.balance, { sign: false })}` : ''] }),
  };
}

function plannerCard(w, p, peers) {
  const P = peers.planner === undefined ? plannerPeriod(p) : peers.planner;
  if (!P) return null;
  const hab = P.habits.map((h) => `<li><span>${esc(h.name)}</span><b>${h.n}×</b></li>`).join('');
  return {
    id: 'planner', name: 'Planner', colors: ['#140a02', '#7a3d0f', '#ffb36b'], mode: 0, ms: 7000,
    html: `${kick(p, 'Planner')}${kt('Off the charts too')}<div class="split"><div><small>Tasks done</small><b>${P.done}</b></div><div><small>Still open</small><b>${P.open}</b></div><div><small>Events</small><b>${P.events}</b></div></div>
      ${hab ? `<ul class="bots">${hab}</ul>` : ''}${P.top.length ? `<p class="fact">Done: ${P.top.map(esc).join(' · ')}</p>` : ''}`,
    enter() {}, share: () => ({ kicker: `${p.label} · Planner`, title: 'Off the charts too', big: `${P.done} done`, tone: 'flat', lines: P.habits.map((h) => `${h.name}: ${h.n}×`) }),
  };
}

/** The all-time hall: the lifetime numbers and the records (best trade, best day, longest green run, win rate). */
function hallStats(all) {
  if (!all || !all.trades) return null;
  const days = (all.days || []).filter((d) => Array.isArray(d) && num(d[1]) != null);
  let bestDay = null, run = 0, streak = 0;
  for (const [d, v] of days) {
    if (!bestDay || v > bestDay[1]) bestDay = [d, v];
    run = v > 0 ? run + 1 : 0;
    streak = Math.max(streak, run);
  }
  return { net: all.net, perMonth: all.per_month, trades: all.trades, winPct: all.win_pct, from: all.from, best: all.best || null,
    bestDay: bestDay && bestDay[1] > 0 ? bestDay : null, streak, greenDays: days.filter(([, v]) => v > 0).length, days: days.length };
}

function hallCard(w) {
  const H = hallStats(w.periods.all);
  if (!H) return null;
  const plaque = (label, value, sub, cls = '') => `<div class="plaque ${cls}"><small>${esc(label)}</small><b>${esc(value)}</b><i>${esc(sub)}</i></div>`;
  const b = H.best;
  return {
    id: 'hall', name: 'Hall of fame', colors: ['#0b0702', '#5c3d07', '#ffd76a'], mode: 5, ms: 8500,
    html: `<p class="kicker">All time · since ${esc(dayLabel(H.from, { month: 'short', day: 'numeric', year: 'numeric' }))}</p>${kt('The hall of fame', 'title hall-t')}
      <div class="hero" data-z="3">${counter(H.net, 'xl gold')}<p class="sub">${esc(plural(H.trades, 'trade'))} · ${esc(usd(H.perMonth, { cents: false }))} a month on average</p></div>
      <div class="plaques" data-z="2">
        ${b ? plaque('Best trade ever', usd(b.pnl), `${b.bot} · ${dayLabel(b.day)}`, 'up') : ''}
        ${H.bestDay ? plaque('Best day', usd(H.bestDay[1]), dayLabel(H.bestDay[0], { weekday: 'short', month: 'short', day: 'numeric' }), 'up') : ''}
        ${plaque('Longest green run', plural(H.streak, 'day'), `${H.greenDays} of ${H.days} trading days green`)}
        ${H.winPct != null ? plaque('Win rate', `${H.winPct}%`, 'every trade, losses included') : ''}
      </div>`,
    enter(el, fx) { fx.burst('glitter', 70, { colors: ['#ffd76a', '#fff3c4', '#f7c948'] }); },
    share: () => ({ kicker: 'All time · the hall of fame', title: 'The hall of fame', big: usd(H.net), tone: tone(H.net),
      lines: [b ? `Best trade: ${b.bot} ${usd(b.pnl)} (${dayLabel(b.day)})` : '', H.bestDay ? `Best day: ${usd(H.bestDay[1])} (${dayLabel(H.bestDay[0])})` : '',
        `Longest green run: ${plural(H.streak, 'day')}`, H.winPct != null ? `Win rate ${H.winPct}% over ${plural(H.trades, 'trade')}` : ''].filter(Boolean) }),
  };
}

function nextCard(w, p) {
  const n = w.next || { goal: 'Same rules, same edge', why: '' };
  return {
    id: 'next', name: 'Next week', colors: ['#12081f', '#7a2fd1', '#ff5edb'], mode: 1, ms: 9000,
    html: `<p class="kicker">Next week's plan · one goal</p>${kt(n.goal, 'title goal')}<p class="lesson">${esc(n.why)}</p>
      <div class="end"><button type="button" class="btn ghost" data-act="replay">Watch again</button><button type="button" class="btn gold" data-act="share-week">Share the ${p.key === 'month' ? 'month' : p.key === 'all' ? 'story' : 'week'}</button></div>
      <p class="note">${w.demo ? 'DEMO data: the real recap appears once the dashboard publishes.' : `Built ${esc(new Date(w.t * 1000).toLocaleString('en-US', { timeZone: 'America/New_York', weekday: 'short', hour: 'numeric', minute: '2-digit' }))} ET${NBSP}· paper and eval accounts, losses included.`}</p>`,
    enter(el, fx) { fx.burst('confetti', 70, { colors: ['#ff5edb', '#c08bff', '#f7c948', '#ffffff'] }); },
    share: () => ({ kicker: "Next week's plan", title: n.goal, big: 'One goal', tone: 'up', lines: [n.why] }),
  };
}

export function deck(w, key, peers = {}) {
  const p = w.periods[key] || w.periods.week;
  return [money, best, worst, evalCard, disciplineCard, learnedCard, discoveryCard, kalshiCard, plannerCard, hallCard, nextCard]
    .map((f) => f(w, p, peers)).filter(Boolean);
}

// ------------------------------------------------------------------------------------------------ the opening animations
const easeOut = (x) => 1 - Math.pow(1 - x, 4);
export function animateCounts(el, still) {
  const C = [...el.querySelectorAll('.count[data-to]')];
  const fmt = (c, v) => (c.dataset.fmt === 'int' ? String(Math.round(v)) : usd(v));
  if (still) { C.forEach((c) => { c.textContent = fmt(c, +c.dataset.to); }); return () => {}; }
  const t0 = performance.now(), dur = 1500;
  let raf = 0;
  const step = (now) => {
    const k = easeOut(Math.min(1, (now - t0) / dur));
    C.forEach((c) => { c.textContent = fmt(c, +c.dataset.to * k); });
    raf = k < 1 ? requestAnimationFrame(step) : 0;
  };
  raf = requestAnimationFrame(step);
  return () => { if (raf) cancelAnimationFrame(raf); C.forEach((c) => { c.textContent = fmt(c, +c.dataset.to); }); };
}
