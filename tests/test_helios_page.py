"""HELIOS, the OLYMPUS morning briefing (tools/web_public/helios/, AGORA look, 2026-11-10): one scroll for 01:45 / 07:00 / 10:45 ET: how today looks (calm / busy / careful, from Pythia's events.json), drawdown left per
account, deals ending, the three most urgent Compass actions, the quiz status, one sentence of plan for the bots, a 'Copy as text' button, and a marble sun-disc rising over columns with a gold ray per good sign.

  a. static: the files, the kit lines, the AGORA look, read-only (the quiz progress is only read), the Jarvis card, the manifest, the DEMO fixture, the row in tools/new_apps.json
  b. the maths in node (helioscore.js), and its light copies AGREE with the real ones: Pythia's day rules (eventsOn / dayRisk) and Compass's urgent rules (ids, titles, urgency) on a set of scenarios
  c. Chromium 390 x 844: DEMO, the three briefing slots, Copy as text, the real files and quiz progress, broken and missing files fall back, 3D or flat sun (reduced motion = still), LITE, taps >= 44 px
    python -X utf8 -m tests.test_helios_page            (--static: parts a and b only)
"""
from __future__ import annotations

import json
import os
import re
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import agora_kit as AK  # noqa: E402

APP, NAME = "helios", "Helios"
check = AK.check
FIX = os.path.join(AK.WEB, APP, "fixture.json")
NOW = "2026-11-10T12:45:00Z"           # 07:45 New York
SCENES = {"stars", "smoke", "coins", "embers", "neurons", "skyline", "torches", "threads", "streaks", "bars", "leaves", "columns", "shards", "rings", "maze"}


def test_static():
    AK.static_kit(APP, NAME, reads=("../pythia/events.json", "../home.json", "../money/index.json"), storage=True)
    d = os.path.join(AK.WEB, APP)
    js = AK.read(os.path.join(d, "helios.js")) + AK.read(os.path.join(d, "helioscore.js"))
    check("a. the quiz progress is only READ (localStorage.getItem 'lyceum.v1'): no setItem / removeItem / clear / sessionStorage / indexedDB anywhere", "readLS('lyceum.v1')" in js and not re.search(r"localStorage\.(setItem|removeItem|clear)|sessionStorage|indexedDB", js))
    check("a. the 3D files: sun.js (render core) and sunload.js (its own module tag)", all(os.path.isfile(os.path.join(d, n)) for n in ("sun.js", "sunload.js")))
    sj = AK.read(os.path.join(d, "sun.js"))
    check("a. sun.js: on the OLYMPUS render core, AGORA look, bloom <= .25, no network, no markup from data, reduced motion keeps the sun still",
          "../olympus/render.js" in sj and "../jarvis/three.module.min.js" in sj and not AK.BANNED_LOOK.search(sj) and not re.search(r"fetch\(|innerHTML|XMLHttpRequest|https?://", sj) and all(float(x) <= 0.25 for x in re.findall(r"bloom: \{ strength: ([\d.]+)", sj)) and "if (!reduced)" in sj)
    html = AK.read(os.path.join(d, "index.html"))
    check("a. sunload.js before helios.js; a canvas AND a flat svg sunrise; page order: today looks, drawdown, do first, deals, quiz, plan, copy",
          html.index("sunload.js") < html.index('src="helios.js') and 'id="stage"' in html and 'id="flat"' in html and html.index('id="lookWord"') < html.index('id="accts"') < html.index('id="acts"') < html.index('id="deals"') < html.index('id="quiz"') < html.index('id="plan"') < html.index('id="copy"'))
    check("a. Helios only informs: no POST, no window.open, nothing bought or traded", not re.search(r"method:\s*['\"]POST|window\.open|location\.href\s*=", js))
    fx = json.load(open(FIX, encoding="utf-8"))
    check("a. the fixture (days and hours counted from now): a CPI day with a medium release, three accounts, a deal ending in 5 h, a quiz not done with a 3-day streak",
          fx["events"][0]["kind"] == "cpi" and fx["events"][0]["impact"] == "high" and len(fx["home"]["accounts"]) == 3 and fx["money"]["streams"][0]["items"][0]["expires_in_h"] == 5 and fx["quiz"] == {"done_today": False, "streak": 3})
    na = json.load(open(os.path.join(AK.ROOT, "tools", "new_apps.json"), encoding="utf-8"))
    row = next((a for a in na["apps"] if a["id"] == APP), None)
    check("a. the row in tools/new_apps.json: group trading, a description under 80 characters, an existing intro scene, a transition, an ambient bed, an accent and a glyph (--apply is for the lead)",
          row is not None and row["group"] == "trading" and len(row["description"]) < 80 and row["flavour"][0] in SCENES and len(row["flavour"]) == 3 and row["transition"]["kind"] and row["ambient"] and re.match(r"^#[0-9a-f]{6}$", row["accent"]) and row["glyph"], row)


