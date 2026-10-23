"""NQ around the clock (owner 2026-10-23: "Start trading 24/7. Find more setups with the same or higher win rate. Deep research.")

Maps every part of the CME NQ day (18:00 -> 17:00 ET) and tests the setup families that fit each part, so the bots could trade
24/5. Everything is CME NQ1! from TradingView (data/NQ_5m.csv 2021-11 .. 2026-10-16, data/NQ_1m.csv for 2026); no Yahoo, no CFD.

Windows (ET, trading-day order; a trading day starts at 18:00 the evening before):
  open18 18:00-20:00 (Sunday open on Mondays) | asia 20:00-00:00 | late_asia 00:00-02:00 | lon_open 02:00-05:00 |
  london 05:00-08:00 | ny_pre 08:00-09:30 | ny_open 09:30-11:00 | ny_mid 11:00-13:30 | ny_pm 13:30-15:55 | post 16:00-17:00

  python -X utf8 tools/allday.py map       # 1. the 24-hour map -> research/allday/map.json
  python -X utf8 tools/allday.py lit       # 2a. LIT's chain per window (engine/lit.py run_x, window + kz overrides)
  python -X utf8 tools/allday.py fam       # 2b. sweep-reclaim / ORB / mean reversion / continuation per window
  python -X utf8 tools/allday.py pick      # 3. picks on 2026 H1, H2 untouched, 2025 + 2021-24, months, plateau, placebo
  python -X utf8 tools/allday.py combo     # 4. 24/5 schedules on LIT's 50K / ATLAS 25K / a third account
  python -X utf8 tools/allday.py save      # rl.save runs ad_* + research/allday/<pick>.json
Paper only. Edits no engine file and no live_model*.json / second_model.json.

Execution of the non-LIT families (no look-ahead, costs in): a signal is known at a 5m bar close; market entry at the next 5m
open + 1 tick. Stops are structural (1 tick beyond the sweep extreme / the swing / the opposite side of the opening range),
never a fixed distance; 6-80 pts. Management on true 1m bars on 2026 days with full 1m coverage (lit.bars_1m), else on 5m:
stop first when stop and target sit in one bar; target = limit, filled on a trade-through (1 tick beyond); stop and time
exits - 1 tick; breakeven (when on) = entry + 1.25 pts once +be R was reached (from the next bar). Flat at the setup's time
exit, never after 15:55 (MFFU: flat by 16:10) and never through the 17:00 halt; the post window (16:00-17:00) cannot be traded
on MFFU (auto-liquidation 16:10) and is mapped only. Size: the LIT size rule ($800 up to a 20-pt stop, then 800 x 20 / stop,
max 40 micros), $1.40 a micro (eval views: $1.90).
"""
from __future__ import annotations

import collections
import datetime as dt
import gzip
import hashlib
import itertools
import json
import math
import os
import pickle
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import lit  # noqa: E402

OUT = os.path.join(ROOT, "research", "allday")
CACHE = os.path.join(ROOT, "research", "runs", "_cache")
TICK, PV, COMM = 0.25, 2.0, 1.40
BE_OFF = 1.25
WINS = [  # key, label, start, end (ET minutes of the bar start, end exclusive)
    ("open18", "Evening / Sunday open 18:00-20:00", 1080, 1200),
    ("asia", "Asia 20:00-00:00", 1200, 1440),
    ("late_asia", "Late Asia 00:00-02:00", 0, 120),
    ("lon_open", "London open 02:00-05:00", 120, 300),
    ("london", "London 05:00-08:00", 300, 480),
    ("ny_pre", "NY pre-market 08:00-09:30", 480, 570),
    ("ny_open", "NY open 09:30-11:00", 570, 660),
    ("ny_mid", "NY midday 11:00-13:30", 660, 810),
    ("ny_pm", "NY afternoon 13:30-15:55", 810, 955),
    ("post", "Post-close 16:00-17:00", 960, 1020),
]
WK = [w[0] for w in WINS]
WD = {w[0]: w for w in WINS}
SPANS = {"H1": ("2026-01-01", "2026-06-30"), "H2": ("2026-07-01", "2026-12-31"), "2026": ("2026-01-01", "2026-12-31"),
         "2025": ("2025-01-01", "2025-12-31"), "2021-24": ("2021-01-01", "2024-12-31"), "2021-25": ("2021-01-01", "2025-12-31")}
DOW = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
VIXB = [(0, 16, "<16"), (16, 20, "16-20"), (20, 25, "20-25"), (25, 99, "25+")]


def rel(m):
    """ET minute -> minutes since 18:00 (trading-day order)."""
    return (int(m) - 1080) % 1440


def _dump(obj, path, **kw):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, **kw)
    os.replace(tmp, path)


# ================================================================================================ data
_D = {}


def data():
    """The 5m market (lit.Market: bars, trading days, 5m ATR, per-day context incl. PDH/PDL and the VIX one-day move), the
    1m bars (2026), per-day window bar ranges and the scoring sessions (= run baseline's days, as every LIT study)."""
    if _D:
        return _D
    from tools import lit_final as F
    M = lit.Market()
    B1 = lit.bars_1m(M)
    sess = list(F.SESS)
    sset = set(sess)
    # window bar index ranges per trading day: W[k][w] = (first, last+1) or None
    W = []
    for k, (d, s, e) in enumerate(M.days):
        md = M.mod[s:e]
        rr = (md - 1080) % 1440
        row = {}
        for key, _, a, b in WINS:
            ra, rb = rel(a), rel(b) if b != 1440 else rel(0)
            if rb == 0:
                rb = 1440
            ii = np.flatnonzero((rr >= ra) & (rr < rb))
            row[key] = (int(s + ii[0]), int(s + ii[-1] + 1)) if len(ii) else None
        W.append(row)
    # daily range ATR (mean of the prior 14 trading days' high-low), known at the day start
    dr = np.array([M.h[s:e].max() - M.l[s:e].min() for d, s, e in M.days])
    adr = np.full(len(dr), np.nan)
    for k in range(14, len(dr)):
        adr[k] = dr[k - 14:k].mean()
    # 1m index per 5m bar start (2026 full-coverage days only)
    full = B1.full or set()
    _D.update(M=M, B1=B1, sess=sess, sset=sset, W=W, adr=adr, full=full, dmap={str(d): k for k, (d, s, e) in enumerate(M.days)})
    # session VWAP from 18:00 (typical price x volume), anchored per trading day
    tp = (M.h + M.l + M.c) / 3.0
    v = np.maximum(M.v, 1.0)
    cv = np.zeros(M.n)
    cpv = np.zeros(M.n)
    for d, s, e in M.days:
        cv[s:e] = np.cumsum(v[s:e]); cpv[s:e] = np.cumsum(tp[s:e] * v[s:e])
    _D["vwap"] = cpv / cv                                   # VWAP including bar i (known at bar i's close)
    return _D


def span_of(day):
    for nm in ("H1", "H2", "2025", "2021-24"):
        a, z = SPANS[nm]
        if a <= day <= z:
            return nm
    return None


def vix_bucket(v):
    for a, b, nm in VIXB:
        if a <= v < b:
            return nm
    return "?"


# ================================================================================================ 1. the 24-hour map
def window_box(k, w):
    D = data()
    M = D["M"]
    r = D["W"][k][w] if 0 <= k < len(D["W"]) else None
    if not r:
        return None
    a, b = r
    return float(M.h[a:b].max()), float(M.l[a:b].min()), a, b


def prev_box(k, w):
    """The box of the window before w (the post window of the prior day before open18; ny_pm when post is missing)."""
    j = WK.index(w)
    if j == 0:
        return window_box(k - 1, "post") or window_box(k - 1, "ny_pm")
    return window_box(k, WK[j - 1])


def sweep_stats(M, a, b, hi, lo, a14):
    """Sweeps of a reference box (hi, lo) inside window bars [a, b): per side, swept?, back inside at the window close
    (reversal) or still beyond (continuation), extension beyond the level and move back from the sweep extreme (5m ATRs)."""
    out = {}
    H, L, C = M.h[a:b], M.l[a:b], M.c[b - 1]
    for side, lvl in (("hi", hi), ("lo", lo)):
        hit = np.flatnonzero(H > lvl) if side == "hi" else np.flatnonzero(L < lvl)
        if not len(hit):
            out[side] = None
            continue
        j = int(hit[0])
        if side == "hi":
            ext_i = j + int(np.argmax(H[j:]))
            ext = H[ext_i] - lvl
            back = H[ext_i] - (L[ext_i:].min())
            rev = C < lvl
        else:
            ext_i = j + int(np.argmin(L[j:]))
            ext = lvl - L[ext_i]
            back = (H[ext_i:].max()) - L[ext_i]
            rev = C > lvl
        out[side] = {"rev": bool(rev), "ext": float(ext / a14), "back": float(back / a14), "t": j}
    return out


def build_map():
    D = data()
    M, W, adr = D["M"], D["W"], D["adr"]
    rows = []
    for k, (d, s, e) in enumerate(M.days):
        d = str(d)
        if d not in D["sset"]:
            continue
        x = M.ctx[k]
        vix = x.get("vix")
        for w in WK:
            r = W[k][w]
            if not r or r[1] - r[0] < 3:
                continue
            a, b = r
            a14 = float(M.atr[a - 1]) if a > 0 else float(M.atr[a])
            o, c = float(M.o[a]), float(M.c[b - 1])
            hi, lo = float(M.h[a:b].max()), float(M.l[a:b].min())
            row = {"day": d, "w": w, "dow": int(x["dow"]), "vix": vix, "rng": hi - lo, "rng_adr": (hi - lo) / adr[k] if adr[k] == adr[k] else None,
                   "bar": float(np.mean(M.h[a:b] - M.l[a:b])), "vol": float(np.mean(M.v[a:b])), "up": hi - o, "dn": o - lo,
                   "eff": abs(c - o) / (hi - lo) if hi > lo else 0.0, "net": c - o, "a14": a14, "nb": b - a}
            refs = {}
            pb = prev_box(k, w)
            if pb:
                refs["prev"] = (pb[0], pb[1])
            if a > s + 1:
                refs["sofar"] = (float(M.h[s:a].max()), float(M.l[s:a].min()))
            if x.get("pdh") is not None:
                refs["pd"] = (x["pdh"], x["pdl"])
            for nm, (rh, rl_) in refs.items():
                # only levels still untouched at the window open count (the open is inside the box side)
                st = sweep_stats(M, a, b, rh, rl_, a14)
                for side in ("hi", "lo"):
                    lvl = rh if side == "hi" else rl_
                    live = (o < lvl) if side == "hi" else (o > lvl)
                    row[f"{nm}_{side}"] = st[side] if live else "na"
            # DOL reach from the window open: VIX band edges (18:00 open +/- 1 VIX day move) and the prior day high / low
            vm = x.get("vix_move")
            if vm:
                up_b, dn_b = x["open18"] + vm, x["open18"] - vm
                row["vix_up"] = bool(hi >= up_b) if o < up_b else "na"
                row["vix_dn"] = bool(lo <= dn_b) if o > dn_b else "na"
                row["rng_vix"] = (hi - lo) / vm
            rows.append(row)
    return rows


