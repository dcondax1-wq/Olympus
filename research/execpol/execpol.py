"""Entry execution policy study for LIT and ATLAS (pre-registered: research/execpol/DESIGN.md). PAPER RESEARCH ONLY.

    python -X utf8 research/execpol/execpol.py        -> research/execpol/results.json + a printed table

Every price is handled in "direction space" (price x side): higher = worse for the trade, so one rule serves longs and shorts.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, ROOT)
OUT = os.path.join(HERE, "results.json")
TICK, PV, COMM = 0.25, 2.0, 1.90
SPANS = {"2026 H1": ("2026-01-01", "2026-06-30"), "2026 Jul-Oct": ("2026-07-01", "2026-10-16"), "2021-25": ("2021-01-01", "2025-12-31")}
MEASURED_S = {"ATLAS": 12, "LIT": 2}
S_GRID = (0, 1, 2, 4, 6, 8, 12, 16)
SLIP_EXITS_ATLAS = {"STOP", "stop", "BE", "cut", "T15", "FLAT", "flat", "HEDGE"}
POLICIES = ["MKT", "LIM0-1", "LIM0-2", "LIM0-5", "LIM0-15", "LIMb2-5", "LIMb4-5", "ML2", "ML4", "ML8", "PB-5", "HYB-2"]


# ---------------------------------------------------------------------- data
class Bars:
    def __init__(self, path, secs):
        b = pd.read_csv(path)
        self.t = b["time"].values.astype(np.int64)
        self.o, self.h, self.l, self.c = (b[k].values.astype(float) for k in ("open", "high", "low", "close"))
        self.secs = secs


def signals_atlas(B5):
    from tools import atlas as A, second_mix as M
    M.units()
    out = []
    for u in A.account_units(A.BASE):
        k = int(np.searchsorted(B5.t, int(u["entry_t"])))
        if k >= len(B5.t) or B5.t[k] != int(u["entry_t"]):
            continue
        d = int(u["dir"])
        P = float(B5.o[k])                                        # model entry = the signal bar's open (real price)
        out.append({"bot": "ATLAS", "day": u["day"], "t": int(u["entry_t"]), "exit_t": int(u["exit_t"]), "d": d, "P": P,
                    "Pd": P * d, "Xd": P * d + float(u["pts"]), "kind": u["exit"], "risk": float(u["risk"]),
                    "qty": 250.0 / (float(u["risk"]) * PV), "xslip": 2 if u["exit"] in SLIP_EXITS_ATLAS else 0,
                    "win": float(u["pts"]) > 0, "src": u["src"]})
    return out


def signals_lit():
    from engine.lit import COMM as LCOMM, SLIP as LSLIP
    from tools import lit_losses as L
    out = []
    for x in L.base_trades():
        d, q = int(x["dir"]), int(x["qty"])
        if q < 1:
            continue
        E = float(x["entry_px"]) * d                              # includes the backtest's 1 tick
        pts = (float(x["pnl"]) + LCOMM * q) / (PV * q)            # gross from E (the backtest's exit already has its 1 tick)
        P = float(x["entry_px"]) - d * LSLIP                      # the 1m (or 5m) bar's open
        out.append({"bot": "LIT", "day": x["day"], "t": int(x["entry_t"]), "exit_t": int(x["exit_t"]), "d": d, "P": P,
                    "Pd": P * d, "Xd": E + pts, "kind": x["exit"], "risk": float(x["risk_pts"]), "qty": float(q),
                    "xslip": 0 if x["exit"] == "TARGET" else 1, "win": pts > 0, "tf": x.get("tf")})
    return out


# ---------------------------------------------------------------------- one signal, one policy
def _ix(B, t):
    k = int(np.searchsorted(B.t, t))
    return k if k < len(B.t) and B.t[k] == t else None


_WIN: dict = {}


def _window(sg, B):
    """The bars from the signal to a little past the model's exit, in direction space (cached per signal and bar set)."""
    key = (id(sg), id(B))
    if key in _WIN:
        return _WIN[key]
    k0 = _ix(B, sg["t"])
    if k0 is None:
        _WIN[key] = None
        return None
    d = sg["d"]
    kx = int(np.searchsorted(B.t, sg["exit_t"], side="right")) - 1
    z = min(len(B.t), max(kx, k0) + 3 + 900 // B.secs * 2)
    off = B.o[k0] - sg["P"]                                     # 1m bars on another contract basis (12 days of 2026): align
    off = off if abs(off) > 1.0 else 0.0
    sl = slice(k0, z)
    o_d = (B.o[sl] - off) * d
    lo_d = np.where(d > 0, B.l[sl] - off, -(B.h[sl] - off))     # the best price for the trade in each bar (direction space)
    c_d = (B.c[sl] - off) * d
    _WIN[key] = (0, kx - k0, B.t[sl], o_d, lo_d, c_d)
    return _WIN[key]


def run_signal(sg, B, pol, s, q=1, variant="base"):
    """-> (filled, fill price in direction space or None). B: the bars of the test (1m or 5m)."""
    w = _window(sg, B)
    if w is None:
        return None
    k0, ke, t_w, o_d, lo_d, c_d = w
    d = sg["d"]
    P = sg["Pd"]
    win = sg["win"]

    def at_exit_bar(j):                                          # conservative: on the exit bar a winner is missed, a loser filled
        return j == ke and win

    def passive(L, until_t, start=k0):
        j = start
        while j < len(t_w) and t_w[j] < until_t and j <= ke:
            if variant == "next" and j == k0:
                j += 1
                continue
            # entry bar: its open (P) traded BEFORE the order rested, so the bar must trade q + 2 ticks beyond the lower of the
            # limit and P (a limit worse than P cannot be filled by the open itself)
            thr = (min(L, P) if j == k0 else L) - (q + (2 if j == k0 else 0)) * TICK
            if lo_d[j] <= thr:
                return (False, None) if at_exit_bar(j) else (True, L)
            j += 1
        return (False, None)

    def market_at(j, slip):
        if j > ke or at_exit_bar(j):
            return (False, None)
        return (True, o_d[j] + slip * TICK)

    if pol == "MKT":
        return (True, P + s * TICK)
    if pol.startswith("LIM0-"):
        return passive(P, sg["t"] + int(pol.split("-")[1]) * 60)
    if pol.startswith("LIMb"):
        b, n = pol[4:].split("-")
        return passive(P - int(b) * TICK, sg["t"] + int(n) * 60)
    if pol.startswith("ML"):
        k = int(pol[2:])
        if s <= k:
            return (True, P + s * TICK)
        return passive(P + k * TICK, sg["t"] + 5 * 60)
    if pol == "PB-5":
        j = k0
        while j < len(t_w) and t_w[j] < sg["t"] + 5 * 60 and j < ke:
            if c_d[j] < o_d[j]:                                  # a bar closing against the trade (a pullback)
                return market_at(j + 1, 2)
            j += 1
        return (False, None)
    if pol == "HYB-2":
        f = passive(P, sg["t"] + 120)
        if f[0]:
            return f
        jn = int(np.searchsorted(t_w, sg["t"] + 120))
        if jn >= len(t_w) or o_d[jn] - P > 0.25 * sg["risk"]:
            return (False, None)
        return market_at(jn, s)
    raise ValueError(pol)


def usd(sg, F):
    return sg["qty"] * ((sg["Xd"] - F - sg["xslip"] * TICK) * PV - COMM)


def evaluate(sigs, B, pol, s, variant="base"):
    n = len(sigs)
    tot = 0.0
    filled = missed_w = wins = 0
    rs = []
    for sg in sigs:
        r = run_signal(sg, B, pol, s, variant=variant)
        wins += sg["win"]
        if r is None or not r[0]:
            missed_w += sg["win"]
            rs.append(0.0)
            continue
        filled += 1
        u = usd(sg, r[1])
        tot += u
        rs.append(u)
    rs = np.array(rs)
    g, l = rs[rs > 0].sum(), -rs[rs < 0].sum()
    return {"n": n, "filled": filled, "fill_rate": round(filled / n, 3) if n else None, "net_usd": round(tot),
            "usd_per_signal": round(tot / n, 2) if n else None, "pf": round(g / l, 2) if l else None,
            "missed_winners": missed_w, "winners": wins, "missed_winner_share": round(missed_w / wins, 3) if wins else None}


# ---------------------------------------------------------------------- calibration on the real fills
def calibration(B1):
    A = json.load(open(os.path.join(ROOT, "research", "second", "atlas_fills_why.json"), encoding="utf-8"))
    out = []
    for f in A["fills"]:
        d = 1 if f["side"] == "BUY" else -1
        k = _ix(B1, int(f["entry_t"]))
        row = {"day": f["day"], "bot": f["bot"], "side": f["side"], "model": f["model"], "real_fill": f["fill"],
               "real_ticks_worse": f["ticks_vs_model"]}
        if k is not None:
            P = f["model"]
            best = [(B1.l[j] if d > 0 else B1.h[j]) for j in range(k, min(k + 5, len(B1.t)))]
            row["limit_at_model_trade_through_ticks"] = [round((P - x) * d / TICK, 1) for x in best]   # >0 = traded through P
            row["limit_at_model_fills_min1"] = bool((P - best[0]) * d / TICK >= 3)                    # q 1 + 2 on the entry bar
            row["limit_at_model_fills_by_min2_next"] = bool(len(best) > 1 and (P - best[1]) * d / TICK >= 1)
            row["ticks_saved_vs_real"] = round((f["fill"] - P) * -d / TICK, 1) if row["limit_at_model_fills_min1"] else None
        out.append(row)
    return out


def main():
    B1 = Bars(os.path.join(ROOT, "data", "NQ_1m.csv"), 60)
    B5 = Bars(os.path.join(ROOT, "data", "NQ_5m.csv"), 300)
    S = {"ATLAS": signals_atlas(B5), "LIT": signals_lit()}
    res = {"made": "2026-11-26", "design": "research/execpol/DESIGN.md", "calibration": calibration(B1), "results": {}}
    for bot, sigs in S.items():
        for sp, (a, z) in SPANS.items():
            ss = [x for x in sigs if a <= x["day"] <= z]
            B = B1 if sp.startswith("2026") else B5
            cell = {}
            for s in S_GRID:
                for pol in POLICIES:
                    if pol != "MKT" and pol not in ("ML2", "ML4", "ML8", "HYB-2") and s != S_GRID[0]:
                        continue                                  # passive / pullback fills do not depend on s
                    for var in ("base", "next"):
                        if pol == "MKT" and var == "next":
                            continue
                        key = f"{pol}|s{s}|{var}"
                        cell[key] = evaluate(ss, B, pol, s, var)
            if sp.startswith("2026"):                              # the coarse 5m method on 2026 too: how biased is it?
                for pol in ("MKT", "LIM0-5", "LIM0-15", "PB-5"):
                    cell[f"{pol}|s{MEASURED_S[bot]}|5m"] = evaluate(ss, B5, pol, MEASURED_S[bot])
            res["results"].setdefault(bot, {})[sp] = cell
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1)
    for bot in S:
        s = MEASURED_S[bot]
        print(f"\n{bot} (market slippage {s} ticks measured)")
        for sp in SPANS:
            c = res["results"][bot][sp]
            m = c[f"MKT|s{s}|base"]
            print(f"  {sp}: {m['n']} signals; MKT ${m['net_usd']:,} (${m['usd_per_signal']}/signal, PF {m['pf']})")
            for pol in POLICIES[1:]:
                ks = s if pol in ("ML2", "ML4", "ML8", "HYB-2") else 0
                for var in ("base", "next"):
                    r = c[f"{pol}|s{ks}|{var}"]
                    print(f"     {pol:8s} {var:4s} fill {r['fill_rate']:.0%}  ${r['net_usd']:>8,}  ${r['usd_per_signal']:>7}/sig  PF {r['pf']}  "
                          f"missed winners {r['missed_winner_share']:.0%}")
    print("\ncalibration:", json.dumps(res["calibration"], indent=1))


if __name__ == "__main__":
    main()
