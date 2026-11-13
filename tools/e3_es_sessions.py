"""Team E3 (2026-11-13): "same edge, more markets". Does the proven LIT and ATLAS logic work AS-IS (only instrument-scaled
parameters) on CME ES (traded as MES micros) and in other session slots, as a second, weakly correlated signal stream for
more prop-firm accounts (MFFU's 3 funded slots are full)? Write-up: research/writeups/es-and-sessions-2026-11-13.md.
Numbers: research/second/e3_es_sessions.json. Paper research only: edits no engine / model / UI file, arms nothing.

Data (CME futures only, TradingView exports):
  NQ1!  5m 2021-11 -> 2026-10-16, 1m for 2026 (data/NQ_5m.csv, data/NQ_1m.csv)
  ES1!  5m 2025-04-14 -> 2026-10-16 ONLY (data/ES_5m.csv). There is NO ES 1m file and NO ES before 2025-04: ES has no
        2021-24 history and runs on 5m execution (the LIT 1m CISD window = 4 five-minute bars), like NQ before 2026.
        The fair NQ comparison is therefore NQ on 5m execution too ("nq_5m").

Instrument scaling (pre-registered, nothing tuned): k = the ES / NQ price ratio (median of the daily 18:00 opens of
2025-04..2026-10 = 0.28). Every point-valued setting is multiplied by k (LIT min / max stop 8 / 80 -> 2.25 / 22.5; ATLAS
members' 6 / 80 -> 1.75 / 22.5; S/R outcomes' 6 / 120). Breakeven offsets that pay the costs (LIT be_off 1.25, EMA beo
1.25 NQ pts = $1.90 / $2 + 1 tick) become the MES cost equivalent: $1.90 / $5 + 1 tick = 0.63 -> 0.5 ES pts. ATR / R / VIX
settings need no scaling (the LIT and EMA VIX band = VIX% x the instrument's own price = the S&P implied move on ES).
Neighbours: k x 0.8 / x 1.25 (stop range) to show the result is not a knife edge.

Money: ES points -> MNQ-equivalent points (x 2.5: MES $5 / ES pt vs MNQ $2 / NQ pt), so the same $ sizing, eval and
commission ($1.90 a micro round trip, MES assumed equal to MNQ) apply; slippage is the engine's 1 tick on ES (= $1.25 a
micro, 2.5x MNQ's $0.50: costs are proportionally higher on ES).
  LIT streams    the LIT rule size ($800 up to a 20-pt stop, 800x20/stop, max 40, weekly stop) = tools/lit_more.py
  ATLAS streams  $500 a trade per member (second_model.json usd), one position at a time, max 2 a day (account-B rule)
Eval: an own MFFU account per stream (the "more firms" question: each new firm's account is its own eval):
  LIT    Builder 50K, live lit_sizing two_week (room_f 0.8) for 10 sessions then safe_eval, exact tools/lit_more.run_eval
  ATLAS  Builder 25K, the account-B two_week preset (tools/second_account_b.sizing_cfg) with the 25K limits
  a fresh eval on every session of the span -> p10 / f10 / dec10 (2 weeks), p15 / f15 (3 weeks), pass_med, slow_pass
  (% of passes within 60 sessions that need more than 15).
Judge: LIT-style = pick on 2026 H1, check on H2 (no picking happens: the scaled version is fixed in advance); the only
history is 2025-04..12 for ES (2021-25 for NQ). Correlation = daily P&L over every session of the span (0 on no-trade days)
vs runs lit_live (NQ LIT) and atlas_base (NQ ATLAS).

    python -X utf8 tools/e3_es_sessions.py members NQ|ES   # ATLAS members on one instrument -> _cache pickle (own process)
    python -X utf8 tools/e3_es_sessions.py all             # every stream + evals + correlations -> research/second/e3_es_sessions.json
    python -X utf8 tools/e3_es_sessions.py save            # rl.save the runs e3_*
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import logging
import os
import pickle
import subprocess
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
logging.getLogger("engine.sizing").setLevel(logging.ERROR)
from engine import lit  # noqa: E402
from engine import sizing as SZ  # noqa: E402
from tools import lit_more as L  # noqa: E402

OUT = os.path.join(ROOT, "research", "second", "e3_es_sessions.json")
CACHE = os.path.join(ROOT, "research", "runs", "_cache")
ES_START = "2025-04-14"
SPANS = {"H1": ("2026-01-01", "2026-06-30"), "H2": ("2026-07-01", "2026-12-31"), "2026": ("2026-01-01", "2026-12-31"),
         "2025": (ES_START, "2025-12-31"), "2021-24": ("2021-01-01", "2024-12-31")}
PVI = {"NQ": 2.0, "ES": 5.0}
COMM = 1.90
BEO_ES = 0.5
L.SPAN.update(SPANS)
SESS = L.SESS


def k_ratio():
    """ES / NQ price ratio: median over common trading days of the first 5m open of the day."""
    a = pd.read_csv(os.path.join(ROOT, "data", "ES_5m.csv"))
    b = pd.read_csv(os.path.join(ROOT, "data", "NQ_5m.csv"))
    m = a.merge(b, on="time", suffixes=("_es", "_nq"))
    return round(float(np.median(m["open_es"] / m["open_nq"])), 3)


K = 0.28   # k_ratio() = 0.28 (checked in all_main; printed)


def scaled(k=K, inst="ES"):
    if inst == "NQ":
        return {}
    return {"min_stop": round(8.0 * k * 4) / 4, "max_stop": round(80.0 * k * 4) / 4, "be_off": BEO_ES}


# ================================================================================================ LIT streams
def lit_units(src, P):
    inst = "ES" if src == "es" else "NQ"
    return L.unit(L.run_on(src, P), inst, src)


def lit_streams():
    """name -> (units, meta). NQ references first, then ES (scaled), its neighbours, ES session slots, NQ session slots."""
    S = {}
    S["nq_lit_live"] = (lit_units("nq", {}), "NQ LIT as live (1m execution in 2026, 5m before)")
    S["nq_lit_5m"] = (lit_units("nq", {"tf": "5m"}), "NQ LIT on 5m execution (the fair ES comparison)")
    S["es_lit"] = (lit_units("es", scaled()), f"ES (MES) LIT, stops / BE scaled by k={K} (5m execution)")
    S["es_lit_k08"] = (lit_units("es", scaled(K * 0.8)), "ES LIT, stop range x0.8 (neighbour)")
    S["es_lit_k125"] = (lit_units("es", scaled(K * 1.25)), "ES LIT, stop range x1.25 (neighbour)")
    S["es_lit_be125"] = (lit_units("es", {**scaled(), "be_off": 1.25}), "ES LIT, BE offset left at 1.25 ES pts (lit-more-setups' choice)")
    S["es_lit_lon"] = (lit_units("es", {**scaled(), "window": [[120, 480]]}), "ES LIT, London slot only (02:00-08:00)")
    S["es_lit_ny"] = (lit_units("es", {**scaled(), "window": [[480, 930]]}), "ES LIT, NY slot only (08:00-15:30)")
    S["nq_lit_ny_slot"] = (lit_units("nq", {"window": [[480, 930]]}),
                          "NQ LIT, NY slot only (08:00-15:30) as its own account (takes the NY setup even when London traded)")
    S["nq_lit_lon_slot"] = (lit_units("nq", {"window": [[120, 480]]}), "NQ LIT, London slot only (02:00-08:00)")
    return S


def asia_units():
    """The Asia-slot trades of the stored LIT + Asia-slot run (lit-more-entries lead 1, already tested: correlation only)."""
    from tools import runlib as rl
    r = rl.load("lit_more_ent_asia_slot_rr3")
    T = [dict(zip(r["trade_cols"], a)) for a in r["trades"]]
    out = []
    from zoneinfo import ZoneInfo
    for t in T:
        x = dt.datetime.fromtimestamp(int(t["entry_t"]), ZoneInfo("America/New_York"))
        m = x.hour * 60 + x.minute
        if m >= 1080 or m < 120:
            out.append(t)
    return out


# ================================================================================================ ATLAS members on an instrument
def _rec(day, et, xt, dr, e, s, x, tgt, kind, worst, src):
    risk = abs(e - s)
    return {"day": str(day), "entry_t": int(et), "exit_t": int(xt), "dir": int(dr), "entry": float(e), "stop": float(s),
            "exit": float(x), "target": None if tgt is None else float(tgt), "exit_kind": str(kind), "risk_pts": float(risk),
            "pts": float((x - e) * dr), "worst": float(min(0.0, worst)), "src": src}


def members(sym):
    """EMA / MD / SR exactly as second_model.json, on sym's 5m bars (5m execution), point settings x k for ES."""
    from tools import retail_standalone as RS
    from tools import second_ema as SE
    from tools import second_md as SM
    from tools import second_sr as SR
    from engine.data import load
    k = 1.0 if sym == "NQ" else K
    cfg = json.load(open(os.path.join(ROOT, "second_model.json"), encoding="utf-8"))["strategies"]
    df = pd.read_csv(os.path.join(ROOT, "data", f"{sym}_5m.csv"))
    RS.load_frame(df)
    if sym != "NQ":                                     # unadjusted price for round numbers: the instrument's own rolls
        rolls = json.load(open(os.path.join(ROOT, "data", f"{sym}_rolls.json")))["rolls"]
        adj = np.zeros(RS.D["n"])
        for r in rolls:
            adj[RS.D["t"] < r["switch_t"]] += r["gap"]
        RS.D["adj"] = adj
    out = {}
    # ---- EMA (London EMA trend pullback)
    c = cfg["ema_lon_vix"]
    E, X = dict(c["entry"]), dict(c["exit"])
    SE.MIN_STOP, SE.MAX_STOP = 6.0 * k, 80.0 * k
    SE.CPTS = COMM / PVI[sym]
    if sym != "NQ":
        X["beo"] = BEO_ES
    U = SE.trades_of(E, X, span=("2021-11-01", "2026-10-16"))
    out["EMA"] = [_rec(u["day"], u["entry_t"], u["exit_t"], u["dir"], u["entry"], u["stop"], u["exit"], u["target"], u["exit_kind"],
                       u["worst_pts"], "EMA") for u in U]
    # ---- SR (NY sweep-and-reclaim)
    c = cfg["sr_nyreclaim"]
    key = dict(c["key"])
    key["max_stop"] = 80.0 * k
    SR.outcomes.__defaults__ = (120.0 * k, 6.0 * k, 1.5)
    SR.D.clear(); SR._OC.clear()
    SR.data()
    T = SR.run_key(key)
    TT = SR.set_targets(SR.trades_of(T, "usd500", "nyreclaim"), key)
    out["SR"] = [_rec(t["day"], t["entry_t"], t["exit_t"], t["dir"], t["entry"], t["stop"], t["exit"], t["target"], t["exit_kind"],
                      -float(t["mae"]) * float(t["_x"]["risk"]), "SR") for t in TT]
    # ---- MD (MACD divergence at a sweep), 5m execution (no ES 1m)
    c = cfg["macd_sweep"]
    gen, sim, flt = dict(c["gen"]), dict(c["sim"]), dict(c["flt"])
    SM.MIN_STOP, SM.MAX_STOP = 6.0 * k, 80.0 * k
    M = lit.Market(bars=load(sym, "5m"))
    Xc = SM.Ctx(M, "none")
    C = SM.md_cands(Xc, **gen)
    outs = [SM.sim_x(Xc, z, sim) for z in C]
    TM = SM.greedy(Xc, C, outs, flt["kz"], flt["maxpd"], SM.md_filter(flt))
    recs = []
    for z, r in TM:
        t = SM.tr_rec(Xc, z, r, 1, "MD")
        recs.append(_rec(t["day"], t["entry_t"], t["exit_t"], t["dir"], t["entry"], t["stop"], t["exit"], t["target"], t["exit_kind"],
                         t["_worst"], "MD"))
    out["MD"] = recs
    p = os.path.join(CACHE, f"e3_members_{sym}.pkl")
    pickle.dump(out, open(p, "wb"))
    for nm, v in out.items():
        print(sym, nm, len(v), "trades", flush=True)
    return out


