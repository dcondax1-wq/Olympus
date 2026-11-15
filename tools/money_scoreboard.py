#!/usr/bin/env python3
"""MONEY SCOREBOARD (owner 2026-11-13, "I want everything connected ... make me money"): ONE file with every money source, read-only.

  python tools/money_scoreboard.py                       read the sources, write tools/web_public/money/scoreboard.json (gitignored)
  python tools/money_scoreboard.py --site <site_dir>     the site build: read <site>/home.json, kalshi.json, money/index.json ... and
                                                         write <site>/money/scoreboard.json (the Ledger page's Scoreboard card reads it)
  python tools/money_scoreboard.py --private             also count your own ledger (data/money_ledger.json) in the written file
  python tools/money_scoreboard.py --print               print the plain table, write nothing
  options: --out FILE  --ledger FILE  --kalshi FILE  --now EPOCH_S (tests)

What it reads (every one optional; a missing one is LISTED as missing, never invented):
  accounts   <site>/home.json, else <site>/data.json, else the PC's data/pc_report/live.json: the NQ accounts by the SAME rules as
             tools/web_public/olympus/truth.js accountsOf (board.<key> first, then the PC's own row, never the cloud paper twin;
             ATLAS from second.account_b, BLITZ from live.pc.blitz, paper). Eval and funded P&L is performance, NOT cash.
  second     home.json "second": the paper second strategies (paper only, never cash).
  kalshi     <site>/kalshi.json (the feed the PC puts on the site), else --kalshi, else %USERPROFILE%\\.olympus\\kalshi_feed\\kalshi.json:
             the Kalshi bot's REAL money (shape of tools/web_public/kalshi/kalshi.js: t, balance, total_pnl, week_pnl, month_pnl, days).
  machines   <site>/money/index.json (tools/money_engine.py): ideas with an ESTIMATED $ a month, never counted as cash.
  prices     tools/web_public/ledger/rules.json (the owner's real eval prices and dates); without it the CLAUDE.md prices
             (Builder 50K $91.80 on 2026-10-18, the ATLAS 25K $43 on 2026-10-26, Builder 25K $63, $0 activation).
  plan       tools/web_public/plutus/plans.json: the Plutus study's $ a month from purchase (H2 = the Jul-Oct check), an ESTIMATE.
  household  money_out/household.json, else %USERPROFILE%\\.olympus\\money\\household.json (tools/money_import.py: your own bank / card
             exports): this month's money in / out, runway, subscriptions, leaks, net worth, prop-firm fees vs payouts as the BANK saw them.
             Shown apart (never added to the cash totals, which come from the ledger + the eval prices). PRIVATE like the ledger: in a
             written file only with --private.
  agency     money_out/agency.json (agency/billing, 2026-11-14; --agency FILE): the website agency's client payments as daily cash in /
             out (+ MRR and churn in its row). Real cash, PRIVATE like the ledger: counted only with --private or "publish": true in
             the file; a sample file is never counted; when your own ledger has entries for acct "agency" those win (no double count).
  ledger     data/money_ledger.json (gitignored, owner-editable): eval purchases, resets, payouts, Kalshi deposits, expenses. The
             same format as the Ledger app's Export JSON ({"entries": [{"kind", "amount", "date", "acct", "note"}]}), so an export
             saved there works as is. PRIVATE by default: it is counted in a written file only with --private or "publish": true
             in the file (the site is public); notes are never written anywhere.

Cash = money that really moved: payouts received + other income + the Kalshi result - eval fees - resets - activation - expenses.
Nothing here trades, sends anything or reads a key. Stdlib only. Test: python -X utf8 -m tests.test_money_scoreboard
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
WEB = os.path.join(HERE, "web_public")
DEFAULT_OUT = os.path.join(WEB, "money", "scoreboard.json")
DEFAULT_LEDGER = os.path.join(ROOT, "data", "money_ledger.json")
HOUSEHOLD = os.path.join(ROOT, "money_out", "household.json")
PC_LIVE = os.path.join(ROOT, "data", "pc_report", "live.json")
RULES = os.path.join(WEB, "ledger", "rules.json")
PLANS = os.path.join(WEB, "plutus", "plans.json")
AGENCY = os.path.join(ROOT, "money_out", "agency.json")      # agency/billing's summary (python -m agency.billing summary)
AGENCY_STALE_S = 35 * 86400                                  # the kit rewrites it on every change; a month without one is old
VERSION = 1
MILESTONES = (10_000, 100_000, 1_000_000)
MIN_DAYS_FOR_RATE = 28            # a cash run-rate needs four weeks of data
DAYS_PER_MONTH = 30.4375
# how old a source may be before it is called stale (seconds)
STALE_S = {"accounts": 36 * 3600, "kalshi": 6 * 3600, "machines": 24 * 3600, "second": 36 * 3600, "ledger": 45 * 86400, "household": 40 * 86400}

# the owner's real prices (CLAUDE.md "Prop-firm prices"), used only when ledger/rules.json is missing
PRICES = {"builder_50k": 91.80, "builder_25k": 63.00, "atlas_25k": 43.00, "activation": 0.0}
FALLBACK_ACCOUNTS = {"lit50k": {"name": "MFFU Builder 50K eval (Zlarior)", "price": PRICES["builder_50k"], "paid": "2026-10-18"},
                     "atlas25k": {"name": "MFFU Builder 25K eval (ATLAS)", "price": PRICES["atlas_25k"], "paid": "2026-10-26"}}

# the Ledger app's kinds (tools/web_public/ledger/ledgercore.js KINDS): dir +1 = cash in, -1 = cash out, 0 = neither
KINDS = {"fee": -1, "reset": -1, "activation": -1, "expense": -1, "payout_in": 1, "payout_req": 0, "income": 1,
         "deposit": 0, "withdrawal": 0, "tax": 0}
PROP_COST = ("fee", "reset", "activation")
EVERY = ("week", "month", "year")

# truth.js META + the published-field order (accountsOf)
META = {"lit": {"name": "Zlarior", "bot": "LIT", "size": "50K", "start": 50000.0, "mll": 2000.0, "target": 3000.0, "paper": False},
        "atlas": {"name": "ATLAS", "bot": "ATLAS", "size": "25K", "start": 25000.0, "mll": 1000.0, "target": 1500.0, "paper": False},
        "blitz": {"name": "BLITZ", "bot": "BLITZ", "size": "25K", "start": 25000.0, "mll": 1000.0, "target": 1500.0, "paper": True}}
ROW_RE = {"lit": re.compile(r"mffu50k|zlarior|builder 50k|\blit\b|\b50k\b"), "atlas": re.compile(r"atlas|acctb|acct_b"),
          "blitz": re.compile(r"blitz|acct_c")}
PLAN_ID = {"lit": "lit_50k", "atlas": "atlas_25k", "blitz": "blitz_25k"}


# ------------------------------------------------------------------------------------------------ small helpers
def num(v):
    """A finite number or None (bool, nan, inf, junk text are not numbers). '$1,234' -> 1234."""
    if isinstance(v, bool):
        return None
    if isinstance(v, str):
        try:
            v = float(v.replace("$", "").replace(",", "").strip())
        except ValueError:
            return None
    if isinstance(v, (int, float)) and v == v and abs(v) != float("inf"):
        return float(v)
    return None


def first(*xs):
    for x in xs:
        v = num(x)
        if v is not None:
            return v
    return None


def r2(x) -> float:
    return round(float(x) + 0.0, 2)


def obj(x) -> dict:
    return x if isinstance(x, dict) else {}


def arr(x) -> list:
    return x if isinstance(x, list) else []


def text(v, n=80) -> str:
    s = v if isinstance(v, str) else (str(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else "")
    return " ".join(s.split())[:n]


def money(x, signed=False) -> str:
    v = num(x)
    if v is None:
        return "-"
    a = math.floor(abs(v) + 0.5)          # half up, the same as the page (scoreboardcore.usd)
    s = "${:,.0f}".format(a)
    if a == 0:
        return "$0"
    return ("-" if v < 0 else "+" if signed else "") + s


def read_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def mtime(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return None


def to_s(v):
    """epoch s / ms / ISO text -> epoch seconds, else None"""
    if v is None or v == "" or isinstance(v, bool):
        return None
    n = num(v) if not isinstance(v, str) or re.fullmatch(r"\s*\d+(\.\d+)?\s*", v) else None
    if n is not None:
        return n / 1000 if n > 1e12 else n
    try:
        t = dt.datetime.fromisoformat(str(v).strip().replace("Z", "+00:00"))
        return (t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)).timestamp()
    except ValueError:
        return None


def age_words(sec) -> str:
    """the same words as truth.js ageWords: '47 minutes', '5 hours 12 minutes', '4 days 3 hours'"""
    s = max(0, int(num(sec) or 0))
    pl = lambda n, w: f"{n} {w}{'' if n == 1 else 's'}"  # noqa: E731
    if s < 60:
        return "less than a minute"
    if s < 3600:
        return pl(s // 60, "minute")
    if s < 86400:
        h, m = s // 3600, (s % 3600) // 60
        return pl(h, "hour") + (" " + pl(m, "minute") if m else "")
    d, h = s // 86400, (s % 86400) // 3600
    return pl(d, "day") + (" " + pl(h, "hour") if h else "")


# ------------------------------------------------------------------------------------------------ dates (ISO strings, New York days)
def today_et(now_s: float) -> str:
    try:
        from zoneinfo import ZoneInfo
        return dt.datetime.fromtimestamp(now_s, ZoneInfo("America/New_York")).strftime("%Y-%m-%d")
    except Exception:
        return dt.datetime.fromtimestamp(now_s - 5 * 3600, dt.timezone.utc).strftime("%Y-%m-%d")


def day_of(t_s) -> str | None:
    return today_et(t_s) if num(t_s) is not None else None


def is_date(s) -> bool:
    if not isinstance(s, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
        return False
    try:
        dt.date.fromisoformat(s)
        return True
    except ValueError:
        return False


def d_of(s: str) -> dt.date:
    return dt.date.fromisoformat(s)


def add_days(s: str, n: int) -> str:
    return (d_of(s) + dt.timedelta(days=n)).isoformat()


def add_months(s: str, n: int) -> str:
    """the same day of the month, clamped (31 Jan + 1 month = 28/29 Feb), as ledgercore.addMonths"""
    d = d_of(s)
    m0 = d.month - 1 + n
    y, m = d.year + m0 // 12, m0 % 12 + 1
    last = (dt.date(y + (m == 12), m % 12 + 1, 1) - dt.timedelta(days=1)).day
    return dt.date(y, m, min(d.day, last)).isoformat()


def week_start(s: str) -> str:
    """Monday of the week of s"""
    return add_days(s, -d_of(s).weekday())


# ------------------------------------------------------------------------------------------------ the owner's ledger
def clean_entry(e, keep_note=False):
    """ledgercore.cleanEntry: a known kind, an amount > 0, a real date; acct defaults to 'general'. Notes only when asked."""
    if not isinstance(e, dict) or e.get("kind") not in KINDS:
        return None
    amount = num(e.get("amount"))
    if amount is None or amount <= 0 or amount > 1e9 or not is_date(e.get("date")):
        return None
    out = {"kind": e["kind"], "amount": r2(amount), "date": e["date"], "acct": text(e.get("acct"), 40) or "general"}
    if keep_note and text(e.get("note"), 160):
        out["note"] = text(e.get("note"), 160)
    rec = obj(e.get("rec"))
    if rec.get("every") in EVERY:
        out["rec"] = {"every": rec["every"], "until": rec.get("until") if is_date(rec.get("until")) else None}
    if e.get("auto"):
        out["auto"] = True
    if e.get("key"):
        out["key"] = text(e.get("key"), 80)
    return out


def occurrences(e: dict, today: str) -> list:
    """the dated copies of an entry up to today (recurring: every week / month / year until 'until')"""
    if not e.get("rec"):
        return [e["date"]] if e["date"] <= today else []
    until = e["rec"].get("until")
    stop = until if until and until < today else today
    out = []
    for i in range(1200):
        every = e["rec"]["every"]
        d = add_days(e["date"], 7 * i) if every == "week" else add_months(e["date"], i if every == "month" else 12 * i)
        if d > stop:
            break
        out.append(d)
    return out


def expand(entries: list, today: str) -> list:
    return [{**{k: v for k, v in e.items() if k != "rec"}, "date": d, "recurring": bool(e.get("rec"))} for e in entries for d in occurrences(e, today)]


def load_ledger(path: str, keep_notes=False) -> dict:
    """-> {"state": ok|missing|bad, "entries", "hidden", "publish", "skipped", "t"}. Never raises."""
    raw = read_json(path) if path and os.path.exists(path) else None
    if raw is None:
        return {"state": "missing" if not (path and os.path.exists(path)) else "bad", "entries": [], "hidden": [], "publish": False, "skipped": 0, "t": mtime(path) if path else None}
    src = raw if isinstance(raw, list) else arr(obj(raw).get("entries"))
    ent = [c for c in (clean_entry(e, keep_notes) for e in src[:5000]) if c and not c.get("auto")]
    return {"state": "ok", "entries": ent, "hidden": [text(x, 80) for x in arr(obj(raw).get("hidden")) if text(x, 80)][:200],
            "publish": obj(raw).get("publish") is True, "skipped": len(src) - len(ent), "t": mtime(path)}


# ------------------------------------------------------------------------------------------------ the accounts, as truth.js accountsOf
def _row_of(home: dict, key: str):
    for a in arr(home.get("accounts")):
        if not isinstance(a, dict) or a.get("error"):
            continue
        s = " ".join(str(a.get(k) or "") for k in ("id", "name", "plan", "strategy")).lower()
        if key != "blitz" and (str(a.get("source") or "").lower() == "cloud" or re.search(r"\bcloud\b", s)):
            continue
        if key == "lit" and (ROW_RE["atlas"].search(s) or ROW_RE["blitz"].search(s)):
            continue
        if ROW_RE[key].search(s):
            return a
    return None


def _block_of(key: str, home: dict):
    board, pc, row = obj(home.get("board")), obj(obj(home.get("live")).get("pc")), _row_of(home, key)
    b = board.get(key)
    if isinstance(b, dict) and num(b.get("room")) is not None:
        return {"e": b, "today": first(b.get("today_pnl"), b.get("today")), "week": b.get("week_pnl"), "src": "board." + key, "row": row}
    if row and (isinstance(row.get("eval"), dict) or isinstance(row.get("funded_eval"), dict)):
        e = row["eval"] if isinstance(row.get("eval"), dict) else row["funded_eval"]
        return {"e": e, "today": first(obj(row.get("pnl")).get("today"), e.get("today")), "week": obj(row.get("pnl")).get("week"),
                "src": "accounts." + str(row.get("id") or key), "row": row}
    if key == "atlas":
        ab = obj(obj(home.get("second")).get("account_b"))
        if isinstance(ab.get("eval"), dict):
            return {"e": ab["eval"], "today": first(ab["eval"].get("today"), ab.get("day_pnl")), "week": None, "src": "second.account_b", "row": None}
    if key == "blitz":
        bl = obj(pc.get("blitz"))
        if isinstance(bl.get("eval"), dict):
            return {"e": bl["eval"], "today": bl["eval"].get("today"), "week": None, "src": "live.pc.blitz", "row": None}
    return None


def _report_t(key: str, home: dict):
    board, pc = obj(home.get("board")), obj(obj(home.get("live")).get("pc"))
    if key == "atlas":
        return first(obj(pc.get("second")).get("t"), pc.get("t"), obj(home.get("second")).get("pc_t"), board.get("data_t"),
                     obj(obj(_row_of(home, "atlas")).get("conn")).get("t"))
    if key == "blitz":
        return first(obj(pc.get("blitz")).get("t"), pc.get("t") if isinstance(pc.get("blitz"), dict) else None,
                     obj(obj(_row_of(home, "blitz")).get("conn")).get("t"))
    row = _row_of(home, "lit")
    return first(pc.get("t"), board.get("data_t"), obj(row.get("conn")).get("t") if row else None)


def accounts_of(home) -> dict:
    """truth.js accountsOf, the numbers the scoreboard needs. Never raises; an account without numbers has has = False."""
    h, out = obj(home), {}
    for key, M in META.items():
        base = {"key": key, "name": M["name"], "bot": M["bot"], "size": M["size"], "has": False, "balance": None, "profit": None, "today": 0.0,
                "week": 0.0, "room": None, "mll": M["mll"], "kind": "paper" if M["paper"] else "eval", "status": "", "paper": M["paper"], "t": None, "src": ""}
        blk = _block_of(key, h)
        if not blk:
            out[key] = base
            continue
        e = blk["e"]
        start, mll = first(e.get("start_balance"), M["start"]), first(e.get("mll"), M["mll"])
        bal = num(e.get("balance"))
        profit = first(e.get("profit"), bal - start if bal is not None else None)
        room = num(e.get("room"))
        kind_raw = str(obj(blk["row"]).get("kind") or e.get("kind") or ("funded" if e.get("stage") == "funded" else "")).lower()
        out[key] = {**base, "has": True, "balance": bal, "profit": profit, "today": num(blk["today"]) or 0.0, "week": num(blk["week"]) or 0.0,
                    "room": None if room is None else max(0.0, min(mll, room)), "mll": mll,
                    "kind": "funded" if kind_raw == "funded" else ("paper" if M["paper"] else "eval"),
                    "status": text(e.get("status"), 40), "t": _report_t(key, h), "src": blk["src"]}
    return out


def key_of_acct(acct_id: str):
    s = str(acct_id or "").lower()
    if "atlas" in s or "acctb" in s:
        return "atlas"
    if "blitz" in s:
        return "blitz"
    if "lit" in s or "50k" in s or "zlarior" in s:
        return "lit"
    return None


# ------------------------------------------------------------------------------------------------ eval fees the site already knows (AUTO)
def auto_fees(home, rules, today: str) -> tuple[list, str]:
    """-> (entries, where the prices came from). Every account in rules.json "accounts" is a real purchase at the owner's price; an
    account of home.json goals the rules do not know uses home.json's own price (ledgercore.autoEntries, but every purchase counts)."""
    known = obj(obj(rules).get("accounts"))
    basis = "ledger/rules.json (your real prices)"
    if not known:
        known, basis = FALLBACK_ACCOUNTS, "CLAUDE.md prices (rules.json missing)"
    out, seen = [], set()
    for aid, a in known.items():
        price = num(obj(a).get("price"))
        if price is None or price <= 0:
            continue
        paid = obj(a).get("paid") if is_date(obj(a).get("paid")) else today
        out.append({"key": f"auto:fee:{aid}", "kind": "fee", "amount": r2(price), "date": min(paid, today), "acct": str(aid), "auto": True,
                    "name": text(obj(a).get("name"), 60) or str(aid)})
        seen.add(str(aid))
    for a in arr(obj(obj(home).get("goals")).get("accounts")):
        aid = text(obj(a).get("id"), 40)
        price = num(obj(a).get("price"))
        if not aid or aid in seen or price is None or price <= 0:
            continue
        start = obj(a.get("eval")).get("start")
        d = start if is_date(start) else today
        out.append({"key": f"auto:fee:{aid}", "kind": "fee", "amount": r2(price), "date": min(d, today), "acct": aid, "auto": True,
                    "name": text(a.get("name"), 60) or aid})
        seen.add(aid)
    return out, basis


