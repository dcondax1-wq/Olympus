// OLYMPUS Mind: the demo brain, shown until the owner connects his vault. Fake notes only (trading, goals, gym, Kalshi,
// business, daily notes, Jarvis memories), built deterministically, with the same interface as jarvis/obsidian.js:
//   createDemo({size}) -> {graphSnapshot(), onIndexChange(cb) -> unsubscribe, addPack(pack)}      size: pad to that many notes (perf checks)
//   addPack(pack): the starter vault (starter/starter_pack.js, tools/obsidian_pack.py: ~225 real notes with [[links]] and frontmatter tags) joins the
//   fake brain, linked into it, so the demo is as rich and realistic as the owner's vault will be (data.js adds it when the demo is shown).
// While someone watches, it "learns" a new fact every ~20 s (and now and then files a new inbox note), so the page shows
// what the live brain does. Nothing here is real data.

const H = 3600e3, D = 24 * H, LEARN_EVERY_MS = 20000;

const TOPICS = {
  trading: ['Trading', ['trading'], [
    'LIT strategy', 'NQ futures', 'MFFU Builder 50K eval', 'Sweep, inducement, displacement', 'IFVG entries', '1m CISD trigger',
    'Stop beyond the sweep extreme', 'Size follows the stop', 'VIX day-move target', 'Bank at 8R', 'Break-even at 1R',
    'NY open playbook', 'London session', 'Asia range', 'Trade journal', 'Weekly review', 'Losing streak rules',
    'No revenge trades', 'Eval pass plan', 'NinjaTrader setup', 'Backtest 2021-25', 'Liquidity levels', 'Funded payout plan',
    'Market structure', 'Killzones', 'Prop firm rules', 'Risk of ruin', 'Best setups 2026'],
    ['eval', 'risk', 'setup', 'journal']],
  goals: ['Goals', ['goals'], [
    '2027 goals', 'Q1 plan', 'Funded by spring', 'Morning routine', 'Read 20 books', 'Habit tracker', 'Vision board',
    'Deep work blocks', 'Discipline', 'Save $10k', 'Move out plan', 'Year review 2026', 'Weekly goals', 'Who I want to be'],
    ['plan', 'habits']],
  health: ['Health', ['gym'], [
    'Push day', 'Pull day', 'Leg day', 'Sleep 8 hours', 'Protein 180 g', 'Creatine', 'Zone 2 cardio', 'Bench PR', 'Meal prep',
    'Mobility', 'Cut or bulk', 'Supplements', 'Recovery', 'Steps 10k'],
    ['training', 'food']],
  kalshi: ['Kalshi', ['kalshi'], [
    'Kalshi bot', 'BTC 15-minute markets', 'Fade the favourite', 'Kalshi P&L', 'Market making ideas', 'Event contracts',
    'Kalshi risk caps', 'Edge log', 'Strategy B: momentum', 'Settlement rules'],
    ['bot', 'markets']],
  business: ['Business', ['business'], [
    'OLYMPUS', 'Jarvis roadmap', 'Side hustle ideas', 'Content plan', 'Clients', 'Pricing', 'Brand', 'Cold outreach',
    'Automation agency', 'Tools stack', 'Revenue goals', 'Pitch deck'],
    ['ideas', 'olympus']],
};

const MEMORIES = [
  ['Prefers short, result-first answers', null], ['Trades the NY open from 9:30', 'Trading/NY open playbook.md'],
  ['Gym at 6 AM before the session', 'Health/Push day.md'], ['Goal: pass the eval within 2 weeks', 'Trading/Eval pass plan.md'],
  ['Likes the dark gold look', 'Business/Brand.md'], ['Kalshi bot runs 24/7 on its own server', 'Kalshi/Kalshi bot.md'],
  ['Wants to be funded by spring', 'Goals/Funded by spring.md'], ['Never arm live trading for him', 'Trading/Prop firm rules.md'],
];

const LEARNING = [
  ['You move leg day to Thursdays now', 'Health/Leg day.md'],
  ['Your best LIT trades come before 11:00', 'Trading/LIT strategy.md'],
  ['Kalshi BTC markets pay most on fast moves', 'Kalshi/BTC 15-minute markets.md'],
  ['You want 4 deep work blocks a week', 'Goals/Deep work blocks.md'],
  ['OLYMPUS needs a pricing page next', 'Business/Pricing.md'],
  ['A wide stop means fewer micros, not skipping', 'Trading/Size follows the stop.md'],
  ['You sleep better without screens after 23:00', 'Health/Sleep 8 hours.md'],
  ['Weekly review is on Sundays at 18:00', 'Trading/Weekly review.md'],
  ['You read 2 chapters a day this month', 'Goals/Read 20 books.md'],
  ['Cold outreach works best on Tuesdays', 'Business/Cold outreach.md'],
];

