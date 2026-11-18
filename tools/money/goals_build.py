"""GOALS page data (owner 2026-11-18: "Goals: next plans for me"). Writes tools/web_public/business/goals.json for
tools/web_public/business/goals.html: this week's steps with dates, the money ladder (milestones with done / next / later
chips), the rules that protect the accounts, and the decisions waiting on the owner.

  python tools/money/goals_build.py              rebuild from the files + the live board (git fetch + ntfy; offline if that fails)
  python tools/money/goals_build.py --offline    the same from the repo only
  python tools/money/goals_build.py --print      print the JSON instead of writing it

Sources (read only):
  research/lab/fleet_plan.json   tools/money/fleet_plan.py: one Monte Carlo for every account (the dates are its medians)
  research/lab/rapid25.json      tools/money/rapid25.py: Rapid EOD 25K / 50K eval and funded numbers
  tools/web_public/business/accounts.json   the plan (stages, ATLAS funded payouts) and the "decisions"
  tools/board.py gather          the live board: which accounts the PC / owner say passed or are funded
THE LEAD KEEPS IT CURRENT: edit WEEK below (mark "done": True when a step is finished) and re-run. Estimates only; the dates
are medians of a Jul-Oct 2026-like market. Never trades, arms or routes anything.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for p in (ROOT, os.path.join(ROOT, "tools"), os.path.join(ROOT, "tools", "money")):
    if p not in sys.path:
        sys.path.insert(0, p)

FLEET = os.path.join(ROOT, "research", "lab", "fleet_plan.json")
RAPID25 = os.path.join(ROOT, "research", "lab", "rapid25.json")
ACCOUNTS = os.path.join(ROOT, "tools", "web_public", "business", "accounts.json")
OUT = os.path.join(ROOT, "tools", "web_public", "business", "goals.json")

MKT = "H2"                        # the ladder's market: 2026 Jul-Oct-like (the honest middle; Jan-Jun was better)
BAD = "REF"                       # the bad case: 2021-25-like (no edge)
BUDGET = 150.0                    # the owner's budget for new evals out of pocket
PRICE = {"builder25k": 63.0, "builder50k": 91.8, "rapid25": 97.2, "rapid50": 165.0}   # CLUB prices (owner's real prices)
SPLIT = 0.8                       # Builder: you keep 80%
TAX = 0.3                         # the tax pot on every payout
ASK25 = 1000.0                    # funded 25K: ask the full $1,000 at balance $27,100 (payout-policy-funded25-2026-11-17.md)

# This week. The lead edits this list (dates ET; "done": True once the owner did it). "status" is worked out from the date.
WEEK = [
    {"date": "2026-11-18", "what": "Finish MFFU's address check: upload a recent bank statement PDF (your name + address on it)",
     "why": "So the funded 25K's first payout is not blocked when it is ready (~late Dec).", "done": False},
    {"date": "2026-11-18", "what": "Leave the PC and NinjaTrader on every weekday",
     "why": "The bot trades 02:00-15:55 ET by itself and is flat by 15:55. Nothing to click.", "done": False, "every": "every weekday"},
    {"date": "2026-11-20", "what": "Buy the Rapid EOD 25K ($97.20 with CLUB) from your own money, then add it to the bot",
     "why": "One line on the PC, added OFF until you arm it: python -X utf8 -m engine.accounts add --plan rapideod25 --name \"NAME\" "
            "(or ADD_ACCOUNT.bat once its menu lists it). Leaves $52.80 of your $150.", "done": False, "id": "buy_r25"},
    {"date": "2026-11-19", "what": "Add Cloudflare Pages (free, 3 steps in docs/HOSTING.md)",
     "why": "Removes the Netlify badge and allows 15 dashboard updates a day instead of ~18 a month.", "done": False},
    {"date": "2026-11-20", "what": "Friday after 16:10 ET: 5-minute check on My Accounts (payout coach)",
     "why": "If the PC is silent, type the MFFU balances in, so the plan stays true.", "done": False},
    {"date": "2026-11-26", "what": "Thanksgiving Thu Nov 26 + early close Fri Nov 27 (13:15 ET): nothing to do",
     "why": "The bot stops new trades 15 min before and is flat 5 min before each early close (tested).", "done": False, "auto": True},
]

RULES = [
    ["Don't trade the accounts by hand",
     "The bot sizes every trade to the room left. A hand trade can break the max loss or the best-day rule and end the account. "
     "To stop, use STOP BOT."],
    ["The 7-day rule",
     "No trade for 7 calendar days and MFFU can close the account; on a funded account all its profit is lost. The bot pushes "
     "\"no trade for 5 days\". Then (and only then) place 1 MNQ in and out by hand. Watch holiday weeks."],
    ["30% of every payout to the tax pot",
     "The day a payout lands, move 30% to a separate savings account. Next federal estimated tax payment: Jan 15, 2027."],
    ["ZEUS changes: you say yes first",
     "Claude never changes how ZEUS trades (ZEUS Lab) without asking you. A pause / flatten button for the phone is coming."],
]


def _load(path, default=None):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default if default is not None else {}


def sessions(n: int, start: str) -> list:
    """n CME sessions from start (weekdays, full closures skipped), via tools/money/payout_plan.calendar."""
    try:
        import payout_plan as PP
        return PP.calendar(n, start)
    except Exception:  # noqa: BLE001
        out, d = [], dt.date.fromisoformat(start)
        while len(out) < n:
            if d.weekday() < 5 and d.strftime("%m-%d") not in ("12-25", "01-01"):
                out.append(d.isoformat())
            d += dt.timedelta(days=1)
        return out


def after(day: str, n: int) -> str:
    """The session n sessions after day (day itself = 0)."""
    nxt = (dt.date.fromisoformat(day) + dt.timedelta(days=1)).isoformat()
    return sessions(max(1, n), nxt)[max(1, n) - 1]


MN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def when(day: str, approx: bool = True) -> str:
    d = dt.date.fromisoformat(day)
    return ("~" if approx else "") + f"{MN[d.month - 1]} {d.day}"


def usd(v) -> str:
    v = float(v)
    body = f"{abs(v):,.2f}" if abs(v - round(v)) >= 0.005 else f"{abs(round(v)):,}"
    return ("-$" if v < 0 else "$") + body


def board_rows(offline: bool) -> tuple:
    """(accounts by key, pc dict) from tools/board.py gather; the plan rows when the board cannot be read."""
    try:
        import board as BD
        try:
            b = BD.gather(offline=offline)
        except Exception:  # noqa: BLE001
            b = BD.gather(offline=True)
        return {r.get("key"): r for r in b.get("accounts") or [] if isinstance(r, dict)}, b.get("pc") or {}
    except Exception:  # noqa: BLE001
        return {}, {}


def stage(row: dict) -> str:
    s = str(row.get("chip") or row.get("stage") or "").lower()
    return s


def build(offline: bool = False, today: str | None = None, fleet=None, r25=None, acc=None, rows=None, pc=None) -> dict:
    today = today or dt.date.today().isoformat()
    fleet = fleet if fleet is not None else _load(FLEET)
    r25 = r25 if r25 is not None else _load(RAPID25)
    acc = acc if acc is not None else _load(ACCOUNTS)
    if rows is None:
        rows, pc = board_rows(offline)
    pc = pc or {}
    A = fleet["rows"][MKT]["accounts"]
    plan_by = {a.get("key"): a for a in acc.get("accounts") or []}

    def is_(key, *words):
        r = rows.get(key) or {}
        p = plan_by.get(key) or {}
        txt = " ".join([stage(r), str(p.get("stage") or "").lower()])
        return any(w in txt for w in words)

    rp = (r25.get("rows") or {})
    r25k = rp.get("25K, keep $500", {}).get(MKT, {})
    r50k = rp.get("50K, keep $1,000 (live preset)", {}).get(MKT, {})
    pass25 = int((r25k.get("eval") or {}).get("pass_med") or 25)
    pass50 = int((r50k.get("eval") or {}).get("pass_med") or 21)
    m25 = float((r25k.get("funded") or {}).get("per_month") or 0)

    n25_pass = A["N25"]["funded_med"]
    z50_pass = A["Z50"]["funded_med"]
    a25_pay = A["A25"]["first_pay_med"]
    z50_pay = A["Z50"]["first_pay_med"]
    wk = next((w for w in WEEK if w.get("id") == "buy_r25"), None)
    buy_r25 = wk["date"] if wk else after(n25_pass, 1)  # owner 2026-11-18: buy it THIS WEEK from his own money
    buy_r50 = after(a25_pay, 1)                        # the session after the first payout lands
    r25_pass = after(buy_r25, pass25)
    r50_pass = after(buy_r50, pass50)
    all5 = max(fleet["rows"][MKT]["fill5"]["all5_med"], r25_pass, r50_pass)
    keep = ASK25 * SPLIT * (1 - TAX)

    four = fleet["rows"][MKT]["fleet"]["four"]["months"]
    spring = [m for m in four if m["month"] in ("2027-03", "2027-04")]
    sp_net = sum(m["net_mean"] for m in spring) / max(1, len(spring)) + m25 * (1 - TAX)
    sp_cash = sum(m["cash_mean"] for m in spring) / max(1, len(spring)) + m25

    atlas = plan_by.get("atlas") or {}
    payouts_n = int(((atlas.get("funded") or {}).get("payouts_n")) or 0)
    has_plan = lambda word: any(word in str(a.get("plan") or "").lower() and a.get("status") == "live" for a in acc.get("accounts") or [])  # noqa: E731

    L = [
        {"id": "atlas_funded", "date": "2026-11-17", "what": "ATLAS passed the Builder 25K: now funded",
         "detail": "Passed at $26,946.10 (target $26,500). It trades the funded 25K by itself.",
         "done": is_("atlas", "passed", "funded")},
        {"id": "z25_pass", "date": n25_pass, "what": "Zlarior 25K #2 passes",
         "detail": "Needs +$1,500 with at most $1,000 lost. Then it gets funded (a 2nd funded 25K).",
         "done": is_("fresh25", "passed", "funded")},
        {"id": "buy_r25", "date": buy_r25, "what": f"Buy the Rapid EOD 25K ({usd(PRICE['rapid25'])} with CLUB)",
         "detail": f"This week, from your own {usd(BUDGET)} budget (leaves {usd(BUDGET - PRICE['rapid25'])}). Zlarior + ATLAS trade it from "
                   f"day one. Add it with: engine.accounts add --plan rapideod25 (it is added OFF).",
         "usd": -PRICE["rapid25"], "done": has_plan("rapid eod 25k")},
        {"id": "z50_pass", "date": z50_pass, "what": "Zlarior 50K passes",
         "detail": f"Needs about $3,807 more with only ~$1,025 of room, so it may take one re-buy ({usd(PRICE['builder50k'])}).",
         "done": is_("zlarior", "passed", "funded")},
        {"id": "pay1", "date": a25_pay, "what": "First payout: ATLAS's funded 25K",
         "detail": f"Ask the full {usd(ASK25)} when the balance is $27,100. You get {usd(ASK25 * SPLIT)} (80%), "
                   f"{usd(ASK25 * SPLIT * TAX)} to the tax pot, {usd(keep)} to keep.", "usd": keep, "done": payouts_n > 0},
        {"id": "buy_r50", "date": buy_r50, "what": f"Buy the Rapid EOD 50K ({usd(PRICE['rapid50'])} with CLUB), paid from that payout",
         "detail": f"The {usd(keep)} you keep covers it. The 50K makes about 3x the 25K a month.",
         "usd": -PRICE["rapid50"], "done": has_plan("rapid eod 50k")},
        {"id": "r25_pass", "date": r25_pass, "what": "Rapid EOD 25K passes",
         "detail": f"About {pass25} trading days after you buy it. Payouts then come daily (you keep 90%).", "done": False},
        {"id": "z50_pay", "date": z50_pay, "what": "First payout: Zlarior's funded 50K",
         "detail": f"Middle case; half the time between {when(A['Z50']['first_pay_p25'])} and {when(A['Z50']['first_pay_p75'])}.",
         "done": False},
        {"id": "r50_pass", "date": r50_pass, "what": "Rapid EOD 50K passes",
         "detail": f"About {pass50} trading days after you buy it.", "done": False},
        {"id": "all5", "date": all5, "what": "All 5 funded slots full",
         "detail": "MFFU's limit: 1 Builder 50K + 2 Builder 25K + Rapids, 5 funded in all. Nothing more to buy, only re-buys.",
         "done": False},
        {"id": "spring", "date": "2027-03-01", "what": f"About {usd(round(sp_net, -2))} a month to you by spring",
         "detail": f"Mar-Apr average after fees, splits and the 30% tax pot (about {usd(round(sp_cash, -2))} before the tax pot).",
         "usd": round(sp_net, -2), "done": False},
    ]
    L.sort(key=lambda m: (m["date"], m["id"] != "spring"))
    nxt = False
    for m in L:
        m["when"] = when(m["date"], approx=not m["done"])
        if m.pop("done"):
            m["status"] = "done"
        elif not nxt:
            m["status"], nxt = "next", True
        else:
            m["status"] = "later"

    week = []
    t0 = dt.date.fromisoformat(today)
    sunday = (t0 + dt.timedelta(days=6 - t0.weekday())).isoformat()      # "this week" = up to this Sunday
    for w in sorted(WEEK, key=lambda w: (w["date"], not w.get("every"))):
        st = "done" if w.get("done") else ("next" if w["date"] <= sunday or w.get("every") else "later")
        week.append({"date": w["date"], "when": w.get("every") or when(w["date"], approx=False), "what": w["what"], "why": w["why"],
                     "status": st, **({"auto": True} if w.get("auto") else {})})

    ref = fleet["rows"][BAD]["fleet"]["five"]
    bad = (f"If the market is like 2021-25 (the bots had no edge): about {usd(round(ref['total_net_mean'], -2))} in 6 months, "
           f"{round(ref['p_no_pay_6m'])} in 100 get no payout at all. Keep up to {usd(round(ref['pocket_p95'], -2))} ready for re-buys.")

    now = []
    for key in ("zlarior", "fresh25", "atlas"):
        r = rows.get(key) or {}
        p = plan_by.get(key) or {}
        if not (r or p):
            continue
        bal = r.get("balance")
        tp = r.get("to_pass")
        txt = (usd(bal) if bal is not None else "balance not reported yet")
        if tp is not None and float(tp) > 0:
            txt += f", {usd(tp)} to pass"
        now.append([str(r.get("name") or p.get("name") or key) + " (" + str(p.get("plan") or r.get("plan") or "").replace("MFFU ", "").replace(" (funded)", "") + ")",
                    txt, stage(r) or str(p.get("stage") or "")])
    pc_txt = "PC: no report seen from the cloud (check the PC)" if pc.get("stale", True) else "PC: reporting"

    return {
        "v": 1, "updated": today, "built_by": "tools/money/goals_build.py",
        "market": fleet.get("markets", {}).get(MKT, "2026 Jul-Oct-like"),
        "note": "Dates are ESTIMATES: the middle of 1,000 runs of a market like Jul-Oct 2026 (Jan-Jun was better, 2021-25 much worse). "
                "Real dates move with real trades; this page is rebuilt when they do.",
        "now": now, "pc": pc_txt,
        "week": week, "ladder": L, "bad_case": bad, "rules": RULES,
        "decisions": [str(x) for x in acc.get("decisions") or []],
        "sources": ["research/lab/fleet_plan.json (" + str(fleet.get("date")) + ")", "research/lab/rapid25.json",
                    "business/accounts.json (" + str(acc.get("updated")) + ")", "tools/board.py gather"],
    }


def write(doc: dict, path: str = OUT) -> str:
    try:
        from tools import site_privacy
        raw = site_privacy.clean_string(json.dumps(doc, ensure_ascii=False, indent=1))
        json.loads(raw)
    except Exception:  # noqa: BLE001
        raw = json.dumps(doc, ensure_ascii=False, indent=1)
    with open(path + ".tmp", "w", encoding="utf-8") as fh:
        fh.write(raw + "\n")
    os.replace(path + ".tmp", path)
    return path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Rebuild business/goals.json (the Goals page).")
    ap.add_argument("--offline", action="store_true", help="no git fetch / ntfy: repo files only")
    ap.add_argument("--print", action="store_true", help="print the JSON, do not write it")
    ap.add_argument("--today", default=None)
    a = ap.parse_args(argv)
    doc = build(offline=a.offline, today=a.today)
    if a.print:
        print(json.dumps(doc, ensure_ascii=False, indent=1))
        return 0
    print("wrote", write(doc))
    for m in doc["ladder"]:
        print(f"  {m['status']:5s} {m['when']:8s} {m['what']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
