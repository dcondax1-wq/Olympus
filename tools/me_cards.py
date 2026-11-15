"""ME CARDS (team ME1, 2026-11-14, docs/ME_HUB.md): your credit cards in one private file you fill once on the PC, for the Me hub.

  python tools/me_cards.py --add        asks per card: nickname, limit, balance, statement day, due day, APR, autopay
  python tools/me_cards.py --add --nick "Chase Freedom" --limit 5000 --balance 1200 --statement-day 3 --due-day 28 --apr 24.99 --autopay yes
  python tools/me_cards.py --list       use % per card and in total, the next due and statement dates, interest if carried
  python tools/me_cards.py --set "Chase Freedom" balance=900 due_day=27
  python tools/me_cards.py --remove "Chase Freedom"

The file is %USERPROFILE%\\.olympus\\me\\cards.json (OLYMPUS_HOME overrides): outside the repo, never published, owner-only.
NICKNAME ONLY: a nickname (or a match name) with 4 or more digits in a row (a card number, the last 4) is refused, and nothing here asks
for, reads or keeps any number printed on a card. The balance comes from your bank import when a balance in
%USERPROFILE%\\.olympus\\money\\balances.json (kind "debt", tools/money_import.py --balance) has the card's name (or its match name),
else from what you typed (with its date).

The math (pure functions, tests/test_me_hub.py):
  use        = balance / limit; total = all balances / all limits. Under 30% is fine, under 10% is best (the card reports the
               STATEMENT balance, so paying before the statement date lowers it)
  due date   = the next day of the month you gave (today included), clamped to short months (a due day 31 is Feb 28 / 29)
  interest   = balance x APR / 365 x 30 if you carry it one month (paid in full by the due date = $0)
  reminders  = 5 days and 1 day before each due date, pushed to your phone by tools/me_hub.py through the PC report's ntfy topic,
               with the nickname and the date only (never a balance)
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tools import me_core as M  # noqa: E402

FILE = "cards.json"
REMIND_DAYS = (5, 1)
UTIL_BEST, UTIL_FINE, UTIL_HIGH = 10.0, 30.0, 50.0
CYCLE_DAYS = 30
KEYS = ("nick", "limit", "balance", "balance_day", "statement_day", "due_day", "apr", "autopay", "match")
CONNECT = "On the PC: python tools\\me_cards.py --add (a nickname, the limit and the due day; never the card number)"


def path(env=None) -> str:
    return os.path.join(M.me_dir(env), FILE)


def balances_path(env=None) -> str:
    return os.path.join(M.olympus_dir(env), "money", "balances.json")


# ------------------------------------------------------------------------------------------------ one card, checked
def clean_name(s, what: str = "nickname"):
    n = re.sub(r"[^\w &'+.()/-]", "", M.clean(s, 40)).strip()
    if not n:
        return None, f"a {what}, like 'Chase Freedom' or 'Gas card'"
    if M.cardlike(n):
        return None, f"{what} only: no card number and no last 4 digits (they are never kept)"
    return n, ""


def yesno(v):
    if isinstance(v, bool):
        return v
    s = str(v if v is not None else "").strip().lower()
    if s in ("y", "yes", "true", "1", "on"):
        return True
    if s in ("n", "no", "false", "0", "off"):
        return False
    return None


def _ranged(d, key, lo, hi, required=False, whole=False):
    raw = d.get(key)
    if raw is None or (isinstance(raw, str) and raw.strip() == ""):
        return (None, f"{key.replace('_', ' ')} is needed") if required else (None, "")
    v = M.num(raw)
    if v is None or v < lo or v > hi:
        return None, f"{key.replace('_', ' ')}: a number from {lo:g} to {hi:g}"
    return (int(round(v)) if whole else round(v, 2)), ""


def validate(d: dict, today: str):
    """-> (card, '') or (None, why). Strict: known keys only, the nickname rule, numbers in range."""
    d = M.obj(d)
    bad = [k for k in d if k not in KEYS and k != "id"]
    if bad:
        return None, "unknown field: " + ", ".join(sorted(bad))
    nick, why = clean_name(d.get("nick"))
    if not nick:
        return None, why
    out = {"id": hashlib.sha1(nick.lower().encode("utf-8")).hexdigest()[:8], "nick": nick}
    for key, lo, hi, req, whole in (("limit", 1, 1_000_000, True, False), ("balance", -100_000, 1_000_000, False, False),
                                    ("statement_day", 1, 31, False, True), ("due_day", 1, 31, True, True), ("apr", 0, 80, False, False)):
        v, why = _ranged(d, key, lo, hi, req, whole)
        if why:
            return None, why
        out[key] = v
    ap = yesno(d.get("autopay"))
    if d.get("autopay") not in (None, "") and ap is None:
        return None, "autopay: yes or no"
    out["autopay"] = bool(ap)
    if d.get("match") not in (None, ""):
        m, why = clean_name(d.get("match"), "match name")
        if not m:
            return None, why
        out["match"] = m
    else:
        out["match"] = None
    bd = M.parse_day(d.get("balance_day")) if d.get("balance_day") else None
    out["balance_day"] = bd.isoformat() if bd else (today if out["balance"] is not None else None)
    return out, ""


# ------------------------------------------------------------------------------------------------ the private file
def load(env=None) -> dict:
    doc = M.read_json(path(env), None)
    doc = doc if isinstance(doc, dict) else {}
    cards = [c for c in M.arr(doc.get("cards")) if isinstance(c, dict) and c.get("nick") and not M.cardlike(c.get("nick"))]
    return {"v": 1, "kind": "olympus-me-cards", "cards": cards, "updated": doc.get("updated")}


def save(doc: dict, env=None, now_s: float | None = None) -> str:
    now_s = time.time() if now_s is None else now_s
    if M.olympus_dir(env).startswith(os.path.realpath(ROOT) + os.sep):
        raise RuntimeError("the private folder must be outside the bot folder")
    doc = {"v": 1, "kind": "olympus-me-cards", "updated": M.ny_day(now_s), "t": int(now_s),
           "about": "Your cards for the Me hub: nicknames only, never a card number. Private: this file never leaves the PC.",
           "cards": [c for c in M.arr(doc.get("cards")) if not M.cardlike(c.get("nick"))]}
    return M.write_json(path(env), doc)


def upsert(doc: dict, card: dict) -> dict:
    cards = [c for c in M.arr(doc.get("cards")) if str(c.get("nick", "")).lower() != card["nick"].lower()]
    cards.append(card)
    cards.sort(key=lambda c: str(c.get("nick", "")).lower())
    return {**doc, "cards": cards}


def find(doc: dict, nick: str):
    n = str(nick or "").strip().lower()
    for c in M.arr(doc.get("cards")):
        if str(c.get("nick", "")).lower() == n or c.get("id") == n:
            return c
    return None


# ------------------------------------------------------------------------------------------------ the math
def debts_of(accounts) -> list:
    """the debt balances of the bank import: [{name, usd, updated}] (household.json networth.accounts or balances.json accounts)"""
    out = []
    for a in M.arr(accounts):
        if isinstance(a, dict) and str(a.get("kind") or "").lower() == "debt" and M.num(a.get("usd")) is not None:
            out.append({"name": M.clean(a.get("name"), 40), "usd": abs(M.num(a["usd"])), "updated": str(a.get("updated") or "")[:10]})
    return out


def match_balance(card: dict, debts: list):
    """the import's balance for this card: the same name, or the card's match name (whole name or inside it, any case)"""
    keys = [k.lower() for k in (card.get("match"), card.get("nick")) if k]
    for k in keys:
        for d in debts:
            n = d["name"].lower()
            if n and (n == k or k in n or n in k):
                return d
    return None


def util_level(u):
    if u is None:
        return "", ""
    if u < UTIL_BEST:
        return "ok", "under 10%: best"
    if u < UTIL_FINE:
        return "ok", "under 30%: fine"
    if u < UTIL_HIGH:
        return "warn", "over 30%: high"
    return "bad", "over 50%: very high"


def interest_month(balance, apr) -> float:
    b, a = M.num(balance), M.num(apr)
    if not b or not a or b <= 0:
        return 0.0
    return round(b * a / 100.0 / 365.0 * CYCLE_DAYS, 2)


def card_view(c: dict, today: str, debts=None) -> dict:
    m = match_balance(c, debts or [])
    if m:
        bal, src, bday = m["usd"], "your bank import", m["updated"] or None
    else:
        bal, src, bday = M.num(c.get("balance")), "typed", c.get("balance_day")
    limit = M.num(c.get("limit")) or 0.0
    u = round(max(0.0, bal) / limit * 100.0, 1) if (bal is not None and limit) else None
    lvl, words = util_level(u)
    due = M.next_on_day(today, int(c["due_day"])) if c.get("due_day") else None
    stmt = M.next_on_day(today, int(c["statement_day"])) if c.get("statement_day") else None
    im = interest_month(bal, c.get("apr"))
    to30 = round(max(0.0, (bal or 0) - UTIL_FINE / 100.0 * limit), 2) if bal is not None else None
    to10 = round(max(0.0, (bal or 0) - UTIL_BEST / 100.0 * limit), 2) if bal is not None else None
    return {"id": c.get("id"), "nick": c.get("nick"), "limit": limit, "balance": bal, "balance_src": src, "balance_day": bday,
            "util": u, "lvl": lvl, "words": words, "due": due, "due_in": M.days_between(today, due) if due else None,
            "statement": stmt, "statement_in": M.days_between(today, stmt) if stmt else None, "apr": M.num(c.get("apr")),
            "autopay": bool(c.get("autopay")), "interest_month": im, "interest_year": round(im * 12, 2), "pay_to_30": to30, "pay_to_10": to10}


def summary(doc: dict, today: str, accounts=None) -> dict:
    debts = debts_of(accounts)
    views = [card_view(c, today, debts) for c in M.arr(doc.get("cards"))]
    known = [v for v in views if v["balance"] is not None]
    tb = round(sum(max(0.0, v["balance"]) for v in known), 2)
    tl = round(sum(v["limit"] for v in known), 2)
    u = round(tb / tl * 100.0, 1) if tl else None
    lvl, words = util_level(u)
    dues = sorted([v for v in views if v["due"]], key=lambda v: (v["due"], v["nick"].lower()))
    return {"cards": views, "n": len(views), "balance": tb, "limit": tl, "util": u, "lvl": lvl, "words": words,
            "missing_balance": [v["nick"] for v in views if v["balance"] is None],
            "next_due": dues[0] if dues else None, "interest_month": round(sum(v["interest_month"] for v in views), 2)}


GUIDE = ("Under 30% is fine, under 10% is best for your credit score. A card reports its STATEMENT balance, so paying before the "
         "statement date lowers the use it reports.")


def section(doc: dict, today: str, accounts=None, t=None) -> dict:
    """the Me hub's Cards section (me.json): a short card stack"""
    S = summary(doc, today, accounts)
    base = {"id": "cards", "title": "Cards", "connect": CONNECT, "src": {"name": "Your cards file (PC)", "t": t, "note": "nicknames only"}}
    if not S["n"]:
        return {**base, "state": "empty", "line": "No cards yet", "cards": [], "summary": S}
    rows = []
    for v in S["cards"]:
        rows.append({"k": v["nick"], "v": M.pct(v["util"]) if v["util"] is not None else "no balance",
                     "s": (f"{M.money(v['balance'])} of {M.money(v['limit'])}" + (" (from your bank import)" if v["balance_src"] == "your bank import" else "")
                           if v["balance"] is not None else f"limit {M.money(v['limit'])}: type its balance (--set)"),
                     "pct": min(100.0, v["util"]) if v["util"] is not None else None, "lvl": v["lvl"]})
    total = {"id": "use", "title": "All cards used", "value": M.pct(S["util"]) if S["util"] is not None else "-",
             "sub": (f"{M.money(S['balance'])} of {M.money(S['limit'])} · {S['words']}" if S["util"] is not None else "no balances yet"),
             "lvl": S["lvl"], "pct": min(100.0, S["util"]) if S["util"] is not None else None, "rows": rows, "note": GUIDE}
    nd = S["next_due"]
    due_rows = [{"k": v["nick"], "v": M.short_day(v["due"]), "s": M.in_days(v["due_in"]) + (" · autopay on" if v["autopay"] else " · autopay off")
                 + (f" · statement {M.short_day(v['statement'])}" if v["statement"] else ""),
                 "lvl": "warn" if v["due_in"] is not None and v["due_in"] <= 5 and not v["autopay"] else ""}
                for v in sorted([v for v in S["cards"] if v["due"]], key=lambda v: v["due"])]
    due = {"id": "due", "title": "Next due", "value": M.short_day(nd["due"]) if nd else "-",
           "sub": (f"{nd['nick']} · {M.in_days(nd['due_in'])}" + (" · autopay on" if nd["autopay"] else " · autopay off")) if nd else "",
           "lvl": "warn" if nd and nd["due_in"] <= 5 and not nd["autopay"] else "", "rows": due_rows,
           "note": "Your phone gets a reminder 5 days and 1 day before each due date (nickname and date only)."}
    tips = []
    for v in S["cards"]:
        if v["statement"] and v["pay_to_30"]:
            tips.append({"k": v["nick"], "v": M.money(v["pay_to_30"]), "s": f"paid before {M.short_day(v['statement'])} reports under 30%", "lvl": "warn"})
    irows = [{"k": v["nick"], "v": f"{M.money(v['interest_month'])} a month", "s": f"{v['apr']:g}% APR on {M.money(v['balance'])}" if v["apr"] is not None and v["balance"] is not None else "add the APR (--set ... apr=24.99)"}
             for v in S["cards"]]
    inter = {"id": "interest", "title": "Interest if carried", "value": f"{M.money(S['interest_month'])} a month",
             "sub": f"about {M.money(S['interest_month'] * 12)} a year if these balances stay; $0 when paid in full by the due date",
             "lvl": "warn" if S["interest_month"] >= 25 else "", "rows": irows + tips, "note": "An estimate: APR / 365 x 30 days on today's balance."}
    stale = [v for v in S["cards"] if v["balance_src"] == "typed" and v["balance_day"] and M.days_between(v["balance_day"], today) > 35]
    line = f"{plural_cards(S['n'])} · {M.pct(S['util'])} used" + (f" · next due {M.short_day(nd['due'])}" if nd else "")
    if S["missing_balance"]:
        line += f" · {len(S['missing_balance'])} without a balance"
    return {**base, "state": "stale" if stale else "ok", "line": line, "cards": [total, due, inter], "summary": S,
            "stale_note": (f"Typed balances older than 35 days: {', '.join(v['nick'] for v in stale)}. Update them with --set." if stale else "")}


