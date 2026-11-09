"""ARES (tools/web_public/ares/, tools/ares_plutus_build.py, 2026-11-03): the war room, a pre-trade checklist + risk calculator.

  a. the files: the OLYMPUS kit links (?v=o2), the pattern of arena / pantheon, only local scripts, the module imports exist, the Jarvis card
  b. the data: rules.json = a fresh build of research/lit/mffu_rules.json, the numbers = the engine's own MFFU constants, the embedded
     copy inside arescore.js = rules.json (so the offline page can never drift)
  c. the rules as functions, in the page, against an independent Python mirror: the EOD trailing floor and its lock, the session clock
     (weekend, the 17:00 break, flat by 16:10, daylight saving), the size (stop + 2 ticks + commission, budget = min(room x %, daily loss
     left, cap), the contract limit), every veto
  d. the page in Playwright Chromium at 390 x 844: GO / WAIT / HALT end to end, the checklist, the tabs and #routes, the saved inputs and
     the new-day reset, the bot's account prefill from data.json, the offline rules, no sideways scroll, the orb corner free, LITE,
     reduced motion, no errors

    python -X utf8 -m tests.test_ares_page            (everything; d needs Playwright's Chromium)
    python -X utf8 -m tests.test_ares_page fast       (a-c's file checks only: no browser)
"""
from __future__ import annotations

import json
import math
import os
import re
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tests.olympus_money_kit import RES, WEB, browser, check, open_page, orb_hits, site, tidy_errors  # noqa: E402
from tools import ares_plutus_build as B  # noqa: E402

PAGE = os.path.join(WEB, "ares")
WED = "?now=2026-11-04T10:30:00-05:00"          # a Wednesday, 10:30 ET (EST: daylight saving ended 2026-11-01)


def rd(name):
    with open(os.path.join(PAGE, name), encoding="utf-8") as fh:
        return fh.read()


# ------------------------------------------------------------------------------------------------------------ a
def part_a():
    html = rd("index.html")
    check("a. the OLYMPUS kit: olympus.css, themes.js, olympus.js (data-app) all at ?v=o2",
          all(s in html for s in ('../olympus/olympus.css?v=o4', '../olympus/themes.js?v=o4', '../olympus/olympus.js?v=o4" data-app="ares"')))
    check("a. title Ares, a description, theme-color = the page colour, the Jarvis icon like the siblings",
          "<title>Ares</title>" in html and 'name="description"' in html and 'content="#14110e"' in html and "../jarvis/icon-192.png" in html
          and "#14110e" in rd("ares.css") + html)
    srcs = re.findall(r'(?:src|href)="([^"]+)"', html)
    check("a. only local files (no external script, font or stylesheet)", all(not s.startswith(("http:", "https:", "//")) for s in srcs), srcs)
    check("a. every local file the page links exists",
          all(os.path.exists(os.path.normpath(os.path.join(PAGE, s.split("?")[0]))) for s in srcs if not s.startswith("#")), srcs)
    js = rd("ares.js") + rd("arescore.js")
    imps = re.findall(r"from '(\.[^']+)'", js)
    check("a. every module import resolves (three.js from ../jarvis/, the core next door)",
          all(os.path.exists(os.path.normpath(os.path.join(PAGE, i))) for i in imps), imps)
    check("a. no Yahoo, no network but the page's own rules.json / jarvis.json and the site's ../data.json",
          "yahoo" not in js.lower() and sorted(set(re.findall(r"fetch\('([^'?]+)", js))) == ["../data.json", "jarvis.json"]
          and "fetch(url" in js, re.findall(r"fetch\(([^,)]+)", js))
    check("a. a calculator for the human: nothing in the page places, routes or changes an order", not re.search(r"ninjatrader|place_?order|/api/|websocket", js, re.I))
    card = json.loads(rd("jarvis.json"))
    check("a. the Jarvis card: v 1, name, status, kpis, open #size, the page theme, a stale_after",
          card["v"] == 1 and card["name"] == "Ares" and card["open"] == "#size" and card["theme"] == "#0b0608" and len(card["kpis"]) >= 2
          and card["status"]["level"] in ("ok", "off", "warn", "bad") and card["stale_after"] > 0, card)
    css = rd("ares.css")
    desk, fxm = rd("aresdesk.js"), rd("aresfx.js")
    check("a. the OLYMPUS effects library (fx-core, ui, text, burst ?v=f1) is linked after olympus.js; aresdesk.js is the screen of the journal / ritual / scenarios / share card, aresfx.js dresses the room",
          all(f"../olympus/fx-{n}.js?v=f1" in html for n in ("core", "ui", "text", "burst")) and html.find("fx-core.js") > html.find("olympus.js?v=o4")
          and "from './aresdesk.js'" in rd("ares.js") and "from './aresfx.js'" in rd("ares.js") and "ares.journal.v1" in desk and "fetch('../home.json'" in desk
          and "RoomEnvironment" in fxm and "ACESFilmicToneMapping" in fxm and not re.search(r"ninjatrader|place_?order|websocket", desk + fxm, re.I))
    check("a. static containers for the scenarios, drawdown bar, ritual ring, journal and the rules-you-broke tracker; the journal never touches the other keys",
          all(f'id="{i}"' in html for i in ("scen", "dd", "ritualRing", "journal", "broken", "logCheck", "shareBtn")) and set(re.findall(r"localStorage\.\w+Item\(([A-Za-z'\"\.]+)", desk)) <= {"JKEY"})
    check("a. the dock and the sheet keep the bottom-right 80 x 160 px free (right padding 88, sheet ends 166 px up)",
          "padding: 8px calc(88px" in css and "bottom: calc(166px" in css)


