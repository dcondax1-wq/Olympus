"""Dead hours per pillar (research/hours/DESIGN.md). PAPER RESEARCH ONLY.
    python -X utf8 research/hours/hours.py  -> research/hours/results.json
The windows are picked on 2021-11..2024 and FROZEN before any hold-out is scored (results.json["pick"]).
"""
from __future__ import annotations

import collections
import datetime as dt
import gzip
import json
import os
import random
import sys
from zoneinfo import ZoneInfo

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "research", "portfolio"))
import portfolio as PF  # noqa: E402

OUT = os.path.join(HERE, "results.json")
ET = ZoneInfo("America/New_York")
PICK = ("2021-11-01", "2024-12-31")
HOLD = {"2025": ("2025-01-01", "2025-12-31"), "Jan-Jun 2026": ("2026-01-01", "2026-06-30"), "Jul-Oct 2026": ("2026-07-01", "2026-12-31")}
BOOKS = {"LIT": ("lit", "LIT"), "ATLAS EMA": ("atlas", "EMA"), "ATLAS MACD": ("atlas", "MACD"), "ATLAS S/R": ("atlas", "S/R"),
         "BLITZ": ("blitz", "BLITZ")}
DRAWS = 2000


def slot(ts):
    t = dt.datetime.fromtimestamp(int(ts), ET)
    return t.hour * 2 + t.minute // 30


def sname(k):
    return f"{k // 2:02d}:{30 * (k % 2):02d}"


def inside(d, span):
    return span[0] <= d <= span[1]


def pf(x):
    x = np.asarray(x, float)
    g, l = x[x > 0].sum(), -x[x < 0].sum()
    return float(g / l) if l else None


def stats(T, span, sessions):
    S = [t for t in T if inside(t["day"], span)]
    days = [d for d in sessions if inside(d, span)]
    p = np.array([t["usd"] for t in S]) if S else np.zeros(0)
    eq = np.cumsum(p) if len(p) else np.zeros(1)
    dd = float((eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min()) if len(p) else 0.0
    by = collections.defaultdict(lambda: [0.0, 0.0, 0])
    for t in S:
        b = by[t["day"]]
        b[0] += t["usd"]; b[1] = min(b[1], b[0], b[0]); b[2] += 1
    dp = np.array([by[d][0] for d in days]); dl = np.array([min(by[d][1], by[d][0], 0) for d in days])
    ev = {a: PF.evals(dp, dl, A) for a, A in PF.ACCTS.items()} if len(days) else {}
    return {"n": len(S), "tpw": round(len(S) / (len(days) / 5), 2) if days else 0, "pf": round(pf(p), 2) if pf(p) else None,
            "net": round(float(p.sum())), "per_month": round(float(p.sum()) / (len(days) / 21)) if days else 0, "max_dd": round(dd),
            "evals": ev}


def run(say=print):
    rows = [json.loads(x) for x in gzip.open(os.path.join(ROOT, "research", "learn", "lessons.jsonl.gz"), "rt", encoding="utf-8")]
    rows = [r for r in rows if r.get("span") in ("2021-25", "H1", "H2") and r.get("entry_t")]
    sessions = sorted({r["day"] for r in rows})
    books = {}
    for b, (p, m) in BOOKS.items():
        books[b] = [{"day": r["day"], "slot": slot(r["entry_t"]), "usd": float(r.get("usd") or 0)} for r in rows
                    if r["pillar"] == p and r.get("member") == m]
    # ---------------- PICK (2021-11..2024 only), frozen
    pick = {}
    for b, T in books.items():
        P = [t for t in T if inside(t["day"], PICK)]
        hours = sorted({t["slot"] for t in T if inside(t["day"], PICK)})
        lo, hi = hours[0], hours[-1]
        best = None
        for L in (1, 2, 3):
            for a in range(lo, hi - L + 2):
                W = set(range(a, a + L))
                x = [t["usd"] for t in P if t["slot"] in W]
                if len(x) < 20 or sum(x) >= 0 or (pf(x) or 0) >= 0.80:
                    continue
                key = (sum(x), L)
                if best is None or key < best[0]:
                    best = (key, a, L, len(x), round(pf(x), 2))
        pick[b] = None if best is None else {"from": sname(best[1]), "to": sname(best[1] + best[2]), "slots": [best[1], best[2]],
                                             "pick_usd": round(best[0][0]), "pick_n": best[3], "pick_pf": best[4],
                                             "hours": [lo, hi]}
        say(f"PICK {b}: {pick[b]}")
    res = {"made": "2026-11-24", "design": "research/hours/DESIGN.md", "pick": pick, "frozen_before_holdouts": True, "books": {}}
    # ---------------- hold-outs
    rnd = random.Random(7)
    for b, T in books.items():
        w = pick[b]
        if not w:
            res["books"][b] = {"window": None, "verdict": "no dead window on PICK"}
            continue
        a, L = w["slots"]
        W = set(range(a, a + L))
        T2 = [t for t in T if t["slot"] not in W]
        o = {"window": f"{w['from']}-{w['to']} ET", "spans": {}}
        gain = 0.0
        for h, sp in HOLD.items():
            s0, s1 = stats(T, sp, sessions), stats(T2, sp, sessions)
            g = s1["net"] - s0["net"]
            gain += g
            o["spans"][h] = {"today": s0, "skip": s1, "gain": g, "skipped": s0["n"] - s1["n"]}
        lo, hi = w["hours"]
        HT = [t for t in T if any(inside(t["day"], sp) for sp in HOLD.values())]
        beat = 0
        for _ in range(DRAWS):
            ra = rnd.randint(lo, max(lo, hi - L + 1))
            RW = set(range(ra, ra + L))
            gr = -sum(t["usd"] for t in HT if t["slot"] in RW)
            beat += gr >= gain
        o["placebo_p"] = round(beat / DRAWS, 4)
        o["gain_all_holdouts"] = round(gain)
        why = [f"{h} {o['spans'][h]['gain']:+,} $" for h in HOLD if o["spans"][h]["gain"] <= 0]
        if o["placebo_p"] >= 0.05:
            why.append(f"placebo p {o['placebo_p']}")
        o["verdict"] = "needs-owner-yes" if not why else "FAIL"
        o["why"] = why
        res["books"][b] = o
        say(f"{b} skip {o['window']}: {o['verdict']} | " + " | ".join(
            f"{h} {o['spans'][h]['today']['net']:,} -> {o['spans'][h]['skip']['net']:,} (skipped {o['spans'][h]['skipped']})" for h in HOLD)
            + f" | p {o['placebo_p']} | {'; '.join(why)}")
    res["passed"] = [b for b, o in res["books"].items() if o.get("verdict") == "needs-owner-yes"]
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1, default=float)
    say(f"passed: {res['passed'] or 'none'}")
    return res


if __name__ == "__main__":
    run()