def merge(entries: list, hidden: list, auto: list) -> tuple[list, list]:
    """ledgercore.merge: an auto fee is dropped when the owner entered that kind for that account himself, or hid its key"""
    have = {(e["kind"], e["acct"]) for e in entries if e["kind"] in PROP_COST}
    shown = [a for a in auto if a["key"] not in hidden and (a["kind"], a["acct"]) not in have]
    return entries + shown, shown


def bot_payouts(home, own: list, today: str) -> list:
    """Payouts recorded with the bot (engine/money_goal.py -> home.json goals.money.payouts: [{day, gross, to_you, type, name}]) as
    payout_in entries of what reached you (to_you). One the owner's ledger already has (same account, same day, the gross or the
    to-you amount) is not counted twice."""
    out = []
    for p in arr(obj(obj(obj(home).get("goals")).get("money")).get("payouts")):
        p = obj(p)
        amt, day = first(p.get("to_you"), p.get("gross")), p.get("day")
        if amt is None or amt <= 0 or not is_date(day) or day > today:
            continue
        label = text(p.get("name"), 60) or text(p.get("type"), 40)
        key = key_of_acct(label) or key_of_acct(p.get("type"))
        acct = {"lit": "lit50k", "atlas": "atlas25k", "blitz": "blitz"}.get(key) or ("prop:" + (label or "funded"))[:40]
        gross = num(p.get("gross"))
        dup = any(e["kind"] == "payout_in" and e["acct"] == acct and e["date"] == day and
                  (abs(e["amount"] - amt) < 0.01 or (gross is not None and abs(e["amount"] - gross) < 0.01)) for e in own)
        if not dup:
            out.append({"kind": "payout_in", "amount": r2(amt), "date": day, "acct": acct, "bot": True, "name": label})
    return out


