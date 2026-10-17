"""Causal liquidity map: every draw on liquidity on the trade's side of price, and what stands in the way.

API - stable, usable by any model (tools/trader_layer.py), no engine needed:
  draws_at(bars5_df, t_entry, d, entry, stop, es5_df=None, **opts) -> list[dict]
      bars5_df: strategy_lab frame (time = bar open in unix s, open/high/low/close/volume; et/day/mod optional).
      t_entry: decision time (unix s); only bars CLOSED at or before it are used (time + 300 <= t_entry).
      d: +1 long / -1 short; entry / stop: planned prices (R = |entry - stop|). es5_df is accepted, not used.
      Returns every draw beyond entry, nearest first. Keys: kind (ERL pool | IRL gap), source, tier (A/B/C), price,
      dist, dist_r, dist_atr, obstacles, age_h, eq, htf_dir, session, within_reach, label, role ("final" = the chosen
      target T, "partial" = TP1, else None) and target (exit price) on the two role draws.
      opts: pick ("farthest_reach" default | "tier" | "significance"), pm_nearest (True: PM entries take the nearest
      within-reach draw), min_rr 2.0, alt_min_rr 1.5, partial_min_r 1.0, mitigation, fvg_min, min_fvg, tick,
      lookback_days. Standalone limits: eq is always False (no D8 detector), pools are rebuilt from the 5m frame.
  new_position(d, entry, stop, qty, entry_i, target, tp1=None) -> position dict
  manage_step(position, bar_index, context) -> {"fills": [{qty, price, reason}], "closed": bool, "stop": float}
      person-style management of one CLOSED bar (DOL_PLAYBOOK MGMT-1..8, = the engine's manage_mode "person");
      context = {"o","h","l","c","mod": numpy arrays, "atr": float or array, "params": MANAGE_DEFAULTS overrides}.
Engine building blocks: LiquidityBook (live FVGs + extra pools, fed bar by bar), live_swings, draws, pick_primary,
pick_partial, nearest_in_reach, features (the draw-learner feature dict), wilder_atr.

Used by engine/model.py when target_mode = "draw" and manage_mode = "person". Nothing here runs with the engine defaults.
Definitions follow research/lab/DOL_PLAYBOOK.md (D3, D6, D7, DOL-1..6); deviations are noted inline.

  ERL  resting liquidity (stops), every pool: the engine's pools - prior week H/L, prior day H/L, Asia / London /
       overnight H/L, 1H swings, 15m internal swings, equal highs/lows - plus the extra pools kept here: prior RTH H/L
       (from 16:00), 4H / daily 3-bar swings (from the close of the confirming bar) and fresh 5m (k=2, today or
       yesterday) / 15m (k=1, last 5 days) swing points. Prior-day H/L and session H/L older than the current CME day
       are dropped (D7 lists only the previous day's H/L and today's sessions).
  IRL  internal range liquidity: live fair value gaps on 5m / 15m / 1H / 4H / 1D that price would rebalance on the way
       (bearish gaps above price for a long, bullish gaps below for a short); only the 10 nearest 4H / 1D gaps count.

Tiers (DOL-3): A = PW, PD, prior RTH, ON, Asia, London H/L, 4H / daily swings, equal highs/lows on 15m+
               B = 1H swings, live 1H / 4H / 1D gaps
               C = 15m / 5m swings, live 5m / 15m gaps
Gap lifecycle (D6): a gap is a draw until a WICK touches its CE (selectable: ce_touch | ce_close | touch | full);
  expiry 5m = end of the next CME day, 15m = 5 days, 1H = 10 days, 4H / 1D never. Minimum size 5m = max(1 tick,
  0.1 x ATR14), 15m+ = 1 tick (fvg_min "playbook"), or the engine's min_fvg x {1, 1.5, 2.5, 4, 8} (fvg_min "engine").
Path resistance (DOL-6): obstacles = fresh 5m (k=2) / 15m (k=1) swing points + live opposing 15m+ gaps strictly
  between entry and the draw, each price zone counted once (a swing inside a gap, or swings within max(2 ticks,
  0.1 ATR) of each other, are one zone). LRLR <= 1, HRLR >= 3.

No lookahead: gaps exist from the CLOSE of their third candle, swings from the close of their confirming bar, pools
from the end of their window; a level is taken / mitigated by CLOSED bars only.

Draw features (one dict per draw; engine/draw_learner.predict() receives `features(x)`):
  kind ERL|IRL, source, tier A|B|C, dist_atr, dist_r, obstacles, age_h, eq, htf_dir (+1/0/-1), session AM|PM
"""
from __future__ import annotations

import math

import numpy as np

SOURCE = {"PWH": "PWH", "PWL": "PWL", "PDH": "PDH", "PDL": "PDL", "PDH2": "PDH", "PDL2": "PDL",
          "ASH": "ASIA", "ASL": "ASIA", "LOH": "LON", "LOL": "LON", "ONH": "ON", "ONL": "ON",
          "RTHH": "RTH", "RTHL": "RTH", "H4H": "H4SW", "H4L": "H4SW", "D1H": "D1SW", "D1L": "D1SW",
          "H1H": "H1SW", "H1L": "H1SW", "ITH": "M15SW", "ITL": "M15SW", "M5H": "M5SW", "M5L": "M5SW",
          "M15H": "M15SW", "M15L": "M15SW"}
# significance ladder (draw_pick "significance"): week > day > session > 1H swing; EQ adds draw_eq_w
SIGNIFICANCE = {"PWH": 4.0, "PWL": 4.0, "PDH": 3.0, "PDL": 3.0, "D1SW": 3.0, "RTH": 3.0, "ASIA": 2.0, "LON": 2.0,
                "ON": 2.0, "H4SW": 2.0, "H1SW": 1.0, "M15SW": 0.0, "M5SW": 0.0, "EQ": 0.0,
                "FVG1D": 0.8, "FVG4H": 0.6, "FVG1H": 0.4, "FVG15": 0.2, "FVG5": 0.1}
