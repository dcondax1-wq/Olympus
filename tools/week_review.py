#!/usr/bin/env python3
"""WEEK IN REVIEW data (day-weekreview 2026-11-27) -> tools/web_public/nq/week_review.json, for the phone page nq/week.html.

Owner (MFFU prop trader, phone first): "what happened this week, in plain words, with $". Four selectable weeks (this one + 3 before).
Per account (Zlarior 50K, Zlarior 25K #2, Rapid EOD 25K, ATLAS 25K funded): the week's $ and trades, every trade as a card (side,
entry / exit, $, R, why it won or lost in one line), the setups that formed but were rejected and why, the trades the backtest twin
took that the account did not (bot = backtest check, with the cause), what each bot is waiting for now, the MFFU 7-day clock and
the payout progress, the order-flow practice lane (paper), BLITZ (hidden, paper) and next week's events, then a Grade.

Sources, every one optional (a missing one is NAMED in "sources.missing", never guessed). Read only: nothing here trades:
  live feed   tools/board.py fetch_lite (the PC's public status post: accounts, trades, at, mf, k7, arm, glog, ofp, p4) - network, optional
  twins       tools/web_public/nq/replay/<day>.json (tools/build_replay.py: the bots' backtest twins: entries, exits, rejected setups, notes)
  live days   research/livegap/daily.json (the pulled PC day folders: live trades + $ per account per day) + research/livegap/missed_*.json (causes)
  PC ledgers  tools/weekly_review.pc_rows / day_rows when this machine has them (the PC, or after tools/data_pull.py)
  calendar    nq/ports.json if present, else nq/news_week.json; engine/cme_calendar (holiday / early close)
  order flow  the 'of' notes of the replay days + the feed's "ofp" block; BLITZ: research/forward/forward.json (bot BLITZ rules) + the feed's p4
The feed's "glog" (the bots' last 3 rejected setups) is a live ring: each build merges it into the previous week_review.json so the
list grows over the week (nothing else keeps it).
Privacy: account names only; no account numbers (the page masks them), no keys. Public site: the $ are the owner's own figures, like business/week.json.

    python -X utf8 tools/week_review.py [--offline] [--now EPOCH] [--out FILE]      (--offline: no network, repo files only)
Test: python -X utf8 -m tests.test_nq_week [--browser]
"""
from __future__ import annotations

import argparse
import datetime as dt
import glob
import json
import os
import re
import sys
import time
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
NQ = os.path.join(ROOT, "tools", "web_public", "nq")
OUT = os.path.join(NQ, "week_review.json")
ET = ZoneInfo("America/New_York")
N_WEEKS = 4
MAX_BYTES = 180_000

ACCTS = [
    {"id": "z50k", "feed": "mffu50k_eval", "name": "Zlarior 50K", "plan": "Builder 50K eval", "twin": ["LIT"], "stage": "eval"},
    {"id": "z25k2", "feed": "b25k_2", "name": "Zlarior 25K #2", "plan": "Builder 25K eval", "twin": ["LIT"], "stage": "eval"},
    {"id": "rapid", "feed": "rapid", "name": "Rapid EOD 25K", "plan": "Rapid EOD 25K eval", "twin": ["LIT", "ATLAS"], "stage": "eval"},
    {"id": "atlas25", "feed": "atlas", "name": "ATLAS 25K", "plan": "Builder 25K funded", "twin": ["ATLAS"], "stage": "funded"},
]
BY_ID = {a["id"]: a for a in ACCTS}
FEED_TO_ID = {a["feed"]: a["id"] for a in ACCTS}
FEED_TO_ID.update({"lit": "z50k", "zlarior": "z50k", "atlas": "atlas25"})
MEMBER_WORDS = {"ema_lon_vix": "EMA (London, VIX band)", "macd_sweep": "MACD after a sweep", "sr_nyreclaim": "S/R New York reclaim",
                "EMA": "EMA", "MACD": "MACD", "S/R": "S/R", "LIT": "LIT"}
REJECT_GLOSS = {"idm": "no inducement before the sweep", "t15": "the 15-minute check said no", "target": "failed the target check"}
DOW = ["Mon", "Tue", "Wed", "Thu", "Fri"]


# ------------------------------------------------------------------------------------------------ small helpers
def _j(path, default=None):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:  # noqa: BLE001
        return default


def _f(v):
    try:
        x = float(v)
        return x if x == x else None
    except (TypeError, ValueError):
        return None


def _d(x) -> dict:
    return x if isinstance(x, dict) else {}


def _l(x) -> list:
    return x if isinstance(x, list) else []


def mask(s, n=200) -> str:
    """No account numbers / broker account names on a public page."""
    s = str(s or "")
    s = re.sub(r"MFFU[A-Z0-9]*[….]*\d{2,4}", "the account", s)
    s = re.sub(r"(?:\.\.\.|…)\s?\d{3,4}\b", "", s)
    s = re.sub(r"\b\d{9,}\b", "", s)
    return re.sub(r"\s+", " ", s).strip()[:n]


def et(t):
    return dt.datetime.fromtimestamp(int(t), ET)


def hm(t) -> str:
    return et(t).strftime("%H:%M")


def tday(t) -> str:
    """CME trading day of a unix time: 18:00 ET starts the next day."""
    return (et(t) + dt.timedelta(hours=6)).strftime("%Y-%m-%d")


def usd(v, sign=True) -> str:
    v = _f(v)
    if v is None:
        return "-"
    s = f"${abs(v):,.0f}"
    return ("+" if v >= 0 else "-") + s if sign else (("-" if v < 0 else "") + s)


