"""STOP-HUNT family research (owner 2026-10-23): "When all the retail traders get stopped out, it's usually because their
stop loss is at a low or high. If we wait for a resweep, or inducement, then a strong candle move toward our DOL, we could
find gold. Find more setups with the same or higher win rate (LIT wins 55%)."

    python -X utf8 tools/stophunt.py base        # pools / sweeps / DOL tables -> cache (research/runs/_cache/stophunt_*.pkl)
    python -X utf8 tools/stophunt.py grid        # stage 1: every setup x entry x target/15-min x window x max/day (4 procs)
    python -X utf8 tools/stophunt.py pick        # pick on 2026 H1 (plateau), H2 untouched, chance checks -> picks
    python -X utf8 tools/stophunt.py stage2      # management / target / entry / stop-cap grid on the stage-1 picks
    python -X utf8 tools/stophunt.py pick2       # stage-2 picks (H1-only rules and the robust rule: worst t of H1 / 2025 / 2021-24)
    python -X utf8 tools/stophunt.py stage3      # refinement grids around the two leads (Asia, trend); pick3 = their picks
    python -X utf8 tools/stophunt.py final       # FINAL picks: spans, months, placebos, look-ahead, sensitivity -> research/stophunt
    python -X utf8 tools/stophunt.py book        # the picks as one strategy (one position, max 2 a session)
    python -X utf8 tools/stophunt.py evals       # MFFU eval paths: own account, with LIT on the 50K, ATLAS member on the 25K
    python -X utf8 tools/stophunt.py summary     # multiple-testing / chance numbers -> research/stophunt/search_summary.json
    python -X utf8 tools/stophunt.py save        # rl.save the runs sh_*
Needs numba for the grids (pip install numba; minutes instead of hours); final / test run without it, slower.
Core: engine/stophunt.py (pools, hunts, triggers, DOL tables, fills, walk). Write-up: research/writeups/stophunt.md.

Method (no look-ahead, costs in):
- Data: TradingView CME NQ1! 5m (data/NQ_5m.csv, 2021-11 .. 2026-10-16) for pools, hunts and signals; the trade itself is
  walked on the 1m bars in 2026 (data/NQ_1m.csv; 5m before 2026, there is no 1m history).
- Costs: $1.90 a micro round trip + 1 tick slippage on market entries and on stop / time / flat exits; limits fill only when
  price trades 1 tick through, targets at the limit; stop and target in one bar = stop.
- Size for scoring: $500 risk a trade = floor(500 / (stop pts x $2)) micros, max 50. Stops 1 tick beyond the hunt extreme.
- Pick on 2026 H1 (Jan 2 - Jun 30) only; H2 (Jul 1 - Oct 16) untouched; 2025 and 2021-24 reference lines.
Paper research only. Edits no engine/lit.py, engine/live.py, live_model*.json or second_model.json.
"""
from __future__ import annotations

import collections
import gzip
import itertools
import json
import math
import os
import pickle
import sys
import time
from multiprocessing import Pool

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import stophunt as E  # noqa: E402
from engine.stophunt import njit  # noqa: E402

OUT = os.path.join(ROOT, "research", "stophunt")
CACHE = os.path.join(ROOT, "research", "runs", "_cache")
RISK_USD, MAXQ = 500.0, 50
SPANS = (("H1", "2026-01-01", "2026-06-30"), ("H2", "2026-07-01", "2026-12-31"), ("2025", "2025-01-01", "2025-12-31"),
         ("2021-24", "2021-11-01", "2024-12-31"))
SPAN_NAMES = [s[0] for s in SPANS]
NSTAT = 8          # per span: n, net $, wins, gross win $, gross loss $, sum R, sum R^2, max DD $
G = {}             # the base (fork-shared with the workers)


# ================================================================================================ base
def base(cut_t=None):
    """Bars, pools, swing index, DOL tables, sorted sweeps. cut_t: data as it was at that time (look-ahead check)."""
    if cut_t is None and G:
        return G
    B = E.load(cut_t=cut_t)
    if cut_t is not None:
        B["cut"] = True
    P = E.build_pools(B)
    F = E.swing_index(B)
    TB = E.dol_tables(P, B)
    order = E.sorted_sweeps(P)
    sp = np.full(len(B["days"]), -1, np.int64)
    for i, (nm, a, z) in enumerate(SPANS):
        sp[(B["days"] >= a) & (B["days"] <= z)] = i
    nsess = [int(((B["days"] >= a) & (B["days"] <= min(z, "2026-10-16"))).sum()) for nm, a, z in SPANS]
    g = dict(B=B, P=P, F=F, TB=TB, order=order, span_of_sid=sp, nsess=nsess, ev={})
    if cut_t is None:
        G.update(g)
    return g


# ================================================================================================ pool sets
def _tm(*names):
    return [E.TI[x] for x in names]


POOL_SETS = {
    # name: (types, min event score, min feature classes, min age in 5m bars, plain words)
    "f1": (_tm("f1"), 0, 1, 0, "1m swing highs/lows (2026 only)"),
    "f5": (_tm("f5"), 0, 1, 0, "5m swing highs/lows"),
    "f15": (_tm("f15"), 0, 1, 0, "15m swing highs/lows"),
    "f60": (_tm("f60"), 0, 1, 0, "1h swing highs/lows"),
    "eq": (_tm("eq5", "eq15"), 0, 1, 0, "equal highs/lows (5m or 15m swings, 2+ touches)"),
    "range": (_tm("range"), 0, 1, 0, "consolidation edges (2h / 4h ranges)"),
    "tl": (_tm("tl"), 0, 1, 0, "3-touch trendlines"),
    "sess": (_tm("asia", "lon"), 0, 1, 0, "Asia / London session highs/lows"),
    "day": (_tm("ny", "on", "pd"), 0, 1, 0, "prior NY session, overnight, prior day highs/lows"),
    "pw": (_tm("pw"), 0, 1, 0, "prior week high/low"),
    "round": (_tm("r100", "r50"), 0, 1, 0, "round numbers (x00 / x50)"),
    "htf": (_tm("f15", "f60", "eq15", "asia", "lon", "ny", "on", "pd", "pw"), 0, 1, 0, "higher-timeframe pools (15m/1h swings, 15m equal, sessions, day, week)"),
    "all": (list(range(len(E.TYPES))), 0, 1, 0, "every pool type"),
    "obv": (list(range(len(E.TYPES))), 3.0, 1, 0, "the most obvious pools (score >= 3: 1h swings, 15m equal highs, sessions, day, week)"),
    "stack": (list(range(len(E.TYPES))), 0, 2, 0, "stacked pools (2+ retail features within 0.3 ATR swept by the same bar)"),
    "old": (list(range(len(E.TYPES))), 2.0, 1, 48, "older obvious pools (score >= 2 and 4h+ old)"),
}


def ev_of(g, ps):
    if ps in g["ev"]:
        return g["ev"][ps]
    types, msc, mcl, mag, _ = POOL_SETS[ps]
    P = g["P"]
    mask = np.isin(P["typ"], types)
    ev = E.events(P, g["order"], mask, g["B"], min_score=msc, min_cls=mcl, min_age=mag)
    g["ev"][ps] = ev
    return ev


# ================================================================================================ trades
MODE_SPEC = {"any": (0, 2), "fast": (1, 2), "rs_pool": (2, 0), "rs_ext": (2, 1), "rs": (2, 2), "idm": (3, 2), "pre": (4, 2),
             "rs_idm": (5, 2), "rs_or_idm": (6, 2)}
BODY_SPEC = {"a0.5": (0.5, 0), "a0.8": (0.8, 0), "a1.0": (1.0, 0), "a1.2": (1.2, 0), "a1.5": (1.5, 0), "a2.0": (2.0, 0),
             "x2": (2.0, 1), "x3": (3.0, 1)}
STRUCT = {"none": 0, "cisd": 1, "mss": 2}
ENTRY = {"mkt": 0, "mid": 1, "fvg": 2, "c1m": 3}


def sigs_of(g, S):
    m, rk = MODE_SPEC[S["mode"]]
    kb, bt = BODY_SPEC[S["body"]]
    return E.signals(ev_of(g, S["pool"]), g["B"], g["F"], W=S["W"], mode=m, rs_kind=rk, kb=kb, btype=bt,
                     struct=STRUCT[S["struct"]], fvg=int(S["fvg"]), depth=S["depth"])


@njit(cache=True)
def _fills(sig, dr, ext, mid, fvg, kind, t5, o5, h5, l5, c5, rel5, sid5, t1, o1, h1, l1, c1, rel1, sid1, m1_from, m1_to,
           flat5, sflat5, flat1, sflat1, min_stop, max_stop, cut_rel):
    """Entries for one signal list: path (0 = 5m, 1 = 1m), fill bar on that path, entry (direction space), stop, risk,
    flat bars (15:55 and session end), fill time."""
    m = len(sig)
    PA = np.full(m, -1, np.int64); K0 = np.empty(m, np.int64); EN = np.empty(m); SP = np.empty(m); RK = np.empty(m)
    KF = np.empty(m, np.int64); KS = np.empty(m, np.int64); FT = np.empty(m, np.int64); LM = np.empty(m, np.int64)
    for i in range(m):
        s = sig[i]
        stop_d = ext[i] - 0.25
        tsig = t5[s] + 300
        lim = mid[i] if kind == 1 else fvg[i]
        sd = sid5[s]
        if tsig >= m1_from and tsig < m1_to:
            k1 = np.searchsorted(t1, tsig)
            if k1 >= len(t1):
                continue
            mb = 30 if (kind == 1 or kind == 2) else 20
            k0, e, isl = E_fill(t1, o1, h1, l1, c1, rel1, sid1, k1, dr[i], kind, lim, stop_d, mb, sd, cut_rel)
            if k0 < 0:
                continue
            PA[i] = 1; K0[i] = k0; KF[i] = flat1[k0]; KS[i] = sflat1[k0]; FT[i] = t1[k0]
        else:
            mb = 6 if (kind == 1 or kind == 2) else 4
            k0, e, isl = E_fill(t5, o5, h5, l5, c5, rel5, sid5, s + 1, dr[i], kind, lim, stop_d, mb, sd, cut_rel)
            if k0 < 0:
                continue
            PA[i] = 0; K0[i] = k0; KF[i] = flat5[k0]; KS[i] = sflat5[k0]; FT[i] = t5[k0]
        risk = e - stop_d
        if risk < min_stop or risk > max_stop or KF[i] < 0:
            PA[i] = -1
            continue
        EN[i] = e; SP[i] = stop_d; RK[i] = risk; LM[i] = isl
    return PA, K0, EN, SP, RK, KF, KS, FT, LM


E_fill = E._fill


def fills(g, sg, entry, min_stop=6.0, max_stop=80.0):
    B = g["B"]; M1 = B["m1"]
    PA, K0, EN, SP, RK, KF, KS, FT, LM = _fills(sg["sig"], sg["dr"], sg["ext"], sg["mid"], sg["fvg"], ENTRY[entry], B["t"], B["o"],
                                                 B["h"], B["l"], B["c"], B["rel"], B["sid"], M1["t"], M1["o"], M1["h"], M1["l"],
                                                 M1["c"], M1["rel"], M1["sid"], B["m1_from"], B["m1_to"], B["flat5"], B["sflat5"],
                                                 M1["flat"], M1["sflat"], min_stop, max_stop, E.ENTRY_CUT)
    k = PA >= 0
    X = dict(i=np.nonzero(k)[0], path=PA[k], k0=K0[k], e=EN[k], sp=SP[k], risk=RK[k], kf=KF[k], ks=KS[k], ft=FT[k], lim=LM[k])
    for f in ("sig", "dr", "score", "flags", "j", "p", "ext"):
        X[f] = sg[f][X["i"]]
    X["sid"] = B["sid"][X["sig"]]
    X["bucket"] = np.searchsorted(np.array([240, 480, 840, 1080]), B["rel"][X["sig"]], side="right")   # Asia early/late, Lon, NY AM, NY PM
    return X


# targets: (kind, value, bank)
TARGETS = {"r1.5": ("R", 1.5, None), "r2": ("R", 2.0, None), "r3": ("R", 3.0, None),
           "dolA": ("dol", 0, None), "dolA_b3": ("dol", 0, 3.0), "dolA_b5": ("dol", 0, 5.0),
           "dolH": ("dol", 1, None), "dolH_b3": ("dol", 1, 3.0), "dolH_b5": ("dol", 1, 5.0),
           "dolO": ("dol", 2, None), "dolO_b5": ("dol", 2, 5.0), "vix_b8": ("vix", 0, 8.0)}


def targets(g, X, tg, min_rr=1.5):
    """Target price (direction space) per trade; nan = no target that far (no trade)."""
    kind, v, bank = TARGETS[tg]
    e, r = X["e"], X["risk"]
    if kind == "R":
        return e + v * r
    if kind == "vix":
        B = g["B"]
        s = X["sid"]
        T = np.where(X["dr"] > 0, B["open18"][s] + B["vixmove"][s], -B["open18"][s] + B["vixmove"][s])
        T = np.where(T >= e + min_rr * r, T, np.nan)
    else:
        tb = g["TB"][X["sig"], (X["dr"] < 0).astype(np.int64), v].astype(np.float64)       # (m, K) ascending
        need = (e + min_rr * r)[:, None]
        ok = tb >= need
        first = np.where(ok.any(1), np.argmax(ok, 1), -1)
        T = np.where(first >= 0, tb[np.arange(len(e)), np.maximum(first, 0)], np.nan)
    if bank:
        T = np.minimum(T, e + bank * r)
    return T


