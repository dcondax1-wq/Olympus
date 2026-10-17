"""Trader layer: person-style trading applied to ANY model's setups (rules: research/lab/TRADER_LAYER_RULES.md).

A model proposes entries (where, which way, invalidation). The layer trades them like a discretionary trader:
  J  judgment     engine/narrative.py narrative() + assess(): take / skip, grade, thoughts; hard vetoes (news windows,
                  lunch, FOMC, open-drive and trend-day fades, late entries); 2-a-week frequency guard; bias option
  P  stop + plan  model stop + playbook buffer; targets from engine/liquidity_map.py draws(): TP1 at the first internal
                  draw, runner to the most significant ERL within reach; skip (never tighten) under 1R
  M  management   break-even after TP1 / +1R, structure trail, opposing-CISD exit, giveback, time exits (DOL_PLAYBOOK)
  S  size         engine/risk_policy.py size() on a simulated back-to-back MFFU 50K account; flat $350 fallback
Day rules (always): one position at a time, max 2 trades a day, done after 2 losers / -$600 / a +1R winner.

    from tools.trader_layer import apply, setups_from_trades
    trades = apply(setups, bars5, es5, {"bias_align": "require"})

A setup: {"entry_t": unix s, the open of the first bar in which the position exists (market: the bar after the
signal bar = the signal close; limit: the fill bar, judged on the bars closed before it), "dir": +1/-1, "entry",
"stop" (the model's invalidation), optional "entry_kind" ("market" | "limit"), "target" (the model's own target, used
by plan-off), "sweep_label" / "sweep_t" / "sweep_extreme", "trigger_tf", "model", "setup"}.
Output: strategy_lab.make_trade-format dicts (pnl / r after costs) plus grade, plan, thoughts, mgmt, legs.
Causal: decisions read closed 5m bars only; intrabar order stop -> TP1 -> T, the stop wins ties (optionally resolved on
1m bars); every in-trade decision acts from the next bar.
"""
from __future__ import annotations

import datetime as dt
import math
import os
import sys
import traceback

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

TICK, BAR = 0.25, 300
PV = {"NQ": 2.0, "ES": 5.0}
COMM, SLIP, MAX_QTY = 1.40, 0.25, 40

_IMPORT_ERR = {}


def _imp(name):
    try:
        mod = __import__(f"engine.{name}", fromlist=[name])
        _IMPORT_ERR.pop(name, None)
        return mod
    except Exception as ex:                      # other agents may be mid-edit: fall back, retry on the next apply()
        _IMPORT_ERR[name] = f"{type(ex).__name__}: {ex}"
        return None


NAR = LM = RP = DL = None


def _load():
    global NAR, LM, RP, DL
    if NAR is None:
        NAR = _imp("narrative")
    if LM is None:
        LM = _imp("liquidity_map")
    if RP is None:
        RP = _imp("risk_policy")
    if DL is None:
        DL = _imp("draw_learner")


DEFAULT = {
    "judgment": True, "plan": True, "manage": True, "sizing": True,
    "bias_align": "grade",            # off | grade (brain E1) | require = skip_counter | grade_pm1 (external bias +/-1)
    "bias_source": "narrative",       # narrative | daily_bias[:method] (engine/daily_bias.py); "bias_replace" swaps it into assess
    "version": "v1",                  # brain version for assess()
    "min_r": 1.0, "runner_r": 3.0, "fallback_r": 2.0, "discovery_r": 12.0, "buf_frac": 0.1,
    "stall_bars": 12, "stall_mfe": 0.5, "giveback_r": 0.5, "be_r": 1.0,
    "max_trades_day": 2, "max_losses_day": 2, "day_stop": 600.0, "win_stop_r": 1.0,
    "freq_floor": 2, "freq_sessions": 5,
    "flat_risk": 350.0, "tier_risk": {"A": 700.0, "B": 350.0, "C": 175.0}, "tier_max": {"A": 10, "B": 40, "C": 40},
    "lunch": (695, 810), "news830_until": 585, "no_entry_after": 930, "skip_fomc_day": True,
    "od_veto": True, "trend_veto": True, "inside_rule": True, "b1_target": True,
    "sym": "NQ",
}

ATR_KEY = "_tl_cache"


# ------------------------------------------------------------------------------------------------ helpers
def _hm(mod):
    return f"{int(mod) // 60 % 24:02d}:{int(mod) % 60:02d}"


def _px(x):
    return "n/a" if x is None else f"{x:,.2f}"


def _et(t):
    return dt.datetime.fromtimestamp(int(t), dt.timezone.utc).astimezone(NAR_ET())


def NAR_ET():
    from zoneinfo import ZoneInfo
    return ZoneInfo("America/New_York")


class _Book:
    """Duck-typed liquidity_map.LiquidityBook: live gaps (already filtered) and no extra pools."""

    def __init__(self, gaps):
        self._g = gaps
        self.xpools = []

    def gaps(self, gdir, tfs=None):
        return [g for g in self._g if g["dir"] == gdir and (tfs is None or g["tf"] in tfs)]


KMAP = {"PDH": "PDH", "PDL": "PDL", "RTH-H": "RTHH", "RTH-L": "RTHL", "PWH": "PWH", "PWL": "PWL", "ASIA-H": "ASH",
        "ASIA-L": "ASL", "LON-H": "LOH", "LON-L": "LOL", "ON-H": "ONH", "ON-L": "ONL", "ATM-H": "ONH", "ATM-L": "ONL",
        "H4SW-H": "H4H", "H4SW-L": "H4L", "D1SW-H": "D1H", "D1SW-L": "D1L", "H1SW-H": "H1H", "H1SW-L": "H1L",
        "EQH": "H1H", "EQL": "H1L"}


def _cache(C):
    """Per-frame precomputation kept on the brain's Ctx object (ATRd, 4H/1D gaps with their mitigation bar)."""
    c = getattr(C, ATR_KEY, None)
    if c is not None:
        return c
    c = {}
    H, L, last, _ = C.sess["RTH"]
    n = len(C.days)
    rc = np.array([C.c[x] if x >= 0 else np.nan for x in last])
    tr = np.full(n, np.nan)
    for k in range(n):
        if np.isfinite(H[k]):
            pc = rc[k - 1] if k >= 1 and np.isfinite(rc[k - 1]) else C.c[last[k]] if last[k] >= 0 else np.nan
            tr[k] = max(H[k], pc) - min(L[k], pc) if np.isfinite(pc) else H[k] - L[k]
    atrd = np.full(n, np.nan)
    for k in range(n):
        prev = tr[max(0, k - 14):k]
        prev = prev[np.isfinite(prev)]
        atrd[k] = float(prev.mean()) if len(prev) else (float(C.adr10[k]) if np.isfinite(C.adr10[k]) else np.nan)
    c["atrd"] = atrd
    # 09:30 bar index per day
    i930 = np.full(n, -1)
    m = C.mod
    for k in range(n):
        a, z = C.ds[k], C.de[k]
        seg = np.flatnonzero(m[a:z] == 570)
        if len(seg):
            i930[k] = a + int(seg[0])
    c["i930"] = i930
    # 4H / 1D gaps and the first 5m bar whose wick reaches their CE (live while i_now < mit)
    hh = []
    for tf, T in (("4h", C.H4), ("1d", C.D)):
        try:
            F = C._fvgs_tf(T)
        except Exception:
            continue
        for q in range(len(F["i3"])):
            i3, ct, d, bot, top = int(F["i3"][q]), int(F["ct"][q]), int(F["d"][q]), float(F["bot"][q]), float(F["top"][q])
            ce = 0.5 * (bot + top)
            a = i3 + 1
            if d < 0:
                hit = np.flatnonzero(C.h[a:] >= ce)
            else:
                hit = np.flatnonzero(C.l[a:] <= ce)
            mit = a + int(hit[0]) if len(hit) else len(C.t) + 1
            hh.append({"tf": tf, "dir": d, "bot": bot, "top": top, "ce": ce, "tc": ct, "i3": i3, "mit": mit})
    c["htf_gaps"] = hh
    setattr(C, ATR_KEY, c)
    return c


