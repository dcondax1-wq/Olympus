"""ICT lab follow-up (lead 2026-11-25): the CLAUDE.md proof format on the EVAL-SAFE forms of the two findings, with the REAL
engine (research/plans/rank.py + research/onebook/book.py sizers, real fills) and the funded ATLAS replay (tools/atlas_funded.py).
Paper research only; nothing in the live models is changed.

  A   LIT x0.5 when the entry is on the WRONG side of the 00:00 True Day Open (long above / short below; entries before 00:00 = x1)
  B1  ATLAS C2: x1.5 when the entry is in a Silver Bullet hour (03, 10, 14 ET) AND on the 20-day IPDA side, else x1
  B2  ATLAS x0.5 outside the Silver Bullet hours, x1 inside
  C   FUNDED ATLAS 25K only: x1.5 in Silver Bullet hours under the live funded sizing (room share 40% -> 60%, cap $750 -> $1,125;
      the $1,000 best-day guard, the soft daily loss guard and the 2-loss streak rule unchanged)

    python -X utf8 research/ictlab/proof.py [--n 1000]   -> research/ictlab/proof.json
"""
import argparse
import collections
import datetime as dt
import json
import math
import os
import sys
import time
from zoneinfo import ZoneInfo

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(ROOT, "research", "onebook"))
sys.path.insert(0, ROOT)
import logging  # noqa: E402
logging.disable(logging.WARNING)
import book as BK  # noqa: E402  (applies rank's real-fill patch and the book sizers)

R, RL, SOA, SZ, U = BK.R, BK.RL, BK.SOA, BK.SZ, BK.U
ET = ZoneInfo("America/New_York")
U.SPAN["2025"] = ("2025-01-01", "2025-12-31")
SPANS = ("H1", "H2", "REF", "2025")
PLANS = ("mffu_builder_50k", "mffu_builder_25k", "mffu_rapid_eod_25k")
TR = json.load(open(os.path.join(HERE, "trades.json")))


def et_hour(t):
    return dt.datetime.fromtimestamp(int(t), ET).hour


def sb_hour(t):
    return et_hour(t) in (3, 10, 14)


# --------------------------------------------------------------------------------------------- per-trade multipliers
LIT_F = {int(t["t"]): t["f"] for t in TR["LIT"]}
ATL_F = {int(t["t"]): t["f"] for t in TR["ATLAS"]}


def m_A(t):
    if t["strat"] != "LIT":
        return 1.0
    f = LIT_F.get(int(t["entry_t"]))
    if f is None or et_hour(t["entry_t"]) >= 18:        # before 00:00: no True Day Open yet
        return 1.0
    return 1.0 if f["F_TDO"] else 0.5


def m_B1(t):
    if t["strat"] != "ATLAS":
        return 1.0
    f = ATL_F.get(int(t["entry_t"]))
    return 1.5 if f and f["F_SB"] and f["F_IPDA20"] else 1.0


def m_B2(t):
    if t["strat"] != "ATLAS":
        return 1.0
    return 1.0 if sb_hour(t["entry_t"]) else 0.5


VARIANTS = {"A": ("B01 LIT only", m_A, "LIT x0.5 on the wrong side of the 00:00 True Day Open"),
            "B1": ("B02 ATLAS only", m_B1, "ATLAS C2: x1.5 in an SB hour AND on the 20-day IPDA side"),
            "B2": ("B02 ATLAS only", m_B2, "ATLAS x0.5 outside the SB hours")}
MF = {"f": None}
CUR = [None]


class TD(dict):
    """a trade dict that remembers itself when the eval's LIT path reads its risk (SZ.lit_qty gets no trade)."""

    def __getitem__(self, k):
        if k == "risk":
            CUR[0] = self
        return dict.__getitem__(self, k)


def _m(t):
    return 1.0 if MF["f"] is None or t is None else MF["f"](t)


def _scale(q, m):
    if m == 1.0 or q <= 0:
        return q
    return max(1, int(math.floor(q * m + 1e-9)))


_lq, _fq, _qa = SZ.lit_qty, SZ.funded_qty, RL.q_add


def lit_qty(*a, **k):
    r = _lq(*a, **k)
    m = _m(CUR[0])
    if m != 1.0:
        r = dict(r)
        r["qty"] = _scale(int(r["qty"]), m)
    return r


def funded_qty(t, *a, **k):
    return _scale(int(_fq(t, *a, **k)), _m(t))


