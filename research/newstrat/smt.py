"""New strategy research for the extra accounts: ICT ATM range + ES/NQ SMT, and a Judas-swing control.
PAPER RESEARCH ONLY: reads data/NQ_5m.csv + data/ES_5m.csv (TradingView CME futures), writes research/newstrat/results.json.
Never imported by engine/ or server.py. Rules: research/newstrat/RULES.md (pre-registered before any run, not changed after).

    python -X utf8 research/newstrat/smt.py            # all 5 sets, 3 periods, evals, correlation -> results.json
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(HERE, "results.json")
TICK, COMM, RISK_USD, MAXQ = 0.25, 1.90, 250.0, 20
PV = {"NQ": 2.0, "ES": 5.0}
PERIODS = {"H1": ("2026-01-01", "2026-06-30"), "H2": ("2026-07-01", "2026-10-31"), "REF": ("2021-11-01", "2025-12-31")}
ES_START = "2025-04-14"


# ------------------------------------------------------------------------------------------------ data
def load(sym):
    d = pd.read_csv(os.path.join(ROOT, "data", f"{sym}_5m.csv"))
    et = pd.to_datetime(d.time, unit="s", utc=True).dt.tz_convert("America/New_York")
    d["mod"] = et.dt.hour * 60 + et.dt.minute
    d["date"] = et.dt.strftime("%Y-%m-%d")
    return d


def days_of(d):
    """{date: dict of arrays} for RTH-bearing days, plus ATM / overnight / prior-day levels (closed bars only)."""
    t, o, h, l, c, m, dd = (d[k].to_numpy() for k in ("time", "open", "high", "low", "close", "mod", "date"))
    rth_idx = collections.OrderedDict()
    for i in np.flatnonzero((m >= 570) & (m <= 955)):
        rth_idx.setdefault(dd[i], []).append(i)
    out, prev = {}, None
    for day, ix in rth_idx.items():
        ix = np.array(ix)
        if len(ix) < 60:                                   # half days / holidays
            prev = (day, ix)
            continue
        i0 = ix[0]
        if prev is None:
            prev = (day, ix)
            continue
        pix = prev[1]
        on_start = t[pix[-1]] + 2 * 3600                   # 18:00 ET after the prior RTH close (15:55 bar + 2h05 ~ 18:00)
        on = np.flatnonzero((t >= on_start) & (t < t[i0]))
        atm = [j for j in on if dd[j] == day and 420 <= m[j] < 570]
        if len(atm) < 15 or len(on) < 30:
            prev = (day, ix)
            continue
        out[day] = {"t": t[ix], "o": o[ix], "h": h[ix], "l": l[ix], "c": c[ix], "m": m[ix],
                    "atm_h": float(h[atm].max()), "atm_l": float(l[atm].min()),
                    "on_h": float(h[on].max()), "on_l": float(l[on].min()),
                    "pd_h": float(h[pix].max()), "pd_l": float(l[pix].min())}
        prev = (day, ix)
    return out


# ------------------------------------------------------------------------------------------------ signals
def levels(S, day, kind):
    if kind == "atm":
        return S["atm_h"], S["atm_l"]
    if kind == "sess":
        return max(S["pd_h"], S["on_h"]), min(S["pd_l"], S["on_l"])
    return S["on_h"], S["on_l"]                            # judas


def signal_smt(N, E, kind, windows):
    """First SMT signal of the day -> (bar index i of the signal close, dir) or None. N, E aligned on the same bar times."""
    hN, lN = levels(N, None, kind)
    hE, lE = levels(E, None, kind)
    rhN = rhE = -1e18
    rlN = rlE = 1e18
    n = len(N["t"])
    for i in range(n - 1):
        rhN, rhE = max(rhN, N["h"][i]), max(rhE, E["h"][i])
        rlN, rlE = min(rlN, N["l"][i]), min(rlE, E["l"][i])
        em = N["m"][i + 1]                                 # the entry bar opens here
        if not any(a <= em < b for a, b in windows):
            continue
        swN_h, swE_h = rhN >= hN + TICK, rhE >= hE + TICK
        swN_l, swE_l = rlN <= lN - TICK, rlE <= lE - TICK
        bear = (swN_h and not swE_h and N["c"][i] < hN) or (swE_h and not swN_h and E["c"][i] < hE)
        bull = (swN_l and not swE_l and N["c"][i] > lN) or (swE_l and not swN_l and E["c"][i] > lE)
        if bear and bull:
            return None
        if bear or bull:
            return i, (-1 if bear else 1)
    return None


def signal_judas(N, windows):
    h, l = N["on_h"], N["on_l"]
    side = 0
    for i in range(len(N["t"]) - 1):
        if side == 0:
            if N["h"][i] >= h + TICK and N["l"][i] <= l - TICK:
                return None
            side = -1 if N["h"][i] >= h + TICK else (1 if N["l"][i] <= l - TICK else 0)
        em = N["m"][i + 1]
        if not any(a <= em < b for a, b in windows):
            if em >= max(b for _, b in windows):
                return None
            continue
        if side == -1 and N["c"][i] < h:
            return i, -1
        if side == 1 and N["c"][i] > l:
            return i, 1
    return None


# ------------------------------------------------------------------------------------------------ the trade
def trade(X, sym, i, dr, tgt_rule, kind):
    """Market entry at bar i+1 open (+1 tick), stop 1 tick beyond the extreme since 09:30, one target, flat 15:55."""
    pv = PV[sym]
    e = X["o"][i + 1] + dr * TICK
    ext = X["h"][: i + 1].max() if dr == -1 else X["l"][: i + 1].min()
    stop = ext - dr * TICK
    risk = (e - stop) * dr
    if risk <= 0:
        return {"skip": "gap"}
    if tgt_rule == "atm":
        far = (X["atm_l"] + TICK) if dr == -1 else (X["atm_h"] - TICK)
        rr = (far - e) * dr / risk
        if rr < 1.5:
            return {"skip": "rr"}
        tgt = far if rr <= 3 else e + dr * 3 * risk
    else:
        tgt = e + dr * 2 * risk
    q = min(MAXQ, int(RISK_USD // ((risk + TICK) * pv + COMM)))
    if q < 1:
        return {"skip": "wide"}
    ex, why, mae = None, None, 0.0
    for j in range(i + 1, len(X["t"])):
        hi, lo = X["h"][j], X["l"][j]
        mae = max(mae, (hi - e) if dr == -1 else (e - lo))
        if (dr == -1 and hi >= stop) or (dr == 1 and lo <= stop):
            ex, why = stop - dr * TICK, "STOP"
            break
        if (dr == -1 and lo <= tgt - TICK) or (dr == 1 and hi >= tgt + TICK):
            ex, why = tgt, "TGT"
            break
        if X["m"][j] >= 955:
            ex, why = X["c"][j], "EOD"
            break
    if ex is None:
        ex, why = X["c"][-1], "EOD"
    pts = (ex - e) * dr
    return {"dir": dr, "entry": round(float(e), 2), "stop": round(float(stop), 2), "tgt": round(float(tgt), 2),
            "risk": round(float(risk), 2), "q": q, "exit": why, "pts": round(float(pts), 2),
            "r": round(float(pts / risk), 3), "pnl": round(q * (pts * pv - COMM), 2),
            "pnl10": round(q * ((pts - 10 * TICK) * pv - COMM), 2),
            "low": round(-q * (min(mae, risk + TICK) * pv + COMM), 2),
            "entry_t": int(X["t"][i + 1]), "exit_t": int(X["t"][min(j, len(X["t"]) - 1)])}


SETS = {
    "S1": {"name": "SMT-ATM, trade NQ", "kind": "atm", "sym": "NQ", "tgt": "atm", "win": [(570, 690)]},
    "S2": {"name": "SMT-ATM, trade MES", "kind": "atm", "sym": "ES", "tgt": "atm", "win": [(570, 690)]},
    "S3": {"name": "Session SMT, trade NQ", "kind": "sess", "sym": "NQ", "tgt": "2r", "win": [(570, 690), (810, 900)]},
    "S4": {"name": "Session SMT, trade MES", "kind": "sess", "sym": "ES", "tgt": "2r", "win": [(570, 690), (810, 900)]},
    "S5": {"name": "Judas swing (NQ only, control)", "kind": "judas", "sym": "NQ", "tgt": "2r", "win": [(570, 630)]},
}


def run_set(k, DN, DE):
    s = SETS[k]
    T, days, skips = [], [], collections.Counter()
    for day in sorted(DN):
        N = DN[day]
        if s["kind"] == "judas":
            days.append(day)
            sg = signal_judas(N, s["win"])
            X = N
        else:
            if day not in DE:
                continue
            E = DE[day]
            common = np.intersect1d(N["t"], E["t"])
            if len(common) < 60:
                continue
            Na = {**N, **{f: N[f][np.isin(N["t"], common)] for f in "tohlcm"}}
            Ea = {**E, **{f: E[f][np.isin(E["t"], common)] for f in "tohlcm"}}
            days.append(day)
            sg = signal_smt(Na, Ea, s["kind"], s["win"])
            X = Na if s["sym"] == "NQ" else Ea
        if not sg:
            continue
        r = trade(X, s["sym"], sg[0], sg[1], s["tgt"], s["kind"])
        if "skip" in r:
            skips[r["skip"]] += 1
            continue
        T.append({**r, "day": day})
    return T, days, dict(skips)


# ------------------------------------------------------------------------------------------------ scoring
def stats(T, days, key="pnl"):
    p = np.array([t[key] for t in T]) if T else np.zeros(0)
    by = collections.defaultdict(float)
    for t in T:
        by[t["day"]] += t[key]
    eq = np.cumsum([by.get(d, 0.0) for d in days]) if days else np.zeros(1)
    gl = -p[p < 0].sum()
    wk = len(days) / 5.0 or 1
    return {"days": len(days), "trades": len(T), "tpw": round(len(T) / wk, 2),
            "win": round(100.0 * float((p > 0).mean()), 1) if len(p) else None,
            "pf": round(float(p[p > 0].sum() / gl), 2) if gl else None, "net": round(float(p.sum())),
            "per_month": round(float(p.sum()) / (len(days) / 21.0)) if days else 0,
            "avg_r": round(float(np.mean([t["r"] for t in T])), 3) if T else None,
            "max_dd": round(float((eq - np.maximum.accumulate(np.r_[0.0, eq])[1:]).min())) if len(eq) else 0}


def evals(T, days, plan, horizon=60):
    sys.path.insert(0, ROOT)
    from engine.analytics import simulate_eval
    by, lo = collections.defaultdict(float), collections.defaultdict(float)
    for t in T:
        by[t["day"]] += t["pnl"]
        lo[t["day"]] = min(lo[t["day"]], t["low"])
    pn = [by.get(d, 0.0) for d in days]
    ln = [lo.get(d, 0.0) for d in days]
    res = [simulate_eval(pn[s:s + horizon], plan, ln[s:s + horizon]) for s in range(len(days))]
    n = len(res) or 1
    ps = [r["days"] for r in res if r["result"] == "PASS"]
    return {"starts": len(res), "pass": round(100.0 * len(ps) / n, 1),
            "blow": round(100.0 * sum(r["result"] == "FAIL" for r in res) / n, 1),
            "open": round(100.0 * sum(r["result"] == "OPEN" for r in res) / n, 1),
            "med_days": float(np.median(ps)) if ps else None}


PLANS = {"rapid_eod_25k": {"start": 25000.0, "mll": 1000.0, "lock_above": 100.0, "eval_consistency": 0.3, "target": 1500.0,
                           "min_days_eval": 4},
         "builder_25k": {"start": 25000.0, "mll": 1000.0, "lock_above": 100.0, "eval_consistency": None, "target": 1500.0,
                         "min_days_eval": 1}}


def span(T, days, a, b):
    ds = [d for d in days if a <= d <= b]
    return [t for t in T if a <= t["day"] <= b], ds


def passes(row):
    return all(row[p]["net"] > 0 and (row[p]["pf"] or 0) >= 1.2 and 2.0 <= row[p]["tpw"] <= 4.0 and row[p]["net10"] > 0
               for p in PERIODS)


# ------------------------------------------------------------------------------------------------ correlation
def others():
    """LIT ($350 flat) and ATLAS ($250) daily $ and positions, from the repo's stored trades (tools/money/stack_one_account)."""
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    sys.path.insert(0, os.path.join(ROOT, "tools", "money"))
    import stack_one_account as SOA
    import account4_sim as A4
    S, BY = A4.load()
    D = {"S": S, "LIT": [[{**t, "strat": "LIT"} for t in ts] for ts in BY], "OTHER": collections.defaultdict(list)}
    for t in SOA._atlas():                                # the live ATLAS through account_units (BLITZ not needed here)
        D["OTHER"][t["day"]].append(t)
    usd = {"LIT": 350.0, "ATLAS": 250.0}
    daily = {"LIT": collections.defaultdict(float), "ATLAS": collections.defaultdict(float)}
    pos = {"LIT": [], "ATLAS": []}
    for i, d in enumerate(D["S"]):
        for t in list(D["LIT"][i]) + [x for x in D["OTHER"].get(d, ()) if x["strat"] == "ATLAS"]:
            s = t["strat"]
            q = max(1, int(usd[s] // ((t["risk"] + SOA.SLIP) * SOA.PV + SOA.COMM)))
            daily[s][d] += t["pts"] * SOA.PV * q - SOA.COMM * q
            pos[s].append((int(t["entry_t"]), int(t["exit_t"]), int(t["dir"])))
    return daily, pos


def correlation(T, days, daily, pos):
    out = {}
    mine = collections.defaultdict(float)
    for t in T:
        mine[t["day"]] += t["pnl"]
    for s in ("LIT", "ATLAS"):
        x = np.array([mine.get(d, 0.0) for d in days])
        y = np.array([daily[s].get(d, 0.0) for d in days])
        both = [d for d in days if mine.get(d) and daily[s].get(d)]
        ov = same = opp = 0
        for t in T:
            hits = [p for p in pos[s] if p[0] < t["exit_t"] and t["entry_t"] < p[1]]
            if hits:
                ov += 1
                same += any(p[2] == t["dir"] for p in hits)
                opp += any(p[2] != t["dir"] for p in hits)
        out[s] = {"corr": round(float(np.corrcoef(x, y)[0, 1]), 3) if x.std() and y.std() else None,
                  "days_both_trade": len(both),
                  "both_lose_days": sum(1 for d in both if mine[d] < 0 and daily[s][d] < 0),
                  "open_at_same_time": ov, "same_dir": same, "opposite_dir": opp, "trades": len(T)}
    return out


def main():
    DN, DE = days_of(load("NQ")), days_of(load("ES"))
    daily, pos = others()
    R = {"built": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"), "risk_usd": RISK_USD, "sets": {}}
    for k, s in SETS.items():
        T, days, sk = run_set(k, DN, DE)
        row = {"name": s["name"], "skips": sk}
        for p, (a, b) in PERIODS.items():
            if s["kind"] != "judas" and p == "REF":
                a = ES_START
            t2, d2 = span(T, days, a, b)
            st = stats(t2, d2)
            st["net10"] = stats(t2, d2, "pnl10")["net"]
            st["from"], st["to"] = (d2[0], d2[-1]) if d2 else (a, b)
            st["eval"] = {pl: evals(t2, d2, P) for pl, P in PLANS.items()}
            st["corr"] = correlation(t2, d2, daily, pos)
            row[p] = st
        row["pass_all"] = passes(row)
        row["trades"] = T
        R["sets"][k] = row
        print(k, s["name"], {p: (row[p]["trades"], row[p]["tpw"], row[p]["pf"], row[p]["net"], row[p]["net10"]) for p in PERIODS},
              "PASS" if row["pass_all"] else "fail", sk)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(R, fh, indent=1)
    return R


if __name__ == "__main__":
    main()
