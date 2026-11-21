"""ZEUS this week (tools/weekly_review.py -> tools/web_public/business/week.json, page business/week.html + week.js, 2026-11-18):
the week window, per-account $ / trades / win % / best day vs the consistency rule / to pass or payout, Zlarior + ATLAS vs the
2026 expectation (on track / behind / ahead), the code changes, next week's news days + early closes + decisions, the honest pace
line, graceful "what is missing" with no live data, the board event "Weekly review ready", the Friday ops hook, the generated-file
list (no blocked auto-update), textContent only, no private details. Offline. --browser adds one 390 px phone check (run it under
flock -w 2400 /tmp/olympus_browser.lock).

  python -X utf8 -m tests.test_weekly_review [--browser]
"""
from __future__ import annotations

import datetime as dt
import functools
import glob
import http.server
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
WEB = os.path.join(ROOT, "tools", "web_public")
BIZ = os.path.join(WEB, "business")
ET = ZoneInfo("America/New_York")
RES = []

from tools import weekly_review as W  # noqa: E402
from engine import board_events as B  # noqa: E402


def check(name, cond, detail=""):
    RES.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({str(detail)[:300]})" if detail and not cond else ""))


def read(*p):
    with open(os.path.join(*p), encoding="utf-8") as fh:
        return fh.read()


def ts(day, hm="10:00"):
    h, m = map(int, hm.split(":"))
    return int(dt.datetime.combine(dt.date.fromisoformat(day), dt.time(h, m), ET).timestamp())


FRI = ts("2026-11-20", "16:20")


def fake_board(now=FRI):
    return {"pc": {"t": now - 300, "via": "ntfy"}, "events": [], "accounts": [
        {"key": "zlarior", "name": "Zlarior", "plan": "MFFU Builder 50K", "stage": "eval", "chip": "eval", "balance": 49900.0,
         "room": 1700.0, "to_pass": 3100.0, "src": "PC live", "src_t": now - 300, "age_s": 300},
        {"key": "atlas", "name": "ATLAS", "plan": "MFFU Builder 25K (funded)", "stage": "funded", "chip": "funded", "balance": 25600.0,
         "room": None, "to_pass": None, "src": "PC live", "src_t": now - 300, "age_s": 300},
        {"key": "fresh25", "name": "Zlarior 25K #2", "plan": "MFFU Builder 25K", "stage": "eval", "chip": "eval", "balance": 24800.0,
         "room": 800.0, "to_pass": 1700.0, "src": "PC live", "src_t": now - 300, "age_s": 300},
        {"key": "rapid1", "name": "Rapid EOD 25K (next)", "plan": "MFFU Rapid EOD 25K", "stage": "eval", "balance": None, "src": "PLAN"}]}


def ex(day, pnl, acct="zlarior", bot="zlarior", hm="10:30", mode="live", **kw):
    return {"side": "exit", "t": ts(day, hm), "entry_t": ts(day, hm) - 1800, "pnl": pnl, "acct": acct, "bot": bot, "mode": mode, **kw}


ROWS = [ex("2026-11-16", 800.0), ex("2026-11-18", -200.0), ex("2026-11-19", 300.0),
        ex("2026-11-16", 800.0),                                         # the same exit seen twice (state file + archive): once
        ex("2026-11-17", 999.0, mode="paper"),                           # paper: never counted
        ex("2026-11-17", 0.0, reason="NO TRADE"),
        ex("2026-11-18", 500.0, void="not placed"),                      # a voided exit: never counted
        ex("2026-11-13", 400.0),                                         # last week
        ex("2026-11-17", 400.0, acct="atlas", bot="atlas"), ex("2026-11-19", 200.0, acct="atlas", bot="atlas"),
        ex("2026-11-18", -200.0, acct="b25k_2", bot="zlarior", hm="11:00")]


