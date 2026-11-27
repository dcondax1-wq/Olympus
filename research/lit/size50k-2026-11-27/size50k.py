"""Builder 50K upsizing grid (DESIGN.md, pre-registered). PAPER RESEARCH ONLY: calls tools/money/combo_account, writes results.json.
    python -X utf8 research/lit/size50k-2026-11-27/size50k.py [--n 1000] [--workers 4]"""
import argparse, copy, json, os, sys, time
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
for p in (ROOT, os.path.join(ROOT, "tools"), os.path.join(ROOT, "tools", "money")):
    sys.path.insert(0, p)
import logging
logging.getLogger("engine.sizing").setLevel(logging.ERROR)
import combo_account as C  # noqa

ROOMS = (0.4, 0.5, 0.6, 0.7)
AFS = (0.5, 0.75, 1.0)
MKTS = ("H1", "H2", "REF", "Y2025")
TODAY = {"bal": -518.0, "floor": -1831.0, "peak": 169.0, "s": 25, "dtr": 5, "best": 300.0}
_cell_of0 = C.cell_of


def cell_of(r):
    c = _cell_of0(r)
    if r.get("lit_eval"):
        c["lit_eval"] = r["lit_eval"]
    return c


C.cell_of = cell_of


def row(room, af):
    r = C.frow("a50_eval", a_f={"eval": af, "funded": 1.0})
    ze = copy.deepcopy(C.plan("b50")["z_eval"])
    ze["two_week"]["room_f"] = room
    r["lit_eval"] = ze
    return r


def set_today(e):
    e.bal, e.floor, e.peak, e.s, e.dtr, e.best = (TODAY[k] for k in ("bal", "floor", "peak", "s", "dtr", "best"))


def eval_run(r, paths, today):
    De = C.combo_days(r["eval"])
    cell = C.cell_of(r)
    out = []
    for seq in paths:
        e = C.Eval(cell, r["eval"])
        if today:
            set_today(e)
        res, used = "open", len(seq)
        for k, si in enumerate(seq):
            x, _ = e.step(De[si])
            if x:
                res, used = ("pass" if x == "pass" else "fail"), k + 1
                break
        out.append((res, used, e.max_risk))
    n = len(out)
    ps = [u for o, u, _ in out if o == "pass"]; fs = [u for o, u, _ in out if o == "fail"]
    return {"pass": round(100.0 * len(ps) / n, 1), "fail": round(100.0 * len(fs) / n, 1),
            "med_pass": float(np.median(ps)) if ps else None, "med_fail": float(np.median(fs)) if fs else None,
            "max_risk_med": round(float(np.median([m for *_, m in out]))), "max_risk_p90": round(float(np.percentile([m for *_, m in out], 90)))}


def slot_run(r, paths, today):
    De = C.combo_days(r["eval"]); Df = C.combo_days(r["funded"])
    out = []
    for seq in paths:
        s = C.Slot(r)
        if today:
            set_today(s.e); s.cost = 0.0           # the current eval is already paid for
        for k, si in enumerate(seq):
            s.step(k, De[si], Df[si])
        out.append(s.out())
    net = np.array([q[0] for q in out]); fp = [q[7] for q in out if q[7]]
    return {"net_6m": round(float(net.mean())), "per_month": round(float(net.mean()) / C.MONTHS), "net_p10": round(float(np.percentile(net, 10))),
            "owner_6m": round(float(np.mean([q[1] for q in out]))), "evals": round(float(np.mean([q[3] for q in out])), 2),
            "first_pay_med": float(np.median(fp)) if fp else None, "no_pay": round(100.0 * sum(1 for q in out if not q[7]) / len(out), 1),
            "_net": net.tolist()}


def job(a):
    room, af, m, n = a
    C._patch_account_b()
    r = row(room, af)
    PE = C.day_paths(m, n, length=C.H_EVAL, seed=C.SEED_SLOT)
    PS = C.day_paths(m, n, seed=C.SEED_FUND)
    t0 = time.time()
    o = {"eval_fresh": eval_run(r, PE, False), "eval_today": eval_run(r, PE, True),
         "slot_fresh": slot_run(r, PS, False), "slot_today": slot_run(r, PS, True)}
    return room, af, m, o, round(time.time() - t0)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--n", type=int, default=1000); ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    C.trades(); C.atlas_paths(); C._patch_account_b()
    cells = [(r_, f_) for r_ in ROOMS for f_ in AFS]
    if a.only:
        cells = [tuple(map(float, x.split("/"))) for x in a.only.split(",")]
    jobs = [(r_, f_, m, a.n) for r_, f_ in cells for m in MKTS]
    res = {}
    import multiprocessing as mp
    t0 = time.time()
    with mp.get_context("fork").Pool(a.workers) as pool:
        for room, af, m, o, sec in pool.imap_unordered(job, jobs):
            res.setdefault(f"{room}/{af}", {})[m] = o
            print(f"{room}/{af} {m} {sec}s eval {o['eval_fresh']['pass']}/{o['eval_fresh']['fail']}% ~{o['eval_fresh']['med_pass']} "
                  f"today {o['eval_today']['pass']}/{o['eval_today']['fail']}% slot ${o['slot_fresh']['net_6m']} today ${o['slot_today']['net_6m']} "
                  f"[{time.time() - t0:.0f}s]", flush=True)
    # judge (DESIGN.md)
    L = res.get("0.4/0.5")
    for k, R in res.items():
        if L is None or k == "0.4/0.5":
            continue
        g = lambda mk, f, st="slot_fresh": R[mk][st][f] - L[mk][st][f]  # noqa
        paired = {mk: round(float(np.std(np.array(R[mk]["slot_fresh"]["_net"]) - np.array(L[mk]["slot_fresh"]["_net"])) / np.sqrt(a.n))) for mk in MKTS}
        ok = (g("H1", "net_6m") > 0 and g("H2", "net_6m") > 0 and R["H1"]["eval_fresh"]["pass"] >= L["H1"]["eval_fresh"]["pass"]
              and R["H2"]["eval_fresh"]["pass"] >= L["H2"]["eval_fresh"]["pass"] and g("REF", "net_6m") >= -100
              and R["REF"]["eval_fresh"]["fail"] <= L["REF"]["eval_fresh"]["fail"] + 3)
        R["judge"] = {"d_net": {mk: g(mk, "net_6m") for mk in MKTS}, "paired_se": paired, "qualifies": bool(ok)}
    for R in res.values():
        for m in MKTS:
            for st in ("slot_fresh", "slot_today"):
                R[m][st].pop("_net", None)
    q = [k for k, R in res.items() if R.get("judge", {}).get("qualifies")]
    pick = max(q, key=lambda k: res[k]["H1"]["slot_fresh"]["net_6m"]) if q else "0.4/0.5"
    json.dump({"design": "DESIGN.md", "n": a.n, "today": TODAY, "cells": res, "qualifying": q, "pick": pick},
              open(os.path.join(HERE, "results.json" if not a.only else "results_partial.json"), "w"), indent=1)
    print("qualifying", q, "pick", pick)


if __name__ == "__main__":
    main()
