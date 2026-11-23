"""Stage 3: ranked table for research/writeups/retest-new-standards-2026-11-23.md -> research/retest/summary.json + markdown.
    python -X utf8 tools/retest/report.py
"""
import glob, json, math, os, sys
import re
import numpy as np
HINDSIGHT = re.compile(r"(pick|best|plateau|joint|_book|robust|_rec$|final|winner|combo)")
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(os.path.dirname(HERE))
OUT = os.path.join(ROOT, "research", "retest")
SP = ("REF", "H1", "H2")
PAIR = {"b50|Z+P|own": "b50|Z|own", "b50|Z+A+P|own": "b50|Z+A|own", "b25|Z+A+P|own": "b25|Z+A|own", "r25|Z+A+P|lanes": "r25|Z+A|lanes"}
ACCT = {"r25|Z+A+P|lanes": "Rapid 25K", "b25|Z+A+P|own": "Builder 25K", "b50|Z+A+P|own": "Builder 50K", "b50|Z+P|own": "Builder 50K (Z only)"}


def fk(f):
    return f.replace(":", "_").replace("/", "_")


def main():
    W = json.load(open(os.path.join(OUT, "wf.json")))
    N, alpha = W["N"], W["alpha"]
    base = json.load(open(os.path.join(OUT, "acct_none.json")))["rows"]
    S = []
    fams = list(W["families"].items()) + [(os.path.basename(p)[5:-5], None) for p in glob.glob(os.path.join(OUT, "acct_fixed=*.json"))]
    for g, r in fams:
        if r is None:                                   # a fixed pre-declared rule (no selection): accounts only
            r = {"kind": "fixed", "n_var": 1, "oos_mo": 0.0, "p": 1.0, "t": 0.0, "ref": None, "h1": None, "h2": None,
                 "top_picks": [], "picks": []}
        row = {"family": g, "kind": r["kind"], "n_var": r["n_var"], "oos_mo": r["oos_mo"], "p": r["p"], "t": r["t"],
               "ref": r["ref"], "h1": r["h1"], "h2": r["h2"], "bonf": r["p"] < alpha, "raw": r["p"] < 0.05,
               "s1": all((r[k] or 0) > 0 for k in ("ref", "h1", "h2")), "top": r["top_picks"][:1],
               "hindsight": round(sum(1 for k in r["picks"] if k != "(no change)" and HINDSIGHT.search(k.split(":")[-1])) /
                                  max(1, sum(1 for k in r["picks"] if k != "(no change)")), 2)}
        pa = os.path.join(OUT, f"acct_{fk(g)}.json")
        if os.path.exists(pa):
            A = json.load(open(pa))
            acc = {}
            for key, bk in PAIR.items():
                if key not in A["rows"]:
                    continue
                d = {}
                for sp in SP:
                    c, b = np.array(A["rows"][key][sp]["net"]), np.array(base[bk][sp]["net"])
                    diff = c - b
                    se = diff.std(ddof=1) / math.sqrt(len(diff))
                    cs, bs = A["rows"][key][sp]["slot"], base[bk][sp]["slot"]
                    d[sp] = {"gain": round(float(diff.mean())), "z": round(float(diff.mean() / se), 2) if se else 0.0,
                             "net": cs["net_m"], "base": bs["net_m"], "p_neg": cs["p_neg"], "p_neg_base": bs["p_neg"],
                             "p10": cs["p10_m"], "p10_base": bs["p10_m"], "pass_med": cs["eval"]["pass_med"],
                             "pass_med_base": bs["eval"]["pass_med"], "pay_med": cs["first_pay_med"], "pay_med_base": bs["first_pay_med"],
                             "f10": cs["eval"]["f10"], "f10_base": bs["eval"]["f10"]}
                good = all(d[s]["z"] > 2 for s in SP)
                smooth = all(d[s]["gain"] >= -25 and d[s]["p_neg"] <= d[s]["p_neg_base"] and d[s]["p10"] >= d[s]["p10_base"] for s in SP) and any(d[s]["p10"] > d[s]["p10_base"] + 25 for s in SP)
                acc[key] = {"spans": d, "beats": good, "smooths": smooth}
            for key in ("b25|P|own", "r25|P|own"):
                if key in A["rows"]:
                    acc[key] = {"spans": {sp: {"net": A["rows"][key][sp]["slot"]["net_m"], "pass_med": A["rows"][key][sp]["slot"]["eval"]["pass_med"],
                                               "pay_med": A["rows"][key][sp]["slot"]["first_pay_med"], "p_neg": A["rows"][key][sp]["slot"]["p_neg"]} for sp in SP}}
                    acc[key]["alone_positive"] = all(acc[key]["spans"][s]["net"] > 0 for s in SP)
            row["acct"] = acc
            ov = A.get("overlap", {})
            row["overlap"] = {sp: {"p_days": v["p_days"], "same_day": v["same_day_as_ZA"],
                                   "tpw": (v["P_plain"] or {}).get("tpw"), "p_dd": (v["P_plain"] or {}).get("max_dd"),
                                   "p_mo_250": (v["P_plain"] or {}).get("per_month")} for sp, v in ov.items()}
        S.append(row)
    S.sort(key=lambda x: -x["oos_mo"])
    json.dump({"N": N, "alpha": alpha, "rows": S}, open(os.path.join(OUT, "summary.json"), "w"), indent=1)
    for r in S[:40]:
        a = r.get("acct", {})
        def cell(k):
            if k not in a:
                return "-"
            d = a[k]["spans"]
            return "/".join(f"{d[s]['gain']:+d}" for s in SP) + (" BEATS" if a[k]["beats"] else "") + (" smooth" if a[k]["smooths"] else "")
        print(f"{r['family'][:34]:34s} {r['kind']:6s} {r['oos_mo']:7.0f} p{r['p']:.4f} {'B' if r['bonf'] else ('r' if r['raw'] else ' ')} "
              f"{'S1' if r['s1'] else '  '} | R25 {cell('r25|Z+A+P|lanes')} | B25 {cell('b25|Z+A+P|own')} | B50 {cell('b50|Z+A+P|own')} | B50Z {cell('b50|Z+P|own')}")


if __name__ == "__main__":
    main()
