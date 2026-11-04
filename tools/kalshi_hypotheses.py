#!/usr/bin/env python3
"""KALSHI CITY edge-hypothesis tracker (OLYMPUS, 2026-11-04). READ ONLY, paper only: no Kalshi call, no key, no order.

The research (tools/kalshi_research.py, research/kalshi/edge_tables.json) names ideas that might turn the bot's loss into a profit. This module keeps
a PAPER SCORE for each of them, re-measured every time the learning engine (tools/kalshi_edges.py) runs, so the city can show them learning:

  hypotheses.json   one record per idea: the rule in plain words, the paper result LOOKING BACK (all the bets the engine has seen; the rule was
                    picked after seeing them, so this alone proves nothing) and the paper result LIVE (only bets that came after the idea was
                    registered: the real test), the verdict, the sample it still needs, a daily history, and an append-only plain-words log.

A filter rule ("only buy 95c and up") removes some of the bot's bets. Its paper gain is minus what the removed bets made: if they lost $268 the
rule would have added $268. A fee rule (maker orders) prices the fee saving and says it needs data it does not have. A size rule (smaller bets)
scales every bet and re-computes the risk of ruin. Verdicts use the engine's own tests (Wilson / z against the market's odds, n >= 30):
  COLLECTING   fewer than 30 bets the rule would skip: nothing to say yet
  PROMISING    the skipped bets lose, not proven beyond luck (or proven, but only looking back)
  WORKS        the skipped bets are proven losers in LIVE bets (z <= -1.645 over 30+ live bets)
  NO HELP      the skipped bets made money: the rule would have cost money
  NEEDS DATA   the test needs numbers the bot does not log (bid / ask, spot price)
  SAFER        a size rule that takes the chance of losing half to 10% or less
Looking back can never say WORKS: that word needs live bets.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

try:
    from tools import kalshi_edges as E
except ImportError:                                   # run as a script from tools/
    import kalshi_edges as E

VERSION = 1
MIN_N = E.MIN_N
Z_SIG = E.Z_SIG
TAKER = 0.07
MAKER = 0.0175
SIZE_CAP = 0.05                                       # the size rule: no bet above a twentieth of the bankroll
HOURS_SKIP = ("00-04 ET", "04-08 ET")                 # the thin overnight books (the engine's hour blocks)
LOW_BANDS = ["<20c", "20-40c", "40-60c", "60-80c", "80-90c", "90-95c"]
MAX_HIST = 90
MAX_LOG_PER_RUN = 24
WORD_STATUS = {"COLLECTING": "NEW", "NEEDS DATA": "NEW", "PROMISING": "HOLDING", "WORKS": "GROWING", "NO HELP": "DEAD", "SAFER": "GROWING"}
ENDING = {"COLLECTING": "too few bets to say", "NEEDS DATA": "needs data the bot does not log yet", "PROMISING": "looks good, not proven",
          "WORKS": "it works so far", "NO HELP": "no help, it would have cost money", "SAFER": "much safer"}

# one record per idea. skip = the bets the rule would NOT take. covers = the real edges (engine ids) it would plug.
SPECS = [
    {"id": "leak9095", "name": "Stop buying at 90-95c", "short": "90-95C LEAK", "idea": 1, "kind": "filter", "src": "feed", "fam": "band", "skip": ["90-95c"], "needed": 400,
     "rule": "Never buy a contract priced 90c to 95c. In the bot's totals that band is the biggest leak.", "covers": [E.edge_id(("*", "*", "*", "90-95c", "*"))]},
    {"id": "floor95", "name": "Only buy 95c and up", "short": "95C FLOOR", "idea": 1, "kind": "filter", "src": "feed", "fam": "band", "skip": LOW_BANDS, "needed": 600,
     "rule": "Skip every bet priced under 95c. Only the 95c-and-up pocket pays after fees.", "covers": [E.edge_id(("*", "*", "*", b, "*")) for b in LOW_BANDS]},
    {"id": "xrp", "name": "Drop XRP", "short": "DROP XRP", "idea": 4, "kind": "filter", "src": "feed", "fam": "market", "skip": ["XRP"], "needed": 300,
     "rule": "Stop betting on XRP. It loses while Bitcoin wins (the alt coins are noisier and move together).", "covers": [E.edge_id(("*", "XRP", "*", "*", "*"))]},
    {"id": "window1", "name": "One bet per 15-minute window", "short": "ONE PER WINDOW", "idea": 4, "kind": "filter", "src": "ledger", "needed": 500,
     "rule": "When several coins are bought in the same window, keep only the safest (highest priced) one. They move together, so they are really one bet.", "covers": []},
    {"id": "hours", "name": "Skip the thin overnight hours", "short": "NIGHT FILTER", "idea": 5, "kind": "filter", "src": "ledger", "needed": 800,
     "rule": "No bets from midnight to 8 am New York time, when the order books are thin.", "covers": []},
    {"id": "maker", "name": "Rest orders instead of paying the fee", "short": "MAKER ORDERS", "idea": 2, "kind": "fee", "src": "feed", "needed": 300,
     "rule": "Post a resting order one cent better instead of taking the price. The maker fee is a quarter of the taker fee, but you only get filled when the price moves against you.", "covers": []},
    {"id": "strike", "name": "Skip bets too close to the strike", "short": "STRIKE GAP", "idea": 3, "kind": "data", "src": "none", "needed": 400,
     "rule": "Skip the hourly Bitcoin late favourite when the price is within a few minutes of volatility of the strike. Needs free public spot candles joined to the bets.", "covers": []},
    {"id": "small", "name": "Bet smaller", "short": "SMALL BETS", "idea": 0, "kind": "size", "src": "feed", "needed": 0,
     "rule": f"Never stake more than {round(SIZE_CAP * 100)}% of the bankroll on one bet. Same bets, smaller size.", "covers": []},
]
SPEC_BY_ID = {s["id"]: s for s in SPECS}


def usd(x, d=2):
    return f"{'-' if x < 0 else ''}${abs(x):,.{d}f}"


def sgn(x, d=2):
    return f"{'-' if x < 0 else '+'}${abs(x):,.{d}f}"


def fee_taker(c, p):
    return TAKER * c * p * (1 - p)


# ------------------------------------------------------------------------------------------------ the stats of one set of bets
def mk(n, wins, pnl, staked, sp, sv, fees=0.0):
    """Count, wins, $ -> the numbers of one set of bets. sp = sum of the entry prices, sv = sum of p (1 - p): the market's own odds."""
    if not n:
        return {"n": 0, "wins": 0, "pnl": 0.0, "staked": 0.0, "w": None, "p": None, "ev": None, "z": None, "sig": "", "fees": 0.0}
    z = pv = None
    if sp is not None and sv and sv > 0:
        z, pv = E.z_test(wins, sp, sv)
    return {"n": int(n), "wins": int(wins), "pnl": E.r4(pnl), "staked": E.r4(staked or 0.0), "w": E.r4(wins / n), "p": E.r4(sp / n) if sp is not None else None,
            "ev": E.r4(pnl / staked) if staked else None, "z": E.r4(z), "sig": "" if z is None else ("+" if z >= Z_SIG else "-" if z <= -Z_SIG else ""), "fees": E.r4(fees)}


