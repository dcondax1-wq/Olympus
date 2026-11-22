"""Robustness for the one-account book shortlist (labelled post-hoc checks, not the pick):
(1) paired per-path difference vs today's setup (same paths) with its standard error, (2) ATLAS's 5 best Jul-Oct days removed
(the 2026-11-19 red-team break), (3) 2022 alone.   python -X utf8 research/onebook/robust.py -> research/onebook/robust.json"""
import collections
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import book as B  # noqa: E402

R, SOA, U = B.R, B.SOA, B.U
SHORT = [("mffu_rapid_eod_50k", "B11 size split: LIT x0.5 in the eval"),
         ("mffu_rapid_eod_50k", "B09 LIT eval, LIT + ATLAS once funded"),
         ("mffu_rapid_eod_50k", "B03 LIT + ATLAS first-come"),
         ("mffu_builder_50k", "B08 ATLAS x0.5 in the eval, full funded"),
         ("mffu_builder_50k", "B05 time split: ATLAS NY only (from 09:30)"),
         ("mffu_builder_50k", "B09 LIT eval, LIT + ATLAS once funded"),
         ("mffu_builder_50k", "B03 LIT + ATLAS first-come")]
TODAY = [("mffu_builder_50k", "B01 LIT only"), ("mffu_builder_25k", "B02 ATLAS only")]


def nets(plan, bk, paths, drop=()):
    sp = B.build(plan, bk)
    if drop:
        for k in ("BYe", "BYf"):
            sp[k] = [[t for t in ts if not (t["strat"] == "ATLAS" and t["day"] in drop)] for ts in sp[k]]
    B.CFG.clear(); B.CFG.update(sp["knobs"])
    out = np.array([R.slot_run(sp, [p])["net_6m"] for p in paths], dtype=float)
    B.CFG.clear()
    return out


def atlas_top_days(span, k=5):
    a, z = R.U.SPAN[span]
    by = collections.defaultdict(float)
    for d, ts in SOA.data()["OTHER"].items():
        if a <= d <= z:
            for t in ts:
                if t["strat"] == "ATLAS":
                    by[d] += t["pts"] / max(t["risk"], 1e-9)
    return set(sorted(by, key=lambda d: -by[d])[:k])


def main(n=1000):
    S = SOA.data()["S"]
    U.SPAN["Y2022"] = ("2022-01-01", "2022-12-31")
    spans = ("H1", "H2", "REF", "Y2022")
    PF = {s: U.mc_paths(S, s, n, length=R.LEN, seed=23) for s in spans}
    top = atlas_top_days("H2")
    out = {"atlas_top5_h2_days": sorted(top), "rows": {}}
    T = {s: sum(nets(p, b, PF[s]) for p, b in TODAY) for s in spans}
    Td = sum(nets(p, b, PF["H2"], drop=top) for p, b in TODAY)
    for plan, bk in SHORT:
        r = {}
        for s in spans:
            x = nets(plan, bk, PF[s])
            d = x - T[s]
            r[s] = {"net_6m": round(float(x.mean())), "today_6m": round(float(T[s].mean())), "diff_6m": round(float(d.mean())),
                    "se": round(float(d.std(ddof=1) / np.sqrt(len(d)))), "p_worse": round(100.0 * float((d < 0).mean()), 1)}
        xd = nets(plan, bk, PF["H2"], drop=top)
        dd = xd - Td
        r["H2_no_atlas_top5"] = {"net_6m": round(float(xd.mean())), "today_6m": round(float(Td.mean())),
                                 "diff_6m": round(float(dd.mean())), "se": round(float(dd.std(ddof=1) / np.sqrt(len(dd))))}
        out["rows"][f"{plan} | {bk}"] = r
        print(plan, bk, " | ".join(f"{s} {r[s]['net_6m']} vs {r[s]['today_6m']} diff {r[s]['diff_6m']}+-{r[s]['se']} worse {r[s]['p_worse']}%"
                                   for s in spans), "| H2 -top5", r["H2_no_atlas_top5"], flush=True)
    json.dump(out, open(os.path.join(HERE, "robust.json"), "w"), indent=1, default=float)


if __name__ == "__main__":
    main()
