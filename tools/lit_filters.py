"""LIT research, dimension FILTERS AND CONFLUENCES (owner order 2026-10-18: LIT is the strategy, tuned and judged on 2026 only).

Starts from lit_A (tools/research_lit.py CAND["A"]) and tests, one change at a time and then the best few together:
  * displacement size (body / ATR), body share of the bar, the displacement leaving a fair value gap
  * sweep depth (min / max, in ATR)
  * PVSRA vector / climax candles on the sweep bar, the displacement, either one
  * VIX implied one-day move: sweep distance from the 18:00 / 00:00 open in moves, target room, VIX-level size
  * NWOG / NDOG: entry side of the gap midpoint, sweeps of a gap edge
  * SMT with ES (ES 5m starts 2025-04, so all of 2026 is covered): ES fails to take its own copy of the swept level (or its
    own swing low) while NQ sweeps it; as a filter or a size boost
  * day of week (size or skip), high-impact news days (data/news/events.csv + ff_archive.csv) and a news guard around releases
  * volatility regime: previous-day range vs the 5-day average, 5-day vs 60-day range, VIX level

Nothing in engine/lit.py is edited. FiltMarket / ESMarket subclass lit.Market; annotate_filters() adds features to the
lit.candidates() dicts; run_f() is lit.run (verified identical for lit_A) plus a post-target hook and a size multiplier.

Overfitting guard: every setting is picked on 2026 H1 (Jan-Jun), checked on 2026 H2 (Jul-Oct 16). 2021-25 is a reference line
only (never a gate). Size changes are preferred over skips (owner rule), and every variant reports trades/week.

  python tools/lit_filters.py search     # every variant -> research/lit/filters_results.json (+ printed table)
  python tools/lit_filters.py save       # store the best 5 with rl.save (ids lit_filters_*, family other, tag lit)
  python tools/lit_filters.py table      # markdown table of every variant (for research/lit/filters.md)
"""
from __future__ import annotations

import bisect
import collections
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import data as edata  # noqa: E402
from engine import lit  # noqa: E402
from engine.analytics import PLANS, simulate_eval  # noqa: E402
from tools import runlib as rl  # noqa: E402
from tools import research_lit as R  # noqa: E402

OUT = os.path.join(ROOT, "research", "lit", "filters_results.json")
SESS_ALL = R.SESS
S26 = [d for d in SESS_ALL if d >= "2026-01-01"]
S_H1 = [d for d in S26 if d <= "2026-06-30"]
S_H2 = [d for d in S26 if d >= "2026-07-01"]
S_REF = [d for d in SESS_ALL if "2021-01-01" <= d <= "2025-12-31"]
LIT_A = R.CAND["A"]


# ------------------------------------------------------------------------------------------------ ES market (for SMT)
class ESMarket(lit.Market):
    """lit.Market built on CME ES1! 5m instead of NQ (same components, so ES has its own session boxes / PDH / PDL...)."""

    def __init__(self, tol_atr=0.15):
        orig = lit.load
        lit.load = lambda sym, tf: edata.load("ES", tf)
        try:
            super().__init__(tol_atr=tol_atr)
        finally:
            lit.load = orig


