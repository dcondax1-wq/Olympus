"""Stops x targets x TIME (owner 2026-11-24: "our stops and take-profits are too big; build them from different timeframes;
learn TIME x PRICE"). RESEARCH ONLY: paper, nothing live changes, live_model*.json untouched.
Write-up: research/writeups/stops-targets-time-2026-11-24.md. Lab numbers: research/lab/stops_targets.json.

Base = the live LIT trades (tools/lit_edge.ctx()["T"] == run lit_live: same setups, same limit, same 1m CISD fill), re-walked
after the fill by `walk` below (all options off == every live exit, checked by `check`). Only the stop / target / clock
change, so the trade list is the live one (a variant never adds a trade; the 1.5R setup check stays on the live band).

PRE-REGISTERED VARIANTS (written 2026-11-24 before any run; 19 counted in the many-tests correction):
 A  stops from lower timeframes (2026 = 1m days; 2021-25 has 5m bars only -> the same rule on 5m bars, a PROXY):
    A1 cisd1   1 tick beyond the 1m CISD candle (the 1m bar whose close confirmed the entry)
    A2 swing1  1 tick beyond the 1m swing that formed the entry (lowest 1m low from the limit tap to the confirmation)
               (= lit_tightstop "tap", 2026-10-18: repeated only as the control for the new targets / sizing / wick count)
    A3 fvg3    1 tick beyond the bottom of the newest 3m FVG (3m bars built from 1m) formed between the sweep extreme and the
               fill; none -> the live stop (counted)
    every tight stop: never wider than the live stop, at least 5 pts. Each with 3 targets: the live target PRICE (band,
    unchanged), 2R and 3R of the new stop -> 9 variants. BE at +1R and the 15-min check measured on the new stop.
    Sizing views: (i) the LIT rule as written ($800 up to 20 pts: a tight stop risks MORE $), (ii) RISK-MATCHED = the same $
    at risk as the live trade (more micros, capped at 40; the honest one), (iii) the live eval two_week sizing per account.
 B  targets from structure on other timeframes, live stop (nearest qualifying level >= 1.5R from the fill, <= 8R, else the
    live band):
    B1 liq15   nearest untaken 15m swing high (3-bar fractal, last 2 days)
    B2 liq1h   nearest untaken 1h swing high (3-bar fractal, last 5 days)
    B3 sess    nearest untaken opposing session high: today's Asia (18:00-24:00), London (02:00-05:00), previous day
    B4 fvg1h   near edge of the nearest unfilled opposing 1h FVG (last 5 days)
    B5-B7      fixed 1.5R / 2R / 3R (controls)                       -> 7 variants (the VIX band = today = base)
 C  TIME x PRICE (live stop and target; N fixed from the 2026 Jan-Jun 1m distribution ONLY, rule below):
    N = the 80th percentile of minutes-to-+0.5R of Jan-Jun TARGET winners (80% of the winners have shown +0.5R by then).
    C1 tstop   at N minutes without +0.5R -> out at the next 1m open. Pre-set condition: only reported as a candidate if in
               Jan-Jun the trades with no +0.5R at N win < 15% and average < 0R (else it is run and marked "data says no").
    C2 tighten at N minutes without +0.5R -> stop to entry - 0.5R (closed beyond it -> out at the next open)
    C3 timeBE  at N minutes, not yet at breakeven but closed >= entry + 1.25 -> stop to breakeven (entry + 1.25)
                                                                     -> 3 variants
 Gate (the LIT rule + this task): H1 AND H2 better than live on the risk-matched LIT $ and on the 50K eval path, no more
 2-week fails, 2+ trades/week, 2021-25 not worse; and the H2 gain beats a paired bootstrap at p < 0.05/19 (Bonferroni).

  python -X utf8 tools/stops_targets_time.py check   # options off == live (every trade's exit kind and points)
  python -X utf8 tools/stops_targets_time.py time    # TIME x PRICE tables + N from H1 -> research/lit/stops_time.json
  python -X utf8 tools/stops_targets_time.py all     # every variant -> research/lab/stops_targets.json
"""
from __future__ import annotations

import collections
import json
import math
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import lit  # noqa: E402
from engine import sizing as S  # noqa: E402
from tools import lit_edge as E  # noqa: E402
from tools import lit_rev_exit as R  # noqa: E402