def plural_cards(n: int) -> str:
    return M.plural(n, "card")


def reminders(doc: dict, today: str) -> list:
    """the pushes due now: [{key, also, title, body}] 5 days and 1 day before each due date (a missed one comes once, later)"""
    out = []
    for c in M.arr(doc.get("cards")):
        if not c.get("due_day"):
            continue
        due = M.next_on_day(today, int(c["due_day"]))
        n = M.days_between(today, due)
        if n > max(REMIND_DAYS) or n < 0:
            continue
        slot = min(o for o in REMIND_DAYS if n <= o)
        ap = "Autopay is on." if c.get("autopay") else "Autopay is off: pay it yourself."
        out.append({"key": f"card:{c.get('id')}:{due}:{slot}", "also": [f"card:{c.get('id')}:{due}:{o}" for o in REMIND_DAYS if o > slot],
                    "title": f"Card due {M.in_days(n)}", "body": f"{c.get('nick')} is due {M.short_day(due)} ({M.in_days(n)}). {ap}",
                    "priority": "default" if c.get("autopay") else "high", "tags": "credit_card"})
    return out


# ------------------------------------------------------------------------------------------------ the CLI
def table(S: dict) -> str:
    if not S["n"]:
        return "  No cards yet. Add one: python tools\\me_cards.py --add"
    lines = [f"  {'card':<22} {'balance':>10} {'limit':>10} {'use':>6}  {'due':<14} {'interest/mo':>11}"]
    for v in S["cards"]:
        lines.append(f"  {v['nick'][:22]:<22} {M.money(v['balance']):>10} {M.money(v['limit']):>10} {M.pct(v['util']):>6}  "
                     f"{(M.short_day(v['due']) + ' ' + ('A' if v['autopay'] else '')).strip():<14} {M.money(v['interest_month']):>11}")
    lines.append(f"  {'all cards':<22} {M.money(S['balance']):>10} {M.money(S['limit']):>10} {M.pct(S['util']):>6}  ({S['words']})")
    lines.append("  " + GUIDE)
    return "\n".join(lines)


