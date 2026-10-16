"""ICT / SMC concepts as bar-level features: inducement, PO3/AMD, NQ-ES SMT, smart-money traps.

Pure functions. Every feature for a candidate at signal bar `i` reads only bars 0..i (closed bars), so nothing here can
look ahead. The candidate is described by the same objects the engine's `_plan` sees:

    d       +1 long (sell-side sweep) / -1 short (buy-side sweep)
    i       signal bar (the bar whose close confirmed the IFVG / CISD trigger)
    arm_i   bar that first traded through the swept pool (setup armed)
    ext_i   bar of the sweep extreme (lowest low for longs / highest high for shorts) at signal time
    pool    price of the first pool swept (raw price, not direction-space)

All logic runs in "direction space" exactly like engine/model.py: for shorts the price series is mirrored
(O,H,L,C) -> (-O,-L,-H,-C), so every rule is written once, for a long.

Typical use:
    ctx = Context(bars, partner_bars)          # once per bar series
    f = features(ctx, d, i, arm_i, ext_i, pool, arms=[...])   # dict of ict_* features (ints / floats)
    annotate(rows, ctx, arms_by_dir)           # adds row["ict"] = features(...) to trade / shadow dicts
"""
from __future__ import annotations

import numpy as np

# ------------------------------------------------------------------------------------------- default parameters
P = {
    "leg_lookback": 24,      # bars searched back from the extreme for the manipulation-leg origin (engine: 120 min)
    "atr_n": 14,
    # inducement
    "idm_frac": 2,           # fractal half-width for an internal swing low (2 = lower than 2 bars each side)
    "idm_age": 12,           # inducement must have formed within this many bars before the sweep (1 h)
    "idm_dist_atr": 1.0,     # ... and sit no more than this many ATR above the swept pool (it is "just before the POI")
    # inducement before the real sweep (first sweep fails, second is real)
    "ss_raid_lb": 24,        # the first sweep: a low that undercut the prior 24 bars (2 h)
    "ss_rally_atr": 1.0,     # ... followed by a close at least 1 ATR above it (longs got trapped)
    "ss_min_gap": 3,         # first sweep at least 3 bars before the current sweep bar
    # PO3 / AMD
    "asia_accum_adr": 0.40,  # Asia range (20:00-24:00 ET) <= 40% of the 20-day average range = accumulation
    # SMT
    "smt_window": 48,        # reference swing searched in the 4 h before the sweep extreme
    "smt_min_gap": 3,        # reference swing at least 3 bars before the extreme
    "smt_margin_atr": 0.0,   # partner must hold its reference low by at least this many partner ATR
    # traps
    "trap_n": 3,             # failed break: back inside within N bars of the first close beyond the pool
    "turtle_n": 2,           # turtle soup: first close back inside within N bars of the sweep bar
    "choch_frac": 2,
    "choch_n": 6,            # trap CHoCH: the break of the last swing low is closed back above within N bars
}


def dir_space(o, h, l, c, d):
    return (o, h, l, c) if d == 1 else (-o, -l, -h, -c)


