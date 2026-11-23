"""MONEY IMPORT (tools/money_import.py, 2026-11-14): your own bank / card exports -> a private ledger + a small summary. Checks:
  a. every bank layout (fixtures in tests/fixtures/money_import/): Chase card + checking, Bank of America checking (summary above the header)
     + card, Wells Fargo (no header), Capital One card + 360, Apple Card, Discover, Cash App, PayPal, Venmo (preamble, leading empty column),
     Amex, a generic bank CSV and a generic card CSV (positive = a charge), OFX (SGML) and QFX (XML): layout found, money out negative,
     pending / failed rows skipped, the right category
  b. privacy: no account / card / reference number survives in the private ledger or the summary (number columns dropped, 4+ digit runs
     masked, OFX ACCTID never read), no merchant names in the summary unless privacy.publish_merchants, no 5+ digit run in any string
  c. de-dup: the same file twice, an overlapping export, two equal coffees on one day (both kept), the iPhone inbox ids
  d. rules: whole words (PARENT is not rent), direction (MFFU out = fee, in = payout), first match wins, the owner's own rules file and
     overrides, the bank's category as a fallback, transfers and card payments left out of in / out, Kalshi shown apart
  e. subscriptions: monthly / weekly / yearly, a price rise, two plans at one merchant, a stopped one, $ a month and the next date
  f. the summary by hand: month in / out / net, by category, prop-firm ROI, Kalshi moves, runway, net worth (Kalshi from the feed, debts),
     history, leaks, the Jarvis answers
  g. Oikos: the oikos ledger reads in tools/money/oikos.py, has no merchant names, and oikos.py picks it up from the private folder
  h. the CLI in a temp home: drop folder, --balance, --init-rules never overwrites, a junk file is reported, no network, stdlib only
    python -X utf8 -m tests.test_money_import
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import money_import as MI  # noqa: E402

FIX = os.path.join(ROOT, "tests", "fixtures", "money_import")
TODAY = "2026-11-14"
RES = []
FAKE_NUMBERS = ("9876543210", "4760039224", "1234567890", "24692166278100106416135", "3912345678901234567", "41006", "5550001234567890",
                "4111111111111111", "93601", "S308289123456", "57444123456", "5544", "8AB12345CD678901E")


def check(name, ok, info=""):
    RES.append(bool(ok))
    print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:700]}"), flush=True)


def near(a, b, tol=0.011):
    return a is not None and b is not None and abs(a - b) <= tol


def fx(name):
    return os.path.join(FIX, name)


def cats_of(name):
    p = MI.parse_file(fx(name))
    rules = MI.compile_rules(MI.DEFAULT_RULES_DOC)
    out = []
    for r in p["rows"]:
        r = {**r, "source": p["layout"]}
        out.append((r["date"], MI.r2(r["amount"]), MI.categorize(r, rules)["cat"]))
    return p, out


# ------------------------------------------------------------------------------------------------ a. layouts
def test_layouts():
    want = {
        "chase_card.csv": ("chase_card", 7, 0, [("2026-10-28", -15.49, "subscriptions"), ("2026-10-27", -23.1, "food"), ("2026-10-25", 500.0, "transfer"),
                                                ("2026-10-20", -41.02, "gas"), ("2026-10-18", -91.8, "prop_fees"), ("2026-10-15", 12.99, "shopping"), ("2026-10-14", -30.0, "shopping")]),
        "chase_bank.csv": ("chase_bank", 6, 0, [("2026-10-31", 2150.0, "income"), ("2026-10-30", -60.0, "people"), ("2026-10-29", -200.0, "kalshi_deposit"),
                                                ("2026-10-28", -500.0, "transfer"), ("2026-10-05", -12.0, "bank_fees"), ("2026-10-01", -1450.0, "rent")]),
        "bofa_bank.csv": ("bofa_bank", 4, 1, [("2026-10-02", -84.12, "food"), ("2026-10-03", 1250.0, "income"), ("2026-10-09", -100.0, "cash"), ("2026-10-10", -300.0, "transfer")]),
        "bofa_card.csv": ("bofa_card", 3, 0, [("2026-10-14", -11.99, "subscriptions"), ("2026-10-12", 250.0, "transfer"), ("2026-10-11", -49.0, "prop_fees")]),
        "wells_fargo.csv": ("wells_fargo", 3, 0, [("2026-10-16", -54.3, "food"), ("2026-10-15", 1800.0, "income"), ("2026-10-14", -9.99, "subscriptions")]),
        "capone_card.csv": ("capone_card", 3, 0, [("2026-10-22", -18.45, "transport"), ("2026-10-20", 300.0, "transfer"), ("2026-10-19", -14.95, "trading_tools")]),
        "capone_bank.csv": ("capone_bank", 2, 0, [("2026-10-21", -25.0, "health"), ("2026-10-18", 100.0, "prop_payout")]),
        "apple_card.csv": ("apple_card", 3, 0, [("2026-10-22", -2.99, "subscriptions"), ("2026-10-21", 150.0, "transfer"), ("2026-10-20", -62.4, "food")]),
        "discover.csv": ("discover", 2, 0, [("2026-10-11", -38.2, "gas"), ("2026-10-10", 120.0, "transfer")]),
        "cash_app.csv": ("cash_app", 4, 1, [("2026-10-23", -8.75, "food"), ("2026-10-22", -40.0, "food"), ("2026-10-21", -100.0, "transfer"), ("2026-10-20", 25.0, "income_other")]),
        "paypal.csv": ("paypal", 3, 1, [("2026-10-24", -22.99, "subscriptions"), ("2026-10-24", 22.99, "transfer"), ("2026-10-20", 750.0, "prop_payout")]),
        "venmo.csv": ("venmo", 3, 2, [("2026-10-05", -600.0, "rent"), ("2026-10-07", 15.0, "food"), ("2026-10-08", -15.0, "transfer")]),
        "amex.csv": ("amex", 3, 0, [("2026-10-26", -5.45, "food"), ("2026-10-25", 300.0, "transfer"), ("2026-10-24", -65.0, "prop_fees")]),
        "generic_bank.csv": ("generic", 4, 0, [("2026-10-02", -79.99, "utilities"), ("2026-10-03", -45.1, "food"), ("2026-10-04", 900.0, "income"), ("2026-10-05", -20.0, "other")]),
        "generic_card.csv": ("generic_card", 4, 0, [("2026-10-02", -52.0, "gas"), ("2026-10-03", -31.1, "shopping"), ("2026-10-04", 200.0, "transfer"), ("2026-10-05", -12.0, "health")]),
        "bank.ofx": ("ofx_bank", 3, 0, [("2026-10-03", -64.5, "utilities"), ("2026-10-15", 2150.0, "income"), ("2026-10-20", -35.0, "bank_fees")]),
        "card.qfx": ("ofx_card", 3, 0, [("2026-10-05", -11.99, "subscriptions"), ("2026-10-07", 400.0, "transfer"), ("2026-10-09", -91.8, "prop_fees")]),
    }
    for name, (lid, n, skipped, rows) in want.items():
        p, got = cats_of(name)
        check(f"a. {name}: layout {lid}, {n} rows, {skipped} skipped, signs and categories", p["layout"] == lid and len(p["rows"]) == n and p["skipped"] == skipped and got == rows,
              (p["layout"], len(p["rows"]), p["skipped"], got))
    check("a. a file that is not a bank export is not read", MI.parse_file(fx("notes.txt")) is None)
    check("a. amounts: '$1,234.56' '-$12.00' '- $12.00' '(12.00)' '12.00-' '+ $50' 'abc'",
          [MI.parse_amount(x) for x in ("$1,234.56", "-$12.00", "- $12.00", "(12.00)", "12.00-", "+ $50", "abc", "")] == [1234.56, -12.0, -12.0, -12.0, -12.0, 50.0, None, None])
    check("a. dates: 10/01/2026, 1/2/26, 2026-10-01 12:00:00 EDT, 20261001120000[-5:EST], Oct 1, 2026, 01 Oct 2026, 2026-02-30 (bad)",
          [MI.parse_date(x) for x in ("10/01/2026", "1/2/26", "2026-10-01 12:00:00 EDT", "20261001120000[-5:EST]", "Oct 1, 2026", "01 Oct 2026", "2026-02-30")] ==
          ["2026-10-01", "2026-01-02", "2026-10-01", "2026-10-01", "2026-10-01", "2026-10-01", None])
    p = MI.parse_file(fx("cash_app.csv"))
    check("a. Cash App: the FAILED row is skipped", all(r["amount"] != -5.0 for r in p["rows"]), p["rows"])
    p = MI.parse_file(fx("venmo.csv"))
    check("a. Venmo: the pending row and the balance line are skipped; the person paid is in the description (private only)",
          all(r["amount"] != -12.0 for r in p["rows"]) and "Roommate Bob" in p["rows"][0]["desc"], p["rows"])


# ------------------------------------------------------------------------------------------------ a synthetic household (4+ months)
def household_rows():
    """(date, amount, description, file) for Jul..Nov 2026, each row's intended category alongside"""
    rows = []
    add = lambda d, a, desc, f, cat: rows.append((d, a, desc, f, cat))  # noqa: E731
    for m in ("2026-07", "2026-08", "2026-09", "2026-10", "2026-11"):
        add(m + "-01", 2150.00, "ACME CORP PAYROLL PPD ID: 9876543210", "bank", "income")
        if m != "2026-11":
            add(m + "-15", 2150.00, "ACME CORP PAYROLL PPD ID: 9876543210", "bank", "income")
        if m != "2026-07":
            add(m + "-01", -1450.00, "SUNSET APARTMENTS RENT WEB PMTS", "bank", "rent")
            add(m + "-05", -11.99, "SPOTIFY USA", "card", "subscriptions")
        if m in ("2026-07", "2026-08", "2026-09", "2026-10"):
            add(m + "-25", -500.00, "CHASE CREDIT CRD AUTOPAY PPD ID: 4760039224", "bank", "transfer")
            add(m + "-26", 500.00, "AUTOMATIC PAYMENT - THANK", "card", "transfer")
        if m in ("2026-07", "2026-08", "2026-09"):
            add(m + "-28", -15.49, "NETFLIX.COM", "card", "subscriptions")
        if m in ("2026-08", "2026-09", "2026-10"):
            add(m + "-22", -2.99, "APPLE.COM/BILL", "card", "subscriptions")
            add(m + "-22", -10.99, "APPLE.COM/BILL", "card", "subscriptions")
        if m in ("2026-08", "2026-09", "2026-10", "2026-11"):
            add(m + "-10", -25.00, "PLANET FITNESS", "card", "health")
        if m in ("2026-07", "2026-08"):
            add(m + "-14", -9.99, "HULU 877-8244858", "card", "subscriptions")
        for i, day in enumerate(("03", "08", "13", "19", "24", "29")):
            if m == "2026-11" and day > "14":
                continue
            add(f"{m}-{day}", -(28.0 + i), "DOORDASH*DASHPASS ORDER", "card", "food")
        if m != "2026-11":
            add(m + "-12", -84.12 - 7 * int(m[5:7]) + 70, "KROGER #1234", "card", "food")      # Jul 63.12, Aug 70.12 ... Oct 84.12 (a store, not a bill)
            add(m + "-20", -41.00 - int(m[5:7]) + 7, "SHELL OIL 57444123456", "card", "gas")
    add("2026-10-28", -17.99, "NETFLIX.COM", "card", "subscriptions")            # price rise: 15.49 -> 17.99
    for d in ("2026-10-02", "2026-10-09", "2026-10-16", "2026-10-23", "2026-10-30", "2026-11-06", "2026-11-13"):
        add(d, -4.00, "NYTIMES DIGITAL", "card", "other")                        # weekly
    add("2025-11-20", -139.00, "AMAZON PRIME MEMBERSHIP", "card", "subscriptions")
    add("2026-11-12", -139.00, "AMAZON PRIME MEMBERSHIP", "card", "subscriptions")  # yearly (357 days)
    add("2026-10-18", -91.80, "MYFUNDEDFUTURES.COM", "card", "prop_fees")
    add("2026-11-02", -65.00, "LUCID TRADING LLC", "card", "prop_fees")
    add("2026-11-10", 500.00, "MYFUNDEDFUTURES PAYOUT", "bank", "prop_payout")
    add("2026-09-10", -200.00, "KALSHI INC DEPOSIT", "bank", "kalshi_deposit")
    add("2026-10-20", 150.00, "KALSHI INC WITHDRAWAL", "bank", "kalshi_withdrawal")
    add("2026-10-06", -35.00, "OVERDRAFT FEE", "bank", "bank_fees")
    add("2026-10-14", -6.50, "STARBUCKS STORE 01234", "card", "food")
    add("2026-10-14", -6.50, "STARBUCKS STORE 01234", "card", "food")            # two equal coffees, one day: both count
    return rows


