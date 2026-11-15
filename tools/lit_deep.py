"""Team E-LIT deep edge (2026-11-15, owner: "look deeper for edges"). RESEARCH ONLY: engine/ and live_model*.json untouched.

Goes past size tilts (S2, tools/lit_s2_edge.py): WHY LIT loses, where Jul-Oct fell from Jan-Jun, which setups formed but were
skipped (limit not filled, the 1-trade cap, the entry window), and STRUCTURAL rules: a setup skipped before the entry with
the day left free (engine skip_keys, so a later setup of that day can still trade, exactly like the live loop), re-run through
engine/lit.py run_x with the live parameters. Same scoring as S2 (tools/lit_edge.evaluate: LIT size rule, the live eval path
two_week room_f 0.4 kept past session 10, the funded 50K Monte Carlo).

  python -X utf8 tools/lit_deep.py diag      # 2026 trades by setup feature, H1 vs H2 -> research/lit/deep_diag.json
  python -X utf8 tools/lit_deep.py missed    # setups that formed but did not trade, and what they would have done
  python -X utf8 tools/lit_deep.py grid      # structural rules (picked on H1 only) -> research/lit/deep_grid.json
  python -X utf8 tools/lit_deep.py report
  python -X utf8 tools/lit_deep.py save      # rl.save runs lit_deep_*
"""
from __future__ import annotations

import collections
import json
import math
import os
import sys
import time

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from engine import lit  # noqa: E402
from tools import lit_ideas_night as N  # noqa: E402
from tools import lit_edge as E  # noqa: E402
from tools import lit_adv_manage as A  # noqa: E402
from tools import lit_final as F  # noqa: E402

ROOM = float(os.environ.get("DEEP_ROOM", "0.4"))
UNTIL = int(os.environ.get("DEEP_UNTIL", "80"))
A.CFG = {**A.CFG, "two_week": {**A.CFG["two_week"], "room_f": ROOM}, "two_week_until": UNTIL}
OUT_D = os.path.join(ROOT, "research", "lit", "deep_diag.json")
OUT_M = os.path.join(ROOT, "research", "lit", "deep_missed.json")
OUT = os.environ.get("DEEP_OUT") or os.path.join(ROOT, "research", "lit", "deep_grid.json")
SPANS = E.SPANS
LIVE = E.LIVE
H1 = ("2026-01-01", "2026-06-30")
H2 = ("2026-07-01", "2026-12-31")


def span_of(d):
    return "H1" if H1[0] <= d <= H1[1] else "H2" if H2[0] <= d <= H2[1] else "REF"


# ================================================================================================ features
def facts(t):
    """Facts known at the fill for live trade t (trade_intel row + engine candidate + a few derived, signed by direction)."""
    c = E.ctx()
    row = dict(c["intel"].get(int(t["entry_t"]), {}))
    z = E.zc(t)
    M = c["M"]
    x = M.ctx[z["k"]]
    d = int(t["dir"])
    vm = float(x["vix_move"])
    tg = abs(float(t["target_px"]) - float(t["entry_px"]))
    o18 = float(x["open18"])
    f = {k: row.get(k) for k in ("depth_atr", "disp", "idm_n", "idm_dist", "stop_pts", "stop_atr", "rr", "tgt_pts", "entry_min",
                                 "since_open", "wait_min", "sweep_bars", "leg_bars", "vix", "vix_chg", "atr_regime", "day_rng",
                                 "asia_rng", "obst_r", "lvl_age_h", "lvl_touches", "n_lvls", "wick", "news_next", "lvl_type",
                                 "session", "weekday", "major", "macro", "close_back", "vec", "how", "fill")}
    f["side"] = "long" if d == 1 else "short"
    f["tgt_vix"] = tg / vm if vm else np.nan                                   # target distance in VIX one-day moves
    f["used_vix"] = d * (float(t["entry_px"]) - o18) / vm if vm else np.nan    # move from the 18:00 open in the trade's way
    for k in ("h4_draw", "prev_day", "gap", "pd18", "prev_week"):
        v = row.get(k)
        f[k + "_s"] = d * float(v) if v is not None else np.nan               # + = with the trade
    f["stop_vix"] = float(t["risk_pts"]) / vm if vm else np.nan
    f["ext_to_fill_min"] = (int(t["entry_t"]) - int(M.t[int(z["ext_i"])])) / 60.0
    f["lvl_cls"] = "+".join(sorted(set(z.get("swept_cls") or [])))
    return f


