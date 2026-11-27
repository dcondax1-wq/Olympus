"""LIT on MES for the setups MNQ cannot size (research/lit/mes-2026-11-27/DESIGN.md, pre-registered). PAPER RESEARCH ONLY.
    python -X utf8 research/lit/mes-2026-11-27/mes.py   -> results.json
"""
import bisect, collections, json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(ROOT, "research", "lit", "drought-2026-11-27"))
import common as c  # noqa: E402
import variants as dv  # noqa: E402  (metrics, perm_p, risk_of; the drought study's code)
import pandas as pd  # noqa: E402
lit, lf = c.lit, c.lf
SPANS = {"H1": ("2026-01-01", "2026-06-30"), "JulNov": ("2026-07-01", "2026-11-26"), "JulOct14": ("2026-07-01", "2026-10-14"),
         "Drought": ("2026-10-15", "2026-11-26"), "2021-25": ("2021-01-01", "2025-12-31")}
V3_SPANS = {**SPANS, "2021-25": ("2025-04-14", "2025-12-31")}
MES_PV, MES_COMM, ES_TICK_USD, WIDE_MAX = 5.0, 1.90, 1.25, 150.0
_q0 = lit.qty_for
WIDE = set()


def daily_ratio():
    es = pd.read_csv(os.path.join(ROOT, "data", "ES_1d.csv")); nq = pd.read_csv(os.path.join(ROOT, "data", "NQ_1d.csv"))
    f = lambda d: {pd.Timestamp(t, unit="s", tz="UTC").tz_convert("America/New_York").strftime("%Y-%m-%d"): x for t, x in zip(d["time"], d["close"])}
    e, n = f(es), f(nq)
    return sorted(set(e) & set(n)), e, n


RD, RE, RN = daily_ratio()


def ratio(day, scale=1.0):
    i = bisect.bisect_left(RD, day) - 1                    # prior-day closes
    r = RE[RD[i]] / RN[RD[i]] if i >= 0 else 0.30           # before ES data (2025-04-14): flat 0.30
    return r * scale


def risk_usd(risk_nq):
    return 800.0 if risk_nq <= 20.0 else 800.0 * 20.0 / risk_nq


def q_es(risk_nq, r, floor):
    q = int(risk_usd(risk_nq) / (risk_nq * r * MES_PV))
    return max(q, 1) if floor else q


def run_nq_wide(P, S, floor, scale=1.0):
    """NQ-path run with wide setups (80 < risk <= 150) allowed; those not sizable on MES (V1: 0 MES) are dropped before the run."""
    M, C = lf.market(P["ref"], P["extra_boxes"])
    keep = []
    WIDE.clear()
    for z in C:
        rk = dv.risk_of(z, P)
        if rk > 80.0:
            if rk > WIDE_MAX or q_es(rk, ratio(z["day"], scale), floor) < 1:
                continue
            WIDE.add((z["day"], z["i"]))
        keep.append(z)
    qq = lambda risk_pts, *a, **k: 1 if risk_pts > 80.0 else _q0(risk_pts, *a, **k)    # wide: 1 NQ unit, converted below
    lit.qty_for = qq
    try:
        return lit.run_x(M, keep, {**P, "max_stop": WIDE_MAX}, S, B1=lf.bars(M, "1m"), B5=lf.bars(M, "5m"))
    finally:
        lit.qty_for = _q0


def to_mes(t, floor, scale=1.0, extra_ticks=0.0):
    """A wide NQ trade (q = 1 unit) -> the same trade on MES."""
    r = ratio(t["day"], scale)
    pts = (t["pnl"] + lit.COMM) / lit.PV                    # NQ points per contract (the path, slippage in)
    low_pts = (t["low"] + lit.COMM) / lit.PV if t["low"] < 0 else 0.0
    q = q_es(t["risk_pts"], r, floor)
    n_slip = (1 if t["exit"] == "TARGET" else 2) + extra_ticks * 2
    extra = n_slip * (ES_TICK_USD - 0.25 * r * MES_PV)      # ES tick slippage instead of the NQ tick already in the path
    per = pts * r * MES_PV - MES_COMM - extra
    low = min(0.0, low_pts * r * MES_PV - MES_COMM - extra, per)
    return {**t, "pnl": round(q * per, 2), "low": round(q * low, 2), "qty": q, "risk_usd": round(q * t["risk_pts"] * r * MES_PV, 2), "mes": True}


