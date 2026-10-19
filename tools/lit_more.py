"""More LIT setups a week (owner 2026-10-19: "There's definitely more LIT-based setups a week, look harder.").

The live LIT (engine/lit.py run_x, live_model.json "lit") takes ~2.9 trades a week in 2026. This study looks for MORE LIT
setups that keep the edge, on angles not tried before (research/writeups/lit-more-setups.md):
  es       the same LIT engine on CME ES1! (data/ES_5m.csv from 2025-04; ES 1m only from 2026-09-16, so ES runs on 5m
           execution except its last month), traded as MES on the same MFFU account: ES alone, NQ + ES (1 per instrument per
           day, both may be open at once) and 1 a day across both (the first fill wins)
  htf      LIT setups detected on 15m candles (detector windows scaled to the same clock time; entry still the 30-min limit at
           the 15m CISD level + 1m CISD), added to the 5m setups: 1 a day across both, or 1 per timeframe a day
  miss     setups that passed every filter but did not fill: why they missed, and LIT re-entries (re-tap after a failed 1m
           CISD window, a longer limit, a longer 1m CISD window)
  loose    filter loosening (sweep depth, displacement, inducement window, stop range), one knob at a time + neighbours
  native   other LIT-native extras: a 2nd trade a day only for higher-tier liquidity (PDH/PDL, PWH/PWL, PMH/PML, NWOG/NDOG)

Scoring (every variant, both 2026 halves, costs in):
  money    the LIT rule size ($800 up to a 20-pt stop, 800x20/stop, max 40 micros, weekly stop: half size after 2 stop-outs in
           the ISO week, counted across instruments), $1.90 per micro round trip (MFFU MNQ; MES assumed the same), 1 tick of
           slippage on market entries and stop / BE / EOD exits (inside the engine's trade). MES: $5 per ES point per micro,
           converted to MNQ-equivalent points (x2.5) so the same $ sizing applies.
  eval     the live eval sizing (engine/sizing.lit_qty, live_model.json lit_sizing: two_week config C for 10 sessions, then
           safe_eval), MFFU Builder 50K exact rules (as tools/lit_eventual.py), a fresh eval started on every session of the
           half that sees 10+ sessions -> p10 / f10 (pass / fail within 10 sessions = 2 weeks) + a 1,000-path Monte Carlo (5-session
           blocks). Two instruments: trades in entry order; while another trade is open its full stop loss is taken off the
           room and the day's P&L for sizing, and the fail check adds every open trade's worst point (conservative).
  judge    pick on H1 (2026-01-02..06-30), check on H2 (07-01..10-16); adopt only if BOTH halves gain $ AND the 2-week pass rate,
           2-4 trades a week (to ~5 with a strong case). 2021-25 = reference only (5m execution; ES has no 2021-24).

  python tools/lit_more.py check      # base == run lit_live (120 trades 2026) and eval == lit_eventual "C 10 then safe_eval"
  python tools/lit_more.py all        # every family -> research/lit/more_setups.json
  python tools/lit_more.py save       # rl.save the runs lit_more_*
One process. Paper only.
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import os
import pickle
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import lit  # noqa: E402
from engine import sizing as SZ  # noqa: E402
from engine.data import load, load_ltf, resample  # noqa: E402
from tools import lit_final as F  # noqa: E402
from tools import runlib as rl  # noqa: E402

OUT = os.path.join(ROOT, "research", "lit", "more_setups.json")
CACHE = F.CACHE
LM = json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))
LIVE = {**lit.DEFAULTS, **LM["lit"]}
LS = LM["lit_sizing"]
EVAL_CFG = {**{k: LS[k] for k in ("two_week", "safe_cap", "eval_ref_stop", "fast_ref_stop")}, "mode": "two_week",
            "two_week_until": 10, "after_mode": "safe_eval"}
SESS = F.SESS
SPAN = {"H1": ("2026-01-01", "2026-06-30"), "H2": ("2026-07-01", "2026-12-31"), "2026": ("2026-01-01", "2026-12-31"),
        "ref": ("2021-01-01", "2025-12-31")}
PV, COMM, SLIP = 2.0, SZ.TW_COMM, 0.25          # MNQ $ per point, $1.90 a micro round trip
TGT, MLL, DLL, LOCK = 3000.0, 2000.0, 1000.0, 100.0
ES_X = 5.0 / 2.0                                # MES $5 / ES pt vs MNQ $2 / NQ pt: ES pts -> MNQ-equivalent pts
_S = {}


# ================================================================================================ data
def nq():
    if "nq" not in _S:
        M, C = F.market("cisd", ())
        _S["nq"] = (M, C, F.bars(M, "1m"), F.bars(M, "5m"))
    return _S["nq"]


def es():
    """LIT Market + candidates on CME ES1! 5m (2025-04 on), ES 1m where it rebuilds the 5m bars (2026-09-16 on)."""
    if "es" not in _S:
        M = lit.Market(bars=load("ES", "5m"))
        p = os.path.join(CACHE, f"litmore_es_cands_v1_{os.path.getmtime(os.path.join(ROOT, 'data', 'ES_5m.csv')):.0f}.pkl")
        if os.path.exists(p):
            C = pickle.load(open(p, "rb"))
        else:
            C = lit.candidates(M, ref="cisd")
            pickle.dump(C, open(p, "wb"))
        src, _ = load_ltf("ES", M.b)
        B1 = lit.bars_1m(M, src=src) if src is not None else None
        _S["es"] = (M, C, B1, lit.bars_5m(M))
    return _S["es"]


def remap(B, M_from, M_to):
    dmap = {d: k for k, (d, s, e) in enumerate(M_to.days)}
    tr = np.array([dmap.get(M_from.days[k][0], -1) for k in range(len(M_from.days))] + [-1])
    day = tr[np.asarray(B.day)]
    full = {int(tr[k]) for k in (B.full or ()) if tr[k] >= 0}
    return lit.XBars(B.t, B.o, B.h, B.l, B.c, B.mod, day, B.secs, full if B.full is not None else None)


def m15():
    """LIT on 15m candles resampled from the NQ 5m file, detector windows scaled to the same clock time (leg / sweep window 8,
    structure / inducement look-back 12 bars = tools/lit_losses.py market15); executor bars = the NQ 1m / 5m bars."""
    if "m15" not in _S:
        M, C, B1, B5 = nq()
        M15 = lit.Market(bars=resample(load("NQ", "5m"), "15m"))
        p = os.path.join(CACHE, f"litloss_m15_cands_{rl._data_key().replace(':', '_')}.pkl")
        if os.path.exists(p):
            C15 = pickle.load(open(p, "rb"))
        else:
            C15 = lit.candidates(M15, leg=8, sweep_win=8, ref_back=12, ind_back=12, ref="cisd")
            pickle.dump(C15, open(p, "wb"))
        _S["m15"] = (M15, C15, remap(B1, M, M15), remap(B5, M, M15))
    return _S["m15"]


def run_on(src, P, cands=None):
    M, C, B1, B5 = {"nq": nq, "es": es, "m15": m15}[src]()
    P = {**LIVE, **(P or {})}
    if src == "es" and B1 is None:
        P["tf"] = "5m"
    T = lit.run_x(M, cands if cands is not None else C, P, SESS, B1=B1 if P["tf"] == "1m" else None, B5=B5)
    return T


# ================================================================================================ trades -> common unit
def unit(T, inst="NQ", src="nq"):
    """Engine trades -> per-micro records in MNQ-equivalent points (exact: P&L, slippage, commission linear in micros)."""
    x = ES_X if inst == "ES" else 1.0
    U = []
    for t in T:
        q = t["qty"]
        if not q:
            continue
        U.append({"day": t["day"], "entry_t": int(t["entry_t"]), "exit_t": int(t["exit_t"]), "dir": t["dir"], "inst": inst, "src": src,
                  "risk": round(t["risk_pts"] * x, 4), "tgt": round(abs(t["target_px"] - t["entry_px"]) * x, 4),
                  "pts": (t["pnl"] + lit.COMM * q) / (lit.PV * q) * x, "w1": (t["low"] + lit.COMM * q) / (lit.PV * q) * x,
                  "exit": t["exit"], "tf": t["tf"], "swept": t.get("swept")})
    U.sort(key=lambda u: (u["entry_t"], u["inst"]))
    return U


def merge(sources, max_day=1, per_src_day=1):
    """Combine unit lists (each run on its own at 1 trade a day) into one account path: entry order, at most max_day trades a
    day in total and per_src_day per source; one trade at a time per instrument. With max_day 1 this is exact (the day's trade
    is the first fill of any source); with more it ignores a source's later same-day setups (a lower bound)."""
    allu = sorted([u for S in sources for u in S], key=lambda u: (u["entry_t"], u["src"]))
    out, nday, nsrc, busy = [], collections.Counter(), collections.Counter(), {}
    for u in allu:
        if nday[u["day"]] >= max_day or nsrc[(u["day"], u["src"])] >= per_src_day:
            continue
        if u["entry_t"] < busy.get(u["inst"], -1):
            continue
        out.append(u)
        nday[u["day"]] += 1; nsrc[(u["day"], u["src"])] += 1; busy[u["inst"]] = u["exit_t"]
    return out


