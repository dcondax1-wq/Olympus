#!/usr/bin/env python3
"""Kalshi City DEMO data: a made-up, deterministic Kalshi feed so the city can be shown offline (tools/web_public/kalshicity/fixture.json).

  python tools/kalshi_demo.py                      # rewrites kalshicity/fixture.json (seed 36)

Everything here is SYNTHETIC: about 1,500 invented bets over 70 days from six invented rules, with known edges planted on purpose (so the
city has every kind of building: proven, growing, fading, dead, new, too small to trust). The page shows a DEMO badge whenever it uses this.
The fixture holds the feed (as the bot publishes it: 40 trades, totals) and the edges / learning log the engine (tools/kalshi_edges.py)
worked out from ALL the invented bets, so the offline city is as rich as the real one will be after weeks of learning.
"""
from __future__ import annotations

import json
import math
import os
import random
import sys
import tempfile
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import kalshi_edges as ke  # noqa: E402

OUT = os.path.join(ke.OUT_DEFAULT, "fixture.json")
DAYS = 70
ASSET = {"Bitcoin": "BTC", "Ethereum": "ETH", "Solana": "SOL", "XRP": "XRP", "Dogecoin": "DOGE", "Other": "OTH", "Gold": "GOLD", "HYPE": "HYPE", "BNB": "BNB"}
GROUP = {"Bitcoin": "Crypto", "Ethereum": "Crypto", "Solana": "Crypto", "XRP": "Crypto", "Dogecoin": "Crypto", "HYPE": "Crypto", "BNB": "Crypto", "Gold": "Commodities", "Other": "Other"}


def true_q(rule, day, market, p, hour):
    """The planted truth: the chance a bet really wins, given what the market priced."""
    if rule == "Late favourite (BTC hourly)":
        return p + 0.03 if p < 0.97 else p - 0.03
    if rule == "15-min favourites":
        if market == "Bitcoin":
            return p + 0.014
        if market == "Ethereum":
            return p + 0.02 if day < DAYS - 22 else p - 0.025
        if market == "XRP":
            return p - 0.04
        if market == "Dogecoin":
            return p + 0.003
        return p - 0.002 if market == "Solana" else p + 0.002
    if rule == "Hourly BTC":
        return p + 0.07 if 10 <= hour <= 16 else p - 0.012
    if rule == "combo":
        return p + (0.045 if day >= DAYS - 15 else 0.006)
    if rule == "Value":
        return p - 0.05
    return p + 0.02                                    # Gold 5 PM


RULES = [   # name, markets, price low, price high, bets per day, first day index
    ("Late favourite (BTC hourly)", ["Bitcoin"], 0.93, 0.99, 5, 0),
    ("15-min favourites", ["Bitcoin", "Ethereum", "Solana", "XRP", "Dogecoin", "Other"], 0.85, 0.97, 9, 0),
    ("Hourly BTC", ["Bitcoin"], 0.55, 0.95, 4, 0),
    ("combo", ["Bitcoin", "Ethereum"], 0.90, 0.96, 2, 0),
    ("Value", ["Other", "HYPE", "BNB"], 0.30, 0.70, 1.5, 0),
    ("Gold 5 PM", ["Gold"], 0.88, 0.96, 2, DAYS - 2),
]