def write_exports(d, rows, card_from=None, card_to=None, name_card="card.csv", name_bank="bank.csv"):
    card = ["Transaction Date,Post Date,Description,Category,Type,Amount,Memo"]
    bank = ["Details,Posting Date,Description,Amount,Type,Balance,Check or Slip #"]
    for date, amt, desc, f, _ in sorted(rows, key=lambda r: r[0], reverse=True):
        mdy = f"{date[5:7]}/{date[8:10]}/{date[:4]}"
        if f == "card" and (card_from is None or card_from <= date <= card_to):
            card.append(f'{mdy},{mdy},"{desc}",,{"Payment" if amt > 0 else "Sale"},{amt:.2f},')
        elif f == "bank" and card_from is None:
            bank.append(f'{"CREDIT" if amt > 0 else "DEBIT"},{mdy},"{desc}",{amt:.2f},ACH,1000.00,,')
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, name_card), "w", encoding="utf-8", newline="") as fh:
        fh.write("\r\n".join(card) + "\r\n")
    if card_from is None:
        with open(os.path.join(d, name_bank), "w", encoding="utf-8", newline="") as fh:
            fh.write("\r\n".join(bank) + "\r\n")


def fresh_ledger(paths):
    led = MI.empty_ledger()
    rep = MI.import_paths(led, paths, TODAY)
    return led, rep


