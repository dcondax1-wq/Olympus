"""tools/rules_watch.py: the MFFU rule-change watcher. Saved MFFU help-center pages (tests/fixtures/mffu_pages/, fetched 2026-11-23,
<article> only); NO network.

  a. today's pages vs research/lit/mffu_rules.json: every watched rule reads, all "ok" (46 rules)
  b. a real change (MFFU raises the Builder 25K DLL to $700 on its page): "changed", the alert says was $600 now $700 + the URL +
     "the bot still uses $600 until Claude updates it"; ONE alert + one board line; never again for the same value
  c. a layout change (the label renamed / the table gone) = "missing", never "changed", no alert
  d. unreachable (HTTP 503 / timeout / an empty page) = "unreachable", no alert; all pages down = the day is not marked done
  e. never touches mffu_rules.json or a live file; the stored value follows mffu_rules.json (a Claude update moves it)
  f. schedule: weekdays from 17:05 ET, once a day; off with LE_RULES_WATCH=0
    python -X utf8 -m tests.test_rules_watch
"""
from __future__ import annotations

import copy
import datetime as dt
import hashlib
import json
import os
import shutil
import sys
import tempfile
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tools import rules_watch as RW  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "mffu_pages")
ET = ZoneInfo("America/New_York")
RES: list = []


def check(name, ok, detail=""):
    RES.append(bool(ok))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{str(detail)[:400]}]" if detail and not ok else ""))


def page(url):
    aid = url.rsplit("/", 1)[-1].split("-", 1)[0]
    return open(os.path.join(FIX, f"{aid}.html"), encoding="utf-8").read()


def http_ok(url):
    return 200, page(url)


def ts(y, m, d, h, mi=0):
    return dt.datetime(y, m, d, h, mi, tzinfo=ET).timestamp()


RULES = json.load(open(RW.RULES_PATH, encoding="utf-8"))


def part_a():
    res = RW.run(http=http_ok, rules=RULES, now=ts(2026, 11, 23, 17, 10))
    bad = [r for r in res["rows"] if r["status"] != "ok"]
    check(f"a. all {len(RW.WATCH)} watched rules read and match mffu_rules.json", not bad and res["counts"]["ok"] == len(RW.WATCH), bad)
    ids = {r["id"] for r in RW.WATCH}
    need = {"b25_dll", "b50_dll", "b25_mll", "b50_mll", "b25_cons", "r25_cons", "b25_pay_min", "r25_pay_min", "b25_accounts",
            "inactivity", "news_window", "rapid_live", "r25_dll"}
    check("a. the rules the lead named are watched (DLL, MLL, consistency, payout minimums, accounts, inactivity, news, Rapid live)",
          need <= ids, need - ids)


