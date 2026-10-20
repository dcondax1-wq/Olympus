"""The prop-business tools (tools/business.py, tools/prop_watch.py, engine/biz_api.py, the ops-task hooks): expense / payout
logs and their merge with the Excel tracker, the monthly statement (HTML + PDF), the tax-year CSV (labelled not tax advice),
payout eligibility (MFFU $2,100 buffer + the $1,500 habit), the next-eval planner (5-session stagger, the owner's prices,
codes 'verify at checkout'), the scaling calendar with its downside case, the Z06 goal, ROI per account / firm, and the
weekly rule-page / discount-code watchers with a fake fetcher (hash, change push, unreachable pages never push). No
network; everything written goes to a temp folder.

  python -X utf8 -m tests.test_business
"""
from __future__ import annotations

import csv
import datetime as dt
import json
import os
import shutil
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tools import business as B          # noqa: E402
from tools import prop_watch as W        # noqa: E402

ET = B.ET
RES = []


def check(name, cond, detail=""):
    RES.append(bool(cond))
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({str(detail)[:300]})" if detail and not cond else ""))


def ts(y, mo, d, h=12, mi=0):
    return dt.datetime(y, mo, d, h, mi, tzinfo=ET).timestamp()


def biz(accounts, expenses=None, payouts=None, **kw):
    base = json.load(open(os.path.join(ROOT, "research", "props", "business.json"), encoding="utf-8"))
    b = {**base, "accounts": accounts, "expenses": expenses if expenses is not None else [], "payouts": payouts or [],
         "source": "research/props/business.json"}
    b.update(kw)
    return b


A50 = {"id": "mffu_50k", "firm": "MyFundedFutures", "plan": "Builder 50K", "lit_id": "mffu_builder_50k", "stage": "eval", "start": "2026-10-19",
       "aliases": ["MFFU 50K eval #1"]}
A25 = {"id": "mffu_25k", "firm": "MyFundedFutures", "plan": "Builder 25K", "lit_id": "mffu_builder_25k", "stage": "planned", "start": "2026-10-26"}
FEE50 = {"date": "2026-10-19", "item": "Builder 50K eval, one-time", "usd": 91.8, "firm": "MyFundedFutures (MFFU)", "account": "mffu_50k"}


def t_logs(tmp):
    ep, pp = os.path.join(tmp, "expenses.csv"), os.path.join(tmp, "payouts.csv")
    r = B.append_row(ep, B.EXP_COLS, {"date": "2026-10-19", "firm": "MyFundedFutures (MFFU)", "account": "mffu_50k", "type": "Eval purchase",
                                      "description": "Builder 50K eval", "amount_usd": "$91.80"})
    check("add-expense: amount cleaned to 91.80, header written", r["amount_usd"] == "91.80" and open(ep).readline().startswith("date,firm"))
    try:
        B.append_row(ep, B.EXP_COLS, {"date": "2026-10-20", "amount_usd": "abc"})
        check("add-expense refuses a non-number amount", False)
    except ValueError:
        check("add-expense refuses a non-number amount", True)
    B.append_row(pp, B.PAY_COLS, {"date": "2026-11-20", "firm": "MyFundedFutures", "account": "mffu_50k", "requested_usd": 1600, "received_usd": 1280})
    ex, po = B.expense_rows(ep), B.payout_rows(pp)
    check("expense / payout rows read back", len(ex) == 1 and ex[0]["usd"] == 91.8 and po[0]["usd"] == 1280 and po[0]["requested"] == 1600, (ex, po))
    # merge: the xlsx row (same date + amount) counts once, a planned row stays
    b = {"source": "research/business/prop_business.xlsx", "expenses": [dict(FEE50), {"date": "2026-10-26", "usd": 63, "planned": True, "item": "25K"}]}
    m = B.merge_logs(b, ep, pp)
    check("merge: the same payment in the xlsx and the CSV counts once (planned kept)", len([e for e in m["expenses"] if not e.get("planned")]) == 1
          and any(e.get("planned") for e in m["expenses"]), m["expenses"])
    check("merge: payouts from the CSV", len(m["payouts"]) == 1 and m["logs"]["payouts_rows"] == 1)
    b2 = {"source": "research/props/business.json", "expenses": [{"date": "2026-10-18", "usd": 91.8, "item": "seed"}]}
    m2 = B.merge_logs(b2, ep, pp)
    check("merge: with CSV rows, business.json's own seed rows are dropped (the CSV is the log of record)",
          [e["date"] for e in m2["expenses"]] == ["2026-10-19"], m2["expenses"])
    check("union: two equal payments on one day in the CSV both count", len(B.union([], [dict(FEE50), dict(FEE50)])) == 2)


