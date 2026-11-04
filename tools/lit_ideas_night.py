"""LIT ideas night (job 26, 2026-11-04): new management, size-tilt and entry-window ideas for the live LIT strategy.
RESEARCH ONLY: engine/ and live_model*.json are untouched; this file builds on tools/lit_edge.py (same live trades =
run lit_live, same executor, same LIT size rule, same live two_week eval path, same funded 50K model).

Judging (owner 2026-10-18): picked on 2026 H1 (Jan-Jun), checked on H2 (Jul-Oct), 2021-25 a reference line only; costs in;
2+ trades a week; eval path = live two_week sizing (p10/f10 = pass/fail within 10 sessions = 2 weeks).

New post-fill options (X), all decided at a bar's close, acting from the next bar (no look-ahead):
  partial {"f": share, "r": R, "lock": R|None}   share f of the micros out at +R (limit, needs 1 tick through), the runner keeps the
                                                  live rules; lock = runner stop to entry + lock x R once the partial fills
  ladder  [[mfe R, lock R], ...]                 stair stop: once the best point reaches mfe R the stop goes to entry + lock R
  tc2     {"at": min, "x": R, "mfe": R}          a second cut check (like the live 15-minute check) at `at` minutes
  tc1     {"at": min, ...}                       the live check at another minute (replaces the 15)
  stale   {"min": m, "r": R}                     m minutes after the fill, still no breakeven and best point < R -> out at the next open
  news    {"lead": min, "mode": "flat"|"be", "r": R}  the next scheduled high-impact release (trade_intel news_next, known at the entry):
                                                  `lead` minutes before it, flat (if best point < R) or the stop to entry + 1.25 (if best >= R)

  python -X utf8 tools/lit_ideas_night.py check     # options off == live trades
  python -X utf8 tools/lit_ideas_night.py grid [fam..]   # -> research/lit/ideas_night_grid.json (+ ideas_night_results.json)
"""
from __future__ import annotations

import collections
import json
import math
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import lit_edge as E  # noqa: E402  (also patches lit_adv_manage.run_eval with the tilt-aware eval)
from tools import lit_final as F  # noqa: E402
from engine import lit  # noqa: E402

OUT = os.environ.get("IDEAS_OUT") or os.path.join(ROOT, "research", "lit", "ideas_night_grid.json")
OUT_S = os.path.join(ROOT, "research", "lit", "ideas_night_results.json")
LIVE, PV, COMM, SLIP, TICK, BE_OFF, SPANS = E.LIVE, E.PV, E.COMM, E.SLIP, E.TICK, E.BE_OFF, E.SPANS
NPLC = int(os.environ.get("IDEAS_NPLC", "150"))


# ================================================================================================ executor (post-fill)
def manage2(X, BX, fill, d, entry, stop, tg, s_day, risk, tg_far=None, be_r=None, tc_x=None):
    """lit_edge.manage (options off == live) + partial / ladder / tc1 / tc2 / stale / news. Returns the 5 values of manage plus
    the legs [(share, pts), (rest, pts)] when a partial filled (else None)."""
    X = X or {}
    c = E.ctx()
    B = BX.B
    hi_d, lo_d, c_d, o_d = B.dirs(d)
    flat = LIVE["flat_mod"]
    on1 = B.secs == 60
    tc = LIVE.get("t_check") if on1 else None
    if tc and tc_x is not None:
        tc = {**tc, "x": tc_x}
    if tc and X.get("tc1"):
        tc = {**tc, **X["tc1"]}
    tc2 = X.get("tc2") if on1 else None
    be_r = LIVE["be_r"] if be_r is None else be_r
    pa, ld, st_, nw = X.get("partial"), X.get("ladder"), X.get("stale"), X.get("news")
    rel = None
    if nw:
        nn = c["intel"].get(int(B.t[fill]), {}).get("news_next")
        if nn is not None and float(nn) < 600:
            rel = float(B.t[fill]) + float(nn) * 60.0 - float(nw.get("lead", 2)) * 60.0
    cur, be_done, mfe, worst = stop, False, 0.0, 0.0
    cut = None
    pdone, ppx, nd = False, None, False
    k = fill
    exit_px = kind = None
    while k < B.n:
        if B.day[k] != s_day or B.mod[k] >= 1080:
            k -= 1; exit_px, kind = float(c_d[k]) - SLIP, "EOD"; break
        if cut is not None:
            exit_px, kind = float(o_d[k]) - SLIP, cut; break
        worst = min(worst, lo_d[k] - entry)
        if lo_d[k] <= cur:
            exit_px, kind = cur - SLIP, ("BE" if be_done else "STOP"); break
        mfe = max(mfe, (hi_d[k] - entry) / risk)
        if hi_d[k] >= tg:
            exit_px, kind = tg, "TARGET"; break
        if pa and not pdone and hi_d[k] >= entry + pa["r"] * risk + TICK:
            pdone, ppx = True, entry + pa["r"] * risk
            if pa.get("lock") is not None:
                cur = max(cur, entry + pa["lock"] * risk)
                be_done = True
        if be_r is not None and not be_done and hi_d[k] >= entry + be_r * risk:
            if entry + BE_OFF > cur:
                cur = entry + BE_OFF
            be_done = True
        if ld:
            for a, lk in ld:
                if hi_d[k] >= entry + a * risk and entry + lk * risk > cur:
                    cur = entry + lk * risk
                    be_done = True
        if B.mod[k] >= flat:
            exit_px, kind = float(c_d[k]) - SLIP, "EOD"; break
        mins = round((B.t[k] - B.t[fill]) / 60.0) + B.secs // 60
        nxt = k + 1 < B.n and B.day[k + 1] == s_day
        if tc and not be_done and round((B.t[k] - B.t[fill]) / 60.0) + 1 == int(tc.get("at", 15)) \
                and mfe < float(tc.get("mfe", 0.5)) and c_d[k] < entry - float(tc.get("x", 0.3)) * risk:
            if nxt:
                cut = "CUT_T15"; k += 1; continue
        if tc2 and not be_done and round((B.t[k] - B.t[fill]) / 60.0) + 1 == int(tc2["at"]) \
                and mfe < float(tc2.get("mfe", 0.5)) and c_d[k] < entry - float(tc2.get("x", 0.0)) * risk:
            if nxt:
                cut = "CUT_T2"; k += 1; continue
        if st_ and not be_done and mins >= st_["min"] and mfe < st_["r"] and nxt:
            cut = "STALE"; k += 1; continue
        if rel is not None and not nd and float(B.t[k]) + B.secs >= rel:
            nd = True
            if nw.get("mode", "flat") == "flat":
                if not be_done and mfe < float(nw.get("r", 1.0)) and nxt:
                    cut = "NEWS"; k += 1; continue
            else:
                if mfe >= float(nw.get("r", 1.0)) and entry + BE_OFF > cur:
                    cur = entry + BE_OFF
                    be_done = True
        k += 1
    if exit_px is None:
        return None
    legs = None
    pts = exit_px - entry
    if pdone:
        f, pp = float(pa["f"]), ppx - entry
        legs = [(f, pp), (1.0 - f, pts)]
    return kind, pts, worst, mfe, k, legs