def variant_nq(name, P, S, floor, scale=1.0, extra=0.0):
    T = run_nq_wide(P, S, floor, scale)
    return [to_mes(t, floor, scale, extra) if (t["day"], t["i"]) in WIDE else t for t in T]


def metrics(T, ss):
    m = dv.metrics(T, ss)
    w = [t for t in T if t.get("mes")]
    m["wide"], m["wide_net"] = len(w), round(sum(t["pnl"] for t in w))
    return m


def run_es(P, S, nq_wide_days, cap_by_ratio=False):
    """V3: LIT's own detection on ES 5m bars as MES (engine/lit_markets.use, scaled stop range), only setups whose NQ-equivalent stop
    (stop ES / ratio) is 80-150 pts, only on days NQ had a wide setup. 5m execution (ES has no 1m). Size = V1's rule, no floor."""
    from engine import lit_markets as lm
    esb = lit.load("ES", "5m")
    Me = lit.Market(bars=esb)
    Mn, _ = lf.market(P["ref"], P["extra_boxes"])
    # k = median ES 5m ATR(14) / NQ's on the same bars (a volatility ratio, lm.params)
    nq_atr = dict(zip(Mn.t.tolist(), Mn.atr)); ks = [a / nq_atr[t] for t, a in zip(Me.t.tolist(), Me.atr) if t in nq_atr and nq_atr[t] > 0 and a == a]
    k = float(np.median(ks))
    spec = lm.Spec("ES", "MES", "Micro E-mini S&P 500", "CME", 0.25, 5.0, MES_COMM, "MFFU $1.90", "VIX", "HMUZ")
    with lm.use(spec, k):
        pe = {**P, **lm.params(spec, k), "tf": "5m", "max_stop": 150.0 * (0.27 if cap_by_ratio else k)}
        Ce = lit.candidates(Me, ref=P["ref"])
        keep, wide = [], {}
        for z in Ce:
            if z["day"] not in nq_wide_days:
                continue
            rk = dv.risk_of(z, pe)
            r = ratio(z["day"])
            nq_eq = rk / r
            if not (80.0 < nq_eq <= WIDE_MAX) or rk < pe["min_stop"]:
                continue
            if q_es(nq_eq, r, False) < 1:
                continue
            keep.append(z)
            wide[(z["day"], z["i"])] = (nq_eq, r)
        lit.qty_for = lambda risk_pts, *a, **kw: 1
        try:
            T = lit.run_x(Me, keep, pe, S, B1=None, B5=lit.bars_5m(Me))
        finally:
            lit.qty_for = _q0
        out = []
        for t in T:
            nq_eq, r = wide[(t["day"], t["i"])]
            pts = (t["pnl"] + MES_COMM) / MES_PV
            low_pts = (t["low"] + MES_COMM) / MES_PV if t["low"] < 0 else 0.0
            q = q_es(nq_eq, r, False)
            per = pts * MES_PV - MES_COMM
            low = min(0.0, low_pts * MES_PV - MES_COMM, per)
            out.append({**t, "pnl": round(q * per, 2), "low": round(q * low, 2), "qty": q, "mes": True, "risk_nq_eq": round(nq_eq, 1)})
    return out, k


def combine(live, es):
    """One position, one trade a day: per day the earlier entry of the live NQ trade and the ES trade."""
    byday = {}
    for t in sorted(live + es, key=lambda t: t["entry_t"]):
        byday.setdefault(t["day"], t)
    keep = {id(t) for t in byday.values()}
    return [t for t in sorted(live + es, key=lambda t: t["entry_t"]) if id(t) in keep]


