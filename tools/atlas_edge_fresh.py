"""ATLAS edge on fresh data (2026-11-20, day-atlasedge, lead's add-on): is the edge holding, fading or noise?
Per leg and for ATLAS as a whole: the last 40 sessions to 2026-11-19 vs 2026 vs 2021-25, at 1 / 6 / 10 ticks a side,
$250 a trade, and where the last 40 sit among every earlier 40-session stretch (percentile).
Trades: the stored research rows (research/second/{ema,md,sr}_best.json, to Oct 16) + the live-code replay Oct 19 - Nov 19
(research/second/atlas_more_fresh.json, tools/atlas_more.py fresh: engine/second.run, CBOE VIX appended, parity on
Oct 7 / 13 / 15 = the stored trades). Member alone; ATLAS = the three, one position, max 2 a day (LIT's block not applied).
RESEARCH ONLY.   python -X utf8 tools/atlas_edge_fresh.py        -> research/second/atlas_edge_fresh.json
                 python -X utf8 tools/atlas_edge_fresh.py save   -> stored run atlas_fresh_fixed (what tools/edge_health.py reads):
                 the live ATLAS account units (never opposite LIT to Oct 16; the fresh weeks have no stored LIT trades, so no block)
                 + the fresh replay's units, one position, max 2 a day, each trade at a FIXED $250 (r = net R at the backtest cost).
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
OUT = os.path.join(ROOT, "research", "second", "atlas_edge_fresh.json")
TICK, PV, COMM = 0.25, 2.0, 1.9
FILES = {"EMA": "ema_best", "MD": "md_best", "SR": "sr_best"}
COSTS = (1, 6, 10)
WIN = 40


def rows():
    fr = json.load(open(os.path.join(ROOT, "research", "second", "atlas_more_fresh.json"), encoding="utf-8"))
    out = {}
    for m, f in FILES.items():
        st = json.load(open(os.path.join(ROOT, "research", "second", f + ".json"), encoding="utf-8"))["trades"]
        last = max(t["day"] for t in st)
        new = [t for t in fr["trades"].get(m, []) if t["day"] > "2026-10-16"]
        out[m] = sorted([{**t, "src": m} for t in st] + [{**t, "src": m, "fresh": True} for t in new], key=lambda t: t["entry_t"])
        out[m + "_n_fresh"] = len(new)
        out[m + "_stored_last"] = last
    return out, fr["sessions"]


def sessions(fresh_sessions):
    from tools import atlas_health as AH
    S = [d for d in AH.sessions() if d <= "2026-10-16"]
    return S + [d for d in fresh_sessions if d > S[-1]]


def usd(t, n):
    e, s, x, d = float(t["entry"]), float(t["stop"]), float(t["exit"]), int(t["dir"])
    risk = abs(e - s)
    tgt = str(t.get("exit_kind", "")).upper() == "TARGET"
    pts = (x - e) * d - (n - 1) * TICK - (0 if tgt else (n - 1) * TICK)
    q = int(250.0 // ((risk + TICK) * PV + COMM))
    return q * (pts * PV - COMM) if q > 0 else None


def one_pos(T):
    out, cur, busy, nd = [], None, 0, 0
    for t in sorted(T, key=lambda t: t["entry_t"]):
        if t["day"] != cur:
            cur, busy, nd = t["day"], 0, 0
        if t["entry_t"] < busy or nd >= 2:
            continue
        busy, nd = t["exit_t"], nd + 1
        out.append(t)
    return out


def stats(T, S, n):
    days = set(S)
    p = np.array([v for v in (usd(t, n) for t in T if t["day"] in days) if v is not None], float)
    gw, gl = p[p > 0].sum(), -p[p < 0].sum()
    eq = np.cumsum(p) if len(p) else np.zeros(1)
    return {"n": len(p), "tpw": round(len(p) / (len(S) / 5), 2), "pf": round(float(gw / gl), 2) if gl > 0 else None,
            "per_month": round(float(p.sum()) / (len(S) / 21)), "net": round(float(p.sum())),
            "max_dd": round(float((eq - np.maximum.accumulate(np.r_[0.0, eq])[1:]).min())) if len(p) else 0,
            "win": round(100.0 * float(np.mean(p > 0)), 1) if len(p) else None}


def windows(T, S, n, a, z):
    """$ a month of every 40-session window fully inside [a, z] (step 5 sessions)."""
    by = {}
    for t in T:
        v = usd(t, n)
        if v is not None:
            by[t["day"]] = by.get(t["day"], 0.0) + v
    SS = [d for d in S if a <= d <= z]
    vals = np.array([by.get(d, 0.0) for d in SS])
    return [float(vals[i:i + WIN].sum()) / (WIN / 21) for i in range(0, len(SS) - WIN + 1, 5)]


def main():
    R, fs = rows()
    S = sessions(fs)
    last40 = S[-WIN:]
    spans = {"last40": last40, "fresh_oct19_nov19": [d for d in S if d >= "2026-10-19"],
             "2026_to_oct16": [d for d in S if "2026-01-01" <= d <= "2026-10-16"],
             "H1": [d for d in S if "2026-01-01" <= d <= "2026-06-30"], "H2": [d for d in S if "2026-07-01" <= d <= "2026-10-16"],
             "2021-25": [d for d in S if d <= "2025-12-31"]}
    legs = {"EMA": R["EMA"], "MD": R["MD"], "SR": R["SR"], "ATLAS": one_pos(R["EMA"] + R["MD"] + R["SR"])}
    out = {"date": "2026-11-20", "last40": [last40[0], last40[-1]], "n_fresh": {m: R[m + "_n_fresh"] for m in FILES},
           "stored_last_trade": {m: R[m + "_stored_last"] for m in FILES}, "legs": {}}
    for nm, T in legs.items():
        o = {}
        for n in COSTS:
            o[f"{n}t"] = {sp: stats(T, d, n) for sp, d in spans.items()}
            cur = o[f"{n}t"]["last40"]["per_month"]
            w26 = windows(T, S, n, "2026-01-01", "2026-10-16")
            w21 = windows(T, S, n, "2021-11-01", "2025-12-31")
            o[f"{n}t"]["pct_vs_2026_windows"] = round(100.0 * float(np.mean(np.array(w26) <= cur)), 1)
            o[f"{n}t"]["pct_vs_2021_25_windows"] = round(100.0 * float(np.mean(np.array(w21) <= cur)), 1)
            o[f"{n}t"]["share_2026_windows_negative"] = round(100.0 * float(np.mean(np.array(w26) < 0)), 1)
            o[f"{n}t"]["share_2021_25_windows_negative"] = round(100.0 * float(np.mean(np.array(w21) < 0)), 1)
        out["legs"][nm] = o
        for n in COSTS:
            x = o[f"{n}t"]
            print(f"{nm:5s} {n:2d}t " + " | ".join(f"{sp} {x[sp]['n']}tr PF {x[sp]['pf']} ${x[sp]['per_month']}/mo" for sp in spans)
                  + f" | last40 pct: 2026 p{x['pct_vs_2026_windows']} 2021-25 p{x['pct_vs_2021_25_windows']}")
    json.dump(out, open(OUT, "w", encoding="utf-8"), indent=1)
    print("last40", out["last40"], "fresh trades", out["n_fresh"], "wrote", os.path.relpath(OUT, ROOT))


RUN_ID = "atlas_fresh_fixed"


def save():
    from tools import atlas_more as AM
    from tools import atlas_revive as RV
    from tools import runlib as rl
    _, fs = rows()
    S = [d for d in sessions(fs) if d >= "2021-01-01"]
    F = AM.fresh_units()
    U = [u for u in AM.base_units() if u["day"] <= "2026-10-16"] + [u for m in ("EMA", "MD", "SR") for u in F.get(m, []) if u["day"] > "2026-10-16"]
    T = []
    for u in RV.one_pos(U):
        loss1 = (float(u["risk"]) + TICK) * PV + COMM
        q = int(250.0 // loss1)
        if q <= 0:
            continue
        pnl = q * (float(u["pts"]) * PV - COMM)
        T.append({"day": u["day"], "entry_t": int(u["entry_t"]), "exit_t": int(u["exit_t"]), "dir": int(u["dir"]),
                  "r": round(float(RV.r_net(u)), 3), "pnl": round(pnl, 2), "risk_pts": float(u["risk"]), "qty": q,
                  "risk_usd": round(q * loss1, 2), "half": False, "exit": str(u.get("exit", "")), "trigger": u["src"], "mfe": None,
                  "mae": None, "bars_held": None, "regime": "", "mult": None, "low": round(q * (min(0.0, float(u["w1"])) * PV - COMM), 2)})
    rl.save(RUN_ID, "ATLAS at a fixed $250 a trade, to the newest bars (edge-health input)", "other",
            "Is ATLAS's edge holding on the newest data? (lead 2026-11-20)", params={}, sizing={"usd": 250, "size": "fixed"},
            trades=T, scored=rl.score(T, S), status="info",
            verdict="Fixed-size view of the live ATLAS units to the newest bars; replaces atlas_deep_zombie (eval path, data to Oct 16) as the edge check's ATLAS input.",
            notes="tools/atlas_edge_fresh.py save: stored research trades to Oct 16 + the live-code replay Oct 19 - Nov 19 (research/second/atlas_more_fresh.json).",
            writeup="atlas-edge-2026-11-20", tags=["second", "atlas", "edge_health"])
    print("saved", RUN_ID, len(T), "trades", S[0], "->", S[-1])


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "save":
        save()
    else:
        main()
