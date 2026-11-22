"""Fleet v2 noise check (post-hoc, labelled): paired per-path net6 differences vs N=0 at the same budget, with standard errors.
    python -X utf8 research/fleet/noise_v2.py -> research/fleet/noise_v2.json"""
import json, os, sys
import numpy as np
from multiprocessing import Pool
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import fleet2 as G

CELLS = [(300, 2, "BASE"), (300, 3, "BASE"), (300, 5, "LU"), (500, 3, "BASE"), (500, 5, "LU"), (800, 5, "LU")]


def job(a):
    span, = a
    P = G.U.mc_paths(G.SOA.data()["S"], span, 1000, length=G.F.LEN, seed=23)
    out = {}
    for b in (300, 500, 800):
        base = np.array([r["o6"] - r["f6"] for r in (G.run_path2(s, b, 0, "LU") for s in P)])
        out[f"{b}|0"] = (float(base.mean()), float(base.std() / 1000 ** 0.5))
        for bb, n, o in CELLS:
            if bb != b:
                continue
            x = np.array([r["o6"] - r["f6"] for r in (G.run_path2(s, b, n, o) for s in P)])
            d = x - base
            out[f"{b}|{n}|{o}"] = (float(d.mean()), float(d.std() / 1000 ** 0.5), float((d > 0).mean() * 100))
    return span, out


if __name__ == "__main__":
    with Pool(3) as p:
        res = dict(p.map(job, [(s,) for s in G.R.SPANS]))
    json.dump(res, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "noise_v2.json"), "w"), indent=1)
    print(json.dumps(res, indent=1))
