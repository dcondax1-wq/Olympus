"""ICT / SMC concepts (inducement, PO3/AMD, NQ-ES SMT, smart-money traps) as confluence, sizing weight and entry gate.

    python -X utf8 study_ict_run.py [--src PATH|default] [--from YYYY-MM-DD] [--to YYYY-MM-DD]
                                    [--train0 WEEKS] [--block WEEKS] [--workers 8] [--boot 2000]

--window N     = independent engine runs over N-week windows (each with 21 days warm-up), concatenated.
Runs behind research/ICT_REPORT.md:
    --src default --from 2026-08-06 --to 2026-10-16            -> study_ict_results_11wk.txt
    --src default --from 2021-11-08 --window 10                -> study_ict_results_5y_windowed.txt
    --src <copy of data/clean/NQ_5m.csv>  (one continuous run)  -> study_ict_results_5y_continuous.txt
    --src default --from 2025-04-28 --window 10  (NQ+ES aligned) -> study_ict_results_smt_18mo.txt
--src default  = exactly the data engine.backtest.run uses (data/NQ_5m.csv + NQ_1h warm-up, ES partner).
--src omitted  = data/clean/NQ_5m.csv if it exists, else a temp merge of data/tv_exports/NQ1_5m_chunk_*.csv (+ NQ_5m.csv).
Nothing in engine/ is changed: features come from engine/ict_features.py inside a subclass (study_ict_common.ICTEngine).

Samples
  A  taken trades, default config (flat research sizing: grade x $350, dd_aware off, no daily stop)
  C  shadow candidates of the wide run (max_trades_day 9, stop_after_win off): every valid setup, resolved at stop /
     target / flat, in R (no BE / giveback / time stop)
Uses
  (a) confluence: mean R with vs without the feature (A and C), week-block bootstrap CI
  (b) sizing: risk x (1 + w) with the feature, x (1 - w) without, re-sized exactly like engine._size; w picked
      walk-forward on the training weeks from {-0.5, -0.25, 0, +0.25, +0.5}
  (c) gate: real engine re-runs with the feature required / vetoed / +1 score / -1 score when absent; walk-forward picks
      per concept on the training weeks (2.0-4.5 trades/wk required in training), scored on the next block
"""
from __future__ import annotations

import argparse
import json
from multiprocessing import Pool

import numpy as np

import study_ict_common as C
from engine import ict_features as I

FEATS = I.BINARY + ["smt"]          # "smt" = the engine's existing SMT feature (Engine._smt), for comparison
CONCEPT = {**I.CONCEPT, "smt": "smt"}
MODES = ("require", "veto", "plus", "minus")
GR = [(7, 1.5), (5, 1.25), (3, 1.0), (1, 0.75), (-99, 0.5)]      # Engine.GRADES
GS = (-2, -1, 0, 1, 2)


def gmult(pts):
    return next(m for th, m in GR if pts >= th)
WS = (-0.5, -0.25, 0.0, 0.25, 0.5)
LO, HI = 2.0, 4.5


def _job(job):
    name, params, ict, src, a, z, win = job
    return name, C.run(params, src, a, z, ict, win)


def stats_tr(tr, ndays):
    if not tr:
        return {"n": 0, "tpw": 0.0, "avg_r": 0.0, "net": 0.0, "pf": 0.0, "dd": 0.0, "wr": 0.0}
    pnl = np.array([t["pnl"] for t in tr])
    g, l = pnl[pnl > 0].sum(), -pnl[pnl < 0].sum()
    eq = np.cumsum(pnl)
    dd = float((eq - np.maximum.accumulate(np.r_[0.0, eq])[1:]).min())
    return {"n": len(tr), "tpw": len(tr) / max(ndays / 5, 1e-9), "avg_r": float(np.mean([t["pnl_r"] for t in tr])),
            "net": float(pnl.sum()), "pf": float(g / l) if l > 0 else 99.0, "dd": dd, "wr": float((pnl > 0).mean())}