def partial_px(g, X, T):
    """The first pool (any type) on the way: >= 1R from the entry and below the target; 0 = none."""
    tb = g["TB"][X["sig"], (X["dr"] < 0).astype(np.int64), 0].astype(np.float64)
    ok = (tb >= (X["e"] + X["risk"])[:, None]) & (tb < T[:, None])
    first = np.where(ok.any(1), np.argmax(ok, 1), -1)
    return np.where(first >= 0, tb[np.arange(len(T)), np.maximum(first, 0)], 0.0)


@njit(cache=True)
def _walk_many(o, h, l, c, t, secs, k0, kf, dr, e, sp, risk, T, be_at, be_off, tcb, lim, part, part_f):
    m = len(k0)
    PT = np.empty(m); XK = np.empty(m, np.int64); KD = np.empty(m, np.int64); MF = np.empty(m); MA = np.empty(m)
    XT = np.empty(m, np.int64)
    for i in range(m):
        pts, kx, kd, mf, ma = E_walk(o, h, l, c, k0[i], kf[i], dr[i], e[i], sp[i], risk[i], T[i], be_at, be_off, tcb, lim[i],
                                     part[i], part_f)
        PT[i] = pts; XK[i] = kx; KD[i] = kd; MF[i] = mf; MA[i] = ma
        XT[i] = t[kx] if kd == 3 else t[kx] + secs
    return PT, XK, KD, MF, MA, XT


E_walk = E._walk


def walk(g, X, T, be="be1c", t15=True, part=False, flat="1555"):
    """Walk every trade with target T. be: none | be1 (stop to entry at 1R) | be1c (entry + 1.25 at 1R, LIT's BE + costs)."""
    B = g["B"]; M1 = B["m1"]
    m = len(X["e"])
    out = {k: np.zeros(m) for k in ("pts", "mfe", "mae")}
    out["kind"] = np.zeros(m, np.int64); out["xt"] = np.zeros(m, np.int64)
    be_at, be_off = (0.0, 0.0) if be == "none" else (1.0, 0.0 if be == "be1" else 1.25)
    ok = ~np.isnan(T)
    pp = partial_px(g, X, np.where(ok, T, 0.0)) if part else np.zeros(m)
    kf = X["kf"] if flat == "1555" else np.where(X["ks"] >= 0, X["ks"], X["kf"])
    for pa, (o, h, l, c, t, secs, tcb) in ((0, (B["o"], B["h"], B["l"], B["c"], B["t"], 300, 3)),
                                          (1, (M1["o"], M1["h"], M1["l"], M1["c"], M1["t"], 60, 15))):
        q = np.nonzero((X["path"] == pa) & ok)[0]
        if not len(q):
            continue
        PT, XK, KD, MF, MA, XT = _walk_many(o, h, l, c, t, secs, X["k0"][q], kf[q], X["dr"][q], X["e"][q], X["sp"][q], X["risk"][q],
                                            T[q], be_at, be_off, tcb if t15 else 0, X["lim"][q], pp[q], 0.5)
        out["pts"][q] = PT; out["kind"][q] = KD; out["mfe"][q] = MF; out["mae"][q] = MA; out["xt"][q] = XT
    out["ok"] = ok
    qty = np.minimum(MAXQ, np.floor(RISK_USD / (X["risk"] * E.PV))).astype(np.int64)
    out["qty"] = qty
    out["pnl"] = np.where(ok, qty * (out["pts"] * E.PV - E.COMM), 0.0)
    out["R"] = np.where(ok, out["pnl"] / (X["risk"] * E.PV * np.maximum(qty, 1)), 0.0)
    return out


# ================================================================================================ selection + stats
WINDOWS = {"all": 31, "asia": 3, "lon": 4, "nyam": 8, "nypm": 16, "ny": 24, "day": 28, "asia_e": 1, "asia_l": 2, "asia_lon": 7}


@njit(cache=True)
def select_stats(ft, xt, sid, bucket, ok, pnl, R, winmask, maxpd, span_of_sid, nspan, keep):
    m = len(ft)
    st = np.zeros((nspan, 8))
    eq = np.zeros(nspan); pk = np.zeros(nspan)
    busy = -1
    last_s = -1; cnt = 0
    sel = np.empty(m if keep else 1, np.int64)
    ns = 0
    for i in range(m):
        if not ok[i] or ft[i] < busy:
            continue
        if not ((winmask >> bucket[i]) & 1):
            continue
        if sid[i] != last_s:
            last_s = sid[i]; cnt = 0
        if cnt >= maxpd:
            continue
        cnt += 1
        busy = xt[i]
        if keep:
            sel[ns] = i; ns += 1
        sp = span_of_sid[sid[i]]
        if sp < 0:
            continue
        p = pnl[i]
        st[sp, 0] += 1; st[sp, 1] += p
        if p > 0:
            st[sp, 2] += 1; st[sp, 3] += p
        else:
            st[sp, 4] -= p
        st[sp, 5] += R[i]; st[sp, 6] += R[i] * R[i]
        eq[sp] += p
        if eq[sp] > pk[sp]:
            pk[sp] = eq[sp]
        if eq[sp] - pk[sp] < st[sp, 7]:
            st[sp, 7] = eq[sp] - pk[sp]
    return st, sel[:ns]


def order_by_time(X, W):
    o = np.argsort(X["ft"], kind="stable")
    return o


def stats_dict(st, nsess, s=0):
    n, net, w, gp, gl, sr, sr2, dd = st[s]
    if n == 0:
        return {"n": 0, "tpw": 0.0, "net": 0.0, "win": None, "pf": None, "avg_r": None, "t": None, "dd": 0.0, "per_month": 0.0}
    sd = math.sqrt(max(sr2 / n - (sr / n) ** 2, 0.0)) * math.sqrt(n / max(n - 1, 1))
    return {"n": int(n), "tpw": round(float(n / (nsess[s] / 5)), 2), "net": round(net), "win": round(100 * w / n, 1),
            "pf": round(gp / gl, 2) if gl > 0 else 99.0, "avg_r": round(sr / n, 3),
            "t": round((sr / n) / (sd / math.sqrt(n)), 2) if sd > 0 and n > 2 else 0.0, "dd": round(dd),
            "per_month": round(net / (nsess[s] / 21))}


def trade_rows(g, X, Wk, T, sel, setup):
    """Chosen trades in the common format {day, entry_t, exit_t, dir, entry, stop, target, exit, exit_kind, r, qty, pnl_usd,
    setup} (+ risk_pts, session, hunt bar time, pool score, flags)."""
    B = g["B"]
    rows = []
    for i in sel:
        d = int(X["dr"][i])
        e = float(X["e"][i])
        rows.append({"day": str(B["days"][X["sid"][i]]), "entry_t": int(X["ft"][i]), "exit_t": int(Wk["xt"][i]), "dir": d,
                     "entry": round(d * e, 2), "stop": round(d * float(X["sp"][i]), 2), "target": round(d * float(T[i]), 2),
                     "exit": round(d * (e + float(Wk["pts"][i])), 2), "exit_kind": E.EXIT_KINDS[int(Wk["kind"][i])],
                     "r": round(float(Wk["R"][i]), 3), "qty": int(Wk["qty"][i]), "pnl_usd": round(float(Wk["pnl"][i]), 2),
                     "setup": setup, "risk_pts": round(float(X["risk"][i]), 2), "session": E.BUCKET_NAMES[max(0, int(X["bucket"][i]) - 1)],
                     "hunt_t": int(B["t"][X["j"][i]]), "signal_t": int(B["t"][X["sig"][i]]) + 300, "pool_px": round(d * float(X["p"][i]), 2),
                     "pool_score": round(float(X["score"][i]), 2), "flags": int(X["flags"][i]), "path": "1m" if X["path"][i] == 1 else "5m",
                     "mfe_r": round(float(Wk["mfe"][i]), 2), "mae_r": round(float(Wk["mae"][i]), 2)})
    return rows


# ================================================================================================ stage 1 grid
DIMS = {"pool": list(POOL_SETS), "mode": list(MODE_SPEC), "W": [6, 12, 24], "body": ["a0.5", "a0.8", "a1.2", "x2"],
        "struct": ["none", "cisd", "mss"], "fvg": [0, 1], "depth": [0.0, 0.25]}
G1_TG = ["r2", "dolA_b5", "dolH_b5", "vix_b8"]
G1_T15 = [0, 1]
G1_WIN = list(WINDOWS)
G1_MP = [1, 2]
VCOLS = ["cfg", "entry", "tg", "t15", "win", "mp"]


def setup_grid():
    out = []
    for vals in itertools.product(*DIMS.values()):
        S = dict(zip(DIMS, vals))
        if S["mode"] == "fast" and S["W"] != 6:
            continue
        out.append(S)
    return out


def run_setup(g, S, entries, tgs, t15s, wins, mps, be="be1c", part=False, flat="1555", min_stop=6.0, max_stop=80.0,
              min_rr=1.5, keep=None):
    """All variants of one setup config -> list of ((entry, tg, t15, win, mp), stats [4, 8])."""
    sg = sigs_of(g, S)
    res = []
    for en in entries:
        if en == "fvg" and not S["fvg"]:
            continue
        X = fills(g, sg, en, min_stop=min_stop, max_stop=max_stop)
        o = np.argsort(X["ft"], kind="stable")
        Xo = {k: v[o] for k, v in X.items()}
        for tg in tgs:
            T = targets(g, Xo, tg, min_rr=min_rr)
            for t15 in t15s:
                Wk = walk(g, Xo, T, be=be, t15=bool(t15), part=part, flat=flat)
                for wn in wins:
                    for mp in mps:
                        st, sel = select_stats(Xo["ft"], Wk["xt"], Xo["sid"], Xo["bucket"], Wk["ok"], Wk["pnl"], Wk["R"],
                                               WINDOWS[wn], mp, g["span_of_sid"], 4, keep is not None)
                        res.append(((en, tg, t15, wn, mp), st))
                        if keep is not None:
                            keep[(en, tg, t15, wn, mp)] = (Xo, Wk, T, sel)
    return res


def _g1_job(ci):
    g = base()
    S = SETUPS[ci]
    R = run_setup(g, S, ["mkt", "mid", "fvg"], G1_TG, G1_T15, G1_WIN, G1_MP)
    codes = np.array([[ci, ["mkt", "mid", "fvg"].index(k[0]), G1_TG.index(k[1]), k[2], G1_WIN.index(k[3]), G1_MP.index(k[4])]
                      for k, _ in R], np.int32)
    st = np.array([x for _, x in R], np.float32)
    return codes, st


SETUPS = setup_grid()


def cmd_grid(procs=4):
    base()
    t0 = time.time()
    J = list(range(len(SETUPS)))
    print(len(J), "setup configs", flush=True)
    C, S = [], []
    with Pool(procs) as pool:
        for k, (c, st) in enumerate(pool.imap(_g1_job, J, chunksize=16)):
            C.append(c); S.append(st)
            if k % 2000 == 0:
                print(f"  {k}/{len(J)} {time.time() - t0:.0f}s", flush=True)
    C = np.concatenate(C); S = np.concatenate(S)
    os.makedirs(CACHE, exist_ok=True)
    np.save(os.path.join(CACHE, "stophunt_g1_codes.npy"), C)
    np.save(os.path.join(CACHE, "stophunt_g1_stats.npy"), S)
    print("variants", len(C), f"{time.time() - t0:.0f}s", flush=True)


# ================================================================================================ stage 1 pick
G1_ENTRY = ["mkt", "mid", "fvg"]
KEY_DIMS = list(DIMS) + ["entry", "tg", "t15", "win", "mp"]


def load_g1():
    C = np.load(os.path.join(CACHE, "stophunt_g1_codes.npy")); S = np.load(os.path.join(CACHE, "stophunt_g1_stats.npy"))
    dimv = {d: np.array([DIMS[d].index(x[d]) for x in SETUPS]) for d in DIMS}
    K = np.zeros((len(C), len(KEY_DIMS)), np.int64)
    for i, d in enumerate(DIMS):
        K[:, i] = dimv[d][C[:, 0]]
    K[:, len(DIMS):] = C[:, 1:]
    return C, S, K


def metrics(S):
    n = S[:, :, 0]; net = S[:, :, 1]
    m = S[:, :, 5] / np.maximum(n, 1)
    sd = np.sqrt(np.maximum(S[:, :, 6] / np.maximum(n, 1) - m * m, 1e-12))
    t = m / (sd / np.sqrt(np.maximum(n, 1)))
    return dict(n=n, net=net, win=100 * S[:, :, 2] / np.maximum(n, 1), pf=S[:, :, 3] / np.maximum(S[:, :, 4], 1e-9), t=t, avg_r=m,
                dd=S[:, :, 7])


