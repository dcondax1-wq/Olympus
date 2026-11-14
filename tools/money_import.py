#!/usr/bin/env python3
"""MONEY IMPORT (owner 2026-11-14, "connect the money"): your own bank / card exports -> a private ledger + a small summary. Free, private.

  python tools/money_import.py                 import every new file in the drop folder, write the private ledger and money_out/household.json
  python tools/money_import.py --print         the same, then print the plain table
  python tools/money_import.py --file X.csv    import one file from anywhere (it is not moved or changed)
  python tools/money_import.py --balance "Checking=1234.56"   set one balance in your net-worth file (repeatable)
  python tools/money_import.py --init-rules    write the default category rules to data/money_rules.json (never overwrites)
  options: --home DIR (the private folder, default %USERPROFILE%\\.olympus)  --inbox DIR (another drop folder)  --out DIR (default money_out)
           --rules FILE (default data/money_rules.json)  --today YYYY-MM-DD  --quiet

How it works (nothing here logs in anywhere, nothing is sent, no paid aggregator, no bank password):
  1. You download a CSV / OFX / QFX export on your bank's own site and drop it in  %USERPROFILE%\\.olympus\\money_inbox\\
     (or %USERPROFILE%\\OlympusMoneyInbox\\, or OLYMPUS_MONEY_INBOX). The layout is found by itself: Chase (checking + card), Bank of America
     (checking + card), Wells Fargo, Capital One (card + 360), Apple Card, Cash App, PayPal, Venmo, Amex, Discover, any OFX / QFX, and a
     generic "date, description, amount" CSV. The files are left where they are.
  2. Every row is cleaned: account and card numbers are never kept (any run of 4+ digits in a description is masked, number columns are
     dropped), and each row gets a fingerprint so a file imported twice, or two exports that overlap, never count twice.
  3. Rules sort each row into a category (data/money_rules.json, gitignored, yours to edit; the first rule that matches wins): rent, food,
     gas, subscriptions, prop-firm fees (MFFU, Lucid, ...), prop-firm payouts, Kalshi deposits / withdrawals, paycheck, transfers between
     your own accounts (ignored), ...
  4. Out come
       PRIVATE  <home>/money/ledger.json        every cleaned row (gitignored folder outside the repo; never published)
       PRIVATE  <home>/money/balances.json      your net-worth list (accounts, crypto, Kalshi, payouts owed); edit it or use --balance
       PRIVATE  <home>/money/networth_history.json  one net-worth point a day
       SUMMARY  <out>/household.json            monthly in / out, by category, subscriptions ($ a month + next date), prop-firm ROI, net
                                                 cash flow, runway, money leaks, net worth, and short answers for Jarvis. No account
                                                 numbers ever; no merchant names unless "privacy": {"publish_merchants": true} in the rules.
                                                 It reaches the phone only through the PC's private Tailscale link (engine/live_site.py
                                                 serves money_out/), never the public site.
       OIKOS    <home>/money/oikos_ledger.json  the same money in the Ledger's export format (category level), so tools/money/oikos.py
                                                 finds the leaks in your real bank data
  Cash entries from the iPhone Shortcut (tools/money_inbox_server.py -> <home>/money_inbox/cash.jsonl) are read the same way.

Paper only: nothing here trades or touches the bot. Stdlib only. Test: python -X utf8 -m tests.test_money_import
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DEFAULT_RULES = os.path.join(ROOT, "data", "money_rules.json")
DEFAULT_OUT = os.path.join(ROOT, "money_out")
VERSION = 1
MAX_FILE = 25 * 1024 * 1024
MAX_ROWS = 200_000
DPM = 30.4375

# ------------------------------------------------------------------------------------------------ categories
# kind: spend (money out, refunds lower it), income (money in), move (your money moving somewhere you still own), ignore (own transfers)
CATS = {
    "rent": ("Rent", "spend"), "food": ("Food", "spend"), "gas": ("Gas", "spend"), "subscriptions": ("Subscriptions", "spend"),
    "trading_tools": ("Trading tools and data", "spend"), "utilities": ("Phone, internet, power", "spend"), "transport": ("Car and rides", "spend"),
    "shopping": ("Shopping", "spend"), "health": ("Health and gym", "spend"), "bank_fees": ("Bank fees and interest", "spend"),
    "cash": ("Cash (ATM)", "spend"), "people": ("Sent to people", "spend"), "prop_fees": ("Prop-firm fees", "spend"), "other": ("Other spending", "spend"),
    "income": ("Paycheck", "income"), "prop_payout": ("Prop-firm payouts", "income"), "income_other": ("Other money in", "income"),
    "kalshi_deposit": ("Kalshi deposits", "move"), "kalshi_withdrawal": ("Kalshi withdrawals", "move"), "transfer": ("Transfers between your accounts", "ignore"),
}
BILLS = ("rent", "utilities", "transport", "health")
P2P_APPS = ("venmo", "cash_app", "paypal")
LOOSE_CATS = ("subscriptions", "trading_tools", "utilities", "rent", "health")   # recurring bills whose amount may move a little
CARDS = ("chase_card", "bofa_card", "capone_card", "apple_card", "discover", "amex", "generic_card", "ofx_card")   # recurring charges here are "bills", the rest "subscriptions"

# the default rules: first match wins; "match" = words / phrases found in the description (case and spacing ignored, whole words);
# "category" = one category, or {"out": .., "in": ..} by the direction of the money; "label" = a GENERIC name (published); "sub" = a sub-group
DEFAULT_RULES_DOC = {
    "v": 1,
    "note": "Your money rules (tools/money_import.py). First match wins. Edit freely: add words to 'match', change a 'category'. "
            "'label' is the generic name shown on the phone. 'overrides' maps a row id (from the private ledger) to a category. "
            "privacy.publish_merchants true shows merchant names on the phone (default false).",
    "privacy": {"publish_merchants": False},
    "overrides": {},
    "rules": [
        {"match": ["KALSHI"], "category": {"out": "kalshi_deposit", "in": "kalshi_withdrawal"}, "label": "Kalshi"},
        {"match": ["MYFUNDEDFUTURES", "MY FUNDED FUTURES", "MFFU"], "category": {"out": "prop_fees", "in": "prop_payout"}, "label": "MFFU"},
        {"match": ["LUCID TRADING", "LUCIDTRADING", "LUCID FUNDED"], "category": {"out": "prop_fees", "in": "prop_payout"}, "label": "Lucid"},
        {"match": ["TOPSTEP", "TOPSTEPTRADER"], "category": {"out": "prop_fees", "in": "prop_payout"}, "label": "Topstep"},
        {"match": ["APEX TRADER", "APEXTRADER", "APEX TRADER FUNDING"], "category": {"out": "prop_fees", "in": "prop_payout"}, "label": "Apex"},
        {"match": ["TAKE PROFIT TRADER", "TAKEPROFITTRADER"], "category": {"out": "prop_fees", "in": "prop_payout"}, "label": "Take Profit Trader"},
        {"match": ["FUNDEDNEXT", "FUNDED NEXT"], "category": {"out": "prop_fees", "in": "prop_payout"}, "label": "FundedNext"},
        {"match": ["TRADEIFY", "ALPHA FUTURES", "ALPHAFUTURES", "BULENOX", "TRADEDAY", "ELITE TRADER FUNDING", "FUNDINGTICKS", "EARN2TRADE"],
         "category": {"out": "prop_fees", "in": "prop_payout"}, "label": "Other prop firm"},
        {"match": ["RISEWORKS", "RISE WORKS", "RISE PAYOUT", "DEEL", "PLANE PAYOUT"], "category": {"out": "other", "in": "prop_payout"}, "label": "Payout platform"},
        {"match": ["PAYMENT THANK YOU", "PAYMENT RECEIVED THANK", "PAYMENT - THANK YOU", "AUTOPAY", "AUTO PAY", "AUTOMATIC PAYMENT", "ONLINE PAYMENT", "CREDIT CARD PAYMENT",
                   "CRD AUTOPAY", "EPAYMENT", "MOBILE PMT", "MOBILE PYMT", "ONLINE PYMT", "ONLINE TRANSFER", "INTERNAL TRANSFER", "APPLECARD GSBANK", "ACH CREDIT CARD",
                   "STANDARD TRANSFER", "INSTANT TRANSFER", "BANK DEPOSIT TO PP", "GENERAL CARD DEPOSIT", "USER INITIATED WITHDRAWAL", "CASH OUT", "CASHOUT", "ADD CASH"],
         "category": "transfer", "label": "Own transfer"},
        {"match": ["ZELLE", "VENMO", "CASH APP", "SQUARE CASH", "SQC", "APPLE CASH"], "category": {"out": "people", "in": "income_other"}, "label": "People"},
        {"match": ["TRANSFER TO", "TRANSFER FROM", "XFER TO", "XFER FROM", "TRANSFER"], "category": "transfer", "label": "Own transfer"},
        {"match": ["TRADINGVIEW", "NINJATRADER", "RITHMIC", "TRADOVATE", "CQG", "DATABENTO", "POLYGON IO"], "category": "trading_tools", "label": "Trading tools"},
        {"match": ["PAYROLL", "DIRECT DEP", "DIR DEP", "DIRECT DEPOSIT", "GUSTO", "ADP", "PAYCHEX", "SALARY", "PAYCHECK", "WAGES"], "dir": "in", "category": "income", "label": "Paycheck"},
        {"match": ["IRS TREAS", "TAX REFUND", "STATE TAX REFUND"], "dir": "in", "category": "income_other", "label": "Tax refund"},
        {"match": ["INTEREST PAID", "INTEREST PAYMENT", "INTEREST EARNED", "DIVIDEND"], "dir": "in", "category": "income_other", "label": "Interest"},
        {"match": ["RENT", "APARTMENT", "APARTMENTS", "APTS", "PROPERTY MANAGEMENT", "PROPERTY MGMT", "LEASING OFFICE", "BILT", "ZILLOW RENT", "APPFOLIO",
                   "RENTCAFE", "YARDI", "AVAIL RENT", "MORTGAGE"], "category": "rent", "label": "Rent"},
        {"match": ["DOORDASH", "UBER EATS", "UBEREATS", "GRUBHUB", "POSTMATES", "SEAMLESS", "CAVIAR"], "category": "food", "sub": "delivery", "label": "Delivery apps"},
        {"match": ["INSTACART", "WALMART GROCERY", "KROGER", "PUBLIX", "ALDI", "TRADER JOE", "WHOLE FOODS", "WHOLEFDS", "SAFEWAY", "HEB", "H E B", "MEIJER",
                   "WINCO", "FOOD LION", "WEGMANS", "GIANT EAGLE", "SPROUTS", "COSTCO WHSE", "SAMS CLUB", "HARRIS TEETER", "ALBERTSONS", "VONS", "RALPHS",
                   "FOOD 4 LESS", "PIGGLY WIGGLY", "GROCERY", "SUPERMARKET", "WALMART", "WAL MART", "WM SUPERCENTER"], "category": "food", "sub": "groceries", "label": "Groceries"},
        {"match": ["MCDONALD", "MCDONALDS", "CHICK FIL A", "CHIPOTLE", "STARBUCKS", "DUNKIN", "TACO BELL", "WENDYS", "WENDY S", "BURGER KING", "SUBWAY",
                   "DOMINOS", "PIZZA", "PANERA", "SONIC DRIVE", "POPEYES", "KFC", "FIVE GUYS", "WINGSTOP", "RESTAURANT", "CAFE", "GRILL", "SUSHI", "DINER",
                   "TST", "BUFFALO WILD", "OLIVE GARDEN", "APPLEBEES", "IHOP", "DENNYS", "JERSEY MIKES", "JIMMY JOHNS", "RAISING CANES", "WHATABURGER",
                   "IN N OUT", "SHAKE SHACK", "PANDA EXPRESS", "ARBYS", "DAIRY QUEEN", "CRACKER BARREL", "BAR", "TAVERN", "BAKERY", "COFFEE"],
         "category": "food", "sub": "eating_out", "label": "Eating out"},
        {"match": ["NETFLIX", "HULU", "DISNEY PLUS", "DISNEYPLUS", "HBO MAX", "HBOMAX", "MAX COM", "PARAMOUNT", "PEACOCK", "PRIME VIDEO", "CRUNCHYROLL",
                   "ESPN PLUS", "SLING", "YOUTUBE TV", "FUBO", "PHILO"], "category": "subscriptions", "label": "Streaming"},
        {"match": ["SPOTIFY", "APPLE MUSIC", "PANDORA", "TIDAL", "SIRIUSXM", "SIRIUS XM", "AUDIBLE", "YOUTUBE PREMIUM", "YOUTUBEPREMIUM", "GOOGLE YOUTUBE"],
         "category": "subscriptions", "label": "Music and audio"},
        {"match": ["OPENAI", "CHATGPT", "ANTHROPIC", "CLAUDE AI", "MIDJOURNEY", "PERPLEXITY", "CURSOR", "GITHUB", "COPILOT"], "category": "subscriptions", "label": "AI and dev tools"},
        {"match": ["ICLOUD", "APPLE COM BILL", "GOOGLE ONE", "GOOGLE STORAGE", "DROPBOX", "MICROSOFT 365", "MICROSOFT", "MSFT", "ADOBE", "NOTION", "CANVA",
                   "AMAZON PRIME", "AMZN PRIME", "PRIME MEMBERSHIP", "WALMART PLUS"], "category": "subscriptions", "label": "Apps and memberships"},
        {"match": ["PLAYSTATION", "SONY INTERACTIVE", "XBOX", "NINTENDO", "STEAM", "STEAMGAMES", "EPIC GAMES", "DISCORD", "TWITCH", "PATREON", "ROBLOX"],
         "category": "subscriptions", "label": "Games and creators"},
        {"match": ["PLANET FITNESS", "LA FITNESS", "CRUNCH FITNESS", "ANYTIME FITNESS", "GOLDS GYM", "EQUINOX", "YMCA", "GYM", "24 HOUR FITNESS", "ORANGETHEORY"],
         "category": "health", "label": "Gym"},
        {"match": ["CVS", "WALGREENS", "PHARMACY", "RITE AID", "DENTAL", "DENTIST", "DOCTOR", "MEDICAL", "HOSPITAL", "CLINIC", "URGENT CARE", "OPTOMETR"],
         "category": "health", "label": "Health"},
        {"match": ["VERIZON", "T MOBILE", "TMOBILE", "AT T", "ATT", "XFINITY", "COMCAST", "SPECTRUM", "COX COMM", "GOOGLE FI", "MINT MOBILE", "VISIBLE",
                   "CRICKET", "BOOST MOBILE", "METRO BY T"], "category": "utilities", "label": "Phone and internet"},
        {"match": ["ELECTRIC", "ENERGY", "POWER CO", "WATER", "UTILITY", "UTILITIES", "DUKE ENERGY", "CON ED", "CONED", "PG E", "FPL", "DOMINION", "GAS CO",
                   "NATIONAL GRID", "XCEL", "ENTERGY", "GEORGIA POWER", "SEWER", "TRASH", "WASTE MANAGEMENT"], "category": "utilities", "label": "Power and water"},
        {"match": ["SHELL", "EXXON", "EXXONMOBIL", "CHEVRON", "BP", "SUNOCO", "MARATHON", "SPEEDWAY", "WAWA", "SHEETZ", "CIRCLE K", "QUIKTRIP", "QT",
                   "7 ELEVEN", "VALERO", "CITGO", "MOBIL", "PHILLIPS 66", "CONOCO", "RACETRAC", "MURPHY USA", "MURPHY EXPRESS", "LOVES", "PILOT", "CASEYS",
                   "COSTCO GAS", "SAMS FUEL", "ARCO", "GAS STATION", "FUEL"], "category": "gas", "label": "Gas"},
        {"match": ["GEICO", "PROGRESSIVE", "STATE FARM", "ALLSTATE", "LIBERTY MUTUAL", "USAA", "NATIONWIDE", "FARMERS INS"], "category": "transport", "label": "Insurance"},
        {"match": ["UBER", "LYFT", "PARKING", "TOLL", "E ZPASS", "EZPASS", "SUNPASS", "AUTOZONE", "JIFFY LUBE", "OREILLY", "ADVANCE AUTO", "CAR WASH",
                   "TOYOTA FIN", "HONDA FIN", "ALLY AUTO", "CARMAX", "DMV", "TESLA"], "category": "transport", "label": "Car and rides"},
        {"match": ["OVERDRAFT", "NSF", "SERVICE FEE", "SERVICE CHARGE", "MONTHLY FEE", "MAINTENANCE FEE", "LATE FEE", "INTEREST CHARGE", "FINANCE CHARGE",
                   "FOREIGN TRANSACTION FEE", "ATM FEE", "RETURNED ITEM", "CASH ADVANCE FEE"], "dir": "out", "category": "bank_fees", "label": "Bank fees"},
        {"match": ["ATM WITHDRAWAL", "ATM WITHDRAW", "ATM", "CASH WITHDRAWAL"], "dir": "out", "category": "cash", "label": "Cash"},
        {"match": ["AMAZON", "AMZN", "TARGET", "BEST BUY", "EBAY", "ETSY", "SHEIN", "TEMU", "NIKE", "APPLE STORE", "HOME DEPOT", "LOWES", "IKEA", "MACYS",
                   "KOHLS", "TJ MAXX", "TJMAXX", "MARSHALLS", "ROSS STORES", "DOLLAR TREE", "DOLLAR GENERAL", "FAMILY DOLLAR", "GAMESTOP", "FOOT LOCKER"],
         "category": "shopping", "label": "Shopping"},
    ],
}

# the bank's own category column (Chase, Apple Card, Capital One, Discover ...) when no rule matched
BANK_CATS = (("restaurant", "food", "eating_out"), ("food", "food", "eating_out"), ("dining", "food", "eating_out"), ("grocer", "food", "groceries"),
             ("supermarket", "food", "groceries"), ("gas", "gas", None), ("fuel", "gas", None), ("automotive", "transport", None),
             ("travel", "transport", None), ("transport", "transport", None), ("entertainment", "subscriptions", None), ("utilit", "utilities", None),
             ("phone", "utilities", None), ("health", "health", None), ("medical", "health", None), ("pharmac", "health", None),
             ("shopping", "shopping", None), ("merchandise", "shopping", None), ("fee", "bank_fees", None), ("interest", "bank_fees", None),
             ("payment", "transfer", None), ("bills", "utilities", None), ("home", "shopping", None))


# ------------------------------------------------------------------------------------------------ small helpers
def r2(x) -> float:
    return math.floor(float(x) * 100 + 0.5) / 100 if x >= 0 else -math.floor(-float(x) * 100 + 0.5) / 100


def money(x, signed=False) -> str:
    if x is None:
        return "-"
    v = r2(x)
    a = abs(v)
    s = "${:,.0f}".format(a) if a >= 100 or a == int(a) else "${:,.2f}".format(a)
    if a == 0:
        return "$0"
    return ("-" if v < 0 else "+" if signed else "") + s


def read_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def write_json(path, doc, indent=None):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, indent=indent, separators=None if indent else (",", ":"), ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, path)
    return path


def olympus_dir(env=None) -> str:
    env = os.environ if env is None else env
    return env.get("OLYMPUS_HOME") or os.path.join(env.get("USERPROFILE") or os.path.expanduser("~"), ".olympus")


def inbox_dirs(home: str, extra=None, env=None) -> list:
    """the drop folders, in order: --inbox, OLYMPUS_MONEY_INBOX, <home>/money_inbox, <user>/OlympusMoneyInbox (repo-independent fallback)"""
    env = os.environ if env is None else env
    user = env.get("USERPROFILE") or os.path.expanduser("~")
    out = []
    for d in (extra, env.get("OLYMPUS_MONEY_INBOX"), os.path.join(home, "money_inbox"), os.path.join(user, "OlympusMoneyInbox")):
        if d and os.path.abspath(d) not in [os.path.abspath(x) for x in out]:
            out.append(d)
    return out


def add_days(s: str, n: int) -> str:
    return (dt.date.fromisoformat(s) + dt.timedelta(days=n)).isoformat()


def add_months(s: str, n: int) -> str:
    y, m, d = (int(x) for x in s.split("-"))
    m += n
    y += (m - 1) // 12
    m = (m - 1) % 12 + 1
    nxt = dt.date(y + (1 if m == 12 else 0), 1 if m == 12 else m + 1, 1)
    return "%04d-%02d-%02d" % (y, m, min(d, (nxt - dt.timedelta(days=1)).day))


def days_between(a: str, b: str) -> int:
    return (dt.date.fromisoformat(b) - dt.date.fromisoformat(a)).days


def month_add(ym: str, n: int) -> str:
    y, m = int(ym[:4]), int(ym[5:7]) + n
    y += (m - 1) // 12
    return "%04d-%02d" % (y, (m - 1) % 12 + 1)


# ------------------------------------------------------------------------------------------------ privacy: never an account number
DIGITS_RE = re.compile(r"\d[\d\s\-]{2,}\d")            # 4+ digits, maybe split by spaces / dashes (cards, accounts, phones, refs)
MASKED_RE = re.compile(r"(?i)(?:x{2,}|\*{2,}|#)\s*\d{2,}|(?:ending|ending in|acct|account|card|a/c)\s*(?:no\.?|number|#)?\s*:?\s*\d{2,}")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
TOKEN_RE = re.compile(r"\b[A-Za-z]*\d[A-Za-z0-9]*\b")


def scrub(s: str, n: int = 120) -> str:
    """a description you can keep: masked account / card / reference numbers and e-mails, one line, at most n chars"""
    s = " ".join(str(s or "").split())
    s = EMAIL_RE.sub("[email]", s)
    s = MASKED_RE.sub("#", s)
    s = DIGITS_RE.sub(lambda m: "#" if sum(c.isdigit() for c in m.group(0)) >= 4 else m.group(0), s)
    s = TOKEN_RE.sub(lambda m: "#" if sum(c.isdigit() for c in m.group(0)) >= 4 else m.group(0), s)
    return re.sub(r"#(?:\s*#)+", "#", s)[:n].strip()


def long_digits(s: str) -> bool:
    """True when a string still holds 5+ digits in a row (outside an ISO date): the published-file guard"""
    t = re.sub(r"\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}:\d{2}Z?)?", "", s)
    return re.search(r"\d{5,}", t) is not None


def guard_public(doc):
    """walk a published document: every string with 5+ digits in a row is masked. Returns (doc, how many were masked)."""
    hits = [0]

    def walk(x):
        if isinstance(x, str):
            if long_digits(x):
                hits[0] += 1
                return re.sub(r"\d{5,}", "#", x)
            return x
        if isinstance(x, list):
            return [walk(v) for v in x]
        if isinstance(x, dict):
            return {k: walk(v) for k, v in x.items()}
        return x
    return walk(doc), hits[0]


# ------------------------------------------------------------------------------------------------ reading values
def parse_amount(v):
    """'$1,234.56' / '-$12.00' / '- $12.00' / '(12.00)' / '12.00-' / '+ $50' -> float, else None"""
    if v is None:
        return None
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v) if math.isfinite(v) else None
    s = str(v).strip().replace("−", "-")
    if not s:
        return None
    neg = False
    if s.startswith("(") and s.endswith(")"):
        neg, s = True, s[1:-1]
    if s.endswith("-"):
        neg, s = True, s[:-1]
    s = s.replace("$", "").replace(",", "").replace("USD", "").replace(" ", "")
    if s.startswith("+"):
        s = s[1:]
    if s.startswith("-"):
        neg, s = not neg, s[1:]
    if not re.fullmatch(r"\d+(\.\d+)?|\.\d+", s):
        return None
    x = float(s)
    return -x if neg else x


MONTHS = {m: i + 1 for i, m in enumerate(("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"))}


def parse_date(v) -> str | None:
    """mm/dd/yyyy, m/d/yy, yyyy-mm-dd (+ time / zone), yyyymmdd (OFX), 'Oct 1, 2026', '01 Oct 2026' -> 'YYYY-MM-DD'"""
    s = str(v or "").strip().strip('"')
    if not s:
        return None
    y = m = d = None
    mt = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if mt:
        y, m, d = int(mt.group(1)), int(mt.group(2)), int(mt.group(3))
    elif re.match(r"^\d{8}", s):
        y, m, d = int(s[:4]), int(s[4:6]), int(s[6:8])
    else:
        mt = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{2,4})", s)
        if mt:
            m, d, y = int(mt.group(1)), int(mt.group(2)), int(mt.group(3))
            y = y + 2000 if y < 100 else y
        else:
            mt = re.match(r"^([A-Za-z]{3})[a-z]*\.?\s+(\d{1,2}),?\s+(\d{4})", s) or None
            if mt:
                m, d, y = MONTHS.get(mt.group(1).lower()), int(mt.group(2)), int(mt.group(3))
            else:
                mt = re.match(r"^(\d{1,2})\s+([A-Za-z]{3})[a-z]*\.?\s+(\d{4})", s)
                if mt:
                    d, m, y = int(mt.group(1)), MONTHS.get(mt.group(2).lower()), int(mt.group(3))
    try:
        return dt.date(y, m, d).isoformat() if y and m and d else None
    except (ValueError, TypeError):
        return None


def norm_head(h) -> str:
    return " ".join(str(h or "").replace("﻿", "").strip().strip('"').lower().split())


# ------------------------------------------------------------------------------------------------ the layouts
# each: id, name, need (header names that must all be there), date, desc (first non-empty), amount: ("signed", col) | ("flip", col)
# (positive = a charge) | ("debitcredit", debit, credit) | ("typed", col, type col), cat (bank category), status (col, allowed words), drop (number columns)
LAYOUTS = [
    {"id": "chase_card", "name": "Chase card", "need": {"transaction date", "post date", "description", "category", "type", "amount"},
     "date": ["transaction date"], "desc": ["description"], "amount": ("signed", "amount"), "cat": "category"},
    {"id": "chase_bank", "name": "Chase checking / savings", "need": {"details", "posting date", "description", "amount", "type", "balance"},
     "date": ["posting date"], "desc": ["description"], "amount": ("signed", "amount")},
    {"id": "bofa_card", "name": "Bank of America card", "need": {"posted date", "reference number", "payee", "address", "amount"},
     "date": ["posted date"], "desc": ["payee"], "amount": ("signed", "amount"), "drop": ["reference number"]},
    {"id": "bofa_bank", "name": "Bank of America checking", "need": {"date", "description", "amount", "running bal."},
     "date": ["date"], "desc": ["description"], "amount": ("signed", "amount")},
    {"id": "capone_card", "name": "Capital One card", "need": {"transaction date", "posted date", "card no.", "description", "debit", "credit"},
     "date": ["transaction date"], "desc": ["description"], "amount": ("debitcredit", "debit", "credit"), "cat": "category", "drop": ["card no."]},
    {"id": "capone_bank", "name": "Capital One 360", "need": {"account number", "transaction date", "transaction amount", "transaction type", "transaction description"},
     "date": ["transaction date"], "desc": ["transaction description"], "amount": ("typed", "transaction amount", "transaction type"), "drop": ["account number"]},
    {"id": "apple_card", "name": "Apple Card", "need": {"transaction date", "clearing date", "description", "merchant", "category", "type", "amount (usd)"},
     "date": ["transaction date"], "desc": ["merchant", "description"], "amount": ("flip", "amount (usd)"), "cat": "category", "kind": "type"},
    {"id": "discover", "name": "Discover card", "need": {"trans. date", "post date", "description", "amount", "category"},
     "date": ["trans. date"], "desc": ["description"], "amount": ("flip", "amount"), "cat": "category"},
    {"id": "cash_app", "name": "Cash App", "need": {"transaction id", "date", "transaction type", "amount", "net amount", "status"},
     "date": ["date"], "desc": ["name of sender/receiver", "notes", "transaction type"], "amount": ("signed", "net amount"),
     "status": ("deny", "status", ("fail", "cancel", "declin", "pending", "waiting", "refunded")), "kind": "transaction type", "drop": ["transaction id", "account"]},
    {"id": "paypal", "name": "PayPal", "need": {"date", "name", "type", "status", "net"},
     "date": ["date"], "desc": ["name", "type"], "amount": ("signed", "net"), "status": ("allow", "status", ("completed", "")), "kind": "type",
     "skip_kind": ("authorization", "hold", "currency conversion", "void"), "drop": ["transaction id", "from email address", "to email address"]},
    {"id": "venmo", "name": "Venmo", "need": {"id", "datetime", "type", "status", "note", "from", "to", "amount (total)"},
     "date": ["datetime"], "desc": ["note", "type"], "amount": ("signed", "amount (total)"), "status": ("deny", "status", ("pending", "fail", "cancel", "declin")),
     "kind": "type", "drop": ["id"]},
    {"id": "amex", "name": "American Express", "need": {"date", "description", "amount"}, "any": {"card member", "extended details", "appears on your statement as", "account #"},
     "date": ["date"], "desc": ["description"], "amount": ("flip", "amount"), "cat": "category", "drop": ["account #", "reference"]},
    {"id": "generic", "name": "Bank CSV (date, description, amount)", "need": {"date", "description", "amount"},
     "date": ["date"], "desc": ["description"], "amount": ("auto", "amount")},
]
DATE_KEYS = ("transaction date", "trans date", "date", "posted date", "posting date", "post date", "datetime")
DESC_KEYS = ("description", "payee", "merchant", "name", "memo", "details", "transaction description", "note")


def _find(heads, keys):
    for k in keys:
        if k in heads:
            return k
    for k in keys:
        for h in heads:
            if k in h:
                return h
    return None


def detect(heads: list):
    """the layout for a header row, else a generic one built from the column names, else None"""
    hs = set(heads)
    for L in LAYOUTS:
        if L["need"] <= hs and (not L.get("any") or L["any"] & hs):
            if L["id"] == "generic":
                break
            return L
    d, s = _find(heads, DATE_KEYS), _find(heads, DESC_KEYS)
    amt = _find(heads, ("amount", "transaction amount", "amount (usd)", "net amount"))
    deb, cre = _find(heads, ("debit", "withdrawal", "withdrawals", "money out", "paid out")), _find(heads, ("credit", "deposit", "deposits", "money in", "paid in"))
    if d and s and (amt or (deb and cre)):
        return {"id": "generic", "name": "Bank CSV", "date": [d], "desc": [s], "amount": ("auto", amt) if amt else ("debitcredit", deb, cre),
                "cat": _find(heads, ("category",))}
    return None


def _sniff_rows(text: str) -> list:
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    return list(csv.reader(io.StringIO(text), dialect))


def parse_csv(text: str):
    """-> (layout id, layout name, rows [{date, amount, desc, bank_cat}], skipped). Finds the header row itself (banks put a summary above it)."""
    rows = _sniff_rows(text)
    if not rows:
        return None, None, [], 0
    # Wells Fargo: no header, 5 columns: "10/01/2026","-12.34","*","","DESCRIPTION"
    first = [c.strip() for c in rows[0]]
    if len(first) == 5 and parse_date(first[0]) and parse_amount(first[1]) is not None and first[2] in ("*", ""):
        out, bad = [], 0
        for r in rows[:MAX_ROWS]:
            if len(r) < 5 or not parse_date(r[0]) or parse_amount(r[1]) is None:
                bad += 1 if any(c.strip() for c in r) else 0
                continue
            out.append({"date": parse_date(r[0]), "amount": parse_amount(r[1]), "desc": r[4], "bank_cat": ""})
        return "wells_fargo", "Wells Fargo", out, bad
    for i, r in enumerate(rows[:40]):
        heads = [norm_head(c) for c in r]
        while heads and heads[0] == "":
            heads = heads[1:]
            r = r[1:]
        L = detect(heads)
        if not L:
            continue
        off = len(rows[i]) - len(heads)                         # a leading empty column (Venmo)
        idx = {h: j + off for j, h in enumerate(heads)}
        out, bad = [], 0
        signs = []
        for row in rows[i + 1:i + 1 + MAX_ROWS]:
            if not any(c.strip() for c in row):
                continue
            g = lambda k: (row[idx[k]].strip() if k in idx and idx[k] < len(row) else "")  # noqa: E731
            date = next((parse_date(g(k)) for k in L["date"] if parse_date(g(k))), None)
            if not date:
                bad += 1
                continue
            st = L.get("status")
            sv = g(st[1]).lower() if st else ""
            if st and ((st[0] == "allow" and sv not in st[2]) or (st[0] == "deny" and any(w in sv for w in st[2]))):
                bad += 1
                continue
            kind = g(L["kind"]).lower() if L.get("kind") else ""
            if any(w in kind for w in L.get("skip_kind", ())):
                bad += 1
                continue
            a = L["amount"]
            if a[0] in ("signed", "flip", "auto"):
                amt = parse_amount(g(a[1]))
                if amt is not None and a[0] == "flip":
                    amt = -amt
            elif a[0] == "debitcredit":
                de, cr = parse_amount(g(a[1])), parse_amount(g(a[2]))
                amt = (cr or 0.0) - abs(de or 0.0) if (de is not None or cr is not None) else None
            else:  # typed: a positive amount + "Debit" / "Credit"
                amt = parse_amount(g(a[1]))
                if amt is not None:
                    amt = -abs(amt) if "debit" in g(a[2]).lower() or "withdraw" in g(a[2]).lower() else abs(amt)
            if amt is None or amt == 0:
                bad += 1
                continue
            desc = " ".join(x for x in (g(k) for k in L["desc"]) if x)
            if L["id"] == "venmo":
                who = g("to") if amt < 0 else g("from")
                desc = " ".join(x for x in (g("note"), g("type"), who) if x)
            out.append({"date": date, "amount": amt, "desc": desc, "bank_cat": g(L["cat"]) if L.get("cat") else "", "kind": kind})
            signs.append(amt > 0)
        lid, lname = L["id"], L["name"]
        if L["amount"][0] == "auto" and signs and sum(signs) > 2 * (len(signs) - sum(signs)):
            # a bare "date, description, amount" file where most rows are positive is a card (positive = a charge): flip it
            for x in out:
                x["amount"] = -x["amount"]
            lid, lname = "generic_card", "Card CSV (positive = a charge)"
        return lid, lname, out, bad
    return None, None, [], len(rows)


OFX_TRN = re.compile(r"<STMTTRN>(.*?)(?:</STMTTRN>|(?=<STMTTRN>)|(?=</BANKTRANLIST>))", re.S | re.I)
OFX_TAG = re.compile(r"<([A-Za-z0-9.]+)>([^<\r\n]*)")


def parse_ofx(text: str):
    """OFX / QFX (SGML or XML): each STMTTRN's DTPOSTED, TRNAMT, NAME, MEMO. The account number (ACCTID) is never read."""
    card = re.search(r"<CREDITCARDMSGSRSV1>|<CCSTMTRS>", text, re.I) is not None
    out, bad = [], 0
    for blk in OFX_TRN.findall(text)[:MAX_ROWS]:
        f = {k.upper(): v.strip() for k, v in OFX_TAG.findall(blk)}
        date, amt = parse_date(f.get("DTPOSTED") or f.get("DTUSER")), parse_amount(f.get("TRNAMT"))
        if not date or amt is None or amt == 0:
            bad += 1
            continue
        name, memo = f.get("NAME", ""), f.get("MEMO", "")
        desc = name if not memo or memo.upper() in name.upper() else f"{name} {memo}"
        out.append({"date": date, "amount": amt, "desc": desc, "bank_cat": "", "kind": f.get("TRNTYPE", "").lower()})
    return ("ofx_card", "OFX / QFX card") if card else ("ofx_bank", "OFX / QFX bank"), out, bad


