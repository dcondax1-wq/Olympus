"""LIT entry-model research (owner order 2026-10-18: LIT is the strategy, tuned and judged on 2026 only).

Dimension: ENTRY MODELS. lit_A sessions, levels, filters and targets stay fixed; only the way the trade is entered changes:
  * entry price on the 5m setup: market / retest of the broken swing (lit_A) / FVG edge or 50% / order block open or 50% /
    CISD level / breaker / fib retrace;
  * structure-shift definition: last 5m fractal (lit_A) / 5m CISD / the leg's swing high / a 15m swing;
  * inducement definitions: I-a pre-sweep untouched IDM near the level, I-c POI-side IDM taken before the fill, I-d
    build-up swept together with another level;
  * 1m in 2026: the same limit filled and managed on 1m bars, and a 1m CISD confirmation inside the POI.
The stop is always beyond the 5m sweep extreme (CLAUDE.md hard rule); size $800 up to a 20-pt stop then 800x20/stop.

engine/lit.py is imported, never edited. New pieces are named lit_entry-specific (gen_cands, zones, Bars1, sim, run_v) so the
combine step can merge them.

  python tools/lit_entry.py check          # gen_cands(ref='frac') + run_v reproduce lit_A exactly
  python tools/lit_entry.py search         # every variant -> research/lab/lit_entry_results.json
  python tools/lit_entry.py save           # store the best 5 (ids lit_entry_*) with rl.save
Overfitting guard: pick on 2026 H1 (Jan-Jun), check on 2026 H2 (Jul-Oct 16); 2021-25 is a reference line only.
1 CPU process only.
"""
from __future__ import annotations

import bisect
import collections
import json
import os
import pickle
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import lit  # noqa: E402
from engine.analytics import PLANS, simulate_eval  # noqa: E402
from engine.data import load_ltf, load, resample  # noqa: E402
from tools import research_lit as R  # noqa: E402
from tools import runlib as rl  # noqa: E402

TICK, PV, COMM, SLIP = lit.TICK, lit.PV, lit.COMM, lit.SLIP
CACHE = os.path.join(ROOT, "research", "runs", "_cache")
OUT = os.path.join(ROOT, "research", "lab", "lit_entry_results.json")
SESS = R.SESS
H1 = ("2026-01-01", "2026-06-30")
H2 = ("2026-07-01", "2026-12-31")
LIT_A = dict(R.CAND["A"])          # day 02:00-15:30, all liquidity, entry ref, disp>=1 ATR, depth>=0.5 ATR, PD/PW/PM targets


# ------------------------------------------------------------------------------------------------ candidates (5m)
def _cisd_level(c_d, o_d, ee, back=3):
    """CISD (TTrades): open of the first bar of the last unbroken run of down-close bars into the extreme (direction space).
    Returns (level, first_bar) or None."""
    j = ee
    while j > ee - back and not (c_d[j] < o_d[j]):
        j -= 1
    if not (c_d[j] < o_d[j]):
        return None
    st = j
    while st - 1 >= 0 and c_d[st - 1] < o_d[st - 1] and st > ee - 30:
        st -= 1
    return float(o_d[st]), st