def part_a():
    w = W.week_of(FRI)
    check("a. the week: Mon-Fri of the ET week, complete on Friday after 16:00; next week = the Mon-Fri after",
          w["from"] == "2026-11-16" and w["to"] == "2026-11-20" and w["complete"] and w["next_from"] == "2026-11-23"
          and w["next_to"] == "2026-11-27", w)
    sat = W.week_of(ts("2026-11-21", "12:00"))
    wed = W.week_of(ts("2026-11-18", "12:00"))
    check("a. Saturday reviews the week that just ended; mid-week is 'so far' (not complete)",
          sat["from"] == "2026-11-16" and sat["complete"] and not wed["complete"] and wed["sessions_done"] == 3, (sat, wed))
    check("a. Friday before 16:00 ET is not complete yet", not W.week_of(ts("2026-11-20", "15:00"))["complete"])

    plan = B.plan()
    tr = W.trades(ROWS, w, plan.get("accounts") or [])
    z = [x for x in tr if x["acct"] == "zlarior"]
    check("a. trades: live exits of this week only, duplicates once, paper / NO TRADE / void / last week left out",
          [x["pnl"] for x in z] == [800.0, -200.0, 300.0], tr)
    check("a. trades: a PC id (b25k_2) lands on its plan account (Zlarior 25K #2), never by plan size",
          any(x["acct"] == "fresh25" and x["pnl"] == -200.0 for x in tr) and all(x["acct"] != "b25k_2" for x in tr), tr)

    doc = W.build(now=FRI, board=fake_board(), rows=list(ROWS))
    acc = {a["key"]: a for a in doc["accounts"]}
    za = acc["zlarior"]
    check("a. account: $ this week, start = now - week $, trades, win %, room, $ to pass",
          za["usd_week"] == 900.0 and za["start"] == 49000.0 and za["end"] == 49900.0 and za["trades"] == 3 and za["win_pct"] == 67
          and za["room"] == 1700.0 and "$3,100 to pass" in za["status_line"], za)
    check("a. account: best day vs the rule (Builder eval: no best-day rule)",
          "11-16" in za["consistency"]["line"] and "no rule in the eval" in za["consistency"]["line"], za["consistency"])
    at = acc["atlas"]
    check("a. funded account: best day vs the 50% cycle rule + the payout coach's line",
          "50%" in at["consistency"]["rule"] and "% of the cycle profit" in at["consistency"]["line"] and at["status_line"].startswith("Payout:"),
          (at["consistency"], at["status_line"]))
    check("a. a planned account not bought yet (no balance) is left out", "rapid1" not in acc, list(acc))
    st = {s["name"]: s for s in doc["strategies"]}
    check("a. strategies: Zlarior and ATLAS, each with trades vs the 2-4 target, PF, $ and the 2026 numbers",
          set(st) == {"Zlarior", "ATLAS"} and st["Zlarior"]["trades"] == 4 and st["Zlarior"]["target"] == "2-4 a week"
          and st["Zlarior"]["pf"] == 2.75 and st["ATLAS"]["pf"] == "no loss"
          and all(isinstance(s["exp_tpw"], list) and isinstance(s["exp_pf"], list) for s in st.values()), st)
    check("a. verdicts: on track / behind / ahead only", all(s["verdict"] in ("on track", "behind", "ahead") for s in st.values()), st)
    bad = W.build(now=FRI, board=fake_board(), rows=[ex("2026-11-17", -300.0)])
    sb = {s["name"]: s for s in bad["strategies"]}
    check("a. behind: a losing week and fewer than 2 trades say so in plain words",
          sb["Zlarior"]["verdict"] == "behind" and "-$300" in sb["Zlarior"]["why"] and "target 2-4" in sb["Zlarior"]["why"], sb["Zlarior"])
    big = W.build(now=FRI, board=fake_board(), rows=[ex("2026-11-17", 1500.0, acct="atlas", bot="atlas"),
                                                     ex("2026-11-18", 600.0, acct="atlas", bot="atlas")])
    check("a. ahead: far above the expected $ a week", {s["name"]: s for s in big["strategies"]}["ATLAS"]["verdict"] == "ahead",
          big["strategies"])
    p = doc["pace"]["line"]
    check("a. one honest pace line: $ a month, 'estimate', one week is noise",
          p.startswith("On pace for $") and "a month" in p and "estimate" in p and "noise" in p and doc["pace"]["usd_month"] > 0, p)
    nx = doc["next"]
    check("a. next week (Nov 23-27): the Thanksgiving early closes from engine/cme_calendar, news rows from events.csv",
          [h["date"] for h in nx["holidays"]] == ["2026-11-26", "2026-11-27"] and all("Early close" in h["what"] for h in nx["holidays"])
          and isinstance(nx["news"], list), nx)
    check("a. decisions = accounts.json decisions first (goals.json added, no repeats), max 6",
          nx["decisions"][:len(plan.get("decisions") or [])] == [W._clean(x, 140) for x in (plan.get("decisions") or [])][:6]
          and len(nx["decisions"]) <= 6
          and len(set(nx["decisions"])) == len(nx["decisions"]), nx["decisions"])
    ch = doc["changes"]
    check("a. what changed in the code: git one-liners, max 8, no merge commits",
          isinstance(ch["items"], list) and len(ch["items"]) <= 8 and not any(i.lower().startswith("merge") for i in ch["items"]), ch)

    # graceful: nothing live
    empty = W.build(now=FRI, board={"accounts": [], "events": [], "pc": {}}, rows=[])
    m = " ".join(empty["missing"])
    check("a. no live data: says what is missing (PC numbers, trade list), verdicts 'unknown', pace 'unknown'",
          "PC live numbers" in m and "trade list" in m and all(s["verdict"] == "unknown" for s in empty["strategies"])
          and empty["pace"]["usd_month"] is None and "unknown" in empty["pace"]["line"], (empty["missing"], empty["pace"]))
    stale = W.build(now=FRI, board={**fake_board(), "pc": {"t": FRI - 7200}}, rows=list(ROWS))
    check("a. a stale PC is named with its last report time", any("last report" in x for x in stale["missing"]), stale["missing"])
    plan_only = fake_board()
    plan_only["accounts"][0].update(src="PLAN (owner, Nov 17)", age_s=None)
    po = W.build(now=FRI, board=plan_only, rows=[])
    check("a. plan-only balance named as missing; $ this week unknown rather than guessed",
          any(x.startswith("Zlarior: no live PC balance") for x in po["missing"]) and po["accounts"][0]["usd_week"] is None, po["missing"])

    # ledgers on disk (PC) and the data pipe's day files (cloud)
    with tempfile.TemporaryDirectory() as tmp:
        os.makedirs(os.path.join(tmp, "data"))
        with open(os.path.join(tmp, "data", "live_state.json"), "w") as fh:
            json.dump({"adapter": "ninjatrader", "nt_account": "MFFU-X", "ledger": [
                {"side": "exit", "t": ts("2026-11-17", "11:00"), "pnl": 250.0, "entry_t": ts("2026-11-17", "10:00")}]}, fh)
        rows = W.pc_rows(tmp)
        check("a. PC ledger: data/live_state.json rows tagged main / zlarior / live", rows and rows[0]["acct"] == "zlarior"
              and rows[0]["mode"] == "live", rows)
        import gzip
        d = os.path.join(tmp, "data", "pc_days", "2026-11-18")
        os.makedirs(d)
        with open(os.path.join(d, "trades.jsonl.gz"), "wb") as fh:
            fh.write(gzip.compress((json.dumps(ex("2026-11-18", 123.0)) + "\n").encode()))
        dr, lab = W.day_rows(["2026-11-18"], tmp, offline=True)
        check("a. data pipe days (data/pc_days) are read", len(dr) == 1 and dr[0]["pnl"] == 123.0 and "data pipe" in lab, (dr, lab))

    # the board event
    check("a. board: weekly_review is a known event kind", "weekly_review" in B.KINDS)
    with tempfile.TemporaryDirectory() as tmp:
        old = {k: os.environ.get(k) for k in ("LE_BOARD_DIR", "LE_BOARD_SHARED")}
        os.environ["LE_BOARD_DIR"] = tmp
        os.environ["LE_BOARD_SHARED"] = os.path.join(tmp, "shared.jsonl")
        try:
            r1 = W.post(doc, from_pc=True)
            r2 = W.post(doc, from_pc=False)
            ev = B.read_jsonl(os.path.join(tmp, "events.jsonl"))
            sh = B.read_jsonl(os.path.join(tmp, "shared.jsonl"))
        finally:
            for k, v in old.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
    check("a. board event 'Weekly review ready': from the bot on the PC (events.jsonl), a Claude note in the cloud (shared.jsonl)",
          r1 and r2 and ev and ev[0]["kind"] == "weekly_review" and ev[0]["src"] == "bot" and sh[0]["src"] == "claude"
          and ev[0]["text"].startswith("Weekly review ready") and "$" in ev[0]["text"] and len(ev[0]["text"]) <= 300, (ev, sh))

    # the Friday ops hook
    from engine import ops_checks as O
    s = {}
    check("a. ops: due Friday from 16:15 ET (not 16:00), or Sat/Sun when missed; once per ISO week",
          O.weekly_review_due(s, ts("2026-11-20", "16:20")) and not O.weekly_review_due(s, ts("2026-11-20", "16:00"))
          and not O.weekly_review_due(s, ts("2026-11-19", "17:00")) and O.weekly_review_due(s, ts("2026-11-22", "10:00"))
          and not O.weekly_review_due({"weekly_review_wk": "2026-W47"}, ts("2026-11-20", "16:20")))
    src = read(ROOT, "engine", "ops_checks.py")
    check("a. ops: tick() runs weekly_review.pc_run only on the real scheduled run, inside try",
          re.search(r"if do_backup and real and weekly_review_due\(state, now\):[\s\S]{0,400}weekly_review\.pc_run", src) is not None)
    from engine import generated_files as G
    check("a. week.json is a bot-made file: the PC's rewrite never blocks the auto-update",
          G.is_generated("tools/web_public/business/week.json"))
    check("a. Work week's Friday review links to the page", "'week.html'" in read(BIZ, "schedule.js"))

    # the page
    html, js = read(BIZ, "week.html"), read(BIZ, "week.js")
    heads = ["The pace", "Accounts", "Zlarior and ATLAS vs 2026", "What changed in the code", "Next week"]
    pos = [html.find(">" + h + "<") for h in heads]
    check("a. page: one screen titled ZEUS this week, sections in order", "<title>ZEUS this week</title>" in html
          and ">ZEUS this week<" in html and all(p > 0 for p in pos) and pos == sorted(pos), dict(zip(heads, pos)))
    check("a. page: no innerHTML / outerHTML / insertAdjacentHTML / document.write / eval",
          not re.search(r"innerHTML|outerHTML|insertAdjacentHTML|document\.write|\beval\(|new Function", js))
    check("a. page: phone first (viewport, AGORA theme, business.css, back link, only same-site scripts)",
          'name="viewport"' in html and 'data-theme="agora"' in html and "business.css" in html and 'href="./"' in html
          and not re.search(r'<(script|link)[^>]+(src|href)="https?://', html))
    raw = read(BIZ, "week.json")
    wj = json.loads(raw)
    check("a. week.json in the repo is a built review", wj.get("title") == "ZEUS this week" and isinstance(wj.get("accounts"), list)
          and isinstance(wj.get("strategies"), list) and wj.get("pace", {}).get("line"))
    low = raw.lower()
    check("a. no private details in week.json (emails, account numbers, the owner's handle, a 'kind' key the privacy scan reads)",
          not re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", raw) and "dcondax" not in low and not re.search(r"\b\d{6,}\b",
          re.sub(r'"(built_t|board_pc_t)": \d+', "", raw)) and '"kind"' not in raw)
    try:
        from tools import site_privacy
        check("a. the site privacy check passes week.json", site_privacy.private_file("business/week.json", raw.encode()) is None)
    except ImportError as e:
        check("a. the site privacy check passes week.json", False, e)
    try:
        r = subprocess.run(["node", "--check", os.path.join(BIZ, "week.js")], capture_output=True, text=True, timeout=60)
        check("a. node: week.js parses", r.returncode == 0, r.stderr[-300:])
    except (OSError, subprocess.TimeoutExpired) as e:
        check("a. node: week.js parses", False, e)


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a):
        pass