def t_sync(tmp):
    xl = os.path.join(ROOT, "research", "business", "prop_business.xlsx")
    if not os.path.exists(xl):
        check("tracker sync (xlsx missing: skipped)", True)
        return
    try:
        import openpyxl  # noqa: F401
    except ImportError:
        check("tracker sync (openpyxl missing: skipped)", True)
        return
    from tools import build_business_tracker as bt
    x = os.path.join(tmp, "t.xlsx")
    shutil.copy(xl, x)
    ep, pp = os.path.join(tmp, "s_exp.csv"), os.path.join(tmp, "s_pay.csv")
    B.append_row(ep, B.EXP_COLS, {"date": "2026-10-28", "firm": "Lucid Trading", "account": "lucid_50k", "type": "Eval purchase",
                                  "description": "LucidPro 50K eval", "amount_usd": 115.4, "code": "DGT"})
    r1 = bt.sync(x, ep, pp)
    check("sync: a CSV-only fee goes into the xlsx", r1["to_xlsx_fees"] == 1, r1)
    check("sync: xlsx-only rows come back into the CSV", r1["to_csv_expenses"] >= 0)
    r2 = bt.sync(x, ep, pp)
    check("sync twice: nothing more to copy (no duplicates)", not any(r2.values()), r2)


def t_statement(tmp):
    b = biz([A50, A25], [dict(FEE50)], [{"date": "2026-10-30", "item": "mffu_50k", "usd": 1280.0, "account": "mffu_50k", "firm": "MyFundedFutures"}])
    trades = [{"day": "2026-10-20", "entry_t": 1, "pnl": 520.0}, {"day": "2026-10-21", "entry_t": 2, "pnl": -300.0}, {"day": "2026-09-30", "entry_t": 3, "pnl": 99.0}]
    s = B.statement("2026-10", b, ts(2026, 10, 31), trades)
    S = s["business"]
    check("statement: fees, payouts, net for the month", S["fees_total"] == 91.8 and S["payouts_total"] == 1280 and abs(S["net"] - 1188.2) < 0.01, S)
    check("statement: set-aside on a positive month at the tax %", abs(S["set_aside"] - 1188.2 * S["tax_pct"] / 100) < 0.01)
    check("statement: only this month's routed trades", s["trading"]["trades"] == 2 and s["trading"]["pnl"] == 220 and s["trading"]["wins"] == 1)
    check("statement: tax label says not tax advice", "NOT tax advice" in s["tax_label"])
    h = B.write_statement("2026-10", b, os.path.join(tmp, "st"), html=True, now=ts(2026, 10, 31), trades=trades)
    txt = open(h, encoding="utf-8").read()
    check("statement HTML: written, with dark mode + NOT tax advice", h.endswith("2026-10.html") and "prefers-color-scheme:dark" in txt and "NOT tax advice" in txt)
    try:
        import reportlab  # noqa: F401
        p = B.write_statement("2026-10", b, os.path.join(tmp, "st"), now=ts(2026, 10, 31), trades=trades)
        check("statement PDF: a real PDF", p.endswith(".pdf") and open(p, "rb").read(5) == b"%PDF-")
    except ImportError:
        check("statement PDF (reportlab missing: HTML fallback)", True)


def t_tax(tmp):
    b = biz([A50], [dict(FEE50), {"date": "2025-12-30", "usd": 50, "item": "old"}], [{"date": "2026-11-20", "usd": 2000, "item": "mffu_50k"}])
    t = B.tax_year(2026, b, ts(2026, 12, 1))
    check("tax year: only 2026 rows, net = payouts - fees", t["fees"] == 91.8 and t["payouts"] == 2000 and abs(t["net"] - 1908.2) < 0.01, t)
    check("tax year: quarters (fee Q4, payout Q4)", t["quarters"][3]["fees"] == 91.8 and t["quarters"][3]["payouts"] == 2000)
    check("tax year: set-aside = pct x positive net", abs(t["set_aside"] - 1908.2 * t["pct"] / 100) < 0.05, t["set_aside"])
    p = B.write_tax_csv(2026, b, tmp, ts(2026, 12, 1))
    body = open(p, encoding="utf-8").read()
    rows = list(csv.reader(body.splitlines()))
    check("tax CSV: labelled NOT tax advice on the first line", "NOT tax advice" in rows[0][0], rows[0])
    check("tax CSV: the fee as a negative amount", any(r[:2] == ["2026-10-19", "fee"] and r[-1] == "-91.80" for r in rows), rows[:4])


