"""Is there a trustworthy "market is 2026-like" switch? (research/regime2026/DESIGN.md, f38dcf45). PAPER RESEARCH ONLY.
    python -X utf8 research/regime2026/regime.py -> research/regime2026/results.json (+ streams.json.gz)
"""
from __future__ import annotations

import datetime as dt
import gzip
import json
import os
import sys
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
for p in (ROOT, os.path.join(ROOT, "research", "litasia"), os.path.join(ROOT, "research", "atlas2")):
    sys.path.insert(0, p)
OUT = os.path.join(HERE, "results.json")
STREAMS = os.path.join(HERE, "streams.json.gz")
ET = ZoneInfo("America/New_York")
PICK = (("2021-11-01", "2023-12-31"), ("2026-01-01", "2026-06-30"))
CHECK = (("2024-01-01", "2025-12-31"), ("2026-07-01", "2026-10-16"))
SPANS = {"2021-25": ("2021-11-01", "2025-12-31"), "2026 H1": ("2026-01-01", "2026-06-30"), "2026 Jul-Oct": ("2026-07-01", "2026-10-16"),
         **{str(y): (f"{y}-01-01", f"{y}-12-31") for y in (2022, 2023, 2024, 2025)}}
RULES = ("S1_RV", "S2_VIX", "S3_VIX20", "S4_TERM", "S5_TREND", "S6_EXPAND", "S7_OWN", "S8_VOTE")


# ======================================================================================== streams
def streams():
    if os.path.exists(STREAMS):
        return json.load(gzip.open(STREAMS, "rt", encoding="utf-8"))
    at = json.load(gzip.open(os.path.join(ROOT, "research", "atlas2", "trades.json.gz"), "rt", encoding="utf-8"))["V0"]
    A = [{"day": t["day"], "entry_t": int(t["entry_t"]), "exit_t": int(t["exit_t"]), "R": float(t["R_c"])} for t in at]
    import asia as AS
    S2 = [[[1080, 120], [120, 1080]], 1]
    T = AS.M.run(AS.M.P_of("full", 2, None, 1.0, {"per_session": S2, "second": {},
                                                    "kz": [[1080, 1440, {"max_rr": 3.0}], [0, 120, {"max_rr": 3.0}]]}))
    T2 = AS.adj_T(T, 2)
    X = [{"day": t["day"], "entry_t": int(t["entry_t"]), "exit_t": int(t["exit_t"]), "R": float(t["pnl"]) / float(t["risk_usd"])}
         for t in T2 if AS.is_asia(t["entry_t"]) and t.get("risk_usd")]
    out = {"ATLAS": sorted(A, key=lambda t: t["entry_t"]), "ASIA": sorted(X, key=lambda t: t["entry_t"])}
    json.dump(out, gzip.open(STREAMS, "wt", encoding="utf-8"))
    return out


# ======================================================================================== signals
def daily():
    nq = pd.read_csv(os.path.join(ROOT, "data", "NQ_1d.csv"))
    nq["day"] = [(dt.datetime.fromtimestamp(int(t), ET) + dt.timedelta(hours=6)).date().isoformat() for t in nq.time]
    nq = nq.drop_duplicates("day", keep="last").set_index("day").sort_index()
    rng = (nq.high - nq.low) / nq.close
    f = pd.DataFrame(index=nq.index)
    f["rv20"] = rng.rolling(20).mean()
    dC = nq.close.diff().abs()
    f["er20"] = (nq.close - nq.close.shift(20)).abs() / dC.rolling(20).sum()
    f["exp"] = rng.rolling(5).mean() / rng.rolling(60).mean()
    vx = pd.read_csv(os.path.join(ROOT, "data", "VIX_1d.csv")).set_index("date").close
    v3 = pd.read_csv(os.path.join(ROOT, "data", "CBOE_vol_1d.csv")).set_index("date").vix3m
    # cash dates -> the last cash close BEFORE the session's day (the session d starts 18:00 on d-1, after the d-1 cash close)
    cash = pd.DataFrame({"vix": vx, "v3": v3}).sort_index()
    cash["term"] = cash.vix / cash.v3
    days = list(f.index)
    idx = np.searchsorted(np.array(cash.index), np.array(days), side="left") - 1
    for c in ("vix", "term"):
        f[c] = [cash[c].iloc[i] if i >= 0 else np.nan for i in idx]
    return f


