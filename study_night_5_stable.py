"""Night study 5 - what is stable across all four periods? (descriptive, default trades, flat sizing)

For the default configuration's taken trades, break the per-trade R down by exit reason, trigger type, grade, side,
session and first/second trade of the day, period by period. Then scan every recorded binary feature and keep only
those whose lift (avg R with the feature minus avg R without it) has the SAME SIGN in all four periods with at least
4 trades on each side in every period. Everything else is period-specific noise.
Also: does the grade (and therefore grade sizing) actually line up with outcomes in each period?
Run: python study_night_5_stable.py
"""
import numpy as np

from study_night_common import SEGS, run_both, seg_trades, md_table

MIN_N = 4


def _avg(tr):
    return (f"{np.mean([t['pnl_r'] for t in tr]):+.2f}R ({len(tr)})") if tr else "-"


def _breakdown(segs, title, keyf):
    keys = sorted({keyf(t) for tr, _ in segs.values() for t in tr}, key=str)
    rows = []
    for k in keys:
        rows.append([k] + [_avg([t for t in tr if keyf(t) == k]) for tr, _ in segs.values()])
    print(f"### {title}\n")
    print(md_table(rows, [title] + [lab for lab in segs]))
    print()


if __name__ == "__main__":
    res = run_both({})
    segs = seg_trades(res)
    print("# Study 5 - what holds in every period (default config, flat sizing)\n")
    print("Cells: average R per trade (number of trades).\n")
    _breakdown(segs, "exit reason", lambda t: t["exit_reason"])
    _breakdown(segs, "trigger", lambda t: t["trigger"])
    _breakdown(segs, "grade", lambda t: t["grade"])
    _breakdown(segs, "side", lambda t: "long" if t["dir"] == 1 else "short")
    _breakdown(segs, "session", lambda t: "PM" if t["features"].get("pm") else "AM")
    _breakdown(segs, "trade of day", lambda t: "2nd" if t["features"].get("x_second_trade") else "1st")
    _breakdown(segs, "regime", lambda t: t.get("regime", "?"))
    _breakdown(segs, "target", lambda t: "major pool" if t["features"].get("tgt_major") else ("R cap / fallback" if "R" in t["target_label"].split(" ")[0] else "other pool"))

    # ---- grade vs outcome: correlation of the grade multiplier with R per period
    print("### Grade sizing: does a higher grade mean a better trade?\n")
    rows = []
    for lab, (tr, _) in segs.items():
        m = np.array([t["grade_mult"] for t in tr]); r = np.array([t["pnl_r"] for t in tr])
        corr = float(np.corrcoef(m, r)[0, 1]) if len(tr) > 3 and m.std() > 0 else float("nan")
        flat = float(np.sum(r)); graded = float(np.sum(r * m))
        rows.append([lab, len(tr), f"{corr:+.2f}", f"{flat:+.1f}R", f"{graded:+.1f}R", f"{graded - flat:+.1f}R"])
    print(md_table(rows, ["period", "trades", "corr(grade mult, R)", "sum R flat", "sum R x grade mult", "grade sizing adds"]))
    print()

    # ---- sign-stable binary features among taken trades
    print("### Binary features whose lift has the same sign in all four periods (>= 4 trades each side per period)\n")
    feats = sorted({k for tr, _ in segs.values() for t in tr for k, v in t["features"].items() if v in (0, 1, True, False) and not isinstance(v, float)})
    rows = []
    for k in feats:
        cells, signs, ok = [], [], True
        for lab, (tr, _) in segs.items():
            a = [t["pnl_r"] for t in tr if t["features"].get(k) == 1]
            b = [t["pnl_r"] for t in tr if t["features"].get(k) in (0, -1, None)]
            if len(a) < MIN_N or len(b) < MIN_N:
                ok = False; break
            lift = float(np.mean(a) - np.mean(b)); signs.append(np.sign(lift))
            cells.append(f"{lift:+.2f} ({len(a)}v{len(b)})")
        if ok and len(set(signs)) == 1:
            rows.append([k, "+" if signs[0] > 0 else "-"] + cells)
    rows.sort(key=lambda r: r[1])
    print(md_table(rows, ["feature", "sign", *segs.keys()]) if rows else "(none)")
    print("\nlift = avg R when present minus avg R when absent; (present v absent) trade counts. A '-' sign means the trade does WORSE with the feature.")
