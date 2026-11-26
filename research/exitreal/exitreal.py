"""Exit + backtest realism (pre-registered: research/exitreal/DESIGN.md). PAPER RESEARCH ONLY.

    python -X utf8 research/exitreal/exitreal.py [--n 1000] [--no-eval]   -> research/exitreal/results.json + tables

results.json was made BEFORE engine/costs.py was adopted (commit 3bdf53d3). Since then tools/account4_sim already carries the
2-tick stop on LIT's trades, so a re-run of the eval part here would count that tick twice (E0 is no longer "as stored").

Per stored trade (LIT: the research ledger tools/account4_sim reads; ATLAS: tools/atlas_fills.units, the units the eval
engines use), on NQ bars (1m for 2026, 5m before), in direction space (higher = better for the trade):
  target:  the exit bar must trade THROUGH the target by thr ticks; a touch-only target is re-walked from the next bar
           (filled on a later trade-through, else the original stop, else the 15:55 ET bar's close)
  stops / market exits: extra ticks of slippage; a bar that OPENS through the stop fills at that open (STOP exits)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
for p in (ROOT, os.path.join(ROOT, "tools"), os.path.join(ROOT, "tools", "money"), os.path.join(ROOT, "research", "plans")):
    sys.path.insert(0, p)
OUT = os.path.join(HERE, "results.json")
ET = ZoneInfo("America/New_York")
TICK, PV, COMM = 0.25, 2.0, 1.90
SPANS = {"2026 H1": ("2026-01-01", "2026-06-30"), "2026 Jul-Oct": ("2026-07-01", "2026-10-16"), "2021-25": ("2021-01-01", "2025-12-31")}
MODELS = {"E0": dict(thr=None, extra=0, gap=False), "Et": dict(thr=1, extra=0, gap=False), "Es": dict(thr=None, extra=1, gap=True),
          "E1": dict(thr=1, extra=1, gap=True), "E1-BE": dict(thr=1, extra=1, gap=True, be=True), "E2": dict(thr=2, extra=3, gap=True)}


class Bars:
    def __init__(self, path):
        b = pd.read_csv(path)
        self.t = b["time"].values.astype(np.int64)
        self.o, self.h, self.l, self.c = (b[k].values.astype(float) for k in ("open", "high", "low", "close"))


_B = {}


def bars():
    if not _B:
        _B["1"] = Bars(os.path.join(ROOT, "data", "NQ_1m.csv"))
        _B["5"] = Bars(os.path.join(ROOT, "data", "NQ_5m.csv"))
    return _B["1"], _B["5"]


def _ix(B, t):
    k = int(np.searchsorted(B.t, t))
    return k if k < len(B.t) and B.t[k] == t else None


def flat_t(t):
    d = dt.datetime.fromtimestamp(int(t), ET)
    return int(d.replace(hour=15, minute=55, second=0, microsecond=0).timestamp())


def frame(t_entry, model_px=None):
    """(bars, offset) for a trade: 1m in 2026 (aligned onto the 5m basis), else 5m."""
    B1, B5 = bars()
    w = t_entry // 300 * 300
    if t_entry >= int(B1.t[0]) + 86400:
        k1, k5 = _ix(B1, w), _ix(B5, w)
        if k1 is not None and k5 is not None:
            off = B1.o[k1] - B5.o[k5]
            return B1, (off if abs(off) > 1.0 else 0.0)
    return B5, 0.0


def correct(tr, m, slip_stop=1):
    """tr: {dir, entry_t, exit_t, entry_d, stop_d, target_d (or None), pts, exit}. -> (pts per micro, note)."""
    d, pts, kind = tr["dir"], float(tr["pts"]), str(tr["exit"]).upper()
    B, off = frame(tr["entry_t"])
    hi_d = (B.h - off) * d if d > 0 else -(B.l - off)
    lo_d = (B.l - off) * d if d > 0 else -(B.h - off)
    op_d, cl_d = (B.o - off) * d, (B.c - off) * d
    # exit_t = the CLOSE of the strategy's exit bar (LIT 2026: 1m; ATLAS and 2021-25: 5m): the exit happened in the bars
    # [exit_t - S, exit_t) of B
    S = int(tr.get("secs") or 300)
    ka = int(np.searchsorted(B.t, int(tr["exit_t"]) - S))
    kz = int(np.searchsorted(B.t, int(tr["exit_t"]))) - 1      # the last bar of the exit window
    if kz < ka:
        kz = ka
    note = None
    extra = m["extra"] * TICK
    if kind.startswith("TARGET") and m["thr"] is not None and tr.get("target_d") is not None and 0 <= ka < len(B.t):
        T = tr["target_d"]
        kx = kz
        if hi_d[ka:kz + 1].max() < T + m["thr"] * TICK - 1e-9:     # touch only: the limit may sit unfilled
            stop = tr["entry_d"] if m.get("be") else tr["stop_d"]
            fl = flat_t(tr["exit_t"])
            j, new = kx + 1, None
            while j < len(B.t) and B.t[j] < fl + (300 if B is bars()[1] else 60):
                if lo_d[j] <= stop + 1e-9:
                    px = min(stop, op_d[j]) - (slip_stop + m["extra"]) * TICK
                    new, note = px - tr["entry_d"], "touch->stop"
                    break
                if hi_d[j] >= T + m["thr"] * TICK - 1e-9:
                    new, note = pts, "touch->later fill"
                    break
                if B.t[j] >= fl:
                    new, note = cl_d[j] - (slip_stop + m["extra"]) * TICK - tr["entry_d"], "touch->flat"
                    break
                j += 1
            if new is None:
                new, note = cl_d[min(j, len(B.t)) - 1] - (slip_stop + m["extra"]) * TICK - tr["entry_d"], "touch->flat"
            return new, note
        return pts, None
    if kind.startswith("TARGET"):
        return pts, None
    new = pts - extra
    if m["gap"] and kind.startswith("STOP") and 0 <= ka < len(B.t):
        hit = [j for j in range(ka, kz + 1) if lo_d[j] <= tr["stop_d"] + 1e-9]   # the first bar of the window at the stop
        if hit and op_d[hit[0]] < tr["stop_d"] - TICK:                            # ... opened through it: fills near that open
            gap_px = op_d[hit[0]] - (slip_stop + m["extra"]) * TICK
            if gap_px - tr["entry_d"] < new:
                new, note = gap_px - tr["entry_d"], "gap through the stop"
    return new, note


# ---------------------------------------------------------------------- the two bots' stored trades
def lit_rows():
    """account4_sim's own rows + their prices (re-read from the ledger, same file)."""
    import csv
    import uprisk as U
    rows = {}
    with open(os.path.join(U.HO, "COMPLETE_TRADE_LEDGER.csv"), encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["trade_id"].startswith(("T-2026", "REF-")):
                rows[r["trade_id"]] = r
    return rows


def lit_spec(t, rows):
    r = rows[t["id"]]
    d = t["dir"]
    return {"dir": d, "entry_t": t["entry_t"], "exit_t": t["exit_t"], "entry_d": float(r["entry_price"]) * d,
            "stop_d": float(r["initial_stop"]) * d, "target_d": float(r["target_price"]) * d if r["target_price"] else None,
            "pts": t["pts"], "exit": t["exit"], "secs": 300 if t.get("ref") else 60}


def atlas_spec(u):
    _, B5 = bars()
    k = _ix(B5, int(u["entry_t"]))
    e = float(B5.o[k]) * int(u["dir"]) if k is not None else None
    return {"dir": int(u["dir"]), "entry_t": int(u["entry_t"]), "exit_t": int(u["exit_t"]), "entry_d": e,
            "stop_d": None if e is None else e - float(u["risk"]), "target_d": None if e is None or not u.get("tgt") else e + float(u["tgt"]),
            "pts": float(u["pts"]), "exit": u["exit"], "secs": 300}


# ---------------------------------------------------------------------- plain stats
def plain(rows):
    """rows: (day, risk, pts). $250 risk a trade, $1.90 a micro."""
    if not rows:
        return None
    rows = sorted(rows)
    usd = np.array([250.0 / (r * PV) * (p * PV - COMM) for _, r, p in rows])
    g, l = usd[usd > 0].sum(), -usd[usd < 0].sum()
    eq = np.cumsum(usd)
    dd = float((np.maximum.accumulate(np.r_[0.0, eq]) - np.r_[0.0, eq]).max())
    d0, d1 = dt.date.fromisoformat(rows[0][0]), dt.date.fromisoformat(rows[-1][0])
    weeks = max(1.0, ((d1 - d0).days + 1) / 7.0)
    return {"n": len(rows), "per_week": round(len(rows) / weeks, 2), "pf": round(g / l, 3) if l else None, "net_usd": round(float(usd.sum())),
            "usd_month": round(float(usd.sum()) / (weeks / 4.345)), "max_dd": round(dd)}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=1000)
    ap.add_argument("--no-eval", action="store_true")
    a = ap.parse_args(argv)
    import account4_sim as A4
    import atlas_fills as AF
    LT = [t for ts in A4.trades().values() for t in ts]
    rows = lit_rows()
    AU = AF.units()
    spec = {"LIT": [(t, lit_spec(t, rows)) for t in LT], "ATLAS": [(u, atlas_spec(u)) for u in AU if atlas_spec(u)["entry_d"] is not None]}
    res = {"made": "2026-11-26", "design": "research/exitreal/DESIGN.md", "plain": {}, "touch": {}, "corrected": {}}
    corr = {}
    for bot, S in spec.items():
        for mk, m in MODELS.items():
            out = []
            notes = {}
            for t, s in S:
                p, note = correct(s, m)
                out.append(p)
                if note:
                    notes[note] = notes.get(note, 0) + 1
            corr[(bot, mk)] = out
            res["touch"].setdefault(bot, {})[mk] = notes
            for sp, (lo, hi) in SPANS.items():
                rr = [(t["day"], float(t["risk"]), p) for (t, s), p in zip(S, out) if lo <= t["day"] <= hi]
                res["plain"].setdefault(bot, {}).setdefault(sp, {})[mk] = plain(rr)
        tg = [(t, s) for t, s in S if str(s["exit"]).upper().startswith("TARGET") and s.get("target_d") is not None]
        thr_hist = {}
        for t, s in tg:
            B, off = frame(s["entry_t"])
            ka = int(np.searchsorted(B.t, int(s["exit_t"]) - int(s["secs"])))
            kz = max(ka, int(np.searchsorted(B.t, int(s["exit_t"]))) - 1)
            hi = ((B.h[ka:kz + 1].max() - off) * s["dir"]) if s["dir"] > 0 else -(B.l[ka:kz + 1].min() - off)
            through = round((hi - s["target_d"]) / TICK)
            key = "0 (touch only)" if through <= 0 else "1" if through == 1 else "2" if through == 2 else "3+"
            sp = "2026" if t["day"] >= "2026" else "2021-25"
            thr_hist.setdefault(sp, {}).setdefault(key, 0)
            thr_hist[sp][key] += 1
        res["touch"][bot]["targets_through_ticks"] = thr_hist
    if not a.no_eval:
        res["eval"] = evals(LT, AU, corr, spec, a.n)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1, default=float)
    show(res)