# ------------------------------------------------------------------------------------------------ inventory
def inventory(C, i_dec, t_dec, d, E, R, atr):
    """Every draw beyond E in direction d, from liquidity_map.draws(), with the brain's pools / gaps as inputs."""
    k = int(C.di[i_dec])
    P = NAR.pools(C, i_dec, t_dec)
    pools = []
    for p in P:
        if p["taken"] or p["name"] not in KMAP:
            continue
        kk = KMAP[p["name"]]
        av = min(int(p["avail"]), len(C.t) - 1)
        pools.append({"kind": kk, "side": "H" if p["side"] > 0 else "L", "price": float(p["price"]), "t0": int(C.t[av]),
                      "eq": p["name"] in ("EQH", "EQL"), "kinds": [kk], "label": NAR.NICE.get(p["name"], p["name"]),
                      "nname": p["name"]})
    gaps = []
    for g in NAR.live_gaps(C, i_dec, -d, kinds=("5m", "15m", "1h")):
        gaps.append({"tf": g["tf"], "dir": -d, "top": g["top"], "bot": g["bottom"], "ce": g["ce"], "tc": int(g["created_t"])})
    for g in _cache(C)["htf_gaps"]:
        if g["dir"] == -d and g["tc"] <= t_dec and g["mit"] > i_dec and g["i3"] < i_dec:
            gaps.append({"tf": g["tf"], "dir": -d, "top": g["top"], "bot": g["bot"], "ce": g["ce"], "tc": g["tc"]})
    # fresh swings: 5m k=2 (today + yesterday), 15m k=1 (last 5 days)
    a5 = C.ds[max(0, k - 1)]
    hs, ls = LM.live_swings(C.h, C.l, 2, i_dec, max(5, i_dec - a5), TICK)
    sw = {"H": [(p, j, "5m", int(C.t[min(j + 2, len(C.t) - 1)]) + BAR) for p, j in hs],
          "L": [(p, j, "5m", int(C.t[min(j + 2, len(C.t) - 1)]) + BAR) for p, j in ls]}
    T = C.M15
    j1 = T.at(t_dec)
    for j in range(max(1, j1 - 5 * 96), j1):
        if T.day[j] < k - 5:
            continue
        for side, flag, lvl in (("H", T.swh[j], T.H[j]), ("L", T.swl[j], T.L[j])):
            if not flag:
                continue
            a = int(T.last[j + 1]) + 1
            if a <= i_dec:
                if side == "H" and C.h[a:i_dec + 1].max() >= lvl + TICK:
                    continue
                if side == "L" and C.l[a:i_dec + 1].min() <= lvl - TICK:
                    continue
            sw[side].append((float(lvl), int(T.last[j]), "15m", int(T.close_t[j + 1])))
    jh = C.H1.at(t_dec)
    h1 = int(C.H1.dir[jh]) if jh >= 0 else 0
    ds = LM.draws(d, E, R, atr, t_dec, pools, book=_Book(gaps), swings=sw, h1_trend=h1, mod=int(C.mod[i_dec]),
                  tick=TICK)
    for x in ds:
        q = x.get("pool")
        x["nname"] = q.get("nname") if isinstance(q, dict) else None
    return ds


def _exit_px(x, d):
    if x is None:
        return None
    if x.get("is_gap") or x.get("source") == "PROJ":
        return float(x["price"])
    return float(x["price"]) - d * 2 * TICK


# ------------------------------------------------------------------------------------------------ context vetoes
def _news(day):
    try:
        return NAR.news_on(day)
    except Exception:
        return []


def _open_drive(C, k, i_dec, cache):
    """+1 / -1 open-drive day classified at 10:00 (0 = none or not yet known)."""
    i0 = int(cache["i930"][k])
    if i0 < 0 or i0 + 5 >= len(C.t) or i0 + 5 > i_dec or C.di[i0 + 5] != k:
        return 0
    atrd = cache["atrd"][k]
    if not np.isfinite(atrd) or atrd <= 0:
        return 0
    O = C.o[i0]
    seg_h, seg_l = C.h[i0:i0 + 6], C.l[i0:i0 + 6]
    cl = C.c[i0 + 5]
    e = 0.05 * atrd
    if O - seg_l.min() <= e and cl - O >= 0.20 * atrd and (seg_l[2:] > O).all():
        return 1
    if seg_h.max() - O <= e and O - cl >= 0.20 * atrd and (seg_h[2:] < O).all():
        return -1
    return 0


def vetoes(C, cfg, s, nar, i_dec, mod_dec):
    """Hard context vetoes (rules section 1.2). Returns a reason or None."""
    k = int(C.di[i_dec])
    day = C.days[k]
    ev = _news(day)
    d = s["dir"]
    lo, hi = cfg["lunch"]
    if lo <= mod_dec < hi:
        return f"lunch ({_hm(mod_dec)}): no entries 11:35-13:30"
    if mod_dec >= cfg["no_entry_after"] and mod_dec < 1080:
        return f"{_hm(mod_dec)}: no new entries after 15:30"
    if cfg["skip_fomc_day"] and any("FOMC" in e and imp == "high" for _, e, imp in ev):
        return "FOMC day: standing aside"
    if mod_dec < cfg["news830_until"] and any(m == 510 and imp == "high" for m, _, imp in ev) and mod_dec >= 360:
        return f"08:30 release day and it is only {_hm(mod_dec)}: wait for 09:45"
    cache = _cache(C)
    if cfg["od_veto"] and mod_dec >= 600:
        od = _open_drive(C, k, i_dec, cache)
        if od != 0 and od == -d:
            i0 = int(cache["i930"][k])
            O = C.o[i0]
            back = (C.c[i0:i_dec + 1] < O).any() if od > 0 else (C.c[i0:i_dec + 1] > O).any()
            if not back:
                return f"open drive {'up' if od > 0 else 'down'} from {_px(O)} and price never closed back through the open: I don't fade it"
    if cfg["trend_veto"]:
        a = C.ds[k]
        o18 = C.o[a]
        hi_, lo_ = C.h[a:i_dec + 1].max(), C.l[a:i_dec + 1].min()
        px = C.c[i_dec]
        adr = float(C.adr10[k])
        rng = max(hi_ - lo_, TICK)
        pos = (px - lo_) / rng
        if adr > 0:
            if px - o18 >= 0.4 * adr and pos >= 0.75 and d < 0:
                return f"trend day up ({px - o18:.0f} pts over the 18:00 open, top quarter of the range): no shorts"
            if o18 - px >= 0.4 * adr and pos <= 0.25 and d > 0:
                return f"trend day down ({o18 - px:.0f} pts under the 18:00 open, bottom quarter of the range): no longs"
    return None