# ------------------------------------------------------------------------------------------------ b + c. privacy and de-dup
def test_privacy_dedup(tmp):
    allfx = sorted(os.path.join(FIX, n) for n in os.listdir(FIX))
    led, rep = fresh_ledger(allfx)
    text = json.dumps(led)
    leaked = [n for n in FAKE_NUMBERS if n in text]
    check("b. the private ledger holds no account / card / reference number from any fixture", not leaked, leaked)
    check("b. the ledger keeps no file names (they can hold an account's last digits)", "chase_card.csv" not in text and "Chase1234" not in text)
    check("b. scrub: 'CARD 4321', 'XXXX1234', 'ending in 5678', 'a@b.com', 'S308289123456' are masked; 'SHELL OIL' stays",
          MI.scrub("PUBLIX CARD 4321 XXXX1234 ending in 5678 a@b.com S308289123456 SHELL OIL") == "PUBLIX # [email] S# SHELL OIL",
          MI.scrub("PUBLIX CARD 4321 XXXX1234 ending in 5678 a@b.com S308289123456 SHELL OIL"))
    doc = MI.build(led, MI.DEFAULT_RULES_DOC, TODAY)
    t = json.dumps(doc)
    strs = []

    def walk(x):
        if isinstance(x, str):
            strs.append(x)
        elif isinstance(x, dict):
            [walk(v) for v in x.values()]
        elif isinstance(x, list):
            [walk(v) for v in x]
    walk(doc)
    check("b. the summary has no account number and no 5+ digit run in any string", not [n for n in FAKE_NUMBERS if n in t] and not [s for s in strs if MI.long_digits(s)],
          [s for s in strs if MI.long_digits(s)][:5])
    names = ("NETFLIX", "Netflix", "SPOTIFY", "Spotify", "DOORDASH", "KROGER", "STARBUCKS", "Roommate", "Jane Doe", "PUBLIX", "WHOLEFDS")
    check("b. no merchant or person name in the summary by default", not [n for n in names if n in t], [n for n in names if n in t])
    check("b. the guard masks a 5+ digit run that slips into a string", MI.guard_public({"a": ["ref 1234567 ok", "2026-11-14"]}) == ({"a": ["ref # ok", "2026-11-14"]}, 1))
    # de-dup
    again = MI.import_paths(led, allfx, TODAY)
    check("c. the same files again: all skipped as already imported", all(r["state"] == "already imported" for r in again if r["layout"]) and len(led["txns"]) == sum(r.get("added", 0) for r in rep))
    forced = MI.import_paths(led, [fx("chase_card.csv")], TODAY, force=True)
    check("c. the same file forced (a renamed copy): 0 new rows, 7 duplicates", forced[0]["added"] == 0 and forced[0]["dupes"] == 7, forced)
    d = os.path.join(tmp, "dedup")
    rows = household_rows()
    write_exports(d, rows)
    write_exports(d, rows, "2026-10-15", "2026-11-14", name_card="card_overlap.csv")
    led2, rep2 = fresh_ledger([os.path.join(d, "card.csv"), os.path.join(d, "bank.csv"), os.path.join(d, "card_overlap.csv")])
    n_over = len([r for r in rows if r[3] == "card" and "2026-10-15" <= r[0] <= TODAY])
    check("c. an overlapping export (Oct 15 - Nov 14 again) adds nothing new", rep2[2]["added"] == 0 and rep2[2]["dupes"] == n_over and len(led2["txns"]) == len(rows),
          (rep2[2], n_over, len(led2["txns"]), len(rows)))
    sb = [t for t in led2["txns"] if t["date"] == "2026-10-14" and "STARBUCKS" in t["desc"]]
    check("c. two equal coffees on one day are two rows", len(sb) == 2 and sb[0]["id"] != sb[1]["id"], sb)
    inbox = os.path.join(tmp, "cash.jsonl")
    with open(inbox, "w") as fh:
        fh.write(json.dumps({"id": "c1", "kind": "expense", "amount": 12.5, "what": "Tacos", "cat": "food", "date": "2026-11-13"}) + "\n")
        fh.write(json.dumps({"id": "b1", "kind": "balance", "name": "Checking", "amount": 3200, "date": "2026-11-13"}) + "\n")
        fh.write("not json\n")
    l3 = MI.empty_ledger()
    r1 = MI.import_paths(l3, [inbox], TODAY)
    with open(inbox, "a") as fh:
        fh.write(json.dumps({"id": "c2", "kind": "income", "amount": 40, "what": "Sold a chair", "date": "2026-11-14"}) + "\n")
    r2 = MI.import_paths(l3, [inbox], TODAY)
    check("c. iPhone inbox: one cash row + one balance, a bad line skipped; read again, only the new line is added and the balance is not re-applied",
          r1[0]["added"] == 1 and r1[0]["skipped"] == 1 and [b["name"] for b in r1[0]["balances"]] == ["Checking"] and r2[0]["added"] == 1 and r2[0]["dupes"] == 1
          and r2[0]["balances"] == [] and sorted(t["amount"] for t in l3["txns"]) == [-12.5, 40.0], (r1, r2, l3["txns"]))


