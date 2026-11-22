"""KALSHI BANKROLL RULE for the K8 clock bets (night-moneyideas 2026-11-20). PAPER RESEARCH ONLY: reads the stored K8 bets
(research/kalshi_edge_K8/data/legs_bets.csv), writes research/lab/kalshi_bankroll.json. Never calls Kalshi, never bets,
never touches engine/kalshi_clock.py. Write-up: research/writeups/money-ideas-2026-11-20.md (idea 1).

Question: the owner has $55 on Kalshi and K8 goes live Monday at $15 a bet on 3 legs (up to $45 out at once). How likely is
the $55 to be wiped out before the edge pays, and which bet size grows the pot fastest without that risk?

Method: the 3 LIVE legs (gold 05:30 down, gold 17:00 up, silver 17:00 up). Each stored bet's result per $1 staked
(net_usd_at_15 / 15: fee and price included) is re-scaled to the stake. Days are kept whole (a day's 3 bets move together)
and resampled with replacement (bootstrap) for 20 trading days (4 weeks), 20,000 paths, seed 7. "Bust" = cash below $5
(no bet possible). Three edge levels: held-out Oct 1-Nov 18 as it was; "half the edge" (each win flipped to a loss with the
probability that brings the win rate halfway to break-even); "no edge" (win rate at break-even). Bet rules: flat $5 / $8 /
$10 / $15, "step": stake = 15% of cash, rounded down to $1, between $5 and $15 (grows with the pot, shrinks after losses), and "ladder" = the same with only the phone picks $5 / $8 / $10 / $15.

    python -X utf8 tools/money/kalshi_bankroll.py            # writes research/lab/kalshi_bankroll.json, prints the table
    python -X utf8 tools/money/kalshi_bankroll.py --quick    # 2,000 paths (tests)
"""
from __future__ import annotations

import csv
import json
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BETS = os.path.join(ROOT, "research", "kalshi_edge_K8", "data", "legs_bets.csv")
OUT = os.path.join(ROOT, "research", "lab", "kalshi_bankroll.json")
LIVE_LEGS = ("A_gold", "B_gold", "B_silver")  # = gold_0530_down, gold_1700_up, silver_1700_up in engine/kalshi_clock.py
START = 55.0
MIN_BET = 5.0
DAYS = 20
RULES = ("flat5", "flat8", "flat10", "flat15", "step15pct", "ladder")
LADDER = ((100.0, 15.0), (67.0, 10.0), (53.0, 8.0), (0.0, 5.0))  # cash >= x -> phone pick $y (the picks the K8 page already has)


