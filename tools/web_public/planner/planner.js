// PLANNER page (ES module): the trader's day and week plan. The plan lives in this phone's localStorage ('planner.agora.v1') with Export / Import JSON and works offline.
// While nothing is saved it shows the DEMO plan from fixture.json (never blank; changes made in the demo are not saved). Sends nothing anywhere.
// Text only through textContent / a value (no markup is built from data). window.PLANNER is the test hook.
import * as C from './plannercore.js';

const O = window.OLYMPUS || null;
const $ = (id) => document.getElementById(id);
function h(tag, cls, text) { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = String(text); return e; }
const clear = (el) => { while (el.firstChild) el.removeChild(el.firstChild); };
const TABS = ['today', 'week', 'habits', 'notes', 'data'];
const S = { state: null, demo: false, forced: false, fixture: null, day: '', today: '', tab: 'today', fixedNow: null, saveOk: null, savedAt: 0, arm: '', ready: false, now: new Date() };
let noteTimer = 0, armTimer = 0;

async function getJSON(url, ms) {
  const ac = typeof AbortController === 'function' ? new AbortController() : null, timer = ac ? setTimeout(() => ac.abort(), ms || 6000) : 0;
  try { const r = await fetch(url, { cache: 'no-cache', ...(ac ? { signal: ac.signal } : {}) }); return r.ok ? await r.json() : null; } catch (_) { return null; } finally { clearTimeout(timer); }
}
function say(t) { $('status').textContent = t; }
function nowDate() { return S.fixedNow || new Date(); }

// ------------------------------------------------------------------------------------------------ storage
function loadSaved() {
  let t = null;
  try { t = localStorage.getItem(C.STORE_KEY); } catch (_) { return null; }
  if (t == null) return null;
  try { return C.normalise(JSON.parse(t)); } catch (_) { try { localStorage.setItem(C.STORE_KEY + '.bad', t); } catch (_e) { /* nothing */ } return null; }
}
function save() {
  if (S.demo) return;
  S.state.updated = Date.now();
  try {
    localStorage.setItem(C.STORE_KEY, JSON.stringify(S.state)); S.saveOk = true; S.savedAt = S.state.updated;
    localStorage.setItem('planner.today.v1', JSON.stringify(C.todaySummary(S.state, S.today, S.state.updated)));
  } catch (_) { S.saveOk = false; }
}
function change(fn, keepFocus) {
  fn(S.state);
  save();
  render();
  if (keepFocus && $(keepFocus)) $(keepFocus).focus();
}
function armed(key) {
  if (S.arm === key) { S.arm = ''; clearTimeout(armTimer); return true; }
  S.arm = key; clearTimeout(armTimer); armTimer = setTimeout(() => { S.arm = ''; render(); }, 4000);
  render();
  return false;
}

// ------------------------------------------------------------------------------------------------ small builders
function checkRow(done, text, small, onTap, extra) {
  const li = h('li', 'row'), b = h('button', 'rowbtn'); b.type = 'button'; b.setAttribute('role', 'checkbox'); b.setAttribute('aria-checked', done ? 'true' : 'false');
  b.appendChild(h('span', 'box', done ? '✓' : ''));
  if (extra) b.appendChild(h('span', 'slot', extra));
  const t = h('span', 'txt', text); if (small) t.appendChild(h('small', '', small));
  b.appendChild(t);
  b.addEventListener('click', onTap);
  li.appendChild(b);
  return li;
}
function iconBtn(label, glyph, onTap, cls) { const b = h('button', 'btn ' + (cls || ''), glyph); b.type = 'button'; b.setAttribute('aria-label', label); b.addEventListener('click', onTap); return b; }
function empty(ul, text) { ul.appendChild(h('li', 'note empty', text)); }

// ------------------------------------------------------------------------------------------------ panels
function renderDayNav() {
  const d = S.day;
  $('dayTitle').textContent = C.dayLabel(d);
  $('daySub').textContent = d === S.today ? 'Today' : d < S.today ? 'A past day' : 'A day ahead';
  $('dayToday').hidden = d === S.today;
  $('dayNav').hidden = !(S.tab === 'today' || S.tab === 'notes' || S.tab === 'habits');
}