class Context:
    """Per-bar-series precomputation (day boundaries, true opens, Asia range, ADR, partner alignment).
    Works on an engine.data.Bars (fields t, o, h, l, c, mod, tday)."""

    def __init__(self, b, partner=None, params=None, partner_1h=None):
        self.b = b
        self.p = {**P, **(params or {})}
        n = len(b)
        self.n = n
        self.secs = int(np.median(np.diff(b.t[:2000]))) if n > 1 else 300     # bar length (5m = 300 s)
        self.dirs = {1: dir_space(b.o, b.h, b.l, b.c, 1), -1: dir_space(b.o, b.h, b.l, b.c, -1)}
        tr = np.maximum(b.h, np.r_[b.c[0], b.c[:-1]]) - np.minimum(b.l, np.r_[b.c[0], b.c[:-1]])
        k = self.p["atr_n"]
        cs = np.r_[0.0, np.cumsum(tr)]
        idx = np.arange(n)
        lo = np.maximum(0, idx - k + 1)
        self.atr = (cs[idx + 1] - cs[lo]) / (idx + 1 - lo)          # ATR over bars i-13..i (closed at i)
        # trading days
        self.day_start = np.zeros(n, dtype=np.int64)
        starts = np.r_[0, np.nonzero(np.diff(b.tday))[0] + 1]
        ends = np.r_[starts[1:], n]
        self.day_open = np.full(n, np.nan)       # 18:00 ET open of the trading day
        self.mid_i = np.full(n, -1, dtype=np.int64)   # index of the midnight (00:00 ET) bar of the trading day
        self.asia_end = np.full(n, -1, dtype=np.int64)  # last Asia (20:00-24:00) bar of the trading day
        self.asia_hi = np.full(n, np.nan)
        self.asia_lo = np.full(n, np.nan)
        self.adr20 = np.full(n, np.nan)
        self.pd_hi = np.full(n, np.nan); self.pd_lo = np.full(n, np.nan)
        self.pd_open = np.full(n, np.nan); self.pd_close = np.full(n, np.nan)
        rngs = []
        prev = None
        for a, z in zip(starts, ends):
            self.day_start[a:z] = a
            self.day_open[a:z] = b.o[a]
            mods = b.mod[a:z]
            mid = np.nonzero(mods < 1080)[0]
            if len(mid):
                self.mid_i[a:z] = a + mid[0]
            asia = np.nonzero(mods >= 1200)[0]
            if len(asia):
                self.asia_end[a:z] = a + asia[-1]
                self.asia_hi[a:z] = b.h[a + asia].max()
                self.asia_lo[a:z] = b.l[a + asia].min()
            if len(rngs) >= 5:
                self.adr20[a:z] = float(np.mean(rngs[-20:]))
            if prev is not None:
                pa, pz = prev
                self.pd_hi[a:z] = b.h[pa:pz].max(); self.pd_lo[a:z] = b.l[pa:pz].min()
                self.pd_open[a:z] = b.o[pa]; self.pd_close[a:z] = b.c[pz - 1]
            rngs.append(float(b.h[a:z].max() - b.l[a:z].min()))
            prev = (a, z)
        # partner (ES) aligned by timestamp: pidx[k] = partner bar with the same open time, or -1
        self.partner = partner
        self.pidx = None
        if partner is not None:
            pos = {int(t): j for j, t in enumerate(partner.t)}
            self.pidx = np.array([pos.get(int(t), -1) for t in b.t], dtype=np.int64)
            ptr = np.maximum(partner.h, np.r_[partner.c[0], partner.c[:-1]]) - np.minimum(partner.l, np.r_[partner.c[0], partner.c[:-1]])
            pcs = np.r_[0.0, np.cumsum(ptr)]
            pi = np.arange(len(partner)); plo = np.maximum(0, pi - k + 1)
            self.patr = (pcs[pi + 1] - pcs[plo]) / (pi + 1 - plo)
            self.pdirs = {1: dir_space(partner.o, partner.h, partner.l, partner.c, 1),
                          -1: dir_space(partner.o, partner.h, partner.l, partner.c, -1)}
        # partner 1h bars (longer ES history than 5m): used by smt_1h
        self.p1h = partner_1h
        if partner_1h is not None:
            self.p1h_pos = {int(t): j for j, t in enumerate(partner_1h.t)}
            pc = np.r_[partner_1h.c[0], partner_1h.c[:-1]]
            self.p1h_jump = np.abs(partner_1h.o - pc) / np.maximum(pc, 1e-9)   # roll / data-gap detector


# ------------------------------------------------------------------------------------------- helpers
def _fractal_lows(L, a, z, n):
    """Indices k in [a, z] that are swing lows: L[k] < the n bars before and <= the n bars after.
    The caller must make sure k + n <= the current bar (the swing is confirmed)."""
    out = []
    for k in range(max(a, n), min(z, len(L) - 1 - n) + 1):
        if L[k] < L[k - n:k].min() and L[k] <= L[k + 1:k + n + 1].min():
            out.append(k)
    return out


def leg_start(H, ext_i, lookback):
    a = max(0, ext_i - lookback)
    return a + int(np.argmax(H[a:ext_i + 1]))


# ------------------------------------------------------------------------------------------- 1. inducement
def inducement(ctx, d, i, arm_i, ext_i, pool):
    """IDM: a minor internal swing low (fractal) that formed inside the manipulation leg shortly before price reached
    the point of interest (the swept pool), sitting just above it. Early longs buy that minor low; their stops rest
    between it and the pool; the sweep takes both. Since the leg ends below the pool, any such low has been taken by
    the time of the sweep: the feature is "the POI was reached THROUGH an inducement" vs "in one straight drop"."""
    p = ctx.p
    O, H, L, C = ctx.dirs[d]
    pool_d = pool * d
    ls = leg_start(H, ext_i, p["leg_lookback"])
    n = p["idm_frac"]
    atr = ctx.atr[arm_i] or 1e-9
    best, any_internal = None, 0
    for k in _fractal_lows(L, ls + 1, arm_i - n, n):     # k + n <= arm_i: the swing was confirmed by the sweep bar
        if L[k] <= pool_d:
            continue
        any_internal += 1
        dist = (L[k] - pool_d) / atr
        if dist <= p["idm_dist_atr"] and arm_i - k <= p["idm_age"]:
            best = (k, dist)
    return {"ict_idm": int(best is not None), "ict_idm_dist": round(best[1], 2) if best else None,
            "ict_idm_any": int(any_internal > 0), "ict_idm_count": any_internal}


