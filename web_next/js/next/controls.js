// Control layer for the redesigned dashboard. Runs over every page (including the shared page modules in web/js):
//  - every <select> becomes a custom dropdown (the native select stays in the DOM, hidden, as the source of truth:
//    page code keeps reading .value and listening for 'change')
//  - unicode glyphs in button labels (⟳ ▶ ✕ ⚙ ...) become SVG icons
// A MutationObserver applies both to anything a page renders later.
import { icon, GLYPH } from './icons.js';
import { esc } from '../util.js';

// ------------------------------------------------------------------ custom select
const SEL = new WeakMap();   // select -> { wrap, btn, label }
let openMenu = null;

function labelOf(sel) {
  const o = sel.options[sel.selectedIndex];
  return o ? o.textContent : (sel.options[0]?.textContent || '—');
}
function sync(sel) {
  const s = SEL.get(sel);
  if (!s) return;
  s.label.textContent = labelOf(sel);
  s.btn.disabled = sel.disabled;
  s.wrap.classList.toggle('sm', sel.classList.contains('sm'));
}

function closeMenu() {
  if (!openMenu) return;
  openMenu.menu.remove();
  openMenu.btn.setAttribute('aria-expanded', 'false');
  openMenu.btn.classList.remove('open');
  openMenu = null;
}

function choose(sel, idx) {
  if (idx < 0 || idx === sel.selectedIndex) { closeMenu(); return; }
  sel.selectedIndex = idx;
  sync(sel);
  sel.dispatchEvent(new Event('input', { bubbles: true }));
  sel.dispatchEvent(new Event('change', { bubbles: true }));
  closeMenu();
}

function openFor(sel) {
  const s = SEL.get(sel);
  if (!s || sel.disabled) return;
  if (openMenu?.sel === sel) { closeMenu(); return; }
  closeMenu();
  const menu = document.createElement('div');
  menu.className = 'nx-menu';
  menu.setAttribute('role', 'listbox');
  let html = '', i = 0;
  for (const child of sel.children) {
    if (child.tagName === 'OPTGROUP') {
      html += `<div class="nx-menu-grp">${esc(child.label)}</div>`;
      for (const o of child.children) html += item(o, i++);
    } else html += item(child, i++);
  }
  function item(o, idx) {
    const on = idx === sel.selectedIndex;
    return `<button type="button" role="option" class="nx-opt${on ? ' on' : ''}" data-i="${idx}" ${o.disabled ? 'disabled' : ''} aria-selected="${on}">
      <span>${esc(o.textContent)}</span>${on ? icon('check') : ''}</button>`;
  }
  menu.innerHTML = html || '<div class="nx-menu-grp">No options</div>';
  document.body.appendChild(menu);
  const r = s.btn.getBoundingClientRect();
  menu.style.minWidth = Math.max(r.width, 180) + 'px';
  const w = menu.offsetWidth;
  const left = Math.max(8, Math.min(r.left, innerWidth - w - 8));
  const below = innerHeight - r.bottom - 12, above = r.top - 12;
  const h = Math.min(menu.scrollHeight, 340);
  menu.style.left = left + 'px';
  if (below >= Math.min(h, 220) || below >= above) { menu.style.top = (r.bottom + 6) + 'px'; menu.style.maxHeight = Math.max(140, below) + 'px'; }
  else { menu.style.bottom = (innerHeight - r.top + 6) + 'px'; menu.style.maxHeight = Math.max(140, above) + 'px'; }
  // scroll the chosen option into view inside the menu only (scrollIntoView could scroll the page and close the menu)
  const on = menu.querySelector('.nx-opt.on');
  if (on) menu.scrollTop = Math.max(0, on.offsetTop - menu.clientHeight / 2 + on.offsetHeight / 2);
  menu.addEventListener('click', (e) => { const b = e.target.closest('.nx-opt'); if (b && !b.disabled) choose(sel, +b.dataset.i); });
  s.btn.setAttribute('aria-expanded', 'true');
  s.btn.classList.add('open');
  openMenu = { sel, btn: s.btn, menu, top: r.top, left: r.left };
  (menu.querySelector('.nx-opt.on') || menu.querySelector('.nx-opt'))?.focus({ preventScroll: true });
}

function menuKeys(e) {
  if (!openMenu) return;
  // the menu owns the keyboard while open: page shortcuts (ux.js, replay keys) must not see these keys
  if (e.key !== 'Tab') e.stopPropagation();
  const opts = [...openMenu.menu.querySelectorAll('.nx-opt:not([disabled])')];
  const cur = opts.indexOf(document.activeElement);
  if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); const b = openMenu.btn; closeMenu(); b.focus(); }
  else if (e.key === 'ArrowDown') { e.preventDefault(); opts[Math.min(opts.length - 1, cur + 1)]?.focus(); }
  else if (e.key === 'ArrowUp') { e.preventDefault(); opts[Math.max(0, cur - 1)]?.focus(); }
  else if (e.key === 'Tab') closeMenu();
  else if (e.key.length === 1 && /\S/.test(e.key)) {
    const k = e.key.toLowerCase();
    const hit = opts.find((o, i) => i > cur && o.textContent.trim().toLowerCase().startsWith(k)) || opts.find(o => o.textContent.trim().toLowerCase().startsWith(k));
    hit?.focus();
  }
}