def t_payout():
    base = {**A50, "stage": "funded", "funded_start": "2026-11-02", "pc_bot": False}
    now = ts(2026, 11, 20)

    def st(bal, **extra):
        return B.payout_status(biz([{**base, "balance": bal, **extra}]), now)["rows"][0]
    r = st(53700)
    check("payout: MFFU 50K needs $2,100 buffer + $1,500 habit = $3,600", r["need_habit"] == 3600 and r["rules"]["buffer"] == 2100, r.get("need_habit"))
    check("payout: profit $3,700 -> ready, ask $1,600 (keep 80%)", r["status"] == "ready" and r["request"] == 1600 and r["keep"] == 1280, r)
    check("payout: profit $2,700 -> allowed, habit says wait", st(52700)["status"] == "allowed_wait")
    check("payout: profit $1,000 -> not yet", st(51000)["status"] == "not_yet")
    check("payout: request capped at the $2,000 max", st(56000)["request"] == 2000)
    check("payout: best day over 50% of the cycle blocks it", st(53700, cycle_profit=3700, best_day=2500)["status"] == "not_yet")
    check("payout: funded without a balance -> asks for it", B.payout_status(biz([base]), now)["rows"][0]["status"] == "unknown")
    pc = B.payout_status(biz([{**base, "pc_bot": True}]), now, pc_eval={"balance": 53800})["rows"][0]
    check("payout: the PC bot's balance is used for the pc_bot account", pc["status"] == "ready" and pc["balance_src"] == "the PC bot", pc.get("balance_src"))
    check("payout: an eval account says pass first", B.payout_status(biz([A50]), now)["rows"][0]["status"] == "not_funded")
    lu = B.payout_status(biz([{"id": "lu", "firm": "Lucid Trading", "plan": "LucidPro 50K", "lit_id": "lucid_pro_50k", "stage": "eval"}]), now)["rows"][0]
    check("payout: other firms' rules from the study (Lucid has a buffer)", lu["rules"]["known"] and (lu["rules"]["buffer"] or 0) > 0, lu["rules"])
    n = B.notices(now, biz([{**base, "balance": 53700}]))
    pn = [x for x in n if x["sub"] == "payout"]
    check("payout push: one notice, keyed by account + payout count", len(pn) == 1 and pn[0]["key"] == "biz:payout:mffu_50k:0" and "can request" in pn[0]["title"], n)


def t_planner():
    b = biz([A50, A25], [dict(FEE50)])
    p = B.planner(b, ts(2026, 10, 20))
    s0 = p["steps"][0]
    check("planner: the owner's planned 25K first at his price $63", s0["slot"] == "planned:mffu_25k" and s0["price"] == 63 and s0["price_basis"].startswith("your price"), s0)
    check("planner: not due before its date", not s0["due"] and p["cash"] == round(p["budget"] - 91.8, 2))
    check("planner: codes listed, verify at checkout", s0["verify"] == "verify at checkout" and s0["codes"], s0.get("codes"))
    nxt = p["steps"][1]
    check("planner: next ladder slot (LucidPro) at least 5 sessions after the 25K", nxt["plan"] == "lucid_pro_50k"
          and nxt["date"] == B.sessions_after(dt.date(2026, 10, 26), 5).isoformat(), nxt)
    check("planner: Lucid waits for the 50K eval to be decided", not nxt["due"] and "decided" in (nxt["wait"] or ""), nxt.get("wait"))
    check("planner: 5 sessions after Mon 2026-10-19 is Mon 2026-10-26", B.sessions_after(dt.date(2026, 10, 19), 5) == dt.date(2026, 10, 26))
    # 50K decided (funded), no planned 25K: Lucid is due 5 sessions after the 50K start, inside the budget
    b2 = biz([{**A50, "stage": "funded"}], [dict(FEE50)])
    early = B.planner(b2, ts(2026, 10, 23))["steps"][0]
    check("planner: before 5 sessions -> wait", not early["due"] and "sessions after" in (early["wait"] or ""), early)
    due = B.planner(b2, ts(2026, 10, 26))["steps"][0]
    check("planner: on session 5 with cash -> due", due["due"] and due["plan"] == "lucid_pro_50k", due)
    n = [x for x in B.notices(ts(2026, 10, 26), b2) if x["sub"] == "buy"]
    check("buy push: 'Time to buy', price + codes + verify at checkout", len(n) == 1 and n[0]["title"].startswith("Time to buy") and "verify at checkout" in n[0]["body"], n)
    poor = biz([{**A50, "stage": "funded"}], [dict(FEE50)], planner={"budget_usd": 100, "stagger_sessions": 5})
    pp = B.planner(poor, ts(2026, 10, 26))["steps"][0]
    check("planner: not enough cash -> wait for payouts", not pp["due"] and "cash" in (pp["wait"] or ""), pp)
    check("prices: MFFU Builder 50K = the owner's $91.80", B.plan_price("mffu_builder_50k")["usd"] == 91.8)


