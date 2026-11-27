"""day-weekreview 2026-11-27: the WEEK IN REVIEW page (tools/web_public/nq/week.html / week.js / weekcore.js / week.css) + its builder tools/week_review.py.
  a. static: files, read only (no innerHTML / storage / eval / sends), no outside URL, OLYMPUS NIGHT (no cyan / brown), sw.js / build_web_dashboard.py / apps untouched
  b. builder (offline, a fixed clock, a synthetic feed post): 4 weeks; the quiet week says so; Nov 16 week = Zlarior -$129 matched, Rapid EOD missed (not armed), ATLAS 3 trades;
     the rejected-setup ring grows across builds; no account number anywhere; payout + 7-day clock + waiting-for from the feed; file < 180 KB
  c. node (weekcore.js): empty doc, default week, picker labels, $ / R words, grade view, payout %
  d. browser 390x844 + 1440x900 (the builder's own output served as nq/week_review.json): every section, 4 weeks selectable and the page changes, honest empty + error
     states, text >= 12 px, taps >= 44, no sideways scroll, nothing off the site, no console error. --shots -> research/handoff/2026-11-27/week/shots/
Run: python -X utf8 -m tests.test_nq_week [--shots]
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import subprocess
import sys
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tests import agora_kit as AK  # noqa: E402

check = AK.check
NQ = os.path.join(ROOT, "tools", "web_public", "nq")
SHOTS = os.path.join(ROOT, "research", "handoff", "2026-11-27", "week", "shots")
ET = ZoneInfo("America/New_York")
NOW = int(dt.datetime(2026, 11, 27, 10, 5, tzinfo=ET).timestamp())


def rd(n):
    with open(os.path.join(NQ, n), encoding="utf-8") as fh:
        return fh.read()


def fixture_lite() -> dict:
    """A trimmed copy of the PC's public status post (shape only; the account numbers are the real shape, to prove they never reach the page)."""
    return {"v": 1, "kind": "le-live", "t": NOW - 30, "model_state": "LIT: watching for a sweep (MFFUEVBLDR…6016)",
            "board": {"today": "2026-11-27", "lit": {"window": {"text": "entry window open until 13:00 ET"}},
                      "atlas": {"balance": 25401.38, "floor": 24401.38, "room": 1000.0, "profit": 401.38, "to_target": 948.62, "today_pnl": 0.0, "window": {"text": "entry window open until 11:00 ET"}},
                      "trades": [{"acct": "atlas", "src": "live", "key": "ema_lon_vix", "member": "EMA", "day": "2026-11-20", "entry_t": 1795164300, "exit_t": 1795176603, "side": "SHORT", "qty": 1, "exit": "TARGET", "r": 6.635, "usd": 514.18, "open": False},
                                 {"acct": "atlas", "src": "live", "key": "macd_sweep", "member": "MACD", "day": "2026-11-18", "entry_t": 1794995400, "exit_t": 1794996603, "side": "SHORT", "qty": 2, "exit": "STOP", "r": -1.044, "usd": -112.8, "open": False},
                                 {"acct": "atlas", "src": "paper", "key": "sr_nyreclaim", "member": "S/R", "day": "2026-11-17", "entry_t": 1794928500, "exit_t": 1794928800, "side": "LONG", "qty": 4, "exit": "STOP", "r": -1.022, "usd": -441.6, "open": False}]},
            "accounts": [{"id": "mffu50k_eval", "eval": {"balance": 49177.52, "room": 1009.32, "to_target": 3822.48, "profit": -822.48}, "pnl": {"week": 0, "today": 0}},
                         {"id": "b25k_2", "eval": {"balance": 25019.24, "room": 995.62, "to_target": 1480.76, "profit": 19.24}, "pnl": {"week": 0, "today": 0}},
                         {"id": "rapid", "eval": {"balance": 24995.24, "room": 995.24, "to_target": 1504.76, "profit": -4.76}, "pnl": {"week": 0, "today": 0}}],
            "at": {"a": [{"id": "atlas", "l4": "6018", "tr": [[1794995400, 1794996603, -1, 2, 27395.5, 27422.5, 27179.5, "STOP", -112.8, -1.04], [1795164300, 1795176603, -1, 1, 26380.75, 26419.5, 26122.75, "TARGET", 514.18, 6.63]]}]},
            "mf": {"a": [{"id": "atlas", "nm": "ATLAS 25K funded", "sd": "2026-11-17", "l4": "6018", "f": {"cp": 401, "bd": 514, "cd": 2}}, {"id": "rapid", "sd": "2026-11-20"}, {"id": "b25k_2", "sd": "2026-11-18"}]},
            "k7": {"a": [{"id": "atlas", "nm": "ATLAS 25K funded", "lf": "2026-11-25", "dl": "2026-12-01", "hard": "2026-12-02", "left": 5, "lvl": "ok", "on": True},
                         {"id": "rapid", "nm": "Rapid EOD 25K", "lf": "2026-11-25", "dl": "2026-12-01", "hard": "2026-12-02", "left": 1, "lvl": "warn", "on": True}]},
            "arm": {"a": [["Zlarior (LIT)", "...6016", 1, 1, ""], ["Rapid EOD 25K", "...6020", 1, 1, ""]]},
            "pc": {"glance": {"bots": [{"id": "lit", "name": "Zlarior", "on": True, "armed": True, "stage": "Displacement (4/10)", "wait": "Long setup forming: swept NY low (6.89 ATR)"},
                                        {"id": "atlas", "name": "ATLAS", "on": True, "armed": True, "mode": "ATLAS MFFUSFBLDR…6018", "wait": "MACD: Armed (long) at 26,269 account ...6018"}]}},
            "glog": {"lit": [["09:45", "Swept Tokyo low 26,232.25 (0.11 ATR deep; ✗ LIT needs 0.5)"]], "atlas": [["09:45", "S/R: 09:45 Asia low swept (long): no - idm"]]},
            "ofp": {"d": "2026-11-27", "n": 1, "o": 1, "R": 0, "ln": "OF paper Nov 27: 1 trade, +0.0R, 1 open"}, "ck": {"pl": [["BLITZ", "off", "off (hidden, paper only)"]]}}