def parse_inbox_lines(text: str):
    """the iPhone Shortcut's cash.jsonl (tools/money_inbox_server.py): expense / income lines become rows, balance lines are returned apart"""
    rows, balances, bad = [], [], 0
    for line in text.splitlines()[:MAX_ROWS]:
        line = line.strip()
        if not line:
            continue
        try:
            e = json.loads(line)
        except ValueError:
            bad += 1
            continue
        if not isinstance(e, dict):
            bad += 1
            continue
        amt = parse_amount(e.get("amount"))
        if e.get("kind") == "balance":
            name = scrub(e.get("name") or e.get("what"), 40)
            if name and amt is not None:
                balances.append({"id": str(e.get("id") or "")[:40], "name": name, "usd": amt, "kind": str(e.get("account_kind") or "")[:20], "date": parse_date(e.get("date")) or ""})
            else:
                bad += 1
            continue
        date = parse_date(e.get("date")) or (parse_date(str(e.get("t"))[:10]) if e.get("t") else None)
        if not date or amt is None or amt <= 0:
            bad += 1
            continue
        sign = 1 if e.get("kind") == "income" else -1
        rows.append({"date": date, "amount": sign * abs(amt), "desc": str(e.get("what") or "Cash"), "bank_cat": str(e.get("cat") or ""), "kind": "cash",
                     "inbox_id": str(e.get("id") or "")[:40]})
    return rows, balances, bad


