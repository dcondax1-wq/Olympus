"""edge2 (2026-11-21): 10 pre-registered ideas (research/edge2/DESIGN.md) - ATLAS entry variants A1-A4 and new NQ setups N1-N6.
PAPER RESEARCH ONLY: reads data/NQ_5m.csv + the stored LIT / ATLAS trades, writes research/edge2/results.json.

    python -X utf8 research/edge2/edge2.py n          # N1-N6 (fast)
    python -X utf8 research/edge2/edge2.py a [--n 1000]   # A1-A4 on the atlas_edge funded engine
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
for p in (ROOT, os.path.join(ROOT, "tools"), os.path.join(ROOT, "tools", "money"), os.path.join(ROOT, "research", "newstrat")):
    sys.path.insert(0, p)
import logging  # noqa: E402
logging.getLogger("engine.sizing").setLevel(logging.ERROR)
import smt as NS  # noqa: E402  (research/newstrat: data loader, stats, eval sim)

OUT = os.path.join(HERE, "results.json")
TICK, COMM, PV, RISK_USD, MAXQ = 0.25, 1.90, 2.0, 250.0, 20
PERIODS = {"H1": ("2026-01-01", "2026-06-30"), "H2": ("2026-07-01", "2026-10-31"), "REF": ("2021-11-01", "2025-12-31")}


def save(key, val):
    R = json.load(open(OUT)) if os.path.exists(OUT) else {}
    R[key] = val
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(R, fh, indent=1, default=float)


# ================================================================================================ N: the trade engine
def sim(X, j0, dr, entry, stop, tgt, limit=False, wait=0):
    """Entry at bar j0: market = X.o[j0] + 1 tick (entry None) or a limit at `entry` live for `wait` bars from j0 (fills on a
    trade 1 tick through). Stop fills 1 tick worse; target needs 1 tick through; stop first; flat at the 15:55 bar close."""
    n = len(X["t"])
    if limit:
        jf = None
        for j in range(j0, min(n, j0 + wait)):
            if (dr == 1 and X["l"][j] <= entry - TICK) or (dr == -1 and X["h"][j] >= entry + TICK):
                jf = j
                break
            if (dr == 1 and X["h"][j] >= tgt + TICK) or (dr == -1 and X["l"][j] <= tgt - TICK):
                return {"skip": "ran"}
        if jf is None:
            return {"skip": "nofill"}
        e, j1 = entry, jf
    else:
        if j0 >= n:
            return {"skip": "late"}
        e, j1 = X["o"][j0] + dr * TICK, j0
    risk = (e - stop) * dr
    if risk <= 0:
        return {"skip": "gap"}
    if tgt is None or (tgt - e) * dr <= 0:
        return {"skip": "tgt"}
    q = min(MAXQ, int(RISK_USD // ((risk + TICK) * PV + COMM)))
    if q < 1:
        return {"skip": "wide"}
    ex, why, mae = None, "EOD", 0.0
    for j in range(j1, n):
        hi, lo = X["h"][j], X["l"][j]
        if limit and j == j1:              # the fill bar: only the stop can act after a limit fill (conservative)
            if (dr == 1 and lo <= stop) or (dr == -1 and hi >= stop):
                ex, why = stop - dr * TICK, "STOP"
                mae = risk
                break
            if X["m"][j] >= 955:
                ex = X["c"][j]
                break
            continue
        mae = max(mae, (e - lo) if dr == 1 else (hi - e))
        if (dr == 1 and lo <= stop) or (dr == -1 and hi >= stop):
            ex, why = stop - dr * TICK, "STOP"
            break
        if (dr == 1 and hi >= tgt + TICK) or (dr == -1 and lo <= tgt - TICK):
            ex, why = tgt, "TGT"
            break
        if X["m"][j] >= 955:
            ex = X["c"][j]
            break
    if ex is None:
        ex = X["c"][-1]
    pts = (ex - e) * dr
    return {"dir": dr, "entry": round(float(e), 2), "stop": round(float(stop), 2), "tgt": round(float(tgt), 2),
            "risk": round(float(risk), 2), "q": q, "exit": why, "pts": round(float(pts), 2), "r": round(float(pts / risk), 3),
            "pnl": round(q * (pts * PV - COMM), 2), "pnl10": round(q * ((pts - 10 * TICK) * PV - COMM), 2),
            "low": round(-q * (min(mae, risk + TICK) * PV + COMM), 2), "entry_t": int(X["t"][j1]), "exit_t": int(X["t"][min(j, n - 1)])}


def first(X, a, b):
    return [j for j in range(len(X["t"])) if a <= X["m"][j] < b]


def n_setups(day, X, ctx):
    """-> {N1..N6: trade dict | skip dict | None} for one day."""
    out = {}
    m = X["m"]
    ib = [j for j in range(len(m)) if 570 <= m[j] < 630]
    adr = ctx["adr"]
    if len(ib) < 10 or adr is None:
        return out
    ibh, ibl = float(X["h"][ib].max()), float(X["l"][ib].min())
    ibm = (ibh + ibl) / 2
    after = [j for j in range(len(m)) if m[j] >= 630]
    rth_end = len(m)

    # N1 IB failed-break fade
    r = None
    brk, side, ext = None, 0, None
    for j in after:
        if m[j] >= 870:
            break
        if brk is None:
            if X["h"][j] >= ibh + TICK and X["l"][j] <= ibl - TICK:
                break
            if X["h"][j] >= ibh + TICK:
                brk, side, ext = j, -1, X["h"][j]
            elif X["l"][j] <= ibl - TICK:
                brk, side, ext = j, 1, X["l"][j]
            if brk is None:
                continue
        else:
            ext = max(ext, X["h"][j]) if side == -1 else min(ext, X["l"][j])
        if j - brk > 3:
            break
        if (side == -1 and X["c"][j] < ibh) or (side == 1 and X["c"][j] > ibl):
            stop = ext + TICK if side == -1 else ext - TICK
            e0 = X["o"][j + 1] + side * TICK if j + 1 < rth_end else None
            if e0 is not None and m[j + 1] < 870:
                r = sim(X, j + 1, side, None, stop, e0 + side * 2 * abs(e0 - stop))
            break
    out["N1"] = r

    # N2 IB break-retest (limit at the IB edge), N5 first-hour trend
    r = None
    for j in after:
        if m[j] >= 870:
            break
        if X["c"][j] > ibh or X["c"][j] < ibl:
            dr = 1 if X["c"][j] > ibh else -1
            lvl = ibh if dr == 1 else ibl
            stop = ibm - dr * TICK
            if abs(lvl - stop) > 0.5 * adr:
                r = {"skip": "wide_stop"}
            elif j + 1 < rth_end:
                r = sim(X, j + 1, dr, lvl, stop, lvl + dr * 2 * abs(lvl - stop), limit=True, wait=6)
            break
    out["N2"] = r
    r = None
    j10 = next((j for j in range(len(m)) if m[j] == 630), None)
    if j10 is not None:
        mv = X["c"][ib[-1]] - X["o"][ib[0]]
        pos = (X["c"][ib[-1]] - ibl) / max(1e-9, ibh - ibl)
        if abs(mv) >= 0.35 * adr and ((mv > 0 and pos >= 0.8) or (mv < 0 and pos <= 0.2)):
            dr = 1 if mv > 0 else -1
            e0 = X["o"][j10] + dr * TICK
            stop = ibm - dr * TICK
            r = sim(X, j10, dr, None, stop, e0 + dr * 2 * abs(e0 - stop))
    out["N5"] = r

    # N3 prior-day level break-retest
    r = None
    pdh, pdl = ctx["pd_h"], ctx["pd_l"]
    for j in range(len(m)):
        if m[j] < 585:
            continue
        if m[j] >= 900:
            break
        if X["c"][j] > pdh or X["c"][j] < pdl:
            dr = 1 if X["c"][j] > pdh else -1
            lvl = pdh if dr == 1 else pdl
            k = max(0, j - 3)
            stop = (X["l"][k:j].min() - TICK) if dr == 1 else (X["h"][k:j].max() + TICK)
            if j - k < 1 or (lvl - stop) * dr <= 0 or abs(lvl - stop) > 0.5 * adr:
                r = {"skip": "stop"}
            elif j + 1 < rth_end:
                r = sim(X, j + 1, dr, lvl, stop, lvl + dr * 2 * abs(lvl - stop), limit=True, wait=6)
            break
    out["N3"] = r

    # N4 opening gap fade
    r = None
    pc = ctx["prev_close"]
    j0 = next((j for j in range(len(m)) if m[j] == 570), None)
    if j0 is not None and j0 + 1 < rth_end and pc:
        g = (X["o"][j0] - pc) / pc
        if 0.0015 <= abs(g) <= 0.008:
            dr = -1 if g > 0 else 1
            if (dr == -1 and X["c"][j0] < X["o"][j0]) or (dr == 1 and X["c"][j0] > X["o"][j0]):
                e0 = X["o"][j0 + 1] + dr * TICK
                stop = X["h"][j0] + TICK if dr == -1 else X["l"][j0] - TICK
                risk = (e0 - stop) * dr
                tgt = pc - dr * TICK
                rr = (tgt - e0) * dr / risk if risk > 0 else 0
                if rr < 1:
                    r = {"skip": "rr"}
                else:
                    r = sim(X, j0 + 1, dr, None, stop, tgt if rr <= 3 else e0 + dr * 3 * risk)
    out["N4"] = r

    # N6 overnight-inside breakout
    r = None
    if ctx["on_h"] <= pdh and ctx["on_l"] >= pdl:
        for j in range(len(m)):
            if m[j] < 570:
                continue
            if m[j] >= 660:
                break
            if X["c"][j] > pdh or X["c"][j] < pdl:
                dr = 1 if X["c"][j] > pdh else -1
                stop = X["l"][j] - TICK if dr == 1 else X["h"][j] + TICK
                e_est = X["c"][j]
                if not 8 <= abs(e_est - stop) <= 0.5 * adr:
                    r = {"skip": "stop"}
                elif j + 1 < rth_end:
                    e0 = X["o"][j + 1] + dr * TICK
                    r = sim(X, j + 1, dr, None, stop, e0 + dr * 2 * abs(e0 - stop))
                break
    out["N6"] = r
    return out


def lit_atlas_daily():
    import account4_sim as A4
    import atlas_health as AH
    S, BY = A4.load()
    d = collections.defaultdict(float)
    pos = []
    for t in [x for ts in BY for x in ts] + list(AH.stream()):
        q = int(250.0 // ((t["risk"] + 0.25) * PV + COMM))
        if q > 0:
            d[t["day"]] += q * (t["pts"] * PV - COMM)
    return d


def cmd_n(log=print):
    t0 = time.time()
    DN = NS.days_of(NS.load("NQ"))
    days = sorted(DN)
    ranges = {d: float(DN[d]["h"].max() - DN[d]["l"].min()) for d in days}
    T = collections.defaultdict(list)
    skips = collections.defaultdict(collections.Counter)
    for i, d in enumerate(days):
        if i < 15:
            continue
        X = DN[d]
        prev = DN[days[i - 1]]
        ctx = {"adr": float(np.mean([ranges[x] for x in days[i - 14:i]])), "pd_h": X["pd_h"], "pd_l": X["pd_l"],
               "on_h": X["on_h"], "on_l": X["on_l"], "prev_close": float(prev["c"][-1])}
        for k, r in n_setups(d, X, ctx).items():
            if r is None:
                continue
            if "skip" in r:
                skips[k][r["skip"]] += 1
            else:
                T[k].append({**r, "day": d})
    base = lit_atlas_daily()
    daily_la, pos_la = NS.others()
    out = {}
    for k in ("N1", "N2", "N3", "N4", "N5", "N6"):
        row = {"skips": dict(skips[k])}
        for p, (a, b) in PERIODS.items():
            ds = [d for d in days if a <= d <= b]
            tt = [t for t in T[k] if a <= t["day"] <= b]
            st = NS.stats(tt, ds)
            st["net10"] = NS.stats(tt, ds, "pnl10")["net"]
            st["eval_rapid"] = NS.evals(tt, ds, NS.PLANS["rapid_eod_25k"])
            mine = collections.defaultdict(float)
            for t in tt:
                mine[t["day"]] += t["pnl"]
            b0 = [base.get(d, 0.0) for d in ds]
            b1 = [base.get(d, 0.0) + mine.get(d, 0.0) for d in ds]
            st["stack"] = {"breach_per100_base": round(100.0 * sum(x < -500 for x in b0) / len(ds), 2),
                           "breach_per100_with": round(100.0 * sum(x < -500 for x in b1) / len(ds), 2),
                           "rapid_pass_base": stack_eval(b0), "rapid_pass_with": stack_eval(b1)}
            st["corr"] = NS.correlation(tt, ds, daily_la, pos_la)
            row[p] = st
        row["pass"] = all(row[p]["net"] > 0 and (row[p]["pf"] or 0) >= 1.2 and row[p]["net10"] > 0 and 0.8 <= row[p]["tpw"] <= 2.5
                          and row[p]["stack"]["breach_per100_with"] <= row[p]["stack"]["breach_per100_base"]
                          and row[p]["stack"]["rapid_pass_with"] > row[p]["stack"]["rapid_pass_base"] for p in PERIODS)
        row["trades"] = T[k]
        out[k] = row
        log(f"{k} " + " | ".join(f"{p} {row[p]['trades']}t {row[p]['tpw']}/wk PF {row[p]['pf']} ${row[p]['net']} s10 ${row[p]['net10']} "
                                 f"dd {row[p]['max_dd']} brch {row[p]['stack']['breach_per100_base']}->{row[p]['stack']['breach_per100_with']} "
                                 f"pass {row[p]['stack']['rapid_pass_base']}->{row[p]['stack']['rapid_pass_with']}" for p in PERIODS)
            + f" {'PASS' if row['pass'] else 'fail'} {dict(skips[k])} [{time.time() - t0:.0f}s]")
    save("N", out)
    return out


def stack_eval(pn, horizon=60):
    from engine.analytics import simulate_eval
    P = NS.PLANS["rapid_eod_25k"]
    res = [simulate_eval(pn[s:s + horizon], P) for s in range(len(pn))]
    return round(100.0 * sum(r["result"] == "PASS" for r in res) / max(1, len(res)), 1)


# ================================================================================================ A: ATLAS entries
def stop_fill(u, k, timeout, n, add=2):
    """A3/A4: a stop k ticks past the 5m open, live `timeout` minutes, filled at the trigger + `add` ticks; None = not filled /
    avoided. Arrival cost n (the market is n ticks past the open): k <= n would be a market order."""
    from tools import atlas_fills as AF
    B5, B1 = AF._bars()
    d = int(u["dir"])
    k5, o = AF._open5(u)
    trig = o * d + k * TICK                              # dir space
    stop_q = (o + d * TICK) * d - float(u["risk"])       # the stored stop in dir space (entry = open + 1 tick)
    et_ = int(u["entry_t"])
    got = None
    if et_ >= int(B1.t[0]) + 86400:
        j = int(np.searchsorted(B1.t, et_))
        if j < len(B1.t) and int(B1.t[j]) == et_:
            for mm in range(timeout):
                if j + mm >= len(B1.t) or int(B1.t[j + mm]) >= et_ + 60 * timeout:
                    break
                hi = float(B1.h[j + mm]) if d == 1 else -float(B1.l[j + mm])
                lo = float(B1.l[j + mm]) if d == 1 else -float(B1.h[j + mm])
                if lo <= stop_q:
                    got = "both" if hi >= trig else "avoided"
                    break
                if hi >= trig:
                    got = "fill"
                    break
            if got is None:
                return None, "nofill"
    if got is None:                                       # 5m-only spans: the entry 5m bar decides
        hi = float(B5.h[k5]) if d == 1 else -float(B5.l[k5])
        lo = float(B5.l[k5]) if d == 1 else -float(B5.h[k5])
        if hi < trig:
            return None, "nofill"
        got = "both" if lo <= stop_q else "fill"
    if got == "avoided":
        return None, "avoided"
    worse = k + add                                       # ticks worse than the open
    if got == "both":
        return {**u, "pts": round(-float(u["risk"]) - (worse - 1) * TICK - TICK, 4), "w1": round(-float(u["risk"]) - worse * TICK, 4),
                "exit": "STOP"}, "both"
    return AF.priced(u, max(worse, n), n), "fill"


def a_units(kind, n):
    from tools import atlas_edge as AE
    from tools import atlas_fills as AF
    out, note = [], collections.Counter()
    for u in AF.units():
        if kind == "base":
            out.append(AF.priced(u, n, n))
            continue
        if kind in ("A1", "A2"):
            v = AF.limit_fill(u, -8 if kind == "A1" else -16, n, timeout=15)
            note["filled" if v is not None else "unfilled"] += 1
            if v is None:
                note["missed_usd"] += AE.usd250(AF.priced(u, n, n))
            else:
                out.append(v)
            continue
        v, why = stop_fill(u, 12 if kind == "A3" else 20, 5 if kind == "A3" else 10, n)
        note[why] += 1
        if v is None:
            note["skipped_usd"] += AE.usd250(AF.priced(u, n, n))
        else:
            out.append(v)
    return out, {k: (round(v) if isinstance(v, float) else v) for k, v in note.items()}


def cmd_a(n_paths=1000, log=print):
    from tools import atlas_edge as AE
    t0 = time.time()
    res = {}
    base = {}
    for n in AE.JUDGE:
        U, _ = a_units("base", n)
        base[n] = AE.score(AE.to_T(U), n_paths)
    res["base"] = {f"{n}t": base[n] for n in base}
    for kind in ("A1", "A2", "A3", "A4"):
        opt, notes = {}, {}
        for n in AE.JUDGE:
            U, notes[n] = a_units(kind, n)
            opt[n] = AE.score(AE.to_T(U), n_paths)
        ok, why = AE.gate_g(opt, base)
        res[kind] = {"pass": ok, "why": why, "notes": {f"{n}t": notes[n] for n in notes}, **{f"{n}t": opt[n] for n in opt}}
        for n in AE.JUDGE:
            o, b = opt[n], base[n]
            log(f"{kind} {n}t notes {notes[n]} | fixed " + " ".join(f"{sp} ${b['fixed'][sp]['per_month']}->${o['fixed'][sp]['per_month']} PF {b['fixed'][sp]['pf']}->{o['fixed'][sp]['pf']} {o['fixed'][sp]['tpw']}/wk"
                                                         for sp in ("H1", "H2", "2025", "2021-24")) +
                " | B60 " + " ".join(f"{sp} ${b['B60'][sp]['usd_m']}->${o['B60'][sp]['usd_m']} lost {b['B60'][sp]['lost_6m']}->{o['B60'][sp]['lost_6m']}"
                                     for sp in ("H1", "H2", "REF")) + f" [{time.time() - t0:.0f}s]")
        log(f"{kind} {'PASS' if ok else 'fail'}: {'; '.join(why[:5])}")
    save("A", res)
    return res


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("n", "a"))
    ap.add_argument("--n", type=int, default=1000)
    a = ap.parse_args(argv)
    cmd_n() if a.cmd == "n" else cmd_a(a.n)


if __name__ == "__main__":
    main()