NUM = ["depth_atr", "disp", "idm_n", "idm_dist", "stop_pts", "stop_atr", "rr", "tgt_pts", "tgt_vix", "used_vix", "stop_vix",
       "entry_min", "since_open", "wait_min", "sweep_bars", "leg_bars", "ext_to_fill_min", "vix", "vix_chg", "atr_regime",
       "day_rng", "asia_rng", "obst_r", "lvl_age_h", "lvl_touches", "n_lvls", "wick", "news_next", "h4_draw_s", "prev_day_s",
       "gap_s", "pd18_s", "prev_week_s"]
CAT = ["lvl_type", "lvl_cls", "session", "weekday", "side", "major", "macro", "close_back", "vec", "how", "fill"]


def rstats(R):
    R = np.array(R, float)
    if not len(R):
        return {"n": 0}
    g, l_ = R[R > 0].sum(), -R[R < 0].sum()
    return {"n": int(len(R)), "win": round(100 * float((R > 0.05).mean()), 1), "mean_r": round(float(R.mean()), 3),
            "sum_r": round(float(R.sum()), 2), "pf": round(float(g / l_), 2) if l_ > 0 else None}


def diag():
    c = E.ctx()
    T = [t for t in c["T"] if t["day"] >= "2026"]
    rows = []
    for t in T:
        f = facts(t)
        f.update(day=t["day"], sp=span_of(t["day"]), r=float(t["r"]), pnl=float(t["pnl"]), exit=t["exit"], mfe=float(t["mfe"]))
        rows.append(f)
    out = {"n": len(rows)}
    # H1 -> H2: what changed (mix of exits, win rate, size of wins and losses)
    dec = {}
    for sp in ("H1", "H2"):
        X = [r for r in rows if r["sp"] == sp]
        R = np.array([r["r"] for r in X])
        ex = collections.Counter(r["exit"] for r in X)
        dec[sp] = {**rstats(R), "exits": {k: [v, round(float(np.mean([r["r"] for r in X if r["exit"] == k])), 2)] for k, v in ex.items()},
                   "avg_win_r": round(float(R[R > 0.05].mean()), 2), "avg_loss_r": round(float(R[R < -0.05].mean()), 2),
                   "target_hit": round(100 * ex["TARGET"] / len(X), 1), "mean_rr_planned": round(float(np.mean([r["rr"] for r in X])), 2),
                   "mean_tgt_vix": round(float(np.nanmean([r["tgt_vix"] for r in X])), 3),
                   "mean_vix": round(float(np.nanmean([r["vix"] for r in X])), 2),
                   "mean_stop_pts": round(float(np.mean([r["stop_pts"] for r in X])), 1),
                   "mfe_ge_2": round(100 * float(np.mean([r["mfe"] >= 2 for r in X])), 1),
                   "mfe_lt_05": round(100 * float(np.mean([r["mfe"] < 0.5 for r in X])), 1),
                   "per_week": round(len(X) / (sum(1 for d in F.SESS if (H1 if sp == "H1" else H2)[0] <= d <= (H1 if sp == "H1" else H2)[1] and d <= "2026-10-16") / 5), 2)}
        # target reached? among trades that ran >= 2R, how many got the band
        dec[sp]["tgt_of_mfe2"] = round(100 * float(np.mean([r["exit"] == "TARGET" for r in X if r["mfe"] >= 2])), 1) if any(r["mfe"] >= 2 for r in X) else None
    out["h1_vs_h2"] = dec
    # features: H1 terciles (the cut points come from Jan-Jun only), stats per bin per half
    feat = {}
    for k in NUM:
        v1 = np.array([r[k] for r in rows if r["sp"] == "H1" and r[k] is not None and r[k] == r[k]], float)
        if len(v1) < 15:
            continue
        q1, q2 = np.quantile(v1, [1 / 3, 2 / 3])
        if q1 == q2:
            bins = [("<= %.3g" % q1, lambda v, q=q1: v <= q), ("> %.3g" % q1, lambda v, q=q1: v > q)]
        else:
            bins = [("low <= %.3g" % q1, lambda v, a=q1: v <= a), ("mid", lambda v, a=q1, b=q2: a < v <= b),
                    ("high > %.3g" % q2, lambda v, b=q2: v > b)]
        feat[k] = {}
        for nm, fn in bins:
            feat[k][nm] = {sp: rstats([r["r"] for r in rows if r["sp"] == sp and r[k] is not None and r[k] == r[k] and fn(float(r[k]))])
                           for sp in ("H1", "H2")}
        # H2 shift: mean feature value per half
        feat[k]["_mean"] = {sp: round(float(np.nanmean([float(r[k]) for r in rows if r["sp"] == sp and r[k] is not None])), 3)
                            for sp in ("H1", "H2")}
    for k in CAT:
        feat[k] = {}
        for v in sorted({str(r[k]) for r in rows}):
            feat[k][v] = {sp: rstats([r["r"] for r in rows if r["sp"] == sp and str(r[k]) == v]) for sp in ("H1", "H2")}
    out["features"] = feat
    # consistency: features whose best / worst H1 bin keeps its sign in H2
    cons = []
    for k, bins in feat.items():
        bb = {b: s for b, s in bins.items() if not b.startswith("_") and s["H1"].get("n", 0) >= 8}
        if len(bb) < 2:
            continue
        worst = min(bb, key=lambda b: bb[b]["H1"]["mean_r"])
        best = max(bb, key=lambda b: bb[b]["H1"]["mean_r"])
        cons.append({"feat": k, "worst": worst, "worst_h1": bb[worst]["H1"], "worst_h2": bb[worst]["H2"],
                     "best": best, "best_h1": bb[best]["H1"], "best_h2": bb[best]["H2"]})
    out["extremes"] = cons
    out["rows"] = rows
    json.dump(out, open(OUT_D, "w"), indent=1, default=lambda o: o.item() if isinstance(o, np.generic) else str(o))
    # print
    for sp, s in dec.items():
        print(sp, s)
    print()
    for x in cons:
        a, b = x["worst_h1"], x["worst_h2"]
        print(f"{x['feat']:16s} worst {x['worst']:18s} H1 n{a['n']:3d} {a['mean_r']:+.2f}R  H2 n{b.get('n', 0):3d} {b.get('mean_r', 0):+.2f}R"
              f" | best {x['best']:18s} H1 n{x['best_h1']['n']:3d} {x['best_h1']['mean_r']:+.2f}R  H2 n{x['best_h2'].get('n', 0):3d} "
              f"{x['best_h2'].get('mean_r', 0):+.2f}R")
    return out


