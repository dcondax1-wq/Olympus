"""ARENA, Olympian Ranks (tools/arena/ builds events.json + jarvis.json; tools/web_public/arena/ is the page).
  a. the XP rules on the fixture: deterministic, the site XP by hand, only verifiable events, never a reward for risk
     ($, size, R or more trades than the plan), caps per day, a broken rule earns nothing
  b. the 12 Labours unlock on the right day
  c. streaks across days and in New York time (grace for today, gaps, holidays skipped, 23:30 ET, the DST change)
  d. the twins agree: tools/arena/score.py and arena/rules.js (node) give the same JSON on the demo and on edge cases
  e. the builder: publish(site), the Jarvis card contract (docs/JARVIS_APPS.md), the committed demo, the site hooks
  f. static page rules: the kit, safe areas, the orb's corner, reduced motion, no CDN, no innerHTML
  h. the 2026-11 upgrade: weekly discipline bosses (bosses.js), 28 trophies (trophies.js), the boss XP in both twins
  g. the page in Chromium at 390 x 844: no errors, the level-up plays on a fixture XP jump (once), no sideways scroll,
     nothing in the orb's corner, the sheets, a labour card, the real mode with a Planner on the phone (ledger + export),
     reduced motion; screenshots to research/handoff/2026-11-03-day/arena/
    python -X utf8 -m tests.test_arena            (temp folders + a local server; nothing else touched)
ARENA_NO_BROWSER=1 skips part g.
"""
from __future__ import annotations

import copy
import functools
import glob
import http.server
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools.arena import build, events as EV, fixture, score as S  # noqa: E402

WEB = os.path.join(ROOT, "tools", "web_public")
PAGE = os.path.join(WEB, "arena")
SHOTS = os.path.join(ROOT, "research", "handoff", "2026-11-03-day", "arena")
R = S.load_rules()
RES = []


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:500]}"), flush=True)


def site_events(data=None, today=fixture.TODAY):
    return EV.from_site(data if data is not None else fixture.data(), fixture.home(), today)


def xp_of(evs, today=fixture.TODAY):
    return S.score(evs, R, today)["xp"]


# ------------------------------------------------------------------------------------------------ a. the XP rules
def part_a():
    e1, e2 = site_events(), site_events(json.loads(json.dumps(fixture.data())))
    check("a. deterministic: the same site data twice (and through JSON) gives the same events", build.dumps(e1) == build.dumps(e2))
    kinds = {}
    for e in e1:
        kinds[e["kind"]] = kinds.get(e["kind"], 0) + 1
    want = {"bot_day": 18, "bot_down": 1, "clean_trade": 13, "rule_broken": 1, "plan_week": 2, "green_week": 2, "lapse": 1,
            "eval_passed": 1, "payout": 1}
    check("a. the fixture's site events by hand: 18 bot days, 1 down day (Oct 13), 13 clean trades, 1 manual exit, 2 plan + 2 green weeks, "
          "1 lapse, 1 eval passed, 1 payout", kinds == want, kinds)
    sc = S.score(e1, R, fixture.TODAY)
    by_hand = 18 * 20 + 13 * 25 + 2 * 60 + 2 * 40 + 500 + 400
    check(f"a. site XP by hand = {by_hand} (18x20 + 13x25 + 2x60 + 2x40 + 500 + 400); breaks, lapses and down days add 0",
          sc["xp"] == by_hand and sc["bySrc"] == {"site": by_hand}, (sc["xp"], sc["bySrc"]))
    check("a. only verifiable: every site event names its source, a known kind, a day not after today, and no $ / size / R field",
          all(e["src"] == "site" and e["kind"] in R["xp"] and e["day"] <= fixture.TODAY and not ({"pnl", "qty", "usd", "r", "amount"} & set(e))
              for e in e1), [e for e in e1 if e["src"] != "site"][:2])
    check("a. the rules table itself: XP is a flat number per kind, no rule reads money (no usd / pnl / qty / r keys)",
          all(set(v) == {"xp", "cap_day", "label", "src", "why"} and isinstance(v["xp"], int) for v in R["xp"].values()))
    # no reward for risk: 10x the size and the $ of every trade -> the same XP
    big = fixture.data()
    for a in big["accounts"]:
        for t in a.get("trades") or []:
            t["pnl"] *= 10
            t["qty"] *= 10
    check("a. no reward for risk: 10x the size and $ of every trade gives exactly the same events and XP",
          build.dumps(site_events(big)) == build.dumps(e1), xp_of(site_events(big)))
    # more trades than the plan: two more clean Zlarior trades in the week of Oct 5 (5 trades) -> less XP, not more
    over = fixture.data()
    lit = next(a for a in over["accounts"] if a["id"] == "mffu50k_eval")
    for day in ("2026-10-05", "2026-10-07"):
        t = copy.deepcopy(lit["trades"][0])
        t["day"], t["entry_t"], t["exit_t"] = day, fixture.HF.ts(day, "09:45"), fixture.HF.ts(day, "10:30")
        lit["trades"].insert(0, t)
    eo = site_events(over)
    check("a. overtrading earns less: 5 Zlarior trades in a week lose the plan week (+50 for the trades, -60 for the week)",
          xp_of(eo) == xp_of(e1) + 2 * 25 - 60 and not any(e["id"] == "plan_week:2026-10-05" for e in eo), (xp_of(eo), xp_of(e1)))
    # a trade with no stop, a stop on the wrong side, a second trade the same day: rule_broken, 0 XP
    bad = fixture.data()
    lit = next(a for a in bad["accounts"] if a["id"] == "mffu50k_eval")
    lit["trades"][0]["stop"] = None
    lit["trades"][1]["stop"] = lit["trades"][1]["entry"] + (5 if lit["trades"][1]["side"] == "LONG" else -5)
    t2 = copy.deepcopy(lit["trades"][2])
    t2["entry_t"] += 3600
    t2["exit_t"] += 3600
    lit["trades"].insert(3, t2)
    eb = site_events(bad)
    broke = [e for e in eb if e["kind"] == "rule_broken"]
    check("a. a missing stop, a stop on the wrong side, a 2nd Zlarior trade the same day: 'rule_broken', 0 XP each",
          len(broke) == 4 and all(S.score([e], R, fixture.TODAY)["xp"] == 0 for e in broke)
          and any("1 trade a day" in e["note"] for e in broke), [e["note"] for e in broke])
    check("a. a broken rule never pays: the week with it loses its plan / green week",
          not any(e["id"] in ("plan_week:2026-10-05", "green_week:2026-10-05") for e in eb))
    # caps: three clean trades the same day -> two count
    cap = [{"id": f"x{i}", "day": "2026-10-20", "kind": "clean_trade", "src": "site"} for i in range(3)]
    sc3 = S.score(cap, R, "2026-10-20")
    check("a. caps: 3 clean trades in a day count 2 (cap_day 2); the 3rd is logged as 'capped' with 0 XP",
          sc3["xp"] == 50 and [x["capped"] for x in sc3["log"]] == [True, False, False], sc3["log"])
    # junk in: unknown kinds, bad days, duplicate ids are dropped
    junk = [{"id": "a", "day": "2026-10-20", "kind": "free_xp"}, {"id": "b", "day": "20-10-2026", "kind": "bot_day"}, {"id": "", "day": "2026-10-20", "kind": "bot_day"},
            {"id": "c", "day": "2026-10-20", "kind": "bot_day"}, {"id": "c", "day": "2026-10-21", "kind": "bot_day"}, None, 5]
    check("a. junk in: unknown kinds, bad days, empty and duplicate ids are dropped (only 'c' once)", S.score(junk, R, "2026-10-21")["n"] == 1)
    check("a. no site data: no events, Mortal at 0 XP", EV.from_site(None, None, "2026-10-30") == [] and S.score([], R, "2026-10-30")["rank"]["id"] == "mortal")
    up = [e for e in e1 if e["kind"] in ("bot_day", "bot_down")]
    check("a. uptime: weekdays only, 90%+ = bot day, under 50% = down, 75% (Oct 21) neither",
          not any(e["day"] == fixture.DEGRADED_DAY for e in up) and any(e["id"] == f"bot_down:{fixture.DOWN_DAY}" for e in up), up[:3])


