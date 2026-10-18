"""LIT higher-time-frame (HTF) confluences (owner order 2026-10-18: "Higher time frame stuff, look at that. Look at all
confluences, deep dive it.").

Builds on tools/lit_select.py (the 2026 LIT candidate set: every setup the live filters accept, each simulated alone with the
live executor, + 50 causal LTF features; candidate replay == run lit_live trade for trade). Adds causal HTF context at each
setup's trigger bar close (bars <= i only; 1H / 4H / daily / weekly built from the CME NQ1! 5m file):
  draw on liquidity   untaken PDH/PDL, PWH/PWL, PMH/PML, NWOG/NDOG edges: which side is nearer / holds more; untaken 1H/4H
                      swing and equal-high/low pools; did the sweep itself take an HTF pool
  dealing range       premium / discount of the entry in the prior-day, prior-week, 20-day, week-to-date and 4H swing ranges
  candle profile      PO3 of the daily (18:00), 4H, weekly and midnight opens (sweep on the manipulation side); the last
                      closed 1H / 4H / daily candle against the trade
  bias                prior-day / prior-week close location, prior-day close beyond the day before's extreme, prior-day
                      turtle soup
  structure           the last 1H / 4H / daily break of structure (fractal swings, close beyond) with the trade
  HTF FVGs            an unfilled opposing 1H / 4H FVG between entry and target; the sweep into a supportive 1H / 4H FVG
  time of week        Tue/Wed, the high/low-of-week window, the sweep as the week's new extreme
  composite           WITH the HTF draw (nearest untaken HTF level on the target side + 4H structure + prior-day close)
plus 26 LTF LIT confluences from lit_select's features. Steps:

  python tools/lit_htf.py build      # HTF features for every candidate -> research/runs/_cache/lithtf_*.pkl
  python tools/lit_htf.py lookahead  # HTF features recomputed on data cut at the entry bar == full-data features
  python tools/lit_htf.py map        # the confluence map (candidates + taken trades, H1/H2/2021-25, permutation p,
                                     # Benjamini-Hochberg) -> research/lit/htf_map.json
  python tools/lit_htf.py combos     # 2- and 3-way AND combinations picked on H1 (Westfall-Young max-z correction),
                                     # checked on H2 -> research/lit/htf_combos.json
  python tools/lit_htf.py rules      # survivors as skip / size 1.25x-0.75x / "HTF-aligned only in London" on the real LIT
                                     # path at the eval size -> research/lit/htf_rules.json
  python tools/lit_htf.py save       # rl.save the runs lit_htf_* (family other, tags lit, lit_htf)
Judged on 2026: pick on H1 (Jan 2 - Jun 30), check on H2 (Jul 1 - Oct 16). 2021-25 is a reference line (5m entries only).
Main metric: the MFFU 50K eval passed within 10 sessions (p10 / f10) and the cost per 2-week pass ($91.80 / p10).
Paper only. 1 CPU process. Changes no engine file.
"""
from __future__ import annotations

import collections
import itertools
import json
import math
import os
import pickle
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import lit  # noqa: E402
from tools import lit_final as F  # noqa: E402
from tools import lit_select as S  # noqa: E402
from tools import runlib as rl  # noqa: E402

CACHE = os.path.join(ROOT, "research", "runs", "_cache")
OUTD = os.path.join(ROOT, "research", "lit")
VER = "v1"
PRICE = 91.80                                   # owner's MFFU Builder 50K price
H1_MAX_AGE, H4_MAX_AGE = 5 * 276, 20 * 276      # FVG / pool memory in 5m bars (1H: 5 trading days, 4H: 20)
SWEEP_WIN = 24                                  # the LIT sweep window (2 h of 5m bars before the extreme)


# ================================================================================================ HTF bars and components
def _bars_of(M, key):
    key = np.asarray(key)
    st = np.r_[0, np.flatnonzero(np.diff(key) != 0) + 1]
    en = np.r_[st[1:], M.n]
    return {"o": M.o[st].astype(float), "h": np.maximum.reduceat(M.h, st).astype(float),
            "l": np.minimum.reduceat(M.l, st).astype(float), "c": M.c[en - 1].astype(float), "first": st, "last": en - 1}


def _first_after(arr, start, stop, cond_fn):
    """First index j in [start, stop) with cond_fn(arr[start:stop]) True, else a big number."""
    if start >= stop:
        return 10 ** 12
    seg = cond_fn(arr[start:stop])
    j = int(np.argmax(seg))
    return start + j if seg[j] else 10 ** 12


