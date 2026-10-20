"""The owner's prop-firm business: money in and out, planners and phone reminders. Paper only, no trading logic.

Everything here reads files the owner keeps (no orders, no bot state, no secrets):
  research/business/expenses.csv   the expense log the owner appends to (one row per payment)       -> item 7
  research/business/payouts.csv    the payout log (money that reached the bank)
  research/business/prop_business.xlsx  the Excel tracker; tools/build_business_tracker.py --sync keeps it and the CSVs equal
  research/props/business.json     accounts, settings (goal, tax %, payout habit, planner budget / stagger / ladder)
  research/props/firms.json        prices, discount codes, payout rules as text
  research/business/plan_rates.json  LIT per-plan numbers (eval speed, funded $/month, 6-month life curve) extracted from
                                   research/lit/funded_combo.json (`python tools/business.py rates`), small enough for the cloud

What it builds (tools/hub_data.py and engine/biz_api.py serve it to both dashboards; engine/ops_checks.py pushes the notices):
  1  statement(month)      monthly P&L statement: fees, payouts, net, YTD, the bot's routed trades that month -> PDF / HTML
  2  payout_status()       per funded account: can it request a payout now (MFFU buffer $2,100 + the $1,500 habit, other
                           firms' rules from the study) -> push when it can
  3  tax_year(year)        fees, payouts, net, quarters, set-aside estimate -> CSV. Not tax advice.
  4  planner()             when to buy the next eval (5 sessions after the last start, inside the cash budget), the
                           owner's price and the codes to try (verify at checkout) -> push when it is time
  5  calendar()            month-by-month funded scaling plan (lit-funded-combo.md order), expected $ at the Jul-Oct (H2)
                           rate and the downside case (2021-25 trades)
  6  goal()                Z06 savings: goal (setting), saved from payouts, months to go at the H2 and a conservative rate
  8  roi()                 per account / firm: fees in, payouts out, net, ROI, days to the first payout

  python tools/business.py view                     everything as JSON (what the dashboards show)
  python tools/business.py statement [--month 2026-10] [--html]   write research/business/statements/<month>.pdf (or .html)
  python tools/business.py tax [--year 2026]        write research/business/tax_<year>.csv
  python tools/business.py add-expense --usd 115.40 --firm "Lucid Trading" --account lucid_50k --type "Eval purchase"
                                       --desc "LucidPro 50K eval" [--date 2026-10-28] [--code DGT]
  python tools/business.py add-payout --received 1280 --requested 1600 --firm MyFundedFutures --account mffu_50k
  python tools/business.py notices                  the reminders that would be pushed now (prints, never sends)
  python tools/business.py rates                    rebuild research/business/plan_rates.json from funded_combo.json

Every $ projection is an estimate from paper backtests (2026 Jul-Oct = H2, the half to quote; 2021-25 = the downside
reference), never a promise. Tax lines are a savings rule, NOT tax advice.
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import json
import math
import os
import re
import sys
import time
from collections import Counter
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
ET = ZoneInfo("America/New_York")
BIZ = os.path.join(ROOT, "research", "business")
PROPS = os.path.join(ROOT, "research", "props")
EXPENSES_CSV = os.path.join(BIZ, "expenses.csv")
PAYOUTS_CSV = os.path.join(BIZ, "payouts.csv")
RATES_PATH = os.path.join(BIZ, "plan_rates.json")
STATEMENTS = os.path.join(BIZ, "statements")
COMBO_PATH = os.path.join(ROOT, "research", "lit", "funded_combo.json")
EXP_COLS = ["date", "firm", "account", "type", "description", "amount_usd", "code", "note"]
PAY_COLS = ["date", "firm", "account", "requested_usd", "received_usd", "method", "note"]
NOT_TAX = "Estimate only - NOT tax advice. A savings rule; ask a tax professional what you really owe."
DISCLAIMER = ("Estimates from paper backtests (LIT 2026; Jul-Oct = H2, the half to quote; 2021-25 = downside reference). "
              "Not a promise, not financial or tax advice. Paper only: nothing here trades.")
VERIFY = "verify at checkout"
# lit-funded-combo.md: the order to buy (only firms whose rules allow the bot); "when" = the condition before the slot opens
DEFAULT_LADDER = [
    {"plan": "mffu_builder_50k", "when": None},
    {"plan": "lucid_pro_50k", "when": "decided:mffu_50k", "why": "after the 50K eval is decided (pass or fail)"},
    {"plan": "fn_rapid_daily_50k", "when": "funded:2|months:2", "why": "once two accounts are funded or by month 2"},
    {"plan": "lucid_pro_50k", "when": None, "why": "from the payouts"},
    {"plan": "lucid_pro_50k", "when": None, "why": "from the payouts"},
    {"plan": "fn_rapid_daily_50k", "when": None, "why": "from the payouts"},
]
# ask for a funded payout only once this much sits above the buffer (lit-money-batch2.md: +$29-32 a month per account on
# MFFU; lit-funded-combo.md: habit on for Lucid, off for FundedNext whose $1,200 cap makes waiting worthless)
DEFAULT_HABIT = {"mffu_builder_50k": 1500, "mffu_builder_25k": 1500, "lucid_pro_50k": 1500, "fn_rapid_daily_50k": 0,
                 "fn_rapid_pro_50k": 0}
FIRM_KEYS = {"mffu": ("mffu", "myfundedfutures", "my funded futures"), "lucid": ("lucid",), "fundednext": ("fundednext", "funded next"),
             "tradeify": ("tradeify",), "bulenox": ("bulenox",), "topstep": ("topstep",)}
FIRM_SHORT = {"mffu": "MFFU", "lucid": "Lucid", "fundednext": "FundedNext", "tradeify": "Tradeify", "bulenox": "Bulenox", "topstep": "Topstep"}


# ================================================================================================ helpers
def _today(now=None) -> dt.date:
    return dt.datetime.fromtimestamp(time.time() if now is None else now, ET).date()


def _f(x, nd=2):
    try:
        v = float(str(x).replace("$", "").replace(",", "").strip()) if isinstance(x, str) else float(x)
        return None if math.isnan(v) else round(v, nd)
    except (TypeError, ValueError):
        return None


def _date(x) -> str:
    if hasattr(x, "strftime"):
        return x.strftime("%Y-%m-%d")
    s = str(x or "").strip()[:10]
    try:
        return dt.date.fromisoformat(s).isoformat()
    except ValueError:
        return s


def _json(path, default=None):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return default


def money(x, d=0) -> str:
    v = _f(x) or 0.0
    return ("-" if v < 0 else "") + f"${abs(v):,.{d}f}"


def firm_key(text) -> str | None:
    t = str(text or "").lower()
    for k, keys in FIRM_KEYS.items():
        if any(x in t for x in keys):
            return k
    return None


def trading_days(a: dt.date, n: int) -> list:
    """The next n CME trading days on/after a (tools/hub_data's calendar; plain weekdays if it cannot load)."""
    try:
        from tools import hub_data
        return hub_data._trading_days(a, n)
    except Exception:
        out, d = [], a
        while len(out) < n:
            if d.weekday() < 5:
                out.append(d)
            d += dt.timedelta(days=1)
        return out


def sessions_after(start: dt.date, n: int) -> dt.date:
    """The date of the session n sessions after the session on/after start (start's own session = 0)."""
    return trading_days(start, n + 1)[-1]


def _add_months(d: dt.date, m: int) -> dt.date:
    y, mo = divmod(d.month - 1 + m, 12)
    return dt.date(d.year + y, mo + 1, 1)


# ================================================================================================ 7. expense / payout logs
def read_csv(path, cols) -> list:
    """Rows of a log CSV (blank rows and rows without a date or an amount skipped). Missing file -> []."""
    if not os.path.exists(path):
        return []
    out = []
    with open(path, encoding="utf-8-sig", newline="") as fh:
        for r in csv.DictReader(fh):
            r = {k.strip().lower(): (v or "").strip() for k, v in r.items() if k}
            if not r.get("date"):
                continue
            out.append({c: r.get(c, "") for c in cols})
    return out


def _ensure_csv(path, cols):
    if not os.path.exists(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="") as fh:
            csv.writer(fh).writerow(cols)


def append_row(path, cols, row: dict) -> dict:
    """Append one row to a log CSV (creates it with its header). Values are cleaned; amounts must be numbers."""
    _ensure_csv(path, cols)
    clean = {c: str(row.get(c, "") if row.get(c) is not None else "").replace("\n", " ").strip() for c in cols}
    clean["date"] = _date(clean["date"] or _today().isoformat())
    for c in cols:
        if c.endswith("_usd") and clean[c]:
            v = _f(clean[c])
            if v is None:
                raise ValueError(f"{c} must be a number, got {clean[c]!r}")
            clean[c] = f"{v:.2f}"
    with open(path, "a", encoding="utf-8", newline="") as fh:
        csv.writer(fh).writerow([clean[c] for c in cols])
    return clean


def expense_rows(path=EXPENSES_CSV) -> list:
    out = []
    for r in read_csv(path, EXP_COLS):
        v = _f(r["amount_usd"])
        if v is None:
            continue
        out.append({"date": _date(r["date"]), "item": r["description"] or r["account"] or r["firm"] or "fee", "usd": v,
                    "kind": (r["type"].lower().split() or [None])[0], "firm": r["firm"] or None, "account": r["account"] or None,
                    "code": r["code"] or None, "src": "expenses.csv"})
    return out


def payout_rows(path=PAYOUTS_CSV) -> list:
    out = []
    for r in read_csv(path, PAY_COLS):
        v = _f(r["received_usd"])
        if v is None:
            continue
        out.append({"date": _date(r["date"]), "item": r["account"] or r["firm"] or "payout", "usd": v,
                    "requested": _f(r["requested_usd"]), "firm": r["firm"] or None, "account": r["account"] or None,
                    "src": "payouts.csv"})
    return out


def _key(r) -> tuple:
    return (_date(r.get("date")), round(float(r.get("usd") or 0), 2))


def union(base: list, extra: list) -> list:
    """base + the rows of extra that base does not hold yet, counted by (date, amount): the same payment typed in the CSV and
    in the Excel tracker counts once; two equal payments on one day count twice if either list has both."""
    have = Counter(_key(r) for r in base)
    out = list(base)
    for r in extra:
        k = _key(r)
        if have[k] > 0:
            have[k] -= 1
        else:
            out.append(r)
    return out


def merge_logs(b: dict, exp_path=EXPENSES_CSV, pay_path=PAYOUTS_CSV) -> dict:
    """business.json / the tracker's expenses + payouts, merged with the CSV logs (the log of record once it has rows).
    When the CSV has rows, business.json's own (non-planned) expense rows are dropped unless the Excel tracker supplied
    them: business.json keeps only the first eval as a seed and the CSV starts from that same payment."""
    b = dict(b or {})
    ex_csv, po_csv = expense_rows(exp_path), payout_rows(pay_path)
    from_xlsx = str(b.get("source") or "").endswith(".xlsx")
    cur = [e for e in b.get("expenses") or [] if not e.get("planned")]
    planned = [e for e in b.get("expenses") or [] if e.get("planned")]
    if ex_csv:
        base = cur if from_xlsx else []
        b["expenses"] = union(base, ex_csv) + planned
    if po_csv:
        base = list(b.get("payouts") or []) if from_xlsx else []
        b["payouts"] = union(base, po_csv)
    b["logs"] = {"expenses_csv": os.path.relpath(exp_path, ROOT).replace("\\", "/"), "expenses_rows": len(ex_csv),
                 "payouts_csv": os.path.relpath(pay_path, ROOT).replace("\\", "/"), "payouts_rows": len(po_csv)}
    return b


def business(b: dict | None = None) -> dict:
    """The owner's business data, merged (tools/hub_data.business_raw does the xlsx + CSV merge)."""
    if b is not None:
        return b
    try:
        from tools import hub_data
        return hub_data.business_raw()
    except Exception:
        return merge_logs(_json(os.path.join(PROPS, "business.json"), {}) or {})


def paid(b) -> list:
    return [e for e in b.get("expenses") or [] if not e.get("planned")]


def settings(b) -> dict:
    tax = b.get("tax") or {}
    wd = b.get("withdraw") or {}
    pl = b.get("planner") or {}
    g = b.get("goal") or {}
    return {"tax_pct": float(tax.get("set_aside_pct") or 30), "keep_pct": float(wd.get("keep_pct") or 50),
            "budget": float(pl.get("budget_usd") if pl.get("budget_usd") is not None else 300),
            "stagger": int(pl.get("stagger_sessions") or 5), "variant": pl.get("variant") or "t15_be_off",
            "ladder": pl.get("ladder") or DEFAULT_LADDER, "habit": {**DEFAULT_HABIT, **(b.get("payout_habit") or {})},
            "goal_name": g.get("name") or "Corvette Z06", "goal_usd": float(g.get("usd") or 115000),
            "goal_saved_extra": float(g.get("saved_extra_usd") or 0), "conservative": g.get("conservative_rate") or "builder_alone"}


# ================================================================================================ plan rates (LIT study)
def build_rates(combo_path=COMBO_PATH) -> dict:
    """The few numbers of research/lit/funded_combo.json the planners need, per variant (t15_be_off = live now, scale-in off;
    all3 = with scale-in after the owner's Sim check)."""
    d = _json(combo_path, {}) or {}
    out = {"built": dt.datetime.now(ET).strftime("%Y-%m-%d %H:%M ET"), "from": "research/lit/funded_combo.json",
           "study_built": d.get("built"), "writeup": d.get("writeup") or "research/writeups/lit-funded-combo.md",
           "how": "per plan: eval pass median sessions, funded $/month, first payout sessions after funding, 6-month life "
                  "(net of every fee, re-buys included) per span. H2 = Jul-Oct 2026 (quote it), 2021-25 = downside reference.",
           "variants": {}}
    for v in ("t15_be_off", "all3"):
        x = d.get(v) or {}
        plans = {}
        for p in x.get("plans") or []:
            r = p.get("results") or {}
            spans = {}
            for h in ("H1", "H2", "2021-25"):
                e, fu, li = (r.get("eval") or {}).get(h) or {}, (r.get("funded") or {}).get(h) or {}, (r.get("life") or {}).get(h) or {}
                spans[h] = {"pass_med": e.get("pass_med"), "p10": e.get("p10"), "f10": e.get("f10"), "p60": e.get("p60"),
                            "funded_month": fu.get("per_month"), "first_pay": fu.get("first_med"), "lost_6m": fu.get("loss_6m"),
                            "net_month": li.get("net_per_month"), "m46": li.get("months4_6_per_month"), "neg_6m": li.get("neg_6m")}
            plans[p["id"]] = {"firm": p.get("firm"), "plan": p.get("plan"), "price": p.get("price"), "list": p.get("list_price"),
                              "target": p.get("target"), "mll": p.get("mll"), "dll": p.get("dll"), "eligible": p.get("eligible"),
                              "funded": p.get("funded"), "spans": spans}
        stacks = [{"stack": s.get("stack"), "span": s.get("span"), "accounts": s.get("accounts"), "net_month": s.get("net_per_month"),
                   "m46": s.get("months4_6_per_month"), "neg_6m": s.get("neg_6m"), "p10_6m": s.get("net_p10_6m"),
                   "all_zero_m46": s.get("all_zero_m46"), "cash": s.get("cash_up_front")} for s in x.get("stacks") or []]
        out["variants"][v] = {"plans": plans, "stacks": stacks}
    return out


def rates() -> dict:
    r = _json(RATES_PATH, None)
    if not r or not r.get("variants"):
        r = build_rates()
    return r


def plan_rate(pid, variant="t15_be_off", R=None) -> dict:
    R = R or rates()
    return (((R.get("variants") or {}).get(variant) or {}).get("plans") or {}).get(pid) or {}


def stack_rate(name, span="H2", variant="t15_be_off", R=None) -> dict:
    R = R or rates()
    for s in ((R.get("variants") or {}).get(variant) or {}).get("stacks") or []:
        if s.get("stack") == name and s.get("span") == span:
            return s
    return {}


# ================================================================================================ firms.json lookups
def firms() -> dict:
    return _json(os.path.join(PROPS, "firms.json"), {}) or {}


def find_plan(pid, F=None):
    F = F or firms()
    for f in F.get("firms") or []:
        for p in f.get("plans") or []:
            if p.get("id") == pid:
                return f, p
    return None, None


def plan_price(pid, F=None, R=None) -> dict:
    """The owner's price (MFFU: what he paid with his code), else the study's price with a code, else the list price."""
    f, p = find_plan(pid, F)
    pr = (p or {}).get("price") if isinstance((p or {}).get("price"), dict) else {}
    lst = pr.get("list")
    lst = lst.get("v") if isinstance(lst, dict) else lst
    owner = pr.get("owner")
    code = pr.get("with_code")
    rr = plan_rate(pid, R=R)
    usd = owner if isinstance(owner, (int, float)) else code if isinstance(code, (int, float)) else rr.get("price") or lst
    basis = "your price with your code" if isinstance(owner, (int, float)) else "with a code (study price)" if isinstance(code, (int, float)) else "list price"
    name = f"{FIRM_SHORT.get((f or {}).get('id'), (f or {}).get('name') or '')} {(p or {}).get('name') or pid}".strip()
    return {"plan": pid, "name": name, "usd": _f(usd), "list": _f(lst), "basis": basis, "firm": (f or {}).get("id")}


def codes_for(firm_id, F=None, watch=None, n=4) -> list:
    """Codes to try for a firm: the study's (firms.json) and new ones from the code watcher, all 'verify at checkout'."""
    F = F or firms()
    out = []
    for f in F.get("firms") or []:
        if f.get("id") != firm_id:
            continue
        for c in f.get("codes") or []:
            if c.get("code") and "expired" not in str(c.get("seen") or "").lower():
                out.append({"code": c["code"], "off": c.get("off"), "seen": c.get("seen"), "st": c.get("st") or "unconfirmed", "from": "study"})
    w = watch if watch is not None else (_json(os.path.join(PROPS, "code_watch.json"), {}) or {})
    have = {str(c["code"]).upper() for c in out}
    for c in w.get("codes") or []:
        if c.get("firm") == firm_id and str(c.get("code", "")).upper() not in have:
            out.append({"code": c["code"], "off": c.get("off"), "seen": c.get("seen"), "st": "unverified", "from": "code watcher"})
    return out[:n]


# ================================================================================================ accounts + matching
def accounts(b) -> list:
    return [a for a in b.get("accounts") or [] if a.get("id")]


def plan_size(pid) -> float:
    m = re.search(r"(\d+)k", str(pid or "").lower())
    return float(m.group(1)) * 1000 if m else 50000.0


def _plan_words(a) -> str:
    return re.sub(r"\s+", " ", str(a.get("plan") or "").lower()).strip()


def match_account(row, accts) -> str | None:
    """Which account a fee / payout row belongs to: its account field (id, name or alias), else firm + plan words in the row."""
    acc = str(row.get("account") or "").strip().lower()
    for a in accts:
        names = {str(a.get("id")).lower(), str(a.get("name") or "").lower(), *[str(x).lower() for x in a.get("aliases") or []]}
        if acc and acc in names:
            return a["id"]
    text = " ".join(str(row.get(k) or "") for k in ("item", "account", "firm", "description")).lower()
    fk = firm_key(text)
    cands = [a for a in accts if firm_key(a.get("firm")) == fk and _plan_words(a) and _plan_words(a) in text]
    if not cands and fk:
        cands = [a for a in accts if firm_key(a.get("firm")) == fk and str(plan_size(a.get("lit_id")))[:2] in re.sub(r"[^0-9]", "", text)]
    return cands[0]["id"] if cands else None


# ================================================================================================ 8. ROI per account / firm
def roi(b=None, now=None) -> dict:
    b = business(b)
    accts = accounts(b)
    today = _today(now)
    per = {a["id"]: {"id": a["id"], "firm": a.get("firm"), "plan": a.get("plan"), "stage": a.get("stage"), "start": a.get("start"),
                     "fees": 0.0, "payouts": 0.0, "n_fees": 0, "n_payouts": 0, "first_payout": None} for a in accts}
    un = {"id": "unassigned", "firm": None, "plan": None, "stage": None, "start": None, "fees": 0.0, "payouts": 0.0, "n_fees": 0,
          "n_payouts": 0, "first_payout": None}
    for e in paid(b):
        r = per.get(match_account(e, accts)) or un
        r["fees"] += float(e.get("usd") or 0)
        r["n_fees"] += 1
        if r is un and not un["firm"]:
            un["firm"] = e.get("firm")
    for p in b.get("payouts") or []:
        r = per.get(match_account(p, accts)) or un
        r["payouts"] += float(p.get("usd") or 0)
        r["n_payouts"] += 1
        d = _date(p.get("date"))
        r["first_payout"] = min(r["first_payout"] or d, d)
    rows = list(per.values()) + ([un] if un["n_fees"] or un["n_payouts"] else [])
    for r in rows:
        r["fees"], r["payouts"] = round(r["fees"], 2), round(r["payouts"], 2)
        r["net"] = round(r["payouts"] - r["fees"], 2)
        r["roi_pct"] = round(100 * r["net"] / r["fees"], 1) if r["fees"] else None
        st = r.get("start")
        r["days_open"] = (today - dt.date.fromisoformat(st)).days if st and st <= today.isoformat() else None
        r["days_to_first_payout"] = (dt.date.fromisoformat(r["first_payout"]) - dt.date.fromisoformat(st)).days if r["first_payout"] and st else None
    firms_ = {}
    for r in rows:
        k = firm_key(r.get("firm")) or "other"
        f = firms_.setdefault(k, {"firm": FIRM_SHORT.get(k, k), "accounts": 0, "fees": 0.0, "payouts": 0.0, "first_payout_days": None})
        f["accounts"] += 1 if r["id"] != "unassigned" else 0
        f["fees"] += r["fees"]
        f["payouts"] += r["payouts"]
        if r["days_to_first_payout"] is not None:
            f["first_payout_days"] = min(f["first_payout_days"] or 10 ** 6, r["days_to_first_payout"])
    frows = []
    for f in firms_.values():
        f["fees"], f["payouts"] = round(f["fees"], 2), round(f["payouts"], 2)
        f["net"] = round(f["payouts"] - f["fees"], 2)
        f["roi_pct"] = round(100 * f["net"] / f["fees"], 1) if f["fees"] else None
        frows.append(f)
    tot_f, tot_p = sum(r["fees"] for r in rows), sum(r["payouts"] for r in rows)
    return {"accounts": rows, "firms": sorted(frows, key=lambda x: -x["fees"]),
            "total": {"fees": round(tot_f, 2), "payouts": round(tot_p, 2), "net": round(tot_p - tot_f, 2),
                      "roi_pct": round(100 * (tot_p - tot_f) / tot_f, 1) if tot_f else None},
            "how": "fees and payouts matched to an account by the log's account column (id, name or alias in business.json), "
                   "else by firm + plan words; ROI = (payouts - fees) / fees. Planned purchases are not counted."}


# ================================================================================================ 3. tax year
def tax_year(year=None, b=None, now=None) -> dict:
    b = business(b)
    s = settings(b)
    year = int(year or _today(now).year)
    rows = []
    for e in paid(b):
        if _date(e.get("date"))[:4] == str(year):
            rows.append({"date": _date(e["date"]), "type": "fee", "firm": e.get("firm") or "", "account": e.get("account") or "",
                         "description": e.get("item") or "", "amount_usd": -round(float(e.get("usd") or 0), 2)})
    for p in b.get("payouts") or []:
        if _date(p.get("date"))[:4] == str(year):
            rows.append({"date": _date(p["date"]), "type": "payout", "firm": p.get("firm") or "", "account": p.get("account") or "",
                         "description": p.get("item") or "payout", "amount_usd": round(float(p.get("usd") or 0), 2)})
    rows.sort(key=lambda r: (r["date"], r["type"]))
    fees = round(-sum(r["amount_usd"] for r in rows if r["type"] == "fee"), 2)
    pays = round(sum(r["amount_usd"] for r in rows if r["type"] == "payout"), 2)
    net = round(pays - fees, 2)
    q = []
    for i in range(4):
        m0, m1 = 3 * i + 1, 3 * i + 3
        qr = [r for r in rows if m0 <= int(r["date"][5:7]) <= m1]
        qf = -sum(r["amount_usd"] for r in qr if r["type"] == "fee")
        qp = sum(r["amount_usd"] for r in qr if r["type"] == "payout")
        q.append({"q": f"Q{i + 1}", "fees": round(qf, 2), "payouts": round(qp, 2), "net": round(qp - qf, 2),
                  "set_aside": round(max(0.0, qp - qf) * s["tax_pct"] / 100, 2)})
    return {"year": year, "rows": rows, "fees": fees, "payouts": pays, "net": net, "pct": s["tax_pct"],
            "set_aside": round(max(0.0, net) * s["tax_pct"] / 100, 2), "set_aside_on_payouts": round(pays * s["tax_pct"] / 100, 2),
            "quarters": q, "label": NOT_TAX,
            "note": "Prop-firm payouts are usually reported as contractor income (1099); eval fees may be business expenses. "
                    "Which applies to you is a question for a tax professional."}


def tax_csv(t: dict) -> str:
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([f"Prop business tax-year summary {t['year']} - {NOT_TAX}"])
    w.writerow(["date", "type", "firm", "account", "description", "amount_usd"])
    for r in t["rows"]:
        w.writerow([r["date"], r["type"], r["firm"], r["account"], r["description"], f"{r['amount_usd']:.2f}"])
    w.writerow([])
    w.writerow(["summary", "", "", "", "total fees (paid out)", f"{t['fees']:.2f}"])
    w.writerow(["summary", "", "", "", "total payouts received", f"{t['payouts']:.2f}"])
    w.writerow(["summary", "", "", "", "net (payouts - fees)", f"{t['net']:.2f}"])
    w.writerow(["summary", "", "", "", f"set-aside estimate at {t['pct']:g}% of positive net (not tax advice)", f"{t['set_aside']:.2f}"])
    for qq in t["quarters"]:
        w.writerow(["quarter", qq["q"], "", "", f"fees {qq['fees']:.2f} / payouts {qq['payouts']:.2f}", f"{qq['net']:.2f}"])
    return buf.getvalue()


def write_tax_csv(year=None, b=None, out_dir=BIZ, now=None) -> str:
    t = tax_year(year, b, now)
    path = os.path.join(out_dir, f"tax_{t['year']}.csv")
    os.makedirs(out_dir, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(tax_csv(t))
    return path


# ================================================================================================ 2. payout eligibility
def payout_rules(pid, R=None, F=None) -> dict:
    """Numeric payout rules of a plan (the study's funded block, research/lit/funded_combo.json via plan_rates.json; MFFU
    Builder from research/lit/mffu_rules.json when it is here) + the firms.json text facts to show next to them."""
    fu = dict(plan_rate(pid, R=R).get("funded") or {})
    lim = ((_json(os.path.join(ROOT, "research", "lit", "mffu_rules.json"), {}) or {}).get("limits") or {})
    lk = {"mffu_builder_50k": "builder_50k", "mffu_builder_25k": "builder_25k"}.get(pid)
    if lk and lim.get(lk):
        L = lim[lk]
        fu.update({k: L[k2] for k, k2 in (("buffer", "buffer"), ("pay_min", "pay_min"), ("pay_max", "pay_max"), ("split", "split"),
                                          ("cons", "cons")) if L.get(k2) is not None})
    pm = fu.get("pay_max")
    _, p = find_plan(pid, F)
    text = {k: (v.get("v") if isinstance(v, dict) else v) for k, v in ((p or {}).get("payouts") or {}).items()}
    return {"buffer": _f(fu.get("buffer")), "pay_min": _f(fu.get("pay_min")), "pay_max": _f(pm[0] if isinstance(pm, list) else pm),
            "split": _f(fu.get("split"), 3), "cons": _f(fu.get("cons"), 3), "cycle_min": _f(fu.get("cyc_min")),
            "days": fu.get("days"), "first_wait_days": fu.get("first_wait"), "max_payouts": fu.get("max_payouts"), "text": text,
            "known": bool(fu)}


def payout_status(b=None, now=None, pc_eval=None, R=None, F=None) -> dict:
    """Per account: can it ask for a payout now? Funded accounts need their balance: business.json accounts[].balance (and
    optionally best_day / cycle_profit / payouts_n), or the PC bot's own balance for the account marked "pc_bot": true."""
    b = business(b)
    s = settings(b)
    R = R or rates()
    today = _today(now)
    rows = []
    for a in accounts(b):
        pid = a.get("lit_id")
        ru = payout_rules(pid, R, F)
        size = plan_size(pid)
        habit = float(s["habit"].get(pid, 0) or 0)
        r = {"id": a["id"], "firm": a.get("firm"), "plan": a.get("plan"), "stage": a.get("stage"), "rules": ru, "habit": habit,
             "split": ru.get("split")}
        buf, pmin, pmax = ru.get("buffer") or 0, ru.get("pay_min") or 0, ru.get("pay_max")
        need_min, need_habit = buf + pmin, buf + max(pmin, habit)
        r.update(need_min=need_min, need_habit=need_habit, size=size)
        if a.get("stage") != "funded":
            r.update(status="not_funded", text=f"Pass the eval first. Once funded: ask when profit is ${need_habit:,.0f}+ "
                                               f"(buffer ${buf:,.0f} + ${max(pmin, habit):,.0f}).")
            rows.append(r)
            continue
        bal = _f(a.get("balance"))
        src = "business.json"
        if a.get("pc_bot") and pc_eval and pc_eval.get("balance") is not None:
            bal, src = _f(pc_eval.get("balance")), "the PC bot"
        if bal is None:
            r.update(status="unknown", text="Type the account balance into research/props/business.json (accounts[].balance) "
                                            "so the reminder can check it.")
            rows.append(r)
            continue
        profit = round(bal - size, 2)
        checks = []
        fs = a.get("funded_start")
        if fs and ru.get("first_wait_days"):
            ready_t = dt.date.fromisoformat(fs) + dt.timedelta(days=int(ru["first_wait_days"]))
            checks.append(("wait after the first funded trade", today >= ready_t, f"from {ready_t.isoformat()}"))
        if ru.get("cycle_min") and a.get("cycle_profit") is not None:
            checks.append((f"cycle profit >= ${ru['cycle_min']:,.0f}", float(a["cycle_profit"]) >= ru["cycle_min"], money(a["cycle_profit"])))
        if ru.get("cons") and a.get("best_day") is not None and a.get("cycle_profit"):
            lim = ru["cons"] * float(a["cycle_profit"])
            checks.append((f"best day <= {ru['cons'] * 100:.0f}% of the cycle", float(a["best_day"]) <= lim,
                           f"best {money(a['best_day'])} vs {money(lim)}"))
        if ru.get("max_payouts") and a.get("payouts_n") is not None and int(a["payouts_n"]) >= int(ru["max_payouts"]):
            checks.append(("payouts left", False, f"{a['payouts_n']} of {ru['max_payouts']} used: move to live / new account"))
        bad = [c for c in checks if not c[1]]
        req = max(0.0, profit - buf)
        req = min(req, pmax) if pmax else req
        r.update(balance=bal, balance_src=src, profit=profit, request=round(req, 2), keep=round(req * (ru.get("split") or 1), 2),
                 checks=[{"rule": c[0], "ok": c[1], "now": c[2]} for c in checks], payouts_n=int(a.get("payouts_n") or 0))
        if profit >= need_habit and not bad:
            r.update(status="ready", text=f"Can request now: ask for {money(req)} (you keep ~{money(r['keep'])}). "
                                          f"Profit {money(profit)} >= ${need_habit:,.0f} (buffer + habit).")
        elif profit >= need_min and not bad:
            r.update(status="allowed_wait", text=f"Allowed (profit {money(profit)} >= ${need_min:,.0f}), but the habit says wait "
                                                 f"until ${need_habit:,.0f}: {money(need_habit - profit)} to go.")
        else:
            why = "; ".join(f"{c[0]} ({c[2]})" for c in bad)
            r.update(status="not_yet", text=f"{money(max(0.0, need_habit - profit))} to go to ${need_habit:,.0f} profit" + (f"; {why}" if why else "") + ".")
        rows.append(r)
    return {"rows": rows, "how": "MFFU Builder: $2,100 buffer + $500 minimum, the owner's habit asks only once $1,500+ is above "
                                 "the buffer (lit-money-batch2.md). Other firms: the study's rules (lit-funded-combo.md). Check the "
                                 "firm's dashboard before you click: rules change."}


# ================================================================================================ 4. eval purchase planner
def _eval_decided(a) -> bool:
    return a.get("stage") not in ("eval", "planned", None)


def _cond_ok(cond, b, now, first_start) -> tuple[bool, str]:
    if not cond:
        return True, ""
    today = _today(now)
    acc = {a["id"]: a for a in accounts(b)}
    for part in str(cond).split("|"):
        k, _, v = part.partition(":")
        if k == "decided" and v in acc and _eval_decided(acc[v]):
            return True, ""
        if k == "funded" and sum(1 for a in acc.values() if a.get("stage") == "funded") >= int(v or 1):
            return True, ""
        if k == "months" and first_start and today >= _add_months(first_start, int(v or 1)).replace(day=min(first_start.day, 28)):
            return True, ""
        if k == "date" and today.isoformat() >= v:
            return True, ""
    txt = {"decided": "after the {v} eval is decided", "funded": "once {v} accounts are funded", "months": "or {v} months after the first eval",
           "date": "from {v}"}
    return False, " ".join(txt.get(p.partition(":")[0], p).format(v=p.partition(":")[2]) for p in str(cond).split("|"))


def planner(b=None, now=None, R=None, F=None, watch=None) -> dict:
    """When to buy the next eval: the owner's planned buys first (business.json accounts with stage "planned"), then the
    lit-funded-combo ladder. Rule: start an eval at least `stagger` sessions after the last one started, and only from cash
    (budget - fees paid + payouts received)."""
    b = business(b)
    s = settings(b)
    R, F = R or rates(), F or firms()
    today = _today(now)
    accts = accounts(b)
    starts = sorted(dt.date.fromisoformat(a["start"]) for a in accts if a.get("start") and a.get("stage") != "planned")
    first_start = starts[0] if starts else None
    last = max([dt.date.fromisoformat(a["start"]) for a in accts if a.get("start") and a.get("stage") != "planned"] or [today])
    fees = sum(float(e.get("usd") or 0) for e in paid(b))
    pays = sum(float(p.get("usd") or 0) for p in b.get("payouts") or [])
    cash = round(s["budget"] - fees + pays, 2)
    steps, reserve = [], 0.0
    earliest = sessions_after(last, s["stagger"])
    # 1. the owner's own planned buys
    for a in sorted([a for a in accts if a.get("stage") == "planned"], key=lambda a: a.get("start") or "9999"):
        pr = plan_price(a.get("lit_id"), F, R)
        day = max(dt.date.fromisoformat(a["start"]) if a.get("start") else earliest, earliest)
        left = round(cash - reserve, 2)
        due = today >= day and left >= (pr["usd"] or 0)
        steps.append({"slot": f"planned:{a['id']}", "plan": a.get("lit_id"), "name": pr["name"], "price": pr["usd"], "price_basis": pr["basis"],
                      "list": pr["list"], "date": day.isoformat(), "due": due, "why": a.get("why") or "your planned buy",
                      "cash_left": left, "codes": codes_for(pr["firm"], F, watch), "verify": VERIFY, "planned": True,
                      "wait": None if due else (f"from {day.isoformat()}" if today < day else f"cash {money(left)} < {money(pr['usd'])}")})
        reserve += pr["usd"] or 0
        earliest = sessions_after(day, s["stagger"])
    # 2. the ladder: slots not yet held / planned
    held = Counter(a.get("lit_id") for a in accts if a.get("stage") not in ("closed",))
    for i, step in enumerate(s["ladder"]):
        pid = step.get("plan")
        if held[pid] > 0:
            held[pid] -= 1
            continue
        pr = plan_price(pid, F, R)
        ok, why_not = _cond_ok(step.get("when"), b, now, first_start)
        left = round(cash - reserve, 2)
        day = earliest
        due = ok and today >= day and left >= (pr["usd"] or 0)
        wait = None
        if not due:
            wait = why_not if not ok else (f"from {day.isoformat()} ({s['stagger']} sessions after the last start)" if today < day
                                           else f"cash {money(left)} < {money(pr['usd'])}: from payouts")
        h2 = (plan_rate(pid, s["variant"], R).get("spans") or {}).get("H2") or {}
        steps.append({"slot": f"ladder:{i}", "plan": pid, "name": pr["name"], "price": pr["usd"], "price_basis": pr["basis"], "list": pr["list"],
                      "date": day.isoformat(), "due": due, "why": step.get("why") or "", "cash_left": left, "wait": wait,
                      "codes": codes_for(pr["firm"], F, watch), "verify": VERIFY, "h2_month": h2.get("net_month"),
                      "eligible": plan_rate(pid, s["variant"], R).get("eligible")})
        reserve += pr["usd"] or 0
        earliest = sessions_after(day, s["stagger"])
    nxt = next((x for x in steps), None)
    return {"budget": s["budget"], "fees_paid": round(fees, 2), "payouts": round(pays, 2), "cash": cash, "stagger": s["stagger"],
            "last_start": last.isoformat(), "next": nxt, "steps": steps[:8],
            "rule": f"buy the next eval {s['stagger']} sessions after the last one started (the evals decouple), only from cash "
                    "(budget - fees + payouts); order from lit-funded-combo.md. Prices: your real price when known; codes change "
                    "weekly: verify at checkout.",
            "warn": "Two or more accounts at once: the PC bot can route each signal to several accounts (engine/multi_account.py, "
                    "data/accounts.json), OFF by default; switch it on only after a Sim check. Ask each firm in writing first."}


# ================================================================================================ 5. funded scaling calendar
def _life_curve(pid, span, variant, R, months=24) -> list:
    """Expected net $ per month of one account from the month it is bought: month 1 = the fee; the rest of the study's
    months 1-3 lands from the month of the median first payout (eval median pass + median first payout after funding,
    21 sessions a month; month 2 or 3); months 4+ = the study's months 4-6 rate (6-month life net of every fee, re-buys
    included). Months 1-3 add up to the study's own months 1-3 total."""
    sp = (plan_rate(pid, variant, R).get("spans") or {}).get(span) or {}
    net, m46 = sp.get("net_month"), sp.get("m46")
    price = plan_rate(pid, variant, R).get("price") or 0
    if net is None or m46 is None:
        return [0.0] * months
    m13 = 2 * net - m46                                        # the 6-month average = (3 * m13 + 3 * m46) / 6
    first = -float(price)
    k = min(2, max(1, round(((sp.get("pass_med") or 7) + (sp.get("first_pay") or 30)) / 21)))
    rest = (3 * m13 - first) / (3 - k)
    head = [round(first, 2)] + [0.0] * (k - 1) + [round(rest, 2)] * (3 - k)
    return head + [float(m46)] * (months - 3)


def calendar(b=None, now=None, months=12, R=None, F=None) -> dict:
    """Month-by-month: which accounts when (held + the owner's planned buys + the lit-funded-combo ladder bought from cash),
    expected $ at the H2 rate and the downside case (the same rules on 2021-25 trades)."""
    b = business(b)
    s = settings(b)
    R, F = R or rates(), F or firms()
    today = _today(now)
    m0 = today.replace(day=1)
    accts = accounts(b)
    fees_paid = sum(float(e.get("usd") or 0) for e in paid(b))

    def run(span):
        held = []                                            # (plan, buy month index, label)
        for a in accts:
            if a.get("stage") in ("closed",):
                continue
            st = dt.date.fromisoformat(a["start"]) if a.get("start") else today
            mi = (st.year - m0.year) * 12 + st.month - m0.month
            held.append((a.get("lit_id"), max(mi, 0) if a.get("stage") == "planned" else mi, a["id"], a.get("stage") == "planned"))
        cnt = Counter(h[0] for h in held)
        todo = []
        for step in s["ladder"]:
            if cnt[step["plan"]] > 0:
                cnt[step["plan"]] -= 1
            else:
                todo.append(step)
        cash = s["budget"] - fees_paid - sum(plan_price(h[0], F, R)["usd"] or 0 for h in held if h[3])
        rows, cum = [], 0.0
        for mi in range(months):
            # buy at most one ladder account a month (the 5-session stagger), when the cash covers it; Lucid waits for the
            # 50K decision (~ its median pass + a week), FundedNext for month 2
            buys = []
            if todo:
                step = todo[0]
                pr = plan_price(step["plan"], F, R)["usd"] or 0
                gate = {"decided:mffu_50k": 1, "funded:2|months:2": 2}.get(step.get("when") or "", 0)
                if mi >= gate and cash >= pr:
                    held.append((step["plan"], mi, f"{step['plan']}#{len(held) + 1}", False))
                    cash -= pr
                    buys.append(plan_price(step["plan"], F, R)["name"])
                    todo.pop(0)
            for h in held:
                if h[1] == mi and h[3]:
                    buys.append(plan_price(h[0], F, R)["name"] + " (planned)")
            got, back = 0.0, 0.0
            for h in held:
                age = mi - h[1]
                if age < 0:
                    continue
                got += _life_curve(h[0], span, s["variant"], R, months + 1)[min(age, months)]
                if age == 0:                                 # its price already left the cash (fees paid / reserved / bought)
                    back += plan_price(h[0], F, R)["usd"] or 0
            cash += got + back
            cum += got
            rows.append({"month": _add_months(m0, mi).strftime("%Y-%m"), "buy": buys, "accounts": sum(1 for h in held if h[1] <= mi),
                         "usd": round(got), "cum": round(cum)})
        return rows

    exp, down = run("H2"), run("2021-25")
    for r, d in zip(exp, down):
        r["down_usd"], r["down_cum"], r["down_accounts"] = d["usd"], d["cum"], d["accounts"]
    trio = stack_rate("current: B50+Lucid+FN", "H2", s["variant"], R)
    trio_d = stack_rate("current: B50+Lucid+FN", "2021-25", s["variant"], R)
    alt = stack_rate("current: B50+Lucid+FN", "H2", "all3", R)
    return {"rows": exp, "variant": s["variant"], "budget": s["budget"],
            "trio": {"h2_month": trio.get("net_month"), "h2_m46": trio.get("m46"), "h2_lose_6m": trio.get("neg_6m"),
                     "down_month": trio_d.get("net_month"), "with_scale_in_h2": alt.get("net_month")},
            "how": "Each account follows its study curve from the month it is bought: month 1 = the fee, months 2-3 = the rest of "
                   "the 6-month average, months 4+ = the months 4-6 rate (net of every fee, re-buys included). Expected = Jul-Oct "
                   "2026 trades (H2, quote it); downside = the same rules on 2021-25 trades, where every mix loses its fees. "
                   "Ladder (lit-funded-combo.md): Builder 50K, LucidPro, FundedNext, then 2nd and 3rd LucidPro and a 2nd "
                   "FundedNext, each bought when cash (budget + payouts) allows, one a month at most.",
            "warn": "Same LIT signals on every account (81-91% correlated): more accounts = more money and the same bad months. "
                    "Several accounts on one PC bot: engine/multi_account.py, OFF by default (switch on after a Sim check)."}


# ================================================================================================ 6. Z06 goal
def goal(b=None, now=None, R=None) -> dict:
    b = business(b)
    s = settings(b)
    R = R or rates()
    pays = sum(float(p.get("usd") or 0) for p in b.get("payouts") or [])
    share = (1 - s["tax_pct"] / 100) * s["keep_pct"] / 100
    saved = round(pays * share + s["goal_saved_extra"], 2)
    left = max(0.0, s["goal_usd"] - saved)
    trio = stack_rate("current: B50+Lucid+FN", "H2", s["variant"], R).get("net_month")
    b50 = stack_rate("B50", "H2", s["variant"], R).get("net_month")
    cons_rate = b50 if s["conservative"] == "builder_alone" else float(s["conservative"]) if str(s["conservative"]).replace(".", "").isdigit() else b50

    def months(rate):
        if not rate or rate <= 0:
            return None
        return round(left / (rate * share), 1)
    return {"name": s["goal_name"], "target": s["goal_usd"], "saved": saved, "left": round(left, 2),
            "pct": round(100 * saved / s["goal_usd"], 2) if s["goal_usd"] else None, "payouts": round(pays, 2),
            "share": round(share, 4), "tax_pct": s["tax_pct"], "keep_pct": s["keep_pct"],
            "rate_h2": trio, "months_h2": months(trio), "rate_cons": cons_rate, "months_cons": months(cons_rate),
            "months_h2_all": round(left / (trio * (1 - s["tax_pct"] / 100)), 1) if trio and trio > 0 else None,
            "rate_down": stack_rate("current: B50+Lucid+FN", "2021-25", s["variant"], R).get("net_month"),
            "how": f"saved = payouts received x (1 - {s['tax_pct']:g}% set-aside) x {s['keep_pct']:g}% to the goal fund (business.json "
                   "withdraw.keep_pct) + goal.saved_extra_usd. H2 rate = Builder 50K + LucidPro + FundedNext on Jul-Oct trades, "
                   "6 months net of fees; conservative = the Builder 50K alone (the account you have). On 2021-25 trades the plan "
                   "loses money: the goal is never reached on that rate.",
            "placeholder": s["goal_usd"] == 115000, "note": "Goal price is a setting: research/props/business.json goal.usd "
                                                            "(or the tracker's Settings sheet)."}


# ================================================================================================ trading ledger (for the statement)
def ledger_trades(journal=None, hb_path=None) -> list:
    """The bot's routed trades: data/lit_journal.jsonl rows with source "pc" + logs/heartbeat_last.json "acct" trades (PC only).
    Backtest / replay rows are never counted. Deduplicated by entry time."""
    out = {}
    jp = journal or os.path.join(ROOT, "data", "lit_journal.jsonl")
    try:
        with open(jp, encoding="utf-8") as fh:
            for ln in fh:
                try:
                    r = json.loads(ln)
                except ValueError:
                    continue
                if r.get("source") == "pc" and r.get("entry_t"):
                    out[int(r["entry_t"])] = {"day": r.get("day"), "entry_t": int(r["entry_t"]), "side": r.get("side"), "qty": r.get("qty"),
                                              "pnl": _f(r.get("pnl")), "exit": r.get("exit"), "src": "journal"}
    except OSError:
        pass
    hb = _json(hb_path or os.path.join(ROOT, "logs", "heartbeat_last.json"), {}) or {}
    for t in ((hb.get("acct") or {}).get("trades") or []):
        if isinstance(t, dict) and t.get("entry_t"):
            out.setdefault(int(t["entry_t"]), {"day": t.get("day"), "entry_t": int(t["entry_t"]), "side": t.get("side"), "qty": t.get("qty"),
                                               "pnl": _f(t.get("pnl")), "exit": t.get("exit"), "src": "heartbeat"})
    return sorted(out.values(), key=lambda x: x["entry_t"])


# ================================================================================================ 1. monthly statement
def statement(month=None, b=None, now=None, trades=None) -> dict:
    b = business(b)
    s = settings(b)
    month = month or _today(now).strftime("%Y-%m")
    y = month[:4]
    fe = [e for e in paid(b) if _date(e.get("date"))[:7] == month]
    po = [p for p in b.get("payouts") or [] if _date(p.get("date"))[:7] == month]
    ytd_f = sum(float(e.get("usd") or 0) for e in paid(b) if y + "-01" <= _date(e.get("date"))[:7] <= month)
    ytd_p = sum(float(p.get("usd") or 0) for p in b.get("payouts") or [] if y + "-01" <= _date(p.get("date"))[:7] <= month)
    all_f = sum(float(e.get("usd") or 0) for e in paid(b) if _date(e.get("date"))[:7] <= month)
    all_p = sum(float(p.get("usd") or 0) for p in b.get("payouts") or [] if _date(p.get("date"))[:7] <= month)
    f_tot, p_tot = sum(float(e.get("usd") or 0) for e in fe), sum(float(p.get("usd") or 0) for p in po)
    net = p_tot - f_tot
    tr = [t for t in (ledger_trades() if trades is None else trades) if str(t.get("day") or "")[:7] == month]
    pnl = sum(float(t.get("pnl") or 0) for t in tr)
    days = {}
    for t in tr:
        days[str(t["day"])[:10]] = round(days.get(str(t["day"])[:10], 0.0) + float(t.get("pnl") or 0), 2)
    months = {}
    for e in paid(b):
        m = _date(e.get("date"))[:7]
        if m <= month:
            months.setdefault(m, [0.0, 0.0])[0] += float(e.get("usd") or 0)
    for p in b.get("payouts") or []:
        m = _date(p.get("date"))[:7]
        if m <= month:
            months.setdefault(m, [0.0, 0.0])[1] += float(p.get("usd") or 0)
    hist, cum = [], 0.0
    for m in sorted(months):
        cum += months[m][1] - months[m][0]
        hist.append({"month": m, "fees": round(months[m][0], 2), "payouts": round(months[m][1], 2), "net": round(months[m][1] - months[m][0], 2),
                     "cum": round(cum, 2)})
    open_accts = [{"id": a["id"], "firm": a.get("firm"), "plan": a.get("plan"), "stage": a.get("stage"), "start": a.get("start")}
                  for a in accounts(b) if a.get("stage") not in ("closed",)]
    return {"month": month, "generated": dt.datetime.now(ET).strftime("%Y-%m-%d %H:%M ET"),
            "business": {"fees": [{"date": _date(e["date"]), "item": e.get("item"), "firm": e.get("firm"), "usd": round(float(e["usd"]), 2)} for e in fe],
                         "payouts": [{"date": _date(p["date"]), "item": p.get("item"), "firm": p.get("firm"), "usd": round(float(p["usd"]), 2)} for p in po],
                         "fees_total": round(f_tot, 2), "payouts_total": round(p_tot, 2), "net": round(net, 2),
                         "ytd_fees": round(ytd_f, 2), "ytd_payouts": round(ytd_p, 2), "ytd_net": round(ytd_p - ytd_f, 2),
                         "all_net": round(all_p - all_f, 2), "set_aside": round(max(0.0, net) * s["tax_pct"] / 100, 2), "tax_pct": s["tax_pct"]},
            "trading": {"trades": len(tr), "wins": sum(1 for t in tr if (t.get("pnl") or 0) > 0), "losses": sum(1 for t in tr if (t.get("pnl") or 0) < 0),
                        "pnl": round(pnl, 2), "days": [{"day": d, "pnl": v} for d, v in sorted(days.items())],
                        "note": "Routed trades on the prop account (the bot's own numbers): account P&L, not cash. Cash only "
                                "moves with fees and payouts." if tr else
                                "No routed trades recorded this month on this machine (the PC bot's journal / heartbeat)."},
            "history": hist, "accounts": open_accts, "tax_label": NOT_TAX, "disclaimer": DISCLAIMER}


def _chart_png(stmt) -> bytes | None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return None
    have = {h["month"]: h for h in stmt["history"]}
    m_end = dt.date.fromisoformat(stmt["month"] + "-01")
    first = min([dt.date.fromisoformat(m + "-01") for m in have] + [_add_months(m_end, -5)])
    hist, cum, m = [], 0.0, first
    while m <= m_end:                                    # every month from the first entry (6 at least), empty months at $0
        h = have.get(m.strftime("%Y-%m"))
        cum = h["cum"] if h else cum
        hist.append({"month": m.strftime("%Y-%m"), "net": h["net"] if h else 0.0, "cum": cum})
        m = _add_months(m, 1)
    hist = hist[-12:]
    days = stmt["trading"]["days"]
    fig, axes = plt.subplots(1, 2 if days else 1, figsize=(8.2, 2.6), dpi=130)
    axes = axes if days else [axes]
    ax = axes[0]
    xs = [h["month"][2:] for h in hist]
    ax.bar(xs, [h["net"] for h in hist], color=["#16a34a" if h["net"] >= 0 else "#dc2626" for h in hist], width=0.6, label="month net")
    ax.plot(xs, [h["cum"] for h in hist], color="#2563eb", marker="o", lw=1.8, label="cumulative")
    ax.axhline(0, color="#9ca3af", lw=0.8)
    ax.set_title("Business cash: payouts - fees", fontsize=9)
    ax.legend(fontsize=7, frameon=False, loc="best")
    ax.tick_params(labelsize=7)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    if days:
        a2 = axes[1]
        a2.bar([d["day"][5:] for d in days], [d["pnl"] for d in days], color=["#16a34a" if d["pnl"] >= 0 else "#dc2626" for d in days])
        a2.axhline(0, color="#9ca3af", lw=0.8)
        a2.set_title("Routed trades: account P&L per day", fontsize=9)
        a2.tick_params(labelsize=6, rotation=45)
        for sp in ("top", "right"):
            a2.spines[sp].set_visible(False)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    return buf.getvalue()


def render_html(stmt) -> str:
    import base64
    from html import escape as E
    B, T = stmt["business"], stmt["trading"]
    png = _chart_png(stmt)
    img = f'<img alt="chart" style="max-width:100%" src="data:image/png;base64,{base64.b64encode(png).decode()}">' if png else ""

    def tbl(rows, cols):
        if not rows:
            return "<p class=m>None this month.</p>"
        h = "".join(f"<th>{E(c[1])}</th>" for c in cols)
        body = "".join("<tr>" + "".join(f"<td>{E(money(r[c[0]], 2) if c[0] == 'usd' else str(r.get(c[0]) or ''))}</td>" for c in cols) + "</tr>" for r in rows)
        return f"<table><tr>{h}</tr>{body}</table>"
    return f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>P&amp;L statement {E(stmt['month'])}</title><style>
:root{{color-scheme:light dark;--bg:#fff;--ink:#111827;--mut:#6b7280;--line:#e5e7eb}}
@media (prefers-color-scheme:dark){{:root{{--bg:#0b0d12;--ink:#e5e7eb;--mut:#9ca3af;--line:#1f2937}}}}
body{{background:var(--bg);color:var(--ink);font:14px/1.5 system-ui,sans-serif;max-width:860px;margin:0 auto;padding:16px}}
table{{border-collapse:collapse;width:100%;margin:6px 0 14px}}td,th{{border-bottom:1px solid var(--line);padding:5px 6px;text-align:left}}
.m{{color:var(--mut)}}.k{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px}}.k div{{border:1px solid var(--line);border-radius:10px;padding:8px 10px}}
.k b{{display:block;font-size:18px}}</style></head><body>
<h1>Prop business - P&amp;L statement {E(stmt['month'])}</h1><p class=m>Generated {E(stmt['generated'])}. {E(stmt['disclaimer'])}</p>
<div class=k><div>Fees<b>{money(B['fees_total'], 2)}</b></div><div>Payouts<b>{money(B['payouts_total'], 2)}</b></div>
<div>Net this month<b>{money(B['net'], 2)}</b></div><div>Year to date<b>{money(B['ytd_net'], 2)}</b></div><div>Since the start<b>{money(B['all_net'], 2)}</b></div></div>
{img}<h2>Fees</h2>{tbl(B['fees'], [('date', 'Date'), ('item', 'Item'), ('firm', 'Firm'), ('usd', 'Amount')])}
<h2>Payouts received</h2>{tbl(B['payouts'], [('date', 'Date'), ('item', 'Account'), ('firm', 'Firm'), ('usd', 'Received')])}
<h2>Tax set-aside</h2><p>{money(B['set_aside'], 2)} ({B['tax_pct']:g}% of a positive month). <b>{E(stmt['tax_label'])}</b></p>
<h2>Bot trades (routed)</h2><p>{T['trades']} trades ({T['wins']} won, {T['losses']} lost), account P&amp;L {money(T['pnl'], 2)}. <span class=m>{E(T['note'])}</span></p>
<h2>Accounts</h2>{tbl(stmt['accounts'], [('id', 'Account'), ('firm', 'Firm'), ('plan', 'Plan'), ('stage', 'Stage'), ('start', 'Start')])}
</body></html>"""


def render_pdf(stmt, path) -> str:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    st = getSampleStyleSheet()
    B, T = stmt["business"], stmt["trading"]
    el = [Paragraph(f"Prop business - P&amp;L statement {stmt['month']}", st["Title"]),
          Paragraph(f"Generated {stmt['generated']}. {stmt['disclaimer']}", st["Italic"]), Spacer(1, 8)]
    kv = [["Fees", money(B["fees_total"], 2), "Payouts", money(B["payouts_total"], 2)],
          ["Net this month", money(B["net"], 2), "Year to date", money(B["ytd_net"], 2)],
          ["Since the start", money(B["all_net"], 2), f"Set-aside ({B['tax_pct']:g}%)", money(B["set_aside"], 2)]]
    t = Table(kv, colWidths=[1.6 * inch, 1.3 * inch, 1.6 * inch, 1.3 * inch])
    t.setStyle(TableStyle([("FONT", (0, 0), (-1, -1), "Helvetica", 10), ("FONT", (1, 0), (1, -1), "Helvetica-Bold", 10),
                           ("FONT", (3, 0), (3, -1), "Helvetica-Bold", 10), ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.lightgrey)]))
    el += [t, Spacer(1, 8)]
    png = _chart_png(stmt)
    if png:
        el += [Image(io.BytesIO(png), width=7.2 * inch, height=2.28 * inch), Spacer(1, 6)]

    def table(title, rows, cols):
        el.append(Paragraph(title, st["Heading3"]))
        if not rows:
            el.append(Paragraph("None this month.", st["Normal"]))
            return
        data = [[c[1] for c in cols]] + [[money(r[c[0]], 2) if c[0] == "usd" else str(r.get(c[0]) or "")[:48] for c in cols] for r in rows]
        tb = Table(data, repeatRows=1)
        tb.setStyle(TableStyle([("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 9), ("FONT", (0, 1), (-1, -1), "Helvetica", 9),
                                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                                ("LINEBELOW", (0, 1), (-1, -1), 0.3, colors.lightgrey)]))
        el.append(tb)
    table("Fees", B["fees"], [("date", "Date"), ("item", "Item"), ("firm", "Firm"), ("usd", "Amount")])
    table("Payouts received", B["payouts"], [("date", "Date"), ("item", "Account"), ("firm", "Firm"), ("usd", "Received")])
    el.append(Paragraph("Bot trades (routed)", st["Heading3"]))
    el.append(Paragraph(f"{T['trades']} trades ({T['wins']} won, {T['losses']} lost), account P&amp;L {money(T['pnl'], 2)}. {T['note']}", st["Normal"]))
    table("Accounts", stmt["accounts"], [("id", "Account"), ("firm", "Firm"), ("plan", "Plan"), ("stage", "Stage"), ("start", "Start")])
    el += [Spacer(1, 8), Paragraph(f"<b>{stmt['tax_label']}</b>", st["Normal"])]
    SimpleDocTemplate(path, pagesize=letter, leftMargin=0.6 * inch, rightMargin=0.6 * inch, topMargin=0.6 * inch, bottomMargin=0.6 * inch,
                      title=f"P&L statement {stmt['month']}").build(el)
    return path


def write_statement(month=None, b=None, out_dir=STATEMENTS, html=False, now=None, trades=None) -> str:
    """research/business/statements/<month>.pdf (reportlab), or .html when reportlab is missing or html=True."""
    stmt = statement(month, b, now, trades)
    os.makedirs(out_dir, exist_ok=True)
    if not html:
        try:
            return render_pdf(stmt, os.path.join(out_dir, f"{stmt['month']}.pdf"))
        except ImportError:
            pass
    path = os.path.join(out_dir, f"{stmt['month']}.html")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(render_html(stmt))
    return path


# ================================================================================================ reminders (pushes)
def notices(now=None, b=None, pc_eval=None, R=None, F=None) -> list:
    """The business reminders due now: [{"sub", "title", "body", "key"}]. engine/ops_checks.py pushes each once (by key) in
    its daily windows (pre-session, end of day, Sunday evening)."""
    now = time.time() if now is None else now
    b = business(b)
    out = []
    try:
        for r in payout_status(b, now, pc_eval, R, F)["rows"]:
            if r.get("status") == "ready":
                name = f"{FIRM_SHORT.get(firm_key(r.get('firm')), r.get('firm'))} {r.get('plan')}"
                out.append({"sub": "payout", "title": f"Payout: {name} can request",
                            "body": f"{r['text']} Check the firm's payout page (best-day rule, traded days) before you click.",
                            "key": f"biz:payout:{r['id']}:{r.get('payouts_n', 0)}"})
    except Exception:
        pass
    try:
        p = planner(b, now, R, F)
        n = next((x for x in p["steps"] if x.get("due")), None)
        if n:
            codes = ", ".join(c["code"] for c in n.get("codes") or [] if not str(c["code"]).startswith("("))[:80]
            out.append({"sub": "buy", "title": f"Time to buy: {n['name']}",
                        "body": f"{money(n['price'], 2)} ({n['price_basis']}); cash in the budget {money(n['cash_left'])}. "
                                + (f"Codes to try: {codes} - {VERIFY}. " if codes else f"Prices change: {VERIFY}. ")
                                + "Log it: python tools/business.py add-expense.",
                        "key": f"biz:buy:{n['slot']}:{n['plan']}"})
    except Exception:
        pass
    return out


# ================================================================================================ the dashboards' view
def view(b=None, now=None, pc_eval=None) -> dict:
    """Everything the Business / Prop Firms pages show (both dashboards). Never raises per panel."""
    def safe(fn, *a, **kw):
        try:
            return fn(*a, **kw)
        except Exception as e:                           # noqa: BLE001
            return {"error": f"{e.__class__.__name__}: {str(e)[:160]}"}
    b = business(b)
    R, F = rates(), firms()
    today = _today(now)
    last_m = (today.replace(day=1) - dt.timedelta(days=1)).strftime("%Y-%m")
    st = safe(statement, today.strftime("%Y-%m"), b, now)
    watch = safe(_watch_view)
    return {"t": int(time.time() if now is None else now), "statement": st, "statement_prev": safe(statement, last_m, b, now),
            "tax": safe(tax_year, today.year, b, now), "payouts": safe(payout_status, b, now, pc_eval, R, F),
            "planner": safe(planner, b, now, R, F), "calendar": safe(calendar, b, now, 12, R, F), "goal": safe(goal, b, now, R),
            "roi": safe(roi, b, now), "logs": b.get("logs"), "settings": safe(settings, b), "watch": watch,
            "notices": safe(notices, now, b, pc_eval, R, F), "disclaimer": DISCLAIMER, "tax_label": NOT_TAX,
            "files": {"expenses": "research/business/expenses.csv", "payouts": "research/business/payouts.csv",
                      "tracker": "research/business/prop_business.xlsx", "settings": "research/props/business.json",
                      "statements": "research/business/statements/", "sync": "python tools/build_business_tracker.py --sync"}}


def _watch_view() -> dict:
    try:
        from tools import prop_watch
        return prop_watch.summary()
    except Exception as e:                               # noqa: BLE001
        return {"error": f"{e.__class__.__name__}: {str(e)[:120]}"}


# ================================================================================================ CLI
def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="python tools/business.py", description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("view")
    s1 = sub.add_parser("statement")
    s1.add_argument("--month")
    s1.add_argument("--html", action="store_true")
    s1.add_argument("--out", default=STATEMENTS)
    s3 = sub.add_parser("tax")
    s3.add_argument("--year", type=int)
    s3.add_argument("--out", default=BIZ)
    e = sub.add_parser("add-expense")
    for k in ("date", "firm", "account", "type", "desc", "code", "note"):
        e.add_argument("--" + k, default="")
    e.add_argument("--usd", required=True)
    p = sub.add_parser("add-payout")
    for k in ("date", "firm", "account", "method", "note"):
        p.add_argument("--" + k, default="")
    p.add_argument("--received", required=True)
    p.add_argument("--requested", default="")
    sub.add_parser("notices")
    sub.add_parser("rates")
    for x in (e, p):
        x.add_argument("--no-sync", action="store_true", help="do not copy the row into prop_business.xlsx")
    a = ap.parse_args(argv)
    if a.cmd == "view":
        print(json.dumps(view(), indent=1, default=str))
    elif a.cmd == "statement":
        print("wrote", write_statement(a.month, out_dir=a.out, html=a.html))
    elif a.cmd == "tax":
        print("wrote", write_tax_csv(a.year, out_dir=a.out), "-", NOT_TAX)
    elif a.cmd in ("add-expense", "add-payout"):
        if a.cmd == "add-expense":
            r = append_row(EXPENSES_CSV, EXP_COLS, {"date": a.date, "firm": a.firm, "account": a.account, "type": a.type,
                                                    "description": a.desc, "amount_usd": a.usd, "code": a.code, "note": a.note})
        else:
            r = append_row(PAYOUTS_CSV, PAY_COLS, {"date": a.date, "firm": a.firm, "account": a.account, "requested_usd": a.requested,
                                                   "received_usd": a.received, "method": a.method, "note": a.note})
        print("added", r)
        if not a.no_sync:
            try:
                from tools import build_business_tracker as bt
                print("tracker:", bt.sync())
            except Exception as ex:                      # noqa: BLE001
                print("tracker not synced:", ex.__class__.__name__, str(ex)[:120], "(run python tools/build_business_tracker.py --sync)")
    elif a.cmd == "notices":
        for n in notices():
            print(f"[{n['key']}] {n['title']}: {n['body']}")
    elif a.cmd == "rates":
        r = build_rates()
        with open(RATES_PATH, "w", encoding="utf-8") as fh:
            json.dump(r, fh, indent=1)
        print("wrote", RATES_PATH, f"({os.path.getsize(RATES_PATH) // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