# ------------------------------------------------------------------------------------------------ Kalshi (real money)
def kalshi_result(entries: list, feed) -> dict:
    """ledgercore.kalshiResult: deposits recorded -> balance + withdrawals - deposits; else the bot's own total P&L; else unknown"""
    dep = r2(sum(e["amount"] for e in entries if e["kind"] == "deposit"))
    wd = r2(sum(e["amount"] for e in entries if e["kind"] == "withdrawal"))
    f = obj(feed)
    bal, tot = num(f.get("balance")), num(f.get("total_pnl"))
    days = [[d[0], num(d[1])] for d in arr(f.get("days")) if isinstance(d, list) and len(d) >= 2 and is_date(d[0]) and num(d[1]) is not None]
    base = {"deposits": dep, "withdrawals": wd, "balance": bal, "total": tot, "days": days, "t": to_s(f.get("t")),
            "week_pnl": num(f.get("week_pnl")), "month_pnl": num(f.get("month_pnl")), "today_pnl": num(f.get("today_pnl"))}
    if bal is not None and dep > 0:
        return {**base, "result": r2(bal + wd - dep), "basis": "balance"}
    if tot is not None:
        return {**base, "result": r2(tot), "basis": "bot"}
    return {**base, "result": None, "basis": "none"}


def kalshi_in(k: dict, start: str, end: str, which: str):
    """the bot's P&L inside [start, end]: its daily results; without days, its own week / month figure when its report is inside"""
    if k["basis"] == "none":
        return 0.0
    if k["days"]:
        return r2(sum(v for d, v in k["days"] if start <= d <= end))
    fd = day_of(k["t"]) if k["t"] else None
    v = k.get("week_pnl" if which == "week" else "month_pnl")
    return r2(v) if v is not None and fd and start <= fd <= end else 0.0


