"""LIT untested target / exit ideas (owner, 2026-10-18: "LIT based, nothing outside; try every one and find more").

Wraps engine/lit.py (not edited) on the live LIT settings (live_model.json "lit" = lit_final + loss pack) with the live eval
sizing ($800 up to a 25-pt stop, then 800 x 25 / stop, weekly-stop half, never more than 60% of the room to the MFFU trailing
max-loss floor = run lit_tight_eval_800_25_room60). Same LIT signals, same limit at the 5m CISD level, same 1m CISD
confirmation, same stop 1 tick beyond the sweep extreme. Only the target / exit side changes:

  1. HTF FVG / order block targets (classes fvg1h, fvg4h, ob1h, ob4h, optionally next to "vix"): the nearest unfilled 1H / 4H
     fair value gap edge (the part of the gap price has not traded into yet) or untouched 1H / 4H order block edge in the
     trade's direction, >= 1.5R; tgt_pick "nearest" = the nearer of every class listed, "htf_else_vix" = the HTF level when
     there is one >= 1.5R, else the VIX band. HTF candles are built from the 5m file (1H clock hours, 4H from 18:00 ET) and
     count only once closed by the trigger candle's close. Banked at 8R as live.
  2. Time exits in profit (tx): out at the open of the first bar starting at/after the time (high-impact 08:30 ET release
     minus a lead, or the London close 11:00 / 11:30 ET) if the open profit there is >= tx_r R; else the trade runs on.
  3. Opposite-inducement exit (oi): while long, a confirmed 5m swing high that sits within 1 ATR below an untaken high-side LIT
     level (the inducement a short LIT setup would need) gets traded through with the swing >= oi_r R above the entry: out at
     that bar's close (- 1 tick). Mirror for shorts. oi_mode "rev": out at the next bar open after a full opposite LIT setup
     (an opposite-direction candidate that passes the live setup filters) triggers while the trade is >= oi_r R in profit.
  4. Daily profit stop (pstop $): no new trade on a day once the day's closed P&L is >= $X; with max_per_day 2.
  5. Bank / band: max_rr 6 / 10 / None, vix_k 0.8 / 1.2.
  6. (found) Front-run the VIX band: the target sits front_k VIX moves (or front_pts points) before the band.

  python tools/lit_t_targets.py check   # default options == lit_tightstop ext (== run lit_live), 120 trades in 2026
  python tools/lit_t_targets.py grid    # every idea -> research/lit/t_targets_results.json
  python tools/lit_t_targets.py save    # store runs lit_u_targets_* (rl.save, family other, tags lit, lit_untested, lit_targets)
Pick on 2026 H1 (Jan 2 - Jun 30), check on 2026 H2 (Jul 1 - Oct 16); 2021-25 is a reference line (5m only). 1 CPU process.
"""
from __future__ import annotations

import collections
import csv
import datetime as dt
import json
import os
import sys
from zoneinfo import ZoneInfo

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import lit  # noqa: E402
from tools import lit_final as F  # noqa: E402
from tools import lit_tightstop as T  # noqa: E402
from tools import runlib as rl  # noqa: E402

OUT = os.path.join(ROOT, "research", "lit", "t_targets_results.json")
SESS, SPAN, LIVE = T.SESS, T.SPAN, T.LIVE
PV, COMM, SLIP = lit.PV, lit.COMM, lit.SLIP
EVAL = ("lit", 800, 25.0)
ROOM = 0.6
ET = ZoneInfo("America/New_York")

ODEF = {
    "tgt_pick": "nearest", "htf_edge": "edge", "htf_lb": {"1h": 1380, "4h": 5520},
    "tx": None, "tx_r": 1.0, "tx_lead": 300,
    "oi": None, "oi_r": 1.0, "oi_atr": 1.0,
    "pstop": None,
    "front_k": 0.0, "front_pts": 0.0,
}


def P_of(P=None):
    return {**LIVE, **ODEF, **(P or {})}


# ================================================================================================ HTF zones
_Z = {}


