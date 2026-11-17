"""LIT smart entries (2026-11-17, owner: "smart entries"). RESEARCH ONLY: engine/ and live_model*.json untouched.

Same setups as live (engine/lit.py candidates + the live filters, one trade a day, Monday rule, weekly stop); only HOW the
entry is taken after the 5m CISD-level tap changes. engine/lit.simulate_x is wrapped in this process only: the wrapper
decides the fill (bar + price) and hands it to the engine's own executor through the research hook cand["mkt"], so the
stop (1 tick beyond the sweep extreme), the target (VIX band, >= 1.5R from the real fill, banked at 8R), breakeven + 1.25,
the 15-minute check and the 15:55 flat are the live ones. A setup that does not fill leaves the day free (engine queue).

Fills (conservative): a market entry = the next bar's open + 1 tick. A limit fills only when price trades THROUGH it by
1 tick, at min(limit, bar open); if that bar also breaks the stop it is a stop-out; otherwise the trade is managed from the
NEXT bar (the fill bar gets no target / breakeven credit). Decisions are made on a bar's close and act from the next bar.

Families (new; the rejected ones of research/writeups/lit-entry-precision.md, lit-1m-management.md, lit-untested-entries.md,
lit-tight-stops-size.md, 2026-11-04_lit_ideas_night.md, lit-edge-2026-10-30.md, 2026-11-15-lit-deep.md are NOT re-run):
  A  conditional pullback limit: only when the 1m CISD candle ran far (close > x planned R above the 5m CISD level, or a
     candle range > x planned R; x = the Jan-Jun median / top third of live trades), a limit at that candle's 50% or at the
     1m CISD level for n minutes, then market (not filled in time). Otherwise the live next-open entry.
  B  confirmation combos on the 1m CISD: OR / AND a 1m break of structure, AND a close back above the 5m CISD level, AND a
     close back inside the swept level (nearest / all), a run of 2+ down candles, a strong close (top third / above the
     previous high).
  D  timing around the 15-minute check: (D1) wait N minutes after the would-be fill and enter only if the trade is working
     (close >= the would-be entry, or it passes the 15-minute check), size from the real stop; (D2) staged: half at the
     live entry, the other half at minute N only if working, the two halves together inside the live trade's $ risk.
Scoring = tools/lit_edge.evaluate (LIT size rule; the live eval path two_week room_f 0.4 kept to session 80; funded 50K
Monte Carlo) with the D2 legs scored by their own copy of each path.

  python -X utf8 tools/lit_smart_entries.py check     # base wrapper == live (631 trades, every entry / exit / $)
  python -X utf8 tools/lit_smart_entries.py grid [prefix..]   # -> research/lit/smart_entries.json (SE_OUT=<file>)
  python -X utf8 tools/lit_smart_entries.py merge     # smart_entries*.json -> smart_entries.json
  python -X utf8 tools/lit_smart_entries.py report
"""
from __future__ import annotations

import collections
import glob
import json
import math
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import lit  # noqa: E402
from engine import sizing as SZ  # noqa: E402
from tools import lit_edge as E  # noqa: E402
from tools import lit_adv_manage as A  # noqa: E402
from tools import lit_final as F  # noqa: E402
from tools import lit_rev_exit as R  # noqa: E402
from tools import uprisk as UP  # noqa: E402

ROOM, UNTIL = 0.4, 80
A.CFG = {**A.CFG, "two_week": {**A.CFG["two_week"], "room_f": ROOM}, "two_week_until": UNTIL}
OUT = os.environ.get("SE_OUT") or os.path.join(ROOT, "research", "lit", "smart_entries.json")
LIVE = E.LIVE
PV, COMM, SLIP, TICK = lit.PV, lit.COMM, lit.SLIP, lit.TICK
H1 = ("2026-01-01", "2026-06-30")
ORIG = lit.simulate_x
VAR = None             # the variant the wrapper applies (None = the engine untouched)
SIDE = {}              # entry_t -> facts of the entry (signal facts; D2 add)