// a few notes carry a markdown preview (the card renders headings, lists, tasks, [[links]] and #tags)
const PREVIEWS = {
  'Trading/LIT strategy.md': '## The setup\n- Sweep of a LIT level, then **inducement**\n- Displacement, then the 5m CISD\n- Entry on the [[1m CISD trigger]]\n\n## Risk\n- Stop: [[Stop beyond the sweep extreme]]\n- [[Size follows the stop]], ==bank at 8R==\n\n#trading #lit',
  'Goals/2027 goals.md': '## This year\n- [x] Start the Builder 50K eval\n- [ ] Pass it inside two weeks\n- [ ] [[Funded by spring]]\n> One clear target, no greed.',
  'Health/Push day.md': '## Push\n1. Bench 5 x 5\n2. Overhead press 4 x 8\n3. Dips to failure\n\nSee [[Protein 180 g]] and [[Sleep 8 hours]].',
  'Kalshi/Kalshi bot.md': '## Kalshi bot\nRuns 24/7 on its own server.\n- Strategy: [[Fade the favourite]]\n- Caps: [[Kalshi risk caps]]\n`paper first, then real money`',
  'Business/OLYMPUS.md': '# OLYMPUS\nThe system that runs my life: **Jarvis** plus nine 3D apps.\n- [[Jarvis roadmap]]\n- [[Pricing]]\n- [ ] Landing page',
};

const IDEAS = ['Idea: Jarvis voice journal', 'Idea: Kalshi weather markets', 'Idea: gym PR wall', 'Idea: funded-trader content',
  'Idea: auto weekly review', 'Idea: OLYMPUS landing page'];