def trades2(X=None, T=None, mfn=None):
    """lit_edge.trades with manage2 (legs, partial: pts = share-weighted points)."""
    X = X or {}
    c = E.ctx()
    T = T if T is not None else c["T"]
    out = []
    for t in T:
        BX = c[60] if t["tf"] == 1 else c[300]
        B = BX.B
        d = t["dir"]
        fill = int(np.searchsorted(B.t, t["entry_t"]))
        entry, stop, tg = t["entry_px"] * d, t["stop_px"] * d, t["target_px"] * d
        risk = entry - stop
        r = manage2(X, BX, fill, d, entry, stop, tg, int(B.day[fill]), risk)
        kind, pts, worst, mfe, kx, legs = r
        row = c["intel"].get(int(t["entry_t"]), {})
        m = float(mfn(t, row)) if mfn else 1.0
        u = {"day": t["day"], "entry_t": int(t["entry_t"]), "exit_t": int(B.t[kx]) + B.secs, "dir": d, "exit": kind,
             "risk": round(risk, 2), "tgt": round(tg - entry, 2), "pts": round(pts, 4), "w1": round(worst, 4),
             "legs": [(1.0, pts)], "mfe": round(mfe, 3), "tf": t["tf"], "m": m, "floored": False,
             "live_exit": t.get("exit"), "live_pts": round((t["pnl"] + COMM * t["qty"]) / (PV * t["qty"]), 4)}
        if legs:
            u["legs"] = [(legs[0][0], legs[0][1]), (legs[1][0], legs[1][1])]
            u["pts"] = round(legs[0][0] * legs[0][1] + legs[1][0] * legs[1][1], 4)
        out.append(u)
    return out


def check():
    c = E.ctx()
    U = trades2({})
    bad = 0
    for u, t in zip(U, c["T"]):
        if u["exit"] != t["exit"] or abs(u["pts"] - u["live_pts"]) > 0.02:
            bad += 1
    print(f"options off vs live: {len(U)} trades, {bad} mismatches")
    for X in ({"news": {"lead": 2, "mode": "flat"}}, {"partial": {"f": 0.5, "r": 2.0}}):
        U2 = trades2(X)
        print(X, "changed trades:", sum(1 for a, b in zip(U, U2) if abs(a["pts"] - b["pts"]) > 1e-6),
              "2026:", sum(1 for a, b in zip(U, U2) if abs(a["pts"] - b["pts"]) > 1e-6 and a["day"] >= "2026"))


# ================================================================================================ scoring helpers
N_TESTED = 0


def placebo2(U, base_L, n=NPLC, seed=11):
    """Shuffle the tilt's multipliers inside each span (H1 / H2 / 2021-25 apart), n draws.
    p_h1 / p_h2: share of shuffles with at least the real tilt's $ in that half (low = real beats chance);
    chance_both: share of shuffles that beat the BASE in H1 and H2 together (the luck rate of a 'survivor');
    p_both: share of shuffles with at least the real tilt's $ in H1 and H2 together."""
    L = E.lit_size(U)
    real = {sp: sum(l["pnl"] for l in L if SPANS[sp][0] <= l["day"] <= SPANS[sp][1]) for sp in SPANS}
    base = {sp: sum(l["pnl"] for l in base_L if SPANS[sp][0] <= l["day"] <= SPANS[sp][1]) for sp in SPANS}
    rng = np.random.default_rng(seed)
    cnt = collections.Counter()
    for _ in range(n):
        V = [dict(u) for u in U]
        for sp, (a, z) in SPANS.items():
            ix = [i for i, u in enumerate(V) if a <= u["day"] <= z]
            ms = [V[i]["m"] for i in ix]
            rng.shuffle(ms)
            for i, m in zip(ix, ms):
                V[i]["m"] = m
        LL = E.lit_size(V)
        got = {sp: sum(l["pnl"] for l in LL if SPANS[sp][0] <= l["day"] <= SPANS[sp][1]) for sp in SPANS}
        for sp in ("H1", "H2"):
            if got[sp] >= real[sp]:
                cnt["p_" + sp.lower()] += 1
        if got["H1"] >= real["H1"] and got["H2"] >= real["H2"]:
            cnt["p_both"] += 1
        if got["H1"] > base["H1"] and got["H2"] > base["H2"]:
            cnt["chance_both"] += 1
    return {k: round(cnt[k] / n, 3) for k in ("p_h1", "p_h2", "p_both", "chance_both")}