def load_members(sym, fresh=False):
    p = os.path.join(CACHE, f"e3_members_{sym}.pkl")
    if fresh or not os.path.exists(p):
        subprocess.run([sys.executable, "-X", "utf8", os.path.abspath(__file__), "members", sym], check=True)
    return pickle.load(open(p, "rb"))


def check_members():
    """Our NQ re-run vs the stored research trades (ema_best / md_best / sr_best): same days, same P&L at $500."""
    Mq = load_members("NQ")
    res = {}
    for nm, f in (("EMA", "ema_best"), ("MD", "md_best"), ("SR", "sr_best")):
        st = json.load(open(os.path.join(ROOT, "research", "second", f + ".json"), encoding="utf-8"))["trades"]
        a = {(t["day"], int(t["entry_t"])) for t in st}
        b = {(t["day"], int(t["entry_t"])) for t in Mq[nm]}
        res[nm] = {"stored": len(a), "here": len(b), "same_entries": len(a & b)}
    print("member check (NQ re-run vs stored):", res, flush=True)
    return res


def atlas_units(sym, Mm, usd=500.0, max_day=2):
    """Members pooled on one account: entry order, one position at a time, max 2 a day; MNQ-equivalent units."""
    x = PVI[sym] / 2.0
    allt = sorted([t for v in Mm.values() for t in v], key=lambda t: (t["entry_t"], t["src"]))
    out, nday, busy = [], collections.Counter(), -1
    for t in allt:
        if nday[t["day"]] >= max_day or t["entry_t"] < busy or t["risk_pts"] <= 0:
            continue
        nday[t["day"]] += 1; busy = t["exit_t"]
        tgt = abs(t["target"] - t["entry"]) if t["target"] is not None else 3.0 * t["risk_pts"]
        out.append({"day": t["day"], "entry_t": t["entry_t"], "exit_t": t["exit_t"], "dir": t["dir"], "inst": sym, "src": t["src"],
                    "risk": round(t["risk_pts"] * x, 4), "tgt": round(tgt * x, 4), "pts": t["pts"] * x,
                    "w1": max(-(t["risk_pts"] + 0.25), min(t["worst"], t["pts"])) * x, "exit": t["exit_kind"].upper(), "usd": usd})
    return out


