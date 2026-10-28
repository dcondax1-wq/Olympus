"""Grid search of mean-reversion scalps (research). Pick on 2026 H1 (Jan-Jun, 1m), check on H2 (Jul-Oct 16, 1m), then the
2021-25 5m reference (tools/scalp_mr_check.py).

  python tools/scalp_mr_search.py            # -> research/scalp/mr_grid_1m.json (every config, H1 + H2 stats)
"""
from __future__ import annotations

import itertools
import json
import multiprocessing as mp
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import scalp_mr_lib as L  # noqa: E402
from tools import scalp_mr_sig as S  # noqa: E402

OUT = os.path.join(L.ROOT, "research", "scalp")
WINDOWS = {"lon": (180, 300), "nyo": (570, 660), "am": (570, 720), "lunch": (690, 810), "pm": (810, 930), "rth": (570, 930),
           "all": (180, 930)}


def signals():
    for k, m, an, cf, tg, tr in itertools.product((1.5, 2.0, 2.5, 3.0), (2, 4), ("session", "rth"), ("inside", "turn"),
                                                 ("vwap", "sd1", "r"), ("none", "with", "against")):
        yield ("vwap", dict(k=k, m=m, anchor=an, confirm=cf, tgt=tg, trend=tr))
    lvsets = (("pd",), ("on",), ("asia",), ("lon",), ("or",), ("ib",), ("pd", "on"), ("asia", "lon"), ("pd", "on", "asia", "lon"),
              ("pd", "on", "asia", "lon", "or", "ib"))
    for lv, m, mp_, tg, tr in itertools.product(lvsets, (2, 5, 10), (8.0, 20.0), ("r", "vwap"), ("none", "with", "against")):
        yield ("levels", dict(levels=lv, m=m, maxpen=mp_, tgt=tg, trend=tr))
    for rnd, m, tr in itertools.product((50, 100), (1, 3), ("none", "with", "against")):
        yield ("round", dict(levels=(), rnd=rnd, m=m, maxpen=8.0, trend=tr))
    for n, lo, m, tr, tg in itertools.product((2, 3, 7), (5, 10, 20), (2, 4), ("none", "with", "against"), ("r", "ema", "vwap")):
        yield ("rsi", dict(n=n, lo=lo if n < 7 else lo + 10, m=m, trend=tr, tgt=tg))
    for k, e, m, tr, tg in itertools.product((2.0, 3.0, 4.0), ("ema20", "ema50"), (2, 4), ("none", "with", "against"), ("r", "ema")):
        yield ("stretch", dict(k=k, ema=e, m=m, trend=tr, tgt=tg))
    for k, an, ss, tr in itertools.product((2.0, 2.5, 3.0), ("session", "rth"), (0.5, 1.0), ("none", "with", "against")):
        yield ("bandlim", dict(k=k, anchor=an, stop_sd=ss, trend=tr))


def make(F, fam, p):
    if fam == "vwap":
        return S.sig_vwap(F, **p)
    if fam in ("levels", "round"):
        return S.sig_levels(F, **p)
    if fam == "rsi":
        return S.sig_rsi(F, **p)
    if fam == "stretch":
        return S.sig_stretch(F, **p)
    if fam == "bandlim":
        return S.sig_band_limit(F, **p)
    raise ValueError(fam)


def sims(p):
    fixed_tgt = p.get("tgt") in ("vwap", "sd1", "ema") or "k" in p and "stop_sd" in p
    rrs = (None,) if fixed_tgt else (0.75, 1.0, 1.5, 2.0)
    for w, rr, mb, be in itertools.product(WINDOWS, rrs, (15, 45), (0.0,)):
        yield dict(win=w, rr=rr or 1.0, maxbars=mb, be_r=be)


F = None


def _job(item):
    fam, p = item
    sig = make(F, fam, p)
    rows = []
    for sp in sims(p):
        T = L.simulate(F, sig, rr=sp["rr"], maxbars=sp["maxbars"], be_r=sp["be_r"], ent=WINDOWS[sp["win"]], max_day=8)
        h1 = L.stats(T, F, "H1"); h2 = L.stats(T, F, "H2")
        rows.append({"fam": fam, "p": {k: (list(v) if isinstance(v, tuple) else v) for k, v in p.items()}, "sim": sp, "H1": h1, "H2": h2})
    return rows


def main(tf="1m", procs=4):
    global F
    F = L.frame(tf)
    items = list(signals())
    print(len(items), "signals", flush=True)
    t0 = time.time()
    out = []
    with mp.get_context("fork").Pool(procs) as pool:
        for k, rows in enumerate(pool.imap_unordered(_job, items, chunksize=4)):
            out.extend(rows)
            if k % 200 == 0:
                print(k, len(out), round(time.time() - t0), flush=True)
    os.makedirs(OUT, exist_ok=True)
    json.dump(out, open(os.path.join(OUT, f"mr_grid_{tf}.json"), "w"))
    print("configs", len(out), round(time.time() - t0), "s")


if __name__ == "__main__":
    main(*(sys.argv[1:2] or ["1m"]))