def summarize_map(rows, key=None):
    """Per window (and an optional split key): volatility, sweeps, reversal vs continuation, DOL reach."""
    G = collections.defaultdict(list)
    for r in rows:
        G[(r["w"],) + ((key(r),) if key else ())].append(r)
    out = {}
    for g, R in sorted(G.items(), key=lambda kv: (WK.index(kv[0][0]),) + kv[0][1:]):
        o = {"n": len(R), "rng_med": round(float(np.median([r["rng"] for r in R])), 1),
             "rng_mean": round(float(np.mean([r["rng"] for r in R])), 1),
             "rng_adr": round(float(np.nanmedian([r["rng_adr"] for r in R if r["rng_adr"] is not None])), 3),
             "rng_vix": round(float(np.median([r["rng_vix"] for r in R if r.get("rng_vix")])), 3) if any(r.get("rng_vix") for r in R) else None,
             "bar_med": round(float(np.median([r["bar"] for r in R])), 2),
             "pts_hr": round(float(np.median([r["rng"] / (r["nb"] / 12.0) for r in R])), 1),
             "vol": round(float(np.mean([r["vol"] for r in R]))),
             "eff": round(float(np.median([r["eff"] for r in R])), 3),
             "trend_pct": round(100.0 * np.mean([r["eff"] >= 0.6 for r in R]), 1),
             "move_med": round(float(np.median([max(r["up"], r["dn"]) for r in R])), 1)}
        for nm in ("prev", "sofar", "pd"):
            sw = [r[f"{nm}_{sd}"] for r in R for sd in ("hi", "lo") if f"{nm}_{sd}" in r and r[f"{nm}_{sd}"] != "na"]
            nlive = sum(1 for r in R for sd in ("hi", "lo") if f"{nm}_{sd}" in r and r[f"{nm}_{sd}"] != "na") + \
                sum(1 for r in R for sd in ("hi", "lo") if r.get(f"{nm}_{sd}") is None and f"{nm}_{sd}" in r)
            S = [x for x in sw if x]
            nall = sum(1 for r in R for sd in ("hi", "lo") if f"{nm}_{sd}" in r and r[f"{nm}_{sd}"] != "na")
            if nall:
                o[f"{nm}_swept"] = round(100.0 * len(S) / nall, 1)
                if S:
                    o[f"{nm}_rev"] = round(100.0 * np.mean([x["rev"] for x in S]), 1)
                    o[f"{nm}_ext"] = round(float(np.median([x["ext"] for x in S])), 2)
                    o[f"{nm}_back"] = round(float(np.median([x["back"] for x in S])), 2)
                    # clean reversal: back inside AND it moved back >= 3 x the 5m ATR from the sweep extreme
                    o[f"{nm}_rev3"] = round(100.0 * np.mean([x["rev"] and x["back"] >= 3 for x in S]), 1)
            del nlive
        for side in ("vix_up", "vix_dn"):
            v = [r[side] for r in R if side in r and r[side] != "na"]
            if v:
                o[side] = round(100.0 * np.mean(v), 1)
        out["|".join(str(x) for x in g)] = o
    return out


def cmd_map():
    rows = build_map()
    out = {"built": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "windows": [{"key": k, "label": l, "from": a, "to": b} for k, l, a, b in WINS],
           "notes": {"rng": "window high - low, pts (median)", "rng_adr": "window range / the prior 14 days' mean daily range",
                     "rng_vix": "window range / the VIX one-day move (the LIT target band)", "bar_med": "median 5m bar range, pts",
                     "pts_hr": "range per hour of window, pts", "eff": "|close - open| / range (1 = one straight move)",
                     "trend_pct": "% of windows with eff >= 0.6", "move_med": "median max excursion from the window open, pts",
                     "X_swept": "% of untouched X levels (each side) traded through in the window; X = prev (the window before), "
                                "sofar (the trading day's high/low before the window), pd (prior day high/low)",
                     "X_rev": "% of those sweeps where the window closes back inside the level (reversal) - the rest closed "
                              "beyond it (continuation)", "X_rev3": "% of sweeps that reversed AND moved back >= 3 x 5m ATR",
                     "X_ext": "median extension beyond the level (5m ATRs)", "X_back": "median move back from the sweep extreme (5m ATRs)",
                     "vix_up/vix_dn": "% of windows (opening inside the band) reaching the VIX band edge (LIT's target)"}}
    for nm, sp in (("2026", ("2026-01-01", "2026-12-31")), ("2021-25", ("2021-01-01", "2025-12-31")), ("all", ("2000", "2100"))):
        R = [r for r in rows if sp[0] <= r["day"] <= sp[1]]
        out[nm] = summarize_map(R)
        out[nm + "_dow"] = summarize_map(R, lambda r: DOW[r["dow"]])
        out[nm + "_vix"] = summarize_map([r for r in R if r["vix"]], lambda r: vix_bucket(r["vix"]))
    _dump(out, os.path.join(OUT, "map.json"), indent=1)
    show_map(out)
    return out


def show_map(out=None):
    out = out or json.load(open(os.path.join(OUT, "map.json")))
    for nm in ("2026", "2021-25"):
        print(f"\n== {nm}")
        print(f"{'window':10s} {'rng':>6s} {'%adr':>5s} {'xvix':>5s} {'bar':>5s} {'eff':>5s} {'trd%':>5s} | prev sw/rev/rev3 | sofar sw/rev | pd sw/rev | vix up/dn")
        for w in WK:
            o = out[nm].get(w)
            if not o:
                continue
            g = lambda k: o.get(k, "-")  # noqa: E731
            print(f"{w:10s} {o['rng_med']:6.1f} {o['rng_adr']:5.2f} {g('rng_vix')!s:>5s} {o['bar_med']:5.1f} {o['eff']:5.2f} {o['trend_pct']:5.1f} | "
                  f"{g('prev_swept')}/{g('prev_rev')}/{g('prev_rev3')} | {g('sofar_swept')}/{g('sofar_rev')} | {g('pd_swept')}/{g('pd_rev')} | "
                  f"{g('vix_up')}/{g('vix_dn')}")


# ================================================================================================ 2b. own families: execution
def flat_rel(w, hold):
    """Trading-day minute (since 18:00) of the time exit: 'w' = window end + 60 min, 'eod' = 15:55; never after 15:55."""
    _, _, a, b = WD[w]
    end = rel(b)
    if b == 1440:
        end = 360
    if hold == "w":
        return min(end + 60, rel(955))
    return rel(955)


def path(k, i_entry, w, hold):
    """Bars a trade entering at the open of 5m bar i_entry lives on, up to its time exit: true 1m bars on 2026 days with
    full 1m coverage, else 5m. Returns (t, o, h, l, c, bar seconds)."""
    D = data()
    M, B1 = D["M"], D["B1"]
    d, s, e = M.days[k]
    t0 = int(M.t[i_entry])
    tf = int(M.t[s]) + (flat_rel(w, hold) - rel(M.mod[s])) * 60
    if k in D["full"]:
        a = int(np.searchsorted(B1.t, t0))
        z = int(np.searchsorted(B1.t, tf))
        if z > a and int(B1.t[a]) == t0:
            return B1.t[a:z], B1.o[a:z], B1.h[a:z], B1.l[a:z], B1.c[a:z], 60
    z = min(e, int(np.searchsorted(M.t, tf)))
    return M.t[i_entry:z], M.o[i_entry:z], M.h[i_entry:z], M.l[i_entry:z], M.c[i_entry:z], 300


def _first(mask, start=0):
    j = np.flatnonzero(mask[start:])
    return int(j[0]) + start if len(j) else len(mask)