def run_variant(res, fam, nm, base, L0, X=None, mfn=None, T=None, U=None, plc=False, fund=True, info=None):
    key = f"{fam}:{nm}"
    if key in res and not os.environ.get("IDEAS_REDO"):
        print(E.line(key, res[key]), flush=True)
        return res[key]
    if U is None:
        U = trades2(X, T=T, mfn=mfn)
    o, _, L = E.evaluate(U=U, fund=fund)
    o["chg"] = E.changed(L, L0)
    if plc:
        up = all(sum(l["pnl"] for l in L if SPANS[h][0] <= l["day"] <= SPANS[h][1]) >
                 sum(l["pnl"] for l in L0 if SPANS[h][0] <= l["day"] <= SPANS[h][1]) for h in ("H1", "H2"))
        o["placebo"] = placebo2(U, L0) if up else {"skipped": "not better in both halves"}
    n26 = [u for u in U if u["day"] >= "2026"]
    o["info"] = {**(info or {}), "up_2026": sum(1 for u in n26 if u["m"] > 1), "down_2026": sum(1 for u in n26 if u["m"] < 1),
                 "exits": dict(collections.Counter(u["exit"] for u in n26))}
    s = E.short(o, base)
    s["X"] = X
    res[key] = s
    print(E.line(key, s), "|", o.get("placebo", ""), flush=True)
    return s


# ================================================================================================ ideas
def lvl(row, k, dflt=np.nan):
    v = row.get(k)
    if v is True:
        return 1.0
    if v is False:
        return 0.0
    return E._num(v, dflt)


