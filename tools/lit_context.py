"""LIT market context (2026-10-19): dealer gamma (GEX / DIX), vanna proxies, the VIX term structure / vol-of-vol, the options
calendar and the 0DTE-implied move, used ONLY as size tilts, target / bank changes or breakeven changes on today's LIT trades
(never as a filter: the trade list, and so trades/week, stays identical; asserted on every variant).

Judged the LIT way: 2026 only, pick on H1 (Jan-Jun), check on H2 (Jul-Oct 16); 2021-25 is a reference line. Two references:
  base   today's live LIT (live_model.json lit = run lit_live)
  all3   the adopt-candidate combo t_check + scale_in + be_off (research/lit/adopt_combo.json)
Two views, costs in:
  eval   the real eval path: engine/sizing.lit_qty two_week for 10 sessions then safe_eval, no reset, $1.90 a micro, true 1m;
         fresh MFFU 50K evals on every session (p10 / f10 = pass / fail within 10 sessions), a 2,000-path Monte Carlo and the
         back-to-back path ($, PF, DD) - tools/lit_adv_manage.py + tools/lit_big_ideas.run_eval_x (size multiplier t["m"]:
         a cut is int(q x m) min 1, an up-size is capped by the live caps: 60% of the room, the $1,000 soft daily loss, 40)
  lit    the LIT size rule ($800 up to a 20-pt stop, weekly stop): engine trades scaled by engine/lit.scale_trade

Context (all known before the session: the reading of the last CBOE / SqueezeMetrics close BEFORE the trading day):
  data/GEX_1d.csv       SqueezeMetrics SPX gamma exposure (gex), dark-pool index (dix), SPX close (price)
  data/VIX_1d.csv       CBOE VIX close (also in the repo's live feed)
  data/CBOE_vol_1d.csv  CBOE VIX9D, VIX3M, VIX1D, VVIX, SKEW closes (2015 on; tools/context_refresh.py keeps it current from cdn-api.cboe.com; the part up to
                        2026-09-17 came from a public GitHub mirror of the CBOE History files, checked equal to
                        data/VXN_1d.csv on all 1,234 overlapping VXN days)
Not testable: CBOE put/call ratios (the free daily file stops 2019-10-04), real vanna / VEX (no free history: proxies only),
NYSE TICK / DXY / 10Y (no futures-grade file in data/; no Yahoo).

Target / breakeven variants run the engine itself (engine/lit.py run_x) with the default-off option ctx_day = {day: {...}}:
the day's target / bank / breakeven re-set after the fill; the setup, limit, pre-fill cancel and 1.5R check stay live.

    python -X utf8 tools/lit_context.py          # screen everything -> research/lit/context.json
    python -X utf8 tools/lit_context.py save     # + rl.save runs lit_ctx_*
    python -X utf8 tools/lit_context.py store    # rl.save runs lit_ctx_* from research/lit/context.json
Paper only. Changes nothing in live_model.json.
"""
from __future__ import annotations

import bisect
import collections
import csv
import datetime as dt
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import lit  # noqa: E402
from tools import lit_adopt_combo as AC  # noqa: E402
from tools import lit_adv_manage as A  # noqa: E402
from tools import lit_big_ideas as BI  # noqa: E402  (installs run_eval_x: size multiplier + adds)
from tools import lit_final as F  # noqa: E402

OUT = os.path.join(ROOT, "research", "lit", "context.json")
REFS = {"base": {}, "all3": {"t_check": AC.T15, "scale_in": AC.SCALE, "be_off": AC.BE_OFF}}
QS = (0.2, 0.33, 0.5, 0.67, 0.8)


# ================================================================================================ context data
def _series(path, col, datecol="date", fmt=None):
    out = {}
    for r in csv.DictReader(open(path, encoding="utf-8")):
        v = r.get(col)
        if v in (None, ""):
            continue
        out[r[datecol][:10]] = float(v)
    return dict(sorted(out.items()))


def _prior(S, day, lag=1):
    """Value of series S on its lag-th last date strictly before day (no look-ahead)."""
    ks = S["_k"]
    i = bisect.bisect_left(ks, day) - lag
    return S[ks[i]] if i >= 0 else None