function renderNow() {
  const d = S.day, isToday = d === S.today, ses = C.sessionState(nowDate());
  const row = $('clkTime').parentNode; row.hidden = !isToday;
  $('clkTime').textContent = ses.hhmm;
  const ph = $('clkPhase'); ph.textContent = ses.label; ph.className = 'pill ' + (ses.id === 'entries' ? 'ok' : ses.id === 'winddown' || ses.id === 'flat' ? 'warn' : ses.id === 'closed' ? '' : 'info');
  $('clkBar').style.width = (isToday && !ses.weekend ? ses.pct : 0) + '%';
  $('clkBar').parentNode.hidden = !isToday || ses.weekend;
  $('nowH').textContent = isToday ? 'Trading windows' : 'Trading windows for ' + C.dayLabel(d);
  $('clkNext').textContent = isToday ? ses.nextText : C.isWeekend(d) ? 'The bot does not trade at the weekend. Plan the week.' : (d < S.today ? 'This day is over. See what you planned and wrote.' : 'A trading day. The windows below apply.');
  const kv = $('winKv'); clear(kv);
  if (C.isWeekend(d)) { kv.appendChild(h('dt', '', 'Trading')); kv.appendChild(h('dd', '', 'None at the weekend')); return; }
  for (const w of C.WINDOWS) { kv.appendChild(h('dt', '', w.label)); kv.appendChild(h('dd', '', w.at + ' ET')); }
}

function renderToday(v) {
  $('checkSum').textContent = `${v.checkDone} of ${v.check.length} done`;
  const cl = $('checkList'); clear(cl);
  if (!v.check.length) empty(cl, 'The checklist is empty. Add lines in the Data tab.');
  for (const c of v.check) cl.appendChild(checkRow(c.done, c.text, '', () => change((st) => C.toggleCheck(st, S.day, c.id))));
  const tl = $('taskList'); clear(tl);
  if (!v.tasks.length) empty(tl, 'No tasks for this day. Add one above; a time like 09:30 sets its slot.');
  for (const t of v.tasks) {
    const li = checkRow(t.done, t.text, '', () => change((st) => C.toggleTask(st, t.id)), t.slot);
    li.appendChild(iconBtn('Move to the next day: ' + t.text, '→', () => change((st) => C.moveTask(st, t.id, C.addDays(t.day, 1)))));
    li.appendChild(iconBtn('Delete: ' + t.text, '×', () => change((st) => C.removeTask(st, t.id))));
    tl.appendChild(li);
  }
  const hl = $('habitList'); clear(hl);
  if (!v.habits.length) empty(hl, 'No habits yet. Add one in the Habits tab.');
  for (const x of v.habits) hl.appendChild(checkRow(x.done, x.name, x.streak ? `${x.streak} day${x.streak === 1 ? '' : 's'} in a row` : '', () => change((st) => C.toggleHabit(st, S.day, x.id))));
}

function renderWeek() {
  const rows = C.weekView(S.state, S.day, S.today), tot = C.weekTotals(rows, S.today);
  $('weekSub').textContent = `${C.dayLabel(rows[0].day)} to ${C.dayLabel(rows[6].day)}`;
  const tiles = $('weekTiles'); clear(tiles);
  const tile = (k, v, n) => { const t = h('div', 'tile'); t.appendChild(h('small', '', k)); t.appendChild(h('b', 'ag-num', v)); t.appendChild(h('span', '', n)); tiles.appendChild(t); };
  tile('Tasks done', `${tot.done} of ${tot.tasks}`, 'this week');
  tile('Average day', tot.avg == null ? '--' : tot.avg + '%', 'checklist, tasks, habits');
  const ul = $('weekList'); clear(ul);
  for (const r of rows) {
    const li = h('li', 'row'), b = h('button', 'rowbtn' + (r.today ? ' today' : '') + (r.selected ? ' sel' : '') + (r.weekend ? ' weekend' : '')); b.type = 'button';
    b.setAttribute('aria-label', `${C.dayLabel(r.day)}: ${r.tasksDone} of ${r.tasks} tasks`);
    const dn = h('span', 'dn', r.label); dn.appendChild(h('b', '', r.num)); b.appendChild(dn);
    const t = h('span', 'txt');
    t.appendChild(h('span', 'mini', `${r.tasksDone} of ${r.tasks} tasks · ${r.checkDone} of ${r.check} checks`));
    t.appendChild(h('small', '', `${r.habitsDone} of ${r.habits} habits${r.weekend ? ' · no trading' : ''}${r.hasNote ? ' · note' : ''}`));
    b.appendChild(t);
    b.appendChild(h('span', 'score', r.score == null ? '--' : r.score + '%'));
    b.addEventListener('click', () => { S.day = r.day; setTab('today'); });
    li.appendChild(b); ul.appendChild(li);
  }
}

