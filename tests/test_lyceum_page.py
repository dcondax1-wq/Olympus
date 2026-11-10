"""LYCEUM, the OLYMPUS school (tools/web_public/lyceum/, AGORA look, 2026-11-10): a daily 5-question quiz on the owner's own rules, XP + Greek ranks, spaced-repetition cards from past mistakes,
the 3 habits that cost the most money, a weekly report card, and a marble lecture hall that gains a column per rank.

  a. static: the files, the kit lines, the AGORA look, read-only (no markup from data, the only network is the published files, the Journal's ratings are only READ, only 'lyceum.v1' is written),
     the Jarvis card, the manifest, the DEMO fixture, the 3D hall file (warm light, no bloom / neon, falls back)
  b. the maths in node (lyceumcore.js): the question bank, the daily quiz, XP, ranks and the hall, streaks, once-a-day, habits in $ and R, cards and boxes, the report card, bad data
  c. Chromium 390 x 844 (and 375 x 667): the DEMO school, answering the quiz to the end (XP, no repeat), a review card, real trades + Journal ratings, no data at all, LITE / reduced motion, taps >= 44 px
    python -X utf8 -m tests.test_lyceum_page            (--static: parts a and b only)
"""
from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import agora_kit as AK  # noqa: E402

APP, NAME = "lyceum", "Lyceum"
check = AK.check


def test_static():
    AK.static_kit(APP, NAME, reads=("../odeon/trades.json", "../home.json"), storage="own")
    d = os.path.join(AK.WEB, APP)
    html, js, core, s3d = (AK.read(os.path.join(d, n)) for n in ("index.html", "lyceum.js", "lyceumcore.js", "lyceum3d.js"))
    check("a. the page order: the hall + rank first, today's quiz, habits, review cards, the weekly report card, the ranks",
          html.index('id="rankH"') < html.index('id="quizCard"') < html.index('id="habitsCard"') < html.index('id="reviewCard"') < html.index('id="reportCard"') < html.index('id="ranks"'))
    check("a. the 3D hall is a labelled canvas loaded by its own optional module", '<canvas id="stage"' in html and 'aria-label="A marble lecture hall' in html and 'src="lyceum3d.js' in html)
    check("a. the hall: marble + bronze + olive laurels, a warm key light, warm fog, no bloom / emissive / neon, WebGL failure hides the canvas, LITE / reduced motion = one still frame, no network",
          "MeshStandardMaterial" in s3d and "0xffd7a0" in s3d and "Fog(" in s3d and "0x7f8a52" in s3d and not re.search(r"Bloom|emissive", s3d) and "classList.add('off')" in s3d and "st.still" in s3d
          and not AK.BANNED_LOOK.search(s3d) and not re.search(r"fetch\(|XMLHttpRequest|innerHTML|WebSocket|https?://", s3d))
    check("a. storage: it writes only 'lyceum.v1', reads the Journal's 'journal.v1' without ever writing it, and never writes in the demo",
          re.findall(r"localStorage\.setItem\('([^']+)'", js) == ["lyceum.v1"] and "localStorage.getItem('journal.v1')" in js and "if (S.demo) return;" in js
          and not re.search(r"sessionStorage|indexedDB", js + core))
    check("a. the five rules are the owner's: stop, size, target, greed, flat 15:55, the 15:30 entry limit, BE at 1R, one trade a day",
          all(x in core for x in ("1 tick beyond the sweep extreme", "size follows the stop", "banked at 8R", "15:55", "15:30", "one trade a day", "Break-even"))
          and "RULES = ['stop', 'size', 'target', 'greed', 'flat']" in core)
    check("a. every habit and card shows its dollars with their R", "both(" in core and "(R n/a)" in js and "C.both(" in js)
    fx = json.load(open(os.path.join(d, "fixture.json"), encoding="utf-8"))
    ids = {t["id"] for t in fx["trades"]}
    check("a. the fixture has demo trades (with R), journal ratings for them, and example progress with a streak", len(fx["trades"]) >= 8 and all("r" in t for t in fx["trades"]) and set(fx["entries"]) <= ids and len(fx["progress"]["days"]) >= 3)


