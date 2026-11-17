#!/usr/bin/env python3
"""K4 idea 2: favourite-longshot bias in Kalshi sports winner markets, by sport x time to start x price band.
Taker at the ask, fee 0.07 p(1-p) rounded up on a $10 order, spread <= 6c. Train = games starting before SPLIT,
test = from SPLIT (read once). Cluster = the game (event). A cell is carried to the test only if its train t beats the
Bonferroni bar over all eligible cells (n_train >= 100). Pre-registered pooled ideas are reported too.
    python research/kalshi_edge_K4/sports_study.py   -> results_sports.json
"""
import json
import os
import statistics
from collections import defaultdict
from datetime import datetime, timezone

from lib import summary
from sports_units import band, load, units

HERE = os.path.dirname(os.path.abspath(__file__))
SPLIT = datetime(2026, 10, 26, tzinfo=timezone.utc).timestamp()
NORM_Z = {1: 1.645}


def zbar(k, alpha=0.05):
    """one-sided Bonferroni z for k cells."""
    a = alpha / max(k, 1)
    lo, hi = 0.0, 10.0
    for _ in range(60):
        mid = (lo + hi) / 2
        tail = 0.5 * math_erfc(mid / 2 ** 0.5)
        lo, hi = (mid, hi) if tail > a else (lo, mid)
    return hi


def math_erfc(x):
    import math
    return math.erfc(x)


def days(rows):
    if not rows:
        return 1
    return (max(r["ts"] for r in rows) - min(r["ts"] for r in rows)) / 86400 + 1


def main():
    U = units(load())
    tr = [u for u in U if u["ts"] < SPLIT]
    te = [u for u in U if u["ts"] >= SPLIT]
    dtr, dte = days(tr), days(te)
    out = {"n_units": len(U), "train_days": dtr, "test_days": dte, "split": "2026-10-26",
           "train_from": datetime.fromtimestamp(min(u["ts"] for u in tr), timezone.utc).date().isoformat(),
           "test_to": datetime.fromtimestamp(max(u["ts"] for u in te), timezone.utc).date().isoformat()}
    # pooled, pre-registered ideas (no search): favourite / longshot by horizon, all sports
    pre = {}
    for name, f in (("buy favourite 75-90c, pregame (pre24/pre6/pre1/start)", lambda u: u["h"].startswith("pre") or u["h"] == "start"),
                    ("buy favourite 75-90c, in-game", lambda u: u["h"].startswith("in"))):
        a = [u for u in tr if 0.75 <= u["p"] < 0.90 and f(u)]
        b = [u for u in te if 0.75 <= u["p"] < 0.90 and f(u)]
        pre[name] = {"train": summary(a, dtr), "test": summary(b, dte)}
    for lo, hi in ((0.90, 0.98), (0.02, 0.25), (0.40, 0.60)):
        for hz in ("pregame", "in-game"):
            f = (lambda u: not u["h"].startswith("in")) if hz == "pregame" else (lambda u: u["h"].startswith("in"))
            a = [u for u in tr if lo <= u["p"] < hi and f(u)]
            b = [u for u in te if lo <= u["p"] < hi and f(u)]
            pre["buy %d-%dc, %s" % (lo * 100, hi * 100, hz)] = {"train": summary(a, dtr), "test": summary(b, dte)}
    out["pooled"] = pre
    # calibration table (all horizons pooled, by band): win rate vs price
    cal = {}
    for split_name, S in (("train", tr), ("test", te)):
        g = defaultdict(list)
        for u in S:
            g[band(u["p"])].append(u)
        cal[split_name] = {k: {"n": len(v), "price": statistics.mean(x["p"] for x in v),
                               "win": sum(x["won"] for x in v) / len(v), "edge": statistics.mean(x["r"] for x in v)}
                           for k, v in sorted(g.items())}
    out["calibration"] = cal
    # cell search: sport x horizon x band
    cells = defaultdict(list)
    for u in tr:
        cells[(u["sport"], u["h"], band(u["p"]))].append(u)
    elig = {k: v for k, v in cells.items() if len(v) >= 100}
    z = zbar(len(elig))
    scored = []
    for k, v in elig.items():
        s = summary(v, dtr)
        scored.append((s["t"], k, s))
    scored.sort(reverse=True)
    out["cells"] = {"eligible": len(elig), "z_bar": z, "top": [], "carried": []}
    for t, k, s in scored[:10]:
        out["cells"]["top"].append({"cell": "|".join(k), "train": s})
    for t, k, s in scored:
        if t >= z:
            b = [u for u in te if (u["sport"], u["h"], band(u["p"])) == k]
            out["cells"]["carried"].append({"cell": "|".join(k), "train": s, "test": summary(b, dte)})
    # also: by sport (all horizons, favourite side >= 60c)
    bys = {}
    for sp in sorted({u["sport"] for u in U}):
        a = [u for u in tr if u["sport"] == sp and u["p"] >= 0.6]
        b = [u for u in te if u["sport"] == sp and u["p"] >= 0.6]
        bys[sp] = {"train": summary(a, dtr), "test": summary(b, dte)}
    out["by_sport_fav60"] = bys
    with open(os.path.join(HERE, "results_sports.json"), "w") as f:
        json.dump(out, f, indent=1)
    fmt = lambda s: "n %5d edge %+6.2f%% [%+6.2f, %+6.2f] t %+5.2f win %s" % (
        s["n"], 100 * s["edge"], 100 * s["lo"], 100 * s["hi"], s["t"], s["win"] and round(s["win"], 3)) if s["n"] else "n 0"
    print("units", len(U), "train days", round(dtr), "test days", round(dte))
    for k, v in pre.items():
        print("%-58s TR %s | TE %s" % (k, fmt(v["train"]), fmt(v["test"])))
    for k, v in bys.items():
        print("%-10s fav>=60 TR %s | TE %s" % (k, fmt(v["train"]), fmt(v["test"])))
    print("eligible cells", len(elig), "z bar", round(z, 2))
    for c in out["cells"]["top"]:
        print("  top", c["cell"], fmt(c["train"]))
    for c in out["cells"]["carried"]:
        print("  CARRIED", c["cell"], fmt(c["train"]), "| TE", fmt(c["test"]))


if __name__ == "__main__":
    main()