function renderHabits() {
  const box = $('habitCards'); clear(box);
  if (!S.state.habits.length) { const c = h('section', 'ag-card card'); c.appendChild(h('p', 'note', 'No habits yet. Add one below.')); box.appendChild(c); return; }
  for (const x of S.state.habits) {
    const card = h('section', 'ag-card card'), top = h('div', 'hcard-top'), st = C.streak(S.state, x.id, S.today);
    top.appendChild(h('h3', '', x.name));
    const key = 'hab:' + x.id, a = S.arm === key;
    const rm = h('button', 'btn small warnbtn', a ? 'Tap again' : 'Remove'); rm.type = 'button'; rm.setAttribute('aria-label', (a ? 'Tap again to remove ' : 'Remove ') + x.name);
    rm.addEventListener('click', () => { if (armed(key)) change((s) => C.removeHabit(s, x.id)); });
    top.appendChild(rm); card.appendChild(top);
    card.appendChild(h('p', 'note', st ? `${st} day${st === 1 ? '' : 's'} in a row` : 'No streak yet. Tap today to start one.'));
    const wk = h('div', 'hweek');
    for (const d of C.habitWeek(S.state, x.id, S.day)) {
      const b = h('button', 'hday' + (d.day === S.today ? ' now' : '')); b.type = 'button'; b.setAttribute('aria-pressed', d.done ? 'true' : 'false'); b.setAttribute('aria-label', `${x.name}, ${C.dayLabel(d.day)}`);
      b.appendChild(h('span', '', C.shortDay(d.day).slice(0, 2))); b.appendChild(h('b', '', C.dayNum(d.day)));
      b.addEventListener('click', () => change((s) => C.toggleHabit(s, d.day, x.id)));
      wk.appendChild(b);
    }
    card.appendChild(wk); box.appendChild(card);
  }
}

function renderNotes() {
  const ta = $('noteIn');
  if (ta.dataset.day !== S.day) { ta.value = S.state.notes[S.day] || ''; ta.dataset.day = S.day; }
  $('noteH').textContent = 'Note for ' + C.dayLabel(S.day);
  renderRecent();
}
function renderRecent() {
  const ul = $('recentList'); clear(ul);
  $('noteCount').textContent = `${$('noteIn').value.length} of 4000 characters`;
  const list = C.recentNotes(S.state, 10);
  if (!list.length) empty(ul, 'No notes yet. The first one you write shows up here.');
  for (const n of list) {
    const li = h('li', 'row'), b = h('button', 'rowbtn' + (n.day === S.day ? ' sel' : '')); b.type = 'button';
    const t = h('span', 'txt', C.dayLabel(n.day)); t.appendChild(h('small', '', n.text.replace(/\s+/g, ' ').slice(0, 90)));
    b.appendChild(t); b.addEventListener('click', () => { S.day = n.day; render(); });
    li.appendChild(b); ul.appendChild(li);
  }
}

