"""Performance statistics, MFFU prop-firm rule simulation and Monte Carlo."""
from __future__ import annotations

import math
import random
from collections import defaultdict

import numpy as np

# MFFU plan presets (verify on myfundedfutures.com before trading; rules change)
PLANS = {
    "builder_50k": {"name": "MFFU Builder 50K", "start": 50000, "target": 3000, "mll": 2000, "dll": 1000,
                    "lock_above": 100, "max_minis": 4, "buffer": 2100, "payout_min": 500, "payout_max": 2000,
                    "consistency": 0.5, "split": 0.8, "min_days_eval": 1, "payout_min_days": 2},
    "builder_50k_addon": {"name": "MFFU Builder 50K (add-on, $1.5K MLL)", "start": 50000, "target": 3000, "mll": 1500,
                          "dll": 1000, "lock_above": 100, "max_minis": 4, "buffer": 1600, "payout_min": 500,
                          "payout_max": 2000, "consistency": 0.5, "split": 0.8, "min_days_eval": 1, "payout_min_days": 2},
}


# Other firms' 50K plans (researched from each firm's help center, Oct 2026 - re-check before buying).
# lock_above None = drawdown keeps trailing; eval_consistency = best day must be <= this share of profit to pass.
PLANS.update({
    "topstep_50k": {"name": "Topstep 50K Combine", "start": 50000, "target": 3000, "mll": 2000, "dll": 0, "lock_above": 0,
                    "max_minis": 5, "buffer": 0, "payout_min": 125, "payout_max": 2000, "consistency": 1.0, "split": 0.9,
                    "min_days_eval": 2, "payout_min_days": 5, "eval_consistency": 0.55,
                    "automation": "Allowed via TopstepX API ($29/mo), own device, no HFT; not on Live accounts",
                    "price": "$49/mo + $149 activation", "flat": "3:10 PM CT"},
    "tradeify_select_50k": {"name": "Tradeify Select 50K", "start": 50000, "target": 3000, "mll": 2000, "dll": 0, "lock_above": 100,
                            "max_minis": 4, "buffer": 0, "payout_min": 250, "payout_max": 2500, "consistency": 1.0, "split": 0.9,
                            "min_days_eval": 3, "payout_min_days": 5, "eval_consistency": 0.40,
                            "automation": "Allowed if you are the sole owner; no HFT; no same bot across firms",
                            "price": "$165 one-time", "flat": "4:45 PM ET"},
    "tradeify_growth_50k": {"name": "Tradeify Growth 50K", "start": 50000, "target": 3000, "mll": 2000, "dll": 1250, "lock_above": 100,
                            "max_minis": 4, "buffer": 2100, "payout_min": 250, "payout_max": 1250, "consistency": 1.0, "split": 0.9,
                            "min_days_eval": 1, "payout_min_days": 5, "eval_consistency": None,
                            "automation": "Allowed if you are the sole owner; no HFT", "price": "$145 one-time", "flat": "4:45 PM ET"},
    "lucid_flex_50k": {"name": "Lucid Flex 50K", "start": 50000, "target": 3000, "mll": 2000, "dll": 0, "lock_above": 100,
                       "max_minis": 4, "buffer": 0, "payout_min": 500, "payout_max": 2000, "consistency": 1.0, "split": 0.9,
                       "min_days_eval": 2, "payout_min_days": 5, "eval_consistency": 0.50,
                       "automation": "Automated systems and copiers allowed; no HFT / microscalping / hedging",
                       "price": "$146 one-time (often ~$90-105)", "flat": "4:45 PM ET"},
    "apex_50k": {"name": "Apex 50K EOD", "start": 50000, "target": 3000, "mll": 2000, "dll": 1000, "lock_above": None,
                 "max_minis": 6, "buffer": 2100, "payout_min": 500, "payout_max": 1500, "consistency": 0.5, "split": 1.0,
                 "min_days_eval": 1, "payout_min_days": 5, "eval_consistency": None,
                 "automation": "PROHIBITED - no automation or algorithms", "price": "~$197 couponed + $129 activation", "flat": "before close"},
})
PLANS["builder_50k"].update({"automation": "Allowed with active oversight (confirm with MFFU)", "price": "$153 list ($92-107 couponed)",
                             "flat": "session close", "eval_consistency": None})
