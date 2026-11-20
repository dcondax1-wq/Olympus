"""Zlarior (LIT) more money (night-litmore 2026-11-19, research/writeups/lit-more-money-2026-11-19.md). RESEARCH ONLY.

Pre-registered (committed before any result): research/lit/more_money_design_batch1.md (2 ideas) and
research/lit/more_money_design_batch2.md (7 ideas, the owner's added scope). Every idea is ONE fixed version.

Base = the live LIT trades (tools/lit_edge.ctx()["T"] == run lit_live), re-walked after the fill by manage_v below
(= tools/lit_lab_ideas.manage_x with every option off; `check` proves it equals tools/lit_edge.trades({}) for all 631
trades) + the new options. Scored by tools/lit_edge.evaluate(U=...): LIT size, the live Builder 50K eval path (two_week,
room_f 0.4 to session 80), the funded Builder 50K Monte Carlo. Decisions use closed bars only and act at the next bar's
open (- 1 tick), like the 15-minute check.

  exit / entry options (manage_v):  be_frac, cisd_fail, es_fail, fill_limit_close, tgt_through (honesty check, not an idea)
  setup filters (engine skip_keys, the day left free like the live loop): bias_london, news_after, smt_filter
  trade lists: es_filler (ES LIT as MES, NQ priority + preempt), smt_pick (MES instead of MNQ when ES held = SMT)

    python -X utf8 tools/lit_more_money.py check     # options off == the live trades; SMT / ES coverage counts
    python -X utf8 tools/lit_more_money.py run       # every pre-registered idea -> research/lit/more_money.json + Lab rows
    python -X utf8 tools/lit_more_money.py gap       # live vs backtest twin since the eval start (Oct 19) on today's bars
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import logging
import math
import os
import sys
from zoneinfo import ZoneInfo

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
logging.getLogger("engine.sizing").setLevel(logging.ERROR)
from engine import lit  # noqa: E402
from tools import lit_edge as E  # noqa: E402
from tools import lit_adv_manage as A  # noqa: E402
from tools import lit_final as F  # noqa: E402

OUT = os.path.join(ROOT, "research", "lit", "more_money.json")
LAB = os.path.join(ROOT, "research", "lab", "lit_more_money.json")
NEWS = os.path.join(ROOT, "data", "news", "events.csv")
ET = ZoneInfo("America/New_York")
TICK, SLIP = lit.TICK, lit.SLIP
ES_X = 2.5                       # MES $5 / ES pt vs MNQ $2 / NQ pt: ES pts -> MNQ-equivalent pts
ES_K = 0.28                      # E3's pre-registered ES / NQ price ratio
ES_STOP = (round(8.0 * ES_K * 4) / 4, round(80.0 * ES_K * 4) / 4)      # 2.25 .. 22.5 ES pts
ES_BEO = 0.75                    # E3: the ES breakeven offset that pays the costs
LIVE = E.LIVE
SPANS = E.SPANS

BATCH1 = ("es_filler", "be_frac")
BATCH2 = ("fill_limit_close", "bias_london", "news_after", "cisd_fail", "es_fail", "smt_filter", "smt_pick")
IDEAS = BATCH1 + BATCH2
DESC = {
    "es_filler": "LIT on ES as MES, same account, only while NQ has not traded that day; NQ preempts an open ES trade",
    "be_frac": "breakeven at clip(0.25 x planned target R, 0.5R, 2.0R) instead of +1R",
    "fill_limit_close": "entry LIMIT at the 1m CISD close for one bar (needs 1 tick through), else market next bar",
    "bias_london": "NY setups only on London's discount side (long: sweep extreme <= London 02-05 midpoint)",
    "news_after": "Tier-1 day: skip setups triggered before the day's first high-impact release (day left free)",
    "cisd_fail": "before +0.5R / BE: a 5m close below the CISD level and the entry -> out",
    "es_fail": "before +0.5R / BE: ES closes beyond its own extreme of the sweep window -> out",
    "smt_filter": "keep an NQ setup only when ES did NOT make a new 2-hour extreme at NQ's sweep (SMT present)",
    "smt_pick": "SMT present -> trade MES instead of MNQ (ES stop, ES VIX band target), else NQ",
}
PLAIN = {
    "es_filler": "Extra trades on ES (S&P micros) on days Zlarior has not traded yet",
    "be_frac": "Move to breakeven later on far targets, sooner on near ones",
    "fill_limit_close": "Enter with a limit order at the signal candle's close instead of a market order",
    "bias_london": "New York trades only from London's cheap side (longs) / expensive side (shorts)",
    "news_after": "On big-news days, wait for the release before taking a setup",
    "cisd_fail": "Get out when price falls back through the shift level before the trade works",
    "es_fail": "Get out when ES breaks its own low (high) before the trade works",
    "smt_filter": "Only take setups where ES did not make the same new low (SMT divergence)",
    "smt_pick": "When ES held up (SMT), trade ES instead of NQ",
}


# ================================================================================================ ES data
_ES = {}


def es_bars():
    """CME ES1! 5m (data/ES_5m.csv, 2025-04-14 .. 2026-10-16): arrays + time -> index."""
    if not _ES:
        import pandas as pd
        d = pd.read_csv(os.path.join(ROOT, "data", "ES_5m.csv"))
        d.columns = [c.strip().lower() for c in d.columns]
        d = d.sort_values("time").drop_duplicates("time")
        _ES["t"] = d["time"].to_numpy(np.int64)
        for k in ("open", "high", "low", "close"):
            _ES[k[0]] = d[k].to_numpy(float)
        _ES["ix"] = {int(t): i for i, t in enumerate(_ES["t"])}
        mod = np.array([(lambda e: e.hour * 60 + e.minute)(dt.datetime.fromtimestamp(int(t), ET)) for t in _ES["t"]])
        _ES["mod"] = mod
    return _ES


def es_dir(d):
    """(lo, hi, c, o) of ES in direction space (long: as is; short: negated and swapped)."""
    X = es_bars()
    if d == 1:
        return X["l"], X["h"], X["c"], X["o"]
    return -X["h"], -X["l"], -X["c"], -X["o"]


def es_window(t0, t1):
    """ES bar indices with open time in [t0, t1)."""
    X = es_bars()
    a = int(np.searchsorted(X["t"], t0, side="left"))
    b = int(np.searchsorted(X["t"], t1, side="left"))
    return a, b


def smt_present(z, M):
    """SMT at NQ's sweep extreme: ES did NOT make a new 2-hour extreme on the extreme's 5m bar +/- 1 bar (long: the
    lowest ES low of those 3 bars stays above the lowest ES low of the 24 bars before them). None = no ES data."""
    X = es_bars()
    te = int(M.t[z["ext_i"]])
    if te < X["t"][0] or te > X["t"][-1]:
        return None
    lo_d = es_dir(z["dir"])[0]
    a, b = es_window(te - 300, te + 600)
    p, q = es_window(te - 300 - 24 * 300, te - 300)
    if b - a < 3 or q - p < 20:
        return None
    return bool(lo_d[a:b].min() > lo_d[p:q].min())


# ================================================================================================ executor (post-fill)
def manage_v(o, BX, fill, d, entry, stop, tg, s_day, risk, ext=None):
    """tools/lit_lab_ideas.manage_x with options off (== the live executor) + the batch options in o:
      be_frac    {}        be trigger = clip(0.25 x (tg - entry) / risk, 0.5, 2.0) R
      cisd_fail  {"ref"}   ref = the 5m CISD level (direction space): a 5m close < min(ref, entry) before +0.5R / BE -> out
      es_fail    {"es_ref"} ES's extreme (direction space) of the sweep window: an ES 5m close < it before +0.5R / BE -> out
      tgt_through          a target fills only when the bar trades 1 tick through it (honesty check)
      pre        {"skip_mfe_bar": True}  set by fill_limit_close: the fill bar's favourable move is not counted
    Returns (exit kind, pts, worst, mfe, exit k)."""
    o = o or {}
    LV, BE_OFF = E.LIVE, E.BE_OFF
    B = BX.B
    hi_d, lo_d, c_d, o_d = B.dirs(d)
    flat = LV["flat_mod"]
    step = B.secs // 60
    tc = LV.get("t_check") if B.secs == 60 else None
    be_r = LV["be_r"]
    if o.get("be_frac"):
        be_r = min(2.0, max(0.5, 0.25 * (tg - entry) / risk))
    cur, be_done, mfe, worst = stop, False, 0.0, 0.0
    cut = None
    k = fill
    exit_px = kind = None
    es_lo = es_c = es_t = None
    if o.get("es_ref") is not None:
        X = es_bars()
        es_lo, _h, es_c, _o = es_dir(d)
        es_t = X["ix"]
    tg_hit = tg + TICK if o.get("tgt_through") else tg
    while k < B.n:
        if B.day[k] != s_day or B.mod[k] >= 1080:
            k -= 1; exit_px, kind = float(c_d[k]) - SLIP, "EOD"; break
        if cut is not None:
            exit_px, kind = float(o_d[k]) - SLIP, cut; break
        worst = min(worst, lo_d[k] - entry)
        if lo_d[k] <= cur:
            exit_px, kind = cur - SLIP, ("BE" if be_done else "STOP"); break
        mfe = max(mfe, (hi_d[k] - entry) / risk)
        if hi_d[k] >= tg_hit:
            exit_px, kind = tg, "TARGET"; break
        if be_r is not None and not be_done and hi_d[k] >= entry + be_r * risk:
            if entry + BE_OFF > cur:
                cur = entry + BE_OFF
            be_done = True
        if B.mod[k] >= flat:
            exit_px, kind = float(c_d[k]) - SLIP, "EOD"; break
        if tc and not be_done and round((B.t[k] - B.t[fill]) / 60.0) + 1 == int(tc.get("at", 15)) \
                and mfe < float(tc.get("mfe", 0.5)) and c_d[k] < entry - float(tc.get("x", 0.3)) * risk:
            if k + 1 < B.n and B.day[k + 1] == s_day:
                cut = "CUT_T15"
                k += 1
                continue
        nxt = k + 1 < B.n and B.day[k + 1] == s_day
        five_close = B.secs == 300 or (int(B.t[k]) + 60) % 300 == 0          # this bar closes a 5m bar
        if nxt and not be_done and mfe < 0.5 and five_close:
            if o.get("ref") is not None and c_d[k] < min(float(o["ref"]), entry):
                cut = "CISD_FAIL"; k += 1; continue
            if es_lo is not None:
                j = es_t.get(int(B.t[k]) + B.secs - 300)                    # the ES 5m bar closing with this bar
                if j is not None and es_c[j] < float(o["es_ref"]):
                    cut = "ES_FAIL"; k += 1; continue
        k += 1
    if exit_px is None:
        return None
    return kind, exit_px - entry, worst, mfe, k


def _unit(t, B, kx, kind, pts, worst, mfe, entry, risk, tg, extra=None):
    return {"day": t["day"], "entry_t": int(t["entry_t"]), "exit_t": int(B.t[kx]) + B.secs, "dir": t["dir"], "exit": kind,
            "risk": round(risk, 2), "tgt": round(tg - entry, 2), "pts": round(pts, 4), "w1": round(worst, 4),
            "legs": [(1.0, pts)], "mfe": round(mfe, 3), "tf": t["tf"], "m": 1.0, "floored": False, "inst": "NQ",
            **(extra or {})}


def walk(o=None, T=None):
    """Every live trade (or T) re-walked under the manage options o; fill_limit_close changes the entry first."""
    o = o or {}
    c = E.ctx()
    T = T if T is not None else c["T"]
    out = []
    for t in T:
        BX = c[60] if t["tf"] == 1 else c[300]
        B = BX.B
        d = t["dir"]
        fill = int(np.searchsorted(B.t, t["entry_t"]))
        entry, stop, tg = t["entry_px"] * d, t["stop_px"] * d, t["target_px"] * d
        oo = dict(o)
        if o.get("cisd_fail"):
            oo["ref"] = float(E.zc(t)["ref_d"])
        if o.get("es_fail"):
            oo["es_ref"] = es_ref(t)
            if oo["es_ref"] is None:
                oo.pop("es_ref")
        if o.get("fill_limit_close") and t["tf"] == 1 and fill >= 1 and fill + 1 < B.n and B.day[fill + 1] == B.day[fill]:
            hi_d, lo_d, c_d, o_d = B.dirs(d)
            L = float(c_d[fill - 1])                      # the 1m CISD candle's close (direction space)
            if L > stop and lo_d[fill] <= L - TICK:       # filled inside the entry bar (1 tick through)
                risk = L - stop
                if lo_d[fill] <= stop:                    # a stop touch in the fill bar = a full stop-out
                    out.append(_unit(t, B, fill, "STOP", stop - SLIP - L, lo_d[fill] - L, 0.0, L, risk, tg, {"fill": "limit"}))
                    continue
                r = manage_v(oo, BX, fill + 1, d, L, stop, tg, int(B.day[fill]), risk)
                kind, pts, worst, mfe, kx = r
                out.append(_unit(t, B, kx, kind, pts, min(worst, lo_d[fill] - L), mfe, L, risk, tg, {"fill": "limit"}))
                continue
            e2 = float(o_d[fill + 1]) + SLIP              # not filled: market at the next bar's open + 1 tick
            if e2 - stop < 1.0:
                e2 = stop + 1.0
            risk = e2 - stop
            r = manage_v(oo, BX, fill + 1, d, e2, stop, tg, int(B.day[fill]), risk)
            kind, pts, worst, mfe, kx = r
            out.append(_unit(t, B, kx, kind, pts, worst, mfe, e2, risk, tg, {"fill": "chase"}))
            continue
        risk = entry - stop
        kind, pts, worst, mfe, kx = manage_v(oo, BX, fill, d, entry, stop, tg, int(B.day[fill]), risk)
        out.append(_unit(t, B, kx, kind, pts, worst, mfe, entry, risk, tg))
    return out


def es_ref(t):
    """ES's extreme (direction space) from 60 min before NQ's sweep extreme to NQ's fill. None = no ES data."""
    X = es_bars()
    M = E.ctx()["M"]
    z = E.zc(t)
    te = int(M.t[z["ext_i"]])
    if te - 3600 < X["t"][0] or t["entry_t"] > X["t"][-1]:
        return None
    a, b = es_window(te - 3600, int(t["entry_t"]) - 299)          # ES bars closed by the fill
    if b - a < 6:
        return None
    return float(es_dir(t["dir"])[0][a:b].min())