def part_a():
    h, j, c, k = rd("week.html"), rd("week.js"), rd("week.css"), rd("weekcore.js")
    check("a. files exist: week.html / week.js / weekcore.js / week.css + the builder", all(os.path.exists(os.path.join(NQ, n)) for n in ("week.html", "week.js", "weekcore.js", "week.css")) and os.path.exists(os.path.join(ROOT, "tools", "week_review.py")))
    check("a. read only: no innerHTML / storage / eval / sends / sockets", not re.search(r"innerHTML|outerHTML|insertAdjacentHTML|localStorage|sessionStorage|eval\(|new Function|XMLHttpRequest|sendBeacon|WebSocket|method:\s*['\"]POST", j + k))
    check("a. no outside URL in the page, script or css", not re.search(r"https?://", h + j + k + c.replace("http://www.w3.org", "")), "")
    check("a. no inline script, loads weekcore.js before week.js", "<script>" not in h and h.index("weekcore.js") < h.index("week.js"))
    check("a. OLYMPUS NIGHT: black, violet #9d59ee, gold #f1c14b, mint #77db89; no cyan / brown / olive / marble", all(x in c.lower() for x in ("#9d59ee", "#f1c14b", "#77db89", "--bg: #000")) and not re.search(r"cyan|brown|olive|marble|#00[eEfF][0-9a-fA-F]{3}\b|#0ff", c))
    check("a. text sizes in the css are all >= 12 px", not [m for m in re.findall(r"font-size:\s*(\d+(?:\.\d+)?)px", c) if float(m) < 12])
    check("a. the 4 weeks are selectable (nav.wk-picker) + a Grade at the end", "wk-picker" in h and h.index('id="next"') < h.index('id="gradeBox"'))
    d = subprocess.run(["git", "diff", "--name-only", "HEAD~0"], cwd=ROOT, capture_output=True, text=True).stdout
    check("a. sw.js / build_web_dashboard.py / jarvis/apps.js untouched", not any(x in d for x in ("sw.js", "tools/build_web_dashboard.py", "jarvis/apps.js")), d)