TIER_A_SRC = {"PWH", "PWL", "PDH", "PDL", "RTH", "ON", "ASIA", "LON", "H4SW", "D1SW"}
ERL_SRC = TIER_A_SRC | {"H1SW"}
FVG_SOURCE = {"5m": "FVG5", "15m": "FVG15", "1h": "FVG1H", "4h": "FVG4H", "1d": "FVG1D"}
HTF_GAP_TFS = {"1h", "4h", "1d"}
OBST_GAP_TFS = {"15m", "1h", "4h", "1d"}
MITIGATION = ("ce_touch", "ce_close", "touch", "full")
FEATURE_KEYS = ("kind", "source", "tier", "dist_atr", "dist_r", "obstacles", "age_h", "eq", "htf_dir", "session")


# ----------------------------------------------------------------------------------------------- volatility
def wilder_atr(h, l, c, n=14):
    """Wilder ATR(n) for every bar (value at bar j uses bars <= j only), seeded with the running simple mean."""
    h, l, c = (np.asarray(x, float) for x in (h, l, c))
    N = len(h)
    out = np.zeros(N)
    if N == 0:
        return out
    pc = np.r_[c[0], c[:-1]]
    tr = np.maximum(h, pc) - np.minimum(l, pc)
    tr[0] = h[0] - l[0]
    m = min(n, N)
    out[:m] = np.cumsum(tr[:m]) / np.arange(1, m + 1)
    a = out[m - 1]
    for j in range(m, N):
        a = (a * (n - 1) + tr[j]) / n
        out[j] = a
    return out


def buffer(atr, tick, frac=0.1):
    """Playbook stop / trail buffer: max(2 ticks, frac x ATR14_5m)."""
    return max(2 * tick, frac * float(atr))


# ----------------------------------------------------------------------------------------------- book
class LiquidityBook:
    """Live fair value gaps per timeframe plus the extra ERL pools (prior RTH H/L, 4H / daily swings), fed bar by bar as
    bars CLOSE. advance(t_now, i) must be called once per base bar i with t_now = that bar's close time."""
    ENGINE_MULT = {"5m": 1.0, "15m": 1.5, "1h": 2.5, "4h": 4.0, "1d": 8.0}
    AGE_H = {"15m": 120.0, "1h": 240.0}           # 5m: end of the next CME day; 4h / 1d: never
    KEEP_HTF = 40                                 # cap on stored 4H / 1D gaps per direction (the nearest 10 are used)

    def __init__(self, tick, min_fvg, mitigation="ce_touch", min_mode="playbook"):
        if mitigation not in MITIGATION:
            raise ValueError(f"irl_mitigation must be one of {MITIGATION}")
        self.tick, self.min_fvg, self.mode, self.min_mode = float(tick), float(min_fvg), mitigation, min_mode
        self.series, self.swing_series = {}, {}
        self.xpools = []
        self.base = None
        self._rth = None

    # ---- inputs
    def add_gap_series(self, tf, t_open, t_close, h, l, c, start_t=None, atr=None, tday=None):
        t_open = np.asarray(t_open, dtype=np.int64)
        k0 = int(np.searchsorted(t_open, start_t)) if start_t is not None else 0
        self.series[tf] = {"t": t_open, "tc": np.asarray(t_close, dtype=np.int64), "h": np.asarray(h, float),
                           "l": np.asarray(l, float), "c": np.asarray(c, float), "ptr": k0, "k0": k0, "active": [],
                           "atr": atr, "tday": tday}

    def add_swing_series(self, tf, t_open, t_close, h, l, start_t=None, ref=None):
        """3-bar (k=1) swings of an HTF series become Tier-A pools; ref = (t_open, t_close, h, l) of 1H bars used to see
        whether a swing confirmed during the warm-up was already taken before the base bars start."""
        t_open = np.asarray(t_open, dtype=np.int64)
        k0 = int(np.searchsorted(t_open, start_t)) if start_t is not None else 0
        self.swing_series[tf] = {"t": t_open, "tc": np.asarray(t_close, dtype=np.int64), "h": np.asarray(h, float),
                                 "l": np.asarray(l, float), "ptr": max(k0, 0), "k0": k0, "ref": ref}

    def set_base(self, b):
        """Base (5m) bars: prior RTH H/L pools and the per-bar 'taken' check of the extra pools."""
        self.base = b

    # ---- per-bar update
    def advance(self, t_now, i=None):
        for tf, S in self.series.items():
            k, tc = S["ptr"], S["tc"]
            n = len(tc)
            while k < n and tc[k] <= t_now:
                self._gap_bar(tf, S, k)
                k += 1
            S["ptr"] = k
        for tf, S in self.swing_series.items():
            k, tc = S["ptr"], S["tc"]
            n = len(tc)
            while k < n and tc[k] <= t_now:
                self._swing_bar(tf, S, k, t_now)
                k += 1
            S["ptr"] = k
        if i is not None and self.base is not None:
            self._base_bar(i)

    def _mitigated(self, g, h, l, c):
        m = self.mode
        if g["dir"] == -1:                       # bearish gap above price, filled from below
            if m == "ce_touch":
                return h >= g["ce"]
            if m == "ce_close":
                return c >= g["ce"]
            if m == "touch":
                return h >= g["bot"]
            return h >= g["top"]
        if m == "ce_touch":                      # bullish gap below price, filled from above
            return l <= g["ce"]
        if m == "ce_close":
            return c <= g["ce"]
        if m == "touch":
            return l <= g["top"]
        return l <= g["bot"]

    def _min_size(self, tf, S, k):
        if self.min_mode == "engine":
            return self.min_fvg * self.ENGINE_MULT.get(tf, 1.0)
        if tf == "5m" and S["atr"] is not None:
            return max(self.tick, 0.1 * float(S["atr"][k]))
        return self.tick

    def _gap_bar(self, tf, S, k):
        H, L, C = S["h"], S["l"], S["c"]
        h, l, c, tck = H[k], L[k], C[k], int(S["tc"][k])
        td = int(S["tday"][k]) if S["tday"] is not None else None
        age = self.AGE_H.get(tf)
        keep = []
        for g in S["active"]:
            if tf == "5m" and td is not None and g.get("tday") is not None and td > g["tday"] + 1:
                continue                                         # 5m gap: expires at the end of the next CME day
            if age is not None and tck - g["tc"] > age * 3600:
                continue
            if self._mitigated(g, h, l, c):
                continue
            keep.append(g)
        if k - 2 >= S["k0"]:
            mn = self._min_size(tf, S, k)
            g = None
            if l - H[k - 2] >= mn:
                bot, top = float(H[k - 2]), float(l)
                g = {"tf": tf, "dir": 1, "top": top, "bot": bot}
            elif L[k - 2] - h >= mn:
                top, bot = float(L[k - 2]), float(h)
                g = {"tf": tf, "dir": -1, "top": top, "bot": bot}
            if g is not None:
                g.update({"ce": (g["top"] + g["bot"]) / 2, "tc": tck, "t0": int(S["t"][k - 2]), "tday": td})
                keep.append(g)
        if tf in ("4h", "1d") and len(keep) > 2 * self.KEEP_HTF:
            keep = keep[-2 * self.KEEP_HTF:]
        S["active"] = keep

    def _swing_bar(self, tf, S, k, t_now):
        """Bar k closed: it confirms a 3-bar swing at k-1."""
        m = k - 1
        if m - 1 < S["k0"] or m < 1:
            return
        H, L = S["h"], S["l"]
        tc = int(S["tc"][k])
        tag = "H4" if tf == "4h" else "D1"
        for side, ok, lvl in (("H", H[m] > H[m - 1] and H[m] >= H[k], float(H[m])),
                              ("L", L[m] < L[m - 1] and L[m] <= L[k], float(L[m]))):
            if not ok:
                continue
            if self._taken_since(S.get("ref"), side, lvl, tc, t_now):
                continue
            self.xpools.append({"kind": tag + side, "side": side, "price": lvl, "t0": tc, "eq": False,
                                "kinds": [tag + side], "label": f"{tf.upper()} swing {'high' if side == 'H' else 'low'}"})

    def _taken_since(self, ref, side, lvl, t_from, t_now):
        """Was a level confirmed at t_from already traded through (1 tick) by 1H bars that closed by t_now?"""
        if ref is None or t_now <= t_from:
            return False
        t_o, t_c, h, l = ref
        a = int(np.searchsorted(t_o, t_from))
        z = int(np.searchsorted(t_c, t_now, side="right"))
        if z <= a:
            return False
        if side == "H":
            return bool(h[a:z].max() >= lvl + self.tick)
        return bool(l[a:z].min() <= lvl - self.tick)

    def _base_bar(self, i):
        b, tick = self.base, self.tick
        h, l, c = float(b.h[i]), float(b.l[i]), float(b.c[i])
        t1 = int(b.t[i]) + b.secs
        # D6: every gap's state is evaluated on EVERY closed 5m bar (a 1H gap whose CE is wicked at 10:05 stops being a
        # draw at 10:05, not at the 11:00 close). Gaps formed at this very bar's close are left alone.
        for tf, S in self.series.items():
            if tf == b.tf or not S["active"]:
                continue
            S["active"] = [g for g in S["active"] if g["tc"] >= t1 or not self._mitigated(g, h, l, c)]
        if self.xpools:
            self.xpools = [q for q in self.xpools
                           if not ((q["side"] == "H" and h >= q["price"] + tick) or (q["side"] == "L" and l <= q["price"] - tick))]
        mod, td = int(b.mod[i]), int(b.tday[i])
        r = self._rth
        if r is not None and r["tday"] != td:
            r = self._rth = None                                   # the RTH window never closed (data gap)
        if 570 <= mod < 960:
            if r is None:
                r = self._rth = {"tday": td, "h": h, "l": l, "done": False}
            else:
                r["h"], r["l"] = max(r["h"], h), min(r["l"], l)
        if r is not None and not r["done"] and mod + b.secs // 60 >= 960:
            r["done"] = True                                       # 16:00 ET: the prior RTH high / low now exist
            t1 = int(b.t[i]) + b.secs
            self.xpools = [q for q in self.xpools if q["kind"] not in ("RTHH", "RTHL") or t1 - q["t0"] < 30 * 3600]
            for side, lvl in (("H", r["h"]), ("L", r["l"])):
                self.xpools.append({"kind": "RTH" + side, "side": side, "price": float(lvl), "t0": t1, "eq": False,
                                    "kinds": ["RTH" + side], "label": f"RTH {'high' if side == 'H' else 'low'}"})

    # ---- queries
    def gaps(self, gdir, tfs=None):
        out = []
        for tf, S in self.series.items():
            if tfs is not None and tf not in tfs:
                continue
            out.extend(g for g in S["active"] if g["dir"] == gdir)
        return out


