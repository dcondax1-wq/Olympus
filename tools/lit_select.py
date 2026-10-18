"""LIT trade selection: which LIT setups an experienced trader would take, and how much to put on (owner, 2026-10-18:
"higher win rates / smarter trades... think like a person, not how a bot would trade").

Wraps engine/lit.py and tools/lit_tightstop.py (neither edited) on the live LIT settings (live_model.json "lit" = lit_final +
loss pack). Steps:
  1. candidate set: every LIT setup the live filters accept (sweep, inducement, displacement, CISD, Monday rule, 8-80 pt
     stop, VIX-band target >= 1.5R), not only the first one a day. Each is simulated alone (unit size, the live executor:
     limit at the CISD level, 1m CISD confirmation, stop 1 tick beyond the sweep extreme, VIX band banked at 8R, BE at 1R,
     flat 15:55), plus causal features known at the trigger bar close (`feats`, checked by `lookahead`).
  2. person-like rules (grade A/B/C from 3-4 features, wait for a better setup, size by grade) and
  3. a small regularised model (numpy logistic regression, walk-forward: train Jan-Apr -> test May-Jun, train Jan-Jun ->
     test Jul-Oct), scored on
  4. the real one-trade-a-day path (2 a day where a rule needs it) under the eval sizing ($800 up to a 25-pt stop, then
     800x25/stop, weekly stop, never more than 60% of the room to the trailing max-loss floor, MFFU $1,000 soft daily loss).

  python tools/lit_select.py build       # candidates + outcomes + features -> research/runs/_cache/litsel_*.pkl
  python tools/lit_select.py check       # the 1-a-day replay of the candidates == lit_tightstop unit() (== run lit_live)
  python tools/lit_select.py lookahead   # features recomputed on data cut at the entry bar == full-data features
  python tools/lit_select.py explore     # single-feature tables, H1 / H2 (candidate level)
  python tools/lit_select.py rules       # grade / wait / size-by-grade rules -> research/lit/select_results.json
  python tools/lit_select.py model       # walk-forward logistic model, calibration, importances, model rules
  python tools/lit_select.py save        # store runs lit_sel_* (rl.save, family other, tags lit, lit_select)
Pick on 2026 H1 (Jan 2 - Jun 30), check on 2026 H2 (Jul 1 - Oct 16); 2021-25 is a reference line (5m only).
1 CPU process.
"""
from __future__ import annotations

import collections
import datetime as dt
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
from engine.data import DATA_DIR  # noqa: E402
from tools import lit_final as F  # noqa: E402
from tools import lit_tightstop as TL  # noqa: E402
from tools import runlib as rl  # noqa: E402

LIVE = TL.LIVE
PU = TL.P_of()                       # live params + the tight-stop defaults (stop_mode ext = the live stop)
SESS = F.SESS
SPAN = dict(F.SPAN)
SPAN["H1a"] = ("2026-01-01", "2026-04-30")
SPAN["H1b"] = ("2026-05-01", "2026-06-30")
CACHE = os.path.join(ROOT, "research", "runs", "_cache")
OUT = os.path.join(ROOT, "research", "lit", "select_results.json")
VER = "v1"
PV, COMM, SLIP, MAXQ = lit.PV, lit.COMM, lit.SLIP, lit.MAX_MICROS
EVAL_RULE = ("lit", 800, 25.0)
ROOM_K = 0.6
RISK_CAP = 900.0             # $ at risk at most on a sized-up trade (a full stop stays inside the $1,000 soft daily loss limit)
MAJOR = {"pd", "pw", "pm", "gap"}


# ================================================================================================ context
def es_aligned(M, upto_t=None):
    es = pd.read_csv(os.path.join(DATA_DIR, "ES_5m.csv")).drop_duplicates("time").set_index("time")
    if upto_t is not None:
        es = es[es.index <= upto_t]
    al = es.reindex(M.t)
    return {"h": al["high"].values, "l": al["low"].values, "c": al["close"].values}