def simulate(c, exits):
    """One candidate c (k, i = signal bar, dir, stop px, structural target px or None, w) through a list of exit configs
    (tgt: 'R1' | 'R1.5' | 'R2' | 'R3' | 'S' = the setup's structural target (>= 1R, banked at 8R); be: None | R; hold: 'w' |
    'eod'). Returns {exit cfg: trade or None}; trade in the common format + per-micro points (pts), worst open points (w1)."""
    M = data()["M"]
    d, i = c["dir"], c["i"]
    if i + 1 >= M.n or M.day_of[i + 1] != c["k"]:
        return {}
    out, cache = {}, {}
    for ex in exits:
        tgt, be, hold = ex
        if hold not in cache:
            cache[hold] = path(c["k"], i + 1, c["w"], hold)
        T, O, H, L, C, secs = cache[hold]
        if len(T) == 0:
            out[ex] = None
            continue
        if d == 1:
            o, h, l, cl = O, H, L, C
        else:
            o, h, l, cl = -O, -L, -H, -C
        e = float(o[0]) + TICK                       # market entry: next open + 1 tick
        sp = c["stop"] * d
        risk = e - sp
        if not (6.0 <= risk <= 80.0):
            out[ex] = None
            continue
        if tgt == "S":
            if c.get("tgt") is None:
                out[ex] = None
                continue
            tg = c["tgt"] * d
            if tg - e < 1.0 * risk:
                out[ex] = None
                continue
            tg = min(tg, e + 8.0 * risk)
        else:
            tg = e + float(tgt[1:]) * risk
        n = len(l)
        s0 = _first(l <= sp)
        tt = _first(h >= tg + TICK)
        b = _first(h >= e + be * risk) if be else n
        bes = e + BE_OFF
        s_pre = s0 if s0 <= b else n
        s_post = _first(l <= bes, b + 1) if (b < n and s_pre == n) else n
        si = s_pre if s_pre < n else s_post
        if si <= tt and si < n:
            j = si
            lv = sp if si == s_pre else bes
            px, kind = min(float(o[j]), lv) - TICK, ("STOP" if si == s_pre else "BE")
        elif tt < n:
            j = tt
            px, kind = max(float(o[j]), tg), "TARGET"
        else:
            j = n - 1
            px, kind = float(cl[j]) - TICK, "TIME"
        pts = px - e
        w1 = float(min(0.0, l[:j + 1].min() - e))
        if kind != "TIME":
            w1 = max(w1, -(risk + TICK))
        q = lit.qty_for(risk)
        if q <= 0:
            out[ex] = None
            continue
        pnl = (pts * PV - COMM) * q
        out[ex] = {"day": c["day"], "entry_t": int(T[0]), "exit_t": int(T[j]) + secs, "dir": d, "entry": round(e * d, 2),
                   "stop": round(sp * d, 2), "target": round(tg * d, 2), "exit": round(px * d, 2), "exit_kind": kind,
                   "r": round(pts / risk, 3), "qty": q, "pnl_usd": round(pnl, 2), "setup": c["setup"], "risk": round(risk, 2),
                   "pts": round(pts, 4), "w1": round(w1, 4), "tgt_pts": round(tg - e, 2), "w": c["w"]}
    return out


# ================================================================================================ 2b. own families: signals
def _dirs(M, d):
    """Direction-space views of the 5m arrays (a short is a long on the negated prices)."""
    if d == 1:
        return M.o, M.h, M.l, M.c
    return -M.o, -M.l, -M.h, -M.c


def win_len(w):
    _, _, a, b = WD[w]
    return (b - a) % 1440


def ref_box(k, w, ref):
    """A reference box known at the window open: (hi or None, lo or None, first bar it may be swept on)."""
    D = data()
    M = D["M"]
    r = D["W"][k][w]
    if not r:
        return None
    a, b = r
    d, s, e = M.days[k]
    if ref == "prev":
        pb = prev_box(k, w)
        return (pb[0], pb[1], a) if pb else None
    if ref == "sofar":
        return (float(M.h[s:a].max()), float(M.l[s:a].min()), a) if a > s + 1 else None
    if ref == "pd":
        x = M.ctx[k]
        if x.get("pdh") is None:
            return None
        hi, lo = x["pdh"], x["pdl"]
        if a > s:                                    # only if not taken earlier in the trading day
            hi = hi if M.h[s:a].max() < hi else None
            lo = lo if M.l[s:a].min() > lo else None
        return (hi, lo, a)
    if ref.startswith("or"):                         # the window's own opening range (or15 / or30), from its end
        m = int(ref[2:]) // 5
        if b - a < m + 3:
            return None
        return (float(M.h[a:a + m].max()), float(M.l[a:a + m].min()), a + m)
    raise ValueError(ref)


def gen_reclaim(w, ref, depth, nconf, conf):
    """Sweep-and-reclaim: price trades through a box side (by >= depth x 5m ATR), then a 5m close back inside the box within
    nconf bars (conf 'close'; 'cisd' = that close is also beyond the open of the candle run that made the extreme). Short at a
    high sweep, long at a low sweep. Stop 1 tick beyond the sweep extreme; structural target = the box's other side."""
    D = data()
    M = D["M"]
    C = []
    for k, (d, s, e) in enumerate(M.days):
        d = str(d)
        if d not in D["sset"]:
            continue
        r = D["W"][k][w]
        bx = ref_box(k, w, ref)
        if not r or not bx:
            continue
        a, b = r
        hi, lo, f = bx
        best = None
        for lvl, dr in ((hi, -1), (lo, 1)):
            if lvl is None or f < 1:
                continue
            o_, h_, l_, c_ = _dirs(M, dr)            # trade space: a high sweep (short) is a low sweep of the negated prices
            L = lvl * dr
            ii = np.flatnonzero(l_[f:b] < L - depth * M.atr[f - 1]) + f
            if not len(ii):
                continue
            j = int(ii[0])
            for m in range(j, min(b - 1, j + nconf + 1)):
                if c_[m] > L:                        # closed back inside the box
                    ext = int(j + np.argmin(l_[j:m + 1]))
                    if conf == "cisd":
                        q = ext
                        while q > a and c_[q - 1] < o_[q - 1]:
                            q -= 1                   # first candle of the run into the extreme
                        if not c_[m] > o_[q]:
                            continue
                    tgt = hi if dr == 1 else lo
                    cand = {"k": k, "day": d, "i": m, "dir": dr, "stop": float((l_[ext] - TICK) * dr),
                            "tgt": float(tgt) if tgt is not None else None, "w": w,
                            "setup": f"reclaim of the {ref} {'high' if dr == -1 else 'low'} ({WD[w][1]})"}
                    if best is None or m < best["i"]:
                        best = cand
                    break
        if best:
            C.append(best)
    return C


def gen_orb(w, orm, stopm):
    """Opening-range breakout: the first 5m close beyond the window's first orm minutes' range -> trade that way. Stop at
    the other side of the range ('opp') or 1 tick beyond the breakout candle ('bar'). No structural target (R)."""
    D = data()
    M = D["M"]
    C = []
    m0 = orm // 5
    for k, (d, s, e) in enumerate(M.days):
        d = str(d)
        if d not in D["sset"]:
            continue
        r = D["W"][k][w]
        if not r or r[1] - r[0] < m0 + 3:
            continue
        a, b = r
        hi, lo = float(M.h[a:a + m0].max()), float(M.l[a:a + m0].min())
        for m in range(a + m0, b - 1):
            dr = 1 if M.c[m] > hi else (-1 if M.c[m] < lo else 0)
            if dr:
                if stopm == "opp":
                    stop = lo - TICK if dr == 1 else hi + TICK
                else:
                    stop = M.l[m] - TICK if dr == 1 else M.h[m] + TICK
                C.append({"k": k, "day": d, "i": m, "dir": dr, "stop": float(stop), "tgt": None, "w": w,
                          "setup": f"ORB {orm}m breakout ({WD[w][1]})"})
                break
    return C


def gen_mr(w, anchor, kk):
    """Mean reversion: price stretched >= kk x 5m ATR away from the anchor (the 18:00 session VWAP or the window open), then
    a 5m close beyond the prior candle's high (long) / low (short), still on the stretched side -> trade back toward the
    anchor. Stop 1 tick beyond the lowest low / highest high of the last 6 candles; structural target = the anchor."""
    D = data()
    M = D["M"]
    V = D["vwap"]
    C = []
    for k, (d, s, e) in enumerate(M.days):
        d = str(d)
        if d not in D["sset"]:
            continue
        r = D["W"][k][w]
        if not r or r[1] - r[0] < 4:
            continue
        a, b = r
        wo = float(M.o[a])
        for m in range(a + 2, b - 1):
            anc = float(V[m]) if anchor == "vwap" else wo
            at = float(M.atr[m])
            lo6, hi6 = float(M.l[max(a, m - 5):m + 1].min()), float(M.h[max(a, m - 5):m + 1].max())
            dr = 0
            if anc - lo6 >= kk * at and M.c[m] > M.h[m - 1] and M.c[m] < anc:
                dr, stop = 1, lo6 - TICK
            elif hi6 - anc >= kk * at and M.c[m] < M.l[m - 1] and M.c[m] > anc:
                dr, stop = -1, hi6 + TICK
            if dr:
                C.append({"k": k, "day": d, "i": m, "dir": dr, "stop": float(stop), "tgt": anc, "w": w,
                          "setup": f"mean reversion to the {'session VWAP' if anchor == 'vwap' else 'window open'} ({WD[w][1]})"})
                break
    return C


def gen_cont(w, src, eff, pb):
    """Continuation: the window before ('prev') or the trading day so far ('sofar') moved one way (|close - open| >= eff x
    its range, range >= 0.15 x the 14-day mean daily range); in this window price pulls back >= pb x that range from the
    move's extreme, then a 5m close beyond the prior candle's high (long) / low (short) -> trade with the move. Stop 1 tick
    beyond the pullback's extreme; structural target = the move's extreme (high since the move began)."""
    D = data()
    M, adr = D["M"], D["adr"]
    C = []
    for k, (d, s, e) in enumerate(M.days):
        d = str(d)
        if d not in D["sset"]:
            continue
        r = D["W"][k][w]
        if not r or r[1] - r[0] < 4 or adr[k] != adr[k]:
            continue
        a, b = r
        if src == "prev":
            j = WK.index(w)
            pr = D["W"][k][WK[j - 1]] if j > 0 else None
            if not pr:
                continue
            pa, pz = pr
        else:
            pa, pz = s, a
        if pz - pa < 3:
            continue
        ph, pl = float(M.h[pa:pz].max()), float(M.l[pa:pz].min())
        rg = ph - pl
        mv = float(M.c[pz - 1] - M.o[pa])
        if rg < 0.15 * adr[k] or abs(mv) < eff * rg:
            continue
        dr = 1 if mv > 0 else -1
        o_, h_, l_, c_ = _dirs(M, dr)
        hh = ph if dr == 1 else -pl                  # the move's extreme in trade space
        pulled, low_i = False, -1
        for m in range(a, b - 1):
            hh = max(hh, float(h_[m]))
            if not pulled and l_[m] <= hh - pb * rg:
                pulled, low_i = True, m
            if pulled:
                if l_[m] < l_[low_i]:
                    low_i = m
                if m > a and c_[m] > h_[m - 1]:
                    stop = (float(l_[low_i:m + 1].min()) - TICK) * dr
                    C.append({"k": k, "day": d, "i": m, "dir": dr, "stop": float(stop), "tgt": float(hh * dr), "w": w,
                              "setup": f"continuation after the {'prior window' if src == 'prev' else 'day so far'} ({WD[w][1]})"})
                    break
    return C


