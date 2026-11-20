#!/usr/bin/env python3
"""K8 plan + edge health for the phone (day-kalshi 2026-11-20): tools/web_public/kalshi/k8.json, from Kalshi's PUBLIC results only.

Reads the recorded public tape of the K8 legs (research/kalshi_k8_day/data/tape.jsonl, filled by research/kalshi_k8_day/fetch.py at
<= 1 request a second; research/kalshi_k8_monday/data/tape_fresh.jsonl too) and writes, per leg and for the 3 live legs pooled: how
often the leg won at the bot's +20 s entry with $2.50 bets, the average price, the fair price (the win rate minus the fee: the
price where the bet breaks even), the last 30 / 60 win rates against the 58% OFF line, the average price on the last 30 against the
58c creep line, the last 10 results, and the last 8 weeks in $. This is the STRATEGY's health (every window, whether or not we bet),
not our own ledger (that is the PC's card). No key, no order, no network.

    python tools/kalshi_k8_feed.py                 # write tools/web_public/kalshi/k8.json (not rewritten when nothing changed)
    python tools/kalshi_k8_feed.py --check         # exit 1 if the committed k8.json is out of date
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import kalshi_adapt as KA, kalshi_clock as KC  # noqa: E402

TAPES = (os.path.join(ROOT, "research", "kalshi_k8_monday", "data", "tape_fresh.jsonl"),
         os.path.join(ROOT, "research", "kalshi_k8_day", "data", "tape.jsonl"))      # the later file wins on overlap
OUT = os.path.join(ROOT, "tools", "web_public", "kalshi", "k8.json")
NOISE = os.path.join(ROOT, "research", "kalshi_k8_day", "noise.json")
FIRST = dt.date(2026, 8, 3)
STAKE = 2.5
DELAY = 20.0
CODE = {"gold_0530_down": "g5", "silver_0530_down": "s5", "silver_1615_down": "s16", "gold_1700_up": "g17", "silver_1700_up": "s17"}


def tape() -> dict:
    out = {}
    for p in TAPES:
        out.update(KA.read_tape(p))
    return out


def our_trades(tr, side):
    out = []
    for x in tr or []:
        try:
            s, ts, yp, c = float(x[0]), str(x[1]), float(x[2]), float(x[3])
        except (TypeError, ValueError, IndexError):
            continue
        if ts == side and c > 0 and 0 < yp < 1:
            out.append((s, round(yp if side == "yes" else 1 - yp, 4), c))
    return sorted(out)


def walk_from(tr, side, t0, stake, cap=0.70, until=45.0):
    """What a $stake taker order sent at t0 s gets, walking the public takers of our side from t0 (the red team's '+20 s walk',
    research/kalshi_k8_monday/k8m_data.walk_from; the executor's 70c cap): -> (contracts, average price, first price)."""
    got, cost, first = 0, 0.0, None
    for s, p, c in our_trades(tr, side):
        if s < t0 or s > until or p > cap + 1e-9:
            continue
        first = p if first is None else first
        k = int(min(c + 1e-9, math.floor((stake - cost) / p + 1e-9)))
        if k <= 0:
            if got == 0 and c < 1 and (stake - cost) >= p:
                continue
            break
        got, cost = got + k, cost + k * p
        if stake - cost < p:
            break
    return (got, round(cost / got, 4), first) if got else (0, None, first)


def bets(T=None, first=FIRST, last=None, legs=None, stake=STAKE, delay=DELAY) -> list:
    """One row per leg-day the executor would have bet (its calendar), priced from the public tape; unfilled days are left out."""
    T = tape() if T is None else T
    last = last or dt.date.today()
    out, d = [], first
    while d <= last:
        if d.weekday() < 5:
            for lid in legs or list(KC.LEG):
                L = KC.LEG[lid]
                if KC.skipped(L, d):
                    continue
                o = KC.leg_open(L, d)
                rec = T.get(KC.ticker(L["series"], o))
                if not rec or rec.get("res") not in ("yes", "no"):
                    continue
                n, px, p1 = walk_from(rec["tr"], L["side"], delay, stake)
                if not n:
                    continue
                want = max(1, int(math.floor(stake / p1 + 1e-9))) if p1 else 1
                if n < max(1, math.ceil(want * 0.5 - 1e-9)):
                    continue
                f = KA.fee(px, n)
                won = rec["res"] == L["side"]
                cost = n * px + f
                out.append({"day": d, "leg": lid, "o": o, "won": won, "n": n, "price": px, "fee": f, "cost": round(cost, 4),
                            "pnl": round((n if won else 0) - cost, 4)})
        d += dt.timedelta(days=1)
    return sorted(out, key=lambda r: r["o"])


def _rate(rs):
    return round(sum(1 for r in rs if r["won"]) / len(rs), 4) if rs else None


def _avg_c(rs):
    return round(100 * sum(r["price"] for r in rs) / len(rs), 1) if rs else None


def block(rs) -> dict:
    fee_c = 100 * sum(r["fee"] / r["n"] for r in rs) / len(rs) if rs else 0.0
    rate = _rate(rs)
    return {"n": len(rs), "won": sum(1 for r in rs if r["won"]), "rate": rate, "avg_c": _avg_c(rs),
            "fair_c": round(100 * rate - fee_c, 1) if rate is not None else None, "r30": _rate(rs[-30:]), "r60": _rate(rs[-60:]),
            "avg30_c": _avg_c(rs[-30:]), "last10": "".join("W" if r["won"] else "L" for r in rs[-10:]),
            "net_usd": round(sum(r["pnl"] for r in rs), 2)}


def weeks(rs, k=8) -> list:
    by = {}
    for r in rs:
        by.setdefault(KC.week_of(r["day"]), []).append(r)
    return [{"wk": w, "n": len(x), "won": sum(1 for r in x if r["won"]), "net": round(sum(r["pnl"] for r in x), 2)}
            for w, x in sorted(by.items())[-k:]]


def build(T=None, today=None) -> dict:
    cfg = KC.load_config()[0]
    rs = bets(T, last=today)
    legs = []
    for L in KC.LEGS:
        x = [r for r in rs if r["leg"] == L["id"]]
        b = block(x)
        last = x[-1] if x else None
        legs.append({"id": L["id"], "code": CODE[L["id"]], "name": L["name"], "live": L["id"] in cfg["live_legs"],
                     "tz": "Europe/London" if L["tz"] == "London" else "America/New_York", "open": "%02d:%02d" % L["open"],
                     "side": "UP" if L["side"] == "yes" else "DOWN", **b,
                     "last_c": round(100 * last["price"]) if last else None, "last_day": str(last["day"]) if last else None,
                     "last_res": ("W" if last["won"] else "L") if last else None})
    live = [r for r in rs if r["leg"] in cfg["live_legs"]]
    pool = dict(block(live), weeks=weeks(live))
    noise = KA._jread(NOISE, None)
    out = {"v": 1, "kind": "k8_plan", "through": str(rs[-1]["day"]) if rs else None, "first": str(FIRST),
           "about": "Kalshi's PUBLIC results of every K8 window at the bot's +20 s entry, $2.50 bets, fees in: the strategy's health, not our own bets.",
           "rule": {"bankroll": cfg.get("bankroll_usd"), "stake": cfg["stake_usd"], "max_day": cfg["max_bets_per_day"],
                    "day_stop": cfg["daily_loss_stop_usd"], "week_stop": cfg["week_loss_stop_usd"], "dd_stop": cfg["kill_drawdown_usd"],
                    "min_win": cfg["kill_min_win_rate"], "after": cfg["kill_after_bets"], "creep_max": cfg["kill_avg_price"],
                    "creep_bets": cfg["kill_avg_price_bets"], "cap": cfg["price_cap"]},
           "legs": legs, "pool": pool, "skip": {"cme": sorted(KC.CME_SKIP), "uk": sorted(KC.UK_SKIP)}}
    if isinstance(noise, dict) and noise.get("plain"):
        out["noise"] = {k: noise.get(k) for k in ("plain", "verdict", "p_bad4", "p_trend_win", "p_trend_price")}
    return out


def same(a, b) -> bool:
    strip = lambda d: {k: v for k, v in (d or {}).items() if k != "updated"}      # noqa: E731
    return json.dumps(strip(a), sort_keys=True) == json.dumps(strip(b), sort_keys=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    new = build()
    old = KA._jread(a.out, None)
    if a.check:
        ok = same(new, old)
        print("k8.json up to date" if ok else "k8.json is out of date: python tools/kalshi_k8_feed.py")
        return 0 if ok else 1
    if same(new, old):
        print("k8.json: nothing changed")
        return 0
    new["updated"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with open(a.out, "w", encoding="utf-8") as fh:
        json.dump(new, fh, separators=(",", ":"))
    p = new["pool"]
    print(f"k8.json: {p['n']} live-leg bets through {new['through']}, {p['won']} won ({100 * (p['rate'] or 0):.0f}%), "
          f"last 30 {100 * (p['r30'] or 0):.0f}%, last 60 {100 * (p['r60'] or 0):.0f}%, {p['net_usd']:+.2f} $ at $2.50, {os.path.getsize(a.out)} bytes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