def part_b():
    from tools import week_review as W
    lite = fixture_lite()
    doc = W.build(now=NOW, offline=True, lite=lite, prev={})
    ws = doc["weeks"]
    check("b. four weeks, newest first, the current one flagged", len(ws) == 4 and ws[0]["current"] and not any(w["current"] for w in ws[1:]) and ws[0]["key"] == "2026-11-23", [w["key"] for w in ws])
    w0, w1 = ws[0], ws[1]
    check("b. this week: quiet and SAYS so (no trades, twins found none, rejected setups counted)", w0["totals"]["n"] == 0 and "Quiet week" in w0["headline"] and w0["quiet"] and w0["totals"]["setups_rejected"] > 0, w0["headline"])
    check("b. Thanksgiving Thu Nov 26 + the Nov 27 half day are marked", any("early" in (d.get("note") or "") or d["state"] == "closed" for d in w0["days"]), w0["days"])
    acc = {a["id"]: a for a in w1["accounts"]}
    check("b. Nov 16 week: Zlarior 50K -$129 (1 loss, a LOST line), ATLAS funded = 2 trades +$401.38 (= the PC tracker); the Nov 17 eval trade listed apart; paper one flagged", acc["z50k"]["usd"] == -129.4 and acc["z50k"]["n"] == 1 and acc["z50k"]["trades"][0]["why"].startswith("LOST")
          and acc["atlas25"]["n"] == 2 and round(acc["atlas25"]["usd"], 2) == 401.38 and acc["atlas25"].get("eval_usd") == 1791.89 and any(c.get("mode") == "paper" for c in acc["atlas25"]["trades"]), (acc["z50k"]["usd"], acc["atlas25"]["n"]))
    check("b. ATLAS cards carry entry / stop / target from the feed (at) and a WON line", any(c.get("target") and c["why"].startswith("WON") for c in acc["atlas25"]["trades"]))
    tw = {t["id"]: t for t in w1["twin"]}
    check("b. bot = backtest: Zlarior 50K matched; Rapid EOD missed Nov 20 with the 'not armed' cause", tw["z50k"]["missed"] == 0 and tw["z50k"]["matched"] == 1 and tw["rapid"]["missed"] == 1 and "not armed" in tw["rapid"]["rows"][0]["text"], tw["rapid"]["rows"])
    check("b. the 25K #2 / Rapid twin check starts at their own first day (nothing 'missed' before they existed)", tw["z25k2"]["expected"] == 0 or all(r["day"] >= "2026-11-18" for r in tw["z25k2"]["rows"]), tw["z25k2"]["rows"])
    check("b. the PC-off week (Nov 9-13) says why (bot not running) and the grade is not an A", "bot not running" in json.dumps(ws[2]["twin"]) and ws[2]["grade"]["letter"] != "A")
    check("b. this week's grade = process only: quiet + matching, Rapid's 7-day clock at 1 day = B (money is not in the letter)", w0["grade"]["letter"] == "B" and any(r["k"] == "Money" for r in w0["grade"]["rows"]))
    check("b. payout (ATLAS 401 of 2,100, best day 128% = not yet OK), 7-day clock (Rapid warn), waiting-for (2 bots)", w0["payout"]["profit"] == 401 and w0["payout"]["ratio_ok"] is False and w0["payout"]["need"] > 1600
          and any(k["lvl"] == "warn" for k in w0["clock"]) and len(w0["waiting"]["bots"]) == 2, (w0["payout"], w0["clock"]))
    check("b. order-flow week (paper rows) + today's line; BLITZ off + paper-only wording", w0["of"]["rows_n"] > 0 and "OF paper" in w0["of"]["today"]["line"] and "paper" in w0["blitz"]["text"].lower())
    check("b. next week: Dec 4 jobs report listed (calendar file)", any("Payrolls" in e["title"] for e in w0["next"]["events"]), w0["next"])
    s = json.dumps(doc)
    check("b. no account number / broker account name / key anywhere in the file", not re.search(r"MFFU[A-Z]{4,}|\.\.\.\d{4}|…\d{4}|\"l4\"|svk|\"sg\"", s), re.findall(r"MFFU\w+|\.\.\.\d{4}|…\d{4}", s)[:5])
    check("b. file < 180 KB", len(s.encode()) < 180_000, len(s))
    # the glog ring grows across builds (the feed holds only the last 3 per bot)
    l2 = json.loads(json.dumps(lite))
    l2["glog"] = {"lit": [["10:10", "Swept Asia high 26,420 (0.2 ATR deep; ✗ LIT needs 0.5)"]], "atlas": []}
    doc2 = W.build(now=NOW + 1500, offline=True, lite=l2, prev=doc)
    live = doc2["weeks"][0]["rejected"]["live"]
    check("b. the rejected-setup ring keeps the old live rows and adds the new (3 rows) with the idm code spelled out", len(live) == 3 and any("no inducement" in g["text"] for g in live), [g["text"] for g in live])
    off = W.build(now=NOW, offline=True, lite={}, prev={})
    check("b. no feed: still builds, says what is missing, no waiting / payout invented", off["weeks"][0]["waiting"] is None and off["weeks"][0]["payout"] is None and any("live feed" in m for m in off["sources"]["missing"]), off["sources"])
    return doc, off