def monday_of(day: str) -> str:
    d = dt.date.fromisoformat(day)
    return (d - dt.timedelta(days=d.weekday())).isoformat()


def week_days(mon: str) -> list:
    m = dt.date.fromisoformat(mon)
    return [(m + dt.timedelta(days=i)).isoformat() for i in range(5)]


def label_of(mon: str) -> str:
    m = dt.date.fromisoformat(mon)
    f = m + dt.timedelta(days=4)
    return f"{m.strftime('%b')} {m.day} - {f.strftime('%b')} {f.day}"


def day_status(day: str, today: str, now_et: dt.datetime) -> dict:
    """{d, dow, state: past|today|future|closed, note}. closed = a full CME closure, early = early halt (engine/cme_calendar)."""
    out = {"d": day, "dow": DOW[dt.date.fromisoformat(day).weekday()], "state": "past" if day < today else "today" if day == today else "future"}
    try:
        from engine import cme_calendar as C
        if C.full_closure(day):
            out["state"], out["note"] = "closed", "CME closed"
        else:
            e = C.early_close(day)
            if e:
                out["note"] = f"early halt {e // 60:02d}:{e % 60:02d} ET"
    except Exception:  # noqa: BLE001
        pass
    return out


# ------------------------------------------------------------------------------------------------ sources
def feed(offline: bool):
    if offline:
        return None
    try:
        from tools import board
        return board.fetch_lite()
    except Exception:  # noqa: BLE001
        return None


def replay_day(day: str):
    return _j(os.path.join(NQ, "replay", day + ".json"))


def twin_trades(rep: dict) -> list:
    """The twins' trades of one replay day: entry + exit events paired by id."""
    ent, out = {}, []
    for e in _l(_d(rep).get("events")):
        if e.get("kind") == "entry":
            ent[e.get("id")] = e
        elif e.get("kind") == "exit" and e.get("id") in ent:
            n = ent.pop(e["id"])
            out.append({"bot": n.get("bot"), "member": n.get("member") or n.get("bot"), "side": n.get("side"), "in_t": n.get("t"), "out_t": e.get("t"),
                        "in_hm": n.get("hm") or (hm(n["t"]) if n.get("t") else None), "out_hm": e.get("hm") or (hm(e["t"]) if e.get("t") else None),
                        "entry": n.get("px"), "stop": n.get("stop"), "target": n.get("target"), "qty": n.get("qty"),
                        "r": e.get("r"), "usd": e.get("usd"), "exit": str(e.get("how") or "")})
    return sorted(out, key=lambda x: x.get("in_t") or 0)


def rejected_from_replay(rep: dict) -> list:
    out = []
    for e in _l(_d(rep).get("events")):
        if e.get("kind") != "setup":
            continue
        txt = str(e.get("text") or "")
        m = re.search(r"stopped: ([^;]+)(?:; it would have made ([+-][\d.]+)R)?", txt)
        out.append({"hm": e.get("hm") or (hm(e["t"]) if e.get("t") else ""), "bot": e.get("bot") or "LIT", "side": e.get("side"),
                    "why": (m.group(1).strip() if m else txt[:80]), "would_r": (float(m.group(2)) if m and m.group(2) else None), "src": "replay"})
    return out


OF_RE = re.compile(r"Order flow \(paper\): (.+?) swept (long|short) side, (absorbed|not absorbed) -> (taken|skipped), ([+-][\d.]+)R")


def of_from_replay(rep: dict) -> list:
    out = []
    for n in _l(_d(rep).get("notes")):
        m = OF_RE.search(str(n.get("text") or ""))
        if m:
            out.append({"level": m.group(1), "dir": m.group(2), "absorbed": m.group(3) == "absorbed", "taken": m.group(4) == "taken", "r": float(m.group(5))})
    return out


def live_notes(rep: dict) -> dict:
    """{account id: {trades, usd, twin, gap}} from the replay day's 'Live X: n trades ($) vs the twin's m; gap KIND' notes."""
    nm = {"Zlarior 50K": "z50k", "Zlarior 25K #2": "z25k2", "Rapid EOD 25K": "rapid", "ATLAS 25K": "atlas25"}
    out = {}
    for n in _l(_d(rep).get("notes")):
        m = re.match(r"Live (.+?): (\d+) trades? \(([+-])\$([\d,]+)\) vs the twin's (\d+)(?:; gap (.+))?", str(n.get("text") or ""))
        if m and m.group(1) in nm:
            out[nm[m.group(1)]] = {"trades": int(m.group(2)), "usd": (1 if m.group(3) == "+" else -1) * float(m.group(4).replace(",", "")),
                                   "twin": int(m.group(5)), "gap": m.group(6)}
    return out


def daily_rows():
    d = _d(_j(os.path.join(ROOT, "research", "livegap", "daily.json")))
    out = {}
    for r in _l(d.get("rows")):
        out[(r.get("account"), r.get("day"))] = r
    return out, bool(d)


def missed_causes():
    out = {}
    for p in sorted(glob.glob(os.path.join(ROOT, "research", "livegap", "missed_*.json"))):
        for g in _l(_d(_j(p)).get("gaps")):
            out.setdefault((g.get("key"), g.get("day")), []).append(g)
    return out


def pick_gap(gaps: dict, aid: str, day: str, side):
    """The audited gap row for this account + day (same side first)."""
    keys = {"z25k2": ["z25k2", "z50k"], "rapid": ["rapid25k", "rapid", "z50k"], "z50k": ["z50k"], "atlas25": ["atlas25"]}.get(aid, [aid])
    for k in keys:
        rows = gaps.get((k, day)) or []
        for g in rows:
            if str(_d(g.get("twin")).get("side") or "").upper() == str(side or "").upper():
                return g
        if rows:
            return rows[0]
    return None