# ------------------------------------------------------------------------------------------------ plan
def make_plan(C, cfg, s, i_dec, t_dec, mod_dec, nar):
    """Stop, final target, partial and plan shape. Returns (plan dict | None, reason)."""
    d, E = s["dir"], float(s["entry"])
    atr = max(float(C.atr5[i_dec]), TICK)
    buf = max(2 * TICK, cfg["buf_frac"] * atr)
    if not cfg["plan"]:
        S = float(s["stop"])
        R = abs(E - S)
        tg = s.get("target")
        if tg is None or not np.isfinite(tg) or (tg - E) * d <= 0:
            tg = E + d * cfg["fallback_r"] * R
            lab = f"{cfg['fallback_r']:g}R (model gave no target)"
        else:
            lab = "the model's own target"
        return {"stop": S, "R": R, "buf": 0.0, "T": float(tg), "T_label": lab, "T_r": round(abs(tg - E) / R, 2),
                "tp1": None, "shape": "model", "text": f"model plan: stop {_px(S)}, all out at {lab} {_px(tg)}"}, "ok"
    S = float(s["stop"]) - d * buf
    R = abs(E - S)
    if R <= TICK:
        return None, "no room between entry and stop"
    ds = inventory(C, i_dec, t_dec, d, E, R, atr)
    k = int(C.di[i_dec])
    reach = float(nar.get("reach_now") or max(0.5 * C.adr10[k], C.adr10[k]))
    removed = []
    if cfg["inside_rule"] and k >= 1:
        PDH, PDL = float(C.D.H[k - 1]), float(C.D.L[k - 1])
        a = C.ds[k]
        i0 = int(_cache(C)["i930"][k])
        Oref = C.o[i0] if (mod_dec > 570 and 0 <= i0 <= i_dec) else C.o[a]
        if PDL < Oref < PDH:
            th = C.h[a:i_dec + 1].max() >= PDH + TICK
            tl = C.l[a:i_dec + 1].min() <= PDL - TICK
            if th != tl:
                other = ("PDL", "RTH-L") if th else ("PDH", "RTH-H")
                if (d < 0 and th) or (d > 0 and tl):
                    keep = []
                    for x in ds:
                        if x.get("nname") in other or (x.get("source") in ("PDH", "PDL") and x.get("nname") is None):
                            removed.append(x["label"])
                        else:
                            keep.append(x)
                    ds = keep
    T, why = None, ""
    if cfg["b1_target"] and k >= 2:
        Y_c, P_h, P_l = float(C.D.C[k - 1]), float(C.D.H[k - 2]), float(C.D.L[k - 2])
        a = C.ds[k]
        name = None
        if d > 0 and Y_c > P_h and not (C.l[a:i_dec + 1].min() <= C.D.L[k - 1] - TICK):
            name = "PDH"
        if d < 0 and Y_c < P_l and not (C.h[a:i_dec + 1].max() >= C.D.H[k - 1] + TICK):
            name = "PDL"
        if name:
            for x in ds:
                if x.get("nname") == name and x["dist_r"] >= cfg["min_r"] and x["dist"] <= reach:
                    T, why = x, f"yesterday closed {'above' if d > 0 else 'below'} the day-before {'high' if d > 0 else 'low'}: the {x['label']} is the draw (taken ~{'80' if d > 0 else '67'}% of the time)"
                    break
    if T is None:
        T, w, _ = LM.pick_primary(ds, cfg["min_r"], max_dist=reach, pick="significance")
        if T is not None:
            why = f"most significant external pool inside the {reach:.0f}-pt range left ({w})"
    if T is None:
        T = LM.nearest_in_reach(ds, cfg["min_r"], reach)
        if T is not None:
            why = "no external pool inside reach: nearest draw >= 1R"
    if T is None:
        if not any(x["dist_r"] <= cfg["discovery_r"] for x in ds):
            T = {"price": E + d * cfg["fallback_r"] * R, "dist": cfg["fallback_r"] * R, "dist_r": cfg["fallback_r"],
                 "label": f"{cfg['fallback_r']:g}R projection", "is_gap": False, "source": "PROJ", "tier": "-",
                 "kind": "-", "obstacles": 0, "dist_atr": cfg["fallback_r"] * R / atr}
            why = "price discovery (no pool within 12R): 2R projection"
        else:
            near = ds[0] if ds else None
            return None, ("no draw >= 1R inside today's reach" + (f" (nearest: {near['label']} at {near['dist_r']:.1f}R)" if near else "")
                          + "; I won't tighten the stop to make it fit")
    first = LM.nearest_in_reach(ds, cfg["min_r"], reach) or T
    quick_why = []
    if nar.get("day_type") == "consolidation":
        quick_why.append("consolidation day")
    if mod_dec >= 720:
        quick_why.append("PM session")
    if T.get("obstacles", 0) >= 3:
        quick_why.append(f"crowded path ({T['obstacles']} obstacles, HRLR)")
    tp1 = None
    if quick_why:
        tgt, shape = first, "first_draw"
        text = f"all out at the first draw: {first['label']} {_px(_exit_px(first, d))} ({first['dist_r']:.1f}R) - " + ", ".join(quick_why)
    elif T["dist_r"] >= cfg["runner_r"]:
        tp1 = LM.pick_partial(ds, T["dist"], cfg["min_r"], R, "playbook")
        tgt, shape = T, ("partial_runner" if tp1 else "single")
        text = (f"half at the first internal draw {tp1['label']} {_px(_exit_px(tp1, d))} ({tp1['dist_r']:.1f}R), runner to "
                f"{T['label']} {_px(_exit_px(T, d))} ({T['dist_r']:.1f}R)" if tp1 else
                f"no internal draw in between: all to {T['label']} {_px(_exit_px(T, d))} ({T['dist_r']:.1f}R)")
    else:
        tgt, shape = T, "single"
        text = f"single target: {T['label']} {_px(_exit_px(T, d))} ({T['dist_r']:.1f}R, under 3R so no runner)"
    p_hit = None
    if DL is not None and LM is not None and tgt.get("source") != "PROJ":
        try:
            p_hit = DL.predict({**LM.features(tgt), "within_reach": tgt["dist"] <= reach})
        except Exception:
            p_hit = None
    plan = {"stop": S, "R": R, "buf": round(buf, 2), "T": _exit_px(tgt, d), "T_label": tgt["label"],
            "T_r": round(abs(_exit_px(tgt, d) - E) / R, 2), "T_tier": tgt.get("tier"), "T_obst": tgt.get("obstacles"),
            "final_draw": {"label": T["label"], "price": float(T["price"]), "r": round(T["dist_r"], 2)},
            "tp1": _exit_px(tp1, d) if tp1 else None, "tp1_label": tp1["label"] if tp1 else None,
            "tp1_r": round(abs(_exit_px(tp1, d) - E) / R, 2) if tp1 else None, "shape": shape, "why_T": why,
            "reach": round(reach, 1), "removed": removed, "p_hit": None if p_hit is None else round(float(p_hit), 3),
            "n_draws": len(ds), "text": text}
    return plan, "ok"


