"""MARKET STRUCTURE STUDY (owner 2026-11-24: "Expansion, retracements, look at these stuff"). PAPER RESEARCH ONLY: measures,
never trades; no live file is read for writing. Futures data only (data/NQ_5m.csv: TradingView NQ1! + the PC's NinjaTrader bars).

What it measures (all rules fixed in this file before the numbers were looked at; base rates, not a strategy):
  A  daily: expansion days (range >= 1.5x the prior 14-session ATR), expansion-after-compression (inside day, NR4, NR7, quiet
     prior day < 0.7 ATR, small overnight range < 0.35 ATR), trend-day odds, return to the 09:30 open after a first-hour drive,
     time of day of the session high / low.
  B  5m displacement candles (body >= 1.5x the 5m ATR14, close in the outer quarter): time of day, follow-through, FVG left
     and FVG fill odds.
  C  swing legs (zigzag, a pivot is fixed when price comes back 0.3x the daily ATR): expansion legs (>= 0.75 ATR), how deep the
     retracement goes (fib buckets 0.382 / 0.5 / 0.618 / 0.705 / 0.79 / 1.0), continuation vs reversal by depth, measured-move
     completion of the next leg (0.618 / 1.0 / 1.272 / 1.618 x the expansion), the TRADEABLE fib table (limit at fib f placed
     when the leg is confirmed, stop 1 tick beyond the leg start, target the leg extreme: win %, avg R), the hour legs start.
  D  how the pillars' own backtest trades (research/learn/lessons.jsonl.gz: LIT / ATLAS / BLITZ, costs in) sit in that
     structure at entry (causal tags: range used, place in the day's range, with / against the last swing and how deep, a
     displacement in the trade's direction in the last 30 min, compression day) and in hindsight (did the win come at the
     start of an expansion leg, did the loss fight one).

    python -X utf8 research/structure/study.py      -> research/structure/STRUCTURE_ATLAS.json (+ prints the headline)
"""
from __future__ import annotations

import collections
import gzip
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import bars as BR  # noqa: E402

OUT = os.path.join(HERE, "STRUCTURE_ATLAS.json")
TICK = 0.25
ZZ_K = 0.30            # zigzag reversal = 0.3 x daily ATR
EXP_K = 0.75           # an expansion leg >= 0.75 x daily ATR
DISP_K = 1.5           # 5m displacement body >= 1.5 x 5m ATR14
FIBS = (0.382, 0.5, 0.618, 0.705, 0.79)
DEPTH_EDGES = (0.236, 0.382, 0.5, 0.618, 0.705, 0.79, 1.0)
SPANS = ("2021-25", "H1", "H2")
HORIZON = 3 * 276      # walk at most ~3 sessions of 5m bars after a leg


def pct(a, b):
    return round(100.0 * a / b, 1) if b else None


def r3(x):
    return None if x is None or x != x else round(float(x), 3)