def usd_trades(U, usd=500.0):
    """$ a trade sizing: micros = floor(usd / (risk x $2)), 1-40 (MNQ-equivalent units)."""
    T = []
    for u in U:
        q = max(1, min(40, int(usd / (u["risk"] * 2.0))))
        pnl = u["pts"] * 2.0 * q - COMM * q
        T.append(dict(u, qty=q, pnl=round(pnl, 2), low=round(min(0.0, u["w1"] * 2.0 * q - COMM * q, pnl), 2)))
    return T


# ================================================================================================ evals (own account per stream)
PLAN = {"50k": dict(SZ.TW_50K), "25k": dict(SZ.TW_25K)}


def cfg_25k():
    from tools import second_account_b as AB
    c = AB.sizing_cfg("builder25k")
    c.update(two_week_until=10, after_mode="safe_eval")
    return c


def run_eval(seq, by, cfg, plan, horizon):
    """tools/lit_more.run_eval with the plan's limits (target, trailing max loss, soft daily loss, max micros)."""
    P = PLAN[plan]
    TGT, MLL, DLL, LOCK, MQ = P["target"], P["mll"], P["dll"], P["lock"], int(P["max_micros"])
    PV, SLIP = 2.0, 0.25
    bal = peak = 0.0
    floor = -MLL
    for k, si in enumerate(seq[:horizon]):
        cum = 0.0
        opn = []
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
                           room=st["room"], state=st, max_micros=MQ, learning=None)["qty"] if m0 else 0
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


