"""ATLAS v2: survive real fills (research/atlas2/DESIGN.md, pre-registered ea5a20d9). PAPER RESEARCH ONLY.

    python -X utf8 research/atlas2/atlas2.py build          # the 8 variants' trades -> research/atlas2/trades.json.gz + fixed-$250 table
    python -X utf8 research/atlas2/atlas2.py engines V2     # one variant through the real engines (own process: the engines patch globals)
    python -X utf8 research/atlas2/atlas2.py final          # merge the engine files + the gate -> results.json
    python -X utf8 research/atlas2/atlas2.py all            # build + every variant's engines in subprocesses -> results.json
"""
from __future__ import annotations

import gzip
import json
import os
import subprocess
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
for p in (ROOT, os.path.join(ROOT, "tools", "money"), os.path.join(ROOT, "research", "plans")):
    sys.path.insert(0, p)
import logging  # noqa: E402
logging.getLogger("engine.sizing").setLevel(logging.ERROR)

TRADES = os.path.join(HERE, "trades.json.gz")
OUT = os.path.join(HERE, "results.json")
TICK, PV, COMM = 0.25, 2.0, 1.90
E_MKT, X_MKT = 12, 2                      # calibrated: market entry 12 ticks, market / stop exit 2 ticks, target 0, limit entry 0
SPANS = {"2021-25": ("2021-11-01", "2025-12-31"), "2026 H1": ("2026-01-01", "2026-06-30"), "2026 Jul-Oct": ("2026-07-01", "2026-10-16")}
WF = {str(y): (f"{y}-01-01", f"{y}-12-31") for y in (2022, 2023, 2024, 2025)}
VARIANTS = {
    "V0": {"what": "today: market, EMA + MACD + S/R", "entry": "market"},
    "V1": {"what": "limit at the 5m open, 5 min (= F1)", "entry": "limit", "f": 0.0, "timeout": 5},
    "V2": {"what": "limit 0.25 R inside the signal, 15 min", "entry": "limit", "f": 0.25, "timeout": 15},
    "V3": {"what": "limit 0.5 R inside, 30 min", "entry": "limit", "f": 0.5, "timeout": 30},
    "V4": {"what": "market, EMA removed", "entry": "market", "drop": ("EMA",)},
    "V5": {"what": "V2 + EMA removed", "entry": "limit", "f": 0.25, "timeout": 15, "drop": ("EMA",)},
    "V6": {"what": "market, all + regime switch (rolling 40-signal mean R > 0)", "entry": "market", "switch": 40},
    "V7": {"what": "V5 + the regime switch", "entry": "limit", "f": 0.25, "timeout": 15, "drop": ("EMA",), "switch": 40},
}
MEMBER = {"EMA": "EMA", "MD": "MACD", "SR": "S/R"}


def _AF():
    from tools import atlas_fills as AF
    return AF


# ============================================================================================ fills
def market(u):
    return _AF().priced(u, E_MKT, X_MKT)