def gen_cands(M: lit.Market, ref="frac", leg=24, sweep_win=24, ref_back=36, ind_back=36, t_from=60, t_to=955, f15=None):
    """lit.candidates() with a pluggable structure-shift swing (ref):
       frac  = last confirmed 5m k=2 fractal high before the extreme (lit_A, identical output)
       cisd  = open of the last run of down-close bars into the extreme (TTrades CISD)
       leg   = the highest fractal high in the ref_back bars before the extreme (the swing that started the leg)
       frac15= the last 15m k=2 fractal high before the extreme, broken by a 15m close (5m bar that closes the 15m bar)
    Adds per candidate: idm_a (pre-sweep IDM list [(dist_atr, age_bars)]), zone prices for every entry model (direction space)."""
    o, h, l, c, mod, at = M.o, M.h, M.l, M.c, M.mod, M.atr
    out = []
    for k, (date, s, e) in enumerate(M.days):
        x = M.ctx[k]
        if "pdh" not in x or e - s < 50:
            continue
        L = M.levels(k)
        for d in (1, -1):
            if d == 1:
                hi_d, lo_d, c_d, o_d = h, l, c, o
                swing_hi, swing_lo = M.fh, M.fl
                f15i = f15["fh"] if f15 else None
            else:
                hi_d, lo_d, c_d, o_d = -l, -h, -c, -o
                swing_hi, swing_lo = M.fl, M.fh
                f15i = f15["fl"] if f15 else None
            liq = [(px * d, ki, nm, cls) for side, px, ki, nm, cls in L if (side == "low") == (d == 1)]
            tgt = [(px * d, ki, nm, cls) for side, px, ki, nm, cls in L if (side == "high") == (d == 1)]
            seg_end = e
            fb = [lit._first_breach(lo_d, max(ki, s - 600), seg_end, p) for p, ki, nm, cls in liq]
            tb = []
            for p, ki, nm, cls in tgt:
                st = max(ki, s - 600)
                seg = hi_d[st + 1:seg_end] >= p
                j = int(np.argmax(seg)) if len(seg) else 0
                tb.append(st + 1 + j if len(seg) and seg[j] else seg_end)
            last_e = -1
            for i in range(s + leg, e - 1):
                if not (t_from <= mod[i] < t_to) or mod[i] >= 1080:
                    continue
                a = i - leg
                ee = a + int(np.argmin(lo_d[a:i + 1]))
                if ee == i or ee == last_e:
                    continue
                # ---- structure-shift swing
                if ref == "frac":
                    jj = bisect.bisect_left(swing_hi, ee) - 1
                    if jj < 0 or swing_hi[jj] < ee - ref_back:
                        continue
                    j = int(swing_hi[jj]); rp = float(hi_d[j])
                elif ref == "leg":
                    a0 = bisect.bisect_left(swing_hi, ee - ref_back); a1 = bisect.bisect_left(swing_hi, ee)
                    if a1 <= a0:
                        continue
                    cand_j = swing_hi[a0:a1]
                    j = int(cand_j[int(np.argmax(hi_d[cand_j]))]); rp = float(hi_d[j])
                elif ref == "cisd":
                    cz = _cisd_level(c_d, o_d, ee)
                    if cz is None:
                        continue
                    rp, j = cz
                elif ref == "frac15":
                    # 15m fractal swing bars (5m index of the 15m bar's last 5m bar), confirmed 2 15m bars later
                    arr = f15i
                    jj = bisect.bisect_left(arr["bar"], ee) - 1
                    if jj < 0 or arr["bar"][jj] < ee - 3 * ref_back // 2:
                        continue
                    j = int(arr["bar"][jj]); rp = float(arr["px"][jj] * d)
                    if arr["known"][jj] > i:
                        continue
                    if not M.is15[i]:
                        continue
                else:
                    raise ValueError(ref)
                if ref == "frac15":
                    closes = c_d[ee:i][M.is15[ee:i]]
                    if not (c_d[i] > rp and (closes.max() if len(closes) else -np.inf) <= rp):
                        continue
                elif not (c_d[i] > rp and c_d[ee:i].max() <= rp):
                    continue
                ext = float(lo_d[ee])
                swept = [(liq[q], fb[q]) for q in range(len(liq)) if liq[q][1] < ee and ee - sweep_win <= fb[q] <= ee and ext < liq[q][0]]
                if not swept:
                    continue
                last_e = ee
                sb = min(z[1] for z in swept)
                lev_near = max(z[0][0] for z in swept)
                ind_n = 0
                lo_i = bisect.bisect_left(swing_lo, sb - ind_back)
                for m in swing_lo[lo_i:bisect.bisect_left(swing_lo, sb)]:
                    m = int(m)
                    if m + 2 <= sb and lo_d[m] > lev_near and lo_d[m + 1:sb + 1].min() < lo_d[m]:
                        ind_n += 1
                # I-a: fractal lows above the swept level, untouched until the final run (from the leg's swing high to the
                # extreme) takes them -> (distance above the level in ATR, age in bars before the sweep)
                idm_a = []
                leg_top = int(ee - np.argmax(hi_d[max(ee - ref_back, s - 600):ee + 1][::-1])) if ee > s else ee
                lo_i2 = bisect.bisect_left(swing_lo, sb - 72)
                for m in swing_lo[lo_i2:bisect.bisect_left(swing_lo, ee)]:
                    m = int(m)
                    if lo_d[m] <= lev_near:
                        continue
                    seg = lo_d[m + 1:ee + 1] < lo_d[m]
                    if not seg.any():
                        continue
                    tk = m + 1 + int(np.argmax(seg))
                    if tk < max(leg_top, m + 3) or tk > ee:
                        continue
                    idm_a.append((round((lo_d[m] - lev_near) / max(at[sb], 1e-9), 3), int(sb - m)))
                body = (c_d[ee:i + 1] - o_d[ee:i + 1]) / np.maximum(at[ee:i + 1], 1e-9)
                dir_bull = (c_d[ee + 1:i + 1] > o_d[ee + 1:i + 1])
                vec = bool((M.climax[ee + 1:i + 1] & dir_bull).any())
                vec_any = bool(((M.climax[ee + 1:i + 1] | M.above[ee + 1:i + 1]) & dir_bull).any())
                ei = i + 1
                if ei >= e or mod[ei] >= 955 or mod[ei] >= 1080:
                    continue
                entry_d = float(o_d[ei]) + SLIP
                T = collections.defaultdict(list)
                for q, (p, ki, nm, cls) in enumerate(tgt):
                    if ki <= i and tb[q] > i and p > entry_d:
                        T[cls].append(round(p - entry_d, 2))
                for cls in T:
                    T[cls].sort()
                po3 = {}
                for nm, arr in (("1h", M.open_1h), ("4h", M.open_4h), ("d", M.open_d), ("00", M.open_00), ("830", M.open_830),
                                ("930", M.open_930), ("wk", M.open_wk), ("22", M.open_22)):
                    ov = arr[i]
                    po3[nm] = None if np.isnan(ov) else (int(ext < ov * d), int(entry_d - SLIP < ov * d))
                vm = x.get("vix_move"); xm = x.get("vxn_move")
                op = x["open18"] * d
                ws = int(np.searchsorted(M.week_id[:ee + 1], M.week_id[ee]))
                z = {
                    "day": str(date), "k": k, "dir": d, "i": int(i), "ext_i": int(ee), "ref_i": int(j), "entry_i": ei, "sweep_i": int(sb),
                    "entry_t": int(M.t[ei]), "entry_d": entry_d, "ext_d": ext, "ref_d": rp, "trig_c": float(c_d[i]), "mod": int(mod[ei]),
                    "swept": sorted({zz[0][2] for zz in swept}), "swept_cls": sorted({zz[0][3] for zz in swept}),
                    "depth_atr": round((lev_near - ext) / max(at[ee], 1e-9), 3), "ind_n": ind_n, "idm_a": idm_a,
                    "disp": round(float(body[1:].max()) if len(body) > 1 else 0.0, 3), "vec": vec, "vec_any": vec_any,
                    "vec_sweep": bool(M.climax[ee]), "bars": int(i - ee), "atr": round(float(at[i]), 2),
                    "targets": dict(T), "po3": po3,
                    "vix_ext": round((op - ext) / vm, 3) if vm else None, "vxn_ext": round((op - ext) / xm, 3) if xm else None,
                    "vix_room": round((op + vm - entry_d), 2) if vm else None,
                    "how": bool(M.how[ee]), "wk_ext": bool(lo_d[ee] <= lo_d[ws:ee + 1].min()), "dow": x["dow"],
                }
                z["zones"] = zones(M, z, hi_d, lo_d, c_d, o_d)
                out.append(z)
    out.sort(key=lambda z: (z["entry_t"], -z["dir"]))
    return out


