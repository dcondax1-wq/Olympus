"""LIT research batch 3b (2026-10-20): 12 ideas on today's live LIT and on the adopt-candidate combo (t_check + scale_in +
be_off), as size tilts or management tweaks (the trade list stays the same unless noted), plus a robustness and a stability
study of the combo.

  1 es_conf   ES also swept its matching level (same side) within N minutes of NQ's sweep (size tilt)
  2 rs        intraday NQ/ES relative strength in the trade's direction over the last 30 / 60 min before the entry (size tilt)
  3 be_swing  structure breakeven: BE on the first new 1m swing beyond the entry instead of / besides 1R (engine be_swing)
  4 day10     day-type read at 10:00 ET for a trade still open (range so far vs ATR / VIX move, trend efficiency) -> bank
              nearer (3-5R) on one side (engine day_mgmt)
  5 asia      Asia range (20:00-00:00) size vs ATR -> London trade (02:00-08:00 entries) size / target
  6 london    London range (02:00-05:00) size vs ATR -> NY trade (08:00+ entries) size / target
  7 news      CPI / NFP / FOMC / PPI days (data/news/events.csv): size only
  8 season    week of month, pre-holiday, first / last trading day of the month (size)
  9 fvg       an unfilled 5m imbalance (FVG / void) beyond the entry as the target: instead / only if nearer / only if farther
 10 stop_tgt  VIX-band target scaled by the stop: a wide stop -> a nearer target in R
 11 robust    the combo under +1/+2/+4 ticks on entries and exits, commission +50%, a 1-bar entry delay, 10% / 20% missed
              fills at random (seeded, 50 repeats)
 12 stable    month by month, a 1,215-point grid around the combo (t_check at/x/mfe, scale_in pb/f, be_off) and a walk-forward
              (pick on the 3 months before, trade the next month)

Judged the LIT way: 2026 only, pick on H1 (Jan-Jun), check on H2 (Jul-Oct 16); 2021-25 = reference. Main view: the real eval
path (engine/sizing.lit_qty two_week for 10 sessions then safe_eval, no reset, $1.90 a micro, true 1m; fresh MFFU 50K evals
on every session, Monte Carlo, back-to-back path), scored by tools/lit_adv_manage.py + tools/lit_big_ideas.py through
tools/lit_context.py (the executor of research/lit/context.json and research/lit/adopt_combo.json). Second view: the LIT size
rule (engine trades, $800 up to a 20-pt stop, weekly stop).

Adopt test (strict, both halves): eval net up, 2-week pass not down, 2-week fail (exact and Monte Carlo) not up, LIT-rule net
not down, >= 10 flagged trades in H1 and >= 5 in H2 (management: >= 5 / 3 changed trades, the best one < 50% of the gain),
neighbouring settings up in both halves, and a size tilt must beat a flat size change of the same mean (plain leverage).

    python -X utf8 tools/lit_batch3b.py [ideas...]   # screen -> research/lit/batch3b.json (all ideas when none given)
    python -X utf8 tools/lit_batch3b.py store        # rl.save runs lit_b3b_* from research/lit/batch3b.json
Paper only. Changes nothing in live_model.json. No look-ahead: every feature uses bars that closed before the entry (or
before the 10:00 decision), news from the calendar file, holidays from the session list.
"""
from __future__ import annotations

import collections
import copy
import datetime as dt
import json
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import lit  # noqa: E402
from engine import sizing as SZ  # noqa: E402
from tools import lit_adopt_combo as AC  # noqa: E402
from tools import lit_adv_manage as A  # noqa: E402
from tools import lit_big_ideas as BI  # noqa: E402  (installs run_eval_x: size multiplier t["m"] + adds)
from tools import lit_context as LC  # noqa: E402
from tools import lit_final as F  # noqa: E402

OUT = os.environ.get("B3B_OUT") or os.path.join(ROOT, "research", "lit", "batch3b.json")
REFS = LC.REFS
QS = LC.QS
SHAPES = LC.SHAPES
FSHAPES = LC.FSHAPES
RES = {}


def dump():
    json.dump(RES, open(OUT, "w"), indent=1, default=float)


# ================================================================================================ references
class Ref(LC.Ref):
    def __init__(self, nm):
        super().__init__(nm)
        self.M, self.C = F.market(AC.LIVE["ref"], AC.LIVE.get("extra_boxes") or [])
        self.B1 = F.bars(self.M, "1m")
        self.by_key = {(t["day"], int(t["entry_t"])): t for t in self.T}
        self.by_day = {t["day"]: t for t in self.T if t["day"] >= "2026-01-01"}


_R = {}


def ref(nm):
    if nm not in _R:
        _R[nm] = Ref(nm)
    return _R[nm]


def key(t):
    return (t["day"], int(t["entry_t"]))


def ev(U):
    A._MC.clear()
    return BI.short(BI.score(U))


def lit_score(T):
    return LC.score_lit(T)


# ================================================================================================ size tilts
def tilt_eval(R, mm, info):
    """mm: {trade key: multiplier} (missing = 1.0). Scores the eval path (2026 units) and the LIT size rule (all trades)."""
    TT = [lit.scale_trade(t, m) if (m := mm.get(key(t), 1.0)) != 1.0 else t for t in R.T]
    UU = [{**u, "m": mm.get(key(u), 1.0)} for u in R.U]
    ms = [mm.get(key(u), 1.0) for u in R.U]
    h1 = [m for u, m in zip(R.U, ms) if u["day"] <= "2026-06-30"]
    h2 = [m for u, m in zip(R.U, ms) if u["day"] >= "2026-07-01"]
    info = {**info, "flag_h1": sum(1 for m in h1 if m != 1.0), "flag_h2": sum(1 for m in h2 if m != 1.0),
            "mean_m": round(float(np.mean(ms)), 4) if ms else 1.0}
    return {"info": info, "eval": ev(UU), "lit": lit_score(TT)}


def flat_eval(R, m):
    return tilt_eval(R, {key(u): m for u in R.U} | {key(t): m for t in R.T}, {})


def q_grid(R, feat, name, sub=None, min_n=20):
    """Quantile threshold x shape grid of a continuous per-trade feature {key: value} (None = no tilt); thresholds at the H1
    trade quantiles. sub(t) -> bool restricts the tilt to some trades (e.g. London entries)."""
    vals = [feat[k] for k, t in R.by_key.items() if "2026-01-01" <= k[0] <= "2026-06-30" and feat.get(k) is not None
            and (sub is None or sub(t))]
    res = {}
    if len(vals) < min_n:
        print(f"   {name}: only {len(vals)} H1 values, skipped", flush=True)
        return res
    for q in QS:
        th = float(np.quantile(vals, q))
        for sn, hm, lm in SHAPES:
            mm = {}
            for k, t in R.by_key.items():
                v = feat.get(k)
                if v is None or (sub is not None and not sub(t)):
                    continue
                m = hm if v >= th else lm
                if m != 1.0:
                    mm[k] = m
            res[f"{name} >= q{q} ({th:.4g}) {sn}"] = tilt_eval(R, mm, {"feat": name, "q": q, "th": th, "shape": sn})
    return res


def f_grid(R, flags, name):
    """Flag tilts: flags {label: set of trade keys}; shape x0.5 / x0.75 / x1.25 / x1.5 on the flagged trades."""
    res = {}
    for fl, ks in flags.items():
        for sn, m in FSHAPES:
            res[f"{name}:{fl} {sn}"] = tilt_eval(R, {k: m for k in ks}, {"feat": f"{name}:{fl}", "q": None, "th": None, "shape": sn})
    return res


