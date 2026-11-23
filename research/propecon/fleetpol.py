"""Prop economics (2026-11-23), stage 2: the whole business under a budget. PAPER RESEARCH ONLY.
Extends research/fleet/fleet.py (v1, today's plan) with policy levers: the eval / funded book per account type (lanes + size),
payout ask, Builder close-after-N, Rapid close-at-$X, a buy stagger (max 1 new eval per week), and the re-buy stop.
Every account of a fleet steps the SAME market path. Start = the owner's 4 MFFU accounts as of the board 2026-11-23 (sunk).
"""
from __future__ import annotations
import json, os, sys, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE); sys.path.insert(0, os.path.join(ROOT, "research", "fleet"))
import unit as X  # noqa  (loads book.py + patches)
import fleet as F  # noqa
B, R, U, SOA = X.B, X.R, X.U, X.SOA
F.TYPES["LU"] = ("lucid_pro_50k", "B01 LIT only", "lucid", 3)     # Lucid cap 3 ASSUMED (fleet v2), price $126 ASSUMED
MO = 21
_SP = {}


def spec(key, bk, pol):
    """bk = None -> today's book for the type (fleet.py), else a unit.py policy tuple."""
    k = (key, bk, pol)
    if k in _SP:
        return _SP[k]
    plan = F.TYPES[key][0]
    if bk is None:
        sp = F.spec(key, None, pol)
    else:
        pmax = 4 if (plan.startswith("mffu_builder") and pol == "P4") else None
        sp = X.build(plan, *bk, pmax=pmax)
    _SP[k] = sp
    return sp


def start_fleet(pol):
    """The owner's 4 MFFU accounts (board 2026-11-23 10:12 ET), today's books (sunk cost, no fee)."""
    out = []
    sp = F.spec("B50", "B09 LIT eval, LIT + ATLAS once funded", pol); e = sp["ev"]()
    e.bal, e.peak, e.floor, e.s, e.dtr = -786.0, 168.0, -1832.0, 12, 9
    out.append(F.Acct("B50", sp, e=e))
    sp = F.spec("B25", "B02 ATLAS only", pol); f = sp["fund"]()
    f.bal, f.peak, f.floor = 401.0, 401.0, -599.0
    out.append(F.Acct("B25", sp, f=f))
    sp = F.spec("R25", F.B03, pol); out.append(F.Acct("R25", sp, e=sp["ev"]()))
    sp = F.spec("B25", "B01 LIT only", pol); e = sp["ev"](); e.bal, e.peak, e.floor, e.s, e.dtr = 24.0, 24.0, -976.0, 3, 1
    out.append(F.Acct("B25", sp, e=e))
    return out


def run_path(seq, P, budget, L=126):
    blist, stop, pol = P["list"], P.get("stop", "S0"), P.get("pol", "P4")
    books, stag, rclose, caps = P.get("books", {}), P.get("stagger", 0), P.get("rclose"), P.get("caps", {})
    accts = start_fleet(pol)
    avail, fees, owner, streak, stopped, live, fn_pays, turn, last_buy, pays = 0.0, 0.0, 0.0, 0, False, None, 0, 0, -99, 0
    monthly = []
    for k, si in enumerate(seq[:L]):
        if k % MO == 0:
            avail += budget
            monthly.append([0.0, 0.0])
        if not stopped and (not stag or k - last_buy >= stag):
            alt = P.get("alt", len(blist) == 2 and blist in (("R50", "FN"), ("FN", "R50")))
            while True:
                order = list(blist[turn % len(blist):] + blist[:turn % len(blist)]) if alt else list(blist)
                bought = False
                for t in order:
                    plan, _, firm, cap = F.TYPES[t]
                    cap = caps.get(t, cap)
                    price = R.PLANS[plan]
                    if price > avail + 1e-9 or (firm == "mffu" and live) or (firm == "fn" and fn_pays >= 15):
                        continue
                    same = sum(1 for x in accts if x.key == t)
                    mffu = sum(1 for x in accts if x.firm == "mffu")
                    if same >= cap or (firm == "mffu" and mffu >= 5):
                        continue
                    sp = spec(t, books.get(t), pol)
                    accts.append(F.Acct(t, sp, e=sp["ev"]()))
                    avail -= price; fees += price; monthly[-1][1] += price
                    bought, turn, last_buy = True, turn + 1, k
                    break
                if not bought or stag:
                    break
        keep = []
        for a in accts:
            if a.firm == "mffu" and live:
                continue
            B.CFG.clear(); B.CFG.update(a.sp["knobs"])
            if a.e is not None:
                r, _ = a.e.step(a.sp["BYe"][si])
                if r == "pass":
                    a.e, a.wait = None, R.GAP
                elif r in ("fail", "stuck"):
                    streak += 1
                    continue
                keep.append(a); continue
            if a.f is None:
                a.wait -= 1
                if a.wait <= 0:
                    a.f = a.sp["fund"]()
                keep.append(a); continue
            ev, x, cum = a.f.step(a.sp["BYf"][si])
            if ev in ("paid", "grad"):
                owner += x; pays += 1; streak = 0; monthly[-1][0] += x
                if a.firm == "fn":
                    fn_pays += 1
            if a.rapid and cum is not None and cum >= 10000.0:
                live = live or ("rapid10k", k)
            if rclose and a.rapid and sum(a.f.pays) >= rclose:
                continue
            if ev == "lost":
                streak += 1; continue
            if ev == "grad":
                if a.builder and pol == "P5":
                    live = live or ("builder5", k)
                continue
            keep.append(a)
        accts = keep
        if stop == "S3" and streak >= 3:
            stopped = True
    B.CFG.clear()
    return owner, fees, pays, bool(live), monthly


def summ(rows):
    n = np.array([r[0] - r[1] for r in rows]); mo = len(rows[0][4])
    m = np.array([[a - b for a, b in r[4]] for r in rows])
    return {"per_month": round(float(n.mean()) / mo), "net6": round(float(n.mean())), "p10": round(float(np.percentile(n, 10))),
            "p50": round(float(np.median(n))), "p90": round(float(np.percentile(n, 90))), "owner": round(float(np.mean([r[0] for r in rows]))),
            "fees": round(float(np.mean([r[1] for r in rows]))), "pays": round(float(np.mean([r[2] for r in rows])), 1),
            "live": round(100 * float(np.mean([r[3] for r in rows])), 1), "p_neg": round(100 * float((n < 0).mean()), 1),
            "se": round(float(n.std() / np.sqrt(len(n)))), "month_mean": [round(float(x)) for x in m.mean(0)],
            "per_eval_dollar": round(float(np.mean([r[0] for r in rows]) / max(1e-9, np.mean([r[1] for r in rows]))), 2)}


def run(P, budget, span, n, seed=23, L=126):
    return summ([run_path(s, P, budget, L) for s in X.paths(span, n, L, seed)])
