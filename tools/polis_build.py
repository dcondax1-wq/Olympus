#!/usr/bin/env python3
"""POLIS life builder (OLYMPUS, docs/POLIS_25.md section B, items 11-18): the civic life of the city-state, written only from files
OLYMPUS already publishes. READ ONLY, OFFLINE, stdlib only. Paper only: nothing here is an order and nothing is sent anywhere.

    python tools/polis_build.py                     # tools/web_public -> tools/web_public/olympus/polis.json (+ the labelled demo olympus/polis-demo.json)
    python tools/polis_build.py --date 2026-11-11   # a given day (default: today, UTC; the clock is used for nothing else)
    python tools/polis_build.py --web site          # read the BUILT site (data.json, home.json, money/*.json are there) and write site/olympus/polis.json
    python tools/polis_build.py --check             # exit 1 when polis.json (and the demo) is not what this script writes now for its date
    python tools/polis_build.py --selftest

polis.json (the renderer is tools/web_public/olympus/polis-life.js):
  herald     11  short lines a herald cries: eval passed, trade closed (+$ with its R), Kalshi paper fill, money estimate, festival near, torch
  oracle     12  the morning game plan as a Delphi reading: a verse, the plain words under it, and the facts (each with its file)
  festivals  13  FOMC = Panathenaia, CPI = Dionysia, NFP = Thesmophoria, roll week = Synoikia, with days left (pythia/events.json,
                 else a small BUILT-IN table of known dates that says so)
  torch      14  green weeks in a row and rule-kept days in a row (the rules of tools/hermes/wrapped.discipline, as ARENA checks them)
  grove      15  one olive tree per account; growth from the eval progress (a funded account is a full tree), rings and olives by a stated rule
  amphorae   16  one painted amphora per closed trade (long = rising horse, short = diving dolphin; win / loss / flat), shelved by month
  statues    17  the best winning trades and every eval pass / payout, with a carved plaque (date, $, R)
  stoic      18  one short public-domain line (Marcus Aurelius, Epictetus, Seneca, old translations) picked by the day's state

THE RULE: no invented numbers. Every number printed in a herald line, the oracle or a plaque is a value read from a named file (or a count
/ sum of them, said so). audit() checks it. Missing files give empty but valid parts (each listed under sources.missing).
Same files + same date = the same polis.json, byte for byte ("built" is the newest time found in the sources, never the clock).
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tools.arena import events as AE  # noqa: E402  (same discipline rules as ARENA / HERMES)
from tools.hermes import wrapped as W  # noqa: E402

WEB = os.path.join(ROOT, "tools", "web_public")
OUT_REL = os.path.join("olympus", "polis.json")
DEMO_REL = os.path.join("olympus", "polis-demo.json")
VERSION = 1
NUM_RE = re.compile(r"\d+(?:,\d{3})*(?:\.\d+)?")
FLAT_USD = 5.0                 # |$| under this is a scratch (breakeven): a pale amphora, neither win nor loss
RING_USD = 500.0               # one growth ring per $500 of profit on the account
MAX_AMPHORAE, MAX_STATUES, MAX_HERALD, MAX_FEST = 240, 7, 8, 10
FEST_DAYS = 120                # festivals shown up to this many days ahead

FESTIVALS = {
    "fomc": {"festival": "Panathenaia", "god": "Athena", "glyph": "owl", "event": "FOMC rate decision",
             "meaning": "The city's greatest feast, for Athena. The Fed sets the price of money."},
    "cpi": {"festival": "Dionysia", "god": "Dionysus", "glyph": "kantharos", "event": "CPI inflation report",
            "meaning": "The wine feast of Dionysus. Prices speak and the market can lose its head."},
    "nfp": {"festival": "Thesmophoria", "god": "Demeter", "glyph": "wheat", "event": "Jobs report (NFP)",
            "meaning": "Demeter's harvest feast. The jobs count shows how the fields of work are growing."},
    "roll": {"festival": "Synoikia", "god": "Athena Polias", "glyph": "walls", "event": "Contract roll week",
             "meaning": "The feast of the joining of the city. The bot moves to the next NQ contract."},
}

# A small BUILT-IN table, used only when pythia/events.json is missing. Copied on 2026-11-11 from data/news/events.csv (federalreserve.gov,
# bls.gov) and pythia/events.json (roll dates: docs/ROLL_DEC_2026.md). Labelled as built-in on the page; confirm on the official page.
BUILTIN_EVENTS = (
    [(d, "14:00", "fomc") for d in ("2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17", "2026-07-29", "2026-09-16", "2026-10-28",
                                    "2026-12-09", "2027-01-27", "2027-03-17")]
    + [(d, "08:30", "cpi") for d in ("2026-01-13", "2026-02-13", "2026-03-11", "2026-04-10", "2026-05-12", "2026-06-10", "2026-07-14",
                                     "2026-08-12", "2026-09-11", "2026-11-10")]
    + [(d, "08:30", "nfp") for d in ("2026-01-09", "2026-02-11", "2026-03-06", "2026-04-03", "2026-05-08", "2026-06-05", "2026-07-02",
                                     "2026-08-07", "2026-09-04", "2026-10-02", "2026-11-06", "2026-12-04", "2027-02-05", "2027-03-05")]
    + [("2026-12-10", "00:00", "roll"), ("2027-03-11", "00:00", "roll")])
BUILTIN_LABEL = "Built-in table of known dates (copied 2026-11-11 from the saved calendar). The published calendar was missing. Confirm on the official page."

# Public-domain translations only: Marcus Aurelius, Meditations (George Long, 1862); Epictetus, Enchiridion (T. W. Higginson, 1865) and
# Discourses (George Long, 1877); Seneca, Moral Letters to Lucilius (R. M. Gummere, 1917-25). Short lines, picked by the day's mood.
STOIC = {
    "loss": [
        ("If thou art pained by any external thing, it is not this thing that disturbs thee, but thy own judgement about it.", "Marcus Aurelius", "Meditations VIII.47", "George Long"),
        ("Be like the promontory against which the waves continually break, but it stands firm and tames the fury of the water around it.", "Marcus Aurelius", "Meditations IV.49", "George Long"),
        ("Never say of anything, \"I have lost it\"; but, \"I have returned it.\"", "Epictetus", "Enchiridion 11", "T. W. Higginson"),
        ("How much more grievous are the consequences of anger than the causes of it.", "Marcus Aurelius", "Meditations XI.18", "George Long"),
    ],
    "win": [
        ("It is not the man who has too little, but the man who craves more, that is poor.", "Seneca", "Moral Letters 2", "R. M. Gummere"),
        ("Remember that you must behave in life as at a dinner party. Is anything brought around to you? Put out your hand and take your share with moderation.", "Epictetus", "Enchiridion 15", "T. W. Higginson"),
        ("Occupy thyself with few things, says the philosopher, if thou wouldst be tranquil.", "Marcus Aurelius", "Meditations IV.24", "George Long"),
    ],
    "discipline": [
        ("No longer talk at all about the kind of man that a good man ought to be, but be such.", "Marcus Aurelius", "Meditations X.16", "George Long"),
        ("Such as are thy habitual thoughts, such also will be the character of thy mind; for the soul is dyed by the thoughts.", "Marcus Aurelius", "Meditations V.16", "George Long"),
        ("Some things are in our control and others not.", "Epictetus", "Enchiridion 1", "T. W. Higginson"),
    ],
    "storm": [
        ("We are more often frightened than hurt; and we suffer more from imagination than from reality.", "Seneca", "Moral Letters 13", "R. M. Gummere"),
        ("Men are disturbed not by things, but by the principles and notions which they form concerning things.", "Epictetus", "Enchiridion 5", "T. W. Higginson"),
        ("When a man does not know what harbour he is making for, no wind is the right wind.", "Seneca", "Moral Letters 71", "R. M. Gummere"),
    ],
    "steady": [
        ("No great thing is produced suddenly, since not even the grape or the fig is.", "Epictetus", "Discourses I.15", "George Long"),
        ("Look within. Within is the fountain of good, and it will ever bubble up, if thou wilt ever dig.", "Marcus Aurelius", "Meditations VII.59", "George Long"),
    ],
    "quiet": [
        ("Hold every hour in your grasp. Lay hold of to-day's task, and you will not need to depend so much upon to-morrow's.", "Seneca", "Moral Letters 1", "R. M. Gummere"),
        ("Everywhere means nowhere.", "Seneca", "Moral Letters 2", "R. M. Gummere"),
        ("Don't demand that things happen as you wish, but wish that they happen as they do happen, and you will go on well.", "Epictetus", "Enchiridion 8", "T. W. Higginson"),
    ],
}
MOOD_WHY = {"loss": "The last closed trade was a loss: a line on patience.", "win": "The last closed trade was a win: a line on not getting greedy.",
            "discipline": "A rule was broken on the last trading day: a line on keeping the rules.",
            "storm": "A big release is today or tomorrow: a line on staying calm.", "steady": "The torch is burning: a line on steady work.",
            "quiet": "A quiet day with no fresh trade: a line on today's task."}


# ------------------------------------------------------------------------------------------------ small helpers
def read_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError, UnicodeDecodeError):
        return None


def is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v == v and abs(v) != float("inf")


def usd(v, sign=True):
    """'+$1,912.50' / '-$240' / '$0' (never -$0): cents only when there are cents."""
    v = round(float(v), 2)
    a = abs(v)
    s = f"{a:,.0f}" if abs(a - round(a)) < 0.005 else f"{a:,.2f}"
    if s in ("0", "0.00"):
        return "$0"
    return ("-" if v < 0 else "+" if sign else "") + "$" + s


def rtxt(r):
    return ("+" if r > 0 else "") + f"{r:.1f}R" if abs(r) >= 0.05 else "0.0R"


def tokens(text):
    return {t.replace(",", "") for t in NUM_RE.findall(str(text))}


def audit(item, fields=("cry", "plain", "verse", "plaque", "title")):
    """The numbers printed in an item that are not among its facts (must be empty)."""
    allowed = set()
    for f in item.get("facts") or []:
        allowed |= tokens(f.get("t", ""))
    printed = set()
    for k in fields:
        printed |= tokens(item.get(k) or "")
    return sorted(printed - allowed)


def fact(t, src, at=None, how=None):
    f = {"t": str(t), "src": src}
    if at:
        f["at"] = at
    if how:
        f["how"] = how
    return f


def seed(*parts):
    return int(hashlib.sha256("|".join(str(p) for p in parts).encode()).hexdigest()[:8], 16)


def monday(day):
    d = dt.date.fromisoformat(day)
    return (d - dt.timedelta(days=d.weekday())).isoformat()


def month_label(ym):
    d = dt.date.fromisoformat(ym + "-01")
    return f"{d.strftime('%B')} {d.year}"


def day_words(day):
    d = dt.date.fromisoformat(day)
    return f"{d.strftime('%a')} {d.day} {d.strftime('%b')}"


def stamp(v):
    """A sortable ISO-ish time from a value in the sources (unix seconds or an ISO string), else None."""
    if is_num(v) and v > 1e9:
        return dt.datetime.fromtimestamp(int(v), dt.timezone.utc).isoformat(timespec="seconds")
    if isinstance(v, str) and re.match(r"^\d{4}-\d\d-\d\d", v):
        return v[:25]
    return None


# ------------------------------------------------------------------------------------------------ the sources
class Sources:
    """Everything the polis may read, loaded once, each file cited by its path in the site folder."""

    FILES = ("data.json", "home.json", "pythia/events.json", "kalshicity/ledger.json", "money/index.json", "olympus/people.json")

    def __init__(self, web):
        self.web, self.read, self.missing, self.docs = web, [], [], {}
        for rel in self.FILES:
            d = read_json(os.path.join(web, *rel.split("/")))
            self.docs[rel] = d if isinstance(d, (dict, list)) else None
            (self.read if self.docs[rel] is not None else self.missing).append(rel)
        self.data, self.home = self.docs["data.json"] or {}, self.docs["home.json"] or {}

    def newest(self):
        c = []
        for d in (self.data, self.home):
            c.append(stamp((d or {}).get("built")))
        ev = self.docs["pythia/events.json"] or {}
        c += [stamp(ev.get("updated")), stamp(ev.get("generated"))]
        led = self.docs["kalshicity/ledger.json"] or {}
        c += [stamp(t.get("t")) for t in (led.get("trades") or []) if isinstance(t, dict)]
        c.append(stamp((self.docs["money/index.json"] or {}).get("asof")))
        c.append(stamp((self.docs["olympus/people.json"] or {}).get("asof")))
        c = [x for x in c if x]
        return max(c) if c else None

    def person(self, pid):
        for p in ((self.docs["olympus/people.json"] or {}).get("people") or []) + ((self.docs["olympus/people.json"] or {}).get("villagers") or []):
            if isinstance(p, dict) and p.get("id") == pid and p.get("name"):
                return {"id": pid, "name": str(p["name"])[:40]}
        return None


def board_trades(doc):
    """The live board's trade log (data.json / home.json "board") in the shape tools/hermes/wrapped.collect writes."""
    out = []
    names = {"lit": "Zlarior", "atlas": "ATLAS", "blitz": "BLITZ"}
    for t in ((doc or {}).get("board") or {}).get("trades") or []:
        if not isinstance(t, dict) or t.get("open") or not is_num(t.get("usd")):
            continue
        day = W._day(t.get("day")) or (W.trading_day(t["entry_t"]) if is_num(t.get("entry_t")) else None)
        if not day:
            continue
        acct = str(t.get("acct") or "lit")
        out.append({**t, "pnl": round(float(t["usd"]), 2), "day": day, "bot": names.get(acct, acct.upper()), "account": names.get(acct, acct),
                    "account_id": acct, "paper": t.get("src") == "paper", "orders": []})
    out.sort(key=lambda x: (x["day"], W._num(x.get("entry_t")) or 0, x["account_id"]))
    return out