def from_trades(trs):
    a = E.Acc()
    fees = 0.0
    for t in trs:
        a.add(t)
        if E.outcome(t["pnl"]) != 0:
            fees += fee_taker(t["c"], t["p"])
    return mk(a.n, a.wins, a.pnl, a.staked, a.sp, a.sv, fees)


def from_rows(rows):
    """rows = [(n, wins, pnl, staked, p)] of the feed's own totals (a band or a market): sums, with the band's mean price as the market's odds."""
    n = sum(r[0] for r in rows)
    if not n:
        return mk(0, 0, 0, 0, 0, 0)
    wins, pnl = sum(r[1] for r in rows), sum(r[2] for r in rows)
    staked = sum(r[3] for r in rows if r[3]) or None
    have_p = all(r[4] is not None for r in rows if r[0])
    sp = sum(r[0] * r[4] for r in rows if r[0]) if have_p else None
    sv = sum(r[0] * r[4] * (1 - r[4]) for r in rows if r[0]) if have_p else None
    fees = sum(TAKER * r[3] * (1 - r[4]) for r in rows if r[3] and r[4] is not None)
    return mk(n, wins, pnl, staked, sp, sv, fees)


# ------------------------------------------------------------------------------------------------ the rules
def skip_window1(trs):
    groups = {}
    for t in trs:
        key = t["k"].split("-")[1] if "-" in t["k"] else t["k"]
        groups.setdefault(key, []).append(t)
    out = []
    for g in groups.values():
        if len(g) > 1:
            keep = min(g, key=lambda t: (-t["p"], t["t"], t["k"]))
            out += [t for t in g if t is not keep]
    return out