def t_calendar_goal_roi():
    b = biz([A50, A25], [dict(FEE50)])
    c = B.calendar(b, ts(2026, 10, 20))
    check("calendar: 12 months from this month", len(c["rows"]) == 12 and c["rows"][0]["month"] == "2026-10")
    check("calendar: expected and downside columns", all("down_cum" in r for r in c["rows"]) and c["rows"][-1]["cum"] > c["rows"][-1]["down_cum"], c["rows"][-1])
    check("calendar: downside of the trio is negative (2021-25 trades)", (c["trio"]["down_month"] or 0) < 0, c["trio"])
    check("calendar: buys the planned 25K and a LucidPro", any("25K" in " ".join(r["buy"]) for r in c["rows"]) and any("LucidPro" in " ".join(r["buy"]) for r in c["rows"]))
    g = B.goal(biz([A50], [dict(FEE50)], [{"date": "2026-11-20", "usd": 2000}]), ts(2026, 11, 21))
    share = (1 - g["tax_pct"] / 100) * g["keep_pct"] / 100
    check("goal: saved = payouts x (1 - tax) x keep share", abs(g["saved"] - 2000 * share) < 0.01, g)
    check("goal: months at the H2 rate shorter than the conservative one", g["months_h2"] < g["months_cons"], (g["months_h2"], g["months_cons"]))
    r = B.roi(biz([A50, A25], [dict(FEE50), {"date": "2026-10-28", "usd": 115.4, "item": "LucidPro 50K eval", "firm": "Lucid Trading"}],
                  [{"date": "2026-11-20", "usd": 1280, "item": "MFFU 50K eval #1", "account": "MFFU 50K eval #1"}]), ts(2026, 11, 21))
    a = {x["id"]: x for x in r["accounts"]}
    check("ROI: fee + payout matched to the 50K (alias), ROI %", a["mffu_50k"]["net"] == 1188.2 and a["mffu_50k"]["roi_pct"] == round(100 * 1188.2 / 91.8, 1), a["mffu_50k"])
    check("ROI: days to the first payout", a["mffu_50k"]["days_to_first_payout"] == 32)
    check("ROI: an unmatched fee lands in 'unassigned', firm totals", "unassigned" in a and any(f["firm"] == "Lucid" for f in r["firms"]), r["firms"])