# ================================================================================================ entry walk
def _cisd(c_d, o_d, ee, back=3):
    """engine/lit._cisd_level + the last down-close bar of the run: (level, first bar, last bar) or None."""
    j = ee
    while j > ee - back and not (c_d[j] < o_d[j]):
        j -= 1
    if not (c_d[j] < o_d[j]):
        return None
    st = j
    while st - 1 >= 0 and c_d[st - 1] < o_d[st - 1] and st > ee - 30:
        st -= 1
    return float(o_d[st]), st, j


def _bos_level(hi_d, tapped, lowk):
    """The last 1m swing high (3-bar fractal) before the post-tap low; none -> the highest high from the tap to the low."""
    for j in range(lowk - 1, max(tapped - 30, 1) - 1, -1):
        if j + 1 <= lowk and hi_d[j] > hi_d[j - 1] and hi_d[j] > hi_d[j + 1]:
            return float(hi_d[j])
    return float(hi_d[tapped:lowk + 1].max())


def _confirm(V, k, lowk, tapped, B, d, cand, entry_px):
    hi_d, lo_d, c_d, o_d = B.dirs(d)
    cz = _cisd(c_d, o_d, lowk)
    cis = cz is not None and k > lowk and c_d[k] > cz[0]
    conf = V.get("conf", "cisd")
    if conf == "cisd":
        return cis, cz
    if conf in ("or_bos", "and_bos"):
        bos = k > lowk and c_d[k] > _bos_level(hi_d, tapped, lowk)
        return (cis or bos) if conf == "or_bos" else (cis and bos), cz
    if not cis:
        return False, cz
    if conf == "and_zone":
        return c_d[k] > entry_px, cz
    if conf in ("and_swept_near", "and_swept_all"):
        lv = [float(v) * d for v in (cand.get("sw") or {}).values()]
        if not lv:
            return True, cz
        return c_d[k] > (min(lv) if conf == "and_swept_near" else max(lv)), cz
    if conf == "run2":
        return cz[2] - cz[1] + 1 >= 2, cz
    if conf == "strong":
        return c_d[k] >= lo_d[k] + (2.0 / 3.0) * (hi_d[k] - lo_d[k]), cz
    if conf == "engulf":
        return c_d[k] > hi_d[k - 1], cz
    raise ValueError(conf)