def read_text(path: str) -> str | None:
    try:
        if os.path.getsize(path) > MAX_FILE:
            return None
        raw = open(path, "rb").read()
    except OSError:
        return None
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return None


def parse_file(path: str):
    """-> {"layout", "name", "rows", "skipped", "balances"} or None when the file is not an export we know"""
    text = read_text(path)
    if text is None:
        return None
    ext = os.path.splitext(path)[1].lower()
    if ext == ".jsonl" or (ext == ".json" and text.lstrip().startswith("{\"") and "\n{" in text):
        rows, bal, bad = parse_inbox_lines(text)
        return {"layout": "inbox", "name": "iPhone cash entries", "rows": rows, "skipped": bad, "balances": bal}
    if ext in (".ofx", ".qfx", ".qbo") or re.search(r"<OFX>", text[:5000], re.I):
        (lid, lname), rows, bad = parse_ofx(text)
        return {"layout": lid, "name": lname, "rows": rows, "skipped": bad, "balances": []}
    if ext in (".csv", ".txt", ".tsv", ""):
        lid, lname, rows, bad = parse_csv(text)
        if lid is None:
            return None
        return {"layout": lid, "name": lname, "rows": rows, "skipped": bad, "balances": []}
    return None


# ------------------------------------------------------------------------------------------------ rules
def norm_text(s: str) -> str:
    """upper case, punctuation to spaces: 'SQ *Blue Bottle-Cafe #12' -> 'SQ BLUE BOTTLE CAFE #'"""
    return " ".join(re.sub(r"[^A-Z0-9#]+", " ", str(s or "").upper().replace("'", "").replace("&", " ")).split())


