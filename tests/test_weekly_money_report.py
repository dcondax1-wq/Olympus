"""SUNDAY MONEY REPORT (tools/weekly_money_report.py, 2026-11-13): the scoreboard as a plain table + 3 lines, a file in docs/reports/
and one push on the owner's PRIVATE ntfy topic, once a week on Sunday from 17:00 ET (hooked into tools/pc_report.py's 15-minute task).
Fake network, temp folders: never the real ntfy, never the real docs/reports.
    python -X utf8 -m tests.test_weekly_money_report
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import money_scoreboard as MS  # noqa: E402
from tools import weekly_money_report as W  # noqa: E402

RES = []
HOME_REAL = os.path.join(ROOT, "tests", "fixtures", "argus", "home_real.json")


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:600]}"), flush=True)


def utc(y, mo, d, h, mi=0):
    return dt.datetime(y, mo, d, h, mi, tzinfo=dt.timezone.utc).timestamp()


SUN_1659 = utc(2026, 11, 15, 21, 59)     # Sunday 16:59 EST (UTC-5)
SUN_1700 = utc(2026, 11, 15, 22, 0)      # Sunday 17:00 EST
SAT = utc(2026, 11, 14, 23, 0)
MON = utc(2026, 11, 16, 15, 0)


def rules():
    return json.load(open(os.path.join(ROOT, "tools", "web_public", "ledger", "rules.json"), encoding="utf-8"))


def led(entries):
    return {"state": "ok", "entries": [MS.clean_entry(e, True) for e in entries], "hidden": [], "publish": False, "t": SUN_1700 - 60}


class Net:
    def __init__(self, status=200):
        self.calls, self.status = [], status

    def __call__(self, method, url, body=None, headers=None, timeout=None):
        self.calls.append({"method": method, "url": url, "body": (body or b"").decode("utf-8"), "headers": dict(headers or {})})
        return self.status, "{}"


def site_with(tmp, kalshi=None):
    site = os.path.join(tmp, "site")
    os.makedirs(site, exist_ok=True)
    shutil.copy(HOME_REAL, os.path.join(site, "home.json"))
    if kalshi:
        json.dump(kalshi, open(os.path.join(site, "kalshi.json"), "w", encoding="utf-8"))
    return site


def main():
    R = rules()
    # ---- the three lines
    E = [{"kind": "payout_in", "amount": 800, "date": "2026-11-12", "acct": "lit50k", "note": "PRIVATE-NOTE"},
         {"kind": "reset", "amount": 80, "date": "2026-11-10", "acct": "atlas25k"}]
    sb = MS.build({"rules": R, "ledger": led(E), "kalshi": {"kind": "kalshi", "t": SUN_1700 - 60, "total_pnl": -20, "days": [["2026-11-13", -12.5], ["2026-11-03", -7.5]]}}, SUN_1700)
    L = W.three_lines(sb)
    check("lines: what made money (the 50K's $800 payout this week), what lost (ATLAS's $80 reset), and one change (Kalshi lost this week and this month)",
          L[0] == "Made money: MFFU Builder 50K eval (Zlarior) +$800 this week." and L[1] == "Lost: MFFU Builder 25K eval (ATLAS) -$80 this week." and L[2].startswith("Change: Kalshi lost $20 this month"), L)
    empty = MS.build({"rules": R}, SUN_1700)
    L0 = W.three_lines(empty)
    check("lines with nothing this week: 'nothing put cash in', 'nothing took cash out', and the first fix (save the Ledger export as data/money_ledger.json)",
          "nothing put cash in" in L0[0] and "nothing took cash out" in L0[1] and "data/money_ledger.json" in L0[2], L0)
    home = json.load(open(HOME_REAL, encoding="utf-8"))
    st = MS.build({"rules": R, "home": home, "ledger": led([])}, SUN_1700)
    check("change rule order: a stale accounts feed (the PC report is 12 days old) comes before anything else once the ledger exists", W.suggestion(st).startswith("fix the NQ accounts"), W.suggestion(st))
    pend = MS.build({"rules": R, "ledger": led([{"kind": "payout_req", "amount": 600, "date": "2026-11-14", "acct": "lit50k"}])}, SUN_1700)
    nop = MS.build({"rules": R, "ledger": led([])}, SUN_1700)
    good = MS.build({"rules": R, "ledger": led([{"kind": "payout_in", "amount": 900, "date": "2026-11-02", "acct": "lit50k"}])}, SUN_1700)
    texts = [W.suggestion(x) for x in (sb, empty, st, pend, nop, good)]
    check("change: a pending payout says record it when it lands; no payout yet says keep the plan; all paid says no change",
          "$600 of payouts requested" in texts[3] and texts[4].startswith("no payout yet") and texts[5] == "no change: keep the plan.", texts[3:])
    check("no suggestion ever says to arm, route or go live (that stays the owner's)", not any(re.search(r"\b(arm|route|go live|live trading)\b", t, re.I) for t in texts), texts)

    # ---- the report text and the push
    rep = W.report(sb, SUN_1700)
    check("report: the markdown has the plain table (cash in / out / net, each source, ROI, run-rate), the three lines numbered, and the honest limits",
          "| Cash in |" in rep["markdown"] and "| Source |" in rep["markdown"] and "## The week in three lines" in rep["markdown"] and "1. Made money" in rep["markdown"]
          and "3. Change:" in rep["markdown"] and "ROI on eval fees" in rep["markdown"], rep["markdown"][:400])
    check("push: title 'Money week to <Sunday>: net ...', a short body under 3,800 bytes with week / month / all time, ROI, the three lines; the owner's notes never in it",
          rep["title"] == "Money week to 2026-11-15: net +$708" and len(rep["push"].encode("utf-8")) < 3800 and "Week: in $800" in rep["push"] and "Change:" in rep["push"]
          and "PRIVATE-NOTE" not in rep["push"] + rep["markdown"], (rep["title"], rep["push"][:300]))

    # ---- when it is due
    check("due: Sunday from 17:00 ET only, once per Sunday (16:59 no, 17:00 yes, already sent no, Saturday / Monday no)",
          W.due(SUN_1659, {}) is None and W.due(SUN_1700, {}) == "2026-11-15" and W.due(SUN_1700, {"sent_day": "2026-11-15"}) is None and W.due(SAT, {}) is None and W.due(MON, {}) is None)

    # ---- the hook: once, on the private topic, files in temp folders
    tmp = tempfile.mkdtemp(prefix="wmr_")
    try:
        oly = os.path.join(tmp, "olympus")
        os.makedirs(oly)
        json.dump({"topic": "nq-test-topic-0000", "ntfy": "https://ntfy.example"}, open(os.path.join(oly, "ntfy.json"), "w", encoding="utf-8"))
        feed = os.path.join(tmp, "status_feed.json")
        json.dump({"ntfy": "https://ntfy.example", "topic": "public-status"}, open(feed, "w", encoding="utf-8"))
        env = {"OLYMPUS_HOME": oly}
        site = site_with(tmp, {"kind": "kalshi", "t": SUN_1700 - 60, "balance": 50, "total_pnl": 5, "days": [["2026-11-13", 5]]})
        ledger = os.path.join(tmp, "money_ledger.json")
        json.dump({"entries": E}, open(ledger, "w", encoding="utf-8"))
        work, out = os.path.join(tmp, "work"), os.path.join(tmp, "reports")
        net = Net()
        kw = dict(work=work, http=net, env=env, out_dir=out, say=lambda *_: None, feed_path=feed, site=site, ledger=ledger)
        r0 = W.maybe_run(SUN_1659, **kw)
        r1 = W.maybe_run(SUN_1700, **kw)
        r2 = W.maybe_run(SUN_1700 + 900, **kw)
        check("hook: nothing before 17:00; at 17:00 one report written to docs/reports-style money_week_2026-11-15.md and one push; 15 minutes later nothing again",
              r0 is None and r1 and r1["sent"] and r2 is None and len(net.calls) == 1 and os.path.isfile(os.path.join(out, "money_week_2026-11-15.md")), (r1 and r1.get("why"), len(net.calls)))
        c = net.calls[0] if net.calls else {}
        check("hook: the push goes to the PRIVATE alert topic (never the public status topic), POST, an ASCII title, the moneybag tag",
              c.get("method") == "POST" and c.get("url") == "https://ntfy.example/nq-test-topic-0000" and "public-status" not in c.get("url", "")
              and c["headers"].get("Title", "").startswith("Money week to 2026-11-15") and c["headers"].get("Tags") == "moneybag", c)
        check("hook: the PC's report counts the owner's ledger (private: his own phone and file) and the site's Kalshi feed",
              "+$800" in c.get("body", "") and "PRIVATE-NOTE" not in c.get("body", ""), c.get("body", "")[:300])
        st = json.load(open(os.path.join(work, "state.json"), encoding="utf-8"))
        check("hook: state.json records the Sunday sent", st.get("sent_day") == "2026-11-15", st)
        net2, work2 = Net(status=500), os.path.join(tmp, "work2")
        W.maybe_run(SUN_1700, **{**kw, "http": net2, "work": work2})
        W.maybe_run(SUN_1700 + 900, **{**kw, "http": net2, "work": work2})
        check("hook: ntfy down -> not marked sent, tried again on the next 15-minute run", len(net2.calls) == 2 and "sent_day" not in json.load(open(os.path.join(work2, "state.json"))), len(net2.calls))
        net3, work3 = Net(), os.path.join(tmp, "work3")
        oly2 = os.path.join(tmp, "olympus2")
        os.makedirs(oly2)
        r3 = W.maybe_run(SUN_1700, **{**kw, "http": net3, "work": work3, "env": {"OLYMPUS_HOME": oly2}})
        r3b = W.maybe_run(SUN_1700 + 900, **{**kw, "http": net3, "work": work3, "env": {"OLYMPUS_HOME": oly2}})
        check("hook: no private topic -> the report is still written, nothing is sent, and it is not retried every 15 minutes", r3 and not r3["sent"] and "no private alert topic" in r3["why"] and r3b is None and not net3.calls, r3 and r3["why"])
        net4 = Net()
        r4 = W.maybe_run(SUN_1700, **{**kw, "http": net4, "work": os.path.join(tmp, "work4"), "env": {**env, "LE_MONEY_WEEKLY": "0"}})
        check("hook: LE_MONEY_WEEKLY=0 turns it off", r4 is None and not net4.calls)
        r5 = W.maybe_run(SUN_1700, **{**kw, "site": os.path.join(tmp, "nowhere"), "ledger": os.path.join(tmp, "none.json"), "work": os.path.join(tmp, "work5"), "http": Net()})
        check("hook: no site, no ledger -> still a report (fees only, sources listed missing), never a crash", r5 and "Missing:" in r5["push"], r5 and r5.get("push"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # ---- the wiring and the files
    pr = open(os.path.join(ROOT, "tools", "pc_report.py"), encoding="utf-8").read()
    # night-tasks 2026-11-23 moved the soft hooks into after_run(), called by main() only on a real run (night-reds3: same checks)
    hook = pr[pr.index("def after_run("):pr.index("\ndef ", pr.index("def after_run(") + 10)]
    main_src = pr[pr.index("def main("):]
    check("pc_report.py calls the Sunday hook after its own run, not on --dry-run, inside a try (it can never stop the 15-minute report)",
          "weekly_money_report" in hook and re.search(r"try:\s+from tools import weekly_money_report as _wmr\s+_wmr\.maybe_run\(", hook) is not None
          and main_src.count("after_run(") >= 1 and main_src.count("after_run(") == len(re.findall(r"if not a\.dry_run:\s+after_run\(", main_src))
          and main_src.index("run_once(") < main_src.index("after_run("))
    code = open(os.path.join(ROOT, "tools", "weekly_money_report.py"), encoding="utf-8").read()
    check("the report reaches the network only through pc_report.ntfy_post (no urllib / requests of its own), and has no key or token in it",
          "ntfy_post" in code and not re.search(r"^\s*(import|from)\s+(urllib|requests|http|socket)", code, re.M) and not re.search(r"api[_-]?key|password|bearer", code, re.I))
    gi = open(os.path.join(ROOT, ".gitignore"), encoding="utf-8").read()
    check("the reports in docs/reports/ and the state folder are gitignored (they hold the owner's own figures)", "docs/reports/money_week_*.md" in gi and "data/money_report/" in gi)
    print(f"\n{sum(RES)}/{len(RES)} passed")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
