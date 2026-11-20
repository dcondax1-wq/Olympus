"""ATLAS's 3 members (EMA = ema_lon_vix, MD = macd_sweep, SR = sr_nyreclaim, exactly as second_model.json) run on CME ES
(S&P 500 futures) 5m bars instead of NQ, as trade rows in the stored NQ research format, for the lead to score.
RESEARCH ONLY (2026-11-20): edits no engine / model / UI file, arms nothing, no network. Futures data only (data/*.csv).

Method: the research generators themselves (tools/second_ema.trades_of, tools/second_md md_cands/sim_x/greedy,
tools/second_sr run_key/set_targets) are fed the instrument's 5m bars by setting their module data (the same route as
tools/e3_es_sessions.members, 2026-11-13); engine/second.run is not replayed (it calls these same generators on live
bars). Each instrument runs in its own process (the generators keep module-level settings and caches).
  - 5m execution everywhere: there is NO ES 1m file. The stored NQ MD trades use true 1m bars for the 2026 trade path
    (fill / stop / target order inside the 5m bar); here MD runs on 5m on both NQ and ES. EMA and SR are 5m-only anyway.
    The NQ run also does MD with the 1m path (MD_1m) to show the generator reproduces the stored trades.
  - Point settings x k, k = 0.28 fixed (= the median ES/NQ 5m-open ratio over common bars, printed by `k`):
      EMA / MD stop range 6-80 -> 1.68-22.4; SR max_stop 80 -> 22.4, SR candidate range 6-120 -> 1.68-33.6;
      engine.lit.BU_TOL_MIN (MD's build-up "equal highs/lows" tolerance) 1.5 -> 0.42 (patched in this process only);
      EMA breakeven offset beo 1.25 NQ pts -> 0.75 ES pts (NOT 1.25 x k = 0.35: as tools/e3_es_sessions, the offset is
      the BE that pays the costs: exit 1 tick below it x $5 covers $1.90 -> 3 ticks).
    Unchanged: ATR / R / bar-count settings, the tick (0.25 on both), the VIX target band (VIX prior close / 100 /
    sqrt(252) x the 18:00 open of the instrument's OWN price: on ES it is the S&P implied move, no scaling needed).
  - Rows: day, entry_t, exit_t, dir, entry, stop, target, exit, exit_kind, risk_pts, pts = (exit - entry) x dir,
    r = pts / risk_pts, w1 = worst open excursion in points (<= 0). Cost convention (same as the NQ rows): market entry
    price already includes 1 tick of slippage (next 5m open + 1 tick), stop / time / flat exits include 1 tick of slippage,
    target and BE-limit exits fill at the price; commission ($1.90 a micro) is NOT in pts.

    python -X utf8 tools/atlas_es.py run      # NQ parity + ES, writes research/second/atlas_es_trades.json
    python -X utf8 tools/atlas_es.py k        # print the ES/NQ price ratio
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

OUT = os.path.join(ROOT, "research", "second", "atlas_es_trades.json")
K = 0.28
BEO_ES = 0.75
COMM = 1.90
PVI = {"NQ": 2.0, "ES": 5.0}
PARITY = ("2026-09-01", "2026-10-16")
SPANS = {"2025 Apr-Dec": ("2025-04-14", "2025-12-31"), "2026 Jan-Jun": ("2026-01-01", "2026-06-30"),
         "2026 Jul-Oct": ("2026-07-01", "2026-10-31")}
STORED = {"EMA": "ema_best", "MD": "md_best", "SR": "sr_best"}


def k_ratio():
    a = pd.read_csv(os.path.join(ROOT, "data", "ES_5m.csv"))
    b = pd.read_csv(os.path.join(ROOT, "data", "NQ_5m.csv"))
    m = a.merge(b, on="time", suffixes=("_es", "_nq"))
    return round(float(np.median(m["open_es"] / m["open_nq"])), 4)


def scaled_params(k=K):
    return {"k": k, "k_note": "fixed (median ES/NQ 5m open ratio over common bars 2025-04..2026-10)",
            "EMA min_stop": [6.0, round(6.0 * k, 4)], "EMA max_stop": [80.0, round(80.0 * k, 4)],
            "EMA beo (BE offset)": [1.25, BEO_ES],
            "MD min_stop": [6.0, round(6.0 * k, 4)], "MD max_stop": [80.0, round(80.0 * k, 4)],
            "MD build-up tol_min (engine.lit.BU_TOL_MIN)": [1.5, round(1.5 * k, 4)],
            "SR key max_stop": [80.0, round(80.0 * k, 4)], "SR outcomes max_stop": [120.0, round(120.0 * k, 4)],
            "SR outcomes min_stop": [6.0, round(6.0 * k, 4)],
            "unchanged": "ATR / R / bar-count settings, tick 0.25, VIX band (VIX% x own price), SR 2R target, MD VIX target"}


def _rec(t, worst):
    e, s, x, dr = float(t["entry"]), float(t["stop"]), float(t["exit"]), int(t["dir"])
    risk = abs(e - s)
    pts = (x - e) * dr
    return {"day": str(t["day"]), "entry_t": int(t["entry_t"]), "exit_t": int(t["exit_t"]), "dir": dr, "entry": e, "stop": s,
            "target": None if t.get("target") is None else float(t["target"]), "exit": x, "exit_kind": str(t["exit_kind"]),
            "risk_pts": round(risk, 4), "pts": round(pts, 4), "r": round(pts / risk, 4) if risk > 0 else None,
            "w1": round(float(min(0.0, worst)), 4)}


def members(sym, path):
    """EMA / MD / SR as second_model.json on sym's 5m bars; point settings x K for ES. Writes {name: rows} to path."""
    from engine import lit
    from engine.data import load
    from tools import retail_standalone as RS
    from tools import second_ema as SE
    from tools import second_md as SM
    from tools import second_sr as SR
    k = 1.0 if sym == "NQ" else K
    lit.BU_TOL_MIN = 1.5 * k
    cfg = json.load(open(os.path.join(ROOT, "second_model.json"), encoding="utf-8"))["strategies"]
    df = pd.read_csv(os.path.join(ROOT, "data", f"{sym}_5m.csv"))
    RS.load_frame(df)
    if sym != "NQ":                                     # unadjusted price for round numbers: the instrument's own rolls
        rolls = json.load(open(os.path.join(ROOT, "data", f"{sym}_rolls.json")))["rolls"]
        adj = np.zeros(RS.D["n"] if "n" in RS.D else len(RS.D["t"]))
        for r in rolls:
            adj[RS.D["t"] < r["switch_t"]] += r["gap"]
        RS.D["adj"] = adj
    out = {}
    t0 = time.time()
    # ---- EMA
    c = cfg["ema_lon_vix"]
    E, X = dict(c["entry"]), dict(c["exit"])
    SE.MIN_STOP, SE.MAX_STOP = 6.0 * k, 80.0 * k
    SE.CPTS = COMM / PVI[sym]
    if sym != "NQ":
        X["beo"] = BEO_ES
    U = SE.trades_of(E, X, span=("2021-11-01", "2026-10-31"))
    out["EMA"] = [_rec(u, u["worst_pts"]) for u in U]
    print(sym, "EMA", len(out["EMA"]), f"{time.time() - t0:.0f}s", flush=True)
    # ---- SR
    c = cfg["sr_nyreclaim"]
    key = dict(c["key"])
    key["max_stop"] = 80.0 * k
    SR.outcomes.__defaults__ = (120.0 * k, 6.0 * k, 1.5)
    SR.D.clear(); SR._OC.clear()
    SR.data()
    TT = SR.set_targets(SR.trades_of(SR.run_key(key), "usd500", "nyreclaim"), key)
    out["SR"] = [_rec(t, -float(t["mae"]) * float(t["_x"]["risk"])) for t in TT]
    print(sym, "SR", len(out["SR"]), f"{time.time() - t0:.0f}s", flush=True)
    # ---- MD (5m execution; on NQ also the stored 1m path for the parity check)
    c = cfg["macd_sweep"]
    gen, sim, flt = dict(c["gen"]), dict(c["sim"]), dict(c["flt"])
    SM.MIN_STOP, SM.MAX_STOP = 6.0 * k, 80.0 * k
    M = lit.Market(bars=load(sym, "5m"))
    for nm, b1 in (("MD", "none"),) + ((("MD_1m", None),) if sym == "NQ" else ()):
        Xc = SM.Ctx(M, b1)
        C = SM.md_cands(Xc, **gen)
        outs = [SM.sim_x(Xc, z, sim) for z in C]
        TM = SM.greedy(Xc, C, outs, flt["kz"], flt["maxpd"], SM.md_filter(flt))
        out[nm] = [_rec(t, t["_worst"]) for t in (SM.tr_rec(Xc, z, r, 1, "MD") for z, r in TM)]
        print(sym, nm, len(out[nm]), f"{time.time() - t0:.0f}s", flush=True)
    json.dump(out, open(path, "w"))
    return out