PREFIXES = re.compile(r"^(?:(?:SQ|TST|PP|SP|DD|PAYPAL|POS|ACH|CHECKCARD|CHECK CARD|DEBIT CARD PURCHASE|DEBIT CARD|PURCHASE AUTHORIZED ON|PURCHASE|RECURRING PAYMENT|"
                      r"AUTHORIZED ON|PAYMENT|DEPOSIT FROM|DEPOSIT|"
                      r"RECURRING|CARD PURCHASE|VISA|MC|DEBIT|WEB|ONLINE|PREAUTHORIZED|PRE AUTH|BILL PAY|BILLPAY|IN|GOOGLE|APPLE PAY|APL PAY|SQUARE)\s+)+")


def merchant_key(desc: str) -> str:
    """a stable short name for grouping: the first two real words after the card-network noise"""
    t = re.sub(r"\b\d+\b", " ", norm_text(scrub(desc)).replace("#", " "))
    t = PREFIXES.sub("", " ".join(t.split()))
    words = [w for w in t.split() if len(w) >= 2 and not w.isdigit() and w not in ("COM", "WWW", "INC", "LLC", "USA", "US", "CO", "THE", "ON", "AT")]
    return " ".join(words[:2]) or "UNKNOWN"


def compile_rules(doc) -> list:
    out = []
    for r in (doc or {}).get("rules", []) if isinstance(doc, dict) else []:
        if not isinstance(r, dict):
            continue
        words = [norm_text(w) for w in (r.get("match") or []) if isinstance(w, str) and norm_text(w)]
        cat = r.get("category")
        ok = (isinstance(cat, str) and cat in CATS) or (isinstance(cat, dict) and all(v in CATS for v in cat.values()) and cat)
        if not words or not ok:
            continue
        rx = re.compile(r"(?<![A-Z0-9])(?:" + "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True)) + r")(?![A-Z0-9])")
        out.append({"rx": rx, "cat": cat, "dir": r.get("dir") if r.get("dir") in ("in", "out") else None,
                    "label": scrub(r.get("label") or "", 40), "sub": str(r.get("sub") or "")[:20]})
    return out


