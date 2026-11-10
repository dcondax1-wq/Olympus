// ERGASTERION core (pure, node-tested): the workshop where every worker is visible.
// Inputs (every one optional): home (home.json: accounts), money (money/index.json: streams), kalshi (the public kalshi.json feed), cron (cronos/status.json: tasks),
// forge (prometheus/forge.json), heph (hephaestus/data.json), queue (queue.json built by tools/ergasterion_build.py: queue, writeups, rejected, learnings, mind, git).
// Output: one station per real worker with a status lamp (working / idle / stale / failed / sample), what it is doing, its last five outputs, what it LEARNED (dated, with its source file) and its health.
// Honest by rule: a missing file says "no file yet" (stale), a fixture says "sample", nothing is invented. Nothing here trades or sends anything.

export const H = 3600000, D = 24 * H;
export const OLD_H = 36;                 // a nightly worker is stale after this many hours (weekends are quiet, so not shorter)
export const WEEK_D = 7;
export const BOUNDS = { x: 11.4, z: 8.6 };
export const STATION_R = 1.45;           // how close the walker may come to a station centre
export const EYE = 1.6;

export const STATIONS = [
  { id: 'chrysos', name: 'Chrysos', role: 'Prop-firm eval and payout planner', group: 'Money machines', x: -8, z: -6 },
  { id: 'mercury', name: 'Mercury', role: 'Deal finder (prop-firm sales and codes)', group: 'Money machines', x: -4, z: -6 },
  { id: 'sibyl', name: 'Sibyl', role: 'Prediction-market pick finder', group: 'Money machines', x: 0, z: -6 },
  { id: 'oikos', name: 'Oikos', role: 'Household savings finder', group: 'Money machines', x: 4, z: -6 },
  { id: 'arbiter', name: 'Arbiter', role: 'Price-gap checker', group: 'Money machines', x: 8, z: -6 },
  { id: 'lit', name: 'Zlarior (LIT)', role: 'The live NQ strategy, paper account', group: 'NQ bots', x: -7.5, z: -1.2 },
  { id: 'atlas', name: 'ATLAS', role: 'Second NQ strategy, 25K account', group: 'NQ bots', x: -4.5, z: -1.2 },
  { id: 'blitz', name: 'BLITZ', role: 'Third NQ strategy, 25K account', group: 'NQ bots', x: -1.5, z: -1.2 },
  { id: 'mind', name: 'Mind', role: 'Nightly self-research and game plans', group: 'Thinkers', x: 2, z: -1.2 },
  { id: 'kalshi', name: 'Kalshi bot', role: 'Prediction-market trading bot (paper)', group: 'Thinkers', x: 5, z: -1.2 },
  { id: 'prometheus', name: 'Prometheus', role: 'Breeds LIT settings, checks them on later months', group: 'Jobs', x: -7.5, z: 3.6 },
  { id: 'hephaestus', name: 'Hephaestus', role: 'Stored results of every LIT setting that was run', group: 'Jobs', x: -4.5, z: 3.6 },
  { id: 'cronos', name: 'Cronos', role: 'The night clock: refreshes every research app', group: 'Jobs', x: -1.5, z: 3.6 },
  { id: 'queue', name: 'The queue', role: 'ChatGPT / Claude task queue (handoff/QUEUE.md)', group: 'People and agents', x: 2, z: 3.6 },
  { id: 'dev', name: 'Dev agents', role: 'The coding agents of this project (branches, commits, write-ups)', group: 'People and agents', x: 5.5, z: 3.6 },
];
export const IDS = STATIONS.map((s) => s.id);
export const STATUS_WORD = { working: 'Working', idle: 'Idle', stale: 'Stale', failed: 'Failed', sample: 'Sample data' };
export const STATUS_HELP = { working: 'ran recently', idle: 'quiet, nothing wrong', stale: 'old or missing data', failed: 'its last run failed', sample: 'demo numbers, not real' };
export const STATUS_RANK = { failed: 0, stale: 1, sample: 2, idle: 3, working: 4 };