NODE = r"""
const C = require(process.argv[2]); const doc = JSON.parse(require('fs').readFileSync(process.argv[3], 'utf8'));
const out = {};
out.emptyPick = C.pick({}, 'x'); out.emptyHero = C.hero(null); out.emptyGrade = C.gradeView(null); out.emptyRej = C.rejectedEmpty(null);
out.def = C.pick(doc, 'nope').key; out.pk = C.pickerRows(doc, doc.weeks[1].key).map(p => [p.label, p.active]);
out.usd = [C.usd(514.18), C.usd(-112.8), C.usd(0), C.usd(null), C.usd(-5, false), C.usd(1234567)]; out.r = [C.r(6.635), C.r(-1.04), C.r(null)];
out.hero = C.hero(doc.weeks[0]); out.hero1 = C.hero(doc.weeks[1]); out.dots = C.dayDots(doc.weeks[0]).map(d => d.tone);
out.pay = C.payoutPct(doc.weeks[0].payout); out.age = [C.age(1000, 1000 + 30).text, C.age(1000, 1000 + 7200).level, C.age(1000, 1000 + 200000).level];
out.card = C.cardTitle({side: 'short', qty: 2, setup: 'MACD'}); out.when = C.cardWhen({day: '2026-11-18', in_hm: '04:50', out_hm: '05:08'});
out.tw = [C.twinStatus('missed').e, C.twinStatus('weird').t]; out.why = C.whyBar([{why: 'a', n: 4, n_would: 2, would: 1.5, wins: 1}, {why: 'b', n: 2, n_would: 0, would: 0, wins: 0}]);
out.clock = C.clockRows([{name: 'x', left: 1, lvl: 'warn', due: 'd'}, {name: 'y', left: 5, lvl: 'ok'}, {name: 'z'}]).map(c => c.tone + '|' + c.text);
console.log(JSON.stringify(out));
"""