def live_swings(H, L, k, end, lookback, tick):
    """Fresh (untaken) fractal swing points of strength k on bars [end-lookback, end] (closed): a swing high at m needs
    H[m] > max(H[m-k:m]) and H[m] >= max(H[m+1:m+k+1]); it is fresh while no later bar trades 1 tick through it.
    Returns (highs, lows) as lists of (price, bar index)."""
    a = max(k, end - lookback)
    if end - a < 2 * k + 1:
        return [], []
    h = np.asarray(H[a - k:end + 1], float)
    lo = np.asarray(L[a - k:end + 1], float)
    n = len(h)
    sufmax = np.maximum.accumulate(h[::-1])[::-1]
    sufmin = np.minimum.accumulate(lo[::-1])[::-1]
    highs, lows = [], []
    for m in range(k, n - k):
        hm, lm = h[m], lo[m]
        if hm > h[m - k:m].max() and hm >= h[m + 1:m + k + 1].max():
            if m + k + 1 >= n or sufmax[m + k + 1] < hm + tick:
                highs.append((float(hm), a - k + m))
        if lm < lo[m - k:m].min() and lm <= lo[m + 1:m + k + 1].min():
            if m + k + 1 >= n or sufmin[m + k + 1] > lm - tick:
                lows.append((float(lm), a - k + m))
    return highs, lows


# ----------------------------------------------------------------------------------------------- the map
def _merge_pools(pools, extra, tick):
    """Engine pools + book pools; the same level from several lenses is one pool (kinds merged)."""
    out = [dict(q, kinds=list(q.get("kinds") or [q["kind"]]), _orig=q) for q in pools]
    for x in extra:
        hit = next((q for q in out if q["side"] == x["side"] and abs(q["price"] - x["price"]) < tick / 2 + 1e-9), None)
        if hit is not None:
            for kk in x["kinds"]:
                if kk not in hit["kinds"]:
                    hit["kinds"].append(kk)
        else:
            out.append(dict(x))
    return out


