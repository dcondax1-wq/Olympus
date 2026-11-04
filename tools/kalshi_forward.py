#!/usr/bin/env python3
"""Kalshi FORWARD PAPER TALLY for the rule sets A / B / C (research only: reads the public feed, never an order, no key, no Kalshi call).

The what-if card (tools/kalshi_whatif.py) replays PAST bets, with a band picked after looking at them. This is the honest test: it freezes a
start date (the feed's own time at its first run, kept in its own state file) and from then on applies each rule set to every NEW settled bet,
once, in the order they were placed. Nothing that was placed before the start is ever counted, so there is no look-ahead.

    python tools/kalshi_forward.py                        # fetch the public feed, update kalshicity/forward.json (+ forward_state.json, forward_card.json)
    python tools/kalshi_forward.py --feed kalshi.json     # a local copy (tests, offline)
    python tools/kalshi_forward.py --out state/forward.json     # the workflow's folder (state and card are written next to it)

Rule sets (same as the what-if card; the 90-95c band was picked after the fact, and the result says so):
    as is  every bet as the bot placed it
    A      skip every bet priced 90-95c
    B      only bets at 95c and up, each shrunk to 2% of the balance
    C      skip 90-95c, and shrink every other bet to 2% of the balance
A shrunk bet counts the bot's real net P&L (Kalshi's fee already in it) times min(1, cap / the bet's cost); cap = 2% of the feed's balance when the bet is
first seen settled. A feed only carries its last 40 bets: if more than that settled between two runs, `gaps` counts it and the tally says it may be incomplete.

Files (all in the --out folder, all new, nothing else is touched):
  forward.json        what the Kalshi page's "Forward test" strip and the city read: start date, bets so far, per set net $ vs the bot as it is
  forward_state.json  the tally's own memory: the frozen start, the bets already counted, the running totals (do not edit)
  forward_card.json   a Jarvis-style card (v 1, status, 3 kpis, 3 lines, t, open, theme)
Exit codes: 0 ok (also "no new bets": nothing is rewritten), 2 feed unreachable (nothing is rewritten: stale beats invented).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FEED_URL = "https://raw.githubusercontent.com/demetrades2000-coder/kalshi-feed/main/kalshi.json"
OUT = os.path.join(ROOT, "tools", "web_public", "kalshicity", "forward.json")
CAP = 0.02
MIN_BETS = 30                    # under this many new bets the tally says "collecting" and names no leader
FEED_TRADES = 40                 # how many bets the feed carries one by one
KEEP_SEEN = 300
NAMES = {"asis": "The bot as it is", "A": "A · skip the 90–95¢ band", "B": "B · only 95¢ and up, 2% bets", "C": "C · skip 90–95¢, 2% bets"}


def usd(x, sign=False):
    v = round(abs(x) + 1e-9, 2)
    return ("−" if x < 0 and v else "+" if sign and v else "") + f"${v:,.2f}"


def in_leak(p):
    return 0.9 - 1e-9 <= p < 0.95 - 1e-9


def apply_rule(rule, p, cost, cap):
    """(counted?, the share of the real P&L that counts)"""
    shrink = min(1.0, cap / cost) if cost > 0 else 1.0
    if rule == "asis":
        return True, 1.0
    if rule == "A":
        return (not in_leak(p)), 1.0
    if rule == "B":
        return p >= 0.95 - 1e-9, shrink
    return (not in_leak(p)), shrink


def blank_set():
    return {"bets": 0, "net": 0.0, "wins": 0, "losses": 0, "eq": 0.0, "peak": 0.0, "max_dd": 0.0}


def new_state(start_t):
    day = dt.datetime.fromtimestamp(start_t, dt.timezone.utc).strftime("%Y-%m-%d")
    return {"v": 1, "start_t": start_t, "start_day": day, "seen": [], "last_t": None, "gaps": 0, "sets": {k: blank_set() for k in NAMES}}


def key_of(t):
    return f"{t.get('ticker')}|{t.get('t')}|{t.get('side')}"


def settled_buys(feed):
    out = []
    for t in feed.get("trades") or []:
        if not isinstance(t, dict) or t.get("action") == "sell":
            continue
        p, n, pnl, ts = t.get("price"), t.get("contracts"), t.get("pnl"), t.get("t")
        if not all(isinstance(x, (int, float)) for x in (p, n, pnl, ts)) or isinstance(pnl, bool) or not 0 < p <= 1.0001 or n <= 0:
            continue
        out.append(t)
    return sorted(out, key=lambda t: (t["t"], key_of(t)))


def update(state, feed):
    """Fold the feed's new settled bets into the state. Returns the number of NEW bets counted (0 = nothing changed)."""
    all_t = [t["t"] for t in feed.get("trades") or [] if isinstance(t, dict) and isinstance(t.get("t"), (int, float))]
    # a full window of bets that are all newer than the newest one we have ever seen: some bets were never in a feed we read
    if state["last_t"] is not None and len(all_t) >= FEED_TRADES and min(all_t) > state["last_t"]:
        state["gaps"] += 1
    bal = feed.get("balance")
    cap = CAP * bal if isinstance(bal, (int, float)) and bal > 0 else None
    seen, added = set(state["seen"]), 0
    for t in settled_buys(feed):
        k = key_of(t)
        if k in seen:
            continue
        seen.add(k)
        state["seen"].append(k)
        if t["t"] < state["start_t"] or cap is None:
            continue                                  # placed before the frozen start (no look-ahead), or no balance to size against
        cost = t["contracts"] * t["price"]
        for rule in NAMES:
            take, share = apply_rule(rule, t["price"], cost, cap)
            if not take:
                continue
            s, x = state["sets"][rule], t["pnl"] * share
            s["bets"] += 1
            s["net"] = round(s["net"] + x, 6)
            s["wins"] += x > 0.005
            s["losses"] += x < -0.005
            s["eq"] += x
            s["peak"] = max(s["peak"], s["eq"])
            s["max_dd"] = max(s["max_dd"], s["peak"] - s["eq"])
        added += 1
    sett_t = [t["t"] for t in settled_buys(feed)]                  # the newest SETTLED bet seen (an open bet settles later, with an older time)
    if sett_t:
        state["last_t"] = max(max(sett_t), state["last_t"] or 0)
    state["seen"] = state["seen"][-KEEP_SEEN:]
    return added