function renderData() {
  const c = C.counts(S.state);
  $('expSum').textContent = `${c.tasks} task${c.tasks === 1 ? '' : 's'}, ${c.habits} habit${c.habits === 1 ? '' : 's'}, ${c.notes} note${c.notes === 1 ? '' : 's'} and ${c.checklist} checklist line${c.checklist === 1 ? '' : 's'}.`;
  const ul = $('clEdit'); clear(ul);
  if (!S.state.checklist.length) empty(ul, 'No lines. Add the first one below.');
  for (const x of S.state.checklist) {
    const li = h('li', 'row edit-row'); li.appendChild(h('span', 'txt', x.text));
    const key = 'cl:' + x.id, a = S.arm === key;
    const b = h('button', 'btn warnbtn' + (a ? ' armed' : ''), a ? 'Sure?' : '×'); b.type = 'button'; b.setAttribute('aria-label', (a ? 'Tap again to delete ' : 'Delete ') + x.text);
    b.addEventListener('click', () => { if (armed(key)) change((s) => C.removeChecklist(s, x.id)); });
    li.appendChild(b); ul.appendChild(li);
  }
  $('stMsg').textContent = S.demo ? 'Showing the example plan. Nothing is saved until you tap Start my plan.'
    : S.saveOk === false ? 'This browser would not save. Use Export to keep your plan.'
    : 'Saved on this phone' + (S.savedAt ? ', last change ' + new Date(S.savedAt).toLocaleString() : '') + '. It works offline.';
  const rb = $('resetBtn'), a = S.arm === 'reset';
  rb.textContent = a ? 'Tap again to erase everything' : 'Reset to a blank plan';
}

function setTab(t) {
  S.tab = TABS.includes(t) ? t : 'today';
  for (const id of TABS) { const on = id === S.tab; $('tab-' + id).setAttribute('aria-selected', on ? 'true' : 'false'); $('p-' + id).hidden = !on; }
  render();
  const el = $('tab-' + S.tab); try { if (el.scrollIntoView) el.scrollIntoView({ block: 'nearest', inline: 'nearest' }); } catch (_) { /* nothing */ }
}

function render() {
  S.today = C.etParts(nowDate()).day;
  if (!C.validDay(S.day)) S.day = S.today;
  $('demo').hidden = !S.demo; $('demoBar').hidden = !S.demo;
  try { $('lite').hidden = !(O && O.lite && O.lite()); } catch (_) { $('lite').hidden = true; }
  const v = C.dayView(S.state, S.day);
  renderDayNav(); renderNow(); renderToday(v);
  if (S.tab === 'week') renderWeek();
  if (S.tab === 'habits') renderHabits();
  if (S.tab === 'notes') renderNotes();
  if (S.tab === 'data') renderData();
  say(`${C.dayLabel(S.day)}: ${v.tasksDone} of ${v.tasks.length} tasks, checklist ${v.checkDone} of ${v.check.length}, habits ${v.habitsDone} of ${v.habits.length}.${S.demo ? ' Example plan.' : ''}`);
  S.ready = true;
  try { if (O && O.ready) O.ready(); } catch (_) { /* the veil lifts by itself */ }
}

// ------------------------------------------------------------------------------------------------ actions
function doExport() {
  const text = C.exportText(S.state, Date.now()), name = C.exportName(S.today);
  try {
    const url = URL.createObjectURL(new Blob([text], { type: 'application/json' })), a = document.createElement('a');
    a.href = url; a.download = name; document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 4000);
    say(`Exported ${name}. Keep it somewhere safe.`);
  } catch (_) { say('Export did not work on this browser. Copy the text from the import box instead.'); $('impText').value = text; }
}
function doImport() {
  const r = C.parseImport($('impText').value), msg = $('impMsg');
  if (!r.ok) { msg.textContent = r.error; say(r.error); return; }
  if (!S.demo) { try { localStorage.setItem(C.STORE_KEY + '.backup', JSON.stringify(S.state)); } catch (_) { /* nothing */ } }
  S.state = r.state; S.demo = false; S.saveOk = null; $('noteIn').dataset.day = '';
  save(); render();
  const c = r.counts, m = `Imported ${c.tasks} tasks, ${c.habits} habits and ${c.notes} notes.`;
  $('impMsg').textContent = m; $('impText').value = ''; say(m);
}
function startPlan() {
  S.demo = false; S.state = C.blankState(); $('noteIn').dataset.day = '';
  save(); setTab('today'); say('Your plan is ready. It is saved on this phone.');
}

