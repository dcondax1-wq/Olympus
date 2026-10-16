"""Follow-up to study_regime_night1: is the expectancy governor skill or just 'smaller size on a losing system'?

    python study_regime_night2.py [--from YYYY-MM-DD] [--to YYYY-MM-DD] [--boot 3000]

1. Sensitivity grid of the expectancy governor (window W, threshold, cut) and the no-runner governor on NQ and ES taken trades
   (sample A, emulated sizing exactly as in night1; er10 rule kept and dropped).
2. Placebo: on each market, cut the SAME NUMBER of trades at random (2,000 draws) and compare the governor's lift with that
   distribution. A governor with real timing beats the placebo; one that only shrinks a losing system does not.
3. Regime-agnostic cost/benefit: block-bootstrap synthetic trade sequences (blocks of 5 trades) from NQ and from ES and apply
   the governor: expected cost when the market looks like NQ, expected saving when it looks like ES.
4. Which trades drive the "drop the er10 rule" result on NQ.
Real CME futures only (NQ, ES). Nothing in engine/ is changed.
"""
from __future__ import annotations

import argparse
from multiprocessing import Pool

import numpy as np

from engine.instruments import INSTRUMENTS
from study_regime_night1 import _job, resize, cur_rule, metrics, RISK

MARKETS = ("NQ", "ES")


def gov_exp(rs, exits, entries, W, thr, cut):
    """rs: closed-trade R list in order; returns multipliers. Uses only trades closed before each entry."""
    out = []
    for i in range(len(rs)):
        done = [rs[j] for j in range(i) if exits[j] <= entries[i]]
        last = done[-W:]
        out.append(cut if len(last) >= W and np.mean(last) < thr else 1.0)
    return out