def fs(m):
    return f"{m['n']} / {m['tpw']:.1f} / {m['avg_r']:+.2f}R / ${m['net']:+,.0f} / PF {m['pf']:.2f} / DD {m['dd']:,.0f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=None)
    ap.add_argument("--from", dest="a", default=None)
    ap.add_argument("--to", dest="z", default=None)
    ap.add_argument("--train0", type=int, default=None)
    ap.add_argument("--block", type=int, default=None)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--boot", type=int, default=2000)
    ap.add_argument("--dump", default=None)
    ap.add_argument("--window", type=int, default=0, help="independent engine runs over N-week windows (0 = one run)")
    args = ap.parse_args()
    src = args.src if args.src == "default" else (args.src or C.merged_source())
    a = args.a
    if a is None:
        b = C.load("NQ", "5m") if src == "default" else C.bars_from(src)
        a = b.date_str[0] if src == "default" else C.warm_from(b.date_str[0], -21)
    print(f"source: {src}\nrange: {a} .. {args.z or 'end'}   engine windows: {args.window or 'one continuous run'} wk")

    jobs = [("base", {}, None, src, a, args.z, args.window), ("wide", C.WIDE, None, src, a, args.z, args.window)]
    for f in FEATS:
        for m in MODES:
            jobs.append((f"{f}|{m}", {}, {"feat": f, "mode": m, "w": 1}, src, a, args.z, args.window))
    with Pool(args.workers) as pool:
        R = dict(pool.map(_job, jobs))
    base, wide = R["base"], R["wide"]
    days = base["days"]
    weeks = sorted({C.week(d) for d in days})
    nw = len(weeks)
    train0 = args.train0 or (4 if nw <= 16 else 13)
    block = args.block or (2 if nw <= 16 else 4)
    FOLDS = C.folds(weeks, train0, block)
    days_in = lambda wk: [d for d in days if C.week(d) in wk]
    B = args.boot
    print(f"sessions {len(days)}, weeks {nw}, folds {len(FOLDS)} (train0 {train0} wk, block {block} wk)")

    iv = lambda v: None if v is None else int(bool(v))       # undefined (no partner bars) stays None, never "0"
    A = [dict(t, wk=C.week(t["day"]), r=t["pnl_r"], **{k: iv(t["features"].get(k)) for k in FEATS}) for t in base["trades"]]
    S = [dict(s, wk=C.week(s["day"]), **{k: iv(s["f"].get(k)) for k in FEATS}) for s in wide["shadows"] if s.get("r") is not None]
    for x in A + S:
        x["eng_smt"] = (x.get("features") or x.get("f"))["smt"]
    print(f"\nBASELINE A: {fs(stats_tr(base['trades'], len(days)))}")
    print(f"shadow sample C: {len(S)} candidates, mean R {np.mean([s['r'] for s in S]):+.3f}")
    # frequency of the baseline per test block
    bt = []
    for tr_w, te_w in FOLDS:
        nd = len(days_in(te_w))
        bt.append(len([t for t in A if t["wk"] in te_w]) / max(nd / 5, 1e-9))
    print("baseline trades/wk per test block: " + " ".join(f"{x:.1f}" for x in bt))

    def defined(rows, f):
        """Rows where feature f is defined (SMT features need partner bars; the engine smt is compared on ES-5m days)."""
        key = "ict_smt" if f in ("smt", "eng_smt", "ict_smt") else f
        return [x for x in rows if (x.get("features") or x.get("f")).get(key) is not None]

    # ------------------------------------------------------------------ (a) confluence
    print("\n## (a) Confluence: mean R with vs without (90% week-block CI, p+ = P(diff > 0))")
    print("| feature | C n with/without | C R with / without | C diff (CI) | A n with | A R with / without | A diff (CI) | A diff by fold (sign) |")
    print("|---|---|---|---|---|---|---|---|")
    out_a = {}
    for f in I.BINARY + ["eng_smt"]:
        Sx, Ax = defined(S, f), defined(A, f)
        cw = [s["r"] for s in Sx if s.get(f) == 1]; cn = [s["r"] for s in Sx if s.get(f) == 0]
        aw = [t["r"] for t in Ax if t.get(f) == 1]; an = [t["r"] for t in Ax if t.get(f) == 0]
        cd = C.boot(Sx, C.diff_mean(f), n=B)
        ad = C.boot(Ax, C.diff_mean(f), n=B)
        signs = []
        for tr_w, te_w in FOLDS:
            v = C.diff_mean(f)([t for t in Ax if t["wk"] in te_w])
            signs.append("." if np.isnan(v) else ("+" if v > 0 else "-"))
        out_a[f] = {"c": cd, "a": ad}
        mean = lambda v: f"{np.mean(v):+.2f}" if v else "-"
        print(f"| {f} | {len(cw)}/{len(cn)} | {mean(cw)} / {mean(cn)} | {C.fmt_ci(cd)} | {len(aw)} | {mean(aw)} / {mean(an)} | "
              f"{C.fmt_ci(ad)} | {''.join(signs)} |")

    # ------------------------------------------------------------------ (b) sizing
    print("\n## (b) Sizing weight on taken trades: risk x (1+w) with, x (1-w) without")
    print("| feature | best fixed w (in-sample) | $ lift at w=+0.5 (CI) | $ lift at w=-0.5 (CI) | R-normalised lift w=+0.5 (CI) | WF picks | WF OOS $ lift (CI) |")
    print("|---|---|---|---|---|---|---|")
    out_b = {}
    for f in FEATS:
        Ax = defined(A, f)
        if not Ax:
            continue
        def lift_items(w, items):
            return [{"wk": t["wk"], "d": C.resize(t, 1 + w * (1 if t[f] else -1)) - t["pnl"]} for t in items]
        sumd = lambda its: float(sum(x["d"] for x in its))
        full = {w: sumd(lift_items(w, Ax)) for w in WS}
        bw = max(full, key=full.get)
        lp = C.boot(lift_items(0.5, Ax), sumd, n=B)
        lm = C.boot(lift_items(-0.5, Ax), sumd, n=B)
        def rnorm(items, w=0.5):
            if not items:
                return np.nan
            m = np.array([1 + w * (1 if t[f] else -1) for t in items]); r = np.array([t["r"] for t in items])
            return float((m / m.mean() * r).sum() - r.sum())
        rn = C.boot(Ax, rnorm, n=B)
        picks, oos = [], []
        for tr_w, te_w in FOLDS:
            trn = [t for t in Ax if t["wk"] in tr_w]
            sc = {w: sumd(lift_items(w, trn)) for w in WS}
            w = max(sc, key=lambda k: (round(sc[k], 2), -abs(k)))
            picks.append(w)
            oos += lift_items(w, [t for t in Ax if t["wk"] in te_w])
        wf = C.boot(oos, sumd, n=B) if oos else (0.0, None, None, None)
        out_b[f] = {"full": full, "wf": wf, "picks": picks}
        drop = sum(1 for t in Ax if C.resize(t, 1 + 0.5 * (1 if t[f] else -1)) == 0.0) + \
            sum(1 for t in Ax if C.resize(t, 1 - 0.5 * (1 if t[f] else -1)) == 0.0)
        print(f"| {f} | {bw:+.2f} (${full[bw]:+,.0f}) | {C.fmt_ci(lp, 0)} | {C.fmt_ci(lm, 0)} | {C.fmt_ci(rn)} | "
              f"{' '.join(f'{w:+.2f}' for w in picks)} | {C.fmt_ci(wf, 0)} |" + (f" ({drop} trades round to 0 micros at w=+-0.5)" if drop else ""))

    # ------------------------------------------------------------------ (b2) grade-points weight (the engine's own lever)
    print("\n## (b2) Grade item: grade_points + g when the feature is present, grade -> size re-mapped (A+ 1.5 .. D 0.5)")
    print("| feature | $ lift g=-2 / -1 / +1 / +2 | g=-1 lift (CI) | WF picks (count) | WF OOS $ lift (CI) | OOS lift by year | OOS trades dropped (0 micros) |")
    print("|---|---|---|---|---|---|---|")
    from collections import Counter
    def g_items(g, items, f):
        return [{"wk": t["wk"], "day": t["day"], "d": C.resize(t, gmult(t["grade_points"] + g * t[f]) / t["grade_mult"]) - t["pnl"],
                 "drop": int(C.resize(t, gmult(t["grade_points"] + g * t[f]) / t["grade_mult"]) == 0.0 and g * t[f] != 0)}
                for t in items]
    for f in FEATS:
        Ax = defined(A, f)
        if not Ax:
            continue
        sumd = lambda its: float(sum(x["d"] for x in its))
        full = {g: sumd(g_items(g, Ax, f)) for g in GS}
        l1 = C.boot(g_items(-1, Ax, f), sumd, n=B)
        picks, oos = [], []
        for tr_w, te_w in FOLDS:
            trn = [t for t in Ax if t["wk"] in tr_w]
            sc = {g: sumd(g_items(g, trn, f)) for g in GS}
            g = max(sc, key=lambda k: (round(sc[k], 2), -abs(k)))
            picks.append(g)
            oos += g_items(g, [t for t in Ax if t["wk"] in te_w], f)
        wf = C.boot(oos, sumd, n=B) if oos else (0.0, None, None, None)
        yrs = {}
        for x in oos:
            yrs[x["day"][:4]] = yrs.get(x["day"][:4], 0) + x["d"]
        pc = Counter(picks)
        drops = sum(x["drop"] for x in oos)
        print(f"| {f} | {' / '.join(f'{full[g]:+,.0f}' for g in (-2, -1, 1, 2))} | {C.fmt_ci(l1, 0)} | "
              f"{', '.join(f'{k:+d} x{v}' for k, v in sorted(pc.items()))} | {C.fmt_ci(wf, 0)} | "
              f"{' '.join(f'{y}: {v:+,.0f}' for y, v in sorted(yrs.items()))} | {drops} |")

    # ------------------------------------------------------------------ (b3) honest pooled selection over ALL grade items
    print("\n## (b3) Walk-forward choice among ALL (feature, g) grade items + 'none' (the realistic 'pick an ICT item' test)")
    allf = [f for f in FEATS if f not in ("smt", "ict_smt", "ict_smt1h")]
    picks, oos = [], []
    sumd = lambda its: float(sum(x["d"] for x in its))
    for tr_w, te_w in FOLDS:
        trn = [t for t in A if t["wk"] in tr_w]
        best, bv = ("none", 0), 0.0
        for f in allf:
            for g in GS:
                if g == 0:
                    continue
                v = sumd(g_items(g, trn, f))
                if v > bv + 1e-6:
                    best, bv = (f, g), v
        picks.append(best)
        te = [t for t in A if t["wk"] in te_w]
        oos += g_items(best[1], te, best[0]) if best[0] != "none" else [{"wk": t["wk"], "day": t["day"], "d": 0.0, "drop": 0} for t in te]
    pc = Counter(picks)
    yrs = {}
    for x in oos:
        yrs[x["day"][:4]] = yrs.get(x["day"][:4], 0) + x["d"]
    print(f"picks: {', '.join(f'{k[0]} {k[1]:+d} x{v}' for k, v in pc.most_common())}")
    print(f"OOS $ lift: {C.fmt_ci(C.boot(oos, sumd, n=B), 0)}; by year: {' '.join(f'{y}: {v:+,.0f}' for y, v in sorted(yrs.items()))}")

    # ------------------------------------------------------------------ (a2) stability by calendar year
    yrs = sorted({t["day"][:4] for t in A})
    if len(yrs) > 1:
        print("\n## (a2) Mean-R difference (with - without) by calendar year: C shadows | A taken  (n with in brackets)")
        print("| feature | " + " | ".join(f"{y} C | {y} A" for y in yrs) + " |")
        print("|---|" + "---|" * (2 * len(yrs)))
        for f in I.BINARY:
            cells = []
            for y in yrs:
                for rows in (S, A):
                    ry = [x for x in rows if x["day"][:4] == y]
                    v = C.diff_mean(f)(ry)
                    nw_ = sum(1 for x in ry if x.get(f) == 1)
                    cells.append("-" if np.isnan(v) else f"{v:+.2f} ({nw_})")
            print(f"| {f} | " + " | ".join(cells) + " |")

    # ------------------------------------------------------------------ (c) gates (real engine re-runs)
    print("\n## (c) Entry gate / score change (real engine runs). Cells: n / trades per wk / avg R / net / PF / DD")
    bweek = {}
    for t in base["trades"]:
        bweek[C.week(t["day"])] = bweek.get(C.week(t["day"]), 0) + t["pnl"]
    def weekly(res):
        w = {}
        for t in res["trades"]:
            w[C.week(t["day"])] = w.get(C.week(t["day"]), 0) + t["pnl"]
        return w
    def block_tpw(res, wk):
        nd = len(days_in(wk))
        return len([t for t in res["trades"] if C.week(t["day"]) in wk]) / max(nd / 5, 1e-9)
    print("| variant | full sample | min..max trades/wk over test blocks | blocks outside 2.0-4.5 | $ lift vs base (CI) |")
    print("|---|---|---|---|---|")
    out_c = {}
    for name in ["base"] + [n for n in R if "|" in n]:
        res = R[name]
        m = stats_tr(res["trades"], len(days))
        tp = [block_tpw(res, te) for _, te in FOLDS]
        wv = weekly(res)
        items = [{"wk": k, "d": wv.get(k, 0) - bweek.get(k, 0)} for k in weeks]
        lift = C.boot(items, lambda its: float(sum(x["d"] for x in its)), n=B) if name != "base" else (0.0, None, None, None)
        bad = sum(1 for x in tp if not LO <= x <= HI)
        out_c[name] = {"m": m, "tp": tp, "lift": lift, "bad": bad}
        if name == "base" or m["n"] != stats_tr(base["trades"], len(days))["n"] or abs(m["net"] - out_c["base"]["m"]["net"]) > 1:
            print(f"| {name} | {fs(m)} | {min(tp):.1f}..{max(tp):.1f} | {bad}/{len(tp)} | {C.fmt_ci(lift, 0)} |")
        else:
            print(f"| {name} | identical to base | | | 0 |")

    print("\n## (c) Walk-forward gate selection per concept (train: 2.0-4.5 trades/wk, best train $; test next block)")
    print("| concept | picks per fold | OOS trades/wk per block | OOS $ (base OOS $) | OOS lift $ (CI) |")
    print("|---|---|---|---|---|")
    for concept in ("inducement", "po3", "smt", "trap", "all"):
        cands = ["base"] + [n for n in R if "|" in n and (concept == "all" or CONCEPT[n.split("|")[0]] == concept)]
        picks, items, tpws, oos_net, base_net = [], [], [], 0.0, 0.0
        for tr_w, te_w in FOLDS:
            best, bv = "base", None
            for nme in cands:
                res = R[nme]
                tr = [t for t in res["trades"] if C.week(t["day"]) in tr_w]
                nd = len(days_in(tr_w))
                tpw = len(tr) / max(nd / 5, 1e-9)
                if not LO <= tpw <= HI:
                    continue
                v = sum(t["pnl"] for t in tr)
                if bv is None or v > bv + 1e-6:
                    best, bv = nme, v
            picks.append(best)
            res = R[best]
            wv = weekly(res)
            items += [{"wk": k, "d": wv.get(k, 0) - bweek.get(k, 0)} for k in te_w]
            tpws.append(block_tpw(res, te_w))
            oos_net += sum(wv.get(k, 0) for k in te_w); base_net += sum(bweek.get(k, 0) for k in te_w)
        lift = C.boot(items, lambda its: float(sum(x["d"] for x in its)), n=B)
        from collections import Counter
        pc = Counter(picks)
        print(f"| {concept} | {', '.join(f'{k} x{v}' for k, v in pc.most_common())} | {' '.join(f'{x:.1f}' for x in tpws)} | "
              f"${oos_net:+,.0f} (${base_net:+,.0f}) | {C.fmt_ci(lift, 0)} |")

    # ------------------------------------------------------------------ SMT: ours vs the engine's
    Sx = [s for s in S if s["f"].get("ict_smt") is not None]
    Ax = [t for t in A if t["features"].get("ict_smt") is not None]
    if Sx:
        print("\n## SMT: swing-anchored ict_smt vs engine `smt` (where ES bars exist)")
        for lab, rows in (("C shadows", Sx), ("A taken", Ax)):
            tab = {}
            for x in rows:
                k = (x["eng_smt"], x["ict_smt"])
                tab.setdefault(k, []).append(x["r"])
            print(f"{lab}: " + "; ".join(f"engine {k[0]} / ict {k[1]}: n {len(v)}, R {np.mean(v):+.2f}" for k, v in sorted(tab.items())))
    if args.dump:
        with open(args.dump, "w") as fh:
            json.dump({"a": out_a, "b": out_b, "c": {k: {kk: vv for kk, vv in v.items()} for k, v in out_c.items()}}, fh, default=str)


if __name__ == "__main__":
    main()
