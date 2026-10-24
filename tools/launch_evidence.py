"""Pre-launch evidence pack numbers (research/lit/launch_evidence.md). Read-only: changes no engine file, no live_model*.json,
stores no run. Recomputes every count in the pack from the stored runs and a fresh engine run_x on live_model.json "lit".

    python -X utf8 tools/launch_evidence.py        # ~1 min; prints the sections A-F
"""
from __future__ import annotations

import collections
import datetime as dt
import hashlib
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
from engine import lit  # noqa: E402
from engine.analytics import PLANS, simulate_eval  # noqa: E402
from tools import runlib as rl  # noqa: E402
from tools import lit_final as F  # noqa: E402
from tools import lit_adopt_combo as AC  # noqa: E402
from tools import lit_big_ideas as BI  # noqa: E402,F401  (patches lit_adv_manage.run_eval with the add-aware one)
from tools import lit_adv_manage as A  # noqa: E402

HALVES = (("2026", "2026-01-01", "2026-12-31"), ("H1", "2026-01-01", "2026-06-30"), ("H2", "2026-07-01", "2026-12-31"))
wd = lambda s: dt.date.fromisoformat(s).weekday()  # noqa: E731
iso = lambda s: dt.date.fromisoformat(s).isocalendar()[:2]  # noqa: E731


def sha(p):
    return hashlib.sha1(open(p, "rb").read()).hexdigest()[:10]


def section_a(m):
    print("== A. labels")
    print(" parameter_hash sha1(json.dumps({'lit','lit_sizing'}, sort_keys=True)):",
          hashlib.sha1(json.dumps({"lit": m["lit"], "lit_sizing": m["lit_sizing"]}, sort_keys=True).encode()).hexdigest())
    print(" sha1(dumps(lit, sort_keys) + dumps(lit_sizing, sort_keys)):",
          hashlib.sha1((json.dumps(m["lit"], sort_keys=True) + json.dumps(m["lit_sizing"], sort_keys=True)).encode()).hexdigest())
    print(" sha1(dumps(lit, sort_keys)):", hashlib.sha1(json.dumps(m["lit"], sort_keys=True).encode()).hexdigest())
    print(" data_key (runlib._data_key, NQ_5m.csv only):", rl._data_key())
    for f in ("NQ_1m.csv", "VIX_1d.csv", "VXN_1d.csv"):
        print(f"  data/{f}: {os.path.getsize('data/' + f)} bytes sha1[:10] {sha('data/' + f)}")
    run = rl.load("lit_live")
    print(" run lit_live params == lit.DEFAULTS + live lit:", run["params"] == {**lit.DEFAULTS, **m["lit"]}, "| sizing:", run["sizing"])