# ------------------------------------------------------------------------------------------------ entry / stop variants
def trigger_zone(C, i_sig, d, s=None):
    """Where a person would rest a retest limit after the trigger closed (causal, closed bars <= i_sig):
    the inverted FVG's edge (IFVG), else the CISD level (open of the first candle of the opposing series the signal
    closed through), else the signal body's midpoint. ATM trades carry their own IFVG zone (info.ifvg_lo/hi)."""
    info = ((s or {}).get("raw") or {}).get("info") or {}
    if info.get("ifvg_lo") is not None and info.get("ifvg_hi") is not None:
        lo, hi = float(info["ifvg_lo"]), float(info["ifvg_hi"])
        return ("IFVG", hi if d > 0 else lo)
    c, o, h, l = C.c, C.o, C.h, C.l
    cl = c[i_sig]
    for j in range(i_sig, max(2, i_sig - 24), -1):          # j = third candle of an opposing FVG
        if d > 0 and l[j - 2] - h[j] >= TICK:
            top = float(l[j - 2])
            if cl > top and (j == i_sig or (c[j + 1:i_sig] <= top).all()):
                return ("IFVG", top)
        if d < 0 and l[j] - h[j - 2] >= TICK:
            bot = float(h[j - 2])
            if cl < bot and (j == i_sig or (c[j + 1:i_sig] >= bot).all()):
                return ("IFVG", bot)
    j = i_sig - 1
    while j > 0 and (c[j] - o[j]) * d > 0:
        j -= 1
    end = j
    while j > 0 and (c[j] - o[j]) * d < 0:
        j -= 1
    if end > j:
        lvl = float(o[j + 1])
        if (cl - lvl) * d > 0:
            return ("CISD", lvl)
    return ("BODY", float(0.5 * (o[i_sig] + cl)))


def retest_fill(C, s, plan, level, minutes, m1=None):
    """First time within `minutes` after the decision that price trades 1 tick through the limit `level`, before the stop
    or the target. Returns (fill_t, how) or (None, reason). 1m bars when available, else 5m bars."""
    d, t0 = s["dir"], int(s["entry_t"])
    S, T = plan["stop"], plan["T"]
    t1 = t0 + 60 * int(minutes)
    if m1 is not None and len(m1["t"]) and m1["t"][0] <= t0:
        a = int(np.searchsorted(m1["t"], t0))
        z = int(np.searchsorted(m1["t"], t1))
        ts, hs, ls = m1["t"][a:z], m1["h"][a:z], m1["l"][a:z]
    else:
        a = bar_of(C, t0)
        z = int(np.searchsorted(C.t, t1))
        ts, hs, ls = C.t[a:z], C.h[a:z], C.l[a:z]
    k0 = int(C.di[min(bar_of(C, t0), len(C.t) - 1)])
    for tt, hh, ll in zip(ts, hs, ls):
        if int(C.di[min(bar_of(C, int(tt)), len(C.t) - 1)]) != k0:
            return None, "session ended before a retest"
        if (ll <= level - TICK) if d > 0 else (hh >= level + TICK):
            return int(tt), "filled"
        if (hh >= T) if d > 0 else (ll <= T):
            return None, "ran to the target without a retest"
        if (ll <= S) if d > 0 else (hh >= S):
            return None, "stopped out before a retest"
    return None, f"no retest within {minutes} min"


def recent_swing_stop(s, m1, min_stop_atr=1.0, swing_tf=None):
    """ATM variant (coordinator 19:50): beyond the most recent swing (2 bars each side, on the trigger timeframe built
    from 1m, or on `swing_tf` minutes when given) formed between the sweep extreme and the entry, + max(2 ticks,
    0.1 ATR_tf). Falls back to the model stop. Returns (stop | None, note); None = skip (stop under min_stop_atr x ATR_tf)."""
    info = (s.get("raw") or {}).get("info") or {}
    ext_t, atr = info.get("ext_t"), info.get("atr_tf")
    tf = int(swing_tf or info.get("trigger_tf") or info.get("tf") or 1)
    d, E = s["dir"], float(s["entry"])
    if not ext_t or not atr or m1 is None:
        return float(s["stop"]), "no sweep info / 1m data: model stop"
    a = int(np.searchsorted(m1["t"], int(ext_t)))
    z = int(np.searchsorted(m1["t"], int(s["entry_t"]) - 60, side="right"))
    if z - a < 3:
        return float(s["stop"]), "too few bars after the sweep: model stop"
    T, H, L = m1["t"][a:z], m1["h"][a:z], m1["l"][a:z]
    if tf > 1:
        key = (T - (T % (60 * tf)))
        last_ok = int(s["entry_t"]) - 60 * tf                 # only tf-bars closed by the entry
        ks, idx = np.unique(key, return_index=True)
        HH = np.maximum.reduceat(H, idx)
        LL = np.minimum.reduceat(L, idx)
        keep = ks <= last_ok
        HH, LL = HH[keep], LL[keep]
    else:
        HH, LL = H, L
    n = len(LL)
    lvl = None
    for m in range(n - 3, 1, -1):
        if d > 0 and LL[m] < min(LL[m - 2], LL[m - 1]) and LL[m] <= min(LL[m + 1], LL[m + 2]):
            lvl = float(LL[m])
            break
        if d < 0 and HH[m] > max(HH[m - 2], HH[m - 1]) and HH[m] >= max(HH[m + 1], HH[m + 2]):
            lvl = float(HH[m])
            break
    if lvl is None:
        return float(s["stop"]), "no swing after the sweep: model stop"
    buf = max(2 * TICK, 0.1 * float(atr))
    st = lvl - d * buf
    if (E - st) * d < min_stop_atr * float(atr):
        return None, f"recent-swing stop {abs(E - st):.1f} pts < {min_stop_atr:g} x ATR({tf}m) {float(atr):.1f}: skip"
    if (E - st) * d >= (E - float(s["stop"])) * d:
        return float(s["stop"]), "recent swing is not tighter: model stop"
    return st, f"recent {tf}m swing {_px(lvl)} + {buf:.2f} buffer"


# ------------------------------------------------------------------------------------------------ simulation
def _sub_bars(i, C, m1, t_from=None):
    """Intrabar path for bar i: 1m (high, low) pairs when they reproduce the 5m bar (from t_from on, for an entry
    inside the bar), else the 5m bar itself (None when an inside-the-bar entry has no 1m data)."""
    t0 = int(C.t[i])
    if m1 is not None:
        a = int(np.searchsorted(m1["t"], t0))
        z = int(np.searchsorted(m1["t"], t0 + BAR))
        if z > a and abs(m1["h"][a:z].max() - C.h[i]) <= TICK + 1e-9 and abs(m1["l"][a:z].min() - C.l[i]) <= TICK + 1e-9:
            if t_from is not None and t_from > t0:
                a = int(np.searchsorted(m1["t"], t_from))
            return list(zip(m1["h"][a:z], m1["l"][a:z]))
    if t_from is not None and t_from > t0:
        return None
    return [(C.h[i], C.l[i])]


def bar_of(C, t):
    """Index of the 5m bar that starts at or contains time t (the next bar when t falls in a data gap)."""
    i = int(np.searchsorted(C.t, int(t), side="right")) - 1
    if i < 0:
        return 0
    if int(C.t[i]) + BAR <= int(t):
        i += 1
    return i