function wire() {
  for (const id of TABS) $('tab-' + id).addEventListener('click', () => setTab(id));
  $('dayPrev').addEventListener('click', () => { S.day = C.addDays(S.day, -1); render(); });
  $('dayNext').addEventListener('click', () => { S.day = C.addDays(S.day, 1); render(); });
  $('dayToday').addEventListener('click', () => { S.day = S.today; render(); });
  $('weekPrev').addEventListener('click', () => { S.day = C.addDays(S.day, -7); render(); });
  $('weekNext').addEventListener('click', () => { S.day = C.addDays(S.day, 7); render(); });
  $('startBtn').addEventListener('click', startPlan);
  $('taskForm').addEventListener('submit', (e) => { e.preventDefault(); const v = $('taskIn').value; if (!C.parseQuick(v).text) { say('Type the task first.'); return; } S.state && change((st) => C.addTask(st, v, S.day)); $('taskIn').value = ''; $('taskIn').focus(); });
  $('habitForm').addEventListener('submit', (e) => { e.preventDefault(); const v = $('habitIn').value; if (!v.trim()) { say('Type the habit first.'); return; } change((st) => C.addHabit(st, v)); $('habitIn').value = ''; });
  $('clForm').addEventListener('submit', (e) => { e.preventDefault(); const v = $('clIn').value; if (!v.trim()) { say('Type the line first.'); return; } change((st) => C.addChecklist(st, v)); $('clIn').value = ''; });
  $('noteIn').addEventListener('input', () => {
    C.setNote(S.state, S.day, $('noteIn').value); renderRecent(); clearTimeout(noteTimer); noteTimer = setTimeout(save, 300);
  });
  $('noteIn').addEventListener('blur', () => { clearTimeout(noteTimer); save(); });
  window.addEventListener('pagehide', () => { clearTimeout(noteTimer); save(); });
  $('expBtn').addEventListener('click', doExport);
  $('impBtn').addEventListener('click', doImport);
  $('impFile').addEventListener('change', () => {
    const f = $('impFile').files && $('impFile').files[0]; if (!f) return;
    const fr = new FileReader();
    fr.onload = () => { $('impText').value = String(fr.result || ''); $('impMsg').textContent = `${f.name} is loaded. Tap Import to use it.`; say('File loaded. Tap Import to use it.'); };
    fr.onerror = () => { $('impMsg').textContent = 'That file could not be read.'; };
    fr.readAsText(f);
    $('impFile').value = '';
  });
  $('resetBtn').addEventListener('click', () => { if (armed('reset')) { S.demo = false; S.state = C.blankState(); $('noteIn').dataset.day = ''; save(); render(); say('The plan is blank again.'); } });
  document.addEventListener('visibilitychange', () => { if (!document.hidden) render(); });
}

async function boot() {
  const q = new URLSearchParams(location.search);
  S.forced = q.get('demo') === '1';
  const at = q.get('at'); if (at) { const d = new Date(at); if (Number.isFinite(d.getTime())) S.fixedNow = d; }
  S.today = C.etParts(nowDate()).day; S.day = S.today;
  const saved = S.forced ? null : loadSaved();
  if (saved) { S.state = saved; S.demo = false; }
  else {
    S.fixture = await getJSON('./fixture.json');
    S.state = C.buildDemo(S.fixture, S.today); S.demo = true;
    $('demoNote').textContent = (S.fixture && S.fixture.note) || 'Example plan, not real. Tap Start my plan to begin with your own.';
  }
  wire();
  render();
  setInterval(() => { if (!document.hidden) { renderNow(); renderDayNav(); } }, 30000);
}
window.PLANNER = { S, C, ready: () => S.ready, render, setTab };
boot().catch((e) => { say('Something went wrong: ' + (e && e.message ? e.message : e)); try { if (O && O.fail) O.fail('Planner could not start'); } catch (_) { /* nothing */ } });
