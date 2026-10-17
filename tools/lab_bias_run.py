"""Daily-bias study runner (rules: research/lab/BIAS_RULES.md; method code: engine/daily_bias.py).

    python -X utf8 tools/lab_bias_run.py raw      # raw predictive test, no strategy  -> research/lab/BIAS_raw.json
    python -X utf8 tools/lab_bias_run.py align    # alignment test on every model bed -> research/lab/BIAS_align.json
    python -X utf8 tools/lab_bias_run.py tables   # markdown tables from both          -> research/lab/BIAS_tables.md
    python -X utf8 tools/lab_bias_run.py all

Read-only on everything outside research/lab/BIAS_*: it never calls strategy_lab.score() (which writes the
leaderboard and confirm log); it only uses bars(), sessions() and _boot().
"""
from __future__ import annotations

import collections
import datetime as dt
import json
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine.daily_bias import METHODS, TICK, BiasContext  # noqa: E402
from tools.strategy_lab import _boot, bars, sessions  # noqa: E402

LAB = os.path.join(ROOT, "research", "lab")
SEED = 20261016
NPERM = 2000
RAW_START = "2022-01-03"
YEARS = ["2022", "2023", "2024", "2025", "2026"]
DEV, CONF = ("2026-01-02", "2026-06-30"), ("2026-07-01", "2026-10-16")
Y25 = ("2025-04-14", "2025-12-31")
SPAN = ("2025-04-14", "2026-10-16")
TEST_METHODS = [m for m in METHODS]            # h1_trend is the reference row; it is still counted in the family
INDEP = ["ENG1", "SB", "MECH", "M22", "CONT", "ATM1m"]
LABEL = {"ttrades": "A ttrades", "ttrades_carry": "A2 ttrades_carry", "htf_draw": "B htf_draw", "structure": "C structure",
         "open_amd": "D open_amd", "composite": "E composite(A,B,C)", "samd_cont": "F1 samd_cont",
         "samd_rev": "F2 samd_rev", "samd_rev_only": "F0 samd_rev_only", "composite2": "E2 composite2(A,B,C,D,F0)",
         "h1_trend": "ref h1_trend"}


def _ctx():
    t0 = time.time()
    b = bars("NQ", "5m")
    ctx = BiasContext(b)
    print(f"context: {len(b)} bars, {ctx.nd} days ({time.time() - t0:.1f}s)", flush=True)
    return ctx


def _pct(x):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(100 * float(x), 1)


def _r(x, k=3):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), k)


# =============================================================================================== raw test
def raw_rows(ctx):
    rows = []
    for m in range(ctx.nd):
        d = ctx.days[m]
        if d < RAW_START:
            continue
        S = ctx._sess(m)
        if S["i930"] is None or np.isnan(ctx.adr[m]) or np.isnan(ctx.atr[m]) or ctx.Y[m] < 0:
            continue
        a, z = ctx.ds[m], ctx.de[m]
        mm = ctx.mod[a:z]
        rth = a + np.flatnonzero((mm >= 570) & (mm < 960))
        if len(rth) < 70:
            continue
        i930 = S["i930"]
        noon = rth[ctx.mod[rth] < 720]
        rec = {"day": d, "m": m, "O": float(ctx.o[i930]), "H": float(ctx.h[rth].max()), "L": float(ctx.l[rth].min()),
               "C": float(ctx.c[rth[-1]]), "H12": float(ctx.h[noon].max()), "L12": float(ctx.l[noon].min()),
               "adr": float(ctx.adr[m]), "atr": float(ctx.atr[m]), "i930": int(i930), "i12": int(noon[-1]) + 1,
               "iend": int(rth[-1]), "t930": int(ctx.t[i930])}
        for mth in METHODS:
            r = ctx.bias(rec["t930"], mth)
            rec[mth] = (r["dir"], r["draw"])
        # sanity (Appendix A): whole CME day vs Y.H / Y.L, strict > as in the appendix
        y = ctx.Y[m]
        rec["cme_hit_yh"] = bool(ctx.dH[m] > ctx.dH[y])
        rec["cme_hit_yl"] = bool(ctx.dL[m] < ctx.dL[y])
        rec["a_state"] = ctx.a_state[m]
        rows.append(rec)
    return rows


def _metrics(rows, mth, rng, nperm=NPERM):
    if not rows:
        return {"n_days": 0}
    D = np.array([r[mth][0] for r in rows], float)
    k = D != 0
    out = {"n_days": len(rows), "coverage": _pct(k.mean()), "n": int(k.sum()), "long_share": _pct((D[k] > 0).mean()) if k.any() else None}
    if k.sum() < 10:
        return out
    O = np.array([r["O"] for r in rows])[k]
    H = np.array([r["H"] for r in rows])[k]
    L = np.array([r["L"] for r in rows])[k]
    C = np.array([r["C"] for r in rows])[k]
    A = np.array([r["adr"] for r in rows])[k]
    dr = np.array([np.nan if r[mth][1] is None else r[mth][1] for r in rows], float)[k]
    d = D[k]
    mv = (C - O) / A
    ex = ((H - O) - (O - L)) / A
    sgn = np.sign(C - O)
    dist = (dr - O) * d
    val = np.isfinite(dist) & (dist > 0)
    up_hit = H >= O + np.where(val, dist, 0) + TICK
    dn_hit = L <= O - np.where(val, dist, 0) - TICK

    def stats(dd):
        m_ = float((dd * mv).mean())
        acc = float((sgn == dd).mean())
        e_ = float((dd * ex).mean())
        hd = np.where(dd > 0, up_hit, dn_hit)[val]
        hm = np.where(dd > 0, dn_hit, up_hit)[val]
        return m_, acc, e_, (float(hd.mean()) if val.any() else np.nan), (float(hm.mean()) if val.any() else np.nan)
    m0, a0, e0, h0, hm0 = stats(d)
    P = np.array([stats(rng.permutation(d)) for _ in range(nperm)])
    out.update({"move_adr": _r(m0), "move_ci": _boot(d * mv, n=2000), "acc": _pct(a0), "mfe_edge_adr": _r(e0),
                "n_draw": int(val.sum()), "hit_draw": _pct(h0), "hit_mirror": _pct(hm0),
                "draw_dist_adr": _r(float(np.median(dist[val] / A[val]))) if val.any() else None,
                "null_move": _r(P[:, 0].mean()), "p_move": _r((P[:, 0] >= m0).mean(), 4),
                "null_acc": _pct(P[:, 1].mean()), "p_acc": _r((P[:, 1] >= a0).mean(), 4),
                "null_mfe": _r(P[:, 2].mean()), "p_mfe": _r((P[:, 2] >= e0).mean(), 4),
                "null_hit": _pct(np.nanmean(P[:, 3])), "p_hit": _r((P[:, 3] >= h0).mean(), 4) if val.any() else None})
    return out