RADIX = [len(DIMS[d]) for d in DIMS] + [3, len(G1_TG), 2, len(G1_WIN), 2]


def keyint(K):
    k = np.zeros(len(K), np.int64)
    for i, r in enumerate(RADIX):
        k = k * r + K[:, i]
    return k


NEIGH = {"W": "ord", "body": "ord3", "depth": "flip", "t15": "flip", "mp": "flip", "entry": "mm", "struct": "any", "tg": "any",
         "fvg": "flip"}


def neighbour_keys(row):
    out = []
    for d, how in NEIGH.items():
        i = KEY_DIMS.index(d); v = row[i]; r = RADIX[i]
        cand = []
        if how == "ord":
            cand = [v - 1, v + 1]
        elif how == "ord3":
            cand = [v - 1, v + 1] if v < 3 else [1]
        elif how == "flip":
            cand = [1 - v]
        elif how == "mm":
            cand = [1 - v] if v < 2 else [0]
        else:
            cand = [x for x in range(r) if x != v]
        for c in cand:
            if 0 <= c < r:
                x = row.copy(); x[i] = c
                out.append(x)
    return np.array(out)


def plateau(K, M, ki, sorter, idx, span=0):
    nb = neighbour_keys(K[idx])
    kk = keyint(nb)
    pos = np.searchsorted(ki[sorter], kk)
    pos = np.minimum(pos, len(sorter) - 1)
    hit = ki[sorter][pos] == kk
    j = sorter[pos[hit]]
    if not len(j):
        return 0.0, 0
    return float((M["net"][j, span] > 0).mean()), len(j)


def label(K, i):
    r = K[i]
    vals = [DIMS[d][r[j]] for j, d in enumerate(DIMS)] + [G1_ENTRY[r[7]], G1_TG[r[8]], "t15" if r[9] else "no-t15", G1_WIN[r[10]],
                                                          f"max{G1_MP[r[11]]}"]
    return "|".join(str(v) for v in vals)


def row_txt(M, i):
    f = lambda s: (f"{SPAN_NAMES[s]} n{int(M['n'][i, s])} w{M['win'][i, s]:.0f} pf{min(M['pf'][i, s], 99):.2f} "
                   f"${M['net'][i, s]:+,.0f} t{M['t'][i, s]:.1f}")
    return " | ".join(f(s) for s in range(4))


def cmd_pick(top=25):
    C, S, K = load_g1()
    M = metrics(S)
    ki = keyint(K); sorter = np.argsort(ki)
    g = base()
    nweeks = [x / 5 for x in g["nsess"]]
    out = {"n_variants": int(len(C)), "rules": {}}
    elig = (M["n"][:, 0] >= nweeks[0]) & (M["net"][:, 0] > 0)
    rules = {"A_winrate": elig & (M["win"][:, 0] >= 55) & (M["pf"][:, 0] >= 1.3),
             "B_money": elig & (M["pf"][:, 0] >= 1.3)}
    base_h2 = float((M["net"][M["n"][:, 0] >= nweeks[0], 1] > 0).mean())
    out["base_rate_h2_pos"] = round(base_h2, 3)
    for rn, m in rules.items():
        idx = np.nonzero(m)[0]
        score = M["t"][idx, 0] if rn == "A_winrate" else M["net"][idx, 0]
        o = idx[np.argsort(-score)]
        picks, seen = [], set()
        for i in o:
            sig = (int(M["n"][i, 0]), int(M["net"][i, 0]))
            if sig in seen:
                continue
            fr, nn = plateau(K, M, ki, sorter, i)
            if nn < 5 or fr < 0.8:
                continue
            seen.add(sig)
            picks.append(int(i))
            if len(picks) >= top:
                break
        P = np.array(picks)
        out["rules"][rn] = {"eligible": int(m.sum()), "picks": [{"i": int(i), "label": label(K, i), "row": row_txt(M, i),
                                                                 **{f"{SPAN_NAMES[s]}_{k}": round(float(M[k][i, s]), 2) for s in range(4)
                                                                    for k in ("n", "net", "win", "pf", "t")}} for i in P],
                            "h2_pos_share": round(float((M["net"][P, 1] > 0).mean()), 3) if len(P) else None,
                            "ref_pos_share": round(float(((M["net"][P, 2] > 0) & (M["net"][P, 3] > 0)).mean()), 3) if len(P) else None}
        print(f"== rule {rn}: eligible {m.sum():,}; top {len(P)} plateau picks: H2>0 {out['rules'][rn]['h2_pos_share']} "
              f"(base {base_h2:.3f}), 2025 & 2021-24 > 0 {out['rules'][rn]['ref_pos_share']}")
        for i in P[:top]:
            print("  ", label(K, i)); print("      ", row_txt(M, i))
    os.makedirs(OUT, exist_ok=True)
    json.dump(out, open(os.path.join(OUT, "stage1_picks.json"), "w"), indent=1)
    return out


# ================================================================================================ stage 2 machinery
def context(g):
    """Per 5m bar, from closed bars only: trend = sign(last closed 1h close - its EMA 50); disc = sign(session 18:00 open -
    close) (+1 = price below the open = discount, a long is 'from discount')."""
    if "ctx" in g:
        return g["ctx"]
    import pandas as pd
    B = g["B"]
    H = E.htf(B, 60)
    c1h = B["c"][H["last"]]
    ema = pd.Series(c1h).ewm(span=50, adjust=False).mean().values
    v = np.full(B["n"], np.nan)
    v[H["last"]] = np.sign(c1h - ema)
    trend = pd.Series(v).ffill().fillna(0.0).values
    o18 = B["open18"][B["sid"]]
    disc = np.sign(o18 - B["c"])
    g["ctx"] = dict(trend=trend, disc=disc)
    return g["ctx"]


def ctx_ok(g, X, how):
    if how == "none":
        return np.ones(len(X["sig"]), bool)
    C = context(g)
    if how == "with":
        return C["trend"][X["sig"]] * X["dr"] > 0
    if how == "against":
        return C["trend"][X["sig"]] * X["dr"] < 0
    if how == "disc":
        return C["disc"][X["sig"]] * X["dr"] > 0
    if how == "prem":
        return C["disc"][X["sig"]] * X["dr"] < 0
    raise ValueError(how)


S2_KEYS = ["entry", "max_stop", "tg", "min_rr", "t15", "be", "part", "flat", "ctx", "win", "mp"]


def run_grid2(g, S, opt, keep=None):
    """Every combination of the stage-2 options for one setup: list of (option dict, stats [4, 8])."""
    sg = sigs_of(g, S)
    out = []
    for en in opt["entry"]:
        if en == "fvg" and not S["fvg"]:
            continue
        for ms in opt["max_stop"]:
            X = fills(g, sg, en, max_stop=ms)
            o = np.argsort(X["ft"], kind="stable")
            Xo = {k: v[o] for k, v in X.items()}
            cm = {c: ctx_ok(g, Xo, c) for c in opt["ctx"]}
            for tg in opt["tg"]:
                for mr in opt["min_rr"]:
                    if TARGETS[tg][0] == "R" and mr != opt["min_rr"][0]:
                        continue
                    T = targets(g, Xo, tg, min_rr=mr)
                    for t15 in opt["t15"]:
                        for be in opt["be"]:
                            for part in opt["part"]:
                                for fl in opt["flat"]:
                                    Wk = walk(g, Xo, T, be=be, t15=bool(t15), part=bool(part), flat=fl)
                                    for c in opt["ctx"]:
                                        okc = Wk["ok"] & cm[c]
                                        for wn in opt["win"]:
                                            for mp in opt["mp"]:
                                                st, sel = select_stats(Xo["ft"], Wk["xt"], Xo["sid"], Xo["bucket"], okc, Wk["pnl"],
                                                                       Wk["R"], WINDOWS[wn], mp, g["span_of_sid"], 4, keep is not None)
                                                d = dict(entry=en, max_stop=ms, tg=tg, min_rr=mr, t15=t15, be=be, part=part, flat=fl,
                                                         ctx=c, win=wn, mp=mp)
                                                out.append((d, st))
                                                if keep is not None:
                                                    keep.append((d, Xo, Wk, T, sel))
    return out


def one(g, spec):
    """One full variant spec (setup + options) -> (stats, trade rows)."""
    S = {k: spec[k] for k in DIMS}
    opt = {k: [spec[k]] for k in S2_KEYS}
    keep = []
    R = run_grid2(g, S, opt, keep=keep)
    d, Xo, Wk, T, sel = keep[0]
    return R[0][1], trade_rows(g, Xo, Wk, T, sel, spec.get("name", "stophunt"))


# ================================================================================================ stage 2 grids
OPT_A = dict(entry=["mkt", "mid", "fvg", "c1m"], max_stop=[40.0, 60.0, 80.0, 120.0], tg=list(TARGETS), min_rr=[1.5, 2.0],
             t15=[0, 1], be=["none", "be1", "be1c"], part=[0, 1], flat=["1555", "sess"], ctx=["none", "with", "against", "disc", "prem"],
             win=None, mp=[1, 2])
OPT_B = dict(entry=["mid", "mkt"], max_stop=[60.0, 80.0], tg=["dolA_b3", "dolA_b5", "dolH_b5", "r2", "vix_b8"], min_rr=[1.5],
             t15=[0, 1], be=["none", "be1c"], part=[0], flat=["1555"], ctx=["none", "with", "against", "disc"],
             win=["asia", "asia_e", "asia_l"], mp=[1, 2])
FAM_B = dict(pool=["f15", "htf", "stack", "f5", "all", "eq", "sess"], mode=["rs_pool", "rs", "rs_or_idm", "idm", "any"], W=[12, 24, 36],
             body=["a1.0", "a1.2", "a1.5"], struct=["none", "mss"], fvg=[0], depth=[0.0, 0.25, 0.5])
S2 = {}


def fam_a_setups():
    P = json.load(open(os.path.join(OUT, "stage1_picks.json")))
    seen, out = set(), []
    for rn in P["rules"]:
        for p in P["rules"][rn]["picks"]:
            d = p["label"].split("|")
            S = dict(pool=d[0], mode=d[1], W=int(d[2]), body=d[3], struct=d[4], fvg=int(d[5]), depth=float(d[6]))
            k = json.dumps(S, sort_keys=True)
            if k in seen:
                continue
            seen.add(k)
            out.append((S, d[10]))
    return out


def _s2_job(j):
    g = base()
    fam, S, win0 = S2["jobs"][j]
    opt = dict(OPT_A if fam == "A" else OPT_B)
    if fam == "A":
        opt["win"] = sorted({win0, "all"})
    R = run_grid2(g, S, opt)
    codes = np.array([[j] + [opt[k].index(d[k]) for k in S2_KEYS] for d, _ in R], np.int32)
    return codes, np.array([x for _, x in R], np.float32)


def cmd_stage2(procs=4):
    base()
    jobs = [("A", S, w) for S, w in fam_a_setups()]
    for vals in itertools.product(*FAM_B.values()):
        jobs.append(("B", dict(zip(FAM_B, vals)), None))
    S2["jobs"] = jobs
    json.dump([[f, S, w] for f, S, w in jobs], open(os.path.join(CACHE, "stophunt_s2_jobs.json"), "w"))
    t0 = time.time()
    print(len(jobs), "setups (A:", sum(1 for j in jobs if j[0] == "A"), ")", flush=True)
    for fam in ("A", "B"):
        J = [i for i, j in enumerate(jobs) if j[0] == fam]
        K, ST = [], []
        with Pool(procs) as pool:
            for k, (keys, st) in enumerate(pool.imap(_s2_job, J, chunksize=1 if fam == "A" else 4)):
                K.append(keys); ST.append(st)
                if k % 200 == 0:
                    print(f"  {fam} {k}/{len(J)} {time.time() - t0:.0f}s", flush=True)
        ST = np.concatenate(ST)
        np.save(os.path.join(CACHE, f"stophunt_s2{fam}_stats.npy"), ST)
        np.save(os.path.join(CACHE, f"stophunt_s2{fam}_codes.npy"), np.concatenate(K))
        print(fam, "variants", len(K), f"{time.time() - t0:.0f}s", flush=True)


# ================================================================================================ placebos
@njit(cache=True)
def _plc_many(t, o, h, l, c, rel, sid, fl, k_start, dr, dist, kind, tmo, risk, rr, be_at, be_off, tcb, cut_rel):
    """Placebo trades with the real trade's entry mechanics: from path bar k_start (the first bar after the signal close),
    market at its open + 1 tick (kind 0) or a limit `dist` points below the signal close (kind 1, timeout tmo bars);
    stop = entry - risk, target = entry + rr x risk; same management. pnl per micro pts (nan = no fill)."""
    m = len(k_start)
    PT = np.full(m, np.nan); RK = np.empty(m)
    for i in range(m):
        k = k_start[i]
        if k < 1 or k >= len(o):
            continue
        s = sid[k]
        csig = c[k - 1] if dr[i] > 0 else -c[k - 1]
        lim = math.floor((csig - dist[i]) / 0.25) * 0.25
        k0, e, isl = E_fill(t, o, h, l, c, rel, sid, k, dr[i], kind, lim, -1e18, tmo, s, cut_rel)
        if k0 < 0 or fl[k0] < k0:
            continue
        sp = e - risk[i]
        T = e + rr[i] * risk[i]
        pts, kx, kd, mf, ma = E_walk(o, h, l, c, k0, fl[k0], dr[i], e, sp, risk[i], T, be_at, be_off, tcb, isl, 0.0, 0.5)
        PT[i] = pts
    return PT