def report(state, feed):
    base = state["sets"]["asis"]
    sets = []
    for k, name in NAMES.items():
        s = state["sets"][k]
        sets.append({"id": k, "name": name, "bets": s["bets"], "net": round(s["net"], 2), "wins": s["wins"], "losses": s["losses"], "max_dd": round(s["max_dd"], 2),
                     "vs_asis": round(s["net"] - base["net"], 2)})
    n = base["bets"]
    lead = None
    if n >= MIN_BETS:
        best = max(sets[1:], key=lambda x: x["net"])
        lead = best["id"] if best["net"] > sets[0]["net"] else None
    out = {"v": 1, "kind": "kalshi-forward", "t": feed.get("t"), "start_t": state["start_t"], "start_day": state["start_day"], "bets": n, "min_bets": MIN_BETS,
           "collecting": n < MIN_BETS, "sets": sets, "leader": lead, "gaps": state["gaps"],
           "flags": {"band_picked_after_the_fact": True, "no_look_ahead": True, "size_cap_scales_real_pnl": True, "may_be_incomplete": state["gaps"] > 0},
           "label": "A forward paper tally: only bets placed after the start date are counted, once each. Suggestions only: nothing here places or changes a bet."}
    out["text"] = headline(out)
    return out


def headline(r):
    n, sets = r["bets"], {x["id"]: x for x in r["sets"]}
    if n == 0:
        return f"Collecting: 0 bets so far (started {r['start_day']}). The tally counts only new bets."
    if r["collecting"]:
        return f"Collecting: {n} bet{'' if n == 1 else 's'} so far (need {r['min_bets']} to judge). The bot is at {usd(sets['asis']['net'], True)}."
    if r["leader"]:
        s = sets[r["leader"]]
        return f"Over {n} new bets {s['name'].split(' · ')[0]} is {usd(s['vs_asis'], True)} ahead of the bot ({usd(s['net'], True)} against {usd(sets['asis']['net'], True)})."
    return f"Over {n} new bets none of A, B, C beats the bot ({usd(sets['asis']['net'], True)}) yet."


