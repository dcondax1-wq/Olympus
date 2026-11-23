"""Re-test EVERY rejected idea under the owner's alternative standards (2026-11-23). PAPER RESEARCH ONLY: reads stored
runs + regenerated cells, writes research/retest/*.json; never touches live_model*.json or any engine file.

Stage 1 (this file): rolling walk-forward on daily $ (costs in, futures bars only).
  * family = one study (runs grouped by write-up) or one regenerated hunt family (tools/retest/regen.py).
  * a LIT / ATLAS / BLITZ modification family is scored as its DAILY DELTA vs its own study's base run (base found by
    correlation among the study's base-like runs + the repo's baseline runs); a stand-alone family vs cash.
  * every month M from 2022-05: fit = the 6 months before M, pick the variant (or "no change") with the most $ in the
    fit, record its $ in M (never seen when picking). The stitched months are the out-of-sample (OOS) result.
  * test: one-sided t on the OOS monthly $ (H0 mean <= 0); Bonferroni over ALL families tested: p < 0.05 / N.
    python -X utf8 tools/retest/retest.py wf
"""
import collections, glob, json, math, os, re, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
RUNS = os.path.join(ROOT, "research", "runs"); OUT = os.path.join(ROOT, "research", "retest")
FIT, FIRST_TEST = int(os.environ.get("RETEST_FIT", 6)), "2022-05"
END = "2026-10-16"
GLOBAL_BASES = ["baseline", "live_2026-10-17am", "lit_live", "lit_live_2026-10-18", "lit_s2_base", "lit_deep_base",
                "lit_edge_base", "atlas_base", "atx_today", "atlas_deep_today", "atlas_v2_base", "sb_robust_base",
                "blitz_2026_backtest", "sn_blitz_today", "blitz25k_today_acct_c"]
BASE_RX = re.compile(r"(^baseline$|_base$|_base_|today|_live$|_live_|_ref$|^lit_live|control|_off$)")
# write-ups the owner excluded (kalshi) / pure account-mechanics studies with no strategy idea are still kept; kalshi has no runs.


def load_runs():
    R = {}
    for p in glob.glob(os.path.join(RUNS, "*.json")):
        nm = os.path.basename(p)[:-5]
        if nm == "index":
            continue
        try:
            d = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        if not d.get("days"):
            continue
        dc = d.get("day_cols") or ["date", "pnl"]
        i0, i1 = dc.index("date"), dc.index("pnl")
        R[nm] = {"id": nm, "grp": d.get("writeup") or d.get("family") or "other", "status": d.get("status"),
                 "title": d.get("title"), "tags": d.get("tags") or [],
                 "days": {r[i0]: float(r[i1] or 0.0) for r in d["days"] if r[i0] <= END},
                 "n": sum(1 for r in d["days"] if (r[dc.index("trades")] if "trades" in dc else 0))}
    return R


def load_cells():
    C = {}
    for p in glob.glob(os.path.join(OUT, "cells_*.json")):
        for cid, rows in json.load(open(p)).items():
            src, fam, nm = cid.split(":", 2)
            dd = collections.defaultdict(float)
            for r in rows:
                if r[0] <= END:
                    dd[r[0]] += r[7]
            C[cid] = {"id": cid, "grp": f"{src}:{fam}", "days": dict(dd), "n": len(rows), "status": "rejected", "title": nm,
                      "legal": fam != "overnight"}
    return C


def sessions(R):
    return sorted(R["baseline"]["days"])


def vec(run, S):
    d = run["days"]
    return np.array([d.get(s, 0.0) for s in S])


def pick_base(members, R, S):
    cands = [m for m in members if BASE_RX.search(m["id"]) or m["status"] == "baseline"] + [R[g] for g in GLOBAL_BASES if g in R]
    best, bc = None, -1.0
    V = [vec(m, S) for m in members]
    for c in cands:
        cv = vec(c, S)
        if cv.std() == 0:
            continue
        cs = [float(np.corrcoef(cv, v)[0, 1]) for v, m in zip(V, members) if v.std() > 0 and m["id"] != c["id"]]
        if not cs:
            continue
        mc = float(np.median(cs))
        if mc > bc:
            best, bc = c, mc
    return (best, bc) if bc >= 0.5 else (None, bc)


def months_of(S):
    return sorted({s[:7] for s in S})


def walk_forward(variants, base_vec, S):
    """variants: {id: vec}. Returns OOS monthly $ (delta vs base, or vs cash) + the picks."""
    M = months_of(S)
    mix = {m: np.array([s[:7] == m for s in S]) for m in M}
    ids = ["(no change)"] + list(variants)
    D = np.vstack([np.zeros(len(S))] + [v - base_vec for v in variants.values()])
    Mo = np.vstack([D[:, mix[m]].sum(1) for m in M]).T            # ids x months
    out, picks = [], []
    for i, m in enumerate(M):
        if m < FIRST_TEST or i < FIT:
            continue
        fit = Mo[:, i - FIT:i].sum(1)
        k = int(np.argmax(fit)) if fit.max() > 0 else 0
        out.append((m, float(Mo[k, i])))
        picks.append(ids[k])
    return out, picks