def zones(M, z, hi_d, lo_d, c_d, o_d):
    """Entry-zone prices (direction space) known at the trigger close:
      fvg_*: bullish FVGs inside the displacement leg (bar k low above bar k-2 high), not fully filled by the trigger close;
             top = near edge, ce = 50% (consequent encroachment); first / last / biggest gap
      ob_*:  order block = the last down-close bar at or before the biggest displacement body (not before ext-6):
             ob_open = its open (top of the body), ob_50 = 50% of its range
      cisd:  open of the last run of down-close bars into the extreme
      brk_*: breaker = the last up-close bar at or before the broken swing (ref_i): high / 50% of its range"""
    ee, i, at = z["ext_i"], z["i"], max(M.atr[z["i"]], 1e-9)
    Z = {"ref": z["ref_d"]}
    fv = []
    for k in range(ee + 1, i + 1):
        top, bot = lo_d[k], hi_d[k - 2]
        if top > bot:
            if k < i and lo_d[k + 1:i + 1].min() <= bot:
                continue
            fv.append((k, float(top), float(bot), (top - bot) / at))
    if fv:
        for nm, g in (("first", fv[0]), ("last", fv[-1]), ("big", max(fv, key=lambda q: q[3]))):
            Z[f"fvg_top_{nm}"] = g[1]; Z[f"fvg_ce_{nm}"] = (g[1] + g[2]) / 2; Z[f"fvg_sz_{nm}"] = round(g[3], 3)
    body = c_d[ee:i + 1] - o_d[ee:i + 1]
    kb = ee + int(np.argmax(body))
    ob = None
    for j in range(kb, max(ee - 6, 0) - 1, -1):
        if c_d[j] < o_d[j]:
            ob = j; break
    if ob is not None:
        Z["ob_open"] = float(o_d[ob]); Z["ob_50"] = float((hi_d[ob] + lo_d[ob]) / 2)
    cz = _cisd_level(c_d, o_d, ee)
    if cz is not None:
        Z["cisd"] = cz[0]
    r = z["ref_i"]
    for j in range(r, max(r - 4, 0) - 1, -1):
        if c_d[j] > o_d[j]:
            Z["brk_high"] = float(hi_d[j]); Z["brk_50"] = float((hi_d[j] + lo_d[j]) / 2); break
    cl, ext = z["trig_c"], z["ext_d"]
    for nm, f in (("fib50", 0.5), ("fib62", 0.618)):
        Z[nm] = cl - f * (cl - ext)
    return Z