def decide(M, B, cand, entry_px, tgt, stop, P, V):
    """The live tap -> 1m CISD walk (engine/lit.simulate_x, cisd1m path) with the variant's confirmation, then the
    variant's entry. Returns (fill bar, direction-space entry price, facts) or None (no trade; the day stays free)."""
    d = cand["dir"]
    hi_d, lo_d, c_d, o_d = B.dirs(d)
    t0 = int(M.t[cand["entry_i"]])
    k0 = int(np.searchsorted(B.t, t0))
    s_day = int(M.day_of[cand["entry_i"]])
    if k0 >= B.n:
        return None
    flat, ev = P["flat_mod"], bool(P.get("all_hours"))
    wait_s = P["wait"] * 300
    cis = P["cisd1m"]
    if B.secs == 300:
        cis = max(1, cis // 5)
    bpm = B.secs // 60
    tgt_cancel = entry_px + tgt[1] if tgt[0] == "pts" else tgt[1]
    R0 = entry_px - stop
    late = lambda j: B.day[j] != s_day or lit._late(B.mod[j], flat, ev)
    tapped, sig, k = None, None, k0
    while k < B.n:
        if late(k):
            break
        if tapped is None and B.t[k] >= t0 + wait_s:
            break
        if lo_d[k] <= stop:
            break
        if tapped is None and lo_d[k] <= entry_px:
            tapped = k
        if tapped is None and hi_d[k] >= tgt_cancel:
            break
        if tapped is not None:
            if k - tapped > cis:
                break
            lowk = tapped + int(np.argmin(lo_d[tapped:k + 1]))
            ok, cz = _confirm(V, k, lowk, tapped, B, d, cand, entry_px)
            if ok and k + 1 < B.n and B.day[k + 1] == s_day:
                sig = (k, lowk, cz)
                break
        k += 1
    if sig is None:
        return None
    k, lowk, cz = sig
    f = k + 1
    facts = {"run_r": (c_d[k] - entry_px) / R0, "rng_r": (hi_d[k] - lo_d[k]) / R0, "tf": bpm}
    ent = V.get("ent", "next")
    if ent == "next":
        return f, float(o_d[f]) + SLIP, facts
    if ent == "climit":
        x = facts[V["cond"]]
        if x <= V["thr"]:
            return f, float(o_d[f]) + SLIP, facts
        if V["lvl"] == "mid":
            L = 0.5 * (hi_d[k] + lo_d[k])
        elif V["lvl"] == "cz1":
            L = cz[0] if cz is not None else 0.5 * (hi_d[k] + lo_d[k])
        else:
            raise ValueError(V["lvl"])
        L = math.floor(L / TICK + 1e-9) * TICK
        if L >= c_d[k] - TICK or L <= stop:
            return f, float(o_d[f]) + SLIP, facts
        nb = max(1, int(round(V["n"] / bpm)))
        for j in range(f, f + nb):
            if j >= B.n or late(j):
                return None
            if lo_d[j] <= L - TICK:                       # traded THROUGH the limit by 1 tick
                px = min(L, float(o_d[j]))
                facts["limit"] = True
                if lo_d[j] <= stop:
                    return j, px, facts                   # filled and stopped in the same bar
                if j + 1 < B.n and not late(j + 1):
                    return j + 1, px, facts               # managed from the next bar (no fill-bar credit)
                return None
            if hi_d[j] >= tgt_cancel:
                return None
        j = f + nb
        if V.get("fb", "mkt") == "mkt" and j < B.n and not late(j):
            if lo_d[f:j].min() <= stop:
                return None
            facts["limit_to"] = True
            return j, float(o_d[j]) + SLIP, facts
        return None
    if ent in ("wait", "stage"):
        ve = float(o_d[f]) + SLIP
        Rv = ve - stop
        nb = max(1, int(round(V["n"] / bpm)))
        ja = f + nb                                       # the bar whose open takes the (2nd) entry
        if ja >= B.n or any(late(j) for j in range(f, ja + 1)):
            if ent == "wait":
                return None
            facts["noadd"] = True
            return f, ve, facts
        mfe, dead = 0.0, False
        for j in range(f, ja):
            if lo_d[j] <= stop or hi_d[j] >= tgt_cancel:
                dead = True
                break
            mfe = max(mfe, (hi_d[j] - ve) / Rv)
        cl = float(c_d[ja - 1])
        if V["cond"] == "above":
            ok = cl >= ve
        elif V["cond"] == "t15":
            ok = not (mfe < 0.5 and cl < ve - 0.3 * Rv)
        else:
            raise ValueError(V["cond"])
        if ent == "wait":
            if dead or not ok:
                return None
            return ja, float(o_d[ja]) + SLIP, facts
        facts.update(noadd=dead or not ok, add_k=ja, add_px=float(o_d[ja]) + SLIP, w_pre=float(lo_d[f:ja].min()) - ve)
        return f, ve, facts
    raise ValueError(ent)


def sim_v(M, B, cand, entry_px, tgt, stop, P, live=False):
    V = VAR
    if V is None or live or P.get("fills") is not None or cand.get("mkt") or not P.get("cisd1m"):
        return ORIG(M, B, cand, entry_px, tgt, stop, P, live)
    dec = decide(M, B, cand, entry_px, tgt, stop, P, V)
    if dec is None:
        return None
    kf, px, facts = dec
    t = ORIG(M, B, {**cand, "mkt": {"t": int(B.t[kf]), "entry_d": px}}, entry_px, tgt, stop, P)
    if t is None:
        return None
    if V.get("ent") == "stage":
        d = cand["dir"]
        hi_d, lo_d, c_d, o_d = B.dirs(d)
        ja = facts.get("add_k")
        kx = int(np.searchsorted(B.t, int(t["exit_t"]) - B.secs))      # the exit bar
        tg = float(t["target_px"]) * d
        if not facts["noadd"] and (kx < ja or facts["add_px"] >= tg):
            facts["noadd"] = True
        if not facts["noadd"]:
            facts.update(dist=facts["add_px"] - px, rk=facts["add_px"] - stop, w_ph=float(lo_d[ja:kx + 1].min()) - px)
    SIDE[int(t["entry_t"])] = facts
    return t


lit.simulate_x = sim_v


def run(V):
    global VAR
    VAR = V
    SIDE.clear()
    try:
        return F.run(LIVE), dict(SIDE)
    finally:
        VAR = None


# ================================================================================================ D2 (staged) scoring
def stage_pnl(u, q, comm):
    """$ P&L, worst open $ and micros of a staged unit at q (the live micros): q1 = half (>= 1) at the live entry, the add
    at minute N inside what is left of the live trade's $ risk (full stop + 1 tick + commission), 40 micros at most."""
    st = u.get("st")
    if not st:
        g = u["pts"] * PV * q - comm * q
        return g, min(0.0, u["w1"] * PV * q - comm * q, g), q
    q1 = max(1, q // 2)
    q2 = 0
    if not st.get("noadd"):
        budget = q * (u["risk"] + SLIP) * PV + comm * q
        used = q1 * ((u["risk"] + SLIP) * PV + comm)
        per = (st["rk"] + SLIP) * PV + comm
        q2 = max(0, min(int(max(0.0, budget - used) / per), 40 - q1))
    if q2 == 0:
        g = u["pts"] * PV * q1 - comm * q1
        return g, min(0.0, u["w1"] * PV * q1 - comm * q1, g), q1
    pts2 = u["pts"] - st["dist"]
    g = (q1 * u["pts"] + q2 * pts2) * PV - comm * (q1 + q2)
    low = min(q1 * st["w_pre"], q1 * st["w_ph"] + q2 * (st["w_ph"] - st["dist"])) * PV - comm * (q1 + q2)
    return g, min(0.0, low, g), q1 + q2


def stage_lit_size(U):
    W = E.wk_mult(U)
    out = []
    for u in sorted(U, key=lambda u: u["entry_t"]):
        q0 = lit.qty_for(u["risk"])
        wm = W[u["entry_t"]]
        q = q0 if wm >= 1 else max(1, int(q0 * wm + 1e-9))
        pnl, low, tot = stage_pnl(u, q, COMM)
        out.append({**u, "qty": tot, "pnl": round(pnl, 2), "low": round(low, 2), "r": round(pnl / (u["risk"] * PV * q), 3),
                    "risk_pts": u["risk"], "risk_usd": round(u["risk"] * PV * q, 2), "half": wm < 1, "mult": wm,
                    "trigger": "LIT-%dm" % u["tf"], "mae": None, "bars_held": None, "regime": ""})
    return out


def run_eval_stage(seq, by, horizon=20, keep=None, cfg=None):
    """tools/lit_edge.run_eval_m (engine/sizing.lit_qty two_week, $1.90) with the staged legs."""
    cfg = cfg or A.CFG
    tgt, mll, dll, lockv = A.A50["target"], A.A50["mll"], A.A50["dll"], A.A50["lock"]
    bal = peak = 0.0
    floor = -mll
    for kk, si in enumerate(seq[:horizon]):
        cum = 0.0
        for t in by[si]:
            if cum <= -dll:
                break
            st = {"profit": bal, "cum": cum, "room": bal + cum - floor, "session": kk + 1, "n_today": 0}
            m0 = lit.qty_for(t["risk"])
            q = SZ.lit_qty(m0, {"risk_pts": t["risk"], "tgt_pts": t["tgt"], "size_mult": 1.0}, cfg, room=st["room"], state=st,
                           learning=None)["qty"] if m0 else 0
            if q <= 0:
                continue
            pnl, low, tot = stage_pnl(t, q, A.ECOMM)
            if cum + low <= -dll:
                pnl = -dll - cum - SLIP * PV * tot
                low = pnl
            rec = {**{k: t[k] for k in ("day", "entry_t", "exit_t", "dir", "exit", "risk", "tgt")}, "qty": tot, "pnl": round(pnl, 2),
                   "low": round(low, 2), "risk_usd": round(t["risk"] * PV * q, 2)}
            if bal + cum + low <= floor:
                if keep is not None:
                    keep.append(rec)
                return "FAIL", kk + 1
            cum += pnl
            if keep is not None:
                keep.append(rec)
        bal += cum
        if bal <= floor:
            return "FAIL", kk + 1
        peak = max(peak, bal)
        floor = min(max(floor, peak - mll), lockv)
        if bal >= tgt:
            return "PASS", kk + 1
    return "OPEN", min(len(seq), horizon)


class FundedStage(UP.Funded):
    """The live funded account (60% of the room <= $1,500, winner <= $2,000); the staged legs at the live micros."""

    def qty(self, t, st):
        q = super().qty(t, st)
        if q > 0 and t.get("_st"):
            pnl, low, tot = stage_pnl(t["_st"], q, UP.COMM)
            t["pts"] = (pnl + UP.COMM * q) / (PV * q)
            t["w1"] = (low + UP.COMM * q) / (PV * q)
        return q


def stage_funded(U, n=None):
    c = E.ctx()
    n = n or E.N_FUND
    W = E.wk_mult(U)
    by = collections.defaultdict(list)
    for u in sorted(U, key=lambda u: u["entry_t"]):
        x = {"day": u["day"], "risk": u["risk"], "risk_pts": u["risk"], "tgt": u["tgt"], "tgt_pts": u["tgt"], "pts": u["pts"],
             "w1": u["w1"], "size_mult": W[u["entry_t"]]}
        if u.get("st"):
            x["_st"] = u
        by[u["day"]].append(x)
    BY = [by.get(d, []) for d in c["S_up"]]
    keep = UP.Funded
    UP.Funded = lambda plan, cfg_, ask=None: FundedStage(plan, cfg_, ask)
    try:
        o = {}
        for sp in ("H1", "H2", "REF"):
            if (sp, n) not in E._FP:
                E._FP[(sp, n)] = UP.mc_paths(c["S_up"], sp, n)
            r = UP.funded_mc(BY, E._FP[(sp, n)], "builder50k", E.FUND_LIVE)
            o[sp] = {k: r[k] for k in ("per_month", "paid_6m", "loss_6m", "first_med", "any_pay", "payouts", "max_risk", "trades_6m")}
    finally:
        UP.Funded = keep
    return o


def evaluate_stage(T, side):
    U = E.trades(T=T)
    for u in U:
        st = side.get(u["entry_t"])
        if st and "noadd" in st:
            u["st"] = st
    L = stage_lit_size(U)
    keep = A.run_eval
    A.run_eval = run_eval_stage
    try:
        ev = E.eval_path(U)
    finally:
        A.run_eval = keep
    return {"X": {}, "lit": E.lit_stats(L), "eval": ev, "fund": stage_funded(U), "floored": 0}, U, L


# ================================================================================================ variants
def thresholds():
    """Cut points for family A from the live Jan-Jun 2026 trades (median and top third of the run and the candle range)."""
    T, side = run({"conf": "cisd", "ent": "next"})
    out = {}
    for key in ("run_r", "rng_r"):
        v = np.array([side[int(t["entry_t"])][key] for t in T if H1[0] <= t["day"] <= H1[1] and t["tf"] == 1], float)
        out[key] = {"q50": round(float(np.quantile(v, 0.5)), 3), "q67": round(float(np.quantile(v, 2 / 3)), 3)}
    return out


def variants():
    th = thresholds()
    V = collections.OrderedDict()
    nm = {"run_r": "ran", "rng_r": "big"}
    for cond in ("run_r", "rng_r"):
        for q in ("q50", "q67"):
            for lvl in ("mid", "cz1"):
                for n in (3, 5):
                    x = th[cond][q]
                    V[f"A_{nm[cond]}{q[1:]}_{lvl}_{n}m"] = (
                        {"conf": "cisd", "ent": "climit", "cond": cond, "thr": x, "lvl": lvl, "n": n, "fb": "mkt"},
                        f"when the 1m CISD candle {'closed' if cond == 'run_r' else 'is'} more than {x:.2f}R "
                        f"{'above the 5m CISD level' if cond == 'run_r' else 'tall'} (Jan-Jun {q}): limit at "
                        f"{'its 50%' if lvl == 'mid' else 'the 1m CISD level'} for {n} min, then market")
    for conf, desc in (("or_bos", "1m CISD OR a 1m break of structure, whichever first"),
                       ("and_bos", "1m CISD AND a close above the last 1m swing high"),
                       ("and_zone", "1m CISD AND the close back above the 5m CISD level"),
                       ("and_swept_near", "1m CISD AND the close back inside the swept level (the nearest one)"),
                       ("and_swept_all", "1m CISD AND the close back above every swept level"),
                       ("run2", "1m CISD from a run of 2+ down candles"),
                       ("strong", "1m CISD candle closes in its top third"),
                       ("engulf", "1m CISD candle closes above the previous candle's high")):
        V[f"B_{conf}"] = ({"conf": conf, "ent": "next"}, desc)
    for n, cond in ((5, "above"), (10, "above"), (15, "above"), (15, "t15")):
        V[f"D1_wait{n}_{cond}"] = ({"conf": "cisd", "ent": "wait", "n": n, "cond": cond},
                                   f"wait {n} min after the would-be fill; enter (full size, real stop) only if "
                                   + ("the close is at or above the would-be entry" if cond == "above" else "it passes the 15-minute check"))
    for n, cond in ((5, "above"), (15, "above"), (15, "t15")):
        V[f"D2_stage{n}_{cond}"] = ({"conf": "cisd", "ent": "stage", "n": n, "cond": cond},
                                    f"half at the live entry, the other half at minute {n} only if "
                                    + ("the close is at or above the entry" if cond == "above" else "it passes the 15-minute check")
                                    + " (both halves inside the live $ risk)")
    return V, th


# ================================================================================================ runs
def check():
    T0 = F.run(LIVE)
    T, side = run({"conf": "cisd", "ent": "next"})
    assert len(T) == len(T0), (len(T), len(T0))
    bad = [(a["day"], a["entry_t"], b["entry_t"], a["pnl"], b["pnl"]) for a, b in zip(T0, T)
           if a["entry_t"] != b["entry_t"] or abs(a["pnl"] - b["pnl"]) > 0.01 or a["exit"] != b["exit"]]
    print(f"base wrapper: {len(T)} trades, {len(bad)} differ from live; 2026 {sum(1 for t in T if t['day'] >= '2026')}, "
          f"net {sum(t['pnl'] for t in T):+,.0f} vs {sum(t['pnl'] for t in T0):+,.0f}")
    for b in bad[:10]:
        print("  ", b)
    # the D2 path with no add anywhere == half size; with the stage family off == live: check the scorer on the live trades
    U = E.trades(T=T)
    L0 = E.lit_size(U)
    L1 = stage_lit_size(U)
    assert all(abs(a["pnl"] - b["pnl"]) < 0.01 for a, b in zip(L0, L1)), "stage scorer != live with no stage"
    print("stage scorer with no stage == live LIT size:", round(sum(l["pnl"] for l in L1)))
    return not bad


def grid(prefixes=None):
    t0 = time.time()
    res = json.load(open(OUT)) if os.path.exists(OUT) else {}
    E.ctx()
    base, U0, L0 = E.evaluate({}, fund=True)
    bs = E.short(base)
    V, th = variants()
    res["base"] = bs
    res["_cfg"] = {"room_f": ROOM, "two_week_until": UNTIL, "thresholds": th, "cells": len(V)}
    print(E.line("base", bs), flush=True)
    for nm, (X, desc) in V.items():
        if prefixes and not any(nm.startswith(p) for p in prefixes):
            continue
        t1 = time.time()
        T, side = run(X)
        if X["ent"] == "stage":
            o, U, L = evaluate_stage(T, side)
        else:
            o, U, L = E.evaluate(T=T, fund=True)
        n26 = {sp: sum(1 for t in T if E.SPANS[sp][0] <= t["day"] <= E.SPANS[sp][1]) for sp in E.SPANS}
        f = [side.get(int(t["entry_t"]), {}) for t in T if t["day"] >= "2026"]
        info = {"desc": desc, "X": X, "n_trades": n26,
                "limit_fills": sum(1 for x in f if x.get("limit")), "limit_timeouts": sum(1 for x in f if x.get("limit_to")),
                "adds": sum(1 for x in f if "noadd" in x and not x["noadd"]), "no_adds": sum(1 for x in f if x.get("noadd"))}
        o["chg"] = E.changed(L, L0)
        o["info"] = info
        s = E.short(o, bs)
        s["gate"] = E.gate(s)
        res[nm] = s
        print(E.line(nm, s), f"| dLIT {s['d_lit']['H1']:+,}/{s['d_lit']['H2']:+,}/{s['d_lit']['2021-25']:+,} dEV "
              f"{s['d_eval']['H1']:+,}/{s['d_eval']['H2']:+,} fund {s['d_fund']} {'GATE' if s['gate'] else ''} "
              f"({time.time() - t1:.0f}s)", flush=True)
        json.dump(res, open(OUT, "w"), indent=1, default=float)
    print(f"done in {time.time() - t0:.0f}s", flush=True)


def merge():
    res = {}
    for p in sorted(glob.glob(os.path.join(ROOT, "research", "lit", "smart_entries*.json"))):
        res.update(json.load(open(p)))
    json.dump(res, open(OUT, "w"), indent=1, default=float)
    print(len(res), "keys ->", OUT)


def report():
    res = json.load(open(OUT))
    b = res["base"]
    print(E.line("base", b))
    n = 0
    for k, s in res.items():
        if k.startswith("_") or k == "base":
            continue
        n += 1
        L, ev, f = s["lit"], s["eval"], s["fund"]
        print(f"| {k} | {L['H1']['per_month']:,} / {L['H2']['per_month']:,} / {L['2021-25']['per_month']:,} | "
              f"{s['d_lit']['H1']:+,} / {s['d_lit']['H2']:+,} / {s['d_lit']['2021-25']:+,} | {s['d_eval']['H1']:+,} / {s['d_eval']['H2']:+,} | "
              f"{ev['H1']['p10']}/{ev['H1']['f10']} med {ev['H1']['pass_med']}, {ev['H2']['p10']}/{ev['H2']['f10']} med {ev['H2']['pass_med']} | "
              f"{L['H1']['tpw']} / {L['H2']['tpw']} | {L['H1']['pf']} / {L['H2']['pf']} | {L['H1']['dd']:,} / {L['H2']['dd']:,} | "
              f"{f['H1']['per_month'] - b['fund']['H1']['per_month']:+} / {f['H2']['per_month'] - b['fund']['H2']['per_month']:+} | "
              f"{'GATE' if s.get('gate') else 'rejected'} |")
    print(n, "cells")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "grid":
        grid(sys.argv[2:] or None)
    else:
        {"check": check, "merge": merge, "report": report}[cmd]()
