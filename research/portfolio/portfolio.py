"""Walk-forward portfolio search over every stored run (research/portfolio/DESIGN.md part 2). PAPER RESEARCH ONLY.
    python -X utf8 research/portfolio/portfolio.py  -> research/portfolio/results.json
The pick is computed and FROZEN (written to results.json["pick"]) before the hold-outs are scored in the same run.
"""
from __future__ import annotations

import glob
import json
import os

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(HERE, "results.json")
CORE = ("lit_live", "atlas_funded_live")
PICK = (("2021-11-08", "2024-12-31"), ("2026-01-01", "2026-06-30"))
HOLD = {"2025": ("2025-01-01", "2025-12-31"), "2026 Jul-Oct": ("2026-07-01", "2026-10-16")}
MAX_ADD, MIN_GAIN, UNIT = 6, 0.005, 0.25
ACCTS = {"Builder 50K": {"target": 3000, "mll": 2000, "lock": 100, "dll": 1000, "x": 1.0},
         "Builder 25K": {"target": 1500, "mll": 1000, "lock": 100, "dll": 600, "x": 0.5},
         "Rapid EOD 25K": {"target": 1500, "mll": 1000, "lock": 100, "dll": 500, "x": 0.5, "best": 0.30, "min_days": 4}}


def load():
    S = {}
    for f in sorted(glob.glob(os.path.join(ROOT, "research", "runs", "*.json"))):
        try:
            d = json.load(open(f, encoding="utf-8"))
        except (OSError, ValueError):
            continue
        ds = d.get("days")
        if not ds or ds[0][0] > "2021-12-31" or ds[-1][0] < "2026-10-01":
            continue
        S[os.path.basename(f)[:-5]] = {"family": d.get("family"), "notes": str(d.get("notes"))[:160],
                                       "rows": {r[0]: (float(r[1]), float(r[2]), int(r[3])) for r in ds}}
    return S


def mask(days, spans):
    return np.array([any(a <= d <= z for a, z in spans) for d in days])


def series(S, k, days):
    R = S[k]["rows"]
    p = np.array([R.get(d, (0, 0, 0))[0] for d in days])
    lo = np.array([R.get(d, (0, 0, 0))[1] for d in days])
    n = np.array([R.get(d, (0, 0, 0))[2] for d in days])
    return p, np.minimum(lo, np.minimum(p, 0)), n


def pf(p):
    g, l = p[p > 0].sum(), -p[p < 0].sum()
    return round(float(g / l), 2) if l else None


def sharpe(p):
    s = p.std()
    return float(p.mean() / s) if s else 0.0


def budget(p, lo, dll):
    """The shared soft daily loss: a day whose summed low reaches -DLL is paused at -DLL."""
    p = p.copy()
    hit = lo <= -dll
    p[hit] = -dll
    return p, np.maximum(lo, -dll)


def stats(p, n, days_m):
    eq = np.cumsum(p)
    dd = float((eq - np.maximum.accumulate(np.r_[0, eq])[1:]).min()) if len(p) else 0.0
    nd = int(days_m.sum())
    return {"sessions": nd, "trades": int(n.sum()), "tpw": round(float(n.sum()) / (nd / 5), 2), "pf": pf(p), "net": round(float(p.sum())),
            "per_month": round(float(p.sum()) / (nd / 21)), "max_dd": round(dd)}


def evals(p, lo, A, horizon=40):
    p, lo = p * A["x"], lo * A["x"]
    n = len(p)
    res = []
    for i in range(n):
        bal = peak = best = 0.0
        floor = -A["mll"]
        days = 0
        out = ("OPEN", None)
        for k in range(i, min(n, i + horizon)):
            dp, dl = p[k], lo[k]
            if dl <= -A["dll"]:
                dp, dl = -A["dll"], -A["dll"]
            if bal + dl <= floor:
                out = ("FAIL", k - i + 1); break
            bal += dp
            days += dp != 0
            best = max(best, dp)
            peak = max(peak, bal)
            floor = min(max(floor, peak - A["mll"]), A["lock"])
            ok = bal >= A["target"] and days >= A.get("min_days", 1) and (not A.get("best") or best <= A["best"] * bal)
            if ok:
                out = ("PASS", k - i + 1); break
        res.append(out + (n - i,))
    f10 = [r for r in res if r[2] >= 10] or res
    f40 = [r for r in res if r[2] >= horizon] or res
    pm = [r[1] for r in res if r[0] == "PASS"]
    return {"pass10": round(100 * sum(r[0] == "PASS" and r[1] <= 10 for r in f10) / len(f10), 1),
            "fail10": round(100 * sum(r[0] == "FAIL" and r[1] <= 10 for r in f10) / len(f10), 1),
            "pass40": round(100 * sum(r[0] == "PASS" for r in f40) / len(f40), 1),
            "fail40": round(100 * sum(r[0] == "FAIL" for r in f40) / len(f40), 1),
            "days_med": float(np.median(pm)) if pm else None}


