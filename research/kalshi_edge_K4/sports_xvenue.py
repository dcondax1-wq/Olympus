#!/usr/bin/env python3
"""K4 idea 1/2 (sports): Kalshi game-winner markets vs Polymarket moneylines on the same game (NBA, NFL, NHL, MLB).

Match: Kalshi event KX<L>GAME-26NOV15OKCSAC -> Polymarket event slug <l>-okc-sac-2026-11-15 (every split of the team
codes is tried); the moneyline market's outcome 0 is the first team in the slug. Validation: both venues must settle the
same way. Polymarket price = its hourly price history (fidelity 60), the last print at or before the decision time.
Rule: buy the Kalshi side (at its ask, fee in) when Polymarket's price for that side is higher by more than thr.
Horizons pre6 / pre1 / start; one trade per game per horizon. Train before SPLIT, test after (read once).
Also: locked arbitrage after both fees (Kalshi ask + Polymarket other side + 1c half spread).
    python research/kalshi_edge_K4/sports_xvenue.py [--harvest]  -> results_sports_xvenue.json
"""
import json
import math
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone

from lib import fee_per_contract, pnl_per_dollar, summary
from net import CLOB, GAMMA, get
from sports_units import load

HERE = os.path.dirname(os.path.abspath(__file__))
SPLIT = datetime(2026, 10, 26, tzinfo=timezone.utc).timestamp()
LEAGUE = {"KXNBAGAME": "nba", "KXNFLGAME": "nfl", "KXNHLGAME": "nhl", "KXMLBGAME": "mlb"}
MON = {m: i + 1 for i, m in enumerate("JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split())}
HOR = {"pre6": -6, "pre1": -1, "start": 0}
THRS = (0.02, 0.04, 0.06)


def parse(ev):
    code = ev.split("-")[1]
    y, mo, d = 2000 + int(code[:2]), MON[code[2:5]], int(code[5:7])
    teams = code[7:]
    if teams[:4].isdigit():  # MLB tickers carry the start time (HHMM)
        teams = teams[4:]
    return "%04d-%02d-%02d" % (y, mo, d), teams


def match(r):
    lg = LEAGUE[r["s"]]
    date, teams = parse(r["e"])
    for i in range(2, len(teams) - 1):
        a, b = teams[:i], teams[i:]
        if not 2 <= len(b) <= 4:
            continue
        e = get(GAMMA + "/events", {"slug": "%s-%s-%s-%s" % (lg, a.lower(), b.lower(), date)}, gap=0.07)
        if e:
            for m in e[0].get("markets", []):
                if m.get("sportsMarketType") == "moneyline":
                    return a, b, m
    return None


def main():
    rows = [r for r in load() if r["s"] in LEAGUE and r["start"] >= datetime(2026, 9, 17, tzinfo=timezone.utc).timestamp()]
    seen, games = set(), []
    for r in rows:
        if r["e"] not in seen and r.get("c"):
            seen.add(r["e"])
            games.append(r)
    print("kalshi games", len(games), flush=True)
    trades = defaultdict(list)
    arb, matched, agree = [], 0, [0, 0]
    for gi, r in enumerate(games):
        mt = match(r)
        if not mt:
            continue
        a, b, m = mt
        team = r["t"].split("-")[-1]
        if team not in (a, b):
            continue
        try:
            toks = json.loads(m["clobTokenIds"])
            fin = [float(x) for x in json.loads(m["outcomePrices"])]
        except Exception:
            continue
        idx = 0 if team == a else 1
        pm_won = fin[idx] > 0.5
        agree[0] += pm_won == (r["res"] == "yes")
        agree[1] += 1
        if pm_won != (r["res"] == "yes"):
            continue
        matched += 1
        h = get(CLOB + "/prices-history", {"market": toks[idx], "startTs": int(r["start"] - 25 * 3600),
                                           "endTs": int(r["start"] + 600), "fidelity": 60}, gap=0.07)
        hist = sorted((x["t"], x["p"]) for x in (h or {}).get("history", []))
        c = sorted(x for x in r["c"] if x[1] is not None and x[2] is not None)
        for hz, off in HOR.items():
            t = r["start"] + off * 3600
            q = [x for x in c if t - 3600 < x[0] <= t + 1]
            pp = [p for ts_, p in hist if t - 3600 < ts_ <= t + 1]
            if not q or not pp:
                continue
            _, bid, ask, _, _ = q[-1]
            pu = pp[-1]
            if ask - bid > 0.06:
                continue
            yes_won = r["res"] == "yes"
            for kp, pp_other in ((ask, 1 - pu + 0.01), (1 - bid, pu + 0.01)):
                if 0.02 < kp < 0.98 and 0.02 < pp_other < 0.98 and kp + fee_per_contract(kp) + pp_other + fee_per_contract(pp_other) < 1:
                    arb.append({"g": r["e"], "h": hz, "profit": 1 - (kp + fee_per_contract(kp) + pp_other + fee_per_contract(pp_other))})
            for thr in THRS:
                side = None
                if pu - ask > thr:
                    side, p, won = "yes", ask, yes_won
                elif (1 - pu) - (1 - bid) > thr:
                    side, p, won = "no", 1 - bid, not yes_won
                if side and 0.02 <= p <= 0.98:
                    trades[(hz, thr)].append({"r": pnl_per_dollar(p, won), "won": won, "cl": r["e"], "ts": r["start"],
                                              "p": p, "gap": abs(pu - (bid + ask) / 2), "lg": r["s"]})
        if gi % 200 == 0:
            print("game", gi, len(games), "matched", matched, flush=True)
    lo = min(r["start"] for r in games)
    hi = max(r["start"] for r in games)
    dtr, dte = (SPLIT - lo) / 86400, (hi - SPLIT) / 86400
    out = {"kalshi_games": len(games), "matched": matched, "settle_agreement": agree, "train_days": dtr, "test_days": dte,
           "arb": {"hits": len(arb), "games": len({x["g"] for x in arb}),
                   "mean_profit": (sum(x["profit"] for x in arb) / len(arb)) if arb else 0}, "rules": {}}
    fmt = lambda s: "n %4d edge %+6.2f%% [%+6.2f, %+6.2f] t %+5.2f" % (
        s["n"], 100 * s["edge"], 100 * s["lo"], 100 * s["hi"], s["t"]) if s["n"] else "n 0"
    print("matched", matched, "agreement", agree, "arb", out["arb"])
    for k, v in sorted(trades.items()):
        a = summary([u for u in v if u["ts"] < SPLIT], dtr)
        b = summary([u for u in v if u["ts"] >= SPLIT], dte)
        out["rules"]["%s|%.2f" % k] = {"train": a, "test": b}
        print("follow poly %-5s thr %.2f  TR %s | TE %s" % (k[0], k[1], fmt(a), fmt(b)))
    with open(os.path.join(HERE, "results_sports_xvenue.json"), "w") as f:
        json.dump(out, f, indent=1)


if __name__ == "__main__":
    main()