def ledger_trades(days: list) -> list:
    """Closed live trades from the PC's own ledgers, when this machine has them (the PC; a cloud checkout after data_pull). [] otherwise."""
    try:
        from tools import weekly_review as W
        rows = W.pc_rows(ROOT)
        extra, _ = W.day_rows(days, ROOT, offline=True)
        rows += extra
    except Exception:  # noqa: BLE001
        return []
    out, seen = [], set()
    for r in rows:
        try:
            if r.get("side") != "exit" or r.get("void") or r.get("mode") != "live":
                continue
            t = _f(r.get("exit_t")) or _f(r.get("t"))
            pnl = _f(r.get("pnl"))
            if t is None or pnl is None or tday(t) not in days:
                continue
            a = str(r.get("acct") or r.get("account") or "").lower()
            aid = FEED_TO_ID.get(a) or ("atlas25" if "atlas" in a else "z25k2" if "25k" in a and "2" in a else "rapid" if "rapid" in a else "z50k")
            sig = (aid, int(_f(r.get("entry_t")) or 0), round(pnl, 2))
            if sig in seen:
                continue
            seen.add(sig)
            out.append({"acct": aid, "day": tday(t), "pnl": round(pnl, 2), "entry_t": r.get("entry_t"), "exit_t": t, "dir": r.get("dir"),
                        "entry": r.get("entry"), "stop": r.get("stop"), "target": r.get("target"), "r": r.get("r"), "reason": r.get("reason"),
                        "qty": r.get("qty")})
        except Exception:  # noqa: BLE001
            continue
    return out


# ------------------------------------------------------------------------------------------------ trade cards
def why_line(c: dict) -> str:
    """One plain line: why this trade won or lost (from how it exited; no hindsight claims beyond that)."""
    ex = str(c.get("exit") or "").upper().replace(" ", "_")
    r = _f(c.get("r"))
    who = c.get("setup") or c.get("bot") or "The bot"
    side = c.get("side") or ""
    if ex.startswith("TARGET"):
        return f"WON: the {who} {side} read the sweep right and price ran to the target ({r:+.1f}R)." if r is not None else f"WON: price ran to the {who} target."
    if ex.startswith("STOP"):
        return f"LOST: price went back through the stop before the target: the planned loss ({r:+.1f}R), size follows the stop." if r is not None else "LOST: the stop was hit: the planned loss."
    if ex.startswith("BE"):
        return "FLAT: the stop moved to break-even once price went our way, then price came back: about $0."
    if ex.startswith("CUT"):
        return f"SMALL LOSS: the bot's time rule cut it early (15-minute check: no progress), cheaper than the full stop ({r:+.2f}R)." if r is not None else "Cut early by the 15-minute time rule."
    if ex.startswith("EOD") or ex.startswith("FLAT"):
        return f"Held to the end of the session and closed at the bell ({r:+.1f}R)." if r is not None else "Held to the end of the session."
    if ex:
        return f"Closed by {ex.replace('_', ' ').lower()} ({r:+.1f}R)." if r is not None else f"Closed by {ex.replace('_', ' ').lower()}."
    return "Closed; the exit reason was not in the feed."


def _card(base: dict) -> dict:
    base["why"] = why_line(base)
    return base


def cards_from_feed(lite) -> list:
    """The feed's recent closed trades (board.trades = ATLAS lane, with at[] giving the prices) as cards."""
    out = []
    if not isinstance(lite, dict):
        return out
    px = {}
    for a in _l(lite.get("at", {}).get("a") if isinstance(lite.get("at"), dict) else None):
        for tr in _l(_d(a).get("tr")):
            if isinstance(tr, list) and len(tr) >= 10:
                px[int(tr[0])] = {"entry": tr[4], "stop": tr[5], "target": tr[6]}
    for t in _l(_d(lite.get("board")).get("trades")):
        aid = FEED_TO_ID.get(str(t.get("acct")))
        if not aid or t.get("open") or _f(t.get("usd")) is None or not t.get("entry_t"):
            continue
        p = px.get(int(t["entry_t"]), {})
        out.append(_card({"acct": aid, "day": t.get("day") or tday(t["entry_t"]), "bot": "ATLAS", "setup": MEMBER_WORDS.get(t.get("key"), t.get("member")),
                          "side": str(t.get("side") or "").upper(), "qty": t.get("qty"), "in_hm": hm(t["entry_t"]), "out_hm": hm(t["exit_t"]) if t.get("exit_t") else None,
                          "entry": p.get("entry"), "stop": p.get("stop"), "target": p.get("target"), "usd": _f(t.get("usd")), "r": _f(t.get("r")),
                          "exit": t.get("exit"), "mode": "paper" if t.get("src") == "paper" else "live", "src": "feed", "in_t": t["entry_t"]}))
    return out


def cards_from_ledger(rows: list) -> list:
    out = []
    for r in rows:
        it = _f(r.get("entry_t"))
        out.append(_card({"acct": r["acct"], "day": r["day"], "bot": "ATLAS" if r["acct"] == "atlas25" else "LIT", "side": ("LONG" if (_f(r.get("dir")) or 0) > 0 else "SHORT"),
                          "qty": r.get("qty"), "in_hm": hm(it) if it else None, "out_hm": hm(r["exit_t"]), "entry": r.get("entry"), "stop": r.get("stop"),
                          "target": r.get("target"), "usd": r["pnl"], "r": _f(r.get("r")), "exit": r.get("reason"), "mode": "live", "src": "ledger", "in_t": int(it) if it else None}))
    return out