const isObj = (v) => v !== null && typeof v === 'object' && !Array.isArray(v);
const num = (v) => (typeof v === 'number' && isFinite(v) ? v : null);
export function clean(t, n) { const s = String(t == null ? '' : t).replace(/[<>]/g, '').replace(/\s+/g, ' ').trim(); return s.length > n ? s.slice(0, n - 1).trimEnd() + '…' : s; }
export function money(v) { const n = num(v); if (n == null) return '$?'; return (n < 0 ? '-$' : '$') + Math.abs(Math.round(n)).toLocaleString('en-US'); }
export function moneyS(v) { const n = num(v); if (n == null) return '$?'; return (n > 0 ? '+' : '') + money(n); }
/** ISO text, 'YYYY-MM-DD', 'YYYY-MM-DD HH:MM', epoch seconds or milliseconds -> ms (or null) */
export function toMs(v) {
  if (typeof v === 'number' && isFinite(v) && v > 0) return v > 1e11 ? v : v * 1000;
  if (typeof v !== 'string' || !v) return null;
  const t = Date.parse(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$/.test(v) ? v.replace(' ', 'T') + ':00Z' : /^\d{4}-\d{2}-\d{2}$/.test(v) ? v + 'T12:00:00Z' : v);
  return isFinite(t) ? t : null;
}
export const dayOf = (ms) => (ms == null ? '' : new Date(ms).toISOString().slice(0, 10));
export function ageH(ms, now) { return ms == null || !isFinite(now) ? null : Math.max(0, (now - ms) / H); }
export function agoText(ms, now) {
  const a = ageH(ms, now);
  if (a == null) return 'no time on record';
  if (a < 1) return Math.max(1, Math.round(a * 60)) + ' min ago';
  if (a < 36) return Math.round(a) + ' h ago';
  return Math.round(a / 24) + ' days ago';
}

function base(s) { return { id: s.id, name: s.name, role: s.role, group: s.group, x: s.x, z: s.z, status: 'stale', doing: '', last: null, outputs: [], learned: [], health: '', n: null, items: 0, demo: false, missing: false, src: '' }; }
const out = (t, text) => ({ t: t == null ? null : t, text: clean(text, 150) });

function learnedFrom(queue, id, extra) {
  const L = [];
  for (const l of (isObj(queue) && Array.isArray(queue.learnings) ? queue.learnings : [])) {
    if (isObj(l) && l.who === id && l.text) L.push({ d: String(l.d || '').slice(0, 10), text: clean(l.text, 170), src: clean(l.src || 'research/writeups', 90) });
  }
  return (extra || []).concat(L);
}

function money1(id, inp, now, w) {
  const m = isObj(inp.money) ? inp.money : null, s = m && Array.isArray(m.streams) ? m.streams.find((x) => isObj(x) && x.id === id) : null;
  w.src = 'money/' + id + '.json';
  if (!s) { w.missing = true; w.doing = 'No file from this machine yet.'; w.health = 'money/' + id + '.json is not published (run RUN_MONEY.bat on the PC).'; return; }
  const last = toMs(s.asof) != null ? toMs(s.asof) : (num(s.age_min) != null ? now - s.age_min * 60000 : null), age = ageH(last, now), items = Array.isArray(s.items) ? s.items.filter(isObj) : [];
  w.last = last; w.items = items.length; w.n = items.length;
  w.status = s.status === 'sample' ? 'sample' : (s.status === 'error' || s.status === 'failed') ? 'failed' : s.status === 'stale' || (age != null && age > OLD_H) ? 'stale' : age != null && age <= 6 ? 'working' : 'idle';
  w.demo = s.status === 'sample';
  w.doing = clean(s.headline, 200) || (items.length ? 'Weighing ' + items.length + ' pick' + (items.length === 1 ? '' : 's') + '.' : 'Looked, found nothing worth a card.');
  w.outputs = items.slice(0, 5).map((i) => out(last, clean(i.title, 90) + (num(i.usd) != null ? ' (about ' + money(i.usd) + ', an estimate)' : '')));
  w.learned = learnedFrom(inp.queue, id, (Array.isArray(s.notes) ? s.notes : []).slice(0, 3).map((t) => ({ d: dayOf(last), text: clean(t, 170), src: w.src })));
  w.health = (w.demo ? 'Sample data, not a real find. ' : '') + 'Updated ' + agoText(last, now) + '.';
}