PV, COMM, SLIP, TICK = lit.PV, lit.COMM, lit.SLIP, lit.TICK
ECOMM = S.TW_COMM
LIVE = E.LIVE
BE_OFF = E.BE_OFF
SPANS = R.SPANS
OUT = os.path.join(ROOT, "research", "lab", "stops_targets.json")
OUT_T = os.path.join(ROOT, "research", "lit", "stops_time.json")
TIGHT_MIN = 5.0
N_TESTS = 19
_LM = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))["lit_sizing"]
TW = {**_LM["two_week"]}
ACCTS = {   # docs/ACCOUNT_RULES.md (2026-11-20)
    "builder50k": {"target": 3000.0, "mll": 2000.0, "lock": 100.0, "dll": 1000.0, "max_micros": 40, "scale": 1.0,
                   "price": 91.80},
    "builder25k": {"target": 1500.0, "mll": 1000.0, "lock": 100.0, "dll": 600.0, "max_micros": 20, "scale": 0.5,
                   "price": 63.0},
    "rapid25k": {"target": 1500.0, "mll": 1000.0, "lock": 100.0, "dll": 500.0, "max_micros": 20, "scale": 0.5,
                 "price": 97.20, "best_day": 0.30, "min_days": 4, "day_win_cap": 0.30 * 1500 * 0.95},
}


# ================================================================================================ bars / helpers
_X = {}