def fill_from_daily(cards: list, rows: dict, twins_by_day: dict, days: list) -> list:
    """A live trade the feed / ledger has no detail for (the feed holds only the last few) but the pulled day folders count: a card from
    the matching twin trade (same bot family + side), $ = the live $, flagged src 'twin' (entry / stop / target are the twin's)."""
    for (aid, day), r in sorted(rows.items(), key=lambda kv: kv[0][1]):
        if aid not in BY_ID or day not in days:
            continue
        have = [c for c in cards if c["acct"] == aid and c["day"] == day and c.get("mode") == "live"]
        n_live = int(r.get("live_trades") or 0)
        if n_live <= len(have):
            continue
        rest = _f(r.get("live_usd")) or 0.0
        rest -= sum(c.get("usd") or 0 for c in have)
        fam = BY_ID[aid]["twin"]
        cand = [t for t in twins_by_day.get(day, []) if t["bot"] in fam]
        det = _l(r.get("diffs"))
        for k in range(n_live - len(have)):
            tw = None
            if det:
                dd = det[min(k, len(det) - 1)]
                tw = next((t for t in cand if str(t.get("side") or "").upper() == str(dd.get("side") or "").upper() and (not dd.get("bot") or t.get("member") == dd.get("bot") or t["bot"] == dd.get("bot"))), None)
            tw = tw or (cand[k] if k < len(cand) else None)
            u = rest if k == n_live - len(have) - 1 else None
            c = {"acct": aid, "day": day, "bot": (tw or {}).get("bot") or fam[0], "setup": (tw or {}).get("member"), "side": str((tw or {}).get("side") or "").upper(),
                 "qty": None, "in_hm": (tw or {}).get("in_hm"), "out_hm": (tw or {}).get("out_hm"), "entry": (tw or {}).get("entry"), "stop": (tw or {}).get("stop"),
                 "target": (tw or {}).get("target"), "usd": round(u, 2) if u is not None else None, "r": (tw or {}).get("r"), "exit": (tw or {}).get("exit"),
                 "mode": "live", "src": "twin", "in_t": (tw or {}).get("in_t")}
            cards.append(_card(c))
    return cards


