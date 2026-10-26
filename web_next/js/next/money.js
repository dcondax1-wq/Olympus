// PC dashboard: Road to $10K / Stingray 3LT (2026-10-26) at the bottom of the Goals page (cc.js goals() calls fillMoney).
// Data: GET /api/next/money (engine/money_api.py -> engine/money_goal.py): the next action, the 9-account stack and
// "My goals" ($10K month, the Stingray 3LT by Feb 22 2027, the Z06). The form under it saves the owner's own figures
// (savings balance, this month's jobs / Kalshi, the targets) with POST /api/next/money, accepted only from a browser on this
// PC (engine/cloud_guard.local_only); the phone sees the same card read-only. Nothing here talks to the bot.
// Renderer: ./moneycore.js (window.MoneyUI, byte-identical to tools/web_public/moneycore.js).
let CP = null;
function loadCore() {
  if (window.MoneyUI && window.MoneyUI.card) return Promise.resolve();
  if (CP) return CP;
  CP = new Promise((res, rej) => {
    const s = document.createElement('script');
    s.src = new URL('./moneycore.js?v=1', import.meta.url).href;
    s.onload = () => res(); s.onerror = () => { CP = null; rej(new Error('moneycore.js did not load')); };
    document.head.appendChild(s);
  });
  return CP;
}
async function save(body) {
  const r = await fetch('/api/next/money', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  return r.json().catch(() => ({ ok: false, error: 'HTTP ' + r.status }));
}
function draw(el, M) {
  const U = window.MoneyUI;
  const lock = M && !M.error && !M.local ? `<p class="mg-note">${M.local_why ? M.local_why.replace(/[<>&]/g, '') : 'Only on the PC itself'}: the numbers can be changed only from the dashboard on this PC.</p>` : '';
  el.innerHTML = `<div class="card nx-glass cc-card cc-money">${U.card(M, { where: 'pc' })}</div>` +
    (M && !M.error && M.local ? `<div class="card nx-glass cc-card cc-money">${U.form(M)}</div>` : lock);
  U.wire(el, M, M && M.local ? { save, done: (card, say) => {
    draw(el, { ...card, local: true });
    el.querySelectorAll('.mg-msg').forEach((m) => { m.textContent = say || 'Saved.'; m.className = 'mg-msg good'; });
  } } : {});
}
export async function fillMoney(el) {
  if (!el) return;
  el.innerHTML = '<div class="cc-skel"></div>';
  let M;
  try {
    await loadCore();
    const r = await fetch('/api/next/money');
    M = await r.json().catch(() => ({ error: 'HTTP ' + r.status }));
    if (!r.ok && !M.error) M = { error: 'HTTP ' + r.status };
  } catch (e) { M = { error: e.message || String(e) }; }
  if (!window.MoneyUI) { el.innerHTML = `<p class="muted">Road to $10K: ${String(M && M.error || 'renderer missing').replace(/[<>&]/g, '')}</p>`; return; }
  draw(el, M);
}
