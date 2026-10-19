"""LIT entry precision (owner, 2026-10-18: "Get more bots to get the perfect entries. I need entries that are on dot.") plus the
owner's advanced report ch.5 / ch.13 experiment 1: direct-zone entry vs delayed confirmation vs refined limit, compared PER
ORIGINAL CANDIDATE (a missed fill counts as 0, never dropped), net $ per candidate at one common cash budget, fill fraction.

Same LIT signals as live (live_model.json "lit" = lit_final + loss pack; tools/lit_tightstop.py market / bars / candidate walk;
engine/lit.py not edited). The candidate set, the stop (1 tick beyond the 5m sweep extreme = the 1m sweep extreme, the 1m bars
rebuild the 5m bars exactly), the target PRICE (VIX band, >= 1.5R re-measured from the real fill, banked at 8R) and the
management (BE at 1R of the real risk, flat 15:55) are the live ones. Only HOW and WHERE the entry fills changes:

  mode   cisd1m  (live) the zone tap starts a 1m CISD watch (cisd1m bars); fill at the next 1m open + 1 tick
         direct  a resting limit at the zone, valid `wait` 5m bars; fills only when price trades THROUGH it by `thru` ticks
                 (0 = touch), at min(limit, bar open); the fill bar gets no target / breakeven credit (conservative)
         bos1m   tap -> first 1m close above the last 1m swing high (3-bar fractal) before the post-tap low -> next open
         reclaim tap -> price trades below the zone, then the first 1m close back above it -> next open
         close   as cisd1m, but the fill is the CISD candle's close + 1 tick (signal-bar close vs next open)
         two     two-step: half a resting limit at the zone (trade-through), half on the 1m CISD (next open)
  zone   cisd (live: the 5m CISD level) | disp50 (50% of the 5m displacement leg, extreme -> leg high) | idm (the highest
         inducement swing that qualified the setup) | swept (the swept level itself) | mid (halfway between the CISD level
         and the trigger close)
  tol    the tap counts when price comes within tol ticks of the zone (entry tolerance)
  lm     limit-then-market after the 1m confirmation: (level, n): a limit at level (close = CISD candle close, mid = its
         body 50%, cisd1 = the 1m CISD level, fvg = the 1m FVG top) for n 1m bars (trade-through fill); not filled -> market
         at the open after n bars (cancelled if the target trades first or the stop breaks)
  runaway skip when the fill is more than x planned R above the zone (patience; the day stays free)
  wait / cisd1m: the live P keys (5m bars the zone is valid / 1m bars to see the CISD)

Scoring (all costs in: $1.40 a micro, 1 tick on market entries and on stop / BE / EOD exits):
  1. per candidate (report ch.5): every 2026 setup that passes the live filters, simulated alone (no one-a-day queue),
     sized at a common budget U = $1,000 (integer micros at the policy's own fill risk); net $ per candidate counts a
     missed fill as $0; paired difference vs live per candidate; fill fraction.
  2. the account path (one trade a day, a missed setup leaves the day free): the LIT rule ($800 up to 20 pts, weekly stop)
     for $ / $ a month / PF / win % / max DD, and the LIVE eval sizing (lit_sizing two_week: one winner passes, 60% room
     cap, $1,000 soft daily loss, 40 micros) for the MFFU 50K pass / fail within 10 sessions (fresh eval every session of
     the half, tools/lit_2wk.run_eval) + a 4,000-path Monte Carlo.
  Pick on 2026 H1 (Jan 2 - Jun 30), check on H2 (Jul 1 - Oct 16).

  python -X utf8 tools/lit_entry_precision.py check   # live mode == lit_tightstop.unit() (== run lit_live) + two-week numbers
  python -X utf8 tools/lit_entry_precision.py grid    # every variant -> research/lit/entry_precision.json
  python -X utf8 tools/lit_entry_precision.py save    # store the runs lit_ep_*
Paper only. 1 process.
"""
from __future__ import annotations

import collections
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import lit  # noqa: E402
from tools import lit_tightstop as T  # noqa: E402
from tools import lit_2wk as W  # noqa: E402

F = T.F
OUT = os.path.join(ROOT, "research", "lit", "entry_precision.json")
PV, COMM, SLIP, TICK = lit.PV, lit.COMM, lit.SLIP, 0.25
S26 = [d for d in T.SESS if d >= "2026-01-01"]
LIVE = T.LIVE
TW = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))["lit_sizing"]["two_week"]
U_BUDGET = 1000.0
EDEF = {"mode": "cisd1m", "zone": "cisd", "tol": 0, "thru": 1, "lm": None, "runaway": None, "two_w": 0.5, "ctf": 1}