def card(r):
    sets = {x["id"]: x for x in r["sets"]}
    n = r["bets"]
    best = max(r["sets"][1:], key=lambda x: x["net"])
    return {"v": 1, "name": "Kalshi forward test", "status": {"level": "off" if n == 0 else "ok" if not r["collecting"] else "warn", "label": ("Collecting: %d bets" % n)[:48] if r["collecting"] else "Forward tally running"},
            "kpis": [{"label": "New bets", "value": str(n)}, {"label": "Bot", "value": usd(sets["asis"]["net"], True)},
                     {"label": "Best rule " + best["id"], "value": usd(best["net"], True)}],
            "lines": [r["text"].replace("&", "and")[:120], "A backtest forward in time: suggestions only.", "The 90-95c band was picked after looking."],
            "t": int(r.get("t") or 0), "open": "#", "theme": "#010a07"}


def load(src):
    if src and os.path.isfile(src):
        return json.load(open(src, encoding="utf-8"))
    req = urllib.request.Request(src or FEED_URL, headers={"User-Agent": "kalshi-forward/1"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def dump(path, obj):
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(obj, fh, indent=1, ensure_ascii=False, sort_keys=True)
        fh.write("\n")


def main(argv=None, now=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--feed", help="path or URL of kalshi.json (default: the public feed)")
    ap.add_argument("--out", default=OUT, help="forward.json; forward_state.json and forward_card.json are written beside it")
    a = ap.parse_args(argv)
    try:
        feed = load(a.feed)
        if not isinstance(feed, dict) or feed.get("kind") != "kalshi":
            raise ValueError("not a kalshi.json")
    except Exception as e:                                             # noqa: BLE001 - stale beats invented: nothing is rewritten
        print(f"feed unreachable ({e.__class__.__name__}): nothing changed")
        return 2
    folder = os.path.dirname(os.path.abspath(a.out))
    spath, cpath = os.path.join(folder, "forward_state.json"), os.path.join(folder, "forward_card.json")
    state, first = None, False
    if os.path.isfile(spath):
        try:
            state = json.load(open(spath, encoding="utf-8"))
            assert state["v"] == 1 and set(state["sets"]) == set(NAMES)
        except Exception:                                              # noqa: BLE001 - a broken state is never guessed at
            print("forward_state.json is not readable: nothing changed (delete it to start a new tally)")
            return 2
    if state is None and os.path.isfile(a.out):                        # a tally without its memory: never restart it silently (the start date is frozen)
        print("forward.json exists but forward_state.json is missing: nothing changed (restore the state, or delete both to start over)")
        return 2
    if state is None:
        start = feed.get("t") if isinstance(feed.get("t"), (int, float)) else (now if now is not None else dt.datetime.now(dt.timezone.utc).timestamp())
        state, first = new_state(int(start)), True
    added = update(state, feed)
    if not first and added == 0 and os.path.isfile(a.out) and state["gaps"] == json.load(open(a.out, encoding="utf-8")).get("gaps"):
        print("no new bets: nothing changed")
        return 0
    rep = report(state, feed)
    os.makedirs(folder, exist_ok=True)
    dump(spath, state)
    dump(a.out, rep)
    dump(cpath, card(rep))
    print(("started " + state["start_day"] + ": " if first else "") + rep["text"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