def _pct(vals, x):
    return float(np.mean(np.array(vals) <= x)) if vals else None


def third_friday(y, m):
    d = dt.date(y, m, 15)
    return d + dt.timedelta(days=(4 - d.weekday()) % 7)


_CTX = None


def context():
    """day -> features (None = no reading). Continuous: gex, gex_pct (1-year percentile), gex_chg (1-day change / |gex|),
    dix, dix_pct, vix_chg (% 1-day VIX change), spx_chg (% 1-day SPX change), vanna (proxy = -vix_chg x |spx_chg| sign-kept:
    vol falling while spot moves = dealer vanna buying), ts9 (VIX9D / VIX), ts3 (VIX / VIX3M; > 1 = backwardation), vvix,
    vvix_vix, d1 (VIX1D / VIX: the 0DTE-implied move vs the 30-day), skew. Flags: opex, opex_wk, post_opex, quad_wk, vix_exp,
    tom (last session of the month + first two), mend (last two sessions)."""
    global _CTX
    if _CTX is not None:
        return _CTX
    G = os.path.join(ROOT, "data", "GEX_1d.csv")
    gex, dix, spx = _series(G, "gex"), _series(G, "dix"), _series(G, "price")
    vix = _series(os.path.join(ROOT, "data", "VIX_1d.csv"), "close")
    V = os.path.join(ROOT, "data", "CBOE_vol_1d.csv")
    cb = {c: _series(V, c) for c in ("vix9d", "vix3m", "vix1d", "vvix", "skew")}
    for S in [gex, dix, spx, vix] + list(cb.values()):
        S["_k"] = sorted(k for k in S if k != "_k")
    gk = gex["_k"]
    sess = F.SESS
    out = {}
    by_month = collections.defaultdict(list)
    for d in sess:
        by_month[d[:7]].append(d)
    for d in sess:
        o = {}
        i = bisect.bisect_left(gk, d) - 1
        if i >= 1:
            g = gex[gk[i]]
            o["gex"] = g
            o["gex_pct"] = _pct([gex[k] for k in gk[max(0, i - 251):i + 1]], g)
            o["gex_chg"] = (g - gex[gk[i - 1]]) / max(abs(gex[gk[i - 1]]), 1e8)
            o["dix"] = dix.get(gk[i])
            o["dix_pct"] = _pct([dix[k] for k in gk[max(0, i - 251):i + 1] if k in dix], o["dix"]) if o["dix"] is not None else None
            o["spx_chg"] = 100.0 * (spx[gk[i]] / spx[gk[i - 1]] - 1.0)
        v1, v0 = _prior(vix, d), _prior(vix, d, 2)
        if v1 and v0:
            o["vix_chg"] = 100.0 * (v1 / v0 - 1.0)
            if "spx_chg" in o:
                # vanna proxy: implied vol falling (vix_chg < 0) pushes dealers to buy the hedge back -> supportive; the size
                # of the spot move scales it. Positive = bullish vanna flow, negative = bearish (vol up).
                o["vanna"] = -o["vix_chg"] * (1.0 + abs(o["spx_chg"]))
        for c in cb:
            ks = cb[c]["_k"]
            j = bisect.bisect_left(ks, d) - 1
            if j >= 0 and ks[j] >= _prev_day(d):                       # a reading at most 4 calendar days old
                o[c] = cb[c][ks[j]]
        if v1:
            if "vix9d" in o:
                o["ts9"] = o["vix9d"] / v1
            if "vix3m" in o:
                o["ts3"] = v1 / o["vix3m"]
            if "vvix" in o:
                o["vvix_vix"] = o["vvix"] / v1
            if "vix1d" in o:
                o["d1"] = o["vix1d"] / v1
        y, m = int(d[:4]), int(d[5:7])
        of = third_friday(y, m).isoformat()
        ms = by_month[d[:7]]
        opex = max([x for x in ms if x <= of], default=None)          # 3rd Friday, or the session before on a holiday
        dd = dt.date.fromisoformat(d)
        ow = dt.date.fromisoformat(opex).isocalendar()[:2] if opex else None
        o["opex"] = d == opex
        o["opex_wk"] = ow is not None and dd.isocalendar()[:2] == ow
        o["post_opex"] = ow is not None and (dd - dt.timedelta(days=7)).isocalendar()[:2] == ow
        o["quad_wk"] = o["opex_wk"] and m in (3, 6, 9, 12)
        # VIX expiry: the Wednesday 30 days before the next month's 3rd Friday
        nm = (y + (m == 12), m % 12 + 1)
        ve = third_friday(*nm) - dt.timedelta(days=30)
        o["vix_exp"] = d == ve.isoformat()
        k = ms.index(d)
        left = sum(1 for j in range(1, 8) if (x := dd + dt.timedelta(days=j)).month == dd.month and x.weekday() < 5)
        o["mend"] = left <= 1                    # weekdays left in the calendar month (data end safe)
        o["tom"] = left == 0 or k <= 1
        out[d] = o
    _CTX = out
    return out