def evals(U, span, plan="50k", lit_size=True):
    """Fresh eval on every session of the span with 10 sessions after it -> the repo's eval-speed metrics."""
    cfg = L.EVAL_CFG if plan == "50k" else cfg_25k()
    U = L.wk_mults(U) if lit_size else [dict(u, wk_m=1.0) for u in U]
    by = collections.defaultdict(list)
    for t in U:
        by[t["day"]].append(t)
    a, z = SPANS[span]
    ss = [s for s in SESS if a <= s <= z]
    allss = [s for s in SESS if s >= a]                  # a start in the span may run past its end (longer horizons)
    B = [sorted(by.get(s, []), key=lambda t: t["entry_t"]) for s in allss]
    n = len(ss)
    if n < 10:
        return {}
    r10 = [run_eval(list(range(k, n)), B, cfg, plan, 10) for k in range(0, n - 10 + 1)]
    r15 = [run_eval(list(range(k, len(allss))), B, cfg, plan, 15) for k in range(0, n - 10 + 1)]
    r60 = [run_eval(list(range(k, len(allss))), B, cfg, plan, 60) for k in range(0, n - 10 + 1)]
    f = lambda R, r: round(100.0 * sum(1 for x in R if x[0] == r) / max(1, len(R)), 1)
    pas = [d for r, d in r60 if r == "PASS"]
    return {"p10": f(r10, "PASS"), "f10": f(r10, "FAIL"), "dec10": round(f(r10, "PASS") + f(r10, "FAIL"), 1),
            "p15": f(r15, "PASS"), "f15": f(r15, "FAIL"), "pass_med": float(np.median([d for r, d in r10 if r == "PASS"])) if any(r == "PASS" for r, _ in r10) else None,
            "slow_pass": round(100.0 * sum(1 for d in pas if d > 15) / len(pas), 1) if pas else None,
            "p60": f(r60, "PASS"), "n_starts": len(r10)}


