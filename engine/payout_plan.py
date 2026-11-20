"""PAYOUT PLANNER (night team B, 2026-11-16; owner: "we need to start making money"). Read-only, pure, stdlib only.

From each eval's progress (the published home.json shape: accounts[] kind "eval" = Zlarior / LIT on the Builder 50K, second.account_b =
ATLAS on a Builder 25K) it estimates, per account:
  pass         typical and slow date (trading days at the research pace: 50K $3,000 target in a median 9 sessions, docs/ACCOUNT_4.md;
               25K $1,500 at $150 a session, engine/funded_life.PLANS typical_day)
  first payout the day the funded account reaches the owner's ask line (MFFU buffer + $1,500 / $750, engine/funded_life.track),
               the request (MFFU min..max) and what lands with him (80%), money in the bank about 4 business days later (ESTIMATE)
  funded       $ a month once funded (research/props/roadmap.json net12 / 12, conservative H2: LIT 50K $546, ATLAS 25K $338)
and the account #4 rule (docs/ACCOUNT_4.md): buy the LucidPro 50K the day the FIRST payout is in the bank (about $120-135 with a code;
in the Black Friday window Nov 19 - Dec 1 buy in the sale).

Every date and $ here is an ESTIMATE at a typical pace, never a promise; an eval can also fail (47% pass within 2 weeks, 0.2% fail in
the 2-week study; the rest still open). The same math runs on the phone (tools/web_public/business/businesscore.js planPayouts);
tests.test_money_door checks both give the same answer.

  python -X utf8 -m engine.payout_plan                 the plan from tools/web_public/home.json (if built) else the demo accounts
  python -X utf8 -m engine.payout_plan --demo          the demo accounts (no files read)
"""
from __future__ import annotations

import datetime as _dt
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine.funded_life import PLANS  # noqa: E402

VERSION = 1
# per plan: eval target, $ a session at the eval pace, funded $ a session, funded $/month (research), the eval's price (owner's price)
PACE = {
    "builder50k": {"target": 3000.0, "eval_day": round(3000.0 / 9, 2), "funded_month": 546.0, "price": 91.80, "bot": "Zlarior (LIT)"},
    "builder25k": {"target": 1500.0, "eval_day": 150.0, "funded_month": 338.0, "price": 63.00, "bot": "ATLAS"},
}
SLOW = 2.0                     # the slow case: twice the sessions (about 1 in 10 paths in the roadmap study is slower still)
BANK_DAYS = 4                  # business days from the request to the bank (ESTIMATE: check MFFU's payout page)
CLOSED = {"2026-11-26", "2026-12-25", "2027-01-01", "2027-01-18", "2027-02-15", "2027-04-02", "2027-05-31", "2027-06-18", "2027-07-05",
          "2027-09-06", "2027-11-25", "2027-12-24"}   # CME equity futures full closures (Thanksgiving, Christmas, New Year ... ): no session
# the next buys (owner 2026-11-20, Decide card drop-lucid-account4: YES, "MFFU only"; was a LucidPro 50K): the Rapid EOD 25K now, the Rapid EOD 50K
# from the first payout (business/fleet_plan.json next_buy: $165 with code CLUB, about $1,969 a month Jul-Oct-like), then a fresh Builder 50K
ACCOUNT4 = {"name": "Rapid EOD 50K", "now": "Rapid EOD 25K", "then": "a fresh Builder 50K", "price": [165, 165], "code": "CLUB", "adds_month": 1969.0,
            "sale": None, "doc": "business/fleet_plan.json"}


def _d(s: str) -> _dt.date:
    return _dt.date.fromisoformat(str(s)[:10])


def sessions_after(day: str, n: int) -> str:
    """the date of the n-th trading session after day (weekdays, CME full closures skipped); n <= 0 -> day itself"""
    d = _d(day)
    while n > 0:
        d += _dt.timedelta(days=1)
        if d.weekday() < 5 and d.isoformat() not in CLOSED:
            n -= 1
    return d.isoformat()


