"""Owner 2026-10-18: "I'm not resetting it at all" (one-time fee). Eventual pass / fail of one MFFU Builder 50K eval with NO
reset, for the eval sizings (engine/sizing.lit_qty, exactly as the live loop calls it; commission $1.90, 1 tick on stops):
config C (two_week) to the end, two_week for 10 sessions then another mode, the eval mode only, and others. Exact starts on
every 2026 session of the half (played on that half's sessions; open at the end of data counted as open) + a Monte Carlo of
2,000 evals x 120 sessions in 5-session blocks from the half. Pick on H1, check on H2. Paper only.
  python tools/lit_eventual.py      -> research/lit/eventual.json
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import sizing as SZ  # noqa: E402
from engine.lit import qty_for  # noqa: E402
from tools import lit_2wk as W  # noqa: E402

PV, COMM, SLIP = 2.0, SZ.TW_COMM, 0.25
TGT, MLL, DLL, LOCK = 3000.0, 2000.0, 1000.0, 100.0
LM = json.load(open(os.path.join(ROOT, "live_model.json")))["lit_sizing"]
C = {k: LM[k] for k in ("two_week", "safe_cap", "eval_ref_stop", "fast_ref_stop")}


def cfgs():
    return {"C two_week to the end": {**C, "mode": "two_week"},
            "C 10 sessions, then eval": {**C, "mode": "two_week", "two_week_until": 10, "after_mode": "eval"},
            "C 10 sessions, then safe_eval": {**C, "mode": "two_week", "two_week_until": 10, "after_mode": "safe_eval"},
            "C 15 sessions, then eval": {**C, "mode": "two_week", "two_week_until": 15, "after_mode": "eval"},
            "eval mode only": {**C, "mode": "eval"},
            "normal LIT size only": {**C, "mode": "normal"}}


def run(cfg, seq, by, horizon):
    bal = peak = 0.0
    floor = -MLL
    for k, si in enumerate(seq[:horizon]):
        cum = 0.0
        for j, t in enumerate(by[si]):
            if cum <= -DLL:
                break
            st = {"profit": bal, "cum": cum, "room": bal + cum - floor, "session": k + 1, "n_today": j}
            base = qty_for(t["risk"])
            m0 = max(1, int(base * (t.get("wk_m") or 1.0) + 1e-9)) if base else 0
            q = SZ.lit_qty(m0, {"risk_pts": t["risk"], "tgt_pts": t["tgt"], "size_mult": t.get("wk_m", 1.0)}, cfg,
                           room=st["room"], state=st, learning=None)["qty"] if m0 else 0
            if q <= 0:
                continue
            pnl = t["pts"] * PV * q - COMM * q
            low = min(0.0, t["w1"] * PV * q - COMM * q, pnl)
            if cum + low <= -DLL:
                pnl = -DLL - cum - SLIP * PV * q
                low = pnl
            if bal + cum + low <= floor:
                return "FAIL", k + 1
            cum += pnl
        bal += cum
        if bal <= floor:
            return "FAIL", k + 1
        peak = max(peak, bal)
        floor = min(max(floor, peak - MLL), LOCK)
        if bal >= TGT:
            return "PASS", k + 1
    return "OPEN", min(len(seq), horizon)


def summ(res):
    n = len(res)
    p = [d for r, d in res if r == "PASS"]
    return {"n": n, "p10": round(100.0 * sum(1 for d in p if d <= 10) / n, 1),
            "f10": round(100.0 * sum(1 for r, d in res if r == "FAIL" and d <= 10) / n, 1),
            "p20": round(100.0 * sum(1 for d in p if d <= 20) / n, 1),
            "pass": round(100.0 * len(p) / n, 1), "fail": round(100.0 * sum(1 for r, _ in res if r == "FAIL") / n, 1),
            "open": round(100.0 * sum(1 for r, _ in res if r == "OPEN") / n, 1),
            "pass_med": float(np.median(p)) if p else None, "pass_p75": float(np.percentile(p, 75)) if p else None}


def main():
    D = W.data()
    out = {}
    rng = np.random.default_rng(5)
    seqs = {}
    for span in ("H1", "H2"):
        a, z = W.span_idx(span)
        S = []
        for _ in range(2000):
            s = []
            while len(s) < 120:
                b = int(rng.integers(a, z - 5 + 1))
                s.extend(range(b, b + 5))
            S.append(s[:120])
        seqs[span] = S
    for nm, cfg in cfgs().items():
        o = {}
        for span in ("H1", "H2"):
            a, z = W.span_idx(span)
            ex = [run(cfg, list(range(k, z)), D["by"], 10 ** 6) for k in range(a, z - 10)]   # starts that see 10+ sessions
            o[span] = summ(ex)
            o["MC " + span] = summ([run(cfg, s, D["by"], 120) for s in seqs[span]])
        out[nm] = o
        print(nm, json.dumps(o), flush=True)
    json.dump(out, open(os.path.join(ROOT, "research", "lit", "eventual.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