def _prev_day(d):
    return (dt.date.fromisoformat(d) - dt.timedelta(days=4)).isoformat()   # a reading at most ~4 days old counts


# ================================================================================================ runs / scoring
_RUN = {}


def run(ref, ctx_day=None):
    x = {**AC.LIVE, **REFS[ref]}
    if ctx_day:
        x["ctx_day"] = ctx_day
    return F.run(x)


def trades_key(T):
    return [(t["day"], int(t["entry_t"])) for t in T]


def score_eval(U):
    A._MC.clear()
    return BI.short(BI.score(U))


def score_lit(T):
    return F.score(T, spans=("H1", "H2", "2021-25"), fast=True)


def tilt(T, U, mfun):
    """Apply a size multiplier m(day, dir) to engine trades T (LIT rule) and units U (eval path)."""
    C = context()
    TT = [lit.scale_trade(t, m) if (m := mfun(C.get(t["day"], {}), int(t["dir"]))) != 1.0 else t for t in T]
    UU = [{**u, "m": mfun(C.get(u["day"], {}), int(u["dir"]))} for u in U]
    return TT, UU


class Ref:
    def __init__(self, nm):
        self.nm = nm
        self.T = run(nm)
        self.U = AC.units(self.T)
        self.key = trades_key(self.T)
        self.ev = score_eval(self.U)
        self.lr = score_lit(self.T)
        M, _ = F.market(AC.LIVE["ref"], AC.LIVE.get("extra_boxes") or [])
        self.vm = {str(M.days[k][0]): M.ctx[k].get("vix_move") for k in range(len(M.days))}


def h1_values(R, feat, dirn=False):
    C = context()
    v = []
    for t in R.T:
        if "2026-01-01" <= t["day"] <= "2026-06-30":
            x = C.get(t["day"], {}).get(feat)
            if x is not None:
                v.append(float(x) * (int(t["dir"]) if dirn else 1))
    return v


CONT = ["gex", "gex_pct", "gex_chg", "dix", "dix_pct", "vix_chg", "spx_chg", "vanna", "ts9", "ts3", "vvix", "vvix_vix", "d1",
        "skew"]
DIRN = ["spx_chg", "vanna", "gex_chg"]          # also as "with the trade" (feature x dir): the day before moved the trade's way
FLAGS = ["opex", "opex_wk", "post_opex", "quad_wk", "vix_exp", "tom", "mend"]
SHAPES = [("hi x0.5", 0.5, 1.0), ("lo x0.5", 1.0, 0.5), ("hi x1.5", 1.5, 1.0), ("lo x1.5", 1.0, 1.5),
          ("hi x0.75/lo x1.25", 0.75, 1.25), ("hi x1.25/lo x0.75", 1.25, 0.75)]
