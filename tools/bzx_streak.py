"""BLITZ research (2026-10-31 evening): size the next BLITZ trade of a day by how the day's previous BLITZ trade ended
("in-day streak size"). Research only: nothing here changes engine/blitz.py, engine/account_c.py or any model file.

The rule (eval size only; the funded 25K keeps today's size): on top of today's later-break eval size (first break x0.5,
later break x1.75, blitz_25k_pick_v2), a trade that follows a LOSING BLITZ trade on the same day is sized x m_loss, one
that follows a WINNING trade x m_win; the day's first trade is unchanged. Known before the entry (BLITZ holds one
position at a time), so no look-ahead.

Pick on 2026 H1 (slot $ a month, then 2-week pass), check on 2026 H2 and 2021-25 (5m reference), control = the same
multipliers on SHUFFLED previous-trade outcomes (10 seeds): if the shuffled flags do as well, the outcome carries no
information.

    python -X utf8 tools/bzx_streak.py          # -> research/runs/bzx_streak.json (runlib) + research/scalp/bzx_streak.json
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

A = X.A
N_MC = int(os.environ.get("BZS_N", "1000"))
GRID = [(1.0, 1.0), (0.5, 1.0), (0.0, 1.0), (1.0, 1.5), (0.5, 1.5), (1.5, 1.0), (1.0, 0.5)]


def prev_flags(T):
    """per trade: 0 = first BLITZ trade of its day, -1 = the day's previous trade lost, +1 = it won (pnl_pm, costs in)."""
    out, last_day, last = [], None, 0
    for t in T:
        if t["day"] != last_day:
            out.append(0)
        else:
            out.append(-1 if last < 0 else 1)
        last_day, last = t["day"], float(t["pnl_pm"])
    return np.array(out)


def mults(T, m_loss, m_win, flags=None):
    f = prev_flags(T) if flags is None else flags
    m = np.ones(len(T))
    m[f < 0], m[f > 0] = m_loss, m_win
    return m


def score(T, S, m_loss, m_win, flags=None, n=N_MC):
    lb = A.nth_m(T, *X.LB)
    sm = mults(T, m_loss, m_win, flags)
    keep = sm > 0                                     # x0 = skip the trade
    Te = [dict(t, mult=float(a * b)) for t, a, b, k in zip(T, lb, sm, keep) if k]
    ev = X.eval_scorex(Te, S, X.EZ_LB)
    sl = X.lifeX(Te, T, S, X.EZ_LB, X.FZ0, n=n)
    rv = A.rview([t for t, k in zip(T, keep) if k], S, (lb * sm)[keep], usd=150.0)
    return {"ev": {k: ev.get(k) for k in ("p10", "f10", "dec10", "p15", "f15", "pass_med", "slow_pass")},
            "slot_pm": sl["life_pm"], "slot_lose": sl["life_lose"], "money150": rv}