def _span_idx(g, days):
    B = g["B"]
    dm = {str(d): i for i, d in enumerate(B["days"])}
    return np.array([g["span_of_sid"][dm[d]] for d in days])


def placebo(g, rows, spec, nsim=2000, seed=7):
    """rows: a pick's trades. Each placebo trade copies a real one's entry mechanics (market, or a limit the same points
    below the signal close with the same timeout), stop points, target R and management; only time or direction change.
      skeleton  the real signals re-run through this machinery (checks it reproduces the real result)
      flip      same signal bars, direction 50/50 at random (the limit mirrored above the close)
      rtime     same direction, a random 5m signal bar of the same session bucket in a random session of the same span
                (1m path in 2026); unfilled limits are redrawn (up to 20 times) so the count matches
    p = share of placebo runs whose net is >= the skeleton's net (one-sided)."""
    rng = np.random.default_rng(seed)
    B = g["B"]; M1 = B["m1"]
    if not rows:
        return {}
    en = spec.get("entry", "mkt")
    kind = 0 if en in ("mkt", "c1m") else 1
    be = spec.get("be", "be1c")
    be_at, be_off = (0.0, 0.0) if be == "none" else (1.0, 0.0 if be == "be1" else 1.25)
    t15 = bool(spec.get("t15"))
    fln = "flat" if spec.get("flat", "1555") == "1555" else "sflat"
    P5 = (B["t"], B["o"], B["h"], B["l"], B["c"], B["rel"], B["sid"], B["flat5"] if fln == "flat" else np.where(B["sflat5"] >= 0, B["sflat5"], B["flat5"]))
    P1 = (M1["t"], M1["o"], M1["h"], M1["l"], M1["c"], M1["rel"], M1["sid"], M1["flat"] if fln == "flat" else np.where(M1["sflat"] >= 0, M1["sflat"], M1["flat"]))
    sigt = np.array([r["signal_t"] for r in rows])
    dr = np.array([r["dir"] for r in rows]); risk = np.array([r["risk_pts"] for r in rows])
    rr = np.array([(r["target"] - r["entry"]) * r["dir"] / r["risk_pts"] for r in rows])
    ks5 = np.searchsorted(B["t"], sigt - 300)
    cs = B["c"][ks5]
    dist = np.where(kind == 1, (cs - np.array([r["entry"] for r in rows])) * dr, 0.0)
    sp = _span_idx(g, [r["day"] for r in rows])

    def run(sig5, d):
        """sig5: 5m signal bar index per trade; d: directions. Returns pnl $ (nan = not filled)."""
        ts = B["t"][sig5] + 300
        use1 = (ts >= B["m1_from"]) & (ts < B["m1_to"])
        out = np.full(len(sig5), np.nan)
        for P_, q, tmo, tcb, kst in ((P5, ~use1, 6 if kind else 1, 3, sig5 + 1), (P1, use1, 30 if kind else 1, 15, np.searchsorted(M1["t"], ts))):
            if not q.any():
                continue
            pts = _plc_many(*P_[:7], P_[7], kst[q], d[q], dist[q], kind, tmo, risk[q], rr[q], be_at, be_off, tcb if t15 else 0, E.ENTRY_CUT)
            qty = np.minimum(MAXQ, np.floor(RISK_USD / (risk[q] * E.PV)))
            out[q] = qty * (pts * E.PV - E.COMM)
        return out

    agg = lambda pn: np.array([np.nansum(pn[sp == s]) for s in range(4)])
    real = np.array([r["pnl_usd"] for r in rows])
    skp = run(ks5, dr)
    sk = agg(skp)
    FL = np.array([agg(run(ks5, np.where(rng.random(len(rows)) < 0.5, dr, -dr))) for _ in range(nsim)])
    rel = B["rel"]
    bk = np.searchsorted(np.array([480, 840, 1080]), rel, side="right")
    elig = (rel <= E.ENTRY_CUT - 5) & (B["flat5"] >= 0)
    sp5 = g["span_of_sid"][B["sid"]]
    rb = np.array([E.BUCKET_NAMES.index(r["session"]) for r in rows])
    pools = {}
    for j in range(len(rows)):
        key = (sp[j], rb[j])
        if key not in pools:
            pools[key] = np.nonzero(elig & (sp5 == sp[j]) & (bk == rb[j]))[0]
    RT = np.zeros((nsim, 4))
    for i in range(nsim):
        pn = np.full(len(rows), np.nan)
        todo = np.arange(len(rows))
        for _ in range(20):
            if not len(todo):
                break
            k5 = np.array([pools[(sp[j], rb[j])][rng.integers(len(pools[(sp[j], rb[j])]))] for j in todo])
            x = np.full(len(rows), np.nan)
            sub = run_sub = None
            x_sub = run_idx(run, k5, todo, dr, len(rows))
            pn[todo] = np.where(np.isnan(pn[todo]), x_sub, pn[todo])
            todo = todo[np.isnan(pn[todo])]
        RT[i] = agg(pn)
    out = {}
    for s in range(4):
        out[SPAN_NAMES[s]] = {"n": int((sp == s).sum()), "real": round(float(real[sp == s].sum())), "skeleton": round(float(sk[s])),
                              "flip_mean": round(float(FL[:, s].mean())), "p_flip": round(float((FL[:, s] >= sk[s]).mean()), 4),
                              "rtime_mean": round(float(RT[:, s].mean())), "p_rtime": round(float((RT[:, s] >= sk[s]).mean()), 4)}
    allr = sk.sum()
    out["all"] = {"real": round(float(real.sum())), "skeleton": round(float(allr)), "p_flip": round(float((FL.sum(1) >= allr).mean()), 4),
                  "p_rtime": round(float((RT.sum(1) >= allr).mean()), 4), "nsim": nsim}
    return out


def run_idx(run, k5, todo, dr, n):
    """run() on a subset of trades: the other trades' inputs are kept but their results dropped."""
    full = np.zeros(n, np.int64)
    full[todo] = k5
    # trades not in todo: give them a valid bar (their own result is ignored)
    rest = np.setdiff1d(np.arange(n), todo)
    full[rest] = k5[0] if len(k5) else 0
    return run(full, dr)[todo]


# ================================================================================================ stage 2 analysis
def load_s2(fam):
    C = np.load(os.path.join(CACHE, f"stophunt_s2{fam}_codes.npy")); S = np.load(os.path.join(CACHE, f"stophunt_s2{fam}_stats.npy"))
    jobs = json.load(open(os.path.join(CACHE, "stophunt_s2_jobs.json")))
    return C, S, jobs


def s2_opt(fam, job):
    opt = dict(OPT_A if fam == "A" else OPT_B)
    if fam == "A":
        opt["win"] = sorted({job[2], "all"})
    return opt


def s2_spec(fam, C, jobs, i):
    job = jobs[C[i, 0]]
    opt = s2_opt(fam, job)
    return {**job[1], **{k: opt[k][C[i, 1 + j]] for j, k in enumerate(S2_KEYS)}}


def s2_codes(fam, C, jobs):
    """Full code matrix: setup dims (B: grid indices; A: job id) + option indices, with radix and neighbour kinds."""
    if fam == "B":
        sd = list(FAM_B)
        M = np.array([[FAM_B[d].index(jobs[j][1][d]) for d in sd] for j in range(len(jobs))] if False else
                     [[FAM_B[d].index(jobs[j][1][d]) if jobs[j][0] == "B" else 0 for d in sd] for j in range(len(jobs))])
        K = np.c_[M[C[:, 0]], C[:, 1:]]
        radix = [len(FAM_B[d]) for d in sd] + [len(OPT_B[k]) for k in S2_KEYS]
        names = sd + S2_KEYS
        nb = {"W": "ord", "body": "ord", "depth": "ord", "struct": "any", "mode": "any", "entry": "any", "max_stop": "ord",
              "tg": "any", "t15": "any", "be": "any", "mp": "any"}
    else:
        K = C.copy()
        radix = [len(jobs)] + [max(len(OPT_A[k]) if OPT_A[k] else 2, 2) for k in S2_KEYS]
        names = ["job"] + S2_KEYS
        nb = {"entry": "any", "max_stop": "ord", "tg": "any", "min_rr": "any", "t15": "any", "be": "any", "part": "any",
              "flat": "any", "mp": "any"}
    return K.astype(np.int64), radix, names, nb


def _kint(K, radix):
    k = np.zeros(len(K), np.int64)
    for i, r in enumerate(radix):
        k = k * r + K[:, i]
    return k


def plateau2(K, radix, names, nb, ki, sorter, i, net, span=0):
    row = K[i]
    cands = []
    for d, how in nb.items():
        j = names.index(d); v = row[j]
        vals = [v - 1, v + 1] if how == "ord" else [x for x in range(radix[j]) if x != v]
        for x in vals:
            if 0 <= x < radix[j]:
                r2 = row.copy(); r2[j] = x; cands.append(r2)
    if not cands:
        return 0.0, 0
    kk = _kint(np.array(cands), radix)
    pos = np.minimum(np.searchsorted(ki[sorter], kk), len(sorter) - 1)
    hit = ki[sorter][pos] == kk
    jj = sorter[pos[hit]]
    return (float((net[jj, span] > 0).mean()) if len(jj) else 0.0), len(jj)


def s2_pick(fam, rule="money", top=15, min_tpw=1.0, robust=False, quiet=False):
    C, S, jobs = load_s2(fam)
    M = metrics(S)
    g = base()
    nwk = [x / 5 for x in g["nsess"]]
    K, radix, names, nb = s2_codes(fam, C, jobs)
    ki = _kint(K, radix); sorter = np.argsort(ki)
    el = (M["n"][:, 0] >= min_tpw * nwk[0]) & (M["net"][:, 0] > 0) & (M["pf"][:, 0] >= 1.3)
    if rule == "winrate":
        el &= M["win"][:, 0] >= 55
    if robust:
        el &= (M["n"][:, 2] >= 20) & (M["n"][:, 3] >= 60)
        score = np.min(M["t"][:, [0, 2, 3]], 1)            # never H2: H2 stays the check
    else:
        score = M["t"][:, 0] if rule == "winrate" else M["net"][:, 0]
    idx = np.nonzero(el)[0]
    o = idx[np.argsort(-score[idx])]
    picks, seen = [], set()
    for i in o:
        sig = (int(M["n"][i, 0]), int(M["net"][i, 0]), int(M["n"][i, 3]))
        if sig in seen:
            continue
        fr, nn = plateau2(K, radix, names, nb, ki, sorter, i, M["net"], 0)
        if nn < 5 or fr < 0.8:
            continue
        if robust:
            fr2, _ = plateau2(K, radix, names, nb, ki, sorter, i, M["net"], 3)
            if fr2 < 0.8:
                continue
        seen.add(sig)
        picks.append(int(i))
        if len(picks) >= top:
            break
    base_h2 = float((M["net"][M["n"][:, 0] >= nwk[0], 1] > 0).mean())
    res = {"family": fam, "rule": rule, "robust": robust, "n_variants": int(len(C)), "eligible": int(el.sum()), "base_h2_pos": round(base_h2, 3),
           "picks": [{"i": i, "spec": s2_spec(fam, C, jobs, i), "row": row_txt(M, i),
                      **{f"{SPAN_NAMES[s]}_{k}": round(float(M[k][i, s]), 2) for s in range(4) for k in ("n", "net", "win", "pf", "t")}}
                     for i in picks]}
    res["h2_pos_share"] = round(float(np.mean([p["H2_net"] > 0 for p in res["picks"]])), 3) if picks else None
    if not quiet:
        print(f"== stage 2 {fam} rule {rule} robust={robust}: {len(C):,} variants, eligible {el.sum():,}, picks H2>0 {res['h2_pos_share']} (base {base_h2:.3f})")
        for p in res["picks"]:
            sp = p["spec"]
            print("  ", "|".join(str(sp[k]) for k in list(DIMS) + S2_KEYS)); print("      ", p["row"])
    return res


def cmd_pick2():
    out = {}
    for fam in ("A", "B"):
        for rule in ("winrate", "money"):
            out[f"{fam}_{rule}"] = s2_pick(fam, rule)
        out[f"{fam}_robust"] = s2_pick(fam, "money", robust=True)
    json.dump(out, open(os.path.join(OUT, "stage2_picks.json"), "w"), indent=1, default=str)


