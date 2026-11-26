"""BLITZ v2 (research/blitzv2/DESIGN.md). PAPER RESEARCH ONLY.
    python -X utf8 research/blitzv2/blitzv2.py   -> research/blitzv2/results.json
"""
from __future__ import annotations

import collections
import copy
import datetime as dt
import json
import os
import sys
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "research", "moretrades"))
os.chdir(ROOT)
from tools import blitz25k_lib as L, scalp_na_lib as N  # noqa: E402
import moretrades as MT  # noqa: E402

TICK, PV, COMM = 0.25, 2.0, 1.90
USD = 150.0
SPANS = {"2026 H1": (1, "H1"), "2026 Jul-Nov20": (1, "H2"), "2021-25": (5, "R")}
YEARS = ("2022", "2023", "2024", "2025")

V = {
    "V0 today": {},
    "V1 noise-area exit (band/VWAP, no clock, no trail)": {"exit": "band", "hold": 0, "trail": None},
    "V2 no time exit (trail + stop only)": {"hold": 0},
    "V3 cost gate (stop >= 0.25% of price)": {"gate": 0.25},
    "V4 + opening-drive checks 09:45-10:30": {"wins": ("od", "rth")},
    "V5 limit back at the band (10 min)": {"lim": "band"},
    "V6 first break of the day only, V1 exit": {"exit": "band", "hold": 0, "trail": None, "first_only": True},
    "V7 V1 + V3": {"exit": "band", "hold": 0, "trail": None, "gate": 0.25},
    "V8 V1 + V3 + V4": {"exit": "band", "hold": 0, "trail": None, "gate": 0.25, "wins": ("od", "rth")},
}
BASEV = {"hold": 30, "trail": 1.5, "tstart": 1.0, "maxday": 6, "day_stop": 3.0, "last_mod": 930, "exit": None, "gate": None,
         "wins": ("rth",), "lim": None, "lim_w": 10, "first_only": False}


def cands(B, v):
    G = L.base(B, "prng>=0.8", tuple(v["wins"]))
    I, D = G["sig"].copy(), G["dir"].copy()
    stop = B["c"][I] - D * 1.5 * B["atr5"][I]
    keep = np.ones(len(I), bool)
    if v["gate"]:
        keep &= 1.5 * B["atr5"][I] / B["c"][I] * 100 >= v["gate"]
    if v["first_only"]:
        seen = set()
        for q in range(len(I)):
            dd = int(B["day"][I[q]])
            if dd in seen:
                keep[q] = False
            elif keep[q]:
                seen.add(dd)
    F0 = L._signals_win(B, "rth")
    lim = np.full(len(I), np.nan)
    if v["lim"] == "band":
        lim = np.where(D > 0, F0["_up"][I], F0["_lo"][I])
    return I[keep], D[keep], stop[keep], lim[keep], F0


def is_check(B, i):
    m = int(B["mod"][i]) + B["tf"]          # the bar's close minute
    return m >= 600 and (m - 570) % 30 == 0