const BOT_RE = { lit: /zlarior|\blit\b|mffu50k/i, atlas: /atlas|acctb/i, blitz: /blitz|acct_c/i };
function bot1(id, inp, now, w) {
  const home = isObj(inp.home) ? inp.home : null, accts = home && Array.isArray(home.accounts) ? home.accounts.filter(isObj) : [];
  const a = accts.find((x) => BOT_RE[id].test(String(x.name || '') + ' ' + String(x.id || '')));
  w.src = 'home.json';
  w.learned = learnedFrom(inp.queue, id, []);
  if (!a) { w.missing = true; w.doing = 'No account for this bot in home.json yet.'; w.health = 'home.json has no ' + w.name + ' account.'; return; }
  const ev = isObj(a.eval) ? a.eval : {}, pnl = isObj(a.pnl) ? a.pnl : {}, conn = isObj(a.conn) ? a.conn : {}, last = home.t != null ? toMs(home.t) : null;
  w.last = last;
  w.status = conn.connected === false ? 'stale' : a.paused || ev.paused ? 'idle' : 'working';
  const dd = num(ev.room) != null && num(ev.mll) != null ? 'Drawdown left ' + money(ev.room) + ' of ' + money(ev.mll) + ' max loss.' : '';
  w.doing = 'Paper account: ' + (num(pnl.today) != null ? moneyS(pnl.today) + ' today. ' : 'no P&L yet today. ') + dd;
  w.outputs = [out(last, 'Today ' + (num(pnl.today) != null ? moneyS(pnl.today) : 'no P&L yet'))].concat(dd ? [out(last, dd)] : []);
  w.items = num(pnl.today) != null && pnl.today !== 0 ? 1 : 0;
  w.health = conn.connected === false ? 'Not connected right now.' : 'Connected. ' + (a.paused ? 'Paused.' : 'Paper only: it never places a real order.');
}

function mind1(inp, now, w) {
  const q = isObj(inp.queue) ? inp.queue : null, m = q && isObj(q.mind) ? q.mind : null, t = m && m.t ? toMs(m.t) : null;
  w.src = m && m.source ? m.source : 'research/mind/';
  w.last = t; w.n = m ? m.tested : null;
  const obs = m && Array.isArray(m.observations) ? m.observations.filter(isObj) : [];
  w.items = obs.length;
  if (!m) { w.missing = true; w.doing = 'No research file yet.'; w.health = 'queue.json has no Mind block.'; return; }
  const age = ageH(t, now);
  w.status = age != null && age <= 48 ? 'working' : 'stale';
  w.demo = !!inp.demo;
  w.doing = 'Nightly self-research: ' + (num(m.tested) || 0) + ' ideas tested, ' + obs.length + ' notes about recent trades. It only suggests; it never changes a rule.';
  w.outputs = obs.slice(0, 5).map((o) => out(t, o.text));
  w.learned = learnedFrom(inp.queue, 'mind', [{ d: '', text: 'Similar-setup memory is context only: it is not predictive out of sample.', src: 'docs/CLAUDE_REFERENCE.md (Mind)' }]);
  w.health = 'Last research ' + agoText(t, now) + (age != null && age > 48 ? ' (the nightly run is overdue or only the seed is here).' : '.');
}

function kalshi1(inp, now, w) {
  const k = isObj(inp.kalshi) ? inp.kalshi : null;
  w.src = 'kalshi.json';
  w.learned = learnedFrom(inp.queue, 'kalshi', []);
  if (!k) { w.missing = true; w.doing = 'No Kalshi feed reachable.'; w.health = 'The public kalshi.json feed was not read.'; return; }
  const last = k.t != null ? toMs(k.t) : null, age = ageH(last, now), tr = Array.isArray(k.last_trades) ? k.last_trades : Array.isArray(k.trades) ? k.trades : [];
  w.last = last; w.n = num(k.settled_n) != null ? k.settled_n : num(k.n_settled) != null ? k.n_settled : null;
  w.status = k.running === false ? 'failed' : age != null && age > OLD_H ? 'stale' : k.running ? 'working' : 'idle';
  w.demo = !!inp.demo;
  w.doing = (k.running === false ? 'Not running. ' : k.running ? 'Running (paper). ' : '') + (num(k.today_pnl) != null ? 'Today ' + moneyS(k.today_pnl) + '.' : 'No P&L today.');
  w.outputs = tr.filter(isObj).slice(0, 5).map((x) => out(toMs(x.t != null ? x.t : x.ts), clean(x.title || x.ticker || x.market || 'trade', 70) + (num(x.pnl) != null ? ' ' + moneyS(x.pnl) : '')));
  if (!w.outputs.length && num(k.today_pnl) != null) w.outputs = [out(last, 'Today ' + moneyS(k.today_pnl))];
  w.items = tr.length;
  w.health = k.running === false ? 'Not running: check the Oracle VM.' : 'Feed updated ' + agoText(last, now) + '.';
}

