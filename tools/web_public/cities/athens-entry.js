// ATHENS entry: adds the "Enter Athens" buttons to Cities and opens the metropolis on demand (nothing heavy loads until then).
// #athens or ?athens=1 opens it directly. Read-only scenery: no order, no trade.
let session = null;
const O = () => window.OLYMPUS || null;

export async function openAthens() {
  if (session) return session;
  const [{ AthensUI }, { Athens }] = await Promise.all([import('./athens-ui.js?v=t1'), import('./athens.js?v=t1')]);
  if (!document.querySelector('link[data-athens-css]')) {
    const l = document.createElement('link'); l.rel = 'stylesheet'; l.href = new URL('./athens.css?v=t1', import.meta.url).href; l.dataset.athensCss = '1'; document.head.append(l);
    await new Promise((r) => { l.onload = l.onerror = r; setTimeout(r, 1500); });
  }
  const q = new URLSearchParams(location.search), lite = !!(O() && O().lite && O().lite()), tier = q.get('q') === 'low' || lite ? 'low' : q.get('q') === 'ultra' ? 'ultra' : 'high';
  const ui = new AthensUI(undefined, { onClose: closeAthens }).mount();
  session = { ui, scene: null, raf: 0, last: 0, closed: false };
  document.documentElement.classList.add('athens-open'); if (O() && O().covered) O().covered(true);
  await new Promise((r) => setTimeout(r, 40));
  try {
    const reduced = !!(O() && O().reduced && O().reduced());
    const scene = new Athens(ui.canvas, { tier, reduced, dusk: false }); scene.resize(); ui.attach(scene); session.scene = scene;
    if (q.get('dusk') === '1') ui.act('time');
    window.__athens = { scene, ui, calls: () => scene.calls, tris: () => scene.trisDrawn, houses: scene.houseCount, tier };
    addEventListener('resize', onResize);
    const loop = (now) => {
      if (session.closed) return; session.raf = requestAnimationFrame(loop);
      if (document.hidden) return;
      const gap = Math.max(O() && O().frameGap ? O().frameGap() : 0, tier === 'low' ? 33 : 0);
      if (now - session.last < gap) return;
      const dt = Math.min(.1, (now - (session.last || now)) / 1000); session.last = now;
      scene.frame(dt, now / 1000); ui.frame();
    };
    session.raf = requestAnimationFrame(loop);
  } catch (err) {
    // no WebGL: the map and the jump list still work
    ui.root.classList.add('nogl', 'bigmap'); ui.root.querySelector('#athLoad')?.remove(); ui.drawStatic(); ui.drawMini();
    const note = document.createElement('div'); note.className = 'ath-fallback'; note.textContent = 'This device cannot draw the 3D city. The map and the list still work.'; ui.root.append(note);
    ui.scene = null; window.__athensError = String(err);
  }
  return session;
}
function onResize() { if (session && session.scene) { session.scene.resize(); session.ui.drawStatic(); } }
export function closeAthens() {
  if (!session) return; session.closed = true; cancelAnimationFrame(session.raf); removeEventListener('resize', onResize);
  try { session.scene && session.scene.dispose(); } catch (e) { /* already gone */ }
  session.ui.root.remove(); document.documentElement.classList.remove('athens-open'); if (O() && O().covered) O().covered(false);
  session = null; delete window.__athens; if (location.hash === '#athens') history.replaceState(null, '', location.pathname + location.search);
}

function addButtons() {
  const mk = (cls) => { const b = document.createElement('button'); b.type = 'button'; b.className = cls; b.textContent = 'Enter Athens'; b.setAttribute('aria-label', 'Enter Athens, the giant Greek metropolis'); b.onclick = () => openAthens(); return b; };
  const actions = document.querySelector('.atlas-actions');
  if (actions && !actions.querySelector('.athens-enter')) actions.append(mk('athens-enter'));
  if (!document.querySelector('.athens-fab')) document.body.append(mk('athens-fab'));
}
function boot() {
  if (!document.querySelector('link[data-athens-btn]')) { const l = document.createElement('link'); l.rel = 'stylesheet'; l.href = new URL('./athens-btn.css?v=t1', import.meta.url).href; l.dataset.athensBtn = '1'; document.head.append(l); }
  addButtons();
  if (location.hash === '#athens' || new URLSearchParams(location.search).get('athens') === '1') openAthens();
}
window.openAthens = openAthens; window.closeAthens = closeAthens;
if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot); else boot();