def run(say=print):
    S = load()
    days = sorted({d for k in CORE for d in S[k]["rows"]})
    mP = mask(days, PICK)
    lit_p = series(S, "lit_live", days)[0]
    atl_p = series(S, "atlas_funded_live", days)[0]
    sd_lit = lit_p[mP].std()
    # ---------------- candidates (PICK only)
    C = {}
    for k, s in S.items():
        if k in CORE:
            continue
        p, lo, n = series(S, k, days)
        pp, nn = p[mP], n[mP]
        if nn.sum() < 100 or pp.sum() <= 0 or (pf(pp) or 0) < 1.10 or pp.std() == 0:
            continue
        c1, c2 = np.corrcoef(pp, lit_p[mP])[0, 1], np.corrcoef(pp, atl_p[mP])[0, 1]
        if not (abs(c1) < 0.30 and abs(c2) < 0.30):
            continue
        sc = UNIT * sd_lit / pp.std()
        C[k] = {"scale": sc, "corr_lit": round(float(c1), 3), "corr_atlas": round(float(c2), 3), "pf_pick": pf(pp),
                "family": s["family"], "notes": s["notes"]}
    say(f"pool {len(S)} runs, candidates after the PICK rule {len(C)}")
    core_p = lit_p + atl_p
    core_lo = series(S, "lit_live", days)[1] + series(S, "atlas_funded_live", days)[1]
    chosen, cur = [], core_p.copy()
    base_sh = sharpe(cur[mP])
    trace = [{"step": 0, "sharpe_pick": round(base_sh, 4)}]
    while len(chosen) < MAX_ADD:
        best, bk = None, None
        for k, c in C.items():
            if k in chosen:
                continue
            q = series(S, k, days)[0] * c["scale"]
            if any(abs(np.corrcoef(q[mP], series(S, j, days)[0][mP])[0, 1]) > 0.60 for j in chosen):
                continue
            sh = sharpe((cur + q)[mP])
            if best is None or sh > best:
                best, bk = sh, k
        if bk is None or best - sharpe(cur[mP]) < MIN_GAIN:
            break
        chosen.append(bk)
        cur = cur + series(S, bk, days)[0] * C[bk]["scale"]
        trace.append({"step": len(chosen), "add": bk, "sharpe_pick": round(best, 4)})
        say(f"  add {bk} (x{C[bk]['scale']:.2f}) -> PICK Sharpe {best:.4f}")
    pick = {"members": [{"run": k, **C[k]} for k in chosen], "trace": trace, "frozen_before_holdouts": True}
    # ---------------- score: core vs portfolio, every span
    port_p, port_lo, port_n = core_p.copy(), core_lo.copy(), series(S, "lit_live", days)[2] + series(S, "atlas_funded_live", days)[2]
    add_n = np.zeros(len(days))
    for k in chosen:
        p, lo, n = series(S, k, days)
        port_p += p * C[k]["scale"]; port_lo += lo * C[k]["scale"]; port_n += n; add_n += n
    core_n = series(S, "lit_live", days)[2] + series(S, "atlas_funded_live", days)[2]
    out = {"made": "2026-11-24", "design": "research/portfolio/DESIGN.md", "pool": len(S), "candidates": len(C), "pick": pick,
           "spans": {}}
    spans = {"PICK": PICK, **{k: (v,) for k, v in HOLD.items()}}
    for nm, sp in spans.items():
        m = mask(days, sp)
        row = {}
        for lab, p, lo, n in (("core LIT+ATLAS", core_p, core_lo, core_n), ("portfolio", port_p, port_lo, port_n)):
            pb, lb = budget(p[m], lo[m], 1000)
            row[lab] = {**stats(pb, n[m], m), "evals": {a: evals(p[m], lo[m], A) for a, A in ACCTS.items()}}
        row["add_ons_tpw"] = round(float(add_n[m].sum()) / (m.sum() / 5), 2)
        row["corr_add_ons_vs_core"] = round(float(np.corrcoef((port_p - core_p)[m], core_p[m])[0, 1]), 3) if chosen else None
        out["spans"][nm] = row
    why = []
    for h in HOLD:
        a, b = out["spans"][h]["portfolio"], out["spans"][h]["core LIT+ATLAS"]
        if a["net"] <= b["net"]:
            why.append(f"{h}: net ${a['net']:,} vs core ${b['net']:,}")
        if (a["pf"] or 0) < (b["pf"] or 0):
            why.append(f"{h}: PF {a['pf']} vs {b['pf']}")
        if a["max_dd"] < 1.25 * b["max_dd"]:
            why.append(f"{h}: max DD ${a['max_dd']:,} vs ${b['max_dd']:,}")
        e, f = a["evals"]["Builder 50K"], b["evals"]["Builder 50K"]
        if e["pass40"] < f["pass40"] or e["fail40"] > f["fail40"] + 2:
            why.append(f"{h}: 50K pass/fail {e['pass40']}/{e['fail40']} vs {f['pass40']}/{f['fail40']}")
        if not (2 <= out["spans"][h]["add_ons_tpw"] <= 6):
            why.append(f"{h}: add-ons {out['spans'][h]['add_ons_tpw']} trades/week")
    if not chosen:
        why.append("no candidate raised the PICK Sharpe")
    out["verdict"] = "needs-owner-yes" if not why else "FAIL: no portfolio beats today on both hold-outs"
    out["why"] = why
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, default=float)
    for nm, row in out["spans"].items():
        for lab in ("core LIT+ATLAS", "portfolio"):
            r = row[lab]
            e = r["evals"]
            say(f"{nm:13s} {lab:15s} {r['tpw']}/wk PF {r['pf']} ${r['net']:,} ${r['per_month']:,}/mo DD ${r['max_dd']:,} | "
                + " | ".join(f"{a} {e[a]['pass40']}/{e[a]['fail40']} {e[a]['days_med']}d" for a in ACCTS))
        say(f"{'':13s} add-ons {row['add_ons_tpw']}/wk, corr vs core {row['corr_add_ons_vs_core']}")
    say(f"VERDICT: {out['verdict']} | {'; '.join(why)}")
    return out


if __name__ == "__main__":
    run()
