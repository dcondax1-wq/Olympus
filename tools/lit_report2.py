"""LIT report coverage, second pass: the codable rules and clock/data requirements of the owner's LIT Complete Report
(2026-10-18) that neither LIT live nor the first-pass agent (tools/lit_report.py) tested.

Owner order 2026-10-18: "make sure EVERYTHING in the report is extracted for the bot". Judged like every LIT change: picked on
2026 H1 (Jan-Jun), checked on 2026 H2 (Jul-Oct 16); adopt-candidate only if BOTH halves improve and 2+ trades a week stay.
2021-25 is a reference line. Inventory: research/lit/report_inventory.md; write-up: research/writeups/lit-report-coverage.md.

Wraps engine/lit.py (not edited). core() is lit._run_core(live=False) with default-off hooks; sim() is lit.simulate_x
(live=False) with default-off execution options. With no option set both reproduce run lit_live (live_model.json "lit"):
120 trades in 2026, +$41,734 (`check`).

  python tools/lit_report2.py check     # core() == lit_final.run(P_live)
  python tools/lit_report2.py test      # every variant -> research/lit/report2_results.json
  python tools/lit_report2.py facts     # evidence numbers (Wilson interval, break-even win rate, holidays, rolls, sessions)
  python tools/lit_report2.py save      # store the runs lit_rep2_* (rl.save, family other, tags lit, lit_report2)
1 CPU process.
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import math
import os
import sys
from zoneinfo import ZoneInfo

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import lit  # noqa: E402
from tools import lit_final as F  # noqa: E402
from tools import runlib as rl  # noqa: E402

OUT = os.path.join(ROOT, "research", "lit", "report2_results.json")
TICK, PV, COMM = lit.TICK, lit.PV, lit.COMM
P_LIVE = {**lit.DEFAULTS, **json.load(open(os.path.join(ROOT, "live_model.json"), encoding="utf-8"))["lit"]}
ET = ZoneInfo("America/New_York")
MAJOR = {"pd", "pw", "pm", "gap"}          # ch.7 strength tiers: prior day / week / month extremes and opening gaps
MEDIUM = {"asia", "london", "ny", "pre", "x_ny"}   # session boxes; "buildup" (equal highs / lows) = minor


# ================================================================================================ executor (copy + options)
def sim(M, B, cand, entry_px, tgt, stop, P, O):
    """lit.simulate_x(live=False) with execution options O (all default off):
      slip       extra adverse points on the market entry and on stop / breakeven / end-of-day exits (ch.22 stress)
      tgt_thru   a target fills only when price trades this many points THROUGH it (ch.22: a touch is not a fill)
      tap_thru   the limit tap counts only when price trades this many points through the limit (ch.22)
      news       sorted unix times of high-impact releases: an open position is closed at the open of the first bar that
                 starts at or after release - lead (ReimFX: close before NFP / avoid news, ch.18 / 26)
      lead       seconds before the release (default 300)
      prog       (seconds, min_r): exit at the bar open once `seconds` have passed since the fill and the best point so far is
                 below min_r (ch.16 time exit for a trade that has not progressed)"""
    SLIP = lit.SLIP + O.get("slip", 0.0)
    tthru = O.get("tgt_thru", 0.0)
    pthru = O.get("tap_thru", 0.0)
    news = O.get("news")
    lead = O.get("lead", 300)
    prog = O.get("prog")
    mt = None
    d = cand["dir"]
    if O.get("mt_cancel"):                 # ch.8 mean threshold of the CISD run (the order block body), direction space
        _h, _l, _c, _o = (M.h, M.l, M.c, M.o) if d == 1 else (-M.l, -M.h, -M.c, -M.o)
        a_, z_ = int(cand["ref_i"]), int(cand["ext_i"]) + 1
        bt = np.maximum(_c[a_:z_], _o[a_:z_]); bb = np.minimum(_c[a_:z_], _o[a_:z_])
        mt = 0.5 * (float(bt.max()) + float(bb.min()))
    hi_d, lo_d, c_d, o_d = B.dirs(d)
    t0 = int(M.t[cand["entry_i"]])
    k0 = int(np.searchsorted(B.t, t0))
    s_day = int(M.day_of[cand["entry_i"]])
    if k0 >= B.n:
        return None
    flat = P["flat_mod"]
    wait_s = P["wait"] * 300
    cis = P.get("cisd1m")
    if cis and B.secs == 300:
        cis = max(1, cis // 5)
    tgt_cancel = entry_px + tgt[1] if tgt[0] == "pts" else tgt[1]
    limit_fill = True
    fill = tapped = None
    k = k0
    while k < B.n:
        if B.day[k] != s_day or B.mod[k] >= flat or B.mod[k] >= 1080:
            break
        if tapped is None and B.t[k] >= t0 + wait_s:
            break
        if lo_d[k] <= stop:
            if tapped is None and lo_d[k] <= entry_px - pthru and not cis:
                fill = k; entry = min(entry_px, float(o_d[k]))
            break
        if tapped is None and lo_d[k] <= entry_px - pthru:
            if cis:
                tapped = k
            else:
                fill = k; entry = min(entry_px, float(o_d[k])); break
        if tapped is None and hi_d[k] >= tgt_cancel:
            break
        if tapped is not None:
            if k - tapped > cis:
                break
            if mt is not None and c_d[k] < mt:      # a close through the block's mean threshold cancels the setup
                break
            lowk = tapped + int(np.argmin(lo_d[tapped:k + 1]))
            cz = lit._cisd_level(c_d, o_d, lowk)
            if cz is not None and k > lowk and c_d[k] > cz[0] and k + 1 < B.n and B.day[k + 1] == s_day:
                fill = k + 1; entry = float(o_d[k + 1]) + SLIP; limit_fill = False; break
        k += 1
    if fill is None:
        return None
    risk = entry - stop
    if risk <= 0:
        return None
    if tgt[0] == "pts":
        tg = entry + tgt[1]
    else:
        if tgt[2]:
            tg = entry + P["fallback_rr"] * risk
        else:
            dist = tgt[1] - entry
            if dist < P["min_rr"] * risk:
                return None
            tg = entry + (min(dist, P["max_rr"] * risk) if P["max_rr"] else dist)
    q = lit.qty_for(risk)
    if q < 1:
        return None
    be_r = P["be_r"]
    cur, be_done, mfe, mae, worst = stop, False, 0.0, 0.0, 0.0
    nx = None
    if news is not None:
        j = int(np.searchsorted(news, int(B.t[fill]) + lead, side="right"))   # first release more than `lead` after the fill
        nx = news[j] - lead if j < len(news) else None
    t_fill = int(B.t[fill])
    k = fill
    exit_px = kind = None
    while k < B.n:
        if B.day[k] != s_day or B.mod[k] >= 1080:
            k -= 1; exit_px, kind = float(c_d[k]) - SLIP, "EOD"; break
        if k > fill and nx is not None and B.t[k] >= nx:
            exit_px, kind = float(o_d[k]) - SLIP, "NEWS"; break
        if k > fill and prog and B.t[k] - t_fill >= prog[0] and mfe < prog[1]:
            exit_px, kind = float(o_d[k]) - SLIP, "TIME"; break
        mae = max(mae, (entry - lo_d[k]) / risk)
        worst = min(worst, lo_d[k] - entry)
        if lo_d[k] <= cur:
            exit_px, kind = cur - SLIP, ("BE" if be_done else "STOP"); break
        if not (k == fill and limit_fill):
            mfe = max(mfe, (hi_d[k] - entry) / risk)
            if hi_d[k] >= tg + tthru:
                exit_px, kind = tg, "TARGET"; break
            if be_r is not None and not be_done and hi_d[k] >= entry + be_r * risk:
                cur, be_done = entry, True
        if B.mod[k] >= flat:
            exit_px, kind = float(c_d[k]) - SLIP, "EOD"; break
        k += 1
    if exit_px is None:
        return None
    pnl = (exit_px - entry) * PV * q - COMM * q
    low = min(0.0, worst * PV * q - COMM * q, pnl)
    xi5 = int(np.searchsorted(M.t, B.t[k], side="right") - 1)
    ei5 = int(np.searchsorted(M.t, B.t[fill], side="right") - 1)
    return {"day": cand["day"], "entry_t": int(B.t[fill]), "exit_t": int(B.t[k]) + B.secs, "exit_i": xi5, "dir": d,
            "r": round(pnl / (risk * PV * q), 3), "pnl": round(pnl, 2), "risk_pts": round(risk, 2), "qty": q,
            "risk_usd": round(risk * PV * q, 2), "half": False, "exit": kind, "trigger": "LIT-" + ("1m" if B.secs == 60 else "5m"),
            "mfe": round(mfe, 3), "mae": round(min(mae, 1.0 + SLIP / risk), 3), "bars_held": int(k - fill + 1), "regime": "",
            "mult": 1.0, "low": round(low, 2), "entry_px": round(entry * d, 2), "stop_px": round(stop * d, 2),
            "target_px": round(tg * d, 2), "swept": cand["swept"], "ind_n": cand["ind_n"], "vec": cand["vec"], "i": cand["i"],
            "ext_i": cand["ext_i"], "ref_i": cand["ref_i"], "sweep_i": cand["sweep_i"], "entry_i": ei5, "tf": B.secs // 60}


def core(M, cands, P, sessions, B1, B5, X=None):
    """lit._run_core(live=False) plus hooks in X (all default off): skip(M, z) -> True drops the setup (the day stays free);
    mult(M, z) -> size multiplier (one rounding with the weekly stop, floor 1 micro); O = sim() execution options."""
    X = X or {}
    O = X.get("O") or {}
    P = {**lit.DEFAULTS, **(P or {})}
    names = set(P["sweep_names"]) if P.get("sweep_names") else None
    sset = set(sessions) if sessions else None
    out, busy, per_day = [], -1, collections.Counter()
    buf = P["stop_buf"]
    for z in cands:
        if sset is not None and z["day"] not in sset:
            continue
        if z["entry_i"] <= busy or per_day[z["day"]] >= P["max_per_day"]:
            continue
        if not lit.setup_ok(z, P, names):
            continue
        if P.get("monday") and lit.monday_block(M, z):
            continue
        if X.get("skip") and X["skip"](M, z):
            continue
        ep = min(float(z["ref_d"]), z["trig_c"])
        stop = z["ext_d"] - buf
        risk = ep - stop
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
        use1 = P["tf"] == "1m" and B1 is not None and int(M.day_of[z["entry_i"]]) in B1.full
        B = B1 if use1 else B5
        tgt = ("lvl", ep + tp, fb) if P.get("cisd1m") else ("pts", tp)
        t = sim(M, B, z, ep, tgt, stop, P, O)
        if t is None:
            continue
        busy = t["exit_i"]; per_day[z["day"]] += 1
        m = P["how_out"] if (P["how_out"] != 1.0 and not z["how"]) else 1.0
        if P.get("wk_stop"):
            n_st, m_st = P["wk_stop"]
            if lit.week_stops(z["day"], t["entry_t"], out) >= n_st:
                m *= float(m_st)
        if X.get("mult"):
            m *= float(X["mult"](M, z))
        if m != 1.0:
            t = lit.scale_trade(t, m)
        out.append(t)
    return out


_S = {}


def base(key="live"):
    """(M, C, B1, B5) for the live detector; key "dst" = the London 03:00-04:00 box moved to 04:00-05:00 ET in the weeks the
    US and Europe are out of step (ReimFX's window is 09:00-10:00 Berlin, ch.12 / 28); "tolX" = build-up tolerance X ATR."""
    if key in _S:
        return _S[key]
    if key == "live":
        M, C = F.market(P_LIVE["ref"], P_LIVE["extra_boxes"])
    elif key == "dst":
        M = lit.Market(extra_boxes=list(P_LIVE["extra_boxes"]))
        n = dst_patch(M)
        print("DST London box moved on", n, "days", flush=True)
        C = lit.candidates(M, ref=P_LIVE["ref"])
    elif key.startswith("tol"):
        M = lit.Market(tol_atr=float(key[3:]), extra_boxes=list(P_LIVE["extra_boxes"]))
        C = lit.candidates(M, ref=P_LIVE["ref"])
    else:
        raise ValueError(key)
    _S[key] = (M, C, F.bars(M, "1m"), F.bars(M, "5m"))
    return _S[key]


def run(X=None, P=None, key="live"):
    M, C, B1, B5 = base(key)
    return core(M, C, {**P_LIVE, **(P or {})}, F.SESS, B1, B5, X)


def tkey(T):
    return [(t["day"], t["entry_t"], round(t["pnl"], 2), t["exit"], t["qty"]) for t in sorted(T, key=lambda t: t["entry_t"])]


def check():
    A = F.run(P_LIVE)
    Bt = run()
    a26 = [t for t in A if t["day"] >= "2026"]
    ok = tkey(A) == tkey(Bt)
    print("lit_live:", len(a26), round(sum(t["pnl"] for t in a26)), "| core():", sum(t["day"] >= "2026" for t in Bt),
          round(sum(t["pnl"] for t in Bt if t["day"] >= "2026")), "| identical:", ok, flush=True)
    return ok


# ================================================================================================ features (all causal)
def dst_mismatch(day):
    """True when 09:00 Berlin is 04:00 New York (US on summer time, Europe not yet / no longer)."""
    d = dt.date.fromisoformat(str(day))
    b = dt.datetime(d.year, d.month, d.day, 9, 0, tzinfo=ZoneInfo("Europe/Berlin"))
    return b.astimezone(ET).hour == 4


def dst_patch(M):
    """Rebuild the lon34 box (03:00-04:00 ET) as 04:00-05:00 ET on mismatch days. Returns the number of days changed."""
    n = 0
    for k, (d, s, e) in enumerate(M.days):
        x = M.ctx[k]
        if "lon34" not in x or not dst_mismatch(d):
            continue
        md = M.mod[s:e]
        ii = np.flatnonzero((md >= 240) & (md < 300))
        if len(ii) >= 2:
            x["lon34"] = (float(M.h[s + ii].max()), float(M.l[s + ii].min()), int(s + ii[-1]))
            n += 1
    return n


def tiers(z):
    cls = set(z["swept_cls"])
    return "major" if cls & MAJOR else "medium" if cls & MEDIUM else "minor"


def pd_eq_side(M, z, which="pd"):
    """ch.11 premium / discount of a completed range: +1 = the limit price is on the premium side of the range midpoint for
    the trade (a long above it), -1 discount, 0 no range. which: pd (prior day), pw (prior week), asia18 (18:00-24:00 box)."""
    x = M.ctx[z["k"]]
    if which in ("pd", "pw"):
        if which + "h" not in x:
            return 0
        hi, lo = x[which + "h"], x[which + "l"]
    else:
        if which not in x or x[which][2] >= z["i"]:
            return 0
        hi, lo = x[which][0], x[which][1]
    ep = min(float(z["ref_d"]), z["trig_c"]) * z["dir"]           # price space
    mid = 0.5 * (hi + lo)
    return 1 if (ep - mid) * z["dir"] > 0 else -1


def news_times(kinds=None):
    """Unix times of high-impact releases (data/news/events.csv), optionally only those whose name contains one of kinds."""
    import csv
    out = []
    for r in csv.DictReader(open(os.path.join(ROOT, "data", "news", "events.csv"), encoding="utf-8")):
        if (r.get("impact") or "").lower() != "high":
            continue
        if kinds and not any(k.lower() in r["event"].lower() for k in kinds):
            continue
        try:
            hh, mm = (int(v) for v in r["time_et"].split(":"))
        except Exception:
            continue
        d = dt.date.fromisoformat(r["date"])
        out.append(int(dt.datetime(d.year, d.month, d.day, hh, mm, tzinfo=ET).timestamp()))
    return np.array(sorted(set(out)), dtype=np.int64)


_ROLL = None


def unadj(t, px):
    """Unadjusted (traded-contract) price of a back-adjusted NQ1! price at unix time t (data/NQ_rolls.json)."""
    global _ROLL
    if _ROLL is None:
        R = json.load(open(os.path.join(ROOT, "data", "NQ_rolls.json")))["rolls"]
        _ROLL = (np.array([r["switch_t"] for r in R]), np.array([r["gap"] for r in R], float))
    st, gp = _ROLL
    return px - float(gp[st > t].sum())


def round_swept(M, z, step=100.0):
    """ch.3 round numbers: the sweep excursion (from the nearest swept level to the extreme) crossed a multiple of `step`
    in the traded contract's (unadjusted) price."""
    if not z.get("sw"):
        return False
    d = z["dir"]
    t = int(M.t[z["ext_i"]])
    lev = unadj(t, max(z["sw"].values()) * d)
    ext = unadj(t, z["ext_d"] * d)
    lo, hi = min(lev, ext), max(lev, ext)
    return math.floor(hi / step) * step >= lo


# ================================================================================================ variants
def V():
    S = collections.OrderedDict()
    sk = lambda fn: {"skip": fn}
    half = lambda fn: {"mult": lambda M, z: 0.5 if fn(M, z) else 1.0}
    nlev = lambda z: len(set(z["swept"]))
    # ch.7 ETM final liquidity sweep: a sweep across at least two levels
    S["final sweep: skip unless 2+ levels swept"] = ("ch7 ETM final sweep", sk(lambda M, z: nlev(z) < 2), {})
    S["final sweep: half size with 1 level"] = ("ch7 ETM final sweep", half(lambda M, z: nlev(z) < 2), {})
    S["final sweep: skip unless 3+ levels swept"] = ("ch7 ETM final sweep", sk(lambda M, z: nlev(z) < 3), {})
    # ch.7 minor / medium / major strength tiers
    S["tiers: skip minor-only sweeps (build-ups only)"] = ("ch7 strength tiers", sk(lambda M, z: tiers(z) == "minor"), {})
    S["tiers: half size on minor-only sweeps"] = ("ch7 strength tiers", half(lambda M, z: tiers(z) == "minor"), {})
    S["tiers: half size unless a major level (PD/PW/PM/gap) was swept"] = ("ch7 strength tiers", half(lambda M, z: tiers(z) != "major"), {})
    S["tiers: skip unless a major level was swept"] = ("ch7 strength tiers", sk(lambda M, z: tiers(z) != "major"), {})
    # ch.11 premium / discount of a completed range (the first pass did the leg; earlier studies the opens and NWOG)
    for w in ("pd", "pw", "asia18"):
        S[f"discount: skip premium side of the {w} range"] = ("ch11 range premium/discount", sk(lambda M, z, w=w: pd_eq_side(M, z, w) == 1), {})
        S[f"discount: half size on the premium side of the {w} range"] = ("ch11 range premium/discount", half(lambda M, z, w=w: pd_eq_side(M, z, w) == 1), {})
    # ch.16 / 21 time exits
    for hh, mm in ((11, 0), (12, 0), (13, 30)):
        S[f"time exit: flat at {hh:02d}:{mm:02d} ET (no new entry after)"] = ("ch21 time exit", {}, {"flat_mod": hh * 60 + mm})
    for mins, r in ((60, 0.5), (120, 0.5), (120, 1.0), (240, 1.0)):
        S[f"time exit: out after {mins} min if the best point < {r}R"] = ("ch16 no-progress exit", {"O": {"prog": (mins * 60, r)}}, {})
    # ch.18 / 26 news (ReimFX: gaps pass stops, close before NFP)
    S["news: close an open trade 5 min before any high-impact release"] = ("ch26 news exit", {"O": {"news": "all", "lead": 300}}, {})
    S["news: close an open trade 5 min before NFP / CPI / FOMC"] = ("ch26 news exit", {"O": {"news": "big", "lead": 300}}, {})
    S["news: close an open trade 5 min before NFP only"] = ("ch26 news exit", {"O": {"news": "nfp", "lead": 300}}, {})
    # ch.21 / ReimFX stop buffer
    S["stop: 2 ticks beyond the sweep extreme (ch.21)"] = ("ch21 stop buffer", {}, {"stop_buf": 0.5})
    S["stop: 4 ticks beyond the sweep extreme"] = ("ch21 stop buffer", {}, {"stop_buf": 1.0})
    # ch.12 / 28 clocks: the ReimFX London window in Berlin time across DST
    S["clock: London 09:00-10:00 Berlin box, DST-correct"] = ("ch28 DST London box", {"key": "dst"}, {})
    # ch.3 equal highs / lows tolerance (build-up levels)
    S["equal highs/lows tolerance 0.10 ATR (live 0.15)"] = ("ch3 EQH/EQL tolerance", {"key": "tol0.1"}, {})
    S["equal highs/lows tolerance 0.25 ATR (live 0.15)"] = ("ch3 EQH/EQL tolerance", {"key": "tol0.25"}, {})
    # ch.3 round numbers (unadjusted contract prices)
    for st in (100.0, 50.0):
        S[f"round number: skip unless the sweep crossed a {st:g}-pt round number"] = ("ch3 round numbers", sk(lambda M, z, st=st: not round_swept(M, z, st)), {})
        S[f"round number: half size unless the sweep crossed a {st:g}-pt round number"] = ("ch3 round numbers", half(lambda M, z, st=st: not round_swept(M, z, st)), {})
    # ch.8 mean threshold invalidation of the order block (the CISD run) while waiting for the 1m confirmation
    S["order block: cancel on a close through its mean threshold"] = ("ch8 mean threshold", {"O": {"mt_cancel": True}}, {})
    # ch.22 execution sensitivity (evidence, not adopt-able)
    S["stress: target must trade 1 tick through"] = ("ch22 execution stress", {"O": {"tgt_thru": TICK}}, {})
    S["stress: limit tap must trade 1 tick through"] = ("ch22 execution stress", {"O": {"tap_thru": TICK}}, {})
    S["stress: +1 tick slippage on market entries and stop exits"] = ("ch22 execution stress", {"O": {"slip": TICK}}, {})
    S["stress: +2 ticks slippage on market entries and stop exits"] = ("ch22 execution stress", {"O": {"slip": 2 * TICK}}, {})
    S["stress: all three (1-tick through on targets and taps, +2 ticks slippage)"] = (
        "ch22 execution stress", {"O": {"tgt_thru": TICK, "tap_thru": TICK, "slip": 2 * TICK}}, {})
    return S


_NEWS = {}


def resolve(X):
    X = dict(X)
    key = X.pop("key", "live")
    if "O" in X and isinstance(X["O"].get("news"), str):
        k = X["O"]["news"]
        if k not in _NEWS:
            _NEWS[k] = news_times(None if k == "all" else ["non-farm", "cpi", "fomc"] if k == "big" else ["non-farm"])
        X["O"] = {**X["O"], "news": _NEWS[k]}
    return X, key


def h(s):
    return (f"n={s['n']} {s['tpw']}/wk win {s['win']}% PF {s['pf']} net {s['net']:+,} (${s['per_month']:,}/mo) DD {s['dd']:,} "
            f"eval 2wk {s['p10']}/{s['f10']} 1mo {s['p20']}/{s['f20']} pass rate {s['pass_rate']}%")


def test(only=None):
    res = json.load(open(OUT)) if os.path.exists(OUT) else {}
    T0 = run()
    b = F.score(T0)
    res["_base"] = {"name": "lit_live", **b}
    print("BASE", F.fmt(b), flush=True)
    for nm, (fam, X, P) in V().items():
        if only and only not in nm:
            continue
        XX, key = resolve(X)
        T = run(XX, P, key)
        o = F.score(T)
        d1 = o["H1"]["net"] - b["H1"]["net"]; d2 = o["H2"]["net"] - b["H2"]["net"]
        both = d1 > 0 and d2 > 0 and o["H1"]["tpw"] >= 2.0 and o["H2"]["tpw"] >= 2.0
        ex = collections.Counter(t["exit"] for t in T if t["day"] >= "2026")
        res[nm] = {"family": fam, **o, "dH1": d1, "dH2": d2, "both": both, "exits_2026": dict(ex)}
        print(f"{nm:72s} dH1={d1:+7,} dH2={d2:+7,} both={both} | H1 {o['H1']['tpw']}/wk PF {o['H1']['pf']} | H2 {o['H2']['tpw']}/wk "
              f"PF {o['H2']['pf']} | 2026 DD {o['2026']['dd']:,} 2w {o['2026']['p10']}/{o['2026']['f10']} pr {o['2026']['pass_rate']} "
              f"| 21-25 PF {o['2021-25']['pf']} {o['2021-25']['net']:+,}", flush=True)
        json.dump(res, open(OUT, "w"), indent=1, default=str)
    return res


# ================================================================================================ evidence facts
def wilson(k, n, z=1.96):
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    w = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return round(100 * (c - w), 1), round(100 * (c + w), 1)


def facts():
    M, C, B1, B5 = base()
    T = [t for t in run() if t["day"] >= "2026"]
    n = len(T)
    wins = [t["pnl"] for t in T if t["pnl"] > 0]
    loss = [-t["pnl"] for t in T if t["pnl"] < 0]
    W, L = float(np.mean(wins)), float(np.mean(loss))
    o = {"n": n, "wins": len(wins), "losses": len(loss), "scratch": n - len(wins) - len(loss),
         "win_pct": round(100 * len(wins) / n, 1), "wilson95": wilson(len(wins), n),
         "avg_win": round(W), "avg_loss": round(L), "payoff": round(W / L, 2),
         "breakeven_win_pct": round(100 * L / (W + L), 1), "expectancy": round(sum(t["pnl"] for t in T) / n)}
    # same for each half, and without the 3 best trades
    for nm, a, z in (("H1", "2026-01-01", "2026-06-30"), ("H2", "2026-07-01", "2026-12-31")):
        TT = [t for t in T if a <= t["day"] <= z]
        w = sum(t["pnl"] > 0 for t in TT)
        o[nm] = {"n": len(TT), "win_pct": round(100 * w / len(TT), 1), "wilson95": wilson(w, len(TT))}
    # robustness table rows the report asks for (ch.22): side, entry session, exit kind, VIX level
    def grp(fn):
        g = collections.defaultdict(list)
        for t in T:
            g[fn(t)].append(t["pnl"])
        return {k: {"n": len(v), "net": round(sum(v)), "pf": round(sum(x for x in v if x > 0) / max(1e-9, -sum(x for x in v if x < 0)), 2)}
                for k, v in sorted(g.items())}

    def sess(t):
        m = dt.datetime.fromtimestamp(t["entry_t"], ET)
        mm = m.hour * 60 + m.minute
        return "02-05 London" if mm < 300 else "05-08 pre-NY" if mm < 480 else "08-09:30 NY open" if mm < 570 else "09:30-12 RTH am" if mm < 720 else "12-15:30 RTH pm"
    vix = {M.ctx[k]["date"]: M.ctx[k].get("vix") for k in range(len(M.days))}
    o["by_side"] = grp(lambda t: "long" if t["dir"] == 1 else "short")
    o["by_session"] = grp(sess)
    o["by_exit"] = grp(lambda t: t["exit"])
    o["by_vix"] = grp(lambda t: "VIX<16" if (vix.get(t["day"]) or 0) < 16 else "VIX 16-20" if vix[t["day"]] < 20 else "VIX>=20")
    # news exposure: trades open across a high-impact release
    nt = news_times()
    o["open_across_release"] = int(sum(1 for t in T if ((nt > t["entry_t"]) & (nt < t["exit_t"])).any()))
    nfp = news_times(["non-farm"])
    o["open_across_nfp"] = int(sum(1 for t in T if ((nfp > t["entry_t"]) & (nfp < t["exit_t"])).any()))
    # holiday / early-close days and roll days traded
    from engine.lit_live import early_close
    o["early_close_trades"] = [(t["day"], early_close(t["day"])) for t in T if early_close(t["day"])]
    rolls = json.load(open(os.path.join(ROOT, "data", "NQ_rolls.json")))
    o["rolls_file"] = rolls if isinstance(rolls, (list, dict)) and len(str(rolls)) < 2000 else str(rolls)[:400]
    # DST mismatch days traded and the London box
    o["dst_mismatch_trade_days"] = [t["day"] for t in T if dst_mismatch(t["day"])]
    print(json.dumps(o, indent=1, default=str))
    res = json.load(open(OUT)) if os.path.exists(OUT) else {}
    res["_facts"] = o
    json.dump(res, open(OUT, "w"), indent=1, default=str)
    return o


# ================================================================================================ store runs
def rid_of(nm):
    """Run id: lit_rep2_<n>_<slug>, n = the variant's position in V() (so truncated slugs never collide)."""
    n = list(V()).index(nm) + 1
    slug = "".join(ch if ch.isalnum() else "_" for ch in nm.lower())
    while "__" in slug:
        slug = slug.replace("__", "_")
    return f"lit_rep2_{n:02d}_" + slug.strip("_")[:44].strip("_")


def save(only=None):
    res = json.load(open(OUT))
    b = res["_base"]
    for nm, (fam, X, P) in V().items():
        r = res.get(nm)
        if not r or (only and only not in nm):
            continue
        rid = rid_of(nm)
        XX, key = resolve(X)
        T = run(XX, P, key)
        S = rl.score(T, F.SESS)
        o = {k: r[k] for k in ("H1", "H2", "2026", "2021-25")}
        status = "adopt-candidate" if r["both"] else ("info" if fam.startswith("ch22") else "rejected")
        rl.save(rid, "LIT live + report rule: " + nm, "other",
                "Owner order 2026-10-18: is every codable rule of the LIT Complete Report tested on LIT live (2026 H1 pick, H2 check)?",
                params={**P_LIVE, **P, "report_rule": nm, "chapter": fam}, trades=T, scored=S, status=status,
                verdict=(f"{'BOTH halves better' if r['both'] else ('execution stress (evidence)' if fam.startswith('ch22') else 'rejected')}: "
                         f"dH1 {r['dH1']:+,} dH2 {r['dH2']:+,}. 2026 H1 (pick) {h(o['H1'])}; 2026 H2 (check) {h(o['H2'])}; "
                         f"2026 {h(o['2026'])}; 2021-25 reference only {h(o['2021-25'])}"),
                notes="tools/lit_report2.py core()/sim() = engine/lit.py _run_core/simulate_x copies with default-off hooks; base "
                      f"lit_live (live_model.json lit) H1 {b['H1']['net']:+,} H2 {b['H2']['net']:+,}.",
                writeup="lit-report-coverage", tags=["lit", "lit_report2"])
        print("saved", rid, flush=True)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    arg = sys.argv[2] if len(sys.argv) > 2 else None
    {"check": check, "test": lambda: test(arg), "facts": facts, "save": lambda: save(arg)}[cmd]()