# grids (generators x exits); the post window is mapped only (MFFU flat 16:10)
TRADE_W = [w for w in WK if w != "post"]
EX_R = [(t, be, h) for t in ("R1.5", "R2", "R3") for be in (None, 1.0) for h in ("w", "eod")]
EX_S = EX_R + [("S", be, h) for be in (None, 1.0) for h in ("w", "eod")]
EX_MR = [(t, be, h) for t in ("S", "R1", "R1.5") for be in (None, 1.0) for h in ("w", "eod")]
GEN = {"reclaim": gen_reclaim, "orb": gen_orb, "mr": gen_mr, "cont": gen_cont}
EXITS = {"reclaim": EX_S, "orb": EX_R, "mr": EX_MR, "cont": EX_S}
GRID = {"reclaim": {"ref": None, "depth": (0.0, 0.5), "nconf": (3, 6), "conf": ("close", "cisd")},
        "orb": {"orm": (15, 30), "stopm": ("opp", "bar")},
        "mr": {"anchor": ("vwap", "wopen"), "kk": (1.5, 2.5, 3.5)},
        "cont": {"src": ("prev", "sofar"), "eff": (0.5, 0.65), "pb": (0.25, 0.4)}}


def refs_of(w):
    if w == "open18":
        return ["prev", "pd", "or30"]
    return ["prev", "sofar", "pd"] + (["or30"] if win_len(w) >= 90 else [])


def fam_jobs():
    J = []
    for w in TRADE_W:
        for g in itertools.product(refs_of(w), *[GRID["reclaim"][x] for x in ("depth", "nconf", "conf")]):
            J.append(("reclaim", w, g))
        for g in itertools.product(*GRID["orb"].values()):
            J.append(("orb", w, g))
        for g in itertools.product(*GRID["mr"].values()):
            J.append(("mr", w, g))
        for g in itertools.product(*GRID["cont"].values()):
            if w == "open18" and g[0] == "sofar":
                continue
            J.append(("cont", w, g))
    return J


def vkey(fam, w, g, ex):
    return f"{fam}|{w}|{','.join(str(x) for x in g)}|{ex[0]},{ex[1]},{ex[2]}"


def parse_key(key):
    fam, w, g, ex = key.split("|")
    return fam, w, g.split(","), ex.split(",")


def _fam_job(job):
    fam, w, g = job
    cands = GEN[fam](w, *g)
    res = collections.defaultdict(list)
    for c in cands:
        for ex, t in simulate(c, EXITS[fam]).items():
            if t is not None:
                res[ex].append(t)
    return {vkey(fam, w, g, ex): res.get(ex, []) for ex in EXITS[fam]}


def stats(T, span, sessions=None):
    """Money at the LIT size (costs in) for one span: trades, a week, win %, clean win % (>= +0.5R), PF, net $, $/month,
    max DD, sum of R."""
    D = data()
    a, z = SPANS[span]
    ss = [x for x in (sessions or D["sess"]) if a <= x <= z]
    TT = [t for t in T if a <= t["day"] <= z]
    nw = max(1.0, len(ss) / 5.0)
    if not TT:
        return {"n": 0, "tpw": 0.0, "net": 0, "pf": None, "win": None, "sumr": 0.0, "per_month": 0, "dd": 0}
    p = np.array([t["pnl_usd"] for t in TT])
    r = np.array([t["r"] for t in TT])
    gl = -p[p < 0].sum()
    eq = np.cumsum(p)
    dd = float((eq - np.maximum.accumulate(np.r_[0.0, eq])[1:]).min())
    return {"n": len(TT), "tpw": round(len(TT) / nw, 2), "win": round(100.0 * float((p > 0).mean()), 1),
            "cwin": round(100.0 * float((r >= 0.5).mean()), 1), "pf": round(float(p[p > 0].sum() / gl), 2) if gl > 0 else 99.0,
            "net": round(float(p.sum())), "per_month": round(float(p.sum()) / max(1.0, len(ss) / 21.0)), "dd": round(dd),
            "sumr": round(float(r.sum()), 2), "avg_r": round(float(r.mean()), 3)}


FAM_PKL = os.path.join(CACHE, "allday_fam_trades.pkl")


def cmd_fam(procs=4):
    from multiprocessing import Pool
    data()
    J = fam_jobs()
    print(len(J), "generator jobs", flush=True)
    t0 = time.time()
    out = {}
    with Pool(procs) as pool:
        for i, R in enumerate(pool.imap_unordered(_fam_job, J, chunksize=2)):
            out.update(R)
            if i % 50 == 0:
                print(f"  {i}/{len(J)} {time.time() - t0:.0f}s", flush=True)
    pickle.dump(out, open(FAM_PKL, "wb"))
    S = {key: {sp: stats(T, sp) for sp in ("H1", "H2", "2025", "2021-24")} for key, T in out.items()}
    _dump(S, os.path.join(OUT, "fam_grid.json"), separators=(",", ":"))
    print(len(S), "variants", f"{time.time() - t0:.0f}s", flush=True)
    return S


# ================================================================================================ 2a. LIT's chain per window
LIT_PKL = os.path.join(CACHE, "allday_lit_trades.pkl")
LIT_GRID = {"depth": (0.3, 0.5, 0.75, 1.0), "disp": (0.6, 0.8, 1.0, 1.2), "max_rr": (2.0, 3.0, 5.0, 8.0), "be_r": (1.0, 1.5)}


def lit_live():
    return {**lit.DEFAULTS, **json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))["lit"]}


def lit_P(w, depth=0.5, disp=0.8, max_rr=8.0, be_r=1.0, extra=None):
    """The live LIT (t_check, be_off, Monday rule, weekly stop, 1m CISD entries) with its entries limited to window w and
    that window's own sweep depth / displacement / bank / breakeven; evening windows use the all-hours executor."""
    _, _, a, b = WD[w]
    P = {**lit_live(), "window": [[a, b]], "depth": depth, "disp": disp, "max_rr": max_rr, "be_r": be_r}
    if a >= 1080:
        P["all_hours"] = True
    P.update(extra or {})
    return P


def lit_run(P):
    from tools import lit_all_hours as AH
    return AH.run(P)


def lit_common(T, setup="LIT"):
    """engine/lit.py run_x trades -> the common format (exit price from the trade's points incl. slippage)."""
    out = []
    for t in T:
        q = int(t["qty"])
        pts = (t["pnl"] / q + lit.COMM) / lit.PV if q else 0.0
        e = float(t["entry_px"])
        out.append({"day": t["day"], "entry_t": int(t["entry_t"]), "exit_t": int(t["exit_t"]), "dir": int(t["dir"]), "entry": e,
                    "stop": float(t["stop_px"]), "target": float(t["target_px"]), "exit": round(e + t["dir"] * pts, 2),
                    "exit_kind": t["exit"], "r": float(t["r"]), "qty": q, "pnl_usd": round(float(t["pnl"]), 2), "setup": setup,
                    "risk": float(t["risk_pts"]), "pts": round(pts, 4), "_raw": t})
    return out


def lit_mod_of(t):
    x = dt.datetime.fromtimestamp(int(t["entry_t"]), dt.timezone.utc).astimezone(__import__("zoneinfo").ZoneInfo("America/New_York"))
    return x.hour * 60 + x.minute


def win_of_mod(m):
    for k, _, a, b in WINS:
        if a <= m < b:
            return k
    return None


def cmd_lit():
    t0 = time.time()
    out = {}
    base = lit_common(lit_run(lit_live()), "LIT live")
    out["lit|live|base"] = base
    for w in TRADE_W:
        for depth, disp, mrr, be in itertools.product(*LIT_GRID.values()):
            key = f"lit|{w}|{depth},{disp},{mrr},{be}"
            out[key] = lit_common(lit_run(lit_P(w, depth, disp, mrr, be)), f"LIT ({WD[w][1]})")
        print(f"  {w} {time.time() - t0:.0f}s", flush=True)
    slim = {k: [{kk: vv for kk, vv in t.items() if kk != "_raw"} for t in T] for k, T in out.items()}
    pickle.dump(slim, open(LIT_PKL, "wb"))
    S = {key: {sp: stats(T, sp) for sp in ("H1", "H2", "2025", "2021-24")} for key, T in slim.items()}
    # the live LIT's own trades split by window (where LIT already trades)
    split = {}
    for w in WK:
        TT = [t for t in base if win_of_mod(lit_mod_of(t)) == w]
        split[w] = {sp: stats(TT, sp) for sp in ("H1", "H2", "2025", "2021-24")}
    S["_live_split"] = split
    _dump(S, os.path.join(OUT, "lit_grid.json"), separators=(",", ":"))
    print(len(S), "LIT variants", f"{time.time() - t0:.0f}s", flush=True)
    return S


# ================================================================================================ 3. picks, checks, placebo
CHECK_SPANS = ("H1", "H2", "2025", "2021-24")
_T = {}


def all_trades():
    """Every variant's trades: the own families (FAM_PKL) + LIT per window (LIT_PKL)."""
    if not _T:
        _T.update(pickle.load(open(FAM_PKL, "rb")))
        _T.update(pickle.load(open(LIT_PKL, "rb")))
    return _T


def grids():
    S = json.load(open(os.path.join(OUT, "fam_grid.json")))
    L = json.load(open(os.path.join(OUT, "lit_grid.json")))
    L.pop("_live_split", None)
    L.pop("lit|live|base", None)
    S.update(L)
    return S


def dims(key):
    """A variant key -> (family, window, tuple of parameter values) for neighbour search."""
    p = key.split("|")
    fam, w = p[0], p[1]
    vals = p[2].split(",") + (p[3].split(",") if len(p) > 3 else [])
    return fam, w, tuple(vals)