def feat_tilts():
    """name -> (mfn, desc, hypothesis). Cut points are H1 terciles (E.h1_cut). Direction = the hypothesis written BEFORE looking;
    both-way pairs are listed explicitly (and counted as tests)."""
    F_ = collections.OrderedDict()
    q = E.h1_cut

    def tri(key, hi_good, up=1.25, dn=0.75, which="both"):
        lo, hi = q(key, 1 / 3), q(key, 2 / 3)

        def f(t, r):
            v = lvl(r, key)
            if v != v:
                return 1.0
            g = (v >= hi) if hi_good else (v <= lo)          # the good tail
            b = (v <= lo) if hi_good else (v >= hi)          # the bad tail
            return up if (g and which in ("both", "up")) else dn if (b and which in ("both", "down")) else 1.0
        return f

    # --- VIX / VXN regime (size, never skip)
    F_["vix_lo_up125"] = (tri("vix", False, which="up"), "calm tape (VIX bottom third) x1.25", "calm = cleaner sweeps")
    F_["vix_hi_dn075"] = (tri("vix", False, which="down"), "VIX top third x0.75", "stress = trend days, reversals fail")
    F_["vix_both"] = (tri("vix", False), "VIX bottom third x1.25, top third x0.75", "same, both")
    F_["vixchg_up_dn075"] = (tri("vix_chg", False, which="down"), "VIX rose yesterday (top third) x0.75", "rising fear = trend")
    F_["vixchg_dn_up125"] = (tri("vix_chg", False, which="up"), "VIX fell yesterday (bottom third) x1.25", "falling fear = mean reversion")
    F_["vxn_hi_dn075"] = (tri("vxn", False, which="down"), "VXN top third x0.75", "tech fear premium")
    # --- time of day (pre-registered by session name, not mined)
    F_["lon_up125"] = (lambda t, r: 1.25 if r.get("session") == "London 02-05" else 1.0, "London 02-05 x1.25", "Asia/London sweeps are clean")
    F_["nyam_dn075"] = (lambda t, r: 0.75 if r.get("session") == "NY AM 09:30-11:30" else 1.0, "NY AM 09:30-11:30 x0.75", "news noise")
    F_["lon_up_nypm_dn"] = (lambda t, r: 1.25 if r.get("session") == "London 02-05" else 0.75 if str(r.get("session", "")).startswith("NY PM") else 1.0,
                            "London x1.25, NY PM x0.75", "time of day")
    F_["macro_up125"] = (lambda t, r: 1.25 if r.get("macro") is True else 1.0, "fill inside an ICT macro window x1.25", "macro = algorithmic delivery")
    F_["early_up125"] = (lambda t, r: 1.25 if E._num(r.get("entry_min"), 999) < 300 else 1.0, "entered before 05:00 ET x1.25", "overnight")
    # --- day of week (Monday review, Friday, the high/low-of-week window)
    F_["mon_dn075"] = (lambda t, r: 0.75 if r.get("weekday") in ("Mon", "Monday", 0) else 1.0, "Monday x0.75", "Monday review")
    F_["fri_dn075"] = (lambda t, r: 0.75 if r.get("weekday") in ("Fri", "Friday", 4) else 1.0, "Friday x0.75", "weekend de-risk")
    F_["how_up125"] = (lambda t, r: 1.25 if r.get("how") is True else 1.0, "sweep in the Tue 03:00 - Wed 11:30 high/low-of-week window x1.25",
                       "weekly reversals form Tue-Wed (ICT)")
    F_["how_dn075"] = (lambda t, r: 0.75 if r.get("how") is True else 1.0, "same window x0.75 (the eval-safe how_out switch as a size)", "the existing how_out idea")
    F_["midweek_up125"] = (lambda t, r: 1.25 if r.get("weekday") in ("Tue", "Wed", "Tuesday", "Wednesday", 1, 2) else 1.0, "Tue/Wed x1.25", "midweek")
    # --- price vs the 18:00 open, prior day / week, gap
    F_["disc_up125"] = (tri("pd18", False, which="up"), "entry in the discount vs the 18:00 open (bottom third) x1.25", "target is open +/- VIX move: more room")
    F_["prem_dn075"] = (tri("pd18", False, which="down"), "entry in the premium vs the 18:00 open (top third) x0.75", "less room")
    F_["disc_both"] = (tri("pd18", False), "discount x1.25, premium x0.75", "both")
    F_["prevday_with_up125"] = (tri("prev_day", True, which="up"), "prior day moved the trade's way (top third) x1.25", "daily momentum")
    F_["prevday_against_up125"] = (tri("prev_day", False, which="up"), "prior day moved against the trade (bottom third) x1.25", "reversal after exhaustion")
    F_["prevwk_with_up125"] = (tri("prev_week", True, which="up"), "prior week with the trade (top third) x1.25", "weekly momentum")
    F_["prevwk_against_up125"] = (tri("prev_week", False, which="up"), "prior week against the trade x1.25", "weekly exhaustion")
    F_["gap_with_up125"] = (tri("gap", True, which="up"), "gap in the trade's direction (top third) x1.25", "gap supports")
    F_["gap_against_dn075"] = (tri("gap", True, which="down"), "gap against the trade (bottom third) x0.75", "gap fights it")
    # --- setup strength as size
    F_["depth_up125"] = (tri("depth_atr", True, which="up"), "deep sweep (top third) x1.25", "deeper = more stops run")
    F_["depth_dn075"] = (tri("depth_atr", True, which="down"), "shallow sweep (bottom third) x0.75", "same")
    F_["disp_up125"] = (tri("disp", True, which="up"), "big displacement (top third) x1.25", "conviction")
    F_["obst_up125"] = (tri("obst_r", True, which="up"), "clear path (nearest opposing level far, top third) x1.25", "room to run")
    F_["obst_dn075"] = (tri("obst_r", True, which="down"), "opposing level close (bottom third) x0.75", "blocked")
    F_["vec_up125"] = (lambda t, r: 1.25 if r.get("vec") is True else 1.0, "PVSRA climax (volume) candle in the displacement x1.25", "volume confirms")
    F_["vec_dn075"] = (lambda t, r: 0.75 if r.get("vec") is not True else 1.0, "no climax-volume candle x0.75", "volume confirms")
    F_["fast_up125"] = (tri("leg_bars", False, which="up"), "extreme -> CISD in few bars (bottom third) x1.25", "fast reversal")
    F_["fast_dn_slow075"] = (tri("leg_bars", False, which="down"), "slow CISD (top third) x0.75", "slow reversal")
    F_["wait_short_up125"] = (tri("wait_min", False, which="up"), "filled quickly after the CISD (bottom third) x1.25", "immediate")
    F_["stopatr_wide_dn075"] = (tri("stop_atr", False, which="down"), "stop wide in ATR (top third) x0.75", "extra de-risk on wide stops")
    F_["stopatr_tight_up125"] = (tri("stop_atr", False, which="up"), "stop tight in ATR (bottom third) x1.25 (risk capped $990)", "tight stops pay")
    F_["idm_dist_up125"] = (tri("idm_dist", False, which="up"), "inducement close to the level (bottom third) x1.25", "clean inducement")
    F_["wick_up125"] = (tri("wick", True, which="up"), "long rejection wick (top third) x1.25", "rejection")
    # --- position inside the prior day's range (pdl..pdh) at the fill, in the trade's direction (low = buying discount / selling premium)
    c = E.ctx()
    M = c["M"]
    pos = {}
    for t in c["T"]:
        z = E.zc(t)
        x = M.ctx[z["k"]]
        if "pdh" in x and x["pdh"] > x["pdl"]:
            p_ = (t["entry_px"] - x["pdl"]) / (x["pdh"] - x["pdl"])
            pos[int(t["entry_t"])] = p_ if t["dir"] == 1 else 1.0 - p_
    h1pos = np.array([pos[int(t["entry_t"])] for t in c["T"] if "2026-01-01" <= t["day"] <= "2026-06-30" and int(t["entry_t"]) in pos])
    plo, phi = float(np.quantile(h1pos, 1 / 3)), float(np.quantile(h1pos, 2 / 3))
    F_["pdpos_disc_up125"] = (lambda t, r: 1.25 if pos.get(int(t["entry_t"]), 0.5) <= plo else 1.0,
                              "bought in the discount / sold in the premium of yesterday's range (bottom third) x1.25", "mean reversion inside the prior range")
    F_["pdpos_prem_dn075"] = (lambda t, r: 0.75 if pos.get(int(t["entry_t"]), 0.5) >= phi else 1.0,
                              "bought in the premium / sold in the discount of yesterday's range (top third) x0.75", "chasing")
    F_["pdpos_outside_up125"] = (lambda t, r: 1.25 if (pos.get(int(t["entry_t"]), 0.5) < 0.0 or pos.get(int(t["entry_t"]), 0.5) > 1.0) else 1.0,
                                 "fill outside yesterday's range x1.25", "stops run beyond the prior extreme")
    F_["pdpos_inside_dn075"] = (lambda t, r: 0.75 if 0.0 <= pos.get(int(t["entry_t"]), 0.5) <= 1.0 else 1.0,
                                "fill inside yesterday's range x0.75", "inside = chop")
    F_["asia_wide_up125"] = (tri("asia_rng", True, which="up"), "wide Asia range (top third) x1.25", "more liquidity resting")
    F_["asia_wide_dn075"] = (tri("asia_rng", True, which="down"), "narrow Asia range (bottom third) x0.75", "same")
    F_["lon_rng_dn075"] = (tri("lon_rng", False, which="down"), "wide London range (top third) x0.75 (NY entries)", "already moved")
    # --- ES / gamma confluence
    F_["es_up125"] = (lambda t, r: 1.25 if r.get("es_swept") is True else 1.0, "ES swept its own 3-hour extreme too x1.25", "SMT-like confluence")
    F_["es_dn075"] = (lambda t, r: 0.75 if r.get("es_swept") is not True else 1.0, "ES did not sweep x0.75", "no confluence")
    F_["gex_neg_dn075"] = (lambda t, r: 0.75 if r.get("gex_pos") is False else 1.0, "negative gamma x0.75", "negative gamma = trending")
    F_["gexpct_hi_up125"] = (tri("gex_pct", True, which="up"), "GEX percentile top third x1.25", "dealers dampen")
    F_["gexpct_lo_dn075"] = (tri("gex_pct", True, which="down"), "GEX percentile bottom third x0.75", "dealers amplify")
    # --- news
    F_["newsnear_dn05"] = (lambda t, r: 0.5 if E._num(r.get("news_next"), 600) <= 30 else 1.0, "a high-impact release within 30 min of the fill x0.5", "event risk")
    F_["newsnear_dn075"] = (lambda t, r: 0.75 if E._num(r.get("news_next"), 600) <= 60 else 1.0, "a release within 60 min of the fill x0.75", "event risk")
    F_["newsday_dn075"] = (lambda t, r: 0.75 if r.get("news_day") is True else 1.0, "news day x0.75", "event risk")
    # --- graded entry quality (continuous, never fewer than 0.75 x)
    sc = np.array([E.quality(E.ctx()["intel"][int(t["entry_t"])]) for t in E.ctx()["T"]
                   if "2026-01-01" <= t["day"] <= "2026-06-30" and int(t["entry_t"]) in E.ctx()["intel"]])
    sc.sort()

    def graded(lo, hi):
        def f(t, r):
            if not r:
                return 1.0
            p = float(np.searchsorted(sc, E.quality(r))) / len(sc)       # H1 percentile 0..1
            return lo + (hi - lo) * min(1.0, max(0.0, p))
        return f
    F_["graded_075_125"] = (graded(0.75, 1.25), "A+ score as a smooth size: 0.75x at the H1 bottom to 1.25x at the top", "never skip")
    F_["graded_05_15"] = (graded(0.5, 1.5), "A+ score as a smooth size: 0.5x to 1.5x", "stronger")
    return F_