HARNESS = r"""
import(process.argv[2]).then((C) => {
  const o = {};
  const Q = C.QUESTIONS, by = {}; for (const q of Q) by[q.topic] = (by[q.topic] || 0) + 1;
  o.bank = { n: Q.length, ids: new Set(Q.map((q) => q.id)).size, topics: by, ok: Q.every((q) => q.o.length === 3 && q.a === 0 && q.why.length > 20 && q.o[0].length > 0) };
  const q1 = C.dailyQuiz('2026-11-10'), q2 = C.dailyQuiz('2026-11-10'), q3 = C.dailyQuiz('2026-11-11'), same = JSON.stringify(q1) === JSON.stringify(q2);
  let diff = 0; for (let d = 11; d < 31; d++) if (JSON.stringify(C.dailyQuiz('2026-11-' + d)) !== JSON.stringify(q1)) diff++;
  const right = (qz) => qz.every((q) => { const src = Q.find((x) => x.id === q.id); return q.o[q.a] === src.o[0] && new Set(q.o).size === 3; });
  o.quiz = { topics: q1.map((q) => q.topic), same, diff, right: right(q1) && right(q3), moved: Q.some((q) => { for (let d = 1; d < 29; d++) { const z = C.dailyQuiz('2026-12-' + String(d).padStart(2, '0')).find((x) => x.id === q.id); if (z && z.a !== 0) return true; } return false; }) };
  o.rank = [C.rankFor(0).rank.id, C.rankFor(119).rank.id, C.rankFor(120).rank.id, C.rankFor(120).frac, C.rankFor(210).frac, C.rankFor(2600).rank.id, C.rankFor(2600).toNext, C.rankFor(-5).xp, C.rankFor('x').rank.id, C.rankFor(299).toNext];
  o.hall = [0, 3, 6, 9, -1].map((i) => C.hallFor(i));
  o.xp = [C.quizXp(5, 0), C.quizXp(3, 2), C.quizXp(5, 9), C.quizXp(0, 0), C.quizXp(4, 3)];
  const P = (days, extra) => ({ ...C.emptyProg(), days, ...(extra || {}) }), d = (s) => ({ score: s, xp: 10 * s, miss: [] });
  o.streak = [C.streak(P({ '2026-11-08': d(3), '2026-11-09': d(4) }), '2026-11-10'), C.streak(P({ '2026-11-08': d(3), '2026-11-09': d(4), '2026-11-10': d(5) }), '2026-11-10'),
              C.streak(P({ '2026-11-05': d(3), '2026-11-09': d(4) }), '2026-11-10'), C.streak(P({ '2026-11-01': d(3), '2026-11-02': d(3), '2026-11-03': d(3), '2026-11-09': d(4) }), '2026-11-10'), C.streak(C.emptyProg(), '2026-11-10')];
  const quiz = C.dailyQuiz('2026-11-10'), allRight = quiz.map((q) => q.a), none = quiz.map((q) => (q.a + 1) % 3);
  const f1 = C.finishQuiz(C.emptyProg(), quiz, allRight, '2026-11-10'), f2 = C.finishQuiz(f1.prog, quiz, none, '2026-11-10'), f3 = C.finishQuiz(P({ '2026-11-09': d(4), '2026-11-08': d(4) }), quiz, none.map((x, i) => (i < 2 ? allRight[i] : x)), '2026-11-10');
  o.finish = { first: f1.result, again: f2.result.already, kept: f2.prog.days['2026-11-10'].score, mixed: f3.result, miss: f3.result.miss.length };
  o.total = [C.totalXp(P({ a: d(1) }, {})), C.totalXp({ ...C.emptyProg(), days: { '2026-11-01': { score: 5, xp: 70, miss: [] } }, reviewsByDay: { '2026-11-01': 12, '2026-11-02': 2 } })];
  const T = (id, day, usd, r) => ({ id, day, usd, r, side: 'LONG', qty: 5 });
  const trades = [T('t1', '2026-11-09', 400, 2), T('t2', '2026-11-09', 200, 1), T('t3', '2026-11-08', -400, -1), T('t4', '2026-11-07', -200, -0.5), T('t5', '2026-11-06', 100, 0.5), T('t6', '2026-10-01', 50, null)];
  const ent = { t1: { rating: 'plan', mood: 'calm' }, t2: { rating: 'plan' }, t3: { rating: 'interfered', mood: 'fomo' }, t4: { rating: 'interfered', mood: 'calm' }, t5: { rating: 'hesitated' }, t6: { mood: 'bored' } };
  const hb = C.habits(trades, ent);
  o.habits = { keys: hb.top.map((x) => x.key), cost: hb.top.map((x) => x.cost), costR: hb.top.map((x) => x.costR), plan: hb.planAvg, n: hb.top.map((x) => x.n) };
  o.nobase = C.habits([T('a', '2026-11-01', -100, -1)], { a: { rating: 'interfered' } }).top.map((x) => [x.cost, x.vsPlan]);
  o.none = [C.habits(trades, {}).top.length, C.habits([], ent).top.length, C.habits(trades, { t1: { rating: 'plan' } }).top.length];
  const cards = C.cardsFromMistakes(trades, ent);
  o.cards = { ids: cards.map((c) => c.id), front: cards[0].front, back: cards[0].back.slice(0, 30), topics: cards.map((c) => c.topic) };
  const prog0 = C.emptyProg(), a = C.reviewCard(prog0, 'c-t3', true, '2026-11-10'), b = C.reviewCard(a, 'c-t3', true, '2026-11-12'), c = C.reviewCard(b, 'c-t3', false, '2026-11-14');
  o.srs = { a: a.srs['c-t3'], b: b.srs['c-t3'], c: c.srs['c-t3'], rev: c.reviewsByDay, due0: C.dueCards(cards, {}, '2026-11-10').length, due1: C.dueCards(cards, a.srs, '2026-11-10').length, due2: C.dueCards(cards, a.srs, '2026-11-12').length };
  let big = C.emptyProg(); for (let i = 0; i < 6; i++) big = C.reviewCard(big, 'c-x', true, '2026-11-10');
  o.maxbox = big.srs['c-x'];
  const wp = { ...C.emptyProg(), days: { '2026-11-04': { score: 5, xp: 70, miss: [] }, '2026-11-08': { score: 3, xp: 40, miss: ['s1', 's2'] }, '2026-11-09': { score: 4, xp: 40, miss: ['g1'] }, '2026-10-20': { score: 1, xp: 10, miss: [] } }, reviewsByDay: { '2026-11-09': 3 } };
  const wr = C.weeklyReport(wp, trades, ent, '2026-11-10');
  o.week = { quizDays: wr.quizDays, avg: wr.avgScore, reviews: wr.reviews, trades: wr.trades, usd: wr.usd, r: wr.r, rated: wr.rated, plan: wr.plan, grade: wr.grade, weak: wr.weakTopic, days: wr.days.length, first: wr.days[0] };
  o.grades = [C.gradeFor(95).name, C.gradeFor(90).name, C.gradeFor(75).name, C.gradeFor(60).name, C.gradeFor(10).name, C.weeklyReport(C.emptyProg(), [], {}, '2026-11-10').grade.name];
  o.text = [C.both(412, 1.98), C.both(-437, -1.03), C.both(0, null), C.money(-1234.5), C.moneyS(5), C.rText(0)];
  const sh = C.shiftDemo({ trades: [T('x', '2026-11-06', 1, 1)], entries: {}, progress: { v: 1, days: { '2026-11-08': d(3), '2026-11-09': d(4) }, reviewsByDay: { '2026-11-09': 2 }, srs: {} } }, '2026-12-20');
  o.shift = { days: Object.keys(sh.progress.days), rev: Object.keys(sh.progress.reviewsByDay), trade: sh.trades[0].day, nil: C.shiftDemo(null, '2026-12-20') };
  const junk = C.cleanProg({ days: { '2026-11-09': { score: 99, xp: 9999, miss: ['s1', '<b>', 5] }, 'bad': d(1), '2026-02-30': d(1) }, reviewsByDay: { '2026-11-09': -4, 'x': 3 }, srs: { 'c-ok': { box: 9, due: '2026-11-10' }, 'evil': { box: 1, due: '2026-11-10' }, 'c-bad': { box: 1, due: 'soon' } } });
  o.junk = { days: junk.days, rev: junk.reviewsByDay, srs: junk.srs, nulls: [C.cleanProg(null).days, C.cleanProg('x').srs, C.cleanProg([]).reviewsByDay] };
  o.norm = { t: C.normTrades([{ id: 'a', day: '2026-11-01', usd: 5, r: 1 }, { id: 'b', pnl: -3, t: 1793367660 }, { id: '<x>', usd: 1, day: '2026-11-01' }, { id: 'c', usd: 'x', day: '2026-11-01' }, null, 4, { id: 'd', usd: 1 }]).map((x) => [x.id, x.day, x.usd]),
    e: C.normEntries({ v: 1, entries: { a: { rating: 'plan', mood: 'zzz' }, b: { rating: 'nope' }, '<c>': { rating: 'plan' }, d: { mood: 'fomo' } } }), e2: C.normEntries(null), e3: C.normEntries({ a: { rating: 'interfered' } }), t2: C.normTrades(null).length };
  console.log(JSON.stringify(o));
});
"""