ORDER = {  # the ordered values of every parameter position (neighbours = one step in one position)
    "reclaim": [None, ["0.0", "0.5"], ["3", "6"], ["close", "cisd"], ["R1.5", "R2", "R3", "S"], ["None", "1.0"], ["w", "eod"]],
    "orb": [["15", "30"], ["opp", "bar"], ["R1.5", "R2", "R3"], ["None", "1.0"], ["w", "eod"]],
    "mr": [["vwap", "wopen"], ["1.5", "2.5", "3.5"], ["S", "R1", "R1.5"], ["None", "1.0"], ["w", "eod"]],
    "cont": [["prev", "sofar"], ["0.5", "0.65"], ["0.25", "0.4"], ["R1.5", "R2", "R3", "S"], ["None", "1.0"], ["w", "eod"]],
    "lit": [["0.3", "0.5", "0.75", "1.0"], ["0.6", "0.8", "1.0", "1.2"], ["2.0", "3.0", "5.0", "8.0"], ["1.0", "1.5"]],
}


def neighbours(key, by):
    fam, w, v = dims(key)
    out = []
    for o in by[(fam, w)]:
        _, _, u = dims(o)
        diff = [j for j in range(len(v)) if u[j] != v[j]]
        if len(diff) != 1:
            continue
        j = diff[0]
        seq = ORDER[fam][j]
        if seq is None or (u[j] in seq and v[j] in seq and abs(seq.index(u[j]) - seq.index(v[j])) == 1):
            out.append(o)
    return out


def eligible(s, mode):
    if s["n"] < 8 or s["net"] <= 0 or (s["pf"] or 0) < 1.3:
        return False
    return mode != "win" or (s["win"] or 0) >= 50.0


def pick_all(S=None, on="H1", min_n=8):
    """Per window x family: the H1 pick (plateau score = half its own H1 $ + half the median H1 $ of its one-step
    neighbours), two modes: 'win' (win % >= 50, as the owner asked) and 'money' (no win-rate floor). Nothing after H1 is
    looked at to pick. on='2021-24' (min_n 30): the long-sample view (pick on 4 years, check 2025 and both 2026 halves)."""
    S = S or grids()
    if on != "H1":
        S = {k: {**v, "H1": v[on], "_h1": v["H1"]} for k, v in S.items()}
        S = {k: v for k, v in S.items() if v["H1"]["n"] >= min_n}
    by = collections.defaultdict(list)
    for k in S:
        f, w, _ = dims(k)
        by[(f, w)].append(k)
    picks = {}
    for (f, w), keys in sorted(by.items(), key=lambda kv: (WK.index(kv[0][1]), kv[0][0])):
        for mode in ("win", "money"):
            best, bs = None, None
            for k in keys:
                if not eligible(S[k]["H1"], mode):
                    continue
                nb = neighbours(k, by)
                med = float(np.median([S[o]["H1"]["net"] for o in nb])) if nb else 0.0
                sc = 0.5 * S[k]["H1"]["net"] + 0.5 * med
                if bs is None or sc > bs:
                    best, bs = k, sc
            if best:
                nb = neighbours(best, by)
                picks[f"{f}|{w}|{mode}"] = {"key": best, "fam": f, "w": w, "mode": mode, "plateau_h1": round(bs),
                                             "n_variants": len(keys), "n_eligible": sum(1 for k in keys if eligible(S[k]["H1"], mode)),
                                             "nb_n": len(nb), "nb_h1_med": round(float(np.median([S[o]["H1"]["net"] for o in nb]))) if nb else None,
                                             "nb_h2_med": round(float(np.median([S[o]["H2"]["net"] for o in nb]))) if nb else None,
                                             "nb_h2_pos": f"{sum(1 for o in nb if S[o]['H2']['net'] > 0)}/{len(nb)}",
                                             "spans": {s: S[best][s] for s in CHECK_SPANS}}
    return picks


def months(T, a="2026-01-01", z="2026-12-31"):
    m = collections.defaultdict(lambda: [0, 0.0, 0])
    for t in T:
        if a <= t["day"] <= z:
            x = m[t["day"][:7]]
            x[0] += 1; x[1] += t["pnl_usd"]; x[2] += t["pnl_usd"] > 0
    return {k: {"n": v[0], "net": round(v[1]), "wins": v[2]} for k, v in sorted(m.items())}


def exit_of(key):
    """The exit config of a variant key (LIT: its own bank / breakeven, simulated with the trade's own target R)."""
    fam, w, v = dims(key)
    if fam == "lit":
        return ("S", float(v[3]), "eod")
    t, be, h = v[-3:]
    return (t, None if be == "None" else float(be), h)


def placebo(key, T, span, n_draw=300, seed=7):
    """Random entries in the same window and span: the same number of trades, the same long/short mix, stop distances and
    target R drawn from the pick's own trades, the same exit rule (breakeven, time exit). Returns the share of random draws
    that do at least as well as the pick (net $; and win % + PF), and the random spread."""
    D = data()
    M = D["M"]
    a_, z_ = SPANS[span]
    TT = [t for t in T if a_ <= t["day"] <= z_]
    if len(TT) < 3:
        return None
    fam, w, _ = dims(key)
    tg, be, hold = exit_of(key)
    days = [d for d in D["sess"] if a_ <= d <= z_]
    rng = np.random.default_rng(seed + int(hashlib.md5(key.encode()).hexdigest()[:6], 16) % 1000)
    risks = np.array([t["risk"] for t in TT])
    rr = np.array([abs(t["target"] - t["entry"]) / t["risk"] for t in TT])
    pl = float(np.mean([t["dir"] == 1 for t in TT]))
    nets, wins, pfs = [], [], []
    ex = (tg, be, hold) if tg != "S" else ("S", be, hold)
    for _ in range(n_draw):
        P = []
        for _j in range(len(TT)):
            for _try in range(20):
                d = days[int(rng.integers(len(days)))]
                k = D["dmap"][d]
                r = D["W"][k][w]
                if not r or r[1] - r[0] < 3:
                    continue
                m = int(rng.integers(r[0], r[1] - 1))
                dr = 1 if rng.random() < pl else -1
                q = int(rng.integers(len(TT)))
                e0 = float(M.o[m + 1]) + TICK * dr
                c = {"k": k, "day": d, "i": m, "dir": dr, "stop": e0 - dr * float(risks[q]), "tgt": e0 + dr * float(rr[q] * risks[q]),
                     "w": w, "setup": "placebo"}
                t = simulate(c, [ex]).get(ex)
                if t is not None:
                    P.append(t)
                    break
        p = np.array([t["pnl_usd"] for t in P])
        gl = -p[p < 0].sum()
        nets.append(float(p.sum())); wins.append(100.0 * float((p > 0).mean())); pfs.append(float(p[p > 0].sum() / gl) if gl > 0 else 99.0)
    s = stats(T, span)
    nets, wins, pfs = np.array(nets), np.array(wins), np.array(pfs)
    return {"span": span, "n": len(TT), "draws": n_draw, "p_net": round(float((nets >= s["net"]).mean()), 3),
            "p_win_pf": round(float(((wins >= s["win"]) & (pfs >= s["pf"])).mean()), 3),
            "rand_net_p50": round(float(np.median(nets))), "rand_net_p90": round(float(np.percentile(nets, 90))),
            "rand_win_p50": round(float(np.median(wins)), 1)}


def chance_rate(n_strat=150, seed=3):
    """How often a random-entry strategy (random bar of a window, random side, the stop / target / exit rule of a random
    family variant of that window) is positive in all four spans: the chance level for 'positive everywhere'."""
    S = grids()
    T = all_trades()
    rng = np.random.default_rng(seed)
    keys = [k for k in S if not k.startswith("lit") and S[k]["H1"]["n"] >= 8]
    hits, n = 0, 0
    D = data()
    M = D["M"]
    for _ in range(n_strat):
        k = keys[int(rng.integers(len(keys)))]
        TT = T[k]
        if len(TT) < 20:
            continue
        _, w, _ = dims(k)
        ex = exit_of(k)
        risks = np.array([t["risk"] for t in TT]); rr = np.array([abs(t["target"] - t["entry"]) / t["risk"] for t in TT])
        R = []
        for t in TT:                                 # one random trade per pick trade, same span (same day count)
            d = t["day"]
            kk = D["dmap"][d]
            r = D["W"][kk][w]
            m = int(rng.integers(r[0], r[1] - 1))
            dr = 1 if rng.random() < 0.5 else -1
            q = int(rng.integers(len(TT)))
            e0 = float(M.o[m + 1]) + TICK * dr
            c = {"k": kk, "day": d, "i": m, "dir": dr, "stop": e0 - dr * float(risks[q]), "tgt": e0 + dr * float(rr[q] * risks[q]),
                 "w": w, "setup": "chance"}
            x = simulate(c, [ex]).get(ex)
            if x:
                R.append(x)
        n += 1
        hits += all(stats(R, s)["net"] > 0 for s in CHECK_SPANS)
    return {"strategies": n, "positive_all_4": hits, "rate": round(hits / max(1, n), 4)}


def verdict(p, fam):
    s = p["spans"]
    h2 = s["H2"]
    ok_h2 = h2["n"] >= 4 and h2["net"] > 0 and (h2["pf"] or 0) >= 1.2
    ok_win = (h2["win"] or 0) >= 50.0 if p["mode"] == "win" else True
    ok_ref = s["2025"]["net"] > 0 and s["2021-24"]["net"] > 0
    pl = p.get("placebo_H2") or {}
    ok_pl = pl.get("p_net", 1.0) <= 0.10
    if ok_h2 and ok_win and (ok_ref or fam == "lit") and ok_pl:
        return "holds"
    if ok_h2 and ok_win:
        return "H2 only"
    return "fails H2"