def second_sweep(ctx, d, i, arm_i, ext_i, pool, arms=None):
    """'Inducement before the real sweep': an earlier sweep on the same side today failed (price raided a low, rallied,
    then came back), and the current sweep runs BELOW that first raid. Two versions:
      ict_ss_bar  - from bars only: a bar k in today's session (from 00:00 ET) whose low undercut the prior ss_raid_lb
                    bars (a raid), followed by a close >= ss_rally_atr ATR above it before the current sweep, and the
                    current extreme is below L[k].
      ict_ss_eng  - from the engine's own arming log (`arms`: earlier armed-sweep bars in direction d): an earlier setup
                    in this direction was armed today and the current extreme is below that setup's extreme."""
    p = ctx.p
    O, H, L, C = ctx.dirs[d]
    s0 = int(ctx.mid_i[i]) if ctx.mid_i[i] >= 0 else int(ctx.day_start[i])
    atr = ctx.atr[arm_i] or 1e-9
    found = 0
    lb = p["ss_raid_lb"]
    for k in range(max(s0, lb), arm_i - p["ss_min_gap"] + 1):
        if L[k] < L[k - lb:k].min():
            rally = C[k + 1:arm_i].max() if arm_i > k + 1 else -1e18
            if rally - L[k] >= p["ss_rally_atr"] * atr and L[ext_i] < L[k] and L[k + 1:arm_i].min() >= L[k]:
                found = 1
                break
    eng = 0
    if arms:
        ds = int(ctx.day_start[i])
        prev = [a for a in arms if ds <= a < arm_i]
        if prev:
            a1 = prev[-1]
            e1 = L[a1:arm_i].min()
            eng = int(L[ext_i] < e1)
    return {"ict_ss_bar": found, "ict_ss_eng": eng}


# ------------------------------------------------------------------------------------------- 2. PO3 / AMD
def po3(ctx, d, i, arm_i, ext_i, pool):
    """Power of three relative to the true opens. Manipulation = the sweep extreme is on the far side of the open
    (below it for a long); reclaim = the signal bar closes back on the distribution side; accumulation = a compressed
    Asia range; Asia raid = the sweep took the Asia low. ict_po3 = accumulation + manipulation below midnight open +
    reclaim of the midnight open at the signal (the textbook A-M-D sequence)."""
    p = ctx.p
    O, H, L, C = ctx.dirs[d]
    ext_d = L[ext_i]
    out = {}
    do = ctx.day_open[i] * d
    out["ict_manip18"] = int(ext_d < do)
    out["ict_reclaim18"] = int(ext_d < do and C[i] > do)
    mi = int(ctx.mid_i[i])
    if 0 <= mi <= i:
        mo = (ctx.b.o[mi]) * d
        out["ict_manip00"] = int(ext_d < mo)
        out["ict_reclaim00"] = int(ext_d < mo and C[i] > mo)
    else:
        out["ict_manip00"] = out["ict_reclaim00"] = 0
    ae = int(ctx.asia_end[i])
    accum = 0
    asia_raid = 0
    if 0 <= ae < i and not np.isnan(ctx.adr20[i]):
        rng = ctx.asia_hi[i] - ctx.asia_lo[i]
        accum = int(rng <= p["asia_accum_adr"] * ctx.adr20[i])
        a_lo_d = ctx.asia_lo[i] if d == 1 else -ctx.asia_hi[i]
        asia_raid = int(ext_d < a_lo_d)
    out["ict_asia_accum"] = accum
    out["ict_asia_raid"] = asia_raid
    out["ict_po3"] = int(accum and out["ict_reclaim00"])
    # daily bias proxy: prior day closed in its upper half (longs) / lower half (shorts) -> manipulation AGAINST the bias
    if not np.isnan(ctx.pd_hi[i]) and ctx.pd_hi[i] > ctx.pd_lo[i]:
        pos = (ctx.pd_close[i] - ctx.pd_lo[i]) / (ctx.pd_hi[i] - ctx.pd_lo[i])
        bias = int((pos >= 0.5) if d == 1 else (pos <= 0.5))
    else:
        bias = 0
    out["ict_po3_bias"] = int(bias and out["ict_manip00"])
    return out


