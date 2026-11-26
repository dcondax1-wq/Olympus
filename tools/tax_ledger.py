"""TAX / P&L LEDGER for the accountant (day-batch7 2026-11-26): every prop-firm payout and fee, per account per month, to CSV, plus a
yearly summary in Schedule C terms (eval fees = business expenses, payouts = income). Read-only, stdlib only, never sends anything.
Education, not tax advice: research/writeups/taxes-2026-11-17.md (payouts are normally self-employment income, about 14.1% SE tax
on profit plus income tax, no withholding; quarterly 1040-ES; set aside 30% of every payout).

Sources (every one optional; a missing one is listed in the summary, never invented):
  1. YOUR ledger  data/money_ledger.json (the Ledger app's Export JSON: {"entries": [{kind, amount, date, acct, note}]}): fees,
     resets, activation, payouts received (payout_in = what reached you), expenses, other income, tax paid
  2. the eval prices the site knows  tools/web_public/ledger/rules.json (your real prices + purchase days; an account you entered a fee
     for yourself is not counted twice)
  3. the payouts recorded with the bot (gross, x the firm's split = to you; one your ledger already has is not counted twice):
       ATLAS's 25K  data/account_b.json "payouts" (python -m engine.account_b --payout day=$)
       extra / funded accounts  data/accounts.json funded.payouts
       Rapid EOD  data/rapid.json / data/rapid2.json "payouts" (python -m engine.rapid --payout ...)
  An account the bot knows with no purchase fee anywhere -> a "fee missing" line in the summary (add it in the Ledger app).
Kalshi deposits / withdrawals are NOT prop income (different tax rules): left out and said so.

Output (PRIVATE, gitignored folder money_out/tax/):
  ledger_<year>.csv    every row: date, month, account, firm, kind, schedule_c, gross, split, to_you (+ = income, - = expense), source
  monthly_<year>.csv   account x month: payouts gross, payouts to you, eval fees, resets, activation, other expenses, net
  summary_<year>.md    the year: income, expenses by category, net profit, SE tax estimate, the 30% set-aside, quarterly dates,
                       what is missing

    python -X utf8 tools/tax_ledger.py                  # this year
    python -X utf8 tools/tax_ledger.py --year 2026 [--ledger f.json] [--root <dir>] [--out <dir>]
Tests: python -X utf8 -m tests.test_tax_ledger
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import money_scoreboard as MS  # noqa: E402

OUT = os.path.join(ROOT, "money_out", "tax")
SPLIT = {"builder": 0.8, "rapid": 0.9}
SCHED = {"payout_in": "Income: prop firm payouts (gross receipts)", "income": "Income: other",
         "fee": "Expense: evaluation fees", "activation": "Expense: activation fees", "reset": "Expense: resets",
         "expense": "Expense: other business costs (data, platform, software)"}
SE_RATE, SE_BASE, SET_ASIDE = 0.153, 0.9235, 0.30
QUARTERS = {2026: [("Jan 15, 2027", "Sep-Dec 2026")],
            2027: [("Apr 15, 2027", "Jan-Mar"), ("Jun 15, 2027", "Apr-May"), ("Sep 15, 2027", "Jun-Aug"), ("Jan 15, 2028", "Sep-Dec")]}


def _read(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def _firm(acct: str, plan: str = "") -> str:
    s = f"{acct} {plan}".lower()
    return "MFFU Rapid EOD" if "rapid" in s else "MFFU Builder"


def bot_payouts(root: str) -> tuple[list, list]:
    """(payout rows, accounts the bot knows [(acct, plan)]) from the engine's own stores (gross; to you = x split)."""
    rows, known = [], []

    def add(acct, plan, pays, src):
        split = SPLIT["rapid"] if "rapid" in f"{acct} {plan}".lower() else SPLIT["builder"]
        for d, g in (pays or {}).items():
            try:
                g = float(g)
            except (TypeError, ValueError):
                continue
            if g > 0 and MS.is_date(str(d)):
                rows.append({"date": str(d), "acct": acct, "kind": "payout_in", "gross": round(g, 2), "split": split,
                             "amount": round(g * split, 2), "source": src})
    ab = _read(os.path.join(root, "data", "account_b.json"))
    blk = ab.get("account_b") if isinstance(ab, dict) else None
    if isinstance(blk, dict) and blk:
        known.append(("atlas25k", blk.get("plan") or "builder25k"))
        add("atlas25k", blk.get("plan") or "builder25k", blk.get("payouts"), "data/account_b.json")
    acc = _read(os.path.join(root, "data", "accounts.json"))
    items = acc.get("accounts") if isinstance(acc, dict) else acc
    for a in items or []:
        if not isinstance(a, dict) or not a.get("id"):
            continue
        plan = str(a.get("preset") or a.get("plan") or "")
        known.append((str(a["id"]), plan))
        f = a.get("funded") if isinstance(a.get("funded"), dict) else {}
        add(str(a["id"]), plan, f.get("payouts"), "data/accounts.json")
    for nm in ("rapid.json", "rapid2.json"):
        r = _read(os.path.join(root, "data", nm))
        b = r.get("rapid") if isinstance(r, dict) and isinstance(r.get("rapid"), dict) else r
        if isinstance(b, dict) and (b.get("account") or b.get("payouts")):
            aid = nm[:-5]                                   # "rapid" / "rapid2" (the engine's slot names)
            known.append((aid, "rapid " + str(b.get("plan") or "")))
            add(aid, "rapid", b.get("payouts"), f"data/{nm}")
    return rows, known