# ================================================================================================ management variants
def run_opts(nm, opts):
    return F.run({**AC.LIVE, **REFS[nm], **opts})


def mgmt_eval(R, opts, info, same=True):
    T = run_opts(R.nm, opts)
    if same:
        assert LC.trades_key(T) == R.key, f"variant changed the trade list: {info}"
    U = AC.units(T)
    ch = LC.changed(R.U, U) if same else {}
    return {"info": {**info, **ch}, "eval": ev(U), "lit": lit_score(T)}


# ================================================================================================ verdicts
def gains(R, o):
    return LC.gains(R, o)


def strict(g, info):
    return LC.strict(g, info)


def judge(R, res, nb_key=None):
    """Adds _g, strict, nb_ok, adopt to every variant of res. nb_key(info) -> (group, position, ordered positions): the
    neighbours are the variants of the same group at the adjacent positions."""
    for lab, o in res.items():
        o["_g"] = gains(R, o)
        o["strict"] = strict(o["_g"], o["info"])
    groups = collections.defaultdict(dict)
    if nb_key is not None:
        for lab, o in res.items():
            g = nb_key(o["info"])
            if g is not None:
                groups[g[0]][g[1]] = lab
    for lab, o in res.items():
        nb = None
        if nb_key is not None and (g := nb_key(o["info"])) is not None:
            pos = g[2]
            i = pos.index(g[1])
            adj = [groups[g[0]].get(pos[j]) for j in (i - 1, i + 1) if 0 <= j < len(pos)]
            adj = [a for a in adj if a]
            if adj:
                nb = all(res[a]["_g"]["d_net_h1"] > 0 and res[a]["_g"]["d_net_h2"] > 0 for a in adj)
        o["nb_ok"] = nb
        o["adopt"] = bool(o["strict"] and nb is not False)
        if o["adopt"] and abs(o["info"].get("mean_m", 1.0) - 1.0) > 1e-3:
            lc = flat_eval(R, o["info"]["mean_m"])
            o["lev_ctrl"] = {s: lc["eval"][s]["net"] for s in ("H1", "H2")}
            o["adopt"] = all(o["eval"][s]["net"] > lc["eval"][s]["net"] for s in ("H1", "H2"))
    return res


def nb_quant(i):
    if i.get("q") is None:
        if i.get("shape") in ("x0.5", "x0.75", "x1.25", "x1.5"):         # flags: the other multiplier on the same side
            side = "lo" if i["shape"] in ("x0.5", "x0.75") else "hi"
            return ((i["feat"], side), i["shape"], ["x0.5", "x0.75"] if side == "lo" else ["x1.25", "x1.5"])
        return None
    return ((i["feat"], i.get("shape"), i.get("mode")), i["q"], list(QS) if "shape" in i and i.get("shape") else [0.33, 0.5, 0.67])


def report(idea, nm, res, top=8):
    n_loose = sum(1 for o in res.values() if o["_g"]["d_net_h1"] > 0 and o["_g"]["d_net_h2"] > 0)
    n_strict = sum(1 for o in res.values() if o["strict"])
    n_ad = sum(1 for o in res.values() if o["adopt"])
    print(f"   [{idea}/{nm}] {len(res)} variants, net up both halves {n_loose}, strict {n_strict}, adopt {n_ad}", flush=True)
    srt = sorted(res.items(), key=lambda kv: min(kv[1]["_g"]["d_net_h1"], kv[1]["_g"]["d_net_h2"]), reverse=True)
    for lab, o in srt[:top]:
        g, i = o["_g"], o["info"]
        print(f"     {lab[:62]:62s} dnet {g['d_net_h1']:+7,}/{g['d_net_h2']:+7,} 2wP {g['d_p10_h1']:+5}/{g['d_p10_h2']:+5} "
              f"2wF {g['d_f10_h1']:+5}/{g['d_f10_h2']:+5} mcF {g['d_mcf_h1']:+5}/{g['d_mcf_h2']:+5} LIT {g['d_lit_h1']:+7,}/"
              f"{g['d_lit_h2']:+7,} ref {g['d_lit_ref']:+7,} n {i.get('flag_h1')}/{i.get('flag_h2')} chg {i.get('chg_h1')}/"
              f"{i.get('chg_h2')} top {i.get('top_h1')}/{i.get('top_h2')} st={o['strict']} nb={o['nb_ok']} ad={o['adopt']}",
              flush=True)
    for lab, o in res.items():
        if o["adopt"]:
            print(f"     ADOPT {lab}", flush=True)


def summary(res):
    srt = sorted(res.items(), key=lambda kv: min(kv[1]["_g"]["d_net_h1"], kv[1]["_g"]["d_net_h2"]), reverse=True)
    return {"n": len(res), "loose": sum(1 for o in res.values() if o["_g"]["d_net_h1"] > 0 and o["_g"]["d_net_h2"] > 0),
            "strict": sum(1 for o in res.values() if o["strict"]), "adopt": [k for k, o in res.items() if o["adopt"]],
            "top": [{"label": k, **{x: o[x] for x in ("info", "_g", "strict", "nb_ok", "adopt")}, "lev_ctrl": o.get("lev_ctrl"),
                     "eval": o["eval"], "lit": {s: o["lit"][s] for s in ("H1", "H2", "2021-25")}} for k, o in srt[:6]]}


def run_idea(idea, fn, nb=nb_quant):
    t0 = time.time()
    out = {}
    for nm in REFS:
        R = ref(nm)
        res = fn(R)
        judge(R, res, nb)
        report(idea, nm, res)
        out[nm] = res
    RES[idea] = {nm: summary(res) for nm, res in out.items()}
    RES[idea]["_secs"] = round(time.time() - t0)
    dump()
    return out


# ================================================================================================ helpers: bars / features
def mod_of(R, t):
    return int(R.M.mod[int(t["entry_i"])])


def last_closed5(R, t):
    """Index of the last 5m bar that closed at or before the entry (the bar containing the 1m entry is still forming)."""
    j = int(np.searchsorted(R.M.t, int(t["entry_t"]), side="right") - 1)
    return j - 1 if int(R.M.t[j]) + 300 > int(t["entry_t"]) else j


_ATRD = {}


def atr_d(R, k, n=14):
    """Average true range of the n trading days before day index k (18:00-17:00 days, 5m highs / lows), points."""
    if k in _ATRD:
        return _ATRD[k]
    M = R.M
    rs = []
    for kk in range(max(1, k - n), k):
        _, s, e = M.days[kk]
        pc = float(M.c[M.days[kk - 1][2] - 1])
        rs.append(max(float(M.h[s:e].max()), pc) - min(float(M.l[s:e].min()), pc))
    _ATRD[k] = float(np.mean(rs)) if rs else None
    return _ATRD[k]


def day_index(R):
    if not hasattr(R, "_dk"):
        R._dk = {str(d): k for k, (d, s, e) in enumerate(R.M.days)}
    return R._dk


def cand_of(R, t):
    if not hasattr(R, "_ci"):
        R._ci = {(z["day"], z["dir"], z["i"]): z for z in R.C}
    return R._ci.get((t["day"], int(t["dir"]), int(t["i"])))


