"""LIT edge night (2026-10-29/30, owner: "build every bot more than you can, find more edge, better rules for everything").
research/writeups/lit-edge-2026-10-30.md. Paper research only: engine/ and live_model*.json untouched.

Base = the live LIT trades (tools/lit_final.run with live_model.json "lit": 631 trades, 120 in 2026, == run lit_live), re-walked
after the fill by the executor of tools/lit_rev_exit.py (options off == every live exit and point, `check`). New options (all
decided at a bar's CLOSE, acting from the next bar; nothing looks ahead):

  tgt   {"mode": "vix"|"adr"|"bmax"|"bmin"|"bmean"|"entry"|"time", "k": x, "n": ADR days}: the target band from the 18:00 open
        +/- k x the average daily range of the N trading days before (adr), the farther / nearer / mean of that and the VIX
        band (bmax / bmin / bmean, VIX k 1.0), the entry +/- k VIX moves (entry), or the entry +/- k VIX moves x sqrt(time
        left to 16:00 / 22 h) (time). Banked at 8R as live; never below 1.5R from the fill (the setup list stays live).
  be    {"atr": k | "pts": p, "how": "max"|"min"}: the breakeven trigger in 5m ATR (k x ATR(14) of the last closed 5m bar
        before the fill) or points instead of 1R: "max" = max(1R, that) (narrow stops wait for a real move), "min" =
        min(1R, that) (wide stops protect sooner). Still entry + 1.25.
  speed {"r": R, "min": m}: the trade reached +R within m minutes of the fill -> the 8R bank is lifted (the unbanked band).
  slow  {"min": m, "r": R, "rr": X}: m minutes after the fill the trade never reached +R -> the target comes in to X R
        (already beyond it -> out at the next open).
  late  {"at": ET minute, "rr": X}: from that minute on, the target is at most X R (already beyond -> out at the next open).

Size tilts (multiplier m on the trade, one rounding with the weekly stop): LIT size rule (size-up never risks more than
$990 incl. 1 tick + $1.40), eval path (m goes in as the engine's idm_m: engine/sizing.lit_qty two_week, the live caps
after it), funded path (idm_m with idm_cap $1,500 = the live funded per-trade max; tools/uprisk.funded_mc, the MFFU Builder
Sim Funded rules of engine/funded_life, 1,000 six-month paths of 5-session blocks per span, live funded sizing 60% of the
room <= $1,500, winner <= $2,000). Features = research/lab/trade_intel.json (57 facts known at the fill, look-ahead tested).
Random placebo for every tilt: the same multipliers shuffled across the span's trades, 200 draws.

Entry-side: weekly catch-up (a looser setup on Thu/Fri when the week has < 2 trades) from engine runs with looser params;
scale-in (built, OFF) re-measured on today's live; eval knobs (two_week_until, room_f) re-measured on today's trades.

  python -X utf8 tools/lit_edge.py check          # options off == live trades; band recompute == live targets
  python -X utf8 tools/lit_edge.py grid [fam..]   # families tgt be dyn tc tilt reentry catchup second tp ebank scale evalknobs
                                                  # -> research/lit/edge_grid.json (gitignored; EDGE_OUT=<file> per process)
  python -X utf8 tools/lit_edge.py merge          # edge_grid*.json -> edge_grid.json + research/lit/edge_results.json (committed)
  python -X utf8 tools/lit_edge.py save           # rl.save runs lit_edge_* (PICKS)
"""
from __future__ import annotations

import collections
import copy
import json
import logging
import math
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
logging.getLogger("engine.sizing").setLevel(logging.ERROR)
from engine import lit  # noqa: E402
from engine import sizing as SZ  # noqa: E402
from tools import lit_final as F  # noqa: E402
from tools import lit_adv_manage as A  # noqa: E402
from tools import lit_big_ideas as BI  # noqa: E402  (patches A.run_eval; replaced below by run_eval_m)
from tools import lit_rev_exit as R  # noqa: E402
from tools import runlib as rl  # noqa: E402
from tools import uprisk as UP  # noqa: E402

OUT = os.environ.get("EDGE_OUT") or os.path.join(ROOT, "research", "lit", "edge_grid.json")   # full grid (gitignored)
OUT_S = os.path.join(ROOT, "research", "lit", "edge_results.json")     # headline numbers per variant (committed)
PV, COMM, SLIP, TICK = lit.PV, lit.COMM, lit.SLIP, lit.TICK
LIVE = R.LIVE
BE_OFF = R.BE_OFF
SPANS = R.SPANS
DAY_MIN = 1320.0                    # 18:00 -> 16:00 ET, the trading day the VIX one-day move covers (minutes)
N_FUND = int(os.environ.get("EDGE_NFUND", "1000"))
FUND_LIVE = dict(UP.FUND_LIVE)
SCALE = {"pb": 0.25, "f": 1.0, "rat_k": 1.0, "min_rk": 2.0, "n": 1}


# ================================================================================================ context
_C = {}


def ctx():
    if not _C:
        c = R.cx()
        M = c["M"]
        _C.update(c)
        _C["dix"] = {str(d): k for k, (d, s, e) in enumerate(M.days)}
        rng = np.array([float(M.h[s:e].max() - M.l[s:e].min()) for d, s, e in M.days])
        _C["rng"] = rng
        for n in (5, 10, 20):
            a = np.full(len(rng), np.nan)
            for k in range(n, len(rng)):
                a[k] = rng[k - n:k].mean()
            _C[f"adr{n}"] = a
        I = json.load(open(os.path.join(ROOT, "research", "lab", "trade_intel.json"), encoding="utf-8"))
        keys = [c_["key"] for c_ in I["cols"]]
        _C["intel"] = {int(r[2]): dict(zip(keys, r)) for r in I["rows"] if r[0] == "backtest"}
        _C["S_up"] = UP.sessions()
    return _C


def atr5_at(entry_t):
    c = ctx()
    B5 = c[300].B
    j = int(np.searchsorted(B5.t, entry_t - 300, side="right")) - 1
    return float(c[300].atr[max(0, j)])


def zc(t):
    """The engine candidate of trade t (planned entry ep = min(CISD level, trigger close), its day index k)."""
    c = ctx()
    if "zc" not in c:
        M, C = F.market(LIVE["ref"], LIVE["extra_boxes"])
        c["zc"] = {(int(z["i"]), int(z["dir"])): z for z in C}
    return c["zc"][(int(t["i"]), int(t["dir"]))]


def band(t, o):
    """Target level (direction space) of mode o for trade t with the live caps: min(band level, planned entry + 8 planned R,
    fill + 8 fill R) (== the engine's target for mode vix, k 1); never below planned entry + 1.5 planned R (the engine's
    setup check; a variant whose band falls below that would skip the setup: counted as `floored`, kept at 1.5R).
    Returns (level, unbanked level, floored)."""
    c = ctx()
    M = c["M"]
    d = t["dir"]
    z = zc(t)
    x = M.ctx[z["k"]]
    entry = t["entry_px"] * d
    stop = t["stop_px"] * d
    ep = min(float(z["ref_d"]), z["trig_c"])
    rp, rf = ep - stop, entry - stop
    vm = float(x["vix_move"])
    o18 = float(x["open18"]) * d
    mode, kk = o.get("mode", "vix"), float(o.get("k", 1.0))
    adr = c[f"adr{int(o.get('n', 10))}"][z["k"]]
    if mode == "vix":
        p = o18 + kk * vm
    elif mode == "adr":
        p = o18 + kk * adr
    elif mode in ("bmax", "bmin", "bmean"):
        a, b = o18 + vm, o18 + kk * adr
        p = max(a, b) if mode == "bmax" else min(a, b) if mode == "bmin" else 0.5 * (a + b)
    elif mode == "entry":
        p = ep + kk * vm
    elif mode == "mid":
        p = float(M.open_00[int(z["i"])]) * d + kk * vm
    elif mode == "time":
        left = max(30.0, 960.0 - float(z["mod"]))
        p = ep + kk * vm * math.sqrt(left / DAY_MIN)
    else:
        raise ValueError(mode)
    raw = p
    floored = p - ep < LIVE["min_rr"] * rp
    p = max(p, ep + LIVE["min_rr"] * rp)
    p = min(p, ep + LIVE["max_rr"] * rp, entry + LIVE["max_rr"] * rf)
    return p, raw, floored