def _sub(sym, tmp):
    p = os.path.join(tmp, f"atlas_es_{sym}.json")
    subprocess.run([sys.executable, "-X", "utf8", os.path.abspath(__file__), "members", sym, p], check=True)
    return json.load(open(p))


def parity(mine, stored, span):
    a = {(t["day"], int(t["entry_t"]), int(t["dir"])): t for t in stored if span[0] <= t["day"] <= span[1]}
    b = {(t["day"], int(t["entry_t"]), int(t["dir"])): t for t in mine if span[0] <= t["day"] <= span[1]}
    same = set(a) & set(b)
    ex = sum(1 for q in same if int(a[q]["exit_t"]) == int(b[q]["exit_t"]) and abs(float(a[q]["exit"]) - float(b[q]["exit"])) < 1e-6)
    return {"stored": len(a), "here": len(b), "same_entries": len(same), "same_exits": ex}


def span_stats(T):
    o = {}
    for nm, (a, z) in SPANS.items():
        r = [t["r"] for t in T if a <= t["day"] <= z and t["r"] is not None]
        o[nm] = {"n": len(r), "mean_r": round(float(np.mean(r)), 3) if r else None}
    return o


def run():
    t0 = time.time()
    tmp = tempfile.mkdtemp(prefix="atlas_es_")
    nq, es = _sub("NQ", tmp), _sub("ES", tmp)
    par = {}
    for nm, f in STORED.items():
        st = json.load(open(os.path.join(ROOT, "research", "second", f + ".json"), encoding="utf-8"))["trades"]
        par[nm] = {"2026-09-01..2026-10-16": parity(nq[nm], st, PARITY), "all": parity(nq[nm], st, ("2021-01-01", "2026-12-31"))}
        if nm == "MD":
            par["MD_1m_path"] = {"2026-09-01..2026-10-16": parity(nq["MD_1m"], st, PARITY),
                                 "all": parity(nq["MD_1m"], st, ("2021-01-01", "2026-12-31"))}
    stats = {nm: span_stats(es[nm]) for nm in ("EMA", "MD", "SR")}
    o = {"date": "2026-11-20", "method": __doc__.split("Method:")[1].split("    python")[0].strip(),
         "scaled_params": scaled_params(), "nq_parity": par, "es_span_stats": stats,
         "es_bars": "data/ES_5m.csv sessions 2025-04-14 .. last day; 5m execution",
         "trades": {nm: es[nm] for nm in ("EMA", "MD", "SR")}}
    json.dump(o, open(OUT, "w", encoding="utf-8"), indent=0)
    print(json.dumps(par, indent=1))
    print(json.dumps(stats, indent=1))
    print("wrote", OUT, f"{time.time() - t0:.0f}s")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    if cmd == "members":
        members(sys.argv[2], sys.argv[3])
    elif cmd == "k":
        print(k_ratio())
    else:
        run()