# ================================================================================================ 1. ES confirmation
def es_lags(R):
    """trade key -> minutes between NQ's first breach of a swept level and ES's first breach of its copy (same side), the
    smallest over the trade's swept levels with an ES copy, both up to the trigger bar (known before the entry); 9999 = ES
    held every judged copy; None = no copy could be judged (ES data missing / no copy rule)."""
    from tools import lit_adv_audit as AU
    M = R.M
    E = AU.es_bars(M)
    out = {}
    for k_, t in R.by_key.items():
        if t["day"] < "2025-05-01":
            continue
        z = cand_of(R, t)
        if z is None:
            continue
        d, k, i = z["dir"], z["k"], z["i"]
        lo_es = E["l"] if d == 1 else -E["h"]
        lo_nq = M.l if d == 1 else -M.h
        want = "low" if d == 1 else "high"
        best = None
        for side, px, ki, nm, cls in M.levels(k):
            if side != want or nm not in z["sw"] or abs(px * d - z["sw"][nm]) > 1e-6 or ki >= i:
                continue
            cp = AU.es_copy(M, E, k, nm, cls, side, px, ki, d)
            a = max(ki + 1, z["ext_i"] - 600)
            if cp is None or a > i:
                continue
            seg_es = lo_es[a:i + 1]
            if not np.isfinite(seg_es).mean() >= 0.99:
                continue
            br_nq = np.flatnonzero(lo_nq[a:i + 1] < px * d)
            if not len(br_nq):
                continue
            br_es = np.flatnonzero(np.nan_to_num(seg_es, nan=np.inf) < cp)
            lag = 9999 if not len(br_es) else abs(int(br_es[0]) - int(br_nq[0])) * 5
            best = lag if best is None else min(best, lag)
        out[k_] = best
    return out


NS = [5, 10, 15, 30, 60, 120]
ES_SHAPES = [("conf x1.25", 1.25, 1.0), ("conf x1.5", 1.5, 1.0), ("unconf x0.75", 1.0, 0.75), ("unconf x0.5", 1.0, 0.5),
             ("conf x1.25/unconf x0.75", 1.25, 0.75), ("conf x0.75", 0.75, 1.0), ("unconf x1.25", 1.0, 1.25)]


def idea_es(R):
    L = es_lags(R)
    known = [v for k, v in L.items() if v is not None and k[0] >= "2026-01-01"]
    print(f"   ES lags judged on {len(known)} 2026 trades; ES held all copies on {sum(1 for v in known if v == 9999)}; "
          f"lag <= 15 min on {sum(1 for v in known if v <= 15)}", flush=True)
    RES.setdefault("_diag", {})["es_lag_2026"] = dict(collections.Counter(
        "held" if v == 9999 else ("<=5" if v <= 5 else "<=15" if v <= 15 else "<=60" if v <= 60 else ">60") for v in known))
    res = {}
    for N in NS:
        for sn, cm, um in ES_SHAPES:
            mm = {}
            for k, v in L.items():
                if v is None:
                    continue
                m = cm if v <= N else um
                if m != 1.0:
                    mm[k] = m
            res[f"ES took its copy within {N} min: {sn}"] = tilt_eval(R, mm, {"feat": "es_conf", "N": N, "shape": sn})
    return res


def nb_N(i):
    return (("es", i["shape"]), i["N"], NS) if "N" in i else None


# ================================================================================================ 2. NQ/ES relative strength
def rs_feat(R, mins):
    from tools import lit_adv_audit as AU
    M = R.M
    E = AU.es_bars(M)
    n = mins // 5
    out = {}
    for k, t in R.by_key.items():
        if t["day"] < "2025-05-01":
            continue
        j = last_closed5(R, t)
        if j - n < 0:
            continue
        a, b = float(M.c[j - n]), float(M.c[j])
        ea, eb = E["c"][j - n], E["c"][j]
        if not (np.isfinite(ea) and np.isfinite(eb)) or ea <= 0:
            out[k] = None
            continue
        out[k] = round(100.0 * ((b / a - 1.0) - (eb / ea - 1.0)) * int(t["dir"]), 5)
    return out


def idea_rs(R):
    res = {}
    for mins in (30, 45, 60):
        res.update(q_grid(R, rs_feat(R, mins), f"rs{mins}"))
    return res


# ================================================================================================ 3. structure breakeven
BE_SW = {}
for _k in (1, 2, 3):
    for _mode in ("or", "only", "and"):
        for _side in ("low", "high"):
            for _mr in (0.0, 0.25, 0.5):
                BE_SW[f"k{_k} {_mode} {_side} min{_mr}"] = {"k": _k, "mode": _mode, "side": _side, "min_r": _mr}


def idea_be(R):
    res = {}
    for lab, spec in BE_SW.items():
        res[f"BE swing {lab}"] = mgmt_eval(R, {"be_swing": spec}, {"feat": f"be_{spec['mode']}_{spec['side']}_{spec['min_r']}",
                                                                   "kk": spec["k"], "spec": spec, "flag_h1": 99, "flag_h2": 99})
    return res


def nb_be(i):
    return ((i["feat"],), i["kk"], [1, 2, 3]) if "kk" in i else None


# ================================================================================================ 4. day type at 10:00
def day10_feats(R, at_mod=600):
    """day -> features of the trading day from bars that closed before at_mod ET (5m bars starting before it), for the day's
    trade when it was filled before then: rng00 / rng18 (range since 00:00 / 18:00 over the 14-day ATR), used (range since
    00:00 over the VIX one-day move), eff (|close - 00:00 open| / range since 00:00), wdir (the same signed with the trade),
    prog (the trade's open profit at the decision in R)."""
    M = R.M
    dk = day_index(R)
    out = {}
    for d, t in R.by_day.items():
        k = dk.get(d)
        if k is None:
            continue
        _, s, e = M.days[k]
        md = M.mod[s:e]
        t_dec = None
        ii = np.flatnonzero((md >= at_mod) & (md < 1080))
        if not len(ii):
            continue
        jdec = s + int(ii[0])                         # the first bar starting at the decision time
        t_dec = int(M.t[jdec])
        if int(t["entry_t"]) >= t_dec:
            continue
        i00 = np.flatnonzero((md >= 0) & (md < at_mod))
        if not len(i00):
            continue
        a0 = s + int(i00[0])
        hi0, lo0 = float(M.h[a0:jdec].max()), float(M.l[a0:jdec].min())
        hi8, lo8 = float(M.h[s:jdec].max()), float(M.l[s:jdec].min())
        rng = max(hi0 - lo0, 1e-9)
        A_ = atr_d(R, k)
        vm = R.vm.get(d)
        c = float(M.c[jdec - 1])
        dirn = int(t["dir"])
        out[d] = {"t": t_dec, "rng00": (hi0 - lo0) / A_ if A_ else None, "rng18": (hi8 - lo8) / A_ if A_ else None,
                  "used": (hi0 - lo0) / vm if vm else None, "eff": abs(c - float(M.o[a0])) / rng,
                  "wdir": (c - float(M.o[a0])) * dirn / rng,
                  "prog": (c - float(t["entry_px"])) * dirn / float(t["risk_pts"])}
    return out


D10_FEATS = ("rng00", "rng18", "used", "eff", "wdir", "prog")