def news_cal():
    ev = pd.read_csv(os.path.join(DATA_DIR, "news", "events.csv"))
    out = collections.defaultdict(list)
    for r in ev.itertuples():
        if r.impact != "high":
            continue
        tm = str(r.time_et)
        hh, mm = (int(x) for x in tm.split(":")) if ":" in tm else (8, 30)
        out[r.date].append(hh * 60 + mm)
    return out


def week_open_close(M):
    """{week_id: (open of the week's first bar, close of its last bar)} for finished weeks, by trading day."""
    W = {}
    for d, s, e in M.days:
        w = int(M.week_id[s])
        if w not in W:
            W[w] = [float(M.o[s]), float(M.c[e - 1]), s]
        else:
            W[w][1] = float(M.c[e - 1])
    return W


def plan_of(M, z, P=PU):
    """The live plan of a setup (lit._run_core), or None when the live filters refuse it."""
    if not lit.setup_ok(z, P, None):
        return None
    if P.get("monday") and lit.monday_block(M, z):
        return None
    ep = min(float(z["ref_d"]), z["trig_c"])
    stop0 = z["ext_d"] - P["stop_buf"]
    risk = ep - stop0
    if not (P["min_stop"] <= risk <= P["max_stop"]):
        return None
    sh = z["entry_d"] - ep
    TT = {c: [x + sh for x in v] for c, v in lit.targets_x(M, z, P).items()}
    best = None
    for c in P["classes"]:
        for dist in TT.get(c, []):
            if dist >= P["min_rr"] * risk:
                if best is None or dist < best:
                    best = dist
                break
    if best is None:
        return None
    tp = min(best, P["max_rr"] * risk) if P["max_rr"] else best
    obst = [x + sh for v in z["targets"].values() for x in v if x + sh > 0]
    return {"ep": ep, "stop0": stop0, "risk": risk, "tp": tp, "rr_raw": best / risk, "obst": min(obst) if obst else None}