def tstat(x):
    x = np.asarray(x, float)
    if len(x) < 3 or x.std(ddof=1) == 0:
        return 0.0, 1.0
    t = x.mean() / (x.std(ddof=1) / math.sqrt(len(x)))
    from math import erf
    # one-sided p from Student t via a normal approx with df correction (n >= 40 months here)
    df = len(x) - 1
    z = t * (1 - 1 / (4 * df)) / math.sqrt(1 + t * t / (2 * df))
    return float(t), float(0.5 * (1 - erf(z / math.sqrt(2))))


def span_mean(oos, a, z):
    v = [x for m, x in oos if a <= m <= z]
    return round(float(np.mean(v)), 1) if v else None


KEEP = {"rejected", "promising"}       # thrown-out ideas (promising = paper leads never adopted); info / baseline / adopt-candidate excluded


def base_for(m, cands, S):
    """the base run most correlated with this variant (>= 0.3 = a modification of it), else None = a stand-alone stream."""
    v = vec(m, S)
    if v.std() == 0:
        return None, 0.0
    best, bc = None, -1.0
    for c in cands:
        if c["id"] == m["id"]:
            continue
        cv = c.get("_v")
        if cv is None:
            cv = c["_v"] = vec(c, S)
        if cv.std() == 0:
            continue
        r = float(np.corrcoef(cv, v)[0, 1])
        if r > bc:
            best, bc = c, r
    return (best, bc) if bc >= 0.3 else (None, bc)


def scale_k(v, b):
    """risk-neutral: a size-up is leverage, not an idea. k = the variant's mean |$| on its trading days / the base's."""
    av, ab = np.abs(v[v != 0]), np.abs(b[b != 0])
    if not len(av) or not len(ab):
        return 1.0
    return float(av.mean() / ab.mean())


def wf_all():
    R = load_runs(); C = load_cells(); S = sessions(R)
    groups = collections.defaultdict(list)
    for r in R.values():
        groups[r["grp"]].append(r)
    for c in C.values():
        groups[c["grp"]].append(c)
    glob_b = [R[g] for g in GLOBAL_BASES if g in R]
    res = {}
    for g, mem in sorted(groups.items()):
        stored = ":" not in g
        cands = [m for m in mem if m.get("status") in ("info", "baseline") or BASE_RX.search(m["id"])] + glob_b if stored else []
        var, kinds, ks = {}, collections.Counter(), []
        for m in mem:
            if stored and m.get("status") not in KEEP:
                continue
            if not m.get("legal", True):
                continue
            b, bc = base_for(m, cands, S) if stored else (None, 0.0)
            v = vec(m, S)
            if b is not None:
                bv = b["_v"]
                k = scale_k(v, bv)
                ks.append(k)
                var[m["id"]] = v / k - bv
                kinds[b["id"]] += 1
            else:
                var[m["id"]] = v
                kinds["(stream)"] += 1
        if not var:
            continue
        oos, picks = walk_forward(var, np.zeros(len(S)), S)
        x = [v for _, v in oos]
        t, p = tstat(x)
        act = sum(1 for k in picks if k != "(no change)")
        top = collections.Counter(k for k in picks if k != "(no change)").most_common(3)
        kind = "stream" if kinds.most_common(1)[0][0] == "(stream)" else "mod"
        res[g] = {"kind": kind, "bases": dict(kinds), "n_var": len(var), "size_k_med": round(float(np.median(ks)), 2) if ks else None,
                  "oos_mo": round(float(np.mean(x)), 1), "t": round(t, 2), "p": p, "months": len(x), "active_months": act,
                  "ref": span_mean(oos, "2022-05", "2025-12"), "h1": span_mean(oos, "2026-01", "2026-06"),
                  "h2": span_mean(oos, "2026-07", "2026-10"),
                  "top_picks": top, "oos": oos, "picks": picks}
    N = len(res)
    for g, r in res.items():
        r["bonf_pass"] = r["p"] < 0.05 / N
        r["raw_pass"] = r["p"] < 0.05
    os.makedirs(OUT, exist_ok=True)
    json.dump({"N": N, "alpha": 0.05 / N, "fit_months": FIT, "first_test": FIRST_TEST, "end": END, "families": res},
              open(os.path.join(OUT, "wf.json" if FIT == 6 else f"wf_fit{FIT}.json"), "w"), indent=0)
    rows = sorted(res.items(), key=lambda kv: -kv[1]["oos_mo"])
    print(f"N families {N}, Bonferroni alpha {0.05 / N:.5f}")
    for g, r in rows[:45]:
        print(f"{g[:40]:40s} {r['kind']:6s} {str(r['size_k_med']):5s} v{r['n_var']:4d} OOS ${r['oos_mo']:8.1f}/mo t {r['t']:5.2f} p {r['p']:.4f}"
              f" ref {r['ref']} h1 {r['h1']} h2 {r['h2']} act {r['active_months']}/{r['months']} {'BONF' if r['bonf_pass'] else ('raw' if r['raw_pass'] else '')}")
    print("...", sum(r["bonf_pass"] for r in res.values()), "pass Bonferroni;", sum(r["raw_pass"] for r in res.values()), "raw p<0.05")


if __name__ == "__main__":
    {"wf": wf_all}[sys.argv[1]]()