def cmd_pick_long():
    """The long-sample view: pick on 2021-24 (4 years, >= 30 trades), check 2025, 2026 H1, 2026 H2."""
    S = grids()
    T = all_trades()
    P = pick_all(S, on="2021-24", min_n=30)
    out = {}
    for nm, p in P.items():
        sp = {s: S[p["key"]][s] for s in CHECK_SPANS}
        ok = all(sp[s]["net"] > 0 for s in ("2025", "H1", "H2"))
        out[nm] = {"key": p["key"], "fam": p["fam"], "w": p["w"], "mode": p["mode"], "plateau_2124": p["plateau_h1"], "spans": sp,
                   "holds_2025_H1_H2": ok, "nb_h2_pos": p["nb_h2_pos"],
                   "placebo_2025": placebo(p["key"], T[p["key"]], "2025", n_draw=200),
                   "placebo_H2": placebo(p["key"], T[p["key"]], "H2", n_draw=200)}
        print(f"{nm:26s} {p['key']:50s} " + " ".join(f"{x}:{sp[x]['n']}/{sp[x]['win']}/{sp[x]['pf']}/{sp[x]['net']:+}" for x in ("2021-24", "2025", "H1", "H2"))
              + ("  HOLDS" if ok else ""), flush=True)
    res = json.load(open(os.path.join(OUT, "picks.json")))
    res["long_view"] = out
    res["multiple_testing"]["long_view_holding"] = sum(1 for v in out.values() if v["holds_2025_H1_H2"])
    _dump(res, os.path.join(OUT, "picks.json"), indent=1, default=float)
    return out


def cmd_pick():
    S = grids()
    T = all_trades()
    picks = pick_all(S)
    tot = len(S)
    for nm, p in picks.items():
        TT = T[p["key"]]
        p["months_2026"] = months(TT)
        p["placebo_H2"] = placebo(p["key"], TT, "H2")
        p["placebo_H1"] = placebo(p["key"], TT, "H1", n_draw=150)
        p["verdict"] = verdict(p, p["fam"])
        s = p["spans"]
        print(f"{nm:28s} {p['key']:50s} " + " ".join(f"{x}:{s[x]['n']}/{s[x]['win']}/{s[x]['pf']}/{s[x]['net']:+}" for x in CHECK_SPANS)
              + f" | nbH2 {p['nb_h2_med']} ({p['nb_h2_pos']}) | plac p {p['placebo_H2'] and p['placebo_H2']['p_net']} | {p['verdict']}", flush=True)
    ch = chance_rate()
    pos4 = sum(1 for k in S if all(S[k][s]["net"] > 0 for s in CHECK_SPANS))
    h1ok = [k for k in S if eligible(S[k]["H1"], "win")]
    h1ok_h2 = [k for k in h1ok if S[k]["H2"]["net"] > 0]
    # persistence: rank correlation of H1 and H2 $ across the variants of each family x window
    def spearmanr(a, b):
        ra = np.argsort(np.argsort(a)).astype(float); rb = np.argsort(np.argsort(b)).astype(float)
        r = float(np.corrcoef(ra, rb)[0, 1])
        n = len(a)
        z = r * math.sqrt(max(1, n - 2)) / math.sqrt(max(1e-12, 1 - r * r))
        return r, math.erfc(abs(z) / math.sqrt(2))     # two-sided, normal approximation of the t statistic
    rho = {}
    by = collections.defaultdict(list)
    for k in S:
        f, w, _ = dims(k)
        by[(f, w)].append(k)
    for (f, w), ks in by.items():
        a = [S[k]["H1"]["net"] for k in ks]; b = [S[k]["H2"]["net"] for k in ks]
        if len(set(a)) > 2 and len(set(b)) > 2:
            r, pv = spearmanr(a, b)
            rho[f"{f}|{w}"] = [round(float(r), 3), round(float(pv), 4), len(ks)]
    mt = {"variants": tot, "positive_all_4_spans": pos4, "positive_all_4_rate": round(pos4 / tot, 4), "chance": ch,
          "h1_eligible_win": len(h1ok), "h1_eligible_win_h2_pos": len(h1ok_h2),
          "picks": len(picks), "picks_holding": sum(1 for p in picks.values() if p["verdict"] == "holds"),
          "picks_placebo_p10": sum(1 for p in picks.values() if (p.get("placebo_H2") or {}).get("p_net", 1) <= 0.10),
          "expected_placebo_p10_by_chance": round(0.10 * sum(1 for p in picks.values() if p.get("placebo_H2")), 1),
          "h1_h2_rank_corr": rho}
    out = {"built": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "picks": picks, "multiple_testing": mt}
    _dump(out, os.path.join(OUT, "picks.json"), indent=1, default=float)
    print(json.dumps({k: v for k, v in mt.items() if k != "h1_h2_rank_corr"}, indent=1))
    return out


# ================================================================================================ 4. 24/5 schedules on the accounts
EVENING = ("open18", "asia", "late_asia")


def my_units(T, src):
    """Common-format trades -> tools/second_mix units (risk, target, points per micro incl. slippage, worst open points and
    the bar path a LIT pre-emption cuts on), exactly as second_mix.second_units builds them for EMA / MACD / S-R."""
    D = data()
    M, B1 = D["M"], D["B1"]
    B5 = lit.bars_5m(M)
    out = []
    for t in T:
        dr = int(t["dir"])
        e, s, x = float(t["entry"]), float(t["stop"]), float(t["exit"])
        risk = abs(e - s)
        if risk <= 0:
            continue
        pts = (x - e) * dr
        tgt = abs(float(t["target"]) - e) if t.get("target") is not None else 3.0 * risk
        B = B1 if int(t["entry_t"]) >= int(B1.t[0]) + 86400 else B5
        k0 = int(np.searchsorted(B.t, int(t["entry_t"]), side="right"))
        kx = int(np.searchsorted(B.t, int(t["exit_t"]) - B.secs))
        lo = B.l if dr == 1 else -B.h
        w = float(lo[k0:kx].min()) - e * dr if kx > k0 else 0.0
        w1 = max(-(risk + 0.25), min(0.0, w, pts))
        op = (B.o[k0:kx + 1] * dr - e * dr) if kx >= k0 else np.zeros(0)
        lw = np.minimum.accumulate(np.r_[0.0, lo[k0:kx] - e * dr]) if kx >= k0 else np.zeros(0)
        out.append({"day": t["day"], "entry_t": int(t["entry_t"]), "exit_t": int(t["exit_t"]), "dir": dr, "exit": t["exit_kind"],
                    "risk": round(risk, 4), "tgt": round(tgt, 4), "pts": round(pts, 4), "w1": round(w1, 4), "src": src,
                    "pt": B.t[k0:kx + 1].astype(np.int64), "po": np.round(op, 2), "pw": np.maximum(np.round(lw, 2), -(risk + 0.25))})
    return out


def merge_std(lists, max_day=2):
    """Several setups' trades at the LIT size in one account: entry order (earlier list first on a tie: LIT first), one
    position at a time, max_day trades a trading day."""
    allt = sorted([(t, j) for j, L in enumerate(lists) for t in L], key=lambda x: (x[0]["entry_t"], x[1]))
    out, nday, busy = [], collections.Counter(), -1
    for t, j in allt:
        if nday[t["day"]] >= max_day or t["entry_t"] < busy:
            continue
        out.append(t)
        nday[t["day"]] += 1
        busy = t["exit_t"]
    return out