def collect(year: int, root: str = ROOT, ledger_path: str | None = None) -> dict:
    today = dt.date.today().isoformat()
    led = MS.load_ledger(ledger_path or os.path.join(root, "data", "money_ledger.json"), keep_notes=False)
    own = MS.expand(led["entries"], today)
    rules = _read(os.path.join(root, "tools", "web_public", "ledger", "rules.json")) or {}
    auto, basis = MS.auto_fees({}, rules, today)
    entries, _shown = MS.merge(own, led["hidden"], auto)
    rows = []
    for e in entries:
        k = e["kind"]
        if k not in SCHED:
            continue                                  # payout requests, Kalshi deposits / withdrawals, tax payments: not P&L
        sign = 1 if MS.KINDS[k] > 0 else -1
        rows.append({"date": e["date"], "acct": e["acct"], "kind": k, "gross": e["amount"] if k == "payout_in" else None,
                     "split": None, "amount": round(sign * e["amount"], 2),
                     "source": "auto: ledger/rules.json price" if e.get("auto") else "your ledger"})
    bp, known = bot_payouts(root)
    for p in bp:                                      # not twice: your own payout_in on that day for that account (to you or gross)
        dup = any(r["kind"] == "payout_in" and r["acct"] == p["acct"] and r["date"] == p["date"] and
                  (abs(r["amount"] - p["amount"]) < 0.01 or abs(r["amount"] - p["gross"]) < 0.01) for r in rows)
        if not dup:
            rows.append(p)
    y = str(year)
    rows = sorted([r for r in rows if r["date"].startswith(y) and r["date"] <= today], key=lambda r: (r["date"], r["acct"], r["kind"]))
    fee_accts = {e["acct"] for e in entries if e["kind"] in ("fee", "activation")}
    missing = sorted({a for a, _ in known if a not in fee_accts})
    kal = [e for e in own if e["kind"] in ("deposit", "withdrawal") and e["date"].startswith(y)]
    taxp = round(sum(e["amount"] for e in own if e["kind"] == "tax" and e["date"].startswith(y)), 2)
    return {"year": year, "rows": rows, "ledger_state": led["state"], "fee_basis": basis, "missing_fee": missing,
            "kalshi_rows": len(kal), "tax_paid": taxp, "bot_payout_rows": len(bp)}