def streak_fns(U0):
    """Size by what LIT just did (known at the fill): the previous finished trade's result in R, the week's R so far."""
    order = sorted(U0, key=lambda u: u["entry_t"])
    prev, wk = {}, {}
    hist = []
    for u in order:
        done = [h for h in hist if h["exit_t"] <= u["entry_t"]]
        prev[u["entry_t"]] = (done[-1]["pts"] / done[-1]["risk"]) if done else 0.0
        l2 = done[-2:]
        wkk = lit.iso_week(u["day"])
        wk[u["entry_t"]] = (sum(h["pts"] / h["risk"] for h in done if lit.iso_week(h["day"]) == wkk),
                            [h["pts"] / h["risk"] for h in l2])
        hist.append(u)
    F_ = collections.OrderedDict()
    F_["after_loss_dn075"] = (lambda t, r: 0.75 if prev.get(int(t["entry_t"]), 0) < -0.5 else 1.0, "previous trade lost > 0.5R: x0.75", "tilt/cold hand")
    F_["after_loss_up125"] = (lambda t, r: 1.25 if prev.get(int(t["entry_t"]), 0) < -0.5 else 1.0, "previous trade lost > 0.5R: x1.25", "mean reversion of luck")
    F_["after_win_up125"] = (lambda t, r: 1.25 if prev.get(int(t["entry_t"]), 0) > 1.0 else 1.0, "previous trade won > 1R: x1.25", "hot hand")
    F_["after_win_dn075"] = (lambda t, r: 0.75 if prev.get(int(t["entry_t"]), 0) > 1.0 else 1.0, "previous trade won > 1R: x0.75", "give-back")
    F_["after_2loss_dn05"] = (lambda t, r: 0.5 if len(wk.get(int(t["entry_t"]), (0, []))[1]) == 2 and all(x < -0.5 for x in wk[int(t["entry_t"])][1]) else 1.0,
                              "two losses in a row: x0.5", "cold streak as size, not skip")
    F_["wk_red_dn075"] = (lambda t, r: 0.75 if wk.get(int(t["entry_t"]), (0, []))[0] < -1.0 else 1.0, "week-to-date below -1R: x0.75", "week de-risk")
    F_["wk_green_up125"] = (lambda t, r: 1.25 if wk.get(int(t["entry_t"]), (0, []))[0] > 2.0 else 1.0, "week-to-date above +2R: x1.25", "house money")
    return F_


def mgmt_variants():
    V = collections.OrderedDict()
    for f in (1 / 3, 0.5):
        for r in (1.0, 2.0, 3.0, 4.0):
            V[f"partial_f{f:.2f}_r{r}"] = {"partial": {"f": f, "r": r}}
    V["partial_f0.50_r2_lock1"] = {"partial": {"f": 0.5, "r": 2.0, "lock": 1.0}}
    V["partial_f0.50_r4_lock2"] = {"partial": {"f": 0.5, "r": 4.0, "lock": 2.0}}
    V["partial_f0.33_r3_lock1.5"] = {"partial": {"f": 1 / 3, "r": 3.0, "lock": 1.5}}
    V["partial_f0.25_r2_lock0.5"] = {"partial": {"f": 0.25, "r": 2.0, "lock": 0.5}}
    for lad in ([[1.0, 0.1]], [[1.0, 0.25]], [[1.5, 0.5]], [[2, 0.5]], [[3, 1.0]], [[4, 2.0]], [[3, 1.0], [5, 3.0]], [[2, 0.5], [4, 2.0], [6, 4.0]], [[2.5, 1.0], [5, 2.5]]):
        V["ladder_" + "_".join(f"{a}to{b}" for a, b in lad)] = {"ladder": lad}
    for at in (30, 45, 60, 90):
        for x, mfe in ((0.0, 0.5), (0.3, 0.5)):
            V[f"tc2_at{at}_x{x}"] = {"tc2": {"at": at, "x": x, "mfe": mfe}}
    for at in (10, 20, 25):
        V[f"tc1_at{at}"] = {"tc1": {"at": at}}
    for m in (60, 90, 120, 180, 240):
        for r in (0.5, 1.0):
            V[f"stale_m{m}_r{r}"] = {"stale": {"min": m, "r": r}}
    for lead in (2, 5, 10):
        V[f"news_flat_lead{lead}_r1"] = {"news": {"lead": lead, "mode": "flat", "r": 1.0}}
    V["news_flat_lead5_r0.5"] = {"news": {"lead": 5, "mode": "flat", "r": 0.5}}
    for r in (0.5, 1.0, 1.5):
        V[f"news_be_lead5_r{r}"] = {"news": {"lead": 5, "mode": "be", "r": r}}
    V["news_flat_or_be_lead5"] = {"news": {"lead": 5, "mode": "flat", "r": 1.0}}
    return V