# ------------------------------------------------------------------------------------------------ the website agency (agency/billing)
def agency_part(ag, include: bool, own: list, today: str, now: float) -> tuple[list, dict | None, dict]:
    """-> (entries, info for its row, its source line). The kit's daily [date, cash in, cash out] rows become income / expense entries of
    acct "agency" (cash out = refunds + processor fees). Counted only when the ledger would be (include) or the file says publish;
    a sample file never; the owner's own ledger entries for acct "agency" win over the kit's."""
    ag = ag if isinstance(ag, dict) and ag.get("kind") == "olympus-agency-income" else None
    src = {"sid": "agency", "name": "Website agency (client payments)", "kind": "cash", "state": "off", "t": None, "now": now, "file": None,
           "note": "Not started: python -m agency.billing (agency/billing/PAYMENTS.md)."}
    if not ag:
        return [], None, src
    t = to_s(ag.get("built")) or num(ag.get("t"))
    mrr = obj(ag.get("mrr"))
    info = {"mrr": num(mrr.get("now")), "clients": int(num(mrr.get("clients")) or 0), "text": text(ag.get("text"), 240), "t": t}
    src.update(t=t, file="money_out/agency.json", note=f"MRR {money(info['mrr'])} from {info['clients']} client{'' if info['clients'] == 1 else 's'}")
    if ag.get("status") == "sample":
        src.update(state="sample", note="SAMPLE numbers: never counted as cash")
        return [], None, src
    if not (include or ag.get("publish") is True):
        src.update(state="private", note="kept private (run with --private, or python -m agency.billing setup --publish yes)")
        return [], None, src
    if any(e["acct"] == "agency" for e in own):
        src.update(state="ok", note=src["note"] + "; your ledger has agency entries, those are counted instead (no double count)")
        return [], info, src
    out = []
    for d in arr(ag.get("days")):
        if isinstance(d, list) and len(d) >= 3 and is_date(d[0]) and d[0] <= today:
            for kind, v in (("income", num(d[1])), ("expense", num(d[2]))):
                if v is not None and 0 < v < 1e9:
                    out.append({"kind": kind, "amount": r2(v), "date": d[0], "acct": "agency", "agency": True})
    src.update(state="stale" if t is not None and now - t > AGENCY_STALE_S else "ok", note=src["note"] + f"; {len(out)} cash rows")
    return out, info, src


# ------------------------------------------------------------------------------------------------ the sums
def sums(entries: list, start: str = "0000-01-01", end: str = "9999-12-31") -> dict:
    s = {k: 0.0 for k in KINDS}
    for e in entries:
        if start <= e["date"] <= end:
            s[e["kind"]] += e["amount"]
    cin, cost = s["payout_in"] + s["income"], s["fee"] + s["reset"] + s["activation"] + s["expense"]
    return {"payouts": r2(s["payout_in"]), "income": r2(s["income"]), "fees": r2(s["fee"]), "resets": r2(s["reset"]),
            "activation": r2(s["activation"]), "expenses": r2(s["expense"]), "cash_in": r2(cin), "cash_out": r2(cost),
            "requested": r2(s["payout_req"]), "deposits": r2(s["deposit"]), "withdrawals": r2(s["withdrawal"]), "tax": r2(s["tax"])}


def net_in(entries: list, start: str, end: str) -> float:
    s = sums(entries, start, end)
    return r2(s["cash_in"] - s["cash_out"])