def sim(B, v, placebo=None):
    v = {**BASEV, **v}
    I, Dd, ST, LIM, F0 = cands(B, v)
    if placebo is not None:
        rng = np.random.default_rng(placebo)
        nd = rng.choice([-1.0, 1.0], len(I))
        ref = B["c"][I]
        ST = np.where(nd != Dd, 2 * ref - ST, ST)
        LIM = np.where(nd != Dd, 2 * ref - LIM, LIM)
        Dd = nd
    o, h, l, c, mod, day, flat, t = B["o"], B["h"], B["l"], B["c"], B["mod"], B["day"], B["flat"], B["t"]
    up, lo, vw = F0["_up"], F0["_lo"], B["vwap"]
    hold = int(round(v["hold"] / B["tf"])) if v["hold"] else 0
    lw = max(1, int(round(v["lim_w"] / B["tf"])))
    out, busy, cur, dn, dR = [], -1, -1, 0, 0.0
    for q in range(len(I)):
        s = int(I[q]); D = float(Dd[q])
        if day[s] != cur:
            cur, dn, dR = day[s], 0, 0.0
        if s < busy or dn >= v["maxday"] or dR <= -v["day_stop"]:
            continue
        fe = int(flat[s])
        if s + 1 > fe or mod[s] > v["last_mod"]:
            continue
        j = s + 1
        st = float(ST[q])
        lm = LIM[q]
        limfill = False
        if lm == lm:
            jf = -1
            for jj in range(s + 1, min(s + 1 + lw, fe + 1)):
                if (D > 0 and o[jj] <= lm) or (D < 0 and o[jj] >= lm):
                    jf, fill = jj, float(o[jj]); break
                if (D > 0 and l[jj] <= lm - TICK) or (D < 0 and h[jj] >= lm + TICK):
                    jf, fill = jj, float(lm); break
            if jf < 0:
                busy = min(s + lw, fe)
                continue
            j, limfill = jf, True
        else:
            fill = float(o[j]) + D * TICK
        risk = D * (fill - st)
        if risk < TICK:
            busy = j
            continue
        stp, ext, mae, xp, xk, kind = st, fill, 0.0, None, j, None
        for i in range(j, fe + 1):
            first = i == j
            if not first and ((D > 0 and o[i] <= stp) or (D < 0 and o[i] >= stp)):
                xp, xk, kind = o[i] - D * TICK, i, "stop"; mae = max(mae, D * (fill - xp)); break
            if (l[i] <= stp) if D > 0 else (h[i] >= stp):
                xp, xk, kind = stp - D * TICK, i, "stop"; mae = max(mae, D * (fill - xp)); break
            mae = max(mae, (fill - l[i]) if D > 0 else (h[i] - fill))
            if i >= fe:
                xp, xk, kind = c[i] - D * TICK, i, "flat"; break
            if hold > 0 and i >= j + hold:
                xp, xk, kind = c[i] - D * TICK, i, "time"; break
            if v["exit"] == "band" and is_check(B, i) and not first:
                lvl = max(up[i], vw[i]) if D > 0 else min(lo[i], vw[i])
                if lvl == lvl and D * (c[i] - lvl) < 0:
                    xp, xk, kind = c[i] - D * TICK, i, "band"; break
            if first and limfill:
                ext = max(ext, c[i]) if D > 0 else min(ext, c[i])
            else:
                ext = max(ext, h[i]) if D > 0 else min(ext, l[i])
            mfe = D * (ext - fill)
            if v["trail"] and mfe >= v["tstart"] * risk:
                nt = ext - D * v["trail"] * risk
                if D * (nt - stp) > 0:
                    stp = nt
        pts = D * (xp - fill)
        out.append({"day": str(B["dates"][day[j]]), "sig_t": int(t[s]), "entry_t": int(t[j]), "exit_t": int(t[xk]) + 60 * B["tf"],
                    "dir": int(D), "pts": pts, "risk_pts": risk, "exit_kind": kind, "pnl_pm": pts * PV - COMM,
                    "risk_pm": (risk + TICK) * PV + COMM, "mae_pm": -mae * PV - COMM, "mod": int(mod[s]) + B["tf"]})
        busy = xk
        dn += 1
        dR += (pts * PV - COMM) / ((risk + TICK) * PV + COMM)
    return out


def usd(T):
    """$150 a trade (scalp_na_lib.stats sizing): -> trades with pnl / low $ (MT scoring format)."""
    out = []
    for t in T:
        q = max(1, min(20, int(USD / t["risk_pm"])))
        out.append({**t, "pnl": q * t["pnl_pm"], "low": min(0.0, q * t["mae_pm"]), "q": q})
    return out


def walk(T5, B5, T0):
    """6-month windows every 3 months on the 5m series: variant $ > today $."""
    wins = tot = 0
    m = dt.date(2021, 11, 1)
    while True:
        z = (m + dt.timedelta(days=183)).replace(day=1) - dt.timedelta(days=1)
        if z > dt.date(2026, 11, 20):
            break
        a, zz = m.isoformat(), z.isoformat()
        sv = sum(t["pnl"] for t in T5 if a <= t["day"] <= zz)
        sb = sum(t["pnl"] for t in T0 if a <= t["day"] <= zz)
        tot += 1; wins += sv > sb
        m = (m + dt.timedelta(days=95)).replace(day=1)
    return f"{wins}/{tot}"


# ------------------------------------------------------------------------------------------------ LIT + ATLAS for the combined path
def lit_trades():
    from engine import lit
    from tools import lit_final as F
    M, C = F.market(MT.LIVE["ref"], MT.LIVE.get("extra_boxes") or [])
    S = sorted(set(F.SESS) | {d for d, _, _ in M.days if d > F.SESS[-1] and dt.date.fromisoformat(d).weekday() < 5})
    P = {**lit.DEFAULTS, **MT.LIVE}
    T = [t for t in lit.run_x(M, C, P, S, B1=F.bars(M, "1m"), B5=F.bars(M, "5m")) if t.get("qty")]
    return [{"day": t["day"], "entry_t": int(t["entry_t"]), "exit_t": int(t["exit_t"]), "pnl": float(t["pnl"]), "low": float(t["low"]), "src": "LIT"} for t in T], S