def score_50k(U, rule, span, max_day=2, pre=True, reserve=True):
    """tools/second_mix.score_span with a max-trades-a-day choice (LIT's 50K eval with extra setups; LIT priority)."""
    from tools import second_mix as SM
    by = SM.by_day(U)
    S = SM.span_days(span)
    res = [(SM.run_eval(S[i:i + 20], by, rule, max_day=max_day, pre=pre, reserve=reserve), len(S) - i) for i in range(len(S))]
    o = {}
    for lab, h in (("10", 10), ("20", 20)):
        R = [r for r, av in res if av >= h]
        N = len(R) or 1
        o["p" + lab] = round(100.0 * sum(1 for r in R if r[0] == "PASS" and r[1] <= h) / N, 1)
        o["f" + lab] = round(100.0 * sum(1 for r in R if r[0] == "FAIL" and r[1] <= h) / N, 1)
    pas = [r[1] for r, _ in res if r[0] == "PASS" and r[1] <= 20]
    o["pass_med"] = float(np.median(pas)) if pas else None
    k, T, n, lost = 0, [], collections.Counter(), []
    while k < len(S):
        r, used = SM.run_eval(S[k:], by, rule, len(S) - k, keep=T, lost=lost, max_day=max_day, pre=pre, reserve=reserve)
        n[r] += 1
        if r == "OPEN":
            break
        k += used
    p = np.array([t["pnl"] for t in T]) if T else np.zeros(1)
    gl = -p[p < 0].sum()
    eq = np.cumsum(p)
    o.update(n=len(T), tpw=round(len(T) / (len(S) / 5), 2), net=round(float(p.sum())), per_month=round(float(p.sum()) / (len(S) / 21)),
             dd=round(float((eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min())), pf=round(float(p[p > 0].sum() / gl), 2) if gl else None,
             win=round(100.0 * float((p > 0).mean()), 1) if T else None, b2b=f"{n['PASS']}/{n['FAIL']}/{n['OPEN']}",
             lit_lost=sum(1 for _, s in lost if s == "LIT"),
             by_src={s: [sum(1 for t in T if t["src"] == s), round(sum(t["pnl"] for t in T if t["src"] == s))] for s in sorted({t["src"] for t in T})})
    return o, T


class MaxDay:
    """Account B's executor with max_day trades a day (tools/second_account_b runs 2)."""

    def __init__(self, n):
        self.n = n

    def __enter__(self):
        from tools import second_mix as SM
        self.SM, self.orig = SM, SM.play_day
        orig, n = self.orig, self.n

        def pd(L, day, bal, floor, session, rule, pre=False, max_day=2, *a, **k):
            return orig(L, day, bal, floor, session, rule, pre, n, *a, **k)
        SM.play_day = pd
        return self

    def __exit__(self, *a):
        self.SM.play_day = self.orig


def score_acct(U, plan, span, max_day=2):
    """An own account (account B / a third account) on a Builder plan: tools/second_account_b.score with the plan's
    two_week need size (= engine/account_b.qty), no-hedge vs LIT applied to U beforehand."""
    from tools import second_account_b as AB2
    with AB2.Plan(plan) as pl:
        with MaxDay(max_day):
            o, T = AB2.score(U, "acctb_need", span, pl.safe_rule)
    keep = ("p10", "f10", "s10", "dead10", "p20", "f20", "dead20", "pass_med", "p60", "f60", "n", "tpw", "net", "per_month", "dd", "pf",
            "b2b", "fund_paid_3m", "ev_eval_3m", "path_net_less_fees", "max_risk", "med_risk", "by_src")
    return {k: o.get(k) for k in keep}, T


def schedule_sets():
    """The setups a 24/5 schedule is built from. Every choice is made on 2026 H1 (or, for the long view, 2021-24) only."""
    P = json.load(open(os.path.join(OUT, "picks.json")))
    T = all_trades()
    picks = P["picks"]
    # one setup per window: the 'win'-mode pick (win % >= 50 in H1) with the best H1 plateau score of the window's families
    per_w = {}
    for nm, p in picks.items():
        if p["mode"] != "win":
            continue
        if p["w"] not in per_w or p["plateau_h1"] > per_w[p["w"]]["plateau_h1"]:
            per_w[p["w"]] = p
    sets = {"h1_all": {w: per_w[w]["key"] for w in TRADE_W if w in per_w},
            "h1_evening": {w: per_w[w]["key"] for w in EVENING if w in per_w}}
    lv = P.get("long_view", {})
    # the long view: one setup per window picked on 2021-24 only (best 2021-24 plateau of the window's families)
    for mode in ("money", "win"):
        best = {}
        for nm, v in lv.items():
            if v["mode"] != mode:
                continue
            if v["w"] not in best or v["plateau_2124"] > best[v["w"]]["plateau_2124"]:
                best[v["w"]] = v
        sets[f"long_all_{mode}"] = {w: best[w]["key"] for w in TRADE_W if w in best}
        sets[f"long_evening_{mode}"] = {w: best[w]["key"] for w in EVENING if w in best}
    # PEEKED (chosen because they were positive in 2025, H1 and H2): reference / paper watch only, not a test
    sets["long_holds_peeked"] = {}
    for nm, v in lv.items():
        if v["holds_2025_H1_H2"] and nm.endswith("money"):
            sets["long_holds_peeked"][v["w"]] = v["key"]
    sets["asia_reclaim_peeked"] = {"asia": "reclaim|asia|prev,0.5,6,cisd|S,None,eod"}
    return sets, T


def cmd_combo():
    from tools import second_mix as SM
    U0 = SM.units()
    sets, T = schedule_sets()
    lit_c = lit_common(lit_run(lit_live()), "LIT")
    res = {"sets": sets, "std": {}, "50k": {}, "acctB": {}, "third": {}}
    # standalone at the LIT size: LIT + the schedule's setups, one position, max 2 / 3 a day
    asia_slot = [t for t in lit_common(SM_asia_trades(), "LIT Asia slot") if lit_mod_of(t) >= 1080 or lit_mod_of(t) < 120]
    extra = {"asia_slot": [asia_slot]}
    for nm, S in sets.items():
        extra[nm] = [[{**t, "setup": t["setup"]} for t in T[k]] for w, k in S.items()]
    for nm, lists in [("lit", [])] + list(extra.items()):
        for md in (2, 3):
            M_ = merge_std([lit_c] + lists, md)
            res["std"][f"{nm}|{md}"] = {s: stats(M_, s) for s in CHECK_SPANS}
    # (i) LIT's 50K eval (two_week path) + the schedule, LIT priority (a LIT signal flattens an open extra trade)
    UL = list(U0["LIT"])
    UX = {"asia_slot": list(U0["Asia"])}
    for nm, S in sets.items():
        UX[nm] = [u for w, k in S.items() for u in my_units(T[k], f"{w}")]
    res["50k"]["lit"] = {s: score_50k(UL, "usd300", s, 2)[0] for s in ("H1", "H2", "2025", "2021-24")}
    for nm, UU in UX.items():
        for rule in (("-",) if nm == "asia_slot" else ("need0.5", "need1.0", "usd300_safe_dll")):
            for md in (2, 3):
                key = f"{nm}|{rule}|{md}"
                res["50k"][key] = {s: score_50k(UL + UU, rule if rule != "-" else "usd300", s, md)[0] for s in ("H1", "H2", "2025", "2021-24")}
                print("50k", key, {s: (v["p10"], v["f10"], v["net"], v["tpw"]) for s, v in res["50k"][key].items()}, flush=True)
    # (ii) ATLAS on its own Builder 25K + the schedule's setups (never opposite to LIT)
    ATL = SM.acct_units(("EMA", "MD", "SR"), nohedge=True)
    res["acctB"]["atlas"] = {s: score_acct(ATL, "builder25k", s)[0] for s in ("H1", "H2", "2025", "2021-24")}
    for nm, UU in UX.items():
        if nm == "asia_slot":                        # on an own account the Asia-slot trades are an ordinary setup
            UU = my_units(asia_slot, "AsiaLIT")
        UUn = SM.no_hedge(UU)
        for md in (2, 3):
            key = f"{nm}|{md}"
            res["acctB"][key] = {s: score_acct(ATL + UUn, "builder25k", s, md)[0] for s in ("H1", "H2", "2025", "2021-24")}
            print("atlas25k", key, {s: (v["p10"], v["dead10"], v["net"], v["tpw"]) for s, v in res["acctB"][key].items()}, flush=True)
            # (iii) the schedule alone on a third account (Builder 25K), never opposite to LIT
            res["third"][key] = {s: score_acct(UUn, "builder25k", s, md)[0] for s in ("H1", "H2", "2025", "2021-24")}
            print("third25k", key, {s: (v["p10"], v["dead10"], v["net"], v["tpw"]) for s, v in res["third"][key].items()}, flush=True)
    _dump(res, os.path.join(OUT, "schedule.json"), indent=1, default=float)
    return res


def SM_asia_trades():
    """The Asia-slot run (tools/lit_more_entries variant asiaslotn_rr3_x1.0 = run lit_more_ent_asia_slot_rr3)."""
    from tools import lit_more_entries as ME
    return ME.run(ME.variants()["asiaslotn_rr3_x1.0"])


# ================================================================================================ store: pick files + runs ad_*
COMMON = ("day", "entry_t", "exit_t", "dir", "entry", "stop", "target", "exit", "exit_kind", "r", "qty", "pnl_usd", "setup")


def rules_of(key):
    """Plain-language rules of a variant key."""
    fam, w, v = dims(key)
    lab = WD[w][1]
    _, _, a, b = WD[w]
    if fam == "lit":
        depth, disp, mrr, be = v
        return [f"LIT exactly as live (engine/lit.py, live_model.json 'lit': inducement first, 5m CISD, limit 30 min, 1m CISD entry, "
                f"stop 1 tick beyond the sweep extreme, VIX-band target, 15-minute check, BE + 1.25 pts, Monday rule, weekly stop), "
                f"but entries only in {lab}, 1 trade a day.",
                f"This window's own thresholds: sweep >= {depth} ATR deep, displacement body >= {disp} ATR, target banked at {mrr}R, "
                f"breakeven at {be}R.", "Flat 15:55 ET at the latest (an evening entry is held at most to 15:55 of its trading day)."]
    t, be, h = v[-3:]
    tg = {"S": "the setup's own level (see above; >= 1R away, banked at 8R)", "R1": "1R", "R1.5": "1.5R", "R2": "2R", "R3": "3R"}[t]
    hold = "flat at the window end + 60 min" if h == "w" else "flat 15:55 ET"
    common = [f"Target {tg}." + ("" if be == "None" else f" Breakeven (entry + 1.25 pts) once +{be}R was reached."),
              f"Time exit: {hold}. One trade a day. Entry at the next 5m open + 1 tick; stop and time exits - 1 tick; $1.40 a micro.",
              "Size: $800 risk up to a 20-pt stop, then 800 x 20 / stop (max 40 micros); stops 6-80 pts."]
    if fam == "reclaim":
        ref, dep, nc, cf = v[:4]
        box = {"prev": "the window before's high / low", "sofar": "the trading day's high / low so far (from 18:00)",
               "pd": "the previous day's high / low (not yet taken today)", "or30": "this window's first 30 minutes' high / low"}[ref]
        return [f"Window: {lab} (entry bar inside it).", f"Level: {box}.",
                f"Sweep: a 5m bar trades through the level" + (f" by >= {dep} x the 5m ATR(14)" if float(dep) else "") + ".",
                f"Reclaim: within {nc} bars a 5m close back inside" + (" that is also beyond the open of the candle run into the extreme (CISD)" if cf == "cisd" else "") + ".",
                "Short after a high sweep, long after a low sweep; stop 1 tick beyond the sweep extreme; the setup's own level = the box's other side."] + common
    if fam == "orb":
        orm, sm = v[:2]
        return [f"Window: {lab}. Opening range = its first {orm} minutes.", "Entry: the first 5m close beyond the range, that way.",
                "Stop: " + ("the other side of the range." if sm == "opp" else "1 tick beyond the breakout candle.")] + common
    if fam == "mr":
        anc, kk = v[:2]
        return [f"Window: {lab}.", f"Stretch: the last 6 candles reached >= {kk} x the 5m ATR(14) beyond the "
                + ("session VWAP (from 18:00)" if anc == "vwap" else "window's open price") + ".",
                "Trigger: a 5m close beyond the prior candle's high (long) / low (short), still on the stretched side.",
                "Stop 1 tick beyond the 6-candle extreme; the setup's own level = the anchor (VWAP / window open)."] + common
    if fam == "cont":
        src, ef, pb = v[:3]
        return [f"Window: {lab}.", ("The window before" if src == "prev" else "The trading day so far") +
                f" moved one way: |close - open| >= {ef} x its range, range >= 0.15 x the 14-day mean daily range.",
                f"Pullback >= {pb} x that range from the move's extreme, then a 5m close beyond the prior candle's high (long) / low (short), with the move.",
                "Stop 1 tick beyond the pullback extreme; the setup's own level = the move's extreme."] + common
    return []


def run_trades(T):
    """Common-format trades -> runlib trade records (incl. the worst open $ for the day low)."""
    out = []
    for t in T:
        q = int(t["qty"])
        w1 = t.get("w1")
        low = min(0.0, (w1 * PV * q - COMM * q) if w1 is not None else 0.0, t["pnl_usd"])
        out.append({"day": t["day"], "entry_t": int(t["entry_t"]), "exit_t": int(t["exit_t"]), "dir": int(t["dir"]), "r": float(t["r"]),
                    "pnl": float(t["pnl_usd"]), "risk_pts": float(t["risk"]), "qty": q, "risk_usd": round(float(t["risk"]) * PV * q, 2),
                    "half": False, "exit": t["exit_kind"], "trigger": t["setup"], "mfe": None, "mae": None, "bars_held": None,
                    "regime": t.get("w", ""), "mult": None, "low": round(low, 2)})
    return out


def _h(s):
    return (f"{s['n']} trades ({s['tpw']}/wk), win {s['win']}% (clean >= +0.5R {s.get('cwin')}%), PF {s['pf']}, "
            f"net {s['net']:+,} (${s.get('per_month', 0):,}/mo), DD {s.get('dd', 0):,}")


def cmd_save():
    from tools import runlib as rl
    from tools import second_mix as SM
    D = data()
    sess = D["sess"]
    T = all_trades()
    S = grids()
    P = json.load(open(os.path.join(OUT, "picks.json")))
    sets, _ = schedule_sets()
    SC = json.load(open(os.path.join(OUT, "schedule.json")))
    Q = ("Owner 2026-10-23: start trading 24/7 - which setups work in each part of the NQ day, at the same or a higher win rate "
         "than LIT?")
    # 1. pick files: every window's H1 pick (win mode), the long view (money mode), the two peeked evening setups
    files = {}
    for w, k in sets["h1_all"].items():
        files[f"h1_{w}"] = (k, "H1 pick (2026 Jan-Jun, win % >= 50, plateau score)")
    for w, k in sets["long_all_money"].items():
        files[f"long_{w}"] = (k, "long-view pick (2021-24, plateau score)")
    files["peeked_open18_vwap"] = (sets["long_holds_peeked"].get("open18"), "long-view pick that was positive in 2025, H1 and H2 (chosen after looking)")
    seen = {k for k, _ in files.values()}
    if sets["long_holds_peeked"].get("asia") not in seen:
        files["peeked_asia_reclaim"] = (sets["long_holds_peeked"].get("asia"), "long-view pick positive in 2025, H1 and H2 (chosen after looking)")
    index = {}
    for fid, (k, how) in files.items():
        if not k:
            continue
        TT = T[k]
        pk = next((p for p in P["picks"].values() if p["key"] == k), None)
        lv = next((p for p in P.get("long_view", {}).values() if p["key"] == k), None)
        rec = {"id": fid, "key": k, "family": dims(k)[0], "window": dims(k)[1], "window_label": WD[dims(k)[1]][1], "how_picked": how,
               "params": dict(zip(["p%d" % j for j in range(len(dims(k)[2]))], dims(k)[2])), "rules": rules_of(k),
               "spans": {s: S[k][s] for s in CHECK_SPANS}, "months_2026": months(TT),
               "placebo": {"H2": (pk or {}).get("placebo_H2") or (lv or {}).get("placebo_H2"),
                           "2025": (lv or {}).get("placebo_2025")},
               "neighbours_h2": {"median": (pk or {}).get("nb_h2_med"), "positive": (pk or {}).get("nb_h2_pos") or (lv or {}).get("nb_h2_pos")},
               "verdict": (pk or {}).get("verdict") or ("holds 2025/H1/H2" if (lv or {}).get("holds_2025_H1_H2") else "fails a check"),
               "costs": "$1.40 a micro round trip + 1 tick on market entries, stop and time exits (eval views $1.90)",
               "data": "TradingView CME NQ1! 5m (data/NQ_5m.csv), 1m for the 2026 trade path (data/NQ_1m.csv)",
               "trade_format": list(COMMON), "trades": [{c: t.get(c) for c in COMMON} for t in TT]}
        _dump(rec, os.path.join(OUT, f"pick_{fid}.json"), separators=(",", ":"))
        index[fid] = {"key": k, "how": how, "verdict": rec["verdict"], "spans": {s: {x: S[k][s].get(x) for x in ("n", "tpw", "win", "pf", "net")}
                                                                                for s in CHECK_SPANS}}
    _dump({"built": dt.datetime.now().strftime("%Y-%m-%d %H:%M"), "files": index}, os.path.join(OUT, "picks_index.json"), indent=1)
    print(len(index), "pick files", flush=True)

    # 2. runs: single setups
    for fid, (k, how) in files.items():
        if not k:
            continue
        TT = run_trades(T[k])
        s = S[k]
        status = "rejected"
        rl.save("ad_" + fid, f"All day: {WD[dims(k)[1]][1]} - {dims(k)[0]} ({how.split(' (')[0]})", "sessions", Q,
                params={"key": k, "rules": rules_of(k)}, trades=TT, scored=rl.score(TT, sess), status=status,
                verdict=f"LIT size, costs in. H1 {_h(s['H1'])}. H2 {_h(s['H2'])}. 2025 {_h(s['2025'])}. 2021-24 {_h(s['2021-24'])}.",
                notes=f"tools/allday.py, variant {k}; picked: {how}", writeup="allday", tags=["allday", dims(k)[1], dims(k)[0]])
    # 3. runs: schedules at the LIT size (LIT + the extra setups, one position, max 2 a day)
    lit_c = lit_common(lit_run(lit_live()), "LIT")
    for sid, title in (("h1_all", "LIT + one H1-picked setup in every window (24/5 schedule)"),
                       ("h1_evening", "LIT + the H1-picked evening setups (18:00-02:00)"),
                       ("long_all_money", "LIT + one 2021-24-picked setup per window"),
                       ("long_holds_peeked", "LIT + the two evening setups positive everywhere (peeked)")):
        lists = [[t for t in T[k]] for w, k in sets[sid].items()]
        MM = merge_std([lit_c] + lists, 2)
        TT = run_trades([{**t, "w1": t.get("w1")} for t in MM])
        x = SC["std"][f"{sid}|2"]
        e = {kk: SC["50k"].get(f"{sid}|need0.5|2", {}).get(kk) for kk in ("H1", "H2")}
        b = SC["50k"]["lit"]
        rl.save("ad_sched_" + sid, "All day schedule: " + title, "sessions", Q, params={"setups": sets[sid], "max_per_day": 2, "one_position": True},
                trades=TT, scored=rl.score(TT, sess), status="rejected",
                verdict=(f"LIT size, costs in, LIT first. H1 {_h(x['H1'])}. H2 {_h(x['H2'])}. 2025 net {x['2025']['net']:+,}, 2021-24 net "
                         f"{x['2021-24']['net']:+,}. LIT alone H1 +33,891 / H2 +9,493. On LIT's 50K eval (two_week, extras at half the need "
                         f"size, LIT priority): 2-week pass/fail H1 {e['H1'] and e['H1']['p10']}/{e['H1'] and e['H1']['f10']}, "
                         f"H2 {e['H2'] and e['H2']['p10']}/{e['H2'] and e['H2']['f10']} (LIT alone {b['H1']['p10']}/{b['H1']['f10']}, "
                         f"{b['H2']['p10']}/{b['H2']['f10']})."),
                notes="tools/allday.py combo / save; LIT trades = run lit_live (1m entries in 2026, 5m before)", writeup="allday",
                tags=["allday", "schedule"])
    # 4. run: ATLAS on its 25K + LIT's Asia slot trades (the closest combination)
    ATL = SM.acct_units(("EMA", "MD", "SR"), nohedge=True)
    asia_slot = [t for t in lit_common(SM_asia_trades(), "LIT Asia slot") if lit_mod_of(t) >= 1080 or lit_mod_of(t) < 120]
    UU = SM.no_hedge(my_units(asia_slot, "AsiaLIT"))
    PT = []
    for s in ("H1", "H2", "2025", "2021-24"):
        PT += score_acct(ATL + UU, "builder25k", s, 2)[1]
    TT = [{"day": t["day"], "entry_t": t["entry_t"], "exit_t": t["exit_t"], "dir": t["dir"], "r": round(t["pnl"] / t["risk_usd"], 3) if t["risk_usd"] else 0.0,
           "pnl": t["pnl"], "risk_pts": t["risk"], "qty": t["qty"], "risk_usd": t["risk_usd"], "half": False, "exit": t["exit"], "trigger": t["src"],
           "mfe": None, "mae": None, "bars_held": None, "regime": "", "mult": None, "low": t["low"]} for t in PT]
    xa, xb = SC["acctB"]["asia_slot|2"], SC["acctB"]["atlas"]
    f = lambda o: f"2-week pass {o['p10']}% / dead {o['dead10']}%, path {o['net']:+,}, {o['tpw']}/wk"  # noqa: E731
    rl.save("ad_atlas25k_asia_slot", "All day: ATLAS 25K + LIT's Asia-slot trades (18:00-02:00) on account B", "sessions", Q,
            params={"account": "builder25k", "setups": ["EMA", "MD", "SR", "LIT Asia slot (asiaslotn_rr3_x1.0, evening entries)"],
                    "size": "acctb need", "no_hedge": True}, trades=TT, scored=rl.score(TT, [d for d in SM.units()["sessions"] if d >= "2021-01-01"]),
            status="rejected",
            verdict=(f"H1 {f(xa['H1'])} (ATLAS alone {f(xb['H1'])}); H2 {f(xa['H2'])} (alone {f(xb['H2'])}); 2025 {f(xa['2025'])} "
                     f"(alone {f(xb['2025'])}); 2021-24 {f(xa['2021-24'])} (alone {f(xb['2021-24'])})."),
            notes="stored trades = the back-to-back eval path of each span (tools/second_account_b.score)", writeup="allday",
            tags=["allday", "account_b"])
    print("runs saved", flush=True)


# ================================================================================================ main
if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "map"
    if cmd == "map":
        cmd_map()
    elif cmd == "showmap":
        show_map()
    elif cmd == "fam":
        cmd_fam()
    elif cmd == "lit":
        cmd_lit()
    elif cmd == "pick":
        cmd_pick()
        cmd_pick_long()
    elif cmd == "picklong":
        cmd_pick_long()
    elif cmd == "combo":
        cmd_combo()
    elif cmd == "save":
        cmd_save()