def classify(q):
    """(source, tier, kind) of a pool. Equal highs/lows on 15m+ are Tier A (the engine's eq flag; see report caveat)."""
    kinds = q.get("kinds") or [q["kind"]]
    srcs = [SOURCE.get(k, "M15SW") for k in kinds]
    best = max(srcs, key=lambda s: SIGNIFICANCE.get(s, 0.0))
    eq = bool(q.get("eq"))
    if any(s in TIER_A_SRC for s in srcs) or eq:
        tier = "A"
    elif "H1SW" in srcs:
        tier = "B"
    else:
        tier = "C"
    src = "EQ" if (eq and best in ("M15SW", "M5SW")) else best
    return src, tier, "ERL", best                   # every resting pool is ERL (D7); only gaps are IRL


DAILY_KINDS = {"PDH", "PDL", "PDH2", "PDL2", "ASH", "ASL", "LOH", "LOL", "ONH", "ONL"}


def draws(d, entry, risk, atr, t_now, pools, book=None, swings=None, h1_trend=0, mod=None, tick=0.25,
          irl_tfs=None, irl_level="edge", eq_w=1.0, day_start_t=None, keep_htf=10):
    """Every draw on liquidity beyond `entry` in direction d (+1 long / -1 short), nearest first.

    pools: the engine's active (unswept) pools; book: LiquidityBook advanced to t_now; swings: {"H": [(price, idx, tf,
    t)], "L": [...]} fresh 5m / 15m swing points. day_start_t: open of the current CME day - prior-day H/L and session
    H/L created before it are stale (D7 lists only the previous day's H/L and today's sessions). keep_htf: only the
    nearest live 4H / 1D gaps on the trade side count (D6). Returns dicts with the module features plus price (the
    level), dist (points), sig, label, pool (engine pool dict or None), gap (bot, top) for gaps."""
    opp = "H" if d == 1 else "L"
    e_d = entry * d
    risk = max(float(risk), 1e-9)
    atr = max(float(atr), 1e-9)
    session = None if mod is None else ("AM" if mod < 720 else "PM")
    htf_dir = int(np.sign(h1_trend * d)) if h1_trend else 0
    irl_set = None if irl_tfs is None else {x.strip().lower() for x in str(irl_tfs).split(",") if x.strip()}
    tol = buffer(atr, tick)

    if day_start_t is not None:
        pools = [q for q in pools if not (set(q.get("kinds") or [q["kind"]]) <= DAILY_KINDS and int(q["t0"]) < day_start_t)]
    all_pools = _merge_pools(pools, book.xpools if book is not None else [], tick)
    gaps = book.gaps(-d) if book is not None else []      # bearish gaps for a long, bullish gaps for a short
    near = (lambda g: g["bot"] * d) if d == 1 else (lambda g: g["top"] * d)
    far = (lambda g: g["top"] * d) if d == 1 else (lambda g: g["bot"] * d)
    if keep_htf:
        hi_tf = sorted((g for g in gaps if g["tf"] in ("4h", "1d") and far(g) > e_d), key=near)[:keep_htf]
        gaps = [g for g in gaps if g["tf"] not in ("4h", "1d")] + hi_tf

    # ---- path resistance zones beyond entry (DOL-6): fresh 5m/15m swings + live opposing 15m+ gaps, merged
    items = [(near(g), far(g)) for g in gaps if g["tf"] in OBST_GAP_TFS and near(g) > e_d]
    sw = [] if swings is None else [s for s in swings.get(opp, []) if s[0] * d > e_d]
    items += [(s[0] * d, s[0] * d) for s in sw]
    items.sort()
    zones = []
    for a, z in items:
        if zones and a <= zones[-1][1] + tol:
            zones[-1][1] = max(zones[-1][1], z)
        else:
            zones.append([a, z])
    starts = [zz[0] for zz in zones]

    def obstacles(lvl_d):
        lim = lvl_d - 2 * tick                     # a zone at the draw itself is part of the draw, not in its way
        return sum(1 for s0 in starts if e_d < s0 < lim)

    out = []
    seen = []
    for q in all_pools:
        if q["side"] != opp:
            continue
        lvl_d = q["price"] * d
        dist = lvl_d - e_d
        if dist <= 0:
            continue
        src, tier, kind, base = classify(q)
        seen.append(q["price"])
        out.append({"kind": kind, "source": src, "tier": tier, "price": float(q["price"]), "dist": float(dist),
                    "dist_atr": round(dist / atr, 3), "dist_r": round(dist / risk, 3), "obstacles": obstacles(lvl_d),
                    "age_h": round((t_now - int(q["t0"])) / 3600.0, 2), "eq": bool(q.get("eq")), "htf_dir": htf_dir,
                    "session": session, "sig": SIGNIFICANCE.get(base, 0.0) + (eq_w if q.get("eq") else 0.0),
                    "label": q.get("label") or q["kind"], "pool": q.get("_orig"), "is_gap": False})
    for s in sw:                                    # fresh 5m / 15m swings not already an engine pool: Tier C
        px = s[0]
        if any(abs(px - x) < tick / 2 + 1e-9 for x in seen):
            continue
        seen.append(px)
        dist = px * d - e_d
        tf = s[2] if len(s) > 2 else "5m"
        src = "M5SW" if tf == "5m" else "M15SW"
        out.append({"kind": "ERL", "source": src, "tier": "C", "price": float(px), "dist": float(dist),
                    "dist_atr": round(dist / atr, 3), "dist_r": round(dist / risk, 3), "obstacles": obstacles(px * d),
                    "age_h": round((t_now - int(s[3])) / 3600.0, 2) if len(s) > 3 else None, "eq": False,
                    "htf_dir": htf_dir, "session": session, "sig": 0.0, "label": f"{tf} swing", "pool": None,
                    "is_gap": False})
    for g in gaps:
        if irl_set is not None and g["tf"] not in irl_set:
            continue
        lvl = g["ce"] if irl_level == "ce" else (g["bot"] if d == 1 else g["top"])
        dist = lvl * d - e_d
        if dist <= 0:
            continue
        src = FVG_SOURCE.get(g["tf"], "FVG")
        out.append({"kind": "IRL", "source": src, "tier": "B" if g["tf"] in HTF_GAP_TFS else "C", "price": float(lvl),
                    "dist": float(dist), "dist_atr": round(dist / atr, 3), "dist_r": round(dist / risk, 3),
                    "obstacles": obstacles(lvl * d), "age_h": round((t_now - int(g["tc"])) / 3600.0, 2), "eq": False,
                    "htf_dir": htf_dir, "session": session, "sig": SIGNIFICANCE.get(src, 0.0),
                    "label": f"{g['tf']} FVG {g['bot']:.2f}-{g['top']:.2f}", "pool": None, "is_gap": True,
                    "gap": (g["bot"], g["top"])})
    out.sort(key=lambda x: x["dist"])
    return out


