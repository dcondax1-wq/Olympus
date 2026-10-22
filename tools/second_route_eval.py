"""LIT + the ROUTED EMA (ema_lon_vix) on one MFFU Builder 50K eval, under the live account rules of engine/live.py
(LiveBot._second_route_tick), against the research eval path of research/writeups/second-ema.md.

    python -X utf8 tools/second_route_eval.py            # -> research/second/route_eval.json + a table on stdout (~3 min)

The research eval path (tools/second_ema.eval_mix, run lit_adopt_t15_be_off_eval for LIT): every EMA trade of 2026 that is
not inside a LIT trade (combine max 2) is added at eval-safe size; a LIT trade that starts while an EMA trade is open runs
NEXT to it (two positions at once). The live route allows one position: steps, each on top of the previous one:
  1. research            tools/second_ema.eval_mix as published (H1 61.3/5.0, H2 69.6/2.9, H2 path +$23,040)
  2. LIT-armed block     no EMA entry while LIT has a limit armed / waits for its 1m CISD / is entering (the live loop's
                         own state at the EMA bar's open: engine/lit_live.run on the bars closed by then, as the PC bot)
  3. LIT priority close  an EMA trade still open when LIT enters is closed at market at LIT's entry minute (its 1m open
                         - 1 tick, costs in), then LIT enters (one position at a time)
  4. pass lock           no EMA entry once the eval is passed (profit + today >= $3,000; engine/sizing.eval_lock)
Step 4 = what the PC bot does (engine/sizing.second_qty = the research eval-safe size, tests/test_second_route.py).
The EMA trades themselves are the live loop's (engine/second.run == research/second/ema_best.json on every 2026 session,
tests/test_second.py), LIT's are run lit_live (engine/lit_live.py == the backtest, tests/test_lit_live.py).
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import os
import sys
import time
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))

from engine import lit_live  # noqa: E402
from engine.data import load, load_ltf  # noqa: E402
from tools import second_ema as SE  # noqa: E402

ET = ZoneInfo("America/New_York")
OUT = os.path.join(ROOT, "research", "second", "route_eval.json")
TICK, PV, COMM = SE.TICK, SE.PV, SE.COMM


def hm(t):
    return dt.datetime.fromtimestamp(int(t), ET).strftime("%H:%M")


def run_eval_mix(seq, byL, byE, horizon=20, keep=None, base="usd500", pass_lock=False):
    """tools/second_ema.run_eval_mix + the optional pass lock (no EMA entry once profit + today >= the target)."""
    from engine import lit
    from engine import sizing as SZ
    from tools import lit_adv_manage as A
    tgt, mll, dll, lockv = SE.A50["target"], SE.A50["mll"], SE.A50["dll"], SE.A50["lock"]
    bal = peak = 0.0
    floor = -mll
    for kk, si in enumerate(seq[:horizon]):
        cum = 0.0
        ev = sorted([(t["entry_t"], 0, t) for t in byL[si]] + [(u["entry_t"], 1, u) for u in byE[si]], key=lambda x: (x[0], x[1]))
        for _, kind, t in ev:
            if cum <= -dll:
                break
            st = {"profit": bal, "cum": cum, "room": bal + cum - floor, "session": kk + 1, "n_today": 0}
            if kind == 0:
                m0 = lit.qty_for(t["risk"])
                q = SZ.lit_qty(m0, {"risk_pts": t["risk"], "tgt_pts": t["tgt"], "size_mult": 1.0}, A.CFG, room=st["room"], state=st,
                               learning=None)["qty"] if m0 else 0
                if q <= 0:
                    continue
                pnl = A.leg_pnl(t, q)
                low = min(0.0, t["w1"] * PV * q - A.ECOMM * q, pnl)
            else:
                if pass_lock and bal + cum >= tgt:
                    continue
                q = SE.ema_eval_qty(t, st, base)
                if q <= 0:
                    continue
                pnl = q * PV * t["r"] * t["risk_pts"]
                low = min(0.0, q * (PV * t["worst_pts"] - COMM), pnl)
            if cum + low <= -dll:
                pnl = -dll - cum - TICK * PV * q
                low = pnl
            if keep is not None:
                keep.append({"day": t["day"], "entry_t": t["entry_t"], "src": "LIT" if kind == 0 else "EMA", "qty": q,
                             "pnl": round(pnl, 2), "low": round(low, 2)})
            if bal + cum + low <= floor:
                return "FAIL", kk + 1
            cum += pnl
        bal += cum
        if bal <= floor:
            return "FAIL", kk + 1
        peak = max(peak, bal)
        floor = min(max(floor, peak - mll), lockv)
        if bal >= tgt:
            return "PASS", kk + 1
    return "OPEN", min(len(seq), horizon)


def eval_res(EU, span, pass_lock=False, base="usd500"):
    """tools/second_ema.eval_mix / _eval_res with this module's run_eval_mix."""
    from tools import lit_adv_manage as A
    S26 = A.S26
    a, z = SE.SPAN[span]
    ix = [i for i, x in enumerate(S26) if a <= x <= z]
    pos = {x: i for i, x in enumerate(S26)}
    byL = collections.defaultdict(list); byE = collections.defaultdict(list)
    for t in SE.lit_units():
        if t["day"] in pos:
            byL[pos[t["day"]]].append(t)
    for u in EU:
        if u["day"] in pos:
            byE[pos[u["day"]]].append(u)
    a_, z_ = ix[0], ix[-1] + 1
    res = [(run_eval_mix(list(range(i, min(z_, i + 20))), byL, byE, base=base, pass_lock=pass_lock), z_ - i) for i in range(a_, z_)]
    o = {}
    for lab, h in (("10", 10), ("20", 20)):
        R = [r for r, av in res if av >= h]
        N = len(R) or 1
        o["p" + lab] = round(100.0 * sum(1 for r in R if r[0] == "PASS" and r[1] <= h) / N, 1)
        o["f" + lab] = round(100.0 * sum(1 for r in R if r[0] == "FAIL" and r[1] <= h) / N, 1)
    k, T, n = a_, [], collections.Counter()
    while k < z_:
        r, used = run_eval_mix(list(range(k, z_)), byL, byE, z_ - k, keep=T, base=base, pass_lock=pass_lock)
        n[r] += 1
        if r == "OPEN":
            break
        k += used
    p = np.array([t["pnl"] for t in T]) if T else np.zeros(1)
    eq = np.cumsum(p)
    gl = -p[p < 0].sum()
    o.update(b2b=f"{n['PASS']}/{n['FAIL']}/{n['OPEN']}", net=round(float(p.sum())), pf=round(float(p[p > 0].sum() / gl), 2) if gl else None,
             dd=round(float((eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min())), n=len(T),
             n_ema=sum(1 for t in T if t["src"] == "EMA"), net_ema=round(sum(t["pnl"] for t in T if t["src"] == "EMA")))
    return o


_LB = {}


def lit_busy_at(now):
    """Why the live loop's LIT is busy at `now` (in a trade / entering / limit armed / waiting for its 1m CISD) or None:
    engine/lit_live.run on the bars closed by then (research-clean 1m, early mode, the forming 1m open), as the PC bot."""
    if not _LB:
        P = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))["lit"]
        df5 = pd.read_csv(os.path.join(ROOT, "data", "NQ_5m.csv"))
        df5 = df5[df5["time"] >= int(dt.datetime(2025, 9, 1, tzinfo=ET).timestamp())].reset_index(drop=True)
        b1, _ = load_ltf("NQ", load("NQ", "5m"))
        b1 = b1.slice(int(np.searchsorted(b1.t, int(df5["time"].min()))), len(b1))
        _LB.update(P=P, df5=df5, b1=b1, T5=df5["time"].values, o1=dict(zip(b1.t.astype("int64"), b1.o.astype(float))))
    df5, b1, T5, o1 = _LB["df5"], _LB["b1"], _LB["T5"], _LB["o1"]
    cut5 = df5.iloc[:int(np.searchsorted(T5 + 300, now, side="right"))]
    cut1 = b1.slice(0, int(np.searchsorted(b1.t + 60, now, side="right")))
    t = now - now % 60
    st = lit_live.run(cut5, _LB["P"], one_min=cut1, now=now, forming=(t, o1[t]) if t in o1 else None, early=True)["state"]
    su = st.get("setups") or {}
    return ("LIT is entering" if st.get("enter_now") else "LIT is in a trade" if st.get("position") else
            ("LIT is waiting for its 1m CISD" if next(iter(su.values())).get("tapped_t") else "LIT has a limit armed") if su else None)