def make(seed=36):
    rnd = random.Random(seed)
    now = datetime(2026, 11, 2, 21, 0, tzinfo=ke.ET)
    start = (now - timedelta(days=DAYS)).replace(hour=0, minute=0)
    trades = []
    for day in range(DAYS):
        for name, markets, lo, hi, per_day, first in RULES:
            if day < first:
                continue
            k = int(per_day) + (1 if rnd.random() < per_day - int(per_day) else 0)
            for _ in range(k):
                m = rnd.choice(markets)
                hour = rnd.randrange(24) if name != "Hourly BTC" else rnd.randrange(8, 22)
                t = start + timedelta(days=day, hours=hour, minutes=rnd.randrange(60))
                if t > now:
                    continue
                p = round(rnd.uniform(lo, hi), 2)
                stake = rnd.uniform(6, 14)
                c = max(1, round(stake / p))
                side = rnd.choice(["yes", "no"])
                q = min(0.995, max(0.02, true_q(name, day, m, p, hour)))
                win = rnd.random() < q
                fee = math.ceil(0.07 * c * p * (1 - p) * 100) / 100
                pnl = round(c * ((1.0 if win else 0.0) - p) - fee, 2)
                trades.append({"t": int(t.timestamp()), "ticker": f"KX{ASSET[m]}-{t:%y%b%d%H}-{rnd.randrange(10 ** 5):05d}".upper(), "title": f"{m} above target at {t:%I %p} ET",
                               "side": side, "action": "buy", "contracts": float(c), "price": p, "pnl": pnl, "asset": ASSET[m], "strategy": name, "category": m})
    trades.sort(key=lambda r: r["t"])
    return now, trades


def feed_of(now, trades):
    by_s, by_m, by_b = {}, {}, {}
    for r in trades:
        o = ke.outcome(r["pnl"])
        for table, k in ((by_s, r["strategy"]), (by_m, r["category"])):
            row = table.setdefault(k, {"trades": 0, "wins": 0, "losses": 0, "pnl": 0.0, "staked": 0.0})
            row["trades"] += 1
            row["wins"] += o > 0
            row["losses"] += o < 0
            row["pnl"] = round(row["pnl"] + r["pnl"], 2)
            row["staked"] = round(row["staked"] + r["contracts"] * r["price"], 2)
        b = ke.band_index(r["price"])
        row = by_b.setdefault(b, {"trades": 0, "wins": 0, "losses": 0, "pnl": 0.0, "staked": 0.0, "sp": 0.0})
        row["trades"] += 1
        row["wins"] += o > 0
        row["losses"] += o < 0
        row["pnl"] = round(row["pnl"] + r["pnl"], 2)
        row["staked"] = round(row["staked"] + r["contracts"] * r["price"], 2)
        row["sp"] += r["price"]
    days = {}
    for r in trades:
        d = ke.et_date(r["t"])
        days[d] = round(days.get(d, 0.0) + r["pnl"], 2)
    day_rows = sorted(days.items())[-41:]
    bal, eq = 260.0, []
    for r in trades:
        bal += r["pnl"]
        eq.append([r["t"], round(bal, 2)])
    st = {"trades": len(trades), "wins": sum(1 for r in trades if r["pnl"] > 0.005), "losses": sum(1 for r in trades if r["pnl"] < -0.005),
          "staked": round(sum(r["contracts"] * r["price"] for r in trades), 2), "pnl": round(sum(r["pnl"] for r in trades), 2),
          "avg_price": round(sum(r["price"] for r in trades) / len(trades), 4)}
    t0 = int(now.timestamp())
    pos = [{"ticker": "KXBTC-DEMO-OPEN1", "title": "Bitcoin above target at 10 PM ET", "side": "yes", "contracts": 8.0, "avg_price": 0.96, "price": 0.97, "strategy": "Late favourite (BTC hourly)", "category": "Bitcoin", "closes": t0 + 3600},
           {"ticker": "KXETH-DEMO-OPEN2", "title": "Ethereum above target at 10 PM ET", "side": "no", "contracts": 9.0, "avg_price": 0.93, "price": 0.94, "strategy": "15-min favourites", "category": "Ethereum", "closes": t0 + 2400},
           {"ticker": "KXSOL-DEMO-OPEN3", "title": "Solana above target at 9:30 PM ET", "side": "yes", "contracts": 7.0, "avg_price": 0.91, "price": 0.9, "strategy": "15-min favourites", "category": "Solana", "closes": t0 + 1200}]
    return {
        "v": 3, "kind": "kalshi", "name": "Kalshi Edge (demo)", "mode": "demo", "status": "Running", "running": True, "t": t0, "balance": round(bal, 4),
        "today_pnl": days.get(ke.et_date(t0), 0.0), "week_pnl": round(sum(v for _, v in day_rows[-7:]), 2), "total_pnl": st["pnl"], "note": "DEMO: invented bets, not the real bot",
        "positions": pos, "trades": list(reversed(trades[-40:])), "days": [[d, v] for d, v in day_rows],
        "strategies": [{"name": k, "mode": "demo", "running": True, "today_pnl": 0.0, "total_pnl": v["pnl"], "trades": v["trades"], "wins": v["wins"], "losses": v["losses"]} for k, v in by_s.items()],
        "equity": eq[-98:], "categories": [{"name": k, "group": GROUP[k], "trades": v["trades"], "wins": v["wins"], "losses": v["losses"], "pnl": v["pnl"], "staked": v["staked"]}
                                           for k, v in sorted(by_m.items(), key=lambda kv: -kv[1]["trades"])],
        "buckets": [{"lo": ke.BAND_EDGES[i], "hi": min(1.0, ke.BAND_EDGES[i + 1]), "trades": v["trades"], "wins": v["wins"], "losses": v["losses"], "pnl": v["pnl"], "staked": v["staked"]} for i, v in sorted(by_b.items())],
        "calibration": [{"p": round(v["sp"] / v["trades"], 4), "n": v["trades"], "hit": round(v["wins"] / v["trades"], 4)} for i, v in sorted(by_b.items())],
        "alerts": [], "kelly": {"bankroll": round(bal, 2), "min_edge": 0.0}, "stats": st, "calib_basis": "price", "pub_t": t0,
    }