function prom1(inp, now, w) {
  const f = isObj(inp.forge) ? inp.forge : null, ct = cronTask(inp, 'prometheus');
  w.src = 'prometheus/forge.json';
  w.learned = learnedFrom(inp.queue, 'prometheus', []);
  if (!f) { w.missing = true; w.doing = 'No forge file yet.'; w.health = 'prometheus/forge.json is not published.'; return; }
  const last = toMs(f.built), age = ageH(last, now), v = isObj(f.verdict) ? f.verdict : {}, hn = isObj(f.honesty) ? f.honesty : {};
  w.last = last; w.demo = f.demo === true;
  w.status = w.demo ? 'sample' : ct && ct.ok === false ? 'failed' : age != null && age > 8 * 24 ? 'stale' : 'idle';
  w.doing = 'Breeds LIT settings: ' + (f.gens_n || '?') + ' generations of ' + (f.pop || '?') + ' candidates, fitted on Jan-Jun 2026 only, then checked on Jul-Oct. ' + (v.real_margin === false ? 'No real margin over live.' : v.real_margin ? 'A candidate holds a margin.' : '');
  if (num(v.h1_gain_pm) != null) w.outputs.push(out(last, 'Best candidate: ' + moneyS(v.h1_gain_pm) + '/month on the fit half, ' + moneyS(v.h2_gain_pm) + '/month on the check half.'));
  if (num(hn.genomes_checked) != null) w.outputs.push(out(last, num(hn.beat_live_both) + ' of ' + hn.genomes_checked + ' candidates beat live on both halves.'));
  if (num(v.survive_pct) != null) w.outputs.push(out(last, 'Share of the fit-half gain that survived the check half: ' + v.survive_pct + '%.'));
  w.items = w.outputs.length;
  if (num(hn.genomes_checked) != null) w.learned.unshift({ d: dayOf(last), text: 'Only ' + num(hn.beat_live_both) + ' of ' + hn.genomes_checked + ' bred candidates beat live LIT on both halves' + (v.real_margin === false ? '; no real margin, nothing to switch.' : '.'), src: w.src });
  w.health = (ct && ct.ok === false ? 'Last run failed. ' : '') + 'Built ' + agoText(last, now) + ' (weekly job).';
}

function heph1(inp, now, w) {
  const f = isObj(inp.heph) ? inp.heph : null;
  w.src = 'hephaestus/data.json';
  w.learned = learnedFrom(inp.queue, 'hephaestus', []);
  if (!f) { w.missing = true; w.doing = 'No results file yet.'; w.health = 'hephaestus/data.json is not published.'; return; }
  const last = toMs(f.built), age = ageH(last, now), dials = Array.isArray(f.dials) ? f.dials.filter(isObj) : [];
  w.last = last; w.demo = f.demo === true;
  w.status = w.demo ? 'sample' : age != null && age > 30 * 24 ? 'stale' : 'idle';
  w.doing = 'Keeps the stored 2026 results of every LIT setting that was really run, Jan-Jun against Jul-Oct. It never runs the strategy and changes nothing.';
  w.outputs = dials.slice(0, 5).map((d) => out(last, 'Dial: ' + clean(d.label, 60) + ' (' + (Array.isArray(d.options) ? d.options.length : 0) + ' settings stored)'));
  w.items = dials.length; w.n = dials.length;
  w.health = 'Results stored ' + agoText(last, now) + '. Read-only.';
}

