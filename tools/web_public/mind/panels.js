// OLYMPUS Mind: the nine pages that open from the dock under the search bar. Plain DOM; vault text only ever goes in as textContent.
//   Home      the dashboard: notes, links, galaxies, streak, today's learning, growth chart, quick actions
//   Notes     glass cards with previews and tags, a tag cloud, galaxy chips, sorting
//   Days      the daily-notes timeline: each day's daily note, edits and lessons
//   Learned   what Jarvis learned, as a feed with replay
//   Graph     links and backlinks: filters (linked, hubs, orphans, recent, min links), the local map of a note, hubs, orphans, galaxies
//   Review    spaced-repetition questions from your notes
//   Teach     tell Jarvis a fact or save a note (written in Jarvis's own formats, teach.js)
//   Stats     the numbers: level, galaxies, weekly bars, records
//   Look      skins, the nebula sky, ambient particles, sounds, the Obsidian vault name
//   createPanels(h) -> {open(name), close(), update(ctx), current}
// ctx: {g (graph), mode, now, live: {counts, items}, prefs: {skin, sky, dust, sound, vault}, review (cards), tag, gmode, gmin, filter, focus, soundOk}
// h: fly(id), cluster(key | null), tag(tag | null), gmode(mode, min), replay(items), teach(input) -> result, skin(id), pref(name, value),
//    review(state), play(sfx), surprise(), toast(text)
import { $, el, svg, fmt, big, ago, dayKey, dayLabel } from './dom.js';
import { brainStats, ego, greeting, hubs, learnedFeed, orphans, previewText, tagCloud, timeline } from './insights.js';
import { boxes, buildDeck, dueCount, grade, pickSession } from './quiz.js';
import { screen } from './teach.js';
import { SKINS } from './skins.js';

const TITLES = { home: 'Home', notes: 'Notes', days: 'Days', learned: 'Learned', graph: 'Graph', review: 'Review', teach: 'Teach Jarvis', stats: 'Stats', look: 'Look' };
const PANELS = Object.keys(TITLES);
const MODES = [['all', 'All'], ['linked', 'Linked'], ['hubs', 'Hubs'], ['orphans', 'Orphans'], ['recent', 'Recent']];
let uid = 0;
let deckMemo = { g: null, deck: [] };                       // the questions are made once per graph, not on every repaint
const deckOf = (g, now) => { if (deckMemo.g !== g) deckMemo = { g, deck: buildDeck(g, now) }; return deckMemo.deck; };

// ------------------------------------------------------------------ small parts
const seg = (options, current, onPick, label) => el('div', { class: 'seg', role: 'group', 'aria-label': label || 'Choose' },
  options.map(([key, text]) => el('button', { type: 'button', 'aria-pressed': String(key === current), 'data-k': key, text, onclick: () => onPick(key) })));

const dot = (c) => el('i', { class: 'dot', style: { '--c': c } });
const empty = (text, action) => el('div', { class: 'empty' }, [el('p', { text }), action || null]);
const noun = (n, w) => `${n} ${w}${n === 1 ? '' : 's'}`;
/** what the owner can do when a page has nothing to show: teach Jarvis, look at a grown (demo) brain, or come back to the real one */
const acts = (h, ctx) => el('div', { class: 'toolbar' }, [
  el('button', { class: 'cta', type: 'button', text: 'Teach Jarvis', onclick: () => h.open('teach') }),
  el('button', { class: 'cta ghosty', type: 'button', text: ctx && ctx.preview ? 'Back to my vault' : 'Preview a demo brain', onclick: () => h.preview() })]);
const head = (text, aside) => el('h3', { class: 'sec' }, [el('span', { text }), aside || null]);

function tile(k, label, value, hint, c) {
  return el('div', { class: 'tile', 'data-k': k, style: c ? { '--c': c } : {} }, [el('b', { text: value }), el('span', { text: label }), hint ? el('small', { text: hint }) : null]);
}

/** A smooth glowing area chart of numbers (oldest first). */
function areaChart(values, { w = 320, h = 96, colour = 'var(--cyan)', label = '' } = {}) {
  const id = 'ac' + uid++, pad = 8, n = values.length;
  const lo = Math.min(...values), hi = Math.max(...values), span = Math.max(1, hi - lo);
  const x = (k) => pad + (n === 1 ? 0.5 : k / (n - 1)) * (w - pad * 2), y = (v) => h - pad - ((v - lo) / span) * (h - pad * 2 - 6);
  const pts = values.map((v, k) => [x(k), y(v)]);
  const line = pts.map(([a, b], k) => (k ? 'L' : 'M') + a.toFixed(1) + ' ' + b.toFixed(1)).join(' ');
  const last = pts[pts.length - 1];
  return svg('svg', { viewBox: `0 0 ${w} ${h}`, class: 'chart', role: 'img', 'aria-label': label }, [
    svg('defs', {}, [svg('linearGradient', { id, x1: 0, y1: 0, x2: 0, y2: 1 }, [
      svg('stop', { offset: '0%', 'stop-color': colour, 'stop-opacity': '0.45' }), svg('stop', { offset: '100%', 'stop-color': colour, 'stop-opacity': '0' })])]),
    svg('path', { d: `${line} L${last[0].toFixed(1)} ${h - pad} L${pts[0][0].toFixed(1)} ${h - pad} Z`, fill: `url(#${id})` }),
    svg('path', { d: line, fill: 'none', stroke: colour, 'stroke-width': '2', 'stroke-linejoin': 'round', 'stroke-linecap': 'round', class: 'glowline' }),
    svg('circle', { cx: last[0].toFixed(1), cy: last[1].toFixed(1), r: '5', fill: colour, class: 'pulse' }),
    svg('circle', { cx: last[0].toFixed(1), cy: last[1].toFixed(1), r: '2.2', fill: '#fff' }),
  ]);
}

