"""Build the LIT setup score's pool + its out-of-sample check (research/setupscore/DESIGN.md). PAPER RESEARCH ONLY.

    python -X utf8 tools/setupscore_build.py          # rows (real engine) -> research/setupscore/pool.json + eval.json (+ prints the table)
    python -X utf8 tools/setupscore_build.py --eval   # the holdout check only (from the cached rows)
The pool's "verdict" is set by the pre-registered holdout test ("separates" / "info only"); engine/setup_score reads it.
Nightly: run by tools/forward_paper.py's end (soft) so the pool includes the newest sessions. Tests: tests/test_setup_score.py.
"""
from __future__ import annotations

import datetime as dt
import gzip
import json
import math
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (ROOT, os.path.join(ROOT, "research", "setupscore")):
    if _p not in sys.path:
        sys.path.insert(0, _p)
from engine import setup_score as SS  # noqa: E402

DIR = os.path.join(ROOT, "research", "setupscore")
ROWS = os.path.join(DIR, "rows.json.gz")
POOL = os.path.join(DIR, "pool.json")
EVAL = os.path.join(DIR, "eval.json")
HOLD = {"A Jul-Oct 2026 (pool to 2026-06-30)": ("2026-07-01", "2026-10-31"), "B Jan-Jun 2026 (pool to 2025-12-31)": ("2026-01-01", "2026-06-30")}


def pool_of(rows, upto=None):
    R = [r for r in rows if r.get("r") is not None and (upto is None or r["day"] < upto)]
    cols = ["day", "dir"] + list(SS.FEATS) + ["r"]
    out = []
    for r in R:
        f = SS.feats(mod=r.get("mod"), depth=r.get("depth"), disp=r.get("disp"), idm=r.get("idm"), vix=r.get("vix"))
        out.append([r["day"], int(r["dir"])] + [None if f[c] is None else round(f[c], 4) for c in SS.FEATS] + [round(float(r["r"]), 4)])
    sd = {}
    for j, c in enumerate(SS.FEATS):
        v = [x[2 + j] for x in out if x[2 + j] is not None]
        if len(v) > 1:
            m = sum(v) / len(v)
            sd[c] = round(math.sqrt(sum((a - m) ** 2 for a in v) / (len(v) - 1)), 4)
    return {"cols": cols, "sd": sd, "rows": out}


def _rank(x):
    o = sorted(range(len(x)), key=lambda i: x[i])
    r = [0.0] * len(x)
    i = 0
    while i < len(o):
        j = i
        while j + 1 < len(o) and x[o[j + 1]] == x[o[i]]:
            j += 1
        for k in range(i, j + 1):
            r[o[k]] = (i + j) / 2.0
        i = j + 1
    return r


def spearman(a, b):
    ra, rb = _rank(a), _rank(b)
    n = len(a)
    ma, mb = sum(ra) / n, sum(rb) / n
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    va = math.sqrt(sum((x - ma) ** 2 for x in ra))
    vb = math.sqrt(sum((y - mb) ** 2 for y in rb))
    return cov / (va * vb) if va and vb else 0.0


def auc(score, win):
    pos = [s for s, w in zip(score, win) if w]
    neg = [s for s, w in zip(score, win) if not w]
    if not pos or not neg:
        return None
    c = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return c / (len(pos) * len(neg))


def judge(sc, rr, draws=2000, seed=5):
    n = len(sc)
    rho = spearman(sc, rr)
    rnd = random.Random(seed)
    beat = 0
    for _ in range(draws):
        s2 = sc[:]
        rnd.shuffle(s2)
        beat += spearman(s2, rr) >= rho
    o = sorted(range(n), key=lambda i: sc[i])
    t = n // 3
    lo, hi = [rr[i] for i in o[:t]], [rr[i] for i in o[-t:]]
    return {"n": n, "spearman": round(rho, 3), "p": round(beat / draws, 4), "auc": None if auc(sc, [x > 0 for x in rr]) is None else round(auc(sc, [x > 0 for x in rr]), 3),
            "top_third_r": round(sum(hi) / len(hi), 3) if hi else None, "bottom_third_r": round(sum(lo) / len(lo), 3) if lo else None,
            "top_third_win": round(sum(x > 0 for x in hi) / len(hi), 3) if hi else None,
            "bottom_third_win": round(sum(x > 0 for x in lo) / len(lo), 3) if lo else None,
            "mean_r": round(sum(rr) / n, 3) if n else None}