def part_b():
    from playwright.sync_api import sync_playwright
    doc = W.build(now=FRI, board=fake_board(), rows=list(ROWS))
    body = json.dumps(doc)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=WEB))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    port = srv.server_address[1]
    outside, errs = [], []
    try:
        with sync_playwright() as pw:
            exe = next(iter(sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))), None)
            br = pw.chromium.launch(**({"executable_path": exe} if exe else {}))
            ctx = br.new_context(viewport={"width": 390, "height": 844}, has_touch=True)

            def guard(route):
                u = route.request.url
                if u.split("?")[0].endswith("/business/week.json"):        # the test's own week (fake PC numbers + trades)
                    return route.fulfill(status=200, content_type="application/json", body=body)
                if u.startswith(f"http://127.0.0.1:{port}") or u.startswith(("data:", "blob:")):
                    return route.continue_()
                outside.append(u)
                return route.abort()
            ctx.route("**/*", guard)
            p = ctx.new_page()
            p.on("pageerror", lambda e: errs.append(str(e)))
            p.goto(f"http://127.0.0.1:{port}/business/week.html")
            p.wait_for_function(f"document.querySelectorAll('#accts .acc').length === {len(doc['accounts'])}")
            got = p.evaluate("() => ({acc: document.querySelectorAll('#accts .acc').length, st: document.querySelectorAll('#strats .acc').length,"
                             " pace: document.querySelector('#pace').textContent, hol: document.querySelectorAll('#hol li').length,"
                             " big: document.querySelector('#accts .big').textContent, verdicts: [...document.querySelectorAll('#strats .pill')].map(e => e.textContent)})")
            check("b. phone: accounts with $ this week, both strategies with a verdict, the pace line, next week's early closes",
                  got["acc"] == len(doc["accounts"]) and got["st"] == 2 and got["pace"].startswith("On pace for $") and got["hol"] == 2
                  and "+$900 this week" in got["big"] and all(v in ("on track", "behind", "ahead") for v in got["verdicts"]), got)
            wide = p.evaluate("() => document.documentElement.scrollWidth - document.documentElement.clientWidth")
            check("b. no sideways scroll at 390 px", wide <= 0, wide)
            check("b. no script errors and nothing fetched from outside", not errs and not outside, (errs, outside))
            br.close()
    finally:
        srv.shutdown()


def main():
    part_a()
    if "--browser" in sys.argv:
        part_b()
    ok = all(RES)
    print(f"\n{sum(RES)}/{len(RES)} passed" + ("" if ok else "  FAILURES"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