# ------------------------------------------------------------------------------------------------ d. rules
def test_rules():
    R = MI.compile_rules(MI.DEFAULT_RULES_DOC)
    c = lambda desc, amt, **kw: MI.categorize({"desc": desc, "amount": amt, **kw}, R)["cat"]  # noqa: E731
    check("d. whole words: PARENT / CURRENT are not rent, RENT PAYMENT is", (c("PARENT TEACHER ASSOC", -5), c("CURRENT ENERGY", -5), c("RENT PAYMENT", -5)) == ("other", "utilities", "rent"))
    check("d. direction: MFFU out = prop fee, in = payout; Kalshi out = deposit, in = withdrawal",
          (c("MYFUNDEDFUTURES", -91.8), c("MFFU PAYOUT", 500), c("KALSHI", -100), c("KALSHI", 80)) == ("prop_fees", "prop_payout", "kalshi_deposit", "kalshi_withdrawal"))
    check("d. first match wins: UBER EATS is food, UBER is a ride; AMAZON PRIME a subscription, AMAZON shopping",
          (c("UBER EATS 1234", -20), c("UBER TRIP", -12), c("AMAZON PRIME", -14.99), c("AMAZON MKTPLACE", -30)) == ("food", "transport", "subscriptions", "shopping"))
    check("d. a paycheck rule only takes money in (an ADP fee out is not income)", (c("ADP PAYROLL", 1000), c("ADP FEE", -10)) == ("income", "other"))
    check("d. P2P: Zelle out = people, Zelle in = other money in; Zelle 'transfer to' is not an own transfer",
          (c("ZELLE TO JOHN", -50), c("ZELLE FROM ANN", 50), c("Zelle Transfer to John", -50)) == ("people", "income_other", "people"))
    check("d. the bank's category when no rule matches; nothing = other / other money in",
          (c("BLUE DOOR", -9, bank_cat="Food & Drink"), c("BLUE DOOR", -9), c("BLUE DOOR", 9)) == ("food", "other", "income_other"))
    check("d. a card's own 'Payment' row is an own transfer; Venmo's 'Payment' is a person", (c("THANKS", 100, kind="payment", source="apple_card"), c("x", -10, kind="payment", source="venmo")) == ("transfer", "people"))
    own = {"rules": [{"match": ["BLUE DOOR"], "category": "food", "label": "Cafe"}, {"match": ["junk"], "category": "nope"}], "overrides": {"abc": "rent"}}
    R2 = MI.compile_rules(own)
    check("d. the owner's rules file: his rule is used, a rule with an unknown category is dropped, an override by row id wins",
          (len(R2), MI.categorize({"desc": "BLUE DOOR", "amount": -3}, R2)["cat"], MI.categorize({"id": "abc", "desc": "BLUE DOOR", "amount": -3}, R2, own["overrides"])["cat"]) == (1, "food", "rent"))