FSHAPES = [("x0.5", 0.5), ("x0.75", 0.75), ("x1.25", 1.25), ("x1.5", 1.5)]
MODES = {"wide+0.5": {"tgt_add_mv": 0.5}, "wide+1": {"tgt_add_mv": 1.0}, "near x0.75": {"tgt_m": 0.75},
         "near x0.6": {"tgt_m": 0.6}, "bank5": {"max_rr": 5.0}, "bank12": {"max_rr": 12.0}, "nobank": {"max_rr": None},
         "be0.75": {"be_r": 0.75}, "be1.5": {"be_r": 1.5}, "be2": {"be_r": 2.0}, "nobe": {"be_r": None}}


def feat_fn(feat, dirn):
    def f(c, d):
        x = c.get(feat)
        return None if x is None else float(x) * (d if dirn else 1)
    return f


def size_grid(R):
    """Every size tilt on reference R -> {label: {...}}."""
    res = {}
    for feat in CONT + [f + "@dir" for f in DIRN]:
        dirn = feat.endswith("@dir")
        fn = feat_fn(feat.replace("@dir", ""), dirn)
        vals = h1_values(R, feat.replace("@dir", ""), dirn)
        if len(vals) < 30:
            continue
        ths = [float(np.quantile(vals, q)) for q in QS]
        for qi, th in enumerate(ths):
            for sn, hm, lm in SHAPES:
                mf = (lambda c, d, fn=fn, th=th, hm=hm, lm=lm: 1.0 if (v := fn(c, d)) is None else (hm if v >= th else lm))
                res[f"{feat} >= q{QS[qi]} ({th:.4g}) {sn}"] = _eval_tilt(R, mf, {"feat": feat, "q": QS[qi], "th": th, "shape": sn})
    for fl in FLAGS:
        for sn, mm in FSHAPES:
            mf = (lambda c, d, fl=fl, mm=mm: mm if c.get(fl) else 1.0)
            res[f"{fl} {sn}"] = _eval_tilt(R, mf, {"feat": fl, "q": None, "th": None, "shape": sn})
    return res


def _eval_tilt(R, mf, info):
    TT, UU = tilt(R.T, R.U, mf)
    C = context()
    ms = [mf(C.get(u["day"], {}), int(u["dir"])) for u in UU]
    h1 = [m for u, m in zip(UU, ms) if u["day"] <= "2026-06-30"]
    h2 = [m for u, m in zip(UU, ms) if u["day"] >= "2026-07-01"]
    info = {**info, "flag_h1": sum(1 for m in h1 if m != 1.0), "flag_h2": sum(1 for m in h2 if m != 1.0),
            "mean_m": round(float(np.mean(ms)), 4) if ms else 1.0}
    return {"info": info, "eval": score_eval(UU), "lit": score_lit(TT)}


def ctx_for(R, flag, spec):
    """ctx_day dict for the days where flag(c) is true, mode spec (tgt_add_mv in VIX moves -> pts)."""
    C = context()
    out = {}
    for d in {t["day"] for t in R.T}:
        if not flag(C.get(d, {})):
            continue
        o = {k: v for k, v in spec.items() if k != "tgt_add_mv"}
        if "tgt_add_mv" in spec:
            vm = R.vm.get(d)
            if not vm:
                continue
            o["tgt_add"] = spec["tgt_add_mv"] * float(vm)
        out[d] = o
    return out


def regimes(R):
    """Day flags (label -> (fn(c) -> bool, info)) for the target / breakeven grid: thresholds at H1 trade quantiles."""
    out = {"ALL days": (lambda c: True, {"feat": "all"}),
           "gex<0": (lambda c: c.get("gex") is not None and c["gex"] < 0, {"feat": "gex", "side": "<", "th": 0.0})}
    for feat in ("gex_pct", "dix_pct", "ts9", "ts3", "vvix", "vvix_vix", "d1", "vix_chg", "vanna"):
        vals = h1_values(R, feat)
        for q in (0.33, 0.5, 0.67):
            th = float(np.quantile(vals, q))
            out[f"{feat} <= q{q}"] = (lambda c, f=feat, th=th: c.get(f) is not None and c[f] <= th, {"feat": feat, "side": "<=", "q": q, "th": th})
            out[f"{feat} >= q{q}"] = (lambda c, f=feat, th=th: c.get(f) is not None and c[f] >= th, {"feat": feat, "side": ">=", "q": q, "th": th})
    out["ts3 > 1 (backwardation)"] = (lambda c: c.get("ts3") is not None and c["ts3"] > 1.0, {"feat": "ts3", "side": ">", "th": 1.0})
    for fl in FLAGS:
        out[fl] = (lambda c, fl=fl: bool(c.get(fl)), {"feat": fl})
    return out


