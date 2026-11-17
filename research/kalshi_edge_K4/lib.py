"""K4 shared maths: Kalshi fee, P&L per $1, cluster bootstrap, streaks, $/month."""
import math
import random


def fee_per_contract(p, stake=10.0, rate=0.07):
    """Kalshi taker fee 0.07 x C x p x (1-p), rounded UP to the cent on the whole order of C = floor(stake / p)
    contracts, returned per contract."""
    c = max(1, int(stake // max(p, 0.01)))
    return math.ceil(round(rate * c * p * (1 - p) * 100, 6)) / 100.0 / c


def pnl_per_dollar(p, won, stake=10.0, rate=0.07):
    """Buy one side at price p (the ask): profit per $1 of cost (price + fee)."""
    fe = fee_per_contract(p, stake, rate)
    return ((1.0 if won else 0.0) - p - fe) / (p + fe)


def cluster_boot(vals, clusters, n=2000, seed=7):
    """mean of vals and a 95% cluster bootstrap range (resample clusters with replacement)."""
    if not vals:
        return (float("nan"),) * 3
    by = {}
    for v, c in zip(vals, clusters):
        by.setdefault(c, []).append(v)
    groups = [(sum(g), len(g)) for g in by.values()]
    rnd = random.Random(seed)
    k = len(groups)
    means = []
    for _ in range(n):
        s = m = 0
        for _ in range(k):
            a, b = groups[rnd.randrange(k)]
            s += a
            m += b
        means.append(s / m)
    means.sort()
    return sum(vals) / len(vals), means[int(0.025 * n)], means[int(0.975 * n)]


def tstat(vals, clusters):
    by = {}
    for v, c in zip(vals, clusters):
        by.setdefault(c, []).append(v)
    sums = [sum(g) for g in by.values()]
    ns = [len(g) for g in by.values()]
    N = sum(ns)
    if len(sums) < 3:
        return 0.0
    mu = sum(sums) / N
    var = sum((s - mu * n) ** 2 for s, n in zip(sums, ns)) * len(sums) / (len(sums) - 1) / N ** 2
    return mu / math.sqrt(var) if var > 0 else 0.0


def max_losing_streak(wins_in_time_order):
    best = cur = 0
    for w in wins_in_time_order:
        cur = 0 if w else cur + 1
        best = max(best, cur)
    return best


def summary(rows, days):
    """rows: dicts with r (pnl per $1), cl (cluster), won, ts. days = calendar days covered."""
    rows = sorted(rows, key=lambda x: x["ts"])
    v = [x["r"] for x in rows]
    m, lo, hi = cluster_boot(v, [x["cl"] for x in rows])
    per_month = len(rows) / max(days, 1) * 30.4
    return {"n": len(rows), "edge": m, "lo": lo, "hi": hi, "t": tstat(v, [x["cl"] for x in rows]),
            "win": (sum(x["won"] for x in rows) / len(rows)) if rows else None,
            "trades_month": per_month, "usd_month_3": m * 3 * per_month if rows else 0,
            "usd_month_10": m * 10 * per_month if rows else 0, "max_lose_streak": max_losing_streak([x["won"] for x in rows])}
