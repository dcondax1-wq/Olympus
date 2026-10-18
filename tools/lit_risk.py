"""LIT stops, targets and trade management, tuned on 2026 only (research; agent "risk" of the LIT sprint 2026-10-18).

The lit_A entry stays fixed (engine/lit.py candidates + tools/research_lit.py CAND["A"] filter: 02:00-15:30, all liquidity,
displacement >= 1 ATR, sweep >= 0.5 ATR deep, limit on the retest of the broken swing, wait 12 bars, 1 trade/day). Only the
exit side varies:
  stop       anchor (5m sweep extreme = the protected low; 15m swing; research-only closer 5m/1m higher lows), buffer (pts or
             ATR), min / max stop
  targets    target classes (PD/PW/PM, session boxes, build-ups with a strict definition, previous 1H/4H candle extreme, VIX
             implied-move band), min R, bank level, fallback R, fixed R
  management breakeven (wick / close trigger, lock offset), partials, trailing on new 5m protected swings, time stop,
             flat times for London / AM trades, 1m execution in 2026 (exact intrabar order where 1m exists)

engine/lit.py is NOT edited: the executor below (rk_simulate / rk_run) is a superset of lit.simulate / lit.run and reproduces
lit_A exactly with the default options (`python tools/lit_risk.py check`).

  python tools/lit_risk.py check     # default options == lit_A trade for trade
  python tools/lit_risk.py search    # the variant search -> research/lab/lit_risk_results.json
  python tools/lit_risk.py save      # store the best 5 with rl.save (ids lit_risk_*)
  python tools/lit_risk.py table     # markdown table for research/lit/risk.md

Overfitting guard: choose on 2026 H1 (Jan 2 - Jun 30), check on 2026 H2 (Jul 1 - Oct 16); 2021-25 is a reference line only.
"""
from __future__ import annotations

import bisect
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import lit  # noqa: E402
from engine.analytics import PLANS, simulate_eval  # noqa: E402
from engine.data import load_ltf  # noqa: E402
from tools import research_lit as R  # noqa: E402
from tools import runlib as rl  # noqa: E402

TICK, PV, COMM, SLIP = lit.TICK, lit.PV, lit.COMM, lit.SLIP
SESS = R.SESS
H1 = ("2026-01-01", "2026-06-30")
H2 = ("2026-07-01", "2026-12-31")
OUT = os.path.join(ROOT, "research", "lab", "lit_risk_results.json")
LIT_A = dict(R.CAND["A"])
PD = ("pd", "pw", "pm")


# ------------------------------------------------------------------------------------------------ bars
class XB:
    """Executor bars with direction-space views. day = Market day index (-1 = not a session bar)."""

    def __init__(self, t, o, h, l, c, mod, day, secs):
        self.t, self.o, self.h, self.l, self.c, self.mod, self.day, self.secs = t, o, h, l, c, mod, np.asarray(day), secs
        self.n = len(t)
        self._d = {1: (h, l, c, o), -1: (-l, -h, -c, -o)}

    def dirs(self, d):
        return self._d[d]