function cronTask(inp, name) { const c = isObj(inp.cron) && isObj(inp.cron.tasks) ? inp.cron.tasks : null; return c && isObj(c[name]) ? c[name] : null; }
function cron1(inp, now, w) {
  const c = isObj(inp.cron) && isObj(inp.cron.tasks) ? inp.cron.tasks : null;
  w.src = 'cronos/status.json';
  w.learned = learnedFrom(inp.queue, 'cronos', []);
  if (!c) { w.missing = true; w.doing = 'No job log yet.'; w.health = 'cronos/status.json is not published (it is built by the nightly jobs).'; return; }
  const rows = Object.keys(c).filter((k) => isObj(c[k])).map((k) => ({ k, e: c[k], t: toMs(c[k].last_run_t) })).sort((a, b) => (b.t || 0) - (a.t || 0));
  const failed = rows.filter((r) => r.e.ok === false), old = rows.filter((r) => r.e.ok !== false && r.t != null && ageH(r.t, now) > (r.e.cadence === 'weekly' ? 8 * 24 : 80));
  w.last = rows.length && rows[0].t; w.items = rows.length; w.n = rows.length;
  w.status = failed.length ? 'failed' : old.length ? 'stale' : rows.length ? 'working' : 'idle';
  w.demo = !!inp.demo;
  w.doing = rows.length + ' scheduled jobs: ' + (rows.length - failed.length - old.length) + ' fine' + (old.length ? ', ' + old.length + ' overdue' : '') + (failed.length ? ', ' + failed.length + ' failed' : '') + '.';
  w.outputs = rows.slice(0, 5).map((r) => out(r.t, r.k + ': ' + (r.e.ok === false ? 'FAILED ' + clean(r.e.error, 70) : 'ok') + (r.e.note && r.e.ok !== false ? ' (' + clean(r.e.note, 60) + ')' : '')));
  w.health = failed.length ? 'Failed: ' + failed.map((r) => r.k).join(', ') + '.' : old.length ? 'Overdue: ' + old.map((r) => r.k).join(', ') + '.' : 'Every job ran on time.';
}

function queue1(inp, now, w) {
  const q = isObj(inp.queue) && isObj(inp.queue.queue) ? inp.queue.queue : null;
  w.src = 'handoff/QUEUE.md';
  if (!q) { w.missing = true; w.doing = 'No queue file yet.'; w.health = 'queue.json is not published (python tools/ergasterion_build.py).'; return; }
  const tasks = Array.isArray(q.tasks) ? q.tasks.filter(isObj) : [], last = toMs(inp.queue.asof);
  w.last = last; w.items = num(q.open) || 0; w.n = num(q.total);
  w.status = (num(q.open) || 0) > 0 ? 'working' : 'idle';
  w.demo = !!inp.demo;
  w.doing = (num(q.open) || 0) + ' open task' + (q.open === 1 ? '' : 's') + ', ' + (num(q.done) || 0) + ' done. ' + (tasks[0] ? 'Next: ' + clean(tasks[0].id, 40) + '.' : '');
  w.outputs = tasks.slice(0, 5).map((t) => out(last, clean(t.id, 30) + ': ' + clean(t.text, 100)));
  w.learned = [];
  w.health = 'Task list as of ' + (dayOf(last) || 'an unknown day') + '. Done tasks are ticked in the file by whoever did them.';
}

function dev1(inp, now, w) {
  const q = isObj(inp.queue) ? inp.queue : null, g = q && isObj(q.git) ? q.git : null, wu = q && isObj(q.writeups) ? q.writeups : null, commits = g && Array.isArray(g.commits) ? g.commits.filter(isObj) : [];
  w.src = commits.length ? 'git log' : 'research/writeups';
  w.demo = !!inp.demo;
  if (!q) { w.missing = true; w.doing = 'No project index yet.'; w.health = 'queue.json is not published.'; return; }
  const bs = g && Array.isArray(g.branches) ? g.branches.filter(isObj) : [];
  if (commits.length) {
    w.last = toMs(commits[0].t); w.outputs = commits.slice(0, 5).map((c) => out(toMs(c.t), c.s));
    w.doing = 'Latest commit: ' + clean(commits[0].s, 100) + (bs.length ? ' (' + bs.length + ' agent / task branches)' : '');
    w.status = ageH(w.last, now) <= 24 ? 'working' : 'idle';
    w.health = 'Git history read at build time; ' + commits.length + ' recent commits.';
  } else {
    const l = wu && Array.isArray(wu.latest) ? wu.latest.filter(isObj) : [];
    w.last = l.length ? toMs(l[0].date) : null; w.outputs = l.slice(0, 5).map((x) => out(toMs(x.date), 'Write-up: ' + clean(x.title, 90)));
    w.doing = l.length ? 'No git history at build time. The latest write-up: ' + clean(l[0].title, 90) : 'Nothing indexed yet.';
    w.status = l.length ? 'idle' : 'stale';
    w.health = 'Git history was not available when the site was built; showing write-ups only.';
  }
  w.items = w.outputs.length; w.n = wu && num(wu.count);
  const rej = (Array.isArray(q.rejected) ? q.rejected : []).filter(isObj).slice(0, 3).map((r) => ({ d: String(r.date || '').slice(0, 10), text: 'Tested and rejected: ' + clean(r.title, 110), src: clean(r.file, 90) }));
  w.learned = learnedFrom(q, 'dev', []).concat(rej);
}