def idea_day10(R):
    res = {}
    for at_lab, at_mod in (("10:00", 600), ("10:30", 630), ("09:30", 570)):
        Fd = day10_feats(R, at_mod)
        n_open = len(Fd)
        for feat in D10_FEATS:
            vals = [f[feat] for d, f in Fd.items() if d <= "2026-06-30" and f[feat] is not None]
            if len(vals) < 15:
                continue
            for q in (0.33, 0.5, 0.67):
                th = float(np.quantile(vals, q))
                for side in ("<=", ">="):
                    for bank in (3.0, 4.0, 5.0):
                        dm = {d: {"t": f["t"], "max_rr": bank} for d, f in Fd.items()
                              if f[feat] is not None and ((f[feat] <= th) if side == "<=" else (f[feat] >= th))}
                        info = {"feat": f"{at_lab} {feat} {side}", "mode": f"bank{bank:g}", "q": q, "th": th,
                                "flag_h1": sum(1 for d in dm if d <= "2026-06-30"), "flag_h2": sum(1 for d in dm if d >= "2026-07-01"),
                                "open_at": n_open}
                        res[f"{at_lab} {feat} {side} q{q} ({th:.3g}) -> bank {bank:g}R"] = mgmt_eval(R, {"day_mgmt": dm}, info)
        for bank in (3.0, 4.0, 5.0):          # every open trade (no day read): the control
            dm = {d: {"t": f["t"], "max_rr": bank} for d, f in Fd.items()}
            res[f"{at_lab} ALL open trades -> bank {bank:g}R"] = mgmt_eval(R, {"day_mgmt": dm}, {
                "feat": f"{at_lab} all", "mode": f"bank{bank:g}", "flag_h1": sum(1 for d in dm if d <= "2026-06-30"),
                "flag_h2": sum(1 for d in dm if d >= "2026-07-01")})
    return res


def nb_mgmt(i):
    return ((i["feat"], i.get("mode")), i["q"], [0.33, 0.5, 0.67]) if i.get("q") is not None else None


# ================================================================================================ 5 / 6. session range -> later trade
def box_feat(R, box, sub, norm="atr"):
    """trade key -> the day's `box` range (high - low) over the 14-day ATR (or the VIX one-day move) for trades with sub(t);
    the box must have closed before the entry (its last bar closed)."""
    M = R.M
    dk = day_index(R)
    out = {}
    for k_, t in R.by_key.items():
        if not sub(R, t):
            continue
        k = dk.get(t["day"])
        x = M.ctx[k]
        if box not in x:
            continue
        hi, lo, ki = x[box]
        if int(M.t[ki]) + 300 > int(t["entry_t"]):
            continue
        den = atr_d(R, k) if norm == "atr" else R.vm.get(t["day"])
        if not den:
            continue
        out[k_] = round((hi - lo) / den, 4)
    return out


def is_london(R, t):
    return 120 <= mod_of(R, t) < 480


def is_ny(R, t):
    return 480 <= mod_of(R, t) < 1080


TGT_MODES = {"wide+0.5": {"tgt_add_mv": 0.5}, "near x0.75": {"tgt_m": 0.75}, "bank5": {"max_rr": 5.0},
             "be0.75": {"be_r": 0.75}, "be1.5": {"be_r": 1.5}}


def ctx_days(R, days, spec):
    out = {}
    for d in days:
        o = {k: v for k, v in spec.items() if k != "tgt_add_mv"}
        if "tgt_add_mv" in spec:
            vm = R.vm.get(d)
            if not vm:
                continue
            o["tgt_add"] = spec["tgt_add_mv"] * float(vm)
        out[d] = o
    return out


def range_idea(R, box, sub, lab, min_n=20):
    res = {}
    for norm in ("atr", "vm"):
        f = box_feat(R, box, sub, norm)
        res.update(q_grid(R, f, f"{lab} range/{norm}", min_n=min_n))
        vals = [v for k, v in f.items() if "2026-01-01" <= k[0] <= "2026-06-30" and v is not None]
        if len(vals) < min_n:
            continue
        for q in (0.33, 0.5, 0.67):
            th = float(np.quantile(vals, q))
            for side in ("<=", ">="):
                days = {k[0] for k, v in f.items() if k[0] >= "2026-01-01" and v is not None and ((v <= th) if side == "<=" else (v >= th))}
                for mn, spec in TGT_MODES.items():
                    cd = ctx_days(R, days, spec)
                    info = {"feat": f"{lab} range/{norm} {side}", "mode": mn, "q": q, "th": th,
                            "flag_h1": sum(1 for d in cd if d <= "2026-06-30"), "flag_h2": sum(1 for d in cd if d >= "2026-07-01")}
                    res[f"{lab} range/{norm} {side} q{q} ({th:.3g}) -> {mn}"] = mgmt_eval(R, {"ctx_day": cd}, info)
    return res


def idea_asia(R):
    return range_idea(R, "asia20", is_london, "asia")


def idea_london(R):
    return range_idea(R, "lon25", is_ny, "london", min_n=12)    # only ~25 NY-time trades in 2026 (17 in H1)


# ================================================================================================ 7. news days
def news_flags(R):
    import csv
    ev_ = list(csv.DictReader(open(os.path.join(ROOT, "data", "news", "events.csv"), encoding="utf-8")))
    kinds = {"cpi": lambda e: e.startswith("CPI"), "nfp": lambda e: "Non-Farm Payrolls" in e and "ADP" not in e,
             "fomc": lambda e: e.startswith("FOMC rate decision"), "ppi": lambda e: e.startswith("PPI")}
    days = collections.defaultdict(set)
    times = collections.defaultdict(list)
    for r in ev_:
        for kd, fn in kinds.items():
            if fn(r["event"]):
                days[kd].add(r["date"])
                h, m = r["time_et"].split(":")
                times[r["date"]].append(int(h) * 60 + int(m))
    days["any4"] = set().union(*[days[k] for k in kinds])
    days["cpi_nfp"] = days["cpi"] | days["nfp"]
    out = {}
    for kd, ds in days.items():
        out[kd] = {k for k in R.by_key if k[0] in ds}
    # news still ahead at the entry (the trade is open into the release) vs already out
    ahead = {k for k, t in R.by_key.items() if k[0] in days["any4"] and any(m > mod_of(R, t) for m in times[k[0]])}
    out["any4_ahead"] = ahead
    out["any4_done"] = out["any4"] - ahead
    # the session before a news day (positioning day)
    S = F.SESS
    pre = {S[i] for i in range(len(S) - 1) if S[i + 1] in days["any4"]}
    out["eve_of_news"] = {k for k in R.by_key if k[0] in pre}
    n26 = {kd: (sum(1 for k in ks if "2026-01-01" <= k[0] <= "2026-06-30"), sum(1 for k in ks if k[0] >= "2026-07-01"))
           for kd, ks in out.items()}
    print("   news-flagged trades H1/H2:", n26, flush=True)
    RES.setdefault("_diag", {})["news_n"] = n26
    return out


def idea_news(R):
    return f_grid(R, news_flags(R), "news")


# ================================================================================================ 8. seasonality
def _is_holiday(d):
    """US exchange holiday (CME equity early close / closed): the early-close list of engine/lit_live.py, Good Friday, New
    Year's Day and Christmas (observed)."""
    from engine.lit_live import early_close, _easter
    if early_close(d.isoformat()) is not None and d.isoformat() != (d.replace(month=12, day=24)).isoformat() \
            and not (d.month == 11 and d.weekday() == 4):
        return True
    y = d.year
    fixed = []
    for m_, dd_ in ((1, 1), (12, 25)):
        x = dt.date(y, m_, dd_)
        fixed.append(x + dt.timedelta(days=1) if x.weekday() == 6 else x - dt.timedelta(days=1) if x.weekday() == 5 else x)
    return d in fixed or d == _easter(y) - dt.timedelta(days=2)