def _htf(M, tf):
    """HTF candles from the 5m file: (o, h, l, c, last 5m index)."""
    if tf == "1h":
        g = M.t // 3600
    else:
        g = M.day_of.astype(np.int64) * 10 + ((M.mod - 1080) % 1440) // 240
    st = np.r_[0, np.flatnonzero(np.diff(g)) + 1]
    en = np.r_[st[1:], M.n] - 1
    o = M.o[st]; c = M.c[en]
    h = np.maximum.reduceat(M.h, st); l = np.minimum.reduceat(M.l, st)
    return o, h, l, c, en


def zones(M, kind, tf, d):
    """Direction-space zones [(near edge, far edge, known 5m index)] of kind fvg / ob on tf, for trades in direction d."""
    key = (id(M), kind, tf, d)
    if key in _Z:
        return _Z[key]
    o, h, l, c, en = _htf(M, tf)
    if d == 1:
        hd, ld, cd, od = h, l, c, o
    else:
        hd, ld, cd, od = -l, -h, -c, -o
    out = []
    if kind == "fvg":
        for j in range(2, len(o)):
            if ld[j] > hd[j - 2]:
                out.append((float(hd[j - 2]), float(ld[j]), int(en[j])))
            elif hd[j] < ld[j - 2]:
                out.append((float(hd[j]), float(ld[j - 2]), int(en[j])))
    else:   # order block above (direction space): up-close candle, then a down-close candle closing below its low
        for j in range(len(o) - 1):
            if cd[j] > od[j] and cd[j + 1] < od[j + 1] and cd[j + 1] < ld[j]:
                out.append((float(ld[j]), float(hd[j]), int(en[j + 1])))
    out.sort(key=lambda z: z[2])
    arr = (np.array([z[0] for z in out]), np.array([z[1] for z in out]), np.array([z[2] for z in out], dtype=np.int64))
    _Z[key] = arr
    return arr


def htf_targets(M, z, cls, P):
    """Distances from the market entry (direction space) to the nearest unfilled FVG edge / untouched OB edge of class cls."""
    kind, tf = cls[:-2], cls[-2:]
    d, i = z["dir"], z["i"]
    zb, zt, kn = zones(M, kind, tf, d)
    hi5 = M.h if d == 1 else -M.l
    lb = P["htf_lb"][tf]
    a = int(np.searchsorted(kn, i - lb)); b = int(np.searchsorted(kn, i, side="right"))
    out = []
    for q in range(a, b):
        k0 = int(kn[q])
        mx = float(hi5[k0 + 1:i + 1].max()) if i > k0 else -np.inf
        if kind == "fvg":
            near = max(zb[q], mx)
            if near >= zt[q]:
                continue
            px = near if P["htf_edge"] == "edge" else 0.5 * (near + zt[q]) if P["htf_edge"] == "ce" else zt[q]
        else:
            if mx >= zb[q]:
                continue
            px = zb[q] if P["htf_edge"] == "edge" else 0.5 * (zb[q] + zt[q]) if P["htf_edge"] == "ce" else zt[q]
        if px > z["entry_d"]:
            out.append(round(px - z["entry_d"], 2))
    return sorted(out)


def targets(M, z, P):
    T_ = {c: v for c, v in lit.targets_x(M, z, P).items()}
    if "vix" in T_ and (P["front_k"] or P["front_pts"]):
        vm = M.ctx[z["k"]].get("vix_move") or 0.0
        T_["vix"] = [x - P["front_k"] * vm - P["front_pts"] for x in T_["vix"]]
        T_["vix"] = [x for x in T_["vix"] if x > 0]
    for c in P["classes"]:
        if c[:3] in ("fvg", "ob1", "ob4"):
            T_[c] = htf_targets(M, z, c, P)
    return T_


# ================================================================================================ exit helpers
_NEWS = {}