def mgmt_grid(R):
    res = {}
    for rn, (fl, info) in regimes(R).items():
        for mn, spec in MODES.items():
            cd = ctx_for(R, fl, spec)
            res[f"{rn} -> {mn}"] = _eval_ctx(R, cd, {**info, "regime": rn, "mode": mn})
    # two-sided gamma regime: low gamma -> wider / later bank, high gamma -> nearer / earlier bank (the classic dealer story)
    gv = h1_values(R, "gex_pct")
    for q in (0.33, 0.5, 0.67):
        th = float(np.quantile(gv, q))
        for lo_m, hi_m in (("wide+0.5", "near x0.75"), ("wide+1", "near x0.75"), ("nobank", "bank5"), ("wide+0.5", "bank5"),
                           ("be1.5", "be0.75"), ("wide+1", "near x0.6")):
            C = context()
            cd = {**ctx_for(R, lambda c: c.get("gex_pct") is not None and c["gex_pct"] <= th, MODES[lo_m]),
                  **ctx_for(R, lambda c: c.get("gex_pct") is not None and c["gex_pct"] > th, MODES[hi_m])}
            _ = C
            res[f"gamma pair q{q}: low -> {lo_m}, high -> {hi_m}"] = _eval_ctx(R, cd, {"feat": "gex_pct", "q": q, "th": th,
                                                                                       "regime": f"gamma pair q{q}", "mode": f"{lo_m}|{hi_m}"})
    return res


def _eval_ctx(R, cd, info):
    T = run(R.nm, cd) if cd else R.T
    assert trades_key(T) == R.key, "a context variant changed the trade list"
    U = AC.units(T)
    info = {**info, "flag_h1": sum(1 for d in cd if "2026-01-01" <= d <= "2026-06-30"),
            "flag_h2": sum(1 for d in cd if d >= "2026-07-01"), **changed(R.U, U)}
    return {"info": info, "eval": score_eval(U), "lit": score_lit(T)}


def changed(U0, U1):
    """Trades whose unit result changed (R per trade incl. adds' points), per half: count, total R change, and the share of
    the positive R change that the single biggest one carries (concentration: a 'handful of trades' check)."""
    o = {}
    for sp, a, z in (("h1", "2026-01-01", "2026-06-30"), ("h2", "2026-07-01", "2026-12-31")):
        dR = []
        for u0, u1 in zip(U0, U1):
            if a <= u0["day"] <= z:
                r0 = (u0["pts"] + sum(x["pts"] for x in u0.get("adds") or [])) / u0["risk"]
                r1 = (u1["pts"] + sum(x["pts"] for x in u1.get("adds") or [])) / u1["risk"]
                if abs(r1 - r0) > 1e-3:
                    dR.append(r1 - r0)
        pos = sum(x for x in dR if x > 0)
        o["chg_" + sp] = len(dR)
        o["dR_" + sp] = round(sum(dR), 2)
        o["top_" + sp] = round(max(dR) / pos, 2) if pos > 0 else None
    return o


# ================================================================================================ verdicts
def gains(R, o):
    e, b = o["eval"], R.ev
    lr, lb = o["lit"], R.lr
    return {"d_net_h1": e["H1"]["net"] - b["H1"]["net"], "d_net_h2": e["H2"]["net"] - b["H2"]["net"],
            "d_p10_h1": round(e["H1"]["p10"] - b["H1"]["p10"], 1), "d_p10_h2": round(e["H2"]["p10"] - b["H2"]["p10"], 1),
            "d_f10_h1": round(e["H1"]["f10"] - b["H1"]["f10"], 1), "d_f10_h2": round(e["H2"]["f10"] - b["H2"]["f10"], 1),
            "d_mcf_h1": round(e["H1"]["mc_f10"] - b["H1"]["mc_f10"], 1), "d_mcf_h2": round(e["H2"]["mc_f10"] - b["H2"]["mc_f10"], 1),
            "d_lit_h1": lr["H1"]["net"] - lb["H1"]["net"], "d_lit_h2": lr["H2"]["net"] - lb["H2"]["net"],
            "d_lit_ref": lr["2021-25"]["net"] - lb["2021-25"]["net"]}