/** Vertical bars (oldest first), the last one lit. */
function barChart(values, { colour = 'var(--cyan)', labels = [], label = '' } = {}) {
  const peak = Math.max(1, ...values);
  return el('div', { class: 'cbars', role: 'img', 'aria-label': label }, values.map((v, k) => el('div', { class: 'cbar' + (k === values.length - 1 ? ' now' : ''), style: { '--h': String(0.06 + 0.94 * (v / peak)), '--c': colour }, title: `${labels[k] || ''} ${v}`.trim() },
    [el('i'), el('small', { text: String(v) })])));
}

function ring(progress, text, sub) {
  const r = 34, c = 2 * Math.PI * r;
  return el('div', { class: 'ringbox' }, [
    svg('svg', { viewBox: '0 0 84 84', 'aria-hidden': 'true' }, [
      svg('circle', { cx: 42, cy: 42, r, fill: 'none', stroke: 'rgba(255,255,255,.1)', 'stroke-width': 7 }),
      svg('circle', { cx: 42, cy: 42, r, fill: 'none', stroke: 'var(--cyan)', 'stroke-width': 7, 'stroke-linecap': 'round', class: 'glowline',
        'stroke-dasharray': `${(c * progress).toFixed(1)} ${c.toFixed(1)}`, transform: 'rotate(-90 42 42)' })]),
    el('div', {}, [el('b', { text }), el('small', { text: sub })])]);
}

function noteCard(n, g, ctx, h, now) {
  const c = g.clusters[n.cluster];
  return el('button', { class: 'ncard', type: 'button', style: { '--c': c.colour }, 'data-id': n.id, onclick: () => h.fly(n.id), 'aria-label': 'Open ' + n.title }, [
    el('span', { class: 'nc-top' }, [dot(c.colour), el('span', { text: c.label }), el('em', { text: ago(n.mtime, now) })]),
    el('strong', { text: n.title }),
    el('span', { class: 'nc-pre', text: previewText(n) }),
    n.tags.length ? el('span', { class: 'nc-tags' }, n.tags.slice(0, 3).map((t) => el('span', { text: '#' + t }))) : null,
    el('span', { class: 'nc-meta' }, [el('span', { text: `${fmt.format(n.words)} words` }), el('span', { text: `${n.out.length + n.back} links` })]),
  ]);
}

function row(n, g, h, extra, now) {
  const c = g.clusters[n.cluster];
  return el('button', { class: 'row', type: 'button', style: { '--c': c.colour }, onclick: () => h.fly(n.id) }, [
    dot(c.colour), el('span', { class: 'r-t', text: n.title }), el('small', { text: extra || ago(n.mtime, now) })]);
}