def news_times(at=("08:30",)):
    key = tuple(at)
    if key not in _NEWS:
        ts = set()
        for r in csv.DictReader(open(os.path.join(ROOT, "data", "news", "events.csv"), encoding="utf-8")):
            if r.get("impact", "").lower() != "high" or r["time_et"] not in at:
                continue
            y, m, dd = map(int, r["date"].split("-")); hh, mm = map(int, r["time_et"].split(":"))
            ts.add(int(dt.datetime(y, m, dd, hh, mm, tzinfo=ET).timestamp()))
        _NEWS[key] = np.array(sorted(ts), dtype=np.int64)
    return _NEWS[key]


def tx_time(M, B, fill, P):
    """Unix time of the time exit for a trade filled on bar `fill` of B (None = no time exit that day after the fill)."""
    tx = P["tx"]
    t_f = int(B.t[fill])
    if tx == "news":
        nt = news_times()
        j = int(np.searchsorted(nt, t_f + P["tx_lead"], side="right"))
        if j >= len(nt):
            return None
        t = int(nt[j]) - P["tx_lead"]
        return t if t - t_f < 12 * 3600 else None
    mod = int(tx)                      # ET minute of the day (660 = 11:00)
    m_f = int(B.mod[fill])
    if m_f >= mod or m_f >= 1080:
        return None
    return t_f + (mod - m_f) * 60 - (t_f % 60)


def opp_inducements(M, z, P, fill_t):
    """[(known unix time, direction-space swing price)] of the swings that would induce the reverse LIT trade."""
    d, k = z["dir"], z["k"]
    x = M.ctx[k]; s, e = x["s"], x["e"]
    sw = M.fh if d == 1 else M.fl
    hi5 = M.h if d == 1 else -M.l
    L = [(px * d, ki) for side, px, ki, nm, cls in M.levels(k) if (side == "high") == (d == 1)]
    out = []
    a = int(np.searchsorted(sw, s - 72)); b = int(np.searchsorted(sw, e - 2))
    for m in sw[a:b]:
        m = int(m)
        if m + 2 >= M.n:
            continue
        p = float(hi5[m]); at = float(M.atr[m])
        ok = False
        for lv, ki in L:
            if ki < m and lv > p and lv - p <= P["oi_atr"] * at:
                st = max(ki + 1, s - 600)
                if hi5[st:m + 3].max() < lv:
                    ok = True; break
        if ok:
            out.append((int(M.t[m + 2]) + 300, p, m))
    return out


def rev_times(M, C, P):
    """{(day, dir): sorted unix times} when an opposite-direction LIT setup (live filters) closed its trigger candle."""
    names = set(P["sweep_names"]) if P.get("sweep_names") else None
    R = collections.defaultdict(list)
    for z in C:
        if lit.setup_ok(z, P, names):
            R[(z["day"], -z["dir"])].append(int(M.t[z["i"]]) + 300)
    return {k: sorted(v) for k, v in R.items()}