def early_close(d):
    from engine.lit_live import early_close as ec
    return ec(d)


def season_flags(R):
    S = F.SESS
    sset = set(S)
    out = collections.defaultdict(set)
    by_m = collections.defaultdict(list)
    for d in S:
        by_m[d[:7]].append(d)
    last_day = S[-1]
    for k in R.by_key:
        d = k[0]
        dd = dt.date.fromisoformat(d)
        wom = (dd.day - 1) // 7 + 1
        out[f"wom{min(wom, 5)}"].add(k)
        ms = by_m[d[:7]]
        if d == ms[0]:
            out["first_td"].add(k)
        if d == ms[-1] and d[:7] != last_day[:7]:
            out["last_td"].add(k)
        nx = dd + dt.timedelta(days=1)
        while nx.weekday() >= 5:
            nx += dt.timedelta(days=1)
        if (nx.isoformat() <= last_day and nx.isoformat() not in sset) or _is_holiday(nx):
            out["pre_holiday"].add(k)
        if _is_holiday(dd) or (early_close(d) is not None):
            out["holiday_or_early"].add(k)
        pv = dd - dt.timedelta(days=1)
        while pv.weekday() >= 5:
            pv -= dt.timedelta(days=1)
        if pv.isoformat() >= S[0] and pv.isoformat() not in sset:
            out["post_holiday"].add(k)
        if dd.day <= 7:
            out["first_week"].add(k)
        if (dd + dt.timedelta(days=7)).month != dd.month:
            out["last_week"].add(k)
    n26 = {kd: (sum(1 for k in ks if "2026-01-01" <= k[0] <= "2026-06-30"), sum(1 for k in ks if k[0] >= "2026-07-01"))
           for kd, ks in out.items()}
    print("   season-flagged trades H1/H2:", n26, flush=True)
    RES.setdefault("_diag", {})["season_n"] = n26
    return dict(out)


def idea_season(R):
    return f_grid(R, season_flags(R), "season")


# ================================================================================================ 9. unfilled 5m imbalance target
def fvgs(R, t, look="day", min_atr=0.0):
    """Unfilled opposite 5m imbalances beyond the entry of trade t (a long looks for bearish FVGs above: low[j-2] > high[j];
    their near edge = high[j]), formed by bars that closed before the entry and untouched (no 1m / 5m high reached the near
    edge) from their formation to the entry. Returns [(near, mid, far)] in direction space, nearest first."""
    M = R.M
    d = int(t["dir"])
    hi_d, lo_d = (M.h, M.l) if d == 1 else (-M.l, -M.h)
    dk = day_index(R)
    k = dk[t["day"]]
    s = M.days[k][1] if look == "day" else M.days[max(0, k - 1)][1]
    jl = last_closed5(R, t)
    e_d = float(t["entry_px"]) * d
    A_ = float(M.atr[jl])
    B = R.B1
    bh = B.h if d == 1 else -B.l
    out = []
    for j in range(s + 2, jl + 1):
        top, near = float(lo_d[j - 2]), float(hi_d[j])          # gap between bar j's high and bar j-2's low (direction space)
        # direction space for a long: bearish FVG above = lo(j-2) > hi(j) in real prices; in direction space the same
        if top - near <= max(min_atr * A_, lit.TICK) or near <= e_d:
            continue
        # untouched since formation: 5m bars j+1 .. jl, then 1m bars from jl's close to the entry
        if jl > j and float(hi_d[j + 1:jl + 1].max()) >= near:
            continue
        a1, b1 = np.searchsorted(B.t, int(M.t[jl]) + 300), np.searchsorted(B.t, int(t["entry_t"]))
        if b1 > a1 and float(bh[a1:b1].max()) >= near:
            continue
        out.append((near, 0.5 * (near + top), top))
    out.sort()
    return out


def idea_fvg(R):
    res = {}
    rk = {}
    for d, t in R.by_day.items():
        if t.get("tf") != 1:
            continue
        rk[d] = t
    for look in ("day", "2day"):
        for min_atr in (0.0, 0.25, 0.5):
            G = {d: fvgs(R, t, look, min_atr) for d, t in rk.items()}
            for edge_i, edge in enumerate(("near", "mid", "far")):
                for mode in ("alt", "near", "far"):
                    cd = {}
                    for d, t in rk.items():
                        dd = int(t["dir"])
                        e = float(t["entry_px"]) * dd
                        r = float(t["risk_pts"])
                        band = float(t["target_px"]) * dd
                        cands = [g[edge_i] for g in G[d] if g[edge_i] - e >= 1.5 * r]
                        if not cands:
                            continue
                        x = cands[0]
                        if mode == "near" and x >= band:
                            continue
                        if mode == "far":
                            far = [c for c in cands if c > band]
                            if not far:
                                continue
                            x = far[0]
                        if abs(x - band) < lit.TICK:
                            continue
                        cd[d] = {"tgt_px": round(x * dd, 2)}
                    info = {"feat": f"fvg {look} {edge} {mode}", "mode": mode, "q": None, "min_atr": min_atr,
                            "flag_h1": sum(1 for d in cd if d <= "2026-06-30"), "flag_h2": sum(1 for d in cd if d >= "2026-07-01")}
                    res[f"FVG target ({look}, {edge} edge, >= {min_atr} ATR) {mode}"] = mgmt_eval(R, {"ctx_day": cd}, info)
    return res


def nb_fvg(i):
    return ((i["feat"],), i["min_atr"], [0.0, 0.25, 0.5]) if "min_atr" in i else None


# ================================================================================================ 10. target scaled by the stop
def idea_stop_tgt(R):
    res = {}
    for S in (20.0, 30.0, 40.0, 50.0):
        for a in (0.25, 0.5, 1.0):
            cd = {d: {"tgt_m": round((S / float(t["risk_pts"])) ** a, 4)} for d, t in R.by_day.items() if float(t["risk_pts"]) > S}
            info = {"feat": f"tgt x (S/stop)^{a}", "S": S, "a": a, "mode": "scale",
                    "flag_h1": sum(1 for d in cd if d <= "2026-06-30"), "flag_h2": sum(1 for d in cd if d >= "2026-07-01")}
            res[f"stop > {S:g}: target x ({S:g}/stop)^{a}"] = mgmt_eval(R, {"ctx_day": cd}, info)
        for bank in (3.0, 4.0, 5.0):
            cd = {d: {"max_rr": bank} for d, t in R.by_day.items() if float(t["risk_pts"]) > S}
            info = {"feat": f"bank {bank:g}R if stop > S", "S": S, "mode": "bank",
                    "flag_h1": sum(1 for d in cd if d <= "2026-06-30"), "flag_h2": sum(1 for d in cd if d >= "2026-07-01")}
            res[f"stop > {S:g}: bank at {bank:g}R"] = mgmt_eval(R, {"ctx_day": cd}, info)
        # the mirror (control): a tight stop -> a farther target in R
        cd = {d: {"tgt_m": round((S / float(t["risk_pts"])) ** 0.25, 4)} for d, t in R.by_day.items() if float(t["risk_pts"]) < S}
        res[f"mirror: stop < {S:g}: target x ({S:g}/stop)^0.25"] = mgmt_eval(R, {"ctx_day": cd}, {
            "feat": "mirror", "S": S, "mode": "mirror", "flag_h1": sum(1 for d in cd if d <= "2026-06-30"),
            "flag_h2": sum(1 for d in cd if d >= "2026-07-01")})
    return res