def raw(ctx):
    rng = np.random.default_rng(SEED)
    t0 = time.time()
    rows = raw_rows(ctx)
    print(f"raw rows: {len(rows)} days ({time.time() - t0:.1f}s)", flush=True)
    res = {"n_days": len(rows), "first": rows[0]["day"], "last": rows[-1]["day"], "methods": {}}
    splits = {"all": rows, **{y: [r for r in rows if r["day"][:4] == y] for y in YEARS},
              "dev": [r for r in rows if DEV[0] <= r["day"] <= DEV[1]], "confirm": [r for r in rows if CONF[0] <= r["day"] <= CONF[1]]}
    for mth in METHODS:
        res["methods"][mth] = {s: _metrics(rr, mth, rng, NPERM if s == "all" else 1000) for s, rr in splits.items()}
        a = res["methods"][mth]["all"]
        print(f"  {mth:14s} cov {a.get('coverage')}% n {a.get('n')} move {a.get('move_adr')} (null {a.get('null_move')}, p {a.get('p_move')}) "
              f"acc {a.get('acc')}% (p {a.get('p_acc')}) hit {a.get('hit_draw')} vs mirror {a.get('hit_mirror')} (p {a.get('p_hit')})", flush=True)
    # Appendix A sanity check
    cu = [r for r in rows if r["a_state"] == "CONT_UP"]
    cd = [r for r in rows if r["a_state"] == "CONT_DN"]
    res["sanity"] = {"cont_up_n": len(cu), "cont_up_cme_takes_YH": _pct(np.mean([r["cme_hit_yh"] for r in cu])),
                     "all_cme_takes_YH": _pct(np.mean([r["cme_hit_yh"] for r in rows])),
                     "cont_dn_n": len(cd), "cont_dn_cme_takes_YL": _pct(np.mean([r["cme_hit_yl"] for r in cd])),
                     "all_cme_takes_YL": _pct(np.mean([r["cme_hit_yl"] for r in rows]))}
    print("  sanity:", res["sanity"], flush=True)
    res["proximity_posthoc"] = proximity(ctx, rows, rng)
    print("  proximity (post hoc):", json.dumps(res["proximity_posthoc"]["from_1800"]), flush=True)
    res["samd"] = samd_tables(ctx, rows)
    with open(os.path.join(LAB, "BIAS_raw.json"), "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1, default=float)
    print(f"raw done ({time.time() - t0:.1f}s)", flush=True)
    return res


def proximity(ctx, rows, rng):
    """POST HOC (added after the pre-registered results): how much of the TTrades 'next day takes Y.H 80%' is distance?
    From the 18:00 open, compare taking the TTrades target with taking a level the same distance on the other side.
    Also: is the bias move realized overnight (18:00 -> 09:30) or in NY (09:30 -> 15:55)?"""
    out = {"from_1800": {}, "from_0930_target_untaken": {}, "move_split": {}}
    for st, d in (("CONT_UP", 1), ("CONT_DN", -1), ("REV_UP", 1), ("REV_DN", -1)):
        rs = [r for r in rows if r["a_state"] == st]
        hit, mir, gap, dists, hit9, mir9, on_mv, ny_mv, day_mv = [], [], 0, [], [], [], [], [], []
        for r in rs:
            m = r["m"]
            y = ctx.Y[m]
            T = ctx.dH[y] if d > 0 else ctx.dL[y]
            O18 = ctx.dO[m]
            adr = r["adr"]
            on_mv.append(d * (r["O"] - O18) / adr)
            ny_mv.append(d * (r["C"] - r["O"]) / adr)
            day_mv.append(d * (ctx.dC[m] - O18) / adr)
            dist = (T - O18) * d
            if dist <= 0:
                gap += 1
            else:
                dists.append(dist / adr)
                hit.append(bool(ctx.dH[m] >= T + TICK) if d > 0 else bool(ctx.dL[m] <= T - TICK))
                M = O18 - d * dist
                mir.append(bool(ctx.dL[m] <= M - TICK) if d > 0 else bool(ctx.dH[m] >= M + TICK))
            k = ctx.pdh_taken[m] if d > 0 else ctx.pdl_taken[m]
            if k >= r["i930"]:
                dist9 = (T - r["O"]) * d
                if dist9 > 0:
                    hit9.append(bool(r["H"] >= T + TICK) if d > 0 else bool(r["L"] <= T - TICK))
                    M9 = r["O"] - d * dist9
                    mir9.append(bool(r["L"] <= M9 - TICK) if d > 0 else bool(r["H"] >= M9 + TICK))
        out["from_1800"][st] = {"n": len(rs), "open_already_beyond": gap, "hit_target": _pct(np.mean(hit)) if hit else None,
                                "hit_mirror": _pct(np.mean(mir)) if mir else None,
                                "median_dist_adr": _r(np.median(dists)) if dists else None}
        out["from_0930_target_untaken"][st] = {"n": len(hit9), "share_of_days": _pct(len(hit9) / max(len(rs), 1)),
                                               "rth_hit_target": _pct(np.mean(hit9)) if hit9 else None,
                                               "rth_hit_mirror": _pct(np.mean(mir9)) if mir9 else None}
        out["move_split"][st] = {"overnight_1800_0930_adr": _r(np.mean(on_mv)), "on_ci": _boot(on_mv, n=2000),
                                 "ny_0930_1555_adr": _r(np.mean(ny_mv)), "ny_ci": _boot(ny_mv, n=2000),
                                 "cme_day_adr": _r(np.mean(day_mv)), "day_ci": _boot(day_mv, n=2000)}
    # unconditional overnight drift for reference (NQ drifts up)
    out["all_days_overnight_up_adr"] = _r(np.mean([(r["O"] - ctx.dO[r["m"]]) / r["adr"] for r in rows]))
    out["all_days_ny_up_adr"] = _r(np.mean([(r["C"] - r["O"]) / r["adr"] for r in rows]))
    return out


# ----------------------------------------------------------------------------------------------- session AMD (F)
PRED = {"REV_UP": 1, "REV_DN": -1}


def samd_tables(ctx, rows):
    """Coordinator's state table for the owner's session AMD (F)."""
    out = {}
    for window, ref in (("lon", "asia"), ("ext", "asia"), ("lon", "lo")):
        recs = []
        for r in rows:
            m = r["m"]
            st, info = ctx.samd_state(m, window, ref)
            if st == "NA":
                continue
            S = ctx._sess(m)
            y = ctx.Y[m]
            lv = {"asia_hi": (info["asia_hi"], 1, S["asia"]["i1"] + 1), "asia_lo": (info["asia_lo"], -1, S["asia"]["i1"] + 1),
                  "pdh": (ctx.dH[y], 1, ctx.de[y]), "pdl": (ctx.dL[y], -1, ctx.de[y])}
            if S["lon"]:
                lv["lon_hi"] = (S["lon"]["hi"], 1, S["lon"]["i1"] + 1)
                lv["lon_lo"] = (S["lon"]["lo"], -1, S["lon"]["i1"] + 1)
            tk = {}
            for nm, (x, sd, fi) in lv.items():
                k = ctx._first_take(x, sd, fi)
                tk[nm] = ("pre" if k < r["i930"] else "by12" if k < r["i12"] else "by16" if k <= r["iend"] else "no")
            recs.append({"day": r["day"], "st": st, "up": r["C"] > r["O"], "mv_atr": (r["C"] - r["O"]) / r["atr"],
                         "mfe_up": (r["H"] - r["O"]) / r["atr"], "mfe_dn": (r["O"] - r["L"]) / r["atr"], "tk": tk})
        out[f"{window}_{ref}"] = _samd_summary(recs)
    return out


def _hit_stats(rs, nm):
    tot = len(rs)
    if not tot:
        return None
    un = [x for x in rs if x["tk"].get(nm) not in (None, "pre")]
    if not un:
        return {"untaken_930": 0.0, "by12": None, "by16": None}
    return {"untaken_930": _pct(len(un) / tot), "by12": _pct(np.mean([x["tk"][nm] == "by12" for x in un])),
            "by16": _pct(np.mean([x["tk"][nm] in ("by12", "by16") for x in un]))}


def _samd_summary(recs):
    states = ["REV_UP", "REV_DN", "INPROC_UP", "INPROC_DN", "BOTH", "NONE"]
    S = {"n_days": len(recs)}

    def block(rs):
        if not rs:
            return {"n": 0}
        return {"n": len(rs), "share": _pct(len(rs) / len(recs)), "p_up": _pct(np.mean([x["up"] for x in rs])),
                "mv_atr": _r(np.mean([x["mv_atr"] for x in rs])), "mv_ci": _boot([x["mv_atr"] for x in rs], n=2000),
                "mfe_up_atr": _r(np.mean([x["mfe_up"] for x in rs])), "mfe_dn_atr": _r(np.mean([x["mfe_dn"] for x in rs])),
                "mfe_up_med": _r(np.median([x["mfe_up"] for x in rs])), "mfe_dn_med": _r(np.median([x["mfe_dn"] for x in rs])),
                "hits": {nm: _hit_stats(rs, nm) for nm in ("asia_hi", "lon_hi", "pdh", "asia_lo", "lon_lo", "pdl")}}
    S["all"] = block(recs)
    for st in states:
        S[st] = block([x for x in recs if x["st"] == st])
    # NONE days: which Asia side does NY take (both untaken at 09:30)
    nn = [x for x in recs if x["st"] == "NONE" and x["tk"]["asia_hi"] != "pre" and x["tk"]["asia_lo"] != "pre"]
    if nn:
        hi = np.array([x["tk"]["asia_hi"] in ("by12", "by16") for x in nn])
        lo = np.array([x["tk"]["asia_lo"] in ("by12", "by16") for x in nn])
        S["none_ny"] = {"n": len(nn), "only_high": _pct((hi & ~lo).mean()), "only_low": _pct((lo & ~hi).mean()),
                        "both": _pct((hi & lo).mean()), "neither": _pct((~hi & ~lo).mean())}
    # by year / 2026 month: predicted-direction accuracy and move for REV and INPROC
    def pred_block(rs):
        o = {}
        for st in states[:4]:
            q = [x for x in rs if x["st"] == st]
            o[st] = {"n": len(q), "p_up": _pct(np.mean([x["up"] for x in q])) if q else None,
                     "mv_atr": _r(np.mean([x["mv_atr"] for x in q])) if q else None}
        o["all"] = {"n": len(rs), "p_up": _pct(np.mean([x["up"] for x in rs])) if rs else None,
                    "mv_atr": _r(np.mean([x["mv_atr"] for x in rs])) if rs else None}
        rv = [x for x in rs if x["st"] in PRED]
        o["REV_pred_acc"] = _pct(np.mean([x["up"] == (PRED[x["st"]] > 0) for x in rv])) if rv else None
        o["REV_pred_mv"] = _r(np.mean([x["mv_atr"] * PRED[x["st"]] for x in rv])) if rv else None
        o["REV_n"] = len(rv)
        return o
    S["by_year"] = {y: pred_block([x for x in recs if x["day"][:4] == y]) for y in YEARS}
    S["m2026"] = {mo: pred_block([x for x in recs if x["day"][:7] == mo]) for mo in sorted({x["day"][:7] for x in recs if x["day"][:4] == "2026"})}
    return S


# =============================================================================================== alignment test
def _load(path, key=None):
    with open(os.path.join(LAB, path), encoding="utf-8") as fh:
        o = json.load(fh)
    if key == "eng":
        return o["ytd"]["trades"] + o["y2025"]["trades"]
    if isinstance(o, dict) and "trades" in o:
        return o["trades"]
    return o


def beds():
    B = collections.OrderedDict()
    B["ENG1"] = ("engine live pick, max 1/day", _load("conf_testbed_orig1day.json", "eng"))
    B["ENG2"] = ("engine max 2/day", _load("conf_testbed_engine.json", "eng"))
    B["SB"] = ("Silver Bullet base", _load("SB_trades_NQ_base.json"))
    B["MECH"] = ("Mechanical IFVG base", _load("MECH_trades_NQ_base.json"))
    B["M22"] = ("ICT 2022, no built-in bias", _load("M22_trades/M22_NQ_nobias.json"))
    B["CONT"] = ("Continuation FVG", _load("CONT_trades/CONT_NQ_FVG.json"))
    B["ATM1m"] = ("ATM 1m/3m base (2026)", _load("ATM_trades_1m_base.json"))
    B["ATM1m_best"] = ("ATM 1m/3m best (2026)", _load("ATM_trades_1m_best.json"))
    B["M22canon"] = ("ICT 2022 canon (has a TTrades-like bias built in)", _load("M22_trades/M22_NQ_canon.json"))
    B["CONT_AMPM"] = ("Continuation IFVG_AMPM", _load("CONT_trades/CONT_NQ_IFVG_AMPM.json"))
    B["ATM5m_all"] = ("ATM 5m, every signal (diagnostic)", _load("ATM_trades_diag_noskip_flat.json"))
    out = collections.OrderedDict()
    for k, (desc, tr) in B.items():
        tr = [t for t in tr if SPAN[0] <= t["day"] <= SPAN[1]]
        tr.sort(key=lambda t: t["entry_t"])
        out[k] = (desc, tr)
    return out


def _grp(tr, start, end, nsess):
    x = [t for t in tr if start <= t["day"] <= end]
    if not x:
        return {"n": 0, "tpw": 0.0}
    r = np.array([t["r"] for t in x], float)
    p = np.array([t["pnl"] for t in x], float)
    gp, gl = p[p > 0].sum(), -p[p < 0].sum()
    return {"n": len(x), "tpw": round(len(x) / max(nsess / 5, 1e-9), 2), "win": _pct((p > 0).mean()), "avg_r": _r(r.mean()),
            "ci": _boot(r, n=2000), "pf": _r(gp / gl, 2) if gl > 0 else (None if gp == 0 else 99.0), "net": round(float(p.sum()), 0)}


def align(ctx):
    rng = np.random.default_rng(SEED + 1)
    t0 = time.time()
    B = beds()
    nses = {nm: len(sessions(*pr)) for nm, pr in (("span", SPAN), ("dev", DEV), ("confirm", CONF), ("y2025", Y25),
                                                   ("ytd", ("2026-01-02", "2026-10-16")))}
    res = {"beds": {}, "methods": TEST_METHODS}
    lab_mats, r_vecs, dir_vecs = {}, {}, {}
    for bed, (desc, tr) in B.items():
        if not tr:
            continue
        span = ("2026-01-02", "2026-10-16") if bed.startswith("ATM1m") else SPAN
        ns_span = nses["ytd"] if bed.startswith("ATM1m") else nses["span"]
        labs = np.zeros((len(TEST_METHODS), len(tr)), np.int8)
        bias_dir = np.zeros((len(TEST_METHODS), len(tr)), np.int8)
        for i, t in enumerate(tr):
            for k, mth in enumerate(TEST_METHODS):
                d = ctx.bias(int(t["entry_t"]), mth)["dir"]
                bias_dir[k, i] = d
                labs[k, i] = 0 if d == 0 else (1 if d == int(t["dir"]) else -1)
        lab_mats[bed] = labs
        r_vecs[bed] = np.array([t["r"] for t in tr], float)
        dir_vecs[bed] = np.array([int(t["dir"]) for t in tr], np.int8)
        bres = {"desc": desc, "n": len(tr), "first": tr[0]["day"], "last": tr[-1]["day"], "span": span,
                "all": {p: _grp(tr, *pr, nses[nm]) for p, pr, nm in (("span", span, "span" if not bed.startswith("ATM1m") else "ytd"),
                                                                       ("dev", DEV, "dev"), ("confirm", CONF, "confirm"), ("y2025", Y25, "y2025"),
                                                                       ("ytd", ("2026-01-02", "2026-10-16"), "ytd"))},
                "methods": {}}
        bres["all"]["span"]["tpw"] = round(len(tr) / max(ns_span / 5, 1e-9), 2)
        for k, mth in enumerate(TEST_METHODS):
            L = labs[k]
            al = [t for t, x in zip(tr, L) if x == 1]
            co = [t for t, x in zip(tr, L) if x == -1]
            ne = [t for t, x in zip(tr, L) if x == 0]
            nc = [t for t, x in zip(tr, L) if x != -1]
            mres = {}
            for nm_s, sub in (("aligned", al), ("counter", co), ("neutral", ne), ("skip_counter", nc)):
                mres[nm_s] = {"span": _grp(sub, span[0], span[1], ns_span), "dev": _grp(sub, *DEV, nses["dev"]),
                              "confirm": _grp(sub, *CONF, nses["confirm"]), "y2025": _grp(sub, *Y25, nses["y2025"]),
                              "ytd": _grp(sub, "2026-01-02", "2026-10-16", nses["ytd"])}
            # 2026 monthly
            mon = collections.defaultdict(lambda: {"all": 0.0, "aligned": 0.0, "counter": 0.0, "neutral": 0.0,
                                                   "n_all": 0, "n_aligned": 0})
            for t, x in zip(tr, L):
                if t["day"][:4] != "2026":
                    continue
                mo = mon[t["day"][:7]]
                mo["all"] += t["pnl"]
                mo["n_all"] += 1
                key = "aligned" if x == 1 else "counter" if x == -1 else "neutral"
                mo[key] += t["pnl"]
                if x == 1:
                    mo["n_aligned"] += 1
            mres["m2026"] = {m_: {k_: round(v_, 0) if isinstance(v_, float) else v_ for k_, v_ in v.items()} for m_, v in sorted(mon.items())}
            ra, rc = r_vecs[bed][L == 1], r_vecs[bed][L == -1]
            mres["diff"] = _r(ra.mean() - rc.mean()) if len(ra) and len(rc) else None
            mres["share_aligned"] = _pct((L == 1).mean())
            mres["share_counter"] = _pct((L == -1).mean())
            bres["methods"][mth] = mres
        res["beds"][bed] = bres
        print(f"  bed {bed}: {len(tr)} trades labelled ({time.time() - t0:.1f}s)", flush=True)
    res["perm"] = _perm(lab_mats, r_vecs, dir_vecs, rng)
    res["atm_sweep"] = atm_sweep_check(B, lab_mats)
    with open(os.path.join(LAB, "BIAS_align.json"), "w", encoding="utf-8") as fh:
        json.dump(res, fh, indent=1, default=float)
    print(f"align done ({time.time() - t0:.1f}s)", flush=True)
    return res


def _diff_mat(labs, r):
    A = labs == 1
    C = labs == -1
    na, nc = A.sum(1), C.sum(1)
    with np.errstate(invalid="ignore", divide="ignore"):
        return np.where((na > 0) & (nc > 0), (A @ r) / np.maximum(na, 1) - (C @ r) / np.maximum(nc, 1), np.nan)


def _perm(lab_mats, r_vecs, dir_vecs, rng):
    """Within-bed, within-trade-direction permutation of the bias labels (same permutation for every method)."""
    beds_ = list(lab_mats)
    real = {b: _diff_mat(lab_mats[b], r_vecs[b]) for b in beds_}
    nulls = {b: np.full((NPERM, len(TEST_METHODS)), np.nan) for b in beds_}
    for it in range(NPERM):
        for b in beds_:
            labs, d = lab_mats[b], dir_vecs[b]
            idx = np.arange(labs.shape[1])
            for s in (1, -1):
                g = np.flatnonzero(d == s)
                idx[g] = rng.permutation(g)
            nulls[b][it] = _diff_mat(labs[:, idx], r_vecs[b])
    out = {"tests": [], "pooled": {}}
    zs_null = []
    for b in beds_:
        mu, sd = np.nanmean(nulls[b], 0), np.nanstd(nulls[b], 0)
        for k, mth in enumerate(TEST_METHODS):
            x = real[b][k]
            if not np.isfinite(x) or not np.isfinite(sd[k]) or sd[k] == 0:
                continue
            nz = nulls[b][:, k]
            p = float(np.mean(np.abs(nz[np.isfinite(nz)] - mu[k]) >= abs(x - mu[k])))
            out["tests"].append({"bed": b, "method": mth, "diff": _r(x), "null_mu": _r(mu[k]), "z": _r((x - mu[k]) / sd[k], 2), "p": _r(p, 4)})
        zs_null.append((nulls[b] - mu) / np.where(sd > 0, sd, np.nan))
    # family-wise: max |z| over all tests per permutation (only beds x methods that exist as tests)
    tested = {(t["bed"], t["method"]) for t in out["tests"]}
    mask = np.array([[(b, m) in tested for m in TEST_METHODS] for b in beds_])
    Z = np.stack(zs_null, 1)                             # NPERM x beds x methods
    Zm = np.where(mask[None], np.abs(Z), np.nan)
    mx = np.nanmax(Zm.reshape(NPERM, -1), 1)
    out["fw95_absz"] = _r(np.nanpercentile(mx, 95), 2)
    out["fw_median_max_absz"] = _r(np.nanmedian(mx), 2)
    # BH-FDR at q = 0.10
    ps = sorted(out["tests"], key=lambda t: t["p"])
    m_ = len(ps)
    thr = 0
    for i, t in enumerate(ps, 1):
        if t["p"] <= 0.10 * i / m_:
            thr = i
    for i, t in enumerate(ps, 1):
        t["bh_q10"] = i <= thr
        t["fw"] = abs(t["z"]) >= out["fw95_absz"]
    out["n_tests"] = m_
    # pooled over the independent beds (equal weight)
    ib = [b for b in INDEP if b in real]
    pr_real = np.nanmean(np.stack([real[b] for b in ib]), 0)
    pr_null = np.nanmean(np.stack([nulls[b] for b in ib]), 0)
    mu, sd = pr_null.mean(0), pr_null.std(0)
    pz_null = (pr_null - mu) / sd
    out["pooled_fw95_absz"] = _r(np.percentile(np.abs(pz_null).max(1), 95), 2)
    for k, mth in enumerate(TEST_METHODS):
        x = pr_real[k]
        out["pooled"][mth] = {"diff": _r(x), "null_mu": _r(mu[k]), "z": _r((x - mu[k]) / sd[k], 2),
                              "p": _r(float(np.mean(np.abs(pr_null[:, k] - mu[k]) >= abs(x - mu[k]))), 4),
                              "beds_pos": int(sum(real[b][k] > 0 for b in ib if np.isfinite(real[b][k]))),
                              "beds": len(ib)}
    return out


def atm_sweep_check(B, lab_mats):
    """ATM fades a sweep of the 07:00-09:25 range: trade dir = -(sweep side). Verify that 'sweep against the bias'
    is exactly the aligned split (it must be by construction)."""
    out = {}
    for bed in ("ATM1m", "ATM1m_best"):
        if bed not in B:
            continue
        tr = B[bed][1]
        side = []
        for t in tr:
            s = t.get("setup", "")
            side.append(1 if "high-sweep" in s else (-1 if "low-sweep" in s else 0))
        side = np.array(side)
        d = np.array([t["dir"] for t in tr])
        out[bed] = {"n": len(tr), "dir_is_minus_sweep_side": _pct(np.mean(d == -side)) if len(tr) else None,
                    "unknown_side": int((side == 0).sum())}
    return out


# =============================================================================================== tables
def _fmt_g(g):
    if not g or not g.get("n"):
        return "0 | | | | |"
    ci = g.get("ci") or [None, None]
    cis = f"[{ci[0]:+.2f}, {ci[1]:+.2f}]" if ci[0] is not None else ""
    return f"{g['n']} | {g['win']} | {g['avg_r']:+.2f} {cis} | {g['pf']} | {g['net']:+,.0f}"


def tables():
    with open(os.path.join(LAB, "BIAS_raw.json"), encoding="utf-8") as fh:
        RAW = json.load(fh)
    with open(os.path.join(LAB, "BIAS_align.json"), encoding="utf-8") as fh:
        AL = json.load(fh)
    T = [f"# BIAS tables (generated {dt.datetime.now().strftime('%Y-%m-%d %H:%M')} by `python -X utf8 tools/lab_bias_run.py tables`)", ""]
    T += ["## 1. Raw predictive test at 09:30, NQ RTH, " + f"{RAW['first']}..{RAW['last']} ({RAW['n_days']} days)", "",
          "move = mean RTH (close - 09:30 open) in the bias direction, in ADR20. acc = share of biased days closing with the bias. "
          "hit = RTH takes the method's draw (untaken at 09:30); mirror = the same distance on the other side. "
          "null = 2,000 permutations of the bias across biased days (keeps the long/short mix); p one-sided.", "",
          "| method | coverage % | long % | n | move ADR [95% CI] | null move | p | acc % | null acc | p | MFE edge ADR | p | hit draw % | mirror % | null hit | p | median draw dist ADR |",
          "|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for mth in METHODS:
        a = RAW["methods"][mth]["all"]
        ci = a.get("move_ci") or [None, None]
        T.append(f"| {LABEL[mth]} | {a.get('coverage')} | {a.get('long_share')} | {a.get('n')} | {a.get('move_adr'):+.3f} [{ci[0]:+.3f}, {ci[1]:+.3f}] | "
                 f"{a.get('null_move'):+.3f} | {a.get('p_move')} | {a.get('acc')} | {a.get('null_acc')} | {a.get('p_acc')} | {a.get('mfe_edge_adr'):+.3f} | "
                 f"{a.get('p_mfe')} | {a.get('hit_draw')} | {a.get('hit_mirror')} | {a.get('null_hit')} | {a.get('p_hit')} | {a.get('draw_dist_adr')} |")
    T += ["", "### 1b. By calendar year and dev/confirm: move in ADR (p) | accuracy % | hit draw % vs mirror %", "",
          "| method | " + " | ".join(YEARS + ["dev", "confirm"]) + " |", "|---|" + "---|" * (len(YEARS) + 2)]
    for mth in METHODS:
        cells = []
        for s in YEARS + ["dev", "confirm"]:
            a = RAW["methods"][mth][s]
            if a.get("move_adr") is None:
                cells.append(f"n={a.get('n')}")
            else:
                cells.append(f"{a['move_adr']:+.3f} (p {a['p_move']:.2f}) / {a['acc']} / {a['hit_draw']} v {a['hit_mirror']} (n {a['n']})")
        T.append(f"| {LABEL[mth]} | " + " | ".join(cells) + " |")
    s = RAW["sanity"]
    T += ["", f"Sanity vs TRADER_HEURISTICS Appendix A: CONT_UP days n={s['cont_up_n']}, CME day takes Y.H {s['cont_up_cme_takes_YH']}% "
          f"(all days {s['all_cme_takes_YH']}%); CONT_DN n={s['cont_dn_n']}, takes Y.L {s['cont_dn_cme_takes_YL']}% (all {s['all_cme_takes_YL']}%).", ""]
    px = RAW.get("proximity_posthoc")
    if px:
        T += ["### 1c. POST HOC: how much of the TTrades hit rate is distance, and when is the move realized?", "",
              "From the 18:00 open: P(the CME day takes the TTrades target) vs P(it takes a level the same distance on the other side). "
              "From 09:30 (target still untaken): the same in RTH. Moves in ADR20 in the bias direction, with bootstrap 95% CI.", "",
              "| state | n | 18:00: hit target % | mirror % | median dist ADR | open already beyond | 09:30 untaken: n (share) | RTH hit % | mirror % | move 18:00-09:30 ADR | move 09:30-15:55 ADR | whole CME day ADR |",
              "|---|---:|---:|---:|---:|---:|---|---:|---:|---|---|---|"]
        for st in ("CONT_UP", "CONT_DN", "REV_UP", "REV_DN"):
            a_, b_, c_ = px["from_1800"][st], px["from_0930_target_untaken"][st], px["move_split"][st]
            fmt = lambda v, ci: f"{v:+.3f} [{ci[0]:+.3f}, {ci[1]:+.3f}]" if ci and ci[0] is not None else f"{v:+.3f}"
            T.append(f"| {st} | {a_['n']} | {a_['hit_target']} | {a_['hit_mirror']} | {a_['median_dist_adr']} | {a_['open_already_beyond']} | "
                     f"{b_['n']} ({b_['share_of_days']}%) | {b_['rth_hit_target']} | {b_['rth_hit_mirror']} | {fmt(c_['overnight_1800_0930_adr'], c_['on_ci'])} | "
                     f"{fmt(c_['ny_0930_1555_adr'], c_['ny_ci'])} | {fmt(c_['cme_day_adr'], c_['day_ci'])} |")
        T += ["", f"Unconditional drift, all days: 18:00-09:30 {px['all_days_overnight_up_adr']:+.3f} ADR, 09:30-15:55 {px['all_days_ny_up_adr']:+.3f} ADR (up = +).", ""]
    # session AMD
    T += ["## 2. Session AMD (F): state table at 09:25", ""]
    for key, nm in (("lon_asia", "primary: London 02:00-04:55, REV = 09:20 close back past the Asia extreme"),
                    ("ext_asia", "variant: extended window 02:00-09:20"), ("lon_lo", "variant: REV = back past the London open")):
        S = RAW["samd"][key]
        T += [f"### {nm} ({S['n_days']} days)", "",
              "| state | n | share % | P(NY up) % | mean move ATR [95% CI] | MFE up / down ATR (mean) | median | Asia H by12/by16 (untaken@9:30 %) | London H | PDH | Asia L | London L | PDL |",
              "|---|---:|---:|---:|---|---|---|---|---|---|---|---|---|"]
        for st in ("all", "REV_UP", "REV_DN", "INPROC_UP", "INPROC_DN", "BOTH", "NONE"):
            b = S[st]
            if not b.get("n"):
                T.append(f"| {st} | 0 | | | | | | | | | | | |")
                continue
            ci = b["mv_ci"] or [0, 0]
            hs = []
            for lv in ("asia_hi", "lon_hi", "pdh", "asia_lo", "lon_lo", "pdl"):
                h = b["hits"][lv]
                hs.append("" if not h else f"{h['by12']}/{h['by16']} ({h['untaken_930']})")
            T.append(f"| {st} | {b['n']} | {b['share']} | {b['p_up']} | {b['mv_atr']:+.3f} [{ci[0]:+.3f}, {ci[1]:+.3f}] | {b['mfe_up_atr']:.2f} / {b['mfe_dn_atr']:.2f} | "
                     f"{b['mfe_up_med']:.2f} / {b['mfe_dn_med']:.2f} | " + " | ".join(hs) + " |")
        if S.get("none_ny"):
            q = S["none_ny"]
            T += ["", f"NONE days with both Asia sides untaken at 09:30 (n={q['n']}): NY takes only the Asia high {q['only_high']}%, only the low "
                  f"{q['only_low']}%, both {q['both']}%, neither {q['neither']}%."]
        T += ["", "By year: P(NY up) % / mean move ATR per state; REV accuracy = closes in the predicted direction", "",
              "| year | all | REV_UP | REV_DN | INPROC_UP | INPROC_DN | REV accuracy % (n) | REV move with prediction ATR |", "|---|---|---|---|---|---|---:|---:|"]
        for y in YEARS:
            o = S["by_year"][y]
            c_ = [f"{o[k]['p_up']} / {o[k]['mv_atr']} (n {o[k]['n']})" if o[k]["n"] else "-" for k in ("all", "REV_UP", "REV_DN", "INPROC_UP", "INPROC_DN")]
            T.append(f"| {y} | " + " | ".join(c_) + f" | {o['REV_pred_acc']} ({o['REV_n']}) | {o['REV_pred_mv']} |")
        T += ["", "2026 by month", "", "| month | all | REV_UP | REV_DN | INPROC_UP | INPROC_DN | REV accuracy % (n) | REV move ATR |", "|---|---|---|---|---|---|---:|---:|"]
        for mo, o in S["m2026"].items():
            c_ = [f"{o[k]['p_up']} / {o[k]['mv_atr']} (n {o[k]['n']})" if o[k]["n"] else "-" for k in ("all", "REV_UP", "REV_DN", "INPROC_UP", "INPROC_DN")]
            T.append(f"| {mo} | " + " | ".join(c_) + f" | {o['REV_pred_acc']} ({o['REV_n']}) | {o['REV_pred_mv']} |")
        T.append("")
    # alignment
    P = AL["perm"]
    T += ["## 3. Alignment test on model trades", "",
          f"diff = avg R aligned - avg R counter over the bed's span. z and p from {NPERM} within-direction label permutations. "
          f"Family-wise 95% line over all {P['n_tests']} tests: |z| >= {P['fw95_absz']} (median max |z| under the null {P['fw_median_max_absz']}). "
          "BH = survives Benjamini-Hochberg at q = 0.10.", ""]
    zl = {(t["bed"], t["method"]): t for t in P["tests"]}
    beds_ = list(AL["beds"])
    T += ["### 3a. diff in R (z) per bed", "", "| method | " + " | ".join(beds_) + " | pooled (indep. beds) | pooled z | pooled p | beds > 0 |",
          "|---|" + "---:|" * (len(beds_) + 4)]
    for mth in TEST_METHODS:
        cells = []
        for b in beds_:
            t = zl.get((b, mth))
            cells.append("-" if not t else f"{t['diff']:+.2f} ({t['z']:+.1f}){'*' if t['bh_q10'] else ''}{'!' if t['fw'] else ''}")
        pp = P["pooled"][mth]
        T.append(f"| {LABEL[mth]} | " + " | ".join(cells) + f" | {pp['diff']:+.3f} | {pp['z']:+.2f} | {pp['p']} | {pp['beds_pos']}/{pp['beds']} |")
    T += ["", f"`*` = BH q 0.10, `!` = family-wise. Pooled family-wise 95% line over the {len(TEST_METHODS)} methods: |z| >= {P['pooled_fw95_absz']}.", ""]
    # 3c: sign consistency of the diff by period
    T += ["### 3c. diff (aligned - counter avg R) by period: y2025 / dev / confirm (n aligned / n counter in the full span)", "",
          "| method | " + " | ".join(beds_) + " |", "|---|" + "---|" * len(beds_)]
    for mth in TEST_METHODS:
        cells = []
        for b in beds_:
            M = AL["beds"][b]["methods"][mth]
            ds_ = []
            for per in ("y2025", "dev", "confirm"):
                a_, c_ = M["aligned"][per], M["counter"][per]
                ds_.append("." if not a_.get("n") or not c_.get("n") else f"{a_['avg_r'] - c_['avg_r']:+.2f}")
            cells.append(" / ".join(ds_) + f" ({M['aligned']['span'].get('n', 0)}/{M['counter']['span'].get('n', 0)})")
        T.append(f"| {LABEL[mth]} | " + " | ".join(cells) + " |")
    # 3d: 2026 impact of enforcing alignment
    T += ["", "### 3d. 2026 YTD (2026-01-02..10-16): all trades vs aligned-only vs skip-counter (aligned + neutral)", "",
          "Each cell: trades/week, net $, PF.", "", "| bed | all trades | method | aligned only | skip counter | counter only |", "|---|---|---|---|---|---|"]

    def cell(g):
        return "0 trades" if not g.get("n") else f"{g['tpw']}/wk, {g['net']:+,.0f}, PF {g['pf']}"
    for b in beds_:
        A_ = AL["beds"][b]
        first = True
        for mth in TEST_METHODS:
            M = A_["methods"][mth]
            T.append(f"| {b if first else ''} | {cell(A_['all']['ytd']) if first else ''} | {LABEL[mth]} | {cell(M['aligned']['ytd'])} | "
                     f"{cell(M['skip_counter']['ytd'])} | {cell(M['counter']['ytd'])} |")
            first = False
    # 3e: 2026 monthly for the pre-declared 'best' (highest pooled z) and for TTrades (the owner's habit)
    best = max(TEST_METHODS, key=lambda m_: P["pooled"][m_]["z"] if P["pooled"][m_]["z"] is not None else -9)
    for mth in dict.fromkeys([best, "ttrades"]):
        T += ["", f"### 3e. 2026 monthly net $: all trades / aligned only / skip counter, method {LABEL[mth]}"
              + (" (highest pooled z, picked after seeing results)" if mth == best else " (the owner's habit)"), "",
              "| month | " + " | ".join(beds_) + " |", "|---|" + "---|" * len(beds_)]
        months = sorted({mo for b in beds_ for mo in AL["beds"][b]["methods"][mth]["m2026"]})
        for mo in months:
            cells = []
            for b in beds_:
                v = AL["beds"][b]["methods"][mth]["m2026"].get(mo)
                cells.append("." if not v else f"{v['all']:+,.0f} / {v['aligned']:+,.0f} / {v['aligned'] + v['neutral']:+,.0f}")
            T.append(f"| {mo} | " + " | ".join(cells) + " |")
    T.append("")
    for b in beds_:
        B = AL["beds"][b]
        T += [f"### 3b. {b}: {B['desc']} ({B['n']} trades, {B['first']}..{B['last']})", "",
              f"All trades: span {_fmt_g(B['all']['span'])} | {B['all']['span']['tpw']}/wk; dev {_fmt_g(B['all']['dev'])}; confirm {_fmt_g(B['all']['confirm'])}; y2025 {_fmt_g(B['all']['y2025'])}", "",
              "| method | split | span: n | win % | avg R [CI] | PF | net $ | /wk | dev: n, avg R, net | confirm: n, avg R, net | y2025: n, avg R, net |",
              "|---|---|---:|---:|---|---:|---:|---:|---|---|---|"]
        for mth in TEST_METHODS:
            M = B["methods"][mth]
            for sp in ("aligned", "counter", "neutral", "skip_counter"):
                g = M[sp]
                def short(x):
                    return "0" if not x.get("n") else f"{x['n']}, {x['avg_r']:+.2f}, {x['net']:+,.0f}"
                T.append(f"| {LABEL[mth] if sp == 'aligned' else ''} | {sp} | {_fmt_g(g['span'])} | {g['span'].get('tpw')} | {short(g['dev'])} | {short(g['confirm'])} | {short(g['y2025'])} |")
        T.append("")
    with open(os.path.join(LAB, "BIAS_tables.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(T) + "\n")
    print("tables written", flush=True)


def posthoc(ctx):
    """POST HOC (after the pre-registered results): is D's lift just 'entry on the reclaimed side of the open'?
    open_side = sign(last close before entry - reference open), reference = O930 once the 09:30 bar has printed, else MO.
    Reports, per bed: diff for open_side alone, and diff for D inside the open_side-aligned trades only."""
    rng = np.random.default_rng(SEED + 3)
    B = beds()
    out = {}
    for bed in INDEP + ["ENG2", "ATM1m_best"]:
        tr = B[bed][1]
        r = np.array([t["r"] for t in tr], float)
        dd = np.array([int(t["dir"]) for t in tr])
        side, dl = [], []
        for t in tr:
            et = int(t["entry_t"])
            j, m = ctx._locate(et)
            S = ctx._sess(m) if m < ctx.nd else None
            ref = None
            if S is not None:
                if S["i930"] is not None and ctx.t[S["i930"]] <= et:
                    ref = S["o930"]
                elif S["i_mo"] is not None and ctx.t[S["i_mo"]] <= et:
                    ref = S["mo"]
            side.append(0 if ref is None or j < 0 or ctx.c[j] == ref else int(np.sign(ctx.c[j] - ref)))
            dl.append(ctx.bias(et, "open_amd")["dir"])
        side, dl = np.array(side), np.array(dl)
        os_al = (side == dd) & (side != 0)
        os_co = (side == -dd) & (side != 0)
        d_al, d_co = (dl == dd) & (dl != 0), (dl == -dd) & (dl != 0)

        def diff(a, c):
            return _r(r[a].mean() - r[c].mean()) if a.any() and c.any() else None
        out[bed] = {"n": len(tr), "open_side_aligned_n": int(os_al.sum()), "open_side_counter_n": int(os_co.sum()),
                    "open_side_diff": diff(os_al, os_co),
                    "open_side_aligned_avg_r": _r(r[os_al].mean()) if os_al.any() else None,
                    "open_side_counter_avg_r": _r(r[os_co].mean()) if os_co.any() else None,
                    "D_within_open_side_aligned": {"D_aligned_n": int((os_al & d_al).sum()), "D_not_aligned_n": int((os_al & ~d_al).sum()),
                                                   "diff": diff(os_al & d_al, os_al & ~d_al)},
                    "D_aligned_share_on_reclaimed_side": _pct((os_al[d_al]).mean()) if d_al.any() else None}
    ib = [b for b in INDEP if out[b]["open_side_diff"] is not None]
    out["pooled_open_side_diff"] = _r(np.mean([out[b]["open_side_diff"] for b in ib]))
    ib2 = [b for b in INDEP if out[b]["D_within_open_side_aligned"]["diff"] is not None]
    out["pooled_D_within_open_side_aligned_diff"] = _r(np.mean([out[b]["D_within_open_side_aligned"]["diff"] for b in ib2]))
    print(json.dumps(out, indent=1))
    with open(os.path.join(LAB, "BIAS_posthoc.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1)


def lookahead(n_tr=150, n_days=50, window_days=90):
    """Recompute every method on a frame cut at the decision time (no future bars at all) and compare with the
    full-frame answer; also report agreement when only the last `window_days` trading days are passed (live use)."""
    rng = np.random.default_rng(SEED + 2)
    b = bars("NQ", "5m")
    full = BiasContext(b)
    B = beds()
    ts = [int(t["entry_t"]) for bed in ("ENG1", "SB", "MECH", "M22", "CONT", "ATM1m") for t in B[bed][1]]
    ts = list(rng.choice(ts, size=min(n_tr, len(ts)), replace=False))
    rows = raw_rows(full)
    ts += [r["t930"] for r in rng.choice(rows, size=n_days, replace=False)]
    tt = b["time"].to_numpy(np.int64)
    mism, mism_w, tot = collections.Counter(), collections.Counter(), 0
    ex = []
    for t in ts:
        j = int(np.searchsorted(tt, t - 300, side="right"))
        cut = BiasContext(b.iloc[:j])
        day0 = b["day"].iloc[j - 1]
        days_u = b["day"].iloc[:j].unique()
        w0 = days_u[max(0, len(days_u) - window_days)]
        win = BiasContext(b.iloc[:j][b["day"].iloc[:j] >= w0])
        tot += 1
        for mth in METHODS:
            a, c_, w_ = full.bias(t, mth), cut.bias(t, mth), win.bias(t, mth)
            if a["dir"] != c_["dir"] or (a["draw"] is not None and c_["draw"] is not None and abs(a["draw"] - c_["draw"]) > 1e-6):
                mism[mth] += 1
                if len(ex) < 10:
                    ex.append((int(t), mth, a["dir"], c_["dir"], a["draw"], c_["draw"], day0))
            if a["dir"] != w_["dir"]:
                mism_w[mth] += 1
    out = {"samples": tot, "mismatch_cut": dict(mism), "examples": ex,
           f"dir_differs_with_{window_days}d_window": {m: _pct(mism_w[m] / tot) for m in METHODS}}
    print(json.dumps(out, indent=1, default=str))
    with open(os.path.join(LAB, "BIAS_lookahead.json"), "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, default=str)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    if cmd == "lookahead":
        lookahead()
    if cmd == "posthoc":
        posthoc(_ctx())
    if cmd in ("raw", "align", "all"):
        ctx = _ctx()
        if cmd in ("raw", "all"):
            raw(ctx)
        if cmd in ("align", "all"):
            align(ctx)
    if cmd in ("tables", "all"):
        tables()