# ================================================================================================ stage 3 refinement
FAM3 = {
    "asia": (dict(pool=["htf", "f15", "f60", "stack", "eq", "sess"], mode=["any", "rs", "rs_pool", "rs_or_idm", "idm"], W=[24, 36, 48, 60],
                  body=["a1.0", "a1.2", "a1.5", "a2.0"], struct=["mss", "cisd", "none"], fvg=[0], depth=[0.25, 0.5, 0.75, 1.0]),
             dict(entry=["mkt", "mid", "c1m"], max_stop=[80.0, 120.0], tg=["r1.5", "r2", "r3", "dolA_b5", "dolH_b5"],
                  min_rr=[1.5], t15=[0, 1], be=["none", "be1c"], part=[0], flat=["1555"], ctx=["none", "with"],
                  win=["asia", "asia_e", "asia_l"], mp=[1, 2])),
    "trend": (dict(pool=["all", "f5", "f15", "htf", "stack", "tl", "eq"], mode=["any", "rs", "pre", "idm"], W=[6, 12, 24],
                   body=["a0.8", "a1.0", "a1.2", "a1.5"], struct=["mss", "cisd"], fvg=[0, 1], depth=[0.0, 0.25, 0.5]),
              dict(entry=["mkt", "mid", "c1m"], max_stop=[60.0, 80.0], tg=["r2", "r3", "dolA_b3", "dolA_b5", "dolH_b5", "vix_b8"],
                   min_rr=[1.5], t15=[0, 1], be=["none", "be1c"], part=[0], flat=["1555"], ctx=["with"],
                   win=["all", "day", "ny", "asia_lon"], mp=[1, 2])),
}


def _s3_job(j):
    g = base()
    fam, S = S2["jobs3"][j]
    R = run_grid2(g, S, FAM3[fam][1])
    opt = FAM3[fam][1]
    codes = np.array([[j] + [opt[k].index(d[k]) for k in S2_KEYS] for d, _ in R], np.int32)
    return codes, np.array([x for _, x in R], np.float32)


def cmd_stage3(procs=4):
    base()
    for fam in FAM3:
        sd = FAM3[fam][0]
        jobs = [(fam, dict(zip(sd, v))) for v in itertools.product(*sd.values())]
        S2["jobs3"] = jobs
        json.dump(jobs, open(os.path.join(CACHE, f"stophunt_s3{fam}_jobs.json"), "w"))
        t0 = time.time()
        K, ST = [], []
        with Pool(procs) as pool:
            for k, (c, st) in enumerate(pool.imap(_s3_job, range(len(jobs)), chunksize=2)):
                K.append(c); ST.append(st)
                if k % 500 == 0:
                    print(f"  {fam} {k}/{len(jobs)} {time.time() - t0:.0f}s", flush=True)
        np.save(os.path.join(CACHE, f"stophunt_s3{fam}_codes.npy"), np.concatenate(K))
        np.save(os.path.join(CACHE, f"stophunt_s3{fam}_stats.npy"), np.concatenate(ST))
        print(fam, "setups", len(jobs), "variants", sum(len(x) for x in K), f"{time.time() - t0:.0f}s", flush=True)


# ================================================================================================ final report pieces
MODE_TXT = {"any": "no extra condition after the hunt", "fast": "the reclaim comes at once (within 1 bar of the hunt)",
            "rs_pool": "a RESWEEP first: after a close back inside, price runs the same pool again",
            "rs_ext": "a RESWEEP first: after a bounce of 0.5 ATR, price takes the hunt's own new extreme (double stop hunt)",
            "rs": "a RESWEEP first: the same pool re-run after a close back inside, or the hunt's new extreme taken after a 0.5 ATR bounce",
            "idm": "an INDUCEMENT first: a small swing formed after the hunt (early reversal traders' stops) is taken",
            "pre": "an INDUCEMENT before the hunt (LIT style): a 5m swing within 1 ATR of the pool was taken on the way in",
            "rs_idm": "both a resweep and an inducement first", "rs_or_idm": "a resweep or an inducement first"}
TG_TXT = {"r1.5": "fixed 1.5R", "r2": "fixed 2R", "r3": "fixed 3R", "dolA": "the nearest untaken opposite pool (any type) >= {mr}R away",
          "dolA_b3": "the nearest untaken opposite pool (any type) >= {mr}R away, banked at 3R",
          "dolA_b5": "the nearest untaken opposite pool (any type) >= {mr}R away, banked at 5R",
          "dolH": "the nearest untaken higher-timeframe opposite pool (score >= 2) >= {mr}R away",
          "dolH_b3": "the nearest untaken higher-timeframe opposite pool (score >= 2) >= {mr}R away, banked at 3R",
          "dolH_b5": "the nearest untaken higher-timeframe opposite pool (score >= 2) >= {mr}R away, banked at 5R",
          "dolO": "the nearest untaken obvious opposite pool (score >= 3) >= {mr}R away",
          "dolO_b5": "the nearest untaken obvious opposite pool (score >= 3) >= {mr}R away, banked at 5R",
          "vix_b8": "LIT's VIX band (18:00 open +/- 1 VIX one-day move) if >= {mr}R away, banked at 8R"}
WIN_TXT = {"all": "any hour 18:00-15:30 ET", "asia": "Asia 18:00-02:00 ET", "asia_e": "early Asia 18:00-22:00 ET", "asia_l": "late Asia 22:00-02:00 ET",
           "lon": "London 02:00-08:00 ET", "nyam": "NY AM 08:00-12:00 ET", "nypm": "NY PM 12:00-15:30 ET", "ny": "NY 08:00-15:30 ET",
           "day": "02:00-15:30 ET (LIT's hours)", "asia_lon": "18:00-08:00 ET"}


def rules_text(sp):
    body = BODY_SPEC[sp["body"]]
    btxt = f"a body >= {body[0]} x ATR(14, 5m)" if body[1] == 0 else f"a body >= {body[0]} x the average body of the 10 bars before"
    st = {"none": "closing back beyond the pool", "cisd": "closing back beyond the pool and beyond the CISD level (the open of the run of candles into the extreme)",
          "mss": "closing back beyond the pool and beyond the last confirmed 5m swing the other way (market structure shift)"}[sp["struct"]]
    ent = {"mkt": "market at the next 5m open + 1 tick", "mid": "a limit at the middle of the trigger candle for 30 minutes",
           "fvg": "a limit at the near edge of the trigger candle's fair value gap for 30 minutes",
           "c1m": "a 1m CISD within 20 minutes after the signal, then the next 1m open + 1 tick (5m bars before 2026)"}[sp["entry"]]
    ctx = {"none": "", "with": " Only in the direction of the 1h trend (last closed 1h close vs its EMA 50): the hunt is a pullback against the trend.",
           "against": " Only against the 1h trend.", "disc": " Longs only below the 18:00 open, shorts only above it.",
           "prem": " Longs only above the 18:00 open, shorts only below it."}[sp["ctx"]]
    be = {"none": "no breakeven", "be1": "stop to entry at +1R", "be1c": "stop to entry + 1.25 pts at +1R (LIT's BE + costs)"}[sp["be"]]
    dep = "" if not sp["depth"] else f" and the hunt reaches >= {sp['depth']} ATR beyond it"
    out = [f"Pools (where retail stops sit, each known before it is used): {POOL_SETS[sp['pool']][4]}.",
           f"Hunt: a 5m bar trades 1+ tick through the pool{dep}.",
           f"Then: {MODE_TXT[sp['mode']]}.",
           f"Trigger within {sp['W']} 5m bars of the hunt: a strong candle back toward the draw, {btxt}, {st}"
           + (", leaving a fair value gap (the signal is the bar after)" if sp["fvg"] else "") + ".",
           f"Entry: {ent}. Hours: {WIN_TXT[sp['win']]}; max {sp['mp']} trade(s) a session, one position at a time.{ctx}",
           f"Stop: 1 tick beyond the hunt extreme (the protected low/high); stop 6-{sp['max_stop']:.0f} pts, else no trade; size follows the stop.",
           f"Target: {TG_TXT[sp['tg']].format(mr=sp['min_rr'])}; no target that far = no trade.",
           f"Management: {be}" + ("; LIT's 15-minute check (15 min after the fill: never +0.5R and the close more than 0.3R against -> out at the next open)" if sp["t15"] else "")
           + ("; half off at the first pool on the way (>= 1R), then BE" if sp["part"] else "")
           + ("; flat at the end of the entry's session (Asia 02:00, London 08:00, NY AM 12:00)" if sp["flat"] == "sess" else "")
           + "; flat 15:55 ET (MFFU: flat by 16:10).",
           "Costs: $1.90 a micro round trip + 1 tick slippage on market entries and stop / time / flat exits. Scored at $500 risk a trade."]
    return out


def span_table(rows, g):
    out = {}
    sp = _span_idx(g, [r["day"] for r in rows]) if rows else np.zeros(0)
    for s, nm in enumerate(SPAN_NAMES):
        R = [r for r, x in zip(rows, sp) if x == s]
        p = np.array([r["pnl_usd"] for r in R]) if R else np.zeros(0)
        nw = g["nsess"][s] / 5
        if not len(p):
            out[nm] = {"n": 0}
            continue
        eq = np.cumsum(p)
        dd = float((eq - np.maximum.accumulate(np.r_[0.0, eq])[1:]).min())
        gl = -p[p < 0].sum()
        top3 = np.sort(p)[::-1][:3].sum()
        wk = collections.Counter()
        import datetime as _dt
        for r in R:
            y, w, _ = _dt.date.fromisoformat(r["day"]).isocalendar()
            wk[(y, w)] += 1
        out[nm] = {"n": len(p), "tpw": round(len(p) / nw, 2), "win": round(100 * float((p > 0).mean()), 1),
                   "pf": round(float(p[p > 0].sum() / gl), 2) if gl else None, "net": round(float(p.sum())),
                   "per_month": round(float(p.sum()) / (g["nsess"][s] / 21)), "dd": round(dd),
                   "avg_r": round(float(np.mean([r["r"] for r in R])), 3), "net_wo_best3": round(float(p.sum() - top3)),
                   "wk2_pct": round(100 * sum(1 for v in wk.values() if v >= 2) / max(nw, 1), 1),
                   "sessions": {b: [sum(1 for r in R if r["session"] == b), round(sum(r["pnl_usd"] for r in R if r["session"] == b))]
                                for b in E.BUCKET_NAMES},
                   "exits": dict(collections.Counter(r["exit_kind"] for r in R))}
    return out


def months_table(rows):
    m = collections.OrderedDict()
    for r in sorted(rows, key=lambda r: r["entry_t"]):
        x = m.setdefault(r["day"][:7], {"n": 0, "wins": 0, "net": 0.0})
        x["n"] += 1; x["wins"] += int(r["pnl_usd"] > 0); x["net"] = round(x["net"] + r["pnl_usd"], 2)
    return m


def lookahead(spec, rows, n=25, seed=3):
    """Re-derive sampled trades from data cut at their signal close (only bars that opened before it): the same signal
    (bar, direction, stop at the hunt extreme, pool) and the same target must appear. Returns (checked, identical, diffs)."""
    rng = np.random.default_rng(seed)
    idx = sorted(rng.choice(len(rows), size=min(n, len(rows)), replace=False))
    ok, diffs = 0, []
    S = {k: spec[k] for k in DIMS}
    for i in idx:
        r = rows[i]
        g2 = base(cut_t=r["signal_t"])
        sg = sigs_of(g2, S)
        B2 = g2["B"]
        ks = int(np.searchsorted(B2["t"], r["signal_t"] - 300))
        hit = np.nonzero((sg["sig"] == ks) & (sg["dr"] == r["dir"]))[0]
        if not len(hit):
            diffs.append({"day": r["day"], "why": "no signal on cut data"})
            continue
        h = hit[0]
        stop = r["dir"] * (sg["ext"][h] - 0.25)
        same = abs(stop - r["stop"]) < 1e-6 and abs(r["dir"] * sg["p"][h] - r["pool_px"]) < 0.01
        X = {"sig": np.array([ks]), "dr": np.array([r["dir"]]), "e": np.array([r["dir"] * r["entry"]]),
             "risk": np.array([r["risk_pts"]]), "sid": np.array([B2["sid"][ks]])}
        T = targets(g2, X, spec["tg"], min_rr=spec["min_rr"])[0]
        same = same and abs(r["dir"] * T - r["target"]) < 0.01
        if spec["ctx"] != "none":
            same = same and bool(ctx_ok(g2, {"sig": np.array([ks]), "dr": np.array([r["dir"]])}, spec["ctx"])[0])
        if same:
            ok += 1
        else:
            diffs.append({"day": r["day"], "stop": [r["stop"], stop], "pool": [r["pool_px"], r["dir"] * float(sg["p"][h])],
                          "target": [r["target"], r["dir"] * float(T)]})
    return len(idx), ok, diffs


# ================================================================================================ eval paths
EVAL_KEYS = ("n", "tpw", "net", "per_month", "dd", "pf", "p10", "f10", "p20", "f20", "pass_med", "b2b")


def _ev_short(o):
    return {k: o.get(k) for k in EVAL_KEYS + ("s10", "dead10", "p60", "f60", "lit_lost", "by_src", "max_risk", "med_risk") if k in o}


