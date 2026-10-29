// Holodeck (owner 2026-10-29: "a main feature that allows me to see exactly chart fills, very high quality and 3D, where I can see
// what every bot is thinking"): Main group, right after Live View. One day of NQ in 3D (fx.js holo.js) with every fill at its
// exact second and price (real = solid in the bot's colour, paper / model = hollow, the model price as a ghost next to a real
// fill), the trades as glass risk / reward volumes with the stop stepping to break-even, each LIT setup as an annotated
// anatomy, the bots' thoughts as holographic panels, working orders, levels and structure; replay 1x-120x; Live follows the
// bot (GET /api/next/holo every 5 s on today); the day picker reads GET /api/next/holo/days. Read-only.
// The page: ./holocore.js (byte-identical to tools/web_public/holocore.js) + /css/holo.css. No WebGL 2 (or quality "2D"):
// the Live View chart (./liveviewchart.js) with the fills drawn on it. Page section is created here (no index.html change).
import { store } from '../util.js';
import { mountHolodeck } from './holocore.js?v=179d0e69';
import { fxModule, fxLevel } from './fx3d.js';

const ID = 'holo';
let H = null;
function ensure() {
  if (!document.querySelector('link[data-hd]')) {
    const l = document.createElement('link'); l.rel = 'stylesheet'; l.href = new URL('../../css/holo.css?v=3179a369', import.meta.url).href; l.dataset.hd = '1';
    document.head.appendChild(l);
  }
  if (document.getElementById('page-' + ID)) return;
  const ref = document.getElementById('page-cc') || document.querySelector('.page');
  const s = document.createElement('section'); s.className = 'page'; s.id = 'page-' + ID;
  s.innerHTML = '<div class="empty">Loading the Holodeck…</div>';
  (ref?.parentNode || document.querySelector('main') || document.body).appendChild(s);
}
ensure();
async function getJSON(url) {
  const r = await fetch(url, { cache: 'no-store' });
  let j = null; try { j = await r.json(); } catch { j = null; }
  if (!r.ok || !j || j.error) throw new Error((j && j.error) || ('HTTP ' + r.status));
  return j;
}
const env = {
  platform: 'pc', store, every: 5,
  loadFX: () => fxModule(),
  loadChart: () => import('./liveviewchart.js'),
  getDay: (day) => getJSON('/api/next/holo' + (day ? '?day=' + encodeURIComponent(day) : '')),
  getDays: async () => {
    const j = await getJSON('/api/next/holo/days');
    const L = Array.isArray(j) ? j : Array.isArray(j.days) ? j.days : [];
    return L.map((x) => (typeof x === 'string' ? { day: x } : x)).filter((x) => x && x.day);
  },
  quality: fxLevel() === 'lite' ? 'lite' : 'max',
};
export const holo = {
  show: () => {
    ensure();
    const el = document.getElementById('page-' + ID);
    if (H && H.root.classList.contains('hd-max') && H.root.isConnected) return;
    if (!H || !el.contains(H.root)) {
      if (H) { el.innerHTML = ''; el.appendChild(H.root); H.resume(); H.load(H.state.pickedDay || null); }
      else { el.innerHTML = ''; H = mountHolodeck(el, env); }
    } else H.resume();
    window.LE = Object.assign(window.LE || {}, { holo: H });
  },
};
// leaving the page: pause the replay and leave full screen
addEventListener('hashchange', () => setTimeout(() => {
  if (!H || document.getElementById('page-' + ID)?.classList.contains('active')) return;
  if (H.root.classList.contains('hd-max')) H.maxOff();
  H.pause();
}, 0));
