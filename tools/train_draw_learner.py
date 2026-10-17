"""Draw learner trainer: which draws on liquidity does price actually reach before the stop?

  python tools/train_draw_learner.py              # enumerate + label draws, walk-forward fit, evaluate, write model + report
  python tools/train_draw_learner.py --quick      # same, without the (slow) drop-one feature ranking
  python tools/train_draw_learner.py --check 5    # print the draws of 5 sample entries and stop

Inputs (read-only): data/NQ_5m.csv through tools/strategy_lab.bars() (real CME NQ1!, never CFD) and the engine's
live-replay trades in research/five_year/run_live.json.
Outputs: data/draw_learner.json (logistic model fitted on every labelled draw, for live use) and
research/lab/DRAW_LEARNER.md (walk-forward results only). Single process, numpy only.

Every definition follows research/lab/DOL_PLAYBOOK.md (D1-D9, DOL-1, DOL-4, DOL-6); DRAW_LEARNER.md lists them.
Causality: an entry decided at the close of its signal bar sees only 5m bars that have closed by then, and an HTF bar only
once its last 5m bar has closed. Labels look only forward from the bar after the signal bar.
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import math
import os
import sys
import time

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from engine import draw_learner as DL  # noqa: E402

TICK, SLIP = 0.25, 0.25
FLAT_MOD = 955                       # labels and exits stop at 15:55 ET
WIN_DAYS = 62                        # 5m history window handed to the enumerator (covers every lookback below)
SW_K = {"5m": 2, "15m": 1, "1h": 1, "4h": 1, "1d": 1}            # D1 fractal strength
SW_LB_H = {"15m": 120, "1h": 240, "4h": 720, "1d": 1440}         # swing pools tracked this long after confirming (ours)
SW_SRC = {"15m": "M15SW", "1h": "H1SW", "4h": "H4SW", "1d": "D1SW"}
EQ_TFS = ("5m", "15m", "1h")
FVG_SRC = {"5m": "FVG5", "15m": "FVG15", "1h": "FVG1H", "4h": "FVG4H", "1d": "FVG1D"}
FVG_LIFE_H = {"15m": 120, "1h": 240}                         # 5m: end of the next CME day; 4H / 1D: never (10 nearest)
NEVER_EXPIRE = ("4h", "1d")
PRIO = {"PWH": 0, "PWL": 0, "PDH": 1, "PDL": 1, "RTH": 2, "LON": 3, "ASIA": 4, "ON": 5, "D1SW": 6, "H4SW": 7, "H1SW": 8,
        "M15SW": 9, "M5SW": 10}
EQ_ABSORB = 8                        # an EQ pool is folded into a named pool of this priority or better (H1SW and up)
MINOR = ("M15SW", "M5SW")            # swing draws that an EQ pool absorbs
MAX_R = 12.0                         # draws further than this many R are not enumerated
MIN_TRAIN_TRADES = 120               # walk-forward: first month predicted once this many trades are in the past
RUN_LIVE = os.path.join(ROOT, "research", "five_year", "run_live.json")
MODEL_OUT = os.path.join(ROOT, "data", "draw_learner.json")
REPORT = os.path.join(ROOT, "research", "lab", "DRAW_LEARNER.md")


# ============================================================================================ history (precomputed once)
def wilder_atr(h, l, c, n=14):
    """Wilder ATR(n) at the close of every bar (seeded with the running mean of the first n true ranges)."""
    m = len(c)
    out = np.zeros(m)
    if m == 0:
        return out
    pc = np.r_[c[0], c[:-1]]
    tr = np.maximum(h, pc) - np.minimum(l, pc)
    tr[0] = h[0] - l[0]
    k0 = min(n, m)
    out[:k0] = np.cumsum(tr[:k0]) / np.arange(1, k0 + 1)
    a = out[k0 - 1]
    for k in range(k0, m):
        a = (a * (n - 1) + tr[k]) / n
        out[k] = a
    return out


def swing_flags(H, L, k):
    """D1 fractal: high[i] > max(high[i-k..i-1]) and high[i] >= max(high[i+1..i+k]); lows mirrored."""
    n = len(H)
    sh, sl = np.zeros(n, bool), np.zeros(n, bool)
    if n < 2 * k + 1:
        return sh, sl
    idx = np.arange(k, n - k)
    lh = np.max([H[idx - j] for j in range(1, k + 1)], axis=0)
    rh = np.max([H[idx + j] for j in range(1, k + 1)], axis=0)
    ll = np.min([L[idx - j] for j in range(1, k + 1)], axis=0)
    rl = np.min([L[idx + j] for j in range(1, k + 1)], axis=0)
    sh[idx] = (H[idx] > lh) & (H[idx] >= rh)
    sl[idx] = (L[idx] < ll) & (L[idx] <= rl)
    return sh, sl


class TF:
    """One timeframe built from 5m bars. end = close time; first5 = first 5m bar opening at/after that close."""

    def __init__(self, name, t5, o5, h5, l5, c5, key, end5_nominal, day_k5):
        st = np.flatnonzero(np.r_[True, key[1:] != key[:-1]])
        en = np.r_[st[1:], len(key)] - 1
        self.name = name
        self.o, self.c = o5[st], c5[en]
        self.h, self.l = np.maximum.reduceat(h5, st), np.minimum.reduceat(l5, st)
        self.end = end5_nominal[st] if end5_nominal is not None else t5[en] + 300
        self.first5 = np.searchsorted(t5, self.end)
        self.dayk = day_k5[en]
        self.atr = wilder_atr(self.h, self.l, self.c)
        k = SW_K[name]
        self.k = k
        sh, sl = swing_flags(self.h, self.l, k)
        n = len(self.h)
        self.sw = {}
        for side, flags, lv in ((1, sh, self.h), (-1, sl, self.l)):
            idx = np.flatnonzero(flags)
            ci = idx + k
            self.sw[side] = {"i": idx, "lvl": lv[idx], "conf_end": self.end[ci], "first5": self.first5[ci],
                             "atr": self.atr[ci]}
        # 3-candle FVGs (D3): bullish low[c3] > high[c1]; bearish high[c3] < low[c1]
        j = np.arange(2, n)
        minsz = np.maximum(TICK, 0.1 * self.atr[j]) if name == "5m" else np.full(len(j), TICK)
        self.gaps = {}
        for pol in (1, -1):
            if pol == 1:
                bot, top = self.h[j - 2], self.l[j]
            else:
                bot, top = self.h[j], self.l[j - 2]
            ok = (top - bot) >= minsz - 1e-9
            jj = j[ok]
            self.gaps[pol] = {"j": jj, "bot": bot[ok], "top": top[ok], "ce": (bot[ok] + top[ok]) / 2.0,
                              "end": self.end[jj], "first5": self.first5[jj], "dayk": self.dayk[jj]}
        self.n = n


class History:
    def __init__(self, df):
        self.t = df["time"].values.astype(np.int64)
        self.o, self.h, self.l, self.c = (df[k].values.astype(float) for k in ("open", "high", "low", "close"))
        self.mod = df["mod"].values.astype(np.int64)
        self.dayn = pd.to_datetime(df["day"]).values.astype("datetime64[D]").astype(np.int64)
        t, n = self.t, len(self.t)
        self.atr5 = wilder_atr(self.h, self.l, self.c)
        # CME days (trading-day index kd)
        self.udays, self.dfirst = np.unique(self.dayn, return_index=True)
        self.dlast = np.r_[self.dfirst[1:], n] - 1
        self.dayk = np.repeat(np.arange(len(self.udays)), np.diff(np.r_[self.dfirst, n]))
        self.day_hi = np.maximum.reduceat(self.h, self.dfirst)
        self.day_lo = np.minimum.reduceat(self.l, self.dfirst)
        g = pd.Series(self.dayk)
        self.run_hi = pd.Series(self.h).groupby(g).cummax().values
        self.run_lo = pd.Series(self.l).groupby(g).cummin().values
        # ET midnight of each CME day (bars after midnight carry mod < 1080)
        self.midnight = np.full(len(self.udays), -1, dtype=np.int64)
        am = np.flatnonzero(self.mod < 1080)
        ka = self.dayk[am]
        first_am = np.unique(ka, return_index=True)
        self.midnight[first_am[0]] = t[am[first_am[1]]] - self.mod[am[first_am[1]]] * 60
        # sessions of each CME day: Asia 20:00-24:00, London 02:00-05:00, overnight 18:00-09:30 (D7)
        self.sess = {}
        masks = {"ASIA": self.mod >= 1200, "LON": (self.mod >= 120) & (self.mod < 300),
                 "ON": (self.mod >= 1080) | (self.mod < 570)}
        for name, m in masks.items():
            hi = np.full(len(self.udays), np.nan)
            lo = np.full(len(self.udays), np.nan)
            idx = np.flatnonzero(m)
            kd = self.dayk[idx]
            s = pd.DataFrame({"k": kd, "h": self.h[idx], "l": self.l[idx]}).groupby("k").agg(h=("h", "max"), l=("l", "min"))
            hi[s.index.values] = s["h"].values
            lo[s.index.values] = s["l"].values
            self.sess[name] = (hi, lo)
        self.sess_off = {"ASIA": 0, "LON": 300, "ON": 570}       # usable from midnight + this many minutes
        # RTH 09:30-16:00 H/L of each CME day (the next day's "prior RTH" pool, usable from 16:00)
        m = (self.mod >= 570) & (self.mod < 960)
        idx = np.flatnonzero(m)
        s = pd.DataFrame({"k": self.dayk[idx], "h": self.h[idx], "l": self.l[idx]}).groupby("k").agg(h=("h", "max"), l=("l", "min"))
        self.rth_hi = np.full(len(self.udays), np.nan)
        self.rth_lo = np.full(len(self.udays), np.nan)
        self.rth_hi[s.index.values] = s["h"].values
        self.rth_lo[s.index.values] = s["l"].values
        # CME weeks (Sunday 18:00 -> Friday 17:00 = the Monday-based week of the trading-day label)
        self.weekn = (self.dayn + 3) // 7
        self.uweeks, self.wfirst = np.unique(self.weekn, return_index=True)
        self.week_hi = np.maximum.reduceat(self.h, self.wfirst)
        self.week_lo = np.minimum.reduceat(self.l, self.wfirst)
        # higher timeframes (C3): 15m / 1H clock-aligned, 4H anchored on the 18:00 ET open, daily = CME day
        m18 = (self.mod - 1080) % 1440
        start4 = t - (m18 % 240) * 60
        self.tf = {
            "5m": TF("5m", t, self.o, self.h, self.l, self.c, t, t + 300, self.dayk),
            "15m": TF("15m", t, self.o, self.h, self.l, self.c, t // 900, (t // 900 + 1) * 900, self.dayk),
            "1h": TF("1h", t, self.o, self.h, self.l, self.c, t // 3600, (t // 3600 + 1) * 3600, self.dayk),
            "4h": TF("4h", t, self.o, self.h, self.l, self.c, start4, start4 + 14400, self.dayk),
            "1d": TF("1d", t, self.o, self.h, self.l, self.c, self.dayk, None, self.dayk),
        }
        # 4H / daily gaps never expire: first 5m bar whose wick reaches the CE, over the whole future (D6)
        for pol, tfn in ((1, "4h"), (-1, "4h"), (1, "1d"), (-1, "1d")):
            G = self.tf[tfn].gaps[pol]
            tag = np.full(len(G["j"]), n + 10, dtype=np.int64)
            for q in range(len(G["j"])):
                a = int(G["first5"][q])
                ce = G["ce"][q]
                for w in (3000, None):
                    seg = (self.l[a:a + w] if w else self.l[a:]) if pol == 1 else (self.h[a:a + w] if w else self.h[a:])
                    hit = (seg <= ce) if pol == 1 else (seg >= ce)
                    if hit.any():
                        tag[q] = a + int(np.argmax(hit))
                        break
                    if w is None or a + w >= n:
                        break
                    a = a + w
            G["tag5"] = tag


# ============================================================================================ enumerator (one entry)
def enumerate_draws(H: History, i, d, E, R, htf_dir):
    """Every draw beyond entry E in direction d at the close of 5m bar i (playbook definitions), with features.
    Returns (draws, info). Each draw: dict with level (price), level_d (direction space), the feature keys and extras."""
    t5, T = H.t, int(H.t[i]) + 300
    kd = int(H.dayk[i])
    a5 = int(np.searchsorted(t5, T - WIN_DAYS * 86400))
    hd5 = H.h[a5:i + 1] if d == 1 else -H.l[a5:i + 1]
    suf = np.maximum.accumulate(hd5[::-1])[::-1]          # max direction-space high from bar k through i

    def mx(k5):
        k5 = np.atleast_1d(np.asarray(k5, dtype=np.int64))
        out = np.full(k5.shape, -np.inf)
        ok = k5 <= i
        out[ok] = suf[np.clip(k5[ok] - a5, 0, None)]
        return out

    Ed = E * d
    atr5 = float(H.atr5[i])
    tol5 = max(2 * TICK, 0.1 * atr5)
    session = "AM" if int(H.mod[i]) < 720 else "PM"
    # reach (DOL-4): max(0.5 x ADR10, ADR10 - today's range so far)
    k0 = max(0, kd - 10)
    rng = H.day_hi[k0:kd] - H.day_lo[k0:kd]
    adr10 = float(rng.mean()) if len(rng) else float("nan")
    run_rng = float(H.run_hi[i] - H.run_lo[i])
    reach = max(0.5 * adr10, adr10 - run_rng) if len(rng) else float("inf")

    named = []      # [level_d, source, usable_t, eq]

    def add_named(lvl_d, src, usable, k5):
        if usable > T:
            return
        if mx(k5)[0] >= lvl_d + TICK:          # taken (D9): a 5m wick 1 tick through it since it became usable
            return
        if lvl_d - Ed <= 0:
            return
        named.append([float(lvl_d), src, int(usable), False])

    hi_side = d == 1
    if kd >= 1:                                                   # PDH / PDL: previous CME day, usable from 18:00
        lv = H.day_hi[kd - 1] if hi_side else -H.day_lo[kd - 1]
        add_named(lv, "PDH" if hi_side else "PDL", int(t5[H.dfirst[kd]]), int(H.dfirst[kd]))
    wk = int(np.searchsorted(H.uweeks, H.weekn[i]))               # PWH / PWL: previous week, usable from Sunday 18:00
    if wk >= 1:
        lv = H.week_hi[wk - 1] if hi_side else -H.week_lo[wk - 1]
        add_named(lv, "PWH" if hi_side else "PWL", int(t5[H.wfirst[wk]]), int(H.wfirst[wk]))
    mid = int(H.midnight[kd])
    if mid > 0:                                                   # today's Asia / London / overnight H-L
        for name, (shi, slo) in H.sess.items():
            v = shi[kd] if hi_side else slo[kd]
            if not np.isfinite(v):
                continue
            usable = mid + H.sess_off[name] * 60
            add_named(v if hi_side else -v, name, usable, int(np.searchsorted(t5, usable)))
    if kd >= 1 and int(H.midnight[kd - 1]) > 0:                  # prior RTH H/L (09:30-16:00), usable from 16:00
        v = H.rth_hi[kd - 1] if hi_side else H.rth_lo[kd - 1]
        if np.isfinite(v):
            usable = int(H.midnight[kd - 1]) + 960 * 60
            add_named(v if hi_side else -v, "RTH", usable, int(np.searchsorted(t5, usable)))
    day_from = int(t5[H.dfirst[max(0, kd - 1)]])                 # "fresh" 5m swings: confirmed today or yesterday

    def swings(tfn, lb_h, t_from=None):
        """Untaken confirmed swings on the draw side: (lvl_d, conf_end, tf index, atr at confirmation)."""
        S = H.tf[tfn].sw[1 if hi_side else -1]
        lo_t = T - lb_h * 3600 if t_from is None else t_from
        a = int(np.searchsorted(S["conf_end"], lo_t, side="left"))
        b = int(np.searchsorted(S["conf_end"], T, side="right"))
        if b <= a:
            return np.zeros(0), np.zeros(0, np.int64), np.zeros(0, np.int64), np.zeros(0)
        lvl_d = S["lvl"][a:b] * (1 if hi_side else -1)
        keep = mx(S["first5"][a:b]) < lvl_d + TICK
        return lvl_d[keep], S["conf_end"][a:b][keep], S["i"][a:b][keep], S["atr"][a:b][keep]

    for tfn in ("15m", "1h", "4h", "1d"):                        # HTF swing pools (k=1)
        lv, ce_, _, _ = swings(tfn, SW_LB_H[tfn])
        for x, u in zip(lv, ce_):
            if x - Ed > 0:
                named.append([float(x), SW_SRC[tfn], int(u), False])
    s5_lv, s5_ce, _, _ = swings("5m", 0, t_from=day_from)        # fresh 5m swings (k=2)
    for x, u in zip(s5_lv, s5_ce):
        if x - Ed > 0:
            named.append([float(x), "M5SW", int(u), False])

    # same price on several lenses = one pool, labelled by its most significant source
    best = {}
    for p in named:
        key = int(round(p[0] / TICK))
        if key not in best or PRIO[p[1]] < PRIO[best[key][1]]:
            best[key] = p
    named = sorted(best.values(), key=lambda p: p[0])

    # EQH / EQL (D8): two confirmed swings on the same TF within max(2 ticks, 0.1 ATR_tf), >= 3 bars apart, with a
    # >= 1 ATR_tf pullback between them. Level = the higher one; usable when the second swing confirms.
    eqs = {}
    for tfn in EQ_TFS:
        tf = H.tf[tfn]
        if tfn == "5m":
            lv, ce_, ix, at = swings("5m", 0, t_from=day_from)
        else:
            lv, ce_, ix, at = swings(tfn, SW_LB_H[tfn])
        if len(lv) < 2:
            continue
        Ld = tf.l if hi_side else -tf.h
        order = np.argsort(ix)
        lv, ce_, ix, at = lv[order], ce_[order], ix[order], at[order]
        for b in range(1, len(lv)):
            for a in range(b):
                if ix[b] - ix[a] < 3:
                    continue
                tol = max(2 * TICK, 0.1 * at[b])
                if abs(lv[a] - lv[b]) > tol:
                    continue
                if Ld[ix[a] + 1:ix[b]].min() > min(lv[a], lv[b]) - at[b]:
                    continue
                lvl = max(lv[a], lv[b])
                key = int(round(lvl / TICK))
                u = int(max(ce_[a], ce_[b]))
                if key not in eqs or u < eqs[key][1]:
                    eqs[key] = (float(lvl), u, tol)
    pools = [p for p in named if p[1] not in MINOR]
    minor = [p for p in named if p[1] in MINOR]
    eq_draws = []
    for lvl, u, tol in sorted(eqs.values()):
        if lvl - Ed <= 0:
            continue
        near = [p for p in pools if PRIO[p[1]] <= EQ_ABSORB and abs(p[0] - lvl) <= tol]
        if near:
            near.sort(key=lambda p: (PRIO[p[1]], abs(p[0] - lvl)))
            near[0][3] = True
        else:
            eq_draws.append([lvl, "EQ", u, True])
        minor = [p for p in minor if abs(p[0] - lvl) > tol]      # its member swings are this pool, not separate draws
    pools = pools + minor + eq_draws

    # live opposing FVGs (DOL-1): bearish gaps above for a long, bullish gaps below for a short; a target until a
    # 5m wick reaches the CE (D6); expiry 5m = end of the next CME day, 15m 5 days, 1H 10 days, 4H/1D never (10 nearest)
    pol = -1 if hi_side else 1
    gap_draws, zones = [], []
    for tfn in ("5m", "15m", "1h", "4h", "1d"):
        G = H.tf[tfn].gaps[pol]
        b = int(np.searchsorted(G["end"], T, side="right"))
        if tfn == "5m":
            a = int(np.searchsorted(G["dayk"], kd - 1, side="left"))
        elif tfn in FVG_LIFE_H:
            a = int(np.searchsorted(G["end"], T - FVG_LIFE_H[tfn] * 3600, side="left"))
        else:
            a = 0
        if b <= a:
            continue
        sl = slice(a, b)
        if hi_side:
            near_d, far_d, ce_d = G["bot"][sl], G["top"][sl], G["ce"][sl]
        else:
            near_d, far_d, ce_d = -G["top"][sl], -G["bot"][sl], -G["ce"][sl]
        if tfn in NEVER_EXPIRE:
            live = G["tag5"][sl] > i
        else:
            live = mx(G["first5"][sl]) < ce_d
        ok = live & (near_d - Ed > 0)
        idx = np.flatnonzero(ok)
        if tfn in NEVER_EXPIRE and len(idx) > 10:
            idx = idx[np.argsort(near_d[idx] - Ed)[:10]]
        ends = G["end"][sl]
        for q in idx:
            gap_draws.append([float(near_d[q]), FVG_SRC[tfn], int(ends[q]), False, float(far_d[q])])
            if tfn != "5m":
                zones.append((float(near_d[q]), float(far_d[q])))

    # obstacles (DOL-6): live opposing 15m+ gap zones + fresh 5m (k=2, today + previous CME day) and 15m (k=1, 5 days)
    # swing points, merged into price zones (a swing inside a gap, or items within max(2 ticks, 0.1 ATR5) of each
    # other, are one zone); a draw counts the zones that start strictly between entry and (draw - 2 ticks)
    s15, _, _, _ = swings("15m", SW_LB_H["15m"])
    items = sorted(zones + [(float(s), float(s)) for s in np.r_[s5_lv, s15] if s > Ed])
    merged = []
    for a_, z_ in items:
        if merged and a_ <= merged[-1][1] + tol5:
            merged[-1][1] = max(merged[-1][1], z_)
        else:
            merged.append([a_, z_])
    starts = np.array([z[0] for z in merged]) if merged else np.zeros(0)

    def obstacles(X):
        return int(((starts > Ed) & (starts < X - 2 * TICK)).sum())

    out = []
    for p in pools + gap_draws:
        lvl_d, src, usable, eq = p[0], p[1], p[2], p[3]
        dist = lvl_d - Ed
        if dist <= 0 or dist / R > MAX_R:
            continue
        x = {"kind": "IRL" if src.startswith("FVG") else "ERL", "source": src,
             "dist_atr": round(dist / atr5, 4), "dist_r": round(dist / R, 4), "obstacles": obstacles(lvl_d),
             "age_h": round((T - usable) / 3600.0, 3), "eq": bool(eq), "htf_dir": int(htf_dir), "session": session,
             "within_reach": bool(dist <= reach), "level": float(lvl_d * d), "level_d": float(lvl_d), "dist": float(dist)}
        if len(p) > 4:
            x["far"] = float(p[4] * d)
        out.append(x)
    out.sort(key=lambda x: x["dist"])
    return out, {"T": T, "atr5": atr5, "adr10": adr10, "reach": reach, "run_rng": run_rng}


# ============================================================================================ entries, labels, exits
def load_entries(H: History):
    with open(RUN_LIVE, encoding="utf-8") as fh:
        tr = json.load(fh)["trades"]
    out, bad = [], collections.Counter()
    for t in tr:
        et = int(t["entry_t"])
        jf = int(np.searchsorted(H.t, et))
        if jf >= len(H.t) or H.t[jf] != et or jf < 1:
            bad["no fill bar"] += 1
            continue
        i = jf - 1
        if H.t[i] != et - 300:
            bad["signal bar missing (used the previous bar)"] += 1
        d = int(t["dir"])
        fill = H.o[jf] + d * SLIP
        S = fill - d * float(t["risk_pts"])                      # the engine's stop exactly
        E = float(H.c[i])                                        # the signal-bar close (the engine's planned entry)
        R = (E - S) * d
        if R <= 0:
            bad["non-positive plan risk"] += 1
            continue
        f = t.get("f") or {}
        out.append({"day": t["day"], "month": t["day"][:7], "entry_t": et, "i": i, "dir": d, "E": E, "S": S, "R": R,
                    "risk_pts": float(t["risk_pts"]), "rr_plan": f.get("rr_plan"), "htf": int(np.sign(f.get("htf_trend") or 0)),
                    "eng_r": float(t.get("r") or 0.0), "eng_exit": t.get("exit")})
    return out, bad


def path_of(H: History, e):
    """Bars after the signal bar through the bar that ends 15:55 ET, same CME day, in direction space."""
    i, d = e["i"], e["dir"]
    k = i + 1
    kd = H.dayk[i]
    z = k
    n = len(H.t)
    while z < n and H.dayk[z] == kd and H.mod[z] < FLAT_MOD:
        z += 1
    sl = slice(k, z)
    if d == 1:
        return H.o[sl], H.h[sl], H.l[sl], H.c[sl]
    return -H.o[sl], -H.l[sl], -H.h[sl], -H.c[sl]


def simulate(path, Ed, Sd, R, target_d):
    """Exit at the target (limit, needs price at target + 1 tick), else the stop (stop first on ties, 1 tick slip),
    else the 15:55 close (market, 1 tick slip). Returns (R multiple, kind)."""
    od, hd, ld, cd = path
    if len(hd) == 0:
        return 0.0, "none"
    st = np.flatnonzero(ld <= Sd)
    tg = np.flatnonzero(hd >= target_d + TICK) if target_d is not None else np.zeros(0, np.int64)
    s = st[0] if len(st) else 10 ** 9
    g = tg[0] if len(tg) else 10 ** 9
    if s <= g and s < 10 ** 9:
        return (min(od[s], Sd) - SLIP - Ed) / R, "stop"
    if g < 10 ** 9:
        return (target_d - Ed) / R, "target"
    return (cd[-1] - SLIP - Ed) / R, "eod"


def build(H: History, entries, verbose=True):
    rows, trades = [], []
    t0 = time.time()
    for n, e in enumerate(entries):
        d = e["dir"]
        draws, info = enumerate_draws(H, e["i"], d, e["E"], e["R"], e["htf"])
        path = path_of(H, e)
        od, hd, ld, cd = path
        Ed, Sd = e["E"] * d, e["S"] * d
        st = np.flatnonzero(ld <= Sd)
        s = st[0] if len(st) else len(hd)
        mfe = float(hd[:s].max()) if s > 0 else -np.inf             # best price before the stop bar (stop wins ties)
        for x in draws:
            x["hit"] = int(x["level_d"] <= mfe)
            x["tid"] = n
            # realised R if this draw had been the target (limit 1 tick in front, plain exit): used by the EV checks
            x["r_real"], x["exit_kind"] = simulate(path, Ed, Sd, e["R"], x["level_d"] - TICK)
            rows.append(x)
        trades.append({**e, "draws": len(draws), "path": path, "mfe_r": (mfe - Ed) / e["R"] if s > 0 else 0.0,
                       "stopped": bool(len(st)), "atr5": info["atr5"], "reach": info["reach"]})
        if verbose and (n + 1) % 200 == 0:
            print(f"  {n + 1}/{len(entries)} entries, {len(rows)} draws, {time.time() - t0:.0f}s", flush=True)
    return rows, trades


# ============================================================================================ model
def fit_logit(X, y, lam, iters=40):
    n, p = X.shape
    mu = X.mean(0)
    sd = X.std(0)
    sd[sd < 1e-9] = 1.0
    Z = np.c_[np.ones(n), (X - mu) / sd]
    ybar = float(np.clip(y.mean(), 1e-4, 1 - 1e-4))
    b = np.zeros(p + 1)
    b[0] = math.log(ybar / (1 - ybar))
    P = np.full(p + 1, float(lam))
    P[0] = 0.0
    for _ in range(iters):
        pr = 1.0 / (1.0 + np.exp(-np.clip(Z @ b, -30, 30)))
        g = Z.T @ (y - pr) - P * b
        Hm = (Z * (pr * (1 - pr))[:, None]).T @ Z + np.diag(P)
        step = np.linalg.solve(Hm, g)
        b += step
        if np.max(np.abs(step)) < 1e-7:
            break
    return {"mu": mu, "sd": sd, "b0": float(b[0]), "b": b[1:]}


def pred(m, X):
    return 1.0 / (1.0 + np.exp(-np.clip(m["b0"] + ((X - m["mu"]) / m["sd"]) @ m["b"], -30, 30)))


def lam_for(n_rows, n_trades):
    """Ridge strength = 2 pseudo-trades per standardised coefficient (draws of one trade share one price path)."""
    return 2.0 * n_rows / max(n_trades, 1)


def walk_forward(X, y, tid, month_of_trade, cols=None, step="month", min_trades=MIN_TRAIN_TRADES):
    """Out-of-sample predictions: the model for month M is fitted only on draws of entries before month M."""
    Xc = X if cols is None else X[:, cols]
    months = sorted(set(month_of_trade))
    mt = np.array([month_of_trade[k] for k in tid])
    p = np.full(len(y), np.nan)
    ntr = collections.Counter(month_of_trade)
    seen = 0
    model = None
    first = None
    for mi, M in enumerate(months):
        refit = step == "month" or (int(M[5:7]) - 1) % 3 == 0 or model is None
        if seen >= min_trades:
            if first is None:
                first = M
            if refit or model is None:
                tr = mt < M
                model = fit_logit(Xc[tr], y[tr], lam_for(tr.sum(), seen))
            te = mt == M
            p[te] = pred(model, Xc[te])
        seen += ntr[M]
    return p, first


R_EDGES = [1, 1.5, 2, 3, 4, 6]          # dist_r bands for the miss table: <1, 1-1.5, 1.5-2, 2-3, 3-4, 4-6, 6-12
R_BAND_NAMES = ["<1R", "1-1.5R", "1.5-2R", "2-3R", "3-4R", "4-6R", "6-12R"]


def wf_miss_mean(y, rr, dr, tid, month_of_trade, first, k_shrink=20.0):
    """Walk-forward expected R of a MISS at each draw's distance band (training months only, shrunk to the overall
    training miss mean with k_shrink pseudo-draws)."""
    mt = np.array([month_of_trade[k] for k in tid])
    bi = np.searchsorted(R_EDGES, dr, side="right")
    out = np.full(len(y), np.nan)
    for M in sorted(set(mt)):
        if first is None or M < first:
            continue
        tr = (mt < M) & (y == 0)
        if not tr.any():
            continue
        overall = rr[tr].mean()
        s = np.bincount(bi[tr], weights=rr[tr], minlength=len(R_BAND_NAMES))
        c = np.bincount(bi[tr], minlength=len(R_BAND_NAMES))
        mb = (s + k_shrink * overall) / (c + k_shrink)
        te = mt == M
        out[te] = mb[bi[te]]
    return out


def fit_ridge(X, y, lam):
    mu = X.mean(0)
    sd = X.std(0)
    sd[sd < 1e-9] = 1.0
    Z = np.c_[np.ones(len(y)), (X - mu) / sd]
    P = np.full(Z.shape[1], float(lam))
    P[0] = 0.0
    b = np.linalg.solve(Z.T @ Z + np.diag(P), Z.T @ y)
    return {"mu": mu, "sd": sd, "b0": float(b[0]), "b": b[1:]}


def wf_ridge(X, y, tid, month_of_trade, first):
    """Walk-forward ridge regression of the realised R of targeting each draw (direct E[R] model)."""
    mt = np.array([month_of_trade[k] for k in tid])
    ntr = collections.Counter(month_of_trade)
    out = np.full(len(y), np.nan)
    seen = 0
    for M in sorted(set(month_of_trade)):
        if first is not None and M >= first:
            tr = mt < M
            m = fit_ridge(X[tr], y[tr], lam_for(tr.sum(), seen))
            te = mt == M
            out[te] = m["b0"] + ((X[te] - m["mu"]) / m["sd"]) @ m["b"]
        seen += ntr[M]
    return out


def logloss(y, p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean())


def auc(y, p):
    r = pd.Series(p).rank(method="average").values
    npos, nneg = y.sum(), len(y) - y.sum()
    if npos == 0 or nneg == 0:
        return float("nan")
    return float((r[y == 1].sum() - npos * (npos + 1) / 2) / (npos * nneg))


# ============================================================================================ decision rules
def rule_stats(rs):
    r = np.array([x[0] for x in rs]) if rs else np.zeros(0)
    if not len(r):
        return {"n": 0}
    gp, gl = r[r > 0].sum(), -r[r < 0].sum()
    kinds = collections.Counter(x[1] for x in rs)
    return {"n": int(len(r)), "avg_r": float(r.mean()), "total_r": float(r.sum()), "win": float((r > 0).mean() * 100),
            "pf": float(gp / gl) if gl > 0 else float("inf"), "tgt": float(kinds["target"] / len(r) * 100),
            "stop": float(kinds["stop"] / len(r) * 100), "eod": float(kinds["eod"] / len(r) * 100)}


def boot_diff(a, b, n=4000, seed=11):
    """95% CI of mean(b - a) with paired bootstrap over trades."""
    a, b = np.asarray(a), np.asarray(b)
    if len(a) < 5:
        return [float("nan"), float("nan")]
    rng = np.random.default_rng(seed)
    dd = b - a
    m = dd[rng.integers(0, len(dd), (n, len(dd)))].mean(1)
    return [float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))]


def decide(trades, rows_by_t, rules):
    """Per trade and rule: (R, exit kind, chosen dist_r). rows_by_t[tid] = list of dicts {x, p, pd, m, er}:
    p = full-model P(hit), pd = distance-only P(hit), m = expected R of a miss at that distance, er = regression E[R]."""
    res = {k: {} for k in rules}
    for tid, tr in enumerate(trades):
        if tid not in rows_by_t:
            continue
        d, R = tr["dir"], tr["R"]
        Ed, Sd = tr["E"] * d, tr["S"] * d
        path = tr["path"]
        cand = rows_by_t[tid]
        for name, spec in rules.items():
            kind = spec[0]
            tgt, cr = None, None
            if kind == "engine":
                if tr["rr_plan"] is not None:
                    cr = float(tr["rr_plan"])
                    tgt = Ed + cr * R
            elif kind == "fixed":
                cr = spec[1]
                tgt = Ed + cr * R
            elif kind == "ev":
                min_r, which, erl_only = spec[1], spec[2], spec[3]
                best = None
                for z in cand:
                    x = z["x"]
                    if x["dist_r"] < min_r or (erl_only and x["kind"] != "ERL"):
                        continue
                    if which == "er":
                        e = z["er"]
                    else:
                        p = z["p"] if which in ("full", "adj") else z["pd"]
                        if which == "adj":           # miss = what misses at this distance really returned, not -1R
                            e = p * (x["dist_r"] - TICK / R) + (1 - p) * z["m"]
                        else:                        # the brief's EV: every miss costs the full 1R
                            e = p * x["dist_r"] - (1 - p)
                    if not np.isfinite(e):
                        continue
                    if best is None or e > best[0]:
                        best = (e, x)
                if best is not None:
                    cr = best[1]["dist_r"]
                    tgt = best[1]["level_d"] - TICK
                elif tr["rr_plan"] is not None:          # no qualifying draw: the current rule's target
                    cr = float(tr["rr_plan"])
                    tgt = Ed + cr * R
            elif kind == "nearest":
                min_r, erl_only = spec[1], spec[2]
                c2 = [z["x"] for z in cand if z["x"]["dist_r"] >= min_r and (not erl_only or z["x"]["kind"] == "ERL")]
                if c2:
                    x = min(c2, key=lambda z: z["dist_r"])
                    cr, tgt = x["dist_r"], x["level_d"] - TICK
                elif tr["rr_plan"] is not None:
                    cr = float(tr["rr_plan"])
                    tgt = Ed + cr * R
            if tgt is None:
                continue
            r, k = simulate(path, Ed, Sd, R, tgt)
            res[name][tid] = (r, k, cr)
    return res


# ============================================================================================ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true", help="skip the drop-one feature ranking")
    ap.add_argument("--check", type=int, default=0, help="print the draws of N sample entries and stop")
    ap.add_argument("--no-write", action="store_true", help="do not write the model / report")
    a = ap.parse_args()
    t0 = time.time()
    from tools.strategy_lab import bars
    df = bars("NQ", "5m")
    H = History(df)
    del df
    print(f"history: {len(H.t)} 5m bars, {len(H.udays)} CME days, built in {time.time() - t0:.0f}s", flush=True)
    entries, bad = load_entries(H)
    print(f"entries: {len(entries)} usable ({dict(bad)})", flush=True)
    if a.check:
        for e in entries[:: max(1, len(entries) // a.check)][:a.check]:
            ds, info = enumerate_draws(H, e["i"], e["dir"], e["E"], e["R"], e["htf"])
            print(f"\n{e['day']} {'LONG' if e['dir'] == 1 else 'SHORT'} E={e['E']:.2f} S={e['S']:.2f} R={e['R']:.2f} "
                  f"rr_plan={e['rr_plan']} atr5={info['atr5']:.2f} adr10={info['adr10']:.1f} reach={info['reach']:.1f}")
            for x in ds[:40]:
                print(f"   {x['source']:6s} {x['kind']} lvl={x['level']:.2f} r={x['dist_r']:.2f} atr={x['dist_atr']:.2f} "
                      f"obst={x['obstacles']} age={x['age_h']:.1f}h eq={int(x['eq'])} reach={int(x['within_reach'])}")
        return
    rows, trades = build(H, entries)
    print(f"draws: {len(rows)} from {len(trades)} entries ({len(rows) / max(len(trades), 1):.1f} per entry), "
          f"{time.time() - t0:.0f}s", flush=True)
    results = analyse(rows, trades, quick=a.quick)
    results["bad_entries"] = dict(bad)
    results["runtime_s"] = round(time.time() - t0, 1)
    if not a.no_write:
        write_model(rows, trades)
        write_report(results)
    print(f"done in {time.time() - t0:.0f}s")


def design(rows):
    X = np.array([DL.design_row(x) for x in rows], dtype=float)
    y = np.array([x["hit"] for x in rows], dtype=float)
    tid = np.array([x["tid"] for x in rows], dtype=np.int64)
    return X, y, tid


def analyse(rows, trades, quick=False):
    X, y, tid = design(rows)
    month_of_trade = [t["month"] for t in trades]
    names = list(DL.FEATURE_NAMES)
    dist_cols = [names.index(c) for c in DL.GROUPS["dist_r"] + DL.GROUPS["dist_atr"]]
    p_full, first = walk_forward(X, y, tid, month_of_trade)
    p_dist, _ = walk_forward(X, y, tid, month_of_trade, cols=dist_cols)
    oos = np.isfinite(p_full)
    # base rate: training-period mean, walk-forward
    mt = np.array([month_of_trade[k] for k in tid])
    p_base = np.full(len(y), np.nan)
    for M in sorted(set(mt[oos])):
        p_base[mt == M] = y[mt < M].mean()
    R = {"n_rows": int(len(y)), "n_trades": len(trades), "first_oos_month": first, "hit_rate": float(y.mean())}
    dr = np.array([x["dist_r"] for x in rows])
    rel = oos & (dr >= 1.0)
    R["metrics"] = {}
    for nm, m in (("all OOS draws", oos), ("OOS draws with dist_r >= 1", rel)):
        R["metrics"][nm] = {k: {"logloss": logloss(y[m], p[m]), "brier": float(((p[m] - y[m]) ** 2).mean()),
                                "auc": auc(y[m], p[m]) if k != "base rate" else 0.5}
                            for k, p in (("full model", p_full), ("distance only", p_dist), ("base rate", p_base))}
        R["metrics"][nm]["n"] = int(m.sum())
    # calibration by decile (OOS)
    def calib(m, p):
        q = np.quantile(p[m], np.linspace(0, 1, 11))
        out = []
        for k in range(10):
            mm = m & (p >= q[k]) & ((p <= q[k + 1]) if k == 9 else (p < q[k + 1]))
            if mm.sum():
                out.append({"decile": k + 1, "n": int(mm.sum()), "pred": float(p[mm].mean()), "actual": float(y[mm].mean())})
        return out
    R["calib_all"] = calib(oos, p_full)
    R["calib_rel"] = calib(rel, p_full)
    R["calib_dist_rel"] = calib(rel, p_dist)
    # hit-rate tables (all labelled draws; OOS mean prediction alongside)
    def table(keyf, m=None):
        m = np.ones(len(y), bool) if m is None else m
        g = collections.defaultdict(list)
        for k in np.flatnonzero(m):
            g[keyf(rows[k])].append(k)
        out = []
        for key, ks in g.items():
            ks = np.array(ks)
            o = ks[oos[ks]]
            out.append({"key": key, "n": int(len(ks)), "trades": int(len(set(tid[ks]))), "hit": float(y[ks].mean()),
                        "avg_dist_r": float(dr[ks].mean()),
                        "oos_pred": float(p_full[o].mean()) if len(o) else None, "oos_hit": float(y[o].mean()) if len(o) else None})
        return out
    def band(v, edges, fmt="{:g}"):
        for lo, hi in zip(edges[:-1], edges[1:]):
            if lo <= v < hi:
                return f"{fmt.format(lo)}-{fmt.format(hi)}" if hi < 1e8 else f">={fmt.format(lo)}"
        return "other"
    R["by_source"] = sorted(table(lambda x: x["source"]), key=lambda z: DL.SOURCES.index(z["key"]))
    R["by_kind"] = table(lambda x: x["kind"])
    R["by_obstacles"] = sorted(table(lambda x: min(x["obstacles"], 6)), key=lambda z: z["key"])
    R["by_dist_atr"] = sorted(table(lambda x: band(x["dist_atr"], [0, 1, 2, 3, 5, 8, 12, 20, 1e9])),
                              key=lambda z: float(z["key"].replace(">=", "").split("-")[0]))
    R["by_dist_r"] = sorted(table(lambda x: band(x["dist_r"], [0, 0.5, 1, 1.5, 2, 3, 4, 6, 1e9])),
                            key=lambda z: float(z["key"].replace(">=", "").split("-")[0]))
    R["by_eq"] = table(lambda x: bool(x["eq"]))
    R["by_reach"] = table(lambda x: bool(x["within_reach"]))
    R["by_htf"] = sorted(table(lambda x: x["htf_dir"]), key=lambda z: z["key"])
    R["by_session"] = table(lambda x: x["session"])
    R["by_age"] = sorted(table(lambda x: band(x["age_h"], [0, 1, 4, 12, 24, 72, 168, 1e9])),
                         key=lambda z: float(z["key"].replace(">=", "").split("-")[0]))
    # matched-distance view: hit rate by source inside R bands, and reach / obstacles inside R bands
    for nm, keyf in (("src_x_r", lambda x: x["source"]), ("reach_x_r", lambda x: "in reach" if x["within_reach"] else "beyond reach"),
                     ("obst_x_r", lambda x: f"obst {min(x['obstacles'], 3)}{'+' if x['obstacles'] >= 3 else ''}"),
                     ("kind_x_r", lambda x: x["kind"])):
        tab = collections.defaultdict(dict)
        for lo, hi in ((1, 2), (2, 3), (3, 5), (5, 12.01)):
            m = (dr >= lo) & (dr < hi)
            for z in table(keyf, m):
                tab[z["key"]][f"{lo}-{int(hi)}R"] = (z["hit"], z["n"], z["trades"])
        R[nm] = tab
    # coefficients of the final model (standardised)
    lam = lam_for(len(y), len(trades))
    fm = fit_logit(X, y, lam)
    R["coef"] = sorted(((names[k], float(fm["b"][k])) for k in range(len(names))), key=lambda z: -abs(z[1]))
    R["lambda"] = lam
    # what a miss really costs, by distance (in-sample, descriptive): misses at 15:55 are not -1R
    rr = np.array([x["r_real"] for x in rows])
    ek = np.array([x["exit_kind"] for x in rows])
    bi = np.searchsorted(R_EDGES, dr, side="right")
    R["miss_table"] = []
    for b_, nm in enumerate(R_BAND_NAMES):
        m = bi == b_
        ms = m & (y == 0)
        if not m.any():
            continue
        R["miss_table"].append({"band": nm, "n": int(m.sum()), "hit": float(y[m].mean()), "avg_r": float(rr[m].mean()),
                                "miss_r": float(rr[ms].mean()) if ms.any() else None,
                                "miss_stop": float((ek[ms] == "stop").mean() * 100) if ms.any() else None,
                                "miss_eod": float((ek[ms] == "eod").mean() * 100) if ms.any() else None})
    m_miss = wf_miss_mean(y, rr, dr, tid, month_of_trade, first)
    er_hat = wf_ridge(X, np.clip(rr, -1.5, MAX_R), tid, month_of_trade, first)
    # decision rules on entries with OOS predictions
    rows_by_t = collections.defaultdict(list)
    for k in np.flatnonzero(oos):
        rows_by_t[int(tid[k])].append({"x": rows[k], "p": float(p_full[k]), "pd": float(p_dist[k]), "m": float(m_miss[k]),
                                       "er": float(er_hat[k])})
    rules = {"current (engine target)": ("engine",), "learned max-EV, any draw >= 1R": ("ev", 1.0, "full", False),
             "learned max-EV, ERL >= 1.5R": ("ev", 1.5, "full", True),
             "distance-only max-EV, any draw >= 1R": ("ev", 1.0, "dist", False),
             "learned max-EV miss-adjusted, any draw >= 1R": ("ev", 1.0, "adj", False),
             "learned max-EV miss-adjusted, ERL >= 1.5R": ("ev", 1.5, "adj", True),
             "learned E[R] regression, any draw >= 1R": ("ev", 1.0, "er", False),
             "nearest draw >= 1R": ("nearest", 1.0, False), "nearest ERL >= 1.5R": ("nearest", 1.5, True),
             "fixed 1R": ("fixed", 1.0), "fixed 1.5R": ("fixed", 1.5), "fixed 2R": ("fixed", 2.0), "fixed 3R": ("fixed", 3.0)}
    res = decide(trades, rows_by_t, rules)
    # sanity: the unmanaged replay of the engine target must reproduce the engine's own STOP / TARGET exits
    agree, tot = collections.Counter(), collections.Counter()
    for k, v in res["current (engine target)"].items():
        ex = trades[k]["eng_exit"]
        if ex in ("STOP", "TARGET"):
            tot[ex] += 1
            agree[ex] += int(v[1] == ex.lower())
    R["sanity"] = {ex: f"{agree[ex]}/{tot[ex]}" for ex in tot}
    periods = {"2026": ("2026-01-01", "2026-12-31"), "2025": ("2025-01-01", "2025-12-31"),
               "2026 Jan-Jul (before the tuning window)": ("2026-01-01", "2026-07-31"),
               f"all OOS ({first}..2026-10)": ("0000", "9999")}
    R["rules"] = {}
    for pn, (lo, hi) in periods.items():
        ids = [k for k in range(len(trades)) if lo <= trades[k]["day"] <= hi and k in res["current (engine target)"]
               and k in res["learned max-EV, any draw >= 1R"]]
        R["rules"][pn] = {"n_trades": len(ids)}
        base = [res["current (engine target)"][k][0] for k in ids]
        for rn in rules:
            rs = [res[rn][k] for k in ids if k in res[rn]]
            s = rule_stats(rs)
            s["avg_target_r"] = float(np.mean([x[2] for x in rs])) if rs else None
            if rn != "current (engine target)" and len(rs) == len(ids):
                s["diff_vs_current"] = float(np.mean([x[0] for x in rs]) - np.mean(base)) if ids else None
                s["diff_ci95"] = boot_diff(base, [x[0] for x in rs])
            R["rules"][pn][rn] = s
    # monthly R, 2026 and 2025
    R["monthly"] = {}
    for rn in ("current (engine target)", "learned max-EV, any draw >= 1R", "learned max-EV miss-adjusted, any draw >= 1R",
               "learned max-EV, ERL >= 1.5R", "fixed 2R"):
        mm = collections.defaultdict(float)
        cnt = collections.Counter()
        for k, v in res[rn].items():
            if trades[k]["day"] >= "2025-01-01":
                mm[trades[k]["month"]] += v[0]
                cnt[trades[k]["month"]] += 1
        R["monthly"][rn] = {m: (round(mm[m], 2), cnt[m]) for m in sorted(mm)}
    # sanity: the engine's real (managed) R on the same entries vs the unmanaged current-rule replay
    ids26 = [k for k in res["current (engine target)"] if trades[k]["day"] >= "2026-01-01"]
    R["engine_real_2026"] = {"n": len(ids26), "avg_r_engine_managed": float(np.mean([trades[k]["eng_r"] for k in ids26])) if ids26 else None,
                             "avg_r_unmanaged_replay": float(np.mean([res["current (engine target)"][k][0] for k in ids26])) if ids26 else None}
    # feature ranking: drop-one and single-feature walk-forward log-loss (quarterly refits)
    if not quick:
        groups = DL.GROUPS
        p_q, _ = walk_forward(X, y, tid, month_of_trade, step="quarter")
        ll_full_rel, ll_full = logloss(y[rel], p_q[rel]), logloss(y[oos], p_q[oos])
        ll_base_rel, ll_base = logloss(y[rel], p_base[rel]), logloss(y[oos], p_base[oos])
        imp = []
        for g, cols_g in groups.items():
            gi = [names.index(c) for c in cols_g]
            keep = [k for k in range(len(names)) if k not in gi]
            pd_, _ = walk_forward(X, y, tid, month_of_trade, cols=keep, step="quarter")
            ps_, _ = walk_forward(X, y, tid, month_of_trade, cols=gi, step="quarter")
            imp.append({"feature": g, "drop_one_rel": logloss(y[rel], pd_[rel]) - ll_full_rel,
                        "drop_one_all": logloss(y[oos], pd_[oos]) - ll_full,
                        "alone_rel": ll_base_rel - logloss(y[rel], ps_[rel]), "alone_all": ll_base - logloss(y[oos], ps_[oos]),
                        "alone_auc_rel": auc(y[rel], ps_[rel])})
            print(f"  importance {g:12s} drop-one dLL(rel) {imp[-1]['drop_one_rel']:+.5f}  alone gain(rel) {imp[-1]['alone_rel']:+.5f}",
                  flush=True)
        R["importance"] = sorted(imp, key=lambda z: -z["drop_one_rel"])
        R["importance_ref"] = {"ll_full_rel": ll_full_rel, "ll_base_rel": ll_base_rel}
    # console summary
    print("sanity (engine exit reproduced by the unmanaged replay):", R["sanity"])
    for z in R["miss_table"]:
        print(f"  {z['band']:7s} n={z['n']:5d} hit {z['hit'] * 100:5.1f}%  avgR {z['avg_r']:+.3f}  miss R {z['miss_r'] if z['miss_r'] is None else round(z['miss_r'], 3)}"
              f"  miss->stop {z['miss_stop'] if z['miss_stop'] is None else round(z['miss_stop'])}%")
    for pn, v in R["rules"].items():
        print(f"\n== {pn}: {v['n_trades']} trades")
        for rn in rules:
            s = v[rn]
            if s.get("n"):
                print(f"  {rn:38s} avgR {s['avg_r']:+.3f}  win {s['win']:5.1f}%  PF {s['pf']:.2f}  tgt {s['tgt']:4.1f}%  "
                      f"avg tgt {s['avg_target_r'] or 0:.2f}R  diff {s.get('diff_vs_current', 0) or 0:+.3f} {s.get('diff_ci95', '')}")
    for nm, v in R["metrics"].items():
        print(nm, {k: {kk: round(vv, 4) for kk, vv in m.items()} if isinstance(m, dict) else m for k, m in v.items()})
    return R


def write_model(rows, trades):
    X, y, tid = design(rows)
    lam = lam_for(len(y), len(trades))
    m = fit_logit(X, y, lam)
    out = {"version": 1, "created": dt.datetime.now().isoformat(timespec="seconds"),
           "trained_through": max(t["day"] for t in trades), "trained_from": min(t["day"] for t in trades),
           "n_trades": len(trades), "n_draws": int(len(y)), "base_rate": float(y.mean()), "lambda": lam,
           "features": list(DL.FEATURE_NAMES), "intercept": m["b0"], "coef": [float(v) for v in m["b"]],
           "mu": [float(v) for v in m["mu"]], "sd": [float(v) for v in m["sd"]],
           "label": "draw touched before the stop (stop wins same-bar ties), before 15:55 ET, same CME day",
           "entries": "research/five_year/run_live.json (engine live-loop replay, NQ1! 5m)",
           "definitions": "research/lab/DRAW_LEARNER.md (DOL_PLAYBOOK.md D1-D9, DOL-1/4/6)"}
    with open(MODEL_OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)
    # round trip through the live module
    DL.load_model(reload=True)
    chk = [DL.predict(rows[k]) for k in range(0, len(rows), max(1, len(rows) // 50))]
    ref = pred(m, X[::max(1, len(rows) // 50)])
    assert all(c is not None for c in chk) and np.max(np.abs(np.array(chk) - ref)) < 1e-9, "module / trainer mismatch"
    print(f"model written: {MODEL_OUT} ({len(y)} draws, {len(trades)} trades); module round-trip OK")


# ============================================================================================ report
def _f(v, nd=3, sign=False):
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return "-"
    return f"{v:+.{nd}f}" if sign else f"{v:.{nd}f}"


def write_report(R):
    L = []
    w = L.append
    rk = R["rules"]
    p26 = rk["2026"]
    cur, lrn = p26["current (engine target)"], p26["learned max-EV, any draw >= 1R"]
    w("# Draw learner: which draws on liquidity does price actually reach?")
    w("")
    w(f"Built {dt.datetime.now():%Y-%m-%d %H:%M} ET by `tools/train_draw_learner.py` (runtime {R.get('runtime_s')} s). "
      "Model for live use: `data/draw_learner.json`, read by `engine/draw_learner.py` (`predict(features)`). "
      "**Every number below is walk-forward (out of sample) unless it says otherwise.**")
    w("")
    w("## Verdict")
    w("")
    w("VERDICT_PLACEHOLDER")
    w("")
    w("## Data and method")
    w("")
    w(f"- **Entries:** {R['n_trades']} NQ trades of the engine's live-loop replay (`research/five_year/run_live.json`, "
      "2021-11 .. 2026-10). Real CME NQ1! 5m bars only (`data/NQ_5m.csv`).")
    w("- **Entry, stop:** `entry_t` in run_live.json is the *fill* bar (the engine fills at the open of the bar after the "
      "signal). The decision is taken at the close of the signal bar (`entry_t - 5m`): entry E = that close (the engine's "
      "planned entry), stop S = the engine's real stop = fill - dir x risk_pts (fill = next open + 1 tick). R = |E - S|. "
      "Using the close of the bar *starting* at `entry_t` would peek 5 minutes ahead, so it is not used.")
    w(f"- **Draws:** {R['n_rows']} candidate draws ({R['n_rows'] / R['n_trades']:.1f} per entry), enumerated causally at the signal "
      "close from 5m bars only (definitions below). Draws further than 12R are not enumerated.")
    w(f"- **Label:** hit = price touches the draw before the stop (a bar that touches both counts as a stop), before 15:55 ET, "
      f"same CME day. Base hit rate {R['hit_rate'] * 100:.1f}%.")
    w(f"- **Model:** L2 logistic regression (numpy IRLS, standardised features, ridge = 2 pseudo-trades per coefficient: "
      f"lambda {R['lambda']:.0f}). Features in `engine/draw_learner.py` (`design_row`). Walk-forward by month: the model for "
      f"month M is fitted only on entries before M; first predicted month {R['first_oos_month']} (after {MIN_TRAIN_TRADES} trades).")
    w("- **Decision rules** use the same entry and stop and a plain exit: the target if touched first (limit 1 tick in front "
      "of the draw, needs a touch of the draw), else the stop (1 tick slippage, stop first on ties), else the 15:55 close "
      "(1 tick slippage). No break-even, time stop or giveback, so this isolates the *target choice*. "
      "`current` = the engine's own planned target for that trade (nearest major pool >= 1.5R, 5R cap, 2R fallback; read from "
      "`rr_plan`). `learned max-EV` = the draw with the highest EV = p x dist_r - (1 - p) among draws >= 1R (falls back to "
      "the current target when none qualifies).")
    w("")
    w("## Feature definitions (match these exactly when calling `predict`)")
    w("")
    w("All prices in the trade direction (long: above entry; short: below). Definitions follow `research/lab/DOL_PLAYBOOK.md`.")
    w("")
    w("| feature | definition |")
    w("|---|---|")
    w("| `kind` | `IRL` for FVG draws, `ERL` for every resting pool (day/week/session H-L, swings, EQ) |")
    w("| `source` | `PDH`/`PDL` previous CME day H/L (usable from 18:00); `PWH`/`PWL` previous week H/L (usable from Sunday 18:00); "
      "`RTH` previous day's 09:30-16:00 H/L (from 16:00); `ASIA` 20:00-00:00 H/L (from 00:00), `LON` 02:00-05:00 (from 05:00), "
      "`ON` 18:00-09:30 (from 09:30), today's sessions only; `D1SW`/`H4SW`/`H1SW`/`M15SW` confirmed 3-bar fractal swings (k=1) "
      "on daily / 4H / 1H / 15m bars built from 5m, tracked 60 / 30 / 10 / 5 days after confirming; `M5SW` 5m k=2 swings "
      "confirmed today or on the previous CME day; `EQ` equal highs/lows (D8) not coinciding with a named pool; `FVG5`/`FVG15`/"
      "`FVG1H`/`FVG4H`/`FVG1D` live opposing fair value gaps. Same price on several lenses = one draw with the most significant "
      "source (PW > PD > RTH > LON > ASIA > ON > D1SW > H4SW > H1SW > M15SW > M5SW). |")
    w("| pool taken | a 5m high >= level + 1 tick (low <= level - 1 tick) at any bar since the pool became usable: it is no longer a draw |")
    w("| FVG | 3-candle gap on 5m/15m/1H/4H/1D (15m/1H clock-aligned, 4H anchored 18:00 ET, 1D = CME day, all built from closed "
      "5m bars; known at the close of candle 3). Min size 5m = max(1 tick, 0.1 x Wilder ATR14(5m)), else 1 tick. Draw = bearish "
      "gap above (long) / bullish gap below (short); level = its **near edge**. It stops being a draw when **any 5m wick touches "
      "its CE** (50%). Expiry: 5m at the end of the next CME day, 15m after 5 days, 1H after 10 days, 4H/1D never (the 10 "
      "nearest per side are kept). |")
    w("| `eq` | true when the draw is a D8 EQH/EQL pool or a named pool (H1SW or more significant) within its tolerance: two "
      "confirmed swings on the same TF (5m k=2 today+yesterday, 15m, 1H) within max(2 ticks, 0.1 x Wilder ATR14 of that TF at "
      "the 2nd confirmation), >= 3 bars apart, with a pullback of >= 1 ATR_tf between them; level = the higher (lower) one; "
      "usable when the 2nd swing confirms. M15SW / M5SW swings inside an EQ pool are folded into it. |")
    w("| `dist_atr` | (draw - entry) x dir / Wilder ATR14 of the closed 5m bars at the signal bar |")
    w("| `dist_r` | (draw - entry) x dir / (entry - stop) x dir |")
    w("| `obstacles` | DOL-6 n_res as price zones: live opposing 15m/1H/4H/1D gaps (near-far interval) and fresh untaken swing "
      "points (5m k=2 confirmed today or yesterday, 15m k=1 of the last 5 days) beyond entry, sorted and merged when an item "
      "starts within max(2 ticks, 0.1 ATR5) of the previous zone's end; obstacles = number of zones starting strictly between "
      "entry and (draw - 2 ticks). Same rule as `engine/liquidity_map.draws()`. |")
    w("| `age_h` | hours from when the pool/gap became usable (table above; swings: close of the confirming bar; FVG: close of "
      "candle 3; EQ: 2nd confirmation) to the signal close |")
    w("| `htf_dir` | engine 1H structure trend x trade direction (+1 / 0 / -1), i.e. the engine's `features['htf_trend']` |")
    w("| `session` | `AM` if the signal bar opens before 12:00 ET, else `PM` |")
    w("| `within_reach` | dist (points) <= max(0.5 x ADR10, ADR10 - (running CME-day high - low through the signal bar)); "
      "ADR10 = mean high-low of the last 10 completed CME days |")
    w("")
    w("## Out-of-sample fit")
    w("")
    w("| draws | model | log-loss | Brier | AUC |")
    w("|---|---|---:|---:|---:|")
    for nm, v in R["metrics"].items():
        for k in ("full model", "distance only", "base rate"):
            w(f"| {nm} (n={v['n']}) | {k} | {v[k]['logloss']:.4f} | {v[k]['brier']:.4f} | {_f(v[k]['auc'])} |")
    w("")
    w("### Calibration (walk-forward predictions, by decile of predicted p)")
    w("")
    w("| decile | all draws: n | predicted | actual | draws >= 1R: n | predicted | actual |")
    w("|---:|---:|---:|---:|---:|---:|---:|")
    for a_, b_ in zip(R["calib_all"], R["calib_rel"]):
        w(f"| {a_['decile']} | {a_['n']} | {a_['pred'] * 100:.1f}% | {a_['actual'] * 100:.1f}% | {b_['n']} | "
          f"{b_['pred'] * 100:.1f}% | {b_['actual'] * 100:.1f}% |")
    w("")
    if R.get("importance"):
        w("### Which features predict (walk-forward, quarterly refits)")
        w("")
        w("`drop-one` = how much worse the out-of-sample log-loss gets without the feature (unique information); `alone` = "
          "log-loss gain of a model with only that feature over the base rate. Draws >= 1R (the decision region), x 1000.")
        w("")
        w("| feature | drop-one (x1000) | alone (x1000) | alone AUC | drop-one, all draws (x1000) |")
        w("|---|---:|---:|---:|---:|")
        for z in R["importance"]:
            w(f"| {z['feature']} | {z['drop_one_rel'] * 1000:+.2f} | {z['alone_rel'] * 1000:+.2f} | {_f(z['alone_auc_rel'])} | "
              f"{z['drop_one_all'] * 1000:+.2f} |")
        w("")
    w("### Final-model coefficients (standardised; positive = more likely to be hit)")
    w("")
    w("| term | coef | term | coef |")
    w("|---|---:|---|---:|")
    cf = R["coef"]
    half = (len(cf) + 1) // 2
    for k in range(half):
        a_ = cf[k]
        b_ = cf[k + half] if k + half < len(cf) else ("", None)
        w(f"| {a_[0]} | {a_[1]:+.3f} | {b_[0]} | {_f(b_[1], 3, True) if b_[1] is not None else ''} |")
    w("")
    w("## Hit rates (all labelled draws; OOS columns = walk-forward months only)")
    w("")
    for title, key in (("source", "by_source"), ("kind", "by_kind"), ("obstacles (6 = 6+)", "by_obstacles"),
                       ("dist_atr", "by_dist_atr"), ("dist_r", "by_dist_r"), ("within_reach", "by_reach"), ("eq", "by_eq"),
                       ("htf_dir", "by_htf"), ("session", "by_session"), ("age_h", "by_age")):
        w(f"**By {title}**")
        w("")
        w("| value | draws | trades | hit % | avg dist_r | OOS predicted % | OOS actual % |")
        w("|---|---:|---:|---:|---:|---:|---:|")
        for z in R[key]:
            w(f"| {z['key']} | {z['n']} | {z['trades']} | {z['hit'] * 100:.1f} | {z['avg_dist_r']:.2f} | "
              f"{_f(z['oos_pred'] * 100 if z['oos_pred'] is not None else None, 1)} | "
              f"{_f(z['oos_hit'] * 100 if z['oos_hit'] is not None else None, 1)} |")
        w("")
    w("**At matched distance** (hit % [draws / trades] inside R bands; distance dominates everything, so compare along a column)")
    w("")
    for nm, title in (("src_x_r", "source"), ("kind_x_r", "kind"), ("reach_x_r", "within_reach"), ("obst_x_r", "obstacles")):
        tab = R[nm]
        cols = ["1-2R", "2-3R", "3-5R", "5-12R"]
        w(f"| {title} | " + " | ".join(cols) + " |")
        w("|---|" + "---:|" * len(cols))
        keys = sorted(tab, key=lambda k: (DL.SOURCES.index(k) if k in DL.SOURCES else 99, str(k)))
        for k in keys:
            cells = []
            for c in cols:
                v = tab[k].get(c)
                cells.append(f"{v[0] * 100:.0f}% [{v[1]}/{v[2]}]" if v and v[1] >= 20 else (f"({v[0] * 100:.0f}% n={v[1]})" if v else "-"))
            w(f"| {k} | " + " | ".join(cells) + " |")
        w("")
    w("## Decision rule: learned max-EV draw vs the current target")
    w("")
    w("Same entries, same stop, plain exit (target / stop / 15:55). R per trade; PF = sum of winning R / sum of losing R. "
      "`diff` = mean R per trade minus the current rule, with a paired bootstrap 95% CI.")
    w("")
    for pn, v in rk.items():
        w(f"**{pn}** ({v['n_trades']} trades)")
        w("")
        w("| rule | avg R | total R | win % | PF | target % | stop % | 15:55 % | avg target R | diff vs current [95% CI] |")
        w("|---|---:|---:|---:|---:|---:|---:|---:|---:|---|")
        for rn, s in v.items():
            if rn == "n_trades" or not s.get("n"):
                continue
            ci = s.get("diff_ci95")
            dtxt = f"{s['diff_vs_current']:+.3f} [{ci[0]:+.3f}, {ci[1]:+.3f}]" if s.get("diff_vs_current") is not None else "-"
            w(f"| {rn} | {s['avg_r']:+.3f} | {s['total_r']:+.1f} | {s['win']:.1f} | {s['pf']:.2f} | {s['tgt']:.0f} | "
              f"{s['stop']:.0f} | {s['eod']:.0f} | {_f(s['avg_target_r'], 2)} | {dtxt} |")
        w("")
    w("**What a miss really costs** (all labelled draws, in-sample, descriptive). The brief's EV charges -1R for every "
      "miss; a miss that is still open at 15:55 exits at the market instead, so far targets are under-valued by that formula. "
      "`miss-adjusted` rules replace the -1R by the walk-forward mean R of past misses in the same distance band.")
    w("")
    w("| dist_r band | draws | hit % | avg realised R if targeted | avg R of a miss | misses ending at the stop % | misses ending at 15:55 % |")
    w("|---|---:|---:|---:|---:|---:|---:|")
    for z in R["miss_table"]:
        w(f"| {z['band']} | {z['n']} | {z['hit'] * 100:.1f} | {z['avg_r']:+.3f} | {_f(z['miss_r'], 3, True)} | "
          f"{_f(z['miss_stop'], 0)} | {_f(z['miss_eod'], 0)} |")
    w("")
    w(f"Replay check: replaying each trade with the engine's own target reproduces the engine's STOP / TARGET exits on "
      f"{', '.join(f'{k} {v}' for k, v in R['sanity'].items())} trades (the rest left early through the engine's "
      "management before reaching either).")
    w("")
    w("**Monthly R (sum over the month's trades), 2025-2026**")
    w("")
    rns = list(R["monthly"])
    w("| month | trades | " + " | ".join(rns) + " |")
    w("|---|---:|" + "---:|" * len(rns))
    months = sorted(set().union(*[set(v) for v in R["monthly"].values()]))
    for m in months:
        n_ = R["monthly"][rns[0]].get(m, (0, 0))[1]
        w(f"| {m} | {n_} | " + " | ".join(_f(R["monthly"][rn].get(m, (None, 0))[0], 2, True) for rn in rns) + " |")
    w("")
    er = R["engine_real_2026"]
    w(f"Reference: on the same {er['n']} 2026 entries the engine's real managed result (BE at 1R, 30-min time stop, giveback, "
      f"news flat) averaged {_f(er['avg_r_engine_managed'], 3, True)}R; the unmanaged replay of its target averages "
      f"{_f(er['avg_r_unmanaged_replay'], 3, True)}R.")
    w("")
    w("CAVEATS_PLACEHOLDER")
    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    txt = "\n".join(L) + "\n"
    txt = txt.replace("VERDICT_PLACEHOLDER", verdict(R)).replace("CAVEATS_PLACEHOLDER", caveats(R))
    with open(REPORT, "w", encoding="utf-8") as fh:
        fh.write(txt)
    print(f"report written: {REPORT}")


def verdict(R):
    rk = R["rules"]
    out = []
    for pn in ("2026", "2025", "2026 Jan-Jul (before the tuning window)"):
        v = rk.get(pn)
        if not v:
            continue
        c, l = v["current (engine target)"], v["learned max-EV, any draw >= 1R"]
        e = v["learned max-EV, ERL >= 1.5R"]
        ad = v["learned max-EV miss-adjusted, any draw >= 1R"]
        ci = l.get("diff_ci95") or [float("nan")] * 2
        out.append(f"- **{pn}** ({v['n_trades']} trades): learned max-EV {l['avg_r']:+.3f}R/trade (win {l['win']:.0f}%, PF "
                   f"{l['pf']:.2f}) vs current {c['avg_r']:+.3f}R (win {c['win']:.0f}%, PF {c['pf']:.2f}); difference "
                   f"{l['diff_vs_current']:+.3f}R [95% CI {ci[0]:+.3f}, {ci[1]:+.3f}]. ERL-only learned (>= 1.5R): "
                   f"{e['avg_r']:+.3f}R; miss-adjusted EV: {ad['avg_r']:+.3f}R.")
    mo = R.get("monthly") or {}
    cur_m, lrn_m = mo.get("current (engine target)", {}), mo.get("learned max-EV, any draw >= 1R", {})
    if cur_m and lrn_m:
        def span(m, a, z):
            return sum(v[0] for k, v in m.items() if a <= k <= z)
        out.append(f"- Regime pattern: in 2026-01..07 (losing months) the learned rule lost {span(lrn_m, '2026-01', '2026-07'):+.1f}R "
                   f"vs {span(cur_m, '2026-01', '2026-07'):+.1f}R for the current rule; in 2026-08..10 it made "
                   f"{span(lrn_m, '2026-08', '2026-10'):+.1f}R vs {span(cur_m, '2026-08', '2026-10'):+.1f}R. Nearer targets "
                   "(about 2R vs about 4R) lose less in the bad regime and give back more in the trending one.")
    imp = R.get("importance")
    if imp:
        uniq = [f"{z['feature']} ({z['drop_one_rel'] * 1000:+.1f})" for z in imp if z["drop_one_rel"] > 0.0002]
        none = [z["feature"] for z in imp if z["drop_one_rel"] <= 0.0002]
        alone = sorted(imp, key=lambda z: -z["alone_rel"])[:5]
        out.append(f"- Features with unique out-of-sample information (drop-one log-loss x1000, draws >= 1R): {', '.join(uniq)}. "
                   f"No unique gain: {', '.join(none)}. Strongest on their own: "
                   f"{', '.join(z['feature'] + ' (' + format(z['alone_rel'] * 1000, '+.0f') + ')' for z in alone)}.")
    return "\n".join(out)


def handoff():
    return "\n".join([
        "## Hand-off: using it from the engine",
        "",
        "- Call `from engine.draw_learner import predict` with one draw's feature dict (`engine/liquidity_map.features(x)` "
        "plus `within_reach`). It returns P(hit before the stop, by 15:55) or **None** when `data/draw_learner.json` is missing "
        "or the input has no usable distance; the caller then falls back to its rule. `pick(draws, min_r)` returns the max-EV "
        "draw with the brief's EV. Extra keys (`tier`, `price`, ...) are ignored; an unknown `source` gets the average source "
        "effect; `age_h=None` counts as 0; a missing `within_reach` counts as inside reach.",
        "- Retrain: `python tools/train_draw_learner.py` (about 15 s, single process). It rewrites the model and this report.",
        "- The model's weight sits on `dist_r`, `dist_atr`, `session` and `within_reach`. These match exactly when the "
        "caller uses the same entry (signal close), stop, Wilder ATR14(5m) and ADR10. Source / eq / kind coefficients are small "
        "(|standardised coef| < 0.1), so the definition gaps below move p by a few points at most (e.g. PDH -> unknown source "
        "at 2.5R: 0.25 -> 0.22).",
        "",
        "Known differences between this trainer and `engine/liquidity_map.py` as read at 18:36 ET (align one side or the other):",
        "",
        "| item | this trainer (DOL_PLAYBOOK) | liquidity_map.py / engine pools |",
        "|---|---|---|",
        "| 1H / 15m swing pools | 3-bar fractal (k=1) on 1H / 15m bars built from 5m; tracked 10 / 5 days | engine `H1H/H1L`, "
        "`ITH/ITL` = Structure(2) (k=2) fractals, 1H from `data/NQ_1h.csv`; retired after 5 / 1.2 days |",
        "| PDH/PDL, sessions | previous CME day's H/L only; today's Asia / London / ON only | engine keeps untaken PD and session "
        "pools up to 2.2 days, so yesterday's sessions can still be draws |",
        "| `eq` | D8: max(2 ticks, 0.1 ATR_tf), >= 3 bars apart, >= 1 ATR pullback, same TF | engine eq flag (6 NQ points, set "
        "when a pool is created) |",
        "| `kind` of non-eq M15SW / M5SW | ERL (D7 lists swings as external liquidity) | IRL |",
        "| HTF gap mitigation timing | any closed 5m bar whose wick reaches the CE | checked when the gap's own TF bar closes "
        "(a 1H gap tagged at 10:05 stays live until 11:00) |",
        "| 4H / 1D gaps kept | the 10 nearest live per side | up to 40 stored per side |",
    ])


def caveats(R):
    return "\n".join([
        handoff(),
        "",
        "## Caveats (read before using it)",
        "",
        "- **Labels are one number per trade.** Every draw of a trade shares one price path, so 'hit' is just "
        "`max favourable excursion before the stop >= distance`. Draw features can only matter *across* trades (a PDH at 2R "
        "vs a 5m gap at 2R on different days). The effective sample is the number of trades, not the number of draws.",
        "- **Distance, time of day and reach carry the information.** Out of sample, only dist_r, dist_atr, session (AM vs PM) "
        "and within_reach add unique information; the liquidity attributes (source, kind, eq, obstacles beyond what "
        "distance already says, age, htf_dir) add nothing. Read the matched-distance tables, not the raw ones.",
        "- **The EV formula charges a full -1R to every miss.** Many far targets end at 15:55 with a partial result, not at the "
        "stop, so EV = p x R - (1 - p) is conservative for far draws. The simulated R uses the real path, so the comparison "
        "itself is fair.",
        "- **Unmanaged exits.** The comparison removes the engine's break-even, 30-minute time stop and giveback exit for "
        "both rules, so neither line equals the engine's real P&L. A target that wins here can still lose once those "
        "management rules cut trades early.",
        "- **Entry edge is not created here.** The five-year verdict (no proven entry edge) still stands; the learner can only "
        "reshape exits on entries that are themselves roughly break-even before Aug 2026.",
        "- **Definition drift.** The live caller (engine/liquidity_map.py) must compute the features exactly as defined "
        "above. Known differences at the time of writing are listed in the hand-off notes. `predict()` returns None "
        "without data/draw_learner.json, and unknown sources fall back to the average source effect.",
        "- **2026 Aug-Oct is the window the engine's defaults were tuned on**; the Jan-Jul 2026 and 2025 lines are the "
        "cleaner out-of-sample checks.",
    ])


if __name__ == "__main__":
    main()
