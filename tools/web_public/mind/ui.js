// OLYMPUS Mind: everything on top of the 3D view (plain DOM; vault text only ever goes in as textContent).
// One top bar (name, state, view, quality, search, time-lapse) and one bottom sheet (what Jarvis learned, the thought
// stream, the galaxy chips for focus mode, the numbers); the note card is the sheet opened up.
//   createUI(handlers) -> {mode, stats, chips, focusBar, filterBar, ticker, stream, results, card, labels, timeLapse, quality, view, toast, noGL, band}
// handlers: onSearch(q), onPick(id), onFilter(key|null), onTimeLapse(), onQuality(), onView(), onCloseCard(), onFly(id),
//           resolve(name) -> id | null (a [[wikilink]] in the preview), onClearFilter(), obsidian(node) -> obsidian:// link | null
import { mdPreview } from './markdown.js';
import { $, el, fmt, big, ago } from './dom.js';

const MODES = { loading: 'Waking up', live: 'Live vault', demo: 'Demo', offline: 'Vault offline' };
const TICK_EVERY = 7000;

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
    const panelOpen = !$('panel').hidden;
    if (e.key === 'Escape' && !$('card').hidden) h.onCloseCard();
    else if (e.key === 'Escape' && !panelOpen && !$('focusbar').hidden && document.activeElement !== q) h.onFilter(null);
    else if (e.key === 'Escape' && !panelOpen && !$('filterbar').hidden && document.activeElement !== q) h.onClearFilter();
  });

  // ---------------------------------------------------------------- buttons
  $('timelapse').addEventListener('click', () => h.onTimeLapse());
  $('today').addEventListener('click', () => h.onToday());
  $('day-close').addEventListener('click', () => h.onToday(false));
  $('day-replay').addEventListener('click', () => h.onReplayDay());
  $('quality').addEventListener('click', () => h.onQuality());
  $('view').addEventListener('click', () => h.onView());
  $('focus-exit').addEventListener('click', () => h.onFilter(null));
  $('filter-exit').addEventListener('click', () => h.onClearFilter());
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
    const t = $('top'), b = $('bottom'), p = $('panel');
    band.top = t ? t.getBoundingClientRect().bottom + 6 : 0;
    band.bottom = b ? b.getBoundingClientRect().top - 6 : innerHeight;
    if (p && !p.hidden && p.getBoundingClientRect().width < innerWidth * 0.8) band.bottom = innerHeight;          // a side sheet: the sky stays open
    else if (p && !p.hidden) band.bottom = Math.min(band.bottom, p.getBoundingClientRect().top - 6);
    document.documentElement.style.setProperty('--top-h', (t ? t.getBoundingClientRect().bottom : 0).toFixed(0) + 'px');
  };
  if (typeof ResizeObserver === 'function') { const ro = new ResizeObserver(measure); ['top', 'bottom', 'panel'].forEach((k) => $(k) && ro.observe($(k))); }
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

    /** The Jarvis brain counter: memories she keeps, notes she wrote to the vault, topics (galaxies) the brain spans. */
    brain(c, topics) {
      $('jb-mem').textContent = big(c.memories || 0);
      $('jb-notes').textContent = big(c.written || 0);
      $('jb-topics').textContent = big(Math.max(topics || 0, c.topics || 0));
    },

    stats(s) {
      $('s-notes').textContent = big(s.notes);
      $('s-links').textContent = big(s.links);
      $('s-clusters').textContent = big(s.clusters);
      $('s-learned').textContent = big(s.learnedWeek);
    },

    chips(clusters, current) {
      const box = $('chips');
      box.replaceChildren(...[{ key: null, label: 'All', colour: '#ffffff', count: clusters.reduce((a, c) => a + c.count, 0) }, ...clusters.filter((c) => c.count && c.key !== 'me')
        .sort((a, b) => (a.key === 'memory') - (b.key === 'memory') || b.count - a.count)]
        .map((c) => el('button', {
          class: 'chip', type: 'button', 'aria-pressed': String(c.key === current), 'data-key': c.key || '', style: { '--c': c.colour },
          onclick: () => h.onFilter(c.key === current ? null : c.key),
        }, [el('i'), el('span', { text: c.label }), el('small', { text: fmt.format(c.count) })])));
    },

    /** The tag / filter pill under the top bar ({kind, name, colour} or null). */
    filterBar(f) {
      const bar = $('filterbar');
      bar.hidden = !f;
      if (!f) return;
      bar.style.setProperty('--c', f.colour || 'var(--cyan)');
      $('filter-kind').textContent = f.kind;
      $('filter-name').textContent = f.name;
    },

    /** Focus mode's pill under the top bar (cluster or null). */
    focusBar(c) {
      const bar = $('focusbar');
      bar.hidden = !c;
      if (!c) return;
      bar.style.setProperty('--c', c.colour);
      $('focus-name').textContent = c.label;
    },

    /** The thought stream: [{kind: 'learned' | 'edit', t, text, colour, id}] newest first; `fresh` = ids that just arrived. */
    stream(list, fresh = new Set(), now = Date.now()) {
      const box = $('stream');
      box.replaceChildren(...list.map((x) => el('li', { class: x.kind + (fresh.has(x.key) ? ' new' : '') }, [
        el('button', {
          type: 'button', style: { '--c': x.kind === 'learned' ? 'var(--cyan)' : x.colour }, title: x.text,
          'aria-label': (x.kind === 'learned' ? 'Jarvis learned: ' : 'Edited: ') + x.text, onclick: () => x.id && h.onFly(x.id),
        }, [el('i'), el('small', { text: (x.kind === 'learned' ? 'Learned · ' : 'Edited · ') + ago(x.t, now) }), el('span', { text: x.text })]),
      ])));
      if (fresh.size) box.scrollLeft = 0;
    },

    /** Today's lessons: the count on the button, the 24-hour strip, the list (a tap flies to the note); `log` from graph.dayLog. */
    day(log, nodes, now = Date.now()) {
      const n = log.items.length, nowH = new Date(now).getHours(), peak = Math.max(1, ...log.hours);
      $('today-n').textContent = String(n);
      $('day-sum').textContent = n ? `${n} lesson${n === 1 ? '' : 's'} · ${log.edits} note${log.edits === 1 ? '' : 's'} edited` : `Nothing yet · ${log.edits} note${log.edits === 1 ? '' : 's'} edited`;
      $('day-strip').replaceChildren(...log.hours.map((c, hr) => el('i', {
        class: (c ? 'on ' : '') + (hr === nowH ? 'now' : ''), style: { '--h': String(c ? 0.22 + 0.78 * (c / peak) : 0.08) }, title: `${hr}:00 · ${c}`,
      })));
      $('day-list').replaceChildren(...(n ? log.items.slice().reverse().map((l) => {
        const note = l.i >= 0 && nodes[l.i] ? nodes[l.i] : null, t = new Date(l.t);
        return el('li', {}, [el('button', { type: 'button', 'data-t': String(l.t), onclick: () => note && h.onFly(note.id) }, [
          el('small', { text: t.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' }) }),
          el('span', { text: l.text }), note ? el('em', { text: note.title }) : null].filter(Boolean))]);
      }) : [el('li', { class: 'empty', text: 'Tell Jarvis something to remember and it lands here.' })]));
    },
    dayOpen(open) {
      $('day').hidden = !open; $('today').setAttribute('aria-pressed', String(open));
    },
    /** Light the list row of the lesson being replayed (by time stamp). */
    dayMark(t) {
      for (const b of $('day-list').querySelectorAll('button')) b.classList.toggle('replay', b.dataset.t === String(t));
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
        const link = h.obsidian ? h.obsidian(node) : null, ob = $('c-obsidian');
        ob.hidden = !link;
        if (link) ob.setAttribute('href', link); else ob.setAttribute('href', '#');
        $('c-snippet').replaceChildren(mdPreview(node.snippet || '', { link: h.resolve, onLink: (id) => h.onFly(id) }));
        $('c-learned').replaceChildren(...graph.learned.filter((l) => l.i === node.i).slice(-3).reverse()
          .map((l) => el('p', {}, [el('b', { text: 'Jarvis learned ' }), document.createTextNode(`${ago(l.t, now)}: ${l.text}`)])));
        // links out of the note, then its backlinks (the notes that link to it)
        const byDegree = (a, b) => b.degree - a.degree;
        const out = node.out.map((i) => graph.nodes[i]).sort(byDegree);
        const back = graph.nodes.filter((m) => m.out.includes(node.i)).sort(byDegree);
        const group = (title, list, cls) => (list.length ? [el('h3', { text: `${title} · ${fmt.format(list.length)}` }), el('div', { class: cls }, list.slice(0, 8).map((m) => el('button', {
          type: 'button', style: { '--c': graph.clusters[m.cluster].colour }, onclick: () => h.onFly(m.id),
        }, [el('i'), document.createTextNode(m.title)])))] : []);
        $('c-near').replaceChildren(...group('Links to', out, 'out'), ...group('Linked from', back, 'back'));
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
      $('tl-bar').style.transform = `scaleX(${state.progress.toFixed(3)})`;
      $('tl-count').textContent = `${fmt.format(state.count)} notes`;
    },

    quality(q) {
      const b = $('quality');
      b.textContent = q === 'high' ? 'HD' : 'LITE';
      b.setAttribute('aria-pressed', String(q === 'high'));
      b.title = q === 'high' ? 'High quality (tap for the light mode)' : 'Light mode (tap for high quality)';
    },

    view(v) {
      const b = $('view'), stars = v === 'stars';
      b.setAttribute('aria-pressed', String(stars));
      b.title = stars ? 'Galaxy view' : 'Constellation view';
      b.setAttribute('aria-label', b.title);
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