# ================================================================================================ features
def feats(M, z, pl, ES, NEWS, WK, same_day, hist):
    """Causal features of setup z at the close of its trigger bar i (bars <= i only; z's own fields come from candidates(),
    checked by tests/test_lit_lookahead.py). same_day = earlier accepted setups of the day; hist = finished LIT-live trades
    (exit_t <= the trigger bar's close)."""
    i, ee, d, k = z["i"], z["ext_i"], z["dir"], z["k"]
    x = M.ctx[k]
    s = x["s"]
    hi_d, lo_d = (M.h, M.l) if d == 1 else (-M.l, -M.h)
    ep, risk = pl["ep"], pl["risk"]
    vm = x.get("vix_move") or np.nan
    a_i = float(M.atr[i])
    f = {}
    f["dir"] = d
    f["mod"] = z["mod"]
    f["hour"] = z["mod"] // 60
    f["sess"] = 0 if z["mod"] < 300 else 1 if z["mod"] < 480 else 2 if z["mod"] < 720 else 3
    f["dow"] = z["dow"]
    cls = set(z["swept_cls"])
    f["n_swept"] = len(z["swept"])
    f["n_cls"] = len(cls)
    f["major"] = int(bool(cls & MAJOR))
    f["box"] = int(bool(cls & {"asia", "london", "ny", "pre", "x_ny"}))
    f["bu_only"] = int(cls == {"buildup"})
    f["depth"] = z["depth_atr"]
    f["disp"] = z["disp"]
    q = [(dd, aa) for dd, aa in z["idm_a"] if dd <= 1.0 and aa <= 36]
    f["idm_n"] = len(q)
    f["idm_age"] = min(aa for dd, aa in q) if q else 36
    f["idm_dist"] = min(dd for dd, aa in q) if q else 1.0
    f["leg_bars"] = z["bars"]
    f["cisd_run"] = int(ee - z["ref_i"] + 1)
    f["stop_pts"] = round(risk, 2)
    f["stop_atr"] = round(risk / max(a_i, 1e-9), 3)
    f["rr"] = round(pl["rr_raw"], 3)
    f["obst_r"] = round(min(pl["obst"] / risk, 10.0), 3) if pl["obst"] else 10.0
    f["vec"] = int(z["vec"]); f["vec_sweep"] = int(z["vec_sweep"])
    f["how"] = int(z["how"])
    f["first_wk"] = int(bool(x.get("first_of_week")))
    f["nwog_side"] = z["nwog_side"]
    # the day so far
    dh, dl = float(hi_d[s:i + 1].max()), float(lo_d[s:i + 1].min())
    op = x["open18"] * d
    f["rng_used"] = (dh - dl) / vm
    f["fav_used"] = (dh - op) / vm
    f["adv_used"] = (op - dl) / vm
    f["pd18"] = (ep - op) / vm
    o00 = M.open_00[i]
    f["pd00"] = np.nan if np.isnan(o00) else (ep - o00 * d) / max(a_i, 1e-9)
    f["sweep_day_ext"] = int(lo_d[ee] <= dl + 1e-9)
    jh = s + int(np.argmax(hi_d[s:i + 1]))
    f["opp_ext_lon"] = int(120 <= M.mod[jh] < 300 and M.mod[jh] < 1080)
    f["opp_ext_age"] = round((i - jh) / 12.0, 2)                 # hours since the day's target-side extreme
    f["sweep_lon"] = int(120 <= M.mod[ee] < 300)
    ab = x.get("asia18")
    if ab and ab[2] < i:
        hi_a, lo_a = (ab[0], ab[1]) if d == 1 else (-ab[1], -ab[0])
        f["asia_pos"] = (ep - lo_a) / max(hi_a - lo_a, 1e-9)
        f["asia_rng"] = (hi_a - lo_a) / vm
    else:
        f["asia_pos"] = np.nan; f["asia_rng"] = np.nan
    # prior day / week trend (+ = with the trade), in VIX moves
    if k > 0:
        ps, pe = M.days[k - 1][1], M.days[k - 1][2]
        f["prev_day"] = (float(M.c[pe - 1]) - float(M.o[ps])) * d / vm
        f["prev_rng"] = (float(M.h[ps:pe].max()) - float(M.l[ps:pe].min())) / vm
    else:
        f["prev_day"] = f["prev_rng"] = np.nan
    w = int(M.week_id[s])
    pw = [ww for ww in WK if ww < w and WK[ww][2] < s]
    if pw:
        wo, wc, _ = WK[max(pw)]
        f["prev_week"] = (wc - wo) * d / vm
    else:
        f["prev_week"] = np.nan
    f["vix"] = x.get("vix", np.nan)
    pv = M.ctx[k - 1].get("vix") if k > 0 else None
    f["vix_chg"] = (x["vix"] - pv) if (pv and x.get("vix")) else np.nan
    f["atr_vm"] = a_i / vm
    # ES at the sweep: did ES also take its own prior 3h low (high for shorts)?
    a0, a1 = max(s - 600, ee - 36), ee - 3
    e_lo = ES["l"] if d == 1 else -ES["h"]
    f["es_swept"] = np.nan
    f["es_lead"] = np.nan
    if a1 > a0 and not np.isnan(e_lo[a0:ee + 1]).all() and not np.isnan(e_lo[a0:a1]).all():
        w2 = e_lo[ee - 2:min(ee + 3, i + 1)]
        if not np.isnan(w2).all():
            f["es_swept"] = int(np.nanmin(w2) < np.nanmin(e_lo[a0:a1]))
        ec = ES["c"] if d == 1 else -ES["c"]
        c_d = M.c if d == 1 else -M.c
        if not (np.isnan(ec[ee]) or np.isnan(ec[i])):
            nq_mv = (c_d[i] - lo_d[ee]) / abs(lo_d[ee])
            f["es_lead"] = float((ec[i] - ec[ee]) / abs(ec[ee]) / max(nq_mv, 1e-9))
    # news (scheduled high-impact releases)
    nd = NEWS.get(z["day"], [])
    nxt = [m - z["mod"] for m in nd if m >= z["mod"]]
    prv = [z["mod"] - m for m in nd if m < z["mod"]]
    f["news_next"] = min(nxt) if nxt else 600
    f["news_prev"] = min(prv) if prv else 600
    f["news_day"] = int(bool(nd))
    # levels already taken today (first breach between the day's start and the trigger bar)
    n_tk = 0
    for side, px, ki, nm, c_ in M.levels(k):
        if ki >= i:
            continue
        a = max(ki + 1, s)
        if a > i:
            continue
        if side == "high":
            n_tk += bool(M.h[a:i + 1].max() > px)
        else:
            n_tk += bool(M.l[a:i + 1].min() < px)
    f["lv_taken"] = n_tk
    f["prior_same"] = sum(1 for zz in same_day if zz["dir"] == d and zz["i"] < i)
    f["prior_opp"] = sum(1 for zz in same_day if zz["dir"] != d and zz["i"] < i)
    # recent LIT-live results (the shadow path, finished before the trigger bar's close)
    H = hist
    rr_ = [t["r1"] for t in H]
    f["last3_r"] = float(sum(rr_[-3:])) if rr_ else 0.0
    f["last5_w"] = int(sum(1 for r in rr_[-5:] if r > 0.5))
    f["prev_win"] = int(bool(rr_) and rr_[-1] > 0.5)
    wk = lit.iso_week(z["day"])
    f["wk_stops"] = sum(1 for t in H if t["exit"] == "STOP" and lit.iso_week(t["day"]) == wk)
    return {kk: (float(v) if v is not None else np.nan) for kk, v in f.items()}