# ================================================================================================ executor (post-fill)
def manage(X, BX, fill, d, entry, stop, tg, s_day, risk, tg_far=None, be_r=None, tc_x=None):
    """tools/lit_rev_exit.manage (options off == live) + the speed / slow / late target rules and a per-trade BE trigger."""
    X = X or {}
    B = BX.B
    hi_d, lo_d, c_d, o_d = B.dirs(d)
    flat = LIVE["flat_mod"]
    on1 = B.secs == 60
    tc = LIVE.get("t_check") if on1 else None
    if tc and tc_x is not None:
        tc = {**tc, "x": tc_x}
    be_r = LIVE["be_r"] if be_r is None else be_r
    sp, sl, la = X.get("speed"), X.get("slow"), X.get("late")
    cur, be_done, mfe, worst = stop, False, 0.0, 0.0
    cut = None
    sp_done = sl_done = False
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
        if be_r is not None and not be_done and hi_d[k] >= entry + be_r * risk:
            if entry + BE_OFF > cur:
                cur = entry + BE_OFF
            be_done = True
        if B.mod[k] >= flat:
            exit_px, kind = float(c_d[k]) - SLIP, "EOD"; break
        mins = round((B.t[k] - B.t[fill]) / 60.0) + B.secs // 60       # minutes from the fill to this bar's close
        if tc and not be_done and round((B.t[k] - B.t[fill]) / 60.0) + 1 == int(tc.get("at", 15)) \
                and mfe < float(tc.get("mfe", 0.5)) and c_d[k] < entry - float(tc.get("x", 0.3)) * risk:
            if k + 1 < B.n and B.day[k + 1] == s_day:
                cut = "CUT_T15"
                k += 1
                continue
        nxt = k + 1 < B.n and B.day[k + 1] == s_day
        if sp and not sp_done and tg_far is not None and mins <= sp["min"] and mfe >= sp["r"]:
            sp_done = True
            tg = max(tg, tg_far)
        if sl and not sl_done and mins >= sl["min"]:
            sl_done = True
            if mfe < sl["r"]:
                tg = min(tg, entry + sl["rr"] * risk)
                if c_d[k] >= tg and nxt:
                    cut = "SLOW"; k += 1; continue
        if la and B.mod[k] + B.secs // 60 >= la["at"]:
            tg2 = min(tg, entry + la["rr"] * risk)
            if tg2 < tg:
                tg = tg2
            if c_d[k] >= tg and nxt:
                cut = "LATE"; k += 1; continue
        k += 1
    if exit_px is None:
        return None
    return kind, exit_px - entry, worst, mfe, k


def trades(X=None, T=None, mfn=None):
    """Every live trade (or T) re-managed under X; mfn(t, intel_row) -> size multiplier m (default 1)."""
    X = X or {}
    c = ctx()
    T = T if T is not None else c["T"]
    out = []
    for t in T:
        BX = c[60] if t["tf"] == 1 else c[300]
        B = BX.B
        d = t["dir"]
        fill = int(np.searchsorted(B.t, t["entry_t"]))
        assert int(B.t[fill]) == t["entry_t"], t["day"]
        entry, stop, tg = t["entry_px"] * d, t["stop_px"] * d, t["target_px"] * d
        risk = entry - stop
        floored = False
        if X.get("tgt"):
            tg, raw, floored = band(t, X["tgt"])
        tg_far = None
        if X.get("speed"):
            p, raw, _ = band(t, {"mode": "vix"})
            tg_far = max(raw, p)
        be_r = None
        if X.get("be"):
            o = X["be"]
            pts = float(o["atr"]) * atr5_at(t["entry_t"]) if "atr" in o else float(o["pts"])
            be_r = max(1.0, pts / risk) if o.get("how", "max") == "max" else min(1.0, pts / risk)
        tc_x = None
        if X.get("tc"):
            o = X["tc"]
            xa = float(o["k"]) * atr5_at(t["entry_t"]) / risk
            x0 = float(LIVE["t_check"]["x"])
            tc_x = xa if o.get("how", "atr") == "atr" else max(x0, xa) if o["how"] == "max" else min(x0, xa)
        r = manage(X, BX, fill, d, entry, stop, tg, int(B.day[fill]), risk, tg_far=tg_far, be_r=be_r, tc_x=tc_x)
        kind, pts, worst, mfe, kx = r
        row = c["intel"].get(int(t["entry_t"]), {})
        m = float(mfn(t, row)) if mfn else 1.0
        out.append({"day": t["day"], "entry_t": int(t["entry_t"]), "exit_t": int(B.t[kx]) + B.secs, "dir": d, "exit": kind,
                    "risk": round(risk, 2), "tgt": round(tg - entry, 2), "pts": round(pts, 4), "w1": round(worst, 4),
                    "legs": [(1.0, pts)], "mfe": round(mfe, 3), "tf": t["tf"], "m": m, "floored": floored,
                    "live_exit": t.get("exit"), "live_pts": round((t["pnl"] + COMM * t["qty"]) / (PV * t["qty"]), 4)})
    return out


# ================================================================================================ sizing
def wk_mult(U):
    """The weekly stop multiplier of each unit (2 STOP exits earlier in the ISO week -> 0.5), in entry order."""
    done, out = [], {}
    for u in sorted(U, key=lambda u: u["entry_t"]):
        wk = lit.iso_week(u["day"])
        ws = sum(1 for o in done if lit.iso_week(o["day"]) == wk and o["exit_t"] <= u["entry_t"] and o["exit"] == "STOP")
        out[u["entry_t"]] = LIVE["wk_stop"][1] if LIVE.get("wk_stop") and ws >= LIVE["wk_stop"][0] else 1.0
        done.append(u)
    return out


def lit_size(U):
    """The LIT size rule (as run lit_live) x the tilt m (one rounding with the weekly stop; a size-up risks <= $990)."""
    W = wk_mult(U)
    out = []
    for u in sorted(U, key=lambda u: u["entry_t"]):
        q0 = lit.qty_for(u["risk"])
        wm = W[u["entry_t"]]
        mm = wm * float(u.get("m", 1.0))
        q = q0 if abs(mm - 1.0) < 1e-9 else max(1, int(q0 * mm + 1e-9))
        if mm > 1.0 + 1e-9:
            qw = q0 if wm >= 1 else max(1, int(q0 * wm + 1e-9))
            q = min(q, 40, max(qw, int(990.0 / ((u["risk"] + SLIP) * PV + COMM))))
        pnl = u["pts"] * PV * q - COMM * q
        low = min(0.0, u["w1"] * PV * q - COMM * q, pnl)
        out.append({**u, "qty": q, "pnl": round(pnl, 2), "low": round(low, 2), "r": round(pnl / (u["risk"] * PV * q), 3),
                    "risk_pts": u["risk"], "risk_usd": round(u["risk"] * PV * q, 2), "half": wm < 1, "mult": mm,
                    "trigger": "LIT-%dm" % u["tf"], "mae": None, "bars_held": None, "regime": ""})
    return out


def run_eval_m(seq, by, horizon=20, keep=None, cfg=None):
    """lit_adv_manage.run_eval exactly (engine/sizing.lit_qty, $1.90) + the tilt as the engine's idm_m (two_week applies it
    before the live caps) + scale-in adds (lit_big_ideas.trade_pnl = engine/sizing.scale_in_qty)."""
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
            tr = {"risk_pts": t["risk"], "tgt_pts": t["tgt"], "size_mult": 1.0}
            m = float(t.get("m", 1.0))
            if abs(m - 1.0) > 1e-9:
                tr.update(idm_m=m, idm_cap=None, wk_m=1.0)
            q = SZ.lit_qty(m0, tr, cfg, room=st["room"], state=st, learning=None)["qty"] if m0 else 0
            if q <= 0:
                continue
            pnl, low, tot = BI.trade_pnl(t, q, q, st)
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


A.run_eval = run_eval_m


def eval_path(U, cfg=None):
    if cfg is not None:
        A.CFG, keep = cfg, A.CFG
    try:
        U26 = [u for u in U if u["day"] >= "2026"]
        return {s: R.eval_path(U26, s) for s in ("H1", "H2")}
    finally:
        if cfg is not None:
            A.CFG = keep


def funded_by(U):
    """uprisk units per session: risk / tgt / pts / w1 + the weekly stop (size_mult) + the tilt (idm_m, idm_cap $1,500)."""
    c = ctx()
    W = wk_mult(U)
    by = collections.defaultdict(list)
    for u in sorted(U, key=lambda u: u["entry_t"]):
        x = {"day": u["day"], "risk": u["risk"], "risk_pts": u["risk"], "tgt": u["tgt"], "tgt_pts": u["tgt"], "pts": u["pts"],
             "w1": u["w1"], "size_mult": W[u["entry_t"]]}
        m = float(u.get("m", 1.0))
        if abs(m - 1.0) > 1e-9:
            x.update(idm_m=m, idm_cap=1500.0, wk_m=W[u["entry_t"]])
        by[u["day"]].append(x)
    return [by.get(d, []) for d in c["S_up"]]