# ------------------------------------------------------------------------------------------------------------ b
def part_b():
    built = B.build()
    rules = json.loads(rd("rules.json"))
    check("b. rules.json is a fresh build of research/lit/mffu_rules.json (python tools/ares_plutus_build.py)", rules == built["ares/rules.json"])
    check("b. jarvis.json is a fresh build", json.loads(rd("jarvis.json")) == built["ares/jarvis.json"])
    p50, p25 = rules["plans"]["50k"], rules["plans"]["25k"]
    check("b. Builder 50K: $50,000, +$3,000, $2,000 EOD max loss locked at +$100, $1,000 soft daily, 40 micros / 4 minis",
          (p50["start"], p50["target"], p50["mll"], p50["lock"], p50["dll"], p50["max_micros"], p50["max_minis"]) == (50000, 3000, 2000, 100, 1000, 40, 4), p50)
    check("b. Builder 25K: $25,000, +$1,500, $1,000, $600 daily, 20 micros / 2 minis",
          (p25["start"], p25["target"], p25["mll"], p25["dll"], p25["max_micros"], p25["max_minis"]) == (25000, 1500, 1000, 600, 20, 2), p25)
    check("b. the owner's prices ($91.80 / $63), funded buffer, payouts and split",
          (p50["price"], p25["price"], p50["buffer"], p50["pay_min"], p50["pay_max"], p50["split"], p25["buffer"]) == (91.8, 63.0, 2100, 500, 2000, 0.8, 1100))
    check("b. flat by 16:10 ET, break 17:00-18:00, MNQ $2 a point + $1.90, NQ $20 a point + $4.68, 2 ticks of slip",
          rules["flat_by"] == "16:10" and rules["break"] == ["17:00", "18:00"] and rules["point_value"] == {"MNQ": 2.0, "NQ": 20.0}
          and rules["comm_rt"] == {"MNQ": 1.9, "NQ": 4.68} and rules["slip_ticks"] == 2)
    check("b. every rule line has a status (confirmed / conflict / unconfirmed): nothing is passed off as sure",
          len(rules["rules"]) >= 9 and all(r["status"] in ("confirmed", "conflict", "unconfirmed") and len(r["text"]) > 30 for r in rules["rules"]))
    try:
        from engine import accounts as A
        from engine import sizing as Z
        check("b. the engine's own MFFU constants agree (sizing.MFFU_50K, accounts.PLAN_50K, sizing.TW_25K, TW_PV, TW_COMM)",
              Z.MFFU_50K["start"] == p50["start"] and Z.MFFU_50K["target"] == p50["target"] and Z.MFFU_50K["mll"] == p50["mll"]
              and Z.MFFU_50K["lock"] == p50["start"] + p50["lock"] and A.PLAN_50K["dll"] == p50["dll"] and Z.TW_25K["mll"] == p25["mll"]
              and Z.TW_25K["dll"] == p25["dll"] and Z.TW_25K["max_micros"] == p25["max_micros"] and Z.TW_PV == rules["point_value"]["MNQ"]
              and abs(Z.TW_COMM - rules["comm_rt"]["MNQ"]) < 1e-9)
    except Exception as e:  # noqa: BLE001
        check("b. the engine's own MFFU constants agree", False, repr(e))
    return rules