def atlas_trades():
    import pandas as pd
    from engine import second
    base = second.load_cfg()
    c = copy.deepcopy(base)
    c["strategies"] = {k: c["strategies"][k] for k in MT.KEYS}
    d5 = pd.read_csv("data/NQ_5m.csv").drop_duplicates("time").sort_values("time").reset_index(drop=True)
    d1 = pd.read_csv("data/NQ_1m.csv").drop_duplicates("time").sort_values("time").reset_index(drop=True)
    ET = dt.timezone(dt.timedelta(hours=-5))
    T = {}
    m = dt.date(2021, 11, 1)
    while m <= dt.date(2026, 11, 1):
        nxt = (m.replace(day=28) + dt.timedelta(days=4)).replace(day=1)
        end = min(int(dt.datetime(nxt.year, nxt.month, 1, 17, 0, tzinfo=ET).timestamp()) - 86400, int(d5.time.max()) + 300)
        x5 = d5[(d5.time < end) & (d5.time >= end - 86400 * 110)].reset_index(drop=True)
        x1 = d1[(d1.time < end) & (d1.time >= end - 86400 * 70)].reset_index(drop=True) if m >= dt.date(2026, 1, 1) else None
        if len(x5) > 1000:
            r = second.run(x5, one_min=x1 if x1 is not None and len(x1) else None, now=end, cfg=c, lit=[])
            for k in MT.KEYS:
                for t in r["strategies"][k]["trades"]:
                    if t.get("exit_kind") and t["day"][:7] == m.isoformat()[:7]:
                        u = float(t.get("usd") or 0)
                        T[(k, t["entry_t"])] = {"day": t["day"], "entry_t": int(t["entry_t"]), "exit_t": int(t["exit_t"]), "pnl": u,
                                                "low": -abs(float(t.get("risk_usd") or 0)) if t.get("exit_kind") == "STOP" else min(0.0, u), "src": "ATLAS"}
        m = nxt
    return list(T.values())


def one_position(T):
    out, busy = [], 0
    for t in sorted(T, key=lambda t: t["entry_t"]):
        if t["entry_t"] >= busy:
            out.append(t); busy = t["exit_t"]
    return out


def corr(A, Bt, S):
    a = collections.defaultdict(float); b = collections.defaultdict(float)
    for t in A:
        a[t["day"]] += t["pnl"]
    for t in Bt:
        b[t["day"]] += t["pnl"]
    x = np.array([a.get(d, 0) for d in S]); y = np.array([b.get(d, 0) for d in S])
    return round(float(np.corrcoef(x, y)[0, 1]), 3) if x.std() and y.std() else None