def closed_trades(S):
    """(trades, the file they came from): data.json accounts (the paper twin only when the PC has none), else the board's log."""
    tr, _paper, _only = W.counted(S.data)
    if tr:
        return tr, "data.json"
    for rel, doc in (("data.json", S.data), ("home.json", S.home)):
        b = board_trades(doc)
        if b:
            return b, rel
    return [], None


def accounts(S):
    for rel, doc in (("data.json", S.data), ("home.json", S.home)):
        A = [a for a in (doc or {}).get("accounts") or [] if isinstance(a, dict) and not a.get("error") and a.get("id")]
        if A:
            return A, rel
    return [], None


# ------------------------------------------------------------------------------------------------ 14. torch relay
def torch(trades, src, today):
    tev, clean = AE.trade_events(trades) if trades else ([], {})
    broke = {}
    for e in tev:
        if e["kind"] == "rule_broken":
            broke.setdefault(e["day"], []).append(e["note"].split(": broke ", 1)[-1])
    days = {}
    for t in trades:
        days.setdefault(t["day"], []).append(t)
    drows = []
    for d in sorted(days):
        rules = sorted(set(r for x in broke.get(d, []) for r in x.split(", ")))
        drows.append({"day": d, "trades": len(days[d]), "kept": not rules, "broke": rules})
    weeks = {}
    for t in trades:
        weeks.setdefault(monday(t["day"]), []).append(t)
    wrows, current = [], None
    for mon in sorted(weeks):
        T = weeks[mon]
        fri = (dt.date.fromisoformat(mon) + dt.timedelta(days=4)).isoformat()
        net = round(sum(t["pnl"] for t in T), 2)
        ok = all(clean.get(f"trade:{t['account_id']}:{int(W._num(t.get('entry_t')) or 0)}:{t['day']}") for t in T)
        row = {"week": mon, "net": net, "trades": len(T), "clean": ok, "green": ok and net > 0}
        if today <= fri:
            current = {**row, "green": None}
        else:
            wrows.append(row)

    def runs(rows, key):
        cur = best = run = 0
        for r in rows:
            run = run + 1 if r[key] else 0
            best = max(best, run)
        for r in reversed(rows):
            if not r[key]:
                break
            cur += 1
        return cur, best
    wc, wb = runs(wrows, "green")
    dc, db = runs(drows, "kept")
    flame = "unlit" if not wrows and not drows else ("lit" if (wc or dc) else "out")
    return {"weeks": {"streak": wc, "best": wb, "rows": wrows[-12:], "current": current},
            "days": {"streak": dc, "best": db, "rows": drows[-20:]},
            "flame": flame, "src": src,
            "rule": "A runner takes the torch for every finished week that closed green with every trade inside the rules (weeks without a trade are skipped), "
                    "and for every trading day where each trade kept the rules (1 trade a day, stop beyond the sweep, entries 02:00-15:30, flat by 15:55, hands off). "
                    "One break puts the flame out."}