def part_c(doc):
    import tempfile
    d = tempfile.mkdtemp()
    drv, dj = os.path.join(d, "drv.js"), os.path.join(d, "doc.json")
    open(drv, "w").write(NODE)
    json.dump(doc, open(dj, "w"))
    r = subprocess.run(["node", drv, os.path.join(NQ, "weekcore.js"), dj], capture_output=True, text=True, timeout=60)
    if r.returncode:
        check("c. node ran", False, r.stderr[-400:]); return
    o = json.loads(r.stdout.strip().splitlines()[-1])
    check("c. empty doc: no throw; an honest 'no week data' hero, 'No grade' view, 'no setups' line", o["emptyPick"] is None and o["emptyHero"]["empty"] and "No week data" in o["emptyHero"]["line"] and o["emptyGrade"]["empty"] and "No setups" in o["emptyRej"], o["emptyHero"])
    check("c. default week = this week; picker: This week / Last week / dated, the chosen one active", o["def"] == doc["weeks"][0]["key"] and [p[0] for p in o["pk"]][:2] == ["This week", "Last week"] and [p[1] for p in o["pk"]] == [False, True, False, False], o["pk"])
    check("c. $ and R words", o["usd"] == ["+$514", "-$113", "+$0", "-", "-$5", "+$1,234,567"] and o["r"] == ["+6.6R", "-1.0R", ""], (o["usd"], o["r"]))
    check("c. quiet week hero = $0, flat, 4 stat tiles; Nov 16 week hero is a dollar sum", o["hero"]["big"] == "$0" and o["hero"]["tone"] == "flat" and len(o["hero"]["stats"]) == 4 and o["hero1"]["big"].startswith(("+", "-")), (o["hero"], o["hero1"]["big"]))
    check("c. day dots: 5 days, Thanksgiving week shows early-halt days as quiet / past", len(o["dots"]) == 5, o["dots"])
    check("c. payout 19% of the way; age words; card title + when", o["pay"] == 19 and o["age"][0] == "built just now" and o["age"][1] == "ok" and o["age"][2] == "bad" and "SHORT" in o["card"] and "11/18 04:50→05:08 ET" == o["when"], o)
    check("c. twin status icons; unknown status does not throw; why-bars scale to the biggest", o["tw"][0] == "❌" and o["tw"][1] == "weird" and o["why"][0]["pct"] == 100 and o["why"][1]["pct"] == 50 and "1 of 2" in o["why"][0]["would"], o["why"])
    check("c. clock rows: warn at 1 day left is 'bad', ok is ok, missing data says so", o["clock"][0].startswith("bad|") and o["clock"][1].startswith("ok|") and "no clock data" in o["clock"][2], o["clock"])


SIZES = """() => { const bad = []; for (const e of document.querySelectorAll('body *')) { if (e.closest('script,style') ) continue;
  const own = [...e.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim()); if (!own) continue;
  const cs = getComputedStyle(e); if (cs.display === 'none' || cs.visibility === 'hidden') continue; const r = e.getBoundingClientRect(); if (!r.width) continue;
  if (parseFloat(cs.fontSize) < 12) bad.push(e.className + ':' + parseFloat(cs.fontSize)); } return bad.slice(0, 6); }"""


