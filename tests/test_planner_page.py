"""PLANNER v2, the OLYMPUS planner (tools/web_public/planner/, AGORA look, 2026-11-10): calendar, projects and tasks, the trading day, habits, goals, focus timer, notes, search, export / import / .ics.

  a. static: the files, the kit lines, the AGORA look, no markup from data, reads only Pythia's events, home.json and the fixture, the documented storage keys, the Jarvis card, the manifest, the sundial scene
  b. the core in node (tests/planner_core_harness.cjs, 50+ checks): New York time and the clock change of Nov 1 2026, recurrence across it, the phrase parser (46 phrases), migrations from planner.agora.v1 and planner.v1,
     .ics, search, hostile input, lanes, steps, goals, habits and the heatmap, focus timer, reviews for Epilogue / Lyceum, market events, the bots' drawdown line, export / import, the demo
  c. Chromium 390 x 844 (and 375 x 667 with LITE and reduced motion): DEMO when empty, quick add, the sheets, calendar month / week / day, tasks and lanes, projects, habits, goals (Argo, read only), notes, focus, find,
     Export / Import / .ics, the migration from the two old keys (the old keys stay untouched), reload keeps everything, every tap >= 44 px, no sideways scroll, no console error, nothing off the page's origin
    python -X utf8 -m tests.test_planner_page            (--static: parts a and b only; AGORA_SHOTS=<dir> saves screenshots)
    node tests/planner_core_harness.cjs                   (part b alone)
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import agora_kit as AK  # noqa: E402

APP, NAME = "planner", "Planner"
check = AK.check
KEY = "planner.agora.v2"
MON = "?at=2026-11-09T14:41:00Z"   # Monday 09:41 New York
D = os.path.join(AK.WEB, APP)


def test_static():
    AK.static_kit(APP, NAME, reads=("../pythia/events.json", "../home.json"), storage="own")
    html, js, core, css, scene = (AK.read(os.path.join(D, n)) for n in ("index.html", "planner.js", "plannercore.js", "planner.css", "plannerscene.js"))
    order = ["demoBar", "qForm", "tabs", "p-today", "p-calendar", "p-tasks", "p-projects", "p-habits", "p-goals", "p-notes", "p-focus", "p-find", "p-data"]
    idx = [html.index(f'id="{i}"') for i in order]
    check("a. the page order: demo bar, quick add, the ten tabs, then the ten panels", idx == sorted(idx), idx)
    check("a. ten tabs: Today, Calendar, Tasks, Projects, Habits, Goals, Notes, Focus, Find, Data", all(f'id="tab-{t}"' in html for t in ("today", "calendar", "tasks", "projects", "habits", "goals", "notes", "focus", "find", "data")))
    check("a. the sheet (one editor for events, tasks, notes, projects, goals) is a dialog with a close button, and the header has the sundial canvas",
          'role="dialog"' in html and 'aria-modal="true"' in html and 'id="sheetX"' in html and 'id="scene"' in html)
    check("a. storage is the phone's localStorage only, always in try / catch; no cookie, no sessionStorage, no IndexedDB",
          "localStorage.setItem" in js and "planner.agora.v2" in core and "document.cookie" not in js and "sessionStorage" not in js and "indexedDB" not in js and js.count("try {") >= 6)
    keys = ("planner.agora.v2", "planner.agora.v1", "planner.v1", "planner.sessions.v1", "planner.today.v1", "planner.focus.v1", "argo.goals.v1")
    head = core.split("export const STORE_KEY")[0]
    check("a. every storage key is documented at the top of plannercore.js (the plan, the two old keys that are never touched, the Epilogue / Lyceum sessions key, the Jarvis summary, the focus timer, Argo's goals read only)",
          all(k in head for k in keys) and "NEVER changed or deleted" in head and "FOR EPILOGUE AND LYCEUM" in head, [k for k in keys if k not in head])
    check("a. the old keys are only ever read: no write or remove of planner.agora.v1, planner.v1 or argo.goals.v1 anywhere in the page",
          not re.search(r"lsSet\(\s*C\.(OLD_KEY|LEGACY_KEY|ARGO_KEY)|lsDel\(\s*C\.(OLD_KEY|LEGACY_KEY|ARGO_KEY)|removeItem\(\s*C\.(OLD_KEY|LEGACY_KEY|ARGO_KEY)", js) and "lsGet(C.ARGO_KEY)" in js and "lsGet(C.OLD_KEY)" in js and "lsGet(C.LEGACY_KEY)" in js)
    check("a. the trading windows are the strategy's: entries 02:00, last entry 15:30, bot flat 15:55, MFFU 16:10, the CME break; New York time by rule (America/New_York in the calendar file)",
          all(x in core for x in ("'02:00'", "'15:30'", "'15:55'", "'16:10'", "'17:00'")) and "America/New_York" in core and "dstRange" in core)
    check("a. Kairos' window names are used (Asia slot, London entries, New York morning / afternoon, No new trades, Flat time, CME break) and Pythia's event shape is read, not rewritten",
          all(x in core for x in ("Asia slot", "London entries", "New York morning", "New York afternoon", "No new trades", "Flat time", "CME break")) and "normMarket" in core and "events.json" in head)
    check("a. money wording: 'drawdown left $X of $max loss'", "drawdown left" in core and "max loss" in core)
    fx = json.loads(AK.read(os.path.join(D, "fixture.json")))
    check("a. the fixture has a checklist, events with repeats, projects, tasks (with steps, priorities and a Someday lane), habits with history, goals, notes with tags, a review, market events and example bot numbers (so the DEMO is never blank)",
          len(fx["checklist"]) >= 5 and any(e["repeat"] != "none" for e in fx["events"]) and len(fx["projects"]) >= 2 and any(t.get("steps") for t in fx["tasks"]) and any(t.get("lane") == "someday" for t in fx["tasks"]) and len(fx["habits"]) >= 2
          and fx["goals"] and fx["notes"] and fx["review"] and fx["market"] and fx["bots"]["accounts"])
    check("a. the sundial scene is a plain 2D canvas (no WebGL, no library), holds still when LITE or reduced motion, and never throws",
          "getContext('2d')" in scene and "webgl" not in scene.lower() and "requestAnimationFrame" not in scene and "lite" in scene and "reduced" in scene and "catch" in scene)
    check("a. the AGORA look in the CSS: the sheet respects reduced motion and LITE, safe areas, 44 px taps, no neon", "prefers-reduced-motion" in css and 'data-oly-lite="1"' in css and css.count("min-height: 44px") >= 8 and "safe-area-inset" in css)
    check("a. a Playwright-free reader can run the core: tests/planner_core_harness.cjs exists", os.path.isfile(os.path.join(os.path.dirname(os.path.abspath(__file__)), "planner_core_harness.cjs")))


def test_core():
    exe = shutil.which("node")
    if not exe:
        check("b. node is not installed: the core checks are skipped", True)
        return
    r = subprocess.run([exe, os.path.join(os.path.dirname(os.path.abspath(__file__)), "planner_core_harness.cjs")], capture_output=True, text=True, timeout=120)
    try:
        rows = json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:  # noqa: BLE001
        check("b. the core harness ran", False, (r.stdout + r.stderr)[-600:])
        return
    for name, ok, info in rows:
        check("b. " + name if not name[:2].strip(".").isdigit() else "b. " + name, ok, info)


# ------------------------------------------------------------------------------------------------ c. Chromium
def rd(p, key=KEY):
    return p.evaluate("(k) => { try { return localStorage.getItem(k); } catch (e) { return null; } }", key)


def state(p):
    t = rd(p)
    return json.loads(t) if t else None


def tab(p, name):
    p.click(f"#tab-{name}")
    p.wait_for_timeout(150)


def card(p, title):
    return p.locator("section.card", has=p.locator("h2", has_text=title)).first


def sheet_open(p):
    return p.is_visible("#sheet")


def act(p, label):
    p.locator("#sheetAct button", has_text=label).first.click()
    p.wait_for_timeout(200)


V1 = {"v": 1, "checklist": [{"id": "c1", "text": "Look at the news"}, {"id": "c2", "text": "Check the drawdown"}], "checks": {"2026-11-09": {"c1": True}},
      "tasks": [{"id": "t1", "text": "Saved task", "day": "2026-11-09", "done": False, "slot": "07:00"}, {"id": "t2", "text": "Done task", "day": "2026-11-06", "done": True, "slot": ""}, {"text": "bad day", "day": "2026-02-30"}],
      "habits": [{"id": "h1", "name": "Journal the day"}], "habitLog": {"2026-11-09": {"h1": True}, "2026-11-08": {"h1": True}}, "notes": {"2026-11-09": "One rule: wait for the sweep.", "2026-11-08": "Quiet day."}, "updated": 1793000000000}
LEGACY = {"events": [{"id": "a", "title": "Dentist", "date": "2026-11-12", "start": "09:30", "end": "10:15", "repeat": "weekly", "category": "health"}],
          "tasks": [{"id": "x", "title": "Pay the card", "date": "2026-11-11", "done": False, "priority": "high"}], "projects": [{"id": "pm", "name": "Money"}]}
HOME = {"live": {"model_state": "LIT is watching the 18:00 open. No trade yet today."}, "accounts": [{"id": "zlarior", "name": "Zlarior MFFU 50K", "eval": {"room": 1750, "mll": 2000}}, {"id": "atlas", "name": "ATLAS 25K", "room": 700, "mll": 1000}]}


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
            d = p.evaluate("""() => ({ demo: !document.querySelector('#demo').hidden, bar: !document.querySelector('#demoBar').hidden, clock: document.querySelector('#clkTime').textContent, phase: document.querySelector('#clkPhase').textContent,
              wins: document.querySelectorAll('.win').length, mrows: document.querySelectorAll('.mrow').length, bots: document.querySelector('.botbox').textContent, h1: document.querySelectorAll('h1').length, font: getComputedStyle(document.querySelector('h1')).fontFamily,
              bg: getComputedStyle(document.body).backgroundColor, theme: document.documentElement.dataset.theme, title: document.querySelector('#dayTitle').textContent, sub: document.querySelector('#daySub').textContent,
              cards: [...document.querySelectorAll('#v-today > .card > h2')].map((h) => h.textContent), rows: document.querySelectorAll('#v-today .rowbtn').length,
              scene: (() => { const c = document.querySelector('#scene'); const g = c.getContext('2d'); const px = g.getImageData(0, 0, c.width, c.height).data; let n = 0; for (let i = 3; i < px.length; i += 4) if (px[i] > 0) n++; return n; })(),
              fixture: performance.getEntriesByType('resource').filter((r) => /fixture\\.json/.test(r.name)).length })""")
            check("c. nothing saved: the DEMO chip and the 'example plan' bar; Today has the trading day, Your day, the pre-session checklist, Tasks, Habits, the post-session review and the note; never blank",
                  d["demo"] and d["bar"] and d["cards"] == ["The trading day", "Your day", "Pre-session checklist", "Tasks", "Habits", "Post-session review", "Note for Mon 9 Nov"], d["cards"])
            check("c. Monday 09:41 New York: the clock, 'Entries open', the seven bot windows, the market events, the bots card says it is an example, the day picker says Mon 9 Nov / Today",
                  d["clock"] == "09:41" and d["phase"] == "Entries open" and d["wins"] == 7 and d["mrows"] >= 1 and "example" in d["bots"] and "left" in d["bots"] and d["title"] == "Mon 9 Nov" and d["sub"] == "Today", d)
            check("c. the AGORA look: a serif title, a warm dark body (not black), data-theme agora, one h1; the sundial in the header is drawn (not blank)", any(f in d["font"] for f in ("Palatino", "Iowan", "Georgia")) and d["bg"] != "rgb(0, 0, 0)" and d["theme"] == "agora" and d["h1"] == 1 and d["scene"] > 500, d)
            AK.shot(p, "planner-today-demo")
            t = AK.taps(p)
            check("c. every tap target is at least 44 x 44 px", not t, t[:5])
            check("c. no sideways scroll; Jarvis's bottom-right corner is free", AK.no_sideways(p) and not AK.corner(p))
            card(p, "Pre-session checklist").locator(".rowbtn").nth(3).click()
            check("c. in the demo you can tick things but nothing is saved (storage stays empty)", rd(p) is None and rd(p, "planner.today.v1") is None and rd(p, "planner.sessions.v1") is None)
            check("c. no console error, no page error, nothing requested off the page's origin", not errs and not off, (errs[:3], off[:3]))
            # ---- 2. Start my plan -> real, saved, still not blank
            p.click("#startBtn")
            p.wait_for_timeout(250)
            s = state(p)
            check("c. Start my plan: a saved blank v2 plan with the starter checklist, the review lines and three habits; no DEMO chip; an empty-task hint instead of a blank card",
                  s and s["v"] == 2 and len(s["checklist"]) == 6 and len(s["postlist"]) == 4 and len(s["habits"]) == 3 and s["tasks"] == [] and s["events"] == [] and p.is_hidden("#demo") and "No tasks" in p.inner_text("#v-today"), s and s.keys())
            # ---- 3. quick add with natural phrases
            p.fill("#qIn", "Fri 9am journal review")
            prev = p.inner_text("#qPrev")
            p.click("#qAdd")
            p.fill("#qIn", "every Sunday weekly review")
            p.press("#qIn", "Enter")
            p.fill("#qIn", "pay the data subscription tomorrow !!")
            p.press("#qIn", "Enter")
            p.fill("#qIn", "gym 6am for 1h #fitness")
            p.press("#qIn", "Enter")
            p.fill("#qIn", "   ")
            p.press("#qIn", "Enter")
            p.wait_for_timeout(200)
            s = state(p)
            ev = {e["title"]: e for e in s["events"]}
            check("c. the preview line says what will be made ('Event: journal review (Fri 13 Nov at 9 am)'), Add and Enter both work, an empty phrase is refused with a plain message",
                  prev == "Event: journal review (Fri 13 Nov at 9 am)" and "Type it first" in p.inner_text("#status"), prev)
            check("c. 'Fri 9am journal review' is an event Fri 13 Nov 09:00; 'every Sunday weekly review' repeats weekly from Sun 15 Nov; 'tomorrow !!' is a task due Tue 10 Nov with medium priority; a new #project is created and used",
                  ev["journal review"]["day"] == "2026-11-13" and ev["journal review"]["start"] == "09:00" and ev["weekly review"]["repeat"] == "weekly" and ev["weekly review"]["day"] == "2026-11-15" and ev["gym"]["start"] == "06:00" and ev["gym"]["end"] == "07:00"
                  and any(t["text"] == "pay the data subscription" and t["day"] == "2026-11-10" and t["prio"] == 2 for t in s["tasks"]) and any(x["name"] == "fitness" for x in s["projects"]), s["events"])
            p.click("[data-kind=task]")
            p.fill("#qIn", "Fri 3pm call the broker")
            p.press("#qIn", "Enter")
            p.click("[data-kind=auto]")
            p.wait_for_timeout(150)
            tk = [t for t in state(p)["tasks"] if t["text"] == "call the broker"]
            check("c. the Task / Event chips force the kind: 'Fri 3pm call the broker' as a Task keeps its time on the day", tk and tk[0]["slot"] == "15:00" and tk[0]["day"] == "2026-11-13" and len(state(p)["events"]) == 3, tk)
            # ---- 4. Today: agenda, tick, tomorrow, delete via the sheet
            p.fill("#qIn", "Read the weekly report")
            p.press("#qIn", "Enter")
            p.wait_for_timeout(150)
            rows = p.evaluate("() => [...document.querySelectorAll('#v-today .card')].find((c) => c.querySelector('h2').textContent === 'Tasks').innerText")
            check("c. a task typed on Today with no day is for today (lane Today); Tasks shows '0 of 1 done'", "Read the weekly report" in rows and "0 of 1 done" in rows, rows)
            card(p, "Tasks").locator(".tick").first.click()
            p.wait_for_timeout(150)
            s = state(p)
            check("c. the tick (44 px) marks it done and saves; the Jarvis summary (planner.today.v1) and the sessions file are written", any(t["text"] == "Read the weekly report" and t["done"] for t in s["tasks"]) and json.loads(rd(p, "planner.today.v1"))["v"] == 1 and json.loads(rd(p, "planner.sessions.v1"))["v"] == 1)
            card(p, "Tasks").get_by_role("button", name="Move to the next day").first.click() if card(p, "Tasks").get_by_role("button", name="Move to the next day").count() else None
            # ---- 5. pre-session checklist and post-session review feed Epilogue / Lyceum
            card(p, "Pre-session checklist").locator(".rowbtn").nth(0).click()
            card(p, "Pre-session checklist").locator(".rowbtn").nth(1).click()
            p.click("text=Hesitated")
            p.click("#v-today >> text=FOMO")
            card(p, "Post-session review").locator(".rowbtn").nth(0).click()
            p.fill("#rvLesson", "Waited for the sweep")
            p.press("#rvLesson", "Tab")
            p.fill("#rvRule", "No second trade after a loss")
            p.press("#rvRule", "Tab")
            p.wait_for_timeout(200)
            ss = json.loads(rd(p, "planner.sessions.v1"))
            check("c. planner.sessions.v1 for Epilogue and Lyceum: pre 2 of 6, post rating hesitated, mood fomo, the lesson and the rule, 1 of 4 review lines ticked (the Journal's own words)",
                  ss["days"]["2026-11-09"] == {"pre": {"done": 2, "total": 6}, "post": {"rating": "hesitated", "mood": "fomo", "lesson": "Waited for the sweep", "rule": "No second trade after a loss", "done": 1, "total": 4}}, ss)
            n = card(p, "Note for Mon 9 Nov").locator("textarea")
            n.fill("One rule: wait for the sweep.")
            p.wait_for_timeout(450)
            check("c. the note of the day saves as you type (a note tagged daily on that day)", any(x["day"] == "2026-11-09" and "daily" in x["tags"] and "sweep" in x["text"] for x in state(p)["notes"]))
            # ---- 6. Calendar: month, tap a day, add an event with a repeat, reminder, week, day
            tab(p, "calendar")
            m = p.evaluate("() => ({ title: document.querySelector('#calTitle').textContent, cells: document.querySelectorAll('.mcell').length, today: document.querySelectorAll('.mcell.today').length, first: document.querySelector('.mcell').getAttribute('aria-label'), dots: document.querySelectorAll('.mcell .dots i').length, pressed: [...document.querySelectorAll('#calView button')].map((b) => b.getAttribute('aria-pressed')).join() })")
            check("c. Calendar month: November 2026, 42 day buttons (6 weeks from Mon 26 Oct), today marked, dots for events, the Month chip pressed", m["title"] == "November 2026" and m["cells"] == 42 and m["today"] == 1 and m["first"].startswith("Mon 26 Oct") and m["dots"] >= 4 and m["pressed"] == "true,false,false", m)
            t = AK.taps(p)
            check("c. Calendar: every tap >= 44 px, no sideways scroll", not t and AK.no_sideways(p), t[:4])
            AK.shot(p, "planner-calendar-month")
            p.locator(".mcell", has_text="13").first.click()
            p.wait_for_timeout(150)
            check("c. tapping Fri 13 shows that day below: the journal review at 09:00 and the call task at 15:00", "journal review" in p.inner_text("#calDay") and "09:00" in p.inner_text("#calDay") and "call the broker" in p.inner_text("#calDay") and "Friday 13 November 2026" in p.inner_text("#calDayH"), p.inner_text("#calDay"))
            p.click("#calAdd")
            p.wait_for_timeout(100)
            check("c. Add event opens the sheet with the day preset", sheet_open(p) and p.input_value("#sf-day") == "2026-11-13")
            t = AK.taps(p)
            check("c. the sheet: every field and button is at least 44 px", not t, t[:6])
            AK.shot(p, "planner-event-sheet")
            p.fill("#sf-title", "")
            act(p, "Save")
            empty_msg = p.inner_text("#status")
            p.fill("#sf-title", "Weekly pre-session look")
            p.fill("#sf-day", "2026-10-30")
            p.fill("#sf-start", "09:00")
            p.fill("#sf-end", "09:30")
            p.select_option("#sf-repeat", "daily")
            p.click("#sheet >> text=Trading")
            p.select_option("#sf-remind", "15")
            p.fill("#sf-note", "Line one\nLine two")
            act(p, "Save")
            s = state(p)
            e = next((x for x in s["events"] if x["title"] == "Weekly pre-session look"), None)
            check("c. a sheet that is missing its title says so and stays open; saving makes a daily 09:00-09:30 event from Fri 30 Oct, Trading colour, 15 minute reminder, a two-line note; the sheet closes",
                  "Type what the event is first" in empty_msg and e and e["repeat"] == "daily" and e["start"] == "09:00" and e["end"] == "09:30" and e["cat"] == "trading" and e["remind"] == 15 and e["note"] == "Line one\nLine two" and not sheet_open(p), e)
            counts = p.evaluate("""() => { const P = window.PLANNER; const o = P.C.expand(P.S.state.events.filter((e) => e.title === 'Weekly pre-session look'), '2026-10-30', '2026-11-03');
              return o.map((x) => x.day + ' ' + x.start + ' ' + new Date(x.ms).toISOString().slice(11, 16)); }""")
            check("c. through the clock change of Sun 1 Nov the daily 09:00 event stays 09:00 on the wall clock (13:00Z before, 14:00Z after)", counts == ["2026-10-30 09:00 13:00", "2026-10-31 09:00 13:00", "2026-11-01 09:00 14:00", "2026-11-02 09:00 14:00", "2026-11-03 09:00 14:00"], counts)
            p.locator(".mcell", has_text="1").nth(1).click()
            p.wait_for_timeout(100)
            sun = p.evaluate("() => document.querySelector('.mcell.sel').getAttribute('aria-label')")
            check("c. Sun 1 Nov (the 25-hour day) lists the daily event in the month grid", "Sun 1 Nov" in sun and "event" in sun and "Weekly pre-session look" in p.inner_text("#calDay"), sun)
            p.click("#calView [data-view=week]")
            p.wait_for_timeout(150)
            w = p.evaluate("() => ({ title: document.querySelector('#calTitle').textContent, rows: document.querySelectorAll('#calBody .rowbtn').length, text: document.querySelector('#calBody').innerText })")
            check("c. Week view: a row per day Mon to Sun with its first events; the title is the week range (Mon 26 Oct to Sun 1 Nov) and the daily event shows on its days", w["rows"] == 7 and w["title"] == "Mon 26 Oct to Sun 1 Nov" and "Weekly pre-session look" in w["text"], w)
            p.click("#calNext")
            check("c. the next week is Mon 2 Nov to Sun 8 Nov", p.inner_text("#calTitle") == "Mon 2 Nov to Sun 8 Nov", p.inner_text("#calTitle"))
            p.click("#calToday")
            p.click("#calView [data-view=day]")
            p.wait_for_timeout(150)
            dv = p.evaluate("() => ({ strip: document.querySelectorAll('.strip i').length, ticks: document.querySelectorAll('.strip b').length, title: document.querySelector('#calTitle').textContent, lbl: document.querySelector('.strip').getAttribute('aria-label') })")
            check("c. Day view: the 24 hour strip with the bot windows and a tick per timed item; the title is the day", dv["strip"] >= 4 and dv["ticks"] >= 1 and "00:00 to 24:00" in dv["lbl"], dv)
            AK.shot(p, "planner-calendar-day")
            p.locator("#calDay .rowbtn", has_text="Weekly pre-session look").first.click()
            p.wait_for_timeout(100)
            check("c. tapping an event opens it in the sheet with 'Skip this day' for a repeat", sheet_open(p) and p.locator("#sheetAct button", has_text="Skip this day").count() == 1)
            act(p, "Skip this day")
            ex = next(x for x in state(p)["events"] if x["title"] == "Weekly pre-session look")
            check("c. 'Skip this day' drops that one day only (an exception) and keeps the series", len(ex["ex"]) == 1 and ex["repeat"] == "daily", ex)
            p.click("#tgWin")
            p.click("#tgMkt")
            check("c. the Trading windows and Market events switches are saved in the plan", state(p)["prefs"]["windows"] is False and state(p)["prefs"]["market"] is False)
            p.click("#tgWin")
            p.click("#tgMkt")
            # ---- 7. Tasks: lanes, edit sheet, steps, someday, project filter
            tab(p, "tasks")
            lanes = p.inner_text("#laneBtns")
            check("c. Tasks: lanes Today / Next / Someday / Done with counts", re.search(r"Today \d+\s+Next \d+\s+Someday \d+\s+Done \d+", lanes) is not None, lanes)
            p.click("#laneBtns >> text=Next")
            p.wait_for_timeout(100)
            check("c. Next holds the tasks due after today (the data subscription, due tomorrow, and the Fri 3pm call)", "pay the data subscription" in p.inner_text("#taskRows") and "call the broker" in p.inner_text("#taskRows"), p.inner_text("#taskRows"))
            p.locator("#taskRows .rowbtn", has_text="call the broker").first.click()
            p.wait_for_timeout(100)
            p.fill("#sf-text", "Call the broker about the payout")
            p.click("#sheet >> text=High")
            p.fill("#sf-step", "Find the number")
            p.press("#sf-step", "Enter")
            p.fill("#sf-step", "Write the question")
            p.press("#sf-step", "Enter")
            p.wait_for_timeout(100)
            act(p, "Save")
            tk = next(t for t in state(p)["tasks"] if t["text"].startswith("Call the broker"))
            subs = [t for t in state(p)["tasks"] if t["parent"] == tk["id"]]
            check("c. the task sheet edits the text and priority and adds steps (2 steps, tied to their task)", tk["prio"] == 3 and len(subs) == 2 and "0 of 2 steps" in p.inner_text("#taskRows"), (tk, subs))
            p.locator("#taskRows .subs .rowbtn").first.click()
            p.wait_for_timeout(100)
            check("c. a step ticks on its own row and the parent counts it (1 of 2 steps)", "1 of 2 steps" in p.inner_text("#taskRows"), p.inner_text("#taskRows"))
            p.click("#taskAdd")
            p.fill("#sf-text", "Learn scale-in")
            p.click("#sheet >> text=Someday")
            act(p, "Save")
            p.click("#laneBtns >> text=Someday")
            p.wait_for_timeout(100)
            check("c. Add a task with the lane Someday: it appears in Someday, not in Today; its 'Next' button moves it", "Learn scale-in" in p.inner_text("#taskRows") and "Next" in p.inner_text("#taskRows"))
            p.locator("#taskRows .row button", has_text="Next").first.click()
            p.wait_for_timeout(100)
            check("c. ... moved to Next", next(t for t in state(p)["tasks"] if t["text"] == "Learn scale-in")["lane"] == "next")
            t = AK.taps(p)
            check("c. Tasks: every tap >= 44 px, no sideways scroll", not t and AK.no_sideways(p), t[:4])
            AK.shot(p, "planner-tasks")
            # ---- 8. Projects
            tab(p, "projects")
            p.fill("#projIn", "Prop firm payout")
            p.press("#projIn", "Enter")
            p.wait_for_timeout(100)
            p.locator("#projList .card", has_text="Prop firm payout").get_by_role("button", name="Add a task to Prop firm payout").click()
            p.fill("#sf-text", "Send the payout request")
            p.fill("#sf-day", "2026-11-10")
            act(p, "Save")
            pj = card(p, "") if False else p.locator("#projList .card", has_text="Prop firm payout").first
            check("c. Projects: add a project, then 'Add task' from its card links the task; the card shows '0 of 1 tasks done', next due Tue 10 Nov and a progress bar",
                  "0 of 1 tasks done" in pj.inner_text() and "Tue 10 Nov" in pj.inner_text() and pj.locator(".ag-bar").count() == 1, pj.inner_text())
            pj.locator("button", has_text="Tasks").first.click()
            p.wait_for_timeout(150)
            check("c. a project's 'Tasks' button opens the Tasks tab filtered to it", p.get_attribute("#tab-tasks", "aria-selected") == "true" and "Send the payout request" in p.inner_text("#taskRows") and "pay the data" not in p.inner_text("#taskRows"), p.inner_text("#taskRows"))
            p.select_option("#taskProj", "")
            tab(p, "projects")
            t = AK.taps(p)
            check("c. Projects: every tap >= 44 px, no sideways scroll", not t and AK.no_sideways(p), t[:4])
            # ---- 9. Habits
            tab(p, "habits")
            p.locator("#habitCards .hday").nth(0).click()
            p.locator("#habitCards .hday").nth(1).click()
            p.wait_for_timeout(100)
            h = p.evaluate("() => ({ rows: document.querySelectorAll('#heat .hrow').length, cells: document.querySelectorAll('#heat .hcells')[0].children.length, lv: document.querySelectorAll('#heat .hcells')[0].querySelectorAll('i.lv1,i.lv2,i.lv3,i.lv4').length, text: document.querySelector('#habitCards .card').innerText })")
            check("c. Habits: a 12 week heatmap row per habit, a card with the streak, best and 'this week n of 7', the week buttons tick", h["rows"] == 3 and h["cells"] == 12 and h["lv"] >= 1 and "this week 2 of 7" in h["text"] and "best 2" in h["text"], h)
            p.fill("#habitIn", "Read for 20 minutes")
            p.press("#habitIn", "Enter")
            p.wait_for_timeout(100)
            check("c. add a habit", len(state(p)["habits"]) == 4)
            t = AK.taps(p)
            check("c. Habits: every tap >= 44 px, no sideways scroll", not t and AK.no_sideways(p), t[:4])
            ctx.close()

            # ---- 10. goals linked to Argo (read only), notes, focus, find (a saved plan, Argo's goals on the phone)
            argo = json.dumps([{"id": "g1", "name": "First payout", "type": "payouts", "target": 1}, {"id": "g2", "name": "$1,000 paid out", "type": "paid", "target": 1000}])
            ctx, p, errs, seen, off = AK.page(br, origin, storage={"argo.goals.v1": argo, KEY: json.dumps({"v": 2, "events": [], "tasks": [{"id": "t1", "text": "Open the funded account", "day": "2026-11-10", "done": True, "slot": "", "prio": 0, "lane": "next", "project": "", "parent": "", "goal": "g1", "note": ""}, {"id": "t2", "text": "Pass the eval", "day": "2026-11-12", "done": False, "slot": "", "prio": 0, "lane": "next", "project": "", "parent": "", "goal": "g1", "note": ""}],
                                                                                                          "goals": [{"id": "g1", "name": "Get paid", "due": "2026-12-31", "argo": "g2", "pct": 0, "note": ""}, {"id": "g2", "name": "Journal 20 days", "due": "", "argo": "", "pct": 30, "note": ""}], "notes": [{"id": "n1", "title": "Stop rule", "text": "The stop goes beyond the sweep.", "tags": ["rules"], "day": "", "pin": False, "at": 5}]})})
            AK.open_app(p, origin, APP, MON)
            tab(p, "goals")
            g = p.evaluate("() => ({ cards: [...document.querySelectorAll('#goalList .card')].map((c) => c.innerText), argo: document.querySelector('#argoList').innerText, note: document.querySelector('#argoNote').textContent })")
            check("c. Goals: a goal follows its linked tasks (1 of 2 = 50%) and shows the linked Argo goal's own name and target; a goal without tasks uses the hand-set 30% with -10% / +10% buttons; Argo's goals are listed read only",
                  "50%" in g["cards"][0] and "1 of 2 linked tasks done" in g["cards"][0] and "$1,000 paid out" in g["cards"][0] and "30%" in g["cards"][1] and "+10%" in g["cards"][1] and "First payout" in g["argo"] and "Read from Argo" in g["note"], g)
            p.locator("#goalList .card").nth(1).get_by_role("button", name="More progress").click()
            p.wait_for_timeout(100)
            check("c. +10% saves (30% to 40%); the Argo goals key is untouched", state(p)["goals"][1]["pct"] == 40 and rd(p, "argo.goals.v1") == argo)
            p.locator("#goalList .card").first.get_by_role("button", name="Edit goal").click()
            p.wait_for_timeout(100)
            check("c. the goal sheet lists Argo's goals to link to (read only)", "First payout" in p.inner_text("#sf-argo") and sheet_open(p))
            p.click("#sheetX")
            p.fill("#goalIn", "Pass the eval in 2 weeks")
            p.press("#goalIn", "Enter")
            p.wait_for_timeout(100)
            check("c. add a goal", len(state(p)["goals"]) == 3)
            # notes
            tab(p, "notes")
            p.click("#noteNew")
            p.fill("#sf-title", "Risk idea")
            p.fill("#sf-text", "Size follows the stop.\nBigger stop, fewer micros.")
            p.fill("#sf-tags", "rules ideas")
            p.click("#sheet >> text=Pinned")
            act(p, "Save")
            nl = p.inner_text("#noteList")
            check("c. Notes: a new note with a title, text, tags and a pin lands at the top ('Pinned: Risk idea'); tag chips show #rules 2", nl.startswith("Pinned: Risk idea") and "#rules" in p.inner_text("#noteTags") and "#ideas" in p.inner_text("#noteTags"), (nl, p.inner_text("#noteTags")))
            p.click("#noteTags >> text=#rules")
            p.wait_for_timeout(100)
            check("c. tapping a tag chip filters the notes (both rules notes stay, search box says #rules)", p.input_value("#noteQ") == "#rules" and p.locator("#noteList .rowbtn").count() == 2)
            p.fill("#noteQ", "micros")
            check("c. searching notes: 'micros' finds only the new note", p.locator("#noteList .rowbtn").count() == 1)
            p.fill("#noteQ", "")
            p.locator("#noteList .rowbtn", has_text="Stop rule").click()
            p.wait_for_timeout(100)
            check("c. tapping a note opens it with a Delete that needs a second tap", sheet_open(p) and p.input_value("#sf-title") == "Stop rule")
            p.locator("#sheetAct button", has_text="Delete").click()
            first = p.inner_text("#sheetAct")
            p.locator("#sheetAct button", has_text="Tap again").click()
            p.wait_for_timeout(150)
            check("c. ... the first tap says 'Tap again', the second deletes it and closes", "Tap again" in first and not sheet_open(p) and len(state(p)["notes"]) == 1)
            t = AK.taps(p)
            check("c. Goals and Notes: every tap >= 44 px, no sideways scroll", not t and AK.no_sideways(p), t[:4])
            # focus timer
            tab(p, "focus")
            p.select_option("#fTask", "t2")
            p.click("#fStart")
            p.wait_for_timeout(2100)
            f1 = p.evaluate("() => ({ time: document.querySelector('#fTime').textContent, phase: document.querySelector('#fPhase').textContent, pause: !document.querySelector('#fPause').hidden, start: document.querySelector('#fStart').hidden })")
            check("c. Focus: Start runs a 25 minute round (24:5x on the clock), Pause / Skip / Reset appear, the phase says Work, round 1", f1["time"].startswith("24:5") and "Work, round 1" in f1["phase"] and f1["pause"] and f1["start"], f1)
            p.click("#fPause")
            tm = p.inner_text("#fTime")
            p.wait_for_timeout(1200)
            check("c. Pause freezes the clock; the running timer is kept in planner.focus.v1 so a reload keeps it", p.inner_text("#fTime") == tm and "Paused" in p.inner_text("#fPhase") and json.loads(rd(p, "planner.focus.v1"))["phase"] == "work")
            p.click("#fPause")
            p.evaluate("() => { window.PLANNER.S.focus.endsAt = Date.now() - 500; }")
            p.wait_for_timeout(1600)
            fs = state(p)["focus"]
            check("c. when the round ends the page says so on screen, counts the round (1 round, 25 minutes today) and starts the 5 minute break", fs == {"2026-11-09": {"n": 1, "min": 25}} and "Short break" in p.inner_text("#fPhase") and "1 round" in p.inner_text("#fStats") and "Round done" in p.inner_text("#status"), (fs, p.inner_text("#fPhase")))
            p.click("#fNotify")
            p.wait_for_timeout(600)
            check("c. 'Tell me when it ends' asks the phone once and says so; whatever the phone answers the page explains in words and never errors", any(x in p.inner_text("#fNote").lower() for x in ("asking", "not allowed", "tell you")) and not errs, (p.inner_text("#fNote"), errs[:2]))
            p.click("#fReset")
            t = AK.taps(p)
            check("c. Focus: every tap >= 44 px, no sideways scroll", not t and AK.no_sideways(p), t[:4])
            # find
            tab(p, "find")
            p.fill("#findIn", "micros")
            p.wait_for_timeout(100)
            fr = p.inner_text("#findOut")
            check("c. Find: 'micros' finds the note across the whole plan with its kind and tags; the count is spoken ('1 result')", "Risk idea" in fr and "#rules" in fr and p.inner_text("#findNote") == "1 result", (fr, p.inner_text("#findNote")))
            p.fill("#findIn", "open funded")
            p.wait_for_timeout(100)
            p.locator("#findOut .rowbtn").first.click()
            p.wait_for_timeout(150)
            check("c. tapping a task result opens it in the sheet", sheet_open(p) and p.input_value("#sf-text") == "Open the funded account")
            p.click("#sheetX")
            p.fill("#findIn", "zzzz nothing")
            check("c. nothing found says so plainly", "Nothing found" in p.inner_text("#findOut"))
            check("c. no console error through all of it", not errs, errs[:3])
            ctx.close()

            # ---- 11. migration from the two old keys: planner.agora.v1 + planner.v1 -> planner.agora.v2, the old keys untouched
            v1t, lgt = json.dumps(V1), json.dumps(LEGACY)
            ctx, p, errs, seen, off = AK.page(br, origin, storage={"planner.agora.v1": v1t, "planner.v1": lgt})
            AK.open_app(p, origin, APP, MON)
            s = state(p)
            check("c. migration: with only the two old keys saved the page opens with your data (no DEMO), writes planner.agora.v2, and the old keys stay byte for byte as they were",
                  s and s["v"] == 2 and p.is_hidden("#demo") and rd(p, "planner.agora.v1") == v1t and rd(p, "planner.v1") == lgt and not errs, (s and s["from"], errs[:2]))
            check("c. ... every v1 task, ticked line, habit day and day note is there, and the first Planner's weekly event, task and project came along (Money, high priority)",
                  {t["text"] for t in s["tasks"]} == {"Saved task", "Done task", "Pay the card"} and s["checks"] == V1["checks"] and s["habitLog"] == V1["habitLog"] and len(s["notes"]) == 2 and any(e["title"] == "Dentist" and e["repeat"] == "weekly" and e["cat"] == "health" for e in s["events"]) and any(t["text"] == "Pay the card" and t["prio"] == 3 for t in s["tasks"]) and any(x["name"] == "Money" for x in s["projects"]), s)
            today_txt = p.inner_text("#v-today")
            check("c. Today shows the migrated task at 07:00, the ticked checklist line (1 of 2 done) and the day note", "Saved task" in today_txt and "1 of 2 done" in today_txt and "wait for the sweep" in p.input_value("#noteIn"), today_txt[:300])
            p.locator("#v-today .tick").first.click()
            p.wait_for_timeout(150)
            check("c. after a change the old keys are still untouched, only v2 moves", rd(p, "planner.agora.v1") == v1t and rd(p, "planner.v1") == lgt and any(t["done"] for t in state(p)["tasks"] if t["text"] == "Saved task"))
            AK.open_app(p, origin, APP, MON)
            check("c. reload: the saved v2 plan wins and keeps the change", any(t["done"] for t in state(p)["tasks"] if t["text"] == "Saved task") and p.is_hidden("#demo") and not errs)
            # export / import
            tab(p, "data")
            check("c. Data: the export summary counts events, tasks, projects, habits, goals and notes; the storage line says where the plan came from and that the old copy is untouched",
                  "event" in p.inner_text("#expSum") and "Moved over from your earlier Planner" in p.inner_text("#stFrom") and "untouched" in p.inner_text("#stFrom"), p.inner_text("#stFrom"))
            with p.expect_download() as dl:
                p.click("#expBtn")
            fn, path = dl.value.suggested_filename, dl.value.path()
            exp = json.load(open(path, encoding="utf-8"))
            check("c. Export JSON downloads planner-2026-11-09.json: app planner, v 2, the whole plan inside", fn == "planner-2026-11-09.json" and exp["app"] == "planner" and exp["v"] == 2 and len(exp["data"]["tasks"]) == 3 and len(exp["data"]["events"]) == 1, fn)
            with p.expect_download() as dl:
                p.click("#icsBtn")
            fn2, path2 = dl.value.suggested_filename, dl.value.path()
            ics = open(path2, encoding="utf-8", newline="").read()
            check("c. Export events (.ics) downloads planner-2026-11-09.ics: a real calendar file with the New York time zone rules, the weekly Dentist with its RRULE and category",
                  fn2 == "planner-2026-11-09.ics" and ics.startswith("BEGIN:VCALENDAR\r\n") and "TZID=America/New_York:20261112T093000" in ics and "RRULE:FREQ=WEEKLY" in ics and "SUMMARY:Dentist" in ics and "CATEGORIES:Health" in ics and ics.endswith("END:VCALENDAR\r\n"), ics[:300])
            exp["data"]["tasks"].append({"id": "t9", "text": "From the file", "day": "2026-11-09", "done": False, "slot": "11:00", "prio": 0, "lane": "next", "project": "", "parent": "", "goal": "", "note": ""})
            p.set_input_files("#impFile", files=[{"name": "plan.json", "mimeType": "application/json", "buffer": json.dumps(exp).encode()}])
            p.wait_for_timeout(300)
            check("c. choosing a file loads it into the box and says to tap Import (nothing is replaced yet)", "From the file" in p.input_value("#impText") and "Tap Import" in p.inner_text("#impMsg") and len(state(p)["tasks"]) == 3)
            p.click("#impBtn")
            p.wait_for_timeout(250)
            s = state(p)
            check("c. Import replaces the plan (4 tasks), says what it imported, keeps the old plan as a backup, clears the box", len(s["tasks"]) == 4 and "Imported 4 tasks" in p.inner_text("#impMsg") and len(json.loads(rd(p, KEY + ".backup"))["tasks"]) == 3 and p.input_value("#impText") == "")
            p.fill("#impText", json.dumps({"app": "planner", "v": 1, "data": V1}))
            p.click("#impBtn")
            check("c. an old Planner export (v1) imports too and is migrated (2 tasks)", len(state(p)["tasks"]) == 2 and "Imported 2 tasks" in p.inner_text("#impMsg"), p.inner_text("#impMsg"))
            p.fill("#impText", "this is not json")
            p.click("#impBtn")
            m1 = p.inner_text("#impMsg")
            p.fill("#impText", '{"hello": 1}')
            p.click("#impBtn")
            m2 = p.inner_text("#impMsg")
            check("c. a bad file is refused with a plain sentence and the plan is untouched", "not a Planner file" in m1 and "no Planner plan" in m2 and len(state(p)["tasks"]) == 2, (m1, m2))
            p.fill("#clIn", "Screens off by 18:00")
            p.press("#clIn", "Enter")
            p.fill("#pcIn", "Phone in the other room")
            p.press("#pcIn", "Enter")
            p.wait_for_timeout(100)
            s = state(p)
            check("c. both templates can be edited: a new pre-session line and a new post-session review line", len(s["checklist"]) == 3 and len(s["postlist"]) == 5, (len(s["checklist"]), len(s["postlist"])))
            p.click("#clEdit .row:last-child button")
            lbl = p.inner_text("#clEdit .row:last-child button")
            p.click("#clEdit .row:last-child button")
            p.wait_for_timeout(100)
            check("c. deleting a line needs a second tap ('Sure?')", lbl == "Sure?" and len(state(p)["checklist"]) == 2)
            t = AK.taps(p)
            check("c. Data: every tap >= 44 px, no sideways scroll, the corner is free", not t and AK.no_sideways(p) and not AK.corner(p), (t[:4], AK.corner(p)))
            p.click("#resetBtn")
            a1 = p.inner_text("#resetBtn")
            p.click("#resetBtn")
            p.wait_for_timeout(100)
            check("c. Reset to a blank plan needs a second tap, then it is the starter plan again", "Tap again" in a1 and state(p)["tasks"] == [] and len(state(p)["habits"]) == 3)
            check("c. through all of it: no console error, nothing requested off the page's origin", not errs and not off, (errs[:3], off[:3]))
            ctx.close()

            # ---- 12. corrupt storage never loses data
            ctx, p, errs, seen, off = AK.page(br, origin, storage={KEY: "{not json", "planner.agora.v1": v1t})
            AK.open_app(p, origin, APP, MON)
            check("c. a corrupt v2 plan falls back to the DEMO (never blank, no error), the broken text is kept under '.bad' and the old v1 key is untouched (never replaced silently)", p.is_visible("#demo") and rd(p, KEY + ".bad") == "{not json" and rd(p, "planner.agora.v1") == v1t and not errs, (rd(p, KEY + ".bad"), errs[:2]))
            ctx.close()

            # ---- 13. reminders as in-app badges; the weekend; a saved plan with junk inside
            ev = {"id": "e1", "title": "Call the prop firm", "day": "2026-11-09", "start": "10:00", "end": "10:30", "cat": "work", "repeat": "none", "until": "", "ex": [], "remind": 15, "note": ""}
            plan = json.dumps({"v": 2, "events": [ev, {"junk": 1}, {"title": "bad day", "day": "2026-02-30"}], "tasks": [{"id": "t1", "text": "Saved task", "day": "2026-11-09", "done": False, "slot": "", "prio": 1, "lane": "next", "project": "", "parent": "t7", "goal": "", "note": ""}, 5]})
            ctx, p, errs, seen, off = AK.page(br, origin, storage={KEY: plan})
            AK.open_app(p, origin, APP, "?at=2026-11-09T14:50:00Z")
            rb = p.inner_text("#remindBar")
            check("c. a reminder shows as a badge at the top 15 minutes before: 'Call the prop firm at 10:00, in 10 min' at 09:50", "Call the prop firm at 10:00, in 10 min" in rb and p.is_visible("#remindBar"), rb)
            check("c. a saved plan with junk inside: the junk rows are dropped, the step with a missing parent became a normal task, no DEMO, no error", p.is_hidden("#demo") and "Saved task" in p.inner_text("#v-today") and not errs and len(p.evaluate("() => window.PLANNER.S.state.events")) == 1)
            AK.open_app(p, origin, APP, "?at=2026-11-09T15:10:00Z")
            rb = p.inner_text("#remindBar") if p.is_visible("#remindBar") else ""
            check("c. once it started the badge says so (10:10: 'started at 10:00'), and it goes away after 15 minutes", "started at 10:00" in rb)
            AK.open_app(p, origin, APP, "?at=2026-11-09T15:40:00Z")
            check("c. 10:40: no badge", not p.is_visible("#remindBar"))
            ctx.close()
            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, APP, "?at=2026-11-14T15:00:00Z")
            w = p.evaluate("() => [document.querySelector('#clkPhase').textContent, document.querySelector('#clkNext').textContent, document.querySelectorAll('.win').length, document.querySelector('#dayTitle').textContent, document.querySelectorAll('.wins .empty').length]")
            check("c. Saturday: 'Weekend', 'does not trade', no windows (an empty-state line), the planner still works", w[0] == "Weekend" and "does not trade" in w[1] and w[2] == 0 and w[3] == "Sat 14 Nov" and w[4] == 1 and not errs, w)
            ctx.close()

            # ---- 14. small phone, LITE, reduced motion: every tab, the sheet, still scene
            ctx, p, errs, seen, off = AK.page(br, origin, w=375, h=667, reduced=True, lite=True)
            AK.open_app(p, origin, APP, MON + "&q=low")
            bad = []
            for name in ("today", "calendar", "tasks", "projects", "habits", "goals", "notes", "focus", "find", "data"):
                tab(p, name)
                tp = AK.taps(p)
                if tp or not AK.no_sideways(p):
                    bad.append((name, tp[:3]))
            p.click("#tab-calendar")
            p.click("#calAdd")
            p.wait_for_timeout(200)
            tp = AK.taps(p)
            if tp or not AK.no_sideways(p):
                bad.append(("sheet", tp[:3]))
            anim = p.evaluate("() => getComputedStyle(document.querySelector('.sheet-card')).animationName")
            check("c. 375 x 667 with LITE and reduced motion: every tab and the sheet have no sideways scroll and every tap >= 44 px, no error; the sheet does not animate; the LITE chip shows", not bad and not errs and anim == "none" and p.is_visible("#lite"), (bad, errs[:2], anim))
            AK.shot(p, "planner-375-sheet")
            p.click("#sheetX")
            p.keyboard.press("Escape")
            check("c. the sheet closes with its close button and with Escape", not sheet_open(p))
            ctx.close()
            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, APP, "?demo=1&" + MON[1:])
            check("c. ?demo=1 forces the example plan and never writes anything", p.is_visible("#demo") and rd(p) is None and not errs, errs[:2])
            ctx.close()
    finally:
        srv.shutdown()

    # ---- 15. the live files: home.json (the bots' state and the drawdown left) and Pythia's events, and the fallback when they are missing
    srv, origin = AK.serve(overrides={"/home.json": json.dumps(HOME), "/pythia/events.json": None})
    try:
        with AK.browser() as br:
            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, APP, MON)
            bx = p.inner_text(".botbox")
            check("c. home.json (read only): the bots' own status line and 'drawdown left' per account; no 'example' label when it is real", "LIT is watching the 18:00 open" in bx and "$1,750 left of $2,000" in bx and "$700 left of $1,000" in bx and "example" not in bx.lower(), bx)
            check("c. Pythia's file missing: the market events are the labelled example (never blank) and a missing file is not an error", "(example)" in p.inner_text("#v-today") and not errs, errs[:2])
            ctx.close()
            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, APP, "?demo=1&at=2026-11-09T14:41:00Z")
            ctx.close()
    finally:
        srv.shutdown()
    srv, origin = AK.serve()
    try:
        with AK.browser() as br:
            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, APP, MON)
            mt = p.evaluate("() => ({ demo: window.PLANNER.S.marketDemo, n: window.PLANNER.S.market.events.length })")
            check("c. the site's real Pythia events.json is used when it exists (the next 14 days of events as overlays on Today and the calendar), not the example", not mt["demo"] and mt["n"] > 20 and "(example)" not in p.inner_text("#v-today").split("Market events")[1][:40], mt)
            ctx.close()
    finally:
        srv.shutdown()


if __name__ == "__main__":
    test_static()
    test_core()
    if "--static" not in sys.argv:
        test_page()
    AK.finish()