# ------------------------------------------------------------------------------------------------ 15. olive grove
def grove(A, src, trades):
    wins = {}
    for t in trades:
        if t["pnl"] > FLAT_USD:
            wins[t["account_id"]] = wins.get(t["account_id"], 0) + 1
    out = []
    for a in A:
        aid, name = str(a["id"]), str(a.get("name") or a["id"])[:40]
        ev = a.get("eval") if isinstance(a.get("eval"), dict) else {}
        fu = a.get("funded") if isinstance(a.get("funded"), dict) else None
        status = str(ev.get("status") or "").lower()
        paper = aid in W.PAPER_IDS or a.get("kind") == "paper"
        funded = (fu is not None or a.get("kind") == "funded" or status in AE.PASSED) and not paper
        bal, start = W._num(ev.get("balance")), W._num(ev.get("start_balance"))
        profit = W._num(ev.get("profit"))
        if profit is None and bal is not None and start is not None:
            profit = round(bal - start, 2)
        target = None
        if W._num(ev.get("target_balance")) is not None and start is not None:
            target = round(W._num(ev["target_balance"]) - start, 2)
        prog = W._num(ev.get("progress"))
        if prog is None and profit is not None and target:
            prog = profit / target
        prog = max(0.0, min(1.0, prog or 0.0))
        growth = 1.0 if funded else round(max(0.12, prog), 4)
        facts = []
        if bal is not None:
            facts.append(fact(usd(bal, False), src, f"accounts/{aid}/eval/balance"))
        if profit is not None:
            facts.append(fact(usd(profit), src, f"accounts/{aid}/eval/profit"))
        if target:
            facts.append(fact(usd(target, False), src, f"accounts/{aid}/eval/target_balance - start_balance", "target minus start"))
        room, mll = W._num(ev.get("room")), W._num(ev.get("mll"))
        if room is not None and mll is not None:
            facts.append(fact(f"Drawdown left {usd(room, False)} of {usd(mll, False)} max loss", src, f"accounts/{aid}/eval/room, mll"))
        stage = "paper" if paper else "funded" if funded else "eval"
        line = {"paper": "A paper sapling: the cloud's twin, not real money.", "funded": "Funded: a full tree.",
                "eval": f"Eval {round(prog * 100)}% of the way to the target." if target else "Eval: growing."}[stage]
        if stage == "eval" and profit is not None and profit < 0:
            line = f"Below its start by {usd(-profit, False)}: a thirsty tree."
            facts.append(fact(usd(-profit, False), src, f"accounts/{aid}/eval/profit", "minus the profit"))
        elif stage == "eval" and target:
            facts.append(fact(f"{round(prog * 100)}%", src, f"accounts/{aid}/eval/progress", "profit / target, 0 to 100"))
        out.append({"id": aid, "name": name, "stage": stage, "bot": W.bot_name(a), "balance": bal, "profit": profit, "target": target,
                    "progress": round(prog, 4), "growth": growth, "rings": int(max(0.0, profit or 0.0) // RING_USD) if profit is not None else 0,
                    "olives": min(60, wins.get(aid, 0)), "thirsty": bool(profit is not None and profit < 0), "room": room, "mll": mll,
                    "payouts": round(sum(float(v) for v in ((fu or {}).get("payouts") or {}).values() if is_num(v)), 2) if fu else None,
                    "line": line, "facts": facts})
    return {"src": src, "trees": out,
            "rule": f"One olive tree per account. It grows with the eval's progress to the target (a funded account is a full tree), one ring per "
                    f"{usd(RING_USD, False)} of profit, one olive per winning trade. A tree below its start balance looks thirsty."}


# ------------------------------------------------------------------------------------------------ 16. amphorae
def amphorae(trades, src):
    items = []
    for t in trades[-MAX_AMPHORAE:]:
        side = "LONG" if str(t.get("side") or "LONG").upper().startswith(("L", "B")) else "SHORT"
        r = W._num(t.get("r"))
        res = "flat" if abs(t["pnl"]) < FLAT_USD else ("win" if t["pnl"] > 0 else "loss")
        items.append({"id": f"{t['account_id']}:{int(W._num(t.get('entry_t')) or 0)}:{t['day']}", "day": t["day"], "bot": t["bot"],
                      "side": side, "scene": "horse" if side == "LONG" else "dolphin", "result": res, "usd": t["pnl"],
                      "r": None if r is None else round(r, 2), "exit": (str(t.get("exit") or "")[:20] or None), "paper": bool(t.get("paper")),
                      "label": usd(t["pnl"]) + ("" if r is None else f" ({rtxt(r)})")})
    shelves = {}
    for it in items:
        shelves.setdefault(it["day"][:7], []).append(it)
    rows = [{"month": m, "label": month_label(m), "n": len(v), "net": round(sum(x["usd"] for x in v), 2),
             "wins": sum(1 for x in v if x["result"] == "win"), "losses": sum(1 for x in v if x["result"] == "loss"), "items": v}
            for m, v in sorted(shelves.items(), reverse=True)]
    return {"src": src, "n": len(items), "shelves": rows,
            "rule": "One amphora per closed trade. Long = a horse rising, short = a dolphin diving. Bright clay = win, dark clay = loss, "
                    f"pale clay = a scratch (under {usd(FLAT_USD, False)} either way)."}


# ------------------------------------------------------------------------------------------------ 17. statues
def statues(trades, src, A, asrc):
    out = []
    for a in A:
        aid, name = str(a["id"]), str(a.get("name") or a["id"])[:40]
        if aid in W.PAPER_IDS or a.get("kind") == "paper":
            continue
        ev = a.get("eval") if isinstance(a.get("eval"), dict) else {}
        fu = a.get("funded") if isinstance(a.get("funded"), dict) else None
        if fu is not None or a.get("kind") == "funded" or str(ev.get("status") or "").lower() in AE.PASSED:
            day = W._day((fu or {}).get("start")) or W._day(ev.get("passed_day"))
            facts = [fact(name, asrc, f"accounts/{aid}/name")] + ([fact(day_words(day), asrc, f"accounts/{aid}/funded/start")] if day else [])
            out.append({"id": f"pass:{aid}", "kind": "pass", "figure": "nike", "title": f"{name}: eval passed", "day": day, "usd": None, "r": None,
                        "bot": W.bot_name(a), "plaque": (day_words(day) + " · eval passed") if day else "Eval passed", "facts": facts})
        pays = {d: float(v) for d, v in ((fu or {}).get("payouts") or {}).items() if W._day(d) and is_num(v) and v > 0}
        if pays:
            tot = round(sum(pays.values()), 2)
            last = max(pays)
            n = len(pays)
            out.append({"id": f"payout:{aid}", "kind": "payout", "figure": "nike", "title": f"{name}: {n} payout{'s' if n != 1 else ''}", "day": last,
                        "usd": tot, "r": None, "bot": W.bot_name(a), "plaque": f"{day_words(last)} · {usd(tot)} paid out",
                        "facts": [fact(name, asrc, f"accounts/{aid}/name"), fact(str(n), asrc, f"accounts/{aid}/funded/payouts", "count of payout days"),
                                  fact(usd(tot), asrc, f"accounts/{aid}/funded/payouts", "sum of the payouts"), fact(day_words(last), asrc, f"accounts/{aid}/funded/payouts")]})
    best = sorted([t for t in trades if t["pnl"] > FLAT_USD], key=lambda t: (-t["pnl"], t["day"]))[:MAX_STATUES - min(len(out), 3)]
    for i, t in enumerate(best):
        r = W._num(t.get("r"))
        side = "long" if str(t.get("side") or "LONG").upper().startswith(("L", "B")) else "short"
        txt = usd(t["pnl"]) + ("" if r is None else f" ({rtxt(r)})")
        out.append({"id": f"trade:{t['account_id']}:{int(W._num(t.get('entry_t')) or 0)}:{t['day']}", "kind": "trade", "figure": "athlete" if i else "victor",
                    "title": f"{t['bot']} {side}" + (" (paper)" if t.get("paper") else ""), "day": t["day"], "usd": t["pnl"], "r": None if r is None else round(r, 2),
                    "bot": t["bot"], "record": i == 0, "plaque": f"{day_words(t['day'])} · {txt}",
                    "facts": [fact(t["bot"], src, "trades/account"), fact(day_words(t["day"]), src, "trades/day"), fact(txt, src, "trades/pnl, r")]})
    return {"src": src or asrc, "items": out[:MAX_STATUES],
            "rule": "The best winning trades (biggest $ first; the first is the record) and every eval pass and payout stand in the hall."}


# ------------------------------------------------------------------------------------------------ 13. festivals
def festivals(S, today):
    ev = S.docs["pythia/events.json"]
    rows, label, src = [], None, "pythia/events.json"
    if isinstance(ev, dict) and isinstance(ev.get("events"), list):
        for e in ev["events"]:
            if isinstance(e, dict) and e.get("kind") in FESTIVALS and W._day(e.get("date")):
                rows.append((e["date"], e.get("time"), e["kind"], str(e.get("title") or "")[:90], bool(e.get("verify"))))
        label = "From the published calendar (pythia/events.json). Confirm times on the official page."
    else:
        src, label = "built-in", BUILTIN_LABEL
        rows = [(d, tm, k, FESTIVALS[k]["event"], True) for d, tm, k in BUILTIN_EVENTS]
    t0 = dt.date.fromisoformat(today)
    items, seen_roll = [], set()
    for d, tm, k, title, verify in sorted(rows):
        left = (dt.date.fromisoformat(d) - t0).days
        if left < 0 or left > FEST_DAYS:
            continue
        if k == "roll":                       # one Synoikia per roll week (the evening step + the switch are one festival)
            wk = monday(d)
            if wk in seen_roll:
                continue
            seen_roll.add(wk)
        m = FESTIVALS[k]
        items.append({"id": f"{k}:{d}", "kind": k, "festival": m["festival"], "god": m["god"], "glyph": m["glyph"], "meaning": m["meaning"],
                      "event": m["event"], "title": title or m["event"], "date": d, "date_words": day_words(d), "time": tm if tm and tm != "00:00" else None,
                      "days_left": left, "when": "today" if left == 0 else "tomorrow" if left == 1 else f"in {left} days", "verify": verify,
                      "week_of": monday(d) if k == "roll" else None})
    return {"src": src, "label": label, "items": items[:MAX_FEST], "builtin": src == "built-in"}


# ------------------------------------------------------------------------------------------------ 12. oracle
def oracle(S, today, fest):
    brief, bsrc = None, None
    for rel, doc in (("home.json", S.home), ("data.json", S.data)):
        b = ((doc or {}).get("live") or {}).get("brief")
        if isinstance(b, dict) and (b.get("plan") or b.get("day")):
            brief, bsrc = b, rel
            break
    mind = None
    for rel, doc in (("home.json", S.home), ("data.json", S.data)):
        m = (((doc or {}).get("live") or {}).get("pc") or {}).get("mind")
        if isinstance(m, dict):
            mind = (m, rel)
            break
    facts, plain = [], []
    near = [f for f in fest["items"] if f["days_left"] == 0]
    if brief is None:
        if near:
            f = near[0]
            facts.append(fact(f["title"] + (f" at {f['time']} ET" if f["time"] else ""), fest["src"], f"events/{f['date']}"))
            verse = f"Today is the {f['festival']}. When the city's voice speaks, let the wise stand still until the dust has settled."
            plain = [f"No morning game plan was published. The calendar has the {f['event']} today" + (f" at {f['time']} ET." if f["time"] else ".")]
        else:
            verse = "The tripod is cold. The god keeps silent today."
            plain = ["No morning game plan was published yet, so the oracle says nothing about the market."]
        return {"src": fest["src"] if near else None, "day": today, "stale": False, "speaker": S.person("villager:pythia"), "verse": verse, "plain": plain, "facts": facts}
    day = W._day(brief.get("day")) or today
    if brief.get("plan"):
        plain.append(str(brief["plan"])[:400])
        facts.append(fact(str(brief["plan"])[:400], bsrc, "live/brief/plan"))
    vix = brief.get("vix") if isinstance(brief.get("vix"), dict) else {}
    lo, hi = W._num(vix.get("low")), W._num(vix.get("high"))
    news = [n for n in brief.get("news") or [] if isinstance(n, dict) and n.get("title")]
    ev = brief.get("eval") if isinstance(brief.get("eval"), dict) else {}
    lines = []
    txt = str(brief.get("plan") or "").lower()
    if news:
        n0 = news[0]
        tm = str(n0.get("time") or "")[:5]
        facts.append(fact(f"{n0['title']} at {tm} ET" if tm else str(n0["title"]), bsrc, "live/brief/news/0"))
        lines.append(f"At the hour {tm} the bronze voice will speak. Hold the spear until the echo fades." if tm else
                     "A bronze voice will speak today. Hold the spear until the echo fades.")
        plain.append(str(brief.get("news_text") or f"News today: {n0['title']}" + (f" at {tm} ET" if tm else "") + ".")[:300])
        if brief.get("news_text"):
            facts.append(fact(str(brief["news_text"])[:300], bsrc, "live/brief/news_text"))
    if "short" in txt and "long" in txt:
        lines.append("Two roads leave the city: one climbs, one falls. Walk the one the market opens and leave the other to the crows.")
    elif "short" in txt:
        lines.append("The eagle stoops from the heights. The road leads down.")
    elif "long" in txt:
        lines.append("The lark rises from the furrow. The road leads up.")
    if lo is not None and hi is not None:
        a, b = f"{lo:,.0f}", f"{hi:,.0f}"
        facts.append(fact(f"VIX band {a} to {b}", bsrc, "live/brief/vix/low, high"))
        lines.append(f"The god's reach today runs from {a} to {b}; beyond it, take your prize and go home.")
        plain.append(f"The target band for the day (18:00 open plus or minus one VIX day move) is {a} to {b}.")
    room = W._num(ev.get("room"))
    if room is not None:
        facts.append(fact(f"{usd(room, False)} of drawdown left", bsrc, "live/brief/eval/room"))
        plain.append(f"Drawdown left today: {usd(room, False)}.")
    if mind:
        reg = (mind[0].get("regime") or {}) if isinstance(mind[0].get("regime"), dict) else {}
        if reg.get("label"):
            facts.append(fact(str(reg["label"])[:120], mind[1], "live/pc/mind/regime/label"))
            plain.append(f"The Mind reads the market as: {str(reg['label'])[:120]}.")
    if not lines:
        lines.append("Watch the swept high and the swept low. The one that fails points the way.")
    verse = " ".join(lines[:3])
    return {"src": bsrc, "day": day, "stale": day != today, "speaker": S.person("villager:pythia"), "verse": verse, "plain": plain[:5], "facts": facts}


# ------------------------------------------------------------------------------------------------ 11. herald
def herald(S, today, trades, tsrc, grove_, statues_, fest, torch_):
    lines = []
    crier = S.person("villager:herald")
    bot_person = {"Zlarior": "bot:lit", "ATLAS": "bot:atlas", "BLITZ": "bot:blitz", "Paper twin": "bot:lit"}
    for st in statues_["items"]:
        if st["kind"] == "pass":
            lines.append({"kind": "pass", "day": st["day"] or today, "cry": f"Hear, citizens! {st['title']}. Crown it with laurel.", "plain": st["title"] + ".",
                          "usd": None, "r": None, "src": statues_["src"], "by": S.person(bot_person.get(st["bot"], "")), "facts": st["facts"]})
        if st["kind"] == "payout":
            lines.append({"kind": "payout", "day": st["day"], "cry": f"Silver from the treasury! {st['title']}, {usd(st['usd'], False)} in all.",
                          "plain": f"{st['title']}: {usd(st['usd'], False)} paid out in all.", "usd": st["usd"], "r": None, "src": statues_["src"],
                          "by": S.person(bot_person.get(st["bot"], "")), "facts": st["facts"]})
    for t in trades[-3:][::-1]:
        r = W._num(t.get("r"))
        money = usd(t["pnl"]) + ("" if r is None else f" ({rtxt(r)})")
        side = "long" if str(t.get("side") or "LONG").upper().startswith(("L", "B")) else "short"
        word = "returns with a prize" if t["pnl"] > FLAT_USD else "returns wounded" if t["pnl"] < -FLAT_USD else "returns even"
        paper = " (paper)" if t.get("paper") else ""
        lines.append({"kind": "trade", "day": t["day"], "cry": f"{t['bot']}{paper} {word} from the market: {money}.",
                      "plain": f"{t['bot']}{paper} closed a {side} trade on {day_words(t['day'])}: {money}.", "usd": t["pnl"], "r": None if r is None else round(r, 2),
                      "src": tsrc, "by": S.person(bot_person.get(t["bot"], "")), "facts": [fact(t["bot"], tsrc, "trades/account"), fact(money, tsrc, "trades/pnl, r"), fact(day_words(t["day"]), tsrc, "trades/day")]})
    led = S.docs["kalshicity/ledger.json"] or {}
    kt = [t for t in (led.get("trades") or []) if isinstance(t, dict) and is_num(t.get("t")) and is_num(t.get("pnl"))]
    for t in sorted(kt, key=lambda x: -x["t"])[:2]:
        day = dt.datetime.fromtimestamp(int(t["t"]), W.NY).date().isoformat()
        what = str(t.get("s") or "a Kalshi bet")[:50]
        mk = str(t.get("m") or "")[:30]
        lines.append({"kind": "kalshi", "day": day, "cry": f"From the Kalshi paper book: {what}{' on ' + mk if mk else ''} settled {usd(t['pnl'])}.",
                      "plain": f"Kalshi paper trade settled {usd(t['pnl'])} ({what}). Paper only, no real bet.", "usd": round(float(t["pnl"]), 2), "r": None,
                      "src": "kalshicity/ledger.json", "by": S.person("bot:kalshi"), "facts": [fact(usd(t["pnl"]), "kalshicity/ledger.json", "trades/pnl"), fact(what, "kalshicity/ledger.json", "trades/s")]})
    mi = S.docs["money/index.json"] or {}
    base = W._num((mi.get("total") or {}).get("base"))
    if base is not None:
        n = (mi.get("counts") or {}).get("streams")
        nn = f"{int(n)} " if is_num(n) else ""
        lines.append({"kind": "money", "day": W._day(mi.get("asof")) or today, "cry": f"The {nn}money machines reckon about {usd(base, False)} a month. An estimate, not a promise.",
                      "plain": f"Money machines (paper): an estimate of about {usd(base, False)} a month. Not a promise.", "usd": base, "r": None,
                      "src": "money/index.json", "by": S.person("keeper:money"),
                      "facts": [fact(usd(base, False), "money/index.json", "total/base")] + ([fact(str(int(n)), "money/index.json", "counts/streams")] if nn else [])})
    for f in fest["items"]:
        if f["days_left"] <= 2:
            tm = f" at {f['time']} ET" if f["time"] else ""
            lines.append({"kind": "festival", "day": f["date"], "cry": f"The {f['festival']} comes {f['when']}! The {f['event']}{tm}.",
                          "plain": f"{f['title']} {f['when']}{tm}.", "usd": None, "r": None, "src": fest["src"], "by": crier,
                          "facts": [fact(f["when"] + tm, fest["src"], f"events/{f['date']}"), fact(f["title"], fest["src"], f"events/{f['date']}/title")]})
            break
    w = torch_["weeks"]["streak"]
    if w >= 2:
        lines.append({"kind": "torch", "day": today, "cry": f"The torch has passed through {w} green weeks in a row. Keep it burning.",
                      "plain": f"{w} green weeks in a row with every trade inside the rules.", "usd": None, "r": None, "src": torch_["src"], "by": crier,
                      "facts": [fact(str(w), torch_["src"], "weeks", "count of green weeks in a row")]})
    order = {"payout": 1, "trade": 3, "torch": 4, "kalshi": 5, "money": 6}
    first = [x for x in lines if x["kind"] in ("pass", "festival")]
    rest = sorted([x for x in lines if x["kind"] not in ("pass", "festival")], key=lambda x: (x.get("day") or "", -order[x["kind"]]), reverse=True)
    out = (first + rest)[:MAX_HERALD]
    for x in out:
        x["crier"] = crier
    return out


# ------------------------------------------------------------------------------------------------ 18. stoic
def stoic(today, trades, torch_, fest):
    mood = "quiet"
    last = trades[-1] if trades else None
    drows = torch_["days"]["rows"]
    if drows and not drows[-1]["kept"]:
        mood = "discipline"
    elif last is not None and last["pnl"] < -FLAT_USD:
        mood = "loss"
    elif last is not None and last["pnl"] > FLAT_USD:
        mood = "win"
    if mood in ("win", "quiet") and any(f["days_left"] <= 1 and f["kind"] in ("fomc", "cpi", "nfp") for f in fest["items"]):
        mood = "storm"
    if mood == "quiet" and torch_["weeks"]["streak"] >= 2:
        mood = "steady"
    pool = STOIC[mood]
    text, who, work, tr = pool[seed("stoic", today, mood) % len(pool)]
    return {"mood": mood, "why": MOOD_WHY[mood], "text": text, "author": who, "work": work, "translator": tr, "public_domain": True}


# ------------------------------------------------------------------------------------------------ the whole polis
def build(web, date, demo=False):
    S = Sources(web)
    trades, tsrc = closed_trades(S)
    trades = [t for t in trades if t["day"] <= date]
    A, asrc = accounts(S)
    fest = festivals(S, date)
    tor = torch(trades, tsrc, date)
    gr = grove(A, asrc, trades)
    am = amphorae(trades, tsrc)
    stt = statues(trades, tsrc, A, asrc)
    orc = oracle(S, date, fest)
    her = herald(S, date, trades, tsrc, gr, stt, fest, tor)
    sto = stoic(date, trades, tor, fest)
    return {"v": VERSION, "kind": "olympus-polis", "date": date, "built": S.newest(), "demo": bool(demo), "paper": True,
            "label": "DEMO: made-up example files, not real numbers." if demo else "Written from the published files. Nothing is invented. Paper only.",
            "herald": her, "oracle": orc, "festivals": fest, "torch": tor, "grove": gr, "amphorae": am, "statues": stt, "stoic": sto,
            "sources": {"read": sorted(S.read), "missing": sorted(S.missing), "trades": tsrc, "accounts": asrc}}


def all_audits(doc):
    bad = []
    for h in doc["herald"]:
        if audit(h):
            bad.append(("herald", h["cry"], audit(h)))
    if doc["oracle"] and audit(doc["oracle"], ("verse",)):
        bad.append(("oracle", doc["oracle"]["verse"], audit(doc["oracle"], ("verse",))))
    for g in doc["grove"]["trees"]:
        if audit({"line": g["line"], "facts": g["facts"]}, ("line",)):
            bad.append(("grove", g["line"], audit({"line": g["line"], "facts": g["facts"]}, ("line",))))
    for s in doc["statues"]["items"]:
        if audit(s, ("plaque", "title")):
            bad.append(("statue", s["plaque"], audit(s, ("plaque", "title"))))
    return bad


def dump(obj):
    return json.dumps(obj, indent=1, ensure_ascii=False) + "\n"


# ------------------------------------------------------------------------------------------------ the sample site (demo + tests)
def _ts(day, hhmm):
    h, m = (int(x) for x in hhmm.split(":"))
    y, mo, d = (int(x) for x in day.split("-"))
    return int(dt.datetime(y, mo, d, h, m, tzinfo=W.NY).timestamp())


# day, entry HH:MM, minutes held, side, entry, risk pts, exit, R, $   (made up: the demo only)
SAMPLE_LIT = [
    ("2026-09-15", "09:41", 52, "LONG", 24010.25, 21.0, "TARGET", 8.0, 1480.0), ("2026-09-17", "10:02", 18, "SHORT", 24188.5, 19.0, "STOP", -1.0, -185.0),
    ("2026-09-18", "03:12", 40, "LONG", 24101.0, 16.0, "BE", 0.0, 2.5), ("2026-09-22", "09:47", 70, "SHORT", 24320.0, 22.5, "TARGET", 6.2, 1140.0),
    ("2026-09-24", "02:55", 31, "LONG", 24233.75, 24.0, "STOP", -1.0, -240.0), ("2026-09-24", "14:10", 20, "LONG", 24190.0, 20.0, "STOP", -1.0, -200.0), ("2026-09-29", "10:12", 15, "LONG", 24400.5, 18.0, "TIME", -0.4, -76.0),
    ("2026-10-01", "09:39", 160, "SHORT", 24512.25, 20.0, "FLAT", 2.1, 420.0), ("2026-10-06", "09:42", 48, "LONG", 24812.25, 22.0, "TARGET", 8.0, 1520.0),
    ("2026-10-08", "10:05", 21, "SHORT", 24960.5, 18.5, "STOP", -1.0, -190.0), ("2026-10-09", "03:15", 64, "LONG", 24890.0, 15.25, "BE", -0.02, -4.1),
    ("2026-10-14", "09:51", 12, "SHORT", 25102.75, 20.0, "STOP", -1.0, -205.0), ("2026-10-20", "09:38", 95, "SHORT", 25210.5, 19.0, "TARGET", 6.4, 1216.0),
    ("2026-10-22", "02:48", 33, "LONG", 25005.25, 24.0, "STOP", -1.0, -260.0), ("2026-10-23", "11:05", 280, "LONG", 25118.0, 17.5, "FLAT", 1.6, 448.0),
    ("2026-10-27", "09:44", 18, "LONG", 25301.25, 21.0, "STOP", -1.0, -240.0), ("2026-10-29", "09:47", 74, "SHORT", 25412.0, 23.75, "TARGET", 8.0, 1912.5),
    ("2026-11-03", "09:52", 41, "LONG", 25288.5, 16.0, "FLAT", 1.2, 310.0), ("2026-11-05", "10:08", 22, "SHORT", 25390.0, 18.0, "TARGET", 3.4, 640.0),
    ("2026-11-10", "09:44", 26, "LONG", 25260.0, 20.0, "STOP", -1.0, -210.0),
]
SAMPLE_ATLAS = [
    ("2026-10-28", "10:31", 36, "LONG", 25350.25, 12.0, "TARGET", 2.0, 240.0), ("2026-10-30", "13:02", 22, "SHORT", 25270.75, 15.0, "STOP", -1.0, -150.0),
    ("2026-11-04", "11:20", 30, "SHORT", 25430.0, 14.0, "TARGET", 2.0, 280.0), ("2026-11-06", "13:40", 28, "LONG", 25300.0, 13.0, "TARGET", 2.0, 260.0),
]


def _sample_trades(rows):
    out = []
    for day, hm, held, side, entry, risk, ex, r, pnl in rows:
        s = 1 if side == "LONG" else -1
        et = _ts(day, hm)
        out.append({"day": day, "entry_t": et, "exit_t": et + held * 60, "side": side, "qty": 5, "entry": entry, "stop": round(entry - s * risk, 2),
                    "sweep_ext": round(entry - s * (risk - 0.25), 2), "exit": ex, "r": r, "pnl": pnl, "risk_pts": risk})
    return out


def sample_site(tmp):
    """A tiny made-up site folder with every file the polis reads (easy numbers). Returns the web folder."""
    web = os.path.join(tmp, "web")
    for sub in ("pythia", "kalshicity", "money", "olympus"):
        os.makedirs(os.path.join(web, sub), exist_ok=True)

    def put(rel, obj):
        with open(os.path.join(web, rel), "w", encoding="utf-8", newline="\n") as fh:
            json.dump(obj, fh, ensure_ascii=False)
    lit, atl = _sample_trades(SAMPLE_LIT), _sample_trades(SAMPLE_ATLAS)
    lit_profit = round(sum(t["pnl"] for t in lit if t["day"] >= "2026-10-27"), 2)
    accts = [
        {"id": "mffu50k_eval", "name": "Zlarior 50K", "kind": "eval", "source": "pc", "trades": lit,
         "eval": {"start_balance": 50000.0, "balance": 50000.0 + lit_profit, "profit": lit_profit, "target_balance": 53000.0, "room": 1830.0, "mll": 2000.0,
                  "progress": round(lit_profit / 3000.0, 4), "status": "on_track", "start": "2026-10-27"}},
        {"id": "atlas25k", "name": "ATLAS 25K", "kind": "funded", "source": "pc", "trades": atl,
         "eval": {"start_balance": 25000.0, "balance": 26520.0, "profit": 1520.0, "target_balance": 26500.0, "room": 1000.0, "mll": 1000.0, "progress": 1.0, "status": "passed"},
         "funded": {"start": "2026-10-26", "payouts": {"2026-11-09": 500.0}}},
        {"id": "blitz25k", "name": "BLITZ 25K", "kind": "eval", "source": "pc_blitz", "trades": [],
         "eval": {"start_balance": 25000.0, "balance": 24880.0, "profit": -120.0, "target_balance": 26500.0, "room": 880.0, "mll": 1000.0, "progress": 0.0, "status": "on_track"}},
        {"id": "cloud_paper", "name": "Paper (cloud)", "kind": "paper", "source": "cloud", "trades": []},
    ]
    put("data.json", {"built": "2026-11-11T06:10:00+00:00", "accounts": accts, "live": {}})
    put("home.json", {"built": "2026-11-11T06:10:00+00:00", "home_only": True, "accounts": [{k: v for k, v in a.items() if k != "trades"} for a in accts],
                      "live": {"brief": {"day": "2026-11-11", "plan": "A sweep of the Asia high above is the short setup, target near the VIX band low. A sweep of yesterday's low below is the long setup, target near the VIX band high.",
                                         "vix": {"vix": 17.2, "move": 261.7, "open18": 25300, "low": 25038.3, "high": 25561.7},
                                         "news": [{"time": "10:30", "title": "Crude Oil Inventories", "kind": "Energy"}],
                                         "news_text": "Example news today: Crude Oil Inventories 10:30.", "eval": {"room": 1830, "to_target": 1932}},
                               "pc": {"mind": {"regime": {"label": "Quiet range, normal volatility"}}}}})
    put("pythia/events.json", {"v": 1, "updated": "2026-11-10", "events": [
        {"date": "2026-11-10", "time": "08:30", "kind": "cpi", "title": "Example CPI", "impact": "high", "verify": True},
        {"date": "2026-11-12", "time": "08:30", "kind": "other", "title": "Example claims", "impact": "low", "verify": True},
        {"date": "2026-11-13", "time": "08:30", "kind": "cpi", "title": "Example CPI (consumer prices)", "impact": "high", "verify": True},
        {"date": "2026-12-04", "time": "08:30", "kind": "nfp", "title": "Example jobs report (NFP)", "impact": "high", "verify": True},
        {"date": "2026-12-09", "time": "14:00", "kind": "fomc", "title": "Example FOMC decision 2:00 PM", "impact": "high", "verify": True},
        {"date": "2026-12-09", "time": "16:00", "kind": "roll", "title": "Example roll step: switch the chart", "impact": "med", "verify": False},
        {"date": "2026-12-10", "time": "00:00", "kind": "roll", "title": "Example NQ roll", "impact": "med", "verify": False}]})
    put("kalshicity/ledger.json", {"v": 1, "trades": [
        {"t": _ts("2026-11-09", "10:15"), "k": "EX-1", "s": "Example late favourite", "m": "Bitcoin", "sd": "no", "p": 0.97, "c": 6.0, "pnl": 0.18},
        {"t": _ts("2026-11-10", "15:05"), "k": "EX-2", "s": "Example 15-min favourite", "m": "Bitcoin", "sd": "yes", "p": 0.95, "c": 12.0, "pnl": -0.6}]})
    put("money/index.json", {"v": 1, "asof": "2026-11-10T06:00:00Z", "total": {"low": -40.0, "base": 310.5, "high": 900.0}, "counts": {"streams": 5}})
    put("olympus/people.json", {"v": 1, "asof": "2026-11-10", "people": [{"id": "bot:lit", "name": "Phoibos"}, {"id": "bot:atlas", "name": "Telamon"},
                                                                           {"id": "bot:kalshi", "name": "Eutychos"}, {"id": "keeper:money", "name": "Tamias"}],
                                "villagers": [{"id": "villager:herald", "name": "Kosmas"}, {"id": "villager:pythia", "name": "Delia"}]})
    return web


DEMO_DATE = "2026-11-11"


def fixture():
    with tempfile.TemporaryDirectory() as tmp:
        return build(sample_site(tmp), DEMO_DATE, demo=True)


# ------------------------------------------------------------------------------------------------ check / selftest / main
def check(web, out, with_demo):
    cur = read_json(out)
    if not isinstance(cur, dict) or not W._day(cur.get("date")):
        return False
    if dump(cur) != dump(build(web, cur["date"], demo=bool(cur.get("demo")))):
        return False
    if with_demo:
        demo = read_json(os.path.join(WEB, DEMO_REL))
        return isinstance(demo, dict) and dump(demo) == dump(fixture())
    return True


def selftest():
    res = []

    def t(name, ok, info=""):
        res.append(bool(ok))
        print(("[PASS] " if ok else "[FAIL] ") + name + ("" if ok else f"  -> {str(info)[:600]}"))
    t("usd / R words: +$1,912.50, -$240, $0 (never -$0), +8.0R", [usd(1912.5), usd(-240), usd(-0.001), rtxt(8), rtxt(-1)] == ["+$1,912.50", "-$240", "$0", "+8.0R", "-1.0R"])
    t("audit catches a stray number", audit({"cry": "won 12 and 99", "facts": [fact("12", "a")]}) == ["99"])
    with tempfile.TemporaryDirectory() as tmp:
        empty = build(os.path.join(tmp, "nothing"), "2026-11-11")
        t("empty site: valid, every part present and empty, built-in calendar labelled, stoic line still there",
          all(h["kind"] == "festival" for h in empty["herald"]) and empty["grove"]["trees"] == [] and empty["amphorae"]["n"] == 0
          and empty["festivals"]["builtin"] and "Built-in" in empty["festivals"]["label"] and empty["stoic"]["text"] and empty["torch"]["flame"] == "unlit", empty["herald"])
    fx = fixture()
    t("demo: deterministic, labelled DEMO, numbers audited", dump(fx) == dump(fixture()) and fx["demo"] and not all_audits(fx), all_audits(fx))
    t("demo: 4 trees (one paper), 24 amphorae over 3 shelves, a pass and a payout statue", len(fx["grove"]["trees"]) == 4 and fx["amphorae"]["n"] == 24
      and [s["month"] for s in fx["amphorae"]["shelves"]] == ["2026-11", "2026-10", "2026-09"] and {"pass", "payout"} <= {s["kind"] for s in fx["statues"]["items"]})
    bad = res.count(False)
    print(f"\n{len(res) - bad}/{len(res)} passed")
    return 1 if bad else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--date", default=None, help="YYYY-MM-DD (default: today, UTC)")
    ap.add_argument("--web", default=WEB, help="the site folder to read and to write olympus/polis.json into (default: tools/web_public)")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    out = os.path.join(a.web, OUT_REL)
    with_demo = os.path.abspath(a.web) == os.path.abspath(WEB)
    if a.check:
        ok = check(a.web, out, with_demo)
        print("polis: polis.json is up to date" if ok else "polis: polis.json is STALE (run python tools/polis_build.py --date <its date>)")
        return 0 if ok else 1
    date = a.date or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    if not W._day(date):
        print("polis: --date must be YYYY-MM-DD")
        return 2
    doc = build(a.web, date)
    bad = all_audits(doc)
    if bad:
        print("polis: refused, a printed number is not among its facts:", bad[:3])
        return 1
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(dump(doc))
    if with_demo:
        with open(os.path.join(WEB, DEMO_REL), "w", encoding="utf-8", newline="\n") as fh:
            fh.write(dump(fixture()))
    print(f"polis: {date}: {len(doc['herald'])} herald lines, oracle {'yes' if doc['oracle']['facts'] else 'silent'}, {len(doc['festivals']['items'])} festivals"
          f"{' (built-in table)' if doc['festivals']['builtin'] else ''}, torch {doc['torch']['weeks']['streak']} weeks / {doc['torch']['days']['streak']} days, "
          f"{len(doc['grove']['trees'])} trees, {doc['amphorae']['n']} amphorae, {len(doc['statues']['items'])} statues, stoic: {doc['stoic']['author']}"
          f"; missing: {', '.join(doc['sources']['missing']) or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