# ================================================================================================ missed setups
def key_of(t):
    return (t["day"], int(t["i"]), int(t["dir"]))


MISSED = collections.OrderedDict([
    ("cap", ({"max_per_day": 3}, "blocked by the 1-trade-a-day cap (a 2nd / 3rd setup of the day, one at a time)")),
    ("wait", ({"wait": 12, "cisd1m": 44}, "limit not tapped in 30 min or no 1m CISD in 22 bars (window doubled)")),
    ("window", ({"window": [[0, 955]]}, "outside the 02:00-15:30 entry window (00:00-02:00 and 15:30-15:55)")),
    ("min_rr", ({"min_rr": 1.0}, "target under 1.5R (1.0-1.5R)")),
    ("stop", ({"min_stop": 4.0, "max_stop": 120.0}, "stop under 8 or over 80 pts")),
    ("monday", ({"monday": False}, "blocked by the Monday rule")),
])


def missed():
    c = E.ctx()
    base = [t for t in c["T"]]
    bk = {key_of(t) for t in base}
    out = {}
    for nm, (ov, desc) in MISSED.items():
        T = F.run({**LIVE, **ov})
        new = [t for t in T if key_of(t) not in bk]
        gone = [t for t in base if key_of(t) not in {key_of(x) for x in T}]
        o = {"desc": desc, "override": ov}
        for sp in ("H1", "H2", "REF"):
            nn = [t for t in new if span_of(t["day"]) == sp]
            gg = [t for t in gone if span_of(t["day"]) == sp]
            o[sp] = {"new": rstats([t["r"] for t in nn]), "new_usd": round(sum(t["pnl"] for t in nn)),
                     "new_exits": dict(collections.Counter(t["exit"] for t in nn)),
                     "displaced": len(gg), "displaced_usd": round(sum(t["pnl"] for t in gg))}
        out[nm] = o
        print(nm, desc)
        for sp in ("H1", "H2", "REF"):
            print("   ", sp, o[sp])
    json.dump(out, open(OUT_M, "w"), indent=1, default=float)
    return out