def rules(f, lag=1):
    """ON / OFF per session day; market features of day d-lag (lag 1 = the previous session's close; VIX already d-1 cash)."""
    g = f.copy()
    sh = lambda s: s.shift(lag)                                             # noqa: E731
    med = lambda s: s.rolling(252, min_periods=120).median()               # noqa: E731
    vl = lag - 1                                                            # VIX / term are already the previous cash close
    vix, term = g.vix.shift(vl), g.term.shift(vl)
    R = pd.DataFrame(index=g.index)
    R["S1_RV"] = sh(g.rv20) > sh(med(g.rv20))
    R["S2_VIX"] = vix > med(g.vix).shift(vl)
    R["S3_VIX20"] = vix >= 20
    R["S4_TERM"] = term > med(g.term).shift(vl)
    R["S5_TREND"] = sh(g.er20) > sh(med(g.er20))
    R["S6_EXPAND"] = sh(g.exp) > 1
    R["S8_VOTE"] = R[["S1_RV", "S2_VIX", "S4_TERM", "S5_TREND", "S6_EXPAND"]].sum(axis=1) >= 3
    return R


def own(T, n=40):
    ex = sorted(T, key=lambda t: t["exit_t"])
    xs = np.array([t["exit_t"] for t in ex]); rs = np.array([t["R"] for t in ex])
    on = {}
    for t in T:
        k = int(np.searchsorted(xs, t["entry_t"], side="right"))
        on[t["entry_t"]] = bool(k < n or rs[k - n:k].mean() > 0)
    return on


def gate(T, R, rule):
    if rule == "S7_OWN":
        o = own(T)
        return [t for t in T if o[t["entry_t"]]]
    s = R[rule]
    return [t for t in T if bool(s.get(t["day"], False))]


# ======================================================================================== scoring
def money(T, a, z):
    x = [t["R"] * 250.0 for t in T if a <= t["day"] <= z]
    return round(float(sum(x))), len(x)


def table(S, R, f):
    out = {}
    for nm, T in S.items():
        base = {sp: money(T, a, z) for sp, (a, z) in SPANS.items()}
        out[nm] = {"ungated": {sp: {"net": v[0], "n": v[1]} for sp, v in base.items()}, "rules": {}}
        for r in RULES:
            G = gate(T, R, r)
            row = {}
            for sp, (a, z) in SPANS.items():
                g, n = money(G, a, z)
                offs = [t["R"] for t in T if a <= t["day"] <= z and t not in G]
                ons = [t["R"] for t in G if a <= t["day"] <= z]
                row[sp] = {"net": g, "n": n, "vs_ungated": g - base[sp][0], "mean_r_on": round(float(np.mean(ons)), 3) if ons else None,
                           "mean_r_off": round(float(np.mean(offs)), 3) if offs else None}
            if r != "S7_OWN":
                dd = [d for d in R.index if "2021-11-01" <= d <= "2026-10-16"]
                row["on_share"] = {sp: round(float(R.loc[[d for d in dd if a <= d <= z], r].mean()), 3) for sp, (a, z) in SPANS.items()}
            out[nm]["rules"][r] = row
    return out


def by_month(S, R, rule):
    out = {}
    for nm, T in S.items():
        G = set(t["entry_t"] for t in gate(T, R, rule))
        m = {}
        for t in T:
            if t["day"] >= "2026-01-01":
                k = t["day"][:7]
                a = m.setdefault(k, [0.0, 0.0])
                a[0] += t["R"] * 250; a[1] += t["R"] * 250 if t["entry_t"] in G else 0.0
        out[nm] = {k: [round(v[0]), round(v[1])] for k, v in sorted(m.items())}
    return out