# ------------------------------------------------------------------------------------------------ one week
def week_block(mon: str, ctx: dict) -> dict:
    days = week_days(mon)
    today, now_et = ctx["today"], ctx["now_et"]
    cur = mon == monday_of(today)
    ds = [day_status(d, today, now_et) for d in days]
    reps = {d: replay_day(d) for d in days}
    twins = {d: twin_trades(reps[d]) for d in days if reps[d]}
    cards = [c for c in ctx["cards"] if c["day"] in days]
    cards = fill_from_daily(cards, ctx["daily"], twins, days)
    cards.sort(key=lambda c: (c["day"], c.get("in_t") or 0))
    gaps = ctx["gaps"]
    missing = []

    # ---- accounts
    accts = []
    for a in ACCTS:
        mine = [c for c in cards if c["acct"] == a["id"]]
        if a["id"] == "atlas25":                       # the funded tracker starts at the eval pass: earlier trades are EVAL phase, listed but never summed into the funded week
            fs = ctx["starts"].get("atlas25_funded", "2026-11-17")
            for c in mine:
                if c["day"] <= fs:
                    c["phase"] = "eval"
        live = [c for c in mine if c.get("mode") == "live" and c.get("phase") != "eval"]
        wk = round(sum(c.get("usd") or 0 for c in live), 2)
        row = {"id": a["id"], "name": a["name"], "plan": a["plan"], "stage": a["stage"], "usd": wk, "n": len(live), "wins": sum(1 for c in live if (c.get("usd") or 0) > 0),
               "losses": sum(1 for c in live if (c.get("usd") or 0) < 0), "trades": mine, "note": None}
        if cur and ctx.get("acct_now", {}).get(a["id"]):
            row["now"] = ctx["acct_now"][a["id"]]
            fw = row["now"].get("week")
            if fw is not None and abs(fw - wk) > 1.0 and not live:
                row["usd"], row["note"] = round(fw, 2), "the feed's week total (no per-trade card for it)"
        ev = [c for c in mine if c.get("phase") == "eval" and c.get("mode") == "live"]
        if ev:
            row["eval_usd"] = round(sum(c.get("usd") or 0 for c in ev), 2)
            row["note"] = f"The {usd(row['eval_usd'])} trade on {ev[0]['day'][5:]} was the EVAL that passed the 25K: shown below, not in the funded week $ (MFFU funded starts at $0; the PC tracker counts only funded trades)."
        accts.append(row)

    # ---- bot = backtest (the twins)
    chk = []
    for a in ACCTS:
        exp = []
        start = ctx["starts"].get(a["id"])
        for d in days:
            if start and d < start:
                continue
            tw = twins.get(d, [])
            lit_tw = [t for t in tw if t["bot"] == "LIT"]
            for t in tw:
                if t["bot"] in a["twin"] and not (a["id"] == "rapid" and t["bot"] == "ATLAS" and lit_tw):
                    exp.append({**t, "day": d})
        mine = [c for c in cards if c["acct"] == a["id"] and c.get("mode") == "live"]   # eval-phase included: the twin compare is about the bot, not the stage
        used, rows, missed_usd = set(), [], 0.0
        for t in exp:
            hit = None
            for i, c in enumerate(mine):
                if i in used or c["day"] != t["day"]:
                    continue
                if str(c.get("side") or "").upper() == str(t.get("side") or "").upper() or not c.get("side"):
                    hit = i
                    break
            if hit is not None:
                used.add(hit)
                c = mine[hit]
                rows.append({"day": t["day"], "hm": t["in_hm"], "side": t["side"], "bot": t.get("member") or t["bot"], "twin_r": t.get("r"), "twin_usd": t.get("usd"),
                             "status": "matched", "live_usd": c.get("usd"), "text": f"Taken: live {usd(c.get('usd'))} vs the twin {usd(t.get('usd'))} ({t.get('r'):+.1f}R)." if t.get("r") is not None else "Taken."})
            else:
                g = pick_gap(gaps, a["id"], t["day"], t.get("side"))
                ln = _d(live_notes(reps.get(t["day"]) or {}).get(a["id"]))
                cause = (g or {}).get("cause") or ("no audit row explains it: check the PC log" if t["day"] < today else "not taken yet / no record in the feed")
                if ln.get("gap") and not g:
                    cause = f"audit says {ln['gap'].lower()}"
                if g and str(g.get("kind")).upper() == "NOT A GAP":
                    status, cause = "skipped", str(g.get("cause"))
                elif t["day"] == today and not ctx.get("session_over"):
                    status, cause = "open", "today's session is not over: check again after the close"
                else:
                    status = "missed"
                    missed_usd += _f(t.get("usd")) or 0.0
                rows.append({"day": t["day"], "hm": t["in_hm"], "side": t["side"], "bot": t.get("member") or t["bot"], "twin_r": t.get("r"), "twin_usd": t.get("usd"),
                             "status": status, "live_usd": 0 if status == "missed" else None, "text": f"{'Missed' if status == 'missed' else 'Skipped by design' if status == 'skipped' else 'Pending'}: the twin took this {t['side']} ({usd(t.get('usd'))}, {t.get('r'):+.1f}R at the twin's size); {cause}." if t.get("r") is not None else cause})
        extra = [c for i, c in enumerate(mine) if i not in used]
        for c in extra:
            rows.append({"day": c["day"], "hm": c.get("in_hm"), "side": c.get("side"), "bot": c.get("setup") or c.get("bot"), "twin_r": None, "twin_usd": None,
                         "status": "extra", "live_usd": c.get("usd"), "text": f"Live traded {usd(c.get('usd'))} where the twin did not (a size / fill difference, or the twin file is older than the trade)."})
        nm = sum(1 for r in rows if r["status"] == "matched")
        nx = sum(1 for r in rows if r["status"] == "missed")
        nsk = sum(1 for r in rows if r["status"] == "skipped")
        exp_n = len(exp) - nsk
        chk.append({"id": a["id"], "name": a["name"], "expected": exp_n, "matched": nm, "missed": nx, "extra": len(extra), "skipped": nsk,
                    "missed_usd": round(missed_usd, 2), "rows": rows,
                    "verdict": ("nothing to match: the twin took no trade this week" if not exp_n and not extra else
                                f"all {nm} matched" if nx == 0 and not extra and exp_n else f"{nm} of {exp_n} twin trades taken, {nx} missed")})
    twin_files = sum(1 for d in days if reps[d])
    if twin_files == 0:
        missing.append("backtest twins (nq/replay)")

    # ---- rejected setups
    rej_replay = []
    for d in days:
        for r in rejected_from_replay(reps[d]):
            rej_replay.append({**r, "day": d})
    by_why = {}
    for r in rej_replay:
        w = by_why.setdefault(r["why"], {"why": r["why"], "n": 0, "would": 0.0, "n_would": 0, "wins": 0})
        w["n"] += 1
        if r["would_r"] is not None:
            w["would"] += r["would_r"]
            w["n_would"] += 1
            w["wins"] += 1 if r["would_r"] > 0 else 0
    why_rows = sorted(({**w, "would": round(w["would"], 2)} for w in by_why.values()), key=lambda w: -w["n"])
    live_glog = [g for g in ctx["glog"] if g["day"] in days]
    rej = {"replay_n": len(rej_replay), "why": why_rows, "latest": sorted(rej_replay, key=lambda r: (r["day"], r["hm"]))[-14:][::-1], "live": live_glog[::-1][:24],
           "note": "LIT: the bot's own rules replayed on the PC's bars (a twin): each row is a setup that formed and stopped at a rule. 'would have made' is hindsight, not a promise."}
    if not twin_files:
        rej["note"] = "No twin replay for this week in the repo."

    # ---- order flow lane (paper)
    of_rows = [o for d in days for o in of_from_replay(reps[d])]
    of = {"rows_n": len(of_rows), "taken_n": sum(1 for o in of_rows if o["taken"]), "taken_r": round(sum(o["r"] for o in of_rows if o["taken"]), 2),
          "skipped_n": sum(1 for o in of_rows if not o["taken"]), "skipped_r": round(sum(o["r"] for o in of_rows if not o["taken"]), 2),
          "absorbed_n": sum(1 for o in of_rows if o["absorbed"]), "cap": "1 paper trade a day (the tested first-of-day book)", "paper": True,
          "today": ctx.get("ofp") if cur else None}

    # ---- totals + days
    live_all = [c for c in cards if c.get("mode") == "live" and c.get("phase") != "eval"]
    tot = {"usd": round(sum(r["usd"] for r in accts), 2), "n": sum(r["n"] for r in accts), "wins": sum(r["wins"] for r in accts), "losses": sum(r["losses"] for r in accts),
           "twin_trades": sum(c["expected"] for c in chk), "missed": sum(c["missed"] for c in chk), "setups_rejected": len(rej_replay)}
    traded_days = {c["day"] for c in live_all}
    for x in ds:
        x["traded"] = x["d"] in traded_days
        x["usd"] = round(sum(c.get("usd") or 0 for c in live_all if c["day"] == x["d"]), 2) if x["traded"] else 0
    quiet = tot["twin_trades"] <= 1 and tot["n"] <= 1
    wk = {"key": mon, "label": label_of(mon), "current": cur, "complete": all(x["state"] in ("past", "closed") for x in ds), "days": ds, "totals": tot, "accounts": accts,
          "rejected": rej, "twin": chk, "of": of, "quiet": quiet, "missing": missing}
    if cur:
        wk["waiting"] = ctx.get("waiting")
        wk["clock"] = ctx.get("clock")
        wk["payout"] = ctx.get("payout")
    wk["blitz"] = ctx["blitz"]
    wk["next"] = next_week(mon, ctx)
    wk["grade"] = grade(wk, ctx)
    wk["headline"] = headline(wk)
    return wk