def wk_mults(U):
    """Weekly stop (live_model.json lit wk_stop [2, 0.5]) across the account: half size once 2 STOP exits finished in the
    trade's ISO week before its entry."""
    n_st, m_st = LIVE["wk_stop"] if LIVE.get("wk_stop") else (10 ** 9, 1.0)
    out = []
    for u in U:
        wk = lit.iso_week(u["day"])
        n = sum(1 for v in U if v["exit"] == "STOP" and v["exit_t"] <= u["entry_t"] and lit.iso_week(v["day"]) == wk)
        out.append(dict(u, wk_m=float(m_st) if n >= n_st else 1.0))
    return out


# ================================================================================================ scoring
def money_trades(U):
    """LIT rule size + weekly stop, $1.90 commission -> trade dicts with pnl / low / qty."""
    T = []
    for u in wk_mults(U):
        q = lit.qty_for(u["risk"])
        if q < 1:
            continue
        if u["wk_m"] < 1:
            q = max(1, int(q * u["wk_m"] + 1e-9))
        pnl = u["pts"] * PV * q - COMM * q
        T.append(dict(u, qty=q, pnl=round(pnl, 2), low=round(min(0.0, u["w1"] * PV * q - COMM * q, pnl), 2)))
    return T


def sess_in(span):
    a, z = SPAN[span]
    return [s for s in SESS if a <= s <= z]


