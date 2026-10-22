"""Retail-tool entries for LIT (owner 2026-10-21: "EMAs / supply and demand / support and resistance / MACD ... implementing
into LIT. We still should definitely find 3 entries a week"). Research: research/writeups/lit-retail-entries.md,
tools/lit_retail.py. Off by default: engine/lit.py DEFAULTS "retail" = None (today's LIT, unchanged).

Every setup here ends in the same LIT trade: a 5m CISD (first close through the open of the last run of opposite-close bars
into the extreme) -> engine/lit.run_x executor (30-min limit at the CISD level, 1m CISD within 20 bars, stop 1 tick beyond
the structural extreme, VIX-band target >= 1.5R banked at 8R, BE at 1R, flat 15:55, 1 trade a day). Only the WHY of the
setup changes. Pure functions of closed bars (no look-ahead):
  * 15m / 1h candles are built from the 5m bars; a candle is known only once its last 5m bar has closed;
  * fractal swings (k=2) count only 2 candles after the swing candle; zones only after the leg-out candle closed;
  * EMAs / MACD at a 5m bar use that bar's close (5m) or the last closed 15m / 1h candle.

Families (cfg["kind"]):
  "levels"   extra LIT sweep levels: swing-cluster S/R (2+ touches on 15m / 1h), round numbers (00 / 50 handles), fresh 15m / 1h
             supply-demand zone edges; the unchanged LIT detector (lit.candidates + setup_ok filters) runs on them
  "sd"       supply/demand zone retest: price returns into a fresh 15m / 1h zone, 5m CISD in the zone's direction
  "brt"      S/R break-and-retest: a 5m close through S/R, a pull back to it that holds, 5m CISD with the break
  "ema"      EMA pullback in trend: 1h and 15m EMA 21 > EMA 50 (mirror for shorts), pullback to the 5m EMA 21 / 50 (or the 15m
             EMA 21), 5m CISD back with the trend
  "macd"     MACD divergence as the substitute confirmation on LIT sweeps the live filters reject (too shallow, too small a
             displacement, no inducement): regular divergence of MACD(12, 26) on 5m or 15m at the sweep extreme
"""
from __future__ import annotations

import bisect
import collections

import numpy as np

from engine import lit

TICK = lit.TICK


# ------------------------------------------------------------------------------------------------ bar helpers
def ema(x, n):
    a = 2.0 / (n + 1.0)
    out = np.empty(len(x))
    if not len(x):
        return out
    out[0] = x[0]
    for i in range(1, len(x)):
        out[i] = out[i - 1] + a * (x[i] - out[i - 1])
    return out


def n_closed(M):
    return int(getattr(M, "n_closed", M.n) or M.n)


class HTF:
    """15m / 1h candles from the Market's 5m bars. known[j] = 5m index whose close completes candle j (its last 5m bar when
    the candle is full, else the first 5m bar of the next candle); first[j] = its first 5m index. Only 5m bars < n_closed."""

    def __init__(self, M, secs):
        n = n_closed(M)
        t = M.t[:n]
        g = t // secs
        st = np.r_[0, np.flatnonzero(np.diff(g)) + 1] if n else np.array([], int)
        en = np.r_[st[1:], n] if n else np.array([], int)
        self.first = st
        self.last = en - 1
        self.o = M.o[st]
        self.h = np.maximum.reduceat(M.h[:n], st) if n else np.array([])
        self.l = np.minimum.reduceat(M.l[:n], st) if n else np.array([])
        self.c = M.c[en - 1] if n else np.array([])
        full = (t[en - 1] + 300) % secs == 0 if n else np.array([], bool)
        known = np.where(full, en - 1, np.r_[en[:-1], 10 ** 12] if n else en)
        # the last candle of the data is known only if it is full
        self.known = known.astype(np.int64)
        self.n = len(st)
        self.secs = secs
        self.atr = lit.atr(self.h, self.l, self.c) if self.n else np.array([])
        self._known_sorted = self.known  # non-decreasing

    def last_known(self, i):
        """Index of the last candle known by the close of 5m bar i (-1 if none)."""
        return int(np.searchsorted(self.known, i, side="right")) - 1


def fractals(h, l, k=2):
    return lit.fractals(h, l, k)