def engine2_variants():
    """Per-session (killzone) overrides of the live thresholds, sweep-depth ceiling, stop caps: one change at a time."""
    V = collections.OrderedDict()
    SES = {"s0200_0500": (120, 300), "s0500_0800": (300, 480), "s0800_0930": (480, 570), "s0930_1530": (570, 930)}
    for sn, (a, b) in SES.items():
        for nm, ov in (("disp0.6", {"disp": 0.6}), ("disp1.0", {"disp": 1.0}), ("disp1.3", {"disp": 1.3}),
                       ("depth0.3", {"depth": 0.3}), ("depth0.8", {"depth": 0.8}),
                       ("bank6", {"max_rr": 6.0}), ("bank12", {"max_rr": 12.0})):
            V[f"kz_{sn}_{nm}"] = {"kz": [[a, b, ov]]}
    for v in (2.0, 3.0, 4.0):
        V[f"depth_max{v}"] = {"depth_max": v}
    for v in (50, 60, 70):
        V[f"max_stop{v}"] = {"max_stop": float(v)}
    for v in (10, 12, 15):
        V[f"min_stop{v}"] = {"min_stop": float(v)}
    V["monday_half"] = {"monday": False, "_mon_m": 0.5}
    V["monday_quarter"] = {"monday": False, "_mon_m": 0.25}
    V["wk_stop_3"] = {"wk_stop": [3, 0.5]}
    V["wk_stop_off"] = {"wk_stop": None}
    V["wk_stop_2_0.75"] = {"wk_stop": [2, 0.75]}
    return V


def engine_variants():
    """Entry-side runs (the real engine, lit_final.run): each ~minutes. Window = entry-bar ET minutes."""
    V = collections.OrderedDict()
    V["monday_off"] = {"monday": False}
    V["win_end_1130"] = {"window": [[120, 690]]}
    V["win_end_1300"] = {"window": [[120, 780]]}
    V["win_end_1400"] = {"window": [[120, 840]]}
    V["win_start_0300"] = {"window": [[180, 930]]}
    V["win_london_only_0200_0800"] = {"window": [[120, 480]]}
    V["win_no_lunch_1130_1330"] = {"window": [[120, 690], [810, 930]]}
    V["win_pre_london_0000_0200_plus"] = {"window": [[0, 120], [120, 930]]}
    V["win_0000_0200_only"] = {"window": [[0, 120]]}
    V["win_late_ext_1600"] = {"window": [[120, 960]]}
    return V


# ================================================================================================ grid
def grid(fams=None):
    res = json.load(open(OUT)) if os.path.exists(OUT) else {}
    t0 = time.time()
    c = E.ctx()
    base, U0, L0 = E.evaluate({}, fund=True)
    bs = E.short(base)
    res["base"] = bs
    print(E.line("base", bs), flush=True)
    fams = fams or ["mgmt", "tilt", "streak", "engine", "engine2"]

    def dump():
        json.dump(res, open(OUT, "w"), indent=1, default=float)

    if "mgmt" in fams:
        for nm, X in mgmt_variants().items():
            run_variant(res, "mgmt", nm, bs, L0, X=X)
            dump()
    if "tilt" in fams:
        sh = os.environ.get("IDEAS_SHARD")
        for ix, (nm, (fn, desc, hyp)) in enumerate(feat_tilts().items()):
            if sh and ix % int(sh.split("/")[1]) != int(sh.split("/")[0]):
                continue
            run_variant(res, "tilt", nm, bs, L0, mfn=fn, plc=True, info={"desc": desc, "hyp": hyp})
            dump()
    if "streak" in fams:
        for nm, (fn, desc, hyp) in streak_fns(U0).items():
            run_variant(res, "streak", nm, bs, L0, mfn=fn, plc=True, info={"desc": desc, "hyp": hyp})
            dump()
    if "engine" in fams:
        for nm, ch in engine_variants().items():
            key = f"engine:{nm}"
            if key in res and not os.environ.get("IDEAS_REDO"):
                print(E.line(key, res[key]), flush=True)
                continue
            t1 = time.time()
            T = F.run({**LIVE, **ch})
            mfn = None
            if nm == "monday_off":
                pass
            run_variant(res, "engine", nm, bs, L0, T=T, mfn=mfn, info={"ch": ch, "n_trades": len(T), "secs": round(time.time() - t1)})
            dump()
    if "engine2" in fams:
        for nm, ch in engine2_variants().items():
            key = f"engine2:{nm}"
            if key in res and not os.environ.get("IDEAS_REDO"):
                print(E.line(key, res[key]), flush=True)
                continue
            t1 = time.time()
            ch = dict(ch)
            mon_m = ch.pop("_mon_m", None)
            wk_old = LIVE.get("wk_stop")
            if "wk_stop" in ch:                       # the weekly stop is applied by lit_edge.wk_mult (LIT size + funded), not the trade list
                LIVE["wk_stop"] = ch.pop("wk_stop")
            T = F.run({**LIVE, **ch})
            mfn = None
            if mon_m:
                M = c["M"]
                mfn = lambda t, r, mm=mon_m: mm if lit.monday_block(M, E.zc(t)) else 1.0
            try:
                run_variant(res, "engine2", nm, bs, L0, T=T, mfn=mfn, info={"ch": ch, "n_trades": len(T), "secs": round(time.time() - t1)})
            finally:
                LIVE["wk_stop"] = wk_old
            dump()
    dump()
    json.dump({k: {kk: v[kk] for kk in v if kk in ("lit", "eval", "fund", "d_lit", "d_eval", "d_p10", "d_f10", "d_fund", "chg",
                                                    "placebo", "info", "X")} | {"gate": E.gate(v)}
               for k, v in res.items()}, open(OUT_S, "w"), indent=0, separators=(",", ":"), default=float)
    print(f"done in {time.time() - t0:.0f}s -> {OUT}", flush=True)
    return res