export function buildWorkers(inp0, now) {
  const inp = isObj(inp0) ? inp0 : {};
  const W = STATIONS.map((s) => {
    const w = base(s);
    try {
      if (['chrysos', 'mercury', 'sibyl', 'oikos', 'arbiter'].includes(s.id)) money1(s.id, inp, now, w);
      else if (BOT_RE[s.id]) bot1(s.id, inp, now, w);
      else if (s.id === 'mind') mind1(inp, now, w);
      else if (s.id === 'kalshi') kalshi1(inp, now, w);
      else if (s.id === 'prometheus') prom1(inp, now, w);
      else if (s.id === 'hephaestus') heph1(inp, now, w);
      else if (s.id === 'cronos') cron1(inp, now, w);
      else if (s.id === 'queue') queue1(inp, now, w);
      else if (s.id === 'dev') dev1(inp, now, w);
    } catch (_) { w.status = 'failed'; w.doing = 'Could not read its file.'; }
    if (w.status === 'stale' && w.missing) w.health = w.health || 'No file yet.';
    if (inp.demo) { w.demo = true; w.health = 'Example data. ' + w.health; }
    w.outputs = w.outputs.slice(0, 5);
    w.learned = w.learned.slice(0, 8);
    return w;
  });
  return W;
}

/** newest first, plain words: every dated output of every worker */
export function events(workers, now, limit) {
  const E = [];
  for (const w of workers) for (const o of w.outputs) if (o.t != null && o.t <= now + H) E.push({ t: o.t, who: w.id, name: w.name, text: o.text });
  for (const w of workers) if (w.last != null && w.last <= now + H && !E.some((e) => e.who === w.id && e.t === w.last)) E.push({ t: w.last, who: w.id, name: w.name, text: w.status === 'failed' ? 'its last run failed' : 'last ran (' + STATUS_WORD[w.status].toLowerCase() + ')' });
  E.sort((a, b) => b.t - a.t);
  return E.slice(0, limit || 30);
}

/** the Learning board: up to 12 dated lessons, the week first, at most 3 per worker in the first pass */
export function lessons(workers, now, limit) {
  const n = limit || 12, seen = new Set(), all = [];
  for (const w of workers) for (const l of w.learned) {
    const key = l.text.toLowerCase();
    if (seen.has(key)) continue; seen.add(key);
    const ms = toMs(l.d);
    all.push({ who: w.id, name: w.name, d: l.d || '', ms, text: l.text, src: l.src, week: ms != null && now - ms <= WEEK_D * D && ms <= now + D, sample: w.status === 'sample' });
  }
  all.sort((a, b) => (b.ms == null ? -1 : b.ms) - (a.ms == null ? -1 : a.ms) || (a.who < b.who ? -1 : 1));
  const pick = [], per = {};
  for (const pass of [3, 99]) {
    for (const l of all) { if (pick.length >= n) break; if (pick.includes(l) || (per[l.who] || 0) >= pass) continue; if (l.ms == null && pass === 3 && pick.length < n - 2) continue; pick.push(l); per[l.who] = (per[l.who] || 0) + 1; }
  }
  pick.sort((a, b) => (b.ms == null ? -1 : b.ms) - (a.ms == null ? -1 : a.ms));
  return pick;
}

