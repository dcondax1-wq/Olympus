"""The 8 pre-registered structure variants (rules: research/structure/DESIGN.md, written before this ran). PAPER RESEARCH ONLY.

    python -X utf8 research/structure/variants.py      -> research/structure/variants.json (+ prints one line a variant)
"""
from __future__ import annotations

import collections
import json
import math
import os
import random
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, ROOT)
import bars as BR  # noqa: E402
import study as ST  # noqa: E402

OUT = os.path.join(HERE, "variants.json")
PV, COMM, SLIP, TICK = 2.0, 1.40, 0.25, 0.25
RISK_USD = 500.0
N_TESTS = 8
SPANS = ("H1", "H2", "2021-25")
B50 = {"target": 3000.0, "mll": 2000.0, "lock": 100.0, "dll": 1000.0}


# ================================================================================================ shared stats / evals
def sessions(X):
    return sorted(set(X["day"]))


def stats(T, sp, all_days):
    days = [d for d in all_days if BR.span_of(d) == sp]
    TT = [t for t in T if BR.span_of(t["day"]) == sp]
    p = np.array([t["pnl"] for t in TT]) if TT else np.zeros(0)
    gl = -p[p < 0].sum() if len(p) else 0
    eq = np.cumsum(p) if len(p) else np.zeros(1)
    dd = float((eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min()) if len(p) else 0.0
    wk = len(days) / 5 or 1
    e = eval_b50(TT, days)
    return {"n": len(TT), "tpw": round(len(TT) / wk, 2), "win": round(100 * float((p > 0).mean()), 1) if len(p) else None,
            "pf": round(float(p[p > 0].sum() / gl), 2) if gl else None, "net": round(float(p.sum())),
            "per_month": round(float(p.sum()) / (len(days) / 21)) if days else 0, "dd": round(dd), **e}


def eval_b50(TT, days, A=B50, horizon=40):
    """Rolling start on every session: Builder 50K rules, trades at their own $ (low = the worst open point if known)."""
    by = collections.defaultdict(list)
    for t in TT:
        by[t["day"]].append(t)
    res = []
    for i in range(len(days)):
        bal = peak = 0.0
        floor = -A["mll"]
        out = ("OPEN", None)
        for k, d in enumerate(days[i:i + horizon]):
            cum = 0.0
            for t in by.get(d, []):
                if cum <= -A["dll"]:
                    break
                low = min(0.0, t.get("low", min(0.0, t["pnl"])))
                if bal + cum + low <= floor:
                    out = ("FAIL", k + 1); break
                cum += t["pnl"]
            if out[0] == "FAIL":
                break
            bal += cum
            if bal <= floor:
                out = ("FAIL", k + 1); break
            peak = max(peak, bal)
            floor = min(max(floor, peak - A["mll"]), A["lock"])
            if bal >= A["target"]:
                out = ("PASS", k + 1); break
        res.append(out + (len(days) - i,))
    f10 = [r for r in res if r[2] >= 10] or res
    f40 = [r for r in res if r[2] >= horizon] or res
    pm = [r[1] for r in res if r[0] == "PASS"]
    return {"eval_p10": round(100 * sum(r[0] == "PASS" and r[1] <= 10 for r in f10) / len(f10), 1) if f10 else None,
            "eval_f10": round(100 * sum(r[0] == "FAIL" and r[1] <= 10 for r in f10) / len(f10), 1) if f10 else None,
            "eval_p40": round(100 * sum(r[0] == "PASS" for r in f40) / len(f40), 1) if f40 else None,
            "eval_days_med": float(np.median(pm)) if pm else None}


# ================================================================================================ standalone S1-S3
def _walk(X, j0, d, entry, stop, tg, day):
    """From bar j0 (filled at `entry` on that bar), to stop / target / 15:55. Returns (exit kind, pts, worst pts, exit bar)."""
    h, l, c, o, mins, D = X["h"], X["l"], X["c"], X["o"], X["mins"], X["day"]
    worst = 0.0
    j = j0
    n = len(h)
    while j < n and D[j] == day:
        if mins[j] >= 955 and mins[j] < 1080:
            return "EOD", (o[j] - entry) * d - SLIP, worst, j
        lo = (l[j] - entry) * d if d > 0 else (entry - h[j])
        worst = min(worst, lo)
        if (l[j] <= stop if d > 0 else h[j] >= stop):
            return "STOP", (stop - entry) * d - SLIP, min(worst, (stop - entry) * d - SLIP), j
        if (h[j] >= tg if d > 0 else l[j] <= tg):
            return "TARGET", (tg - entry) * d, worst, j
        j += 1
    j -= 1
    return "EOD", (c[j] - entry) * d - SLIP, worst, j


def _book(day, et, d, entry, stop, kind, pts, worst):
    risk = abs(entry - stop)
    q = max(1, min(40, int(RISK_USD / (risk * PV)))) if risk > 0 else 0
    if q == 0:
        return None
    return {"day": day, "entry_t": int(et), "dir": d, "risk": round(risk, 2), "qty": q, "exit": kind,
            "pnl": round(pts * PV * q - COMM * q, 2), "low": round(min(0.0, worst * PV * q - COMM * q), 2), "r": round(pts / risk, 3)}


def standalone_pullback(X, L, fib, tgt_ext):
    """S1 (fib 0.5, target the extreme) / S2 (fib 0.79, target 1.272): limit placed at the leg's confirmation bar."""
    h, l, mins, D, t = X["h"], X["l"], X["mins"], X["day"], X["t"]
    taken = set()
    out = []
    conf = sorted(p[3] for p in X["piv"])
    for x in sorted(L, key=lambda x: x["c1"]):
        if x["a_atr"] < ST.EXP_K or not x["disp"]:
            continue
        d, p0, p1, c1 = x["dir"], x["p0"], x["p1"], x["c1"]
        a = abs(p1 - p0)
        seg = slice(x["i1"] + 1, c1 + 1)
        deep = (p1 - l[seg].min()) / a if d > 0 else (h[seg].max() - p1) / a
        if deep >= fib:
            continue
        lvl = p1 - d * fib * a
        stop = p0 - d * TICK
        tg = p1 + d * tgt_ext * a
        nxt = conf[int(np.searchsorted(conf, c1, side="right"))] if np.searchsorted(conf, c1, side="right") < len(conf) else len(h)
        j = c1 + 1
        day = D[j] if j < len(D) else None
        while j < min(len(h), nxt + 1) and D[j] == day:
            m = mins[j]
            if 120 <= m <= 930 and (l[j] <= lvl if d > 0 else h[j] >= lvl):
                if day in taken:
                    break
                ent = lvl
                if (l[j] <= stop if d > 0 else h[j] >= stop):
                    kind, pts, worst, k = "STOP", (stop - ent) * d - SLIP, (stop - ent) * d - SLIP, j
                else:
                    kind, pts, worst, k = _walk(X, j + 1, d, ent, stop, tg, day)
                b = _book(day, t[j], d, ent, stop, kind, pts, worst)
                if b:
                    taken.add(day)
                    out.append(b)
                break
            if m > 930 and m < 1080:
                break
            j += 1
    return out


def standalone_s3(X):
    """S3: after a big day (prior range >= 1.5 ATR) or a big overnight (>= 0.6 ATR): the first 5m displacement 09:30-11:00
    -> next bar open, stop 1 tick beyond the candle's far end, target 2R."""
    D = X["D"]
    o, h, l, mins, day, disp, t = X["o"], X["h"], X["l"], X["mins"], X["day"], X["disp"], X["t"]
    ok = set(D.index[(D["prior_ratio"] >= 1.5) | (D["on_rng"] >= 0.6)])
    out, seen = [], set()
    for j in np.nonzero(disp)[0]:
        dd = day[j]
        if dd in seen or dd not in ok or not (570 <= mins[j] < 660) or j + 1 >= len(o) or day[j + 1] != dd:
            continue
        seen.add(dd)
        d = int(disp[j])
        ent = o[j + 1]
        stop = (l[j] - TICK) if d > 0 else (h[j] + TICK)
        risk = abs(ent - stop)
        if risk <= 1:
            continue
        kind, pts, worst, _ = _walk(X, j + 1, d, ent, stop, ent + d * 2 * risk, dd)
        b = _book(dd, t[j + 1], d, ent, stop, kind, pts, worst)
        if b:
            out.append(b)
    return out


def gate_standalone(S):
    why = []
    for sp in SPANS:
        s = S[sp]
        if not s["n"] or (s["pf"] or 0) < 1.10 or s["net"] <= 0:
            why.append(f"{sp}: PF {s['pf']} net ${s['net']:,}")
        if not (1 <= s["tpw"] <= 5):
            why.append(f"{sp}: {s['tpw']} trades/week")
    for sp in ("H1", "H2"):
        if (S[sp]["eval_p10"] or 0) <= (S[sp]["eval_f10"] or 0):
            why.append(f"{sp}: 2-week eval pass {S[sp]['eval_p10']}% <= fail {S[sp]['eval_f10']}%")
    return ("PASS" if not why else "FAIL"), why


# ================================================================================================ LIT F1-F3
def lit_variants(X):
    from tools import stops_targets_time as STT
    from tools import lit_edge as E
    U = STT.units()
    rows = [{"pillar": "lit", "span": BR.span_of(u["day"]), "day": u["day"], "entry_t": u["entry_t"], "dir": u["dir"],
             "r": 0.0, "usd": 0.0} for u in U]
    T = {r["entry_t"]: r for r in ST.tag_trades(X, rows)}
    tags = {u["entry_t"]: T.get(u["entry_t"]) for u in U}

    def f1(tg):
        return bool(tg and tg["early_disp"])

    def f2(tg):
        return bool(tg and tg["phase"] and tg["phase"].startswith("against") and tg["depth"] is not None and 0.5 <= tg["depth"] < 0.79)

    def f3(tg):
        return bool(tg and tg["pos"] < 0.2)

    base_L = STT.size_matched(U)
    base_E = E.eval_path(U)
    base = {"stats": {sp: STT.stats(base_L, sp) for sp in STT.SPANS},
            "eval50": {sp: {k: base_E[sp].get(k) for k in ("n", "net", "p10", "f10", "pass_med")} for sp in ("H1", "H2")}}
    out = {"base (live LIT)": base}
    for name, fn, kind in (("F1 LIT skip late chase", f1, "skip"), ("F2 LIT skip mid-retrace fade", f2, "skip"),
                           ("F3 LIT x1.5 at the day's extreme", f3, "boost")):
        hit = {u["entry_t"] for u in U if fn(tags[u["entry_t"]])}
        if kind == "skip":
            U2 = [u for u in U if u["entry_t"] not in hit]
            L2 = STT.size_matched(U2)
        else:
            U2 = [{**u, "m": 1.5} if u["entry_t"] in hit else u for u in U]
            L2 = []
            for l_ in base_L:
                if l_["entry_t"] in hit:
                    q = min(40, int(l_["qty"] * 1.5))
                    pnl = l_["pts"] * PV * q - COMM * q
                    l_ = {**l_, "qty": q, "pnl": round(pnl, 2)}
                L2.append(l_)
        Ev = E.eval_path(U2)
        o = {"hit": {sp: sum(1 for u in U if u["entry_t"] in hit and BR.span_of(u["day"]) == sp) for sp in SPANS},
             "stats": {sp: STT.stats(L2, sp) for sp in STT.SPANS},
             "eval50": {sp: {k: Ev[sp].get(k) for k in ("n", "net", "p10", "f10", "pass_med")} for sp in ("H1", "H2")},
             "placebo_p_H2": placebo_lit(base_L, hit, kind)}
        why = []
        for sp in ("H1", "H2"):
            if o["stats"][sp]["net"] <= base["stats"][sp]["net"]:
                why.append(f"{sp} net ${o['stats'][sp]['net']:,} vs live ${base['stats'][sp]['net']:,}")
            if (o["eval50"][sp]["net"] or 0) <= (base["eval50"][sp]["net"] or 0):
                why.append(f"{sp} 50K eval path ${o['eval50'][sp]['net']:,.0f} vs ${base['eval50'][sp]['net']:,.0f}")
            if (o["eval50"][sp]["f10"] or 0) > (base["eval50"][sp]["f10"] or 0):
                why.append(f"{sp} 2-week fails {o['eval50'][sp]['f10']}% vs {base['eval50'][sp]['f10']}%")
            if o["stats"][sp]["tpw"] < 2:
                why.append(f"{sp} {o['stats'][sp]['tpw']} trades/week")
        if o["placebo_p_H2"] is None or o["placebo_p_H2"] >= 0.05 / N_TESTS:
            why.append(f"H2 placebo p {o['placebo_p_H2']} (bar {0.05 / N_TESTS:.4f})")
        o["verdict"], o["why"] = ("PASS" if not why else "FAIL"), why
        out[name] = o
    return out


def placebo_lit(L, hit, kind, draws=2000, seed=7):
    H2 = [l_ for l_ in L if BR.span_of(l_["day"]) == "H2"]
    k = sum(1 for l_ in H2 if l_["entry_t"] in hit)
    if k == 0:
        return None
    def gain(sel):
        if kind == "skip":
            return -sum(l_["pnl"] for l_ in sel)
        return sum(l_["pnl"] * 0.5 for l_ in sel)
    g = gain([l_ for l_ in H2 if l_["entry_t"] in hit])
    rnd = random.Random(seed)
    beat = sum(gain(rnd.sample(H2, k)) >= g for _ in range(draws))
    return round(beat / draws, 4)


# ================================================================================================ ATLAS / BLITZ F4-F5
def pillar_variants(X, all_days):
    rows = [r for r in ST.pillar_rows() if r.get("span") in SPANS and r["pillar"] in ("atlas", "blitz")]
    T = ST.tag_trades(X, rows)
    out = {}
    for name, p, fn in (("F4 ATLAS skip middle of the range", "atlas", lambda r: 0.5 <= r["pos"] < 0.8),
                        ("F5 BLITZ skip half-used day", "blitz", lambda r: 0.5 <= r["used"] < 0.8)):
        P = [{"day": r["day"], "pnl": float(r["usd"] or 0), "skip": fn(r)} for r in T if r["pillar"] == p]
        P2 = [x for x in P if not x["skip"]]
        b = {sp: stats(P, sp, all_days) for sp in SPANS}
        v = {sp: stats(P2, sp, all_days) for sp in SPANS}
        why = []
        for sp in SPANS:
            if v[sp]["net"] <= b[sp]["net"]:
                why.append(f"{sp} net ${v[sp]['net']:,} vs ${b[sp]['net']:,}")
            if (v[sp]["pf"] or 0) < (b[sp]["pf"] or 0):
                why.append(f"{sp} PF {v[sp]['pf']} vs {b[sp]['pf']}")
        rnd = random.Random(7)
        k = sum(x["skip"] for x in P)
        g = -sum(x["pnl"] for x in P if x["skip"])
        beat = sum(-sum(x["pnl"] for x in rnd.sample(P, k)) >= g for _ in range(2000)) if k else 2000
        pp = round(beat / 2000, 4)
        if pp >= 0.05 / N_TESTS:
            why.append(f"placebo p {pp} (bar {0.05 / N_TESTS:.4f})")
        out[name] = {"skipped": {sp: sum(x["skip"] for x in P if BR.span_of(x["day"]) == sp) for sp in SPANS},
                     "base": b, "stats": v, "placebo_p": pp, "verdict": "PASS" if not why else "FAIL", "why": why}
    return out


def run(say=print):
    X = ST.context()
    L = ST.legs(X)
    days = sessions(X)
    res = {"made": "2026-11-24", "design": "research/structure/DESIGN.md", "variants": {}}
    for name, T in (("S1 expansion pullback 0.5 -> extreme", standalone_pullback(X, L, 0.5, 0.0)),
                    ("S2 deep pullback 0.79 -> 1.272", standalone_pullback(X, L, 0.79, 0.272)),
                    ("S3 expansion follows expansion (first 5m displacement)", standalone_s3(X))):
        S = {sp: stats(T, sp, days) for sp in SPANS}
        v, why = gate_standalone(S)
        res["variants"][name] = {"stats": S, "verdict": v, "why": why}
        say(f"{name}: {v} | " + " | ".join(f"{sp} n{S[sp]['n']} {S[sp]['tpw']}/wk PF {S[sp]['pf']} ${S[sp]['net']:,} "
                                             f"${S[sp]['per_month']:,}/mo DD ${S[sp]['dd']:,} 2wk {S[sp]['eval_p10']}/{S[sp]['eval_f10']}"
                                             for sp in SPANS))
    LV = lit_variants(X)
    res["lit_base"] = LV.pop("base (live LIT)")
    b = res["lit_base"]
    say("LIT live: " + " | ".join(f"{sp} n{b['stats'][sp]['n']} PF {b['stats'][sp]['pf']} ${b['stats'][sp]['net']:,}" for sp in STT_SP))
    for k, o in LV.items():
        res["variants"][k] = o
        say(f"{k}: {o['verdict']} | hit {o['hit']} | " + " | ".join(
            f"{sp} PF {o['stats'][sp]['pf']} ${o['stats'][sp]['net']:,} ${o['stats'][sp]['per_month']:,}/mo DD ${o['stats'][sp]['dd']:,}"
            for sp in STT_SP) + " | 50K " + " ".join(f"{sp} ${o['eval50'][sp]['net']:,.0f} 2wk {o['eval50'][sp]['p10']}/{o['eval50'][sp]['f10']}"
                                                  for sp in ("H1", "H2")) + f" | {'; '.join(o['why'])}")
    PV_ = pillar_variants(X, days)
    for k, o in PV_.items():
        res["variants"][k] = o
        say(f"{k}: {o['verdict']} | skipped {o['skipped']} | " + " | ".join(
            f"{sp} PF {o['base'][sp]['pf']}->{o['stats'][sp]['pf']} ${o['base'][sp]['net']:,}->${o['stats'][sp]['net']:,}" for sp in SPANS)
            + f" | {'; '.join(o['why'])}")
    res["passed"] = [k for k, o in res["variants"].items() if o["verdict"] == "PASS"]
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1, default=float)
    say(f"passed: {res['passed'] or 'none'} -> {os.path.relpath(OUT, ROOT)}")
    return res


STT_SP = ("H1", "H2", "2021-25")

if __name__ == "__main__":
    run()
