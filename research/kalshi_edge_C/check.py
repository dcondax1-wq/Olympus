#!/usr/bin/env python3
"""Sanity checks for team C (offline, reads the committed snapshots and results). Exit code 1 on any failure.
    python research/kalshi_edge_C/check.py
"""
import glob, gzip, json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib_c as L

bad = 0


def ck(name, ok, extra=""):
    global bad
    print(("ok   " if ok else "FAIL ") + name + (" : " + str(extra) if extra else ""))
    bad += 0 if ok else 1


def main():
    files = sorted(glob.glob(os.path.join(L.DATA, "snap_*.jsonl.gz")))
    size = sum(os.path.getsize(f) for f in glob.glob(os.path.join(L.DATA, "*")))
    ck("data snapshots present and <= 8 MB", len(files) > 0 and size <= 8e6, f"{len(files)} files, {size/1e6:.2f} MB")
    # fee and pnl
    ck("fee 0.07*p*(1-p): 50c -> 1.75c, 95c -> 0.3325c", abs(L.fee(0.5) - 0.0175) < 1e-12 and abs(L.fee(0.95) - 0.003325) < 1e-12)
    ck("taker sides: buy yes at the ask, buy no at 1 - bid, wide spread skipped",
       L.sides(0.40, 0.42) == [("yes", 0.42), ("no", 0.6)] and L.sides(0.40, 0.50) == [] and L.sides(0.0, 0.01) == [("yes", 0.01)])
    # weather events: exactly one bucket wins; the settlement value sits inside the winning bucket
    import weather as W
    n_ev = n_bad = n_in = n_chk = 0
    for s in W.GROUPS["weather_main"] + W.GROUPS["weather_rep"] + W.GROUPS["weather_low"]:
        for d, ev in W.build_events(s).items():
            if len(ev["ms"]) < 4:
                continue
            n_ev += 1
            y = [r for r in ev["ms"] if r["res"] == "yes"]
            n_bad += len(y) != 1
            if len(y) == 1 and ev["exact"]:
                a, b = W.bounds(y[0]); n_chk += 1; n_in += a <= ev["act"] <= b
    ck("weather: one winning bucket per city-day", n_ev > 0 and n_bad <= 0.01 * n_ev, f"{n_ev} city-days, {n_bad} odd")
    ck("weather: settlement temperature lies in the winning bucket (strike parsing)", n_chk > 0 and n_in >= 0.99 * n_chk, f"{n_in}/{n_chk}")
    ck("normal bucket probabilities sum to 1", abs(sum(W.prob(60.3, 2.1, a, b) for a, b in [(-99, 55), (56, 57), (58, 59), (60, 61), (62, 63), (64, 199)]) - 1) < 1e-9)
    # cluster statistic: a fair coin bought at fair price minus fee has a negative edge and |t| small-ish
    rng = np.random.default_rng(1)
    p = np.full(4000, 0.5); win = (rng.random(4000) < 0.5).astype(float); cl = np.arange(4000) // 10
    n, ncl, e, t = L.cell_stats(win - p - L.fee(p), p, cl)
    ck("cell_stats on a fair coin: edge about -3.5% (the fee), 400 clusters", ncl == 400 and -0.09 < e < 0.02, f"edge {e:.4f} t {t:.2f}")
    # results and rules agree
    rp = os.path.join(L.HERE, "edge_rules_C.json")
    if os.path.exists(rp):
        rules = json.load(open(rp))
        surv = 0
        for fn, key in (("results_weather.json", "main"), ("results_index.json", "spx")):
            f = os.path.join(L.HERE, fn)
            if os.path.exists(f):
                surv += len(json.load(open(f))["families"].get(key, {}).get("survive", []))
        f = os.path.join(L.HERE, "results_other.json")
        if os.path.exists(f):
            surv += len(json.load(open(f)).get("family", {}).get("survive", []))
        ck("edge_rules_C.json status matches the results", (rules["status"] == "no_edge_found") == (len(rules["rules"]) == 0) and rules["mode"] == "paper"
           and (surv > 0 or rules["status"] == "no_edge_found"), f"status {rules['status']}, cells surviving the held-out block {surv}")
        ck("paper only: no order routing in the rules file", "NONE" in json.dumps(rules.get("forward_paper_test", {})).upper() or rules["status"] == "no_edge_found")
    print("FAILED" if bad else "ALL OK")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