def strict(g, info):
    """Adopt test (both halves): eval net up, 2-week pass not down, 2-week fail (exact and Monte Carlo) not up, LIT-rule net
    not down, and enough flagged trades (>= 10 in H1, >= 5 in H2)."""
    return (g["d_net_h1"] > 0 and g["d_net_h2"] > 0 and g["d_p10_h1"] >= 0 and g["d_p10_h2"] >= 0 and g["d_f10_h1"] <= 0
            and g["d_f10_h2"] <= 0 and g["d_mcf_h1"] <= 0 and g["d_mcf_h2"] <= 0 and g["d_lit_h1"] >= 0 and g["d_lit_h2"] >= 0
            and info.get("flag_h1", 0) >= 10 and info.get("flag_h2", 0) >= 5
            and (info.get("chg_h1") is None or (info["chg_h1"] >= 5 and info["chg_h2"] >= 3
                                                and (info["top_h1"] or 1) <= 0.5 and (info["top_h2"] or 1) <= 0.5)))


def loose(g):
    return g["d_net_h1"] > 0 and g["d_net_h2"] > 0


def neighbours(res, lab, o):
    """Same feature / side / shape at the adjacent quantile thresholds: all must keep eval net up in both halves."""
    i = o["info"]
    if i.get("q") is None:
        return None
    qs = QS if "shape" in i else (0.33, 0.5, 0.67)
    k = qs.index(i["q"])
    nb = [qs[j] for j in (k - 1, k + 1) if 0 <= j < len(qs)]
    out = []
    for lab2, o2 in res.items():
        i2 = o2["info"]
        if lab2 == lab or i2.get("feat") != i["feat"] or i2.get("q") not in nb:
            continue
        if i2.get("shape") != i.get("shape") or i2.get("mode") != i.get("mode") or i2.get("side") != i.get("side"):
            continue
        if ("gamma pair" in str(i.get("regime"))) != ("gamma pair" in str(i2.get("regime"))):
            continue
        out.append(o2["_g"]["d_net_h1"] > 0 and o2["_g"]["d_net_h2"] > 0)
    return all(out) if out else None


def leverage_control(R, mean_m):
    """A flat multiplier equal to the tilt's mean size (does the tilt beat plain leverage?)."""
    if abs(mean_m - 1.0) < 1e-3:
        return None
    TT, UU = tilt(R.T, R.U, lambda c, d: mean_m)
    return {"eval": score_eval(UU), "lit": score_lit(TT)}