_FP = {}


def funded(U, spans=("H1", "H2", "REF"), n=None):
    c = ctx()
    n = n or N_FUND
    BY = funded_by(U)
    o = {}
    for sp in spans:
        if (sp, n) not in _FP:
            _FP[(sp, n)] = UP.mc_paths(c["S_up"], sp, n)
        r = UP.funded_mc(BY, _FP[(sp, n)], "builder50k", FUND_LIVE)
        o[sp] = {k: r[k] for k in ("per_month", "paid_6m", "loss_6m", "first_med", "any_pay", "payouts", "max_risk", "trades_6m")}
    return o


# ================================================================================================ scoring
def lit_stats(L):
    return {s: R.lit_stats(L, s) for s in ("H1", "H2", "2021-25")}


def evaluate(X=None, T=None, mfn=None, fund=False, eval_cfg=None, U=None):
    U = U if U is not None else trades(X, T, mfn)
    L = lit_size(U)
    o = {"X": X or {}, "lit": lit_stats(L), "eval": eval_path(U, eval_cfg)}
    if fund:
        o["fund"] = funded(U)
    o["floored"] = sum(1 for u in U if u.get("floored") and u["day"] >= "2026")
    return o, U, L


def changed(L, base_L):
    bm = {l["entry_t"]: l for l in base_L}
    out = {}
    for sp in ("H1", "H2", "2021-25"):
        a, z = SPANS[sp]
        n = sum(1 for l in L if a <= l["day"] <= z and (l["entry_t"] not in bm or abs(l["pnl"] - bm[l["entry_t"]]["pnl"]) > 0.5))
        n += sum(1 for l in base_L if a <= l["day"] <= z and l["entry_t"] not in {x["entry_t"] for x in L})
        out[sp] = n
    return out


def placebo(U, base_L, n=200, seed=11, fund_n=0):
    """The tilt's multipliers shuffled across each span's trades (H1 / H2 / 2021-25 apart): share of draws with more LIT-size
    $ than the real tilt, per span (low = the real tilt beats chance)."""
    L = lit_size(U)
    real = {sp: sum(l["pnl"] for l in L if SPANS[sp][0] <= l["day"] <= SPANS[sp][1]) for sp in SPANS}
    rng = np.random.default_rng(seed)
    beat = collections.Counter()
    for _ in range(n):
        V = [dict(u) for u in U]
        for sp, (a, z) in SPANS.items():
            ix = [i for i, u in enumerate(V) if a <= u["day"] <= z]
            ms = [V[i]["m"] for i in ix]
            rng.shuffle(ms)
            for i, m in zip(ix, ms):
                V[i]["m"] = m
        LL = lit_size(V)
        for sp, (a, z) in SPANS.items():
            if sum(l["pnl"] for l in LL if a <= l["day"] <= z) >= real[sp]:
                beat[sp] += 1
    return {sp: round(beat[sp] / n, 3) for sp in SPANS}


def short(o, base=None):
    """Headline per variant: LIT size (H1 / H2 / 2021-25) and eval path (H1 / H2), + funded, + deltas vs base."""
    s = {"lit": {sp: {k: o["lit"][sp][k] for k in ("n", "tpw", "wk2", "win", "pf", "net", "per_month", "dd", "p10", "f10")}
                 for sp in o["lit"]},
         "eval": {sp: {k: o["eval"][sp][k] for k in ("n", "tpw", "pf", "net", "per_month", "dd", "p10", "f10", "dec10", "p15",
                                                     "f15", "slow_pass", "pass_med", "b2b")} | {"mc_p10": o["eval"][sp]["mc"]["p10"],
                                                                                                "mc_f10": o["eval"][sp]["mc"]["f10"]}
                  for sp in o["eval"]}}
    if "fund" in o:
        s["fund"] = o["fund"]
    if base is not None:
        s["d_lit"] = {sp: o["lit"][sp]["net"] - base["lit"][sp]["net"] for sp in o["lit"]}
        s["d_eval"] = {sp: o["eval"][sp]["net"] - base["eval"][sp]["net"] for sp in o["eval"]}
        s["d_p10"] = {sp: round(o["eval"][sp]["p10"] - base["eval"][sp]["p10"], 1) for sp in o["eval"]}
        s["d_f10"] = {sp: round(o["eval"][sp]["f10"] - base["eval"][sp]["f10"], 1) for sp in o["eval"]}
        if "fund" in o and "fund" in base:
            s["d_fund"] = {sp: o["fund"][sp]["per_month"] - base["fund"][sp]["per_month"] for sp in o["fund"]}
    for k in ("floored", "chg", "placebo", "info"):
        if k in o:
            s[k] = o[k]
    return s


def gate(s):
    """The LIT gate: more net $ in H1 AND H2 on the live eval path and at the LIT size, no rise in 2-week fails (H1 / H2),
    2+ trades a week in both halves (eval path n per week)."""
    if "d_lit" not in s:
        return False
    ok = all(s["d_lit"][h] > 0 and s["d_eval"][h] > 0 and s["d_f10"][h] <= 0 for h in ("H1", "H2"))
    ok = ok and all(s["lit"][h]["tpw"] >= 2.0 for h in ("H1", "H2"))
    return ok


def line(nm, s):
    L, E = s["lit"], s["eval"]
    f = lambda x: f"PF {x['pf']} {x['net']:+,} (${x['per_month']:,}/mo)"
    t = (f"{nm[:34]:34s} LIT H1[{f(L['H1'])}] H2[{f(L['H2'])}] 21-25[{f(L['2021-25'])}] {L['H1']['tpw']}/{L['H2']['tpw']}/wk | "
         f"EVAL H1[{f(E['H1'])} 2w {E['H1']['p10']}/{E['H1']['f10']}] H2[{f(E['H2'])} 2w {E['H2']['p10']}/{E['H2']['f10']}]")
    if "fund" in s:
        t += f" | FUND $/mo {s['fund']['H1']['per_month']}/{s['fund']['H2']['per_month']}/{s['fund']['REF']['per_month']}"
    if "d_lit" in s:
        t += f" | d LIT {s['d_lit']['H1']:+,}/{s['d_lit']['H2']:+,}/{s['d_lit']['2021-25']:+,} d EVAL {s['d_eval']['H1']:+,}/{s['d_eval']['H2']:+,}"
        if "d_fund" in s:
            t += f" d FUND {s['d_fund']['H1']:+}/{s['d_fund']['H2']:+}/{s['d_fund']['REF']:+}"
        t += "  GATE" if gate(s) else ""
    return t


# ================================================================================================ tilts (features at the fill)
def _num(v, dflt=np.nan):
    try:
        return float(v) if v is not None else dflt
    except (TypeError, ValueError):
        return dflt


def h1_cut(key, q):
    """Quantile q of feature `key` over the 2026 H1 live trades (cut points are picked on H1 only)."""
    c = ctx()
    v = [_num(c["intel"][int(t["entry_t"])].get(key)) for t in c["T"] if "2026-01-01" <= t["day"] <= "2026-06-30"
         and int(t["entry_t"]) in c["intel"]]
    v = [x for x in v if x == x]
    return float(np.quantile(v, q))


_Z = {}


def zstats(keys):
    c = ctx()
    for k in keys:
        if k not in _Z:
            v = np.array([_num(c["intel"][int(t["entry_t"])].get(k)) for t in c["T"]
                          if "2026-01-01" <= t["day"] <= "2026-06-30" and int(t["entry_t"]) in c["intel"]], float)
            v = v[v == v]
            _Z[k] = (float(v.mean()), float(v.std() or 1.0))
    return _Z


QUAL = (("depth_atr", 1), ("disp", 1), ("idm_n", 1), ("n_lvls", 1), ("major", 1), ("since_open", -1), ("close_back", 1),
        ("wick", 1))


def quality(row):
    """Pre-registered LIT A+ score (signs from the LIT texts, not fitted): deeper sweep, bigger displacement, more
    inducements, more levels, a major level, earlier in the killzone, closed back inside, a longer rejection wick.
    Each fact z-scored on 2026 H1, equal weights."""
    Z = zstats([k for k, _ in QUAL])
    s = 0.0
    for k, sg in QUAL:
        v = row.get(k)
        v = 1.0 if v is True else 0.0 if v is False else _num(v)
        if v != v:
            continue
        mu, sd = Z[k]
        s += sg * (v - mu) / sd
    return s