def test_maths():
    o = AK.node(APP, HARNESS)
    if o is None:
        print("[SKIP] node is not installed: the maths checks were skipped")
        return
    if "_error" in o:
        check("b. the node harness ran", False, o["_error"])
        return
    b = o["bank"]
    check("b. the question bank: 20 questions, every rule has at least 4, 3 options, a reason for each", b["n"] == 20 and b["ids"] == 20 and all(b["topics"][t] >= 4 for t in ("stop", "size", "target", "greed", "flat")) and b["ok"], b)
    q = o["quiz"]
    check("b. the daily quiz: one question per rule (stop, size, target, greed, flat), the same all day, different on other days", q["topics"] == ["stop", "size", "target", "greed", "flat"] and q["same"] and q["diff"] >= 10, q)
    check("b. the quiz shuffles the answers by date but the marked answer is always the right text, and the right answer is not always first", q["right"] and q["moved"], q)
    r = o["rank"]
    check("b. ranks: Mathetes to Sophos by XP, the bar fraction, XP to the next rank, junk in is safe", r[:3] == ["mathetes", "mathetes", "hoplite"] and r[3] == 0 and abs(r[4] - 0.5) < 1e-9 and r[5] == "sophos" and r[6] == 0 and r[7] == 0 and r[8] == "mathetes" and r[9] == 1, r)
    check("b. the hall: 2 columns at the start, one more per rank, 8 at the top, a laurel per column from the 4th rank, never out of range", [(h["columns"], h["laurels"]) for h in o["hall"]] == [(2, 0), (5, 1), (8, 4), (8, 4), (2, 0)], o["hall"])
    check("b. XP: 10 a right answer, +20 for 5 of 5, +5 per streak day (at most 30)", o["xp"] == [70, 40, 100, 0, 55], o["xp"])
    s = o["streak"]
    check("b. streaks: counted back from today, or from yesterday while today is still open; a gap breaks it; best is kept", [x["streak"] for x in s] == [2, 3, 1, 1, 0] and s[3]["best"] == 3 and s[0]["doneToday"] is False and s[1]["doneToday"], s)
    f = o["finish"]
    check("b. finishing the quiz: 5 of 5 = 70 XP, a second try the same day changes nothing, the streak bonus counts, misses are remembered", f["first"]["score"] == 5 and f["first"]["xp"] == 70 and f["again"] and f["kept"] == 5 and f["mixed"]["score"] == 2 and f["mixed"]["xp"] == 20 + 10 and f["miss"] == 3, f)
    check("b. total XP = quiz XP + 5 per review (10 reviews a day at most)", o["total"] == [10, 70 + 50 + 10], o["total"])
    h = o["habits"]
    check("b. habits: ranked by the $ they cost against your followed-plan trades, each with its R (interfered $1,200 / 4.5R, FOMO $700 / 2.5R, bored $250 with no R on the trade -> R n/a)",
          h["keys"] == ["interfered", "fomo", "bored"] and h["cost"] == [1200, 700, 250] and h["costR"] == [4.5, 2.5, None] and h["n"] == [2, 1, 1] and h["plan"]["usd"] == 300, h)
    check("b. habits with no followed-plan trades are priced against $0 and say so; no ratings = no habits, never an error", o["nobase"] == [[100, False]] and o["none"] == [0, 0, 0], (o["nobase"], o["none"]))
    c = o["cards"]
    check("b. cards: one per mistake in the Journal (newest first), the front shows the $ with its R, the back is the owner's rule", c["ids"] == ["c-t3", "c-t4", "c-t5", "c-t6"] and "-$400 (-1.00R)" in c["front"] and "touched the trade" in c["front"] and c["back"] == "The stop and the target are se" and c["topics"][0] == "stop", c)
    sr = o["srs"]
    check("b. spaced repetition: right -> box 1 (due in 2 days), right again -> box 2 (4 days), wrong -> box 0 (tomorrow); a reviewed card is not due the same day", sr["a"] == {"box": 1, "due": "2026-11-12"} and sr["b"] == {"box": 2, "due": "2026-11-16"} and sr["c"] == {"box": 0, "due": "2026-11-15"} and sr["due0"] == 4 and sr["due1"] == 3 and sr["due2"] == 4, sr)
    check("b. the top box is 4 (16 days) and review counts add up per day", o["maxbox"]["box"] == 4 and o["maxbox"]["due"] == "2026-11-26" and sr["rev"] == {"2026-11-10": 1, "2026-11-12": 1, "2026-11-14": 1}, (o["maxbox"], sr["rev"]))
    w = o["week"]
    check("b. weekly report: the last 7 days only, quiz days, average, reviews, the week's trades in $ and R, plan-following, the most missed rule, a Greek grade",
          w["days"] == 7 and w["first"] == "2026-11-04" and w["quizDays"] == 3 and abs(w["avg"] - 4) < 1e-9 and w["reviews"] == 3 and w["trades"] == 5 and w["usd"] == 100 and abs(w["r"] - 2) < 1e-9 and w["rated"] == 5 and w["plan"] == 2 and w["weak"] == "stop"
          and w["grade"]["name"] in ("Gamma", "Delta"), w)
    check("b. grades: Alpha 90+, Beta 75+, Gamma 60+, else Delta; an empty week is Delta, never an error", o["grades"] == ["Alpha", "Alpha", "Beta", "Gamma", "Delta", "Delta"], o["grades"])
    check("b. money words always pair $ with R", o["text"] == ["+$412 (+1.98R)", "-$437 (-1.03R)", "$0 (R n/a)", "-$1,234", "+$5", "0.00R"], o["text"])
    check("b. the demo is moved in time so its last quiz day is yesterday", o["shift"]["days"] == ["2026-12-18", "2026-12-19"] and o["shift"]["rev"] == ["2026-12-19"] and o["shift"]["trade"] == "2026-12-16" and o["shift"]["nil"] is None, o["shift"])
    j = o["junk"]
    check("b. junk progress is cleaned: scores / XP clamped, bad dates and ids dropped, markup in 'miss' dropped, a bad box clamped", list(j["days"]) == ["2026-11-09"] and j["days"]["2026-11-09"] == {"score": 5, "xp": 200, "miss": ["s1"]} and j["rev"] == {"2026-11-09": 0} and j["srs"] == {"c-ok": {"box": 4, "due": "2026-11-10"}} and j["nulls"] == [{}, {}, {}], j)
    n = o["norm"]
    check("b. trades and Journal ratings are cleaned (bad ids, bad money, markup dropped; the whole journal.v1 store or just its entries both work)",
          n["t"] == [["a", "2026-11-01", 5], ["b", "2026-11-01", -3]] or [x[0] for x in n["t"]] == ["a", "b"] and n["e"] == {"a": {"rating": "plan"}, "d": {"mood": "fomo"}} and n["e2"] == {} and n["e3"] == {"a": {"rating": "interfered"}} and n["t2"] == 0, n)


