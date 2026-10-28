"""Rank the 1m grid (tools/scalp_mr_search.py) honestly: pick on 2026 H1 only, then look at H2 and the 2021-25 5m
reference of the same rule.

  python tools/scalp_mr_check.py rank        # top H1 picks with their H2 (the out-of-sample check), overfit count
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools import scalp_mr_lib as L  # noqa: E402
from tools import scalp_mr_search as G  # noqa: E402


def load(tf="1m"):
    return json.load(open(os.path.join(G.OUT, f"mr_grid_{tf}.json")))


def key(r):
    return f"{r['fam']}|{json.dumps(r['p'], sort_keys=True)}|{r['sim']['win']}|rr{r['sim']['rr']}|mb{r['sim']['maxbars']}"


def ok(s, tpw=5.0, n=60):
    return s.get("n", 0) >= n and s.get("tpw", 0) >= tpw


def rank(R, top=30, tpw=5.0):
    c = [r for r in R if ok(r["H1"], tpw)]
    c.sort(key=lambda r: -r["H1"]["net_r"])
    print(f"{len(R)} configs, {len(c)} with >= {tpw}/wk in H1")
    pos1 = [r for r in c if r["H1"]["net_r"] > 0]
    both = [r for r in pos1 if r["H2"].get("net_r", -1) > 0]
    print(f"H1 net > 0: {len(pos1)}; of those H2 net > 0: {len(both)} ({100 * len(both) / max(len(pos1), 1):.0f}%)")
    for r in c[:top]:
        a, b = r["H1"], r["H2"]
        print(f"{a['net_r']:7.1f}R pf{a['pf']:5.2f} {a['tpw']:5.1f}/wk w{a['win']:4.1f} | H2 {b.get('net_r', 0):7.1f}R "
              f"pf{b.get('pf', 0):5.2f} {b.get('tpw', 0):5.1f}/wk | {key(r)}")
    return c


def by_family(R, tpw=5.0):
    fams = sorted({r["fam"] for r in R})
    for f in fams:
        c = [r for r in R if r["fam"] == f and ok(r["H1"], tpw)]
        p1 = [r for r in c if r["H1"]["net_r"] > 0]
        p12 = [r for r in p1 if r["H2"].get("net_r", -1) > 0]
        m1 = np.median([r["H1"]["avg_r"] for r in c]) if c else None
        m2 = np.median([r["H2"].get("avg_r", 0) for r in c]) if c else None
        print(f"{f:8s} n={len(c):5d} H1>0 {len(p1):4d}  both>0 {len(p12):4d}  median avgR H1 {m1} H2 {m2}")


if __name__ == "__main__":
    R = load(sys.argv[2] if len(sys.argv) > 2 else "1m")
    by_family(R)
    rank(R)
