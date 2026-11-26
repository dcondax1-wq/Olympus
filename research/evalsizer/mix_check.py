"""Sensitivity check (NOT pre-registered; asked by day-moretrades): markets that mix 2026 and 2021-25 blocks.
Each 5-session block comes from 2026 (Jan-Oct) with prob w, else from 2021-25.  python -X utf8 research/evalsizer/mix_check.py"""
import json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sizer as Z  # noqa: E402
R, U, AR, SOA, BC = Z.R, Z.U, Z.AR, Z.SOA, Z.BC


def mix_paths(S, w, n, length, seed):
    U.SPAN["N26"] = ("2026-01-01", "2026-10-31")
    a1, z1 = U.span_ix(S, "N26")
    a0, z0 = U.span_ix(S, "REF")
    rng = np.random.default_rng(seed)
    P = []
    for _ in range(n):
        s = []
        while len(s) < length:
            a, z = (a1, z1) if rng.random() < w else (a0, z0)
            b = int(rng.integers(a, z - U.BLOCK + 1))
            s.extend(range(b, b + U.BLOCK))
        P.append(s[:length])
    return P


AR.rapid_patch(AR.T_at(10))
S = SOA.data()["S"]
out = {}
for w in (0.5, 0.25):
    PE, PF = mix_paths(S, w, 1000, R.H_EVAL, 7), mix_paths(S, w, 1000, R.LEN, 23)
    for plan in ("mffu_builder_50k", "mffu_builder_25k"):
        sp = R.spec(plan)
        for v in ("T0", "R25", "R30", "PR1", "R50"):
            Z.POL.clear(); Z.POL.update(id=v, kelly=0.27)
            e, s = R.eval_run(sp, PE), BC.slot_full(sp, PF)
            out[f"{w}|{plan}|{v}"] = {"eval": e, "slot": s}
            print(f"w2026={w} {plan:18s} {v:4s} pass {e['pass']}/{e['fail']}% ~{e['med_days']}d  net ${s['net_6m']}  ${s['net_per_eval']}/ev", flush=True)
Z.POL.clear(); Z.POL["id"] = "T0"
json.dump(out, open(os.path.join(HERE, "mix_check.json"), "w"), indent=1)
