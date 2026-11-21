"""ZEUS this week, round 2 (tools/week_more.py + tools/weekly_review.py, day-brief 2026-11-20): trades from the PC's status post,
each bot vs its backtest twin, best / worst trade with one lesson, Kalshi K8, next week day by day (Thanksgiving), the weekend
list ranked by $, no churn beyond `built`, the page draws every new block (textContent only).

    python -X utf8 -m tests.test_week_more
Offline: a fake status post; the twins replay the repo's own bars (Nov 16-19 2026).
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import subprocess
import sys
import tempfile
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
ET = ZoneInfo("America/New_York")
BIZ = os.path.join(ROOT, "tools", "web_public", "business")
RES = []

from tools import week_more as M  # noqa: E402
from tools import weekly_review as W  # noqa: E402


def check(name, cond, detail=""):
    RES.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({str(detail)[:300]})" if detail and not cond else ""))


def ts(day, hm):
    h, m = map(int, hm.split(":"))
    return int(dt.datetime.combine(dt.date.fromisoformat(day), dt.time(h, m), ET).timestamp())


FRI = ts("2026-11-20", "16:20")
# the PC's real post of Nov 20 (the "at" block shape: entry_t, exit_t, dir, qty, entry, stop, target, exit, $, R); the
# third ATLAS row is still open (no exit) and must be left out
LITE = {"t": FRI - 300,
        "at": {"a": [{"id": "mffu50k_eval", "tr": [[1794827760, 1794830400, 1, 1, 27799.5, 27735.25, 28174.0, "STOP", -129.4, -1.01]]},
                     {"id": "atlas", "tr": [[1794995400, 1794996603, -1, 2, 27395.5, 27422.5, 27179.5, "STOP", -112.8, -1.04],
                                            [1795164300, None, -1, 1, 26380.75, 26419.5, 26122.75, None, None, 4.63]]}]},
        "life": {"acc": {"atlas": {"since": 1794965203}, "lit": {"since": 1794965203}}},
        "kalshi_live": {"k8": {"m": "P", "td": [2, 0, -5.08], "l": "WWWLLLL", "wk": [0.0, 13.75], "wr": [7, 43]}}}


def board(now=FRI):
    return {"pc": {"t": now - 300, "via": "ntfy"}, "events": [], "accounts": [
        {"key": "zlarior", "name": "Zlarior", "plan": "MFFU Builder 50K", "stage": "eval", "chip": "eval", "balance": 49192.78,
         "room": 1024.58, "to_pass": 3807.22, "src": "PC live", "src_t": now - 300, "age_s": 300},
        {"key": "atlas", "name": "ATLAS", "plan": "MFFU Builder 25K (funded)", "stage": "funded", "chip": "funded", "balance": 24887.2,
         "room": 887.2, "to_pass": None, "src": "PC live", "src_t": now - 300, "age_s": 300}]}


def main():
    from engine import board_events as B
    plan = B.plan().get("accounts") or []

    # 1. trades from the status post
    fr = M.feed_rows(LITE, plan)
    check("feed: 2 closed trades, the open one left out", len(fr) == 2, fr)
    check("feed: accounts mapped to the plan keys", sorted(r["acct"] for r in fr) == ["atlas", "zlarior"], [r["acct"] for r in fr])
    dup = fr + [dict(fr[0], src="ledger")]
    wk = W.week_of(FRI)
    tr = W.trades(dup, wk, plan)
    check("feed + ledger copy of one entry = one trade", len(tr) == 2, tr)
    check("trade facts carried (entry, stop, target, R, exit)", all(k in tr[0] for k in ("entry_t", "stop", "target", "r", "exit")), tr[0])

    # 2. the full build with the post, offline otherwise
    doc = W.build(now=FRI, board=board(), rows=[], lite=LITE)
    z = next(a for a in doc["accounts"] if a["key"] == "zlarior")
    check("account: $ this week, won / lost, R", z["usd_week"] == -129.4 and z["wins"] == 0 and z["losses"] == 1 and z["r_week"] == -1.01, z)
    check("account: room and to-pass at the start of the week", z["room_start"] == round(1024.58 + 129.4, 2)
          and z["to_pass_start"] == round(3807.22 - 129.4, 2), z)
    check("sources name the status post", "PC status post" in doc["sources"]["trades"], doc["sources"])

    # 3. twins on the repo's bars
    T = doc["twins"]
    names = [b["name"] for b in T.get("bots", [])]
    check("twins: Zlarior and ATLAS", names == ["Zlarior", "ATLAS"], T)
    zt = T["bots"][0]
    check("Zlarior twin: Nov 16 06:16 long matched, -1.01R both", any(r["day"] == "2026-11-16" and r["status"] == "matched"
          and r["twin_r"] == -1.01 and r["live_r"] == -1.01 for r in zt["rows"]), zt["rows"])
    at = T["bots"][1]
    st = {(r["day"], r["who"]): r["status"] for r in at["rows"]}
    check("ATLAS twin: Nov 18 MACD matched", st.get(("2026-11-18", "MACD")) == "matched", st)
    check("ATLAS twin: Nov 17 trades before the funded account = not live yet (not 'missed')",
          st.get(("2026-11-17", "EMA")) == "not live yet", st)
    check("twin compare: a live trade with no twin = extra", M.compare("x", [], [{"day": "2026-11-16", "entry_t": 1794827760, "dir": 1,
                                                                                   "r": -1.0, "pnl": -10}])["n"]["extra"] == 1)

    # 4. best / worst + lesson
    w = doc["worst"]
    check("worst = Zlarior -$129 with a cause code and a lesson", w and w["usd"] == -129.4 and w["cause"] in M.CAUSES_ALL and w["lesson"], w)
    check("no winner -> best is null", doc["best"] is None)
    check("cause order: news first, wick, turned, never; winners target / managed",
          M.cause({"pnl": -1, "exit": "STOP"}, {"post_tgt": True}, "CPI") == "news"
          and M.cause({"pnl": -1, "exit": "STOP"}, {"post_tgt": True}, None) == "wick"
          and M.cause({"pnl": -1, "exit": "STOP"}, {"mfe_r": 0.6}, None) == "turned"
          and M.cause({"pnl": -1, "exit": "STOP"}, {"mfe_r": 0.2}, None) == "never"
          and M.cause({"pnl": 5, "exit": "TARGET"}, {}, None) == "target" and M.cause({"pnl": 5, "exit": "BE"}, {}, None) == "managed")

    # 5. Kalshi, calendar, weekend
    k = doc["kalshi"]
    check("K8 week from the card when no ledger is here", k and k["mode"] == "paper" and "$13.75" in k["line"], k)
    cal = doc["calendar"]
    check("next week = Mon Nov 23 - Fri Nov 27", [d["date"] for d in cal] == ["2026-11-23", "2026-11-24", "2026-11-25", "2026-11-26", "2026-11-27"])
    th = cal[3]
    check("Thanksgiving: early close 13:00 (NQ trades; the bots' own calendar), named", th["status"] == "early" and "13:00" in th["text"]
          and "Thanksgiving" in th["text"], th)
    check("Fri Nov 27: early close 13:15", cal[4]["status"] == "early" and "13:15" in cal[4]["text"], cal[4])
    we = doc["weekend"]
    us = [x["usd_month"] for x in we]
    n_open = sum(1 for c in json.load(open(os.path.join(ROOT, "tools", "web_public", "business", "decisions.json"), encoding="utf-8"))["items"]
                 if c.get("status") == "open")      # 2026-11-20 lead: 0 open is real once the owner answered every card
    check("weekend: open cards only, biggest $ first, max 5", len(we) <= 5 and (len(we) > 0 or n_open == 0) and us == sorted(us, reverse=True)
          and all(x.get("status", "open") == "open" for x in we), we)
    with tempfile.TemporaryDirectory() as d:
        os.makedirs(os.path.join(d, "x"))
        old = M.BIZ
        try:
            M.BIZ = d
            with open(os.path.join(d, "decisions.json"), "w") as fh:
                json.dump({"items": [{"id": "a", "question": "A?", "status": "open", "impact_usd": 10},
                                     {"id": "b", "question": "B?", "status": "open", "impact_usd": 50},
                                     {"id": "c", "question": "C?", "status": "done", "impact_usd": 99}]}, fh)
            with open(os.path.join(d, "fleet_plan.json"), "w") as fh:
                json.dump({"cards": [{"id": "a", "usd_month": 300}]}, fh)
            r = M.weekend()
            check("weekend: fleet_plan.json $ wins over the card's", [x["id"] for x in r] == ["a", "b"] and r[0]["src"] == "fleet_plan.json", r)
        finally:
            M.BIZ = old

    # 6. week window + no churn
    check("Friday 06:35 ET: 4 sessions done (Friday not over)", W.week_of(ts("2026-11-20", "6:35"))["sessions_done"] == 4)
    check("one built-at only (no built_t / ago text)", "built_t" not in doc and "ago" not in doc["pc"]
          and all("ago" not in str(a.get("src")) for a in doc["accounts"]), doc["pc"])
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "week.json")
        W.write(doc, p)
        a = open(p).read()
        W.write({**doc, "built": "2099-01-01 00:00 ET"}, p)
        check("no rewrite when only `built` changes", open(p).read() == a)
    doc2 = W.build(now=FRI, board=board(), rows=[], lite=LITE)
    check("same inputs = same review (except built)", {**doc, "built": 0} == {**doc2, "built": 0})
    check("week.json stays small (< 20 KB)", len(json.dumps(doc)) < 20000, len(json.dumps(doc)))

    # 7. the page
    html = open(os.path.join(BIZ, "week.html"), encoding="utf-8").read()
    js = open(os.path.join(BIZ, "week.js"), encoding="utf-8").read()
    for i in ("weekend", "bw", "twins", "k8", "cal"):
        check(f"page has #{i}", f'id="{i}"' in html)
    check("page draws the new blocks", all(x in js for x in ("drawMore", "D.twins", "D.best", "D.kalshi", "D.calendar", "D.weekend")))
    check("page: text only (no innerHTML / eval)", not re.search(r"innerHTML|outerHTML|insertAdjacentHTML|document\.write|\beval\(", js))
    check("page cache-busts week.js (v=4)", 'week.js?v=9' in html)
    r = subprocess.run(["node", "--check", os.path.join(BIZ, "week.js")], capture_output=True, text=True)
    check("node: week.js parses", r.returncode == 0, r.stderr[-200:])

    print(f"\n{sum(RES)}/{len(RES)} passed")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
