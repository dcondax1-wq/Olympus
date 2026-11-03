// ORACLE HUD: the few numbers over the 3D view. Price, P&L today, the stage, the next LIT window, the weather, today's
// nearest levels with their distance in points and $ per MNQ, the open position, and where the data comes from.
// Text only through textContent (nothing from the feed is ever parsed as HTML).
import { litWindow, fmtDur, hm, dayLabel, sessionAt, killzoneAt } from './time.js';
import { kindOf, hex } from './glow.js';

const $ = (id) => document.getElementById(id);
const px = (p) => (p == null ? '–' : p.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }));
export function usd(v, sign = false) {
  if (v == null || !Number.isFinite(v)) return '–';
  const r = Math.round(Math.abs(v)), s = '$' + r.toLocaleString('en-US');
  return r === 0 ? '$0' : v < 0 ? '−' + s : sign ? '+' + s : s;
}
const pts = (d) => (d > 0 ? '+' : d < 0 ? '−' : '') + Math.abs(d).toFixed(2);

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text != null) e.textContent = text;
  return e;
}

export class Hud {
  constructor() {
    this.world = null;
    this.levelsOpen = true;
    $('lv-toggle').addEventListener('click', () => {
      this.levelsOpen = !this.levelsOpen;
      $('levels').classList.toggle('closed', !this.levelsOpen);
      $('lv-toggle').setAttribute('aria-expanded', String(this.levelsOpen));
    });
  }

  /** The source chip: LIVE · 14 s / LAST SEEN 09:41 / SITE · 12 min / DEMO · replay. */
  mode(mode, w, extra = {}) {
    const m = $('mode');
    m.dataset.mode = mode;
    const txt = mode === 'live' ? `LIVE · ${w.age_s < 90 ? w.age_s + ' s' : Math.round(w.age_s / 60) + ' min'}`
      : mode === 'site' ? `CLOUD · ${Math.round(w.age_s / 60)} min`
      : mode === 'stale' ? `LAST SEEN ${dayLabel(w.t)} ${hm(w.t)}`
      : mode === 'demo' ? 'DEMO' : 'CONNECTING';
    m.querySelector('span').textContent = txt;
    $('replay').hidden = !(mode === 'stale' || (mode === 'demo' && extra.canLeave));
    $('replay').textContent = mode === 'demo' ? 'Back to live' : 'Replay a day';
    $('demo-bar').hidden = mode !== 'demo';
    $('demo-tag').textContent = `REPLAY · ${extra.day || ''}`;
  }

  render(w) {
    this.world = w;
    $('price').textContent = px(w.price);
    const p = $('pnl');
    p.textContent = usd(w.pnlNow, true);
    p.dataset.sign = w.pnlNow > 0 ? 'up' : w.pnlNow < 0 ? 'down' : 'flat';
    $('pnl-note').textContent = w.position ? `incl. open ${usd(w.position.usd, true)}` : '';
    // the stage
    $('stage-n').textContent = w.stage.n ? `${w.stage.n}/${w.stage.of}` : '–';
    $('stage-label').textContent = w.stage.label + (w.stage.dir ? (w.stage.dir > 0 ? ' · long' : ' · short') : '');
    $('waiting').textContent = w.stage.waiting || '';
    // the weather
    const wx = $('wx');
    wx.replaceChildren(
      ...[w.vix && w.vix.vix != null ? `VIX ${w.vix.vix.toFixed(1)}` : null, w.atr != null ? `ATR ${w.atr.toFixed(1)}` : null,
        w.regime ? (w.regime.trend === 'up' ? 'Trend ↑' : w.regime.trend === 'down' ? 'Trend ↓' : 'Range') : null,
        w.regime && w.regime.vol !== 'normal' ? (w.regime.vol === 'high' ? 'High vol' : 'Quiet') : null]
        .filter(Boolean).map((t) => el('span', 'chip', t)));
    this.renderLevels(w);
    this.renderPosition(w);
  }

