"""A personal futures account vs the MFFU path (research/ownacct/DESIGN.md). PAPER RESEARCH ONLY.
    python -X utf8 research/ownacct/ownacct.py  -> research/ownacct/results.json
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
OUT = os.path.join(HERE, "results.json")
PV, TICK = 2.0, 0.25
RT, RT_HI = 1.24, 1.70
MARGIN = 100.0
CAPS = (5000, 10000, 25000, 50000)
RISKS = (0.005, 0.01, 0.02)
PERIODS = {"2021-11..2025-12": ("2021-11-01", "2025-12-31"), "2025": ("2025-01-01", "2025-12-31"),
           "Jan-Jun 2026": ("2026-01-01", "2026-06-30"), "Jul-Oct 2026": ("2026-07-01", "2026-10-16")}


# ================================================================================================ the trade units (per micro)
def lit_units():
    from tools import stops_targets_time as STT
    return [{"bot": "LIT", "day": u["day"], "t": u["entry_t"], "x": u["exit_t"], "risk": float(u["risk"]) + TICK, "pts": float(u["pts"]),
             "w1": float(u["w1"])} for u in STT.units()]


def atlas_units():
    from tools import atlas as A, second_mix as M
    M.units()
    U = sorted(A.account_units(A.BASE), key=lambda u: u["entry_t"])
    out, busy, per = [], 0, collections.Counter()
    for u in U:                                    # one position, max 2 a day (second_mix.play_day)
        if u["entry_t"] < busy or per[u["day"]] >= 2:
            continue
        busy = u["exit_t"]; per[u["day"]] += 1
        out.append({"bot": "ATLAS", "day": u["day"], "t": u["entry_t"], "x": u["exit_t"], "risk": float(u["risk"]) + TICK,
                    "pts": float(u["pts"]), "w1": float(u["w1"])})
    return out


def blitz_units():
    from tools import scalp_na_lib as N
    _, TT = N.lines(None, lambda F: F["prng_ratio"] >= 0.8)
    out = []
    for tf, T in TT.items():
        for t in T:
            sp_2026 = t["day"] >= "2026-01-01"
            if (tf == 1) != sp_2026:
                continue
            pts = (t["pnl_pm"] + N.COMM) / PV                # per micro, before commission (slippage as the executor booked it)
            out.append({"bot": "BLITZ", "day": t["day"], "t": int(t["entry_t"]), "x": int(t["exit_t"]),
                        "risk": (t["risk_pm"] - N.COMM) / PV, "pts": pts, "w1": (t["mae_pm"] + N.COMM) / PV})
    return out


# ================================================================================================ the account
def simulate(T, cap, f, rt=RT, days=None):
    """Fixed-fractional on the month-start equity; whole micros; margin cap. -> daily equity + stats."""
    T = sorted(T, key=lambda u: u["t"])
    eq = cap
    m_eq, cur_m = cap, None
    daily = collections.OrderedDict()
    taken = skipped = 0
    for d in days:
        daily[d] = None
    by = collections.defaultdict(list)
    for u in T:
        by[u["day"]].append(u)
    out_days = []
    for d in days:
        if d[:7] != cur_m:
            cur_m, m_eq = d[:7], eq
        for u in by.get(d, []):
            per = u["risk"] * PV + rt
            q = int(m_eq * f / per)
            q = min(q, int(max(0.0, eq) / MARGIN))
            if q <= 0:
                skipped += 1
                continue
            taken += 1
            eq += q * (u["pts"] * PV - rt)
        out_days.append((d, eq))
    return out_days, taken, skipped


def stats(path, cap, taken, skipped):
    d = [x[0] for x in path]
    e = np.array([x[1] for x in path])
    if not len(e):
        return {}
    peak = np.maximum.accumulate(np.r_[cap, e])[1:]
    dd = e - peak
    j = int(np.argmin(dd))
    dd_pct = float((dd / peak).min()) * 100
    months = collections.OrderedDict()
    prev = cap
    for day, v in path:
        months[day[:7]] = v
    mret, last = [], cap
    for m, v in months.items():
        mret.append(v - last); last = v
    n_m = len(months)
    yrs = max(1e-9, (dt.date.fromisoformat(d[-1]) - dt.date.fromisoformat(d[0])).days / 365.25)
    final = float(e[-1])
    cagr = ((final / cap) ** (1 / yrs) - 1) * 100 if final > 0 else -100.0
    # longest drawdown in months (peak -> new peak)
    longest, start = 0, None
    pk = cap
    mvals = list(months.values())
    for i, v in enumerate(mvals):
        if v >= pk:
            if start is not None:
                longest = max(longest, i - start)
            pk, start = v, None
        elif start is None:
            start = i - 1 if i > 0 else 0
    if start is not None:
        longest = max(longest, len(mvals) - 1 - start)
    return {"final": round(final), "net": round(final - cap), "cagr_pct": round(cagr, 1), "per_month": round((final - cap) / n_m),
            "max_dd": round(float(dd.min())), "max_dd_pct": round(dd_pct, 1), "worst_month": round(min(mret)),
            "losing_months_pct": round(100 * sum(1 for x in mret if x < 0) / n_m, 1), "longest_dd_months": longest,
            "trades": taken, "skipped": skipped, "months": n_m}


def ruin(T, days, cap, f, n=1000, length=252, seed=7):
    by = collections.defaultdict(list)
    for u in T:
        by[u["day"]].append(u)
    rng = np.random.default_rng(seed)
    hits = 0
    ends = []
    for _ in range(n):
        seq = []
        while len(seq) < length:
            b = int(rng.integers(0, len(days) - 5))
            seq.extend(days[b:b + 5])
        eq, m_eq, low = cap, cap, cap
        for k, d in enumerate(seq[:length]):
            if k % 21 == 0:
                m_eq = eq
            for u in by.get(d, []):
                q = min(int(m_eq * f / (u["risk"] * PV + RT)), int(max(0.0, eq) / MARGIN))
                if q > 0:
                    eq += q * (u["pts"] * PV - RT)
            low = min(low, eq)
        hits += low <= 0.5 * cap
        ends.append(eq - cap)
    return {"ruin_50_pct": round(100 * hits / n, 1), "net_12m_p10": round(float(np.percentile(ends, 10))),
            "net_12m_p50": round(float(np.percentile(ends, 50)))}


def main():
    books = {"LIT": lit_units(), "ATLAS": atlas_units()}
    books["LIT + ATLAS"] = books["LIT"] + books["ATLAS"]
    books["BLITZ (paper)"] = blitz_units()
    sessions = json.load(open(os.path.join(ROOT, "research", "runs", "lit_live.json"), encoding="utf-8"))["days"]
    sessions = [r[0] for r in sessions]
    res = {"made": "2026-11-24", "design": "research/ownacct/DESIGN.md",
           "costs": {"rt_per_micro": RT, "rt_hi": RT_HI, "intraday_margin": MARGIN}, "books": {}}
    for b, T in books.items():
        res["books"][b] = {"trades": len(T)}
        for pn, (a, z) in PERIODS.items():
            ds = [d for d in sessions if a <= d <= z]
            for cap in CAPS:
                for f in RISKS:
                    path, tk, sk = simulate([u for u in T if a <= u["day"] <= z], cap, f, days=ds)
                    st = stats(path, cap, tk, sk)
                    p2, tk2, sk2 = simulate([u for u in T if a <= u["day"] <= z], cap, f, rt=RT_HI, days=ds)
                    st["net_at_1.70_rt"] = round(p2[-1][1] - cap) if p2 else None
                    res["books"][b].setdefault(pn, {})[f"{cap}|{f}"] = st
        # 2022 alone (the bear market) at each capital x risk
        ds22 = [d for d in sessions if "2022-01-01" <= d <= "2022-12-31"]
        for cap in CAPS:
            for f in RISKS:
                path, tk, sk = simulate([u for u in T if "2022" <= u["day"] < "2023"], cap, f, days=ds22)
                res["books"][b].setdefault("2022", {})[f"{cap}|{f}"] = stats(path, cap, tk, sk)
        # ruin
        for pool, (a, z) in (("2021-25 pool", ("2021-11-01", "2025-12-31")), ("2026 pool", ("2026-01-01", "2026-10-16"))):
            ds = [d for d in sessions if a <= d <= z]
            TT = [u for u in T if a <= u["day"] <= z]
            for cap in (10000, 25000):
                for f in RISKS:
                    res["books"][b].setdefault("ruin_12m", {}).setdefault(pool, {})[f"{cap}|{f}"] = ruin(TT, ds, cap, f)
        print(b, "done", flush=True)
    # minimum capital (LIT, 1 micro)
    L = books["LIT"]
    per = np.array([u["risk"] * PV + RT for u in L])
    res["lit_min_capital"] = {f"{int(f * 1000) / 10}%": {"90pct_of_trades": round(float(np.percentile(per, 90)) / f),
                                                          "all_trades": round(float(per.max()) / f),
                                                          "median_trade": round(float(np.median(per)) / f)} for f in RISKS}
    res["lit_stop_usd_per_micro"] = {"median": round(float(np.median(per)), 2), "p90": round(float(np.percentile(per, 90)), 2),
                                     "max": round(float(per.max()), 2)}
    # the MFFU path (research/badcase)
    B = json.load(open(os.path.join(ROOT, "research", "badcase", "results.json"), encoding="utf-8"))["plans"]
    res["mffu"] = {p: {m: {"per_month": round(B[p][m]["slot"]["net_6m"] / 6), "per_month_p10": round(B[p][m]["slot"]["net_p10"] / 6),
                           "fees_per_month": round(B[p][m]["slot"]["fees_6m"] / 6)} for m in ("Y25", "REF", "H1", "H2")} for p in B}
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1, default=float)
    for b in books:
        for pn in list(PERIODS) + ["2022"]:
            for k in ("10000|0.01", "25000|0.01", "25000|0.02", "50000|0.01"):
                s = res["books"][b][pn][k]
                print(f"{b:14s} {pn:17s} {k:12s} net ${s['net']:,} CAGR {s['cagr_pct']}% ${s['per_month']:,}/mo DD ${s['max_dd']:,} "
                      f"({s['max_dd_pct']}%) worst mo ${s['worst_month']:,} losing {s['losing_months_pct']}% longDD {s['longest_dd_months']}mo "
                      f"trades {s['trades']} skip {s['skipped']}")
        print(b, "ruin", json.dumps(res["books"][b]["ruin_12m"]))
    print("LIT min capital", res["lit_min_capital"], res["lit_stop_usd_per_micro"])
    print("MFFU", json.dumps(res["mffu"]))


if __name__ == "__main__":
    main()