def robust():
    """Neighbours and a long placebo for the two size tilts that beat their shuffles (stop tight in ATR, fast extreme -> CISD)."""
    global NPLC
    res = json.load(open(OUT_R)) if os.path.exists(OUT_R) else {}
    c = E.ctx()
    base, U0, L0 = E.evaluate({}, fund=True)
    bs = E.short(base)
    res["base"] = bs

    def mk(key, q, up, hi_good=False, dn_q=None, dn=1.0):
        lo = E.h1_cut(key, q)
        hi = E.h1_cut(key, 1 - dn_q) if dn_q else None

        def f(t, r):
            v = lvl(r, key)
            if v != v:
                return 1.0
            if (v <= lo) if not hi_good else (v >= lo):
                return up
            if hi is not None and ((v >= hi) if not hi_good else (v <= hi)):
                return dn
            return 1.0
        return f
    NPLC = 150
    for key, nm in (("stop_atr", "stopatr"), ("leg_bars", "fast")):
        for q in (0.25, 0.33, 0.5):
            for up in ((1.15, 1.25, 1.5) if nm == "stopatr" else (1.25,)):
                run_variant(res, "robust", f"{nm}_q{q}_x{up}", bs, L0, mfn=mk(key, q, up), plc=True, info={"cut": E.h1_cut(key, q)})
                json.dump(res, open(OUT_R, "w"), indent=1, default=float)
    # both together (x1.25 each, x1.5 when both)
    f1, f2 = mk("stop_atr", 0.33, 1.25), mk("leg_bars", 0.33, 1.25)
    run_variant(res, "robust", "stopatr_and_fast_x1.25_each", bs, L0, mfn=lambda t, r: min(1.5, f1(t, r) * f2(t, r)), plc=True)
    # tight stop + size down on the loosest third (the size-follows-the-stop view)
    run_variant(res, "robust", "stopatr_tight1.25_wide0.85", bs, L0, mfn=mk("stop_atr", 0.33, 1.25, dn_q=0.33, dn=0.85), plc=True)
    json.dump(res, open(OUT_R, "w"), indent=1, default=float)
    # the long placebo on the two picks (1,500 shuffles)
    NPLC = int(os.environ.get("IDEAS_LONG", "1500"))
    for key, nm in (("stop_atr", "stopatr"), ("leg_bars", "fast")):
        U = trades2({}, mfn=mk(key, 0.33, 1.25))
        pl = placebo2(U, L0, n=NPLC, seed=5)
        res[f"long_placebo:{nm}_q0.33_x1.25"] = pl
        print("long placebo", nm, NPLC, pl, flush=True)
        json.dump(res, open(OUT_R, "w"), indent=1, default=float)
    # yearly LIT-size deltas of the stop-ATR pick (2021-25 reference, one line per year)
    U = trades2({}, mfn=mk("stop_atr", 0.33, 1.25))
    L = E.lit_size(U)
    yr = collections.defaultdict(lambda: [0.0, 0.0])
    for l in L:
        yr[l["day"][:4]][0] += l["pnl"]
    for l in L0:
        yr[l["day"][:4]][1] += l["pnl"]
    res["yearly:stopatr_q0.33_x1.25"] = {y: {"tilt": round(a), "base": round(b), "d": round(a - b)} for y, (a, b) in sorted(yr.items())}
    print(res["yearly:stopatr_q0.33_x1.25"], flush=True)
    json.dump(res, open(OUT_R, "w"), indent=1, default=float)
    print("done in robust", flush=True)


def scale_look():
    """Scale-in (OFF) per trade at LIT size: the $ the adds make, the best 3 removed, and the extra cost of worse add fills
    (+0 / 2 / 4 / 8 ticks per add micro and the live $1.90 vs the research $1.40) -> research/lit/ideas_night_scale.json."""
    T0 = F.run({**LIVE})
    T1 = F.run({**LIVE, "scale_in": E.SCALE})
    b = {t["entry_t"]: t for t in T0}
    rows = [(t["day"], round(t["pnl"] - b[t["entry_t"]]["pnl"]), sum(int(a.get("qty", 0)) for a in t["adds"])) for t in T1 if t.get("adds")]
    out = {}
    for sp, a, z in (("H1", "2026-01-01", "2026-06-30"), ("H2", "2026-07-01", "2026-12-31")):
        r = [x for x in rows if a <= x[0] <= z]
        d = sorted((x[1] for x in r), reverse=True)
        q = sum(x[2] for x in r)
        out[sp] = {"trades_with_adds": len(r), "gain": sum(d), "best3": d[:3], "worst3": d[-3:], "gain_without_best3": sum(d[3:]), "add_micros": q,
                   "extra_cost": {str(tk): round(q * (tk * 0.25 * 2.0 + 0.5)) for tk in (0, 2, 4, 8)}}
    json.dump(out, open(os.path.join(ROOT, "research", "lit", "ideas_night_scale.json"), "w"), indent=1)
    print(json.dumps(out))


OUT_R = os.path.join(ROOT, "research", "lit", "ideas_night_robust.json")


def merge():
    """All ideas_night_grid*.json -> research/lit/ideas_night_results.json (headline numbers + gate flag per version)."""
    import glob
    res = {}
    for fn in sorted(glob.glob(os.path.join(ROOT, "research", "lit", "ideas_night_grid*.json"))):
        res.update(json.load(open(fn)))
    json.dump({k: {kk: v[kk] for kk in v if kk in ("lit", "eval", "fund", "d_lit", "d_eval", "d_p10", "d_f10", "d_fund", "chg",
                                                    "placebo", "info", "X")} | {"gate": E.gate(v)}
               for k, v in res.items()}, open(OUT_S, "w"), indent=0, separators=(",", ":"), default=float)
    print(len(res) - 1, "versions ->", OUT_S)


def rebuild(key):
    """Units of a grid key (for rl.save)."""
    c = E.ctx()
    if key == "base":
        return trades2({})
    fam, nm = key.split(":", 1)
    if fam == "mgmt":
        return trades2(mgmt_variants()[nm])
    if fam == "tilt":
        return trades2({}, mfn=feat_tilts()[nm][0])
    if fam == "streak":
        return trades2({}, mfn=streak_fns(trades2({}))[nm][0])
    ch = dict((engine_variants() if fam == "engine" else engine2_variants())[nm])
    mon_m = ch.pop("_mon_m", None)
    wk_old = LIVE.get("wk_stop")
    try:
        if "wk_stop" in ch:
            LIVE["wk_stop"] = ch.pop("wk_stop")
        T = F.run({**LIVE, **ch})
        mfn = (lambda t, r, mm=mon_m: mm if lit.monday_block(c["M"], E.zc(t)) else 1.0) if mon_m else None
        U = trades2({}, T=T, mfn=mfn)
        L = E.lit_size(U)               # sized while the wk_stop override is on
        return U, L
    finally:
        LIVE["wk_stop"] = wk_old