def features(x):
    """The learner-facing feature dict of one draw."""
    return {k: x.get(k) for k in FEATURE_KEYS}


def nearest_in_reach(ds, min_r, max_dist=None):
    """Nearest draw of any kind at least min_r away and within reach (None if none)."""
    for x in ds:                                    # nearest first
        if x["dist_r"] >= min_r and (max_dist is None or x["dist"] <= max_dist):
            return x
    return None


def pick_primary(ds, min_rr, max_dist=None, pick="tier", max_obst=99, rank="rule", predictor=None, min_ev=-99.0,
                 alt_min_rr=1.5):
    """Final target T (DOL-4).
      tier            nearest Tier-A draw >= min_rr within reach, else nearest Tier-B (playbook default)
      significance    most significant ERL draw >= min_rr within reach with obstacles <= max_obst (ties: nearest)
      farthest_reach  the FARTHEST significant (Tier A/B) ERL >= min_rr that is still within reach; none -> the
                      nearest within-reach draw of any kind >= alt_min_rr (DRAW_LEARNER.md variant a)
      rank learned    among Tier A/B draws >= min_rr within reach, max EV = p*R - (1-p), p = predictor(features)
    Returns (draw | None, why, ev | None)."""
    ok = [x for x in ds if x["dist_r"] >= min_rr and (max_dist is None or x["dist"] <= max_dist)]
    if rank == "learned" and predictor is not None:
        cand = [x for x in ok if x["tier"] in ("A", "B")]
        best, best_ev = None, None
        for x in cand:
            try:                                    # a broken / untrained learner never stops trading: rule fallback
                pr = predictor({**features(x), "within_reach": True})
                pr = None if pr is None else float(pr)
            except Exception:
                pr = None
            if pr is None or not (0.0 <= pr <= 1.0):
                continue
            ev = pr * x["dist_r"] - (1.0 - pr)
            x["p_hit"], x["ev"] = round(pr, 3), round(ev, 3)
            if best_ev is None or ev > best_ev:
                best, best_ev = x, ev
        if best is not None:
            if best_ev < min_ev:
                return None, f"best draw EV {best_ev:+.2f}R < {min_ev} (learned)", best_ev
            return best, "learned", best_ev
    if pick == "farthest_reach":
        erl = [x for x in ok if x["kind"] == "ERL" and x["tier"] in ("A", "B")]
        if erl:
            return max(erl, key=lambda x: x["dist"]), "farthest ERL within reach", None
        x = nearest_in_reach(ds, alt_min_rr, max_dist)
        if x is not None:
            return x, "nearest draw within reach", None
        return None, f"no ERL >= {min_rr}R and no draw >= {alt_min_rr}R within reach", None
    if pick == "significance":
        clean = [x for x in ok if x["kind"] == "ERL" and x["tier"] in ("A", "B") and x["obstacles"] <= max_obst]
        if not clean:
            return None, f"no clean external draw >= {min_rr}R within reach", None
        clean.sort(key=lambda x: (-x["sig"], x["dist"]))
        return clean[0], "significance", None
    for tier in ("A", "B"):
        t = [x for x in ok if x["tier"] == tier]
        if t:
            return t[0], f"tier {tier}", None          # ds is sorted nearest first
    return None, f"no Tier A/B draw >= {min_rr}R within reach", None


TP1_PRIORITY = {"htf_gap": 0, "eq": 1, "swing": 2, "gap5": 3}


def _tp1_rank(x):
    if x["is_gap"]:
        return TP1_PRIORITY["gap5"] if x["source"] == "FVG5" else TP1_PRIORITY["htf_gap"]
    return TP1_PRIORITY["eq"] if x["eq"] else TP1_PRIORITY["swing"]


def pick_partial(ds, primary_dist, min_r, risk, src="playbook"):
    """First internal draw TP1 (DOL-5): nearest candidate with distance in [min_r x R, dist(T)).
      playbook  live opposing gaps (any tf) + Tier B / C pools; when candidates lie within 0.25R of the nearest one,
                prefer an HTF (15m+) gap, then EQH/EQL, then a swing, then a 5m gap
      all       any draw (gaps + every pool), nearest
      fvg       gaps only"""
    risk = max(float(risk), 1e-9)
    c = [x for x in ds if x["dist_r"] >= min_r and x["dist"] < primary_dist - 1e-9]
    if src == "fvg":
        c = [x for x in c if x["is_gap"]]
    elif src == "playbook":
        c = [x for x in c if x["is_gap"] or x["tier"] in ("B", "C")]
    if not c:
        return None
    if src != "playbook":
        return c[0]
    lim = c[0]["dist"] + 0.25 * risk
    near = [x for x in c if x["dist"] <= lim]
    return sorted(near, key=lambda x: (_tp1_rank(x), x["dist"]))[0]


def compact(x):
    """Small JSON-safe summary of a draw for trade records / events."""
    if x is None:
        return None
    out = {k: x.get(k) for k in ("kind", "source", "tier", "price", "target", "dist_atr", "dist_r", "obstacles", "age_h",
                                 "eq", "htf_dir", "session", "label")}
    out["sig"] = round(float(x.get("sig") or 0.0), 2)
    for k in ("p_hit", "ev"):
        if k in x:
            out[k] = x[k]
    return out


# ----------------------------------------------------------------------------------------------- standalone API
_SESSION_WIN = {"ASIA": (1200, 1440, 0), "LON": (120, 300, 300), "ON": (1080, 570, 570)}   # (start, end, usable mod)


