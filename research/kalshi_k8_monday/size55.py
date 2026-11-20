"""K8 for a $55 account (night-kalshi8 2026-11-20; owner: "I have $55 and I'm not adding anymore for a while").

1. Kelly: f* = (q - c) / (1 - c) of the bankroll per bet, c = price + fee per contract, q = the win rate. In-sample q is the
   friend's own months (Aug 3 - Nov 19), so the PLAN uses a haircut q (in-sample minus 10 points), and a quarter of that Kelly.
2. The rule, from the bankroll B (engine/kalshi_clock.bankroll_rule): stake = B x 4.5% rounded to $0.50 (at least $1 = 1
   contract), at most 3 bets a day (the 3 live legs), day stop 15% of B, WEEK stop 25% of B (worst-case: settled $ this week +
   every open bet, checked before every order, so a week can never lose more), drawdown stop 35% of B from the peak (the same
   worst-case gate; OFF when not even one bet fits), the 58%-after-60 kill. The simulation applies exactly these gates.
3. Four weeks (20 weekdays), 20,000 paths, resampling whole real days (the 3 live legs of one day stay together), the exact fee per
   order (verify.py), the +20 s walk price. Three worlds: as tested; half the edge (some wins turned into losses at random until
   the win rate is 10 points lower); edge gone (win rate = the price paid + fee: about 53.5%).

    python research/kalshi_k8_monday/size55.py      -> research/kalshi_k8_monday/size55.json
"""
from __future__ import annotations

import json
import math
import os
import random
import statistics
import sys

import k8m_data as D

sys.path.insert(0, D.ROOT)
from engine import kalshi_clock as KC  # noqa: E402

OUT = os.path.join(D.HERE, "size55.json")
PATHS, DAYS, SEED = 20000, 20, 20261120


def day_table():
    """[[(leg, price, won), ...] per real weekday] for the 3 live legs, morning first (the +20 s walk price at $2.50)."""
    rows = [r for r in D.bets(stake=2.5, legs=D.LIVE3) if r.get("n")]
    by = {}
    for r in rows:
        by.setdefault(r["day"], []).append(r)
    order = {"gold_0530_down": 0, "gold_1700_up": 1, "silver_1700_up": 2}
    return [[(r["leg"], r["price"], r["won"]) for r in sorted(v, key=lambda r: order[r["leg"]])] for _, v in sorted(by.items())]


def kelly(q, c):
    return max(0.0, (q - c) / (1 - c))


