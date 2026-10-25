// The "⋯" menu of the cleaned-up PC dashboard (2026-10-25): one primary action per card stays a button, the secondary
// actions move into this small menu. moreMenu(items) returns the HTML; the items are ordinary buttons (data-goto,
// data-copy, an id with its own handler), so every action works exactly as before. One delegated listener opens / closes
// every menu (outside click or Esc closes it, choosing an item closes it). Read-only UI: nothing here talks to the bot.
import { esc } from '../util.js';

export function moreMenu(items, label = 'More actions') {
  return `<div class="nx-more"><button type="button" class="nx-more-b" aria-haspopup="menu" aria-expanded="false" title="${esc(label)}"><span aria-hidden="true">⋯</span></button>
    <div class="nx-more-m" role="menu">${items}</div></div>`;
}
// one menu item: [label, attrs] -> <button ... >label</button>
export const item = (label, attrs = '', ic = '') => `<button type="button" role="menuitem" class="nx-more-i" ${attrs}>${ic}<span>${esc(label)}</span></button>`;

function closeAll(except) {
  document.querySelectorAll('.nx-more.open').forEach((m) => {
    if (m === except) return;
    m.classList.remove('open'); m.querySelector('.nx-more-b')?.setAttribute('aria-expanded', 'false');
  });
}
let wired = false;
export function initMenus() {
  if (wired) return; wired = true;
  document.addEventListener('click', (e) => {
    const b = e.target.closest('.nx-more-b');
    if (b) {
      const m = b.closest('.nx-more'), open = !m.classList.contains('open');
      closeAll(m); m.classList.toggle('open', open); b.setAttribute('aria-expanded', String(open));
      e.stopPropagation(); return;
    }
    const inMenu = e.target.closest('.nx-more-m');
    if (inMenu) {
      // a click on an item closes the menu once the item's own handler ran (segmented controls inside stay open)
      if (e.target.closest('.nx-more-i, .nx-more-row > button, .nx-more-row > .btn')) setTimeout(() => closeAll(), 0);
      return;
    }
    closeAll();
  });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeAll(); });
}
initMenus();