def _et_close_of_day(day_str):
    """Unix time of 17:00 ET on a CME session date (the daily bar's close)."""
    import datetime as _dt
    from zoneinfo import ZoneInfo
    d = _dt.date.fromisoformat(day_str)
    return int(_dt.datetime(d.year, d.month, d.day, 17, 0, tzinfo=ZoneInfo("America/New_York")).timestamp())


def _frame_bars(df):
    from .data import from_frame
    return from_frame("NQ", "5m", df[["time", "open", "high", "low", "close", "volume"]])


def _daily_series(b):
    """CME-day bars from 5m bars with the TRUE close time (17:00 ET), so a forming day is never treated as closed."""
    t0, tc, h, l, c = [], [], [], [], []
    keys = b.tday
    a = 0
    n = len(b)
    for k in range(1, n + 1):
        if k == n or keys[k] != keys[a]:
            t0.append(int(b.t[a])); tc.append(_et_close_of_day(b.date_str[a]))
            h.append(float(b.h[a:k].max())); l.append(float(b.l[a:k].min())); c.append(float(b.c[k - 1]))
            a = k
    return np.array(t0), np.array(tc), np.array(h), np.array(l), np.array(c)


def _standalone_pools(b, tick):
    """Prior day / week / prior RTH / today's session H-L and fresh 1H 3-bar swings, untaken by the last closed bar.
    Engine-format pool dicts (kind, side, price, t0, eq, kinds, label)."""
    n = len(b)
    last = n - 1
    td = b.tday
    ds0 = int(np.searchsorted(td, td[last]))                   # first bar of the current CME day
    out = []

    def add(kind, side, px, t0, from_i):
        if from_i <= last:
            seg_h, seg_l = b.h[from_i:last + 1], b.l[from_i:last + 1]
            if (side == "H" and seg_h.max() >= px + tick) or (side == "L" and seg_l.min() <= px - tick):
                return
        out.append({"kind": kind, "side": side, "price": float(px), "t0": int(t0), "eq": False, "kinds": [kind],
                    "label": kind})

    if ds0 > 0:
        p0 = int(np.searchsorted(td, td[ds0 - 1]))
        add("PDH", "H", b.h[p0:ds0].max(), b.t[ds0], ds0)
        add("PDL", "L", b.l[p0:ds0].min(), b.t[ds0], ds0)
        rth = [k for k in range(p0, ds0) if 570 <= int(b.mod[k]) < 960]
        if rth:
            k1 = rth[-1] + 1
            add("RTHH", "H", b.h[rth].max(), b.t[rth[-1]] + b.secs, k1)
            add("RTHL", "L", b.l[rth].min(), b.t[rth[-1]] + b.secs, k1)
    import datetime as _dt
    wk = [_dt.date.fromisoformat(s).isocalendar()[:2] for s in b.date_str]
    w0 = next((k for k in range(last, -1, -1) if wk[k] != wk[last]), None)
    if w0 is not None:
        ws = w0 + 1                                             # first bar of this week
        pw0 = next((k for k in range(w0, -1, -1) if wk[k] != wk[w0]), -1) + 1
        add("PWH", "H", b.h[pw0:ws].max(), b.t[ws], ws)
        add("PWL", "L", b.l[pw0:ws].min(), b.t[ws], ws)
    mods = b.mod[ds0:last + 1].astype(int)
    for name, (a_, z_, use) in _SESSION_WIN.items():
        if name == "ASIA":
            inwin = mods >= a_
        elif name == "ON":
            inwin = (mods >= a_) | (mods < z_)
        else:
            inwin = (mods >= a_) & (mods < z_)
        idx = np.nonzero(inwin)[0]
        if not len(idx):
            continue
        k_end = ds0 + int(idx[-1]) + 1                          # first bar after the window
        if k_end > last or not (int(b.mod[k_end]) >= use or (name == "ASIA" and int(b.mod[k_end]) < 1080)):
            continue                                            # the window has not closed yet
        kk = ds0 + idx
        tag = {"ASIA": "AS", "LON": "LO", "ON": "ON"}[name]
        add(tag + "H", "H", b.h[kk].max(), b.t[k_end], k_end)
        add(tag + "L", "L", b.l[kk].min(), b.t[k_end], k_end)
    return out, ds0