# ------------------------------------------------------------------------------------------------ e + f. subscriptions and the summary
def test_summary(tmp):
    rows = household_rows()
    d = os.path.join(tmp, "house")
    write_exports(d, rows)
    led, _ = fresh_ledger([os.path.join(d, "card.csv"), os.path.join(d, "bank.csv")])
    cls = MI.classify(led, MI.DEFAULT_RULES_DOC)
    want = {}
    for r in rows:
        want.setdefault((r[0], round(r[1], 2), r[4]), 0)
        want[(r[0], round(r[1], 2), r[4])] += 1
    got = {}
    for r in cls:
        got.setdefault((r["date"], r["amount"], r["cat"]), 0)
        got[(r["date"], r["amount"], r["cat"])] += 1
    check("e. every synthetic row lands in its intended category", got == want, sorted(set(got.items()) ^ set(want.items()))[:6])
    bal = {"accounts": [{"name": "Checking", "kind": "cash", "usd": 3000}, {"name": "Savings", "kind": "savings", "usd": 6000},
                        {"name": "Kalshi", "kind": "kalshi", "usd": None}, {"name": "Visa 4111111111111111", "kind": "debt", "usd": 1200},
                        {"name": "Crypto", "kind": "crypto", "usd": None}]}
    hist = [{"date": "2026-10-10", "total": 10000.0}, {"date": "2026-11-01", "total": 11000.0}]
    doc = MI.build(led, MI.DEFAULT_RULES_DOC, TODAY, bal, 250.0, hist)
    subs = {(s["label"], s["every"], s["usd"]): s for s in doc["subscriptions"]["items"]}
    S = lambda lab, ev, usd: subs.get((lab, ev, usd))  # noqa: E731
    nf, sp, ap1, ap2, gym, ny, pr, hu = (S("Streaming", "month", 17.99), S("Music and audio", "month", 11.99), S("Apps and memberships", "month", 2.99),
                                         S("Apps and memberships", "month", 10.99), S("Gym", "month", 25.0), S("Other spending", "week", 4.0),
                                         S("Apps and memberships", "year", 139.0), S("Streaming", "month", 9.99))
    check("e. found: Netflix (price rise to 17.99), Spotify, two Apple plans, the gym, a weekly charge, a yearly one, a stopped Hulu",
          all((nf, sp, ap1, ap2, gym, ny, pr, hu)), sorted(subs))
    if all((nf, sp, ap1, ap2, gym, ny, pr, hu)):
        check("e. Netflix: price up $2.50, next 2026-11-28, active", (nf["price_up"], nf["next"], nf["active"]) == (2.5, "2026-11-28", True), nf)
        check("e. Spotify next 2026-12-05; the gym next 2026-12-10, a bill-type 'Gym' stays a subscription", (sp["next"], gym["next"], gym["type"]) == ("2026-12-05", "2026-12-10", "subscription"), (sp, gym))
        check("e. weekly $4 = $17.33 a month, next 2026-11-20", (ny["usd_month"], ny["next"]) == (17.33, "2026-11-20"), ny)
        check("e. yearly $139 = $11.58 a month, next 2027-11-12", (pr["usd_month"], pr["next"]) == (11.58, "2027-11-12"), pr)
        check("e. Hulu stopped in August: not active, not in the total", hu["active"] is False, hu)
        act = 17.99 + 11.99 + 2.99 + 10.99 + 25.0 + 17.33 + 11.58
        check("e. the monthly total of the active ones (rent is recurring too: a bill)", near(doc["subscriptions"]["usd_month"], act + 1450.0, 0.02), (doc["subscriptions"]["usd_month"], act + 1450))
    check("e. DoorDash six times a month (amounts vary), Kroger and gas monthly (amounts vary) are not subscriptions",
          not any(s["category"] in ("food", "gas") for s in doc["subscriptions"]["items"]), [s["label"] for s in doc["subscriptions"]["items"]])
    # f. October by hand
    oct_ = next(m for m in doc["months"] if m["month"] == "2026-10")
    oct_in = 2150 * 2
    oct_out = 1450 + 11.99 + 2.99 + 10.99 + 25 + sum(28.0 + i for i in range(6)) + 84.12 + 44 + 17.99 + 4 * 5 + 91.8 + 35 + 13.0
    check("f. October: in $4,300 (paychecks), out by hand (transfers and Kalshi left out), net", near(oct_["in"], oct_in) and near(oct_["out"], oct_out) and near(oct_["net"], oct_in - oct_out),
          (oct_["in"], oct_["out"], oct_in, oct_out))
    check("f. October food = DoorDash 183 + Kroger 84.12 + coffees 13 = 280.12; Kalshi net +150 apart", near(oct_["by_cat"]["food"], 280.12) and oct_["kalshi_net"] == 150.0, (oct_["by_cat"], oct_["kalshi_net"]))
    nov = doc["this_month"]
    check("f. this month (to Nov 14): in = 2150 + MFFU payout 500", near(nov["in"], 2650.0) and nov["partial"], nov["in"])
    check("f. prop firms: fees 91.80 + 65 = 156.80, payouts 500, net +343.20, ROI +218.88%, by firm MFFU / Lucid",
          (doc["prop"]["fees"], doc["prop"]["payouts"], doc["prop"]["net"], doc["prop"]["roi_pct"], sorted(f["firm"] for f in doc["prop"]["firms"])) == (156.8, 500.0, 343.2, 218.88, ["Lucid", "MFFU"]), doc["prop"])
    check("f. Kalshi: 200 sent, 150 back, -50 moved", (doc["kalshi"]["deposits"], doc["kalshi"]["withdrawals"], doc["kalshi"]["net_moved"]) == (200.0, 150.0, -50.0), doc["kalshi"])
    full = [m for m in doc["months"] if m["month"] in ("2026-08", "2026-09", "2026-10")]
    avg_out = sum(m["out"] for m in full) / 3
    check("f. 3-month average out = Aug-Oct; runway = (3000 + 6000) / that", near(doc["avg3"]["out"], avg_out) and near(doc["runway"]["months"], 9000 / round(avg_out, 2), 0.01),
          (doc["avg3"], doc["runway"]))
    nw = doc["networth"]
    check("f. net worth: 3000 + 6000 + Kalshi 250 (from the feed) - 1200 debt = 8050; crypto missing; +7050... change over 30 days = 8050 - 10000",
          (nw["total"], nw["assets"], nw["debts"], nw["liquid"], nw["missing"], nw["change_30d"]) == (8050.0, 9250.0, 1200.0, 9000.0, ["Crypto"], -1950.0), nw)
    check("f. an account name with a card number is masked in the summary", all("4111" not in a["name"] for a in nw["accounts"]), [a["name"] for a in nw["accounts"]])
    ids = [x["id"] for x in doc["leaks"]]
    check("f. leaks: overdraft fee, the delivery apps, the price rise, all subscriptions; sorted by $ a month",
          {"bank_fees", "delivery", "subs"} <= set(ids) and any(i.startswith("up:") for i in ids) and [x["usd_month"] for x in doc["leaks"]] == sorted((x["usd_month"] for x in doc["leaks"]), reverse=True), doc["leaks"])
    J = doc["jarvis"]
    check("f. Jarvis: food this month, subscriptions with $ and next dates, runway in months, net worth",
          J["food_month"].startswith("Food this month: $") and "a month" in J["subscriptions"] and "next 2026-" in J["subscriptions"] and "months on savings alone" in J["runway"] and "Net worth $8,050" in J["networth"], J)
    doc2 = MI.build(led, {**MI.DEFAULT_RULES_DOC, "privacy": {"publish_merchants": True}}, TODAY, bal, 250.0, hist)
    check("b. publish_merchants on: merchant names appear (Netflix)", "Netflix" in json.dumps(doc2) and "Netflix" not in json.dumps(doc))
    empty = MI.build(MI.empty_ledger(), MI.DEFAULT_RULES_DOC, TODAY)
    check("f. no data: status empty, honest words, nothing invented", empty["status"] == "empty" and empty["this_month"]["out"] == 0 and empty["networth"]["total"] is None and
          "No bank data" in empty["jarvis"]["food_month"] and "balances" in empty["runway"]["text"], empty["runway"])
    return led