# ------------------------------------------------------------------------------------------- 3. SMT (NQ vs ES)
def smt(ctx, d, i, arm_i, ext_i, pool):
    """Swing-anchored SMT. Reference swing = the lowest NQ low in [ext_i - smt_window, ext_i - smt_min_gap]. If NQ's
    sweep extreme is below it (NQ made the lower low) while ES's low around the extreme (bars ext_i-1..min(ext_i+1, i))
    is ABOVE ES's low around the reference bar (k-1..k+1), ES failed to confirm: SMT divergence.
    Returns None-valued flags when the partner has no bars there (no ES history)."""
    p = ctx.p
    if ctx.pidx is None:
        return {"ict_smt": None, "ict_smt_margin": None}
    O, H, L, C = ctx.dirs[d]
    a = max(0, ext_i - p["smt_window"]); z = ext_i - p["smt_min_gap"]
    if z <= a:
        return {"ict_smt": None, "ict_smt_margin": None}
    k = a + int(np.argmin(L[a:z + 1]))
    j_ref = [ctx.pidx[x] for x in range(max(0, k - 1), min(k + 2, ext_i))]
    j_now = [ctx.pidx[x] for x in range(max(0, ext_i - 1), min(ext_i + 2, i + 1))]
    j_ref = [j for j in j_ref if j >= 0]; j_now = [j for j in j_now if j >= 0]
    if not j_ref or not j_now:
        return {"ict_smt": None, "ict_smt_margin": None}  # no partner bars here: undefined, not "no divergence"
    if not L[ext_i] < L[k]:
        return {"ict_smt": 0, "ict_smt_margin": None}     # NQ itself did not make the lower low vs that swing
    PO, PH, PL, PC = ctx.pdirs[d]
    ref = min(PL[j] for j in j_ref); now = min(PL[j] for j in j_now)
    patr = ctx.patr[j_now[-1]] or 1e-9
    margin = (now - ref) / patr
    return {"ict_smt": int(margin > p["smt_margin_atr"]), "ict_smt_margin": round(float(margin), 2)}


def smt_1h(ctx, d, i, arm_i, ext_i, pool):
    """SMT with ES 1h bars (ES 5m history is short). Same idea as smt(), at hourly resolution, closed bars only:
    reference swing = lowest NQ 5m low 2-12 h before the sweep extreme; NQ must have undercut it. ES 'now' low = the
    1h bars of the extreme's hour and the hour before; ES reference low = the 1h bars around the reference swing's hour.
    Defined only when the extreme's hour has CLOSED by the signal bar's close (else None), the two hours differ, and
    no ES 1h bar in the window opens > 0.6% away from the previous close (contract roll / data gap -> None)."""
    if ctx.p1h is None:
        return {"ict_smt1h": None}
    b = ctx.b
    O, H, L, C = ctx.dirs[d]
    t_close = int(b.t[i]) + ctx.secs
    he = int(b.t[ext_i]) // 3600 * 3600
    if he + 3600 > t_close:
        return {"ict_smt1h": None}
    a = max(0, ext_i - 144); z = ext_i - 24
    if z <= a:
        return {"ict_smt1h": None}
    k = a + int(np.argmin(L[a:z + 1]))
    hk = int(b.t[k]) // 3600 * 3600
    if hk + 3600 > he - 3600:
        return {"ict_smt1h": None}
    pos = ctx.p1h_pos
    jn = [pos.get(he - 3600), pos.get(he)]
    jr = [pos.get(hk - 3600), pos.get(hk), pos.get(hk + 3600)]
    jn = [j for j in jn if j is not None]; jr = [j for j in jr if j is not None]
    if not jn or not jr:
        return {"ict_smt1h": None}
    if ctx.p1h_jump[min(jr):max(jn) + 1].max() > 0.006:
        return {"ict_smt1h": None}
    if not L[ext_i] < L[k]:
        return {"ict_smt1h": 0}
    pl = ctx.p1h.l if d == 1 else -ctx.p1h.h
    return {"ict_smt1h": int(min(pl[j] for j in jn) > min(pl[j] for j in jr))}