# ================================================================================================ money stats + correlation
def stats(T, span):
    a, z = SPANS[span]
    ss = [s for s in SESS if a <= s <= z]
    if not ss:
        return {"n": 0}
    TT = [t for t in T if a <= t["day"] <= z]
    p = np.array([t["pnl"] for t in TT] or [0.0])
    gl = -p[p < 0].sum()
    eq = np.cumsum(p)
    dd = float((eq - np.maximum.accumulate(np.r_[0.0, eq])[1:]).min()) if TT else 0.0
    wks = collections.Counter(lit.iso_week(t["day"]) for t in TT)
    allw = {lit.iso_week(s) for s in ss}
    byd = collections.defaultdict(float)
    for t in TT:
        byd[t["day"]] += t["pnl"]
    return {"n": len(TT), "tpw": round(len(TT) / (len(ss) / 5.0), 2),
            "wk2": round(100.0 * sum(1 for w in allw if wks[w] >= 2) / max(1, len(allw)), 1),
            "win": round(100.0 * sum(1 for t in TT if t["pnl"] > 0) / max(1, len(TT)), 1),
            "pf": round(float(p[p > 0].sum() / gl), 2) if gl else None, "net": round(float(p.sum())),
            "per_month": round(float(p.sum()) / (len(ss) / 21.0)), "dd": round(dd),
            "worst_day": round(min(byd.values())) if byd else 0, "sessions": len(ss)}


_REF = {}


def ref_daily(rid):
    if rid not in _REF:
        from tools import runlib as rl
        _REF[rid] = {d[0]: float(d[1]) for d in rl.load(rid)["days"]}
    return _REF[rid]


def corr(T, ref, span):
    a, z = SPANS[span]
    byd = collections.defaultdict(float)
    for t in T:
        byd[t["day"]] += t["pnl"]
    R = ref_daily(ref) if isinstance(ref, str) else ref
    days = [s for s in SESS if a <= s <= z]
    x = np.array([R.get(d, 0.0) for d in days]); y = np.array([byd.get(d, 0.0) for d in days])
    if len(days) < 10 or x.std() == 0 or y.std() == 0:
        return None
    both = int(((x != 0) & (y != 0)).sum())
    return {"r": round(float(np.corrcoef(x, y)[0, 1]), 3), "both_days": both,
            "both_lose": int(((x < 0) & (y < 0)).sum()), "both_win": int(((x > 0) & (y > 0)).sum())}