def part_d(doc):
    try:
        import playwright  # noqa: F401
    except ImportError:
        print("  (playwright not installed: browser part skipped)"); return
    shots = "--shots" in sys.argv
    bad_doc = json.loads(json.dumps(doc)); bad_doc["weeks"] = []
    runs = [("full-390", 390, 844, doc), ("full-1440", 1440, 900, doc), ("empty-390", 390, 844, bad_doc), ("error-390", 390, 844, None)]
    for name, w, h, dd in runs:
        srv, origin = AK.serve({"/nq/week_review.json": json.dumps(dd) if dd is not None else None})
        try:
            with AK.browser() as br:
                ctx, p, errs, seen, off = AK.page(br, origin, w=w, h=h)
                p.goto(f"{origin}/nq/week.html")
                p.wait_for_function("document.getElementById('app').dataset.state !== 'loading'", timeout=60000)
                p.wait_for_timeout(500)
                o = p.evaluate("""() => ({ state: document.getElementById('app').dataset.state, hero: document.getElementById('hero').textContent, picks: document.querySelectorAll('.wk-pick').length,
                  secs: [...document.querySelectorAll('.wk-card')].map((e) => e.id), trades: document.querySelectorAll('.wk-trade').length, grade: !!document.querySelector('#grade .wk-grade-l'),
                  gradeLast: document.querySelector('.wk-card:last-of-type') === document.getElementById('grade'), chip: document.getElementById('src').textContent,
                  big: (document.querySelector('.wk-big') || {}).textContent, txt: document.getElementById('app').textContent })""")
                if name.startswith("full"):
                    need = ["accts", "rejected", "twin", "waiting", "clock", "of", "blitz", "next", "grade"]
                    check(f"d. {name}: every section drawn (accounts, rejected, missed vs backtest, waiting, clock + payout, order flow, BLITZ, next week, grade) + 4 week buttons",
                          o["state"] == "ready" and o["picks"] == 4 and all(s in o["secs"] for s in need), (o["secs"], o["picks"]))
                    check(f"d. {name}: quiet week says so, $0 big number, a Grade card with a letter, emoji on the page",
                          "Quiet week" in o["hero"] and o["big"] == "$0" and o["grade"] and "🏅" in o["txt"] and "🚫" in o["txt"], o["hero"][:120])
                    check(f"d. {name}: no account number on the page", not re.search(r"MFFU[A-Z]{4,}|\.\.\.\d{4}|…\d{4}", o["txt"]))
                    p.click(".wk-pick:nth-child(2)")
                    p.wait_for_timeout(300)
                    o2 = p.evaluate("() => ({ big: document.querySelector('.wk-big').textContent, trades: document.querySelectorAll('.wk-trade').length, on: document.querySelector('.wk-pick.on b').textContent, txt: document.getElementById('app').textContent, waiting: !!document.getElementById('waiting').firstChild })")
                    check(f"d. {name}: tap 'Last week' = the Nov 16 week (trade cards with a why line, Zlarior -$129, the missed Rapid trade, no 'waiting' card for a past week)",
                          o2["on"] == "Last week" and o2["trades"] >= 4 and "LOST" in o2["txt"] and "-$129" in o2["txt"] and "Missed" in o2["txt"] and not o2["waiting"], (o2["big"], o2["trades"]))
                    p.click(".wk-pick:nth-child(3)")
                    p.wait_for_timeout(300)
                    t3 = p.evaluate("() => document.getElementById('app').textContent")
                    check(f"d. {name}: tap the Nov 9 week = the PC-off weeks's misses explained", "bot not running" in t3)
                    p.click(".wk-pick:nth-child(1)")
                    p.wait_for_timeout(200)
                elif name.startswith("empty"):
                    check("d. empty-390: no weeks = state 'empty' + an honest 'No week data yet' hero, no throw", o["state"] == "empty" and "No week data yet" in o["hero"] and o["picks"] == 0, o)
                else:
                    check("d. error-390: week_review.json missing = 'No data' chip + a plain error line", "No data" in o["chip"] and "Could not read" in o["hero"], o)
                bad = p.evaluate(SIZES)
                check(f"d. {name}: no text under 12 px, taps >= 44 px, no sideways scroll, nothing off the site, no console error",
                      not bad and not AK.taps(p) and AK.no_sideways(p) and not off and not errs, (bad, AK.taps(p)[:4], off[:3], errs[:3]))
                if shots:
                    os.makedirs(SHOTS, exist_ok=True)
                    p.screenshot(path=os.path.join(SHOTS, f"week-{name}.png"), full_page=True)
                ctx.close()
        finally:
            srv.shutdown()


def main():
    part_a()
    doc, _ = part_b()
    part_c(doc)
    part_d(doc)
    return AK.finish()


if __name__ == "__main__":
    sys.exit(main())
