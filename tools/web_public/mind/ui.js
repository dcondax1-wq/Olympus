// OLYMPUS Mind: everything on top of the 3D view (plain DOM; vault text only ever goes in as textContent).
//   createUI(handlers) -> {mode, stats, chips, ticker, results, card, labels, timeLapse, quality, toast, noGL}
// handlers: onSearch(q), onPick(id), onFilter(key|null), onTimeLapse(), onQuality(), onCloseCard(), onFly(id)

const $ = (id) => document.getElementById(id);
const fmt = new Intl.NumberFormat('en-US');
const compact = new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 1 });
const big = (n) => (n >= 10000 ? compact.format(n) : fmt.format(n));     // 12.3K fits a stat tile
const MODES = { loading: 'Waking up', live: 'Live vault', demo: 'Demo', offline: 'Vault offline' };
const TICK_EVERY = 7000;

function el(tag, props = {}, kids = []) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (k === 'text') e.textContent = v;
    else if (k === 'style') for (const [p, x] of Object.entries(v)) e.style.setProperty(p, x);
    else if (k.startsWith('on')) e.addEventListener(k.slice(2), v);
    else e.setAttribute(k, v);
  }
  kids.forEach((c) => e.append(c));
  return e;
}

function ago(t, now = Date.now()) {
  if (!t) return 'unknown';
  const s = Math.max(0, (now - t) / 1000);
  if (s < 60) return 'just now';
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  if (s < 86400 * 30) return `${Math.floor(s / 86400)} d ago`;
  const d = new Date(t), sameYear = d.getFullYear() === new Date(now).getFullYear();
  return d.toLocaleDateString('en-US', sameYear ? { month: 'short', day: 'numeric' } : { month: 'short', year: 'numeric' });
}