PROMISING = ("tilt:stopatr_tight_up125", "mgmt:tc2_at60_x0.0")


def save_runs(keys, status="rejected"):
    from tools import runlib as rl
    res = {}
    import glob
    for fn in sorted(glob.glob(os.path.join(ROOT, "research", "lit", "ideas_night_grid*.json"))):
        res.update(json.load(open(fn)))
    for key in keys:
        s = res[key]
        r = rebuild(key)
        U, L = r if isinstance(r, tuple) else (r, E.lit_size(r))
        L = [{k: (v.item() if isinstance(v, np.generic) else v) for k, v in l.items()} for l in L]
        S = rl.score(L, F.SESS)
        h = lambda sp: f"PF {s['lit'][sp]['pf']} net {s['lit'][sp]['net']:+,} (${s['lit'][sp]['per_month']:,}/mo) {s['lit'][sp]['tpw']}/wk"
        e = lambda sp: (f"PF {s['eval'][sp]['pf']} net {s['eval'][sp]['net']:+,} 2w {s['eval'][sp]['p10']}/{s['eval'][sp]['f10']} "
                        f"dec10 {s['eval'][sp]['dec10']} med {s['eval'][sp]['pass_med']}")
        ver = (f"LIT size: H1 {h('H1')}; H2 {h('H2')}; 2021-25 ref {h('2021-25')}. Eval path (two_week): H1 {e('H1')}; H2 {e('H2')}. "
               f"Funded 50K $/mo H1 {s['fund']['H1']['per_month']} / H2 {s['fund']['H2']['per_month']}. Placebo {s.get('placebo')}.")
        rid = "lit_ideas_" + key.replace(":", "_").replace(".", "")
        rl.save(rid, f"LIT ideas night: {key}", "other", "Job 26 (2026-11-04): new LIT ideas on the exact live trades",
                params={**LIVE, "x_ideas": s.get("X") or key}, trades=L, scored=S,
                status=("info" if key == "base" else "promising" if key in PROMISING else status), verdict=ver,
                notes="tools/lit_ideas_night.py: live LIT trades (== lit_live), post-fill executor, LIT size rule; eval = live two_week; funded 50K",
                writeup="2026-11-04_lit_ideas_night", tags=["lit", "lit_ideas_night"])
        print("saved", rid, flush=True)


def report(min_h=2.0):
    """Ranked table from the grid file: d LIT $ (H1 picked / H2 checked), d eval-path $, d 2-week pass / fail, placebo, gate."""
    import glob
    res = {}
    for fn in sorted(glob.glob(os.path.join(ROOT, "research", "lit", "ideas_night_grid*.json"))):
        res.update(json.load(open(fn)))
    base = res["base"]
    rows = []
    for k, s in res.items():
        if k == "base" or "d_lit" not in s:
            continue
        pl = s.get("placebo") or {}
        both = s["d_lit"]["H1"] > 0 and s["d_lit"]["H2"] > 0
        eval_ok = s["d_eval"]["H1"] > 0 and s["d_eval"]["H2"] > 0
        no_more_fail = s["d_f10"]["H1"] <= 0 and s["d_f10"]["H2"] <= 0
        tpw_ok = s["lit"]["H1"]["tpw"] >= 2.0 and s["lit"]["H2"]["tpw"] >= 2.0
        fund_ok = ("d_fund" not in s) or (s["d_fund"]["H1"] >= -10 and s["d_fund"]["H2"] >= -10)
        rows.append({"k": k, "dH1": s["d_lit"]["H1"], "dH2": s["d_lit"]["H2"], "dR": s["d_lit"]["2021-25"],
                     "eH1": s["d_eval"]["H1"], "eH2": s["d_eval"]["H2"], "p10": (s["d_p10"]["H1"], s["d_p10"]["H2"]),
                     "f10": (s["d_f10"]["H1"], s["d_f10"]["H2"]), "fund": tuple(s["d_fund"].values()) if "d_fund" in s else None,
                     "tpw": (s["lit"]["H1"]["tpw"], s["lit"]["H2"]["tpw"]), "pl": pl, "both": both, "eval_ok": eval_ok,
                     "nf": no_more_fail, "tpw_ok": tpw_ok, "fund_ok": fund_ok,
                     "chg": s.get("chg"), "n": res[k].get("info", {})})
    n_all = len(rows)
    n_tilt = sum(1 for r in rows if r["pl"])
    print(f"variants scored: {n_all} (size tilts with a placebo: {n_tilt}); base H1 {base['lit']['H1']['net']:+,} H2 {base['lit']['H2']['net']:+,}")
    print("== passes both halves at LIT size + eval path + no more 2-week fails + 2/wk + funded not worse")
    for r in sorted(rows, key=lambda r: -(r["dH1"] + r["dH2"])):
        if r["both"] and r["eval_ok"] and r["nf"] and r["tpw_ok"] and r["fund_ok"]:
            print(f"  {r['k']:40s} dLIT H1 {r['dH1']:+7,} H2 {r['dH2']:+7,} ref {r['dR']:+7,} | dEVAL {r['eH1']:+7,} {r['eH2']:+7,} | p10 {r['p10']} f10 {r['f10']} "
                  f"| fund {r['fund']} | placebo {r['pl']} | chg {r['chg']}")
    print("== everything, by H2 change")
    for r in sorted(rows, key=lambda r: -r["dH2"]):
        print(f"  {r['k']:40s} dLIT H1 {r['dH1']:+7,} H2 {r['dH2']:+7,} ref {r['dR']:+7,} | dEVAL {r['eH1']:+7,} {r['eH2']:+7,} | p10 {r['p10']} f10 {r['f10']} "
              f"| fund {r['fund']} | tpw {r['tpw']} | pl {r['pl']}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "check":
        check()
    elif cmd == "grid":
        grid(sys.argv[2:] or None)
    elif cmd == "merge":
        merge()
    elif cmd == "scale":
        scale_look()
    elif cmd == "robust":
        robust()
    elif cmd == "report":
        report()
    elif cmd == "save":
        save_runs(sys.argv[2:])