def load(path=BETS, period="test"):
    """{date: [(won, net_per_$1), ...]} for the live legs of one period ('test' = held-out Oct 1-Nov 18, 'train', 'all')."""
    days: dict = {}
    with open(path, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["leg"] not in LIVE_LEGS or (period != "all" and r["period"] != period):
                continue
            days.setdefault(r["date"], []).append((int(r["won"]), float(r["net_usd_at_15"]) / 15.0))
    return days


def stats(days):
    bets = [b for d in days.values() for b in d]
    wins = [b[1] for b in bets if b[0]]
    losses = [b[1] for b in bets if not b[0]]
    w = len(wins) / len(bets)
    aw = sum(wins) / len(wins)
    al = -sum(losses) / len(losses)
    be = al / (aw + al)  # win rate where the average bet nets 0
    return {"bets": len(bets), "days": len(days), "win_rate": round(w, 4), "avg_win_per_$1": round(aw, 4),
            "avg_loss_per_$1": round(al, 4), "break_even_win_rate": round(be, 4),
            "net_per_$1": round(sum(b[1] for b in bets) / len(bets), 4)}


def ladder_stake(cash):
    """The phone-pick version of 15% of cash: $5 under $53, $8 from $53, $10 from $67, $15 from $100."""
    return next((st for lo, st in LADDER if cash >= lo), 5.0)


def stake_for(rule, cash):
    if rule.startswith("flat"):
        s = float(rule[4:])
    elif rule == "ladder":
        s = ladder_stake(cash)
    else:  # step15pct
        s = max(MIN_BET, min(15.0, float(int(cash * 0.15))))
    return s if cash >= s else (float(int(cash)) if cash >= MIN_BET else 0.0)


def simulate(days, rule, flip=0.0, paths=20000, n_days=DAYS, seed=7, aw=None, al=None):
    """flip: chance each win becomes a loss (a loss pays -al per $1). Returns bust %, median / p10 / p90 cash after n_days."""
    rng = random.Random(seed)
    pool = list(days.values())
    if al is None:
        bets = [b for d in pool for b in d]
        al = -sum(b[1] for b in bets if not b[0]) / max(1, sum(1 for b in bets if not b[0]))
    ends, bust = [], 0
    for _ in range(paths):
        cash = START
        dead = False
        for _d in range(n_days):
            for won, r in rng.choice(pool):
                s = stake_for(rule, cash)
                if s <= 0:
                    dead = True
                    break
                if won and flip and rng.random() < flip:
                    won, r = 0, -al
                cash += s * r
            if dead or cash < MIN_BET:
                dead = True
                break
        bust += dead
        ends.append(cash)
    ends.sort()
    q = lambda p: round(ends[min(len(ends) - 1, int(p * len(ends)))], 2)  # noqa: E731
    return {"bust_pct": round(100.0 * bust / paths, 1), "median_cash": q(0.5), "p10_cash": q(0.1), "p90_cash": q(0.9)}


def run(paths=20000):
    test = load(period="test")
    train = load(period="train")
    st = stats(test)
    w, be = st["win_rate"], st["break_even_win_rate"]
    levels = {"as_tested": 0.0, "half_edge": 1 - ((w + be) / 2) / w, "no_edge": 1 - be / w}
    table = {}
    for lvl, flip in levels.items():
        table[lvl] = {rule: simulate(test, rule, flip=flip, paths=paths, al=st["avg_loss_per_$1"]) for rule in RULES}
    table["train_months"] = {rule: simulate(train, rule, paths=paths) for rule in RULES}
    pick = "ladder"
    return {
        "title": "Kalshi K8 bankroll rule: $55 start, 3 live legs, 4 weeks",
        "built": "2026-11-20 tools/money/kalshi_bankroll.py (paper research; nothing live changed)",
        "start_cash": START, "days": DAYS, "paths": paths, "legs": list(LIVE_LEGS),
        "held_out": st, "train": stats(train), "flip_chance": {k: round(v, 4) for k, v in levels.items()},
        "table": table, "pick": pick,
        "ladder": [{"cash_from": lo, "bet": st} for lo, st in LADDER],
        "plain": ("At $15 a bet on $55, one bad week can wipe the pot before the edge shows. Bet about 15% of the cash with the "
                  "phone picks: $8 from $53, $10 from $67, $15 from $100 (and back down after losses)."),
    }


def main(argv):
    paths = 2000 if "--quick" in argv else 20000
    out = run(paths)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    if "--no-write" not in argv:
        with open(OUT, "w", encoding="utf-8") as fh:
            json.dump(out, fh, indent=1)
    print(f"held-out: {out['held_out']}")
    for lvl in ("as_tested", "half_edge", "no_edge", "train_months"):
        print(f"\n{lvl}  (bust % / median / p10 / p90 cash after {DAYS} days, start ${START:.0f})")
        for rule, r in out["table"][lvl].items():
            print(f"  {rule:10s} {r['bust_pct']:5.1f}%  ${r['median_cash']:8.2f}  ${r['p10_cash']:8.2f}  ${r['p90_cash']:8.2f}")
    return out


if __name__ == "__main__":
    main(sys.argv[1:])