def qual_cuts():
    c = ctx()
    v = [quality(c["intel"][int(t["entry_t"])]) for t in c["T"] if "2026-01-01" <= t["day"] <= "2026-06-30"
         and int(t["entry_t"]) in c["intel"]]
    return float(np.quantile(v, 1 / 3)), float(np.quantile(v, 2 / 3))


def tilt_fns():
    """name -> (mfn, description). Every cut point is fixed on 2026 H1."""
    lo_q, hi_q = qual_cuts()
    F_ = collections.OrderedDict()
    F_["q_abc_15_05"] = (lambda t, r: 1.5 if quality(r) >= hi_q else 0.5 if quality(r) <= lo_q else 1.0,
                         "A+ score: top third x1.5, bottom third x0.5")
    F_["q_abc_125_075"] = (lambda t, r: 1.25 if quality(r) >= hi_q else 0.75 if quality(r) <= lo_q else 1.0,
                           "A+ score: top third x1.25, bottom third x0.75")
    F_["q_c_only_05"] = (lambda t, r: 0.5 if quality(r) <= lo_q else 1.0, "A+ score: bottom third x0.5 only")
    F_["q_a_only_15"] = (lambda t, r: 1.5 if quality(r) >= hi_q else 1.0, "A+ score: top third x1.5 only")
    F_["idm2_15_075"] = (lambda t, r: 1.5 if _num(r.get("idm_n"), 0) >= 2 else 0.75, "2+ inducements x1.5, else x0.75")
    F_["kz_first60_125"] = (lambda t, r: 1.25 if _num(r.get("since_open"), 999) <= 60 else 0.75,
                            "first 60 min of the London / NY open x1.25, later x0.75")
    F_["kz_late_05"] = (lambda t, r: 0.5 if _num(r.get("since_open"), 0) > 180 else 1.0, "more than 3 h after the open x0.5")
    F_["h4draw_125"] = (lambda t, r: 1.25 if _num(r.get("h4_draw"), 0) > 0 else 0.75 if _num(r.get("h4_draw"), 0) < 0 else 1.0,
                        "4H draw with the trade x1.25, against x0.75")
    rr_hi = h1_cut("rr", 2 / 3)
    F_["far_tgt_075"] = (lambda t, r: 0.75 if _num(r.get("rr"), 0) >= rr_hi else 1.0, f"target >= {rr_hi:.1f}R (top third) x0.75")
    F_["near_tgt_125"] = (lambda t, r: 1.25 if _num(r.get("rr"), 99) <= h1_cut("rr", 1 / 3) else 1.0, "target in the nearest third x1.25")
    F_["atrreg_hi_125"] = (lambda t, r: 1.25 if _num(r.get("atr_regime"), 0) >= h1_cut("atr_regime", 2 / 3) else 1.0,
                           "busy tape (5m ATR / VIX move, top third) x1.25")
    F_["dayrng_hi_075"] = (lambda t, r: 0.75 if _num(r.get("day_rng"), 0) >= h1_cut("day_rng", 2 / 3) else 1.0,
                           "day already ranged a lot (top third, VIX moves) x0.75")
    F_["vix_hi_125"] = (lambda t, r: 1.25 if _num(r.get("vix"), 0) >= h1_cut("vix", 2 / 3) else 1.0, "VIX top third x1.25")
    return F_


def dow_tilt():
    """Data-mined control: the weekday with the most H1 R x1.5, the least x0.5 (picked on H1, checked on H2)."""
    c = ctx()
    S = collections.defaultdict(float)
    U = trades({})
    for u in U:
        if "2026-01-01" <= u["day"] <= "2026-06-30":
            S[c["intel"][u["entry_t"]]["weekday"]] += u["pts"] / u["risk"]
    best, worst = max(S, key=S.get), min(S, key=S.get)
    return (lambda t, r: 1.5 if r.get("weekday") == best else 0.5 if r.get("weekday") == worst else 1.0), \
        f"H1-mined weekday: {best} x1.5, {worst} x0.5 (H1 R by weekday {dict((k, round(v, 1)) for k, v in S.items())})"


def hour_tilt():
    c = ctx()
    S = collections.defaultdict(float)
    for u in trades({}):
        if "2026-01-01" <= u["day"] <= "2026-06-30":
            S[c["intel"][u["entry_t"]]["session"]] += u["pts"] / u["risk"]
    best, worst = max(S, key=S.get), min(S, key=S.get)
    return (lambda t, r: 1.5 if r.get("session") == best else 0.5 if r.get("session") == worst else 1.0), \
        f"H1-mined session: {best} x1.5, {worst} x0.5 (H1 R by session {dict((k, round(v, 1)) for k, v in S.items())})"


def news_tilt():
    return (lambda t, r: 0.5 if r.get("news_day") else 1.0), "scheduled high-impact US release day x0.5"


# ================================================================================================ variants
def target_variants():
    V = collections.OrderedDict()
    for n in (5, 10, 20):
        for k in (0.5, 0.6, 0.75, 1.0):
            V[f"adr{n}_k{k}"] = {"tgt": {"mode": "adr", "n": n, "k": k}}
    for mode in ("bmax", "bmin", "bmean"):
        for n in (10, 20):
            for k in (0.6, 0.75):
                V[f"{mode}_adr{n}_k{k}"] = {"tgt": {"mode": mode, "n": n, "k": k}}
    for k in (0.75, 1.0, 1.25):
        V[f"entry_k{k}"] = {"tgt": {"mode": "entry", "k": k}}
    for k in (0.75, 1.0, 1.25):
        V[f"mid_k{k}"] = {"tgt": {"mode": "mid", "k": k}}
    for k in (1.0, 1.25, 1.5, 2.0):
        V[f"time_k{k}"] = {"tgt": {"mode": "time", "k": k}}
    return V


def be_variants():
    V = collections.OrderedDict()
    for k in (1.5, 2.0, 3.0, 4.0):
        V[f"be_atr{k}_max"] = {"be": {"atr": k, "how": "max"}}
        V[f"be_atr{k}_min"] = {"be": {"atr": k, "how": "min"}}
    for p in (15, 20, 30):
        V[f"be_pts{p}_max"] = {"be": {"pts": p, "how": "max"}}
    for p in (20, 30, 40):
        V[f"be_pts{p}_min"] = {"be": {"pts": p, "how": "min"}}
    return V


def tc_variants():
    V = collections.OrderedDict()
    for k in (0.5, 0.75, 1.0, 1.5, 2.0):
        for how in ("atr", "max", "min"):
            V[f"tc_atr{k}_{how}"] = {"tc": {"k": k, "how": how}}
    return V


def dyn_variants():
    V = collections.OrderedDict()
    for r in (1.75, 2.0, 2.5):
        for mn in (10, 15, 20):
            V[f"speed_r{r}_m{mn}"] = {"speed": {"r": r, "min": mn}}
    for r in (1.5, 2.0, 3.0):
        for mn in (15, 30, 60):
            V[f"speed_r{r}_m{mn}"] = {"speed": {"r": r, "min": mn}}
    for mn in (60, 120, 180):
        for r in (0.5, 1.0):
            for rr in (2.0, 3.0, 4.0):
                V[f"slow_m{mn}_r{r}_rr{rr}"] = {"slow": {"min": mn, "r": r, "rr": rr}}
    for at in (660, 720, 780, 840):
        for rr in (2.0, 3.0, 4.0):
            V[f"late_{at // 60:02d}{at % 60:02d}_rr{rr}"] = {"late": {"at": at, "rr": rr}}
    return V


def catchup_trades(loose, days=(3, 4), m=0.5, need=2):
    """Live trades + on Thu/Fri (days) of a week with < need trades so far, the looser run's trade of that day (when the live
    run had none) at m x size."""
    c = ctx()
    T = c["T"]
    TL = F.run({**LIVE, **loose})
    by_l = {}
    for t in TL:
        by_l.setdefault(t["day"], t)
    live_days = {t["day"] for t in T}
    import datetime as dt
    wk = collections.Counter()
    out = []
    added = 0
    allT = sorted(T, key=lambda t: t["entry_t"])
    ix = 0
    for d in F.SESS:
        w = lit.iso_week(d)
        while ix < len(allT) and allT[ix]["day"] == d:
            out.append(dict(allT[ix], _m=1.0)); wk[w] += 1; ix += 1
        if d in live_days:
            continue
        wd = dt.date.fromisoformat(d).weekday()
        if wd in days and wk[w] < need and d in by_l:
            out.append(dict(by_l[d], _m=m)); wk[w] += 1; added += 1
    return out, added