def field_why(key: str, v, today: str) -> str:
    """'' when this one answer is good (the other fields are filled with good values to check it alone), else why not"""
    d = {"nick": "Card", "limit": 1, "due_day": 1, "autopay": "n", key: v}
    if key == "autopay" and yesno(v) is None:
        return "autopay: yes or no"
    card, why = validate(d, today)
    return "" if card else why


def ask_card(ask=input, say=print, today: str = "") -> dict | None:
    """one card, question by question (Enter on the nickname stops)"""
    while True:
        nick = ask("  Nickname (no card number, no last 4; Enter = done), e.g. Chase Freedom: ").strip()
        if not nick:
            return None
        n, why = clean_name(nick)
        if n:
            break
        say("  " + why)
    today = today or M.ny_day(time.time())
    d = {"nick": n}
    for key, q in (("limit", "Credit limit in $"), ("balance", "Balance now in $ (Enter = from your bank import, same name)"),
                   ("statement_day", "Statement closing day of the month (1-31, Enter = skip)"), ("due_day", "Payment due day of the month (1-31)"),
                   ("apr", "APR in % (Enter = skip)"), ("autopay", "Autopay on? (y / n)")):
        while True:
            v = ask(f"  {q}: ").strip()
            why = field_why(key, v, today)
            if not why:
                d[key] = v
                break
            say("  " + why)
    card, why = validate(d, today)
    if not card:
        say("  not saved: " + why)
        return None
    return card