PLANS["builder_50k_addon"].update({"automation": "Allowed with active oversight (confirm with MFFU)", "price": "$125 list", "eval_consistency": None})


def stats(trades: list, days: list) -> dict:
    n = len(trades)
    pnl = np.array([t["pnl"] for t in trades]) if n else np.zeros(0)
    rs = np.array([t["pnl_r"] for t in trades]) if n else np.zeros(0)
    wins = pnl[pnl > 0]
    losses = pnl[pnl <= 0]
    gp, gl = wins.sum(), -losses.sum()
    eq = np.cumsum(pnl) if n else np.zeros(0)
    peak = np.maximum.accumulate(np.concatenate([[0], eq]))[1:] if n else np.zeros(0)
    dd = (eq - peak) if n else np.zeros(0)
    # streaks
    max_w = max_l = cw = cl = 0
    for x in pnl:
        if x > 0:
            cw += 1; cl = 0
        else:
            cl += 1; cw = 0
        max_w, max_l = max(max_w, cw), max(max_l, cl)
    dpnl = np.array([d["pnl"] for d in days]) if days else np.zeros(0)
    active_days = [d for d in days if d.get("trades")]
    n_days = len(days)
    weeks = max(1e-9, n_days / 5.0)
    sharpe = float(dpnl.mean() / dpnl.std() * math.sqrt(252)) if len(dpnl) > 1 and dpnl.std() > 0 else 0.0
    neg = dpnl[dpnl < 0]
    sortino = float(dpnl.mean() / neg.std() * math.sqrt(252)) if len(neg) > 1 and neg.std() > 0 else 0.0
    by_exit = defaultdict(int)
    for t in trades:
        by_exit[t["exit_reason"]] += 1
    best_day = float(dpnl.max()) if len(dpnl) else 0.0
    total = float(pnl.sum())
    return {
        "trades": n,
        "net": round(total, 2),
        "gross_profit": round(float(gp), 2),
        "gross_loss": round(float(gl), 2),
        "win_rate": round(float(len(wins) / n * 100), 1) if n else 0.0,
        "profit_factor": round(float(gp / gl), 2) if gl > 0 else (999.0 if gp > 0 else 0.0),
        "avg_win": round(float(wins.mean()), 2) if len(wins) else 0.0,
        "avg_loss": round(float(losses.mean()), 2) if len(losses) else 0.0,
        "expectancy": round(float(pnl.mean()), 2) if n else 0.0,
        "avg_r": round(float(rs.mean()), 3) if n else 0.0,
        "total_r": round(float(rs.sum()), 2),
        "max_dd": round(float(dd.min()), 2) if n else 0.0,
        "max_win_streak": max_w,
        "max_loss_streak": max_l,
        "sharpe": round(sharpe, 2),
        "sortino": round(sortino, 2),
        "days": n_days,
        "active_days": len(active_days),
        "trades_per_week": round(n / weeks, 2),
        "best_day": round(best_day, 2),
        "worst_day": round(float(dpnl.min()), 2) if len(dpnl) else 0.0,
        "best_day_pct": round(best_day / total * 100, 1) if total > 0 else None,
        "longs": sum(1 for t in trades if t["dir"] == 1),
        "shorts": sum(1 for t in trades if t["dir"] == -1),
        "long_net": round(sum(t["pnl"] for t in trades if t["dir"] == 1), 2),
        "short_net": round(sum(t["pnl"] for t in trades if t["dir"] == -1), 2),
        "avg_bars_held": round(float(np.mean([t["bars_held"] for t in trades])), 1) if n else 0.0,
        "avg_mae": round(float(np.mean([t["mae"] for t in trades])), 2) if n else 0.0,
        "avg_mfe": round(float(np.mean([t["mfe"] for t in trades])), 2) if n else 0.0,
        "commissions": round(sum(t["comm"] for t in trades), 2),
        "exit_reasons": dict(by_exit),
    }