def main(save=False):
    out = {"_note": "eval = live two_week eval path; lit = LIT size rule; d_* = vs the reference", "refs": {}}
    for nm in REFS:
        R = Ref(nm)
        out["refs"][nm] = {"eval": R.ev, "lit": R.lr}
        print(f"== reference {nm}: " + " | ".join(f"{s} net {R.ev[s]['net']:+,} PF {R.ev[s]['pf']} DD {R.ev[s]['dd']:,} "
                                                f"2w {R.ev[s]['p10']}/{R.ev[s]['f10']} mc {R.ev[s]['mc_p10']}/{R.ev[s]['mc_f10']}"
                                                for s in ("H1", "H2")), flush=True)
        for grp, fn in (("size", size_grid), ("mgmt", mgmt_grid)):
            res = fn(R)
            for lab, o in res.items():
                o["_g"] = gains(R, o)
            for lab, o in res.items():
                o["nb_ok"] = neighbours(res, lab, o)
                o["strict"] = strict(o["_g"], o["info"])
                o["adopt"] = bool(o["strict"] and o["nb_ok"] is not False)
            for lab, o in res.items():
                if grp == "mgmt" and o["info"].get("feat") != "all" and "|" not in str(o["info"].get("mode")):
                    al = res.get(f"ALL days -> {o['info']['mode']}")
                    if al is not None:          # the context must beat the same change on every day
                        o["vs_all"] = {s: o["eval"][s]["net"] - al["eval"][s]["net"] for s in ("H1", "H2")}
                        o["adopt"] = bool(o["adopt"] and all(v > 0 for v in o["vs_all"].values()))
                if o["adopt"] and grp == "size":
                    lc = leverage_control(R, o["info"]["mean_m"])
                    if lc is not None:
                        o["lev_ctrl"] = {s: lc["eval"][s]["net"] for s in ("H1", "H2")}
                        o["adopt"] = all(o["eval"][s]["net"] > lc["eval"][s]["net"] for s in ("H1", "H2"))
            n_loose = sum(1 for o in res.values() if loose(o["_g"]))
            n_strict = sum(1 for o in res.values() if o["strict"])
            n_ad = sum(1 for o in res.values() if o["adopt"])
            print(f"   {grp}: {len(res)} variants, net up in both halves {n_loose}, strict {n_strict}, adopt (+ neighbours"
                  f"{', + beats flat leverage' if grp == 'size' else ''}) {n_ad}", flush=True)
            top = sorted(res.items(), key=lambda kv: min(kv[1]["_g"]["d_net_h1"], kv[1]["_g"]["d_net_h2"]), reverse=True)[:12]
            for lab, o in top:
                g = o["_g"]
                print(f"     {lab[:58]:58s} dnet {g['d_net_h1']:+6,}/{g['d_net_h2']:+6,} d2w pass {g['d_p10_h1']:+5}/{g['d_p10_h2']:+5} "
                      f"fail {g['d_f10_h1']:+5}/{g['d_f10_h2']:+5} mcfail {g['d_mcf_h1']:+5}/{g['d_mcf_h2']:+5} LIT {g['d_lit_h1']:+6,}/"
                      f"{g['d_lit_h2']:+6,} ref {g['d_lit_ref']:+7,} n {o['info']['flag_h1']}/{o['info']['flag_h2']} "
                      f"chg {o['info'].get('chg_h1')}/{o['info'].get('chg_h2')} top {o['info'].get('top_h1')}/{o['info'].get('top_h2')} "
                      f"vs_all {o.get('vs_all')} strict={o['strict']} nb={o['nb_ok']} adopt={o['adopt']}", flush=True)
            for lab, o in res.items():
                if o["adopt"]:
                    print(f"     ADOPT {lab}", flush=True)
            out.setdefault(nm, {})[grp] = res
    json.dump(out, open(OUT, "w"), indent=1, default=float)
    if save:
        store(out)
    return out


# ================================================================================================ store
def store(out):
    from tools import runlib as rl
    Q = ("Owner 2026-10-19: does market context (GEX / DIX, vanna proxies, VIX term structure / VVIX, options calendar, "
         "0DTE move) help LIT as a size tilt or a target / breakeven change, with trades/week and the rules unchanged?")
    picks = {}
    for nm in REFS:
        for grp in ("size", "mgmt"):
            res = out[nm][grp]
            top = sorted(res.items(), key=lambda kv: min(kv[1]["_g"]["d_net_h1"], kv[1]["_g"]["d_net_h2"]), reverse=True)
            for lab, o in top[:3]:
                picks[(nm, grp, lab)] = o
            for lab, o in res.items():
                if o["adopt"]:
                    picks[(nm, grp, lab)] = o
    for (nm, grp, lab), o in picks.items():
        _store_one(rl, Q, nm, grp, lab, o, out)


def _he(e, s):
    x = e[s]
    return (f"n={x['n']} PF {x['pf']} net {x['net']:+,} (${x['per_month']:,}/mo) DD {x['dd']:,}; 2-week pass/fail "
            f"{x['p10']}/{x['f10']} (Monte Carlo {x['mc_p10']}/{x['mc_f10']}), 1 month {x['p20']}/{x['f20']}")


def _slug(s):
    import re
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")[:60]