// ------------------------------------------------------------------ the views
function homeView(h) {
  const root = el('div', { class: 'view pg-home' });
  return {
    root,
    render(ctx) {
      const { g, now } = ctx, s = brainStats(g, now), lv = s.level, due = dueCount(deckOf(g, now), ctx.review, now);
      const demo = ctx.mode === 'demo', hero = el('div', { class: 'hero' }, [
        el('div', {}, [
          el('p', { class: 'hello', text: greeting(now) }),
          el('h2', { text: demo ? 'Your brain, in demo' : ctx.mode === 'offline' ? 'Your brain (vault offline)' : 'Your brain' }),
          el('p', { class: 'sub', text: demo ? 'Showing a demo brain. Connect your vault in Jarvis ⋯ → Connect Obsidian.' : ctx.mode === 'offline' ? 'The vault is offline, so this is the last brain Jarvis saw.' : `${noun(s.notes, 'note')} and ${noun(s.links, 'link')}, growing every day.` }),
          demo ? el('span', { class: 'pill demo-pill', text: ctx.preview ? 'DEMO PREVIEW' : 'DEMO' }) : null]),
        ring(lv.progress, 'Lv ' + lv.level, lv.name)]);
      const tiles = el('div', { class: 'tiles' }, [
        tile('notes', 'Notes', big(s.notes), `${s.tags} tags`), tile('links', 'Links', big(s.links), `${s.avgLinks} per note`),
        tile('topics', 'Galaxies', String(s.galaxies.length), 'topics'), tile('streak', 'Streak', `${s.streak.current}d`, `best ${s.streak.best}d`, 'var(--gold)'),
        tile('today', 'Learned today', String(s.today), `${s.learned} in all`), tile('orphans', 'Orphans', String(s.orphans), 'no links yet')]);
      const chart = el('div', { class: 'card2' }, [
        head('Brain growth', el('small', { text: 'last 12 weeks' })),
        areaChart(s.growth.map((p) => p.total), { label: `Notes over the last 12 weeks, now ${s.notes}` }),
        el('div', { class: 'axis' }, [el('span', { text: 'notes by last edit' }), el('b', { text: '+' + fmt.format(s.growth.slice(-4).reduce((a, p) => a + p.added, 0)) + ' this month' })])]);
      const todays = learnedFeed(g).filter((x) => dayKey(x.t) === dayKey(now)).slice(0, 3);
      const learn = el('div', { class: 'card2' }, [
        head("Today's learning", el('button', { class: 'mini', type: 'button', text: 'Replay', onclick: () => todays.length ? h.replay(todays) : h.open('teach') })),
        todays.length ? el('div', { class: 'list' }, todays.map((x) => el('button', { class: 'row learn', type: 'button', onclick: () => (x.i >= 0 ? h.fly(g.nodes[x.i].id) : h.open('learned')) },
          [dot('var(--cyan)'), el('span', { class: 'r-t', text: x.text }), el('small', { text: ago(x.t, now) })])))
          : empty('Nothing yet today. Tell Jarvis one thing and watch a spark fly.', el('button', { class: 'cta', type: 'button', text: 'Teach Jarvis', onclick: () => h.open('teach') }))]);
      const actions = el('div', { class: 'actions' }, [
        el('button', { class: 'act', type: 'button', onclick: () => h.open('teach') }, [el('b', { text: 'Teach' }), el('small', { text: 'tell Jarvis' })]),
        el('button', { class: 'act', type: 'button', onclick: () => h.open('review') }, [el('b', { text: 'Review' }), el('small', { text: due ? `${due} to practise` : 'all caught up' })]),
        el('button', { class: 'act', type: 'button', onclick: () => h.surprise() }, [el('b', { text: 'Surprise me' }), el('small', { text: 'a random note' })]),
        el('button', { class: 'act', type: 'button', onclick: () => h.open('graph') }, [el('b', { text: 'Explore' }), el('small', { text: 'hubs and orphans' })])]);
      const topic = el('div', { class: 'card2' }, [head('Galaxies'), el('div', { class: 'gal' }, s.galaxies.filter((c) => c.key !== 'me').slice(0, 6).map((c) => el('button', {
        class: 'galrow', type: 'button', style: { '--c': c.colour, '--w': String(c.count / Math.max(1, s.galaxies[0].count)) }, onclick: () => h.cluster(c.key) },
      [dot(c.colour), el('span', { text: c.label }), el('i'), el('small', { text: fmt.format(c.count) })])))]);
      const kids = [hero, tiles, actions, chart, learn, topic];
      if (s.notes < 15 && ctx.mode !== 'demo') {
        kids.push(el('div', { class: 'card2 start' }, [head('Grow your brain'), el('ol', {}, [el('li', { text: 'Teach Jarvis a fact about you.' }), el('li', { text: 'Write a note and link it with [[double brackets]].' }), el('li', { text: 'Come back tomorrow to keep the streak.' })]), acts(h, ctx)]));
      } else if (ctx.preview) kids.push(el('div', { class: 'card2 start' }, [head('This is a demo brain'), el('p', { class: 'sub', text: 'Every galaxy, link and lesson here is made up so you can see what a grown brain feels like. Your own vault is untouched.' }), acts(h, ctx)]));
      root.replaceChildren(...kids);
    },
  };
}

function notesView(h) {
  const st = { q: '', sort: 'recent', cluster: null, more: 24 };
  const search = el('input', { type: 'search', placeholder: 'Filter notes', 'aria-label': 'Filter notes', spellcheck: 'false', enterkeyhint: 'search', class: 'field' });
  const sortBox = el('div'), galBox = el('div', { class: 'chiprow' }), cloud = el('div', { class: 'cloud' }), grid = el('div', { class: 'grid' }), more = el('div', { class: 'morebox' });
  const root = el('div', { class: 'view pg-notes' }, [search, sortBox, galBox, head('Tags'), cloud, grid, more]);
  let last = null;
  search.addEventListener('input', () => { st.q = search.value.trim().toLowerCase(); st.more = 24; if (last) paintGrid(last); });
  const SORTS = { recent: (a, b) => b.mtime - a.mtime, links: (a, b) => b.degree - a.degree, words: (a, b) => b.words - a.words, az: (a, b) => a.title.localeCompare(b.title) };
  function paintGrid(ctx) {
    const { g, now } = ctx;
    let list = g.nodes.filter((n) => n.kind !== 'me');
    if (st.cluster) list = list.filter((n) => g.clusters[n.cluster].key === st.cluster);
    if (ctx.tag) list = list.filter((n) => n.tags.includes(ctx.tag));
    if (st.q) list = list.filter((n) => n.title.toLowerCase().includes(st.q) || n.tags.some((t) => t.includes(st.q)) || (n.snippet || '').toLowerCase().includes(st.q));
    list.sort(SORTS[st.sort]);
    const none = !g.nodes.some((n) => n.kind !== 'me');
    grid.replaceChildren(...(list.length ? list.slice(0, st.more).map((n) => noteCard(n, g, ctx, h, now))
      : [none ? empty('No notes in your vault yet. Write one in Obsidian, or save one right here with Teach.', acts(h, ctx)) : empty('No note matches. Clear the filter or pick another galaxy.')]));
    more.replaceChildren(...(list.length > st.more ? [el('button', { class: 'cta', type: 'button', text: `Show more (${list.length - st.more})`, onclick: () => { st.more += 24; paintGrid(ctx); } })] : []));
  }
  return {
    root,
    render(ctx) {
      last = ctx;
      const { g } = ctx;
      sortBox.replaceChildren(seg([['recent', 'Recent'], ['links', 'Most linked'], ['words', 'Longest'], ['az', 'A-Z']], st.sort, (k) => { st.sort = k; this.render(ctx); }, 'Sort notes'));
      galBox.replaceChildren(...[{ key: null, label: 'All', colour: '#fff' }, ...g.clusters.filter((c) => c.count && c.key !== 'me')].map((c) => el('button', {
        class: 'chip', type: 'button', 'aria-pressed': String(c.key === st.cluster), style: { '--c': c.colour }, 'data-key': c.key || '',
        onclick: () => { st.cluster = c.key === st.cluster ? null : c.key; st.more = 24; this.render(ctx); } }, [dot(c.colour), el('span', { text: c.label })])));
      const tags = tagCloud(g, 30);
      cloud.replaceChildren(...(tags.length ? tags.map((t) => el('button', {
        class: 'tagc', type: 'button', 'aria-pressed': String(ctx.tag === t.tag), style: { '--c': t.colour, 'font-size': (12 + t.weight * 8).toFixed(1) + 'px' },
        title: `${t.count} notes`, onclick: () => h.tag(ctx.tag === t.tag ? null : t.tag) }, [document.createTextNode('#' + t.tag)])) : [el('span', { class: 'hint', text: 'Tags you use in notes show up here.' })]));
      paintGrid(ctx);
    },
  };
}