def pending_requests(entries: list) -> float:
    """payout requests not yet matched by a payout received for that account since (the full amount, or the 80% split)"""
    got = [e for e in entries if e["kind"] == "payout_in"]
    left = 0.0
    for r in (e for e in entries if e["kind"] == "payout_req"):
        if not any(g["acct"] == r["acct"] and g["date"] >= r["date"] and (abs(g["amount"] - r["amount"]) < 0.01 or abs(g["amount"] - r["amount"] * 0.8) < 0.015 * r["amount"] + 0.01) for g in got):
            left += r["amount"]
    return r2(left)


def window(entries: list, k: dict, start: str, end: str, which: str) -> dict:
    s = sums(entries, start, end)
    kal = k["result"] if which == "all" and k["result"] is not None else (0.0 if which == "all" else kalshi_in(k, start, end, which))
    cin, cout = s["cash_in"] + max(0.0, kal), s["cash_out"] + max(0.0, -kal)
    return {"from": start if which != "all" else None, "to": end, "cash_in": r2(cin), "cash_out": r2(cout), "net": r2(cin - cout),
            "payouts": s["payouts"], "fees": s["fees"], "kalshi": r2(kal)}


# ------------------------------------------------------------------------------------------------ the scoreboard
def _source(sid, name, kind, state, t=None, now=None, file=None, note=""):
    age = None if t is None or now is None else max(0, int(now - t))
    if state == "ok" and age is not None and age > STALE_S.get(sid, 10 ** 9):
        state = "stale"
    return {"id": sid, "name": name, "kind": kind, "status": state, "t": int(t) if t is not None else None, "age_s": age,
            "age": "never" if age is None else age_words(age) + " ago", "file": file, "note": note}


def _plan_rate(plans, keys: list) -> dict | None:
    accts = {a.get("id"): a for a in arr(obj(obj(plans).get("strategy")).get("accounts")) if isinstance(a, dict)}
    parts, total = [], 0.0
    for k in keys:
        a = accts.get(PLAN_ID.get(k))
        v = num(obj(obj(a).get("net_per_month_from_purchase")).get("H2"))
        if v is not None:
            parts.append({"key": k, "name": text(a.get("name"), 60), "per_month": r2(v)})
            total += v
    if not parts:
        return None
    return {"per_month": r2(total), "parts": parts, "span": "H2 (Jul-Oct 2026, the honest check)",
            "text": f"Plutus study estimate: {money(total)} a month from purchase for {' + '.join(p['name'] for p in parts)} (H2 check). An estimate, not cash."}


def _eta(left: float, rate, today: str):
    if rate is None or rate <= 0:
        return None
    m = max(1, math.ceil(left / rate))
    return {"months": m, "date": add_months(today, m) if m <= 1200 else None}