# ------------------------------------------------------------------------------------------------ g. Oikos
def test_oikos(tmp, led):
    sys.path.insert(0, os.path.join(ROOT, "tools", "money"))
    import oikos as OK  # noqa: E402
    ol = MI.oikos_ledger(led, MI.DEFAULT_RULES_DOC, TODAY, 2500, 9000)
    norm = OK.normalize(ol, TODAY)
    a = OK.analyze(norm, TODAY)
    t = json.dumps(ol)
    check("g. the oikos ledger reads in oikos.py: no row skipped, prop fees / payouts per firm, subscriptions as monthly recurring entries",
          norm["skipped"] == 0 and a["totals"]["fees"] == 156.8 and a["totals"]["payouts"] == 500.0 and len(a["subs"]) >= 5, (norm["skipped"], a["totals"], len(a["subs"])))
    check("g. no merchant names or numbers in it", not any(n in t for n in ("NETFLIX", "Netflix", "SPOTIFY", "DOORDASH", "KROGER", "9876543210")))
    home = os.path.join(tmp, "okhome")
    os.makedirs(os.path.join(home, "money"))
    MI.write_json(os.path.join(home, "money", "oikos_ledger.json"), ol)
    out = os.path.join(tmp, "okout")
    env = {**os.environ, "OLYMPUS_HOME": home}
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "money", "oikos.py"), "--out", out, "--today", TODAY], capture_output=True, text=True, env=env, timeout=60)
    o = json.load(open(os.path.join(out, "oikos.json"))) if r.returncode == 0 else {}
    check("g. oikos.py with no --ledger picks up <home>/money/oikos_ledger.json (status ok, 'from your bank exports')",
          o.get("status") == "ok" and any("bank" in n for n in o.get("notes", [])), (r.stdout, r.stderr, o.get("status"), o.get("notes")))
    r2 = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "money", "oikos.py"), "--out", out, "--fixture", "--today", TODAY], capture_output=True, text=True, env=env, timeout=60)
    o2 = json.load(open(os.path.join(out, "oikos.json")))
    check("g. --fixture still gives the sample (the site build stays sample)", r2.returncode == 0 and o2["status"] == "sample")
    env3 = {**os.environ, "OLYMPUS_HOME": os.path.join(tmp, "nohome")}
    subprocess.run([sys.executable, os.path.join(ROOT, "tools", "money", "oikos.py"), "--out", out, "--today", TODAY], capture_output=True, text=True, env=env3, timeout=60)
    check("g. no oikos ledger: the sample, as before", json.load(open(os.path.join(out, "oikos.json")))["status"] == "sample")