# ================================================================================================ structural skip rules
def cand_feats(M, z):
    """Facts of a candidate at its trigger bar (closed bars only), as the executor will plan it (direction space)."""
    x = M.ctx[z["k"]]
    vm = float(x.get("vix_move") or np.nan)
    ep = min(float(z["ref_d"]), z["trig_c"])
    risk = ep - (z["ext_d"] - LIVE["stop_buf"])
    band = float(x["open18"]) * z["dir"] + vm - ep
    tp = min(band, LIVE["max_rr"] * risk) if risk > 0 else np.nan
    sh = z["entry_d"] - ep
    obs = [dd + sh for cl, v in (z.get("targets") or {}).items() for dd in v if dd + sh > 0]
    s, i = int(x["s"]), int(z["i"])
    rng = float(M.h[s:i + 1].max() - M.l[s:i + 1].min()) if i >= s else np.nan
    return {"tgt_pts": tp, "tgt_vix": tp / vm, "rr": tp / risk if risk > 0 else np.nan, "stop_vix": risk / vm,
            "stop_atr": risk / z["atr"] if z.get("atr") else np.nan, "dayrng_vix": rng / vm,
            "obst_r": (min(obs) / risk) if obs and risk > 0 else 99.0, "depth_atr": float(z["depth_atr"]), "disp": float(z["disp"])}


_CF = {}


def all_cands():
    if not _CF:
        M, C = F.market(LIVE["ref"], LIVE["extra_boxes"])
        _CF["M"], _CF["C"] = M, C
        _CF["f"] = {(z["day"], int(z["i"]), int(z["dir"])): cand_feats(M, z) for z in C}
    return _CF


def h1_q(key, q):
    """Cut point from the live Jan-Jun 2026 trades only (the pick half)."""
    cf = all_cands()["f"]
    v = [cf[key_of(t)][key] for t in E.ctx()["T"] if H1[0] <= t["day"] <= H1[1]]
    v = np.array([a for a in v if a == a], float)
    return float(np.quantile(v, q))


def rules():
    """name -> (predicate on candidate facts = SKIP, plain words, hypothesis). Written from the Jan-Jun 2026 diagnosis
    (deep_diag.json: the worst Jan-Jun tercile of each structural fact); each at the H1 tercile (q67 / q33) and a milder cut
    (q80 / q20). All are counted as tests."""
    V = collections.OrderedDict()
    for q, tag in ((2 / 3, "t"), (0.8, "m")):
        a = h1_q("tgt_pts", q)
        V[f"far_tgt_{tag}"] = (lambda f, a=a: f["tgt_pts"] > a, f"skip a target farther than {a:.0f} pts", "a far target rarely gets hit; the day stays free")
        a = h1_q("tgt_vix", q)
        V[f"tgt_vix_{tag}"] = (lambda f, a=a: f["tgt_vix"] > a, f"skip a target farther than {a:.2f} VIX day-moves from the entry", "needs a whole day's move")
        a = h1_q("dayrng_vix", q)
        V[f"day_ext_{tag}"] = (lambda f, a=a: f["dayrng_vix"] > a, f"skip once the day's range so far is > {a:.2f} VIX day-moves", "the day's move is spent")
        a = h1_q("stop_vix", q)
        V[f"stop_vix_{tag}"] = (lambda f, a=a: f["stop_vix"] > a, f"skip a stop wider than {a:.3f} VIX day-moves", "a wide stop vs the day's move = low R quality")
        a = h1_q("stop_atr", q)
        V[f"stop_atr_{tag}"] = (lambda f, a=a: f["stop_atr"] > a, f"skip a stop wider than {a:.2f} x 5m ATR", "re-check of the wide-stop side")
        b = h1_q("obst_r", 1 - q)
        V[f"obst_{tag}"] = (lambda f, b=b: f["obst_r"] < b, f"skip when an opposing level sits within {b:.2f}R", "blocked path")
        b = h1_q("rr", 1 - q)
        V[f"low_rr_{tag}"] = (lambda f, b=b: f["rr"] < b, f"skip a target under {b:.2f}R", "low payoff")
        a1, a2 = h1_q("depth_atr", q), h1_q("disp", q)
        V[f"breakout_{tag}"] = (lambda f, a1=a1, a2=a2: f["depth_atr"] > a1 and f["disp"] > a2,
                                f"skip a sweep deeper than {a1:.2f} ATR with a displacement over {a2:.2f} ATR", "deep run + big candle = a breakout, not a trap")
    return V