def catchup_variants():
    V = collections.OrderedDict()
    looses = {"disp06": {"disp": 0.6}, "depth035": {"depth": 0.35}, "disp06_depth035": {"disp": 0.6, "depth": 0.35},
              "noidm": {"idm_a": None}, "minrr12": {"min_rr": 1.2}}
    for nm, lo in looses.items():
        for m in (0.5, 1.0):
            V[f"cu_{nm}_thufri_x{m}"] = {"loose": lo, "days": (3, 4), "m": m}
        V[f"cu_{nm}_wedfri_x0.5"] = {"loose": lo, "days": (2, 3, 4), "m": 0.5}
    return V


def reentry_units(U, W=30, m=1.0, min_rr=1.5, after=("CUT_T15",)):
    """Re-entry after a 15-minute cut (2026, 1m): from the cut bar on, while the sweep extreme (the original stop) holds, the
    first 1m CISD after the lowest low since the cut (engine/lit._cisd_level) within W bars -> enter at the next 1m open +
    1 tick, same stop, same target level (needs >= min_rr R from the new fill), managed like a live trade (15-minute check,
    BE at 1R + 1.25, 15:55). Returns the extra units (m = size multiplier)."""
    c = ctx()
    BX = c[60]
    B = BX.B
    byt = {int(t["entry_t"]): t for t in c["T"]}
    out = []
    for u in U:
        if u["exit"] not in after or u["tf"] != 1:
            continue
        t = byt[u["entry_t"]]
        d = u["dir"]
        hi_d, lo_d, c_d, o_d = B.dirs(d)
        stop, tg = t["stop_px"] * d, t["target_px"] * d
        kc = int(np.searchsorted(B.t, u["exit_t"] - 60))          # the bar the cut filled at (its open)
        s_day = int(B.day[kc])
        fill = None
        for k in range(kc, min(B.n - 1, kc + W)):
            if B.day[k] != s_day or B.mod[k] >= LIVE["window"][0][1] or B.mod[k] >= LIVE["flat_mod"]:
                break
            if lo_d[k] <= stop:
                break
            lowk = kc + int(np.argmin(lo_d[kc:k + 1]))
            cz = lit._cisd_level(c_d, o_d, lowk)
            if cz is not None and k > lowk and c_d[k] > cz[0] and B.day[k + 1] == s_day:
                fill = k + 1
                break
        if fill is None:
            continue
        entry = float(o_d[fill]) + SLIP
        risk = entry - stop
        if risk < LIVE["min_stop"] or risk > LIVE["max_stop"] + 8 or tg - entry < min_rr * risk:
            continue
        r = manage({}, BX, fill, d, entry, stop, tg, s_day, risk)
        kind, pts, worst, mfe, kx = r
        out.append({"day": u["day"], "entry_t": int(B.t[fill]), "exit_t": int(B.t[kx]) + 60, "dir": d, "exit": kind,
                    "risk": round(risk, 2), "tgt": round(tg - entry, 2), "pts": round(pts, 4), "w1": round(worst, 4),
                    "legs": [(1.0, pts)], "mfe": round(mfe, 3), "tf": 1, "m": m, "floored": False, "live_exit": None,
                    "live_pts": None, "reentry": True})
    return out


def reentry_variants():
    V = collections.OrderedDict()
    for W in (15, 30, 60):
        for m in (0.5, 1.0):
            V[f"re_cut_w{W}_x{m}"] = {"W": W, "m": m, "after": ("CUT_T15",)}
    for W in (30, 60):
        V[f"re_cut_be_w{W}_x0.5"] = {"W": W, "m": 0.5, "after": ("CUT_T15", "BE")}
    return V


def scored_family(fam, V, base, base_L, res, fund=True):
    for nm, X in V.items():
        key = f"{fam}:{nm}"
        if key in res:
            print(line(key, res[key]), flush=True)
            continue
        o, U, L = evaluate(X, fund=fund)
        o["chg"] = changed(L, base_L)
        s = short(o, base)
        res[key] = s
        print(line(key, s), flush=True)