def part_b():
    tmp = tempfile.mkdtemp()
    try:
        rp = os.path.join(tmp, "rw.json")

        def http_changed(url):
            h = page(url)
            if "17036130" in url:
                h = h.replace("$600", "$700")            # MFFU raises the Builder 25K soft DLL on its page
            return 200, h
        res = RW.run(http=http_changed, rules=RULES, now=ts(2026, 11, 23, 17, 10))
        ch = [r for r in res["rows"] if r["status"] == "changed"]
        check("b. one rule changed: the Builder 25K DLL, stored $600, page $700", len(ch) == 1 and ch[0]["id"] == "b25_dll"
              and ch[0]["stored"] == 600 and ch[0]["seen"] == 700, ch)
        sent, board = [], []
        out = RW.report(res, path=rp, sender=lambda a: sent.append(a) or True, board=board.append)
        t, b = RW.alert_text(ch[0])
        check("b. the alert: 'MFFU rule changed: ... was $600, now $700 (source <url>). The bot still uses $600 until Claude updates it'",
              len(sent) == 1 and sent[0]["title"].startswith("MFFU rule changed: Builder 25K daily loss limit") and "was $600, now $700" in sent[0]["body"]
              and "17036130" in sent[0]["body"] and "still uses $600 until Claude updates it" in sent[0]["body"], sent)
        check("b. one board line", len(board) == 1 and "$700" in board[0], board)
        out2 = RW.report(res, path=rp, sender=lambda a: sent.append(a) or True, board=board.append)
        check("b. the same change again = no second alert", out and not out2 and len(sent) == 1, (out, out2))
        fail = RW.report(dict(res), path=os.path.join(tmp, "rw2.json"), sender=lambda a: False, board=board.append)
        check("b. a send that failed is not marked told (tried again next day)", not fail
              and not json.load(open(os.path.join(tmp, "rw2.json"))).get("told"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def part_c():
    def http_layout(url):
        h = page(url)
        if "17036130" in url:
            h = h.replace("Soft Daily Loss Limit", "Daily Pause Threshold")   # a renamed label
        if "8230009" in url:
            h = h.replace("minutes before and after", "min around")             # a reworded sentence
        return 200, h
    res = RW.run(http=http_layout, rules=RULES)
    st = {r["id"]: r["status"] for r in res["rows"]}
    check("c. a renamed label / a reworded sentence = 'missing', never 'changed'", st["b25_dll"] == "missing"
          and st["news_window"] == "missing" and "changed" not in st.values(), st)
    tmp = tempfile.mkdtemp()
    try:
        sent = []
        RW.report(res, path=os.path.join(tmp, "rw.json"), sender=lambda a: sent.append(a) or True, board=lambda t: None)
        check("c. no alert for 'missing'", not sent, sent)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    tbl = RW.page_text("<article><p>Soft Daily Loss Limit (Soft Pause)</p><p>None</p></article>")
    check("c. a cell with no number ('None') = missing, not $0", RW.read_rule(tbl, next(r for r in RW.WATCH if r["id"] == "b25_dll"))[0] is None)


def part_d():
    def http_down(url):
        if "14290805" in url:
            return 503, ""
        if "16727601" in url:
            raise TimeoutError("slow")
        if "8230009" in url:
            return 200, "<html><body>Please sign in</body></html>"
        return 200, page(url)
    res = RW.run(http=http_down, rules=RULES)
    st = {}
    for r in res["rows"]:
        st.setdefault(r["url"], set()).add(r["status"])
    check("d. HTTP 503 = unreachable", st[RW.P["b50"]] == {"unreachable"}, st[RW.P["b50"]])
    check("d. a timeout = unreachable", st[RW.P["r25"]] == {"unreachable"}, st[RW.P["r25"]])
    check("d. an empty / login page = unreachable", st[RW.P["news"]] == {"unreachable"}, st[RW.P["news"]])
    check("d. the other pages still check fine", st[RW.P["b25"]] == {"ok"}, st[RW.P["b25"]])
    tmp = tempfile.mkdtemp()
    try:
        p = os.path.join(tmp, "rw.json")
        r = RW.maybe_run(now=ts(2026, 11, 23, 17, 10), http=lambda u: (503, ""), sender=lambda a: True, path=p)
        check("d. every page down: no alert, the day NOT marked done", r and not r["alerts"] and RW.due(ts(2026, 11, 23, 17, 30), p), r)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def part_e():
    before = hashlib.sha256(open(RW.RULES_PATH, "rb").read()).hexdigest()
    RW.run(http=http_ok)
    check("e. mffu_rules.json is never written", hashlib.sha256(open(RW.RULES_PATH, "rb").read()).hexdigest() == before)
    r2 = copy.deepcopy(RULES)
    r2["limits"]["builder_25k"]["dll"] = 700.0
    res = RW.run(http=http_ok, rules=r2)
    row = next(r for r in res["rows"] if r["id"] == "b25_dll")
    check("e. the stored value comes from mffu_rules.json (an edited file -> the watcher compares with it)",
          row["stored"] == 700 and row["status"] == "changed", row)
    src = open(os.path.join(ROOT, "tools", "rules_watch.py"), encoding="utf-8").read()
    check("e. no write to a live / rules file in the code", "open(RULES_PATH, \"w\"" not in src and "live_model" not in src)


def part_f():
    tmp = tempfile.mkdtemp()
    try:
        p = os.path.join(tmp, "rw.json")
        check("f. not before 17:05 ET", not RW.due(ts(2026, 11, 23, 16, 50), p))
        check("f. due at 17:10 ET on a weekday", RW.due(ts(2026, 11, 23, 17, 10), p))
        check("f. not on Saturday", not RW.due(ts(2026, 11, 28, 18, 0), p))
        r = RW.maybe_run(now=ts(2026, 11, 23, 17, 10), http=http_ok, sender=lambda a: True, path=p)
        check("f. a run marks the day done: once a day", r and not RW.due(ts(2026, 11, 23, 18, 0), p) and RW.due(ts(2026, 11, 24, 17, 10), p))
        os.environ["LE_RULES_WATCH"] = "0"
        check("f. LE_RULES_WATCH=0 = off", RW.maybe_run(now=ts(2026, 11, 24, 17, 10), http=http_ok, path=p) is None)
        os.environ.pop("LE_RULES_WATCH", None)
        check("f. the PC's 15-minute report calls it", "rules_watch as _rw" in open(os.path.join(ROOT, "tools", "pc_report.py"), encoding="utf-8").read())
    finally:
        os.environ.pop("LE_RULES_WATCH", None)
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    for f in (part_a, part_b, part_c, part_d, part_e, part_f):
        try:
            f()
        except Exception as e:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            check(f"{f.__name__} raised {e.__class__.__name__}: {e}", False)
    n, ok = len(RES), sum(RES)
    print(f"\nrules watch: {ok}/{n} " + ("ALL PASS" if ok == n else "FAILED"))
    return 0 if ok == n else 1


if __name__ == "__main__":
    sys.exit(main())