def evals(names):
    """MFFU eval paths with the repo's own executors (tools/second_mix.py, tools/second_account_b.py; no re-tuning):
      own account    the pick alone on its own Builder 50K / Builder 25K, the plan's two_week "need" size (engine/account_b.qty),
                     never opposite to LIT on the other account (no-hedge), max 2 a day, fresh eval every session, 20 sessions
      with LIT 50K   LIT (live rules + live two_week sizing) and the pick on ONE Builder 50K: LIT first (a LIT entry flattens an
                     open stop-hunt trade), one position, max 2 a day with a slot kept for LIT; pick sized usd500_safe_dll /
                     need0.5 / need1.0 (tools/second_mix.second_q)
      ATLAS 25K      the pick as a 4th ATLAS member on account B (EMA + MD + SR + pick), Builder 25K, need size, no-hedge
    names: pick names with research/stophunt/<name>.json (common trade format)."""
    from tools import second_mix as M
    from tools import second_account_b as AB
    U = M.units()
    out = {}
    for nm in names:
        M.SECOND[nm] = os.path.join("..", "stophunt", nm + ".json")
        U[nm] = M.second_units(nm)
    res = {"LIT_alone_50k": {s: _ev_short(M.score_span(M.combo_units(()), "usd500", s)[0]) for s in M.SPANS}}
    with AB.Plan("builder25k") as pl:
        UA = M.acct_units(("EMA", "MD", "SR"), nohedge=True)
        res["ATLAS_25k"] = {s: _ev_short(AB.score(UA, "acctb_need", s, pl.safe_rule)[0]) for s in AB.SPANS}
    for nm in names:
        r = {}
        for plan in ("builder50k", "builder25k"):
            with AB.Plan(plan) as pl:
                Uo = M.acct_units((nm,), nohedge=True)
                r[f"own_{plan}"] = {s: _ev_short(AB.score(Uo, "acctb_need", s, pl.safe_rule)[0]) for s in AB.SPANS}
        for rule in ("usd500_safe_dll", "need0.5", "need1.0"):
            r[f"withLIT_50k_{rule}"] = {s: _ev_short(M.score_span(list(U["LIT"]) + list(U[nm]), rule, s, pre=True)[0]) for s in M.SPANS}
        with AB.Plan("builder25k") as pl:
            UA2 = M.acct_units(("EMA", "MD", "SR", nm), nohedge=True)
            r["ATLAS_plus_25k"] = {s: _ev_short(AB.score(UA2, "acctb_need", s, pl.safe_rule)[0]) for s in AB.SPANS}
        res[nm] = r
    return res


# ================================================================================================ stage 3 analysis
def load_s3(fam):
    C = np.load(os.path.join(CACHE, f"stophunt_s3{fam}_codes.npy")); S = np.load(os.path.join(CACHE, f"stophunt_s3{fam}_stats.npy"))
    jobs = json.load(open(os.path.join(CACHE, f"stophunt_s3{fam}_jobs.json")))
    sd, opt = FAM3[fam]
    G_ = np.array([[sd[d].index(j[1][d]) for d in sd] for j in jobs])
    K = np.c_[G_[C[:, 0]], C[:, 1:]].astype(np.int64)
    radix = [len(sd[d]) for d in sd] + [len(opt[k]) for k in S2_KEYS]
    names = list(sd) + S2_KEYS
    nb = {"W": "ord", "body": "ord", "depth": "ord", "struct": "any", "mode": "any", "fvg": "any", "entry": "any", "max_stop": "ord",
          "tg": "any", "t15": "any", "be": "any", "mp": "any"}
    spec = lambda i: {**jobs[C[i, 0]][1], **{k: opt[k][C[i, 1 + j]] for j, k in enumerate(S2_KEYS)}}
    return C, S, K, radix, names, nb, spec


def s3_pick(fam, rule="robust", top=12, min_tpw=1.0, quiet=False, data=None):
    C, S, K, radix, names, nb, spec = data or load_s3(fam)
    M = metrics(S)
    g = base()
    nwk = [x / 5 for x in g["nsess"]]
    ki = _kint(K, radix); sorter = np.argsort(ki)
    el = (M["n"][:, 0] >= min_tpw * nwk[0]) & (M["net"][:, 0] > 0) & (M["pf"][:, 0] >= 1.3)
    if rule == "winrate":
        el &= M["win"][:, 0] >= 55
        score = M["t"][:, 0]
    elif rule == "money":
        score = M["net"][:, 0]
    else:
        el &= (M["n"][:, 2] >= 0.5 * nwk[2]) & (M["n"][:, 3] >= 0.5 * nwk[3])
        if rule == "robust_win":
            el &= (M["win"][:, 0] >= 55) & (M["win"][:, 2] >= 52) & (M["win"][:, 3] >= 52)
        score = np.min(M["t"][:, [0, 2, 3]], 1)
    idx = np.nonzero(el)[0]
    o = idx[np.argsort(-score[idx])]
    picks, seen = [], set()
    for i in o:
        sig = (int(M["n"][i, 0]), int(M["net"][i, 0]), int(M["n"][i, 3]), int(M["net"][i, 3]))
        if sig in seen:
            continue
        fr, nn = plateau2(K, radix, names, nb, ki, sorter, i, M["net"], 0)
        if nn < 5 or fr < 0.8:
            continue
        fr3 = None
        if rule.startswith("robust"):
            fr3, _ = plateau2(K, radix, names, nb, ki, sorter, i, M["net"], 3)
            if fr3 < 0.8:
                continue
        seen.add(sig)
        picks.append((int(i), fr, fr3, nn))
        if len(picks) >= top:
            break
    base_h2 = float((M["net"][M["n"][:, 0] >= min_tpw * nwk[0], 1] > 0).mean())
    res = {"family": fam, "rule": rule, "n_variants": int(len(C)), "eligible": int(el.sum()), "base_h2_pos": round(base_h2, 3),
           "picks": [{"i": i, "plateau_h1": round(fr, 2), "plateau_2124": fr3, "neighbours": nn, "spec": spec(i), "row": row_txt(M, i),
                      **{f"{SPAN_NAMES[s]}_{k}": round(float(M[k][i, s]), 2) for s in range(4) for k in ("n", "net", "win", "pf", "t")}}
                     for i, fr, fr3, nn in picks]}
    res["h2_pos_share"] = round(float(np.mean([p["H2_net"] > 0 for p in res["picks"]])), 3) if picks else None
    if not quiet:
        print(f"== stage 3 {fam} rule {rule}: {len(C):,} variants, eligible {el.sum():,}, picks H2>0 {res['h2_pos_share']} (base {base_h2:.3f})")
        for p_ in res["picks"]:
            sp = p_["spec"]
            print("  ", "|".join(str(sp[k]) for k in list(DIMS) + S2_KEYS), f"plateau {p_['plateau_h1']}/{p_['plateau_2124']}")
            print("      ", p_["row"])
    return res


def cmd_pick3():
    out = {}
    for fam in FAM3:
        data = load_s3(fam)
        for rule in ("winrate", "money", "robust", "robust_win"):
            out[f"{fam}_{rule}"] = s3_pick(fam, rule, data=data)
    json.dump(out, open(os.path.join(OUT, "stage3_picks.json"), "w"), indent=1, default=str)


# ================================================================================================ final picks
_B = dict(min_rr=1.5, part=0, flat="1555", fvg=0)
FINAL = {
    "sh_asia_resweep": dict(_B, name="sh_asia_resweep", title="Asia stop hunt with a resweep (HTF pools, fixed 2R)",
                            pool="htf", mode="rs", W=36, body="a1.2", struct="mss", depth=0.5, entry="mkt", max_stop=80.0, tg="r2",
                            t15=0, be="be1c", ctx="none", win="asia", mp=1),
    "sh_trend_idm": dict(_B, name="sh_trend_idm", title="Trend stop hunt with an inducement first (any pool, DOL target)",
                         pool="all", mode="pre", W=6, body="a1.2", struct="mss", depth=0.5, entry="mid", max_stop=80.0, tg="dolA_b5",
                         t15=0, be="be1c", ctx="with", win="all", mp=1),
    "sh_trend_idm5": dict(_B, name="sh_trend_idm5", title="Trend stop hunt with an inducement first (5m swings, fixed 2R)",
                          pool="f5", mode="pre", W=6, body="a1.2", struct="mss", depth=0.25, entry="mid", max_stop=80.0, tg="r2",
                          t15=0, be="be1c", ctx="with", win="all", mp=2),
}


def sens(g, spec):
    """One-change sensitivity of a pick: management / entry / target / hours swaps (scored the same way)."""
    alts = [("part", 1), ("flat", "sess"), ("t15", 1 - spec["t15"]), ("be", "none"), ("be", "be1"), ("entry", "mkt"), ("entry", "mid"),
            ("entry", "c1m"), ("max_stop", 60.0), ("max_stop", 120.0), ("tg", "r1.5"), ("tg", "r3"), ("tg", "dolA_b5"), ("tg", "dolH_b5"),
            ("tg", "vix_b8"), ("mp", 3 - spec["mp"]), ("ctx", "none"), ("W", 24), ("W", 12), ("body", "a1.0"), ("body", "a1.5"),
            ("depth", 0.25), ("depth", 0.75), ("pool", "all"), ("pool", "htf"), ("pool", "f15"), ("pool", "f5"), ("pool", "sess"), ("pool", "day"),
            ("pool", "eq"), ("pool", "tl"), ("pool", "range"), ("pool", "round"), ("pool", "obv"), ("pool", "stack"),
            ("mode", "any"), ("mode", "rs"), ("mode", "idm"), ("mode", "pre"), ("mode", "rs_or_idm")]
    out = []
    for k, v in alts:
        if spec.get(k) == v:
            continue
        sp = {**spec, k: v}
        st, _ = one(g, sp)
        out.append({"change": f"{k}={v}", **{SPAN_NAMES[s]: stats_dict(st, g["nsess"], s) for s in range(4)}})
    return out


def common(rows):
    keep = ("day", "entry_t", "exit_t", "dir", "entry", "stop", "target", "exit", "exit_kind", "r", "qty", "pnl_usd", "setup",
            "risk_pts", "session", "hunt_t", "signal_t", "pool_px", "pool_score", "flags", "path")
    return [{k: r[k] for k in keep} for r in rows]


def cmd_final(nsim=2000):
    g = base()
    os.makedirs(OUT, exist_ok=True)
    summary = {}
    for nm, spec in FINAL.items():
        t0 = time.time()
        st, rows = one(g, spec)
        rows = [r for r in rows if r["day"] >= "2021-11-01"]
        rep = {"name": nm, "title": spec["title"], "built": time.strftime("%Y-%m-%d %H:%M"), "params": {k: spec[k] for k in list(DIMS) + S2_KEYS},
               "rules": rules_text(spec), "code": "engine/stophunt.py + tools/stophunt.py (FINAL)",
               "data": "TradingView CME NQ1! 5m (data/NQ_5m.csv) for pools / hunts / signals; trades walked on 1m bars in 2026 (data/NQ_1m.csv), 5m before",
               "costs": "$1.90 a micro round trip + 1 tick slippage on market entries and stop / time / flat exits; $500 risk a trade (max 50 micros)",
               "spans": span_table(rows, g), "months": months_table(rows)}
        # one extra tick of slippage each side
        rows2 = [{**r, "pnl_usd": r["pnl_usd"] - r["qty"] * 1.0} for r in rows]
        rep["slip_plus1"] = {k: {"net": v.get("net"), "pf": v.get("pf")} for k, v in span_table(rows2, g).items()}
        rep["placebo"] = placebo(g, rows, spec, nsim=nsim)
        n, ok, diffs = lookahead(spec, rows, n=40, seed=11)
        rep["lookahead"] = {"checked": n, "identical": ok, "diffs": diffs[:5]}
        rep["sensitivity"] = sens(g, spec)
        rep["trades"] = common(rows)
        json.dump(rep, open(os.path.join(OUT, nm + ".json"), "w"), indent=1, default=str)
        summary[nm] = {k: rep[k] for k in ("title", "spans", "placebo", "lookahead", "slip_plus1")}
        print(nm, f"{time.time() - t0:.0f}s", "lookahead", n, ok, flush=True)
        for sname, v in rep["spans"].items():
            print(f"   {sname:8s} {v}")
        print("   placebo", json.dumps(rep["placebo"]))
    json.dump(summary, open(os.path.join(OUT, "final_summary.json"), "w"), indent=1, default=str)


# ================================================================================================ multiple-testing summary
def _chance(S, min_n=(25, 10, 25, 50)):
    M = metrics(S)
    ok = np.ones(len(S), bool)
    for s, m in enumerate(min_n):
        ok &= M["n"][:, s] >= m
    pos = M["net"][ok] > 0
    t = M["t"][ok]
    p = pos.mean(0)
    sig = np.round(np.c_[M["n"][ok], M["net"][ok]]).astype(np.int64)
    distinct = len(np.unique(sig, axis=0)) if len(sig) else 0
    a = pos[:, 0] & pos[:, 2] & pos[:, 3]
    t1 = (t > 1)
    return {"variants": int(len(S)), "with_enough_trades": int(ok.sum()), "distinct": int(distinct),
            "p_pos": {SPAN_NAMES[i]: round(float(p[i]), 3) for i in range(4)},
            "sign_corr_H1_H2": round(float(np.corrcoef(pos[:, 0], pos[:, 1])[0, 1]), 3),
            "t_corr_H1_H2": round(float(np.corrcoef(t[:, 0], t[:, 1])[0, 1]), 3),
            "t_corr_2025_2124": round(float(np.corrcoef(t[:, 2], t[:, 3])[0, 1]), 3),
            "all4_pos_obs": int(pos.all(1).sum()), "all4_pos_exp_indep": round(float(np.prod(p) * ok.sum()), 1),
            "t1_all4_obs": int(t1.all(1).sum()), "t1_all4_exp_indep": round(float(np.prod(t1.mean(0)) * ok.sum()), 1),
            "t1_H1_2025_2124_obs": int((t1[:, 0] & t1[:, 2] & t1[:, 3]).sum()),
            "t1_H1_2025_2124_exp": round(float(t1[:, 0].mean() * t1[:, 2].mean() * t1[:, 3].mean() * ok.sum()), 1),
            "p_H2pos_given_H1_2025_2124_pos": round(float(pos[a, 1].mean()), 3) if a.any() else None,
            "p_H2pos_given_t1_H1_2025_2124": round(float(pos[t1[:, 0] & t1[:, 2] & t1[:, 3], 1].mean()), 3) if (t1[:, 0] & t1[:, 2] & t1[:, 3]).any() else None}