function rng(seed) {                               // mulberry32: the same demo brain every time
  return () => {
    seed |= 0; seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function build(size, now) {
  const r = rng(1729), pick = (a) => a[Math.floor(r() * a.length)];
  const notes = [], byTopic = {};
  const add = (n) => { notes.push(n); return n; };
  const me = add({ id: 'Me.md', title: 'Me', path: 'Me.md', tags: ['me'], links: [], mtime: now - 3 * H, words: 900, kind: 'me',
    snippet: 'Who I am, what I am building and why. Trader, builder, gym every morning. OLYMPUS is the system that runs my life.' });
  for (const [key, [folder, tags, titles, sub]] of Object.entries(TOPICS)) {
    byTopic[key] = titles.map((title, k) => add({
      id: `${folder}/${title}.md`, title, path: `${folder}/${title}.md`, tags: k % 3 ? [...tags, pick(sub)] : tags.slice(),
      links: [], mtime: now - Math.floor(r() * r() * 420) * D - Math.floor(r() * D), words: Math.floor(80 + r() * r() * 2400),
      kind: 'note', snippet: k === 0 ? `${title}: the hub for everything ${folder.toLowerCase()}. Rules, numbers and what I learned.` : '',
      ...(PREVIEWS[`${folder}/${title}.md`] ? { preview: PREVIEWS[`${folder}/${title}.md`] } : {}),
    }));
  }
  // links: each topic is a hub-and-spoke web with some cross-links, the way a real vault grows
  for (const list of Object.values(byTopic)) {
    list.forEach((n, k) => {
      if (k) n.links.push(list[0].id);
      const extra = 1 + Math.floor(r() * 3);
      for (let x = 0; x < extra; x++) { const m = pick(list); if (m !== n) n.links.push(m.id); }
    });
    me.links.push(list[0].id);
  }
  const all = Object.values(byTopic).flat();
  for (let x = 0; x < 26; x++) { const a = pick(all), b = pick(all); if (a !== b) a.links.push(b.id); }
  // daily notes: the last 21 days, each mentions what that day touched
  for (let d = 0; d < 21; d++) {
    const day = new Date(now - d * D), iso = day.toISOString().slice(0, 10);
    add({ id: `Daily/${iso}.md`, title: iso, path: `Daily/${iso}.md`, tags: ['daily'], kind: 'daily', words: Math.floor(60 + r() * 500),
      mtime: now - d * D - Math.floor(r() * 6 * H), links: [pick(byTopic.trading).id, pick(all).id, pick(all).id], snippet: '' });
  }
  MEMORIES.forEach(([text, note], k) => add({ id: `Jarvis/Memory/${k + 1}.md`, title: text, path: `Jarvis/Memory/${k + 1}.md`,
    tags: ['jarvis', 'memory'], kind: 'memory', words: 20 + k * 3, mtime: now - (k * 2 + 1) * D, links: note ? [note, me.id] : [me.id], snippet: text }));
  // loose ends nobody has linked yet: the Graph page finds them as orphans
  [['Buy a standing desk', 6], ['Try cold showers', 20], ['Book the dentist', 31]].forEach(([title, hrs]) => add({ id: `Inbox/${title}.md`, title, path: `Inbox/${title}.md`, tags: ['inbox'],
    kind: 'inbox', words: 9, mtime: now - hrs * H, links: [], snippet: '' }));
  add({ id: 'Inbox/Call the accountant.md', title: 'Call the accountant', path: 'Inbox/Call the accountant.md', tags: ['inbox'],
    kind: 'inbox', words: 12, mtime: now - 5 * H, links: [byTopic.business[0].id], snippet: '' });
  // padding for big demos (?demo=2000, the performance check): more notes in each topic, same shape
  const keys = Object.keys(byTopic);
  for (let x = 0; notes.length < size; x++) {
    const key = keys[x % keys.length], [folder, tags] = TOPICS[key], hub = byTopic[key];
    const n = add({ id: `${folder}/Log ${x}.md`, title: `${folder} log ${x}`, path: `${folder}/Log ${x}.md`, tags: tags.slice(), kind: 'note',
      words: Math.floor(40 + r() * 600), mtime: now - Math.floor(r() * 900) * D, links: [pick(hub).id], snippet: '' });
    if (r() < 0.5) n.links.push(pick(notes).id);
    hub.push(n);
  }
  const learned = LEARNING.slice(0, 5).map(([text, note], k) => ({ t: now - (k ? (k * 30 + 9) * H : 0.4 * H), text, note }));   // the first one landed 24 minutes ago
  return { notes, learned };
}

/** The starter vault's notes in the demo's shape: id = path, links resolved by note name, tags from the frontmatter, a markdown preview. */
function packInto(state, pack, now) {
  const r = rng(4242), list = Array.isArray(pack && pack.notes) ? pack.notes : [];
  const byTitle = new Map();
  for (const n of list) byTitle.set(n.path.split('/').pop().replace(/\.md$/i, ''), n.path);
  const out = [];
  for (const n of list) {
    const fm = /^---\n([\s\S]*?)\n---\n/.exec(n.text), body = fm ? n.text.slice(fm[0].length) : n.text;
    const tg = fm ? /^tags:\s*\[(.*)\]\s*$/m.exec(fm[1]) : null;
    const links = [];
    for (const m of body.matchAll(/\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]/g)) {
      const id = byTitle.get(m[1].trim());
      if (id && id !== n.path && !links.includes(id)) links.push(id);
    }
    const para = body.replace(/^#.*$/gm, '').split(/\n\s*\n/).map((x) => x.replace(/^>\s?/, '').trim()).find((x) => x && !x.startsWith('|') && !x.startsWith('---')) || '';
    out.push({ id: n.path, title: n.path.split('/').pop().replace(/\.md$/i, ''), path: n.path, tags: tg ? tg[1].split(',').map((t) => t.trim().toLowerCase()).filter(Boolean) : [],
      links, mtime: now - Math.floor(r() * r() * 60) * D - Math.floor(r() * D), words: (body.match(/\S+/g) || []).length, kind: 'note',
      snippet: para.replace(/[*`]/g, '').slice(0, 240), preview: body.replace(/\n---\nUp:[^\n]*\s*$/, '').trim().slice(0, 1400) });
  }
  state.notes.push(...out);
  const join = (fromId, title) => {                                  // the old fake hubs lead into their real twins
    const a = state.notes.find((x) => x.id === fromId), to = byTitle.get(title);
    if (a && to && !a.links.includes(to)) a.links.push(to);
  };
  join('Me.md', '00 Home'); join('Trading/LIT strategy.md', 'Zlarior LIT strategy'); join('Trading/Prop firm rules.md', 'MFFU rules that matter');
  join('Kalshi/Kalshi bot.md', 'Kalshi bot research'); join('Business/OLYMPUS.md', 'OLYMPUS apps'); join('Trading/Trade journal.md', 'Trade journal');
}

export function createDemo({ size = 0 } = {}) {
  const now = Date.now();
  const state = build(size, now);
  const listeners = new Set();
  let step = 5, timer = 0, packed = false;
  const learn = () => {
    const t = Date.now(), [text, note] = LEARNING[step % LEARNING.length];
    state.learned.push({ t, text, note });
    const n = state.notes.find((x) => x.id === note);
    if (n) { n.mtime = t; n.words += 14; }
    const title = IDEAS[step / 3 - 2];               // every third lesson from the 6th files an idea in the inbox
    if (title) {
      state.notes.push({ id: `Inbox/${title}.md`, title, path: `Inbox/${title}.md`, tags: ['inbox'], kind: 'inbox', words: 30,
        mtime: t, links: note ? [note] : [], snippet: '' });
    }
    step++;
    listeners.forEach((cb) => cb());
  };
  return {
    addPack(pack) {
      if (packed || size > 0) return;                  // ?demo=N is the performance check: exactly N notes, the starter vault stays out
      packed = true;
      packInto(state, pack, Date.now());
    },
    async graphSnapshot() {
      return { v: 1, t: Date.now(), notes: state.notes.map((n) => ({ ...n, tags: n.tags.slice(), links: n.links.slice() })), learned: state.learned.slice() };
    },
    onIndexChange(cb) {
      listeners.add(cb);
      if (!timer) timer = setInterval(learn, LEARN_EVERY_MS);
      return () => { listeners.delete(cb); if (!listeners.size) { clearInterval(timer); timer = 0; } };
    },
  };
}
