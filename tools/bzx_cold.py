"""BLITZ research (2026-10-31, 19:40): an equity-curve size on BLITZ's OWN recent trades ("cold-streak size"). Research
only: nothing here changes engine/blitz.py, engine/account_c.py or any model file.

The rule (eval size only, on top of the later-break size; the funded 25K keeps today's size): when the sum of R of
BLITZ's previous K trades (all closed before this entry; BLITZ holds one position) is below 0, the trade is sized
x m_cold, else x m_warm. Grid K = 5 / 10 / 20, (m_cold, m_warm) = (0.5, 1), (1.5, 1), (1, 1.5).

Same gate as tools/bzx_streak.py: pick on 2026 H1 (best slot $ a month with a 2-week fail no worse than today's), check
on 2026 H2 and 2021-25, control = the picked sizes on SHUFFLED cold / warm flags (10 seeds, 1,000 paths everywhere).

    python -X utf8 tools/bzx_cold.py          # -> research/scalp/bzx_cold.json + run bzx_cold
"""
from __future__ import annotations

import json
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import bzx_edge as X  # noqa: E402
from tools import bzx_streak as Z  # noqa: E402

A = X.A
N_MC = Z.N_MC
GRID = [(k, mc, mw) for k in (5, 10, 20) for mc, mw in ((0.5, 1.0), (1.5, 1.0), (1.0, 1.5))]


def cold_flags(T, k):
    """-1 = the previous k BLITZ trades (R, costs in) sum below 0 ("cold"), +1 = otherwise; fewer than k before -> +1."""
    R = np.array([t["pnl_pm"] / t["risk_pm"] for t in T])
    out = np.ones(len(T), int)
    for i in range(len(T)):
        if i >= k and R[i - k:i].sum() < 0:
            out[i] = -1
    return out


def main():
    t0 = time.time()
    TT, SP = X.prep()
    out = {"built": time.strftime("%Y-%m-%d %H:%M"), "n_mc": N_MC, "grid": []}
    base = {"k": 0, "m_cold": 1.0, "m_warm": 1.0}
    for sp, (T, S) in SP.items():
        base[sp] = Z.score(T, S, 1.0, 1.0)
    out["grid"].append(base)
    facts = {}
    for k, mc, mw in GRID:
        row = {"k": k, "m_cold": mc, "m_warm": mw}
        for sp, (T, S) in SP.items():
            f = cold_flags(T, k)
            row[sp] = Z.score(T, S, mc, mw, flags=f)
            if (mc, mw) == (0.5, 1.0):
                R = np.array([t["pnl_pm"] / t["risk_pm"] for t in T])
                facts[f"{sp}_k{k}"] = {"cold": int((f < 0).sum()), "warm": int((f > 0).sum()),
                                       "R_cold": round(float(R[f < 0].mean()), 3) if (f < 0).any() else None,
                                       "R_warm": round(float(R[f > 0].mean()), 3) if (f > 0).any() else None}
        out["grid"].append(row)
        print(k, mc, mw, " | ".join(f"{sp} slot ${row[sp]['slot_pm']} 2w {row[sp]['ev']['p10']}/{row[sp]['ev']['f10']} "
                                    f"$150 ${row[sp]['money150'].get('per_month')}/mo PF {row[sp]['money150'].get('pf')}" for sp in SP),
              f"{time.time() - t0:.0f}s", flush=True)
    out["facts"] = facts
    print("facts", json.dumps(facts), flush=True)
    cand = [r for r in out["grid"][1:] if r["H1"]["ev"]["f10"] <= base["H1"]["ev"]["f10"] + 0.5]
    pick = max(cand or out["grid"][1:], key=lambda r: r["H1"]["slot_pm"])
    out["pick"] = {"k": pick["k"], "m_cold": pick["m_cold"], "m_warm": pick["m_warm"]}
    ctrl = {}
    for sp, (T, S) in SP.items():
        f = cold_flags(T, pick["k"])
        vals = [Z.score(T, S, pick["m_cold"], pick["m_warm"], flags=np.random.default_rng(200 + s).permutation(f)) for s in range(10)]
        ctrl[sp] = {"slot_pm_mean": round(float(np.mean([v["slot_pm"] for v in vals]))), "slot_pm_seeds": [v["slot_pm"] for v in vals],
                    "p10_mean": round(float(np.mean([v["ev"]["p10"] for v in vals])), 1),
                    "f10_mean": round(float(np.mean([v["ev"]["f10"] for v in vals])), 1),
                    "pm150_mean": round(float(np.mean([v["money150"]["per_month"] for v in vals])))}
        print("control", sp, json.dumps(ctrl[sp]), flush=True)
    out["control"] = ctrl
    good = all(pick[sp]["slot_pm"] > base[sp]["slot_pm"] and pick[sp]["slot_pm"] > ctrl[sp]["slot_pm_mean"] for sp in ("H2", "R")) \
        and all(pick[sp]["ev"]["f10"] <= base[sp]["ev"]["f10"] + 0.5 for sp in ("H2", "R"))
    out["verdict"] = "paper lead (ships OFF)" if good else "rejected"
    with open(os.path.join(ROOT, "research", "scalp", "bzx_cold.json"), "w", encoding="utf-8") as fh:
        json.dump(A._j(out), fh, indent=1)
    from tools import runlib as rl
    mt = {}
    for sp, (T, S) in SP.items():
        lb = A.nth_m(T, *X.LB)
        f = cold_flags(T, pick["k"])
        for t, a, b in zip(T, lb, Z.mults(T, pick["m_cold"], pick["m_warm"], f)):
            mt[t["entry_t"]] = float(a * b)
    allT = [t for sp in SP for t in SP[sp][0]]
    sess = sorted({d for sp in SP for d in SP[sp][1]})
    rows = X.store_trades(allT, lambda t: mt.get(t["entry_t"], 1.0))
    keys = ("net", "per_month", "pf", "dd", "tpw", "avg_r")
    summ = {sp: {"today": {"slot_pm": base[sp]["slot_pm"], **base[sp]["ev"], **{k: base[sp]["money150"].get(k) for k in keys}},
                 "pick": {"slot_pm": pick[sp]["slot_pm"], **pick[sp]["ev"], **{k: pick[sp]["money150"].get(k) for k in keys}},
                 "control": ctrl[sp]} for sp in ("H1", "H2", "R")}
    rl.save("bzx_cold", f"BLITZ cold-streak size (x{pick['m_cold']} when its last {pick['k']} trades sum below 0R, x{pick['m_warm']} else) - {out['verdict']}",
            "risk", "Does BLITZ's own recent run of trades tell how big the next one should be (eval 25K)?",
            params={**X.K.TODAY, "cold": out["pick"], "grid": GRID, "n_mc": N_MC, "summary": summ, "facts": facts},
            sizing={"usd_per_trade": X.USD, "eval_25k": X.EZ_LB, "funded_25k": X.FZ0, "later_break": X.LB},
            trades=rows, scored=rl.score(rows, sess), status="rejected" if out["verdict"] == "rejected" else "promising",
            verdict=out["verdict"], notes="tools/bzx_cold.py; stored rows = $150 x later-break x cold-streak multiplier",
            writeup="blitz-streak-size-2026-10-31.md", tags=["blitz", "account_c", "sizing", "eval"])
    print("pick", out["pick"], "verdict", out["verdict"], f"{time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