def breakdowns(trades: list) -> dict:
    import datetime as dt
    from zoneinfo import ZoneInfo
    et = ZoneInfo("America/New_York")
    by = {"hour": defaultdict(lambda: [0, 0.0, 0]), "dow": defaultdict(lambda: [0, 0.0, 0]),
          "trigger": defaultdict(lambda: [0, 0.0, 0]), "score": defaultdict(lambda: [0, 0.0, 0]),
          "pool": defaultdict(lambda: [0, 0.0, 0]), "conf": defaultdict(lambda: [0, 0.0, 0]),
          "dir": defaultdict(lambda: [0, 0.0, 0]), "target": defaultdict(lambda: [0, 0.0, 0])}
    for t in trades:
        x = dt.datetime.fromtimestamp(t["entry_t"], et)
        keys = {
            "hour": f"{x.hour:02d}:00", "dow": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"][x.weekday()],
            "trigger": t["trigger"], "score": str(t["score"]), "dir": "Long" if t["dir"] == 1 else "Short",
            "target": "".join(ch for ch in t["target_label"].split(" ")[0] if not ch.isdigit()) or "R",
        }
        for k, v in keys.items():
            a = by[k][v]; a[0] += 1; a[1] += t["pnl"]; a[2] += 1 if t["pnl"] > 0 else 0
        for pl in set(p.split("·")[-1] for p in t["pools"]):
            a = by["pool"][pl]; a[0] += 1; a[1] += t["pnl"]; a[2] += 1 if t["pnl"] > 0 else 0
        for tag in t["conf_tags"]:
            tag = tag.split(" (")[0]
            a = by["conf"][tag]; a[0] += 1; a[1] += t["pnl"]; a[2] += 1 if t["pnl"] > 0 else 0
    out = {}
    for k, m in by.items():
        out[k] = sorted([{"key": kk, "n": v[0], "pnl": round(v[1], 2), "wr": round(v[2] / v[0] * 100, 1)}
                         for kk, v in m.items()], key=lambda z: z["key"])
    return out


# ------------------------------------------------------------------------------- prop firm
def simulate_eval(day_pnls: list, plan: dict, intraday_lows: list | None = None) -> dict:
    """Run an MFFU-style evaluation over a sequence of daily P&L values.
    EOD trailing MLL: trails new end-of-day balance highs, locks at start + lock_above."""
    bal = plan["start"]
    peak = bal
    mll = bal - plan["mll"]
    lock = plan["start"] + plan["lock_above"] if plan.get("lock_above") is not None else float("inf")
    cons = plan.get("eval_consistency")
    best, active = 0.0, 0
    path = []
    for k, dp in enumerate(day_pnls):
        low_intra = bal + (intraday_lows[k] if intraday_lows else min(0.0, dp))
        bal += dp
        best = max(best, dp)
        active += 1 if dp != 0 else 0
        if low_intra <= mll or bal <= mll:
            path.append({"day": k + 1, "balance": round(bal, 2), "mll": mll})
            return {"result": "FAIL", "days": k + 1, "balance": round(bal, 2), "path": path}
        peak = max(peak, bal)
        mll = min(max(mll, peak - plan["mll"]), lock)
        path.append({"day": k + 1, "balance": round(bal, 2), "mll": mll})
        profit = bal - plan["start"]
        consistent = not cons or (profit > 0 and best <= cons * profit)
        if profit >= plan["target"] and active >= plan["min_days_eval"] and consistent:
            return {"result": "PASS", "days": k + 1, "balance": round(bal, 2), "path": path}
    return {"result": "OPEN", "days": len(day_pnls), "balance": round(bal, 2), "path": path}


def rolling_evals(days: list, plan: dict) -> dict:
    """Start a fresh evaluation on every historical trading day and run it forward."""
    pnls = [d["pnl"] for d in days]
    lows = [d.get("low_intraday", min(0.0, d["pnl"])) for d in days]
    res = []
    for s in range(len(pnls)):
        r = simulate_eval(pnls[s:], plan, lows[s:])
        res.append({"start": days[s]["date"], "result": r["result"], "days": r["days"]})
    done = [r for r in res if r["result"] != "OPEN"]
    passes = [r for r in done if r["result"] == "PASS"]
    return {
        "runs": res,
        "completed": len(done),
        "pass": len(passes),
        "fail": len(done) - len(passes),
        "open": len(res) - len(done),
        "pass_rate": round(len(passes) / len(done) * 100, 1) if done else None,
        "avg_days_to_pass": round(float(np.mean([r["days"] for r in passes])), 1) if passes else None,
    }