def simulate(C, s, plan, q, cfg, m1=None):
    """Bar-by-bar replay of the plan. Returns dict(legs, log, exit_t, mae_usd, mfe_r, be, partial).
    With 1m data the path inside each 5m bar is walked minute by minute (stop first inside each minute) and the
    break-even move after TP1 / +1R applies from the next minute; every other decision stays on 5m closes."""
    d, E = s["dir"], float(s["entry"])
    S0, R, T, tp1 = plan["stop"], plan["R"], plan["T"], plan.get("tp1")
    limit = s.get("entry_kind") == "limit"
    slip_in = 0.0 if limit else SLIP
    fill_in = E + d * slip_in
    pv = PV.get(cfg["sym"], 2.0)
    t_in = int(s["entry_t"])
    i0 = bar_of(C, t_in)
    n = len(C.t)
    if i0 >= n:
        return None
    mid = int(C.t[i0]) < t_in                     # entry inside a 5m bar (1m-trigger models)
    k = int(C.di[i0])
    q1 = 0
    if tp1 is not None and q >= 2:
        q1 = min(q - 1, int(math.ceil(q / 2)))
    rem = q
    stop = S0
    be = partial = False
    mfe = 0.0
    legs, log = [], []
    realized = 0.0
    worst = 0.0
    atr = max(float(C.atr5[max(0, i0 - 1)]), TICK)
    buf = plan.get("buf") or max(2 * TICK, 0.1 * atr)
    swings = []                                   # unbroken in-favor swing levels formed after entry: (level, idx)
    exit_t = None
    i = i0
    manage = cfg["manage"]

    def leg(qty, px, kind, tm):
        nonlocal realized
        fo = px - d * SLIP if kind in ("stop", "market", "time") else px
        realized += (fo - fill_in) * d * pv * qty
        legs.append((int(qty), float(px), kind, int(tm)))

    while i < n and int(C.di[i]) == k and rem > 0:
        tm = int(C.t[i])
        mod_c = (int(C.mod[i]) + 5) % 1440
        first_min_stop_only = False
        if i == i0 and mid:
            path, stop_only = _sub_bars(i, C, m1, t_from=t_in), False
            if path is None:                          # inside-the-bar entry without 1m data: stop check only
                path, stop_only = [(C.h[i], C.l[i])], True
            elif limit:                               # a limit filled inside this minute: stop check only on it
                first_min_stop_only = True
        elif i == i0 and limit:                       # limit filled inside this 5m bar: stop check only
            path, stop_only = [(C.h[i], C.l[i])], True
        else:
            path, stop_only = _sub_bars(i, C, m1), False
        fine = len(path) > 1 or (i == i0 and mid and not stop_only)
        done = False
        for jj, (hh, ll) in enumerate(path):
            adverse = ll if d > 0 else hh
            unreal = (adverse - fill_in) * d * pv * rem
            worst = min(worst, realized + unreal)
            if (ll <= stop) if d > 0 else (hh >= stop):
                kind = "stop"
                leg(rem, stop, kind, tm + BAR)
                log.append((tm + BAR, f"stopped at {_px(stop)}" + (" (break-even / trailed stop)" if (stop - E) * d >= 0 else "")))
                rem = 0
                done = True
                break
            if stop_only or (first_min_stop_only and jj == 0):
                continue
            mfe = max(mfe, ((hh - E) if d > 0 else (E - ll)) / R)
            if q1 and not partial and ((hh >= tp1 + TICK) if d > 0 else (ll <= tp1 - TICK)):
                leg(q1, tp1, "target", tm + BAR)
                rem -= q1
                partial = True
                log.append((tm + BAR, f"partial {q1} at the internal draw {_px(tp1)}"))
            if rem > 0 and ((hh >= T + TICK) if d > 0 else (ll <= T - TICK)):
                leg(rem, T, "target", tm + BAR)
                log.append((tm + BAR, f"target {_px(T)} ({plan.get('T_label')}) delivered"))
                rem = 0
                done = True
                break
            if fine and manage and not be and (partial or mfe >= cfg["be_r"]):
                ns = E + d * 2 * TICK                 # with 1m data the break-even move is live from the next minute
                if (ns - stop) * d > 0:
                    stop = ns
                    log.append((tm + BAR, ("partial banked" if partial else f"+{mfe:.1f}R in my favor") + f": stop to break-even {_px(ns)} (1m)"))
                be = True
        if done:
            exit_t = tm + BAR
            break
        cl, op = C.c[i], C.o[i]
        # swing bookkeeping (k=2): bar m = i-2 confirmed at the close of i
        m = i - 2
        if m >= i0 + (1 if limit else 0) and m >= 2:
            if d > 0 and C.h[m] > max(C.h[m - 2], C.h[m - 1]) and C.h[m] >= max(C.h[m + 1], C.h[m + 2]):
                swings.append((float(C.h[m]), m))
            if d < 0 and C.l[m] < min(C.l[m - 2], C.l[m - 1]) and C.l[m] <= min(C.l[m + 1], C.l[m + 2]):
                swings.append((float(C.l[m]), m))
        bos_pl = None
        if swings:
            broken = [(lv, mm) for lv, mm in swings if (cl - lv) * d > 0]
            if broken:
                mm = max(b[1] for b in broken)
                bos_pl = float(C.l[mm:i + 1].min()) if d > 0 else float(C.h[mm:i + 1].max())
                swings = [(lv, x) for lv, x in swings if (cl - lv) * d <= 0]
        reason = None
        if 955 <= mod_c < 1080:
            reason = ("time", "15:55: flat for the day")
        elif manage:
            # MGMT-5 opposing CISD with displacement (series in favor that began after entry)
            j = i - 1
            while j >= i0 and (C.c[j] - C.o[j]) * d <= 0:
                j -= 1
            end = j
            while j >= i0 and (C.c[j] - C.o[j]) * d > 0:
                j -= 1
            start = j + 1
            if end >= i0 and start >= i0 and start <= end and j >= i0 - 1:
                body = abs(cl - op)
                rng = max(C.h[i] - C.l[i], TICK)
                against = (cl - op) * d < 0
                disp = body >= 1.0 * atr and body >= 0.6 * rng
                gap = (i >= 2 and ((C.h[i] < C.l[i - 2]) if d > 0 else (C.l[i] > C.h[i - 2])))
                if against and (cl - C.o[start]) * d < 0 and (disp or gap) and (start > i0 or not limit):
                    reason = ("market", "opposing displacement closed through the open of the in-favor series (CISD against): delivery changed state")
            if reason is None and mfe >= cfg["giveback_r"] and (cl - E) * d < 0:
                reason = ("market", f"it reached +{mfe:.1f}R and came all the way back through my entry: giveback exit")
            if reason is None and (i - i0 + 1) >= cfg["stall_bars"] and mfe < cfg["stall_mfe"] and not partial:
                reason = ("time", f"{5 * (i - i0 + 1)} min in and only +{mfe:.2f}R: no progress, the idea isn't working")
            if reason is None and mod_c == 720 and (stop - E) * d < 0:
                reason = ("time", "12:00 and the stop is still on the wrong side of entry: lunch is no place for open risk")
        if reason is not None:
            leg(rem, float(cl), reason[0], tm + BAR)
            log.append((tm + BAR, f"exit {rem} at {_px(cl)}: {reason[1]}"))
            rem = 0
            exit_t = tm + BAR
            break
        if manage:
            if not be and (partial or mfe >= cfg["be_r"]):
                ns = E + d * 2 * TICK
                if (ns - stop) * d > 0:
                    stop = ns
                    log.append((tm + BAR, ("partial banked" if partial else f"+{mfe:.1f}R in my favor") + f": stop to break-even {_px(ns)}"))
                be = True
            elif be and bos_pl is not None:
                ns = bos_pl - d * buf
                if (ns - stop) * d > 0:
                    stop = ns
                    log.append((tm + BAR, f"5m break of structure in my favor: trail under the protected {'low' if d > 0 else 'high'} to {_px(ns)}"))
        i += 1
    live = None
    if rem > 0:                                     # data ended (live) or the session closed without a 15:55 bar
        j = min(i, n) - 1
        kind = "open" if i >= n else "time"
        if kind == "open":
            live = {"live_stop": float(stop), "live_target": float(tp1 if (q1 and not partial) else T), "live_qty": int(rem),
                    "live_be": be}
        leg(rem, float(C.c[j]), "market" if kind == "open" else "time", int(C.t[j]) + BAR)
        log.append((int(C.t[j]) + BAR, "end of data: still open" if kind == "open" else "session over: flat"))
        exit_t = int(C.t[j]) + BAR
        legs[-1] = (legs[-1][0], legs[-1][1], kind if kind == "open" else "time", legs[-1][3])
    return {"legs": legs, "log": log, "exit_t": exit_t, "mae_usd": round(-min(0.0, worst), 2), "mfe_r": round(mfe, 2),
            "be": be, "partial": partial, "fill_in": fill_in, "live": live}


