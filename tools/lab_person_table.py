"""PERSON track: print the variant table (dev / confirm / ytd / aug_oct / y2025) and 2026 monthly nets from the
research/lab/P_<variant>__<period>.json scorecards written by tools/lab_person_run.py.

  python tools/lab_person_table.py [best_variant]
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tools.lab_person_run import VARIANTS  # noqa: E402

OUT = os.path.join(ROOT, "research", "lab")
PERIODS = ("dev", "confirm", "ytd", "aug_oct", "y2025")
MONTHS = [f"2026-{m:02d}" for m in range(1, 11)]


def load(v, per):
    f = os.path.join(OUT, f"P_{v}__{per}.json")
    if not os.path.exists(f):
        return None
    with open(f, encoding="utf-8") as fh:
        return json.load(fh)


def cell(s):
    if not s:
        return "-"
    pf = s["pf"] if s["pf"] is not None else "-"
    return (f"{s['trades']} ({s['tpw']}/wk) PF {pf} {s['net']:+,.0f} DD {s['max_dd']:,.0f} "
            f"pass {s['rolling_pass']}% ({s['zero_edge_pass']})")


def compact():
    """One row per variant: dev / confirm / ytd / y2025 side by side."""
    print("| variant | dev net (PF) | confirm net (PF) | ytd trades (/wk) | ytd PF | ytd net | ytd max DD | "
          "50K pass % (zero-edge) | losing months 2026 | y2025 net (PF) |")
    print("|---|---:|---:|---:|---:|---:|---:|---|---:|---:|")
    f = lambda s: f"{s['net']:+,.0f} ({s['pf']})"
    for v in VARIANTS:
        d, c, y, z = (load(v, p) for p in ("dev", "confirm", "ytd", "y2025"))
        if not (d and c and y and z):
            continue
        print(f"| {v} | {f(d)} | {f(c)} | {y['trades']} ({y['tpw']}) | {y['pf']} | {y['net']:+,.0f} | {y['max_dd']:,.0f} | "
              f"{y['rolling_pass']} ({y['zero_edge_pass']}) | {y['losing_months']} | {f(z)} |")


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "compact":
        return compact()
    rows = ["| variant | period | trades | /wk | win % | avg R | PF | net $ | max DD $ | 50K pass % (zero-edge) | losing months | weeks 2-5 % |",
            "|---|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|"]
    for v in VARIANTS:
        for per in PERIODS:
            s = load(v, per)
            if not s:
                continue
            rows.append(f"| {v} | {per} | {s['trades']} | {s['tpw']} | {s['win_rate']} | {s['avg_r']:+.3f} | {s['pf']} | "
                        f"{s['net']:+,.0f} | {s['max_dd']:,.0f} | {s['rolling_pass']} ({s['zero_edge_pass']}) | "
                        f"{s['losing_months']} | {s['weeks_in_2_5']:.0f} |")
    print("\n".join(rows))
    print()
    hdr = "| variant | " + " | ".join(m[5:] for m in MONTHS) + " | losing |"
    print(hdr)
    print("|---|" + "---:|" * (len(MONTHS) + 1))
    for v in VARIANTS:
        s = load(v, "ytd")
        if not s:
            continue
        ms = s.get("months", {})
        vals = [ms.get(m, {}).get("net", 0.0) for m in MONTHS]
        print(f"| {v} | " + " | ".join(f"{x:+,.0f}" for x in vals) + f" | {sum(1 for x in vals if x < 0)} |")
    print()
    print("| variant (sum of R) | " + " | ".join(m[5:] for m in MONTHS) + " | total R | trades/wk |")
    print("|---|" + "---:|" * (len(MONTHS) + 2))
    for v in VARIANTS:
        f = os.path.join(OUT, f"P_{v}_trades_ytd.json")
        s = load(v, "ytd")
        if not os.path.exists(f) or not s:
            continue
        with open(f, encoding="utf-8") as fh:
            tr = json.load(fh)
        rs = [sum(t["r"] for t in tr if t["day"][:7] == m and t["day"] >= "2026-01-02") for m in MONTHS]
        print(f"| {v} | " + " | ".join(f"{x:+.1f}" for x in rs) + f" | {sum(rs):+.1f} | {s['tpw']} |")


if __name__ == "__main__":
    main()