def headline(w: dict) -> str:
    t = w["totals"]
    if t["n"] == 0 and t["twin_trades"] == 0:
        return (f"Quiet week: no trades on any account, and the backtest twins found none either ({t['setups_rejected']} LIT setups formed but each stopped at a rule). "
                "The bots did what they should: wait.")
    if t["n"] == 0:
        return f"No live trades, but the twins took {t['twin_trades']}: {t['missed']} missed. See 'Missed vs backtest'."
    return f"{t['n']} live trade{'s' if t['n'] != 1 else ''}: {t['wins']} won, {t['losses']} lost, {usd(t['usd'])} net across the accounts."


# ------------------------------------------------------------------------------------------------ calendar, grade
def next_week(mon: str, ctx: dict) -> dict:
    nm = (dt.date.fromisoformat(mon) + dt.timedelta(days=7)).isoformat()
    nd = week_days(nm)
    evs = []
    for e in ctx["events"]:
        if nd[0] <= str(e.get("date")) <= nd[-1]:
            evs.append({"date": e["date"], "time": e.get("time"), "title": mask(e.get("title"), 90), "impact": e.get("impact") or "high"})
    ds = [day_status(d, ctx["today"], ctx["now_et"]) for d in nd]
    return {"label": label_of(nm), "days": ds, "events": sorted(evs, key=lambda e: (e["date"], str(e.get("time")))), "source": ctx["events_src"]}


def grade(w: dict, ctx: dict) -> dict:
    t = w["totals"]
    rows = []
    # money
    rows.append({"k": "Money", "e": "🟢" if t["usd"] > 0 else "🟡" if t["usd"] == 0 else "🔴", "v": usd(t["usd"]) if t["n"] else "$0 (no trades)",
                 "t": "Net live $ across the 4 accounts." + (" A flat week is not a loss: the setups did not come." if t["n"] == 0 else "")})
    # bot = backtest
    if t["twin_trades"] == 0 and t["n"] == 0:
        rows.append({"k": "Bot = backtest", "e": "🟢", "v": "nothing to match", "t": "The twin took no trade; the live bots took none. Same."})
    else:
        rows.append({"k": "Bot = backtest", "e": "🔴" if t["missed"] else "🟢", "v": f"{t['twin_trades'] - t['missed']} of {t['twin_trades']} taken",
                     "t": "Every twin trade should show up live." + (f" {t['missed']} did not: fix the cause, not the strategy." if t["missed"] else "")})
    # activity vs the 2-4 / week aim
    n = t["n"]
    rows.append({"k": "Setups", "e": "🟡" if n == 0 else "🟢" if 2 <= n <= 4 else "🟠" if n > 4 else "🟡", "v": f"{n} trade{'s' if n != 1 else ''}, {t['setups_rejected']} rejected",
                 "t": "LIT aims for 2-4 a week. " + ("Almost no LIT setups formed: the rules said wait. Honest, not a bug." if w["quiet"] else "")})
    # risk / process
    if w["current"]:
        ar = ctx.get("armed")
        clk = [c for c in _l(ctx.get("clock")) if c.get("lvl") not in (None, "ok")]
        ok = ar is not False and not clk
        rows.append({"k": "Armed + 7-day clock", "e": "🟢" if ok else "🟠", "v": ("all armed, clocks ok" if ok else "check the clocks / arming"),
                     "t": "MFFU needs a fill every 7 days on each account; the bots must be armed."})
    # order flow
    o = w["of"]
    rows.append({"k": "Order flow (paper)", "e": "🧪", "v": f"{o['taken_n']} taken, {o['taken_r']:+.1f}R" if o["rows_n"] else "no rows",
                 "t": "Practice lane, paper only: nothing here moves money."})
    pts = sum(1 for r in rows if r["e"] == "🟢")
    # process letter: money is NOT in the letter (a quiet week must not look like a fail)
    proc = [r for r in rows if r["k"] in ("Bot = backtest", "Armed + 7-day clock")]
    bad = sum(1 for r in proc if r["e"] == "🔴")
    warn = sum(1 for r in proc if r["e"] == "🟠")
    letter = "A" if bad == 0 and warn == 0 else "B" if bad == 0 else "C" if bad == 1 else "D"
    emoji = {"A": "🏆", "B": "👍", "C": "⚠️", "D": "🚨"}[letter]
    say = {"A": "Clean process: the bots did what the rules say.", "B": "Mostly clean: one thing to check.", "C": "A trade the backtest took was missed: fix the cause.",
           "D": "More than one miss: look at the PC before Monday."}[letter]
    return {"letter": letter, "emoji": emoji, "say": say, "rows": rows, "note": "The letter grades PROCESS (bots = backtest, armed), not the week's $: a quiet week with matching bots is an A."}