def evaluate(rows, say=print):
    res = {}
    for nm, (a, z) in HOLD.items():
        P = pool_of(rows, upto=a)
        test = [r for r in rows if a <= r["day"] <= z and r.get("r") is not None]
        out = {}
        for sub, T in (("all with an outcome", test), ("taken only", [r for r in test if r["step"] == 8])):
            sc, rr, bk = [], [], []
            for r in T:
                s = SS.score(SS.feats(mod=r["mod"], depth=r["depth"], disp=r["disp"], idm=r["idm"], vix=r["vix"]), int(r["dir"]), pool=P)
                if s:
                    sc.append(s["avg_r"])
                    rr.append(float(r["r"]))
            out[sub] = judge(sc, rr) if len(sc) >= 9 else {"n": len(sc)}
            j = out[sub]
            say(f"{nm:38s} {sub:20s} n {j['n']:4d} spearman {j.get('spearman')} p {j.get('p')} AUC {j.get('auc')} | top third "
                f"{j.get('top_third_r')}R win {j.get('top_third_win')} vs bottom {j.get('bottom_third_r')}R win {j.get('bottom_third_win')}")
        try:                                            # the pre-registered baseline: the learner's bucket lookup (lit_setups_learn.similar)
            from tools import lit_setups_learn as LS
            sc, rr = [], []
            for r in test:
                b = LS.similar(rows, r, a)
                if b.get("avg_r") is not None:
                    sc.append(float(b["avg_r"]))
                    rr.append(float(r["r"]))
            out["baseline: bucket lookup, all"] = judge(sc, rr) if len(sc) >= 9 else {"n": len(sc)}
            j = out["baseline: bucket lookup, all"]
            say(f"{nm:38s} {'baseline buckets':20s} n {j['n']:4d} spearman {j.get('spearman')} p {j.get('p')} AUC {j.get('auc')} | top third "
                f"{j.get('top_third_r')}R vs bottom {j.get('bottom_third_r')}R")
        except Exception as e:  # noqa: BLE001
            out["baseline: bucket lookup, all"] = {"error": repr(e)}
        res[nm] = out
    sep = all((res[nm]["all with an outcome"].get("spearman") or 0) > 0 and (res[nm]["all with an outcome"].get("p") or 1) < 0.05
              and (res[nm]["all with an outcome"].get("top_third_r") or -9) > (res[nm]["all with an outcome"].get("bottom_third_r") or 9) for nm in HOLD)
    return res, ("separates" if sep else "info only")


def main(argv=None):
    argv = argv or sys.argv[1:]
    if "--eval" not in argv or not os.path.exists(ROWS):
        import rows as RW
        rows, _, _ = RW.build()
        with gzip.open(ROWS, "wt", encoding="utf-8") as fh:
            json.dump([{k: v for k, v in r.items() if k != "swept"} for r in rows], fh, default=float)
    rows = json.load(gzip.open(ROWS, "rt", encoding="utf-8"))
    res, verdict = evaluate(rows)
    P = pool_of(rows)
    doc = {"v": 1, "kind": "lit-setup-score-pool", "design": "research/setupscore/DESIGN.md", "data_end": max(r["day"] for r in rows),
           "built": dt.date.today().isoformat(), "k": SS.K, "features": list(SS.FEATS), "verdict": verdict, "holdouts": res,
           "note": "Display only: never changes which trades are taken.", **P}
    with open(POOL, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, separators=(",", ":"))
    with open(EVAL, "w", encoding="utf-8") as fh:
        json.dump({"verdict": verdict, "holdouts": res, "pool_rows": len(P["rows"]), "data_end": doc["data_end"]}, fh, indent=1)
    print(f"verdict: {verdict} | pool {len(P['rows'])} setups with an outcome, data to {doc['data_end']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