def q_add(t, z, room, cum, maxq, dll):
    m = _m(t)
    s = t["strat"]
    if m != 1.0 and isinstance(z.get(s), dict):     # the $ budget scaled, every cap of the lane kept (book.py's way)
        z = {**z, s: {"usd": z[s]["usd"] * m, "f": z[s]["f"] * m}}
    return _qa(t, z, room, cum, maxq, dll)


SZ.lit_qty, SZ.funded_qty, RL.q_add = lit_qty, funded_qty, q_add


def wrap(sp):
    for k in ("BYe", "BYf", "BYx"):
        sp[k] = [[TD(t) for t in ts] for ts in sp[k]]
    return sp


# --------------------------------------------------------------------------------------------- fixed-size stats + walk-forward
def fixed(BY, S, span, mf):
    """real days, LIT at its own $800 rule (qty_for), ATLAS at $250, x the multiplier (floor, min 1 micro), costs in."""
    a, z = U.span_ix(S, span)
    pnl, days = [], []
    for si in range(a, z):
        d = 0.0
        for t in BY[si]:
            q0 = RL.qty_for(t["risk"]) if t["strat"] == "LIT" else int(250.0 // ((t["risk"] + R.SLIP) * R.PV + R.COMM))
            if not q0:
                continue
            q = _scale(q0, mf(t) if mf else 1.0)
            p = t["pts"] * R.PV * q - R.COMM * q
            pnl.append(p)
            d += p
        days.append(d)
    p = np.array(pnl) if pnl else np.zeros(1)
    eq = np.cumsum(days)
    gl = -p[p < 0].sum()
    ns = z - a
    return {"trades": len(pnl), "tpw": round(len(pnl) / (ns / 5.0), 2), "pf": round(float(p[p > 0].sum() / gl), 2) if gl else None,
            "net": round(float(p.sum())), "per_month": round(float(p.sum()) / (ns / 21.0)),
            "max_dd": round(float((eq - np.maximum.accumulate(np.r_[0.0, eq])[1:]).min()))}, days


def monthly(BY, S, mf):
    m = collections.defaultdict(float)
    for si, d in enumerate(S):
        for t in BY[si]:
            q0 = RL.qty_for(t["risk"]) if t["strat"] == "LIT" else int(250.0 // ((t["risk"] + R.SLIP) * R.PV + R.COMM))
            if not q0:
                continue
            q = _scale(q0, mf(t) if mf else 1.0)
            m[d[:7]] += t["pts"] * R.PV * q - R.COMM * q
    return m


def walk_forward(mb, mv, last):
    """3-month windows from 2022-05: won = the variant made more than as-is in that window; WF $ = the change when the variant
    is switched on only after a 6-month look-back where it beat as-is."""
    ms = []
    y, mo = 2021, 11
    while f"{y:04d}-{mo:02d}" <= last:
        ms.append(f"{y:04d}-{mo:02d}")
        mo += 1
        if mo > 12:
            y, mo = y + 1, 1
    k = ms.index("2022-05")
    won = n = 0
    wf = 0.0
    while k < len(ms):
        lb, oos = ms[k - 6:k], ms[k:k + 3]
        d_oos = sum(mv.get(m, 0) - mb.get(m, 0) for m in oos)
        d_lb = sum(mv.get(m, 0) - mb.get(m, 0) for m in lb)
        n += 1
        won += d_oos > 0
        if d_lb > 0:
            wf += d_oos
        k += 3
    return {"windows_won": won, "windows": n, "wf_usd": round(wf)}


# --------------------------------------------------------------------------------------------- C: funded ATLAS replay
def part_c(n):
    from tools import atlas_funded as F
    from engine import account_b as EAB
    M = F.M
    M.units()
    units = F.A.account_units(F.A.BASE)
    by = collections.defaultdict(list)
    for t in sorted(units, key=lambda t: t["entry_t"]):
        by[t["day"]].append(t)
    LS = [0]
    cfg15 = {**F.CFG["funded"], "pct": min(0.6, 1.5 * float(F.CFG["funded"]["pct"])),
             "pct_max_usd": 1.5 * float(F.CFG["funded"]["pct_max_usd"])}

    def q_base(t, st):
        return F.q_live(t, {**st, "loss_streak": LS[0]})

    def q_sb(t, st):
        st = {**st, "loss_streak": LS[0]}
        if not sb_hour(t["entry_t"]):
            return F.q_live(t, st)
        r = float(t["risk"])
        q = int(_fq({"risk_pts": r, "tgt_pts": float(t["tgt"]), "size_mult": 1.0}, dict(st), cfg15, acct=F.ACCT))
        rr = {"qty": min(int(F.ACCT["max_micros"]), q), "reasons": []}
        rr = EAB.streak_cap(rr, F.SPEC, st)
        return int(EAB.dll_guard(rr, r, F.SPEC["rules"], st)["qty"])

    _pd, _acct = M.play_day, F.account

    def play_day(*a, **k):
        cum, recs, failed = _pd(*a, **k)
        for r in recs:
            LS[0] = LS[0] + 1 if r["pnl"] < 0 else 0
        return cum, recs, failed

    def account(*a, **k):
        LS[0] = 0
        return _acct(*a, **k)
    M.play_day, F.account = play_day, account
    out = {"rule": {"live": F.CFG["funded"], "sb_x1.5": cfg15, "streak_shrink": F.SPEC.get("streak_shrink")}}
    for nm, qf in (("as_is", q_base), ("sb_x1.5", q_sb)):
        row = {}
        with F.Sizer(qf):
            for s in F.SPANS:
                row[s] = F.mc(by, s, n)
                row[s + "_real"] = F.real(by, s)
                x, y = row[s], row[s + "_real"]
                print(f"C {nm:8s} {s:8s} MC ${x['per_month']}/mo paid6m ${x['paid_6m']} lost {x['lost_6m']}% dead {x['dead_6m']}% "
                      f"payouts {x['payouts_6m']} first {x['first_med']} grad {x['grad_6m']}% | real pays {y['payouts']} ${y['paid']} "
                      f"lost {y['lost']} of {y['accounts']}", flush=True)
        out[nm] = row
    M.play_day, F.account = _pd, _acct
    return out


# --------------------------------------------------------------------------------------------- main
def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--skip_c", action="store_true")
    a = ap.parse_args(argv)
    t0 = time.time()
    S = SOA.data()["S"]
    PE = {s: U.mc_paths(S, s, a.n, length=R.H_EVAL, seed=7) for s in SPANS}
    PF = {s: U.mc_paths(S, s, a.n, length=R.LEN, seed=23) for s in SPANS}
    out = {"n": a.n, "variants": {}}
    for vid, (book, mf, desc) in VARIANTS.items():
        V = {"desc": desc, "book": book, "plans": {}}
        for plan in PLANS:
            P = {}
            for lab, f in (("as_is", None), ("variant", mf)):
                sp = wrap(BK.build(plan, book))
                BK.CFG.clear()
                BK.CFG.update(sp["knobs"])
                MF["f"] = f
                P[lab] = {s: {"eval": R.eval_run(sp, PE[s]), "slot": R.slot_run(sp, PF[s])} for s in SPANS}
                MF["f"] = None
                BK.CFG.clear()
            V["plans"][plan] = P
            print(vid, plan, " | ".join(f"{s} eval {P['as_is'][s]['eval']['pass']}/{P['as_is'][s]['eval']['fail']} -> "
                                        f"{P['variant'][s]['eval']['pass']}/{P['variant'][s]['eval']['fail']} "
                                        f"slot ${P['as_is'][s]['slot']['net_6m']} -> ${P['variant'][s]['slot']['net_6m']}"
                                        for s in SPANS), f"[{time.time() - t0:.0f}s]", flush=True)
        sp = wrap(BK.build("mffu_builder_25k", book))
        V["fixed"] = {lab: {s: fixed(sp["BYx"], S, s, f)[0] for s in SPANS} for lab, f in (("as_is", None), ("variant", mf))}
        mb, mv = monthly(sp["BYx"], S, None), monthly(sp["BYx"], S, mf)
        V["wf"] = walk_forward(mb, mv, S[-1][:7])
        V["share_changed"] = round(100.0 * np.mean([mf(t) != 1.0 for ts in sp["BYx"] for t in ts]), 1)
        print(vid, "fixed", V["fixed"], V["wf"], V["share_changed"], flush=True)
        out["variants"][vid] = V
    if not a.skip_c:
        out["C"] = part_c(a.n)
    json.dump(out, open(os.path.join(HERE, "proof.json"), "w"), indent=1, default=float)
    print("done", time.time() - t0)


if __name__ == "__main__":
    main()