def skip_trades(pred):
    cf = all_cands()["f"]
    sk = [list(k) for k, f in cf.items() if pred(f)]
    return F.run({**LIVE, "skip_keys": sk}), len(sk)


def grid():
    t0 = time.time()
    res = json.load(open(OUT)) if os.path.exists(OUT) else {}
    E.ctx()
    base, U0, L0 = E.evaluate({}, fund=True)
    bs = E.short(base)
    res["base"] = bs
    res["_cfg"] = {"room_f": ROOM, "two_week_until": UNTIL}
    print(E.line("base", bs), flush=True)
    for nm, (pred, desc, hyp) in rules().items():
        T, nsk = skip_trades(pred)
        N.run_variant(res, "skip", nm, bs, L0, T=T, info={"desc": desc, "hyp": hyp, "skipped_cands": nsk,
                                                          "n_trades": {sp: sum(1 for t in T if SPANS[sp][0] <= t["day"] <= SPANS[sp][1]) for sp in SPANS}})
        json.dump(res, open(OUT, "w"), indent=1, default=float)
    print(f"done in {time.time() - t0:.0f}s", flush=True)


def explain():
    """Per skip rule: the base trades it removes and the later setups that take their day (R at the LIT size), + the
    H1 -> H2 money decomposition (trades a month x $ a trade = R a trade x $ per R)."""
    c = E.ctx()
    base = c["T"]
    bk = {key_of(t): t for t in base}
    out = {}
    for nm, (pred, desc, hyp) in rules().items():
        T, _ = skip_trades(pred)
        tk = {key_of(t) for t in T}
        o = {}
        for sp in ("H1", "H2", "REF"):
            rm = [t for t in base if span_of(t["day"]) == sp and key_of(t) not in tk]
            ad = [t for t in T if span_of(t["day"]) == sp and key_of(t) not in bk]
            o[sp] = {"removed": rstats([t["r"] for t in rm]), "removed_usd": round(sum(t["pnl"] for t in rm)),
                     "added": rstats([t["r"] for t in ad]), "added_usd": round(sum(t["pnl"] for t in ad))}
        out[nm] = o
        print(f"{nm:14s} " + " | ".join(f"{sp} removed n{o[sp]['removed']['n']} {o[sp]['removed'].get('mean_r', 0):+.2f}R ${o[sp]['removed_usd']:+,} "
                                         f"added n{o[sp]['added']['n']} {o[sp]['added'].get('mean_r', 0):+.2f}R ${o[sp]['added_usd']:+,}" for sp in ("H1", "H2")))
    dec = {}
    for sp, (a, z) in (("H1", ("2026-01-01", "2026-06-30")), ("H2", ("2026-07-01", "2026-10-16"))):
        X = [t for t in base if a <= t["day"] <= z]
        ns = sum(1 for d in F.SESS if a <= d <= z)
        mo = ns / 21.0
        usd = sum(t["pnl"] for t in X)
        rr = [t["r"] for t in X]
        per_r = float(np.mean([t["pnl"] / t["r"] for t in X if abs(t["r"]) > 0.5]))
        dec[sp] = {"trades": len(X), "sessions": ns, "trades_mo": round(len(X) / mo, 2), "usd_trade": round(usd / len(X)),
                   "r_trade": round(float(np.mean(rr)), 3), "usd_per_r": round(per_r), "stop_pts": round(float(np.mean([t["risk_pts"] for t in X])), 1),
                   "micros": round(float(np.mean([t["qty"] for t in X])), 1), "usd": round(usd)}
        print(sp, dec[sp])
    out["_decomp"] = dec
    json.dump(out, open(os.path.join(ROOT, "research", "lit", "deep_explain.json"), "w"), indent=1, default=float)