function daysView(h) {
  const root = el('div', { class: 'view pg-days' });
  return {
    root,
    render(ctx) {
      const { g, now } = ctx, days = timeline(g, now, 28);
      if (!days.length) { root.replaceChildren(empty('No days yet. Daily notes, edits and lessons from the last four weeks show up here as a timeline. Write a daily note in Obsidian, or tell Jarvis something today.', acts(h, ctx))); return; }
      root.replaceChildren(el('ol', { class: 'tline' }, days.map((d) => {
        const total = d.daily.length + d.edits.length + d.editsMore + d.learned.length;
        return el('li', { class: 'tday', 'data-day': d.key }, [
          el('i', { class: 'tdot' }),
          el('h3', {}, [el('span', { text: dayLabel(d.key, now) }), el('small', { text: `${total} thing${total === 1 ? '' : 's'}` })]),
          ...d.daily.map((i) => el('button', { class: 'daily', type: 'button', onclick: () => h.fly(g.nodes[i].id) }, [el('b', { text: 'Daily note' }), el('span', { text: g.nodes[i].title }), el('small', { text: previewText(g.nodes[i], 90) })])),
          ...d.learned.map((l) => el('button', { class: 'row learn', type: 'button', onclick: () => (l.i >= 0 ? h.fly(g.nodes[l.i].id) : h.replay([l])) }, [dot('var(--cyan)'), el('span', { class: 'r-t', text: l.text }), el('small', { text: 'learned' })])),
          d.edits.length ? el('div', { class: 'pills' }, [...d.edits.map((i) => el('button', { class: 'pillbtn', type: 'button', style: { '--c': g.clusters[g.nodes[i].cluster].colour }, onclick: () => h.fly(g.nodes[i].id) }, [dot(g.clusters[g.nodes[i].cluster].colour), document.createTextNode(g.nodes[i].title)])),
            d.editsMore ? el('span', { class: 'hint', text: `+${d.editsMore} more edited` }) : null]) : null]);
      })));
    },
  };
}