def grid(fams=None):
    res = json.load(open(OUT)) if os.path.exists(OUT) else {}
    t0 = time.time()
    base, U0, L0 = evaluate({}, fund=True)
    bs = short(base)
    res["base"] = bs
    print(line("base", bs), flush=True)
    fams = fams or ["tgt", "be", "dyn", "tilt", "catchup", "scale", "evalknobs"]

    def dump():
        json.dump(res, open(OUT, "w"), indent=1, default=float)

    if "tgt" in fams:
        scored_family("tgt", target_variants(), base, L0, res); dump()
    if "be" in fams:
        scored_family("be", be_variants(), base, L0, res); dump()
    if "dyn" in fams:
        scored_family("dyn", dyn_variants(), base, L0, res); dump()
    if "tc" in fams:
        scored_family("tc", tc_variants(), base, L0, res); dump()
    if "tilt" in fams:
        TF = tilt_fns()
        dmf, dmd = dow_tilt()
        hmf, hmd = hour_tilt()
        nmf, nmd = news_tilt()
        TF["dow_mined"] = (dmf, dmd)
        TF["session_mined"] = (hmf, hmd)
        TF["news_day_05"] = (nmf, nmd)
        for nm, (fn, desc) in TF.items():
            key = f"tilt:{nm}"
            if key in res and not os.environ.get("EDGE_REDO"):
                print(line(key, res[key]), flush=True)
                continue
            U = trades({}, mfn=fn)
            o, _, L = evaluate(U=U, fund=True)
            o["chg"] = changed(L, L0)
            o["placebo"] = placebo(U, L0)
            n26 = [u for u in U if u["day"] >= "2026"]
            o["info"] = {"desc": desc, "up_2026": sum(1 for u in n26 if u["m"] > 1), "down_2026": sum(1 for u in n26 if u["m"] < 1)}
            s = short(o, base)
            res[key] = s
            print(line(key, s), "| placebo", o["placebo"], "|", desc, flush=True)
            dump()
    if "catchup" in fams:
        for nm, v in catchup_variants().items():
            key = f"catchup:{nm}"
            if key in res:
                print(line(key, res[key]), flush=True)
                continue
            T, added = catchup_trades(v["loose"], v["days"], v["m"])
            U = trades({}, T=T, mfn=lambda t, r: t.get("_m", 1.0))
            o, _, L = evaluate(U=U, fund=True)
            o["chg"] = changed(L, L0)
            o["info"] = {"added": added, "added_2026": sum(1 for t in T if t.get("_m", 1.0) != 1.0 and t["day"] >= "2026")
                         if v["m"] != 1.0 else None}
            s = short(o, base)
            res[key] = s
            print(line(key, s), "| added", added, flush=True)
            dump()
    if "reentry" in fams:
        for nm, v in reentry_variants().items():
            key = f"reentry:{nm}"
            if key in res:
                print(line(key, res[key]), flush=True)
                continue
            U = trades({})
            X = reentry_units(U, v["W"], v["m"], after=v["after"])
            o, _, L = evaluate(U=U + X, fund=True)
            o["chg"] = changed(L, L0)
            o["info"] = {"added_2026": len(X), "added_h1": sum(1 for x in X if x["day"] <= "2026-06-30"),
                         "added_r": round(sum(x["pts"] / x["risk"] for x in X), 2),
                         "exits": dict(collections.Counter(x["exit"] for x in X))}
            s = short(o, base)
            res[key] = s
            print(line(key, s), "|", o["info"], flush=True)
            dump()
    if "second" in fams:
        for nm, sc in (("any_x0.5", {"after": None, "m": 0.5}), ("any_x1.0", {"after": None, "m": 1.0}),
                       ("stop_x0.5", {"after": ["STOP", "CUT_T15"], "m": 0.5}), ("stop_x0.25", {"after": ["STOP", "CUT_T15"], "m": 0.25}),
                       ("win_be_x0.5", {"after": ["TARGET", "BE", "EOD"], "m": 0.5}), ("any_x0.5_cool30", {"after": None, "m": 0.5, "cool": 30}),
                       ("any_x0.5_newlvl", {"after": None, "m": 0.5, "new_level": True})):
            key = f"second:{nm}"
            if key in res:
                print(line(key, res[key]), flush=True)
                continue
            T = F.run({**LIVE, "max_per_day": 2, "second": {"side": "any", "cool": 0, **sc}})
            U = trades({}, T=T, mfn=lambda t, r: float(t.get("x_m", 1.0)))
            o, _, L = evaluate(U=U, fund=True)
            o["chg"] = changed(L, L0)
            n2 = collections.Counter(t["day"] for t in T)
            o["info"] = {"second_2026": sum(1 for d, c in n2.items() if c > 1 and d >= "2026"),
                         "second_h2": sum(1 for d, c in n2.items() if c > 1 and d >= "2026-07")}
            s = short(o, base)
            res[key] = s
            print(line(key, s), "|", o["info"], flush=True)
            dump()
    if "tp" in fams:
        tp_family(res, bs, dump)
    if "ebank" in fams:
        ebank_family(res, bs, dump)
    if "scale" in fams:
        from tools import lit_adopt_combo as AC
        for nm, si in (("scale_in_live", SCALE), ("scale_in_pb0.35", {**SCALE, "pb": 0.35}), ("scale_in_pb0.15", {**SCALE, "pb": 0.15}),
                       ("scale_in_f0.5", {**SCALE, "f": 0.5})):
            key = f"scale:{nm}"
            if key in res:
                print(line(key, res[key]), flush=True)
                continue
            T = F.run({**LIVE, "scale_in": si})
            Ue = [dict(u, add_f=si["f"]) if u.get("adds") else u for u in AC.units(T)]
            Ld = [{**t, "risk": t["risk_pts"], "pts": (t["pnl"] + COMM * t["qty"]) / (PV * t["qty"])} for t in T]
            o = {"X": {"scale_in": si}, "lit": lit_stats(Ld),
                 "eval": {s: R.eval_path(Ue, s) for s in ("H1", "H2")}}
            o["info"] = {"adds_2026": sum(1 for t in T if t.get("adds") and t["day"] >= "2026"),
                         "adds_h2": sum(1 for t in T if t.get("adds") and t["day"] >= "2026-07")}
            s = short(o, base)
            res[key] = s
            print(line(key, s), "| adds", o["info"], flush=True)
            dump()
    if "evalknobs" in fams:
        for nm, ch in (("tw_until999", {"two_week_until": 999}), ("tw_until15", {"two_week_until": 15}),
                       ("room_f0.7", {"room_f": 0.7}), ("room_f0.9", {"room_f": 0.9}), ("room_f1.0", {"room_f": 1.0}),
                       ("tw_until999_room_f0.7", {"two_week_until": 999, "room_f": 0.7}),
                       ("after_eval", {"after_mode": "eval"}), ("need_buf1.2", {"need_buf": 1.2}), ("need_buf0.8", {"need_buf": 0.8}),
                       ("rf0.7_s4_0.9", {"room_f": 0.7, "press_at": 4, "press_room": 0.9}),
                       ("rf0.9_s4_0.7", {"room_f": 0.9, "press_at": 4, "press_room": 0.7}),
                       ("rf0.6_s3_0.8", {"room_f": 0.6, "press_at": 3, "press_room": 0.8}),
                       ("rf1.0_s2_0.8", {"room_f": 1.0, "press_at": 2, "press_room": 0.8}),
                       ("press6_x1.25", {"press_at": 6, "press_mult": 1.25}),
                       ("press6_x0.75", {"press_at": 6, "press_mult": 0.75})):
            key = f"evalknobs:{nm}"
            if key in res:
                print(line(key, res[key]), flush=True)
                continue
            cfg = copy.deepcopy(A.CFG)
            for k, v in ch.items():
                if k in ("room_f", "need_buf", "press_at", "press_room", "press_mult"):
                    cfg["two_week"][k] = v
                else:
                    cfg[k] = v
            A._MC.clear()
            o, _, L = evaluate({}, eval_cfg=cfg)
            A._MC.clear()
            s = short(o, base)
            res[key] = s
            print(line(key, s), flush=True)
            dump()
    dump()
    json.dump({k: {kk: v[kk] for kk in v if kk in ("lit", "eval", "fund", "d_lit", "d_eval", "d_p10", "d_f10", "d_fund", "chg",
                                                    "placebo", "info", "floored")} | {"gate": gate(v)}
               for k, v in res.items()}, open(OUT_S, "w"), indent=0, separators=(",", ":"), default=float)
    print(f"done in {time.time() - t0:.0f}s -> {OUT}", flush=True)
    return res


def merge():
    """research/lit/edge_grid*.json (one per process) -> edge_grid.json + the committed headline file."""
    import glob
    res = {}
    for p in sorted(glob.glob(os.path.join(ROOT, "research", "lit", "edge_grid*.json"))):
        res.update(json.load(open(p)))
    json.dump(res, open(os.path.join(ROOT, "research", "lit", "edge_grid.json"), "w"), indent=1, default=float)
    json.dump({k: {kk: v[kk] for kk in v if kk in ("lit", "eval", "fund", "d_lit", "d_eval", "d_p10", "d_f10", "d_fund", "chg",
                                                    "placebo", "info", "floored")} | {"gate": gate(v)}
               for k, v in res.items()}, open(OUT_S, "w"), indent=0, separators=(",", ":"), default=float)
    print(len(res), "variants ->", OUT_S)
    return res


# ================================================================================================ the cap as a take-profit
RGRID = [round(1.0 + 0.25 * i, 2) for i in range(29)]          # 1.0R .. 8.0R


def outcome_table(U):
    """Per live unit: the trade re-walked with its target at r R (every r of RGRID below the live target) -> (tgt pts, pts,
    worst pts, exit). Nearest-below lookup = a take-profit that never pays more than asked."""
    c = ctx()
    byt = {int(t["entry_t"]): t for t in c["T"]}
    tab = {}
    for u in U:
        t = byt[u["entry_t"]]
        BX = c[60] if t["tf"] == 1 else c[300]
        B = BX.B
        d = t["dir"]
        fill = int(np.searchsorted(B.t, t["entry_t"]))
        entry, stop, tg = t["entry_px"] * d, t["stop_px"] * d, t["target_px"] * d
        risk = entry - stop
        rows = []
        for r in RGRID:
            if r * risk >= tg - entry - 1e-9:
                break
            kind, pts, worst, mfe, kx = manage({}, BX, fill, d, entry, stop, entry + r * risk, int(B.day[fill]), risk)
            rows.append((round(r * risk, 4), round(pts, 4), round(worst, 4), kind))
        rows.append((round(tg - entry, 4), u["pts"], u["w1"], u["exit"]))
        tab[u["entry_t"]] = rows
    return tab


def pick(rows, tp_pts):
    best = rows[0]
    for row in rows:
        if row[0] <= tp_pts + 1e-9:
            best = row
    return best


class FundedTP(UP.Funded):
    """The live funded account, but the winner cap ($ max_win) is a take-profit, not a size cut: micros by the live risk rule
    (60% of the room, <= pct_max_usd, x20/stop beyond 20 pts, hard caps), the target pulled in to the price where the trade
    pays max_win (never below min_r R: then the micros are cut so min_r R pays max_win; never beyond the live target)."""

    def qty(self, t, st):
        c = dict(self.cfg)
        cap = float(c.pop("tp_usd"))
        min_r = float(c.pop("tp_min_r", 1.0))
        c["max_win"] = None
        q = SZ.funded_qty(t, st, c, acct=self.A)
        rows = t["_tab"]
        if q <= 0:
            return q
        # 1 micro's win at min_r R
        w_min = min_r * t["risk"] * PV - COMM
        if w_min * q > cap:
            q = max(1, int(cap / w_min))
            if w_min > cap:
                return 0
        tp = (cap + COMM * q) / (PV * q)
        row = pick(rows, tp) if tp < t["tgt"] else rows[-1]
        t["pts"], t["w1"] = row[1], row[2]
        return q


def funded_tp(U, tab, cfg, spans=("H1", "H2", "REF"), n=None):
    c = ctx()
    n = n or N_FUND
    BY = funded_by(U)
    byt = collections.defaultdict(list)
    for u in sorted(U, key=lambda u: u["entry_t"]):
        byt[u["day"]].append(u)
    for k, dlist in enumerate(BY):
        if dlist:
            us = byt[dlist[0]["day"]]
            for x, u in zip(dlist, us):
                x["_tab"] = tab[u["entry_t"]]
    keep = UP.Funded
    UP.Funded = lambda plan, cfg_, ask=None: FundedTP(plan, cfg_, ask)
    try:
        o = {}
        for sp in spans:
            if (sp, n) not in _FP:
                _FP[(sp, n)] = UP.mc_paths(c["S_up"], sp, n)
            r = UP.funded_mc(BY, _FP[(sp, n)], "builder50k", cfg)
            o[sp] = {k: r[k] for k in ("per_month", "paid_6m", "loss_6m", "first_med", "any_pay", "payouts", "max_risk", "trades_6m")}
    finally:
        UP.Funded = keep
    return o