# ------------------------------------------------------------------------------------------------ b. the Labours
def part_b():
    d = build.demo()
    sc = S.score(d["events"], R, d["today"])
    L = {l["id"]: l for l in sc["labours"]}
    check("b. 12 Labours, numbered I-XII", [l["n"] for l in sc["labours"]] == list(range(1, 13)) and len(R["labours"]) == 12)
    check("b. the demo: the Nemean Lion (first eval passed, Oct 7), the Hind (first payout, Oct 28), the Stables (7 goal days, Oct 27)",
          (L["lion"]["earned"], L["lion"]["day"], L["hind"]["day"], L["stables"]["day"]) == (True, "2026-10-07", "2026-10-28", "2026-10-27"), L["stables"])
    check("b. not yet: the Hydra 12 of 21 market days, the Birds 13 of 25 clean trades, the Bull 9 of 10, Cerberus 0 of 1",
          (L["hydra"]["value"], L["birds"]["value"], L["bull"]["value"], L["cerberus"]["value"]) == (12, 13, 9, 0)
          and not any(L[k]["earned"] for k in ("hydra", "birds", "bull", "cerberus")), [(k, L[k]["value"]) for k in ("hydra", "birds", "bull", "cerberus")])
    more = d["events"] + [{"id": f"more{i}", "day": "2026-11-0" + str(2 + i // 2), "kind": "clean_trade", "src": "site"} for i in range(12)]
    L2 = {l["id"]: l for l in S.score(more, R, "2026-11-09")["labours"]}
    check("b. 12 more clean trades: the Birds (25) on the day of the 25th, the Bull (10 in a row) too",
          L2["birds"]["earned"] and L2["birds"]["day"] == "2026-11-07" and L2["bull"]["earned"], (L2["birds"], L2["bull"]))
    olymp = [{"id": f"p{i}", "day": "2026-11-0" + str(1 + i), "kind": "eval_passed", "src": "site"} for i in range(8)] + \
            [{"id": f"q{i}", "day": "2026-11-09", "kind": "payout", "src": "site"} for i in range(9)]
    s3 = S.score(olymp, R, "2026-11-09")
    L3 = {l["id"]: l for l in s3["labours"]}
    check("b. Cerberus unlocks the day the XP crosses Olympian (7,000) and the rank says Olympian",
          s3["rank"]["id"] == "olympian" and L3["cerberus"]["earned"] and L3["cerberus"]["day"] == "2026-11-09", (s3["xp"], L3["cerberus"]))
    zero = S.score([{"id": "z", "day": "2026-10-01", "kind": "rule_broken", "src": "site"}, {"id": "y", "day": "2026-10-02", "kind": "lapse", "src": "site"}], R, "2026-10-02")
    check("b. broken rules and lapses unlock nothing", zero["earned"] == 0 and zero["xp"] == 0)


# ------------------------------------------------------------------------------------------------ c. streaks
def ev(day, kind, i=""):
    return {"id": f"{kind}:{day}{i}", "day": day, "kind": kind, "src": R["xp"][kind]["src"]}


def part_c():
    goal = [ev(d, "goal_day") for d in ("2026-10-26", "2026-10-27", "2026-10-28", "2026-10-30", "2026-10-31")]
    s = S.score(goal, R, "2026-10-31")["streaks"]["planner"]
    check("c. daily streak: Oct 26-28, a gap on the 29th, then 30-31 -> now 2, best 3", (s["cur"], s["best"]) == (2, 3), s)
    s = S.score(goal, R, "2026-11-01")["streaks"]["planner"]
    check("c. grace: today (Nov 1) not done yet keeps yesterday's streak alive (2)", s["cur"] == 2, s)
    s = S.score(goal, R, "2026-11-02")["streaks"]["planner"]
    check("c. a whole missed day ends it: on Nov 2 with Nov 1 missed -> 0 (best stays 3)", (s["cur"], s["best"]) == (0, 3), s)
    s = S.score(goal + [ev("2026-10-31", "goal_day", "b")], R, "2026-10-31")["streaks"]["planner"]
    check("c. two goal events the same day count one day", s["cur"] == 2, s)
    up = [ev(d, "bot_day") for d in ("2026-10-22", "2026-10-23", "2026-10-26", "2026-10-28")]
    s = S.score(up, R, "2026-10-28")["streaks"]["uptime"]
    check("c. uptime streak counts market days with data: the weekend and a day with no samples (Oct 27) are skipped -> 4", s["cur"] == 4, s)
    s = S.score(up + [ev("2026-10-29", "bot_down")], R, "2026-10-30")["streaks"]["uptime"]
    check("c. a down day resets it (best kept)", (s["cur"], s["best"]) == (0, 4), s)
    tr = [{"id": f"t{i}", "day": "2026-10-20", "kind": "clean_trade", "src": "site", "t": 100 + i} for i in range(3)] + \
         [{"id": "t9", "day": "2026-10-20", "kind": "rule_broken", "src": "site", "t": 101.5}]
    s = S.score(tr, R, "2026-10-20")["streaks"]["discipline"]
    check("c. hands-off streak follows the trades' own order inside a day (t): clean, clean, BROKEN, clean -> 1, best 2", (s["cur"], s["best"]) == (1, 2), s)
    # New York time: the trading day of a trade at 23:30 ET (04:30 UTC next day) and after 18:00 ET
    from tools.hermes import wrapped as W
    import datetime as dt
    from zoneinfo import ZoneInfo
    ny = ZoneInfo("America/New_York")
    t1 = int(dt.datetime(2026, 10, 27, 23, 30, tzinfo=ny).timestamp())
    t2 = int(dt.datetime(2026, 10, 27, 15, 0, tzinfo=ny).timestamp())
    check("c. New York time: a trade at 23:30 ET Tue belongs to Wednesday's trading day (18:00 starts the next), 15:00 to Tuesday",
          (W.trading_day(t1), W.trading_day(t2)) == ("2026-10-28", "2026-10-27"))
    js = node("""
      const R = JSON.parse(fs.readFileSync(dir + '/rules.json', 'utf8'));
      const r = await import(url + '/rules.js'), s = await import(url + '/sources.js');
      const at = (iso) => new Date(iso);
      out({
        late: r.etDay(at('2026-11-03T04:30:00Z')), early: r.etDay(at('2026-11-03T05:30:00Z')),
        dst: r.etDay(at('2026-11-01T05:30:00Z')), dstEve: r.etDay(at('2026-11-01T03:59:00Z')),
        doneAt: s.dateOf(Date.parse('2026-11-03T04:30:00Z')), doneSec: s.dateOf(Math.floor(Date.parse('2026-11-03T04:30:00Z') / 1000)), str: s.dateOf('2026-11-02T23:59'),
        hour: r.etHour(at('2026-11-02T21:05:00Z')),
        beat: [s.beatToday({ t: 1793660000 }, '2026-11-02', 1793660000 + 600), s.beatToday({ t: 1793660000 }, '2026-11-02', 1793660000 + 3600), s.beatToday({ t: 1793660000, cached: true }, '2026-11-02', 1793660001)],
      });
    """)
    check("c. JS New York days: 04:30Z = 23:30 ET the day before, 05:30Z = 00:30 ET; across the DST change (Nov 1) too",
          js and (js["late"], js["early"], js["dst"], js["dstEve"]) == ("2026-11-02", "2026-11-03", "2026-11-01", "2026-10-31"), js)
    check("c. a Planner task ticked at 23:30 ET counts for that ET day (ms, seconds, or a date string)",
          js and (js["doneAt"], js["doneSec"], js["str"]) == ("2026-11-02", "2026-11-02", "2026-11-02"), js)
    check("c. etHour: 21:05Z is 16:05 ET (the hands-off quest is checked after 16:00)", js and abs(js["hour"] - (16 + 5 / 60)) < 1e-6, js)
    check("c. heartbeat today: fresh = yes, an hour old = no, a cached copy = no", js and js["beat"] == [True, False, False], js)


# ------------------------------------------------------------------------------------------------ d. the twins agree
def node(body: str):
    script = ("import fs from 'node:fs';\nconst dir = " + json.dumps(PAGE) + ", url = 'file://' + dir;\nconst out = (x) => process.stdout.write(JSON.stringify(x));\n"
              "(async () => {\n" + body + "\n})().catch((e) => { process.stdout.write(JSON.stringify({ error: String(e && e.stack || e) })); });")
    try:
        p = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True, timeout=60)
        return json.loads(p.stdout) if p.stdout.strip() else {"error": p.stderr[-400:]}
    except (OSError, ValueError, subprocess.TimeoutExpired) as e:
        return {"error": str(e)}


def part_d():
    d = build.demo()
    cases = {"demo": [d["events"], d["today"]],
             "grace": [d["events"], "2026-10-31"], "late": [d["events"], "2026-11-04"],
             "boss": [[{"id": "boss:2026-10-26:cerberus", "day": "2026-10-30", "kind": "boss", "src": "quest", "note": "x"}, {"id": "boss:2026-10-26:sphinx", "day": "2026-10-29", "kind": "boss", "src": "quest"},
                      {"id": "b3", "day": "2026-10-29", "kind": "boss"}, {"id": "b4", "day": "2026-10-29", "kind": "boss"}, {"id": "b5", "day": "2026-10-29", "kind": "boss"}, {"id": "b6", "day": "2026-10-29", "kind": "boss"}], "2026-10-30"],
             "edge": [[{"id": "x", "day": "2026-10-20", "kind": "clean_trade", "t": 5}, {"id": "y", "day": "2026-10-20", "kind": "rule_broken", "t": 3},
                       {"id": "z", "day": "2026-10-20", "kind": "clean_trade"}, {"id": "w", "day": "bad", "kind": "bot_day"},
                       {"id": "v", "day": "2026-10-21", "kind": "nope"}, {"id": "u", "day": "2026-10-21", "kind": "journal", "note": "n" * 300}], "2026-10-21"]}
    js = node("const R = JSON.parse(fs.readFileSync(dir + '/rules.json', 'utf8')); const r = await import(url + '/rules.js');\n"
              f"const C = {json.dumps(cases)};\n"
              "const days = []; for (let i = 0; i < 21; i++) days.push(r.addDays('2026-10-26', i));\n"
              "const ctxs = [{}, { planner: true }, { planner: true, habits: true, vault: true, kalshi: true, tasksToday: 5 }, { vault: true }];\n"
              "out({ scores: Object.fromEntries(Object.entries(C).map(([k, [e, t]]) => [k, r.score(e, R, t)])),\n"
              "  quests: days.map((d) => ctxs.map((c) => r.pickQuests(d, c, R))) });")
    if js.get("error"):
        check("d. node runs rules.js", False, js["error"])
        return
    for k, (e, t) in cases.items():
        py = S.score(e, R, t)
        check(f"d. score() twins agree on '{k}' (Python score.py == JS rules.js, every field)", build.dumps(py) == build.dumps(js["scores"][k]),
              [(x, py[x], js["scores"][k].get(x)) for x in py if build.dumps(py[x]) != build.dumps(js["scores"][k].get(x))][:2])
    days = [S.add_days("2026-10-26", i) for i in range(21)]
    ctxs = [{}, {"planner": True}, {"planner": True, "habits": True, "vault": True, "kalshi": True, "tasksToday": 5}, {"vault": True}]
    pq = [[S.pick_quests(d, c, R) for c in ctxs] for d in days]
    check("d. pick_quests twins agree on 21 days x 4 phones", build.dumps(pq) == build.dumps(js["quests"]))
    q = pq[0]
    check("d. quests: a market day leads with the trading quests, then the day's life quest; a weekend with nothing linked has only setup quests",
          [x["id"] for x in q[2]][:2] == ["bots_watch", "hands_off"] and [x["id"] for x in pq[5][0]] == ["link_planner", "link_vault"]
          and all(len(x) == 3 for x in pq[5][2:3]), [[x["id"] for x in y] for y in (q[2], pq[5][0])])
    check("d. quest '{n}' follows today's tasks (at most 3)", pq[0][2][2]["n"] == 3 if pq[0][2][2]["id"] == "clear_tasks" else
          any(x["id"] == "clear_tasks" and x["n"] == 3 and x["title"] == "Clear 3 Planner tasks" for y in pq for x in y[2]))
    ver = node("""const R = JSON.parse(fs.readFileSync(dir + '/rules.json', 'utf8')); const r = await import(url + '/rules.js');
      const Q = (id, n = 1) => ({ id, n, title: id });
      const day = '2026-10-29', qs = r.pickQuests(day, { planner: true, habits: true }, R);
      out({ early: r.verifyQuest(Q('hands_off'), { hour: 15.9, beatToday: true }), late: r.verifyQuest(Q('hands_off'), { hour: 16.1, beatToday: true }),
        broke: r.verifyQuest(Q('hands_off'), { hour: 17, beatToday: true, brokenToday: true }), noBot: r.verifyQuest(Q('hands_off'), { hour: 17 }),
        tasks: [r.verifyQuest(Q('clear_tasks', 3), { doneToday: 2 }).done, r.verifyQuest(Q('clear_tasks', 3), { doneToday: 3 }).done],
        sweep: r.questEvents(day, qs, [{ done: true, why: 'a' }, { done: true, why: 'b' }, { done: true, why: 'c' }]).map((e) => e.kind),
        partial: r.questEvents(day, qs, [{ done: true, why: 'a' }, { done: false }, { done: true, why: 'c' }]).map((e) => e.id) });""")
    check("d. 'Hands off' is only checked after 16:00 ET, needs the bot to have run, and fails on a broken rule",
          not ver["early"]["done"] and ver["late"]["done"] and not ver["broke"]["done"] and not ver["noBot"]["done"], ver)
    check("d. quest events: 3 verified = 3 quests + the sweep; 2 of 3 = 2 quests, no sweep",
          ver["tasks"] == [False, True] and ver["sweep"] == ["quest", "quest", "quest", "quest_sweep"] and len(ver["partial"]) == 2, ver)


# ------------------------------------------------------------------------------------------------ e. builder and card
def card_ok(c):
    bad = []
    txt = lambda s: isinstance(s, str) and not re.search(r"[<>]|&\w+;|[\r\n]", s)  # noqa: E731
    if c.get("v") != 1 or not txt(c.get("name")) or len(c["name"]) > 40:
        bad.append("v/name")
    st = c.get("status") or {}
    if st.get("level") not in ("ok", "warn", "bad", "off") or not txt(st.get("label")) or len(st["label"]) > 48:
        bad.append("status")
    if len(c.get("kpis") or []) > 3 or any(not txt(k["label"]) or len(k["label"]) > 20 or len(str(k["value"])) > 24 or len(str(k.get("delta", ""))) > 16 for k in c.get("kpis") or []):
        bad.append("kpis")
    if len(c.get("lines") or []) > 3 or any(not txt(x) or len(x) > 120 for x in c.get("lines") or []):
        bad.append("lines")
    if not isinstance(c.get("t"), int) or not re.match(r"^#[0-9a-f]{6}$", str(c.get("theme"))) or not 60 <= c.get("stale_after", 0) <= 1209600:
        bad.append("t/theme/stale_after")
    if len(build.dumps(c).encode()) > 8192:
        bad.append("size")
    return bad


def part_e():
    tmp = tempfile.mkdtemp(prefix="le_arena_build_")
    try:
        check("e. publish(): no data.json -> None (the page's demo stays)", build.publish(tmp) is None)
        json.dump(fixture.data(), open(os.path.join(tmp, "data.json"), "w"))
        json.dump(fixture.home(), open(os.path.join(tmp, "home.json"), "w"))
        res = build.publish(tmp, now=fixture.NOW)
        doc = json.load(open(os.path.join(tmp, "arena", "events.json")))
        card = json.load(open(os.path.join(tmp, "arena", "jarvis.json")))
        check("e. publish(site) writes arena/events.json (not demo, today in New York) + arena/jarvis.json",
              res and doc["kind"] == "olympus-arena" and doc["demo"] is False and doc["today"] == fixture.TODAY and len(doc["events"]) == res["events"], res)
        check("e. the Jarvis card keeps every rule of docs/JARVIS_APPS.md (limits, plain text, theme, stale_after)", not card_ok(card), card_ok(card))
        sc = S.score(doc["events"], R, doc["today"])
        check("e. the card: rank + level, XP with what is left to the next rank, the Labours, today's quests, opens #quests",
              card["status"] == {"level": "ok", "label": f"{sc['rank']['name']} - level {sc['level']}"} and card["kpis"][1]["value"] == f"{sc['xp']:,}"
              and card["kpis"][2]["value"] == f"{sc['earned']} of 12" and card["lines"][0].startswith("Today: Bots on watch (done), Hands off (done)")
              and card["open"] == "#quests" and card["theme"] == build.THEME, card)
        d = build.demo()
        check("e. the committed demo files are build --demo's output (events.json + jarvis.json, DEMO card)",
              open(os.path.join(PAGE, "events.json"), encoding="utf-8").read() == build.dumps(d)
              and open(os.path.join(PAGE, "jarvis.json"), encoding="utf-8").read() == build.dumps(build.jarvis_card(d))
              and build.jarvis_card(d)["status"]["level"] == "off" and not card_ok(build.jarvis_card(d)))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    b = open(os.path.join(ROOT, "tools", "build_web_dashboard.py"), encoding="utf-8").read()
    check("e. the site build copies arena/ and runs the builder guarded (a failure never stops the publish)",
          re.search(r'for app in \([^)]*"arena"[^)]*\):', b) is not None and "from tools.arena import build as _arena" in b and 'print("  arena unavailable:"' in b)
    sw = open(os.path.join(WEB, "sw.js"), encoding="utf-8").read()
    check("e. the site's service worker leaves arena/ alone (OTHER_APPS)", re.search(r"const OTHER_APPS = \[[^\]]*'arena/'", sw) is not None)


# ------------------------------------------------------------------------------------------------ h. bosses and trophies
def part_h():
    js = node("""const R = JSON.parse(fs.readFileSync(dir + '/rules.json', 'utf8'));
      const B = await import(url + '/bosses.js'), T = await import(url + '/trophies.js'), r = await import(url + '/rules.js');
      const MON = '2026-10-26', D = ['2026-10-26', '2026-10-27', '2026-10-28', '2026-10-29', '2026-10-30'];
      const ev = (id, day, kind, src) => ({ id, day, kind, src: src || 'site' });
      const base = [];                                              // five days the bot ran, clean trades on Tue and Thu
      D.forEach((d) => base.push(ev('bd' + d, d, 'bot_day')));
      base.push(ev('t1', D[1], 'clean_trade'), ev('t2', D[3], 'clean_trade'));
      const J = (days) => days.map((d) => ev('j' + d, d, 'journal', 'obsidian')), G = (days) => days.map((d) => ev('g' + d, d, 'goal_day', 'planner'));
      const all = { planner: true, vault: true };
      const ids = (rs) => Object.fromEntries(rs.map((x) => [x.id, [x.state, x.hits, x.day]]));
      const A = B.evaluateWeek([...base, ...J(D.slice(0, 4)), ...G(D.slice(0, 3))], MON, '2026-10-30', 17, all, R);
      const brokenEv = [...base, ev('rb', D[2], 'rule_broken')], twoTrades = [...base, ev('t3', D[3], 'clean_trade')];
      const six = [...base, ev('s1', D[0], 'clean_trade'), ev('s2', D[0], 'clean_trade'), ev('s3', D[2], 'clean_trade'), ev('s4', D[4], 'clean_trade')];
      const open = B.evaluateWeek(base.filter((e) => e.day <= D[2]), MON, D[2], 15, {}, R);
      const fri = (h) => B.evaluateWeek(base, MON, D[4], h, all, R);
      const evs = B.bossEvents(A, MON);
      const sc0 = r.score([...base, ...evs], R, '2026-10-30'), sc1 = r.score(base, R, '2026-10-30');
      const tr = T.trophies(sc0, B.bossStats(evs));
      out({ A: ids(A), broken: ids(B.evaluateWeek(brokenEv, MON, '2026-10-30', 17, all, R)), two: ids(B.evaluateWeek(twoTrades, MON, '2026-10-30', 17, all, R)),
        six: ids(B.evaluateWeek(six, MON, '2026-10-30', 17, all, R)), open: ids(open), f159: ids(fri(15.9)), f160: ids(fri(16)),
        parts: A[0].parts.map((p) => p.state), evs: evs.map((e) => e.id).sort(), xp: sc0.xp - sc1.xp,
        ws: [B.weekStart('2026-11-01'), B.weekStart('2026-10-26'), B.weekStart('2026-10-30')], feat: [0, 1, 2, 3, 4].map((i) => B.featured(r.addDays(MON, 7 * i))),
        stats: B.bossStats([{ kind: 'boss', day: '2026-10-30' }, { kind: 'boss', day: '2026-10-28' }, { kind: 'boss', day: '2026-11-06' }, { kind: 'boss', day: '2026-11-20' }]),
        hist: B.history(base, '2026-10-30', 17, all, 4, R).map((w) => [w.mon, w.bosses.length]),
        tl: tr.length, tearn: tr.filter((t) => t.earned).map((t) => t.id), tids: new Set(tr.map((t) => t.id)).size,
        tiers: [...new Set(tr.map((t) => t.tier))].sort(), caps: r.score(Array.from({ length: 6 }, (_, i) => ev('c' + i, '2026-10-30', 'boss', 'quest')), R, '2026-10-30').xp });""")
    if js.get("error"):
        check("h. node runs bosses.js and trophies.js", False, js["error"])
        return
    A = js["A"]
    check("h. a quiet, clean week with the notes and the goals: all four bosses slain, on the day the last blow landed",
          A == {"minotaur": ["slain", 5, "2026-10-30"], "cerberus": ["slain", 3, "2026-10-30"], "sphinx": ["slain", 4, "2026-10-29"], "chimera": ["slain", 3, "2026-10-28"]}, A)
    check("h. a broken rule lets the Minotaur and Cerberus escape; a second trade in a day (revenge) too; 6 trades break the plan (Cerberus)",
          js["broken"]["minotaur"][0] == "escaped" and js["broken"]["cerberus"][0] == "escaped" and js["two"]["minotaur"][0] == "escaped" and js["two"]["cerberus"][0] == "slain"
          and js["six"]["cerberus"][0] == "escaped" and js["six"]["minotaur"][0] == "escaped", (js["broken"], js["two"], js["six"]))
    check("h. mid-week nothing is slain early (Minotaur and Cerberus settle on Friday's close); without Obsidian and the Planner the journal and goal bosses are locked",
          js["open"]["minotaur"][0] == "fighting" and js["open"]["minotaur"][1] == 2 and js["open"]["cerberus"][0] == "fighting"
          and js["open"]["sphinx"][0] == "locked" and js["open"]["chimera"][0] == "locked", js["open"])
    check("h. a market day counts as finished from 16:00 ET (Friday 15:59 still fights, 16:00 slays)",
          js["f159"]["minotaur"] == ["fighting", 4, None] and js["f160"]["minotaur"] == ["slain", 5, "2026-10-30"], (js["f159"]["minotaur"], js["f160"]["minotaur"]))
    check("h. boss events: one per slain boss, id boss:<monday>:<boss>; 4 x 100 XP; the cap per day is 4 bosses",
          js["evs"] == ["boss:2026-10-26:cerberus", "boss:2026-10-26:chimera", "boss:2026-10-26:minotaur", "boss:2026-10-26:sphinx"] and js["xp"] == 400 and js["caps"] == 400,
          (js["evs"], js["xp"], js["caps"]))
    check("h. weeks start on Monday (a Sunday belongs to the week before), the spotlight boss rotates through all four, the Minotaur's days read ok x5",
          js["ws"] == ["2026-10-26", "2026-10-26", "2026-10-26"] and len(set(js["feat"][:4])) == 4 and js["feat"][0] == js["feat"][4] and js["parts"] == ["ok"] * 5, (js["ws"], js["feat"], js["parts"]))
    check("h. history lists the last 4 finished weeks, newest first; bossStats counts slain bosses and the best run of weeks in a row",
          [w[0] for w in js["hist"]] == ["2026-10-19", "2026-10-12", "2026-10-05", "2026-09-28"] and all(w[1] == 4 for w in js["hist"]) and js["stats"] == {"slain": 4, "weeks": 3, "best": 2}, (js["hist"], js["stats"]))
    check("h. trophies: 28 unique, every tier used, earned from the score (First Blood and Boss Slayer yes; Boss Hunter and Centurion not yet)",
          js["tl"] == 28 and js["tids"] == 28 and js["tiers"] == ["bronze", "gold", "legend", "silver"] and "first_blood" in js["tearn"] and "boss_slayer" in js["tearn"]
          and "boss_hunter" not in js["tearn"] and "centurion" not in js["tearn"], js["tearn"])


# ------------------------------------------------------------------------------------------------ f. static rules
def part_f():
    html = open(os.path.join(PAGE, "index.html"), encoding="utf-8").read()
    css = open(os.path.join(PAGE, "arena.css"), encoding="utf-8").read()
    js = {n: open(os.path.join(PAGE, n), encoding="utf-8").read() for n in os.listdir(PAGE) if n.endswith(".js")}
    check("f. the kit first (olympus.css + olympus.js data-app=arena), viewport-fit=cover, theme-color, dark",
          '<link rel="stylesheet" href="../olympus/olympus.css' in html and 'src="../olympus/olympus.js?v=o27" data-app="arena"' in html
          and "viewport-fit=cover" in html and 'name="theme-color" content="#000000"' in html and 'content="dark"' in html)
    check("f. the PC feed reader is on the page (../pc_feed.js, id pcFeedJs): ../jarvis/data.js reads the PC's status post first, never the old live.json of the suspended account when the post answers",
          '<script src="../pc_feed.js?v=' in html and 'id="pcFeedJs"' in html)
    check("f. no CDN, no outside script or font: every src / href is local", not re.search(r'(src|href)="https?://', html)
          and not any(re.search(r"import[^;]*['\"]https?://", s) for s in js.values()))
    check("f. three.js is Jarvis's copy (../jarvis/three.module.min.js), the vault only through ../jarvis/obsidian.js",
          "from '../jarvis/three.module.min.js'" in js["scene.js"] and "import('../jarvis/obsidian.js')" in js["sources.js"] and "graphSnapshot" in js["sources.js"])
    check("f. no innerHTML / insertAdjacentHTML / document.write anywhere (data only ever goes in as text)",
          not any(re.search(r"innerHTML|insertAdjacentHTML|document\.write", s) for s in js.values()))
    check("f. safe areas on every edge and the orb's corner: tabs stop 96 px from the right, the sheet sits 168 px up",
          all(f"var(--s{x})" in css for x in "trbl") and "right: calc(var(--sr) + var(--oly-orb-clear, 96px))" in css and "bottom: calc(var(--sb) + 168px)" in css)
    check("f. reduced motion (CSS media + the kit's fx=off), touch-action none on the canvas, dvh after vh",
          "@media (prefers-reduced-motion: reduce)" in css and 'html[data-fx="off"]' in css and "touch-action: none" in css
          and re.search(r"max-height: calc\(100vh[^;]*; max-height: calc\(100dvh", css) is not None)
    check("f. the render core: createRenderer from ../olympus/render.js (tiers, tone mapping, bloom, hidden-tab pause, automatic step down), materials from ../olympus/materials.js, rc.render() in the frame loop, no WebGLRenderer of its own",
          "from '../olympus/render.js'" in js["scene.js"] and "from '../olympus/materials.js'" in js["scene.js"] and "createRenderer(" in js["scene.js"]
          and "rc.render()" in js["scene.js"] and "new THREE.WebGLRenderer" not in js["scene.js"] and "rc.dispose()" in js["scene.js"])
    check("f. the new modules exist and are wired: bosses.js, trophies.js (imported by main.js), no network API in them",
          "from './bosses.js'" in js["main.js"] and "from './trophies.js'" in js["main.js"]
          and not re.search(r"fetch\(|XMLHttpRequest|localStorage|Date\.now|new Date\(", js["bosses.js"] + js["trophies.js"]))
    check("f. themes: Olympus.theme() / onTheme hooked when present, else applyTheme(tokens)",
          "O.onTheme" in js["main.js"] and "export function applyTheme" in js["main.js"])


# ------------------------------------------------------------------------------------------------ g. the browser
class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def handle(self):
        try:
            super().handle()
        except (BrokenPipeError, ConnectionResetError):
            pass                                             # the page closed while a file was still being sent

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def make_site(tmp, doc=None):
    site = os.path.join(tmp, "nq-dashboard")
    shutil.rmtree(site, ignore_errors=True)
    shutil.copytree(PAGE, os.path.join(site, "arena"))
    shutil.copytree(os.path.join(WEB, "jarvis"), os.path.join(site, "jarvis"))
    shutil.copytree(os.path.join(WEB, "olympus"), os.path.join(site, "olympus"))
    # the PC feed reader the page loads (polish2 2026-11-19: Arena reads the PC's status post first, like Jarvis) and a stub pointer to a
    # topic that never answers here (every off-machine request is a 404 in this test)
    shutil.copy(os.path.join(WEB, "pc_feed.js"), os.path.join(site, "pc_feed.js"))
    with open(os.path.join(site, "status_feed.json"), "w", encoding="utf-8") as fh:
        json.dump({"v": 1, "ntfy": "https://ntfy.invalid", "topic": "arena_test"}, fh)
    if doc is not None:
        with open(os.path.join(site, "arena", "events.json"), "w", encoding="utf-8") as fh:
            fh.write(build.dumps(doc))
    return site


OVERFLOW = """() => {
  const W = innerWidth, H = innerHeight, bad = [];
  for (const el of document.querySelectorAll('#ui *, #tabs *, #sheet:not([hidden]) *, #pop:not([hidden]) *')) {
    if (el.closest('svg') && el.tagName.toLowerCase() !== 'svg') continue;
    const b = el.getBoundingClientRect(), cs = getComputedStyle(el), clip = el.closest('.sheet .body');
    if (!b.width || !b.height || cs.visibility === 'hidden') continue;
    // inside the sheet's scroller only the visible part counts (the rest is clipped by its overflow)
    const c = clip ? clip.getBoundingClientRect() : null, r = { left: b.left, right: b.right, top: c ? Math.max(b.top, c.top) : b.top, bottom: c ? Math.min(b.bottom, c.bottom) : b.bottom };
    if (r.bottom <= r.top) continue;
    if (r.right > W - 16 + 0.5 || r.left < 16 - 0.5) bad.push('gutter ' + el.className + ' ' + Math.round(r.left) + '-' + Math.round(r.right));
    if (r.right > W - 80 && r.bottom > H - 160) bad.push('orb ' + (el.id || el.className) + ' ' + Math.round(r.right) + ',' + Math.round(r.bottom));
  }
  if (document.documentElement.scrollWidth > W || document.body.scrollWidth > W) bad.push('scroll ' + document.documentElement.scrollWidth);
  return bad;
}"""

PLANNER = None


def planner_doc(today):
    import datetime as dt
    y = (dt.date.fromisoformat(today) - dt.timedelta(days=1)).isoformat()
    tm = (dt.date.fromisoformat(today) + dt.timedelta(days=1)).isoformat()
    return {"tasks": [{"id": "t1", "title": "Review fills", "date": today, "done": True}, {"id": "t2", "title": "Gym", "date": today, "done": True},
                      {"id": "t3", "title": "Read <b>50</b> pages", "date": today, "done": False}, {"id": "t4", "title": "Old", "date": y, "done": True},
                      {"id": "t5", "title": "Plan the week", "date": tm, "done": False}],
            "habits": [{"id": "h1", "name": "Gym", "log": [y, today]}, {"id": "h2", "name": "Read", "log": [y]}], "events": []}


def run_browser():
    from playwright.sync_api import sync_playwright
    import datetime as dt
    from zoneinfo import ZoneInfo
    os.makedirs(SHOTS, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix="le_arena_page_")
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=tmp))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}/nq-dashboard/arena/"
    today = dt.datetime.now(ZoneInfo("America/New_York")).date().isoformat()
    try:
        with sync_playwright() as pw:
            exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
            br = pw.chromium.launch(**({"executable_path": exe} if exe else {}), args=["--use-gl=swiftshader", "--enable-webgl", "--ignore-gpu-blocklist"])

            def page(init=(), reduced=False, quality="low"):
                ctx = br.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1, has_touch=True, accept_downloads=True,
                                     reduced_motion="reduce" if reduced else "no-preference")
                if quality:           # SwiftShader is a CPU rasteriser: a chosen LITE tier keeps the frames cheap (the one HD context below checks the passes)
                    ctx.add_init_script(f"try {{ localStorage.setItem('jfx', '{quality}'); }} catch (e) {{}}")
                for s in init:
                    ctx.add_init_script(s)
                cors = {"Access-Control-Allow-Origin": "*"}
                ctx.route(re.compile(r"^https?://(?!127\.0\.0\.1)"), lambda r: r.fulfill(status=404, body="not found", headers=cors))   # nothing leaves the machine
                p = ctx.new_page()
                p.errs, p.bad = [], []
                p.set_default_timeout(120000)
                p.on("pageerror", lambda e: p.errs.append(str(e)))
                p.on("console", lambda m: m.type == "error" and "Failed to load resource" not in m.text and p.errs.append(m.text))
                p.on("response", lambda r: r.status >= 400 and "127.0.0.1" in r.url and "favicon" not in r.url and p.bad.append(f"{r.status} {r.url}"))
                return ctx, p

            def ready(p, url=base):
                p.goto(url)
                p.wait_for_function("window.ARENA && ARENA.state().ready", timeout=90000)

            st = lambda p: p.evaluate("ARENA.state()")  # noqa: E731

            # ---- 1. the demo with a fixture XP jump: the last visit saw level 10 (Hero) -> level-up + rank-up
            make_site(tmp)
            seen = "localStorage.setItem('arena.demo.seen', JSON.stringify({ xp: 2400, level: 10, rank_i: 1, earned: ['lion'] }))"
            ctx, p = page([seen])
            ready(p)
            p.wait_for_function("ARENA.state().levelups > 0", timeout=120000)
            s = st(p)
            check("g. demo: DEMO badge, Demigod level 18 (the demo's slain bosses count), 4 Labours, today's 3 quests done, no errors",
                  s["demo"] and p.is_visible("#demo") and (s["rank"], s["level"], s["earned"]) == ("Demigod", 18, 4)
                  and [q["done"] for q in s["quests"]] == [True, True, True] and not p.errs and not p.bad, (s, p.errs, p.bad))
            sc = s["scene"] or {}
            check("g. the fixture XP jump (level 10 -> 18, Hero -> Demigod) plays the rank-up ceremony: lightning bolts, the gold burst, three shockwave rings, the banner",
                  s["levelups"] == 1 and sc.get("levelups") == 1 and (sc.get("bolts", 0) >= 3 or sc.get("burst")) and sc.get("rings") == 3 and s["banner"] == "Rank up Demigod Level 18"
                  and p.get_attribute("html", "data-levelup") == "1", (sc, s["banner"]))
            try:                                               # the card is timed 2.4 s after the burst (700 ms after load): wait for it, not a guess
                p.wait_for_function("(() => { const e = document.getElementById('pop'); return !!e && !e.hidden && e.getClientRects().length > 0 && e.textContent.includes('Ceryneian Hind'); })()",
                                    timeout=20000, polling=100)
            except Exception:
                pass
            check("g. the new Labour's card opens after the burst (the Hind, earned since the last visit)",
                  p.is_visible("#pop") and "Ceryneian Hind" in p.inner_text("#pop"), (p.is_visible("#pop"), p.inner_text("#pop")[:120] if p.is_visible("#pop") else ""))
            p.click("#popClose")
            p.wait_for_timeout(300)
            p.evaluate("ARENA.hold(true)")                             # the same rank-up frozen at its peak for the picture
            p.wait_for_timeout(900)
            p.screenshot(path=os.path.join(SHOTS, "arena-levelup.png"))
            check("g. the rank-up banner shows the ladder: five pips, three lit (Mortal, Hero, Demigod)", p.locator("#banner .pips i").count() == 5 and p.locator("#banner .pips i.on").count() == 3
                  and p.evaluate("document.getElementById('banner').classList.contains('rankup')"))
            p.evaluate("ARENA.hold(false)")
            ov = p.evaluate(OVERFLOW)
            check("g. home at 390 x 844: inside the 16 px gutters, nothing in the orb's 80 x 160 corner, no sideways scroll", not ov, ov)
            p.screenshot(path=os.path.join(SHOTS, "arena-home.png"))
            fr = p.evaluate("new Promise((ok) => { let n = 0; const t0 = performance.now(); const f = () => { n++; if (performance.now() - t0 < 1000) requestAnimationFrame(f); else ok(n); }; requestAnimationFrame(f); })")
            sc = st(p)["scene"] or {}
            check(f"g. the frame loop runs ({fr} fps headless SwiftShader, relative only) on the chosen LITE tier: 2 passes (scene + finish with FXAA), the LITE tag shown",
                  fr >= 2 and sc.get("frames", 0) > 10 and sc.get("lite") and sc.get("passes") == 2 and p.is_visible("#lite"), (fr, sc))
            for tab, shot in (("quests", "arena-quests.png"), ("labours", "arena-labours.png"), ("log", "arena-log.png")):
                p.click(f"[data-tab={tab}]")
                p.wait_for_timeout(350)
                ov = p.evaluate(OVERFLOW)
                check(f"g. the {tab} sheet: open, pressed tab, URL #{tab}, inside the gutters, out of the orb's corner",
                      p.is_visible("#sheet") and p.get_attribute(f"[data-tab={tab}]", "aria-pressed") == "true" and p.evaluate("location.hash") == "#" + tab and not ov, ov)
                p.screenshot(path=os.path.join(SHOTS, shot))
            check("g. the XP log names every source with its XP (site, Planner, Obsidian, Kalshi, quests) and the honest rule",
                  all(x in p.inner_text("#sheet") for x in ("Site data", "Planner", "Obsidian", "Kalshi", "Daily quests", "never from $, size, R")))
            p.click("[data-tab=labours]")
            p.wait_for_timeout(200)
            p.click("[data-labour=birds]")
            p.wait_for_timeout(200)
            check("g. a Labour tile opens its card: the Stymphalian Birds, 13 of 25, how it is earned",
                  p.is_visible("#pop") and "13 of 25" in p.inner_text("#pop") and "Trade inside every rule" in p.inner_text("#pop"), p.inner_text("#pop") if p.is_visible("#pop") else None)
            p.screenshot(path=os.path.join(SHOTS, "arena-card.png"))
            # ---- the 2026-11 upgrade: bosses, trophies, the rank ladder, the render core
            s = st(p)
            sc = s["scene"] or {}
            check("g. the scene runs on the render core: a tier is set, 1-3 post passes, the ladder shows 3 steps lit (Demigod), the trophies match the sheet, the week's boss is in the sky",
                  sc.get("quality") == "low" and sc.get("passes") == 2 and sc.get("steps") == 3 and sc.get("trophies") == s["trophies"] and s["trophyTotal"] == 28
                  and sc.get("boss") in ("fighting", "slain", "escaped", "locked"), (sc, s["trophies"]))
            p.click("[data-tab=bosses]")
            p.wait_for_timeout(300)
            ov = p.evaluate(OVERFLOW)
            txt = p.inner_text("#sheet").lower()
            check("g. the Bosses sheet: 4 bosses, the boss of the week first and big, HP pips, the discipline-only promise, +100 XP, the last four weeks; inside the gutters",
                  p.locator(".boss").count() == 4 and p.locator(".boss.big").count() == 1 and p.evaluate("document.querySelector('.boss').classList.contains('big')")
                  and "no $, size or r" in txt and "+100 xp" in txt and "last four weeks" in txt and p.locator(".week").count() == 4 and not ov and p.evaluate("location.hash") == "#bosses", (ov, txt[:200]))
            check("g. the tab counts: bosses slain this week, trophies earned of 28", p.inner_text("#bCount") == "2/4" and p.inner_text("#tCount") == f"{s['trophies']}/28", (p.inner_text("#bCount"), p.inner_text("#tCount")))
            p.screenshot(path=os.path.join(SHOTS, "arena-bosses.png"))
            p.click("[data-tab=trophies]")
            p.wait_for_timeout(300)
            ov = p.evaluate(OVERFLOW)
            check("g. the Trophy room: 28 tiles in three tiers of metal, the earned ones lit, inside the gutters",
                  p.locator(".trophy").count() == 28 and p.locator(".trophy.earned").count() == s["trophies"] and p.locator(".trophy.legend").count() == 2 and not ov, ov)
            p.screenshot(path=os.path.join(SHOTS, "arena-trophies.png"))
            p.click("[data-trophy=first_blood]")
            p.wait_for_timeout(200)
            check("g. a trophy tile opens its card (First Blood, bronze, honour not XP)",
                  p.is_visible("#pop") and "First Blood" in p.inner_text("#pop") and "Honour, not XP" in p.inner_text("#pop"), p.inner_text("#pop") if p.is_visible("#pop") else None)
            p.click("#popClose")
            p.click("#rank")
            p.wait_for_timeout(300)
            ov = p.evaluate(OVERFLOW)
            check("g. the rank card opens the ladder: five rungs, Titan on top, 'You are here' on Demigod, URL #ranks, inside the gutters",
                  p.locator(".rung").count() == 5 and p.locator(".rung.here").get_attribute("data-rank") == "demigod" and "You are here" in p.inner_text(".rung.here")
                  and p.locator(".rung").first.get_attribute("data-rank") == "titan" and p.evaluate("location.hash") == "#ranks" and not ov, ov)
            p.screenshot(path=os.path.join(SHOTS, "arena-ladder.png"))
            p.keyboard.press("Escape")
            p.keyboard.press("Escape")
            p.mouse.click(195, 520)                                    # a tap on the arena floor (no statue) closes nothing open, picks nothing
            p.wait_for_timeout(200)
            check("g. Escape closes the card and the sheet; a tap on the floor opens no card", not p.is_visible("#pop") and not p.is_visible("#sheet"))
            ctx.close()

            # ---- 2. the demo again with the current level seen: nothing plays
            cur = "localStorage.setItem('arena.demo.seen', JSON.stringify({ xp: 4475, level: 18, rank_i: 2, earned: ['lion','hind','stables','apples'] }))"
            ctx, p = page([cur])
            ready(p)
            p.wait_for_timeout(1200)
            check("g. no XP jump since the last visit: no level-up", st(p)["levelups"] == 0 and not p.is_visible("#banner"))
            ctx.close()

            # ---- 2b. the HD tier: the render core's three passes (scene, bloom, finish)
            ctx, p = page([cur], quality="high")
            ready(p, base + "?gpu=1")       # ?gpu=1: lift the software-GL cap (high / ultra held to LITE on SwiftShader), as tests.test_olympus_kit
            p.wait_for_function("ARENA.state().scene && ARENA.state().scene.drawn > 0", timeout=180000)
            sc = st(p)["scene"]
            check("g. the HD tier (high): the render core draws 3 passes (scene, bloom, finish), no errors", sc["quality"] == "high" and sc["passes"] == 3 and not p.errs, (sc, p.errs))
            ctx.close()

            # ---- 3. the real mode: the site's events + a Planner on this phone; the ledger keeps it, the export carries it
            real = build.build(fixture.data(), fixture.home(), fixture.NOW)
            make_site(tmp, real)
            plan = f"localStorage.setItem('planner.v1', {json.dumps(json.dumps(planner_doc(today)))})"
            ctx, p = page([plan])
            ready(p)
            p.wait_for_timeout(600)
            s = st(p)
            site_xp = S.score(real["events"], R, today)["xp"]
            check("g. real mode: no DEMO badge, the Planner linked, its XP counted (tasks, habits, the daily goal), the site's XP as published",
                  not s["demo"] and not p.is_visible("#demo") and s["linked"].get("planner") and (s["bySrc"] or {}).get("planner", 0) == 3 * 5 + 3 * 5 + 20
                  and (s["bySrc"] or {}).get("site") == site_xp and not p.errs, (s, p.errs))
            check("g. not linked: no vault, no Kalshi feed -> no XP from them, the log says so",
                  not s["linked"].get("vault") and not s["linked"].get("kalshi") and not (s["bySrc"] or {}).get("obsidian") and not (s["bySrc"] or {}).get("kalshi"))
            check("g. the first visit only marks the level (no level-up on a first open)", s["levelups"] == 0)
            led = p.evaluate("JSON.parse(localStorage.getItem('arena.v1'))")
            check("g. the progress is kept on this phone: localStorage 'arena.v1' with every event and its source + the seen level",
                  led and len(led["events"]) >= len(real["events"]) and all(e.get("src") for e in led["events"]) and led["seen"]["level"] == s["level"], (led or {}).get("seen"))
            ex = json.loads(p.evaluate("ARENA.exportText()"))
            check("g. export: a JSON file of every event with its source and the score it gives",
                  ex["kind"] == "olympus-arena-export" and len(ex["events"]) == len(led["events"]) and ex["score"]["xp"] == s["xp"], ex.get("score"))
            p.click("[data-tab=log]")
            p.wait_for_timeout(200)
            with p.expect_download() as dl:
                p.click("#export")
            check("g. the Export button downloads arena-progress-<day>.json", dl.value.suggested_filename == f"arena-progress-{today}.json", dl.value.suggested_filename)
            check("g. the Planner's task titles stay text (no HTML from the phone's data)", p.evaluate("document.querySelectorAll('#sheet b b').length") == 0)
            p.reload()
            p.wait_for_function("window.ARENA && ARENA.state().ready", timeout=90000)
            p.wait_for_timeout(800)
            s2 = st(p)
            check("g. reload: the same XP from the kept ledger, no level-up replay", s2["xp"] == s["xp"] and s2["levelups"] == 0, (s2["xp"], s["xp"]))
            card = p.evaluate("ARENA.card()")
            check("g. the card the page posts to Jarvis keeps the contract (rank, quests)", not card_ok(card) and card["lines"][0].startswith("Today: "), card_ok(card))
            p.screenshot(path=os.path.join(SHOTS, "arena-real.png"))
            ctx.close()

            # ---- 4. reduced motion: the level-up shows its banner, no flash animation, a still scene
            make_site(tmp)
            ctx, p = page([seen], reduced=True)
            ready(p)
            p.wait_for_function("ARENA.state().levelups > 0", timeout=120000)
            anim = p.evaluate("getComputedStyle(document.getElementById('flash')).animationName")
            check("g. reduced motion: the level-up still says so (banner), no flash animation, no errors",
                  st(p)["banner"].startswith("Rank up") and anim in ("none", "") and not p.errs, (anim, p.errs))
            ctx.close()
            br.close()
    finally:
        srv.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)


def main():
    part_a()
    part_b()
    part_c()
    part_d()
    part_e()
    part_f()
    part_h()
    if os.environ.get("ARENA_NO_BROWSER") != "1":
        run_browser()
    print(f"\n{sum(RES)}/{len(RES)} passed")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