def X():
    if not _X:
        c = E.ctx()
        _X.update(c=c, M=c["M"], B1=c[60].B, B5=c[300].B)
        B5 = c[300].B
        for tf, sec in (("15", 900), ("60", 3600), ("3", 180)):
            src = c[60].B if tf == "3" else B5
            g = (src.t // sec).astype(np.int64)
            cut = np.r_[0, np.nonzero(np.diff(g))[0] + 1]
            _X["g" + tf] = dict(t=g[cut] * sec, h=np.maximum.reduceat(src.h, cut), l=np.minimum.reduceat(src.l, cut),
                                src_ix=cut, n=len(cut))
    return _X


def dirs(b, d):
    return (b["h"], b["l"]) if d == 1 else (-b["l"], -b["h"])


def maxhi(B, d, t0, t1):
    """Highest direction-space high of bars of B starting in [t0, t1)."""
    hi = B.h if d == 1 else -B.l
    a, z = int(np.searchsorted(B.t, t0)), int(np.searchsorted(B.t, t1))
    return float(hi[a:z].max()) if z > a else -1e18


# ================================================================================================ stops (A)
def tight_stop(t, mode, fill, entry, stop0):
    """Direction-space stop of mode for trade t (1m days: 1m/3m bars; 5m days: the same rule on 5m bars)."""
    x = X()
    M = x["M"]
    z = E.zc(t)
    d = t["dir"]
    B = x["B1"] if t["tf"] == 1 else x["B5"]
    hi_d, lo_d, c_d, o_d = B.dirs(d)
    kconf = fill - 1
    k0 = int(np.searchsorted(B.t, M.t[z["i"]] + 300))
    tap = None
    for k in range(k0, kconf + 1):
        if lo_d[k] <= z["ref_d"] + 1e-9:
            tap = k
            break
    tap = k0 if tap is None else tap
    st = None
    if mode == "cisd1":
        st = float(lo_d[kconf]) - TICK
    elif mode == "swing1":
        st = float(lo_d[tap:kconf + 1].min()) - TICK
    elif mode == "fvg3":
        if t["tf"] != 1:
            return stop0, "nofvg"
        g = x["g3"]
        h3, l3 = dirs(g, d)
        t_ext = M.t[z["ext_i"]]
        a = int(np.searchsorted(g["t"], t_ext))
        z3 = int(np.searchsorted(g["t"], B.t[fill] - 180, side="right"))   # 3m bars closed by the fill
        for j in range(z3 - 1, a + 1, -1):
            bot, top = float(h3[j - 2]), float(l3[j])
            if top > bot and bot < entry and bot > stop0:
                st = bot - TICK
                break
        if st is None:
            return stop0, "nofvg"
    if st is None or st >= entry:
        return stop0, "fallback"
    st = min(st, entry - TIGHT_MIN)
    return (max(stop0, st), mode if st > stop0 else "ext")


# ================================================================================================ targets (B)
def struct_target(t, mode, entry, risk, tg_live):
    x = X()
    d = t["dir"]
    B = x["B1"] if t["tf"] == 1 else x["B5"]
    fill = int(np.searchsorted(B.t, t["entry_t"]))
    tf_t = int(B.t[fill])
    lo_ok, hi_ok = entry + 1.5 * risk, entry + 8.0 * risk
    cands = []
    B5 = x["B5"]
    if mode in ("liq15", "liq1h", "fvg1h"):
        key, look = ("15", 2 * 86400) if mode == "liq15" else ("60", 5 * 86400)
        g = x["g" + key]
        sec = 900 if key == "15" else 3600
        h, l = dirs(g, d)
        z = int(np.searchsorted(g["t"], tf_t - sec, side="right"))    # bars closed by the fill
        a = int(np.searchsorted(g["t"], tf_t - look))
        if mode != "fvg1h":
            for j in range(max(a, 1), z - 1):
                if h[j] > h[j - 1] and h[j] > h[j + 1] and h[j] > entry:
                    if maxhi(B5, d, g["t"][j] + sec, tf_t) < h[j] and maxhi(B, d, tf_t, tf_t + 1) < h[j]:
                        cands.append(float(h[j]))
        else:
            for j in range(max(a, 2), z):
                if l[j - 2] > h[j] and h[j] > entry and maxhi(B5, d, g["t"][j] + sec, tf_t) < h[j]:
                    cands.append(float(h[j]))
    elif mode == "sess":
        Bd = B5
        hi5 = Bd.h if d == 1 else -Bd.l
        i5 = int(np.searchsorted(Bd.t, tf_t))
        sday = Bd.day[max(0, i5 - 1)]
        m = (Bd.day == sday)
        idx = np.nonzero(m[:i5])[0]
        boxes = []
        if len(idx):
            mods = Bd.mod[idx]
            for lo_m, hi_m in ((1080, 1440), (120, 300)):
                sel = idx[(mods >= lo_m) & (mods < hi_m)]
                if len(sel):
                    end = int(sel[-1]) + 1
                    if end < i5:
                        boxes.append((float(hi5[sel].max()), end))
            d0 = idx[0]
            pm = np.nonzero(Bd.day[:d0] == Bd.day[d0 - 1])[0] if d0 > 0 else []
            if len(pm):
                boxes.append((float(hi5[pm].max()), d0))
        for lev, end in boxes:
            if lev > entry and (hi5[end:i5].max() if i5 > end else -1e18) < lev:
                cands.append(lev)
    ok = sorted(c for c in cands if lo_ok <= c <= hi_ok)
    return (ok[0] - TICK, True) if ok else (tg_live, False)     # exit 1 tick in front of the level (live habit)


# ================================================================================================ walk (post-fill)
def walk(B, fill, d, entry, stop, tg, s_day, risk, opt=None, rec=None):
    """lit_edge.manage with every option off (== live) + the C rules. rec: dict collecting minute-stamps."""
    opt = opt or {}
    hi_d, lo_d, c_d, o_d = B.dirs(d)
    flat = LIVE["flat_mod"]
    on1 = B.secs == 60
    tc = LIVE.get("t_check") if on1 else None
    be_r = LIVE["be_r"]
    cur, be_done, mfe, worst = stop, False, 0.0, 0.0
    cut = None
    k = fill
    exit_px = kind = None
    Nm = opt.get("N")
    time_done = False
    while k < B.n:
        if B.day[k] != s_day or B.mod[k] >= 1080:
            k -= 1; exit_px, kind = float(c_d[k]) - SLIP, "EOD"; break
        if cut is not None:
            exit_px, kind = float(o_d[k]) - SLIP, cut; break
        worst = min(worst, lo_d[k] - entry)
        if lo_d[k] <= cur:
            exit_px, kind = cur - SLIP, ("BE" if be_done else ("TSTOP" if cur > stop + 1e-9 else "STOP")); break
        mfe = max(mfe, (hi_d[k] - entry) / risk)
        mins = round((B.t[k] - B.t[fill]) / 60.0) + B.secs // 60
        if rec is not None:
            for lv in (0.5, 1.0):
                if mfe >= lv and ("r%g" % lv) not in rec:
                    rec["r%g" % lv] = mins
        if hi_d[k] >= tg:
            exit_px, kind = tg, "TARGET"; break
        if be_r is not None and not be_done and hi_d[k] >= entry + be_r * risk:
            if entry + BE_OFF > cur:
                cur = entry + BE_OFF
            be_done = True
        if B.mod[k] >= flat:
            exit_px, kind = float(c_d[k]) - SLIP, "EOD"; break
        nxt = k + 1 < B.n and B.day[k + 1] == s_day
        if tc and not be_done and round((B.t[k] - B.t[fill]) / 60.0) + 1 == int(tc.get("at", 15)) \
                and mfe < float(tc.get("mfe", 0.5)) and c_d[k] < entry - float(tc.get("x", 0.3)) * risk:
            if nxt:
                cut = "CUT_T15"; k += 1; continue
        if Nm and not time_done and mins >= Nm:
            time_done = True
            r = opt["rule"]
            if r == "tstop" and mfe < 0.5 and nxt:
                cut = "TIME"; k += 1; continue
            if r == "tighten" and mfe < 0.5:
                ns = entry - 0.5 * risk
                if c_d[k] <= ns and nxt:
                    cut = "TIME"; k += 1; continue
                cur = max(cur, ns)
            if r == "timebe" and not be_done and c_d[k] >= entry + BE_OFF:
                cur = max(cur, entry + BE_OFF); be_done = True
        k += 1
    return kind, exit_px - entry, worst, mfe, k


def units(V=None, rec_time=False):
    """Unit trades of variant V {'stop': mode|None, 'tgt': 'live'|'R2'|'R3'|struct mode|'R1.5', 'time': {...}}."""
    V = V or {}
    x = X()
    T = x["c"]["T"]
    out = []
    for t in T:
        B = x["B1"] if t["tf"] == 1 else x["B5"]
        d = t["dir"]
        fill = int(np.searchsorted(B.t, t["entry_t"]))
        entry, stop0, tg0 = t["entry_px"] * d, t["stop_px"] * d, t["target_px"] * d
        risk0 = entry - stop0
        stop, src = stop0, "ext"
        if V.get("stop"):
            stop, src = tight_stop(t, V["stop"], fill, entry, stop0)
        risk = entry - stop
        tg, hit = tg0, False
        tm = V.get("tgt", "live")
        if tm.startswith("R"):
            tg = entry + float(tm[1:]) * risk
        elif tm != "live":
            tg, hit = struct_target(t, tm, entry, risk, tg0)
        rec = {} if rec_time else None
        kind, pts, worst, mfe, kx = walk(B, fill, d, entry, stop, tg, int(B.day[fill]), risk, V.get("time"), rec)
        u = {"day": t["day"], "entry_t": int(t["entry_t"]), "exit_t": int(B.t[kx]) + B.secs, "dir": d, "exit": kind,
             "risk": round(risk, 2), "risk0": round(risk0, 2), "tgt": round(tg - entry, 2), "pts": round(pts, 4),
             "w1": round(worst, 4), "legs": [(1.0, pts)], "mfe": round(mfe, 3), "tf": t["tf"], "m": 1.0,
             "src": src, "struct_hit": hit, "live_exit": t.get("exit"),
             "live_pts": round((t["pnl"] + COMM * t["qty"]) / (PV * t["qty"]), 4), "live_qty": t["qty"]}
        if rec is not None:
            u["t_r05"], u["t_r1"] = rec.get("r0.5"), rec.get("r1")
            u["mins"] = round((u["exit_t"] - u["entry_t"]) / 60.0)
        out.append(u)
    return out


# ================================================================================================ sizing / stats
def size_matched(U):
    """Risk-matched: the live trade's $ at risk (live qty x live stop) spread over the new stop, max 40, weekly stop."""
    W = E.wk_mult(U)
    L = []
    for u in sorted(U, key=lambda u: u["entry_t"]):
        q0 = lit.qty_for(u["risk0"])
        usd = q0 * u["risk0"] * PV
        q = max(1, min(40, int(usd / (u["risk"] * PV) + 1e-9))) if q0 else 0
        if W[u["entry_t"]] < 1:
            q = max(1, int(q * W[u["entry_t"]] + 1e-9))
        pnl = u["pts"] * PV * q - COMM * q
        low = min(0.0, u["w1"] * PV * q - COMM * q, pnl)
        L.append({**u, "qty": q, "pnl": round(pnl, 2), "low": round(low, 2), "r": round(pnl / (u["risk"] * PV * q), 3)})
    return L


def stats(L, span):
    s = R.lit_stats(L, span)
    a, z = SPANS[span]
    TT = [l for l in L if a <= l["day"] <= z]
    s["avg_r"] = round(float(np.mean([l["pnl"] / (l["risk0"] * PV * max(1, lit.qty_for(l["risk0"]))) for l in TT])), 3) \
        if TT else None
    return {k: s[k] for k in ("n", "tpw", "win", "pf", "net", "per_month", "dd", "avg_r")}


def r_stats(U, span):
    """Per-trade R on the trade's own stop (costs ignored): win %, avg R."""
    a, z = SPANS[span]
    TT = [u for u in U if a <= u["day"] <= z]
    r = np.array([u["pts"] / u["risk"] for u in TT])
    return {"win": round(100 * float((r > 0.05).mean()), 1), "avg_r_own": round(float(r.mean()), 3),
            "target_hit": round(100 * sum(u["exit"] == "TARGET" for u in TT) / len(TT), 1),
            "full_stop": round(100 * sum(u["exit"] == "STOP" for u in TT) / len(TT), 1),
            "stop_pts_med": round(float(np.median([u["risk"] for u in TT])), 1)}


def wick(U, span):
    """How often the tight stop is wicked out: tight STOP exits whose live version (same entry) won."""
    a, z = SPANS[span]
    TT = [u for u in U if a <= u["day"] <= z and u["src"] not in ("ext", "nofvg", "fallback")]
    st = [u for u in TT if u["exit"] == "STOP"]
    w = [u for u in st if u["live_pts"] > 0]
    tgt = [u for u in st if u["live_exit"] == "TARGET"]
    return {"tight_trades": len(TT), "tight_stopouts": len(st), "stopout_pct": round(100 * len(st) / len(TT), 1) if TT else None,
            "wicked_live_winner": len(w), "wicked_live_target": len(tgt),
            "wick_pct_of_stopouts": round(100 * len(w) / len(st), 1) if st else None}


# ================================================================================================ evals (3 accounts)
def run_eval(seq, by, A, horizon):
    tgt, mll, dll, lockv = A["target"], A["mll"], A["dll"], A["lock"]
    bal = peak = 0.0
    floor = -mll
    best = 0.0
    days = 0
    for kk, si in enumerate(seq[:horizon]):
        cum = 0.0
        traded = False
        for j, t in enumerate(by.get(si, [])):
            if cum <= -dll:
                break
            st = {"profit": bal, "cum": cum, "room": bal + cum - floor, "session": kk + 1, "n_today": j, "days_traded": days}
            q = S.two_week_qty({"risk_pts": t["risk"], "tgt_pts": t["tgt"]}, st, TW, acct=A)
            if A.get("day_win_cap") and t["tgt"] * PV - ECOMM > 0:
                q = min(q, max(1, int(A["day_win_cap"] / (t["tgt"] * PV - ECOMM))))
            if q <= 0:
                continue
            traded = True
            pnl = t["pts"] * PV * q - ECOMM * q
            low = min(0.0, t["w1"] * PV * q - ECOMM * q, pnl)
            if cum + low <= -dll:
                pnl = -dll - cum - SLIP * PV * q
                low = pnl
            if bal + cum + low <= floor:
                return "FAIL", kk + 1
            cum += pnl
        days += traded
        bal += cum
        best = max(best, cum)
        if bal <= floor:
            return "FAIL", kk + 1
        peak = max(peak, bal)
        floor = min(max(floor, peak - mll), lockv)
        ok = bal >= tgt and days >= A.get("min_days", 1)
        if ok and A.get("best_day") and best > A["best_day"] * bal:
            ok = False
        if ok:
            return "PASS", kk + 1
    return "OPEN", min(len(seq), horizon)


_SESS = {}


def evals(U, span, horizon=40):
    from tools import lit_final as F
    if span not in _SESS:
        a, z = SPANS[span]
        _SESS[span] = [d for d in F.SESS if a <= d <= z]
    ss = _SESS[span]
    pos = {d: i for i, d in enumerate(ss)}
    by = collections.defaultdict(list)
    for u in sorted(U, key=lambda u: u["entry_t"]):
        if u["day"] in pos:
            by[pos[u["day"]]].append(u)
    out = {}
    for nm, A in ACCTS.items():
        res = [run_eval(list(range(i, len(ss))), by, A, horizon) + (len(ss) - i,) for i in range(len(ss))]
        f10 = [r for r in res if r[2] >= 10]
        f40 = [r for r in res if r[2] >= horizon] or res
        p10 = 100 * sum(r[0] == "PASS" and r[1] <= 10 for r in f10) / len(f10)
        x10 = 100 * sum(r[0] == "FAIL" and r[1] <= 10 for r in f10) / len(f10)
        p40 = 100 * sum(r[0] == "PASS" for r in f40) / len(f40)
        x40 = 100 * sum(r[0] == "FAIL" for r in f40) / len(f40)
        med = float(np.median([r[1] for r in res if r[0] == "PASS"])) if any(r[0] == "PASS" for r in res) else None
        out[nm] = {"pass10": round(p10, 1), "fail10": round(x10, 1), "pass40": round(p40, 1), "fail40": round(x40, 1),
                   "days_to_pass": med, "cost_per_pass": round(A["price"] * 100 / p40) if p40 else None}
    return out


def boot_p(L, L0, span, n=4000, seed=7):
    """Paired bootstrap on per-trade $ differences (risk-matched): share of resamples with total diff <= 0."""
    a, z = SPANS[span]
    b = {l["entry_t"]: l["pnl"] for l in L0}
    dd = np.array([l["pnl"] - b[l["entry_t"]] for l in L if a <= l["day"] <= z])
    if not len(dd) or not dd.any():
        return 1.0
    rng = np.random.default_rng(seed)
    s = dd[rng.integers(0, len(dd), (n, len(dd)))].sum(1)
    return round(float((s <= 0).mean()), 4)


# ================================================================================================ commands
def check():
    U = units()
    bad = [u for u in U if abs(u["pts"] - u["live_pts"]) > 0.02 or u["exit"] != u["live_exit"]]
    print(f"{len(U)} trades, {len(bad)} mismatches")
    for u in bad[:10]:
        print(u["day"], u["exit"], u["live_exit"], u["pts"], u["live_pts"])
    return not bad


def time_tables():
    U = units(rec_time=True)
    out = {}
    for sp in ("H1", "H2"):
        a, z = SPANS[sp]
        TT = [u for u in U if a <= u["day"] <= z and u["tf"] == 1]
        win = [u for u in TT if u["exit"] == "TARGET"]
        stp = [u for u in TT if u["exit"] in ("STOP", "CUT_T15")]
        q = lambda xs: {p: (round(float(np.percentile(xs, p)), 1) if xs else None) for p in (25, 50, 75, 90)}
        o = {"n": len(TT), "targets": len(win), "stops": len(stp),
             "mins_to_target": q([u["mins"] for u in win]), "mins_to_stop": q([u["mins"] for u in stp]),
             "mins_to_05R_winners": q([u["t_r05"] for u in win if u["t_r05"] is not None]),
             "mins_to_1R_winners": q([u["t_r1"] for u in win if u["t_r1"] is not None])}
        rows = []
        for N in (5, 10, 15, 20, 30, 45, 60, 90, 120):
            late = [u for u in TT if (u["t_r05"] is None or u["t_r05"] > N) and u["mins"] > N]
            if late:
                rows.append({"N": N, "n_no05": len(late), "won_pct": round(100 * sum(u["exit"] == "TARGET" for u in late) / len(late), 1),
                             "avg_r": round(float(np.mean([u["pts"] / u["risk"] for u in late])), 3)})
        o["no_05R_after_N"] = rows
        out[sp] = o
    w1 = [u["t_r05"] for u in U if SPANS["H1"][0] <= u["day"] <= SPANS["H1"][1] and u["tf"] == 1 and u["exit"] == "TARGET"
          and u["t_r05"] is not None]
    N = int(math.ceil(np.percentile(w1, 80)))
    row = next((r for r in out["H1"]["no_05R_after_N"] if r["N"] >= N), None)
    late = [u for u in U if SPANS["H1"][0] <= u["day"] <= SPANS["H1"][1] and u["tf"] == 1
            and (u["t_r05"] is None or u["t_r05"] > N) and u["mins"] > N]
    wr = 100 * sum(u["exit"] == "TARGET" for u in late) / len(late) if late else None
    ar = float(np.mean([u["pts"] / u["risk"] for u in late])) if late else None
    out["N"] = N
    out["N_rule"] = "80th pct of minutes-to-+0.5R of Jan-Jun TARGET winners"
    out["tstop_condition"] = {"late_trades": len(late), "won_pct": round(wr, 1) if wr is not None else None,
                              "avg_r": round(ar, 3) if ar is not None else None,
                              "met": bool(late and wr < 15 and ar < 0)}
    out["other_bots"] = other_bots()
    json.dump(out, open(OUT_T, "w"), indent=1)
    return out


def other_bots():
    """Hold-time distributions by exit for ATLAS (run atlas_base) and BLITZ (run blitz25k_today_acct_c), 2026 H1 / H2."""
    o = {}
    for nm, f in (("ATLAS", "atlas_base"), ("BLITZ", "blitz25k_today_acct_c")):
        d = json.load(open(os.path.join(ROOT, "research", "runs", f + ".json")))
        T = [dict(zip(d["trade_cols"], r)) for r in d["trades"]]
        oo = {}
        for sp in ("H1", "H2", "2021-25"):
            a, z = SPANS[sp]
            TT = [t for t in T if a <= t["day"] <= z]
            if not TT:
                continue
            mins = lambda xs: {p: round(float(np.percentile(xs, p))) for p in (25, 50, 75, 90)} if xs else None
            win = [(t["exit_t"] - t["entry_t"]) / 60 for t in TT if (t["r"] or 0) > 0.5]
            los = [(t["exit_t"] - t["entry_t"]) / 60 for t in TT if (t["r"] or 0) <= -0.5]
            hb = []
            for lo, hi in ((0, 15), (15, 30), (30, 60), (60, 120), (120, 1e9)):
                g = [t for t in TT if lo <= (t["exit_t"] - t["entry_t"]) / 60 < hi]
                if g:
                    hb.append({"held_min": f"{lo}-{hi if hi < 1e9 else 'more'}", "n": len(g),
                               "win_pct": round(100 * sum((t["r"] or 0) > 0 for t in g) / len(g)),
                               "avg_r": round(float(np.mean([t["r"] or 0 for t in g])), 2)})
            oo[sp] = {"n": len(TT), "mins_winners": mins(win), "mins_losers": mins(los), "by_hold": hb}
        o[nm] = oo
    return o


def variants(N):
    V = {"LIVE (1 tick beyond the 5m sweep, VIX band)": {}}
    nm = {"cisd1": "A1 1m CISD candle", "swing1": "A2 1m entry swing", "fvg3": "A3 3m FVG"}
    for s in ("cisd1", "swing1", "fvg3"):
        for tg, tl in (("live", "live target price"), ("R2", "2R"), ("R3", "3R")):
            V[f"{nm[s]} stop, {tl}"] = {"stop": s, "tgt": tg}
    for tg, tl in (("liq15", "B1 next 15m liquidity"), ("liq1h", "B2 next 1h liquidity"), ("sess", "B3 opposing session high/low"),
                   ("fvg1h", "B4 1h FVG"), ("R1.5", "B5 fixed 1.5R"), ("R2", "B6 fixed 2R"), ("R3", "B7 fixed 3R")):
        V[tl] = {"tgt": tg}
    V[f"C1 time stop: no +0.5R after {N} min -> out"] = {"time": {"N": N, "rule": "tstop"}}
    V[f"C2 tighten: no +0.5R after {N} min -> stop to -0.5R"] = {"time": {"N": N, "rule": "tighten"}}
    V[f"C3 time-BE: after {N} min in profit -> breakeven"] = {"time": {"N": N, "rule": "timebe"}}
    return V


def run_all():
    tt = time_tables()
    N = tt["N"]
    V = variants(N)
    assert len(V) - 1 == N_TESTS, len(V)
    base_U = units()
    base_L = size_matched(base_U)
    res = {}
    for name, v in V.items():
        U = base_U if not v else units(v)
        Lm = size_matched(U)
        Ll = E.lit_size(U)
        o = {"params": v,
             "risk_matched": {sp: stats(Lm, sp) for sp in SPANS},
             "lit_rule": {sp: stats(Ll, sp) for sp in SPANS},
             "own_r": {sp: r_stats(U, sp) for sp in SPANS},
             "evals": {sp: evals(U, sp) for sp in SPANS}}
        e50 = E.eval_path(U)
        o["eval50_live_path"] = {sp: {k: e50[sp][k] for k in ("n", "pf", "net", "per_month", "dd", "p10", "f10", "pass_med")}
                                 for sp in e50}
        if v.get("stop"):
            o["wick"] = {sp: wick(U, sp) for sp in SPANS}
            o["tight_share"] = {sp: round(100 * sum(1 for u in U if SPANS[sp][0] <= u["day"] <= SPANS[sp][1]
                                                    and u["src"] == v["stop"]) /
                                          max(1, sum(1 for u in U if SPANS[sp][0] <= u["day"] <= SPANS[sp][1])), 1)
                                for sp in SPANS}
        if v.get("tgt") in ("liq15", "liq1h", "sess", "fvg1h"):
            o["struct_used_pct"] = {sp: round(100 * np.mean([u["struct_hit"] for u in U
                                                              if SPANS[sp][0] <= u["day"] <= SPANS[sp][1]]), 1) for sp in SPANS}
        o["boot_p_H2"] = boot_p(Lm, base_L, "H2") if v else None
        o["boot_p_H1"] = boot_p(Lm, base_L, "H1") if v else None
        res[name] = o
        rm = o["risk_matched"]
        print(f"{name[:52]:52s} H1 {rm['H1']['net']:+7,} PF {rm['H1']['pf']} | H2 {rm['H2']['net']:+7,} PF {rm['H2']['pf']} | "
              f"21-25 {rm['2021-25']['net']:+8,} | win {rm['H1']['win']}/{rm['H2']['win']} | "
              f"50K 2w {o['eval50_live_path']['H1']['p10']}/{o['eval50_live_path']['H2']['p10']}", flush=True)
    b = res[next(iter(V))]
    for name, o in res.items():
        if not o["params"]:
            o["verdict"] = "baseline"
            continue
        g = all(o["risk_matched"][h]["net"] > b["risk_matched"][h]["net"] for h in ("H1", "H2"))
        g = g and all(o["eval50_live_path"][h]["net"] > b["eval50_live_path"][h]["net"]
                      and o["eval50_live_path"][h]["f10"] <= b["eval50_live_path"][h]["f10"] for h in ("H1", "H2"))
        g = g and all(o["risk_matched"][h]["tpw"] >= 2.0 for h in ("H1", "H2"))
        g21 = o["risk_matched"]["2021-25"]["net"] >= b["risk_matched"]["2021-25"]["net"]
        sig = o["boot_p_H2"] is not None and o["boot_p_H2"] < 0.05 / N_TESTS
        o["gate"] = {"both_2026_halves": g, "2021_25_not_worse": g21, "h2_significant_bonferroni": sig}
        o["verdict"] = "PROPOSAL (owner yes needed)" if g and g21 and sig else (
            "lead (passes halves, not significant)" if g and g21 else "rejected")
    out = {"title": "Stops x targets x TIME (2026-11-24)", "kind": "stops_targets", "built": "2026-11-24",
           "writeup": "research/writeups/stops-targets-time-2026-11-24.md", "tool": "tools/stops_targets_time.py",
           "n_tests": N_TESTS, "alpha_bonferroni": round(0.05 / N_TESTS, 4), "N_minutes": N, "time": tt,
           "spans": SPANS, "note": "2021-25 has no 1m bars: A stops there are the same rule on 5m bars (proxy); A3 falls back "
                                   "to the live stop. Costs in ($1.40 + 1 tick a side on the stop/EOD exits; evals $1.90).",
           "variants": res}
    json.dump(out, open(OUT, "w"), indent=1, default=float)
    return out


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "check":
        sys.exit(0 if check() else 1)
    if cmd == "time":
        print(json.dumps(time_tables(), indent=1)[:4000])
    if cmd == "all":
        run_all()