def build(inputs: dict, now: float, include_ledger: bool = True) -> dict:
    """The scoreboard from loaded inputs (pure: no file, no clock). inputs = {home, home_file, home_kind, kalshi, kalshi_file, machines,
    machines_file, rules, plans, ledger (load_ledger result), ledger_file}."""
    today = today_et(now)
    home, rules, plans = inputs.get("home"), inputs.get("rules"), inputs.get("plans")
    led = inputs.get("ledger") or {"state": "missing", "entries": [], "hidden": [], "publish": False, "t": None}
    use_led = led["state"] == "ok" and (include_ledger or led.get("publish"))
    own = expand(led["entries"], today) if use_led else []
    auto, price_basis = auto_fees(home, rules, today)
    entries, auto_shown = merge(own, led["hidden"] if use_led else [], auto)
    pays = bot_payouts(home, own, today)
    entries += pays
    ag_entries, ag_info, ag_src = agency_part(inputs.get("agency"), include_ledger, own, today, now)
    entries += ag_entries
    feed = inputs.get("kalshi")
    feed = feed if isinstance(feed, dict) and (feed.get("kind") in (None, "kalshi")) and (num(feed.get("balance")) is not None or num(feed.get("total_pnl")) is not None or feed.get("days")) else None
    k = kalshi_result(entries, feed)
    A = accounts_of(home) if isinstance(home, dict) else {key: {"has": False} for key in META}

    wk, mo = week_start(today), today[:8] + "01"
    totals = {"week": window(entries, k, wk, today, "week"), "month": window(entries, k, mo, today, "month"), "all": window(entries, k, "0000-01-01", today, "all")}
    totals["all"]["pending"] = pending_requests(entries)

    # ---- by source: each eval / funded account, Kalshi, general, then the paper-only ones
    ids = []
    for e in entries:
        if e["acct"] not in ids and e["acct"] not in ("kalshi", "general", "agency"):
            ids.append(e["acct"])
    names = {a["acct"]: a["name"] for a in auto + pays}
    for aid, a in obj(obj(rules).get("accounts")).items():
        names.setdefault(aid, text(obj(a).get("name"), 60))
    rows = []
    for aid in ids:
        mine = [e for e in entries if e["acct"] == aid]
        s, key = sums(mine), key_of_acct(aid)
        acc = A.get(key) if key else None
        cost = s["fees"] + s["resets"] + s["activation"] + s["expenses"]
        kind = acc["kind"] if acc and acc.get("has") else ("funded" if s["payouts"] > 0 else "eval")
        row = {"id": aid, "name": names.get(aid) or aid, "kind": kind, "group": "prop", "cash_in": s["cash_in"], "cash_out": r2(cost),
               "net": r2(s["cash_in"] - cost), "fees": s["fees"], "resets": s["resets"], "payouts": s["payouts"],
               "pending": pending_requests(mine), "auto_fee": any(e.get("auto") for e in mine),
               "week": net_in(mine, wk, today), "month": net_in(mine, mo, today),
               "roi_pct": r2((s["cash_in"] - cost) / cost * 100) if cost > 0 else None}
        if acc and acc.get("has"):
            row["paper"] = {"bot": acc["bot"], "balance": acc["balance"], "profit": acc["profit"], "today": acc["today"], "week": acc["week"],
                            "room": acc["room"], "mll": acc["mll"], "status": acc["status"], "t": acc["t"],
                            "text": f"{acc['bot']} {acc['kind']}: {money(acc['profit'], True)} on paper (not cash)"
                                    + (f", drawdown left {money(acc['room'])} of {money(acc['mll'])} max loss" if acc["room"] is not None else "")}
        row["t"] = acc["t"] if acc and acc.get("has") else None
        rows.append(row)
    kal_row = None
    if k["basis"] != "none" or k["deposits"] > 0:
        kal_row = {"id": "kalshi", "name": "Kalshi bot (real money)", "kind": "kalshi", "group": "cash", "basis": k["basis"],
                   "net": k["result"], "balance": k["balance"], "deposits": k["deposits"], "withdrawals": k["withdrawals"],
                   "week": totals["week"]["kalshi"], "month": totals["month"]["kalshi"], "t": k["t"],
                   "cash_in": r2(max(0.0, k["result"] or 0)), "cash_out": r2(max(0.0, -(k["result"] or 0))),
                   "text": ("balance + withdrawals - deposits" if k["basis"] == "balance" else "the bot's own total P&L (record your deposits for the true result)" if k["basis"] == "bot" else "deposits recorded, no feed")}
        rows.append(kal_row)
    gen = [e for e in entries if e["acct"] == "general"]
    if gen:
        s = sums(gen)
        rows.append({"id": "general", "name": "General (expenses, other income)", "kind": "general", "group": "cash", "cash_in": s["cash_in"],
                     "cash_out": s["cash_out"], "net": r2(s["cash_in"] - s["cash_out"]),
                     "week": net_in(gen, wk, today), "month": net_in(gen, mo, today), "t": None})
    agx = [e for e in entries if e["acct"] == "agency"]
    if agx or ag_info:
        s = sums(agx)
        rows.append({"id": "agency", "name": "Website agency (client payments)", "kind": "agency", "group": "cash", "cash_in": s["cash_in"],
                     "cash_out": s["cash_out"], "net": r2(s["cash_in"] - s["cash_out"]), "week": net_in(agx, wk, today), "month": net_in(agx, mo, today),
                     "mrr": (ag_info or {}).get("mrr"), "clients": (ag_info or {}).get("clients"), "text": (ag_info or {}).get("text", ""),
                     "t": (ag_info or {}).get("t")})

    paper = []
    for key, acc in A.items():
        if acc.get("has") and acc.get("paper"):
            paper.append({"id": key, "name": f"{acc['bot']} {acc['size']} (paper)", "kind": "paper", "profit": acc["profit"], "today": acc["today"],
                          "week": acc["week"], "room": acc["room"], "mll": acc["mll"], "t": acc["t"]})
    sec = obj(obj(home).get("second"))
    second = []
    for s in arr(sec.get("strategies")):
        if not isinstance(s, dict):
            continue
        p = obj(s.get("paper"))
        usd = num(p.get("usd"))
        if usd is None:
            continue
        second.append({"key": text(s.get("key"), 40), "name": text(s.get("label"), 70) or text(s.get("key"), 40), "trades": int(num(p.get("n")) or 0),
                       "usd": r2(usd), "routed": bool(s.get("route"))})
    if second:
        paper.append({"id": "second", "name": "Second strategies (paper trades)", "kind": "paper", "profit": r2(sum(x["usd"] for x in second)),
                      "trades": sum(x["trades"] for x in second), "t": to_s(sec.get("pc_t")) or to_s(sec.get("t")), "items": second})

    mi = obj(inputs.get("machines"))
    machines = None
    if mi:
        cnt, streams = obj(mi.get("counts")), [x for x in arr(mi.get("streams")) if isinstance(x, dict)]
        state = "sample" if streams and num(cnt.get("sample")) == len(streams) else "ok" if num(cnt.get("ok")) else "stale" if num(cnt.get("stale")) else "sample" if num(cnt.get("sample")) else "unknown"
        items = [{"id": text(x.get("id"), 30), "name": text(x.get("name") or x.get("id"), 40), "status": text(x.get("status"), 12),
                  "usd_month": num(obj(x.get("usd_month")).get("base")), "headline": text(x.get("headline"), 160)} for x in streams[:12]]
        machines = {"status": state, "usd_month": num(obj(mi.get("total")).get("base")), "real_usd_month": num(obj(mi.get("total")).get("real_base")),
                    "items": items, "text": "Ideas with an estimated $ a month; none of it is cash, and nothing here is counted in the totals."}

    # ---- ROI on eval fees, the run-rate, the milestones
    prop = [r for r in rows if r["group"] == "prop"]
    ps = sums([e for e in entries if e["acct"] in {r["id"] for r in prop}])
    fees = r2(ps["fees"] + ps["resets"] + ps["activation"])
    back = r2(sum(r["cash_in"] for r in prop))
    roi = {"fees": fees, "back": back, "net": r2(back - fees), "pct": r2((back - fees) / fees * 100) if fees > 0 else None}
    roi["text"] = ("No eval fees yet." if fees <= 0 else
                   f"{money(back)} back on {money(fees)} of eval fees: {roi['pct']:+.0f}%." if back > 0 else
                   f"{money(fees)} of eval fees, no payout yet ({roi['pct']:+.0f}%).")
    dates = [e["date"] for e in entries] + [d for d, _ in k["days"]]
    first_day = min(dates) if dates else None
    span = (d_of(today) - d_of(first_day)).days + 1 if first_day else 0
    net_all = totals["all"]["net"]
    cash_rate = r2(net_all / (span / DAYS_PER_MONTH)) if span >= MIN_DAYS_FOR_RATE else None
    have_keys = [key_of_acct(r["id"]) for r in prop if key_of_acct(r["id"]) in ("lit", "atlas")]
    plan = _plan_rate(plans, sorted(set(have_keys), key=["lit", "atlas"].index)) if have_keys else None
    rate = {"cash_per_month": cash_rate, "days": span, "since": first_day,
            "text": (f"{money(cash_rate, True)} a month in real cash over {span} days since {first_day}." if cash_rate is not None else
                     f"Too early for a cash run-rate: {span} day{'s' if span != 1 else ''} of data (needs {MIN_DAYS_FOR_RATE})." if first_day else
                     "No cash recorded yet."),
            "plan": plan}
    ms = []
    for m in MILESTONES:
        left = r2(m - net_all)
        ms.append({"usd": m, "reached": left <= 0, "left": max(0.0, left), "eta_cash": _eta(left, cash_rate, today) if left > 0 else None,
                   "eta_plan": _eta(left, plan["per_month"] if plan else None, today) if left > 0 else None})
    nxt = next((x for x in ms if not x["reached"]), None)
    if nxt:
        bits = [f"{money(nxt['left'])} to go to {money(nxt['usd'])}"]
        bits.append(f"about {nxt['eta_cash']['months']} months at the cash pace ({nxt['eta_cash']['date']})" if nxt["eta_cash"] else "no date at the cash pace yet")
        if nxt["eta_plan"]:
            bits.append(f"about {nxt['eta_plan']['months']} months at the plan estimate")
        nxt = {**nxt, "text": "; ".join(bits) + "."}

    # ---- sources and their ages
    hk = inputs.get("home_kind") or "home.json"
    pc_t = first(obj(obj(obj(home).get("live")).get("pc")).get("t"), obj(obj(home).get("board")).get("data_t")) if home else None
    built_t = to_s(obj(home).get("built")) if home else None
    sources = [
        _source("accounts", "NQ accounts (eval / funded, paper P&L)", "paper", "ok" if home else "missing", pc_t or built_t, now, inputs.get("home_file"),
                (f"from {hk}: " + ", ".join(f"{a['bot']} {money(a['profit'], True)}" for a in A.values() if a.get("has"))) if home else
                "No home.json / data.json / PC live.json: the accounts are not known here."),
        _source("kalshi", "Kalshi bot (real money)", "cash", "ok" if feed else "missing", k["t"], now, inputs.get("kalshi_file"),
                f"balance {money(k['balance'])}, result {money(k['result'], True)} ({k['basis']})" if feed else "No Kalshi feed on the site (kalshi.json); set kalshi_file in publish.json on the PC."),
        _source("ledger", "Your ledger (payouts, deposits, fees)", "cash",
                ("ok" if use_led else "private") if led["state"] == "ok" else led["state"], led.get("t"), now, "data/money_ledger.json",
                (f"{len(led['entries'])} entries" + ("" if use_led else " kept private (set \"publish\": true in the file to show them here)")) if led["state"] == "ok" else
                "No data/money_ledger.json: payouts and Kalshi deposits are not recorded here (save a Ledger Export JSON there)." if led["state"] == "missing" else "data/money_ledger.json is not valid JSON."),
        _source("payouts", "Payouts recorded with the bot", "cash", "ok" if pays else ("none" if home else "missing"), None, None,
                inputs.get("home_file") if pays else None,
                f"{len(pays)} payout{'s' if len(pays) != 1 else ''}, {money(sum(x['amount'] for x in pays))} to you" if pays else
                "No payout recorded with the bot yet (eval_life --payout / account_b --payout on the PC)."),
        _source("prices", "Eval prices", "cost", "ok", to_s(obj(obj(rules).get("source")).get("built")) if rules else None, None, "ledger/rules.json" if rules else "CLAUDE.md",
                f"{price_basis}; {len(auto_shown)} eval fee{'s' if len(auto_shown) != 1 else ''} filled in"),
        _source("second", "Second strategies (paper)", "paper", "ok" if second else "missing", to_s(sec.get("pc_t")) or to_s(sec.get("t")), now, inputs.get("home_file") if second else None,
                f"{len(second)} strategies, {money(sum(x['usd'] for x in second), True)} on paper" if second else "No second strategies in the accounts file."),
        _source("machines", "Money machines (estimates)", "estimate", ("sample" if machines and machines["status"] == "sample" else "ok") if machines else "missing",
                to_s(mi.get("asof")), now, inputs.get("machines_file"),
                ("SAMPLE numbers (the PC has not run RUN_MONEY.bat)" if machines["status"] == "sample" else f"estimates only, about {money(machines['usd_month'])} a month (not cash)") if machines else "No money/index.json."),
        _source("plan", "Plutus plan (estimate)", "estimate", "ok" if plan else "missing", None, None, "plutus/plans.json" if plans else None,
                plan["text"] if plan else "No plan estimate."),
    ]
    hh = inputs.get("household")
    hh = hh if isinstance(hh, dict) and hh.get("kind") == "olympus-household" else None
    household = household_block(hh) if hh and include_ledger else None
    sources.append(_source("household", "Household (your bank exports)", "cash", ("ok" if household else "private") if hh else "off",
                           to_s(hh.get("built")) if hh else None, now, inputs.get("household_file") if hh else None,
                           (household["text"] if household else "kept private (run with --private to show it here)") if hh else
                           "Not connected: drop your bank exports in the money inbox and run tools/money_import.py (docs/CONNECT_MONEY.md)."))
    sources.append(_source(**ag_src))
    missing =[{"id": s["id"], "name": s["name"], "why": s["note"]} for s in sources if s["status"] in ("missing", "bad")]

    words = []
    if not use_led:
        words.append("Payouts and Kalshi deposits you record in data/money_ledger.json are not in this copy" + (" (kept private)." if led["state"] == "ok" else "."))
    words.append("Eval and funded P&L is shown as paper, never as cash: it becomes cash only as a payout.")
    return {"v": VERSION, "kind": "olympus-money-scoreboard", "built": dt.datetime.fromtimestamp(now, dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "t": int(now), "today": today, "paper_only": True, "ledger_included": bool(use_led),
            "totals": totals, "roi": roi, "run_rate": rate, "milestones": ms, "next": nxt, "by_source": rows, "paper": paper,
            "machines": machines, "household": household, "sources": sources, "missing": missing, "notes": words}


def household_block(hh: dict) -> dict:
    """the bank-export summary (tools/money_import.py) in a few numbers: shown apart, never added to the cash totals"""
    tm, a3, pr, nw, run, sub, kal = (obj(hh.get(k)) for k in ("this_month", "avg3", "prop", "networth", "runway", "subscriptions", "kalshi"))
    b = {"today": text(hh.get("today"), 10), "month": text(tm.get("month"), 7), "in": num(tm.get("in")), "out": num(tm.get("out")), "net": num(tm.get("net")),
         "avg3": {"in": num(a3.get("in")), "out": num(a3.get("out")), "net": num(a3.get("net")), "months": int(num(a3.get("months")) or 0)},
         "runway_months": num(run.get("months")), "runway_text": text(run.get("text"), 220), "subs_month": num(sub.get("usd_month")),
         "subs_active": int(num(sub.get("active")) or 0), "leak_month": num(hh.get("leak_month")), "networth": num(nw.get("total")),
         "networth_30d": num(nw.get("change_30d")), "prop": {"fees": num(pr.get("fees")), "payouts": num(pr.get("payouts")), "net": num(pr.get("net")),
                                                            "roi_pct": num(pr.get("roi_pct"))}, "kalshi_moved": num(kal.get("net_moved")),
         "rows": int(num(obj(hh.get("data")).get("rows")) or 0), "status": text(hh.get("status"), 10)}
    bits = [f"this month {money(b['in'])} in, {money(b['out'])} out, net {money(b['net'], True)}" if b["month"] else "no month yet"]
    if b["runway_months"] is not None:
        bits.append(f"runway about {b['runway_months']:.1f} months")
    if b["networth"] is not None:
        bits.append(f"net worth {money(b['networth'])}")
    b["text"] = "From your bank exports: " + "; ".join(bits) + "."
    return b


# ------------------------------------------------------------------------------------------------ reading the files
def _kalshi_default():
    try:
        sys.path.insert(0, ROOT)
        from engine import nogithub
        d = nogithub.olympus_dir()
    except Exception:
        d = os.environ.get("OLYMPUS_HOME") or os.path.join(os.environ.get("USERPROFILE") or os.path.expanduser("~"), ".olympus")
    return os.path.join(d, "kalshi_feed", "kalshi.json")


def _household_default():
    try:
        sys.path.insert(0, ROOT)
        from engine import nogithub
        d = nogithub.olympus_dir()
    except Exception:
        d = os.environ.get("OLYMPUS_HOME") or os.path.join(os.environ.get("USERPROFILE") or os.path.expanduser("~"), ".olympus")
    return os.path.join(d, "money", "household.json")


def gather(site: str | None = None, ledger_path: str | None = None, kalshi_path: str | None = None, keep_notes=False, household_path: str | None = None,
           agency_path: str | None = None) -> dict:
    """Load every source that exists. Never raises."""
    site = site or WEB
    home = home_file = home_kind = None
    for p, kind in ((os.path.join(site, "home.json"), "home.json"), (os.path.join(site, "data.json"), "data.json"), (PC_LIVE, "the PC's live.json")):
        j = read_json(p)
        if isinstance(j, dict):
            home, home_file, home_kind = j, os.path.relpath(p, site) if p.startswith(site) else os.path.relpath(p, ROOT), kind
            break
    kal = kal_file = None
    for p in (os.path.join(site, "kalshi.json"), kalshi_path, _kalshi_default()):
        if p:
            j = read_json(p)
            if isinstance(j, dict):
                kal, kal_file = j, ("kalshi.json" if p == os.path.join(site, "kalshi.json") else "kalshi feed (PC)")
                break
    mach = mach_file = None
    for p in (os.path.join(site, "money", "index.json"), os.path.join(ROOT, "money_out", "index.json")):
        j = read_json(p)
        if isinstance(j, dict):
            mach, mach_file = j, "money/index.json"
            break
    rules = read_json(os.path.join(site, "ledger", "rules.json")) or read_json(RULES)
    plans = read_json(os.path.join(site, "plutus", "plans.json")) or read_json(PLANS)
    hh = hh_file = None
    for p in ([household_path] if household_path else [HOUSEHOLD, _household_default()]):
        j = read_json(p)
        if isinstance(j, dict) and j.get("kind") == "olympus-household":
            hh, hh_file = j, ("money_out/household.json" if p == HOUSEHOLD else "household.json (private folder)")
            break
    ag = read_json(agency_path or AGENCY)
    ag = ag if isinstance(ag, dict) and ag.get("kind") == "olympus-agency-income" else None
    return {"home": home, "home_file": home_file, "home_kind": home_kind, "kalshi": kal, "kalshi_file": kal_file, "machines": mach,
            "machines_file": mach_file, "rules": rules if isinstance(rules, dict) else None, "plans": plans if isinstance(plans, dict) else None,
            "ledger": load_ledger(ledger_path or DEFAULT_LEDGER, keep_notes), "household": hh, "household_file": hh_file, "agency": ag}


def write(sb: dict, path: str) -> str:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    try:                                   # hidden bots (engine/hidden_bots.py, dashboard_view.json; owner 2026-11-15: BLITZ off the pages)
        from engine import hidden_bots
        sb = hidden_bots.publish(sb)
    except Exception:
        pass
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(sb, fh, separators=(",", ":"), ensure_ascii=False)
    os.replace(tmp, path)
    return path


def table(sb: dict) -> str:
    """the plain table (the terminal and the Sunday report)"""
    T = sb["totals"]
    out = ["| What | This week | This month | All time |", "|---|---|---|---|",
           f"| Cash in | {money(T['week']['cash_in'])} | {money(T['month']['cash_in'])} | {money(T['all']['cash_in'])} |",
           f"| Cash out | {money(T['week']['cash_out'])} | {money(T['month']['cash_out'])} | {money(T['all']['cash_out'])} |",
           f"| **Net cash** | **{money(T['week']['net'], True)}** | **{money(T['month']['net'], True)}** | **{money(T['all']['net'], True)}** |"]
    out += ["", "| Source | Net (all time) | This week | Data age |", "|---|---|---|---|"]
    ages = {s["id"]: s["age"] for s in sb["sources"]}
    for r in sb["by_source"]:
        age = ages.get("kalshi") if r["id"] == "kalshi" else ages.get("accounts") if r.get("paper") else "-"
        extra = f" ({r['paper']['text']})" if r.get("paper") else ""
        out.append(f"| {r['name']}{extra} | {money(r['net'], True)} | {money(r.get('week'), True)} | {age} |")
    for p in sb["paper"]:
        out.append(f"| {p['name']} (paper, not cash) | {money(p.get('profit'), True)} | {money(p.get('week'), True) if p.get('week') is not None else '-'} | {ages.get('second' if p['id'] == 'second' else 'accounts')} |")
    out.append("")
    out.append(f"ROI on eval fees: {sb['roi']['text']} Run-rate: {sb['run_rate']['text']}")
    if sb.get("household"):
        out.append(sb["household"]["text"] + (" " + sb["household"]["runway_text"] if sb["household"].get("runway_text") else ""))
    if sb["next"]:
        out.append(f"Next milestone: {sb['next']['text']}")
    if sb["missing"]:
        out.append("Missing: " + "; ".join(f"{m['name']} ({m['why']})" for m in sb["missing"]))
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="One money scoreboard from every source (read-only, paper only).")
    ap.add_argument("--site", help="the built site folder: read its files, write <site>/money/scoreboard.json")
    ap.add_argument("--out")
    ap.add_argument("--ledger", default=DEFAULT_LEDGER)
    ap.add_argument("--kalshi")
    ap.add_argument("--household", help="a household.json from tools/money_import.py (default money_out/, then the private folder)")
    ap.add_argument("--agency", help="the website agency's summary (default money_out/agency.json, python -m agency.billing summary)")
    ap.add_argument("--private", action="store_true", help="count your ledger in the written file even without \"publish\": true")
    ap.add_argument("--print", dest="show", action="store_true")
    ap.add_argument("--now", type=float)
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args(argv)
    now = a.now if a.now is not None else time.time()
    sb = build(gather(a.site, a.ledger, a.kalshi, household_path=a.household, agency_path=a.agency), now, include_ledger=a.private or a.show)
    if a.show:
        print(table(sb))
        return 0
    path = a.out or (os.path.join(a.site, "money", "scoreboard.json") if a.site else DEFAULT_OUT)
    write(sb, path)
    if not a.quiet:
        T = sb["totals"]["all"]
        print(f"money scoreboard: net cash {money(T['net'], True)} all time, {len(sb['by_source'])} sources, {len(sb['missing'])} missing -> {path}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as e:  # a build step never stops the publish
        print("money scoreboard failed softly:", f"{e.__class__.__name__}: {str(e)[:200]}")
        sys.exit(0)