# ================================================================================================ setup filters (engine)
_CAND = {}


def cands():
    if not _CAND:
        M, C = F.market(LIVE["ref"], LIVE["extra_boxes"])
        _CAND["M"], _CAND["C"] = M, C
    return _CAND["M"], _CAND["C"]


def news_first() -> dict:
    """day -> ET minute of the first high-impact US release (data/news/events.csv)."""
    import csv
    out = {}
    with open(NEWS, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if (r.get("impact") or "").lower() != "high":
                continue
            hh, mm = (r.get("time_et") or "0:0").split(":")[:2]
            m = int(hh) * 60 + int(mm)
            out[r["date"]] = min(out.get(r["date"], 10 ** 9), m)
    return out


def skip_keys(name):
    """Candidates the filter skips: [(day, i, dir)]; plus counts."""
    M, C = cands()
    sk = []
    if name == "news_after":
        nf = news_first()
        for z in C:
            m = nf.get(z["day"])
            if m is None:
                continue
            trig_close = (int(M.mod[z["i"]]) + 5)            # the 5m trigger bar's close (ET minute)
            if trig_close <= m and int(M.mod[z["i"]]) < 1080:
                sk.append([z["day"], int(z["i"]), int(z["dir"])])
    elif name == "bias_london":
        for z in C:
            if int(z["mod"]) < 480 or int(z["mod"]) >= 1080:
                continue
            x = M.ctx[z["k"]]
            if "lon25" not in x:
                continue
            hi, lo, _ki = x["lon25"]
            mid = 0.5 * (hi + lo)
            ext = float(z["ext_d"]) * z["dir"]
            ok = ext <= mid if z["dir"] == 1 else ext >= mid
            if not ok:
                sk.append([z["day"], int(z["i"]), int(z["dir"])])
    elif name == "smt_filter":
        for z in C:
            s = smt_present(z, M)
            if s is False:
                sk.append([z["day"], int(z["i"]), int(z["dir"])])
    else:
        raise ValueError(name)
    return sk


def filtered_trades(name):
    sk = skip_keys(name)
    T = F.run({**LIVE, "skip_keys": sk})
    return T, len(sk)


# ================================================================================================ ES trade lists
def es_engine_trades():
    """ES LIT (E3 scaling, 5m execution) trades from the engine (tools/lit_more.es Market + candidates)."""
    if "T" not in _ES:
        from tools import lit_more as LM
        _ES["T"] = LM.run_on("es", {"min_stop": ES_STOP[0], "max_stop": ES_STOP[1], "be_off": ES_BEO, "tf": "5m"})
    return _ES["T"]


def es_unit_from_engine(t):
    q = t["qty"]
    pts = (t["pnl"] + lit.COMM * q) / (lit.PV * q) * ES_X
    w1 = (t["low"] + lit.COMM * q) / (lit.PV * q) * ES_X
    return {"day": t["day"], "entry_t": int(t["entry_t"]), "exit_t": int(t["exit_t"]), "dir": t["dir"], "exit": t["exit"],
            "risk": round(t["risk_pts"] * ES_X, 4), "tgt": round(abs(t["target_px"] - t["entry_px"]) * ES_X, 4),
            "pts": round(pts, 4), "w1": round(min(0.0, w1), 4), "legs": [(1.0, pts)], "mfe": None, "tf": 5, "m": 1.0,
            "floored": False, "inst": "ES", "es_entry": float(t["entry_px"])}


def es_filler(U0):
    """NQ unchanged + ES trades that open while NQ has not traded that day (an NQ entry during an ES trade closes ES
    at the ES 5m open at / after the NQ entry, - 1 tick)."""
    X = es_bars()
    nq_by = collections.defaultdict(list)
    for u in U0:
        nq_by[u["day"]].append(u)
    add, n_pre, n_drop = [], 0, 0
    for t in es_engine_trades():
        if not t["qty"]:
            continue
        u = es_unit_from_engine(t)
        nq = sorted(nq_by.get(u["day"], []), key=lambda x: x["entry_t"])
        if any(x["entry_t"] <= u["entry_t"] for x in nq):
            n_drop += 1
            continue
        first = next((x for x in nq if u["entry_t"] < x["entry_t"] < u["exit_t"]), None)
        if first is not None:                          # NQ preempts: ES closed at market at the ES open at / after it
            d = u["dir"]
            lo_d, hi_d, c_d, o_d = es_dir(d)
            a = int(np.searchsorted(X["t"], u["entry_t"], side="left"))
            b = int(np.searchsorted(X["t"], first["entry_t"], side="left"))
            if b >= len(X["t"]):
                continue
            e = u["es_entry"] * d
            px = float(o_d[b]) - SLIP
            worst = min(0.0, float(lo_d[a:b].min()) - e) if b > a else 0.0
            pts = (px - e) * ES_X
            u.update(exit="PREEMPT", pts=round(pts, 4), w1=round(min(worst * ES_X, pts, 0.0), 4), legs=[(1.0, pts)],
                     exit_t=int(X["t"][b]))
            n_pre += 1
        add.append(u)
    U = sorted(U0 + add, key=lambda x: x["entry_t"])
    return U, {"es_added": len(add), "es_preempted": n_pre, "es_dropped_nq_first": n_drop,
               "es_by_span": {sp: sum(1 for u in add if SPANS[sp][0] <= u["day"] <= SPANS[sp][1]) for sp in SPANS}}


def es_trade_for(t, z, M):
    """The MES trade that replaces NQ trade t (smt_pick), or (None, why)."""
    X = es_bars()
    d = t["dir"]
    lo_d, hi_d, c_d, o_d = es_dir(d)
    a = int(np.searchsorted(X["t"], int(t["entry_t"]), side="left"))
    if a >= len(X["t"]) or X["t"][a] - int(t["entry_t"]) > 600:
        return None, "no ES bar"
    ts = int(M.t[z["sweep_i"]])
    p = int(np.searchsorted(X["t"], ts, side="left"))
    if a - p < 1:
        return None, "no ES sweep window"
    entry = float(o_d[a]) + SLIP
    stop = float(lo_d[p:a].min()) - TICK
    risk = entry - stop
    if not (ES_STOP[0] <= risk <= ES_STOP[1]):
        return None, "ES stop out of range"
    x = _es_ctx().get(t["day"])
    if not x or not x.get("vix_move"):
        return None, "no ES VIX band"
    band = float(x["open18"]) * d + float(x["vix_move"])
    if band - entry < 1.5 * risk:
        return None, "ES target under 1.5R"
    tg = min(band, entry + 8.0 * risk)
    # manage on ES 5m: stop first, then target, BE at +1R -> entry + 0.75, flat 15:55 (the 15:55 bar's close)
    day_end = int(M.t[M.days[z["k"]][2] - 1]) + 300
    cur, be, worst, mfe = stop, False, 0.0, 0.0
    k = a
    kind = px = None
    while k < len(X["t"]) and X["t"][k] < day_end:
        worst = min(worst, lo_d[k] - entry)
        if lo_d[k] <= cur:
            px, kind = cur - SLIP, ("BE" if be else "STOP"); break
        mfe = max(mfe, (hi_d[k] - entry) / risk)
        if hi_d[k] >= tg:
            px, kind = tg, "TARGET"; break
        if not be and hi_d[k] >= entry + risk:
            cur, be = max(cur, entry + ES_BEO), True
        if X["mod"][k] >= LIVE["flat_mod"] and X["mod"][k] < 1080:
            px, kind = float(c_d[k]) - SLIP, "EOD"; break
        k += 1
    if kind is None:
        k = max(a, k - 1)
        px, kind = float(c_d[k]) - SLIP, "EOD"
    pts = (px - entry) * ES_X
    return {"day": t["day"], "entry_t": int(X["t"][a]), "exit_t": int(X["t"][k]) + 300, "dir": d, "exit": kind,
            "risk": round(risk * ES_X, 4), "tgt": round((tg - entry) * ES_X, 4), "pts": round(pts, 4),
            "w1": round(min(0.0, worst * ES_X, pts), 4), "legs": [(1.0, pts)], "mfe": round(mfe, 3), "tf": 5, "m": 1.0,
            "floored": False, "inst": "ES"}, "ok"


def _es_ctx():
    if "ctx" not in _ES:
        from tools import lit_more as LM
        Mes = LM.es()[0]
        _ES["ctx"] = {str(x["date"]): x for x in Mes.ctx}
    return _ES["ctx"]


def smt_pick(U0):
    c = E.ctx()
    M = c["M"]
    out, why = [], collections.Counter()
    by_t = {int(t["entry_t"]): t for t in c["T"]}
    for u in U0:
        t = by_t[u["entry_t"]]
        z = E.zc(t)
        s = smt_present(z, M)
        if not s:
            why["no SMT" if s is False else "no ES data"] += 1
            out.append(u)
            continue
        es, w = es_trade_for(t, z, M)
        why[w] += 1
        out.append(es if es else u)
    return out, dict(why)


# ================================================================================================ scoring
def week_boot(L, L0, n=5000, seed=19):
    """Week-block bootstrap of the weekly LIT-size $ change (variant - base), ISO weeks resampled within each 2026
    half. Returns the share of draws with total change <= 0 (2026, H1, H2) + the real change."""
    def wk(Lx, sp):
        a, z = SPANS[sp]
        w = collections.defaultdict(float)
        for l in Lx:
            if a <= l["day"] <= z:
                w[lit.iso_week(l["day"])] += l["pnl"]
        return w
    rng = np.random.default_rng(seed)
    out, tot = {}, np.zeros(n)
    real = 0.0
    for sp in ("H1", "H2"):
        a, z = SPANS[sp]
        weeks = sorted({lit.iso_week(d) for d in F.SESS if a <= d <= z})
        w1, w0 = wk(L, sp), wk(L0, sp)
        dlt = np.array([w1.get(x, 0.0) - w0.get(x, 0.0) for x in weeks])
        real += float(dlt.sum())
        draws = dlt[rng.integers(0, len(dlt), size=(n, len(dlt)))].sum(axis=1)
        out[sp] = round(float((draws <= 0).mean()), 4)
        tot += draws
    out["2026"] = round(float((tot <= 0).mean()), 4)
    out["real_2026"] = round(real)
    return out


def gate(s, boot) -> dict:
    """G1-G6 of the design files."""
    L, Ev = s["lit"], s["eval"]
    g = {"G1_lit_both": all(s["d_lit"][h] > 0 for h in ("H1", "H2")),
         "G2_eval": all(s["d_eval"][h] > 0 and s["d_f10"][h] <= 0 and s["d_p10"][h] >= -2.0 for h in ("H1", "H2")),
         "G3_2021_25": s["d_lit"]["2021-25"] >= -600,
         "G4_tpw": all(2.0 <= L[h]["tpw"] <= 4.0 for h in ("H1", "H2")),
         "G5_boot": boot["2026"] <= 0.10,
         "G6_funded": all(s["d_fund"][h] >= -10 for h in ("H1", "H2")) if "d_fund" in s else False}
    g["PASS"] = all(g.values())
    return g


def score(name, U, base, L0, info=None):
    n0 = len(U)
    U = [u for u in U if lit.qty_for(u["risk"]) > 0]          # the size rule: under 1 micro = no trade (wide 5m-exec ES fills)
    info = {**(info or {}), "dropped_under_1_micro": n0 - len(U)}
    o, _, L = E.evaluate(U=U, fund=True)
    o["chg"] = E.changed(L, L0)
    s = E.short(o, base)
    boot = week_boot(L, L0)
    s["boot"] = boot
    s["gate"] = gate(s, boot)
    n26 = [u for u in U if u["day"] >= "2026"]
    s["info"] = {**(info or {}), "exits_2026": dict(collections.Counter(u["exit"] for u in n26)),
                 "es_2026": sum(1 for u in n26 if u.get("inst") == "ES")}
    s["desc"] = DESC.get(name, name)
    s["plain"] = PLAIN.get(name, name)
    s["batch"] = 1 if name in BATCH1 else 2 if name in BATCH2 else 0
    print(E.line(name, s), "| boot", boot, "| PASS" if s["gate"]["PASS"] else "| fail", flush=True)
    return s


def units_for(name, U0):
    if name in ("be_frac", "cisd_fail", "es_fail", "fill_limit_close", "tgt_through"):
        return walk({name: True}), {}
    if name in ("bias_london", "news_after", "smt_filter"):
        T, nsk = filtered_trades(name)
        info = {"skipped_cands": nsk,
                "n_trades": {sp: sum(1 for t in T if SPANS[sp][0] <= t["day"] <= SPANS[sp][1]) for sp in SPANS}}
        return walk({}, T=T), info
    if name == "es_filler":
        return es_filler(U0)
    if name == "smt_pick":
        U, why = smt_pick(U0)
        return U, {"why": why}
    raise ValueError(name)


def run(names=None):
    E.ctx()
    base, U0, L0 = E.evaluate({}, fund=True)
    bs = E.short(base)
    res = {"base": bs, "_cfg": {"room_f": A.CFG["two_week"]["room_f"], "two_week_until": A.CFG.get("two_week_until"),
                                "design": ["research/lit/more_money_design_batch1.md", "research/lit/more_money_design_batch2.md"]}}
    print(E.line("base", bs), flush=True)
    U0w = walk({})
    for nm in (names or IDEAS):
        U, info = units_for(nm, U0w)
        res[nm] = score(nm, U, base, L0, info)
    # honesty check (not an idea): a target needs 1 tick through
    U, _ = units_for("tgt_through", U0w)
    res["check_tgt_through"] = score("tgt_through", U, base, L0, {"note": "honesty check, not an idea"})
    res["fills_real"] = real_fills()
    res["count"] = {"batch1": len(BATCH1), "batch2": len(BATCH2), "total": len(IDEAS),
                    "passed": [k for k in IDEAS if k in res and res[k]["gate"]["PASS"]]}
    json.dump(res, open(OUT, "w"), indent=1, default=float)
    lab_rows(res)
    print("passed:", res["count"]["passed"])
    return res


def real_fills():
    """The two real Zlarior fills found (published trades / the PC's trade rows) vs the backtest's fill model."""
    return [{"day": "2026-10-28", "side": "SHORT", "qty": 5, "bar_open": 29945.25, "model_entry": 29945.00, "real_entry": 29945.00,
             "signal_close": 29945.75, "stop_exit_model": 29987.75, "stop_exit_real": 29987.75, "ticks_worse_than_model": 0,
             "source": "tools/web_public/trading/trades.json live.lit.2026-10-28_0343_short + PC 1m bars"},
            {"day": "2026-11-16", "side": "LONG", "qty": 1, "bar_open": 27798.50, "model_entry": 27798.75, "real_entry": 27799.50,
             "signal_close": 27799.25, "ticks_worse_than_model": 3,
             "source": "data/pc_days/2026-11-16 trades (leg fill_px) + PC 1m bars; the exit row is model-booked"}]


def months(sp):
    a, z = SPANS[sp]
    return sum(1 for d in F.SESS if a <= d <= z) / 21.0


def lab_rows(res):
    rows = []
    for nm in IDEAS:
        s = res.get(nm)
        if not s:
            continue
        L, Ev, Fu = s["lit"], s["eval"], s.get("fund", {})
        rows.append({"id": f"lit_more_{nm}", "bot": "lit", "kind": "lit_more_money", "batch": s["batch"], "title": s["plain"],
                     "rule": s["desc"], "status": "candidate" if s["gate"]["PASS"] else "rejected",
                     "per_month": {"H1": L["H1"]["per_month"], "H2": L["H2"]["per_month"], "2021-25": L["2021-25"]["per_month"]},
                     "d_per_month": {h: round(s["d_lit"][h] / months(h)) for h in ("H1", "H2", "2021-25")},
                     "tpw": {h: L[h]["tpw"] for h in ("H1", "H2", "2021-25")},
                     "pf": {h: L[h]["pf"] for h in ("H1", "H2", "2021-25")},
                     "dd": {h: L[h]["dd"] for h in ("H1", "H2", "2021-25")},
                     "eval": {h: {"per_month": Ev[h]["per_month"], "p10": Ev[h]["p10"], "f10": Ev[h]["f10"],
                                  "pass_med": Ev[h]["pass_med"]} for h in ("H1", "H2")},
                     "funded_per_month": {h: Fu.get(h, {}).get("per_month") for h in ("H1", "H2", "REF")},
                     "boot_p": s["boot"]["2026"], "gate": s["gate"],
                     "source": "tools/lit_more_money.py, research/writeups/lit-more-money-2026-11-19.md"})
    b = res["base"]
    doc = {"v": 1, "date": "2026-11-19", "kind": "lit_more_money", "bot": "lit",
           "about": "Zlarior (LIT) more-money ideas, pre-registered in 2 batches (research/lit/more_money_design_batch1/2.md), "
                    "one fixed version each, costs in; gate G1-G6 (both 2026 halves better at the LIT size and on the eval "
                    "path, 2021-25 not worse, 2-4 trades a week, week-block bootstrap <= 0.10, funded 50K not lower)",
           "base": {"per_month": {h: b["lit"][h]["per_month"] for h in ("H1", "H2", "2021-25")},
                    "eval": {h: {"per_month": b["eval"][h]["per_month"], "p10": b["eval"][h]["p10"], "f10": b["eval"][h]["f10"]}
                             for h in ("H1", "H2")},
                    "funded_per_month": {h: b["fund"][h]["per_month"] for h in ("H1", "H2", "REF")}},
           "count": res["count"], "rows": rows}
    json.dump(doc, open(LAB, "w"), indent=1, default=float)


# ================================================================================================ checks
def check() -> int:
    U0 = E.trades({})
    W = walk({})
    bad = sum(1 for a, b in zip(U0, W) if a["exit"] != b["exit"] or abs(a["pts"] - b["pts"]) > 1e-6)
    print(f"check: {len(W)} trades, {bad} differ from tools/lit_edge.trades (options off)")
    M, C = cands()
    s = collections.Counter(smt_present(z, M) for z in C if z["day"] >= "2025-04-15")
    c = E.ctx()
    st = collections.Counter(smt_present(E.zc(t), c["M"]) for t in c["T"] if t["day"] >= "2025-04-15")
    print("SMT on candidates since 2025-04-15:", dict(s), "| on live trades:", dict(st))
    nf = news_first()
    print("Tier-1 days:", len(nf), "first", min(nf), "last", max(nf))
    return 0 if bad == 0 else 1


def gap():
    """Live vs backtest twin since the eval start on today's bars (data/NQ_*.csv incl. the PC's bars after Oct 16)."""
    M, C = cands()
    days = [d for d, s, e in M.days if d >= "2026-10-19"]
    T = lit.run_x(M, C, LIVE, days, B1=F.bars(M, "1m"), B5=F.bars(M, "5m"))
    rows = []
    for t in T:
        rows.append({"day": t["day"], "et": dt.datetime.fromtimestamp(t["entry_t"], ET).strftime("%H:%M"), "entry_t": t["entry_t"],
                     "side": "LONG" if t["dir"] == 1 else "SHORT", "exit": t["exit"], "r": round(float(t["r"]), 2),
                     "qty_lit": t["qty"], "pnl_lit": t["pnl"], "risk_pts": t["risk_pts"]})
        print(rows[-1])
    return rows


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "check":
        raise SystemExit(check())
    if cmd == "run":
        run(sys.argv[2:] or None)
    elif cmd == "gap":
        gap()
    else:
        print(__doc__)