# ------------------------------------------------------------------------------------------- 4. smart-money traps
def traps(ctx, d, i, arm_i, ext_i, pool):
    """ict_trap_fail  - failed break: at least one 5m bar CLOSED beyond the swept pool (breakout traders committed) and
                        price closed back inside within trap_n bars of that first close beyond (by the signal bar).
       ict_wick_only  - no 5m close beyond the pool before the signal (pure wick raid).
       ict_turtle     - turtle soup: the first close back above the pool comes within turtle_n bars of the sweep bar.
       ict_choch_trap - trap CHoCH: inside the leg, a bar closed below the last confirmed 5m swing low (bearish
                        structure break) and a close back above that level followed within choch_n bars (by i)."""
    p = ctx.p
    O, H, L, C = ctx.dirs[d]
    pool_d = pool * d
    seg = C[arm_i:i + 1]
    beyond = np.nonzero(seg < pool_d)[0]
    out = {"ict_wick_only": int(len(beyond) == 0)}
    fail = 0
    if len(beyond):
        f0 = arm_i + int(beyond[0])
        back = np.nonzero(C[f0 + 1:i + 1] > pool_d)[0]
        fail = int(len(back) > 0 and back[0] + 1 <= p["trap_n"])
    out["ict_trap_fail"] = fail
    inside = np.nonzero(seg > pool_d)[0]
    out["ict_turtle"] = int(len(inside) > 0 and inside[0] <= p["turtle_n"])
    # trap CHoCH
    ls = leg_start(H, ext_i, p["leg_lookback"])
    n = p["choch_frac"]
    # the last swing low confirmed before the leg started, and the last one inside the leg confirmed before the extreme
    sw = _fractal_lows(L, max(n, ls - p["leg_lookback"]), ls - n, n)
    inner = _fractal_lows(L, ls + 1, ext_i - n - 1, n)
    ch = 0
    cands = (sw[-1:] if sw else []) + inner[-1:]
    for k in cands:
        lvl = L[k]
        brk = [x for x in range(k + n + 1, i + 1) if C[x] < lvl]
        if not brk:
            continue
        b0 = brk[0]
        rec = [x for x in range(b0 + 1, min(i, b0 + p["choch_n"]) + 1) if C[x] > lvl]
        if rec:
            ch = 1
            break
    out["ict_choch_trap"] = ch
    return out


# ------------------------------------------------------------------------------------------- all together
def features(ctx, d, i, arm_i, ext_i, pool, arms=None):
    f = {}
    f.update(inducement(ctx, d, i, arm_i, ext_i, pool))
    f.update(second_sweep(ctx, d, i, arm_i, ext_i, pool, arms))
    f.update(po3(ctx, d, i, arm_i, ext_i, pool))
    f.update(smt(ctx, d, i, arm_i, ext_i, pool))
    f.update(smt_1h(ctx, d, i, arm_i, ext_i, pool))
    f.update(traps(ctx, d, i, arm_i, ext_i, pool))
    return f


BINARY = ["ict_idm", "ict_idm_any", "ict_ss_bar", "ict_ss_eng",
          "ict_manip18", "ict_reclaim18", "ict_manip00", "ict_reclaim00", "ict_asia_accum", "ict_asia_raid", "ict_po3", "ict_po3_bias",
          "ict_smt", "ict_smt1h",
          "ict_trap_fail", "ict_wick_only", "ict_turtle", "ict_choch_trap"]

CONCEPT = {"ict_idm": "inducement", "ict_idm_any": "inducement", "ict_ss_bar": "inducement", "ict_ss_eng": "inducement",
           "ict_manip18": "po3", "ict_reclaim18": "po3", "ict_manip00": "po3", "ict_reclaim00": "po3", "ict_asia_accum": "po3",
           "ict_asia_raid": "po3", "ict_po3": "po3", "ict_po3_bias": "po3", "ict_smt": "smt", "ict_smt1h": "smt",
           "ict_trap_fail": "trap", "ict_wick_only": "trap", "ict_turtle": "trap", "ict_choch_trap": "trap"}


def annotate(rows, ctx, arms_by_dir=None, key="ict"):
    """Add row[key] = features(...) to every trade / shadow dict that carries the sweep geometry the study engine
    stores in its feature dict (_sig_i, _arm_i, _ext_i, _pool). Rows without it are left untouched."""
    for r in rows:
        f = r.get("features") or r.get("f") or {}
        if "_arm_i" not in f:
            continue
        d = r["dir"]
        r[key] = features(ctx, d, f["_sig_i"], f["_arm_i"], f["_ext_i"], f["_pool"],
                          (arms_by_dir or {}).get(d))
    return rows