def monte_carlo(day_pnls: list, plan: dict, runs: int = 2000, horizon: int = 60, seed: int = 7) -> dict:
    """Bootstrap trading days (with replacement) to estimate eval pass odds and funded payout expectations."""
    rng = random.Random(seed)
    if not day_pnls:
        return {"runs": 0}
    pass_n = fail_n = 0
    days_to_pass = []
    curves = []
    finals = []
    for r in range(runs):
        seq = [rng.choice(day_pnls) for _ in range(horizon)]
        res = simulate_eval(seq, plan)
        if res["result"] == "PASS":
            pass_n += 1; days_to_pass.append(res["days"])
        elif res["result"] == "FAIL":
            fail_n += 1
        eq = np.cumsum(seq)
        finals.append(float(eq[-1]))
        if r < 400:
            curves.append(eq)
    curves = np.array(curves)
    pct = {str(q): [round(float(x), 1) for x in np.percentile(curves, q, axis=0)] for q in (5, 25, 50, 75, 95)}
    # funded-stage payout simulation (sim funded: balance starts 0, MLL -2000, buffer, 50% consistency)
    payouts = funded_payouts(day_pnls, plan, rng, runs=min(1000, runs))
    return {
        "runs": runs, "horizon": horizon,
        "pass_prob": round(pass_n / runs * 100, 1),
        "fail_prob": round(fail_n / runs * 100, 1),
        "open_prob": round((runs - pass_n - fail_n) / runs * 100, 1),
        "median_days_to_pass": float(np.median(days_to_pass)) if days_to_pass else None,
        "p90_days_to_pass": float(np.percentile(days_to_pass, 90)) if days_to_pass else None,
        "bands": pct,
        "final_p50": round(float(np.median(finals)), 2),
        "final_p5": round(float(np.percentile(finals, 5)), 2),
        "final_p95": round(float(np.percentile(finals, 95)), 2),
        "funded": payouts,
    }


def funded_payouts(day_pnls, plan, rng, runs=1000, horizon=120):
    total_paid = []
    n_payouts = []
    blown = 0
    for _ in range(runs):
        bal, peak = 0.0, 0.0
        mll = -plan["mll"]
        lock = plan["lock_above"] if plan.get("lock_above") is not None else float("inf")
        cycle = []
        paid, cnt = 0.0, 0
        last_payout_bal = 0.0
        for k in range(horizon):
            dp = rng.choice(day_pnls)
            bal += dp
            if bal <= mll:
                blown += 1
                break
            peak = max(peak, bal)
            mll = min(max(mll, peak - plan["mll"]), lock)
            if dp != 0:
                cycle.append(dp)
            profit_cycle = bal - last_payout_bal
            qualifying = sum(1 for x in cycle if x > 0)
            best = max(cycle) if cycle else 0
            if (bal >= plan["buffer"] + plan["payout_min"] and profit_cycle >= plan["payout_min"]
                    and qualifying >= plan["payout_min_days"] and profit_cycle > 0 and best <= plan["consistency"] * profit_cycle):
                amt = min(plan["payout_max"], bal - plan["buffer"])
                if amt >= plan["payout_min"]:
                    paid += amt * plan["split"]
                    cnt += 1
                    bal -= amt
                    last_payout_bal = bal
                    cycle = []
                    if cnt >= 5:
                        break
        total_paid.append(paid)
        n_payouts.append(cnt)
    return {
        "avg_paid_to_trader": round(float(np.mean(total_paid)), 2),
        "median_paid": round(float(np.median(total_paid)), 2),
        "avg_payouts": round(float(np.mean(n_payouts)), 2),
        "p_at_least_one": round(sum(1 for c in n_payouts if c >= 1) / runs * 100, 1),
        "p_all_five": round(sum(1 for c in n_payouts if c >= 5) / runs * 100, 1),
        "blow_rate": round(blown / runs * 100, 1),
        "horizon_days": horizon,
    }


def equity_curve(trades: list, start: float):
    out = [{"t": trades[0]["entry_t"] - 60, "eq": start}] if trades else []
    eq = start
    for t in trades:
        eq += t["pnl"]
        out.append({"t": t["exit_t"], "eq": round(eq, 2)})
    return out