# ================================================================================================ bars + context
def context():
    df = BR.load("NQ", "5m")
    D = BR.daily(df)
    df = df[df["day"].isin(D.index)].reset_index(drop=True)
    t = df["time"].to_numpy()
    o, h, l, c = (df[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    day = df["day"].to_numpy()
    mins = df["mins"].to_numpy()
    atr_d = D["atr"].reindex(day).to_numpy(float)
    tr = np.maximum(h - l, np.maximum(abs(h - np.roll(c, 1)), abs(l - np.roll(c, 1))))
    tr[0] = h[0] - l[0]
    atr5 = np.convolve(tr, np.ones(14) / 14, mode="full")[:len(tr)]
    atr5 = np.concatenate([[np.nan], atr5[:-1]])                       # prior 14 bars
    atr5[:15] = np.nan
    body = c - o
    disp = np.zeros(len(c), dtype=int)
    rngb = np.maximum(h - l, TICK)
    up = (body >= DISP_K * atr5) & ((c - l) / rngb >= 0.75)
    dn = (-body >= DISP_K * atr5) & ((h - c) / rngb >= 0.75)
    disp[up], disp[dn] = 1, -1
    # session start index per bar
    first = {}
    for i, d in enumerate(day):
        first.setdefault(d, i)
    s0 = np.array([first[d] for d in day])
    piv = BR.zigzag(h, l, ZZ_K * np.nan_to_num(atr_d, nan=np.nanmedian(atr_d)))
    return {"df": df, "D": D, "t": t, "o": o, "h": h, "l": l, "c": c, "day": day, "mins": mins, "atr_d": atr_d,
            "atr5": atr5, "disp": disp, "s0": s0, "piv": piv}


# ================================================================================================ A daily
def daily_stats(X):
    D = X["D"]
    out = {}
    for sp in SPANS + ("all",):
        d = D if sp == "all" else D[D["span"] == sp]
        n = len(d)
        base = float((d["ratio"] >= 1.5).mean())
        row = {"sessions": n, "expansion_day_pct": round(100 * base, 1), "avg_range_x_atr": r3(d["ratio"].mean()),
               "quiet_day_pct": round(100 * float((d["ratio"] < 0.7).mean()), 1)}
        cl = (d["close"] - d["low"]) / (d["high"] - d["low"])
        row["trend_day_pct"] = round(100 * float(((cl >= 0.8) | (cl <= 0.2)).mean()), 1)
        comp = {}
        for nm, m in (("inside_day_before", d["inside"]), ("nr4_before", d["nr4"]), ("nr7_before", d["nr7"]),
                      ("quiet_day_before", d["prior_ratio"] < 0.7), ("big_day_before", d["prior_ratio"] >= 1.5),
                      ("small_overnight", d["on_rng"] < 0.35), ("big_overnight", d["on_rng"] >= 0.6)):
            m = m.fillna(False).astype(bool)
            k = d[m]
            if len(k) < 5:
                continue
            ex = float((k["ratio"] >= 1.5).mean())
            rth_r = ((k["rth_high"] - k["rth_low"]) / k["atr"]).mean()
            comp[nm] = {"n": int(len(k)), "next_expansion_pct": round(100 * ex, 1), "lift_vs_base": r3(ex / base if base else None),
                        "avg_range_x_atr": r3(k["ratio"].mean()), "avg_rth_range_x_atr": r3(rth_r)}
        row["after"] = comp
        out[sp] = row
    return out


def open_return(X):
    """First RTH hour drives >= 0.5 ATR from the 09:30 open: does price come back to the open before 16:00?"""
    df = X["df"]
    res = collections.defaultdict(lambda: [0, 0])
    tod = {}
    for day, g in df[(df["mins"] >= 570) & (df["mins"] < 960)].groupby("day"):
        if day not in X["D"].index or len(g) < 70:
            continue
        atr = float(X["D"].at[day, "atr"])
        op = float(g["open"].iloc[0])
        fh = g[g["mins"] < 630]
        rest = g[g["mins"] >= 630]
        up, dn = fh["high"].max() - op, op - fh["low"].min()
        sp = BR.span_of(day)
        hi_t = int(g["mins"].iloc[int(np.argmax(g["high"].to_numpy()))])
        lo_t = int(g["mins"].iloc[int(np.argmin(g["low"].to_numpy()))])
        tod.setdefault(sp, []).append((hi_t, lo_t))
        for k in (0.3, 0.5):
            if max(up, dn) >= k * atr:
                drove_up = up >= dn
                back = (rest["low"].min() <= op) if drove_up else (rest["high"].max() >= op)
                res[(sp, k)][0] += 1
                res[(sp, k)][1] += bool(back)
    out = {}
    for (sp, k), (n, b) in sorted(res.items()):
        out.setdefault(sp, {})[f"first_hour_drive_{k}atr"] = {"n": n, "back_to_open_pct": pct(b, n)}
    hours = {}
    for sp, L in tod.items():
        hc = collections.Counter(min(15, m // 60) for m, _ in L) + collections.Counter(min(15, m // 60) for _, m in L)
        n = 2 * len(L)
        hours[sp] = {f"{hh:02d}:00": pct(v, n) for hh, v in sorted(hc.items())}
    return out, hours


# ================================================================================================ B displacement + FVG
def displacement(X):
    h, l, c, o, disp, day, mins = X["h"], X["l"], X["c"], X["o"], X["disp"], X["day"], X["mins"]
    n = len(c)
    rows = collections.defaultdict(list)
    for i in np.nonzero(disp)[0]:
        if i < 2 or i + 2 >= n:
            continue
        d = int(disp[i])
        sp = BR.span_of(day[i])
        bd = abs(c[i] - o[i])
        # follow-through: within 12 bars, +1 body beyond the close before the candle's open is lost
        ft, j = None, i + 1
        while j < min(n, i + 13) and day[j] == day[i]:
            if (h[j] - c[i] if d > 0 else c[i] - l[j]) >= bd:
                ft = True; break
            if (l[j] <= o[i] if d > 0 else h[j] >= o[i]):
                ft = False; break
            j += 1
        # FVG = bar i-1 and bar i+1 do not overlap (left by the displacement); fill = price trades back to bar i-1's extreme
        if d > 0:
            gap = l[i + 1] - h[i - 1]
            edge = h[i - 1]
        else:
            gap = l[i - 1] - h[i + 1]
            edge = l[i - 1]
        fvg = gap > 0
        fill12 = fill_s = None
        if fvg:
            fill12 = fill_s = False
            j = i + 2
            while j < n and day[j] == day[i]:
                hit = l[j] <= edge if d > 0 else h[j] >= edge
                if hit:
                    fill_s = True
                    fill12 = j - i <= 13
                    break
                j += 1
        rows[sp].append((int(mins[i]) // 30, ft, fvg, fill12, fill_s))
    out = {}
    for sp, R in rows.items():
        tod = collections.Counter(r[0] for r in R)
        fts = [r[1] for r in R if r[1] is not None]
        fv = [r for r in R if r[2]]
        top = sorted(tod.items(), key=lambda kv: -kv[1])[:6]
        out[sp] = {"candles": len(R), "per_session": round(len(R) / max(1, len(set(X["day"][BR_mask(X, sp)]))), 2),
                   "follow_through_pct": pct(sum(fts), len(fts)), "left_fvg_pct": pct(len(fv), len(R)),
                   "fvg_filled_1h_pct": pct(sum(r[3] for r in fv), len(fv)),
                   "fvg_filled_same_session_pct": pct(sum(r[4] for r in fv), len(fv)),
                   "busiest_half_hours_et": {f"{k // 2:02d}:{30 * (k % 2):02d}": pct(v, len(R)) for k, v in top}}
    return out


def BR_mask(X, sp):
    return np.array([BR.span_of(d) == sp for d in X["day"]])


# ================================================================================================ C legs, retracements, fibs
def legs(X):
    """Consecutive zigzag pivots P0 -> P1 (expansion A), P1 -> P2 (retracement B), P2 -> P3 (next leg C)."""
    piv, atr, day = X["piv"], X["atr_d"], X["day"]
    L = []
    for k in range(len(piv) - 3):
        (i0, p0, k0, _), (i1, p1, k1, c1), (i2, p2, _, c2), (i3, p3, _, _) = piv[k:k + 4]
        a = abs(p1 - p0)
        A = atr[i1]
        if not A or A != A:
            continue
        d = 1 if k0 == -1 else -1                       # A's direction: from a low = up
        disp_in = bool(np.any(X["disp"][i0:i1 + 1] == d))
        L.append({"i0": i0, "i1": i1, "i2": i2, "c1": c1, "c2": c2, "dir": d, "p0": p0, "p1": p1, "p2": p2, "p3": p3,
                  "a_atr": a / A, "depth": abs(p1 - p2) / a if a else None, "c_ratio": abs(p3 - p2) / a if a else None,
                  "span": BR.span_of(day[i1]), "start_min": int(X["mins"][i0]), "disp": disp_in,
                  "bars": i1 - i0})
    return L


def depth_bucket(x):
    if x is None:
        return None
    for e in DEPTH_EDGES:
        if x < e:
            return f"<{e}"
    return ">=1.0 (reversal)"


def leg_stats(L):
    out = {}
    for sp in SPANS:
        E = [x for x in L if x["span"] == sp and x["a_atr"] >= EXP_K]
        allL = [x for x in L if x["span"] == sp]
        if not E:
            continue
        dep = collections.Counter(depth_bucket(x["depth"]) for x in E)
        by = {}
        for b in [f"<{e}" for e in DEPTH_EDGES] + [">=1.0 (reversal)"]:
            g = [x for x in E if depth_bucket(x["depth"]) == b]
            if not g:
                continue
            cont = [x for x in g if x["depth"] < 1 and x["c_ratio"] > 1.0 - x["depth"] + 1e-9]
            # continuation = leg C goes beyond A's extreme: |p3 - p2| > |p1 - p2| -> c_ratio > depth
            cont = [x for x in g if x["depth"] < 1 and x["c_ratio"] > x["depth"]]
            by[b] = {"n": len(g), "share_pct": pct(len(g), len(E)), "continued_pct": pct(len(cont), len(g)) if b != ">=1.0 (reversal)" else None}
        ok = [x for x in E if x["depth"] < 1]
        mm = {f">={m}x": pct(sum(x["c_ratio"] >= m for x in ok), len(ok)) for m in (0.618, 1.0, 1.272, 1.618)}
        hours = collections.Counter(min(23, x["start_min"] // 60) for x in E)
        top = sorted(hours.items(), key=lambda kv: -kv[1])[:6]
        disp = [x for x in E if x["disp"]]
        nod = [x for x in E if not x["disp"]]
        out[sp] = {"legs": len(allL), "expansion_legs": len(E), "expansion_share_pct": pct(len(E), len(allL)),
                   "median_expansion_x_atr": r3(np.median([x["a_atr"] for x in E])),
                   "median_retrace_depth": r3(np.median([x["depth"] for x in E])),
                   "retrace_depth_buckets": by,
                   "reversal_pct": pct(sum(x["depth"] >= 1 for x in E), len(E)),
                   "next_leg_vs_expansion_pct (measured move, when the retrace held)": mm,
                   "displaced_legs": {"n": len(disp), "median_depth": r3(np.median([x["depth"] for x in disp])) if disp else None,
                                      "reversal_pct": pct(sum(x["depth"] >= 1 for x in disp), len(disp))},
                   "not_displaced_legs": {"n": len(nod), "median_depth": r3(np.median([x["depth"] for x in nod])) if nod else None,
                                          "reversal_pct": pct(sum(x["depth"] >= 1 for x in nod), len(nod))},
                   "expansion_start_hours_et (top 6, % of legs)": {f"{hh:02d}:00": pct(v, len(E)) for hh, v in top}}
    return out


def fib_trades(X, L, fibs=FIBS, only_disp=False, k_min=EXP_K):
    """TRADEABLE fib table. For each expansion leg, once it is CONFIRMED (bar c1, the zigzag pivot fixed), a limit at fib f of
    the leg (f = depth back from the extreme) - only if price has not reached f yet. Stop 1 tick beyond the leg start, target
    the leg extreme (retest) or 1.272 extension. Walk 5m bars; a bar touching stop and target = a loss. No costs (base rate)."""
    h, l, day = X["h"], X["l"], X["day"]
    n = len(h)
    res = collections.defaultdict(list)
    for x in L:
        if x["a_atr"] < k_min or (only_disp and not x["disp"]):
            continue
        d, p0, p1, c1 = x["dir"], x["p0"], x["p1"], x["c1"]
        a = abs(p1 - p0)
        # deepest point reached between the extreme and the confirmation bar
        seg = slice(x["i1"] + 1, c1 + 1)
        deep = (p1 - l[seg].min()) / a if d > 0 else (h[seg].max() - p1) / a
        for f in fibs:
            if deep >= f:
                continue
            lvl = p1 - d * f * a
            stop = p0 - d * TICK
            for tgt_name, tg in (("extreme", p1), ("ext1.272", p1 + d * 0.272 * a)):
                risk = abs(lvl - stop)
                rew = abs(tg - lvl)
                fill = None
                j = c1 + 1
                end = min(n, c1 + HORIZON)
                out = None
                while j < end:
                    if fill is None:
                        if (l[j] <= lvl if d > 0 else h[j] >= lvl):
                            fill = j
                            if (l[j] <= stop if d > 0 else h[j] >= stop):
                                out = -1.0; break
                        elif (h[j] > p1 + 0.272 * a * 2 if d > 0 else l[j] < p1 - 0.272 * a * 2):
                            break                                   # ran away: order cancelled
                    else:
                        hs = l[j] <= stop if d > 0 else h[j] >= stop
                        ht = h[j] >= tg if d > 0 else l[j] <= tg
                        if hs:
                            out = -1.0; break
                        if ht:
                            out = rew / risk; break
                    j += 1
                if fill is not None and out is None:
                    out = ((X["c"][j - 1] - lvl) * d) / risk           # timed out: mark to the last close
                if fill is not None:
                    res[(x["span"], f, tgt_name)].append(out)
    out = {}
    for (sp, f, tn), R in sorted(res.items()):
        R = np.array(R)
        out.setdefault(sp, {}).setdefault(tn, {})[str(f)] = {"fills": int(len(R)), "win_pct": pct(int((R > 0).sum()), len(R)),
                                                              "avg_r": r3(R.mean()), "rr": r3(np.median(R[R > 0])) if (R > 0).any() else None}
    return out


# ================================================================================================ D the pillars' trades
def tag_trades(X, rows):
    t, h, l, c, day, s0, atr_d, disp = X["t"], X["h"], X["l"], X["c"], X["day"], X["s0"], X["atr_d"], X["disp"]
    piv = X["piv"]
    conf = np.array([p[3] for p in piv])
    pidx = np.array([p[0] for p in piv])
    D = X["D"]
    out = []
    for r in rows:
        et = int(r["entry_t"])
        j = int(np.searchsorted(t, et - 300, side="right")) - 1        # the last 5m bar CLOSED before the entry
        if j < 50 or day[j] != r["day"] and abs(int(t[j]) - et) > 4 * 3600:
            continue
        d = int(r["dir"])
        A = atr_d[j]
        if not A or A != A:
            continue
        a0 = s0[j]
        hi, lo = h[a0:j + 1].max(), l[a0:j + 1].min()
        p = c[j]
        used = (hi - lo) / A
        pos = (p - lo) / (hi - lo) if hi > lo else 0.5
        pos = pos if d > 0 else 1 - pos                                # 0 = bought the day's low so far / sold its high
        # causal swing state: last two pivots confirmed by bar j
        k = int(np.searchsorted(conf, j, side="right")) - 1
        phase, depth = None, None
        if k >= 1:
            (i_a, p_a, k_a, _), (i_b, p_b, k_b, _) = piv[k - 1], piv[k]
            leg_dir = 1 if k_a == -1 else -1                           # the last completed swing P_a -> P_b
            a = abs(p_b - p_a)
            depth = abs(p - p_b) / a if a else None
            phase = "with the last swing (buying its pullback)" if d == leg_dir else "against the last swing (fading it)"
            big = a / A >= EXP_K
        else:
            big = False
        early = bool(np.any(disp[max(a0, j - 5):j + 1] == d))
        dd = D.loc[r["day"]] if r["day"] in D.index else None
        comp = bool(dd is not None and (bool(dd["inside"]) or bool(dd["nr7"]) or (dd["prior_ratio"] < 0.7)))
        # hindsight: the zigzag leg the entry sits in
        q = int(np.searchsorted(pidx, j, side="right")) - 1
        hs = None
        if 0 <= q < len(piv) - 1:
            (i_s, p_s, k_s, _), (i_e, p_e, _, _) = piv[q], piv[q + 1]
            ldir = 1 if k_s == -1 else -1
            span = abs(p_e - p_s)
            frac = abs(p - p_s) / span if span else None
            if span / A >= EXP_K:
                if ldir == d:
                    hs = "start of an expansion leg (first 25%)" if frac is not None and frac <= 0.25 else "inside an expansion leg, with it"
                else:
                    hs = "fought an expansion leg"
            else:
                hs = "small swing (no expansion)"
        out.append({**{k_: r.get(k_) for k_ in ("pillar", "span", "day", "entry_t", "dir", "r", "usd", "member")},
                    "used": used, "pos": pos, "phase": phase, "depth": depth, "big_swing": big, "early_disp": early,
                    "compression": comp, "hindsight": hs})
    return out


def _b_used(x):
    return "<0.5 ATR" if x < 0.5 else "0.5-0.8 ATR" if x < 0.8 else "0.8-1.1 ATR" if x < 1.1 else ">=1.1 ATR (day stretched)"


def _b_pos(x):
    return "0-20% (at the day's extreme on our side)" if x < 0.2 else "20-50%" if x < 0.5 else "50-80%" if x < 0.8 else "80-100% (chasing)"


def _b_phase(r):
    if r["phase"] is None or r["depth"] is None:
        return None
    w = "with" if r["phase"].startswith("with") else "against"
    dp = r["depth"]
    b = "<0.5" if dp < 0.5 else "0.5-0.79" if dp < 0.79 else "0.79-1.0" if dp < 1.0 else ">=1.0 (swing broken)"
    return f"{w} swing, retrace {b}"


def table(T, key):
    out = {}
    for p in sorted({r["pillar"] for r in T}):
        for sp in SPANS:
            g = [r for r in T if r["pillar"] == p and r["span"] == sp]
            if not g:
                continue
            base = np.mean([r["r"] for r in g])
            cells = collections.defaultdict(list)
            for r in g:
                k = key(r)
                if k is not None:
                    cells[k].append(r)
            out.setdefault(p, {})[sp] = {"base_avg_r": r3(base), "n": len(g), "cells": {
                k: {"n": len(v), "avg_r": r3(np.mean([x["r"] for x in v])), "win_pct": pct(sum(x["r"] > 0 for x in v), len(v)),
                    "usd": round(sum(x["usd"] or 0 for x in v))} for k, v in sorted(cells.items())}}
    return out


def loss_win_story(T):
    out = {}
    for p in sorted({r["pillar"] for r in T}):
        for sp in SPANS:
            g = [r for r in T if r["pillar"] == p and r["span"] == sp and r["hindsight"]]
            if not g:
                continue
            W = [r for r in g if r["r"] > 0.05]
            Ls = [r for r in g if r["r"] < -0.05]
            cw = collections.Counter(r["hindsight"] for r in W)
            cl = collections.Counter(r["hindsight"] for r in Ls)
            deep = [r for r in Ls if r["phase"] and r["depth"] is not None and r["depth"] >= 0.79]
            out.setdefault(p, {})[sp] = {
                "wins": len(W), "losses": len(Ls),
                "wins_where_pct": {k: pct(v, len(W)) for k, v in cw.most_common()},
                "losses_where_pct": {k: pct(v, len(Ls)) for k, v in cl.most_common()},
                "losses_at_a_retracement_extreme_pct (entry >= 0.79 of the last swing)": pct(len(deep), len(Ls)),
                "losses_usd": round(sum(r["usd"] or 0 for r in Ls))}
    return out


def pillar_rows():
    with gzip.open(os.path.join(ROOT, "research", "learn", "lessons.jsonl.gz"), "rt", encoding="utf-8") as fh:
        return [json.loads(x) for x in fh if x.strip()]


def run(say=print):
    X = context()
    say(f"bars {len(X['c'])}, sessions {len(X['D'])}, pivots {len(X['piv'])}")
    A = daily_stats(X)
    ret, hours = open_return(X)
    B = displacement(X)
    L = legs(X)
    C = leg_stats(L)
    F = fib_trades(X, L)
    Fd = fib_trades(X, L, only_disp=True)
    rows = [r for r in pillar_rows() if r.get("span") in SPANS]
    T = tag_trades(X, rows)
    say(f"pillar trades tagged {len(T)} of {len(rows)}")
    J = {"made": "2026-11-24", "data": "data/NQ_5m.csv (TradingView NQ1! exports + PC NinjaTrader bars), sessions 18:00-17:00 ET",
         "rules": {"atr": "prior 14 sessions' range", "expansion_day": "range >= 1.5 ATR", "zigzag": f"{ZZ_K} x ATR reversal",
                   "expansion_leg": f">= {EXP_K} ATR", "displacement_5m": f"body >= {DISP_K} x 5m ATR14, close in the outer 25%"},
         "spans": {"2021-25": "Oct 2021 - Dec 2025", "H1": "Jan-Jun 2026", "H2": "Jul 2026 - now"},
         "A_daily": A, "A_back_to_rth_open": ret, "A_session_high_low_hour_et_pct": hours,
         "B_displacement_5m": B, "C_expansion_legs": C, "C_fib_limit_trades (stop beyond leg start, no costs)": F,
         "C_fib_limit_trades_displaced_legs_only": Fd,
         "D_pillars": {"range_used_at_entry": table(T, lambda r: _b_used(r["used"])),
                       "place_in_day_range_at_entry": table(T, lambda r: _b_pos(r["pos"])),
                       "swing_phase_at_entry": table(T, _b_phase),
                       "displacement_our_way_last_30min": table(T, lambda r: "yes" if r["early_disp"] else "no"),
                       "compression_day": table(T, lambda r: "yes" if r["compression"] else "no"),
                       "hindsight_story": loss_win_story(T)}}
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(J, fh, indent=1, default=float)
    say(f"wrote {os.path.relpath(OUT, ROOT)}")
    return J, X, L, T


if __name__ == "__main__":
    run()