def stats(T, span):
    ss = sess_in(span)
    a, z = SPAN[span]
    TT = [t for t in T if a <= t["day"] <= z]
    p = np.array([t["pnl"] for t in TT] or [0.0])
    gl = -p[p < 0].sum()
    eq = np.cumsum(p)
    dd = float((eq - np.maximum.accumulate(np.r_[0.0, eq])[1:]).min()) if len(TT) else 0.0
    wks = collections.Counter(lit.iso_week(t["day"]) for t in TT)
    allw = {lit.iso_week(s) for s in ss}
    dd_ = collections.defaultdict(float)
    for t in TT:
        dd_[t["day"]] += t["pnl"]
    return {"n": len(TT), "tpw": round(len(TT) / (len(ss) / 5.0), 2), "wk2": round(100.0 * sum(1 for w in allw if wks[w] >= 2) / max(1, len(allw)), 1),
            "win": round(100.0 * sum(1 for t in TT if t["pnl"] > 0) / max(1, len(TT)), 1),
            "pf": round(float(p[p > 0].sum() / gl), 2) if gl else None, "net": round(float(p.sum())),
            "per_month": round(float(p.sum()) / (len(ss) / 21.0)), "dd": round(dd),
            "worst_day": round(min(dd_.values())) if dd_ else 0, "n_es": sum(1 for t in TT if t.get("inst") == "ES")}


def run_eval(seq, by, cfg=EVAL_CFG, horizon=10):
    """One MFFU Builder 50K eval (exact rules as tools/lit_eventual.run) over session indices seq, with concurrent trades."""
    bal = peak = 0.0
    floor = -MLL
    for k, si in enumerate(seq[:horizon]):
        cum = 0.0
        opn = []                                    # (exit_t, pnl, low, stop loss $)
        for j, t in enumerate(by[si]):
            still = []
            for o in opn:
                if o[0] <= t["entry_t"]:
                    cum += o[1]
                else:
                    still.append(o)
            opn = still
            if cum <= -DLL:
                break
            orisk = sum(o[3] for o in opn)
            st = {"profit": bal, "cum": cum - orisk, "room": bal + cum - orisk - floor, "session": k + 1, "n_today": j}
            base = lit.qty_for(t["risk"])
            m0 = max(1, int(base * (t.get("wk_m") or 1.0) + 1e-9)) if base else 0
            q = SZ.lit_qty(m0, {"risk_pts": t["risk"], "tgt_pts": t["tgt"], "size_mult": t.get("wk_m", 1.0)}, cfg,
                           room=st["room"], state=st, learning=None)["qty"] if m0 else 0
            if q <= 0:
                continue
            pnl = t["pts"] * PV * q - COMM * q
            low = min(0.0, t["w1"] * PV * q - COMM * q, pnl)
            olow = sum(o[2] for o in opn)
            if cum + olow + low <= -DLL:
                pnl = -DLL - cum - olow - SLIP * PV * q
                low = pnl
            if bal + cum + olow + low <= floor:
                return "FAIL", k + 1
            opn.append((t["exit_t"], pnl, low, (t["risk"] + SLIP) * PV * q + COMM * q))
        cum += sum(o[1] for o in opn)
        bal += cum
        if bal <= floor:
            return "FAIL", k + 1
        peak = max(peak, bal)
        floor = min(max(floor, peak - MLL), LOCK)
        if bal >= TGT:
            return "PASS", k + 1
    return "OPEN", min(len(seq), horizon)