def main():
    t0 = time.time()
    say = lambda s: print(f"[{time.time() - t0:5.0f}s] {s}", flush=True)  # noqa: E731
    B1, B5 = N.bars(1), N.bars(5)
    # parity vs today's engine
    ref = L.trades()
    mine = {1: sim(B1, {}), 5: sim(B5, {})}
    par = {tf: {"n_lib": len(ref[tf]), "n_port": len(mine[tf]),
                "same_entries": len({t["entry_t"] for t in ref[tf]} & {t["entry_t"] for t in mine[tf]}),
                "net_pm_lib": round(sum(t["pnl_pm"] for t in ref[tf]), 1), "net_pm_port": round(sum(t["pnl_pm"] for t in mine[tf]), 1)} for tf in (1, 5)}
    say(f"parity {par}")
    res = {"made": "2026-11-26", "design": "research/blitzv2/DESIGN.md", "parity": par, "variants": {}}
    S1 = {sp: N.sessions(B1, k) for sp, (tf, k) in SPANS.items() if tf == 1}
    SR = N.sessions(B5, "R")
    S5all = [d for d in B5["dates"] if d >= "2021-11-01" and dt.date.fromisoformat(d).weekday() < 5]
    base5 = None
    TV = {}
    for nm, v in V.items():
        T1, T5 = usd(sim(B1, v)), usd(sim(B5, v))
        TV[nm] = (T1, T5)
        base5 = base5 or T5
        o = {"cfg": v, "spans": {}, "years": {}}
        for sp, (tf, k) in SPANS.items():
            S = N.sessions(B1 if tf == 1 else B5, k)
            st = N.stats(sim_cache(nm, tf, T1, T5), S, USD, 20)
            ev = MT.span_stats(T1 if tf == 1 else T5, S, S[0], S[-1])
            st["rapid25k"] = ev["evals"]["Rapid25K"]; st["b25k"] = ev["evals"]["25K"]
            st["exits"] = dict(collections.Counter(t["exit_kind"] for t in (T1 if tf == 1 else T5) if S[0] <= t["day"] <= S[-1]))
            o["spans"][sp] = st
        for y in YEARS:
            S = [d for d in SR if d.startswith(y)]
            o["years"][y] = N.stats(T5, S, USD, 20)["per_month"]
        o["walk_forward"] = walk(T5, B5, base5) if nm != "V0 today" else "-"
        # placebo on 2021-25 (5m): random sides, same bars / stop distances
        if nm in ("V0 today",) or True:
            real = N.stats(T5, SR, USD, 20)["avg_r"]
            pl = [N.stats(usd(sim(B5, v, placebo=s)), SR, USD, 20)["avg_r"] for s in range(20)]
            o["placebo_2125"] = {"avg_r": real, "beat": sum(1 for x in pl if x >= real), "of": 20, "p": round((1 + sum(1 for x in pl if x >= real)) / 21, 3)}
        res["variants"][nm] = o
        s = o["spans"]
        say(f"{nm:52s} " + " | ".join(f"{k}: {s[k]['tpw']}/wk PF {s[k]['pf']} ${s[k]['per_month']:,}/mo R25 {s[k]['rapid25k']['pass']}/{s[k]['rapid25k']['fail']}" for k in SPANS)
            + f" | yrs {o['years']} | WF {o['walk_forward']} | placebo p {o['placebo_2125']['p']}")
        json.dump(res, open(os.path.join(HERE, "results.json"), "w"), indent=1, default=float)
    # ---- combined path (one 50K, one position): LIT + ATLAS vs + BLITZ (today / best v2 by 2021-25 $)
    say("LIT + ATLAS trades ...")
    LT, S = lit_trades()
    AT = atlas_trades()
    say(f"LIT {len(LT)} ATLAS {len(AT)}")
    best = max((k for k in V if k != "V0 today"), key=lambda k: res["variants"][k]["spans"]["2021-25"]["per_month"])
    comb = {}
    for nm, extra in (("LIT + ATLAS (no BLITZ)", None), ("LIT + ATLAS + BLITZ today", "V0 today"), (f"LIT + ATLAS + BLITZ {best[:2]}", best)):
        T = list(LT) + list(AT)
        if extra:
            T1, T5 = TV[extra]
            T += [{"day": t["day"], "entry_t": t["entry_t"], "exit_t": t["exit_t"], "pnl": t["pnl"], "low": t["low"], "src": "BLITZ"}
                  for t in (T1 + [x for x in T5 if x["day"] < "2026-01-01"])]
        T = one_position(T)
        sp = {k: MT.span_stats(T, S, a, z) for k, (a, z) in (("2021-25", ("2021-11-01", "2025-12-31")), ("2026 H1", ("2026-01-01", "2026-06-30")),
                                                                ("2026 Jul-Nov20", ("2026-07-01", "2026-11-20")))}
        comb[nm] = {k: {"tpw": x["tpw"], "pf": x["pf"], "per_month": x["per_month"], "max_dd": x["max_dd"], "50K": x["evals"]["50K"],
                        "Rapid25K": x["evals"]["Rapid25K"]} for k, x in sp.items()}
        comb[nm]["by_src"] = dict(collections.Counter(t["src"] for t in T))
        say(f"{nm:34s} " + " | ".join(f"{k}: {x['tpw']}/wk ${x['per_month']:,}/mo 50K {x['50K']['pass']}/{x['50K']['fail']} med {x['50K']['med']}" for k, x in comb[nm].items() if k != "by_src"))
    res["combined"] = comb
    T1, T5 = TV["V0 today"]
    BL = T1 + [x for x in T5 if x["day"] < "2026-01-01"]
    S25 = [d for d in S if d <= "2025-12-31"]; S26 = [d for d in S if d >= "2026-01-01"]
    res["correlation"] = {"BLITZ vs LIT": {"2021-25": corr(BL, LT, S25), "2026": corr(BL, LT, S26)},
                          "BLITZ vs ATLAS": {"2021-25": corr(BL, AT, S25), "2026": corr(BL, AT, S26)},
                          "LIT vs ATLAS": {"2021-25": corr(LT, AT, S25), "2026": corr(LT, AT, S26)}}
    say(f"correlation {res['correlation']}")
    json.dump(res, open(os.path.join(HERE, "results.json"), "w"), indent=1, default=float)


def sim_cache(nm, tf, T1, T5):
    return T1 if tf == 1 else T5


if __name__ == "__main__":
    main()