def corr_all(T):
    return {nm: {sp: corr(T, rid, sp) for sp in ("2026", "H1", "H2", "2025")} for nm, rid in (("lit", "lit_live"), ("atlas", "atlas_base"))}


def corr_null(T, ref, span, n=500, seed=3):
    """Correlation of the stream's daily P&L vs the reference's after shuffling the stream's days (null: no link)."""
    a, z = SPANS[span]
    byd = collections.defaultdict(float)
    for t in T:
        byd[t["day"]] += t["pnl"]
    R = ref_daily(ref)
    days = [s for s in SESS if a <= s <= z]
    x = np.array([R.get(d, 0.0) for d in days]); y = np.array([byd.get(d, 0.0) for d in days])
    rng = np.random.default_rng(seed)
    c = [float(np.corrcoef(x, rng.permutation(y))[0, 1]) for _ in range(n)]
    return {"p95": round(float(np.percentile(np.abs(c), 95)), 3)}


# ================================================================================================ main
def score_stream(name, T, U, desc, plan, lit_size):
    o = {"desc": desc, "plan": plan}
    for sp in ("H1", "H2", "2026", "2025", "2021-24"):
        o[sp] = stats(T, sp)
        if sp in ("H1", "H2", "2025") and o[sp].get("n"):
            o[sp].update(evals(U, sp, plan, lit_size))
    o["corr"] = corr_all(T)
    o["n_by_src"] = dict(collections.Counter(t.get("src") for t in T if t["day"] >= "2026"))
    return o


def line(nm, o):
    f = lambda s: (f"{o[s].get('n', 0):3d} {o[s].get('tpw', 0):4.2f}/wk PF {o[s].get('pf')} ${o[s].get('net', 0):+7,} "
                   f"(${o[s].get('per_month', 0):+,}/mo) 2wk {o[s].get('p10')}/{o[s].get('f10')}")
    c = o["corr"]["lit"]["2026"]
    return f"{nm:18s} H1[{f('H1')}] H2[{f('H2')}] 2025[{f('2025')}] corrLIT26 {c and c['r']}"


def all_main():
    print("k = ES/NQ price ratio:", k_ratio(), "(used", K, ")", flush=True)
    res = {"built": dt.date.today().isoformat(), "k": K, "be_off_es": BEO_ES, "streams": {}}
    # ---- LIT streams (LIT size, own Builder 50K)
    for nm, (U, desc) in lit_streams().items():
        T = L.money_trades(U)
        o = score_stream(nm, T, U, desc, "50k", True)
        res["streams"][nm] = o
        print(line(nm, o), flush=True)
    # ---- ATLAS streams ($500 a trade, own Builder 25K)
    res["member_check"] = check_members()
    for sym in ("NQ", "ES"):
        Mm = load_members(sym)
        for mem in (None, "EMA", "MD", "SR"):
            sub = Mm if mem is None else {mem: Mm[mem]}
            U = atlas_units(sym, sub, max_day=2 if mem is None else 1)
            T = usd_trades(U)
            nm = f"{sym.lower()}_atlas" + ("" if mem is None else f"_{mem.lower()}")
            o = score_stream(nm, T, U, f"{sym} ATLAS" + ("" if mem is None else f" member {mem}") + " (5m execution, $500 a trade)",
                             "25k", False)
            res["streams"][nm] = o
            print(line(nm, o), flush=True)
    # ---- the already-tested Asia slot: correlation only (lit-more-entries lead 1; not redone)
    TA = asia_units()
    res["asia_slot_corr"] = corr_all(TA)
    res["asia_slot_n2026"] = sum(1 for t in TA if t["day"] >= "2026")
    # ---- null band for the correlations
    res["corr_null"] = {sp: corr_null(L.money_trades(lit_streams()["es_lit"][0]), "lit_live", sp) for sp in ("2026", "2025")}
    json.dump(res, open(OUT, "w", encoding="utf-8"), indent=1, default=float)
    print("->", OUT)