def skip_hours(trs):
    return [t for t in trs if E.hour_block(t["t"]) in HOURS_SKIP]


def feed_rows(snap, base, fam, names, pmap):
    """The feed totals of `names`: all-time (base None) or what came after the registration snapshot (the difference, never below 0)."""
    rows = []
    for nm in names:
        cur = (snap.get(fam) or {}).get(nm)
        if not cur:
            continue
        old = ((base or {}).get(fam) or {}).get(nm) if base is not None else None
        if base is not None and old is None:
            old = [0, 0, 0.0, 0.0 if cur[3] is not None else None]
        v = [max(0, cur[0] - old[0]), max(0, cur[1] - old[1]), cur[2] - old[2], (cur[3] - old[3]) if cur[3] is not None and old[3] is not None else cur[3]] if old else list(cur)
        if v[0] <= 0:
            continue
        rows.append((v[0], v[1], v[2], v[3], pmap.get((fam, nm))))
    return rows


def judge(sk):
    """The verdict word from the stats of the bets a rule would skip."""
    if sk["n"] < MIN_N:
        return "COLLECTING"
    if sk["pnl"] < 0 and sk["sig"] == "-":
        return "WORKS"
    if sk["pnl"] < 0:
        return "PROMISING"
    return "NO HELP"


def evaluate(spec, ctx, live):
    """-> {n_all, n_skip, gain, pnl_skip, ...} for the whole record (live False) or only what came after the registration (live True)."""
    reg = ctx["reg"][spec["id"]]
    kind = spec["kind"]
    if kind == "filter" and spec["src"] == "feed":
        base = reg["snap"] if live else None
        fam = spec["fam"]
        names = list((ctx["snap"].get(fam) or {}).keys())
        sk = from_rows(feed_rows(ctx["snap"], base, fam, spec["skip"], ctx["pmap"]))
        al = from_rows(feed_rows(ctx["snap"], base, fam, names, ctx["pmap"]))
    elif kind == "filter":
        trs = [t for t in ctx["trades"] if (t["t"] > reg["t"] if live else True)]
        skipped = skip_window1(trs) if spec["id"] == "window1" else skip_hours(trs)
        sk, al = from_trades(skipped), from_trades(trs)
    elif kind == "fee":
        if live:
            trs = [t for t in ctx["trades"] if t["t"] > reg["t"]]
            fees = sum(fee_taker(t["c"], t["p"]) for t in trs if E.outcome(t["pnl"]) != 0)
            al = from_trades(trs)
        else:
            al = from_rows(feed_rows(ctx["snap"], None, "band", list((ctx["snap"].get("band") or {}).keys()), ctx["pmap"]))
            fees = al["fees"]
        saved = (1 - MAKER / TAKER) * fees
        return {"n_all": al["n"], "n_skip": 0, "gain": E.r4(saved), "pnl_skip": 0.0, "fees": E.r4(fees), "saved": E.r4(saved), "w": None, "ev": None, "z": None, "sig": ""}
    elif kind == "size":
        bk = ctx["book"]
        frac = bk.get("stake_frac")
        scale = min(1.0, SIZE_CAP / frac) if frac else 1.0
        if live:
            trs = [t for t in ctx["trades"] if t["t"] > reg["t"]]
            total, n = sum(t["pnl"] for t in trs), len(trs)
        else:
            total, n = bk.get("total") or 0.0, bk.get("bets_total") or 0
        out = {"n_all": n, "n_skip": 0, "gain": E.r4(total * (scale - 1.0)) or 0.0, "pnl_skip": 0.0, "scale": E.r4(scale), "w": None, "ev": None, "z": None, "sig": "",
               "total": E.r4(total), "after": E.r4(total * scale)}
        if not live:
            w, p = bk.get("w"), bk.get("p")
            out["ruin_now"] = bk.get("ruin_now")
            out["ruin_after"] = E.r4(E.ruin_half(w, p, min(frac, SIZE_CAP))) if (w and p and frac) else None
            out["worst_day"] = bk.get("worst_day")
            out["worst_day_after"] = E.r4(bk["worst_day"] * scale) if bk.get("worst_day") is not None else None
        return out
    else:                                                # data: nothing can be tested yet
        return {"n_all": 0, "n_skip": 0, "gain": 0.0, "pnl_skip": 0.0, "w": None, "ev": None, "z": None, "sig": ""}
    return {"n_all": al["n"], "n_skip": sk["n"], "gain": E.r4(-sk["pnl"]) or 0.0, "pnl_skip": sk["pnl"], "w": sk["w"], "p": sk["p"], "ev": sk["ev"], "z": sk["z"], "sig": sk["sig"],
            "fees_skip": sk["fees"], "staked_skip": sk["staked"], "pnl_all": al["pnl"], "judge": judge(sk)}