HYP_DAYS = 20                                            # the demo's ideas were registered this many days ago; the engine ran every second day since


def hypotheses_of(now, trades):
    """Replay the engine every second day for the last 12 days in a scratch folder, so the demo's ideas have a registration day, a live window and a history."""
    doc = None
    with tempfile.TemporaryDirectory() as tmp:
        for back in range(HYP_DAYS, -1, -2):
            at = now - timedelta(days=back)
            tr = [r for r in trades if r["t"] <= at.timestamp()]
            if tr:
                ke.run(dict(feed_of(at, tr), trades=list(reversed(tr))), tmp, now=at.timestamp())
        doc = ke.read_json(os.path.join(tmp, "hypotheses.json"), None)
    return doc


def build(seed=36):
    now, trades = make(seed)
    full = feed_of(now, trades)
    with tempfile.TemporaryDirectory() as tmp:
        doc, _, _ = ke.run(dict(full, trades=list(reversed(trades))), tmp, now=now.timestamp())
        log = ke.read_json(os.path.join(tmp, "learning_log.json"), {})["entries"]
    # the demo pretends yesterday's run found these: a building going up (Gold) and one crumbling (XRP)
    yday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
    for e in doc["edges"]:
        if "Gold" in e["dims"] or "Gold 5 PM" in e["dims"]:
            e["first"] = yday
        if "XRP" in e["dims"] and e["status"] == "DEAD":
            e["since"] = yday
    feed = dict(full)                                     # what the bot publishes: only the last 40 trades
    return {"v": 1, "demo": True, "app": "kalshicity", "about": "SYNTHETIC demo: about 1,500 invented bets from six invented rules with planted edges. Not the real bot.",
            "kalshi": feed, "edges": doc, "log": log, "hyps": hypotheses_of(now, trades)}


def main():
    fx = build()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(fx, fh, ensure_ascii=False, separators=(",", ":"))
        fh.write("\n")
    c = fx["edges"]["counts"]
    print(f"kalshi_demo: {fx['edges']['ledger']['n']} invented bets, {c['edges']} edges, {c}; {os.path.getsize(OUT) // 1024} KB")


if __name__ == "__main__":
    main()