# ================================================================================================ build
_S = {}


def base():
    if "M" not in _S:
        M, C = F.market(PU["ref"], PU["extra_boxes"])
        _S.update(M=M, C=C, B1=F.bars(M, "1m"), B5=F.bars(M, "5m"))
    return _S["M"], _S["C"], _S["B1"], _S["B5"]


def build(force=False):
    p = os.path.join(CACHE, f"litsel_{VER}_{rl._data_key().replace(':', '_')}.pkl")
    if os.path.exists(p) and not force:
        return pickle.load(open(p, "rb"))
    M, C, B1, B5 = base()
    sset = set(SESS)
    ES = es_aligned(M)
    NEWS = news_cal()
    WK = week_open_close(M)
    live = TL.unit()                                      # the LIT-live path (unit trades, == run lit_live)
    for t in live:
        t["r1"] = t["legs"][0][1] / t["risk_pts"]
    live_s = sorted(live, key=lambda t: t["exit_t"])
    ex_t = np.array([t["exit_t"] for t in live_s])
    rows, by_day = [], collections.defaultdict(list)
    for z in C:
        if z["day"] not in sset:
            continue
        pl = plan_of(M, z)
        if pl is None:
            continue
        use1 = int(M.day_of[z["entry_i"]]) in B1.full
        B = B1 if use1 else B5
        u = TL.tsim(M, B, z, pl["ep"], pl["ep"] + pl["tp"], False, pl["stop0"], PU)
        t_sig = int(M.t[z["i"]]) + 300
        hist = live_s[:int(np.searchsorted(ex_t, t_sig, side="right"))]
        f = feats(M, z, pl, ES, NEWS, WK, by_day[z["day"]], hist)
        by_day[z["day"]].append(z)
        if u is not None:
            u["r1"] = u["legs"][0][1] / u["risk_pts"]
        rows.append({"day": z["day"], "key": (z["day"], z["i"], z["dir"]), "entry_i": z["entry_i"], "t_sig": t_sig,
                     "u": u, "f": f, "z": {kk: z[kk] for kk in ("i", "dir", "swept", "swept_cls", "ext_i", "entry_i", "k")}})
    out = {"rows": rows}
    pickle.dump(out, open(p, "wb"))
    return out