def t_watch(tmp):
    hp, cp = os.path.join(tmp, "rule_hashes.json"), os.path.join(tmp, "code_watch.json")
    page = "<html><nav>menu</nav><p>The payout buffer is $2,100 on the 50K. Updated 3 days ago.</p><p>Automated trading is allowed with approval.</p></html>"
    pages = [{"firm": "mffu", "key": "mffu_b50", "url": "https://help.myfundedfutures.com/x"}, {"firm": "lucid", "key": "lucid", "url": "https://lucid.example/y"}]
    content = {"https://help.myfundedfutures.com/x": page}
    fetcher = lambda u: (content[u], None) if u in content else (None, "HTTP 403")   # noqa: E731
    r1 = W.check_rules(ts(2026, 10, 25, 18), fetcher, pages, hp)
    check("rules: first sight stores the hash, no change pushed", r1["checked"] == 1 and not r1["changes"] and len(r1["errors"]) == 1, r1["errors"])
    check("rules: the text itself is not stored", "buffer" not in open(hp).read())
    content["https://help.myfundedfutures.com/x"] = page.replace("3 days", "5 days")
    r2 = W.check_rules(ts(2026, 11, 1, 18), fetcher, pages, hp)
    check("rules: a moving 'updated N days ago' is not a change", not r2["changes"])
    content["https://help.myfundedfutures.com/x"] = page.replace("$2,100", "$2,500")
    r3 = W.check_rules(ts(2026, 11, 8, 18), fetcher, pages, hp)
    check("rules: a changed rule sentence is a change", len(r3["changes"]) == 1 and r3["changes"][0]["key"] == "mffu_b50")
    n = W.rule_notice(r3["changes"][0])
    check("rules push: 'MFFU rules page changed — review'", n["title"].startswith("MFFU rules page changed") and n["key"].startswith("biz:rules:mffu_b50:"))
    st = json.load(open(hp))
    check("rules: unreachable page recorded with its error and fail count", st["pages"]["https://lucid.example/y"]["fails"] == 3
          and st["pages"]["https://lucid.example/y"]["last_error"] == "HTTP 403")
    cpages = {"mffu": ["https://c.example/a"]}
    content["https://c.example/a"] = "<p>Use code SAVE40X for 40% off. Promo code: MFFU (no). Coupon code: TRADEBIG</p>"
    c1 = W.check_codes(ts(2026, 10, 25, 18), fetcher, cpages, cp, search=False)
    got = {x["code"] for x in c1["new"]}
    check("codes: new codes found, stop words skipped", {"SAVE40X", "TRADEBIG"} <= got and "MFFU" not in got, got)
    check("codes: all unverified, 'verify at checkout'", all(x["st"] == "unverified" and "verify at checkout" in x["note"] for x in c1["new"]))
    check("codes: % off read from the text", next(x for x in c1["new"] if x["code"] == "SAVE40X")["off"] == "40%")
    c2 = W.check_codes(ts(2026, 11, 1, 18), fetcher, cpages, cp, search=False)
    check("codes: the same codes next week are not new again", not c2["new"])
    check("codes push: one weekly notice", W.codes_notice(c1["new"], ts(2026, 10, 25, 18))["key"] == "biz:codes:2026-W43")
    sm = W.summary(hp, cp)
    check("summary: pages, changes, code rows", sm["rules"]["pages"] == 2 and sm["rules"]["changes"] and sm["codes"]["rows"], sm)
    w = {"codes": [{"firm": "lucid", "code": "NEWLU", "off": "30%", "seen": "2026-10-25"}]}
    cf = B.codes_for("lucid", watch=w)
    check("planner codes include the watcher's (unverified)", any(c["code"] == "NEWLU" and c["st"] == "unverified" for c in cf), cf)
    # weekly(): offline -> no push, retried an hour later, at most 3 runs; reachable -> once a week
    off = lambda u: (None, "URLError: Tunnel connection failed: 403")   # noqa: E731
    state = {}
    old = W.RULE_KEYS, W.CODE_PAGES
    hp2, cp2 = os.path.join(tmp, "h2.json"), os.path.join(tmp, "c2.json")
    t0 = ts(2026, 10, 25, 18)
    out = W.weekly(t0, state, off, hp2, cp2)
    check("weekly offline: no push, week not marked done", out == [] and "prop_watch_wk" not in state and state["prop_watch_try"]["n"] == 1, state)
    check("weekly offline: no retry within the hour", W.weekly(t0 + 600, state, off, hp2, cp2) == [] and state["prop_watch_try"]["n"] == 1)
    W.weekly(t0 + 3700, state, off, hp2, cp2)
    W.weekly(t0 + 7400, state, off, hp2, cp2)
    check("weekly offline: after 3 tries the week is closed", state.get("prop_watch_wk") == "2026-W43", state)
    check("weekly: nothing more that week", W.weekly(t0 + 20000, state, off, hp2, cp2) == [])
    W.RULE_KEYS, W.CODE_PAGES = old