STATUS = {"es_lit": "rejected", "nq_lit_ny_slot": "rejected", "es_atlas": "rejected", "nq_atlas": "info", "nq_lit_5m": "info"}


def save_main():
    from tools import runlib as rl
    res = json.load(open(OUT, encoding="utf-8"))
    LS = lit_streams()
    rows = [("e3_nq_lit_5m", "NQ LIT on 5m execution (fair ES comparison)", "nq_lit_5m", LS["nq_lit_5m"][0], "lit"),
            ("e3_es_lit", f"LIT on ES as MES, stops / BE scaled by k={K}, 5m execution", "es_lit", LS["es_lit"][0], "lit"),
            ("e3_es_lit_lon", "LIT on ES, London slot only (02:00-08:00)", "es_lit_lon", LS["es_lit_lon"][0], "lit"),
            ("e3_es_lit_ny", "LIT on ES, NY slot only (08:00-15:30)", "es_lit_ny", LS["es_lit_ny"][0], "lit"),
            ("e3_nq_lit_ny_slot", "NQ LIT NY slot (08:00-15:30) as its own account", "nq_lit_ny_slot", LS["nq_lit_ny_slot"][0], "lit")]
    for sym in ("NQ", "ES"):
        rows.append((f"e3_{sym.lower()}_atlas", f"ATLAS (EMA + MD + S/R) on {sym}, 5m execution, $500 a trade, max 2 a day",
                     f"{sym.lower()}_atlas", atlas_units(sym, load_members(sym)), "usd"))
    for rid, title, key, U, kind in rows:
        T = L.money_trades(U) if kind == "lit" else usd_trades(U)
        sess = [s for s in SESS if s >= (ES_START if "es_" in key else "2021-01-01")]
        T = [dict(t, r=round(t["pts"] / t["risk"], 3), risk_pts=t["risk"], half=False, trigger=t.get("src"), mfe=None, mae=None,
                  bars_held=None, regime="", mult=1.0, risk_usd=round(t["risk"] * 2.0 * t["qty"], 2)) for t in T]
        S = rl.score(T, sess)
        o = res["streams"][key]
        c = o["corr"]["lit"]["2026"]
        verdict = (f"H1 ${o['H1']['net']:+,} / H2 ${o['H2']['net']:+,} / 2025 ${o['2025'].get('net', 0):+,}; own-eval 2-week pass/fail "
                   f"H1 {o['H1'].get('p10')}/{o['H1'].get('f10')}, H2 {o['H2'].get('p10')}/{o['H2'].get('f10')}; daily corr with NQ LIT "
                   f"2026 {c and c['r']}.")
        rl.save(rid, title, "other", "Team E3 2026-11-13: does the proven LIT / ATLAS logic work on ES (MES) and other session slots "
                "as a 2nd, weakly correlated stream for more prop accounts?",
                params={"stream": key, "k": K, "be_off_es": BEO_ES, "tool": "tools/e3_es_sessions.py",
                        "data": "CME ES1! 5m 2025-04-14 -> 2026-10-16 (no ES 1m, no 2021-24)" if "es_" in key else "CME NQ1! 5m + 1m 2026"},
                sizing={"mode": "lit_rule" if kind == "lit" else "fixed_risk", "risk_usd": 500 if kind == "usd" else None},
                trades=T, scored=S, status=STATUS.get(key, "rejected"), verdict=verdict,
                notes="tools/e3_es_sessions.py (research/second/e3_es_sessions.json); MES $5/pt converted to MNQ-equivalent points (x2.5), "
                      "$1.90 a micro, 1 tick slippage; the own-account eval columns in the write-up use the plan's two_week sizing.",
                writeup="es-and-sessions-2026-11-13", tags=["e3", "es" if "es_" in key else "nq", "sessions"])
        print("saved", rid, rl.line(S, "2026"), flush=True)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    if cmd == "members":
        members(sys.argv[2])
    elif cmd == "all":
        all_main()
    elif cmd == "save":
        save_main()
    elif cmd == "check":
        check_members()
    else:
        raise SystemExit(__doc__)