def P_of(X=None):
    return {**LIVE, **T.TDEF, **EDEF, **(X or {})}


# ================================================================================================ zone level
def zone_level(M, z, P, ep_live, stop0):
    d = z["dir"]
    mode = P["zone"]
    if mode == "cisd":
        L = ep_live
    elif mode == "disp50":
        hi5 = M.h if d == 1 else -M.l
        top = float(hi5[z["ext_i"]:z["i"] + 1].max())
        L = 0.5 * (top + z["ext_d"])
    elif mode == "mid":
        L = 0.5 * (ep_live + z["trig_c"])
    elif mode == "swept":
        L = max(z["sw"].values())
    elif mode == "idm":
        lev = max(z["sw"].values()); at = float(M.atr[z["sweep_i"]])
        dm, age, _ = P["idm_a"] or (1.0, 36, 1)
        px = [lev + dd * at for dd, aa in z["idm_a"] if dd <= dm and aa <= age]
        L = max(px) if px else ep_live
    else:
        raise ValueError(mode)
    L = min(L, z["trig_c"])
    if L <= stop0 + 1.0:                 # a zone at / under the stop is no entry: fall back to the live level
        L = ep_live
    return L


def _bos_level(hi_d, tapped, lowk):
    """The last 1m swing high (3-bar fractal, confirmed) before the post-tap low; else the high of the bars tap..low."""
    for j in range(lowk - 1, max(tapped - 30, 1) - 1, -1):
        if j + 1 <= lowk and hi_d[j] > hi_d[j - 1] and hi_d[j] >= hi_d[j + 1]:
            return float(hi_d[j])
    return float(hi_d[tapped:lowk + 1].max())