# ================================================================================================ path + sizing
def replay(R, skip=None, size=None, max_per_day=1, second=None):
    """One trade at a time, in setup order, at most max_per_day a day (the live _run_core rule), on the candidate rows R.
    skip(row) -> True: not taken (the day stays free). size(row) -> grade multiplier. second(row) -> True allows a trade
    after the day's first one (when max_per_day > 1). Returns unit trades with wk_m (the weekly stop) and g_m (grade)."""
    out, busy, per_day = [], -1, collections.Counter()
    for r in R:
        if r["entry_i"] <= busy or per_day[r["day"]] >= max_per_day:
            continue
        if per_day[r["day"]] >= 1 and second is not None and not second(r):
            continue
        if skip is not None and skip(r):
            continue
        u = r["u"]
        if u is None:
            continue
        t = dict(u)
        t["g_m"] = float(size(r)) if size else 1.0
        t["_row"] = r
        busy = t["exit_i"]; per_day[r["day"]] += 1
        out.append(t)
    TL.wk_marks(out)
    return out


def qty_sel(t, rule, room=None, room_k=None):
    """lit_tightstop.qty_of + the grade multiplier, one rounding (engine/sizing.py lit_qty 'eval': base x weekly stop, floor 1,
    then the room cap)."""
    mi, mn = TL.base_q(t, rule)
    m = t.get("wk_m", 1.0) * t.get("g_m", 1.0)
    if m != 1.0:
        mi = max(1, min(MAXQ, int(mi * m + 1e-9)))
        if t.get("g_m", 1.0) > 1.0:          # a size-up never risks more than RISK_CAP (the MFFU daily loss limit is $1,000)
            mi = max(1, min(mi, int(RISK_CAP / (t["risk_pts"] * PV + COMM))))
    if room_k is not None and room is not None:
        cap = max(1, int(room_k * room / (t["risk_pts"] * PV)))
        mi = min(mi, cap)
    return mi, mn


TL.qty_of = qty_sel          # lit_tightstop's eval player and sizer now apply the grade multiplier too


def evals_x(U, span, rule=EVAL_RULE, room_k=ROOM_K, horizon=60):
    """lit_tightstop.evals + p15/f15, dec10, slow_pass (% of passes slower than 15 sessions)."""
    a, z = SPAN[span]
    ss = [d for d in SESS if a <= d <= z]
    by = collections.defaultdict(list)
    for t in sorted(U, key=lambda t: t["entry_t"]):
        if a <= t["day"] <= z:
            by[t["day"]].append(t)
    res = [TL._play(ss, by, i, horizon, rule, room_k) for i in range(len(ss))]
    N = len(res) or 1
    o = {}
    for H in (10, 15, 20):
        o[f"p{H}"] = round(100 * sum(1 for r, n in res if r == "PASS" and n <= H) / N, 1)
        o[f"f{H}"] = round(100 * sum(1 for r, n in res if r == "FAIL" and n <= H) / N, 1)
    o["dec10"] = round(o["p10"] + o["f10"], 1)
    P_ = sum(1 for r, _ in res if r == "PASS"); F_ = sum(1 for r, _ in res if r == "FAIL")
    o["pass_rate"] = round(100 * P_ / (P_ + F_), 1) if P_ + F_ else None
    pas = [n for r, n in res if r == "PASS"]
    o["pass_med"] = float(np.median(pas)) if pas else None
    o["slow_pass"] = round(100 * sum(1 for n in pas if n > 15) / len(pas), 1) if pas else None
    k, pa, fa, path = 0, 0, 0, []
    while k < len(ss):
        r, n = TL._play(ss, by, k, len(ss), rule, room_k, keep=path)
        if r == "OPEN":
            break
        pa += r == "PASS"; fa += r == "FAIL"; k += n
    o["b2b"] = f"{pa}/{fa}"
    return o, path


def score(U, spans=("H1", "H2", "2026", "2021-25")):
    out = {}
    for s in spans:
        e, path = evals_x(U, s)
        out[s] = {**TL.stats(path, s), **e}
    return out