HARNESS = r"""
import(process.argv[2]).then(async (C) => {
  const fs = require('fs'), fx = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
  const CP = await import(process.argv[4]), PY = await import(process.argv[5]);
  const now = Date.parse('2026-11-10T12:45:00Z'), H = 3600000, D = 86400000, o = {};
  o.words = [C.money(2000), C.money(-60), C.moneyS(312), C.rWord(312, 425), C.rWord(-60, 150, true), C.both(312, 425, false), C.drawdownLine(1420, 2000), C.hoursText(0.4), C.hoursText(5), C.hoursText(72), C.timeWord('08:30'), C.timeWord('14:00'), C.timeWord('00:05'), C.timeWord('x')];
  o.clock = [C.etParts(now), C.etParts(Date.parse('2026-11-10T06:45:00Z')), C.etParts(Date.parse('2026-07-10T05:45:00Z')), C.slotOf(Date.parse('2026-11-10T06:45:00Z')).key, C.slotOf(Date.parse('2026-11-10T12:00:00Z')).key, C.slotOf(Date.parse('2026-11-10T15:45:00Z')).key, C.slotOf(now, 'pre').key, C.slotOf(now, 'zzz').key, C.slotOf(Date.parse('2026-11-10T10:30:00Z')).key, C.slotOf(Date.parse('2026-11-10T14:29:00Z')).key, C.slotOf(Date.parse('2026-11-10T14:30:00Z')).key];
  const ev = (over) => ({ v: 1, weekly: [], events: [], ...over });
  const look = (j) => C.lookOf(j, '2026-11-10');
  const L = [look(null).look, look(ev({})).look, look(ev({ events: [{ date: '2026-11-10', time: '08:30', kind: 'cpi', title: 'CPI', impact: 'high' }] })).look, look(ev({ events: [{ date: '2026-11-10', time: '10:00', kind: 'other', title: 'CB', impact: 'med' }] })).look,
    look(ev({ events: [{ date: '2026-11-10', kind: 'other', title: 'x', impact: 'low' }] })).look, look(ev({ events: [{ date: '2026-11-10', kind: 'holiday', title: 'Closed', impact: 'low', closed: true }] })).look, look(ev({ events: [{ date: '2026-11-10', kind: 'early', title: 'Early close', impact: 'low', close_et: '13:15' }] })).look,
    look(ev({ events: [{ date: '2026-11-11', kind: 'cpi', title: 'tomorrow', impact: 'high' }] })).look, look(ev({ weekly: [{ kind: 'claims', title: 'Jobless claims', dow: 2, time: '08:30', impact: 'low' }] })).look, look(ev({ weekly: [{ kind: 'claims', title: 'Jobless claims', dow: 2, time: '08:30', impact: 'low', skip: ['2026-11-10'] }] })).events.length];
  o.look = L;
  const cpi = look(ev({ events: [{ date: '2026-11-10', time: '08:30', kind: 'cpi', title: 'CPI (consumer prices)', impact: 'high' }, { date: '2026-11-10', time: '10:00', kind: 'other', title: 'CB Consumer Confidence', impact: 'med' }] }));
  o.cpi = [cpi.look, cpi.why, cpi.events.map((e) => e.time), C.lookWords(cpi), look(null).have, look(ev({})).have, look(ev({})).why];
  // agreement with Pythia's real rules
  const pyN = PY.normEvents({ v: 1, updated: '2026-11-10', events: [
      { date: '2026-11-10', time: '08:30', kind: 'cpi', title: 'CPI', impact: 'high' }, { date: '2026-11-10', time: '10:00', kind: 'other', title: 'CB', impact: 'med' }, { date: '2026-11-11', time: '14:00', kind: 'fomc', title: 'FOMC', impact: 'high' },
      { date: '2026-11-12', kind: 'holiday', title: 'Closed', impact: 'low', closed: true }, { date: '2026-11-13', kind: 'early', title: 'Early close', impact: 'low', close_et: '13:15' }, { date: '2026-11-14', time: '09:00', kind: 'other', title: 'light', impact: 'low' }],
    weekly: [{ kind: 'claims', title: 'Jobless claims', dow: 4, time: '08:30', impact: 'low', skip: ['2026-11-20'] }] });
  const raw = { v: 1, events: [
      { date: '2026-11-10', time: '08:30', kind: 'cpi', title: 'CPI', impact: 'high' }, { date: '2026-11-10', time: '10:00', kind: 'other', title: 'CB', impact: 'med' }, { date: '2026-11-11', time: '14:00', kind: 'fomc', title: 'FOMC', impact: 'high' },
      { date: '2026-11-12', kind: 'holiday', title: 'Closed', impact: 'low', closed: true }, { date: '2026-11-13', kind: 'early', title: 'Early close', impact: 'low', close_et: '13:15' }, { date: '2026-11-14', time: '09:00', kind: 'other', title: 'light', impact: 'low' }],
    weekly: [{ kind: 'claims', title: 'Jobless claims', dow: 4, time: '08:30', impact: 'low', skip: ['2026-11-20'] }] };
  const days = ['2026-11-09', '2026-11-10', '2026-11-11', '2026-11-12', '2026-11-13', '2026-11-14', '2026-11-19', '2026-11-20', '2026-11-21'];
  o.pyAgree = days.map((d) => { const a = PY.eventsOn(pyN, d), b = C.eventsOn(raw, d); return [d, a.length === b.length && a.every((e, i) => e.title === b[i].title && (e.time || '') === (b[i].time || '')), PY.dayRisk(a), C.dayRisk(b)]; });
  // the accounts
  const home = { accounts: [{ id: 'mffu50k_eval', kind: 'eval', conn: { connected: true }, eval: { room: 1420, mll: 2000, dll: 1000, dll_used: 100 }, pnl: { today: 312 } }, { id: 'acctb', eval: { room: 240, mll: 1000, dll: 600, dll_used: 60 }, stats: { avg_loss: -150 }, pnl: { today: -60 } }] };
  const ac = C.buildAccounts(home);
  o.acc = [ac.have, ac.accounts.map((a) => [a.key, a.has, a.room, a.mll, a.risk, a.est, C.health(a)]), ac.accounts.map(C.accountLine)];
  o.accEmpty = [C.buildAccounts(null).have, C.buildAccounts({ accounts: 'x' }).accounts.every((a) => !a.has), C.accountLine(C.buildAccounts(null).accounts[2]), C.health(C.buildAccounts(null).accounts[0])];
  o.health = [C.health(C.accountView('zlarior', { eval: { room: 1500, mll: 2000 } })), C.health(C.accountView('zlarior', { eval: { room: 900, mll: 2000 } })), C.health(C.accountView('zlarior', { eval: { room: 400, mll: 2000 } })), C.health(C.accountView('zlarior', { eval: { room: 0, mll: 2000 } })), C.health(C.accountView('zlarior', { eval: { room: 1500, mll: 2000, dll: 1000, dll_used: 850 } }))];
  const money = (h, st) => ({ streams: [{ id: 'mercury', name: 'Mercury', status: st || 'ok', items: [{ title: 'Sale', usd: 60, score: 75, expires: new Date(now + h * H).toISOString() }, { title: 'Other', usd: 5, expires: new Date(now + 90 * H).toISOString() }, { title: 'No date' }] }] });
  o.deals = [C.dealsEnding(money(5), now).map((d) => [d.title, Math.round(d.hours), d.usd, d.stream]), C.dealsEnding(money(60), now).length, C.dealsEnding(money(-2), now).length, C.dealsEnding(money(5, 'sample'), now).length, C.dealsEnding(null, now).length, C.dealsEnding({ streams: [null, 5, { id: 'x', items: 'y' }] }, now).length];
  const lq = (days) => JSON.stringify({ v: 1, days });
  o.quiz = [C.quizStatus(lq({ '2026-11-10': { score: 4, xp: 40 }, '2026-11-09': { score: 5, xp: 50 }, '2026-11-08': { score: 3, xp: 30 } }), '2026-11-10'), C.quizStatus(lq({ '2026-11-09': { score: 5, xp: 50 }, '2026-11-08': { score: 3, xp: 30 } }), '2026-11-10'), C.quizStatus(lq({}), '2026-11-10'), C.quizStatus('nope', '2026-11-10'), C.quizStatus(null, '2026-11-10'), C.quizStatus('x'.repeat(500000), '2026-11-10'), C.quizStatus(lq({ '2026-11-10': { score: 99 } }), '2026-11-10').score];
  // the plan for the bots
  const calmLook = look(ev({})), carefulLook = cpi, closedLook = look(ev({ events: [{ date: '2026-11-10', kind: 'holiday', title: 'Closed', impact: 'low', closed: true }] })), busyLook = look(ev({ events: [{ date: '2026-11-10', time: '10:00', kind: 'other', title: 'CB', impact: 'med' }] }));
  const pl = [C.planSentence(calmLook, C.SLOTS.pre), C.planSentence(carefulLook, C.SLOTS.morning), C.planSentence(closedLook, C.SLOTS.ny), C.planSentence(busyLook, C.SLOTS.ny)];
  o.plan = [pl[0].startsWith('LIT trades its normal rules: entries 02:00 to 15:30 ET, at most one trade, the stop beyond the sweep with the size following the stop, the target banked at 8R, flat by 15:55 ET.'), pl[0].endsWith('Entries open at 02:00 ET.'), pl[1].includes('CPI (consumer prices) at 8:30 AM ET can move the price both ways') && pl[1].includes('no news pause'), pl[2], pl[3].includes('medium release'), pl[3].endsWith('then everything is flat by 15:55 ET.'), PY.RULES.entryFrom === C.LIT.entryFrom && PY.RULES.entryTo === C.LIT.entryTo && PY.RULES.flat === C.LIT.flat];
  // the whole briefing from the fixture
  const m = C.build(C.demoInputs(fx, now), now), m2 = C.build(C.demoInputs(fx, now), Date.parse('2026-11-10T06:45:00Z')), m3 = C.build(C.demoInputs(fx, now), Date.parse('2026-11-10T15:45:00Z'));
  o.demo = [m.look.look, m.look.why, m.slot.key, m2.slot.key, m3.slot.key, m.accounts.map((a) => a.has), m.actions.map((a) => a.id), m.deals.length, m.quiz, m.good, m.total, m.signs.map((s) => [s.id, s.ok]), m.rise];
  o.text = [m.text.split('\n').length, m.text.startsWith('Good morning. HELIOS, Morning briefing (07:00 ET), 2026-11-10.'), m.text.includes('Today looks careful. CPI (consumer prices) at 8:30 AM ET: the price can spike both ways.'), m.text.includes('- Zlarior 50K: Drawdown left $1,420 of $2,000 max loss. Today +$312 (~+0.7R). One full stop costs about $425 (1.0R, an estimate).'),
    m.text.includes('Deals ending:\n- Prop-firm sale: 30% off a 50K plan (Mercury), ends in 5 h, about $60 (estimate)'), m.text.includes('Quiz: not done today (3 day streak).'), m.text.includes('Plan for the bots: LIT trades its normal rules'), m.text.endsWith('it never trades.'), /\$-/.test(m.text), /[<>]/.test(m.text)];
  o.card = [C.jarvisCard(m), C.jarvisCard(C.build({}, now)).level];
  // agreement with Compass's real rules: the shared (urgent) rules give the same ids, titles and urgency
  const cmp = (inp) => {
    const real = CP.actions(CP.context(inp, now)).filter((a) => ['bots_off', 'dll_near', 'dd_low', 'dd_half', 'feeds_old', 'deal_soon', 'idle'].includes(a.id)), lite = C.actions(inp, now);
    const norm = (l) => l.map((a) => [a.id, a.title, a.urgency, a.usd]).sort((x, y) => (x[0] < y[0] ? -1 : 1));
    return JSON.stringify(norm(real)) === JSON.stringify(norm(lite)) ? true : [norm(real), norm(lite)];
  };
  const acct = (over) => ({ id: 'a', name: 'Zlarior', kind: 'eval', conn: { connected: true }, eval: { room: 1420, mll: 2000, dll: 1000, dll_used: 0, target: 3000, to_target: 2580 }, pnl: { today: 0 }, ...over });
  const homeOf = (...a) => ({ asof: new Date(now - H).toISOString(), accounts: a });
  const fresh = { streams: [{ id: 'chrysos', status: 'ok', age_min: 20, items: [] }] };
  const calm = { home: homeOf(acct({})), money: fresh };
  const scen = [calm, { ...calm, home: homeOf(acct({ conn: { connected: false } })) }, { ...calm, home: homeOf(acct({ eval: { room: 1420, mll: 2000, dll: 1000, dll_used: 850 } })) }, { ...calm, home: homeOf(acct({ eval: { room: 400, mll: 2000, dll: 1000, dll_used: 0 } })) },
    { ...calm, home: homeOf(acct({ eval: { room: 900, mll: 2000, dll: 1000, dll_used: 0 } })) }, { ...calm, home: null }, { ...calm, money: null }, { ...calm, home: { ...homeOf(acct({})), asof: new Date(now - 40 * H).toISOString() } },
    { ...calm, money: { streams: [{ id: 'oikos', status: 'stale', age_min: 700, items: [] }] } }, { ...calm, money: money(5) }, { ...calm, money: money(60) }, C.demoInputs(fx, now),
    { home: homeOf(acct({ conn: { connected: false }, eval: { room: 300, mll: 2000, dll: 1000, dll_used: 900 } })), money: money(4) }, { home: homeOf(acct({}), acct({ id: 'acctb', name: 'ATLAS', eval: { room: 240, mll: 1000, dll: 600, dll_used: 60 } })), money: fresh }];
  o.agree = scen.map(cmp);
  o.junk = [null, undefined, 'x', 5, [], {}, { events: 'x', home: 5, money: [], lyceum: 7 }, { home: { accounts: [null, { eval: 'x' }] }, money: { streams: [null] } }].map((j) => { try { const b = C.build(j, now); return [b.text.length > 50, ['calm', 'busy', 'careful'].includes(b.look.look), Number.isFinite(b.rise), b.actions.length <= 3]; } catch (e) { return String(e); } });
  console.log(JSON.stringify(o));
});
"""