def gov_run(rs, tg, exits, entries, N, cut):
    out = []
    for i in range(len(rs)):
        done = [j for j in range(i) if exits[j] <= entries[i]]
        k = 0
        for j in reversed(done):
            if rs[j] >= 2 or tg[j]:
                break
            k += 1
        out.append(cut if k >= N else 1.0)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="a", default=None)
    ap.add_argument("--to", dest="z", default=None)
    ap.add_argument("--boot", type=int, default=3000)
    args = ap.parse_args()
    inr = lambda d: (not args.a or d >= args.a) and (not args.z or d <= args.z)
    rng = np.random.default_rng(11)
    with Pool(2) as pool:
        res = {s: v for s, k, v in pool.map(_job, [(s, "full") for s in MARKETS])}
    L = [f"# study_regime_night2 output (range {args.a or 'start'} .. {args.z or 'end'})"]
    P = L.append
    seqs = {}
    for sym in MARKETS:
        spec = INSTRUMENTS[sym]
        trs = sorted([t for t in res[sym]["trades"] if inr(t["day"])], key=lambda t: t["entry_t"])
        nd = len([d for d in res[sym]["days"] if inr(d["date"])])
        rs = [t["pnl_r"] for t in trs]
        tg = [t["exit_reason"] == "TARGET" for t in trs]
        ex = [t["exit_t"] for t in trs]
        en = [t["entry_t"] for t in trs]
        seqs[sym] = rs
        def pnl(mults, keep_cur=True):
            return [resize(t, m * (cur_rule(t) if keep_cur else 1.0), spec) for t, m in zip(trs, mults)]
        base = pnl([1.0] * len(trs))
        bnet = sum(p for p in base if p is not None)
        P(f"\n## {sym}: {len(trs)} full-size trades, {nd} sessions, baseline (current rule) net {bnet:+,.0f}")
        P("\n### 1. Governor sensitivity (er10 rule kept). cells: lift $ vs current / trades cut")
        P("| governor | cut x0.5 | cut x0.25 |")
        P("|---|---|---|")
        rows = []
        for W in (5, 8, 10, 15, 20):
            for thr in (0.0, -0.1, -0.25):
                cells = []
                for cut in (0.5, 0.25):
                    m = gov_exp(rs, ex, en, W, thr, cut)
                    v = pnl(m)
                    lift = sum(x or 0 for x in v) - bnet
                    cells.append(f"{lift:+,.0f} / {sum(1 for x in m if x < 1)}")
                    rows.append((f"exp W{W} <{thr}", cut, m, lift))
                P(f"| expectancy last {W} < {thr:+.2f}R | {cells[0]} | {cells[1]} |")
        for N in (3, 4, 5, 6, 8):
            cells = []
            for cut in (0.5, 0.25):
                m = gov_run(rs, tg, ex, en, N, cut)
                v = pnl(m)
                lift = sum(x or 0 for x in v) - bnet
                cells.append(f"{lift:+,.0f} / {sum(1 for x in m if x < 1)}")
                rows.append((f"no-runner N{N}", cut, m, lift))
            P(f"| no-runner N{N} | {cells[0]} | {cells[1]} |")

        P("\n### 2. Placebo: same number of trades cut at random (2,000 draws)")
        P("| governor | cut | trades cut | governor lift $ | placebo median $ | placebo 5-95% | P(placebo >= governor) |")
        P("|---|---|---|---|---|---|---|")
        for name, cut, m, lift in rows:
            if not (name in ("exp W10 <0.0", "exp W5 <0.0", "exp W15 <0.0", "no-runner N5", "no-runner N6", "no-runner N4") and cut == 0.5):
                continue
            k = sum(1 for x in m if x < 1)
            if k == 0:
                P(f"| {name} | x{cut} | 0 | +0 | - | - | - |")
                continue
            pl = []
            for _ in range(2000):
                idx = rng.choice(len(trs), size=k, replace=False)
                mm = np.ones(len(trs)); mm[idx] = cut
                pl.append(sum(x or 0 for x in pnl(list(mm))) - bnet)
            pl = np.array(pl)
            P(f"| {name} | x{cut} | {k} | {lift:+,.0f} | {np.median(pl):+,.0f} | [{np.percentile(pl, 5):+,.0f}, {np.percentile(pl, 95):+,.0f}] | "
              f"{(pl >= lift).mean():.2f} |")

        P("\n### 4. Trades where the current er10 rule bites (full size vs half size)")
        P("| day | dir | grade | R | exit | $ full | $ current |")
        P("|---|---|---|---|---|---|---|")
        for t, b in zip(trs, base):
            if cur_rule(t) < 1:
                P(f"| {t['day']} | {t['dir']:+d} | {t['grade']} | {t['pnl_r']:+.2f} | {t['exit_reason']} | {t['pnl']:+,.0f} | "
                  f"{'skipped (qty 0)' if b is None else f'{b:+,.0f}'} |")

    P("\n## 3. Block-bootstrap synthetic sequences (60 trades, blocks of 5, R units at 1R per trade)")
    P("| source | governor | mean lift R | 5% | 95% | P(lift > 0) | share of trades cut |")
    P("|---|---|---|---|---|---|---|")
    for sym, rs in seqs.items():
        rs = np.array(rs)
        for gname, fn in (("exp W10 <0 x0.5", lambda r: gov_exp(list(r), list(range(len(r))), list(range(1, len(r) + 1)), 10, 0.0, 0.5)),
                          ("exp W5 <0 x0.5", lambda r: gov_exp(list(r), list(range(len(r))), list(range(1, len(r) + 1)), 5, 0.0, 0.5)),
                          ("no-runner N5 x0.5", lambda r: gov_run(list(r), [x >= 2 for x in r], list(range(len(r))), list(range(1, len(r) + 1)), 5, 0.5)),
                          ("no-runner N6 x0.5", lambda r: gov_run(list(r), [x >= 2 for x in r], list(range(len(r))), list(range(1, len(r) + 1)), 6, 0.5))):
            lifts, cutshare = [], []
            for _ in range(args.boot):
                starts = rng.integers(0, max(1, len(rs) - 5), size=12)
                seq = np.concatenate([rs[s:s + 5] for s in starts])
                m = np.array(fn(seq))
                lifts.append(float(((m - 1) * seq).sum()))
                cutshare.append(float((m < 1).mean()))
            lifts = np.array(lifts)
            P(f"| {sym}-like | {gname} | {lifts.mean():+.2f} | {np.percentile(lifts, 5):+.2f} | {np.percentile(lifts, 95):+.2f} | "
              f"{(lifts > 0).mean():.2f} | {np.mean(cutshare):.0%} |")
    print("\n".join(L))


if __name__ == "__main__":
    main()
