// ARGUS plus (ES module, 2026-11-04): the Money tab. Can the bot trade today (the gates and a countdown to the 02:00 ET entry window), the two evals in
// money words ("Drawdown left $X of $max loss", the 7-day inactivity clock) and what the red lights of the last 14 days cost (entry-window hours,
// trades at risk). From arguscore.js (readiness, moneyLines, blindCost, demoData). Text only through textContent; read only. With no data it says so
// and offers the demo (?demo=1): never a blank pane.
import { readiness, moneyLines, blindCost, histSummary } from './arguscore.js';

const h = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = String(text); return e; };
const MARK = { ok: 'ok', warn: 'warn', bad: 'bad', idle: 'idle' };

export function renderMoney(box, R, hist, now) {
  if (!box) return null;
  box.replaceChildren();
  if (!R || !R.hasData) {
    box.append(h('p', 'grp', 'MONEY'), h('p', 'empty', 'I cannot see the dashboard yet, so I cannot say whether the bot can trade or how much room the evals have. Open this on Wi-Fi once, or look at a recorded day.'));
    const b = h('a', 'demobtn', 'See it with demo data'); b.href = '?demo=1#money'; b.setAttribute('role', 'button'); box.append(b);
    box.append(h('p', 'grp', 'WHAT YOU WILL SEE HERE'), h('p', 'empty', 'The gates that must be green before 02:00 ET, the drawdown left on Zlarior and ATLAS as "$X of $max loss", the 7-day inactivity clock, and what red lights cost in missed trades.'));
    return null;
  }
  const Rd = readiness(R, now), M = moneyLines(R), B = blindCost(hist, now), S = histSummary(hist, now);
  // ---- can the bot trade today
  box.append(h('p', 'grp', 'CAN THE BOT TRADE TODAY'));
  const head = h('div', 'rdy ' + (Rd.ready ? (Rd.blockers.length ? 'warn' : 'ok') : 'bad'));
  head.append(h('b', '', Rd.ready ? (Rd.blockers.length ? 'YES, WITH A LOOK' : 'YES') : 'NO'), h('span', '', Rd.plain));
  box.append(head, h('p', 'note', Rd.when));
  const list = h('div', 'gates');
  Rd.gates.forEach((g) => { const r = h('div', 'gate ' + MARK[g.level]); r.append(h('i', '', g.level === 'ok' ? '✓' : g.level === 'idle' ? '–' : '!'), h('span', 'gl', g.label), h('span', 'gv', g.value)); list.append(r); });
  box.append(list);
  // ---- the evals in money words
  box.append(h('p', 'grp', 'THE EVALS: DRAWDOWN AND THE 7-DAY CLOCK'));
  M.forEach((m) => {
    const c = h('div', 'mrow ' + MARK[m.level]);
    c.append(h('b', '', m.label), h('span', 'dd', m.ddText));
    const bar = h('span', 'mbar'), i = h('i'); i.style.width = `${m.frac == null ? 0 : Math.round(m.frac * 100)}%`; bar.append(i); c.append(bar);
    c.append(h('span', 'q ' + MARK[m.quietLevel], `Inactivity ${m.quiet}. ${m.quietText || ''}`.trim()));
    box.append(c);
  });
  // ---- what red lights cost
  box.append(h('p', 'grp', 'WHAT RED LIGHTS COST (14 DAYS)'), h('p', 'plainp', B.plain));
  box.append(h('p', 'note', `${S.seen} day${S.seen === 1 ? '' : 's'} seen. The estimate counts the share of red time that falls inside the 13.5-hour entry window.`));
  return { Rd, M, B };
}