# ------------------------------------------------------------------------------------------------ news
def news_table():
    """High-impact releases per date: {date: [ET minute, ...]} from events.csv (official calendars) + ff_archive.csv."""
    out = collections.defaultdict(set)
    for fn in ("events.csv", "ff_archive.csv"):
        p = os.path.join(edata.DATA_DIR, "news", fn)
        if not os.path.exists(p):
            continue
        df = pd.read_csv(p)
        for _, r in df.iterrows():
            if str(r.get("impact", "")).strip().lower() != "high":
                continue
            try:
                hh, mm = str(r["time_et"]).split(":")
                m = int(hh) * 60 + int(mm)
            except Exception:
                continue
            if m >= 1080:          # an evening release belongs to the next trading day (18:00 -> 17:00)
                d = (pd.Timestamp(r["date"]) + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
            else:
                d = str(r["date"])
            out[d].add(m)
    return {d: sorted(v) for d, v in out.items()}


# ------------------------------------------------------------------------------------------------ features
TICKS2 = 0.5
def annotate_filters(M, C, E=None):
    """Adds to every candidate (all values known at the trigger bar close or at entry):
      disp_br     body / range of the largest-body bar of the displacement
      fvg_atr     largest fair value gap the displacement left (direction space, ATR units; 0 = none)
      vec_sweep_any  climax or above-average vector on the extreme (sweep) bar
      vix, vix_ext00  VIX level; sweep distance from the midnight open in VIX moves (18:00 anchor before midnight)
      vix_move, open18_d  for the target-room check (direction space)
      nwog_side / ndog_side  +1 entry on the long side of the gap midpoint (above for longs, below for shorts), -1 the other, 0 none
      gap_pts_w / gap_pts_d  NWOG / NDOG size in points
      smt_lvl / smt_sw  ES did NOT take its copy of the swept level (lvl) / its own prior swing (sw) while NQ swept: True/False/None
      news_day, news_dist  high-impact release on the trading day; minutes from entry to the nearest release (signed)
      pr_ratio, rg_ratio  previous-day range / avg of the 5 days before it; 5-day avg range / 60-day avg range
    """
    o, h, l, c, at = M.o, M.h, M.l, M.c, M.atr
    rng = np.array([float(h[s:e].max() - l[s:e].min()) for _, s, e in M.days])
    NEWS = news_table()
    CLX = np.flatnonzero(M.climax)
    if E is not None:
        e_idx = {int(t): i for i, t in enumerate(E.t)}
        e_day = {d: k for k, (d, s, e) in enumerate(E.days)}
    for z in C:
        d = z["dir"]; ee, i, ei, k = z["ext_i"], z["i"], z["entry_i"], z["k"]
        hi_d, lo_d, c_d, o_d = (h, l, c, o) if d == 1 else (-l, -h, -c, -o)
        seg = np.arange(ee + 1, i + 1)
        if len(seg):
            body = c_d[seg] - o_d[seg]
            j = int(seg[int(np.argmax(body))])
            z["disp_br"] = round(float((c_d[j] - o_d[j]) / max(h[j] - l[j], 1e-9)), 3)
        else:
            z["disp_br"] = 0.0
        g = 0.0
        for j in range(ee + 2, i + 1):
            g = max(g, float(lo_d[j] - hi_d[j - 2]))
        z["fvg_atr"] = round(max(g, 0.0) / max(at[i], 1e-9), 3)
        z["vec_sweep_any"] = bool(M.climax[ee] or M.above[ee])
        # unrecovered PVSRA climax zones (candle bodies) above the entry (direction space), formed before the sweep extreme
        # in the last 1 / 3 sessions (288 / 864 bars), not traded through by the trigger bar: list of (bottom, top)
        for nmz, L in (("vz1", 288), ("vz3", 864)):
            a0 = bisect.bisect_left(CLX, i - L); a1 = bisect.bisect_left(CLX, ee)
            zs = []
            for j in CLX[a0:a1]:
                j = int(j)
                bot, top = sorted((float(o_d[j]), float(c_d[j])))
                if top - bot < TICKS2 or bot < z["entry_d"] - lit.SLIP:
                    continue
                if hi_d[j + 1:i + 1].max() >= top:
                    continue
                zs.append((round(bot, 2), round(top, 2)))
            z[nmz] = zs
        x = M.ctx[k]
        z["vix"] = x.get("vix")
        vm = x.get("vix_move")
        z["vix_move"] = vm
        z["open18_d"] = x["open18"] * d
        o00 = M.open_00[ee]
        if vm and not np.isnan(o00):
            z["vix_ext00"] = round((o00 * d - lo_d[ee]) / (vm * o00 / x["open18"]), 3)
        else:
            z["vix_ext00"] = z["vix_ext"]
        ent = z["entry_d"] * d
        for gk, nm in (("nwog", "w"), ("ndog", "d")):
            gv = x.get(gk)
            if gv:
                mid = 0.5 * (gv[0] + gv[1])
                z[f"{gk}_side"] = 1 if (ent - mid) * d > 0 else -1
                z[f"gap_pts_{nm}"] = round(gv[1] - gv[0], 2)
            else:
                z[f"{gk}_side"] = 0
                z[f"gap_pts_{nm}"] = 0.0
        # SMT with ES
        z["smt_lvl"] = z["smt_sw"] = None
        if E is not None:
            ek = e_day.get(z["day"])
            ie, ii_, isb = e_idx.get(int(M.t[ee])), e_idx.get(int(M.t[i])), e_idx.get(int(M.t[z["sweep_i"]]))
            if ek is not None and ie is not None and ii_ is not None and isb is not None:
                elo = E.l if d == 1 else -E.h
                ex = E.ctx[ek]; es_ = ex["s"]
                win_lo = float(elo[min(isb, ie):ii_ + 1].min())          # ES's extreme from NQ's sweep to the trigger
                # level SMT: ES copies of the swept session boxes / daily levels
                took, have = [], 0
                for nm in z["swept"]:
                    base = nm[:-2] if nm.endswith(("_h", "_l")) else None
                    lv = None
                    if base in lit.SESSIONS and base in ex:
                        hi_, lo_, ki = ex[base]
                        lv = (lo_ if d == 1 else -hi_, ki)
                    elif nm in ("pdl", "pwl", "pml", "pdh", "pwh", "pmh") and nm[:2] + "h" in ex:
                        v = ex[nm[:2] + ("l" if d == 1 else "h")]
                        lv = (v * d, es_ - 1)
                    if lv is None:
                        continue
                    have += 1
                    pv, ki = lv
                    prior = elo[max(ki + 1, es_ - 600):min(isb, ie)]
                    if len(prior) and prior.min() < pv:   # ES had already taken it before NQ's sweep: ES led, not SMT
                        took.append(True); continue
                    took.append(win_lo < pv)
                if have:
                    z["smt_lvl"] = not all(took)
                # swing SMT: ES's low from the sweep to the trigger vs ES's low over the 24 bars before the sweep
                a = max(es_, min(isb, ie) - 24)
                if min(isb, ie) - a >= 3:
                    z["smt_sw"] = bool(win_lo > float(elo[a:min(isb, ie)].min()))
        # news
        ev = NEWS.get(z["day"], [])
        z["news_day"] = bool(ev)
        z["news_dist"] = min((z["mod"] - m for m in ev), key=abs) if ev else None
        # volatility regime (known at the 18:00 open of the day)
        z["pr_ratio"] = round(float(rng[k - 1] / max(rng[k - 6:k - 1].mean(), 1e-9)), 3) if k >= 6 else None
        z["rg_ratio"] = round(float(rng[k - 5:k].mean() / max(rng[k - 60:k].mean(), 1e-9)), 3) if k >= 60 else None
    return C


# ------------------------------------------------------------------------------------------------ executor
def scale(t, m):
    q0 = t["qty"]
    q = max(1, int(q0 * m + 1e-9)) if m < 1 else min(lit.MAX_MICROS, int(q0 * m + 1e-9))
    f = q / q0
    per = (t["pnl"] + lit.COMM * q0) / q0
    x = dict(t)
    x.update(qty=q, pnl=round(per * q - lit.COMM * q, 2), risk_usd=round(t["risk_usd"] * f, 2), half=f < 1, mult=round(f, 3),
             low=round(t["low"] * f, 2))
    return x


def run_f(M, C, cfg, sessions, post=None, size=None):
    """lit.run plus: post(z, tp, risk, ep) -> bool after the target is chosen (False = not this candidate), and
    size(z, tp, ep) -> multiplier on the micros (applied after the fill, so the trade sequence is lit.run's)."""
    filt = cfg.get("filt") or (lambda z: True)
    sset = set(sessions) if sessions else None
    out, busy, per_day = [], -1, collections.Counter()
    buf = cfg.get("stop_buf", 2.0)
    for z in C:
        if sset is not None and z["day"] not in sset:
            continue
        if z["entry_i"] <= busy or per_day[z["day"]] >= cfg.get("max_per_day", 1):
            continue
        if not filt(z):
            continue
        mode = cfg.get("entry", "market")
        ep = lit.entry_price(z, mode, buf)
        risk = ep - (z["ext_d"] - buf)
        if not (cfg.get("min_stop", 8.0) <= risk <= cfg.get("max_stop", 60.0)):
            continue
        zz = z
        if mode != "market":
            sh = z["entry_d"] - ep
            zz = {**z, "targets": {kk: [x + sh for x in v] for kk, v in z["targets"].items()}}
        tp = lit.pick_target(zz, risk, cfg.get("classes", R.ALL_CLS), cfg.get("min_rr", 1.5), cfg.get("max_rr", 5.0),
                             cfg.get("fixed_rr"), cfg.get("fallback_rr"))
        if tp is None:
            continue
        if post is not None and not post(z, tp, risk, ep):
            continue
        t = lit.simulate(M, z, tp, buf, cfg.get("be_r"), cfg.get("time_bars"), cfg.get("time_min_r", 0.0), entry_mode=mode,
                         wait=cfg.get("wait", 12))
        if t is None:
            continue
        busy = t["exit_i"]; per_day[z["day"]] += 1
        if size is not None:
            m = float(size(z, tp, ep))
            if m != 1.0:
                t = scale(t, m)
        out.append(t)
    return out


# ------------------------------------------------------------------------------------------------ variants
def build(v):
    """v: dict of filter / size settings on top of lit_A. Returns (cfg, post, size)."""
    base = {**LIT_A, **{k: v[k] for k in ("disp", "depth", "vec", "vix") if k in v}}
    cfg = R.make(**base)
    f0 = cfg["filt"]

    def filt(z):
        if not f0(z):
            return False
        if "br" in v and z["disp_br"] < v["br"]:
            return False
        if "fvg" in v and z["fvg_atr"] < v["fvg"]:
            return False
        if v.get("vsweep") and not z["vec_sweep_any"]:
            return False
        if v.get("vec_either") and not (z["vec"] or z["vec_sweep_any"]):
            return False
        if "vix00" in v:
            ve = z["vix_ext00"]
            if ve is None or ve >= v["vix00"]:
                return False
        if "nwog_side" in v and z["nwog_side"] == -v["nwog_side"] and not (v.get("nwog_how_ok") and z["how"]):
            return False
        if "ndog_side" in v and z["ndog_side"] == -v["ndog_side"]:
            return False
        if "smt" in v:
            sv = z["smt_lvl"] if v["smt"] == "lvl" else z["smt_sw"] if v["smt"] == "sw" else (
                z["smt_lvl"] if z["smt_lvl"] is not None else z["smt_sw"])
            if sv is False:     # None (no ES data / no copy level) does not block
                return False
        if "dow_skip" in v and z["dow"] in v["dow_skip"]:
            return False
        if v.get("news_skip") and z["news_day"]:
            return False
        if "news_guard" in v and z["news_dist"] is not None and -2 <= z["news_dist"] <= v["news_guard"]:
            return False
        if "pr_max" in v and z["pr_ratio"] is not None and z["pr_ratio"] > v["pr_max"]:
            return False
        if "rg_band" in v and z["rg_ratio"] is not None and not (v["rg_band"][0] <= z["rg_ratio"] < v["rg_band"][1]):
            return False
        if "vix_max" in v and z["vix"] is not None and z["vix"] > v["vix_max"]:
            return False
        if v.get("es_conf") == "strict" and z["smt_lvl"] is not False:
            return False      # ES must have swept its own copy of the level too (no SMT divergence)
        if v.get("es_conf") == "loose" and z["smt_lvl"] is True:
            return False      # block only a known divergence
        if "how_only" in v and not z["how"]:
            return False
        return True

    cfg["filt"] = filt
    for k in ("min_rr", "max_rr", "be_r", "max_stop", "min_stop", "max_per_day"):
        if k in v:
            cfg[k] = v[k]

    posts = []
    if "vix_room" in v:
        def p_room(z, tp, risk, ep, k2=v["vix_room"]):
            vm = z["vix_move"]
            if not vm:
                return True
            return ep + tp <= z["open18_d"] + k2 * vm
        posts.append(p_room)
    if v.get("vz_skip"):
        def p_vz(z, tp, risk, ep, key=v["vz_skip"]):
            return not any(ep < bot < ep + tp for bot, top in z[key])
        posts.append(p_vz)
    post = (lambda z, tp, risk, ep: all(f(z, tp, risk, ep) for f in posts)) if posts else None
    vz_size = v.get("vz_size")

    def size(z, tp=None, ep=None):
        m = 1.0
        if "vix_size" in v and z["vix"] is not None:
            a, b = v["vix_size"]
            m *= 1.0 if z["vix"] < 20 else a if z["vix"] < 30 else b
        if "smt_size" in v:
            sv = z["smt_lvl"] if z["smt_lvl"] is not None else z["smt_sw"]
            if sv is True:
                m *= v["smt_size"][0]
            elif sv is False:
                m *= v["smt_size"][1]
        if "dow_size" in v:
            m *= v["dow_size"].get(z["dow"], 1.0)
        if "news_size" in v and z["news_day"]:
            m *= v["news_size"]
        if "pr_size" in v and z["pr_ratio"] is not None and z["pr_ratio"] > v["pr_size"][0]:
            m *= v["pr_size"][1]
        if "vec_size" in v:
            m *= v["vec_size"][0] if z["vec"] else v["vec_size"][1]
        if "fvg_size" in v:
            m *= v["fvg_size"][0] if z["fvg_atr"] >= v["fvg_size"][2] else v["fvg_size"][1]
        if "disp_size" in v:
            m *= v["disp_size"][1] if z["disp"] >= v["disp_size"][0] else 1.0
        if "depth_size" in v:
            m *= v["depth_size"][1] if z["depth_atr"] >= v["depth_size"][0] else 1.0
        if "vixext_size" in v and z["vix_ext"] is not None:
            m *= v["vixext_size"][1] if z["vix_ext"] >= v["vixext_size"][0] else 1.0
        if "gap_size" in v:
            m *= v["gap_size"] if z["nwog_side"] == 1 else 1.0
        if "gap2_size" in v:       # NWOG + NDOG discount count: 2 -> 1.0, 1 -> a, 0 -> b (no gap counts as discount)
            nd = (z["nwog_side"] != 1) + (z["ndog_side"] != 1)
            m *= 1.0 if nd == 2 else v["gap2_size"][0] if nd == 1 else v["gap2_size"][1]
        if "es_size" in v:          # ES did NOT take its copy of the level (SMT divergence) -> x
            m *= v["es_size"] if z["smt_lvl"] is True else 1.0
        if "how_size" in v and not z["how"]:
            m *= v["how_size"]
        if vz_size and tp is not None and any(ep < bot < ep + tp for bot, top in z[vz_size[0]]):
            m *= vz_size[1]
        return m

    return cfg, post, size


# ------------------------------------------------------------------------------------------------ scoring
KEYS = ("n", "tpw", "wk2", "win", "pf", "net", "per_month", "dd", "p10", "f10", "p20", "f20", "dec10", "pass_med", "b2b")


def pass_rate(days, horizon=60):
    plan = PLANS["builder_50k"]
    pn = [d["pnl"] for d in days]; lo = [d["low"] for d in days]
    p = f = 0
    for i in range(len(days)):
        r = simulate_eval(pn[i:i + horizon], plan, lo[i:i + horizon])["result"]
        p += r == "PASS"; f += r == "FAIL"
    return round(100 * p / (p + f), 1) if p + f else None


def score_all(T):
    out = {}
    for nm, sess, span in (("h1", S_H1, "2026"), ("h2", S_H2, "2026"), ("y26", S26, "2026"), ("ref", S_REF, "2021-25")):
        ss = set(sess)
        TT = [t for t in T if t["day"] in ss]
        S = rl.score(TT, sess)
        s = S["spans"][span]
        o = {k: s.get(k) for k in KEYS}
        o["pass_rate"] = pass_rate(S["days"]) if s.get("n") else None
        out[nm] = o
    return out


def fmt(s):
    if not s.get("n"):
        return "no trades"
    return (f"n={s['n']} tpw={s['tpw']} wk2={s['wk2']}% win={s['win']}% PF={s['pf']} net={s['net']:+,} (${s['per_month']:,}/mo) "
            f"DD={s['dd']:,} 2w {s['p10']}/{s['f10']} 1m {s['p20']}/{s['f20']} passrate {s['pass_rate']}% med {s['pass_med']}")


def short(s):
    if not s.get("n"):
        return "-"
    return f"n={s['n']:3d} tpw={s['tpw']:.2f} PF={s['pf']} net={s['net']:+6,} DD={s['dd']:,}"


# ------------------------------------------------------------------------------------------------ data
def load_all():
    M, C = R.market()
    E = ESMarket()
    annotate_filters(M, C, E)
    return M, C


def selftest(M, C):
    T0 = lit.run(M, C, R.make(**LIT_A), SESS_ALL)
    cfg, post, size = build({})
    T1 = run_f(M, C, cfg, SESS_ALL, post, size)
    a = [(t["day"], t["entry_t"], t["pnl"]) for t in T0]; b = [(t["day"], t["entry_t"], t["pnl"]) for t in T1]
    print("selftest lit_A:", len(a), len(b), "identical" if a == b else "DIFFERENT", flush=True)
    return a == b


def run_v(M, C, v):
    cfg, post, size = build(v)
    return run_f(M, C, cfg, SESS_ALL, post, size)


# ------------------------------------------------------------------------------------------------ the search
def stage1():
    """One change at a time on top of lit_A (group, name, settings, kind)."""
    V = collections.OrderedDict()
    V["lit_A"] = ("base", {}, "-")
    # displacement
    for x in (0.8, 1.2, 1.5):
        V[f"disp{x}"] = ("displacement", {"disp": x}, "filter")
    V["br0.6"] = ("displacement", {"br": 0.6}, "filter")
    V["br0.7"] = ("displacement", {"br": 0.7}, "filter")
    V["fvg0"] = ("displacement", {"fvg": 1e-6}, "filter")
    V["fvg0.25"] = ("displacement", {"fvg": 0.25}, "filter")
    V["fvg_size"] = ("displacement", {"fvg_size": (1.0, 0.5, 0.25)}, "size")
    V["disp1.5_size"] = ("displacement", {"disp_size": (1.5, 1.25)}, "size")
    # sweep depth
    for lo, hi in ((0.25, 99), (0.75, 99), (1.0, 99), (0.5, 2.0), (0.5, 3.0)):
        V[f"depth{lo}_{hi}"] = ("depth", {"depth": (lo, hi)}, "filter")
    V["depth1.5_size"] = ("depth", {"depth_size": (1.5, 0.5)}, "size")
    # vectors
    V["vec_climax"] = ("vector", {"vec": "climax"}, "filter")
    V["vec_any"] = ("vector", {"vec": "any"}, "filter")
    V["vec_sweep"] = ("vector", {"vsweep": True}, "filter")
    V["vec_either"] = ("vector", {"vec_either": True}, "filter")
    V["vec_size"] = ("vector", {"vec_size": (1.0, 0.5)}, "size")
    # VIX
    for k in (0.3, 0.5, 0.75, 1.0):
        V[f"vix18_{k}"] = ("vix", {"vix": (-9, k)}, "filter")
    V["vix00_0.5"] = ("vix", {"vix00": 0.5}, "filter")
    V["vix00_0.75"] = ("vix", {"vix00": 0.75}, "filter")
    V["vixroom1.0"] = ("vix", {"vix_room": 1.0}, "filter")
    V["vixroom1.5"] = ("vix", {"vix_room": 1.5}, "filter")
    V["vix_size"] = ("vix", {"vix_size": (0.75, 0.5)}, "size")
    V["vixext_size0.5"] = ("vix", {"vixext_size": (0.5, 0.5)}, "size")
    # gaps
    V["nwog_side"] = ("gaps", {"nwog_side": 1}, "filter")
    V["nwog_against"] = ("gaps", {"nwog_side": -1}, "filter")
    V["ndog_side"] = ("gaps", {"ndog_side": 1}, "filter")
    V["nwog_size"] = ("gaps", {"gap_size": 0.5}, "size")
    # SMT
    V["smt_lvl"] = ("smt", {"smt": "lvl"}, "filter")
    V["smt_sw"] = ("smt", {"smt": "sw"}, "filter")
    V["smt_any"] = ("smt", {"smt": "any"}, "filter")
    V["smt_size"] = ("smt", {"smt_size": (1.25, 1.0)}, "size")
    V["smt_size_half"] = ("smt", {"smt_size": (1.0, 0.5)}, "size")
    # day of week
    for dd, nm in enumerate(("mon", "tue", "wed", "thu", "fri")):
        V[f"skip_{nm}"] = ("weekday", {"dow_skip": {dd}}, "filter")
    V["monfri_half"] = ("weekday", {"dow_size": {0: 0.5, 4: 0.5}}, "size")
    # news
    V["news_skip"] = ("news", {"news_skip": True}, "filter")
    V["news_half"] = ("news", {"news_size": 0.5}, "size")
    V["news_guard5"] = ("news", {"news_guard": 5}, "filter")
    V["news_guard15"] = ("news", {"news_guard": 15}, "filter")
    V["news_guard60"] = ("news", {"news_guard": 60}, "filter")
    # volatility regime
    for r in (1.8, 2.0, 2.5):
        V[f"pr_half{r}"] = ("vol regime", {"pr_size": (r, 0.5)}, "size")
    V["pr_skip2.0"] = ("vol regime", {"pr_max": 2.0}, "filter")
    V["rg_0.8_1.3"] = ("vol regime", {"rg_band": (0.8, 1.3)}, "filter")
    V["rg_lt1.2"] = ("vol regime", {"rg_band": (0, 1.2)}, "filter")
    V["rg_gt0.8"] = ("vol regime", {"rg_band": (0.8, 99)}, "filter")
    V["vix_max25"] = ("vol regime", {"vix_max": 25}, "filter")
    return V


def evaluate(M, C, V, res=None):
    res = {} if res is None else res
    for nm, (grp, v, kind) in V.items():
        T = run_v(M, C, v)
        S = score_all(T)
        res[nm] = {"group": grp, "kind": kind, "v": _ser(v), **S}
        print(f"{nm:18s} H1 {short(S['h1']):46s} | H2 {short(S['h2']):46s} | 26 {short(S['y26']):46s} | ref {short(S['ref'])}",
              flush=True)
    return res


def _ser(v):
    return {k: (sorted(x) if isinstance(x, set) else list(x) if isinstance(x, tuple) else
                {str(a): b for a, b in x.items()} if isinstance(x, dict) else x) for k, x in v.items()}


def better_h1(r, b):
    """Selection rule on H1 only: higher PF and higher net than lit_A, 2+ trades a week."""
    h, bh = r["h1"], b["h1"]
    return (h.get("n") and (h["pf"] or 0) > (bh["pf"] or 0) and h["net"] > bh["net"] and (h["tpw"] or 0) >= 2.0)


def main_search():
    M, C = load_all()
    assert selftest(M, C)
    V = stage1()
    res = evaluate(M, C, V)
    json.dump(res, open(OUT, "w"), indent=1)
    b = res["lit_A"]
    print("\nH1 winners (PF and net above lit_A, tpw >= 2), with the H2 check:")
    for nm, r in res.items():
        if better_h1(r, b):
            ok = (r["h2"]["pf"] or 0) > (b["h2"]["pf"] or 0) and r["h2"]["net"] > b["h2"]["net"]
            print(f"  {nm:18s} H1 PF {r['h1']['pf']} {r['h1']['net']:+,} | H2 PF {r['h2']['pf']} {r['h2']['net']:+,} "
                  f"{'HOLDS' if ok else 'fails H2'}")


def stage2_list():
    """Second round: variants of what held in both 2026 halves in round 1 (NWOG discount, ES confirmation), the PVSRA
    vector-zone obstacle, the high/low-of-week window as size, weekday size, and frequency recovery."""
    V = collections.OrderedDict()
    for a in (0.25, 0.75):
        V[f"nwog_size{a}"] = ("gaps", {"gap_size": a}, "size")
    V["gap2_size"] = ("gaps", {"gap2_size": (0.75, 0.5)}, "size")
    V["gap2_size_b"] = ("gaps", {"gap2_size": (1.0, 0.5)}, "size")
    V["es_conf"] = ("smt", {"es_conf": "strict"}, "filter")
    V["es_conf_loose"] = ("smt", {"es_conf": "loose"}, "filter")
    V["es_div_half"] = ("smt", {"es_size": 0.5}, "size")
    V["vz1_skip"] = ("vector", {"vz_skip": "vz1"}, "filter")
    V["vz3_skip"] = ("vector", {"vz_skip": "vz3"}, "filter")
    V["vz1_half"] = ("vector", {"vz_size": ("vz1", 0.5)}, "size")
    V["vz3_half"] = ("vector", {"vz_size": ("vz3", 0.5)}, "size")
    V["how_half"] = ("weekday", {"how_size": 0.5}, "size")
    V["tuethu_half"] = ("weekday", {"dow_size": {1: 0.5, 3: 0.5}}, "size")
    V["nwog_ag+disp0.8"] = ("gaps", {"nwog_side": -1, "disp": 0.8}, "filter")
    V["nwog_ag+depth0.25"] = ("gaps", {"nwog_side": -1, "depth": (0.25, 99)}, "filter")
    return V


def stage3_list():
    """Combinations of the changes that raised PF in BOTH 2026 halves on their own (picked on H1, checked on H2)."""
    NA, NS, HH, TT, BR = {"nwog_side": -1}, {"gap_size": 0.5}, {"how_size": 0.5}, {"dow_size": {1: 0.5, 3: 0.5}}, {"br": 0.6}
    V = collections.OrderedDict()
    V["C_na+how"] = ("combo", {**NA, **HH}, "filter+size")
    V["C_ns+how"] = ("combo", {**NS, **HH}, "size")
    V["C_ns25+how"] = ("combo", {"gap_size": 0.25, **HH}, "size")
    V["C_na+how+br"] = ("combo", {**NA, **HH, **BR}, "filter+size")
    V["C_na+br"] = ("combo", {**NA, **BR}, "filter")
    V["C_how+br"] = ("combo", {**HH, **BR}, "filter+size")
    V["C_ns+how+tt"] = ("combo", {**NS, **HH, **TT}, "size")
    V["C_na+how+tt"] = ("combo", {**NA, **HH, **TT}, "filter+size")
    V["C_na+tt"] = ("combo", {**NA, **TT}, "filter+size")
    V["C_how+tt"] = ("combo", {**HH, **TT}, "size")
    # frequency recovery for C_na+how (2.0 trades/week is the floor)
    V["C_na+how+pd2"] = ("combo", {**NA, **HH, "max_per_day": 2}, "filter+size")
    V["C_na+how+disp0.9"] = ("combo", {**NA, **HH, "disp": 0.9}, "filter+size")
    V["C_na(out-how)+how"] = ("combo", {**NA, **HH, "nwog_how_ok": True}, "filter+size")
    return V


def stage3():
    M, C = load_all()
    res = json.load(open(OUT))
    evaluate(M, C, stage3_list(), res)
    json.dump(res, open(OUT, "w"), indent=1)


def stage2():
    M, C = load_all()
    res = json.load(open(OUT))
    V = stage2_list()
    evaluate(M, C, V, res)
    json.dump(res, open(OUT, "w"), indent=1)


# ------------------------------------------------------------------------------------------------ best runs, checks, table
BEST = collections.OrderedDict([
    ("lit_filters_na_how", ("LIT filters: lit_A + NWOG discount side + half size outside the high/low-of-week window",
                            {"nwog_side": -1, "how_size": 0.5}, "promising")),
    ("lit_filters_na_how_d09", ("LIT filters: lit_A + NWOG discount + HOW size, displacement >= 0.9 ATR (more trades)",
                                {"nwog_side": -1, "how_size": 0.5, "disp": 0.9}, "promising")),
    ("lit_filters_na_how_pd2", ("LIT filters: lit_A + NWOG discount + HOW size, up to 2 trades a day",
                                {"nwog_side": -1, "how_size": 0.5, "max_per_day": 2}, "info")),
    ("lit_filters_ns_how", ("LIT filters, size only: half size on the NWOG premium side and outside the HOW window",
                            {"gap_size": 0.5, "how_size": 0.5}, "info")),
    ("lit_filters_how_half", ("LIT filters: lit_A + half size outside the high/low-of-week window", {"how_size": 0.5}, "info")),
])


def slip_extra(T, ticks=2):
    return [{**t, "pnl": round(t["pnl"] - ticks * lit.TICK * lit.PV * t["qty"], 2)} for t in T]


def robust():
    M, C = load_all()
    base = {"nwog_side": -1, "how_size": 0.5}
    for nm, (title, v, st) in BEST.items():
        T = run_v(M, C, v)
        S = score_all(T)
        print(f"=== {nm}: {v}")
        for k in ("h1", "h2", "y26", "ref"):
            print(f"  {k:4s} {fmt(S[k])}")
        Q = score_all(slip_extra(T))
        print(f"  +2 ticks: H1 {short(Q['h1'])} | H2 {short(Q['h2'])} | 26 {short(Q['y26'])}")
        mo = collections.defaultdict(float)
        for t in T:
            if t["day"] >= "2026":
                mo[t["day"][:7]] += t["pnl"]
        print("  2026 months:", {k: round(x) for k, x in sorted(mo.items())})
        L = [t for t in T if t["dir"] == 1]; Sh = [t for t in T if t["dir"] == -1]
        print(f"  longs 26 {short(score_all(L)['y26'])} | shorts 26 {short(score_all(Sh)['y26'])}")
    print("=== neighbours of lit_filters_na_how")
    for k, tw in (("how0.25", {"how_size": 0.25}), ("how0.75", {"how_size": 0.75}), ("disp1.1", {"disp": 1.1}),
                  ("depth0.4", {"depth": (0.4, 99)}), ("depth0.6", {"depth": (0.6, 99)}), ("ndog_too", {"ndog_side": -1}),
                  ("no_how", {"how_size": 1.0})):
        S = score_all(run_v(M, C, {**base, **tw}))
        print(f"  {k:9s} H1 {short(S['h1'])} | H2 {short(S['h2'])} | 26 {short(S['y26'])} | ref {short(S['ref'])}")


def save_best():
    M, C = load_all()
    for rid, (title, v, st) in BEST.items():
        T = run_v(M, C, v)
        S = rl.score(T, SESS_ALL)
        sp = score_all(T)
        verdict = (f"2026 H1 PF {sp['h1']['pf']} {sp['h1']['net']:+,} / H2 PF {sp['h2']['pf']} {sp['h2']['net']:+,} / full PF "
                   f"{sp['y26']['pf']} {sp['y26']['net']:+,} at {sp['y26']['tpw']}/wk; 2021-25 reference PF {sp['ref']['pf']} "
                   f"{sp['ref']['net']:+,}. Picked on 2026 H1, checked on H2.")
        rl.save(rid, title, "other", "Which filters / confluences improve LIT (lit_A) on 2026? (owner order 2026-10-18)",
                params={"base": "lit_A", **_ser(v)}, trades=T, scored=S, status=st, verdict=verdict, writeup=None, tags=["lit"],
                notes="tools/lit_filters.py (stage1-3); lit_A + filters; size $800 up to a 20-pt stop then 800x20/stop, MNQ, max 40 "
                      "micros, $1.40/micro + 1 tick slippage; NWOG = Friday 17:00 close to Sunday 18:00 open; HOW window Tue 03:00 "
                      "-> Wed 11:30 ET; halves: H1 2026-01-02..06-30, H2 2026-07-01..10-16")
        print(rid, fmt(sp["y26"]))


def table():
    res = json.load(open(OUT))
    print("| Variant | Group | Kind | H1 n | H1 PF | H1 net | H2 n | H2 PF | H2 net | 2026 tpw | 2026 PF | 2026 net | 2026 DD | 2021-25 PF | 2021-25 net |")
    print("|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for nm, r in res.items():
        a, b, y, f = r["h1"], r["h2"], r["y26"], r["ref"]
        g = lambda s, k: s.get(k) if s.get("n") else "-"
        print(f"| {nm} | {r['group']} | {r['kind']} | {a.get('n')} | {g(a, 'pf')} | {g(a, 'net')} | {b.get('n')} | {g(b, 'pf')} | {g(b, 'net')} | "
              f"{g(y, 'tpw')} | {g(y, 'pf')} | {g(y, 'net')} | {g(y, 'dd')} | {g(f, 'pf')} | {g(f, 'net')} |")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "search"
    if cmd == "search":
        main_search()
    elif cmd == "stage2":
        stage2()
    elif cmd == "stage3":
        stage3()
    elif cmd == "robust":
        robust()
    elif cmd == "save":
        save_best()
    elif cmd == "table":
        table()