def evals(U, span, n_mc=1000):
    U = wk_mults(U)
    by = collections.defaultdict(list)
    for t in U:
        by[t["day"]].append(t)
    ss = sess_in(span)
    B = [sorted(by.get(s, []), key=lambda t: t["entry_t"]) for s in ss]
    z = len(ss)
    ex = [run_eval(list(range(k, z)), B) for k in range(0, z - 10 + 1)]
    rng = np.random.default_rng(11)
    mc = []
    for _ in range(n_mc):
        s = []
        while len(s) < 10:
            b = int(rng.integers(0, z - 5 + 1))
            s.extend(range(b, b + 5))
        mc.append(run_eval(s[:10], B))
    f = lambda R, r: round(100.0 * sum(1 for x in R if x[0] == r) / max(1, len(R)), 1)
    pas = [d for r, d in ex if r == "PASS"]
    return {"p10": f(ex, "PASS"), "f10": f(ex, "FAIL"), "pass_med": float(np.median(pas)) if pas else None,
            "mc_p10": f(mc, "PASS"), "mc_f10": f(mc, "FAIL"), "n_starts": len(ex)}


def score(U):
    T = money_trades(U)
    o = {s: stats(T, s) for s in ("H1", "H2", "2026", "ref")}
    for s in ("H1", "H2"):
        o[s].update(evals(U, s))
    return o


def line(key, o):
    f = lambda s: (f"{o[s]['n']:3d} {o[s]['tpw']:4.2f}/wk w{o[s]['win']:4.1f} PF {o[s]['pf']} {o[s]['net']:+7,} "
                   f"DD {o[s]['dd']:+,} 2wk {o[s]['p10']}/{o[s]['f10']} mc {o[s]['mc_p10']}/{o[s]['mc_f10']}")
    return f"{key:44s} H1[{f('H1')}] H2[{f('H2')}] ref PF {o['ref']['pf']} {o['ref']['net']:+,}"


_RES = {}


def put(key, U, meta=None):
    o = score(U)
    o["meta"] = meta or {}
    _RES[key] = o
    _S.setdefault("U", {})[key] = U
    print(line(key, o), flush=True)
    return o


def dump():
    old = json.load(open(OUT)) if os.path.exists(OUT) else {}
    old.update(_RES)
    json.dump(old, open(OUT, "w"), indent=1, default=float)


# ================================================================================================ check
def check():
    T = run_on("nq", {})
    r = rl.load("lit_live")
    Tr = [dict(zip(r["trade_cols"], a)) for a in r["trades"]]
    a = {(t["day"], int(t["entry_t"])): round(t["pnl"], 2) for t in Tr if t["day"] >= "2026"}
    b = {(t["day"], int(t["entry_t"])): round(t["pnl"], 2) for t in T if t["day"] >= "2026"}
    same = sum(1 for k in a if k in b and abs(a[k] - b[k]) < 0.02)
    print(f"lit_live 2026 {len(a)} {sum(a.values()):+,.0f} | here {len(b)} {sum(b.values()):+,.0f} | identical {same}")
    U = unit(T)
    MT = money_trades(U)
    d = max(abs((m["pnl"] + 0.5 * m["qty"]) - t["pnl"]) for m, t in zip(MT, [t for t in T if t["qty"]]))
    print("money re-size vs engine ($1.40 -> $1.90): max diff", round(d, 2))
    from tools import lit_eventual as E
    from tools import lit_2wk as W
    D = W.data()
    for span in ("H1", "H2"):
        a_, z_ = W.span_idx(span)
        ex = [E.run(EVAL_CFG, list(range(k, z_)), D["by"], 10) for k in range(a_, z_ - 10 + 1)]
        print(span, "lit_eventual run (10 sessions):", round(100 * sum(r == "PASS" for r, _ in ex) / len(ex), 1),
              round(100 * sum(r == "FAIL" for r, _ in ex) / len(ex), 1), "| here:", evals(U, span, n_mc=200))


# ================================================================================================ families
def fam_base():
    U = unit(run_on("nq", {}))
    put("base (live LIT)", U, {"family": "base"})
    return U


def es_stops(k=1.0):
    """ES stop range in ES points: the NQ 8-80 range x the ES/NQ price ratio (2026 median ~0.28) x k."""
    return {"min_stop": round(8.0 * 0.28 * k, 2), "max_stop": round(80.0 * 0.28 * k, 2)}