# ------------------------------------------------------------------------------------------------ levels
def sr_levels(M, H: HTF, tol_atr=0.25, lookback=120, min_touch=2):
    """Swing-cluster S/R on candles H: a fractal high (low) whose price is within tol_atr x ATR(H) of min_touch - 1 earlier
    fractal highs (lows) in the last `lookback` candles -> level = the cluster's extreme (resistance: the highest high; support:
    the lowest low), known at the 5m close that confirms the newest swing (candle j + 2 known). Returns level dicts
    {"side", "px", "ki", "kind": "sr", "touches"}."""
    fh, fl = fractals(H.h, H.l)
    out = []
    for side, idx, arr in (("high", fh, H.h), ("low", fl, H.l)):
        rec = collections.deque()
        for j in idx:
            j = int(j)
            while rec and j - rec[0] > lookback:
                rec.popleft()
            if j + 2 >= H.n:
                break
            tol = tol_atr * max(H.atr[j], 1e-9)
            near = [m for m in rec if abs(arr[m] - arr[j]) <= tol]
            if len(near) + 1 >= min_touch:
                grp = near + [j]
                px = float(max(arr[m] for m in grp)) if side == "high" else float(min(arr[m] for m in grp))
                ki = int(H.known[j + 2])
                if ki < 10 ** 12:
                    out.append({"side": side, "px": px, "ki": ki, "kind": "sr", "touches": len(grp), "tf": H.secs // 60})
            rec.append(j)
    out.sort(key=lambda x: x["ki"])
    return out


def sd_zones(M, H: HTF, body_k=1.5, base_max=3, base_body=0.5, max_h_atr=1.5):
    """Fresh supply / demand zones on candles H (drop-base-rally / rally-base-drop style). Leg-out candle j: body >= body_k x
    ATR(H) and close beyond the base; base = the 1..base_max candles right before j, each with body <= base_body x its range
    (indecision). Demand (bullish leg-out): distal = lowest base low, proximal = highest base body top. Supply mirror.
    Known at the close of candle j. Zone height <= max_h_atr x ATR. Returns {"dir": +1 demand / -1 supply, "prox", "dist",
    "ki"} in price (not direction) space."""
    out = []
    o, h, l, c, at = H.o, H.h, H.l, H.c, H.atr
    for j in range(base_max + 1, H.n):
        if H.known[j] >= 10 ** 12:
            continue
        b = c[j] - o[j]
        if abs(b) < body_k * at[j - 1]:
            continue
        d = 1 if b > 0 else -1
        nb = 0
        for q in range(j - 1, j - 1 - base_max, -1):
            rng = h[q] - l[q]
            if rng <= 0 or abs(c[q] - o[q]) > base_body * rng:
                break
            nb += 1
        if nb == 0:
            continue
        bs = slice(j - nb, j)
        if d == 1:
            dist = float(l[bs].min()); prox = float(np.maximum(o[bs], c[bs]).max())
            if c[j] <= h[bs].max():
                continue
        else:
            dist = float(h[bs].max()); prox = float(np.minimum(o[bs], c[bs]).min())
            if c[j] >= l[bs].min():
                continue
        if abs(prox - dist) > max_h_atr * at[j - 1] or abs(prox - dist) < TICK:
            continue
        out.append({"dir": d, "prox": prox, "dist": dist, "ki": int(H.known[j]), "tf": H.secs // 60})
    out.sort(key=lambda x: x["ki"])
    return out


def first_touch_after(M, side, px, ki, n):
    """First 5m index > ki where a wick reaches px from the given side ("low": low <= px, "high": high >= px); n if never."""
    arr = M.l[:n] if side == "low" else M.h[:n]
    seg = arr[ki + 1:n]
    m = seg <= px if side == "low" else seg >= px
    return ki + 1 + int(np.argmax(m)) if m.any() else n


def round_levels(M, k, step=100.0, span_k=2.0):
    """Round-number levels (multiples of `step`) within span_k VIX one-day moves of the 18:00 open, known at the start of the
    day: above the open = "high" (buy stops), below = "low"."""
    x = M.ctx[k]
    vm = x.get("vix_move") or 0.0
    op = x["open18"]
    rg = max(span_k * vm, 2 * step)
    lo, hi = np.ceil((op - rg) / step) * step, np.floor((op + rg) / step) * step
    out = []
    for px in np.arange(lo, hi + step / 2, step):
        if abs(px - op) < TICK:
            continue
        out.append(("high" if px > op else "low", float(px), x["s"] - 1, "rn%d" % int(step), "round"))
    return out


class LevelsMarket(lit.Market):
    """A copy of a built Market whose levels(k) are only the retail levels (S/R clusters, round numbers, zone edges), so the
    unchanged LIT detector (lit.candidates) finds LIT setups on them. No super().__init__ (shares the base arrays)."""

    def __init__(self, base, cfg):        # noqa: D401
        self.__dict__.update(base.__dict__)
        self._cfg = cfg
        n = n_closed(base)
        L = []
        for tf in cfg.get("sr_tf", ()):
            H = HTF(base, {"15m": 900, "1h": 3600}[tf])
            for lv in sr_levels(base, H, tol_atr=cfg.get("sr_tol", 0.25), lookback=cfg.get("sr_look", 120 if tf == "15m" else 60),
                                min_touch=cfg.get("sr_n", 2)):
                L.append((lv["side"], lv["px"], lv["ki"], "sr%s_%s" % (tf, lv["side"][0]), "sr"))
        for tf in cfg.get("sd_tf", ()):
            H = HTF(base, {"15m": 900, "1h": 3600}[tf])
            for z in sd_zones(base, H, body_k=cfg.get("sd_body", 1.5)):
                side = "low" if z["dir"] == 1 else "high"
                for nm, px in (("p", z["prox"]), ("d", z["dist"])):
                    if nm in cfg.get("sd_edges", "pd"):
                        L.append((side, px, z["ki"], "sd%s_%s" % (tf, nm), "sd"))
        # a level is liquidity until its first touch after it is known (then the sweep is that touch)
        self._L = sorted(L, key=lambda x: x[2])
        self._ki = [x[2] for x in self._L]
        self._touch = [first_touch_after(base, x[0], x[1], x[2], n) for x in self._L]
        self._age = int(cfg.get("max_age", 1440))
        self._rn = cfg.get("rn") or ()

    def levels(self, k):
        x = self.ctx[k]
        s, e = x["s"], x["e"]
        L = []
        a = bisect.bisect_left(self._ki, s - self._age)
        b = bisect.bisect_left(self._ki, e)
        w0 = s - 600
        for q in range(a, b):
            if self._touch[q] <= max(self._ki[q], w0):
                continue
            L.append(self._L[q])
        for step in self._rn:
            L.extend(round_levels(self, k, float(step)))
        return L


# ------------------------------------------------------------------------------------------------ CISD triggers + candidate
def _dirs(M, d):
    return (M.h, M.l, M.c, M.o) if d == 1 else (-M.l, -M.h, -M.c, -M.o)


def triggers(M, leg=24, t_from=60, t_to=955):
    """Every 5m CISD trigger, both directions: bar i closes above the CISD level of the leg extreme ee (lowest low of the last
    `leg` bars, direction space) for the first time. Yields (k, d, i, ee, rp, j_ref). Bars < n_closed only."""
    n = n_closed(M)
    mod = M.mod
    for k, (date, s, e) in enumerate(M.days):
        x = M.ctx[k]
        if "pdh" not in x or e - s < 50:
            continue
        e2 = min(e, n + 1)               # the trigger bar is closed (i < n); its entry bar may be the forming one
        for d in (1, -1):
            hi_d, lo_d, c_d, o_d = _dirs(M, d)
            last_e = -1
            for i in range(s + leg, e2 - 1):
                if not (t_from <= mod[i] < t_to) or mod[i] >= 1080:
                    continue
                a = i - leg
                ee = a + int(np.argmin(lo_d[a:i + 1]))
                if ee == i or ee == last_e:
                    continue
                cz = lit._cisd_level(c_d, o_d, ee)
                if cz is None:
                    continue
                rp, j = cz
                if not (c_d[i] > rp and c_d[ee:i].max() <= rp):
                    continue
                last_e = ee
                yield k, d, i, ee, rp, j


def make_cand(M, k, d, i, ee, rp, j, src, name, ext=None, extra=None):
    """A candidate in engine/lit.candidates' shape (pre_ok: the family's own rule replaces setup_ok; the window is checked
    by the builder). ext = direction-space stop extreme (default: the leg low)."""
    hi_d, lo_d, c_d, o_d = _dirs(M, d)
    date, s, e = M.days[k]
    x = M.ctx[k]
    ei = i + 1
    if ei >= e or lit._late(M.mod[ei], 955, False):
        return None
    at = M.atr
    ext = float(lo_d[ee]) if ext is None else float(ext)
    body = (c_d[ee:i + 1] - o_d[ee:i + 1]) / np.maximum(at[ee:i + 1], 1e-9)
    gside = {}
    for gk in ("nwog", "ndog"):
        gv = x.get(gk)
        gside[gk] = (1 if ((float(o_d[ei]) + lit.SLIP) * d - 0.5 * (gv[0] + gv[1])) * d > 0 else -1) if gv else 0
    ws = int(np.searchsorted(M.week_id[:ee + 1], M.week_id[ee]))
    z = {"day": str(date), "k": k, "dir": d, "i": int(i), "ext_i": int(ee), "ref_i": int(j), "entry_i": ei, "sweep_i": int(ee),
         "entry_t": int(M.t[ei]), "entry_d": float(o_d[ei]) + lit.SLIP, "ext_d": ext, "ref_d": float(rp), "trig_c": float(c_d[i]),
         "mod": int(M.mod[ei]), "swept": [name], "swept_cls": [src], "depth_atr": 0.0, "ind_n": 0,
         "disp": round(float(body[1:].max()) if len(body) > 1 else 0.0, 3), "vec": False, "vec_any": False, "vec_sweep": False,
         "bars": int(i - ee), "atr": round(float(at[i]), 2), "targets": {}, "po3": {}, "vix_ext": None, "vxn_ext": None,
         "vix_room": None, "how": bool(M.how[ee]), "wk_ext": bool(lo_d[ee] <= lo_d[ws:ee + 1].min()), "dow": x["dow"],
         "sw": {name: ext}, "atr_ext": float(at[ee]), "idm_a": [], "nwog_side": gside["nwog"], "ndog_side": gside["ndog"],
         "mw_break": None, "pre_ok": True, "src": src}
    if extra:
        z.update(extra)
    return z


def _in_window(z, P):
    return any(a <= z["mod"] < b for a, b in P["window"])


# ------------------------------------------------------------------------------------------------ families
def fam_sd(M, cfg, P, trig):
    """Zone retest: the leg's extreme ran into a fresh zone (its first touch since it formed is inside this leg), the extreme
    held (not more than cfg sd_through x ATR beyond the distal edge), 5m CISD in the zone's direction. stop "zone" = beyond
    the farther of the extreme and the distal edge; "ext" = beyond the retest extreme."""
    n = n_closed(M)
    out = []
    Z = []
    for tf in cfg.get("sd_tf", ("15m",)):
        H = HTF(M, {"15m": 900, "1h": 3600}[tf])
        for z in sd_zones(M, H, body_k=cfg.get("sd_body", 1.5)):
            side = "low" if z["dir"] == 1 else "high"
            z["touch"] = first_touch_after(M, side, z["prox"], z["ki"], n)
            Z.append(z)
    byd = {1: sorted([z for z in Z if z["dir"] == 1], key=lambda z: z["touch"]),
           -1: sorted([z for z in Z if z["dir"] == -1], key=lambda z: z["touch"])}
    tch = {d: [z["touch"] for z in byd[d]] for d in (1, -1)}
    thr = cfg.get("sd_through", 0.5)
    leg = cfg.get("leg", 24)
    for k, d, i, ee, rp, j in trig:
        _, lo_d, _, _ = _dirs(M, d)
        a = bisect.bisect_left(tch[d], ee - leg)
        b = bisect.bisect_right(tch[d], ee)
        best = None
        for z in byd[d][a:b]:
            if z["ki"] >= z["touch"] or i - z["ki"] > cfg.get("sd_age", 576):
                continue
            prox, dist = z["prox"] * d, z["dist"] * d
            if lo_d[ee] > prox or lo_d[ee] < dist - thr * M.atr[ee]:
                continue
            if best is None or prox > best[0]:
                best = (prox, dist, z)
        if best is None:
            continue
        ext = min(float(lo_d[ee]), best[1]) if cfg.get("stop", "zone") == "zone" else float(lo_d[ee])
        c = make_cand(M, k, d, i, ee, rp, j, "sd", "sd%d" % best[2]["tf"], ext=ext)
        if c and _in_window(c, P) and c["disp"] >= cfg.get("disp", 0.0):
            out.append(c)
    return out


def fam_brt(M, cfg, P, trig):
    """Break and retest: an S/R level (15m / 1h swing cluster, or a 100-pt round number, or PDH/PDL) broken by a 5m close
    (first close beyond it after it is known) within cfg brt_win bars before the extreme; the pull back to the level reaches
    within brt_tol x ATR of it and does not trade more than brt_hold x ATR back through it; 5m CISD with the break."""
    n = n_closed(M)
    lv = []
    for tf in cfg.get("sr_tf", ("15m", "1h")):
        H = HTF(M, {"15m": 900, "1h": 3600}[tf])
        for x in sr_levels(M, H, tol_atr=cfg.get("sr_tol", 0.25), lookback=120 if tf == "15m" else 60):
            lv.append((x["px"], x["ki"], "sr" + tf))
    if cfg.get("brt_pd"):
        for k, x in enumerate(M.ctx):
            if "pdh" in x:
                lv.append((x["pdh"], x["s"] - 1, "pdh")); lv.append((x["pdl"], x["s"] - 1, "pdl"))
    # first 5m close above / below each level after it is known
    c = M.c[:n]
    brk = []
    for px, ki, nm in lv:
        for d in (1, -1):
            seg = (c[ki + 1:] * d) > px * d
            if not seg.any():
                continue
            b = ki + 1 + int(np.argmax(seg))
            if b - ki > cfg.get("brt_age", 1440):
                continue
            brk.append((b, d, px, nm))
    brk.sort()
    bt = [x[0] for x in brk]
    win, tol, hold = cfg.get("brt_win", 36), cfg.get("brt_tol", 0.25), cfg.get("brt_hold", 0.5)
    out = []
    for k, d, i, ee, rp, j in trig:
        _, lo_d, c_d, _ = _dirs(M, d)
        a = bisect.bisect_left(bt, ee - win)
        b = bisect.bisect_left(bt, ee)
        best = None
        for q in range(a, b):
            bb, dd, px, nm = brk[q]
            if dd != d:
                continue
            p = px * d
            at = M.atr[ee]
            if not (p - hold * at <= lo_d[ee] <= p + tol * at):
                continue
            if c_d[bb:i + 1].min() < p - hold * at:
                continue
            if best is None or bb > best[0]:
                best = (bb, p, nm)
        if best is None:
            continue
        z = make_cand(M, k, d, i, ee, rp, j, "brt", "brt_" + best[2])
        if z and _in_window(z, P) and z["disp"] >= cfg.get("disp", 0.0):
            out.append(z)
    return out


def fam_ema(M, cfg, P, trig):
    """EMA pullback in trend: at the trigger bar the last closed 1h and 15m candles have EMA fast > EMA slow (21 / 50; mirror
    for shorts); the leg extreme touched the pullback EMA (5m EMA 21 / 50 or the 15m EMA 21 at the extreme) and stayed on the
    trend side of the 1h EMA slow; 5m CISD back with the trend."""
    n = n_closed(M)
    f, sl = cfg.get("ema_fast", 21), cfg.get("ema_slow", 50)
    H15, H1 = HTF(M, 900), HTF(M, 3600)
    e15f, e15s = ema(H15.c, f), ema(H15.c, sl)
    e1f, e1s = ema(H1.c, f), ema(H1.c, sl)
    c5 = M.c[:n]
    pb = cfg.get("ema_pb", "5m21")
    e5 = ema(c5, int(pb[2:])) if pb.startswith("5m") else None
    out = []
    for k, d, i, ee, rp, j in trig:
        _, lo_d, _, _ = _dirs(M, d)
        q15, q1 = H15.last_known(i), H1.last_known(i)
        if q15 < sl or q1 < sl:
            continue
        if not ((e15f[q15] - e15s[q15]) * d > 0 and (e1f[q1] - e1s[q1]) * d > 0):
            continue
        if cfg.get("ema_h4"):            # also price above the 1h fast EMA at the trigger (strong trend)
            if (M.c[i] - e1f[q1]) * d <= 0:
                continue
        if pb.startswith("5m"):
            ev = e5[ee] * d
        else:
            qe = H15.last_known(ee)
            if qe < 0:
                continue
            ev = e15f[qe] * d
        if lo_d[ee] > ev + cfg.get("ema_tol", 0.0) * M.atr[ee]:
            continue
        if lo_d[ee] < e1s[q1] * d:
            continue
        z = make_cand(M, k, d, i, ee, rp, j, "ema", "ema_" + pb)
        if z and _in_window(z, P) and z["disp"] >= cfg.get("disp", 0.0):
            out.append(z)
    return out


def macd_div(M, z, tf="5m", look=48, min_gap=6, H=None, mac=None):
    """Regular MACD(12, 26) divergence at the candidate's sweep extreme (direction space): the extreme is a lower low than the
    lowest confirmed fractal low of the `look` bars before it (at least min_gap bars earlier) while the MACD line is higher.
    15m: the same on 15m candles closed by the trigger bar (the extreme's candle must be closed)."""
    d = z["dir"]
    if tf == "5m":
        m = mac * d
        _, lo_d, _, _ = _dirs(M, d)
        ee = z["ext_i"]
        fl = M.fl if d == 1 else M.fh
        a = bisect.bisect_left(fl, ee - look)
        b = bisect.bisect_right(fl, ee - min_gap)
        cand = [int(q) for q in fl[a:b] if q + 2 <= ee]
        if not cand:
            return False
        q = min(cand, key=lambda q: lo_d[q])
        return bool(lo_d[ee] < lo_d[q] and m[ee] > m[q])
    lo = H.l * d if d == 1 else -H.h
    m = mac * d
    qi = H.last_known(z["i"])
    qe = int(np.searchsorted(H.first, z["ext_i"], side="right")) - 1
    if qe < 0 or qe > qi:
        return False
    fh, fl = fractals(H.h, H.l)
    fl = fl if d == 1 else fh
    a = bisect.bisect_left(fl, qe - look // 3)
    b = bisect.bisect_right(fl, qe - 2)
    cand = [int(q) for q in fl[a:b] if q + 2 <= qi]
    if not cand:
        return False
    q = min(cand, key=lambda q: lo[q])
    return bool(lo[qe] < lo[q] and m[qe] > m[q])


def fam_macd(M, cfg, P, C):
    """LIT candidates the live filters reject that show a regular MACD divergence: cfg macd_sub = which failed filters the
    divergence may replace ("idm", "depth", "disp" or "any"); the kept filters stay at the live values; floors depth_min /
    disp_min."""
    tf = cfg.get("macd_tf", "5m")
    if tf == "5m":
        H, mac = None, ema(M.c, 12) - ema(M.c, 26)
    else:
        H = HTF(M, 900)
        mac = ema(H.c, 12) - ema(H.c, 26)
    sub = set(cfg.get("macd_sub", ["any"]))
    out = []
    for z in C:
        if not any(a <= z["mod"] < b for a, b in P["window"]):
            continue
        if lit.setup_ok(z, P):
            continue                       # a LIT setup already
        fails = set()
        if z["depth_atr"] < P["depth"]:
            fails.add("depth")
        if z["disp"] < P["disp"]:
            fails.add("disp")
        if P.get("idm_a"):
            dm, age, cnt = P["idm_a"]
            if sum(1 for dd, aa in z["idm_a"] if dd <= dm and aa <= age) < cnt:
                fails.add("idm")
        if not fails or ("any" not in sub and not fails <= sub):
            continue
        if z["depth_atr"] < cfg.get("depth_min", 0.0) or z["disp"] < cfg.get("disp_min", 0.0):
            continue
        if not macd_div(M, z, tf, look=cfg.get("macd_look", 48), H=H, mac=mac):
            continue
        out.append(dict(z, pre_ok=True, src="macd", swept=list(z["swept"]) + ["macd" + tf]))
    return out


def build(M, C, cfg, P):
    """New (non-LIT) candidates of one retail family cfg for Market M (LIT candidates C), sorted like lit.candidates."""
    kind = cfg["kind"]
    if kind == "levels":
        LM = LevelsMarket(M, cfg)
        have = {(z["day"], z["ext_i"], z["dir"]) for z in C}
        out = [dict(z, src="lvl") for z in lit.candidates(LM, ref=P["ref"]) if (z["day"], z["ext_i"], z["dir"]) not in have]
    elif kind == "macd":
        out = fam_macd(M, cfg, P, C)
    else:
        trig = list(triggers(M, leg=cfg.get("leg", 24)))
        have = {(z["day"], z["ext_i"], z["dir"]) for z in C if lit.setup_ok(z, P)} if cfg.get("drop_lit", True) else set()
        out = {"sd": fam_sd, "brt": fam_brt, "ema": fam_ema}[kind](M, cfg, P, trig)
        out = [z for z in out if (z["day"], z["ext_i"], z["dir"]) not in have]
    out.sort(key=lambda z: (z["entry_t"], -z["dir"]))
    return out


def merge(C, new):
    """LIT candidates + retail candidates in entry order; at the same entry bar the LIT setup comes first."""
    return sorted(list(C) + list(new), key=lambda z: (z["entry_t"], z.get("src", "lit") != "lit", -z["dir"]))


def apply(M, C, P):
    """The live hook (engine/lit_live.py): P["retail"] = None (today) -> C unchanged; else C + every family's candidates."""
    R = P.get("retail")
    if not R:
        return C
    fams = R if isinstance(R, list) else [R]
    new = []
    for cfg in fams:
        new.extend(build(M, C, cfg, P))
    return merge(C, new)