def section_bcd(run):
    C = run["trade_cols"]
    T = [dict(zip(C, r)) for r in run["trades"]]
    D = [dict(zip(run["day_cols"], r)) for r in run["days"]]
    plan = PLANS["builder_50k"]
    for nm, a, z in HALVES:
        TT = [t for t in T if a <= t["day"] <= z]; DD = [x for x in D if a <= x["date"] <= z]
        r = np.array([t["r"] for t in TT]); p = np.array([t["pnl"] for t in TT]); mfe = np.array([t["mfe"] for t in TT])
        print(f"== B/C/D {nm}: {len(TT)} trades, {len(DD)} sessions {DD[0]['date']}..{DD[-1]['date']}, net {p.sum():+,.0f}")
        for k in sorted({t["exit"] for t in TT}):
            g = [t for t in TT if t["exit"] == k]
            print(f"  {k:8s} n={len(g):3d} pnl>0={sum(t['pnl'] > 0 for t in g):3d} net={sum(t['pnl'] for t in g):+9,.0f} "
                  f"avgR={np.mean([t['r'] for t in g]):+.3f} R {min(t['r'] for t in g):+.3f}..{max(t['r'] for t in g):+.3f}")
        print(f"  win pnl>0 {(p > 0).sum()} ({100 * (p > 0).mean():.1f}%) | r>=0.5 {(r >= 0.5).sum()} ({100 * (r >= 0.5).mean():.1f}%) | "
              f"r>=1 {(r >= 1).sum()} ({100 * (r >= 1).mean():.1f}%) | mfe>=0.5R {(mfe >= 0.5).sum()} | mfe>=1R {(mfe >= 1).sum()}")
        wk = collections.Counter(iso(t["day"]) for t in TT); allwk = sorted({iso(x["date"]) for x in DD})
        cal = ((dt.date.fromisoformat(DD[-1]["date"]) - dt.date.fromisoformat(DD[0]["date"])).days + 1) / 7
        print(f"  trades/week: n/(sessions/5) = {len(TT)}/{len(DD) / 5:.1f} = {len(TT) / (len(DD) / 5):.2f}; {len(allwk)} ISO weeks -> "
              f"{len(TT) / len(allwk):.2f}; {cal:.1f} calendar weeks -> {len(TT) / cal:.2f}; weekly counts "
              f"{dict(sorted(collections.Counter(wk[w] for w in allwk).items()))}")
        pn = [x["pnl"] for x in DD]; lo = [x["low"] for x in DD]
        res = [simulate_eval(pn[i:i + 60], plan, lo[i:i + 60]) for i in range(len(DD))]
        for H in (10, 20):
            P_ = sum(x["result"] == "PASS" and x["days"] <= H for x in res); F_ = sum(x["result"] == "FAIL" and x["days"] <= H for x in res)
            full = res[:len(res) - H + 1]
            Pf = sum(x["result"] == "PASS" and x["days"] <= H for x in full); Ff = sum(x["result"] == "FAIL" and x["days"] <= H for x in full)
            print(f"  LIT-size eval {H} sessions, every start (N={len(res)}): pass {P_} fail {F_} open {len(res) - P_ - F_} | "
                  f"full-window starts N={len(full)}: {Pf}/{Ff}/{len(full) - Pf - Ff}")


def section_c_eval(T):
    U = AC.units(T)
    by = A.by_day(U)
    for span in ("H1", "H2"):
        a, z = A.span_ix(span)
        res = [(A.run_eval(list(range(i, min(z, i + 20))), by), z - i) for i in range(a, z)]
        out = []
        for h in (10, 20):
            R = [x for x, av in res if av >= h]
            p = sum(x[0] == "PASS" and x[1] <= h for x in R); f = sum(x[0] == "FAIL" and x[1] <= h for x in R)
            out.append(f"{h} sessions: starts {len(R)} pass {p} fail {f} open {len(R) - p - f}")
        win_days, one_day = set(), 0
        for i in range(a, z - 9):
            keep = []
            r_, n_ = A.run_eval(list(range(i, min(z, i + 20))), by, keep=keep)
            if r_ == "PASS" and n_ <= 10:
                win_days.add(A.S26[i + n_ - 1]); one_day += len({t["day"] for t in keep}) < 2
        blocks = collections.Counter(A.run_eval(list(range(i, i + 10)), by)[0] for i in range(a, z - 9, 10))
        print(f"== C eval path {span}: {len(res)} starts | " + " | ".join(out) + f" | b2b {dict(A.b2b(U, span)[1])} | mc {A.mc(U, span)}")
        print(f"  2-week passes end on {len(win_days)} distinct sessions; passes with 1 traded day {one_day}; "
              f"non-overlapping 10-session blocks {dict(blocks)}")