def draws_at(bars5_df, t_entry, d, entry, stop, es5_df=None, pick="farthest_reach", pm_nearest=True, min_rr=2.0,
             alt_min_rr=1.5, partial_min_r=1.0, mitigation="ce_touch", fvg_min="playbook", min_fvg=3.0, tick=0.25,
             lookback_days=35):
    """Liquidity map for ANY model at a decision time (see the API note at the top of this module).

    bars5_df  strategy_lab frame (time = bar open, unix s; open/high/low/close/volume; et/day/mod optional)
    t_entry   decision time, unix s: only bars CLOSED at or before it are used (bar time + 300 <= t_entry)
    d         +1 long / -1 short;  entry, stop: the planned entry and stop prices (R = |entry - stop|)
    es5_df    accepted for interface symmetry (SMT is not used by the map)
    Returns every draw beyond entry, nearest first. Each dict: kind, source, tier, price, dist, dist_r, dist_atr,
    obstacles, age_h, eq, htf_dir, session, within_reach, label, role ("final" | "partial" | None) and, for the two
    role draws, target (the exit price: 2 ticks before a pool, the near edge of a gap)."""
    from .data import resample
    from .model import Structure
    from .mtf import build_4h
    df = bars5_df
    df = df[(df["time"] + 300 <= int(t_entry)) & (df["time"] >= int(t_entry) - lookback_days * 86400)]
    if len(df) < 50:
        return []
    b = _frame_bars(df)
    n = len(b)
    atr_w = wilder_atr(b.h, b.l, b.c)
    m15 = resample(b, "15m")
    h1 = resample(b, "1h")
    s4 = build_4h(h1)
    d0, d1c, dh, dl, dc = _daily_series(b)
    book = LiquidityBook(tick, min_fvg, mitigation, fvg_min)
    book.add_gap_series("5m", b.t, b.t + 300, b.h, b.l, b.c, atr=atr_w, tday=b.tday)
    book.add_gap_series("15m", m15.t, m15.t + 900, m15.h, m15.l, m15.c)
    book.add_gap_series("1h", h1.t, h1.t + 3600, h1.h, h1.l, h1.c, start_t=int(t_entry) - 12 * 86400)
    ref = (h1.t, h1.t + 3600, h1.h, h1.l)
    book.add_gap_series("4h", s4.t, s4.tc, s4.h, s4.l, s4.c)
    book.add_swing_series("4h", s4.t, s4.tc, s4.h, s4.l, ref=ref)
    book.add_gap_series("1d", d0, d1c, dh, dl, dc)
    book.add_swing_series("1d", d0, d1c, dh, dl, ref=ref)
    book.set_base(b)
    for i in range(n):
        book.advance(int(b.t[i]) + 300, i)
    pools, ds0 = _standalone_pools(b, tick)
    last = n - 1
    t_now = int(b.t[last]) + 300
    # fresh 1H 3-bar swings (closed 1H bars of the last 10 days, untaken by any later 5m bar) = Tier B pools
    h1_closed = int(np.searchsorted(h1.t + 3600, t_now, side="right")) - 1
    if h1_closed >= 3:
        hs, ls = live_swings(h1.h, h1.l, 1, h1_closed, 240, tick)
        k5 = int(np.searchsorted(b.t, int(h1.t[h1_closed]) + 3600))
        hi_s = float(b.h[k5:].max()) if k5 < n else -1e18
        lo_s = float(b.l[k5:].min()) if k5 < n else 1e18
        pools += [{"kind": "H1H", "side": "H", "price": px, "t0": int(h1.t[j]) + 7200, "eq": False, "kinds": ["H1H"],
                   "label": "1H swing high"} for px, j in hs if hi_s < px + tick]
        pools += [{"kind": "H1L", "side": "L", "price": px, "t0": int(h1.t[j]) + 7200, "eq": False, "kinds": ["H1L"],
                   "label": "1H swing low"} for px, j in ls if lo_s > px - tick]
    sw = {"H": [], "L": []}
    hs, ls = live_swings(b.h, b.l, 2, last, (last - ds0) + 276, tick)
    sw["H"] += [(px, j, "5m", int(b.t[j])) for px, j in hs]
    sw["L"] += [(px, j, "5m", int(b.t[j])) for px, j in ls]
    m_closed = int(np.searchsorted(m15.t + 900, t_now, side="right")) - 1
    if m_closed >= 3:
        hs, ls = live_swings(m15.h, m15.l, 1, m_closed, 5 * 92, tick)
        k5 = int(np.searchsorted(b.t, int(m15.t[m_closed]) + 900))
        hi_s = float(b.h[k5:].max()) if k5 < n else -1e18
        lo_s = float(b.l[k5:].min()) if k5 < n else 1e18
        sw["H"] += [(px, j, "15m", int(m15.t[j])) for px, j in hs if hi_s < px + tick]
        sw["L"] += [(px, j, "15m", int(m15.t[j])) for px, j in ls if lo_s > px - tick]
    st = Structure(2)
    for k in range(h1_closed + 1):
        st.add(h1.t[k], h1.h[k], h1.l[k], h1.c[k])
    risk = abs(float(entry) - float(stop))
    mod = int(b.mod[last])
    ds = draws(d, float(entry), risk, float(atr_w[last]), t_now, pools, book, swings=sw, h1_trend=st.trend, mod=mod,
               tick=tick, day_start_t=int(b.t[ds0]))
    # reach (DOL-4): max(0.5 x ADR10, ADR10 - today's range so far)
    days = sorted(set(int(x) for x in b.tday[:ds0]))[-10:]
    reach = None
    if days:
        rngs = [float(b.h[b.tday == x].max() - b.l[b.tday == x].min()) for x in days]
        adr10 = float(np.mean(rngs))
        reach = max(0.5 * adr10, adr10 - float(b.h[ds0:].max() - b.l[ds0:].min()))
    for x in ds:
        x["within_reach"] = bool(reach is None or x["dist"] <= reach)
        x["role"] = None
        x.pop("pool", None)
    if mod >= 720 and pm_nearest:
        fin = nearest_in_reach(ds, alt_min_rr, reach)
    else:
        fin, _, _ = pick_primary(ds, min_rr, reach, pick, alt_min_rr=alt_min_rr)
    if fin is not None:
        fin["role"] = "final"
        fin["target"] = float(fin["price"] - d * 2 * tick)
        tp1 = pick_partial(ds, fin["dist"], partial_min_r, risk, "playbook")
        if tp1 is not None and tp1 is not fin:
            tp1["role"] = "partial"
            tp1["target"] = float(tp1["price"] if tp1["is_gap"] else tp1["price"] - d * 2 * tick)
    return ds


# ----------------------------------------------------------------------------------------------- person management
MANAGE_DEFAULTS = {"partial_pct": 0.5, "be_r": 1.0, "be_ticks": 2, "trail": False, "trail_buf_atr": 0.1,
                   "giveback_r": 0.5, "cisd_exit": False, "stall_bars": 6, "noon_exit": False, "flat_mod": 955,
                   "touch_ticks": 1, "slip_ticks": 1, "tick": 0.25}


def new_position(d, entry, stop, qty, entry_i, target, tp1=None):
    """A position for manage_step(). entry_i = index (in the caller's bar arrays) of the FILL bar."""
    return {"dir": int(d), "entry": float(entry), "stop": float(stop), "stop0": float(stop), "qty": int(qty),
            "remaining": int(qty), "entry_i": int(entry_i), "target": float(target),
            "tp1": None if tp1 is None else float(tp1), "tp1_done": False, "be_done": False, "mfe": 0.0,
            "risk": abs(float(entry) - float(stop)), "fills": [], "closed": False, "pswing": None}