def verdict_of(spec, back, live):
    """-> (word, judged_live, plain-words sentence). Looking back alone can say PROMISING at best."""
    kind = spec["kind"]
    if kind == "data":
        return "NEEDS DATA", False, "Cannot be tested yet: it needs free public spot candles joined to the bot's bets, which the feed does not carry."
    if kind == "fee":
        return ("NEEDS DATA", False, f"Fees took about {usd(back['fees'])}. Resting orders pay a quarter of that fee, up to {usd(back['saved'])} saved if every order filled, "
                "but they only fill when the price moves against you. The bot does not log bid and ask, so this cannot be proven yet.")
    if kind == "size":
        ra, rn = back.get("ruin_after"), back.get("ruin_now")
        word = "SAFER" if ra is not None and ra <= 0.10 else "PROMISING"
        txt = f"At {round(SIZE_CAP * 100)}% of the bankroll the same bets would have made {usd(back['after'])} instead of {usd(back['total'])}"
        if back.get("worst_day_after") is not None:
            txt += f", and the worst day would have been {usd(back['worst_day_after'])} instead of {usd(back['worst_day'])}"
        if ra is not None and ra >= 0.5:
            txt += ". But the bot has no edge after fees, so smaller bets only slow the bleed: the chance of losing half stays near 100%."
        elif ra is not None:
            txt += f"; the chance of losing half falls from {round((rn or 0) * 100)}% to {round(ra * 100)}%."
        else:
            txt += "."
        return word, False, txt
    if live["n_skip"] >= MIN_N:
        word, jl = live["judge"], True
    else:
        word, jl = back["judge"], False
        if word == "WORKS":
            word = "PROMISING"
    n, g = back["n_skip"], back["gain"]
    if word == "COLLECTING":
        txt = f"Only {n} past bets would be skipped so far. {MIN_N} are needed before it says anything."
    elif word == "NO HELP":
        txt = f"The {back['n_skip']} bets it would skip made {usd(back['pnl_skip'])}: the rule would have cost money."
    else:
        proof = "Beyond luck, but the rule was picked after seeing the result." if back["sig"] == "-" else "Not yet proven beyond luck."
        txt = f"The {n} bets it would skip lost {usd(abs(back['pnl_skip']))} looking back. {proof}"
    if not jl and word != "COLLECTING":
        txt += f" Live: {live['n_skip']} of the {MIN_N} bets needed so far."
    if jl:
        txt += f" Live: {live['n_skip']} bets, {sgn(live['gain'])}."
    return word, jl, txt