  renderLevels(w) {
    const up = w.levels.filter((l) => !l.taken && l.dist != null && l.dist > 0).sort((a, b) => a.dist - b.dist).slice(0, 3).reverse();
    const dn = w.levels.filter((l) => !l.taken && l.dist != null && l.dist < 0).sort((a, b) => b.dist - a.dist).slice(0, 3);
    const row = (l, far) => {
      const li = el('li', far ? 'lv far' : 'lv');
      li.dataset.id = l.id;
      li.dataset.dist = String(l.dist);
      li.dataset.usd = String(l.usd);
      const dot = el('i');
      dot.style.background = hex(kindOf(l.kind).color);
      li.append(dot, el('span', 'lv-name', l.label), el('span', 'lv-px', px(l.price)), el('span', 'lv-d', pts(l.dist)), el('span', 'lv-usd', usd(l.usd)));
      return li;
    };
    const now = el('li', 'lv now');
    now.append(el('i'), el('span', 'lv-name', 'Price'), el('span', 'lv-px', px(w.price)), el('span', 'lv-d', 'pts'), el('span', 'lv-usd', '/ MNQ'));
    const taken = w.levels.filter((l) => l.taken).length;
    $('lv-list').replaceChildren(...up.map((l, i) => row(l, i === 0 && up.length === 3)), now, ...dn.map((l, i) => row(l, i === 2)));
    $('lv-meta').textContent = `${w.levels.length - taken} open · ${taken} swept`;
  }

  renderPosition(w) {
    const p = w.position, box = $('pos');
    box.hidden = !p;
    if (!p) return;
    box.dataset.side = p.side.toLowerCase();
    $('pos-side').textContent = `${p.side} ${p.qty} @ ${px(p.entry)}`;
    $('pos-levels').textContent = `stop ${p.be ? 'BE ' : ''}${px(p.stop)} · tgt ${px(p.target)}`;
    const v = $('pos-pnl');
    v.textContent = usd(p.usd, true);
    $('pos-r').textContent = p.r == null ? '' : `${p.r >= 0 ? '+' : '−'}${Math.abs(p.r).toFixed(2)}R`;
    v.dataset.sign = (p.usd || 0) >= 0 ? 'up' : 'down';
  }

  /** Every second: the LIT window countdown and the session (they move even when the data does not). */
  tick(nowT) {
    const w = this.world, lw = litWindow(nowT, w && w.src !== 'demo' ? w.windows : null), s = sessionAt(nowT);
    const box = $('window');
    box.dataset.open = String(lw.open);
    $('win-text').textContent = lw.open_t == null ? 'No LIT window in the next days'
      : lw.open ? `LIT window open · closes in ${fmtDur(lw.in_s)}` : `Next LIT window in ${fmtDur(lw.in_s)} · ${dayLabel(lw.open_t)} ${hm(lw.open_t)} ET`;
    $('session').textContent = `${s.label}${killzoneAt(nowT) ? ' killzone' : ''} · ${hm(nowT)} ET`;
  }

  demoProgress(t, span) {
    $('demo-time').textContent = `${hm(t)} ET`;
    $('demo-fill').style.transform = `scaleX(${Math.max(0, Math.min(1, (t - span.from) / (span.to - span.from))).toFixed(4)})`;
  }

  /** The part of the screen the HUD leaves free (CSS px); the scene centres itself there (it may run a little under the glass). */
  freeRect() {
    const W = innerWidth, H = innerHeight, t = $('top').getBoundingClientRect(), d = $('dock').getBoundingClientRect();
    if (W > H && H <= 500) return { x0: t.right * 0.75, y0: 0, x1: d.left + (W - d.left) * 0.25, y1: H };
    return { x0: 0, y0: t.bottom - 28, x1: W, y1: d.top + 16 };
  }

  quality(q) {
    const b = $('quality');
    b.textContent = q === 'high' ? 'HD' : 'LITE';
    b.setAttribute('aria-pressed', String(q === 'high'));
  }

  noGL() { $('nogl').hidden = false; }
}