def main_v3():
    P = {**lit.DEFAULTS, **c.live_P()}
    S = c.sessions()
    T = json.load(open(os.path.join(HERE, "trades_nq.json")))
    live, v2 = T["live"], T["V2_mes_floor1"]
    wide_days = {t["day"] for t in v2 if t.get("mes")}
    # days where the NQ wide setup is the first qualifying one are in v2; also any day with a wide qualifying candidate on its own:
    es, k = run_es(P, S, wide_days)
    comb = combine(live, es)
    es_b, _ = run_es(P, S, wide_days, cap_by_ratio=True)         # sensitivity V3b: stop cap by the price ratio (150 x 0.27 ES pts)
    comb_b = combine(live, es_b)
    res = {"k": round(k, 4), "es_trades": len(es), "es_net": round(sum(t["pnl"] for t in es)), "wide_days": len(wide_days)}
    res["spans"] = {}
    base = {}
    for sp, (a, b) in V3_SPANS.items():
        ss = [d for d in S if a <= d <= b]
        res["spans"][sp] = {"live": metrics([t for t in live if a <= t["day"] <= b], ss), "V3_es_detect": metrics([t for t in comb if a <= t["day"] <= b], ss),
                                  "V3b_cap_by_ratio": metrics([t for t in comb_b if a <= t["day"] <= b], ss)}
    json.dump({"v3": res}, open(os.path.join(HERE, "results_v3.json"), "w"), indent=1, default=float)
    json.dump({"es": es, "comb": comb}, open(os.path.join(HERE, "trades_v3.json"), "w"), default=float)
    print("k", k, "ES wide trades", len(es), "net", res["es_net"], "wide days", len(wide_days))
    for sp, d in res["spans"].items():
        for nm, m in d.items():
            print(" ", sp, nm, {x: m[x] for x in ("tpw", "pf", "net", "per_month", "dd", "pass_rate", "wide", "wide_net")})


def main():
    P = {**lit.DEFAULTS, **c.live_P()}
    S = c.sessions()
    M, C = lf.market(P["ref"], P["extra_boxes"])
    live = lit.run_x(M, C, P, S, B1=lf.bars(M, "1m"), B5=lf.bars(M, "5m"))
    R = {"live": live}
    R["V1_mes_same_risk"] = variant_nq("V1", P, S, False)
    R["V2_mes_floor1"] = variant_nq("V2", P, S, True)
    # sensitivity (V2 and V1): ratio +-10%, +1 ES tick each way
    sens = {}
    for nm, fl in (("V1", False), ("V2", True)):
        for lab, sc, ex in (("ratio x0.9", 0.9, 0.0), ("ratio x1.1", 1.1, 0.0), ("+1 ES tick", 1.0, 1.0)):
            sens[f"{nm} {lab}"] = variant_nq(nm, P, S, fl, sc, ex)
    out = {"design": "DESIGN.md (committed before this run)", "variants": {}, "sensitivity": {}}
    for nm, T in list(R.items()):
        out["variants"][nm] = {sp: metrics([t for t in T if a <= t["day"] <= b], [d for d in S if a <= d <= b]) for sp, (a, b) in SPANS.items()}
    for nm, T in sens.items():
        out["sensitivity"][nm] = {sp: metrics([t for t in T if a <= t["day"] <= b], [d for d in S if a <= d <= b]) for sp, (a, b) in SPANS.items()}
    json.dump(out, open(os.path.join(HERE, "results_nq.json"), "w"), indent=1)
    json.dump({k: v for k, v in R.items()}, open(os.path.join(HERE, "trades_nq.json"), "w"), default=float)
    for nm in out["variants"]:
        print(nm)
        for sp in SPANS:
            m = out["variants"][nm][sp]
            print("  ", sp, {k: m[k] for k in ("tpw", "pf", "net", "per_month", "dd", "pass_rate", "wide", "wide_net")})


if __name__ == "__main__":
    main_v3() if "v3" in sys.argv[1:] else main()