def line_of(spec, word, back, live, jl):
    """The one-line lesson: 'Tested X: 14 paper bets, +$3, fees ate it'."""
    if spec["kind"] in ("filter",):
        n, g = (live["n_skip"], live["gain"]) if jl else (back["n_skip"], back["gain"])
        fee_note = ""
        src = live if jl else back
        if word in ("PROMISING", "COLLECTING", "NO HELP") and src.get("pnl_skip", 0) < 0 and src.get("pnl_skip", 0) + (src.get("fees_skip") or 0) >= 0:
            fee_note = ", fees ate it"
        return f"Tested '{spec['name']}': {n} paper bets, {sgn(g)}{fee_note}, {ENDING[word]}{'' if jl else ' (looking back)'}"
    if spec["kind"] == "fee":
        return f"Tested '{spec['name']}': fees ate {usd(back['fees'])}, up to {usd(back['saved'])} could be saved, {ENDING[word]}"
    if spec["kind"] == "size":
        wd, wa = back.get("worst_day"), back.get("worst_day_after")
        head = f"Tested '{spec['name']}': {back['n_all']} paper bets, {sgn(back['gain'])}"
        if wd is not None and wa is not None:
            head += f", worst day {usd(wd, 0)} to {usd(wa, 0)}"
        return head + (", it only slows the bleed" if (back.get("ruin_after") or 0) >= 0.5 else f", {ENDING[word]}")
    return f"Tested '{spec['name']}': {ENDING[word]}"


# ------------------------------------------------------------------------------------------------ the run
def pair_of(edges, hyps):
    """Best edge so far / Worst leak, in dollars: the biggest proven winner and loser among the single-slice edges (30+ bets), and the idea that would plug the leak."""
    real = [e for e in edges if e["size"] == 1 and not e["small"] and e["pnl"] is not None]
    best = max((e for e in real if e["pnl"] > 0), key=lambda e: e["pnl"], default=None)
    worst = min((e for e in real if e["pnl"] < 0), key=lambda e: e["pnl"], default=None)

    def pack(e):
        if e is None:
            return None
        fix = next((h["id"] for h in sorted(hyps, key=lambda h: len(SPEC_BY_ID[h["id"]]["covers"])) if e["id"] in SPEC_BY_ID[h["id"]]["covers"]), None)
        d = e["dims"]
        label = f"Buying at {d[3]}" if d[3] != "*" else f"{d[1]} bets" if d[1] != "*" else e["label"]
        return {"id": e["id"], "label": label, "pnl": E.r4(e["pnl"]), "n": e["n"], "ev": e["ev"], "src": e["src"], "fix": fix}
    return {"best": pack(best), "worst": pack(worst)}


