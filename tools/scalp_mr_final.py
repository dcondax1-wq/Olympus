"""Final scoring of the mean-reversion scalp candidates: money, eval speed, cost share, runs in research/runs/, the best
one's per-trade list (research/scalp/mr_best_trades.json).

  python tools/scalp_mr_final.py          # prints the tables, stores runs mr_scalp_*, writes research/scalp/mr_final.json
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import scalp_mr_lib as L  # noqa: E402
from tools import scalp_mr_sig as S  # noqa: E402

OUT = os.path.join(L.ROOT, "research", "scalp")

# name -> (title, signal fn, signal kwargs, sim kwargs on 1m)   (5m: maxbars // 5, same windows)
CANDS = {
    "vwap25": ("RTH-VWAP 2.5-sd band fade, 1.5R, 45-min time stop", S.sig_vwap,
               dict(k=2.5, m=2, anchor="rth", confirm="inside", tgt="r", trend="none"),
               dict(rr=1.5, maxbars=45, ent=(570, 930), max_day=8)),
    "vwap25_flat": ("RTH-VWAP 2.5-sd band fade on flat-VWAP (range) days, 1.5R", S.sig_vwap,
                    dict(k=2.5, m=2, anchor="rth", confirm="inside", tgt="r", trend="vwflat0.5"),
                    dict(rr=1.5, maxbars=45, ent=(570, 930), max_day=8)),
    "levels_am": ("Level sweep-and-reclaim (PDH/L, overnight, Asia, London, OR, IB) 09:30-12:00, target VWAP", S.sig_levels,
                  dict(levels=("pd", "on", "asia", "lon", "or", "ib"), m=2, maxpen=20.0, tgt="vwap", trend="none"),
                  dict(rr=1.0, maxbars=45, ent=(570, 720), max_day=8)),
}
EXTRA = os.path.join(OUT, "mr_extra_cands.json")      # optional more candidates from the 5m grid (same format, fn by name)


def trades(name, tf):
    title, fn, sk, mk = CANDS[name]
    F = L.frame(tf)
    mk = dict(mk)
    if tf == "5m":
        mk["maxbars"] = max(1, mk["maxbars"] // 5)
    return F, L.simulate(F, fn(F, **sk), **mk)


def cost_share(T, plan, risk_usd):
    P = L.PLANS[plan]
    q = np.array([L.size_q(x, risk_usd, P["max_q"]) for x in T["risk"].values])
    gross = q * (T["pts"].values + 2 * L.TICK) * L.PT_USD          # before commission and the market slippage
    cost = q * (L.COMM + 2 * L.TICK * L.PT_USD)
    g = float(gross.sum())
    return (round(float(cost.sum()) / g, 2) if g > 0 else None), round(float(cost.sum())), round(g)


def score(name, risk25=100.0, risk50=200.0):
    F1, T1 = trades(name, "1m")
    F5, T5 = trades(name, "5m")
    out = {}
    for span, F, T in (("H1", F1, T1), ("H2", F1, T1), ("2021-25", F5, T5), ("2025", F5, T5), ("2021-24", F5, T5)):
        s = L.stats(T, F, span)
        a, z = L.SPANS[span]
        t = T[(T.day >= a) & (T.day <= z)]
        m25 = L.path_money(T, F, span, "25k", risk25); m50 = L.path_money(T, F, span, "50k", risk50)
        cs, cost, gross = cost_share(t, "25k", risk25) if len(t) else (None, 0, 0)
        e25 = L.eval_sim(T, F, span, "25k", risk_usd=risk25)
        e50 = L.eval_sim(T, F, span, "50k", risk_usd=risk50)
        out[span] = {**s, "money25": m25, "money50": m50, "cost25": cost, "gross25": gross, "costs_eat": cs, "eval25": e25, "eval50": e50}
    return out, (F1, T1), (F5, T5)


def store(name, res, F1, T1, F5, T5, status, verdict):
    from tools import runlib as rl
    rows = []
    for F, T in ((F5, T5[T5.day < "2026-01-01"]), (F1, T1[T1.day >= "2026-01-01"])):
        P = L.PLANS["50k"]
        for r in T.itertuples(index=False):
            q = L.size_q(r.risk, 200.0, P["max_q"])
            if q <= 0:
                continue
            pnl = q * (r.pts * L.PT_USD - L.COMM)
            rows.append({"day": r.day, "entry_t": int(r.entry_t), "exit_t": int(r.exit_t), "dir": int(r.dir), "r": float(r.r),
                         "pnl": round(float(pnl), 2), "risk_pts": float(r.risk), "qty": q, "risk_usd": round(q * r.risk * L.PT_USD, 2),
                         "half": 0, "exit": L.KINDS[int(r.kind)], "trigger": name, "mfe": None, "mae": float(r.mae),
                         "bars_held": int(r.exit_i - r.ent_i + 1), "regime": None, "mult": 1.0,
                         "low": -q * float(r.mae) * L.PT_USD})
    sess = sorted(set(F5["day"][(F5["day"] < "2026-01-01") & (F5["dow"] < 5)]) | set(F1["day"][(F1["day"] >= "2026-01-01") & (F1["dow"] < 5)]))
    S_ = rl.score(rows, sess)
    title, fn, sk, mk = CANDS[name]
    rl.save(f"mr_scalp_{name}", f"MR scalp: {title}", "other", "Is there a mean-reversion scalp (5+/wk) that makes money after costs?",
            params={"signal": fn.__name__, **{k: (list(v) if isinstance(v, tuple) else v) for k, v in sk.items()},
                    **{k: (list(v) if isinstance(v, tuple) else v) for k, v in mk.items()}},
            sizing={"risk_usd": 200, "plan": "builder_50k static", "note": "2026 = 1m bars, 2021-25 = 5m bars"},
            trades=rows, scored=S_, status=status, verdict=verdict,
            notes=json.dumps({k: {kk: v[kk] for kk in ("n", "tpw", "pf", "avg_r", "eval25", "money25")} for k, v in res.items()}),
            writeup="research/writeups/scalp-mean-reversion.md", tags=["scalp", "mean-reversion", "third-strategy"])


def main():
    allres = {}
    for name in CANDS:
        res, (F1, T1), (F5, T5) = score(name)
        allres[name] = res
        print("==", name, CANDS[name][0])
        for span, s in res.items():
            print(f"  {span:8s} n{s['n']:5d} {s['tpw']:5.1f}/wk win{s.get('win')} avgR{s.get('avg_r')} pf{s.get('pf')} | 25K $100 risk: net "
                  f"${s['money25']['net']:,} ${s['money25']['per_month']:,}/mo dd ${s['money25']['dd']:,} costs ${s['cost25']:,} "
                  f"(gross ${s['gross25']:,}) | eval25 p10/f10 {s['eval25']['p10']}/{s['eval25']['f10']} med {s['eval25']['pass_med']} "
                  f"| eval50 p10/f10 {s['eval50']['p10']}/{s['eval50']['f10']}")
        ok = all(res[s].get("net_r", -1) > 0 for s in ("H1", "H2", "2021-25"))
        store(name, res, F1, T1, F5, T5, "promising" if ok else "rejected",
              "holds in H1, H2 and 2021-25" if ok else "does not hold in all of H1 / H2 / 2021-25 after costs")
    json.dump(allres, open(os.path.join(OUT, "mr_final.json"), "w"), indent=1, default=float)
    best = max(allres, key=lambda k: min(allres[k]["H1"].get("net_r", -1e9), allres[k]["H2"].get("net_r", -1e9)))
    F1, T1 = trades(best, "1m")
    n = L.save_trades(T1[T1.day >= "2026-01-01"], F1, os.path.join(OUT, "mr_best_trades.json"))
    print("best (by worse 2026 half):", best, n, "trades -> research/scalp/mr_best_trades.json")


if __name__ == "__main__":
    main()