class Ctx:
    """Market + candidates + executor bars + extra target levels, built once."""

    def __init__(self):
        self.M, self.C = R.market()
        M = self.M
        self.B5 = XB(M.t, M.o, M.h, M.l, M.c, M.mod, M.day_of, 300)
        self.filt = R.make(**LIT_A)["filt"]
        self.FA = [z for z in self.C if self.filt(z)]
        self._B1 = None
        self._bu = {}
        self._htf = None
        self._f15 = None
        self._fr5 = {1: (M.fl, M.l), -1: (M.fh, -M.h)}      # direction-space fractal lows (protected swings), confirmed at j+2

    # ---- 1m bars for 2026 (only days with full 1m coverage)
    def B1(self):
        if self._B1 is None:
            M = self.M
            b, _ = load_ltf("NQ", M.b)
            dmap = {d: k for k, (d, s, e) in enumerate(M.days)}
            day = np.array([dmap.get(x, -1) for x in b.date_str])
            cnt = np.bincount(day[day >= 0], minlength=len(M.days))
            full = set()
            for k, (d, s, e) in enumerate(M.days):
                if cnt[k] >= 0.97 * 5 * (e - s):
                    full.add(k)
            self._B1 = (XB(b.t, b.o, b.h, b.l, b.c, b.mod, day, 60), full)
        return self._B1

    # ---- build-up levels with a strict definition (tol x ATR, untouched until the trigger)
    def bu(self, tol):
        if tol not in self._bu:
            M = self.M
            L = lit.buildups(M.h, M.l, M.fh, M.fl, M.atr, tol_atr=tol)
            self._bu[tol] = (L, [x[2] for x in L])
        return self._bu[tol]

    # ---- previous completed 1H / 4H candle extremes per 5m bar
    def htf(self):
        if self._htf is None:
            M = self.M
            out = {}
            hb = M.t // 3600
            rel = (M.mod - 1080) % 1440
            b4 = M.day_of.astype(np.int64) * 10 + rel // 240
            for nm, g in (("h1", hb), ("h4", b4)):
                ph = np.full(M.n, np.nan); pl = np.full(M.n, np.nan); st = np.zeros(M.n, np.int64)
                first = np.r_[True, g[1:] != g[:-1]]
                starts = np.flatnonzero(first)
                ends = np.r_[starts[1:], M.n]
                for q in range(1, len(starts)):
                    a, z = starts[q], ends[q]
                    pa, pz = starts[q - 1], ends[q - 1]
                    ph[a:z] = M.h[pa:pz].max(); pl[a:z] = M.l[pa:pz].min(); st[a:z] = a
                out[nm] = (ph, pl, st)
            self._htf = out
        return self._htf

    # ---- 15m swing lows/highs (k=2), confirmed at the close of the 2nd 15m bar after the swing
    def f15(self):
        if self._f15 is None:
            M = self.M
            g = (M.t // 900)
            first = np.r_[True, g[1:] != g[:-1]]
            starts = np.flatnonzero(first); ends = np.r_[starts[1:], M.n]
            h15 = np.array([M.h[a:z].max() for a, z in zip(starts, ends)])
            l15 = np.array([M.l[a:z].min() for a, z in zip(starts, ends)])
            fh, fl = lit.fractals(h15, l15)
            # known at the last 5m bar of the 15m bar j+2
            kn_l = np.array([ends[j + 2] - 1 for j in fl]); kn_h = np.array([ends[j + 2] - 1 for j in fh])
            self._f15 = {1: (kn_l, l15[fl]), -1: (kn_h, -h15[fh])}
        return self._f15


# ------------------------------------------------------------------------------------------------ extra target classes
def extra_targets(X: Ctx, z, v):
    """Distances (from the market entry z['entry_d'], direction space) of the extra target classes asked for in v."""
    M = X.M
    d, i, ed = z["dir"], z["i"], z["entry_d"]
    hi_d = M.h if d == 1 else -M.l
    T = {}
    want = v.get("classes", PD)
    if any(c.startswith("bu") and c != "buildup" for c in want):
        for c in want:
            if not (c.startswith("bu") and c != "buildup"):
                continue
            tol = float(c[2:]) / 100.0          # e.g. bu08 -> 0.08 ATR
            L, kn = X.bu(tol)
            s = M.days[z["k"]][1]
            a = bisect.bisect_left(kn, s - 288 * v.get("bu_days", 2)); b = bisect.bisect_right(kn, i)
            ds = []
            side = "high" if d == 1 else "low"
            for sd, px, ki in L[a:b]:
                if sd != side:
                    continue
                p = px * d
                if p > ed and hi_d[ki + 1:i + 1].max(initial=-np.inf) < p:
                    ds.append(round(p - ed, 2))
            T[c] = sorted(ds)
    for c in ("h1", "h4"):
        if c in want:
            ph, pl, st = X.htf()[c]
            p = ph[i] if d == 1 else -pl[i]
            if not np.isnan(p) and p > ed and hi_d[st[i]:i + 1].max() < p:
                T[c] = [round(p - ed, 2)]
    if "vix" in want:
        x = M.ctx[z["k"]]
        vm = x.get("vix_move")
        if vm:
            anc = v.get("vix_anchor", "18")
            op = x["open18"] if anc == "18" else (M.open_00[i] if anc == "00" else np.nan)
            if not np.isnan(op):
                p = op * d + v.get("vix_k", 1.0) * vm
                if p > ed:
                    T["vix"] = [round(p - ed, 2)]
    return T


def vix_band_dist(X: Ctx, z, k=1.0):
    x = X.M.ctx[z["k"]]
    vm = x.get("vix_move")
    if not vm:
        return None
    return x["open18"] * z["dir"] + k * vm - z["entry_d"]


# ------------------------------------------------------------------------------------------------ stop anchor
def stop_level(X: Ctx, z, v):
    """Direction-space stop price. anchor:
      ext   the 5m sweep extreme (protected low), the CLAUDE.md rule (default)
      sw15  the latest confirmed 15m swing low at or below the 5m extreme (wider; known at the trigger), else ext
      hl5   RESEARCH ONLY (closer than the sweep extreme, breaks the stop rule): the latest confirmed 5m swing low formed after
            the extreme and known at the trigger, else ext"""
    M = X.M
    d, ext, i, ee = z["dir"], z["ext_d"], z["i"], z["ext_i"]
    buf = v.get("stop_buf", 2.0)
    if v.get("buf_atr"):
        buf = max(TICK, v["buf_atr"] * z["atr"])
    a = v.get("anchor", "ext")
    lvl = ext
    if a == "sw15":
        kn, px = X.f15()[d]
        q = bisect.bisect_right(kn, i) - 1
        while q >= 0 and px[q] > ext + 1e-9 and q > bisect.bisect_right(kn, i) - 6:
            q -= 1
        if q >= 0 and px[q] <= ext + 1e-9 and ext - px[q] <= v.get("sw15_max", 40.0):
            lvl = float(px[q])
    elif a == "hl5":
        js, px = X._fr5[d]
        q = bisect.bisect_right(js, i - 2) - 1
        if q >= 0 and js[q] > ee and px[js[q]] > ext:
            lvl = float(px[js[q]])
    return lvl - buf


# ------------------------------------------------------------------------------------------------ executor
def rk_simulate(X: Ctx, z, tgt_pts, stop, v, B: XB):
    """Superset of lit.simulate (identical with default v on 5m bars). Limit entry at the broken swing (lit_A), wait
    v['wait'] 5m bars (cancel if the target trades first); then stop / target / management bar by bar, stop before target
    inside a bar, no target credit on the limit-fill bar."""
    M = X.M
    d = z["dir"]
    hi_d, lo_d, c_d, o_d = B.dirs(d)
    s_day = int(M.day_of[z["entry_i"]])
    t0 = int(M.t[z["entry_i"]])
    k0 = int(np.searchsorted(B.t, t0))
    flat = v.get("flat_mod", 955)
    entry = float(z["ref_d"])
    tgt_px = entry + tgt_pts
    wait_s = v.get("wait", 12) * 300
    fill = None
    k = k0
    while k < B.n and B.t[k] < t0 + wait_s:
        if B.day[k] != s_day or B.mod[k] >= flat or B.mod[k] >= 1080:
            break
        if lo_d[k] <= entry:
            fill = k; entry = min(entry, float(o_d[k])); break
        if hi_d[k] >= tgt_px:
            break
        k += 1
    if fill is None:
        return None
    risk = entry - stop
    if risk <= 0:
        return None
    q = lit.qty_for(risk)
    if q < 1:
        return None
    tgt = entry + tgt_pts
    emod = int(B.mod[fill])
    if v.get("flat_lon") and emod < 480:
        flat = min(flat, v["flat_lon"])
    if v.get("flat_am") and 480 <= emod < 720:
        flat = min(flat, v["flat_am"])
    be_r, be_close, lock = v.get("be_r", 1.0), v.get("be_close"), v.get("be_lock", 0.0)
    part = v.get("partial")                      # (fraction, at_R, move_be_after)
    pq, ppx, pdone = 0, None, False
    if part:
        pq = int(round(q * part[0]))
        if pq < 1 or pq >= q:
            pq = 0
        ppx = entry + part[1] * risk
    trail = v.get("trail")                       # (activate_R or 'be', buffer pts)
    js, fpx = X._fr5[d]
    fill5 = int(np.searchsorted(M.t, B.t[fill], side="right") - 1)
    jp = bisect.bisect_right(js, fill5 - 1)      # fractals formed at/after the fill bar only
    trail_on = False
    time_s = v.get("time_bars") and v["time_bars"] * 300
    cur, be_done = stop, False
    mfe = mae = worst = 0.0
    exit_px = kind = None
    k = fill
    while k < B.n:
        if B.day[k] != s_day or B.mod[k] >= 1080:
            k -= 1; exit_px, kind = float(c_d[k]) - SLIP, "EOD"; break
        mae = max(mae, (entry - lo_d[k]) / risk)
        worst = min(worst, lo_d[k] - entry)
        if lo_d[k] <= cur:
            exit_px, kind = cur - SLIP, ("TRAIL" if cur > entry + 1e-9 and trail_on else "BE" if be_done else "STOP"); break
        if not (k == fill):
            mfe = max(mfe, (hi_d[k] - entry) / risk)
            if pq and not pdone and hi_d[k] >= ppx:
                pdone = True
                if part[2] and not be_done:
                    cur, be_done = max(cur, entry + lock * risk), True
            if hi_d[k] >= tgt:
                exit_px, kind = tgt, "TARGET"; break
            if be_r is not None and not be_done and hi_d[k] >= entry + be_r * risk:
                cur, be_done = max(cur, entry + lock * risk), True
        if be_close is not None and not be_done and c_d[k] >= entry + be_close * risk:
            cur, be_done = max(cur, entry + lock * risk), True
        if trail:
            if not trail_on and ((trail[0] == "be" and be_done) or (trail[0] != "be" and mfe >= trail[0])):
                trail_on = True
            if trail_on:
                tk = B.t[k] + B.secs                  # time at this bar's close
                while jp < len(js) and M.t[js[jp] + 2] + 300 <= tk:
                    p = float(fpx[js[jp]]) - trail[1]
                    if p > cur and p < c_d[k]:
                        cur = p
                    jp += 1
        if time_s and B.t[k] + B.secs - B.t[fill] >= time_s and not be_done and (c_d[k] - entry) / risk < v.get("time_min_r", 0.0):
            exit_px, kind = float(c_d[k]) - SLIP, "TIME"; break
        if B.mod[k] >= flat:
            exit_px, kind = float(c_d[k]) - SLIP, "EOD"; break
        k += 1
    if exit_px is None:
        return None
    rest = q - (pq if pdone else 0)
    pnl = (exit_px - entry) * PV * rest + ((ppx - entry) * PV * pq if pdone else 0.0) - COMM * q
    low = min(0.0, worst * PV * q - COMM * q, pnl)
    xi5 = int(np.searchsorted(M.t, B.t[k], side="right") - 1)
    return {"day": z["day"], "entry_t": int(B.t[fill]), "exit_t": int(B.t[k]) + B.secs, "exit_i": xi5, "dir": d,
            "r": round(pnl / (risk * PV * q), 3), "pnl": round(pnl, 2), "risk_pts": round(risk, 2), "qty": q,
            "risk_usd": round(risk * PV * q, 2), "half": False, "exit": kind, "trigger": "LIT-risk", "mfe": round(mfe, 3),
            "mae": round(min(mae, 1.0 + SLIP / risk), 3), "bars_held": int(k - fill + 1), "regime": "", "mult": 1.0, "low": round(low, 2),
            "entry_px": round(entry * d, 2), "stop_px": round(stop * d, 2), "target_px": round(tgt * d, 2), "swept": z["swept"],
            "ind_n": z["ind_n"], "vec": z["vec"], "i": z["i"], "ext_i": z["ext_i"], "ref_i": z["ref_i"], "sweep_i": z["sweep_i"],
            "entry_i": fill5, "partial": bool(pdone)}


def pick(z_targets, risk, classes, min_rr, max_rr, fixed_rr=None, fallback_rr=None):
    if fixed_rr:
        return fixed_rr * risk
    best = None
    for cls in classes:
        for dist in z_targets.get(cls, []):
            if dist >= min_rr * risk:
                best = dist if best is None else min(best, dist)
                break
    if best is None:
        return fallback_rr * risk if fallback_rr else None
    return min(best, max_rr * risk) if max_rr else best


def rk_run(X: Ctx, v, sessions=SESS):
    """lit.run with the risk options. v keys (defaults = lit_A): stop_buf 2, buf_atr, anchor ext, min_stop 8, max_stop 80,
    classes PD, min_rr 1.5, max_rr 5, fixed_rr, fallback_rr, vix_cap (bank at the VIX band k if nearer), be_r 1, be_close,
    be_lock, partial, trail, time_bars, time_min_r, flat_mod, flat_am, flat_lon, wait 12, exec '5m'|'1m'."""
    M = X.M
    sset = set(sessions)
    use1m = v.get("exec") == "1m"
    if use1m:
        B1, full = X.B1()
    out, busy, per_day = [], -1, {}
    classes = v.get("classes", PD)
    for z in X.FA:
        if z["day"] not in sset or z["entry_i"] <= busy or per_day.get(z["day"], 0) >= v.get("max_per_day", 1):
            continue
        ep = float(z["ref_d"])
        stop = stop_level(X, z, v)
        risk = ep - stop
        if not (v.get("min_stop", 8.0) <= risk <= v.get("max_stop", 80.0)):
            continue
        sh = z["entry_d"] - ep
        TT = dict(z["targets"])
        TT.update(extra_targets(X, z, v))
        TT = {k: [x + sh for x in vv] for k, vv in TT.items()}
        tp = pick(TT, risk, classes, v.get("min_rr", 1.5), v.get("max_rr", 5.0), v.get("fixed_rr"), v.get("fallback_rr"))
        if tp is None:
            continue
        if v.get("vix_cap"):
            vb = vix_band_dist(X, z, v["vix_cap"])
            if vb is not None:
                vb += sh
                if v.get("min_rr", 1.5) * risk <= vb < tp:
                    tp = vb
        B = B1 if use1m and M.day_of[z["entry_i"]] in full else X.B5
        t = rk_simulate(X, z, tp, stop, v, B)
        if t is None:
            continue
        out.append(t); busy = t["exit_i"]; per_day[z["day"]] = per_day.get(z["day"], 0) + 1
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
        out[nm]["pass_rate"] = pass_rate(sp["days"]) if s.get("n") else None
        pn = sorted(t["pnl"] for t in T if a <= t["day"] <= z)
        out[nm]["net_ex_top"] = round(sum(pn[:-1])) if pn else 0          # net without the single best trade (outlier check)
    for nm in ("2026", "2021-25"):
        s = S["spans"][nm]
        out[nm] = {k: s.get(k) for k in KEYS}
        out[nm]["pass_rate"] = pass_rate([d for d in S["days"] if (d["date"] >= "2026") == (nm == "2026")])
        pn = sorted(t["pnl"] for t in T if (t["day"] >= "2026") == (nm == "2026"))
        out[nm]["net_ex_top"] = round(sum(pn[:-1])) if pn else 0
    out["exits"] = {}
    for t in T:
        if t["day"] >= "2026":
            out["exits"][t["exit"]] = out["exits"].get(t["exit"], 0) + 1
    return out, S


def fmt(o):
    def f(s):
        if not s.get("n"):
            return "n=0"
        return f"n={s['n']} tpw={s['tpw']} win={s['win']} PF={s['pf']} net={s['net']:+,} DD={s['dd']:,} 2w={s['p10']}/{s['f10']} pr={s['pass_rate']} xTop={s['net_ex_top']:+,}"
    return f"H1[{f(o['H1'])}] H2[{f(o['H2'])}] 26[{f(o['2026'])}] ref[{f(o['2021-25'])}]"


# ------------------------------------------------------------------------------------------------ search
BASE = {}          # lit_A defaults: stop_buf 2, anchor ext, stop 8-80, PD targets >= 1.5R banked at 5R, BE 1R, wait 12, 5m


def round1():
    V = {"lit_A": {}}
    # stops
    for b in (0.25, 1.0, 3.0, 4.0):
        V[f"buf{b}"] = {"stop_buf": b}
    for a in (0.1, 0.25):
        V[f"bufatr{a}"] = {"buf_atr": a}
    for m in (6.0, 10.0, 12.0):
        V[f"minstop{int(m)}"] = {"min_stop": m}
    for m in (40.0, 50.0, 60.0, 100.0):
        V[f"maxstop{int(m)}"] = {"max_stop": m}
    V["anchor_sw15"] = {"anchor": "sw15"}
    V["anchor_hl5_RESEARCH"] = {"anchor": "hl5"}
    # targets
    V["tgt+sess"] = {"classes": PD + ("asia", "london", "ny")}
    V["tgt+buildup"] = {"classes": PD + ("buildup",)}
    V["tgt+bu08"] = {"classes": PD + ("bu08",)}
    V["tgt+h4"] = {"classes": PD + ("h4",)}
    V["tgt+h1"] = {"classes": PD + ("h1",)}
    V["tgt+vix1"] = {"classes": PD + ("vix",), "vix_k": 1.0}
    V["vixcap1"] = {"vix_cap": 1.0}
    V["vixcap1.5"] = {"vix_cap": 1.5}
    V["fixed3R"] = {"fixed_rr": 3.0}
    V["fixed4R"] = {"fixed_rr": 4.0}
    V["fallback3R"] = {"fallback_rr": 3.0}
    V["fallback4R"] = {"fallback_rr": 4.0}
    for m in (1.0, 2.0, 2.5):
        V[f"minrr{m}"] = {"min_rr": m}
    for b in (3.0, 4.0, 6.0, 8.0):
        V[f"bank{int(b)}"] = {"max_rr": b}
    V["nobank"] = {"max_rr": None}
    # management
    V["be_none"] = {"be_r": None}
    for b in (0.75, 1.5, 2.0, 3.0):
        V[f"be{b}"] = {"be_r": b}
    V["be_close1"] = {"be_r": None, "be_close": 1.0}
    V["be1_lock0.1"] = {"be_lock": 0.1}
    V["part50@1R"] = {"partial": (0.5, 1.0, True)}
    V["part50@2R"] = {"partial": (0.5, 2.0, True)}
    V["part33@2R"] = {"partial": (0.33, 2.0, True)}
    V["trail_be"] = {"trail": ("be", 2.0)}
    V["trail_2R"] = {"trail": (2.0, 2.0)}
    V["time6"] = {"time_bars": 6, "time_min_r": 0.0}
    V["time12_0.5"] = {"time_bars": 12, "time_min_r": 0.5}
    V["flat_am1130"] = {"flat_am": 690}
    V["flat_lon1130"] = {"flat_lon": 690}
    V["exec1m"] = {"exec": "1m"}
    return V


def run_list(X, V, res=None):
    res = res if res is not None else {}
    for nm, v in V.items():
        if nm in res:
            continue
        T = rk_run(X, {**BASE, **v})
        o, _ = score_v(T)
        res[nm] = {"v": {k: (list(x) if isinstance(x, tuple) else x) for k, x in v.items()}, **o}
        print(f"{nm:22s} {fmt(o)}", flush=True)
        json.dump(res, open(OUT, "w"), indent=1)
    return res


def check():
    X = Ctx()
    A = lit.run(X.M, X.C, R.make(**LIT_A), SESS)
    B = rk_run(X, {})
    same = len(A) == len(B) and all(a["pnl"] == b["pnl"] and a["entry_t"] == b["entry_t"] and a["exit"] == b["exit"] for a, b in zip(A, B))
    print("lit_A trades", len(A), "risk executor", len(B), "identical:", same)
    if not same:
        for a, b in zip(A, B):
            if a["pnl"] != b["pnl"] or a["entry_t"] != b["entry_t"]:
                print(a["day"], a["pnl"], b["pnl"], a["exit"], b["exit"]); break
    o, _ = score_v(B)
    print(fmt(o))


VIX1 = {"classes": PD + ("vix",), "vix_k": 1.0}


def round2():
    """On top of the round-1 H1 winner (target = nearest of PD/PW/PM and the VIX one-day band from the 18:00 open)."""
    b = VIX1
    V = {}
    for k in (0.75, 1.25, 1.5):
        V[f"vix{k}"] = {**b, "vix_k": k}
    V["vix1_anchor00"] = {**b, "vix_anchor": "00"}
    V["vix_only"] = {"classes": ("vix",), "vix_k": 1.0}
    V["vix1+fb4R"] = {**b, "fallback_rr": 4.0}
    V["fb4R+maxstop100"] = {"fallback_rr": 4.0, "max_stop": 100.0}
    for nm, x in (("maxstop100", {"max_stop": 100.0}), ("maxstop60", {"max_stop": 60.0}), ("buf0.25", {"stop_buf": 0.25}),
                  ("sw15", {"anchor": "sw15"}), ("exec1m", {"exec": "1m"}), ("time12_0.5", {"time_bars": 12, "time_min_r": 0.5}),
                  ("time6", {"time_bars": 6, "time_min_r": 0.0}), ("bank4", {"max_rr": 4.0}), ("bank6", {"max_rr": 6.0}),
                  ("minrr1", {"min_rr": 1.0}), ("minrr2", {"min_rr": 2.0}), ("be1.5", {"be_r": 1.5}), ("be_none", {"be_r": None}),
                  ("be_lock0.1", {"be_lock": 0.1}), ("part33@2R", {"partial": (0.33, 2.0, True)}), ("+buildup", {"classes": PD + ("vix", "buildup")}),
                  ("+sess", {"classes": PD + ("vix", "asia", "london", "ny")})):
        V[f"vix1+{nm}"] = {**b, **x}
    return V


VO = {"classes": ("vix",), "vix_k": 1.0}


def round3():
    """On top of the round-2 H1 winner vix_only (target = the VIX one-day band edge from the 18:00 open, >= 1.5R, bank 5R)."""
    b = VO
    V = {}
    for k in (0.75, 1.25):
        V[f"vo_k{k}"] = {**b, "vix_k": k}
    for nm, x in (("maxstop100", {"max_stop": 100.0}), ("exec1m", {"exec": "1m"}), ("buf0.25", {"stop_buf": 0.25}),
                  ("sw15", {"anchor": "sw15"}), ("time12_0.5", {"time_bars": 12, "time_min_r": 0.5}), ("bank4", {"max_rr": 4.0}),
                  ("bank6", {"max_rr": 6.0}), ("nobank", {"max_rr": None}), ("minrr2", {"min_rr": 2.0}), ("minrr1", {"min_rr": 1.0}),
                  ("fb4R", {"fallback_rr": 4.0}), ("be1.5", {"be_r": 1.5}), ("be_lock0.1", {"be_lock": 0.1}),
                  ("anchor00", {"vix_anchor": "00"})):
        V[f"vo+{nm}"] = {**b, **x}
    return V


def round4():
    """Combinations of the round-3 H1 winners on vix_only (each helped H1 alone): stops to 100, 1m execution, 1-tick buffer,
    4R fallback when no band target, bank 5 / 8 / none."""
    base = {**VO, "max_stop": 100.0, "exec": "1m"}
    V = {"C1 vo+ms100+1m": base}
    V["C2 C1+buf0.25"] = {**base, "stop_buf": 0.25}
    V["C3 C1+fb4R"] = {**base, "fallback_rr": 4.0}
    V["C4 C1+buf0.25+fb4R"] = {**base, "stop_buf": 0.25, "fallback_rr": 4.0}
    V["C5 C1+sw15"] = {**base, "anchor": "sw15"}
    V["C6 C1+time12_0.5"] = {**base, "time_bars": 12, "time_min_r": 0.5}
    for b in (6.0, 8.0, None):
        tag = "nobank" if b is None else f"bank{int(b)}"
        V[f"C1+{tag}"] = {**base, "max_rr": b}
        V[f"C4+{tag}"] = {**base, "stop_buf": 0.25, "fallback_rr": 4.0, "max_rr": b}
    V["C1+k1.25"] = {**base, "vix_k": 1.25}
    V["C4+k1.25"] = {**base, "stop_buf": 0.25, "fallback_rr": 4.0, "vix_k": 1.25}
    return V


C4 = {**VO, "max_stop": 100.0, "exec": "1m", "stop_buf": 0.25, "fallback_rr": 4.0}


def robust():
    """Neighbours of the two picks (robustness only, nothing is chosen here)."""
    V = {}
    for nm, b in (("nobank", None), ("bank8", 8.0)):
        base = {**C4, "max_rr": b}
        V[f"R {nm} k0.9"] = {**base, "vix_k": 0.9}
        V[f"R {nm} k1.1"] = {**base, "vix_k": 1.1}
        V[f"R {nm} maxstop80"] = {**base, "max_stop": 80.0}
        V[f"R {nm} maxstop120"] = {**base, "max_stop": 120.0}
        V[f"R {nm} exec5m"] = {**base, "exec": "5m"}
        V[f"R {nm} buf2"] = {**base, "stop_buf": 2.0}
    V["R bank10"] = {**C4, "max_rr": 10.0}
    V["R bank12"] = {**C4, "max_rr": 12.0}
    return V


PICKS = {
    "lit_risk_vix_nobank": ("LIT risk best: lit_A entry, target = VIX one-day band edge (no bank), 4R fallback, 1-tick stop buffer, stop 8-100",
                            {**C4, "max_rr": None}, "promising"),
    "lit_risk_vix_bank8": ("LIT risk runner-up: as lit_risk_vix_nobank but banked at 8R", {**C4, "max_rr": 8.0}, "promising"),
    "lit_risk_vix_bank5": ("LIT risk: VIX band target banked at 5R, 4R fallback, 1-tick buffer, stop 8-100", C4, "info"),
    "lit_risk_vix_only": ("LIT risk: lit_A with the target swapped to the VIX one-day band edge (single change)", VO, "info"),
    "lit_risk_vix_pd": ("LIT risk: lit_A target = nearest of PDH/PWH/PMH and the VIX band edge", VIX1, "info"),
}


def slip_extra(T, ticks=2):
    return [{**t, "pnl": round(t["pnl"] - ticks * TICK * PV * t["qty"], 2)} for t in T]


def details():
    X = Ctx()
    for rid, (title, v, st) in PICKS.items():
        T = rk_run(X, v)
        o, S = score_v(T)
        o2, _ = score_v(slip_extra(T))
        t26 = [t for t in T if t["day"] >= "2026"]
        print("==", rid, json.dumps({k: (list(x) if isinstance(x, tuple) else x) for k, x in v.items()}))
        for nm in ("H1", "H2", "2026", "2021-25"):
            print("  ", nm, json.dumps({k: o[nm].get(k) for k in KEYS + ("pass_rate", "net_ex_top")}))
        print("   wk2 26", S["spans"]["2026"]["wk2"], "| +2 ticks: H1", o2["H1"]["net"], o2["H1"]["pf"], "H2", o2["H2"]["net"], o2["H2"]["pf"],
              "26", o2["2026"]["net"], o2["2026"]["pf"], "ref", o2["2021-25"]["net"], o2["2021-25"]["pf"])
        print("   months", {m: round(x["net"]) for m, x in S["months"].items() if m >= "2026"})
        print("   years", {y: (x["n"], x["pf"], x["net"]) for y, x in S["years"].items()})
        print("   exits 2026", o["exits"], "longs", round(sum(t["pnl"] for t in t26 if t["dir"] == 1)), "shorts", round(sum(t["pnl"] for t in t26 if t["dir"] == -1)))
        top = sorted(t26, key=lambda t: -t["pnl"])[:3]
        print("   top3", [(t["day"], t["dir"], t["r"], round(t["pnl"]), t["risk_pts"], t["qty"], t["entry_px"], t["target_px"], t["exit"]) for t in top])


def save():
    X = Ctx()
    for rid, (title, v, st) in PICKS.items():
        T = rk_run(X, v)
        o, S = score_v(T)
        vv = {k: (list(x) if isinstance(x, tuple) else x) for k, x in v.items()}
        h = lambda s: f"n={s['n']} {s['tpw']}/wk PF {s['pf']} net {s['net']:+,} DD {s['dd']:,} pass rate {s['pass_rate']}%"
        rl.save(rid, title, "other", "LIT stops, targets and management (lit_A entry fixed), tuned on 2026 H1, checked on 2026 H2",
                params={"entry": "lit_A (tools/research_lit.py CAND['A'])", **vv}, trades=T, scored=S, status=st,
                verdict=f"2026 H1 (selection) {h(o['H1'])}; 2026 H2 (check) {h(o['H2'])}; 2026 {h(o['2026'])}; 2021-25 reference only {h(o['2021-25'])}",
                notes="tools/lit_risk.py (wraps engine/lit.py, no engine edits). 2026 trades walk true 1m bars where a day has full 1m "
                      "coverage (exec 1m), 5m elsewhere. Size $800 up to a 20-pt stop then 800x20/stop, MNQ, max 40, $1.40/micro + 1 tick "
                      "on entry and non-limit exits. No cold-streak filter.", writeup=None, tags=["lit", "lit_risk"])
        print("saved", rid)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "check":
        check()
    elif cmd == "round1":
        X = Ctx()
        res = json.load(open(OUT)) if os.path.exists(OUT) else {}
        run_list(X, round1(), res)
    elif cmd == "details":
        details()
    elif cmd == "save":
        save()
    elif cmd in ("round2", "round3", "round4", "robust"):
        X = Ctx()
        res = json.load(open(OUT)) if os.path.exists(OUT) else {}
        run_list(X, globals()[cmd](), res)