def run_eval_tp(seq, by, horizon=20, keep=None, cfg=None):
    """run_eval_m with the eval's "one winner passes" turned around: micros = the live caps (two_week sizing with a huge
    need buffer = the room / soft-daily-loss / 40-micro caps), the target pulled in to the price where the trade covers what
    is still needed to +$3,000 (never below tp_min_r R, never beyond the live target)."""
    cfg = cfg or A.CFG
    tgt, mll, dll, lockv = A.A50["target"], A.A50["mll"], A.A50["dll"], A.A50["lock"]
    min_r = float(cfg.get("_tp_min_r", 1.5))
    big = copy.deepcopy(cfg)
    big["two_week"]["need_buf"] = 50.0
    bal = peak = 0.0
    floor = -mll
    for kk, si in enumerate(seq[:horizon]):
        cum = 0.0
        for t in by[si]:
            if cum <= -dll:
                break
            st = {"profit": bal, "cum": cum, "room": bal + cum - floor, "session": kk + 1, "n_today": 0}
            m0 = lit.qty_for(t["risk"])
            tr = {"risk_pts": t["risk"], "tgt_pts": t["tgt"], "size_mult": 1.0}
            q = SZ.lit_qty(m0, tr, big, room=st["room"], state=st, learning=None)["qty"] if m0 else 0
            if q <= 0:
                continue
            need = tgt - bal - cum
            in_tw = kk + 1 <= int(cfg.get("two_week_until") or 10)
            if in_tw and need > 0:
                tp = max(min_r * t["risk"], (need + A.ECOMM * q) / (PV * q))
                row = pick(t["_tab"], tp) if tp < t["tgt"] else t["_tab"][-1]
                pts, w1 = row[1], row[2]
            else:
                q = SZ.lit_qty(m0, tr, cfg, room=st["room"], state=st, learning=None)["qty"]
                if q <= 0:
                    continue
                pts, w1 = t["pts"], t["w1"]
            pnl = pts * PV * q - A.ECOMM * q
            low = min(0.0, w1 * PV * q - A.ECOMM * q, pnl)
            if cum + low <= -dll:
                pnl = -dll - cum - SLIP * PV * q
                low = pnl
            rec = {**{k: t[k] for k in ("day", "entry_t", "exit_t", "dir", "exit", "risk", "tgt")}, "qty": q, "pnl": round(pnl, 2),
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


def ebank_family(res, base, dump):
    """Eval-only bank: on the eval account the target is banked at k R (not 8R); two_week then sizes for that nearer target
    (more micros, capped by the room / soft daily loss). The LIT size and the funded account keep the live target."""
    U = trades({})
    tab = outcome_table(U)
    for k in (3.0, 4.0, 5.0, 6.0):
        key = f"ebank:bank{k}R"
        if key in res:
            continue
        V = []
        for u in U:
            if u["day"] < "2026":
                continue
            rows = tab[u["entry_t"]]
            if u["tgt"] > k * u["risk"] + 1e-6:
                row = pick(rows, k * u["risk"])
                V.append(dict(u, tgt=row[0], pts=row[1], w1=row[2], exit=row[3], legs=[(1.0, row[1])]))
            else:
                V.append(u)
        A._MC.clear()
        ev = {s: R.eval_path(V, s) for s in ("H1", "H2")}
        A._MC.clear()
        s_ = {"eval": {sp: {kk: ev[sp][kk] for kk in ("n", "tpw", "pf", "net", "per_month", "dd", "p10", "f10", "dec10", "p15", "f15",
                                                     "slow_pass", "pass_med", "b2b")} | {"mc_p10": ev[sp]["mc"]["p10"], "mc_f10": ev[sp]["mc"]["f10"]}
                       for sp in ev}}
        s_["d_eval"] = {sp: ev[sp]["net"] - base["eval"][sp]["net"] for sp in ev}
        s_["d_p10"] = {sp: round(ev[sp]["p10"] - base["eval"][sp]["p10"], 1) for sp in ev}
        s_["d_f10"] = {sp: round(ev[sp]["f10"] - base["eval"][sp]["f10"], 1) for sp in ev}
        s_["info"] = {"bank_r": k, "trades_banked_2026": sum(1 for u in U if u["day"] >= "2026" and u["tgt"] > k * u["risk"] + 1e-6)}
        res[key] = s_
        print(key, {sp: (ev[sp]["net"], ev[sp]["p10"], ev[sp]["f10"], ev[sp]["mc"], ev[sp]["pass_med"]) for sp in ev}, s_["info"], flush=True)
        dump()


def tp_family(res, base, dump):
    U = trades({})
    tab = outcome_table(U)
    for nm, ch in (("tp2000_r1.0", {"tp_usd": 2000, "tp_min_r": 1.0}), ("tp2000_r1.5", {"tp_usd": 2000, "tp_min_r": 1.5}),
                   ("tp2000_r2.0", {"tp_usd": 2000, "tp_min_r": 2.0}), ("tp2000_r1.5_max1000", {"tp_usd": 2000, "tp_min_r": 1.5, "pct_max_usd": 1000}),
                   ("tp2000_r1.5_pct40", {"tp_usd": 2000, "tp_min_r": 1.5, "pct": 0.4}), ("tp1500_r1.5", {"tp_usd": 1500, "tp_min_r": 1.5})):
        key = f"tp:fund_{nm}"
        if key in res:
            print(key, res[key]["fund"], flush=True)
            continue
        f = funded_tp(U, tab, {**FUND_LIVE, **ch})
        res[key] = {"fund": f, "d_fund": {sp: f[sp]["per_month"] - base["fund"][sp]["per_month"] for sp in f}, "info": ch}
        print(key, f, res[key]["d_fund"], flush=True)
        dump()
    # eval: the room cap's micros with a take-profit at the need
    U26 = [dict(u, _tab=tab[u["entry_t"]]) for u in U if u["day"] >= "2026"]
    keep = A.run_eval
    for nm, mr in (("etp_r1.0", 1.0), ("etp_r1.5", 1.5), ("etp_r2.0", 2.0), ("etp_r3.0", 3.0)):
        key = f"tp:eval_{nm}"
        if key in res:
            continue
        cfg = copy.deepcopy(A.CFG); cfg["_tp_min_r"] = mr
        A.run_eval = lambda seq, by, horizon=20, keep_=None, cfg_=None, keep=None: run_eval_tp(seq, by, horizon, keep, cfg)
        A._MC.clear()
        try:
            ev = {s: R.eval_path(U26, s) for s in ("H1", "H2")}
        finally:
            A.run_eval = keep
            A._MC.clear()
        s_ = {"eval": {sp: {k: ev[sp][k] for k in ("n", "tpw", "pf", "net", "per_month", "dd", "p10", "f10", "dec10", "p15", "f15",
                                                    "slow_pass", "pass_med", "b2b")} | {"mc_p10": ev[sp]["mc"]["p10"], "mc_f10": ev[sp]["mc"]["f10"]}
                       for sp in ev}}
        s_["d_eval"] = {sp: ev[sp]["net"] - base["eval"][sp]["net"] for sp in ev}
        s_["d_p10"] = {sp: round(ev[sp]["p10"] - base["eval"][sp]["p10"], 1) for sp in ev}
        s_["d_f10"] = {sp: round(ev[sp]["f10"] - base["eval"][sp]["f10"], 1) for sp in ev}
        s_["info"] = {"tp_min_r": mr}
        res[key] = s_
        print(key, {sp: (ev[sp]["net"], ev[sp]["p10"], ev[sp]["f10"], ev[sp]["mc"]) for sp in ev}, flush=True)
        dump()


# ================================================================================================ check
def check():
    c = ctx()
    U = trades({})
    bad = [(u["day"], u["exit"], u["live_exit"], u["pts"], u["live_pts"]) for u in U
           if u["exit"] != u["live_exit"] or abs(u["pts"] - u["live_pts"]) > 0.01]
    L = lit_size(U)
    badq = [(l["day"], l["qty"], t["qty"]) for l, t in zip(L, sorted(c["T"], key=lambda t: t["entry_t"])) if l["qty"] != t["qty"]]
    # the band recomputed from the 18:00 open + VIX move == the live target (1m-CISD trades: target from the fill)
    dif = []
    for t in c["T"]:
        p, raw, fl = band(t, {"mode": "vix"})
        live = t["target_px"] * t["dir"]
        if abs(p - live) > 0.3:
            dif.append((t["day"], round(p * t["dir"], 2), t["target_px"], fl))
    U2 = trades({"tgt": {"mode": "vix"}})
    d2 = sum(1 for a, b in zip(U, U2) if abs(a["pts"] - b["pts"]) > 0.01)
    n_intel = sum(1 for t in c["T"] if int(t["entry_t"]) in c["intel"])
    print(f"live trades {len(U)} | exit/points mismatches {len(bad)} | size mismatches {len(badq)} | intel rows {n_intel}/{len(c['T'])}")
    print(f"band recompute != live target: {len(dif)} trades; re-managed with the recomputed band: {d2} trades differ")
    for x in dif[:10]:
        print("  band", x)
    for b in bad[:5]:
        print("  diff", b)
    print("2026 net", round(sum(l["pnl"] for l in L if l["day"] >= "2026")), "2021-25 net",
          round(sum(l["pnl"] for l in L if l["day"] < "2026")))
    return not bad and not badq


# ================================================================================================ save
SAVE = []          # see PICKS


SC = {"pb": 0.25, "f": 1.0, "rat_k": 1.0, "min_rk": 2.0, "n": 1}
PICKS = [   # run id, grid key, rl family, status, X (variant params)
    ("lit_edge_base", "base", "baseline", "info", {}),
    ("lit_edge_adr5_k1", "tgt:adr5_k1.0", "targets", "rejected", {"tgt": {"mode": "adr", "n": 5, "k": 1.0}}),
    ("lit_edge_adr20_k1", "tgt:adr20_k1.0", "targets", "rejected", {"tgt": {"mode": "adr", "n": 20, "k": 1.0}}),
    ("lit_edge_bmean_adr10_k06", "tgt:bmean_adr10_k0.6", "targets", "rejected", {"tgt": {"mode": "bmean", "n": 10, "k": 0.6}}),
    ("lit_edge_time_k15", "tgt:time_k1.5", "targets", "rejected", {"tgt": {"mode": "time", "k": 1.5}}),
    ("lit_edge_mid_k125", "tgt:mid_k1.25", "targets", "rejected", {"tgt": {"mode": "mid", "k": 1.25}}),
    ("lit_edge_be_atr3_min", "be:be_atr3.0_min", "management", "rejected", {"be": {"atr": 3.0, "how": "min"}}),
    ("lit_edge_be_pts20_max", "be:be_pts20_max", "management", "rejected", {"be": {"pts": 20, "how": "max"}}),
    ("lit_edge_speed_r2_m15", "dyn:speed_r2.0_m15", "targets", "promising", {"speed": {"r": 2.0, "min": 15}}),
    ("lit_edge_slow_m120_r1_rr3", "dyn:slow_m120_r1.0_rr3.0", "targets", "rejected", {"slow": {"min": 120, "r": 1.0, "rr": 3.0}}),
    ("lit_edge_late_1400_rr3", "dyn:late_1400_rr3.0", "targets", "promising", {"late": {"at": 840, "rr": 3.0}}),
    ("lit_edge_late_1400_rr4", "dyn:late_1400_rr4.0", "targets", "rejected", {"late": {"at": 840, "rr": 4.0}}),
    ("lit_edge_tc_atr075_min", "tc:tc_atr0.75_min", "management", "rejected", {"tc": {"k": 0.75, "how": "min"}}),
    ("lit_edge_tilt_aplus", "tilt:q_abc_15_05", "risk", "rejected", {}),
    ("lit_edge_tilt_idm2", "tilt:idm2_15_075", "risk", "rejected", {}),
    ("lit_edge_tilt_busy_tape", "tilt:atrreg_hi_125", "risk", "rejected", {}),
    ("lit_edge_tilt_kz_first60", "tilt:kz_first60_125", "risk", "rejected", {}),
    ("lit_edge_tilt_session_mined", "tilt:session_mined", "risk", "rejected", {}),
    ("lit_edge_catchup_disp06", "catchup:cu_disp06_thufri_x0.5", "sessions", "rejected", {}),
    ("lit_edge_reentry_cut_w30", "reentry:re_cut_w30_x1.0", "sessions", "rejected", {}),
    ("lit_edge_second_after_stop", "second:stop_x0.5", "sessions", "rejected", {"after": ["STOP", "CUT_T15"], "m": 0.5}),
    ("lit_edge_scale_in_now", "scale:scale_in_live", "management", "info", SC),
]


def save(picks):
    res = json.load(open(OUT))
    for rid, key, fam, st, X in picks:
        s = res[key]
        if key.startswith("tilt:"):
            TF = tilt_fns()
            TF["dow_mined"] = dow_tilt(); TF["session_mined"] = hour_tilt(); TF["news_day_05"] = news_tilt()
            U = trades({}, mfn=TF[key.split(":", 1)[1]][0])
        elif key.startswith("catchup:"):
            v = catchup_variants()[key.split(":", 1)[1]]
            T, _ = catchup_trades(v["loose"], v["days"], v["m"])
            U = trades({}, T=T, mfn=lambda t, r: t.get("_m", 1.0))
        elif key.startswith("reentry:"):
            v = reentry_variants()[key.split(":", 1)[1]]
            U = trades({})
            U = U + reentry_units(U, v["W"], v["m"], after=v["after"])
        elif key.startswith("second:"):
            T = F.run({**LIVE, "max_per_day": 2, "second": {"side": "any", "cool": 0, **X}})
            U = trades({}, T=T, mfn=lambda t, r: float(t.get("x_m", 1.0)))
        elif key.startswith("scale:"):
            T = F.run({**LIVE, "scale_in": X})
            U = None
            L = [{**t, "risk": t["risk_pts"], "pts": (t["pnl"] + COMM * t["qty"]) / (PV * t["qty"])} for t in T]
        else:
            U = trades(X)
        if U is not None:
            L = lit_size(U)
        L = [{k: (v.item() if isinstance(v, np.generic) else v) for k, v in l.items()} for l in L]
        S = rl.score(L, F.SESS)
        h = lambda sp: (f"PF {s['lit'][sp]['pf']} net {s['lit'][sp]['net']:+,} (${s['lit'][sp]['per_month']:,}/mo) "
                        f"{s['lit'][sp]['tpw']}/wk")
        e = lambda sp: (f"PF {s['eval'][sp]['pf']} net {s['eval'][sp]['net']:+,} (${s['eval'][sp]['per_month']:,}/mo) 2w "
                        f"{s['eval'][sp]['p10']}/{s['eval'][sp]['f10']} dec10 {s['eval'][sp]['dec10']} p15/f15 "
                        f"{s['eval'][sp]['p15']}/{s['eval'][sp]['f15']} slow {s['eval'][sp]['slow_pass']} med {s['eval'][sp]['pass_med']}")
        ver = f"LIT size: H1 {h('H1')}; H2 {h('H2')}; 2021-25 ref {h('2021-25')}. Eval path (two_week): H1 {e('H1')}; H2 {e('H2')}."
        if "fund" in s:
            ver += f" Funded 50K $/mo to the owner H1 {s['fund']['H1']['per_month']} / H2 {s['fund']['H2']['per_month']} / 2021-25 {s['fund']['REF']['per_month']}."
        if "placebo" in s:
            ver += f" Placebo (share of shuffled tilts with more $): {s['placebo']}."
        rl.save(rid, f"LIT edge night: {key}", fam,
                "Owner 2026-10-29: find more edge on Zlarior (live LIT) - new target bands, BE in ATR, speed/slow/late targets, "
                "quality / timing size tilts on the eval and funded paths, weekly catch-up, scale-in and eval knobs re-measured",
                params={**LIVE, "x_edge": X or key}, trades=L, scored=S, status=st, verdict=ver,
                notes="tools/lit_edge.py: live LIT trades (tools/lit_final.run == lit_live), post-fill re-managed on true 1m bars "
                      "(2026; 5m in 2021-25), LIT size rule; eval = live two_week sizing; funded = tools/uprisk.funded_mc live preset.",
                writeup="lit-edge-2026-10-30", tags=["lit", "lit_edge"])
        print("saved", rid, flush=True)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "check":
        check()
    elif cmd == "grid":
        grid(sys.argv[2:] or None)
    elif cmd == "merge":
        merge()
    elif cmd == "save":
        save(PICKS)