def categorize(row: dict, rules: list, overrides: dict | None = None) -> dict:
    """-> {"cat", "label", "sub", "rule"}: the first rule that matches (by words and direction), else the bank's own category, else other"""
    d = "in" if row["amount"] > 0 else "out"
    if overrides and row.get("id") in overrides and overrides[row["id"]] in CATS:
        return {"cat": overrides[row["id"]], "label": "", "sub": "", "rule": "override"}
    t = norm_text(row.get("desc"))
    for i, r in enumerate(rules):
        if r["dir"] and r["dir"] != d:
            continue
        if r["rx"].search(t):
            c = r["cat"] if isinstance(r["cat"], str) else r["cat"].get(d)
            if not c:
                continue
            return {"cat": c, "label": r["label"], "sub": r["sub"], "rule": i}
    kind, src = str(row.get("kind") or "").lower(), str(row.get("source") or "")
    if src in P2P_APPS:
        if any(w in kind for w in ("transfer", "cash out", "deposit", "add cash", "withdraw")):
            return {"cat": "transfer", "label": "Own transfer", "sub": "", "rule": "kind"}
        if any(w in kind for w in ("p2p", "payment", "charge", "request")):
            return {"cat": "people" if d == "out" else "income_other", "label": "People", "sub": "", "rule": "kind"}
    elif src in CARDS and kind in ("payment", "credit card payment", "autopay"):
        return {"cat": "transfer", "label": "Own transfer", "sub": "", "rule": "kind"}
    elif "transfer" in kind or kind == "xfer":
        return {"cat": "transfer", "label": "Own transfer", "sub": "", "rule": "kind"}
    bc = str(row.get("bank_cat") or "").lower()
    if bc:
        for key, cat, sub in BANK_CATS:
            if key in bc and (d == "out" or cat == "transfer"):
                return {"cat": cat, "label": CATS[cat][0], "sub": sub or "", "rule": "bank"}
    return {"cat": "other" if d == "out" else "income_other", "label": "", "sub": "", "rule": None}


def load_rules(path: str | None):
    """the owner's rules file, else the defaults. Returns (doc, where)."""
    doc = read_json(path) if path else None
    if isinstance(doc, dict) and isinstance(doc.get("rules"), list):
        return doc, path
    return DEFAULT_RULES_DOC, "defaults"


# ------------------------------------------------------------------------------------------------ the private ledger
def fingerprint(row: dict, n: int) -> str:
    """same day, same cents, same (normalized) description, the n-th such row in its file: one id. Overlapping exports share ids."""
    key = f"{row['date']}|{int(round(row['amount'] * 100))}|{norm_text(row['desc'])[:24]}|{n}"
    return hashlib.sha1(key.encode()).hexdigest()[:16]