# ------------------------------------------------------------------------------------------------ h. the CLI
def test_cli(tmp):
    home, out = os.path.join(tmp, "clihome"), os.path.join(tmp, "cliout")
    drop = os.path.join(home, "money_inbox")
    os.makedirs(drop)
    for n in ("chase_card.csv", "chase_bank.csv", "bank.ofx", "notes.txt"):
        shutil.copy(fx(n), os.path.join(drop, n))
    rules = os.path.join(tmp, "rules.json")
    env = {**os.environ, "USERPROFILE": tmp, "HOME": tmp}
    env.pop("OLYMPUS_MONEY_INBOX", None)
    cmd = [sys.executable, os.path.join(ROOT, "tools", "money_import.py"), "--home", home, "--out", out, "--rules", rules, "--today", TODAY]
    r = subprocess.run(cmd + ["--balance", "Checking=2500", "--balance", "Savings=$4,000.50", "--print"], capture_output=True, text=True, env=env, timeout=60)
    doc = json.load(open(os.path.join(out, "household.json"))) if os.path.exists(os.path.join(out, "household.json")) else {}
    check("h. the CLI: drop folder read, 16 rows, household.json + the private files written, the table printed",
          r.returncode == 0 and doc.get("data", {}).get("rows") == 16 and all(os.path.exists(os.path.join(home, "money", f)) for f in ("ledger.json", "balances.json", "networth_history.json", "oikos_ledger.json", "household.json"))
          and "| Money out |" in r.stdout, (r.returncode, r.stdout[-800:], r.stderr[-800:]))
    check("h. a junk file in the drop folder is reported, not imported", "not a bank export I know" in r.stdout)
    check("h. --balance: Checking 2500, Savings 4000.50 -> liquid 6500.50", doc.get("networth", {}).get("liquid") == 6500.5, doc.get("networth"))
    r2 = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=60)
    check("h. run again: nothing new, same rows", r2.returncode == 0 and json.load(open(os.path.join(out, "household.json")))["data"]["rows"] == 16 and "0 new rows" in r2.stdout, r2.stdout)
    r3 = subprocess.run(cmd + ["--init-rules"], capture_output=True, text=True, env=env, timeout=60)
    first = open(rules).read() if os.path.exists(rules) else ""
    with open(rules, "w") as fh:
        fh.write(first.replace('"publish_merchants": false', '"publish_merchants": false, "mine": 1'))
    r4 = subprocess.run(cmd + ["--init-rules"], capture_output=True, text=True, env=env, timeout=60)
    check("h. --init-rules writes the defaults once and never overwrites", r3.returncode == 0 and '"rules"' in first and "already exists" in r4.stdout and '"mine": 1' in open(rules).read())
    src = open(os.path.join(ROOT, "tools", "money_import.py"), encoding="utf-8").read()
    imports = set(re.findall(r"^(?:from|import) ([a-zA-Z_]+)", src, re.M))
    check("h. stdlib only, no network, no secrets read", imports <= {"__future__", "argparse", "csv", "datetime", "hashlib", "io", "json", "math", "os", "re", "sys", "zoneinfo"}
          and not re.search(r"urllib|requests|socket|http\.client|getpass|api_key", src, re.I), imports)
    gi = open(os.path.join(ROOT, ".gitignore"), encoding="utf-8").read()
    check("h. data/money_rules.json is gitignored (the private folder is outside the repo; .olympus/ ignored too)", "data/money_rules.json" in gi and ".olympus/" in gi)