def line(o, s):
    x = o.get(s) or {}
    if not x.get("n"):
        return f"{s}: n=0"
    return (f"{s}: n={x['n']} {x['tpw']}/wk 2+wk {x['wk2']}% win {x['win']} PF {x['pf']} net {x['net']:+,} (${x['per_month']:,}/mo) "
            f"DD {x['dd']:,} | 2wk {x['p10']}/{x['f10']} 3wk {x['p15']}/{x['f15']} 1mo {x['p20']}/{x['f20']} pr {x['pass_rate']} "
            f"med {x['pass_med']} slow {x['slow_pass']}")


# ================================================================================================ checks
def check():
    D = build()
    R = D["rows"]
    U = replay(R)
    L = TL.unit()
    ka = [(t["day"], t["entry_t"], t["exit"], round(t["legs"][0][1], 2)) for t in sorted(L, key=lambda t: t["entry_t"])]
    kb = [(t["day"], t["entry_t"], t["exit"], round(t["legs"][0][1], 2)) for t in U]
    print("candidates", len(R), "filled", sum(r["u"] is not None for r in R), "| live path", len(ka), "replay", len(kb),
          "identical", ka == kb)
    o = score(U, spans=("H1", "H2", "2026"))
    for s in ("H1", "H2", "2026"):
        print(line(o, s))
    return ka == kb


def lookahead(cuts=12, seed=11):
    """Cut the 5m data (and ES) at a setup's entry bar N (bar N reduced to its open, as tests/test_lit_lookahead.py), rebuild
    the market and the candidates, recompute every feature of the setups whose entry bar is N and compare with the full data."""
    import random
    from engine.data import load
    from tests.test_lit_lookahead import _cut
    full = load("NQ", "5m")
    a = int(np.searchsorted(np.array(full.date_str), "2025-08-01"))
    B = full.slice(a, len(full))
    Mf = lit.Market(bars=B, extra_boxes=PU["extra_boxes"])
    Cf = lit.candidates(Mf, ref=PU["ref"])
    NEWS = news_cal()
    ESf = es_aligned(Mf)
    WKf = week_open_close(Mf)

    def fe(M, C, ES, WK, keyset):
        by_day = collections.defaultdict(list)
        out = {}
        for z in C:
            pl = plan_of(M, z)
            if pl is None:
                continue
            if (z["i"], z["dir"]) in keyset:
                out[(z["i"], z["dir"])] = feats(M, z, pl, ES, NEWS, WK, by_day[z["day"]], [])
            by_day[z["day"]].append(z)
        return out
    rng = random.Random(seed)
    ent = sorted({z["entry_i"] for z in Cf if z["day"] >= "2026" and plan_of(Mf, z) is not None})
    picks = sorted(rng.sample(ent, min(cuts, len(ent))))
    bad = n = 0
    for N in picks:
        keys = {(z["i"], z["dir"]) for z in Cf if z["entry_i"] == N}
        A = fe(Mf, Cf, ESf, WKf, keys)
        Mt = lit.Market(bars=_cut(B, N), extra_boxes=PU["extra_boxes"])
        Ct = lit.candidates(Mt, ref=PU["ref"])
        Z = fe(Mt, Ct, es_aligned(Mt, upto_t=int(B.t[N]) - 300), week_open_close(Mt), keys)
        for kk in A:
            n += 1
            if kk not in Z:
                bad += 1; print("missing in cut", B.date_str[N], kk); continue
            df = [f for f in A[kk] if not (A[kk][f] == Z[kk][f] or (np.isnan(A[kk][f]) and np.isnan(Z[kk][f]))
                                            or abs(A[kk][f] - Z[kk][f]) < 1e-9)]
            if df:
                bad += 1; print("differs", B.date_str[N], kk, [(f, A[kk][f], Z[kk][f]) for f in df])
        print(f"cut {B.date_str[N]} bar {N}: {len(A)} setups checked", flush=True)
    print(f"lookahead: {n} setups, {bad} with a difference")
    return bad == 0


# ================================================================================================ helpers
def span_rows(R, s):
    a, z = SPAN[s]
    return [r for r in R if a <= r["day"] <= z]