def file_hash(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()[:24]


def empty_ledger() -> dict:
    return {"v": VERSION, "kind": "olympus-money-ledger", "private": True, "txns": [], "files": {}, "inbox_done": []}


def load_ledger(path: str) -> dict:
    doc = read_json(path)
    if not isinstance(doc, dict) or not isinstance(doc.get("txns"), list):
        return empty_ledger()
    doc.setdefault("files", {})
    doc.setdefault("inbox_done", [])
    return doc


def add_rows(ledger: dict, parsed: dict, source: str, today: str) -> dict:
    """add a parsed file's rows; returns {"added", "dupes"}. Rows with a date after today are kept (pending charges) but counted by date."""
    have = {t["id"] for t in ledger["txns"]}
    seen, added, dupes = {}, 0, 0
    done_inbox = set(ledger.get("inbox_done") or [])
    for row in parsed["rows"]:
        if row.get("inbox_id"):
            if row["inbox_id"] in done_inbox:
                dupes += 1
                continue
            done_inbox.add(row["inbox_id"])
        base = f"{row['date']}|{int(round(row['amount'] * 100))}|{norm_text(row['desc'])[:24]}"
        n = seen.get(base, 0)
        seen[base] = n + 1
        tid = fingerprint(row, n)
        if tid in have:
            dupes += 1
            continue
        have.add(tid)
        ledger["txns"].append({"id": tid, "date": row["date"], "amount": r2(row["amount"]), "desc": scrub(row["desc"]), "bank_cat": scrub(row.get("bank_cat"), 40),
                               "kind": str(row.get("kind") or "")[:30], "source": source, "added": today})
        added += 1
    fresh = []
    for b in parsed.get("balances") or []:
        if b.get("id") and b["id"] in done_inbox:
            continue
        if b.get("id"):
            done_inbox.add(b["id"])
        fresh.append(b)
    ledger["inbox_done"] = sorted(done_inbox)[-5000:]
    return {"added": added, "dupes": dupes, "balances": fresh}


def import_paths(ledger: dict, paths: list, today: str, force=False) -> list:
    """import files; a file whose bytes were imported before is skipped (fast). Returns one report line per file (no file names: they can
    hold the last digits of an account)."""
    rep = []
    for p in paths:
        try:
            fh = file_hash(p)
        except OSError:
            continue
        ext = os.path.splitext(p)[1].lower()
        if fh in ledger["files"] and not force and ext != ".jsonl":
            rep.append({"layout": ledger["files"][fh].get("layout"), "state": "already imported", "added": 0, "dupes": 0})
            continue
        parsed = parse_file(p)
        if parsed is None:
            rep.append({"layout": None, "state": "not a bank export I know", "added": 0, "dupes": 0, "ext": ext})
            continue
        res = add_rows(ledger, parsed, parsed["layout"], today)
        dates = sorted(r["date"] for r in parsed["rows"])
        ledger["files"][fh] = {"layout": parsed["layout"], "name": parsed["name"], "rows": len(parsed["rows"]), "skipped": parsed["skipped"],
                               "first": dates[0] if dates else None, "last": dates[-1] if dates else None, "added": today}
        rep.append({"layout": parsed["layout"], "name": parsed["name"], "state": "imported", "rows": len(parsed["rows"]), "skipped": parsed["skipped"],
                    "first": dates[0] if dates else None, "last": dates[-1] if dates else None, **res})
    return rep


def inbox_files(dirs: list) -> list:
    out = []
    for d in dirs:
        try:
            names = sorted(os.listdir(d))
        except OSError:
            continue
        for n in names:
            p = os.path.join(d, n)
            if os.path.isfile(p) and not n.startswith(".") and os.path.splitext(n)[1].lower() in (".csv", ".ofx", ".qfx", ".qbo", ".jsonl", ".txt", ".tsv"):
                out.append(p)
    return out


# ------------------------------------------------------------------------------------------------ net worth
BAL_KINDS = {"cash": 1, "savings": 1, "investment": 1, "retirement": 1, "crypto": 1, "kalshi": 1, "receivable": 1, "property": 1, "other": 1, "debt": -1}
LIQUID = ("cash", "savings")
DEFAULT_BALANCES = {
    "v": 1,
    "note": "Your net worth (tools/money_import.py). Put today's balance in usd (no account numbers, just a name). kind: cash, savings, investment, "
            "retirement, crypto, kalshi (leave usd null to read the Kalshi feed), receivable (funded payouts owed to you), property, other, debt "
            "(what you owe, as a positive number). Or run: python tools/money_import.py --balance \"Checking=1234.56\"",
    "accounts": [
        {"name": "Checking", "kind": "cash", "usd": None},
        {"name": "Savings", "kind": "savings", "usd": None},
        {"name": "Crypto", "kind": "crypto", "usd": None},
        {"name": "Kalshi", "kind": "kalshi", "usd": None},
        {"name": "Funded payouts owed to you", "kind": "receivable", "usd": None},
        {"name": "Credit cards", "kind": "debt", "usd": None},
    ],
}


def load_balances(path: str) -> dict:
    doc = read_json(path)
    if not isinstance(doc, dict) or not isinstance(doc.get("accounts"), list):
        return json.loads(json.dumps(DEFAULT_BALANCES))
    return doc


def set_balance(doc: dict, name: str, usd: float, kind: str = "", date: str = "") -> dict:
    name = scrub(name, 40)
    for a in doc["accounts"]:
        if isinstance(a, dict) and str(a.get("name", "")).strip().lower() == name.lower():
            a["usd"] = r2(usd)
            if kind in BAL_KINDS:
                a["kind"] = kind
            if date:
                a["updated"] = date
            return doc
    doc["accounts"].append({"name": name, "kind": kind if kind in BAL_KINDS else ("debt" if re.search(r"(?i)card|loan|debt|owe", name) else "cash"),
                            "usd": r2(usd), **({"updated": date} if date else {})})
    return doc


def kalshi_balance(home: str):
    for p in (os.path.join(home, "kalshi_feed", "kalshi.json"), os.path.join(ROOT, "tools", "web_public", "kalshi.json")):
        j = read_json(p)
        if isinstance(j, dict):
            try:
                b = float(j.get("balance"))
                if math.isfinite(b):
                    return b
            except (TypeError, ValueError):
                pass
    return None


def networth(doc: dict, kalshi=None) -> dict:
    rows, assets, debts, liquid, missing = [], 0.0, 0.0, 0.0, []
    for a in doc.get("accounts", [])[:100]:
        if not isinstance(a, dict):
            continue
        name, kind = scrub(a.get("name"), 40) or "Account", a.get("kind") if a.get("kind") in BAL_KINDS else "other"
        usd = parse_amount(a.get("usd"))
        auto = False
        if usd is None and kind == "kalshi" and kalshi is not None:
            usd, auto = kalshi, True
        if usd is None:
            missing.append(name)
            continue
        if kind == "debt":
            debts += abs(usd)
        else:
            assets += usd
            if kind in LIQUID:
                liquid += usd
        rows.append({"name": name, "kind": kind, "usd": r2(abs(usd) if kind == "debt" else usd), "auto": auto, "updated": str(a.get("updated") or "")[:10]})
    return {"total": r2(assets - debts) if rows else None, "assets": r2(assets), "debts": r2(debts), "liquid": r2(liquid) if any(r["kind"] in LIQUID for r in rows) else None,
            "accounts": rows, "missing": missing}


def update_history(path: str, today: str, nw: dict) -> list:
    hist = read_json(path)
    hist = [h for h in hist if isinstance(h, dict) and h.get("date")] if isinstance(hist, list) else []
    if nw.get("total") is not None:
        hist = [h for h in hist if h["date"] != today] + [{"date": today, "total": nw["total"], "assets": nw["assets"], "debts": nw["debts"]}]
        hist.sort(key=lambda h: h["date"])
        hist = hist[-1500:]
        write_json(path, hist)
    return hist


# ------------------------------------------------------------------------------------------------ the analysis
def classify(ledger: dict, rules_doc: dict) -> list:
    rules = compile_rules(rules_doc)
    ov = rules_doc.get("overrides") if isinstance(rules_doc.get("overrides"), dict) else {}
    out = []
    for t in ledger["txns"]:
        c = categorize(t, rules, ov)
        out.append({**t, **c, "kind_cat": CATS[c["cat"]][1], "mkey": merchant_key(t["desc"])})
    out.sort(key=lambda x: (x["date"], x["id"]))
    return out


CADENCE = (("week", 5, 9, 7), ("month", 26, 35, 30.4375), ("quarter", 84, 97, 91.3), ("year", 350, 380, 365.25))


def _median(xs):
    s = sorted(xs)
    n = len(s)
    return (s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2) if n else 0.0


def _recurring(g: list, today: str):
    """one merchant's charges -> the recurring pattern, or None"""
    g = sorted(g, key=lambda x: x["date"])
    dates = []
    for x in g:
        if not dates or x["date"] != dates[-1]:
            dates.append(x["date"])
    if len(dates) < 2 or len(dates) != len(g):
        return None
    gaps = [days_between(a, b) for a, b in zip(dates, dates[1:])]
    cad = next((c for c in CADENCE if c[1] <= _median(gaps) <= c[2]), None)
    if not cad or sum(1 for x in gaps if cad[1] <= x <= cad[2]) < len(gaps) - (1 if len(gaps) >= 4 else 0):
        return None
    is_sub_rule = any(x["cat"] in ("subscriptions", "trading_tools") for x in g)
    if len(dates) < (2 if cad[0] in ("quarter", "year") or is_sub_rule else 3):
        return None
    amts = [-x["amount"] for x in g]
    base = _median(amts[:-1]) if len(amts) > 2 else amts[0]
    strict = not any(x["cat"] in LOOSE_CATS for x in g)       # a store you visit often (food, gas, shopping) must charge the SAME amount
    tol = (lambda b: max(0.01 * b, 0.05)) if strict else (lambda b: max(0.15 * b, 1.5))
    steady = [a for a in amts[:-1] if abs(a - base) <= tol(base)]
    if strict and abs(amts[-1] - base) > tol(base):
        return None
    if len(steady) < max(1, len(amts) - 2):
        return None
    return g, cad, amts, base


def subscriptions(rows: list, today: str, show_merchants=False) -> list:
    """recurring charges: the same merchant, a steady cadence (weekly / monthly / quarterly / yearly), a steady amount (within 15% or $1.50;
    the last charge may differ = a price change). Monthly needs 3 charges (2 when a rule called it a subscription); yearly 2. Two plans at
    one merchant (two Apple charges) are split by amount."""
    groups = {}
    for r in rows:
        if r["kind_cat"] != "spend" or r["amount"] >= 0 or r["cat"] in ("cash", "bank_fees", "people", "prop_fees"):
            continue
        groups.setdefault(r["mkey"], []).append(r)
    found = []
    for key, g in groups.items():
        hit = _recurring(g, today)
        if hit:
            found.append((key, hit))
            continue
        if not any(x["cat"] in LOOSE_CATS for x in g):      # a store (food, gas, shopping): never split into "plans" by amount
            continue
        clusters = []
        for x in sorted(g, key=lambda x: x["amount"]):
            a = -x["amount"]
            if clusters and abs(a - clusters[-1][0]) <= max(0.15 * clusters[-1][0], 1.5):
                clusters[-1][1].append(x)
            else:
                clusters.append((a, [x]))
        for i, (a, c) in enumerate(clusters):
            hit = _recurring(c, today) if len(c) >= 2 else None
            if hit:
                found.append((f"{key} {i + 1}" if len(clusters) > 1 else key, hit))
    out = []
    for key, (g, cad, amts, base) in found:
        last = g[-1]
        last_amt = -last["amount"]
        late = days_between(last["date"], today)
        active = late <= cad[3] * 1.6 + 5
        step = (lambda d: add_months(d, 1)) if cad[0] == "month" else (lambda d: add_months(d, 3)) if cad[0] == "quarter" else \
            (lambda d: add_months(d, 12)) if cad[0] == "year" else (lambda d: add_days(d, 7))
        nxt = step(last["date"])
        while active and nxt < today:
            nxt = step(nxt)
        per_month = last_amt * {"week": 52 / 12, "month": 1.0, "quarter": 1 / 3, "year": 1 / 12}[cad[0]]
        cat = last["cat"]
        label = last.get("label") or CATS[cat][0]
        out.append({"key": key, "label": label, "merchant": key.title() if show_merchants else None, "category": cat, "cat_name": CATS[cat][0],
                    "type": "bill" if cat in BILLS and label != "Gym" else "subscription", "every": cad[0], "usd": r2(last_amt),
                    "usd_month": r2(per_month), "usd_year": r2(per_month * 12), "n": len(g), "first": g[0]["date"], "last": last["date"], "next": nxt,
                    "active": active, "price_up": r2(last_amt - base) if last_amt - base >= max(1.0, 0.05 * base) else 0.0})
    out.sort(key=lambda s: (not s["active"], -s["usd_month"], s["key"]))
    return out


def month_table(rows: list, today: str, months: int = 12) -> list:
    cur = today[:7]
    keys = [month_add(cur, -i) for i in range(months - 1, -1, -1)]
    tab = {k: {"month": k, "in": 0.0, "out": 0.0, "by_cat": {}, "kalshi_in": 0.0, "kalshi_out": 0.0, "n": 0} for k in keys}
    for r in rows:
        m = tab.get(r["date"][:7])
        if not m or r["date"] > today:
            continue
        m["n"] += 1
        k = r["kind_cat"]
        if k == "spend":
            m["out"] += -r["amount"]
            m["by_cat"][r["cat"]] = m["by_cat"].get(r["cat"], 0.0) - r["amount"]
        elif k == "income":
            m["in"] += r["amount"]
            m["by_cat"][r["cat"]] = m["by_cat"].get(r["cat"], 0.0) + r["amount"]
        elif k == "move":
            if r["amount"] < 0:
                m["kalshi_out"] += -r["amount"]
            else:
                m["kalshi_in"] += r["amount"]
    out = []
    for k in keys:
        m = tab[k]
        out.append({"month": k, "in": r2(m["in"]), "out": r2(m["out"]), "net": r2(m["in"] - m["out"]), "kalshi_net": r2(m["kalshi_in"] - m["kalshi_out"]),
                    "by_cat": {c: r2(v) for c, v in sorted(m["by_cat"].items(), key=lambda kv: -abs(kv[1])) if abs(v) >= 0.005}, "n": m["n"],
                    "partial": k == today[:7]})
    return out


def leaks(rows, subs, months, today) -> list:
    """money that goes out and does not come back, worst first ($ a month)"""
    out = []
    d90 = add_days(today, -90)
    fees90 = r2(sum(-r["amount"] for r in rows if r["cat"] == "bank_fees" and r["date"] > d90 and r["amount"] < 0))
    if fees90 > 0:
        out.append({"id": "bank_fees", "title": "Bank fees and interest", "detail": f"{money(fees90)} in the last 90 days: overdraft, late, monthly or interest charges. Most can be avoided or waived.",
                    "usd_month": r2(fees90 / 3)})
    act = [s for s in subs if s["active"]]
    by_label = {}
    for s in act:
        if s["type"] == "subscription":
            by_label.setdefault(s["label"], []).append(s)
    for lab, ss in by_label.items():
        if len(ss) >= 2:
            tot = r2(sum(s["usd_month"] for s in ss))
            out.append({"id": "dupe:" + lab, "title": f"{len(ss)} {lab.lower()} subscriptions", "detail": f"{money(tot)} a month together ({money(tot * 12)} a year). Keep the one you use most.",
                        "usd_month": r2(tot - max(s["usd_month"] for s in ss))})
    for s in act:
        if s["price_up"] > 0:
            nm = s["merchant"] or s["label"]
            out.append({"id": "up:" + s["key"], "title": f"Price went up: {nm}", "detail": f"Now {money(s['usd'])} a charge, {money(s['price_up'])} more than before.", "usd_month": r2(s["price_up"] * (s["usd_month"] / s["usd"] if s["usd"] else 1))})
    subs_m = r2(sum(s["usd_month"] for s in act if s["type"] == "subscription"))
    if subs_m > 0:
        out.append({"id": "subs", "title": "All your subscriptions", "detail": f"{len([s for s in act if s['type'] == 'subscription'])} running: {money(subs_m)} a month, {money(subs_m * 12)} a year. If one in four is not used, that is {money(subs_m * 0.25)} a month.",
                    "usd_month": r2(subs_m * 0.25)})
    full = [m for m in months if not m["partial"] and m["n"]][-3:]
    if full:
        deliv = r2(sum(-r["amount"] for r in rows if r.get("sub") == "delivery" and r["date"][:7] in {m["month"] for m in full}) / len(full))
        if deliv >= 60:
            out.append({"id": "delivery", "title": "Delivery apps", "detail": f"About {money(deliv)} a month on delivery. Fees and tips add ~30%: cooking half of it saves about {money(deliv * 0.5 * 0.3 + deliv * 0.25)}.",
                        "usd_month": r2(deliv * 0.5 * 0.3 + deliv * 0.25)})
    p90 = r2(sum(-r["amount"] for r in rows if r["cat"] == "prop_fees" and r["date"] > d90))
    pay90 = r2(sum(r["amount"] for r in rows if r["cat"] == "prop_payout" and r["date"] > d90))
    if p90 > 0 and pay90 < p90:
        out.append({"id": "prop", "title": "Prop-firm fees not paid back yet", "detail": f"{money(p90)} of prop-firm fees in 90 days and {money(pay90)} of payouts. Buy the next eval only after a payout.",
                    "usd_month": r2((p90 - pay90) / 3)})
    if len(full) >= 2:
        last, before = full[-1], full[:-1]
        for c in set(last["by_cat"]):
            if CATS[c][1] != "spend" or c in ("prop_fees",):
                continue
            avg = sum(m["by_cat"].get(c, 0.0) for m in before) / len(before)
            now = last["by_cat"].get(c, 0.0)
            if avg > 0 and now - avg >= 50 and now >= avg * 1.3:
                out.append({"id": "jump:" + c, "title": f"{CATS[c][0]} went up", "detail": f"{money(now)} in {last['month']} against about {money(avg)} a month before (+{round((now / avg - 1) * 100)}%).",
                            "usd_month": r2(now - avg)})
    for x in out:
        x["score"] = int(max(0, min(100, round(20 + x["usd_month"] / 2))))
    out.sort(key=lambda x: (-x["usd_month"], x["id"]))
    return out


def build(ledger: dict, rules_doc: dict, today: str, balances: dict | None = None, kalshi=None, history=None, report=None) -> dict:
    """the published summary (pure: no file, no clock). No account numbers; no merchant names unless privacy.publish_merchants."""
    priv = rules_doc.get("privacy") if isinstance(rules_doc.get("privacy"), dict) else {}
    show = priv.get("publish_merchants") is True
    rows = classify(ledger, rules_doc)
    months = month_table(rows, today)
    subs = subscriptions(rows, today, show)
    lk = leaks(rows, subs, months, today)
    cur = months[-1]
    prev = months[-2]
    full = [m for m in months if not m["partial"] and m["n"]][-3:]
    avg_out = r2(sum(m["out"] for m in full) / len(full)) if full else None
    avg_in = r2(sum(m["in"] for m in full) / len(full)) if full else None
    avg_net = r2(avg_in - avg_out) if full else None

    # prop firms: fees vs payouts, all time, by firm (the rule's label: a firm name, not a card merchant string)
    firms = {}
    for r in rows:
        if r["cat"] in ("prop_fees", "prop_payout"):
            f = firms.setdefault(r.get("label") or "Prop firm", {"firm": r.get("label") or "Prop firm", "fees": 0.0, "payouts": 0.0, "n_fees": 0, "n_payouts": 0})
            if r["cat"] == "prop_fees":
                f["fees"] += -r["amount"]
                f["n_fees"] += 1
            else:
                f["payouts"] += r["amount"]
                f["n_payouts"] += 1
    fl = [{**f, "fees": r2(f["fees"]), "payouts": r2(f["payouts"]), "net": r2(f["payouts"] - f["fees"])} for f in firms.values()]
    fl.sort(key=lambda f: -(f["fees"] + f["payouts"]))
    pf, pp = r2(sum(f["fees"] for f in fl)), r2(sum(f["payouts"] for f in fl))
    prop = {"fees": pf, "payouts": pp, "net": r2(pp - pf), "roi_pct": r2((pp - pf) / pf * 100) if pf > 0 else None, "firms": fl,
            "text": "No prop-firm charges found." if not fl else f"{money(pp)} of payouts on {money(pf)} of fees: {money(pp - pf, True)}" + (f" ({round((pp - pf) / pf * 100):+d}%)." if pf > 0 else ".")}
    kd = r2(sum(-r["amount"] for r in rows if r["cat"] == "kalshi_deposit"))
    kw = r2(sum(r["amount"] for r in rows if r["cat"] == "kalshi_withdrawal"))
    kal = {"deposits": kd, "withdrawals": kw, "net_moved": r2(kw - kd), "text": "No Kalshi transfers found." if not (kd or kw) else f"{money(kd)} sent to Kalshi, {money(kw)} back: {money(kw - kd, True)}."}

    nw = networth(balances, kalshi) if isinstance(balances, dict) else {"total": None, "accounts": [], "missing": [], "liquid": None, "assets": 0.0, "debts": 0.0}
    hist = [h for h in (history or []) if isinstance(h, dict)]
    ago = [h for h in hist if h["date"] <= add_days(today, -30)]
    nw["change_30d"] = r2(nw["total"] - ago[-1]["total"]) if nw.get("total") is not None and ago else None
    nw["history"] = [{"date": h["date"], "total": h["total"]} for h in hist[-120:]]

    burn = avg_out
    liquid = nw.get("liquid")
    if liquid is not None and burn:
        months_left = r2(liquid / burn)
        run = {"months": months_left, "liquid": liquid, "burn": burn, "net_month": avg_net,
               "months_at_net": r2(liquid / -avg_net) if avg_net is not None and avg_net < 0 else None,
               "text": f"About {months_left:.1f} months on savings alone: {money(liquid)} in cash and savings, {money(burn)} a month of spending."
                       + (f" At your real pace (money in included) {liquid / -avg_net:.1f} months." if avg_net is not None and avg_net < 0 else
                          " Money in covers your spending right now, so savings are not shrinking." if avg_net is not None else "")}
    else:
        run = {"months": None, "liquid": liquid, "burn": burn, "net_month": avg_net, "months_at_net": None,
               "text": "Add your checking and savings balances (balances.json or --balance) to see how long your savings last." if liquid is None else
                       "Import a full month of bank data to see how long your savings last."}

    subs_pub = [{k: v for k, v in s.items() if k != "key" and (show or k != "merchant")} for s in subs]
    act = [s for s in subs if s["active"]]
    food_m = cur["by_cat"].get("food", 0.0)
    food_sub = {}
    for r in rows:
        if r["cat"] == "food" and r["date"][:7] == cur["month"] and r["date"] <= today:
            food_sub[r.get("sub") or "other"] = food_sub.get(r.get("sub") or "other", 0.0) - r["amount"]
    top = sorted(((c, v) for c, v in cur["by_cat"].items() if CATS[c][1] == "spend"), key=lambda kv: -kv[1])[:3]
    has = bool(rows)
    jarvis = {
        "spend_month": f"This month so far ({cur['month']}): {money(cur['out'])} out, {money(cur['in'])} in, net {money(cur['net'], True)}." if has else "No bank data imported yet.",
        "food_month": (f"Food this month: {money(food_m)}" + (" (" + ", ".join(f"{k.replace('_', ' ')} {money(v)}" for k, v in sorted(food_sub.items(), key=lambda kv: -kv[1])) + ")" if food_sub else "")
                       + (f"; last month {money(prev['by_cat'].get('food', 0.0))}." if prev["n"] else ".")) if has else "No bank data imported yet.",
        "subscriptions": (f"{len(act)} recurring charges, {money(sum(s['usd_month'] for s in act))} a month: " + "; ".join(
            f"{s['merchant'] or s['label']} {money(s['usd'])} a {s['every']}, next {s['next']}" for s in act[:8]) + ".") if act else
        ("No recurring charges found yet (it needs two or three months of data)." if has else "No bank data imported yet."),
        "runway": run["text"],
        "networth": (f"Net worth {money(nw['total'])}: {money(nw['assets'])} in assets, {money(nw['debts'])} owed" + (f", {money(nw['change_30d'], True)} in 30 days." if nw.get("change_30d") is not None else ".")) if nw.get("total") is not None else "No balances entered yet.",
        "prop": prop["text"],
        "top_spend": ("Biggest spending this month: " + ", ".join(f"{CATS[c][0]} {money(v)}" for c, v in top) + ".") if top else "No spending this month yet.",
        "leaks": ("Money leaks: " + "; ".join(f"{x['title']} (~{money(x['usd_month'])} a month)" for x in lk[:3]) + ".") if lk else "No money leaks found.",
    }
    src = {}
    for f in ledger.get("files", {}).values():
        s = src.setdefault(f.get("layout") or "?", {"layout": f.get("layout"), "name": f.get("name"), "files": 0, "rows": 0, "first": None, "last": None})
        s["files"] += 1
        s["rows"] += int(f.get("rows") or 0)
        for k, fn in (("first", min), ("last", max)):
            if f.get(k):
                s[k] = fn(s[k], f[k]) if s[k] else f[k]
    last_day = max((r["date"] for r in rows if r["date"] <= today), default=None)
    doc = {"v": VERSION, "kind": "olympus-household", "built": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "today": today,
           "status": "ok" if has else "empty", "paper_only": True,
           "privacy": {"account_numbers": "never kept", "merchants": "shown" if show else "hidden (generic labels; privacy.publish_merchants in the rules turns names on)",
                       "where": "the PC's private Tailscale link only (money_out/household.json); never the public site"},
           "data": {"rows": len(rows), "first": rows[0]["date"] if rows else None, "last": last_day,
                    "age_days": days_between(last_day, today) if last_day else None, "sources": sorted(src.values(), key=lambda s: s["layout"] or "")},
           "this_month": {**cur, "cats": [{"id": c, "name": CATS[c][0], "usd": v} for c, v in cur["by_cat"].items()]},
           "last_month": {**prev, "cats": [{"id": c, "name": CATS[c][0], "usd": v} for c, v in prev["by_cat"].items()]},
           "months": months, "avg3": {"in": avg_in, "out": avg_out, "net": avg_net, "months": len(full)},
           "categories": {c: {"name": n, "kind": k} for c, (n, k) in CATS.items()},
           "subscriptions": {"items": subs_pub, "active": len(act), "usd_month": r2(sum(s["usd_month"] for s in act)),
                             "subs_month": r2(sum(s["usd_month"] for s in act if s["type"] == "subscription")),
                             "bills_month": r2(sum(s["usd_month"] for s in act if s["type"] == "bill"))},
           "prop": prop, "kalshi": kal, "runway": run, "networth": nw, "leaks": lk,
           "leak_month": r2(sum(x["usd_month"] for x in lk)), "jarvis": jarvis,
           "notes": ["From the exports you downloaded yourself; nothing logs in to a bank.",
                     "Transfers between your own accounts and card payments are left out, so nothing counts twice.",
                     "Kalshi deposits and withdrawals are your money moving, not spending; they are shown apart.",
                     "Estimates, not advice. The phone copy has no account numbers" + ("." if show else " and no merchant names.")]}
    if report:
        doc["last_import"] = [{k: v for k, v in r.items() if k in ("layout", "name", "state", "rows", "added", "dupes", "skipped", "first", "last")} for r in report][-20:]
    doc, masked = guard_public(doc)
    doc["privacy"]["masked_strings"] = masked
    return doc


# ------------------------------------------------------------------------------------------------ Oikos: the same money as a Ledger export
OIKOS_KIND = {"prop_fees": "fee", "prop_payout": "payout_in", "kalshi_deposit": "deposit", "kalshi_withdrawal": "withdrawal"}


def oikos_ledger(ledger: dict, rules_doc: dict, today: str, living=None, saved=None) -> dict:
    """category-level entries in the Ledger app's export format (tools/money/oikos.py reads it): one expense per category per month,
    each active subscription as ONE monthly recurring expense (generic label), prop fees / payouts per firm, Kalshi moves. No merchant names."""
    rows = classify(ledger, rules_doc)
    subs = [s for s in subscriptions(rows, today, False) if s["active"]]
    sub_keys = {s["key"] for s in subs}
    agg, ents = {}, []
    for r in rows:
        if r["date"] > today or r["kind_cat"] == "ignore":
            continue
        c = r["cat"]
        if c in OIKOS_KIND:
            acct = ("prop_" + re.sub(r"[^a-z0-9]+", "_", (r.get("label") or "firm").lower())) if c.startswith("prop") else "kalshi"
            ents.append({"kind": OIKOS_KIND[c], "amount": r2(abs(r["amount"])), "date": r["date"], "cat": CATS[c][0], "acct": acct, "note": r.get("label") or CATS[c][0]})
            continue
        if r["kind_cat"] == "spend" and r["mkey"] in sub_keys:
            continue
        key = (r["date"][:7], c, "income" if r["kind_cat"] == "income" else "expense")
        agg[key] = agg.get(key, 0.0) + (r["amount"] if r["kind_cat"] == "income" else -r["amount"])
    for (m, c, kind), v in sorted(agg.items()):
        if v <= 0.005:
            continue
        last = add_days(month_add(m, 1) + "-01", -1)
        ents.append({"kind": kind, "amount": r2(v), "date": min(last, today), "cat": CATS[c][0], "acct": "general", "note": CATS[c][0]})
    for s in subs:
        start = s["first"] if s["every"] == "month" else s["last"]
        ents.append({"kind": "expense", "amount": s["usd_month"] if s["every"] in ("month", "week") else s["usd"], "date": start, "cat": "Subscriptions" if s["type"] == "subscription" else s["cat_name"],
                     "acct": "general", "note": s["label"], "rec": {"every": "month" if s["every"] in ("month", "week") else "year", "until": None}})
    for i, e in enumerate(ents):
        e["id"] = "b%d" % i
    opts = {}
    if living:
        opts["living"] = r2(living)
    if saved is not None:
        opts["em_saved"] = r2(max(0.0, saved))
    firms = sorted({e["acct"] for e in ents if e["acct"].startswith("prop_")})
    return {"v": 1, "app": "ledger", "source": "money_import", "exported": today, "note": "Built from your bank exports by tools/money_import.py (category level, no merchant names).",
            "settings": {"taxPct": 25}, "opts": opts, "accounts": [{"id": f, "name": f[5:].replace("_", " ").title() + " (prop firm)"} for f in firms], "entries": ents}


# ------------------------------------------------------------------------------------------------ the table
def table(doc: dict) -> str:
    c, p = doc["this_month"], doc["last_month"]
    out = ["| What | This month | Last month | 3-month average |", "|---|---|---|---|",
           f"| Money in | {money(c['in'])} | {money(p['in'])} | {money(doc['avg3']['in'])} |",
           f"| Money out | {money(c['out'])} | {money(p['out'])} | {money(doc['avg3']['out'])} |",
           f"| **Net** | **{money(c['net'], True)}** | **{money(p['net'], True)}** | **{money(doc['avg3']['net'], True)}** |"]
    for cat in c["cats"][:8]:
        out.append(f"| {cat['name']} | {money(cat['usd'])} | {money(p['by_cat'].get(cat['id']))} | |")
    s = doc["subscriptions"]
    out += ["", f"Subscriptions and bills: {s['active']} running, {money(s['usd_month'])} a month.", f"Prop firms: {doc['prop']['text']}", f"Kalshi: {doc['kalshi']['text']}",
            f"Runway: {doc['runway']['text']}", doc["jarvis"]["networth"]]
    if doc["leaks"]:
        out.append("Leaks: " + "; ".join(f"{x['title']} ~{money(x['usd_month'])}/mo" for x in doc["leaks"][:5]))
    return "\n".join(out)


def today_et() -> str:
    try:
        from zoneinfo import ZoneInfo
        return dt.datetime.now(ZoneInfo("America/New_York")).date().isoformat()
    except Exception:
        return (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=5)).date().isoformat()