/** ranked "what should we research next?": from data gaps (sample / missing / stale / failed / small samples / the queue) */
export function suggestions(workers, queueBlock, now) {
  const S = [], q = isObj(queueBlock) && isObj(queueBlock.queue) ? queueBlock.queue : null;
  for (const w of workers) {
    const money = ['chrysos', 'mercury', 'sibyl', 'oikos', 'arbiter'].includes(w.id);
    if (w.status === 'failed') S.push({ w: 100, who: w.id, title: w.name + ' failed its last run', why: w.health || w.doing, next: w.id === 'kalshi' ? 'Check the Oracle VM and restart the bot there.' : 'Open its log, fix the cause, run it once by hand.' });
    else if (w.missing) S.push({ w: 80, who: w.id, title: w.name + ' has no file here', why: w.health, next: money ? 'Run RUN_MONEY.bat on the PC, then publish the site.' : w.id === 'cronos' ? 'Run python -m tools.cronos once, or wait for the nightly job.' : 'Rebuild the site so its file is published.' });
    else if (w.status === 'sample') S.push({ w: 70, who: w.id, title: w.name + ' is in demo mode', why: 'Its numbers are a sample, so nothing it shows is a real finding.', next: money ? 'Run RUN_MONEY.bat so ' + w.name + ' reads real public data.' : 'Connect its real feed; until then treat everything as an example.' });
    else if (w.status === 'stale') S.push({ w: 60, who: w.id, title: w.name + ' is stale', why: w.health, next: 'Refresh it (' + (money ? 'RUN_MONEY.bat' : w.id === 'mind' ? 'wait for the nightly research, or python -X utf8 tools/mind_build.py' : 'the next site build') + ') and look again.' });
    if (w.n != null && w.n < 30 && ['kalshi'].includes(w.id) && w.status !== 'sample') S.push({ w: 50, who: w.id, title: w.name + ' has only ' + w.n + ' settled trades', why: 'Too few to call any edge real.', next: 'Keep it running on paper; test nothing new until there are 30 or more.' });
  }
  if (q && (num(q.open) || 0) > 0) { const t = Array.isArray(q.tasks) && q.tasks[0]; S.push({ w: 40, who: 'queue', title: 'The queue has ' + q.open + ' open tasks', why: 'Nobody has ticked them yet.', next: t ? 'Start with ' + clean(t.id, 40) + '.' : 'Open handoff/QUEUE.md.' }); }
  S.sort((a, b) => b.w - a.w || (a.who < b.who ? -1 : 1));
  const top = S.slice(0, 6);
  if (!top.length) top.push({ w: 0, who: '', title: 'Nothing is waiting', why: 'Every worker has fresh, real data.', next: 'Pick the next idea from the "Tested and rejected" list only if you have a new reason.' });
  return top;
}

export function headline(workers) {
  const c = { working: 0, idle: 0, stale: 0, failed: 0, sample: 0 };
  for (const w of workers) c[w.status]++;
  const bad = c.failed + c.stale, n = workers.length;
  const level = c.failed ? 'bad' : bad || c.sample ? 'warn' : 'ok';
  const parts = [];
  if (c.working) parts.push(c.working + ' working');
  if (c.idle) parts.push(c.idle + ' idle');
  if (c.sample) parts.push(c.sample + ' showing sample data');
  if (c.stale) parts.push(c.stale + ' stale');
  if (c.failed) parts.push(c.failed + ' failed');
  const title = c.failed ? c.failed + ' worker' + (c.failed === 1 ? '' : 's') + ' failed' : bad ? bad + ' of ' + n + ' workers need a look' : c.sample ? 'Showing sample data' : 'All ' + n + ' workers are fine';
  return { level, title, line: parts.join(', ') + '.', counts: c, n };
}