def limit_signal(u, f, timeout):
    """Resting limit f x (open-based risk) inside the 5m open; filled only if price trades 1 tick THROUGH it within `timeout`
    minutes (1m bars where they exist, else the 5m bars). Stop / target prices unchanged. None = no trade."""
    AF = _AF()
    B5, B1 = AF._bars()
    d = int(u["dir"])
    et_ = int(u["entry_t"])
    k5, o = AF._open5(u)
    risk_o = float(u["risk"]) - TICK                     # the stored unit enters 1 tick past the open
    imp = round(f * risk_o / TICK) * TICK
    L = o * d - imp                                      # limit, dir space (higher = worse for us)
    need = L - TICK
    fill_t = None                                        # start of the bar that filled, + its length
    on1 = et_ >= int(B1.t[0]) + 86400
    if on1:
        j = int(np.searchsorted(B1.t, et_))
        if j < len(B1.t) and int(B1.t[j]) == et_:
            for m in range(timeout):
                if j + m >= len(B1.t) or int(B1.t[j + m]) >= et_ + 60 * timeout:
                    break
                lo_q = float(B1.l[j + m]) if d == 1 else -float(B1.h[j + m])
                if f == 0.0 and m == 0:                  # at the open itself: the first minute must CLOSE through (F1's rule)
                    lo_q = float(B1.c[j]) * d
                if lo_q <= need:
                    fill_t = (int(B1.t[j + m]), 60)
                    break
        else:
            on1 = False
    if not on1:
        for m in range(max(1, timeout // 5)):
            k = k5 + m
            if k >= len(B5.t) or int(B5.t[k]) >= et_ + 60 * max(5, timeout):
                break
            lo_q = float(B5.l[k]) if d == 1 else -float(B5.h[k])
            if f == 0.0 and m == 0:
                lo_q = float(B5.c[k]) * d
            if lo_q <= need:
                fill_t = (int(B5.t[k]), 300)
                break
    if fill_t is None:
        return None
    t0, ln = fill_t
    if AF.is_target(u) and int(u["exit_t"]) < t0 + ln:
        return None                                      # the target was (or may have been) reached before the fill
    if not AF.is_target(u) and int(u["exit_t"]) < t0:
        return None                                      # the stored trade was already over
    risk = risk_o - imp
    if risk <= 1.0:
        return None
    gain = TICK + imp                                    # vs the stored entry (open + 1 tick)
    ex = 0.0 if AF.is_target(u) else (X_MKT - 1) * TICK
    pts = float(u["pts"]) + gain - ex
    w1 = min(0.0, float(u["w1"]) + gain, pts)
    tgt = (float(u["tgt"]) + gain) if u.get("tgt") else u.get("tgt")
    return {**u, "risk": round(risk, 4), "tgt": tgt, "pts": round(pts, 4), "w1": round(w1, 4), "fill_t": t0}


def r_cost(t):
    return (float(t["pts"]) - COMM / PV) / float(t["risk"])


def switch(T, n):
    """keep a trade only while the mean R of the last n paper signals CLOSED before its entry is > 0 (fewer than n: keep)."""
    ex = sorted(T, key=lambda t: t["exit_t"])
    xs = np.array([t["exit_t"] for t in ex]); rs = np.array([t["R_c"] for t in ex])
    out = []
    for t in T:
        k = int(np.searchsorted(xs, t["entry_t"], side="right"))
        if k < n or rs[k - n:k].mean() > 0:
            out.append(t)
    return out


def build_variant(name, U):
    AF = _AF()
    V = VARIANTS[name]
    UU = [u for u in U if u["src"] not in V.get("drop", ())]
    if V["entry"] == "market":
        P = [market(u) for u in UU]
    else:
        P = [x for x in (limit_signal(u, V["f"], V["timeout"]) for u in UU) if x is not None]
    T = AF.to_T(P)
    for t in T:
        t["R_c"] = r_cost(t)
    if V.get("switch"):
        T = switch(T, V["switch"])
    return T, len(UU)


# ============================================================================================ fixed $250 scoring
def fixed(T, a, z):
    X = [t for t in T if a <= t["day"] <= z]
    if not X:
        return {"n": 0}
    usd = np.array([t["R_c"] * 250.0 for t in X])
    days = sorted({t["day"] for t in X})
    import datetime as dt
    d0, d1 = dt.date.fromisoformat(a), min(dt.date.fromisoformat(z), dt.date(2026, 10, 16))
    weeks = (d1 - d0).days / 7.0
    eq = np.cumsum(usd)
    dd = float((np.maximum.accumulate(np.r_[0, eq]) - np.r_[0, eq]).max())
    g, l = usd[usd > 0].sum(), -usd[usd < 0].sum()
    return {"n": len(X), "tpw": round(len(X) / weeks, 2), "pf": round(float(g / l), 2) if l else None, "net": round(float(usd.sum())),
            "per_month": round(float(usd.sum()) / (weeks / 4.345)), "max_dd": round(dd), "mean_r": round(float(usd.mean() / 250), 3),
            "_days": len(days)}


def table(T):
    out = {sp: fixed(T, a, z) for sp, (a, z) in SPANS.items()}
    out["wf"] = {y: fixed(T, a, z) for y, (a, z) in WF.items()}
    out["members"] = {MEMBER[m]: {sp: fixed([t for t in T if t["src"] == m], a, z) for sp, (a, z) in SPANS.items()} for m in MEMBER}
    return out


def cmd_build(say=print):
    AF = _AF()
    t0 = time.time()
    U = AF.units()
    res, dump = {}, {}
    for v in VARIANTS:
        T, nsig = build_variant(v, U)
        dump[v] = T
        res[v] = {"what": VARIANTS[v]["what"], "signals": nsig, "trades": len(T), **table(T)}
        r = res[v]
        say(f"{v} {VARIANTS[v]['what'][:44]:44s} " + " | ".join(
            f"{sp} {r[sp]['tpw']}/wk PF {r[sp]['pf']} ${r[sp]['net']} dd ${r[sp]['max_dd']}" for sp in SPANS)
            + " | WF " + " ".join(f"{y}:{r['wf'][y]['net']}" for y in WF) + f" [{time.time() - t0:.0f}s]", flush=True)
    with gzip.open(TRADES, "wt", encoding="utf-8") as fh:
        json.dump(dump, fh, default=float)
    old = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
    old.update({"made": "2026-11-26", "design": "research/atlas2/DESIGN.md (ea5a20d9)", "costs": {"market_entry_ticks": E_MKT,
                "market_exit_ticks": X_MKT, "target_exit": 0, "limit_entry": 0, "commission_rt": COMM}, "fixed": res})
    json.dump(old, open(OUT, "w", encoding="utf-8"), indent=1, default=float)
    return res


# ============================================================================================ real engines (one variant a process)
def cmd_engines(v, n=600, say=print):
    t0 = time.time()
    AF = _AF()
    T = json.load(gzip.open(TRADES, "rt", encoding="utf-8"))[v]
    for t in T:
        t["w"] = 1.0
    out = {"funded_25k": AF.score_funded(T)}
    say(f"{v} funded done [{time.time() - t0:.0f}s]", flush=True)
    out["rapid_25k"] = AF.rapid_rows(T, n_paths=n, with_off=(v == "V0"))
    say(f"{v} rapid done [{time.time() - t0:.0f}s]", flush=True)
    import rank as R
    from tools import atlas_risk as AR
    AR.rapid_patch(T)
    S = R.SOA.data()["S"]
    PF = {sp: R.U.mc_paths(S, sp, n, length=R.LEN, seed=23) for sp in R.SPANS}
    PE = {sp: R.U.mc_paths(S, sp, n, length=R.H_EVAL, seed=7) for sp in R.SPANS}
    out["builder"] = {}
    for plan in ("mffu_builder_50k", "mffu_builder_25k"):
        sp = R.spec(plan)
        out["builder"][plan] = {s: {"eval": R.eval_run(sp, PE[s]), "slot": R.slot_run(sp, PF[s])} for s in R.SPANS}
    say(f"{v} builder done [{time.time() - t0:.0f}s]", flush=True)
    json.dump(out, open(os.path.join(HERE, f"_eng_{v}.json"), "w", encoding="utf-8"), indent=1, default=float)
    return out


def cmd_all(say=print):
    cmd_build(say)
    eng = {}
    for v in VARIANTS:
        subprocess.run([sys.executable, "-X", "utf8", os.path.abspath(__file__), "engines", v], check=True)
        p = os.path.join(HERE, f"_eng_{v}.json")
        eng[v] = json.load(open(p, encoding="utf-8"))
        os.remove(p)
    res = json.load(open(OUT, encoding="utf-8"))
    res["engines"] = eng
    json.dump(res, open(OUT, "w", encoding="utf-8"), indent=1, default=float)
    return res


# ============================================================================================ the pre-registered gate
def gate(res):
    F, E = res["fixed"], res["engines"]
    b = F["V0"]
    out = {}
    for v in VARIANTS:
        if v == "V0":
            continue
        x = F[v]
        fx = all((x[sp]["net"] > b[sp]["net"]) and ((x[sp]["pf"] or 0) > (b[sp]["pf"] or 0)) for sp in SPANS)
        wf = sum(x["wf"][y]["net"] > b["wf"][y]["net"] for y in WF)
        fu, fb = E[v]["funded_25k"]["funded"], E["V0"]["funded_25k"]["funded"]
        fund = fu["H1"]["per_month"] >= fb["H1"]["per_month"] and fu["H2"]["per_month"] >= fb["H2"]["per_month"] and \
            fu["REF"]["per_month"] > fb["REF"]["per_month"]
        tpw = all(1.5 <= x[sp]["tpw"] <= 4.1 for sp in SPANS)
        lr = (x["2021-25"]["pf"] or 0) >= 1.0
        give = 1 - (x["2026 H1"]["net"] + x["2026 Jul-Oct"]["net"]) / (b["2026 H1"]["net"] + b["2026 Jul-Oct"]["net"])
        out[v] = {"fixed_all_3_better": fx, "wf_years_better": wf, "funded_ok": fund, "tpw_ok": tpw, "pf_2021_25_ge_1": lr,
                  "pass": fx and wf >= 3 and fund and tpw and lr, "gives_up_2026_pct": round(100 * give, 1),
                  "switch_rule": bool(VARIANTS[v].get("switch")) and x["2021-25"]["net"] >= 0 and give < 0.15}
    passed = [v for v in out if out[v]["pass"]]
    sw = [v for v in out if out[v]["switch_rule"]]
    verdict = (f"ATLAS v2 card: {passed}" if passed else
               f"keep ATLAS only in 2026-like markets with the regime switch ({sw[0]})" if sw else
               "ATLAS stays as is: 2026-like markets only; no pre-registered fix or switch earns its keep")
    return out, verdict


def cmd_final():
    res = json.load(open(OUT, encoding="utf-8"))
    eng = {}
    for v in VARIANTS:
        p = os.path.join(HERE, f"_eng_{v}.json")
        if os.path.exists(p):
            eng[v] = json.load(open(p, encoding="utf-8"))
    res["engines"] = {**res.get("engines", {}), **eng}
    res["gate"], res["verdict"] = gate(res)
    json.dump(res, open(OUT, "w", encoding="utf-8"), indent=1, default=float)
    for v in VARIANTS:
        p = os.path.join(HERE, f"_eng_{v}.json")
        if os.path.exists(p):
            os.remove(p)
    print(json.dumps(res["gate"], indent=0)); print(res["verdict"])


if __name__ == "__main__":
    a = sys.argv[1:] or ["build"]
    if a[0] == "build":
        cmd_build()
    elif a[0] == "engines":
        cmd_engines(a[1])
    elif a[0] == "final":
        cmd_final()
    elif a[0] == "all":
        cmd_all()
        cmd_final()