def _rebuild(nm, grp, o):
    """Rebuild the variant's trades (engine T, units U) from its info."""
    R = _REF.get(nm) or _REF.setdefault(nm, Ref(nm))
    i = o["info"]
    if grp == "size":
        if i["q"] is None:
            mf = (lambda c, d, fl=i["feat"], mm=float(i["shape"][1:]): mm if c.get(fl) else 1.0)
        else:
            sh = next(s for s in SHAPES if s[0] == i["shape"])
            fn = feat_fn(i["feat"].replace("@dir", ""), i["feat"].endswith("@dir"))
            mf = (lambda c, d, fn=fn, th=i["th"], hm=sh[1], lm=sh[2]: 1.0 if (v := fn(c, d)) is None else (hm if v >= th else lm))
        TT, UU = tilt(R.T, R.U, mf)
        return R, TT, UU, None
    rg = regimes(R)
    if i["regime"] in rg:
        cd = ctx_for(R, rg[i["regime"]][0], MODES[i["mode"]])
    else:
        lo_m, hi_m = i["mode"].split("|")
        th = i["th"]
        cd = {**ctx_for(R, lambda c: c.get("gex_pct") is not None and c["gex_pct"] <= th, MODES[lo_m]),
              **ctx_for(R, lambda c: c.get("gex_pct") is not None and c["gex_pct"] > th, MODES[hi_m])}
    T = run(nm, cd)
    return R, T, AC.units(T), cd


_REF = {}


def _store_one(rl, Q, nm, grp, lab, o, out):
    R, TT, UU, cd = _rebuild(nm, grp, o)
    A._MC.clear()
    Tp = []
    for sp in ("H1", "H2"):
        Tp += A.b2b(UU, sp)[0]
    for t in Tp:
        t["risk_pts"] = t["risk"]; t["r"] = round(t["pnl"] / t["risk_usd"], 3) if t["risk_usd"] else 0.0
        t.update(half=False, trigger="LIT-1m", mfe=None, mae=None, bars_held=None, regime="", mult=None, tgt_pts=t["tgt"])
    e, b, g = o["eval"], out["refs"][nm]["eval"], o["_g"]
    st = "adopt-candidate" if o["adopt"] else "rejected"          # net up in both halves alone is not enough (strict test)
    P = {**lit.DEFAULTS, **AC.LIVE, **REFS[nm]}
    if cd:
        P["ctx_day"] = f"{len(cd)} days ({lab})"
    rid = "lit_ctx_" + ("" if nm == "base" else "all3_") + _slug(lab)
    rl.save(rid, f"LIT {'live' if nm == 'base' else '+ all3'} + context {grp}: {lab}", "risk" if grp == "size" else "management", Q,
            params=P, sizing={"mode": "two_week", **A.CFG}, trades=Tp, scored=rl.score(Tp, A.S26), status=st,
            verdict=f"Eval path (two_week 10 sessions then safe_eval, no reset, $1.90, true 1m). H1 (pick) {_he(e, 'H1')}. "
                    f"H2 (check) {_he(e, 'H2')}. Reference {nm}: H1 net {b['H1']['net']:+,} 2-week {b['H1']['p10']}/{b['H1']['f10']}, "
                    f"H2 net {b['H2']['net']:+,} 2-week {b['H2']['p10']}/{b['H2']['f10']}. LIT size rule change H1 {g['d_lit_h1']:+,} "
                    f"H2 {g['d_lit_h2']:+,}, 2021-25 reference {g['d_lit_ref']:+,}. Flagged trades {o['info']['flag_h1']}/"
                    f"{o['info']['flag_h2']}; neighbours hold: {o['nb_ok']}.",
            notes="tools/lit_context.py (stored trades = the back-to-back eval path per half). Same trade list as the reference "
                  "(asserted).", writeup="lit-market-context", tags=["lit", "lit_ctx"])
    print("saved", rid, st, flush=True)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "store":          # rl.save from research/lit/context.json (no re-screen)
        store(json.load(open(OUT, encoding="utf-8")))
    else:
        main(save=len(sys.argv) > 1 and sys.argv[1] == "save")