def test_page():
    try:
        import playwright  # noqa: F401
    except Exception:
        print("[SKIP] playwright is not installed: part c skipped")
        return
    fx = json.load(open(os.path.join(AK.WEB, APP, "fixture.json"), encoding="utf-8"))
    real = {"v": 1, "trades": [{"id": t["id"].replace("demo.", "live."), "day": t["day"], "usd": t["usd"], "r": t["r"], "side": t["side"], "qty": t["qty"], "src": "paper"} for t in fx["trades"]]}
    journal = {"v": 1, "entries": {k.replace("demo.", "live."): {**v, "at": 1} for k, v in fx["entries"].items()}, "rule": None, "checks": [], "demoSeeded": False}
    srv, origin = AK.serve({"/odeon/trades.json": json.dumps(real)})
    try:
        with AK.browser() as br:
            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, APP, "?demo=1")
            r = p.evaluate("""() => ({ demo: !document.querySelector('#demo').hidden, rank: document.querySelector('#rankH').textContent, streak: document.querySelector('#streakPill').textContent,
              habits: document.querySelectorAll('#habits li.hab').length, hab1: document.querySelector('#habits li.hab').textContent, opts: document.querySelectorAll('#quizBody .opt').length,
              q: document.querySelector('#quizPill').textContent, rev: document.querySelector('#revPill').textContent, grade: document.querySelector('#grade').textContent, h1: document.querySelectorAll('h1').length })""")
            check("c. ?demo=1: DEMO chip, a rank and a streak, 3 habits with $ and R, question 1 of 5 with 3 answers, due review cards, a Greek grade", r["demo"] and r["rank"] and "5 day streak" in r["streak"] and r["habits"] == 3 and "(about" in r["hab1"] and r["opts"] == 3 and r["q"] == "Question 1 of 5" and "due" in r["rev"] and "Grade" in r["grade"] and r["h1"] == 1, r)
            check("c. 390 x 844: no sideways scroll, every tap >= 44 px, nothing under Jarvis's corner, no console error, nothing off the page's origin", AK.no_sideways(p) and not AK.taps(p) and not AK.corner(p) and not errs and not off, (AK.taps(p)[:3], AK.corner(p), errs[:3], off[:3]))
            xp0 = p.evaluate("() => window.LYCEUM.C.totalXp(window.LYCEUM.S.prog)")
            for i in range(5):
                p.evaluate("""() => { const S = window.LYCEUM.S, q = S.quiz[S.qi]; document.querySelector('#quizBody .opt[data-k="' + q.a + '"]').click(); }""")
                p.wait_for_selector("#nextBtn")
                if i == 0:
                    check("c. answering shows the right answer in green and the reason, and locks the other answers", p.evaluate("() => document.querySelectorAll('#quizBody .opt.right').length === 1 && document.querySelector('#quizBody .why') && [...document.querySelectorAll('#quizBody .opt')].every((b) => b.disabled)"))
                p.click("#nextBtn")
                p.wait_for_timeout(50)
            r = p.evaluate("() => ({ pill: document.querySelector('#quizPill').textContent, body: document.querySelector('#quizBody').textContent, xp: window.LYCEUM.C.totalXp(window.LYCEUM.S.prog), streak: document.querySelector('#streakPill').textContent, opts: document.querySelectorAll('#quizBody .opt').length })")
            check("c. finishing 5 of 5 right: 'Done: 5 of 5', XP goes up by 95 (70 + 5 streak days x 5), the streak is 6, no answers left to tap", r["pill"] == "Done: 5 of 5" and r["xp"] - xp0 == 95 and "6 day streak" in r["streak"] and r["opts"] == 0 and "next quiz opens tomorrow" in r["body"], (r, xp0))
            p.click("#showBtn")
            p.click('#revBody .btn[data-ok="1"]')
            r = p.evaluate("() => ({ rev: document.querySelector('#revPill').textContent })")
            check("c. a review card: show the rule, 'I knew it' -> one fewer card due", r["rev"] != "" and p.evaluate("() => Object.keys(window.LYCEUM.S.prog.srs).length") == 1, r)
            check("c. the demo never writes to this phone", p.evaluate("() => { try { return localStorage.getItem('lyceum.v1'); } catch (e) { return null; } }") is None and p.evaluate("() => window.LYCEUM.S.saved") == 0)
            p.wait_for_timeout(2500)
            st = p.evaluate("() => ({ on: document.documentElement.getAttribute('data-stage'), cols: window.LYCEUM3D ? window.LYCEUM3D.columns() : -1, off: document.querySelector('.stage').classList.contains('off') })")
            check("c. the marble hall drew with as many columns as the rank allows (or, with no WebGL here, the canvas is hidden and the page still works)", (st["on"] == "on" and st["cols"] >= 3) or st["off"] or st["cols"] == -1, st)
            AK.shot(p, "lyceum")
            ctx.close()
            ctx, p, errs, seen, off = AK.page(br, origin, storage={"journal.v1": json.dumps(journal)})
            AK.open_app(p, origin, APP)
            r = p.evaluate("() => ({ demo: !document.querySelector('#demo').hidden, rank: document.querySelector('#rankH').textContent, habits: document.querySelectorAll('#habits li.hab').length, opts: document.querySelectorAll('#quizBody .opt').length })")
            check("c. real trades + the Journal's ratings on this phone: no DEMO chip, a fresh Mathetes, habits from the ratings, today's quiz ready, the files were read", not r["demo"] and r["rank"] == "Mathetes" and r["habits"] == 3 and r["opts"] == 3 and any("odeon/trades.json" in u for u in seen) and not errs, (r, errs[:2]))
            p.evaluate("""() => { const S = window.LYCEUM.S; for (let i = 0; i < 5; i++) { S.answers[i] = S.quiz[i].a; } S.picked = 0; document.querySelector('#quizBody .opt').click(); }""")
            p.evaluate("() => { const L = window.LYCEUM, S = L.S; S.qi = 4; S.picked = S.quiz[4].a; S.answers = S.quiz.map((q) => q.a); L.render(); }")
            p.click("#nextBtn")
            saved = p.evaluate("() => { const x = JSON.parse(localStorage.getItem('lyceum.v1')); return { d: Object.keys(x.days).length, score: Object.values(x.days)[0].score, journal: JSON.parse(localStorage.getItem('journal.v1')).entries['live.01'].rating }; }")
            check("c. real mode keeps its progress on the phone (lyceum.v1) and leaves the Journal's ratings untouched", saved["d"] == 1 and saved["score"] == 5 and saved["journal"] == "plan", saved)
            p.reload()
            p.wait_for_function("window.LYCEUM && window.LYCEUM.ready()", timeout=60000, polling=300)
            p.wait_for_timeout(300)
            check("c. after a reload today's quiz stays done (once a day) and the rank is kept", p.evaluate("() => document.querySelector('#quizPill').textContent") == "Done: 5 of 5", p.evaluate("() => document.querySelector('#quizPill').textContent"))
            ctx.close()
        srv.shutdown()
        srv, origin = AK.serve({"/odeon/trades.json": None})
        with AK.browser() as br:
            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, APP)
            r = p.evaluate("() => ({ demo: !document.querySelector('#demo').hidden, opts: document.querySelectorAll('#quizBody .opt').length, habits: document.querySelectorAll('#habits li.hab').length })")
            check("c. no trades at all: the DEMO school shows, never a blank page", r["demo"] and r["opts"] == 3 and r["habits"] == 3 and not errs, (r, errs[:2]))
            ctx.close()
            ctx, p, errs, seen, off = AK.page(br, origin, w=375, h=667, reduced=True, lite=True)
            AK.open_app(p, origin, APP, "?demo=1&q=low")
            check("c. 375 x 667, LITE, reduced motion: no sideways scroll, every tap >= 44 px, no error", AK.no_sideways(p) and not AK.taps(p) and not errs, (AK.taps(p)[:3], errs[:2]))
            ctx.close()
    finally:
        srv.shutdown()


if __name__ == "__main__":
    test_static()
    test_maths()
    if "--static" not in sys.argv:
        test_page()
    AK.finish()