def main():
    t0 = time.time()
    TT, SP = X.prep()
    out = {"built": time.strftime("%Y-%m-%d %H:%M"), "n_mc": N_MC, "grid": []}
    facts = {}
    for sp, (T, S) in SP.items():
        f = prev_flags(T)
        R = np.array([t["pnl_pm"] / t["risk_pm"] for t in T])
        facts[sp] = {"n": len(T), "first": int((f == 0).sum()), "after_loss": int((f < 0).sum()), "after_win": int((f > 0).sum()),
                     "R_first": round(float(R[f == 0].mean()), 3) if (f == 0).any() else None,
                     "R_after_loss": round(float(R[f < 0].mean()), 3) if (f < 0).any() else None,
                     "R_after_win": round(float(R[f > 0].mean()), 3) if (f > 0).any() else None}
    out["facts"] = facts
    print("facts", json.dumps(facts), flush=True)
    for ml, mw in GRID:
        row = {"m_loss": ml, "m_win": mw}
        for sp, (T, S) in SP.items():
            row[sp] = score(T, S, ml, mw)
        out["grid"].append(row)
        print(ml, mw, " | ".join(f"{sp} slot ${row[sp]['slot_pm']} 2w {row[sp]['ev']['p10']}/{row[sp]['ev']['f10']} "
                                 f"$150 ${row[sp]['money150'].get('net')} PF {row[sp]['money150'].get('pf')}" for sp in SP), f"{time.time() - t0:.0f}s", flush=True)
    base = out["grid"][0]
    # H1 pick: best H1 slot $ a month among the non-baseline cells whose H1 2-week fail is no worse than today's
    cand = [r for r in out["grid"][1:] if r["H1"]["ev"]["f10"] <= base["H1"]["ev"]["f10"] + 0.5]
    pick = max(cand or out["grid"][1:], key=lambda r: r["H1"]["slot_pm"])
    out["pick"] = {"m_loss": pick["m_loss"], "m_win": pick["m_win"]}
    ctrl = {}
    for sp, (T, S) in SP.items():
        f = prev_flags(T)
        vals = []
        for seed in range(10):
            g = f.copy()
            idx = np.where(g != 0)[0]
            g[idx] = np.random.default_rng(100 + seed).permutation(g[idx])
            vals.append(score(T, S, pick["m_loss"], pick["m_win"], flags=g, n=N_MC))
        ctrl[sp] = {"slot_pm_mean": round(float(np.mean([v["slot_pm"] for v in vals]))),
                    "slot_pm_seeds": [v["slot_pm"] for v in vals],
                    "p10_mean": round(float(np.mean([v["ev"]["p10"] for v in vals])), 1),
                    "f10_mean": round(float(np.mean([v["ev"]["f10"] for v in vals])), 1),
                    "net150_mean": round(float(np.mean([v["money150"]["net"] for v in vals])))}
        print("control", sp, json.dumps(ctrl[sp]), f"{time.time() - t0:.0f}s", flush=True)
    out["control"] = ctrl
    good = all(pick[sp]["slot_pm"] > base[sp]["slot_pm"] and pick[sp]["slot_pm"] > ctrl[sp]["slot_pm_mean"] for sp in ("H2", "R")) \
        and all(pick[sp]["ev"]["f10"] <= base[sp]["ev"]["f10"] + 0.5 for sp in ("H2", "R"))
    out["verdict"] = "paper lead (ships OFF)" if good else "rejected"
    os.makedirs(os.path.join(ROOT, "research", "scalp"), exist_ok=True)
    with open(os.path.join(ROOT, "research", "scalp", "bzx_streak.json"), "w", encoding="utf-8") as fh:
        json.dump(A._j(out), fh, indent=1)
    from tools import runlib as rl
    mt = {}
    for sp, (T, S) in SP.items():
        lb = A.nth_m(T, *X.LB)
        for t, a, b in zip(T, lb, mults(T, pick["m_loss"], pick["m_win"])):
            mt[t["entry_t"]] = float(a * b)
    allT = [t for sp in SP for t in SP[sp][0]]
    sess = sorted({d for sp in SP for d in SP[sp][1]})
    rows = X.store_trades(allT, lambda t: mt.get(t["entry_t"], 1.0))
    summ = {sp: {"today": {"slot_pm": base[sp]["slot_pm"], **base[sp]["ev"], **{k: base[sp]["money150"].get(k) for k in ("net", "per_month", "pf", "dd", "tpw", "avg_r")}},
                 "pick": {"slot_pm": pick[sp]["slot_pm"], **pick[sp]["ev"], **{k: pick[sp]["money150"].get(k) for k in ("net", "per_month", "pf", "dd", "tpw", "avg_r")}},
                 "control": ctrl[sp]} for sp in ("H1", "H2", "R")}
    rl.save("bzx_streak", f"BLITZ in-day streak size (x{pick['m_loss']} after a same-day loss, x{pick['m_win']} after a win) - {out['verdict']}",
            "risk", "Does the result of the day's previous BLITZ trade tell how big the next one should be (eval 25K)?",
            params={**X.K.TODAY, "streak": out["pick"], "grid": GRID, "n_mc": N_MC, "summary": summ, "facts": facts},
            sizing={"usd_per_trade": X.USD, "eval_25k": X.EZ_LB, "funded_25k": X.FZ0, "later_break": X.LB},
            trades=rows, scored=rl.score(rows, sess), status="rejected" if out["verdict"] == "rejected" else "promising",
            verdict=out["verdict"], notes="tools/bzx_streak.py; stored rows = $150 x later-break x streak multiplier",
            writeup="blitz-streak-size-2026-10-31.md", tags=["blitz", "account_c", "sizing", "eval"])
    print("pick", out["pick"], "verdict", out["verdict"], f"{time.time() - t0:.0f}s")
    return out


if __name__ == "__main__":
    main()