# ================================================================================================ executor (unit size)
def osim(M, B, z, entry_px, tgt_lvl, fb, stop0, P, RV=None):
    """lit.simulate_x (research mode, 1m CISD entry) at 1 micro + the target / exit options (== T.tsim with stop_mode ext)."""
    d = z["dir"]
    hi_d, lo_d, c_d, o_d = B.dirs(d)
    t0 = int(M.t[z["entry_i"]])
    k0 = int(np.searchsorted(B.t, t0))
    s_day = int(M.day_of[z["entry_i"]])
    if k0 >= B.n:
        return None
    flat = P["flat_mod"]
    wait_s = P["wait"] * 300
    cis = P.get("cisd1m")
    if cis and B.secs == 300:
        cis = max(1, cis // 5)
    limit_fill = True
    fill = tapped = None
    k = k0
    while k < B.n:
        if B.day[k] != s_day or B.mod[k] >= flat or B.mod[k] >= 1080:
            break
        if tapped is None and B.t[k] >= t0 + wait_s:
            break
        if lo_d[k] <= stop0:
            if tapped is None and lo_d[k] <= entry_px and not cis:
                fill = k; entry = min(entry_px, float(o_d[k]))
            break
        if tapped is None and lo_d[k] <= entry_px:
            if cis:
                tapped = k
            else:
                fill = k; entry = min(entry_px, float(o_d[k])); break
        if tapped is None and hi_d[k] >= tgt_lvl:
            break
        if tapped is not None:
            if k - tapped > cis:
                break
            lowk = tapped + int(np.argmin(lo_d[tapped:k + 1]))
            cz = lit._cisd_level(c_d, o_d, lowk)
            if cz is not None and k > lowk and c_d[k] > cz[0] and k + 1 < B.n and B.day[k + 1] == s_day:
                fill = k + 1; entry = float(o_d[k + 1]) + SLIP; limit_fill = False
                break
        k += 1
    if fill is None:
        return None
    stop = stop0
    risk = entry - stop
    if risk <= 0 or lit.qty_for(risk) < 1:
        return None
    if fb:
        tg = entry + P["fallback_rr"] * risk
    else:
        dist = tgt_lvl - entry
        if dist < P["min_rr"] * risk:
            return None
        tg = entry + (min(dist, P["max_rr"] * risk) if P["max_rr"] else dist)
    be_r = P["be_r"]
    # exit options
    t_tx = tx_time(M, B, fill, P) if P["tx"] is not None else None
    OI = []
    if P["oi"] == "idm":
        ei5 = int(np.searchsorted(M.t, B.t[fill], side="right") - 1)
        hi5 = M.h if d == 1 else -M.l
        for kt, p, m in opp_inducements(M, z, P, int(B.t[fill])):
            if p - entry < P["oi_r"] * risk:
                continue
            if ei5 > m + 1 and hi5[m + 1:ei5].max() >= p:      # already taken before the fill
                continue
            OI.append((kt, p))
    RVt = []
    if P["oi"] == "rev" and RV is not None:
        RVt = [t for t in RV.get((z["day"], d), []) if t > int(B.t[fill])]
    cur, be_done, mfe, mae, worst = stop, False, 0.0, 0.0, 0.0
    k = fill
    exit_px = kind = None
    while k < B.n:
        if B.day[k] != s_day or B.mod[k] >= 1080:
            k -= 1; exit_px, kind = float(c_d[k]) - SLIP, "EOD"; break
        if k > fill:
            if t_tx is not None and B.t[k] >= t_tx:
                if o_d[k] - entry >= P["tx_r"] * risk:
                    exit_px, kind = float(o_d[k]) - SLIP, "TX"; break
                t_tx = None
            while RVt and B.t[k] >= RVt[0]:
                RVt.pop(0)
                if o_d[k] - entry >= P["oi_r"] * risk:
                    exit_px, kind = float(o_d[k]) - SLIP, "REV"; break
            if kind:
                break
        mae = max(mae, (entry - lo_d[k]) / risk)
        worst = min(worst, lo_d[k] - entry)
        if lo_d[k] <= cur:
            exit_px, kind = cur - SLIP, ("BE" if be_done else "STOP"); break
        if not (k == fill and limit_fill):
            mfe = max(mfe, (hi_d[k] - entry) / risk)
            if hi_d[k] >= tg:
                exit_px, kind = tg, "TARGET"; break
            if be_r is not None and not be_done and hi_d[k] >= entry + be_r * risk:
                cur, be_done = entry, True
            if OI and any(kt <= B.t[k] and hi_d[k] > p for kt, p in OI):
                exit_px, kind = float(c_d[k]) - SLIP, "OI"; break
        if B.mod[k] >= flat:
            exit_px, kind = float(c_d[k]) - SLIP, "EOD"; break
        k += 1
    if exit_px is None:
        return None
    xi5 = int(np.searchsorted(M.t, B.t[k], side="right") - 1)
    return {"day": z["day"], "entry_t": int(B.t[fill]), "exit_t": int(B.t[k]) + B.secs, "exit_i": xi5, "dir": d,
            "risk_pts": round(risk, 2), "risk0": round(risk, 2), "exit": kind, "trigger": "LIT-" + ("1m" if B.secs == 60 else "5m"),
            "mfe": round(mfe, 3), "mae": round(min(mae, 1.0 + SLIP / risk), 3), "bars_held": int(k - fill + 1), "regime": "",
            "half": False, "legs": [(1.0, exit_px - entry)], "w1": worst, "w2": 0.0, "part": False, "stop_src": "ext",
            "entry_px": round(entry * d, 2), "stop_px": round(stop * d, 2), "stop0_px": round(stop0 * d, 2),
            "target_px": round(tg * d, 2), "e2_px": None, "limit_fill": limit_fill, "swept": z["swept"], "tf": B.secs // 60,
            "i": z["i"], "ext_i": z["ext_i"]}


def orun(P=None, sessions=SESS):
    P = P_of(P)
    names = set(P["sweep_names"]) if P.get("sweep_names") else None
    sset = set(sessions) if sessions else None
    M, C = F.market(P["ref"], P["extra_boxes"])
    B5 = F.bars(M, "5m")
    B1 = F.bars(M, "1m") if P["tf"] == "1m" else None
    RV = rev_times(M, C, P) if P["oi"] == "rev" else None
    out, busy, per_day = [], -1, collections.Counter()
    for z in C:
        if sset is not None and z["day"] not in sset:
            continue
        if z["entry_i"] <= busy or per_day[z["day"]] >= P["max_per_day"]:
            continue
        if not lit.setup_ok(z, P, names):
            continue
        if P.get("monday") and lit.monday_block(M, z):
            continue
        ep = min(float(z["ref_d"]), z["trig_c"])
        stop0 = z["ext_d"] - P["stop_buf"]
        risk = ep - stop0
        if not (P["min_stop"] <= risk <= P["max_stop"]):
            continue
        sh = z["entry_d"] - ep
        TT = {c: [x + sh for x in v] for c, v in targets(M, z, P).items()}
        first = {}
        for c in P["classes"]:
            for dist in TT.get(c, []):
                if dist >= P["min_rr"] * risk:
                    first[c] = dist
                    break
        best = None
        if P["tgt_pick"] == "htf_else_vix":
            h = [v for c, v in first.items() if c != "vix"]
            best = min(h) if h else first.get("vix")
        elif first:
            best = min(first.values())
        fb = False
        if best is None:
            if not P["fallback_rr"]:
                continue
            tp, fb = P["fallback_rr"] * risk, True
        else:
            tp = min(best, P["max_rr"] * risk) if P["max_rr"] else best
        use1 = P["tf"] == "1m" and B1 is not None and int(M.day_of[z["entry_i"]]) in B1.full
        B = B1 if use1 else B5
        t = osim(M, B, z, ep, ep + tp, fb, stop0, P, RV)
        if t is None:
            continue
        t["tgt_cls"] = "fallback" if fb else next((c for c, v in first.items() if v == best), None)
        busy = t["exit_i"]; per_day[z["day"]] += 1
        out.append(t)
    return out


_U = {}


def unit(P=None):
    key = json.dumps(P or {}, sort_keys=True, default=str)
    if key not in _U:
        U = orun(P)
        T.wk_marks(U)
        ps = P_of(P)["pstop"]
        if ps:
            _pstop_marks(U, ps)
        _U[key] = U
    return _U[key]


def _pstop_marks(U, ps):
    """Mark the trades the daily profit stop skips on the plain eval-size path, then redo the weekly-stop marks without them."""
    skip = set()
    day_cum = collections.defaultdict(float)
    for t in sorted(U, key=lambda t: t["entry_t"]):
        if day_cum[t["day"]] >= ps:
            skip.add(id(t)); t["ps_skip"] = True
            continue
        mi, mn = T.qty_of(t, EVAL)
        day_cum[t["day"]] += T.at_size(t, mi, mn)["pnl"]
    kept = [t for t in U if id(t) not in skip]
    T.wk_marks(kept)


# ================================================================================================ scoring (T's, + profit stop)
def _play(ss, by, i0, H, rule, room_k, pstop, keep=None):
    PLAN = T.PLAN
    bal = PLAN["start"]; peak = bal; mll = bal - PLAN["mll"]; lock = PLAN["start"] + PLAN["lock_above"]
    for k in range(i0, min(len(ss), i0 + H)):
        cum = low = 0.0
        for t in by.get(ss[k], []):
            if T.DLL and cum <= -T.DLL:
                break
            if pstop is not None and cum >= pstop:
                break
            mi, mn = T.qty_of(t, rule, room=bal + cum - mll, room_k=room_k)
            x = T.at_size(t, mi, mn, cum)
            low = min(low, cum + x["low"]); cum += x["pnl"]; low = min(low, cum)
            if keep is not None:
                keep.append(x)
        if bal + low <= mll or bal + cum <= mll:
            return "FAIL", k - i0 + 1
        bal += cum
        peak = max(peak, bal)
        mll = min(max(mll, peak - PLAN["mll"]), lock)
        if bal - PLAN["start"] >= PLAN["target"]:
            return "PASS", k - i0 + 1
    return "OPEN", min(len(ss), i0 + H) - i0


def evals(U, rule, span, room_k=None, pstop=None, horizon=60):
    a, z = SPAN[span]
    ss = [d for d in SESS if a <= d <= z]
    by = collections.defaultdict(list)
    for t in sorted(U, key=lambda t: t["entry_t"]):
        if a <= t["day"] <= z:
            by[t["day"]].append(t)
    res = [_play(ss, by, i, horizon, rule, room_k, pstop) for i in range(len(ss))]
    N = len(res) or 1
    o = {}
    for H in (10, 20):
        o[f"p{H}"] = round(100 * sum(1 for r, n in res if r == "PASS" and n <= H) / N, 1)
        o[f"f{H}"] = round(100 * sum(1 for r, n in res if r == "FAIL" and n <= H) / N, 1)
    P_ = sum(1 for r, _ in res if r == "PASS"); F_ = sum(1 for r, _ in res if r == "FAIL")
    o["pass_rate"] = round(100 * P_ / (P_ + F_), 1) if P_ + F_ else None
    pas = [n for r, n in res if r == "PASS"]
    o["pass_med"] = float(np.median(pas)) if pas else None
    k, pa, fa, path = 0, 0, 0, []
    while k < len(ss):
        r, n = _play(ss, by, k, len(ss), rule, room_k, pstop, keep=path)
        if r == "OPEN":
            break
        pa += r == "PASS"; fa += r == "FAIL"; k += n
    o["b2b"] = f"{pa}/{fa}"
    return o, path


def stats(Tr, span):
    s = T.stats(Tr, span)
    a, z = SPAN[span]
    p = np.array([t["pnl"] for t in Tr if a <= t["day"] <= z])
    if len(p):
        s["avg_win"] = round(float(p[p > 0].mean())) if (p > 0).any() else 0
        s["avg_loss"] = round(float(p[p <= 0].mean())) if (p <= 0).any() else 0
    return s


SP = ("H1", "H2", "2026", "2021-25")


def score(U, rule=EVAL, room_k=ROOM, pstop=None, spans=SP):
    out = {}
    for s in spans:
        e, path = evals(U, rule, s, room_k, pstop)
        out[s] = {**stats(path, s), **e}
    return out


def row(nm, o, spans=("H1", "H2", "2021-25")):
    def f(s):
        if not s or not s.get("n"):
            return "n=0"
        return (f"n={s['n']} {s['tpw']}/wk win {s['win']} PF {s['pf']} net {s['net']:+,} ${s['per_month']:,}/mo DD {s['dd']:,} "
                f"2w {s['p10']}/{s['f10']} 1m {s['p20']}/{s['f20']} pr {s['pass_rate']} med {s['pass_med']}")
    return f"{nm:34s} " + " | ".join(f"{k}[{f(o.get(k))}]" for k in spans if k in o)


# ================================================================================================ check
def check():
    U = unit()
    B = T.unit()
    ka = [(t["day"], t["entry_t"], round(t["legs"][0][1], 2), t["exit"], t.get("wk_m")) for t in sorted(B, key=lambda t: t["entry_t"])]
    kb = [(t["day"], t["entry_t"], round(t["legs"][0][1], 2), t["exit"], t.get("wk_m")) for t in sorted(U, key=lambda t: t["entry_t"])]
    bad = sum(1 for x, y in zip(ka, kb) if x != y) + abs(len(ka) - len(kb))
    n26 = sum(1 for t in U if t["day"] >= "2026")
    print(f"tightstop ext {len(ka)} | targets wrapper {len(kb)} | mismatches {bad} | 2026 trades {n26}")
    L = T.sized(U, ("lit", 800, 20.0))
    print("LIT rule 2026 net", round(sum(t["pnl"] for t in L if t["day"] >= "2026")), "(lit_live +41,734)")
    o = score(U, spans=("H1", "H2", "2026"))
    for s in ("H1", "H2", "2026"):
        print(s, {k: o[s].get(k) for k in ("n", "pf", "net", "per_month", "dd", "p10", "f10", "p20", "f20", "pass_rate", "pass_med")})
    return bad == 0 and n26 == 120


# ================================================================================================ the ideas
def variants():
    V = collections.OrderedDict()
    V["base"] = ("baseline", {})
    # 1. HTF FVG / OB targets
    for c in ("fvg1h", "fvg4h", "ob1h", "ob4h"):
        V[f"htf_{c}_alone"] = ("htf", {"classes": [c]})
        V[f"htf_{c}_nearer"] = ("htf", {"classes": ["vix", c]})
        V[f"htf_{c}_else_vix"] = ("htf", {"classes": ["vix", c], "tgt_pick": "htf_else_vix"})
    V["htf_fvg1h_far_nearer"] = ("htf", {"classes": ["vix", "fvg1h"], "htf_edge": "far"})
    V["htf_fvg4h_far_nearer"] = ("htf", {"classes": ["vix", "fvg4h"], "htf_edge": "far"})
    V["htf_fvg4h_ce_nearer"] = ("htf", {"classes": ["vix", "fvg4h"], "htf_edge": "ce"})
    V["htf_all4h_nearer"] = ("htf", {"classes": ["vix", "fvg4h", "ob4h"]})
    V["htf_all_nearer"] = ("htf", {"classes": ["vix", "fvg1h", "fvg4h", "ob1h", "ob4h"]})
    # 2. time exits in profit
    for r in (0.5, 1.0, 2.0):
        V[f"tx_news0830_l5_{r:g}R"] = ("tx", {"tx": "news", "tx_lead": 300, "tx_r": r})
    V["tx_news0830_l1_1R"] = ("tx", {"tx": "news", "tx_lead": 60, "tx_r": 1.0})
    for mod in (660, 690):
        for r in (0.5, 1.0, 2.0):
            V[f"tx_{mod // 60:02d}{mod % 60:02d}_{r:g}R"] = ("tx", {"tx": mod, "tx_r": r})
    for mod in (675, 705, 720):           # neighbours of the 11:30 pick: 11:15, 11:45, 12:00
        for r in (0.5, 1.0):
            V[f"tx_{mod // 60:02d}{mod % 60:02d}_{r:g}R"] = ("tx", {"tx": mod, "tx_r": r})
    V["tx_1130_0R"] = ("tx", {"tx": 690, "tx_r": 0.0})
    # 3. opposite inducement / opposite LIT setup
    for r in (0.0, 1.0, 2.0, 3.0):
        V[f"oi_idm_{r:g}R"] = ("oi", {"oi": "idm", "oi_r": r})
    V["oi_idm_1R_0.5atr"] = ("oi", {"oi": "idm", "oi_r": 1.0, "oi_atr": 0.5})
    for r in (0.0, 1.0, 2.0):
        V[f"oi_rev_{r:g}R"] = ("oi", {"oi": "rev", "oi_r": r})
    # 4. daily profit stop with 2 trades a day
    V["mpd2"] = ("pstop", {"max_per_day": 2})
    for x in (500, 800, 1200):
        V[f"mpd2_pstop{x}"] = ("pstop", {"max_per_day": 2, "pstop": float(x)})
    V["mpd1_pstop800"] = ("pstop", {"pstop": 800.0})
    # 5. bank / band
    for b in (6.0, 10.0, None):
        V[f"bank_{'none' if b is None else int(b)}R"] = ("bank", {"max_rr": b})
    for k in (0.8, 0.9, 1.1, 1.2):
        V[f"vix_k{k:g}"] = ("bank", {"vix_k": k})
    # 6. found: front-run the VIX band
    for f in (0.05, 0.1):
        V[f"front_{f:g}move"] = ("front", {"front_k": f})
    for p in (2.0, 5.0):
        V[f"front_{p:g}pts"] = ("front", {"front_pts": p})
    return V


def _load():
    return json.load(open(OUT)) if os.path.exists(OUT) else {}


def grid(only=None):
    res = _load()
    for nm, (fam, P) in variants().items():
        if only and not any(o in nm for o in only):
            continue
        U = unit(P)
        o = score(U, pstop=P_of(P)["pstop"])
        U26 = [t for t in U if t["day"] >= "2026" and not t.get("ps_skip")]
        o["_exits"] = dict(collections.Counter(t["exit"] for t in U26))
        o["_cls"] = dict(collections.Counter(str(t.get("tgt_cls")) for t in U26))
        res[nm] = {"family": fam, "params": P, "score": o}
        print(row(nm, o), o["_exits"], flush=True)
        json.dump(res, open(OUT, "w"), indent=1, default=str)
    return res


# ================================================================================================ store runs
def _py(v):
    """numpy scalars -> python (rl.save writes plain json)."""
    if isinstance(v, np.integer):
        return int(v)
    if isinstance(v, np.floating):
        return float(v)
    if isinstance(v, np.bool_):
        return bool(v)
    return v

def save(names=None, status_of=None, why_of=None, skip=()):
    V = variants()
    res = _load()
    for nm in names or list(V):
        if nm in skip:
            continue
        fam, P = V[nm]
        U = unit(P)
        ps = P_of(P)["pstop"]
        Tr = evals(U, EVAL, "2026", ROOM, ps)[1] + evals(U, EVAL, "2021-25", ROOM, ps)[1]
        Tr = [{k: _py(v) for k, v in t.items() if k not in ("legs",)} for t in Tr]
        S = json.loads(json.dumps(rl.score(Tr, SESS), default=_py))
        o = res.get(nm, {}).get("score") or score(U, pstop=ps)
        h = lambda s: (f"n={s['n']} {s['tpw']}/wk win {s['win']}% PF {s['pf']} net {s['net']:+,} (${s['per_month']:,}/mo) DD {s['dd']:,} "
                       f"eval 2wk {s['p10']}/{s['f10']} 1mo {s['p20']}/{s['f20']} pass rate {s['pass_rate']}% median {s['pass_med']}")
        st = (status_of or {}).get(nm, "info" if nm == "base" else "rejected")
        rid = "lit_u_targets_" + nm.replace(".", "p")
        rl.save(rid, f"LIT untested targets: {nm}", "other",
                "Owner order 2026-10-18: LIT only - do HTF FVG/OB targets, time exits in profit, opposite-inducement exits, a daily "
                "profit stop or other bank/band levels beat the VIX band at 8R?",
                params={**LIVE, **ODEF, **P, "size": list(EVAL), "room_k": ROOM}, trades=Tr, scored=S, status=st,
                verdict=f"{(why_of or {}).get(nm, '')} 2026 H1 (pick) {h(o['H1'])}; 2026 H2 (check) {h(o['H2'])}; "
                        f"2021-25 reference only {h(o['2021-25'])}",
                notes="tools/lit_t_targets.py (wraps engine/lit.py; default options == lit_tightstop ext == run lit_live trade for "
                      "trade). Eval sizing $800 up to 25 pts + 60% room cap, b2b MFFU eval path trades.",
                writeup="lit-untested-targets", tags=["lit", "lit_untested", "lit_targets"])
        print("saved", rid, flush=True)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "check":
        print("OK" if check() else "MISMATCH")
    elif cmd == "grid":
        grid(sys.argv[2:] or None)
    elif cmd == "save":
        save(sys.argv[2:] or None)