def cells(min_h1=6, min_h2=3, n_boot=2000, seed=7):
    """Two-fact loser cells: every pair of facts (Jan-Jun terciles), the cells with n >= min_h1 Jan-Jun trades and a NEGATIVE
    mean R there (= a skip rule a data-miner would pick); how many stay negative in Jul-Oct, vs random Jul-Oct subsets of the
    same size (the chance rate). Answers: do losers share a structure that carries over?"""
    D = json.load(open(OUT_D))
    rows = D["rows"]
    h1 = [r for r in rows if r["sp"] == "H1"]
    h2 = [r for r in rows if r["sp"] == "H2"]
    keys = [k for k in NUM if sum(1 for r in h1 if r.get(k) is not None and r[k] == r[k]) >= 60]
    cut = {k: np.quantile([float(r[k]) for r in h1 if r.get(k) is not None and r[k] == r[k]], [1 / 3, 2 / 3]) for k in keys}

    def b(r, k):
        v = r.get(k)
        if v is None or v != v:
            return None
        return int(np.searchsorted(cut[k], float(v), side="left"))
    picked = []
    for a_ in range(len(keys)):
        for b_ in range(a_ + 1, len(keys)):
            ka, kb = keys[a_], keys[b_]
            for i in range(3):
                for j in range(3):
                    X1 = [r["r"] for r in h1 if b(r, ka) == i and b(r, kb) == j]
                    if len(X1) < min_h1 or np.mean(X1) >= 0:
                        continue
                    X2 = [r["r"] for r in h2 if b(r, ka) == i and b(r, kb) == j]
                    if len(X2) < min_h2:
                        continue
                    picked.append({"a": ka, "ia": i, "b": kb, "ib": j, "n1": len(X1), "r1": round(float(np.mean(X1)), 3),
                                   "n2": len(X2), "r2": round(float(np.mean(X2)), 3), "usd2": None})
    rng = np.random.default_rng(seed)
    R2 = np.array([r["r"] for r in h2])
    neg2 = sum(1 for p in picked if p["r2"] < 0)
    exp = 0.0
    for p in picked:
        sims = np.array([R2[rng.choice(len(R2), p["n2"], replace=False)].mean() for _ in range(200)])
        exp += float((sims < 0).mean())
    o = {"pairs": len(keys) * (len(keys) - 1) // 2, "cells_tested": 9 * len(keys) * (len(keys) - 1) // 2, "h1_loser_cells": len(picked),
         "still_negative_h2": neg2, "chance_expected": round(exp, 1),
         "best": sorted(picked, key=lambda p: p["r2"])[:10], "worst_carry": sorted(picked, key=lambda p: -p["r2"])[:5]}
    print({k: v for k, v in o.items() if k not in ("best", "worst_carry")})
    for p in o["best"]:
        print("  ", p)
    json.dump(o, open(os.path.join(ROOT, "research", "lit", "deep_cells.json"), "w"), indent=1, default=float)
    return o