function enhanceSelect(sel) {
  if (SEL.has(sel) || sel.multiple || sel.closest('.nx-native')) return;
  const wrap = document.createElement('span');
  wrap.className = 'nx-select';
  const btn = document.createElement('button');
  btn.type = 'button';
  btn.className = 'nx-select-btn';
  btn.setAttribute('aria-haspopup', 'listbox');
  btn.setAttribute('aria-expanded', 'false');
  if (sel.title) btn.title = sel.title;
  const label = document.createElement('span');
  label.className = 'nx-select-v';
  btn.append(label);
  btn.insertAdjacentHTML('beforeend', icon('down', 'nx-chev'));
  sel.parentNode.insertBefore(wrap, sel);
  wrap.append(sel, btn);
  sel.classList.add('nx-hidden-select');
  sel.tabIndex = -1;
  sel.setAttribute('aria-hidden', 'true');
  if (sel.id) btn.id = sel.id + '__nx';
  SEL.set(sel, { wrap, btn, label });
  btn.addEventListener('click', (e) => { e.stopPropagation(); openFor(sel); });
  btn.addEventListener('keydown', (e) => {
    if (['ArrowDown', 'ArrowUp', 'Enter', ' '].includes(e.key)) { e.preventDefault(); e.stopPropagation(); openFor(sel); }
  });
  sel.addEventListener('change', () => sync(sel));
  new MutationObserver(() => sync(sel)).observe(sel, { childList: true, subtree: true, attributes: true, characterData: true });
  sync(sel);
}

// page code sets select.value / selectedIndex directly: patch the setters so the custom button follows
function patchSelectSetters() {
  const proto = HTMLSelectElement.prototype;
  for (const prop of ['value', 'selectedIndex']) {
    const d = Object.getOwnPropertyDescriptor(proto, prop);
    if (!d?.set || d.set.__nx) continue;
    const set = function (v) { d.set.call(this, v); if (SEL.has(this)) sync(this); };
    set.__nx = true;
    Object.defineProperty(proto, prop, { ...d, set });
  }
}

// ------------------------------------------------------------------ glyph -> icon
const GLYPHS = Object.keys(GLYPH).sort((a, b) => b.length - a.length);
function swapGlyph(btn) {
  if (btn.closest('.nx-keep-glyph')) return;
  // icon-only buttons and buttons whose label starts / ends with a glyph
  const txt = btn.textContent.trim();
  if (!txt) return;
  const first = btn.firstChild, last = btn.lastChild;
  let done = false;
  if (first?.nodeType === 3) {
    const t = first.textContent.replace(/^\s+/, '');
    const g = GLYPHS.find(x => t.startsWith(x));
    if (g) { first.textContent = t.slice(g.length).replace(/^[\s︎️]+/, ''); first.before(frag(GLYPH[g])); done = true; }
  } else if (first?.nodeType === 1 && first.tagName === 'SPAN' && !first.querySelector('svg')) {
    const t = first.textContent.trim().replace(/[︎️]/g, '');
    if (GLYPH[t]) { first.replaceWith(frag(GLYPH[t])); done = true; }
  }
  if (!done && last?.nodeType === 3) {
    const t = last.textContent.replace(/\s+$/, '').replace(/[︎️]+$/, '');
    const g = GLYPHS.find(x => t.endsWith(x));
    if (g && t.length > g.length) { last.textContent = t.slice(0, -g.length).replace(/\s+$/, ''); last.after(frag(GLYPH[g], 'trail')); }
  }
  if (btn.querySelector(':scope > svg.ico') && !btn.textContent.trim()) btn.classList.add('nx-iconly');
  else btn.classList.remove('nx-iconly');
}
function frag(name, cls = '') {
  const t = document.createElement('template');
  t.innerHTML = icon(name, cls);
  return t.content.firstChild;
}

// ------------------------------------------------------------------ observer
const BTN_SEL = 'button.btn, a.btn, .seg button, .card-tools button, .w-tools button, .pop button';
function scan(root) {
  if (!(root instanceof Element)) return;
  if (root.matches?.('select')) enhanceSelect(root);
  root.querySelectorAll?.('select').forEach(enhanceSelect);
  if (root.matches?.(BTN_SEL)) swapGlyph(root);
  root.querySelectorAll?.(BTN_SEL).forEach(swapGlyph);
}
let queue = new Set(), raf = 0;
function flush() {
  raf = 0;
  const q = queue; queue = new Set();
  for (const n of q) if (n.isConnected) scan(n);
}

export function initControls() {
  patchSelectSetters();
  scan(document.body);
  new MutationObserver((muts) => {
    for (const m of muts) {
      if (m.type === 'childList') {
        m.addedNodes.forEach(n => { if (n.nodeType === 1 && !n.classList?.contains('nx-menu') && !(n instanceof SVGElement)) queue.add(n); });
        // a button whose label was replaced (textContent = '🔇') gets re-checked
        const host = m.target.closest?.(BTN_SEL);
        if (host) queue.add(host);
      } else if (m.type === 'characterData') {
        const host = m.target.parentElement?.closest?.(BTN_SEL);
        if (host) queue.add(host);
      }
    }
    if (queue.size && !raf) raf = requestAnimationFrame(flush);
  }).observe(document.body, { childList: true, subtree: true, characterData: true });
  document.addEventListener('keydown', menuKeys, true);
  document.addEventListener('pointerdown', (e) => { if (openMenu && !openMenu.menu.contains(e.target) && !openMenu.btn.contains(e.target)) closeMenu(); }, true);
  addEventListener('resize', closeMenu);
  // close when the page scroll actually moves the button away (small scroll jitter on phones keeps it open)
  document.addEventListener('scroll', (e) => {
    if (!openMenu || openMenu.menu.contains(e.target)) return;
    const r = openMenu.btn.getBoundingClientRect();
    if (Math.abs(r.top - openMenu.top) > 24 || Math.abs(r.left - openMenu.left) > 24) closeMenu();
  }, true);
}