def marginals(S, K, dims, labels):
    """Pooled avg R and win % per value of each dimension (variants with 15+ H1 trades)."""
    M = metrics(S)
    ok = M["n"][:, 0] >= 15
    out = {}
    for j, d in enumerate(dims):
        out[d] = {}
        for v, lab in enumerate(labels[d]):
            m = ok & (K[:, j] == v)
            if not m.any():
                continue
            n = S[m, :, 0].sum(0)
            out[d][str(lab)] = {"variants": int(m.sum()), "avg_r": [round(float(x), 3) for x in S[m, :, 5].sum(0) / np.maximum(n, 1)],
                                "win": [round(float(x), 1) for x in 100 * S[m, :, 2].sum(0) / np.maximum(n, 1)],
                                "pos": [round(float(x), 2) for x in (M["net"][m] > 0).mean(0)]}
    return out


def cmd_summary():
    out = {"spans": SPAN_NAMES, "stages": {}}
    C, S, K = load_g1()
    out["stages"]["stage1"] = _chance(S)
    labels = {**{d: DIMS[d] for d in DIMS}, "entry": G1_ENTRY, "tg": G1_TG, "t15": [0, 1], "win": G1_WIN, "mp": G1_MP}
    out["marginals_stage1"] = marginals(S, K, KEY_DIMS, labels)
    for fam in ("A", "B"):
        C2, S2_, jobs = load_s2(fam)
        out["stages"][f"stage2{fam}"] = _chance(S2_)
    for fam in FAM3:
        d = load_s3(fam)
        out["stages"][f"stage3_{fam}"] = _chance(d[1])
    tot = sum(v["variants"] for v in out["stages"].values())
    out["total_variants"] = int(tot)
    for f in ("stage1_picks.json", "stage2_picks.json", "stage3_picks.json"):
        fp = os.path.join(OUT, f)
        if os.path.exists(fp):
            P = json.load(open(fp))
            if "rules" in P:
                out[f] = {k: {"h2_pos_share": v["h2_pos_share"], "base": P["base_rate_h2_pos"], "eligible": v["eligible"]} for k, v in P["rules"].items()}
            else:
                out[f] = {k: {"h2_pos_share": v["h2_pos_share"], "base": v["base_h2_pos"], "eligible": v["eligible"], "variants": v["n_variants"]} for k, v in P.items()}
    json.dump(out, open(os.path.join(OUT, "search_summary.json"), "w"), indent=1)
    print(json.dumps({k: v for k, v in out.items() if k != "marginals_stage1"}, indent=1))


# ================================================================================================ book + evals command
BOOK = ("sh_asia_resweep", "sh_trend_idm5")


def book_rows(names=BOOK, max_day=2):
    """The picks as one strategy: all their trades in entry order, one position at a time, max 2 a session."""
    R = []
    for nm in names:
        d = json.load(open(os.path.join(OUT, nm + ".json")))
        R += [{**t, "setup": nm} for t in d["trades"]]
    R.sort(key=lambda r: (r["entry_t"], names.index(r["setup"])))
    out, busy, cnt = [], -1, collections.Counter()
    for r in R:
        if r["entry_t"] < busy or cnt[r["day"]] >= max_day:
            continue
        out.append(r); busy = r["exit_t"]; cnt[r["day"]] += 1
    return out


def cmd_book():
    g = base()
    rows = book_rows()
    rep = {"name": "sh_book", "title": "Stop-hunt book: Asia resweep hunt + trend inducement hunt (one position, max 2 a session)",
           "built": time.strftime("%Y-%m-%d %H:%M"), "members": list(BOOK),
           "rules": ["Both picks' rules (research/stophunt/sh_asia_resweep.json, sh_trend_idm5.json); trades in entry order, one position at "
                     "a time (a signal while a trade is open is skipped), max 2 trades a session."],
           "spans": span_table(rows, g), "months": months_table(rows), "trades": rows}
    json.dump(rep, open(os.path.join(OUT, "sh_book.json"), "w"), indent=1, default=str)
    for k, v in rep["spans"].items():
        print(k, {x: v.get(x) for x in ("n", "tpw", "win", "pf", "net", "per_month", "dd", "net_wo_best3", "wk2_pct")})


def cmd_evals():
    names = list(FINAL) + ["sh_book"]
    res = evals(names)
    json.dump(res, open(os.path.join(OUT, "evals.json"), "w"), indent=1, default=str)
    f = lambda o: f"{o.get('tpw')}/wk ${o.get('net'):+,} DD {o.get('dd')} 2w {o.get('p10')}/{o.get('f10')} 1m {o.get('p20')}/{o.get('f20')} med {o.get('pass_med')}"
    for k, v in res.items():
        if k in ("LIT_alone_50k", "ATLAS_25k"):
            print(k, " | ".join(f"{s} {f(v[s])}" for s in v))
            continue
        for kk, vv in v.items():
            print(k, kk, " | ".join(f"{s} {f(vv[s])}" for s in vv))


# ================================================================================================ run library
Q = ("Owner 2026-10-23: retail stops sit at obvious highs/lows; wait for the hunt, a resweep or an inducement, then a strong "
     "candle toward the draw on liquidity. Find setups with LIT's win rate (55%) or better.")


def _rl_trades(rows):
    out = []
    for r in rows:
        risk_usd = r["risk_pts"] * E.PV * r["qty"]
        out.append({"day": r["day"], "entry_t": r["entry_t"], "exit_t": r["exit_t"], "dir": r["dir"], "r": r["r"], "pnl": r["pnl_usd"],
                    "risk_pts": r["risk_pts"], "qty": r["qty"], "risk_usd": round(risk_usd, 2), "half": False, "exit": r["exit_kind"],
                    "trigger": r.get("setup", ""), "mfe": r.get("mfe_r"), "mae": r.get("mae_r"), "bars_held": None, "regime": r.get("session", ""),
                    "mult": None, "low": min(0.0, r["pnl_usd"], (r.get("mae_r") if r.get("mae_r") is not None else -1.0) * risk_usd)})
    return out


def _sess(g):
    return [str(d) for d in g["B"]["days"] if "2021-11-01" <= str(d) <= "2026-10-16"]


def _vtxt(sp):
    f = lambda k: (f"{sp[k]['n']} trades ({sp[k]['tpw']}/wk), win {sp[k]['win']}%, PF {sp[k]['pf']}, ${sp[k]['net']:+,} "
                   f"(${sp[k]['per_month']:+,}/mo), max DD ${sp[k]['dd']:,}")
    return f"2026 H1: {f('H1')}. H2 (untouched check): {f('H2')}. 2025: {f('2025')}. 2021-24: {f('2021-24')}."


def cmd_save():
    from tools import runlib as rl
    from tools import second_mix as M
    from tools import second_account_b as AB
    g = base()
    sess = _sess(g)
    status = {"sh_asia_resweep": "promising", "sh_trend_idm": "info", "sh_trend_idm5": "promising", "sh_book": "promising"}
    for nm in list(FINAL) + ["sh_book"]:
        d = json.load(open(os.path.join(OUT, nm + ".json")))
        T = _rl_trades(d["trades"])
        pl = d.get("placebo", {})
        ptxt = (f" Placebos (2000 runs, same entry mechanics): random times p = {pl['H2']['p_rtime']} in H2, {pl['all']['p_rtime']} over all "
                f"periods; shuffled directions p = {pl['H2']['p_flip']} in H2, {pl['all']['p_flip']} over all.") if pl else ""
        rl.save(nm, d["title"], "other", Q, params=d.get("params", {"members": d.get("members")}), sizing={"risk_usd": RISK_USD, "max_micros": MAXQ},
                trades=T, scored=rl.score(T, sess), status=status[nm],
                verdict=_vtxt(d["spans"]) + ptxt + " Paper only; picked on H1 + 2025 + 2021-24 (worst t), H2 untouched.",
                notes="tools/stophunt.py final / book; engine/stophunt.py; costs $1.90/micro + 1 tick; $500 risk a trade",
                writeup="stophunt", tags=["stophunt", "second"])
        print("saved", nm, flush=True)
    # protocol picks on H1 only (stage 2 A win-rate rule, stage 3 Asia win-rate rule): the failed route, stored for the record
    for rid, fam, rule in (("sh_h1pick_trend", "trend", "winrate"), ("sh_h1pick_asia", "asia", "winrate")):
        P = json.load(open(os.path.join(OUT, "stage3_picks.json")))[f"{fam}_{rule}"]["picks"][0]
        sp = {**P["spec"], "name": rid}
        st, rows = one(g, sp)
        rows = [r for r in rows if r["day"] >= "2021-11-01"]
        T = _rl_trades(rows)
        tab = span_table(rows, g)
        rl.save(rid, f"Stop hunt picked on 2026 H1 only ({fam} family, win-rate rule)", "other", Q, params={k: sp[k] for k in list(DIMS) + S2_KEYS},
                sizing={"risk_usd": RISK_USD}, trades=T, scored=rl.score(T, sess), status="rejected",
                verdict=_vtxt(tab) + " The owner's LIT rule (pick on H1, check H2) picks this; it does not hold in H2 / the earlier years.",
                notes="tools/stophunt.py stage3 + pick3", writeup="stophunt", tags=["stophunt"])
        print("saved", rid, flush=True)
    # eval paths (back-to-back evals, the executors' own trades)
    U = M.units()
    for nm in ("sh_asia_resweep", "sh_trend_idm5", "sh_book"):
        M.SECOND[nm] = os.path.join("..", "stophunt", nm + ".json")
        U[nm] = M.second_units(nm)
    ev = json.load(open(os.path.join(OUT, "evals.json")))
    jobs = [("sh_atlas25k_asia", "ATLAS + Asia stop hunt on account B (Builder 25K, need size, no-hedge)", ("EMA", "MD", "SR", "sh_asia_resweep"), "ATLAS_plus_25k", "sh_asia_resweep"),
            ("sh_atlas25k_book", "ATLAS + stop-hunt book on account B (Builder 25K, need size, no-hedge)", ("EMA", "MD", "SR", "sh_book"), "ATLAS_plus_25k", "sh_book")]
    for rid, title, names, key, src in jobs:
        T = []
        with AB.Plan("builder25k") as pl:
            Ua = M.acct_units(names, nohedge=True)
            for s_ in AB.SPANS:
                T += AB.score(Ua, "acctb_need", s_, pl.safe_rule)[1]
        x = ev[src][key]
        TT = [{"day": t["day"], "entry_t": t["entry_t"], "exit_t": t["exit_t"], "dir": t["dir"], "r": round(t["pnl"] / t["risk_usd"], 3) if t["risk_usd"] else 0.0,
               "pnl": t["pnl"], "risk_pts": t["risk"], "qty": t["qty"], "risk_usd": t["risk_usd"], "half": False, "exit": t["exit"],
               "trigger": t["src"], "mfe": None, "mae": None, "bars_held": None, "regime": "", "mult": None, "low": t["low"]} for t in T]
        f = lambda s_: f"{x[s_]['tpw']}/wk path ${x[s_]['net']:+,} DD ${x[s_]['dd']:,}; 2-week pass/fail {x[s_]['p10']}/{x[s_]['f10']}, 1 month {x[s_]['p20']}/{x[s_]['f20']}"
        a = ev["ATLAS_25k"]
        fa = lambda s_: f"{a[s_]['p10']}/{a[s_]['f10']}"
        rl.save(rid, title, "other", Q, params={"accounts": list(names), "plan": "builder25k", "size": "need", "no_hedge": True},
                sizing={"plan": "builder25k", "size": "need"}, trades=TT, scored=rl.score(TT, [d_ for d_ in sess if d_ >= "2021-01-01"]),
                status="promising", verdict=f"H1 {f('H1')}. H2 {f('H2')}. 2025 {f('2025')}. 2021-24 {f('2021-24')}. ATLAS alone 2-week "
                                            f"pass/fail H1 {fa('H1')}, H2 {fa('H2')}, 2025 {fa('2025')}, 2021-24 {fa('2021-24')}.",
                notes="tools/stophunt.py evals (tools/second_account_b.py executor); stored trades = each span's back-to-back eval path",
                writeup="stophunt", tags=["stophunt", "account_b"])
        print("saved", rid, flush=True)
    # LIT + trend pick on the 50K
    T = []
    for s_ in M.SPANS:
        T += M.score_span(list(U["LIT"]) + list(U["sh_trend_idm5"]), "usd500_safe_dll", s_, pre=True)[1]
    x = ev["sh_trend_idm5"]["withLIT_50k_usd500_safe_dll"]
    a = ev["LIT_alone_50k"]
    TT = [{"day": t["day"], "entry_t": t["entry_t"], "exit_t": t["exit_t"], "dir": t["dir"], "r": round(t["pnl"] / t["risk_usd"], 3) if t["risk_usd"] else 0.0,
           "pnl": t["pnl"], "risk_pts": t["risk"], "qty": t["qty"], "risk_usd": t["risk_usd"], "half": False, "exit": t["exit"], "trigger": t["src"],
           "mfe": None, "mae": None, "bars_held": None, "regime": "", "mult": None, "low": t["low"]} for t in T]
    f = lambda o, s_: f"{o[s_]['tpw']}/wk ${o[s_]['net']:+,} 2-week {o[s_]['p10']}/{o[s_]['f10']}, 1 month {o[s_]['p20']}/{o[s_]['f20']}"
    rl.save("sh_withlit50k_trend5", "LIT + trend stop hunt on one Builder 50K (LIT first, $500 safe + daily-loss cap)", "other", Q,
            params={"lit": "live", "second": "sh_trend_idm5", "rule": "usd500_safe_dll", "pre": True}, sizing={"lit": "two_week", "second": "usd500_safe_dll"},
            trades=TT, scored=rl.score(TT, [d_ for d_ in sess if d_ >= "2021-01-01"]), status="info",
            verdict=" | ".join(f"{s_}: with {f(x, s_)} vs LIT alone {f(a, s_)}" for s_ in M.SPANS),
            notes="tools/stophunt.py evals (tools/second_mix.py executor)", writeup="stophunt", tags=["stophunt", "lit"])
    print("saved sh_withlit50k_trend5", flush=True)