def evals(LT, AU, corr, spec, n):
    """research/plans/rank.py's eval_run + slot_run for three MFFU plans, with the LIT trades and the ATLAS units corrected."""
    import account4_sim as A4
    import atlas_fills as AF
    import atlas_risk as AR
    import rank as RK
    import stack_one_account as SOA
    import uprisk as U
    out = {}
    for mk in ("E0", "E1", "E2"):
        lit_new = {}
        for (t, s), p in zip(spec["LIT"], corr[("LIT", mk)]):
            lit_new.setdefault(t["day"], []).append({**t, "pts": round(p, 4)})
        A4.trades = (lambda d=lit_new: d)
        A4._D.clear()
        # ATLAS: rank.py's own pricing (10 ticks entry, 10 on non-target exits) + this model's TARGET rule only
        m = MODELS[mk]
        mt = {"thr": m["thr"], "extra": 0, "gap": False}
        AT = []
        for u, s in spec["ATLAS"]:
            p, _ = correct(s, mt, slip_stop=10)
            AT.append({**u, "pts": round(p, 4) if str(u.get("exit", "")).upper() == "TARGET" else u["pts"]})
        T = AF.to_T([AF.priced(u, 10, 10) for u in AT])      # a touch-only target re-walked to a stop already carries its 10 ticks
        AR.rapid_patch(T)
        S = SOA.data()["S"]
        PE = {sp: U.mc_paths(S, sp, n, length=RK.H_EVAL, seed=7) for sp in RK.SPANS}
        PF = {sp: U.mc_paths(S, sp, n, length=RK.LEN, seed=23) for sp in RK.SPANS}
        for plan in ("mffu_builder_50k", "mffu_builder_25k", "mffu_rapid_eod_25k"):
            sp = RK.spec(plan)
            for s in RK.SPANS:
                ev, sl = RK.eval_run(sp, PE[s]), RK.slot_run(sp, PF[s])
                out.setdefault(plan, {}).setdefault(s, {})[mk] = {"pass": ev["pass"], "fail": ev["fail"], "med_days": ev["med_days"],
                                                                 "net_6m": sl.get("net_6m"), "owner_6m": sl.get("owner_6m")}
            print(f"  eval {mk} {plan}: " + " | ".join(f"{s} pass {out[plan][s][mk]['pass']}% net6m ${out[plan][s][mk]['net_6m']}"
                                                         for s in RK.SPANS), flush=True)
    return out


def show(res):
    for bot, P in res["plain"].items():
        print(f"\n{bot}: per span, model -> trades/wk  PF  net $  $/mo  maxDD   (touch notes {res['touch'][bot].get('E1')})")
        print(f"   targets by ticks traded through on the exit bar: {res['touch'][bot]['targets_through_ticks']}")
        for sp, M in P.items():
            base = M["E0"]["net_usd"] if M["E0"] else None
            print("  " + sp + ": " + " | ".join(f"{mk} {v['per_week']}/wk PF {v['pf']} ${v['net_usd']:,} (${v['usd_month']:,}/mo, "
                                               f"{(100 * (v['net_usd'] - base) / abs(base)) if base else 0:+.1f}%) DD ${v['max_dd']:,}"
                                               for mk, v in M.items() if v))


if __name__ == "__main__":
    main()