def run(home: str, out_dir: str, rules_path: str | None, today: str, files=None, extra_inbox=None, set_bal=None, quiet=False) -> dict:
    priv = os.path.join(home, "money")
    os.makedirs(priv, exist_ok=True)
    os.makedirs(os.path.join(home, "money_inbox"), exist_ok=True)
    rules_doc, where = load_rules(rules_path)
    if where == "defaults":
        alt = os.path.join(priv, "money_rules.json")
        if os.path.isfile(alt):
            rules_doc, where = load_rules(alt)
    lpath = os.path.join(priv, "ledger.json")
    ledger = load_ledger(lpath)
    paths = list(files) if files else inbox_files(inbox_dirs(home, extra_inbox))
    rep = import_paths(ledger, paths, today, force=bool(files))
    write_json(lpath, ledger)
    bpath = os.path.join(priv, "balances.json")
    bal = load_balances(bpath)
    for r in rep:
        for b in r.get("balances") or []:
            set_balance(bal, b["name"], b["usd"], b.get("kind") or "", b.get("date") or today)
    for s in set_bal or []:
        if "=" in s:
            name, val = s.split("=", 1)
            v = parse_amount(val)
            if v is not None and name.strip():
                set_balance(bal, name.strip(), v, "", today)
    write_json(bpath, bal, indent=1)
    kb = kalshi_balance(home)
    nw = networth(bal, kb)
    hist = update_history(os.path.join(priv, "networth_history.json"), today, nw)
    doc = build(ledger, rules_doc, today, bal, kb, hist, rep)
    doc["rules"] = "your rules" if where != "defaults" else "the default rules (python tools/money_import.py --init-rules to edit them)"
    write_json(os.path.join(out_dir, "household.json"), doc)
    write_json(os.path.join(priv, "household.json"), doc)
    write_json(os.path.join(priv, "oikos_ledger.json"), oikos_ledger(ledger, rules_doc, today, doc["avg3"]["out"], doc["networth"].get("liquid")), indent=None)
    if not quiet:
        n_add = sum(r.get("added", 0) for r in rep)
        n_dup = sum(r.get("dupes", 0) for r in rep)
        print(f"money import: {len(paths)} file(s), {n_add} new rows, {n_dup} already had; {doc['data']['rows']} rows in your private ledger -> {os.path.join(out_dir, 'household.json')}")
        for r in rep:
            if r["state"] != "already imported":
                print(f"  {r.get('name') or r.get('ext') or '?'}: {r['state']}" + (f", {r.get('added', 0)} new, {r.get('dupes', 0)} duplicates, {r.get('skipped', 0)} rows skipped ({r.get('first')} to {r.get('last')})" if r["state"] == "imported" else ""))
    return doc


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Import your own bank / card exports into a private ledger (free, offline, paper only).")
    ap.add_argument("--home", help="the private folder (default %%USERPROFILE%%\\.olympus or OLYMPUS_HOME)")
    ap.add_argument("--inbox", help="another drop folder to read")
    ap.add_argument("--file", action="append", help="import this file (repeatable)")
    ap.add_argument("--out", default=DEFAULT_OUT, help="where household.json goes (default money_out/)")
    ap.add_argument("--rules", default=DEFAULT_RULES)
    ap.add_argument("--balance", action="append", help='"Name=1234.56" sets one balance in your net-worth file')
    ap.add_argument("--init-rules", action="store_true", help="write the default rules to --rules (never overwrites)")
    ap.add_argument("--today")
    ap.add_argument("--print", dest="show", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args(argv)
    if a.init_rules:
        if os.path.exists(a.rules):
            print(f"{a.rules} already exists: not changed")
        else:
            write_json(a.rules, DEFAULT_RULES_DOC, indent=1)
            print(f"wrote the default rules to {a.rules}: edit them freely")
        return 0
    today = a.today if a.today and parse_date(a.today) == a.today else today_et()
    doc = run(a.home or olympus_dir(), a.out, a.rules, today, a.file, a.inbox, a.balance, a.quiet)
    if a.show:
        print(table(doc))
    return 0


if __name__ == "__main__":
    sys.exit(main())