def track(ledger, edges, book, now, prev=None, specs=None):
    """One refresh of every idea. ledger = the engine's memory (trades + snapshots), edges/book = this run's, prev = the last hypotheses.json (or None).
    Returns the new hypotheses.json document; its log only ever grows."""
    specs = specs or SPECS
    prev = prev if isinstance(prev, dict) and isinstance(prev.get("hyps"), list) else {}
    prev_h = {h.get("id"): h for h in prev["hyps"]} if prev else {}
    prev_log = prev.get("log") if isinstance(prev.get("log"), list) else []
    snap = ledger["snaps"][-1] if ledger.get("snaps") else {}
    trades = ledger.get("trades") or []
    last_t = max((t["t"] for t in trades), default=0)
    pmap = {}
    for e in edges:
        if e["size"] == 1 and e["p"] is not None:             # the mean entry price of the slice: the market's own odds for its bets
            for fam, i in (("strategy", 0), ("market", 1), ("band", 3)):
                if e["dims"][i] != "*":
                    pmap[(fam, e["dims"][i])] = e["p"]
    day = E.et_date(now)
    reg = {}
    for s in specs:
        r = (prev_h.get(s["id"]) or {}).get("reg")
        if not (isinstance(r, dict) and "snap" in r and "t" in r):
            r = {"day": day, "t": last_t, "snap": {f: {k: list(v) for k, v in (snap.get(f) or {}).items()} for f in ("band", "market", "strategy")}}
        reg[s["id"]] = r
    ctx = {"snap": snap, "trades": trades, "pmap": pmap, "book": book, "reg": reg}
    seen = {x.get("ek") for x in prev_log}
    entries, hyps = [], []
    for s in specs:
        back, live = evaluate(s, ctx, False), evaluate(s, ctx, True)
        word, jl, txt = verdict_of(s, back, live)
        old = prev_h.get(s["id"]) or {}
        hist = [list(x) for x in (old.get("hist") or []) if isinstance(x, list) and len(x) >= 4 and x[0] != day]
        hist.append([day, back["gain"], live["gain"], live["n_skip"] if s["kind"] == "filter" else live["n_all"]])
        line = line_of(s, word, back, live, jl)
        hyps.append({"id": s["id"], "name": s["name"], "short": s["short"], "idea": s["idea"], "kind": s["kind"], "src": s["src"], "rule": s["rule"], "needed": s["needed"],
                     "covers": s["covers"], "word": word, "status": WORD_STATUS[word], "judged_live": jl, "verdict": txt, "line": line, "back": back, "live": live,
                     "reg": reg[s["id"]], "hist": hist[-MAX_HIST:]})

        def add(ek, text, kind="tested"):
            if ek in seen or len(entries) >= MAX_LOG_PER_RUN:
                return
            seen.add(ek)
            entries.append({"d": day, "t": int(now), "kind": kind, "id": s["id"], "word": word, "gain": back["gain"] if not jl else live["gain"], "text": text, "ek": ek})
        add(f"{s['id']}|reg", f"Started testing '{s['name']}': {s['rule']}", "started")
        add(f"{s['id']}|word|{word}|{int(jl)}", line, "tested")
        nl = live["n_skip"] if s["kind"] == "filter" else live["n_all"]
        for k in (1, 10, 30, 100, 300):
            if nl >= k:
                add(f"{s['id']}|live|{k}", f"'{s['name']}' has now seen {k}+ live bets: {sgn(live['gain'])} on paper", "live")
    log = prev_log + entries
    pair = pair_of(edges, hyps)
    return {"v": VERSION, "kind": "kalshi-hypotheses", "t": int(now), "day": day, "min_n": MIN_N, "hyps": hyps, "pair": pair,
            "log": log, "about": "Paper scores only. The log is append-only. Looking back (the rule was picked after seeing the bets) can never prove anything; only live bets can."}


def best_line(doc):
    p = doc.get("pair") or {}
    b, w = p.get("best"), p.get("worst")
    return (f"Best edge so far: {b['label']} {sgn(b['pnl'])}" if b else "Best edge so far: none proven yet") + " · " + (f"Worst leak: {w['label']} {sgn(w['pnl'])}" if w else "Worst leak: none proven yet")


def main(argv=None):
    ap = argparse.ArgumentParser(description="Kalshi City hypothesis tracker (paper, read only). Normally run by tools/kalshi_edges.py.")
    ap.add_argument("--out", default=E.OUT_DEFAULT)
    a = ap.parse_args(argv)
    ledger = E.read_json(os.path.join(a.out, "ledger.json"), None)
    edges_doc = E.read_json(os.path.join(a.out, "edges.json"), None)
    if not ledger or not edges_doc:
        print("kalshi_hypotheses: no ledger.json / edges.json in --out", file=sys.stderr)
        return 2
    prev = E.read_json(os.path.join(a.out, "hypotheses.json"), None)
    doc = track(ledger, edges_doc["edges"], edges_doc["book"], edges_doc["t"], prev)
    E.write_json(os.path.join(a.out, "hypotheses.json"), doc)
    print("kalshi_hypotheses:", best_line(doc))
    return 0


if __name__ == "__main__":
    sys.exit(main())