def fam_es(Ub):
    M, C, B1, B5 = es()
    print("ES 1m full days:", len(B1.full) if B1 is not None else 0, flush=True)
    out = {}
    for lab, P in (("ES LIT (stops 2.2-22.4)", es_stops()), ("ES LIT (stops 1.8-28, wider)", es_stops(1.25) | {"min_stop": 1.75}),
                   ("ES LIT 5m exec only", es_stops() | {"tf": "5m"})):
        Ue = unit(run_on("es", P), "ES", "es")
        out[lab] = Ue
        put(lab + " alone", Ue, {"family": "es"})
    Ue = out["ES LIT (stops 2.2-22.4)"]
    put("NQ + ES, 1 per instrument a day", merge([Ub, Ue], max_day=2), {"family": "es"})
    put("NQ + ES, 1 a day (first fill)", merge([Ub, Ue], max_day=1), {"family": "es"})
    put("NQ + ES 5m-exec, 1 per instrument a day", merge([Ub, out["ES LIT 5m exec only"]], max_day=2), {"family": "es"})
    # NQ on 5m execution: the fair comparison for ES (which has no 1m before 2026-09-16)
    Un5 = unit(run_on("nq", {"tf": "5m"}))
    put("NQ LIT 5m exec only (fair ES comparison)", Un5, {"family": "es"})
    # correlation of the two
    corr(Ub, Ue)
    return out


def corr(Ub, Ue):
    a = collections.defaultdict(float); b = collections.defaultdict(float)
    for t in money_trades(Ub):
        a[t["day"]] += t["pnl"]
    for t in money_trades(Ue):
        b[t["day"]] += t["pnl"]
    both = sorted(set(a) & set(b))
    days26 = [d for d in both if d >= "2026"]
    same_dir = 0; overl = 0
    ua = {u["day"]: u for u in Ub}; ue = {u["day"]: u for u in Ue}
    for d in days26:
        same_dir += ua[d]["dir"] == ue[d]["dir"]
        overl += ua[d]["entry_t"] < ue[d]["exit_t"] and ue[d]["entry_t"] < ua[d]["exit_t"]
    x = np.array([a[d] for d in days26]); y = np.array([b[d] for d in days26])
    c = float(np.corrcoef(x, y)[0, 1]) if len(days26) > 2 else None
    nq26 = sum(1 for d in a if d >= "2026"); es26 = sum(1 for d in b if d >= "2026")
    # combined day risk at the LIT size when both are open
    _RES["_corr"] = {"days_nq_2026": nq26, "days_es_2026": es26, "days_both_2026": len(days26), "same_dir": same_dir,
                     "overlapping": overl, "daily_pnl_corr_both_days": round(c, 2) if c is not None else None,
                     "both_lose": int(sum((x < 0) & (y < 0))), "both_win": int(sum((x > 0) & (y > 0)))}
    print("NQ/ES:", _RES["_corr"], flush=True)


def fam_htf(Ub):
    M15, C15, _, _ = m15()
    out = {}
    for lab, P in (("15m LIT (live filters, idm 12 bars)", {"idm_a": [1.0, 12, 1]}),
                   ("15m LIT relaxed (depth 0.4, disp 0.7, idm 24, stop 100)", {"idm_a": [1.0, 24, 1], "depth": 0.4, "disp": 0.7, "max_stop": 100.0}),
                   ("15m LIT, limit 60 min", {"idm_a": [1.0, 12, 1], "wait": 12})):
        U15 = unit(run_on("m15", P), "NQ", "m15")
        out[lab] = U15
        put(lab + " alone", U15, {"family": "htf"})
        put("5m + " + lab + ", 1 a day", merge([Ub, U15], max_day=1), {"family": "htf"})
        put("5m + " + lab + ", 1 per tf a day", merge([Ub, U15], max_day=2), {"family": "htf"})
    return out


# ---- missed fills
_ORIG_SIM = lit.simulate_x