def span_vs(S, R, rule, a, z):
    """sum over streams of (gated - ungated) in [a, z]; and each stream's kept share of its ungated money there."""
    tot, kept = 0, {}
    for nm, T in S.items():
        G = gate(T, R, rule)
        g, _ = money(G, a, z); b, _ = money(T, a, z)
        tot += g - b
        kept[nm] = round(g / b, 3) if b > 0 else None
    return tot, kept


def main():
    S = streams()
    f = daily()
    R1, R5 = rules(f, 1), rules(f, 5)
    res = {"made": "2026-11-26", "design": "research/regime2026/DESIGN.md (f38dcf45)",
           "streams": {k: len(v) for k, v in S.items()}, "lag1": table(S, R1, f), "lag5": table(S, R5, f), "pick": {}, "check": {}}
    for r in RULES:
        d1, k1 = span_vs(S, R1, r, *PICK[0])
        d2, k2 = span_vs(S, R1, r, *PICK[1])
        e1, _ = span_vs(S, R1, r, *CHECK[0])
        e2, k4 = span_vs(S, R1, r, *CHECK[1])
        per = {nm: {"pick_old": span_vs({nm: S[nm]}, R1, r, *PICK[0])[0], "check_old": span_vs({nm: S[nm]}, R1, r, *CHECK[0])[0],
                    "check_2026": span_vs({nm: S[nm]}, R1, r, *CHECK[1])[0]} for nm in S}
        res["pick"][r] = {"score": d1 + d2, "old": d1, "h1": d2, "kept_h1": k2, "keep_ok": all(v is not None and v >= 0.8 for v in k2.values())}
        res["check"][r] = {"old_2024_25": e1, "jul_oct": e2, "kept_jul_oct": k4, "per_stream": per}
    ok = [r for r in RULES if res["pick"][r]["keep_ok"]]
    win = max(ok, key=lambda r: res["pick"][r]["score"]) if ok else max(RULES, key=lambda r: res["pick"][r]["score"])
    c = res["check"][win]
    reliable = bool(ok) and all(c["per_stream"][nm]["check_old"] > 0 for nm in S) and \
        all(v is not None and v >= 0.8 for v in c["kept_jul_oct"].values())
    res["winner"] = {"rule": win, "passed_keep_rule_in_pick": win in ok, "reliable": reliable}
    res["by_month_2026"] = by_month(S, R1, win)
    json.dump(res, open(OUT, "w", encoding="utf-8"), indent=1, default=float)
    print("streams", res["streams"])
    for r in RULES:
        p, c = res["pick"][r], res["check"][r]
        print(f"{r:10s} PICK score {p['score']:+7d} (old {p['old']:+7d}, H1 {p['h1']:+6d}, kept H1 {p['kept_h1']}) | CHECK 2024-25 "
              f"{c['old_2024_25']:+7d} Jul-Oct {c['jul_oct']:+6d} kept {c['kept_jul_oct']} | per {c['per_stream']}")
    for nm in S:
        u = res["lag1"][nm]["ungated"]
        print(nm, "ungated", {sp: u[sp]["net"] for sp in SPANS})
        for r in RULES:
            x = res["lag1"][nm]["rules"][r]; y = res["lag5"][nm]["rules"][r]
            print(f"   {r:10s} " + " ".join(f"{sp}:{x[sp]['net']:+d}" for sp in SPANS) + f" | ON {x.get('on_share', {}).get('2021-25')}/"
                  f"{x.get('on_share', {}).get('2026 H1')}/{x.get('on_share', {}).get('2026 Jul-Oct')} | lag5 21-25 {y['2021-25']['net']:+d} "
                  f"H1 {y['2026 H1']['net']:+d} JO {y['2026 Jul-Oct']['net']:+d}")
    print("WINNER", res["winner"])


if __name__ == "__main__":
    main()
