// Trade pictures on the PC dashboard (engine/trade_chart.py PNGs): loads ./tradepics.js (window.TradePics, a byte-identical
// copy of tools/web_public/tradepics.js shared with the phone app) once and reads GET /api/next/charts (the PC bot's own
// pictures in logs/charts + the backtest examples), cached for a minute. Read-only.
let loading = null, cache = null, cacheT = 0;

export function loadPics() {
  if (window.TradePics) return Promise.resolve(window.TradePics);
  if (!loading) loading = new Promise((ok, bad) => {
    const s = document.createElement('script');
    s.src = new URL('./tradepics.js?v=2', import.meta.url).href;
    s.onload = () => ok(window.TradePics); s.onerror = () => { loading = null; bad(new Error('tradepics.js did not load')); };
    document.head.appendChild(s);
  });
  return loading;
}

export async function charts() {
  if (cache && Date.now() - cacheT < 60000) return cache;
  try {
    await loadPics();
    const r = await fetch('/api/next/charts');
    const d = await r.json();
    if (r.ok && d && d.strategies) { cache = d; cacheT = Date.now(); }
  } catch (e) { /* pictures are optional: the page draws without them */ }
  return cache;
}

// one strategy's pictures as a card (latest big + the next ones), or '' when there is none
export function card(ch, key, title) {
  const T = window.TradePics;
  if (!T || !ch || !T.list(ch, key).length) return '';
  return T.latest(ch, key, { title });
}
