"""ATLAS + BLITZ edge search (night of 2026-10-29 -> 30): research/writeups/atlas-blitz-edge-2026-10-30.md. Research only:
nothing here touches second_model.json, engine/ or any live file.

BLITZ (the 1m noise-area scalp, engine/blitz.py) - today's rule as account C (tools/blitz25k_lib, never opposite LIT / ATLAS),
2026 on 1m bars (H1 pick, H2 check), 2021-25 the same rule on 5m bars (reference that must hold too). New ideas are SIZE
tilts (owner: prefer size changes over skipping): every trade is kept, its size x mult. Money:
  * "$500 view": each trade risks $500 x mult (fractional micros, costs in), $ a month, PF, avg R a trade;
  * the MFFU Builder 25K eval with the size pick of blitz-25k.md (40% of the room, 100% from session 5, <= $600, x mult),
    p10 / f10 / dec10 / p15 / f15 / slow_pass / pass_med, and the whole 25K slot $ a month (tools/blitz25k_size.life);
  * a placebo: the same multipliers shuffled over the span's trades (200 draws) -> how often chance does as well.
Plus: extra slippage on the 25K metrics, a 10:30 check added, a "break-and-hold" entry.

ATLAS (account B, Builder 25K: EMA + MACD + S/R) - tools/atlas_v2.score (the real account-B rules, back-to-back eval paths
from every 5th session), new: member weights from the member's own recent trades, a London-clock window in the US/UK DST
gap weeks, LIT copied in as a member, size by S/R level type / EMA pullback depth.

    python -X utf8 tools/ab_edge.py blitz         # BLITZ features, tilts, placebo, eval -> research/scalp/ab_blitz.json
    python -X utf8 tools/ab_edge.py blitzx        # BLITZ slippage / 10:30 check / break-and-hold -> research/scalp/ab_blitz_x.json
    python -X utf8 tools/ab_edge.py atlas         # ATLAS ideas -> research/second/ab_atlas.json
    python -X utf8 tools/ab_edge.py dst           # the DST-gap volume fact + the London-clock member windows
    python -X utf8 tools/ab_edge.py save          # runs ab_* in the run library
Paper research only.
"""
from __future__ import annotations

import collections
import copy
import datetime as dt
import itertools
import json
import os
import sys
import time
import warnings

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
warnings.filterwarnings("ignore")
import logging  # noqa: E402
logging.getLogger("engine.sizing").setLevel(logging.ERROR)

OUT_S = os.path.join(ROOT, "research", "scalp")
OUT_A = os.path.join(ROOT, "research", "second")
PICK_EZ = {"mode": "frac", "f": 0.4, "cap": 600.0, "push": (5, 1.0)}          # blitz-25k.md eval size pick
PICK_FZ = {"mode": "frac", "f": 0.1, "cap": 150.0, "day_tp": 400.0}           # its funded 25K size
EV_KEYS = ("p10", "f10", "dec10", "p15", "f15", "pass_med", "slow_pass", "pass20")