def miss_reason(M, B, cand, entry_px, tgt, stop, P):
    """Why a setup did not fill (replicates simulate_x's pre-fill walk): (reason, last bar index on B)."""
    d = cand["dir"]
    hi_d, lo_d, c_d, o_d = B.dirs(d)
    t0 = int(M.t[cand["entry_i"]])
    k = int(np.searchsorted(B.t, t0))
    s_day = int(M.day_of[cand["entry_i"]])
    wait_s = P["wait"] * 300
    cis = P.get("cisd1m")
    if cis and B.secs == 300:
        cis = max(1, cis // 5)
    tgt_cancel = entry_px + tgt[1] if tgt[0] == "pts" else tgt[1]
    tapped = None
    while k < B.n:
        if B.day[k] != s_day or lit._late(B.mod[k], P["flat_mod"], False):
            return ("eod_tapped" if tapped is not None else "eod"), k
        if tapped is None and B.t[k] >= t0 + wait_s:
            return "expired_untapped", k
        if lo_d[k] <= stop:
            return ("stop_after_tap" if tapped is not None else "stop_first"), k
        if tapped is None and lo_d[k] <= entry_px:
            tapped = k
        if tapped is None and hi_d[k] >= tgt_cancel:
            return "target_first", k
        if tapped is not None:
            if k - tapped > cis:
                return "tapped_no_cisd", k
            lowk = tapped + int(np.argmin(lo_d[tapped:k + 1]))
            cz = lit._cisd_level(c_d, o_d, lowk)
            if cz is not None and k > lowk and c_d[k] > cz[0] and k + 1 < B.n and B.day[k + 1] == s_day:
                return "fill", k
        k += 1
    return "data_end", k


def rearm_sim(mode):
    """Monkeypatch for lit.simulate_x (this process only): when a setup misses, re-arm it.
    mode = {"on": set of miss reasons to re-arm, "extra": minutes the re-armed limit may wait beyond the original 30 min (0 =
    only the time left), "max": re-arms per setup}. The re-armed limit starts at the next 5m bar after the miss (no bar is
    re-used), keeps the same level / stop / target, and dies like the live one (extreme broken, target first, flat 15:55)."""
    def sim(M, B, cand, entry_px, tgt, stop, P, live=False):
        t = _ORIG_SIM(M, B, cand, entry_px, tgt, stop, P, live=live)
        if t is not None or live:
            return t
        z, n = cand, 0
        end_t = int(M.t[cand["entry_i"]]) + P["wait"] * 300 + mode.get("extra", 0) * 60
        while n < mode.get("max", 1):
            why, k = miss_reason(M, B, z, entry_px, tgt, stop, P)
            if why not in mode["on"] or k >= B.n:
                return None
            i5 = int(np.searchsorted(M.t, B.t[k], side="right"))        # the next 5m bar after the miss bar
            if i5 >= M.n or M.day_of[i5] != M.day_of[cand["entry_i"]]:
                return None
            left = (end_t - int(M.t[i5])) // 300
            if left < 1 and why == "tapped_no_cisd" and mode.get("cisd_only_tap"):
                left = 1
            if left < 1:
                return None
            z = dict(cand, entry_i=i5)
            t = _ORIG_SIM(M, B, z, entry_px, tgt, stop, {**P, "wait": int(left)}, live=False)
            n += 1
            if t is not None:
                t["rearm"] = n
                return t
        return None
    return sim


def miss_diag():
    """Every 2026 setup that passed the live filters, run alone: filled or why it missed."""
    M, C, B1, B5 = nq()
    P = LIVE
    cnt = collections.Counter()
    for z in C:
        if not ("2026" <= z["day"] <= "2026-12-31"):
            continue
        if not lit.setup_ok(z, P) or (P.get("monday") and lit.monday_block(M, z)):
            continue
        ep = min(float(z["ref_d"]), z["trig_c"]); stop = z["ext_d"] - P["stop_buf"]; risk = ep - stop
        if not (P["min_stop"] <= risk <= P["max_stop"]):
            cnt["stop out of range"] += 1
            continue
        sh = z["entry_d"] - ep
        TT = {c: [x + sh for x in v] for c, v in lit.targets_x(M, z, P).items()}
        best = next((d_ for c in P["classes"] for d_ in TT.get(c, []) if d_ >= P["min_rr"] * risk), None)
        if best is None:
            cnt["no target >= 1.5R"] += 1
            continue
        tp = min(best, P["max_rr"] * risk)
        use1 = int(M.day_of[z["entry_i"]]) in B1.full
        B = B1 if use1 else B5
        why, _ = miss_reason(M, B, z, ep, ("lvl", ep + tp, False), stop, P)
        cnt[why] += 1
    _RES["_miss"] = dict(cnt)
    print("2026 setups by outcome (run alone):", dict(cnt), flush=True)


def fam_miss(Ub):
    miss_diag()
    V = [("re-tap after a failed 1m CISD window (time left)", {"on": {"tapped_no_cisd"}, "extra": 0, "max": 3}),
         ("re-tap after a failed 1m CISD window (+30 min)", {"on": {"tapped_no_cisd"}, "extra": 30, "max": 3}),
         ("re-tap after a failed 1m CISD window (+60 min)", {"on": {"tapped_no_cisd"}, "extra": 60, "max": 3}),
         ("re-arm untapped expired limit +60 min", {"on": {"expired_untapped"}, "extra": 60, "max": 1}),
         ("re-arm untapped expired limit +120 min", {"on": {"expired_untapped"}, "extra": 120, "max": 1}),
         ("re-arm both (+60 min)", {"on": {"expired_untapped", "tapped_no_cisd"}, "extra": 60, "max": 3}),
         ("re-arm both (+120 min)", {"on": {"expired_untapped", "tapped_no_cisd"}, "extra": 120, "max": 3})]
    for lab, mode in V:
        lit.simulate_x = rearm_sim(mode)
        try:
            put("miss: " + lab, unit(run_on("nq", {})), {"family": "miss", "mode": {**mode, "on": sorted(mode["on"])}})
        finally:
            lit.simulate_x = _ORIG_SIM
    for lab, P in (("1m CISD window 30 bars", {"cisd1m": 30}), ("1m CISD window 40 bars", {"cisd1m": 40}),
                   ("limit 60 min", {"wait": 12}), ("limit 90 min", {"wait": 18}), ("limit 120 min", {"wait": 24}),
                   ("limit 60 min + CISD window 30", {"wait": 12, "cisd1m": 30})):
        put("miss: " + lab, unit(run_on("nq", P)), {"family": "miss", "P": P})


def fam_loose(Ub):
    G = []
    for v in (0.3, 0.4, 0.6):
        G.append((f"depth {v}", {"depth": v}))
    for v in (0.6, 0.7, 0.9):
        G.append((f"disp {v}", {"disp": v}))
    for a in (24, 48, 72):
        G.append((f"idm age {a}", {"idm_a": [1.0, a, 1]}))
    for dm in (0.75, 1.5, 2.0):
        G.append((f"idm dist {dm}", {"idm_a": [dm, 36, 1]}))
    G.append(("no inducement gate", {"idm_a": None}))
    for lo, hi in ((6, 80), (8, 100), (6, 100), (8, 120), (4, 120), (10, 80), (8, 60)):
        G.append((f"stop {lo}-{hi}", {"min_stop": float(lo), "max_stop": float(hi)}))
    G.append(("depth 0.4 + disp 0.7", {"depth": 0.4, "disp": 0.7}))
    G.append(("depth 0.4 + disp 0.7 + stop 6-100", {"depth": 0.4, "disp": 0.7, "min_stop": 6.0, "max_stop": 100.0}))
    G.append(("depth 0.3 + disp 0.6 + idm 48 + stop 6-100", {"depth": 0.3, "disp": 0.6, "idm_a": [1.0, 48, 1], "min_stop": 6.0, "max_stop": 100.0}))
    for lab, P in G:
        put("loose: " + lab, unit(run_on("nq", P)), {"family": "loose", "P": P})
    # wide stops get 0 micros under 800x20/stop beyond ~89 pts (8000 / stop^2 < 1): the same ranges with a 1-micro floor
    for lo, hi in ((8, 100), (8, 120), (6, 120), (8, 150)):
        P = {"min_stop": float(lo), "max_stop": float(hi)}
        with qty_floor():
            put(f"loose: stop {lo}-{hi}, min 1 micro", unit(run_on("nq", P)), {"family": "loose", "P": P, "qty_floor": 1})


_ORIG_QTY = lit.qty_for


class qty_floor:
    """Size follows the stop, but never below 1 micro (this process only: lit.qty_for patched for the engine and the scoring)."""
    def __enter__(self):
        lit.qty_for = lambda risk_pts, risk_usd=800.0, ref_stop=20.0, max_micros=lit.MAX_MICROS: max(1, _ORIG_QTY(risk_pts, risk_usd, ref_stop, max_micros))
        return self

    def __exit__(self, *a):
        lit.qty_for = _ORIG_QTY


def fam_native(Ub):
    """A 2nd trade a day, only for a setup that swept higher-tier liquidity (previous day / week / month high-low, NWOG /
    NDOG), and only after the day's first trade ended; optional: only after the first was not a stop-out."""
    M, C, B1, B5 = nq()
    tiers = {"pd": {"pdh", "pdl"}, "pdwm": {"pdh", "pdl", "pwh", "pwl", "pmh", "pml"}, "pwm": {"pwh", "pwl", "pmh", "pml"},
             "gap": {"nwog", "ndog"}, "pdwm+gap": {"pdh", "pdl", "pwh", "pwl", "pmh", "pml", "nwog", "ndog"}}
    T1 = run_on("nq", {})
    for nm, S in tiers.items():
        for sal in (False, True):
            T2 = run_on("nq", {"max_per_day": 2, "stop_after_loss": sal})
            first = {}
            keep = []
            for t in T2:
                if t["day"] not in first:
                    first[t["day"]] = t
                    keep.append(t)
                elif set(t["swept"]) & S:
                    keep.append(t)
            # the 2nd trade's weekly stop is re-done by wk_mults on the unit path
            put(f"native: 2nd trade only for {nm} sweeps" + (" (not after a stop)" if sal else ""), unit(keep),
                {"family": "native", "tier": sorted(S), "stop_after_loss": sal})
    # tier-only setups as the day's only trade: is higher-tier liquidity better? (diagnostic)
    for nm in ("pdwm", "gap"):
        put(f"native: only {nm} sweeps (diagnostic)", unit(run_on("nq", {"sweep_names": sorted(tiers[nm])})), {"family": "native"})
    put("native: 2 a day, any setup (reference)", unit(run_on("nq", {"max_per_day": 2})), {"family": "native"})


def all_():
    Ub = fam_base()
    fam_es(Ub); dump()
    fam_htf(Ub); dump()
    fam_miss(Ub); dump()
    fam_loose(Ub); dump()
    fam_native(Ub); dump()



# ================================================================================================ more HTF (15m grid, 30m / 1h)
def fam_htf_grid(Ub):
    """Neighbours of the 15m add-on (1 a day across 5m + 15m)."""
    for dep in (0.4, 0.5):
        for dis in (0.7, 0.8):
            for age in (12, 24):
                for mx in (80.0, 100.0):
                    P = {"depth": dep, "disp": dis, "idm_a": [1.0, age, 1], "max_stop": mx}
                    lab = f"15m add d{dep} disp{dis} idm{age} stop{mx:.0f}"
                    U15 = unit(run_on("m15", P), "NQ", "m15")
                    put("htf grid: " + lab + ", 1 a day", merge([Ub, U15], max_day=1), {"family": "htf", "P": P})


def _candidates_short_days():
    """engine/lit.candidates with the 50-bar day minimum lowered to 10 (a 1h day has 23 bars): research copy, this process."""
    import inspect
    src = inspect.getsource(lit.candidates).replace("e - s < 50", "e - s < 10")
    ns = dict(vars(lit))
    exec(compile(src, "lit_candidates_short", "exec"), ns)
    return ns["candidates"]


def mtf(tf):
    key = "m" + tf
    if key not in _S:
        M, C, B1, B5 = nq()
        from engine import data as _data
        _data.TF_SECONDS.setdefault("30m", 1800)          # research only, this process
        Mx = lit.Market(bars=resample(load("NQ", "5m"), tf))
        k = {"30m": 6, "1h": 12}[tf]
        p = os.path.join(CACHE, f"litmore_{tf}_cands_v1_{rl._data_key().replace(':', '_')}.pkl")
        if os.path.exists(p):
            Cx = pickle.load(open(p, "rb"))
        else:
            cf = _candidates_short_days()
            Cx = cf(Mx, leg=max(2, 24 // k), sweep_win=max(2, 24 // k), ref_back=max(3, 36 // k), ind_back=max(3, 36 // k), ref="cisd")
            pickle.dump(Cx, open(p, "wb"))
        _S[key] = (Mx, Cx, remap(B1, M, Mx), remap(B5, M, Mx))
    return _S[key]


def fam_mtf(Ub):
    for tf in ("30m", "1h"):
        Mx, Cx, B1x, B5x = mtf(tf)
        k = {"30m": 6, "1h": 12}[tf]
        for lab, P in (("live filters", {"idm_a": [1.0, max(3, 36 // k), 1]}),
                       ("no inducement gate", {"idm_a": None}),
                       ("relaxed depth 0.4 disp 0.7 stop 100", {"idm_a": [1.0, max(3, 72 // k), 1], "depth": 0.4, "disp": 0.7, "max_stop": 100.0})):
            PP = {**LIVE, **P}
            T = lit.run_x(Mx, Cx, PP, SESS, B1=B1x, B5=B5x)
            Ux = unit(T, "NQ", "m" + tf)
            put(f"{tf} LIT {lab} alone", Ux, {"family": "htf", "P": P})
            put(f"5m + {tf} LIT {lab}, 1 a day", merge([Ub, Ux], max_day=1), {"family": "htf", "P": P})


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "check":
        check()
    elif cmd == "all":
        all_()
    elif cmd in ("es", "htf", "miss", "loose", "native", "htf_grid", "mtf"):
        Ub = fam_base()
        globals()["fam_" + cmd](Ub)
        dump()
