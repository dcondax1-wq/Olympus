"""CONT track: report tables from research/lab/CONT_summary.json + CONT_trades/, plus two diagnostics with the SAME rules:
gross-of-cost R per variant, and NQ's older history (2021-11..2025-04) as an extra out-of-sample look. Nothing is tuned."""
import collections
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools import strategy_lab as sl  # noqa: E402
from tools.lab_models import continuation as m  # noqa: E402

OUT = os.path.join(ROOT, "research", "lab")


def gross_r(tr):
    """R before commission and slippage (fills at the model prices)."""
    out = []
    for t in tr:
        pts = (t["exit"] - t["entry"]) * t["dir"]
        out.append(pts / t["risk_pts"] if t["risk_pts"] else 0.0)
    return out


def main():
    S = json.load(open(os.path.join(OUT, "CONT_summary.json"), encoding="utf-8"))
    print("| variant | period | trades | /wk | weeks>=1 % | win % | avg R [95% CI] | PF | net $ | max DD $ | worst day $ | 50K pass % (zero-edge) | b2b |")
    for name, per in S.items():
        for p in ("ytd", "aug_oct", "y2025", "all18m"):
            s = per[p]
            ps = "n/a (0 evals finished)" if s["rolling_pass"] is None else f"{s['rolling_pass']} ({s['zero_edge_pass']})"
            print(f"| {name} | {p} | {s['trades']} | {s['tpw']} | {s['weeks_ge1']:.0f} | {s['win_rate']} | {s['avg_r']:+.3f} {s['ci95_r']} | "
                  f"{s['pf']} | {s['net']:+,.0f} | {s['max_dd']:,.0f} | {s['worst_day']:,.0f} | {ps} | {s['b2b_pass']}/{s['b2b_fail']} |")
    print()
    for name, per in S.items():
        s = per["all18m"]
        print(name, "exits", s["exits"], "long", s["long_n"], s["long_net"], "short", s["short_n"], s["short_net"],
              "median risk pts", s["median_risk_pts"], "avg qty", s["avg_qty"], "quarters", s["quarters"])
    print()
    # monthly 2026
    months = [f"2026-{k:02d}" for k in range(1, 11)]
    print("| variant | " + " | ".join(mm[5:] for mm in months) + " |")
    for name, per in S.items():
        ms = per["ytd"]["months"]
        cells = [f"{ms[mm]['net']:+,.0f} ({ms[mm]['trades']})" if mm in ms else "0 (0)" for mm in months]
        print(f"| {name} | " + " | ".join(cells) + " |")
    print()
    # gross-of-cost R (all18m)
    for name in S:
        tr = json.load(open(os.path.join(OUT, "CONT_trades", f"{name}.json"), encoding="utf-8"))
        tr = [t for t in tr if "2025-04-14" <= t["day"] <= "2026-10-16"]
        g = gross_r(tr)
        net = [t["r"] for t in tr]
        cost = [(t["pnl"] - (t["exit"] - t["entry"]) * t["dir"] * sl.PV[t["sym"]] * t["qty"]) for t in tr]
        if tr:
            print(f"{name}: all18m gross avg R {sum(g) / len(g):+.3f} vs net {sum(net) / len(net):+.3f}; "
                  f"costs ${-sum(cost):,.0f} over {len(tr)} trades (${-sum(cost) / len(tr):,.0f}/trade)")
    print()
    # NQ older history, same rules, stats only (no files written)
    b = sl.bars("NQ", "5m", "2021-11-01", "2025-04-11", warmup_days=14)
    a, z = "2021-11-01", "2025-04-11"
    print(f"NQ extra history {a}..{z}: {len(b)} bars")
    for v in m.VARIANTS:
        tr = m.run(b, {"variant": v, "sym": "NQ"})
        s = sl.stats(tr, a, z)
        q = collections.defaultdict(float)
        for t in tr:
            if a <= t["day"] <= z:
                q[t["day"][:4]] += t["pnl"]
        ps = "n/a" if s["rolling_pass"] is None else f"{s['rolling_pass']} ({s['zero_edge_pass']})"
        g = gross_r([t for t in tr if a <= t["day"] <= z])
        print(f"| CONT_NQ_{v} | 2021-11..2025-04 | {s['trades']} | {s['tpw']} | {s['win_rate']} | {s['avg_r']:+.3f} {s['ci95_r']} | "
              f"{s['pf']} | {s['net']:+,.0f} | {s['max_dd']:,.0f} | {ps} | gross avgR {sum(g) / max(len(g), 1):+.3f} | by year "
              + ", ".join(f"{k} {v2:+,.0f}" for k, v2 in sorted(q.items())) + " |")


if __name__ == "__main__":
    main()
