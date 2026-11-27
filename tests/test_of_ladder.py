"""Order flow lane A gate ladder (tools/of_ladder.py, research/evalplan/PLAN.md section 3). Offline: fake forward rows, temp files.

  a. in-between: 12 forward trades, 6 won -> step 0 watching, no card, Brain row 'needs 8 more'
  b. pass: first 30 forward trades +0.50R, PF >= 1.3, DD <= 6R (the pre-registered lane A gate) -> step 1 waiting (no Sim101 rows), card draft written for step 1
  c. stops: first 10 won 2 -> stopped; sum <= -6R -> stopped; first 30 at 0R / DD 7R / taken <= skipped / a half < 0 -> stopped; a stop is sticky on the next run
  d. E5 fills: the gate judges the worse of the original fill and the E5 fill (a +2R that is -0.1R at E5 is a loss)
  e. Sim101: 10 trades within 2 ticks -> ask_owner (step 2); a hedge conflict -> stopped
  f. sources: PC shipped paper days win over the cloud replay for the same day; pre-11-27 and untaken rows ignored
    python -X utf8 -m tests.test_of_ladder
"""
from __future__ import annotations

import gzip
import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import of_ladder as L  # noqa: E402

FAILS = []


def check(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  {info}"))
    if not ok:
        FAILS.append(name)


def rows(pattern, start=1):
    """pattern 'WLW..' -> forward taken rows from 2026-12-01 (W = +2R $+100, L = -1R $-50)."""
    out = []
    for i, c in enumerate(pattern):
        w = c == "W"
        out.append({"id": f"A|d{i}", "day": f"2026-12-{(i % 28) + start:02d}" if i < 28 else f"2027-01-{i - 27:02d}", "level": "onh",
                    "d": -1, "taken": True, "R": 2.0 if w else -1.0, "usd_1": 100.0 if w else -50.0})
    return out


def main():
    # a. in-between
    r = rows("WLWLWLWLWLWL")
    d = L.evaluate(r)
    check("a in-between: step 0 watching", d["step"] == 0 and d["status"] == "watching" and not d["card_due"], d["status"])
    t = L.trial_row(d)
    check("a Brain row needs 18 more", t["n"] == 12 and "18 more" in t["word"] and t["status"] == "watching", t["word"])
    # b. pass gate 0 (30 trades +0.50R, PF $ ~2, DD 1R, halves > 0)
    r = rows("WLWLWLWLWLWLWLWLWLWLWLWLWLWLWL")
    d = L.evaluate(r)
    check("b pass: step 1 waiting for Sim101", d["step"] == 1 and d["status"] == "waiting", (d["step"], d["status"]))
    check("b gate 0 passed -> card due (Sim101 build)", d["card_due"] and d["passed_gate"] == 0)
    c = L.card(d)
    check("b card: step 1, recommend yes, no money", c["id"] == "of-ladder-step1" and c["recommend"] == "yes" and "No real money" in c["applies"], c)
    with tempfile.TemporaryDirectory() as tmp:
        # run() with the files pointed at the temp dir
        old = (L.PC_DAYS, L.VERDICT, L.SIM_ROWS)
        L.PC_DAYS, L.SIM_ROWS = os.path.join(tmp, "pc"), os.path.join(tmp, "sim.json")
        L.VERDICT = os.path.join(tmp, "v.json")
        json.dump({"rows": r}, open(L.VERDICT, "w"))
        out, card = os.path.join(tmp, "ladder.json"), os.path.join(tmp, "card.json")
        dd = L.run(out=out, card_path=card, say=lambda *_: None)
        check("b run: ladder.json written", os.path.exists(out) and dd["stats"]["n"] == 30)
        # Sim101 rows: 10 clean -> ask owner + card
        json.dump([{"fill_gap_ticks": 1.0, "R": 2.0, "usd_1": 100.0, "taken": True, "day": "2027-01-05"} for _ in range(10)], open(L.SIM_ROWS, "w"))
        dd = L.run(out=out, card_path=card, say=lambda *_: None)
        check("e Sim101 clean -> ask_owner step 2", dd["step"] == 2 and dd["status"] == "ask_owner", (dd["step"], dd["status"]))
        c = json.load(open(card)) if os.path.exists(card) else {}
        check("e card draft for step 2 (one eval), recommend later", c.get("id") == "of-ladder-step2" and c.get("recommend") == "later", c.get("id"))
        # hedge conflict -> stopped, card removed, sticky
        json.dump([{"fill_gap_ticks": 1.0, "hedge_conflict": True}], open(L.SIM_ROWS, "w"))
        dd = L.run(out=out, card_path=card, say=lambda *_: None)
        check("e hedge conflict -> stopped", dd["status"] == "stopped" and not os.path.exists(card), dd["status"])
        os.remove(L.SIM_ROWS)
        dd = L.run(out=out, card_path=card, say=lambda *_: None)
        check("c stop is sticky across runs", dd["status"] == "stopped" and "stopped earlier" in dd["why"], dd["why"])
        # f. sources: a PC day replaces the replay for that day; old / untaken rows ignored
        os.remove(out)
        pcd = os.path.join(L.PC_DAYS, "2026-12-01", "of")
        os.makedirs(pcd)
        with gzip.open(os.path.join(pcd, "NQ_paper.json.gz"), "wt") as fh:
            json.dump({"rows": [{"id": "pc1", "day": "2026-12-01", "taken": True, "R": -1.0, "usd_1": -40.0}]}, fh)
        json.dump({"rows": r[:3] + [{"id": "old", "day": "2026-11-20", "taken": True, "R": 2.0, "usd_1": 1},
                                    {"id": "skip", "day": "2026-12-05", "taken": False, "R": 2.0, "usd_1": 1}]}, open(L.VERDICT, "w"))
        fr, src = L.forward_rows(L.PC_DAYS, L.VERDICT)
        check("f PC day wins over replay, old/untaken ignored", [x["id"] for x in fr] == ["pc1", "A|d1", "A|d2"] and len(src) == 2,
              ([x["id"] for x in fr], src))
        L.PC_DAYS, L.VERDICT, L.SIM_ROWS = old
    # c. stops
    d = L.evaluate(rows("LLWLLLLWLL"))
    check("c first 10 won 2 -> stopped", d["status"] == "stopped", d["why"])
    d = L.evaluate(rows("WLLLLLLLLL"[:9]))
    check("c 9 trades 1 won (sum -6R) -> stopped", d["status"] == "stopped" and "sum" in d["why"], d["why"])
    d = L.evaluate(rows("WLL" * 10))
    check("c first 30 at 0R avg -> stopped (gate 0 missed)", d["status"] == "stopped" and "missed" in d["why"] and "mean" in d["why"], d["why"])
    d = L.evaluate(rows("WWWWWWWWLLLLLLLWWWWWWWWWWWWWWW"))
    check("c drawdown 7R -> stopped early", d["status"] == "stopped" and "drawdown" in d["why"], d["why"])
    d = L.evaluate(rows("WL" * 15), skipped=[{"R": 0.9}])
    check("c taken not > skipped -> gate 0 missed", d["status"] == "stopped" and "taken > skipped" in d["why"], d["why"])
    d = L.evaluate(rows("WL" * 15), skipped=[{"R": -0.3}])
    check("c taken > skipped -> passes", d["passed_gate"] == 0, d["why"])
    d = L.evaluate(rows("W" * 15 + "WLLL" * 3 + "WLL"))
    check("c newer half below 0R -> gate 0 missed", d["status"] == "stopped" and "halves" in d["why"], d["why"])
    # d. E5 fills
    r = rows("WLWLWLWLWLWLWLWLWLWLWLWLWLWLWL")
    r[0]["R_e5"] = -0.1
    d = L.evaluate(r)
    check("d E5 worse fill turns a win into a loss -> 14 won, still passes", d["stats"]["won"] == 14 and d["step"] == 1, d["stats"])
    r[2]["fill"], r[2]["fill_e5"], r[2]["stop"] = 100.0, 112.0, 110.0      # short (d=-1): E5 12 pts higher on a 10-pt stop
    check("d R_e5 from fill_e5 (short: higher fill = better)", abs(L.r_e5(r[2]) - (2.0 + 1.2)) < 1e-9, L.r_e5(r[2]))
    d = L.evaluate(r)
    check("d judged = the worse of the two", d["stats"]["won"] == 14 and d["stats"]["e5_n"] == 2, d["stats"])
    # g. night-of-monfix: gate 0 judges the FIRST trade of each day; later ones are reported, capped after 15 if mean R < 0
    base = rows("WL" * 15)
    for x in base:
        x["t_sig"] = 1000

    def later(pat, n):
        out = []
        for i in range(n):
            w = pat[i % len(pat)] == "W"
            out.append({"id": f"A|late{i}", "day": base[i]["day"], "level": "orh", "d": 1, "taken": True, "t_sig": 5000,
                        "R": 2.0 if w else -1.0, "usd_1": 100.0 if w else -50.0})
        return out
    d = L.evaluate(later("L", 20) + base)
    check("g first-of-day judged: 30 first trades pass gate 0 despite 20 losing later ones",
          d["passed_gate"] == 0 and d["stats"]["n"] == 30 and d["stats_later"]["n"] == 20 and d["stats_all"]["n"] == 50, d["why"])
    check("g 20 later trades at -1R -> 'cap the lane at 1 trade a day'", d["cap_one_a_day"] and L.CAP_TEXT in d["why"] and L.CAP_TEXT in d["line"], d["line"])
    d = L.evaluate(base + later("L", 14))
    check("g 14 later trades: too few to judge, no cap", not d["cap_one_a_day"] and L.CAP_TEXT not in d["why"] and "Later-in-the-day trades" in d["line"], d["line"])
    d = L.evaluate(base + later("WLL", 15))
    check("g 15 later trades at mean 0R: no cap", not d["cap_one_a_day"], d["stats_later"])
    d = L.evaluate(base + later("LLLLLLLLLLLLLLW", 15))
    check("g 15 later trades mean < 0: cap", d["cap_one_a_day"], d["stats_later"])
    lr = later("WLL", 15)                              # red team #35: +R but -$ (tight-stop winners, wide-stop losers)
    for x in lr:
        x["usd_1"] = 20.0 if x["R"] > 0 else -60.0
    d = L.evaluate(base + lr)
    check("g rt 15 later trades mean R >= 0 but $ < 0: cap (in $ too)", d["cap_one_a_day"] and "-$" in d["why"], d["why"])
    fd = L.split_first([dict(base[0], id="z", t_sig=9000), dict(base[0], id="y", t_sig=10)])
    check("g split_first orders by signal time within a day", [x["id"] for x in fd[0]] == ["y"] and [x["id"] for x in fd[1]] == ["z"])
    print(f"\nof_ladder: {'ALL PASS' if not FAILS else str(len(FAILS)) + ' FAIL'}")
    return 1 if FAILS else 0


if __name__ == "__main__":
    sys.exit(main())
