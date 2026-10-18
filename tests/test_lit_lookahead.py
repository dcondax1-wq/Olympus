"""Look-ahead check for engine/lit.py: cut the 5m data at random bars and confirm every LIT setup (and its plan: limit,
stop, target) that exists at that bar is the same as with the full data.

The cut bar N is kept only as a just-opened bar (high = low = close = open, volume 0), so a setup whose entry bar is N may
use N's open but nothing else from it. Compared per setup: every field candidates() returns (sweep, extreme, CISD level,
inducement, displacement, targets, PO3, VIX room, high/low-of-week flag, ...), plus the run_live signal (limit / stop /
target) for the live LIT parameters (live_model.json "lit", loss pack on; --final: lit_final) on 5m bars.

  python -X utf8 -m tests.test_lit_lookahead            # 30 cuts (half of them on 2026 entry bars), about 3 minutes
  python -X utf8 -m tests.test_lit_lookahead --cuts 8   # quicker
1 CPU process.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import lit  # noqa: E402
from engine.data import Bars, load  # noqa: E402

START = "2025-08-01"          # window start (enough history for PMH/PML, PWH/PWL, build-ups and a warm ATR)


def _cut(b: Bars, n: int) -> Bars:
    """Bars 0..n, with bar n reduced to its open (the bar has just started)."""
    x = b.slice(0, n + 1)
    o = x.o.copy(); h = x.h.copy(); l = x.l.copy(); c = x.c.copy(); v = x.v.copy()
    h[-1] = l[-1] = c[-1] = o[-1]; v[-1] = 0.0
    return Bars(x.sym, x.tf, x.t, o, h, l, c, v, x.mod, x.tday, x.dow, x.date_str)


def _norm(z):
    return json.dumps(z, sort_keys=True, default=str)


def main(cuts=30, seed=7, final=False):
    # the live LIT params (live_model.json "lit": lit_final + the loss pack's Monday rule and weekly stop); --final: lit_final
    params = json.load(open(os.path.join(ROOT, "research", "lit", "lit_final.json")))["params"] if final else \
        json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))["lit"]
    P = {**lit.DEFAULTS, **params, "tf": "5m"}
    full = load("NQ", "5m")
    a = int(np.searchsorted(np.array(full.date_str), START))
    B = full.slice(a, len(full))
    Mf = lit.Market(bars=B, extra_boxes=P["extra_boxes"])
    Cf = lit.candidates(Mf, ref=P["ref"])
    Sf = lit.run_live(Mf, Cf, P)["signals"]
    rng = random.Random(seed)
    on_entry = sorted({z["entry_i"] for z in Cf if z["day"] >= "2026"})
    pool = [i for i in range(len(B)) if B.date_str[i] >= "2026" and 120 <= B.mod[i] < 955]
    picks = rng.sample(on_entry, min(len(on_entry), cuts // 2)) + rng.sample(pool, cuts - min(len(on_entry), cuts // 2))
    bad, checked_c, checked_s = [], 0, 0
    for n in sorted(picks):
        k = int(Mf.day_of[n]); s = Mf.days[k][1]
        if n - s < 50:                     # candidates() skips days with < 50 bars (a holiday stub); not a look-ahead question
            continue
        Mt = lit.Market(bars=_cut(B, n), extra_boxes=P["extra_boxes"])
        Ct = lit.candidates(Mt, ref=P["ref"])
        A = {(z["i"], z["dir"]): z for z in Cf if z["entry_i"] <= n}
        Z = {(z["i"], z["dir"]): z for z in Ct}
        for key in set(A) | set(Z):
            checked_c += 1
            if key not in A or key not in Z:
                bad.append(("setup only in " + ("full" if key in A else "cut"), B.date_str[n], int(n), key))
            elif _norm(A[key]) != _norm(Z[key]):
                diff = sorted(f for f in A[key] if _norm(A[key][f]) != _norm(Z[key].get(f)))
                bad.append(("setup differs", B.date_str[n], int(n), key, diff))
        St = {(x["t"], x["dir"]): x for x in lit.run_live(Mt, Ct, P)["signals"]}
        for x in Sf:
            if (x["t"], x["dir"]) in St:
                y = St[(x["t"], x["dir"])]
                checked_s += 1
                for f in ("limit_px", "stop_px", "target_px", "risk_pts", "rr", "target_label", "swept", "how"):
                    if x[f] != y[f]:
                        bad.append(("signal differs", x["day"], int(n), f, x[f], y[f]))
        print(f"cut {B.date_str[n]} bar {n}: setups {len(Z)} ok so far {not bad}", flush=True)
    print(f"setups compared {checked_c}, signals compared {checked_s}, differences {len(bad)}")
    for b_ in bad[:20]:
        print("  ", b_)
    print("PASS" if not bad and checked_c else "FAIL")
    return not bad


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cuts", type=int, default=30)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--final", action="store_true", help="the lit_final params instead of live_model.json lit")
    sys.exit(0 if main(**vars(ap.parse_args())) else 1)
