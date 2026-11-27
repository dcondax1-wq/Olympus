"""EVAL-ONLY Asia slot on the real eval engines (research/litasia/DESIGN_eval.md, fc401851). PAPER RESEARCH ONLY.
    python -X utf8 research/litasia/eval_only.py [--n 1000] -> research/litasia/eval_only.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
for p in (ROOT, os.path.join(ROOT, "tools"), os.path.join(ROOT, "research", "plans"), HERE):
    sys.path.insert(0, p)
import rank as R  # noqa: E402
import asia as AS  # noqa: E402
from engine.lit import qty_for  # noqa: E402

U, RL, AR, SOA = R.U, R.RL, R.AR, R.SOA
OUT = os.path.join(HERE, "eval_only.json")
TICK = 0.25
PLANS = {"mffu_builder_50k": ("LIT",), "mffu_builder_25k": ("LIT",), "mffu_rapid_eod_25k": ("LIT", "ATLAS")}
MARKETS = ("H1", "H2", "REF", "MIX25", "BAD")
COSTS = (2, 4)


def conv(T, k=0):
    """engine trades (tools/lit_more_entries.run) -> account4_sim's LIT rows; k extra ticks a side on Asia trades."""
    by = {}
    for t in T:
        q = max(1, int(t["qty"]))
        pts = (float(t["pnl"]) / q + 1.40) / 2.0
        risk = float(t["risk_pts"])
        w1 = -float(t["mae"]) * risk
        if k and AS.is_asia(t["entry_t"]):
            pts -= k * TICK * (1 + (0 if AS.tgt(t.get("exit")) else 1))
            w1 -= k * TICK
        base = qty_for(risk)
        by.setdefault(t["day"], []).append({
            "day": t["day"], "risk": risk, "risk_pts": risk, "tgt": abs(float(t["target_px"]) - float(t["entry_px"])),
            "tgt_pts": abs(float(t["target_px"]) - float(t["entry_px"])), "pts": pts, "w1": w1,
            "size_mult": 0.5 if base and q < base else 1.0, "ref": t["day"] < "2026-01-01", "entry_t": int(t["entry_t"]),
            "exit_t": int(t["exit_t"]), "dir": int(t["dir"]), "exit": t.get("exit"), "strat": "LIT",
            "tf": 1 if t["day"] >= "2026-01-01" else 5})
    return by


def by_session(by, S):
    return [sorted(by.get(d, []), key=lambda t: t["entry_t"]) for d in S]


def check(L0, L1):
    """the converter vs the stored ledger stream: same trades, same pts / risk / tgt / size within 1e-6."""
    bad, n = 0, 0
    for a, b in zip(L0, L1):
        if len(a) != len(b):
            bad += 1; continue
        for x, y in zip(a, b):
            n += 1
            if (x["entry_t"] != y["entry_t"] or abs(x["pts"] - y["pts"]) > 1e-6 or abs(x["risk"] - y["risk"]) > 1e-6
                    or abs(x["tgt"] - y["tgt"]) > 1e-6 or x["size_mult"] != y["size_mult"]):
                bad += 1
    return n, bad


def with_lit(L, mix, news=False):
    SOA._D["LIT"] = L
    RL._MB.clear()
    return [list(x) for x in RL.mix_by(mix, news=news)]


def paths(S, market, n, length, seed):
    if market in ("H1", "H2", "REF"):
        return U.mc_paths(S, market, n, length=length, seed=seed)
    rng = np.random.default_rng(seed + (1 if market == "MIX25" else 2))
    a26, z26 = U.span_ix(S, "Y26")
    ar, zr = U.span_ix(S, "REF")
    P = []
    for _ in range(n):
        s = []
        while len(s) < length:
            bad = (rng.random() < 0.25) if market == "MIX25" else (len(s) >= 30)
            a, z = (ar, zr) if bad else (a26, z26)
            b = int(rng.integers(a, z - U.BLOCK + 1))
            s.extend(range(b, b + U.BLOCK))
        P.append(s[:length])
    return P