def test_maths():
    tmp = tempfile.mkdtemp(prefix="helios-ref-")
    cp, py = os.path.join(tmp, "compasscore.mjs"), os.path.join(tmp, "pythiacore.mjs")
    shutil.copy(os.path.join(AK.WEB, "compass", "compasscore.js"), cp)
    shutil.copy(os.path.join(AK.WEB, "pythia", "pythiacore.js"), py)
    o = AK.node(APP, HARNESS, FIX, cp, py)
    if o is None:
        check("b. node is not installed: maths skipped", True)
        return
    check("b. no error in the harness", "_error" not in o, o.get("_error"))
    if "_error" in o:
        return
    check("b. words: $2,000, -$60, +$312, every dollar with its R (+0.7R, ~-0.4R for an estimate), '+$312 (+0.7R)', the exact drawdown sentence, hours, 8:30 AM ET, 2:00 PM ET, 12:05 AM ET, junk -> empty",
          o["words"] == ["$2,000", "-$60", "+$312", "+0.7R", "~-0.4R", "+$312 (+0.7R)", "Drawdown left $1,420 of $2,000 max loss", "under an hour", "5 h", "3 days", "8:30 AM ET", "2:00 PM ET", "12:05 AM ET", ""], o["words"])
    k = o["clock"]
    check("b. the New York clock (winter UTC-5, summer UTC-4): 07:45 on Nov 10, 01:45 and a summer 01:45; the slot is 01:45 before 05:00 ET, 07:00 before 09:30 ET, 10:45 after; a forced slot works, junk is ignored; the 05:30 and 09:29 edges stay 07:00",
          k[0] == {"ymd": "2026-11-10", "min": 465} and k[1] == {"ymd": "2026-11-10", "min": 105} and k[2] == {"ymd": "2026-07-10", "min": 105} and k[3:5] == ["pre", "morning"] and k[5] == "ny" and k[6] == "pre" and k[7] == "morning" and k[8] == "morning" and k[9] == "morning" and k[10] == "ny", k)
    check("b. how today looks: no file -> calm; nothing -> calm; a high-impact release -> careful; a medium one -> busy; a light one -> calm; a closed market -> careful; an early close -> careful; tomorrow's release does not count; a weekly rule on its day counts (calm), a skipped one does not",
          o["look"] == ["calm", "calm", "careful", "busy", "calm", "careful", "careful", "calm", "calm", 0], o["look"])
    c = o["cpi"]
    check("b. the CPI day: careful, 'CPI (consumer prices) at 8:30 AM ET: the price can spike both ways.', the events in time order, 'Today looks careful', no file says nothing is known (have false), an empty file says 'Nothing is scheduled today.'",
          c[0] == "careful" and c[1] == "CPI (consumer prices) at 8:30 AM ET: the price can spike both ways." and c[2] == ["08:30", "10:00"] and c[3] == "Today looks careful" and c[4] is False and c[5] is True and c[6] == "Nothing is scheduled today.", c)
    check("b. the light copy of Pythia's day rules AGREES with the real eventsOn / dayRisk on nine days (dated events, the weekly claims rule, its skip day, a closed day, an early close): same events, same order, same risk word where it matters",
          all(x[1] and x[2] == x[3] for x in o["pyAgree"]), o["pyAgree"])
    a = o["acc"]
    check("b. the accounts: Zlarior 'Drawdown left $1,420 of $2,000 max loss. Today +$312 (~+0.7R). One full stop costs about $425 (1.0R, an estimate).'; ATLAS uses its real $150 loss, so 'Today -$60 (-0.4R)' without '~'; BLITZ has no row",
          a[0] is True and a[1][0] == ["zlarior", True, 1420, 2000, 425, True, "ok"] and a[1][1] == ["atlas", True, 240, 1000, 150, False, "bad"] and a[1][2][1] is False
          and a[2][0] == "Zlarior 50K: Drawdown left $1,420 of $2,000 max loss. Today +$312 (~+0.7R). One full stop costs about $425 (1.0R, an estimate)." and a[2][1] == "ATLAS 25K: Drawdown left $240 of $1,000 max loss. Today -$60 (-0.4R). One full stop costs about $150 (1.0R)."
          and a[2][2] == "BLITZ 25K: no live numbers yet (max loss $1,000).", a)
    check("b. no home.json: three accounts without numbers, 'no live numbers yet', health 'off'; junk is safe", o["accEmpty"] == [False, True, "BLITZ 25K: no live numbers yet (max loss $1,000).", "off"], o["accEmpty"])
    check("b. health: safe / under half / under a quarter / used up / daily loss at 85%", o["health"] == ["ok", "warn", "bad", "bad", "bad"], o["health"])
    dl = o["deals"]
    check("b. deals ending: only within 48 h, soonest first, with the $ estimate and the stream; a deal in 60 h, an ended deal, an example stream, no file and junk give none", dl[0] == [["Sale", 5, 60, "Mercury"]] and dl[1:] == [0, 0, 0, 0, 0], dl)
    q = o["quiz"]
    check("b. the quiz (read only): done today with 4 of 5 and a 3-day streak; not done today (2 days so far); no progress -> known but not done; junk, null and a huge text -> not known; a silly score is clamped to 5",
          q[0] == {"known": True, "done": True, "score": 4, "streak": 3} and q[1] == {"known": True, "done": False, "score": None, "streak": 2} and q[2] == {"known": True, "done": False, "score": None, "streak": 0} and q[3]["known"] is False and q[4]["known"] is False and q[5]["known"] is False and q[6] == 5, q)
    p = o["plan"]
    check("b. the plan for the bots: the LIT rules in one sentence (entries 02:00 to 15:30 ET, one trade, the stop beyond the sweep, 8R banked, flat by 15:55 ET) + what the slot adds; a CPI day names the release and says LIT has no news pause; a closed market says nothing to do; the rules equal Pythia's",
          p[0] and p[1] and p[2] and p[3] == "The market is closed today: no signal and no trade. Nothing for the bots or for you to do." and p[4] and p[5] and p[6], p)
    d = o["demo"]
    check("b. the demo morning (07:45 ET): careful, the CPI sentence, the 07:00 briefing (01:45 and 10:45 at their hours), 3 accounts, the deal first and 'Do nothing' not shown (the deal and feeds outrank it), 1 deal, a quiz not done with a 3-day streak, 4 of 6 good signs, the sun at 0.767",
          d[0] == "careful" and d[1].startswith("CPI (consumer prices) at 8:30 AM ET") and d[2] == "morning" and d[3] == "pre" and d[4] == "ny" and d[5] == [True, True, True] and d[6][0] == "deal_soon" and d[7] == 1 and d[8] == {"known": True, "done": False, "score": None, "streak": 3} and d[10] == 6
          and d[9] == sum(1 for s in d[11] if s[1]) and abs(d[12] - round(0.2 + 0.7 * d[9] / 6, 3)) < 1e-9, d)
    t = o["text"]
    check("b. 'Copy as text': a plain multi-line text with the greeting, today's look, every account with its R, the deal, the quiz, the plan and the 'never trades' line; no '$-', no markup", t[0] >= 18 and all(t[1:8]) and t[8] is False and t[9] is False, t)
    check("b. the Jarvis helper card: Helios, 'careful' look, 'N of 6' good signs, the line names the top action; an empty briefing is still a card", o["card"][0]["name"] == "Helios" and o["card"][0]["look"] == "careful" and o["card"][0]["good"].endswith("of 6") and o["card"][0]["line"].startswith("Today looks careful.") and o["card"][1] in ("ok", "warn"), o["card"])
    ag = o["agree"]
    check("b. the light copy of Compass's urgent rules AGREES with the real compasscore.js on 14 scenarios (calm, bot off, daily loss, drawdown low / half, files missing / old, a stale stream, a deal ending, the demo, everything at once, two accounts): same rule ids, titles, urgency and $ for the shared rules",
          all(x is True for x in ag), [x for x in ag if x is not True][:1])
    check("b. junk in, never a throw: null, text, numbers, arrays, empty, broken files all give a briefing with a look, a text and at most 3 actions", all(x == [True, True, True, True] for x in o["junk"]), o["junk"])