def _trade_from(s, plan, q, sim, cfg, extra):
    d, E = s["dir"], float(s["entry"])
    pv = PV.get(cfg["sym"], 2.0)
    fill_in = sim["fill_in"]
    pnl = 0.0
    for qty, px, kind, _ in sim["legs"]:
        fo = px - d * SLIP if kind in ("stop", "market", "time", "open") else px
        pnl += (fo - fill_in) * d * pv * qty
    pnl -= COMM * q
    R = plan["R"]
    r = pnl / (R * pv * q) if q and R else 0.0
    xq = sum(l[0] for l in sim["legs"])
    xpx = sum(l[0] * l[1] for l in sim["legs"]) / max(xq, 1)
    kind = sim["legs"][-1][2] if sim["legs"] else "market"
    t0 = int(s["entry_t"])
    day = (dt.datetime.fromtimestamp(t0, NAR_ET()) + dt.timedelta(hours=6)).strftime("%Y-%m-%d")
    out = {"day": day, "entry_t": t0, "exit_t": int(sim["exit_t"] or t0), "dir": int(d), "entry": float(E),
           "stop": float(plan["stop"]), "exit": round(float(xpx), 2), "exit_kind": kind,
           "setup": f"{s.get('model', '?')}:{s.get('setup', '')}", "qty": int(q), "risk_pts": round(R, 2),
           "pnl": round(pnl, 2), "r": round(r, 3), "sym": cfg["sym"], "mae_usd": sim["mae_usd"], "mfe_r": sim["mfe_r"],
           "legs": sim["legs"], "model": s.get("model")}
    out.update(extra)
    if sim.get("live"):
        out.update(sim["live"])
    return out


# ------------------------------------------------------------------------------------------------ main entry
def setups_from_trades(trades, kind, bars5=None, model=""):
    """Turn a model's trade list into setups (entries, directions, stops, own targets; exits are ignored).
    kind: 'engine' (entry_t = fill-bar open, stop from risk_pts), 'signal_open' (entry_t = signal-bar open, market at
    its close), 'close' (entry_t = signal close, market), 'limit' (entry_t = fill-bar open), 'cont' (per trade: FVG =
    limit, IFVG = close)."""
    out = []
    C = None
    if kind == "engine":
        _load()
        C = NAR.ctx(bars5)
    for t in trades:
        d = int(t["dir"])
        if kind == "engine":
            i = int(np.searchsorted(C.t, int(t["entry_t"])))
            if i <= 0 or i >= len(C.t) or int(C.t[i]) != int(t["entry_t"]):
                continue
            fill = float(C.o[i]) + d * TICK
            stop = fill - d * float(t["risk_pts"])
            E = float(C.c[i - 1])
            rr = (t.get("f") or {}).get("rr_plan")
            tgt = fill + d * float(rr) * float(t["risk_pts"]) if rr else None
            out.append({"entry_t": int(t["entry_t"]), "dir": d, "entry": E, "stop": stop, "entry_kind": "market",
                        "target": tgt, "model": model, "setup": t.get("trigger") or t.get("setup") or "engine",
                        "trigger_tf": "5m", "raw": t})
            continue
        k = kind
        if kind == "cont":
            k = "limit" if str(t.get("setup", "")).startswith("FVG") else "close"
        et = int(t["entry_t"]) + (BAR if k == "signal_open" else 0)
        x = {"entry_t": et, "dir": d, "entry": float(t["entry"]), "stop": float(t["stop"]),
             "entry_kind": "limit" if k == "limit" else "market", "target": t.get("target"), "model": model,
             "setup": t.get("setup", ""), "trigger_tf": "5m", "raw": t}
        if kind == "atm":                         # the owner's ATM model: the sweep is of the 07:00-09:25 range
            info = t.get("info") or {}
            x["sweep_label"] = "ATM-H" if "high-sweep" in str(t.get("setup", "")) else "ATM-L"
            ext_t = info.get("ext_t")
            if ext_t:
                x["sweep_t"] = int(ext_t) - int(ext_t) % BAR
            if info.get("ext_px") is not None:
                x["sweep_extreme"] = float(info["ext_px"])
            if info.get("ifvg_pts") is not None:
                x["ifvg_pts"] = float(info["ifvg_pts"])
            if info.get("bars_to_v") is not None:
                x["bars_to_v"] = int(info["bars_to_v"])
            tf = t.get("trigger_tf") or info.get("trigger_tf") or info.get("tf")
            if tf:
                x["trigger_tf"] = f"{int(tf)}m" if str(tf).isdigit() else str(tf)
        out.append(x)
    return out