def simulate(days, rule, world="tested", paths=PATHS, seed=SEED, base_q=None):
    rng = random.Random(seed)
    flip = 0.0
    if world != "tested":
        target = base_q - 0.10 if world == "half" else rule["_breakeven"]
        flip = max(0.0, 1 - target / base_q)                      # P(a win becomes a loss)
    ends, weeks, kills, dd_max, bets_n, week_worst = [], [], 0, [], [], []
    for _ in range(paths):
        eq = peak = 0.0
        killed = False
        n_bets = won_bets = 0
        worst_w = 0.0
        maxdd = 0.0
        for w in range(DAYS // 5):
            wk = 0.0
            for _d in range(5):
                if killed:
                    break
                day = days[rng.randrange(len(days))]
                dset = 0.0
                windows = [[x for x in day if x[0] == "gold_0530_down"], [x for x in day if x[0] != "gold_0530_down"]]
                for win in windows:
                    open_cost, placed = 0.0, []
                    for leg, p, won in win:
                        if world != "tested" and won and rng.random() < flip:
                            won = False
                        n = int(math.floor(rule["stake_usd"] / p + 1e-9))
                        if n < 1:
                            continue
                        c = n * p + D.fee(p, n)
                        if wk - open_cost - c < -rule["week_loss_stop_usd"] - 1e-9:
                            continue
                        if dset - open_cost - c < -rule["daily_loss_stop_usd"] - 1e-9:
                            continue
                        if (peak - eq) + open_cost + c > rule["kill_drawdown_usd"] + 1e-9:     # the engine's drawdown gate (DD_STOP)
                            if not placed:
                                killed = True                                                  # no room for one bet: OFF
                            continue
                        open_cost += c
                        placed.append((n, c, won))
                    for n, c, won in placed:
                        pnl = (n if won else 0) - c
                        eq += pnl
                        wk += pnl
                        dset += pnl
                        n_bets += 1
                        won_bets += 1 if won else 0
                    peak = max(peak, eq)
                    maxdd = max(maxdd, peak - eq)
                    if peak - eq >= rule["kill_drawdown_usd"] - 1e-9:
                        killed = True
                    if n_bets >= 60 and won_bets / n_bets < 0.58:
                        killed = True
                    if killed:
                        break
            weeks.append(wk)
            worst_w = min(worst_w, wk)
        ends.append(eq)
        kills += killed
        dd_max.append(maxdd)
        bets_n.append(n_bets)
        week_worst.append(worst_w)
    ends.sort()
    B = rule["bankroll_usd"]
    return {"world": world, "usd_week_mean": round(statistics.mean(weeks), 2), "usd_4w_mean": round(statistics.mean(ends), 2),
            "usd_4w_median": round(ends[len(ends) // 2], 2), "usd_4w_p5": round(ends[int(0.05 * len(ends))], 2),
            "usd_4w_p95": round(ends[int(0.95 * len(ends))], 2), "p_down_4w": round(sum(1 for e in ends if e < 0) / len(ends), 4),
            "p_kill": round(kills / paths, 4), "worst_week_usd": round(min(week_worst), 2),
            "p_week_worse_than_25pct": round(sum(1 for w in weeks if w < -0.25 * B - 1e-9) / len(weeks), 5),
            "p_any_week_below_15pct": round(sum(1 for x in week_worst if x < -0.15 * B) / paths, 4),
            "dd_p95": round(sorted(dd_max)[int(0.95 * len(dd_max))], 2), "bets_4w_mean": round(statistics.mean(bets_n), 1),
            "win_flip": round(flip, 4)}


def main():
    days = day_table()
    allb = [x for d in days for x in d]
    q = sum(1 for x in allb if x[2]) / len(allb)
    p = sum(x[1] for x in allb) / len(allb)
    fee_c = statistics.mean(D.fee(x[1], int(2.5 // x[1])) / int(2.5 // x[1]) for x in allb)
    c = p + fee_c
    out = {"as_of": "2026-11-19", "days": len(days), "bets": len(allb), "win_rate": round(q, 4), "avg_price": round(p, 4),
           "fee_per_contract": round(fee_c, 4), "breakeven_win_rate": round(c, 4),
           "kelly": {"in_sample_q": round(q, 4), "full_kelly_in_sample": round(kelly(q, c), 4),
                     "plan_q": round(q - 0.10, 4), "full_kelly_plan": round(kelly(q - 0.10, c), 4),
                     "quarter_kelly_plan": round(kelly(q - 0.10, c) / 4, 4)},
           "min_bet": {}, "rules": {}}
    for px in (0.50, 0.54, 0.58):
        out["min_bet"][f"{px:.2f}"] = {"contracts": 1, "cost": round(px + D.fee(px, 1), 2), "fee": D.fee(px, 1),
                                        "fee_per_contract_at_4": round(D.fee(px, 4) / 4, 4)}
    for name, B, stake in (("$1 a bet", 55, 1.0), ("$2.50 a bet (the rule)", 55, None), ("$5 a bet", 55, 5.0), ("$15 a bet (old)", 55, 15.0)):
        rule = KC.bankroll_rule(B)
        if stake is not None:
            rule = dict(rule, stake_usd=stake)
        rule["_breakeven"] = c
        res = {w: simulate(days, rule, w, base_q=q) for w in ("tested", "half", "gone")}
        out["rules"][name] = {"rule": {k: v for k, v in rule.items() if not k.startswith("_")}, "worlds": res}
        print(name, json.dumps({w: {k: r[k] for k in ("usd_week_mean", "p_down_4w", "usd_4w_p5", "p_kill", "worst_week_usd")} for w, r in res.items()}), flush=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, default=str)
    print(json.dumps({k: out[k] for k in ("win_rate", "avg_price", "fee_per_contract", "breakeven_win_rate", "kelly", "min_bet")}, indent=1))


if __name__ == "__main__":
    main()