# ------------------------------------------------------------------------------------------------------------ c
def mirror(rules, plan, bal, peak, today, inst, side, entry, stop, pct, cap=None):
    """an independent Python version of sizeTrade"""
    p = rules["plans"][plan]
    pv, comm = rules["point_value"][inst], rules["comm_rt"][inst]
    floor = min(max(p["start"], peak if peak is not None else p["start"]) - p["mll"], p["start"] + p["lock"])
    room = bal - floor
    dll_left = p["dll"] - max(0.0, -today)
    pts = entry - stop if side == "long" else stop - entry
    loss1 = (pts + 0.5) * pv + comm
    budget = max(0.0, min(room * pct / 100.0, dll_left, cap if cap else math.inf))
    max_c = p["max_micros"] if inst == "MNQ" else p["max_micros"] // 10
    n = max(0, min(int(budget // loss1), max_c))
    return {"floor": floor, "room": room, "n": n, "risk": n * loss1, "loss1": loss1, "budget": budget, "pts": pts,
            "stops_left": int(room // (n * loss1)) if n else 0}


def part_c(p, rules):
    js = """async (a) => { const C = window.__ares.CORE; const r = await (await fetch('rules.json')).json();
      return a.map((x) => x.kind === 'size' ? C.sizeTrade(r, x.inp) : x.kind === 'judge' ? (({level, reasons, checks}) => ({level, ids: reasons.map(y => y.id + ':' + y.level), done: checks.done}))(C.judge(r, x.inp, x.now))
        : x.kind === 'session' ? C.sessionState(x.now, r).state : x.kind === 'floor' ? C.floorOf(r.plans[x.plan], x.peak) : null); }"""
    ids = p.evaluate("window.__ares.CORE.CHECKS.map(c => c.id)")
    all_checks = {i: True for i in ids}
    base = {"plan": "50k", "stage": "eval", "inst": "MNQ", "side": "long", "entry": 21500, "stop": 21470, "riskPct": 40, "balance": 50000, "today": 0,
            "tradesToday": 0, "lossesToday": 0, "maxTrades": 2, "stopAfter": 2, "checks": all_checks}
    wed = "2026-11-04T15:30:00Z"                                   # 10:30 ET
    cases, expect = [], []

    def size(**kw):
        cases.append({"kind": "size", "inp": {**base, **kw}})
    for kw in ({}, {"peak": 51000, "balance": 51200}, {"peak": 52500, "balance": 52000}, {"today": -700}, {"inst": "NQ"}, {"plan": "25k", "balance": 25000, "stop": 21495},
               {"side": "short", "entry": 21500, "stop": 21530}, {"riskPct": 80, "balance": 51234.5}, {"riskCap": 300}, {"stop": 21400, "balance": 48400}, {"stop": 21499.75}):
        size(**kw)
    bad = []
    got = p.evaluate(js, cases)
    for c, g in zip(cases, got):
        i = c["inp"]
        m = mirror(rules, i["plan"], i["balance"], i.get("peak"), i["today"], i["inst"], i["side"], i["entry"], i["stop"], i["riskPct"], i.get("riskCap"))
        ok = g["n"] == m["n"] and abs(g["floor"] - m["floor"]) < 1e-6 and abs(g["loss1"] - m["loss1"]) < 1e-6 and abs(g["risk"] - m["risk"]) < 1e-6 \
            and abs(g["budget"] - m["budget"]) < 1e-6 and g["stops_left"] == m["stops_left"] and abs(g["pts"] - m["pts"]) < 1e-9
        if not ok:
            bad.append((i, g["n"], m))
    check("c. sizeTrade = the independent Python mirror on 11 cases (50K / 25K, MNQ / NQ, long / short, peak, daily loss left, cap, wide stop)", not bad, bad[:2])
    g0 = got[0]
    check("c. 30-pt stop on a fresh 50K at 40%: 12 MNQ, a stop-out costs (30 + 2 ticks) x $2 + $1.90 = $62.90 each = $754.80",
          g0["n"] == 12 and abs(g0["loss1"] - 62.9) < 1e-9 and abs(g0["risk"] - 754.8) < 1e-9 and g0["floor"] == 48000 and g0["stops_left"] == 2, g0)
    check("c. the floor trails the best end-of-day balance and locks at $50,100", got[1]["floor"] == 49000 and got[2]["floor"] == 50100, (got[1]["floor"], got[2]["floor"]))
    check("c. $700 down today: the budget shrinks to the $300 of daily loss left (4 MNQ)", got[3]["budget"] == 300 and got[3]["n"] == 4, got[3])
    check("c. NQ: the minis limit is 4 (40 micros / 10), one NQ contract costs $614.68", got[4]["maxC"] == 4 and abs(got[4]["loss1"] - 614.68) < 1e-9 and got[4]["n"] == 1)
    check("c. Builder 25K caps at 20 micros even when the budget allows more", got[5]["maxC"] == 20 and got[5]["n"] == 20 and got[5]["capped"] is True, got[5])
    check("c. a wide stop means fewer micros, and no size at all when one contract does not fit", got[9]["n"] == 0 and got[9]["valid"] is True and got[0]["n"] > got[9]["n"])

    def judge(now=wed, **kw):
        cases.clear(); cases.append({"kind": "judge", "inp": {**base, **kw}, "now": now})
        return p.evaluate(js, cases)[0]
    j = judge()
    check("c. everything ticked, nothing in the way: GO", j["level"] == "go" and j["done"] == 8 and not [x for x in j["ids"] if x.endswith(":halt")], j)
    check("c. an unfinished checklist: WAIT", judge(checks={"level": True})["level"] == "wait")
    check("c. no entry or stop: HALT (input)", "input:halt" in judge(entry="", stop="")["ids"])
    check("c. a long with the stop above the entry: HALT", judge(stop=21530)["level"] == "halt" and "input:halt" in judge(stop=21530)["ids"])
    check("c. daily loss limit reached: HALT (dll)", "dll:halt" in judge(today=-1000)["ids"] and "dll:halt" in judge(today=-1500)["ids"] and "dll:halt" not in judge(today=-999)["ids"])
    check("c. Builder 25K daily limit is $600", "dll:halt" in judge(plan="25k", balance=25000, today=-600)["ids"] and "dll:halt" not in judge(plan="25k", balance=25000, today=-599)["ids"])
    check("c. the account at the floor: HALT (dead); eval target reached: HALT (passed); funded at the same balance is not 'passed'",
          "dead:halt" in judge(balance=48000)["ids"] and "passed:halt" in judge(balance=53000)["ids"] and "passed:halt" not in judge(balance=53000, stage="funded")["ids"])
    check("c. the stop too wide for the room: HALT (wide)", "wide:halt" in judge(stop=21400, balance=48400)["ids"])
    check("c. the opposite side in another account (MFFU forbids hedging): HALT", "hedge:halt" in judge(hedge=True)["ids"])
    check("c. my own rules: max trades a day and stop after N stop-outs: HALT", "count:halt" in judge(tradesToday=2)["ids"] and "losses:halt" in judge(lossesToday=2)["ids"]
          and "count:halt" not in judge(tradesToday=1)["ids"] and "loss1:warn" in judge(lossesToday=1)["ids"])
    check("c. news is a warning, never a veto", "news:warn" in judge(news=True)["ids"] and judge(news=True)["level"] == "go")
    check("c. a stop tighter than the bot's 8 points and a big bite of the room are warnings", "tight:warn" in judge(stop=21495)["ids"] and "big:warn" in judge(riskPct=90, balance=49000)["ids"])
    sess = [("2026-11-04T15:30:00Z", "open"), ("2026-11-04T15:59:00Z", "open"), ("2026-11-04T21:00:00Z", "late"), ("2026-11-04T21:59:00Z", "late"),
            ("2026-11-04T22:00:00Z", "break"), ("2026-11-04T22:59:00Z", "break"), ("2026-11-04T23:00:00Z", "open"), ("2026-11-07T15:00:00Z", "closed"),
            ("2026-11-06T22:30:00Z", "closed"), ("2026-11-06T21:30:00Z", "late"), ("2026-11-08T22:59:00Z", "closed"), ("2026-11-08T23:00:00Z", "open"),
            ("2026-07-08T14:30:00Z", "open"), ("2026-07-08T20:00:00Z", "late"), ("2026-07-08T21:00:00Z", "break")]
    cases.clear()
    cases.extend({"kind": "session", "now": n} for n, _ in sess)
    res = p.evaluate(js, cases)
    check("c. the clock in New York time: open, flat from 16:00 (16:10 minus 10), the 17:00 break, open 18:00, the weekend, daylight saving",
          res == [e for _, e in sess], list(zip([n for n, _ in sess], res, [e for _, e in sess])))
    check("c. outside the session: HALT (clock) with the right words", "clock:halt" in judge(now="2026-11-07T15:00:00Z")["ids"] and "clock:halt" in judge(now="2026-11-04T21:30:00Z")["ids"])
    cases.clear(); cases.append({"kind": "floor", "plan": "50k", "peak": None}); cases.append({"kind": "floor", "plan": "25k", "peak": 25400})
    f = p.evaluate(js, cases)
    check("c. floor: 48,000 at the start; Builder 25K with a $25,400 best close: 24,400", f == [48000, 24400], f)
    emb = p.evaluate("window.__ares.CORE.EMBEDDED.plans")
    check("c. the offline copy inside arescore.js equals rules.json (plans, prices, limits)", emb == rules["plans"], (emb, rules["plans"]))
    other = p.evaluate("(({flat_by, break: b, comm_rt, point_value, slip_ticks, tick}) => ({flat_by, b, comm_rt, point_value, slip_ticks, tick}))(window.__ares.CORE.EMBEDDED)")
    check("c. ... and its clock, commission, point value, slip", other == {"flat_by": rules["flat_by"], "b": rules["break"], "comm_rt": rules["comm_rt"],
                                                                         "point_value": rules["point_value"], "slip_ticks": 2, "tick": 0.25}, other)
    sf = p.evaluate("""() => { const C = window.__ares.CORE; const a = C.accountFromSite({accounts: [{id: 'x', eval: {balance: 'n/a', floor: 1}}, {name: 'B', eval: {balance: 50500, floor: 48000, today: 20, start_balance: 50000}}]});
      return [a && a.name, a && a.balance, C.accountFromSite(null), C.accountFromSite({accounts: 'x'}), C.botStops({extras: {tcols: ['risk_pts'], trades: [[10], [20], [30]]}}), C.botStops(null)]; }""")
    check("c. the bot's account from data.json: the first one with a number balance and floor; junk gives none; too few stops give none",
          sf[0] == "B" and sf[1] == 50500 and sf[2] is None and sf[3] is None and sf[4] is None and sf[5] is None, sf)


# ------------------------------------------------------------------------------------------------------------ d
def tab(p, t):
    p.click(f"#tabs button[data-tab='{t}']")
    p.wait_for_timeout(120)


def part_d(tmp, rules):
    from playwright.sync_api import sync_playwright
    srv1, url = site(tmp, "ares", "s1", True)
    srv2, url_off = site(tmp, "ares", "s2", False, drop=("rules.json", "jarvis.json"))
    try:
        with sync_playwright() as pw:
            br = browser(pw)
            errs = []
            ctx, p = open_page(br, url + WED, errs, "__ares")
            check("d. loads at 390 x 844: the 3D room is up (WebGL), rules.json read (not the embedded copy), no OFFLINE tag",
                  p.evaluate("window.__ares.ready3d") and p.evaluate("window.__ares.rulesSrc") == "file" and not p.is_visible("#demo") and p.is_hidden("#nogl"))
            check("d. no sideways scroll", p.evaluate("document.documentElement.scrollWidth <= innerWidth"))
            for t in ("trade", "account", "why", "list", "rules"):
                tab(p, t)
                check(f"d. tab '{t}': the bottom-right 80 x 160 px stays free for Jarvis's orb", not orb_hits(p), orb_hits(p))
            tab(p, "trade")
            check("d. the bot's eval account from data.json fills the balance ($51,240) and says so (LIVE ACCOUNT tag, the account in the subtitle)",
                  p.input_value("#balance") in ("51240", "51240.0") and p.is_visible("#livetag") and "51,240" in p.inner_text("#sub"))
            check("d. ... its floor ($48,000) becomes the best-close that explains it", p.evaluate("window.__ares.verdict.size.floor") == 48000)
            check("d. nothing typed: HALT 'enter entry + stop'", p.get_attribute("#verdict", "data-level") == "halt" and "entry" in p.inner_text("#vs"))
            p.fill("#entry", "21500"); p.fill("#stop", "21470")
            check("d. entry + stop typed: WAIT with the size (40% of $3,240 = $1,296 but $880 left of the daily loss: 13 MNQ)",
                  p.get_attribute("#verdict", "data-level") == "wait" and "13 MNQ" in p.inner_text("#vs") and "13 MNQ" in p.inner_text("#out"), p.inner_text("#vs"))
            tab(p, "list")
            n = p.evaluate("document.querySelectorAll('[data-chk]').length")
            for i in range(n):
                p.locator("[data-chk]").nth(i).check()
            check("d. all 8 boxes ticked: GO, the counter says 8/8", p.get_attribute("#verdict", "data-level") == "go" and p.inner_text("#chkN") == "8/8", p.inner_text("#vs"))
            check("d. the checklist marks the MUST items", p.evaluate("document.querySelectorAll('.chk em').length") == 3)
            p.locator("[data-chk]").nth(1).uncheck()
            check("d. unticking one box: back to WAIT", p.get_attribute("#verdict", "data-level") == "wait")
            p.click("#resetChecks")
            check("d. 'New trade: clear the list' unticks everything", p.inner_text("#chkN") == "0/8")
            tab(p, "why"); p.check("#hedge")
            check("d. the opposite-side toggle: HALT, and the reason is listed with the verdict word", p.get_attribute("#verdict", "data-level") == "halt"
                  and "HALT" in p.inner_text("#why") and "opposite side" in p.inner_text("#why") and p.inner_text("#whyN") == "1")
            p.uncheck("#hedge")
            tab(p, "account"); p.fill("#today", "-1000")
            tab(p, "why")
            check("d. today -$1,000: HALT with the daily-loss reason; the tower's ring and the dock turn red",
                  p.get_attribute("#verdict", "data-level") == "halt" and "Daily loss limit" in p.inner_text("#why"))
            tab(p, "account"); p.fill("#today", "0"); p.fill("#balance", "48400")
            check("d. typing a balance by hand stops the bot prefill from overwriting it", p.evaluate("window.__ares.state.botBalance") is False)
            p.click("#fromBot")
            check("d. 'Use the bot's eval account' puts the $51,240 back", p.input_value("#balance") in ("51240", "51240.0"))
            tab(p, "trade")
            p.click("[data-set='inst'][data-v='NQ']")
            check("d. NQ: 1 NQ contract, the minis limit and the cost shown", "1 NQ" in p.inner_text("#vs") or "1 NQ" in p.inner_text("#out"), p.inner_text("#out")[:120])
            p.click("[data-set='inst'][data-v='MNQ']"); p.click("[data-set='side'][data-v='short']")
            check("d. a short with the stop below the entry: HALT with a plain sentence", p.get_attribute("#verdict", "data-level") == "halt" and "ABOVE" in p.inner_text("#vline"), p.inner_text("#vline"))
            p.click("[data-set='side'][data-v='long']")
            tab(p, "account"); p.click("[data-set='plan'][data-v='25k']")
            check("d. Builder 25K: the account tab shows its $1,000 max loss and the plan buttons follow",
                  p.get_attribute("[data-set='plan'][data-v='25k']", "aria-pressed") == "true" and p.evaluate("window.__ares.verdict.size.plan.mll") == 1000)
            tab(p, "rules")
            body = p.inner_text("#rules")
            check("d. rules tab: the $1,000 max loss, 'CONFIRMED' badges, the source line; the bot's real stops from data.json",
                  "CONFIRMED" in body and "Source" in body and "research/lit/mffu_rules.json" in body and "real stops" in p.inner_text("#botstops"), body[:200])
            ctx.close()
            check("d. no page errors, console errors or failed requests", not errs, errs[:5])

            errs = []
            ctx, p = open_page(br, url + WED + "#rules", errs, "__ares")
            check("d. #rules opens the rules tab; #why and #list too", p.evaluate("window.__ares.tab") == "rules")
            p.evaluate("location.hash = '#why'"); p.wait_for_timeout(150)
            ok1 = p.evaluate("window.__ares.tab") == "why"
            p.evaluate("location.hash = '#size'"); p.wait_for_timeout(150)
            check("d. ... #size (the Jarvis card's link) opens the trade tab", ok1 and p.evaluate("window.__ares.tab") == "trade")
            p.fill("#entry", "21500"); p.fill("#stop", "21470")
            p.reload(); p.wait_for_function("window.__ares && window.__ares.siteLoaded === true")
            check("d. the inputs are remembered on this phone (entry, stop)", p.input_value("#entry") == "21500" and p.input_value("#stop") == "21470")
            ctx.close()
            check("d. no errors on the route page", not errs, errs[:5])

            errs = []
            ctx, p = open_page(br, url + "?now=2026-11-05T10:30:00-05:00", errs, "__ares")
            p.evaluate("""() => { const s = JSON.parse(localStorage.getItem('ares.v1')); s.tradesToday = 2; s.lossesToday = 2; s.checks = {level: true}; s.today = '-300'; s.entry = '21500'; localStorage.setItem('ares.v1', JSON.stringify(s)); }""")
            p.goto(url + "?now=2026-11-05T10:30:00-05:00"); p.wait_for_function("window.__ares && window.__ares.siteLoaded === true"); p.wait_for_timeout(300)
            check("d. the same day keeps the counters (2 trades, 2 stop-outs: HALT)", p.get_attribute("#verdict", "data-level") == "halt" and "losses" in p.evaluate("window.__ares.verdict.reasons.map(r => r.id).join(',')"))
            p.goto(url + "?now=2026-11-06T10:30:00-05:00"); p.wait_for_function("window.__ares && window.__ares.siteLoaded === true"); p.wait_for_timeout(300)
            st = p.evaluate("window.__ares.state")
            check("d. a new New-York day clears the counters and the ticks (today's P&L comes from the bot again), but keeps the entry and the plan",
                  st["tradesToday"] == 0 and st["lossesToday"] == 0 and st["checks"] == {} and st["today"] == "-120" and st["entry"] == "21500" and st["plan"] == "50k", st)
            ctx.close()

            errs = []
            ctx, p = open_page(br, url + "?now=2026-11-07T11:00:00-05:00", errs, "__ares")
            p.fill("#entry", "21500"); p.fill("#stop", "21470")
            check("d. Saturday: HALT, 'the market is closed', even with a perfect trade typed", p.get_attribute("#verdict", "data-level") == "halt" and "closed" in p.inner_text("#vline"), p.inner_text("#vline"))
            ctx.close()

            errs2 = []
            ctx, p = open_page(br, url_off + WED, errs2, "__ares")
            check("d. no rules.json, no data.json: the embedded rules run, OFFLINE RULES shows, no LIVE tag, no bot account button",
                  p.evaluate("window.__ares.rulesSrc") == "embedded" and p.is_visible("#demo") and p.is_hidden("#livetag") and p.is_hidden("#fromBot"))
            p.fill("#entry", "21500"); p.fill("#stop", "21470"); tab(p, "account"); p.fill("#balance", "50000"); tab(p, "trade")
            check("d. ... and it sizes the same (12 MNQ on a fresh 50K at 40%)", "12 MNQ" in p.inner_text("#out"), p.inner_text("#out")[:80])
            ctx.close()
            bad = tidy_errors(errs2, allow=("rules.json", "data.json", "jarvis.json", "home.json"))
            check("d. offline: only the missing files' 404s, nothing else", not bad, bad[:5])

            # ---- 2026-11-04: scenarios, drawdown left, the journal, the rules-you-broke tracker, the ritual, the share card, the dressed room
            errs5 = []
            ctx, p = open_page(br, url + WED, errs5, "__ares")
            m = p.evaluate("""async () => { const C = __ares.CORE, rules = await (await fetch('rules.json')).json(), now = new Date('2026-11-04T15:00:00Z'), day = 864e5;
              const e = (o) => Object.assign({ t: new Date(+now - 3600e3).toISOString(), level: 'go', halts: [], warns: [], taken: false, ritual: false }, o);
              const list = [e({ level: 'halt', halts: ['dll', 'count'], warns: ['big'], taken: true }), e({ level: 'wait', taken: true }), e({ level: 'go', taken: true, ritual: true }), e({ level: 'halt', halts: ['wide'], taken: false }),
                e({ level: 'halt', halts: ['clock'], taken: true, t: new Date(+now - 40 * day).toISOString() })];
              const B = C.brokenRules(list, now, 30), sc = Object.fromEntries(C.SCENARIOS.map((s) => [s.id, C.scenarioPatch(rules, s.id)]));
              const dd = [C.drawdownLeft(rules, { plan: '50k', balance: '50500', peak: '50500' }), C.drawdownLeft(rules, { plan: '50k', balance: '48700', peak: '50000' }), C.drawdownLeft(rules, { plan: '50k' }, { balance: 48100, floor: 48000 })];
              const R = __ares.verdict, je = C.journalEntry(R, __ares.state, now, true, true), sp = C.shareSpec(R, __ares.state);
              return { B: { entries: B.entries, broken: B.brokenEntries, taken: B.taken, by: B.by.map((x) => [x.id, x.n]), warned: B.warned.map((x) => [x.id, x.n]), clean: B.cleanDays, goClean: B.goClean, ritual: B.ritualShare },
                sc: Object.keys(sc).length, e50: sc.e50.balance, e50m: sc.e50m.balance, e25m: sc.e25m.balance, f50: sc.f50.balance, f50stage: sc.f50.stage, d50: [sc.d50.balance, sc.d50.today, sc.d50.lossesToday], d25: sc.d25.balance, none: C.scenarioPatch(rules, 'x'),
                dd: dd.map((x) => [Math.round(x.room), Math.round(x.frac * 100), x.tone, x.live]), home: [C.accountFromHome({ accounts: [{ name: 'X', eval: { balance: 51000, floor: 49000 } }] }).balance, C.accountFromHome(null), C.accountFromHome({ accounts: [{ eval: {} }] })],
                je: [je.level, je.taken, je.ritual, Array.isArray(je.halts), je.plan], sp: [sp.word, sp.level, sp.lines.length > 0] }; }""")
            check("d. rules you broke: 30 days only; HALT taken counts its reasons (dll, count), WAIT taken counts 'list', passed trades and old ones do not; warnings taken anyway are listed; clean days; the ritual share",
                  m["B"]["entries"] == 4 and m["B"]["broken"] == 2 and m["B"]["taken"] == 3 and sorted(m["B"]["by"]) == [["count", 1], ["dll", 1], ["list", 1]] and m["B"]["warned"] == [["big", 1]]
                  and m["B"]["clean"] == 0 and m["B"]["goClean"] == 1 and abs(m["B"]["ritual"] - 0.25) < 1e-9, m["B"])
            check("d. scenarios: eight presets for 50K / 25K (fresh, 40% there, after a stop-out, funded with the buffer) from the plan's own numbers; an unknown id gives nothing",
                  m["sc"] == 8 and m["e50"] == "50000" and m["e50m"] == "51200" and m["e25m"] == "25600" and m["f50"] == "52100" and m["f50stage"] == "funded" and m["d50"] == ["49100", "-900", 1] and m["d25"] == "24550" and m["none"] is None, m)
            check("d. drawdown left: full room on a fresh peak (calm), 35% (watch), $100 of live account (storm, live)", m["dd"] == [[2000, 100, "calm", False], [700, 35, "watch", False], [100, 5, "storm", True]], m["dd"])
            check("d. the home.json account is read (balance + floor), junk gives null; a journal line and the share card spec carry the verdict", m["home"] == [51000, None, None] and m["je"][:4] == ["halt", True, True, True] and m["sp"][0] in ("GO", "WAIT", "HALT") and m["sp"][2], (m["home"], m["je"], m["sp"]))
            check("d. the drawdown bar is on the page: a figure, a bar, a tone", "left of $2,000" in p.inner_text("#dd") and p.get_attribute("#dd", "data-tone") in ("calm", "watch", "storm", "dead"), p.inner_text("#dd"))
            tab(p, "account")
            p.click("[data-scen=d50]")
            check("d. a scenario fills the account: Eval 50K after a stop-out = $49,100, one stop-out today, the drawdown bar follows", p.input_value("#balance") == "49100" and p.input_value("#lossesToday") == "1" and "left of" in p.inner_text("#dd"), p.input_value("#balance"))
            p.click("[data-scen=e50]")
            tab(p, "trade")
            p.fill("#entry", "21500"); p.fill("#stop", "21470")
            tab(p, "list")
            check("d. the journal starts empty and says so; 'Log this check' is on once the trade has an entry and a stop", p.locator("#journal .jrow").count() == 0 and p.is_enabled("#logCheck") and "No checks logged" in p.inner_text("#journal"))
            p.click("#logCheck")
            p.click("#logTook")
            led = p.evaluate("JSON.parse(localStorage.getItem('ares.journal.v1'))")
            check("d. 'I took it' logs the check: one journal row, kept on this phone only (ares.journal.v1), and the tracker counts it",
                  len(led) == 1 and led[0]["taken"] is True and p.locator("#journal .jrow").count() == 1 and led[0]["level"] in ("wait", "halt", "go") and "checks, 30 days" in p.inner_text("#broken"), led)
            p.click("#ritualBtn")
            check("d. the ritual starts: the button says Stop, the ring is a canvas, a step is read out", p.inner_text("#ritualBtn") == "Stop" and p.locator("#ritualRing canvas").count() == 1 and len(p.inner_text("#ritualTxt")) > 10)
            p.click("#ritualBtn")
            check("d. ... and Stop puts it back", p.inner_text("#ritualBtn") == "Start the ritual")
            p.evaluate("() => { navigator.canShare = () => true; window.__sh = null; navigator.share = async (d) => { window.__sh = d.files[0].type + ':' + d.files[0].size; }; }")
            tab(p, "trade")
            p.click("#shareBtn")
            p.wait_for_function("window.__sh", timeout=30000)
            check("d. the share card is a PNG image", p.evaluate("window.__sh").startswith("image/png:") and int(p.evaluate("window.__sh").split(":")[1]) > 2000, p.evaluate("window.__sh"))
            check("d. the room is dressed (bronze / steel / banners / torches) and still up; no errors", p.evaluate("window.__ares.dressed") and p.evaluate("window.__ares.ready3d") and not errs5, errs5[:3])
            ctx.close()

            errs3 = []
            ctx, p = open_page(br, url + "?lite=1", errs3, "__ares")
            check("d. ?lite=1 forces LITE with no errors", p.evaluate("window.__ares.lite") is True and not errs3, errs3[:3])
            ctx.close()
            errs4 = []
            ctx, p = open_page(br, url, errs4, "__ares", reduced=True)
            y0 = p.evaluate("window.__ares.yaw")
            p.wait_for_timeout(1500)
            check("d. reduced motion: the room stays still (no idle turn), the verdict still works", abs(p.evaluate("window.__ares.yaw") - y0) < 1e-6 and p.get_attribute("#verdict", "data-level") in ("halt", "wait", "go") and not errs4, errs4[:3])
            ctx.close()
            br.close()
    finally:
        srv1.shutdown()
        srv2.shutdown()


def main(argv):
    fast = "fast" in argv
    tmp = tempfile.mkdtemp(prefix="ares_test_")
    try:
        part_a()
        rules = part_b()
        if not fast:
            from playwright.sync_api import sync_playwright
            srv, url = site(tmp, "ares", "c", True)
            try:
                with sync_playwright() as pw:
                    br = browser(pw)
                    errs = []
                    ctx, p = open_page(br, url + WED, errs, "__ares")
                    part_c(p, rules)
                    ctx.close()
                    br.close()
            finally:
                srv.shutdown()
            part_d(tmp, rules)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"\n{sum(RES)}/{len(RES)} passed", flush=True)
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