def _cisd_agg(B, hi_d, lo_d, c_d, o_d, tapped, k, m):
    """CISD on m-minute bars (clock-aligned, built from the 1m bars from the tap's m-minute bar on), checked only when bar k
    closes an m-minute bar (no look-ahead: a decision on a closed m-minute bar)."""
    if (int(B.mod[k]) + 1) % m:
        return False
    g0 = int(B.mod[tapped]) // m
    at = tapped - (int(B.mod[tapped]) - g0 * m)          # first 1m bar of the tap's m-minute bar
    a = max(at - 30 * m, 0)
    while a < at and B.day[a] != B.day[tapped]:
        a += 1
    O, H, L_, C = [], [], [], []
    j = a
    while j <= k:
        g = int(B.mod[j]) // m
        e = j
        while e + 1 <= k and int(B.mod[e + 1]) // m == g and B.day[e + 1] == B.day[j]:
            e += 1
        O.append(float(o_d[j])); C.append(float(c_d[e])); H.append(float(hi_d[j:e + 1].max())); L_.append(float(lo_d[j:e + 1].min()))
        j = e + 1
    if len(C) < 2:
        return False
    O, C, L_ = np.array(O), np.array(C), np.array(L_)
    gt = len(C) - 1 - (int(B.mod[k]) // m - g0)          # index of the tap's m-minute bar
    if gt < 0 or len(C) - 1 <= gt:
        return False
    lk = gt + int(np.argmin(L_[gt:]))
    if lk < 3:
        return False
    cz = lit._cisd_level(C, O, lk)
    n = len(C) - 1
    return cz is not None and n > lk and C[n] > cz[0] and all(C[q] <= cz[0] for q in range(lk + 1, n))


def _lm_level(c_d, o_d, hi_d, lo_d, lowk, k, kind):
    if kind == "close":
        return float(c_d[k])
    if kind == "mid":
        return 0.5 * (float(o_d[k]) + float(c_d[k]))
    if kind == "cisd1":
        cz = lit._cisd_level(c_d, o_d, lowk)
        return cz[0] if cz else None
    if kind == "fvg":
        return T._e2_limit(c_d, o_d, hi_d, lo_d, lowk, k, "fvg")
    raise ValueError(kind)


# ================================================================================================ one entry
def entry_of(M, B, z, L, tgt_lvl, stop0, P, mode=None):
    """(fill bar, entry price, limit_fill) in direction space, or None. No look-ahead: a decision on bar k's close acts
    from bar k + 1; a resting limit fills only on a trade-through."""
    mode = mode or P["mode"]
    d = z["dir"]
    hi_d, lo_d, c_d, o_d = B.dirs(d)
    t0 = int(M.t[z["entry_i"]])
    k0 = int(np.searchsorted(B.t, t0))
    s_day = int(M.day_of[z["entry_i"]])
    if k0 >= B.n:
        return None
    flat = P["flat_mod"]
    wait_s = P["wait"] * 300
    cis = P.get("cisd1m") or 20
    if B.secs == 300:
        cis = max(1, cis // 5)
    tapL = L + P["tol"] * TICK
    thru = P["thru"] * TICK
    tapped = None
    k = k0
    ok = lambda b: b < B.n and B.day[b] == s_day and B.mod[b] < flat and B.mod[b] < 1080
    while k < B.n:
        if not ok(k):
            return None
        if tapped is None and B.t[k] >= t0 + wait_s:
            return None
        if mode == "direct":
            if lo_d[k] <= L - thru or (thru == 0 and lo_d[k] <= L):
                return k, min(L, float(o_d[k])), True       # (a bar through the stop too: filled, then stopped in the walk)
            if lo_d[k] <= stop0:
                return None
            if hi_d[k] >= tgt_lvl:
                return None
            k += 1
            continue
        if lo_d[k] <= stop0:
            return None
        if tapped is None and lo_d[k] <= tapL:
            tapped = k
        elif tapped is None and hi_d[k] >= tgt_lvl:
            return None
        if tapped is not None:
            if k - tapped > cis:
                return None
            lowk = tapped + int(np.argmin(lo_d[tapped:k + 1]))
            trig = False
            if mode in ("cisd1m", "close") and P["ctf"] > 1 and B.secs == 60:
                trig = _cisd_agg(B, hi_d, lo_d, c_d, o_d, tapped, k, P["ctf"])
            elif mode in ("cisd1m", "close"):
                cz = lit._cisd_level(c_d, o_d, lowk)
                trig = cz is not None and k > lowk and c_d[k] > cz[0]
            elif mode == "bos1m":
                trig = k > lowk and c_d[k] > _bos_level(hi_d, tapped, lowk)
            elif mode == "reclaim":
                trig = float(lo_d[tapped:k + 1].min()) < L and c_d[k] > L and k >= lowk
            else:
                raise ValueError(mode)
            if trig:
                if not ok(k + 1):
                    return None
                if mode == "close":
                    return k + 1, float(c_d[k]) + SLIP, False
                if P["lm"] is None:
                    return k + 1, float(o_d[k + 1]) + SLIP, False
                kind, n = P["lm"]
                X = _lm_level(c_d, o_d, hi_d, lo_d, lowk, k, kind)
                if X is None or X <= stop0:
                    return k + 1, float(o_d[k + 1]) + SLIP, False
                X = min(X, float(c_d[k]))
                for b in range(k + 1, k + 1 + n):
                    if not ok(b):
                        return None
                    if lo_d[b] <= X - TICK:
                        return b, min(X, float(o_d[b])), True
                    if hi_d[b] >= tgt_lvl:
                        return None
                b = k + 1 + n
                if not ok(b):
                    return None
                return b, float(o_d[b]) + SLIP, False
        k += 1
    return None


def walk(M, B, z, fill, entry, limit_fill, tgt_lvl, fb, stop0, P):
    """The live management from the fill (lit.simulate_x research mode), at 1 micro."""
    d = z["dir"]
    hi_d, lo_d, c_d, o_d = B.dirs(d)
    s_day = int(M.day_of[z["entry_i"]])
    flat = P["flat_mod"]
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
    cur, be_done, mfe, mae, worst = stop, False, 0.0, 0.0, 0.0
    k = fill
    exit_px = kind = None
    while k < B.n:
        if B.day[k] != s_day or B.mod[k] >= 1080:
            k -= 1; exit_px, kind = float(c_d[k]) - SLIP, "EOD"; break
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
        if B.mod[k] >= flat:
            exit_px, kind = float(c_d[k]) - SLIP, "EOD"; break
        k += 1
    if exit_px is None:
        return None
    xi5 = int(np.searchsorted(M.t, B.t[k], side="right") - 1)
    return {"day": z["day"], "entry_t": int(B.t[fill]), "exit_t": int(B.t[k]) + B.secs, "exit_i": xi5, "dir": d,
            "risk_pts": round(risk, 2), "exit": kind, "trigger": "LIT-" + ("1m" if B.secs == 60 else "5m"),
            "mfe": round(mfe, 3), "mae": round(min(mae, 1.0 + SLIP / risk), 3), "bars_held": int(k - fill + 1), "regime": "",
            "half": False, "legs": [(1.0, exit_px - entry)], "w1": worst, "w2": 0.0, "part": False,
            "entry_px": round(entry * d, 2), "stop_px": round(stop * d, 2), "target_px": round(tg * d, 2),
            "tgt": round(tg - entry, 2), "limit_fill": limit_fill, "swept": z["swept"], "tf": B.secs // 60, "i": z["i"],
            "ext_i": z["ext_i"]}


def esim(M, B, z, ep_live, tgt_lvl, fb, stop0, P):
    L = zone_level(M, z, P, ep_live, stop0)
    if P["mode"] == "two":
        a = entry_of(M, B, z, L, tgt_lvl, stop0, P, mode="direct")
        b = entry_of(M, B, z, L, tgt_lvl, stop0, P, mode="cisd1m")
        ta = walk(M, B, z, *a, tgt_lvl, fb, stop0, P) if a else None
        tb = walk(M, B, z, *b, tgt_lvl, fb, stop0, P) if b else None
        if ta is None and tb is None:
            return None
        w = P["two_w"]
        legs = [(w, ta), (1 - w, tb)]
        got = [(f, t) for f, t in legs if t is not None]
        first = min((t for _, t in got), key=lambda t: t["entry_t"])
        last = max((t for _, t in got), key=lambda t: t["exit_t"])
        fsum = sum(f for f, _ in got)
        ent = sum(f * float(t["entry_px"]) * z["dir"] for f, t in got) / fsum
        x = dict(first)
        # one unit = the planned position; a missing leg trades nothing (its commission share is given back)
        pts = sum(f * t["legs"][0][1] for f, t in got) + (1 - fsum) * COMM / PV
        x.update(legs=[(1.0, pts)], w1=sum(f * t["w1"] for f, t in got), exit=last["exit"], exit_t=last["exit_t"],
                 exit_i=last["exit_i"], risk_pts=round(ent - stop0, 2), tgt=round(tgt_lvl - ent, 2),
                 entry_px=round(ent * z["dir"], 2), legs_filled=len(got))
        return x
    e = entry_of(M, B, z, L, tgt_lvl, stop0, P)
    if e is None:
        return None
    fill, entry, lf = e
    if P["runaway"] is not None and entry - L > P["runaway"] * (L - stop0):
        return None
    return walk(M, B, z, fill, entry, lf, tgt_lvl, fb, stop0, P)


# ================================================================================================ candidate walk
_MB = {}


def mb(P):
    key = (P["ref"], tuple(P["extra_boxes"]))
    if key not in _MB:
        M, C = F.market(P["ref"], P["extra_boxes"])
        _MB[key] = (M, C, F.bars(M, "5m"), F.bars(M, "1m"))
    return _MB[key]


def plans(P, sessions=S26):
    """Every setup that passes the live filters (planned limit, stop, target level), in time order."""
    names = set(P["sweep_names"]) if P.get("sweep_names") else None
    sset = set(sessions)
    M, C, B5, B1 = mb(P)
    out = []
    for z in C:
        if z["day"] not in sset or not lit.setup_ok(z, P, names):
            continue
        if P.get("monday") and lit.monday_block(M, z):
            continue
        ep = min(float(z["ref_d"]), z["trig_c"])
        stop0 = z["ext_d"] - P["stop_buf"]
        risk = ep - stop0
        if not (P["min_stop"] <= risk <= P["max_stop"]):
            continue
        sh = z["entry_d"] - ep
        TT = {c: [x + sh for x in v] for c, v in lit.targets_x(M, z, P).items()}
        best = None
        for c in P["classes"]:
            for dist in TT.get(c, []):
                if dist >= P["min_rr"] * risk:
                    if best is None or dist < best:
                        best = dist
                    break
        fb = False
        if best is None:
            if not P["fallback_rr"]:
                continue
            tp, fb = P["fallback_rr"] * risk, True
        else:
            tp = min(best, P["max_rr"] * risk) if P["max_rr"] else best
        use1 = B1 is not None and int(M.day_of[z["entry_i"]]) in B1.full
        out.append((z, ep, ep + tp, fb, stop0, B1 if use1 else B5))
    return out


_PL = {}


def plans_c(P):
    key = json.dumps({k: P[k] for k in ("ref", "extra_boxes", "window", "sweep_names", "disp", "depth", "idm_a", "monday",
                                        "stop_buf", "min_stop", "max_stop", "classes", "vix_k", "min_rr", "max_rr", "fallback_rr")},
                     sort_keys=True, default=str)
    if key not in _PL:
        _PL[key] = plans(P)
    return _PL[key]


def path(X=None):
    """The account path: one trade a day, one at a time (lit._run_core research mode), unit size, weekly-stop marks."""
    P = P_of(X)
    M = mb(P)[0]
    out, busy, per_day = [], -1, collections.Counter()
    for z, ep, tg, fb, stop0, B in plans_c(P):
        if z["entry_i"] <= busy or per_day[z["day"]] >= P["max_per_day"]:
            continue
        t = esim(M, B, z, ep, tg, fb, stop0, P)
        if t is None:
            continue
        busy = t["exit_i"]; per_day[z["day"]] += 1
        out.append(t)
    T.wk_marks(out)
    return out


def per_candidate(X=None):
    """Every filtered setup alone: {cand key: trade or None}."""
    P = P_of(X)
    M = mb(P)[0]
    return {(z["day"], z["entry_t"], z["dir"]): esim(M, B, z, ep, tg, fb, stop0, P) for z, ep, tg, fb, stop0, B in plans_c(P)}


def u_pnl(t):
    if t is None:
        return 0.0
    q = max(1, int(U_BUDGET / (t["risk_pts"] * PV)))
    return t["legs"][0][1] * PV * q - COMM * q


# ================================================================================================ scoring
def _wfmt(U):
    return [{"day": t["day"], "entry_t": t["entry_t"], "exit_t": t["exit_t"], "dir": t["dir"], "risk": t["risk_pts"],
             "tgt": t["tgt"], "pts": round(float(t["legs"][0][1]), 4), "w1": round(float(t["w1"]), 4), "exit": t["exit"],
             "wk_m": t.get("wk_m", 1.0), "tf": t["tf"]} for t in U]


def two_week(U, key, mc=True):
    """MFFU 50K pass / fail within 10 sessions under the live two_week sizing (tools/lit_2wk.run_eval)."""
    by = collections.defaultdict(list)
    for t in sorted(_wfmt(U), key=lambda t: t["entry_t"]):
        by[t["day"]].append(t)
    W._D[key] = {"sess": S26, "by": [by.get(s, []) for s in S26], "trades": _wfmt(U), "dow": None}
    o = {}
    for s in ("H1", "H2", "2026"):
        o[s] = W.exact(TW, s, key)
    if mc:
        for s in ("H1", "H2"):
            o["mc_" + s] = W.mc(TW, s, key)
    Tb, b = W.b2b(TW, "2026", key)
    o["b2b"] = b
    o["b2b_net"] = {s: round(sum(t["pnl"] for t in Tb if W.SPAN[s][0] <= t["day"] <= W.SPAN[s][1])) for s in ("H1", "H2", "2026")}
    W._D.pop(key, None)
    return o


def score(X=None, mc=True, key="ep"):
    U = path(X)
    lr = T.sized(U, ("lit", 800, 20.0))
    o = {s: T.stats(lr, s) for s in ("H1", "H2", "2026")}
    o["tw"] = two_week(U, key, mc)
    C = per_candidate(X)
    o["cand"] = C
    return o, U


def cand_table(C, C0):
    """Report ch.5: per original candidate, a miss = $0. H1 / H2 / 2026."""
    out = {}
    for s, (a, z) in (("H1", W.SPAN["H1"]), ("H2", W.SPAN["H2"]), ("2026", W.SPAN["2026"])):
        ks = [k for k in C0 if a <= k[0] <= z]
        n = len(ks) or 1
        p = np.array([u_pnl(C.get(k)) for k in ks]); p0 = np.array([u_pnl(C0.get(k)) for k in ks])
        fills = sum(C.get(k) is not None for k in ks)
        both = [k for k in ks if C.get(k) is not None and C0.get(k) is not None]
        only0 = [k for k in ks if C.get(k) is None and C0.get(k) is not None]
        only1 = [k for k in ks if C.get(k) is not None and C0.get(k) is None]
        wins = [u_pnl(C[k]) for k in ks if C.get(k) is not None]
        out[s] = {"cands": len(ks), "fills": fills, "fill_pct": round(100 * fills / n, 1), "net": round(float(p.sum())),
                  "per_cand": round(float(p.mean()), 1) if len(ks) else 0, "diff_per_cand": round(float((p - p0).mean()), 1) if len(ks) else 0,
                  "win_pct": round(100 * sum(w > 0 for w in wins) / max(1, len(wins)), 1),
                  "shared": len(both), "shared_diff": round(sum(u_pnl(C[k]) - u_pnl(C0[k]) for k in both)),
                  "missed": len(only0), "missed_base_net": round(sum(u_pnl(C0[k]) for k in only0)),
                  "extra": len(only1), "extra_net": round(sum(u_pnl(C[k]) for k in only1)),
                  "boot_lo": None}
        if len(ks) > 5:                       # 90% bootstrap band of the paired difference per candidate
            dd = p - p0
            rng = np.random.default_rng(11)
            bs = [dd[rng.integers(0, len(dd), len(dd))].mean() for _ in range(2000)]
            out[s]["boot_lo"], out[s]["boot_hi"] = round(float(np.percentile(bs, 5)), 1), round(float(np.percentile(bs, 95)), 1)
    return out


def line(nm, o, ct=None):
    f = lambda s: (f"n {o[s]['n']} {o[s]['tpw']}/wk win {o[s]['win']} PF {o[s]['pf']} net {o[s]['net']:+,} "
                   f"(${o[s]['per_month']:,}/mo) DD {o[s]['dd']:,}" if o[s].get("n") else "n 0")
    tw = o["tw"]
    g = lambda s: f"{tw[s]['p10']}/{tw[s]['f10']}"
    m = lambda s: f"{tw['mc_' + s]['p10']}/{tw['mc_' + s]['f10']}" if "mc_" + s in tw else "-"
    c = (f" | cand H1 fill {ct['H1']['fill_pct']}% {ct['H1']['per_cand']:+.0f}/c d{ct['H1']['diff_per_cand']:+.0f} "
         f"H2 fill {ct['H2']['fill_pct']}% {ct['H2']['per_cand']:+.0f}/c d{ct['H2']['diff_per_cand']:+.0f}") if ct else ""
    return (f"{nm:34s} H1[{f('H1')} 2w {g('H1')} mc {m('H1')}] H2[{f('H2')} 2w {g('H2')} mc {m('H2')}]{c}")


# ================================================================================================ check
def check():
    U = path()
    U0 = T.unit()
    U0 = [t for t in U0 if t["day"] >= "2026"]
    ka = [(t["day"], t["entry_t"], round(t["legs"][0][1], 4), t["exit"], t["risk_pts"]) for t in U0]
    kb = [(t["day"], t["entry_t"], round(t["legs"][0][1], 4), t["exit"], t["risk_pts"]) for t in U]
    bad = [(x, y) for x, y in zip(ka, kb) if x != y]
    lr = T.sized(U, ("lit", 800, 20.0))
    print(f"lit_tightstop 2026 {len(ka)} | this {len(kb)} | mismatches {len(bad) + abs(len(ka) - len(kb))} | LIT-rule net "
          f"{sum(t['pnl'] for t in lr):+,.0f} (run lit_live 2026 +41,734)")
    for x in bad[:3]:
        print("diff", x)
    tw = two_week(U, "chk", mc=True)
    W.data("live")
    ref = {s: W.exact(TW, s, "live") for s in ("H1", "H2")}
    for s in ("H1", "H2"):
        print(s, "two_week p10/f10 this", tw[s]["p10"], tw[s]["f10"], "| lit_2wk cache", ref[s]["p10"], ref[s]["f10"],
              "| mc", tw["mc_" + s]["p10"], tw["mc_" + s]["f10"])
    return not bad and len(ka) == len(kb)


# ================================================================================================ the grid
def variants():
    V = collections.OrderedDict()
    V["live: tap -> 1m CISD -> next open"] = {}
    # A. the report's three branches
    V["A1 direct limit at the CISD level (1-tick trade-through)"] = {"mode": "direct"}
    V["A1 direct limit, touch fill"] = {"mode": "direct", "thru": 0}
    V["A1 direct limit, 2-tick trade-through"] = {"mode": "direct", "thru": 2}
    V["A2 confirmation: 1m BOS"] = {"mode": "bos1m"}
    V["A2 confirmation: 1m close back above the zone"] = {"mode": "reclaim"}
    V["A2 confirmation: CISD candle close (vs next open)"] = {"mode": "close"}
    V["A2 confirmation: 1m CISD within 10 bars"] = {"cisd1m": 10}
    V["A2 confirmation: 1m CISD within 30 bars"] = {"cisd1m": 30}
    V["A2 confirmation: 1m CISD within 45 bars"] = {"cisd1m": 45}
    V["A3 refined: limit at the CISD close 1 bar, else market"] = {"lm": ("close", 1)}
    V["A3 refined: limit at the CISD close 2 bars, else market"] = {"lm": ("close", 2)}
    V["A3 refined: limit at the CISD close 3 bars, else market"] = {"lm": ("close", 3)}
    V["A3 refined: limit at the CISD close 5 bars, else market"] = {"lm": ("close", 5)}
    V["A3 refined: limit at the CISD body 50% 2 bars, else market"] = {"lm": ("mid", 2)}
    V["A3 refined: limit at the CISD body 50% 5 bars, else market"] = {"lm": ("mid", 5)}
    V["A3 refined: limit at the 1m CISD level 3 bars, else market"] = {"lm": ("cisd1", 3)}
    V["A3 refined: limit at the 1m CISD level 5 bars, else market"] = {"lm": ("cisd1", 5)}
    V["A3 refined: limit at the 1m FVG 3 bars, else market"] = {"lm": ("fvg", 3)}
    V["A3 refined: limit at the 1m FVG 5 bars, else market"] = {"lm": ("fvg", 5)}
    # B. where the zone is
    V["B zone: 50% of the 5m displacement leg"] = {"zone": "disp50"}
    V["B zone: the inducement level"] = {"zone": "idm"}
    V["B zone: the swept level"] = {"zone": "swept"}
    V["B zone: halfway CISD level - trigger close"] = {"zone": "mid"}
    V["B direct limit at 50% of the leg"] = {"mode": "direct", "zone": "disp50"}
    V["B direct limit at the inducement level"] = {"mode": "direct", "zone": "idm"}
    V["B direct limit at the swept level"] = {"mode": "direct", "zone": "swept"}
    # C. tolerance and waiting
    for tl in (2, 4, 8, 16):
        V[f"C tap tolerance {tl} ticks"] = {"tol": tl}
    for w in (3, 9, 12):
        V[f"C zone valid {w * 5} min"] = {"wait": w}
    # D. patience (skip-if-ran-away), signal close, two-step
    for x in (0.25, 0.5, 0.75):
        V[f"D skip if the fill is > {x}R above the zone"] = {"runaway": x}
    V["D two-step: half limit at the zone, half on the 1m CISD"] = {"mode": "two"}
    V["D two-step: 1/3 limit, 2/3 on the 1m CISD"] = {"mode": "two", "two_w": 1 / 3}
    for m in (2, 3, 5):
        V[f"E confirmation: {m}m CISD (instead of 1m), next 1m open"] = {"ctf": m}
    V["E 3m CISD within 30 1m bars"] = {"ctf": 3, "cisd1m": 30}
    return V


def _jsonable(o):
    o = dict(o)
    o.pop("cand", None)
    return o


def grid(V=None, mc=True, only=None):
    V = V or variants()
    if only:
        V = collections.OrderedDict((k, v) for k, v in V.items() if k.startswith(tuple(only)) or k.startswith("live"))
    res = json.load(open(OUT)) if os.path.exists(OUT) else {}
    o0, _ = score({}, mc=mc, key="base")
    C0 = o0["cand"]
    for nm, X in V.items():
        o, U = score(X, mc=mc, key="v")
        ct = cand_table(o["cand"], C0)
        res[nm] = {"X": X, **_jsonable(o), "cand": ct}
        print(line(nm, o, ct), flush=True)
        json.dump(res, open(OUT, "w"), indent=1, default=str)
    return res


SAVES = [   # run id, variant name, status, why
    ("lit_ep_live", "live: tap -> 1m CISD -> next open", "info", "Reference: today's LIT entry (== run lit_live trade for trade)."),
    ("lit_ep_direct", "A1 direct limit at the CISD level (1-tick trade-through)", "rejected",
     "Direct-zone entry: fills 3/4 of the setups instead of 1/2; the extra fills are the setups the 1m CISD filters out and lose $28.9k in H1."),
    ("lit_ep_bos1m", "A2 confirmation: 1m BOS", "rejected", "A 1m BOS instead of the 1m CISD: later, fewer fills, worse in both halves."),
    ("lit_ep_reclaim", "A2 confirmation: 1m close back above the zone", "rejected", "First 1m close back above the zone: worse in both halves."),
    ("lit_ep_close", "A2 confirmation: CISD candle close (vs next open)", "info", "Fill at the CISD candle close instead of the next open: the same within $0.4k a half (noise)."),
    ("lit_ep_lm_close1", "A3 refined: limit at the CISD close 1 bar, else market", "rejected",
     "Closest miss: H1 +$1.3k, H2 -$0.2k and 2-week H2 49.3% vs 50.7%. Not better in both halves."),
    ("lit_ep_lm_fvg3", "A3 refined: limit at the 1m FVG 3 bars, else market", "rejected", "H1 +$1.3k, H2 -$2.0k: H1 only."),
    ("lit_ep_zone_mid", "B zone: halfway CISD level - trigger close", "rejected", "Shallower zone: H1 -$5.9k, H2 +$0.2k."),
    ("lit_ep_tol16", "C tap tolerance 16 ticks", "rejected", "4-pt tap tolerance: H1 -$8.2k, H2 +$1.6k: H2 only."),
    ("lit_ep_two_step", "D two-step: half limit at the zone, half on the 1m CISD", "rejected", "Two-step entry: worse in both halves (already rejected as two_stage in lit-experiments)."),
    ("lit_ep_runaway05", "D skip if the fill is > 0.5R above the zone", "rejected", "Patience: H1 +$2.8k, H2 -$4.2k (as in lit-1m-management)."),
    ("lit_ep_cisd3m", "E confirmation: 3m CISD (instead of 1m), next 1m open", "rejected", "An M3 confirmation instead of M1: far worse in both halves."),
]


def save():
    from tools import runlib as rl
    res = json.load(open(OUT))
    V = variants()
    for rid, nm, status, why in SAVES:
        o = res[nm]
        X = V[nm]
        U = path(X)
        lr = T.sized(U, ("lit", 800, 20.0))
        tw = o["tw"]; ct = o["cand"]
        h = lambda s: (f"{s}: {o[s]['n']} trades {o[s]['tpw']}/wk, win {o[s]['win']}%, PF {o[s]['pf']}, net {o[s]['net']:+,} "
                       f"(${o[s]['per_month']:,}/mo), DD {o[s]['dd']:,}; two-week eval sizing: 2-week pass/fail {tw[s]['p10']}/{tw[s]['f10']}"
                       + (f" (Monte Carlo {tw['mc_' + s]['p10']}/{tw['mc_' + s]['f10']})" if 'mc_' + s in tw else "")
                       + (f"; per candidate (U=$1,000): {ct[s]['cands']} setups, fill {ct[s]['fill_pct']}%, ${ct[s]['per_cand']:+,.0f} a "
                          f"setup ({ct[s]['diff_per_cand']:+,.0f} vs live)" if s in ct else ""))
        verdict = f"{why} " + "; ".join(h(s) for s in ("H1", "H2", "2026")) + "."
        rl.save(rid, nm, "other", "Owner order 2026-10-18: entries on the dot; report ch.5/13 exp. 1: direct vs confirmation vs "
                "refined limit per original candidate.", params={"lit": {k: v for k, v in LIVE.items()}, "entry": {**EDEF, **X}},
                sizing={"rule": "LIT rule $800 up to 20 pts + weekly stop (trades); eval numbers with lit_sizing two_week"},
                trades=lr, scored=rl.score(lr, S26), status=status, verdict=verdict,
                notes="tools/lit_entry_precision.py; research/lit/entry_precision.json. Trades = LIT-rule size on the 2026 path; "
                      "the 2-week eval numbers use the live two_week sizing (tools/lit_2wk.run_eval, fresh eval each session).",
                writeup="lit-entry-precision", tags=["lit", "lit_entry_precision"])
        print("saved", rid)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "check":
        print("OK" if check() else "MISMATCH")
    elif cmd == "grid":
        grid(only=sys.argv[2:] or None)
    elif cmd == "save":
        save()
    else:
        raise SystemExit(__doc__)