def business_after(day: str, n: int) -> str:
    d = _d(day)
    while n > 0:
        d += _dt.timedelta(days=1)
        if d.weekday() < 5:
            n -= 1
    return d.isoformat()


def _num(x, d=0.0):
    try:
        v = float(x)
        return d if v != v else v
    except (TypeError, ValueError):
        return d


def accounts_from_home(home: dict | None) -> list:
    """home.json -> [{name, plan, stage, to_target, room, profit}] (no broker ids: names are the bots')"""
    out = []
    if not isinstance(home, dict):
        return out
    for a in home.get("accounts") or []:
        if not isinstance(a, dict) or a.get("kind") not in ("eval", "funded") or a.get("source") == "cloud":
            continue
        e = a.get("eval") or {}
        start = _num(e.get("start_balance"), 50000.0)
        plan = "builder25k" if abs(start - 25000.0) < 1 else "builder50k"
        out.append({"name": PACE[plan]["bot"], "plan": plan, "stage": a["kind"], "to_target": _num(e.get("to_target"), PACE[plan]["target"]),
                    "room": _num(e.get("room"), PLANS[plan]["mll"]), "profit": _num(e.get("profit")), "status": str(e.get("status") or "open")})
    b = ((home.get("second") or {}).get("account_b")) or {}
    if isinstance(b, dict) and b.get("eval") and b.get("enabled", True):
        e = b["eval"]
        plan = "builder25k" if "25" in str(b.get("plan") or "25") else "builder50k"
        out.append({"name": "ATLAS", "plan": plan, "stage": "funded" if str(b.get("stage") or "") == "funded" else "eval",
                    "to_target": _num(e.get("to_target"), PACE[plan]["target"]), "room": _num(e.get("room"), PLANS[plan]["mll"]),
                    "profit": _num(e.get("profit")), "status": str(e.get("status") or "open")})
    return out


def plan_account(a: dict, today: str) -> dict:
    """one account's estimate (pure)"""
    plan = a.get("plan") if a.get("plan") in PACE else "builder50k"
    P, X = PLANS[plan], PACE[plan]
    name = str(a.get("name") or X["bot"])[:40]
    room, stage = _num(a.get("room"), P["mll"]), a.get("stage") or "eval"
    status = str(a.get("status") or "open").lower()
    goal = P["buffer"] + P["ask_above"]                         # funded profit at the owner's ask line
    req = min(P["pay_max"], P["ask_above"])                     # what he asks at that line (the most the rules allow there)
    r = {"name": name, "plan": plan, "label": P["label"], "stage": stage, "room": round(room, 2), "price": X["price"],
         "request": req, "to_you": round(req * P["split"], 2), "funded_month": X["funded_month"]}
    if room <= 0 or status in ("failed", "breached", "lost"):
        return {**r, "state": "lost", "text": f"{name}: the eval is gone. Buy a new {P['label']} eval at ${X['price']:.2f} when you want it back."}
    if stage == "funded":
        to_ask = max(0.0, goal - _num(a.get("profit")))
        n = max(int(P["cycle_days"]), int(math.ceil(to_ask / P["typical_day"]))) if to_ask > 0 else 0
        typ, slow = sessions_after(today, n), sessions_after(today, int(math.ceil(n * SLOW)))
        r.update(state="funded", pass_typical=None, pass_slow=None, payout_typical=typ, payout_slow=slow,
                 bank_typical=business_after(typ, BANK_DAYS), sessions_to_payout=n)
    else:
        left = max(0.0, _num(a.get("to_target"), X["target"]))
        n = int(math.ceil(left / X["eval_day"])) if left > 0 else 0
        p_typ, p_slow = sessions_after(today, n), sessions_after(today, int(math.ceil(n * SLOW)))
        nf = max(int(P["cycle_days"]), int(math.ceil(goal / P["typical_day"])))       # funded sessions from $0 to the ask line
        f_wait = int(math.ceil(P["first_wait_h"] / 24.0))
        typ = sessions_after(p_typ, 1 + max(nf, f_wait))                               # funded starts the session after the pass
        slow = sessions_after(p_slow, 1 + int(math.ceil(max(nf, f_wait) * SLOW)))
        r.update(state="passed" if left <= 0 or status == "passed" else "eval", pass_typical=p_typ, pass_slow=p_slow,
                 sessions_to_pass=n, payout_typical=typ, payout_slow=slow, bank_typical=business_after(typ, BANK_DAYS), sessions_to_payout=nf)
    when = "passes about " + r["pass_typical"] + " (slow " + r["pass_slow"] + "), " if r.get("pass_typical") else ""
    r["text"] = (f"{name}: {when}first payout about {r['payout_typical']} (slow {r['payout_slow']}): ask ${req:,.0f}, "
                 f"${r['to_you']:,.0f} to you, in the bank about {r['bank_typical']}.")
    return r