def cand_stats(R):
    """Candidate level (each setup alone, unit size): n filled, win %, avg R, PF in R."""
    rr = np.array([r["u"]["r1"] for r in R if r["u"] is not None])
    if not len(rr):
        return {"n": 0}
    gl = -rr[rr < 0].sum()
    return {"n": len(rr), "win": round(100 * float((rr > 0.5).mean()), 1), "avg_r": round(float(rr.mean()), 3),
            "pf_r": round(float(rr[rr > 0].sum() / gl), 2) if gl else None, "tot_r": round(float(rr.sum()), 1)}


NUMF = ["mod", "depth", "disp", "idm_n", "idm_age", "idm_dist", "leg_bars", "cisd_run", "stop_pts", "stop_atr", "rr", "obst_r",
        "rng_used", "fav_used", "adv_used", "pd18", "pd00", "opp_ext_age", "asia_pos", "asia_rng", "prev_day", "prev_rng",
        "prev_week", "vix", "vix_chg", "atr_vm", "es_lead", "news_next", "news_prev", "lv_taken", "prior_same", "prior_opp",
        "last3_r", "last5_w", "n_swept", "wk_stops"]
BINF = ["dir", "major", "box", "bu_only", "vec", "vec_sweep", "how", "first_wk", "sweep_day_ext", "opp_ext_lon", "sweep_lon",
        "es_swept", "news_day", "prev_win"]


def explore():
    D = build()
    R = D["rows"]
    R26 = [r for r in R if r["day"] >= "2026"]
    filled = [r for r in R26 if r["u"] is not None]
    per_day = collections.Counter(r["day"] for r in R26)
    print(f"2026 candidates {len(R26)} on {len(per_day)} days (filled alone {len(filled)}), per day mean {np.mean(list(per_day.values())):.2f}")
    print("2021-25 candidates", sum(1 for r in R if r['day'] < '2026'))
    for s in ("H1", "H2", "2021-25"):
        print(s, cand_stats(span_rows(R, s)))
    rep = {}
    for nm in NUMF + BINF:
        v1 = [(r["f"][nm], r["u"]["r1"]) for r in span_rows(R, "H1") if r["u"] is not None and not np.isnan(r["f"][nm])]
        if len(v1) < 20:
            continue
        xs = np.array([a for a, b in v1])
        if nm in BINF:
            cuts = [0.5]
        else:
            cuts = list(np.unique(np.quantile(xs, [1 / 3, 2 / 3])))
        lines = []
        for s in ("H1", "H2", "2021-25"):
            v = [(r["f"][nm], r["u"]["r1"]) for r in span_rows(R, s) if r["u"] is not None and not np.isnan(r["f"][nm])]
            b = np.digitize([a for a, _ in v], cuts)
            cells = []
            for g in range(len(cuts) + 1):
                rr = np.array([y for (a, y), bb in zip(v, b) if bb == g])
                cells.append((len(rr), round(100 * float((rr > 0.5).mean()), 0) if len(rr) else None, round(float(rr.mean()), 2) if len(rr) else None))
            lines.append((s, cells))
        rep[nm] = {"cuts": [round(float(c), 3) for c in cuts], "rows": lines}
        print(f"{nm:14s} cuts {[round(float(c), 2) for c in cuts]} " + " | ".join(
            f"{s}: " + " ".join(f"[{n} w{w} {a:+}]" if n else "[0]" for n, w, a in cells) for s, cells in lines))
    json.dump(rep, open(os.path.join(ROOT, "research", "lit", "select_explore.json"), "w"), indent=1, default=str)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "build":
        D = build(force=True)
        print("rows", len(D["rows"]))
    elif cmd == "check":
        check()
    elif cmd == "lookahead":
        lookahead(int(sys.argv[2]) if len(sys.argv) > 2 else 12)
    elif cmd == "explore":
        explore()
    else:
        import importlib
        mod = importlib.import_module("tools.lit_select_rules")
        getattr(mod, cmd)()