def write(res: dict, out: str = OUT) -> dict:
    os.makedirs(out, exist_ok=True)
    y = res["year"]
    p1 = os.path.join(out, f"ledger_{y}.csv")
    with open(p1, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["date", "month", "account", "firm", "kind", "schedule_c", "gross", "split", "amount_usd", "source"])
        for r in res["rows"]:
            w.writerow([r["date"], r["date"][:7], r["acct"], _firm(r["acct"]), r["kind"], SCHED[r["kind"]],
                        "" if r["gross"] is None else f"{r['gross']:.2f}", "" if r["split"] is None else r["split"], f"{r['amount']:.2f}",
                        r["source"]])
    M = defaultdict(lambda: defaultdict(float))
    for r in res["rows"]:
        m = M[(r["acct"], r["date"][:7])]
        if r["kind"] == "payout_in":
            m["gross"] += r["gross"] if r["gross"] is not None else r["amount"]
            m["to_you"] += r["amount"]
        else:
            m[r["kind"]] += -r["amount"] if r["amount"] < 0 else r["amount"]
        m["net"] += r["amount"]
    p2 = os.path.join(out, f"monthly_{y}.csv")
    with open(p2, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["account", "month", "payouts_gross", "payouts_to_you", "eval_fees", "activation", "resets", "other_expenses",
                    "other_income", "net"])
        for (a, mo), m in sorted(M.items(), key=lambda kv: (kv[0][1], kv[0][0])):
            w.writerow([a, mo] + [f"{m[k]:.2f}" for k in ("gross", "to_you", "fee", "activation", "reset", "expense", "income", "net")])
    inc = round(sum(r["amount"] for r in res["rows"] if r["amount"] > 0), 2)
    by = defaultdict(float)
    for r in res["rows"]:
        if r["amount"] < 0:
            by[SCHED[r["kind"]]] += -r["amount"]
    exp = round(sum(by.values()), 2)
    net = round(inc - exp, 2)
    se = round(max(0.0, net) * SE_BASE * SE_RATE, 2)
    pay = round(sum(r["amount"] for r in res["rows"] if r["kind"] == "payout_in"), 2)
    L = [f"# Prop trading P&L {y} (for the accountant)", "",
         f"Built {dt.date.today().isoformat()} by tools/tax_ledger.py from: your ledger ({res['ledger_state']}), eval prices ({res['fee_basis']}), "
         f"{res['bot_payout_rows']} payout(s) recorded with the bot. Detail: ledger_{y}.csv, monthly_{y}.csv. Education, not tax advice.", "",
         "| Line | $ |", "|---|---|",
         f"| Income: prop firm payouts received (to you, after the firm's split) | {pay:,.2f} |"]
    oth = round(inc - pay, 2)
    if oth:
        L.append(f"| Income: other | {oth:,.2f} |")
    for k, v in sorted(by.items()):
        L.append(f"| {k} | -{v:,.2f} |")
    L += [f"| **Net profit (Schedule C line 31 style)** | **{net:,.2f}** |",
          f"| Self-employment tax estimate (15.3% x 92.35% of net) | {se:,.2f} |",
          f"| Set-aside rule: 30% of payouts | {round(SET_ASIDE * pay, 2):,.2f} |",
          f"| Estimated tax already paid (your ledger, kind tax) | {res['tax_paid']:,.2f} |", ""]
    q = QUARTERS.get(y)
    if q:
        L.append("Quarterly estimated tax (Form 1040-ES): " + "; ".join(f"{a} for {b}" for a, b in q) + ".")
    L += ["", "Notes:",
          "- Payouts are counted as what reached you (MFFU Builder 80%, Rapid 90% of the request). MFFU's 1099 (via Rise) should match "
          "the amounts paid to you: check it against ledger_<year>.csv.",
          "- Eval fees, resets and activation fees are business expenses here; data / platform / software go in as 'expense' entries in "
          "the Ledger app.",
          f"- Kalshi deposits / withdrawals ({res['kalshi_rows']} this year) are NOT in this file: event contracts are taxed differently; "
          "give the accountant Kalshi's own tax form."]
    if res["missing_fee"]:
        L.append("- **Fee missing** (an account the bot knows with no purchase fee recorded): " + ", ".join(res["missing_fee"])
                 + ". Add each purchase in the Ledger app (kind fee, the price you paid, the day), then run this again.")
    if res["ledger_state"] != "ok":
        L.append("- Your ledger file data/money_ledger.json was not found / not readable: only the site's known eval prices and the "
                 "bot's payouts are in this file.")
    p3 = os.path.join(out, f"summary_{y}.md")
    with open(p3, "w", encoding="utf-8") as fh:
        fh.write("\n".join(L) + "\n")
    return {"ledger": p1, "monthly": p2, "summary": p3, "income": inc, "expenses": exp, "net": net, "se_tax": se, "rows": len(res["rows"])}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="prop-firm payouts and fees per account per month, for the accountant (read-only)")
    ap.add_argument("--year", type=int, default=dt.date.today().year)
    ap.add_argument("--ledger", default=None)
    ap.add_argument("--root", default=ROOT)
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args(argv)
    res = collect(a.year, a.root, a.ledger)
    w = write(res, a.out)
    print(f"tax ledger {a.year}: {w['rows']} row(s), income ${w['income']:,.2f}, expenses ${w['expenses']:,.2f}, net ${w['net']:,.2f}, "
          f"SE tax est ${w['se_tax']:,.2f} -> {w['summary']}")
    if res["missing_fee"]:
        print("  fee missing for: " + ", ".join(res["missing_fee"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
