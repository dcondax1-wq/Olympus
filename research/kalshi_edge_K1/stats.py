"""Shared stats for K1: edge per $1 staked (sum of P&L / sum of stake, after fees and spread) with a cluster bootstrap 95%
range (clusters = settle date / settle time, resampled whole). Deterministic (seeded)."""
import collections, random

MIN_N = 100          # below this many trades in a block a result is "too few", never a verdict
MIN_CLUSTERS = 20


def block(trades, reps=2000, seed=7):
    """trades: [(cluster, pnl_cents, cost_cents)] -> dict"""
    if not trades:
        return {"n": 0}
    by = collections.defaultdict(lambda: [0.0, 0.0, 0, 0])
    for c, p, s in trades:
        b = by[c]
        b[0] += p; b[1] += s; b[2] += 1; b[3] += 1 if p > 0 else 0
    keys = list(by)
    P = sum(by[k][0] for k in keys); S = sum(by[k][1] for k in keys)
    rnd = random.Random(seed)
    est = []
    for _ in range(reps):
        pp = ss = 0.0
        for _ in keys:
            b = by[keys[rnd.randrange(len(keys))]]
            pp += b[0]; ss += b[1]
        est.append(pp / ss if ss else 0.0)
    est.sort()
    n = len(trades)
    return {"n": n, "clusters": len(keys), "won": round(sum(by[k][3] for k in keys) / n, 4),
            "avg_cost_c": round(S / n, 2), "pnl_per_contract_c": round(P / n, 3), "pnl_total_usd_1lot": round(P / 100, 2),
            "edge_per_usd": round(P / S, 4) if S else None,
            "lo95": round(est[int(0.025 * reps)], 4), "hi95": round(est[int(0.975 * reps) - 1], 4),
            "enough": n >= MIN_N and len(keys) >= MIN_CLUSTERS}


def summarize(trades, split):
    """trades with cluster keys comparable to `split` (ISO dates or epoch ints)."""
    tr = [t for t in trades if t[0] < split]
    te = [t for t in trades if t[0] >= split]
    return {"train": block(tr), "test": block(te)}