class Layer:
    """Stateful person: carries the simulated account, day counters and the frequency memory across setups."""

    def __init__(self, cfg):
        self.cfg = cfg
        self.acct = RP.EvalAccount() if (RP is not None and cfg["sizing"]) else None
        self.evals = {"pass": 0, "fail": 0, "abandoned": 0}
        self.k = None
        self.day = {"pnl": 0.0, "trades": 0, "wins": 0, "losses": 0, "halted": False}
        self.busy_until = 0
        self.taken_k = []

    def new_day(self, k):
        if self.k is not None and k != self.k:
            if self.acct is not None and self.day["trades"]:
                st = self.acct.end_of_day()
                if st in ("PASS", "FAIL"):
                    self.evals["pass" if st == "PASS" else "fail"] += 1
                    self.acct = RP.EvalAccount()
            self.day = {"pnl": 0.0, "trades": 0, "wins": 0, "losses": 0, "halted": False}
        self.k = k

    def day_rule(self):
        c, d = self.cfg, self.day
        if d["trades"] >= c["max_trades_day"]:
            return f"already {d['trades']} trades today"
        if d["losses"] >= c["max_losses_day"]:
            return f"{d['losses']} losers today: done"
        if d["pnl"] <= -c["day_stop"]:
            return f"day P&L {d['pnl']:+,.0f} <= -${c['day_stop']:,.0f}: done"
        if d["wins"] >= 1:
            return f"already banked a +{c['win_stop_r']:g}R winner today: done"
        return None

    def size(self, grade, stop_pts):
        c = self.cfg
        pv = PV.get(c["sym"], 2.0)
        if self.acct is None:
            q = int(min(MAX_QTY, c["flat_risk"] // (stop_pts * pv))) if stop_pts > 0 else 0
            return q, (f"flat ${c['flat_risk']:.0f}: {q} MNQ" if q else "stop too wide for 1 MNQ at $350"), "flat"
        if c.get("risk_policy") == "recommended" and "RECOMMENDED" in getattr(RP, "POLICIES", {}):
            base = dict(RP.POLICIES["RECOMMENDED"])         # the risk manager's final pick (flat $350, cushion cap, guards)
        else:
            base = {**RP.DEFAULTS, "name": "trader_layer", "tiers": True, "tier_risk": dict(c["tier_risk"]),
                    "tier_max_micros": dict(c["tier_max"]), "guard": True}
        pol = {**RP.DEFAULTS, **base, "max_trades_day": c["max_trades_day"], "stop_after_win": True,
               "max_losses_day": c["max_losses_day"], "day_stop": c["day_stop"], "point_value": pv}
        ds = {"pnl": self.day["pnl"], "trades": self.day["trades"], "wins": self.day["wins"],
              "losses": self.day["losses"], "halted": self.day["halted"]}
        res = RP.size(grade, stop_pts, self.acct.account_state(), ds, pol)
        dead = res["code"] == "guard" and (self.acct.balance - self.acct.mll) - pol["guard_buffer"] < \
            (stop_pts + pol["guard_slip_pts"]) * pv + pol["comm_rt"]
        if (not dead and c.get("risk_policy") == "recommended" and res["code"] in ("guard", "too_wide")
                and hasattr(RP, "account_dead")):          # the cushion cap can leave a near-dead eval stuck
            try:
                dead = bool(RP.account_dead(self.acct.account_state(), stop_pts, pol)[0])
            except Exception:
                dead = False
        if dead:
            self.evals["abandoned"] += 1
            self.acct = RP.EvalAccount()
            res = RP.size(grade, stop_pts, self.acct.account_state(), ds, pol)
            res["reason"] = "near-dead eval abandoned, fresh 50K: " + res["reason"]
        return int(res["qty_micros"]), res["reason"], res["code"]

    def record(self, tr):
        self.day["trades"] += 1
        self.day["pnl"] += tr["pnl"]
        if tr["r"] >= self.cfg["win_stop_r"]:
            self.day["wins"] += 1
        if tr["pnl"] < 0:
            self.day["losses"] += 1
        if self.acct is not None:
            self.acct.record_trade(tr["pnl"], -abs(tr.get("mae_usd", 0.0)))
            if self.acct.halted:
                self.day["halted"] = True
        self.busy_until = int(tr["exit_t"])
        self.taken_k.append(self.k)


def apply(setups, bars5, es5=None, config=None, log=None, bars1=None, layer=None):
    """Trade `setups` like a person. Returns the taken trades (make_trade format + grade / plan / thoughts / mgmt).
    log: optional list that receives one decision record per setup (taken or skipped, with the reason).
    bars1: optional 1m DataFrame (time/high/low) to resolve stop-vs-target order inside ambiguous 5m bars."""
    _load()
    cfg = {**DEFAULT, **(config or {})}
    if NAR is None or LM is None:
        raise RuntimeError(f"trader_layer needs engine.narrative and engine.liquidity_map: {_IMPORT_ERR}")
    if RP is None:
        cfg["sizing"] = False
    C = NAR.ctx(bars5)
    _cache(C)
    m1 = None
    if bars1 is not None and len(bars1):
        m1 = {"t": bars1["time"].to_numpy(np.int64), "h": bars1["high"].to_numpy(float), "l": bars1["low"].to_numpy(float)}
    L = layer or Layer(cfg)
    out = []
    t_first, t_last = int(C.t[0]), int(C.t[-1]) + BAR
    for s in sorted(setups, key=lambda x: (int(x["entry_t"]), -abs(x["entry"] - x["stop"]))):
        t_dec = int(s["entry_t"])
        rec = {"entry_t": t_dec, "dir": s["dir"], "model": s.get("model"), "setup": s.get("setup")}
        if t_dec <= t_first + 20 * BAR or t_dec > t_last:
            continue
        i_dec = C.idx_at(t_dec)
        i_in = bar_of(C, t_dec)
        if i_dec < 2 or i_in >= len(C.t):
            continue
        k = int(C.di[i_in])
        L.new_day(k)
        mod_dec = (int(C.mod[i_dec]) + 5) % 1440
        rec["day"] = C.days[k]
        replay = bool(cfg.get("replay_raw")) and s.get("raw") is not None
        if not replay and t_dec < L.busy_until:
            rec.update(decision="skip", reason="already in a position")
            log is not None and log.append(rec)
            continue
        why = None if replay else L.day_rule()
        if why:
            rec.update(decision="skip", reason="day rule: " + why)
            log is not None and log.append(rec)
            continue
        try:
            nar = NAR.narrative(bars5, t_dec, es5)
        except Exception as ex:
            nar = {"bias": "neutral", "bias_dir": 0, "conviction": 0.0, "draw": None, "day_type": "normal",
                   "story": f"narrative failed ({type(ex).__name__})", "news": {"events": [], "cpi_nfp": False, "fomc": False}}
        bsrc = cfg.get("bias_source") or "narrative"
        xb = None                                       # external bias: (dir, label, why)
        if bsrc != "narrative" and cfg["judgment"]:      # engine/daily_bias.py (same dir semantics as the brain)
            DB = _imp("daily_bias")
            if DB is not None:
                try:
                    meth = bsrc.split(":", 1)[1] if ":" in bsrc else DB.DEFAULT_METHOD
                    br = DB.bias(bars5, t_dec, method=meth)
                    bd = int(br.get("dir") or 0)
                    xb = (bd, {1: "long", -1: "short", 0: "neutral"}[bd], f"daily_bias {meth}: {br.get('why', '')}"[:200])
                    rec["xbias"] = bd
                    if cfg.get("bias_replace"):          # the external bias also replaces the brain's bias in assess()
                        nar = {**nar, "bias_dir": bd, "bias": xb[1], "conviction": float(br.get("confidence") or 0.5),
                               "bias_failed": False, "bias_why": xb[2]}
                except Exception as ex:
                    rec["bias_error"] = f"{type(ex).__name__}: {ex}"
        gate_dir = xb[0] if xb is not None else int(nar.get("bias_dir", 0) or 0)
        gate_lab = xb[1] if xb is not None else nar.get("bias")
        # sweep context (for the brain's quality / manipulation elements)
        sw = {}
        if s.get("sweep_label") is None:
            try:
                inf = NAR.infer_setup(bars5, t_dec, s["dir"], abs(s["entry"] - s["stop"]))
                sw = {"sweep_label": inf.get("sweep_label"), "sweep_t": inf.get("sweep_t"),
                      "sweep_extreme": inf.get("sweep_extreme")}
            except Exception:
                sw = {}
        s2 = {**s, **{kk: v for kk, v in sw.items() if s.get(kk) is None}}
        if cfg.get("stop_mode") == "recent_swing":       # coordinator variant for the ATM model (RULES section 8)
            st_new, note = recent_swing_stop(s2, m1, cfg.get("min_stop_atr", 1.0), cfg.get("swing_tf"))
            if st_new is None:
                rec.update(decision="skip", reason="stop: " + note)
                log is not None and log.append(rec)
                continue
            s2 = {**s2, "stop": st_new, "stop_note": note}
            rec["stop_note"] = note
        # ---- J: context vetoes first (cheap), then the plan, then the brain's grade on that plan
        if cfg["judgment"]:
            v = vetoes(C, cfg, s2, nar, i_dec, mod_dec)
            if v:
                rec.update(decision="skip", reason="veto: " + v)
                log is not None and log.append(rec)
                continue
            if cfg["bias_align"] in ("require", "skip_counter") and gate_dir not in (0, s["dir"]):
                rec.update(decision="skip", reason=f"against the {gate_lab} bias (bias_align={cfg['bias_align']}, {bsrc})")
                log is not None and log.append(rec)
                continue
        try:
            plan, pwhy = make_plan(C, cfg, s2, i_dec, t_dec, mod_dec, nar)
        except Exception as ex:
            plan, pwhy = None, f"plan failed: {type(ex).__name__}: {ex}"
            traceback.print_exc()
        if plan is None:
            rec.update(decision="skip", reason="plan: " + pwhy)
            log is not None and log.append(rec)
            continue
        grade, verdict, thoughts = "B", None, ""
        if cfg["judgment"]:
            st = {"entry_t": t_dec, "dir": s["dir"], "entry": float(s["entry"]), "stop": plan["stop"],
                  "targets": [plan["T"]], "sweep_label": s2.get("sweep_label"), "sweep_t": s2.get("sweep_t"),
                  "trigger_tf": s2.get("trigger_tf", "5m")}
            for kk in ("ifvg_pts", "bars_to_v", "sweep_level"):
                if s2.get(kk) is not None:
                    st[kk] = s2[kk]
            trust = {"E1_align": 0.0} if cfg["bias_align"] == "off" else None
            try:
                verdict = NAR.assess(st, nar, bars5, es5, version=cfg["version"], trust=trust)
                grade = verdict["grade"]
                thoughts = verdict.get("thoughts", "")
                cut = thoughts.find("; plan:")             # the layer states its own plan below
                if cut > 0:
                    thoughts = thoughts[:cut] + "."
                if cfg["bias_align"] == "grade_pm1" and xb is not None and not verdict.get("veto"):
                    adj = 1.0 if xb[0] == s["dir"] else (-1.0 if xb[0] == -s["dir"] else 0.0)
                    S2 = float(verdict["score"]) + adj
                    gc = NAR.GRADE_CUT
                    grade = "A" if S2 >= gc["A"] else ("B" if S2 >= gc["B"] else ("C" if S2 >= gc["C"] else "SKIP"))
                    verdict = {**verdict, "score": round(S2, 2), "grade": grade}
                    rec["bias_adj"] = adj
                    thoughts += f" {xb[2][:120]} -> {adj:+.0f} to the grade (now {grade}, {S2:+.1f})."
            except Exception as ex:
                grade, thoughts = "B", f"(brain unavailable: {type(ex).__name__}; graded B)"
            if verdict is not None and verdict.get("veto"):
                rec.update(decision="skip", reason="veto: " + str(verdict["veto"]), grade="SKIP")
                log is not None and log.append(rec)
                continue
            if grade == "SKIP":
                recent = sum(1 for kk in L.taken_k if k - cfg["freq_sessions"] < kk <= k)
                if recent < cfg["freq_floor"]:
                    grade = "C"
                    thoughts = thoughts.replace("; I pass.", ", so normally I'd pass.")
                    thoughts += f" But only {recent} trade(s) in the last {cfg['freq_sessions']} sessions: I take it small (C) to keep my 2-a-week rhythm."
                else:
                    rec.update(decision="skip", reason=f"brain: SKIP (score {verdict['score']:+.1f})", grade="SKIP")
                    log is not None and log.append(rec)
                    continue
        if replay:                                     # post-hoc JF row: keep / drop the model's own trade
            tr = {kk: v for kk, v in s["raw"].items()}
            if "mae_usd" not in tr and tr.get("mae") is not None and tr.get("risk_pts") and tr.get("qty"):
                tr["mae_usd"] = round(float(tr["mae"]) * float(tr["risk_pts"]) * PV.get(cfg["sym"], 2.0) * int(tr["qty"]), 2)
            tr.update({"grade": grade, "thoughts": thoughts, "model": s.get("model"), "replayed": True})
            L.k = k
            L.taken_k.append(k)
            out.append(tr)
            rec.update(decision="take", grade=grade, pnl=tr.get("pnl"), r=tr.get("r"))
            log is not None and log.append(rec)
            continue
        # ---- retest entry (coordinator variant, RULES section 8): rest a limit at the trigger zone instead of paying
        #      the trigger close; filled only if price trades back through it within the window
        if cfg.get("entry") == "retest" and s2.get("entry_kind") != "limit":
            zk, lvl = trigger_zone(C, i_dec, s["dir"], s2)
            better = (float(s2["entry"]) - lvl) * s["dir"] >= TICK and (lvl - plan["stop"]) * s["dir"] > TICK
            rec["retest_zone"] = zk
            if better:
                ft, how = retest_fill(C, s2, plan, lvl, cfg.get("retest_min", 30), m1)
                if ft is None:
                    rec.update(decision="skip", reason=f"retest: {how} ({zk} {_px(lvl)})", grade=grade, retest="miss")
                    log is not None and log.append(rec)
                    continue
                Rn = abs(lvl - plan["stop"])
                plan = {**plan, "R": Rn, "T_r": round(abs(plan["T"] - lvl) / Rn, 2),
                        "tp1_r": (round(abs(plan["tp1"] - lvl) / Rn, 2) if plan.get("tp1") is not None else None),
                        "text": plan["text"] + f"; entry on the retest of the {zk} at {_px(lvl)}"}
                s2 = {**s2, "entry": lvl, "entry_t": int(ft), "entry_kind": "limit"}
                rec["retest"] = "fill"
            else:
                rec["retest"] = "market (zone not better)"
        # ---- S: size
        slip_in = 0.0 if s2.get("entry_kind") == "limit" else SLIP
        q, swhy, code = L.size(grade, plan["R"] + slip_in)
        if q < 1:
            rec.update(decision="skip", reason="size: " + swhy, grade=grade)
            log is not None and log.append(rec)
            continue
        sim = simulate(C, s2, plan, q, cfg, m1)
        if sim is None or not sim["legs"]:
            continue
        mg = [f"{_et(tm).strftime('%H:%M')} {txt}" for tm, txt in sim["log"]]
        story = nar.get("premarket_story") or nar.get("story") or ""
        th = (thoughts + " " if thoughts else "") + f"Plan: stop {_px(plan['stop'])} (R {plan['R']:.1f} pts" + \
             (f", model stop + {plan['buf']:.2f} buffer" if plan.get("buf") else "") + f"); {plan['text']}." + \
             (f" Why that target: {plan['why_T']}." if plan.get("why_T") else "") + f" Size: {swhy}"
        extra = {"grade": grade, "score": verdict.get("score") if verdict else None, "plan": {kk: plan[kk] for kk in plan if kk != "text"},
                 "plan_text": plan["text"], "thoughts": th, "mgmt": mg, "narrative": story[:600],
                 "bias": nar.get("bias"), "day_type": nar.get("day_type"), "size_reason": swhy,
                 "be": sim["be"], "partial": sim["partial"], "entry_kind": s.get("entry_kind", "market")}
        tr = _trade_from(s2, plan, q, sim, cfg, extra)
        L.record(tr)
        out.append(tr)
        rec.update(decision="take", grade=grade, pnl=tr["pnl"], r=tr["r"])
        log is not None and log.append(rec)
    if layer is None:
        L.new_day(-1)
    apply.last_layer = L
    return out


def state(trades, log=None):
    """Small dashboard dict: last decision and the thoughts behind it."""
    last = trades[-1] if trades else None
    return {"last_trade": None if last is None else {kk: last.get(kk) for kk in ("day", "dir", "entry", "stop", "exit", "pnl", "r",
                                                                             "grade", "plan_text", "thoughts", "mgmt")},
            "last_decision": (log[-1] if log else None), "imports": dict(_IMPORT_ERR)}