def test_page():
    try:
        import playwright  # noqa: F401
    except ImportError:
        check("c. page tests skipped: no Playwright", True)
        return
    srv, origin = AK.serve()
    try:
        with AK.browser() as br:
            ctx, p, errs, seen, off = AK.page(br, origin)
            ctx.grant_permissions(["clipboard-read", "clipboard-write"], origin=origin)
            AK.open_app(p, origin, APP, f"?demo=1&now={NOW}", hook="HELIOS")
            d = p.evaluate("""() => ({ demo: !document.querySelector('#demo').hidden, sub: document.querySelector('#sub').textContent, pill: document.querySelector('#pill').textContent, word: document.querySelector('#lookWord').textContent,
              why: document.querySelector('#lookWhy').textContent, evs: [...document.querySelectorAll('#events li')].map((l) => l.textContent), signs: document.querySelector('#signs').textContent, accts: [...document.querySelectorAll('#accts .item')].map((l) => l.textContent),
              acts: [...document.querySelectorAll('#acts .item b')].map((l) => l.textContent), tags: [...document.querySelectorAll('#acts .pill')].map((l) => l.textContent), deals: [...document.querySelectorAll('#deals .item')].map((l) => l.textContent), quiz: document.querySelector('#quiz').textContent,
              quizPill: document.querySelector('#quizPill').textContent, plan: document.querySelector('#plan').textContent, font: getComputedStyle(document.querySelector('h1')).fontFamily, bg: getComputedStyle(document.body).backgroundColor, mode: window.HELIOS.mode, text: document.querySelector('#text').textContent })""")
            check("c. DEMO (Nov 10, 07:45 ET): the chip, the 07:00 briefing, 'careful', 'Good morning. Today looks careful.', the CPI why, two events in time order, three accounts each with 'Drawdown left $X of $Y max loss' and an R, three actions (the $60 deal first), the deal, 'Not yet' for the quiz with a 3-day streak, the LIT plan",
                  d["demo"] and d["sub"] == "Morning briefing, 07:00 ET" and d["pill"] == "careful" and d["word"] == "Good morning. Today looks careful." and d["why"].startswith("CPI (consumer prices) at 8:30 AM ET") and d["evs"][0].startswith("8:30 AM ET: CPI") and d["evs"][1].startswith("10:00 AM ET: CB Consumer Confidence")
                  and len(d["accts"]) == 3 and "Drawdown left $1,420 of $2,000 max loss. Today +$312 (~+0.7R)" in d["accts"][0] and len(d["acts"]) == 3 and d["acts"][0].startswith("1. A deal ends in 5 h") and d["tags"][0] == "$60 (est.)" and "free" in d["tags"] and len(d["deals"]) == 1
                  and d["quizPill"] == "Not yet" and "3 days in a row" in d["quiz"] and d["plan"].startswith("LIT trades its normal rules: entries 02:00 to 15:30 ET") and "good signs" in d["signs"], d)
            check("c. AGORA look: serif title, warm dark body", any(f in d["font"] for f in ("Palatino", "Iowan", "Georgia")) and d["bg"] == "rgb(20, 17, 14)", d)
            check("c. the sun is 3D or the flat sunrise, never nothing", d["mode"] in ("3d", "flat") and p.evaluate("() => document.querySelector('#stage').hidden !== document.querySelector('#flat').hasAttribute('hidden')"), d["mode"])
            rays = p.evaluate("() => document.querySelectorAll('#flat line.ray').length")
            check("c. the flat sunrise has one gold ray for each good sign", rays == int(re.search(r"(\d) of 6", d["signs"]).group(1)), (rays, d["signs"]))
            AK.shot(p, "helios-demo")
            p.locator("#copy").click()
            p.wait_for_timeout(400)
            cl = p.evaluate("async () => { try { return await navigator.clipboard.readText(); } catch (e) { return 'ERR ' + e.message; } }")
            st = p.evaluate("() => [document.querySelector('#copy').textContent, document.querySelector('#status').textContent]")
            check("c. 'Copy as text' puts the whole briefing on the clipboard (the same text as 'The text' below), the button says Copied and the status line is spoken; when the clipboard is blocked the text is opened to select",
                  (cl == d["text"] and st[0] == "Copied" and "Copied." in st[1]) or (cl.startswith("ERR") and "Could not copy" in st[1] and p.evaluate("() => document.querySelector('#textBox').open")), (cl[:80], st))
            check("c. the text has the greeting, every account with its R, the deal and the plan", d["text"].startswith("Good morning. HELIOS, Morning briefing (07:00 ET), 2026-11-10.") and "(~+0.7R)" in d["text"] and "Prop-firm sale" in d["text"] and "Plan for the bots:" in d["text"] and "$-" not in d["text"], d["text"][:200])
            t = AK.taps(p)
            check("c. every tap target is at least 44 x 44 px (Copy as text, 'The text', the page)", not t, t[:5])
            check("c. no sideways scroll; Jarvis's corner is free; no console error; nothing off the origin", AK.no_sideways(p) and not AK.corner(p) and not errs and not off, (errs[:3], off[:3]))
            ctx.close()

            for slot, hour, sub, hello in (("pre", "2026-11-10T06:45:00Z", "Before London briefing, 01:45 ET", "Good night, early bird"), ("ny", "2026-11-10T15:45:00Z", "Before the New York afternoon briefing, 10:45 ET", "Good day")):
                ctx, p, errs, seen, off = AK.page(br, origin)
                AK.open_app(p, origin, APP, f"?demo=1&now={hour}", hook="HELIOS")
                r = p.evaluate("() => [document.querySelector('#sub').textContent, document.querySelector('#lookWord').textContent, document.querySelector('#plan').textContent]")
                check(f"c. the {slot} briefing ({hour[11:16]} UTC): '{sub}', '{hello}', its own line in the plan", r[0] == sub and r[1].startswith(hello) and (r[2].endswith("Entries open at 02:00 ET.") if slot == "pre" else r[2].endswith("flat by 15:55 ET.")) and not errs, r)
                ctx.close()

            ctx, p, errs, seen, off = AK.page(br, origin)
            AK.open_app(p, origin, APP, f"?demo=1&q=high&now={NOW}", hook="HELIOS")
            hq = p.evaluate("() => [window.HELIOS.mode, getComputedStyle(document.querySelector('#flat')).display, window.HELIOS.sun ? window.HELIOS.sun.rays : null]")
            check("c. ?q=high: the 3D sun builds with its rays and the flat drawing is hidden (or, with no WebGL, the flat sunrise stays), no console error", ((hq[0] == "3d" and hq[1] == "none" and hq[2] is not None) or (hq[0] == "flat" and hq[1] != "none")) and not errs, (hq, errs[:2]))
            ctx.close()

            ctx, p, errs, seen, off = AK.page(br, origin, reduced=True)
            AK.open_app(p, origin, APP, f"?demo=1&q=high&now={NOW}", hook="HELIOS")
            rr = p.evaluate("() => window.HELIOS.mode === '3d' ? [window.HELIOS.sun.rise, window.HELIOS.sun.settled] : null")
            check("c. reduced motion: the 3D sun stands still at once (settled, already at its height), no animation to wait for", rr is None or (rr[1] is True and rr[0] > 0.2), rr)
            ctx.close()

            events = {"v": 1, "updated": "2026-11-10", "weekly": [], "events": [{"date": "2026-11-10", "time": "14:00", "kind": "fomc", "title": "FOMC decision", "impact": "high"}]}
            home = {"asof": "2026-11-10T12:30:00Z", "accounts": [{"id": "mffu50k_eval", "conn": {"connected": True}, "eval": {"room": 1420, "mll": 2000, "dll": 1000, "dll_used": 0}, "pnl": {"today": 0}}]}
            money = {"streams": [{"id": "mercury", "name": "Mercury", "status": "ok", "age_min": 20, "items": [{"title": "Plan sale", "usd": 50, "expires": "2026-11-10T19:00:00Z"}]}]}
            lyc = json.dumps({"v": 1, "days": {"2026-11-10": {"score": 5, "xp": 50, "miss": []}, "2026-11-09": {"score": 4, "xp": 40, "miss": []}}})
            srv2, origin2 = AK.serve({"/pythia/events.json": json.dumps(events), "/home.json": json.dumps(home), "/money/index.json": json.dumps(money)})
            ctx, p, errs, seen, off = AK.page(br, origin2, storage={"lyceum.v1": lyc})
            AK.open_app(p, origin2, APP, f"?now={NOW}", hook="HELIOS")
            r = p.evaluate("() => ({ demo: !document.querySelector('#demo').hidden, pill: document.querySelector('#pill').textContent, why: document.querySelector('#lookWhy').textContent, quiz: document.querySelector('#quiz').textContent, quizPill: document.querySelector('#quizPill').textContent, ls: localStorage.getItem('lyceum.v1'), acts: [...document.querySelectorAll('#acts .item b')].map((l) => l.textContent) })")
            check("c. the real files and this phone's quiz progress: no DEMO chip, an FOMC day is careful ('FOMC decision at 2:00 PM ET'), the quiz is done today (5 of 5, 2 days in a row), the real deal (ends in 6 h) is the first action, the quiz progress is untouched",
                  not r["demo"] and r["pill"] == "careful" and r["why"].startswith("FOMC decision at 2:00 PM ET") and r["quizPill"] == "Done today" and "5 of 5" in r["quiz"] and "2 days in a row" in r["quiz"] and r["ls"] == lyc and r["acts"][0].startswith("1. A deal ends in 6 h: Plan sale"), r)
            check("c. the real run reads the three files and no console error", all(any(f in u for u in seen) for f in ("pythia/events.json", "home.json", "money/index.json")) and not off and not errs, (off[:3], errs[:3]))
            ctx.close()
            srv2.shutdown()

            srv3, origin3 = AK.serve({"/pythia/events.json": "not json", "/home.json": '{"accounts": "junk"}', "/money/index.json": "[]"})
            ctx, p, errs, seen, off = AK.page(br, origin3)
            AK.open_app(p, origin3, APP, f"?now={NOW}", hook="HELIOS")
            r = p.evaluate("() => [document.querySelector('#pill').textContent, document.querySelectorAll('#accts .item').length, document.querySelector('#text').textContent.length]")
            check("c. broken files never blank the page: a calm day, three accounts without numbers, a text to copy, no console error", r[0] == "calm" and r[1] == 3 and r[2] > 200 and not errs, (r, errs[:2]))
            ctx.close()
            srv3.shutdown()

            srv4, origin4 = AK.serve({"/pythia/events.json": None, "/home.json": None, "/money/index.json": None})
            ctx, p, errs, seen, off = AK.page(br, origin4)
            AK.open_app(p, origin4, APP, f"?now={NOW}", hook="HELIOS")
            r = p.evaluate("() => [!document.querySelector('#demo').hidden, document.querySelector('#pill').textContent]")
            check("c. all files missing (404): the fixture shows with the DEMO chip (a careful CPI day)", r == [True, "careful"], r)
            ctx.close()
            srv4.shutdown()

            ctx, p, errs, seen, off = AK.page(br, origin, w=375, h=667, reduced=True, lite=True)
            AK.open_app(p, origin, APP, f"?demo=1&q=low&now={NOW}", hook="HELIOS")
            mode = p.evaluate("() => window.HELIOS.mode")
            check("c. 375 x 667, LITE (?q=low), reduced motion: the flat sunrise, no sideways scroll, every tap >= 44 px, no error", mode == "flat" and AK.no_sideways(p) and not AK.taps(p) and not errs, (mode, AK.taps(p)[:3], errs[:2]))
            AK.shot(p, "helios-lite")
            ctx.close()
    finally:
        srv.shutdown()


if __name__ == "__main__":
    test_static()
    test_maths()
    if "--static" not in sys.argv:
        test_page()
    AK.finish()