def section_f(T, P):
    M, Cn = F.market(P["ref"], P["extra_boxes"])
    T26 = [t for t in T if t["day"] >= "2026-01-01"]
    st = collections.Counter()
    for k, x in enumerate(M.ctx):
        if x["date"] >= "2026-01-01" and x["dow"] == 0 and "pdh" in x:
            up = max(j for j in range(x["s"], x["e"]) if M.mod[j] < 930 or M.mod[j] >= 1080)
            st[lit.monday_state(M, k, up)] += 1
            assert wd(M.ctx[k - 1]["date"]) == 4, x["date"]
    print("== F1 Monday rule: 2026 Mondays by state at 15:30 ET", dict(st), "(previous trading day a Friday on every one)")
    T0 = [t for t in F.run({**P, "monday": False}) if t["day"] >= "2026-01-01"]
    for nm, a, z in HALVES:
        on = sum(t["pnl"] for t in T26 if a <= t["day"] <= z); off = sum(t["pnl"] for t in T0 if a <= t["day"] <= z)
        print(f"  {nm}: rule on {on:+,.0f} ({sum(a <= t['day'] <= z for t in T26)} trades) / off {off:+,.0f} "
              f"({sum(a <= t['day'] <= z for t in T0)} trades)")
    n_ok = n_add = 0
    for t in T26:
        d, ee, i = int(t["dir"]), int(t["ext_i"]), int(t["i"])
        body = d * (M.c[ee + 1:i + 1] - M.o[ee + 1:i + 1]) / np.maximum(M.atr[ee + 1:i + 1], 1e-9)
        n_ok += body.max() >= P["disp"]
    for c in Cn:
        if c["day"] >= "2026-01-01":
            d, ee, i = int(c["dir"]), int(c["ext_i"]), int(c["i"])
            body = d * (M.c[ee + 1:i + 1] - M.o[ee + 1:i + 1]) / np.maximum(M.atr[ee + 1:i + 1], 1e-9)
            n_add += bool(len(body)) and np.abs(body).max() >= P["disp"] > body.max()
    print(f"== F2 displacement: 2026 trades with a with-direction body >= {P['disp']} ATR {n_ok}/{len(T26)}; "
          f"2026 candidates an |body| rule would add {n_add}")
    be = [t for t in T26 if t["exit"] == "BE"]
    print("== F3 breakeven: (dir, pts per micro after the exit tick) ->",
          dict(collections.Counter((t["dir"], round((t["pnl"] + lit.COMM * t["qty"]) / (lit.PV * t["qty"]), 2)) for t in be)),
          "| $ per micro", dict(collections.Counter(round(t["pnl"] / t["qty"], 2) for t in be)), f"| total {sum(t['pnl'] for t in be):+.0f}")
    B1, B5 = F.bars(M, "1m"), F.bars(M, "5m")
    gaps = []
    for t in T:                                   # STOP / BE exits whose exit bar opened beyond the stop (filled at stop - 1 tick)
        if t["exit"] in ("STOP", "BE"):
            B = B1 if t.get("tf") == 1 else B5
            d = int(t["dir"]); k = int(np.searchsorted(B.t, int(t["exit_t"]) - B.secs))
            lvl = (t["pnl"] + lit.COMM * t["qty"]) / (lit.PV * t["qty"]) + float(t["entry_px"]) * d + lit.SLIP
            g = lvl - float(B.o[k]) * d
            if g > 1e-9:
                gaps.append((t["day"], t["exit"], d, round(g, 2), t["qty"], round(g * lit.PV * t["qty"], 1)))
    print("   gap-through stop / BE exits (all years):", gaps, f"total ${sum(x[5] for x in gaps):,.1f}")


def main():
    m = json.load(open("live_model.json", encoding="utf-8"))
    section_a(m)
    run = rl.load("lit_live")
    section_bcd(run)
    P = dict(m["lit"])
    T = F.run(P)
    same = [(t["day"], int(t["entry_t"]), t["exit"], round(t["pnl"], 1)) for t in T] == \
           [(r[0], int(r[1]), r[10], round(r[5], 1)) for r in run["trades"]]
    print(f"== engine run_x now == stored run lit_live: {same} ({len(T)} trades)")
    section_c_eval(T)
    section_f(T, P)


if __name__ == "__main__":
    main()