def main():
    t0 = time.time()
    title, E, X = SE.VERSIONS["ema2_lon_vix"]
    U = SE.trades_of(E, X)
    T = SE.sized(U, SE.SIZE)
    C2, _ = SE.combine(T, 2)
    keep = {(t["day"], t["entry_t"]) for t in C2 if t["src"] == "EMA"}
    UK = [u for u in U if (u["day"], u["entry_t"]) in keep]
    U26 = [u for u in UK if "2026-01-01" <= u["day"] <= "2026-10-16"]
    print(f"EMA research trades 2026: {sum(1 for u in U if '2026-01-01' <= u['day'] <= '2026-10-16')}, kept next to LIT (max 2): {len(U26)}",
          flush=True)
    # LIT's live loop at each EMA trade's entry bar (engine/lit_live.run on the bars closed by then, early mode + forming open)
    P = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))["lit"]
    df5 = pd.read_csv(os.path.join(ROOT, "data", "NQ_5m.csv"))
    df5 = df5[df5["time"] >= int(dt.datetime(2025, 9, 1, tzinfo=ET).timestamp())].reset_index(drop=True)
    b1, _ = load_ltf("NQ", load("NQ", "5m"))
    b1 = b1.slice(int(np.searchsorted(b1.t, int(df5["time"].min()))), len(b1))
    T5 = df5["time"].values
    o1 = dict(zip(b1.t.astype("int64"), b1.o.astype(float)))

    def poll(now):
        cut5 = df5.iloc[:int(np.searchsorted(T5 + 300, now, side="right"))]
        cut1 = b1.slice(0, int(np.searchsorted(b1.t + 60, now, side="right")))
        t = now - now % 60
        return lit_live.run(cut5, P, one_min=cut1, now=now, forming=(t, o1[t]) if t in o1 else None, early=True)
    runs = json.load(open(os.path.join(ROOT, "research", "runs", "lit_live.json"), encoding="utf-8"))
    LT = collections.defaultdict(list)
    for a in runs["trades"]:
        t = dict(zip(runs["trade_cols"], a))
        LT[t["day"]].append(t)
    armed, pre, rows = set(), {}, []
    for u in U26:
        et_ = int(u["entry_t"])
        st = poll(et_ + 2)["state"]
        su = st.get("setups") or {}
        why = ("LIT entering" if st.get("enter_now") else "LIT in a trade" if st.get("position") else
               ("LIT waiting for its 1m CISD" if next(iter(su.values())).get("tapped_t") else "LIT limit armed") if su else None)
        if why:
            armed.add(et_)
        L = next((t for t in LT.get(u["day"], []) if et_ < int(t["entry_t"]) < int(u["exit_t"])), None)
        if L is not None:
            lt = int(L["entry_t"])
            d = int(u["dir"])
            px = o1.get(lt)
            if px is None:                          # no 1m bar: the 5m open of LIT's bar
                j = int(np.searchsorted(T5, lt - lt % 300)); px = float(df5["open"].iloc[j])
            e = float(u["entry"])
            pts = d * (float(px) - d * TICK - e)
            r = (pts - SE.CPTS) / float(u["risk_pts"])
            pre[et_] = {"lit_t": lt, "px": round(float(px), 2), "r": round(r, 4), "r_research": u["r"], "worst": min(float(u["worst_pts"]), pts)}
        rows.append({"day": u["day"], "entry": hm(et_), "exit_kind": u["exit_kind"], "r": u["r"], "blocked": why,
                     "lit_priority": pre.get(et_)})
    print(f"LIT busy at the EMA entry (armed / 1m-CISD wait / entering): {len(armed)}; LIT enters during the EMA trade: {len(pre)}",
          flush=True)

    def step(block, close):
        out = []
        for u in UK:
            et_ = int(u["entry_t"])
            if block and et_ in armed:
                continue
            if close and et_ in pre:
                u = {**u, "r": pre[et_]["r"], "worst_pts": pre[et_]["worst"], "exit_kind": "LIT PRIORITY"}
            out.append(u)
        return out
    steps = [("1. research (second-ema.md)", step(False, False), False),
             ("2. + no EMA entry while LIT is armed / entering", step(True, False), False),
             ("3. + EMA closed at market when LIT enters", step(True, True), False),
             ("4. + pass lock = the live route", step(True, True), True),
             ("alt: live route without the LIT-armed block", step(False, True), True)]
    res = {"steps": [], "rows": rows, "lit_alone": {sp: eval_res([], sp) for sp in ("H1", "H2")}}
    for nm, EU, pl in steps:
        o = {sp: eval_res(EU, sp, pass_lock=pl) for sp in ("H1", "H2")}
        n26 = sum(1 for u in EU if "2026-01-01" <= u["day"] <= "2026-10-16")
        res["steps"].append({"step": nm, "ema_trades_2026": n26, **o})
        print(f"{nm:50s} EMA {n26:3d} | H1 2-wk {o['H1']['p10']}/{o['H1']['f10']} 1-mo {o['H1']['p20']}/{o['H1']['f20']} path "
              f"{o['H1']['net']:+,} PF {o['H1']['pf']} b2b {o['H1']['b2b']} | H2 2-wk {o['H2']['p10']}/{o['H2']['f10']} 1-mo "
              f"{o['H2']['p20']}/{o['H2']['f20']} path {o['H2']['net']:+,} PF {o['H2']['pf']} b2b {o['H2']['b2b']}", flush=True)
    la = res["lit_alone"]
    print(f"{'LIT alone':50s}         | H1 2-wk {la['H1']['p10']}/{la['H1']['f10']} path {la['H1']['net']:+,} | H2 2-wk "
          f"{la['H2']['p10']}/{la['H2']['f10']} path {la['H2']['net']:+,}")
    res["seconds"] = round(time.time() - t0)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1, default=str)
    print(f"-> {os.path.relpath(OUT, ROOT)} ({res['seconds']} s)")


if __name__ == "__main__":
    main()