def manage_step(position, bar, context):
    """One CLOSED bar of person-style management (DOL_PLAYBOOK MGMT-1..8; the engine's manage_mode "person").

    position  dict from new_position(); mutated in place
    bar       index i of the bar that just closed, in context["o"/"h"/"l"/"c"/"mod"] (numpy arrays of closed bars)
    context   {"o","h","l","c","mod": arrays, "atr": Wilder ATR14 at bar i (or an array), "params": MANAGE_DEFAULTS
              overrides}
    Order: intrabar stop (wins ties) -> TP1 (ceil(n x partial_pct), a runner is always kept) -> T; then at the close:
    opposing CISD + displacement (if enabled) -> giveback -> stall (no +0.5R after stall_bars) -> 12:00 unprotected
    -> flat_mod; then breakeven (entry + be_ticks at TP1 or +be_r R) -> structure trail on each 5m BOS (if enabled).
    Returns {"fills": [{"qty", "price", "reason"}], "closed": bool, "stop": stop for the next bar}."""
    p = {**MANAGE_DEFAULTS, **(context.get("params") or {})}
    pos, i = position, int(bar)
    if pos["closed"]:
        return {"fills": [], "closed": True, "stop": pos["stop"]}
    O, H, L, C, M = (context[k] for k in ("o", "h", "l", "c", "mod"))
    d, tick = pos["dir"], p["tick"]
    slip, touch = p["slip_ticks"] * tick, p["touch_ticks"] * tick
    atr = context.get("atr")
    atr = float(atr[i]) if hasattr(atr, "__len__") else float(atr or pos["risk"])
    o, h, l, c = float(O[i]), float(H[i]), float(L[i]), float(C[i])
    lo_d, hi_d = (l, h) if d == 1 else (-h, -l)
    e_d, risk = pos["entry"] * d, pos["risk"]
    fills = []

    def fill(q, px, why):
        fills.append({"qty": int(q), "price": float(px), "reason": why})
        pos["fills"].append(fills[-1])
        pos["remaining"] -= int(q)

    pos["mfe"] = max(pos["mfe"], (hi_d - e_d) / risk)
    if lo_d <= pos["stop"] * d:
        fill(pos["remaining"], (min(o * d, pos["stop"] * d) - slip) * d, "STOP" if not pos["be_done"] else "BE/TRAIL")
    else:
        if pos["tp1"] is not None and not pos["tp1_done"] and hi_d >= pos["tp1"] * d + touch:
            pos["tp1_done"] = True
            q = min(pos["qty"] - 1, int(math.ceil(pos["qty"] * p["partial_pct"] - 1e-9)))
            if 1 <= q < pos["remaining"]:
                fill(q, pos["tp1"], "TP1")
                pos["stop"] = max(pos["stop"] * d, e_d + p["be_ticks"] * tick) * d
                pos["be_done"] = True
        if hi_d >= pos["target"] * d + touch:
            fill(pos["remaining"], pos["target"], "TARGET")
    if pos["remaining"] > 0:
        why = None
        if p["cisd_exit"] and _cisd_arrays(O, H, L, C, i, pos["entry_i"], d, atr):
            why = "CISD"
        elif pos["mfe"] >= p["giveback_r"] and c * d < e_d:
            why = "GIVEBACK"
        elif p["stall_bars"] and i - pos["entry_i"] + 1 >= p["stall_bars"] and pos["mfe"] < 0.5:
            why = "STALL"
        elif p["noon_exit"] and int(M[i]) + 5 == 720 and int(M[pos["entry_i"]]) < 720 and pos["stop"] * d < e_d:
            why = "NOON"
        elif int(M[i]) >= p["flat_mod"]:
            why = "FLAT"
        if why:
            fill(pos["remaining"], c - d * slip, why)
        else:
            new_d = pos["stop"] * d
            if p["be_r"] and pos["mfe"] >= p["be_r"]:
                new_d = max(new_d, e_d + p["be_ticks"] * tick)
            if p["trail"] and new_d >= e_d:
                prot = _protected_arrays(pos, H, L, C, i, d)
                if prot is not None:
                    new_d = max(new_d, prot - max(2 * tick, p["trail_buf_atr"] * atr))
            if new_d > pos["stop"] * d:
                pos["stop"] = new_d * d
                pos["be_done"] = pos["be_done"] or new_d >= e_d
    pos["closed"] = pos["remaining"] <= 0
    return {"fills": fills, "closed": pos["closed"], "stop": pos["stop"]}


def _protected_arrays(pos, H, L, C, i, d):
    hd = (lambda j: float(H[j])) if d == 1 else (lambda j: -float(L[j]))
    ld = (lambda j: float(L[j])) if d == 1 else (lambda j: -float(H[j]))
    st = pos.get("pswing")
    if st is None:
        st = pos["pswing"] = {"sh": None, "sh_k": None, "prot": None}
        e_i = pos["entry_i"]
        for k in range(e_i - 3, max(1, e_i - 60), -1):
            hk = hd(k)
            if hk > hd(k - 1) and hk > hd(k - 2) and hk >= hd(k + 1) and hk >= hd(k + 2):
                if max(float(C[j]) * d for j in range(k + 1, e_i)) <= hk:
                    st["sh"], st["sh_k"] = hk, k
                break
    k = i - 2
    if k >= 2 and k >= pos["entry_i"] - 2:
        hk = hd(k)
        if hk > hd(k - 1) and hk > hd(k - 2) and hk >= hd(k + 1) and hk >= hd(k + 2):
            st["sh"], st["sh_k"] = hk, k
    if st["sh"] is not None and float(C[i]) * d > st["sh"]:
        lo = min(ld(j) for j in range(st["sh_k"], i + 1))
        st["prot"] = lo if st["prot"] is None else max(st["prot"], lo)
        st["sh"], st["sh_k"] = None, None
    return st["prot"]


def _cisd_arrays(O, H, L, C, i, e_i, d, atr):
    rng = float(H[i] - L[i])
    body = float(O[i] - C[i]) * d
    if i - e_i < 1 or rng <= 0 or body <= 0 or body < 0.5 * rng:
        return False
    up = lambda j: (C[j] - O[j]) * d > 0
    j = i - 1
    while j >= e_i and not up(j):
        j -= 1
    if j < e_i:
        return False
    f = j
    while f - 1 >= e_i and up(f - 1):
        f -= 1
    if f == e_i and e_i >= 1 and up(e_i - 1):
        return False
    if not (C[i] * d < O[f] * d):
        return False
    gap = i >= 2 and ((H[i] < L[i - 2]) if d == 1 else (L[i] > H[i - 2]))
    return bool((body >= atr and body >= 0.6 * rng) or gap)