# ------------------------------------------------------------------------------------------------ the live-only pieces
def now_pieces(lite, now: int, today: str) -> dict:
    out = {"acct_now": {}, "waiting": None, "clock": None, "payout": None, "armed": None, "ofp": None, "glog": [], "p4": None}
    if not isinstance(lite, dict) or not lite:
        return out
    for a in _l(lite.get("accounts")):
        aid = FEED_TO_ID.get(str(a.get("id")))
        ev = _d(a.get("eval"))
        if aid:
            out["acct_now"][aid] = {"balance": ev.get("balance"), "room": ev.get("room"), "to_target": ev.get("to_target"), "profit": ev.get("profit"),
                                    "week": _f(_d(a.get("pnl")).get("week")), "today": _f(_d(a.get("pnl")).get("today"))}
    at = _d(_d(lite.get("board")).get("atlas"))
    if at:
        out["acct_now"]["atlas25"] = {"balance": at.get("balance"), "room": at.get("room"), "to_target": at.get("to_target"), "profit": at.get("profit"), "week": None, "today": _f(at.get("today_pnl"))}
    wt = []
    for b in _l(_d(lite.get("pc")).get("glance", {}).get("bots") if isinstance(_d(lite.get("pc")).get("glance"), dict) else None):
        bid = str(b.get("id"))
        name = {"lit": "Zlarior (LIT)", "atlas": "ATLAS", "rapid": "Rapid EOD 25K", "b25k_2": "Zlarior 25K #2"}.get(bid, b.get("name"))
        wt.append({"bot": name, "on": bool(b.get("on")), "armed": bool(b.get("armed")), "stage": mask(b.get("stage"), 60) or None, "text": mask(b.get("wait"), 220)})
    win = {"lit": _d(_d(lite.get("board")).get("lit")).get("window"), "atlas": _d(_d(lite.get("board")).get("atlas")).get("window")}
    out["waiting"] = {"bots": wt, "model": mask(lite.get("model_state"), 120), "windows": {k: mask(_d(v).get("text"), 60) for k, v in win.items() if v}}
    ar = lite.get("arm")
    if isinstance(ar, dict):
        out["armed"] = all(bool(x[2]) and bool(x[3]) for x in _l(ar.get("a")) if isinstance(x, list) and len(x) >= 4)
    clk = []
    for k in _l(_d(lite.get("k7")).get("a")):
        nm = {"mffu50k_eval": "Zlarior 50K", "b25k_2": "Zlarior 25K #2", "rapid": "Rapid EOD 25K", "atlas": "ATLAS 25K"}.get(k.get("id"), k.get("nm"))
        clk.append({"name": nm, "last_fill": k.get("lf"), "due": k.get("dl"), "hard": k.get("hard"), "left": k.get("left"), "lvl": k.get("lvl") or "ok", "on": bool(k.get("on"))})
    out["clock"] = clk or None
    # payout progress: ATLAS funded (MFFU shows profit as the balance)
    mf = next((x for x in _l(_d(lite.get("mf")).get("a")) if x.get("id") == "atlas"), None)
    if mf and _d(mf.get("f")):
        try:
            from engine.mffu_view import money_view
            b = _d(_d(lite.get("board")).get("atlas"))
            mv = money_view(b.get("balance"), b.get("floor"), b.get("room"), True, "Builder 25K ATLAS")
        except Exception:  # noqa: BLE001
            mv = {}
        f = mf["f"]
        cp = _f(f.get("cp")) or 0.0
        bd = _f(f.get("bd")) or 0.0
        out["payout"] = {"name": "ATLAS 25K", "profit": cp, "best_day": bd, "days": f.get("cd"), "ask": mv.get("payout_ask") or 1000, "at": mv.get("payout_at") or 2100,
                         "need": mv.get("payout_need"), "first_min_profit": 1350,
                         "best_ratio": round(bd / cp, 2) if cp > 0 else None, "ratio_ok": (bd <= 0.5 * cp) if cp > 0 else False,
                         "note": "Plan: the first payout waits for the max request ($1,000 at $2,100 profit). MFFU rule: the best day must be <= 50% of the cycle's profit, over 2+ traded days."}
    for ln, bot in ((k, k) for k in ("lit", "atlas")):
        for g in _l(_d(lite.get("glog")).get(ln)):
            if isinstance(g, list) and len(g) >= 2:
                out["glog"].append({"day": today, "hm": str(g[0]), "bot": "LIT" if ln == "lit" else "ATLAS", "text": mask(g[1], 200), "src": "live"})
    ofp = _d(lite.get("ofp"))
    if ofp:
        out["ofp"] = {"day": ofp.get("d"), "trades": ofp.get("n"), "open": ofp.get("o"), "r": ofp.get("R"), "line": mask(ofp.get("ln"), 160)}
    out["p4"] = lite.get("p4")
    return out


def gloss_glog(text: str) -> str:
    m = re.search(r"no - (\w+)$", text)
    if m:
        return text[:m.start()].rstrip(": ") + f": no ({REJECT_GLOSS.get(m.group(1), 'rule: ' + m.group(1))})"
    return text


def merge_glog(prev: dict, today_rows: list) -> list:
    seen, out = set(), []
    pool = []
    for w in _l(_d(prev).get("weeks")):
        pool += _l(_d(w.get("rejected")).get("live"))
    pool += today_rows
    for g in pool:
        g = dict(g)
        g["text"] = gloss_glog(re.sub(r"\s+", " ", str(g.get("text") or "")))
        k = (g.get("day"), g.get("hm"), g.get("bot"), g.get("text"))
        if k in seen or not g.get("day"):
            continue
        seen.add(k)
        out.append(g)
    return sorted(out, key=lambda g: (g["day"], g["hm"]))[-200:]