class HTF:
    """Every HTF component for a Market, computed once; feats(z, pl) reads only bars <= z['i'] (see lookahead())."""

    def __init__(self, M):
        self.M = M
        n = M.n
        h, l = M.h.astype(float), M.l.astype(float)
        g = lambda a, key, f: getattr(pd.Series(a).groupby(np.asarray(key)), f)().values
        self.dhi, self.dlo = g(h, M.day_of, "cummax"), g(l, M.day_of, "cummin")
        self.whi, self.wlo = g(h, M.week_id, "cummax"), g(l, M.week_id, "cummin")
        self.mhi, self.mlo = g(h, M.month_id, "cummax"), g(l, M.month_id, "cummin")
        self.tf = {}
        keys = {"1h": M.t // 3600, "4h": M.day_of.astype(np.int64) * 10 + ((M.mod - 1080) % 1440) // 240, "d": M.day_of}
        for nm, key in keys.items():
            B = _bars_of(M, key)
            B["k"] = 2 if nm != "d" else 1
            self._structure(B)
            self.tf[nm] = B
        self._fvgs("1h", H1_MAX_AGE)
        self._fvgs("4h", H4_MAX_AGE)
        self._pools("1h", H1_MAX_AGE, 120)
        self._pools("4h", H4_MAX_AGE, 60)
        # week extremes by week for prior-week bias
        self.week_rows = {}
        for k, (d, s, e) in enumerate(M.days):
            w = int(M.week_id[s])
            r = self.week_rows.setdefault(w, {"o": float(M.o[s]), "h": -np.inf, "l": np.inf, "c": None, "end": e})
            r["h"] = max(r["h"], float(h[s:e].max())); r["l"] = min(r["l"], float(l[s:e].min())); r["c"] = float(M.c[e - 1])
            r["end"] = e

    # ---- market structure: last break of a confirmed fractal swing by a close
    def _structure(self, B):
        H, L, C, k = B["h"], B["l"], B["c"], B["k"]
        N = len(H)
        fh, fl = lit.fractals(H, L, k)
        conf_h = collections.defaultdict(list); conf_l = collections.defaultdict(list)
        for j in fh:
            if j + k < N:
                conf_h[j + k].append(j)
        for j in fl:
            if j + k < N:
                conf_l[j + k].append(j)
        trend = np.zeros(N, np.int8); sh_px = np.full(N, np.nan); sl_px = np.full(N, np.nan)
        cur, sh, sl, sh_b, sl_b = 0, np.nan, np.nan, True, True
        for m in range(N):
            if not sh_b and C[m] > sh:
                cur, sh_b = 1, True
            if not sl_b and C[m] < sl:
                cur, sl_b = -1, True
            for j in conf_h.get(m, []):
                sh, sh_b = H[j], False
            for j in conf_l.get(m, []):
                sl, sl_b = L[j], False
            trend[m] = cur
            sh_px[m] = sh; sl_px[m] = sl
        B["trend"], B["sh_px"], B["sl_px"] = trend, sh_px, sl_px
        B["fh"], B["fl"] = fh, fl

    # ---- fair value gaps on closed HTF bars; fill / touch indices on the 5m bars after formation
    def _fvgs(self, nm, max_age):
        B, M = self.tf[nm], self.M
        H, L, last = B["h"], B["l"], B["last"]
        rows = []
        for m in range(2, len(H)):
            if L[m] > H[m - 2]:
                rows.append((1, H[m - 2], L[m], last[m]))
            elif H[m] < L[m - 2]:
                rows.append((-1, H[m], L[m - 2], last[m]))
        side = np.array([r[0] for r in rows], np.int8)
        bot = np.array([r[1] for r in rows]); top = np.array([r[2] for r in rows]); kn = np.array([r[3] for r in rows], np.int64)
        fill = np.empty(len(rows), np.int64); touch = np.empty(len(rows), np.int64)
        for q in range(len(rows)):
            a, z = kn[q] + 1, min(M.n, kn[q] + 1 + max_age)
            if side[q] == 1:
                fill[q] = _first_after(M.l, a, z, lambda x, b=bot[q]: x < b)
                touch[q] = _first_after(M.l, a, z, lambda x, t=top[q]: x <= t)
            else:
                fill[q] = _first_after(M.h, a, z, lambda x, t=top[q]: x > t)
                touch[q] = _first_after(M.h, a, z, lambda x, b=bot[q]: x >= b)
        B["fvg"] = {"side": side, "bot": bot, "top": top, "known": kn, "fill": fill, "touch": touch, "max_age": max_age}

    # ---- liquidity pools: unswept fractal swings and equal highs / lows
    def _pools(self, nm, max_age, eq_back):
        B, M = self.tf[nm], self.M
        H, L, last, k = B["h"], B["l"], B["last"], B["k"]
        N = len(H)
        rng = H - L
        atr = pd.Series(rng).rolling(14, min_periods=1).mean().values
        out = {"swing": [], "eq": []}
        for side, idx, arr in (("high", B["fh"], H), ("low", B["fl"], L)):
            recent = collections.deque()
            for j in idx:
                if j + k >= N:
                    continue
                kn = int(last[j + k])
                out["swing"].append((side, float(arr[j]), kn))
                while recent and j - recent[0] > eq_back:
                    recent.popleft()
                tol = max(2.0, 0.1 * atr[j])
                for jj in reversed(recent):
                    if j - jj < 2 or abs(arr[j] - arr[jj]) > tol:
                        continue
                    if side == "high":
                        lev = max(arr[j], arr[jj])
                        if H[jj + 1:j].max() < lev:
                            out["eq"].append(("high", float(lev), kn)); break
                    else:
                        lev = min(arr[j], arr[jj])
                        if L[jj + 1:j].min() > lev:
                            out["eq"].append(("low", float(lev), kn)); break
                recent.append(j)
        P = {}
        for typ, rows in out.items():
            sd = np.array([1 if r[0] == "high" else -1 for r in rows], np.int8)
            px = np.array([r[1] for r in rows]); kn = np.array([r[2] for r in rows], np.int64)
            tk = np.empty(len(rows), np.int64)
            for q in range(len(rows)):
                a, z = kn[q] + 1, min(M.n, kn[q] + 1 + max_age)
                tk[q] = _first_after(M.h, a, z, lambda x, p=px[q]: x > p) if sd[q] == 1 else \
                    _first_after(M.l, a, z, lambda x, p=px[q]: x < p)
            P[typ] = {"side": sd, "px": px, "known": kn, "taken": tk, "max_age": max_age}
        B["pools"] = P

    # ---- helpers at a bar
    def closed(self, nm, i):
        """Number of closed bars of time frame nm at the close of 5m bar i (bars 0..n-1 are closed)."""
        return int(np.searchsorted(self.tf[nm]["last"], i, side="right"))

    def _active_pools(self, nm, typ, i):
        P = self.tf[nm]["pools"][typ]
        ok = (P["known"] <= i) & (P["taken"] > i) & (i - P["known"] <= P["max_age"])
        return P["side"][ok], P["px"][ok]

    def _swept_pool(self, nm, typ, ext, d):
        """Did the sweep (the 2 h before the extreme up to it) take an HTF pool on the swept side (lows for a long)?"""
        P = self.tf[nm]["pools"][typ]
        w0 = ext - SWEEP_WIN
        sd = -d
        ok = (P["side"] == sd) & (P["known"] <= w0) & (P["taken"] > w0) & (P["taken"] <= ext) & (ext - P["known"] <= P["max_age"])
        return int(ok.any())

    def _pool_draw(self, nm, typ, i, d, px_now):
        sd, px = self._active_pools(nm, typ, i)
        up = px[(sd == 1) & (px > px_now)]; dn = px[(sd == -1) & (px < px_now)]
        if not len(up) and not len(dn):
            return np.nan
        du = (up.min() - px_now) if len(up) else np.inf
        dd = (px_now - dn.max()) if len(dn) else np.inf
        near_up = du < dd
        return float(near_up if d == 1 else not near_up)

    def _fvg_way(self, nm, i, d, ep, tp):
        G = self.tf[nm]["fvg"]
        ok = (G["known"] <= i) & (G["fill"] > i) & (i - G["known"] <= G["max_age"])
        if d == 1:
            ok &= (G["side"] == -1) & (G["bot"] > ep) & (G["bot"] < ep + tp)
        else:
            ok &= (G["side"] == 1) & (G["top"] < ep) & (G["top"] > ep - tp)
        return int(ok.any())

    def _fvg_sweep(self, nm, ext, d):
        G, M = self.tf[nm]["fvg"], self.M
        ok = (G["known"] < ext) & (G["fill"] >= ext) & (ext - G["known"] <= G["max_age"])
        if d == 1:
            ok &= (G["side"] == 1) & (M.l[ext] <= G["top"])
        else:
            ok &= (G["side"] == -1) & (M.h[ext] >= G["bot"])
        return int(ok.any())

    # ---- the features of one setup
    def feats(self, z, pl):
        M = self.M
        i, ext, d, k = int(z["i"]), int(z["ext_i"]), int(z["dir"]), int(z["k"])
        x = M.ctx[k]
        s = x["s"]
        ep, risk, tp = pl["ep"], pl["risk"], pl["tp"]
        vm = x.get("vix_move") or np.nan
        px_now = float(M.c[i])
        f = {}
        # -------- draw on liquidity: daily / weekly / monthly levels and opening gaps, untaken by bar i
        L = []                                                            # (side +1 high / -1 low, price, taken)
        dhi, dlo, whi, wlo, mhi, mlo = self.dhi[i], self.dlo[i], self.whi[i], self.wlo[i], self.mhi[i], self.mlo[i]
        if "pdh" in x:
            L += [(1, x["pdh"], dhi > x["pdh"], "pd"), (-1, x["pdl"], dlo < x["pdl"], "pd")]
        if "pwh" in x:
            L += [(1, x["pwh"], whi > x["pwh"], "pw"), (-1, x["pwl"], wlo < x["pwl"], "pw")]
        if "pmh" in x:
            L += [(1, x["pmh"], mhi > x["pmh"], "pm"), (-1, x["pml"], mlo < x["pml"], "pm")]
        if x.get("ndog"):
            for p in x["ndog"]:
                up = p > M.o[s]
                L.append((1 if up else -1, float(p), (dhi >= p) if up else (dlo <= p), "gap"))
        if x.get("nwog"):
            wo = float(M.open_wk[s])
            for p in x["nwog"]:
                up = p > wo
                L.append((1 if up else -1, float(p), (whi >= p) if up else (wlo <= p), "gap"))

        def side_d(sd):
            return sd * d                                                 # +1 = target side

        def near_with(rows):
            tg = [abs(p - px_now) for sd, p, tk, _ in rows if not tk and side_d(sd) == 1]
            op = [abs(p - px_now) for sd, p, tk, _ in rows if not tk and side_d(sd) == -1]
            if not tg and not op:
                return np.nan
            return float((min(tg) if tg else np.inf) < (min(op) if op else np.inf))

        f["dr_all"] = near_with(L)
        for c_ in ("pd", "pw", "pm", "gap"):
            f["dr_" + c_] = near_with([r for r in L if r[3] == c_])
        tg = [abs(p - px_now) for sd, p, tk, _ in L if not tk and side_d(sd) == 1 and abs(p - px_now) <= 1.5 * vm]
        op = [abs(p - px_now) for sd, p, tk, _ in L if not tk and side_d(sd) == -1 and abs(p - px_now) <= 1.5 * vm]
        f["dr_more"] = np.nan if len(tg) == len(op) else float(len(tg) > len(op))
        f["dr_reach"] = float(any(not tk and side_d(sd) == 1 and 0 < (p - ep) * d <= tp for sd, p, tk, _ in L))
        cls = set(z["swept_cls"])
        f["dr_swept_htf"] = float(bool(cls & {"pd", "pw", "pm"}))
        pd_t = [r for r in L if r[3] == "pd" and side_d(r[0]) == 1]
        f["dr_pd_rev"] = float("pd" in cls and bool(pd_t) and not pd_t[0][2])   # took PDL (long), PDH still untaken
        # 1H / 4H pools
        for nm in ("1h", "4h"):
            f[f"pl_eq{nm}"] = self._pool_draw(nm, "eq", i, d, px_now)
            f[f"pl_sw{nm}"] = self._pool_draw(nm, "swing", i, d, px_now)
            f[f"pl_take{nm}"] = float(self._swept_pool(nm, "swing", ext, d))
        f["pl_take_eq"] = float(self._swept_pool("1h", "eq", ext, d) or self._swept_pool("4h", "eq", ext, d))
        # -------- dealing ranges (position of the entry, direction space: 0 = the stop side, 1 = the target side)
        def pos(hi, lo):
            if not (np.isfinite(hi) and np.isfinite(lo)) or hi - lo <= 0:
                return np.nan
            p = (ep - lo) / (hi - lo)
            return p if d == 1 else 1 - p
        f["rg_pd_pos"] = pos(x["pdh"], x["pdl"]) if "pdh" in x else np.nan
        f["rg_pw_pos"] = pos(x["pwh"], x["pwl"]) if "pwh" in x else np.nan
        ks = [kk for kk in range(max(0, k - 20), k)]
        if len(ks) == 20:
            a0, a1 = M.days[ks[0]][1], M.days[ks[-1]][2]
            f["rg_20d_pos"] = pos(float(M.h[a0:a1].max()), float(M.l[a0:a1].min()))
        else:
            f["rg_20d_pos"] = np.nan
        f["rg_wk_pos"] = pos(float(whi), float(wlo))
        n4 = self.closed("4h", i)
        B4 = self.tf["4h"]
        f["rg_4h_pos"] = pos(B4["sh_px"][n4 - 1], B4["sl_px"][n4 - 1]) if n4 else np.nan
        # -------- candle profile (PO3) at the sweep extreme
        lo_ext = float(M.l[ext]) if d == 1 else -float(M.h[ext])
        def beyond(op):
            return np.nan if op is None or not np.isfinite(op) else float(lo_ext < op * d)
        f["po3_d"] = beyond(float(x["open18"]))
        f["po3_d_buy"] = float((ep - x["open18"]) * d < 0)
        rel = int((M.mod[ext] - 1080) % 1440) % 240
        f["po3_4h"] = float(lo_ext < float(M.open_4h[ext]) * d and rel < 120)
        f["po3_wk"] = beyond(float(M.open_wk[ext]))
        o00 = M.open_00[ext]
        f["po3_00"] = beyond(float(o00)) if not np.isnan(o00) else np.nan
        for nm in ("1h", "4h"):
            nn = self.closed(nm, i)
            B = self.tf[nm]
            f[f"c{nm}_counter"] = float((B["c"][nn - 1] - B["o"][nn - 1]) * d < 0) if nn else np.nan
        # -------- bias: prior day / week
        if k >= 2:
            ps, pe = M.days[k - 1][1], M.days[k - 1][2]
            qs, qe = M.days[k - 2][1], M.days[k - 2][2]
            ph, pl_, pc = float(M.h[ps:pe].max()), float(M.l[ps:pe].min()), float(M.c[pe - 1])
            qh, ql = float(M.h[qs:qe].max()), float(M.l[qs:qe].min())
            cp = (pc - pl_) / max(ph - pl_, 1e-9)
            f["bi_pdc"] = float((cp if d == 1 else 1 - cp) >= 0.5)
            f["cd_counter"] = float((pc - float(M.o[ps])) * d < 0)
            f["bi_pdbos"] = float(pc > qh if d == 1 else pc < ql)
            f["bi_pdts"] = float((pl_ < ql and pc > ql) if d == 1 else (ph > qh and pc < qh))
        else:
            f["bi_pdc"] = f["cd_counter"] = f["bi_pdbos"] = f["bi_pdts"] = np.nan
        w = int(M.week_id[s])
        pw = [ww for ww in self.week_rows if ww < w and self.week_rows[ww]["end"] <= s]
        if pw:
            r = self.week_rows[max(pw)]
            cp = (r["c"] - r["l"]) / max(r["h"] - r["l"], 1e-9)
            f["bi_pwc"] = float((cp if d == 1 else 1 - cp) >= 0.5)
        else:
            f["bi_pwc"] = np.nan
        # -------- structure: the last BOS of closed 1H / 4H / daily bars
        for nm in ("1h", "4h", "d"):
            nn = self.closed(nm, i)
            tr = int(self.tf[nm]["trend"][nn - 1]) if nn else 0
            f[f"ms_{nm}"] = np.nan if tr == 0 else float(tr == d)
        # -------- HTF FVGs
        for nm in ("1h", "4h"):
            f[f"fv_way{nm}"] = float(self._fvg_way(nm, i, d, ep, tp))
            f[f"fv_sweep{nm}"] = float(self._fvg_sweep(nm, ext, d))
        # -------- time of week
        dow = int(x["dow"])
        f["tw_dow"] = float(dow)
        wlo_ext = self.wlo[ext] if d == 1 else -self.whi[ext]
        f["tw_wkext"] = float(lo_ext <= wlo_ext + 1e-9)
        return f


# ================================================================================================ build (all candidates)
_S = {}


def market():
    if "M" not in _S:
        M, C = F.market(S.PU["ref"], S.PU["extra_boxes"])
        Cx = {(z["day"], z["i"], z["dir"]): z for z in C}
        _S.update(M=M, C=C, Cx=Cx)
    return _S["M"], _S["Cx"]


def build(force=False):
    p = os.path.join(CACHE, f"lithtf_{VER}_{rl._data_key().replace(':', '_')}.pkl")
    if os.path.exists(p) and not force:
        return pickle.load(open(p, "rb"))
    R = S.build()["rows"]
    M, Cx = market()
    H = HTF(M)
    out = {}
    for r in R:
        z = Cx[r["key"]]
        pl = S.plan_of(M, z)
        out[r["key"]] = H.feats(z, pl)
    pickle.dump(out, open(p, "wb"))
    return out


def rows():
    """lit_select candidate rows with the HTF features merged into r['h']."""
    if "R" not in _S:
        R = S.build()["rows"]
        Hf = build()
        for r in R:
            r["h"] = Hf[r["key"]]
        _S["R"] = R
    return _S["R"]


def lookahead(cuts=10, seed=5):
    """Cut the 5m data at a setup's entry bar N (bar N reduced to its open, tests/test_lit_lookahead.py), rebuild the market,
    the candidates and the HTF components, recompute every HTF feature of the setups whose entry bar is N, compare."""
    import random
    from engine.data import load
    from tests.test_lit_lookahead import _cut
    full = load("NQ", "5m")
    a = int(np.searchsorted(np.array(full.date_str), "2025-08-01"))
    B = full.slice(a, len(full))
    Mf = lit.Market(bars=B, extra_boxes=S.PU["extra_boxes"])
    Cf = lit.candidates(Mf, ref=S.PU["ref"])
    Hf = HTF(Mf)
    rng = random.Random(seed)
    ent = sorted({z["entry_i"] for z in Cf if z["day"] >= "2026" and S.plan_of(Mf, z) is not None})
    picks = sorted(rng.sample(ent, min(cuts, len(ent))))
    bad = n = 0
    for N in picks:
        A = {(z["i"], z["dir"]): Hf.feats(z, S.plan_of(Mf, z)) for z in Cf if z["entry_i"] == N and S.plan_of(Mf, z)}
        Mt = lit.Market(bars=_cut(B, N), extra_boxes=S.PU["extra_boxes"])
        Ct = lit.candidates(Mt, ref=S.PU["ref"])
        Ht = HTF(Mt)
        Z = {(z["i"], z["dir"]): Ht.feats(z, S.plan_of(Mt, z)) for z in Ct if z["entry_i"] == N and S.plan_of(Mt, z)}
        for kk in A:
            n += 1
            if kk not in Z:
                bad += 1; print("missing in cut", B.date_str[N], kk); continue
            df = [q for q in A[kk] if not (A[kk][q] == Z[kk][q] or (np.isnan(A[kk][q]) and np.isnan(Z[kk][q]))
                                            or abs(A[kk][q] - Z[kk][q]) < 1e-9)]
            if df:
                bad += 1; print("differs", B.date_str[N], kk, [(q, A[kk][q], Z[kk][q]) for q in df])
        print(f"cut {B.date_str[N]} bar {N}: {len(A)} setups checked", flush=True)
    print(f"lookahead: {n} setups, {bad} with a difference")
    return bad == 0


# ================================================================================================ the confluences
def _b(v):
    return np.nan if v is None or (isinstance(v, float) and np.isnan(v)) else float(bool(v))


def _cmp(v, fn):
    return np.nan if v is None or (isinstance(v, float) and np.isnan(v)) else float(bool(fn(v)))


# id: (family, plain-language definition, fn(f = LTF features, h = HTF features) -> 1 / 0 / nan)
CONF = collections.OrderedDict([
    # ---- HTF draw on liquidity
    ("dr_all", ("HTF draw", "the nearest untaken daily/weekly/monthly level or opening-gap edge (PDH/PDL, PWH/PWL, PMH/PML, "
                "NWOG/NDOG) is on the trade's target side", lambda f, h: h["dr_all"])),
    ("dr_pd", ("HTF draw", "daily draw: the previous day's high (long) is untaken and nearer than an untaken PDL (or PDL is taken)",
               lambda f, h: h["dr_pd"])),
    ("dr_pw", ("HTF draw", "weekly draw: the previous week's high/low on the target side is the untaken / nearer one",
               lambda f, h: h["dr_pw"])),
    ("dr_pm", ("HTF draw", "monthly draw: the previous month's high/low on the target side is the untaken / nearer one",
               lambda f, h: h["dr_pm"])),
    ("dr_gap", ("HTF draw", "the nearest unfilled NWOG/NDOG edge is on the target side", lambda f, h: h["dr_gap"])),
    ("dr_more", ("HTF draw", "more untaken HTF levels within 1.5 VIX moves on the target side than behind the trade",
                 lambda f, h: h["dr_more"])),
    ("dr_reach", ("HTF draw", "an untaken HTF level sits between the entry and the VIX-band target (a draw on the way)",
                  lambda f, h: h["dr_reach"])),
    ("dr_swept_htf", ("HTF draw", "the sweep took a daily, weekly or monthly level (PDL/PWL/PML for a long)",
                      lambda f, h: h["dr_swept_htf"])),
    ("dr_pd_rev", ("HTF draw", "the sweep took PDL (long) while PDH is still untaken: the classic daily reversal",
                   lambda f, h: h["dr_pd_rev"])),
    ("pl_eq1h", ("HTF draw", "the nearest untaken 1H equal-highs/lows pool is on the target side", lambda f, h: h["pl_eq1h"])),
    ("pl_eq4h", ("HTF draw", "the nearest untaken 4H equal-highs/lows pool is on the target side", lambda f, h: h["pl_eq4h"])),
    ("pl_sw1h", ("HTF draw", "the nearest unswept 1H swing is on the target side", lambda f, h: h["pl_sw1h"])),
    ("pl_sw4h", ("HTF draw", "the nearest unswept 4H swing is on the target side", lambda f, h: h["pl_sw4h"])),
    ("pl_take1h", ("HTF draw", "the sweep took an unswept 1H swing low (long) / high (short)", lambda f, h: h["pl_take1h"])),
    ("pl_take4h", ("HTF draw", "the sweep took an unswept 4H swing low (long) / high (short)", lambda f, h: h["pl_take4h"])),
    ("pl_take_eq", ("HTF draw", "the sweep took 1H or 4H equal lows (long) / highs (short)", lambda f, h: h["pl_take_eq"])),
    # ---- HTF dealing range (premium / discount)
    ("rg_pd", ("HTF range", "entry in the discount (long) / premium (short) half of the previous day's range",
               lambda f, h: _cmp(h["rg_pd_pos"], lambda v: v < 0.5))),
    ("rg_pw", ("HTF range", "entry in the discount / premium half of the previous week's range",
               lambda f, h: _cmp(h["rg_pw_pos"], lambda v: v < 0.5))),
    ("rg_20d", ("HTF range", "entry in the discount / premium half of the last 20 days' range",
                lambda f, h: _cmp(h["rg_20d_pos"], lambda v: v < 0.5))),
    ("rg_wk", ("HTF range", "entry in the discount / premium half of this week's range so far",
               lambda f, h: _cmp(h["rg_wk_pos"], lambda v: v < 0.5))),
    ("rg_4h", ("HTF range", "entry in the discount / premium half of the 4H dealing range (last confirmed 4H swing high-low)",
               lambda f, h: _cmp(h["rg_4h_pos"], lambda v: v < 0.5))),
    # ---- HTF candle profile (PO3)
    ("po3_d", ("HTF PO3", "the sweep went beyond the 18:00 daily open (the manipulation leg of the day's candle)",
               lambda f, h: h["po3_d"])),
    ("po3_d_buy", ("HTF PO3", "the entry is still on the cheap side of the 18:00 open (below it for a long)",
                   lambda f, h: h["po3_d_buy"])),
    ("po3_4h", ("HTF PO3", "the sweep went beyond the 4H candle's open within the first 2 hours of that 4H candle",
                lambda f, h: h["po3_4h"])),
    ("po3_wk", ("HTF PO3", "the sweep went beyond the weekly open", lambda f, h: h["po3_wk"])),
    ("po3_00", ("HTF PO3", "the sweep went beyond the midnight open", lambda f, h: h["po3_00"])),
    ("c1h_counter", ("HTF PO3", "the last closed 1H candle closed against the trade", lambda f, h: h["c1h_counter"])),
    ("c4h_counter", ("HTF PO3", "the last closed 4H candle closed against the trade", lambda f, h: h["c4h_counter"])),
    ("cd_counter", ("HTF PO3", "the previous day's candle closed against the trade", lambda f, h: h["cd_counter"])),
    # ---- HTF bias
    ("bi_pdc", ("HTF bias", "the previous day closed in the half of its range on the trade's side (upper half for a long)",
                lambda f, h: h["bi_pdc"])),
    ("bi_pdbos", ("HTF bias", "the previous day closed beyond the day before's high (long) / low (short)",
                  lambda f, h: h["bi_pdbos"])),
    ("bi_pdts", ("HTF bias", "the previous day swept the day before's low (long) and closed back above it (daily turtle soup)",
                 lambda f, h: h["bi_pdts"])),
    ("bi_pwc", ("HTF bias", "the previous week closed in the half of its range on the trade's side", lambda f, h: h["bi_pwc"])),
    # ---- HTF structure
    ("ms_1h", ("HTF structure", "the last 1H break of structure (close beyond a fractal swing) was in the trade's direction",
               lambda f, h: h["ms_1h"])),
    ("ms_4h", ("HTF structure", "the last 4H break of structure was in the trade's direction", lambda f, h: h["ms_4h"])),
    ("ms_d", ("HTF structure", "the last daily break of structure was in the trade's direction", lambda f, h: h["ms_d"])),
    # ---- HTF FVGs
    ("fv_way1h", ("HTF FVG", "an unfilled opposing 1H FVG sits between the entry and the target", lambda f, h: h["fv_way1h"])),
    ("fv_way4h", ("HTF FVG", "an unfilled opposing 4H FVG sits between the entry and the target", lambda f, h: h["fv_way4h"])),
    ("fv_sweep1h", ("HTF FVG", "the sweep ran into an unfilled supportive 1H FVG", lambda f, h: h["fv_sweep1h"])),
    ("fv_sweep4h", ("HTF FVG", "the sweep ran into an unfilled supportive 4H FVG", lambda f, h: h["fv_sweep4h"])),
    # ---- time of week
    ("tw_tuewed", ("time of week", "Tuesday or Wednesday", lambda f, h: float(h["tw_dow"] in (1, 2)))),
    ("tw_how", ("time of week", "the sweep extreme is inside Tue 03:00 - Wed 11:30 (the high/low-of-week window)",
                lambda f, h: f["how"])),
    ("tw_wkext", ("time of week", "the sweep made a new low (long) / high (short) of the week", lambda f, h: h["tw_wkext"])),
    ("tw_wkext_mw", ("time of week", "the sweep made a new weekly low/high on Monday-Wednesday (weekly low/high formation)",
                     lambda f, h: float(h["tw_wkext"] == 1 and h["tw_dow"] <= 2))),
    ("tw_mon", ("time of week", "Monday", lambda f, h: float(h["tw_dow"] == 0))),
    ("tw_fri", ("time of week", "Friday", lambda f, h: float(h["tw_dow"] == 4))),
    # ---- composite
    ("cx_with", ("HTF composite", "WITH the HTF draw: at least 2 of (nearest untaken HTF level on the target side, last 4H BOS "
                 "with the trade, previous day closed on the trade's side)", lambda f, h: _cx(h, 2))),
    ("cx_full", ("HTF composite", "all 3 of the HTF-draw items agree with the trade", lambda f, h: _cx(h, 3))),
    ("cx_against", ("HTF composite", "AGAINST the HTF draw: none of the 3 items agrees", lambda f, h: _cx(h, 0, exact=True))),
    # ---- LTF LIT confluences (lit_select features)
    ("lt_trap6", ("LTF LIT", "fresh trap: the inducement swing was made <= 6 bars (30 min) before the sweep",
                  lambda f, h: float(f["idm_age"] <= 6))),
    ("lt_trap_close", ("LTF LIT", "close trap: the inducement swing sits < 0.39 ATR above the swept level",
                       lambda f, h: float(f["idm_dist"] < 0.39))),
    ("lt_idm2", ("LTF LIT", "2+ inducement swings qualified", lambda f, h: float(f["idm_n"] >= 2))),
    ("lt_multi", ("LTF LIT", "the sweep took 2+ levels", lambda f, h: float(f["n_swept"] >= 2))),
    ("lt_major", ("LTF LIT", "the sweep took a daily/weekly/monthly level or an opening-gap edge", lambda f, h: f["major"])),
    ("lt_box", ("LTF LIT", "the sweep took a session box (Asia / London / NY / premarket)", lambda f, h: f["box"])),
    ("lt_bu_only", ("LTF LIT", "the sweep took only build-up (equal 5m) liquidity", lambda f, h: f["bu_only"])),
    ("lt_depth_mid", ("LTF LIT", "sweep depth 1.6-2.7 ATR", lambda f, h: float(1.6 <= f["depth"] <= 2.7))),
    ("lt_disp_big", ("LTF LIT", "displacement body > 1.25 ATR", lambda f, h: float(f["disp"] > 1.25))),
    ("lt_stop_small", ("LTF LIT", "planned stop < 31.5 pts", lambda f, h: float(f["stop_pts"] < 31.5))),
    ("lt_rr4", ("LTF LIT", "the VIX-band target is 4R or more away", lambda f, h: float(f["rr"] >= 4))),
    ("lt_room", ("LTF LIT", "room to run: the first opposing level is >= 1.5R away", lambda f, h: float(f["obst_r"] >= 1.5))),
    ("lt_london", ("LTF LIT", "London-morning entry (before 08:00 ET)", lambda f, h: float(f["mod"] < 480))),
    ("lt_early", ("LTF LIT", "entry before 04:05 ET", lambda f, h: float(f["mod"] < 245))),
    ("lt_lv30", ("LTF LIT", "30 or fewer levels already taken today", lambda f, h: float(f["lv_taken"] <= 30))),
    ("lt_news_clear", ("LTF LIT", "no high-impact release in the next 60 min", lambda f, h: float(f["news_next"] > 60))),
    ("lt_news_day", ("LTF LIT", "a high-impact news day", lambda f, h: f["news_day"])),
    ("lt_es_swept", ("LTF LIT", "ES swept its own low/high too (no SMT divergence)", lambda f, h: f["es_swept"])),
    ("lt_day_ext", ("LTF LIT", "the sweep is the day's extreme so far", lambda f, h: f["sweep_day_ext"])),
    ("lt_opp_lon", ("LTF LIT", "the day's opposite extreme was made in London", lambda f, h: f["opp_ext_lon"])),
    ("lt_vec", ("LTF LIT", "a vector (climax volume) candle at the sweep", lambda f, h: f["vec_sweep"])),
    ("lt_first", ("LTF LIT", "the first accepted setup of the day", lambda f, h: float(f["prior_same"] + f["prior_opp"] == 0))),
    ("lt_prev_win", ("LTF LIT", "the previous LIT trade was a winner", lambda f, h: f["prev_win"])),
    ("lt_wk_clean", ("LTF LIT", "no stop-out yet this week", lambda f, h: float(f["wk_stops"] == 0))),
    ("lt_cisd_long", ("LTF LIT", "the CISD run into the extreme is 5+ bars", lambda f, h: float(f["cisd_run"] >= 5))),
    ("lt_long", ("LTF LIT", "a long (vs a short)", lambda f, h: float(f["dir"] == 1))),
])


def _cx(h, need, exact=False):
    v = [h["dr_all"], h["ms_4h"], h["bi_pdc"]]
    sc = sum(1 for q in v if q == 1)
    if exact:
        return float(sc == need and not any(np.isnan(q) for q in v))
    return float(sc >= need)


def flag(r, cid):
    v = CONF[cid][2](r["f"], r["h"])
    if v is None:
        return np.nan
    v = float(v)
    return v


# ================================================================================================ the confluence map
SPANS = ("H1", "H2", "2021-25")


def _perm_p(y, x, n=4000, rng=None):
    """Two-sided permutation p of the difference in mean R between x == 1 and x == 0 (labels shuffled)."""
    rng = rng or np.random.default_rng(7)
    n1 = int(x.sum()); n0 = len(x) - n1
    if n1 < 3 or n0 < 3:
        return None
    obs = y[x == 1].mean() - y[x == 0].mean()
    Y = np.array([rng.permutation(y) for _ in range(n)])
    s1 = Y[:, x == 1].sum(1)
    dif = s1 / n1 - (y.sum() - s1) / n0
    return round(float(((np.abs(dif) >= abs(obs) - 1e-12).sum() + 1) / (n + 1)), 4)


def _cell(y, usd, x):
    on, off = x == 1, x == 0
    def g(m):
        if not m.any():
            return {"n": 0}
        yy, uu = y[m], usd[m]
        gl = -uu[uu < 0].sum()
        return {"n": int(m.sum()), "win": round(100 * float((yy > 0.5).mean()), 1), "avg_r": round(float(yy.mean()), 3),
                "usd": round(float(uu.sum())), "pf": round(float(uu[uu > 0].sum() / gl), 2) if gl else None}
    return g(on), g(off)


def _usd_alone(u):
    mi, mn = S.TL.base_q(u, S.EVAL_RULE)
    return S.TL.at_size({**u, "wk_m": 1.0}, mi, mn)["pnl"]


def _bh(ps):
    """Benjamini-Hochberg q-values for a list of p (None kept)."""
    idx = [i for i, p in enumerate(ps) if p is not None]
    m = len(idx)
    q = [None] * len(ps)
    order = sorted(idx, key=lambda i: ps[i])
    prev = 1.0
    for rank in range(m, 0, -1):
        i = order[rank - 1]
        prev = min(prev, ps[i] * m / rank)
        q[i] = round(prev, 4)
    return q


def base_path():
    if "U" not in _S:
        R = rows()
        U = S.replay(R)
        T = S.TL.sized(U, S.EVAL_RULE)                # the same trades at the eval base size + weekly stop, no room cap
        _S["U"], _S["T"] = U, T
    return _S["U"], _S["T"]


def map_(quiet=False):
    R = rows()
    U, T = base_path()
    rng = np.random.default_rng(11)
    res = collections.OrderedDict()
    sets = {}
    for s in SPANS:
        a, z = S.SPAN[s]
        C = [r for r in R if a <= r["day"] <= z and r["u"] is not None]
        sets[("cand", s)] = (C, np.array([r["u"]["r1"] for r in C]), np.array([_usd_alone(r["u"]) for r in C]))
        TT = [t for t in T if a <= t["day"] <= z]
        sets[("taken", s)] = ([t["_row"] for t in TT], np.array([t["r1"] for t in TT]), np.array([t["pnl"] for t in TT]))
    for cid, (fam, txt, _) in CONF.items():
        o = {"family": fam, "def": txt}
        for (lvl, s), (RR, y, usd) in sets.items():
            x = np.array([flag(r, cid) for r in RR])
            ok = ~np.isnan(x)
            on, off = _cell(y[ok], usd[ok], x[ok])
            p = _perm_p(y[ok], x[ok], rng=rng) if s != "2021-25" or lvl == "cand" else None
            d_r = round(on["avg_r"] - off["avg_r"], 3) if on["n"] and off["n"] else None
            o[f"{lvl}_{s}"] = {"on": on, "off": off, "d_r": d_r, "p": p, "share": round(100 * on["n"] / max(1, ok.sum()), 1)}
        res[cid] = o
    # multiple-testing correction: BH over the H1 candidate tests (the picking family) and over the H2 checks
    cids = list(res)
    for key in ("cand_H1", "cand_H2", "taken_H1", "taken_H2"):
        q = _bh([res[c][key]["p"] for c in cids])
        for c, qq in zip(cids, q):
            res[c][key]["q"] = qq
    # Fisher-combined p of H1 and H2 (candidates), only when the sign agrees
    comb = []
    for c in cids:
        a, b = res[c]["cand_H1"], res[c]["cand_H2"]
        if a["p"] is None or b["p"] is None or a["d_r"] is None or b["d_r"] is None or a["d_r"] * b["d_r"] <= 0:
            comb.append(None); continue
        st = -2 * (math.log(a["p"]) + math.log(b["p"]))
        comb.append(float(math.exp(-st / 2) * (1 + st / 2)))      # chi2 survival, 4 dof
    qc = _bh(comb)
    for c, p_, q_ in zip(cids, comb, qc):
        res[c]["fisher_p"] = round(p_, 4) if p_ is not None else None
        res[c]["fisher_q"] = q_
        res[c]["verdict"] = verdict(res[c])
    json.dump({"n_confluences": len(cids), "n_tests": 4 * len(cids), "map": res,
               "sizes": {f"{l}_{s}": len(v[0]) for (l, s), v in sets.items()}},
              open(os.path.join(OUTD, "htf_map.json"), "w"), indent=1, default=float)
    if not quiet:
        print_map(res)
    return res


MIN_N = 8          # on-group size needed in each half (candidates) to call a confluence


def verdict(o):
    a, b, ta, tb = o["cand_H1"], o["cand_H2"], o["taken_H1"], o["taken_H2"]
    if None in (a["d_r"], b["d_r"]) or min(a["on"]["n"], b["on"]["n"], a["off"]["n"], b["off"]["n"]) < MIN_N:
        return "too few"
    sa, sb = np.sign(a["d_r"]), np.sign(b["d_r"])
    st = [np.sign(t["d_r"]) for t in (ta, tb) if t["d_r"] is not None]
    if sa == sb and abs(a["d_r"]) >= 0.2 and abs(b["d_r"]) >= 0.2 and all(x == sa for x in st):
        return "holds (+)" if sa > 0 else "holds (-)"
    if sa == sb and all(x == sa for x in st):
        return "same sign, small"
    return "flips"


def print_map(res):
    print(f"{'confluence':14s} {'family':14s} | H1 cand on/off n, avgR, dR, p | H2 cand ... | taken H1 dR p | taken H2 dR p | 21-25 dR | verdict")
    for c, o in res.items():
        def cc(k):
            x = o[k]
            return f"{x['on']['n']:3d}/{x['off']['n']:3d} {x['on'].get('avg_r', 0):+.2f} d{x['d_r'] if x['d_r'] is not None else 0:+.2f} p{x['p'] if x['p'] is not None else 1:.3f}"
        print(f"{c:14s} {o['family'][:14]:14s} | {cc('cand_H1')} | {cc('cand_H2')} | t {o['taken_H1']['d_r']} p{o['taken_H1']['p']} | "
              f"t {o['taken_H2']['d_r']} p{o['taken_H2']['p']} | {o['cand_2021-25']['d_r']} | {o['verdict']} fq {o['fisher_q']}")


# ================================================================================================ 2- and 3-way combinations
def combos(top=25, n_perm=1000, min_on=15):
    """AND combinations of 2 and 3 confluences, each in its H1-favourable orientation, picked on H1 candidates by the z of the
    mean-R difference (combo vs the rest). Family-wise correction: Westfall-Young max-z over every combination tried (labels
    shuffled n_perm times). The top combinations are checked on H2 (and 2021-25 for reference). Run twice: every confluence
    ("all") and HTF confluences only ("htf"). Chance line: the share of ALL H1-positive combinations that also 'hold' in H2."""
    R = rows()
    res = json.load(open(os.path.join(OUTD, "htf_map.json")))["map"]
    out_all = {}
    for fam in ("all", "htf"):
        cids = [c for c in CONF if c != "cx_against" and (fam == "all" or not c.startswith("lt_"))]
        out_all[fam] = _combos(R, res, cids, top, n_perm, min_on)
    json.dump(out_all, open(os.path.join(OUTD, "htf_combos.json"), "w"), indent=1, default=float)
    return out_all


def _combos(R, res, cids, top, n_perm, min_on):
    orient = {c: 1 if (res[c]["cand_H1"]["d_r"] is None or res[c]["cand_H1"]["d_r"] >= 0) else 0 for c in cids}

    def mat(s):
        a, z = S.SPAN[s]
        C = [r for r in R if a <= r["day"] <= z and r["u"] is not None]
        y = np.array([r["u"]["r1"] for r in C])
        X = np.array([[flag(r, c) for c in cids] for r in C])
        Xo = np.where(np.array([orient[c] for c in cids]) == 1, X, 1 - X)
        Xo[np.isnan(X)] = 0.0                                                     # unknown = not on
        usd = np.array([_usd_alone(r["u"]) for r in C])
        return y, Xo, usd
    y1, X1, u1 = mat("H1"); y2, X2, u2 = mat("H2"); y3, X3, u3 = mat("2021-25")
    K = len(cids)
    lits = [f"{c}" if orient[c] else f"NOT {c}" for c in cids]
    combs = list(itertools.combinations(range(K), 2)) + list(itertools.combinations(range(K), 3))
    is2 = np.array([len(c) == 2 for c in combs])

    def cmat(X):
        out = np.empty((X.shape[0], len(combs)), np.float32)
        for j, cb in enumerate(combs):
            out[:, j] = np.prod(X[:, list(cb)], axis=1)
        return out
    Z1, Z2, Z3 = cmat(X1), cmat(X2), cmat(X3)
    n1 = Z1.sum(0)
    valid = (n1 >= min_on) & (len(y1) - n1 >= min_on)
    sd = y1.std()

    def zstat(y, Zm, nn):
        s1 = y @ Zm
        m1 = s1 / np.maximum(nn, 1); m0 = (y.sum() - s1) / np.maximum(len(y) - nn, 1)
        return (m1 - m0) / (sd * np.sqrt(1 / np.maximum(nn, 1) + 1 / np.maximum(len(y) - nn, 1)))
    z_obs = np.where(valid, zstat(y1, Z1, n1), -np.inf)
    rng = np.random.default_rng(21)
    mx = np.empty(n_perm)
    Zv, nv = Z1[:, valid], n1[valid]
    for q in range(n_perm):
        mx[q] = zstat(rng.permutation(y1), Zv, nv).max()
    # H2 for every combination (chance line)
    n2 = Z2.sum(0)
    s2 = y2 @ Z2
    d2 = s2 / np.maximum(n2, 1) - (y2.sum() - s2) / np.maximum(len(y2) - n2, 1)
    pos1 = valid & (z_obs > 0)
    ev2 = pos1 & (n2 >= MIN_N) & (len(y2) - n2 >= MIN_N)
    chance = round(100 * float((d2[ev2] >= 0.2).mean()), 1) if ev2.any() else None

    def st(y, Zc, usd, j):
        m = Zc[:, j] == 1
        if not m.any():
            return {"n": 0}
        return {"n": int(m.sum()), "win": round(100 * float((y[m] > 0.5).mean()), 1), "avg_r": round(float(y[m].mean()), 3),
                "rest_r": round(float(y[~m].mean()), 3), "d_r": round(float(y[m].mean() - y[~m].mean()), 3),
                "usd": round(float(usd[m].sum()))}

    def rows_of(order):
        out = []
        for j in order:
            cb = combs[j]
            h2 = st(y2, Z2, u2, j)
            p2 = _perm_p(y2, (Z2[:, j] == 1).astype(float)) if h2["n"] >= 3 and len(y2) - h2["n"] >= 3 else None
            out.append({"combo": " AND ".join(lits[i] for i in cb), "ids": [cids[i] for i in cb],
                        "neg": [1 - orient[cids[i]] for i in cb], "z_h1": round(float(z_obs[j]), 2),
                        "p_fwer_h1": round(float((mx >= z_obs[j]).mean()), 4), "H1": st(y1, Z1, u1, j), "H2": {**h2, "p": p2},
                        "2021-25": st(y3, Z3, u3, j), "holds_h2": bool(h2["n"] >= MIN_N and h2.get("d_r", -9) >= 0.2)})
        return out
    top_all = rows_of(np.argsort(-z_obs)[:top])
    top_pairs = rows_of(np.argsort(-np.where(is2, z_obs, -np.inf))[:12])
    info = {"literals": lits, "n_literals": K, "n_combos_2": int(is2.sum()), "n_combos_3": int((~is2).sum()),
            "n_valid_h1": int(valid.sum()), "min_on": min_on, "n_perm": n_perm,
            "max_z_null_p95": round(float(np.quantile(mx, 0.95)), 2),
            "chance_hold_pct": chance, "n_chance_pool": int(ev2.sum()),
            "top_holds": sum(o["holds_h2"] for o in top_all), "top_eligible": sum(o["H2"]["n"] >= MIN_N for o in top_all),
            "top": top_all, "top_pairs": top_pairs}
    print(f"\n[{'all' if any(c.startswith('lt_') for c in cids) else 'htf'}] {K} literals: tried {info['n_combos_2']} pairs + "
          f"{info['n_combos_3']} triples ({info['n_valid_h1']} with >= {min_on} setups on each side in H1); null 95% of max z = "
          f"{info['max_z_null_p95']}; chance that an H1-positive combo holds in H2: {chance}% (pool {info['n_chance_pool']}); "
          f"top {top}: {info['top_holds']} hold of {info['top_eligible']} with H2 n >= {MIN_N}")
    for lab, L in (("top", top_all), ("pairs", top_pairs)):
        print(" --", lab)
        for o in L:
            print(f"  z {o['z_h1']:5.2f} fwer p {o['p_fwer_h1']:.3f} | H1 n {o['H1']['n']} avgR {o['H1']['avg_r']:+.2f} (rest "
                  f"{o['H1']['rest_r']:+.2f}) | H2 n {o['H2']['n']} avgR {o['H2'].get('avg_r')} d {o['H2'].get('d_r')} p "
                  f"{o['H2']['p']} | 21-25 n {o['2021-25']['n']} d {o['2021-25'].get('d_r')} | {'HOLDS' if o['holds_h2'] else '-'} | "
                  f"{o['combo']}")
    return info


# ================================================================================================ rules on the real LIT path
def run_spec(spec):
    R = rows()
    from tools import lit_select_rules as SR
    o, U = SR.run_rule(R, spec)
    for s in o:
        p10 = o[s].get("p10") or 0
        o[s]["cost_2wk"] = round(PRICE / (p10 / 100)) if p10 else None
    return o, U


def _on(cid, neg=False):
    def fn(r):
        v = flag(r, cid)
        if np.isnan(v):
            return None
        return (1 - v) if neg else v
    return fn


def _all(fns):
    def fn(r):
        vs = [f(r) for f in fns]
        if any(v is None for v in vs):
            return None
        return float(all(v == 1 for v in vs))
    return fn


def specs_for(name, fn, htf=True):
    """The three ways of turning a confluence (fn(row) -> 1 good / 0 / None unknown) into a rule."""
    V = collections.OrderedDict()
    V[f"{name}: skip without"] = dict(skip=lambda r: fn(r) == 0)
    V[f"{name}: 1.25x with, 0.75x without"] = dict(size=lambda r: 1.25 if fn(r) == 1 else 0.75 if fn(r) == 0 else 1.0)
    if htf:
        V[f"{name}: London setups only when aligned"] = dict(skip=lambda r: r["f"]["mod"] < 480 and fn(r) == 0)
    return V


def shortlist():
    """Survivors of the map (hold in both halves on candidates and taken trades) + the combos that held on H2."""
    res = json.load(open(os.path.join(OUTD, "htf_map.json")))["map"]
    out = collections.OrderedDict()
    for c, o in res.items():
        if o["verdict"].startswith("holds"):
            neg = o["verdict"] == "holds (-)"
            out[("NOT " if neg else "") + c] = (_on(c, neg), not c.startswith("lt_"), o)
    try:
        J = json.load(open(os.path.join(OUTD, "htf_combos.json")))
        cb, seen = [], set()
        for fam in ("all", "htf"):
            for o in J[fam]["top"] + J[fam]["top_pairs"]:
                if o["combo"] not in seen:
                    seen.add(o["combo"]); cb.append(o)
    except FileNotFoundError:
        cb = []
    for o in cb:
        if o["holds_h2"]:
            fns = [_on(c, bool(n)) for c, n in zip(o["ids"], o["neg"])]
            out[o["combo"]] = (_all(fns), any(not c.startswith("lt_") for c in o["ids"]), o)
    return out


def rules(only=None):
    base_o, base_U = run_spec({})
    print("BASE")
    for s in ("H1", "H2", "2021-25"):
        print("  " + S.line(base_o, s), "| cost/2wk pass", base_o[s]["cost_2wk"], "| funded", base_o[s]["funded_net"])
    SL = shortlist()
    extra = extra_rules()
    out = collections.OrderedDict(base={"o": _compact(base_o)})
    todo = []
    for nm, (fn, htf, info) in SL.items():
        todo += list(specs_for(nm, fn, htf).items())
    todo += list(extra.items())
    for nm, spec in todo:
        if only and only not in nm:
            continue
        o, U = run_spec(spec)
        out[nm] = {"o": _compact(o)}
        print(f"\n{nm}")
        for s in ("H1", "H2", "2021-25"):
            print("  " + S.line(o, s), f"| cost/2wk {o[s]['cost_2wk']} | funded {o[s]['funded_net']:+,} "
                  f"(d {o[s]['funded_net'] - base_o[s]['funded_net']:+,}) | d net {o[s]['net'] - base_o[s]['net']:+,}", flush=True)
    json.dump(out, open(os.path.join(OUTD, "htf_rules.json"), "w"), indent=1, default=float)
    return out


def extra_rules():
    """The owner's named HTF rules, scored even when the map does not back them (so the write-up can show them)."""
    V = collections.OrderedDict()
    V["WITH the HTF draw (composite >= 2): London setups only when aligned"] = \
        dict(skip=lambda r: r["f"]["mod"] < 480 and _cx(r["h"], 2) == 0)
    V["WITH the HTF draw (composite >= 2): skip without"] = dict(skip=lambda r: _cx(r["h"], 2) == 0)
    V["WITH the HTF draw (composite >= 2): 1.25x / 0.75x"] = dict(size=lambda r: 1.25 if _cx(r["h"], 2) == 1 else 0.75)
    V["AGAINST the HTF draw (composite 0): skip"] = dict(skip=lambda r: _cx(r["h"], 0, exact=True) == 1)
    return V


def _compact(o):
    keys = ("n", "tpw", "wk2", "win", "pf", "net", "per_month", "dd", "p10", "f10", "dec10", "p15", "f15", "p20", "f20",
            "pass_rate", "pass_med", "slow_pass", "b2b", "cost_2wk", "funded_net", "funded_pf", "funded_dd", "w_r")
    return {s: {k: o[s].get(k) for k in keys} for s in o}


# ================================================================================================ follow-ups (post-hoc, marked as such)
def fvg_way_variants(ages_days=(2, 5, 10), tfs=("1h", "4h")):
    """Robustness of 'an unfilled opposing HTF FVG between entry and target' to the FVG memory: recompute it per candidate
    for each time frame and memory (5m bars = days x 276). Cached."""
    p = os.path.join(CACHE, f"lithtf_fvgvar_{VER}_{rl._data_key().replace(':', '_')}.pkl")
    if os.path.exists(p):
        return pickle.load(open(p, "rb"))
    R = S.build()["rows"]
    M, Cx = market()
    H = HTF(M)
    out = collections.defaultdict(dict)
    for tf in tfs:
        for dd in ages_days:
            H._fvgs(tf, dd * 276)
            for r in R:
                z = Cx[r["key"]]
                pl = S.plan_of(M, z)
                out[r["key"]][f"fv_way{tf}_{dd}d"] = float(H._fvg_way(tf, int(z["i"]), int(z["dir"]), pl["ep"], pl["tp"]))
    out = dict(out)
    pickle.dump(out, open(p, "wb"))
    return out


def pool_variants(ages_days=(10, 20, 40)):
    """Robustness of the 4H draw (nearest unswept 4H swing on the target side) to the swing memory. Cached."""
    p = os.path.join(CACHE, f"lithtf_poolvar_{VER}_{rl._data_key().replace(':', '_')}.pkl")
    if os.path.exists(p):
        return pickle.load(open(p, "rb"))
    R = S.build()["rows"]
    M, Cx = market()
    H = HTF(M)
    out = collections.defaultdict(dict)
    for dd in ages_days:
        H._pools("4h", dd * 276, 60)
        for r in R:
            z = Cx[r["key"]]
            out[r["key"]][f"pl_sw4h_{dd}d"] = H._pool_draw("4h", "swing", int(z["i"]), int(z["dir"]), float(M.c[int(z["i"])]))
    out = dict(out)
    pickle.dump(out, open(p, "wb"))
    return out


def _tilt(fn, up=1.25, dn=0.75):
    return lambda r: up if fn(r) == 1 else dn if fn(r) == 0 else 1.0


def followup_specs():
    R = rows()
    V = fvg_way_variants()
    for r in R:
        r["h"].update(V[r["key"]])
    clear1h = _on("fv_way1h", True)
    clear_lv = _on("dr_reach", True)
    trap = lambda r: float(r["f"]["idm_age"] <= 6)
    n_obst = lambda r: int(r["h"]["fv_way1h"] == 1) + int(r["h"]["dr_reach"] == 1)
    T = collections.OrderedDict()
    T["[post-hoc] clear path: no 1H FVG and no untaken HTF level between entry and target: 1.25x / 0.75x"] = \
        dict(size=_tilt(lambda r: float(n_obst(r) == 0)))
    T["[post-hoc] obstacles graded: 0 -> 1.25x, 1 -> 1x, 2 -> 0.75x"] = dict(size=lambda r: {0: 1.25, 1: 1.0, 2: 0.75}[n_obst(r)])
    T["[post-hoc] no 1H or 4H opposing FVG in the way: 1.25x / 0.75x"] = \
        dict(size=_tilt(lambda r: float(r["h"]["fv_way1h"] == 0 and r["h"]["fv_way4h"] == 0)))
    for up, dn in ((1.15, 0.85), (1.5, 0.5), (1.25, 1.0), (1.0, 0.75)):
        T[f"[neighbour] NOT fv_way1h: {up:g}x / {dn:g}x"] = dict(size=_tilt(clear1h, up, dn))
    for tf in ("1h", "4h"):
        for dd in (2, 5, 10):
            k = f"fv_way{tf}_{dd}d"
            T[f"[memory] no opposing {tf.upper()} FVG ({dd}-day memory) in the way: 1.25x / 0.75x"] = \
                dict(size=_tilt(lambda r, k=k: 1.0 - r["h"][k]))
    T["[stack] fresh trap tilt x clear 1H path tilt (one rounding, $900 cap)"] = \
        dict(size=lambda r: _tilt(trap)(r) * _tilt(clear1h)(r))
    T["[stack] fresh trap tilt x clear HTF-level path tilt"] = dict(size=lambda r: _tilt(trap)(r) * _tilt(clear_lv)(r))
    draw4 = _on("pl_sw4h")
    T["[post-hoc] 4H draw size-neutral: 1.4x when the nearest unswept 4H swing is on the target side, else 0.8x"] = \
        dict(size=_tilt(draw4, 1.4, 0.8))
    T["[post-hoc] 4H draw: 1.25x / 0.85x"] = dict(size=_tilt(draw4, 1.25, 0.85))
    PV_ = pool_variants()
    for r in R:
        r["h"].update(PV_[r["key"]])
    for dd in (10, 40):
        k = f"pl_sw4h_{dd}d"
        T[f"[memory] 4H draw size-neutral 1.4x / 0.8x, {dd}-day 4H swing memory"] = \
            dict(size=_tilt(lambda r, k=k: r["h"][k] if not np.isnan(r["h"][k]) else None, 1.4, 0.8))
    T["[post-hoc] 4H draw: 1.5x / 0.75x"] = dict(size=_tilt(draw4, 1.5, 0.75))
    T["[stack] fresh trap tilt x 4H draw tilt (1.25 / 0.75 each)"] = dict(size=lambda r: _tilt(trap)(r) * _tilt(draw4)(r))
    T["[reference] fresh trap only (lit_sel_trap6_size)"] = dict(size=_tilt(trap))
    return T


def followups():
    T = followup_specs()
    base_o, _ = run_spec({})
    out = collections.OrderedDict(base={"o": _compact(base_o)})
    for nm, spec in T.items():
        o, U = run_spec(spec)
        out[nm] = {"o": _compact(o)}
        print(f"\n{nm}")
        for s_ in ("H1", "H2", "2021-25"):
            print("  " + S.line(o, s_), f"| cost/2wk {o[s_]['cost_2wk']} | funded {o[s_]['funded_net']:+,} "
                  f"(d {o[s_]['funded_net'] - base_o[s_]['funded_net']:+,}) | d net {o[s_]['net'] - base_o[s_]['net']:+,}", flush=True)
    json.dump(out, open(os.path.join(OUTD, "htf_followups.json"), "w"), indent=1, default=float)
    return T


# ================================================================================================ finalists, shuffle test, runs
FINAL = collections.OrderedDict([
    # name in rules() / followups()                                          (run id suffix, status)
    ("NOT fv_way1h: 1.25x with, 0.75x without", ("clear1h_size", "promising")),
    ("NOT dr_reach: 1.25x with, 0.75x without", ("clearlv_size", "promising")),
    ("[stack] fresh trap tilt x clear HTF-level path tilt", ("trap_x_clearlv", "adopt-candidate")),
    ("[stack] fresh trap tilt x clear 1H path tilt (one rounding, $900 cap)", ("trap_x_clear1h", "promising")),
    ("[post-hoc] clear path: no 1H FVG and no untaken HTF level between entry and target: 1.25x / 0.75x", ("clearpath_size", "promising")),
    ("[post-hoc] 4H draw size-neutral: 1.4x when the nearest unswept 4H swing is on the target side, else 0.8x", ("draw4h_neutral", "promising")),
    ("[stack] fresh trap tilt x 4H draw tilt (1.25 / 0.75 each)", ("trap_x_draw4h", "promising")),
    ("WITH the HTF draw (composite >= 2): London setups only when aligned", ("with_draw_london", "rejected")),
    ("WITH the HTF draw (composite >= 2): 1.25x / 0.75x", ("with_draw_size", "rejected")),
    ("pl_sw4h: 1.25x with, 0.75x without", ("draw4h_size", "rejected")),
    ("pl_sw4h: London setups only when aligned", ("draw4h_london", "rejected")),
    ("bi_pdbos: London setups only when aligned", ("pdbos_london", "rejected")),
    ("NOT dr_reach: London setups only when aligned", ("clearlv_london", "rejected")),
    ("AGAINST the HTF draw (composite 0): skip", ("against_skip", "rejected")),
])


def finalists(names=None, save=False, statuses=None):
    """names: rule names as printed by rules(); scores them, runs the size shuffle test, optionally stores runs lit_htf_*."""
    from tools import lit_select_rules as SR
    SL = shortlist()
    allspecs = collections.OrderedDict()
    for nm, (fn, htf, info) in SL.items():
        allspecs.update(specs_for(nm, fn, htf))
    allspecs.update(extra_rules())
    allspecs.update(followup_specs())
    base_o, _ = run_spec({})
    out = {}
    for nm in names or FINAL:
        spec = allspecs[nm]
        o, U = run_spec(spec)
        pm = SR._perm(rows(), U) if spec.get("size") else None
        rid = "lit_htf_" + FINAL[nm][0] if nm in FINAL else None
        out[nm] = {"id": rid, "o": _compact(o), "perm": pm}
        print(nm, "| shuffle", pm, flush=True)
        if save and rid:
            _save(rid, nm, spec, FINAL[nm][1], o, base_o, pm)
    json.dump(out, open(os.path.join(OUTD, "htf_final.json"), "w"), indent=1, default=float)
    return out


def _save(rid, title, spec, status, o, b, pm):
    R = rows()
    U = S.replay(R, skip=spec.get("skip"), size=spec.get("size"))
    T = S.evals_x(U, "2026")[1] + S.evals_x(U, "2021-25")[1]
    T = [{k: v for k, v in t.items() if k not in ("legs", "_row")} for t in T]
    Sc = rl.score(T, S.SESS)

    def h(s):
        x = o[s]
        return (f"n={x['n']} {x['tpw']}/wk win {x['win']}% PF {x['pf']} net {x['net']:+,} (${x['per_month']:,}/mo) DD {x['dd']:,}; "
                f"eval 2wk {x['p10']}/{x['f10']} (cost per 2-week pass ${x['cost_2wk']}), 3wk {x['p15']}/{x['f15']}, 1mo "
                f"{x['p20']}/{x['f20']}, pass rate {x['pass_rate']}%, median {x['pass_med']} sessions; same trades at $800/25 without "
                f"the room cap {x['funded_net']:+,} (base {b[s]['funded_net']:+,})")
    verdict = (f"2026 H1 (pick) {h('H1')}. 2026 H2 (check) {h('H2')}. 2021-25 reference only {h('2021-25')}. Base (LIT live, eval "
               f"sizing) H1 {b['H1']['net']:+,} 2wk {b['H1']['p10']}/{b['H1']['f10']} / H2 {b['H2']['net']:+,} 2wk "
               f"{b['H2']['p10']}/{b['H2']['f10']}." + (f" Shuffle test p H1 {pm['H1']['p']} / H2 {pm['H2']['p']}." if pm else ""))
    rl.save(rid, title, "other", "Owner order 2026-10-18: higher time frame stuff, look at all confluences, deep dive it (HTF "
            "draw on liquidity, dealing range, PO3, bias, structure, HTF FVGs, time of week).",
            params={**S.LIVE, "size": list(S.EVAL_RULE), "room_k": S.ROOM_K, "risk_cap_sized_up": S.RISK_CAP, "rule": title},
            trades=T, scored=Sc, status=status, verdict=verdict,
            notes="tools/lit_htf.py (wraps tools/lit_select.py, engine/lit.py, tools/lit_tightstop.py; none edited). HTF bars built "
                  "from the CME NQ1! 5m file, causal at the trigger bar (lookahead test). Eval sizing $800 up to 25 pts + 60% room "
                  "cap + weekly stop; $ and DD from back-to-back MFFU 50K evals, eval odds from a fresh eval on every session; cost "
                  "per 2-week pass = $91.80 / p10.", writeup="lit-htf-confluences", tags=["lit", "lit_htf"])
    print("  saved", rid)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "map"
    if cmd == "build":
        print(len(build(force=True)))
    elif cmd == "lookahead":
        lookahead(int(sys.argv[2]) if len(sys.argv) > 2 else 10)
    elif cmd == "map":
        map_()
    elif cmd == "combos":
        combos()
    elif cmd == "final":
        finalists(save=False)
    elif cmd == "save":
        finalists(save=True)
    elif cmd == "followups":
        followups()
    elif cmd == "rules":
        rules(sys.argv[2] if len(sys.argv) > 2 else None)
    else:
        raise SystemExit(f"unknown command {cmd}")