def save():
    """Store the base and the tercile version of every skip rule (rl.save runs lit_deep_*)."""
    from tools import runlib as rl
    res = json.load(open(OUT))
    R_ = rules()
    for k in ["base"] + [f"skip:{n}" for n in R_ if n.endswith("_t")]:
        s = res[k]
        T = E.ctx()["T"] if k == "base" else skip_trades(R_[k.split(":")[1]][0])[0]
        U = N.trades2({}, T=T)
        L = [{kk: (v.item() if isinstance(v, np.generic) else v) for kk, v in l.items()} for l in E.lit_size(U)]
        S = rl.score(L, F.SESS)
        h = lambda sp: f"PF {s['lit'][sp]['pf']} net {s['lit'][sp]['net']:+,} (${s['lit'][sp]['per_month']:,}/mo) {s['lit'][sp]['tpw']}/wk"
        e = lambda sp: (f"PF {s['eval'][sp]['pf']} net {s['eval'][sp]['net']:+,} 2w {s['eval'][sp]['p10']}/{s['eval'][sp]['f10']} "
                        f"dec10 {s['eval'][sp]['dec10']} p15/f15 {s['eval'][sp]['p15']}/{s['eval'][sp]['f15']} med {s['eval'][sp]['pass_med']}")
        ver = (f"LIT size: H1 {h('H1')}; H2 {h('H2')}; 2021-25 ref {h('2021-25')}. Eval path (two_week room_f {ROOM}, kept to "
               f"session {UNTIL}): H1 {e('H1')}; H2 {e('H2')}. Funded 50K $/mo H1 {s['fund']['H1']['per_month']} / H2 {s['fund']['H2']['per_month']}.")
        rid = "lit_deep_" + k.replace(":", "_")
        rl.save(rid, f"LIT deep edge (2026-11-15): {k}", "other", "Team E-LIT: structural skip rules (day left free) on the live LIT",
                params={"x_deep": k, "desc": (s.get("info") or {}).get("desc")}, trades=L, scored=S,
                status="info" if k == "base" else "rejected", verdict=ver,
                notes="tools/lit_deep.py: engine run_x with live params + skip_keys (a skipped setup leaves the day free); re-walked, LIT size rule; eval two_week room_f 0.4; funded 50K",
                writeup="2026-11-15-lit-deep", tags=["lit", "lit_deep"])
        print("saved", rid, flush=True)


def table():
    """Markdown rows for the write-up."""
    res = json.load(open(OUT))
    b = res["base"]
    for k, s in res.items():
        if k.startswith("_") or "lit" not in s:
            continue
        d = s.get("d_lit", {"H1": 0, "H2": 0, "2021-25": 0})
        de = s.get("d_eval", {"H1": 0, "H2": 0})
        ev = s["eval"]
        print(f"| {k} | {d['H1']:+,} / {d['H2']:+,} / {d['2021-25']:+,} | {de['H1']:+,} / {de['H2']:+,} | "
              f"{ev['H1']['p10']}/{ev['H1']['f10']}, {ev['H2']['p10']}/{ev['H2']['f10']} | {s['lit']['H1']['tpw']} / {s['lit']['H2']['tpw']} | "
              f"{s['fund']['H1']['per_month'] - b['fund']['H1']['per_month']:+} / {s['fund']['H2']['per_month'] - b['fund']['H2']['per_month']:+} | "
              f"{'GATE' if E.gate(s) else 'rejected'} |")
    for sp in ("H1", "H2"):
        L, V = b["lit"][sp], b["eval"][sp]
        print(sp, "LIT", {k: L[k] for k in ("tpw", "wk2", "pf", "net", "per_month", "dd")}, "EVAL",
              {k: V[k] for k in ("pf", "net", "per_month", "dd", "p10", "f10", "dec10", "p15", "f15", "slow_pass", "pass_med")})


def report():
    res = json.load(open(OUT))
    print(E.line("base", res["base"]))
    for k, s in res.items():
        if k.startswith("_") or k == "base" or "d_lit" not in s:
            continue
        ev = s["eval"]
        print(f"{k:24s} dLIT {s['d_lit']['H1']:+7,} {s['d_lit']['H2']:+7,} ref {s['d_lit']['2021-25']:+7,} | dEV {s['d_eval']['H1']:+7,} "
              f"{s['d_eval']['H2']:+7,} | 2w {ev['H1']['p10']}/{ev['H1']['f10']} {ev['H2']['p10']}/{ev['H2']['f10']} | fund "
              f"{tuple(s['d_fund'].values())} | tpw {s['lit']['H1']['tpw']}/{s['lit']['H2']['tpw']} | {'GATE' if E.gate(s) else ''}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "diag"
    {"diag": diag, "missed": missed, "grid": grid, "report": report, "explain": explain, "save": save, "table": table, "cells": cells}[cmd]()