# ------------------------------------------------------------------------------------------------ i. connected: scoreboard, private link, Oikos card, Jarvis
def test_connect(tmp, led):
    from tools import money_scoreboard as MS
    bal = {"accounts": [{"name": "Checking", "kind": "cash", "usd": 3000}, {"name": "Savings", "kind": "savings", "usd": 6000}]}
    doc = MI.build(led, MI.DEFAULT_RULES_DOC, TODAY, bal, None, [])
    now = 1794762000
    base = {"home": None, "kalshi": None, "machines": None, "rules": None, "plans": None, "ledger": None}
    priv = MS.build({**base, "household": doc, "household_file": "money_out/household.json"}, now, include_ledger=True)
    pub = MS.build({**base, "household": doc, "household_file": "money_out/household.json"}, now, include_ledger=False)
    off = MS.build(base, now, include_ledger=True)
    hb = priv.get("household") or {}
    src = lambda sb: next((s for s in sb["sources"] if s["id"] == "household"), {})  # noqa: E731
    check("i. scoreboard --private: a household block (this month in / out / net, runway, subscriptions, net worth, prop fees vs payouts from the bank)",
          hb.get("month") == "2026-11" and near(hb.get("in"), doc["this_month"]["in"]) and near(hb.get("out"), doc["this_month"]["out"]) and hb.get("runway_months") == doc["runway"]["months"]
          and hb.get("networth") == 9000.0 and hb["prop"]["fees"] == 156.8 and src(priv).get("status") == "ok" and "From your bank exports" in hb.get("text", ""), (hb, src(priv)))
    check("i. ... never added to the cash totals (those stay ledger + eval prices)", priv["totals"] == off["totals"], (priv["totals"]["all"], off["totals"]["all"]))
    check("i. the public scoreboard: no household numbers, the source says private", pub.get("household") is None and src(pub).get("status") == "private" and "9,000" not in json.dumps(pub), src(pub))
    check("i. no household file: the source is 'off' (not connected), not a missing source, and the table still prints",
          src(off).get("status") == "off" and "household" not in [m["id"] for m in off["missing"]] and "CONNECT_MONEY" in src(off).get("note", "") and MS.table(off), src(off))
    check("i. the scoreboard table prints the household line when private", "From your bank exports" in MS.table(priv))
    # the private link serves money_out/household.json; the public publisher never copies it
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import money_publish as MP  # noqa: E402
    ls_src = open(os.path.join(ROOT, "engine", "live_site.py"), encoding="utf-8").read()
    check("i. the PC's private link (engine/live_site.py) serves money/household.json from money_out/; tools/money_publish.py (the public site) never copies it",
          re.search(r'MONEY_KEEP = MONEY_KEEP \+ \("household",', ls_src) is not None and "household" not in MP.KEEP)   # + "agency" since B6 (2026-11-14)
    try:
        from engine import live_site as LS
        mo = os.path.join(tmp, "mo")
        MI.write_json(os.path.join(mo, "household.json"), doc)
        check("i. live_site.money_file('household.json') finds it in money_out; a path trick does not", LS.money_file("household.json", mo) == os.path.join(mo, "household.json") and LS.money_file("../household.json", mo) is None)
    except ImportError as e:
        check("i. live_site import skipped (no fastapi here)", True, e)
    site = os.path.join(tmp, "site")
    pubd = os.path.join(tmp, "pubsrc")
    MI.write_json(os.path.join(pubd, "household.json"), doc)
    MI.write_json(os.path.join(pubd, "index.json"), {"v": 1, "streams": []})
    MP.publish(pubd, site, quiet=True)
    check("i. money_publish run on a folder holding household.json: it is not copied to the site", not os.path.exists(os.path.join(site, "money", "household.json")) and os.path.exists(os.path.join(site, "money", "index.json")))
    # node: the Oikos card core and Jarvis
    if not shutil.which("node"):
        check("i. node not installed: the Oikos card and Jarvis checks were skipped", True)
        return
    p1, p2 = os.path.join(tmp, "hh.json"), os.path.join(tmp, "hh_old.json")
    MI.write_json(p1, doc)
    old = json.loads(json.dumps(doc))
    old["data"]["age_days"] = 60
    MI.write_json(p2, old)
    r = subprocess.run(["node", os.path.join(ROOT, "tests", "test_money_import_node.mjs"), p1, p2], capture_output=True, text=True, timeout=120, env={**os.environ, "TZ": "America/New_York"})
    try:
        o = json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        check("i. node harness ran", False, (r.stdout[-500:], r.stderr[-800:]))
        return
    v = o["view"]
    kp = dict(v["kpis"])
    check("i. Oikos card: state ok, this month's out / in / net, runway in months, subscriptions $ a month, net worth",
          v["state"] == "ok" and kp.get("Out in 2026-11") == MI.money(doc["this_month"]["out"]).replace("$", "$") and kp.get("Runway on savings", "").endswith("months") and kp.get("Net worth") == "$9,000", v["kpis"])
    check("i. Oikos card: spending by category biggest first (spend only), subscriptions with their next date, leaks",
          v["cats"] and v["cats"][0][0] == "Rent" and all(c[1] > 0 for c in v["cats"]) and any(s[3] == "2026-11-28" for s in v["subs"]) and v["leaks"] >= 1, (v["cats"], v["subs"]))
    check("i. Oikos card: no file / another file / empty / a 60-day-old export -> off / off / empty / stale; the off line says how to connect",
          o["off"][:4] == ["off", "off", "empty", "stale"] and "tools/bat/RUN_MONEY.bat" in o["off"][4], o["off"])
    check("i. Oikos card money words", o["usd"] == ["$1,235", "-$12.50", "$15.49", "$0", "-", "+$50"], o["usd"])
    check("i. Jarvis routes the owner's questions: food this month, subscriptions, savings runway, this month's spending, net worth, gas last month",
          o["routes"] == ["household_spend_cat", "household_subs", "household_runway", "household_month", "household_networth", "household_spend_cat"], o["routes"])
    A = o["answers"]
    food = next((m["by_cat"].get("food") for m in doc["months"] if m["month"] == "2026-11"), 0)
    gas_oct = next((m["by_cat"].get("gas") for m in doc["months"] if m["month"] == "2026-10"), 0)
    check("i. Jarvis: food this month in $ (and last month), from money/household.json", A[0] and f"Food in 2026-11 so far: {MI.money(food)}" in A[0]["text"].replace(".00", "") and "money/household.json" in A[0]["text"], A[0])
    check("i. Jarvis: the subscriptions with $ and next dates; runway in months; net worth; gas last month",
          "next 2026-" in A[1]["text"] and "months on savings alone" in A[2]["text"] and "Net worth $9,000" in A[4]["text"] and f"Gas in 2026-10: ${gas_oct:.0f}" in A[5]["text"], [a["text"][:160] for a in A])
    check("i. Jarvis: this month's money in / out / net and the biggest categories", "2026-11 so far:" in A[3]["text"] and "Biggest:" in A[3]["text"], A[3]["text"])
    check("i. Jarvis without the file: 'I don't have that', nothing invented", o["missing"] and o["missing"]["missing"] and o["missing"]["text"].startswith("I don't have that") and "$" not in o["missing"]["text"], o["missing"])


def main():
    tmp = tempfile.mkdtemp(prefix="money-import-test-")
    try:
        test_layouts()
        test_privacy_dedup(tmp)
        test_rules()
        led = test_summary(tmp)
        test_oikos(tmp, led)
        test_cli(tmp)
        test_connect(tmp, led)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    bad = RES.count(False)
    print(f"\n{len(RES) - bad}/{len(RES)} passed")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