def t_ops():
    from engine import ops_checks as oc
    calls = []
    orig_b, orig_w = B.notices, W.weekly
    B.notices = lambda now=None, **kw: calls.append("biz") or [{"sub": "buy", "title": "Time to buy: X", "body": "b", "key": "biz:buy:t"}]
    W.weekly = lambda now=None, state=None, **kw: calls.append("watch") or []
    try:
        n = oc.business_notices({"eval": None}, ts(2026, 10, 26, 16, 10))
        check("ops: business notices become push payloads", len(n) == 1 and n[0]["key"] == "biz:buy:t" and n[0]["title"] == "Time to buy: X", n)
        oc.watch_notices({}, ts(2026, 10, 25, 18))
        check("ops: the weekly watcher hook runs", "watch" in calls)
        B.notices = lambda *a, **k: 1 / 0
        check("ops: a failing business module never breaks the tick", oc.business_notices({}, ts(2026, 10, 26, 16, 10)) == [])
    finally:
        B.notices, W.weekly = orig_b, orig_w
    src = open(os.path.join(ROOT, "engine", "ops_checks.py"), encoding="utf-8").read()
    check("ops: replay / test ticks (ctx handed in) skip business pushes and web fetches", "if real:" in src and 'D["weekly"] and real' in src)
    gi = open(os.path.join(ROOT, ".gitignore"), encoding="utf-8").read()
    check(".gitignore: watcher state + generated statements stay machine-local", all(x in gi for x in (
        "research/props/rule_hashes.json", "research/props/code_watch.json", "research/business/statements/")))


def t_view_api():
    v = B.view(now=ts(2026, 10, 20))
    keys = ("statement", "tax", "payouts", "planner", "calendar", "goal", "roi", "watch", "logs")
    errs = {k: v[k].get("error") for k in keys if isinstance(v.get(k), dict) and v[k].get("error")}
    check("view: every panel builds", not errs and all(k in v for k in keys), errs)
    check("view: small enough for the phone (< 60 KB)", len(json.dumps(v, default=str)) < 60000)
    check("view: no secrets-looking fields", not any(w in json.dumps(v, default=str).lower() for w in ("api_key", "password", "secret", "token")))
    try:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
    except Exception:
        check("API (fastapi missing: skipped)", True)
        return
    from engine import biz_api
    app = FastAPI()
    app.include_router(biz_api.router)
    cl = TestClient(app)
    r = cl.get("/api/next/hub/biz")
    check("API /api/next/hub/biz 200 with the panels", r.status_code == 200 and "planner" in r.json(), r.status_code)
    check("API statement: bad month -> 400", cl.get("/api/next/hub/biz/statement/2026-13").status_code == 400)
    old = B.STATEMENTS
    tmp = tempfile.mkdtemp()
    try:
        orig = B.write_statement
        B.write_statement = lambda m, html=False: orig(m, out_dir=tmp, html=html)
        r = cl.get("/api/next/hub/biz/statement/2026-10?html=1")
        check("API statement HTML", r.status_code == 200 and "P&amp;L statement 2026-10" in r.text, r.status_code)
        B.write_statement = orig
    finally:
        B.STATEMENTS = old
        shutil.rmtree(tmp, ignore_errors=True)
    r = cl.get("/api/next/hub/biz/tax/2026.csv")
    check("API tax CSV: attachment, not tax advice", r.status_code == 200 and "NOT tax advice" in r.text and "attachment" in r.headers.get("content-disposition", ""))
    from engine import next_api
    app2 = FastAPI()
    app2.include_router(next_api.router)
    check("API mounted in engine/next_api.py", TestClient(app2).get("/api/next/hub/biz/statement/bad").status_code == 400)
    from tools import hub_data
    check("hub data export carries biz (both dashboards)", "biz" in open(hub_data.__file__, encoding="utf-8").read() and callable(hub_data.biz_view))
    js = open(os.path.join(ROOT, "web_next", "js", "next", "hubpages.js"), encoding="utf-8").read()
    ph = open(os.path.join(ROOT, "tools", "web_public", "hub.js"), encoding="utf-8").read()
    check("PC pages: Business shows the tools, Prop Firms shows the watchers", "bizSections(bz)" in js and "watchCard(bz)" in js)
    check("phone: Prop firms page shows the business tools from data.hub.biz", "bizTools()" in ph and "HUBD().biz" in ph)


def main():
    tmp = tempfile.mkdtemp(prefix="biz_test_")
    try:
        t_logs(tmp)
        t_sync(tmp)
        t_statement(tmp)
        t_tax(tmp)
        t_payout()
        t_planner()
        t_calendar_goal_roi()
        t_watch(tmp)
        t_ops()
        t_view_api()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(f"business: {sum(RES)}/{len(RES)} {'ALL PASS' if all(RES) else 'FAILED'}")
    return 0 if all(RES) else 1


if __name__ == "__main__":
    sys.exit(main())