function learnedView(h) {
  const st = { f: 'all' };
  const root = el('div', { class: 'view pg-learned' });
  return {
    root,
    render(ctx) {
      const { g, now } = ctx, all = learnedFeed(g), week = all.filter((x) => now - x.t < 7 * 864e5).length;
      const list = all.filter((x) => st.f === 'all' || (st.f === 'lessons') === (x.src === 'lesson'));
      const groups = new Map();
      for (const x of list.slice(0, 60)) { const k = dayKey(x.t); if (!groups.has(k)) groups.set(k, []); groups.get(k).push(x); }
      root.replaceChildren(
        el('div', { class: 'tiles three' }, [tile('all', 'Learned', big(all.length), 'all time', 'var(--cyan)'), tile('week', 'This week', String(week)), tile('mem', 'Memories', String(all.filter((x) => x.src === 'memory').length))]),
        el('div', { class: 'toolbar' }, [seg([['all', 'All'], ['lessons', 'Lessons'], ['memories', 'Memories']], st.f, (k) => { st.f = k; this.render(ctx); }, 'Filter the feed'),
          el('button', { class: 'cta small', type: 'button', text: 'Replay', onclick: () => (list.length ? h.replay(list.slice(0, 12).reverse()) : h.toast('Nothing to replay yet')) })]),
        ...(list.length ? [...groups].map(([k, items]) => el('section', { class: 'feedday' }, [
          el('h4', { text: dayLabel(dayKey(items[0].t), now) }),
          ...items.map((x) => el('div', { class: 'feeditem ' + x.src }, [
            el('button', { class: 'row learn', type: 'button', onclick: () => (x.i >= 0 ? h.fly(g.nodes[x.i].id) : h.replay([x])) }, [dot(x.src === 'lesson' ? 'var(--cyan)' : 'var(--gold)'),
              el('span', { class: 'r-t', text: x.text }), el('small', { text: new Date(x.t).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' }) })]),
            el('button', { class: 'mini play', type: 'button', 'aria-label': 'Replay this', text: '▶', onclick: () => h.replay([x]) })]))]))
          : [empty('Nothing learned yet. Tell Jarvis something (or tap Teach) and it lands here as a feed you can replay.', acts(h, ctx))]));
    },
  };
}

/** The local map of one note: the note in the middle, what it links to on the right, what links to it on the left. */
function egoMap(g, i, h) {
  const e = ego(g, i, 8), W = 340, H = 250, cx = W / 2, cy = H / 2;
  if (!e) return null;
  const spot = new Map(), outs = e.ring.filter((r) => r.dir !== 'back'), backs = e.ring.filter((r) => r.dir === 'back');
  const place = (list, side) => list.forEach((r, k) => {
    const a = (Math.PI * (k + 1)) / (list.length + 1) - Math.PI / 2;
    spot.set(r.n.i, [cx + side * (100 + (k % 2) * 18) * Math.cos(a), cy + Math.sin(a) * 100]);
  });
  place(outs, 1); place(backs, -1);
  const kids = [svg('defs', {}, [svg('filter', { id: 'eg-glow', x: '-50%', y: '-50%', width: '200%', height: '200%' }, [svg('feGaussianBlur', { stdDeviation: '3' })])])];
  for (const [a, b] of e.links) { const p = spot.get(a), q = spot.get(b); if (p && q) kids.push(svg('line', { x1: p[0], y1: p[1], x2: q[0], y2: q[1], class: 'eg-x' })); }
  for (const r of e.ring) { const p = spot.get(r.n.i); kids.push(svg('line', { x1: cx, y1: cy, x2: p[0], y2: p[1], class: 'eg-l ' + r.dir })); }
  const label = (t) => (t.length > 18 ? t.slice(0, 17) + '…' : t);
  for (const r of e.ring) {
    const p = spot.get(r.n.i), c = g.clusters[r.n.cluster].colour;
    kids.push(svg('g', { class: 'eg-n', tabindex: 0, role: 'button', 'aria-label': 'Open ' + r.n.title, onclick: () => h.fly(r.n.id), onkeydown: (ev) => { if (ev.key === 'Enter') h.fly(r.n.id); } }, [
      svg('circle', { cx: p[0], cy: p[1], r: 11, fill: c, opacity: 0.4, filter: 'url(#eg-glow)' }), svg('circle', { cx: p[0], cy: p[1], r: 6.5, fill: c }),
      svg('text', { x: p[0], y: p[1] + 19, 'text-anchor': 'middle', text: label(r.n.title) })]));
  }
  const cc = g.clusters[e.centre.cluster].colour;
  kids.push(svg('circle', { cx, cy, r: 22, fill: cc, opacity: 0.5, filter: 'url(#eg-glow)' }), svg('circle', { cx, cy, r: 12, fill: cc, stroke: '#fff', 'stroke-width': 1.5 }),
    svg('text', { x: cx, y: cy - 20, 'text-anchor': 'middle', class: 'eg-c', text: label(e.centre.title) }));
  kids.push(svg('text', { x: 8, y: 14, class: 'eg-k', text: '← linked from' }), svg('text', { x: W - 8, y: 14, class: 'eg-k', 'text-anchor': 'end', text: 'links to →' }));
  return el('div', { class: 'card2' }, [head('Local map', el('small', { text: e.more ? `+${e.more} more` : `${e.ring.length} neighbours` })),
    svg('svg', { viewBox: `0 0 ${W} ${H}`, class: 'egomap', role: 'group', 'aria-label': 'Links and backlinks of ' + e.centre.title }, kids)]);
}

function graphView(h) {
  const root = el('div', { class: 'view pg-graph' });
  return {
    root,
    render(ctx) {
      const { g, now } = ctx, lonely = orphans(g), top = hubs(g, 6);
      const centre = ctx.focus >= 0 ? ctx.focus : top[0] ? top[0].i : g.nodes.length ? 0 : -1;
      const slider = el('input', { type: 'range', min: 0, max: 8, step: 1, value: String(ctx.gmin), 'aria-label': 'Minimum links', class: 'slider' });
      const lab = el('b', { text: ctx.gmin ? `at least ${ctx.gmin} link${ctx.gmin === 1 ? '' : 's'}` : 'any number of links' });
      slider.addEventListener('input', () => { lab.textContent = +slider.value ? `at least ${slider.value} link${+slider.value === 1 ? '' : 's'}` : 'any number of links'; });
      slider.addEventListener('change', () => h.gmode(ctx.gmode, +slider.value));
      root.replaceChildren(
        el('div', { class: 'card2' }, [head('Filter the brain', el('small', { text: ctx.gmode === 'all' && !ctx.gmin ? 'showing everything' : 'dimming the rest' })),
          seg(MODES, ctx.gmode, (k) => h.gmode(k, ctx.gmin), 'Which notes to light up'),
          el('label', { class: 'sl' }, [el('span', { text: 'Links' }), slider, lab])]),
        centre >= 0 && g.edges.length ? egoMap(g, centre, h) : el('div', { class: 'card2' }, [head('Local map'), empty('The map needs links. In Obsidian, write [[double brackets]] around another note\'s name and the two connect here.', acts(h, ctx))]),
        el('div', { class: 'card2' }, [head('Hubs', el('small', { text: 'most linked' })), top.length ? el('div', { class: 'list' }, top.map((n) => row(n, g, h, `${n.degree} links`, now))) : empty('No hubs yet. A hub is a note with 3 or more links.')]),
        el('div', { class: 'card2' }, [head('Orphans', el('small', { text: `${lonely.length} without links` })),
          lonely.length ? el('div', { class: 'list' }, lonely.slice(0, 8).map((n) => row(n, g, h, 'link me', now))) : empty('No orphans. Every note is connected.')]),
        el('div', { class: 'card2' }, [head('Galaxies', el('small', { text: 'tap to focus' })), el('div', { class: 'gal' }, g.clusters.filter((c) => c.count && c.key !== 'me').slice().sort((a, b) => b.count - a.count).map((c) => el('button', {
          class: 'galrow', type: 'button', 'aria-pressed': String(ctx.filter === c.key), style: { '--c': c.colour, '--w': String(c.count / Math.max(1, ...g.clusters.map((k) => k.count))) }, onclick: () => h.cluster(ctx.filter === c.key ? null : c.key) },
        [dot(c.colour), el('span', { text: c.label }), el('i'), el('small', { text: fmt.format(c.count) })])))]));
    },
  };
}

function reviewView(h) {
  const S = { phase: 'start', qs: [], k: 0, score: 0, picked: -1, retry: false };
  const root = el('div', { class: 'view pg-review' });
  let last = null;
  const redo = () => { if (last) paint(last); };
  function start(ctx) {
    const deck = deckOf(ctx.g, ctx.now);
    S.qs = pickSession(deck, ctx.review, ctx.now, 5); S.k = 0; S.score = 0; S.picked = -1; S.phase = S.qs.length ? 'ask' : 'start';
    h.play('portal');
    redo();
  }
  function answer(ctx, q, i) {
    if (S.picked >= 0) return;
    S.picked = i;
    const ok = i === q.answer;
    if (ok) S.score++;
    h.review(grade(ctx.review, q.id, ok, ctx.now));
    h.play(ok ? 'tick' : 'tap');
    redo();
    requestAnimationFrame(() => { const w = root.querySelector('.why'); if (w) w.scrollIntoView({ block: 'nearest' }); });      // the answer and Next stay in sight
  }
  function next(ctx) {
    S.k++; S.picked = -1;
    if (S.k >= S.qs.length) { S.phase = 'done'; h.play(S.score >= Math.ceil(S.qs.length * 0.8) ? 'rankup' : 'tick'); }
    redo();
  }
  function paint(ctx) {
    const b = boxes(ctx.review), days = (ctx.review && ctx.review.days) || [];
    if (S.phase === 'ask' && S.qs[S.k]) {
      const q = S.qs[S.k], done = S.picked >= 0;
      root.replaceChildren(
        el('div', { class: 'qprog', 'aria-label': `Question ${S.k + 1} of ${S.qs.length}` }, S.qs.map((_, k) => el('i', { class: k < S.k ? 'done' : k === S.k ? 'now' : '' }))),
        el('div', { class: 'card2 q', 'data-kind': q.kind }, [el('small', { class: 'qk', text: { gap: 'Fill the gap', galaxy: 'Galaxy', link: 'Links', tag: 'Tags', hub: 'Hubs', starter: 'Mind basics' }[q.kind] || 'Question' }), el('h2', { id: 'q-prompt', text: q.prompt })]),
        el('div', { class: 'choices', role: 'group', 'aria-labelledby': 'q-prompt' }, q.choices.map((c, i) => el('button', {
          class: 'choice' + (done ? (i === q.answer ? ' right' : i === S.picked ? ' wrong' : ' off') : ''), type: 'button', 'data-i': String(i), disabled: done ? '' : null,
          onclick: () => answer(ctx, q, i) }, [el('span', { text: 'ABCD'[i] }), document.createTextNode(c)]))),
        done ? el('div', { class: 'card2 why', role: 'status' }, [el('b', { text: S.picked === q.answer ? 'Right.' : 'Not quite.' }), el('p', { text: q.why || 'Keep going.' }),
          el('div', { class: 'toolbar' }, [q.note && ctx.g.index.has(q.note) ? el('button', { class: 'cta small ghosty', type: 'button', text: 'Open the note', onclick: () => h.fly(q.note) }) : null,
            el('button', { class: 'cta small', type: 'button', id: 'rv-next', text: S.k + 1 >= S.qs.length ? 'Finish' : 'Next', onclick: () => next(ctx) })])]) : null);
      return;
    }
    if (S.phase === 'done') {
      root.replaceChildren(el('div', { class: 'card2 result' }, [el('h2', { text: `${S.score} of ${S.qs.length}` }), el('p', { text: S.score === S.qs.length ? 'Perfect. Your brain is sharp.' : S.score >= S.qs.length / 2 ? 'Nice. The tricky ones come back sooner.' : 'Good practice. The ones you missed come back soon.' }),
        el('p', { class: 'hint', text: `Review streak: ${days.length} day${days.length === 1 ? '' : 's'} so far` }),
        el('div', { class: 'toolbar' }, [el('button', { class: 'cta', type: 'button', text: 'Go again', onclick: () => start(ctx) }), el('button', { class: 'cta ghosty', type: 'button', text: 'Back to Home', onclick: () => h.open('home') })])]));
      return;
    }
    const due = dueCount(deckOf(ctx.g, ctx.now), ctx.review, ctx.now), total = Object.keys((ctx.review && ctx.review.cards) || {}).length;
    root.replaceChildren(
      el('div', { class: 'card2 rstart' }, [el('h2', { text: due ? `${due} to practise` : 'All caught up' }), el('p', { text: 'Five quick questions made from your own notes. Right answers come back later, missed ones sooner.' }),
        el('button', { class: 'cta', type: 'button', id: 'rv-start', text: 'Start review', onclick: () => start(ctx) })]),
      el('div', { class: 'card2' }, [head('Your boxes', el('small', { text: `${total} cards learned` })),
        total ? barChart(b, { labels: ['New', '1 day', '3 days', '1 week', '2 weeks', 'Mastered'], label: 'Cards in each box' }) : el('p', { class: 'hint', text: 'Answer a question and your first card lands here. Each right answer moves it one box up, a wrong one sends it back.' }),
        el('div', { class: 'axis' }, [el('span', { text: 'new → mastered' }), el('b', { text: `${days.length} day${days.length === 1 ? '' : 's'} reviewed` })])]));
  }
  return {
    root,
    get question() { return S.phase === 'ask' ? S.qs[S.k] || null : null; },
    render(ctx) { last = ctx; paint(ctx); },
  };
}

function teachView(h) {
  const st = { kind: 'fact', msg: '', ok: false };
  const text = el('textarea', { id: 'teach-text', class: 'field big', rows: 3, maxlength: 4000, spellcheck: 'true', 'aria-label': 'What should Jarvis know?', placeholder: 'e.g. My best trades come before 11:00' });
  const title = el('input', { id: 'teach-title', class: 'field', type: 'text', maxlength: 80, placeholder: 'Note title (optional)', 'aria-label': 'Note title' });
  const warn = el('p', { class: 'warn', role: 'status' }), msg = el('p', { class: 'msg', role: 'status' }), recent = el('div', { class: 'list' }), seg0 = el('div'), titleBox = el('div', { class: 'titlebox' }, [title]);
  const save = el('button', { class: 'cta', type: 'button', id: 'teach-save', text: 'Save to Jarvis' });
  const root = el('div', { class: 'view pg-teach' }, [
    el('div', { class: 'card2' }, [head('Teach Jarvis'), el('p', { class: 'sub', text: 'Saved on this phone, in the same place Jarvis reads. She knows it the next time she opens.' }), seg0, text, titleBox, warn, el('div', { class: 'toolbar' }, [save, el('a', { class: 'cta ghosty', href: '../jarvis/', target: '_top', text: 'Open Jarvis' })]), msg]),
    el('div', { class: 'card2' }, [head('Taught lately'), recent])]);
  let last = null;
  text.addEventListener('input', () => { warn.textContent = screen(text.value); });
  save.addEventListener('click', () => {
    const r = h.teach({ kind: st.kind, text: text.value, title: title.value });
    st.ok = !!r.ok; msg.textContent = r.ok ? (st.kind === 'note' ? `Saved the note “${r.text}”. Jarvis can find it now.` : 'Saved. Jarvis will remember that.') : r.error;
    msg.className = 'msg ' + (r.ok ? 'ok' : 'bad');
    if (r.ok) { text.value = ''; title.value = ''; warn.textContent = ''; }
  });
  return {
    root,
    render(ctx) {
      last = ctx;
      seg0.replaceChildren(seg([['fact', 'Remember'], ['note', 'Note']], st.kind, (k) => { st.kind = k; titleBox.hidden = k !== 'note'; text.rows = k === 'note' ? 6 : 3; text.placeholder = k === 'note' ? 'Write the note. Link others with [[double brackets]].' : 'e.g. My best trades come before 11:00'; this.render(last); }, 'What to save'));
      titleBox.hidden = st.kind !== 'note';
      const mine = ((ctx.live && ctx.live.items) || []).filter((x) => x.kind !== 'lesson').slice(-5).reverse();
      recent.replaceChildren(...(mine.length ? mine.map((x) => el('div', { class: 'row static' }, [dot(x.kind === 'note' ? 'var(--gold)' : 'var(--cyan)'), el('span', { class: 'r-t', text: x.text }), el('small', { text: ago(x.t, ctx.now) })]))
        : [el('p', { class: 'hint', text: 'Nothing yet. What you teach lands here and glows in the 3D brain.' })]));
    },
  };
}

function statsView(h) {
  const root = el('div', { class: 'view pg-stats' });
  return {
    root,
    render(ctx) {
      const { g, now } = ctx, s = brainStats(g, now), lv = s.level, galaxies = s.galaxies.filter((c) => c.key !== 'me');
      const top = Math.max(1, ...galaxies.map((c) => c.count));
      const rec = (k, label, n, extra) => (n ? el('button', { class: 'row', type: 'button', onclick: () => h.fly(n.id) }, [el('span', { class: 'r-k', text: label }), el('span', { class: 'r-t', text: n.title }), el('small', { text: extra })]) : null);
      root.replaceChildren(
        el('div', { class: 'hero' }, [el('div', {}, [el('p', { class: 'hello', text: 'Brain level' }), el('h2', { text: `${lv.name}, level ${lv.level}` }), el('p', { class: 'sub', text: `${fmt.format(lv.xp)} points. Notes, links and lessons all add up.` })]), ring(lv.progress, `${Math.round(lv.progress * 100)}%`, 'to next')]),
        el('div', { class: 'tiles' }, [tile('notes', 'Notes', big(s.notes)), tile('links', 'Links', big(s.links)), tile('words', 'Words', big(s.words), `${s.avgWords} per note`),
          tile('active', 'Active days', String(s.activeDays)), tile('streak', 'Best streak', `${s.streak.best}d`, `now ${s.streak.current}d`, 'var(--gold)'), tile('orph', 'Orphans', `${s.orphanPct}%`, `${s.orphans} notes`)]),
        el('div', { class: 'card2' }, [head('Edits per week', el('small', { text: 'last 8 weeks' })), barChart(s.weekly.edits, { label: 'Notes edited per week' })]),
        el('div', { class: 'card2' }, [head('Learned per week', el('small', { text: 'last 8 weeks' })), barChart(s.weekly.learned, { colour: 'var(--gold)', label: 'Lessons per week' })]),
        el('div', { class: 'card2' }, [head('Galaxies by size'), el('div', { class: 'gal' }, galaxies.map((c) => el('button', { class: 'galrow', type: 'button', style: { '--c': c.colour, '--w': String(c.count / top) }, onclick: () => h.cluster(c.key) },
          [dot(c.colour), el('span', { text: c.label }), el('i'), el('small', { text: `${fmt.format(c.count)} · ${Math.round((c.count / Math.max(1, s.notes)) * 100)}%` })])))]),
        el('div', { class: 'card2' }, [head('Records'), el('div', { class: 'list' }, [rec('hub', 'Biggest hub', s.hub, s.hub ? `${s.hub.degree} links` : ''), rec('long', 'Longest note', s.longest, s.longest ? `${fmt.format(s.longest.words)} words` : ''),
          rec('new', 'Newest', s.newest, s.newest ? ago(s.newest.mtime, now) : ''), rec('old', 'Oldest', s.oldest, s.oldest ? ago(s.oldest.mtime, now) : ''),
          s.bestDay ? el('div', { class: 'row static' }, [el('span', { class: 'r-k', text: 'Best day' }), el('span', { class: 'r-t', text: dayLabel(s.bestDay.key, now) }), el('small', { text: `${s.bestDay.n} lessons` })]) : null].filter(Boolean))]));
    },
  };
}

function lookView(h) {
  const root = el('div', { class: 'view pg-look' });
  const vault = el('input', { class: 'field', type: 'text', maxlength: 60, placeholder: 'Your Obsidian vault name', 'aria-label': 'Obsidian vault name', spellcheck: 'false', autocapitalize: 'off', id: 'vault-name' });
  vault.addEventListener('change', () => { h.pref('vault', vault.value.trim()); h.toast(vault.value.trim() ? 'Obsidian links will open in ' + vault.value.trim() : 'Obsidian links off'); });
  const sw = (key, label, sub, on, disabled) => el('button', { class: 'switch', type: 'button', role: 'switch', 'aria-checked': String(!!on), 'data-k': key, disabled: disabled ? '' : null,
    onclick: () => h.pref(key, !on) }, [el('span', {}, [el('b', { text: label }), el('small', { text: sub })]), el('i')]);
  return {
    root,
    render(ctx) {
      const p = ctx.prefs;
      if (document.activeElement !== vault) vault.value = p.vault || '';
      root.replaceChildren(
        el('div', { class: 'card2' }, [head('Skin'), el('div', { class: 'skins' }, SKINS.map((s) => el('button', { class: 'skin', type: 'button', 'aria-pressed': String(p.skin === s.id), 'data-skin': s.id,
          style: { '--a': s.accent || 'var(--cyan)', '--s1': s.sky[0], '--s2': s.sky[1], '--s3': s.sky[2] }, onclick: () => h.skin(s.id) }, [el('i'), el('span', { text: s.name })])))]),
        el('div', { class: 'card2' }, [head('Atmosphere'), sw('sky', 'Nebula sky', 'soft clouds behind the brain', p.sky), sw('dust', 'Ambient particles', 'drifting light motes', p.dust),
          sw('sound', 'Sounds', ctx.soundOk ? 'taps, sparks and rewards' : 'needs the OLYMPUS kit', p.sound, !ctx.soundOk)]),
        el('div', { class: 'card2' }, [head('Obsidian'), el('p', { class: 'sub', text: 'Type your vault name once. Every note card then gets an Open in Obsidian button.' }), vault]));
    },
  };
}

// ------------------------------------------------------------------ the shell
export function createPanels(h) {
  const root = $('panel'), body = $('p-body'), title = $('p-title'), sub = $('p-sub');
  const hh = { ...h, open: (name) => open(name) };
  const views = {
    home: homeView(hh), notes: notesView(hh), days: daysView(hh), learned: learnedView(hh), graph: graphView(hh),
    review: reviewView(hh), teach: teachView(hh), stats: statsView(hh), look: lookView(hh),
  };
  let current = null, ctx = null, stale = new Set(PANELS);

  function paintDock() {
    for (const b of document.querySelectorAll('#dock button[data-panel]')) b.setAttribute('aria-pressed', String(b.dataset.panel === current));
  }
  function render() {
    if (!current || !ctx) return;
    const v = views[current];
    v.render(ctx);
    stale.delete(current);
  }
  function open(name, { peek = false } = {}) {
    if (!views[name]) return;
    current = name;
    root.hidden = false;
    root.dataset.view = name;
    root.classList.toggle('peek', peek);
    title.textContent = TITLES[name];
    sub.textContent = ctx && ctx.mode === 'demo' ? 'DEMO' : '';
    body.replaceChildren(views[name].root);
    body.scrollTop = 0;
    document.body.classList.add('panel-open');
    render();
    paintDock();
  }
  function close() {
    current = null;
    root.hidden = true;
    document.body.classList.remove('panel-open');
    paintDock();
  }
  $('p-close').addEventListener('click', () => close());
  for (const b of document.querySelectorAll('#dock button[data-panel]')) b.addEventListener('click', () => { if (current === b.dataset.panel) close(); else { h.play('tap'); h.beforeOpen && h.beforeOpen(); open(b.dataset.panel); } });
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && current && !(document.activeElement && /INPUT|TEXTAREA/.test(document.activeElement.tagName))) close(); });

  return {
    open, close,
    get current() { return current; },
    get review() { return views.review.question; },
    update(c) {
      ctx = c;
      stale = new Set(PANELS);
      if (current) { sub.textContent = c.mode === 'demo' ? 'DEMO' : ''; render(); }
      const due = c.g ? dueCount(deckOf(c.g, c.now), c.review, c.now) : 0;
      const badge = document.querySelector('#dock [data-panel="review"] .badge');
      if (badge) { badge.textContent = due > 9 ? '9+' : String(due); badge.hidden = !due; }
    },
  };
}