# ================================================================================================ live / OPEN mode
# engine/second.py plugin "stop_hunt" (paper, second_model.json sh_asia / sh_trend): the SAME pipeline as one() / FINAL
# (sigs_of -> fills -> ctx_ok -> targets -> walk -> select_stats) on LIT's live window, data cut at the poll (closed bars
# only: B["cut"] = True drops a forming HTF bar / session / week, as the look-ahead check of the research). A trade whose
# walk ran into the end of the data before its 15:55 flat is OPEN (it holds the one position: later signals are skipped as
# in the research, where its exit lies in the future).
def live_base(B, pool=None, dol=False):
    """base() on given bars: pools of the pool set only (engine/stophunt.build_pools types; the others never change a hunt
    of the set), swing index, sorted sweeps; DOL tables only when a DOL target / partial needs them."""
    types = None if pool is None else [E.TYPES[i] for i in POOL_SETS[pool][0]]
    P = E.build_pools(B, use_1m=types is None or "f1" in types, types=types)
    g = dict(B=B, P=P, F=E.swing_index(B), order=E.sorted_sweeps(P), span_of_sid=np.full(len(B["days"]), -1, np.int64),
             nsess=[1, 1, 1, 1], ev={})
    if dol:
        g["TB"] = E.dol_tables(P, B)
    return g


def live(spec, df5, df1=None, now=None, is_open=None):
    """One poll of a pick (spec = FINAL[...] / its "params"): df5 / df1 = the closed 5m / 1m bars (time, open, high, low,
    close), now = poll time, is_open(day) = that day's 15:55 flat still ahead (engine/second._session_open). Returns
    {"g", "rows" (chosen trades in the research format + "open", "stop_now", "last"), "X", "Wk", "T", "sg", "ok", "spec"}."""
    now = int(now if now is not None else int(df5["time"].max()) + 300)
    has1 = df1 is not None and len(df1)
    m1_from = max(1767308400, int(df1["time"].min())) if has1 else None
    # with a 1m feed every signal from 2026 walks on 1m (the research rule); a signal whose 1m bars have not arrived yet
    # waits (no 5m stand-in that the next poll would replace)
    B = E.bars(df5, df1 if has1 else None, m1_from=m1_from, m1_to=now + 1 if has1 else None)
    B["cut"] = True
    sp = {**spec}
    g = live_base(B, sp["pool"], dol=str(sp["tg"]).startswith("dol") or bool(sp.get("part")))
    S = {k: sp[k] for k in DIMS}
    sg = sigs_of(g, S)
    X = fills(g, sg, sp["entry"], max_stop=sp["max_stop"])
    o = np.argsort(X["ft"], kind="stable")
    Xo = {k: v[o] for k, v in X.items()}
    okc = ctx_ok(g, Xo, sp["ctx"])
    T = targets(g, Xo, sp["tg"], min_rr=sp["min_rr"])
    Wk = walk(g, Xo, T, be=sp["be"], t15=bool(sp["t15"]), part=bool(sp["part"]), flat=sp["flat"])
    M1 = B["m1"]
    kf = Xo["kf"] if sp["flat"] == "1555" else np.where(Xo["ks"] >= 0, Xo["ks"], Xo["kf"])
    p1 = Xo["path"] == 1
    last_i = np.where(p1, M1["n"] - 1, B["n"] - 1)
    r1 = M1["rel"][np.clip(kf, 0, M1["n"] - 1)] if M1["n"] else np.zeros(len(kf), np.int64)
    r5 = B["rel"][np.clip(kf, 0, B["n"] - 1)]
    rel_kf = np.where(p1, r1, r5)
    flat_rel = np.where(p1, E.FLAT_REL1, E.FLAT_REL5)
    days = B["days"][Xo["sid"]]
    sess_open = np.array([True if is_open is None else bool(is_open(str(d))) for d in days], bool)
    opn = Wk["ok"] & (Wk["kind"] == 4) & (kf == last_i) & (rel_kf < flat_rel) & sess_open
    xt = np.where(opn, np.int64(1) << 62, Wk["xt"])
    ok = Wk["ok"] & okc
    _, sel = select_stats(Xo["ft"], xt, Xo["sid"], Xo["bucket"], ok, Wk["pnl"], Wk["R"], WINDOWS[sp["win"]], sp["mp"],
                          g["span_of_sid"], 4, True)
    rows = trade_rows(g, Xo, Wk, T, sel, sp.get("name", "stophunt"))
    be_at, be_off = (0.0, 0.0) if sp["be"] == "none" else (1.0, 0.0 if sp["be"] == "be1" else 1.25)
    for r, i in zip(rows, sel):
        r["open"] = bool(opn[i])
        if r["open"]:
            d = r["dir"]
            moved = be_at > 0 and float(Wk["mfe"][i]) >= be_at
            r["stop_now"] = round(r["entry"] + d * be_off, 2) if moved else r["stop"]
            r["last"] = round(float((M1["c"] if p1[i] else B["c"])[last_i[i]]), 2)
    return {"g": g, "rows": rows, "X": Xo, "Wk": Wk, "T": T, "sg": sg, "ok": ok, "sel": sel, "spec": sp, "now": now}


def explain(g, spec, j, upto=None):
    """The rule checks of ONE hunt (event bar j) as engine/stophunt._signals walks it, written out in plain Python for the
    brain (closed bars only, up to bar `upto`, default the last bar): the hunt (pool, side, depth), the extra condition
    (resweep / inducement), the trigger candle (body vs ATR, close beyond the pool and the last swing) at the trigger bar,
    or at the last bar looked at when there is none yet. Display only: the trade decision is _signals."""
    B, F = g["B"], g["F"]
    ev = ev_of(g, spec["pool"])
    ks = np.nonzero(ev["j"] == j)[0]
    m, rk = MODE_SPEC[spec["mode"]]
    kb, bt = BODY_SPEC[spec["body"]]
    struct = STRUCT[spec["struct"]]
    o, h, l, c, atr, mb10, rel, sid = B["o"], B["h"], B["l"], B["c"], B["atr"], B["mb10"], B["rel"], B["sid"]
    n = B["n"]
    upto = n - 1 if upto is None else min(int(upto), n - 1)
    W, depth = int(spec["W"]), float(spec["depth"])
    out = []
    for e in ks:
        dr = -int(ev["side"][e])
        s = sid[j]
        a = B["sess_start"][s]
        A = atr[j - 1]
        p = dr * ev["p"][e]
        Fp = F["fl"] if dr > 0 else F["fh"]
        pre = False
        for f in Fp[np.searchsorted(Fp, j - 36):]:
            if f + 2 > j - 1:
                break
            fp = l[f] if dr > 0 else -h[f]
            if p < fp <= p + A:
                pre = True
                break
        ext, arg, bounce, inside, rs_bar, idm_bar, il, cz = 1e18, j, -1e18, False, -1, -1, float("nan"), float("nan")
        last = trig = None
        for q in range(j, min(j + W + 1, n)):
            if q > upto or sid[q] != s or rel[q] > E.ENTRY_CUT:
                break
            oq, hq, lq, cq = (o[q], h[q], l[q], c[q]) if dr > 0 else (-o[q], -l[q], -h[q], -c[q])
            if q > j:
                if rs_bar < 0:
                    if rk in (0, 2) and inside and lq < p:
                        rs_bar = q
                    elif rk in (1, 2) and lq < ext and (bounce - ext) >= 0.5 * A and q - arg >= 2:
                        rs_bar = q
                if idm_bar < 0 and not math.isnan(il) and lq < il:
                    idm_bar = q
            if lq < ext:
                ext, arg, bounce = lq, q, hq
                if struct == 1:
                    cz = float(E._cisd_s(o, c, a, arg, dr))
            else:
                bounce = max(bounce, hq)
            rs_ok, idm_ok = 0 <= rs_bar < q, 0 <= idm_bar < q
            mode_ok = {0: True, 1: q <= j + 1, 2: rs_ok, 3: idm_ok, 4: pre, 5: rs_ok and idm_ok, 6: rs_ok or idm_ok}[m]
            body = cq - oq
            thr = kb * A if bt == 0 else kb * mb10[q]
            lvl = float("nan")
            if struct == 2:
                G = F["fh"] if dr > 0 else F["fl"]
                hi_i = int(np.searchsorted(G, q - 2)) - 1
                if hi_i >= 0 and G[hi_i] >= j - 48:
                    lvl = h[G[hi_i]] if dr > 0 else -l[G[hi_i]]
            elif struct == 1:
                lvl = cz
            st_ok = True if struct == 0 else (not math.isnan(lvl) and cq > lvl)
            last = dict(q=int(q), t=int(B["t"][q]), mode_ok=bool(mode_ok), body=float(body), thr=float(thr), atr=float(A),
                        close_beyond_pool=bool(cq > p), depth=float((p - ext) / A) if A > 0 else 0.0, struct_ok=bool(st_ok),
                        lvl=None if math.isnan(lvl) else float(dr * lvl), rs=bool(rs_ok), idm=bool(idm_ok), close=float(c[q]))
            if mode_ok and cq > p and body >= thr and body > 0 and (p - ext) >= depth * A and st_ok:
                trig = last
                break
            if q - 1 > j and q - 2 >= j:
                l1, l0, l2 = (l[q - 1], l[q - 2], l[q]) if dr > 0 else (-h[q - 1], -h[q - 2], -h[q])
                if l1 < l0 and l1 < l2 and l1 > ext + 0.25 and q - 1 != arg:
                    il = l1
            if cq > p:
                inside = True
        tm = int(ev["tmask"][e])
        end_q = j + W
        out.append({"j": int(j), "t": int(B["t"][j]), "dr": dr, "pool": float(dr * p), "score": float(ev["score"][e]),
                    "types": [E.TYPES[i] for i in range(len(E.TYPES)) if tm >> i & 1], "ext": float(dr * ext), "pre": bool(pre),
                    "atr": float(A), "until_t": int(B["t"][j]) + 300 * (W + 1), "last": last, "trigger": trig,
                    "expired": trig is None and (last is None or last["q"] >= end_q or upto > (last or {}).get("q", upto))})
    return out


# ================================================================================================ prototype
def demo():
    g = base()
    S = dict(pool="all", mode="rs", W=12, body="a0.8", struct="cisd", fvg=0, depth=0.0)
    t0 = time.time()
    sg = sigs_of(g, S)
    X = fills(g, sg, "mkt")
    print("signals", len(sg["sig"]), "fills", len(X["e"]), f"{time.time() - t0:.2f}s")
    for tg in ("r2", "dolA_b5", "dolH_b5", "vix_b8"):
        t0 = time.time()
        T = targets(g, X, tg)
        Wk = walk(g, X, T)
        o = order_by_time(X, Wk)
        for wn in ("all", "day", "lon", "nyam"):
            st, _ = select_stats(X["ft"][o], Wk["xt"][o], X["sid"][o], X["bucket"][o], Wk["ok"][o], Wk["pnl"][o], Wk["R"][o],
                                 WINDOWS[wn], 1, g["span_of_sid"], 4, False)
            print(tg, wn, " | ".join(f"{SPAN_NAMES[s]} {stats_dict(st, g['nsess'], s)}" for s in range(2)), f"{time.time() - t0:.2f}s")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "demo"
    globals()["cmd_" + cmd]() if "cmd_" + cmd in globals() else demo()
