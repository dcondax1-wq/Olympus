"""PLANNER, the OLYMPUS day and week planner (tools/web_public/planner/, AGORA look, 2026-11-10; rebuilt after the old 'planner-backup' branch was lost).

  a. static: the files, the kit lines, the AGORA look, no markup from data, no network except fixture.json, the Jarvis card, the manifest, the DEMO fixture, the page order
  b. the maths in node (plannercore.js): New York days and weeks, the trading windows (DST, weekend), quick-add parsing, hostile input, every change, views, streaks, export / import, demo, the Jarvis summary
  c. Chromium 390 x 844 (and 375 x 667): DEMO when empty, Start my plan, add / tick / move / delete tasks, checklist, habits, week, notes, Export and Import (file, paste, bad file), reload keeps everything,
     corrupt storage, weekend, LITE and reduced motion, every tap >= 44 px, no sideways scroll, no console error, nothing off the page's origin
    python -X utf8 -m tests.test_planner_page            (--static: parts a and b only)
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import agora_kit as AK  # noqa: E402

APP, NAME = "planner", "Planner"
check = AK.check
KEY = "planner.agora.v1"
MON = "?at=2026-11-09T14:41:00Z"   # Monday 09:41 New York


def test_static():
    AK.static_kit(APP, NAME, reads=(), storage="own")
    d = os.path.join(AK.WEB, APP)
    html, js, core = (AK.read(os.path.join(d, n)) for n in ("index.html", "planner.js", "plannercore.js"))
    check("a. the page order: demo bar, tabs (Today, Week, Habits, Notes, Data), the day picker, then the panels",
          html.index('id="demoBar"') < html.index('id="tabs"') < html.index('id="dayNav"') < html.index('id="p-today"') < html.index('id="p-week"') < html.index('id="p-habits"') < html.index('id="p-notes"') < html.index('id="p-data"'))
    check("a. Today has the trading windows, the pre-session checklist, tasks and habits; Data has Export and Import",
          all(x in html for x in ('id="nowCard"', 'id="checkCard"', 'id="taskCard"', 'id="habitCard"', 'id="expBtn"', 'id="impBtn"', 'id="impFile"', 'id="impText"')))
    check("a. storage is the phone's localStorage only, always in try / catch; no cookie, no sessionStorage, no IndexedDB",
          "localStorage.setItem" in js and "planner.agora.v1" in core and "document.cookie" not in js and "sessionStorage" not in js and "indexedDB" not in js and js.count("try {") >= 6)
    check("a. the trading windows are the strategy's: entries 02:00, last entry 15:30, bot flat 15:55 (all New York time)", all(x in core for x in ("'02:00'", "'15:30'", "'15:55'")) and "America/New_York" in core)
    fx = json.loads(AK.read(os.path.join(d, "fixture.json")))
    check("a. the fixture has a checklist, tasks today and later, habits with history and notes (so the DEMO is never blank)",
          len(fx["checklist"]) >= 5 and any(t["off"] == 0 for t in fx["tasks"]) and any(t["off"] > 0 for t in fx["tasks"]) and len(fx["habits"]) >= 2 and fx["notes"])


HARNESS = r"""
import(process.argv[2]).then((C) => {
  const o = {};
  o.days = [C.addDays('2026-11-09', -1), C.addDays('2026-02-28', 1), C.addDays('2026-12-31', 1), C.addDays('2028-02-28', 1), C.dow('2026-11-09'), C.weekStart('2026-11-15'), C.weekStart('2026-11-09'), C.weekDays('2026-11-12'), C.isWeekend('2026-11-14'), C.isWeekend('2026-11-13'),
    C.validDay('2026-02-30'), C.validDay('2026-13-01'), C.validDay('x'), C.validDay('2026-11-09'), C.dayLabel('2026-11-09'), C.dayLabel('2026-01-01')];
  const at = (s) => { const x = C.sessionState(new Date(s)); return [x.id, x.hhmm, x.entries, x.day, x.pct]; };
  o.clock = { prep: at('2026-11-09T06:59:00Z'), open: at('2026-11-09T07:00:00Z'), ny: at('2026-11-09T14:41:00Z'), last: at('2026-11-09T20:30:00Z'), wind: at('2026-11-09T20:40:00Z'), flat: at('2026-11-09T21:00:00Z'), done: at('2026-11-09T21:10:00Z'), night: at('2026-11-10T03:00:00Z'),
    sat: at('2026-11-14T15:00:00Z'), sun: at('2026-11-15T15:00:00Z'), dst: at('2026-03-09T06:00:00Z'), edt: at('2026-10-27T13:41:00Z'), late: at('2026-11-10T08:30:00Z') };
  o.next = [C.sessionState(new Date('2026-11-09T14:41:00Z')).nextText, C.sessionState(new Date('2026-11-09T06:00:00Z')).nextText, C.sessionState(new Date('2026-11-14T15:00:00Z')).nextText];
  o.dur = [C.duration(5), C.duration(60), C.duration(349), C.duration(1920), C.duration(null), C.duration(-3)];
  o.quick = [C.parseQuick('Review levels 09:30'), C.parseQuick('9:05 call the broker'), C.parseQuick('  Pay   bill   @14:00 '), C.parseQuick('Ratio 3:99 is not a time'), C.parseQuick('25:00 nope'), C.parseQuick('   '), C.parseQuick(null)];
  // hostile input
  const bad = C.normalise({ checklist: [null, 5, { text: '  ' }, { id: 'a b!', text: 'ok  line' }, { id: 'c1', text: 'dup id?' }, { id: 'c1', text: 'again' }], tasks: [{ text: 'x', day: '2026-02-30' }, { text: 'good', day: '2026-11-09', done: 'yes', slot: '9:30' }, { text: 'good2', day: '2026-11-09', done: true, slot: '09:30' }, 'str', { text: 'y'.repeat(500), day: '2026-11-10' }],
    habits: [{ name: 'H' }, { name: '' }, { id: 'h1', name: 'dup' }], checks: { '2026-11-09': { c1: true, zzz: true, c2: 'no' }, bad: { c1: true } }, habitLog: { '2026-11-09': { h1: true, nope: true } }, notes: { '2026-11-09': 'hello', '2026-11-10': '   ', x: 'y' }, updated: 'soon' });
  o.bad = { cl: bad.checklist.map((c) => c.id + ':' + c.text), tasks: bad.tasks.map((t) => [t.text.length, t.done, t.slot]), habits: bad.habits.map((x) => x.id), checks: bad.checks, hl: bad.habitLog, notes: bad.notes, upd: bad.updated };
  o.nulls = [C.normalise(null), C.normalise([]), C.normalise('x'), C.normalise({}).tasks.length];
  // changes
  const st = C.blankState();
  const t1 = C.addTask(st, 'Review levels 09:30', '2026-11-09'), t2 = C.addTask(st, 'Call', '2026-11-09'), t3 = C.addTask(st, 'Early 08:00', '2026-11-09');
  o.add = [t1.id, t1.slot, t2.slot, C.addTask(st, '   ', '2026-11-09'), C.addTask(st, 'x', 'bad')];
  C.toggleTask(st, t2.id);
  o.order = C.dayView(st, '2026-11-09').tasks.map((t) => t.text + (t.done ? '*' : ''));
  C.moveTask(st, t1.id, C.addDays(t1.day, 1));
  o.moved = [C.dayView(st, '2026-11-09').tasks.length, C.dayView(st, '2026-11-10').tasks.length];
  o.rm = [C.removeTask(st, t3.id), C.removeTask(st, 'nope'), st.tasks.length];
  o.ck = [C.toggleCheck(st, '2026-11-09', 'c1'), C.toggleCheck(st, '2026-11-09', 'c1'), Object.keys(st.checks).length, C.toggleCheck(st, '2026-11-09', 'zzz'), C.toggleCheck(st, 'bad', 'c1')];
  C.toggleCheck(st, '2026-11-09', 'c2');
  o.ha = [C.toggleHabit(st, '2026-11-09', 'h1'), C.toggleHabit(st, '2026-11-08', 'h1'), C.toggleHabit(st, '2026-11-07', 'h1'), C.toggleHabit(st, '2026-11-05', 'h1')];
  o.streak = [C.streak(st, 'h1', '2026-11-09'), C.streak(st, 'h1', '2026-11-10'), C.streak(st, 'h1', '2026-11-06'), C.streak(st, 'h2', '2026-11-09')];
  C.setNote(st, '2026-11-09', 'My rule'); C.setNote(st, '2026-11-08', '  ');
  o.note = [st.notes['2026-11-09'], Object.keys(st.notes).length, C.recentNotes(st, 5).length];
  const nc = C.addChecklist(st, 'Extra line'), nh = C.addHabit(st, 'Read');
  o.lists = [nc.id, nh.id, C.addChecklist(st, ' '), C.addHabit(st, ''), st.checklist.length, st.habits.length];
  C.toggleCheck(st, '2026-11-09', nc.id); C.toggleHabit(st, '2026-11-09', nh.id);
  C.removeChecklist(st, nc.id); C.removeHabit(st, nh.id);
  o.cleaned = [st.checklist.length, st.habits.length, JSON.stringify(st.checks['2026-11-09']), JSON.stringify(st.habitLog['2026-11-09'])];
  const v = C.dayView(st, '2026-11-09');
  o.view = [v.checkDone, v.check.length, v.habitsDone, v.habits.length, v.habits[0].streak, v.tasksDone, v.tasks.length, v.note, C.dayScore(st, '2026-11-09'), C.dayScore(C.normalise({ checklist: [], habits: [] }), '2026-11-09')];
  const wv = C.weekView(st, '2026-11-12', '2026-11-09'), wt = C.weekTotals(wv, '2026-11-09');
  o.week = [wv.map((r) => r.label + r.num).join(' '), wv.findIndex((r) => r.today), wv.filter((r) => r.weekend).length, wv[0].tasks, wv[1].tasks, wt.tasks, wt.done, wt.avg];
  o.hw = C.habitWeek(st, 'h1', '2026-11-12').map((x) => (x.done ? 1 : 0)).join('');
  // export / import
  const text = C.exportText(st, 1793394000000), back = C.parseImport(text);
  o.rt = [back.ok, JSON.stringify(back.state) === JSON.stringify(C.normalise(st)), JSON.parse(text).app, JSON.parse(text).exported, C.exportName('2026-11-09')];
  const bare = C.parseImport(JSON.stringify(st));
  o.imp = [bare.ok, C.parseImport('not json').ok, C.parseImport('{"a":1}').ok, C.parseImport('[1]').ok, C.parseImport('').ok, C.parseImport('﻿' + text).ok, C.parseImport('{"tasks":[]}').state.checklist.length, C.parseImport('{"tasks":[]}').counts.tasks];
  o.errs = [C.parseImport('not json').error, C.parseImport('{"a":1}').error];
  // demo
  const fx = { checklist: ['One', 'Two'], checkedToday: [0, 9], tasks: [{ text: 'T', off: 1, done: true, slot: '08:15' }, { text: 'bad', off: 'x' }, null], habits: [{ name: 'H', hits: [0, 2, 'x'] }], notes: [{ off: -1, text: 'n' }, { off: 'a', text: 'z' }] };
  const dm = C.buildDemo(fx, '2026-11-09');
  o.demo = [dm.checklist.length, JSON.stringify(dm.checks), dm.tasks.map((t) => t.day + t.slot + t.done), JSON.stringify(dm.habitLog), JSON.stringify(dm.notes), C.buildDemo(null, '2026-11-09').checklist.length, C.buildDemo({}, '2026-11-09').habits.length, C.buildDemo(fx, 'x').tasks.length];
  const tsum = C.todaySummary(st, '2026-11-09', 5), tsw = C.todaySummary(st, '2026-11-14', 5);
  o.sum = [tsum.v, tsum.day, tsum.events.length, tsum.events[0].start, tsum.tasks.length, tsum.tasks[0].due, tsw.events.length, tsum.updated];
  console.log(JSON.stringify(o));
});
"""


def test_maths():
    o = AK.node(APP, HARNESS)
    if o is None:
        check("b. node is not installed: maths skipped", True)
        return
    check("b. no error in the harness", "_error" not in o, o.get("_error"))
    if "_error" in o:
        return
    dy = o["days"]
    check("b. day maths without time zones: previous day, 28 Feb, new year, leap year; weekday (Mon = 1); Monday of a Sunday and of a Monday; the week Mon to Sun",
          dy[:7] == ["2026-11-08", "2026-03-01", "2027-01-01", "2028-02-29", 1, "2026-11-09", "2026-11-09"] and dy[7] == ["2026-11-09", "2026-11-10", "2026-11-11", "2026-11-12", "2026-11-13", "2026-11-14", "2026-11-15"], dy[:8])
    check("b. weekend flags and day validation (no 30 Feb, no month 13, no junk); labels 'Mon 9 Nov', 'Thu 1 Jan'", dy[8:] == [True, False, False, False, False, True, "Mon 9 Nov", "Thu 1 Jan"], dy[8:])
    c = o["clock"]
    check("b. 01:59 ET is pre-session, 02:00 entries open, 09:41 entries (27% of the way), 15:30 wind-down starts, 15:55 flat, 16:10 day over",
          c["prep"][:3] == ["prep", "01:59", False] and c["open"][:3] == ["entries", "02:00", True] and c["ny"] == ["entries", "09:41", True, "2026-11-09", 55] and c["wind"][0] == "winddown" and c["last"][0] == "winddown" and c["flat"][0] == "flat" and c["done"][0] == "done", c)
    check("b. the weekend is closed (no entries); a late night after midnight ET is the next day (08:30Z on 11-10 is 03:30 Tuesday, 03:00Z on 11-10 is 22:00 Monday night)",
          c["sat"][:3] == ["closed", "10:00", False] and c["sun"][0] == "closed" and c["late"][3] == "2026-11-10" and c["late"][0] == "entries" and c["night"][3] == "2026-11-09" and c["night"][0] == "done", (c["sat"], c["late"], c["night"]))
    check("b. New York time through the clock change: 06:00Z on 2026-03-09 is 02:00 EDT, 13:41Z on 2026-10-27 is 09:41 EDT", c["dst"][:2] == ["entries", "02:00"] and c["edt"][:2] == ["entries", "09:41"], (c["dst"], c["edt"]))
    check("b. the next-step sentences: 'Last entry at 15:30 ET, in 5 h 49 min.', 'Entries open at 02:00 ET, in 1 h 0 min.' at 01:00; the weekend sentence",
          o["next"][0] == "Last entry at 15:30 ET, in 5 h 49 min." and o["next"][1] == "Entries open at 02:00 ET, in 1 h 0 min." and "weekend" in o["next"][2], o["next"])
    check("b. durations: 5 min, 1 h 0 min, 5 h 49 min, 1 day 8 h, empty for junk", o["dur"] == ["5 min", "1 h 0 min", "5 h 49 min", "1 day 8 h", "", ""], o["dur"])
    q = o["quick"]
    check("b. quick add finds a time: 'Review levels 09:30', '9:05 call the broker', '@14:00'; 3:99 and 25:00 are not times; empty and null are safe",
          q[0] == {"text": "Review levels", "slot": "09:30"} and q[1] == {"text": "call the broker", "slot": "09:05"} and q[2] == {"text": "Pay bill", "slot": "14:00"} and q[3]["slot"] == "" and q[4]["slot"] == "" and q[5] == {"text": "", "slot": ""} and q[6]["text"] == "", q)
    b = o["bad"]
    check("b. hostile input never throws: junk rows dropped, ids made unique and safe, text trimmed to 200, a bad slot or day removed, unknown ids and bad dates dropped from checks, logs and notes",
          b["cl"] == ["ab:ok line", "c1:dup id?", "c3:again"] and b["tasks"] == [[4, False, ""], [5, True, "09:30"], [200, False, ""]] and b["habits"] == ["h1", "h2"] and b["checks"] == {"2026-11-09": {"c1": True}} and b["hl"] == {"2026-11-09": {"h1": True}}
          and b["notes"] == {"2026-11-09": "hello"} and b["upd"] == 0, b)
    check("b. normalise(null / [] / 'x') is null, an empty object gives an empty plan", o["nulls"] == [None, None, None, 0], o["nulls"])
    check("b. adding tasks: ids, the time is taken out of the text, empty text and a bad day are refused; open tasks sort by time, done ones last",
          o["add"] == ["t1", "09:30", "", None, None] and o["order"] == ["Early", "Review levels", "Call*"], (o["add"], o["order"]))
    check("b. move a task to the next day; delete a task; deleting an unknown id changes nothing", o["moved"] == [2, 1] and o["rm"] == [True, False, 2], (o["moved"], o["rm"]))
    check("b. checklist ticks flip on and off, an emptied day is removed, unknown ids and bad days are refused", o["ck"] == [True, False, 0, None, None], o["ck"])
    check("b. habit streaks: Mon, Sun, Sat in a row = 3; the day after counts from yesterday; from Fri 6 Nov back only Thu 5 counts = 1; an unknown habit is 0", o["ha"] == [True, True, True, True] and o["streak"] == [3, 3, 1, 0], (o["ha"], o["streak"]))
    check("b. notes: saved text kept as typed, a blank note removes it, recent notes newest first", o["note"] == ["My rule", 1, 1], o["note"])
    check("b. adding and removing checklist lines and habits (ids never clash, blank refused); removing one also clears its ticks", o["lists"] == ["c7", "h4", None, None, 7, 4] and o["cleaned"] == [6, 3, '{"c2":true}', '{"h1":true}'], (o["lists"], o["cleaned"]))
    check("b. the day view: counts, a habit streak, the note, the score = everything done / everything planned (null when nothing is planned)",
          o["view"][:8] == [1, 6, 1, 3, 3, 1, 1, "My rule"] and o["view"][8] == round(100 * 3 / 10) and o["view"][9] is None, o["view"])
    check("b. the week: Mon to Sun with today marked, two weekend days, tasks per day, totals (tasks done / planned, average score of the days up to today)",
          o["week"][0] == "Mon9 Tue10 Wed11 Thu12 Fri13 Sat14 Sun15" and o["week"][1:5] == [0, 2, 1, 1] and o["week"][5:7] == [2, 1] and o["week"][7] == 30 and o["hw"] == "1000000", (o["week"], o["hw"]))
    check("b. export is a wrapped file (app planner, v1, date) and importing it gives back exactly the same plan; a bare plan, a file with a BOM and a plan with only tasks import too",
          o["rt"][:3] == [True, True, "planner"] and o["rt"][3].startswith("2026-") and o["rt"][4] == "planner-2026-11-09.json" and o["imp"][0] and o["imp"][5] and o["imp"][6] == 6 and o["imp"][7] == 0, o["rt"])
    check("b. bad files are refused with a plain sentence: not JSON, no plan in it, a list, empty", o["imp"][1:5] == [False, False, False, False] and "not a Planner file" in o["errs"][0] and "no Planner plan" in o["errs"][1], (o["imp"], o["errs"]))
    check("b. the demo: relative days, ticks only where the index exists, habit history, notes, junk rows ignored, an empty fixture still gives a plan, a bad day gives a blank plan",
          o["demo"][0] == 2 and o["demo"][1] == '{"2026-11-09":{"c1":true}}' and o["demo"][2] == ["2026-11-1008:15true"] and o["demo"][3] == '{"2026-11-09":{"h1":true},"2026-11-07":{"h1":true}}'
          and o["demo"][4] == '{"2026-11-08":"n"}' and o["demo"][5] == 6 and o["demo"][6] == 3 and o["demo"][7] == 0, o["demo"])
    check("b. the summary for other OLYMPUS pages: v1, the day, the four trading windows on a weekday and none at the weekend, the day's tasks with their due day",
          o["sum"] == [1, "2026-11-09", 4, "02:00", 1, "2026-11-09", 0, 5], o["sum"])


# ------------------------------------------------------------------------------------------------ c. Chromium
def rd(p, key=KEY):
    return p.evaluate("(k) => { try { return localStorage.getItem(k); } catch (e) { return null; } }", key)


def state(p):
    t = rd(p)
    return json.loads(t) if t else None


def tab(p, name):
    p.click(f"#tab-{name}")
    p.wait_for_timeout(150)


def test_page():
    try:
        import playwright  # noqa: F401
    except ImportError:
        check("c. page tests skipped: no Playwright", True)
        return
    srv, origin = AK.serve()
    try:
        with AK.browser() as br:
            # ---- 1. nothing saved: the DEMO plan, never blank
            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, APP, MON)
            d = p.evaluate("""() => ({ demo: !document.querySelector('#demo').hidden, bar: !document.querySelector('#demoBar').hidden, checks: document.querySelectorAll('#checkList .rowbtn').length, tasks: document.querySelectorAll('#taskList .rowbtn').length,
              habits: document.querySelectorAll('#habitList .rowbtn').length, clock: document.querySelector('#clkTime').textContent, phase: document.querySelector('#clkPhase').textContent, win: document.querySelector('#winKv').textContent,
              title: document.querySelector('#dayTitle').textContent, sub: document.querySelector('#daySub').textContent, h1: document.querySelectorAll('h1').length, font: getComputedStyle(document.querySelector('h1')).fontFamily,
              bg: getComputedStyle(document.body).backgroundColor, theme: document.documentElement.dataset.theme, status: document.querySelector('#status').textContent, sum: document.querySelector('#checkSum').textContent,
              note: document.querySelector('#demoNote').textContent, fixture: performance.getEntriesByType('resource').filter((r) => /fixture\\.json/.test(r.name)).length })""")
            check("c. nothing saved: the DEMO chip and the 'example plan' bar, six checklist lines, today's example tasks and habits, never blank",
                  d["demo"] and d["bar"] and d["checks"] == 6 and d["tasks"] == 3 and d["habits"] == 3 and "not real" in d["note"] and d["fixture"] == 1, d)
            check("c. Monday 09:41 New York: clock, 'Entries open', the four windows (02:00, 15:30, 15:55, 16:10 ET), the day picker says Mon 9 Nov / Today",
                  d["clock"] == "09:41" and d["phase"] == "Entries open" and all(x in d["win"] for x in ("02:00 ET", "15:30 ET", "15:55 ET", "16:10 ET")) and d["title"] == "Mon 9 Nov" and d["sub"] == "Today", d)
            check("c. the AGORA look: a serif title, a warm dark body (not black), data-theme agora, one h1, a spoken status line", any(f in d["font"] for f in ("Palatino", "Iowan", "Georgia")) and d["bg"] != "rgb(0, 0, 0)" and d["theme"] == "agora" and d["h1"] == 1 and "Mon 9 Nov" in d["status"] and d["sum"] == "3 of 6 done", d)
            AK.shot(p, "planner-demo")
            t = AK.taps(p)
            check("c. every tap target is at least 44 x 44 px", not t, t[:5])
            check("c. no sideways scroll; Jarvis's bottom-right corner is free", AK.no_sideways(p) and not AK.corner(p))
            p.click("#checkList .rowbtn >> nth=3")
            on = p.get_attribute("#checkList .rowbtn >> nth=3", "aria-checked")
            check("c. in the demo you can tick things but nothing is saved (storage stays empty)", on == "true" and rd(p) is None and rd(p, "planner.today.v1") is None, (on, rd(p)))
            check("c. no console error, no page error, nothing requested off the page's origin", not errs and not off, (errs[:3], off[:3]))
            # ---- 2. Start my plan -> real, saved, still not blank
            p.click("#startBtn")
            p.wait_for_timeout(200)
            s = state(p)
            r = p.evaluate("() => ({ demo: !document.querySelector('#demo').hidden, bar: !document.querySelector('#demoBar').hidden, checks: document.querySelectorAll('#checkList .rowbtn').length, ticked: document.querySelectorAll('#checkList [aria-checked=true]').length, tasks: document.querySelectorAll('#taskList .rowbtn').length, empty: document.querySelector('#taskList').textContent })")
            check("c. Start my plan: no DEMO chip, a saved blank plan with the starter checklist and three habits, an empty-task hint instead of a blank card",
                  not r["demo"] and not r["bar"] and r["checks"] == 6 and r["ticked"] == 0 and r["tasks"] == 0 and "No tasks" in r["empty"] and s and len(s["checklist"]) == 6 and len(s["habits"]) == 3 and s["tasks"] == [], (r, s and s.keys()))
            # ---- 3. tasks
            p.fill("#taskIn", "Review levels 09:30")
            p.click("#taskAdd")
            p.fill("#taskIn", "Call the broker")
            p.press("#taskIn", "Enter")
            p.fill("#taskIn", "   ")
            p.press("#taskIn", "Enter")
            p.wait_for_timeout(150)
            rows = p.evaluate("() => [...document.querySelectorAll('#taskList .row')].map((r) => r.querySelector('.rowbtn').textContent)")
            check("c. add a task with a button and with Enter; '09:30' becomes the task's time and sorts first; an empty task is refused with a plain message",
                  len(rows) == 2 and rows[0].startswith("09:30") and "Review levels" in rows[0] and "Call the broker" in rows[1] and "Type the task first" in p.inner_text("#status"), rows)
            p.click("#taskList .rowbtn >> nth=1")
            s = state(p)
            check("c. tick a task: it moves to the bottom, shows as done and is saved; the 'planner.today.v1' summary for other pages is written",
                  [t["done"] for t in s["tasks"]] == [False, True] and p.get_attribute("#taskList .rowbtn >> nth=1", "aria-checked") == "true" and json.loads(rd(p, "planner.today.v1"))["tasks"][0]["due"] == "2026-11-09", s["tasks"])
            p.click("#taskList [aria-label^='Move to the next day'] >> nth=0")
            p.wait_for_timeout(150)
            check("c. 'move to the next day' takes it off today; tomorrow shows it", len(p.query_selector_all("#taskList .rowbtn")) == 1, state(p)["tasks"])
            p.click("#dayNext")
            p.wait_for_timeout(150)
            check("c. the day picker goes to Tue 10 Nov (a day ahead) and shows the moved task; the trading windows apply; 'Back to today' returns",
                  p.inner_text("#dayTitle") == "Tue 10 Nov" and p.inner_text("#daySub") == "A day ahead" and "Review levels" in p.inner_text("#taskList") and "02:00 ET" in p.inner_text("#winKv") and p.is_hidden("#clkTime"), p.inner_text("#taskList"))
            p.click("#dayToday")
            p.wait_for_timeout(100)
            p.click("#taskList [aria-label^='Delete'] >> nth=0")
            p.wait_for_timeout(100)
            check("c. delete a task", len(state(p)["tasks"]) == 1 and "Review levels" in json.dumps(state(p)["tasks"]), state(p)["tasks"])
            # ---- 4. checklist + habits on Today
            p.click("#checkList .rowbtn >> nth=0")
            p.click("#habitList .rowbtn >> nth=0")
            p.wait_for_timeout(150)
            s = state(p)
            check("c. tick a checklist line and a habit: the counter says 1 of 6, the habit shows '1 day in a row', both are saved",
                  p.inner_text("#checkSum") == "1 of 6 done" and "1 day in a row" in p.inner_text("#habitList") and s["checks"] == {"2026-11-09": {"c1": True}} and s["habitLog"] == {"2026-11-09": {"h1": True}}, (p.inner_text("#checkSum"), s["checks"]))
            # ---- 5. week
            tab(p, "week")
            w = p.evaluate("() => ({ rows: document.querySelectorAll('#weekList .rowbtn').length, today: [...document.querySelectorAll('#weekList .rowbtn')].findIndex((b) => b.classList.contains('today')), sub: document.querySelector('#weekSub').textContent, tiles: document.querySelector('#weekTiles').textContent, first: document.querySelector('#weekList .rowbtn').textContent, sat: document.querySelectorAll('#weekList .rowbtn.weekend').length, dayNavHidden: document.querySelector('#dayNav').hidden })")
            check("c. the Week tab: seven days Mon to Sun with today marked, the week range, 'Tasks done 0 of 1', the weekend marked 'no trading', the day picker hidden",
                  w["rows"] == 7 and w["today"] == 0 and w["sub"] == "Mon 9 Nov to Sun 15 Nov" and "0 of 1" in w["tiles"] and "0 of 0 tasks" in w["first"] and "1 of 6 checks" in w["first"] and w["sat"] == 2 and w["dayNavHidden"], w)
            t = AK.taps(p)
            check("c. Week: every tap >= 44 px, no sideways scroll", not t and AK.no_sideways(p), t[:4])
            p.click("#weekNext")
            p.wait_for_timeout(100)
            check("c. next week: Mon 16 Nov to Sun 22 Nov, empty days say 0 of 0", p.inner_text("#weekSub") == "Mon 16 Nov to Sun 22 Nov" and "0 of 0 tasks" in p.inner_text("#weekList"), p.inner_text("#weekSub"))
            p.click("#weekPrev")
            p.click("#weekList .rowbtn >> nth=2")
            p.wait_for_timeout(150)
            check("c. tapping a day opens it on Today (Wed 11 Nov)", p.get_attribute("#tab-today", "aria-selected") == "true" and p.inner_text("#dayTitle") == "Wed 11 Nov", p.inner_text("#dayTitle"))
            p.click("#dayToday")
            # ---- 6. habits tab
            tab(p, "habits")
            p.click("#habitCards .hday >> nth=0")
            p.wait_for_timeout(100)
            hb = p.evaluate("() => ({ cards: document.querySelectorAll('#habitCards .ag-card').length, days: document.querySelectorAll('#habitCards .card:first-child .hday').length, pressed: document.querySelectorAll('#habitCards .card:first-child .hday[aria-pressed=true]').length, text: document.querySelector('#habitCards .card:first-child .note').textContent })")
            check("c. Habits: a card per habit with Mon to Sun buttons; tapping Monday on a done habit unticks it and the streak resets", hb["cards"] == 3 and hb["days"] == 7 and hb["pressed"] == 0 and "No streak" in hb["text"], hb)
            p.click("#habitCards .hday >> nth=0")
            p.fill("#habitIn", "Read 20 minutes")
            p.press("#habitIn", "Enter")
            p.wait_for_timeout(100)
            check("c. add a habit", len(state(p)["habits"]) == 4 and p.locator("#habitCards .ag-card").count() == 4, state(p)["habits"])
            p.click("#habitCards .card:last-child >> text=Remove")
            first = p.inner_text("#habitCards .card:last-child .hcard-top button")
            n_after_first = len(state(p)["habits"])
            p.click("#habitCards .card:last-child .hcard-top button")
            p.wait_for_timeout(100)
            check("c. removing a habit needs a second tap ('Tap again'); then it is gone", first == "Tap again" and n_after_first == 4 and len(state(p)["habits"]) == 3, (first, n_after_first))
            t = AK.taps(p)
            check("c. Habits: every tap >= 44 px, no sideways scroll", not t and AK.no_sideways(p), t[:4])
            # ---- 7. notes
            tab(p, "notes")
            p.fill("#noteIn", "One rule: wait for the sweep.\nStop beyond the extreme.")
            p.wait_for_timeout(500)
            check("c. Notes: typing saves the day's note and lists it under Recent notes", "wait for the sweep" in state(p)["notes"]["2026-11-09"] and "Mon 9 Nov" in p.inner_text("#recentList") and "of 4000" in p.inner_text("#noteCount"), state(p)["notes"])
            p.click("#dayPrev")
            p.wait_for_timeout(100)
            check("c. another day has its own empty note box; Recent notes jumps back to the written one", p.input_value("#noteIn") == "" and "Sun 8 Nov" in p.inner_text("#noteH"), p.inner_text("#noteH"))
            p.click("#recentList .rowbtn >> nth=0")
            p.wait_for_timeout(100)
            check("c. ... and shows its text", "wait for the sweep" in p.input_value("#noteIn"), p.input_value("#noteIn"))
            t = AK.taps(p)
            check("c. Notes: every tap >= 44 px, no sideways scroll", not t and AK.no_sideways(p), t[:4])
            # ---- 8. reload: everything is still there (offline-first, no network for the plan)
            AK.open_app(p, origin, APP, MON)
            q = p.evaluate("() => ({ demo: !document.querySelector('#demo').hidden, tasks: document.querySelectorAll('#taskList .rowbtn').length, sum: document.querySelector('#checkSum').textContent, fixture: performance.getEntriesByType('resource').filter((r) => /fixture\\.json/.test(r.name)).length })")
            check("c. after a reload the saved plan is back (no DEMO, 1 of 6 checked, the Tuesday task kept) and the demo fixture is not even fetched", not q["demo"] and q["tasks"] == 0 and q["sum"] == "1 of 6 done" and q["fixture"] == 0, q)
            # ---- 9. Data: export, import
            tab(p, "data")
            check("c. Data: the export summary counts the plan, the storage line says saved on this phone", "1 task, 3 habits, 1 note and 6 checklist lines" in p.inner_text("#expSum") and "Saved on this phone" in p.inner_text("#stMsg"), p.inner_text("#expSum"))
            with p.expect_download() as dl:
                p.click("#expBtn")
            fn = dl.value.suggested_filename
            path = dl.value.path()
            exp = json.load(open(path, encoding="utf-8"))
            check("c. Export JSON downloads planner-2026-11-09.json: app planner, v1, the whole plan inside", fn == "planner-2026-11-09.json" and exp["app"] == "planner" and exp["v"] == 1 and len(exp["data"]["tasks"]) == 1 and exp["data"]["notes"], (fn, list(exp)))
            exp["data"]["tasks"].append({"id": "t9", "text": "From the file", "day": "2026-11-09", "done": False, "slot": "11:00"})
            exp["data"]["habits"] = [{"id": "h1", "name": "Only habit"}]
            p.set_input_files("#impFile", files=[{"name": "plan.json", "mimeType": "application/json", "buffer": json.dumps(exp).encode()}])
            p.wait_for_timeout(300)
            loaded = p.input_value("#impText")
            check("c. choosing a file loads it into the box and says to tap Import (nothing is replaced yet)", "From the file" in loaded and "Tap Import" in p.inner_text("#impMsg") and len(state(p)["tasks"]) == 1, p.inner_text("#impMsg"))
            p.click("#impBtn")
            p.wait_for_timeout(250)
            s = state(p)
            check("c. Import replaces the plan (2 tasks, 1 habit), says what it imported, keeps the old plan as a backup, clears the box",
                  len(s["tasks"]) == 2 and [h["name"] for h in s["habits"]] == ["Only habit"] and "Imported 2 tasks, 1 habits" in p.inner_text("#impMsg") and rd(p, KEY + ".backup") and len(json.loads(rd(p, KEY + ".backup"))["tasks"]) == 1 and p.input_value("#impText") == "", (p.inner_text("#impMsg"), s["tasks"]))
            p.fill("#impText", "this is not json")
            p.click("#impBtn")
            m1 = p.inner_text("#impMsg")
            p.fill("#impText", '{"hello": 1}')
            p.click("#impBtn")
            m2 = p.inner_text("#impMsg")
            check("c. a bad file is refused with a plain sentence and the plan is untouched", "not a Planner file" in m1 and "no Planner plan" in m2 and len(state(p)["tasks"]) == 2, (m1, m2))
            p.fill("#clIn", "Screens off by 18:00")
            p.press("#clIn", "Enter")
            p.wait_for_timeout(100)
            p.click("#clEdit .row:last-child button")
            lbl = p.inner_text("#clEdit .row:last-child button")
            p.click("#clEdit .row:last-child button")
            p.wait_for_timeout(100)
            check("c. the checklist can be edited: add a line, delete needs a second tap ('Sure?')", lbl == "Sure?" and len(state(p)["checklist"]) == 6, (lbl, len(state(p)["checklist"])))
            t = AK.taps(p)
            check("c. Data: every tap >= 44 px, no sideways scroll, the corner is free", not t and AK.no_sideways(p) and not AK.corner(p), (t[:4], AK.corner(p)))
            p.click("#resetBtn")
            armed_txt = p.inner_text("#resetBtn")
            p.click("#resetBtn")
            p.wait_for_timeout(100)
            check("c. Reset to a blank plan needs a second tap, then the plan is the starter plan again", "Tap again" in armed_txt and state(p)["tasks"] == [] and len(state(p)["habits"]) == 3, armed_txt)
            check("c. through all of it: no console error, nothing requested off the page's origin, no request except the page's own files", not errs and not off, (errs[:3], off[:3]))
            ctx.close()

            # ---- 10. corrupt storage never loses data: DEMO shows, the bad text is kept aside
            ctx, p, errs, seen, off = AK.page(br, origin, storage={KEY: "{not json"})
            AK.open_app(p, origin, APP, MON)
            kept = rd(p, KEY + ".bad")
            check("c. a corrupt saved plan falls back to the DEMO (never blank, no error) and the broken text is kept under '.bad'", p.is_visible("#demo") and kept == "{not json" and not errs, (kept, errs[:2]))
            ctx.close()

            # ---- 11. a saved plan from before is loaded as is; junk inside it is cleaned
            saved = json.dumps({"v": 1, "checklist": [{"id": "c1", "text": "Only line"}, 7], "tasks": [{"id": "t1", "text": "Saved task", "day": "2026-11-09", "done": False, "slot": "07:00"}, {"text": "bad day", "day": "nope"}], "habits": [], "notes": {"2026-11-09": "kept"}})
            ctx, p, errs, seen, off = AK.page(br, origin, storage={KEY: saved})
            AK.open_app(p, origin, APP, MON)
            v = p.evaluate("() => ({ demo: !document.querySelector('#demo').hidden, checks: document.querySelectorAll('#checkList .rowbtn').length, tasks: document.querySelector('#taskList').textContent, habits: document.querySelector('#habitList').textContent })")
            check("c. a saved plan: no DEMO, its one checklist line and its task show, the junk row is dropped, an empty habit list says so (not blank)", not v["demo"] and v["checks"] == 1 and "Saved task" in v["tasks"] and "07:00" in v["tasks"] and "bad day" not in v["tasks"] and "No habits" in v["habits"] and not errs, v)
            ctx.close()

            # ---- 12. the weekend
            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, APP, "?at=2026-11-14T15:00:00Z")
            w = p.evaluate("() => [document.querySelector('#clkPhase').textContent, document.querySelector('#clkNext').textContent, document.querySelector('#winKv').textContent, document.querySelector('#dayTitle').textContent]")
            check("c. Saturday: 'Weekend', 'does not trade', no windows, the planner still works (checklist and tasks are there)", w[0] == "Weekend" and "does not trade" in w[1] and "None at the weekend" in w[2] and w[3] == "Sat 14 Nov" and p.locator("#checkList .rowbtn").count() == 6 and not errs, w)
            ctx.close()

            # ---- 13. small phone, LITE, reduced motion: every tab
            ctx, p, errs, seen, off = AK.page(br, origin, w=375, h=667, reduced=True, lite=True)
            AK.open_app(p, origin, APP, MON + "&q=low")
            bad = []
            for name in ("today", "week", "habits", "notes", "data"):
                tab(p, name)
                tp = AK.taps(p)
                if tp or not AK.no_sideways(p):
                    bad.append((name, tp[:3]))
            check("c. 375 x 667 with LITE and reduced motion: every tab has no sideways scroll and every tap >= 44 px, no error", not bad and not errs, (bad, errs[:2]))
            ctx.close()
            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, APP, "?demo=1&" + MON[1:])
            check("c. ?demo=1 forces the example plan and never writes anything", p.is_visible("#demo") and rd(p) is None and not errs, errs[:2])
            ctx.close()
    finally:
        srv.shutdown()


if __name__ == "__main__":
    test_static()
    test_maths()
    if "--static" not in sys.argv:
        test_page()
    AK.finish()