def nb_stop(i):
    return ((i["feat"],), i["S"], [20.0, 30.0, 40.0, 50.0]) if "S" in i else None


# ================================================================================================ 11. robustness of the combo
def _patched(fn, slip=None, comm_x=None):
    """Run fn() with lit.SLIP (market entries + stop / BE / EOD / cut exits and adds) and the commissions patched."""
    old = (lit.SLIP, lit.COMM, A.ECOMM, BI.ECOMM, SZ.TW_COMM)
    try:
        if slip is not None:
            lit.SLIP = slip
        if comm_x is not None:
            lit.COMM = old[1] * comm_x
            A.ECOMM = BI.ECOMM = SZ.TW_COMM = old[2] * comm_x
        return fn()
    finally:
        lit.SLIP, lit.COMM, A.ECOMM, BI.ECOMM, SZ.TW_COMM = old


def slip_targets(T, ticks):
    """Target exits (resting limits) also n ticks worse: the harsh version of the slippage stress."""
    out = []
    for t in T:
        if t["exit"] != "TARGET" or not ticks:
            out.append(t)
            continue
        x = copy.deepcopy(t)
        dp = ticks * lit.TICK
        qt = t.get("qty_total", t["qty"])
        x["pnl"] = round(t["pnl"] - dp * lit.PV * qt, 2)
        if t.get("adds"):
            x["pts"] = round(t["pts"] - dp, 4)
            for a in x["adds"]:
                a["pts"] = round(a["pts"] - dp, 4)
        out.append(x)
    return out


def robust_one(nm, opts=None, slip=None, comm_x=None, tgt_ticks=0, drop=None, reps=50):
    def go():
        T = run_opts(nm, opts or {})
        T = slip_targets(T, tgt_ticks)
        U = AC.units(T)
        if drop is None:
            return {"eval": ev(U), "lit": lit_score(T), "n26": len(U)}
        rng = np.random.default_rng(20261020 + int(drop * 100))
        E, L = [], []
        for _ in range(reps):
            keep = rng.random(len(T)) >= drop
            TT = [t for t, k in zip(T, keep) if k]
            ks = {key(t) for t in TT}
            UU = [u for u in U if key(u) in ks]
            E.append(ev(UU))
            L.append(lit_score(TT))
        agg = {}
        for s in ("H1", "H2"):
            nets = [e[s]["net"] for e in E]
            agg[s] = {"net": round(float(np.mean(nets))), "net_p10": round(float(np.percentile(nets, 10))),
                      "net_p90": round(float(np.percentile(nets, 90))), "pf": round(float(np.mean([e[s]["pf"] or 0 for e in E])), 2),
                      "dd": round(float(np.mean([e[s]["dd"] for e in E]))), "p10": round(float(np.mean([e[s]["p10"] for e in E])), 1),
                      "f10": round(float(np.mean([e[s]["f10"] for e in E])), 1),
                      "mc_p10": round(float(np.mean([e[s]["mc_p10"] for e in E])), 1),
                      "mc_f10": round(float(np.mean([e[s]["mc_f10"] for e in E])), 1),
                      "per_month": round(float(np.mean([e[s]["per_month"] for e in E]))),
                      "tpw": round(float(np.mean([e[s]["tpw"] for e in E])), 2)}
        lagg = {s: {"net": round(float(np.mean([x[s]["net"] for x in L]))), "pf": round(float(np.mean([x[s]["pf"] or 0 for x in L])), 2)}
                for s in ("H1", "H2", "2021-25")}
        return {"eval": agg, "lit": lagg, "reps": reps}
    return _patched(go, slip=slip, comm_x=comm_x)


def idea_robust():
    t0 = time.time()
    out = {}
    tests = [("as tested", {}),
             ("+1 tick entries/exits (market orders)", {"slip": 0.5}),
             ("+2 ticks entries/exits (market orders)", {"slip": 0.75}),
             ("+4 ticks entries/exits (market orders)", {"slip": 1.25}),
             ("+1 tick everything (targets too)", {"slip": 0.5, "tgt_ticks": 1}),
             ("+2 ticks everything (targets too)", {"slip": 0.75, "tgt_ticks": 2}),
             ("+4 ticks everything (targets too)", {"slip": 1.25, "tgt_ticks": 4}),
             ("commission +50%", {"comm_x": 1.5}),
             ("1-bar (1 min) entry delay", {"opts": {"entry_delay": 1}}),
             ("2-bar (2 min) entry delay", {"opts": {"entry_delay": 2}}),
             ("10% missed fills (50 seeded draws)", {"drop": 0.10}),
             ("20% missed fills (50 seeded draws)", {"drop": 0.20}),
             ("worst case: +2 ticks all, comm +50%, 1-bar delay, 10% missed", {"slip": 0.75, "tgt_ticks": 2, "comm_x": 1.5,
                                                                                 "opts": {"entry_delay": 1}, "drop": 0.10})]
    for nm in REFS:
        out[nm] = {}
        for lab, kw in tests:
            kw = dict(kw)
            o = kw.pop("opts", {})
            r = robust_one(nm, opts=o, **kw)
            out[nm][lab] = r
            e = r["eval"]
            print(f"   [robust/{nm}] {lab:58s} " + " | ".join(
                f"{s} net {e[s]['net']:+,} PF {e[s]['pf']} DD {e[s]['dd']:,} 2w {e[s]['p10']}/{e[s]['f10']} mc {e[s]['mc_p10']}/{e[s]['mc_f10']}"
                for s in ("H1", "H2")) + f" | LIT {r['lit']['H1']['net']:+,}/{r['lit']['H2']['net']:+,}", flush=True)
    for nm in REFS:
        b = out[nm]["as tested"]["eval"]
        for lab in out[nm]:
            e = out[nm][lab]["eval"]
            out[nm][lab]["keep_pct"] = {s: round(100.0 * e[s]["net"] / b[s]["net"], 1) for s in ("H1", "H2")}
    # what the combo still adds over live under each stress
    out["combo_edge"] = {lab: {s: out["all3"][lab]["eval"][s]["net"] - out["base"][lab]["eval"][s]["net"] for s in ("H1", "H2")}
                         for lab, _ in tests}
    out["_secs"] = round(time.time() - t0)
    RES["robust"] = out
    dump()
    return out


# ================================================================================================ 12. stability of the combo
GRID = {"at": [10, 15, 20], "x": [0.2, 0.3, 0.4], "mfe": [0.3, 0.5, 0.7], "pb": [0.15, 0.25, 0.35], "f": [0.5, 0.75, 1.0],
        "be_off": [0.0, 0.75, 1.25, 1.75, 2.5]}
PICK = {"at": 15, "x": 0.3, "mfe": 0.5, "pb": 0.25, "f": 1.0, "be_off": 1.25}


def combo_opts(p):
    return {"t_check": {"at": p["at"], "x": p["x"], "mfe": p["mfe"]},
            "scale_in": {**AC.SCALE, "pb": p["pb"], "f": p["f"]}, "be_off": p["be_off"]}


def months_of(T, U):
    """Per month of 2026: LIT-rule net (engine trades) and eval-path net (back-to-back path of each half)."""
    lr = collections.defaultdict(float)
    for t in T:
        if t["day"] >= "2026-01-01":
            lr[t["day"][:7]] += t["pnl"]
    A._MC.clear()
    ep = collections.defaultdict(float)
    for sp in ("H1", "H2"):
        for t in A.b2b(U, sp)[0]:
            ep[t["day"][:7]] += t["pnl"]
    ms = sorted(set(lr) | set(ep))
    return {m: {"lit": round(lr.get(m, 0.0)), "eval": round(ep.get(m, 0.0))} for m in ms}