def _j(o):
    if isinstance(o, dict):
        return {str(k): _j(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_j(v) for v in o]
    if isinstance(o, (np.floating,)):
        return float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    return o


def dump(obj, path):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(_j(obj), fh, indent=1)


# ================================================================================================ BLITZ: trades + features
_B = {}


def blitz_libs():
    from tools import scalp_na_lib as N
    from tools import blitz25k_lib as K
    from tools import blitz25k_size as BS
    K.install_qty()
    return N, K, BS


def blitz_trades(v=None, cmode="lit+atlas"):
    """today's BLITZ (or variant v) as account C: {1: 2026 1m trades, 5: 2021-25 5m trades} with features attached."""
    N, K, BS = blitz_libs()
    key = json.dumps([v or {}, cmode], sort_keys=True)
    if key in _B:
        return _B[key]
    TT = K.trades(v or {}, cmode)
    for tf in (1, 5):
        attach(N.bars(tf), TT[tf])
    _B[key] = TT
    return TT


_DF = {}


def day_feats(B):
    """per day id: overnight range (prior date 18:00 -> 09:30) / its 14-day mean, first-hour volume / its 20-day mean,
    the VIX change into the day (prior close / the close before), the 14-day mean RTH range."""
    k = (B["tf"], len(B["t"]))
    if k in _DF:
        return _DF[k]
    N, K, BS = blitz_libs()
    X = N._day_ctx(B)
    m, h, l, v = B["mod"], B["h"], B["l"], B["v"]
    nd = len(B["dates"])
    on_r = np.full(nd, np.nan)
    on_hi = np.full(nd, np.nan)
    on_lo = np.full(nd, np.nan)
    fh_v = np.full(nd, np.nan)
    starts = np.r_[0, np.where(np.diff(B["day"]) != 0)[0] + 1]
    ends = np.r_[starts[1:], len(B["day"])]
    eve = None
    ons, fhs = [], []
    for s, e in zip(starts, ends):
        di = int(B["day"][s])
        mm = m[s:e]
        pre = np.where(mm < 570)[0] + s
        his, los = [], []
        if len(pre):
            his.append(float(h[pre].max())); los.append(float(l[pre].min()))
        if eve:
            his.append(eve[0]); los.append(eve[1])
        if his:
            r = max(his) - min(los)
            on_hi[di], on_lo[di] = max(his), min(los)
            if len(ons) >= 10:
                on_r[di] = r / float(np.mean(ons[-14:]))
            ons.append(r)
        fh = np.where((mm >= 570) & (mm < 630))[0] + s
        if len(fh) >= 3:
            vv = float(v[fh].sum())
            if len(fhs) >= 10:
                fh_v[di] = vv / float(np.mean(fhs[-20:]))
            fhs.append(vv)
        ev = np.where(mm >= 1080)[0] + s
        eve = (float(h[ev].max()), float(l[ev].min())) if len(ev) else None
    import bisect
    dates = B["dates"]
    vchg = np.full(nd, np.nan)
    N.prev_close("VIX", dates[0])                      # loads the VIX file
    ks, vs = N._M["VIX"]
    for di, d in enumerate(dates):
        k = bisect.bisect_left(ks, d) - 1              # the prior session's close and the one before (known before the open)
        if k >= 1 and vs[k - 1]:
            vchg[di] = vs[k] / vs[k - 1] - 1
    _DF[k] = {"on_r": on_r, "fh_v": fh_v, "vix_chg": vchg, "rng14": X["rng14"], "o930": X["o930"], "on_hi": on_hi, "on_lo": on_lo}
    return _DF[k]


FEATS = ("rng_sofar", "fh_ratio", "fh_v", "on_r", "on_pos", "gap_abs", "gap_with", "vix_chg", "vix", "exc", "nth", "held", "vwap_dist",
         "vwap_with", "mod", "prng_ratio", "td")


def attach(B, T):
    """features known at each trade's signal close (scalp_na_lib.signals features + new day / intraday facts)."""
    N, K, BS = blitz_libs()
    F = N.signals(B, 1.0, 30, (630, 930), 1.5)
    pos = {int(i): q for q, i in enumerate(F["sig"])}
    D = day_feats(B)
    sg, op = N._noise(B)
    c, h, l = B["c"], B["h"], B["l"]
    ev = max(1, int(round(30 / B["tf"])))
    day_start = {}
    for t in T:
        i = int(np.searchsorted(B["t"], t["sig_t"]))
        q = pos.get(i)
        di = int(B["day"][i])
        if di not in day_start:
            s = int(np.searchsorted(B["day"], di))
            while B["mod"][s] < 570:
                s += 1
            day_start[di] = s
        s0 = day_start[di]
        f = {}
        f["rng_sofar"] = float((h[s0:i + 1].max() - l[s0:i + 1].min()) / D["rng14"][di]) if D["rng14"][di] == D["rng14"][di] else np.nan
        f["fh_v"], f["on_r"], f["vix_chg"] = float(D["fh_v"][di]), float(D["on_r"][di]), float(D["vix_chg"][di])
        # where the 09:30 open sits in the overnight range, on the trade's side (1 = at the overnight extreme of the trade's side)
        oh, ol, o9 = D["on_hi"][di], D["on_lo"][di], D["o930"][di]
        f["on_pos"] = float(((o9 - ol) / (oh - ol)) if t["dir"] > 0 else ((oh - o9) / (oh - ol))) if (oh == oh and oh > ol and o9 == o9) else np.nan
        if q is not None:
            for nm in ("fh_ratio", "gap", "gap_with", "vix", "exc", "nth", "prng_ratio", "fh_with", "vwap_with"):
                f[nm] = float(F[nm][q])
        f["gap_abs"] = abs(f.get("gap", np.nan))
        # break-and-hold: the previous 30-minute check (10:30 for the 11:00 check) also closed beyond the band, same side
        j = i - ev
        dr = t["dir"]
        if j >= s0 and sg[j] == sg[j]:
            f["held"] = 1.0 if dr * (c[j] - op[j]) > op[j] * sg[j] else 0.0
        else:
            f["held"] = 0.0
        f["vwap_dist"] = float(dr * (c[i] - B["vwap"][i]) / B["atr5"][i]) if B["vwap"][i] == B["vwap"][i] else np.nan
        f["mod"] = float(B["mod"][i] + B["tf"])
        t["f"] = f
    # composite trend-day score (pre-declared): mean percentile of the day's activity known at the signal
    for t in T:
        t["f"]["td"] = np.nan
    return T


def td_score(TT, cuts):
    """trend-day score = mean of the three activity facts' percentiles within the 2026 H1 trades (rng_sofar, fh_ratio,
    fh_v); cuts = sorted H1 values per fact."""
    for tf in (1, 5):
        for t in TT[tf]:
            p = []
            for nm in ("rng_sofar", "fh_ratio", "fh_v"):
                x = t["f"].get(nm, np.nan)
                if x == x:
                    p.append(np.searchsorted(cuts[nm], x) / len(cuts[nm]))
            t["f"]["td"] = float(np.mean(p)) if len(p) == 3 else np.nan


# ================================================================================================ BLITZ: scoring
def spans_of(TT):
    N, K, BS = blitz_libs()
    out = {}
    for sp, tf in K.SPANS:
        T, S = K.span(TT, sp, tf)
        out[sp] = (T, S)
    return out


def rview(T, S, mult=None, usd=500.0):
    """the $500 view: each trade risks usd x mult (fractional micros), costs in."""
    if not T:
        return {"n": 0}
    R = np.array([t["pnl_pm"] / t["risk_pm"] for t in T])
    m = np.ones(len(T)) if mult is None else np.asarray(mult, float)
    pnl = usd * m * R
    gl = -pnl[pnl < 0].sum()
    eq = np.cumsum(pnl)
    months = len(S) / 21.0
    wk = collections.Counter(dt.date.fromisoformat(t["day"]).isocalendar()[:2] for t in T)
    allw = {dt.date.fromisoformat(d).isocalendar()[:2] for d in S}
    return {"n": len(T), "tpw": round(len(T) / (len(S) / 5), 2), "wk2": round(100.0 * sum(1 for w in allw if wk.get(w, 0) >= 2) / len(allw), 1),
            "avg_r": round(float(R.mean()), 3), "r_per_risk": round(float((m * R).sum() / m.sum()), 3), "mean_mult": round(float(m.mean()), 3),
            "pf": round(float(pnl[pnl > 0].sum() / gl), 2) if gl else 99.0, "net": round(float(pnl.sum())),
            "per_month": round(float(pnl.sum() / months)), "dd": round(float((eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min())),
            "win": round(100.0 * float((R > 0).mean()), 1)}


def with_mult(T, m):
    return [{**t, "mult": float(x)} for t, x in zip(T, m)]


def ev25(T, S, m=None, ez=PICK_EZ):
    N, K, BS = blitz_libs()
    Tm = T if m is None else with_mult(T, m)
    e = BS.eval_score(Tm, S, ez)
    return {k: e.get(k) for k in EV_KEYS}


def slot25(T, S, m=None, ez=PICK_EZ, fz=PICK_FZ, n=300):
    N, K, BS = blitz_libs()
    Tm = T if m is None else with_mult(T, m)
    return BS.life(Tm, S, ez, fz, n=n)


def tilt_mult(T, nm, lo_cut, hi_cut, up, dn, sign=1):
    """sign +1: top (>= hi_cut) x up, bottom (< lo_cut) x dn; sign -1 mirrored. NaN -> 1."""
    m = np.ones(len(T))
    for k, t in enumerate(T):
        x = t["f"].get(nm, np.nan)
        if x != x:
            continue
        top, bot = x >= hi_cut, x < lo_cut
        if sign < 0:
            top, bot = bot, top
        m[k] = up if top else dn if bot else 1.0
    return m


def cuts_h1(T, nm, mode):
    x = np.array([t["f"].get(nm, np.nan) for t in T], float)
    x = x[x == x]
    if nm in ("held", "gap_with", "vwap_with", "fh_with"):
        return 0.5, 0.5                                # binary facts: 1 = top, 0 = bottom
    if nm == "nth":
        return 1.5, 1.5                                # first signal of the day vs later ones
    if mode == "terc":
        return float(np.quantile(x, 1 / 3)), float(np.quantile(x, 2 / 3))
    if mode == "med":
        q = float(np.quantile(x, 0.5))
        return q, q
    if mode == "quart":
        return float(np.quantile(x, 0.25)), float(np.quantile(x, 0.75))
    raise ValueError(mode)


def placebo_p(T, S, m, base_money, n=200, seed=11):
    """share of shuffled multiplier sets (same multiset over the span's trades) with $500-view money >= the real tilt's."""
    rng = np.random.default_rng(seed)
    R = np.array([t["pnl_pm"] / t["risk_pm"] for t in T])
    real = float((np.asarray(m) * R).sum())
    hits = 0
    for _ in range(n):
        hits += float((rng.permutation(m) * R).sum()) >= real - 1e-9
    return round(hits / n, 3)


def cmd_blitz():
    t0 = time.time()
    N, K, BS = blitz_libs()
    TT = blitz_trades()
    SP = spans_of(TT)
    H1T = SP["H1"][0]
    cuts = {nm: np.sort([t["f"][nm] for t in H1T if t["f"].get(nm, np.nan) == t["f"].get(nm, np.nan)]) for nm in ("rng_sofar", "fh_ratio", "fh_v")}
    td_score(TT, cuts)
    SP = spans_of(TT)
    out = {"built": time.strftime("%Y-%m-%d %H:%M"), "what": "BLITZ size tilts (account C, today's rule)", "base": {}, "feats": {}, "tilts": []}
    # 1. baseline
    for sp, (T, S) in SP.items():
        out["base"][sp] = {"r500": rview(T, S), "ev": ev25(T, S), "slot": slot25(T, S)}
        print(sp, out["base"][sp], flush=True)
    # 2. what each fact says (avg R by H1 tercile, every span)
    for nm in FEATS:
        lo, hi = cuts_h1(H1T, nm, "terc")
        row = {"cuts": [lo, hi]}
        for sp, (T, S) in SP.items():
            x = np.array([t["f"].get(nm, np.nan) for t in T], float)
            R = np.array([t["pnl_pm"] / t["risk_pm"] for t in T])
            g = {"bot": R[(x < lo) & (x == x)], "mid": R[(x >= lo) & (x < hi)], "top": R[x >= hi]}
            row[sp] = {k: [int(len(v)), round(float(v.mean()), 3) if len(v) else None] for k, v in g.items()}
        out["feats"][nm] = row
        print(f"{nm:10s} cuts {lo:.3f}/{hi:.3f}  " + "  ".join(f"{sp} " + " ".join(f"{k}:{v[0]}/{v[1]}" for k, v in row[sp].items()) for sp in SP), flush=True)
    # 3. tilts (pre-declared): fact x direction x cut mode x (up, down)
    grid = []
    for nm in FEATS:
        for sign in (1, -1):
            for mode in ("terc", "med", "quart"):
                if nm in ("held", "gap_with", "vwap_with", "nth") and mode != "terc":
                    continue
                for up, dn in ((1.5, 0.5), (1.25, 0.75), (2.0, 0.5), (1.0, 0.5), (1.5, 1.0)):
                    grid.append((nm, sign, mode, up, dn))
    rows = []
    for nm, sign, mode, up, dn in grid:
        lo, hi = cuts_h1(H1T, nm, mode)
        r = {"f": nm, "sign": sign, "mode": mode, "up": up, "dn": dn, "cuts": [lo, hi]}
        for sp, (T, S) in SP.items():
            m = tilt_mult(T, nm, lo, hi, up, dn, sign)
            r[sp] = rview(T, S, m)
        rows.append(r)
    b = {sp: out["base"][sp]["r500"] for sp in SP}

    def better(r, sp):        # per unit of risk AND in money (a tilt must not win only by risking more on average)
        return r[sp]["r_per_risk"] > b[sp]["avg_r"] and r[sp]["per_month"] > b[sp]["per_month"]
    for r in rows:
        r["h1"], r["h2"], r["ref"] = better(r, "H1"), better(r, "H2"), better(r, "R")
    # the H1 pick: best H1 r_per_risk gain among tilts with mean mult within 0.8-1.25 (risk-neutral-ish)
    cand = [r for r in rows if r["h1"] and 0.8 <= r["H1"]["mean_mult"] <= 1.25]
    cand.sort(key=lambda r: -(r["H1"]["r_per_risk"] - b["H1"]["avg_r"]))
    out["n_tilts"] = len(rows)
    out["n_h1"] = sum(r["h1"] for r in rows)
    out["n_h1_h2"] = sum(r["h1"] and r["h2"] for r in rows)
    out["n_all3"] = sum(r["h1"] and r["h2"] and r["ref"] for r in rows)
    print(f"tilts {len(rows)}: better H1 {out['n_h1']}, H1+H2 {out['n_h1_h2']}, all three {out['n_all3']}", flush=True)
    # 4. eval + slot + placebo for: the top 12 H1 picks, every all-three survivor
    look = cand[:12] + [r for r in rows if r["h1"] and r["h2"] and r["ref"] and r not in cand[:12]]
    for r in look:
        for sp, (T, S) in SP.items():
            m = tilt_mult(T, r["f"], r["cuts"][0], r["cuts"][1], r["up"], r["dn"], r["sign"])
            r[sp]["ev"] = ev25(T, S, m)
            r[sp]["slot"] = slot25(T, S, m)["life_pm"]
            r[sp]["placebo_p"] = placebo_p(T, S, m, None)
        r["scored"] = True
        print(f"{r['f']:10s} s{r['sign']:+d} {r['mode']:5s} x{r['up']}/{r['dn']}  " + " | ".join(
            f"{sp} R/risk {r[sp]['r_per_risk']:+.3f} ${r[sp]['per_month']}/mo PF {r[sp]['pf']} 2w {r[sp]['ev']['p10']}/{r[sp]['ev']['f10']} "
            f"slot ${r[sp]['slot']} p{r[sp]['placebo_p']}" for sp in SP), flush=True)
    out["h1_picks"] = [r for r in cand[:12]]
    out["all3"] = [r for r in rows if r["h1"] and r["h2"] and r["ref"]]
    out["rows_compact"] = [{k: r[k] for k in ("f", "sign", "mode", "up", "dn", "h1", "h2", "ref")} | {sp: {kk: r[sp][kk] for kk in ("r_per_risk", "per_month", "pf", "mean_mult")} for sp in SP} for r in rows]
    dump(out, os.path.join(OUT_S, "ab_blitz.json"))
    print(f"done {time.time() - t0:.0f}s", flush=True)
    return out


# ================================================================================================ BLITZ: the checks of the survivors
GRID_FACTS = FEATS


def tilt_grid():
    g = []
    for nm in GRID_FACTS:
        for sign in (1, -1):
            for mode in ("terc", "med", "quart"):
                if nm in ("held", "gap_with", "vwap_with", "nth") and mode != "terc":
                    continue
                for up, dn in ((1.5, 0.5), (1.25, 0.75), (2.0, 0.5), (1.0, 0.5), (1.5, 1.0)):
                    g.append((nm, sign, mode, up, dn))
    return g


def _prep_blitz():
    TT = blitz_trades()
    SP = spans_of(TT)
    H1T = SP["H1"][0]
    cuts = {nm: np.sort([t["f"][nm] for t in H1T if t["f"].get(nm, np.nan) == t["f"].get(nm, np.nan)]) for nm in ("rng_sofar", "fh_ratio", "fh_v")}
    td_score(TT, cuts)
    return TT, spans_of(TT)


def _fact_arrays(SP):
    """span -> (R array, {fact: values array})"""
    out = {}
    for sp, (T, S) in SP.items():
        R = np.array([t["pnl_pm"] / t["risk_pm"] for t in T])
        out[sp] = (R, {nm: np.array([t["f"].get(nm, np.nan) for t in T], float) for nm in GRID_FACTS})
    return out


def _mult_arr(x, lo, hi, up, dn, sign):
    m = np.ones(len(x))
    ok = x == x
    top, bot = (x >= hi) & ok, (x < lo) & ok
    if sign < 0:
        top, bot = bot, top
    m[top], m[bot] = up, dn
    return m


def survivors(FA, cuts, months, grid=None):
    """the 390-tilt grid on arrays: per (fact, sign) the number of variants better per unit of risk AND in $ in all three
    spans (the same test as cmd_blitz)."""
    grid = grid or tilt_grid()
    base = {sp: (float(FA[sp][0].mean()), float(FA[sp][0].sum()) / months[sp]) for sp in FA}
    cnt = collections.Counter()
    for nm, sign, mode, up, dn in grid:
        lo, hi = cuts[(nm, mode)]
        ok = True
        for sp in ("H1", "H2", "R"):
            R, F = FA[sp]
            m = _mult_arr(F[nm], lo, hi, up, dn, sign)
            if not ((m * R).sum() / m.sum() > base[sp][0] and (m * R).sum() / months[sp] > base[sp][1]):
                ok = False
                break
        if ok:
            cnt[(nm, sign)] += 1
    return cnt


def per_year(T, m):
    """avg R a trade and R per unit of risk by calendar year (2026 by half)."""
    out = {}
    R = np.array([t["pnl_pm"] / t["risk_pm"] for t in T])
    yrs = np.array([t["day"][:4] if t["day"] < "2026-01-01" else ("2026H1" if t["day"] < "2026-07-01" else "2026H2") for t in T])
    for y in sorted(set(yrs)):
        k = yrs == y
        out[y] = {"n": int(k.sum()), "avg_r": round(float(R[k].mean()), 3), "tilt_r_per_risk": round(float((m[k] * R[k]).sum() / m[k].sum()), 3),
                  "delta": round(float((m[k] * R[k]).sum() / m[k].sum() - R[k].mean()), 3)}
    return out


CANDS = [("rng_sofar", 1, "med", 1.5, 0.5), ("rng_sofar", 1, "terc", 1.5, 0.5), ("rng_sofar", 1, "med", 2.0, 0.5),
         ("rng_sofar", 1, "terc", 1.25, 0.75), ("rng_sofar", 1, "quart", 1.5, 0.5), ("nth", 1, "terc", 1.5, 0.5), ("nth", 1, "terc", 1.0, 0.5),
         ("gap_abs", 1, "terc", 1.5, 0.5), ("vix_chg", -1, "med", 1.5, 0.5), ("exc", 1, "med", 1.5, 0.5), ("prng_ratio", 1, "med", 1.5, 0.5)]


def cand_mult(T, c, H1T):
    nm, sign, mode, up, dn = c
    lo, hi = cuts_h1(H1T, nm, mode)
    return tilt_mult(T, nm, lo, hi, up, dn, sign)


def cname(c):
    nm, sign, mode, up, dn = c
    return f"{nm} {'high' if sign > 0 else 'low'} {mode} x{up}/{dn}"


def cmd_blitz2(reps=100):
    """family placebo (shuffled facts), per-year table, fixed-threshold ramps, the 25K eval-size grid with the tilt."""
    t0 = time.time()
    N, K, BS = blitz_libs()
    TT, SP = _prep_blitz()
    H1T = SP["H1"][0]
    months = {sp: len(S) / 21.0 for sp, (T, S) in SP.items()}
    grid = tilt_grid()
    cuts = {}
    for nm in GRID_FACTS:
        for mode in ("terc", "med", "quart"):
            cuts[(nm, mode)] = cuts_h1(H1T, nm, mode)
    FA = _fact_arrays(SP)
    real = survivors(FA, cuts, months, grid)
    out = {"built": time.strftime("%Y-%m-%d %H:%M"), "real": {f"{a} {b:+d}": v for (a, b), v in real.items()}, "real_total": sum(real.values())}
    print("real survivors", sum(real.values()), dict(real), flush=True)
    # (a) family placebo: every fact's values shuffled over the span's trades (the R stay), the whole grid re-run
    rng = np.random.default_rng(5)
    tot, per = [], collections.defaultdict(list)
    for rep in range(reps):
        FP = {}
        for sp, (R, F) in FA.items():
            FP[sp] = (R, {nm: rng.permutation(v) for nm, v in F.items()})
        # H1 cuts unchanged (a permutation keeps the H1 distribution)
        c = survivors(FP, cuts, months, grid)
        tot.append(sum(c.values()))
        for k in real:
            per[k].append(c.get(k, 0))
    out["placebo_total_mean"] = round(float(np.mean(tot)), 1)
    out["placebo_total_p95"] = float(np.percentile(tot, 95))
    out["placebo_total_ge_real"] = round(float(np.mean(np.array(tot) >= sum(real.values()))), 3)
    # one fact family (up to 15 variants): how often does a shuffled fact reach the real count?
    fam = {}
    for k, v in real.items():
        # the max over all 30 fact-directions in a placebo rep is the fair comparison for the best real family
        fam[f"{k[0]} {k[1]:+d}"] = {"real": v, "placebo_mean": round(float(np.mean(per[k])), 2), "p_same_fact": round(float(np.mean(np.array(per[k]) >= v)), 3)}
    out["family"] = fam
    print("placebo total mean", out["placebo_total_mean"], "p95", out["placebo_total_p95"], "share >= real", out["placebo_total_ge_real"], flush=True)
    print(json.dumps(fam), flush=True)
    # best family count in each placebo rep (any fact): chance of a family with >= 11 of 15
    best = []
    rng = np.random.default_rng(9)
    for rep in range(reps):
        FP = {sp: (R, {nm: rng.permutation(v) for nm, v in F.items()}) for sp, (R, F) in FA.items()}
        c = survivors(FP, cuts, months, grid)
        best.append(max(c.values()) if c else 0)
    out["placebo_best_family"] = {"mean": round(float(np.mean(best)), 2), "p95": float(np.percentile(best, 95)),
                                  "share_ge_real_best": round(float(np.mean(np.array(best) >= max(real.values()))), 3)}
    print("best family in a placebo rep", out["placebo_best_family"], flush=True)
    # (b) per-year table + a 1,000-draw multiplier placebo per candidate
    out["cands"] = {}
    for c in CANDS:
        row = {}
        for sp, (T, S) in SP.items():
            m = cand_mult(T, c, H1T)
            row[sp] = rview(T, S, m)
            row[sp]["placebo_p"] = placebo_p(T, S, m, None, n=1000)
        TA = SP["R"][0] + SP["H1"][0] + SP["H2"][0]
        row["years"] = per_year(TA, cand_mult(TA, c, H1T))
        out["cands"][cname(c)] = row
        print(cname(c), {y: v["delta"] for y, v in row["years"].items()}, {sp: row[sp]["placebo_p"] for sp in SP}, flush=True)
    # (c) fixed thresholds (no quantile): rng_sofar >= x of the 14-day mean range -> x1.5, else x0.5 / x0.75
    out["ramps"] = {}
    for thr in (0.6, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.4):
        for dn in (0.5, 0.75):
            r = {}
            for sp, (T, S) in SP.items():
                x = np.array([t["f"]["rng_sofar"] for t in T])
                m = np.where(x >= thr, 1.5, dn)
                r[sp] = rview(T, S, m)
            out["ramps"][f"rng_sofar>={thr} x1.5 else x{dn}"] = r
            print(f"rng_sofar>={thr} x1.5/x{dn}: " + " | ".join(f"{sp} {r[sp]['r_per_risk']:+.3f} ${r[sp]['per_month']}" for sp in SP), flush=True)
    # continuous ramp: mult = clip(rng_sofar / H1 median, 0.5, 1.5)
    med = float(np.median([t["f"]["rng_sofar"] for t in H1T]))
    r = {}
    for sp, (T, S) in SP.items():
        x = np.array([t["f"]["rng_sofar"] for t in T])
        r[sp] = rview(T, S, np.clip(x / med, 0.5, 1.5))
    out["ramps"]["continuous clip(rng_sofar / H1 median, 0.5, 1.5)"] = r
    print("continuous:", " | ".join(f"{sp} {r[sp]['r_per_risk']:+.3f} ${r[sp]['per_month']}" for sp in SP), flush=True)
    dump(out, os.path.join(OUT_S, "ab_blitz2.json"))
    print(f"done {time.time() - t0:.0f}s", flush=True)
    return out


def eval_grid_specs():
    G = []
    for f, push in itertools.product((0.3, 0.4, 0.5, 0.6), (None, (4, 1.0), (5, 1.0), (6, 1.0), (5, 0.8), (8, 1.0))):
        z = {"mode": "frac", "f": f, "cap": 600.0}
        if push:
            z["push"] = push
        G.append(z)
    return G


def _ezname(z):
    s = f"f{z['f']}"
    if z.get("push"):
        s += f" push s{z['push'][0]}->{z['push'][1]}"
    return s


def cmd_blitz_eval(n_final=1000):
    """the 25K eval sizes x tilts (today = no tilt): eval metrics for all, the whole slot for the H1 finalists. Pick on H1:
    the highest H1 slot $ among sizes that decide >= 70% in 2 weeks with <= 10% of passes slower than 3 weeks."""
    t0 = time.time()
    N, K, BS = blitz_libs()
    TT, SP = _prep_blitz()
    H1T = SP["H1"][0]
    tilts = [None] + CANDS[:7]
    rows = []
    for c in tilts:
        for z in eval_grid_specs():
            r = {"tilt": cname(c) if c else "none", "c": c, "z": z, "name": _ezname(z)}
            for sp, (T, S) in SP.items():
                m = cand_mult(T, c, H1T) if c else None
                r[sp] = ev25(T, S, m, z)
            rows.append(r)
    print(f"{len(rows)} eval rows {time.time() - t0:.0f}s", flush=True)
    ok = [r for r in rows if r["H1"]["dec10"] >= 70.0 and (r["H1"]["slow_pass"] or 0) <= 10.0]
    # slot for the speed-qualified rows (n 300 screen, then n_final for the top 10 by H1 and the base pick)
    for r in ok:
        for sp, (T, S) in SP.items():
            m = cand_mult(T, r["c"], H1T) if r["c"] else None
            r[sp]["slot"] = slot25(T, S, m, r["z"], PICK_FZ, n=300)["life_pm"]
    ok.sort(key=lambda r: -r["H1"]["slot"])
    fin = ok[:10]
    base = next(r for r in rows if r["tilt"] == "none" and r["z"] == {"mode": "frac", "f": 0.4, "cap": 600.0, "push": (5, 1.0)})
    if base not in fin:
        fin.append(base)
    for r in fin:
        for sp, (T, S) in SP.items():
            m = cand_mult(T, r["c"], H1T) if r["c"] else None
            L = slot25(T, S, m, r["z"], PICK_FZ, n=n_final)
            r[sp]["slot_final"] = L["life_pm"]
            r[sp]["slot_lose"] = L["life_lose"]
        print(f"{r['tilt']:34s} {r['name']:20s} " + " | ".join(
            f"{sp} 2w {r[sp]['p10']}/{r[sp]['f10']} dec {r[sp]['dec10']} slow {r[sp]['slow_pass']} med {r[sp]['pass_med']} slot ${r[sp]['slot_final']}"
            for sp in SP), flush=True)
    out = {"built": time.strftime("%Y-%m-%d %H:%M"), "rows": [{k: v for k, v in r.items() if k != "c"} for r in rows],
           "qualified": len(ok), "finalists": [{k: v for k, v in r.items() if k != "c"} for r in fin],
           "base": {k: v for k, v in base.items() if k != "c"}}
    dump(out, os.path.join(OUT_S, "ab_blitz_eval.json"))
    print(f"done {time.time() - t0:.0f}s", flush=True)
    return out


NTH = [("nth", 1, "terc", 1.5, 0.5), ("nth", 1, "terc", 1.25, 0.75), ("nth", 1, "terc", 1.0, 0.5), ("nth", 1, "terc", 2.0, 0.5),
       ("nth", 1, "terc", 1.5, 1.0)]


def cmd_blitz_nth(n_final=1000, n_pl=40):
    """the "later break of the day" size (first band break of the day x dn, a later same-side break x up = break-and-hold /
    trend-day confirmation as a SIZE): 25K eval sizes, whole slots, and a placebo of the eval effect (the same multipliers
    shuffled over the span's trades)."""
    t0 = time.time()
    N, K, BS = blitz_libs()
    TT, SP = _prep_blitz()
    H1T = SP["H1"][0]
    sizes = [{"mode": "frac", "f": f, "cap": 600.0, "push": p} for f in (0.3, 0.4, 0.5, 0.6) for p in ((4, 1.0), (5, 1.0), (6, 1.0))]
    sizes.append({"mode": "frac", "f": 0.4, "cap": 600.0})
    rows = []
    for c in [None] + NTH:
        for z in sizes:
            r = {"tilt": cname(c) if c else "none", "z": z, "name": _ezname(z)}
            for sp, (T, S) in SP.items():
                m = cand_mult(T, c, H1T) if c else None
                r[sp] = ev25(T, S, m, z)
                r[sp]["slot"] = slot25(T, S, m, z, PICK_FZ, n=n_final)["life_pm"]
            rows.append(r)
            print(f"{r['tilt']:28s} {r['name']:18s} " + " | ".join(
                f"{sp} 2w {r[sp]['p10']:4.1f}/{r[sp]['f10']:4.1f} d{r[sp]['dec10']:4.1f} slow {r[sp]['slow_pass']} med {r[sp]['pass_med']} slot ${r[sp]['slot']}"
                for sp in SP), flush=True)
    # placebo of the eval effect for the main tilt at the pick's size and at f0.5 push s5
    pl = {}
    rng = np.random.default_rng(3)
    for c in (NTH[0], NTH[2]):
        for z in (PICK_EZ, {"mode": "frac", "f": 0.5, "cap": 600.0, "push": (5, 1.0)}):
            key = f"{cname(c)} | {_ezname(z)}"
            acc = {sp: [] for sp in SP}
            for k in range(n_pl):
                for sp, (T, S) in SP.items():
                    m = rng.permutation(cand_mult(T, c, H1T))
                    e = ev25(T, S, m, z)
                    acc[sp].append((e["p10"], e["f10"], slot25(T, S, m, z, PICK_FZ, n=200)["life_pm"] if k < 15 else np.nan))
            real = {sp: next(r for r in rows if r["tilt"] == cname(c) and r["z"] == z)[sp] for sp in SP}
            pl[key] = {}
            for sp in SP:
                a = np.array(acc[sp], float)
                pl[key][sp] = {"p10_mean": round(float(a[:, 0].mean()), 1), "f10_mean": round(float(a[:, 1].mean()), 1),
                               "slot_mean": round(float(np.nanmean(a[:, 2]))),
                               "share_p10_ge_real": round(float((a[:, 0] >= real[sp]["p10"]).mean()), 3),
                               "share_f10_le_real": round(float((a[:, 1] <= real[sp]["f10"]).mean()), 3),
                               "share_margin_ge_real": round(float(((a[:, 0] - a[:, 1]) >= real[sp]["p10"] - real[sp]["f10"]).mean()), 3),
                               "real": [real[sp]["p10"], real[sp]["f10"], real[sp]["slot"]]}
            print("placebo", key, json.dumps(pl[key]), flush=True)
    # per-unit-risk view, per year, trades a week
    rv = {}
    for c in NTH:
        rv[cname(c)] = {sp: rview(T, S, cand_mult(T, c, H1T)) for sp, (T, S) in SP.items()}
        TA = SP["R"][0] + SP["H1"][0] + SP["H2"][0]
        rv[cname(c)]["years"] = per_year(TA, cand_mult(TA, c, H1T))
    out = {"built": time.strftime("%Y-%m-%d %H:%M"), "rows": rows, "placebo": pl, "rview": rv,
           "base_rview": {sp: rview(T, S) for sp, (T, S) in SP.items()}}
    dump(out, os.path.join(OUT_S, "ab_blitz_nth.json"))
    print(f"done {time.time() - t0:.0f}s", flush=True)
    return out


def nth_m(T, up, dn):
    return np.array([nth_mult(t["f"].get("nth", np.nan), up, dn) for t in T])


def cmd_blitz_pick(n_final=1000, n_pl=40, seeds=8):
    """the later-break size on the 25K: neighbours (up x dn x room share x push), the shuffled-size placebo, random
    directions with the same sizes, per-year evals, the final numbers of the pick and of today's pick."""
    t0 = time.time()
    N, K, BS = blitz_libs()
    TT, SP = _prep_blitz()
    out = {"built": time.strftime("%Y-%m-%d %H:%M"), "grid": []}
    base = {sp: {"ev": ev25(T, S, None, PICK_EZ), "slot": slot25(T, S, None, PICK_EZ, PICK_FZ, n=n_final)} for sp, (T, S) in SP.items()}
    out["today"] = base
    print("today's pick", {sp: (b["ev"]["p10"], b["ev"]["f10"], b["slot"]["life_pm"]) for sp, b in base.items()}, flush=True)
    # 1. neighbours
    for up, dn, f, ps in itertools.product((1.25, 1.5, 1.75, 2.0, 2.5), (0.4, 0.5, 0.6, 0.75), (0.4, 0.5, 0.6), (4, 5, 6)):
        z = {"mode": "frac", "f": f, "cap": 600.0, "push": (ps, 1.0)}
        r = {"up": up, "dn": dn, "z": z}
        for sp, (T, S) in SP.items():
            m = nth_m(T, up, dn)
            r[sp] = ev25(T, S, m, z)
            r[sp]["slot"] = slot25(T, S, m, z, PICK_FZ, n=300)["life_pm"]
        b = {sp: (base[sp]["ev"], base[sp]["slot"]["life_pm"]) for sp in SP}
        r["beats_all"] = all(r[sp]["p10"] >= b[sp][0]["p10"] and r[sp]["f10"] <= b[sp][0]["f10"] and r[sp]["slot"] >= b[sp][1] for sp in SP)
        out["grid"].append(r)
    nb = sum(r["beats_all"] for r in out["grid"])
    print(f"neighbour grid {len(out['grid'])}: {nb} beat today's pick on 2-week pass, fail and slot $ in all three ({time.time() - t0:.0f}s)", flush=True)
    # H1 pick inside the grid: highest H1 slot $ with H1 dec10 >= 70 and slow_pass <= 12.5
    ok = [r for r in out["grid"] if r["H1"]["dec10"] >= 70.0 and (r["H1"]["slow_pass"] or 0) <= 12.5]
    ok.sort(key=lambda r: (-r["H1"]["slot"], -(r["H1"]["p10"] - r["H1"]["f10"])))
    out["h1_pick"] = ok[0] if ok else None
    print("H1 pick", json.dumps(_j(ok[0]))[:600] if ok else None, flush=True)
    cand = [(ok[0]["up"], ok[0]["dn"], ok[0]["z"])] if ok else []
    cand += [(1.5, 0.5, {"mode": "frac", "f": 0.5, "cap": 600.0, "push": (5, 1.0)}), (2.0, 0.5, {"mode": "frac", "f": 0.5, "cap": 600.0, "push": (5, 1.0)})]
    out["final"] = []
    rng = np.random.default_rng(31)
    for up, dn, z in cand:
        row = {"up": up, "dn": dn, "z": z, "name": f"later break x{up} / first x{dn}, {_ezname(z)}"}
        for sp, (T, S) in SP.items():
            m = nth_m(T, up, dn)
            L = slot25(T, S, m, z, PICK_FZ, n=n_final)
            row[sp] = {"ev": ev25(T, S, m, z), "slot": L, "r500": rview(T, S, m)}
            # shuffled sizes (same multiset, random trades)
            pl = []
            for k in range(n_pl):
                mm = rng.permutation(m)
                e = ev25(T, S, mm, z)
                pl.append((e["p10"], e["f10"], slot25(T, S, mm, z, PICK_FZ, n=200)["life_pm"] if k < 20 else np.nan))
            a = np.array(pl, float)
            e0 = row[sp]["ev"]
            row[sp]["placebo_shuffle"] = {"p10": round(float(a[:, 0].mean()), 1), "f10": round(float(a[:, 1].mean()), 1),
                                          "slot": round(float(np.nanmean(a[:, 2]))),
                                          "share_margin_ge": round(float(((a[:, 0] - a[:, 1]) >= e0["p10"] - e0["f10"]).mean()), 3),
                                          "share_slot_ge": round(float((a[:20, 2] >= L["life_pm"]).mean()), 3)}
        # random directions on the same signal bars (8 seeds), sizes by the real signal's break count
        for sp, tf in K.SPANS:
            acc = []
            for sd in range(seeds):
                TP = K.trades({}, "lit+atlas", placebo=sd)
                Tp, S = K.span(TP, sp, tf)
                B = N.bars(tf)
                mm = np.array([nth_mult(nth_of_entry(B, t["entry_t"]), up, dn) for t in Tp])
                e = ev25(Tp, S, mm, z)
                acc.append((e["p10"], e["f10"], slot25(Tp, S, mm, z, PICK_FZ, n=300)["life_pm"]))
            a = np.array(acc, float)
            row[sp]["random_dir"] = {"p10": round(float(a[:, 0].mean()), 1), "f10": round(float(a[:, 1].mean()), 1), "slot": round(float(a[:, 2].mean()))}
        # per year (2021-25 by year, 5m) eval of the pick vs today's pick
        T5, S5 = SP["R"]
        yr = {}
        for y in ("2022", "2023", "2024", "2025"):
            Ty = [t for t in T5 if t["day"][:4] == y]
            Sy = [d for d in S5 if d[:4] == y]
            e1 = ev25(Ty, Sy, nth_m(Ty, up, dn), z)
            e0 = ev25(Ty, Sy, None, PICK_EZ)
            yr[y] = {"pick": [e1["p10"], e1["f10"]], "today": [e0["p10"], e0["f10"]]}
        row["years"] = yr
        out["final"].append(row)
        print(row["name"], flush=True)
        for sp in SP:
            x = row[sp]
            print(f"   {sp} 2w {x['ev']['p10']}/{x['ev']['f10']} dec {x['ev']['dec10']} p15/f15 {x['ev']['p15']}/{x['ev']['f15']} med {x['ev']['pass_med']} "
                  f"slow {x['ev']['slow_pass']} slot ${x['slot']['life_pm']} (lose {x['slot']['life_lose']}%, funded {x['slot']['funded_per_6m']}/6m, "
                  f"evals {x['slot']['evals_per_6m']}/6m) | shuffled {x['placebo_shuffle']} | random dir {x['random_dir']} | "
                  f"$500 view R {x['r500']['r_per_risk']:+.3f} ${x['r500']['per_month']}/mo PF {x['r500']['pf']}", flush=True)
        print("   years", yr, flush=True)
    # today's pick under random directions too (the reference for the random-direction lines)
    rd = {}
    for sp, tf in K.SPANS:
        acc = []
        for sd in range(seeds):
            TP = K.trades({}, "lit+atlas", placebo=sd)
            Tp, S = K.span(TP, sp, tf)
            e = ev25(Tp, S, None, PICK_EZ)
            acc.append((e["p10"], e["f10"], slot25(Tp, S, None, PICK_EZ, PICK_FZ, n=300)["life_pm"]))
        a = np.array(acc, float)
        rd[sp] = {"p10": round(float(a[:, 0].mean()), 1), "f10": round(float(a[:, 1].mean()), 1), "slot": round(float(a[:, 2].mean()))}
    out["today_random_dir"] = rd
    print("today's pick, random directions", rd, flush=True)
    dump(out, os.path.join(OUT_S, "ab_blitz_pick.json"))
    print(f"done {time.time() - t0:.0f}s", flush=True)
    return out


PICK_V2 = {"up": 1.75, "dn": 0.5, "z": {"mode": "frac", "f": 0.5, "cap": 600.0, "push": (4, 1.0)}}       # cmd_blitz_pick's H1 pick
ALT_V2 = {"up": 1.5, "dn": 0.5, "z": {"mode": "frac", "f": 0.5, "cap": 600.0, "push": (5, 1.0)}}


def cmd_blitz_final(n=1000):
    """the numbers of the later-break pick for blitz_25k_pick_v2.json: the size in the EVAL only (funded unchanged: 10% /
    $150 / +$400 day stop), whole slots on the same Monte Carlo paths as today's pick, funded $, the $500 view by year."""
    t0 = time.time()
    N, K, BS = blitz_libs()
    TT, SP = _prep_blitz()
    out = {"built": time.strftime("%Y-%m-%d %H:%M"), "today": {}, "pick": {}, "alt": {}}
    for key, P in (("today", None), ("pick", PICK_V2), ("alt", ALT_V2)):
        for sp, (T, S) in SP.items():
            if P:
                m = nth_m(T, P["up"], P["dn"])
                Te, z = with_mult(T, m), P["z"]
            else:
                m, Te, z = None, T, PICK_EZ
            e = BS.eval_score(Te, S, z, paths=True)
            L = BS.life_hybrid(Te, T, S, z, PICK_FZ, n=n)
            F = BS.funded_score(T, S, PICK_FZ)
            rv = rview(T, S, m)
            qs = []
            if P:                                     # the risk the eval actually takes (a 20-session eval from every session)
                by = BS._by(Te)
                for i in range(0, len(S), 3):
                    k = []
                    BS.run_eval(S[i:i + 20], by, z, keep=k, stuck=BS._stuck(Te))
                    qs += [x["qty"] * x["risk_pm"] for x in k]
            else:
                by = BS._by(T)
                for i in range(0, len(S), 3):
                    k = []
                    BS.run_eval(S[i:i + 20], by, z, keep=k, stuck=BS._stuck(T))
                    qs += [x["qty"] * x["risk_pm"] for x in k]
            out[key][sp] = {"ev": e, "slot": L, "funded": F, "r500": rv,
                            "eval_risk_usd": {"median": round(float(np.median(qs))), "p90": round(float(np.percentile(qs, 90))), "max": round(float(max(qs)))} if qs else None}
            print(key, sp, {k: e.get(k) for k in EV_KEYS + ("b2b",)}, "slot", L, "funded", F, "risk", out[key][sp]["eval_risk_usd"], flush=True)
        TA = SP["R"][0] + SP["H1"][0] + SP["H2"][0]
        if P:
            out[key]["years_r"] = per_year(TA, nth_m(TA, P["up"], P["dn"]))
    # first / later split of the trades (what the size acts on)
    sp_ = {}
    for sp, (T, S) in SP.items():
        R = np.array([t["pnl_pm"] / t["risk_pm"] for t in T])
        nth = np.array([t["f"].get("nth", np.nan) for t in T])
        days = collections.Counter(t["day"] for t in T)
        sp_[sp] = {"first_n": int((nth < 2).sum()), "first_avg_r": round(float(R[nth < 2].mean()), 3), "later_n": int((nth >= 2).sum()),
                   "later_avg_r": round(float(R[nth >= 2].mean()), 3), "days_traded": len(days),
                   "days_with_a_later_break": len({t["day"] for t in T if t["f"].get("nth", 0) >= 2})}
    out["split"] = sp_
    print("split", sp_, flush=True)
    dump(out, os.path.join(OUT_S, "ab_blitz_final.json"))
    print(f"done {time.time() - t0:.0f}s", flush=True)
    return out


# the adopt-candidate: today's 25K eval size (40% of the room, the full room from session 5, <= $600) x 0.5 on the day's first
# band break per side, x 1.75 on a later same-side break, never more than the room; funded 25K unchanged (cmd_blitz_safe plateau:
# 54 of 54 room-capped sizes beat today's pick in all three spans; this one = today's f / push with only the multiplier added)
PICK_SAFE = {"up": 1.75, "dn": 0.5, "z": {"mode": "frac", "f": 0.4, "cap": 600.0, "push": (5, 1.0), "fmax": 1.0},
             "fz": {"mode": "frac", "f": 0.1, "cap": 150.0, "day_tp": 400.0}, "stage": "eval"}


def cmd_blitz_final_safe(n=1000, n_pl=40, seeds=8):
    """the numbers of the safe later-break pick (never more than the room; eval AND funded) for blitz_25k_pick_v2.json:
    eval paths, whole slots (same Monte Carlo paths as today's pick), funded $, risk taken, shuffled sizes, random
    directions, per-year evals, extra slippage and a late entry."""
    t0 = time.time()
    N, K, BS = blitz_libs()
    install_safe_qty()
    TT, SP = _prep_blitz()
    P = PICK_SAFE
    out = {"built": time.strftime("%Y-%m-%d %H:%M"), "pick": P, "today": {}, "pick_safe": {}}

    def risk_taken(Te, S, z):
        by, qs = BS._by(Te), []
        for i in range(0, len(S), 3):
            k = []
            BS.run_eval(S[i:i + 20], by, z, keep=k, stuck=BS._stuck(Te))
            qs += [x["qty"] * x["risk_pm"] for x in k]
        return {"median": round(float(np.median(qs))), "p90": round(float(np.percentile(qs, 90))), "max": round(float(max(qs)))} if qs else None
    for key in ("today", "pick_safe"):
        for sp, (T, S) in SP.items():
            if key == "pick_safe":
                m = nth_m(T, P["up"], P["dn"])
                Te, z, fz = with_mult(T, m), P["z"], P["fz"]
            else:
                m, Te, z, fz = None, T, PICK_EZ, PICK_FZ
            Tf = Te if P.get("stage") == "both" else T
            e = BS.eval_score(Te, S, z, paths=True)
            L = BS.life_hybrid(Te, Tf, S, z, fz, n=n)
            F = BS.funded_score(Tf, S, fz)
            out[key][sp] = {"ev": e, "slot": L, "funded": F, "r500": rview(T, S, m), "eval_risk_usd": risk_taken(Te, S, z)}
            print(key, sp, {k: e.get(k) for k in EV_KEYS + ("b2b",)}, "slot", L, "funded", F, "risk", out[key][sp]["eval_risk_usd"], flush=True)
    rng = np.random.default_rng(41)
    for sp, (T, S) in SP.items():
        m = nth_m(T, P["up"], P["dn"])
        e0, L0 = out["pick_safe"][sp]["ev"], out["pick_safe"][sp]["slot"]["life_pm"]
        pl = []
        for k in range(n_pl):
            mm = rng.permutation(m)
            Tm = with_mult(T, mm)
            e = ev25(Tm, S, None, P["z"])
            pl.append((e["p10"], e["f10"], BS.life_hybrid(Tm, Tm if P.get("stage") == "both" else T, S, P["z"], P["fz"], n=200)["life_pm"] if k < 20 else np.nan))
        a = np.array(pl, float)
        out["pick_safe"][sp]["placebo_shuffle"] = {"p10": round(float(a[:, 0].mean()), 1), "f10": round(float(a[:, 1].mean()), 1),
                                                   "slot": round(float(np.nanmean(a[:, 2]))),
                                                   "share_margin_ge": round(float(((a[:, 0] - a[:, 1]) >= e0["p10"] - e0["f10"]).mean()), 3),
                                                   "share_slot_ge": round(float((a[:20, 2] >= L0).mean()), 3)}
    for sp, tf in K.SPANS:
        B = N.bars(tf)
        acc, acc0 = [], []
        for sd in range(seeds):
            TP = K.trades({}, "lit+atlas", placebo=sd)
            Tp, S = K.span(TP, sp, tf)
            mm = np.array([nth_mult(nth_of_entry(B, t["entry_t"]), P["up"], P["dn"]) for t in Tp])
            Tm = with_mult(Tp, mm)
            e = ev25(Tm, S, None, P["z"])
            acc.append((e["p10"], e["f10"], BS.life_hybrid(Tm, Tm if P.get("stage") == "both" else Tp, S, P["z"], P["fz"], n=300)["life_pm"]))
            e = ev25(Tp, S, None, PICK_EZ)
            acc0.append((e["p10"], e["f10"], BS.life_hybrid(Tp, Tp, S, PICK_EZ, PICK_FZ, n=300)["life_pm"]))
        for nm, A_ in (("pick_safe", acc), ("today", acc0)):
            a = np.array(A_, float)
            out[nm][sp]["random_dir"] = {"p10": round(float(a[:, 0].mean()), 1), "f10": round(float(a[:, 1].mean()), 1), "slot": round(float(a[:, 2].mean()))}
    T5, S5 = SP["R"]
    yr = {}
    for y in ("2022", "2023", "2024", "2025"):
        Ty = [t for t in T5 if t["day"][:4] == y]
        Sy = [d for d in S5 if d[:4] == y]
        e1 = ev25(with_mult(Ty, nth_m(Ty, P["up"], P["dn"])), Sy, None, P["z"])
        e0 = ev25(Ty, Sy, None, PICK_EZ)
        yr[y] = {"pick": [e1["p10"], e1["f10"]], "today": [e0["p10"], e0["f10"]]}
    out["years"] = yr
    # stress: extra slippage and one bar late (both sizes on the same stressed trades)
    st = {}
    for nm, v, tk in (("+1 tick a side", {}, 1), ("+2 ticks a side", {}, 2), ("1 bar late", {"late": 1}, 0)):
        TTs = blitz_trades(v) if v else TT
        st[nm] = {}
        for sp, tf in K.SPANS:
            T, S = K.span(TTs, sp, tf)
            T = slip(T, tk)
            B = N.bars(tf)
            mm = np.array([nth_mult(nth_of_entry(B, t["entry_t"], int(v.get("late", 0))), P["up"], P["dn"]) for t in T])
            Tm = with_mult(T, mm)
            e1, e0 = ev25(Tm, S, None, P["z"]), ev25(T, S, None, PICK_EZ)
            st[nm][sp] = {"pick": [e1["p10"], e1["f10"], BS.life_hybrid(Tm, Tm if P.get("stage") == "both" else T, S, P["z"], P["fz"], n=600)["life_pm"]],
                          "today": [e0["p10"], e0["f10"], BS.life_hybrid(T, T, S, PICK_EZ, PICK_FZ, n=600)["life_pm"]]}
        print("stress", nm, st[nm], flush=True)
    out["stress"] = st
    for sp in SP:
        print(sp, "placebo", out["pick_safe"][sp]["placebo_shuffle"], "random dir", out["pick_safe"][sp]["random_dir"], "today random", out["today"][sp]["random_dir"], flush=True)
    print("years", yr, flush=True)
    dump(out, os.path.join(OUT_S, "ab_blitz_final_safe.json"))
    print(f"done {time.time() - t0:.0f}s", flush=True)
    return out


_QPATCH = {}


def install_safe_qty():
    """sizes with a per-trade multiplier that never risk more than the room: sz "fmax" caps f x mult (1.0 = the whole room
    to the floor), sz "cap_fixed" keeps the $ cap unscaled. Without those keys = tools/blitz25k_lib.qty."""
    N, K, BS = blitz_libs()
    if _QPATCH:
        return
    korig = K.qty

    def qty2(t, room, cum, bal, P, sz, _k=korig):
        mu = t.get("mult", 1.0)
        if mu != 1.0 and sz.get("mode") == "frac" and (sz.get("fmax") is not None or sz.get("cap_fixed")):
            f = float(sz["f"]) * mu
            if sz.get("fmax") is not None:
                f = min(f, float(sz["fmax"]))
            cap = float(sz["cap"]) * (1.0 if sz.get("cap_fixed") else mu)
            return K._NQTY(t, room, cum, bal, P, {**sz, "f": f, "cap": cap})
        return _k(t, room, cum, bal, P, sz)
    K.qty = qty2
    N.qty = qty2
    _QPATCH["on"] = True


def cmd_blitz_safe(n=600):
    """the later-break size with the room as the hard limit (f x mult <= 1.0) and the $600 cap fixed or scaled; the size in
    the eval only (funded unchanged) or in both stages. Picked on H1 slot $ among sizes deciding >= 70% in 2 weeks with
    <= 12.5% slow passes, never risking more than the room."""
    t0 = time.time()
    N, K, BS = blitz_libs()
    install_safe_qty()
    TT, SP = _prep_blitz()
    base = {sp: {"ev": ev25(T, S, None, PICK_EZ), "slot": BS.life_hybrid(T, T, S, PICK_EZ, PICK_FZ, n=n)["life_pm"]} for sp, (T, S) in SP.items()}
    rows = []
    for up, dn, f, ps, safe, stage in itertools.product((1.5, 1.75, 2.0), (0.5,), (0.4, 0.5, 0.6), (4, 5, 6),
                                                       ("fmax1", "fmax1+cap600", "cap600"), ("eval", "both")):
        z = {"mode": "frac", "f": f, "cap": 600.0, "push": (ps, 1.0)}
        if "fmax1" in safe:
            z["fmax"] = 1.0
        if "cap600" in safe:
            z["cap_fixed"] = True
        fz = dict(PICK_FZ)
        if stage == "both":
            fz["fmax"] = 1.0
        r = {"up": up, "dn": dn, "z": z, "safe": safe, "stage": stage}
        for sp, (T, S) in SP.items():
            Te = with_mult(T, nth_m(T, up, dn))
            r[sp] = ev25(Te, S, None, z)
            r[sp]["slot"] = BS.life_hybrid(Te, Te if stage == "both" else T, S, z, fz, n=n)["life_pm"]
        r["beats_all"] = all(r[sp]["p10"] >= base[sp]["ev"]["p10"] and r[sp]["f10"] <= base[sp]["ev"]["f10"] and r[sp]["slot"] >= base[sp]["slot"] for sp in SP)
        rows.append(r)
    ok = [r for r in rows if r["H1"]["dec10"] >= 70.0 and (r["H1"]["slow_pass"] or 0) <= 12.5]
    ok.sort(key=lambda r: -r["H1"]["slot"])
    out = {"built": time.strftime("%Y-%m-%d %H:%M"), "base": base, "rows": rows, "n_beats_all": sum(r["beats_all"] for r in rows),
           "h1_top": ok[:8]}
    print("today", {sp: (b["ev"]["p10"], b["ev"]["f10"], b["slot"]) for sp, b in base.items()}, flush=True)
    print(f"{len(rows)} safe later-break sizes, {out['n_beats_all']} beat today's pick on 2-week pass, fail and slot $ in all three", flush=True)
    for r in ok[:8]:
        print(f"x{r['up']}/{r['dn']} {_ezname(r['z'])} {r['safe']} {r['stage']} beats_all {r['beats_all']} | " + " | ".join(
            f"{sp} 2w {r[sp]['p10']}/{r[sp]['f10']} dec {r[sp]['dec10']} slow {r[sp]['slow_pass']} med {r[sp]['pass_med']} slot ${r[sp]['slot']}" for sp in SP), flush=True)
    for safe in ("fmax1", "fmax1+cap600", "cap600"):
        for stage in ("eval", "both"):
            sub = [r for r in rows if r["safe"] == safe and r["stage"] == stage]
            print(f"   {safe:13s} {stage:5s}: {sum(r['beats_all'] for r in sub)}/{len(sub)} beat today in all three; mean slot " +
                  " / ".join(f"${np.mean([r[sp]['slot'] for r in sub]):.0f}" for sp in SP), flush=True)
    dump(out, os.path.join(OUT_S, "ab_blitz_safe.json"))
    print(f"done {time.time() - t0:.0f}s", flush=True)
    return out


def nth_of_entry(B, entry_t, late=0):
    """the day's count of same-side band breaks at the checks up to this trade's signal bar (scalp_na_lib.signals "nth"),
    from the entry bar time (signal = the bar before the entry, `late` bars more)."""
    N, K, BS = blitz_libs()
    F = N.signals(B, 1.0, 30, (630, 930), 1.5)
    key = ("nthpos", B["tf"], len(B["t"]))
    if key not in _B:
        _B[key] = {int(i): float(F["nth"][q]) for q, i in enumerate(F["sig"])}
    i = int(np.searchsorted(B["t"], entry_t)) - 1 - late
    return _B[key].get(i, np.nan)


def nth_mult(nth, up, dn):
    return 1.0 if nth != nth else (up if nth >= 2 else dn)


def cmd_blitz50(n=1000):
    """BLITZ as the add-on on LIT's funded 50K (scalp-na-mffu.md: 20% of the room, <= $450, only once funded, while LIT is
    flat): the later-break size there (tools/scalp_na_combo.lit_money, BLITZ size x mult)."""
    t0 = time.time()
    N, K, BS = blitz_libs()
    from tools import scalp_na_combo as C
    import div_stack as DS
    orig_units, orig_q = C.blitz_units, DS.na_q
    state = {"tilt": None}

    def bu(*a, **kw):
        U = orig_units(*a, **kw)
        if state["tilt"]:
            up, dn = state["tilt"]
            for u in U:
                B = N.bars(1 if u["day"] >= "2026-01-01" else 5)
                u["mult"] = nth_mult(nth_of_entry(B, u["entry_t"]), up, dn)
        return U

    def nq(t, room, nc, maxq, dll_left=None):
        m = t.get("mult", 1.0)
        if m != 1.0:
            nc = {**nc, "f": float(nc["f"]) * m, "cap": float(nc["cap"]) * m}
        return orig_q(t, room, nc, maxq, dll_left)
    C.blitz_units, DS.na_q = bu, nq
    # lit_money copies the unit fields it needs: keep "mult" (re-wrap the per-day dicts)
    orig_lm = C.lit_money
    out = {"built": time.strftime("%Y-%m-%d %H:%M"), "rows": []}
    try:
        base = C.lit_money(None, n=n)
        out["lit_alone"] = base
        print("LIT alone", {s: base[s]["slot_pm"] for s in base}, flush=True)
        for tilt in (None, (1.5, 0.5), (1.25, 0.75), (2.0, 0.5), (1.5, 1.0)):
            state["tilt"] = tilt
            C._AU.clear()
            # lit_money builds its per-day units from blitz_units rows: patch the dict build by passing mult through
            r = _lit_money_mult(C, DS, {"f": 0.2, "cap": 450.0}, n)
            row = {"tilt": tilt, "money": r}
            out["rows"].append(row)
            print("BLITZ on LIT's funded 50K, later-break size", tilt, {s: r[s]["slot_pm"] for s in r},
                  {s: r[s]["slot_pm"] - base[s]["slot_pm"] for s in r}, flush=True)
    finally:
        C.blitz_units, DS.na_q = orig_units, orig_q
    dump(out, os.path.join(OUT_S, "ab_blitz_lit50k.json"))
    print(f"done {time.time() - t0:.0f}s", flush=True)
    return out


def _lit_money_mult(C, DS, nc, n, spans=("H1", "H2", "REF")):
    """scalp_na_combo.lit_money(nc, nc_eval=None) with the BLITZ units' "mult" kept in the per-day rows."""
    import uprisk as U
    import csv
    S, BYL = U.load()
    N = C.N
    ets = collections.defaultdict(list)
    for r in csv.DictReader(open(N.LEDGER, encoding="utf-8")):
        if r["trade_id"].startswith(("T-2026", "REF-")):
            ets[r["entry_fill_at"][:10]].append(int(dt.datetime.fromisoformat(r["entry_fill_at"][:25]).timestamp()))
    for i, x in enumerate(BYL):
        for t, e in zip(x, ets.get(S[i], [])):
            t["src"] = "lit"
            t["et"] = e
    T = C.blitz_units(lit_flat=True)
    T = C.cut_on(T, C.lit_by_day())
    T = C.yield_to(T, C.atlas_by_day())
    byn = collections.defaultdict(list)
    for t in T:
        byn[t["day"]].append({"day": t["day"], "src": "na", "risk": t["risk"], "risk_pts": t["risk"], "tgt": None, "tgt_pts": None,
                              "pts": t["pts"], "w1": t["w1"], "size_mult": 1.0, "et": t["entry_t"], "xt": t["exit_t"],
                              "dir": t["dir"], "exit": t["exit"], "mult": t.get("mult", 1.0)})
    BY = [sorted(BYL[i] + byn.get(d, []), key=lambda t: t.get("et", 0)) for i, d in enumerate(S)]
    out = {}
    for sp in spans:
        P = DS.paths(S, sp, n)
        mk_e = (lambda: DS.Eval(DS.LIT_E50, "builder50k", nc=None))
        mk_f = (lambda: DS.Funded("builder50k", DS.LIT_F50, nc=nc))
        R = DS.life(BY, P, mk_e, mk_f, 91.80, U.LEN)
        net = np.array([r["net"] for r in R]) / (U.LEN / 21.0)
        out[sp] = {"slot_pm": round(float(net.mean())), "slot_p10": round(float(np.percentile(net, 10))),
                   "slot_lose": round(100.0 * float((net < 0).mean()), 1), "funded_6m": round(float(np.mean([r["funded"] for r in R])), 2),
                   "lost_6m": round(float(np.mean([r["lost"] for r in R])), 2)}
    return out


def slip(T, ticks):
    """extra slippage: `ticks` more on the entry AND on the exit ($0.50 a tick a micro), the worst open point too."""
    if not ticks:
        return T
    x = 0.5 * ticks
    return [{**t, "pnl_pm": t["pnl_pm"] - 2 * x, "mae_pm": t["mae_pm"] - x} for t in T]


def cmd_blitzx():
    """robustness of today's rule and of the later-break size: +1 / +2 ticks a side, 1 bar late, and the 10:30 check."""
    t0 = time.time()
    N, K, BS = blitz_libs()
    out = {"built": time.strftime("%Y-%m-%d %H:%M"), "rows": []}
    z5 = {"mode": "frac", "f": 0.5, "cap": 600.0, "push": (5, 1.0)}
    K.WINDOWS["x1030"] = (570, (600, 630), 30)                # one more check at the 10:30 close (same band, same filter)
    variants = [("today", {}, 0), ("+1 tick a side", {}, 1), ("+2 ticks a side", {}, 2), ("1 bar late", {"late": 1}, 0),
                ("2 bars late", {"late": 2}, 0), ("+ the 10:30 check", {"wins": ("x1030", "rth")}, 0)]
    for nm, v, tk in variants:
        TT = blitz_trades(v)
        SP = spans_of(TT)
        H1T = SP["H1"][0]
        for tilt in (None, ("nth", 1, "terc", 1.5, 0.5), ("nth", 1, "terc", 2.0, 0.5)):
            for z in ((PICK_EZ, z5) if tilt else (PICK_EZ,)):
                r = {"variant": nm, "tilt": cname(tilt) if tilt else "none", "size": _ezname(z)}
                for sp, (T, S) in SP.items():
                    Ts = slip(T, tk)
                    m = None
                    if tilt:
                        late = int(v.get("late", 0))
                        B = N.bars(1 if sp != "R" else 5)
                        m = np.array([nth_mult(nth_of_entry(B, t["entry_t"], late), tilt[3], tilt[4]) for t in Ts])
                    r[sp] = {"r500": rview(Ts, S, m), "ev": ev25(Ts, S, m, z), "slot": slot25(Ts, S, m, z, PICK_FZ, n=600)["life_pm"]}
                out["rows"].append(r)
                print(f"{nm:18s} {r['tilt']:26s} {r['size']:16s} " + " | ".join(
                    f"{sp} n{r[sp]['r500']['n']} R {r[sp]['r500']['r_per_risk']:+.3f} ${r[sp]['r500']['per_month']}/mo PF {r[sp]['r500']['pf']} "
                    f"2w {r[sp]['ev']['p10']}/{r[sp]['ev']['f10']} slot ${r[sp]['slot']}" for sp in SP), flush=True)
    dump(out, os.path.join(OUT_S, "ab_blitz_x.json"))
    print(f"done {time.time() - t0:.0f}s", flush=True)
    return out


# ================================================================================================ ATLAS
_UM = {}            # name -> {(src, entry_t): size multiplier} for the patched account-B sizer


def atlas_libs():
    from tools import atlas_v2 as V2
    from tools import atlas as A
    from tools import second_mix as M
    from engine import account_b as EAB
    U = V2.install()
    if "LITC" not in U:                       # LIT copied onto account B as a member (account-B size, not LIT's)
        U["LITC"] = [{**u, "src": "LITC", "pt": np.zeros(0, np.int64), "po": np.zeros(0), "pw": np.zeros(0)} for u in U["LIT"]]
    if not getattr(A, "_ab_patched", False):
        orig = A.q_variant

        def qv(t, st, V, _orig=orig):
            q = _orig(t, st, V)
            k = V.get("um")
            if q <= 0 or not k:
                return q
            m = _UM[k].get((t["src"], t["entry_t"]), 1.0)
            if m == 1.0:
                return q
            q2 = max(1, int(q * m + 1e-9)) if m > 0 else 0
            S = A.spec()
            q2 = min(q2, int(S["rules"]["max_micros"]))
            if q2 > 0:
                q2 = int(EAB.dll_guard({"qty": q2, "reasons": []}, float(t["risk"]), S["rules"], st)["qty"])
            return q2
        A.q_variant = qv
        A._ab_patched = True
    return V2, A, M, EAB


def a_score(V):
    V2, A, M, EAB = atlas_libs()
    return V2.score(V)


def a_line(o, s):
    x = o[s]
    return (f"{s} 2w {x['p10']:5.1f}/{x['dead10']:4.1f} med {x['pass_med']} ${x['mp_net_less_fees']:+,} (path {x['net']:+,} PF {x['pf']}) "
            f"tpw {x['sig_tpw']} wk2 {x['sig_wk2']}")


def a_compact(o):
    keys = ("p10", "f10", "s10", "dead10", "dec10", "p15", "f15", "pass_med", "slow_pass", "mp_net_less_fees", "mp_per_eval", "mp_passes",
            "net", "per_month", "pf", "dd", "tpw", "sig_tpw", "sig_wk2", "n", "fund_paid_3m", "by_src")
    return {s: {k: o[s].get(k) for k in keys} for s in o}


def _R(u):
    return float(u["pts"]) / float(u["risk"]) if u["risk"] else 0.0


def um_dynamic(names, n, rule, up, dn):
    """member weight from the member's OWN last n research trades closed before this entry (known at the entry):
    rule "sign": mean R of the last n > 0 -> up else dn; "vs": above the member's own expanding mean R -> up else dn."""
    V2, A, M, EAB = atlas_libs()
    U = M.units()
    out = {}
    for nm in names:
        X = sorted(U[nm], key=lambda u: u["exit_t"])
        ex = np.array([u["exit_t"] for u in X])
        R = np.array([_R(u) for u in X])
        for u in U[nm]:
            k = int(np.searchsorted(ex, u["entry_t"], side="right"))
            if k < n:
                continue
            last = R[k - n:k].mean()
            ref = 0.0 if rule == "sign" else R[:k].mean()
            out[(nm, u["entry_t"])] = up if last > ref else dn
    return out


def um_agree(names, up, dn, others=None):
    """another ATLAS member already entered the same day on the same side -> up; on the other side -> dn."""
    V2, A, M, EAB = atlas_libs()
    U = M.units()
    others = others or names
    by = collections.defaultdict(list)
    for nm in others:
        for u in U[nm]:
            by[u["day"]].append((u["entry_t"], u["dir"], nm))
    out = {}
    for nm in names:
        for u in U[nm]:
            prev = [d for e, d, o in by[u["day"]] if e < u["entry_t"] and o != nm]
            if not prev:
                continue
            if any(d == u["dir"] for d in prev):
                out[(nm, u["entry_t"])] = up
            elif any(d != u["dir"] for d in prev):
                out[(nm, u["entry_t"])] = dn
    return out


def um_second(V, after_loss, after_win):
    """the day's 2nd ATLAS candidate (account units after the no-hedge rules), entered after the 1st closed: x after_loss /
    x after_win by the 1st's result (known at the 2nd's entry)."""
    V2, A, M, EAB = atlas_libs()
    out = {}
    by = collections.defaultdict(list)
    for u in A.account_units(V):
        by[u["day"]].append(u)
    for d, L in by.items():
        L = sorted(L, key=lambda u: u["entry_t"])
        f = L[0]
        for u in L[1:]:
            if u["entry_t"] >= f["exit_t"]:
                out[(u["src"], u["entry_t"])] = after_loss if f["pts"] < 0 else after_win
    return out


def a_placebo(V, um, n=40, seed=17):
    """the same multipliers shuffled over the same units (random members / days get them) -> verdict pass share and the
    2026 H1 / H2 money distribution."""
    V2, A, M, EAB = atlas_libs()
    rng = np.random.default_rng(seed)
    keys = list(um.keys())
    vals = np.array([um[k] for k in keys])
    allk = [(u["src"], u["entry_t"]) for u in A.account_units(V)]
    res = []
    base = a_score(V)
    for i in range(n):
        pick = rng.choice(len(allk), size=min(len(keys), len(allk)), replace=False)
        nm = f"_pl{i}"
        _UM[nm] = {allk[j]: float(v) for j, v in zip(pick, rng.permutation(vals))}
        o = a_score({**V, "um": nm})
        v = V2.verdict(o, base)
        res.append((v["pass"], v["both"], o["H1"]["mp_net_less_fees"], o["H2"]["mp_net_less_fees"]))
        del _UM[nm]
    a = np.array(res, float)
    return {"pass_share": round(float(a[:, 0].mean()), 3), "both_share": round(float(a[:, 1].mean()), 3),
            "h1_mean": round(float(a[:, 2].mean())), "h2_mean": round(float(a[:, 3].mean()))}


def cmd_atlas():
    t0 = time.time()
    V2, A, M, EAB = atlas_libs()
    base_V = V2.V_()
    base = a_score(base_V)
    out = {"built": time.strftime("%Y-%m-%d %H:%M"), "base": a_compact(base), "rows": []}
    print("ATLAS today:")
    for s in base:
        print("  ", a_line(base, s), flush=True)
    rows = []

    def run(fam, name, V, um=None):
        if um is not None:
            _UM[name] = um
            V = {**V, "um": name}
        o = a_score(V)
        v = V2.verdict(o, base)
        r = {"fam": fam, "name": name, "verdict": v, "o": a_compact(o), "n_um": len(um) if um is not None else None}
        rows.append(r)
        print(f"{fam:8s} {name:46s} {'PASS' if v['pass'] else ('both' if v['both'] else '    ')} ref {v['ref']} | " +
              " | ".join(a_line(o, s) for s in ("H1", "H2", "2025", "2021-24")), flush=True)
        return r
    MEM = ["EMA", "MD", "SR"]
    # A1 dynamic member weights (the member's own recent trades)
    for n, rule, (up, dn) in itertools.product((5, 10, 20), ("sign", "vs"), ((1.25, 0.75), (1.0, 0.5), (1.5, 0.5), (1.25, 1.0))):
        run("dyn", f"last {n} {rule} x{up}/{dn}", base_V, um_dynamic(MEM, n, rule, up, dn))
    # A2 member agreement
    for up, dn in ((1.25, 0.75), (1.5, 0.5), (1.0, 0.5), (1.25, 1.0), (0.75, 1.25), (0.5, 1.0)):
        run("agree", f"agree x{up} / against x{dn}", base_V, um_agree(MEM, up, dn))
    # A3 2nd trade of the day by the 1st's result
    for al, aw in ((0.5, 1.0), (1.0, 0.5), (0.5, 1.5), (1.5, 0.5), (0.75, 1.25), (0.0, 1.0), (1.0, 0.0)):
        run("second", f"2nd after loss x{al} / after win x{aw}", base_V, um_second(base_V, al, aw))
    # A4 LIT copied in as a member (account-B size), with / without the two hunts at half size (atlas-v2.md lead)
    for w in (0.25, 0.5, 0.75, 1.0):
        run("litc", f"+ LIT copy x{w}", V2.V_(members=MEM + ["LITC"], w={"LITC": w}))
        run("litc", f"+ LIT copy x{w} + hunts x0.5", V2.V_(members=MEM + ["LITC", "SHA", "SHT"], w={"LITC": w, "SHA": 0.5, "SHT": 0.5}))
    run("litc", "+ LIT copy x1.0 first in order", V2.V_(members=MEM + ["LITC"], w={"LITC": 1.0}, order=["LITC"] + MEM))
    run("ref", "hunts x0.5 (atlas-v2 lead)", V2.V_(members=MEM + ["SHA", "SHT"], w={"SHA": 0.5, "SHT": 0.5}))
    out["rows"] = rows
    out["n"] = len(rows)
    out["n_pass"] = sum(r["verdict"]["pass"] for r in rows)
    print(f"{len(rows)} ATLAS variants, {out['n_pass']} pass the v2 test ({time.time() - t0:.0f}s)", flush=True)
    # placebos for every pass in the size families
    for r in rows:
        if r["verdict"]["pass"] and r["fam"] in ("dyn", "agree", "second"):
            V = {**base_V, "um": r["name"]}
            r["placebo"] = a_placebo(base_V, _UM[r["name"]])
            print("   placebo", r["name"], r["placebo"], flush=True)
    dump(out, os.path.join(OUT_A, "ab_atlas.json"))
    print(f"done {time.time() - t0:.0f}s", flush=True)
    return out


# ================================================================================================ ATLAS: a 4th member from a family that passed alone
def nad_units(cid="na_vm125_1000_n99_fixed"):
    """the noise-area intraday momentum held for the day (Zarattini 2024; diversifier-search.md joint pick, positive as futures
    trading in 2026 H1 / H2 / 2025 / 2021-24): tools/div_search trades -> account-B units (no bar path: a unit that an
    opposite LIT entry would cut is dropped, as the ASIA member; target for the need size = 2R, as the hunts)."""
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import div_search as DSR
    G = dict(DSR.na_grid())
    B = DSR.D()
    out = []
    for w in DSR.run(G[cid]):
        k = w["k"]
        day = B.days[k]
        risk = float(w["risk"])
        if risk <= 0:
            continue
        et = int(B.t[k, w["j"] + 1])
        xt = int(B.t[k, w["exit_j"]]) + (0 if w["exit"] == "EOD" else 300)
        out.append({"day": day, "entry_t": et, "exit_t": xt, "dir": int(w["dir"]), "exit": str(w["exit"]), "risk": risk,
                    "tgt": 2.0 * risk, "pts": float(w["pts"]), "w1": float(max(-(risk + 0.25), min(0.0, w["mae"], w["pts"]))),
                    "src": "NAD", "pt": np.zeros(0, np.int64), "po": np.zeros(0), "pw": np.zeros(0)})
    return out


def cmd_atlas_na():
    t0 = time.time()
    V2, A, M, EAB = atlas_libs()
    U = M.units()
    if "NAD" not in U:
        U["NAD"] = nad_units()
    R = np.array([_R(u) for u in U["NAD"]])
    print("NAD units", len(U["NAD"]), "avg R", round(float(R.mean()), 3), flush=True)
    base = a_score(V2.V_())
    MEM = ["EMA", "MD", "SR"]
    rows = []
    for w in (0.25, 0.5, 0.75, 1.0):
        for nm, V in ((f"+ NA day-hold x{w}", V2.V_(members=MEM + ["NAD"], w={"NAD": w})),
                      (f"+ NA day-hold x{w}, the members first", V2.V_(members=MEM + ["NAD"], w={"NAD": w}, order=MEM + ["NAD"])),
                      (f"+ NA day-hold x{w} + hunts x0.5", V2.V_(members=MEM + ["NAD", "SHA", "SHT"], w={"NAD": w, "SHA": 0.5, "SHT": 0.5}))):
            o = a_score(V)
            v = V2.verdict(o, base)
            rows.append({"name": nm, "verdict": v, "o": a_compact(o)})
            print(f"{nm:44s} {'PASS' if v['pass'] else ('both' if v['both'] else '    ')} ref {v['ref']} | " +
                  " | ".join(a_line(o, s) for s in ("H1", "H2", "2025", "2021-24")), flush=True)
    out = {"built": time.strftime("%Y-%m-%d %H:%M"), "base": a_compact(base), "rows": rows, "nad_n": len(U["NAD"]),
           "nad_avg_r": round(float(R.mean()), 3)}
    dump(out, os.path.join(OUT_A, "ab_atlas_na.json"))
    print(f"done {time.time() - t0:.0f}s", flush=True)
    return out


# ================================================================================================ ATLAS: setup geometry -> size
def _stored(name):
    f = {"EMA": "ema_best.json", "MD": "md_best.json", "SR": "sr_best.json"}[name]
    T = json.load(open(os.path.join(ROOT, "research", "second", f), encoding="utf-8"))["trades"]
    return {int(t["entry_t"]): t for t in T}


def geo_sr():
    """S/R NY reclaim: the levels (tools/second_sr.levels "all_or": PDH/PDL, overnight, Asia box, London box, opening range,
    prior week) between the stop (the sweep extreme) and the entry, known before the entry: how many, and whether a
    prior-day / prior-week level is among them."""
    import pandas as pd
    from tools import retail_standalone as RS
    from tools import second_sr as SR
    df = pd.read_csv(os.path.join(ROOT, "data", "NQ_5m.csv")).drop_duplicates("time").sort_values("time").reset_index(drop=True)
    RS.load_frame(df, live_cut=False)
    SR.D.clear()
    SR._OC.clear()
    d = SR.data()
    kinds = ("pd", "on", "asia", "lon", "or", "pw")
    LV = SR.levels(d, kinds)
    sid_of = {d["days"][s]: (s, a) for s, a, b in d["sess"]}
    out = {}
    for et, t in _stored("SR").items():
        x = sid_of.get(t["day"])
        if x is None:
            continue
        s, a = x
        # the entry's minute from the session open (rel) -> only levels known by then
        k = int(np.searchsorted(d["t"], et)) if "t" in d else None
        rel_e = d["rel"][k] if k is not None and k < len(d["rel"]) else 1e9
        lo, hi = sorted((float(t["stop"]), float(t["entry"])))
        inz = [(p, nm) for p, nm, kr in LV.get(s, []) if kr <= rel_e and lo < p < hi]
        out[et] = {"n_lv": len(inz), "htf": 1.0 if any(nm[:2] in ("pd", "pw") for p, nm in inz) else 0.0,
                   "stop_pts": abs(float(t["entry"]) - float(t["stop"]))}
    SR.D.clear(); SR._OC.clear(); RS.D.clear()
    return out


def geo_ema():
    """EMA London pullback: the sweep depth = (the swept 5m swing low - the pullback low) / ATR(14, 5m) and the entry's
    distance from the 5m EMA 50 in ATR (longs; shorts mirrored), from closed bars before the entry."""
    N, K, BS = blitz_libs()
    B = N.bars(5)
    hp, hk, lp, lk = K._pivots(B["h"], B["l"], 2)
    out = {}
    for et, t in _stored("EMA").items():
        j = int(np.searchsorted(B["t"], et))            # the entry bar
        if j <= 30 or j >= len(B["t"]):
            continue
        dr = int(t["dir"])
        ext = float(t["stop"]) + 0.25 * dr               # the pullback extreme (stop = 1 tick beyond it)
        a = B["atr"][j - 1]
        # the pullback-extreme bar: the last bar in the 40 before the entry that printed it
        lo = B["l"] if dr > 0 else -B["h"]
        tgt = ext * dr
        pb = None
        for i in range(j - 1, max(0, j - 40), -1):
            if abs(lo[i] - tgt) < 0.13:
                pb = i
                break
        depth = np.nan
        if pb is not None and pb >= 1:
            pv = lp[pb - 1] if dr > 0 else hp[pb - 1]
            if pv == pv and (pv - ext) * dr > 0:
                depth = (pv - ext) * dr / a
        out[et] = {"depth": float(depth), "ema_dist": float((float(t["entry"]) - B["ema50"][j - 1]) * dr / a)}
    return out


def um_geo(name, G, f, mode, up, dn, sign):
    V2, A, M, EAB = atlas_libs()
    U = M.units()[name]
    x = np.array([G.get(u["entry_t"], {}).get(f, np.nan) for u in U], float)
    h1 = np.array([u["day"] >= "2026-01-01" and u["day"] < "2026-07-01" for u in U])
    xs = x[h1 & (x == x)]
    if f in ("htf",):
        lo_c = hi_c = 0.5
    elif f == "n_lv":
        lo_c, hi_c = 1.5, 1.5
    elif mode == "terc":
        lo_c, hi_c = np.quantile(xs, 1 / 3), np.quantile(xs, 2 / 3)
    else:
        lo_c = hi_c = np.quantile(xs, 0.5)
    out = {}
    for u, v in zip(U, x):
        if v != v:
            continue
        top, bot = v >= hi_c, v < lo_c
        if sign < 0:
            top, bot = bot, top
        m = up if top else dn if bot else 1.0
        if m != 1.0:
            out[(name, u["entry_t"])] = m
    return out, (float(lo_c), float(hi_c))


def cmd_atlas_geo():
    t0 = time.time()
    V2, A, M, EAB = atlas_libs()
    base_V = V2.V_()
    base = a_score(base_V)
    GS, GE = geo_sr(), geo_ema()
    U = M.units()
    out = {"built": time.strftime("%Y-%m-%d %H:%M"), "base": a_compact(base), "rows": [], "facts": {}}
    # what the facts say (avg R by bucket, research trades, every span)
    for nm, G, fs in (("SR", GS, ("n_lv", "htf", "stop_pts")), ("EMA", GE, ("depth", "ema_dist"))):
        for f in fs:
            x = np.array([G.get(u["entry_t"], {}).get(f, np.nan) for u in U[nm]], float)
            R = np.array([_R(u) for u in U[nm]])
            sp = np.array(["H1" if "2026-01-01" <= u["day"] < "2026-07-01" else "H2" if u["day"] >= "2026-07-01" else "2025" if u["day"] >= "2025-01-01" else "2021-24" for u in U[nm]])
            ok = x == x
            med = float(np.median(x[ok & (sp == "H1")])) if (ok & (sp == "H1")).any() else np.nan
            row = {"cover": round(float(ok.mean()), 3), "h1_median": med}
            for s in ("H1", "H2", "2025", "2021-24"):
                k = sp == s
                row[s] = {"hi": [int((k & ok & (x >= med)).sum()), round(float(R[k & ok & (x >= med)].mean()), 3) if (k & ok & (x >= med)).any() else None],
                          "lo": [int((k & ok & (x < med)).sum()), round(float(R[k & ok & (x < med)].mean()), 3) if (k & ok & (x < med)).any() else None]}
            out["facts"][f"{nm} {f}"] = row
            print(nm, f, json.dumps(row), flush=True)
    rows = []
    for nm, G, fs in (("SR", GS, ("n_lv", "htf")), ("EMA", GE, ("depth", "ema_dist"))):
        for f in fs:
            for sign in (1, -1):
                for mode in (("terc", "med") if f in ("depth", "ema_dist") else ("med",)):
                    for up, dn in ((1.25, 0.75), (1.5, 0.5), (1.0, 0.5), (1.25, 1.0)):
                        um, cuts = um_geo(nm, G, f, mode, up, dn, sign)
                        key = f"{nm} {f} {'high' if sign > 0 else 'low'} {mode} x{up}/{dn}"
                        _UM[key] = um
                        o = a_score({**base_V, "um": key})
                        v = V2.verdict(o, base)
                        rows.append({"name": key, "cuts": cuts, "verdict": v, "o": a_compact(o)})
                        print(f"{key:40s} {'PASS' if v['pass'] else ('both' if v['both'] else '    ')} ref {v['ref']} | " +
                              " | ".join(a_line(o, s) for s in ("H1", "H2", "2025", "2021-24")), flush=True)
    out["rows"] = rows
    out["n"], out["n_pass"] = len(rows), sum(r["verdict"]["pass"] for r in rows)
    for r in rows:
        if r["verdict"]["pass"]:
            r["placebo"] = a_placebo(base_V, _UM[r["name"]])
            print("   placebo", r["name"], r["placebo"], flush=True)
    dump(out, os.path.join(OUT_A, "ab_atlas_geo.json"))
    print(f"{len(rows)} geometry sizes, {out['n_pass']} pass; done {time.time() - t0:.0f}s", flush=True)
    return out


def cmd_pick_v2():
    """research/scalp/blitz_25k_pick_v2.json (the shape of blitz_25k_pick.json): today's rule, the later-break eval size."""
    src = json.load(open(os.path.join(OUT_S, "blitz_25k_pick.json"), encoding="utf-8"))
    F = json.load(open(os.path.join(OUT_S, "ab_blitz_final_safe.json"), encoding="utf-8"))
    sf = json.load(open(os.path.join(OUT_S, "ab_blitz_safe.json"), encoding="utf-8"))
    P = PICK_SAFE
    out = copy.deepcopy(src)
    out["name"] = "BLITZ on its own MFFU Builder 25K (account C) - v2: the later-break eval size"
    out["date"] = "2026-10-30"
    out["writeup"] = "research/writeups/atlas-blitz-edge-2026-10-30.md"
    out["verdict"] = "adopt-candidate (eval size only; owner decides; rule unchanged)"
    out["why"] = ("Same BLITZ rule and trades; only the 25K EVAL size changes: today's size (40% of the room, the full room from eval session 5, "
                  "<= $600) x 0.5 on the day's FIRST band break on a side, x 1.75 on a LATER break on the same side (a check close beyond the band "
                  "that already broke earlier today = the trend day confirmed), never more than the room. 2-week pass up and fail down in 2026 H1, "
                  "H2 and 2021-25, the whole 25K slot $ the same or better in all three; 54 of 54 room-capped neighbours do the same; shuffled sizes "
                  "and random directions do not. The gain comes from pressing later breaks with the day's profit (with the $600 cap kept fixed, "
                  "0 of 27 beat today).")
    out["engine"]["eval_25k"] = {**src["engine"]["eval_25k"], "f": P["z"]["f"], "cap_usd": P["z"]["cap"], "push_from_session": P["z"]["push"][0],
                                 "push_f": P["z"]["push"][1],
                                 "later_break": {"first_x": P["dn"], "later_x": P["up"], "f_max": P["z"]["fmax"], "cap_scales": True,
                                                 "count": "check closes (11:00 ... 15:30) beyond the band on the signal's side today, this one included; "
                                                          ">= 2 = a later break (every check counts, traded or not)"}}
    out["engine"]["funded_25k"] = src["engine"]["funded_25k"]
    out["sizing"]["eval"] = {**src["sizing"]["eval"], "f": P["z"]["f"], "cap_usd": P["z"]["cap"], "push": {"from_session": P["z"]["push"][0], "f": P["z"]["push"][1]},
                             "later_break": {"first_break_of_the_day_x": P["dn"], "later_same_side_break_x": P["up"],
                                             "risk": "min(cap_usd x m, min(f x m, 1.0) x room, 0.9 x the soft daily loss left) with m = first_x or later_x",
                                             "never_more_than_the_room": True}}
    nums = {}
    for sp, lab in (("H1", "2026 H1 (pick)"), ("H2", "2026 H2 (check)"), ("R", "2021-25 (5m)")):
        x, t = F["pick_safe"][sp], F["today"][sp]
        e, s, f, r = x["ev"], x["slot"], x["funded"], x["r500"]
        nums[lab] = {"trades_week": r["tpw"], "weeks_2plus_pct": r["wk2"], "pf_500_view": r["pf"], "net_usd_500_view": r["net"],
                     "usd_month_500_view": r["per_month"], "max_dd_500_view": r["dd"], "avg_r": r["avg_r"], "r_per_unit_risk": r["r_per_risk"],
                     "p10": e["p10"], "f10": e["f10"], "dec10": e["dec10"], "p15": e["p15"], "f15": e["f15"], "p20": e.get("p20"), "f20": e.get("f20"),
                     "slow_pass": e["slow_pass"], "pass_med": e["pass_med"], "b2b": e.get("b2b"), "slot_usd_month": s["life_pm"], "slot_lose_pct": s["life_lose"],
                     "funded_usd_month": f.get("fund_pm"), "funded_stuck_pct": f.get("fund_stuck"), "eval_risk_usd": x["eval_risk_usd"],
                     "today_pick": {"p10": t["ev"]["p10"], "f10": t["ev"]["f10"], "dec10": t["ev"]["dec10"], "p15": t["ev"]["p15"], "f15": t["ev"]["f15"],
                                    "slow_pass": t["ev"]["slow_pass"], "pass_med": t["ev"]["pass_med"], "slot_usd_month": t["slot"]["life_pm"],
                                    "eval_risk_usd": t["eval_risk_usd"]}}
    out["numbers"] = nums
    out["checks"] = {"shuffled_sizes": {sp: F["pick_safe"][sp]["placebo_shuffle"] for sp in ("H1", "H2", "R")},
                     "random_directions_same_sizes": {sp: F["pick_safe"][sp]["random_dir"] for sp in ("H1", "H2", "R")},
                     "random_directions_today": {sp: F["today"][sp]["random_dir"] for sp in ("H1", "H2", "R")},
                     "years_2021_25_p10_f10": F["years"], "stress": F["stress"],
                     "neighbours": f"{sf['n_beats_all']} of {len(sf['rows'])} later-break sizes beat today's pick on 2-week pass, fail and slot $ in all three "
                                   "(all 54 room-capped ones; 0 of 54 with the $600 cap fixed)"}
    out["v1_pick_for_comparison"] = {"name": src["name"], "eval_25k": src["engine"]["eval_25k"]}
    out["caveats"] = src.get("caveats", []) + [
        "H2 decides fewer evals in 2 weeks (58% vs 71%): fewer fail, the rest stay open longer; H1 passes slower than 3 weeks 12% vs 10%",
        "a later break can risk up to $1,050 after a winning start of the day (never more than the room, 0.9 x the daily loss left): the gain needs that press",
        "the 25K slot still loses about $40 a month in 2021-25: BLITZ on its own 25K stays a 2026-regime bet; the change is eval sizing, not edge",
        "per trade the size is within chance (multiplier placebo p 0.16 / 0.42 / 0.32); the eval effect is not (shuffled sizes reproduce it <= 7.5% of draws)"]
    out.pop("paper_size_for_comparison", None)
    out.pop("speed_pick", None)
    dump(out, os.path.join(OUT_S, "blitz_25k_pick_v2.json"))
    print("wrote research/scalp/blitz_25k_pick_v2.json")


# ================================================================================================ run library
def _blitz_store(TT, mult_fn=None, usd=500.0, trig="blitz"):
    """2021-25 5m + 2026 1m BLITZ trades in the tools/runlib format at usd x mult a trade (integer micros, costs in)."""
    T = [t for t in TT[5] if t["day"] < "2026-01-01"] + [t for t in TT[1] if t["day"] >= "2026-01-01"]
    out = []
    for t in T:
        m = mult_fn(t) if mult_fn else 1.0
        q = max(1, min(20, int(usd * m / t["risk_pm"])))
        out.append({"day": t["day"], "entry_t": t["entry_t"], "exit_t": t["exit_t"], "dir": t["dir"], "r": t["pnl_pm"] / t["risk_pm"],
                    "pnl": round(q * t["pnl_pm"], 2), "risk_pts": t["risk_pts"], "qty": q, "risk_usd": round(q * t["risk_pm"], 2), "half": 0,
                    "exit": t["exit_kind"], "trigger": trig, "mfe": t.get("mfe_pts"), "mae": t["mae_pts"], "bars_held": t["bars"], "regime": None,
                    "mult": m, "low": q * t["mae_pm"]})
    return out


def _atlas_store(V, trig="atlas"):
    V2, A, M, EAB = atlas_libs()
    o, P = V2.score(V, keep_paths=True)
    out = []
    for s in ("2021-24", "2025", "H1", "H2"):
        for t in P[s]:
            ru = t.get("risk_usd") or 0.0
            out.append({"day": t["day"], "entry_t": t["entry_t"], "exit_t": t["exit_t"], "dir": t["dir"], "r": t["pnl"] / ru if ru else 0.0,
                        "pnl": t["pnl"], "risk_pts": t["risk"], "qty": t["qty"], "risk_usd": ru, "half": 0, "exit": t["exit"],
                        "trigger": f"{trig}:{t['src']}", "mfe": None, "mae": None, "bars_held": None, "regime": None, "mult": 1.0, "low": t.get("low")})
    out.sort(key=lambda t: t["entry_t"])
    return o, out


def _aline(o):
    f = lambda s: (f"{s}: 2-week pass/dead {o[s]['p10']}/{o[s]['dead10']}, eval paths ${o[s]['mp_net_less_fees']:,} less fees, path PF {o[s]['pf']}, "
                   f"{o[s]['sig_tpw']} trades/wk")
    return "; ".join(f(s) for s in ("H1", "H2", "2025", "2021-24"))


def cmd_save():
    from tools import runlib as rl
    N, K, BS = blitz_libs()
    V2, A, M, EAB = atlas_libs()
    TT, SP = _prep_blitz()
    sess = sorted(set(M.units()["sessions"]) | {d for sp in SP for d in SP[sp][1]})
    J = lambda n, d=OUT_S: json.load(open(os.path.join(d, n), encoding="utf-8"))
    fin, pk, b2, nth = J("ab_blitz_final.json"), J("ab_blitz_pick.json"), J("ab_blitz2.json"), J("ab_blitz_nth.json")
    sf = J("ab_blitz_safe.json") if os.path.exists(os.path.join(OUT_S, "ab_blitz_safe.json")) else None
    P = PICK_SAFE if sf else PICK_V2
    key = "pick_safe" if sf else "pick"
    F = J("ab_blitz_final_safe.json") if sf and os.path.exists(os.path.join(OUT_S, "ab_blitz_final_safe.json")) else fin
    ev = lambda k, sp: f"{F[k][sp]['ev']['p10']}/{F[k][sp]['ev']['f10']}"
    sl = lambda k, sp: F[k][sp]["slot"]["life_pm"]
    v1 = (f"BLITZ's 25K eval size by the day's break count: the FIRST band break of the day (per side) x{P['dn']}, a later same-side break "
          f"x{P['up']} of today's size ({_ezname(P['z'])}, never more than the room). 25K 2-week pass/fail H1 {ev(key, 'H1')} (today {ev('today', 'H1')}), "
          f"H2 {ev(key, 'H2')} ({ev('today', 'H2')}), 2021-25 {ev(key, 'R')} ({ev('today', 'R')}); whole slot ${sl(key, 'H1')} / ${sl(key, 'H2')} / "
          f"${sl(key, 'R')} a month (today ${sl('today', 'H1')} / ${sl('today', 'H2')} / ${sl('today', 'R')}). Same trades, same rule; only the size. "
          f"Shuffled sizes and random directions do not reproduce it.")
    mf = lambda t: nth_mult(t["f"].get("nth", np.nan), P["up"], P["dn"])
    rl.save("ab_blitz_later_break", "BLITZ 25K: first band break of the day small, later breaks bigger (eval size) - adopt-candidate", "risk",
            "Owner 2026-10-29: BLITZ is a trend-day machine - size it up when the day confirms (break-and-hold), down otherwise?",
            params={**K.TODAY, "later_break": {"first_x": P["dn"], "later_x": P["up"]}}, sizing={"usd_per_trade": 500.0, "x": "later-break mult",
                                                                                                   "eval_25k": P["z"], "funded_25k": PICK_FZ},
            trades=_blitz_store(TT, mf), scored=rl.score(_blitz_store(TT, mf), sess), status="adopt-candidate", verdict=v1,
            notes="tools/ab_edge.py blitz_nth / blitz_pick / blitz_safe / blitz_final (stored at $500 x mult a trade)",
            writeup="atlas-blitz-edge-2026-10-30", tags=["scalp", "blitz", "account_c", "25k", "sizing"])
    c = b2["cands"]["rng_sofar high med x1.5/0.5"]
    v2 = (f"Trend-day size: x1.5 when the day's range so far (09:30 to the signal) is above the H1 median of its 14-day RTH range ratio, x0.5 below. "
          f"$500 view: avg R per unit of risk {c['H1']['r_per_risk']:+.3f} / {c['H2']['r_per_risk']:+.3f} / {c['R']['r_per_risk']:+.3f} (today +0.165 / +0.200 / +0.013), "
          f"$ a month {c['H1']['per_month']} / {c['H2']['per_month']} / {c['R']['per_month']} (today 2,928 / 2,851 / 232); but the multiplier placebo p "
          f"{c['H1']['placebo_p']} / {c['H2']['placebo_p']} / {c['R']['placebo_p']}, 2023 and 2024 worse, and the 25K slot $ does not move. Rejected.")
    mr = (lambda t, med=float(np.median([x["f"]["rng_sofar"] for x in SP["H1"][0]])): 1.5 if t["f"].get("rng_sofar", 0) >= med else 0.5)
    rl.save("ab_blitz_trendday_size", "BLITZ trend-day size (the day's range so far) - rejected (within chance)", "risk",
            "Size BLITZ up on predicted trend days (range so far, first-hour range / volume, overnight range, gap, VIX change)?",
            params={**K.TODAY, "tilt": "rng_sofar >= H1 median x1.5 else x0.5"}, sizing={"usd_per_trade": 500.0},
            trades=_blitz_store(TT, mr), scored=rl.score(_blitz_store(TT, mr), sess), status="rejected", verdict=v2,
            notes="tools/ab_edge.py blitz / blitz2 (390 tilts, family placebo)", writeup="atlas-blitz-edge-2026-10-30", tags=["scalp", "blitz", "sizing"])
    # BLITZ with the 10:30 check (rejected)
    K.WINDOWS["x1030"] = (570, (600, 630), 30)
    TTx = blitz_trades({"wins": ("x1030", "rth")})
    X = J("ab_blitz_x.json")
    rx = next(r for r in X["rows"] if r["variant"] == "+ the 10:30 check" and r["tilt"] == "none")
    v3 = ("BLITZ with one more check at the 10:30 close: $500 view avg R " + " / ".join(f"{rx[sp]['r500']['r_per_risk']:+.3f}" for sp in ("H1", "H2", "R")) +
          " (today +0.165 / +0.200 / +0.013), 25K slot " + " / ".join(f"${rx[sp]['slot']}" for sp in ("H1", "H2", "R")) + " a month. H1 collapses: rejected.")
    rl.save("ab_blitz_1030_check", "BLITZ + a 10:30 check - rejected", "timing", "Owner: the first check at 10:30 instead of 11:00?",
            params={**K.TODAY, "wins": ["x1030", "rth"]}, sizing={"usd_per_trade": 500.0}, trades=_blitz_store(TTx), scored=rl.score(_blitz_store(TTx), sess),
            status="rejected", verdict=v3, notes="tools/ab_edge.py blitzx", writeup="atlas-blitz-edge-2026-10-30", tags=["scalp", "blitz", "timing"])
    # ATLAS
    A1 = J("ab_atlas.json", OUT_A)
    base_V = V2.V_()
    o0, T0 = _atlas_store(base_V)
    for rid, fam, name, V, um, q in (
            ("ab_atlas_dyn_weights", "dyn", "last 10 vs x1.0/0.5", base_V, um_dynamic(["EMA", "MD", "SR"], 10, "vs", 1.0, 0.5),
             "Member weights by the member's own recent trades (last 5 / 10 / 20, sign or vs its own mean)?"),
            ("ab_atlas_agree", "agree", "agree x1.25 / against x0.75", base_V, um_agree(["EMA", "MD", "SR"], 1.25, 0.75),
             "Size an ATLAS trade up when another member already took the same side today, down when against?"),
            ("ab_atlas_lit_copy", "litc", "+ LIT copy x0.25", V2.V_(members=["EMA", "MD", "SR", "LITC"], w={"LITC": 0.25}), None,
             "LIT copied onto ATLAS's 25K as a 4th member (account-B size)?"),
            ("ab_atlas_na_member", "na", "+ NA day-hold x0.5 + hunts x0.5", V2.V_(members=["EMA", "MD", "SR", "NAD", "SHA", "SHT"], w={"NAD": 0.5, "SHA": 0.5, "SHT": 0.5}), None,
             "The noise-area day-hold strategy (diversifier-search.md, positive in all four spans alone) as a 4th member?")):
        if fam == "na" and "NAD" not in M.units():
            M.units()["NAD"] = nad_units()
        if um is not None:
            _UM[rid] = um
            V = {**V, "um": rid}
        o, T = _atlas_store(V)
        vv = V2.verdict(o, o0)
        vt = (f"{name}: {_aline(o)}. ATLAS today: {_aline(o0)}. The v2 test (2-week pass up, dead not up, eval-path $ up in BOTH 2026 halves, "
              f"2025 / 2021-24 not worse): {'passes' if vv['pass'] else 'fails'} (H1 {vv['h1']}, H2 {vv['h2']}, reference tier {vv['ref']}). Rejected.")
        rl.save(rid, f"ATLAS: {name} - rejected", "risk" if um is not None else "other", q, params=V, sizing={"account_b": "need size (engine/account_b.qty)"},
                trades=T, scored=rl.score(T, sess), status="rejected", verdict=vt, notes="tools/ab_edge.py atlas / atlas_na (eval-path trades, 4 spans)",
                writeup="atlas-blitz-edge-2026-10-30", tags=["atlas", "account_b", "25k"])
        print("saved", rid, flush=True)
    # London clock (DST gap weeks)
    D = J("ab_atlas_dst.json", OUT_A)
    r = D["rows"]["both"]
    vt = (f"In the US / UK DST gap weeks ({D['gap_sessions']} of {D['sessions']} sessions since 2021-11) the overnight volume surge moves from 03:00 ET to "
          f"04:00 ET (London's 08:00): {D['normal_top_jumps'][:2]} vs {D['gap_top_jumps'][:2]}. Moving EMA's window to 04:00-09:30 and MACD's London window to "
          f"03:00-06:00 on those days: EMA gap-week trades {D['members']['EMA']['gap_trades_now']} -> {D['members']['EMA']['gap_trades_london_clock']}, "
          f"R {D['members']['EMA']['gap_R_now']} -> {D['members']['EMA']['gap_R_london_clock']}; MACD R {D['members']['MD']['gap_R_now']} -> "
          f"{D['members']['MD']['gap_R_london_clock']}; ATLAS H1 2-week pass {r['o']['H1']['p10']} (today {D['base']['H1']['p10']}), eval-path $ "
          f"{r['o']['H1']['mp_net_less_fees']:,} (today {D['base']['H1']['mp_net_less_fees']:,}). The windows stay on the New York clock: rejected.")
    rl.save("ab_atlas_london_clock", "ATLAS London windows on the London clock in the DST gap weeks - rejected", "timing",
            "Owner: the members' time windows after the DST change (the week of 2026-10-26 is a gap week)?",
            params={"EMA_gap_window": "04:00-09:30", "MD_gap_london": "03:00-06:00"}, sizing={"account_b": "need size"}, trades=T0, scored=rl.score(T0, sess),
            status="rejected", verdict=vt, notes="tools/ab_edge.py dst (trades = ATLAS today; the variant's numbers are in the verdict)",
            writeup="atlas-blitz-edge-2026-10-30", tags=["atlas", "dst", "timing"])
    print("saved runs", flush=True)


# ================================================================================================ ATLAS: London clock in the DST gap weeks
def gap_day(d):
    """True when New York is 4 hours behind London at noon (US summer time already / still on, UK not): the 2-3 weeks of
    March and the week around 1 November. London's 08:00 open is then 04:00 ET instead of 03:00 ET."""
    from zoneinfo import ZoneInfo
    x = dt.datetime.fromisoformat(d + "T12:00:00").replace(tzinfo=dt.timezone.utc)
    ny = x.astimezone(ZoneInfo("America/New_York")).utcoffset()
    ld = x.astimezone(ZoneInfo("Europe/London")).utcoffset()
    return (ld - ny) == dt.timedelta(hours=4)


def cmd_dst():
    t0 = time.time()
    N, K, BS = blitz_libs()
    B = N.bars(5)
    days = B["dates"]
    gap = np.array([gap_day(d) for d in days])
    out = {"built": time.strftime("%Y-%m-%d %H:%M"), "gap_sessions": int(gap.sum()), "sessions": len(days)}
    # (a) where does the overnight volume surge sit, in ET, on normal vs gap days? (5m volume / the day's 00:00-07:00 mean)
    m, v, di = B["mod"], B["v"], B["day"]
    sel = (m >= 0) & (m < 420)
    prof = {False: collections.defaultdict(list), True: collections.defaultdict(list)}
    for d in range(len(days)):
        idx = np.where((di == d) & sel)[0]
        if len(idx) < 60:
            continue
        mu = v[idx].mean()
        if mu <= 0:
            continue
        for i in idx:
            prof[bool(gap[d])][int(m[i])].append(v[i] / mu)
    P = {}
    for g in (False, True):
        P["gap" if g else "normal"] = {int(s): round(float(np.mean(prof[g][s])), 3) for s in sorted(prof[g]) if s % 5 == 0}
    out["volume_profile"] = P
    for g in ("normal", "gap"):
        p = P[g]
        jumps = sorted(((p[s] / p[s - 5], s) for s in p if s - 5 in p and 90 <= s <= 330), reverse=True)[:4]
        out[f"{g}_top_jumps"] = [(f"{s // 60:02d}:{s % 60:02d}", round(r, 2)) for r, s in jumps]
        print(g, "biggest 5m volume jumps (ET):", out[f"{g}_top_jumps"], flush=True)
        print("   ", " ".join(f"{s // 60:02d}:{s % 60:02d}={p[s]:.2f}" for s in range(105, 300, 15) if s in p), flush=True)
    # (b) the members' London windows on the London clock in the gap weeks (EMA 04:00-09:30, MACD 03:00-06:00 + NY)
    V2, A, M, EAB = atlas_libs()
    from tools import atlas_members as AM
    from tools import second_ema as SE
    from tools import second_md as SMD
    SE.WINS["lon_dst"] = (240, 570)
    SMD.KZ["lon_ny_dst"] = ((180, 360), (570, 660))
    U = M.units()
    keep = {k: U[k] for k in ("EMA", "MD")}
    ema_s = AM.units("EMA", json.dumps({"E": {"win": "lon_dst"}}, sort_keys=True))
    md_s = AM.units("MD", json.dumps({"flt": {"kz": "lon_ny_dst"}}, sort_keys=True))
    gd = {d for d in U["sessions"] if gap_day(d)}
    comb = {"EMA": [u for u in keep["EMA"] if u["day"] not in gd] + [{**u, "src": "EMA"} for u in ema_s if u["day"] in gd],
            "MD": [u for u in keep["MD"] if u["day"] not in gd] + [{**u, "src": "MD"} for u in md_s if u["day"] in gd]}
    for k in comb:
        comb[k].sort(key=lambda u: u["entry_t"])
    out["members"] = {}
    for k in ("EMA", "MD"):
        a = [u for u in keep[k] if u["day"] in gd]
        b = [u for u in comb[k] if u["day"] in gd]
        out["members"][k] = {"gap_trades_now": len(a), "gap_R_now": round(sum(_R(u) for u in a), 2),
                             "gap_trades_london_clock": len(b), "gap_R_london_clock": round(sum(_R(u) for u in b), 2)}
        print(k, out["members"][k], flush=True)
    base = a_score(V2.V_())
    rows = {}
    for nm, sub in (("EMA on the London clock", ("EMA",)), ("MACD on the London clock", ("MD",)), ("both", ("EMA", "MD"))):
        for k in sub:
            U[k] = comb[k]
        try:
            A_cache = getattr(A, "_VIX", None)
            o = a_score(V2.V_())
        finally:
            for k in sub:
                U[k] = keep[k]
        v = V2.verdict(o, base)
        rows[nm] = {"o": a_compact(o), "verdict": v}
        print(nm, " | ".join(a_line(o, s) for s in o), flush=True)
    out["base"] = a_compact(base)
    out["rows"] = rows
    dump(out, os.path.join(OUT_A, "ab_atlas_dst.json"))
    print(f"done {time.time() - t0:.0f}s", flush=True)
    return out


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "blitz"
    {"blitz": cmd_blitz, "blitz2": cmd_blitz2, "blitz_eval": cmd_blitz_eval, "blitz_nth": cmd_blitz_nth, "atlas": cmd_atlas,
     "dst": cmd_dst, "blitz50": cmd_blitz50, "blitzx": cmd_blitzx, "atlas_geo": cmd_atlas_geo, "blitz_pick": cmd_blitz_pick, "atlas_na": cmd_atlas_na, "blitz_final": cmd_blitz_final, "blitz_safe": cmd_blitz_safe, "blitz_final_safe": cmd_blitz_final_safe,
     "save": cmd_save, "pick_v2": cmd_pick_v2}[cmd]()