def main(argv=None, env=None, ask=input, say=print, now_s: float | None = None) -> int:
    ap = argparse.ArgumentParser(description="Your credit cards for the Me hub (nicknames only, private, on this PC).")
    ap.add_argument("--add", action="store_true")
    ap.add_argument("--nick")
    ap.add_argument("--limit")
    ap.add_argument("--balance")
    ap.add_argument("--statement-day")
    ap.add_argument("--due-day")
    ap.add_argument("--apr")
    ap.add_argument("--autopay")
    ap.add_argument("--match", help="the name of this card's balance in your bank import's balances.json")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--set", nargs="+", metavar=("NICK", "KEY=VALUE"))
    ap.add_argument("--remove")
    a = ap.parse_args(argv)
    now_s = time.time() if now_s is None else now_s
    today = M.ny_day(now_s)
    doc = load(env)
    if a.add:
        if a.nick:
            card, why = validate({"nick": a.nick, "limit": a.limit, "balance": a.balance, "statement_day": a.statement_day, "due_day": a.due_day,
                                  "apr": a.apr, "autopay": a.autopay, "match": a.match}, today)
            if not card:
                say(f"  [FIX] not saved: {why}")
                return 2
            cards = [card]
        else:
            say("  Your cards for the Me hub. Nicknames only: the card number and its last 4 are never asked and never kept.")
            cards = []
            while True:
                c = ask_card(ask, say, today)
                if not c:
                    break
                cards.append(c)
                say(f"  [OK]  {c['nick']} added.")
        for c in cards:
            doc = upsert(doc, c)
        if cards:
            p = save(doc, env, now_s)
            say(f"  [OK]  saved {len(cards)} card(s) in {p} (private, outside the bot folder)")
    elif a.set:
        c = find(doc, a.set[0])
        if not c:
            say(f"  [FIX] no card called {a.set[0]!r} (--list shows them)")
            return 2
        d = {k: v for k, v in c.items() if k in KEYS}
        for kv in a.set[1:]:
            if "=" not in kv:
                say(f"  [FIX] {kv!r}: use key=value (balance, limit, due_day, statement_day, apr, autopay, match)")
                return 2
            k, v = kv.split("=", 1)
            k = k.strip().lower().replace("-", "_")
            d[k] = v.strip()
            if k == "balance":
                d["balance_day"] = today
        card, why = validate(d, today)
        if not card:
            say(f"  [FIX] not saved: {why}")
            return 2
        doc = upsert({**doc, "cards": [x for x in doc["cards"] if x is not c]}, card)
        save(doc, env, now_s)
        say(f"  [OK]  {card['nick']} updated")
    elif a.remove:
        c = find(doc, a.remove)
        if not c:
            say(f"  [FIX] no card called {a.remove!r}")
            return 2
        save({**doc, "cards": [x for x in doc["cards"] if x is not c]}, env, now_s)
        say(f"  [OK]  {c['nick']} removed")
    bal = M.read_json(balances_path(env), {}) or {}
    say(table(summary(load(env), today, M.obj(bal).get("accounts"))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