def eval_stats(sp, PE):
    res = []
    for seq in PE:
        e = sp["ev"]()
        out, used = "open", None
        for k, si in enumerate(seq[:60]):
            r, _ = e.step(sp["BYe"][si])
            if r == "pass":
                out, used = "pass", k + 1; break
            if r in ("fail", "stuck"):
                out, used = "fail", k + 1; break
        res.append((out, used))
    n = len(res)
    f = lambda o, h: round(100.0 * sum(1 for x, u in res if x == o and u <= h) / n, 1)  # noqa: E731
    ps = [u for x, u in res if x == "pass"]
    return {"p10": f("pass", 10), "f10": f("fail", 10), "p21": f("pass", 21), "f21": f("fail", 21),
            "pass_med": float(np.median(ps)) if ps else None}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1000)
    a = ap.parse_args(argv)
    t0 = time.time()
    U.SPAN["Y26"] = ("2026-01-01", "2026-10-16")
    AR.rapid_patch(AR.T_at(10))
    D = SOA.data()
    S = D["S"]
    L_ledger = [list(x) for x in D["LIT"]]
    base_T = AS.M.run(AS.M.LIVE)
    S2 = [[[1080, 120], [120, 1080]], 1]
    asia_T = AS.M.run(AS.M.P_of("full", 2, None, 1.0, {"per_session": S2, "second": {},
                                                         "kz": [[1080, 1440, {"max_rr": 3.0}], [0, 120, {"max_rr": 3.0}]]}))
    L_base = by_session(conv(base_T), S)
    n, bad = check(L_ledger, [[{**t} for t in x] for x in L_base])
    print(f"converter vs the stored ledger: {n} trades, {bad} mismatches [{time.time() - t0:.0f}s]", flush=True)
    assert bad == 0, "converter does not reproduce the ledger: nothing scored"
    L_asia = {k: by_session(conv(asia_T, k), S) for k in COSTS}
    PE = {m: paths(S, m, a.n, 60, 7) for m in MARKETS}
    PF = {m: paths(S, m, a.n, R.LEN, 23) for m in MARKETS}
    out = {"made": "2026-11-26", "design": "research/litasia/DESIGN_eval.md (fc401851)", "n": a.n, "converter_check": [n, bad], "plans": {}}
    for plan, mix in PLANS.items():
        news = plan.startswith("mffu_rapid")
        sp = R.spec(plan)
        BYf = with_lit(L_ledger, mix, news)
        BYe0 = with_lit(L_ledger, mix)
        rows = {}
        for lab, BYe in [("today", BYe0)] + [(f"asia_eval+{k}t", with_lit(L_asia[k], mix)) for k in COSTS]:
            s2 = {**sp, "BYe": BYe, "BYf": BYf}
            rows[lab] = {m: {**eval_stats(s2, PE[m]), **{k: v for k, v in R.slot_run(s2, PF[m]).items()
                                                         if k in ("net_6m", "fees_6m", "owner_6m", "p_lost", "no_pay", "evals")}}
                         for m in MARKETS}
            print(f"{plan} {lab:12s} " + " | ".join(f"{m} 2w {rows[lab][m]['p10']}/{rows[lab][m]['f10']} 30d {rows[lab][m]['p21']}/"
                                                     f"{rows[lab][m]['f21']} med {rows[lab][m]['pass_med']} net6m ${rows[lab][m]['net_6m']}"
                                                     for m in MARKETS) + f" [{time.time() - t0:.0f}s]", flush=True)
        SOA._D["LIT"] = L_ledger
        RL._MB.clear()
        out["plans"][plan] = rows
    gate = {}
    for plan, rows in out["plans"].items():
        b, x = rows["today"], rows["asia_eval+2t"]
        ref_ok = x["REF"]["p10"] >= b["REF"]["p10"] and x["REF"]["p21"] >= b["REF"]["p21"]
        fail_ok = all(x[m][h] <= b[m][h] for m in MARKETS for h in ("f10", "f21"))
        gate[plan] = {"ref_pass_not_worse": ref_ok, "fails_not_up_anywhere": fail_ok, "pass": ref_ok and fail_ok}
    out["gate"] = gate
    out["verdict"] = ("CARD: eval-only Asia slot" if all(g["pass"] for g in gate.values()) else
                      "rejected: " + ", ".join(f"{p} ({'2021-25 pass worse' if not g['ref_pass_not_worse'] else ''}"
                                               f"{' / ' if not g['ref_pass_not_worse'] and not g['fails_not_up_anywhere'] else ''}"
                                               f"{'fails rise' if not g['fails_not_up_anywhere'] else ''})" for p, g in gate.items() if not g["pass"]))
    json.dump(out, open(OUT, "w", encoding="utf-8"), indent=1, default=float)
    print(json.dumps(gate)); print(out["verdict"])


if __name__ == "__main__":
    main()