def idea_stable():
    import itertools
    t0 = time.time()
    keys = list(GRID)
    pts = [dict(zip(keys, v)) for v in itertools.product(*[GRID[k] for k in keys])]
    rows = []
    base_T = run_opts("base", {})
    base_U = AC.units(base_T)
    base_m = months_of(base_T, base_U)
    bev = ev(base_U)
    for n, p in enumerate(pts):
        T = F.run({**AC.LIVE, **combo_opts(p)})
        U = AC.units(T)
        for u in U:                      # lit_adopt_combo.units pins the adds' f to the live 1.0: use the grid point's f
            if u.get("adds"):
                u["add_f"] = p["f"]
        e = ev(U)
        rows.append({"p": p, "eval": {s: {k: e[s][k] for k in ("net", "pf", "dd", "p10", "f10", "mc_p10", "mc_f10")} for s in ("H1", "H2")},
                     "lit": {s: v["net"] for s, v in lit_score(T).items()}, "months": months_of(T, U)})
        if n % 100 == 0:
            print(f"   [stable] {n}/{len(pts)} {time.time() - t0:.0f}s", flush=True)
    pick = next(r for r in rows if r["p"] == PICK)
    # ridge: one-step neighbours of the pick (each parameter moved one grid step)
    nbs = []
    for k in keys:
        i = GRID[k].index(PICK[k])
        for j in (i - 1, i + 1):
            if 0 <= j < len(GRID[k]):
                q = {**PICK, k: GRID[k][j]}
                r = next(r for r in rows if r["p"] == q)
                nbs.append({"param": k, "value": GRID[k][j], "eval": r["eval"], "lit": r["lit"]})
    # one-at-a-time profile per parameter (others at the pick)
    prof = {k: [{"value": v, **{s: next(r for r in rows if r["p"] == {**PICK, k: v})["eval"][s] for s in ("H1", "H2")}}
                for v in GRID[k]] for k in keys}
    # marginal mean over the whole grid per parameter value
    marg = {k: [{"value": v, **{s: round(float(np.mean([r["eval"][s]["net"] for r in rows if r["p"][k] == v]))) for s in ("H1", "H2")}}
                for v in GRID[k]] for k in keys}
    beat = {s: sum(1 for r in rows if r["eval"][s]["net"] > bev[s]["net"]) for s in ("H1", "H2")}
    both = sum(1 for r in rows if all(r["eval"][s]["net"] > bev[s]["net"] for s in ("H1", "H2")))
    rank = {s: 1 + sum(1 for r in rows if r["eval"][s]["net"] > pick["eval"][s]["net"]) for s in ("H1", "H2")}
    h1best = max(rows, key=lambda r: r["eval"]["H1"]["net"])
    # walk-forward on the LIT-rule monthly net and on the eval-path monthly net: pick the best grid point on the 3 months
    # before, trade the next month with it
    ms = sorted(pick["months"])
    wf = {}
    for view in ("lit", "eval"):
        seq = []
        for i in range(3, len(ms)):
            tr, nx = ms[i - 3:i], ms[i]
            best = max(rows, key=lambda r: sum(r["months"].get(m, {}).get(view, 0) for m in tr))
            seq.append({"month": nx, "pick": best["p"], "wf": best["months"].get(nx, {}).get(view, 0),
                        "fixed": pick["months"].get(nx, {}).get(view, 0), "live": base_m.get(nx, {}).get(view, 0)})
        wf[view] = {"months": seq, "wf": sum(x["wf"] for x in seq), "fixed": sum(x["fixed"] for x in seq),
                    "live": sum(x["live"] for x in seq)}
        print(f"   [stable] walk-forward ({view}) {ms[3]}..{ms[-1]}: walk-forward {wf[view]['wf']:+,} fixed pick "
              f"{wf[view]['fixed']:+,} live {wf[view]['live']:+,}", flush=True)
    mon = {m: {"combo": pick["months"][m], "live": base_m.get(m)} for m in ms}
    out = {"n": len(rows), "pick": pick, "base_eval": {s: {k: bev[s][k] for k in ("net", "pf", "dd", "p10", "f10")} for s in ("H1", "H2")},
           "neighbours": nbs, "profile": prof, "marginal": marg, "beat_live": beat, "beat_live_both": both, "pick_rank": rank,
           "h1_best": {"p": h1best["p"], "eval": h1best["eval"]}, "walk_forward": wf, "months": mon, "_secs": round(time.time() - t0)}
    print(f"   [stable] grid {len(rows)}: beat live H1 {beat['H1']} H2 {beat['H2']} both {both}; pick rank H1 {rank['H1']} "
          f"H2 {rank['H2']}; H1-best {h1best['p']} -> H2 {h1best['eval']['H2']['net']:+,} (pick H2 {pick['eval']['H2']['net']:+,})",
          flush=True)
    for x in nbs:
        print(f"     neighbour {x['param']}={x['value']}: eval H1 {x['eval']['H1']['net']:+,} H2 {x['eval']['H2']['net']:+,} "
              f"2w fail {x['eval']['H1']['f10']}/{x['eval']['H2']['f10']}", flush=True)
    for m in ms:
        print(f"     {m}: combo LIT {mon[m]['combo']['lit']:+,} eval {mon[m]['combo']['eval']:+,} | live LIT "
              f"{(mon[m]['live'] or {}).get('lit', 0):+,} eval {(mon[m]['live'] or {}).get('eval', 0):+,}", flush=True)
    RES["stable"] = out
    dump()
    return out


# ================================================================================================ main
IDEAS = {"es_conf": (idea_es, nb_N), "rs": (idea_rs, nb_quant), "be_swing": (idea_be, nb_be), "day10": (idea_day10, nb_mgmt),
         "asia": (idea_asia, nb_quant), "london": (idea_london, nb_quant), "news": (idea_news, nb_quant),
         "season": (idea_season, nb_quant), "fvg": (idea_fvg, nb_fvg), "stop_tgt": (idea_stop_tgt, nb_stop)}