def plan(accounts: list, today: str | None = None) -> dict:
    today = str(today or _dt.date.today().isoformat())[:10]
    rows = [plan_account(a, today) for a in accounts or [] if isinstance(a, dict)]
    alive = [r for r in rows if r["state"] != "lost"]
    first = min(alive, key=lambda r: r["bank_typical"]) if alive else None
    buy = first["bank_typical"] if first else None
    in_sale = bool(buy and ACCOUNT4["sale"] and ACCOUNT4["sale"][0] <= buy <= ACCOUNT4["sale"][1])
    a4 = {**ACCOUNT4, "buy_on": buy, "in_sale": in_sale, "after": first["name"] if first else None,
          "text": (f"Next buys (MFFU only): the {ACCOUNT4['now']} now (added today), then the {ACCOUNT4['name']} about {buy}, the day {first['name']}'s "
                   f"first payout is in your bank (${ACCOUNT4['price'][0]} with code {ACCOUNT4['code']}; adds about ${ACCOUNT4['adds_month']:,.0f} a month, estimate), "
                   f"then {ACCOUNT4['then']}." + (" That is inside the sale: buy in the sale." if in_sale else "")) if first else
                  f"Next buys (MFFU only): the {ACCOUNT4['now']} now; the {ACCOUNT4['name']} waits for a first payout."}
    month = round(sum(r["funded_month"] for r in alive), 2)
    paid_first = round(sum(r["to_you"] for r in alive), 2)
    return {"v": VERSION, "kind": "payout-plan", "today": today, "label": "ESTIMATE", "accounts": rows, "account4": a4,
            "first_payout_to_you": paid_first, "funded_month": month, "funded_month_with_4": round(month + (ACCOUNT4["adds_month"] if alive else 0), 2),
            "first": {"name": first["name"], "bank": first["bank_typical"], "to_you": first["to_you"]} if first else None,
            "note": "Typical pace from the research (not a promise). Evals can fail; the slow date is about twice the sessions. "
                    "Bank dates assume about 4 business days after the request: check MFFU's payout page."}


DEMO = [{"name": "Zlarior (LIT)", "plan": "builder50k", "stage": "eval", "to_target": 3000.0, "room": 2000.0, "profit": 0.0},
        {"name": "ATLAS", "plan": "builder25k", "stage": "eval", "to_target": 1500.0, "room": 1000.0, "profit": 0.0}]


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    accts = DEMO
    if "--demo" not in argv:
        p = os.path.join(ROOT, "tools", "web_public", "home.json")
        try:
            accts = accounts_from_home(json.load(open(p, encoding="utf-8"))) or DEMO
        except (OSError, ValueError):
            pass
    doc = plan(accts)
    for r in doc["accounts"]:
        print(r["text"])
    print(doc["account4"]["text"])
    print(f"Funded, all accounts: about ${doc['funded_month']:,.0f} a month; with account #4 about ${doc['funded_month_with_4']:,.0f} (ESTIMATE).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
