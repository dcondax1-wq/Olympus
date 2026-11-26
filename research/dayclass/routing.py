"""Playbook routing by the walk-forward day-type call (15 pre-registered versions + oracle info rows; DESIGN.md).
PAPER RESEARCH ONLY: reads stored trades / bars, writes research/dayclass/routing.json.

    python -X utf8 research/dayclass/routing.py [--n 600]
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import logging
import os
import random
import sys
import time

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
for p in (ROOT, os.path.join(ROOT, "tools"), os.path.join(ROOT, "tools", "money"), os.path.join(ROOT, "research", "structure"), HERE):
    sys.path.insert(0, p)
logging.disable(logging.WARNING)
import bars as BR  # noqa: E402
import features as F  # noqa: E402

CL = F.CLASSES
OUT = os.path.join(HERE, "routing.json")
SP3 = ("H1", "H2", "2021-25")
ET = dt.timezone(dt.timedelta(hours=-5))
N_TESTS = 15
B25 = {"target": 1500.0, "mll": 1000.0, "lock": 100.0, "dll": 600.0}


# ------------------------------------------------------------------------------------------------ day calls
def calls():
    P = pd.read_csv(os.path.join(HERE, "preds.csv"))
    out = collections.defaultdict(dict)
    for r in P.itertuples(index=False):
        out[r.ck][r.day] = (np.array([getattr(r, "p_" + c) for c in CL]), r.y)
    return out


def ck_of(entry_t):
    import zoneinfo
    e = dt.datetime.fromtimestamp(entry_t, zoneinfo.ZoneInfo("America/New_York"))
    m = e.hour * 60 + e.minute
    if m >= 1080 or m < 120:
        return "C0"
    if m < 570:
        return "C1"
    if m < 630:
        return "C2"
    return "C3"


def view(C, t, oracle=False):
    """-> (top class with direction, p_with, p_against) for trade t, or None (no call that day)."""
    ck = ck_of(t["entry_t"])
    x = C[ck].get(t["day"])
    if x is None:
        return None
    p, y = x
    if oracle:
        p = np.eye(len(CL))[CL.index(y)]
    d = t["dir"]
    pw, pa = (p[1], p[2]) if d > 0 else (p[2], p[1])
    top = CL[int(np.argmax(p))]
    if top in ("trend_up", "trend_down"):
        top = "trend_with" if (top == "trend_up") == (d > 0) else "trend_against"
    return top, float(pw), float(pa), ck


RULES = {
    "lit": [("L1 skip: top = trend against", lambda v: 0.0 if v[0] == "trend_against" else 1.0),
            ("L2 x0.5: top = trend against", lambda v: 0.5 if v[0] == "trend_against" else 1.0),
            ("L3 x1.5: top = range / reversal", lambda v: 1.5 if v[0] in ("range", "reversal") else 1.0),
            ("L4 skip: P(trend against) >= 0.40", lambda v: 0.0 if v[2] >= 0.40 else 1.0),
            ("L5 data router (skip)", "router")],
    "atlas": [("A1 skip: top = range", lambda v: 0.0 if v[0] == "range" else 1.0),
              ("A2 x0.5: top = range", lambda v: 0.5 if v[0] == "range" else 1.0),
              ("A3 x1.5: top = trend with", lambda v: 1.5 if v[0] == "trend_with" else 1.0),
              ("A4 skip: top = trend against", lambda v: 0.0 if v[0] == "trend_against" else 1.0),
              ("A5 data router (skip)", "router")],
    "blitz": [("B1 skip: top = range", lambda v: 0.0 if v[0] == "range" else 1.0),
              ("B2 x0.5: top = range", lambda v: 0.5 if v[0] == "range" else 1.0),
              ("B3 x1.5: top = trend with", lambda v: 1.5 if v[0] == "trend_with" else 1.0),
              ("B4 skip: top = trend against", lambda v: 0.0 if v[0] == "trend_against" else 1.0),
              ("B5 data router (skip)", "router")],
}


def mults(T, C, rule, rkey, oracle=False):
    """{entry_t: m}. T rows need day, entry_t, dir and rkey (the trade's R)."""
    V = {t["entry_t"]: view(C, t, oracle) for t in T}
    if rule != "router":
        return {k: (rule(v) if v else 1.0) for k, v in V.items()}
    out = {}
    TT = sorted(T, key=lambda t: t["entry_t"])
    for t in TT:
        v = V[t["entry_t"]]
        if not v:
            out[t["entry_t"]] = 1.0
            continue
        mo = t["day"][:7]
        past = [u[rkey] for u in TT if u["day"][:7] < mo and V[u["entry_t"]] and V[u["entry_t"]][0] == v[0]]
        out[t["entry_t"]] = 0.0 if (len(past) >= 20 and float(np.mean(past)) < 0) else 1.0
    return out


# ------------------------------------------------------------------------------------------------ money views
def fixed_stats(T, M, usd_key, days_by_span):
    o = {}
    for sp in SP3:
        TT = [(t, t[usd_key] * M.get(t["entry_t"], 1.0)) for t in T if BR.span_of(t["day"]) == sp]
        p = np.array([x for t, x in TT if M.get(t["entry_t"], 1.0) > 0])
        nd = days_by_span[sp]
        by = collections.defaultdict(float)
        for t, x in TT:
            by[t["day"]] += x
        eq = np.cumsum([by[d] for d in sorted(by)]) if by else np.zeros(1)
        gl = -p[p < 0].sum() if len(p) else 0
        o[sp] = {"n": int(len(p)), "tpw": round(len(p) / (nd / 5), 2), "pf": round(float(p[p > 0].sum() / gl), 2) if gl else None,
                 "net": round(float(p.sum())) if len(p) else 0, "per_month": round(float(p.sum()) / (nd / 21)) if len(p) else 0,
                 "dd": round(float((eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min())) if len(p) else 0}
    return o


def eval25(T, M, usd_key, days, horizon=40):
    """Rolling-start Builder 25K (structure-study engine, 25K rules) per 2026 half: 2-week pass / fail %, 40-day pass %."""
    out = {}
    for sp in ("H1", "H2"):
        dd = [d for d in days if BR.span_of(d) == sp]
        by = collections.defaultdict(list)
        for t in T:
            m = M.get(t["entry_t"], 1.0)
            if m > 0 and BR.span_of(t["day"]) == sp:
                by[t["day"]].append(t[usd_key] * m)
        res = []
        for i in range(len(dd)):
            bal = peak = 0.0
            floor = -B25["mll"]
            r = ("OPEN", None)
            for k, d in enumerate(dd[i:i + horizon]):
                cum = 0.0
                for x in by.get(d, []):
                    if cum <= -B25["dll"]:
                        break
                    cum += x
                bal += cum
                if bal <= floor:
                    r = ("FAIL", k + 1); break
                peak = max(peak, bal)
                floor = min(max(floor, peak - B25["mll"]), B25["lock"])
                if bal >= B25["target"]:
                    r = ("PASS", k + 1); break
            res.append(r + (len(dd) - i,))
        f10 = [r for r in res if r[2] >= 10] or res
        out[sp] = {"p10": round(100 * sum(r[0] == "PASS" and r[1] <= 10 for r in f10) / len(f10), 1),
                   "f10": round(100 * sum(r[0] == "FAIL" and r[1] <= 10 for r in f10) / len(f10), 1)}
    return out


def placebo(T, M, usd_key, draws=2000, seed=11):
    """Same count of trades hit per 2026 half, same multipliers, at random -> share of draws with a 2026 gain >= the real one."""
    rnd = random.Random(seed)
    T26 = {sp: [t for t in T if BR.span_of(t["day"]) == sp] for sp in ("H1", "H2")}
    hit = {sp: [M.get(t["entry_t"], 1.0) for t in T26[sp] if M.get(t["entry_t"], 1.0) != 1.0] for sp in T26}
    if not any(hit.values()):
        return None
    real = sum((M.get(t["entry_t"], 1.0) - 1.0) * t[usd_key] for sp in T26 for t in T26[sp])
    beat = 0
    for _ in range(draws):
        g = 0.0
        for sp in T26:
            if hit[sp]:
                for t, m in zip(rnd.sample(T26[sp], len(hit[sp])), hit[sp]):
                    g += (m - 1.0) * t[usd_key]
        beat += g >= real
    return round(beat / draws, 4)


# ------------------------------------------------------------------------------------------------ bots
def lit_bundle():
    from tools import stops_targets_time as STT
    from tools import lit_edge as E
    U = STT.units()
    L = STT.size_matched(U)
    return U, L, STT, E


def lit_money(U, L, M, STT, E):
    L2 = []
    for l_ in L:
        m = M.get(l_["entry_t"], 1.0)
        if m == 0:
            continue
        if m != 1.0:
            q = max(1, min(40, int(l_["qty"] * m)))
            l_ = {**l_, "qty": q, "pnl": round(l_["pts"] * 2.0 * q - 1.40 * q, 2)}
        L2.append(l_)
    U2 = [{**u, "m": float(u.get("m", 1.0)) * M.get(u["entry_t"], 1.0)} for u in U if M.get(u["entry_t"], 1.0) > 0]
    Ev = E.eval_path(U2)
    st = {sp: STT.stats(L2, sp) for sp in STT.SPANS}
    return st, {sp: {k: Ev[sp].get(k) for k in ("n", "net", "p10", "f10", "pass_med")} for sp in ("H1", "H2")}


def lit_mc(M, A4S, PE):
    import account4_sim as A4
    S, BY = A4S
    E_, _ = A4.rules("mffu_builder_50k")
    cfg = A4.ecfg(E_)
    BY2 = []
    for ts in BY:
        row = []
        for t in ts:
            m = M.get(t["entry_t"], 1.0)
            if m == 0:
                continue
            row.append(t if m == 1.0 else {**t, "risk": t["risk"] / m})
        BY2.append(row)
    return {sp: A4.eval_stats(BY2, PE[sp], E_, cfg, 91.80) for sp in ("H1", "H2", "REF")}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=600)
    a = ap.parse_args(argv)
    t0 = time.time()
    import account4_sim as A4
    import atlas_health as AH
    import uprisk as UP
    import builder_levers as BL
    C = calls()
    days = sorted(BR.daily(BR.load("NQ", "5m")).index)
    dbs = {sp: sum(1 for d in days if BR.span_of(d) == sp) for sp in SP3}
    S, BY = A4.load()
    PE = {sp: UP.mc_paths(S, sp, a.n, length=60, seed=7) for sp in ("H1", "H2", "REF")}
    PF = {sp: UP.mc_paths(S, sp, a.n, length=BL.LEN, seed=BL.A4.SEED_LIFE) for sp in BL.SPANS}
    RS = AH.real_starts(S)
    U, L, STT, E = lit_bundle()
    lit_T = [{"day": l_["day"], "entry_t": l_["entry_t"], "dir": l_["dir"], "usd": l_["pnl"], "r": l_["r"]} for l_ in L]
    atl = AH.stream()
    atl_T = [{"day": t["day"], "entry_t": t["entry_t"], "dir": t["dir"], "usd": (lambda q: q * (t["pts"] * 2.0 - 1.90) if q > 0 else 0.0)(
        int(250.0 // ((t["risk"] + 0.25) * 2.0 + 1.90))), "r": t["R"]} for t in atl]
    import study as ST
    bz_T = [{"day": r["day"], "entry_t": r["entry_t"], "dir": r["dir"], "usd": float(r["usd"] or 0), "r": float(r["r"] or 0)}
            for r in ST.pillar_rows() if r["pillar"] == "blitz" and r.get("span") in SP3]
    BOT = {"lit": lit_T, "atlas": atl_T, "blitz": bz_T}
    acc = json.load(open(os.path.join(HERE, "accuracy.json")))
    gate_ck = {ck: acc[ck]["kill_gate_pass"] for ck in ("C0", "C1", "C2", "C3")}

    def evaluate(bot, M):
        T = BOT[bot]
        o = {"fixed": fixed_stats(T, M, "usd", dbs),
             "hit": {sp: sum(1 for t in T if M.get(t["entry_t"], 1.0) != 1.0 and BR.span_of(t["day"]) == sp) for sp in SP3}}
        if bot == "lit":
            o["lit_stats"], o["eval50_2wk"] = lit_money(U, L, M, STT, E)
            o["eval50_mc"] = lit_mc(M, (S, BY), PE)
        elif bot == "atlas":
            r = AH.score({"fam": "base"}, atl, S, PF, RS, w={t["entry_t"]: M.get(t["entry_t"], 1.0) for t in atl})
            o["funded"] = {sp: r["funded"][sp] for sp in ("H1", "H2", "REF")}
            o["eval25"] = eval25(T, M, "usd", days)
        else:
            o["eval25"] = eval25(T, M, "usd", days)
        return o

    res = {"built": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "kill_gate": gate_ck, "bots": {}}
    for bot, rules in RULES.items():
        T = BOT[bot]
        base = evaluate(bot, {})
        # what each predicted / true type pays (info): mean R by class-with-direction
        info = {}
        for orc in (False, True):
            g = collections.defaultdict(lambda: collections.defaultdict(list))
            for t in T:
                v = view(C, t, orc)
                if v:
                    g[v[0]][BR.span_of(t["day"])].append(t["r"])
            info["true" if orc else "pred"] = {k: {sp: (len(x[sp]), round(float(np.mean(x[sp])), 3) if x[sp] else None) for sp in SP3}
                                               for k, x in g.items()}
        res["bots"][bot] = {"base": base, "r_by_type": info, "versions": {}}
        print(f"[{time.time() - t0:.0f}s] {bot} base fixed " + " ".join(f"{sp} n{base['fixed'][sp]['n']} ${base['fixed'][sp]['net']:,}"
                                                                         for sp in SP3), flush=True)
        print(f"   R by PREDICTED type: {info['pred']}")
        print(f"   R by TRUE type:      {info['true']}")
        for name, rule in rules:
            for orc in (False, True):
                M = mults(T, C, rule, "r", orc)
                o = evaluate(bot, M)
                why = []
                cks = {ck_of(t["entry_t"]) for t in T if M.get(t["entry_t"], 1.0) != 1.0}
                if orc:
                    why.append("ORACLE (true label, info only)")
                elif not all(gate_ck[c] for c in cks):
                    why.append("day call has no OOS information (kill-gate) at " + "/".join(sorted(c for c in cks if not gate_ck[c])))
                for sp in SP3:
                    if o["fixed"][sp]["net"] <= base["fixed"][sp]["net"]:
                        why.append(f"{sp} ${base['fixed'][sp]['net']:,} -> ${o['fixed'][sp]['net']:,}")
                    if (o["fixed"][sp]["pf"] or 0) < (base["fixed"][sp]["pf"] or 0):
                        why.append(f"{sp} PF {base['fixed'][sp]['pf']} -> {o['fixed'][sp]['pf']}")
                for sp in ("H1", "H2"):
                    if o["fixed"][sp]["tpw"] < (1 if bot == "blitz" else 2):
                        why.append(f"{sp} {o['fixed'][sp]['tpw']}/wk")
                    if bot == "lit":
                        e, eb = o["eval50_2wk"][sp], base["eval50_2wk"][sp]
                        if (e["net"] or 0) <= (eb["net"] or 0) or (e["f10"] or 0) > (eb["f10"] or 0):
                            why.append(f"{sp} 50K 2wk ${eb['net']:,.0f} f{eb['f10']} -> ${e['net']:,.0f} f{e['f10']}")
                        mc, mb = o["eval50_mc"][sp], base["eval50_mc"][sp]
                        if mc["p60"] < mb["p60"] - 2:
                            why.append(f"{sp} 50K MC pass {mb['p60']} -> {mc['p60']}")
                    elif bot == "atlas":
                        f_, fb = o["funded"][sp], base["funded"][sp]
                        if f_["per_month"] < fb["per_month"] or f_["dead_6m"] > fb["dead_6m"]:
                            why.append(f"{sp} funded ${fb['per_month']}/mo dead {fb['dead_6m']} -> ${f_['per_month']} dead {f_['dead_6m']}")
                    if bot in ("atlas", "blitz"):
                        e, eb = o["eval25"][sp], base["eval25"][sp]
                        if e["p10"] < eb["p10"] or e["f10"] > eb["f10"]:
                            why.append(f"{sp} 25K 2wk {eb['p10']}/{eb['f10']} -> {e['p10']}/{e['f10']}")
                pp = placebo(T, M, "usd")
                o["placebo_p"] = pp
                if pp is None or pp >= 0.05 / N_TESTS:
                    why.append(f"placebo p {pp}")
                o["why"] = why
                o["pass"] = not why
                key = name + (" [ORACLE]" if orc else "")
                res["bots"][bot]["versions"][key] = o
                fx = o["fixed"]
                extra = ""
                if bot == "lit":
                    extra = " | 50K 2wk " + " ".join(f"{sp} ${o['eval50_2wk'][sp]['net']:,.0f} p{o['eval50_2wk'][sp]['p10']}/f{o['eval50_2wk'][sp]['f10']}"
                                                     for sp in ("H1", "H2"))
                elif bot == "atlas":
                    extra = " | funded " + " ".join(f"{sp} ${o['funded'][sp]['per_month']}/mo d{o['funded'][sp]['dead_6m']}" for sp in ("H1", "H2", "REF"))
                print(f"   {key:45s} hit {o['hit']} | " + " ".join(f"{sp} ${fx[sp]['net']:,} PF {fx[sp]['pf']}" for sp in SP3) + extra +
                      f" | p {pp} | {'PASS' if o['pass'] else 'FAIL'}", flush=True)
    res["passers"] = [f"{b}: {k}" for b, x in res["bots"].items() for k, o in x["versions"].items() if o["pass"]]
    res["took_s"] = round(time.time() - t0)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1, default=float)
    print("passers:", res["passers"] or "none")


if __name__ == "__main__":
    main()
