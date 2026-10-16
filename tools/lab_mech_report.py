"""MECH track: print markdown tables from research/lab/MECH_results.json (pasted into MECH_REPORT.md)."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tools.strategy_lab import OUT  # noqa: E402

with open(os.path.join(OUT, "MECH_results.json"), encoding="utf-8") as fh:
    R = json.load(fh)

PER = ["ytd", "aug_oct", "y2025", "all18m"]
for sym in ("NQ", "ES"):
    print(f"\n### {sym}\n")
    print("| variant | period | trades | /wk | win % | avg R [95% CI] | PF | net $ | max DD $ | worst day $ | 50K pass % | zero-edge % | edge pts |")
    print("|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|")
    for name, res in R.items():
        if not name.startswith(f"MECH_{sym}_"):
            continue
        v = name.split("_", 2)[2]
        for p in PER:
            s = res[p]
            ci = s["ci95_r"]
            cis = f"[{ci[0]:+.2f}, {ci[1]:+.2f}]" if ci and ci[0] is not None else ""
            rp, zp = s["rolling_pass"], s["zero_edge_pass"]
            fmt = lambda x: "n/a" if x is None else f"{x}"  # noqa: E731
            edge = "n/a" if rp is None or zp is None else f"{rp - zp:+.1f}"
            print(f"| {v} | {p} | {s['trades']} | {s['tpw']} | {s['win_rate']} | {s['avg_r']:+.3f} {cis} | {s['pf']} | "
                  f"{s['net']:+,.0f} | {s['max_dd']:,.0f} | {s['worst_day']:,.0f} | {fmt(rp)} | {fmt(zp)} | {edge} |")
for sym in ("NQ", "ES"):
    names = [n for n in R if n.startswith(f"MECH_{sym}_")]
    months = sorted({m for n in names for m in R[n]["ytd"]["months"]})
    print(f"\n### {sym} 2026 by month (trades / net $)\n")
    print("| variant | " + " | ".join(months) + " |")
    print("|---|" + "---:|" * len(months))
    for n in names:
        mm = R[n]["ytd"]["months"]
        cells = [f"{mm[m]['trades']} / {mm[m]['net']:+,.0f}" if m in mm else "0 / 0" for m in months]
        print(f"| {n.split('_', 2)[2]} | " + " | ".join(cells) + " |")
print("\n### descriptive (all18m)\n")
for n, res in R.items():
    print(f"- {n}: exits {res['exit_kinds']}, long/short {res['long_short']}, median stop {res['median_stop_pts']} pts, "
          f"levels {dict(sorted(res['levels'].items(), key=lambda z: -z[1]))}")
