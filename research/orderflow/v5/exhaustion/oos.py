"""Out-of-sample scorer for the FROZEN v5 exhaustion variants (frozen.json). Scores only pc_days days NOT in the in-sample list.
PAPER ONLY. Usage: python -X utf8 research/orderflow/v5/exhaustion/oos.py [--holdout-last N]  (N = mock split check only)."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import core as X  # noqa: E402


def main():
    fr = json.load(open(os.path.join(X.HERE, "frozen.json")))
    ins = set(fr["in_sample_days"])
    D, usable = X.LC.load_days()
    if "--holdout-last" in sys.argv:                                    # mock check: pretend the last N in-sample days are new
        n = int(sys.argv[sys.argv.index("--holdout-last") + 1])
        ins = set(sorted(ins)[:-n])
    days = [d for d in usable if d not in ins]
    if not days:
        print("no out-of-sample days yet (pull the new real days into data/pc_days first)"); return
    rows = []
    for vid in fr["variants"]:
        c = X.run_variant(D, days, vid)
        rows.append((vid, X.score(c, days)))
    hp = X.holm({v: s["placebo_p"] for v, s in rows})
    for v, s in rows:
        s["holm_p"] = hp[v]; s["verdict"] = X.verdict(s, hp[v])
    print(f"OUT-OF-SAMPLE days {len(days)} ({days[0]}..{days[-1]}); frozen {list(fr['variants'])}; Holm over {len(rows)}")
    print(X.table(rows))
    for v, s in rows:
        print(f"  {v}: $ at $500 risk {s['usd500']:+,.0f}; targets {s['targets']}; pool as if all taken mean R {s['pool_all_R']}")
    json.dump({"days": days, "variants": dict(rows)}, open(os.path.join(X.HERE, "oos_results.json"), "w"), indent=1, default=str)


if __name__ == "__main__":
    main()