def f15_swings(M):
    """15m k=2 fractals from the 5m bars, mapped to 5m indices: bar = last 5m bar of the swing's 15m candle, known = last 5m
    bar of the 15m candle that confirms it (2 candles later). Also M.is15 = this 5m bar closes a 15m candle."""
    b = M.b
    bk = (b.t // 900)
    last = np.r_[bk[1:] != bk[:-1], True]
    M.is15 = last
    idx = np.flatnonzero(last)
    st = np.r_[0, idx[:-1] + 1]
    H = np.array([M.h[a:z + 1].max() for a, z in zip(st, idx)]); Lw = np.array([M.l[a:z + 1].min() for a, z in zip(st, idx)])
    fh, fl = lit.fractals(H, Lw)
    out = {}
    for nm, ff, arr in (("fh", fh, H), ("fl", fl, Lw)):
        ff = ff[ff + 2 < len(idx)]
        out[nm] = {"bar": idx[ff], "px": arr[ff], "known": idx[ff + 2]}
    return out


def market(ref="frac", **kw):
    key = f"litentry_{ref}_{json.dumps(kw, sort_keys=True)}_{rl._data_key()}".replace(" ", "")
    p = os.path.join(CACHE, "".join(ch for ch in key if ch.isalnum() or ch in "_-.") + ".pkl")
    M = lit.Market()
    f15 = f15_swings(M)
    if os.path.exists(p):
        C = pickle.load(open(p, "rb"))
    else:
        C = gen_cands(M, ref=ref, f15=f15, **kw)
        os.makedirs(CACHE, exist_ok=True)
        pickle.dump(C, open(p, "wb"))
    return M, C


# ------------------------------------------------------------------------------------------------ bars for the executor
class Bars1:
    """Executor bars (5m from the Market, or true 1m for 2026), with direction-space views and fractal lows/highs."""

    def __init__(self, t, o, h, l, c, mod, day, secs):
        self.t, self.o, self.h, self.l, self.c, self.mod, self.day, self.secs = t, o, h, l, c, mod, np.asarray(day), secs
        self.n = len(t)
        self.fh, self.fl = lit.fractals(h, l)
        self._d = {1: (h, l, c, o), -1: (-l, -h, -c, -o)}

    def dirs(self, d):
        return self._d[d]

    @classmethod
    def from_market(cls, M):
        return cls(M.t, M.o, M.h, M.l, M.c, M.mod, M.day_of, 300)

    @classmethod
    def one_minute(cls, M):
        b, _ = load_ltf("NQ", M.b)
        dmap = {d: k for k, (d, s, e) in enumerate(M.days)}
        day = np.array([dmap.get(x, -1) for x in b.date_str])
        return cls(b.t, b.o, b.h, b.l, b.c, b.mod, day, 60)


def sim(M, B: Bars1, cand, entry_px, tgt_pts=None, tgt_lvl=None, stop_buf=2.0, be_r=1.0, flat_mod=955, wait_s=3600,
        idm_c=False, idm_c_mode="cancel", cisd1m=None, min_rr=1.5, max_rr=5.0, market=False):
    """Walk one trade on B (5m or 1m), stop beyond the 5m sweep extreme. Conservative intrabar rule: stop before target.
      entry_px  limit price (direction space); market=True enters at the first bar open + 1 tick
      tgt_pts   target distance from the fill (lit_A semantics); or tgt_lvl = absolute level (cisd1m path), capped at max_rr
      idm_c     POI-side inducement: a swing low formed after the trigger, above the limit, must be taken before the limit
                fills (mode cancel: a fill without it cancels the trade; mode wait: ignore that touch and keep waiting)
      cisd1m    dict(n=bars after the tap): after the limit price is tapped, wait for a close above the open of the last run of
                down-close bars into the tap low (CISD on B), then enter at the next bar open + 1 tick
    Returns a trade dict (runlib columns) or None."""
    d = cand["dir"]
    hi_d, lo_d, c_d, o_d = B.dirs(d)
    t0 = int(M.t[cand["entry_i"]])
    k0 = int(np.searchsorted(B.t, t0))
    if k0 >= B.n:
        return None
    s_day = int(M.day_of[cand["entry_i"]])
    stop = cand["ext_d"] - stop_buf
    limit_fill = not market
    fill = None
    if market:
        fill, entry = k0, float(o_d[k0]) + SLIP
        if B.day[k0] != s_day:
            return None
    else:
        tgt_cancel = entry_px + tgt_pts if tgt_pts is not None else tgt_lvl
        tapped = None
        k = k0
        while k < B.n:
            if B.day[k] != s_day or B.mod[k] >= flat_mod or B.mod[k] >= 1080:
                break
            if tapped is None and B.t[k] >= t0 + wait_s:
                break
            if lo_d[k] <= stop:            # extreme broken before a fill or a 1m confirmation: setup dead
                if tapped is None and lo_d[k] <= entry_px and not idm_c and not cisd1m:
                    fill = k; entry = min(entry_px, float(o_d[k])); break
                break
            if tapped is None and lo_d[k] <= entry_px:
                if idm_c:
                    ok = False
                    fl_d = B.fl if d == 1 else B.fh
                    a = bisect.bisect_left(fl_d, k0 - (3 if B.secs == 300 else 10))
                    for m in fl_d[a:bisect.bisect_left(fl_d, k)]:
                        m = int(m)
                        if m + 2 <= k and lo_d[m] > entry_px and lo_d[m + 1:k + 1].min() < lo_d[m] and B.t[m] >= int(M.t[cand["ext_i"]]):
                            ok = True; break
                    if not ok:
                        if idm_c_mode == "cancel":
                            return None
                        k += 1; continue
                if cisd1m:
                    tapped = k
                else:
                    fill = k; entry = min(entry_px, float(o_d[k])); break
            if tapped is None and hi_d[k] >= tgt_cancel:
                break
            if tapped is not None:
                if k - tapped > cisd1m["n"]:
                    break
                lowk = tapped + int(np.argmin(lo_d[tapped:k + 1]))
                cz = _cisd_level(c_d, o_d, lowk)
                if cz is not None and k > lowk and c_d[k] > cz[0] and k + 1 < B.n and B.day[k + 1] == s_day:
                    fill = k + 1; entry = float(o_d[k + 1]) + SLIP; limit_fill = False; break
            k += 1
        if fill is None:
            return None
    risk = entry - stop
    if risk <= 0:
        return None
    if tgt_pts is not None:
        tgt = entry + tgt_pts
    else:
        dist = tgt_lvl - entry
        if dist < min_rr * risk:
            return None
        tgt = entry + min(dist, max_rr * risk)
    q = lit.qty_for(risk)
    if q < 1:
        return None
    cur, be_done, mfe, mae, worst = stop, False, 0.0, 0.0, 0.0
    k = fill
    exit_px, kind = None, None
    while k < B.n:
        if B.day[k] != s_day or B.mod[k] >= 1080:
            k -= 1; exit_px, kind = float(c_d[k]) - SLIP, "EOD"; break
        mae = max(mae, (entry - lo_d[k]) / risk)
        worst = min(worst, lo_d[k] - entry)
        if lo_d[k] <= cur:
            exit_px, kind = cur - SLIP, ("BE" if be_done else "STOP"); break
        if not (k == fill and limit_fill):
            mfe = max(mfe, (hi_d[k] - entry) / risk)
            if hi_d[k] >= tgt:
                exit_px, kind = tgt, "TARGET"; break
            if be_r is not None and not be_done and hi_d[k] >= entry + be_r * risk:
                cur, be_done = entry, True
        if B.mod[k] >= flat_mod:
            exit_px, kind = float(c_d[k]) - SLIP, "EOD"; break
        k += 1
    if exit_px is None:
        return None
    pts = exit_px - entry
    pnl = pts * PV * q - COMM * q
    low = min(0.0, worst * PV * q - COMM * q, pnl)
    xi5 = int(np.searchsorted(M.t, B.t[k], side="right") - 1)
    ei5 = int(np.searchsorted(M.t, B.t[fill], side="right") - 1)
    return {"day": cand["day"], "entry_t": int(B.t[fill]), "exit_t": int(B.t[k]) + B.secs, "exit_i": xi5, "dir": d,
            "r": round(pnl / (risk * PV * q), 3), "pnl": round(pnl, 2), "risk_pts": round(risk, 2), "qty": q,
            "risk_usd": round(risk * PV * q, 2), "half": False, "exit": kind, "trigger": "LIT-entry", "mfe": round(mfe, 3),
            "mae": round(min(mae, 1.0 + SLIP / risk), 3), "bars_held": int(k - fill + 1), "regime": "", "mult": 1.0, "low": round(low, 2),
            "entry_px": round(entry * d, 2), "stop_px": round(stop * d, 2), "target_px": round(tgt * d, 2), "swept": cand["swept"],
            "ind_n": cand["ind_n"], "vec": cand["vec"], "i": cand["i"], "ext_i": cand["ext_i"], "ref_i": cand["ref_i"],
            "sweep_i": cand["sweep_i"], "entry_i": ei5}


# ------------------------------------------------------------------------------------------------ variant runner
def run_v(M, C, v, B5, B1=None, sessions=SESS):
    """v = lit_A-style filter keys (R.make) + entry keys:
      zone       entry zone name (see zones()), 'market', or a list = first zone that exists (fallback chain)
      tf         '5m' (default) or '1m' (2026 sessions use true 1m bars; earlier sessions fall back to 5m)
      cisd1m     n 1m bars after the tap to see a 1m CISD (tf 1m only)
      idm_a      (max_dist_atr, max_age_bars, min_count) pre-sweep inducement gate
      idm_c      True / 'wait'  POI-side inducement before the fill
      idm_d      True = a build-up swept together with another level class
      need_fvg   minimum FVG size (ATR) inside the leg; maxbars, wait (5m bars)"""
    ent = {k: v[k] for k in ("zone", "tf", "cisd1m", "idm_a", "idm_c", "idm_d", "need_fvg", "zone_fb") if k in v}
    base = {k: x for k, x in v.items() if k not in ent}
    cfg = R.make(**base)
    filt = cfg["filt"]
    zone = ent.get("zone", "ref")
    sset = set(sessions)
    out, busy, per_day = [], -1, collections.Counter()
    buf = cfg.get("stop_buf", 2.0)
    for z in C:
        if z["day"] not in sset:
            continue
        if z["entry_i"] <= busy or per_day[z["day"]] >= cfg.get("max_per_day", 1):
            continue
        if not filt(z):
            continue
        if "idm_a" in ent:
            dm, age, cnt = ent["idm_a"]
            if sum(1 for dd, aa in z["idm_a"] if dd <= dm and aa <= age) < cnt:
                continue
        if ent.get("idm_d") and not ("buildup" in z["swept_cls"] and len(z["swept_cls"]) >= 2):
            continue
        if "need_fvg" in ent:
            if z["zones"].get("fvg_sz_big", -1) < ent["need_fvg"]:
                continue
        zs = zone if isinstance(zone, list) else [zone]
        mk = False
        ep = None
        for zn in zs:
            if zn == "market":
                mk = True; ep = z["entry_d"]; break
            if z["zones"].get(zn) is not None:
                ep = z["zones"][zn]; break
        if ep is None:
            continue
        if not mk:
            ep = min(ep, z["trig_c"])      # a zone above the trigger close is already in play: limit at the close
        risk = ep - (z["ext_d"] - buf)
        if not (cfg.get("min_stop", 8.0) <= risk <= cfg.get("max_stop", 60.0)):
            continue
        sh = z["entry_d"] - ep
        zz = {**z, "targets": {k: [x + sh for x in vv] for k, vv in z["targets"].items()}}
        tp = lit.pick_target(zz, risk, cfg.get("classes"), cfg.get("min_rr", 1.5), cfg.get("max_rr", 5.0), cfg.get("fixed_rr"),
                             cfg.get("fallback_rr"))
        if tp is None:
            continue
        use1 = ent.get("tf") == "1m" and B1 is not None and z["day"] >= "2026"
        B = B1 if use1 else B5
        kw = dict(stop_buf=buf, be_r=cfg.get("be_r"), wait_s=cfg.get("wait", 12) * 300,
                  idm_c=bool(ent.get("idm_c")), idm_c_mode="wait" if ent.get("idm_c") == "wait" else "cancel",
                  min_rr=cfg.get("min_rr", 1.5), max_rr=cfg.get("max_rr", 5.0) or 99.0)
        if mk:
            t = sim(M, B, z, None, tgt_pts=tp - 0.0, market=True, **kw)
        elif ent.get("cisd1m"):
            # 2026: CISD on true 1m bars; before 2026 (no 1m data) the same rule on 5m bars over the same time (n // 5 bars)
            n_c = ent["cisd1m"] if use1 else max(1, ent["cisd1m"] // 5)
            t = sim(M, B, z, ep, tgt_lvl=ep + tp, cisd1m={"n": n_c}, **kw)
        else:
            t = sim(M, B, z, ep, tgt_pts=tp, **kw)
        if t is None:
            continue
        out.append(t); busy = t["exit_i"]; per_day[z["day"]] += 1
    return out


# ------------------------------------------------------------------------------------------------ scoring
def pass_rate(days, horizon=60):
    plan = PLANS["builder_50k"]
    pn = [d["pnl"] for d in days]; lo = [d["low"] for d in days]
    P = F = 0
    for i in range(len(days)):
        r = simulate_eval(pn[i:i + horizon], plan, lo[i:i + horizon])["result"]
        P += r == "PASS"; F += r == "FAIL"
    return round(100 * P / (P + F), 1) if P + F else None


KEYS = ("n", "tpw", "wk2", "win", "pf", "net", "per_month", "dd", "p10", "f10", "p20", "f20", "pass_med", "stop")


def score_v(T):
    S = rl.score(T, SESS)
    out = {}
    for nm, (a, z) in (("H1", H1), ("H2", H2)):
        ss = [d for d in SESS if a <= d <= z]
        sp = rl.score([t for t in T if a <= t["day"] <= z], ss)
        s = sp["spans"]["2026"]
        out[nm] = {k: s.get(k) for k in KEYS}
        out[nm]["pass_rate"] = pass_rate([d for d in sp["days"]]) if s.get("n") else None
    for nm in ("2026", "2021-25"):
        s = S["spans"][nm]
        out[nm] = {k: s.get(k) for k in KEYS}
        out[nm]["pass_rate"] = pass_rate([d for d in S["days"] if (d["date"] >= "2026") == (nm == "2026") and d["date"] >= "2021"])
    return out, S


def fmt(o):
    def f(s):
        if not s.get("n"):
            return "n=0"
        return (f"n={s['n']} tpw={s['tpw']} PF={s['pf']} net={s['net']:+,} DD={s['dd']:,} win={s['win']} "
                f"2w={s['p10']}/{s['f10']} pr={s['pass_rate']}")
    return f"H1[{f(o['H1'])}] H2[{f(o['H2'])}] 26[{f(o['2026'])}] ref21-25[{f(o['2021-25'])}]"


# ------------------------------------------------------------------------------------------------ commands
def check():
    """gen_cands(ref='frac') + run_v must give the same lit_A trades as engine/lit.py."""
    M0, C0 = R.market()
    T0 = lit.run(M0, C0, R.make(**LIT_A), SESS)
    M, C = market("frac")
    B5 = Bars1.from_market(M)
    T1 = run_v(M, C, dict(LIT_A), B5)
    a = [(t["day"], t["entry_t"], t["pnl"]) for t in T0]; b = [(t["day"], t["entry_t"], t["pnl"]) for t in T1]
    print("lit.run", len(T0), round(sum(t["pnl"] for t in T0)), "| run_v", len(T1), round(sum(t["pnl"] for t in T1)), "| equal", a == b)
    if a != b:
        diff = [(x, y) for x, y in zip(a, b) if x != y][:10]
        print(diff)
    print(len(C0), len(C))


def variants():
    """The search: one change at a time from lit_A, then combinations of what helped on H1."""
    A = dict(LIT_A)
    V = collections.OrderedDict()
    V["A_base"] = ("frac", {**A})
    # --- R7 entry price on the lit_A setup (5m)
    V["E_market"] = ("frac", {**A, "zone": "market"})
    for zn in ("fvg_top_first", "fvg_ce_first", "fvg_top_last", "fvg_ce_last", "fvg_top_big", "fvg_ce_big", "ob_open", "ob_50",
               "cisd", "brk_high", "brk_50", "fib50", "fib62"):
        V[f"E_{zn}"] = ("frac", {**A, "zone": zn})
    V["E_fvgce_or_ref"] = ("frac", {**A, "zone": ["fvg_ce_last", "ref"]})
    V["E_ob_or_ref"] = ("frac", {**A, "zone": ["ob_open", "ref"]})
    V["E_ref_wait6"] = ("frac", {**A, "wait": 6})
    V["E_ref_wait24"] = ("frac", {**A, "wait": 24})
    # --- R6 structure shift: which swing, which timeframe, how fast
    V["S_cisd_ref"] = ("cisd", {**A})
    V["S_leg_ref"] = ("leg", {**A})
    V["S_frac15_ref"] = ("frac15", {**A})
    V["S_maxbars6"] = ("frac", {**A, "maxbars": 6})
    V["S_maxbars12"] = ("frac", {**A, "maxbars": 12})
    V["S_needfvg0"] = ("frac", {**A, "need_fvg": 0.0})
    V["S_needfvg0.25"] = ("frac", {**A, "need_fvg": 0.25})
    # --- R4 inducement
    for dm, age in ((0.5, 16), (1.0, 16), (1.0, 36), (1.5, 36), (1.0, 8)):
        V[f"I_a_{dm}_{age}"] = ("frac", {**A, "idm_a": (dm, age, 1)})
    V["I_c_cancel"] = ("frac", {**A, "idm_c": True})
    V["I_c_wait"] = ("frac", {**A, "idm_c": "wait"})
    V["I_d_buildup"] = ("frac", {**A, "idm_d": True})
    # --- 1m in 2026 (2021-25 reference runs the same rule on 5m)
    V["M1_ref"] = ("frac", {**A, "tf": "1m"})
    V["M1_cisd15"] = ("frac", {**A, "tf": "1m", "cisd1m": 15})
    V["M1_cisd30"] = ("frac", {**A, "tf": "1m", "cisd1m": 30})
    V["M1_idmc"] = ("frac", {**A, "tf": "1m", "idm_c": True})
    return V


def variants2():
    """Round 2: the H1 winners of round 1 (5m CISD shift; FVG entry; FVG required; build-up IDM) and their combinations."""
    A = dict(LIT_A)
    V = collections.OrderedDict()
    V["C_cisd_fvgtop"] = ("cisd", {**A, "zone": "fvg_top_last"})
    V["C_cisd_fvgce"] = ("cisd", {**A, "zone": "fvg_ce_last"})
    V["C_cisd_needfvg0"] = ("cisd", {**A, "need_fvg": 0.0})
    V["C_cisd_idmd"] = ("cisd", {**A, "idm_d": True})
    V["C_cisd_idma"] = ("cisd", {**A, "idm_a": (1.0, 36, 1)})
    V["C_cisd_wait6"] = ("cisd", {**A, "wait": 6})
    V["C_cisd_wait24"] = ("cisd", {**A, "wait": 24})
    V["C_cisd_maxbars6"] = ("cisd", {**A, "maxbars": 6})
    V["C_cisd_maxbars12"] = ("cisd", {**A, "maxbars": 12})
    V["C_cisd_disp0.8"] = ("cisd", {**A, "disp": 0.8})
    V["C_cisd_disp1.2"] = ("cisd", {**A, "disp": 1.2})
    V["C_cisd_market"] = ("cisd", {**A, "zone": "market"})
    V["C_cisd_ob"] = ("cisd", {**A, "zone": "ob_open"})
    V["C_cisd_1m"] = ("cisd", {**A, "tf": "1m"})
    V["C_cisd_1m_cisd15"] = ("cisd", {**A, "tf": "1m", "cisd1m": 15})
    V["C_cisd_or_frac"] = ("cisd+frac", {**A})
    V["C_frac_fvgtop_idmd"] = ("frac", {**A, "zone": "fvg_top_last", "idm_d": True})
    V["C_frac_fvgtop_1m"] = ("frac", {**A, "zone": "fvg_top_last", "tf": "1m"})
    V["C_frac_needfvg_idmd"] = ("frac", {**A, "need_fvg": 0.0, "idm_d": True})
    V["C_frac_fvgtop_or_cisd"] = ("frac+cisd", {**A, "zone": ["fvg_top_last", "ref"]})
    return V


def variants3():
    """Round 3: combinations of the round-2 H1 winners (CISD shift + I-a inducement / build-up IDM / order-block entry / 1m)."""
    A = dict(LIT_A)
    IA = (1.0, 36, 1)
    V = collections.OrderedDict()
    V["X_cisd_idma_ob"] = ("cisd", {**A, "idm_a": IA, "zone": "ob_open"})
    V["X_cisd_idma_wait6"] = ("cisd", {**A, "idm_a": IA, "wait": 6})
    V["X_cisd_idmd_ob"] = ("cisd", {**A, "idm_d": True, "zone": "ob_open"})
    V["X_cisd_idma_1mcisd15"] = ("cisd", {**A, "idm_a": IA, "tf": "1m", "cisd1m": 15})
    V["X_cisd_ob_1m"] = ("cisd", {**A, "zone": "ob_open", "tf": "1m"})
    V["X_cisd_idma_ob_1m"] = ("cisd", {**A, "idm_a": IA, "zone": "ob_open", "tf": "1m"})
    return V


def variants4():
    """Round 4: neighbours of the best (robustness, not selection) + 1m-executed versions of the best 5m-only variants."""
    A = dict(LIT_A)
    IA = (1.0, 36, 1)
    best = {**A, "idm_a": IA, "tf": "1m", "cisd1m": 15}
    V = collections.OrderedDict()
    V["N_best_idma0.5"] = ("cisd", {**best, "idm_a": (0.5, 36, 1)})
    V["N_best_idma1.5"] = ("cisd", {**best, "idm_a": (1.5, 36, 1)})
    V["N_best_idma_age16"] = ("cisd", {**best, "idm_a": (1.0, 16, 1)})
    V["N_best_cisd10"] = ("cisd", {**best, "cisd1m": 10})
    V["N_best_cisd20"] = ("cisd", {**best, "cisd1m": 20})
    V["N_best_wait6"] = ("cisd", {**best, "wait": 6})
    V["N_best_wait24"] = ("cisd", {**best, "wait": 24})
    V["N_best_frac"] = ("frac", {**best})
    V["N_best_disp0.8"] = ("cisd", {**best, "disp": 0.8})
    V["N_best_noidma"] = ("cisd", {**A, "tf": "1m", "cisd1m": 15})
    V["X_cisd_idma_wait6_1m"] = ("cisd", {**A, "idm_a": IA, "wait": 6, "tf": "1m"})
    V["X_cisd_idma_1m"] = ("cisd", {**A, "idm_a": IA, "tf": "1m"})
    V["X_cisd_idmd_1mcisd15"] = ("cisd", {**A, "idm_d": True, "tf": "1m", "cisd1m": 15})
    V["Y_best20_disp0.8"] = ("cisd", {**best, "cisd1m": 20, "disp": 0.8})
    V["Y_best20_disp0.8_wait6"] = ("cisd", {**best, "cisd1m": 20, "disp": 0.8, "wait": 6})
    return V


def run_list(V, res=None, B1=None):
    res = res if res is not None else {}
    mk = {}
    for name, (ref, v) in V.items():
        if name in res:
            continue
        if ref not in mk:
            parts = [market(r) for r in ref.split("+")]
            M = parts[0][0]
            C = sorted([z for _, cc in parts for z in cc], key=lambda z: (z["entry_t"], -z["dir"]))
            mk[ref] = (M, C, Bars1.from_market(M))
        M, C, B5 = mk[ref]
        if B1 is None and v.get("tf") == "1m":
            B1 = Bars1.one_minute(M)
        T = run_v(M, C, v, B5, B1)
        o, _ = score_v(T)
        res[name] = {"ref": ref, "variant": {k: (list(x) if isinstance(x, (tuple, set)) else x) for k, x in v.items()}, **o}
        print(f"{name:20s} {fmt(o)}", flush=True)
    return res, B1


def search():
    res = json.load(open(OUT)) if os.path.exists(OUT) else {}
    res, B1 = run_list(variants(), res)
    res, B1 = run_list(variants2(), res, B1)
    res, B1 = run_list(variants3(), res, B1)
    res, B1 = run_list(variants4(), res, B1)
    json.dump(res, open(OUT, "w"), indent=1)
    return res


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "search"
    if cmd == "check":
        check()
    elif cmd == "search":
        search()


# ------------------------------------------------------------------------------------------------ save + table
SAVE = {
    "lit_entry_best": ("Y_best20_disp0.8_wait6", "promising",
                       "LIT entry best (picked on 2026 H1): 5m CISD shift + pre-sweep inducement + 1m CISD confirmation, wait 6"),
    "lit_entry_best_w12": ("Y_best20_disp0.8", "promising",
                           "LIT entry runner-up: same as lit_entry_best with the lit_A 12-bar wait (better 2026 H2)"),
    "lit_entry_cisd_idm_1m20": ("N_best_cisd20", "info", "LIT entry: CISD shift + inducement + 1m CISD confirmation, lit_A displacement 1.0 ATR"),
    "lit_entry_cisd_idm_5m": ("X_cisd_idma_wait6_1m", "info", "LIT entry: CISD shift + inducement, plain retest limit (no 1m confirmation)"),
    "lit_entry_fvg_1m": ("C_frac_fvgtop_1m", "info", "LIT entry: lit_A trigger, limit at the near edge of the last displacement FVG"),
}


def all_variants():
    V = collections.OrderedDict()
    for f in (variants, variants2, variants3, variants4):
        V.update(f())
    return V


def save():
    V = all_variants()
    res = json.load(open(OUT))
    B1 = None
    for rid, (name, status, title) in SAVE.items():
        ref, v = V[name]
        parts = [market(r) for r in ref.split("+")]
        M = parts[0][0]
        C = sorted([z for _, cc in parts for z in cc], key=lambda z: (z["entry_t"], -z["dir"]))
        if B1 is None:
            B1 = Bars1.one_minute(M)
        T = run_v(M, C, v, Bars1.from_market(M), B1)
        o, S = score_v(T)
        vv = {k: (list(x) if isinstance(x, (tuple, set)) else x) for k, x in v.items()}
        vv["ref"] = ref
        h = lambda s: f"n={s['n']} tpw={s['tpw']} PF={s['pf']} net={s['net']:+,} DD={s['dd']:,}"
        rl.save(rid, title, "other", "LIT entry models (owner order 2026-10-18: LIT tuned and judged on 2026 only)",
                params=vv, trades=T, scored=S, status=status,
                verdict=f"2026 H1 (selection) {h(o['H1'])}; 2026 H2 (check) {h(o['H2'])}; 2021-25 reference only {h(o['2021-25'])}",
                notes="tools/lit_entry.py variant " + name + "; 2026 executed on true 1m bars where tf=1m (2021-25 on 5m, same rule); "
                      "stop beyond the 5m sweep extreme +2 pts; $800 up to a 20-pt stop then 800x20/stop, MNQ, max 40, $1.40/micro + 1 tick; "
                      "no cold-streak filter; write-up research/lit/entry.md", tags=["lit", "lit_entry"])
        res[name]["saved_as"] = rid
        print(rid, fmt(o))
    json.dump(res, open(OUT, "w"), indent=1)


def table():
    res = json.load(open(OUT))
    c = lambda s: ("-" if not s.get("n") else f"{s['n']} · {s['tpw']} · {s['pf']} · {s['net']:+,}")
    print("| Variant | What changes | 2026 H1 (pick) n · /wk · PF · net $ | 2026 H2 (check) | 2026 full | 2026 DD | 2021-25 ref |")
    print("|---|---|---|---|---|---|---|")
    for k, r in res.items():
        v = {a: b for a, b in r["variant"].items() if a not in LIT_A or LIT_A[a] != (tuple(b) if isinstance(b, list) else b)}
        print(f"| {k} | {r['ref']} {json.dumps(v)[1:-1] if v else ''} | {c(r['H1'])} | {c(r['H2'])} | {c(r['2026'])} | "
              f"{r['2026'].get('dd', '-')} | {c(r['2021-25'])} |")


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] in ("save", "table"):
    {"save": save, "table": table}[sys.argv[1]]()