/** the fixture's relative times (age_h, ago_h, d_ago) -> real ones from now, so the demo is always "recent" */
export function resolveDemo(fx, now) {
  const f = JSON.parse(JSON.stringify(isObj(fx) ? fx : {}));
  const day = (n) => dayOf(now - n * D);
  if (isObj(f.home) && f.home.t_ago_h != null) f.home.t = Math.round((now - f.home.t_ago_h * H) / 1000);
  if (isObj(f.kalshi) && f.kalshi.t_ago_h != null) f.kalshi.t = Math.round((now - f.kalshi.t_ago_h * H) / 1000);
  if (isObj(f.money)) for (const s of f.money.streams || []) if (num(s.age_min) != null) s.asof = new Date(now - s.age_min * 60000).toISOString();
  if (isObj(f.cron)) for (const k in f.cron.tasks || {}) if (num(f.cron.tasks[k].ago_h) != null) f.cron.tasks[k].last_run_t = Math.round((now - f.cron.tasks[k].ago_h * H) / 1000);
  if (isObj(f.forge) && num(f.forge.built_ago_d) != null) f.forge.built = day(f.forge.built_ago_d) + ' 02:00';
  if (isObj(f.heph) && num(f.heph.built_ago_d) != null) f.heph.built = day(f.heph.built_ago_d) + ' 02:00';
  if (isObj(f.queue)) {
    const q = f.queue;
    if (num(q.asof_ago_d) != null) q.asof = day(q.asof_ago_d);
    for (const l of q.learnings || []) if (num(l.d_ago) != null) l.d = day(l.d_ago);
    for (const r of q.rejected || []) if (num(r.d_ago) != null) r.date = day(r.d_ago);
    if (isObj(q.mind) && num(q.mind.ago_h) != null) q.mind.t = Math.round((now - q.mind.ago_h * H) / 1000);
    if (isObj(q.git)) for (const c of q.git.commits || []) if (num(c.ago_h) != null) c.t = Math.round((now - c.ago_h * H) / 1000);
    if (isObj(q.writeups)) for (const x of q.writeups.latest || []) if (num(x.d_ago) != null) x.date = day(x.d_ago);
  }
  f.demo = true;
  return f;
}

/** true when at least one real worker file arrived (queue.json ships with the site, so it alone does not make the page real) */
export function haveReal(inp) { return isObj(inp) && ['home', 'money', 'kalshi', 'cron', 'forge', 'heph'].some((k) => isObj(inp[k])); }

// ------------------------------------------------------------------ walking the floor (pure, so it is tested)
export function resolveCollision(x, z, stations, r) {
  const R = r == null ? STATION_R : r;
  x = Math.max(-BOUNDS.x, Math.min(BOUNDS.x, x)); z = Math.max(-BOUNDS.z, Math.min(BOUNDS.z, z));
  for (const s of stations) {
    const dx = x - s.x, dz = z - s.z, d = Math.hypot(dx, dz);
    if (d < R) { const k = d < 1e-6 ? 1 : R / d; x = s.x + (d < 1e-6 ? R : dx * k); z = s.z + (d < 1e-6 ? 0 : dz * k); }
  }
  return { x, z };
}
/** move: { fwd, side } in -1..1 (joystick); yaw 0 looks toward -z; dt seconds */
export function walk(p, yaw, move, dt, stations, speed) {
  const sp = (speed || 3.4) * Math.min(dt, 0.1), f = Math.max(-1, Math.min(1, move.fwd || 0)), s = Math.max(-1, Math.min(1, move.side || 0));
  const nx = p.x + (-Math.sin(yaw) * f + Math.cos(yaw) * s) * sp, nz = p.z + (-Math.cos(yaw) * f - Math.sin(yaw) * s) * sp;
  return resolveCollision(nx, nz, stations);
}
export function nearest(p, stations, maxD) {
  let best = null, bd = maxD == null ? 3.2 : maxD;
  for (const s of stations) { const d = Math.hypot(p.x - s.x, p.z - s.z); if (d < bd) { bd = d; best = s; } }
  return best;
}
/** the camera for 'follow worker X': behind and above the figure, looking at it */
export function followCam(s, t, reduced) {
  const a = reduced ? 0 : t * 0.35, fx = s.x + Math.sin(a) * 0.5, fz = s.z + Math.cos(a) * 0.5;
  return { x: fx, z: fz + 3.2, y: 2.2, look: { x: fx, y: 1.25, z: fz } };
}

export function jarvisCard(workers, queueBlock, now, demo) {
  const hd = headline(workers), q = isObj(queueBlock) && isObj(queueBlock.queue) ? queueBlock.queue : {};
  const need = hd.counts.failed + hd.counts.stale;
  return { v: 1, name: 'Ergasterion', status: { level: demo ? 'off' : hd.level === 'bad' ? 'bad' : need || hd.counts.sample ? 'warn' : 'ok', label: demo ? 'Demo data' : need ? need + ' need a look' : 'All fine' },
    kpis: [{ label: 'Working', value: String(hd.counts.working) }, { label: 'Need a look', value: String(need) }, { label: 'Open tasks', value: String(num(q.open) || 0) }],
    lines: [clean(hd.title + '. ' + hd.line, 118)], t: Math.round(now / 1000), open: '#', theme: '#14110e', stale_after: 86400 };
}