def starts(lite) -> dict:
    """First day each account existed (the twin check starts there): the feed's mf 'sd', else the known dates (rapid Nov 20, 25K #2 Nov 18)."""
    out = {"z25k2": "2026-11-18", "rapid": "2026-11-20"}
    for x in _l(_d(_d(lite).get("mf")).get("a")):
        aid = FEED_TO_ID.get(str(x.get("id")))
        if aid in out and x.get("sd"):
            out[aid] = str(x["sd"])
    return out


def blitz_block(lite) -> dict:
    fw = _d(_j(os.path.join(ROOT, "research", "forward", "forward.json")))
    rules = [{"id": r.get("id"), "n": r.get("n"), "sum": r.get("sum"), "status": r.get("status"), "desc": mask(r.get("desc"), 120)}
             for r in _d(fw.get("rules")).values() if str(r.get("bot")).upper() == "BLITZ"]
    state = None
    for p in _l(_d(_d(lite).get("ck")).get("pl")):
        if isinstance(p, list) and p and p[0] == "BLITZ":
            state = p[2] if len(p) > 2 else p[1]
    ev = sum(int(r.get("n") or 0) for r in rules)
    return {"state": mask(state, 80) if state else "off (hidden, paper only)", "rules": rules, "events": ev, "data_end": fw.get("data_end"),
            "text": ("BLITZ is hidden and paper-only. " + (f"{ev} paper trade{'s' if ev != 1 else ''} scored so far in the forward watch." if rules else "No BLITZ paper data in the repo this week."))}


def load_events():
    p = os.path.join(NQ, "ports.json")
    src = "news_week.json"
    d = _d(_j(p))
    evs = _l(d.get("events"))
    if evs:
        src = "ports.json"
    else:
        d = _d(_j(os.path.join(NQ, "news_week.json")))
        evs = _l(d.get("events"))
    return [e for e in evs if isinstance(e, dict) and e.get("date")], (src if evs else "none")


# ------------------------------------------------------------------------------------------------ build
def build(now: int | None = None, offline: bool = False, lite=None, prev=None) -> dict:
    now = int(now or time.time())
    now_et = et(now)
    today = tday(now) if now_et.hour >= 18 else now_et.strftime("%Y-%m-%d")
    if lite is None:
        lite = feed(offline)
    if prev is None:
        prev = _j(OUT)
    piece = now_pieces(lite, now, today)
    daily, have_daily = daily_rows()
    events, events_src = load_events()
    mon0 = monday_of(today)
    mons = [(dt.date.fromisoformat(mon0) - dt.timedelta(days=7 * i)).isoformat() for i in range(N_WEEKS)]
    alldays = [d for m in mons for d in week_days(m)]
    ledger = ledger_trades(alldays)
    cards = cards_from_ledger(ledger) if ledger else []
    have = {(c["acct"], c["day"], c.get("in_t")) for c in cards}
    for c in cards_from_feed(lite):
        if (c["acct"], c["day"], c.get("in_t")) not in have and not any(x["acct"] == c["acct"] and x["day"] == c["day"] and abs((x.get("usd") or 0) - (c.get("usd") or 0)) < 1 for x in cards):
            cards.append(c)
    session_over = now_et.hour * 60 + now_et.minute >= 16 * 60 or now_et.weekday() >= 5
    ctx = {"today": today, "now_et": now_et, "cards": cards, "daily": daily, "gaps": missed_causes(), "events": events, "events_src": events_src,
           "starts": starts(lite), "glog": merge_glog(prev, piece["glog"]), "blitz": blitz_block(lite), "session_over": session_over, **{k: piece[k] for k in ("acct_now", "waiting", "clock", "payout", "armed", "ofp")}}
    weeks = [week_block(m, ctx) for m in mons]
    miss = []
    if not (isinstance(lite, dict) and lite):
        miss.append("live feed (offline or unreachable: balances, waiting-for, 7-day clock and payout come from it)")
    if not have_daily:
        miss.append("research/livegap/daily.json (live trades per day)")
    if not ledger:
        miss.append("PC ledgers (per-trade fills; older trades are cards built from the twin, marked)")
    if events_src == "none":
        miss.append("news calendar")
    doc = {"v": 1, "built": et(now).strftime("%Y-%m-%d %H:%M ET"), "built_t": now, "today": today,
           "feed_t": (lite or {}).get("t") if isinstance(lite, dict) else None,
           "sources": {"feed": bool(isinstance(lite, dict) and lite), "daily": have_daily, "ledger": bool(ledger), "events": events_src, "missing": miss},
           "weeks": weeks}
    return doc


def write(doc: dict, path: str = OUT) -> str:
    s = json.dumps(doc, separators=(",", ":"), ensure_ascii=False)
    if len(s.encode("utf-8")) > MAX_BYTES:                       # keep the file small: drop the oldest weeks' long lists first
        for w in doc["weeks"][::-1]:
            w["rejected"]["latest"] = w["rejected"]["latest"][:6]
            w["rejected"]["live"] = w["rejected"]["live"][:8]
        s = json.dumps(doc, separators=(",", ":"), ensure_ascii=False)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(s)
    os.replace(tmp, path)
    return path


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--now", type=int)
    ap.add_argument("--out", default=OUT)
    a = ap.parse_args(argv)
    doc = build(a.now, a.offline)
    write(doc, a.out)
    w = doc["weeks"][0]
    print(f"week_review: {w['label']}: {w['headline']} | grade {w['grade']['letter']} {w['grade']['emoji']} | missing: {', '.join(doc['sources']['missing']) or 'none'} -> {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