def main(which):
    global RES
    RES = json.load(open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
    RES["refs"] = {nm: {"eval": ref(nm).ev, "lit": {s: ref(nm).lr[s] for s in ("H1", "H2", "2021-25")}} for nm in REFS}
    for idea in which:
        print(f"== {idea}", flush=True)
        if idea == "robust":
            idea_robust()
        elif idea == "stable":
            idea_stable()
        else:
            fn, nb = IDEAS[idea]
            run_idea(idea, fn, nb)
    dump()


# ================================================================================================ store
def _he(e, s):
    x = e[s]
    return (f"n={x['n']} PF {x['pf']} net {x['net']:+,} (${x['per_month']:,}/mo) DD {x['dd']:,}; 2-week pass/fail "
            f"{x['p10']}/{x['f10']} (Monte Carlo {x['mc_p10']}/{x['mc_f10']}), 1 month {x['p20']}/{x['f20']}")


def _slug(s):
    import re
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_")[:56]


def rebuild(idea, nm, lab):
    """Re-run one screened variant (by label) -> (engine trades, units)."""
    R = ref(nm)
    fn, _ = IDEAS[idea]
    store_mode = {"T": None}
    # re-run only the wanted variant: patch tilt_eval / mgmt_eval to capture it
    got = {}
    orig_t, orig_m = globals()["tilt_eval"], globals()["mgmt_eval"]

    def cap_t(R_, mm, info):
        TT = [lit.scale_trade(t, m) if (m := mm.get(key(t), 1.0)) != 1.0 else t for t in R_.T]
        UU = [{**u, "m": mm.get(key(u), 1.0)} for u in R_.U]
        return {"info": info, "_TU": (TT, UU), "eval": None, "lit": None}

    def cap_m(R_, opts, info, same=True):
        return {"info": info, "_opts": opts, "eval": None, "lit": None}
    globals()["tilt_eval"], globals()["mgmt_eval"] = cap_t, cap_m
    try:
        res = fn(R)
    finally:
        globals()["tilt_eval"], globals()["mgmt_eval"] = orig_t, orig_m
    o = res[lab]
    _ = store_mode, got
    if "_TU" in o:
        return o["_TU"][0], o["_TU"][1], None
    T = run_opts(nm, o["_opts"])
    return T, AC.units(T), o["_opts"]


def store():
    from tools import runlib as rl
    R0 = json.load(open(OUT, encoding="utf-8"))
    Q = ("Owner 2026-10-20 (batch 3b): 12 ideas on LIT live and on the combo t_check + scale_in + be_off as size tilts / "
         "management tweaks (ES confirmation, NQ/ES relative strength, structure breakeven, 10:00 day type, Asia / London "
         "range, news days, seasonality, FVG targets, stop-scaled target), plus robustness and stability of the combo.")
    fam = {"es_conf": "risk", "rs": "risk", "be_swing": "management", "day10": "management", "asia": "risk", "london": "risk",
           "news": "risk", "season": "risk", "fvg": "targets", "stop_tgt": "targets"}
    for idea in IDEAS:
        if idea not in R0:
            continue
        for nm in REFS:
            S_ = R0[idea][nm]
            labs = [S_["top"][0]["label"]] + list(S_["adopt"])
            for lab in dict.fromkeys(labs):
                o = next((x for x in S_["top"] if x["label"] == lab), None)
                if o is None:
                    continue
                T, U, opts = rebuild(idea, nm, lab)
                A._MC.clear()
                Tp = []
                for sp in ("H1", "H2"):
                    Tp += A.b2b(U, sp)[0]
                for t in Tp:
                    t["risk_pts"] = t["risk"]; t["r"] = round(t["pnl"] / t["risk_usd"], 3) if t["risk_usd"] else 0.0
                    t.update(half=False, trigger="LIT-1m", mfe=None, mae=None, bars_held=None, regime="", mult=None, tgt_pts=t["tgt"])
                e, b, g = o["eval"], R0["refs"][nm]["eval"], o["_g"]
                other = R0[idea]["all3" if nm == "base" else "base"]["adopt"]
                # adopt-candidate only when the same variant passes on live LIT AND on the combo; one of the two = promising
                st = ("adopt-candidate" if lab in other else "promising") if lab in S_["adopt"] else "rejected"
                P = {**lit.DEFAULTS, **AC.LIVE, **REFS[nm]}
                if opts:
                    for k_, v in opts.items():
                        P[k_] = v if k_ in ("be_swing",) else f"{len(v)} days ({lab})" if isinstance(v, dict) else v
                rid = f"lit_b3b_{idea}_" + ("" if nm == "base" else "all3_") + _slug(lab)
                rl.save(rid, f"LIT {'live' if nm == 'base' else '+ all3'} + batch 3b {idea}: {lab}", fam[idea], Q, params=P,
                        sizing={"mode": "two_week", **A.CFG}, trades=Tp, scored=rl.score(Tp, A.S26), status=st,
                        verdict=f"Eval path (two_week 10 sessions then safe_eval, no reset, $1.90, true 1m). H1 (pick) {_he(e, 'H1')}. "
                                f"H2 (check) {_he(e, 'H2')}. Reference {nm}: H1 net {b['H1']['net']:+,} 2-week {b['H1']['p10']}/"
                                f"{b['H1']['f10']}, H2 net {b['H2']['net']:+,} 2-week {b['H2']['p10']}/{b['H2']['f10']}. LIT size "
                                f"rule change H1 {g['d_lit_h1']:+,} H2 {g['d_lit_h2']:+,}, 2021-25 reference {g['d_lit_ref']:+,}. "
                                f"Flagged {o['info'].get('flag_h1')}/{o['info'].get('flag_h2')}, changed {o['info'].get('chg_h1')}/"
                                f"{o['info'].get('chg_h2')}; strict {o['strict']}, neighbours hold: {o['nb_ok']}.",
                        notes="tools/lit_batch3b.py (stored trades = the back-to-back eval path per half).",
                        writeup="lit-batch3b", tags=["lit", "lit_b3b"])
                print("saved", rid, st, flush=True)
    # robustness: the combo under the worst-case stress, and live under the same
    if "robust" in R0:
        for nm in REFS:
            for lab, kw in (("plus2_all_comm50_delay1", {"slip": 0.75, "tgt_ticks": 2, "comm_x": 1.5, "opts": {"entry_delay": 1}}),):
                def go(nm=nm, kw=kw):
                    T = run_opts(nm, kw["opts"])
                    return slip_targets(T, kw["tgt_ticks"])
                T = _patched(go, slip=kw["slip"], comm_x=kw["comm_x"])
                U = AC.units(T)
                Tp = _patched(lambda: [x for sp in ("H1", "H2") for x in (A._MC.clear() or A.b2b(U, sp)[0])], comm_x=kw["comm_x"])
                for t in Tp:
                    t["risk_pts"] = t["risk"]; t["r"] = round(t["pnl"] / t["risk_usd"], 3) if t["risk_usd"] else 0.0
                    t.update(half=False, trigger="LIT-1m", mfe=None, mae=None, bars_held=None, regime="", mult=None, tgt_pts=t["tgt"])
                rr = R0["robust"][nm]
                ws = "+2 ticks everything (targets too)"
                rid = f"lit_b3b_robust_{'live' if nm == 'base' else 'all3'}_{lab}"
                P = {**lit.DEFAULTS, **AC.LIVE, **REFS[nm], "entry_delay": 1}
                rl.save(rid, f"LIT {'live' if nm == 'base' else '+ all3'} under stress: +2 ticks on every fill, commission +50%, "
                             f"1-minute entry delay", "other", Q, params=P, sizing={"mode": "two_week", **A.CFG, "comm_x": 1.5},
                        trades=Tp, scored=rl.score(Tp, A.S26), status="info",
                        verdict="Robustness (tools/lit_batch3b.py robust): " + "; ".join(
                            f"{k}: H1 {v['eval']['H1']['net']:+,} ({v['keep_pct']['H1']}%), H2 {v['eval']['H2']['net']:+,} "
                            f"({v['keep_pct']['H2']}%)" for k, v in rr.items() if k in ("as tested", ws, "commission +50%",
                                                                                     "1-bar (1 min) entry delay",
                                                                                     "20% missed fills (50 seeded draws)")),
                        notes="Stored trades: the back-to-back eval path under +2 ticks on every fill, commission +50% and a "
                              "1-minute entry delay (no missed fills).", writeup="lit-batch3b", tags=["lit", "lit_b3b"])
                print("saved", rid, flush=True)


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "store":
        store()
    else:
        main(args or list(IDEAS) + ["robust", "stable"])