export function createUI(h) {
  // ---------------------------------------------------------------- search
  const q = $('q'), list = $('results');
  let shown = [], active = -1;
  const pick = (id) => { list.hidden = true; q.blur(); h.onPick(id); };
  q.addEventListener('input', () => h.onSearch(q.value));
  q.addEventListener('focus', () => { if (q.value.trim()) h.onSearch(q.value); });
  q.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault();
      if (!shown.length) return;
      active = (active + (e.key === 'ArrowDown' ? 1 : -1) + shown.length) % shown.length;
      [...list.children].forEach((li, k) => li.setAttribute('aria-selected', String(k === active)));
    } else if (e.key === 'Escape') {
      q.value = ''; h.onSearch('');
    }
  });
  $('search').addEventListener('submit', (e) => {
    e.preventDefault();
    if (shown.length) pick(shown[Math.max(0, active)].id);
  });
  document.addEventListener('pointerdown', (e) => { if (!$('search').contains(e.target)) list.hidden = true; });
  document.addEventListener('keydown', (e) => {
    if (e.key === '/' && document.activeElement !== q) { e.preventDefault(); q.focus(); }
    if (e.key === 'Escape' && !$('card').hidden) h.onCloseCard();
  });

  // ---------------------------------------------------------------- buttons
  $('timelapse').addEventListener('click', () => h.onTimeLapse());
  $('quality').addEventListener('click', () => h.onQuality());
  $('c-close').addEventListener('click', () => h.onCloseCard());
  let cardId = null;
  $('c-fly').addEventListener('click', () => { if (cardId) h.onFly(cardId); });

  // ---------------------------------------------------------------- ticker
  const tkText = $('tk-text'), ticker = $('ticker');
  let items = [], at = 0, rotate = 0;
  const showTick = (text, fresh) => {
    tkText.classList.add('swap');
    setTimeout(() => { tkText.textContent = text; tkText.classList.remove('swap'); }, 180);
    if (fresh) { ticker.classList.remove('fresh'); void ticker.offsetWidth; ticker.classList.add('fresh'); }
  };

  // ---------------------------------------------------------------- labels (galaxy names + the focused note)
  const layer = $('labels'), pool = new Map();
  // the open band between the top HUD and the bottom stats, measured when they change size (never in the frame loop):
  // a galaxy name fades out as it nears either edge instead of sitting under the HUD's glass
  const band = { top: 0, bottom: innerHeight };
  const measure = () => {
    const t = $('top'), b = $('bottom');
    band.top = t ? t.getBoundingClientRect().bottom + 6 : 0;
    band.bottom = b ? b.getBoundingClientRect().top - 6 : innerHeight;
  };
  if (typeof ResizeObserver === 'function') { const ro = new ResizeObserver(measure); ['top', 'bottom'].forEach((k) => $(k) && ro.observe($(k))); }
  addEventListener('resize', measure);
  addEventListener('orientationchange', measure);
  measure();
  const FADE = 28;                                             // px over which a label fades in from the HUD's edge

  return {
    mode(m) {
      const b = $('mode');
      b.dataset.mode = m;
      b.lastElementChild.textContent = MODES[m] || m;
      $('demo').hidden = m !== 'demo';
    },

    stats(s) {
      $('s-notes').textContent = big(s.notes);
      $('s-links').textContent = big(s.links);
      $('s-clusters').textContent = big(s.clusters);
      $('s-learned').textContent = big(s.learnedWeek);
    },

    chips(clusters, current) {
      const box = $('chips');
      box.replaceChildren(...[{ key: null, label: 'All', colour: '#ffffff', count: clusters.reduce((a, c) => a + c.count, 0) }, ...clusters.filter((c) => c.count && c.key !== 'me')]
        .map((c) => el('button', {
          class: 'chip', type: 'button', 'aria-pressed': String(c.key === current), 'data-key': c.key || '', style: { '--c': c.colour },
          onclick: () => h.onFilter(c.key === current ? null : c.key),
        }, [el('i'), el('span', { text: c.label }), el('small', { text: fmt.format(c.count) })])));
    },

    /** The latest learned items (oldest first), the newest shown first then rotating; `fresh` = one just arrived (flash). */
    ticker(learned, fresh) {
      items = learned.slice(-6).reverse();
      clearInterval(rotate);
      at = 0;
      showTick(items.length ? items[0].text : 'Nothing yet. Tell Jarvis something to remember.', fresh);
      if (items.length > 1) rotate = setInterval(() => { at = (at + 1) % items.length; showTick(items[at].text, false); }, TICK_EVERY);
    },

    results(nodes, clusters, query) {
      shown = nodes; active = -1;
      if (!query.trim()) { list.hidden = true; list.replaceChildren(); return; }
      list.replaceChildren(...(nodes.length ? nodes.map((n, k) => el('li', {
        role: 'option', 'aria-selected': 'false', 'data-id': n.id, style: { color: clusters[n.cluster].colour },
        onpointerdown: (e) => e.preventDefault(),
        onclick: () => pick(n.id),
      }, [el('i'), el('b', { text: n.title, style: { color: 'var(--text)' } }), el('small', { text: k === 0 ? '↵' : clusters[n.cluster].label })]))
        : [el('li', { class: 'none', text: 'No note matches' })]));
      list.hidden = false;
    },

    card: {
      show(node, graph, now = Date.now()) {
        cardId = node.id;
        const c = graph.clusters[node.cluster], card = $('card');
        card.style.setProperty('--c', c.colour);
        $('c-cluster').textContent = c.label + (node.kind !== 'note' && node.kind !== c.key ? ` · ${node.kind}` : '');
        $('c-title').textContent = node.title;
        $('c-path').textContent = node.path;
        $('c-tags').replaceChildren(...node.tags.map((t) => el('span', { text: '#' + t })));
        $('c-links').textContent = fmt.format(node.out.length);
        $('c-back').textContent = fmt.format(node.back);
        $('c-words').textContent = fmt.format(node.words);
        $('c-edited').textContent = ago(node.mtime, now);
        $('c-edited').title = node.mtime ? new Date(node.mtime).toLocaleString() : '';
        $('c-snippet').textContent = node.snippet || '';
        $('c-learned').replaceChildren(...graph.learned.filter((l) => l.i === node.i).slice(-3).reverse()
          .map((l) => el('p', {}, [el('b', { text: 'Jarvis learned ' }), document.createTextNode(`${ago(l.t, now)}: ${l.text}`)])));
        const near = [...new Set([...node.out, ...graph.nodes.filter((m) => m.out.includes(node.i)).map((m) => m.i)])]
          .map((i) => graph.nodes[i]).sort((a, b) => b.degree - a.degree).slice(0, 8);
        $('c-near').replaceChildren(...near.map((m) => el('button', {
          type: 'button', style: { '--c': graph.clusters[m.cluster].colour }, onclick: () => h.onFly(m.id),
        }, [el('i'), document.createTextNode(m.title)])));
        card.hidden = false;
        card.scrollTop = 0;
        document.body.classList.add('card-open');
      },
      hide() { cardId = null; $('card').hidden = true; document.body.classList.remove('card-open'); },
    },

    /** list: [{key, text, x, y, alpha, colour, note}] in CSS pixels; labels not in the list are hidden. */
    labels(listed) {
      const seen = new Set();
      for (const l of listed) {
        let alpha = l.alpha;
        if (!l.note) alpha *= Math.max(0, Math.min(1, (l.y - band.top) / FADE, (band.bottom - l.y) / FADE));
        if (alpha < 0.03) continue;                            // under the HUD: hidden below
        let e = pool.get(l.key);
        if (!e) { e = el('span', { class: 'lbl' + (l.note ? ' note' : '') }); pool.set(l.key, e); layer.append(e); }
        if (e.textContent !== l.text) e.textContent = l.text;
        e.style.setProperty('--c', l.colour);
        e.style.opacity = alpha.toFixed(2);
        e.style.transform = `translate(${l.x.toFixed(1)}px, ${l.y.toFixed(1)}px) translate(-50%, ${l.note ? '-160%' : '-50%'})`;
        e.hidden = false;
        seen.add(l.key);
      }
      for (const [k, e] of pool) {
        if (seen.has(k)) continue;
        if (k.startsWith('note:')) { e.remove(); pool.delete(k); } else e.hidden = true;
      }
    },

    timeLapse(state) {
      const box = $('tl'), btn = $('timelapse');
      btn.setAttribute('aria-pressed', String(!!state));
      btn.lastElementChild.textContent = state ? 'Stop' : 'Time-lapse';
      box.hidden = !state;
      if (!state) return;
      $('tl-date').textContent = new Date(state.t).toLocaleDateString('en-US', { month: 'short', year: 'numeric' });
      $('tl-bar').style.width = (state.progress * 100).toFixed(1) + '%';
      $('tl-count').textContent = `${fmt.format(state.count)} notes`;
    },

    quality(q) {
      const b = $('quality');
      b.textContent = q === 'high' ? 'HD' : 'LITE';
      b.setAttribute('aria-pressed', String(q === 'high'));
      b.title = q === 'high' ? 'High quality (tap for the light mode)' : 'Light mode (tap for high quality)';
    },

    toast(text) {
      const t = $('toast');
      t.textContent = text;
      t.hidden = false;
      clearTimeout(t._timer);
      t._timer = setTimeout(() => { t.hidden = true; }, 2600);
    },

    noGL() { $('nogl').hidden = false; },
    /** the open band the galaxy names keep to (tests) */
    band() { return { ...band }; },
  };
}
